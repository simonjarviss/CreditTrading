"""One-off repair: fill prod's empty 2026 ex-date closes from Alpaca's official closing print.

Runs ON THE VM, as `quantt`, with PROD's code at its release tag. The script travels
on stdin, so nothing but the prod clone is needed there (`vmrelease.sh repair-dry`
and `repair-apply` on the team lead's laptop wrap exactly this):

    ssh quantt-vm "sudo -u quantt env HOME=/home/quantt \\
        PYTHONPATH=/home/quantt/prod/quantt-alpaca \\
        QUANTT_STATE_DIR=/home/quantt/quantt_state/cef QUANTT_ENV_FILE=/run/quantt/alpaca.env \\
        /home/quantt/venv/bin/python -B -P - [--apply --plan <digest>]" < ops/repair_empty_closes.py

`-P` keeps the caller's working directory off sys.path, and `-B` writes no
__pycache__ into the prod clone (quantt/deploy/install_vm.py runs the same way).

WHY THIS EXISTS (approved by the team lead 2026-10-28, after a measurement)
--------------------------------------------------------------------------
Until release-20261028-1, `scripts/cef/fetch_daily.py` merged yfinance's EMPTY
ex-date rows unchecked: when Yahoo carries a dividend for a date with no bar,
yfinance emits a row with every price NaN and volume 0, and that row replaced a
good bar (fetch_daily's docstring, EMPTY ROWS). Prod's panel on the VM held 91
such rows on 44 funds' own ex-dates between 2026-02-12 and 2026-04-23
[V: read-only copy of prod's panels taken 2026-10-28T20:36Z], 24 of them on the
live 13. The fixed fetcher repairs an empty row only when yfinance re-sends that
date with a close, and it refetches six months: these rows are older than that,
so nothing will ever repair them. Measured on that copy (2026-10-28, the live
sleeve at the release tag): filling them moves the 2026-10-28 plan's weights by
at most 0.0008 and turns PTY's -0.0053 flat. Small, but the discount's rolling
mean and sd run over these dates for most of a year, and an empty close is not a
close.

WHERE THE CLOSE COMES FROM, AND NOWHERE ELSE
--------------------------------------------
The source the collector treats as primary for a close: Alpaca's official
closing-auction print, from the primary listing exchange, condition `M`
("Market Center Official Close"), one symbol per query, exactly as
`quantt/collect/collect.py` `step_official_closes` fetches it
(`primary_sip_code` + `closing_auction_prints`), and whose gaps it classifies
with the collector's own `FINAL_PRINT_GAPS`. That step records it as "alpaca
official close (M, primary)" and cross-checks the yfinance close against it.
The functions are imported from prod's clone, never copied. A daily bar is NOT
used: its close is set by condition 6, not M (`MissingAuctionPrint`'s docstring,
alpaca.py), so it is a different number.

A cell for which the source gives no print (MissingAuctionPrint, AssetNotFound,
UnmappedExchange: the collector's final gaps) is LEFT EMPTY and reported as NO
PRINT. One the source could not answer (any other AlpacaError, including an
ambiguous primary print: the collector retries those) is left empty and
reported as NOT MEASURED. Nothing is ever filled from another venue, a bar, a
neighbouring day or the laptop's panel, and nothing is guessed.

WHAT IS NOT WRITTEN, AND WHY
----------------------------
An auction print carries a price and nothing else the panel holds: no day
volume, no open, no high, no low. So only `close` is written.

  * open/high/low stay as the panel holds them for these rows: NaN. fetch_daily
    writes all four prices from ONE bar, and keeps no row whose source lacks
    them; inventing o = h = l = close would be a number with no source. Nothing
    on the live path reads them (the sleeve reads close, NAV and volume).
  * volume stays 0, the value yfinance filled into the empty row; it is NOT a
    measurement (fetch_daily, EMPTY ROWS). The column is int64 and holds no
    NaN anywhere, so blanking it would change the column's dtype, which the
    post-check forbids, and the print's auction size is not the day's volume.
    Effect: the sleeve's ADV is `(close * volume).rolling(63).mean().shift(1)`,
    so a repaired row counts as a zero-dollar day inside any 63-session window
    that contains it. On the panel copy above, the 63 sessions to 2026-10-27
    start on 2026-07-30, after every empty date, so today's plan is unaffected;
    a replay of a decision dated before about August 2026 would see it. Every
    dry-run line says so.

THE GUARDS (all required by the team lead's brief of 2026-10-28)
-----------------------------------------------------------------
1. DRY RUN BY DEFAULT. It reads the panel, asks Alpaca (GETs only), reads
   systemd and /proc, prints every planned cell (date, ticker, the close it
   would write, the print it comes from) and writes nothing: no lock file, no
   backup, no log. `--apply` writes, and only with `--plan <digest>`, the
   digest the dry run printed. A digest of the cells and values, so what is
   written is exactly what the team lead read (CLAUDE.md order-path rule 1's
   "show the list, get a go", applied to a panel).
2. NOTHING ELSE RUNNING. It takes the panel lock fetch_daily takes
   (`scripts/cef/fetch_daily.py` `panel_lock` on `LOCK_PATH`, the lock its
   test pins, scripts/cef/tests/test_fetch_daily_lock.py), so neither the
   collector's nor the session's refresh can interleave. The lock alone is not
   enough: the session's sleeve reads the panel AFTER its refresh, outside the
   lock. So it also refuses while any quantt job service is running or QUEUED
   (`install_vm.job_states`, which reads ActiveState AND Job because
   `is-active` misses a queued start [V, measured 2026-10-08]), and while any
   process runs quantt.session, quantt.collect, the installer or fetch_daily
   outside systemd (a hand run over ssh is invisible to systemd).
3. BACKUP FIRST. The panel's bytes are copied to
   `<panel>.pre-repair-<UTC stamp>.bak` beside it, created exclusively: a
   backup by that name already existing refuses. The copy is read back and its
   sha256 must equal the panel's; both are printed and logged.
4. ONLY EMPTY CELLS. A cell is planned only if its close is absent or not
   finite (`fetch_daily.has_close`, the one test for an empty row). Under the
   lock the panel is re-read, and any planned cell that is now filled, missing,
   duplicated or whose row differs from the planned one refuses the write.
   Cells are found by (date, ticker), never by row number: a collector run
   between the dry run and the apply inserts rows mid-panel.
5. ONE LOG LINE PER CELL in `<state>/logs/repair_empty_closes.log`: date,
   ticker, the old row, the new row, the source and the UTC time, as JSON. The
   file is opened before anything is written, so an unwritable log refuses.
6. ATOMIC WRITE through `ops.common.atomic_write`, what fetch_daily uses.
7. POST-CHECK. The written file is re-read and compared with the backup: the
   same columns in the same order, dtypes, Arrow types, row count and index,
   and every cell byte-identical except the planned closes, which must hold
   exactly the planned values. On any difference, or any exception after the
   write began, the backup's bytes are put back (temp file, fsync, rename) and
   the restored file's sha256 is checked against the original.
8. SAFE WINDOWS. Never on a weekday inside 15:30-16:00 or 12:30-13:00 ET
   (install_vm's PLAN_REFUSE_RANGES_ET, the send windows and the minutes before
   them). While the timers are running, also never when a quantt timer fires
   within the next 10 minutes or fired in the last 2: the firing times are
   read from prod's own job table (`install_prod.JOBS`, which the VM's timers
   reproduce), so the collector's :10/:40, the session's :00/:30, the send
   slots and verify's 17:30 are all covered and cannot drift. READ AS "the next
   firing is less than 10 minutes away", because slots 10 and 20 minutes apart
   leave no minute of the hour more than 10 minutes from one; the look-back is
   for a firing whose job is not yet visible. That leaves :12-:20 and :42-:50
   each half hour. With all three timers stopped this clause does not apply.
   Guards 2 and 8 are checked before the lock and again under it, at the
   moment of writing.

A plan already DECIDED is not changed by this: the late-market send reads the
saved plan.json and its closes (quantt/session/run.py `load_decided_plan`), not
the panel. The next decide reads the repaired panel.

EXIT CODES
----------
0  dry run printed, applied and verified, or nothing to do.
2  refused: nothing was written (argparse's usage errors are 2 as well).
3  the post-check failed and the backup was restored and confirmed.
4  the post-check failed and the restore could NOT be confirmed: the panel may
   be wrong. The message names the backup and both sha256 values.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import math
import os
import struct
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
LOG_NAME = "repair_empty_closes.log"
# The collector's condition for "the" official close (collect.py
# step_official_closes passes condition="M"; alpaca.py closing_auction_prints).
CONDITION = "M"
# Guard 8. Ten minutes ahead is the team lead's figure (brief, 2026-10-28); two
# minutes back covers a firing whose job systemd has not shown yet.
SLOT_LOOKAHEAD = dt.timedelta(minutes=10)
SLOT_LOOKBACK = dt.timedelta(minutes=2)
# Guard 2. A held panel lock means a refresh is running; job_states would
# normally have refused already. A short wait, then refuse: never queue
# behind a fetch.
LOCK_WAIT_S = 5.0
LOCK_POLL_S = 0.5
# Guard 2, processes outside systemd. Substrings of an argv token.
PROCESS_MARKERS = ("quantt.session", "quantt.collect", "quantt.deploy.install_vm",
                   "fetch_daily.py")
# Timer ActiveState values: a stopped timer reads inactive (or failed);
# anything but these and "active" cannot be confirmed either way and refuses.
TIMER_STOPPED = frozenset({"inactive", "failed"})
TIMER_RUNNING = frozenset({"active"})
DIGEST_LEN = 12

EXIT_OK, EXIT_REFUSED, EXIT_RESTORED, EXIT_RESTORE_FAILED = 0, 2, 3, 4


class Refused(RuntimeError):
    """A guard refused. Nothing was written."""


# ------------------------------------------------------------------ the run's world

@dataclass
class Ctx:
    """Everything the repair touches, injected so the tests need no VM, no
    network, no systemd and no real panel."""
    panel: Path                 # prod's cef_prices.parquet (fetch_daily.PX_PATH)
    lock: Path                  # fetch_daily.LOCK_PATH: the panel lock
    log: Path                   # <state>/logs/repair_empty_closes.log
    client: Any                 # the GET surface of quantt.broker.alpaca.AlpacaClient
    run_cmd: Callable           # argv -> CompletedProcess-like (systemctl show)
    now: Callable               # () -> aware datetime: the machine's clock, which the timers fire on
    procs: Callable             # () -> [(pid, [argv...])] of every other process
    write: Callable             # (frame, path): ops.common.atomic_write
    live: frozenset             # the frozen spec's universe, to mark live-book cells
    code: str                   # which code this is, for the record (git describe of the clone)
    lock_wait_s: float = LOCK_WAIT_S


@dataclass(frozen=True)
class Cell:
    date: pd.Timestamp
    ticker: str
    old: dict                   # the whole row as planned, column -> value


@dataclass(frozen=True)
class Fill:
    cell: Cell
    close: float
    source: str


@dataclass(frozen=True)
class Gap:
    cell: Cell
    kind: str                   # "NO PRINT" (a final answer) or "NOT MEASURED"
    reason: str


# ------------------------------------------------------------------ helpers

def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _utc(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def _read(raw: bytes) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(raw))


def _same_obj(x, y) -> bool:
    """Exact equality for one object cell: same type, same value, NaN equal to
    a NaN with the same bits. A pair that cannot be compared is NOT the same,
    so the post-check fails towards a restore, never towards a pass."""
    if x is y:
        return True
    if type(x) is not type(y):
        return False
    if isinstance(x, float):
        return struct.pack("<d", x) == struct.pack("<d", y)
    try:
        return bool(x == y)
    except (TypeError, ValueError):
        return False


def _same_cells(a: pd.Series, b: pd.Series) -> np.ndarray:
    """Per row: is the cell byte-identical? Fixed-width columns (floats, ints,
    datetimes) compare their raw bytes, so NaN equals the same NaN and 0.0 does
    not equal -0.0; object columns compare exactly (`_same_obj`)."""
    av, bv = a.to_numpy(), b.to_numpy()
    if len(av) != len(bv) or av.dtype != bv.dtype:
        return np.zeros(max(len(av), len(bv)), dtype=bool)
    if av.dtype.kind in "biufcmM":
        w = av.dtype.itemsize
        ab = np.ascontiguousarray(av).view(np.uint8).reshape(-1, w)
        bb = np.ascontiguousarray(bv).view(np.uint8).reshape(-1, w)
        return (ab == bb).all(axis=1)
    return np.fromiter((_same_obj(x, y) for x, y in zip(av, bv)), dtype=bool, count=len(av))


def _json_value(v):
    if isinstance(v, (pd.Timestamp, dt.datetime, dt.date)):
        t = pd.Timestamp(v)
        return t.date().isoformat() if t == t.normalize() else t.isoformat()
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return f if math.isfinite(f) else str(f)
    return v


def _row_json(row: dict) -> dict:
    return {k: _json_value(v) for k, v in row.items()}


def _row(P: pd.DataFrame, i: int) -> dict:
    """Row `i` as a dict, built the one way both the plan and the re-check
    build it (`to_dict("records")`), so a row read twice compares exactly."""
    return P.iloc[[i]].to_dict("records")[0]


def _same_row(a: dict, b: dict) -> list:
    """The columns on which two rows differ (exactly; `_same_obj`)."""
    return [k for k in a if k not in b or not _same_obj(a[k], b[k])] + \
           [k for k in b if k not in a]


# ------------------------------------------------------------------ plan

def empty_cells(P: pd.DataFrame) -> list:
    """Every row whose close is absent or not finite, by fetch_daily's own test
    (`has_close`: the one test for an empty row, shared with the merge and the
    as-of check). Sorted by date, then ticker."""
    from scripts.cef.fetch_daily import has_close
    cells = [Cell(pd.Timestamp(r["date"]), str(r["ticker"]), r)
             for r in P.loc[~has_close(P)].to_dict("records")]
    return sorted(cells, key=lambda c: (c.date, c.ticker))


def fetch_closes(client, cells: list) -> tuple:
    """(fills, gaps): the official close for each cell, from the collector's
    primary source, asked exactly as `step_official_closes` asks it.

    One query per (ticker, date), as the collector queries one symbol at a
    time, so one cell's error is that cell's gap. The primary exchange is read
    once per ticker, TODAY (`primary_sip_code`'s docstring: a listing move
    since the ex-date is not detected [U]; every universe name is NYSE-listed
    [V: probe 2026-09-28])."""
    from quantt.broker.alpaca import AlpacaError
    from quantt.collect.collect import FINAL_PRINT_GAPS
    exchanges = client.stock_exchanges()       # if this fails, nothing is measured: raise
    codes, no_code = {}, {}
    for t in sorted({c.ticker for c in cells}):
        try:
            codes[t] = client.primary_sip_code(t, exchanges)
        except FINAL_PRINT_GAPS as e:
            no_code[t] = ("NO PRINT", f"primary exchange: {type(e).__name__}: {e}")
        except AlpacaError as e:
            no_code[t] = ("NOT MEASURED", f"primary exchange: {type(e).__name__}: {e}")
    fills, gaps = [], []
    for c in cells:
        if c.ticker in no_code:
            gaps.append(Gap(c, *no_code[c.ticker]))
            continue
        code = codes[c.ticker]
        try:
            got = client.closing_auction_prints([c.ticker], c.date.date(),
                                                exchange_codes={c.ticker: code},
                                                condition=CONDITION)
        except FINAL_PRINT_GAPS as e:
            gaps.append(Gap(c, "NO PRINT", f"{type(e).__name__}: {e}"))
            continue
        except AlpacaError as e:
            gaps.append(Gap(c, "NOT MEASURED", f"{type(e).__name__}: {e}"))
            continue
        if c.ticker not in got:      # collect.py raises on the same impossibility
            raise ValueError(f"closing_auction_prints returned no row and no error for {c.ticker}")
        p = got[c.ticker]
        price = float(p["price"])
        if not (math.isfinite(price) and price > 0):
            gaps.append(Gap(c, "NOT MEASURED", f"the print's price {price!r} is not a finite "
                                               f"positive number"))
            continue
        fills.append(Fill(c, price,
                          f"alpaca official close: GET /v2/stocks/auctions feed=sip, primary "
                          f"exchange {p['exchange']}, condition {p['condition']}, t={p['t']}"))
    return fills, gaps


def plan_digest(fills: list) -> str:
    """A digest of exactly what would be written: date, ticker, the close's
    exact bits and its source. `--apply` refuses unless its own fresh plan
    hashes to the digest the dry run showed. Not the panel's hash: the
    collector appends a day every evening, which must not void a reviewed
    plan; guard 4 re-checks every cell under the lock instead."""
    rows = [[f.cell.date.date().isoformat(), f.cell.ticker, float(f.close).hex(), f.source]
            for f in sorted(fills, key=lambda f: (f.cell.date, f.cell.ticker))]
    return _sha(json.dumps(rows, separators=(",", ":")).encode())[:DIGEST_LEN]


# ------------------------------------------------------------------ guards 2 and 8

def _fires(sched: dict, t: dt.datetime) -> bool:
    """Does one launchd StartCalendarInterval dict (install_prod.JOBS, which the
    VM's timers reproduce) fire at ET wall-clock minute `t`? Omitted keys are
    wildcards (`man launchd.plist`); Weekday 0 and 7 are Sunday."""
    unknown = set(sched) - {"Minute", "Hour", "Weekday"}
    if unknown:
        raise Refused(f"job schedule {sched} has key(s) {sorted(unknown)} this guard cannot read")
    return (sched["Minute"] == t.minute
            and ("Hour" not in sched or sched["Hour"] == t.hour)
            and ("Weekday" not in sched or sched["Weekday"] % 7 == t.isoweekday() % 7))


def firings_near(now: dt.datetime) -> list:
    """Every quantt timer firing in [now - SLOT_LOOKBACK, now + SLOT_LOOKAHEAD],
    as "<job> HH:MM ET". Times are stepped in UTC and read in ET, as systemd
    reads the VM's America/New_York OnCalendar lines."""
    from quantt.deploy.install_prod import JOBS
    base = now.astimezone(dt.timezone.utc).replace(second=0, microsecond=0)
    out = []
    back = int(SLOT_LOOKBACK.total_seconds() // 60) + 1
    ahead = int(SLOT_LOOKAHEAD.total_seconds() // 60) + 1
    for k in range(-back, ahead + 1):
        f = base + dt.timedelta(minutes=k)
        if not (now - SLOT_LOOKBACK <= f <= now + SLOT_LOOKAHEAD):
            continue
        et = f.astimezone(ET)
        for job in JOBS:
            if any(_fires(s, et) for s in job.schedule):
                out.append(f"{job.log_stem} {et:%H:%M} ET")
    return out


def _late(now: dt.datetime):
    from quantt.deploy.install_vm import PLAN_REFUSE_RANGES_ET, late_window_at
    return late_window_at(now.astimezone(dt.timezone.utc), PLAN_REFUSE_RANGES_ET)


def window_refusals(now: dt.datetime, timers_stopped: bool) -> list:
    """Guard 8 at `now` (module docstring)."""
    out = []
    hit = _late(now)
    if hit:
        a, b, t = hit
        out.append(f"it is {t:%H:%M} ET on a weekday, inside {a:%H:%M}-{b:%H:%M} ET (the send "
                   f"window and the minutes before it): never touch the panel there")
    if not timers_stopped:
        near = firings_near(now)
        if near:
            out.append(f"the quantt timers are running and {', '.join(near)} is within "
                       f"{int(SLOT_LOOKAHEAD.total_seconds() // 60)} minutes ahead or "
                       f"{int(SLOT_LOOKBACK.total_seconds() // 60)} behind")
    return out


def next_safe(now: dt.datetime, timers_stopped: bool):
    """The first whole minute from `now` at which guard 8 passes, or None within a day."""
    t = now.astimezone(dt.timezone.utc).replace(second=0, microsecond=0)
    for _ in range(24 * 60):
        t += dt.timedelta(minutes=1)
        if not window_refusals(t, timers_stopped):
            return t
    return None


def systemd_state(run_cmd) -> tuple:
    """(busy job rows, {timer: ActiveState}) from systemd, through prod's
    installer: `job_states` (running OR queued, the measured trap) and
    `systemd_show` for the three timers. A format or state these cannot read
    raises InstallRefused, which the caller turns into a refusal."""
    from quantt.deploy.install_vm import VM_JOBS, _one, job_states, systemd_show
    busy = job_states(run_cmd)
    timers = {}
    for vj in VM_JOBS:
        props = systemd_show(run_cmd, vj.timer, ["ActiveState"])
        timers[vj.timer] = _one(props, "ActiveState", vj.timer).strip()
    return busy, timers


def quantt_processes(procs) -> list:
    """Every other process whose argv names a quantt job, as "pid argv"."""
    out = []
    for pid, argv in procs:
        if any(m in tok for tok in argv for m in PROCESS_MARKERS):
            out.append(f"pid {pid}: {' '.join(argv)[:160]}")
    return out


def guard_refusals(ctx: Ctx) -> tuple:
    """(refusals, facts) for guards 2 and 8, read now. Empty refusals = pass."""
    from quantt.deploy.install_prod import InstallRefused
    refusals, facts = [], {}
    now = ctx.now()
    facts["now"] = f"{now.astimezone(ET):%Y-%m-%d %H:%M:%S} ET"
    timers_stopped = False
    try:
        busy, timers = systemd_state(ctx.run_cmd)
    except (InstallRefused, OSError) as e:
        refusals.append(f"systemd could not be read, so no job can be ruled out "
                        f"({type(e).__name__}: {e})")
    else:
        facts["timers"] = timers
        if busy:
            refusals.append("a quantt job is running or queued: " + "; ".join(
                f"{r['unit']} {r['state']}" + (f" (queued job {r['job']})" if r["job"] else "")
                for r in busy))
        odd = {t: s for t, s in timers.items() if s not in TIMER_STOPPED | TIMER_RUNNING}
        if odd:
            refusals.append(f"timer state(s) {odd} are neither running nor stopped")
        timers_stopped = all(s in TIMER_STOPPED for s in timers.values())
    facts["timers_stopped"] = timers_stopped
    try:
        found = quantt_processes(ctx.procs())
    except OSError as e:
        refusals.append(f"the process table could not be read ({type(e).__name__}: {e}), so a "
                        f"quantt job run by hand cannot be ruled out")
    else:
        if found:
            refusals.append("a quantt process is running outside systemd: " + "; ".join(found))
    refusals += window_refusals(now, timers_stopped)
    return refusals, facts


# ------------------------------------------------------------------ guards 3, 4, 6, 7

def locate(P: pd.DataFrame, fills: list) -> np.ndarray:
    """Row positions of the planned cells in `P` (re-read under the lock), or
    Refused naming every cell that is missing, duplicated, already filled, or
    whose row is no longer the row that was planned (guard 4)."""
    from scripts.cef.fetch_daily import has_close
    dates, tickers = P["date"].to_numpy(), P["ticker"].to_numpy()
    empty = ~has_close(P).to_numpy()             # True where the close is still empty
    pos, bad = [], []
    for f in fills:
        c = f.cell
        m = np.flatnonzero((dates == c.date.to_datetime64()) & (tickers == c.ticker))
        if len(m) != 1:
            bad.append(f"{c.date.date()} {c.ticker}: {len(m)} rows in the panel now, expected 1")
            continue
        i = int(m[0])
        if not empty[i]:
            bad.append(f"{c.date.date()} {c.ticker}: ALREADY FILLED at write time "
                       f"(close {P['close'].iloc[i]!r}); this tool never overwrites a close")
            continue
        changed = _same_row(_row(P, i), c.old)
        if changed:
            bad.append(f"{c.date.date()} {c.ticker}: the row changed since it was planned "
                       f"({', '.join(changed)})")
            continue
        pos.append(i)
    if bad:
        raise Refused("planned cell(s) are not as planned at write time: " + "; ".join(bad))
    return np.asarray(pos, dtype=np.int64)


def backup_path(panel: Path, now: dt.datetime) -> Path:
    stamp = now.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return panel.with_name(f"{panel.name}.pre-repair-{stamp}.bak")


def write_backup(path: Path, raw: bytes, sha_panel: str) -> str:
    """Guard 3: the panel's bytes into a NEW file (O_EXCL: an existing backup by
    this name refuses, never overwritten), fsynced, read back, sha256 checked."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        raise Refused(f"a backup named {path} already exists; not overwriting it, not "
                      f"writing the panel") from None
    try:
        view = memoryview(raw)
        while view:
            n = os.write(fd, view)
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    sha_backup = _sha(path.read_bytes())
    if sha_backup != sha_panel:
        raise Refused(f"backup {path} reads back as sha256 {sha_backup}, the panel is "
                      f"{sha_panel}; not writing the panel")
    return sha_backup


def post_check(panel: Path, backup: Path, pos: np.ndarray, closes: np.ndarray) -> list:
    """Guard 7: the problems found re-reading the written panel against the
    backup (empty = only the planned cells changed, to the planned values)."""
    import pyarrow.parquet as pq
    B = pd.read_parquet(backup)
    Q = pd.read_parquet(panel)
    problems = []
    if list(Q.columns) != list(B.columns):
        return [f"columns are {list(Q.columns)}, were {list(B.columns)}"]
    if len(Q) != len(B):
        return [f"{len(Q)} rows, were {len(B)}"]
    if not Q.index.equals(B.index):
        problems.append("the index changed")
    for c in B.columns:
        if Q[c].dtype != B[c].dtype:
            problems.append(f"column {c} is {Q[c].dtype}, was {B[c].dtype}")
    if problems:
        return problems
    if not pq.read_schema(panel).remove_metadata().equals(pq.read_schema(backup).remove_metadata()):
        problems.append(f"the Arrow schema changed: {pq.read_schema(panel).remove_metadata()} "
                        f"vs {pq.read_schema(backup).remove_metadata()}")
    expected = B.copy()
    col = expected["close"].to_numpy(copy=True)
    col[pos] = closes
    expected["close"] = col
    for c in B.columns:
        same = _same_cells(expected[c], Q[c])
        if not same.all():
            rows = np.flatnonzero(~same)
            shown = "; ".join(f"{B['date'].iloc[i].date()} {B['ticker'].iloc[i]} {c}: expected "
                              f"{expected[c].iloc[i]!r}, found {Q[c].iloc[i]!r}"
                              for i in rows[:5])
            problems.append(f"{len(rows)} cell(s) of {c} are not as planned: {shown}")
    return problems


def restore(backup: Path, panel: Path, sha_original: str) -> tuple:
    """Put the backup's exact bytes back (temp file, fsync, rename). Not
    atomic_write: that serialises a frame, and the restored file must be the
    original BYTES. Returns (confirmed, sha256 of the panel now)."""
    tmp = panel.with_name(panel.name + ".restore.tmp")
    tmp.write_bytes(backup.read_bytes())
    with open(tmp, "rb") as fh:
        os.fsync(fh.fileno())
    os.replace(tmp, panel)
    now = _sha(panel.read_bytes())
    return now == sha_original, now


# ------------------------------------------------------------------ the run

def _print_plan(fills, gaps, live, out) -> None:
    rows = [(f.cell, "PLAN", f"close {_json_value(f.cell.old['close'])} -> {f.close!r}  "
                             f"[{f.source}]") for f in fills]
    rows += [(g.cell, g.kind, f"left empty: {g.reason}") for g in gaps]
    for c, what, text in sorted(rows, key=lambda r: (r[0].date, r[0].ticker)):
        mark = "*" if c.ticker in live else " "
        out(f"  {what:<12} {c.date.date()} {c.ticker + mark:<5} {text}")


def run(ctx: Ctx, *, apply: bool, plan: str | None, out=print) -> int:
    out(f"repair_empty_closes {'APPLY' if apply else 'DRY RUN (writes nothing)'}: {ctx.panel}")
    out(f"  code: {ctx.code}; machine clock {ctx.now().astimezone(ET):%Y-%m-%d %H:%M:%S} ET")
    raw = ctx.panel.read_bytes()
    P = _read(raw)
    if P.duplicated(subset=["date", "ticker"]).any():
        raise Refused(f"{ctx.panel} holds duplicate (date, ticker) rows; a cell is not one row")
    cells = empty_cells(P)
    out(f"  panel: {len(P):,} rows to {P['date'].max().date()}, sha256 {_sha(raw)}; "
        f"{len(cells)} row(s) with no finite close")
    if not cells:
        out("  nothing to repair")
        return EXIT_OK
    fills, gaps = fetch_closes(ctx.client, cells)
    _print_plan(fills, gaps, ctx.live, out)
    digest = plan_digest(fills)
    n_live = sum(f.cell.ticker in ctx.live for f in fills)
    out(f"  {len(cells)} empty: {len(fills)} would be filled ({n_live} on the live book, marked *), "
        f"{sum(g.kind == 'NO PRINT' for g in gaps)} NO PRINT and "
        f"{sum(g.kind == 'NOT MEASURED' for g in gaps)} NOT MEASURED, left empty")
    out("  written: close only. volume stays 0 (yfinance's fill, not a measurement: the print "
        "carries no day volume) and open/high/low stay NaN (the print has none)")
    refusals, facts = guard_refusals(ctx)
    out(f"  guards now: timers {facts.get('timers', 'UNREAD')}; "
        + ("pass" if not refusals else "an apply would REFUSE: " + " | ".join(refusals)))
    if refusals:
        nxt = next_safe(ctx.now(), facts.get("timers_stopped", False))
        if nxt is not None:
            out(f"  next minute guard 8 allows: {nxt.astimezone(ET):%H:%M} ET (guard 2 is "
                f"re-read then)")
    out(f"  plan digest {digest}")
    if not apply:
        out(f"  to write exactly these {len(fills)} close(s): --apply --plan {digest}")
        return EXIT_OK
    if plan != digest:
        raise Refused(f"--plan {plan} is not this run's plan {digest}: what Alpaca or the panel "
                      f"gave has changed since the dry run. Read a new dry run first")
    if not fills:
        out("  nothing to write: no empty cell has a print")
        return EXIT_OK
    if refusals:
        raise Refused(" | ".join(refusals))
    return _apply(ctx, fills, gaps, digest, out)


def _apply(ctx: Ctx, fills, gaps, digest, out) -> int:
    from scripts.cef.fetch_daily import PanelLockTimeout, panel_lock
    try:
        ctx.log.parent.mkdir(exist_ok=True)
        log = open(ctx.log, "a", encoding="utf-8")     # guard 5: refuse before writing anything
    except OSError as e:
        raise Refused(f"cannot open the log {ctx.log} ({type(e).__name__}: {e})") from None
    try:
        try:
            with panel_lock(ctx.lock, ctx.lock_wait_s, LOCK_POLL_S):
                return _apply_locked(ctx, fills, gaps, digest, log, out)
        except PanelLockTimeout as e:
            raise Refused(f"the panel lock is held, so a refresh is running: {e}") from None
    finally:
        log.close()


def _apply_locked(ctx: Ctx, fills, gaps, digest, log, out) -> int:
    # Guards 2 and 8 again, now, at the moment of writing.
    refusals, _ = guard_refusals(ctx)
    if refusals:
        raise Refused("under the lock: " + " | ".join(refusals))
    raw = ctx.panel.read_bytes()                       # guard 4: re-read under the lock
    sha_before = _sha(raw)
    P = _read(raw)
    pos = locate(P, fills)
    closes = np.asarray([f.close for f in fills], dtype=P["close"].dtype)
    backup = backup_path(ctx.panel, ctx.now())
    sha_backup = write_backup(backup, raw, sha_before)  # guard 3
    out(f"  backup {backup}: sha256 {sha_backup} (the panel's: {sha_before})")
    new = P.copy()
    col = new["close"].to_numpy(copy=True)
    col[pos] = closes
    new["close"] = col
    try:
        ctx.write(new, ctx.panel)                       # guard 6
        problems = post_check(ctx.panel, backup, pos, closes)  # guard 7
    except BaseException as e:
        problems = [f"{type(e).__name__} during the write or the post-check: {e}"]
        traceback.print_exc()
    if problems:
        ok, sha_now = restore(backup, ctx.panel, sha_before)
        rec = {"utc": _utc(ctx.now()), "event": "POSTCHECK FAILED", "panel": str(ctx.panel),
               "backup": str(backup), "problems": problems, "restored": ok,
               "sha256_original": sha_before, "sha256_now": sha_now, "plan": digest,
               "code": ctx.code}
        log.write(json.dumps(rec) + "\n")
        log.flush()
        os.fsync(log.fileno())
        for p in problems:
            out(f"  POST-CHECK FAILED: {p}")
        if ok:
            out(f"  RESTORED the backup; the panel is the original again (sha256 {sha_now})")
            return EXIT_RESTORED
        out(f"  RESTORE NOT CONFIRMED: the panel reads sha256 {sha_now}, the original was "
            f"{sha_before}. The original bytes are in {backup}. Do not let a session decide on "
            f"this panel until it is put right")
        return EXIT_RESTORE_FAILED
    sha_after = _sha(ctx.panel.read_bytes())
    when = _utc(ctx.now())
    for i, f in zip(pos, fills):
        new_row = dict(f.cell.old, close=f.close)
        rec = {"utc": when, "event": "REPAIRED", "date": f.cell.date.date().isoformat(),
               "ticker": f.cell.ticker, "old": _row_json(f.cell.old), "new": _row_json(new_row),
               "source": f.source, "plan": digest}
        log.write(json.dumps(rec) + "\n")
        out(f"  REPAIRED     {f.cell.date.date()} {f.cell.ticker:<5} close -> {f.close!r}")
    rec = {"utc": when, "event": "RUN", "panel": str(ctx.panel), "backup": str(backup),
           "sha256_panel_before": sha_before, "sha256_backup": sha_backup,
           "sha256_panel_after": sha_after, "written": len(fills),
           "left_empty": [{"date": g.cell.date.date().isoformat(), "ticker": g.cell.ticker,
                           "kind": g.kind, "reason": g.reason} for g in gaps],
           "plan": digest, "code": ctx.code}
    log.write(json.dumps(rec) + "\n")
    log.flush()
    os.fsync(log.fileno())
    out(f"  wrote {len(fills)} close(s); post-check passed; panel sha256 {sha_before} -> {sha_after}; "
        f"{len(gaps)} left empty; log {ctx.log}")
    return EXIT_OK


# ------------------------------------------------------------------ the real world

def _run_cmd(args):
    return subprocess.run(args, capture_output=True, text=True)


def _proc_table() -> list:
    """[(pid, argv)] of every other process, from /proc (Linux). A process that
    exits mid-scan is skipped; /proc missing raises (the caller refuses)."""
    root = Path("/proc")
    if not root.is_dir():
        raise FileNotFoundError("/proc is not mounted here")
    me, rows = os.getpid(), []
    for d in root.iterdir():
        if not d.name.isdigit() or int(d.name) == me:
            continue
        try:
            raw = (d / "cmdline").read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            continue
        rows.append((int(d.name), [a.decode("utf-8", "replace") for a in raw.split(b"\0") if a]))
    return rows


def build_ctx(env) -> Ctx:
    """Prod's own paths and code: the panel and lock as fetch_daily names them
    (so as the collector and the session reach them), the keys as the collector
    loads them (`AlpacaClient.from_environment`, QUANTT_ENV_FILE, never
    printed), the state dir as the runner requires it (set and existing)."""
    import ops.common as common
    import scripts.cef.fetch_daily as fd
    from quantt.broker.alpaca import AlpacaClient
    from quantt.deploy.install_prod import BOOK
    from quantt.session.records import StateDirError, state_dir_from_env
    from scripts.cef.spec import frozen
    try:
        state = state_dir_from_env(env)
    except StateDirError as e:
        raise Refused(str(e)) from None
    if not env.get("QUANTT_ENV_FILE"):
        raise Refused("QUANTT_ENV_FILE is not set: it must name the book's Alpaca key file "
                      "(/run/quantt/alpaca.env on the VM)")
    r = _run_cmd(["git", "-C", str(fd.REPO), "describe", "--tags", "--always", "--dirty"])
    code = f"{fd.REPO} at " + (r.stdout.strip() if r.returncode == 0
                               else f"UNKNOWN (git describe: {r.stderr.strip()})")
    return Ctx(panel=fd.PX_PATH, lock=fd.LOCK_PATH, log=state / "logs" / LOG_NAME,
               client=AlpacaClient.from_environment(BOOK), run_cmd=_run_cmd,
               now=lambda: dt.datetime.now(dt.timezone.utc), procs=_proc_table,
               write=lambda frame, path: common.atomic_write(frame, path),
               live=frozenset(frozen("universe")), code=code)


def main(argv=None, *, make_ctx=build_ctx, env=None, out=print) -> int:
    ap = argparse.ArgumentParser(prog="repair_empty_closes",
                                 description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="the default: print the plan, write nothing")
    g.add_argument("--apply", action="store_true", help="write the planned closes (needs --plan)")
    ap.add_argument("--plan", help="the digest a dry run printed; --apply writes only that plan")
    a = ap.parse_args(argv)
    if a.apply and not a.plan:
        ap.error("--apply needs --plan <digest>, from a dry run read first")
    if a.plan and not a.apply:
        ap.error("--plan is for --apply")
    env = os.environ if env is None else env
    try:
        ctx = make_ctx(env)
        return run(ctx, apply=a.apply, plan=a.plan, out=out)
    except Refused as e:
        out(f"REFUSED: {e}. Nothing was written.")
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
