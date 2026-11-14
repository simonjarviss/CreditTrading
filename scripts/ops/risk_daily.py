"""The nightly risk report for one account: where it stands against every limit and stop.

    python3 -m scripts.ops.risk_daily --book cef [--state-dir DIR] [--asof YYYY-MM-DD]

WHY THIS EXISTS (team lead, 2026-11-08; design results/ops/AGENT_DESK_DESIGN_2026-11-03.md s2)
-----------------------------------------------------------------------------------------------
The stops exist (HALVE/KILL, trial 53's R1-R3, the core's 60-session rule, C4's
H11, trial 54's L1), but nothing read them on a schedule, and the evening check
that did lived in an open Claude session and ran three days late
(E-2026-11-08-03). So this runs on a VM timer after the decide, reads the files
the runner already wrote, and writes `<state>/reports/risk/<asof>.{md,json}`.

ONE ACCOUNT PER RUN. The design said "both accounts, one report"; the team lead's
2026-11-08 brief puts the output under `quantt_state/<book>/`, so each account gets
its own timer and report (`--book cef`, `--book c4`), and the diversification
block reads the other account's EOD series, read-only.

REPORT ONLY, AND A WRAPPER. Every number comes from an existing reader:
`quantt.session.drawdown` (imported, standard library only), `stops.py`'s printed
output (read from a file, never run here: its import closure reaches the broker
client), the runner's `eod_equity.csv`, `equity.csv`, `scores.csv`, `tca.csv`,
`plan.json`, `account.json`. It holds no broker client and imports nothing from
`quantt.broker` or `quantt.session.run` (scripts/ops/tests/test_report_no_order_path.py).
It never sends, cancels, arms, disarms, halts, or changes a spec or a book json.

A MISSING INPUT IS UNMEASURED AND NAMED, never inferred (CLAUDE.md). Blocks whose
inputs do not exist on the VM say so, with the exact command that would measure
them on a machine that has them: R1-R3 need `stops.py`'s fit series, the
attribution and factor readout read `<state>/reports/pnl/<asof>.json`, written by
the 20:30 job (`scripts/ops/pnl_report.py`, the team lead's report of 2026-11-09;
absent, they stay UNMEASURED and named). Those are stated gaps, not silent zeros.

THE DRAWDOWN READ. At 22:15 the as-of day's EOD row is not written yet, so
`drawdown.check` says UNMEASURED. The team lead ruled (2026-11-08) that this report
reads the freshest row: the as-of's own row if it exists, else D-1, labelled stale.
PR #55 adds that reader (`read_through`) to `drawdown.py`; it is not merged, so this
script calls `check` as it stands, uses the stale figure it already records, says
so on the line, and carries `FOLLOWUP_DRAWDOWN` (switch to `read_through` when #55
lands). A line breached on the newest row available is an ACT either way: a stop
that fires on D-1's close has fired.

SEVERITY (the design's table)
  INFO   inside every limit.
  WATCH  within a declared distance of a limit, or a data-QA flag on a held name.
  ACT    a pre-registered stop has fired. The team lead acts, by the route the
         trial names; this script writes the line and the revert, and nothing else.
Per-name concentration is reported and never raises severity (team lead,
2026-11-08: "measure it, change nothing").

PUSH: only on ACT (`scripts/ops/report_notify.py`). If no channel is configured the
report records `ACT: notification NOT delivered: <reason>` and the run exits
`EXIT_ACT_UNDELIVERED`, never silently.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from quantt.session import drawdown as dd          # noqa: E402  (standard library only)
from scripts.ops.data_qa import (BOOKS, ET, expected_day, latest_plan, read_spec,  # noqa: E402
                                 write_atomic)
from scripts.ops.report_notify import (EXIT_ACT_UNDELIVERED, notify_act,            # noqa: E402
                                       undelivered_line)

INFO, WATCH, ACT, UNMEASURED = "INFO", "WATCH", "ACT", "UNMEASURED"
RANK = {INFO: 0, UNMEASURED: 1, WATCH: 2, ACT: 3}

# Declared distances for WATCH (design s2.3). Labels only: nothing keys on them.
WATCH_DRAWDOWN_FRACTION = 0.75    # of the HALVE line
WATCH_GROSS_FRACTION = 0.95       # of the spec's max_gross_stress
WATCH_MARGIN_USED = 0.90          # maintenance margin / equity
MIN_CORR_DAYS = 20                # below this a correlation is not worth printing

FOLLOWUP_DRAWDOWN = ("FOLLOW-UP: when PR #55 merges, read the drawdown through "
                     "`drawdown.read_through` (the team lead's freshest-row rule, 2026-11-08) "
                     "instead of `check`'s stale figure")
STOPS_SCRIPT = "results/cef/prereg_voltarget/stops.py"
OTHER_BOOK = {"cef": "c4", "c4": "cef"}
GROUP_SOURCES = {"cef": "data/cef/cef_universe.csv", "c4": "results/cef/c4/c4_universe_frozen_2026-10-14.csv"}
GROUP_COLUMN = {"cef": "grp", "c4": "family"}


def block(status: str, lines: list[str], **data) -> dict:
    return {"status": status, "lines": lines, "data": data}


def _unmeasured(why: str, **data) -> dict:
    return block(UNMEASURED, [f"UNMEASURED: {why}"], **data)


# ------------------------------------------------------------------- P&L

def read_csv_rows(path: Path, asof: dt.date) -> list[dict]:
    """The rows of `path` dated on or before `asof` (no lookahead), oldest first.
    Raises FileNotFoundError naming the file if absent."""
    if not path.is_file():
        raise FileNotFoundError(f"no {path.name} at {path}")
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    return sorted((r for r in rows if r["date"] <= asof.isoformat()), key=lambda r: r["date"])


def pnl_block(state: Path, asof: dt.date) -> dict:
    """The day and to-date P&L: the official EOD series (the P&L of record) and
    the 17:30 snapshot, labelled and never blended, plus the auction-marked
    score. Each is its own line so a missing file costs only its line."""
    lines, data, missing = [], {}, []
    for label, name in (("official EOD (P&L of record)", dd.OFFICIAL_FILE), ("17:30 snapshot", dd.SNAPSHOT_FILE)):
        try:
            series = dd.read_series(state / name, asof)
        except dd.Unmeasured as e:
            missing.append(f"{label}: {e}")
            continue
        day = series[-1][1] - series[-2][1] if len(series) > 1 else None
        total = series[-1][1] - series[0][1]
        lines.append(f"{label}: equity ${series[-1][1]:,.2f} on {series[-1][0]}"
                     + (f", day {day:+,.2f}" if day is not None else ", day n/a (first row)")
                     + f", to date {total:+,.2f} since {series[0][0]}")
        data[name] = {"last_date": str(series[-1][0]), "equity": series[-1][1], "day": day, "to_date": total}
    try:
        rows = read_csv_rows(state / "scores.csv", asof)
        today = [r for r in rows if r["date"] == asof.isoformat()]
        if today:
            r = today[-1]
            lines.append(f"auction-marked {r['auction_pnl_usd']} (verdict {r['verdict']}, "
                         f"{r['n_filled']}/{r['n_orders']} filled)")
            data["scores"] = {k: r[k] for k in ("verdict", "n_orders", "n_filled", "auction_pnl_usd")}
        else:
            missing.append(f"no scores.csv row for {asof}")
    except FileNotFoundError as e:
        missing.append(str(e))
    if missing:
        lines.extend(f"UNMEASURED: {m}" for m in missing)
    return block(UNMEASURED if not lines or len(missing) >= 3 else INFO, lines, **data)


# ------------------------------------------------------------------- drawdown

def drawdown_block(state: Path, spec: dict, asof: dt.date) -> dict:
    """Wraps `quantt.session.drawdown.check`. ACT when the newest row it has read
    is at or past a line (module docstring, THE DRAWDOWN READ). The figures are
    `check`'s own; a test proves they match."""
    rec = dd.check(state, spec, asof, dd.REPORT)
    lines = list(dd.lines(rec))
    status = rec["status"]
    reading = rec.get("reading")
    data = {"check_status": status, "reading": _jsonable(reading), "levels": rec.get("levels"), "why": rec.get("why")}
    level_status = (reading or {}).get("status", status)
    stale = status == dd.UNMEASURED and reading is not None and reading["last_date"] != asof
    if level_status in (dd.HALVE, dd.KILL):
        tag = f"{level_status} line reached" + (f" on the newest row {reading['last_date']} (stale)" if stale else "")
        lines.insert(0, f"ACT: {tag}: the spec's {level_status} stop (report mode). "
                        f"The team lead reads the `on` semantics in quantt/session/drawdown.py and acts")
        st = ACT
    elif status == dd.UNMEASURED and reading is None:
        st = UNMEASURED
    else:
        lv = rec.get("levels")
        ddv = None if reading is None else reading["drawdown"]
        st = WATCH if lv and ddv is not None and ddv >= WATCH_DRAWDOWN_FRACTION * lv["halve"] else INFO
    if stale:
        lines.append(f"(stale: EOD row for {asof} not written yet; figures are {reading['last_date']}'s)")
        lines.append(FOLLOWUP_DRAWDOWN)
    return block(st, lines, **data)


