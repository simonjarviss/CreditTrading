"""Explore: closed-end funds keep falling after the ex-date. Every CEF on CRSP, dead funds included.

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_cefs.py
    python3 results/ideas/cef_exdate_drift/explore.py

FIXED BEFORE LOOKING
  event      a session X on which a fund goes ex an ordinary distribution (CRSP `dlyorddivamt` > 0).
  trade      short the fund from X's close to the close three sessions later, earning the
             returns of X+1, X+2 and X+3. Against it, long every other eligible fund equally,
             so the book is dollar neutral and what is left is the event funds' return
             relative to funds that are not in a window.
  eligible   price of $2 or more and a 21-session average dollar volume of $500,000 or more,
             both known the session before.
  sizing     half the book short, split equally across funds in a window; half long, split
             equally across the rest. Unit gross.
  convention shift(2) on the canonical harness. The weight that earns X+1 is decided at X-1,
             so the ex-date must be known the session before it. Ex-dates are declared weeks
             ahead by the fund; CRSP does not carry the declaration date, so that is [U] here
             and the shadow book must read declared ex-dates from a live source.
Returns are CRSP total returns, so the short is charged the distribution only if it is held
through an ex-date, which this trade never is (it opens at the ex-date's close).
Controls: placebo events ten sessions after each real one; and the mean return on each
session from X-3 to X+6, event funds minus the equal-weighted eligible universe.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False      # scripts/research/explore.py says why
HERE = Path(__file__).resolve().parent
PANEL = Path.home() / "quantt_research" / "crsp_cef_daily.parquet"
HOLD, MIN_PRICE, MIN_ADV = 3, 2.0, 500_000.0


def book(in_window: pd.DataFrame, eligible: pd.DataFrame) -> pd.DataFrame:
    """Signed exposure EARNED each session: -0.5 across window funds, +0.5 across the rest."""
    short = (in_window & eligible).astype(float)
    long_ = (~in_window & eligible).astype(float)
    ns, nl = short.sum(axis=1), long_.sum(axis=1)
    both = (ns > 0) & (nl > 0)                      # a day with no event fund, or no other fund, is flat
    w = long_.div(nl.where(both), axis=0).mul(0.5) - short.div(ns.where(both), axis=0).mul(0.5)
    return w.fillna(0.0)


def main() -> int:
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    last = df["date"].max().date()
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc")
    dv = df.pivot(index="date", columns="permno", values="dollar_volume")
    ex = df.pivot(index="date", columns="permno", values="div").fillna(0.0) > 0
    # ALIGNMENT. Eligibility for the session that EARNS s uses price and volume through s-1
    # (shift(1)); the harness then moves the decision two sessions earlier still, so a filter
    # dated s-1 is applied a touch late rather than early. `in_window` for session s is true
    # when an ex-date fell on s-1, s-2 or s-3: it reads only the ex-date calendar.
    eligible = ((prc >= MIN_PRICE) & (dv.rolling(21, min_periods=10).mean() >= MIN_ADV)).shift(1, fill_value=False)
    in_window = pd.concat([ex.shift(k, fill_value=False) for k in range(1, HOLD + 1)]).groupby(level=0).any()
    earn = book(in_window, eligible)
    H = earn.shift(-harness.EXEC_LAG).fillna(0.0)
    held = earn != 0
    gone = int((held & ret.isna()).sum().sum())
    R = ret.fillna(0.0)                                  # a fund with no row has stopped trading (see stage script)
    res_h = harness.evaluate(H, R)
    pnl = res_h["pnl"].iloc[30:-harness.EXEC_LAG]
    plc_w = pd.concat([ex.shift(k + 10, fill_value=False) for k in range(1, HOLD + 1)]).groupby(level=0).any()
    plc = harness.evaluate(book(plc_w, eligible).shift(-harness.EXEC_LAG).fillna(0.0), R)["pnl"].reindex(pnl.index)
    short_leg = (earn.clip(upper=0) * R).sum(axis=1).reindex(pnl.index) * 2      # per unit short
    long_leg = (earn.clip(lower=0) * R).sum(axis=1).reindex(pnl.index) * 2
    # description: event funds minus the eligible universe, by session relative to the ex-date
    uni = ret.where(eligible).mean(axis=1)
    rel = ret.sub(uni, axis=0)
    prof = {}
    for k in range(-3, 7):
        v = rel.where(ex.shift(k, fill_value=False) & eligible).stack()
        prof[f"X{k:+d}"] = {"mean_bp": float(v.mean() * 1e4), "t": float(v.mean() / v.std() * np.sqrt(len(v))), "n": int(len(v))}
    n_events = int((ex & eligible).sum().sum())
    adv = dv.rolling(21, min_periods=10).mean()
    share = (earn.clip(upper=0).abs() / adv).where(earn < 0).loc["2024-01-01":].stack()
    res = explore.summarise(pnl, controls={"placebo events (X+10)": plc}, extra={
        "panel_last_date": str(last), "eligible_events": n_events,
        "events_per_year": float(n_events / (len(ret) / 252)),
        "funds_short_per_day_mean": float((earn < 0).sum(axis=1).mean()),
        "funds_long_per_day_mean": float((earn > 0).sum(axis=1).mean()),
        "turnover_per_year": float(res_h["turn"]), "held_name_days_with_no_row": gone,
        "short_leg_fund_return_per_year": float(-short_leg.mean() * 252),
        "long_leg_fund_return_per_year": float(long_leg.mean() * 252),
        "event_time_profile": prof,
        "capacity_short_leg_2024_on": {f"pct_of_adv_at_{s // 10**6}M": {"median": float(share.median() * s * 100),
                                       "p95": float(share.quantile(0.95) * s * 100)} for s in (10**6, 5 * 10**6, 10**7)}})
    explore.write(HERE, res, pnl, title=f"Short CEFs for 3 sessions after the ex-date, long the rest; shift(2), gross; to {last}",
                  controls={"placebo events (X+10)": plc})
    print("panel to", last, "| events", n_events, "| per year", round(res["events_per_year"]), "| short/long funds a day",
          round(res["funds_short_per_day_mean"]), round(res["funds_long_per_day_mean"]), "| turnover/yr", round(res["turnover_per_year"], 1), "| no-row", gone)
    print(explore.table(res))
    print("event funds earned", f"{res['short_leg_fund_return_per_year']:.2%}", "a year while in a window; the others", f"{res['long_leg_fund_return_per_year']:.2%}")
    print(" ".join(f"{k}:{v['mean_bp']:+.1f}({v['t']:+.1f})" for k, v in prof.items()))
    print(res["capacity_short_leg_2024_on"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
