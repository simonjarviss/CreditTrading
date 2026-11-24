"""A7 (fund leverage changes) census and the distribution-cut overlap test; Alpaca flags for A1 (ZERO TRIALS).

    python3 scripts/events/ssx/ssx_fund1_census.py a7        # this module's main(): offline
    python3 scripts/events/ssx/ssx_fund1_census.py alpaca    # alpaca_flags(): one read-only GET /v2/assets

WHY THIS EXISTS
---------------
A7 is "fund leverage changes": a fund redeems or refinances its preferred
shares, issues notes, or has its preferreds or notes re-rated. The mechanism
would be that a change in leverage changes the common's income and risk
before a yield-buying holder base re-prices it. The graveyard risk is named
in the brief: distribution data failed twice as a signal (M7, `docs/RESEARCH_STATE.md`
"Distribution data"). A deleveraging fund usually cuts its distribution, so
if leverage events are mostly distribution cuts seen from another filing, A7
would rebuild M7. This module counts the events and measures that overlap.

SOURCES AND HOW FUND ISSUERS ARE IDENTIFIED
-------------------------------------------
1. **Rule 23c-2 redemption notices (form N-23C-2)** in the EDGAR indexes,
   listed funds at the filing date (the census's CRSP-based rule). A closed-end
   fund files one before calling its own securities; for leveraged funds that
   is overwhelmingly a preferred-share or note redemption (the common is not
   "called"). Dates are the filing date.
2. **Rule 17g-7 rating histories** (`data/agency_actions_17g7.parquet`; Moody's
   ends 2023-12-15, Fitch 2025-06-30). The panel carries issuer NAMES, no CIK.
   A 17g-7 issuer is a fund issuer if its name matches the EDGAR name of a
   fund-set CIK (BDC or registered CEF) by the merger study's matcher
   (`edgar_merger_dates.name_score` >= 0.85 with a 0.02 margin; the 17g-7 name
   takes the abbreviated side, as CRSP's does there). To keep the matcher
   tractable, candidates are blocked on the first distinctive token (the
   sponsor word: NUVEEN, BLACKROCK, PIMCO, ARES ...). The `HS` class is the
   history-start snapshot (138,212 of its 138,295 rows are dated 2012) and is
   NOT an action; it is excluded. Actions counted: NW (new rating, i.e. a new
   instrument), UP, DG, WD (withdrawn), WO/WE (watch).
3. **Distribution cuts**: `data/cef/cef_dist_features.parquet`, `is_cut`
   ex-dates, 43 of the 44 `cef_universe.csv` funds (dates only; no amount is
   used beyond the flag, no price, no return).

THE OVERLAP TEST, DECLARED BEFORE IT RAN
----------------------------------------
For each leverage event on one of the 43 funds: does a cut ex-date of the
SAME fund fall within +-90 days (primary), +-30 or +-180 (sensitivities)?
The kill line from the brief is overlap > 50% at the primary window. The
CONTROL, named in advance (graveyard pattern 2): the same fund's share of
calendar days, over its own panel span 2010-2025, that lie within the window
of one of its cuts. Overlap close to the control means leverage events and
cuts are unrelated in time; far above it means A7 is entangled with M7 even
if below 50%.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("compute.use_numexpr", False)

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events" / "ssx" / "ssx_fund1"
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_fund1"
AG = REPO / "data" / "agency_actions_17g7.parquet"
DIST = REPO / "data" / "cef" / "cef_dist_features.parquet"
ACTIONS = ("NW", "UP", "DG", "WD", "WO", "WE")
WINDOWS = (30, 90, 180)
PRIMARY = 90
SPAN = (pd.Timestamp("2010-01-01"), pd.Timestamp("2025-12-31"))
# Words that cannot block a name (they start too many names).
BLOCK_STOP = {"THE", "FIRST", "NEW", "AMERICAN", "GLOBAL", "INVESTMENT", "CAPITAL", "INCOME", "MUNICIPAL"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _block(tokens: tuple) -> str | None:
    for t in tokens:
        if len(t) >= 3 and not t.isdigit() and t not in BLOCK_STOP:
            return t[:5]
    return None


def match_17g7_issuers(ag: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    """17g-7 issuer name -> fund-set CIK, by the merger matcher with first-token blocking."""
    from scripts.events.edgar_merger_dates import MIN_MARGIN, MIN_SCORE, name_score, name_tokens
    by_block = defaultdict(list)
    for r in names.itertuples(index=False):
        try:
            tok = name_tokens(r.company)
        except ValueError:
            continue
        b = _block(tok)
        if b:
            by_block[b].append((int(r.cik), r.company, tok))
    rows = []
    for iss in ag["iss"].dropna().unique():
        if not iss.strip():
            continue
        try:
            it = name_tokens(iss)
        except ValueError:
            continue
        b = _block(it)
        cands = by_block.get(b, [])
        if not cands:
            continue
        sc = sorted(((name_score(it, et), cik, comp) for cik, comp, et in cands), reverse=True)
        # Best score per CIK (a CIK has several names).
        best, seen = [], set()
        for s, cik, comp in sc:
            if cik not in seen:
                best.append((s, cik, comp))
                seen.add(cik)
        s1 = best[0]
        s2 = best[1][0] if len(best) > 1 else -np.inf
        if s1[0] >= MIN_SCORE and s1[0] - s2 >= MIN_MARGIN:
            rows.append({"iss": iss, "cik": s1[1], "edgar_name": s1[2], "score": round(s1[0], 3)})
    return pd.DataFrame(rows)


def per_year(df: pd.DataFrame, date_col: str, unit: str, lo: int, hi: int) -> pd.DataFrame:
    d = df.assign(year=df[date_col].dt.year, month=df[date_col].dt.to_period("M").astype(str))
    d["unit_month"] = d[unit].astype(str) + "|" + d["month"]
    g = d.groupby("year").agg(events=(unit, "size"), issuers=(unit, "nunique"),
                              issuer_months=("unit_month", "nunique"), months=("month", "nunique"))
    return g.reindex(range(lo, hi + 1), fill_value=0)


def _summ(s: pd.Series) -> dict:
    return {"per_year": {int(k): int(v) for k, v in s.items()}, "mean": float(s.mean()),
            "median": float(s.median()), "min": int(s.min())}


def overlap(events: pd.DataFrame, cuts: pd.DataFrame, spans: dict) -> dict:
    """Share of (ticker, date) events with a same-fund cut ex-date within +-w days, and the control."""
    cut_by = {t: np.sort(g["ex_date"].values.astype("datetime64[D]")) for t, g in cuts.groupby("ticker")}
    out = {}
    for w in WINDOWS:
        hit, base = [], []
        for t, d in zip(events["ticker"], events["date"].values.astype("datetime64[D]")):
            c = cut_by.get(t, np.array([], dtype="datetime64[D]"))
            hit.append(bool(len(c)) and bool(np.any(np.abs((c - d).astype(int)) <= w)))
            lo, hi = spans[t]
            days = np.arange(lo, hi + np.timedelta64(1, "D"), dtype="datetime64[D]")
            if len(c):
                near = np.zeros(len(days), dtype=bool)
                for x in c:
                    near |= np.abs((days - x).astype(int)) <= w
                base.append(near.mean())
            else:
                base.append(0.0)
        out[f"pm{w}d"] = {"events": int(len(hit)), "overlap": float(np.mean(hit)) if hit else None,
                          "control_same_fund_days": float(np.mean(base)) if base else None}
    return out


def main() -> dict:
    from scripts.events.ssx.ssx_fund1_census import FUND_TYPES, INDEX_ROWS, LISTED_ROWS, sec_tickers_now
    ft = pd.read_parquet(FUND_TYPES)
    idx = pd.read_parquet(INDEX_ROWS)
    rows = pd.read_parquet(LISTED_ROWS)

    # 1. N-23C-2, listed funds at the filing date, 2010-2025.
    n = rows[rows["form"].isin(["N-23C-2", "N-23C-2/A"]) & rows["listed"].str.startswith("listed")].copy()
    n_init = n[n["form"] == "N-23C-2"]
    n23 = {ftp: {k: _summ(v) for k, v in per_year(g, "date_filed", "cik", 2010, 2025).items()}
           for ftp, g in n_init.groupby("fund_type")}
    n23["all"] = {k: _summ(v) for k, v in per_year(n_init, "date_filed", "cik", 2010, 2025).items()}
    n23_2010_22 = {k: _summ(v.loc[2010:2022]) for k, v in per_year(n_init, "date_filed", "cik", 2010, 2025).items()}
    # Sponsor-day clustering: notices filed by one filer agent on one day for many funds.
    n_init = n_init.assign(agent=n_init["accession"].str[:10])
    clusters = n_init.groupby(["agent", "date_filed"]).ngroups

    # 2. 17g-7 fund issuers.
    ag = pd.read_parquet(AG)
    ag["iss"] = ag["issuer_name"].fillna("").str.strip('"').str.strip()
    ag["ins"] = ag["instrument_name"].fillna("").str.strip('"')
    fund_names = idx.groupby(["cik", "company"]).size().reset_index()[["cik", "company"]]
    m = match_17g7_issuers(ag, fund_names)
    m = m.merge(ft[["cik", "fund_type"]], on="cik", how="left")
    m.to_csv(CACHE / "a7_17g7_fund_issuer_matches.csv", index=False)
    fa = ag.merge(m[["iss", "cik", "fund_type", "score"]], on="iss", how="inner")
    fa = fa[fa["object_type_rated"] == "Instrument"]
    fa["pref"] = fa["ins"].str.contains(r"PFD|PREF|Preferred", case=False, regex=True)
    act_rows = fa[fa["rating_action_class"].isin(ACTIONS)].copy()
    # One EVENT is one issuer-day. Measured 2026-10-19: Moody's rates each of Prospect
    # Capital's retail InterNotes separately (722 rows), so instrument rows count one
    # issuer's single action hundreds of times. Rows are kept for the class mix only.
    act = act_rows.sort_values("rating_action_class").drop_duplicates(["agency", "cik", "rating_action_date"])
    last = ag.groupby("agency")["rating_action_date"].max()
    rat = {}
    for (agency, ftp), g in act.groupby(["agency", "fund_type"]):
        hi = int(last[agency].year) - (1 if last[agency].month < 12 else 0)
        rat[f"{agency}|{ftp}"] = {"last_action_in_panel": str(last[agency].date()), "full_years": [2013, hi],
                                  **{k: _summ(v) for k, v in per_year(g, "rating_action_date", "cik", 2013, hi).items()},
                                  "class_mix_rows": act_rows[(act_rows["agency"] == agency) & (act_rows["fund_type"] == ftp)]
                                  ["rating_action_class"].value_counts().to_dict(),
                                  "preferred_share_of_issuer_days": float(g["pref"].mean())}
    h2012 = act[act["rating_action_date"].dt.year == 2012]
    rat["2012H2_note"] = {"actions": int(len(h2012)), "issuers": int(h2012["cik"].nunique()),
                          "busiest_month": str(h2012["rating_action_date"].dt.to_period("M").value_counts().idxmax())
                          if len(h2012) else None,
                          "busiest_month_actions": int(h2012["rating_action_date"].dt.to_period("M").value_counts().max())
                          if len(h2012) else 0}
    matched = {"issuers_matched": int(m["iss"].nunique()), "ciks": int(m["cik"].nunique()),
               "by_fund_type": m.drop_duplicates("cik")["fund_type"].value_counts().to_dict(),
               "instrument_rows_on_fund_issuers": int(len(fa)), "action_rows": int(len(act_rows)),
               "issuer_day_events": int(len(act)),
               "score_min": float(m["score"].min()) if len(m) else None}

    # 3. The overlap test on the 43 dist-panel funds (dates only).
    d = pd.read_parquet(DIST, columns=["ticker", "ex_date", "is_cut"])
    d = d[(d["ex_date"] >= SPAN[0]) & (d["ex_date"] <= SPAN[1])]
    spans = {t: (g["ex_date"].min().to_datetime64().astype("datetime64[D]"),
                 g["ex_date"].max().to_datetime64().astype("datetime64[D]")) for t, g in d.groupby("ticker")}
    cuts = d[d["is_cut"]]
    tk = sec_tickers_now()
    t2c = {t: int(c) for t, c in zip(tk["ticker"], tk["cik"]) if t in spans}
    c2t = defaultdict(list)
    for t, c in t2c.items():
        c2t[c].append(t)
    ev = []
    for r in rows[rows["form"] == "N-23C-2"].itertuples(index=False):
        for t in c2t.get(int(r.cik), []):
            ev.append({"ticker": t, "date": r.date_filed, "src": "N-23C-2"})
    for r in act.itertuples(index=False):
        for t in c2t.get(int(r.cik), []):
            ev.append({"ticker": t, "date": r.rating_action_date, "src": f"17g7-{r.rating_action_class}"})
    ev = pd.DataFrame(ev)
    ev = ev[(ev["date"] >= SPAN[0]) & (ev["date"] <= SPAN[1])]
    # One event per (ticker, date, source family): a rating action on four series of one fund's
    # preferred on one day is one event.
    ev["fam"] = ev["src"].str.split("-").str[0]
    ev = ev.drop_duplicates(["ticker", "date", "fam"])
    ov = {"all_sources": overlap(ev, cuts, spans),
          "n23c2_only": overlap(ev[ev["fam"] == "N"], cuts, spans),
          "ratings_only": overlap(ev[ev["fam"] == "17g7"], cuts, spans),
          "events_by_source": ev["src"].value_counts().to_dict(),
          "funds_with_events": int(ev["ticker"].nunique()), "funds_in_panel": len(spans),
          "cut_exdates_2010_2025": int(len(cuts)),
          "dist_panel_last_exdate": str(pd.read_parquet(DIST, columns=["ex_date"])["ex_date"].max().date())}
    ev.to_csv(CACHE / "a7_overlap_events_43.csv", index=False)
    out = {"ran_utc": _now(), "n23c2_listed_initial": n23, "n23c2_listed_initial_2010_2022": n23_2010_22,
           "n23c2_filer_agent_day_clusters_2010_2025": int(clusters),
           "ratings_17g7": {"matching": matched, **rat}, "overlap_with_cuts_43": ov}
    (OUT / "a7_summary.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str)[:9000])
    return out


def alpaca_flags() -> dict:
    """Today's flags for (a) every fund that filed any listed supplement in 2024-25 (the upper-bound
    population), (b) the 2024-25 sample fund-years classified as an ATM sale of common.

    One read-only `GET /v2/assets` (active, us_equity) through `quantt/broker/alpaca.py`,
    the cef paper key via QUANTT_ENV_FILE. Flags are true on the read date only
    (CLAUDE.md landmine 5). Tickers are TODAY's SEC tickers for the CIK; a fund that
    has since merged away has none and is reported as such, never guessed.
    """
    from quantt.broker.alpaca import AlpacaClient
    c = AlpacaClient.from_environment("cef")
    clock = c.clock()
    A = pd.DataFrame(c.assets(status="active")).set_index("symbol")
    f = pd.read_csv(CACHE / "a1_listed_supplement_frame.csv", parse_dates=["date_filed"])
    f = f[f["date_filed"].dt.year.isin([2024, 2025])]
    samp = pd.read_csv(CACHE / "supp_sample_classified.csv")
    atm_ciks = set(samp[(samp["era"] == "2024-25") & (samp["kind"] == "atm") & (samp["security"] == "common")]["cik"])
    common_ciks = set(samp[(samp["era"] == "2024-25") & samp["kind"].isin(["atm", "underwritten", "offering_method_unread"])
                           & (samp["security"] == "common")]["cik"])

    def flags(ciks: set, tick: dict) -> dict:
        recs = []
        for cik in sorted(ciks):
            ts = tick.get(cik)
            if not isinstance(ts, str):
                recs.append({"cik": cik, "symbol": None, "status": "no SEC ticker today"})
                continue
            t = ts.split(";")[0]
            if t not in A.index:
                recs.append({"cik": cik, "symbol": t, "status": "absent from Alpaca active list"})
                continue
            r = A.loc[t]
            recs.append({"cik": cik, "symbol": t, "status": "found", "tradable": bool(r["tradable"]),
                         "shortable": bool(r["shortable"]), "etb": bool(r["easy_to_borrow"]) if pd.notna(r["easy_to_borrow"]) else None})
        df = pd.DataFrame(recs)
        fnd = df[df["status"] == "found"]
        return {"funds": int(len(df)), "found": int(len(fnd)),
                "shortable": int(fnd["shortable"].sum()) if len(fnd) else 0,
                "etb": int((fnd["etb"] == True).sum()) if len(fnd) else 0,  # noqa: E712
                "share_shortable_of_found": float(fnd["shortable"].mean()) if len(fnd) else None,
                "share_shortable_of_all": float(fnd["shortable"].sum() / len(df)) if len(df) else None,
                "rows": recs}
    tick = f.dropna(subset=["ticker_now"]).drop_duplicates("cik").set_index("cik")["ticker_now"].to_dict()
    tick.update(samp.dropna(subset=["cik"]).merge(f[["cik", "ticker_now"]].drop_duplicates("cik"), on="cik", how="left")
                .dropna(subset=["ticker_now"]).drop_duplicates("cik").set_index("cik")["ticker_now"].to_dict())
    out = {"asof_alpaca_clock": str(clock.get("timestamp")), "endpoint": "GET /v2/assets?status=active (paper, cef key)",
           "all_2024_25_listed_supplement_filers": flags(set(f["cik"]), tick),
           "by_type_2024_25": {ftp: flags(set(g["cik"]), tick) for ftp, g in f.groupby("fund_type")},
           "sample_2024_25_atm_common_filers": flags(atm_ciks, tick),
           "sample_2024_25_common_issuers": flags(common_ciks, tick)}
    slim = json.loads(json.dumps(out, default=str))
    for k in ("all_2024_25_listed_supplement_filers", "sample_2024_25_atm_common_filers", "sample_2024_25_common_issuers"):
        pd.DataFrame(slim[k].pop("rows")).to_csv(OUT / f"a1_alpaca_{k}.csv", index=False)
    for ftp in slim["by_type_2024_25"]:
        slim["by_type_2024_25"][ftp].pop("rows")
    (OUT / "a1_alpaca_flags_summary.json").write_text(json.dumps(slim, indent=1) + "\n")
    print(json.dumps(slim, indent=1))
    return slim