def _jsonable(d):
    return json.loads(json.dumps(d, default=str)) if d is not None else None


# ------------------------------------------------------------------- stops

def stops_block(book: str, spec: dict, stops_output: Path | None) -> dict:
    """R1-R3 as `stops.py` printed them, verbatim, or UNMEASURED naming what would
    measure them. `stops.py` needs the fit series under SCRATCH, which only the
    research machine has, and its import closure reaches the broker client, so a
    report job never runs it. The evening routine can hand this script its output
    file with `--stops-output` (it is labelled with the file's own date: re-measured
    then, not tonight; H14). No threshold is keyed on a number written in a document."""
    m = (spec.get("frozen") or {}).get("sizing_multiplier")
    other = json.loads((REPO / BOOKS[OTHER_BOOK[book]].spec_path).read_text())
    m_other = (other.get("frozen") or {}).get("sizing_multiplier")
    m_core, m_c4 = (m, m_other) if book == "cef" else (m_other, m)
    cmd = (f"python3 {STOPS_SCRIPT} --scratch SCRATCH --m-core {m_core} --m-c4 {m_c4} "
           f"--only {'core' if book == 'cef' else 'c4'}")
    if stops_output is None or not Path(stops_output).is_file():
        return _unmeasured(f"R1-R3 need the fit series under a SCRATCH directory that is not on this machine, "
                           f"and {STOPS_SCRIPT}, which a report job never runs; on the research machine run "
                           f"`{cmd}` and pass its output with `--stops-output`")
    p = Path(stops_output)
    when = dt.datetime.fromtimestamp(p.stat().st_mtime, tz=dt.timezone.utc).date().isoformat()
    text = p.read_text()
    return block(INFO, [f"stops.py output file {p.name}, written {when} (re-measured then, not tonight):",
                        *[ln for ln in text.splitlines() if ln.strip()]], stdout=text, output_file=str(p))


