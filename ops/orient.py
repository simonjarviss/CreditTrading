#!/usr/bin/env python3
"""One command that tells a new agent where it is and what is true RIGHT NOW.

    python3 -m ops.orient              # the readout
    python3 -m ops.orient --json       # machine-readable
    python3 -m ops.orient --no-tests   # skip the pytest collection count

WHY THIS FILE EXISTS
--------------------
`CLAUDE.md` is loaded into every agent's context, and by 2026-09-11 roughly a
third of it was archaeology of its own wrong numbers: "3 of 26" corrected to
"5 of 29"; a test count that read 126, then 271, then 211 inside 24 hours; a
`0.064` literal count that said four and missed three including the one in its
own new file; a table asserting its own remedy was applied when it was not, and
later that it was missing when it was not. Each correction was itself a fact
with a shelf life, so the file grew by the square of its own staleness.

Every one of those passages already carried the command that settles it. The
commands were just scattered across 473 lines, so nobody ran all of them and the
prose kept being the cheaper thing to read. This module runs them.

THE HOUSE RULE THIS SERVES (CLAUDE.md, H14)
-------------------------------------------
"No decision rule may key on a number written in a document. Every figure in
these docs is a dated observation with a method, not an input." A document
cannot follow that rule on its own behalf -- a written number is a written
number. A command can. So the intended end state is that `CLAUDE.md` keeps the
RULES, which do not rot, and points here for the FIGURES, which do.

Accordingly: every line of output below names the reproducer that produced it,
and nothing here is a constant. The one exception is labelled `[doc]` -- the
trial counter, which the repo deliberately keeps canonical in prose because it
counts human decisions and no code can observe it. It is shown with its source
file so that it reads as a citation and not as a measurement.

NO SILENT FALLBACKS, AND WHAT THAT MEANS FOR A READ-ONLY REPORT
---------------------------------------------------------------
Each section is independently guarded, and a section that cannot measure prints
`UNMEASURED` with the exception that stopped it. That is the opposite of a
fallback: it is a named gap, and the repo's rule is "raise, naming what was
missing". A monitor that aborts the whole readout because one panel is absent
tells you less than one that reports nine facts and one gap, and an orientation
tool that invented a plausible value for the tenth would be the exact failure
this desk has paid for most often.

TRANSMITS NOTHING. Reads files and runs `git`, `pytest --collect-only`,
`ops.doc_audit`, `launchctl list` / `print-disabled`, and one `ssh` to the VM
that runs a fixed read-only script (`ops/prod_state.py`). No broker socket is
opened anywhere in this path, and none of the modules it imports opens one at
import time. It never reads `config/.env` or the VM's key file.

REWRITTEN 2026-09-28 FOR THE ALPACA MIGRATION. IBKR was retired that day
(`docs/ROADMAP.md`). The sections that read
the IBKR prod tree -- TREES' prod half, HALTS, BOOK, UPTIME -- described a
system that no longer runs, so they were replaced by ALPACA, which reads the
read-only probe's snapshots. The pre-migration module is at git tag
`pre-clean-slate`.

PROD ADDED 2026-10-08 (`docs/ROADMAP.md` 4.8). The rewrite above hard-coded
"prod none ... the Alpaca prod is not built" and "live book NONE -- nothing
trades". The book armed on 2026-09-29 and both lines stayed, because a string
cannot notice it has become false. PROD now measures both prod machines (the
laptop's launchd jobs and the Azure VM's systemd units) and says which one is
armed; ALPACA takes live equity from the armed machine's `equity.csv` (a
snapshot read after the close; the P&L of record is PNL, 2026-10-19) and labels the probe snapshot with its age, since that snapshot is
evidence of tradability and borrow on its date and of nothing else.

PNL ADDED 2026-10-19. The team lead ruled that day that Alpaca's end-of-day
portfolio history is the official daily P&L of record, and that verify's
after-the-close `equity - last_equity` -- which verify.log had been calling
"(official, gross)" -- is a labelled snapshot. PNL prints the record from the
prod machine's `eod_equity.csv` (last sessions, cumulative since funding,
high-water mark and drawdown, realised vol beside the spec's vol target), and
the snapshot, auction-marked and distribution-adjusted scores beside it, each
in its own labelled column and never blended into it (`pnl`).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# The IBKR-era prod worktree. Retired 2026-09-28; reported only if it lingers,
# because a leftover detached tree is the one place old code could still run.
PROD_TREE = Path.home() / "prod" / "QUANTT"
PROBE_DIR = REPO / "results/ops/alpaca_probe"

RESEARCH_STATE = REPO / "docs/RESEARCH_STATE.md"
PANELS = {
    "cef_prices": REPO / "data/cef/cef_prices.parquet",
    "cef_nav": REPO / "data/cef/cef_nav.parquet",
}


class Unmeasured(Exception):
    """Raised by a section that cannot honestly produce its number."""


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> str:
    r = subprocess.run(cmd, cwd=cwd or REPO, capture_output=True,
                       text=True, timeout=timeout)
    if r.returncode != 0 and not r.stdout.strip():
        raise Unmeasured(f"{' '.join(cmd[:3])}… rc={r.returncode}: "
                         f"{r.stderr.strip()[:120]}")
    return r.stdout


def _trading_days_since(d: dt.date) -> int | None:
    try:
        from ops.schedule import nyse_calendar as cal
        n, cur = 0, d
        today = dt.date.today()
        while cur < today and n < 2000:
            cur += dt.timedelta(days=1)
            if cal.is_trading_day(cur):
                n += 1
        return n
    except Exception:
        return None


# ------------------------------------------------------------------- trees --
def trees() -> dict:
    """Where you are, and whether the retired IBKR prod tree is still around.

    Until 2026-09-28 this compared dev with a detached prod worktree. That tree
    ran the IBKR book and was retired with it. Which machine runs the Alpaca
    prod, at which tag, armed or not, is PROD's question (`prod()`), not this
    one's: it moves, and this section once printed a constant answer to it.
    `ibkr-final` tags the last IBKR-era commit, so "what did the old system
    run" stays a git question.
    """
    out = {"reproducer": "git status  ·  git describe --tags  ·  git tag -l ibkr-final"}
    out["dev"] = {
        "path": str(REPO),
        "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip(),
        "sha": _run(["git", "rev-parse", "--short", "HEAD"]).strip(),
        "uncommitted": len([l for l in _run(
            ["git", "status", "--porcelain"]).splitlines() if l.strip()]),
    }
    out["ibkr_final"] = _run(["git", "tag", "-l", "ibkr-final"]).strip() or None
    out["legacy_prod_present"] = PROD_TREE.is_dir()
    return out


# -------------------------------------------------------------------- prod --
def prod() -> dict:
    """Which machine is prod, at which tag, and whether it is armed.

    All of it is `ops.prod_state.measure()`, shared with the SessionStart
    banner and the status line so the three cannot disagree. orient gives the
    VM the long ssh budget (`prod_state.VM_TIMEOUT_S`); the banner a short one.
    """
    from ops import prod_state
    return prod_state.measure()


# ------------------------------------------------------------------ alpaca --
def _snapshot_age_days(fetched_at_utc, today: dt.date | None = None):
    """Calendar days since the probe ran, from its own `fetched_at_utc`. None
    when the snapshot does not say when it ran: an age is never guessed from
    the file name, which is the date it was written under, not measured at."""
    if not fetched_at_utc:
        return None
    try:
        when = dt.datetime.fromisoformat(str(fetched_at_utc)).date()
    except ValueError:
        return None
    return ((today or dt.date.today()) - when).days


def alpaca() -> dict:
    """What the latest read-only probe of each Alpaca paper account recorded.

    Reads `results/ops/alpaca_probe/<date>_<book>.json`, written by
    `python3 -m quantt.broker.alpaca_probe`. Never calls Alpaca itself and
    never reads keys: orientation must work on a machine with no credentials.
    A book with no snapshot is UNMEASURED by name, not assumed tradable.
    `borrow_status` moves daily, so the snapshot's date and age are printed.

    The snapshot's account figures (equity, positions, orders) are kept in the
    JSON but NOT rendered: until 2026-10-08 the readout printed the
    2026-09-28 snapshot's equity beside the account as if it were today's.
    Live equity is the armed prod's `equity.csv` (PROD): a snapshot read after
    the close. The P&L of record is the PNL section (2026-10-19).
    """
    from quantt.broker.alpaca_probe import BOOK_SPECS
    out = {"reproducer": "python3 -m quantt.broker.alpaca_probe   (snapshots; "
                         "live equity is PROD's)", "books": {}}
    for book in BOOK_SPECS:
        snaps = sorted(PROBE_DIR.glob(f"*_{book}.json"))
        if not snaps:
            out["books"][book] = {"snapshot": None}
            continue
        d = json.loads(snaps[-1].read_text())
        assets = d.get("assets") or {}
        def names(pred):
            return sorted(k for k, a in assets.items() if pred(a))
        acct = d.get("account") or {}
        out["books"][book] = {
            "snapshot": snaps[-1].name,
            "fetched_at_utc": d.get("fetched_at_utc"),
            "age_days": _snapshot_age_days(d.get("fetched_at_utc")),
            "equity_at_snapshot": acct.get("equity"),
            "n_assets": len(assets),
            "not_found": names(lambda a: "_probe" in a),
            "not_tradable": names(lambda a: "_probe" not in a and a.get("tradable") is not True),
            "not_shortable": names(lambda a: "_probe" not in a and a.get("shortable") is not True),
            "hard_to_borrow": names(lambda a: a.get("borrow_status") == "hard_to_borrow"),
            "positions": len(d.get("positions") or []),
            "open_orders": len(d.get("open_orders") or []),
        }
    return out


# --------------------------------------------------------------------- pnl --
# The repo's annualisation: sample sd of daily returns x sqrt(252), as the
# canonical harness and the sleeve's own realised-vol estimate both do
# (`scripts/cef/band_frontier.py` evaluate, `src/deploy/sleeves/cef_discount.py`).
TRADING_DAYS_PER_YEAR = 252
PNL_SHOWN_SESSIONS = 10
# Two-decimal dollar columns: a difference of half a cent or more is a real one.
PNL_TOL_USD = 0.005
# The labelled, never-blended columns of the session table, in print order:
# key, header, (file key in prod_state.PNL_FILES, column) or None for official.
PNL_COLUMNS = (
    ("official", "official", None),
    ("snapshot", "snapshot", ("scores", "alpaca_equity_change_usd")),
    ("auction", "auction", ("scores", "auction_pnl_usd")),
    ("dist_adj", "dist-adj", ("dist", "auction_pnl_with_distributions_usd")),
)
PNL_LEGEND = (
    "official = eod_equity.csv change_usd: Alpaca's end-of-day history, the P&L of record "
    "(team lead 2026-10-19)",
    "snapshot = scores.csv alpaca_equity_change_usd: equity - last_equity read after the "
    "close by verify; a SNAPSHOT, not the record",
    "auction = scores.csv auction_pnl_usd: auction-marked (quantt/session/score.py (b))",
    "dist-adj = distribution_scores.csv auction_pnl_with_distributions_usd "
    "(quantt/session/dist_score.py)",
    "each column is its own file's, never filled from another; all gross",
)


def _finite(text: str, what: str) -> float:
    try:
        x = float(text)
    except (TypeError, ValueError):
        raise Unmeasured(f"{what} is {text!r}, not a number") from None
    if not math.isfinite(x):
        raise Unmeasured(f"{what} is {text!r}, not finite")
    return x


def official_pnl(reading: dict | None) -> dict:
    """The official daily P&L series (Alpaca EOD history) and what it implies.

    `reading` is one of `ops.prod_state.pnl_readings`' entries for
    eod_equity.csv: rows of (date, equity, change_usd) as strings. Every
    figure below is from that file alone; nothing from the snapshot or the
    scores fills a gap in it (team lead 2026-10-19: never blended).

    WHERE IT STARTS. Days before the account was funded carry equity 0
    [V, the history as read by the main session 2026-10-19]. The first row
    with equity > 0 is the first funded row, F. F's own change is measured
    against an unfunded day, so it is the funding, not P&L; every figure here
    runs from F's close. If the file starts after funding, F is simply its
    first row, and F's date is printed so a reader sees where it starts.

    WHAT EACH FIGURE IS.
      cumulative   sum of change_usd over the sessions after F
      high-water   the peak of that cumulative curve (F's close counts, at 0),
                   with the file's equity on the peak date; drawdown is the
                   curve's last value minus the peak, and as a fraction of the
                   equity at the peak
      vol          sample sd of change_usd / previous EOD equity, x sqrt(252),
                   with n; fewer than two returns is a gap, not a zero
    change_usd is the record, so it drives every figure. It is also checked
    against the difference of consecutive EOD equities: a cashflow or a file
    defect shows there, and each day it does is reported with both values;
    neither is averaged in or silently preferred.

    Raises `Unmeasured` naming the file and the row for anything it cannot
    read as agreed: unparseable or non-increasing dates, a non-number, a zero
    equity after funding, or a file longer than the reader carries (the
    whole-series figures are never computed on a window).
    """
    from ops import prod_state
    if not isinstance(reading, dict):
        raise Unmeasured("no eod_equity.csv reading for the prod machine")
    if "absent" in reading:
        raise Unmeasured(reading["absent"])
    if "UNMEASURED" in reading:
        raise Unmeasured(reading["UNMEASURED"])
    f = reading["value"]
    name = f"{f['where']}/{f['file']}"
    rows = f["rows"]
    if f["n_rows"] > len(rows):
        raise Unmeasured(f"{name} holds {f['n_rows']} rows, more than the {len(rows)} the "
                         f"reader carries (ops.prod_state.EOD_MAX_ROWS); whole-series "
                         f"figures are not computed on a window")
    parsed, prev = [], None
    for date_s, eq_s, ch_s in rows:
        try:
            d = dt.date.fromisoformat(date_s)
        except ValueError:
            raise Unmeasured(f"{name}: date {date_s!r} is not YYYY-MM-DD") from None
        if prev is not None and d <= prev:
            raise Unmeasured(f"{name}: {d} follows {prev}; not one row per session in date order")
        prev = d
        eq = _finite(eq_s, f"{name} {d} equity")
        if eq < 0:
            raise Unmeasured(f"{name} {d} equity is negative ({eq_s})")
        parsed.append((d, eq, ch_s))
    if not parsed:
        raise Unmeasured(f"{name} has a header and no rows yet")
    first = next((i for i, r in enumerate(parsed) if r[1] > 0), None)
    if first is None:
        raise Unmeasured(f"{name}: no funded row (equity is 0 on every one of {len(parsed)})")
    f_date, f_eq, _ = parsed[first]

    sessions, disagree = [], []
    for (_pd, peq, _pc), (d, eq, ch_s) in zip(parsed[first:], parsed[first + 1:]):
        if eq <= 0:
            raise Unmeasured(f"{name}: equity {eq} on {d}, after funding on {f_date}")
        ch = _finite(ch_s, f"{name} {d} change_usd")
        if abs(ch - (eq - peq)) >= PNL_TOL_USD:
            disagree.append({"date": d.isoformat(), "change_usd": ch,
                             "equity_diff_usd": round(eq - peq, 2)})
        sessions.append({"date": d.isoformat(), "change_usd": ch, "equity": eq,
                         "return": ch / peq})

    cum, peak, peak_date, peak_eq = 0.0, 0.0, f_date.isoformat(), f_eq
    for s in sessions:
        cum += s["change_usd"]
        if cum > peak:
            peak, peak_date, peak_eq = cum, s["date"], s["equity"]
    rets = [s["return"] for s in sessions]
    if len(rets) >= 2:
        import statistics
        vol = {"annual": statistics.stdev(rets) * TRADING_DAYS_PER_YEAR ** 0.5, "n": len(rets)}
    else:
        vol = {"annual": None, "n": len(rets),
               "why": f"{len(rets)} daily return(s): a sample sd needs at least 2"}
    last_d, last_eq, _ = parsed[-1]
    return {"source": name,
            "first_funded": {"date": f_date.isoformat(), "equity": f_eq},
            "last": {"date": last_d.isoformat(), "equity": last_eq,
                     "trading_days_ago": prod_state.trading_days_since(last_d.isoformat())},
            "n_sessions": len(sessions), "cumulative_usd": cum,
            "hwm": {"date": peak_date, "equity": peak_eq, "cumulative_usd": peak},
            "drawdown_usd": cum - peak, "drawdown_frac": (cum - peak) / peak_eq,
            "vol": vol, "disagreements": disagree,
            "sessions": sessions[-PNL_SHOWN_SESSIONS:]}


def _by_date(reading: dict | None, col: str, file_key: str) -> tuple[dict, str | None, str | None]:
    """({date: [values in file order]}, read-from date or None, gap text or None)
    for one column of one P&L file. When the file holds more rows than were
    carried, dates up to and including the first carried date may be only
    partly read; they are reported as not read, never as "no row"."""
    from ops import prod_state
    name, cols, _keep = prod_state.PNL_FILES[file_key]
    if not isinstance(reading, dict):
        return {}, None, "UNMEASURED"
    if "absent" in reading:
        return {}, None, "no file"
    if "UNMEASURED" in reading:
        return {}, None, "UNMEASURED"
    f = reading["value"]
    i = cols.index(col)
    out: dict = {}
    for row in f["rows"]:
        out.setdefault(row[0], []).append(row[i])
    partial = f["rows"][0][0] if f["n_rows"] > len(f["rows"]) and f["rows"] else None
    return out, partial, None


def _cell(values: list, what: str, notes: list):
    """One date's value from one column: a float, or a marker naming the gap.
    Re-runs append rows, so a date can have several. Two different measured
    values is a CONFLICT, both are noted and neither is picked (the rule
    `quantt/session/dist_score.py` auction_pnl_for applies); an UNMEASURED row
    beside a measured one contradicts nothing."""
    if not values:
        return "no row"
    measured = sorted(set(values) - {"UNMEASURED", ""})
    if not measured:
        return "UNMEASURED"
    if len(measured) > 1:
        notes.append(f"{what}: {len(measured)} rows disagree ({', '.join(measured)}); "
                     f"neither is picked")
        return "CONFLICT"
    try:
        return _finite(measured[0], what)
    except Unmeasured as e:
        notes.append(str(e))
        return "BAD"


def pnl_table(official: dict, files: dict) -> dict:
    """The last sessions, one labelled column per series (`PNL_COLUMNS`).

    The dates are the official series' last sessions when it is measured, so
    each row is a session of record; otherwise the last dates any score file
    holds. A cell is only ever its own file's value for its own date."""
    from ops import prod_state
    notes: list = []
    cols = {}
    for key, _head, src in PNL_COLUMNS[1:]:
        cols[key] = _by_date(files.get(src[0]), src[1], src[0])
    verdicts = _by_date(files.get("scores"), "verdict", "scores")
    if "UNMEASURED" in official:
        dates = sorted({d for m, _p, _g in cols.values() for d in m})[-PNL_SHOWN_SESSIONS:]
        official_by_date = {}
    else:
        dates = [s["date"] for s in official["sessions"]]
        official_by_date = {s["date"]: s["change_usd"] for s in official["sessions"]}
    rows = []
    for d in dates:
        row = {"date": d, "official": official_by_date.get(d, "UNMEASURED")}
        for key, head, _src in PNL_COLUMNS[1:]:
            m, partial, gap = cols[key]
            row[key] = (gap if gap else "not read" if partial and d <= partial
                        else _cell(m.get(d, []), f"{d} {head}", notes))
        vm, vpartial, vgap = verdicts
        vs = list(dict.fromkeys(vm.get(d, [])))
        row["verdict"] = (vgap if vgap else "not read" if vpartial and d <= vpartial
                          else "/".join(vs) if vs else "no row")
        rows.append(row)
    sums = {}
    for key, _head, _src in PNL_COLUMNS:
        vals = [r[key] for r in rows]
        num = [v for v in vals if isinstance(v, float)]
        sums[key] = sum(num) if rows and len(num) == len(vals) else f"{len(num)} of {len(vals)}"
    # The score files' gaps; eod_equity.csv's is the official line's own.
    gaps = [f"{name}: {g}" for k, (name, _c, _n) in prod_state.PNL_FILES.items()
            if k != "eod_equity" and (g := _reading_gap(files.get(k)))]
    return {"rows": rows, "sums": sums, "notes": notes, "file_gaps": gaps}


def _reading_gap(r) -> str | None:
    if not isinstance(r, dict):
        return "UNMEASURED — no reading"
    if "absent" in r:
        return f"none ({r['absent']})"
    if "UNMEASURED" in r:
        return f"UNMEASURED — {r['UNMEASURED']}"
    return None


def _vol_target() -> dict:
    """`vol_target_annual` through `scripts/cef/spec.py`, the spec's single
    reader. A missing key is a named gap: the sleeve's code default is not a
    governance decision and is never printed here (see `spec_fields`)."""
    try:
        sys.path.insert(0, str(REPO / "scripts/cef"))
        import importlib
        sp = importlib.import_module("spec")
        return {"value": sp.frozen("vol_target_annual"), "spec_id": sp.SPEC_ID}
    except Exception as exc:  # SpecError, or the spec module failing at import: a named gap
        return {"UNMEASURED": f"{type(exc).__name__}: {exc}"}


def pnl(prod_sec: dict) -> dict:
    """The book's daily P&L, from the PROD machine's own files.

    WHY (team lead, 2026-10-19). Alpaca's end-of-day portfolio history is the
    official daily P&L of record. verify's `equity - last_equity`, read after
    the close, had been printed as "(official, gross)"; it is marked after the
    close and differed from the EOD history on every session the main session
    compared that day, while the auction-marked score agreed with it far more
    closely. So the record leads here, and the snapshot, auction-marked and
    distribution-adjusted scores sit beside it in their own labelled columns,
    never blended into it and never standing in for a missing day of it.

    Only the prod machine's files are read, as ALPACA's live equity is: the
    other machine's are a different ledger of the same account (PROD lists
    each machine's files). The rows come from PROD's one ssh call, so this
    section adds no connection of its own.
    """
    if "UNMEASURED" in prod_sec:
        raise Unmeasured(f"PROD could not be measured ({prod_sec['UNMEASURED']})")
    v = prod_sec.get("verdict") or {}
    if v.get("warning"):
        raise Unmeasured("two machines are armed (PROD WARNING): there is no one prod "
                         "to read the P&L from")
    if not v.get("prod"):
        raise Unmeasured("no machine is measured armed (PROD), so there is no prod series; "
                         "each machine's P&L files are listed under it there")
    files = ((prod_sec.get("machines") or {}).get(v["prod"]) or {}).get("pnl")
    if not isinstance(files, dict):
        raise Unmeasured(f"PROD's reading of the {v['prod']} carries no P&L files")
    try:
        official = official_pnl(files.get("eod_equity"))
    except Unmeasured as exc:
        official = {"UNMEASURED": str(exc)}
    return {"reproducer": "python3 -m ops.orient --json   (sections.PNL; rows: "
                          "ops.prod_state pnl_tails on the prod machine)",
            "prod": v["prod"], "where": files.get("where"), "official": official,
            "vol_target": _vol_target(), "table": pnl_table(official, files),
            "books": _pnl_other_books(prod_sec, v["prod"])}


def _pnl_other_books(prod_sec: dict, prod_machine: str) -> dict:
    """The same record for every other book on the VM (C4), from the rows PROD's
    one ssh call already brought back (`ops.prod_state` `books`).

    WHY (team lead, 2026-11-18: "make the c4 reachable as easily as everything
    else"). C4 has its own Alpaca account and its own eod_equity.csv on the VM,
    and nothing printed them: on 2026-11-18 its newest figure in reach was a
    copy in the repo seven sessions old. Each book is its own account, so the
    books are never summed here. No vol target line: `_vol_target` reads the
    core's spec, which says nothing about another book.

    Only when the VM is prod. The other books have no laptop twin, and with the
    laptop as prod the VM's files are not the ledger this section prints.
    """
    if prod_machine != "vm":
        return {}
    out = {}
    for name, b in (((prod_sec.get("machines") or {}).get("vm") or {}).get("books") or {}).items():
        files = b.get("pnl") if isinstance(b, dict) else None
        if not isinstance(files, dict):
            why = (b or {}).get("UNMEASURED") or "PROD's reading of this book carries no P&L files"
            out[name] = {"book": name, "prod": "vm", "where": None,
                         "official": {"UNMEASURED": f"book {name}: {why}"},
                         "table": {"rows": [], "sums": {}, "notes": [], "file_gaps": []}}
            continue
        try:
            official = official_pnl(files.get("eod_equity"))
        except Unmeasured as exc:
            official = {"UNMEASURED": str(exc)}
        out[name] = {"book": name, "prod": "vm", "where": files.get("where"),
                     "official": official, "table": pnl_table(official, files)}
    return out


# -------------------------------------------------------------------- spec --
def spec() -> dict:
    """Read through `scripts/cef/spec.py`, the single reader of that JSON."""
    sys.path.insert(0, str(REPO / "scripts/cef"))
    import importlib
    sp = importlib.import_module("spec")
    return spec_fields(sp.spec())


def spec_fields(s: dict) -> dict:
    """The live spec's decision-relevant keys, with ABSENT kept distinct from a value.

    `vol_target_annual` is here because documents disagreed about the vol
    target while the spec held one number: "we target 6%" in three places, "the
    20% cap" in two, and neither said which the sleeve actually reads. When the
    key is missing this reports None and says the sleeve's own default applies
    -- it does not print that default, because a number shown here gets quoted
    as the spec's, and a code default is not a governance decision.
    """
    fr = s.get("frozen", {})
    return {"reproducer": "python3 -c \"import sys; sys.path.insert(0,"
                          "'scripts/cef'); import spec; print(spec.summary())\"",
            "spec_id": s.get("spec_id"), "status": s.get("status"),
            "vol_target_annual": fr.get("vol_target_annual"),
            "vol_target_absent": "vol_target_annual" not in fr,
            "sizing_multiplier": fr.get("sizing_multiplier"),
            "below_min_names": fr.get("below_min_names"),
            "below_min_names_absent": "below_min_names" not in fr,
            "below_min_names_floor": fr.get("below_min_names_floor"),
            "capital_usd": s.get("capital_usd"),
            "band_width": fr.get("band_width"),
            "rebalance_days": fr.get("rebalance_days"),
            "rebalance_days_inert": fr.get("band_width") is not None,
            "z_window": fr.get("z_window"),
            "order_type": fr.get("order_type"),
            "n_universe": len(fr.get("universe") or []),
            "min_trade_usd": (s.get("rebalance") or {}).get("min_trade_usd")}


# ------------------------------------------------------------------ trials --
def trials() -> dict:
    """The ONLY figure here read from a document, and labelled as such.

    A trial counter counts human decisions to test something. No code can
    observe it, so the repo keeps it canonical in one table
    (`docs/RESEARCH_STATE.md`) and requires it to be updated in the same commit
    as the trial. It is cited here, with its file, rather than measured -- and
    the deflated-Sharpe bar sqrt(2 ln N) is DERIVED from it live, because that
    bar was wrong in three documents at once when it was written out by hand.
    """
    import math
    if not RESEARCH_STATE.exists():
        raise Unmeasured(f"{RESEARCH_STATE} is missing")
    text = RESEARCH_STATE.read_text(errors="replace")
    rows = re.findall(r"^\|\s*\*\*([A-Z]+)\*\*\s*\|[^|]*\|\s*\*\*(\d+)\*\*\s*\|",
                      text, re.M)
    if not rows:
        raise Unmeasured("no canonical counter rows matched in "
                         f"{RESEARCH_STATE.name}; the table format changed")
    counters = {}
    for name, n in rows:
        n = int(n)
        counters[name] = {"trials": n,
                          "dsr_bar": round(math.sqrt(2 * math.log(n)), 3)
                          if n > 1 else None}
    return {"reproducer": f"grep -nE '^\\| \\*\\*[A-Z]+\\*\\*' "
                          f"docs/{RESEARCH_STATE.name}   [doc, not measured]",
            "source": f"docs/{RESEARCH_STATE.name} (canonical counter table)",
            "counters": counters}


# ------------------------------------------------------------------ panels --
def panels() -> dict:
    """Last date in each panel the live sleeve prices from. Stale is a form of
    wrong, and several panels in this repo lag by weeks."""
    import pandas as pd
    out = {"reproducer": "python3 -c \"import pandas as pd; "
                         "print(pd.read_parquet(P)['date'].max())\"",
           "panels": {}}
    for name, path in PANELS.items():
        if not path.exists():
            out["panels"][name] = {"last": None,
                                   "error": f"missing: {path}"}
            continue
        df = pd.read_parquet(path, columns=["date"])
        last = pd.to_datetime(df["date"]).max().date()
        out["panels"][name] = {"last": last.isoformat(),
                               "trading_days_old": _trading_days_since(last)}
    return out


# ----------------------------------------------------------------- hygiene --
def hygiene(run_tests: bool = True) -> dict:
    """The greps CLAUDE.md asks a reader to run before believing its prose.

    Each of these has been quoted wrongly in that file at least once. They are
    cheap, so the answer should be produced rather than remembered.
    """
    out = {"checks": {}}

    lits = [l for l in _run(
        ["grep", "-rn", r"0\.064", "--include=*.py", "scripts/cef"]
    ).splitlines() if l.strip()]
    out["checks"]["band_width_literals"] = {
        "reproducer": r"grep -rn '0\.064' --include=*.py scripts/cef",
        "count": len(lits),
        "lines": [l.split(":", 2)[0] + ":" + l.split(":", 2)[1] for l in lits],
        "rule": "read band_width from the frozen spec; never write the literal. "
                "Some hits are legitimate (sweep grids, historical comments) — "
                "the COUNT is what keeps rotting, so read the lines, not this."}

    bad = _unguarded_ib_insync()
    out["checks"]["ib_insync_unguarded"] = {
        "reproducer": "python3 -m ops.orient --json   (AST, not grep — see "
                      "_unguarded_ib_insync)",
        "count": len(bad), "lines": bad,
        "rule": "ib_insync hangs forever in its asyncio handshake on Python "
                "3.12+ and looks exactly like a dead broker connection. The "
                "safe shape is `try: ib_async / except ImportError: ib_insync`."}

    if run_tests:
        txt = _run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                   timeout=180)
        # `-q --collect-only` emits one `path: N` line per file and NO total.
        # Summing them is the whole parse; there is no "N tests collected" line
        # to regex for, and a regex that finds nothing must not silently become
        # a zero.
        per_file = re.findall(r"^\S+\.py: (\d+)$", txt, re.M)
        out["checks"]["tests_collected"] = {
            "reproducer": "python3 -m pytest --collect-only -q",
            "count": sum(int(n) for n in per_file) if per_file else None,
            "n_files": len(per_file) or None,
            "rule": "A green suite says nothing about the code that places "
                    "orders. Write a test with any change to the live path."}
        if not per_file:
            out["checks"]["tests_collected"]["UNMEASURED"] = (
                "pytest --collect-only -q produced no `path: N` lines; its "
                "output format changed and this parse needs updating")
    return out


