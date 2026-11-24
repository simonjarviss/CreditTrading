"""SPAC deadline-only route: the zero-trial D4 pre-screen (team lead, 2026-10-19).

    python3 scripts/events/spac_deadline_prescreen.py            # history (pre-2023, CRSP cache) + today's snapshot
    python3 -m pytest scripts/events/tests/test_spac_deadline_prescreen.py

Note: results/events/SPAC_DEADLINE_PRESCREEN_2026-10-19.md. Output (aggregates
only; CRSP is licensed and this repository is public):
results/events/spac/spac_deadline_prescreen_summary_2026-10-19.json.

WHY THIS EXISTS
---------------
The census (`SPAC_TRUST_CENSUS_2026-10-15.md`) models a deadline-only SPAC
holder earning about +2.0%/yr over T-bills, gross. The team lead's 2026-10-09
ruling is "alpha only": a sleeve must earn beyond beta (D4), and carry is closed.
This script asks whether that excess survives the D4 test on history, before
anyone spends an EVENTS trial on it. Its job is to try to show that it is NOT
alpha.

ZERO TRIALS. THE 2023-01-01 TIME HOLDOUT IS SEALED.
----------------------------------------------------
* No SPAC return dated on or after 2023-01-01 is formed. CRSP rows past
  `LAST_FIT_DAY` raise (`_holdout_guard`); the delisting file in the cache runs
  to 2025 and is cut to `LAST_FIT_DAY` before anything reads it.
* The series is an ASSET-CLASS return (every linked pre-deal SPAC common, equal
  weight), not a selected strategy: no discount screen, no deadline screen, no
  parameter. Every choice below was fixed in this docstring before the first
  return was computed; the note lists them as declared. Seeing the fit-period
  betas does contaminate the 2015-22 fit for a later SPAC pre-registration;
  the note says so. The holdout is untouched.
* Today's section reads only the census's committed 2026-10-15 snapshot (a
  price against a trust figure on one date). It is a terms-implied yield, not a
  backtest.

THE SERIES (declared)
---------------------
Universe: the census's 1,489 SPACs with a first 424B4 dated 2014-01-01 to
2022-12-31, linked to a CRSP common by the census's own `link_crsp` (no new
link rule). The universe is built from IPO prospectuses, so dead SPACs are in
it: it is not a survivor sample (CLAUDE.md attack 7 does not bite here).

Membership, decided at the close of t (no lookahead: every input is dated <= t):
  joined  on the first CRSP day with a TRADE (prc > 0);
  leaves  at the first of: the census's first-425 date (deal announced), its
          completion date, or CRSP's delisting date. A deadline-only holder
          does not elect at an extension vote, so an extension does not end
          membership. On a deal it sells in the market (the decide on the 425
          date sets the weight to zero; under shift(2) the last return earned
          is the session after the 425).
Weights: equal across members (H = 1/n), fed to `band_frontier.evaluate()`
  so the execution convention is the desk's one shift(2) (decide t, MOC fill
  t+1, earn t+2), not a copy.
Returns:
  P (headline, executable): close-to-close on TRADE prices. CRSP's negative
    prc (a bid/ask midpoint on a no-trade day) is NOT a price anyone traded
    at; on such a day the last trade is carried, so the move is booked when
    the name next trades (stale-price attack 1; Dimson lags pick it up).
  B (bounce check): the same on quote midpoints, (bid+ask)/2, where both are
    > 0 and ask/bid - 1 <= MAX_QUOTED_SPREAD; otherwise the last sane
    midpoint is carried. P minus B is the bid-ask bounce (attack 6).
  Terminal value: CRSP's delisting row, V = deldtprc x (1 + delret), booked on
    the first session after the delisting date as V / (last price) - 1. A
    delisting with no delret is counted and left out (no invented payout).
Excess return: minus French's daily RF (the one-month bill).
No price filter in the headline. The harness's own |r| < 0.5 filter
  (`band_frontier.SESSION_RETURN_LIMIT`) is shown beside it, report-only,
  because a pre-deal SPAC can genuinely double on a rumour.

THE TESTS (declared)
--------------------
Factors: MKT = French Mkt-RF; HY = HYG - IEF and TERM = IEF - RF (CRSP total
  returns from data/etf_daily.parquet). D4 (RESEARCH_STATE.md): alpha t >= 3.0
  AND every |beta| <= 0.10.
Daily: factors at t, t-1, t-2 (Dimson), betas summed; HAC(5).
Weekly (Friday, compounded): factors at w, w-1, summed; HAC(4).
Monthly (compounded): factors at m, m-1, summed; HAC(3).
Down-market: (a) MKT split at 0 into up and down parts, each Dimson-summed;
  (b) monthly continuous kink at MKT = -4% (Mitchell & Pulvino's convention,
  used for merger arbitrage in SS5-MA): beta above and below the kink.
Windows: headline 2019-01-02 .. 2022-12-30; eras 2015-18, 2019, 2020-21,
  2022; all 2015-22.
Report-only: FF5 + UMD (+ Pastor-Stambaugh traded liquidity, monthly); the
  |r| < 0.5 filter; the subset that liquidated (EX-POST selection, never
  tradable, shown only to see the bond leg alone); the top-5 names' share of
  the gross P&L (attack 8); the cost grid on the EW book's own turnover.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:   # run as a script, not -m
    sys.path.insert(0, str(REPO))

# scripts/events/numexpr_fault.py: broadcast arithmetic on large frames is wrong
# on this machine with numexpr on (pandas 2.3.3, numpy 2.3.4, numexpr 2.10.1).
pd.set_option("compute.use_numexpr", False)

from scripts.cef.band_frontier import SESSION_RETURN_LIMIT, evaluate   # noqa: E402
from scripts.events import spac_trust_census as C                       # noqa: E402

NOTE_DATE = "2026-10-19"
OUT = REPO / "results" / "events"
SPAC_DIR = C.SPAC_DIR                   # the SPAC outputs' one folder (the census's); the notes sit in OUT
SUMMARY_JSON = SPAC_DIR / f"spac_deadline_prescreen_summary_{NOTE_DATE}.json"
FF_CACHE = REPO / "results" / "cef" / "w4" / "_cache_w4"
ETF_PANEL = REPO / "data" / "etf_daily.parquet"
DELIST_CACHE = C.CACHE / "crsp_stkdelists_2014plus.parquet"

IPO_FROM, IPO_TO = date(2014, 1, 1), date(2022, 12, 31)
LAST_FIT_DAY = pd.Timestamp("2022-12-30")    # last NYSE session before the 2023-01-01 holdout
HOLDOUT_START = pd.Timestamp("2023-01-01")
MAX_QUOTED_SPREAD = 0.05     # a quote wider than 5% on a ~$10 trust claim is not a market (series B only)
D4_ALPHA_T, D4_MAX_BETA = 3.0, 0.10
COSTS_BP = (5, 15, 30)
KINK = -0.04
LAGS = {"daily": 2, "weekly": 1, "monthly": 1}
HAC = {"daily": 5, "weekly": 4, "monthly": 3}
PER_YEAR = {"daily": 252, "weekly": 52, "monthly": 12}
WINDOWS = {"headline 2019-22": ("2019-01-02", "2022-12-30"), "2015-18": ("2015-01-02", "2018-12-31"),
           "2019": ("2019-01-02", "2019-12-31"), "2020-21": ("2020-01-02", "2021-12-31"),
           "2022": ("2022-01-03", "2022-12-30"), "all 2015-22": ("2015-01-02", "2022-12-30")}
FACTORS = ["mkt", "hy", "term"]


class PrescreenError(RuntimeError):
    """A required input is missing, contradicts itself, or would touch the holdout."""


def _holdout_guard(idx, what: str) -> None:
    """Raise if any date in `idx` is on or after the 2023-01-01 time holdout."""
    idx = pd.DatetimeIndex(idx)
    if len(idx) and idx.max() >= HOLDOUT_START:
        raise PrescreenError(f"{what}: a row dated {idx.max().date()} is inside the sealed 2023 holdout")


# ------------------------------------------------------------------ membership

def linked_spacs() -> pd.DataFrame:
    """The census universe's 2014-22 IPOs with a CRSP common (the census's `link_crsp`, unchanged)."""
    U = pd.read_csv(C.UNIVERSE_CSV)
    ipo = pd.to_datetime(U["ipo_date"])
    sp = U[(ipo >= pd.Timestamp(IPO_FROM)) & (ipo <= pd.Timestamp(IPO_TO))].copy()
    if not C.CRSP_NAMES_CACHE.exists():
        raise PrescreenError(f"{C.CRSP_NAMES_CACHE} is missing: run the census with --frozen first")
    L = C.link_crsp(sp, pd.read_parquet(C.CRSP_NAMES_CACHE))
    L = L[L["permno"].notna()].copy()
    L["permno"] = L["permno"].astype(int)
    if L["permno"].duplicated().any():
        raise PrescreenError("two SPACs link to one CRSP permno")
    keep = ["cik", "status", "ipo_date", "announce_date", "completion_date"]
    L = L.merge(sp[keep], on="cik", how="left", validate="one_to_one")
    for c in ("ipo_date", "announce_date", "completion_date"):
        L[c] = pd.to_datetime(L[c])
    L["deal_end"] = L[["announce_date", "completion_date"]].min(axis=1)
    return L.assign(n_universe=len(sp))


def price_panels(px: pd.DataFrame | None = None) -> dict:
    """Trade prices, sane quote midpoints and the session calendar, CRSP 2014-01-01 .. LAST_FIT_DAY.

    `px` (permno, date, prc, bid, ask) defaults to the census's cached `dsf`
    rows; a test passes a synthetic frame. CRSP's negative prc is a bid/ask
    midpoint on a day with no trade: it is never used as a trade price.
    """
    if px is None:
        if not C.CRSP_PX_CACHE.exists():
            raise PrescreenError(f"{C.CRSP_PX_CACHE} is missing: run the census with --frozen first")
        px = pd.read_parquet(C.CRSP_PX_CACHE)
    px = px.copy()
    px["date"] = pd.to_datetime(px["date"])
    _holdout_guard(px["date"], "CRSP dsf cache")
    trade = px["prc"].where(px["prc"] > 0)
    sane = (px["bid"] > 0) & (px["ask"] > 0) & (px["ask"] / px["bid"] - 1 <= MAX_QUOTED_SPREAD)
    mid = ((px["bid"] + px["ask"]) / 2).where(sane)
    T = px.assign(v=trade).pivot(index="date", columns="permno", values="v")
    Q = px.assign(v=mid).pivot(index="date", columns="permno", values="v")
    return {"T": T, "Q": Q, "idx": T.index, "rows": len(px)}


def delistings(idx: pd.DatetimeIndex, d: pd.DataFrame | None = None) -> pd.DataFrame:
    """CRSP delisting rows dated <= LAST_FIT_DAY whose payout session is also inside the fit.

    `d` defaults to the census's cached `stkdelists` (which runs to 2025); a
    test passes a synthetic frame. Rows on or after the holdout are cut here,
    before any other code sees them.
    """
    if d is None:
        if not DELIST_CACHE.exists():
            raise PrescreenError(f"{DELIST_CACHE} is missing: run the census with --frozen first")
        d = pd.read_parquet(DELIST_CACHE)
    d = d.copy()
    d["delistingdt"] = pd.to_datetime(d["delistingdt"])
    d = d[d["delistingdt"] <= LAST_FIT_DAY].copy()   # the cache runs to 2025: cut BEFORE any use
    nxt = np.searchsorted(idx.values, d["delistingdt"].values, side="right")
    d["pay_day"] = [idx[i] if i < len(idx) else pd.NaT for i in nxt]
    d = d[d["pay_day"].notna()]
    _holdout_guard(d["pay_day"], "delisting payout sessions")
    d["V"] = d["deldtprc"].abs() * (1 + d["delret"])
    return d


def membership(L: pd.DataFrame, T: pd.DataFrame, dl: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Boolean member mask (decided at t) and each member's [join, leave) interval.

    A member at t needs: a trade on or before t (it has a price to buy at), no
    425 / completion dated on or before t, and t before CRSP's delisting date
    (a delisting is announced before it happens; the share cannot be bought
    at a close that does not exist). Asserted in `test_membership_no_lookahead`.
    """
    idx = T.index.values
    cols = {p: j for j, p in enumerate(T.columns)}
    first_delist = dl.sort_values("delistingdt").groupby("permno")["delistingdt"].first()
    M = np.zeros(T.shape, bool)
    rows = []
    for r in L.itertuples():
        j = cols.get(r.permno)
        if j is None:
            continue
        has = ~np.isnan(T.values[:, j])
        if not has.any():
            continue
        join = idx[has.argmax()]
        leave = np.datetime64("2262-01-01")
        if pd.notna(r.deal_end):
            leave = min(leave, np.datetime64(r.deal_end))
        if r.permno in first_delist.index:
            leave = min(leave, np.datetime64(first_delist[r.permno]))
        M[:, j] = (idx >= join) & (idx < leave)
        rows.append({"permno": r.permno, "join": pd.Timestamp(join), "leave": pd.Timestamp(leave),
                     "status": r.status})
    return pd.DataFrame(M, index=T.index, columns=T.columns), pd.DataFrame(rows)


