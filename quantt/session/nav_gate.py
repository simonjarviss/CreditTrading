"""The decide-time stale-NAV gate: a NAV dated D that is really an older NAV is checked against CEFConnect.

THE DEFECT (results/cef/LIVE_NAV_QUALITY_2026-10-12.md §5; docs/REFERENCES.md §12n)
-----------------------------------------------------------------------------------
Yahoo serves a NAV row dated D that still carries an older NAV, and corrects it
later. `scripts/cef/fetch_daily.py --require-asof D` checks the DATE of each
deployed name's NAV, not its value, so it passes such a row as "today's pair".
Inverting the z each laptop paper session printed (as-of 2026-09-28 ->
2026-10-07): on 28 of 73 checkable name-days the session decided on NAV(D-1),
and 11 orders that reached the broker were sized on one. Deciding later does
not cure it: plans written 20-23 hours after the close still used stale rows.

THE RULE (team lead, 2026-10-13, redesigned the same day after the replay of
the first version and an independent review of the note)
--------------------------------------------------------------------------------
TRIGGER. A deployed name is checked when its panel NAV for D equals, to the cent,
  (1) its previous panel NAV row (`yf_repeat`), OR
  (2) CEFConnect's NAV for D-1, the previous NYSE trading day, when CEFConnect
      has that row (`cc_prev`). The reviewer's case: PDI captured on 09-28 with
      09-25 = 15.06 against 09-24 = 15.12, because Yahoo's 09-24 row was itself
      an uncorrected archive copy, so (1) did not fire. 15.06 is CEFConnect's
      09-24 NAV; the true 09-25 NAV is 15.10.
RESOLUTION. For a triggered name, CEFConnect's row for D:
  * present and different by more than half a cent -> STALE COPY: its value
    replaces the panel row through the logged fallback fetch_daily already uses
    (`data/cef/nav_fallback_log.csv`, source `cefconnect_stale_copy`).
    CEFConnect is the right source on a stale copy: yfinance's next change
    carries the move it skipped (slope 1.19, s.e. 0.04, n = 414; note §1);
  * present and equal -> GENUINE REPEAT, kept (about a fifth of NAV rows
    genuinely repeat; note §1).
UNVERIFIED (CEFConnect has no row for D, or cannot be read). Never dropped at the
  evening decide: the first replay showed CEFConnect had no row for D at every
  measured evening decide, and dropping would have flattened the whole book on
  2026-10-05 through the sleeve's `min_names` rule. Instead:
  * before the FINAL CHECK (`final_check_at`: the session's calendar close
    minus FINAL_CHECK_BEFORE_CLOSE, on the session date) the decide is
    DEFERRED. run.py records it as a gate-5 `data` refusal, so nothing is
    decided, nothing is marked, and the next slot -- the morning backstop
    06:00-15:15 ET -- re-reads CEFConnect and decides again;
  * at or after the final check a name still unverified is HELD: it keeps its
    current shares (no order in it) and leaves the cross-section
    (`extras["nav_hold"]` in `src/deploy/sleeves/cef_discount.py`). It is
    never targeted to zero, and holds can never trigger the sleeve's
    `min_names` flatten.

"Equal to the cent" is |a - b| <= half a cent: NAVs are quoted in cents and
yfinance stores them as float32, so a stale copy is bit-identical but a
CEFConnect value of the same cent (12.56 against 12.5600004) is not. Half a cent
is the collector's own tolerance (`quantt/collect/collect.py` TOLERANCE_USD).

WHY 90 MINUTES BEFORE THE CLOSE. The morning backstop fires every 30 minutes
until 15:15 ET, and the late-market send opens 8 minutes before the close. A
final check at 14:30 ET (11:30 on a 13:00 close) leaves the 15:00 slot to retry
a final decide that failed for any other reason, and is as late as that allows,
because when CEFConnect publishes D's row is [U]: in the laptop records it had
not by 00:10 ET on D+1 (2026-10-05), had by 11:41 ET (2026-10-01), and Friday's
row was still missing at 09:40 ET on Saturday (2026-10-02). The collector now
logs each row's arrival (`step_cefconnect_arrival`), so this can be re-derived
from measurement rather than from three observations.

WHY A RUNNER SETTING, NOT A FROZEN-SPEC KEY. The frozen spec states the strategy
the research measured, on panels where Yahoo had long since corrected these
rows. This gate restores the NAV the research assumed; it has no backtest
counterpart. It checks the live capture, like gate 5, so it lives beside the
runner's other settings in the book json (`execution.mode`,
`execution.bp_shortfall`), with the same convention: ABSENT is today's
behaviour (`run.stale_nav_for`).

MODES (`MODES`)
  report   every check, CEFConnect read and verdict, and what `on` WOULD do
           (replace, keep, defer, hold), recorded -- and nothing else: no panel
           write, no deferral, no hold. The orders and the plan are those of a
           session without the gate, byte for byte, apart from the added
           `nav_gate` record. An error is recorded as UNMEASURED and never stops
           the session (run.py `_nav_gate`).
  on       the rule above.

H14. Nothing here keys on a number from a document: every check is measured at
run time and recorded (name, D, the panel NAV(D), its previous row, CEFConnect's
D-1 and D or the error, the trigger, the verdict and the action) in the run
record, plan.json and `<state>/nav_gate.csv`.

Imports only the standard library at module level: `quantt.collect.collect`
imports this module at its top, and an idle collector run must stay cheap
(pytest.ini). pandas, requests and fetch_daily are imported where used.
"""
from __future__ import annotations

