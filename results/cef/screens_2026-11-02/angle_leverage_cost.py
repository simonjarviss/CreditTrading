"""Angle D: leverage-cost pass-through. Do changes in the short financing rate predict the next
month's group discount drift of LEVERED FIXED-RATE credit CEFs, against floating-rate loan funds?
Zero trials; fit data only (<= 2022-12-30, asserted). MACRO-lane question (counter at 0).

MECHANISM. Leveraged CEFs borrow short (TOB floaters at SIFMA, VMTP/ARPS preferreds, repo,
credit lines). When short rates rise, net investment income falls with a lag, the board cuts
the distribution, and yield-screening retail sells; the discount widens. The z-score reads that
widening as cheap and buys it (BRIEF M4/M7: a level shift it cannot see). Who loses: the book,
if it buys a re-rating; or, if the widening is predictable, the holder who sells after the cut.

NEGATIVE CONTROL (H12, named first). Floating-rate loan funds (JFR, the only loan fund in the
17): their asset income resets with the same short rate, so leverage cost passes through to
both sides of the balance sheet and the channel is (approximately) shut. The test statistic is
the muni (or taxable fixed-rate) MINUS loan discount change. A second control separates the
leverage channel from duration: the regression carries IEF's same-month total return, so a
long-rate (NAV) effect is not credited to the short rate.

DATA. Discounts: the harness's own panel (band_frontier.build_panel) on the 13 deployed names plus
the four munis Alpaca will not lend (NAD, NEA, NVG, NZF): the 17 the book was built on; none of
the 27 sealed cef_universe.csv names is read. Short rate: data/financing_curve.parquet
`base_rate_pct` (DFF; last date 2026-07-20, truncated here at FIT_END). IEF: data/etf_daily.parquet.
ALIGNMENT: the predictor is the change in the month-END base rate over months m-3..m (known at the
close of month m); the outcome is the change in group mean discount from the last session of m to
the last session of m+1. Nothing from month m+1 enters the predictor.

Run from the repo root:  python3 -B results/cef/screens_2026-11-02/angle_leverage_cost.py
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
from scripts.cef import band_frontier as bf                     # noqa: E402

DROPPED_MUNIS = ["NAD", "NEA", "NVG", "NZF"]                   # trial 49: not shortable on Alpaca


def ols_nw(y, X, lags=3):
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    A = np.column_stack([np.ones(len(d)), d.drop(columns="y").values])
    b, *_ = np.linalg.lstsq(A, d["y"].values, rcond=None)
    e = d["y"].values - A @ b
    n = len(d)
    S = (A * e[:, None]).T @ (A * e[:, None]) / n
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = (A[L:] * e[L:, None]).T @ (A[:-L] * e[:-L, None]) / n
        S += w * (G + G.T)
    Q = np.linalg.inv(A.T @ A / n)
    V = Q @ S @ Q / n
    names = ["const"] + list(d.drop(columns="y").columns)
    return {nm: dict(b=float(b[i]), t=float(b[i] / np.sqrt(V[i, i]))) for i, nm in enumerate(names)} | {"n": n}


def main():
    univ = list(c.UNIVERSE) + DROPPED_MUNIS
    with c.fit_panels():
        p = bf.build_panel(universe=univ)
    disc = c.assert_fit(p["disc"], "disc")
    u = pd.read_csv(c.REPO / "data" / "cef" / "cef_universe.csv")[["ticker", "grp"]]
    grp = dict(zip(u.ticker, u.grp))
    groups = {"muni": [t for t in univ if grp[t] == "muni"],
              "taxable_fixed": [t for t in univ if grp[t] in ("multi", "hy")],
              "loan_CONTROL": [t for t in univ if grp[t] == "loan"]}
    me = disc.groupby(disc.index.to_period("M")).tail(1)          # last session of each month
    me.index = me.index.to_period("M")
    G = pd.DataFrame({g: me[names].mean(axis=1, skipna=True) for g, names in groups.items()})
    G = G.loc["2005-01":]
    dG = G.diff().shift(-1)                                       # change over month m+1, aligned to m
    fc = pd.read_parquet(c.REPO / "data" / "financing_curve.parquet")
    fc["date"] = pd.to_datetime(fc["date"])
    fc = fc[fc["date"] <= c.FIT_END].set_index("date")["base_rate_pct"]
    r_me = fc.groupby(fc.index.to_period("M")).last()
    d3 = (r_me - r_me.shift(3)).rename("d_short_3m")             # known at the end of m
    e = pd.read_parquet(c.REPO / "data" / "etf_daily.parquet", columns=["date", "ticker", "ret_total"])
    e = e[(e.ticker == "IEF") & (pd.to_datetime(e.date) <= c.FIT_END)].copy()
    e["date"] = pd.to_datetime(e["date"])
    ief_m = (1 + e.set_index("date")["ret_total"]).groupby(lambda d: d.to_period("M")).prod() - 1
    ief_next = ief_m.shift(-1).rename("ief_ret_m_plus_1")          # same month as the outcome (control)
    X = pd.concat([d3, ief_next], axis=1)
    out = dict(panel_last=str(disc.index.max().date()), groups=groups,
               months=[str(G.index.min()), str(G.index.max())])
    res = {}
    for lab, y in (("muni - loan", dG["muni"] - dG["loan_CONTROL"]),
                   ("taxable_fixed - loan", dG["taxable_fixed"] - dG["loan_CONTROL"]),
                   ("muni alone", dG["muni"]), ("loan alone (control)", dG["loan_CONTROL"])):
        y = y.loc[:"2022-11"]                                     # the m+1 outcome must end by 2022-12
        res[lab] = dict(short_only=ols_nw(y, X[["d_short_3m"]]), with_ief=ols_nw(y, X))
        print(f"{lab:24s} short-only: b {res[lab]['short_only']['d_short_3m']['b']:+.3f} pp disc per pp rate "
              f"(t {res[lab]['short_only']['d_short_3m']['t']:+.2f}); with IEF: b "
              f"{res[lab]['with_ief']['d_short_3m']['b']:+.3f} (t {res[lab]['with_ief']['d_short_3m']['t']:+.2f}); "
              f"n {res[lab]['with_ief']['n']}")
    # sensitivity (declared, nothing chosen from it): the outcome over m+1..m+3, because NII
    # passes into distributions with a lag. Overlapping months, so NW lags 5.
    dG3 = (G.shift(-3) - G)
    for lab, y in (("3m: muni - loan", dG3["muni"] - dG3["loan_CONTROL"]),
                   ("3m: taxable_fixed - loan", dG3["taxable_fixed"] - dG3["loan_CONTROL"])):
        y = y.loc[:"2022-09"]                                     # m+3 must end by 2022-12
        r = ols_nw(y, X[["d_short_3m"]], lags=5)
        res[lab] = dict(short_only=r)
        print(f"{lab:24s} short-only: b {r['d_short_3m']['b']:+.3f} (t {r['d_short_3m']['t']:+.2f}); n {r['n']}")
    # how many independent episodes: months with |d_short_3m| >= 0.5pp, grouped into runs
    big = (d3.loc["2005-01":"2022-11"].abs() >= 0.5)
    runs = int(((big != big.shift()) & big).sum())
    out["episodes_abs_3m_change_ge_50bp"] = dict(months=int(big.sum()), runs=runs)
    print(f"episodes: {int(big.sum())} months with |3m change| >= 50bp, in {runs} runs")
    out["regressions"] = res
    (HERE / "angle_leverage_cost_output.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
