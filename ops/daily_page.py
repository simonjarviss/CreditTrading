"""One page a morning for every paper account: official P&L, drawdown, exposure, and what could not be measured.

    python3 -m ops.daily_page            # reads the VM over one ssh call, prints the page
    python3 -m ops.daily_page --json     # the same readings as JSON

WHY (team lead, 2026-11-18: "Runner PR, then report"; 2026-11-19: "P&L and risk by book, one
page"). The desk runs two armed paper accounts (core `cef`, `c4`) and a set of simulated shadow
books, and nothing reads them together. Each book has its own nightly risk report on the VM
(scripts/ops/risk_daily.py), but the question "what did the desk make, how far is each book
from its own stop, and is anything unmeasured" took four files and two logins. This page is
those files side by side, plus the one figure no single report has: the accounts summed.

READ ONLY, AND IT MEASURES NOTHING NEW. It reads, over ONE ssh call to the alias `quantt-vm`
(ops/prod_state.py's rule: the address lives in ~/.ssh/config and nowhere in this
repository), files the VM already writes:
  * `<state>/<book>/eod_equity.csv`: Alpaca's end-of-day equity history, the P&L of record
    (team lead, 2026-10-19), written by the collector;
  * `<state>/<book>/reports/risk/<newest>.json`: that book's risk report, block by block;
  * the shadow runner's `SCOREBOARD.md` (simulated books; every figure there is SIMULATED).
It makes no broker call, holds no key, and no code path from here sends, changes or cancels
an order (CLAUDE.md: any monitor is read-only). It prints no position list: only equity,
counts, and the risk report's own summary lines, which may name a book's largest holding.

NO FALLBACKS. A file that cannot be read is UNMEASURED and named, for that book only. The
combined line is printed only over the sessions BOTH accounts have an official row for, and
says how many; a book whose newest official row is older than the other's is named, never
padded with its last value. Nothing is carried forward or filled.

WHAT "COMBINED" MEANS. The sum of the accounts' official equity on each common session, and
its change. The accounts are separate paper accounts with separate limits; there is no
combined risk budget (team lead, 2026-11-18: "No combined budget yet"), so the combined
drawdown is shown for information and judged against nothing.

Each book's HALVE and KILL lines, its gross cap and its severity are read from its own risk
report (which reads them from the book's own files): this module holds no limit of its own
and never writes a literal for one (CLAUDE.md, the frozen spec is the only authority).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import sys
from pathlib import Path

from ops import prod_state as ps

BOOKS = ("cef", "c4")
STATE_ROOT = "/home/quantt/quantt_state"
SHADOW_SCOREBOARD = "/home/quantt-shadow/shadow_state/SCOREBOARD.md"
EOD_COLUMNS = ("date", "equity", "change_usd", "read_at_utc")
TIMEOUT_S = 20
BEGIN, END, MISSING, DONE = "@@BEGIN ", "@@END ", "@@MISSING ", "@@DONE"

# One fixed, read-only script. `sudo cat` only: the state directories are another user's
# (mode 700). A file that is not there prints a MISSING line, never an empty section.
REMOTE_SCRIPT = "\n".join(
    [f"""emit() {{ if sudo test -r "$2"; then echo "{BEGIN}$1"; sudo cat "$2"; echo; echo "{END}$1"; else echo "{MISSING}$1 $2"; fi; }}"""]
    + [f"""emit eod_{b} {STATE_ROOT}/{b}/eod_equity.csv