import contextlib
import csv
import datetime as dt
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Half a cent. See the module docstring for why "equal" means "equal to the cent".
TOLERANCE_USD = 0.005
# The last pre-send check (module docstring, WHY 90 MINUTES BEFORE THE CLOSE).
FINAL_CHECK_BEFORE_CLOSE = dt.timedelta(minutes=90)

REPORT, ON = "report", "on"
MODES = (REPORT, ON)

TRIGGER_YF, TRIGGER_CC = "yf_repeat", "cc_prev"
STALE_COPY, GENUINE_REPEAT, UNVERIFIED = "stale_copy", "genuine_repeat", "unverified"

# The `source` written to data/cef/nav_fallback_log.csv for a replaced stale
# copy; fetch_daily's missing-NAV fallback writes "cefconnect". The collector
# treats every logged row for D as written from CEFConnect (a same-source gap),
# which is what a replaced row is.
FALLBACK_SOURCE = "cefconnect_stale_copy"

CSV_NAME = "nav_gate.csv"
CSV_COLUMNS = ("written_utc", "run", "session_date", "asof", "gate_mode", "final_check",
               "ticker", "trigger", "nav_d", "prev_date", "nav_prev", "cc_prev_date", "cc_prev",
               "cc_d", "cc_status", "verdict", "action")


class CefConnectError(RuntimeError):
    """CEFConnect could not be read (transport, HTTP body, or response shape)."""


class NavGateRecordError(RuntimeError):
    """The gate's own record could not be written. Names the file."""


def _wrap(ticker: str, fn):
    import requests
    try:
        return fn()
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        raise CefConnectError(f"{ticker}: {type(e).__name__}: {e}") from e


def cefconnect_nav(ticker: str, day: dt.date):
    """CEFConnect's NAV dated exactly `day`, or None -- the SAME endpoint and
    parsing fetch_daily's `--nav-fallback cefconnect` uses (reused, not copied,
    so the session, the collector and the fallback can never read different
    fields). Transport and shape errors are raised as CefConnectError, naming
    the fund. Moved here from `quantt/collect/collect.py` on 2026-10-13 so the
    gate and the collector share one reader; collect re-exports it. Imported
    lazily because it pulls in yfinance and pandas."""
    import pandas as pd
    from scripts.cef.fetch_daily import _cefconnect_nav
    return _wrap(ticker, lambda: _cefconnect_nav(ticker, pd.Timestamp(day).normalize()))