def return_matrix(P: pd.DataFrame, M: pd.DataFrame, dl: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Close-to-close returns on the carried price, plus the terminal (delisting) return.

    The terminal value V lands on the session after CRSP's delisting date, as
    V / (last carried price) - 1, only for names that were members the day
    before delisting (so a deadline-only holder still held them).
    """
    F = P.ffill()
    R = F.pct_change(fill_method=None)
    n_term, n_missing = 0, 0
    for r in dl.itertuples():
        if r.permno not in R.columns or r.delistingdt not in M.index:
            continue
        i = M.index.get_loc(r.delistingdt)
        if i == 0 or not M.iat[i - 1, M.columns.get_loc(r.permno)]:
            continue
        if not (np.isfinite(r.V) and r.V > 0):
            n_missing += 1
            continue
        last = F.at[r.delistingdt, r.permno]
        if not (np.isfinite(last) and last > 0):
            n_missing += 1
            continue
        R.at[r.pay_day, r.permno] = r.V / last - 1
        n_term += 1
    return R, {"terminal_returns_booked": n_term, "terminal_returns_missing": n_missing}


def ew_weights(M: pd.DataFrame) -> pd.DataFrame:
    n = M.sum(axis=1)
    return M.astype(float).div(n.where(n > 0), axis=0).fillna(0.0)


# ------------------------------------------------------------------ factors

def factors() -> dict:
    """French daily/monthly factors and the HY / TERM legs from CRSP ETF total returns, to LAST_FIT_DAY."""
    fd = FF_CACHE / "ff5_umd_daily.parquet"
    fm = FF_CACHE / "ff5_umd_monthly.parquet"
    ps = FF_CACHE / "ps_liquidity_monthly.parquet"
    for p, how in ((fd, "scripts/data/fetch_ff_factors.py"), (fm, "scripts/data/fetch_ff_factors.py"),
                   (ps, "scripts/data/fetch_pastor_liquidity.py")):
        if not p.exists():
            raise PrescreenError(f"{p} is missing: run {how}")
    ff = pd.read_parquet(fd).set_index("date")
    ffm = pd.read_parquet(fm).set_index("date")
    psm = pd.read_parquet(ps).set_index("date")
    e = pd.read_parquet(ETF_PANEL)
    e = e[e["ticker"].isin(["HYG", "IEF"]) & (pd.to_datetime(e["date"]) <= LAST_FIT_DAY)]
    E = e.assign(date=pd.to_datetime(e["date"])).pivot(index="date", columns="ticker", values="ret_total")
    src = sorted(e.loc[pd.to_datetime(e["date"]) >= "2014-01-01", "source"].unique().tolist())
    d = pd.DataFrame({"mkt": ff["mktrf"], "rf": ff["rf"], "smb": ff["smb"], "hml": ff["hml"],
                      "rmw": ff["rmw"], "cma": ff["cma"], "umd": ff["umd"]})
    d["hy"] = E["HYG"] - E["IEF"]
    d["term"] = E["IEF"] - d["rf"]
    d = d.loc[:LAST_FIT_DAY]
    meta = {"french_crsp_vintage": str(ff["crsp_vintage"].iloc[0]), "french_daily_last": str(ff.index.max().date()),
            "french_fetched": str(ff["fetched_at_utc"].iloc[0]), "pastor_header": str(psm["header_through"].iloc[0]),
            "pastor_fetched": str(psm["fetched_at_utc"].iloc[0]), "etf_sources_2014_on": src}
    return {"d": d, "m": ffm, "ps": psm["liq_v"], "meta": meta}


def compound(x: pd.Series, rule: str) -> pd.Series:
    return (1 + x).resample(rule).prod(min_count=1) - 1


def to_freq(daily: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Compound every column of a daily return frame to weekly (Friday) or monthly (month-end)."""
    if freq == "daily":
        return daily
    rule = {"weekly": "W-FRI", "monthly": "ME"}[freq]
    return daily.apply(lambda s: compound(s, rule))


# ------------------------------------------------------------------ regressions

def ols_hac(y: pd.Series, X: pd.DataFrame, lags: int) -> dict:
    import statsmodels.api as sm
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    if len(d) < 30:
        raise PrescreenError(f"regression on {len(d)} rows; at least 30 are needed")
    f = sm.OLS(d["y"], sm.add_constant(d.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {"fit": f, "n": int(len(d))}


def dimson(y: pd.Series, F: pd.DataFrame, names: list[str], lags: int, hac: int, per_year: int) -> dict:
    """y on names at t..t-lags; betas summed over lags, their t from the summed contrast."""
    X = pd.concat([F[names].shift(k).add_suffix(f"_l{k}") for k in range(lags + 1)], axis=1).reindex(y.index)
    r = ols_hac(y, X, hac)
    f = r["fit"]
    out = {"n": r["n"], "alpha_ann": float(f.params["const"] * per_year), "alpha_t": float(f.tvalues["const"]),
           "r2": float(f.rsquared), "resid_vol_ann": float(f.resid.std() * math.sqrt(per_year))}
    for c in names:
        terms = [f"{c}_l{k}" for k in range(lags + 1)]
        R = np.zeros(len(f.params))
        for t in terms:
            R[list(f.params.index).index(t)] = 1.0
        test = f.t_test(R)
        out[f"beta_{c}"] = float(f.params[terms].sum())
        out[f"t_{c}"] = float(np.asarray(test.tvalue).ravel()[0])
        out[f"beta_{c}_l0"] = float(f.params[terms[0]])
    return out


def d4_verdict(row: dict, names=FACTORS) -> dict:
    betas = {c: row[f"beta_{c}"] for c in names}
    worst = max(betas, key=lambda c: abs(betas[c]))
    return {"alpha_t_ok": row["alpha_t"] >= D4_ALPHA_T, "betas_ok": all(abs(b) <= D4_MAX_BETA for b in betas.values()),
            "worst_beta": worst, "worst_beta_value": betas[worst],
            "pass": bool(row["alpha_t"] >= D4_ALPHA_T and all(abs(b) <= D4_MAX_BETA for b in betas.values()))}


def down_market(y: pd.Series, F: pd.DataFrame, lags: int, hac: int, per_year: int) -> dict:
    """MKT split at zero into up and down parts (Dimson-summed), with HY and TERM beside."""
    G = F.copy()
    G["mkt_up"] = G["mkt"].clip(lower=0)
    G["mkt_dn"] = G["mkt"].clip(upper=0)
    r = dimson(y, G, ["mkt_up", "mkt_dn", "hy", "term"], lags, hac, per_year)
    return {k: r[k] for k in ("n", "alpha_ann", "alpha_t", "beta_mkt_up", "t_mkt_up", "beta_mkt_dn", "t_mkt_dn")}


def kink_monthly(y: pd.Series, F: pd.DataFrame) -> dict:
    """Continuous kink at MKT = KINK (monthly): beta above, beta below, and the months below."""
    G = pd.DataFrame({"mkt": F["mkt"], "below": (F["mkt"] - KINK).clip(upper=0), "hy": F["hy"],
                      "term": F["term"]}).reindex(y.index)
    r = ols_hac(y, G, HAC["monthly"])
    f = r["fit"]
    R = np.zeros(len(f.params))
    R[list(f.params.index).index("mkt")] = 1
    R[list(f.params.index).index("below")] = 1
    t_low = f.t_test(R)
    m = G["mkt"] < KINK
    return {"n": r["n"], "beta_above": float(f.params["mkt"]), "t_above": float(f.tvalues["mkt"]),
            "beta_below": float(f.params["mkt"] + f.params["below"]),
            "t_below": float(np.asarray(t_low.tvalue).ravel()[0]),
            "months_below": int(m.sum()), "mean_excess_in_months_below": float(y[m].mean()) if m.any() else None,
            "mean_mkt_in_months_below": float(G.loc[m, "mkt"].mean()) if m.any() else None}


# ------------------------------------------------------------------ history

def build_history() -> dict:
    L = linked_spacs()
    pp = price_panels()
    T, Q, idx = pp["T"], pp["Q"], pp["idx"]
    dl = delistings(idx)
    M, spans = membership(L, T, dl)
    H = ew_weights(M)
    out = {"n_universe_2014_22": int(L["n_universe"].iloc[0]), "n_linked": int(len(L)),
           "n_members_ever": int(M.any().sum()), "crsp_rows": pp["rows"],
           "crsp_first": str(idx.min().date()), "crsp_last": str(idx.max().date())}
    series = {}
    contrib = {}
    for tag, prices in (("P", T), ("B", Q)):
        R, term = return_matrix(prices, M, dl)
        _holdout_guard(R.dropna(how="all").index, f"return matrix {tag}")
        ev = evaluate(H, R)
        series[tag] = ev["pnl"]
        out[f"terminal_{tag}"] = term
        if tag == "P":
            turn = ev["turn_series"]
            # the cost of a trade decided at t is paid at its fill, t+1 (as W4 6a)
            for c in COSTS_BP:
                series[f"P_net{c}"] = ev["pnl"] - turn.shift(1).fillna(0.0) * c / 1e4
            out["turnover_per_year"] = float(ev["turn"])
            Rf = R.where(R.abs() < SESSION_RETURN_LIMIT)
            series["P_harness_filter"] = evaluate(H, Rf)["pnl"]
            out["name_days_beyond_harness_filter"] = int(((R.abs() >= SESSION_RETURN_LIMIT) & M.shift(2, fill_value=False)).values.sum())
            c_i = (H.shift(2).fillna(0.0) * R.fillna(0.0)).loc["2019-01-02":"2022-12-30"].sum()
            pos = c_i.sort_values(ascending=False)
            out["top5_share_of_gross_2019_22"] = float(pos.head(5).sum() / c_i.sum()) if c_i.sum() != 0 else None
            out["gross_sum_2019_22"] = float(c_i.sum())
            # attack 8 by month: the largest one-name share of a calendar month's (arithmetic) EW return.
            # Aggregates only: the month and the two sums, never the name's identifier or CRSP rows.
            cm = (H.shift(2).fillna(0.0) * R.fillna(0.0)).loc[:LAST_FIT_DAY].resample("ME").sum()
            mx = cm.abs().stack().idxmax()
            out["largest_one_name_month"] = {"month": str(mx[0].date())[:7],
                                             "name_contribution": float(cm.at[mx[0], mx[1]]),
                                             "month_ew_arithmetic_sum": float(cm.loc[mx[0]].sum())}
            liq = spans.loc[spans["status"] == "liquidated", "permno"]
            Hl = ew_weights(M[[p for p in M.columns if p in set(liq)]])
            series["P_liquidated_ex_post"] = evaluate(Hl, R[Hl.columns])["pnl"]
            traded = (M & T.notna()).sum(axis=1) / M.sum(axis=1).replace(0, np.nan)
            out["share_member_days_with_trade_by_year"] = {str(k.year): round(float(v), 3) for k, v in
                                                          traded.resample("YE").mean().items()}
            out["members_mean_by_year"] = {str(k.year): round(float(v), 1) for k, v in
                                           M.sum(axis=1).resample("YE").mean().items()}
    S = pd.DataFrame(series).loc[:LAST_FIT_DAY]
    _holdout_guard(S.index, "portfolio series")
    return {"S": S, "meta": out}


def run_history() -> dict:
    h = build_history()
    S = h["S"]
    fac = factors()
    Fd = fac["d"]
    S = S.loc[S.index.isin(Fd.index)]
    ex = S.sub(Fd["rf"].reindex(S.index), axis=0)        # excess over the bill
    res = {"meta": {**h["meta"], **fac["meta"]}, "tables": {}}
    # descriptive by window. The census states its spread over the 3-month bill (FRED DTB3); the
    # regressions use French's 1-month RF. In a hiking year the two differ, so both are shown, never blended.
    tb = C.tbill_series(offline=True)
    desc = {}
    for w, (a, b) in WINDOWS.items():
        y = ex["P"].loc[a:b]
        raw = S["P"].loc[a:b]
        dtb3 = float(tb.loc[a:b].mean() / 100)
        desc[w] = {"days": int(y.notna().sum()), "raw_ann": float(raw.mean() * 252),
                   "rf_ann": float(Fd["rf"].loc[a:b].mean() * 252), "excess_ann": float(y.mean() * 252),
                   "dtb3_mean": dtb3, "excess_vs_dtb3_ann": float(raw.mean() * 252 - dtb3),
                   "vol_ann": float(y.std() * math.sqrt(252)),
                   "sharpe": float(y.mean() / y.std() * math.sqrt(252)) if y.std() > 0 else None,
                   "excess_ann_B": float(ex["B"].loc[a:b].mean() * 252),
                   "ac1_daily": float(y.autocorr(1))}
    res["tables"]["describe"] = desc
    # D4: Dimson regressions at three frequencies, every window, series P and B
    reg = {}
    for freq in ("daily", "weekly", "monthly"):
        if freq == "daily":
            Y, F = ex, Fd[FACTORS]
        else:
            # excess at this frequency: compound the RAW series and the bill separately, then subtract
            Fq = to_freq(Fd[["mkt", "hy", "term", "rf"]], freq)
            Y = to_freq(S, freq).sub(Fq["rf"], axis=0)
            F = Fq[FACTORS]
        for w, (a, b) in WINDOWS.items():
            for tag in ("P", "B", "P_net5", "P_net15", "P_net30", "P_harness_filter", "P_liquidated_ex_post"):
                if freq != "daily" and tag not in ("P", "B", "P_liquidated_ex_post"):
                    continue
                if w not in ("headline 2019-22", "all 2015-22") and tag not in ("P", "B"):
                    continue
                y = Y[tag].loc[a:b].dropna()
                try:
                    r = dimson(y, F, FACTORS, LAGS[freq], HAC[freq], PER_YEAR[freq])
                except PrescreenError as e:
                    r = {"error": str(e)}
                if "error" not in r:
                    r["d4"] = d4_verdict(r)
                reg[f"{freq}|{w}|{tag}"] = r
    res["tables"]["d4"] = reg
    # down-market betas
    dm = {}
    for w in ("headline 2019-22", "all 2015-22", "2020-21", "2022"):
        a, b = WINDOWS[w]
        dm[f"daily|{w}"] = down_market(ex["P"].loc[a:b], Fd, LAGS["daily"], HAC["daily"], 252)
    Fm = to_freq(Fd[["mkt", "hy", "term", "rf"]], "monthly")
    Ym = to_freq(S[["P"]], "monthly")["P"] - Fm["rf"]
    for w in ("headline 2019-22", "all 2015-22"):
        a, b = WINDOWS[w]
        dm[f"monthly-kink|{w}"] = kink_monthly(Ym.loc[a:b].dropna(), Fm)
    # March 2020: peak-to-trough of the market
    a, b = "2020-02-20", "2020-03-23"
    dm["covid_window"] = {"from": a, "to": b,
                          "spac_excess_cum": float((1 + ex["P"].loc[a:b]).prod() - 1),
                          "spac_excess_cum_B": float((1 + ex["B"].loc[a:b]).prod() - 1),
                          "mkt_cum": float((1 + Fd["mkt"].loc[a:b]).prod() - 1),
                          "hy_cum": float((1 + Fd["hy"].loc[a:b]).prod() - 1),
                          "spac_excess_cum_to_2020_06_30": float((1 + ex["P"].loc[a:"2020-06-30"]).prod() - 1)}
    res["tables"]["down_market"] = dm
    # report-only: FF5 + UMD + Pastor-Stambaugh traded liquidity, monthly, headline and all
    ffm = fac["m"]
    rep = {}
    for w in ("headline 2019-22", "all 2015-22"):
        a, b = WINDOWS[w]
        y = (to_freq(S[["P"]], "monthly")["P"] - ffm["rf"].reindex(Ym.index)).loc[a:b].dropna()
        X = pd.concat([ffm[["mktrf", "smb", "hml", "rmw", "cma", "umd"]], fac["ps"].rename("liq_v")], axis=1)
        X = X.reindex(y.index)
        r = ols_hac(y, X, HAC["monthly"])
        f = r["fit"]
        rep[w] = {"n": r["n"], "alpha_ann": float(f.params["const"] * 12), "alpha_t": float(f.tvalues["const"]),
                  **{f"beta_{c}": float(f.params[c]) for c in X.columns},
                  **{f"t_{c}": float(f.tvalues[c]) for c in X.columns}}
    res["tables"]["ff5_umd_ps_monthly"] = rep
    # monthly excess by year (descriptive), headline series
    Yy = Ym.loc[S.index.min():].dropna()
    res["tables"]["excess_by_year"] = {str(y): float((1 + g).prod() - 1) for y, g in Yy.groupby(Yy.index.year)}
    # power: years of daily data for t = 3 at a given alpha, with the headline residual vol
    head = reg["daily|headline 2019-22|P"]
    y22 = reg["daily|2022|P"]
    def years_for_t3(alpha, vol):
        return (D4_ALPHA_T * vol / alpha) ** 2 if alpha > 0 else None
    hold_years = (pd.Timestamp(C.NOTE_DATE) - HOLDOUT_START).days / 365.25
    res["tables"]["power"] = {
        "resid_vol_headline": head["resid_vol_ann"], "resid_vol_2022": y22["resid_vol_ann"],
        "years_for_t3_at_2pct_headline_vol": years_for_t3(0.02, head["resid_vol_ann"]),
        "years_for_t3_at_2pct_2022_vol": years_for_t3(0.02, y22["resid_vol_ann"]),
        "years_for_t3_at_2022_alpha_2022_vol": years_for_t3(y22["alpha_ann"], y22["resid_vol_ann"]),
        "holdout_years_to_census_date": hold_years,
        "min_alpha_for_t3_over_holdout_at_2022_vol": D4_ALPHA_T * y22["resid_vol_ann"] / math.sqrt(hold_years),
    }
    # ADDED AFTER THE FIRST RUN (disclosed in the note): the census states its spread over the 3-month bill.
    # The same daily Dimson regression with the excess taken over DTB3 (percent p.a. / 252 per session, an
    # approximation on a discount-basis rate), for the headline and 2022 only. French RF stays the declared one.
    rf3 = (tb / 100 / 252).reindex(S.index).ffill()
    ex3 = S["P"] - rf3
    res["tables"]["d4_over_dtb3_added"] = {}
    for w in ("headline 2019-22", "2022"):
        a, b = WINDOWS[w]
        r = dimson(ex3.loc[a:b].dropna(), Fd[FACTORS], FACTORS, LAGS["daily"], HAC["daily"], 252)
        r["d4"] = d4_verdict(r)
        res["tables"]["d4_over_dtb3_added"][f"daily|{w}|P"] = r
    return res


# ------------------------------------------------------------------ today's snapshot (no return series)

def deadline_only_terms(spread: float, days: float, cost_bp: float, p_sale: float,
                        residual_discount: float = 0.0) -> float:
    """Annual spread over bills for the deadline-only route, after the entry cost and an exit sale.

    The route needs no election, so the exit is either the free liquidation
    (probability 1 - p_sale) or a market sale before the redemption deadline
    (probability p_sale: a deal vote, where a holder who has not elected must
    sell or ride the merger). The sale pays `cost_bp` and gives up
    `residual_discount`, the discount a buyer who CAN redeem still asks for.
    Both legs are amortised over the `days` held. Pure arithmetic; tested.
    """
    if days <= 0:
        raise PrescreenError(f"days held must be positive, got {days}")
    per_year = 365.0 / days
    entry = cost_bp / 1e4 * per_year
    exit_ = p_sale * (cost_bp / 1e4 + residual_discount) * per_year
    return spread - entry - exit_


def run_snapshot() -> dict:
    """Capacity, turnover and exit arithmetic for the deadline-only route, on the census's 2026-10-15 snapshot."""
    D = pd.read_csv(C.LIVE_CSV, parse_dates=["deadline_next"])
    years = pd.read_csv(C.YEARS_CSV)
    mix = C.ibkr_election_load(years)
    live = D[(D["status"] == "live") & (D["tradable"] == True) & (D["redeemable_pool"] == True)]   # noqa: E712
    pool = live[(live["days_next"] > 0) & live["spread_next"].notna()].copy()
    ok = ~pool["gap_over_screen"].astype(bool)
    near = pool["days_next"] <= C.NEAR_DEADLINE_DAYS
    ann = pool["announce_date"].notna()
    below_acc = (pool["discount_accrued"] < 0) & ok
    pool["cap"] = pool["adv_usd_median"] * C.PARTICIPATION * C.ACCUMULATION_SESSIONS
    pool["cap_mean"] = pool["adv_usd_mean"] * C.PARTICIPATION * C.ACCUMULATION_SESSIONS
    pool["gain_over_bills"] = pool["spread_next"] * pool["days_next"] / 365.0
    pool["cay"] = pool["domicile"].eq("E9")
    sets = {"pool": pd.Series(True, index=pool.index), "below_accrued": below_acc,
            "below_accrued_no_deal": below_acc & ~ann, "near_below_accrued": below_acc & near,
            "near_below_accrued_no_deal": below_acc & near & ~ann}
    # The discount a buyer who CAN redeem still leaves near the deadline: the census's pre-2023 LEVELS one
    # month before the base deadline, against the accrued trust (census §3.2; a level, not a return).
    hist = json.loads(C.SUMMARY_JSON.read_text())
    resid = -float(hist["historical_levels"]["1m"]["discount_accrued"]["median"])
    if not 0 <= resid < 0.05:
        raise PrescreenError(f"census 1-month residual discount {resid} is outside 0..5%: re-read the census")
    out = {"asof_prices": "2026-10-15 close (census snapshot)", "terminal_mix": mix, "sets": {},
           "residual_discount_at_sale": resid,
           "residual_discount_source": "census summary historical_levels['1m']['discount_accrued']['median'], sign flipped"}
    p_sale = mix["share_terminal_event_is_deal"]
    for name, m in sets.items():
        g = pool[m]
        row = {"n": int(len(g)), "median_spread_next": float(g["spread_next"].median()),
               "median_spread_max": float(g["spread_max"].median()),
               "median_discount_accrued": float(g["discount_accrued"].median()),
               "median_days_next": float(g["days_next"].median()),
               "entries_per_slot_per_year": 365.0 / float(g["days_next"].median()),
               "one_way_turnover_per_year": (1 + p_sale) * 365.0 / float(g["days_next"].median())}
        if name != "pool":   # capacity only where every name is below the accrued trust and inside the gap screen
            row.update({"capacity_median_adv_usd": float(g["cap"].sum()),
                        "capacity_mean_adv_usd": float(g["cap_mean"].sum()),
                        "gain_over_bills_usd_median_adv": float((g["cap"] * g["gain_over_bills"]).sum()),
                        "names_with_zero_median_adv": int((g["adv_usd_median"] <= 0).sum()),
                        "top3_share_of_capacity": float(g["cap"].nlargest(3).sum() / g["cap"].sum())
                        if g["cap"].sum() > 0 else None})
        for bp in (0,) + COSTS_BP:
            for rd_name, rd in (("no_residual", 0.0), ("census_1m_residual", resid)):
                v = g.apply(lambda r: deadline_only_terms(r["spread_next"], r["days_next"], bp, p_sale, rd), axis=1)
                row[f"spread_{bp}bp_{rd_name}"] = float(v.median())
                row[f"share_pos_{bp}bp_{rd_name}"] = float((v > 0).mean())
        out["sets"][name] = row
    dom = {}
    for cay, g in pool[below_acc].groupby("cay"):
        dom["cayman" if cay else "not_cayman"] = {"n": int(len(g)), "median_discount": float(g["discount"].median()),
                                                   "median_discount_accrued": float(g["discount_accrued"].median()),
                                                   "median_spread_next": float(g["spread_next"].median()),
                                                   "median_days_next": float(g["days_next"].median())}
    out["by_domicile_below_accrued"] = dom
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-write", action="store_true", help="print only; do not write the summary JSON")
    a = ap.parse_args(argv)
    res = {"note_date": NOTE_DATE, "zero_trials": True, "holdout": "2023-01-01 sealed; last return day "
           f"{LAST_FIT_DAY.date()}", "history": run_history(), "snapshot": run_snapshot()}
    txt = json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    if not a.no_write:
        SPAC_DIR.mkdir(parents=True, exist_ok=True)
        SUMMARY_JSON.write_text(txt + "\n")
        print(f"wrote {SUMMARY_JSON.relative_to(REPO)}")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