def _unguarded_ib_insync(root: Path | None = None) -> list[str]:
    """`ib_insync` imports that do NOT sit behind an `ib_async` preference.

    WHY THIS IS AN AST WALK AND NOT THE GREP `CLAUDE.md` PRESCRIBES
    ---------------------------------------------------------------
    That file says to check with

        grep -rn '^ *from ib_insync' ops/ src/ scripts/ | grep -v ImportError

    and asserts the answer is zero. Run it on 2026-09-11 and it returns FIVE,
    because the `except ImportError:` that makes an import safe is on a
    DIFFERENT LINE from the import itself, so `grep -v ImportError` filters
    nothing. The recipe cannot express the property it is checking.

    The real answer that day was TWO -- `scripts/rv/measure_rth_liquidity.py`
    and `scripts/rv/probe_ibkr_spreads.py` both do `try: from ib_insync ...`
    with no `ib_async` attempt first, so on this machine's Python 3.13.5 they
    hang rather than fall back. Three others are correctly guarded. A check
    that says 5 and a document that says 0 are both useless in the same way:
    neither tells you which files to open.

    So: find every ib_insync import, then subtract those reached only as the
    ImportError fallback of a try whose body imports ib_async.
    """
    import ast
    root = root or REPO
    found: list[str] = []
    for d in ("ops", "src", "scripts"):
        if not (root / d).is_dir():
            continue
        for path in sorted((root / d).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(errors="replace"))
            except SyntaxError:
                continue

            def imports(node, mod: str) -> list[ast.AST]:
                hits = []
                for n in ast.walk(node):
                    if isinstance(n, ast.ImportFrom) and (n.module or "") == mod:
                        hits.append(n)
                    elif isinstance(n, ast.Import):
                        if any(a.name.split(".")[0] == mod for a in n.names):
                            hits.append(n)
                return hits

            guarded: set[int] = set()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Try):
                    continue
                # the try body must PREFER ib_async ...
                if not any(imports(s, "ib_async") for s in node.body):
                    continue
                for h in node.handlers:
                    names = []
                    if isinstance(h.type, ast.Name):
                        names = [h.type.id]
                    elif isinstance(h.type, ast.Tuple):
                        names = [e.id for e in h.type.elts
                                 if isinstance(e, ast.Name)]
                    elif h.type is None:
                        names = ["ImportError"]  # bare except catches it
                    if "ImportError" not in names:
                        continue
                    # ... and ib_insync must be the FALLBACK, not the first try
                    for s in h.body:
                        for hit in imports(s, "ib_insync"):
                            guarded.add(hit.lineno)

            for hit in imports(tree, "ib_insync"):
                if hit.lineno not in guarded:
                    found.append(f"{path.relative_to(root)}:{hit.lineno}")
    return found