def cefconnect_navs(ticker: str, days) -> dict:
    """{day: CEFConnect's NAV dated exactly that day, or None}, from ONE request
    (fetch_daily `_cefconnect_navs`). Errors as `cefconnect_nav`."""
    import pandas as pd
    from scripts.cef.fetch_daily import _cefconnect_navs
    got = _wrap(ticker, lambda: _cefconnect_navs(ticker, [pd.Timestamp(d) for d in days]))
    return {d: got[pd.Timestamp(d).normalize()] for d in days}


def differs(a: float, b: float) -> bool:
    """True when two NAVs are different cents (|a - b| > half a cent)."""
    return abs(float(a) - float(b)) > TOLERANCE_USD


def final_check_at(session_date: dt.date, calendar_close: str) -> dt.datetime:
    """The final pre-send check (ET): the session's calendar close minus
    FINAL_CHECK_BEFORE_CLOSE. The calendar close is read as ET, as gate.py reads
    it (Alpaca does not document its zone)."""
    hh, mm = map(int, calendar_close.split(":"))
    return dt.datetime.combine(session_date, dt.time(hh, mm), tzinfo=ET) - FINAL_CHECK_BEFORE_CLOSE


# ------------------------------------------------------------------ the panel

@dataclass(frozen=True)
class Repeat:
    """A name whose panel NAV for `asof` equals its previous NAV row to the cent."""
    ticker: str
    asof: dt.date
    nav_d: float
    prev_date: dt.date
    nav_prev: float


def panel_rows(nav, asof: dt.date, universe) -> dict:
    """{ticker: (nav_d, prev_date, nav_prev)} for each universe name with a
    finite positive NAV dated `asof` and an earlier one.

    `nav` is the NAV panel (columns date, ticker, nav). NO LOOKAHEAD: rows after
    `asof` are dropped before anything is read, and the previous row's date is
    asserted < `asof`. The previous row is the name's last row before `asof`,
    whatever its date (recorded): a carried-forward value repeats the last value
    Yahoo served, which is that row. A duplicate (date, ticker) for a universe
    name raises: which of two values is the NAV cannot be chosen silently. A name
    with no NAV dated `asof` is absent -- a missing as-of NAV is gate 5's to
    refuse, not this gate's.

    A NAV that is NaN, infinite or not positive is no NAV, and its row is
    skipped, both as NAV(D) and as the previous row. FINITE since 2026-10-28
    (review of fetch_daily's NAV half): the filter was `notna() & > 0`, which
    +inf passes; it is now gate 5's test (`run.last_navs`) and fetch_daily's
    `has_nav`. No panel NAV is infinite, so on the panels this is the old filter
    exactly (quantt/session/tests/test_nav_finite.py)."""
    import numpy as np
    import pandas as pd
    n = nav[nav["ticker"].isin(list(universe))][["date", "ticker", "nav"]].copy()
    n["date"] = pd.to_datetime(n["date"]).dt.normalize()
    n = n[n["date"] <= pd.Timestamp(asof)]
    dup = n[n.duplicated(["date", "ticker"], keep=False)]
    if len(dup):
        raise ValueError(f"NAV panel has duplicate (date, ticker) rows, e.g. "
                         f"{dup.head(3).to_dict('records')}")
    nav = pd.to_numeric(n["nav"])
    n = n[np.isfinite(nav) & (nav > 0)]
    out = {}
    for tk in sorted(universe):
        rows = n[n["ticker"] == tk].sort_values("date")
        if len(rows) < 2 or rows["date"].iloc[-1] != pd.Timestamp(asof):
            continue
        prev_date = rows["date"].iloc[-2].date()
        assert prev_date < asof, f"lookahead: {tk} previous NAV dated {prev_date} >= {asof}"
        out[tk] = (float(rows["nav"].iloc[-1]), prev_date, float(rows["nav"].iloc[-2]))
    return out


