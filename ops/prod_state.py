#!/usr/bin/env python3
"""Which machine is prod, and is it armed? Measured on every call, never written.

    python3 -m ops.prod_state            # the readout (orient's PROD section)
    python3 -m ops.prod_state --json
    python3 -m ops.prod_state --no-vm    # the laptop only: no SSH

WHY THIS FILE EXISTS
--------------------
On 2026-09-28 IBKR was retired and three surfaces were rewritten to say so:
`ops.orient` printed "prod none ... the Alpaca prod (cloud VM) is not built"
and "live book NONE -- nothing trades", the SessionStart banner "NO LIVE BOOK
... Nothing trades", and the status line "no live book" in red. Each was a
string constant. The first armed session was 2026-09-29 (the laptop's
`~/quantt_state/cef/verify.log`) and the book has traded since, while all three
went on saying it did not, because a constant cannot notice that it has become
false. That is the failure the IBKR-era reader existed to prevent (a 21-session
outage under surfaces that read "ok") with the sign reversed.

The answer to "which machine is prod" is also about to move: prod goes from the
laptop (launchd) to an Azure VM (systemd) by `docs/RUNBOOK.md` section 8. A
written answer would be wrong within the week. So this module measures, and
orient, the banner and the status line all read it (`docs/ROADMAP.md` 4.8).

WHAT "ARMED" MEANS HERE (`docs/RUNNER.md`, gates 1 and 2)
--------------------------------------------------------
  ARMED          the scheduler will fire the session job, DRY_RUN is exactly
                 "0" in its environment, AND `<state>/AUTO_ARMED` exists: every
                 decided plan is sent.
  PER_DAY        as ARMED but with no AUTO_ARMED: a scheduled send transmits
                 only a plan that carries a recorded per-day approval.
  DRY            the scheduler fires it, and DRY_RUN is anything but "0" (unset
                 included): gate 1 sends nothing.
  OFF            installed, but the scheduler will not fire the session job:
                 launchd has it unloaded AND disabled, or systemd has its timer
                 inactive AND not enabled. What its files say is kept, and a
                 DRY_RUN=0 or an AUTO_ARMED left behind is raised as a caution.
  NOT_INSTALLED  that machine has no session job.
  UNMEASURED     a reading the call needs failed; the reason is kept.

The scheduler's environment is read where the scheduler reads it: the laptop's
plist `EnvironmentVariables`, and systemd's LOADED `Environment` on the VM, not
the unit file (`quantt/deploy/install_vm.py` records why the loaded copy is the
truth). "Will fire" is not "is loaded right now": `docs/RUNBOOK.md` 8.5 step 1
records that launchd loads a plist in `~/Library/LaunchAgents` again at the
next login, so an unloaded job that is NOT disabled still counts as scheduled,
and a stopped timer that is still enabled starts again at boot. Only unloaded
and disabled (or inactive and not enabled) is OFF.

MEASURED 2026-10-08, mid cut-over: the laptop's three jobs were unloaded and
disabled with AUTO_ARMED removed, but its plists still said DRY_RUN=0 (8.5
step 1a not yet run). A first version of this module read "DRY_RUN=0 in the
plist" as armed and printed the two-schedulers WARNING over a scheduler that
could not fire. That false alarm is why OFF exists, and why the plists'
DRY_RUN=0 is still reported (as a caution, not a hazard).

TWO ARMED SCHEDULERS ON ONE ACCOUNT
-----------------------------------
Both machines trade one Alpaca paper account. Each checks gate 6 against its
own state dir, so two schedulers with DRY_RUN=0 would each send, and only the
Alpaca-side `client_order_id` prefix check would stand between them and a
doubled book (`CLAUDE.md` order-path rule 2). `verdict()` raises a WARNING
whenever both machines are ARMED or PER_DAY. A machine that cannot be measured
is never assumed safe: one armed machine beside an UNMEASURED one is reported
as "a second armed scheduler is not ruled out".

READ-ONLY, AND WHAT IT NEVER TOUCHES
------------------------------------
On the laptop: `launchctl list` and `launchctl print-disabled` (read-only verbs;
the only ones the test harness lets through), `git describe`, and file reads.
On the VM: one `ssh` call that runs `REMOTE_SCRIPT`, a fixed read-only script.
It never reads `QUANTT_ENV_FILE` or `config/.env`, never reads `/run/quantt`
(the keys), and cuts systemd's Environment down to DRY_RUN on the VM so not
even the key file's path crosses the wire. It never touches `~/prod/QUANTT`,
the retired IBKR tree, which is not the Alpaca prod.

THE DAILY P&L SERIES (added 2026-10-19)
--------------------------------------
The team lead ruled on 2026-10-19 that Alpaca's end-of-day portfolio history
(GET /v2/account/portfolio/history, timeframe=1D) is the official daily P&L of
record, and that verify's `equity - last_equity`, read after the close, is a
labelled snapshot beside it. On the four sessions the main session compared
that day, the snapshot differed from the EOD history on every one and the
auction-marked score agreed with it far more closely [V, main session
2026-10-19; the account's figures are kept out of this public repo]: the
snapshot is marked after the close (`quantt/session/score.py` (a) flags it
[U]). So each machine's reading now carries its P&L files
(`PNL_FILES`): the EOD series whole, and the last rows of the snapshot,
auction-marked and distribution-adjusted scores. Only the named columns cross
the wire, selected by header ON the VM (`pnl_tails`); scores.csv's
`per_symbol_json`, which holds the positions, never does. orient's PNL section
does the arithmetic, from the prod machine's files only.

THE REPO IS PUBLIC
------------------
The VM is reached only by the ssh alias `quantt-vm`. Its address lives in
`~/.ssh/config` and nowhere in this repository. ssh's own errors name the
address ("connect to host <ip> port 22"), and readouts get pasted into tracked
notes, so stderr is scrubbed of IP addresses before it is returned.

STDLIB ONLY
-----------
The SessionStart hook and the status line import this on every session, so it
imports only the standard library, the NYSE calendar, and the two installers,
which are stdlib-only themselves and are the single owners of the labels, unit
names and paths read here. A path written twice drifts; one imported does not.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import inspect
import json
import os
import plistlib
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from quantt.deploy import install_prod as ip  # noqa: E402
from quantt.deploy import install_vm as iv  # noqa: E402

ARMED, PER_DAY, DRY, OFF = "ARMED", "PER_DAY", "DRY", "OFF"
NOT_INSTALLED, UNMEASURED = "NOT_INSTALLED", "UNMEASURED"
HOT = (ARMED, PER_DAY)          # scheduled with DRY_RUN=0: can transmit

VM_ALIAS = "quantt-vm"
SSH_CONNECT_TIMEOUT_S = 3
# orient's budget for the whole ssh call (connect, every read in REMOTE_SCRIPT,
# teardown). Measured 2026-10-08 from the laptop: ~1 s end to end. The banner
# passes its own, shorter budget (`.claude/hooks/book_state.py`).
VM_TIMEOUT_S = 10
LOCAL_TIMEOUT_S = 5

_VM_LAYOUT = iv.Layout(Path("/home") / iv.SERVICE_USER)
_VM_SESSION = next(j for j in iv.VM_JOBS if j.job.log_stem == "session")
VM_TIMERS = tuple(j.timer for j in iv.VM_JOBS)

Run = Callable[..., subprocess.CompletedProcess]


# --------------------------------------------------------------- readings --
# Every reading is a dict with exactly one of three keys, so a renderer can
# never print a gap as if it were a value:
#   {"value": v}          measured (v may be None, e.g. DRY_RUN unset)
#   {"absent": why}       measured, and the thing does not exist
#   {"UNMEASURED": why}   could not be measured; `why` names what was tried
def _val(v, **extra) -> dict:
    return {"value": v, **extra}


def _absent(why: str) -> dict:
    return {"absent": why}


def _unm(why: str) -> dict:
    return {UNMEASURED: why}


def show(r: dict | None) -> str:
    """One reading as text. A gap always reads as a gap."""
    if not isinstance(r, dict):
        return "UNMEASURED — no reading"
    if UNMEASURED in r:
        return f"UNMEASURED — {r[UNMEASURED]}"
    if "absent" in r:
        return f"none ({r['absent']})"
    return str(r["value"])


_IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
# Four or more groups, or a `::` form. Three groups is left alone: that is what
# an HH:MM:SS timestamp looks like, and an error's time is worth keeping.
_IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}\b"
                   r"|(?:\b[0-9a-fA-F]{1,4})?(?::[0-9a-fA-F]{1,4})*::(?:[0-9a-fA-F]{1,4}\b)?"
                   r"(?::[0-9a-fA-F]{1,4}\b)*")


def scrub(text: str) -> str:
    """ssh's stderr with any IP address replaced, first line only, short.
    The repo is public and readouts get pasted (module docstring)."""
    first = (text or "").strip().splitlines()[0:1]
    line = first[0] if first else ""
    return _IPV6.sub("<address>", _IPV4.sub("<address>", line))[:160]


def _cmd(cmd: list) -> str:
    return " ".join(shlex.quote(str(c)) for c in cmd)


def _call(run: Run, cmd: list, timeout: float, **kw):
    """(CompletedProcess, None) or (None, why). Never raises for the usual
    ways a read-only command fails: missing binary, timeout."""
    try:
        return run(cmd, capture_output=True, text=True, timeout=timeout, **kw), None
    except subprocess.TimeoutExpired:
        return None, f"`{_cmd(cmd)}` did not finish within {timeout}s"
    except OSError as e:
        return None, f"`{_cmd(cmd)}` could not run: {type(e).__name__}: {e}"


# ----------------------------------------------------------------- shared --
VERDICT_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (PASS|FAIL)\b")


def verdict_line(line: str) -> dict:
    """A verify.log line: `<date> PASS|FAIL <book> <reason>` (quantt/session/verify.py).
    A line in another shape is kept whole, with no date or verdict invented."""
    m = VERDICT_RE.match(line)
    return {"date": m.group(1) if m else None,
            "verdict": m.group(2) if m else None, "line": line}


def equity_row(header_line: str, last_line: str, where: str) -> dict:
    """The last equity.csv row, by the file's OWN header.

    The collector writes it (`quantt/collect/collect.py`, step
    account_snapshot): Alpaca's account equity read after D's close. It is
    the broker's own number, unlike the probe snapshot, but since 2026-10-19 it
    is a SNAPSHOT, not the P&L of record: its marks can move after the close
    (eod_equity.csv is the record, orient PNL). The columns are read from the header, not assumed, so a reordered
    or renamed file is a named gap instead of a confident wrong number.
    """
    cols = next(csv.reader([header_line]), [])
    missing = [c for c in ("date", "equity") if c not in cols]
    if missing:
        return _unm(f"{where} header is {cols}: no {missing} column")
    if last_line.strip() == header_line.strip():
        return _absent(f"{where} has a header and no rows yet")
    row = next(csv.reader([last_line]), [])
    if len(row) != len(cols):
        return _unm(f"{where} last row has {len(row)} fields for {len(cols)} columns")
    rec = dict(zip(cols, row))
    return _val({"date": rec["date"], "equity": rec["equity"],
                 "read_at_utc": rec.get("read_at_utc"), "source": where})


# --------------------------------------------------------------- P&L files --
# The three daily P&L series a state dir holds, and the ONLY columns read from
# each (team lead, 2026-10-19: Alpaca's end-of-day portfolio history is the
# official daily P&L of record; verify's after-the-close `equity - last_equity`
# is a labelled snapshot beside it, never blended):
#   eod_equity        Alpaca's EOD history as the collector records it (the
#                     record); absent until that collector step is installed
#   scores            verify's rows: the snapshot and the auction-marked score
#                     (`quantt/session/verify.py` SCORES_COLUMNS)
#   dist              the distribution-adjusted score
#                     (`quantt/session/dist_score.py` COLUMNS)
# The third element is how many rows are kept from the end. scores.csv and
# distribution_scores.csv feed a 10-session comparison, so 30 rows covers it
# with re-run duplicates to spare. eod_equity.csv is kept WHOLE up to a cap,
# because cumulative P&L since funding, the high-water mark and realised vol are
# whole-series figures: computed on the last 30 rows they would be a different
# number under the same name once the book is 31 sessions old. 2520 rows is ten
# years of sessions at ~40 bytes a row; a file longer than that is reported as
# such and those figures go UNMEASURED (`ops/orient.py` pnl), never computed
# on a window.
EOD_MAX_ROWS = 2520
PNL_TAIL_ROWS = 30
PNL_FILES = {
    "eod_equity": ("eod_equity.csv", ("date", "equity", "change_usd"), EOD_MAX_ROWS),
    # scores.csv is kept WHOLE too since 2026-11-18: `auction_hold_pnl_usd` feeds
    # a cumulative figure (orient's "modelled at the close"), and a cumulative
    # figure on a 30-row tail is a different number under the same name.
    "scores": ("scores.csv", ("date", "verdict", "alpaca_equity_change_usd",
                              "auction_pnl_usd", "auction_hold_pnl_usd"), EOD_MAX_ROWS),
    "dist": ("distribution_scores.csv", ("date", "auction_pnl_with_distributions_usd"),
             PNL_TAIL_ROWS),
}


def pnl_tails(state_dir, files):
    '''The named columns of each P&L file, picked by the file's OWN header.

    WHY BY HEADER, AND ON THE VM. scores.csv carries per_symbol_json, which
    holds the account's positions (quantt/session/verify.py score_row), and
    this module's rule is that positions never leave the VM. The wanted columns
    are found in the header and only those cells are copied, so no other cell
    of any row is ever put in the reply; a renamed or reordered file is a named
    error, not a value read from the wrong column.

    WHY IT IS WRITTEN LIKE THIS. Its source is sent to the VM as text
    (_PNL_PY) and run there by python3 -I, and the laptop calls it in-process,
    so both machines are read by one code path. Hence: stdlib only, imports
    inside, no annotations, and no double quote, dollar sign, backtick or
    backslash anywhere in it (it sits in a double-quoted shell word; an assert
    below _PNL_PY enforces that).

    files maps key -> (file name, wanted columns, rows kept from the end).
    Per key the result is exactly one of
        {'rows': [[...], ...], 'n_rows': data rows in the file, 'file': name}
        {'absent': name}       the file does not exist
        {'error': text}        it exists and cannot be read as agreed
    A row whose field count differs from the header's is an error naming its
    line, not a skipped row: scores.csv is appended in place, and a half-written
    last line read mid-append must not become a silently shorter series.
    '''
    import collections
    import csv
    import os
    out = {}
    for key, (name, cols, keep) in files.items():
        try:
            fh = open(os.path.join(state_dir, name), newline='', encoding='utf-8')
        except FileNotFoundError:
            out[key] = {'absent': name}
            continue
        except OSError as e:
            out[key] = {'error': name + ': ' + type(e).__name__ + ': ' + str(e)}
            continue
        try:
            with fh:
                rd = csv.reader(fh)
                head = next(rd, None)
                if not head:
                    raise ValueError('empty: no header')
                missing = [c for c in cols if head.count(c) != 1]
                if missing:
                    raise ValueError('header does not name exactly one of each of '
                                     + ', '.join(missing))
                idx = [head.index(c) for c in cols]
                tail = collections.deque(maxlen=keep)
                n = 0
                for row in rd:
                    if not row:
                        continue
                    if len(row) != len(head):
                        raise ValueError('line ' + str(rd.line_num) + ' has ' + str(len(row))
                                         + ' fields for ' + str(len(head)) + ' columns')
                    n += 1
                    tail.append([row[i] for i in idx])
        except (OSError, ValueError, csv.Error) as e:
            out[key] = {'error': name + ': ' + type(e).__name__ + ': ' + str(e)}
            continue
        out[key] = {'rows': list(tail), 'n_rows': n, 'file': name}
    return out


def pnl_readings(raw, where: str) -> dict:
    """`pnl_tails` output (from the VM's reply or the laptop's own call) as one
    reading per file, in this module's three-key convention. The reply crossed
    a wire, so its shape is checked, not trusted: anything else is UNMEASURED
    naming the file."""
    if not isinstance(raw, dict):
        return {"where": where, **{k: _unm(f"{where}: the P&L reply is not an object")
                                   for k in PNL_FILES}}
    out = {"where": where}
    for key, (name, cols, _keep) in PNL_FILES.items():
        r = raw.get(key)
        if not isinstance(r, dict) or len(r) == 0:
            out[key] = _unm(f"{where}/{name}: no reading for it in the reply")
        elif "absent" in r:
            out[key] = _absent(f"no {name} in {where}")
        elif "error" in r:
            out[key] = _unm(f"{where}/{scrub(str(r['error']))}")
        elif (isinstance(r.get("rows"), list) and isinstance(r.get("n_rows"), int)
              and all(isinstance(row, list) and len(row) == len(cols)
                      and all(isinstance(c, str) for c in row) for row in r["rows"])):
            out[key] = _val({"file": name, "columns": list(cols), "rows": r["rows"],
                             "n_rows": r["n_rows"], "where": where})
        else:
            out[key] = _unm(f"{where}/{name}: the reply's rows are not {len(cols)} strings each")
    return out


def _gate(dry_run: dict, auto_armed: dict) -> tuple[str, str]:
    """(ARMED|PER_DAY|DRY|UNMEASURED, why) from the readings gates 1 and 2 use."""
    if UNMEASURED in dry_run:
        return UNMEASURED, f"DRY_RUN {show(dry_run)}"
    d = dry_run.get("value")
    if d != "0":
        return DRY, ("DRY_RUN unset (gate 1: only exactly \"0\" transmits)"
                     if d is None else f"DRY_RUN={d}")
    if UNMEASURED in auto_armed:
        return UNMEASURED, f"DRY_RUN=0 but AUTO_ARMED {show(auto_armed)}"
    if auto_armed.get("value") is True:
        return ARMED, "DRY_RUN=0 + AUTO_ARMED: every decided plan is sent"
    return PER_DAY, ("DRY_RUN=0, no AUTO_ARMED: sends only a plan with a "
                     "recorded per-day approval")


def _arming(dry_run: dict, auto_armed: dict, scheduled: dict) -> tuple[str, str, list]:
    """(state, why, cautions). `scheduled` is a reading of whether the
    scheduler will fire the session job; UNMEASURED there is counted as
    scheduled, because a machine that cannot be measured is never assumed safe.
    """
    gate, why = _gate(dry_run, auto_armed)
    cautions = []
    if scheduled.get("value") is False:
        left = []
        if (dry_run.get("value") == "0"):
            left.append("its files still say DRY_RUN=0")
        if auto_armed.get("value") is True:
            left.append("AUTO_ARMED is still present")
        if left:
            cautions.append(f"scheduler off ({scheduled.get('why')}), but {' and '.join(left)}"
                            f": docs/RUNBOOK.md 8.5 step 1 sets DRY_RUN=1 and removes AUTO_ARMED")
        files = (f"DRY_RUN={_dry_text(dry_run)}, AUTO_ARMED "
                 + (show(auto_armed) if "value" not in auto_armed
                    else "present" if auto_armed["value"] else "absent"))
        return OFF, f"scheduler off ({scheduled.get('why')}); its files say {files}", cautions
    if UNMEASURED in scheduled:
        why += f"; whether the scheduler fires it is {show(scheduled)}, so it counts as scheduled"
    else:
        why += f"; {scheduled.get('why')}"
    return gate, why, cautions


def trading_days_since(date_iso: str | None, today: dt.date | None = None) -> int | None:
    """Trading days after `date_iso` up to and including today, by the NYSE
    calendar. None when the date is missing or unparseable: an age is shown
    only when it was computed."""
    if not date_iso:
        return None
    try:
        d = dt.date.fromisoformat(date_iso)
        from ops.schedule import nyse_calendar as cal
    except (ValueError, ImportError):
        return None
    today = today or dt.date.today()
    n, cur = 0, d
    while cur < today and n < 4000:
        cur += dt.timedelta(days=1)
        if cal.is_trading_day(cur):
            n += 1
    return n


# ----------------------------------------------------------------- laptop --
def _exists(p: Path) -> bool:
    """True/False, raising on anything but "not there" (a permission error is
    a gap, not an absence)."""
    try:
        p.stat()
        return True
    except (FileNotFoundError, NotADirectoryError):
        return False


def _git_tag(run: Run, clone: Path) -> dict:
    if not clone.is_dir():
        return _absent(f"no clone at {clone}")
    cmd = ["git", "-C", str(clone), "describe", "--tags"]
    r, why = _call(run, cmd, LOCAL_TIMEOUT_S)
    if why:
        return _unm(why)
    if r.returncode != 0 or not r.stdout.strip():
        return _unm(f"`{_cmd(cmd)}` exited {r.returncode}: {scrub(r.stderr)}")
    return _val(r.stdout.strip())


def _launchctl_loaded(run: Run) -> dict:
    """{label: {"pid", "last_exit"}} for every job launchd has loaded in this
    GUI session, from `launchctl list` (PID, Status, Label, tab-separated)."""
    r, why = _call(run, ["launchctl", "list"], LOCAL_TIMEOUT_S)
    if why:
        return _unm(why)
    if r.returncode != 0:
        return _unm(f"`launchctl list` exited {r.returncode}: {scrub(r.stderr)}")
    out = {}
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[2] != "Label":
            out[parts[2]] = {"pid": None if parts[0] == "-" else parts[0],
                             "last_exit": parts[1]}
    return _val(out)


_DISABLED_RE = re.compile(r'"([^"]+)"\s*=>\s*(\w+)')


def _launchctl_disabled(run: Run, uid: int) -> dict:
    """{label: True if disabled} from launchd's override database. A label that
    is not listed has no override; then the plist's own `Disabled` key governs
    (launchd's default). macOS has printed both `disabled`/`enabled` and
    `true`/`false` here; any other word is a gap, not a guess."""
    cmd = ["launchctl", "print-disabled", f"gui/{uid}"]
    r, why = _call(run, cmd, LOCAL_TIMEOUT_S)
    if why:
        return _unm(why)
    if r.returncode != 0:
        return _unm(f"`{_cmd(cmd)}` exited {r.returncode}: {scrub(r.stderr)}")
    out = {}
    for label, word in _DISABLED_RE.findall(r.stdout):
        w = word.lower()
        if w in ("disabled", "true"):
            out[label] = True
        elif w in ("enabled", "false"):
            out[label] = False
        else:
            out[label] = None
    return _val(out)


def _read_last_line(p: Path) -> str | None:
    lines = [ln for ln in p.read_text(errors="replace").splitlines() if ln.strip()]
    return lines[-1] if lines else None


def _local_verify(p: Path) -> dict:
    try:
        if not _exists(p):
            return _absent(f"no {p.name} yet")
        last = _read_last_line(p)
    except OSError as e:
        return _unm(f"reading {p}: {type(e).__name__}: {e}")
    return _val(verdict_line(last)) if last else _absent(f"{p.name} is empty")


def _local_equity(p: Path) -> dict:
    try:
        if not _exists(p):
            return _absent(f"no {p.name} yet")
        lines = [ln for ln in p.read_text(errors="replace").splitlines() if ln.strip()]
    except OSError as e:
        return _unm(f"reading {p}: {type(e).__name__}: {e}")
    if not lines:
        return _unm(f"{p} is empty: no header to read columns from")
    return equity_row(lines[0], lines[-1], str(p))


def laptop(home: Path | None = None, run: Run | None = None,
           uid: int | None = None) -> dict:
    """The laptop prod (launchd), read from this machine's files and launchd.

    Paths and labels come from `quantt.deploy.install_prod` (its `Layout` and
    `JOBS`), the code that installs them. `home` and `run` are parameters so
    the tests build a home under tmp_path and fake every command.
    """
    run = run or subprocess.run
    home = Path(home) if home is not None else Path.home()
    uid = os.getuid() if uid is None else uid
    lay = ip.Layout(home)
    out = {"machine": "laptop", "scheduler": "launchd",
           "reproducer": "plistlib on ~/Library/LaunchAgents/com.quantt.alpaca.cef.*.plist"
                         "  ·  launchctl list / print-disabled  ·  git describe --tags",
           "clone": str(lay.prod_dir), "state_dir": str(lay.state_dir)}
    out["tag"] = _git_tag(run, lay.prod_dir)

    loaded = _launchctl_loaded(run)
    disabled = _launchctl_disabled(run, uid)
    jobs = {}
    for job in ip.JOBS:
        plist = lay.plist_path(job)
        j = {"label": job.label, "plist": str(plist)}
        try:
            present = _exists(plist)
            data = plistlib.loads(plist.read_bytes()) if present else None
        except Exception as e:  # unreadable or not a plist: a named gap
            j["dry_run"] = _unm(f"reading {plist}: {type(e).__name__}: {e}")
            jobs[job.log_stem] = j
            continue
        if not present:
            j["dry_run"] = _absent(f"no {plist.name}")
            jobs[job.log_stem] = j
            continue
        env = data.get("EnvironmentVariables") or {}
        j["dry_run"] = _val(env.get("DRY_RUN"))
        j["plist_state_dir"] = env.get("QUANTT_STATE_DIR")
        if UNMEASURED in loaded:
            j["loaded"] = loaded
        else:
            hit = loaded["value"].get(job.label)
            j["loaded"] = _val(hit is not None, **({"last_exit": hit["last_exit"]} if hit else {}))
        if UNMEASURED in disabled:
            j["disabled"] = disabled
        elif job.label in disabled["value"]:
            flag = disabled["value"][job.label]
            j["disabled"] = (_val(flag) if flag is not None else
                             _unm(f"launchctl print-disabled printed an unknown word for {job.label}"))
        else:
            j["disabled"] = _val(data.get("Disabled") is True, source="plist Disabled key")
        jobs[job.log_stem] = j
    out["jobs"] = jobs

    session = jobs.get("session") or {}
    sd = session.get("plist_state_dir")
    if sd and Path(sd) != lay.state_dir:
        out["state_dir_mismatch"] = (f"the session plist runs with QUANTT_STATE_DIR={sd}, "
                                     f"not the installer's {lay.state_dir}")
    try:
        out["auto_armed"] = _val(_exists(lay.state_dir / "AUTO_ARMED"))
    except OSError as e:
        out["auto_armed"] = _unm(f"stat {lay.state_dir / 'AUTO_ARMED'}: {type(e).__name__}: {e}")
    out["verify_last"] = _local_verify(lay.state_dir / "verify.log")
    out["equity"] = _local_equity(lay.state_dir / "equity.csv")
    # The same selector the VM runs, called in-process: file reads only.
    out["pnl"] = pnl_readings(pnl_tails(str(lay.state_dir), PNL_FILES), str(lay.state_dir))

    dry = session.get("dry_run") or _unm("no session job reading")
    out["cautions"] = []
    if "absent" in dry:
        out["arming"], out["arming_why"] = NOT_INSTALLED, f"no session job ({dry['absent']})"
    else:
        out["scheduled"] = _launchd_scheduled(session)
        out["arming"], out["arming_why"], out["cautions"] = _arming(
            dry, out["auto_armed"], out["scheduled"])
    return out


def _launchd_scheduled(job: dict) -> dict:
    """Will launchd fire this job? Loaded: yes. Unloaded and not disabled: yes,
    at the next login (RUNBOOK 8.5 step 1). Unloaded and disabled: no."""
    lo, di = job.get("loaded") or {}, job.get("disabled") or {}
    if lo.get("value") is True:
        return _val(True, why="launchd has the session job loaded")
    if "value" not in lo or "value" not in di:
        return _unm(f"loaded {show(lo)}; disabled {show(di)}")
    if di["value"]:
        return _val(False, why="launchd session job unloaded and disabled")
    return _val(True, why="session job unloaded but not disabled: launchd loads it at the next login")


# --------------------------------------------------------------------- vm --
# Run on the VM as the admin user, who has passwordless sudo; /home/quantt is
# mode 750, so the state reads go through `sudo -n` (never prompt: -n fails
# instead, and the failure is reported). One line per reading:
#   <key> TAB <exit code> TAB <output, tabs/newlines flattened, cut to 400>
# then an END line, so a reply cut short is seen as cut short. Nothing here
# reads /run/quantt, and the Environment line is filtered to DRY_RUN ON THE
# VM, so the key file's path never leaves it.
#
# `qw` is `q` with a wide cut, for the one reading that is a series: the P&L
# files' selected columns as one JSON line (`pnl_tails`, run as the service
# user, which owns the state dir). A reply cut at that width is not JSON and
# reads as UNMEASURED, never as a shorter series.
_REMOTE_TEMPLATE = r"""q() { k=$1; shift; o=$("$@" 2>&1); r=$?; printf '%s\t%s\t%s\n' "$k" "$r" "$(printf '%s' "$o" | tr '\t\n' '  ' | cut -c1-400)"; }
qw() { k=$1; shift; o=$("$@" 2>&1); r=$?; printf '%s\t%s\t%s\n' "$k" "$r" "$(printf '%s' "$o" | tr '\t\n' '  ' | cut -c1-@WIDE@)"; }
S=@STATE@
q @K@tag sudo -n -u @USER@ git -C @PROD@ describe --tags
q @K@load_state systemctl show -p LoadState --value @SESSION@
q @K@dry_run sh -c "systemctl show -p Environment --value @SESSION@ | tr ' ' '\n' | grep '^DRY_RUN=' || true"
q @K@timers systemctl is-active @TIMERS@
q @K@timers_enabled systemctl is-enabled @TIMERS@
q @K@auto_armed sudo -n sh -c "if [ -e $S/AUTO_ARMED ]; then echo present; elif [ -d $S ]; then echo absent; else echo no-state-dir; fi"
q @K@verify sudo -n sh -c "if [ -e $S/verify.log ]; then tail -n1 $S/verify.log; else echo NO-FILE; fi"
q @K@equity_header sudo -n sh -c "if [ -e $S/equity.csv ]; then head -n1 $S/equity.csv; else echo NO-FILE; fi"
q @K@equity_last sudo -n sh -c "if [ -e $S/equity.csv ]; then tail -n1 $S/equity.csv; else echo NO-FILE; fi"
q @K@newest_plan sudo -n python3 -I -c "@PLAN_PY@" "$S"
qw @K@plan_shape sudo -n python3 -I -c "@SHAPE_PY@" "$S"
qw @K@pnl sudo -n -u @USER@ python3 -I -c "@PNL_PY@" "$S"
printf '@K@END\t0\tquantt-prod-state\n'
"""
# The newest day's plan.json, summarised ON the VM to one JSON line (the plan
# holds the account's positions; only counts and verdicts leave the machine).
# `preflight` is the evening pre-flight's verdict (quantt/session/run.py
# PREFLIGHT_WINDOW_SESSIONS, 2026-10-09): ok, warning, unmeasured, or null for
# a plan decided before the pre-flight existed. No `$`, backtick or double
# quote inside: it sits in a double-quoted shell word.
_PLAN_PY = ("import json,os,sys; s=sys.argv[1]; "
            "ds=sorted(d for d in os.listdir(s) if d[:2]=='20' "
            "and os.path.isfile(os.path.join(s,d,'plan.json'))); "
            "d=os.path.join(s,ds[-1]) if ds else None; "
            "p=json.load(open(os.path.join(d,'plan.json'))) if d else None; "
            "f=(p or {}).get('preflight'); "
            "print('NO-PLAN' if p is None else json.dumps({'session_date': p.get('session_date'), "
            "'status': p.get('status'), 'orders': len(p.get('orders') or []), "
            "'sent': os.path.exists(os.path.join(d,'STARTED')), "
            "'preflight': None if f is None else 'unmeasured' if 'unmeasured' in f "
            "else 'ok' if f.get('ok') else 'warning', "
            "'shock_usd': (f or {}).get('shock_usd')}))")
assert not set(_PLAN_PY) & set('$`"'), "the plan summary must survive double quotes"
# The newest plan's SHAPE, again summarised ON the VM: how many names it covers,
# how many are held long and short, their gross and net at the plan's own
# closes, and how many names carry each kind of reason (the sleeve's reason
# string cut at its z-score, its first `|` or its first digit, letters only: `cef band hold`,
# `cef discount`).
# WHY (team lead, 2026-11-18): C4 sent 0 to 3 orders a day on 74 names while the
# core sent about 10 on 13, and the only way to see why was to copy the plan,
# positions and all, off the VM by hand. Counts and totals answer it; no symbol,
# quantity or per-name weight leaves the machine. A held name with no close in
# the plan makes gross and net null, never a partial sum.
# `gross_cap_bound` counts the names whose reason carries the sleeve's own mark
# that the gross cap scaled the book that day (`gmax=1.8000*x0.97`): when it
# does, the sleeve turns every band HOLD into a trade (cef_discount.py, "THE
# BAND'S HOLDS BECOME TRADES WHEN THIS BINDS"), which is why a book at its cap
# sends an order in every name every day.
_SHAPE_PY = """import json, os, sys
s = sys.argv[1]
ds = sorted(d for d in os.listdir(s) if d[:2] == '20'
            and os.path.isfile(os.path.join(s, d, 'plan.json')))
if not ds:
    print('NO-PLAN')
else:
    p = json.load(open(os.path.join(s, ds[-1], 'plan.json')))
    t = p.get('targets') or {}
    c = p.get('closes') or {}
    why = {}
    for v in t.values():
        k = str(v.get('reason') or 'no reason').split(' z=')[0].split('|')[0].split(' gmax')[0]
        k = k[:min([i for i, ch in enumerate(k) if ch.isdigit()] or [len(k)])]
        k = ' '.join(''.join(ch if ch.isalpha() else ' ' for ch in k).split())[:48]
        why[k] = why.get(k, 0) + 1
    held = {k: v['current'] for k, v in t.items() if v.get('current')}
    capped = sum(1 for v in t.values() if '*x' in str(v.get('reason') or '').split('gmax=')[-1].split(' ')[0])
    moves = sum(1 for v in t.values() if v.get('target') != v.get('current'))
    priced = all(isinstance(c.get(k), (int, float)) for k in held)
    eq = p.get('equity')
    print(json.dumps({'session_date': p.get('session_date'), 'names': len(t),
                      'held': len(held), 'long': sum(1 for q in held.values() if q > 0),
                      'short': sum(1 for q in held.values() if q < 0),
                      'target_differs': moves,
                      'gross_cap_bound': capped,
                      'gross_usd': round(sum(abs(q) * c[k] for k, q in held.items()), 2) if priced else None,
                      'net_usd': round(sum(q * c[k] for k, q in held.items()), 2) if priced else None,
                      'equity': eq if isinstance(eq, (int, float)) else None,
                      'why': dict(sorted(why.items()))}, separators=(',', ':')))
"""
assert not set(_SHAPE_PY) & set('$`"\\'), "the plan shape must survive double quotes"
# `pnl_tails` itself, then one call printing compact JSON. PNL_FILES goes in as
# its repr (single-quoted strings, tuples, ints), so the VM selects exactly the
# columns this module names and no others.
_PNL_PY = (inspect.getsource(pnl_tails)
           + "import json, sys\n"
           + f"print(json.dumps(pnl_tails(sys.argv[1], {PNL_FILES!r}), separators=(',', ':')))\n")
assert not set(_PNL_PY) & set('$`"\\'), "the P&L selector must survive double quotes"
# The wide cut: a full EOD_MAX_ROWS series at well under 100 bytes a row, plus
# two 30-row tails, with room. The reply is bounded by the row caps, not by this.
PNL_REPLY_MAX_CHARS = 400_000


def _vm_book(book: str):
    """One VM book's (layout, session job, timers), from the installer's own
    registry (`install_vm.VM_BOOKS`): the units and the state dir are whatever
    `install_vm --book <book>` installs, never names written again here."""
    vb = iv.VM_BOOKS[book]
    return (iv.Layout(Path("/home") / iv.SERVICE_USER, book=book),
            next(j for j in vb.jobs if j.job.log_stem == "session"),
            tuple(j.timer for j in vb.jobs))


def remote_script(book: str = iv.BOOK, prefix: str = "") -> str:
    """The read-only script for one book. `prefix` goes in front of every
    reading's key (and of END), so several books' scripts can be sent in ONE
    ssh call and their replies told apart."""
    lay, sess, timers = _vm_book(book)
    return (_REMOTE_TEMPLATE
            .replace("@PNL_PY@", _PNL_PY)
            .replace("@WIDE@", str(PNL_REPLY_MAX_CHARS))
            .replace("@PLAN_PY@", _PLAN_PY)
            .replace("@SHAPE_PY@", _SHAPE_PY)
            .replace("@K@", prefix)
            .replace("@STATE@", shlex.quote(str(lay.state_dir)))
            .replace("@PROD@", shlex.quote(str(lay.prod_dir)))
            .replace("@USER@", iv.SERVICE_USER)
            .replace("@SESSION@", sess.service)
            .replace("@TIMERS@", " ".join(timers)))


# The core's script, exactly as it was before the other books were added
# (ops/tests/test_prod_state.py pins it), then one script per other VM book
# with its keys prefixed `<book>.`. WHY one call (team lead, 2026-11-18: "make
# the c4 reachable as easily as everything else"): until then C4's verdicts,
# equity and plan could be read only by hand over ssh, so on a day the VM was
# unreachable from a new network nobody could say whether C4 had traded since
# the last copy pulled into the repo. The core's readings come first and END
# before the others start: a reply cut inside another book's part leaves the
# core measured and that book UNMEASURED.
REMOTE_SCRIPT = remote_script()
OTHER_VM_BOOKS = tuple(b for b in iv.VM_BOOKS if b != iv.BOOK)


def vm_script(books: tuple = OTHER_VM_BOOKS) -> str:
    return REMOTE_SCRIPT + "".join(remote_script(b, prefix=f"{b}.") for b in books)


# ------------------------------------------------------- the shadow books --
# The shadow books (team lead 2026-11-09, docs/SYSTEM.md section 5) are SIMULATED
# books: no broker account, no orders, scored nightly on the VM by their own user
# from a clone that follows a branch. These three names are
# `shadow/deploy/install_shadow_vm.sh`'s (SVC_USER, STATE, the timer it writes);
# ops/tests/test_prod_state.py reads that script and fails if they drift apart.
SHADOW_USER = "quantt-shadow"
SHADOW_STATE = f"/home/{SHADOW_USER}/shadow_state"
SHADOW_TIMER = "quantt-shadow.timer"
# Each book's scores.csv, SUMMARISED ON THE VM to counts and sums by its own
# header (`shadow/engine.py` SCORE_FIELDS): sessions by status, the first and last
# date, the summed price-only and total-return P&L over the SCORED rows, and the
# last row's gross. WHY SUMMARISED THERE (team lead 2026-11-18, "add them like
# C4"): aggregates may leave the VM, per-name weights may not (docs/SYSTEM.md
# section 5, 2026-11-03), and a summary cannot carry a weight. A blank total on
# a SCORED row is the engine's own stated gap (no dividend column); it is counted
# in `total_gaps` and the total is then null, never the price line under another
# name. A row that will not parse is an error naming the book and the line.
_SHADOW_PY = """import csv, json, os, sys
s = sys.argv[1]
out = {}
for slug in sorted(os.listdir(s)) if os.path.isdir(s) else []:
    p = os.path.join(s, slug, 'scores.csv')
    if not os.path.isfile(p):
        continue
    try:
        st, price, total, gaps, first, last, gross = {}, 0.0, 0.0, 0, None, None, None
        with open(p, newline='', encoding='utf-8') as fh:
            rd = csv.DictReader(fh)
            need = ('date', 'status', 'pnl_price_usd', 'pnl_total_usd', 'gross')
            miss = [c for c in need if c not in (rd.fieldnames or [])]
            if miss:
                raise ValueError('scores.csv has no column ' + ', '.join(miss))
            for i, r in enumerate(rd, start=2):
                if None in r or None in r.values():
                    raise ValueError('scores.csv line %d is not a whole row' % i)
                st[r['status']] = st.get(r['status'], 0) + 1
                first = first or r['date']
                last, gross = r['date'], r['gross']
                if r['status'] == 'SCORED':
                    price += float(r['pnl_price_usd'])
                    if r['pnl_total_usd'] == '':
                        gaps += 1
                    else:
                        total += float(r['pnl_total_usd'])
        out[slug] = {'status': dict(sorted(st.items())), 'first': first, 'last': last,
                     'pnl_price_usd': round(price, 2),
                     'pnl_total_usd': None if gaps else round(total, 2),
                     'total_gaps': gaps, 'last_gross': gross}
    except Exception as e:
        out[slug] = {'error': type(e).__name__ + ': ' + str(e)[:160]}
print(json.dumps({'state': os.path.isdir(s), 'books': out}, separators=(',', ':')))
"""
assert not set(_SHADOW_PY) & set('$`"\\'), "the shadow summary must survive double quotes"
SHADOW_SCRIPT = (r"""q shadow.timer sh -c "systemctl is-active @T@; systemctl is-enabled @T@"
qw shadow.books sudo -n -u @U@ python3 -I -c "@PY@" @S@
printf 'shadow.END\t0\tquantt-prod-state\n'
""".replace("@PY@", _SHADOW_PY).replace("@T@", SHADOW_TIMER)
   .replace("@U@", SHADOW_USER).replace("@S@", shlex.quote(SHADOW_STATE)))


def _shadow_from_readings(got: dict, alias: str) -> dict:
    """The shadow books' reading. Never part of the prod verdict: nothing here
    can send an order, so there is nothing to arm."""
    where = f"{alias}:{SHADOW_STATE}"
    out = {"where": where, "label": "SIMULATED"}
    if "shadow.END" not in got:
        return {**out, UNMEASURED: f"ssh {alias}: the reply has no shadow.END line, so the "
                                   f"shadow reading was cut short or never ran"}
    rc, v = got.get("shadow.timer", (None, None))
    words = (v or "").split()
    out["timer"] = (_val({"active": words[0], "enabled": words[1]}) if len(words) == 2 else
                    _unm(f"`systemctl is-active/is-enabled {SHADOW_TIMER}` exited {rc}: {scrub(v or '')}"))
    rc, v = got.get("shadow.books", (None, None))
    if rc != 0 or not v:
        out["books"] = _unm(f"`sudo -n -u {SHADOW_USER} python3` summary exited {rc}: {scrub(v or '')}")
        return out
    try:
        raw = json.loads(v)
    except json.JSONDecodeError:
        out["books"] = _unm(f"the shadow summary ({len(v)} chars) is not JSON: {scrub(v)[:120]}")
        return out
    if not isinstance(raw, dict) or not isinstance(raw.get("books"), dict):
        out["books"] = _unm("the shadow summary is not the expected object")
    elif raw.get("state") is not True:
        out["books"] = _absent(f"no {SHADOW_STATE} on the VM")
    else:
        out["books"] = _val({k: ({UNMEASURED: f"{where}/{k}/{scrub(str(b['error']))}"}
                                 if isinstance(b, dict) and "error" in b else b)
                             for k, b in raw["books"].items()})
    return out


def shadow_lines(sh: dict | None) -> list:
    """(label, text) pairs for the renderer: one line per shadow book."""
    if not isinstance(sh, dict):
        return []
    head = "VM shadow books  (SIMULATED)"
    if UNMEASURED in sh:
        return [(head, f"UNMEASURED — {sh[UNMEASURED]}")]
    t = sh.get("timer") or {}
    lines = [(head, (f"{SHADOW_TIMER} {t['value']['active']}/{t['value']['enabled']}" if "value" in t
                     else f"timer {show(t)}") + "; no broker account, no orders; price-only "
                     "P&L on each book's own notional, total return beside it")]
    b = sh.get("books") or {}
    if "value" not in b:
        return lines + [("  books", show(b))]
    if not b["value"]:
        return lines + [("  books", "none has a scores.csv yet")]
    for slug, r in b["value"].items():
        if UNMEASURED in r:
            lines.append((f"  {slug}", f"UNMEASURED — {r[UNMEASURED]}")); continue
        st = r.get("status") or {}
        tot = r.get("pnl_total_usd")
        lines.append((f"  {slug}", f"{r.get('first')} to {r.get('last')}: "
                      + ", ".join(f"{n} {k}" for k, n in st.items())
                      + f"; price-only {'-' if r['pnl_price_usd'] < 0 else '+'}${abs(r['pnl_price_usd']):,.2f}"
                      + (f", total return UNMEASURED on {r.get('total_gaps')} scored session(s)"
                         if tot is None else
                         f", total return {'-' if tot < 0 else '+'}${abs(tot):,.2f}")
                      + f"; last gross {r.get('last_gross')}"))
    return lines


def ssh_alias_present(alias: str, config: Path) -> bool:
    """Is there a `Host` line naming exactly this alias? Patterns are not
    expanded: the runbook sets the alias up by name, and a wildcard that
    happened to match would send this somewhere nobody chose."""
    for line in config.read_text(errors="replace").splitlines():
        m = re.match(r"^\s*Host\s+(.+?)\s*$", line, re.I)
        if m and alias in m.group(1).split():
            return True
    return False


def vm_unmeasured(why: str, alias: str = VM_ALIAS) -> dict:
    return {"machine": "vm", "scheduler": "systemd", "alias": alias,
            UNMEASURED: why, "arming": UNMEASURED, "arming_why": why, "cautions": []}


def vm(alias: str = VM_ALIAS, ssh_config: Path | None = None,
       timeout: float = VM_TIMEOUT_S, run: Run | None = None,
       books: tuple = OTHER_VM_BOOKS, shadow: bool = True) -> dict:
    """The VM prod (systemd), read over ONE ssh call with a hard time budget.

    Only when `~/.ssh/config` names the alias: without it there is no
    sanctioned way to reach the VM, and guessing an address is out (the repo is
    public). BatchMode: a key that needs a passphrase or an unknown host key
    fails instead of prompting, because a prompt inside a hook hangs a session.

    Refuses under netguard. ssh is a child process, so the test harness's
    socket guard cannot see it (`conftest.py`); a test that reached this with
    the real `subprocess.run` would open a real connection to the VM. Tests
    pass a fake `run`, and only then does this proceed under the guard.
    """
    if run is None:
        from ops import netguard
        if netguard.is_active():
            return vm_unmeasured("netguard is active in this process (a test run): "
                                 "no ssh to the VM; pass a fake `run`", alias)
    run = run or subprocess.run
    config = ssh_config if ssh_config is not None else Path.home() / ".ssh" / "config"
    try:
        if not _exists(config):
            return vm_unmeasured(f"no {config}, so no `Host {alias}` alias to reach the VM by")
        if not ssh_alias_present(alias, config):
            return vm_unmeasured(f"{config} has no `Host {alias}`")
    except OSError as e:
        return vm_unmeasured(f"reading {config}: {type(e).__name__}: {e}")

    cmd = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT_S}",
           alias, "sh -s"]
    r, why = _call(run, cmd, timeout, input=vm_script(books) + (SHADOW_SCRIPT if shadow else ""))
    if why:
        return vm_unmeasured(why, alias)
    if r.returncode == 255:
        return vm_unmeasured(f"ssh {alias} failed (exit 255): {scrub(r.stderr)}")
    got = {}
    for line in r.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3 and re.fullmatch(r"-?\d+", parts[1]):
            got[parts[0]] = (int(parts[1]), parts[2].strip())
    if "END" not in got:
        return vm_unmeasured(f"ssh {alias} exited {r.returncode} and its reply was cut short "
                             f"(no END line; {len(got)} reading(s)): {scrub(r.stderr)}")
    out = _vm_from_readings(got, alias)
    # The other books installed on the same VM (their own units, state dir and
    # Alpaca account). Each stands or falls on its own END line.
    out["books"] = {}
    for b in books:
        pre = f"{b}."
        if f"{pre}END" not in got:
            out["books"][b] = {**vm_unmeasured(
                f"ssh {alias}: the reply has no {pre}END line, so book {b}'s readings "
                f"were cut short or never ran: {scrub(r.stderr)}", alias), "book": b}
        else:
            out["books"][b] = _vm_from_readings(
                {k[len(pre):]: v for k, v in got.items() if k.startswith(pre)}, alias, b)
    if shadow:
        out["shadow"] = _shadow_from_readings(got, alias)
    return out


def _vm_from_readings(got: dict, alias: str, book: str = iv.BOOK) -> dict:
    lay, sess, timers = _vm_book(book)
    out = {"machine": "vm", "scheduler": "systemd", "alias": alias, "book": book,
           "reproducer": f"ssh -o BatchMode=yes -o ConnectTimeout={SSH_CONNECT_TIMEOUT_S} "
                         f"{alias} 'sh -s' < ops.prod_state.REMOTE_SCRIPT",
           "clone": str(lay.prod_dir), "state_dir": str(lay.state_dir)}

    def reading(key: str):
        return got.get(key, (None, None))

    rc, v = reading("tag")
    out["tag"] = (_val(v) if rc == 0 and v else
                  _unm(f"`sudo -u {iv.SERVICE_USER} git -C {lay.prod_dir} describe --tags`"
                       f" exited {rc}: {scrub(v or '')}"))

    rc, v = reading("load_state")
    if rc != 0 or not v:
        installed = _unm(f"`systemctl show -p LoadState {sess.service}` exited {rc}: {scrub(v or '')}")
    else:
        installed = _val(v == "loaded", load_state=v)
    out["session_unit"] = installed

    rc, v = reading("dry_run")
    if rc != 0:
        dry = _unm(f"`systemctl show -p Environment {sess.service}` exited {rc}: {scrub(v or '')}")
    else:
        vals = [t.split("=", 1)[1] for t in (v or "").split() if t.startswith("DRY_RUN=")]
        dry = (_val(None) if not vals else _val(vals[0]) if len(vals) == 1 else
               _unm(f"systemd reports {len(vals)} DRY_RUN assignments: {vals}"))
    out["dry_run"] = dry

    # is-active / is-enabled print one word per unit, in argument order, and
    # exit non-zero when any unit is not active/enabled; the words are the data.
    for key, verb in (("timers", "is-active"), ("timers_enabled", "is-enabled")):
        rc, v = reading(key)
        words = (v or "").split()
        out[key] = (_val(dict(zip(timers, words)))
                    if rc is not None and len(words) == len(timers) else
                    _unm(f"`systemctl {verb} {' '.join(timers)}` exited {rc}: {scrub(v or '')}"))

    rc, v = reading("auto_armed")
    out["auto_armed"] = ({"present": _val(True), "absent": _val(False),
                          "no-state-dir": _val(False, note=f"no {lay.state_dir}")}.get(v)
                         if rc == 0 and v in ("present", "absent", "no-state-dir") else
                         _unm(f"`sudo -n test -e {lay.state_dir}/AUTO_ARMED` exited {rc}: {scrub(v or '')}"))

    rc, v = reading("verify")
    out["verify_last"] = (_absent("no verify.log yet") if rc == 0 and v == "NO-FILE" else
                          _val(verdict_line(v)) if rc == 0 and v else
                          _absent("verify.log is empty") if rc == 0 else
                          _unm(f"`sudo -n tail -n1 {lay.state_dir}/verify.log` exited {rc}: {scrub(v or '')}"))

    rh, hv = reading("equity_header")
    rl, lv = reading("equity_last")
    where = f"{alias}:{lay.state_dir}/equity.csv"
    if rh == 0 and hv == "NO-FILE":
        out["equity"] = _absent("no equity.csv yet")
    elif rh == 0 and rl == 0 and hv:
        out["equity"] = equity_row(hv, lv or "", where)
    else:
        out["equity"] = _unm(f"`sudo -n head/tail {lay.state_dir}/equity.csv` exited "
                             f"{rh}/{rl}: {scrub(hv or lv or '')}")

    rc, v = reading("newest_plan")
    if rc == 0 and v == "NO-PLAN":
        out["newest_plan"] = _absent("no plan.json in any day directory yet")
    elif rc == 0 and v:
        try:
            out["newest_plan"] = _val(json.loads(v))
        except json.JSONDecodeError:
            out["newest_plan"] = _unm(f"the newest plan summary is not JSON: {scrub(v)[:120]}")
    else:
        out["newest_plan"] = _unm(f"`sudo -n python3` plan summary exited {rc}: {scrub(v or '')}")

    rc, v = reading("plan_shape")
    if rc == 0 and v == "NO-PLAN":
        out["plan_shape"] = _absent("no plan.json in any day directory yet")
    elif rc == 0 and v:
        try:
            out["plan_shape"] = _val(json.loads(v))
        except json.JSONDecodeError:
            out["plan_shape"] = _unm(f"the plan shape is not JSON: {scrub(v)[:120]}")
    else:
        out["plan_shape"] = _unm(f"`sudo -n python3` plan shape exited {rc}: {scrub(v or '')}")

    rc, v = reading("pnl")
    where = f"{alias}:{lay.state_dir}"
    why = None
    if rc is None:
        why = "no pnl line in the reply"
    elif rc != 0 or not v:
        why = f"`sudo -n -u {iv.SERVICE_USER} python3` P&L selector exited {rc}: {scrub(v or '')}"
    else:
        try:
            out["pnl"] = pnl_readings(json.loads(v), where)
        except json.JSONDecodeError:
            why = (f"the P&L reply ({len(v)} chars) is not JSON"
                   + (" and was cut at the reply width" if len(v) >= PNL_REPLY_MAX_CHARS else "")
                   + f": {scrub(v)[:120]}")
    if why:
        out["pnl"] = {"where": where, **{k: _unm(f"{where}: {why}") for k in PNL_FILES}}

    out["cautions"] = []
    if UNMEASURED in installed:
        out["arming"], out["arming_why"] = UNMEASURED, show(installed)
    elif installed["value"] is not True:
        out["arming"], out["arming_why"] = (NOT_INSTALLED,
                                            f"{sess.service} LoadState={installed['load_state']}")
    else:
        out["scheduled"] = _systemd_scheduled(out["timers"], out["timers_enabled"], sess.timer)
        out["arming"], out["arming_why"], out["cautions"] = _arming(
            dry, out["auto_armed"], out["scheduled"])
    np_ = out["newest_plan"].get("value") or {}
    if np_.get("preflight") == "warning" and not np_.get("sent"):
        out["cautions"] = list(out["cautions"]) + [
            f"VM {book} plan for {np_.get('session_date')}: PRE-FLIGHT WARNING -- a day as bad as the "
            f"worst of the last year (${np_.get('shock_usd')}) would get its send refused or "
            f"scaled; the detail is in its plan.json and the session log"]
    return out


# `systemctl is-enabled` words that mean the timer starts again at boot, and
# those that mean it does not (systemctl(1)). Any other word is a gap.
_ENABLED_WORDS = frozenset({"enabled", "enabled-runtime", "alias", "indirect",
                            "generated", "linked", "linked-runtime"})
_NOT_ENABLED_WORDS = frozenset({"disabled", "masked", "masked-runtime", "static"})


def _systemd_scheduled(active: dict, enabled: dict, timer: str | None = None) -> dict:
    """Will systemd fire the session job? Its timer active: yes. Stopped but
    enabled: yes, at the next boot (RUNBOOK 8.5 step 2 only stops them).
    Inactive and not enabled: no. `timer` is the book's own session timer (the
    core's by default): read against the core's, another book's timers are a
    dict that never holds the key, and it printed as UNMEASURED."""
    t = timer or _VM_SESSION.timer
    a = (active.get("value") or {}).get(t)
    if a == "active":
        return _val(True, why=f"{t} active")
    e = (enabled.get("value") or {}).get(t)
    if a is None or e is None:
        return _unm(f"{t} is-active {show(active) if a is None else a}; "
                    f"is-enabled {show(enabled) if e is None else e}")
    if e in _ENABLED_WORDS:
        return _val(True, why=f"{t} {a} but {e}: it starts again at boot")
    if e in _NOT_ENABLED_WORDS:
        return _val(False, why=f"{t} {a} and {e}")
    return _unm(f"{t} is-enabled printed {e!r}, a word this reader does not know")


# ---------------------------------------------------------------- verdict --
NAMES = {"laptop": "the laptop", "vm": "the VM"}
WORDS = {ARMED: "ARMED", PER_DAY: "armed for a per-day approval only", DRY: "DRY",
         OFF: "OFF", NOT_INSTALLED: "not installed", UNMEASURED: "UNMEASURED"}


def verdict(machines: dict) -> dict:
    """Which machine is prod, from the per-machine arming states.

    prod is the one machine whose scheduler fires the session job with
    DRY_RUN=0. Two is the doubled-book hazard and gets a WARNING; none means
    nothing is sent. Live equity is the prod machine's last equity.csv row, and
    only that: another machine's row is a different ledger of the same account
    (a shadow's, or the laptop's after cut-over), so it is shown under that
    machine, not here. Cautions (an OFF machine whose files would arm it if
    re-enabled) are collected from every machine and always shown.
    """
    hot = {n: m["arming"] for n, m in machines.items() if m.get("arming") in HOT}
    unknown = [n for n, m in machines.items() if m.get("arming") == UNMEASURED]
    out = {"hot": hot, "unmeasured": unknown, "prod": None, "warning": None,
           "equity": None,
           "cautions": [f"{n}: {c}" for n, m in machines.items() for c in m.get("cautions") or []]}
    if len(hot) >= 2:
        both = ", ".join(f"{n} {WORDS[a]}" for n, a in hot.items())
        out["warning"] = (f"WARNING: TWO ARMED SCHEDULERS ON ONE ALPACA ACCOUNT ({both}). "
                          f"Each passes gate 6 on its own state dir, so both send: the "
                          f"doubled-book hazard (CLAUDE.md order-path rule 2). Disarm one "
                          f"now (docs/RUNBOOK.md 8.5).")
        out["line"] = out["warning"]
        return out
    if len(hot) == 1:
        (name, state), = hot.items()
        out["prod"] = name
        out["equity"] = machines[name].get("equity")
        line = (f"prod is {NAMES.get(name, name)}: {WORDS[state]} "
                f"({machines[name].get('arming_why')})")
        if unknown:
            line += (f"; {', '.join(unknown)} UNMEASURED, so a second armed scheduler "
                     f"is not ruled out")
        out["line"] = line
        return out
    states = ", ".join(f"{n} {WORDS.get(m.get('arming'), m.get('arming'))}"
                       for n, m in machines.items())
    out["line"] = (f"no machine is measured armed ({states}): nothing is sent"
                   + (f" -- but {', '.join(unknown)} is UNMEASURED, so that is not established"
                      if unknown else ""))
    return out


def measure(include_vm: bool = True, vm_timeout: float = VM_TIMEOUT_S,
            run: Run | None = None, home: Path | None = None,
            ssh_config: Path | None = None, vm_skip_reason: str | None = None) -> dict:
    machines = {"laptop": laptop(home=home, run=run)}
    machines["vm"] = (vm(timeout=vm_timeout, run=run, ssh_config=ssh_config) if include_vm
                      else vm_unmeasured(vm_skip_reason or "not measured in this call "
                                         "(run python3 -m ops.orient)"))
    return {"reproducer": "python3 -m ops.prod_state",
            "measured_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "machines": machines, "verdict": verdict(machines)}


# ----------------------------------------------------------------- render --
def equity_text(r: dict | None) -> str:
    """`$101,181.06 — snapshot read after the 2026-10-07 close (<source>, read ...)`.

    A SNAPSHOT, not the P&L of record (team lead, 2026-10-19): equity.csv is
    Alpaca's account equity read after the close, and its marks can move after
    the close (`docs/REFERENCES.md` §12an). The official end-of-day series is
    eod_equity.csv, shown in orient's PNL section."""
    if not isinstance(r, dict) or "value" not in r:
        return show(r)
    e = r["value"]
    try:
        amount = f"${float(e['equity']):,.2f}"
    except (TypeError, ValueError):
        amount = f"{e['equity']!r} (not a number)"
    age = trading_days_since(e.get("date"))
    return (f"{amount} — snapshot read after the {e['date']} close (Alpaca account, "
            f"{e['source']}" + (f", read {e['read_at_utc']}" if e.get("read_at_utc") else "")
            + ")" + (f", {age} trading day(s) ago" if age is not None else "")
            + "; official end-of-day P&L: PNL")


def verify_text(r: dict | None) -> str:
    if not isinstance(r, dict) or "value" not in r:
        return show(r)
    v = r["value"]
    age = trading_days_since(v.get("date"))
    return (v["line"][:150] + ("…" if len(v["line"]) > 150 else "")
            + (f"   ({age} trading day(s) ago)" if age is not None else ""))


def plan_text(r: dict | None) -> str:
    """`2026-10-12: decided, 4 order(s), not sent yet; pre-flight ok (worst-day shock $2,074.61)`."""
    if not isinstance(r, dict) or "value" not in r:
        return show(r)
    n = r["value"]
    pf = n.get("preflight")
    pf_text = ("pre-flight not run (decided before it existed)" if pf is None else
               f"pre-flight {'WARNING' if pf == 'warning' else pf}"
               + (f" (worst-day shock ${n['shock_usd']:,.2f})"
                  if isinstance(n.get("shock_usd"), (int, float)) else ""))
    return (f"{n.get('session_date')}: {n.get('status')}, {n.get('orders')} order(s), "
            f"{'sent' if n.get('sent') else 'not sent yet'}; {pf_text}")


def shape_text(r: dict | None) -> str:
    """`13 names, 12 held (6 long, 6 short); gross $178,000.00 = 1.78x equity, net
    -$1,200.00; 9 target(s) differ from holdings; reasons: cef band hold 4, cef discount 9`."""
    if not isinstance(r, dict) or "value" not in r:
        return show(r)
    n = r["value"]
    g, net, eq = n.get("gross_usd"), n.get("net_usd"), n.get("equity")
    money = ("gross and net UNMEASURED (a held name has no close in the plan)"
             if g is None or net is None else
             f"gross ${g:,.2f}" + (f" = {g / eq:.2f}x the plan's equity" if eq else "")
             + f", net {'-' if net < 0 else '+'}${abs(net):,.2f}")
    why = ", ".join(f"{k} {c}" for k, c in (n.get("why") or {}).items()) or "none"
    cap = n.get("gross_cap_bound")
    cap_text = ("" if cap is None else "; gross cap not binding" if not cap else
                f"; GROSS CAP BINDING on {cap} name(s), so no band hold survives")
    return (f"{n.get('names')} name(s), {n.get('held')} held ({n.get('long')} long, "
            f"{n.get('short')} short); {money}; {n.get('target_differs')} target(s) differ "
            f"from holdings{cap_text}; reasons: {why}")


def pnl_files_text(r: dict | None) -> str:
    """`eod_equity.csv none · scores.csv 16 row(s), to 2026-10-16 · ...`: which
    P&L files a machine holds. The figures are orient's PNL section, from the
    prod machine only; this line shows each machine's files exist and parse."""
    if not isinstance(r, dict):
        return "UNMEASURED — no reading"
    parts = []
    for key, (name, _cols, _keep) in PNL_FILES.items():
        x = r.get(key) or {}
        if "value" in x:
            rows = x["value"]["rows"]
            parts.append(f"{name} {x['value']['n_rows']} row(s)"
                         + (f", to {rows[-1][0]}" if rows else ""))
        elif "absent" in x:
            parts.append(f"{name} none")
        else:
            parts.append(f"{name} UNMEASURED")
    return " · ".join(parts)


def render_lines(d: dict, p: Callable[[str, str], None]) -> None:
    """Print the PROD block through `p(label, value)` (orient's `_p`)."""
    ms = d["machines"]
    lap, v = ms["laptop"], ms["vm"]

    p("laptop  (launchd)", f"{WORDS.get(lap['arming'], lap['arming'])} — {lap['arming_why']}")
    p("  clone", f"{lap['clone']} at {show(lap['tag'])}")
    jobs = lap.get("jobs") or {}
    p("  DRY_RUN in each plist", ", ".join(f"{s} {_dry_text(j.get('dry_run'))}"
                                           for s, j in jobs.items()))
    p("  launchd", ", ".join(_job_state(s, j) for s, j in jobs.items()))
    p("  AUTO_ARMED", _bool_text(lap.get("auto_armed"), f"{lap['state_dir']}/AUTO_ARMED"))
    if lap.get("state_dir_mismatch"):
        p("  WARNING", lap["state_dir_mismatch"])
    p("  last verdict", verify_text(lap.get("verify_last")))
    p("  equity.csv last row", equity_text(lap.get("equity")))
    p("  P&L files", pnl_files_text(lap.get("pnl")))

    _render_vm_book(p, v, f"VM  (systemd, ssh {v.get('alias')})")
    # The other books on the VM: each has its own units, gate files and Alpaca
    # account, so each is armed or not on its own. They are not part of the
    # one-prod verdict below, which is about two SCHEDULERS for the core account.
    for name, b in (v.get("books") or {}).items():
        _render_vm_book(p, b, f"VM book {name}", clone=False)
        for c in b.get("cautions") or []:
            p("  caution", c)
    for label, text in shadow_lines(v.get("shadow")):
        p(label, text)
    vd = d["verdict"]
    for c in vd.get("cautions") or []:
        p("  caution", c)
    p("!!" if vd.get("warning") else "=>", vd["line"])


def _render_vm_book(p, v: dict, label: str, clone: bool = True) -> None:
    """One book's VM lines. `clone` is off for the other books: the VM has ONE
    prod clone at ONE tag for every book (install_vm), printed with the core."""
    p(label, f"{WORDS.get(v['arming'], v['arming'])} — {v['arming_why']}")
    if UNMEASURED in v:
        return
    if clone:
        p("  clone", f"{v['clone']} at {show(v['tag'])}")
    p("  DRY_RUN (systemd, loaded)", _dry_text(v.get("dry_run")))
    ta, te = v.get("timers") or {}, v.get("timers_enabled") or {}
    if "value" in ta and "value" in te:
        p("  timers (active/enabled)", ", ".join(f"{_stem(k)} {a}/{te['value'].get(k)}"
                                                 for k, a in ta["value"].items()))
    else:
        p("  timers", f"is-active {show(ta)}; is-enabled {show(te)}")
    p("  AUTO_ARMED", _bool_text(v.get("auto_armed"), f"{v['state_dir']}/AUTO_ARMED"))
    p("  last verdict", verify_text(v.get("verify_last")))
    p("  equity.csv last row", equity_text(v.get("equity")))
    p("  P&L files", pnl_files_text(v.get("pnl")))
    p("  newest plan", plan_text(v.get("newest_plan")))
    p("  plan shape", shape_text(v.get("plan_shape")))


def _stem(unit: str) -> str:
    """quantt-cef-session.timer -> session."""
    return unit.rsplit(".", 1)[0].rsplit("-", 1)[-1]


def _dry_text(r: dict | None) -> str:
    if not isinstance(r, dict) or "value" not in r:
        return show(r)
    return "unset" if r["value"] is None else str(r["value"])


def _bool_text(r: dict | None, path: str) -> str:
    if not isinstance(r, dict) or "value" not in r:
        return show(r)
    return ("present" if r["value"] else "absent") + f"  ({path})" + (
        f" — {r['note']}" if r.get("note") else "")


def _job_state(stem: str, j: dict) -> str:
    if "absent" in (j.get("dry_run") or {}):
        return f"{stem} not installed"
    lo, di = j.get("loaded") or {}, j.get("disabled") or {}
    s = stem + " " + ("UNMEASURED" if "value" not in lo else
                      ("loaded" + (f" (last exit {lo['last_exit']})" if lo.get("last_exit") is not None else ""))
                      if lo["value"] else "NOT loaded")
    if "value" not in di:
        s += ", disabled UNMEASURED"
    elif di["value"]:
        s += ", DISABLED"
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-vm", action="store_true", help="skip the ssh call")
    a = ap.parse_args(argv)
    d = measure(include_vm=not a.no_vm)
    if a.json:
        json.dump(d, sys.stdout, indent=2, default=str)
        print()
        return 0

    def p(label, value=""):
        print(f"  {label:<30}{value}" if len(label) <= 30 else f"  {label}\n  {'':<30}{value}")
    print(f"PROD — measured {d['measured_at']}")
    render_lines(d, p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
