#!/usr/bin/env python3
"""SessionStart hook: open every session knowing what trades, and from where.

Prints a short plain-text block, which Claude Code shows to Claude on
SessionStart. Deliberately a few lines: this cost is paid on every session.

REWRITTEN 2026-09-28 for the Alpaca migration (the IBKR-era banner -- last
broker-confirmed fill, halts, heartbeats -- is at git tag `pre-clean-slate`),
and again 2026-10-08, because the 09-28 version printed "NO LIVE BOOK ...
Nothing trades" from a constant for nine days after the book armed
(`docs/ROADMAP.md` 4.8). It now prints `book_state.collect()`, which is
`ops.prod_state`: which machine is prod, whether it is armed, its tag, its last
verify verdict and the equity snapshot (official P&L: orient PNL), and a WARNING first if two
machines are armed for the one Alpaca account.

The principle from the IBKR banner stands, in both directions: say plainly
what is true, and when the reader fails, say UNMEASURED rather than print
nothing -- a missing line reads as "nothing to report", which is a claim.

The VM is read over ssh with a 3-second budget (`book_state.BANNER_VM_TIMEOUT_S`),
so an unreachable VM costs a session start at most that and reads UNMEASURED.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from book_state import collect
except Exception as _import_error:  # the banner must still print: see main()
    _IMPORT_ERROR = f"{type(_import_error).__name__}: {_import_error}"

    def collect(**_):
        raise RuntimeError(f"book_state did not import ({_IMPORT_ERROR})")


POINTER = ("  Numbers: python3 -m ops.orient · what the system is and has decided: "
           "docs/SYSTEM.md · the plan to prod: docs/ROADMAP.md · anything older is "
           "git tag pre-clean-slate (docs/HISTORY.md), never current state.")

LABELS = {"laptop": "laptop (launchd)", "vm": "VM (systemd)"}
SHORT = {"laptop": "laptop", "vm": "VM"}
WORDS = {"ARMED": "ARMED", "PER_DAY": "armed for a per-day approval only",
         "DRY": "DRY", "OFF": "OFF", "NOT_INSTALLED": "not installed",
         "UNMEASURED": "UNMEASURED"}


def _reading(r) -> str:
    """One prod_state reading as text, a gap always reading as a gap."""
    if not isinstance(r, dict):
        return "UNMEASURED"
    if "UNMEASURED" in r:
        return "UNMEASURED"
    if "absent" in r:
        return "none"
    return str(r.get("value"))


def _machine_line(name: str, m: dict) -> str:
    a = m.get("arming", "UNMEASURED")
    head = f"  {LABELS.get(name, name)}: {WORDS.get(a, a)}"
    if "UNMEASURED" in m:
        return f"{head} — {m['UNMEASURED']}"
    bits = [f"tag {_reading(m.get('tag'))}"]
    vl = m.get("verify_last") or {}
    if "value" in vl:
        v = vl["value"]
        bits.append(f"last verdict {v.get('date') or '?'} {v.get('verdict') or v.get('line', '')[:40]}")
    else:
        bits.append(f"last verdict {_reading(vl)}")
    return head + " · " + " · ".join(bits)


def prod_lines(s: dict) -> list:
    p = (s or {}).get("prod") or {}
    v = p.get("verdict")
    if not v:
        why = (s or {}).get("error") or "no prod reading"
        return [f"  PROD UNMEASURED ({why}). Assume nothing about what is or is not "
                "trading: run python3 -m ops.orient."]
    out = []
    if v.get("warning"):
        out.append("  " + v["warning"])
    else:
        line = v.get("line", "")
        out.append("  " + line[:1].upper() + line[1:] + ".")
        if v.get("prod"):
            eq = v.get("equity") or {}
            if "value" in eq:
                e = eq["value"]
                try:
                    amount = f"${float(e.get('equity')):,.2f}"
                except (TypeError, ValueError):
                    amount = f"{e.get('equity')!r} (not a number)"
                out.append(f"  Live equity {amount}: snapshot read after the {e.get('date')} "
                           f"close (the {SHORT[v['prod']]}'s equity.csv); official end-of-day "
                           f"P&L: python3 -m ops.orient PNL.")
            else:
                out.append(f"  Live equity: {_reading(eq)} (the {SHORT[v['prod']]}'s equity.csv).")
    for c in v.get("cautions") or []:
        out.append(f"  Caution — {c}")
    for name, m in (p.get("machines") or {}).items():
        out.append(_machine_line(name, m))
    return out


def _probe_text(book: str, p) -> str:
    """`cef 2026-09-28 (10 days old)`: the age is the point, because a probe
    is true about tradability and borrow on its own date only."""
    if not p:
        return f"{book} NONE"
    stamp = str(p.get("fetched_at_utc") or "")
    try:
        d = dt.date.fromisoformat(stamp[:10])
    except ValueError:
        return f"{book} {p.get('file')} (undated: no fetched_at_utc)"
    return f"{book} {d} ({(dt.date.today() - d).days} days old)"


def main() -> int:
    try:
        s = collect(vm="live")
    except Exception as e:
        s = {"error": f"{type(e).__name__}: {e}"}

    out = ["QUANTT state (.claude/hooks/session_context.py):"]
    try:
        body = prod_lines(s)
        probes = s.get("probes") or {}
        if probes:
            body.append("  Alpaca probe snapshots (tradability/borrow on their date only): "
                        + ", ".join(_probe_text(b, p) for b, p in probes.items()))
        g = s.get("git") or {}
        if g:
            am = g.get("against_main")
            # docs/STANDARD.md A1.1: on 2026-11-22 this banner said only the branch
            # and the dirty count while the folder sat 841 commits behind main.
            if am is None:
                rel = "against origin/main UNMEASURED (book_state gave no reading)"
            elif "UNMEASURED" in am:
                rel = f"against origin/main UNMEASURED ({am['UNMEASURED']})"
            else:
                rel = (f"{am['behind']} behind origin/main as of the last fetch "
                       f"({am.get('last_fetch') or 'never fetched'})")
            body.append(f"  git {g.get('branch')}, {g.get('dirty')} file(s) uncommitted, {rel}.")
            if am and "UNMEASURED" not in am and am.get("behind"):
                body.insert(0, f"  WARNING — this checkout is {am['behind']} commit(s) behind "
                               f"origin/main: the CLAUDE.md and rules this session loaded may be "
                               f"superseded. Work from origin/main (docs/STANDARD.md A1.1).")
    except Exception as e:  # a state this banner cannot format is said, not skipped
        body = [f"  PROD UNMEASURED (the banner could not format the state: "
                f"{type(e).__name__}: {e}). Run python3 -m ops.orient."]
    out.extend(body)
    # The one pointer every session needs before it reads anything. Six
    # documents once each claimed to be where to start; the answer now has two
    # owners and a folder that is explicitly not one (docs/INDEX.md).
    out.append(POINTER)
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
