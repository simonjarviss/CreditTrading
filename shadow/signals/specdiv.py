"""Special dividends: hold the wait between the announcement and the ex-date.

THE IDEA (results/ideas/2026-11-15_special_dividends.md). A US common stock that announced a
special cash dividend of 1% or more gained about 1.2% against IWM between the session after
the news and the close before the ex-date, 2000-2025: gross Sharpe 1.10 at 10% a name, 0.62
on names trading $5M a day. Gross; borrow is not needed (the stock is the long side).

THE BOOK
  `wait`   LONG each eligible company for 10% of the book, SHORT IWM for the same amount;
           both sides scaled down together when there are more than five names (50% a side).

WHICH DECISIONS HOLD A NAME. The engine fills a decision at the next close and the book then
earns the session after that: a weight decided at D earns session D+2. The research earns
every session up to and including X-1, the one before the ex-date X, and never X itself. So
a name is held on decisions D with
    E <= D   and   D+2 <= X-1, that is X at least three sessions after D,
where E is the first session on or after the day this desk first saw the row. The event
panel is point-in-time by `first_seen` (shadow/fetch/specdivs.py): the engine has already
removed every row not seen by D, so a late row is a shorter trade, never hindsight. The
research entered one session after the announcement; when Alpaca lists a row later than
that the book simply starts later, and the scoreboard shows what that costs.

ELIGIBLE, judged ONCE at E on prices through E, as the research judged it at its decision:
a close of $2 or more, a 21-session average dollar volume of $500,000 or more, and a yield
(the special amount over that close) of 1% or more. Two special rows for one company and
ex-date are added together. After E the name must still print a close ON D: a company that
did not trade today is not bought tomorrow on yesterday's price.

WHAT COUNTS AS A COMPANY. The research used CRSP's common-share code, which no free live
feed carries. Here: Alpaca's own `foreign` flag is already dropped by the reader; the asset
record must name an exchange this desk can read a closing print for; the asset's name must
not read as a fund, a unit, a preferred or a depositary receipt; and symbols in the desk's
closed-end fund and unit universes are left to their own books. This is an approximation of
the research universe and the card says so.
"""
from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path

import pandas as pd

from ops.schedule.nyse_calendar import next_trading_day

HEDGE = "IWM"
SIZE, CAP = 0.10, 0.50
MIN_PRICE, MIN_ADV, MIN_YIELD, ADV_WINDOW, MIN_ADV_DAYS = 2.0, 500_000.0, 0.01, 21, 10
MIN_SESSIONS_TO_EX = 3
MARKABLE_EXCHANGES = frozenset({"NYSE", "NASDAQ", "AMEX", "ARCA", "TXSE"})
NOT_A_COMPANY = re.compile(r"\bfund\b|\betf\b|\btrust\b|\bunits?\b|preferred|depositary|\badr\b|\bnotes?\b|warrant|"
                           r"\brights?\b|limited partnership|\bl\.?p\.?\b", re.I)
PX, EVENTS = "px", "specdivs"
OTHER_UNIVERSES = ("cef_v1", "units_v1")


def _other_books() -> frozenset:
    out = set()
    for u in OTHER_UNIVERSES:
        with open(Path(__file__).resolve().parents[1] / "universes" / f"{u}.csv") as f:
            out |= {r["symbol"] for r in csv.DictReader(f)}
    return frozenset(out)


def sessions_until(asof: dt.date, x: dt.date, most: int = MIN_SESSIONS_TO_EX) -> int:
    """Trading sessions strictly after `asof` up to and including `x`, counted up to `most`.
    0 when `x` is on or before `asof`. An `x` that is not a session counts the sessions
    before it."""
    n, d = 0, asof
    while n < most:
        d = next_trading_day(d)
        if d > x:
            break
        n += 1
    return n


def candidates(events: pd.DataFrame, asof: dt.date) -> dict:
    """{symbol: (first_seen, ex_date, total special amount)} for rows that can be a US company
    with an ex-date at least MIN_SESSIONS_TO_EX sessions after `asof`. A symbol with two live
    ex-dates keeps the nearer one."""
    skip = _other_books()
    acc: dict = {}
    for r in events.to_dict("records"):
        sym = r["symbol"]
        if sym == HEDGE or sym in skip or r["exchange"] not in MARKABLE_EXCHANGES or NOT_A_COMPANY.search(r["name"] or ""):
            continue
        x = pd.Timestamp(r["ex_date"]).date()
        if sessions_until(asof, x) < MIN_SESSIONS_TO_EX:
            continue
        k = (sym, x)
        seen, amt = acc.get(k, (pd.Timestamp(r["first_seen"]).date(), 0.0))
        acc[k] = (min(seen, pd.Timestamp(r["first_seen"]).date()), amt + float(r["amount"]))
    out: dict = {}
    for (sym, x), (seen, amt) in sorted(acc.items()):
        if sym not in out or x < out[sym][1]:
            out[sym] = (seen, x, amt)
    return out


def wait(asof: dt.date, panels: dict) -> pd.Series:
    px = panels[PX].copy()
    px["date"] = pd.to_datetime(px["date"]).dt.date
    px = px[px["date"] <= asof].dropna(subset=["close"]).sort_values("date")
    hedge = px[px["symbol"] == HEDGE]
    if hedge.empty or hedge["date"].iloc[-1] != asof:
        return pd.Series(dtype=float)                       # no hedge price today: hold nothing
    longs = []
    for sym, (seen, x, amount) in candidates(panels[EVENTS], asof).items():
        g = px[px["symbol"] == sym]
        if g.empty or g["date"].iloc[-1] != asof:
            continue                                         # it did not print today
        upto = g[g["date"] >= seen]
        if upto.empty:
            continue
        e = upto["date"].iloc[0]                             # E: the first session on or after first_seen
        tail = g[g["date"] <= e].tail(ADV_WINDOW)            # eligibility on prices through E only
        dv = (tail["close"] * tail["volume"]).dropna()
        close_e = tail["close"].iloc[-1]
        if len(dv) >= MIN_ADV_DAYS and close_e >= MIN_PRICE and dv.mean() >= MIN_ADV and amount / close_e >= MIN_YIELD:
            longs.append(sym)
    if not longs:
        return pd.Series(dtype=float)
    size = min(SIZE, CAP / len(longs))
    w = {s: size for s in longs}
    w[HEDGE] = -size * len(longs)
    return pd.Series(w)
