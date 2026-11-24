"""How far a checkout is from `origin/main`: the measurer for `docs/STANDARD.md` A1.1.

WHY THIS EXISTS
---------------
On 2026-11-22 the team lead's main dev folder was on a branch made on 2026-10-18,
841 commits behind `origin/main`, holding an untracked `CLAUDE.md` from before the
2026-11-09 rewrite. Every Claude Code session opened there loaded rules that main
had replaced two weeks earlier, and nothing said so: orient printed the branch and
"148 uncommitted", the banner the branch and the dirty count. A session cannot
know its instructions are stale unless something measures it at the start.

`ops.orient` TREES and the SessionStart banner (through
`.claude/hooks/book_state.py`) both call `against_main`, so the two cannot
disagree.

WHAT IT MEASURES, AND WHAT IT DOES NOT
--------------------------------------
Local refs only: commits on `origin/main` that HEAD lacks (behind) and commits on
HEAD that `origin/main` lacks (ahead), as of the last fetch. It never fetches: the
banner runs on every session start and a network call there costs every session.
The last fetch time is returned beside the counts so a stale fetch is visible
instead of reading as "up to date".

No silent fallbacks (`CLAUDE.md`): if `origin/main` is missing or git fails, the
result is `{"UNMEASURED": reason}`, never a zero.
"""
from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

REF = "origin/main"


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])} failed: {r.stderr.strip()[:160]}")
    return r.stdout.strip()


def _last_fetch(repo: Path) -> str | None:
    """Local time of the last fetch, from FETCH_HEAD's mtime in the shared git dir.

    In a worktree `.git` is a file, so the common dir is asked for. None means
    this clone has never fetched, which is said, not hidden.
    """
    common = Path(_git(repo, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = (repo / common).resolve()
    fh = common / "FETCH_HEAD"
    if not fh.exists():
        return None
    return dt.datetime.fromtimestamp(fh.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def against_main(repo: Path) -> dict:
    """`{"behind": int, "ahead": int, "last_fetch": str | None}`, or `{"UNMEASURED": why}`."""
    try:
        _git(repo, "rev-parse", "--verify", "--quiet", REF)
    except RuntimeError:
        return {"UNMEASURED": f"no {REF} ref in this clone (never fetched, or no remote named origin)"}
    try:
        ahead, behind = (int(x) for x in _git(
            repo, "rev-list", "--left-right", "--count", f"HEAD...{REF}").split())
        return {"behind": behind, "ahead": ahead, "last_fetch": _last_fetch(repo)}
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
        return {"UNMEASURED": f"{type(e).__name__}: {e}"}


def describe(a: dict) -> str:
    """One line for a report: '0 behind, 3 ahead of origin/main (as of the last fetch, …)'."""
    if "UNMEASURED" in a:
        return f"UNMEASURED — {a['UNMEASURED']}"
    when = a["last_fetch"] or "never fetched"
    return f"{a['behind']} behind, {a['ahead']} ahead of {REF} (as of the last fetch, {when})"


def warning(a: dict) -> str | None:
    """The sentence a session must see when its checkout is behind main, else None."""
    if "UNMEASURED" in a or a["behind"] == 0:
        return None
    return (f"this checkout is {a['behind']} commit(s) behind {REF} (as of the last fetch, "
            f"{a['last_fetch'] or 'never fetched'}): the CLAUDE.md and rules loaded from it may be "
            f"superseded. Work from {REF} or a branch made from it (docs/STANDARD.md A1.1).")
