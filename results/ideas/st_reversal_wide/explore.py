"""Explore: short-term reversal within industry, on the 1,500 largest US common stocks.

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_equities.py --top 2000
    python3 results/ideas/st_reversal_wide/explore.py

FIXED BEFORE LOOKING
  signal at t   minus the stock's 5-session return ending at t, less its industry's mean
                (2-digit SIC, at least 5 names), among stocks ranked in the top 1,500 by the
                previous month-end's market value and priced at $5 or more at t.
  weights       the signal divided by the sum of its absolute values: unit gross, dollar
                neutral within each industry by construction.
  convention    shift(2) on the canonical harness: decided at t, filled at t+1's close, earns
                t+2. The one-session gap between the signal and the fill is what keeps
                bid-ask bounce out of the result.
Gross only; no cost is modelled (team lead, 2026-11-09). This idea turns over fast, and what
that costs is for paper to measure, not for this file to guess.

THE PANEL holds ranks to 2,000 so that a stock that slips out of the top 1,500 keeps its
returns while the book still holds it. A held stock with NO row at all has stopped trading:
CRSP puts the delisting return on its last row, so afterwards its return is zero, not
missing. Those name-days are counted and printed.
Controls: the same signal 21 sessions stale; and the signal without the industry step.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

# `explore` turns numexpr off at import (its comment says why). This script's weights are
# broadcast arithmetic on a 45-million-cell frame, the exact case that fault corrupts.
assert pd.get_option("compute.use_numexpr") is False

HERE = Path(__file__).resolve().parent
PANEL = Path.home() / "quantt_research" / "crsp_top2000_daily.parquet"
TRADE_RANK, MIN_PRICE, WINDOW, MIN_INDUSTRY = 1500, 5.0, 5, 5


def weights(sig: pd.DataFrame, ind: pd.DataFrame | None) -> pd.DataFrame:
    if ind is not None:
        out = []
        for d in sig.index:
            s = sig.loc[d].dropna()
            g = ind.loc[d].reindex(s.index)
            n = s.groupby(g).transform("size")
            s = (s - s.groupby(g).transform("mean"))[n >= MIN_INDUSTRY]
            out.append(s.rename(d))
        sig = pd.DataFrame(out).reindex(columns=sig.columns)
    else:
        sig = sig.sub(sig.mean(axis=1), axis=0)
    # A day with no usable signal has a zero denominator: that day is FLAT (weight 0), which
    # is what the book would be. Dividing by it instead gave an infinite weight on the first
    # run, and the harness refused it.
    gross = sig.abs().sum(axis=1)
    return sig.div(gross.where(gross > 1e-12), axis=0).fillna(0.0)


def main() -> int:
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    last = df["date"].max().date()
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc")
    rank = df.pivot(index="date", columns="permno", values="cap_rank")
    ind = df.assign(i=df["siccd"] // 100).pivot(index="date", columns="permno", values="i")
    dv = df.pivot(index="date", columns="permno", values="dollar_volume")
    # ALIGNMENT: every input to the signal at t is dated <= t. The 5-session return ends at t;
    # rank is the previous month-end's; price is t's close. min_periods = WINDOW, so a stock
    # with a missing return inside the window has no signal that day.
    r5 = ret.rolling(WINDOW, min_periods=WINDOW).sum()
    ok = (rank <= TRADE_RANK) & (prc >= MIN_PRICE) & r5.notna()
    sig = (-r5).where(ok)
    H = weights(sig, ind)
    held = H.shift(harness.EXEC_LAG).fillna(0.0) != 0
    gone = int((held & ret.isna()).sum().sum())
    R = ret.fillna(0.0)
    res_h = harness.evaluate(H, R)
    pnl = res_h["pnl"].iloc[WINDOW + harness.EXEC_LAG:]
    stale = harness.evaluate(weights(sig.shift(21), ind.shift(21)), R)["pnl"].reindex(pnl.index)
    raw = harness.evaluate(weights(sig, None), R)["pnl"].reindex(pnl.index)
    # exposure, reported not gated: beta to the equal-weighted return of the tradable set
    mkt = ret.where(rank <= TRADE_RANK).mean(axis=1).reindex(pnl.index)
    beta = float(np.cov(pnl, mkt)[0, 1] / mkt.var())
    # two regimes: sessions when the market's trailing 21-session volatility is above or below its median
    vol = mkt.rolling(21).std().shift(harness.EXEC_LAG)         # known two sessions before the return it labels
    hi = vol > vol.median()
    # capacity: each position against that stock's own 21-session average dollar volume, known at t
    adv = dv.rolling(21, min_periods=10).mean()
    share = (H.abs() / adv).replace([np.inf, -np.inf], np.nan).loc["2024-01-01":]
    nz = share.where(H.loc["2024-01-01":] != 0).stack()
    res = explore.summarise(pnl, controls={"signal 21 sessions stale": stale, "no industry step": raw}, extra={
        "panel_last_date": str(last), "names_per_day_mean": float((H != 0).sum(axis=1).mean()),
        "turnover_per_year": float(res_h["turn"]), "beta_to_equal_weight_market": beta,
        "held_name_days_with_no_row": gone,
        "regimes": {"market vol above median": explore.stats(pnl[hi.reindex(pnl.index).fillna(False)]),
                    "market vol below median": explore.stats(pnl[~hi.reindex(pnl.index).fillna(True)])},
        "capacity_2024_on": {f"position_pct_of_adv_at_{s // 10**6}M": {"median": float(nz.median() * s * 100),
                             "p95": float(nz.quantile(0.95) * s * 100)} for s in (10**6, 5 * 10**6, 10**7)}})
    explore.write(HERE, res, pnl, title=f"Reversal within industry, top 1,500 US stocks; shift(2), gross, unit gross; to {last}",
                  controls={"signal 21 sessions stale": stale})
    print("panel to", last, "| names a day", round(res["names_per_day_mean"]), "| turnover/yr", round(res["turnover_per_year"], 1),
          "| beta", round(beta, 3), "| held name-days with no row", gone)
    print(explore.table(res))
    for k, v in res["regimes"].items():
        print(k, "Sharpe", round(v["sharpe"], 2), "ret/yr", f"{v['ann_ret']:.2%}", "n", v["n_days"])
    print(res["capacity_2024_on"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
