"""The snapshot format (0.3: every book on one page, aggregates only) and its checks.

Standard library only, on purpose: the dashboard imports nothing that can open a
connection (dashboard/README.md section 1).

A snapshot is one JSON object, written on the VM by `dashboard/export.py` from the
records the runners have already written. Every section is a READING, the same
three-key convention as ops/prod_state.py, so a renderer can never print a gap as if it
were a value. A reading has exactly one of:

    {"value": v, "source": "...", "read_at": "<ISO UTC>", "label": "broker-confirmed" | "modelled" | "simulated"}
    {"absent": "why the thing does not exist"}
    {"UNMEASURED": "what was tried"}

WHY 0.2 (team lead, 2026-11-23: "showing analytics for all our active books", served from
the VM as a public site). 0.1-draft (Lucy, PR #62) described one book from one night's
reconcile.json. The desk now runs three paper accounts whose runners write different
records (the core and C4 write reconcile.json and eod_equity.csv; the events book writes
verify.json and sleeve_scores.csv), plus the simulated shadow books. 0.2 keeps 0.1's
reading convention and its privacy check unchanged and replaces the single-book body with
a list of books.

WHY 0.3 (team lead, 2026-11-23, "aggregates only"): 0.2 carried each session's positions and
orders by symbol and the runners' note text, and the event book's notes put 173 client order ids
on the public page. A session is now counts and dollar exposure only: positions (long, short,
unpriced, gross and net), orders (filled in full, partly, not at all) and the number of notes.
The risk reading keeps the largest position's share of equity without its name. No symbol, share
count, order line or note text is in a snapshot, and find_private refuses one that has any.

`validate` checks the shape. `find_private` checks what a snapshot may never carry
(dashboard/README.md section 2). Both return a list of problems; empty means clean.
Neither raises on bad data, so a test can show every problem.
"""
from __future__ import annotations

import re

SCHEMA_VERSION = "0.3"
LABELS = ("broker-confirmed", "modelled", "simulated")
UNMEASURED = "UNMEASURED"

