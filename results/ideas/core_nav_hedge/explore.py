"""Explore: where does the core CEF book's P&L come from, NAV or discount, and does an ETF hedge of the NAV part help?

    python3 results/ideas/core_nav_hedge/explore.py --data <a checkout's data/cef>

WHY: the paper book is flat after 34 sessions (2026-09-29..11-13, Alpaca's end-of-day
equity). Rebuilt from its fills, the discount leg, which is the signal, earned about +3.7% of
the account and the NAV leg lost about 3.2%, most of it in two muni funds held short through
a muni rally (results/ideas/2026-11-15_core_nav_hedge.md). The team lead asked on 2026-11-15
for the deployed strategy to be made profitable. The desk closed an ETF hedge on 2026-11-02
on a power argument without computing one hedged return
(results/cef/NAVHEDGE_SCREEN_2026-11-02.md); the mission brief has since dropped that gate.
This reads the 20-year history. THE LIVE WINDOW INSPIRED THE QUESTION AND IS NOT IN THE TEST:
the panel ends before most of it, and nothing here is chosen on it.

FIXED BEFORE ANY HEDGED RETURN WAS READ (2026-11-15):
  BOOK      the frozen spec's: `build_targets()` and `band(T, BAND_WIDTH)` from
            scripts/cef/band_frontier.py, unchanged. shift(2) through the harness.
  SPLIT     a held fund's price return = its NAV return + the rest. NAV part = held weight x
            NAV return; discount part = P&L less the NAV part. Both are price-only, as the
            book's own returns are (a distribution lowers price and NAV alike).
  HEDGE     one ETF per fund group (data/cef/cef_universe.csv): muni -> MUB, hy and multi ->
            HYG, loan -> BKLN (HYG until BKLN has a year of history). For each fund, beta =
            slope of its 5-session NAV return on the ETF's 5-session total return over the
            252 sessions ending t-1 (at least 126), clipped to 0..3. Five sessions because
            NAVs are struck from evaluated prices that lag an ETF's close. The hedge decided
            at t is minus the sum over the group's funds of weight x beta, filled and earned
            on the same shift(2) as the funds. No hedge for a group until its ETF has the
            history; the muni group is therefore unhedged before late 2008.
  VARIANTS  ALL (every group); MUNI (only the muni group, where the live loss was);
            ALL-NO-MUB-SHORT (MUB cannot be shorted at Alpaca on the dates read, so its
            hedge is applied only when it is a long).
  EXPECTED  the NAV part has a mean near zero and adds volatility; the hedge lowers
            volatility and leaves the mean, so the Sharpe rises a little. The desk's record
            says ETFs explain 1-7% of the book's variance, so "a little" is the prior.
  ERAS      the desk's (pre-2013 is thin: CLAUDE.md landmine 8).
Gross only. ETF legs earn total returns (a short pays the ETF's distributions).
Writes results.json beside this file. Prints the tables.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore as _explore  # noqa: E402,F401  turns numexpr off (see its header)

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
ETFS = ("MUB", "HYG", "BKLN")
GROUP_ETF = {"muni": "MUB", "hy": "HYG", "multi": "HYG", "loan": "BKLN"}
WIN, MIN_OBS, H5, BETA_CLIP = 252, 126, 5, (0.0, 3.0)
ERAS = (("2005", "2012"), ("2013", "2015"), ("2016", "2019"), ("2020", "2022"), ("2023", "2026"))


def etf_total_returns(cache: Path, last: pd.Timestamp) -> pd.DataFrame:
    """Daily total returns from Yahoo's adjusted close, cached outside the repository."""
    f = cache / "core_nav_hedge_etf_adj.parquet"
    if not f.exists():
        import yfinance as yf
        raw = yf.download(list(ETFS), start="2003-01-01", end=(last + pd.Timedelta(days=1)).date().isoformat(),
                          auto_adjust=False, progress=False, threads=False)["Adj Close"]
        if raw.empty or set(ETFS) - set(raw.columns):
            raise RuntimeError("Yahoo did not return every hedge ETF")
        cache.mkdir(parents=True, exist_ok=True)
        raw.to_parquet(f)
    adj = pd.read_parquet(f)
    adj.index = pd.to_datetime(adj.index).tz_localize(None)
    return adj.pct_change(fill_method=None)


