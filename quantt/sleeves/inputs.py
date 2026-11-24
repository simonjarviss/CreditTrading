"""One shadow decision per sleeve for a session, or the reason there is none.

WHAT A DECISION FILE IS. `shadow/engine.py` writes `<state>/<slug>/decisions/<asof>.json`
once, after the close of session `asof`: signed weights as fractions of a notional, to be
filled at the close of the NEXT session. This runner trades session F, so for F it wants
the file whose `asof` is the session before F, and no other: an older file is an older
view of the events, and trading it a day late is a different strategy.

WHY EVERY FILE IS CHECKED AND A BAD ONE IS "NO DECISION", NOT A CRASH. The files are written
by another process, by another user, from a clone that follows an unreleased branch. One
malformed file must not stop every other sleeve from trading, and it must never be traded.
So `read` returns, per sleeve, either the weights or a reason string; `net.py` then HOLDS a
sleeve that has no decision (and flattens it after the book file's `max_stale_sessions`).
The reasons are recorded in the plan.

THE ON-TIME RULE is STRICTER than the shadow engine's. The engine scores a decision written
before 13:00 New York on F (shadow/engine.py, "ON TIME, OR NOT SCORED"). This runner trades
one only if it was written before 09:30 New York on F, the open. Why stricter (review of
stage 2, 2026-11-16): on a 13:00 early close the send window is 12:52-12:58, so a file written
at 12:30 on F passes the engine's rule having seen most of F's session, and would be traded
at F's close: lookahead. Before the open no file can have seen any of F's regular session,
on any day. The engine's 13:00 stays the engine's scoring rule; a decision it scores and this
runner refuses is a held session here, recorded as late. The file must also carry
`fill == "next_close"`, the only convention the engine implements, and this module is given F
and the previous session by the caller from the exchange calendar, never from the file.

This module imports nothing from `shadow`: the file format is read as data, and the
constants it needs are restated here and pinned by a test against a file the engine writes.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
ON_TIME_CUTOFF = dt.time(9, 30)          # the open; stricter than shadow/engine.py's 13:00 (docstring)
FILL = "next_close"                      # shadow/book.py FILLS
SYMBOL = re.compile(r"[A-Z][A-Z0-9.]{0,9}")
MAX_ABS_WEIGHT = 2.0                     # a single weight beyond this is not a book this desk runs


def read_one(decisions_dir: Path, slug: str, asof: dt.date, session: dt.date) -> dict:
    """{"weights": {symbol: float}, "sha256": ..., "written_at": ...} or {"missing": reason}."""
    path = Path(decisions_dir) / slug / "decisions" / f"{asof.isoformat()}.json"
    if not path.exists():
        return {"missing": f"no decision file for {asof} ({path.name} absent)"}
    try:
        blob = path.read_bytes()
        rec = json.loads(blob)
    except (OSError, ValueError) as e:
        return {"missing": f"decision file unreadable ({type(e).__name__})"}
    if not isinstance(rec, dict):
        return {"missing": "decision file is not an object"}
    if rec.get("slug") != slug:
        return {"missing": f"decision file names slug {rec.get('slug')!r}"}
    if rec.get("asof") != asof.isoformat():
        return {"missing": f"decision file is for {rec.get('asof')!r}, not {asof}"}
    if rec.get("fill") != FILL:
        return {"missing": f"fill convention {rec.get('fill')!r} is not {FILL!r}"}
    try:
        written = dt.datetime.fromisoformat(rec["written_at"])
    except (KeyError, TypeError, ValueError):
        return {"missing": "written_at missing or unreadable"}
    if written.tzinfo is None:
        return {"missing": "written_at has no time zone"}
    # ALIGNMENT: the file must predate the OPEN of the session it trades in.
    if not written < dt.datetime.combine(session, ON_TIME_CUTOFF, tzinfo=NY):
        return {"missing": f"written {written.isoformat()}, not before 09:30 New York on {session}: late, never traded"}
    if written.astimezone(NY).date() < asof:
        return {"missing": f"written {written.isoformat()}, before its own as-of session {asof}"}
    w = rec.get("weights")
    if not isinstance(w, dict):
        return {"missing": "weights missing or not an object"}
    out = {}
    for sym, v in w.items():
        if not isinstance(sym, str) or not SYMBOL.fullmatch(sym):
            return {"missing": f"weight for {sym!r}: not a symbol this runner will trade"}
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            return {"missing": f"weight for {sym} is {v!r}"}
        if abs(v) > MAX_ABS_WEIGHT:
            return {"missing": f"weight for {sym} is {v}, beyond {MAX_ABS_WEIGHT}"}
        if v != 0:
            out[sym] = float(v)
    return {"weights": dict(sorted(out.items())), "sha256": hashlib.sha256(blob).hexdigest(),
            "written_at": written.isoformat()}


def read(decisions_dir: Path, slugs, asof: dt.date, session: dt.date) -> dict:
    """{slug: read_one(...)} for the listed slugs only. `asof` must be before `session`."""
    if not asof < session:
        raise ValueError(f"asof {asof} must be before the session {session}")
    return {s: read_one(decisions_dir, s, asof, session) for s in slugs}
