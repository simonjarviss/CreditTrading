"""Ingest the VM's live P&L records into sanitised, committed daily CSVs.

    python3 -m scripts.report.snapshot_live --src <vm_pnl dir> [--book cef|c4] [--no-log] [--force]

WHY THIS FILE EXISTS (2026-11-03). The team lead's read-only wrapper `vmpnl.sh` copies
the prod VM's P&L records (equity.csv, scores.csv, distribution_scores.csv, tca.csv and
the verify logs, from `<state>/` and `<state>/logs/`) to the laptop's scratchpad. That
copy is local and temporary. The research report needs the live record in the
repository, day by day, so this tool turns each pull into sanitised CSVs under
`results/report/data/live/<book>/` and appends one `live-pnl` entry per new session to
`results/report/EVIDENCE_LOG.md`.

THE REPOSITORY IS PUBLIC, AND IT KEEPS AGGREGATES ONLY. Team lead, 2026-11-03, on PR #45:
"Aggregates in repo, rows private" (docs/SYSTEM.md §5). So each pull is split in two:
  * daily, account-level AGGREGATES go to `results/report/data/live/<book>/` (tracked):
    equity (the EOD record and the snapshot, labelled), P&L, the hold and fill totals,
    fill-cost summaries in bp with counts, order counts, verify and gate outcomes. The
    precedent is FILL-DRIFT's aggregates file (results/cef/fill_drift_2026-11-02/);
  * ROWS (per-name quantities, per-name or per-fill prices, positions, order-level and
    free-text detail) go to `results/report/_cache_live/<book>/`, which is gitignored. A row
    file is written only where git cannot see it: inside any work tree, every row file must
    be ignored (`git check-ignore`), or nothing is written. An aggregate table that carries a
    row-level column is refused too.
A git commit is published, and git keeps it after deletion (dashboard/README.md §2), so
the split is enforced in code, not left to the operator.

THE SANITISER IS AN ALLOWLIST, NOT A BLOCKLIST, for both halves:
  * every input file has a known schema; a column it does not know is refused, named, and
    nothing is written. A new column on the VM is a schema change for a human to review;
  * inside the JSON columns every key is known; `order_ids` and the corporate-action `id` are
    dropped even from the private rows; an unknown key is refused, named;
  * every string that is kept is scanned for identifier shapes (UUIDs, IPv4 addresses,
    Alpaca account numbers, Azure host or vault names, e-mail addresses, the VM's ssh
    alias); a hit refuses the run, naming the file, the row and the field, never the value;
  * the verify log is free text, so only its three known line shapes are parsed; any other
    non-empty line is refused, by line number.

IDEMPOTENT. A pull is identified by the sha256 of its input files. Re-running on a pull
already recorded in `pulls.csv` writes nothing and appends nothing. A later pull is
merged by key (date, symbol, side): rows only in the old files are kept, and a row the
VM has revised (distribution scores are re-scored when the panel catches up) takes the
new value; the count of revised rows is printed and git shows the diff. Values are kept
as the VM wrote them (strings), never re-formatted, so a re-run is byte-identical.

LABELS. Before 2026-10-19 the verify line called the 17:30 ET `equity − last_equity`
reading "(official, gross)". The team lead ruled that day that the official daily P&L
is Alpaca's end-of-day portfolio history and the 17:30 reading is a labelled snapshot
(docs/SYSTEM.md §5, "P&L of record"). So that reading is stored as `snapshot_1730_usd`
whatever the line called it, and the old wording is kept in `verify_label`. The
official series is `eod_equity.csv`, which `vmpnl.sh` copies only if its grep includes
`eod_equity`; when it is absent, the official figure is written UNMEASURED, never
filled from the snapshot (CLAUDE.md: no silent fallbacks).

A FILE ONE BOOK MAY LACK (2026-11-05). `distribution_scores.csv` is required in a core
(`cef`) pull, exactly as before, and optional in a C4 pull. C4's verify runs the same
distribution score (quantt/session/verify.py `run_distributions`, against C4's own panel),
but dist_score scores a session only once it is two sessions old and has a session folder
(docs/DATA.md), so C4's first pulls, from its first trading week (armed 2026-11-03), carry
no such file, and the core's rule refused every one of them. Optional means named, never
defaulted: a C4 pull without the file writes no distribution aggregate and no distribution
rows, and its live-day entry says the distribution-adjusted P&L is UNMEASURED because
`distribution_scores.csv` is not in the pull. It is never written as zero. A C4 pull that
carries the file is ingested exactly as the core's is.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

import subprocess

from scripts.report.common import CACHE, EVIDENCE_LOG, LIVE, sha256_bytes
from scripts.report import evidence_log as elog


class SanitiseError(RuntimeError):
    """The pull carries something the sanitiser does not know how to drop. Nothing written."""


# ---------------------------------------------------------------- identifier scan --
IDENTIFIER_PATTERNS = [
    ("uuid", re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")),
    ("ipv4", re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")),
    # Alpaca paper account numbers read "PA" plus about ten capitals and digits.
    ("alpaca account number", re.compile(r"\bPA[0-9A-Z]{8,12}\b")),
    ("azure host or vault", re.compile(r"\b[\w-]+\.(?:cloudapp\.azure\.com|vault\.azure\.net|azure\.com|"
                                       r"windows\.net|azurewebsites\.net)\b|\bvault\b", re.I)),
    ("subscription", re.compile(r"\bsubscription\b", re.I)),
    ("e-mail address", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    ("ssh alias or host", re.compile(r"\bquantt-vm\b|\bssh\b|\bhostname\b", re.I)),
    ("account id field", re.compile(r"\baccount[_ ]?(?:id|number|no)\b", re.I)),
]


def scan(value: str, where: str) -> None:
    """Refuse if `value` has an identifier shape. Names the place, never the value."""
    for name, pat in IDENTIFIER_PATTERNS:
        if pat.search(value):
            raise SanitiseError(f"{where}: carries what looks like an identifier ({name}); "
                                "the sanitiser does not know how to drop it. Nothing was written.")


# ------------------------------------------------------------------------ schemas --
# For each input: the columns kept (in this order), the columns dropped, and the JSON
# columns exploded into their own table. Anything else refuses.
SCHEMAS = {
    "equity.csv": {"keep": ["date", "equity", "last_equity", "cash", "long_market_value",
                            "short_market_value", "n_positions", "read_at_utc"], "drop": []},
    "scores.csv": {"keep": ["date", "book", "verdict", "traded", "n_orders", "n_filled",
                            "alpaca_equity", "alpaca_last_equity", "alpaca_equity_change_usd",
                            "auction_pnl_usd", "auction_hold_pnl_usd", "auction_fill_pnl_usd",
                            "fill_vs_auction_bp", "unmeasured", "auction_condition", "cost_basis",
                            "read_at"], "drop": [], "json": "per_symbol_json"},
    # Required for every book except those in `optional_for` (module docstring, 2026-11-05).
    "distribution_scores.csv": {"keep": ["date", "auction_pnl_usd", "distribution_pnl_usd",
                                         "auction_pnl_with_distributions_usd", "unmeasured", "source",
                                         "label", "written_at_utc"], "drop": [],
                                "json": "per_symbol_json", "optional_for": ("c4",)},
    "tca.csv": {"keep": ["date", "book", "n_orders", "n_full", "shares_ordered", "shares_filled",
                         "fill_rate_shares", "slip_bp_buy", "slip_bp_sell", "slip_bp_all",
                         "slip_unmeasured", "residual_gross_usd", "residual_net_usd", "residual_names",
                         "basis"], "drop": []},
    # The P&L of record (drawdown.py: `date`, `equity`, `change_usd`, "possibly with extra
    # columns"); an extra column refuses here until a human adds it to this list.
    # read_at_utc: when the collector read Alpaca's EOD history (a timestamp, no identifier); kept so a
    # restated EOD point can be told from the first read (first seen in the 2026-11-03 pull).
    "eod_equity.csv": {"keep": ["date", "equity", "change_usd", "read_at_utc"], "drop": [], "optional": True},
}
SCORE_SYMBOL_KEYS = {"symbol", "auction_d", "auction_prev", "auction_pnl", "fill_pnl", "held_qty",
                     "hold_pnl", "sides"}
SCORE_SIDE_KEYS = {"side", "qty", "vwap", "bp_vs_auction"}
SCORE_SIDE_DROP = {"order_ids"}
DIST_SYMBOL_KEYS = {"symbol", "held_qty", "per_share", "dist_pnl", "source", "alpaca_events"}
DIST_EVENT_KEYS = {"kind", "amount"}
DIST_EVENT_DROP = {"id"}
LOG_FILES = {"logs/verify.out.log", "logs/verify.err.log"}


def _cell(v) -> str:
    """A JSON value as the string the table stores (numbers exactly as json writes them)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, (int, float)):
        return json.dumps(v)
    if isinstance(v, str):
        return v
    raise SanitiseError(f"unexpected nested value of type {type(v).__name__}")


