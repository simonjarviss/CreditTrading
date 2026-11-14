"""Install (or update) the CEF book on the prod VM at a release tag, as systemd units.

    qi() { sudo env PYTHONPATH=/home/quantt/prod/quantt-alpaca \\
             /home/quantt/venv/bin/python -B -P -m quantt.deploy.install_vm "$@"; }
    qi --tag T --vault V --seed-from DIR          # dry run
    qi --tag T --vault V --seed-from DIR --apply
    qi --tag T --vault V --apply --enable

The installer is imported from the prod clone through PYTHONPATH, because
/home/quantt is mode 750 and the admin user cannot `cd` into it
(docs/RUNBOOK.md section 8.3). `-P` keeps the caller's working directory
off sys.path, so root never imports a module planted there.

WHY THIS EXISTS
---------------
From 2026-09-30 to 10-07 the laptop missed the send on 3 of 6 trading days,
because it was asleep or offline (verify.log, 10-02, 10-05 and 10-06). On
2026-10-07 the team lead moved prod to a cloud VM: Azure for Students, Ubuntu
24.04. This module is install_prod's twin for Linux. The rule is the same: prod
is THIS REPOSITORY AT A TAG AND NOTHING ELSE. So are the jobs, the commands, the
environment and the times; only the scheduler differs (systemd timers, not
launchd). It is a new module rather than an edit to install_prod (RUNBOOK section 8).
It IMPORTS install_prod's JOBS, seed lists, expected_env and timezone reader, so
the two schedulers cannot drift apart without a test failing.

WHERE IT RUNS, AND AS WHOM
--------------------------
On the VM, as root, because it writes /etc/systemd/system and runs systemctl.
It runs with the venv interpreter, the prod clone on PYTHONPATH, and `-B`. Without `-B`,
root would write __pycache__ into the quantt user's tree, leaving root-owned
files there. Every git command runs as the `quantt` user
(`runuser -u quantt --`): git refuses a repository another user owns
("dubious ownership"), and prod's files must stay quantt's. The clone itself is
made once, by quantt/deploy/vm/bootstrap.sh.

TEMPLATES AT THE TAG
--------------------
The units are rendered from templates read AT THE TAG (`git show`). Each is
then parsed and checked, key by key, against what this module expects:

  * the command and environment from install_prod.expected_env;
  * the schedule from `oncalendar(job.schedule)`.

An installer older than the release refuses a release whose units changed,
rather than installing its own idea of them. In that case, check out the tag
as quantt and run the installer again.

DRY RUN BY DEFAULT
------------------
Without `--apply`, it runs every check and prints the steps and the rendered
units. The one write it makes is `git fetch --tags` into the clone's .git,
which changes no checked-out file, no unit and no state. `--apply` writes the
units and runs `systemctl daemon-reload`, after which systemd runs the new
definitions. So a re-install without `--armed` disarms at once. That differs
from launchd, where a written plist is ignored until it is reloaded: here the
reload is part of every apply. `--enable` (only with `--apply`) also enables and
starts the timers and the key service. Enabling is a separate act on purpose,
because enabled timers are what trade.

Arming takes two things: `--armed` (DRY_RUN=0 in the units) and AUTO_ARMED in
the state dir (docs/RUNNER.md gate 2). AUTO_ARMED is the team lead's act; this
module never writes it.

THE TIMERS ARE STOPPED FOR THE RUN (release-check NO-GO, 2026-10-08)
--------------------------------------------------------------------
Checking `is-active` at the right moments is not enough. A 15:52 firing that
lands between the last look and daemon-reload starts the OLD unit, say
DRY_RUN=0, and with AUTO_ARMED it sends, while a disarm run would report
DRY_RUN=1 loaded. So `--apply` runs in this order:

  1. stop every quantt-cef timer that is running;
  2. check that no job is running or QUEUED. A queued start reads `is-active`
     inactive, so the check uses ActiveState and Job (measured, see the parser
     comment). The key service `activating` also counts;
  3. checkout, write, daemon-reload, confirm_loaded;
  4. check again. A job found now exits 3 (EXIT_JOB_DURING_INSTALL), naming
     the job, its MainPID and the DRY_RUN it started with, read from /proc and
     never guessed;
  5. restart quantt-secret.service and confirm it is active and the key file is
     a 0600 file owned by quantt (stat only). A oneshot with RemainAfterExit is
     otherwise never re-run, so a changed --vault or rotated keys would leave
     the old keys in /run/quantt while the run reported success (release-check
     #2). It is done here, while no job can run, because the restart removes and
     re-creates /run/quantt;
  6. start every ENABLED timer, plus any that was running, or enable them all
     with `--enable`, then READ BACK that each is active, and refuse if one is
     not. The end state is set by enablement, not by what happened to be
     running. Otherwise a re-run after a refusal that had stopped the timers
     would exit 0 with all three still stopped (release-check #2).

Restarting DOES replay a slot missed while the timers were stopped. Measured
on the VM, 2026-10-08 [V]: an ENABLED Persistent=false timer, stopped and
restarted within one boot across a missed slot, fires at once on the restart.
(This corrects an earlier note in this file, which said restarting did not
replay; parser comment (b).) So an install that spans 15:52/15:55 (12:52/12:55
on an early close) would replay the send slot into a late, partial send. To
prevent that, the installer refuses at planning on a weekday inside 15:30-16:00
or 12:30-13:00 ET (PLAN_REFUSE_RANGES_ET, a superset of the runner's
LATE_LOCAL_RANGES). It refuses the timer restart inside 15:52-16:00 or
12:52-13:00 (RESTART_REFUSE_RANGES_ET, the send window to the close), and checks
the clock again before restarting the timers, leaving them stopped if it is
now inside a window. Other replays are harmless: a replayed :00/:30 session
idles outside its slots, a replayed collect is a collect, a replayed 17:30
verify writes the day's line, and a replayed 22:00 decide decides once
(DECIDED). Any failure after step 1, a refusal or an unexpected
exception, reads the timers back and reports any that are STOPPED: nothing
trades until the installer is re-run or the timers are started. Planning also
refuses a venv built from a requirements.txt other than the tag's
(REQUIREMENTS_RECORD, written by bootstrap.sh).

TIMEZONE: ONE MECHANISM
-----------------------
The timers' OnCalendar lines carry no zone, so systemd reads them as
system-local time. The installer refuses unless /etc/localtime names
America/New_York (bootstrap.sh sets it). There is no `--accept-timezone`: on a
VM the zone is ours to set, so nothing equivalent needs accepting. The runner's
own ET clock gates are the second guard.

SCHEDULE
--------
* `Persistent=false`: a firing missed while the VM was DOWN never runs at boot
  (systemd.timer(5)). Measured on the VM, 2026-10-08 04:43-04:56 UTC [V]: last
  run 04:44:00, then powered off; slots 04:46-04:54 passed while down; boot at
  04:55:07; next run at the regular 04:56:00. A stop and restart WITHIN one
  boot is different: it replays (see THE TIMERS ARE STOPPED FOR THE RUN).
* A firing that passes WHILE ITS SERVICE IS STILL RUNNING is not dropped.
  MEASURED on the VM, 2026-10-07 (Ubuntu 24.04.4, systemd 255.4-1ubuntu8.17): a
  transient timer firing every minute at :00 (AccuracySec=1s, Persistent=false)
  on a 90-second job started the next run the moment the previous one exited.
  The 23:14:00 firing ran at 23:14:30. For this book that means:
    - the 15:52 send polls its orders until each is final (`_poll_final`). That
      usually ends within seconds; in the worst case it runs to 30 s before the
      close (15:59:30 for a 16:00 close);
    - so the 15:55 firing usually lands INSIDE the window, while the send is
      still running or just after, and then idles on STARTED. In the worst case
      it starts after the window, where the date roll idles it;
    - either way the session must idle on STARTED and the Alpaca-clock send
      window.
  The runner's gates are the ONLY guard on that path, not a second one. The
  test that covers the idle is quantt/session/tests/test_run.py::
  test_late_scheduled_decides_once_then_sends_once. `DeferReactivation=`
  (systemd >= 256) would remove the late start, but Ubuntu 24.04 ships 255.
* `AccuracySec=1s`: systemd's default is 1min, and within that window "the
  expiry time will be placed at a host-specific, randomized" position
  (systemd.timer(5)). That would put a 15:52 firing anywhere up to 15:53.

THE KEY FILE
------------
`quantt-secret.service` (quantt.deploy.boot_secrets) writes /run/quantt/alpaca.env
at boot. The job units declare `Wants=` + `After=` on it, deliberately NOT
`Requires=`. systemd.unit(5): a unit with Requires= "will be stopped (or
restarted) if one of the other units is explicitly stopped (or restarted)".
Rotating the keys (`systemctl restart quantt-secret`) during the 15:52 window
would then kill a send mid-batch. A failed fetch would also stop verify from
starting at all, leaving that day with no verify.log line, and silence must
never read as success. With Wants=, a job whose key file is missing fails
loudly in its own log, and verify records FAIL.

"Once per boot" holds only when the fetch SUCCEEDS. A failed key service is
inactive, so every job start pulls it in again through Wants=. That makes it
self-healing (a role assignment made later starts working on the next firing).
The cost is delay: After= holds the job until the fetch ends, up to about 4
minutes per job start when every request times out. That is IMDS 6 x 10 s plus
82 s of backoff, about 142 s, then about 47 s per secret
(azure_keyvault.IMDS_DELAYS, KEYVAULT_DELAYS, TIMEOUT_S). A 4xx refusal ends
the fetch at once.

WHAT IT NEVER DOES
------------------
* Reads a credential. It knows the vault's NAME only.
* Runs anything quantt cannot already change, with one exception, accepted:
  it runs as root FROM the quantt-writable venv and clone. So quantt (or code
  running as quantt) can make root run code at the next install. The impact is
  low, because quantt already holds the keys and runs the book; the gap is
  noted in docs/RUNBOOK.md section 8.
* Imports quantt.session or any broker code.
* Writes a unit not named quantt-*.
* Writes AUTO_ARMED.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import pwd
import re
import shlex
import stat
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from string import Template
from typing import Callable
from zoneinfo import ZoneInfo

from quantt.deploy import azure_keyvault as akv
from quantt.deploy import install_prod as ip
from quantt.deploy.install_prod import InstallRefused

BOOK = ip.BOOK
REQUIRED_TZ = ip.REQUIRED_TZ
SERVICE_USER = "quantt"
ORIGIN_URL = "https://github.com/quanttqueensu/CreditTrading.git"
UNITS_DIR = Path("/etc/systemd/system")
UNIT_PREFIX = "quantt-"
TEMPLATE_DIR = "quantt/deploy/templates/systemd"

# RuntimeDirectory=quantt in quantt-secret.service creates /run/quantt; the key
# file lives in it. The two must agree, so both come from here.
RUNTIME_DIR = "quantt"
ENV_FILE = Path("/run") / RUNTIME_DIR / "alpaca.env"
SECRET_UNIT = "quantt-secret.service"
SECRET_PROVIDER = "azure-keyvault"
# Key Vault secret name -> variable in the key file. Two secrets because a vault
# secret name allows only 0-9 a-z A-Z '-' (azure_keyvault.SECRET_RE), and the
# portal's value box is a single line. The variable names are
# quantt.broker.alpaca's (env_names("cef")).
SECRET_MAP = (("alpaca-cef-key-id", "ALPACA_CEF_KEY_ID"),
              ("alpaca-cef-secret-key", "ALPACA_CEF_SECRET_KEY"))

# Session exits that are normal outcomes, not failures (quantt/session/run.py:
# NOTHING_TO_SEND 3, PREVIEW 4, IDLE 5, PLANNED 6, DRY 10). REFUSED 11 and FAIL 20
# stay failures. `test_session_success_exits_match_run_py` re-reads run.py.
SESSION_SUCCESS_EXIT = (3, 4, 5, 6, 10)

# Exit codes: 0 done, 2 refused (nothing unsafe happened), 3 a quantt job ran or
# was queued after the reload, which with the timers stopped should be
# impossible, so the run says so loudly instead of reporting success.
EXIT_JOB_DURING_INSTALL = 3

# One install (or bootstrap) at a time (release-check #5). Without it, a disarm
# run could confirm DRY_RUN=1 from systemd and exit 0 while an armed update,
# already in flight, went on to write DRY_RUN=0 and restart the timers: the
# next slot would send after a confirmed halt (CLAUDE.md order-path rule 4).
# An exclusive, non-blocking flock(2) on a root-owned file in /run/lock (tmpfs,
# so a reboot clears it), taken before ANY planning and held until the process
# exits; bootstrap.sh takes the same lock with `flock -n`.
INSTALL_LOCK = Path("/run/lock/quantt-install.lock")


def acquire_install_lock(path: Path) -> int:
    """Take the install lock or raise InstallRefused naming the holder's pid.
    Returns the fd; closing it (or exiting) releases the lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        holder = os.read(fd, 64).decode("utf-8", "replace").strip() or "unknown"
        os.close(fd)
        raise InstallRefused(
            f"another install or bootstrap is running (lock {path}, held by pid "
            f"{holder}). Never run two at once: one could undo the other's disarm. "
            f"Wait for it to finish") from None
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()}\n".encode())
    return fd

# Two windows, weekdays, for a 16:00 and a 13:00 (early) close. Release-check #5
# narrowed the restart window, so fewer days are lost for the same safety.
#   PLAN_REFUSE_RANGES_ET: no install STARTS inside these. They are a superset of
#     the runner's LATE_LOCAL_RANGES (15:40/12:40), and start at 15:30/12:30 so a
#     run, whose key fetch can take about 4 minutes, finishes before the send
#     window (docs/RUNBOOK.md 8.6: "start any --apply before 15:30").
#   RESTART_REFUSE_RANGES_ET: the timers are not RESTARTED inside these. They run
#     from the book's send window start (close - window_minutes_before_close[0]
#     = 15:52/12:52) to the close. A restart there replays a missed 15:52/15:55
#     slot into a late, partial send (M1). A restart in 15:30-15:52 can only
#     replay a :00/:30 session (decide or idle) or a :40 collect, never a send.
# Both are MIRRORED, not imported: the installer never imports quantt.session.
# test_the_windows_cover_the_runners_late_ranges_and_the_books_send_window pins
# them to the runner's ranges and to the book's window.
PLAN_REFUSE_RANGES_ET = ((dt.time(15, 30), dt.time(16, 0)), (dt.time(12, 30), dt.time(13, 0)))
RESTART_REFUSE_RANGES_ET = ((dt.time(15, 52), dt.time(16, 0)), (dt.time(12, 52), dt.time(13, 0)))

# sha256 of the requirements.txt the venv was built from, written by bootstrap.sh
# (and by the RUNBOOK 8.6 dependency step) into the venv directory.
REQUIREMENTS_RECORD = ".quantt-requirements.sha256"

# Every rendered value must match this pattern. It excludes the space (which
# would split ExecStart's argv), '%' (a systemd specifier), '$' (variable
# expansion), quotes and backslashes (systemd's own quoting).
SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9/_.:@+=-]+$")

