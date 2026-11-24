"""Explore: the equity turn of the month. Long SPY over the last session of a month and
the first three of the next; flat otherwise. Gross, shift(2), on the canonical harness.

    python3 scripts/research/fetch_yf_daily.py SPY IEF TLT SHY IEI QQQ IWM HYG LQD
    python3 results/ideas/turn_of_month_eq/explore.py

The window is fixed here, before looking: sessions E, E+1, E+2, E+3, with E the month's
last session (the classic definition). The decision that earns session S is made two
sessions before S, from the calendar alone, which is published in advance: no lookahead.
Control: SPY on every other session.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from ops.schedule.nyse_calendar import is_trading_day  # noqa: E402
from scripts.research import explore, harness  # noqa: E402
from shadow.signals.month_end import month_end_session  # noqa: E402

HERE = Path(__file__).resolve().parent
SYMBOL, AFTER = "SPY", 3


def in_window(cal: pd.DatetimeIndex) -> pd.Series:
    """1.0 on E..E+AFTER of every month, by position in the session calendar."""
    w = pd.Series(0.0, index=cal)
    # E = the last panel date of each calendar month. For history this is the month's last
    # session by definition, and it does not depend on a holiday table. (The repo's NYSE
    # calendar is wrong before 1998: it closes on Martin Luther King Day, which the exchange
    # first observed in 1998, so it cannot date month ends in 1993-97.) The panel's final,
    # partial month is dropped: its last date is not a month end.
    s = pd.Series(cal, index=cal)
    ends = s.groupby([cal.year, cal.month]).max().iloc[:-1]
    pos = {d: i for i, d in enumerate(cal)}
    for E in ends:
        w.iloc[pos[E]:pos[E] + AFTER + 1] = 1.0
    return w


def main() -> int:
    df = pd.read_parquet(Path.home() / "quantt_research" / "yf_daily.parquet")
    x = df[df["ticker"] == SYMBOL].set_index("date").sort_index()
    bad = [d.date() for d in x.index if d.year >= 1998 and not is_trading_day(d.date())]
    if bad:
        raise SystemExit(f"panel dates from 1998 that the NYSE calendar says are not sessions: {bad[:5]}")
    # the live rule (shadow) uses the calendar, so the two definitions must agree where the calendar is right
    recent = [d for d in x.index if d.year >= 1998]
    by_cal = {month_end_session(d.date()) for d in recent[:-25]}
    by_panel = set(pd.Series(recent, index=recent).groupby([pd.DatetimeIndex(recent).year, pd.DatetimeIndex(recent).month]).max().dt.date.iloc[:-1])
    if by_cal - by_panel - {max(by_cal)}:
        raise SystemExit(f"calendar and panel disagree on month ends: {sorted(by_cal - by_panel)[:5]}")
    cal = x.index
    earn = in_window(cal)
    # ALIGNMENT: harness.evaluate holds H.loc[t] over the return of t+2. To EARN session S the
    # weight must sit on the row two sessions earlier, so H = earn.shift(-2). The shift reads
    # only the calendar (which sessions are in the window), never a price.
    H = pd.DataFrame({SYMBOL: earn.shift(-harness.EXEC_LAG).fillna(0.0)})
    R = pd.DataFrame({SYMBOL: x["ret_total"].fillna(0.0)})
    pnl = harness.evaluate(H, R)["pnl"].iloc[5:]
    ctrl = harness.evaluate(1.0 - H, R)["pnl"].iloc[5:]
    assert ((pnl != 0) <= (earn.reindex(pnl.index) == 1.0)).all()      # P&L only on window sessions
    dv = (x["close"] * x["volume"]).loc["2026-01-01":]
    res = explore.summarise(pnl, controls={"SPY on every other session": ctrl}, extra={
        "panel_last_date": str(cal.max().date()), "symbol": SYMBOL,
        "share_of_days_in_market": float((pnl != 0).mean()),
        "capacity": {"median_dollar_volume_2026": float(dv.median()),
                     **{f"pct_of_adv_at_{s // 10**6}M": float(s / dv.median() * 100) for s in (10**6, 5 * 10**6, 10**7)}}})
    explore.write(HERE, res, pnl, title=f"Long SPY on the last session of a month and the next three; shift(2), gross; to {cal.max().date()}",
                  controls={"SPY on every other session": ctrl})
    print("panel to", cal.max().date()); print(explore.table(res)); print(res["capacity"], res["share_of_days_in_market"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
