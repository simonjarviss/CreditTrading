"""Event counts behind the credit / calendar / macro special-situations catalogue.

    python3 scripts/events/ss_credit_catalogue_counts.py             # repo panels only, no network
    export QUANTT_ENV_FILE=<absolute path to the env file holding the Alpaca keys>
    python3 scripts/events/ss_credit_catalogue_counts.py --alpaca    # + one read-only GET /v2/assets

WHAT THIS IS
------------
`results/events/SPECIAL_SITUATIONS_CATALOGUE_CREDIT_2026-10-15.md` ranks event
and calendar sub-strategies by breadth x edge x feasibility. Breadth needs a
count: how many events a year, and how many of them are independent. This
script produces every count that note quotes, from panels already in `data/`
(each section names its panel and prints the panel's last date, because stale
is a form of wrong) and, with `--alpaca`, from one read-only asset-list GET.

ZERO TRIALS. It computes no return, no P&L and no Sharpe of any strategy. The
only market quantity it touches is the HYG/JNK premium/discount (price / NAV - 1,
a level, not a return), counted as stress days and episodes. Nothing is placed,
replaced or cancelled: the only network call is `GET /v2/assets` on the paper
endpoint, through `quantt.broker.alpaca.AlpacaClient` (which refuses any other
endpoint and scrubs keys from errors). Keys are never printed.

WHY EACH COUNT IS DEFINED THE WAY IT IS
--------------------------------------
* **Independent groups.** A fallen-angel "event" in a bond panel is one CUSIP,
  but one issuer's downgrade moves every CUSIP it has, in one month. The unit
  of independence is the issuer-month, and the months themselves cluster (2005-05,
  2008-09, 2020). So both are printed, plus the share of events in the five
  busiest months: a high share means the breadth is mostly a few crises (D6).
* **TRACE grade-flag flips (`data/forced_flow2/m6_events.parquet`).** This is the
  LEGACY S3 study's event set (`docs/RESEARCH_STATE.md` WATCH, S3-forced-flow;
  read by `pre-clean-slate:scripts/s3/fallen_angel_event_study.py`). Its event is
  a flip of TRACE's own `grade` flag from I to H, which is NOT the index
  providers' rule (Bloomberg uses the middle of Moody's, S&P and Fitch). The
  counts are printed as that panel defines them and labelled so.
* **NRSRO 17g-7 histories (`data/agency_actions_17g7.parquet`).** Moody's and
  Fitch instrument-level actions; `is_ig_to_hy` is an IG -> HY crossing by that
  one agency. One agency's crossing is not an index exit either. The histories
  are published with a lag, so the last year or two are incomplete: years whose
  coverage ends early are flagged, never padded.
* **CEF ex-dates.** Ex-dates cluster: a sponsor declares one date for a whole
  family. Distinct ex-dates per year are the independent count, not name-events.
* **HY ETF stress.** A day with the official-NAV premium/discount at or below a
  threshold; days closer than `EPISODE_GAP` sessions apart belong to one
  episode. Episodes, not days, are the independent unit.
* **Macro event days.** FOMC, CPI and NFP dates from `data/events.parquet`.
  The union of dates is the count of distinct event days; days on which two
  kinds coincide are counted once.

NO SILENT FALLBACKS. A missing panel or column raises and names it. A year
outside a panel's coverage is reported as absent, never as zero.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("compute.use_numexpr", False)     # scripts/events/numexpr_fault.py

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))                    # `quantt.broker.alpaca`, imported only under --alpaca
DATA = REPO / "data"
OUT_DIR = REPO / "results" / "events" / "ss_catalogue_credit"

EPISODE_GAP = 10                 # sessions between stress days that end an episode
PD_THRESHOLDS = (-1.0, -2.0, -3.0)   # premium/discount, percent
FULL_YEARS = (2010, 2025)        # the window the per-year means are taken over

# ETFs whose ADV the catalogue quotes for capacity, from the 2026-10-08 universe map.
ADV_SYMBOLS = ("HYG", "JNK", "ANGL", "FALN", "LQD", "IEF", "TLT", "BIL", "SGOV", "MUB",
               "PFF", "PGX", "BKLN", "SRLN", "MBB", "TIP", "EMB", "CWB", "JAAA")

# "Depositary Shares" alone also matches every ADR, so a preferred must say so.
PREF_RE = re.compile(r"PREFERRED|\bPFD\b", re.I)
FUND_RE = re.compile(r"\bETF\b|\bETN\b|EXCHANGE-TRADED|\bFUND\b", re.I)   # pooled vehicles, not issues
BABY_BOND_RE = re.compile(r"%\s*(SENIOR\s+|SUBORDINATED\s+|FIXED[- ]RATE\s+|"
                          r"FIXED[- ]TO[- ]FLOATING\s+)?(NOTES?|DEBENTURES?)\b|"
                          r"\bNOTES?\s+DUE\b|\bDEBENTURES?\s+DUE\b", re.I)
CONVERT_RE = re.compile(r"CONVERTIBLE|MANDATOR", re.I)


# ------------------------------------------------------------------ helpers

def classify_name(name: str) -> str | None:
    """'preferred', 'baby_bond' or None, from an Alpaca asset name. Convertibles and
    pooled vehicles (ETF, ETN, fund) are never an issue of either kind."""
    if CONVERT_RE.search(name) or FUND_RE.search(name):
        return None
    if PREF_RE.search(name):
        return "preferred"
    if BABY_BOND_RE.search(name):
        return "baby_bond"
    return None


def _read(path: Path, cols: tuple[str, ...]) -> pd.DataFrame:
    """Read a panel and require its columns; raise naming whatever is missing."""
    if not path.exists():
        raise FileNotFoundError(f"panel {path} is missing")
    df = pd.read_parquet(path)
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise KeyError(f"{path}: missing columns {miss}")
    return df


def episodes(dates: pd.Series, session_index: pd.Index, gap: int) -> list[tuple]:
    """Group flagged dates into episodes on a session calendar.

    `dates` are the flagged sessions; `session_index` is the full sorted session
    calendar they are drawn from. Two flagged sessions belong to one episode if
    fewer than `gap` sessions separate them. Returns (start, end, n_days).
    """
    if gap < 1:
        raise ValueError("gap must be at least 1 session")
    idx = pd.Index(session_index).sort_values()
    if not pd.Index(dates).isin(idx).all():
        raise ValueError("a flagged date is not on the session calendar")
    pos = np.sort(idx.get_indexer(pd.Index(dates).unique()))
    out, start = [], None
    for i, p in enumerate(pos):
        if start is None:
            start, prev, n = p, p, 1
            continue
        if p - prev < gap:
            prev, n = p, n + 1
        else:
            out.append((idx[start], idx[prev], n))
            start, prev, n = p, p, 1
    if start is not None:
        out.append((idx[start], idx[prev], n))
    return out


def per_year(df: pd.DataFrame, date_col: str, first: int, last: int, **aggs) -> pd.DataFrame:
    """Count by calendar year over [first, last]; a year with no rows is 0 only if
    it lies inside the panel's own date range, else it is NaN (absent, not zero)."""
    d = df.copy()
    d["_y"] = pd.to_datetime(d[date_col]).dt.year
    g = d.groupby("_y").agg(**aggs) if aggs else d.groupby("_y").size().to_frame("n")
    years = pd.Index(range(first, last + 1), name="year")
    g = g.reindex(years)
    lo, hi = pd.to_datetime(d[date_col]).min(), pd.to_datetime(d[date_col]).max()
    inside = (years >= lo.year) & (years <= hi.year)
    g.loc[inside] = g.loc[inside].fillna(0)      # inside coverage an empty year is a measured zero
    return g