def repeats(nav, asof: dt.date, universe) -> list[Repeat]:
    """The names whose NAV dated `asof` equals their previous panel row (trigger
    1 alone). The collector's cross-check uses this: it reads CEFConnect for D
    only."""
    return [Repeat(tk, asof, d, pd_, p) for tk, (d, pd_, p) in
            panel_rows(nav, asof, universe).items() if not differs(d, p)]


# ------------------------------------------------------------------ judging

@dataclass(frozen=True)
class Check:
    """One deployed name: what the panel and CEFConnect said, and what the gate did."""
    ticker: str
    asof: dt.date
    nav_d: float | None           # panel NAV(D); None: no NAV dated D (gate 5's)
    prev_date: dt.date | None
    nav_prev: float | None        # the panel's previous NAV row
    cc_prev_date: dt.date         # the previous NYSE trading day
    cc_prev: float | None         # CEFConnect's NAV for it, None when absent
    cc_d: float | None            # CEFConnect's NAV for D, None when absent
    cc_status: str                # "read" | "error: <what>"
    trigger: str                  # "" | TRIGGER_YF | TRIGGER_CC | both, "+"-joined
    verdict: str                  # "" (not triggered) | STALE_COPY | GENUINE_REPEAT | UNVERIFIED
    action: str                   # see `action_for`

    def reason(self) -> str:
        if not self.trigger:
            return ""
        what = []
        if TRIGGER_YF in self.trigger:
            what.append(f"= panel NAV {self.prev_date} {self.nav_prev:.2f}")
        if TRIGGER_CC in self.trigger:
            what.append(f"= CEFConnect NAV {self.cc_prev_date} {self.cc_prev:.2f}")
        cc = (f"CEFConnect {self.cc_status}" if self.cc_status != "read" else
              f"CEFConnect has no NAV dated {self.asof}" if self.cc_d is None else
              f"CEFConnect {self.asof} {self.cc_d}")
        return f"NAV {self.asof} {self.nav_d:.2f} " + " and ".join(what) + f"; {cc}"

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in (
            "ticker", "asof", "nav_d", "prev_date", "nav_prev", "cc_prev_date", "cc_prev",
            "cc_d", "cc_status", "trigger", "verdict", "action")}


def _finite_positive(v) -> bool:
    return (not isinstance(v, bool) and isinstance(v, (int, float))
            and math.isfinite(float(v)) and float(v) > 0)


def read_cc(reader: Callable, ticker: str, asof: dt.date, prev: dt.date):
    """(cc_prev, cc_d, status). Only CefConnectError is caught, and it is named;
    anything else is a bug and raises. A value that is not a finite positive
    number is unreadable, never used."""
    try:
        got = reader(ticker, [prev, asof])
    except CefConnectError as e:
        return None, None, f"error: {e}"
    vals = (got.get(prev), got.get(asof))
    bad = [v for v in vals if v is not None and not _finite_positive(v)]
    if bad:
        return None, None, (f"error: CEFConnect NAV {bad[0]!r} for {ticker} is not a finite "
                            f"positive number")
    return (None if vals[0] is None else float(vals[0]),
            None if vals[1] is None else float(vals[1]), "read")


def judge(row, cc_prev, cc_d, status) -> tuple[str, str]:
    """(trigger, verdict) for one name. `row` is panel_rows' (nav_d, prev_date,
    nav_prev), or None when the panel has no NAV dated D (not this gate's)."""
    if row is None:
        return "", ""
    nav_d, _, nav_prev = row
    trig = []
    if not differs(nav_d, nav_prev):
        trig.append(TRIGGER_YF)
    if cc_prev is not None and not differs(nav_d, cc_prev):
        trig.append(TRIGGER_CC)
    if not trig:
        return "", ""
    if status != "read" or cc_d is None:
        return "+".join(trig), UNVERIFIED
    return "+".join(trig), (STALE_COPY if differs(nav_d, cc_d) else GENUINE_REPEAT)


