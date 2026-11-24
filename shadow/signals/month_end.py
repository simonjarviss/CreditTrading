"""Month-end Treasury demand: long IEF over the last three sessions of each month.

THE IDEA (results/ideas/2026-11-10_month_end_treasury.md). Bond indices extend their
duration at each month end, and funds that track them buy duration into the close of the
last session. The desk tested it on 2026-10-14 as XASSET-X3
(`docs/RESEARCH_STATE.md`, KILLED table; code on branch `trial-xasset`,
scripts/xasset/x3_month_end.py, after Hartley & Schwarz 2019 as that file cites them):
the effect was present and was stopped for its term-premium exposure and its cost at an
assumed 15bp, two gates the team lead dropped on 2026-11-09. This is that rule, unchanged.

THE RULE, AND WHY THE DECISION DATES ARE WHAT THEY ARE. With E the month's last session,
the book is long from the close of E-3 to the close of E, earning the returns of E-2, E-1
and E. The shadow engine fills a decision at the NEXT close and holds it until a later
decision fills (shadow/engine.py), so the weight must be 1 on decisions made on E-4, E-3
and E-2, and 0 on every other session, E-1 included (that decision fills at E's close and
takes the book flat). The same three rows as X3's `window_rows`.

NO LOOKAHEAD. The only input is the exchange calendar, which is published years ahead.
The signal reads no panel, so there is nothing for it to see early.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from ops.schedule.nyse_calendar import is_trading_day, previous_trading_day

SYMBOL = "IEF"
WINDOW = 3            # sessions held to the month end (the rule's t = 3)


def month_end_session(d: dt.date) -> dt.date:
    """The last trading day of d's month."""
    first_next = (d.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    return previous_trading_day(first_next)


def sessions_before(end: dt.date, n: int) -> dt.date:
    """The session n trading days before `end` (n = 0 is `end`)."""
    d = end
    for _ in range(n):
        d = previous_trading_day(d)
    return d


def decision_days(d: dt.date) -> list:
    """E-4, E-3, E-2 for d's month: the decisions that carry weight."""
    E = month_end_session(d)
    return [sessions_before(E, k) for k in range(WINDOW + 1, 1, -1)]


def signal(asof: dt.date, panels: dict) -> pd.Series:
    if not is_trading_day(asof):
        raise ValueError(f"{asof} is not a trading day; the engine decides on sessions only")
    if asof in decision_days(asof):
        return pd.Series({SYMBOL: 1.0})
    return pd.Series(dtype=float)