def _summ(s: pd.Series) -> dict:
    s = s.dropna()
    if s.empty:
        return {"n_years": 0}
    return {"n_years": int(s.size), "mean": round(float(s.mean()), 1),
            "median": float(s.median()), "min": float(s.min()), "max": float(s.max())}


# ------------------------------------------------------------------ sections

def rating_migrations() -> dict:
    m6 = _read(DATA / "forced_flow2" / "m6_events.parquet", ("cusip_id", "issuer6", "event_date"))
    m6["im"] = m6["issuer6"] + "_" + pd.to_datetime(m6["event_date"]).dt.strftime("%Y-%m")
    m6["ym"] = pd.to_datetime(m6["event_date"]).dt.to_period("M")
    y = per_year(m6, "event_date", 2003, 2025, bonds=("cusip_id", "size"),
                 issuer_months=("im", "nunique"), issuers=("issuer6", "nunique"))
    by_month = m6.groupby("ym").size().sort_values(ascending=False)
    top5 = float(by_month.head(5).sum() / by_month.sum())
    win = y.loc[FULL_YEARS[0]:FULL_YEARS[1]]
    out = {"panel": "data/forced_flow2/m6_events.parquet (TRACE grade-flag I->H flips; LEGACY S3)",
           "first": str(pd.to_datetime(m6.event_date).min().date()),
           "last": str(pd.to_datetime(m6.event_date).max().date()),
           "per_year": y.astype("float").to_dict(orient="index"),
           f"bonds_{FULL_YEARS[0]}_{FULL_YEARS[1]}": _summ(win["bonds"]),
           f"issuer_months_{FULL_YEARS[0]}_{FULL_YEARS[1]}": _summ(win["issuer_months"]),
           "months_over_400_bonds": int((by_month > 400).sum()),
           "months_in_panel": int(m6["ym"].nunique()),
           "share_of_bond_events_in_top5_months": round(top5, 3),
           "top5_months": {str(k): int(v) for k, v in by_month.head(5).items()}}

    rs = _read(DATA / "forced_flow" / "rising_star_events_probe.parquet",
               ("cusip_id", "event_date", "sub_prdct_type", "is_144a_only", "is_convertible",
                "prior_h_months"))
    # The probe is unfiltered: half its flips follow under a week of HY status, which
    # is flag noise, not a rating migration. Apply the fallen-angel set's own filters
    # where the probe has the column: CORP, not 144A-only, not convertible, and at
    # least 12 months in the prior grade (the fallen-angel `f4_prior_i_12m`).
    rs = rs[(rs.sub_prdct_type == "CORP") & ~rs.is_144a_only & ~rs.is_convertible
            & (rs.prior_h_months >= 12)].copy()
    rs["issuer6"] = rs["cusip_id"].str[:6]
    rs["im"] = rs["issuer6"] + "_" + pd.to_datetime(rs["event_date"]).dt.strftime("%Y-%m")
    yr = per_year(rs, "event_date", 2003, 2025, bonds=("cusip_id", "size"),
                  issuer_months=("im", "nunique"))
    out["rising_star_probe"] = {
        "panel": "data/forced_flow/rising_star_events_probe.parquet, filtered CORP, not 144A-only, not convertible, >= 12 months HY before",
        "first": str(pd.to_datetime(rs.event_date).min().date()),
        "last": str(pd.to_datetime(rs.event_date).max().date()),
        f"bonds_{FULL_YEARS[0]}_{FULL_YEARS[1]}": _summ(yr.loc[FULL_YEARS[0]:FULL_YEARS[1], "bonds"]),
        f"issuer_months_{FULL_YEARS[0]}_{FULL_YEARS[1]}": _summ(yr.loc[FULL_YEARS[0]:FULL_YEARS[1], "issuer_months"]),
    }

    ag = _read(DATA / "agency_actions_17g7.parquet",
               ("agency", "issuer_name", "rating_action_date", "is_ig_to_hy", "is_dg", "category"))
    ag = ag[ag.category == "Corporate"]
    x = ag[ag.is_ig_to_hy].copy()
    last_by_agency = ag.groupby("agency").rating_action_date.max()
    yy = {}
    for a, g in x.groupby("agency"):
        t = per_year(g, "rating_action_date", 2013, 2024, instruments=("issuer_name", "size"),
                     issuers=("issuer_name", "nunique"))
        yy[a] = {"last_action_in_panel": str(last_by_agency[a].date()),
                 "issuers_per_year": _summ(t["issuers"]),
                 "per_year_issuers": t["issuers"].to_dict()}
    out["nrsro_17g7_corporate_ig_to_hy"] = yy
    # Any downgrade (one agency, one instrument) collapsed to issuers per year: the
    # breadth of an equity post-downgrade sleeve before any tradability filter.
    dg = {}
    for a, g in ag[ag.is_dg].groupby("agency"):
        t = per_year(g, "rating_action_date", 2013, 2024, issuers=("issuer_name", "nunique"))
        dg[a] = {"last_action_in_panel": str(last_by_agency[a].date()),
                 "issuers_downgraded_per_year": _summ(t["issuers"])}
    out["nrsro_17g7_corporate_any_downgrade"] = dg
    return out


