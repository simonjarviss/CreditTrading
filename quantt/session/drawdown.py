"""The book's drawdown from its high-water mark, against the frozen spec's HALVE and KILL lines. Report mode only.

THE DEFECT (results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md §1 item 4 and §3.4)
----------------------------------------------------------------------------
The frozen spec has carried `risk.halve_drawdown` and `risk.kill_drawdown` since
v5, and the standing decision is to arm HALVE/KILL on broker-confirmed NAV (team
lead, 2026-09-08; docs/SYSTEM.md §5). On the Alpaca path nothing read either key,
and the runner never called any sleeve's `risk_check`. That sleeve method writes
0.18 and 0.12 as literals, and on an exception returns OK, a silent fallback.
Re-verified on 2026-10-19 at main 832aeaa: no `.py` under `quantt/`, `src/` or
`ops/` named either key, and nothing in the repository called `risk_check(`.
A survival line wired to nothing looks armed and is not. The deployed book's own
fit-window drawdown, 12.78% (2017-06 -> 2018-06; that note §1), would have
crossed the 12% HALVE line.

WHAT THIS IS (team lead, 2026-10-19: report mode first)
------------------------------------------------------
At every DECIDE the runner (quantt/session/run.py, step 2b) asks `check` for the
book's drawdown from its high-water mark on the official daily equity series,
compares it with the two lines, and records the result, together with what an
`on` mode WOULD do, in plan.json and the run record (`drawdown`). It also prints
it to the session log (`lines`). Report mode acts on nothing. ONE READER OF THE
STATUS RESTRICTS ON IT, and only while the core spec sets `below_min_names =
"trade_eligible"` (CEF trial 55, paper only; added 2026-11-03): run.py's K0
(`_thin_k0_stop`) lets the sleeve build a reduced 4-5 name book only when the
status is exactly OK, and on HALVE, KILL, UNMEASURED or anything else passes the
stop that takes today's flatten instead. K0 reads its OWN record of this check,
through the previous session's row (READ THROUGH, below; team lead's ruling
2026-11-03), not the `drawdown` record above, which is unchanged. Its one action
is today's rule: it never sizes up and never unlocks a send (the owner's term,
pinned by
quantt/session/tests/test_trade_eligible_runner.py, "no drawdown status can
increase gross"). With that key absent nothing reads the status, and the
orders, the plan_sha and plan.json are a check-off session's, byte for byte,
apart from the added `drawdown` record. The K0-K3 REPORT lines for that trial
are at the end of this module (`thin_stop_record`); they report and act on
nothing. quantt/session/tests/test_drawdown.py
proves it on the live spec, the real sleeve and the real panel. This is the
stale-NAV gate's report-mode design (quantt/session/nav_gate.py, 2026-10-13),
reused.

THE SERIES: `<state>/eod_equity.csv`, never `equity.csv`
-------------------------------------------------------
Team lead, 2026-10-19: Alpaca's end-of-day portfolio history
(`GET /v2/account/portfolio/history`, timeframe 1D) is the OFFICIAL daily P&L.
The collector writes it to `<state>/eod_equity.csv` and backfills it from
2026-09-28. Its header has `date`, `equity` and `change_usd`, possibly with
extra columns after them, and `change_usd` is empty on the first funded row.
This module reads two columns BY HEADER NAME, `date` (YYYY-MM-DD) and `equity`
(USD). `change_usd` and every other column are never read, so an empty cell or an
added column cannot break the check.
  * Why not `equity.csv`. Its rows are account SNAPSHOTS, taken by the collector
    after the close on after-hours marks. A snapshot can set a high-water mark
    the book never closed at, and every later drawdown would then be measured
    from a number that never existed at a close. The day-on-day changes differ
    materially: 2026-10-05 snapshot +$1,068.53 against Alpaca's EOD +$126.05,
    2026-10-16 +$242.56 against +$160.58 (figures as relayed from the session
    that built eod_equity.csv, 2026-10-19 [S]).
  * eod_equity.csv absent or unreadable -> UNMEASURED, naming the file. There is
    NEVER a fallback to equity.csv (CLAUDE.md: no silent fallbacks).
  * The snapshot is still SHOWN, as a second line explicitly labelled as
    snapshots and not the check's input (`snapshot` in the record). It never
    changes the status. It is there because, until eod_equity.csv ships (a
    hotfix release, week of 2026-10-19), it is the only equity history on the
    VM, and a reader should see both.

THE MEASURE
-----------
  HWM       the largest `equity` over every row dated on or before the as-of
            date (its first date is reported);
  drawdown  1 - (equity of the newest such row) / HWM, a fraction >= 0;
  STATUS    KILL if drawdown >= kill_drawdown, else HALVE if >= halve_drawdown,
            else OK. UNMEASURED when it cannot be measured (below).
NO LOOKAHEAD: the decide on as-of date D (evening of D, or the morning backstop
on D+1) may use the EOD equity of D and earlier, never later. Rows dated after D
are dropped before anything is computed, and that is asserted. The newest row
must BE D. A series that ends before D is UNMEASURED and says so; the stale
figures are still recorded, labelled with their own date. Whether the EOD row
for D exists by the 22:00 ET evening decide was open when this was built; report
mode measured it, and it does not: prod's 4 of 4 decides that carry the field
(as-of 10-28, 10-29, 10-30, 11-02) read UNMEASURED because eod_equity.csv's
newest row was D-1 (E-2026-11-03-41, the owner's finding, from prod's plan.json
records [S: not in this repository]). This default reading is unchanged by that
finding: what HALVE/KILL and any `on` mode read is the owning session's to rule.

READ THROUGH AN EARLIER SESSION (`check(..., read_through=d)`; CEF trial 55's K0
only, team lead's ruling 2026-11-03, E-2026-11-03-42). At 22:00 the EOD row for
the as-of D never exists yet (above), so a stop that needs an exact OK at the
evening decide would never pass: te4's K0 would flatten every reduced session and
the trial would never trade. The ruling: K0 reads the previous session's row,
labelled one session stale. With `read_through` set, the check is the same check
on the rows dated on or before `read_through`: the high-water mark over them, the
drawdown of the newest of them, the same status. The newest such row must BE
`read_through`; an older one, a missing or bad file, is UNMEASURED, exactly as an
as-of reading that ends early is. The reading carries `stale` = {row_date,
sessions}, its staleness in NYSE sessions after its row up to the as-of
(ops/schedule/nyse_calendar.py, the runner's own calendar; 1 when `read_through`
is the session before the as-of), and the record names `read_through`. No
lookahead: `read_through` after the as-of raises. Its cost, accepted by the
ruling: a loss on D is seen only at the next evening's decide. `read_through`
None (the default) is the reading above, byte for byte; only run.py's K0
(`_thin_k0_drawdown`) passes it, and HALVE/KILL's own record is unchanged.
The record also gives the worst drawdown in the series and the first date each
line was crossed. A STICKY `on` (below) would still be holding a line crossed
earlier, even after the book recovered above it.

THE LEVELS: the frozen spec, through the live path's own read
------------------------------------------------------------
`levels(spec)` reads `risk.halve_drawdown` and `risk.kill_drawdown` from the spec
dict that run.py's `load_spec` loaded (the live path reads the spec directly,
never through `scripts/`), never a literal. UNITS: a drawdown line is a FRACTION
of the high-water mark, in (0, 1), and halve < kill. A value >= 1 is a percent
written where a fraction belongs. That is the units trap that once made
`book_drawdown_suspend_pct` = 0.99 the tightest live limit in the book
(.claude/skills/spec-change). It is refused, never rescaled.

MODES (`MODES`; the book json's `risk.drawdown`; absent = off, run.drawdown_for)
------------------------------------------------------------------------------
  report   measure, record and print. It never blocks, never changes an order.
           An unexpected error is recorded as UNMEASURED with its type, and the
           session goes on (run.py `_drawdown`), as the stale-NAV gate's report
           mode does.
  on       NOT BUILT. Setting it raises; it needs the team lead's ruling.
What an `on` mode would do is recorded each session (`would_on`, `WOULD_ON`):
  HALVE       size every sleeve on half its budget, which halves the vol target,
              and keep that until the team lead records a review (STICKY: never
              restored automatically on recovery, framework §3.4, because
              re-levering on recovery whipsaws exactly when risk pays least);
  KILL        flatten every sleeve through the normal order path (every gate
              still applies), then write ops/HALT_cef.md; the team lead restarts.
              The halt must follow the flatten's send, or the halt gate would
              refuse the flatten;
  UNMEASURED  REFUSE THE DECIDE (a named `risk` refusal: nothing is sent, and
              verify reads the day as a MISSED FAIL).
WHY UNMEASURED SHOULD BLOCK UNDER `on` (the decision this docstring was asked to
make). A survival stop that fails open is the defect this module replaces: lines
that looked armed for months while nothing read them, and a `risk_check` that
returned OK on an exception. Failing closed costs one missed day. The desk
already shows a missed day loudly (MISSED FAIL in verify, orient and the status
line), and the cure is in our own hands (the collector backfills the file).
Failing open costs an unbounded drawdown, unseen. The trade-off accepted: a
refused day cannot reduce risk either. The alternative for the ruling is a
close-only day, which sends reductions only. That needs new order-path code, so
it was not chosen as the default.
In report mode UNMEASURED never blocks: that is the definition of report mode.

NOT HANDLED, AND WHY IT MATTERS BEFORE `on` ON REAL MONEY
---------------------------------------------------------
Deposits and withdrawals move equity without P&L. Alpaca paper has none, so the
HWM here is not flow-adjusted. A real-money `on` mode must adjust for flows, for
example from the account's CSD/CSW activities, before it can act.

H14: no number from a document is keyed on. The levels come from the frozen
spec, the equity from the broker's own series, both read at run time and
recorded with their source.

Standard library only at module level (pytest.ini; the send path never imports
`scripts/`).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
from pathlib import Path

REPORT = "report"
MODES = (REPORT,)                   # `on` is deliberately absent: not built (docstring)

OFFICIAL_FILE = "eod_equity.csv"    # Alpaca EOD portfolio history, 1D: the official series
SNAPSHOT_FILE = "equity.csv"        # the collector's after-hours account snapshots: shown, never used
READ_COLUMNS = ("date", "equity")   # the ONLY columns read, by header name, from either file

OFFICIAL_LABEL = ("eod_equity.csv: Alpaca end-of-day portfolio history (1D), the official "
                  "daily P&L (team lead 2026-10-19)")
SNAPSHOT_LABEL = ("equity.csv: the collector's after-hours account snapshots; shown for "
                  "comparison, NOT the check's input")

OK, HALVE, KILL, UNMEASURED = "OK", "HALVE", "KILL", "UNMEASURED"
LEVEL_KEYS = (("halve", "halve_drawdown"), ("kill", "kill_drawdown"))

WOULD_ON = {
    OK: "nothing",
    HALVE: ("halve: size every sleeve on half its budget (vol target halved), held until "
            "the team lead records a review (sticky)"),
    KILL: ("kill: flatten every sleeve through the normal order path, then write "
           "ops/HALT_cef.md; the team lead restarts"),
    UNMEASURED: "refuse the decide: a named `risk` refusal, nothing sent (verify: MISSED)",
}


class Unmeasured(Exception):
    """The drawdown cannot be measured. The message names the file, line or spec key."""


def levels(spec: dict) -> dict:
    """{"halve": f, "kill": f, "source": ...} from the frozen spec's `risk` block.

    Units-checked (module docstring, THE LEVELS): each must be a finite number in
    (0, 1), a fraction of the high-water mark, and halve < kill. Anything else
    raises `Unmeasured` naming the key. It is never rescaled and never defaulted."""
    risk = spec.get("risk")
    if not isinstance(risk, dict):
        raise Unmeasured("frozen spec has no `risk` block")
    out = {}
    for name, key in LEVEL_KEYS:
        if key not in risk:
            raise Unmeasured(f"frozen spec has no risk.{key}")
        v = risk[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise Unmeasured(f"frozen spec risk.{key} is {v!r}, not a finite number")
        if not 0 < v < 1:
            raise Unmeasured(
                f"frozen spec risk.{key} is {v!r}: a drawdown line is a FRACTION of the "
                f"high-water mark, in (0, 1); {v!r} reads as a percent (the units trap, "
                f".claude/skills/spec-change). Refused, not rescaled")
        out[name] = float(v)
    if not out["halve"] < out["kill"]:
        raise Unmeasured(f"frozen spec risk.halve_drawdown {out['halve']} is not below "
                         f"risk.kill_drawdown {out['kill']}")
    out["source"] = f"{spec.get('spec_id')} risk.halve_drawdown / risk.kill_drawdown"
    return out


def read_series(path: Path, asof: dt.date) -> list:
    """[(date, equity)] from `path`, rows dated on or before `asof`, oldest first.

    Reads `date` and `equity` by header name and nothing else (READ_COLUMNS), so
    an empty `change_usd` or an added column changes nothing. Raises
    `Unmeasured`, naming the file and line, on: no file, a file that cannot be
    read (a directory, no permission, not text), no header, a header
    without either column or with a repeated name, a row with the wrong number of
    fields, a date that is not YYYY-MM-DD, an equity that is not a finite
    positive number, a repeated date, or no row on or before `asof`. NO
    LOOKAHEAD: later rows are dropped, and that is asserted."""
    path = Path(path)
    if not path.exists():
        raise Unmeasured(f"no {path.name} at {path}")
    try:
        with open(path, newline="") as fh:
            rows = list(csv.reader(fh))
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise Unmeasured(f"{path} could not be read: {type(e).__name__}: {e}") from None
    if not rows:
        raise Unmeasured(f"{path} is empty: no header row")
    header = rows[0]
    missing = [c for c in READ_COLUMNS if c not in header]
    if missing:
        raise Unmeasured(f"{path} header is {header}: no {missing} column")
    if len(set(header)) != len(header):
        raise Unmeasured(f"{path} header {header} repeats a column name")
    di, ei = header.index("date"), header.index("equity")
    seen, out = set(), []
    for n, row in enumerate(rows[1:], start=2):
        if len(row) != len(header):
            raise Unmeasured(f"{path} line {n} has {len(row)} fields for {len(header)} columns")
        try:
            d = dt.date.fromisoformat(row[di])
        except ValueError:
            raise Unmeasured(f"{path} line {n}: date {row[di]!r} is not YYYY-MM-DD") from None
        try:
            e = float(row[ei])
        except ValueError:
            raise Unmeasured(f"{path} line {n}: equity {row[ei]!r} is not a number") from None
        if not (math.isfinite(e) and e > 0):
            raise Unmeasured(f"{path} line {n}: equity {row[ei]!r} is not a finite positive "
                             f"number")
        if d in seen:
            raise Unmeasured(f"{path} has two rows dated {d}")
        seen.add(d)
        if d <= asof:                    # NO LOOKAHEAD: nothing after the as-of date
            out.append((d, e))
    if not out:
        raise Unmeasured(f"{path} has no row dated on or before the as-of {asof}")
    out.sort()
    assert out[-1][0] <= asof, f"lookahead: {path} row {out[-1][0]} after as-of {asof}"
    return out


def measure(series: list, lv: dict) -> dict:
    """The drawdown of the newest row from the high-water mark of `series`, the
    worst drawdown in it (on the running HWM), and the first date each line was
    crossed. `series` is `read_series`'s output; `lv` is `levels`'s."""
    hwm_eq, hwm_date = series[0][1], series[0][0]
    for d, e in series:
        if e > hwm_eq:
            hwm_eq, hwm_date = e, d
    last_date, last_eq = series[-1]
    dd = 1.0 - last_eq / hwm_eq
    run, worst, worst_date = 0.0, 0.0, series[0][0]
    crossed = {"halve": None, "kill": None}
    for d, e in series:
        run = max(run, e)
        x = 1.0 - e / run
        if x > worst:
            worst, worst_date = x, d
        for k in crossed:
            if crossed[k] is None and x >= lv[k]:
                crossed[k] = d
    status = KILL if dd >= lv["kill"] else HALVE if dd >= lv["halve"] else OK
    return {"rows": len(series), "first_date": series[0][0], "last_date": last_date,
            "equity": last_eq, "hwm": hwm_eq, "hwm_date": hwm_date,
            "drawdown": round(dd, 8), "worst_drawdown": round(worst, 8),
            "worst_date": worst_date, "first_crossed": crossed, "status": status}


def _snapshot(state_dir: Path, asof: dt.date, lv: dict | None) -> dict:
    """The equity.csv reading, labelled. Shown beside the official one, NEVER an
    input to the status (module docstring, THE SERIES)."""
    path = Path(state_dir) / SNAPSHOT_FILE
    out = {"file": str(path), "label": SNAPSHOT_LABEL}
    if lv is None:
        out["unmeasured"] = "no levels to compare with (see the official reading)"
        return out
    try:
        out["reading"] = measure(read_series(path, asof), lv)
    except Unmeasured as e:
        out["unmeasured"] = str(e)
    return out


def sessions_after(row_date: dt.date, asof: dt.date) -> int:
    """The NYSE sessions s with row_date < s <= asof: a reading's staleness at the decide on
    `asof` (module docstring, READ THROUGH). From ops/schedule/nyse_calendar.py, the calendar
    run.py's `asof_for` reads (imported here, not at module level: standard library only
    there), never a weekday count."""
    from ops.schedule.nyse_calendar import is_trading_day, previous_trading_day
    if row_date > asof:
        raise ValueError(f"row {row_date} is after the as-of {asof}: lookahead")
    n, d = 0, asof if is_trading_day(asof) else previous_trading_day(asof)
    while d > row_date:
        n, d = n + 1, previous_trading_day(d)
    return n


def check(state_dir: Path, spec: dict, asof: dt.date, mode: str,
          read_through: dt.date | None = None) -> dict:
    """The drawdown record for the decide on `asof` (module docstring). Expected
    failures (no file, bad rows, bad levels, a series that ends before `asof`)
    give status UNMEASURED with `why`. Anything else is a bug and is raised; in
    report mode run.py records it as UNMEASURED.

    `read_through` (module docstring, READ THROUGH; te4's K0 only): None reads
    through `asof`, as always. A date on or before `asof` reads through it
    instead: the status of the newest row on or before it, which must be that
    date (else UNMEASURED), with the high-water mark over the rows on or before
    it, the reading labelled `stale` and the record naming `read_through`. Why:
    at the 22:00 decide the as-of's own EOD row never exists (E-2026-11-03-41)."""
    if mode not in MODES:
        raise ValueError(f"drawdown mode {mode!r} is not one of {MODES}")
    if read_through is not None and read_through > asof:
        raise ValueError(f"read_through {read_through} is after the as-of {asof}: lookahead")
    path = Path(state_dir) / OFFICIAL_FILE
    rec = {"mode": mode, "asof": asof, "series": OFFICIAL_LABEL, "file": str(path),
           "acted": False}       # report mode never acts on what it finds
    if read_through is not None:
        rec["read_through"] = read_through
    upto = asof if read_through is None else read_through
    lv = None
    try:
        lv = levels(spec)
        rec["levels"] = lv
        reading = measure(read_series(path, upto), lv)   # NO LOOKAHEAD: rows <= upto <= asof
        if read_through is not None:
            reading["stale"] = {"row_date": reading["last_date"],
                                "sessions": sessions_after(reading["last_date"], asof)}
        rec["reading"] = reading
        if read_through is None and reading["last_date"] != asof:
            raise Unmeasured(f"{path.name}'s newest row on or before the as-of is "
                             f"{reading['last_date']}, not the as-of {asof}: the figures in "
                             f"`reading` are as of {reading['last_date']}")
        if read_through is not None and reading["last_date"] != read_through:
            raise Unmeasured(f"{path.name}'s newest row on or before the read-through date "
                             f"{read_through} is {reading['last_date']}, not {read_through}: "
                             f"the figures in `reading` are as of {reading['last_date']}, "
                             f"{reading['stale']['sessions']} sessions before the as-of "
                             f"{asof}")
        rec["status"] = reading["status"]
    except Unmeasured as e:
        rec["status"], rec["why"] = UNMEASURED, str(e)
    rec["would_on"] = WOULD_ON[rec["status"]]
    rec["snapshot"] = _snapshot(state_dir, upto, lv)
    return rec


def unmeasured_record(mode: str, asof: dt.date, why: str) -> dict:
    """The record when `check` itself failed (report mode; run.py `_drawdown`)."""
    return {"mode": mode, "asof": asof, "series": OFFICIAL_LABEL, "acted": False,
            "status": UNMEASURED, "why": why, "would_on": WOULD_ON[UNMEASURED]}


def _pct(x: float) -> str:
    return f"{100 * x:.2f}%"


def _reading_text(r: dict) -> str:
    return (f"{_pct(r['drawdown'])} below the high-water mark ${r['hwm']:,.2f} "
            f"({r['hwm_date']}), at ${r['equity']:,.2f} ({r['last_date']})")


def lines(rec: dict) -> list[str]:
    """The session log's lines: the official reading (and what `on` would do),
    then the snapshot, labelled. Report mode says so on every line it acts on."""
    head = f"  DRAWDOWN ({rec['mode']})"
    lv = rec.get("levels")
    lines_ = f"; lines halve {_pct(lv['halve'])} / kill {_pct(lv['kill'])}" if lv else ""
    st = rec["status"]
    if st == UNMEASURED:
        first = f"{head}: UNMEASURED: {rec['why']}{lines_}"
        if "reading" in rec:             # a series that ends before the as-of: shown, dated
            first += f"; stale reading: {_reading_text(rec['reading'])}"
    else:
        r = rec["reading"]
        tag = {OK: "OK", HALVE: "HALVE LINE BREACHED", KILL: "KILL LINE BREACHED"}[st]
        first = f"{head}: {tag}: {_reading_text(r)} on {OFFICIAL_FILE}{lines_}"
        # A line crossed earlier and recovered from: a sticky `on` would still hold it.
        rank = {OK: 0, HALVE: 1, KILL: 2}
        for k, k_rank in (("kill", 2), ("halve", 1)):
            if r["first_crossed"][k] is not None and rank[st] < k_rank:
                first += (f"; the {k} line was crossed on {r['first_crossed'][k]} "
                          f"(a sticky `on` armed before then would still hold it)")
                break
    out = [first + f". `on` would: {rec['would_on']}. Report mode: no order changed."]
    snap = rec.get("snapshot")
    if snap is not None:
        what = (_reading_text(snap["reading"]) if "reading" in snap
                else f"unreadable: {snap['unmeasured']}")
        out.append(f"  DRAWDOWN snapshot ({SNAPSHOT_FILE}, after-hours marks, NOT the "
                   f"check's input): {what}")
    return out


# ---------------------------------------------------------------------------
# CEF TRIAL 55 ("te4"): the K0-K3 report lines
# ---------------------------------------------------------------------------
#
# results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md §6.3 requires, in the activation release,
# report lines for K0-K3 "in report mode and tested": "a stop that lives only in a document is
# a stop nobody reads". This is them. REPORT ONLY: nothing that trades reads any of it. K0's
# ACTION (a reduced build only on an exact OK) is quantt/session/run.py `_thin_k0_stop`, which
# reads this module's status; the line here reports whether that reading also KILLS the trial.
# Called only while the core spec sets `below_min_names = "trade_eligible"` (run.py
# `_thin_stops`), so with the key absent nothing here runs and plan.json has no `thin_stops`.
#
# READ THROUGH THE PREVIOUS SESSION (team lead's ruling 2026-11-03, E-2026-11-03-42). At the
# 22:00 decide the as-of's own EOD row never exists (E-2026-11-03-41), so K0 reads its status
# through the previous session's row, labelled one session stale (`check`'s `read_through`).
# The K1-K3 lines read eod_equity too, and as first built read the as-of's row, so every one
# of them would read UNMEASURED at 22:00 (the quant review). They are report only; they get
# the same read-through and the same label (`thin_stop_record`'s `read_through`, which run.py
# passes): K1 counts an earning day once its row is on or before the read-through date (the
# as-of's own earning day is counted at the next decide), and K2 and K3 divide the as-of
# close's positions by the read-through date's equity, one session stale (they are off by the
# ratio of the two equities, one session's return; labelled, never mixed with a fresh one).
# `read_through` None is the as-of reading, as first built.
# THE FRESHEST ROW (team lead's ruling 2026-11-04; the runner owner's review the same day, item
# 6). K0 reads the as-of's own row when it is there (the morning backstop), else D-1's
# (`run._thin_k0_drawdown`). The K1-K3 lines read through EXACTLY K0's reading date: run.py
# passes K0's `read_through`, and `thin_stop_record` refuses a K0 record that names another.
# So at the morning backstop K1 counts the as-of's own earning day and K2/K3 divide by the
# as-of's own equity (0 sessions stale, no note); at 22:00 they read D-1, labelled. K2 and K3
# always record `equity_date`, and an `equity_note` whenever it is not the as-of.
#
# Every input is passed in (the records, the series, the positions, the thresholds), so the
# function is tested on synthetic records; run.py does the reading.
#
# DEFINITIONS (§4.2, §6.3; compose.py's, where it has one):
#   reduced decision  §4.2: "a decide on which the sleeve's reduced build ran AND ITS TARGETS
#                     WERE SENT". A prior plan.json whose `thin_session.reduced` is true and
#                     whose `refusals` list is empty (the structured flag, never a reason
#                     string), whose targets were sent (`sent`, below; review fix F2 after
#                     7fcc2b7). The first build did not read the send, so a decided reduced plan
#                     whose late-market SEND was refused, dry or never ran counted, and K1
#                     compounded its earning day although the account held another book that
#                     session. A decided reduced plan that was NOT sent is not a reduced
#                     decision: it opens no episode, earns K1 nothing, and its close is not a
#                     reduced close for K2 or K3 (it neither breaks nor extends K3's run). One
#                     whose send cannot be established (`sent`'s UNMEASURED cases) makes the
#                     episode UNMEASURED, named, as an unreadable record does (READING BACK).
#   episode           reduced decisions fewer than THIN_EPISODE_GAP sessions apart; OPEN at this
#                     decide while the newest is fewer than THIN_EPISODE_GAP sessions back.
#   earning day       for a reduced decision whose session is s (filled at s's late window), the
#                     next session e; its return is eod_equity(e) / eod_equity(s) - 1, counted
#                     only once e is on or before the as-of date (no lookahead), or the
#                     read-through date when one is given.
#   K1                the maximum drawdown of the episode's earning-day returns compounded end
#                     to end from 1.0 at the episode's start; TRIPPED at or above the line.
#   K2, K3            at this decide, if the previous session's decision was reduced: the
#                     account's positions (after that session's fills) at the as-of closes,
#                     over eod_equity(as-of), or eod_equity(read-through date) when one is
#                     given (labelled). K2 the largest |name|, K3 |long - short|. TRIPPED
#                     above the line; K3 also above its run line on `thin_k3_run_sessions`
#                     reduced closes (the spec's `risk` block, required under the rule; a
#                     module constant until the runner owner's review 2026-11-04, item 9).
#                     K3's run counts reduced closes IN SEQUENCE (compose.py's
#                     `runs_above` over reduced decisions; a full session between them does not
#                     break it), read back from earlier plans' `thin_stops.K3.net` within the
#                     open episode only (§6.3's heading, "K1-K3 inside an episode"; the runner's
#                     owner confirmed it on 2026-11-04, recorded in the pre-registration's
#                     Approval section: the rule is the note's, and this implements it). A run
#                     that crossed two episodes, which compose.py would count, is not seen:
#                     episodes are 63 or more sessions apart. Each close is judged against
#                     today's line. WHICH RECORD HOLDS WHICH CLOSE: the decide for session X
#                     reads as-of previous(X), so plan(X).thin_stops.K3 judges the close of the
#                     session BEFORE X (its `session` field says so). The close before this
#                     decide's as-of is therefore in the as-of session's own plan, the newest
#                     record read back; the first build skipped it and counted one close too far
#                     back, so K3 tripped a close late on a true run and could trip on a broken
#                     one (both reviews of 7fcc2b7). Each earlier K3 counted must name the close
#                     it judged, or the run is UNMEASURED; so is a run still open where the
#                     walk stopped at a record it could not read.
#   send skip         the previous session's late-market SEND (send.json `skipped`, the run
#                     record's `skipped_at_send`) after a reduced decision. The send skips only
#                     orders that open or increase a short of a name no longer shortable
#                     (run.py `_send_planned`), so any entry is a lost short. Ruled 2026-11-03:
#                     accept it and label it; this is the label, and K3 watches the result.
#                     ONLY FROM A SEND THAT WENT (`_send_state`; review fix F3 after 7fcc2b7).
#                     `_send_planned` builds the skipped list BEFORE its gates, so a send that
#                     was then refused, or dry, writes the list and sends nothing; the first
#                     build labelled that a lost short. A send that did not go labels nothing
#                     (applies False, naming its exit): it is not a reduced decision (below).
#                     One whose outcome is not established leaves the session's record
#                     unmeasured, so whether the label applies reads UNMEASURED.
#   sent              (`_send_state`) whether a decision's targets went to the broker, read
#                     from the session's own records: plan.json `orders` / `plan_sha` /
#                     `execution` / `bp_scale`, send.json `plan_sha` / `exit` / `final` / `not_final`, and
#                     whether <D>/STARTED exists (run.py writes it before the first order of a
#                     set, and never otherwise; CLAUDE.md order-path rule 2); and, for a FAIL
#                     whose send.json records no order only, <D>/orders.jsonl and
#                     <D>/reconcile.json (run.py `_transmit`'s event log; verify.py's
#                     reconcile, `write_outputs`).
#                     WHAT run.py WRITES (read 2026-11-04, the runner owner's review item 10:
#                     te4 is PAPER ONLY and paper runs `late_market`, so this is the only case
#                     that will run). The late-market SEND (`_send_planned`) writes send.json on
#                     every outcome it reaches: `exit` (SENT, FAIL, DRY, REFUSED,
#                     NOTHING_TO_SEND), `plan_sha`, `skipped`, and `final` / `not_final`, which
#                     `_poll_final` fills ONLY for orders Alpaca accepted and the confirm read
#                     found: `final` {client_order_id: {status, filled, unfilled, ...}} for
#                     each that reached a final state by 30 s before the close, `not_final` the
#                     rest. A refused, dry or empty send writes `final` {} and `not_final` [].
#                     STARTED comes first, before any POST: a refusal never writes it. A FAIL
#                     comes from `_transmit` alone, after STARTED: a rejection (the rest still
#                     go), an ambiguous submit, a clock past the window, an order the confirm
#                     read did not find. The cls decide writes NO send.json: STARTED, then
#                     plan.json, then the transmit; its run record holds `sent`.
#                     THE RULE:
#                       * no orders: nothing needed sending, and the account already held the
#                         plan's targets when it was decided (a late-market decide with no
#                         orders exits NOTHING_TO_SEND and no send runs): SENT. EXCEPT when
#                         plan.json carries `bp_scale` (the owner's release-check of 78e3483,
#                         2026-11-09): the buying-power fit took every order out, so the
#                         account did NOT move to the targets: NOT SENT, and only for the one
#                         record run.py can write there (orders_in > 0, orders_out 0, no
#                         STARTED); any other `bp_scale` beside an empty plan is UNMEASURED
#                         (the independent review of PR #69, 2026-11-10);
#                       * late market, SENT: STARTED exists AND send.json's `exit` is SENT
#                         (the runner's rule-2 marker plus the send record), AND its `final` /
#                         `not_final` record at least one of the plan's orders, AND at least
#                         one share filled, or an order is still working (below). Partially
#                         filled orders are sent: what filled is the account's, which K1-K3
#                         read from the broker's own figures;
#                       * late market, "sent, nothing filled" (NOTHING_FILLED; the runner
#                         owner's round-2 answer (b), 2026-11-05: sent requires at least one
#                         fill): a SENT (never a FAIL, whose `final` omits any order of unknown
#                         fate) where every order `final` records ended FINAL with 0 shares
#                         filled, canceled, expired or rejected (NO_FILL_STATES), and
#                         `not_final` is empty. The
#                         book did not change, so it is NOT a reduced decision: no episode,
#                         nothing for K1 to compound, no reduced close for K2/K3. A 0-share final
#                         under any other state (`replaced`: another order may have filled;
#                         `done_for_day`; a `filled` with 0) is UNMEASURED, named, as is a
#                         `final` entry without a whole-number `filled`. An order in `not_final`
#                         was still working 30 s before the close and may yet fill, so with one
#                         the send stays SENT, as the owner's first review defined it;
#                       * late market, a FAIL CLASSIFIED FROM `final`: STARTED exists, `exit`
#                         FAIL, and `final` / `not_final` record what went (at least one of the
#                         plan's orders): SENT IN PART, and the episode names it
#                         (`sent_in_part`). Part of the reduced book is held, and K2/K3 must see
#                         it: a rejected short leaves exactly the one-sided book K3 watches;
#                       * late market, NOT SENT: DRY, REFUSED or NOTHING_TO_SEND with no STARTED
#                         and nothing in `final` / `not_final`; or no send.json and no STARTED
#                         (no send ran in the window);
#                       * late market, NOT SENT, "not sent: 0 submissions proved by <records>"
#                         (the runner owner's round-2 answer (a), 2026-11-05): a FAIL whose
#                         `final` and `not_final` are empty, with STARTED, ONLY when the records
#                         prove positively that no POST was made (`_zero_submissions`): <D>'s
#                         orders.jsonl exists and holds ZERO `submit` events, only the events
#                         `_transmit` writes when it stops at the clock read that precedes
#                         every POST (PRE_POST_EVENTS), each naming one of the plan's orders;
#                         and, if <D>/reconcile.json is there (verify, after the close), it
#                         names no order of the session's client_order_id prefix and was
#                         written with STARTED. `_transmit` appends `submit` to orders.jsonl
#                         BEFORE each POST (fsynced, records.append_jsonl), so no `submit`
#                         means no POST; verify lists every order Alpaca holds with D's
#                         prefix, so its silence is the broker's;
#                       * late market, UNMEASURED, named, never a guess: a FAIL whose `final` and
#                         `not_final` are empty and whose zero submissions are NOT proved (an
#                         accepted POST the confirm read did not find, or an ambiguous submit,
#                         is in neither: orders may have gone): orders.jsonl missing, unreadable
#                         or holding a `submit`, a reconcile.json that cannot be read or names
#                         one of the session's orders; SENT or
#                         FAIL without STARTED; a STARTED beside a refused, dry, empty or missing
#                         send record (a later run's record over the send's, or a send that never
#                         wrote one); a send.json of another plan_sha; `final` or `not_final`
#                         missing or malformed, or naming an order the plan does not hold; an
#                         `exit` no send writes;
#                       * cls (the decide is the send): SENT exactly when STARTED exists. A cls
#                         run writes no send.json, so STARTED is its only per-session record of
#                         the set; a set that began counts as sent, including one that failed
#                         part-way or whose every order was rejected (its run record, not read
#                         here, says what went). Never reached for te4: run.py `thin_rule_for`
#                         refuses the key under any mode but late_market (the owner's
#                         release-check of 78e3483, 2026-11-09), because under cls an episode
#                         could open on STARTED alone with no fill known.
# READING BACK. Sessions are walked newest first from the one before this decide. A plan.json
# with no `thin_session` was decided with the key absent, when no reduced build could run, and
# ends the walk (the rule was off before it). A record that is there and cannot be read, a
# send whose outcome cannot be established (`sent`), or a session with a send.json or a
# STARTED and no plan.json (something went with no plan on record) makes the WHOLE episode
# UNMEASURED, named, and stops the walk: the walk cannot say what lies beyond it.
#   A NAMED GAP (the runner owner's review 2026-11-04, item 5) is a session with NO record at
#   all: no plan.json, no send.json, no STARTED (the runner did not run, or its decide failed
#   before writing a plan; nothing was sent, but whether its decision would have been a reduced
#   one is unknown). The walk records it in `gaps` and goes on. As first built a gap stopped
#   the walk and made every line UNMEASURED for up to 63 sessions, so one missed evening blinded
#   K0-K3 for three months. Now a gap makes UNMEASURED only the stops whose READ WINDOW holds it:
#     K0's episode state  the sessions fewer than THIN_EPISODE_GAP back: OPEN still reads OPEN
#                         when a known reduced decision lies in it (a gap can only add one); with
#                         none known, a gap there makes the state UNMEASURED, so K0 cannot read
#                         CLEAR on HALVE or KILL;
#     K1                  the episode's decisions whose earning day is on or before the
#                         read-through date: a gap there might be one whose day K1 would
#                         compound. A gap whose earning day comes later (the as-of session's,
#                         or the session before it when read through D-1) is outside it;
#     K2, the send skip   the as-of session alone (its close, its send);
#     K3                  the as-of session, then the closes its run reads back: a gap among them
#                         (a close that might be a reduced one, or the plan that would hold one's
#                         K3) makes the run UNMEASURED; a gap beyond where the run breaks does not.

THIN_EPISODE_GAP = 63    # sessions: build_panel's ADV window, the screen's merge rule (§4.2)
THIN_SCAN_LIMIT = 2000   # sessions walked back at most; beyond it the episode is UNMEASURED
TRIPPED, CLEAR, KILLED, NOT_APPLICABLE = "TRIPPED", "CLEAR", "KILLED", "N/A"


def _decided_reduced(plan: dict) -> bool:
    """The sleeve's reduced build ran on a decided plan: the structured flag, no refusals."""
    ts = plan.get("thin_session") or {}
    return ts.get("reduced") is True and plan.get("refusals") == []


def _is_reduced(d, day: dict) -> tuple[bool, str | None, str | None]:
    """(reduced, why not, in part) for the session d: a REDUCED DECISION (block comment) is a
    decided reduced plan whose targets were sent (`_send_state`). `why not` names a decided
    reduced plan that was not sent, else None; `in part` says how, when the send went only in
    part (a late-market FAIL that `_send_state` classified from send.json's `final`), else
    None. Raises `Unmeasured` when the send cannot be read."""
    plan = day["plan"]
    if not _decided_reduced(plan):
        return False, None, None
    went, how = _send_state(d, day)
    if not went:
        if how.startswith(NOTHING_FILLED):
            # Round-2 answer (b): it went to the broker and the book did not change.
            return False, f"{d}'s reduced decision changed nothing: {how}", None
        return False, f"{d}'s reduced decision was not sent: {how}", None
    failed = (plan.get("execution") == "late_market" and bool(plan.get("orders"))
              and (day.get("send") or {}).get("exit") == SEND_FAILED)
    return True, None, (how if failed else None)


SEND_WENT = "SENT"                                         # send.json `exit` of a set that went
SEND_FAILED = "FAIL"                                       # `_transmit` stopped or was rejected
SEND_NOT_GONE = ("DRY", "REFUSED", "NOTHING_TO_SEND")      # exits that send nothing
# Round-2 answer (b) (block comment, `sent`): the final states the owner named for an order that
# ended with nothing filled, and the label of a send whose every order did.
NO_FILL_STATES = ("canceled", "expired", "rejected")
NOTHING_FILLED = "sent, nothing filled"


def _filled(d, final: dict) -> dict:
    """{client_order_id: shares filled} from send.json's `final` (`_poll_final` writes `filled`,
    an int, for every order it saw final). Raises `Unmeasured`, naming the order, on an entry
    without a whole, non-negative `filled`: whether anything filled is then not established."""
    out = {}
    for cid, f in final.items():
        n = f.get("filled") if isinstance(f, dict) else None
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise Unmeasured(f"{d}'s send.json `final` records {cid} with filled {n!r}, not a "
                             f"whole number of shares: whether anything filled is not "
                             f"established")
        out[cid] = n
    return out


def _went(d, plan: dict, send: dict) -> list:
    """The client_order_ids send.json records as having reached Alpaca: the keys of `final`
    (accepted, confirmed, final by the poll's deadline, with their fills) and `not_final`
    (accepted and confirmed, still working at it). `_poll_final` writes both, and nothing
    else does (block comment, WHAT run.py WRITES). Raises `Unmeasured`, naming the session
    and the field, when either is missing or malformed, or names an order the plan does not
    hold: a record of an order nobody decided is not a record of this plan's send."""
    final, not_final = send.get("final"), send.get("not_final")
    if not isinstance(final, dict):
        raise Unmeasured(f"{d}'s send.json has no `final` object ({final!r}): what went is "
                         f"not recorded")
    if not isinstance(not_final, list):
        raise Unmeasured(f"{d}'s send.json has no `not_final` list ({not_final!r}): what went "
                         f"is not recorded")
    ids = set(final) | set(not_final)
    planned = {o.get("client_order_id") for o in plan["orders"] if isinstance(o, dict)}
    stray = sorted(map(str, ids - planned))
    if stray:
        raise Unmeasured(f"{d}'s send.json records order(s) {stray} that its plan.json does not "
                         f"hold: not this plan's send")
    return sorted(ids)


def _send_state(d, day: dict) -> tuple[bool, str]:
    """(sent, how) for the decision recorded for session `d` (`day` = read_day(d)): did its
    targets go to the broker? The rule, and what run.py writes that it reads, is the block
    comment's `sent` (the runner owner's review 2026-11-04, item 10, and item 5: classify the
    send from send.json's `final` wherever it exists). Raises `Unmeasured`, naming the session
    and the record, when the records cannot say: never a guess either way."""
    plan = day["plan"]
    orders = plan.get("orders")
    if not isinstance(orders, list):
        raise Unmeasured(f"{d}'s plan.json has no `orders` list ({orders!r}): whether its "
                         f"targets were sent cannot be read")
    if not orders:
        # Empty for one of two reasons, and they differ (the owner's release-check of 78e3483,
        # 2026-11-09). If the buying-power fit took every order out (`bp_scale` orders_in > 0,
        # orders_out 0: run.py records them so verify can tell "a missed day" from "nothing to
        # do"), the account did NOT move to the reduced build's targets.
        # ONLY THAT SHAPE IS READ (the independent review of PR #69, 2026-11-10). run.py writes
        # `bp_scale` only when the decide had orders (orders_in = their count, > 0) and makes the
        # fitted set the plan's orders (orders_out = its length), so on an empty plan the one
        # record it can write is orders_in > 0 with orders_out 0. Any other record beside an
        # empty plan (a null, a bool, orders_in 0, orders_out > 0) is a file run.py did not write
        # as it stands, and reads Unmeasured, never "already held its targets". A set with no
        # orders never STARTS (STARTED precedes the first order, CLAUDE.md order-path rule 2),
        # so STARTED beside a fit-emptied plan contradicts it too.
        if "bp_scale" in plan:
            fit = plan["bp_scale"]
            n_in = fit.get("orders_in") if isinstance(fit, dict) else None
            n_out = fit.get("orders_out") if isinstance(fit, dict) else None
            if not all(isinstance(n, int) and not isinstance(n, bool) for n in (n_in, n_out)):
                raise Unmeasured(f"{d}'s plan.json has no orders and a malformed `bp_scale` "
                                 f"({fit!r}): whether its targets were sent cannot be read")
            if not (n_in > 0 and n_out == 0):
                raise Unmeasured(f"{d}'s plan.json has no orders and a `bp_scale` of orders_in "
                                 f"{n_in}, orders_out {n_out}: run.py fits only a plan with orders "
                                 f"and writes the fitted set as the plan's orders, so the records "
                                 f"contradict each other")
            started = day.get("started")
            if started is not False:
                raise Unmeasured(
                    f"{d}'s buying-power fit scaled the plan's orders to none, and STARTED is "
                    f"{started!r}: " + ("a set with no orders never starts, so the records "
                                        "contradict each other" if started is True else
                                        "whether a set STARTED was not read"))
            return False, (f"{d}'s buying-power fit scaled the plan's {n_in} order(s) to none "
                           f"({fit.get('binding')}): nothing was sent")
        return True, f"{d}'s plan had no orders: the account already held its targets"
    started = day.get("started")
    if not isinstance(started, bool):
        raise Unmeasured(f"whether a set STARTED for {d} was not read ({started!r})")
    if plan.get("execution") != "late_market":
        return started, (f"cls: the decide is the send, and a set "
                         + ("STARTED" if started else "never STARTED") + f" for {d}")
    send = day.get("send")
    if send is None:
        if started:
            raise Unmeasured(f"a set STARTED for {d} and there is no send.json: what went is "
                             f"not recorded")
        return False, f"no send ran for {d} (no send.json, no STARTED)"
    if not isinstance(send, dict):
        raise Unmeasured(f"{d}'s send.json is {type(send).__name__}, not an object")
    if send.get("plan_sha") != plan.get("plan_sha"):
        raise Unmeasured(f"{d}'s send.json is of plan_sha {send.get('plan_sha')!r}, its "
                         f"plan.json of {plan.get('plan_sha')!r}")
    ex = send.get("exit")
    went = _went(d, plan, send)
    of = f"{len(went)} of the plan's {len(orders)} order(s)"
    if ex in (SEND_WENT, SEND_FAILED):
        if not started:
            raise Unmeasured(f"{d}'s send.json exit is {ex} and no STARTED exists: run.py writes "
                             f"STARTED before the first order of a set (CLAUDE.md order-path "
                             f"rule 2), so the records contradict each other")
        if not went:
            unproved = (f"{d}'s send exited {ex} and its `final` and `not_final` record no "
                        f"order: whether any went is not established (an accepted POST the "
                        f"confirm read did not find, or an ambiguous submit, is in neither)")
            if ex == SEND_FAILED:
                # Not sent only where the records prove that no POST was made (the runner
                # owner's round-2 answer (a)); any weaker evidence raises, naming it.
                return False, _zero_submissions(d, plan, day, unproved)
            raise Unmeasured(unproved)
        # SENT REQUIRES AT LEAST ONE FILL (round-2 answer (b)): every order final at 0 shares,
        # none still working, is "sent, nothing filled", not a reduced decision. ON EXIT SENT
        # ONLY: SENT means no rejection, no ambiguous submit and no missing confirm, so `final`
        # plus `not_final` covers every order sent. A FAIL's `final` leaves out any order whose
        # outcome is unknown (accepted but not found at the confirm read, or ambiguous), so
        # zeros there cannot say the book did not change: it stays "sent in part", which counts
        # and fails closed (the review of fa9e101: a HALVE read CLEAR instead of KILLED).
        filled = _filled(d, send["final"])
        if ex == SEND_WENT and not send["not_final"] and not any(filled.values()):
            states = {c: send["final"][c].get("status") for c in sorted(filled)}
            odd = {c: s for c, s in states.items() if s not in NO_FILL_STATES}
            if odd:
                raise Unmeasured(f"{d}'s send exited {ex} and every order send.json's `final` "
                                 f"records ended with 0 shares filled, but {odd} under a state "
                                 f"other than {list(NO_FILL_STATES)}: whether the book changed "
                                 f"is not established")
            return False, (f"{NOTHING_FILLED}: {d}'s send exited {ex}; send.json's `final` "
                           f"records {of} final with 0 shares filled ({states}) and none still "
                           f"working: the book did not change")
        unfilled = sorted(c for c, f in send["final"].items()
                          if isinstance(f, dict) and f.get("unfilled"))
        fills = (f"; unfilled at the deadline: {unfilled}" if unfilled else "") + (
            f"; not final by the deadline: {sorted(send['not_final'])}"
            if send["not_final"] else "")
        if ex == SEND_WENT:
            return True, f"{d}'s send exited SENT; send.json records {of} as sent{fills}"
        return True, (f"{d}'s send exited FAIL after part of the set went: send.json's "
                      f"`final` records {of} as sent ({went}){fills}")
    if ex in SEND_NOT_GONE:
        if started:
            raise Unmeasured(f"{d}'s send.json exit is {ex} and a set STARTED: a later run's "
                             f"record over the send's, or a send that never wrote one; whether "
                             f"its targets were sent is not established")
        if went:
            raise Unmeasured(f"{d}'s send.json exit is {ex} and it records orders that went "
                             f"({went}): the record contradicts itself")
        return False, f"{d}'s send exited {ex}: nothing was sent"
    raise Unmeasured(f"{d}'s send.json exit is {ex!r}, not one a send writes "
                     f"({[SEND_WENT, SEND_FAILED, *SEND_NOT_GONE]}): whether its targets were "
                     f"sent is not established")


# What `_transmit` (run.py) writes to orders.jsonl when it stops at the Alpaca clock read that
# precedes EVERY POST, before that POST: `clock_error` (the read failed) or `cutoff` (the clock
# was outside the send window). Each names the order it stopped before. Nothing else it writes
# can stand without a `submit` line before it: `accepted`, `rejected`, `ambiguous`, `lookup`,
# `error`, `confirm`, `final`, `poll_error`, `not_final_at_deadline` and
# `skipped_after_rejection` all follow a submit (of that order, or of the rejected one).
PRE_POST_EVENTS = ("cutoff", "clock_error")
NOT_SENT_PROVED = "not sent: 0 submissions proved by"      # the owner's name for the case


def _utf8(d, raw, name: str, unproved: str) -> str:
    """`raw`, a record's bytes as run.py's reader read them (`_thin_read_day`), as text; raises
    `Unmeasured` naming the record when it is not bytes of UTF-8."""
    if not isinstance(raw, bytes):
        raise Unmeasured(f"{unproved}; {d}/{name} was read as {type(raw).__name__}, not bytes")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise Unmeasured(f"{unproved}; {d}/{name} is not UTF-8 ({e})") from None


def _zero_submissions(d, plan: dict, day: dict, unproved: str) -> str:
    """The label "not sent: 0 submissions proved by <records>" for a late-market send that
    exited FAIL with STARTED and nothing in send.json's `final` / `not_final` (the caller has
    read those), when the records PROVE that no order was POSTed. Raises `Unmeasured`, naming the
    record that does not prove it, otherwise.

    WHY (the runner owner's round-2 answer (a), 2026-11-05). `final` / `not_final` hold only
    orders Alpaca accepted AND the confirm read found, so an empty pair cannot tell a send that
    stopped before its first POST from one whose POSTs went unconfirmed: until this answer every
    such FAIL read UNMEASURED, and with it the whole episode. The owner ruled it NOT SENT only on
    positive proof, and fail-closed on anything weaker:
      * <D>/orders.jsonl EXISTS and holds ZERO `submit` events. `_transmit` appends `submit`
        (fsynced: records.append_jsonl) BEFORE each POST, so a POST without one cannot happen.
        Missing, unreadable or empty, or holding a `submit`, it proves nothing. Every event it
        holds must be one `_transmit` writes before a POST (PRE_POST_EVENTS) naming one of the
        plan's orders: any other event with no `submit` is a log that contradicts itself.
      * <D>/reconcile.json, IF PRESENT (verify, after the close), names no order of the
        session's client_order_id prefix (`day["order_prefix"]`, `<cid_prefix>-<YYYYMMDD>-`:
        decide.client_order_id's scheme, the prefix gate 6 and verify match on). verify lists
        every order Alpaca holds with that prefix, into `orders` when orders.jsonl records it
        and into `problems` ("at Alpaca but not in orders.jsonl") when it does not, so a
        reconcile.json that never names the prefix is the broker's own word that no order of
        the session exists. Every string in it is searched, keys included, so a new field
        verify may add later cannot hide an order. ONE mention is not an order: verify's
        `read_orders_jsonl` refuses any event that has no `submit` line, so on exactly the
        session this proves it writes "orders.jsonl line <n>: event 'cutoff' for <cid>, which
        has no submit line" into `problems` (and the verdict line). That text, for an event
        this function has itself read from orders.jsonl at line <n>, is a statement about the
        local log, and is the only text not searched. A reconcile.json written without STARTED
        (`started` not true) is not the reconcile of this send. Absent, the proof rests on
        orders.jsonl, send.json and STARTED (verify has not run, or runs at 17:30 after a
        22:00 decide read the session back).
    The reader passes the two files as BYTES, parsed only here: a damaged orders.jsonl must
    not blind the walk on a session whose send.json already says what went."""
    missing = [k for k in ("orders_log", "reconcile", "order_prefix") if k not in day]
    if missing:
        raise Unmeasured(f"{unproved}; the reader did not read {missing}, so zero submissions "
                         f"cannot be proved")
    prefix = day["order_prefix"]
    if not (isinstance(prefix, str) and prefix):
        raise Unmeasured(f"{unproved}; the session's client_order_id prefix is {prefix!r}")
    planned = [o.get("client_order_id") for o in plan["orders"] if isinstance(o, dict)]
    off = sorted(str(c) for c in planned if not (isinstance(c, str) and c.startswith(prefix)))
    if off or len(planned) != len(plan["orders"]):
        raise Unmeasured(f"{unproved}; the plan's order(s) {off} do not carry the session's "
                         f"client_order_id prefix {prefix!r}: reconcile.json would be searched "
                         f"for the wrong orders")
    raw = day["orders_log"]
    if raw is None:
        raise Unmeasured(f"{unproved}; there is no {d}/orders.jsonl, so zero submissions cannot "
                         f"be proved")
    events = []
    for n, line in enumerate(_utf8(d, raw, "orders.jsonl", unproved).splitlines(), 1):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError as err:
            raise Unmeasured(f"{unproved}; {d}/orders.jsonl line {n} is not JSON ({err})") from None
        if not (isinstance(e, dict) and isinstance(e.get("event"), str)):
            raise Unmeasured(f"{unproved}; {d}/orders.jsonl line {n} is not an event object")
        events.append((n, e))
    submits = [e.get("client_order_id") for _, e in events if e["event"] == "submit"]
    if submits:
        raise Unmeasured(f"{unproved}; {d}/orders.jsonl records {len(submits)} `submit` "
                         f"event(s) {submits}: a POST followed each")
    if not events:
        raise Unmeasured(f"{unproved}; {d}/orders.jsonl holds no event: `_transmit` writes one "
                         f"before it stops, so this is not its log")
    for n, e in events:
        if e["event"] not in PRE_POST_EVENTS:
            raise Unmeasured(f"{unproved}; {d}/orders.jsonl line {n} is a {e['event']!r} event "
                             f"with no `submit` before it: the log contradicts itself")
        if e.get("client_order_id") not in planned:
            raise Unmeasured(f"{unproved}; {d}/orders.jsonl line {n} names "
                             f"{e.get('client_order_id')!r}, which the plan does not hold")
    log = ", ".join(f"{e['event']} before {e['client_order_id']}" for _, e in events)
    rc = day["reconcile"]
    if rc is None:
        rc_how = f"{d}/reconcile.json absent (verify has not reconciled {d})"
    else:
        rc_how = _reconcile_silent(d, rc, prefix, events, unproved)
    return (f"{NOT_SENT_PROVED} {d}/send.json (exit FAIL, `final` and `not_final` empty), "
            f"{d}/STARTED, {d}/orders.jsonl ({len(events)} event(s), 0 `submit`: {log}), "
            f"{rc_how}")


def _reconcile_silent(d, raw, prefix: str, events: list, unproved: str) -> str:
    """How <D>/reconcile.json (bytes) proves the broker holds no order of `prefix`, for
    `_zero_submissions` (its docstring: what is searched and the one text that is not). Raises
    `Unmeasured`, naming where it names one, or why it cannot be read."""
    try:
        rc = json.loads(_utf8(d, raw, "reconcile.json", unproved))
    except json.JSONDecodeError as err:
        raise Unmeasured(f"{unproved}; {d}/reconcile.json is not JSON ({err})") from None
    if not isinstance(rc, dict):
        raise Unmeasured(f"{unproved}; {d}/reconcile.json is {type(rc).__name__}, not an object")
    if rc.get("started") is not True:
        raise Unmeasured(f"{unproved}; {d}/reconcile.json was written with started "
                         f"{rc.get('started')!r}: not the reconcile of this send")
    for f in ("orders", "problems"):
        if not isinstance(rc.get(f), list):
            raise Unmeasured(f"{unproved}; {d}/reconcile.json has no `{f}` list "
                             f"({rc.get(f)!r}): what verify found at the broker is not read")
    own = {f"orders.jsonl line {n}: event {e['event']!r} for {e['client_order_id']}, which has "
           f"no submit line" for n, e in events}
    hits = []

    def search(x, where):
        if isinstance(x, dict):
            for k, v in x.items():
                search(k, f"{where} (a key)")
                search(v, f"{where}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                search(v, f"{where}[{i}]")
        elif isinstance(x, str):
            s = x
            if where == "$.verdict":
                for t in own:
                    s = s.replace(t, "")
            elif where.startswith("$.problems[") and x in own:
                return
            if prefix in s:
                hits.append(f"{where}: {x[:200]!r}")
    search(rc, "$")
    if hits:
        raise Unmeasured(f"{unproved}; {d}/reconcile.json names order(s) of the session's prefix "
                         f"{prefix!r}: {hits}")
    if rc["orders"]:
        # verify fills `orders` from orders.jsonl's `submit` lines only: rows there mean it read
        # a log with submits, which is not the log read here.
        raise Unmeasured(f"{unproved}; {d}/reconcile.json lists {len(rc['orders'])} order "
                         f"row(s), which verify builds from orders.jsonl's `submit` lines: not "
                         f"the orders.jsonl read here")
    return f"{d}/reconcile.json (started, no order row, no order of prefix {prefix!r})"


def _dates(ds) -> str:
    """A short list of sessions for a `why`: all of them up to five, else the newest and the
    oldest and the count (the record keeps the whole list)."""
    ds = sorted(ds)
    if len(ds) <= 5:
        return str([str(d) for d in ds])
    return f"{len(ds)} sessions, {ds[0]} .. {ds[-1]}"


def _gap(day: dict) -> bool:
    """A NAMED GAP (block comment, READING BACK): no plan.json, no send.json and no STARTED."""
    return day.get("plan") is None and day.get("send") is None and day.get("started") is False


def _walk(session_date, previous_session, read_day) -> dict:
    """The open episode's records, read back from the session before `session_date`.

    Walks newest first. It stops at a session THIN_EPISODE_GAP or more sessions back from the
    oldest reduced decision found so far (from this decide when none is found): that session
    cannot belong to the episode. Returns {"status": "OPEN" | "NONE" | "UNMEASURED", "why",
    "days": [(session, day | None)] newest first (None for a gap), "reduced": [session, ...]
    newest first, "unsent": {session: why} (decided reduced plans that were not sent, or
    sent with nothing filled: round-2 answer (b)),
    "in_part": {session: how} (reduced decisions whose send went only in part: a FAIL
    classified from send.json's `final`), "gaps": [session, ...] newest first (block comment,
    READING BACK: sessions with no record at all), "complete" (False when the walk stopped at
    a record it could not read, or the scan limit), "scanned"}. OPEN means a reduced decision
    fewer than THIN_EPISODE_GAP sessions back; UNMEASURED with `complete` True means none is
    known there and a gap is. A session whose send cannot be read is not appended to `days`
    (it is the record that could not be read)."""
    days, reduced, unsent, part, gaps = [], [], {}, {}, []
    d, k, last = session_date, 0, 0

    def out(status, why, complete, scanned):
        return {"status": status, "why": why, "days": days, "reduced": reduced,
                "unsent": unsent, "in_part": part, "gaps": gaps, "complete": complete,
                "scanned": scanned}
    while True:
        d = previous_session(d)
        k += 1
        if k - last >= THIN_EPISODE_GAP:
            why = f"{THIN_EPISODE_GAP} sessions back from the " + (
                "oldest reduced decision found" if reduced else "this decide") + " reached"
            break
        if k > THIN_SCAN_LIMIT:
            return out(UNMEASURED, f"more than {THIN_SCAN_LIMIT} sessions read back", False,
                       k - 1)
        try:
            day = read_day(d)
        except Exception as e:  # recorded, named: an unreadable record is not an empty one
            return out(UNMEASURED, f"the record of {d} could not be read: "
                       f"{type(e).__name__}: {e}", False, k)
        if _gap(day):
            gaps.append(d)           # named; the stops whose window holds it read UNMEASURED
            days.append((d, None))
            continue
        plan = day.get("plan")
        if plan is None:
            has = [n for n, v in (("a send.json", day.get("send") is not None),
                                  ("a STARTED", day.get("started") is not False)) if v]
            return out(UNMEASURED, f"no plan.json for the session {d}, which has "
                       f"{' and '.join(has)}: something was recorded as sent with no plan on "
                       f"record", False, k)
        if "thin_session" not in plan:
            why = f"{d} was decided with the key absent"
            break
        try:
            is_red, not_sent, in_part = _is_reduced(d, day)
        except Unmeasured as e:     # a send that cannot be read is not a send that did not go
            return out(UNMEASURED, str(e), False, k)
        days.append((d, day))
        if is_red:
            reduced.append(d)
            last = k
            if in_part is not None:
                part[d] = in_part
        elif not_sent is not None:
            unsent[d] = not_sent
    if reduced:
        return out("OPEN", why, True, k)
    if gaps:
        return out(UNMEASURED, f"no reduced decision is known within {THIN_EPISODE_GAP} "
                   f"sessions, and {_dates(gaps)} have no record (no plan.json, send.json or "
                   f"STARTED): whether any was a reduced decision is unknown; {why}", True, k)
    return out("NONE", why, True, k)


def _verdict(stat, line, above_or_at: bool) -> str:
    if line is None:
        return UNMEASURED
    return TRIPPED if (stat >= line if above_or_at else stat > line) else CLEAR


def thin_stop_record(*, asof, session_date, drawdown: dict, current: dict, previous_session,
                     read_day, series, positions: dict, closes: dict,
                     thresholds: dict, read_through=None) -> dict:
    """The K0-K3 report lines for the decide on `asof` for `session_date` (block comment above).

    `drawdown` is K0's drawdown record (`check`; run.py passes K0's own, read through the
    freshest row it had: the as-of's own, else the session before it; when it names a
    `read_through`, that must be `read_through` here, or this raises); `current` this decide's
    `thin_session`; `previous_session(d)` the NYSE
    session before d; `read_day(d)` -> {"plan": dict | None, "send": dict | None, "started":
    bool, "orders_log": bytes | None, "reconcile": bytes | None, "order_prefix": str} for the
    session d (it may raise; the last three are read only for a late-market FAIL that records
    no order, `_zero_submissions`, and a reader without them leaves that case UNMEASURED);
    `series` the eod_equity rows [(date, equity)] on
    or before `asof` (or `read_through`), or a string saying why there are none; `positions`
    {symbol: signed shares} now; `closes` {symbol: as-of close}; `thresholds` the five
    `risk.thin_*` values (registry `cef_thin_stop_levels`: the four lines, None where absent,
    that line then reading UNMEASURED, and K3's run length `thin_k3_run_sessions`, which the
    registry requires under the rule); `read_through` None
    (K1-K3 read eod_equity through the as-of) or a session on or before it (they read through
    that session, labelled with its staleness: block comment, READ THROUGH THE PREVIOUS
    SESSION and THE FRESHEST ROW). Pure: reads nothing but what it is given."""
    upto = asof if read_through is None else read_through
    eq = dict(series) if isinstance(series, list) else None
    eq_why = None if eq is not None else f"no equity series: {series}"
    if read_through is None:
        assert eq is None or all(d <= asof for d in eq), "lookahead: an equity row after the as-of"
    else:
        # NO LOOKAHEAD: the read-through date is on or before the as-of, and no row after it
        # is read (run.py reads the series through it).
        if read_through > asof:
            raise ValueError(f"read_through {read_through} is after the as-of {asof}: lookahead")
        assert eq is None or all(d <= read_through for d in eq), (
            "lookahead: an equity row after the read-through date")
    th = dict(thresholds)
    w = _walk(session_date, previous_session, read_day)
    rec = {"report_only": True, "asof": asof, "session_date": session_date,
           "episode": {"status": w["status"], "why": w["why"], "scanned": w["scanned"],
                       "reduced_sessions": sorted(w["reduced"]),
                       "this_decide_reduced": current.get("reduced") is True}}
    if w["gaps"]:
        rec["episode"]["gaps"] = sorted(w["gaps"])      # named (block comment, READING BACK)
    if w["in_part"]:
        # A reduced decision whose send exited FAIL after part of the set went (`_send_state`,
        # classified from send.json's `final`): counted, and named, never silently whole.
        rec["episode"]["sent_in_part"] = {str(d): how for d, how in sorted(w["in_part"].items())}
    # K1-K3 READ THROUGH EXACTLY K0'S READING DATE (the runner owner's review 2026-11-04, item
    # 6): the freshest row K0 had, the as-of's own at the morning backstop, else D-1's. A K0
    # record that names a read-through date other than the one the lines are given would mix
    # two dates silently: refused.
    if "read_through" in drawdown and drawdown["read_through"] != read_through:
        raise ValueError(f"the K1-K3 lines read through {read_through} and K0's record through "
                         f"{drawdown['read_through']}: they must read the same row")
    n = 0
    if read_through is not None:
        d = asof
        while d > read_through:
            d, n = previous_session(d), n + 1
        if d != read_through:
            raise ValueError(f"read_through {read_through} is not a session before the as-of "
                             f"{asof} (the walk back reached {d})")
        # The label says what the DATA showed at this decide (the as-of's row there or not),
        # never which slot ran. This function is not told the slot, and the two do not always
        # agree: the as-of's row can be missing at a morning decide and present at 22:00. As
        # first built it named "the morning backstop" or "the 22:00 decide" from the staleness
        # alone, and so named the wrong slot whenever they disagreed (review of 4e1ab0b).
        why_row = ("the as-of's own row, there at this decide: the freshest row (team lead's "
                   "ruling 2026-11-04)" if n == 0 else
                   f"{n} session(s) before the as-of {asof}: the as-of's row is not there yet "
                   f"at this decide, so the freshest row is this one (team lead's rulings "
                   f"2026-11-03 and 2026-11-04)")
        rec["read_through"] = {"date": read_through, "sessions_stale": n,
                               "label": f"eod_equity read through {read_through}, {why_row}"}
    # ---- K0: the account, read at this decide (K0's own reading: its record says through when)
    status = drawdown.get("status")
    k0 = {"status": status, "asof": drawdown.get("asof"),
          "acted": current.get("stopped_by") == "K0"}
    if "read_through" in drawdown:
        k0["read_through"] = drawdown["read_through"]
        k0["stale"] = (drawdown.get("reading") or {}).get("stale")
    if status in (HALVE, KILL):
        k0["verdict"] = {"OPEN": KILLED, "NONE": CLEAR}.get(w["status"], UNMEASURED)
    else:
        k0["verdict"] = CLEAR       # OK, or UNMEASURED: flattens the session, kills nothing
    rec["K0"] = k0
    # ---- K1: the episode's earning days
    line = th.get("thin_k1_episode_drawdown")
    k1 = {"line": line}
    sessions = [x[0] for x in w["days"]]              # newest first, consecutive sessions
    # K1's read window holds a gap whose earning day (the next session) is read by now: it
    # might be a reduced decision whose day K1 would compound (block comment, READING BACK).
    k1_gaps = [g for i, g in enumerate(sessions) if w["days"][i][1] is None
               and (session_date if i == 0 else sessions[i - 1]) <= upto]
    if not w["complete"]:
        k1.update(verdict=UNMEASURED, why=f"episode unmeasured: {w['why']}")
    elif k1_gaps:
        k1.update(verdict=UNMEASURED,
                  why=(f"{_dates(k1_gaps)} have no record (no plan.json, send.json or "
                       f"STARTED), and their earning days are read by now: whether K1 would "
                       f"compound them is unknown"))
    elif not w["reduced"] and current.get("reduced") is True:
        k1.update(earning_days=0, drawdown=0.0, verdict=_verdict(0.0, line, True),
                  why="the episode opens at this decide; no day earned yet")
    elif not w["reduced"]:
        k1.update(verdict=NOT_APPLICABLE, why="no open episode" + (
            f" known; {_dates(w['gaps'])} have no record, and their earning days are not read "
            f"yet" if w["gaps"] else ""))
    else:
        rets, missing, unread = [], None, []
        for s in sorted(w["reduced"]):
            i = sessions.index(s)
            e = session_date if i == 0 else sessions[i - 1]
            if e > asof:
                continue                              # not yet earned
            if e > upto:
                unread.append(e)                      # earned, its row after the read-through
                continue
            if eq is None:
                missing = eq_why
            elif s not in eq or e not in eq:
                missing = f"no eod_equity row for {s if s not in eq else e}"
            if missing is not None:
                break
            rets.append((e, eq[e] / eq[s] - 1.0))
        if missing is not None:
            k1.update(verdict=UNMEASURED, why=missing)
        else:
            path, peak, worst = 1.0, 1.0, 0.0
            for _, r in sorted(rets):
                path *= 1.0 + r
                peak = max(peak, path)
                worst = max(worst, 1.0 - path / peak)
            k1.update(earning_days=len(rets), drawdown=round(worst, 8),
                      verdict=_verdict(worst, line, True))
        if read_through is not None:
            k1.update(read_through=read_through, earned_not_yet_read=unread)
    rec["K1"] = k1
    # ---- K2, K3: the previous session's close, after a reduced decision
    prev = w["days"][0] if w["days"] and w["days"][0][0] == asof else None
    prev_unread = prev is None and w["status"] == UNMEASURED and not w["days"]
    # The as-of session is a named gap: K2, K3 and the send skip read its close and its send,
    # so all three are UNMEASURED; the other stops are judged on their own windows.
    prev_gap = prev is not None and prev[1] is None
    gap_why = (f"no record for the session {asof} (no plan.json, send.json or STARTED): "
               f"whether its decision was a reduced one is unknown")
    # A reduced decision is one whose targets were sent (`_is_reduced`): the walk classified
    # `prev` already. Not one: N/A, naming a decided reduced plan that was not sent.
    prev_reduced = prev is not None and asof in w["reduced"]
    not_reduced = w["unsent"].get(asof) or f"{asof} was not a reduced session"
    run_line, once_line = th.get("thin_k3_net_run"), th.get("thin_k3_net_once")
    # K3's run length: the spec's `risk.thin_k3_run_sessions` (registry `cef_thin_stop_levels`,
    # required under the rule; the runner owner's review 2026-11-04, item 9), never a constant
    # here. A value the registry would refuse is a caller's bug: raised, not read.
    run_n = th.get("thin_k3_run_sessions")
    if run_n is not None and (isinstance(run_n, bool) or not isinstance(run_n, int)
                              or run_n < 2):
        raise ValueError(f"thin_k3_run_sessions {run_n!r} is not an int of at least 2")
    k2 = {"line": th.get("thin_k2_max_name_frac"), "session": asof}
    k3 = {"line_run": run_line, "line_once": once_line, "run_sessions": run_n, "session": asof}
    if prev_unread:
        for k in (k2, k3):
            k.update(verdict=UNMEASURED, why=f"the record of {asof} is unmeasured: {w['why']}")
    elif prev_gap:
        for k in (k2, k3):
            k.update(verdict=UNMEASURED, why=gap_why)
    elif not prev_reduced:
        for k in (k2, k3):
            k.update(verdict=NOT_APPLICABLE, why=not_reduced)
    else:
        held = {s: q for s, q in positions.items() if q}
        nocl = sorted(s for s in held if not isinstance(closes.get(s), (int, float)))
        # The equity is the read-through date's, always recorded (the runner owner's review
        # 2026-11-04, item 6: the as-of's own row when it exists, else D-1's), and labelled
        # whenever it is not the as-of's: the positions are valued at the as-of closes, so the
        # ratio is then off by one session's return. Never mixed silently.
        for k in (k2, k3):
            k["equity_date"] = upto
            if upto != asof:
                k["equity_note"] = (f"the {asof} closes over the {upto} equity, {n} session(s) "
                                    f"earlier: the as-of's row is not there yet; off by that "
                                    f"session's return")
        why = (eq_why if eq is None else f"no eod_equity row for {upto}" if upto not in eq
               else f"no as-of close for {nocl}" if nocl else None)
        if why is not None:
            for k in (k2, k3):
                k.update(verdict=UNMEASURED, why=why)
        else:
            mv = {s: q * float(closes[s]) for s, q in held.items()}
            e = eq[upto]
            k2_stat = max((abs(v) for v in mv.values()), default=0.0) / e
            net = abs(sum(mv.values())) / e
            k2.update(stat=round(k2_stat, 8), verdict=_verdict(k2_stat, k2["line"], False))
            k3["net"] = round(net, 8)
            unset = [n for n, v in (("thin_k3_net_run", run_line),
                                    ("thin_k3_net_once", once_line),
                                    ("thin_k3_run_sessions", run_n)) if v is None]
            if unset:
                k3.update(verdict=UNMEASURED, why=f"K3's {unset} not set")
            else:
                run, broken = (1, None) if net > run_line else (0, None)
                if run:
                    # Newest first FROM `prev` itself: w["days"][i]'s K3 judges the close of
                    # w["days"][i + 1] (the decide for X reads as-of previous(X); block
                    # comment, WHICH RECORD HOLDS WHICH CLOSE). Only the closes of reduced
                    # decisions count; a full session between them does not break the run.
                    # The oldest day's K3 judges a close outside the walk: skipped. A named
                    # gap among the closes the run reads back makes it UNMEASURED: the gap's
                    # own close might be a reduced one, and a gap's plan would hold the K3 of
                    # the close before it (block comment, READING BACK).
                    reduced_set, gap_set = set(w["reduced"]), set(w["gaps"])
                    for i, (d, day) in enumerate(w["days"]):
                        judged = sessions[i + 1] if i + 1 < len(sessions) else None
                        if judged in gap_set:
                            broken = (f"no record for {judged} (no plan.json, send.json or "
                                      f"STARTED): whether its close is the run's next reduced "
                                      f"close is unknown")
                            break
                        if judged not in reduced_set:
                            continue                        # not a reduced decision's close
                        if day is None:
                            broken = (f"no record for {d}, whose plan would hold the K3 of "
                                      f"{judged}'s reduced close")
                            break
                        k = ((day["plan"].get("thin_stops") or {}).get("K3") or {})
                        if not isinstance(k.get("net"), (int, float)):
                            broken = (f"the K3 of {judged}'s reduced close (in {d}'s plan) is "
                                      f"unmeasured ({k!r})")
                            break
                        if str(k.get("session")) != judged.isoformat():
                            broken = (f"{d}'s K3 names the close of {k.get('session')!r}, not "
                                      f"{judged}; not counting a run on it")
                            break
                        if k["net"] > run_line:
                            run += 1
                            if run >= run_n:
                                break
                        else:
                            break
                    else:
                        # The walk ran out with the run still open. A walk that stopped at a
                        # record it could not read may have cut a longer run short (the oldest
                        # day's K3 judges the close of the session it could not read): not
                        # CLEAR. One that stopped at the key-absent plan or the 63-session gap
                        # did not: no reduced close lies beyond either.
                        if not w["complete"] and run < run_n:
                            broken = (f"the walk back stopped before the run ended, at "
                                      f"{w['why']}")
                k3["run"] = run
                if net > once_line or run >= run_n:
                    k3["verdict"] = TRIPPED
                elif broken is not None:
                    k3.update(verdict=UNMEASURED, why=broken)
                else:
                    k3["verdict"] = CLEAR
    rec["K2"], rec["K3"] = k2, k3
    # ---- the send-time skip after a reduced decision (ruled 2026-11-03: label it)
    sk = {"session": asof}
    if prev_unread:
        sk.update(applies=UNMEASURED, why=f"the record of {asof} is unmeasured: {w['why']}")
    elif prev_gap:
        sk.update(applies=UNMEASURED, why=gap_why)
    elif not prev_reduced:
        # Only a send that went can have lost a short (block comment, send skip): a refused or
        # dry send wrote its skipped list and sent nothing, and is not a reduced decision.
        sk.update(applies=False, why=not_reduced)
    elif prev[1]["plan"].get("execution") != "late_market":
        sk.update(applies=False, why="cls: the decide is the send; there is no send-time skip")
    else:
        # A reduced decision's targets were sent (`_is_reduced`): with no orders no send ran;
        # with orders send.json exited SENT, or FAIL with `final` recording what went
        # (`_send_state`). Either way the send ran past its gates, so its `skipped` list is
        # what it did not send (`_send_planned` skips before the gates and sends the rest).
        send = prev[1].get("send")
        skipped = None if send is None else send.get("skipped")
        if not prev[1]["plan"]["orders"]:
            sk.update(applies=False, why=f"{asof}'s plan had no orders: no send ran, so nothing "
                                         f"was skipped at one")
        elif not isinstance(skipped, list):
            sk.update(applies=True, lost_short=UNMEASURED,
                      why=f"send.json for {asof} has no `skipped` list ({skipped!r})")
        else:
            sk.update(applies=True, skipped_at_send=list(skipped), lost_short=bool(skipped))
    rec["send_skip"] = sk
    return rec


def thin_unmeasured_record(asof, why: str) -> dict:
    """The record when the K-lines could not be computed at all (run.py `_thin_stops`)."""
    return {"report_only": True, "asof": asof, "unmeasured": why}


def thin_stop_lines(rec: dict) -> list[str]:
    """The session log's K0-K3 lines (report only)."""
    head = "  TE4 STOPS (report only)"
    if "unmeasured" in rec:
        return [f"{head}: UNMEASURED: {rec['unmeasured']}"]
    ep = rec["episode"]
    rt = rec.get("read_through")
    out = [f"{head}: episode {ep['status']}"
           + (f" (reduced sessions {ep['reduced_sessions']})" if ep["reduced_sessions"] else "")
           + (f"; {ep['why']}" if ep["status"] == UNMEASURED else "")
           + (f"; K1-K3 {rt['label']}" if rt else "")]
    k0 = rec["K0"]
    st = k0.get("stale") or {}
    through = (f", read through {k0['read_through']}"
               + (f", {st['sessions']} session(s) stale" if "sessions" in st else "")
               if "read_through" in k0 else "")
    out.append(f"    K0 {k0['verdict']}: drawdown status {k0['status']} (as-of {k0['asof']}"
               f"{through})"
               + ("; it stopped this session's reduced build" if k0["acted"] else ""))
    for name in ("K1", "K2", "K3"):
        k = rec[name]
        stat = {"K1": k.get("drawdown"), "K2": k.get("stat"), "K3": k.get("net")}[name]
        lines_ = (f"line {k['line']}" if name != "K3"
                  else f"lines run {k['line_run']} x{k.get('run_sessions')} / once "
                       f"{k['line_once']}")
        out.append(f"    {name} {k['verdict']}: {stat if stat is not None else '-'} against "
                   f"{lines_}" + (f", run {k['run']}" if name == "K3" and "run" in k else "")
                   + (f"; equity of {k['equity_date']}" if k.get("equity_note") else "")
                   + (f"; {k['why']}" if k.get("why") else ""))
    sk = rec["send_skip"]
    if sk.get("applies") is True:
        out.append(f"    SEND SKIP {sk['session']}: lost a short at send: {sk['lost_short']}"
                   + (f" {sk['skipped_at_send']}" if sk.get("skipped_at_send") else "")
                   + (f"; {sk['why']}" if sk.get("why") else ""))
    elif sk.get("applies") == UNMEASURED:
        out.append(f"    SEND SKIP {sk['session']}: UNMEASURED; {sk['why']}")
    return out
