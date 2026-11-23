"""The snapshot format (DRAFT 0.1, awaiting the team lead's approval) and its checks.

Standard library only, on purpose: the dashboard imports nothing that can open a
connection (dashboard/README.md section 1).

A snapshot is one JSON object per night. Every section is a READING, the same
three-key convention as ops/prod_state.py, so a renderer can never print a gap
as if it were a value. A reading has exactly one of:

    {"value": v, "source": "...", "read_at": "<ISO UTC>", "label": "broker-confirmed" | "modelled"}
    {"absent": "why the thing does not exist"}
    {"UNMEASURED": "what was tried"}

`validate` checks the shape. `find_private` checks what a snapshot may never
carry (dashboard/README.md section 2). Both return a list of problems; empty
means clean. Neither raises on bad data, so a test can show every problem.
"""
from __future__ import annotations

import re

SCHEMA_VERSION = "0.1-draft"
LABELS = ("broker-confirmed", "modelled")
UNMEASURED = "UNMEASURED"

# section path -> what its value must look like (None: any scalar number)
SECTIONS = {
    ("account", "equity"): "number",
    ("account", "last_equity"): "number",
    ("pnl", "official_eod_change_usd"): "number",
    ("pnl", "snapshot_change_usd"): "number",
    ("pnl", "auction_pnl_usd"): "number",
    ("equity_history",): "equity_history",
    ("positions",): "positions",
    ("trades",): "trades",
    ("system",): "system",
}
TOP_KEYS = ("schema_version", "synthetic", "book", "session_date", "exported_at_utc")
SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,5}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float("inf")


def _check_value(kind: str, v, where: str, out: list) -> None:
    if kind == "number":
        if not _num(v):
            out.append(f"{where}: value must be a finite number, got {v!r}")
    elif kind == "equity_history":
        if not isinstance(v, list) or not v:
            out.append(f"{where}: value must be a non-empty list of {{date, equity}}")
            return
        for i, r in enumerate(v):
            if not (isinstance(r, dict) and DATE.match(str(r.get("date", ""))) and _num(r.get("equity"))):
                out.append(f"{where}[{i}]: needs a date (YYYY-MM-DD) and a numeric equity")
    elif kind == "positions":
        if not isinstance(v, list):
            out.append(f"{where}: value must be a list of {{symbol, qty}}")
            return
        for i, r in enumerate(v):
            if not (isinstance(r, dict) and SYMBOL.match(str(r.get("symbol", ""))) and _num(r.get("qty"))):
                out.append(f"{where}[{i}]: needs a ticker symbol and a numeric qty (negative = short)")
    elif kind == "trades":
        if not (isinstance(v, dict) and isinstance(v.get("orders"), list) and isinstance(v.get("fills"), list)):
            out.append(f"{where}: value must be {{orders: [...], fills: [...]}}")
            return
        for i, r in enumerate(v["orders"]):
            if not (isinstance(r, dict) and SYMBOL.match(str(r.get("symbol", ""))) and r.get("side") in ("buy", "sell")
                    and _num(r.get("qty")) and isinstance(r.get("status"), str)):
                out.append(f"{where}.orders[{i}]: needs symbol, side buy|sell, numeric qty, status")
        for i, r in enumerate(v["fills"]):
            if not (isinstance(r, dict) and SYMBOL.match(str(r.get("symbol", ""))) and r.get("side") in ("buy", "sell")
                    and _num(r.get("qty")) and _num(r.get("price"))):
                out.append(f"{where}.fills[{i}]: needs symbol, side buy|sell, numeric qty and price")
    elif kind == "system":
        ok = (isinstance(v, dict) and v.get("verdict") in ("PASS", "FAIL")
              and isinstance(v.get("reason"), str) and isinstance(v.get("problems"), list))
        if not ok:
            out.append(f"{where}: value must carry verdict PASS|FAIL, a reason string and a problems list")


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
    if "session_date" in snap and not DATE.match(str(snap["session_date"])):
        out.append("session_date must be YYYY-MM-DD")
    if "exported_at_utc" in snap and not ISO_UTC.match(str(snap["exported_at_utc"])):
        out.append("exported_at_utc must be ISO UTC (YYYY-MM-DDTHH:MM:SSZ)")
    for path, kind in SECTIONS.items():
        node = snap
        for p in path:
            node = node.get(p) if isinstance(node, dict) else None
        if node is None:
            out.append(f"missing section {'.'.join(path)}")
            continue
        _check_reading(node, kind, ".".join(path), out)
    return out


# ---------------------------------------------------------------- privacy --
# dashboard/README.md section 2. Key names that never appear, wherever they nest.
FORBIDDEN_KEYS = re.compile(
    r"(api[_-]?key|secret|token|passw|credential|key[_-]?id|account[_-]?(number|id|no)|"
    r"cusip|permno|isin|sedol|crsp|trace|compustat|host(name)?|server|vm[_-]?(addr|ip|name)|"
    r"vault|subscription|endpoint|bucket|client[_-]?order[_-]?id|\bssh\b)", re.I)
# Value patterns that never appear in any string.
FORBIDDEN_VALUES = {
    "IPv4 address": re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    "IPv6 address": re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}\b"),
    "long hex string (looks like a key or hash)": re.compile(r"\b[0-9a-fA-F]{32,}\b"),
    "Alpaca key id": re.compile(r"\b(?:PK|AK|CK)[A-Z0-9]{16,}\b"),
    "Alpaca account number": re.compile(r"\bPA[0-9A-Z]{8,}\b"),
    "cloud hostname": re.compile(r"\b[\w-]+\.(?:cloudapp\.azure\.com|azure\.com|cloudflarestorage\.com|compute\.amazonaws\.com)\b", re.I),
    "URL": re.compile(r"https?://", re.I),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "email address": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
}


def find_private(node, path: str = "$") -> list:
    """Every place a snapshot carries something the README forbids."""
    out: list = []
    if isinstance(node, dict):
        for k, v in node.items():
            if FORBIDDEN_KEYS.search(str(k)):
                out.append(f"{path}.{k}: forbidden key name")
            out.extend(find_private(v, f"{path}.{k}"))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.extend(find_private(v, f"{path}[{i}]"))
    elif isinstance(node, str):
        for what, rx in FORBIDDEN_VALUES.items():
            if rx.search(node):
                out.append(f"{path}: contains a {what}")
    return out
