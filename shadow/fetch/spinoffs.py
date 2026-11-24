"""Spin-offs for the shadow book: the feed's rows by the day we first saw them, prices for the
new shares, and what the broker said about borrowing them.

    SHADOW_STATE_DIR=<dir> QUANTT_ENV_FILE=<key file> python3 -m shadow.fetch.spinoffs

WHY (results/ideas/2026-11-12_spinoffs.md). A newly spun-off company fell about 2.5% against
small companies over its third to fifth sessions, 2000-2025. The shadow book shorts that
window. To do it without hindsight it must know, on the evening of a share's first session,
that the share is a spin-off. Alpaca's feed is the only free source this desk reads, and
nobody has measured WHEN a spin-off row appears in it: on 2026-11-14 it listed 215 rows back
to 2023 and none dated in the future. So, as with ex-dates (shadow/fetch/exdates.py), every
row is stored with the day this fetch first returned it, and the book reads only rows it had
seen by the decision date. A row that arrives late is a missed event, which the scoreboard
then shows; that measurement is half the point of running the book.

Writes under <state>/panels/:
  spinoffs.parquet         [first_seen, id, source_symbol, new_symbol, ex_date, process_date,
                            name, exchange]; rows are only ever added. `name` and `exchange`
                            are Alpaca's asset record for the new symbol when first seen
                            ('' when Alpaca does not list it yet).
  spinoffs_seen.parquet    [date]: the heartbeat, one row per as-of session a fetch succeeded.
  spinoffs_px.parquet      [date, symbol, close, volume] from Yahoo for IWM (the hedge) and
                            every new symbol whose ex-date is in the last PX_EVENT_DAYS days.
                            Refetched whole each night.
  spinoffs_borrow.parquet  [date, symbol, tradable, shortable, borrow_status]: one row per
                            night for each new symbol in its first BORROW_DAYS days. The
                            research could not say whether a share can be borrowed on its
                            second day; this records what the broker reports, which is not
                            the same as a locate and is kept for that reason only.
The feed's window filters on process date, so the request spans BACK_DAYS behind and
AHEAD_DAYS in front of today.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

import pandas as pd

from . import common, yf_px

BACK_DAYS, AHEAD_DAYS, PX_EVENT_DAYS, PX_DAYS, BORROW_DAYS = 30, 90, 45, 90, 12
HEDGE = "IWM"
COLS = ["first_seen", "id", "source_symbol", "new_symbol", "ex_date", "process_date", "name", "exchange"]


def merge(old: pd.DataFrame | None, rows: list, today: dt.date, describe) -> pd.DataFrame:
    """Add rows not already stored under the same id with the same symbols and ex-date. An old
    row is never changed: a corrected row is a new row with its own first_seen."""
    key = lambda r: (r["id"], r["source_symbol"], r["new_symbol"], pd.Timestamp(r["ex_date"]))  # noqa: E731
    seen = set() if old is None or old.empty else {key(r) for r in old.to_dict("records")}
    add = []
    for r in rows:
        if key(r) in seen:
            continue
        seen.add(key(r))
        info = describe(r["new_symbol"]) or {}
        add.append({"first_seen": pd.Timestamp(today), "id": r["id"], "source_symbol": r["source_symbol"],
                    "new_symbol": r["new_symbol"], "ex_date": pd.Timestamp(r["ex_date"]),
                    "process_date": pd.Timestamp(r["process_date"]), "name": info.get("name", ""),
                    "exchange": info.get("exchange", "")})
    new = pd.DataFrame(add, columns=COLS)
    if old is None or old.empty:
        return new
    return old[COLS].copy() if new.empty else pd.concat([old[COLS], new], ignore_index=True)


def recent_symbols(panel: pd.DataFrame, today: dt.date, days: int) -> list:
    if panel.empty:
        return []
    ex = pd.to_datetime(panel["ex_date"]).dt.date
    keep = panel[(ex >= today - dt.timedelta(days=days)) & (ex <= today + dt.timedelta(days=5))
                 & (panel["new_symbol"] != panel["source_symbol"])]
    return sorted(set(keep["new_symbol"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="cef", help="whose key reads the feed (shadow/sources.py WHICH KEY)")
    a = ap.parse_args(argv)
    from .. import sources
    today = dt.datetime.now(common.NY).date()
    src = sources.ReadOnlyData(a.book)
    rows, bad = src.spin_offs(today - dt.timedelta(days=BACK_DAYS), today + dt.timedelta(days=AHEAD_DAYS))
    d = common.panels_dir()
    p = d / "spinoffs.parquet"
    old = pd.read_parquet(p) if p.exists() else None
    out = merge(old, rows, today, src.asset_flags)
    common.write(out, p.name)
    n_new = len(out) - (0 if old is None else len(old))

    # prices: the hedge always, so the price panel has a row on every session; new shares where Yahoo has them
    syms = recent_symbols(out, today, PX_EVENT_DAYS)
    last = common.last_closed_date()
    px = yf_px.fetch([HEDGE] + syms, PX_DAYS, last)
    if HEDGE not in set(px["symbol"]):
        raise RuntimeError(f"Yahoo returned no rows for {HEDGE}; the book cannot be hedged or dated")
    common.write(px, "spinoffs_px.parquet")
    no_px = sorted(set(syms) - set(px["symbol"]))

    # what the broker says about borrowing each very new share, tonight
    young = recent_symbols(out, today, BORROW_DAYS)
    bp = d / "spinoffs_borrow.parquet"
    b_old = pd.read_parquet(bp) if bp.exists() else pd.DataFrame(columns=["date", "symbol", "tradable", "shortable", "borrow_status"])
    stamp = pd.Timestamp(last)
    b_new = []
    for s in young:
        if ((b_old["date"] == stamp) & (b_old["symbol"] == s)).any():
            continue
        f = src.asset_flags(s)
        b_new.append({"date": stamp, "symbol": s, "tradable": bool(f["tradable"]) if f else False,
                      "shortable": bool(f["shortable"]) if f else False,
                      "borrow_status": (f.get("borrow_status") or "") if f else "not_listed"})
    if b_new:
        b_old = pd.DataFrame(b_new) if b_old.empty else pd.concat([b_old, pd.DataFrame(b_new)], ignore_index=True)
    common.write(b_old, bp.name)

    # the heartbeat goes last: it says every step above succeeded for this as-of session
    hp = d / "spinoffs_seen.parquet"
    seen = pd.read_parquet(hp) if hp.exists() else pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]")})
    if stamp not in set(seen["date"]):
        seen = pd.concat([seen, pd.DataFrame({"date": [stamp]})], ignore_index=True)
    common.write(seen, hp.name)
    fut = out[pd.to_datetime(out["ex_date"]).dt.date > today]
    print(f"spinoffs.parquet: {len(out):,} rows ({n_new} new, {bad} unreadable left out); {len(fut)} with a future ex-date; "
          f"prices for {px['symbol'].nunique() - 1} of {len(syms)} recent new symbols"
          + (f", none for {no_px}" if no_px else "") + f"; borrow rows added {len(b_new)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