def action_for(verdict: str, mode: str, final: bool) -> str:
    """What `on` does with a verdict ("replaced", "kept", "deferred", "held");
    in report mode the same word after "would ", and nothing is done."""
    if not verdict:
        return ""
    act = {STALE_COPY: "replace", GENUINE_REPEAT: "keep",
           UNVERIFIED: "hold" if final else "defer"}[verdict]
    if mode == REPORT:
        return f"would {act}"
    return {"replace": "replaced", "keep": "kept", "defer": "deferred", "hold": "held"}[act]


@dataclass(frozen=True)
class GateResult:
    mode: str
    asof: dt.date
    final: bool                   # at or after the final pre-send check
    checked_utc: dt.datetime
    universe: tuple
    checks: tuple                 # of Check, one per universe name, in ticker order

    @property
    def triggered(self) -> list:
        return [c for c in self.checks if c.trigger]

    @property
    def unverified(self) -> list:
        return [c.ticker for c in self.checks if c.verdict == UNVERIFIED]

    @property
    def replaced(self) -> dict:
        """{ticker: CEFConnect NAV} written into the panel (on only)."""
        if self.mode != ON:
            return {}
        return {c.ticker: c.cc_d for c in self.checks if c.verdict == STALE_COPY}

    @property
    def hold(self) -> dict:
        """{ticker: reason} the sleeve holds at current shares (on only). Passed
        on a deferred decide too, so the refused plan shows what the final check
        would send if CEFConnect never published."""
        if self.mode != ON:
            return {}
        return {c.ticker: c.reason() for c in self.checks if c.verdict == UNVERIFIED}

    @property
    def would_defer(self) -> bool:
        """An unverified name before the final check: `on` defers this decide."""
        return bool(self.unverified) and not self.final

    @property
    def deferred(self) -> bool:
        return self.mode == ON and self.would_defer

    def deferral_text(self) -> str:
        return (f"stale-NAV gate: NAV unverified for {self.unverified} (CEFConnect has no "
                f"row for {self.asof}, or could not be read); deferred to a later slot -- "
                f"the morning backstop re-reads CEFConnect, and from the final check "
                f"({FINAL_CHECK_BEFORE_CLOSE.total_seconds() / 60:.0f} min before the close) "
                f"a name still unverified keeps its shares")

    def to_dict(self) -> dict:
        return {"mode": self.mode, "asof": self.asof, "final_check": self.final,
                "checked_utc": self.checked_utc, "n_universe": len(self.universe),
                "triggered": [c.ticker for c in self.triggered],
                "would_defer": self.would_defer, "deferred": self.deferred,
                "replaced": sorted(self.replaced), "held": sorted(self.hold) if self.final else [],
                "checks": [c.to_dict() for c in self.checks]}

    def lines(self) -> list[str]:
        """The session log's lines for this gate."""
        head = (f"  NAV GATE ({self.mode}) as-of {self.asof}{', final check' if self.final else ''}: "
                f"{len(self.triggered)} of {len(self.universe)} deployed names triggered")
        if self.would_defer:
            head += (f"; {'DEFERRED' if self.deferred else 'would defer'}: "
                     f"{len(self.unverified)} unverified")
        bad = [c for c in self.checks if c.cc_status != "read"]
        out = [head] + [f"    {c.ticker}: {c.reason()} -> {c.verdict}, {c.action}"
                        for c in self.triggered]
        if bad:
            out.append(f"    CEFConnect unreadable for {[c.ticker for c in bad]}")
        return out


# ------------------------------------------------------------------ acting