# ------------------------------------------------------------------- kill rules

def traded_sessions(state: Path, asof: dt.date) -> int:
    rows = read_csv_rows(state / "scores.csv", asof)
    return sum(1 for r in rows if str(r.get("traded", "")).strip().lower() == "true")


def live_sharpe(state: Path, asof: dt.date) -> tuple[float | None, int]:
    """Annualised Sharpe of the official EOD equity's day changes since the first
    traded session, and the number of changes. The core's kill rule (a) is written
    on net Sharpe; paper's official EOD charges fees but no borrow, so this is
    the nearest measured line, labelled so on the block."""
    rows = read_csv_rows(state / "scores.csv", asof)
    first = next((r["date"] for r in rows if str(r.get("traded", "")).strip().lower() == "true"), None)
    if first is None:
        return None, 0
    series = dd.read_series(state / dd.OFFICIAL_FILE, asof)
    eq = [e for d, e in series if d.isoformat() >= first]
    changes = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq))]
    if len(changes) < 2:
        return None, len(changes)
    m = sum(changes) / len(changes)
    sd = math.sqrt(sum((c - m) ** 2 for c in changes) / (len(changes) - 1))
    return (None if sd == 0 else m / sd * math.sqrt(252)), len(changes)


def kill_rules_block(book: str, state: Path, spec: dict, asof: dt.date) -> dict:
    """The kill rules this script can read from the runner's own files."""
    try:
        n = traded_sessions(state, asof)
    except FileNotFoundError as e:
        return _unmeasured(str(e))
    lines = [f"{n} armed (traded) sessions to {asof}"]
    data: dict = {"armed_sessions": n}
    status = INFO
    if book == "cef":
        due = 60
        if n >= due:
            s, k = live_sharpe(state, asof)
            data["sharpe"] = s
            if s is None:
                lines.append(f"core rule (a): UNMEASURED: {k} EOD day changes")
                status = max(status, UNMEASURED, key=RANK.get)
            elif s < 0:
                lines.append(f"ACT: core kill rule (a) fired: live Sharpe {s:+.2f} < 0 at {n} sessions "
                             f"(the P&L of record, net of what paper charges, no borrow). "
                             f"Route: the spec's kill_rule; the team lead acts")
                status = ACT
            else:
                lines.append(f"core rule (a): live Sharpe {s:+.2f} at {n} sessions: not fired")
        else:
            lines.append(f"core 60-session rule: not due ({n}/{due})")
        lines.append("core rules (b) slippage vs modelled and (c) discount spread: UNMEASURED by this "
                     "script: (b) needs the modelled-slippage series, (c) the top-minus-bottom spread "
                     "computed as the rule defines it")
    else:
        for name, why in (("C4 H11 (120-session reversal)", "the fit reference series h11_reference, which "
                           "scripts/cef/c4_paper_benchmark.py writes, is not on this machine"),
                          ("trial 54 L1", "the level-only modelled P&L is produced by the "
                           "prereg_c4_level pipeline, not on this machine")):
            lines.append(f"{name}: {'DUE' if n >= 120 else f'not due ({n}/120)'}; "
                         f"UNMEASURED by this script: {why}")
            if n >= 120:
                status = max(status, WATCH, key=RANK.get)
    return block(status, lines, **data)