def treasury_auctions() -> dict:
    a = _read(DATA / "auction" / "auction_calendar.parquet",
              ("auction_date", "coupon_type", "tenor", "refunding_week", "reopening"))
    nc = a[a.coupon_type == "nominal_coupon"]
    y = per_year(nc, "auction_date", 2010, 2025, auctions=("tenor", "size"),
                 auction_days=("auction_date", "nunique"),
                 refunding_week=("refunding_week", "sum"))
    return {"panel": "data/auction/auction_calendar.parquet (fiscaldata Auctions Query)",
            "last_auction": str(a.auction_date.max().date()),
            "nominal_coupon_auctions_2010_2025": _summ(y["auctions"]),
            "nominal_coupon_auction_days_2010_2025": _summ(y["auction_days"]),
            "refunding_week_auctions_2010_2025": _summ(y["refunding_week"]),
            "tenors": sorted(nc.tenor.dropna().unique().tolist())}


def macro_events() -> dict:
    e = _read(DATA / "events.parquet", ("date", "event_type", "scheduled"))
    e["date"] = pd.to_datetime(e["date"])
    out = {"panel": "data/events.parquet", "coverage": {}}
    for k, g in e.groupby("event_type"):
        out["coverage"][k] = [str(g.date.min().date()), str(g.date.max().date())]
    sched = e[e.scheduled]
    # full calendar years covered by all three kinds
    lo = max(sched[sched.event_type == k].date.min().year + 0 for k in ("CPI", "NFP"))
    hi = min(sched[(sched.event_type == k) & (sched.date <= pd.Timestamp("2025-12-31"))].date.max().year - 1
             for k in ("CPI", "NFP"))
    out["full_years"] = [int(lo), int(hi)]
    w = sched[(sched.date.dt.year >= lo) & (sched.date.dt.year <= hi)]
    for k in ("FOMC", "CPI", "NFP"):
        out[f"{k}_per_year"] = _summ(per_year(w[w.event_type == k], "date", lo, hi)["n"])
    days = w.drop_duplicates("date")
    out["distinct_event_days_per_year"] = _summ(per_year(days, "date", lo, hi)["n"])
    both = w.groupby("date").event_type.nunique()
    out["days_with_two_kinds"] = int((both > 1).sum())
    out["unscheduled_fomc_in_panel"] = int(((e.event_type == "FOMC") & ~e.scheduled).sum())
    fut = e[(e.event_type == "FOMC") & (e.date > pd.Timestamp("2026-10-15"))]
    out["fomc_scheduled_after_2026_10_15"] = [str(d.date()) for d in fut.date]
    return out


