"""The scheduled run: refresh, decide, build the marks, mark, write the scoreboard.

    SHADOW_STATE_DIR=<dir> QUANTT_ENV_FILE=<key file> python3 -m shadow nightly

WHY ONE COMMAND: the timer on the VM fires it several times an evening and once in the
morning (shadow/deploy/install_shadow_vm.sh). Every step is safe to repeat: a decision is
written once, a stored mark never changes, a scored session is never rescored. So a run
that finds a panel not yet published simply records UNMEASURED and the next run tries
again, and nothing needs to know which run it is.

THE AS-OF DATE is never taken from the clock alone. It is the latest session on the
exchange calendar that has closed: an earlier day, or today from SETTLE (16:30 New
York), which is after the close and its auction prints on a normal day and long after on
an early-close day. Before SETTLE on a session day the as-of date is the previous
session, which is the morning backstop's case.

A FAILED STEP DOES NOT STOP THE OTHERS, and is never silent: a refresh command that
fails is printed with its exit code, and the freshness gate then sees a stale panel and
refuses to decide. The exit code is 0 only if every book decided or already had, every
refresh command succeeded and every held name has its marks; else 3.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from . import engine, marks, scoreboard
from .book import Book

DATA_BOOK = "cef"          # whose key reads the data (team lead, 2026-11-09; sources.py WHICH KEY)
SETTLE = dt.time(16, 30)   # New York: from here a session's close and prints exist
TOL_BP = 25.0              # primary vs check: report beyond this (the mark is never changed)
REFRESH_TIMEOUT_S = 900
HOLD_TAIL_SESSIONS = 2     # a decision's weights are held until its successor fills: successor's as-of + 1; one more for margin
GAP_RETRY_SESSIONS = 3     # a missing print is asked for again on the runs of this many sessions, then left as a logged gap


def asof_session(sessions: list, now: dt.datetime):
    """The latest closed session at `now` (timezone-aware), or None if there is none."""
    ny = now.astimezone(engine.NY)
    closed = [s for s in sorted(sessions)
              if s < ny.date() or (s == ny.date() and ny.time() >= SETTLE)]
    return closed[-1] if closed else None


def _refresh(book: Book, state: Path) -> list:
    """Run the book's refresh commands. Returns [(command, exit code or error)] that failed."""
    failed = []
    env = {**os.environ, "SHADOW_STATE_DIR": str(state)}
    for cmd in book.refresh:
        # A book file writes `python3`; it must mean THIS interpreter. Under systemd the
        # PATH's python3 is the system one, which has none of the packages (the VM's venv
        # is reached only through the unit's SHADOW_PYTHON).
        argv = [sys.executable if cmd[0] == "python3" else cmd[0], *cmd[1:]]
        try:
            r = subprocess.run(argv, cwd=engine.REPO, env=env, timeout=REFRESH_TIMEOUT_S)
            if r.returncode != 0:
                failed.append((" ".join(cmd), r.returncode))
        except (OSError, subprocess.TimeoutExpired) as e:
            failed.append((" ".join(cmd), type(e).__name__))
    return failed


def _needed(state: Path, books: list, sessions: list, asof: dt.date) -> dict:
    """{session: symbols whose mark the stored decisions need on it}.

    WHY PER SYMBOL AND PER SESSION (2026-11-14). The first version asked for every symbol any
    decision had ever named, on every session since the first decision. That is right for a
    fixed universe and wrong for a book whose names change: a company listed yesterday has no
    print last month, so each night re-asked for every past session and logged a gap for
    each. A decision's weights are held from its as-of date until the book's NEXT decision
    fills, so its symbols are needed from its as-of date to HOLD_TAIL_SESSIONS after the next
    decision's as-of date; the book's latest decision is held until replaced, so its symbols
    are needed up to the as-of date of this run."""
    pos = {s: i for i, s in enumerate(sessions)}
    need: dict = {}
    for b in books:
        recs = []
        for p in sorted((state / b.slug / "decisions").glob("*.json")):
            rec = json.loads(p.read_text())
            recs.append((dt.date.fromisoformat(rec["asof"]), set(rec["weights"])))
        recs.sort(key=lambda r: r[0])
        for k, (d, syms) in enumerate(recs):
            if not syms or d not in pos:
                continue
            if k + 1 < len(recs) and recs[k + 1][0] in pos:
                last = min(pos[recs[k + 1][0]] + HOLD_TAIL_SESSIONS, len(sessions) - 1)
            else:
                last = len(sessions) - 1
            for s in sessions[pos[d]:last + 1]:
                if s <= asof:
                    need.setdefault(s, set()).update(syms)
    return need


def _log(path: Path, fields, rows) -> None:
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields))
        if new:
            w.writeheader()
        w.writerows(rows)