# launchd numbers weekdays 0..7 with 0 and 7 both Sunday (`man launchd.plist`).
WEEKDAY_NAMES = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
DAY_ORDER = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class VmJob:
    unit: str                  # e.g. quantt-cef-session
    job: ip.Job                # the launchd job it reproduces
    success_exit: tuple = ()

    @property
    def service(self) -> str:
        return f"{self.unit}.service"

    @property
    def timer(self) -> str:
        return f"{self.unit}.timer"


_BY_STEM = {j.log_stem: j for j in ip.JOBS}
VM_JOBS = (
    VmJob(f"quantt-{BOOK}-session", _BY_STEM["session"], SESSION_SUCCESS_EXIT),
    VmJob(f"quantt-{BOOK}-verify", _BY_STEM["verify"]),
    VmJob(f"quantt-{BOOK}-collect", _BY_STEM["collect"]),
)


def template_path(unit_file: str) -> str:
    return f"{TEMPLATE_DIR}/{unit_file}.tmpl"


ALL_UNIT_FILES = (SECRET_UNIT,) + tuple(f for vj in VM_JOBS for f in (vj.service, vj.timer))

# What the units need at the tag, beyond what install_prod requires.
REQUIRED_AT_TAG = ip.REQUIRED_AT_TAG + (
    "quantt/deploy/boot_secrets.py",
    "quantt/deploy/azure_keyvault.py",
    "requirements.txt",
) + tuple(template_path(f) for f in ALL_UNIT_FILES)


# -- books ------------------------------------------------------------------
#
# A SECOND BOOK ON THE SAME VM (C4, CEF trial 52; team lead's fast-track
# 2026-10-28/29, deploy plan row 11). Everything above is the CORE's and is
# unchanged: with no `--book`, or `--book cef`, every unit is rendered from the
# same template with the same values, byte for byte
# (tests/test_install_vm_books.py proves it against 35b429f's installer, read
# from git). `--book c4` installs C4's own units beside them and touches none
# of the core's:
#
#   units      quantt-c4-session/verify/collect .service/.timer and
#              quantt-c4-secret.service, from templates at the tag. The jobs
#              are the core's jobs with `--book c4` (`_book_job`): the same
#              commands, schedule and success exits, derived rather than
#              retyped, so the two cannot drift apart.
#   keys       its own vault secrets, alpaca-c4-key-id / alpaca-c4-secret-key,
#              into its own key file /run/quantt-c4/alpaca.env (RuntimeDirectory
#              quantt-c4), as ALPACA_C4_KEY_ID / _SECRET_KEY: the names
#              quantt.broker.alpaca's env_names("c4") reads. The core's key
#              file never holds C4's keys, nor the other way round. The secrets
#              are the team lead's to create; this module knows their NAMES only.
#   state      /home/quantt/quantt_state/c4 (the collector and the session both
#              refuse a C4 state dir not named c4), its own logs and seed.log.
#   data       data/cef_c4 in the prod clone, seeded only where absent, from
#              `scripts/cef/data_books.py seed-c4` output (`--seed-from`): each
#              panel's sha256 must equal the seed's manifest, and the manifest
#              must name the tag's IGR seed ruling and frozen universe by sha256
#              (team lead 2026-10-29: seed with the IGR ruling).
#   locks      no shared panel lock: C4's refresh is fetch_daily --data-book c4,
#              which locks data/cef_c4/.fetch.lock, never data/cef/.fetch.lock,
#              and each collector locks <its own state dir>/data/.collect.lock.
#              The install lock (INSTALL_LOCK) IS shared: one install at a time.
#   eod_from   REQUIRED, no default (`--eod-from YYYY-MM-DD`): the date C4's
#              paper account was first funded, the team lead's to state. It is
#              rendered into quantt-c4-collect.service as QUANTT_EOD_FROM, which
#              the collector reads (quantt/collect/collect.py, THE C4 BOOK).
#   the clone  ONE prod clone, at ONE tag, for both books (prod is this
#              repository at a tag). `--book c4` NEVER checks out: it refuses
#              unless the clone is already at the tag, so it can never change
#              the code the core runs; install the core at the tag first. The
#              core's install, in turn, refuses to move the clone while any C4
#              timer is enabled or running or a C4 job is busy: a checkout would
#              change the code C4's units run, under them (`_refuse_if_other_books_live`).
#              Disable C4's timers, install the core, then re-install C4 at the
#              same tag.
# Every existing guard holds for C4 as for the core: the late-window refusals
# (_refuse_if_late), the busy checks, the drop-in scans, the stale-venv check,
# DRY_RUN=1 unless `--armed`, and AUTO_ARMED never written.

C4_BOOK = "c4"


def _book_job(job: ip.Job, book: str) -> ip.Job:
    """The core's launchd job with `--book <book>`: same command, schedule and log
    stem. No launchd twin exists for another book (the VM is prod), so the label
    names the book and the plist template is empty: the VM never reads either."""
    args = list(job.args)
    i = args.index("--book")
    if args[i + 1] != BOOK:
        raise InstallRefused(f"{job.label}: expected `--book {BOOK}` in {job.args}")
    args[i + 1] = book
    return ip.Job(job.label.replace(f".{BOOK}.", f".{book}."), "", tuple(args), job.schedule,
                  job.log_stem)


@dataclass(frozen=True)
class VmBook:
    """One book's units, keys, data and checks on the VM (module comment above)."""
    name: str                    # quantt.session BOOKS key, the units' `--book`
    jobs: tuple                  # VmJob, the session first
    secret_unit: str
    runtime_dir: str             # /run/<runtime_dir>, the key file's directory
    secret_map: tuple            # (vault secret name, key file variable)
    required_at_tag: tuple
    data_dir: str                # prod clone's data/<data_dir>
    seed_files: tuple            # copied once, only when absent
    seed_manifest: str | None    # C4: the seed's manifest in --seed-from; None: the core's rule
    seed_checks: tuple           # (manifest key, path at the tag) the manifest must name by sha256
    needs_eod_from: bool         # `--eod-from` required (C4); refused otherwise
    moves_clone: bool            # may check the clone out at the tag (the core only)

    @property
    def env_file(self) -> Path:
        return Path("/run") / self.runtime_dir / "alpaca.env"

    @property
    def unit_files(self) -> tuple:
        return (self.secret_unit,) + tuple(f for vj in self.jobs for f in (vj.service, vj.timer))

    @property
    def timers(self) -> list:
        return [vj.timer for vj in self.jobs]


CORE_VM = VmBook(BOOK, VM_JOBS, SECRET_UNIT, RUNTIME_DIR, SECRET_MAP, REQUIRED_AT_TAG,
                 "cef", ip.SEED_FILES + ip.SEED_SUPPORT, None, (), False, True)

C4_VM_JOBS = tuple(VmJob(f"quantt-{C4_BOOK}-{vj.job.log_stem}", _book_job(vj.job, C4_BOOK),
                         vj.success_exit) for vj in VM_JOBS)
C4_SECRET_UNIT = f"quantt-{C4_BOOK}-secret.service"
C4_SEED_RULINGS = "results/cef/c4/c4_seed_rulings_2026-10-29.json"
C4_UNIVERSE = "results/cef/c4/c4_universe_frozen_2026-10-14.csv"
C4_VM = VmBook(
    C4_BOOK, C4_VM_JOBS, C4_SECRET_UNIT, f"quantt-{C4_BOOK}",
    (("alpaca-c4-key-id", "ALPACA_C4_KEY_ID"), ("alpaca-c4-secret-key", "ALPACA_C4_SECRET_KEY")),
    # What C4's units need at the tag: the core's (the same runner, collector and
    # fetchers), C4's book json and spec, the data-book config and its tracked
    # inputs, the spike guard fetch_daily runs for C4, the seed ruling the
    # manifest is checked against, and C4's templates.
    REQUIRED_AT_TAG + (
        "ops/books/c4_families_book.json",
        "ops/specs/c4_families.frozen.json",
        "scripts/cef/data_books.py",
        "scripts/cef/data_guards.py",
        C4_UNIVERSE,
        "results/cef/c4/c4_nav_symbols_2026-10-14.csv",
        C4_SEED_RULINGS,
    ) + tuple(template_path(f) for f in
              (C4_SECRET_UNIT,) + tuple(x for vj in C4_VM_JOBS for x in (vj.service, vj.timer))),
    "cef_c4", ("cef_prices.parquet", "cef_nav.parquet"), "seed_manifest.json",
    (("bar_rulings", C4_SEED_RULINGS), ("universe", C4_UNIVERSE)), True, False)

VM_BOOKS = {b.name: b for b in (CORE_VM, C4_VM)}
EOD_FROM_ENV = "QUANTT_EOD_FROM"         # quantt/collect/collect.py EOD_FROM_ENV


# -- the report-only units (team lead 2026-11-08: the nightly check is owned by a VM timer)
#
# `--reports` installs, beside the books' units, three report-only jobs per book:
# scripts/ops/data_qa.py (21:45 cef, 21:50 c4, after the :40 collect and before the
# 22:00 decide), scripts/ops/risk_daily.py (22:15 cef, 22:20 c4, after the decide) and
# scripts/ops/pnl_report.py (20:30 cef, 20:35 c4, the P&L report kind below), Mon-Fri,
# clear of the runner's slots (session decide/send windows, collect 21:40, verify 17:30).
# WHY A SEPARATE MODE, NOT MORE JOBS IN THE BOOKS' UNIT LISTS. The core's and C4's
# plans stay byte for byte what they were (tests/test_install_vm_books.py), and an
# install that stops, restarts or re-renders a session unit never depends on a report
# unit. The modes share the install lock, the tag and clean-clone checks, the drop-in
# scan, the loaded-as-written check and the no-job-running check.
# A report job: reads the panels and the runner's files; takes no panel lock; holds
# no broker key (no Environment= key file, no Wants= on the book's key service;
# risk_daily alone gets the SMTP env file, for the ACT push); ReadOnlyPaths= the clone,
# so a bug cannot write into data/ or git; MemoryMax= measured peak with margin;
# TimeoutStartSec= so it cannot run into the next slot. A failed report job is its own
# `failed` unit and touches nothing else.
# The P&L report kind (team lead, 2026-11-09; docs/RUNBOOK.md 8.12): the third
# job per book, scripts/ops/pnl_report.py (20:30 cef, 20:35 c4). It reads the
# account, so it needs a broker key, through a GET-only reader; the key comes from
# the vault at run time into a tmpfs env file of ITS OWN, one per book, written by its
# own secret service. The dataqa and risk units stay key-free (a test pins it), and the
# SMTP alert env file stays separate. A failed key fetch fails its pnl unit, named in
# that report, and nothing else.
REPORT_PNL_MEMORY_MAX = "900M"           # a guess, not a measurement: read `systemctl show quantt-c4-pnl -p MemoryPeak` after a first run (RUNBOOK 8.12)
REPORT_SECRET_UNIT = "quantt-reports-secret.service"
REPORT_RUNTIME_DIR = "quantt-reports"
REPORT_ENV_FILE = Path("/run") / REPORT_RUNTIME_DIR / "alert.env"
REPORT_SECRET_MAP = (("alert-smtp-user", "ALERT_SMTP_USER"), ("alert-smtp-pass", "ALERT_SMTP_PASS"))
REPORT_BOOKS = (BOOK, C4_BOOK)
REPORT_KINDS = {"dataqa": "scripts.ops.data_qa", "risk": "scripts.ops.risk_daily",
                "pnl": "scripts.ops.pnl_report"}
REPORT_SCHEDULE = {("dataqa", BOOK): (21, 45), ("dataqa", C4_BOOK): (21, 50),
                   ("risk", BOOK): (22, 15), ("risk", C4_BOOK): (22, 20),
                   # the runner owner's times (team lead, 2026-11-09): after the 20:00 EOD
                   # stamp, clear of the 21:40 collect. 20:30 is the session timer's idle
                   # tick (it decides nothing at that hour); the job takes no lock.
                   ("pnl", BOOK): (20, 30), ("pnl", C4_BOOK): (20, 35)}
REPORT_MEMORY_MAX = "450M"               # data_qa c4 peak 220 MB (2x that); measured 2026-11-08 (RUNBOOK 8.11)
REPORT_TIMEOUT_S = 480                   # ends before the next :00/:30 session slot
REPORT_TEMPLATES = {"dataqa": "quantt-report-dataqa.service.tmpl",
                    "risk": "quantt-report-risk.service.tmpl",
                    "pnl": "quantt-report-pnl.service.tmpl",
                    "timer": "quantt-report.timer.tmpl",
                    "secret": "quantt-reports-secret.service.tmpl",
                    "pnl_keys": "quantt-reports-pnl-keys.service.tmpl"}


def _report_job(kind: str, book: str) -> VmJob:
    """The report job's unit name and launchd-shaped job (its schedule is Mon-Fri,
    so `oncalendar` renders `Mon,Tue,Wed,Thu,Fri *-*-* HH:MM:00`)."""
    hour, minute = REPORT_SCHEDULE[(kind, book)]
    sched = tuple({"Weekday": d, "Hour": hour, "Minute": minute} for d in range(1, 6))
    args = ("-B", "-m", REPORT_KINDS[kind], "--book", book)
    return VmJob(f"quantt-{book}-{kind}", ip.Job(f"com.quantt.alpaca.{book}.{kind}", "", args, sched, kind))


REPORT_JOBS = tuple(_report_job(k, b) for k in REPORT_KINDS for b in REPORT_BOOKS)


class ReportKeyVm(VmBook):
    """A pnl job's broker keys: the book's own vault secrets, written by a secret service of
    its own into a tmpfs env file of its own (module comment, the P&L report kind)."""
    @property
    def env_file(self) -> Path:
        return Path("/run") / self.runtime_dir / "broker.env"


def _pnl_key_vm(book: VmBook) -> ReportKeyVm:
    """One book's pnl key service (no jobs): named for the book and kept apart from the
    book's own key service, which the runner's units use."""
    return ReportKeyVm(f"reports-{book.name}", (), f"quantt-reports-{book.name}-pnl-keys.service",
                       f"quantt-reports-{book.name}-pnl", book.secret_map, (), "", (), None, (), False, False)


REPORT_PNL_KEYS = {b.name: _pnl_key_vm(b) for b in (CORE_VM, C4_VM)}
REPORT_PNL_KEY_UNITS = {book: vm.secret_unit for book, vm in REPORT_PNL_KEYS.items()}
REPORT_UNIT_FILES = (REPORT_SECRET_UNIT,) + tuple(REPORT_PNL_KEY_UNITS[b] for b in REPORT_BOOKS) + \
    tuple(f for vj in REPORT_JOBS for f in (vj.service, vj.timer))


class ReportVm(VmBook):
    @property
    def env_file(self) -> Path:          # alert.env: it holds SMTP settings, not Alpaca keys
        return REPORT_ENV_FILE