@dataclass
class PanelGate:
    """The gate against the real NAV panel. Paths and the CEFConnect reader are
    injected so tests touch neither data/ nor the network.
    `reader(ticker, [D-1, D]) -> {day: NAV or None}`, raising CefConnectError.

    `log_path` / `lock_path` None means fetch_daily's own FALLBACK_LOG /
    LOCK_PATH, RESOLVED ONLY WHEN THE GATE LOCKS OR WRITES (release-check
    2026-10-13). Building a PanelGate therefore imports nothing from scripts/:
    the session builds one in `default_deps` on every run, the 15:52 send and
    verify included, and those must never load fetch_daily -- it imports
    yfinance and silences warnings process-wide, and a failed import there
    between decide and send would stop a decided plan going.
    `quantt/collect/collect.py` keeps fetch_daily inside a function the same way."""
    nav_path: Path
    log_path: Path | None = None
    lock_path: Path | None = None
    reader: Callable = cefconnect_navs
    lock_wait_s: float | None = None     # None: fetch_daily.LOCK_WAIT_S

    def _lock(self):
        from scripts.cef import fetch_daily as fd
        wait = fd.LOCK_WAIT_S if self.lock_wait_s is None else self.lock_wait_s
        lock = fd.LOCK_PATH if self.lock_path is None else self.lock_path
        return fd.panel_lock(lock, wait, fd.LOCK_POLL_S)

    def run(self, asof: dt.date, universe, mode: str, now: dt.datetime,
            final: bool, record: Callable | None = None) -> GateResult:
        """Measure every deployed name; in `on` mode replace stale copies.

        `on` holds fetch_daily's panel lock from the read to the write, so a fetch
        (the collector's, or another session's) cannot interleave: it waits, as
        for any refresh. Report mode only reads (the panel is written atomically,
        so a read sees a whole file). CEFConnect is read for every name, one
        request each, because trigger (2) needs its D-1 row.

        RECORD FIRST (execution desk, 2026-10-14). In `on` mode `record(result)`
        -- the session's `nav_gate.csv` append -- is REQUIRED and runs before the
        panel is written. If it raises, the panel is never written and the error
        propagates: every action the gate takes is recorded before it is taken.
        Until 2026-10-14 the panel was written first and the record after, so a
        failed record left a replaced NAV that nothing recorded. Report mode
        writes nothing, so its caller records afterwards."""
        import pandas as pd
        from ops.schedule.nyse_calendar import previous_trading_day
        if mode not in MODES:
            raise ValueError(f"stale-NAV gate mode {mode!r} is not one of {MODES}")
        if mode == ON and record is None:
            raise ValueError("stale-NAV gate `on` needs a record to write before it acts")
        universe = tuple(sorted(universe))
        prev = previous_trading_day(asof)
        with (self._lock() if mode == ON else contextlib.nullcontext()):
            N = pd.read_parquet(self.nav_path)
            rows = panel_rows(N, asof, universe)
            checks = []
            for tk in universe:
                cc_prev, cc_d, status = read_cc(self.reader, tk, asof, prev)
                r = rows.get(tk)
                trig, verdict = judge(r, cc_prev, cc_d, status)
                checks.append(Check(tk, asof, None if r is None else r[0],
                                    None if r is None else r[1], None if r is None else r[2],
                                    prev, cc_prev, cc_d, status, trig, verdict,
                                    action_for(verdict, mode, final)))
            res = GateResult(mode, asof, final, now, universe, tuple(checks))
            if mode == ON:
                record(res)                    # before any write: RECORD FIRST
            if res.replaced:
                self._write(N, asof, res.replaced)
        return res

    def _write(self, N, asof: dt.date, replaced: dict) -> None:
        """fetch_daily's fallback convention: merge, atomic write, append the log."""
        import pandas as pd
        import ops.common as common          # at call time: the test harness's write guard
        from scripts.cef import fetch_daily as fd
        F = pd.DataFrame([{"date": pd.Timestamp(asof), "nav": v, "ticker": t}
                          for t, v in sorted(replaced.items())])
        common.atomic_write(fd.merge_nav_fills(N, F), self.nav_path)
        fd.log_nav_fills(F, FALLBACK_SOURCE,
                         fd.FALLBACK_LOG if self.log_path is None else self.log_path)

    def still_holds(self, res: GateResult) -> list[str]:
        """What changed in the panel since `res`, or [] -- read AFTER the sleeve.

        WHY. The lock is released before the sleeve reads the panel. A fetch
        that ran in between (the collector's, every 30 minutes) would write
        yfinance's rows back, a stale copy included, and the sleeve would decide
        on it with nothing saying so. Only the gate writes CEFConnect's value
        into a stale row, so if every replaced row still holds it and no name
        triggers now that did not trigger then (judged on the CEFConnect values
        already read: no second request), the panel the sleeve read in between
        was the one the gate certified."""
        import pandas as pd
        if res.mode != ON:
            return []
        rows = panel_rows(pd.read_parquet(self.nav_path), res.asof, res.universe)
        bad = [f"{t}: replaced with {v} but the panel now holds "
               f"{rows[t][0] if t in rows else None}"
               for t, v in res.replaced.items() if t not in rows or differs(rows[t][0], v)]
        for c in res.checks:
            if c.trigger:
                continue
            trig, _ = judge(rows.get(c.ticker), c.cc_prev, c.cc_d, c.cc_status)
            if trig:
                bad.append(f"{c.ticker}: NAV {rows[c.ticker][0]} now triggers ({trig}); "
                           f"the gate did not judge it")
        return bad


