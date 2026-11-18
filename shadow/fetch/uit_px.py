"""Nightly closes and volumes for the funds a unit trust is about to stop selling.

    SHADOW_STATE_DIR=<dir> python3 -m shadow.fetch.uit_px

Writes <state>/panels/uit_terminations_v1_px.parquet: [date, symbol, close, volume] from Yahoo,
unadjusted, the same reader and the same rules as shadow/fetch/yf_px.py.

WHY ITS OWN FETCHER. `yf_px` reads a universe file with one row per symbol. The termination
calendar (shadow/universes/uit_terminations_v1.csv) has one row per trust and fund, about
three hundred funds in all, and on any night the book needs only the few dozen near a
termination date. So this asks for the funds whose termination session is from BACK_DAYS
behind to AHEAD_DAYS ahead: far enough ahead that a fund has its 21-session volume and its
T-10 close in the panel before it is first judged (shadow/signals/uit_termination.py), far
enough behind that a held fund stays in the panel until its exit at T+3.

WHEN NO DATE IS NEAR. The book requires this panel at the as-of date, so an empty panel would
read as a failed fetch every night of a quiet month. The funds of the NEXT termination date
are fetched instead: they are the ones the book will judge next. When the calendar holds no
future date at all this raises: the calendar is exhausted and must be rebuilt
(shadow/universes/README.md), and a book quietly holding nothing for want of a calendar is
the failure this desk does not allow.

No key and no contact header: Yahoo only. The calendar itself is never fetched from here.
"""
from __future__ import annotations

import datetime as dt
import sys

from ..signals import uit_termination as sig
from . import common, yf_px

BACK_DAYS, AHEAD_DAYS, PX_DAYS = 10, 45, 120
PANEL = "uit_terminations_v1_px.parquet"


def symbols_needed(calendar: list, today: dt.date) -> list:
    """Funds with a termination session in [today - BACK_DAYS, today + AHEAD_DAYS]; if none,
    the funds of the next one. Raises when no termination session is on or after today - BACK_DAYS."""
    by_t: dict = {}
    for r in calendar:
        by_t.setdefault(sig.termination_session(r["termination"]), set()).add(r["symbol"])
    lo, hi = today - dt.timedelta(days=BACK_DAYS), today + dt.timedelta(days=AHEAD_DAYS)
    near = set().union(*[s for t, s in by_t.items() if lo <= t <= hi]) if by_t else set()
    if near:
        return sorted(near)
    ahead = sorted(t for t in by_t if t > hi)
    if not ahead:
        raise RuntimeError(f"the termination calendar holds no date after {lo}: rebuild it "
                           "(python3 -m shadow.universes.build_uit_terminations_v1)")
    return sorted(by_t[ahead[0]])


def main(argv=None) -> int:
    last = common.last_closed_date()
    syms = symbols_needed(sig.read_calendar(sig._csv(sig.CALENDAR)), last)
    df = yf_px.fetch(syms, PX_DAYS, last)
    missing = sorted(set(syms) - set(df["symbol"]))
    path = common.write(df, PANEL)
    print(f"{path.name}: {len(df):,} rows, {df['date'].min().date()} .. {df['date'].max().date()}, "
          f"{df['symbol'].nunique()} of {len(syms)} funds" + (f"; none for {missing}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