REPORT_VM = ReportVm(
    "reports", REPORT_JOBS, REPORT_SECRET_UNIT, REPORT_RUNTIME_DIR, REPORT_SECRET_MAP,
    # What the report units need at the tag: the installer's own files, the scripts,
    # the two readers they import, and the templates. Refused at planning if absent.
    ip.REQUIRED_AT_TAG + ("requirements.txt", "quantt/deploy/boot_secrets.py", "quantt/deploy/azure_keyvault.py",
                          "ops/halt.py", "ops/schedule/nyse_calendar.py", "scripts/cef/data_guards.py",
                          "quantt/session/drawdown.py", "scripts/ops/data_qa.py", "scripts/ops/risk_daily.py",
                          "scripts/ops/report_notify.py", "scripts/ops/pnl_report.py", "scripts/ops/alpaca_read.py",
                          "scripts/cef/live_attribution.py", "scripts/cef/exposure_readout.py", "scripts/cef/spec.py",
                          "quantt/session/dist_score.py", "ops/specs/c4_families.frozen.json",
                          "ops/specs/cef_discount.frozen.json", "results/cef/c4/c4_nav_symbols_2026-10-14.csv")
    + tuple(f"{TEMPLATE_DIR}/{t}" for t in REPORT_TEMPLATES.values()),
    "", (), None, (), False, False)


def _refuse_if_report_jobs_busy(run_cmd: Callable, layout: "Layout") -> None:
    """A book install, at PLANNING only: refuse while a report job is running or
    queued, naming it (the existing no-job-running check covers them). It is never
    re-asked after the timers stop, so a report firing mid-install cannot fail the
    install or leave the books' timers stopped; a report job has no order path, so
    the worst it can do is crash on a tree that moved under it, on its own."""
    if not any(layout.unit_path(f).exists() for f in REPORT_UNIT_FILES):
        return                           # none installed: nothing to ask systemd about
    rows = job_states(run_cmd, REPORT_VM)
    if rows:
        raise InstallRefused(f"{'; '.join(_describe(r) for r in rows)}: a report job is running; "
                             f"wait for it to finish (a minute or two) and re-run")


@dataclass(frozen=True)
class Layout:
    """Every path the VM prod uses. `home` and `units_dir` are parameters so
    the tests build the whole thing under tmp_path."""
    home: Path                       # /home/quantt
    units_dir: Path = UNITS_DIR
    sysroot: Path = Path("/")        # where the drop-in scan looks for /etc, /run, /usr
    book: str = BOOK                 # whose state dir (VmBook.name); the core's by default

    @property
    def prod_dir(self) -> Path:
        return self.home / "prod" / "quantt-alpaca"

    @property
    def state_root(self) -> Path:
        return self.home / "quantt_state"

    @property
    def state_dir(self) -> Path:
        return self.state_root / self.book

    @property
    def log_dir(self) -> Path:
        return self.state_dir / "logs"

    @property
    def seed_log(self) -> Path:
        return self.state_dir / "seed.log"

    @property
    def venv_python(self) -> Path:
        return self.home / "venv" / "bin" / "python"

    @property
    def requirements_record(self) -> Path:
        return self.home / "venv" / REQUIREMENTS_RECORD

    def unit_path(self, unit_file: str) -> Path:
        return self.units_dir / unit_file


# -- schedule ---------------------------------------------------------------

def oncalendar(schedule) -> list:
    """launchd StartCalendarInterval dicts -> systemd OnCalendar expressions.

    A dict without Weekday fires every day; one without Hour fires every
    hour (an omitted launchd key is a wildcard). Weekday dicts sharing an
    hour and minute are folded into one line with a day list, e.g.
    `Mon,Tue,Wed,Thu,Fri *-*-* 15:52:00`. The tests prove the result fires at
    exactly the launchd times, by expanding both over a whole week.
    """
    plain, by_time = [], {}
    for d in schedule:
        if not set(d) <= {"Weekday", "Hour", "Minute"} or "Minute" not in d:
            raise InstallRefused(f"cannot translate launchd interval {d!r}")
        hh = f"{d['Hour']:02d}" if "Hour" in d else "*"
        mm = f"{d['Minute']:02d}"
        if "Weekday" in d:
            by_time.setdefault((hh, mm), set()).add(WEEKDAY_NAMES[d["Weekday"]])
        else:
            plain.append(f"*-*-* {hh}:{mm}:00")
    for (hh, mm), days in by_time.items():
        plain.append(f"{','.join(sorted(days, key=DAY_ORDER.index))} *-*-* {hh}:{mm}:00")
    return plain


# -- units ------------------------------------------------------------------

def parse_unit(text: str, name: str) -> dict:
    """A unit file -> {section: [(key, value), ...]}, keeping repeated keys.

    configparser would collapse the repeated keys systemd allows (Environment=,
    OnCalendar=). Line continuations are refused, so that what is checked is
    exactly what systemd reads.
    """
    sections, cur = {}, None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.endswith("\\"):
            raise InstallRefused(f"{name}:{n}: line continuation not allowed")
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1]
            if cur in sections:
                raise InstallRefused(f"{name}:{n}: section [{cur}] repeated")
            sections[cur] = []
            continue
        if cur is None or "=" not in line:
            raise InstallRefused(f"{name}:{n}: not a key=value line in a section: {line!r}")
        k, v = line.split("=", 1)
        sections[cur].append((k.strip(), v.strip()))
    return sections


def check_unit(text: str, name: str, expected: dict) -> dict:
    """Parse a rendered unit and require exactly `expected`, or raise.

    `expected` maps section -> [(key, value)]. Order within a section is free,
    multiplicity is not. [Unit] must also hold exactly one non-empty
    Description=, whose text is not checked. Returns the parsed unit.
    """
    got = parse_unit(text, name)
    problems = []
    for sec, pairs in got.items():
        for k, v in pairs:
            if "$" in v or "%" in v:
                problems.append(f"[{sec}] {k}={v!r} contains '$' or '%' (systemd would expand it)")
    unit = list(got.get("Unit", []))
    desc = [v for k, v in unit if k == "Description"]
    if len(desc) != 1 or not desc[0]:
        problems.append(f"[Unit] needs exactly one non-empty Description=, has {desc!r}")
    got_cmp = {sec: [p for p in pairs if not (sec == "Unit" and p[0] == "Description")]
               for sec, pairs in got.items()}
    if set(got_cmp) != set(expected):
        problems.append(f"sections are {sorted(got_cmp)}, expected {sorted(expected)}")
    for sec in set(got_cmp) & set(expected):
        # Environment= order is what systemd reports (measured), and the
        # post-reload check compares it in order, so planning pins it too.
        env_have = [v for k, v in got_cmp[sec] if k == "Environment"]
        env_want = [v for k, v in expected[sec] if k == "Environment"]
        if Counter(env_have) == Counter(env_want) and env_have != env_want:
            problems.append(f"[{sec}] Environment order is {env_have}, expected {env_want}")
        have, want = Counter(got_cmp[sec]), Counter(expected[sec])
        for k, v in sorted((want - have).elements()):
            problems.append(f"[{sec}] missing {k}={v}")
        for k, v in sorted((have - want).elements()):
            problems.append(f"[{sec}] unexpected {k}={v}")
    if problems:
        raise InstallRefused(f"{name}: rendered unit fails its checks: " + "; ".join(problems))
    return got


def expected_job_service(vj: VmJob, *, python: Path, layout: Layout, env: dict,
                         secret_unit: str = SECRET_UNIT) -> dict:
    svc = [("Type", "oneshot"), ("User", SERVICE_USER), ("Group", SERVICE_USER),
           ("WorkingDirectory", str(layout.prod_dir)),
           *[("Environment", f"{k}={v}") for k, v in env.items()],
           ("ExecStart", " ".join([str(python), *vj.job.args])),
           ("StandardOutput", f"append:{layout.log_dir}/{vj.job.log_stem}.out.log"),
           ("StandardError", f"append:{layout.log_dir}/{vj.job.log_stem}.err.log")]
    if vj.success_exit:
        svc.append(("SuccessExitStatus", " ".join(str(c) for c in vj.success_exit)))
    return {"Unit": [("Wants", secret_unit), ("After", secret_unit)], "Service": svc}


def expected_timer(vj: VmJob) -> dict:
    return {"Unit": [],
            "Timer": [*[("OnCalendar", e) for e in oncalendar(vj.job.schedule)],
                      ("AccuracySec", "1s"), ("Persistent", "false"),
                      ("Unit", vj.service)],
            "Install": [("WantedBy", "timers.target")]}


def secret_command(python: Path, vault: str, book: VmBook = CORE_VM) -> list:
    cmd = [str(python), "-m", "quantt.deploy.boot_secrets", "--provider", SECRET_PROVIDER,
           "--config", f"vault={vault}"]
    for name, env in book.secret_map:
        cmd += ["--secret", f"{name}={env}"]
    return cmd + ["--out", str(book.env_file)]


def expected_secret_service(*, python: Path, layout: Layout, env: dict, vault: str,
                            book: VmBook = CORE_VM) -> dict:
    return {"Unit": [("Wants", "network-online.target"), ("After", "network-online.target")],
            "Service": [("Type", "oneshot"), ("RemainAfterExit", "yes"),
                        ("User", SERVICE_USER), ("Group", SERVICE_USER),
                        ("RuntimeDirectory", book.runtime_dir), ("RuntimeDirectoryMode", "0700"),
                        ("WorkingDirectory", str(layout.prod_dir)),
                        ("Environment", f"PATH={env['PATH']}"),
                        ("Environment", f"PYTHONUNBUFFERED={env['PYTHONUNBUFFERED']}"),
                        ("ExecStart", " ".join(secret_command(python, vault, book))),
                        ("StandardOutput", f"append:{layout.log_dir}/secret.out.log"),
                        ("StandardError", f"append:{layout.log_dir}/secret.err.log")],
            "Install": [("WantedBy", "multi-user.target")]}


def render(template_text: str, values: dict, name: str) -> str:
    """Substitute ${NAME} placeholders. Every value must match SAFE_VALUE_RE, and
    a placeholder with no value raises rather than shipping a literal `${X}`."""
    for k, v in values.items():
        if not SAFE_VALUE_RE.match(str(v)):
            raise InstallRefused(f"{name}: value for ${{{k}}} ({v!r}) has characters a "
                                 f"unit file would misread (space, %, $, quotes)")
    try:
        return Template(template_text).substitute({k: str(v) for k, v in values.items()})
    except KeyError as e:
        raise InstallRefused(f"{name}: template placeholder {e} has no value") from e
    except ValueError as e:
        raise InstallRefused(f"{name}: template is malformed: {e}") from e


# -- processes --------------------------------------------------------------

def _real_run(args):
    return subprocess.run(args, capture_output=True, text=True)


def _user_ids(user: str) -> tuple:
    try:
        pw = pwd.getpwnam(user)
    except KeyError:
        raise InstallRefused(f"no user {user!r} on this machine; run "
                             f"quantt/deploy/vm/bootstrap.sh first") from None
    return pw.pw_uid, pw.pw_gid


class Git:
    """git in the prod clone, as the service user.

    HOME is set to that user's home, so git never reads root's config. That
    matters because `runuser` without `-l` would keep root's HOME, and git
    cannot read /root as quantt.
    """

    def __init__(self, repo: Path, as_user: list, home: Path):
        self.repo, self.as_user, self.home = repo, as_user, home

    def __call__(self, *args, allow_fail=False, raw=False):
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", HOME=str(self.home))
        r = subprocess.run([*self.as_user, "git", "-C", str(self.repo), *args],
                           capture_output=True, text=not raw, env=env)
        if r.returncode != 0:
            if allow_fail:
                return None
            err = r.stderr.decode("utf-8", "replace") if raw else r.stderr
            raise InstallRefused(f"`git {' '.join(args)}` failed (exit {r.returncode}): "
                                 f"{err.strip()}")
        return r.stdout