# ------------------------------------------------------------------- exposure and concentration

def latest_account(state: Path, asof: dt.date) -> tuple[dict | None, str | None]:
    latest = None
    for d in sorted((state / "data").glob("20*")) if (state / "data").is_dir() else ():
        if d.name <= asof.isoformat() and (d / "account.json").is_file():
            latest = d / "account.json"
    if latest is None:
        return None, None
    return json.loads(latest.read_text()), str(latest)


def group_map(book: str) -> tuple[dict, str | None]:
    path = REPO / GROUP_SOURCES[book]
    if not path.is_file():
        return {}, f"no group source at {path}"
    col = GROUP_COLUMN[book]
    with open(path, newline="") as fh:
        return {r["ticker"]: r.get(col) or "unknown" for r in csv.DictReader(fh)}, None


def concentration(positions: list[dict], equity: float, groups: dict | None = None) -> dict:
    """Per-name and group share of NAV from positions (team lead ruling,
    2026-11-08: measure it, change nothing). `share` = |market value| / equity;
    `signed` keeps the side, because a 20% short is not a 20% long."""
    rows = sorted(({"symbol": p["symbol"], "share": abs(float(p["market_value"])) / equity,
                    "signed": float(p["market_value"]) / equity, "side": p.get("side")}
                   for p in positions), key=lambda r: -r["share"])
    out = {"largest": rows[0] if rows else None, "top3_share": sum(r["share"] for r in rows[:3]),
           "per_name": rows}
    if groups is not None:
        by: dict = {}
        for r in rows:
            g = groups.get(r["symbol"], "unknown")
            by[g] = by.get(g, 0.0) + r["share"]
        out["group_share"] = dict(sorted(by.items(), key=lambda kv: -kv[1]))
    return out


def exposure_block(book: str, state: Path, spec: dict, asof: dt.date) -> dict:
    """Gross, net and margin against the spec's cap, and concentration, from
    `<state>/data/<D>/account.json`, the collector's own record of the close."""
    acct, path = latest_account(state, asof)
    if acct is None:
        return _unmeasured(f"no account.json under {state}/data on or before {asof}")
    equity = float(acct["account"]["equity"])
    raw = (acct.get("positions") or {}).get("raw")
    if raw is None or equity <= 0:
        return _unmeasured(f"{path} has no positions.raw or a non-positive equity")
    groups, grp_err = group_map(book)
    con = concentration(raw, equity, groups if not grp_err else None)
    gross = sum(abs(float(p["market_value"])) for p in raw) / equity
    net = sum(float(p["market_value"]) for p in raw) / equity
    maint = float(acct["account"].get("maintenance_margin", 0)) / equity
    cap = float(spec["frozen"]["max_gross_stress"])
    status = WATCH if gross >= WATCH_GROSS_FRACTION * cap or maint >= WATCH_MARGIN_USED else INFO
    acct_date = Path(path).parent.name
    stale = "" if acct_date == asof.isoformat() else f" (stale: the newest account.json is {acct_date}, not {asof})"
    lines = [f"as of {acct_date}{stale}: gross {gross:.3f}x (cap {cap:.2f}x), net {net:+.3f}x, "
             f"maintenance {maint:.1%} of equity ${equity:,.2f}"]
    if con["largest"]:
        lines.append(f"largest name {con['largest']['symbol']} {con['largest']['share']:.1%} of NAV "
                     f"({con['largest']['side']}); top-3 {con['top3_share']:.1%}")
    if con.get("group_share"):
        lines.append("group share: " + ", ".join(f"{k} {v:.1%}" for k, v in con["group_share"].items()))
    if grp_err:
        lines.append(f"group share UNMEASURED: {grp_err}")
    lines.append("Concentration is measured and reported only (team lead, 2026-11-08): nothing acts on it.")
    return block(status, lines, gross=gross, net=net, maintenance_to_equity=maint, cap=cap, concentration=con)


# ------------------------------------------------------------------- the other blocks

def _pnl_report(state: Path, asof: dt.date) -> tuple[dict | None, Path]:
    """The P&L job's JSON for the as-of (`scripts/ops/pnl_report.py`, 20:30 ET), or None."""
    path = state / "reports" / "pnl" / f"{asof.isoformat()}.json"
    if not path.is_file():
        return None, path
    return json.loads(path.read_text()), path


