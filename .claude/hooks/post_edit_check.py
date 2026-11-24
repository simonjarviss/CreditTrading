#!/usr/bin/env python3
"""PostToolUse(Edit|Write) check: the four bug classes this repo actually ships.

WHY THESE FOUR
--------------
Not a generic linter. Every pattern below is a real defect this codebase has
shipped to production, found later, and written up. The point of running them
on every edit is that all four are DORMANT faults -- they look fine, they pass
tests, and they surface months later inside a confident-looking number.

  A. SILENT FALLBACK. `nav_now = _nav_last(...) or 500000.0` sized every
     displayed target against an invented $500k book. `fee.fillna(fee.median())`
     charged an unmeasured name 0.83%/yr inside a total that looked measured.
     House rule: raise, naming what was missing.
     (CLAUDE.md, "Hard rules — code")

  B. EXECUTION CONVENTION. `validate.py:86` used `held = W.shift(1)` -- an
     entry at day t's close using day t's NAV, which publishes AFTER that
     close. Cost: gross SR 1.26 -> 0.95, net SR 0.82 -> 0.51. The convention is
     shift(2): decide at t, MOC fill at t+1, earn the t+2 return.
     A shift(1) on a ROLLING MOMENT (mu, sigma) is correct and expected; a
     shift(1) on HELD WEIGHTS is the lookahead bug. The check cannot tell them
     apart, so it names both readings and leaves the judgement to you.
     (results/AUDIT_2026-07-31.md)

  C. FROZEN SPEC EDITED. A spec key is a governance object, not a constant.
     A new key must default to current behaviour and the no-op must be PROVED
     by diffing sleeve output byte-for-byte with the key absent.

  D. SYNTAX. A file that does not compile, caught now rather than at 17:15 ET.

Advisory, never blocking: it reports on ADDED lines only (via git diff), so it
speaks about what you just wrote rather than about the file's history. Exit 0
always -- a broken checker must not break editing.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

REPO = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

EXCEPT_RX = re.compile(r"except\b[^:]*:")
SILENT_EXCEPT = (
    "NO SILENT FALLBACKS. Raise, naming what was missing. If the failure is "
    "genuinely tolerable, catch the SPECIFIC exception and log what was lost -- "
    "`except: pass` is how the 2026-07-31 ledger crash printed one repr() line "
    "inside a run that ended with \"ok\" while 302 real executions went "
    "unrecorded.")

# (compiled pattern, short label, what to do about it)
PY_PATTERNS = [
    (re.compile(r"\.fillna\s*\("),
     "fillna",
     "fillna substitutes an invented value for missing data. If the datum is "
     "required, raise and name it. If it is genuinely optional, say so in a "
     "comment and record how many rows were filled."),
    (re.compile(r"=\s*[^=#\n]*\)\s*or\s+(?:[\d'\"]|None\b)"),
     "`x = f(...) or <default>`",
     "This is the `nav_now = _nav_last(...) or 500000.0` shape: a default "
     "silently standing in for a missing measurement. Raise instead."),
    (re.compile(r"\.shift\s*\(\s*1\s*\)"),
     "shift(1)",
     "Check which quantity this shifts. A rolling moment (mu/sigma) shifted 1 "
     "day is correct and point-in-time. HELD WEIGHTS shifted 1 enter at t's "
     "close on t's NAV, which does not exist yet -- that is the lookahead bug "
     "that cost net SR 0.82 -> 0.51. The traded convention is shift(2)."),
]

SPEC_RX = re.compile(r"ops/specs/.*\.frozen\.json$")
BOOK_RX = re.compile(r"ops/books/[^/]*\.json$")


def added_lines(path: str):
    """(lineno, text) for lines this edit ADDED, per git. Falls back to the
    whole file when git cannot help (untracked, no repo, new file)."""
    try:
        out = subprocess.run(
            ["git", "diff", "--unified=0", "--no-color", "--", path],
            cwd=REPO, capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            rows, lineno = [], 0
            for line in out.stdout.splitlines():
                m = re.match(r"^@@ -\S+ \+(\d+)", line)
                if m:
                    lineno = int(m.group(1))
                    continue
                if line.startswith("+") and not line.startswith("+++"):
                    rows.append((lineno, line[1:]))
                    lineno += 1
            return rows
    except Exception:
        pass
    try:
        with open(path, "r", errors="replace") as fh:
            return list(enumerate(fh.read().splitlines(), 1))
    except Exception:
        return []


def check_python(path: str, findings: list):
    try:
        src = open(path, "r", errors="replace").read()
        compile(src, path, "exec")
    except SyntaxError as exc:
        findings.append(f"SYNTAX ERROR {path}:{exc.lineno}: {exc.msg}")
        return
    except Exception:
        return
    rows = added_lines(path)
    seen = set()
    for i, (lineno, text) in enumerate(rows):
        stripped = text.strip()
        if stripped.startswith("#"):
            continue
        # A swallowed exception is usually two lines: `except X:` then `pass`.
        # Look at the same line and the next one, so both forms are caught.
        if EXCEPT_RX.match(stripped):
            body = stripped.split(":", 1)[1].strip()
            if not body and i + 1 < len(rows):
                body = rows[i + 1][1].strip()
            if body in ("pass", "continue") and "silent except" not in seen:
                seen.add("silent except")
                findings.append(f"{path}:{lineno}  silent except -> " + SILENT_EXCEPT)
        for rx, label, advice in PY_PATTERNS:
            if rx.search(text) and label not in seen:
                seen.add(label)
                findings.append(f"{path}:{lineno}  {label} -> {advice}")


def check_json(path: str, findings: list):
    try:
        json.load(open(path))
    except Exception as exc:
        findings.append(f"INVALID JSON {path}: {exc}")
        return
    rel = os.path.relpath(path, REPO)
    if SPEC_RX.search(rel.replace(os.sep, "/")):
        findings.append(
            f"{rel} is a FROZEN SPEC. Changing a key is a governance act, not "
            "a code change: (1) the new key must default to CURRENT behaviour "
            "and the no-op must be proved by diffing sleeve output "
            "byte-for-byte with the key absent; (2) add a sibling `_<key>_note` "
            "recording what was measured, what was rejected, and the exact "
            "REVERT (usually: delete this key); (3) a change that alters "
            "traded behaviour needs a dated note under results/ (what changes, "
            "why, the revert) and a line in results/IDEA_LEDGER.md before the "
            "session that trades it. Run /spec-change if you have not already.")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    try:
        path = payload.get("tool_input", {}).get("file_path", "")
        if not path or not os.path.isfile(path):
            return 0
        findings: list = []
        if path.endswith(".py"):
            check_python(path, findings)
        elif path.endswith(".json"):
            check_json(path, findings)
        if findings:
            head = ("Project check (.claude/hooks/post_edit_check.py) — "
                    "advisory, on the lines you just added:\n  - ")
            json.dump({"systemMessage": head + "\n  - ".join(findings)},
                      sys.stdout)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
