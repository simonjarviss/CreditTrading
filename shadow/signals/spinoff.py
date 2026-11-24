"""The first week of a spin-off: one shadow book.

THE IDEA (results/ideas/2026-11-12_spinoffs.md). Holders of a parent company are handed
shares in a company they did not choose, and many sell at once. Across 387 new spin-offs on
CRSP, 2000-2025, the new share fell in each of its sessions 2 to 6 and other new listings
did not. On the 336 a book could trade it fell 2.45% against IWM over sessions 3 to 5.
Gross; no borrow modelled; the window was read from the data, so it is not pre-specified.

THE BOOK. SHORT each new spin-off for 10% of the book over its life sessions 3, 4 and 5,
LONG IWM for the same amount; at most 50% a side. Life session 1 is the share's first
session with a close ON OR AFTER its ex-date: its first regular-way session, which is what
CRSP's first row was in the research. Yahoo also carries when-issued closes from a few days
before (MSGR, ex-date 2026-10-27, has closes from 2026-10-21 on thin volume); those are not
regular-way trading and are ignored.

WHICH DECISIONS HOLD IT. The engine fills a decision at the next close and the book earns
the session after: a weight decided at D earns session D+2. So the share is held on the
decisions of its life sessions 1, 2 and 3 (earning 3, 4, 5) and on no other.

WHAT A DECISION AT D MAY READ
  the feed      a spin-off row for the symbol that this desk had SEEN by D. The spin-off
                panel is dated by `first_seen` (shadow/fetch/spinoffs.py) and the engine has
                already removed later rows, so a row the feed published late is a shorter
                trade or a missed one, never hindsight.
  it is new     the symbol has no close more than NEW_WINDOW_DAYS before the row's ex-date
                (a share that already traded does, and is a different event), and its first
                close on or after the ex-date comes within NEW_WINDOW_DAYS of it.
  it is a share Alpaca's name for it, stored when the row was first seen, does not say
                warrant, right, unit, preferred, note or contingent value; and its exchange
                is one this desk can read a closing print for (the marks need it).
  eligible      judged on life session 1 only, as in the research: a close of $5 or more and
                $1M or more traded that day.
The price panel must end on D (the book file requires it), so a night Yahoo is behind is a
night the book does not decide.
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd

HEDGE = "IWM"
SIZE, CAP, HOLD_SESSIONS = 0.10, 0.50, (1, 2, 3)
MIN_PRICE, MIN_DOLLAR_VOLUME, NEW_WINDOW_DAYS = 5.0, 1_000_000.0, 10
MARKABLE_EXCHANGES = frozenset({"NYSE", "NASDAQ", "AMEX", "ARCA"})      # shadow/sources.py can map these to a closing print
NOT_A_SHARE = re.compile(r"warrant|\brights?\b|\bunits?\b|preferred|\bnotes?\b|contingent|\bcvr\b|depositary", re.I)
PX, EVENTS = "px", "spinoffs"


def candidates(events: pd.DataFrame) -> dict:
    """{new symbol: [ex-dates]} for rows that can be a tradable new common share."""
    out: dict = {}
    for r in events.to_dict("records"):
        if r["new_symbol"] == r["source_symbol"] or r["new_symbol"] == HEDGE:
            continue
        if r["exchange"] not in MARKABLE_EXCHANGES or NOT_A_SHARE.search(r["name"] or ""):
            continue
        out.setdefault(r["new_symbol"], []).append(pd.Timestamp(r["ex_date"]).date())
    return out


def first_week(asof: dt.date, panels: dict) -> pd.Series:
    px = panels[PX].copy()
    px["date"] = pd.to_datetime(px["date"]).dt.date
    px = px[px["date"] <= asof].dropna(subset=["close"]).sort_values("date")
    hedge = px[px["symbol"] == HEDGE]
    if hedge.empty or hedge["date"].iloc[-1] != asof:
        return pd.Series(dtype=float)                       # no hedge price today: hold nothing
    sessions = list(hedge["date"])                           # the hedge trades every session: it is the calendar
    shorts = []
    for sym, ex_dates in sorted(candidates(panels[EVENTS]).items()):
        g = px[px["symbol"] == sym]
        if g.empty or g["date"].iloc[-1] != asof:
            continue                                         # it did not print today: not traded tomorrow on an old price
        for x in sorted(set(ex_dates)):
            if (x - g["date"].iloc[0]).days > NEW_WINDOW_DAYS:
                continue                                     # it traded long before this ex-date: not new
            reg = g[g["date"] >= x]                          # regular-way closes; earlier ones are when-issued
            if reg.empty or (reg["date"].iloc[0] - x).days > NEW_WINDOW_DAYS:
                continue
            day1 = reg["date"].iloc[0]
            if day1 not in sessions:
                continue
            life = sessions.index(asof) - sessions.index(day1) + 1
            if life not in HOLD_SESSIONS or len(reg) != life:
                continue                                     # outside its window, or a session with no close inside it
            first = reg.iloc[0]
            vol = first["volume"]
            if first["close"] >= MIN_PRICE and pd.notna(vol) and first["close"] * vol >= MIN_DOLLAR_VOLUME:
                shorts.append(sym)
                break
    if not shorts:
        return pd.Series(dtype=float)
    size = min(SIZE, CAP / len(shorts))
    w = {s: -size for s in shorts}
    w[HEDGE] = size * len(shorts)
    return pd.Series(w)
