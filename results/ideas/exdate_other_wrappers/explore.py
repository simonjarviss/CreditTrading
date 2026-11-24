"""Explore: is the fall after the ex-date a closed-end fund quirk, or do other wrappers have it?

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_exdate_groups.py
    python3 results/ideas/exdate_other_wrappers/explore.py

FIXED BEFORE LOOKING: the closed-end fund test, unchanged, run on four other groups. The
event, the three-session short against an equal-weighted long in the group's other eligible
names, the $2 price and $500,000 volume filters, and shift(2) are all imported from
results/ideas/cef_exdate_drift/explore.py, so nothing here was tuned to a group.
  etf     every ETF on CRSP that ever paid an ordinary distribution
  reit    common shares with SIC code 6798
  units   partnership and trust units (CRSP sharetype UG)
  common  the 1,500 largest US common stocks (previous month-end rank), REITs included
Dead securities are in every group. Ex-dates are assumed known the session before, as in the
fund test; companies and funds declare them ahead, and CRSP's declaration date is not staged [U].

WHAT THE LONG LEG MEANS HERE: in a mixed group (ETFs hold bonds, stocks and commodities) the
long leg is a noisy hedge, so the book's Sharpe understates a real effect. The event-time
profile, event names less the group's eligible average, is the cleaner reading.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
_spec = importlib.util.spec_from_file_location("cef_exdate", REPO / "results/ideas/cef_exdate_drift/explore.py")
cef = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(cef)
HOLD, MIN_PRICE, MIN_ADV = cef.HOLD, cef.MIN_PRICE, cef.MIN_ADV
GROUPS = {"etf": "crsp_exdate_etf_daily.parquet", "reit": "crsp_exdate_reit_daily.parquet",
          "units": "crsp_exdate_units_daily.parquet", "common": "crsp_top2000_daily.parquet"}


def one(group: str, file: str) -> tuple[dict, pd.Series, pd.Series]:
    df = pd.read_parquet(RES / file)
    df["date"] = pd.to_datetime(df["date"])
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc")
    dv = df.pivot(index="date", columns="permno", values="dollar_volume")
    ex = df.pivot(index="date", columns="permno", values="div").fillna(0.0) > 0
    # ALIGNMENT, as in the fund test: eligibility for the session that earns s is dated s-1.
    ok = (prc >= MIN_PRICE) & (dv.rolling(21, min_periods=10).mean() >= MIN_ADV)
    if group == "common":
        ok &= df.pivot(index="date", columns="permno", values="cap_rank") <= 1500
    eligible = ok.shift(1, fill_value=False)
    win = lambda lag: pd.concat([ex.shift(k + lag, fill_value=False) for k in range(1, HOLD + 1)]).groupby(level=0).any()  # noqa: E731
    R = ret.fillna(0.0)
    earn = cef.book(win(0), eligible)
    res_h = harness.evaluate(earn.shift(-harness.EXEC_LAG).fillna(0.0), R)
    pnl = res_h["pnl"].iloc[30:-harness.EXEC_LAG]
    plc = harness.evaluate(cef.book(win(10), eligible).shift(-harness.EXEC_LAG).fillna(0.0), R)["pnl"].reindex(pnl.index)
    rel = ret.sub(ret.where(eligible).mean(axis=1), axis=0)
    prof = {}
    for k in range(-3, 7):
        v = rel.where(ex.shift(k, fill_value=False) & eligible).stack()
        prof[f"X{k:+d}"] = {"mean_bp": float(v.mean() * 1e4), "t": float(v.mean() / v.std() * np.sqrt(len(v))), "n": int(len(v))}
    n = int((ex & eligible).sum().sum())
    res = explore.summarise(pnl, controls={"placebo events (X+10)": plc}, extra={
        "panel_last_date": str(df["date"].max().date()), "eligible_events": n,
        "events_per_year": float(n / (len(ret) / 252)),
        "names_short_per_day_mean": float((earn < 0).sum(axis=1).mean()),
        "names_long_per_day_mean": float((earn > 0).sum(axis=1).mean()),
        "turnover_per_year": float(res_h["turn"]), "event_time_profile": prof})
    return res, pnl, plc


def main() -> int:
    out = {}
    for g, f in GROUPS.items():
        res, pnl, plc = one(g, f)
        out[g] = res
        d = HERE / g
        d.mkdir(exist_ok=True)
        explore.write(d, res, pnl, title=f"{g}: short for 3 sessions after the ex-date, long the rest; shift(2), gross; to {res['panel_last_date']}",
                      controls={"placebo events (X+10)": plc})
        p = res["event_time_profile"]
        print(f"\n== {g}: panel to {res['panel_last_date']} | events {res['eligible_events']:,} ({res['events_per_year']:.0f}/yr) | "
              f"short/long a day {res['names_short_per_day_mean']:.0f}/{res['names_long_per_day_mean']:.0f} | turnover/yr {res['turnover_per_year']:.0f}")
        print(explore.table(res))
        print(" ".join(f"{k}:{v['mean_bp']:+.1f}({v['t']:+.1f})" for k, v in p.items()))
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