TOP_KEYS = ("schema_version", "synthetic", "exported_at_utc", "books", "shadow")
BOOK_KEYS = ("name", "title", "official", "session", "risk", "execution", "sleeves")
SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,6}$")
BOOK_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def _is_count(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float("inf")


def _opt_num(x) -> bool:
    return x is None or _num(x)


def _rows(v, where, out, need: dict) -> None:
    """A list of dicts; `need` maps key -> checker."""
    if not isinstance(v, list):
        out.append(f"{where}: must be a list")
        return
    for i, r in enumerate(v):
        if not isinstance(r, dict):
            out.append(f"{where}[{i}]: must be an object")
            continue
        for k, ok in need.items():
            if not ok(r.get(k)):
                out.append(f"{where}[{i}].{k}: bad value {r.get(k)!r}")


_is_date = lambda x: isinstance(x, str) and bool(DATE.match(x))           # noqa: E731
_is_sym = lambda x: isinstance(x, str) and bool(SYMBOL.match(x))          # noqa: E731
_is_str = lambda x: isinstance(x, str)                                    # noqa: E731
_is_side = lambda x: x in ("buy", "sell")                                 # noqa: E731


def _check_value(kind: str, v, where: str, out: list) -> None:
    if not isinstance(v, dict):
        out.append(f"{where}: value must be an object")
        return
    if kind == "official":
        _rows(v.get("rows"), f"{where}.rows", out, {"date": _is_date, "equity": _num, "change_usd": _opt_num})
        if isinstance(v.get("rows"), list) and not v["rows"]:
            out.append(f"{where}.rows: an official reading needs at least one row (else write it as absent)")
    elif kind == "session":
        if not _is_date(v.get("date")):
            out.append(f"{where}.date: must be YYYY-MM-DD")
        if v.get("first_send") is not None and not _is_date(v.get("first_send")):
            out.append(f"{where}.first_send: must be YYYY-MM-DD or null")
        if v.get("verdict") not in ("PASS", "FAIL"):
            out.append(f"{where}.verdict: must be PASS or FAIL")
        if not _is_count(v.get("n_notes")):
            out.append(f"{where}.n_notes: must be a count")
        pos = v.get("positions")
        if not isinstance(pos, dict) or not all(_is_count(pos.get(k)) for k in ("n", "n_long", "n_short", "n_unpriced")) \
                or not all(_num(pos.get(k)) for k in ("gross_usd", "net_usd")) \
                or not all(_opt_num(pos.get(k)) for k in ("gross_x", "net_x")):
            out.append(f"{where}.positions: needs counts n, n_long, n_short, n_unpriced, gross_usd and net_usd")
        o = v.get("orders")
        if not isinstance(o, dict) or not all(_is_count(o.get(k)) for k in ("n", "n_filled", "n_partial", "n_unfilled")) \
                or not _opt_num(o.get("fill_rate_shares")):
            out.append(f"{where}.orders: needs counts n, n_filled, n_partial, n_unfilled")
        snap = v.get("equity_snapshot")
        if snap is not None and not (isinstance(snap, dict) and _num(snap.get("equity"))
                                     and _opt_num(snap.get("change_usd"))):
            out.append(f"{where}.equity_snapshot: needs a numeric equity and change_usd")
    elif kind == "risk":
        if v.get("severity") not in ("OK", "INFO", "WATCH", "ACT", "UNMEASURED"):
            out.append(f"{where}.severity: unexpected {v.get('severity')!r}")
        for k in ("gross", "net", "cap"):
            if not _opt_num(v.get(k)):
                out.append(f"{where}.{k}: must be a number or null")
        if not _is_date(v.get("asof")):
            out.append(f"{where}.asof: must be YYYY-MM-DD")
    elif kind == "execution":
        _rows(v.get("rows"), f"{where}.rows", out, {"date": _is_date, "n_orders": _num, "n_full": _num,
                                                    "fill_rate": _opt_num, "slip_bp": _opt_num})
    elif kind == "sleeves":
        _rows(v.get("rows"), f"{where}.rows", out, {"slug": _is_str, "date": _is_date, "pnl": _opt_num,
                                                    "day_change": _opt_num, "n_names": _num,
                                                    "capital_usd": _opt_num})
    elif kind == "shadow":
        _rows(v.get("rows"), f"{where}.rows", out, {"book": _is_str, "started": _is_date, "scored": _num,
                                                    "flat": _num, "pnl_total": _opt_num})


def _check_reading(r, kind: str, where: str, out: list) -> None:
    if not isinstance(r, dict):
        out.append(f"{where}: a reading must be an object")
        return
    keys = [k for k in ("value", "absent", UNMEASURED) if k in r]
    if len(keys) != 1:
        out.append(f"{where}: a reading has exactly one of value / absent / {UNMEASURED}, found {keys or 'none'}")
        return
    k = keys[0]
    if k in ("absent", UNMEASURED):
        if not (isinstance(r[k], str) and r[k].strip()):
            out.append(f"{where}: {k} must say why")
        return
    if not (isinstance(r.get("source"), str) and r["source"].strip()):
        out.append(f"{where}: a measured value names its source")
    if not (isinstance(r.get("read_at"), str) and ISO_UTC.match(r["read_at"])):
        out.append(f"{where}: a measured value carries read_at as ISO UTC (YYYY-MM-DDTHH:MM:SSZ)")
    if r.get("label") not in LABELS:
        out.append(f"{where}: label must be one of {LABELS}")
    _check_value(kind, r["value"], where, out)


def validate(snap) -> list:
    out: list = []
    if not isinstance(snap, dict):
        return ["snapshot must be a JSON object"]
    for k in TOP_KEYS:
        if k not in snap:
            out.append(f"missing top-level key {k!r}")
    if snap.get("schema_version") != SCHEMA_VERSION:
        out.append(f"schema_version must be {SCHEMA_VERSION!r}, got {snap.get('schema_version')!r}")
    if not isinstance(snap.get("synthetic"), bool):
        out.append("synthetic must be true or false")
    if "exported_at_utc" in snap and not ISO_UTC.match(str(snap["exported_at_utc"])):
        out.append("exported_at_utc must be ISO UTC (YYYY-MM-DDTHH:MM:SSZ)")
    books = snap.get("books")
    if not isinstance(books, list) or not books:
        out.append("books must be a non-empty list")
        books = []
    seen = set()
    for i, b in enumerate(books):
        where = f"books[{i}]"
        if not isinstance(b, dict):
            out.append(f"{where}: must be an object")
            continue
        for k in BOOK_KEYS:
            if k not in b:
                out.append(f"{where}: missing {k!r}")
        if not (isinstance(b.get("name"), str) and BOOK_NAME.match(b["name"])):
            out.append(f"{where}.name: lower-case identifier required")
        elif b["name"] in seen:
            out.append(f"{where}.name: duplicate book {b['name']!r}")
        seen.add(b.get("name"))
        if not (isinstance(b.get("title"), str) and b["title"].strip()):
            out.append(f"{where}.title: required")
        for k in ("official", "session", "risk", "execution", "sleeves"):
            if k in b:
                _check_reading(b[k], k, f"{where}.{k}", out)
    if "shadow" in snap:
        _check_reading(snap["shadow"], "shadow", "shadow", out)
    return out


# ---------------------------------------------------------------- privacy --
# dashboard/README.md section 2. Key names that never appear, wherever they nest.
FORBIDDEN_KEYS = re.compile(
    r"(api[_-]?key|secret|token|passw|credential|key[_-]?id|account[_-]?(number|id|no)|"
    r"cusip|permno|isin|sedol|crsp|trace|compustat|host(name)?|server|vm[_-]?(addr|ip|name)|"
    r"vault|subscription|endpoint|bucket|client[_-]?order[_-]?id|order[_-]?id|\bssh\b)", re.I)
# Per-name fields (team lead, 2026-11-23: the public site shows aggregates only). A key with one of
# these names anywhere in a snapshot means a per-name row got through.
PER_NAME_KEYS = frozenset({"symbol", "symbols", "qty", "shares", "positions_after", "fills_by_symbol", "marks",
                           "problems", "fails", "notes", "reason", "orders_by_symbol"})
# Value patterns that never appear in any string.
FORBIDDEN_VALUES = {
    "IPv4 address": re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    "IPv6 address": re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}\b"),
    "long hex string (looks like a key or hash)": re.compile(r"\b[0-9a-fA-F]{32,}\b"),
    "UUID (looks like an order or account id)": re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    "Alpaca key id": re.compile(r"\b(?:PK|AK|CK)[A-Z0-9]{16,}\b"),
    "Alpaca account number": re.compile(r"\bPA[0-9A-Z]{8,}\b"),
    "cloud hostname": re.compile(r"\b[\w-]+\.(?:cloudapp\.azure\.com|azure\.com|cloudflarestorage\.com|compute\.amazonaws\.com)\b", re.I),
    "URL": re.compile(r"https?://", re.I),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "email address": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "home directory path": re.compile(r"/home/[\w.-]+"),
    "client order id": re.compile(r"\b[a-z][a-z0-9_]*-\d{8}-[A-Z][A-Z0-9.]*-\d+\b"),
}


def find_private(node, path: str = "$") -> list:
    """Every place a snapshot carries something the README forbids."""
    out: list = []
    if isinstance(node, dict):
        for k, v in node.items():
            if FORBIDDEN_KEYS.search(str(k)):
                out.append(f"{path}.{k}: forbidden key name")
            elif str(k) in PER_NAME_KEYS:
                out.append(f"{path}.{k}: a per-name or note field (the site shows aggregates only)")
            out.extend(find_private(v, f"{path}.{k}"))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.extend(find_private(v, f"{path}[{i}]"))
    elif isinstance(node, str):
        for what, rx in FORBIDDEN_VALUES.items():
            if rx.search(node):
                out.append(f"{path}: contains a {what}")
    return out