# -------------------------------------------------------------------- docs --
def doc_drift() -> dict:
    """The document audit, run as a subprocess: it imports this module, and a
    report that imports its own auditor in-process is one refactor from a cycle.
    (The work-order index check, `ops.prompt_status`, was deleted with the work
    orders on 2026-09-28.)"""
    out = {"reproducer": "python3 -m ops.doc_audit --check"}
    r = subprocess.run([sys.executable, "-m", "ops.doc_audit", "--json"],
                       cwd=REPO, capture_output=True, text=True, timeout=120)
    try:
        rows = json.loads(r.stdout)
        drift = [f"{x['key']}: {x['detail']}" for x in rows
                 if x.get("status") in ("DRIFT", "GONE")]
        out["doc_audit_drift"] = len(drift)
        out["doc_audit_rows"] = drift[:5]
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        out["doc_audit_drift"] = (f"UNMEASURED ({type(exc).__name__}; "
                                  f"rc={r.returncode} {r.stderr.strip()[:80]})")
    return out


# ------------------------------------------------------------------ render --
SECTIONS = [
    ("TREES", trees), ("PROD", prod), ("ALPACA", alpaca), ("PNL", pnl),
    ("SPEC", spec), ("TRIALS", trials), ("PANELS", panels),
    ("HYGIENE", hygiene), ("DOC DRIFT", doc_drift),
]