def attribution_block(book: str, state: Path, asof: dt.date) -> dict:
    """The discount/NAV attribution from the P&L job's report, verbatim, or UNMEASURED naming
    the file. A rebuild that does not reconcile to the official EOD change is a WATCH, not an
    ACT: it names a data or execution problem, and the report it comes from names the session;
    a review-line breach has no line here at all. Never an ACT (no ACT line can come from the job)."""
    rep, path = _pnl_report(state, asof)
    if rep is None:
        return _unmeasured(f"no P&L report at {path} (the 20:30 job has not written one for {asof}, or "
                           f"its key service failed; `systemctl status quantt-{book}-pnl`)")
    att = rep.get("attribution") or {}
    lines = list(att.get("lines") or [f"attribution UNMEASURED: {att.get('why')}"])
    status = UNMEASURED if att.get("status") != "OK" else (WATCH if att.get("reconciled") is False else INFO)
    return block(status, lines, report=str(path), reconciled=att.get("reconciled"), first_trade=att.get("first_trade"))


def factor_block(book: str, state: Path, asof: dt.date) -> dict:
    """The factor exposure from the P&L job's report, verbatim, or UNMEASURED naming the file.
    A review-line breach is in these lines and changes nothing: report only (team lead,
    2026-11-09), so a breach never raises the status, and no line is an ACT line.

    A PARTIAL block (team lead, 2026-11-10: a held name without a same-day price is left out
    and named, not the whole block UNMEASURED) is a WATCH, with a first line naming the names
    left out and their share of the book's gross, as an unreconciled attribution is a WATCH:
    it is a data gap on a held name, which the design's severity table (s2.3) already makes a
    WATCH, and a reading on part of the book should not pass as INFO. A share the job's JSON
    does not carry is said to be UNMEASURED, never filled in. Status: INFO, WATCH or
    UNMEASURED, never ACT.

    THE SEVERITY FOLLOWS THE AS-OF READING (independent review of PR #82, 2026-11-11). WATCH
    only when a name held at the as-of close was left out. Before that review a PARTIAL block
    whose `missing` was empty (every name held at the close read, one left out only on an
    earlier date) was a WATCH too, and since the job re-reads from the first trade, a fund
    once held that yfinance no longer serves (merged, renamed) would have kept every later
    night a WATCH. The job now writes such a block as OK with the earlier dates in a history
    note; a PARTIAL block with an empty `missing` (a job from before the review) is INFO, and
    says why. A PARTIAL block with no `missing` at all cannot say what was left out at the
    close, so it stays a WATCH naming that, never read as complete.

    A FLAT block (the same review: the book holds nothing at the as-of close) carries no factor
    risk, so there is nothing to review and nothing missing; the job's lines say it is flat and
    that no earlier close's reading stands in. It is INFO only when the account agrees
    (`_flat_cross_check`, team lead 2026-11-11): the job reads FLAT from its fill rebuild alone,
    and a fill the account never made can make that rebuild flat while the account holds
    positions."""
    rep, path = _pnl_report(state, asof)
    if rep is None:
        return _unmeasured(f"no P&L report at {path} (the 20:30 job has not written one for {asof})")
    fac = rep.get("factor") or {}
    lines = list(fac.get("lines") or [f"factor readout UNMEASURED: {fac.get('why')}"])
    st = fac.get("status")
    if st == "FLAT":
        cst, line, check = _flat_cross_check(state, fac)
        return block(cst, [line] + lines, report=str(path), headline=fac.get("headline"), flat_cross_check=check)
    if st == "PARTIAL":
        miss = fac.get("missing")
        if isinstance(miss, list) and not miss:  # nothing left out at the as-of close: history only
            lines.insert(0, "Factor exposure: every held name read at the last close; a name was left out only on "
                            "an earlier date (history, no severity: the reading at the close is complete)")
            return block(INFO, lines, report=str(path), headline=fac.get("headline"), missing=[],
                         missing_gross_share=fac.get("missing_gross_share"))
        share = fac.get("missing_gross_share")
        names = ("names left out UNMEASURED (not in the job's JSON)" if miss is None
                 else ", ".join(str(m.get("symbol")) for m in miss) + " left out at the last close")
        lines.insert(0, f"Factor exposure PARTIAL: {names}, "
                     + (f"{share:.1%} of the book's gross" if isinstance(share, (int, float)) and not isinstance(share, bool)
                        else "share of the book's gross UNMEASURED (not in the job's JSON)")
                     + "; the readings below are on the remaining names (WATCH: a data gap on a held name; "
                       "a review-line breach still sends nothing)")
        return block(WATCH, lines, report=str(path), headline=fac.get("headline"),
                     missing=None if miss is None else [m.get("symbol") for m in miss], missing_gross_share=share)
    status = INFO if st == "OK" else UNMEASURED
    return block(status, lines, report=str(path), headline=fac.get("headline"))