def _read_csv(name: str, data: bytes) -> list[dict]:
    schema = SCHEMAS[name]
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    header = next(csv.reader(io.StringIO(data.decode("utf-8"))), [])
    known = set(schema["keep"]) | set(schema["drop"]) | ({schema["json"]} if "json" in schema else set())
    unknown = [c for c in header if c not in known]
    if unknown:
        raise SanitiseError(f"{name}: unknown column(s) {unknown}; add each to SCHEMAS with a keep "
                            "or drop decision before ingesting. Nothing was written.")
    absent = [c for c in schema["keep"] if c not in header]
    if absent:
        raise SanitiseError(f"{name}: expected column(s) {absent} are missing (a schema change)")
    out = []
    for i, r in enumerate(rows, start=2):
        kept = {c: r[c] for c in schema["keep"]}
        for c, v in kept.items():
            scan(v or "", f"{name} row {i} column {c}")
        if "json" in schema:
            kept["_json"] = r[schema["json"]]
        out.append(kept)
    return out


def _explode_scores(rows: list[dict], book: str) -> list[dict]:
    out = []
    for r in rows:
        items = json.loads(r.pop("_json") or "[]")
        for it in items:
            bad = set(it) - SCORE_SYMBOL_KEYS
            if bad:
                raise SanitiseError(f"scores.csv {r['date']} per_symbol_json: unknown key(s) {sorted(bad)}")
            base = {"date": r["date"], "book": r["book"] or book, "symbol": _cell(it["symbol"]),
                    "held_qty": _cell(it["held_qty"]), "auction_prev": _cell(it["auction_prev"]),
                    "auction_d": _cell(it["auction_d"]), "hold_pnl": _cell(it["hold_pnl"]),
                    "fill_pnl": _cell(it["fill_pnl"]), "auction_pnl": _cell(it["auction_pnl"])}
            sides = it.get("sides") or []
            if not sides:
                out.append({**base, "side": "", "qty": "", "vwap": "", "bp_vs_auction": ""})
            for s in sides:
                bad = set(s) - SCORE_SIDE_KEYS - SCORE_SIDE_DROP
                if bad:
                    raise SanitiseError(f"scores.csv {r['date']} {base['symbol']} sides: unknown key(s) "
                                        f"{sorted(bad)}")
                out.append({**base, "side": _cell(s["side"]), "qty": _cell(s["qty"]),
                            "vwap": _cell(s["vwap"]), "bp_vs_auction": _cell(s["bp_vs_auction"])})
    for r in out:
        for c, v in r.items():
            scan(v, f"scores.csv per_symbol_json {r['date']} {r['symbol']} field {c}")
    return out