def collect(run_tests: bool = True) -> dict:
    """Each section on its own guard. PNL is built from PROD's reading (its
    rows came over PROD's one ssh call), so it runs after PROD and is handed
    that section rather than measuring the machines a second time."""
    out = {"measured_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "running_in": str(REPO), "sections": {}}
    for name, fn in SECTIONS:
        try:
            out["sections"][name] = (
                fn(run_tests=run_tests) if fn is hygiene else
                fn(out["sections"].get("PROD")
                   or {"UNMEASURED": "PROD was not measured in this call"}) if fn is pnl else
                fn())
        except Exception as exc:
            out["sections"][name] = {
                "UNMEASURED": f"{type(exc).__name__}: {exc}"}
    return out


LABEL_W = 30


def _live_equity(prod_sec: dict) -> str:
    """The armed prod's last equity.csv row, or why there is none.

    Only the ARMED (or per-day) machine's file is the live ledger: a shadow's
    copy, or the laptop's after cut-over, describes the same account through a
    scheduler that is not sending, so it is shown under its machine in PROD and
    never promoted to here.
    """
    from ops import prod_state
    if "UNMEASURED" in prod_sec:
        return f"UNMEASURED — PROD could not be measured ({prod_sec['UNMEASURED']})"
    v = prod_sec.get("verdict") or {}
    if v.get("warning"):
        return ("not chosen — two machines are armed (PROD WARNING), so there is no "
                "one prod to read it from; each machine's last row is shown there")
    if not v.get("prod"):
        return ("none — no machine is measured armed (PROD); each machine's last "
                "row is shown there")
    return f"{prod_state.equity_text(v.get('equity'))}  [{v['prod']}]"


def _usd(x: float, signed: bool = False) -> str:
    sign = ("+" if x >= 0 else "-") if signed else ("-" if x < 0 else "")
    return f"{sign}${abs(x):,.2f}"


PNL_CELL_W = 11


def _cell_text(v) -> str:
    return f"{v:+.2f}" if isinstance(v, float) else str(v)[:PNL_CELL_W - 1]


def _render_pnl(sec: dict) -> None:
    """PNL's lines. The record first; the other three only as their own
    labelled columns, with a legend saying which file and column each is."""
    o = sec["official"]
    if sec.get("book"):
        _p(f"book {sec['book']}: official P&L", f"its own Alpaca account, same source and "
           f"columns as above; never summed with another book  [{sec['prod']}]")
    else:
        _p("official P&L of record", f"Alpaca end-of-day portfolio history (GET /v2/account/"
           f"portfolio/history, 1D; team lead 2026-10-19)  [{sec['prod']}]")
    if "UNMEASURED" in o:
        _p("", f"UNMEASURED — {o['UNMEASURED']}")
    else:
        last, f0, h, vol = o["last"], o["first_funded"], o["hwm"], o["vol"]
        age = last.get("trading_days_ago")
        _p("", f"{o['source']}: last close {last['date']}"
           + (f" ({age} trading day(s) ago)" if age is not None else ""))
        _p("", "[U] Alpaca's docs say neither when a day's point is published nor whether "
               "a published one is revised (docs/REFERENCES.md 12an): this is the file as read now")
        _p("cumulative (official)", f"{_usd(o['cumulative_usd'], True)} over {o['n_sessions']} "
           f"session(s): the {f0['date']} close ({_usd(f0['equity'])}, first funded row) to the "
           f"{last['date']} close ({_usd(last['equity'])})")
        _p("high-water mark (official)", f"{_usd(h['equity'])} at the {h['date']} close; "
           + ("the last close is at it" if abs(o["drawdown_usd"]) < PNL_TOL_USD else
              f"drawdown from it {_usd(o['drawdown_usd'], True)} ({o['drawdown_frac']:+.2%})"))
        _p("realised vol (official)",
           f"{vol['annual']:.2%}/yr, n={vol['n']} daily returns (sample sd of change_usd / "
           f"previous EOD equity, x sqrt({TRADING_DAYS_PER_YEAR}))" if vol["annual"] is not None
           else f"UNMEASURED — {vol['why']}")
        for g in o["disagreements"]:
            _p("  caution", f"{g['date']}: change_usd {g['change_usd']:+.2f} but EOD equity moved "
                            f"{g['equity_diff_usd']:+.2f} (a cashflow or a file defect); the "
                            f"figures above use change_usd, the record")
    vt = sec.get("vol_target")
    if vt is None:
        pass                      # another book: the core's spec is not its target
    elif "UNMEASURED" in vt:
        _p("vol target (spec)", f"UNMEASURED — {vt['UNMEASURED']}")
    else:
        try:
            as_pct = f" = {float(vt['value']):.2%}/yr"
        except (TypeError, ValueError):
            as_pct = " (not a number)"
        _p("vol target (spec)", f"vol_target_annual {vt['value']}{as_pct}   "
                                f"(scripts/cef/spec.py, {vt['spec_id']})")

    t = sec["table"]
    if not t["rows"]:
        _p("sessions", "none: no dated row in scores.csv or distribution_scores.csv"
           if "UNMEASURED" in o else "none yet: no session after the first funded row")
    else:
        w = PNL_CELL_W
        _p(f"last {len(t['rows'])} session(s)",
           f"{'date':<10}" + "".join(f"{h:>{w}}" for _k, h, _s in PNL_COLUMNS) + "  verdict")
        for r in t["rows"]:
            _p("", f"{r['date']:<10}" + "".join(f"{_cell_text(r[k]):>{w}}" for k, _h, _s in PNL_COLUMNS)
               + f"  {r['verdict']}")
        _p("", f"{'sum':<10}" + "".join(f"{_cell_text(t['sums'][k]):>{w}}" for k, _h, _s in PNL_COLUMNS))
    for n in t["notes"]:
        _p("  note", n)
    for g in t["file_gaps"]:
        _p("  file", g)
    if sec.get("book"):
        return                    # the legend is printed once, under the core
    for i, line in enumerate(PNL_LEGEND + (
            "sum is over the sessions shown; 'k of n' where a column has a gap there "
            "(a sum with a missing term is not the sum)",)):
        _p("columns" if i == 0 else "", line)
    for b in (sec.get("books") or {}).values():
        _render_pnl(b)


def _p(label: str, value: str = "") -> None:
    """Pad, but never TRUNCATE a label into the value column: a check name
    that collides with its own number is how a readout starts lying."""
    print(f"  {label:<{LABEL_W}}{value}" if len(label) <= LABEL_W
          else f"  {label}\n  {'':<{LABEL_W}}{value}")


def render(d: dict) -> None:
    print(f"\nQUANTT ORIENTATION — measured {d['measured_at']}")
    print("Every figure below was produced just now by the reproducer named "
          "beside it.\nNothing here is copied from a document except the line "
          "marked [doc].\n")

    s = d["sections"]

    def head(name: str) -> dict | None:
        sec = s.get(name) or {}
        if "UNMEASURED" in sec:
            print(f"{name}\n  UNMEASURED — {sec['UNMEASURED']}\n")
            return None
        print(f"{name:<22}{sec.get('reproducer', '')}")
        return sec

    if (sec := head("TREES")) is not None:
        dv = sec["dev"]
        _p("dev  (you are here)", f"{dv['path']}  {dv['branch']} {dv['sha']}"
                                  f"  {dv['uncommitted']} uncommitted")
        _p("ibkr-final tag", sec["ibkr_final"] or "MISSING — the IBKR-era record has no tag")
        _p("prod", "measured in PROD below (which machine, which tag, armed or not)")
        if sec["legacy_prod_present"]:
            _p("", f"  {PROD_TREE} (the retired IBKR tree) still exists on this "
                   "machine; it is not the Alpaca prod")
        print()

    if (sec := head("PROD")) is not None:
        from ops import prod_state
        prod_state.render_lines(sec, _p)
        print()

    if (sec := head("ALPACA")) is not None:
        _p("live equity", _live_equity(s.get("PROD") or {}))
        for book, b in sec["books"].items():
            if not b.get("snapshot"):
                _p(f"account: {book}", "UNMEASURED — no probe snapshot yet")
                continue
            age = b.get("age_days")
            when = (str(b.get("fetched_at_utc"))[:10] if b.get("fetched_at_utc")
                    else f"UNDATED ({b['snapshot']} has no fetched_at_utc)")
            _p(f"account: {book}", f"snapshot {when}, "
               + (f"{age} day(s) old" if age is not None else "age UNMEASURED")
               + " — tradability/borrow only")
            _p("", f"  {b['n_assets']} spec names; not found {b['not_found'] or 'none'}; "
                   f"not tradable {b['not_tradable'] or 'none'}")
            _p("", f"  not shortable {b['not_shortable'] or 'none'}; "
                   f"hard-to-borrow {b['hard_to_borrow'] or 'none'}")
        print()

    if (sec := head("PNL")) is not None:
        _render_pnl(sec)
        print()

    if (sec := head("SPEC")) is not None:
        _p("spec_id", f"{sec['spec_id']}   ({sec['status']})")
        _p("vol_target_annual",
           "ABSENT from the frozen spec — the sleeve applies its own code "
           "default (src/deploy/sleeves/cef_discount.py _vol_target)"
           if sec["vol_target_absent"] else f"{sec['vol_target_annual']}")
        m = sec.get("sizing_multiplier")
        vt = sec.get("vol_target_annual")
        _p("sizing_multiplier",
           "absent (the account holds the unit book: today's sizing)" if m is None else
           f"{m}   effective vol target {vt} x {m} = "
           + (f"{float(vt) * float(m):.4f}" if isinstance(vt, (int, float)) else "UNMEASURED (no vol target)")
           + "   (CEF trial 53)")
        # CEF trial 55 (te4): the thin-session rule, and its floor only where one is written.
        # ABSENT is said as absent, with what the registry reads it as, never as a value.
        rule, floor = sec.get("below_min_names"), sec.get("below_min_names_floor")
        _p("below_min_names",
           ("absent (read as 'flatten': FLAT under min_names eligible names)"
            if sec.get("below_min_names_absent") else str(rule))
           + (f"   floor {floor}" if floor is not None else "")
           + ("   PAPER ONLY (CEF trial 55)" if rule == "trade_eligible" else ""))
        _p("band_width", f"{sec['band_width']}   "
                         f"z_window {sec['z_window']}   "
                         f"{sec['n_universe']} names   {sec['order_type']}")
        _p("rebalance_days", f"{sec['rebalance_days']}"
           + ("   INERT while band_width is set" if sec["rebalance_days_inert"]
              else ""))
        _p("capital / min trade", f"${sec['capital_usd']:,.0f}  /  "
                                  f"${sec['min_trade_usd']}")
        print()

    if (sec := head("TRIALS")) is not None:
        for name, c in sec["counters"].items():
            _p(f"{name}  [doc]", f"{c['trials']} trials   "
               + (f"deflated-Sharpe bar sqrt(2 ln N) = {c['dsr_bar']}"
                  if c["dsr_bar"] else "no bar at N<=1"))
        _p("", f"source: {sec['source']}")
        print()

    if (sec := head("PANELS")) is not None:
        for name, p in sec["panels"].items():
            if p.get("error"):
                _p(name, f"UNMEASURED — {p['error']}")
            else:
                age = p.get("trading_days_old")
                _p(name, f"last {p['last']}"
                         + (f"   ({age} trading day(s) old)" if age is not None
                            else ""))
        print()

    sec = s.get("HYGIENE") or {}
    if "UNMEASURED" in sec:
        print(f"HYGIENE\n  UNMEASURED — {sec['UNMEASURED']}\n")
    else:
        print("HYGIENE")
        for k, c in (sec.get("checks") or {}).items():
            _p(k, f"{c.get('count')}")
            _p("", f"  {c['reproducer']}")
        print()

    if (sec := head("DOC DRIFT")) is not None:
        _p("doc-audit DRIFT", str(sec.get("doc_audit_drift")))
        for row in sec.get("doc_audit_rows") or []:
            _p("", f"  {row[:96]}")
        print()

    print("Read CLAUDE.md for the RULES. Read this for the FIGURES.\n"
          "Anything you are about to quote that is not above: re-measure it, "
          "or state it as a gap.\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-tests", action="store_true",
                    help="skip the pytest collection count")
    a = ap.parse_args(argv)
    d = collect(run_tests=not a.no_tests)
    if a.json:
        json.dump(d, sys.stdout, indent=2, default=str)
        print()
    else:
        render(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