r=$(sudo ls -1 {STATE_ROOT}/{b}/reports/risk 2>/dev/null | grep '\\.json$' | sort | tail -1)
if [ -n "$r" ]; then emit risk_{b} {STATE_ROOT}/{b}/reports/risk/$r; else echo "{MISSING}risk_{b} {STATE_ROOT}/{b}/reports/risk/*.json"; fi"""
       for b in BOOKS]
    + [f"emit shadow {SHADOW_SCOREBOARD}", f"echo {DONE}", ""])


class PageError(RuntimeError):
    """The VM could not be read at all. Per-file gaps are not errors: they are UNMEASURED."""


def fetch(run=None, alias: str = ps.VM_ALIAS, timeout: float = TIMEOUT_S) -> str:
    """The remote script's raw reply. Refuses under the test network guard unless a fake
    `run` is passed (ssh is a child process, so the guard cannot see it; prod_state.vm)."""
    if run is None:
        from ops import netguard
        if netguard.is_active():
            raise PageError("netguard is active in this process (a test run): no ssh to the VM; pass a fake `run`")
    run = run or subprocess.run
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={ps.SSH_CONNECT_TIMEOUT_S}", alias, "sh -s"]
    try:
        r = run(cmd, capture_output=True, text=True, timeout=timeout, input=REMOTE_SCRIPT)
    except subprocess.TimeoutExpired:
        raise PageError(f"ssh {alias} did not finish within {timeout}s") from None
    except OSError as e:
        raise PageError(f"ssh {alias}: {type(e).__name__}: {e}") from None
    if r.returncode == 255:
        raise PageError(f"ssh {alias} failed (exit 255): {ps.scrub(r.stderr)}")
    if DONE not in r.stdout.splitlines():
        raise PageError(f"ssh {alias} exited {r.returncode} and its reply was cut short (no {DONE} line): {ps.scrub(r.stderr)}")
    return r.stdout


def sections(raw: str) -> tuple:
    """({name: text}, {name: path that was missing}) from the remote reply."""
    got, missing, name, buf = {}, {}, None, []
    for line in raw.splitlines():
        if name is None:
            if line.startswith(BEGIN):
                name, buf = line[len(BEGIN):].strip(), []
            elif line.startswith(MISSING):
                n, _, path = line[len(MISSING):].partition(" ")
                missing[n] = path
        elif line == END + name:
            got[name] = "\n".join(buf).strip("\n")
            name = None
        else:
            buf.append(line)
    if name is not None:
        raise PageError(f"the reply's section {name!r} has no end line")
    return got, missing


def eod_rows(text: str, where: str) -> list:
    """[(date, equity, change or None)] in file order, or raise ValueError naming the line.
    The header must be the collector's, and no cell is defaulted: an empty change (the
    first funded row) stays None."""
    rd = csv.DictReader(io.StringIO(text))
    if tuple(rd.fieldnames or ()) != EOD_COLUMNS:
        raise ValueError(f"{where}: header {rd.fieldnames} is not {list(EOD_COLUMNS)}")
    out = []
    for n, r in enumerate(rd, start=2):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"] or ""):
            raise ValueError(f"{where} line {n}: date {r['date']!r}")
        try:
            out.append((r["date"], float(r["equity"]), float(r["change_usd"]) if r["change_usd"] not in ("", None) else None))
        except (TypeError, ValueError):
            raise ValueError(f"{where} line {n}: equity {r['equity']!r} or change {r['change_usd']!r} is not a number") from None
    if not out:
        raise ValueError(f"{where}: no rows")
    if [d for d, _, _ in out] != sorted({d for d, _, _ in out}):
        raise ValueError(f"{where}: dates are not strictly increasing")
    return out


def drawdown(equity: list) -> tuple:
    """(high-water mark, its index, drawdown fraction of the last value from it)."""
    hwm = max(equity)
    return hwm, equity.index(hwm), (equity[-1] / hwm - 1.0)


def book_reading(book: str, got: dict, missing: dict) -> dict:
    """One account's block. Each of its two inputs is read or named as UNMEASURED."""
    out = {"book": book, "unmeasured": []}
    key = f"eod_{book}"
    if key in got:
        try:
            rows = eod_rows(got[key], f"{STATE_ROOT}/{book}/eod_equity.csv")
            eq = [e for _, e, _ in rows]
            hwm, i, dd = drawdown(eq)
            out["official"] = {"first": rows[0][0], "start_equity": eq[0], "last": rows[-1][0], "equity": eq[-1],
                               "day_change": rows[-1][2], "to_date": eq[-1] - eq[0], "sessions": len(rows) - 1,
                               "hwm": hwm, "hwm_date": rows[i][0], "drawdown": dd}
            out["_rows"] = rows
        except ValueError as e:
            out["unmeasured"].append(f"official P&L: {e}")
    else:
        out["unmeasured"].append(f"official P&L: {missing.get(key, key)} could not be read")
    key = f"risk_{book}"
    if key in got:
        try:
            rep = json.loads(got[key])
            blocks = rep["blocks"]
            out["risk"] = {"asof": rep["asof"], "generated_at": rep["generated_at"], "severity": rep["severity"],
                           "spec_id": rep.get("spec_id"), "act_lines": list(rep.get("act_lines") or []),
                           "status": {k: b["status"] for k, b in blocks.items()},
                           "lines": {k: [str(x).strip() for x in (blocks[k].get("lines") or [])]
                                     for k in ("drawdown", "exposure", "execution") if k in blocks}}
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            out["unmeasured"].append(f"risk report: {STATE_ROOT}/{book}/reports/risk/<newest>.json is not in the "
                                     f"expected form ({type(e).__name__}: {e})")
    else:
        out["unmeasured"].append(f"risk report: {missing.get(key, key)} could not be read")
    return out


def combined(books: list) -> dict:
    """The accounts summed over the sessions every measured account has an official row for."""
    have = [b for b in books if "_rows" in b]
    if len(have) < 2:
        return {"unmeasured": "fewer than two accounts have a readable official history"}
    common = sorted(set.intersection(*[{d for d, _, _ in b["_rows"]} for b in have]))
    if len(common) < 2:
        return {"unmeasured": "the accounts share fewer than two official sessions"}
    by = [{d: e for d, e, _ in b["_rows"]} for b in have]
    eq = [sum(m[d] for m in by) for d in common]
    hwm, i, dd = drawdown(eq)
    behind = [f"{b['book']} (newest official row {b['official']['last']})" for b in have if b["official"]["last"] != max(x["official"]["last"] for x in have)]
    return {"books": [b["book"] for b in have], "first": common[0], "last": common[-1], "sessions": len(common) - 1,
            "equity": eq[-1], "day_change": eq[-1] - eq[-2], "to_date": eq[-1] - eq[0], "start_equity": eq[0],
            "hwm": hwm, "hwm_date": common[i], "drawdown": dd, "behind": behind}