def remote_tag_commit(git: Git, url: str, tag: str) -> str:
    """The commit `refs/tags/<tag>` names on `url`, peeled for annotated tags."""
    out = git("ls-remote", "--tags", url, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")
    refs = {}
    for line in out.splitlines():
        sha, ref = line.split("\t", 1)
        refs[ref] = sha
    plain, peeled = refs.get(f"refs/tags/{tag}"), refs.get(f"refs/tags/{tag}^{{}}")
    if plain is None:
        raise InstallRefused(f"tag {tag} is not on origin ({url}); push it first")
    return peeled or plain


# -- what systemd runs (review 2026-10-07) -----------------------------------
#
# A unit FILE is not what systemd runs. A drop-in (`systemctl edit` writes
# <unit>.d/override.conf; `set-property` writes under system.control; a
# `quantt-.service.d/` directory applies to every quantt-* service) is merged on
# top of the file. A disarm-by-reinstall that rewrote only the file would leave
# an override's Environment=DRY_RUN=0 in force. So the installer asks systemd:
# before planning, that no drop-in exists and the unit comes from our file; after
# daemon-reload, that what systemd loaded is exactly what was written. This is
# install_prod's launchd precedent (refuse when the loaded job and the file could
# disagree), applied to systemd.
#
# The `systemctl show` formats parsed here (`Key=value` lines; ExecStart as
# `{ path=... ; argv[]=... ; ... }`; TimersCalendar as `{ OnCalendar=... ; ... }`)
# are systemd's [S]. A format this code cannot read REFUSES, never passes.
# MEASURED on the VM (systemd 255.4-1ubuntu8.17, 2026-10-07) [V]:
#   * `systemctl show quantt-nonexistent.service -p FragmentPath -p DropInPaths
#     -p Environment` exits 0 and reports all three, empty, with
#     LoadState=not-found. So a first install's planning reads empty values, and
#     no "unit not found" error.
#   * Environment= is reported in FILE order (file ZED, ALPHA, MID -> show
#     `ZED=1 ALPHA=2 MID=3`), so the ordered comparison below is exact, and
#     check_unit pins the order at planning.
#   * A drop-in written WITHOUT daemon-reload is INVISIBLE here. DropInPaths
#     stays empty, the old Environment is shown, and NeedDaemonReload stays
#     `no`, until the next reload, which would be this installer's own. So
#     `systemctl show` cannot be the pre-write check. `dormant_overrides`
#     scans the disk instead. (A naive probe on an inactive, unreferenced unit
#     looks fine, because systemd re-reads that from disk on query; the
#     measurement used a unit held loaded by an active timer.)
# MEASURED on the VM (systemd 255.4-1ubuntu8.17, 2026-10-08 ~01:10 UTC) [V]:
#   (a) A start queued behind its After= dependency (the dependency
#       `activating`) reads `systemctl is-active` = inactive, ActiveState=
#       inactive, SubState=dead. But `show -p Job` is a job id, and
#       `list-jobs` shows `<id> <unit> start waiting`. So `is-active` alone
#       misses a queued job; `job_states` reads ActiveState AND Job.
#   (b) CORRECTED 2026-10-08 (release-check #3). This note first said a
#       restart does NOT replay a missed slot. That came from a probe on a
#       started-but-NOT-ENABLED timer, which is likely unloaded on stop and
#       so forgets its last trigger. It does not apply to our enabled timers.
#       MEASURED on the VM [V: 2026-10-08 04:38-04:41 UTC; OnCalendar *:*:00
#       and *:*:30, enabled]: fired 04:39:00, stopped 04:39:00, slots
#       04:39:30 and 04:40:00 missed, `systemctl start` at 04:40:15 -> ran at
#       04:40:15, LastTriggerUSec=04:40:15. So an ENABLED Persistent=false
#       timer restarted within one boot across a missed slot fires AT ONCE.
#       That is why the installer refuses inside the late windows and
#       re-checks the clock before it restarts the timers (_refuse_if_late).

# Directories where set-property and transient units live. On a system manager
# `systemd-analyze unit-paths` lists them already [S]; they are added anyway,
# because missing one would let an override through.
CONTROL_DIRS = ("etc/systemd/system.control", "run/systemd/system.control",
                "run/systemd/transient")


def unit_search_path(run_cmd: Callable) -> list:
    """systemd's unit search path, in priority order (`systemd-analyze unit-paths`)."""
    r = run_cmd(["systemd-analyze", "unit-paths"])
    if r.returncode != 0:
        raise InstallRefused(f"`systemd-analyze unit-paths` failed: "
                             f"{(r.stderr or r.stdout).strip()}")
    dirs = [Path(line.strip()) for line in (r.stdout or "").splitlines() if line.strip()]
    if not dirs:
        raise InstallRefused("`systemd-analyze unit-paths` listed no directories")
    return dirs


def dropin_dir_names(unit: str) -> list:
    """Every drop-in directory name systemd reads for `unit` (systemd.unit(5)):

      * `<unit>.d/`;
      * each dash-truncated prefix, e.g. `quantt-.service.d/` and
        `quantt-cef-.service.d/` for quantt-cef-session.service. The full stem
        plus '-' is included too: a name that can only refuse more is safe;
      * the type-wide `service.d/` or `timer.d/`, which applies to every unit of
        that type. That is since systemd 253 [S: release notes, not re-read];
        Ubuntu 24.04 ships 255.
    """
    stem, typ = unit.rsplit(".", 1)
    parts = stem.split("-")
    return ([f"{unit}.d"] + [f"{'-'.join(parts[:i])}-.{typ}.d" for i in range(1, len(parts) + 1)]
            + [f"{typ}.d"])


def dormant_overrides(run_cmd: Callable, layout: "Layout", units=ALL_UNIT_FILES, *,
                      unexpected_prefixes: tuple = ()) -> list:
    """Files on disk that would change what systemd runs for our units at the
    next daemon-reload, which is the installer's own. They are invisible to
    `systemctl show` until then (measured; see the comment above). Returns a
    sorted list of descriptions; empty means none.

      * any `*.conf` in any drop-in directory of any of our units, in any
        directory of the search path or the control/transient directories;
      * a unit file with one of our names in a directory that outranks ours,
        which systemd would load instead of the file written here;
      * with `unexpected_prefixes` (a C4 install, `scan_units`): any `.service`
        or `.timer` file named with one of those prefixes, in any of those
        directories, that is not one of `units`. The reload would load it too.
    """
    search = unit_search_path(run_cmd)
    resolved = [d.resolve() for d in search]
    ours = layout.units_dir.resolve()
    if ours not in resolved:
        raise InstallRefused(f"{layout.units_dir} is not on systemd's unit search path "
                             f"({', '.join(map(str, search))}); systemd would not load "
                             f"the units written there")
    roots = list(dict.fromkeys(search + [layout.sysroot / d for d in CONTROL_DIRS]))
    found = set()
    for d in roots:
        for unit in units:
            for name in dropin_dir_names(unit):
                for conf in (d / name).glob("*.conf") if (d / name).is_dir() else ():
                    found.add(f"drop-in {conf} (applies to {unit})")
    for d in search[:resolved.index(ours)]:
        for unit in units:
            if (d / unit).exists() or (d / unit).is_symlink():
                found.add(f"unit file {d / unit} outranks {layout.unit_path(unit)}")
    for d in roots[len(search):]:              # control/transient dirs not on the path
        for unit in units:
            if (d / unit).exists() or (d / unit).is_symlink():
                found.add(f"unit file {d / unit} (control/transient) for {unit}")
    # The report units are installed by `--reports`, so a C4 install does not name them
    # in `units`, but they are ours: never "no unit any book installs" (and a report
    # unit could not change what a C4 session does in any case).
    known = set(units) | set(REPORT_UNIT_FILES)
    for d in roots if unexpected_prefixes else ():
        for f in sorted(d.glob("*")) if d.is_dir() else ():
            if (f.name.startswith(unexpected_prefixes) and f.suffix in (".service", ".timer")
                    and f.name not in known and (f.is_file() or f.is_symlink())):
                found.add(f"unit file {f} is no unit any book installs")
    return sorted(found)


def scan_units(vb: "VmBook") -> tuple:
    """(units, unexpected prefixes) an install of `vb` scans on disk before its reload.

    The core: its own units and nothing else, exactly as before (its whole install
    is pinned to cee16ad's installer, quantt/deploy/tests/test_install_vm_books.py).
    Any other book, i.e. C4 (release-check of 336df9d, ET1, 2026-11-03): EVERY
    book's units, and any other `quantt-` unit file. Its `systemctl daemon-reload`
    applies to every unit on the machine, so a drop-in waiting on the core's ARMED
    units (say `Environment=DRY_RUN=0` on a C4 unit, or anything on the core's)
    would go live through a C4 install that never looked at it. Gate 2 still needs
    AUTO_ARMED or an approved sha before anything transmits; this refuses earlier,
    naming the file."""
    if vb is CORE_VM:
        return vb.unit_files, ()
    every = tuple(dict.fromkeys(f for b in VM_BOOKS.values() for f in b.unit_files))
    return every, ("quantt-",)


def _refuse_if_overridden_on_disk(run_cmd: Callable, layout: "Layout",
                                  units=ALL_UNIT_FILES, unexpected_prefixes: tuple = ()) -> None:
    found = dormant_overrides(run_cmd, layout, units, unexpected_prefixes=unexpected_prefixes)
    if found:
        raise InstallRefused(
            "files on disk would change what systemd runs at the next daemon-reload "
            "(the installer's own), and `systemctl show` cannot see them until then: "
            + "; ".join(found) + ". Read them, remove them, and re-run")


BUSY_STATES = frozenset({"active", "activating", "deactivating", "reloading", "refreshing"})
IDLE_STATES = frozenset({"inactive", "failed", "maintenance"})


def systemd_show(run_cmd: Callable, unit: str, props: list) -> dict:
    """{property: [value, ...]} from `systemctl show`, or raise."""
    args = ["systemctl", "show", unit]
    for prop in props:
        args += ["-p", prop]
    r = run_cmd(args)
    if r.returncode != 0:
        raise InstallRefused(f"`systemctl show {unit}` failed: {(r.stderr or r.stdout).strip()}")
    out = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out.setdefault(k, []).append(v)
    missing = [prop for prop in props if prop not in out]
    if missing:
        raise InstallRefused(f"`systemctl show {unit}` did not report {missing}; cannot "
                             f"confirm what systemd runs")
    return out


def _one(props: dict, key: str, unit: str) -> str:
    if len(props[key]) != 1:
        raise InstallRefused(f"`systemctl show {unit}` reported {key} {len(props[key])} times")
    return props[key][0]


def check_not_overridden(run_cmd: Callable, layout: "Layout", unit: str) -> dict:
    """Planning: no drop-in on `unit`, and if systemd has it loaded, from our file."""
    service = unit.endswith(".service")
    props = systemd_show(run_cmd, unit, ["FragmentPath", "DropInPaths"]
                         + (["Environment"] if service else []))
    drop = _one(props, "DropInPaths", unit).split()
    if drop:
        raise InstallRefused(
            f"{unit} has drop-in(s) {drop}: systemd merges them over the unit file, so "
            f"this install could not decide what runs (an Environment=DRY_RUN=0 there "
            f"would survive a disarm). Read them, then remove them (`systemctl revert "
            f"{unit}`, or delete the file) and re-run")
    frag = _one(props, "FragmentPath", unit)
    if frag and frag != str(layout.unit_path(unit)):
        raise InstallRefused(f"systemd loads {unit} from {frag}, not {layout.unit_path(unit)}; "
                             f"refusing to install over a unit defined elsewhere")
    return props


def verify_loaded(run_cmd: Callable, layout: "Layout", unit: str, expect: dict) -> None:
    """After daemon-reload: systemd's loaded `unit` is exactly what was written."""
    service = unit.endswith(".service")
    props = systemd_show(run_cmd, unit, ["FragmentPath", "DropInPaths"]
                         + (["Environment", "ExecStart"] if service else ["TimersCalendar"]))
    problems = []
    drop = _one(props, "DropInPaths", unit).split()
    if drop:
        problems.append(f"drop-in(s) {drop}")
    frag = _one(props, "FragmentPath", unit)
    if frag != str(layout.unit_path(unit)):
        problems.append(f"FragmentPath is {frag!r}, expected {str(layout.unit_path(unit))!r}")
    if service:
        env = _one(props, "Environment", unit).split()
        if env != expect["env"]:
            problems.append(f"Environment is {env}, expected {expect['env']}")
        argv = re.findall(r"argv\[\]=(.*?) ;", " ".join(props["ExecStart"]))
        if argv != [expect["exec"]]:
            problems.append(f"ExecStart argv is {argv}, expected {[expect['exec']]}")
    else:
        cal = re.findall(r"OnCalendar=(.*?) ;", " ".join(props["TimersCalendar"]))
        if sorted(cal) != sorted(expect["calendar"]):
            problems.append(f"calendar is {sorted(cal)}, expected {sorted(expect['calendar'])}")
    if problems:
        raise InstallRefused(
            f"after daemon-reload systemd's {unit} is not the unit written: "
            + "; ".join(problems) + ". systemd is NOW running the configuration shown. "
            + HALT_ADVICE + ", then find the cause")


# How to halt NOW, named in every refusal that leaves systemd running something
# unexpected. The halt file comes first because it stops every send, whatever
# arms it. On the cut-over day the VM sends from <state>/<D>/APPROVED with no
# AUTO_ARMED (RUNBOOK 8.5), so removing AUTO_ARMED alone would halt nothing
# (release-check #8, 2026-10-08).
HALT_ADVICE = ("Halt now with docs/RUNBOOK.md 8.6 halting step 1 or 2: the halt file "
               "(ops/HALT.md), which stops every send; or remove AUTO_ARMED AND the "
               "APPROVED file of any session not yet sent (<state>/<D>/APPROVED)")


def late_window_at(now_utc: dt.datetime, ranges=PLAN_REFUSE_RANGES_ET):
    """(start, end, local time) if `now_utc` is a weekday inside one of `ranges`, else None.

    Every weekday is guarded for both ranges, as the runner's pre-check does:
    which days close early is a calendar fact the installer does not need to
    get right in order to stay out of the way.
    """
    t = now_utc.astimezone(ZoneInfo(REQUIRED_TZ))
    if t.weekday() >= 5:
        return None
    for a, b in ranges:
        if a <= t.time() < b:
            return a, b, t
    return None


def _refuse_if_late(clock: Callable, what: str, ranges=PLAN_REFUSE_RANGES_ET) -> None:
    """Why (release-check #3, measured on the VM 2026-10-08): an ENABLED
    Persistent=false timer, stopped and restarted within one boot across a
    missed slot, FIRES AT ONCE on the restart. An --apply stops the timers, so
    one that spans 15:52/15:55 (12:52/12:55) would replay the send slot at its
    restart: a late, partial send. So: no install inside the windows, and no
    restart of the timers inside them. The planning window is the wider one
    (see PLAN_REFUSE_RANGES_ET)."""
    hit = late_window_at(clock(), ranges)
    if hit:
        a, b, t = hit
        raise InstallRefused(
            f"{what}: it is {t:%H:%M:%S} ET on a weekday, inside the late-market window "
            f"{a:%H:%M}-{b:%H:%M} ET (start any --apply before 15:30, or 12:30 on an "
            f"early close, or after the close). A timer restarted across a missed slot fires at "
            f"once (measured on the VM, 2026-10-08), so stopping and restarting the timers "
            f"here could replay the 15:52/15:55 (12:52/12:55) send slot into a late, "
            f"partial send. Re-run after {b:%H:%M} ET (after 16:00, or 13:00 on an early "
            f"close)")


def deps_script(layout: "Layout") -> str:
    """The RUNBOOK 8.6 dependency step as one bash script, run as the service user.

    Why this shape (release-check #4): an earlier form hashed requirements.txt as
    the admin user, who cannot read /home/quantt (mode 750), and piped the result
    into `tee` without pipefail. A failed hash then still TRUNCATED the record,
    so the installer refused again with the same advice, and the timers stayed
    stopped. Here everything runs as quantt under `set -euo pipefail`. The hash
    is computed first; the record is written only if the hash is non-empty, via a
    temp file and `mv`, so it is never left truncated.

    It first changes into the service user's home: uv reads uv.toml from the
    working directory, and from the admin's home (unreadable to quantt) it failed
    "Permission denied" (measured on the VM, 2026-10-08).
    """
    q = shlex.quote
    req, rec = layout.prod_dir / "requirements.txt", layout.requirements_record
    return (f"set -euo pipefail; cd {q(str(layout.home))}; "
            f"{q(str(layout.home / '.uv' / 'bin' / 'uv'))} pip install --no-build "
            f"--python {q(str(layout.venv_python))} -r {q(str(req))}; "
            f"h=$(sha256sum {q(str(req))} | cut -d' ' -f1); "
            f'[ -n "$h" ]; '
            f"printf '%s\\n' \"$h\" > {q(str(rec) + '.tmp')}; "
            f"mv {q(str(rec) + '.tmp')} {q(str(rec))}")


def deps_command(layout: "Layout") -> str:
    """deps_script, run as the service user: the whole step is quantt's."""
    return (f"sudo -u {SERVICE_USER} env HOME={shlex.quote(str(layout.home))} "
            f"bash -c {shlex.quote(deps_script(layout))}")


def _refuse_if_venv_is_stale(git: "Git", commit: str, tag: str, layout: "Layout") -> None:
    """The venv must have been built from the TAG's requirements.txt.

    The installer does not install dependencies. Without this check, a release
    that changed requirements.txt would run its new code against the old
    packages, and nothing would say so until something failed at run time.
    bootstrap.sh (and the RUNBOOK 8.6 step) record the sha256 of the
    requirements.txt they installed; it is compared here with the tag's blob.
    """
    want = hashlib.sha256(git("show", f"{commit}:requirements.txt", raw=True)).hexdigest()
    rec = layout.requirements_record
    try:
        words = rec.read_text().split()
    except FileNotFoundError:
        words = []
    if not words:
        raise InstallRefused(
            f"{rec} is missing or empty, so the venv has no record of the "
            f"requirements.txt it was built from. With the timers stopped and the clone "
            f"at {tag} (docs/RUNBOOK.md 8.6 steps 1 and 3), run: {deps_command(layout)}")
    if words[0] != want:
        raise InstallRefused(
            f"the venv was built from a requirements.txt with sha256 {words[0][:12]}..., but "
            f"{tag}'s has {want[:12]}...: its packages do not match the release. With the "
            f"timers stopped, check out {tag} (docs/RUNBOOK.md 8.6 step 3), then run: "
            f"{deps_command(layout)}")


def _confirm_key_file(layout: "Layout", uid: int, book: VmBook = CORE_VM) -> None:
    """The key file exists, is a regular 0600 file, and is owned by the service
    user. The check uses stat only: the file is never opened."""
    f = layout.sysroot / book.env_file.relative_to("/")
    try:
        st = os.lstat(f)
    except FileNotFoundError:
        raise InstallRefused(f"{book.secret_unit} is active but {book.env_file} does not "
                             f"exist") from None
    problems = []
    if not stat.S_ISREG(st.st_mode):
        problems.append("is not a regular file")
    if st.st_mode & 0o777 != 0o600:
        problems.append(f"has mode {oct(st.st_mode & 0o777)}, expected 0o600")
    if st.st_uid != uid:
        problems.append(f"is owned by uid {st.st_uid}, not {SERVICE_USER} ({uid})")
    if problems:
        raise InstallRefused(f"{book.env_file} {' and '.join(problems)}")


class JobDuringInstall(InstallRefused):
    """A quantt job ran or was queued AFTER the reload. That should be
    impossible with the timers stopped, so it is a separate exit code and a
    louder message than a refusal."""


def job_states(run_cmd: Callable, book: VmBook = CORE_VM) -> list:
    """Every quantt service that is running or has a job queued, as dicts.

    Busy means one of:
      * a job service whose ActiveState is active, activating, deactivating,
        reloading or refreshing;
      * a job service with a non-empty `Job` (queued, which `is-active` misses;
        measured, see (a) above);
      * the key service `activating`, or with a queued Job, because jobs may be
        queued behind it (After=). The key service being `active` is normal
        (RemainAfterExit=yes).
    A state this code does not know refuses.
    """
    rows = []
    for unit in [*(vj.service for vj in book.jobs), book.secret_unit]:
        props = systemd_show(run_cmd, unit, ["ActiveState", "Job", "MainPID"])
        state = _one(props, "ActiveState", unit).strip()
        job = _one(props, "Job", unit).strip()
        pid = _one(props, "MainPID", unit).strip()
        if state not in BUSY_STATES | IDLE_STATES:
            raise InstallRefused(f"`systemctl show {unit} -p ActiveState` said {state!r}; "
                                 f"cannot confirm no job is running")
        busy = (state == "activating" if unit == book.secret_unit else state in BUSY_STATES)
        if busy or job:
            rows.append({"unit": unit, "state": state, "job": job, "pid": pid})
    return rows


def _describe(row: dict) -> str:
    queued = f", queued job {row['job']}" if row["job"] else ""
    return f"{row['unit']} is {row['state']}{queued}"


def _refuse_if_busy(run_cmd: Callable, book: VmBook = CORE_VM) -> None:
    rows = job_states(run_cmd, book)
    if rows:
        raise InstallRefused(
            f"{'; '.join(_describe(r) for r in rows)}: never install under a running or "
            f"queued job (it could be mid-send, and a checkout would change its code). "
            f"Wait for it to finish (docs/RUNBOOK.md section 8.6)")


def _read_environ(pid: str) -> dict:
    """A running process's environment, from /proc (needs root for another user's)."""
    raw = Path(f"/proc/{pid}/environ").read_bytes().decode("utf-8", "replace")
    return dict(item.split("=", 1) for item in raw.split("\0") if "=" in item)


def _stop_if_a_job_ran(run_cmd: Callable, read_environ: Callable,
                       book: VmBook = CORE_VM) -> None:
    """After the reload, with the timers stopped, no job should run or be queued.
    If one is, name it, its MainPID and the DRY_RUN it STARTED with. That is
    read from /proc, never inferred: an unreadable environment is reported as
    unknown."""
    rows = job_states(run_cmd, book)
    if not rows:
        return
    parts = []
    for r in rows:
        if r["pid"] and r["pid"] != "0":
            try:
                env = read_environ(r["pid"])
                how = (f"started with DRY_RUN={env['DRY_RUN']}" if "DRY_RUN" in env
                       else "started with NO DRY_RUN in its environment")
            except OSError as e:
                how = (f"the DRY_RUN it started with is UNKNOWN: /proc/{r['pid']}/environ "
                       f"unreadable ({type(e).__name__}: {e})")
            parts.append(f"{_describe(r)}, MainPID {r['pid']}, {how}")
        else:
            parts.append(f"{_describe(r)}, not started yet (queued): it will run whatever "
                         f"definition systemd has loaded when it starts")
    raise JobDuringInstall(
        "a quantt job is running or queued after the reload: " + "; ".join(parts)
        + ". " + HALT_ADVICE + ", then check Alpaca for any order it sent")


# -- the plan ---------------------------------------------------------------

@dataclass
class Step:
    text: str
    run: Callable[[], None]


@dataclass
class Plan:
    notes: list
    warnings: list
    steps: list
    rendered: dict       # unit file name -> text
    state: dict          # run-time facts main() reports, e.g. timers this run left stopped


def _mkdir_owned(path: Path, uid: int, gid: int) -> None:
    path.mkdir(exist_ok=True)
    os.chmod(path, 0o700)
    os.chown(path, uid, gid)


def _other_books_live(run_cmd: Callable, layout: Layout, book: VmBook) -> list:
    """For every OTHER book whose unit files are on disk: each of its timers that
    is enabled or running, and each of its jobs that is busy (job_states). A book
    with no unit file installed is never queried, so on a VM with the core alone
    nothing here calls systemctl. Empty means a checkout cannot run under it."""
    out = []
    for other in VM_BOOKS.values():
        if other.name == book.name or not any(layout.unit_path(f).exists()
                                              for f in other.unit_files):
            continue
        for t in other.timers:
            if run_cmd(["systemctl", "is-enabled", "--quiet", t]).returncode == 0:
                out.append(f"{t} is enabled")
            elif _one(systemd_show(run_cmd, t, ["ActiveState"]), "ActiveState", t) == "active":
                out.append(f"{t} is running")
        out += [_describe(r) for r in job_states(run_cmd, other)]
    return out


def _refuse_if_other_books_live(run_cmd: Callable, layout: Layout, book: VmBook,
                                tag: str) -> None:
    """THE CLONE IS SHARED (module comment, books): moving it to `tag` changes the
    code every other installed book's units run. Refuse while one of them can
    start a job or is running one; its units would also still be its old tag's."""
    live = _other_books_live(run_cmd, layout, book)
    if live:
        others = sorted({b.name for b in VM_BOOKS.values() if b.name != book.name})
        raise InstallRefused(
            f"the prod clone is shared, and checking it out at {tag} would change the code "
            f"another book's units run: {'; '.join(live)}. Disable that book's timers "
            f"(`sudo systemctl disable --now` them) and wait for its jobs, install --book "
            f"{book.name}, then re-install --book {'/'.join(others)} at {tag}")


def parse_eod_from(raw: str | None, book: VmBook, now_utc: dt.datetime) -> dt.date | None:
    """`--eod-from`: REQUIRED for a book that needs it (C4), refused for one that
    does not (the core records its own start in quantt/collect). An ISO date
    exactly, on or before today in New York: the account cannot have been funded
    in the future. No default, ever: it dates the official P&L series."""
    if not book.needs_eod_from:
        if raw is not None:
            raise InstallRefused(f"--eod-from is for a book whose account start the collector "
                                 f"does not record itself; --book {book.name} records its own")
        return None
    if raw is None:
        raise InstallRefused(f"--book {book.name} needs --eod-from YYYY-MM-DD: the date its "
                             f"Alpaca paper account was first funded, the team lead's to state "
                             f"(the collector dates the official end-of-day P&L from it). There "
                             f"is no default")
    try:
        d = dt.date.fromisoformat(raw)
    except ValueError:
        d = None
    if d is None or d.isoformat() != raw:
        raise InstallRefused(f"--eod-from {raw!r} is not an ISO date YYYY-MM-DD")
    today = now_utc.astimezone(ZoneInfo(REQUIRED_TZ)).date()
    if d > today:
        raise InstallRefused(f"--eod-from {raw} is after today ({today} ET): the account "
                             f"cannot have been funded in the future")
    return d


def _seed_manifest_checks(seed_from: Path, book: VmBook, git: "Git", commit: str,
                          tag: str) -> tuple:
    """(manifest, its sha256, {file: sha256}) for a book seeded from a manifest
    (C4: `scripts/cef/data_books.py seed-c4` output), or raise naming what fails:
    each seed file's sha256 must be the manifest's, and the manifest must name,
    by sha256, the tag's copy of every file in `book.seed_checks` (the IGR seed
    ruling the team lead ruled the seed is built with, and the frozen universe)."""
    mpath = Path(seed_from) / book.seed_manifest
    if not mpath.is_file():
        raise InstallRefused(f"cannot seed data/{book.data_dir}: {mpath} does not exist (the "
                             f"seed is `scripts/cef/data_books.py seed-c4 --bar-rulings "
                             f"{C4_SEED_RULINGS}` output, manifest included)")
    raw = mpath.read_bytes()
    try:
        man = json.loads(raw)
    except ValueError as e:
        raise InstallRefused(f"{mpath} is not JSON: {e}") from None
    digests = {}
    for name in book.seed_files:
        src = Path(seed_from) / name
        if not src.is_file():
            raise InstallRefused(f"cannot seed data/{book.data_dir}/{name}: {src} does not exist")
        want = ((man.get("files") or {}).get(name) or {}).get("sha256")
        got = ip._sha256(src)
        if got != want:
            raise InstallRefused(f"{src} has sha256 {got[:12]}..., but {mpath.name} records "
                                 f"{str(want)[:12]}...: not the seed the manifest describes")
        digests[name] = got
    for key, rel in book.seed_checks:
        want = hashlib.sha256(git("show", f"{commit}:{rel}", raw=True)).hexdigest()
        named = (man.get(key) or {}).get("sha256") if isinstance(man.get(key), dict) else None
        if named != want:
            raise InstallRefused(
                f"{mpath.name} `{key}` names sha256 {str(named)[:12]}..., not {tag}'s {rel} "
                f"({want[:12]}...): the seed was not built from this release's "
                f"{'ruling' if key == 'bar_rulings' else 'file'}"
                + (" (team lead 2026-10-29: seed with the IGR ruling)" if key == "bar_rulings"
                   else ""))
    return man, hashlib.sha256(raw).hexdigest(), digests


def _manifest_seed_steps(vb: VmBook, data_dir: Path, seed_from, git: "Git", commit: str,
                         tag: str, layout: Layout, uid: int, gid: int,
                         now_utc: dt.datetime) -> list:
    """The seed steps for a book seeded from a manifest (C4; module comment, books).

    Prod's panels are prod's own once seeded, so both present -> left untouched,
    as for the core. Both absent -> copied from `--seed-from`, each checked
    against the manifest (`_seed_manifest_checks`) at planning and again by
    `_copy_verified` as it lands. ONE present and one absent is refused: a NAV
    panel seeded beside a price panel prod has grown on its own would pair rows
    from two histories."""
    present = [n for n in vb.seed_files if (data_dir / n).exists()]
    if len(present) == len(vb.seed_files):
        return [Step(f"leave {data_dir / n} untouched (prod's panels are prod's own)",
                     lambda: None) for n in vb.seed_files]
    if present:
        raise InstallRefused(
            f"{data_dir} holds {present} but not {[n for n in vb.seed_files if n not in present]}: "
            f"a half-seeded panel pair is never completed from a seed. Read what is there "
            f"and decide; the installer will not")
    if seed_from is None:
        raise InstallRefused(
            f"prod has no {data_dir} panels and --seed-from was not given: build the seed on "
            f"the laptop (`python3 scripts/cef/data_books.py seed-c4 --from data/cef_families "
            f"--out DIR --bar-rulings {C4_SEED_RULINGS}`) and copy DIR to the VM "
            f"(results/ops/C4_DRY_RUN_CHECKLIST_2026-10-29.md)")
    man, man_sha, digests = _seed_manifest_checks(Path(seed_from), vb, git, commit, tag)
    ruling = (man.get("bar_rulings") or {}).get("sha256", "")
    steps = []
    for name in vb.seed_files:
        src, dest, digest = Path(seed_from) / name, data_dir / name, digests[name]
        size = src.stat().st_size

        def seed(src=src, dest=dest, digest=digest, size=size):
            for d in (data_dir.parent, data_dir):
                if not d.exists():
                    d.mkdir()
                    os.chown(d, uid, gid)
            if dest.exists():
                raise InstallRefused(f"{dest} appeared since planning; not completing a "
                                     f"half-seeded pair")
            ip._copy_verified(src, dest, digest)
            os.chown(dest, uid, gid)
            with open(layout.seed_log, "a") as fh:
                fh.write(f"{now_utc:%Y-%m-%dT%H:%M:%SZ} seeded {dest} from {src} "
                         f"sha256={digest} bytes={size} release={tag} "
                         f"manifest_sha256={man_sha} bar_rulings_sha256={ruling}\n")
            os.chown(layout.seed_log, uid, gid)
        steps.append(Step(f"copy {src} -> {dest} ({size} bytes, sha256 {digest[:12]}..., as "
                          f"{vb.seed_manifest} records; built with {C4_SEED_RULINGS}), owner "
                          f"{SERVICE_USER}; record it in {layout.seed_log}", seed))
    return steps


def build_plan(*, tag: str, vault: str, layout: Layout, python: Path, armed: bool,
               enable: bool, seed_from, origin_url: str, localtime: Path,
               run_cmd: Callable, as_user: list, euid: int, dont_write_bytecode: bool,
               user_ids: Callable, now_utc: dt.datetime,
               read_environ: Callable = _read_environ,
               clock: Callable = lambda: dt.datetime.now(dt.timezone.utc),
               book: VmBook = CORE_VM, eod_from: str | None = None) -> Plan:
    """Run every check, then return the steps an install would take.

    Everything that can refuse does so HERE, before any step runs. A refusal
    halfway through would leave prod in a state no tag describes.

    `book` is the book whose units are installed (VM_BOOKS; the core by
    default, whose plan is exactly what it was before books existed).
    """
    notes, warnings, steps = [], [], []
    vb = book
    if layout.book != vb.name:
        raise InstallRefused(f"layout is for book {layout.book!r}, not {vb.name!r}")

    if euid != 0:
        raise InstallRefused("must run as root (sudo): it writes /etc/systemd/system "
                             "and runs systemctl")
    if not dont_write_bytecode:
        raise InstallRefused("run python with -B: as root it would otherwise write "
                             "root-owned __pycache__ into the quantt user's clone")
    uid, gid = user_ids(SERVICE_USER)
    zone = ip.system_timezone(localtime)
    if zone != REQUIRED_TZ:
        raise InstallRefused(f"system timezone is {zone}, not {REQUIRED_TZ}; the timers "
                             f"are local wall-clock time written in US/Eastern. Set it: "
                             f"`sudo timedatectl set-timezone {REQUIRED_TZ}`")
    notes.append(f"system timezone {zone}")
    _refuse_if_late(clock, "refusing to install")
    eod = parse_eod_from(eod_from, vb, now_utc)
    try:
        akv.check_vault_name(vault)
    except akv.SecretFetchError as e:
        raise InstallRefused(str(e)) from None
    if not python.is_absolute() or not python.is_file() or not os.access(python, os.X_OK):
        raise InstallRefused(f"--python {python} is not an absolute path to an executable")
    ip.validate_tag(tag)

    prod = layout.prod_dir
    if not (prod / ".git").is_dir():
        raise InstallRefused(f"no prod clone at {prod}; run quantt/deploy/vm/bootstrap.sh first")
    git = Git(prod, as_user, layout.home)
    url = git("remote", "get-url", "origin").strip()
    if url != origin_url:
        raise InstallRefused(f"{prod} is a clone of {url!r}, not of {origin_url!r}")
    dirty = git("status", "--porcelain").strip()
    if dirty:
        raise InstallRefused(f"prod clone {prod} has local modifications; refusing to "
                             f"update over them:\n{dirty}")
    commit = remote_tag_commit(git, origin_url, tag)
    # Fetching changes only .git. A tag that moved on origin is refused by git
    # itself ("would clobber existing tag"), and the comparison below catches
    # anything else.
    git("fetch", "--quiet", "--tags", "origin")
    local = git("rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}",
                allow_fail=True)
    if local is None or local.strip() != commit:
        raise InstallRefused(f"tag {tag} is {commit} on origin but "
                             f"{local.strip() if local else 'absent'} in {prod}; "
                             f"a tag must not move after release")
    notes.append(f"release {tag} = commit {commit} (origin {origin_url})")
    missing = [p for p in vb.required_at_tag
               if git("cat-file", "-e", f"{commit}:{p}", allow_fail=True) is None]
    if missing:
        raise InstallRefused(f"tag {tag} lacks files the VM units need: {', '.join(missing)}")
    _refuse_if_venv_is_stale(git, commit, tag, layout)

    dry_run = "0" if armed else "1"
    env = ip.expected_env(dry_run, layout, vb.env_file, python)
    values = {"TAG": tag, "PYTHON": python, "PROD_DIR": prod, "DRY_RUN": dry_run,
              "STATE_DIR": layout.state_dir, "ENV_FILE": vb.env_file, "PATH": env["PATH"],
              "LOG_DIR": layout.log_dir, "USER": SERVICE_USER, "VAULT": vault}
    # Each job's environment. The core's three are `env`, as always. C4's
    # collector adds QUANTT_EOD_FROM, last (Environment order is pinned).
    job_env = {}
    for vj in vb.jobs:
        job_env[vj.service] = (dict(env, **{EOD_FROM_ENV: eod.isoformat()})
                               if eod is not None and vj.job.log_stem == "collect" else env)
    if eod is not None:
        values["EOD_FROM"] = eod.isoformat()
        notes.append(f"{vb.name}'s paper account first funded {eod} (--eod-from, the team "
                     f"lead's): the collector reads it as {EOD_FROM_ENV}")
    expected = {vb.secret_unit: expected_secret_service(python=python, layout=layout,
                                                        env=env, vault=vault, book=vb)}
    for vj in vb.jobs:
        expected[vj.service] = expected_job_service(vj, python=python, layout=layout,
                                                    env=job_env[vj.service],
                                                    secret_unit=vb.secret_unit)
        expected[vj.timer] = expected_timer(vj)
    rendered = {}
    for unit_file in vb.unit_files:
        assert unit_file.startswith(UNIT_PREFIX), unit_file
        tmpl = git("show", f"{commit}:{template_path(unit_file)}")
        text = render(tmpl, values, unit_file)
        check_unit(text, unit_file, expected[unit_file])
        rendered[unit_file] = text
    # systemd's own parser on every calendar expression: a line this module
    # accepts but systemd reads differently (or rejects) must stop the install.
    # Its "Normalized form" is also what `systemctl show` reports for a loaded
    # timer (Mon..Fri, not Mon,Tue,...), so the post-reload check compares to it.
    normal = {}
    for vj in vb.jobs:
        for expr in oncalendar(vj.job.schedule):
            r = run_cmd(["systemd-analyze", "calendar", expr])
            if r.returncode != 0:
                raise InstallRefused(f"systemd-analyze rejects {vj.timer} OnCalendar={expr!r}: "
                                     f"{(r.stderr or r.stdout).strip()}")
            m = re.search(r"Normalized form:\s*(.+)", r.stdout or "")
            if not m:
                raise InstallRefused(f"systemd-analyze gave no normalized form for {expr!r}")
            normal[expr] = m.group(1).strip()

    # Files on disk first: a drop-in written without daemon-reload is invisible
    # to `systemctl show`, and would go live at this install's own reload.
    _refuse_if_overridden_on_disk(run_cmd, layout, *scan_units(vb))
    # What systemd runs now: no drop-ins, no unit loaded from another file.
    # And no job running, because a checkout or a unit change under a send is
    # never safe.
    current = {u: check_not_overridden(run_cmd, layout, u) for u in vb.unit_files}
    _refuse_if_busy(run_cmd, vb)
    _refuse_if_report_jobs_busy(run_cmd, layout)
    runtime = {vb.secret_unit: {"env": [f"PATH={env['PATH']}",
                                        f"PYTHONUNBUFFERED={env['PYTHONUNBUFFERED']}"],
                                "exec": " ".join(secret_command(python, vault, vb))}}
    for vj in vb.jobs:
        runtime[vj.service] = {"env": [f"{k}={v}" for k, v in job_env[vj.service].items()],
                               "exec": " ".join([str(python), *vj.job.args])}
        runtime[vj.timer] = {"calendar": [normal[e] for e in oncalendar(vj.job.schedule)]}

    timers = vb.timers
    enabled = [t for t in timers if run_cmd(["systemctl", "is-enabled", "--quiet", t]).returncode == 0]
    running = [t for t in timers
               if _one(systemd_show(run_cmd, t, ["ActiveState"]), "ActiveState", t) == "active"]
    secret_on = (run_cmd(["systemctl", "is-enabled", "--quiet", vb.secret_unit]).returncode == 0
                 or _one(systemd_show(run_cmd, vb.secret_unit, ["ActiveState"]), "ActiveState",
                         vb.secret_unit) == "active")

    def active_now(t):
        return _one(systemd_show(run_cmd, t, ["ActiveState"]), "ActiveState", t) == "active"

    # THE END STATE IS SET BY ENABLEMENT (release-check #2, 2026-10-08): after a
    # successful --apply every enabled timer is running, read back from
    # systemd. Restarting only "what was running" let a re-run after a refusal
    # exit 0 with every timer stopped: no decide, no send, no verify line.
    # `targets` is what must be running at the end. A failure reads it back
    # and reports any that are stopped; the run never claims a state it did not read.
    run_state = {"targets": list(timers) if enable else
                 [t for t in timers if t in set(enabled) | set(running)]}
    run_state["stopped_now"] = lambda: [t for t in run_state["targets"] if not active_now(t)]
    run_state["loaded_dry_run"] = lambda: loaded_dry_run(run_cmd, vb)
    run_state["session_service"] = vb.jobs[0].service

    def _refuse_if_disabled_meanwhile():
        """A timer enabled at planning but disabled now was disabled DURING this
        install, most likely halt step 4 (docs/RUNBOOK.md 8.6). The install
        must not undo a halt: no restart, and no --enable (own review pass,
        release-check #5)."""
        dropped = [t for t in enabled
                   if run_cmd(["systemctl", "is-enabled", "--quiet", t]).returncode != 0]
        if dropped:
            raise InstallRefused(
                f"{', '.join(dropped)} was disabled during this install (a halt, "
                f"docs/RUNBOOK.md 8.6 step 4?). Not starting or enabling any timer. "
                f"Re-run the installer once the halt is lifted on purpose")

    def systemctl(*args):
        r = run_cmd(["systemctl", *args])
        if r.returncode != 0:
            raise InstallRefused(f"systemctl {' '.join(args)} failed: "
                                 f"{(r.stderr or r.stdout).strip()}")

    # THE TIMERS ARE STOPPED FIRST (release-check NO-GO, 2026-10-08). Without
    # that, a 15:52 firing between the last busy look and daemon-reload would
    # start the OLD unit (say DRY_RUN=0) while this run reported DRY_RUN=1
    # loaded. With the timers stopped, no firing can start a job until the run
    # restarts them at the end. A refusal after this point leaves them stopped,
    # and says so. The restart DOES replay a slot missed meanwhile (measured
    # (b)), so it is never done inside a late window (_refuse_if_late).
    if running:
        steps.append(Step(f"systemctl stop {' '.join(running)} (no firing can start a job "
                          f"during the install; every enabled timer is started at the end)",
                          lambda: systemctl("stop", *running)))
    steps.append(Step("confirm no quantt job is running or queued",
                      lambda: _refuse_if_busy(run_cmd, vb)))

    # -- code
    head = git("rev-parse", "HEAD").strip()
    if head != commit and not vb.moves_clone:
        # THE CLONE IS SHARED (module comment, books): this book never moves it.
        raise InstallRefused(
            f"the prod clone is at {head}, not {tag} ({commit}): --book {vb.name} runs the "
            f"release the core runs and never checks the clone out (that would change the "
            f"core's code under its units). Install the core at {tag} first, then re-run")
    if head != commit:
        _refuse_if_other_books_live(run_cmd, layout, vb, tag)
        def checkout():
            git("checkout", "--quiet", "--detach", commit)
            now = git("rev-parse", "HEAD").strip()
            if now != commit:
                raise InstallRefused(f"prod HEAD is {now} after checkout, expected {commit}")
        steps.append(Step(f"git -C {prod} checkout --detach {commit} ({tag}) as "
                          f"{SERVICE_USER}; verify HEAD", checkout))
    else:
        notes.append(f"prod clone is already at {commit}")

    # -- state
    def make_state():
        for p in (layout.state_root, layout.state_dir, layout.log_dir):
            _mkdir_owned(p, uid, gid)
    steps.append(Step(f"mkdir {layout.log_dir} (QUANTT_STATE_DIR={layout.state_dir}), "
                      f"mode 700, owner {SERVICE_USER}", make_state))

    # -- data: prod's panels are prod's own once seeded; only absent files are copied
    data_dir = prod / "data" / vb.data_dir
    if vb.seed_manifest is not None:
        steps += _manifest_seed_steps(vb, data_dir, seed_from, git, commit, tag, layout,
                                      uid, gid, now_utc)
    for name in (vb.seed_files if vb.seed_manifest is None else ()):
        dest = data_dir / name
        if dest.exists():
            steps.append(Step(f"leave {dest} untouched (prod's panels are prod's own)",
                              lambda: None))
            continue
        if seed_from is None:
            raise InstallRefused(f"prod has no {dest} and --seed-from was not given: copy "
                                 f"the laptop prod's data/cef files to the VM first "
                                 f"(docs/RUNBOOK.md section 8)")
        src = Path(seed_from) / name
        if not src.is_file():
            raise InstallRefused(f"cannot seed {dest}: {src} does not exist")
        digest = ip._sha256(src)
        size = src.stat().st_size

        def seed(src=src, dest=dest, digest=digest, size=size):
            for d in (data_dir.parent, data_dir):
                if not d.exists():
                    d.mkdir()
                    os.chown(d, uid, gid)
            if dest.exists():
                print(f"  {dest} appeared since planning; left untouched")
                return
            ip._copy_verified(src, dest, digest)
            os.chown(dest, uid, gid)
            # Provenance (RUNBOOK section 8): where prod's first panels came from.
            with open(layout.seed_log, "a") as fh:
                fh.write(f"{now_utc:%Y-%m-%dT%H:%M:%SZ} seeded {dest} from {src} "
                         f"sha256={digest} bytes={size} release={tag}\n")
            os.chown(layout.seed_log, uid, gid)
        steps.append(Step(f"copy {src} -> {dest} ({size} bytes, sha256 {digest[:12]}...), "
                          f"owner {SERVICE_USER}; record it in {layout.seed_log}", seed))

    def still_clean():
        dirty = git("status", "--porcelain").strip()
        if dirty:
            raise InstallRefused(f"prod clone {prod} is dirty after seeding:\n{dirty}")
    steps.append(Step("verify prod clone is still clean (seeded data is gitignored)",
                      still_clean))

    # -- units
    def last_look():
        _refuse_if_busy(run_cmd, vb)
        _refuse_if_overridden_on_disk(run_cmd, layout, *scan_units(vb))
    steps.append(Step(f"confirm again, before the units change, that no quantt-{vb.name} job is "
                      "running and no drop-in is waiting on disk", last_look))
    for unit_file in vb.unit_files:
        dest = layout.unit_path(unit_file)
        was = ""
        loaded_env = current[unit_file].get("Environment", [""])[0].split()
        old_dry = [a.split("=", 1)[1] for a in loaded_env if a.startswith("DRY_RUN=")]
        if old_dry:
            was = f"; systemd currently runs DRY_RUN={old_dry[0]}"

        def write(dest=dest, text=rendered[unit_file]):
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".installing")
            tmp.write_text(text)
            os.chmod(tmp, 0o644)
            os.replace(tmp, dest)
        dr = f" (DRY_RUN={dry_run}{was})" if unit_file.endswith(".service") and \
            unit_file != vb.secret_unit else ""
        steps.append(Step(f"write {dest}{dr}", write))

    steps.append(Step("systemctl daemon-reload (systemd runs the new units from here on)",
                      lambda: systemctl("daemon-reload")))

    def confirm_loaded():
        for unit_file in vb.unit_files:
            verify_loaded(run_cmd, layout, unit_file, runtime[unit_file])
    steps.append(Step("confirm from systemd that every unit is loaded from the file written, "
                      "with no drop-in, and with the expected environment, command and "
                      "calendar", confirm_loaded))

    steps.append(Step("confirm from systemd that no quantt job ran or was queued during "
                      "the install", lambda: _stop_if_a_job_ran(run_cmd, read_environ, vb)))

    # THE KEYS (release-check #2): quantt-secret is oneshot + RemainAfterExit, so
    # unless it is restarted, /run/quantt/alpaca.env keeps the keys fetched for
    # the OLD unit (another vault, or keys since rotated) while the run reports
    # success. It is re-fetched on every apply, now, while the timers are stopped
    # and no job is busy, so restarting it (which removes and re-creates
    # /run/quantt) cannot pull the file from under a job.
    if enable:
        steps.append(Step(f"systemctl enable {vb.secret_unit} (the keys at every boot)",
                          lambda: systemctl("enable", vb.secret_unit)))
    if enable or secret_on:
        def refresh_keys():
            systemctl("restart", vb.secret_unit)
            st = _one(systemd_show(run_cmd, vb.secret_unit, ["ActiveState"]), "ActiveState",
                      vb.secret_unit)
            if st != "active":
                raise InstallRefused(f"{vb.secret_unit} is {st} after its restart; the keys "
                                     f"were not fetched (see its log, secret.err.log)")
            _confirm_key_file(layout, uid, vb)
        steps.append(Step(f"systemctl restart {vb.secret_unit} (re-fetch the keys for the unit "
                          f"just loaded, while no job can run); confirm it is active and "
                          f"{vb.env_file} is a 0600 file owned by {SERVICE_USER} (stat only)",
                          refresh_keys))

    if enable:
        def enable_timers():
            _refuse_if_late(clock, "not restarting the timers", RESTART_REFUSE_RANGES_ET)
            _refuse_if_disabled_meanwhile()
            systemctl("enable", "--now", *timers)
        steps.append(Step(f"systemctl enable --now {' '.join(timers)} (not inside a late "
                          f"window: a restart there could replay a send slot)", enable_timers))
    else:
        def start_enabled():
            _refuse_if_late(clock, "not restarting the timers", RESTART_REFUSE_RANGES_ET)
            _refuse_if_disabled_meanwhile()
            now_enabled = {t for t in timers
                           if run_cmd(["systemctl", "is-enabled", "--quiet", t]).returncode == 0}
            run_state["targets"] = [t for t in timers if t in now_enabled | set(running)]
            if run_state["targets"]:
                systemctl("start", *run_state["targets"])
        steps.append(Step("systemctl start every enabled timer (and any that was running "
                          "before this install), not inside a late window: a restart there "
                          "could replay a send slot", start_enabled))

    def read_back():
        want = run_state["targets"]
        states = {t: _one(systemd_show(run_cmd, t, ["ActiveState"]), "ActiveState", t)
                  for t in want}
        bad = [t for t in want if states[t] != "active"]
        if bad:
            raise InstallRefused(
                f"{', '.join(f'{t} is {states[t]}' for t in bad)}: not active after the "
                f"start, so it will not fire (see `systemctl status {bad[0]}`)")
        print(f"  timers active (read back from systemd): "
              f"{', '.join(want) if want else 'none (no timer is enabled)'}")
    steps.append(Step("read back from systemd that every enabled timer is active", read_back))

    if not enable:
        notes.append(f"timers enabled now: {', '.join(enabled) or 'none'}; running now: "
                     f"{', '.join(running) or 'none'}. The run ends by starting every enabled "
                     f"timer and reading back that each is active"
                     + ("" if enabled or running else
                        " (none is enabled, so none will run: NOT enabled by this run; pass "
                        "--apply --enable)"))

    if armed:
        warnings.append(f"ARMED: units get DRY_RUN=0. A scheduled session also needs "
                        f"{layout.state_dir}/AUTO_ARMED to transmit (docs/RUNNER.md gate 2)")
    return Plan(notes, warnings, steps, rendered, run_state)