def _flat_cross_check(state: Path, fac: dict) -> tuple[str, str, dict]:
    """A FLAT factor block against the collector's account record for the same close: (status,
    first line, data). Team lead, 2026-11-11, on the second review of PR #82.

    WHY. The P&L job reads FLAT from its fill rebuild alone. In the review a closing fill the
    account never made (a phantom sale of the whole book in the activities) made the block
    FLAT, the report OK and this block INFO while the account held positions; and when that
    fill's P&L cancelled its modelled fees the rebuild even reconciled, so the job's own
    refusal of an unreconciled FLAT (`pnl_report.build_factor`) cannot see it. A second source
    for the same fact can: Alpaca's positions as the collector recorded them.

    WHICH FILE, FOR WHICH SESSION, WRITTEN WHEN. `<state>/data/<D>/account.json`, where D is
    the FLAT block's own `asof`, the attribution's session (`pnl_report.build_factor`'s
    `res.asof`), read for that session only, never the newest on or before it as
    `exposure_block` does. The collector writes it in its `account_snapshot` step
    (quantt/collect/collect.py): D is a data day only once its close + CLOSE_SETTLE (45
    minutes) has passed by Alpaca's clock, the step refuses unless the market is shut and the
    next open is the first trading day after D, the record carries `date` D and `read_at_utc`,
    and a completed step is never redone. So it is Alpaca's positions after D's close and
    before the next open, the close the FLAT describes, written by the first :10/:40 collector
    slot after that, hours before this job's 22:15/22:20 run; comparing the two is the same
    close from two sources. `positions.qty` is {symbol: signed whole shares}; the client
    refuses a zero quantity, so any entry is a position.

    THE OUTCOMES. The record holds no position: INFO, the account agrees. It holds any: WATCH,
    naming the count, the long and short counts and the symbols (this report lives in the state
    directory, never in git; no quantity is printed), because the book's factor risk at that
    close was not read. The record is missing, unreadable, for another session, or the block
    names no close: UNMEASURED, naming which, never INFO by default: an unchecked FLAT is not
    a known one. Never an ACT; a review-line breach still sends nothing."""
    d = fac.get("asof")
    try:
        named = dt.date.fromisoformat(d).isoformat() == d   # the directory name is the ISO date
    except (TypeError, ValueError):
        named = False
    if not named:
        return (UNMEASURED, f"Factor exposure FLAT not cross-checked (UNMEASURED): the job's FLAT block names no "
                            f"as-of close ({d!r}), so which session's account record to read is unknown",
                {"status": UNMEASURED, "session": d})
    path = state / "data" / d / "account.json"
    check: dict = {"session": d, "account_record": str(path)}

    def unmeasured(why: str):
        check["status"] = UNMEASURED
        check["why"] = why
        return (UNMEASURED, f"Factor exposure FLAT at the close of {d} not cross-checked (UNMEASURED): {why}; "
                            f"whether the account holds anything at that close is unread here", check)
    if not path.is_file():
        return unmeasured(f"no account record at {path} (the collector's account_snapshot step writes it after "
                          f"the close of {d})")
    try:
        rec = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return unmeasured(f"the account record {path} is unreadable: {type(e).__name__}: {e}")
    if not isinstance(rec, dict):
        return unmeasured(f"the account record {path} is not a JSON object")
    if rec.get("date") != d:
        return unmeasured(f"the account record {path} is for session {rec.get('date')!r}, not {d}")
    pos = rec.get("positions")
    qty = pos.get("qty") if isinstance(pos, dict) else None
    if not isinstance(qty, dict) or not all(isinstance(q, int) and not isinstance(q, bool) for q in qty.values()):
        return unmeasured(f"the account record {path} has no positions.qty of whole-share quantities")
    held = sorted(s for s, q in qty.items() if q != 0)
    n_long = sum(1 for s in held if qty[s] > 0)
    read_at = rec.get("read_at_utc") or "read time not recorded"
    check.update(status=WATCH if held else INFO, read_at_utc=rec.get("read_at_utc"), positions=len(held),
                 long=n_long, short=len(held) - n_long, symbols=held)
    if held:
        return (WATCH, f"Factor exposure FLAT DISAGREES with the account at the close of {d} (WATCH): the P&L job's "
                       f"fill rebuild holds no position there, but the collector's account record for {d} ({path}, "
                       f"read {read_at}) shows {len(held)} position(s), {n_long} long and {len(held) - n_long} short "
                       f"({', '.join(held)}); no factor exposure was read for them, so the book's factor risk at that "
                       f"close is unread (report only: nothing is sent)", check)
    return (INFO, f"Factor exposure FLAT at the close of {d}, cross-checked: the collector's account record for {d} "
                  f"({path}, read {read_at}) holds no position either", check)