def cef_ex_dates() -> dict:
    sys.path.insert(0, str(REPO / "scripts" / "cef"))
    from spec import UNIVERSE                                     # the frozen spec, never a literal
    d = _read(DATA / "cef" / "cef_dist_features.parquet",
              ("ticker", "ex_date", "is_cut", "is_raise"))
    u44 = _read_universe()
    out = {"panel": "data/cef/cef_dist_features.parquet", "last_ex_date": str(d.ex_date.max().date())}
    for label, names in (("deployed", list(UNIVERSE)), ("universe44", u44)):
        g = d[d.ticker.isin(names)]
        missing = sorted(set(names) - set(g.ticker))
        # The deployed names must all have distributions: the third P&L line depends
        # on it. For the 44-name census a name with none is reported by name and
        # left out of the count, which then says how many names it covers.
        if missing and label == "deployed":
            raise KeyError(f"{label}: no distributions for {missing}")
        y = per_year(g, "ex_date", 2010, 2025, events=("ticker", "size"),
                     distinct_dates=("ex_date", "nunique"),
                     cuts=("is_cut", "sum"), raises=("is_raise", "sum"))
        out[label] = {"names": len(names) - len(missing), "names_without_distributions": missing,
                      "ex_events_per_year": _summ(y["events"]),
                      "distinct_ex_dates_per_year": _summ(y["distinct_dates"]),
                      "cuts_per_year": _summ(y["cuts"]),
                      "raises_per_year": _summ(y["raises"])}
    return out