def _explode_dists(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        items = json.loads(r.pop("_json") or "[]")
        for it in items:
            bad = set(it) - DIST_SYMBOL_KEYS
            if bad:
                raise SanitiseError(f"distribution_scores.csv {r['date']} per_symbol_json: unknown "
                                    f"key(s) {sorted(bad)}")
            events = []
            for ev in it.get("alpaca_events") or []:
                bad = set(ev) - DIST_EVENT_KEYS - DIST_EVENT_DROP
                if bad:
                    raise SanitiseError(f"distribution_scores.csv {r['date']} {it.get('symbol')} "
                                        f"alpaca_events: unknown key(s) {sorted(bad)}")
                events.append(f"{_cell(ev['kind'])}:{_cell(ev['amount'])}")
            out.append({"date": r["date"], "symbol": _cell(it["symbol"]), "held_qty": _cell(it["held_qty"]),
                        "per_share": _cell(it["per_share"]), "dist_pnl": _cell(it["dist_pnl"]),
                        "alpaca_events": ";".join(events), "source": _cell(it["source"])})
    for r in out:
        for c, v in r.items():
            scan(v, f"distribution_scores.csv per_symbol_json {r['date']} {r['symbol']} field {c}")
    return out


# --------------------------------------------------------------------- verify log --
_D = r"(\d{4}-\d{2}-\d{2})"
VERDICT = re.compile(rf"^{_D} (PASS|FAIL|WARN) (\S+) (.*)$")
SHADOW = re.compile(rf"^shadow {_D}: (-?[\d.]+) USD \((MODELLED[^)]*)\)$")
DISTS = re.compile(rf"^distributions {_D}: (-?[\d.]+|UNMEASURED) USD \(([^)]*)\)$")
_USD = r"([+-]?[\d,]+\.\d+) USD"


def _num(rx: str, text: str) -> str:
    m = re.search(rx, text)
    return m.group(1).replace(",", "") if m else ""


def parse_verify(text: str, name: str = "logs/verify.out.log") -> tuple[list, list, list]:
    """(verdict rows, shadow rows, distribution rows). The last line for a date wins,
    because verify re-prints earlier dates' distribution status on every run."""
    verdicts, shadows, dists = {}, {}, {}
    for i, ln in enumerate(text.splitlines(), start=1):
        ln = ln.rstrip()
        if not ln:
            continue
        scan(ln, f"{name} line {i}")
        if m := VERDICT.match(ln):
            d, verdict, book, rest = m.groups()
            official_word = "(official, gross)" in rest
            snap = _num(rf"alpaca equity chg {_USD}", rest) or _num(rf"snapshot 17:30 ET {_USD}", rest)
            official = "" if official_word else _num(rf"official {_USD}", rest)
            refused = re.findall(r"\[(\w+)\]", rest)
            verdicts[(d, book)] = {
                "date": d, "book": book, "verdict": verdict,
                "missed": "True" if "MISSED:" in rest else "False",
                "traded": "True" if re.search(r"\btraded \d+ order", rest) else "False",
                "n_orders": _num(r"traded (\d+) order", rest),
                "n_filled": _num(r"(\d+) filled", rest),
                "snapshot_1730_usd": snap,
                "verify_label": "(official, gross): pre-2026-10-19 wording; it is the 17:30 snapshot"
                                if official_word else ("snapshot 17:30 ET" if snap else ""),
                "official_usd": official,
                "official_status": "PENDING at 17:30" if "official PENDING" in rest else "",
                "auction_marked_usd": _num(rf"auction-marked {_USD}", rest),
                "fill_vs_auction_bp": _num(r"fill vs auction ([+-]?[\d.]+)bp", rest),
                "refusal_gates": ";".join(dict.fromkeys(refused)),
                "detail": rest,
            }
        elif m := SHADOW.match(ln):
            shadows[m.group(1)] = {"date": m.group(1), "shadow_modelled_usd": m.group(2),
                                   "label": m.group(3)}
        elif m := DISTS.match(ln):
            dists[m.group(1)] = {"date": m.group(1), "distribution_adjusted_usd": m.group(2),
                                 "label": m.group(3)}
        else:
            raise SanitiseError(f"{name} line {i}: an unknown line shape; the sanitiser parses only "
                                "verdict, shadow and distributions lines. Nothing was written.")
    return list(verdicts.values()), list(shadows.values()), list(dists.values())


# ------------------------------------------------------------------- pull + merge --
def required(name: str, book: str) -> bool:
    """Whether `book`'s pull must carry input `name`. `book` is always named: a file one
    book may lack is still required of every other (2026-11-05)."""
    schema = SCHEMAS[name]
    return not schema.get("optional") and book not in schema.get("optional_for", ())


def read_pull(src: Path, book: str) -> dict:
    """Every recognised input file's bytes. Unknown files are refused, so nothing new
    can ride along unseen; a file `book` requires (`required`) is refused if absent."""
    src = Path(src)
    if not src.is_dir():
        raise SanitiseError(f"{src}: not a directory (run vmpnl.sh first)")
    files = {}
    for p in sorted(src.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(src).as_posix()
        if rel not in SCHEMAS and rel not in LOG_FILES:
            raise SanitiseError(f"{rel}: an unknown file in the pull; add it to SCHEMAS or LOG_FILES "
                                "with a sanitising rule first. Nothing was written.")
        files[rel] = p.read_bytes()
    for name in SCHEMAS:
        if name not in files and required(name, book):
            raise SanitiseError(f"{name}: missing from the pull at {src}")
    return files


def pull_id(files: dict) -> str:
    """12 hex characters of sha256 over the sorted (name, sha256) pairs."""
    blob = "\n".join(f"{n} {sha256_bytes(b)}" for n, b in sorted(files.items()))
    return sha256_bytes(blob.encode())[:12]


# Columns that make a table row-level. None may appear in a tracked aggregate file.
ROW_LEVEL_COLUMNS = {"symbol", "side", "qty", "held_qty", "vwap", "per_share", "auction_d",
                     "auction_prev", "residual_names", "detail", "alpaca_events"}


def sanitise(files: dict, book: str) -> tuple[dict, dict]:
    """(rows, aggregates) for one pull, each {name: (key columns, rows)}. Raises before
    anything is written."""
    rows, agg = {}, {}
    agg["equity_snapshot.csv"] = (["date"], _read_csv("equity.csv", files["equity.csv"]))
    sc = [r for r in _read_csv("scores.csv", files["scores.csv"]) if (r["book"] or book) == book]
    rows["scores_by_symbol.csv"] = (["date", "symbol", "side"], _explode_scores(sc, book))
    agg["scores.csv"] = (["date"], sc)
    # A book that may lack distribution_scores.csv (C4, 2026-11-05) writes NO distribution
    # table when its pull has none: no empty aggregate, no rows, never a zero. The live-day
    # entry names the missing file instead (live_entries). Every other book still needs it.
    has_dist = "distribution_scores.csv" in files
    if not has_dist and required("distribution_scores.csv", book):
        raise SanitiseError("distribution_scores.csv: missing from the pull")
    if has_dist:
        ds = _read_csv("distribution_scores.csv", files["distribution_scores.csv"])
        rows["distributions_by_symbol.csv"] = (["date", "symbol"], _explode_dists(ds))
        agg["distribution_scores.csv"] = (["date"], ds)
    tca = [r for r in _read_csv("tca.csv", files["tca.csv"]) if (r["book"] or book) == book]
    rows["tca_residual_names.csv"] = (["date"], [{"date": r["date"], "residual_names": r["residual_names"]}
                                                  for r in tca])
    agg["tca.csv"] = (["date"], [{k: v for k, v in r.items() if k != "residual_names"} for r in tca])
    if "eod_equity.csv" in files:
        agg["eod_equity.csv"] = (["date"], _read_csv("eod_equity.csv", files["eod_equity.csv"]))
    err = files.get("logs/verify.err.log", b"")
    if err.strip():
        raise SanitiseError("logs/verify.err.log is not empty; its content has no sanitising rule")
    v, sh, d = parse_verify(files.get("logs/verify.out.log", b"").decode("utf-8"))
    v = [r for r in v if r["book"] == book]
    rows["verify_detail.csv"] = (["date", "book"], [{"date": r["date"], "book": r["book"], "detail": r["detail"]}
                                                    for r in v])
    agg["verify.csv"] = (["date", "book"], [{k: x for k, x in r.items() if k != "detail"} for r in v])
    agg["verify_shadow.csv"] = (["date"], sh)
    # verify's own "distributions D:" lines. With no distribution_scores.csv in the pull and
    # no such line either, there is no distribution record at all, so no table is written
    # (a header-only file would read as a measured nothing). The core always has the file.
    if has_dist or d:
        agg["verify_distributions.csv"] = (["date"], d)
    return rows, agg


def _quantile(xs: list, q: float) -> float:
    """Linear-interpolated quantile (numpy's default), without importing numpy here."""
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def _cost_stats(fills: list[tuple]) -> dict:
    """Fill-cost summary over (bp, notional, side) tuples: counts and bp statistics only."""
    bp = [f[0] for f in fills]
    w = sum(f[1] for f in fills)
    n = len(bp)
    mean = sum(bp) / n
    sd = (sum((x - mean) ** 2 for x in bp) / (n - 1)) ** 0.5 if n > 1 else float("nan")
    r = lambda x: f"{x:.2f}"   # noqa: E731
    return {"n_fills": str(n), "n_buy": str(sum(f[2] == "buy" for f in fills)),
            "n_sell": str(sum(f[2] != "buy" for f in fills)), "notional_usd": f"{w:.2f}",
            "wmean_bp": r(sum(f[0] * f[1] for f in fills) / w), "mean_bp": r(mean),
            "median_bp": r(_quantile(bp, 0.5)), "p10_bp": r(_quantile(bp, 0.1)),
            "p90_bp": r(_quantile(bp, 0.9)), "min_bp": r(min(bp)), "max_bp": r(max(bp)),
            "sd_bp": r(sd) if n > 1 else ""}


def fill_cost_aggregates(symbol_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """(daily, pooled) fill-cost summaries from the private per-name rows. A unit is one
    name, side and session (the VWAP of that day's fills); bp is against the primary-exchange
    official close, positive = worse (scores.csv's convention)."""
    fills = []
    for r in symbol_rows:
        try:
            bp, q, px = float(r["bp_vs_auction"]), float(r["qty"]), float(r["vwap"])
        except (KeyError, ValueError):
            continue                       # a held name with no fill that day: no fill to cost
        fills.append((r["date"], bp, q * px, r["side"]))
    days = sorted({f[0] for f in fills})
    daily = [{"date": d, **_cost_stats([(b, n, s) for dd, b, n, s in fills if dd == d])} for d in days]
    pooled = []
    for name, sel in (("all", fills), ("buy", [f for f in fills if f[3] == "buy"]),
                      ("sell", [f for f in fills if f[3] != "buy"])):
        if sel:
            pooled.append({"group": name, "first": min(f[0] for f in sel), "last": max(f[0] for f in sel),
                           "n_days": str(len({f[0] for f in sel})),
                           **_cost_stats([(b, n, s) for _, b, n, s in sel])})
    return daily, pooled


def _read_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return list(csv.DictReader(io.StringIO(path.read_text())))


def _refuse_tracked(directory: Path, names) -> None:
    """Refuse to write row files git could see. Inside a work tree each must be ignored;
    if git cannot answer, refuse (there is no default). Outside any work tree: allowed."""
    d = Path(directory)
    probe = d
    while not probe.exists():
        probe = probe.parent
    top = subprocess.run(["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, timeout=30)
    if top.returncode != 0:
        return                              # not inside a git work tree
    root = Path(top.stdout.strip()).resolve()
    paths = [(d.resolve() / n).relative_to(root).as_posix() for n in names]
    r = subprocess.run(["git", "-C", str(root), "check-ignore", *paths],
                       capture_output=True, text=True, timeout=30)
    if r.returncode not in (0, 1):
        raise SanitiseError(f"refusing to write rows in {d}: git check-ignore exited {r.returncode}")
    visible = sorted(set(paths) - set(r.stdout.splitlines()))
    if visible:
        raise SanitiseError(f"refusing to write row-level file(s) {visible[:3]} where git can see them: "
                            "rows go only to the gitignored cache (team lead, 2026-11-03: "
                            "'Aggregates in repo, rows private')")


def _refuse_row_columns(name: str, cols) -> None:
    bad = sorted(set(cols) & ROW_LEVEL_COLUMNS)
    if bad:
        raise SanitiseError(f"{name}: row-level column(s) {bad} may not be written to the tracked "
                            "aggregates (team lead, 2026-11-03)")


def _write(path: Path, rows: list[dict], keys: list[str]) -> str:
    cols = list(rows[0].keys()) if rows else keys
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for r in sorted(rows, key=lambda r: tuple(r.get(k, "") for k in keys)):
        w.writerow({c: r.get(c, "") for c in cols})
    path.write_text(buf.getvalue())
    return buf.getvalue()


def merge(existing: list[dict], new: list[dict], keys: list[str]) -> tuple[list[dict], int, int]:
    """(merged rows, added, revised). New values win for a key present in both."""
    by = {tuple(r.get(k, "") for k in keys): r for r in existing}
    added = revised = 0
    for r in new:
        k = tuple(r.get(c, "") for c in keys)
        if k not in by:
            added += 1
        elif by[k] != r:
            revised += 1
        by[k] = r
    return list(by.values()), added, revised


# ------------------------------------------------------------- evidence-log append --
LIVE_NN = {"cef": "90", "c4": "91"}


def _fmt(x: str) -> str:
    return x if x else "UNMEASURED"


def live_entries(book: str, out_dir: Path, pid: str, existing_ids: set, pulled: set) -> list[str]:
    """One `live-pnl` entry per session date not yet in the log, from the sanitised files.
    `pulled` is the set of file names in this pull: a figure whose input file the pull did
    not carry is written UNMEASURED naming that file, never left out or zeroed."""
    nn = LIVE_NN.get(book)
    if nn is None:
        raise SanitiseError(f"book {book!r} has no live entry number; add it to LIVE_NN")
    rd = lambda n: {r["date"]: r for r in _read_existing(out_dir / n)}   # noqa: E731
    scores, verify, tca = rd("scores.csv"), rd("verify.csv"), rd("tca.csv")
    dist, shadow, eod = rd("distribution_scores.csv"), rd("verify_shadow.csv"), rd("eod_equity.csv")
    rel = f"results/report/data/live/{book}"
    out = []
    for d in sorted(set(scores) | set(verify)):
        eid = f"E-{d}-{nn}"
        if eid in existing_ids:
            continue
        s, v, t = scores.get(d, {}), verify.get(d, {}), tca.get(d, {})
        verdict = v.get("verdict") or s.get("verdict") or "UNMEASURED"
        snap = s.get("alpaca_equity_change_usd") or v.get("snapshot_1730_usd", "")
        off = eod.get(d, {}).get("change_usd", "")
        disagree = bool(snap and off and abs(float(snap) - float(off)) > 0.005)
        tag = "[U]" if disagree else "[S]"
        n_orders = s.get("n_orders") or v.get("n_orders") or "0"
        n_filled = s.get("n_filled") or v.get("n_filled") or "0"
        missed = " MISSED" if v.get("missed") == "True" else ""
        # Why the official figure is missing, said truly. Until 2026-11-05 every miss read "not in
        # this pull", but the usual miss is a pull that carries eod_equity.csv without a point for
        # D yet (Alpaca's EOD history for D is read the next morning; E-2026-11-03-90's pull had
        # the file). The figure stays UNMEASURED either way; only the reason changes.
        if off:
            eod_fig = f"official EOD equity change {off} USD (Alpaca portfolio history 1D, the P&L of record) {tag}"
        elif "eod_equity.csv" not in pulled:
            eod_fig = "official EOD equity change UNMEASURED: eod_equity.csv not in this pull [U]"
        else:
            eod_fig = ("official EOD equity change UNMEASURED: eod_equity.csv in this pull has no change_usd "
                       f"for {d} [U]")
        figs = [
            f"verify verdict {verdict}{missed}; orders sent {n_orders}, filled {n_filled} [S]",
            f"17:30 ET snapshot equity change {_fmt(snap)} USD (gross; a snapshot, not the P&L of record) {tag}",
            eod_fig,
            f"auction-marked P&L {_fmt(s.get('auction_pnl_usd') or v.get('auction_marked_usd', ''))} USD [S]",
        ]
        if disagree:
            figs.append("snapshot and EOD disagree; the record is the EOD history "
                        "(docs/SYSTEM.md §5, 2026-10-19) [U]")
        bp = s.get("fill_vs_auction_bp") or v.get("fill_vs_auction_bp", "")
        if bp and bp != "no fills":
            figs.append(f"fills vs official close {bp} bp (+ = worse) [S]")
        if t.get("slip_bp_all"):
            figs.append(f"TCA notional-weighted slippage {t['slip_bp_all']} bp, fill rate "
                        f"{t.get('fill_rate_shares', '')} of shares [S]")
        if d in dist:
            figs.append("distribution-adjusted P&L "
                        f"{_fmt(dist[d].get('auction_pnl_with_distributions_usd', ''))} USD "
                        "(credits distributions paper does not) [S]")
        elif "distribution_scores.csv" not in pulled:
            figs.append("distribution-adjusted P&L UNMEASURED: distribution_scores.csv not in this pull [U]")
        if d in shadow:
            figs.append(f"shadow book {shadow[d]['shadow_modelled_usd']} USD (MODELLED, not broker evidence) [S]")
        if v.get("refusal_gates"):
            figs.append(f"refusing gate(s): {v['refusal_gates']} [S]")
        word = "traded" if s.get("traded") == "True" or v.get("traded") == "True" else "did not trade"
        claim = f"{book} paper book, {d}: {verdict}{missed}, {word}"
        srcs = "; ".join(f"`{rel}/{n}` @ `pull:{pid}`" for n in ("scores.csv", "verify.csv", "tca.csv"))
        out.append("\n".join([f"### {eid} · {claim}", "- kind: live-pnl", "- era: ALPACA", f"- date: {d}",
                              "- figures:", *[f"  - {f}" for f in figs], f"- source: {srcs}",
                              "- supports: §4", "- status: current"]))
    return out


def append_entries(log: Path, blocks: list[str]) -> int:
    if not blocks:
        return 0
    if not log.exists():
        raise SanitiseError(f"{log}: the evidence log is missing; it is created by hand, never here")
    text = log.read_text()
    new = text.rstrip("\n") + "\n\n" + "\n\n".join(blocks) + "\n"
    errs = elog.validate(elog.parse(new)) or elog.check_append_only(text, new)
    if errs:
        raise SanitiseError("the appended log would be invalid: " + "; ".join(errs[:5]))
    log.write_text(new)
    return len(blocks)


# --------------------------------------------------------------------------- main --
def ingest(src: Path, book: str = "cef", out_root: Path = LIVE, log: Path | None = EVIDENCE_LOG,
           force: bool = False, cache_root: Path = CACHE) -> dict:
    files = read_pull(src, book)
    pid = pull_id(files)
    out_dir, cache_dir = Path(out_root) / book, Path(cache_root) / book
    pulls = out_dir / "pulls.csv"
    seen = {r["pull"] for r in _read_existing(pulls)}
    if pid in seen and not force:
        return {"pull": pid, "status": "already ingested", "added": 0, "revised": 0, "entries": 0}
    rows, agg = sanitise(files, book)                 # raises before anything is written
    _refuse_tracked(cache_dir, list(rows))
    merged_rows = {}
    for name, (keys, new) in rows.items():
        merged_rows[name] = (keys, merge(_read_existing(cache_dir / name), new, keys)[0])
    daily, pooled = fill_cost_aggregates(merged_rows["scores_by_symbol.csv"][1])
    agg["fill_cost_daily.csv"] = (["date"], daily)
    for name, (keys, new) in agg.items():
        _refuse_row_columns(name, new[0].keys() if new else keys)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (keys, merged) in merged_rows.items():
        _write(cache_dir / name, merged, keys)
    added = revised = 0
    for name, (keys, new) in agg.items():
        merged, a, r = merge(_read_existing(out_dir / name), new, keys)
        added, revised = added + a, revised + r
        _write(out_dir / name, merged, keys)
    # Pooled over every fill the cache holds; it says which days that is, so a cache that
    # lost old rows shows as fewer days, never as a silently different window.
    _write(out_dir / "fill_cost_pooled.csv", pooled, ["group"])
    if pid not in seen:
        last = max((r["date"] for r in agg["scores.csv"][1]), default="")
        prs = _read_existing(pulls) + [{"pull": pid, "last_session": last, "files": " ".join(sorted(files))}]
        _write(pulls, prs, ["pull"])
    n = 0
    if log is not None:
        ids = {e.id for e in elog.parse(Path(log).read_text())} if Path(log).exists() else set()
        n = append_entries(Path(log), live_entries(book, out_dir, pid, ids, pulled=set(files)))
    return {"pull": pid, "status": "ingested", "added": added, "revised": revised, "entries": n}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", required=True, help="the vm_pnl folder vmpnl.sh wrote")
    ap.add_argument("--book", default="cef")
    ap.add_argument("--no-log", action="store_true", help="do not append live-pnl entries")
    ap.add_argument("--force", action="store_true", help="re-derive the CSVs for a recorded pull")
    a = ap.parse_args(argv)
    try:
        res = ingest(Path(a.src), a.book, log=None if a.no_log else EVIDENCE_LOG, force=a.force)
    except SanitiseError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