def execution_block(state: Path, asof: dt.date, plan: dict | None) -> dict:
    """Planned against filled and fill cost, from the runner's records."""
    lines: list[str] = []
    data: dict = {}
    status = INFO
    if plan is not None:
        data["plan_status"] = plan.get("status")
        data["refusals"] = plan.get("refusals", [])
        lines.append(f"latest plan: status {plan.get('status')}, {len(plan.get('orders', []))} order(s), "
                     f"{len(plan.get('refusals') or [])} refusal(s), notes on "
                     f"{len(plan.get('notes') or {})} name(s)")
    try:
        rows = [r for r in read_csv_rows(state / "tca.csv", asof) if r["date"] == asof.isoformat()]
    except FileNotFoundError as e:
        rows = []
        lines.append(f"UNMEASURED: {e}")
    if rows:
        r = rows[-1]
        lines.append(f"tca {asof}: {r['n_full']}/{r['n_orders']} orders full, fill rate {r['fill_rate_shares']}, "
                     f"slip {r['slip_bp_all']}bp vs the official close")
        data["tca"] = {k: r[k] for k in ("n_orders", "n_full", "fill_rate_shares", "slip_bp_all")}
    else:
        lines.append(f"UNMEASURED: no tca.csv row for {asof} (verify writes it at 17:30 on a day with fills)")
        status = UNMEASURED
    lines.append("fill cost against breakeven: UNMEASURED: no file this job reads carries a per-account "
                 "breakeven; the 15:50-drift split (fill_drift.py) needs broker keys a report job must not hold")
    return block(status, lines, **data)


def diversification_block(book: str, state: Path, asof: dt.date) -> dict:
    """The two accounts' EOD daily changes, last common rows, read-only."""
    other = OTHER_BOOK[book]
    other_state = state.parent / other
    try:
        a = dd.read_series(state / dd.OFFICIAL_FILE, asof)
        b = dd.read_series(other_state / dd.OFFICIAL_FILE, asof)
    except dd.Unmeasured as e:
        return _unmeasured(f"the two accounts' EOD series: {e}")
    da, db = dict(a), dict(b)
    common = sorted(set(da) & set(db))
    ca = [da[d] for d in common]
    cb = [db[d] for d in common]
    ra = [ca[i] / ca[i - 1] - 1 for i in range(1, len(ca))]
    rb = [cb[i] / cb[i - 1] - 1 for i in range(1, len(cb))]
    if len(ra) < MIN_CORR_DAYS:
        return block(INFO, [f"live correlation with {other}: {len(ra)} common EOD changes (< {MIN_CORR_DAYS}): "
                            f"too few to print"], n=len(ra))
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    sa = math.sqrt(sum((x - ma) ** 2 for x in ra))
    sb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    rho = None if sa == 0 or sb == 0 else cov / (sa * sb)
    lines = [f"live correlation with {other} over {len(ra)} common EOD changes: "
             + ("undefined (flat series)" if rho is None else f"{rho:+.2f}"),
             "the fit's rho: UNMEASURED by this script: it is in no machine-readable file this job reads"]
    return block(INFO, lines, rho=rho, n=len(ra))


def data_qa_block(state: Path, asof: dt.date) -> dict:
    """Tonight's data-QA flags on held or targeted names (design s2.3: a WATCH)."""
    path = state / "reports" / "data_qa" / f"{asof.isoformat()}.json"
    if not path.is_file():
        return _unmeasured(f"no data-QA report at {path} (the 21:45 job has not written one for {asof})")
    rep = json.loads(path.read_text())
    held = [f for c in rep.get("checks", {}).values() for f in c.get("flags", []) if f.get("held")]
    if held:
        return block(WATCH, [f"{f['check']} {f.get('ticker') or ''} {f['date']}: {f['rule']}" for f in held],
                     held_flags=held, report_status=rep.get("status"))
    return block(INFO, [f"no data-QA flag on a held name; report status {rep.get('status')}"],
                 report_status=rep.get("status"))


# ------------------------------------------------------------------- the report

def severity_of(blocks: dict) -> str:
    return max((b["status"] for b in blocks.values()), key=lambda s: RANK[s], default=INFO)


def render_md(rep: dict) -> str:
    out = [f"# Risk, {rep['book']}, as-of {rep['asof']}", "",
           f"Generated {rep['generated_at']} (report only; nothing here touches an order).",
           f"Overall: **{rep['severity']}**.", ""]
    for name, b in rep["blocks"].items():
        out.append(f"## {name}: {b['status']}")
        out.extend(f"- {ln}" for ln in b["lines"])
        out.append("")
    if rep.get("act_lines"):
        out.append("## ACT")
        out.extend(f"- {ln}" for ln in rep["act_lines"])
        out.append(f"- notification: {rep['notification']}")
    return "\n".join(out) + "\n"