def expected_report_service(vj: VmJob, *, python: Path, layout: Layout, env: dict) -> dict:
    """The contract for a report service (module comment, report units). The dataqa
    and risk jobs have no broker key file (no DRY_RUN either: a report has no order path
    to dry-run), and take no panel lock; the pnl job's only credential is its own
    per-book env file (the P&L report kind) and it takes no lock either."""
    book, kind = vj.unit.split("-")[1], vj.unit.split("-")[2]
    logs = layout.state_root / book / "logs"
    if kind == "risk":
        unit = [("Wants", REPORT_SECRET_UNIT), ("After", REPORT_SECRET_UNIT)]
    elif kind == "pnl":
        unit = [("Wants", REPORT_PNL_KEY_UNITS[book]), ("After", REPORT_PNL_KEY_UNITS[book])]
    else:
        unit = []
    env_files = ([("EnvironmentFile", f"-{REPORT_ENV_FILE}")] if kind == "risk"
                 else [("EnvironmentFile", f"-{REPORT_PNL_KEYS[book].env_file}")] if kind == "pnl" else [])
    svc = [("Type", "oneshot"), ("User", SERVICE_USER), ("Group", SERVICE_USER),
           ("WorkingDirectory", str(layout.prod_dir)),
           ("Environment", f"PATH={env['PATH']}"), ("Environment", "PYTHONUNBUFFERED=1"),
           ("Environment", f"QUANTT_STATE_DIR={layout.state_root / book}"),
           *env_files,
           ("ExecStart", " ".join([str(python), *vj.job.args])),
           ("ReadOnlyPaths", str(layout.prod_dir)),
           ("MemoryMax", REPORT_PNL_MEMORY_MAX if kind == "pnl" else REPORT_MEMORY_MAX), ("Nice", "10"),
           ("TimeoutStartSec", str(REPORT_TIMEOUT_S)),
           ("StandardOutput", f"append:{logs}/{kind}.out.log"),
           ("StandardError", f"append:{logs}/{kind}.err.log")]
    return {"Unit": unit, "Service": svc}


