"""The session's on-disk record under `$QUANTT_STATE_DIR`. Durable before it is convenient.

LAYOUT
------
    $QUANTT_STATE_DIR/
      AUTO_ARMED                 created by the team lead after the first go (gate 2)
      <YYYY-MM-DD>/              the SESSION date (ET), the day the orders are for
        plan.json                the latest plan; once STARTED exists, the plan
                                 that was transmitted, never overwritten after
        STARTED                  written, exclusively, BEFORE the first order
        orders.jsonl             one line per submit attempt / response / lookup
        runs/<utc-stamp>-<mode>.json   every run's full record, never overwritten

WHY EACH PIECE
--------------
  * STARTED is the local half of gate 6 and CLAUDE.md order-path rule 2 ("must
    record that it started before its first order goes"). It is created with
    `os.link` from a fully-written, fsynced temp file: `link` fails if the name
    exists, so two runs racing cannot both believe they are first, and a crash
    can never leave a half-written STARTED that reads as absent.
  * orders.jsonl is appended and fsynced line by line AS the orders go, so a
    crash between two POSTs leaves an exact record of which ids were attempted.
    The intent line is written before each POST, the response after it.
  * plan.json is what `verify.py` and a human read. A later refused or dry run
    the same day must not overwrite the plan that actually went, so once
    STARTED exists plan.json is left alone; runs/ keeps every run regardless.

Nothing here ever writes a credential: the session never holds one (the client
keeps keys in its HTTP session headers only).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from pathlib import Path


class StateDirError(RuntimeError):
    """QUANTT_STATE_DIR is unset or does not name an existing directory."""


def state_dir_from_env(env) -> Path:
    """The required state root (RUNNER.md: unset -> raise). It must already
    exist: creating it here would let a typo in a plist start a fresh, empty
    state dir in which STARTED and AUTO_ARMED are silently absent."""
    v = env.get("QUANTT_STATE_DIR", "")
    if not v:
        raise StateDirError("QUANTT_STATE_DIR is not set: it must name the book's state "
                            "directory (docs/RUNBOOK.md)")
    p = Path(v).expanduser()
    if not p.is_dir():
        raise StateDirError(f"QUANTT_STATE_DIR={v} is not an existing directory; "
                            f"create it deliberately, the runner will not")
    return p


# THE STATE DIRECTORY'S NAME, PER BOOK (C4 integration, 2026-10-29). Every book
# keeps <state>/<D>/STARTED, plan.json and verify.log under the same names, so a
# book run with another book's QUANTT_STATE_DIR would read that book's STARTED as
# its own (gate 6 would refuse the real one, or pass a second set) and append to
# its verify.log. A book listed here must run in a directory with this name, as
# the collector already requires (collect.BOOKS[...]["state_dir_name"]). The core
# is not listed: its state dir is checked exactly as before. Read by the session
# (run.run_session, approve_main) and verify (verify.main), which never import
# each other, so the rule lives here, beside state_dir_from_env.
STATE_DIR_NAMES = {"c4": "c4"}


def require_book_state_dir(book: str, state: Path) -> None:
    """Raise StateDirError when `book` must run in a directory of its own name and
    `state` is not one (STATE_DIR_NAMES). A book not listed: nothing is checked."""
    want = STATE_DIR_NAMES.get(book)
    if want is not None and Path(state).name != want:
        raise StateDirError(f"--book {book} needs its own state directory, named {want!r}; "
                            f"QUANTT_STATE_DIR={state} is not (another book's STARTED, "
                            f"plan.json and verify.log for the same session live there)")


def day_dir(state: Path, session_date: dt.date) -> Path:
    d = state / session_date.isoformat()
    d.mkdir(exist_ok=True)
    return d


def _default(o):
    if isinstance(o, (dt.datetime, dt.date)):
        return o.isoformat()
    raise TypeError(f"cannot record {type(o).__name__} {o!r} as JSON")


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, default=_default)


def _write_tmp(path: Path, text: str) -> Path:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    return Path(tmp)


def write_json_atomic(path: Path, obj) -> None:
    """Temp file beside it, fsync, rename: a reader sees the old or the new file."""
    tmp = _write_tmp(path, dumps(obj))
    os.replace(tmp, path)


def create_exclusive(path: Path, obj) -> bool:
    """Create `path` with `obj` iff it does not exist. True if this call created
    it, False if it already existed. Atomic and exclusive (see STARTED above)."""
    tmp = _write_tmp(path, dumps(obj))
    try:
        os.link(tmp, path)
        return True
    except FileExistsError:
        return False
    finally:
        os.unlink(tmp)


def append_jsonl(path: Path, obj) -> None:
    """One JSON line, flushed and fsynced before returning."""
    line = json.dumps(obj, sort_keys=True, default=_default)
    with open(path, "a") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