def _read_universe() -> list[str]:
    p = DATA / "cef" / "cef_universe.csv"
    if not p.exists():
        raise FileNotFoundError(p)
    u = pd.read_csv(p)
    if "ticker" not in u.columns:
        raise KeyError(f"{p}: no ticker column")
    return u["ticker"].tolist()


BOND_HOLIDAYS_OBSERVED = ("2026-10-12",)    # SIFMA closed, NYSE open: docs/REFERENCES.md §12j


def bond_holiday_observation() -> dict:
    """Pod idea N3, one observed case. For each deployed name: |NAV change| on the
    bond holiday against the median |NAV change| of the 20 sessions before it.

    A NAV level change, not a return of any strategy. ONE day and 13 names: it
    decides nothing. The panel is Yahoo-sourced and Yahoo serves stale copies
    (`results/cef/LIVE_NAV_QUALITY_2026-10-12.md` §5), so an unchanged NAV here is
    either the fund's carried bond prices or a vendor copy; CEFConnect's dated row
    is the second source that would separate them, and it is not read here."""
    sys.path.insert(0, str(REPO / "scripts" / "cef"))
    from spec import UNIVERSE
    n = _read(DATA / "cef" / "cef_nav.parquet", ("date", "ticker", "nav"))
    n["date"] = pd.to_datetime(n["date"])
    w = n[n.ticker.isin(UNIVERSE)].pivot(index="date", columns="ticker", values="nav").sort_index()
    out = {"panel": "data/cef/cef_nav.parquet", "last": str(w.index.max().date())}
    for d in BOND_HOLIDAYS_OBSERVED:
        t = pd.Timestamp(d)
        if t not in w.index:
            out[d] = "ABSENT from the panel"
            continue
        i = w.index.get_loc(t)
        if i < 21:
            raise ValueError(f"{d}: fewer than 20 prior sessions in the panel")
        dn = w.diff().abs().round(4)                 # NAVs are quoted in cents; the panel stores float32 noise
        hol = dn.iloc[i]
        base = dn.iloc[i - 20:i].median()            # the 20 sessions strictly before
        out[d] = {"names_unchanged": int((hol == 0).sum()),
                  "names_moved_le_1c": int((hol <= 0.01).sum()),
                  "names": int(hol.notna().sum()),
                  "median_abs_change_holiday": round(float(hol.median()), 4),
                  "median_of_names_prior20_median_abs_change": round(float(base.median()), 4)}
    return out