def _report_template(unit_file: str) -> str:
    if unit_file == REPORT_SECRET_UNIT:
        return REPORT_TEMPLATES["secret"]
    if unit_file in REPORT_PNL_KEY_UNITS.values():
        return REPORT_TEMPLATES["pnl_keys"]
    if unit_file.endswith(".timer"):
        return REPORT_TEMPLATES["timer"]
    return REPORT_TEMPLATES[unit_file.split("-")[2].split(".")[0]]


def build_report_plan(*, tag: str, vault: str, layout: Layout, python: Path, enable: bool,
                      origin_url: str, localtime: Path, run_cmd: Callable, as_user: list, euid: int,
                      dont_write_bytecode: bool, user_ids: Callable,
                      clock: Callable = lambda: dt.datetime.now(dt.timezone.utc)) -> Plan:
    """`--reports`: install the report-only units (module comment, report units) and
    touch NOTHING that belongs to a book: no session, verify or collect unit, timer
    or key service is written, stopped, started or restarted. The checks are the
    book install's: root, -B, zone, late window, vault name, clean clone at the tag,
    templates checked key by key, systemd's own parser on every calendar line, the
    drop-in scan, no job busy, and what systemd loaded read back."""
    notes, warnings, steps = [], [], []
    if euid != 0:
        raise InstallRefused("must run as root (sudo): it writes /etc/systemd/system")
    if not dont_write_bytecode:
        raise InstallRefused("run python with -B: as root it would otherwise write root-owned "
                             "__pycache__ into the quantt user's clone")
    uid, gid = user_ids(SERVICE_USER)
    zone = ip.system_timezone(localtime)
    if zone != REQUIRED_TZ:
        raise InstallRefused(f"system timezone is {zone}, not {REQUIRED_TZ}: the report timers are local "
                             f"wall-clock times")
    _refuse_if_late(clock, "refusing to install")
    try:
        akv.check_vault_name(vault)
    except akv.SecretFetchError as e:
        raise InstallRefused(str(e)) from None
    if not python.is_absolute() or not python.is_file() or not os.access(python, os.X_OK):
        raise InstallRefused(f"--python {python} is not an absolute path to an executable")
    ip.validate_tag(tag)
    prod = layout.prod_dir
    if not (prod / ".git").is_dir():
        raise InstallRefused(f"no prod clone at {prod}; run quantt/deploy/vm/bootstrap.sh first")
    git = Git(prod, as_user, layout.home)
    url = git("remote", "get-url", "origin").strip()
    if url != origin_url:
        raise InstallRefused(f"{prod} is a clone of {url!r}, not of {origin_url!r}")
    dirty = git("status", "--porcelain").strip()
    if dirty:
        raise InstallRefused(f"prod clone {prod} has local modifications; refusing:\n{dirty}")
    commit = remote_tag_commit(git, origin_url, tag)
    git("fetch", "--quiet", "--tags", "origin")
    local = git("rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}", allow_fail=True)
    if local is None or local.strip() != commit:
        raise InstallRefused(f"tag {tag} is {commit} on origin but "
                             f"{local.strip() if local else 'absent'} in {prod}")
    head = git("rev-parse", "HEAD").strip()
    if head != commit:                  # the report units never move the clone (a book install does)
        raise InstallRefused(f"the prod clone is at {head}, not {tag} ({commit}): install the core at "
                             f"{tag} first, then re-run --reports")
    notes.append(f"release {tag} = commit {commit}; the report units run the clone as it stands")
    missing = [p for p in REPORT_VM.required_at_tag
               if git("cat-file", "-e", f"{commit}:{p}", allow_fail=True) is None]
    if missing:
        raise InstallRefused(f"tag {tag} lacks files the report units need: {', '.join(missing)}")
    _refuse_if_venv_is_stale(git, commit, tag, layout)

    env = ip.expected_env("1", layout, REPORT_ENV_FILE, python)     # PATH and the like; never a key file
    expected, rendered = {}, {}
    for vj in REPORT_JOBS:
        book, kind = vj.unit.split("-")[1], vj.unit.split("-")[2]
        logs = layout.state_root / book / "logs"
        hour, minute = REPORT_SCHEDULE[(kind, book)]
        values = {"TAG": tag, "PYTHON": python, "PROD_DIR": prod, "STATE_DIR": layout.state_root / book,
                  "LOG_DIR": logs, "USER": SERVICE_USER, "PATH": env["PATH"], "BOOK": book, "KIND": kind,
                  "MODULE": REPORT_KINDS[kind], "HOUR": f"{hour:02d}", "MINUTE": f"{minute:02d}",
                  "SERVICE": vj.service, "MEMORY_MAX": REPORT_MEMORY_MAX, "TIMEOUT_S": REPORT_TIMEOUT_S,
                  "ENV_FILE": REPORT_ENV_FILE, "SECRET_UNIT": REPORT_SECRET_UNIT}
        if kind == "pnl":
            values.update(ENV_FILE=REPORT_PNL_KEYS[book].env_file, SECRET_UNIT=REPORT_PNL_KEY_UNITS[book],
                          MEMORY_MAX=REPORT_PNL_MEMORY_MAX)
        expected[vj.service] = expected_report_service(vj, python=python, layout=layout, env=env)
        expected[vj.timer] = expected_timer(vj)
        for f in (vj.service, vj.timer):
            tmpl = git("show", f"{commit}:{TEMPLATE_DIR}/{_report_template(f)}")
            text = render(tmpl, values, f)
            check_unit(text, f, expected[f])
            rendered[f] = text
    sec_values = {"TAG": tag, "PYTHON": python, "PROD_DIR": prod, "USER": SERVICE_USER, "PATH": env["PATH"],
                  "VAULT": vault, "ENV_FILE": REPORT_ENV_FILE, "LOG_DIR": layout.state_root / BOOK / "logs",
                  "RUNTIME_DIR": REPORT_RUNTIME_DIR}
    sec = expected_secret_service(python=python, layout=replace(layout, book=BOOK), env=env, vault=vault,
                                  book=REPORT_VM)
    # its own log files, so a fetch failure here never reads as the core's Alpaca-key service
    sec["Service"] = [(k, v.replace("/secret.out.log", "/reports-secret.out.log")
                       .replace("/secret.err.log", "/reports-secret.err.log")) for k, v in sec["Service"]]
    expected[REPORT_SECRET_UNIT] = sec
    tmpl = git("show", f"{commit}:{TEMPLATE_DIR}/{REPORT_TEMPLATES['secret']}")
    rendered[REPORT_SECRET_UNIT] = render(tmpl, sec_values, REPORT_SECRET_UNIT)
    check_unit(rendered[REPORT_SECRET_UNIT], REPORT_SECRET_UNIT, expected[REPORT_SECRET_UNIT])
    # The pnl jobs' broker keys, one service and one tmpfs env file per book (module comment).
    for book, key_vm in REPORT_PNL_KEYS.items():
        key_log = layout.state_root / book / "logs"
        key_expected = expected_secret_service(python=python, layout=replace(layout, book=book), env=env, vault=vault,
                                               book=key_vm)
        key_expected["Service"] = [(k, v.replace("/secret.out.log", "/reports-pnl-keys.out.log")
                                    .replace("/secret.err.log", "/reports-pnl-keys.err.log"))
                                   for k, v in key_expected["Service"]]
        # The pnl job's own promise (-B, a read-only clone) applied to its key service. In these
        # two units only: the books' own secret services and `secret_command` are not changed.
        svc = key_expected["Service"]
        svc.insert(svc.index(("Environment", f"PYTHONUNBUFFERED={env['PYTHONUNBUFFERED']}")) + 1,
                   ("Environment", "PYTHONDONTWRITEBYTECODE=1"))
        svc.append(("ReadOnlyPaths", str(prod)))
        unit = key_vm.secret_unit
        expected[unit] = key_expected
        key_values = {"TAG": tag, "PYTHON": python, "PROD_DIR": prod, "USER": SERVICE_USER, "PATH": env["PATH"],
                      "VAULT": vault, "ENV_FILE": key_vm.env_file, "LOG_DIR": key_log, "BOOK": book,
                      "RUNTIME_DIR": key_vm.runtime_dir, "KEY_ID_SECRET": key_vm.secret_map[0][0],
                      "KEY_ID_VAR": key_vm.secret_map[0][1], "SECRET_SECRET": key_vm.secret_map[1][0],
                      "SECRET_VAR": key_vm.secret_map[1][1]}
        tmpl = git("show", f"{commit}:{TEMPLATE_DIR}/{REPORT_TEMPLATES['pnl_keys']}")
        rendered[unit] = render(tmpl, key_values, unit)
        check_unit(rendered[unit], unit, expected[unit])

    normal = {}
    for vj in REPORT_JOBS:
        for expr in oncalendar(vj.job.schedule):
            r = run_cmd(["systemd-analyze", "calendar", expr])
            if r.returncode != 0:
                raise InstallRefused(f"systemd-analyze rejects {vj.timer} OnCalendar={expr!r}: "
                                     f"{(r.stderr or r.stdout).strip()}")
            m = re.search(r"Normalized form:\s*(.+)", r.stdout or "")
            if not m:
                raise InstallRefused(f"systemd-analyze gave no normalized form for {expr!r}")
            normal[expr] = m.group(1).strip()

    every = tuple(dict.fromkeys(f for b in VM_BOOKS.values() for f in b.unit_files)) + REPORT_UNIT_FILES
    _refuse_if_overridden_on_disk(run_cmd, layout, every, ("quantt-",))
    for u in REPORT_UNIT_FILES:
        check_not_overridden(run_cmd, layout, u)
    for vb in (*VM_BOOKS.values(), REPORT_VM):
        _refuse_if_busy(run_cmd, vb)

    timers = REPORT_VM.timers
    enabled = [t for t in timers if run_cmd(["systemctl", "is-enabled", "--quiet", t]).returncode == 0]
    running = [t for t in timers if _one(systemd_show(run_cmd, t, ["ActiveState"]), "ActiveState", t) == "active"]

    def active_now(t):
        return _one(systemd_show(run_cmd, t, ["ActiveState"]), "ActiveState", t) == "active"

    run_state = {"reports": True, "targets": list(timers) if enable else
                 [t for t in timers if t in set(enabled) | set(running)]}
    run_state["stopped_now"] = lambda: [t for t in run_state["targets"] if not active_now(t)]

    def systemctl(*args):
        r = run_cmd(["systemctl", *args])
        if r.returncode != 0:
            raise InstallRefused(f"systemctl {' '.join(args)} failed: {(r.stderr or r.stdout).strip()}")

    if running:
        steps.append(Step(f"systemctl stop {' '.join(running)} (report timers only; no session timer is touched)",
                          lambda: systemctl("stop", *running)))
    steps.append(Step("confirm no report job is running or queued",
                      lambda: _refuse_if_busy(run_cmd, REPORT_VM)))

    def make_dirs():
        for b in REPORT_BOOKS:
            for p in (layout.state_root, layout.state_root / b, layout.state_root / b / "logs",
                      layout.state_root / b / "reports"):
                _mkdir_owned(p, uid, gid)
    steps.append(Step(f"mkdir {layout.state_root}/<book>/reports and logs for {list(REPORT_BOOKS)}, "
                      f"mode 700, owner {SERVICE_USER}", make_dirs))

    def still_clean():
        dirty = git("status", "--porcelain").strip()
        if dirty:
            raise InstallRefused(f"prod clone {prod} is dirty:\n{dirty}")
    steps.append(Step("verify prod clone is still clean", still_clean))

    def last_look():
        _refuse_if_busy(run_cmd, REPORT_VM)
        _refuse_if_overridden_on_disk(run_cmd, layout, every, ("quantt-",))
    steps.append(Step("confirm again that no report job is running and no drop-in is waiting on disk", last_look))
    for unit_file in REPORT_UNIT_FILES:
        dest = layout.unit_path(unit_file)

        def write(dest=dest, text=rendered[unit_file]):
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".installing")
            tmp.write_text(text)
            os.chmod(tmp, 0o644)
            os.replace(tmp, dest)
        steps.append(Step(f"write {dest}", write))
    steps.append(Step("systemctl daemon-reload", lambda: systemctl("daemon-reload")))

    runtime = {REPORT_SECRET_UNIT: {"env": [f"PATH={env['PATH']}", f"PYTHONUNBUFFERED={env['PYTHONUNBUFFERED']}"],
                                    "exec": " ".join(secret_command(python, vault, REPORT_VM))}}
    for book, key_vm in REPORT_PNL_KEYS.items():
        runtime[key_vm.secret_unit] = {"env": [f"PATH={env['PATH']}", f"PYTHONUNBUFFERED={env['PYTHONUNBUFFERED']}",
                                               "PYTHONDONTWRITEBYTECODE=1"],
                                       "exec": " ".join(secret_command(python, vault, key_vm))}
    for vj in REPORT_JOBS:
        book = vj.unit.split("-")[1]
        runtime[vj.service] = {"env": [f"PATH={env['PATH']}", "PYTHONUNBUFFERED=1",
                                       f"QUANTT_STATE_DIR={layout.state_root / book}"],
                               "exec": " ".join([str(python), *vj.job.args])}
        runtime[vj.timer] = {"calendar": [normal[e] for e in oncalendar(vj.job.schedule)]}

    def confirm_loaded():
        for unit_file in REPORT_UNIT_FILES:
            verify_loaded(run_cmd, layout, unit_file, runtime[unit_file])
    steps.append(Step("confirm from systemd that every report unit is loaded from the file written, "
                      "with no drop-in and the expected environment, command and calendar", confirm_loaded))
    if enable:
        steps.append(Step(f"systemctl enable --now {' '.join(timers)}", lambda: systemctl("enable", "--now", *timers)))
    else:
        def start_enabled():
            now_on = {t for t in timers if run_cmd(["systemctl", "is-enabled", "--quiet", t]).returncode == 0}
            run_state["targets"] = [t for t in timers if t in now_on | set(running)]
            if run_state["targets"]:
                systemctl("start", *run_state["targets"])
        steps.append(Step("systemctl start every report timer that is enabled or was running", start_enabled))

    def read_back():
        states = {t: _one(systemd_show(run_cmd, t, ["ActiveState"]), "ActiveState", t)
                  for t in run_state["targets"]}
        bad = [t for t, st in states.items() if st != "active"]
        if bad:
            raise InstallRefused(f"{', '.join(bad)} not active after the start (see `systemctl status {bad[0]}`)")
        print(f"  report timers active (read back from systemd): {', '.join(states) or 'none enabled'}")
    steps.append(Step("read back from systemd that every report timer that should run is active", read_back))
    warnings.append(f"the ACT push needs the vault secrets {[s for s, _ in REPORT_SECRET_MAP]} (the team lead's "
                    f"step): until they exist, {REPORT_SECRET_UNIT} fails on each try and a fired stop "
                    f"exits non-zero with `ACT: notification NOT delivered` (docs/RUNBOOK.md 8.11)")
    warnings.append(f"the pnl units read each book's own Alpaca key from the vault into their own tmpfs env file "
                    f"{sorted(str(v.env_file) for v in REPORT_PNL_KEYS.values())} (the same secrets the books' key "
                    f"services already use: {[s for k in REPORT_PNL_KEYS.values() for s, _ in k.secret_map]}); "
                    f"the dataqa and risk units stay key-free (docs/RUNBOOK.md 8.12)")
    notes.append(f"timers enabled now: {', '.join(enabled) or 'none'}; running now: {', '.join(running) or 'none'}")
    return Plan(notes, warnings, steps, rendered, run_state)


