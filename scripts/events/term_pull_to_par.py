"""Term-CEF pull-to-par, terminations before 2023: the repo re-run of SCALING §7.1 row 7.

    python3 scripts/events/term_pull_to_par.py     # writes results/events/term_cef/term_*.csv|json

ZERO TRIALS. DESCRIPTIVE ONLY. It re-measures what an agent printed on
2026-10-09 from scratch code that was then deleted (`measure.py`,
`beta_adj.py`), so a pre-registration can cite a figure a script in the repo
produces (`results/cef/RESEARCH_PLAN_2026-10-09.md` item 0.9). It is not a
harness backtest and must not be read as one.

THE SAMPLE IS HAND-CURATED, AND SAYS SO
---------------------------------------
`FUNDS` below is the agent's list: 19 "modern" credit term funds that
liquidated before 2023, 2 that tendered at NAV and converted (JLS, JPT), and 26
1988-94 term trusts that liquidated 1995-2010. Permnos are CRSP's; cohort,
class and target status were read by the agent from N-2/497/N-CSR filings and
press releases (labels in `docs/REFERENCES.md` §12d and the 2026-10-09 report:
mostly [S], a few [V]). The peer baskets ("pre-named perpetual peers") are the
agent's choice, fixed before any return was computed, per its report. JLS and
JPT tender dates and prices are from sponsor press releases [S]. A future
pre-registration must re-derive the list from the EDGAR fetcher (plan item
0.7), not inherit it.

WHAT IS MEASURED (per fund, horizon h months before the reference date T)
-------------------------------------------------------------------------
  T      last CRSP trading day (liquidations) or tender expiry (conversions)
  t_h    last trading day on or before T - h months; P = |prc| on t_h
  TV     terminal value still receivable at t_h: the post-delisting liquidation
         payment(s) (dsedist rows with exdt after T, else dlamt), plus special
         or liquidating distributions (distcd first digit 2/3 or third digit
         6/7) paid in the last 12 months before T and after t_h; for a
         conversion, the tender price
  C_h    all cash after t_h: every distribution with exdt in (t_h, T] plus the
         terminal payment
  d_raw  P/TV - 1;  d_adj = P/C_h - 1;  dy = -d_adj / tau (tau in years)
  R      CRSP total return over (t_h, T], times (1 + dlret); NaN if any daily
         return is missing (strict, as the original)
  beta-adjusted excess: weekly (Wednesday-to-Wednesday) returns over the
         24- or 12-month window ending at T, fund and equal-weight peer basket
         each in excess of the 3-month T-bill; OLS f = a + b p; a x 52.

TIME HOLDOUT. T < 2023-01-01 for every fund, asserted, and `crsp_events.daily`
returns no row on or after 2023-01-01.

HOLDOUT NAMES. No fund and no peer may be a `cef_universe.csv` fund: checked
by CRSP permno (`crsp_events.universe_permnos`), so the 1990s BGT (75610) is
correctly not the universe BGT.

CHANGES FROM THE 2026-10-09 SCRATCH CODE (each visible in the output)
---------------------------------------------------------------------
1. WEEKLY RETURNS OF EMPTY WEEKS WERE ZERO. `(1+r).resample("W-WED").prod()-1`
   returns 0 for a week with no valid daily return, and missing daily returns
   had been dropped first, so a missing week entered the regression as a 0%
   return for the fund and/or the peers. Here a week with no valid daily
   return is NaN and drops out of the regression, and the number dropped is
   reported. The original's figure is reproduced beside it, labelled.
2. A partial peer basket (some peers missing that week) was averaged over the
   peers present, silently. It still is -- an equal-weight basket of the peers
   that traded -- but the count of fund-weeks with a partial basket is printed.
3. The risk-free rate came from `data/riskfree_daily.parquet`, which has no
   fetcher in this repo (`scripts/xasset/diversification_screen.py` says so).
   Here it is FRB H.15 DGS3MO from the R2 WRDS mirror (`frb_all.rates_daily`,
   `docs/DATA.md`), cross-checked against that panel on every date both have;
   the largest difference is printed. The two are never mixed. They agree to
   the last digit on shared dates, but the panel also carries FRED's weekday
   holidays, forward-filled (451 dates before 2023), so it accrues an extra
   day of T-bill on each; that alone moves the medians by up to 0.08pp/yr.
   The original's exact figures are reproduced with the panel, labelled
   `beta_adj_orig_rf_panel_and_zero_fill`.
4. Holdout matching is by permno for funds AND peers (the original checked
   fund labels only).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:  # run as a script, not -m
    sys.path.insert(0, str(REPO))

from scripts.events import crsp_events as ce  # noqa: E402

OUT = REPO / "results" / "events"
TERM_CEF_DIR = OUT / "term_cef"        # the term-CEF outputs: the notes sit in OUT, their data here
H = (24, 12, 6, 3, 1)
TARGET_PAR = 9.85  # the stated target of the loan/HY target-term funds in question [S, 2026-10-09 report]

# label, permno, cohort, asset class, target, peers (tickers), tender (date, price) or None
FUNDS = [
    # --- modern cohort, liquidated before 2023
    ("BHL", 92529, "modern", "loan", "plain", ["FRA", "DSU", "BLW"], None),
    ("JHA", 15825, "modern", "hy", "target $9.85", ["JQC", "JSD", "JRO", "NSL"], None),
    ("BPK", 89182, "modern", "muni", "target $15", ["MUI", "BFK", "BLE"], None),
    ("BLH", 89183, "modern", "muni", "target $15", ["MUI", "BFK", "BLE"], None),
    ("BJZ", 89184, "modern", "muni", "target $15", ["MUI", "BFK", "BLE"], None),
    ("JHD", 16081, "modern", "hy", "target $9.85", ["JQC", "JSD", "JRO", "NSL"], None),
    ("JMT", 93249, "modern", "mortgage", "plain", ["BKT", "FMY"], None),
    ("JHY", 15581, "modern", "hy", "target $9.85", ["JQC", "JSD", "JRO", "NSL"], None),
    ("BKK", 89839, "modern", "muni", "target $15", ["MUI", "BFK", "BLE"], None),
    ("BFO", 89840, "modern", "muni", "target $15", ["MUI", "BFK", "BLE"], None),
    ("NHA", 15918, "modern", "muni", "target $9.85", ["NUV", "NMI", "NUW"], None),
    ("MTT", 92901, "modern", "muni", "plain", ["MMU", "MHF", "SBI"], None),
    ("EHT", 16074, "modern", "hy", "target $9.85", ["EVV", "EVF", "EVG"], None),
    ("JHB", 16275, "modern", "ig/hy corp", "target", ["JQC", "JSD", "JRO", "NSL"], None),
    ("FIV", 16514, "modern", "loan", "target $9.85", ["FRA", "EVF", "JRO"], None),
    ("BGIO", 16576, "modern", "multi", "plain", ["BTZ", "DSU", "BLW"], None),
    ("JCO", 16615, "modern", "loan/hy", "target $9.85", ["JQC", "JSD", "JRO", "NSL"], None),
    ("EFL", 16841, "modern", "loan", "target $9.85", ["EVV", "EVF", "EVG"], None),
    ("JEMD", 16956, "modern", "em debt", "target", ["EDI", "GIM"], None),
    # --- modern, tender at 100% NAV then term removed (tender expiry, tender price) [S]
    ("JLS", 93104, "modern-TC", "mortgage", "plain", ["BKT", "FMY"], ("2019-10-07", 23.1002)),
    ("JPT", 16558, "modern-TC", "preferred", "plain", [], ("2022-02-17", 23.2613)),
    # --- old cohort (1988-94 IPOs), liquidated
    ("AGT", 75439, "old", "govt", "term", ["BKT", "BNA", "GVT"], None),
    ("ADJ", 76113, "old", "arm mortgage", "term", ["BKT", "BNA", "GVT"], None),
    ("TGB", 79355, "old", "govt", "term", ["BKT", "BNA", "GVT"], None),
    ("HTA", 78013, "old", "mortgage", "term", ["HTR", "BKT"], None),
    ("BBT", 76606, "old", "govt/mtg", "target $10", ["BKT", "BNA"], None),
    ("HTT", 77690, "old", "mortgage", "term", ["HTR", "BKT"], None),
    ("BNN", 78794, "old", "govt/mtg", "target $10", ["BKT", "BNA"], None),
    ("LTT", 77474, "old", "mortgage", "term", ["BKT", "BNA", "GVT"], None),
    ("IOF", 77921, "old", "govt/mtg", "term", ["BKT", "BNA", "GVT"], None),
    ("BTTo", 75384, "old", "govt/mtg", "target $10", ["BKT", "BNA"], None),
    ("AXT", 76594, "old", "muni", "term", ["BKN", "XAA", "MXA"], None),
    ("BTM", 77875, "old", "govt/mtg", "target $10", ["BKT", "BNA"], None),
    ("MNA", 77145, "old", "muni", "term", ["BKN", "XAA", "MXA"], None),
    ("BXT", 76816, "old", "muni", "term", ["BKN", "XAA", "MXA"], None),
    ("TTR", 78807, "old", "govt/mtg", "target", ["BKT", "BNA", "GVT"], None),
    ("TRM", 78088, "old", "govt/mtg", "term", ["BKT", "BNA", "GVT"], None),
    ("BGTo", 75610, "old", "govt/mtg", "term", ["BKT", "BNA"], None),
    ("AAT", 78935, "old", "multi", "term", ["BKT", "BNA", "GVT"], None),
    ("CXT", 78084, "old", "muni", "term", ["BKN", "XAA", "MXA"], None),
    ("MNB", 77552, "old", "muni", "term", ["BKN", "XAA", "MXA"], None),
    ("NGI", 79659, "old", "govt", "term", ["BKT", "BNA", "GVT"], None),
    ("TMT", 79136, "old", "govt/mtg", "term", ["BKT", "BNA", "GVT"], None),
    ("HTO", 78938, "old", "ig corp", "target", ["HTR", "BKT"], None),
    ("BAT", 76144, "old", "govt/mtg", "target $10", ["BKT", "BNA"], None),
    ("BCT", 79326, "old", "ig", "target", ["BKT", "BNA"], None),
    ("BMT", 77313, "old", "muni", "target $10", ["BKN", "XAA", "MXA"], None),
]


def special(cd) -> bool:
    """CRSP distcd: first digit 2/3 (liquidating / special), or third digit 6/7."""
    s = str(int(cd))
    return s[0] in "23" or s[2] in "67"


class Panel:
    """CRSP daily data for the funds and peers, with ticker -> permno by coverage."""

    def __init__(self, nm: pd.DataFrame, dsf: pd.DataFrame):
        self.dsf = dsf
        self.by = {int(p): g.set_index("date").sort_index() for p, g in dsf.groupby("permno")}
        cef = nm[nm["shrcd"].isin(ce.CEF_SHRCD)]
        self.t2p = {tk: sorted(g["permno"].unique().tolist()) for tk, g in cef.groupby("ticker")}

    def tr(self, permno: int, a, b) -> float:
        """Total return over (a, b]; NaN if any daily return is missing (strict)."""
        s = self.by.get(int(permno))
        if s is None:
            return np.nan
        w = s.loc[(s.index > a) & (s.index <= b), "ret"]
        if w.empty or w.isna().any():
            return np.nan
        return float(np.prod(1 + w.values) - 1)

    def peer_perm(self, tk: str, a, b):
        """The permno trading under `tk` whose history covers [a, b] (tickers recycle)."""
        for p in self.t2p.get(tk, []):
            s = self.by.get(int(p))
            if s is not None and s.index.min() <= a and s.index.max() >= b:
                return int(p)
        return None


def measure(panel: Panel, dist: pd.DataFrame, dl: pd.DataFrame) -> pd.DataFrame:
    rows = []
    dl = dl.set_index("permno")
    for lab, p, cohort, ac, tgt, peers, tender in FUNDS:
        s = panel.by[p].dropna(subset=["prc"])
        s = s[s["prc"] > 0]
        d = dist[dist["permno"] == p].sort_values("exdt")
        if tender is None:
            T = s.index.max()
            rec = dl.loc[p]
            post = d[d["exdt"] > T]
            final = float(post["divamt"].sum()) if len(post) else float(rec["dlamt"])
            spec = d[(d["exdt"] > T - pd.DateOffset(months=12)) & (d["exdt"] <= T) & d["distcd"].map(special)]
            dlret = float(rec["dlret"]) if pd.notna(rec["dlret"]) else np.nan
            end_date = pd.Timestamp(rec["dlstdt"])
            dlstcd = int(rec["dlstcd"])
        else:
            T = pd.Timestamp(tender[0])
            final, dlret, end_date, dlstcd = tender[1], np.nan, T, None
            spec = d.iloc[0:0]
        if T >= ce.TIME_HOLDOUT:
            raise AssertionError(f"{lab}: reference date {T.date()} is inside the sealed 2023+ holdout")
        for h in H:
            sh = s[s.index <= T - pd.DateOffset(months=h)]
            if sh.empty:
                continue
            t, P = sh.index[-1], float(sh["prc"].iloc[-1])
            C = float(d[(d["exdt"] > t) & (d["exdt"] <= T)]["divamt"].sum()) + final
            TV = final + float(spec[spec["exdt"] > t]["divamt"].sum())
            tau = (end_date - t).days / 365.25
            R = panel.tr(p, t, T)
            if tender is None:
                R = (1 + R) * (1 + dlret) - 1 if pd.notna(dlret) else np.nan
            else:
                R = (1 + R) * (final / float(s[s.index <= T]["prc"].iloc[-1])) - 1
            pr = [panel.tr(pp, t, T) for pp in (panel.peer_perm(k, t, T) for k in peers) if pp is not None]
            pr = [v for v in pr if pd.notna(v)]
            rows.append(dict(fund=lab, permno=p, cohort=cohort, ac=ac, tgt=tgt, h=h, t=t.date(), T=T.date(),
                             dlstcd=dlstcd, P=P, TV=TV, C=C, d_raw=P / TV - 1, d_adj=P / C - 1, tau=tau,
                             dy=-(P / C - 1) / tau, R=R, peerR=np.mean(pr) if pr else np.nan, npeer=len(pr)))
    out = pd.DataFrame(rows)
    out["xsR"] = out["R"] - out["peerR"]
    return out


def weekly(s: pd.Series, *, zero_fill_empty: bool) -> pd.Series:
    """Wednesday-to-Wednesday compounded returns of daily returns `s`.

    zero_fill_empty=False (the correction): a week with no valid daily return
    is NaN. zero_fill_empty=True reproduces the original, where such a week
    became 0 (`resample().prod()` of an empty bin is 1).
    """
    s = s.dropna()
    g = (1 + s).resample("W-WED")
    w = g.prod() - 1
    if not zero_fill_empty:
        w = w.where(g.count() > 0)
    return w


def risk_free() -> tuple[pd.Series, dict]:
    """Daily T-bill return, DGS3MO / 100 / 252, from the R2 FRB mirror, and its
    agreement with `data/riskfree_daily.parquet` (reported, never mixed)."""
    from src.data.r2 import connect, q, r2_path
    r = q(connect(), f"SELECT date, dgs3mo FROM read_parquet('{r2_path('frb_all', 'rates_daily')}') "
                     "WHERE dgs3mo IS NOT NULL ORDER BY date")
    r["date"] = pd.to_datetime(r["date"])
    rf = r.set_index("date")["dgs3mo"].astype(float) / 100 / 252
    chk = {"r2_frb_first": str(rf.index.min().date()), "r2_frb_last": str(rf.index.max().date())}
    panel = REPO / "data" / "riskfree_daily.parquet"
    if panel.exists():
        p = pd.read_parquet(panel)
        p = p.set_index(pd.to_datetime(p["date"]))["rf_daily"]
        both = rf.index.intersection(p.index)
        chk.update({"repo_panel_last": str(p.index.max().date()), "dates_compared": len(both),
                    "max_abs_diff_daily": float((rf.loc[both] - p.loc[both]).abs().max())})
    else:
        chk["repo_panel"] = "absent; not compared"
    return rf, chk


def beta_adjusted(panel: Panel, rf_daily: pd.Series, *, zero_fill_empty: bool) -> tuple[pd.DataFrame, dict]:
    out, info = [], {"weeks_dropped_empty": 0, "fund_weeks_partial_basket": 0}
    for lab, p, cohort, ac, tgt, peers, tender in FUNDS:
        if cohort not in ("modern", "old"):
            continue
        s = panel.by[p].dropna(subset=["prc"])
        T = s.index.max()
        for h in (24, 12):
            a = T - pd.DateOffset(months=h)
            def win(pp):
                x = panel.by[pp]
                return x.loc[(x.index > a) & (x.index <= T), "ret"]
            f = weekly(win(p), zero_fill_empty=zero_fill_empty)
            pps = [pp for pp in (panel.peer_perm(k, a, T) for k in peers) if pp is not None]
            if not pps:
                raise LookupError(f"{lab}: no peer covers {a.date()}..{T.date()}")
            pw = pd.concat([weekly(win(pp), zero_fill_empty=zero_fill_empty) for pp in pps], axis=1)
            info["fund_weeks_partial_basket"] += int((pw.notna().sum(axis=1).between(1, len(pps) - 1)).sum())
            pr = pw.mean(axis=1)
            rfw = weekly(rf_daily.loc[(rf_daily.index > a) & (rf_daily.index <= T)], zero_fill_empty=zero_fill_empty)
            j = pd.concat([f, pr, rfw], axis=1)
            j.columns = ["f", "p", "rf"]
            n0 = len(j)
            j = j.dropna()
            info["weeks_dropped_empty"] += n0 - len(j)
            j["f"] -= j["rf"]
            j["p"] -= j["rf"]
            b = np.polyfit(j["p"], j["f"], 1)
            out.append(dict(fund=lab, cohort=cohort, h=h, n_weeks=len(j), beta=b[0], alpha_ann=b[1] * 52))
    return pd.DataFrame(out), info


def q(s: pd.Series, scale=100.0) -> dict:
    s = s.dropna()
    return {"n": int(len(s)), "median": round(s.median() * scale, 2), "p25": round(s.quantile(.25) * scale, 2),
            "p75": round(s.quantile(.75) * scale, 2), "n_pos": int((s > 0).sum())}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)
    TERM_CEF_DIR.mkdir(parents=True, exist_ok=True)
    nm, dl = ce.names(args.refresh), ce.delistings(args.refresh)
    # every permno that ever carried a peer ticker as a CEF; peer_perm picks the one covering the window
    cef = nm[nm["shrcd"].isin(ce.CEF_SHRCD)]
    peer_tk = {k for f in FUNDS for k in f[5]}
    peer_perms = set(cef[cef["ticker"].isin(peer_tk)]["permno"].astype(int))
    fund_perms = {f[1] for f in FUNDS}
    up = {p for ps in ce.universe_permnos(nm).values() for p in ps}
    dsf = ce.daily(fund_perms | peer_perms, args.refresh)
    dist = ce.distributions(fund_perms, args.refresh)
    panel = Panel(nm, dsf)
    res = {"dsf_last_date": str(dsf["date"].max().date())}

    m = measure(panel, dist, dl)
    used_peers = set()
    for lab, p, cohort, ac, tgt, peers, tender in FUNDS:
        T = pd.Timestamp(m.loc[m["fund"] == lab, "T"].iloc[0])
        for h in (24, 12):
            for k in peers:
                pp = panel.peer_perm(k, T - pd.DateOffset(months=h), T)
                if pp is not None:
                    used_peers.add(pp)
    bad = (fund_perms | used_peers) & up
    if bad:
        raise AssertionError(f"holdout leak: permnos {sorted(bad)} are cef_universe.csv funds")
    m.to_csv(TERM_CEF_DIR / "term_pull_to_par_measure.csv", index=False, float_format="%.8g")

    modern = m[m["cohort"] == "modern"]
    first = modern.drop_duplicates("fund")
    res["modern_n"] = int(first["fund"].nunique())
    res["modern_dlstcd"] = first["dlstcd"].value_counts().to_dict()
    res["old_n"] = int(m.loc[m["cohort"] == "old", "fund"].nunique())
    res["old_dlstcd"] = m[m["cohort"] == "old"].drop_duplicates("fund")["dlstcd"].value_counts().to_dict()
    tab = {}
    for coh in ("modern", "old", "modern-TC"):
        for v in ("d_raw", "d_adj", "dy", "xsR"):
            for h in H:
                tab[f"{coh}_{v}_h{h}"] = q(m[(m["cohort"] == coh) & (m["h"] == h)][v])
    res["table"] = tab
    res["terminal_values"] = {r.fund: round(r.TV, 4) for r in m[m["h"] == 24].itertuples()
                              if r.fund in ("JCO", "EFL", "JHB", "JHY", "JEMD")}
    res["target_par_used_for_misses"] = TARGET_PAR

    rf, rf_chk = risk_free()
    res["risk_free"] = rf_chk
    runs = [("beta_adj", rf, False), ("beta_adj_orig_zero_fill", rf, True)]
    panel_rf = REPO / "data" / "riskfree_daily.parquet"
    if panel_rf.exists():
        # The ORIGINAL inputs, for reproduction only: the repo panel (no fetcher
        # in this repo) forward-fills FRED's holiday gaps, so it accrues an extra
        # day of T-bill at /252 on each weekday holiday. Labelled, never the headline.
        pr_ = pd.read_parquet(panel_rf)
        pr_ = pr_.set_index(pd.to_datetime(pr_["date"]))["rf_daily"]
        res["risk_free"]["repo_panel_dates_not_in_r2_pre2023"] = int(
            (pr_.index.difference(rf.index) < ce.TIME_HOLDOUT).sum())
        runs.append(("beta_adj_orig_rf_panel_and_zero_fill", pr_, True))
    for key, rfs, zf in runs:
        ba, info = beta_adjusted(panel, rfs, zero_fill_empty=zf)
        ba.to_csv(TERM_CEF_DIR / f"term_{key}.csv", index=False, float_format="%.8g")
        res[key] = {"info": info}
        for coh in ("modern", "old"):
            for h in (24, 12):
                x = ba[(ba["cohort"] == coh) & (ba["h"] == h)]
                res[key][f"{coh}_h{h}"] = {"alpha_ann_pct": q(x["alpha_ann"]), "beta_median": round(x["beta"].median(), 3)}
    (TERM_CEF_DIR / "term_pull_to_par_summary.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
