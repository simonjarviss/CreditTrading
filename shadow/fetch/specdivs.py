"""Special dividends for the shadow book: the feed's rows by the day we first saw them, and
prices for the companies paying them.

    SHADOW_STATE_DIR=<dir> QUANTT_ENV_FILE=<key file> python3 -m shadow.fetch.specdivs

WHY (results/ideas/2026-11-15_special_dividends.md). A common stock with a special cash
dividend of 1% or more gained about 1.2% against small companies between the session after
the announcement and the close before the ex-date, 2000-2025. The shadow book holds that
wait. The research knew each declaration date; a live book knows only the day a feed first
lists the dividend, and nobody has measured how long Alpaca takes. So, as with ex-dates and
spin-offs, every row is stored with the day this fetch first returned it and the book reads
only rows it had seen by the decision date. A row that arrives late shortens the trade, and
the gap between `first_seen` and the ex-date is the measurement the research could not make.

Writes under <state>/panels/:
  specdivs.parquet       [first_seen, first_run, id, symbol, ex_date, amount, process_date,
                          name, exchange]; rows are only ever added. `first_run` is True for
                          rows stored by the very first fetch: those were already listed
                          when the reader started, so their first_seen says nothing about
                          the feed's lag. `name` and `exchange` are Alpaca's asset record
                          when first seen ('' when Alpaca does not list the symbol).
  specdivs_seen.parquet  [date]: the heartbeat, one row per as-of session a fetch succeeded.
  specdivs_px.parquet    [date, symbol, close, volume] from Yahoo for IWM (the hedge) and
                          every symbol whose ex-date is not more than PX_PAST_DAYS behind.
                          Refetched whole each night.
The feed's window filters on process date (the pay date), which can be weeks after the
ex-date, so the request spans BACK_DAYS behind and AHEAD_DAYS in front of today.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

import pandas as pd

from . import common, yf_px

BACK_DAYS, AHEAD_DAYS, PX_PAST_DAYS, PX_DAYS = 10, 150, 10, 90
HEDGE = "IWM"
COLS = ["first_seen", "first_run", "id", "symbol", "ex_date", "amount", "process_date", "name", "exchange"]


def merge(old: pd.DataFrame | None, rows: list, today: dt.date, describe) -> pd.DataFrame:
    """Add rows not already stored with the same id, symbol, ex-date and amount. An old row is
    never changed: a corrected row is a new row with its own first_seen."""
    key = lambda r: (r["id"], r["symbol"], pd.Timestamp(r["ex_date"]), round(float(r["amount"]), 6))  # noqa: E731
    first_run = old is None
    seen = set() if old is None or old.empty else {key(r) for r in old.to_dict("records")}
    add = []
    for r in rows:
        if key(r) in seen:
            continue
        seen.add(key(r))
        info = describe(r["symbol"]) or {}
        add.append({"first_seen": pd.Timestamp(today), "first_run": first_run, "id": r["id"], "symbol": r["symbol"],
                    "ex_date": pd.Timestamp(r["ex_date"]), "amount": float(r["amount"]),
                    "process_date": pd.Timestamp(r["process_date"]), "name": info.get("name", ""),
                    "exchange": info.get("exchange", "")})
    new = pd.DataFrame(add, columns=COLS)
    if old is None or old.empty:
        return new
    return old[COLS].copy() if new.empty else pd.concat([old[COLS], new], ignore_index=True)


def live_symbols(panel: pd.DataFrame, today: dt.date) -> list:
    """Symbols whose ex-date is ahead, or not more than PX_PAST_DAYS behind."""
    if panel.empty:
        return []
    ex = pd.to_datetime(panel["ex_date"]).dt.date
    return sorted(set(panel.loc[ex >= today - dt.timedelta(days=PX_PAST_DAYS), "symbol"]) - {HEDGE})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="cef", help="whose key reads the feed (shadow/sources.py WHICH KEY)")
    a = ap.parse_args(argv)
    from .. import sources
    today = dt.datetime.now(common.NY).date()
    src = sources.ReadOnlyData(a.book)
    rows, bad = src.special_dividends(today - dt.timedelta(days=BACK_DAYS), today + dt.timedelta(days=AHEAD_DAYS))
    d = common.panels_dir()
    p = d / "specdivs.parquet"
    old = pd.read_parquet(p) if p.exists() else None
    out = merge(old, rows, today, src.asset_flags)
    common.write(out, p.name)
    n_new = len(out) - (0 if old is None else len(old))

    syms = live_symbols(out, today)
    last = common.last_closed_date()
    px = yf_px.fetch([HEDGE] + syms, PX_DAYS, last)
    if HEDGE not in set(px["symbol"]):
        raise RuntimeError(f"Yahoo returned no rows for {HEDGE}; the book cannot be hedged or dated")
    common.write(px, "specdivs_px.parquet")
    no_px = sorted(set(syms) - set(px["symbol"]))

    # the heartbeat goes last: it says every step above succeeded for this as-of session
    hp = d / "specdivs_seen.parquet"
    stamp = pd.Timestamp(last)
    seen = pd.read_parquet(hp) if hp.exists() else pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]")})
    if stamp not in set(seen["date"]):
        seen = pd.concat([seen, pd.DataFrame({"date": [stamp]})], ignore_index=True)
    common.write(seen, hp.name)
    fut = out[pd.to_datetime(out["ex_date"]).dt.date > today]
    print(f"specdivs.parquet: {len(out):,} rows ({n_new} new, {bad} unreadable left out); {len(fut)} with a future ex-date; "
          f"prices for {px['symbol'].nunique() - 1} of {len(syms)} live symbols" + (f", none for {no_px}" if no_px else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
