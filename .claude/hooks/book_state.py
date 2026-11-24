#!/usr/bin/env python3
"""The one reader of "is anything trading, and from which machine?" for the
SessionStart banner and the status line.

    python3 .claude/hooks/book_state.py -p           # the state as JSON (live VM call)
    python3 .claude/hooks/book_state.py -p --no-vm   # the laptop only

HISTORY. Until 2026-09-28 this read the IBKR prod tree: broker-confirmed fills,
halts, heartbeats, the shadow ledger (git tag `pre-clean-slate`,
`_archive/claude_layer/hooks/book_state_2026-09-28.py`). The rewrite that day
returned `"live_book": None` -- a constant -- with a comment promising it would
become a measurement "when the adapter lands". The adapter landed, the book
armed on 2026-09-29, and the constant went on telling every session "NO LIVE
BOOK. Nothing trades" until 2026-10-08 (`docs/ROADMAP.md` 4.8).

WHAT IT PRESERVES. The old reader existed because a 21-session outage went
unnoticed while every surface read "ok". The property that matters is that
SILENCE NEVER READS AS SUCCESS, and it cuts both ways: a book that trades must
not read as idle either. Every state here is measured, and a reading that fails
says UNMEASURED; nothing reads "ok" because nothing complained.

WHAT IT READS. `ops.prod_state`, the same measurement as `python3 -m
ops.orient` PROD, so the banner, the status line and orient cannot disagree:
the laptop's launchd jobs, plists and state dir, and the VM over one read-only
ssh call. Plus git and the names of the read-only Alpaca probe's snapshots. No
broker connection and no keys.

THE VM CALL AND ITS BUDGET. The banner (`vm="live"`) makes the one ssh call
with a hard budget of `BANNER_VM_TIMEOUT_S` (measured ~1 s from the laptop on
2026-10-08), so an unreachable VM delays a session start by at most that, and
then says UNMEASURED. It writes what it read to `VM_CACHE`. The status line
(`vm="cached"`) never opens ssh: it re-renders on every assistant message, and
an ssh login per refresh would fill the VM's auth log and stall the line
whenever the VM is unreachable. It shows the banner's VM reading with its age,
and once that is older than `VM_CACHE_MAX_AGE_S` it says so rather than show a
stale state as current.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops import prod_state as ps  # noqa: E402  (stdlib-only; see its docstring)
from ops import checkout  # noqa: E402  (stdlib-only: git through subprocess)

PROBE_DIR = REPO / "results" / "ops" / "alpaca_probe"
BOOKS = ("cef", "b6")          # quantt.broker.alpaca_probe.BOOK_SPECS; not imported,
                               # because that module's import is not ours to keep light.

BANNER_VM_TIMEOUT_S = 3
VM_CACHE = Path(os.environ.get("TMPDIR", "/tmp")) / "quantt-vm-state.json"
VM_CACHE_MAX_AGE_S = 60 * 60


def _git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                       text=True, timeout=5)
    return r.stdout.strip()


def probes() -> dict:
    """{book: {"file", "fetched_at_utc"} or None} for the latest snapshot.

    The date is the snapshot's own `fetched_at_utc`, because the banner says
    how old it is: a probe records tradability and borrow on its date only
    (`borrow_status` changes daily, CLAUDE.md landmine 5).
    """
    out = {}
    for b in BOOKS:
        snaps = sorted(PROBE_DIR.glob(f"*_{b}.json"))
        if not snaps:
            out[b] = None
            continue
        try:
            fetched = json.loads(snaps[-1].read_text()).get("fetched_at_utc")
        except (OSError, ValueError) as e:
            fetched = f"UNMEASURED ({type(e).__name__})"
        out[b] = {"file": snaps[-1].name, "fetched_at_utc": fetched}
    return out


def _write_vm_cache(reading: dict, now: float | None = None) -> None:
    """Best effort, and only for the status line: a failed write leaves the
    status line saying "no VM reading cached", which is true."""
    try:
        VM_CACHE.write_text(json.dumps({"cached_at_epoch": now or time.time(),
                                        "vm": reading}, default=str))
    except OSError:
        return


def _read_vm_cache(now: float | None = None) -> dict:
    try:
        d = json.loads(VM_CACHE.read_text())
        age = (now or time.time()) - float(d["cached_at_epoch"])
        reading = d["vm"]
    except FileNotFoundError:
        return ps.vm_unmeasured("no VM reading cached yet (the banner makes it at "
                                "session start); run python3 -m ops.orient")
    except (OSError, ValueError, KeyError, TypeError) as e:
        return ps.vm_unmeasured(f"VM cache {VM_CACHE} unreadable ({type(e).__name__}); "
                                "run python3 -m ops.orient")
    if age > VM_CACHE_MAX_AGE_S:
        return ps.vm_unmeasured(f"the last VM reading is {age / 60:.0f} min old; "
                                "run python3 -m ops.orient")
    reading["cached_age_s"] = round(age)
    return reading


def collect(vm: str = "live") -> dict:
    """`vm`: "live" (one ssh call, BANNER_VM_TIMEOUT_S, refreshes the cache),
    "cached" (the status line: never ssh), or "skip"."""
    lap = ps.laptop()
    if vm == "live":
        v = ps.vm(timeout=BANNER_VM_TIMEOUT_S)
        _write_vm_cache(v)
    elif vm == "cached":
        v = _read_vm_cache()
    elif vm == "skip":
        v = ps.vm_unmeasured("not measured by this caller; run python3 -m ops.orient")
    else:
        raise ValueError(f"vm must be live, cached or skip, not {vm!r}")
    machines = {"laptop": lap, "vm": v}
    return {
        "prod": {"machines": machines, "verdict": ps.verdict(machines)},
        "probes": probes(),
        "git": {"branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
                "dirty": len([l for l in _git("status", "--porcelain").splitlines()
                              if l.strip()]),
                # docs/STANDARD.md A1.1; shared with orient TREES (ops/checkout.py).
                "against_main": checkout.against_main(REPO)},
    }


if __name__ == "__main__":
    state = collect(vm="skip" if "--no-vm" in sys.argv else "live")
    json.dump(state, sys.stdout, indent=2 if "-p" in sys.argv else None, default=str)
    print()