def run_report(book: str, state: Path, asof: dt.date, *, stops_output=None,
               now_utc=None, send=None) -> tuple[dict, int]:
    cfg = BOOKS[book]
    try:
        spec = read_spec(cfg)
    except Exception as e:
        spec = {"frozen": {}, "_error": f"spec unreadable: {type(e).__name__}: {e}"}
    now = (now_utc or dt.datetime.now(dt.timezone.utc)).astimezone(ET)
    try:
        plan, plan_path = latest_plan(state, asof)
    except Exception as e:
        plan, plan_path = None, None
        print(f"risk_daily: plan unreadable: {type(e).__name__}: {e}", file=sys.stderr)

    def guard(fn):
        """A block's own bug (an unexpected type in a record) must not cost the
        other blocks or the ACT line: it becomes that block's UNMEASURED, named."""
        try:
            return fn()
        except Exception as e:
            return _unmeasured(f"{type(e).__name__}: {e}")

    blocks = {
        "pnl": guard(lambda: pnl_block(state, asof)),
        "drawdown": guard(lambda: drawdown_block(state, spec, asof)),
        "stops": guard(lambda: stops_block(book, spec, stops_output)),
        "kill_rules": guard(lambda: kill_rules_block(book, state, spec, asof)),
        "exposure": guard(lambda: exposure_block(book, state, spec, asof)),
        "attribution": guard(lambda: attribution_block(book, state, asof)),
        "factor_exposure": guard(lambda: factor_block(book, state, asof)),
        "execution": guard(lambda: execution_block(state, asof, plan)),
        "diversification": guard(lambda: diversification_block(book, state, asof)),
        "data_qa": guard(lambda: data_qa_block(state, asof)),
    }
    act_lines = [ln for b in blocks.values() for ln in b["lines"] if ln.startswith("ACT")]
    rep: dict = {"book": book, "asof": asof.isoformat(), "generated_at": now.isoformat(timespec="seconds"),
                 "plan": plan_path, "spec_id": spec.get("spec_id"), "blocks": blocks,
                 "severity": severity_of(blocks), "act_lines": act_lines, "notification": None}
    code = 0
    out_dir = state / "reports" / "risk"
    report_path = out_dir / f"{asof.isoformat()}.md"
    if act_lines:
        res = notify_act(act_lines, book=book, asof=asof, report_path=str(report_path), send=send)
        rep["notification"] = res
        if not res["delivered"]:
            line = undelivered_line(str(res["reason"]))
            rep["act_lines"].append(line)
            print(line, file=sys.stderr)
            code = EXIT_ACT_UNDELIVERED
    write_atomic(out_dir / f"{asof.isoformat()}.json", json.dumps(rep, indent=1, default=str))
    write_atomic(report_path, render_md(rep))
    print(f"risk_daily {book} {asof}: {rep['severity']}; wrote {report_path}")
    return rep, code


def main(argv=None, *, now_utc=None, send=None) -> int:
    ap = argparse.ArgumentParser(description="The nightly risk report for one account (report only).")
    ap.add_argument("--book", required=True, choices=sorted(BOOKS))
    ap.add_argument("--state-dir", type=Path, default=None, help="default $QUANTT_STATE_DIR")
    ap.add_argument("--asof", type=dt.date.fromisoformat, default=None)
    ap.add_argument("--stops-output", type=Path, default=None,
                    help="a file holding stops.py's printed output, from a machine with its fit series")
    ap.add_argument("--notify-test", action="store_true",
                    help="send one test message through the ACT channel and exit; writes no report. "
                         "So the first thing to use the channel is not a real stop")
    a = ap.parse_args(argv)
    if a.notify_test:
        res = notify_act([f"ACT channel test for {a.book}: no stop has fired."], book=a.book,
                         asof=dt.date.today(), report_path="(test, no report)", send=send)
        print("delivered" if res["delivered"] else undelivered_line(str(res["reason"])),
              file=None if res["delivered"] else sys.stderr)
        return 0 if res["delivered"] else EXIT_ACT_UNDELIVERED
    state = a.state_dir or (Path(os.environ["QUANTT_STATE_DIR"]) if os.environ.get("QUANTT_STATE_DIR") else None)
    if state is None:
        print("REFUSED: no --state-dir and no QUANTT_STATE_DIR", file=sys.stderr)
        return 2
    now = (now_utc or dt.datetime.now(dt.timezone.utc)).astimezone(ET)
    asof = a.asof or expected_day(now)
    _, code = run_report(a.book, state, asof, stops_output=a.stops_output, now_utc=now_utc, send=send)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