def hy_etf_stress() -> dict:
    pdm = _read(DATA / "forced_flow2" / "hyg_jnk_pd_derived.parquet",
                ("date", "ticker", "premium_discount_pct"))
    out = {"panel": "data/forced_flow2/hyg_jnk_pd_derived.parquet (as-traded close / official NAV - 1)"}
    for tk, g in pdm.groupby("ticker"):
        g = g.dropna(subset=["premium_discount_pct"]).sort_values("date")
        cal = pd.Index(pd.to_datetime(g["date"]))
        r = {"first": str(cal.min().date()), "last": str(cal.max().date()), "sessions": int(cal.size)}
        for th in PD_THRESHOLDS:
            flag = pd.to_datetime(g.loc[g.premium_discount_pct <= th, "date"])
            eps = episodes(flag, cal, EPISODE_GAP)
            r[f"days_le_{th:g}pct"] = int(flag.size)
            r[f"episodes_le_{th:g}pct"] = len(eps)
            r[f"episode_starts_le_{th:g}pct"] = [str(s.date()) for s, _, _ in eps][:25]
        # March 2020 (Haddad, Moreira & Muir): the low before the Fed's 2020-03-23
        # announcement and the high from it to 2020-04-30. Levels, not returns.
        g2 = g.set_index(pd.to_datetime(g["date"]))["premium_discount_pct"]
        pre, post = g2.loc["2020-03-01":"2020-03-22"], g2.loc["2020-03-23":"2020-04-30"]
        r["march2020_low_pct"] = [str(pre.idxmin().date()), round(float(pre.min()), 2)]
        r["after_2020_03_23_high_pct"] = [str(post.idxmax().date()), round(float(post.max()), 2)]
        out[tk] = r
    return out


def x3_breakeven() -> dict:
    """Arithmetic gate for a TERM-hedged month-end sleeve (catalogue row CR8).

    Reads X3's own fit statistics at run time (H14: never a number copied into a
    document): the R-D4 full-fit alpha, its TERM beta, and the sized sleeve's
    turnover. If the hedge is one instrument held at |beta| of the long leg, the
    hedged sleeve turns over about (1 + |beta|) times as much, and the most it can
    pay per unit of turnover is alpha / turnover. This computes no new return: it
    divides two numbers the closed XASSET slate already produced."""
    p = REPO / "results" / "xasset" / "trials" / "x3_fit_2026-10-14.json"
    if not p.exists():
        raise FileNotFoundError(p)
    d = json.loads(p.read_text())
    reg = [r for r in d["stage4"]["regressions"] if r["label"] == "R-D4 full fit"]
    if len(reg) != 1:
        raise KeyError(f"{p}: expected one 'R-D4 full fit' regression, found {len(reg)}")
    alpha = float(reg[0]["alpha_pct_yr"])
    beta = abs(float(reg[0]["betas"]["TERM"]["beta"]))
    turn = float(d["stage0b"]["turnover_per_yr_sized"])
    return {"source": str(p.relative_to(REPO)), "alpha_pct_yr": round(alpha, 2),
            "term_beta": round(beta, 3), "turnover_per_yr_sized": round(turn, 1),
            "breakeven_bp_per_unit_turnover_unhedged": round(alpha * 100 / turn, 1),
            "breakeven_bp_per_unit_turnover_hedged": round(alpha * 100 / (turn * (1 + beta)), 1)}


def adv_from_universe_map() -> dict:
    p = REPO / "results" / "data" / "universe_2026-10-08" / "universe_map.csv"
    if not p.exists():
        raise FileNotFoundError(p)
    u = pd.read_csv(p)
    need = ("symbol", "family", "adv63", "shortable", "easy_to_borrow")
    miss = [c for c in need if c not in u.columns]
    if miss:
        raise KeyError(f"{p}: missing {miss}")
    sel = u[u.symbol.isin(ADV_SYMBOLS)].set_index("symbol")
    absent = sorted(set(ADV_SYMBOLS) - set(sel.index))
    # The map's liquidity is CRSP's, over the sessions to 2024-12-31 (its README):
    # 21 months stale on 2026-10-08. Its flags are Alpaca's of 2026-10-08.
    out = {"source": ("results/data/universe_2026-10-08/universe_map.csv: adv63 = the sleeve's "
                      "63-session mean $ volume from CRSP, window ending 2024-12-31; "
                      "shortable flags as of 2026-10-08"),
           "absent_from_map": absent,
           "adv63_musd": {k: round(float(v) / 1e6, 1) for k, v in sel["adv63"].dropna().items()},
           "shortable_2026_10_08": {k: bool(v) for k, v in sel["shortable"].items()}}
    fam = {}
    for f in ("bdc", "preferred", "cef_taxable_credit", "cef_muni", "cef_preferred", "hy_corp"):
        g = u[u.family == f]
        fam[f] = {"n": int(len(g)), "shortable": int((g.shortable == True).sum()),       # noqa: E712 (NaN is not shortable)
                  "median_adv63_musd": round(float(g.adv63.median()) / 1e6, 2) if g.adv63.notna().any() else None}
    out["families"] = fam
    return out


