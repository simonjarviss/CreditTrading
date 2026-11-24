"""The ex-date cycle in closed-end funds: two shadow books from one card.

THE IDEA (results/ideas/2026-11-10_cef_exdate_drift.md). Income investors buy a fund to
collect its distribution and sell once they have it: across every closed-end fund on CRSP,
2000-2025, a fund rose about 22bp against other funds over the three sessions before its
ex-date and fell about 30bp over the three after. Gross; each event is small.

THE TWO BOOKS
  `after`        the pre-specified one: SHORT a fund over the three sessions after its
                 ex-date X (earning X+1, X+2, X+3), LONG every other eligible fund equally.
  `before_after` found after looking at the event profile, so not pre-specified: LONG a
                 fund over X-3, X-2, X-1 and SHORT it over X+1, X+2, X+3; nothing else held.
Both are half long and half short: unit gross, dollar neutral. A day with no fund on one
side is flat, never one-sided.

WHICH EX-DATES A DECISION AT D USES. The engine fills a decision at the next close and the
book then earns the session after that: a weight decided at D earns session D+2. So
  short (post-ex) funds are those with X in {D-1, D, D+1}    (D+2 is X+3, X+2 or X+1)
  long  (pre-ex)  funds are those with X in {D+3, D+4, D+5}  (D+2 is X-1, X-2 or X-3)
counted in trading sessions. Two of those need a FUTURE ex-date, which is why the ex-date
panel is point-in-time by `first_seen` (shadow/fetch/exdates.py): the engine has already
removed every row this desk had not seen by D, so a late declaration is simply a missed
event, not a lookahead.

ELIGIBLE at D: last close of $2 or more and a 21-session average dollar volume of $500,000
or more, from the price panel through D; and the fund must have a close ON D (a fund that
did not print today is not traded tomorrow on yesterday's price). The same filter as the
Explore test.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from ops.schedule.nyse_calendar import next_trading_day, previous_trading_day

MIN_PRICE, MIN_ADV, ADV_WINDOW, MIN_ADV_DAYS = 2.0, 500_000.0, 21, 10
PX, EX = "px", "exdates"


def _sessions_after(d: dt.date, n: int) -> dt.date:
    for _ in range(n):
        d = next_trading_day(d)
    return d


def post_dates(asof: dt.date) -> set:
    return {previous_trading_day(asof), asof, next_trading_day(asof)}


def pre_dates(asof: dt.date) -> set:
    return {_sessions_after(asof, k) for k in (3, 4, 5)}


def eligible(px: pd.DataFrame, asof: dt.date) -> list:
    """Symbols that printed on `asof` and pass the price and liquidity floor on data through it."""
    px = px.copy()
    px["date"] = pd.to_datetime(px["date"]).dt.date
    if px.empty or px["date"].max() != asof:
        return []
    px = px.sort_values("date")
    out = []
    for sym, g in px.groupby("symbol"):
        if g["date"].iloc[-1] != asof:
            continue
        tail = g.tail(ADV_WINDOW)
        dv = (tail["close"] * tail["volume"]).dropna()
        if len(dv) >= MIN_ADV_DAYS and tail["close"].iloc[-1] >= MIN_PRICE and dv.mean() >= MIN_ADV:
            out.append(sym)
    return sorted(out)


def _funds_with_ex_on(ex: pd.DataFrame, dates: set) -> set:
    if ex.empty:
        return set()
    d = pd.to_datetime(ex["ex_date"]).dt.date
    return set(ex.loc[d.isin(dates), "symbol"])


def _book(longs: set, shorts: set) -> pd.Series:
    longs, shorts = sorted(longs), sorted(shorts)
    if not longs or not shorts:
        return pd.Series(dtype=float)                      # never one-sided
    w = {s: 0.5 / len(longs) for s in longs}
    w.update({s: -0.5 / len(shorts) for s in shorts})
    return pd.Series(w)


def after(asof: dt.date, panels: dict) -> pd.Series:
    """Short the funds in their three sessions after an ex-date; long every other eligible fund."""
    el = set(eligible(panels[PX], asof))
    shorts = _funds_with_ex_on(panels[EX], post_dates(asof)) & el
    return _book(el - shorts, shorts)


def before_after(asof: dt.date, panels: dict) -> pd.Series:
    """Long the funds three sessions before an ex-date, short those three sessions after one."""
    el = set(eligible(panels[PX], asof))
    shorts = _funds_with_ex_on(panels[EX], post_dates(asof)) & el
    longs = (_funds_with_ex_on(panels[EX], pre_dates(asof)) & el) - shorts
    return _book(longs, shorts)
