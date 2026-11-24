"""The nightly exporter: the runners' own records in, one snapshot (dashboard/snapshot.py, 0.2) out.

    python3 -m dashboard.export --state-root /home/quantt/quantt_state \\
        --shadow-scoreboard /run/quantt-site/SCOREBOARD.md -o snapshot.json

WHY (team lead, 2026-11-23): the public site shows every active book's live record, and
the page must be built from what the runners have ALREADY recorded, never from a fresh
broker call. A page that could reach the broker could, through a bug, do more than read.

READ ONLY, NO NETWORK. It opens files under the state root and the copied shadow
scoreboard and nothing else. It imports only the standard library and
`dashboard.snapshot`. On the VM its unit runs with PrivateNetwork=yes and the state
directories mounted read-only (dashboard/deploy/install_site_vm.sh), so a bug here cannot
send an order, change a record or reach anything outside the machine.

WHAT EACH BOOK'S RECORDS ARE (read by header name, never by position):
  * core `cef` and `c4` (quantt/session): `eod_equity.csv` is Alpaca's end-of-day equity
    history, the P&L of record (team lead, 2026-10-19). The newest day directory with a
    `reconcile.json` is the last verified session: its verdict, notes, orders, positions
    after the close and the official closing prints, which are reduced to counts and dollar
    exposure here (AGGREGATES ONLY, below). `tca.csv` is fill quality.
    `reports/risk/<date>.json` is the nightly risk report (scripts/ops/risk_daily.py).
  * the event book `events` (quantt/sleeves): the newest day directory with a
    `verify.json`, and `sleeve_scores.csv`, the per-strategy P&L booked by its ledger.
    It has no collector yet, so no end-of-day history: its official reading is absent until
    an `eod_equity.csv` appears, and the session's after-close equity snapshot is shown,
    labelled as a snapshot.
  * the shadow books: the shadow runner's SCOREBOARD.md. Every figure there is SIMULATED.

NO FALLBACKS (CLAUDE.md). A file that is missing or does not parse becomes
{"UNMEASURED": "<what was tried>"} for that section only. Nothing is carried forward,
zero-filled or taken from another file. Error text is scrubbed of paths and order ids
before it is written, because what the snapshot holds is published.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from dashboard import metrics as M, snapshot as S

# (state directory name, title on the site, runner kind). The titles are the names the
# team lead approved for the investor deck (2026-11-22).
BOOKS = (("cef", "Fixed Income Book", "session"),
         ("c4", "Equity Cross-Asset Book", "session"),
         ("events", "Event Book", "sleeves"))
DAY_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OFFICIAL_SOURCE = "Alpaca end-of-day portfolio history, {book}/eod_equity.csv (the P&L of record)"


class Unreadable(Exception):
    """A record could not be read or parsed. Its message is written as UNMEASURED."""


def utc_z(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_to_z(s: str) -> str:
    """'2026-11-21T08:40:04+00:00' or '...-05:00' -> '2026-11-21T08:40:04Z'. Raises Unreadable."""
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError as e:
        raise Unreadable(f"read time {s!r} is not ISO 8601") from e
    if t.tzinfo is None:
        raise Unreadable(f"read time {s!r} carries no time zone")
    return utc_z(t)


def mtime_z(p: Path) -> str:
    return utc_z(dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc))


_PATH = re.compile(r"/(?:home|run|srv|tmp|etc|var)/[^\s'\"),;]*")


# A client order id, `<book>-<YYYYMMDD>-<SYMBOL>-<leg>` (quantt/session/decide.py client_order_id).
# WHY (2026-11-23): the event book's first armed send failed with 173 rejections, and its verify
# note lists every rejected id; the note reached the public page through `problems`. The README
# forbids order ids on the site, so they are taken out of any text here, a quoted list of them
# collapses to one phrase, and snapshot.find_private refuses a snapshot that still carries one.
_ORDER_ID = re.compile(r"\b[a-z][a-z0-9_]*-\d{8}-[A-Z][A-Z0-9.]*-\d+\b")
_ORDER_ID_LIST = re.compile(r"\[\s*(?:'<order id>'\s*,?\s*)+\]")


def scrub(text: str) -> str:
    """Paths and order ids out of any text that came from a record or an exception (the page is public)."""
    s = _ORDER_ID.sub("<order id>", _PATH.sub("<path>", str(text)))
    return _ORDER_ID_LIST.sub("(order ids withheld)", s)


def reading(value, source: str, read_at: str, label: str) -> dict:
    return {"value": value, "source": source, "read_at": read_at, "label": label}


def unmeasured(what: str) -> dict:
    return {S.UNMEASURED: scrub(what)}


def absent(why: str) -> dict:
    return {"absent": why}


def _float(x, what: str):
    """A number, None for an empty cell, Unreadable for anything else."""
    if x is None or str(x).strip() == "":
        return None
    try:
        v = float(x)
    except (TypeError, ValueError) as e:
        raise Unreadable(f"{what}: {x!r} is not a number") from e
    if v != v or v in (float("inf"), float("-inf")):
        raise Unreadable(f"{what}: {x!r} is not finite")
    return v


def _required(x, what: str) -> float:
    v = _float(x, what)
    if v is None:
        raise Unreadable(f"{what} is empty")
    return v


def read_csv(p: Path, need: tuple) -> list:
    if not p.is_file():
        raise FileNotFoundError(p)
    with p.open(newline="") as f:
        r = csv.DictReader(f)
        missing = [c for c in need if c not in (r.fieldnames or [])]
        if missing:
            raise Unreadable(f"{p.name} has no column(s) {missing}")
        return list(r)


def read_json(p: Path):
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise Unreadable(f"{p.name} is not valid JSON ({e.msg})") from e


def oldest_day_with(book_dir: Path, name: str):
    """The oldest YYYY-MM-DD directory holding `name`, or None."""
    days = sorted(d for d in book_dir.iterdir() if d.is_dir() and DAY_DIR.match(d.name))
    for d in days:
        if (d / name).is_file():
            return d
    return None


def newest_day_with(book_dir: Path, name: str):
    """The newest YYYY-MM-DD directory holding `name` (a plan directory for a session that has
    not happened yet has no reconcile/verify file, so it is skipped, not read)."""
    days = sorted((d for d in book_dir.iterdir() if d.is_dir() and DAY_DIR.match(d.name)), reverse=True)
    for d in days:
        if (d / name).is_file():
            return d
    return None


# ------------------------------------------------------------------ sections --

def official(book: str, book_dir: Path) -> dict:
    p = book_dir / "eod_equity.csv"
    if not p.is_file():
        return absent("no end-of-day equity history is recorded for this account yet")
    try:
        rows = read_csv(p, ("date", "equity", "change_usd", "read_at_utc"))
        out, newest_read = [], None
        for i, r in enumerate(rows, start=2):
            if not DAY_DIR.match(r["date"] or ""):
                raise Unreadable(f"eod_equity.csv line {i}: date {r['date']!r}")
            eq = _float(r["equity"], f"eod_equity.csv line {i} equity")
            if eq is None:
                raise Unreadable(f"eod_equity.csv line {i}: empty equity")
            out.append({"date": r["date"], "equity": eq,
                        "change_usd": _float(r["change_usd"], f"eod_equity.csv line {i} change_usd")})
            if r["read_at_utc"]:
                t = iso_to_z(r["read_at_utc"])
                newest_read = max(newest_read or t, t)
        if not out:
            return absent("eod_equity.csv has no rows yet")
        dates = [r["date"] for r in out]
        if dates != sorted(dates) or len(set(dates)) != len(dates):
            raise Unreadable("eod_equity.csv dates are not strictly increasing")
        try:                        # what the page computes must be computable: a defect is this book's gap,
            M.summary(out)          # never a failed build of the whole site (release-check review, 2026-11-23)
        except ValueError as e:
            raise Unreadable(f"eod_equity.csv: {e}") from e
        return reading({"rows": out}, OFFICIAL_SOURCE.format(book=book), newest_read or mtime_z(p),
                       "broker-confirmed")
    except (Unreadable, OSError) as e:
        return unmeasured(f"{book}/eod_equity.csv: {e}")


def _verdict(text: str, date: str):
    """'2026-11-20 PASS cef traded 13 order(s), ...' -> ('PASS', 'cef traded 13 order(s), ...')."""
    m = re.match(r"^\s*(\d{4}-\d{2}-\d{2})\s+(PASS|FAIL)\s+(.*)$", str(text), re.S)
    if not m or m.group(1) != date:
        raise Unreadable(f"verdict line does not read '<{date}> PASS|FAIL ...'")
    return m.group(2), m.group(3).strip()


# AGGREGATES ONLY (team lead, 2026-11-23, after the release check found order ids on the page): the
# public site shows no symbol, share count, order line or note text from the trading system. Each
# session is reduced HERE, so the snapshot never holds a per-name figure for any later code to print:
# counts of positions and orders, dollar exposure, the verdict word and how many notes the record
# has. The per-name rows stay on the VM, in the runners' own records (the report rule: "aggregates
# in the repository, rows private"). Error texts below never name a symbol either, because an
# UNMEASURED reading's text is published.

def _positions_summary(holdings: list, equity) -> dict:
    """holdings: (qty, close or None) per name, from the record. Gross and net are measured only when
    every held name has a close: with any name unpriced they are None and n_unpriced says how many,
    because a sum over part of the book would read as the whole book (release-check review,
    2026-11-23: with every close missing, a fully invested book showed 0.00x)."""
    held = [(q, c) for q, c in holdings if q]
    unpriced = sum(1 for _, c in held if c is None)
    gross = None if unpriced else sum(abs(q * c) for q, c in held)
    net = None if unpriced else sum(q * c for q, c in held)
    eq = equity if equity else None
    return {"n": len(held), "n_long": sum(1 for q, _ in held if q > 0), "n_short": sum(1 for q, _ in held if q < 0),
            "n_unpriced": unpriced, "gross_usd": gross, "net_usd": net,
            "gross_x": None if eq is None or gross is None else gross / eq,
            "net_x": None if eq is None or net is None else net / eq}


def _orders_summary(rows: list) -> dict:
    """Counts only: filled in full, partly, or not at all; shares filled over shares ordered."""
    n_full = n_part = n_none = 0
    ordered = filled = 0.0
    for r in rows:
        q = _float(r.get("qty"), "an order's quantity")
        f = _float(r.get("filled_qty"), "an order's filled quantity") or 0.0
        if q is None:
            raise Unreadable("an order has no quantity")
        ordered += abs(q)
        filled += abs(f)
        if abs(f) >= abs(q):
            n_full += 1
        elif f:
            n_part += 1
        else:
            n_none += 1
    return {"n": len(rows), "n_filled": n_full, "n_partial": n_part, "n_unfilled": n_none,
            "fill_rate_shares": (filled / ordered) if ordered else None}


def session_core(book: str, book_dir: Path) -> dict:
    day = newest_day_with(book_dir, "reconcile.json")
    if day is None:
        return absent("no verified session is recorded yet")
    p = day / "reconcile.json"
    try:
        r = read_json(p)
        verdict, reason = _verdict(r.get("verdict", ""), day.name)
        # A core FAIL's items are `problems` plus the score's unmeasured items, which verify writes
        # only into the verdict line, as "UNMEASURED <item>" before " | " (quantt/session/verify.py,
        # `fails`). Both are counted, as the event book counts problems and fails.
        n_unmeasured = reason.rsplit(" | ", 1)[0].count("UNMEASURED ") if " | " in reason else 0
        prints = (r.get("auction_prints_d") or {}).get("prices") or {}
        snap = r.get("snapshot") or {}
        equity = _float(snap.get("equity"), "the snapshot's equity")
        holdings = [(_float(q, "a position's quantity"), _float(prints.get(s), "a position's close"))
                    for s, q in (r.get("positions_after") or {}).items()]
        value = {"date": day.name, "verdict": verdict, "n_notes": len(r.get("problems") or []) + n_unmeasured,
                 "positions": _positions_summary(holdings, equity),
                 "close_basis": "official closing print (primary exchange)",
                 "orders": _orders_summary(r.get("orders") or []),
                 "equity_snapshot": None if equity is None else {
                     "equity": equity, "change_usd": _float(snap.get("change_usd"), "the snapshot's change"),
                     "kind": "account snapshot after the close (not the P&L of record)"}}
        read_at = iso_to_z(r["read_at"]) if r.get("read_at") else mtime_z(p)
        return reading(value, f"{book}/{day.name}/reconcile.json (written by the session's verify)", read_at,
                       "broker-confirmed")
    except (Unreadable, OSError, AttributeError, TypeError) as e:
        return unmeasured(f"{book}/{day.name}/reconcile.json: {e}")


def session_sleeves(book: str, book_dir: Path) -> dict:
    day = newest_day_with(book_dir, "verify.json")
    if day is None:
        return absent("no verified session is recorded yet")
    p = day / "verify.json"
    try:
        r = read_json(p)
        if r.get("session_date") != day.name:
            raise Unreadable(f"session_date {r.get('session_date')!r} is not its directory's date")
        marks = r.get("marks") or {}
        eq = r.get("equity") or {}
        equity = _float(eq.get("equity"), "the account's equity")
        holdings = [(_float(q, "a position's quantity"), _float(marks.get(s), "a position's close"))
                    for s, q in (r.get("positions_after") or {}).items()]
        # The first session that sent an order: the oldest day with STARTED, which the runner writes
        # before its first order (CLAUDE.md order-path rule 2). A dry-run day has a verify.json and no
        # STARTED, so the book's start is never dated by a session that sent nothing (release-check
        # review, 2026-11-23: "Trading since" used to print the newest session's date).
        first = oldest_day_with(book_dir, "STARTED")
        value = {"date": day.name, "first_send": first.name if first else None,
                 "verdict": "PASS" if r.get("ok") else "FAIL",
                 "n_notes": len((r.get("problems") or []) + (r.get("fails") or [])),
                 "positions": _positions_summary(holdings, equity),
                 "close_basis": "daily bar close (consolidated feed)",
                 "orders": _orders_summary(r.get("orders") or []),
                 "equity_snapshot": None if equity is None else {
                     "equity": equity, "change_usd": _float(eq.get("change_usd"), "the account's change"),
                     "kind": "account snapshot at verify (not the P&L of record)"}}
        read_at = iso_to_z(r["read_at"]) if r.get("read_at") else mtime_z(p)
        return reading(value, f"{book}/{day.name}/verify.json (written by the event book's verify)", read_at,
                       "broker-confirmed")
    except (Unreadable, OSError, AttributeError, TypeError) as e:
        return unmeasured(f"{book}/{day.name}/verify.json: {e}")


def risk(book: str, book_dir: Path) -> dict:
    d = book_dir / "reports" / "risk"
    files = sorted(d.glob("*.json")) if d.is_dir() else []
    if not files:
        return absent("no nightly risk report is scheduled for this book")
    p = files[-1]
    try:
        r = read_json(p)
        ex = ((r.get("blocks") or {}).get("exposure") or {}).get("data") or {}
        dd = ((r.get("blocks") or {}).get("drawdown") or {}).get("data") or {}
        conc = ex.get("concentration") or {}
        largest = conc.get("largest") or {}
        levels = dd.get("levels") or {}
        value = {"asof": r.get("asof"), "severity": r.get("severity"),
                 "gross": _float(ex.get("gross"), "gross"), "net": _float(ex.get("net"), "net"),
                 "cap": _float(ex.get("cap"), "gross cap"),
                 # the largest position's share of equity, never its name (aggregates only, above)
                 "largest_share": None if not largest else _float(largest.get("share"), "largest share"),
                 "top3_share": _float(conc.get("top3_share"), "top-3 share"),
                 "groups": {str(k): _float(v, f"group {k}") for k, v in (conc.get("group_share") or {}).items()},
                 "halve_drawdown": _float(levels.get("halve"), "halve level"),
                 "kill_drawdown": _float(levels.get("kill"), "kill level")}
        gen = r.get("generated_at")
        return reading(value, f"{book}/reports/risk/{p.name} (nightly risk report, report only)",
                       iso_to_z(gen) if gen else mtime_z(p), "modelled")
    except (Unreadable, OSError, AttributeError, TypeError) as e:
        return unmeasured(f"{book}/reports/risk/{p.name}: {e}")


def execution(book: str, book_dir: Path) -> dict:
    p = book_dir / "tca.csv"
    if not p.is_file():
        return absent("no fill-quality record is kept for this book yet")
    try:
        rows = read_csv(p, ("date", "n_orders", "n_full", "fill_rate_shares", "slip_bp_all"))
        out = [{"date": r["date"], "n_orders": _float(r["n_orders"], "n_orders"),
                "n_full": _float(r["n_full"], "n_full"),
                "fill_rate": _float(r["fill_rate_shares"], "fill rate"),
                "slip_bp": _float(r["slip_bp_all"], "slippage")} for r in rows]
        if any(o["n_orders"] is None or o["n_full"] is None for o in out):
            raise Unreadable("a row has an empty order count")
        return reading({"rows": out, "basis": "fills against the primary exchange's official close, "
                                              "notional-weighted; + is worse"},
                       f"{book}/tca.csv", mtime_z(p), "broker-confirmed")
    except (Unreadable, OSError) as e:
        return unmeasured(f"{book}/tca.csv: {e}")


def sleeves(book: str, book_dir: Path, kind: str) -> dict:
    if kind != "sleeves":
        return absent("strategy-level scores are kept for the event book only")
    p = book_dir / "sleeve_scores.csv"
    if not p.is_file():
        return absent("no session has been scored yet")
    try:
        rows = read_csv(p, ("date", "slug", "pnl", "day_change", "n_names", "capital_usd"))
        out = [{"slug": r["slug"], "date": r["date"], "pnl": _float(r["pnl"], "pnl"),
                "day_change": _float(r["day_change"], "day_change"),
                "n_names": _required(r["n_names"], "n_names"),
                "capital_usd": _float(r["capital_usd"], "capital_usd")} for r in rows]
        return reading({"rows": out, "basis": "the book's ledger, marked at each session's daily bar close"},
                       f"{book}/sleeve_scores.csv", mtime_z(p), "broker-confirmed")
    except (Unreadable, OSError) as e:
        return unmeasured(f"{book}/sleeve_scores.csv: {e}")


def _num_cell(s: str):
    s = s.strip()
    if s in ("none", ""):
        return None
    return _float(s.replace(",", "").replace("%", "").replace("+", ""), f"scoreboard cell {s!r}")


def shadow(p: Path | None) -> dict:
    if p is None:
        return absent("no shadow scoreboard was given")
    if not p.is_file():
        return unmeasured(f"shadow scoreboard {p.name} not found")
    try:
        text = p.read_text()
        m = re.search(r"^# Shadow scoreboard\s+\S+\s+(\d{4}-\d{2}-\d{2})", text, re.M)
        if not m:
            raise Unreadable("no '# Shadow scoreboard - <date>' heading")
        lines = [ln for ln in text.splitlines() if ln.startswith("|")]
        if len(lines) < 2:
            raise Unreadable("no table")
        head = [c.strip() for c in lines[0].strip("|").split("|")]
        need = ("book", "started", "scored", "flat", "P&L total return", "max drawdown")
        if any(n not in head for n in need):
            raise Unreadable(f"table header lacks {[n for n in need if n not in head]}")
        rows = []
        for ln in lines[2:]:
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) != len(head):
                break                                   # the next table (correlations) starts
            c = dict(zip(head, cells))
            if not DAY_DIR.match(c["started"]):
                break
            dd = _num_cell(c["max drawdown"])
            rows.append({"book": c["book"], "started": c["started"], "scored": _required(c["scored"], "scored"),
                         "flat": _required(c["flat"], "flat"), "pnl_total": _num_cell(c["P&L total return"]),
                         "max_drawdown": None if dd is None else dd / 100.0})
        if not rows:
            raise Unreadable("the table has no rows")
        return reading({"asof": m.group(1), "rows": rows,
                        "basis": "decisions on live data, filled at the next official close by assumption, "
                                 "with no cost, borrow or fill risk"},
                       "shadow runner SCOREBOARD.md", mtime_z(p), "simulated")
    except (Unreadable, OSError) as e:
        return unmeasured(f"shadow scoreboard: {e}")


# ------------------------------------------------------------------- export --

def export(state_root: Path, scoreboard: Path | None, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    books = []
    for name, title, kind in BOOKS:
        d = state_root / name
        if not d.is_dir():
            miss = unmeasured(f"state directory {name}/ not found")
            books.append({"name": name, "title": title, "official": miss, "session": miss, "risk": miss,
                          "execution": miss, "sleeves": miss})
            continue
        books.append({"name": name, "title": title,
                      "official": official(name, d),
                      "session": session_core(name, d) if kind == "session" else session_sleeves(name, d),
                      "risk": risk(name, d),
                      "execution": execution(name, d),
                      "sleeves": sleeves(name, d, kind)})
    return {"schema_version": S.SCHEMA_VERSION, "synthetic": False, "exported_at_utc": utc_z(now),
            "books": books, "shadow": shadow(scoreboard)}


def check(snap: dict) -> list:
    return S.validate(snap) + S.find_private(snap)


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-root", type=Path, required=True)
    ap.add_argument("--shadow-scoreboard", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args(argv)
    snap = export(a.state_root, a.shadow_scoreboard)
    problems = check(snap)
    if problems:
        print("snapshot refused, nothing written:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2
    write_atomic(a.out, json.dumps(snap, indent=1, sort_keys=True))
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
