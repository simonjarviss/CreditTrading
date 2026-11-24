"""Explore: month-end Treasury demand (long IEF over the last three sessions), gross.

    python3 results/ideas/month_end_treasury/explore.py [--panel <etf_daily.parquet>]

Runs the shadow book's own signal (shadow/signals/month_end.py) through the canonical
harness (shift(2): decide t, fill t+1 close, earn t+2), on IEF total returns from the
desk's ETF panel. Gross only: no cost is modelled (team lead, 2026-11-09). Prints the
full sample, an early/late split, eras, the same position on every OTHER session as the
control, and capacity against the panel's dollar volume. Writes results.json and
equity.png beside this file. The panel's last date is printed first: stale is wrong.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from ops.schedule.nyse_calendar import is_trading_day  # noqa: E402
from scripts.research import harness  # noqa: E402
from shadow.signals import month_end as me  # noqa: E402

HERE = Path(__file__).resolve().parent
ERAS = [("2002-09-01", "2008-12-31"), ("2009-01-01", "2015-12-31"), ("2016-01-01", "2019-12-31"),
        ("2020-01-01", "2022-12-31"), ("2023-01-01", "2026-12-31")]


def stats(pnl: pd.Series) -> dict:
    pnl = pnl.dropna()
    sd = pnl.std()
    on = pnl[pnl != 0]
    return {"n_days": int(len(pnl)), "n_window_days": int(len(on)),
            "ann_ret": float(pnl.mean() * 252), "ann_vol": float(sd * np.sqrt(252)),
            "sharpe": float(pnl.mean() / sd * np.sqrt(252)) if sd > 0 else None,
            "t": float(pnl.mean() / sd * np.sqrt(len(pnl))) if sd > 0 else None,
            "mean_bp_per_window_day": float(on.mean() * 1e4) if len(on) else None,
            "hit_rate_window_days": float((on > 0).mean()) if len(on) else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=Path.home() / "quantt_data" / "etf_daily.parquet")
    a = ap.parse_args(argv)
    df = pd.read_parquet(a.panel)
    x = df[df["ticker"] == me.SYMBOL].sort_values("date").set_index("date")
    if x.empty:
        raise SystemExit(f"{a.panel} has no {me.SYMBOL} rows")
    if x["ret_total"].iloc[1:].isna().any():
        raise SystemExit(f"{me.SYMBOL} has a missing total return in {a.panel}")
    last = x.index.max().date()
    print(f"panel {a.panel.name}: {me.SYMBOL} {x.index.min().date()} .. {last}")
    cal = x.index
    not_sessions = [d.date() for d in cal if not is_trading_day(d.date())]
    if not_sessions:
        raise SystemExit(f"panel dates that the NYSE calendar says are not sessions: {not_sessions[:5]}")
    # ALIGNMENT: H.loc[t] is the weight DECIDED at t from the calendar alone; harness.evaluate
    # holds it over the return of t+2 (shift(2)). The last month in the panel may be partial:
    # its decision days are still correct, because they come from the calendar, not the panel.
    H = pd.DataFrame({me.SYMBOL: [float(len(me.signal(d.date(), {}))) for d in cal]}, index=cal)
    R = pd.DataFrame({me.SYMBOL: x["ret_total"].fillna(0.0)})      # first row only: no prior close
    res = harness.evaluate(H, R)
    pnl = res["pnl"].loc["2002-09-04":]
    ctrl = harness.evaluate(1.0 - H, R)["pnl"].loc["2002-09-04":]
    mid = pnl.index[len(pnl) // 2]
    out = {"panel_last_date": str(last), "symbol": me.SYMBOL, "convention": "shift(2), gross, weight 1.0 in window",
           "full": stats(pnl), "early_half": stats(pnl.loc[:mid]), "late_half": stats(pnl.loc[mid:]),
           "split_date": str(mid.date()),
           "eras": {f"{a_}..{b_}": stats(pnl.loc[a_:b_]) for a_, b_ in ERAS},
           "control_other_sessions": stats(ctrl),
           "turnover_per_year": float(res["turn"]),
           # exposure, reported not gated: the book IS IEF on its days, so its beta to IEF is its time in market
           "share_of_days_in_market": float((pnl != 0).mean())}
    dv = (x["prc_adj"] * x["volume"]).loc["2026-01-01":]
    out["capacity"] = {"median_dollar_volume_2026": float(dv.median()),
                       **{f"position_pct_of_adv_at_{s // 10**6}M": float(s / dv.median() * 100)
                          for s in (10**6, 5 * 10**6, 10**7)}}
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4))
    (pnl.cumsum() * 100).plot(ax=ax, label="month-end window (gross)")
    (ctrl.cumsum() * 100).plot(ax=ax, label="IEF on every other session", alpha=0.6)
    ax.set_ylabel("cumulative return, % of notional (not compounded)")
    ax.set_title(f"Long IEF over the last 3 sessions of each month; shift(2), gross; panel to {last}")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(HERE / "equity.png", dpi=110)
    return 0


if __name__ == "__main__":
    sys.exit(main())