def loaded_dry_run(run_cmd: Callable, book: VmBook = CORE_VM) -> str:
    """`DRY_RUN=<x>` as systemd has it LOADED for the session unit, or
    `DRY_RUN UNKNOWN (<why>)`. It is read, never inferred from a file or flag."""
    unit = book.jobs[0].service
    try:
        env = _one(systemd_show(run_cmd, unit, ["Environment"]), "Environment", unit).split()
    except Exception as e:                       # reported as UNKNOWN, never guessed
        return f"DRY_RUN UNKNOWN ({type(e).__name__}: {e})"
    vals = [a.split("=", 1)[1] for a in env if a.startswith("DRY_RUN=")]
    return f"DRY_RUN={vals[0]}" if len(vals) == 1 else \
        f"DRY_RUN UNKNOWN (systemd reports {len(vals)} DRY_RUN values)"


def _report_stopped_timers(plan: Plan) -> None:
    """After a failed step: which timers that must be running are not, READ
    BACK from systemd. If the read fails, say so; never claim either way.

    Starting them is an order-path act (release-check #4): inside 15:52-15:58
    ET, a start replays the missed send slot (M1, measured), which means a
    late and possibly partial send. So the advice prefers re-running the
    installer, which enforces the window guard. It names the late windows, and
    the DRY_RUN systemd has LOADED, because that is what a start would run.
    """
    if plan.state.get("reports"):                # no session timer was touched by a --reports run
        try:
            stopped = plan.state["stopped_now"]()
        except Exception as e:                   # reported, never swallowed, and the caller still fails
            print(f"report timers: could not read their state back ({type(e).__name__}: {e}); "
                  f"check `systemctl list-timers 'quantt-*'`")
            return
        if stopped:
            print(f"report timers left STOPPED: {' '.join(stopped)}. No session timer was touched. "
                  f"Re-run the installer with --reports to start them")
        return
    try:
        stopped = plan.state["stopped_now"]()
    except Exception as e:                       # reported, and the caller still fails
        print(f"timers: could not read their state back ({type(e).__name__}: {e}); "
              f"treat them as STOPPED and check `systemctl list-timers 'quantt-*'`")
        return
    if stopped:
        loaded = plan.state["loaded_dry_run"]()
        print(f"timers left STOPPED: {' '.join(stopped)}. Nothing will run until they are "
              f"started. Prefer to re-run the installer: it refuses inside the late windows. "
              f"If you start them by hand, NOT on a weekday inside 15:40-16:00 or "
              f"12:40-13:00 ET; wait until after 16:00 (13:00 on an early close). A start "
              f"there replays the missed send slot: a late, possibly partial send. "
              f"systemd has {loaded} LOADED for "
              f"{plan.state.get('session_service', VM_JOBS[0].service)}, and that is "
              f"what starting them would run "
              f"(`sudo systemctl start {' '.join(stopped)}`)")


