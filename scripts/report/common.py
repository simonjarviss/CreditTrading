"""Shared helpers for the research evidence pack: git, hashing, the palette.

WHY THIS FILE EXISTS (2026-11-03). The team lead asked that everything the desk does
be logged so that a research report can be written from it later. The pack's rule is
CLAUDE.md's data rule made mechanical: a figure without provenance is a rumour. So
every output names the committed inputs it was built from, their sha256, the commit
and the data's last date, and the helpers that establish those facts live in one
place, used by `build_pack.py` and `snapshot_live.py` alike.

Nothing here opens a socket. `git` runs as a local subprocess (no fetch, no push):
the root conftest's subprocess guard allows it, and netguard would stop a network
call if one were ever added.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "results" / "report"
LIVE = PACK / "data" / "live"          # tracked: daily aggregates only
# Gitignored: the row-level live records (per name, per fill, positions). Team lead,
# 2026-11-03, on PR #45: "Aggregates in repo, rows private".
CACHE = PACK / "_cache_live"
EVIDENCE_LOG = PACK / "EVIDENCE_LOG.md"

# Okabe & Ito (2008), the colour-blind-safe qualitative palette. Order matters: the
# first colours are the most distinguishable under deuteranopia and protanopia.
OKABE_ITO = {
    "black": "#000000",
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "grey": "#7F7F7F",
}

# The 2026-09-28 clean slate splits the record into two eras. Anything before it is
# provenance only (CLAUDE.md: "provenance, never evidence of what is true now").
ALPACA_START = "2026-09-28"
HOLDOUT_START = "2023-01-01"     # the sealed time holdout (CLAUDE.md, research rules)


class PackError(RuntimeError):
    """A pack invariant failed. Raised, never swallowed (CLAUDE.md: no silent fallbacks)."""


def git(*args: str, repo: Path = REPO, text: bool = True):
    """Run a local git command and return stdout. Raises PackError naming the command."""
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=text, timeout=120)
    if r.returncode != 0:
        err = r.stderr if text else r.stderr.decode(errors="replace")
        raise PackError(f"git {' '.join(args)} failed ({r.returncode}): {err.strip()[:300]}")
    return r.stdout


def head_commit(repo: Path = REPO) -> str:
    """The full hash of HEAD."""
    return git("rev-parse", "HEAD", repo=repo).strip()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def committed_clean(rel: str, repo: Path = REPO) -> bool:
    """True when `rel` is tracked and identical to HEAD (no staged or unstaged change).

    WHY: the pack builds 'from committed sources only'. A figure drawn from a file
    that is not in a commit cannot be reproduced by anyone else, so the builder
    refuses such an input unless told otherwise, and the manifest records it.
    """
    tracked = subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch", rel],
                             capture_output=True, text=True, timeout=60)
    if tracked.returncode != 0:
        return False
    diff = subprocess.run(["git", "-C", str(repo), "diff", "--quiet", "HEAD", "--", rel],
                          capture_output=True, text=True, timeout=60)
    return diff.returncode == 0
