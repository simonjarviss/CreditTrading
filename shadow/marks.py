"""Build the marks a shadow book is scored on: the official close, and a second source.

THE TEAM LEAD'S CHOICE (2026-11-09, docs/SYSTEM.md section 5): Alpaca's closing-auction
print is the mark, and yfinance's close is the cross-check. Why the print: it is the
price an MOC order fills at, and it is what prod's own score uses
(`quantt/session/score.py`). Why a check: a single source's bad bar becomes P&L with
nothing to contradict it.

THE RULES
---------
  * **The primary is the mark. The check never replaces it.** Where the two differ by
    more than `tol_bp`, the row keeps the primary's price and the difference is returned
    for the report (CLAUDE.md: never average two sources, never pick one silently).
  * **A symbol with no primary print has no row.** The engine then scores a book holding
    it as UNMEASURED for that session, naming it. The check's close is not used as a
    mark: on a day the primary exchange ran no auction, another close is a different
    price from the one the fill convention assumes.
  * **Distributions** come from the same broker feed, by ex-date. Its own documentation
    says an event may be missing or late, so the total-return line is only as complete
    as that feed; `dividend_source` on every row says where the amount came from.
  * **Splits are not handled here yet.** The engine refuses a one-session move beyond its
    guard rather than book it, so a split shows as UNMEASURED until a split source is
    added. That is the safe direction.

This module holds no network code of its own. `primary`, `check` and `distributions` are
callables the caller passes in, so the tests run on literals and the two real sources
live in `sources.py`, behind a facade that exposes read-only calls only.
"""
from __future__ import annotations

import datetime as dt
from typing import Callable, Iterable

import pandas as pd

COLUMNS = ["date", "symbol", "close", "dividend", "source", "dividend_source"]


def build(symbols: Iterable[str], sessions: Iterable[dt.date], *,
          primary: Callable[[list, dt.date], dict],
          check: Callable[[list, dt.date, dt.date], pd.DataFrame],
          distributions: Callable[[list, dt.date, dt.date], list],
          tol_bp: float, primary_name: str, check_name: str) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """Returns (marks, disagreements, gaps).

    primary(symbols, day) -> {symbol: price} for the symbols that HAVE a print that day.
    check(symbols, first, last) -> DataFrame[date, symbol, close].
    distributions(symbols, first, last) -> [{"symbol", "ex_date": date, "amount": float}, ...].
    gaps: [(day, symbol)] with no primary print.
    """
    syms = sorted(set(symbols))
    days = sorted(set(sessions))
    if not syms or not days:
        raise ValueError("build needs at least one symbol and one session")
    if tol_bp <= 0:
        raise ValueError("tol_bp must be positive")
    rows, gaps = [], []
    for day in days:
        got = primary(syms, day)
        for s in syms:
            if s not in got:
                gaps.append((day, s))
                continue
            px = float(got[s])
            if not px > 0:
                raise ValueError(f"{primary_name}: {s} on {day} has a non-positive print {px}")
            rows.append({"date": day, "symbol": s, "close": px})
    marks = pd.DataFrame(rows, columns=["date", "symbol", "close"])

    divs = {}
    for ev in distributions(syms, days[0], days[-1]):
        key = (ev["ex_date"], ev["symbol"])
        divs[key] = divs.get(key, 0.0) + float(ev["amount"])     # two events on one ex-date add
    marks["dividend"] = [divs.get((d, s), 0.0) for d, s in zip(marks["date"], marks["symbol"])]
    marks["source"] = primary_name
    marks["dividend_source"] = primary_name

    chk = check(syms, days[0], days[-1]).copy()
    chk["date"] = pd.to_datetime(chk["date"]).dt.date
    both = marks.merge(chk[["date", "symbol", "close"]], on=["date", "symbol"], how="left",
                       suffixes=("", "_check"))
    both["diff_bp"] = (both["close_check"] / both["close"] - 1.0) * 1e4
    bad = both[both["close_check"].isna() | (both["diff_bp"].abs() > tol_bp)].copy()
    bad["check"] = check_name
    return marks[COLUMNS], bad[["date", "symbol", "close", "close_check", "diff_bp", "check"]], gaps


def append(path, new: pd.DataFrame) -> pd.DataFrame:
    """Add sessions to a marks file. A (date, symbol) already stored is never changed: if
    the new value differs, raise, naming it. A mark that a book was already scored on must
    not move underneath the score."""
    from pathlib import Path
    path = Path(path)
    if not path.exists():
        new.to_parquet(path, index=False)
        return new
    old = pd.read_parquet(path)
    old["date"] = pd.to_datetime(old["date"]).dt.date
    m = old.merge(new, on=["date", "symbol"], how="inner", suffixes=("_old", "_new"))
    moved = m[(m["close_old"] - m["close_new"]).abs() > 1e-9]
    if len(moved):
        first = moved.iloc[0]
        raise ValueError(f"{len(moved)} stored mark(s) would change, e.g. {first['symbol']} on {first['date']}: "
                         f"{first['close_old']} -> {first['close_new']}; a stored mark is never rewritten")
    keys = set(zip(old["date"], old["symbol"]))
    add = new[[k not in keys for k in zip(new["date"], new["symbol"])]]
    out = pd.concat([old, add], ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
    out.to_parquet(path, index=False)
    return out
