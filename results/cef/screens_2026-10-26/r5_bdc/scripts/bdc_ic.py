"""R5 BDC screen, step 2: the book's discount z on BDCs, its price-only control, and
the post-filing check. ZERO TRIALS, report only, gross only, fit window only.

Design: NOTE.md §6 and §6a, both written before this ran.

WHY build_panel AND NOT A COPY OF IT
------------------------------------
The treatment z must be the book's z. So the BDC panel is written in the live schema
(prices: date, close, volume, ticker, grp; NAV: date, nav, ticker) and passed to
`band_frontier.build_panel(end=FIT_END, universe=..., source=(prices, nav))`, the same
route C4 took for the CEF families. The price-only control cannot go through
build_panel (it has no NAV). It reuses the same three lines on log price
(`_zscore`), and `_zscore` is asserted to reproduce build_panel's z on the BDC
discount exactly, so the control has the same construction.

ALIGNMENT (no lookahead)
------------------------
* A NAV_q (Compustat ceqq/cshoq for quarter-end datadate) is known on rdq. It enters
  disc_t for every session t >= rdq. That is the book's convention: disc_t is
  date-t information, decided after t's close, filled in the t+1 closing auction,
  earning closes t+1 -> t+3 (`w4_artifacts.fwd(r, 2, 3)`). Asserted: rdq > datadate,
  and for every panel row, known_date <= t.
* mu and sd are shifted one day inside build_panel (H7).
* The NAV is restated into date t's share basis: nav_t = NAV_q * cfacpr_t / cfacpr(dq),
  where dq = the last CRSP session <= datadate. disc is then (close_t - nav_t) / nav_t on
  raw |prc|, so it is free of splits. A NAV older than 200 calendar days (datadate to t)
  is expired: that day carries no NAV.
* Everything is truncated to 2022-12-30 before computing; `assert_fit` checks every
  frame that reaches a statistic. Forward windows that would need 2023 are NaN and drop.

Outputs: bdc_ic_results.json (aggregate statistics only) and a stdout report.
Licensed derived panels go to _cache_r5/ in this folder (scratch, never tracked).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TREE = HERE.parents[1] / "tree"
sys.path.insert(0, str(TREE))

import common as C  # noqa: E402
from scripts.cef.band_frontier import MIN_PERIODS, build_panel  # noqa: E402
from scripts.cef.spec import MIN_ADV_USD, MIN_NAMES, Z_WINDOW  # noqa: E402
from scripts.cef.w4_artifacts import DEPLOYED_WIN, fwd, grid, ic_row, ic_series, nw_t  # noqa: E402

OUT = HERE.parent
CACHE = OUT / "_cache_r5"
CACHE.mkdir(exist_ok=True)
EXPIRY_DAYS = 200                      # NOTE §6a.B: one quarter + p90 10-K lag 89d [doc], margin
POST_K = 4                             # NOTE §6a.G: sessions k = 0..4 after the knowledge date
ERAS = [("2012-17", "2012-01-01", "2017-12-31"), ("2018-22", "2018-01-01", "2022-12-30"),
        ("fit 2012-22", "2012-01-01", "2022-12-30")]
RET_LIMIT = 0.5                        # W4's CRSP ret filter (|ret| < 0.5)
RES: dict = {"spec": {"Z_WINDOW": Z_WINDOW, "MIN_PERIODS": MIN_PERIODS, "MIN_NAMES": MIN_NAMES,
                      "MIN_ADV_USD": MIN_ADV_USD, "DEPLOYED_WIN": list(DEPLOYED_WIN)}}


from bdc_ic_lib import zscore as _zscore  # noqa: E402  (one copy, asserted below against build_panel)


# --------------------------------------------------------------------------- inputs

nav, nav_counts = C.compustat_nav()
ent = C.entities()
px = C.crsp(ent.permno, start="2009-01-01")
have = set(px.permno)
RES["nav_exclusions"] = nav_counts
RES["permnos"] = {"entities": int(len(ent)), "with_crsp_rows": int(len(have))}
nav = nav[nav.permno.isin(have)].copy()
first_px = px.groupby("permno").date.min()
pre = nav.datadate < nav.permno.map(first_px)
RES["nav_exclusions"]["datadate_before_first_crsp_row"] = int(pre.sum())
RES["nav_exclusions"]["no_crsp_permno_rows"] = int((~C.compustat_nav()[0].permno.isin(have)).sum())
nav = nav[~pre].copy()

CAL = pd.DatetimeIndex(sorted(px.date.unique())).astype("datetime64[ns]")
C.assert_fit(CAL)
RES["calendar"] = {"first": str(CAL[0].date()), "last": str(CAL[-1].date()),
                   "sessions_per_year_min_max_2012_22": [int(v) for v in
                       pd.Series(1, index=CAL).loc["2012":"2022"].groupby(lambda d: d.year).size().agg(["min", "max"])]}

px = px.sort_values(["permno", "date"])
px["close"] = px.prc.abs()
px["notrade"] = px.prc < 0
px["volume"] = px.vol


def cf_at(perm_rows: pd.DataFrame, dates: pd.Series) -> np.ndarray:
    """cfacpr in force at each date: the last CRSP row on or before it."""
    s = perm_rows[["date", "cfacpr"]].sort_values("date")
    m = pd.merge_asof(pd.DataFrame({"d": pd.to_datetime(dates.values)}).reset_index().sort_values("d"),
                      s, left_on="d", right_on="date", direction="backward")
    m = m.sort_values("index")
    if m.cfacpr.isna().any():
        raise ValueError("a NAV datadate has no CRSP factor on or before it")
    return m.cfacpr.values


def nav_daily(known_col: str) -> pd.DataFrame:
    """Per (permno, session): the NAV in use, restated to the session's share basis.

    The NAV in use on t is, among NAV rows with known_date <= t, the one with the latest
    datadate (a late or out-of-order report never replaces a newer period). k counts
    sessions since that NAV became known (k = 0 on the first session >= known_date)."""
    rows = []
    for perm, g in nav.dropna(subset=[known_col]).groupby("permno"):
        p = px[px.permno == perm]
        g = g.sort_values([known_col, "datadate"]).copy()
        g["cf_dq"] = cf_at(p, g.datadate)
        # running "newest period known so far"
        best, keep = pd.Timestamp.min, []
        for i, r in g.iterrows():
            if r.datadate > best:
                best = r.datadate
                keep.append(i)
        ev = g.loc[keep, [known_col, "datadate", "nav", "cf_dq"]].rename(columns={known_col: "known"})
        ev["known_session"] = CAL[CAL.searchsorted(ev.known.values, side="left").clip(max=len(CAL) - 1)]
        ev.loc[ev.known > CAL[-1], "known_session"] = pd.NaT
        ev = ev.dropna(subset=["known_session"]).sort_values("known_session")
        # two NAVs first usable on the same session: the later period wins (already sorted)
        ev = ev.drop_duplicates("known_session", keep="last")
        d = pd.merge_asof(p[["date", "close", "volume", "cfacpr", "notrade"]].sort_values("date"),
                          ev, left_on="date", right_on="known_session", direction="backward")
        d = d.dropna(subset=["nav"])
        assert (d.known <= d.date).all() and (d.known_session <= d.date).all(), "NAV used before it was known"
        d["expired"] = (d.date - d.datadate).dt.days > EXPIRY_DAYS
        pos = pd.Series(np.arange(len(CAL)), index=CAL)
        d["k"] = pos.reindex(d.date).values - pos.reindex(d.known_session).values
        d["nav_t"] = d.nav * d.cfacpr / d.cf_dq
        d["permno"] = perm
        rows.append(d)
    out = pd.concat(rows, ignore_index=True)
    C.assert_fit(out.set_index("date"))
    return out


def report_known_dates() -> pd.DataFrame:
    """§6a.B sensitivity: the first 10-Q/10-K reporting the period; next session if
    accepted at or after 16:00 ET."""
    r = C.reports()
    r = r[r.form.isin(["10-Q", "10-K"])].sort_values("accepted")
    first = r.drop_duplicates(["cik", "reportDate"], keep="first")[["cik", "reportDate", "accepted"]]
    m = nav.merge(first, left_on=["cik", "datadate"], right_on=["cik", "reportDate"], how="left")
    acc_day = m.accepted.dt.tz_localize(None).dt.normalize()
    late = m.accepted.dt.hour >= 16
    m["known_f"] = (acc_day + pd.to_timedelta(late.astype(int), unit="D")).where(m.accepted.notna()).astype("datetime64[ns]")
    return m[["gvkey", "datadate", "known_f"]], int(m.accepted.isna().sum())


def write_panel(d: pd.DataFrame, tag: str):
    U = [f"P{p}" for p in sorted(d.permno.unique())]
    ok = d[~d.expired]
    prices = px[px.permno.isin(d.permno.unique())][["date", "close", "volume", "permno"]].copy()
    prices["ticker"] = "P" + prices.permno.astype(str)
    prices["grp"] = "bdc"
    navs = pd.DataFrame({"date": ok.date, "nav": ok.nav_t, "ticker": "P" + ok.permno.astype(str)})
    pp, npth = CACHE / f"bdc_prices_{tag}.parquet", CACHE / f"bdc_nav_{tag}.parquet"
    prices.drop(columns="permno").to_parquet(pp)
    navs.to_parquet(npth)
    return U, pp, npth


def spearman_pair(A, B, M, dates):
    """Per-date Spearman(A, B) on the names where M, A and B all exist (ic_series' ranks)."""
    A, B, M = A.reindex(dates), B.reindex(dates), M.reindex(dates, fill_value=False)
    ok = M & A.notna() & B.notna()
    ra = A.where(ok).rank(axis=1); rb = B.where(ok).rank(axis=1)
    ra = ra.sub(ra.mean(axis=1), axis=0); rb = rb.sub(rb.mean(axis=1), axis=0)
    c = (ra * rb).sum(axis=1) / np.sqrt((ra ** 2).sum(axis=1) * (rb ** 2).sum(axis=1)).replace(0, np.nan)
    return c, ok.sum(axis=1)


def partial_ic(sT, sC, F, M, dates, min_n=MIN_NAMES):
    ok = M & sT.notna() & sC.notna() & F.notna()
    rTF, n = spearman_pair(sT, F, ok, dates)
    rCF, _ = spearman_pair(sC, F, ok, dates)
    rTC, _ = spearman_pair(sT, sC, ok, dates)
    p = (rTF - rTC * rCF) / np.sqrt((1 - rTC ** 2) * (1 - rCF ** 2))
    p = p.replace([np.inf, -np.inf], np.nan)
    return p[(n >= min_n) & p.notna()]


def era_rows(ic: pd.Series) -> dict:
    out = {}
    for lab, a, b in ERAS:
        s = ic.loc[a:b]
        r = ic_row(s)
        out[lab] = {k: (float(v) if isinstance(v, (float, np.floating)) else int(v)) for k, v in r.items()}
    return out


def run(known_col: str, tag: str) -> dict:
    d = nav_daily(known_col)
    U, pp, npth = write_panel(d, tag)
    low = int((px[px.permno.isin(d.permno.unique())].close <= 0.5).sum())
    P = build_panel(end=str(C.FIT_END.date()), universe=U, source=(pp, npth))
    C.assert_fit(P["z"], P["disc"], P["adv"])
    # the control's z-code reproduces build_panel's z on the same discount
    zr = _zscore(P["disc"])
    assert np.allclose(zr.values, P["z"].values, equal_nan=True), "_zscore != build_panel z"
    idx = CAL[CAL <= C.FIT_END]
    zT = P["z"].reindex(index=idx, columns=U)
    adv = P["adv"].reindex(index=idx, columns=U)
    pxs = px.assign(ticker="P" + px.permno.astype(str))
    lp = np.log(pxs.pivot(index="date", columns="ticker", values="close")
                / pxs.pivot(index="date", columns="ticker", values="cfacpr")).reindex(index=idx, columns=U)
    zC = _zscore(lp)
    ret = pxs.pivot(index="date", columns="ticker", values="ret").reindex(index=idx, columns=U)
    ret = ret.where(ret.abs() < RET_LIMIT)
    F = fwd(ret, *DEPLOYED_WIN)
    C.assert_fit(zT, zC, F)
    kk = d[~d.expired].assign(ticker="P" + d.permno.astype(str)).pivot(index="date", columns="ticker", values="k")
    kk = kk.reindex(index=idx, columns=U)
    nt = pxs.pivot(index="date", columns="ticker", values="notrade").reindex(index=idx, columns=U)
    M = zT.notna() & zC.notna()                         # common sample (§6a)
    Mdep = M & (adv >= MIN_ADV_USD)
    sT, sC = -zT, -zC                                    # traded sign: long cheap
    res = {"panel": {
        "nav_rows_in_use": int(d[["permno", "datadate"]].drop_duplicates().shape[0]),
        "name_days_with_nav": int((~d.expired).sum()), "name_days_expired": int(d.expired.sum()),
        "price_rows_close_le_0p5_dropped_by_build_panel": low,
        "bdcs_with_z": int(M.any().sum()),
        "notrade_share_of_signal_name_days": float(nt.where(M).stack().astype(float).mean()),
        "first_date_ge_min_names": str(M.sum(axis=1).ge(MIN_NAMES).idxmax().date()),
    }}
    for ph in (0, 1):
        G = grid(idx[idx >= "2012-01-01"], ph)
        blk = {}
        for setlab, MM in (("primary", M), ("deployed_style_adv", Mdep)):
            icT = ic_series(sT, F, MM, G)
            icC = ic_series(sC, F, MM, G)
            pic = partial_ic(sT, sC, F, MM, G)
            names = MM.reindex(G, fill_value=False).sum(axis=1)
            blk[setlab] = {"treatment": era_rows(icT), "control": era_rows(icC), "partial": era_rows(pic),
                           "names_per_date_median_2012_22": float(names[names >= MIN_NAMES].median())}
            if setlab == "primary":
                Mp, Mr = MM & (kk <= POST_K), MM & (kk > POST_K)
                blk["post_filing"] = {
                    "treatment_post": era_rows(ic_series(sT, F, Mp, G)),
                    "treatment_rest": era_rows(ic_series(sT, F, Mr, G)),
                    "control_post_context": era_rows(ic_series(sC, F, Mp, G)),
                    "control_rest_context": era_rows(ic_series(sC, F, Mr, G)),
                    "pooled_dates_post_ge_min_names": int((Mp.reindex(G, fill_value=False).sum(axis=1) >= MIN_NAMES).sum()),
                }
                # cross-sectional correlation of the two signals, for the record
                cTC, n = spearman_pair(sT, sC, MM, G)
                blk["rank_corr_treatment_control_median"] = float(cTC[n >= MIN_NAMES].median())
        res[f"phase{ph}"] = blk
    return res


RES["rdq_primary"] = run("rdq", "rdq")
kf, unmatched = report_known_dates()
nav = nav.merge(kf, on=["gvkey", "datadate"], how="left")
RES["filing_sensitivity_unmatched_nav_rows"] = unmatched
lag = (nav.known_f - nav.rdq).dt.days
RES["filing_minus_rdq_days_p10_p50_p90"] = [float(lag.quantile(q)) for q in (0.1, 0.5, 0.9)]
RES["filing_before_rdq_rows"] = int((lag < 0).sum())
RES["filingdate_sensitivity"] = run("known_f", "filing")

Path(OUT / "bdc_ic_results.json").write_text(json.dumps(RES, indent=1, default=str))
print(json.dumps(RES, indent=1, default=str))
