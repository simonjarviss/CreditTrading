"""Declared ex-dates for a shadow universe, kept point-in-time by the day we first saw them.

    SHADOW_STATE_DIR=<dir> QUANTT_ENV_FILE=<key file> python3 -m shadow.fetch.exdates cef_v1

WHY "FIRST SEEN" IS THE DATE COLUMN. A signal that trades around an ex-date needs to know it
BEFORE it happens, and the only honest record of when we knew is the day our own fetch first
returned it. So each row carries `first_seen`, and the book names that as the panel's date
column: the engine removes every row with first_seen after the as-of date, which makes it
impossible for a decision to use an ex-date this desk had not yet been told. A history
backfilled from any source would not have that property.

Writes two panels under <state>/panels/:
  <universe>_exdates.parquet       [first_seen, symbol, ex_date, amount]; rows are only ever
                                   added. A changed amount for a known (symbol, ex_date) adds a
                                   new row with its own first_seen; the signal uses the dates.
  <universe>_exdates_seen.parquet  [date]: one row per day this fetch succeeded. The book
                                   requires it at the as-of date, so a night the feed could not
                                   be read is a night the book does not decide.

Source: Alpaca's corporate-actions feed through the read-only facade (shadow/sources.py).
Alpaca says an action "may not be available immediately after" it is announced, so a late
row is a missed event, counted by the scoreboard's unmeasured days, never guessed.
Measured 2026-11-10: of 30 funds asked, 28 had a future ex-date listed, 2 to 28 days ahead.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

import pandas as pd

from . import common

BACK_DAYS, AHEAD_DAYS = 10, 60


def merge(old: pd.DataFrame | None, events: list, today: dt.date) -> pd.DataFrame:
    """Add events not already recorded with the same amount. Never changes an old row."""
    cols = ["first_seen", "symbol", "ex_date", "amount"]
    new = pd.DataFrame([{"first_seen": pd.Timestamp(today), "symbol": e["symbol"],
                         "ex_date": pd.Timestamp(e["ex_date"]), "amount": float(e["amount"])} for e in events],
                       columns=cols)
    if old is None or old.empty:
        return new.drop_duplicates(["symbol", "ex_date", "amount"]).reset_index(drop=True)
    seen = set(zip(old["symbol"], pd.to_datetime(old["ex_date"]), old["amount"].round(6)))
    add = new[[k not in seen for k in zip(new["symbol"], new["ex_date"], new["amount"].round(6))]]
    add = add.drop_duplicates(["symbol", "ex_date", "amount"])
    return pd.concat([old[cols], add], ignore_index=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("universe")
    ap.add_argument("--book", default="cef", help="whose key reads the feed (shadow/sources.py WHICH KEY)")
    a = ap.parse_args(argv)
    from .. import sources
    syms = common.universe(a.universe)
    today = dt.datetime.now(common.NY).date()
    src = sources.ReadOnlyData(a.book)
    events = src.distributions(syms, today - dt.timedelta(days=BACK_DAYS), today + dt.timedelta(days=AHEAD_DAYS))
    d = common.panels_dir()
    p = d / f"{a.universe}_exdates.parquet"
    old = pd.read_parquet(p) if p.exists() else None
    out = merge(old, events, today)
    common.write(out, p.name)
    hp = d / f"{a.universe}_exdates_seen.parquet"
    seen = pd.read_parquet(hp) if hp.exists() else pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]")})
    # the heartbeat is dated by the last CLOSED session's date, which is the as-of date the
    # nightly run decides for: an evening fetch and the morning backstop both satisfy it
    stamp = pd.Timestamp(common.last_closed_date())
    if stamp not in set(seen["date"]):
        seen = pd.concat([seen, pd.DataFrame({"date": [stamp]})], ignore_index=True)
    common.write(seen, hp.name)
    fut = out[out["ex_date"] > pd.Timestamp(today)]
    print(f"{p.name}: {len(out):,} rows ({len(out) - (0 if old is None else len(old))} new); "
          f"{fut['symbol'].nunique()} of {len(syms)} funds have a future ex-date listed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