def update_marks(state: Path, books: list, src, check, sessions: list, asof: dt.date) -> int:
    """Add the (session, symbol) marks the stored decisions need and the file lacks.
    Returns the number of gaps found on this run (a held name with no primary print)."""
    need = _needed(state, books, sessions, asof)
    if not need:
        return 0
    path = state / "marks.parquet"
    have = set()
    if path.exists():
        old = pd.read_parquet(path, columns=["date", "symbol"])
        have = set(zip(pd.to_datetime(old["date"]).dt.date, old["symbol"]))
    gp = state / "marks_gaps.csv"
    logged = set()
    if gp.exists():
        logged = {(r["date"], r["symbol"]) for r in csv.DictReader(open(gp))}
    closed = [s for s in sessions if s <= asof]
    retry_from = closed[-GAP_RETRY_SESSIONS] if len(closed) >= GAP_RETRY_SESSIONS else closed[0]
    # what to ask for: missing, and either never logged as a gap or recent enough to retry
    ask: dict = {}
    for day, syms in need.items():
        want = frozenset(x for x in syms if (day, x) not in have
                         and ((day.isoformat(), x) not in logged or day >= retry_from))
        if want:
            ask.setdefault(want, []).append(day)
    n_gaps, fresh = 0, []
    for syms, days in sorted(ask.items(), key=lambda kv: min(kv[1])):
        new, bad, gaps = marks.build(sorted(syms), sorted(days), primary=src.prints, check=check,
                                     distributions=src.distributions, tol_bp=TOL_BP,
                                     primary_name="alpaca_auction_M", check_name="yfinance_close")
        marks.append(path, new)
        if len(bad):
            _log(state / "marks_disagreements.csv", list(bad.columns), bad.astype(str).to_dict("records"))
        n_gaps += len(gaps)
        # a gap already logged on an earlier run is not logged twice
        fresh += [{"date": d.isoformat(), "symbol": s} for d, s in gaps if (d.isoformat(), s) not in logged]
    if fresh:
        _log(gp, ("date", "symbol"), fresh)
    return n_gaps


def run(state: Path, books: list, src, *, check, now: dt.datetime | None = None) -> int:
    now = now or dt.datetime.now(dt.timezone.utc)
    enabled = [b for b in books if b.enabled]
    if not enabled:
        print("no enabled book under shadow/books/: nothing to do")
        return 0
    today = now.astimezone(engine.NY).date()
    first = min(b.started for b in books)
    sessions = src.sessions(first - dt.timedelta(days=10), today)
    asof = asof_session(sessions, now)
    if asof is None:
        raise engine.ShadowError(f"the calendar holds no closed session up to {today}")
    rc = 0
    for b in enabled:
        if asof < b.started:
            print(f"{b.slug}: starts {b.started}; as-of {asof} is before it")
            continue
        for cmd, code in _refresh(b, state):
            print(f"{b.slug}: REFRESH FAILED ({code}): {cmd}")
            rc = 3
        try:
            res = engine.decide(b, state, asof, now=now)
        except Exception as e:      # noqa: BLE001 - deliberate, see below
            # ONE BOOK'S BUG MUST NOT STOP THE BOOKS AFTER IT. engine.decide turns a book's own
            # `Unmeasured` into a status, but any other exception from a signal (a KeyError on a
            # panel column, a bad calendar row) used to leave this loop, so every book later in
            # the list got no decision that night and its next session was scored FLAT for
            # nothing it did. Eleven books now share this loop (2026-11-18). This is not a
            # fallback: nothing is decided for the broken book, the line names it and the
            # exception, and the run exits non-zero as it does for UNMEASURED.
            print(f"decide {b.slug} {asof}: ERROR {type(e).__name__}: {e}")
            rc = 3
            continue
        print(f"decide {b.slug} {asof}: {res['status']} {res.get('reason', '')}".rstrip())
        if res["status"] == "UNMEASURED":
            rc = 3
    gaps = update_marks(state, books, src, check, sessions, asof)
    if gaps:
        print(f"marks: {gaps} (session, symbol) pair(s) have no primary print; see marks_gaps.csv")
        rc = 3
    mp = state / "marks.parquet"
    if mp.exists():
        m = pd.read_parquet(mp)
        for b in books:
            rows = engine.mark(b, state, m)
            bad = [r["date"] for r in rows if r["status"] == "UNMEASURED"]
            print(f"mark {b.slug}: {len(rows)} new session(s)" + (f", UNMEASURED on {bad}" if bad else ""))
        late = {b.slug: engine.late_decisions(b, state, sessions) for b in books}
        (state / "SCOREBOARD.md").write_text(scoreboard.render(books, state, late=late, today=asof))
    return rc