def main(argv=None, *, layout: Layout | None = None, origin_url: str = ORIGIN_URL,
         localtime: Path = Path("/etc/localtime"), run_cmd: Callable = _real_run,
         as_user: list | None = None, euid: int | None = None,
         dont_write_bytecode: bool | None = None, user_ids: Callable = _user_ids,
         now_utc: dt.datetime | None = None, read_environ: Callable | None = None,
         clock: Callable | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tag", required=True, help="release tag, already pushed to origin")
    # The vault help names every secret an install's key services read, from the same maps the
    # services render. It once named only the core's two, though --book c4 reads C4's two and
    # --reports reads both books' (its pnl key services) and the two SMTP secrets (its alert
    # secret service) (second review of PR #82, 2026-11-11).
    _names = lambda pairs: ", ".join(s for s, _ in pairs)
    vault_help = "; ".join(f"--book {b}: {_names(vm.secret_map)}" for b, vm in VM_BOOKS.items())
    vault_help += (f"; --reports: {_names(p for b in REPORT_BOOKS for p in REPORT_PNL_KEYS[b].secret_map)} "
                   f"(the pnl key services) and {_names(REPORT_SECRET_MAP)} ({REPORT_SECRET_UNIT})")
    ap.add_argument("--vault", required=True,
                    help=f"Azure Key Vault name (no default) holding the secrets the install's key services "
                         f"read: {vault_help}")
    ap.add_argument("--seed-from", type=Path, default=None,
                    help="directory holding the laptop prod's data/cef files; needed "
                         "only while prod lacks them")
    ap.add_argument("--apply", action="store_true", help="act (default: dry run)")
    ap.add_argument("--enable", action="store_true",
                    help="with --apply: enable and start the timers and the key service")
    ap.add_argument("--armed", action="store_true", help="render DRY_RUN=0 (default DRY_RUN=1)")
    ap.add_argument("--python", type=Path, default=None,
                    help="interpreter the units run (default: /home/quantt/venv/bin/python)")
    ap.add_argument("--book", choices=sorted(VM_BOOKS), default=BOOK,
                    help=f"whose units to install (default {BOOK}, the core; {C4_BOOK} installs "
                         f"C4's own units beside the core's and touches none of them)")
    # The help names every unit --reports writes. It once said "the report-only data-QA and
    # risk units" after the pnl units and their key services were added, which read each
    # book's Alpaca key from the vault (independent review of PR #82, 2026-11-11); the names
    # come from the same constants the install renders, so they cannot drift from it. The
    # kind list too: it was the literal "data-QA, risk and pnl" until the second review of
    # PR #82 (2026-11-11), so a fourth kind in REPORT_KINDS would have been left out of it.
    kinds = list(REPORT_KINDS)
    ap.add_argument("--reports", action="store_true",
                    help=(f"install the report-only units instead of a book's: the "
                          f"{', '.join(kinds[:-1])} and {kinds[-1]} units of each book "
                          f"({', '.join(REPORT_BOOKS)}; quantt-<book>-<kind>), the alert secret service "
                          f"{REPORT_SECRET_UNIT}, and the two pnl key services "
                          f"{' and '.join(REPORT_PNL_KEY_UNITS[b] for b in REPORT_BOOKS)}, which read each "
                          f"book's Alpaca key from the vault into a tmpfs env file of its own; touches no "
                          f"session unit (docs/RUNBOOK.md 8.11, 8.12)"))
    ap.add_argument("--eod-from", default=None, metavar="YYYY-MM-DD",
                    help=f"REQUIRED with --book {C4_BOOK}, no default: the date its paper "
                         f"account was first funded (the team lead's)")
    a = ap.parse_args(argv)
    if a.enable and not a.apply:
        ap.error("--enable needs --apply: enabled timers are what trade")
    if a.reports and (a.book != BOOK or a.seed_from is not None or a.eod_from is not None or a.armed):
        ap.error("--reports takes only --tag, --vault, --python, --apply and --enable")

    # The layout for the book being installed (its state dir); the core's is the
    # one it always was.
    layout = replace(layout or Layout(Path("/home") / SERVICE_USER), book=a.book)
    try:
        lock_fd = acquire_install_lock(layout.sysroot / INSTALL_LOCK.relative_to("/"))
    except InstallRefused as e:
        print(f"REFUSED: {e}")
        return 2
    try:
        return _main_locked(a, layout, origin_url=origin_url, localtime=localtime,
                            run_cmd=run_cmd, as_user=as_user, euid=euid,
                            dont_write_bytecode=dont_write_bytecode, user_ids=user_ids,
                            now_utc=now_utc, read_environ=read_environ, clock=clock)
    finally:
        os.close(lock_fd)                        # released on success, refusal and exception


def _main_locked(a, layout: Layout, *, origin_url, localtime, run_cmd, as_user, euid,
                 dont_write_bytecode, user_ids, now_utc, read_environ, clock) -> int:
    try:
        if a.reports:
            plan = build_report_plan(
                tag=a.tag, vault=a.vault, layout=layout, python=a.python or layout.venv_python,
                enable=a.enable, origin_url=origin_url, localtime=localtime, run_cmd=run_cmd,
                as_user=as_user if as_user is not None else ["runuser", "-u", SERVICE_USER, "--"],
                euid=os.geteuid() if euid is None else euid,
                dont_write_bytecode=(sys.flags.dont_write_bytecode
                                     if dont_write_bytecode is None else dont_write_bytecode),
                user_ids=user_ids, clock=clock or (lambda: dt.datetime.now(dt.timezone.utc)))
        else:
            plan = build_plan(
                tag=a.tag, vault=a.vault, layout=layout, python=a.python or layout.venv_python,
                armed=a.armed, enable=a.enable, seed_from=a.seed_from, origin_url=origin_url,
                localtime=localtime, run_cmd=run_cmd,
                as_user=as_user if as_user is not None else ["runuser", "-u", SERVICE_USER, "--"],
                euid=os.geteuid() if euid is None else euid,
                dont_write_bytecode=(sys.flags.dont_write_bytecode
                                     if dont_write_bytecode is None else dont_write_bytecode),
                user_ids=user_ids, now_utc=now_utc or dt.datetime.now(dt.timezone.utc),
                read_environ=read_environ or _read_environ,
                clock=clock or (lambda: dt.datetime.now(dt.timezone.utc)),
                book=VM_BOOKS[a.book], eod_from=a.eod_from)
    except InstallRefused as e:
        print(f"REFUSED: {e}")
        return 2

    for n in plan.notes:
        print(f"note: {n}")
    for w in plan.warnings:
        print(f"WARNING: {w}")
    verb = "DOING" if a.apply else "WOULD"
    for i, s in enumerate(plan.steps, 1):
        print(f"{verb} {i}. {s.text}")
        if a.apply:
            try:
                s.run()
            except InstallRefused as e:
                alert = isinstance(e, JobDuringInstall)
                print(f"{'ALERT' if alert else 'REFUSED'} at step {i}: {e}")
                _report_stopped_timers(plan)
                return EXIT_JOB_DURING_INSTALL if alert else 2
            except BaseException:
                # Not swallowed: re-raised with its traceback. But the operator
                # must still learn that the timers may be stopped.
                print(f"ERROR at step {i}: unexpected exception (traceback follows)")
                _report_stopped_timers(plan)
                raise
    if not a.apply:
        for name, text in plan.rendered.items():
            print(f"\n----- {layout.unit_path(name)} (rendered, not written)\n{text}")
        print("\nDRY RUN: nothing was written (tags were fetched into the clone's .git). "
              "Re-run with --apply to act.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