def rolling_beta(y: pd.Series, x: pd.Series) -> pd.Series:
    """Slope of y on x over the WIN sessions ending t-1, both H5-session sums of daily returns.
    ALIGNMENT: the final shift(1) means the beta used at t reads returns through t-1 only."""
    y5, x5 = y.rolling(H5).sum(), x.rolling(H5).sum()
    ok = y5.notna() & x5.notna()
    y5, x5 = y5.where(ok), x5.where(ok)
    cov = y5.rolling(WIN, min_periods=MIN_OBS).cov(x5)
    var = x5.rolling(WIN, min_periods=MIN_OBS).var()
    return (cov / var.where(var > 0)).clip(*BETA_CLIP).shift(1)


def st(p: pd.Series) -> dict:
    sd = p.std()
    return {"ann_ret_pct": round(100 * p.mean() * 252, 2), "vol_pct": round(100 * sd * 252 ** 0.5, 2),
            "sharpe": round(p.mean() / sd * 252 ** 0.5, 2) if sd > 0 else None,
            "t": round(p.mean() / sd * len(p) ** 0.5, 2) if sd > 0 else None,
            "max_dd_pct": round(100 * (p.cumsum() - p.cumsum().cummax()).min(), 1)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="a data/cef directory holding cef_prices, cef_nav, cef_universe")
    ap.add_argument("--cache", type=Path, default=Path.home() / "quantt_research")
    ap.add_argument("--live", type=float, nargs="*", default=[-3.16, 3.69, -0.10],
                    help="per cent figures to place in the backtest's 34-session windows (report only; nothing is decided on them)")
    a = ap.parse_args(argv)
    from scripts.cef import band_frontier as bf
    from scripts.research import harness
    src = (a.data / "cef_prices.parquet", a.data / "cef_nav.parquet")
    T, R = bf.build_targets(source=src)
    H = bf.band(T, bf.BAND_WIDTH)
    p = bf.build_panel(source=src)
    grp = pd.read_csv(a.data / "cef_universe.csv").set_index("ticker")["grp"].reindex(H.columns)
    if grp.isna().any():
        raise RuntimeError(f"no group for {list(grp[grp.isna()].index)}")
    navret = p["nav"].pct_change(fill_method=None).where(lambda x: x.abs() < 0.5).reindex(H.index)[H.columns]
    W = harness.held(H)
    # a held fund with no NAV return that day contributes nothing to the NAV part; counted below
    missing_nav = int(((W != 0) & navret.isna()).sum().sum())
    held_days = int((W != 0).sum().sum())
    pnl = (W * R).sum(axis=1)
    nav_part = (W * navret.fillna(0.0)).sum(axis=1)
    disc_part = pnl - nav_part
    er = etf_total_returns(a.cache, H.index.max()).reindex(H.index)

    beta = pd.DataFrame(index=H.index, columns=H.columns, dtype=float)
    etf_of = {}
    for tk in H.columns:
        e = GROUP_ETF[grp[tk]]
        b = rolling_beta(navret[tk], er[e])
        if e == "BKLN":                       # HYG stands in until BKLN has its own history
            b = b.where(b.notna(), rolling_beta(navret[tk], er["HYG"]))
            use = pd.Series(np.where(rolling_beta(navret[tk], er["BKLN"]).notna(), "BKLN", "HYG"), index=H.index)
        else:
            use = pd.Series(e, index=H.index)
        beta[tk], etf_of[tk] = b, use
    hedge = pd.DataFrame(0.0, index=H.index, columns=list(ETFS))
    for tk in H.columns:
        contrib = -(H[tk] * beta[tk]).fillna(0.0)          # no beta yet: no hedge for that fund
        for e in ETFS:
            hedge[e] += contrib.where(etf_of[tk] == e, 0.0)

    def run(hd: pd.DataFrame) -> pd.Series:
        # an ETF with no return on a day it is not held is set to 0 so the frames align; a held
        # day with no return raises in the harness
        Rall = pd.concat([R, er[list(ETFS)].where(er[list(ETFS)].notna() | (harness.held(hd) != 0), 0.0)], axis=1)
        return harness.evaluate(pd.concat([H, hd], axis=1), Rall)["pnl"]

    muni_only = hedge.copy(); muni_only[["HYG", "BKLN"]] = 0.0
    no_short = hedge.copy(); no_short["MUB"] = no_short["MUB"].clip(lower=0.0)
    series = {"book (unhedged)": pnl, "NAV part": nav_part, "discount part": disc_part,
              "hedged ALL": run(hedge), "hedged MUNI": run(muni_only), "hedged ALL, no MUB short": run(no_short)}
    assert abs(series["book (unhedged)"].sum() - harness.evaluate(H, R)["pnl"].sum()) < 1e-12
    out = {"panel_last": str(H.index.max().date()), "first": str(H.index.min().date()), "names": list(H.columns),
           "held_name_days": held_days, "held_name_days_without_nav_return": missing_nav,
           "corr_nav_disc": round(float(nav_part.corr(disc_part)), 3),
           "var_share_nav_part": round(float(nav_part.var() / pnl.var()), 3),
           "var_share_disc_part": round(float(disc_part.var() / pnl.var()), 3),
           "hedge_gross_mean": {e: round(float(hedge[e].abs().mean()), 3) for e in ETFS},
           "book_gross_mean": round(float(H.abs().sum(axis=1).mean()), 3),
           "hedge_turnover_per_year": round(float(hedge.diff().abs().sum(axis=1).mean() * 252), 1),
           "book_turnover_per_year": round(float(H.diff().abs().sum(axis=1).mean() * 252), 1),
           "full": {}, "eras": {}, "from_2009": {}}
    for k, s in series.items():
        out["full"][k] = st(s)
        out["from_2009"][k] = st(s.loc["2009":])
        for lo, hi in ERAS:
            seg = s.loc[lo:hi]
            if len(seg) > 200:
                out["eras"].setdefault(f"{lo}-{hi}", {})[k] = st(seg)
    # what the ETFs explain: R2 of the book's daily P&L on its own hedge's P&L, from 2009
    hp = (series["hedged ALL"] - pnl).loc["2009":]
    out["r2_book_on_hedge_pnl_from_2009"] = round(float(np.corrcoef(pnl.loc["2009":], hp)[0, 1] ** 2), 3)
    out["r2_nav_part_on_hedge_pnl_from_2009"] = round(float(np.corrcoef(nav_part.loc["2009":], hp)[0, 1] ** 2), 3)
    # How wide is a 34-session window (the live record's length on 2026-11-13) in the backtest,
    # at the spec's sizing multiplier? Rolling sums from 2013, when the book is first invested.
    from scripts.cef.spec import SIZING_MULTIPLIER
    out["windows_34_sessions_pct_at_multiplier"] = {"multiplier": SIZING_MULTIPLIER}
    for k in ("book (unhedged)", "NAV part", "discount part"):
        r = series[k].loc["2013":].rolling(34).sum().dropna() * SIZING_MULTIPLIER * 100
        out["windows_34_sessions_pct_at_multiplier"][k] = {
            "mean": round(float(r.mean()), 2), "sd": round(float(r.std()), 2), "min": round(float(r.min()), 2),
            "p1": round(float(r.quantile(0.01)), 2), "p5": round(float(r.quantile(0.05)), 2),
            "p95": round(float(r.quantile(0.95)), 2), "max": round(float(r.max()), 2),
            "share_below": {str(x): round(float((r < x).mean()), 3) for x in a.live}}
    net = H.T.groupby(grp).sum().T.loc["2020":].abs()
    out["abs_net_weight_by_group_from_2020"] = {g: {"mean": round(float(net[g].mean()), 3), "p95": round(float(net[g].quantile(0.95)), 3)} for g in net.columns}
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("full", "eras", "from_2009", "names")}, indent=1))
    for name, blk in (("FULL", out["full"]), ("FROM 2009", out["from_2009"]), *((k, v) for k, v in out["eras"].items())):
        print(f"\n{name}")
        for k, v in blk.items():
            sr = "   n/a (flat)" if v["sharpe"] is None else f"{v['sharpe']:5.2f} (t {v['t']:5.2f})"
            print(f"  {k:28s} ret {v['ann_ret_pct']:6.2f}%  vol {v['vol_pct']:5.2f}%  Sharpe {sr}  dd {v['max_dd_pct']:6.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