def shadow_table(text: str) -> dict:
    """The scoreboard's own date line and its first table, verbatim rows; nothing recomputed."""
    lines = text.splitlines()
    title = next((ln.strip("# ").strip() for ln in lines if ln.startswith("# ")), None)
    table = []
    for ln in lines:
        if ln.startswith("|"):
            table.append(ln)
        elif table:
            break
    if title is None or len(table) < 3:
        raise ValueError("SCOREBOARD.md has no title line or no table")
    head = [c.strip() for c in table[0].strip("|").split("|")]
    rows = [dict(zip(head, [c.strip() for c in r.strip("|").split("|")])) for r in table[2:]]
    need = {"book", "started", "scored", "flat", "unmeasured", "late decisions", "P&L total return"}
    if not need <= set(head):
        raise ValueError(f"SCOREBOARD.md's table lacks column(s) {sorted(need - set(head))}")
    return {"title": title, "rows": rows}


def build(raw: str) -> dict:
    got, missing = sections(raw)
    books = [book_reading(b, got, missing) for b in BOOKS]
    page = {"books": books, "combined": combined(books)}
    if "shadow" in got:
        try:
            page["shadow"] = shadow_table(got["shadow"])
        except ValueError as e:
            page["shadow"] = {"unmeasured": str(e)}
    else:
        page["shadow"] = {"unmeasured": f"{missing.get('shadow', SHADOW_SCOREBOARD)} could not be read"}
    for b in books:
        b.pop("_rows", None)
    return page


def _usd(x) -> str:
    return "UNMEASURED" if x is None else f"{x:+,.2f}"


def render(page: dict) -> str:
    out = ["# Desk page: every paper account", "",
           "Official figures are Alpaca's end-of-day history (the P&L of record), gross. Read only; nothing here "
           "touches an order. Shadow books are SIMULATED.", ""]
    c = page["combined"]
    out.append("## Combined")
    if "unmeasured" in c:
        out.append(f"- UNMEASURED: {c['unmeasured']}")
    else:
        out.append(f"- Accounts {' + '.join(c['books'])}, over the {c['sessions']} session(s) both have an official row for "
                   f"({c['first']} to {c['last']}): equity ${c['equity']:,.2f}, last session {_usd(c['day_change'])}, "
                   f"to date {_usd(c['to_date'])} on ${c['start_equity']:,.2f}")
        out.append(f"- Drawdown {c['drawdown']:.2%} from the high-water mark ${c['hwm']:,.2f} ({c['hwm_date']}); for information: "
                   "there is no combined risk budget (team lead, 2026-11-18)")
        for b in c["behind"]:
            out.append(f"- NOTE: {b} is behind the other account; the combined line stops at the last session both have")
    for b in page["books"]:
        out += ["", f"## {b['book']}"]
        o = b.get("official")
        if o:
            out.append(f"- Official: equity ${o['equity']:,.2f} at the {o['last']} close, that session {_usd(o['day_change'])}, "
                       f"to date {_usd(o['to_date'])} over {o['sessions']} session(s) since {o['first']}")
            out.append(f"- Drawdown {o['drawdown']:.2%} from the high-water mark ${o['hwm']:,.2f} ({o['hwm_date']})")
        r = b.get("risk")
        if r:
            out.append(f"- Risk report as-of {r['asof']} (written {r['generated_at']}, spec {r['spec_id']}): severity **{r['severity']}**")
            for ln in r["act_lines"]:
                out.append(f"- **ACT**: {ln}")
            for k in ("drawdown", "exposure", "execution"):
                for ln in r["lines"].get(k, [])[:2]:
                    out.append(f"  - {k}: {ln}")
            unm = sorted(k for k, s in r["status"].items() if s == "UNMEASURED")
            if unm:
                out.append(f"- Blocks the risk report could not measure: {', '.join(unm)} (its own file says why)")
            if o and r["asof"] != o["last"]:
                out.append(f"- NOTE: the risk report is as-of {r['asof']} and the newest official row is {o['last']}")
        for u in b["unmeasured"]:
            out.append(f"- UNMEASURED: {u}")
    s = page["shadow"]
    out += ["", "## Shadow books (simulated)"]
    if "unmeasured" in s:
        out.append(f"- UNMEASURED: {s['unmeasured']}")
    else:
        out.append(f"- {s['title']}: {len(s['rows'])} book(s)")
        out += ["", "| book | started | scored | flat | unmeasured | late | simulated P&L (total return) |", "|---|---|---:|---:|---:|---:|---:|"]
        for r in s["rows"]:
            out.append(f"| {r['book']} | {r['started']} | {r['scored']} | {r['flat']} | {r['unmeasured']} | "
                       f"{r['late decisions']} | {r['P&L total return']} |")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        page = build(fetch())
    except PageError as e:
        print(f"UNMEASURED: the VM could not be read: {e}", file=sys.stderr)
        return 3
    print(json.dumps(page, indent=1) if a.json else render(page), end="" if not a.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
