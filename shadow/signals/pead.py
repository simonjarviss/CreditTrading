"""Earnings drift in smaller stocks: hold the biggest positive surprises for 40 sessions.

THE IDEA (results/ideas/2026-11-15_pead_small.md). Among US stocks ranked 1,501 to 4,000 by
size, priced $5 or more and trading $500,000 a day, the tenth with the largest positive
earnings surprise kept rising for 40 sessions after the release, 2000-2025. Long that tenth
against IWM: gross Sharpe 1.27 on the licensed surprise score; 0.68 on the plain surprise a
free feed can give, with every release taken as known one session after its date. THIS
BOOK IS THE 0.68 VERSION, on Yahoo's figures (shadow/fetch/earnings.py says how close those
are to the licensed ones). Long side only: the short side earned 0.33 and needs borrow.

THE BOOK, `small_long`
  LONG the top tenth by surprise among stocks with a live signal, equally weighted, 100% of
  the book in total; SHORT IWM 100%. Flat when fewer than MIN_NAMES stocks have a live
  signal (the research's rule), so the first weeks of a quarter can be empty.

THE SURPRISE is (reported - forecast) / |forecast|, only when |forecast| is at least $0.05
a share: a forecast near zero makes the ratio meaningless.

WHICH DECISIONS HOLD A SIGNAL. A release dated E (Yahoo's calendar day, which does not say
reliably whether it was before the open or after the close) is taken as known at T, the
first session strictly after E. Its signal is live on the 40 decision sessions T .. T+39,
as in the research (`ffill(limit=39)` from T). The engine fills a decision at the next
close, so the first return earned is session T+2's: the announcement's own move is never
earned. The event panel is point-in-time by `first_seen`: a result Yahoo showed late is a
shorter trade, never hindsight. A stock with two releases in the window carries the later.

ELIGIBLE on the decision date D, as the research judged it on its decision row: a close on
D of $5 or more and a 21-session average dollar volume of $500,000 or more (at least 10
sessions of history). The size limit and the company filter are applied at fetch. Symbols
in the desk's closed-end fund and unit universes are left to their own books.

CAPACITY, from the card: at $1M the median position was 0.14% of a day's volume.
"""
from __future__ import annotations

import csv
import datetime as dt
import math
from pathlib import Path

import pandas as pd

from ops.schedule.nyse_calendar import next_trading_day

HEDGE = "IWM"
HOLD, TAIL, MIN_NAMES = 40, 0.10, 50
MIN_PRICE, MIN_ADV, ADV_WINDOW, MIN_ADV_DAYS, MIN_ABS_FORECAST = 5.0, 500_000.0, 21, 10, 0.05
PX, EVENTS = "px", "earnings"
OTHER_UNIVERSES = ("cef_v1", "units_v1")


def _other_books() -> frozenset:
    out = set()
    for u in OTHER_UNIVERSES:
        with open(Path(__file__).resolve().parents[1] / "universes" / f"{u}.csv") as f:
            out |= {r["symbol"] for r in csv.DictReader(f)}
    return frozenset(out)


def known_session(day: dt.date) -> dt.date:
    """T: the first session strictly after the release's calendar day."""
    return next_trading_day(day)


def live(day: dt.date, asof: dt.date) -> bool:
    """True when `asof` is one of the 40 sessions T .. T+39."""
    t = known_session(day)
    if asof < t:
        return False
    d = t
    for _ in range(HOLD - 1):
        if d >= asof:
            break
        d = next_trading_day(d)
    return d >= asof


def surprises(events: pd.DataFrame, asof: dt.date) -> dict:
    """{symbol: surprise} for the releases whose signal is live at `asof`; the later release
    wins when a symbol has two."""
    skip = _other_books()
    best: dict = {}
    for r in events.to_dict("records"):
        sym, day = r["symbol"], pd.Timestamp(r["day"]).date()
        est, rep = float(r["eps_estimate"]), float(r["reported_eps"])
        if sym == HEDGE or sym in skip or not math.isfinite(est) or not math.isfinite(rep) or abs(est) < MIN_ABS_FORECAST:
            continue
        if not live(day, asof):
            continue
        if sym not in best or day > best[sym][0]:
            best[sym] = (day, (rep - est) / abs(est))
    return {s: v for s, (_, v) in best.items()}


def small_long(asof: dt.date, panels: dict) -> pd.Series:
    px = panels[PX].copy()
    px["date"] = pd.to_datetime(px["date"]).dt.date
    px = px[px["date"] <= asof].dropna(subset=["close"]).sort_values("date")
    hedge = px[px["symbol"] == HEDGE]
    if hedge.empty or hedge["date"].iloc[-1] != asof:
        return pd.Series(dtype=float)                        # no hedge price today: hold nothing
    sig = surprises(panels[EVENTS], asof)
    ok = {}
    for sym, g in px[px["symbol"].isin(sig)].groupby("symbol"):
        if g["date"].iloc[-1] != asof:
            continue                                          # it did not print today
        tail = g.tail(ADV_WINDOW)
        dv = (tail["close"] * tail["volume"]).dropna()
        if len(dv) >= MIN_ADV_DAYS and tail["close"].iloc[-1] >= MIN_PRICE and dv.mean() >= MIN_ADV:
            ok[sym] = sig[sym]
    if len(ok) < MIN_NAMES:
        return pd.Series(dtype=float)
    s = pd.Series(ok).sort_index()
    top = s[s.rank(pct=True) > 1 - TAIL]                      # the research's rule: pct rank above 0.9
    if top.empty:
        return pd.Series(dtype=float)
    w = {sym: 1.0 / len(top) for sym in top.index}
    w[HEDGE] = -1.0
    return pd.Series(w)