# ------------------------------------------------------------------ recording

def _cell(v):
    if v is None:
        return ""
    return v.isoformat() if isinstance(v, dt.date) else v


def move_aside(path: Path, when: dt.datetime) -> Path:
    """Move `path` aside, whole, to `<name>.<UTC stamp>.unreadable` (with `-n`
    if that exists) and return the new path. For a record file whose header is
    not the one its writer expects -- empty after a kill before the first flush,
    or from an older column list: rows under another header would be misread
    for ever after, and refusing to write would stop the record for good. Used
    for `nav_gate.csv` (`append_csv`) and the collector's
    `cefconnect_arrival.csv` (`quantt/collect/collect.py` `_append_arrivals`)."""
    stamp = when.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    aside, n = path.with_name(f"{path.name}.{stamp}.unreadable"), 1
    while aside.exists():
        aside = path.with_name(f"{path.name}.{stamp}-{n}.unreadable")
        n += 1
    os.replace(path, aside)
    return aside


def append_csv(path: Path, res: GateResult, *, run: str, session_date: dt.date,
               written_utc: dt.datetime) -> None:
    """One row per triggered name to `<state>/nav_gate.csv`; a run with none
    writes one row with an empty ticker and verdict `no_trigger`, so the file
    alone counts how many decides ran the gate (the denominator of how often it
    binds). Appended and fsynced.

    A FILE WHOSE HEADER IS NOT CSV_COLUMNS (release-check 2026-10-13). An empty
    file -- a reboot, an OOM kill or a systemd stop before the first write was
    flushed -- or one from an older CSV_COLUMNS is never written into: rows under
    another header would be misread for ever after. It is moved aside, whole, to
    `nav_gate.csv.<UTC stamp>.unreadable`, and NavGateRecordError is raised
    naming both files, so the caller records this run as UNMEASURED (report
    mode) or refuses it (`on`). The next decide starts a new file, so one bad
    file costs one run's CSV rows, never every run until someone deletes it."""
    if path.exists():
        with open(path, newline="") as fh:
            head = next(csv.reader(fh), None)
        if tuple(head or ()) != CSV_COLUMNS:
            aside = move_aside(path, written_utc)
            raise NavGateRecordError(
                f"{path} had columns {head}, not {list(CSV_COLUMNS)}: moved aside to "
                f"{aside.name}; the next decide starts a new file")
    common = {"written_utc": written_utc.isoformat(), "run": run,
              "session_date": session_date.isoformat(), "asof": res.asof.isoformat(),
              "gate_mode": res.mode, "final_check": res.final}
    rows = [{**common, **{k: _cell(v) for k, v in c.to_dict().items() if k != "asof"}}
            for c in res.triggered]
    if not rows:
        rows = [{**common, **{k: "" for k in CSV_COLUMNS if k not in common},
                 "verdict": "no_trigger", "action": "none"}]
    new = not path.exists()
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        if new:
            w.writeheader()
        w.writerows(rows)
        fh.flush()
        os.fsync(fh.fileno())
