"""python3 -m shadow {decide,mark,scoreboard,run}  — see shadow/__init__.py and engine.py.

    SHADOW_STATE_DIR=<dir> python3 -m shadow run [--asof YYYY-MM-DD]

`run` decides every enabled book for the as-of date, marks every book on
<state>/marks.parquet, and prints the scoreboard. It refreshes nothing: fetching the
panels and the marks is a separate step with its own fetchers, so that a failed fetch
is a stale panel the freshness gate sees, never a half-written one.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

from . import book as book_mod
from . import engine, scoreboard

BOOKS_DIR = Path(__file__).resolve().parent / "books"


def _marks(state: Path) -> pd.DataFrame:
    p = state / "marks.parquet"
    if not p.exists():
        raise engine.ShadowError(f"{p} does not exist: build the marks before marking")
    return pd.read_parquet(p)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m shadow")
    ap.add_argument("cmd", choices=("decide", "mark", "scoreboard", "run", "nightly"))
    ap.add_argument("--asof", type=dt.date.fromisoformat,
                    help="the decision date (required for decide and run: never guessed from the clock)")
    ap.add_argument("--out", type=Path, help="scoreboard: also write the page here")
    a = ap.parse_args(argv)
    state = engine.state_dir()
    books = book_mod.load_all(BOOKS_DIR)
    if a.cmd == "nightly":
        # the scheduled entry point: refresh, decide, build marks, mark, scoreboard
        from . import nightly, sources
        return nightly.run(state, books, sources.ReadOnlyData(nightly.DATA_BOOK),
                           check=sources.yfinance_closes)
    if not books:
        print("no book files under shadow/books/: nothing to do")
        return 0
    rc = 0
    if a.cmd in ("decide", "run"):
        if a.asof is None:
            ap.error("--asof is required")
        for b in (b for b in books if b.enabled):
            res = engine.decide(b, state, a.asof)
            print(f"decide {b.slug} {a.asof}: {res['status']} {res.get('reason', '')}".rstrip())
            rc = max(rc, 3 if res["status"] == "UNMEASURED" else 0)
    if a.cmd in ("mark", "run", "scoreboard"):
        marks = _marks(state)
        sessions = sorted(set(pd.to_datetime(marks["date"]).dt.date))
        if a.cmd != "scoreboard":
            for b in books:
                rows = engine.mark(b, state, marks)
                bad = [r["date"] for r in rows if r["status"] == "UNMEASURED"]
                print(f"mark {b.slug}: {len(rows)} new session(s)" + (f", UNMEASURED on {bad}" if bad else ""))
        late = {b.slug: engine.late_decisions(b, state, sessions) for b in books}
        page = scoreboard.render(books, state, late=late, today=sessions[-1] if sessions else a.asof)
        print(page)
        if a.out:
            a.out.write_text(page)
    return rc


if __name__ == "__main__":
    sys.exit(main())
