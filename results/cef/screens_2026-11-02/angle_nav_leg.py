"""Angle A: is the live 'NAV drag' a cost, a staleness identity, or an unchosen hedgeable beta?
Zero trials; fit data only (<= 2022-12-30, asserted); nothing on the live path.

THE QUESTION (PM, 2026-11-02). The live attribution (results/cef/LIVE_ATTRIBUTION_2026-11-02.md,
[V] there) splits the hold P&L into a NAV part (q_prev x close_prev x NAV return) and a discount
part (the rest): NAV -2,250.74, discount +1,583.47, hold -667.27, over 09-29..10-30. Is the
NAV drag predictable from a NAV-lag measure known at t, and is it something the book can stop
paying?

THREE MEASUREMENTS, on the fit-period unit book of the live policy (angle_common.live_book):
  1. the same decomposition on the backtest: means, vols, and corr(NAV part, discount part);
  2. a NAV-lag forecast known at t: for each name, a trailing-252-session OLS of the NAV return
     on the PRICE returns 2, 3 and 4 sessions earlier (the lags whose values are known at the
     decision t for the return the decision earns at t+2). The book-level forecast is
     sum_i H[t,i] * f[i,t]. If the NAV part is predictable but the hold is not, the 'drag'
     is a reallocation between the two parts (an identity under stale NAVs), not a loss;
  3. the hedgeable share: the book's daily P&L on liquid FI ETF returns (MUB, HYG, IEF, LQD;
     BKLN from 2012), Dimson lags 0-2, in-sample R^2 and an out-of-sample variance reduction
     with betas from the trailing 252 sessions strictly before t.

ALIGNMENT (H7). H is decided at t and held over t+2 (harness.held). The NAV-lag coefficients
used at t come from observations s <= t (NAV of s is published the evening of s, before the
decision at t). The hedge betas applied on day s come from days strictly before s.

NEGATIVE CONTROL (named first, H12). For (2): the forecast must NOT predict the price-based hold
P&L; if it does, the 'NAV lag' is a price signal and belongs to the CEF counter. For (3): the
hedge's own P&L mean must be ~0 (otherwise it is a factor bet, D4 territory, not a hedge).

PANELS: data/cef/cef_prices.parquet and cef_nav.parquet truncated at 2022-12-30 (copies in
_cache_fit/); ETF total returns from `scripts/build_etf_daily.py --xasset` (REFERENCES row
'The extended ETF build', [V] 2026-10-14), read from the trial-xasset worktree's gitignored cache
and truncated at FIT_END here.

Run from the repo root:  python3 -B results/cef/screens_2026-11-02/angle_nav_leg.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import angle_common as c                                         # noqa: E402
from scripts.research.harness import held                       # noqa: E402

ETF_XASSET = (c.REPO.parent / "trial-xasset" / "results" / "xasset" / "_cache_xasset"
              / "etf_daily_xasset.parquet")


def decomposition(H, R, nav):
    navr = nav.pct_change(fill_method=None).where(lambda x: x.abs() < 0.5)
    navr = navr.reindex(index=R.index, columns=R.columns)
    Hs = held(H)
    # name-days where the book holds a weight and the NAV return is missing cannot be split;
    # they are excluded from BOTH parts and counted (no invented NAV return).
    held_mask = Hs.abs() > 0
    miss = held_mask & navr.isna()
    ok = held_mask & navr.notna()
    nav_part = (Hs * navr).where(ok).sum(axis=1)
    hold_ok = (Hs * R).where(ok).sum(axis=1)
    disc_part = hold_ok - nav_part
    cover = 1 - miss.sum().sum() / max(held_mask.sum().sum(), 1)
    return nav_part, disc_part, hold_ok, navr, float(cover)


def lag_forecast(R, navr, H, window=252, lags=(2, 3, 4), min_obs=120):
    """f[i,t]: forecast of navr[i,t+2] from R[i,t], R[i,t-1], R[i,t-2], with coefficients fitted
    on observations s <= t (navr[s] on R[s-2], R[s-3], R[s-4])."""
    F = pd.DataFrame(np.nan, index=R.index, columns=R.columns)
    for tk in R.columns:
        y = navr[tk]
        X = pd.concat({f"l{k}": R[tk].shift(k) for k in lags}, axis=1)
        d = pd.concat([y.rename("y"), X], axis=1)
        vals = d.values
        n = len(d)
        for t in range(window, n):
            blk = vals[t - window + 1:t + 1]                       # rows s in (t-window, t]
            blk = blk[~np.isnan(blk).any(axis=1)]
            if len(blk) < min_obs:
                continue
            Xb = np.column_stack([np.ones(len(blk)), blk[:, 1:]])
            beta, *_ = np.linalg.lstsq(Xb, blk[:, 0], rcond=None)
            # the regressors for the t+2 target are R[t], R[t-1], R[t-2]
            xnext = [R[tk].iloc[t - (k - 2)] for k in lags]
            if np.isnan(xnext).any():
                continue
            F.iloc[t, F.columns.get_loc(tk)] = beta[1:] @ np.array(xnext)
    return F


def ar_forecast(navr, window=252, lags=(2, 3, 4), min_obs=120):
    """Second method for (2): f[i,t] from the NAV's OWN returns navr[t], navr[t-1], navr[t-2]
    (stale NAVs are autocorrelated: W4 measured AC(3) 0.15-0.36). Fitted on s <= t."""
    return lag_forecast(navr, navr, None, window=window, lags=lags, min_obs=min_obs)


def position_hedge(H, R, F, names, window=252, lags=(0, 1, 2)):
    """Second method for (3): per-name Dimson betas of the PRICE return on the factors,
    trailing `window` sessions strictly before day s, times the weight held on s.
    hedge[s] = sum_i Hs[s,i] * sum_{f,k} beta[i,f,k](< s) * F[f, s-k]."""
    Hs = held(H)
    X = pd.concat({f"{n}_l{k}": F[n].shift(k) for n in names for k in lags}, axis=1).reindex(R.index)
    hedge = pd.Series(0.0, index=R.index)
    have = pd.Series(False, index=R.index)
    Xv = X.values
    for tk in R.columns:
        y = R[tk].values
        w = Hs[tk].values
        for t in range(window, len(R)):
            if w[t] == 0:
                continue
            yb, Xb = y[t - window:t], Xv[t - window:t]
            ok = ~np.isnan(Xb).any(axis=1) & ~np.isnan(yb) & (yb != 0)
            if ok.sum() < 120 or np.isnan(Xv[t]).any():
                continue
            A = np.column_stack([np.ones(ok.sum()), Xb[ok]])
            b, *_ = np.linalg.lstsq(A, yb[ok], rcond=None)
            hedge.iloc[t] += w[t] * (Xv[t] @ b[1:])
            have.iloc[t] = True
    return hedge.where(have)


def ols_nw(y, x, lags=5):
    d = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    X = np.column_stack([np.ones(len(d)), d["x"].values])
    b, *_ = np.linalg.lstsq(X, d["y"].values, rcond=None)
    e = d["y"].values - X @ b
    n = len(d)
    S = (X * e[:, None]).T @ (X * e[:, None]) / n
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None]) / n
        S += w * (G + G.T)
    Q = np.linalg.inv(X.T @ X / n)
    V = Q @ S @ Q / n
    return float(b[1]), float(b[1] / np.sqrt(V[1, 1])), int(n)


def etf_factors():
    x = pd.read_parquet(ETF_XASSET, columns=["date", "ticker", "ret_total"])
    x["date"] = pd.to_datetime(x["date"])
    x = x[x["date"] <= c.FIT_END]
    F = x.pivot_table(index="date", columns="ticker", values="ret_total").sort_index()
    c.assert_fit(F, "etf factors")
    return F[["MUB", "HYG", "IEF", "LQD", "BKLN"]]


def hedge_share(y, F, names, start, window=252, lags=(0, 1, 2)):
    """In-sample R^2 and out-of-sample variance reduction of y on Dimson-lagged factors."""
    X = pd.concat({f"{n}_l{k}": F[n].shift(k) for n in names for k in lags}, axis=1)
    d = pd.concat([y.rename("y"), X], axis=1).loc[start:].dropna()
    d = d[d["y"] != 0]                                   # active book days only (pre-2013 flat days)
    Xv = np.column_stack([np.ones(len(d)), d.drop(columns="y").values])
    b, *_ = np.linalg.lstsq(Xv, d["y"].values, rcond=None)
    fitted = Xv @ b
    r2 = 1 - np.var(d["y"].values - fitted) / np.var(d["y"].values)
    # out of sample: betas from the trailing window strictly before each day
    vals = d.values
    hedge = np.full(len(d), np.nan)
    for t in range(window, len(d)):
        blk = vals[t - window:t]
        Xb = np.column_stack([np.ones(len(blk)), blk[:, 1:]])
        bb, *_ = np.linalg.lstsq(Xb, blk[:, 0], rcond=None)
        hedge[t] = vals[t, 1:] @ bb[1:]                  # the factor component, no intercept
    m = ~np.isnan(hedge)
    yv, hv = d["y"].values[m], hedge[m]
    vr = 1 - np.var(yv - hv) / np.var(yv)
    hedge_mean_ann = float(np.mean(hv) * 252)
    hedge_t = c.nw_t(pd.Series(hv))
    return dict(names=names, start=str(d.index[0].date()), end=str(d.index[-1].date()), n=int(len(d)),
                r2_in_sample=float(r2), oos_var_reduction=float(vr), oos_n=int(m.sum()),
                factor_component_mean_ann=hedge_mean_ann, factor_component_nw_t=hedge_t)
    # No hedged Sharpe is reported: a hedged book is a variant, and comparing variants is a
    # trial (W10-B's rule). The variance reduction is the diagnostic; it is negative.


def main():
    T, R, R_tr, H, p = c.live_book()
    nav_part, disc_part, hold_ok, navr, cover = decomposition(H, R, p["nav"])
    for s, k in ((nav_part, "nav_part"), (disc_part, "disc_part"), (hold_ok, "hold")):
        c.assert_fit(s, k)
    out = dict(spec=c.SPEC_LINE, panel_last=str(R.index.max().date()), split_coverage=cover)

    # 1. decomposition by era (active days only; units: fraction of unit-book capital)
    act = H.abs().sum(axis=1).shift(2).fillna(0) > 0
    rows = []
    for lab, a, b in c.ERAS + (("fit 2005-22", "2005-01-01", "2022-12-30"),):
        m = act & (nav_part.index >= a) & (nav_part.index <= b)
        if m.sum() < 30:
            continue
        n_, d_, h_ = nav_part[m], disc_part[m], hold_ok[m]
        # 25-session non-overlapping sums: the live attribution's window length
        blk = np.arange(m.sum()) // 25
        n25 = n_.groupby(blk).sum(); d25 = d_.groupby(blk).sum(); h25 = h_.groupby(blk).sum()
        rows.append(dict(era=lab, days=int(m.sum()),
                         nav_ann_pct=100 * n_.mean() * 252, nav_t=c.nw_t(n_),
                         disc_ann_pct=100 * d_.mean() * 252, disc_t=c.nw_t(d_),
                         hold_ann_pct=100 * h_.mean() * 252, hold_sr=c.ann_sharpe(h_),
                         vol_nav_pct=100 * n_.std() * np.sqrt(252), vol_disc_pct=100 * d_.std() * np.sqrt(252),
                         vol_hold_pct=100 * h_.std() * np.sqrt(252),
                         corr_daily=float(n_.corr(d_)), corr_25d=float(n25.corr(d25)),
                         share_25d_nav_bigger_than_hold=float((n25.abs() > h25.abs()).mean()),
                         share_25d_nav_neg_disc_pos=float(((n25 < 0) & (d25 > 0)).mean())))
    dec = pd.DataFrame(rows)
    out["decomposition"] = dec.to_dict(orient="records")
    print("1. NAV part vs discount part, unit book, active days (% of capital per year)")
    print(dec.round(3).to_string(index=False))

    # 2. NAV-lag forecast known at t
    F = lag_forecast(R, navr, H)
    c.assert_fit(F, "forecast")
    pred = (H * F).sum(axis=1, min_count=1)           # decided at t ...
    pred_at_earn = pred.shift(2)                      # ... realised over t+2 (same lag as held(H))
    res2 = {}
    for nm, y in (("nav_part", nav_part), ("disc_part", disc_part), ("hold_NEGATIVE_CONTROL", hold_ok)):
        m = act & pred_at_earn.notna()
        b, t, n = ols_nw(y[m], pred_at_earn[m])
        res2[nm] = dict(slope=b, nw_t=t, n=n)
    # the forecast's own size: how much NAV-part variance it can explain
    m = act & pred_at_earn.notna()
    res2["corr_pred_navpart"] = float(pred_at_earn[m].corr(nav_part[m]))
    res2["sd_pred_vs_sd_navpart"] = float(pred_at_earn[m].std() / nav_part[m].std())
    # second method: the NAV's own lags
    F2 = ar_forecast(navr)
    c.assert_fit(F2, "ar forecast")
    pred2 = (H * F2).sum(axis=1, min_count=1).shift(2)
    m2 = act & pred2.notna()
    for nm, y in (("AR_nav_part", nav_part), ("AR_disc_part", disc_part), ("AR_hold_NEGATIVE_CONTROL", hold_ok)):
        b, t, n = ols_nw(y[m2], pred2[m2])
        res2[nm] = dict(slope=b, nw_t=t, n=n)
    res2["AR_corr_pred_navpart"] = float(pred2[m2].corr(nav_part[m2]))
    out["lag_forecast"] = res2
    print("\n2. NAV-lag forecast known at t -> realised at t+2 (slope per unit forecast, NW t)")
    for k, v in res2.items():
        print(f"  {k}: {v}")

    # 3. hedgeable share
    Fx = etf_factors()
    pnl_tr = (held(H) * R_tr).sum(axis=1)
    c.assert_fit(pnl_tr, "pnl_tr")
    res3 = []
    for lab, y in (("hold (price)", hold_ok), ("hold (total return)", pnl_tr), ("NAV part", nav_part)):
        for names, start in ((["MUB", "HYG", "IEF", "LQD"], "2008-01-02"),
                             (["MUB", "HYG", "IEF", "LQD", "BKLN"], "2012-01-03"),
                             (["MUB", "HYG", "IEF", "LQD", "BKLN"], "2015-01-02")):
            r = hedge_share(y, Fx, names, start)
            r["series"] = lab
            res3.append(r)
    h3 = pd.DataFrame(res3)[["series", "names", "start", "end", "n", "r2_in_sample", "oos_var_reduction",
                             "factor_component_mean_ann", "factor_component_nw_t"]]
    h3["names"] = h3["names"].apply(lambda v: "+".join(v))
    out["hedge"] = h3.to_dict(orient="records")
    # second method: position-based (ex-ante) hedge
    res3b = []
    for names, start in ((["MUB", "HYG", "IEF", "LQD"], "2008-01-02"), (["MUB", "HYG", "IEF", "LQD", "BKLN"], "2012-01-03")):
        hd = position_hedge(H, R, Fx, names)
        # price betas hedge the price-based hold only (a NAV-part hedge would need NAV betas)
        for lab, y in (("hold (price)", hold_ok),):
            m = act & hd.notna() & (y.index >= start)
            yv, hv = y[m], hd[m]
            res3b.append(dict(series=lab, names="+".join(names), n=int(m.sum()),
                              oos_var_reduction=float(1 - (yv - hv).var() / yv.var()),
                              corr=float(yv.corr(hv)), hedge_mean_ann=float(hv.mean() * 252),
                              hedge_nw_t=c.nw_t(hv)))
    h3b = pd.DataFrame(res3b)
    out["hedge_position_based"] = h3b.to_dict(orient="records")
    print("\n3b. position-based hedge (per-name trailing betas x held weight), second method")
    print(h3b.round(4).to_string(index=False))
    print("\n3. hedgeable share (Dimson lags 0-2; OOS betas trailing 252 strictly before)")
    print(h3.round(4).to_string(index=False))
    (HERE / "angle_nav_leg_output.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