def alpaca_listed_fixed_income(asof: dt.date) -> dict:
    """One read-only GET /v2/assets (active, us_equity). Classify exchange-listed
    preferreds and baby bonds BY NAME. A name regex is a census tool, not truth:
    the matched rows are written out so a reader can check them."""
    from quantt.broker.alpaca import AlpacaClient, PAPER_BASE
    c = AlpacaClient.from_environment("cef")
    raw = c._get(PAPER_BASE, "/v2/assets", {"status": "active", "asset_class": "us_equity"})
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("GET /v2/assets returned no list")
    rows = []
    for a in raw:
        name = a.get("name") or ""
        kind = classify_name(name)
        if kind is None:
            continue
        rows.append({"symbol": a["symbol"], "name": name, "kind": kind, "exchange": a.get("exchange"),
                     "tradable": bool(a.get("tradable")), "shortable": bool(a.get("shortable")),
                     "easy_to_borrow": a.get("easy_to_borrow")})
    df = pd.DataFrame(rows).sort_values(["kind", "symbol"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"alpaca_listed_fixed_income_{asof.isoformat()}.csv"
    df.to_csv(path, index=False)
    out = {"read_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "active_assets": len(raw), "written": str(path.relative_to(REPO))}
    for k, g in df.groupby("kind"):
        out[k] = {"n": int(len(g)), "tradable": int(g.tradable.sum()), "shortable": int(g.shortable.sum()),
                  "easy_to_borrow": int((g.easy_to_borrow == True).sum()),          # noqa: E712 (None stays not-ETB)
                  "by_exchange": g.exchange.value_counts().to_dict()}
    # BDCs of the 2026-10-08 map, re-flagged today
    u = pd.read_csv(REPO / "results" / "data" / "universe_2026-10-08" / "universe_map.csv")
    bdc = set(u.loc[u.family == "bdc", "symbol"])
    today = {a["symbol"]: a for a in raw if a["symbol"] in bdc}
    out["bdc_today"] = {"in_map": len(bdc), "active_today": len(today),
                        "shortable_today": sum(bool(a.get("shortable")) for a in today.values()),
                        "easy_to_borrow_today": sum(a.get("easy_to_borrow") is True for a in today.values())}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--alpaca", action="store_true", help="add one read-only GET /v2/assets census")
    args = ap.parse_args(argv)
    asof = dt.date.today()
    res = {"run_date": asof.isoformat(), "zero_trials": True,
           "rating_migrations": rating_migrations(),
           "treasury_auctions": treasury_auctions(),
           "macro_events": macro_events(),
           "cef_ex_dates": cef_ex_dates(),
           "hy_etf_stress": hy_etf_stress(),
           "bond_holiday_observation": bond_holiday_observation(),
           "x3_breakeven": x3_breakeven(),
           "adv": adv_from_universe_map()}
    if args.alpaca:
        res["alpaca_listed_fixed_income"] = alpaca_listed_fixed_income(asof)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / f"counts_{asof.isoformat()}.json"
    p.write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps(res, indent=1, default=str))
    print(f"\nwrote {p.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
