"""Generate the dashboard: one static HTML page from one snapshot.

    python3 -m dashboard.build dashboard/fixtures/sample_snapshot.json -o dashboard/out/index.html

READ-ONLY BY CONSTRUCTION. This module reads one JSON file and writes one HTML
file. It imports only the standard library and `dashboard.snapshot`: no network,
no subprocess, nothing from quantt/ or ops/. The page has no script and loads
nothing from outside. `dashboard/tests/test_build.py` pins all of that.

Every figure prints with its source, read time and label. A gap prints as a gap
(MISSING), never as zero or blank. A snapshot that fails validation, or that
carries anything the README forbids, is refused: no page is written.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from html import escape
from pathlib import Path

from dashboard import snapshot as S

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#ddd;--bad:#b42318;--ok:#067647;--warn:#b54708;--card:#f7f7f8}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececec;--mut:#9a9aa2;--line:#33343a;--bad:#f97066;--ok:#47cd89;--warn:#fdb022;--card:#1d1e22}}
body{font:15px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0 auto;max-width:960px;padding:20px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.mut{color:var(--mut);font-size:12px}.banner{background:var(--card);border:1px solid var(--warn);color:var(--warn);padding:8px 12px;border-radius:6px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.card .n{font-size:22px;font-weight:600}.pos{color:var(--ok)}.neg{color:var(--bad)}.gap{color:var(--warn);font-weight:600}
table{border-collapse:collapse;width:100%;margin:6px 0}th,td{text-align:left;padding:4px 8px;border-bottom:1px solid var(--line)}
th{font-size:12px;color:var(--mut);font-weight:600}td.r,th.r{text-align:right}.wrap{overflow-x:auto}
"""


def usd(x: float, signed: bool = False) -> str:
    s = f"{abs(x):,.2f}"
    sign = ("+" if x >= 0 else "-") if signed else ("-" if x < 0 else "")
    return f"{sign}${s}"


def provenance(r: dict) -> str:
    return f'<div class="mut">{escape(r["source"])} · read {escape(r["read_at"])} · {escape(r["label"])}</div>'


def gap(r: dict) -> str:
    if S.UNMEASURED in r:
        return f'<span class="gap">MISSING (unmeasured)</span><div class="mut">{escape(r[S.UNMEASURED])}</div>'
    return f'<span class="gap">NONE</span><div class="mut">{escape(r["absent"])}</div>'


def money_card(title: str, r: dict, signed: bool = False) -> str:
    if "value" not in r:
        return f'<div class="card"><div class="mut">{escape(title)}</div>{gap(r)}</div>'
    v = r["value"]
    cls = "" if not signed else ("pos" if v > 0 else "neg" if v < 0 else "")
    return (f'<div class="card"><div class="mut">{escape(title)}</div>'
            f'<div class="n {cls}">{usd(v, signed)}</div>{provenance(r)}</div>')


def sparkline(rows: list) -> str:
    w, h, pad = 600, 120, 8
    ys = [r["equity"] for r in rows]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1.0
    n = len(rows)
    pts = []
    for i, y in enumerate(ys):
        x = pad + (w - 2 * pad) * (i / (n - 1) if n > 1 else 0.5)
        pts.append(f"{x:.1f},{h - pad - (h - 2 * pad) * (y - lo) / span:.1f}")
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Account value, {escape(rows[0]["date"])} to {escape(rows[-1]["date"])}">'
            f'<polyline fill="none" stroke="currentColor" stroke-width="2" points="{" ".join(pts)}"/></svg>')


def table(head: list, rows: list, right: tuple = ()) -> str:
    th = "".join(f'<th class="{"r" if i in right else ""}">{escape(h)}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td class="{"r" if i in right else ""}">{escape(str(c))}</td>' for i, c in enumerate(row)) + "</tr>"
                   for row in rows)
    return f'<div class="wrap"><table><tr>{th}</tr>{body}</table></div>'


def age_text(exported: str, now: dt.datetime) -> str:
    t = dt.datetime.strptime(exported, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    hours = (now - t).total_seconds() / 3600
    return f"{hours:.1f} hours old at build time" if hours < 48 else f"{hours / 24:.1f} days old at build time (STALE?)"


def render(snap: dict, now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(dt.timezone.utc)
    p = []
    p.append(f'<h1>Credit book: {escape(snap["book"])}</h1>'
             f'<div class="mut">Session {escape(snap["session_date"])} · snapshot exported {escape(snap["exported_at_utc"])} '
             f'({escape(age_text(snap["exported_at_utc"], now))}) · page built {now.strftime("%Y-%m-%dT%H:%M:%SZ")}</div>')
    if snap["synthetic"]:
        p.append('<div class="banner">SYNTHETIC FIXTURE. Every number on this page is invented for layout work and is not the book.</div>')

    # system status first: is the system alive and did the day pass
    sysr = snap["system"]
    p.append("<h2>System status</h2>")
    if "value" in sysr:
        v = sysr["value"]
        cls = "pos" if v["verdict"] == "PASS" else "neg"
        p.append(f'<div class="card"><div class="n {cls}">{escape(v["verdict"])}</div><div>{escape(v["reason"])}</div>'
                 + (f'<ul>{"".join(f"<li>{escape(str(x))}</li>" for x in v["problems"])}</ul>' if v["problems"] else "")
                 + provenance(sysr) + "</div>")
    else:
        p.append(f'<div class="card">{gap(sysr)}</div>')

    a, pl = snap["account"], snap["pnl"]
    p.append("<h2>Account value and daily P&amp;L</h2><div class=\"grid\">")
    p.append(money_card("Account value (equity)", a["equity"]))
    p.append(money_card("Previous close equity", a["last_equity"]))
    p.append(money_card("P&L, official end-of-day", pl["official_eod_change_usd"], True))
    p.append(money_card("P&L, equity snapshot", pl["snapshot_change_usd"], True))
    p.append(money_card("P&L, auction-marked", pl["auction_pnl_usd"], True))
    p.append("</div>")

    h = snap["equity_history"]
    p.append("<h3>Account value history</h3>")
    if "value" in h:
        p.append(sparkline(h["value"]) + provenance(h))
        p.append(table(["Date", "Equity"], [(r["date"], usd(r["equity"])) for r in h["value"]], right=(1,)))
    else:
        p.append(gap(h))

    pos = snap["positions"]
    p.append("<h2>Positions</h2>")
    if "value" in pos:
        rows = [(r["symbol"], "long" if r["qty"] > 0 else "short" if r["qty"] < 0 else "flat", f'{r["qty"]:,}')
                for r in sorted(pos["value"], key=lambda r: r["symbol"])]
        p.append(table(["Symbol", "Side", "Shares"], rows, right=(2,)) + provenance(pos)
                 + '<div class="mut">Share counts only: this snapshot carries no position prices, so no market value is shown.</div>')
    else:
        p.append(gap(pos))

    tr = snap["trades"]
    p.append("<h2>Last day's trades and fills</h2>")
    if "value" in tr:
        o, f = tr["value"]["orders"], tr["value"]["fills"]
        p.append("<h3>Orders</h3>" + (table(["Symbol", "Side", "Qty", "Type", "Status"],
                 [(r["symbol"], r["side"], r["qty"], r.get("type", "n/a"), r["status"]) for r in o], right=(2,)) if o else "<p>No orders.</p>"))
        p.append("<h3>Fills</h3>" + (table(["Symbol", "Side", "Qty", "Price", "Time"],
                 [(r["symbol"], r["side"], r["qty"], f'{r["price"]:.2f}', r.get("time", "n/a")) for r in f], right=(2, 3)) if f else "<p>No fills.</p>"))
        p.append(provenance(tr))
    else:
        p.append(gap(tr))

    p.append("<h2>Data freshness</h2>" + table(["Item", "Read at (UTC)"], [
        ("Snapshot exported", snap["exported_at_utc"]),
        *[(n, (snap_get(snap, path).get("read_at", "no reading")))
          for n, path in (("Account", ("account", "equity")), ("P&L (official)", ("pnl", "official_eod_change_usd")),
                          ("Equity history", ("equity_history",)), ("Positions", ("positions",)),
                          ("Trades", ("trades",)), ("Verdict", ("system",)))]]))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>Credit book dashboard {escape(snap["session_date"])}</title><style>{CSS}</style></head>'
            f'<body>{"".join(p)}</body></html>')


def snap_get(snap: dict, path: tuple) -> dict:
    node = snap
    for k in path:
        node = node[k]
    return node


def build(path: Path, out: Path, now: dt.datetime | None = None) -> None:
    snap = json.loads(Path(path).read_text())
    problems = S.validate(snap) + S.find_private(snap)
    if problems:
        raise SystemExit("snapshot refused, no page written:\n  " + "\n  ".join(problems))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(snap, now), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("snapshot", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("dashboard/out/index.html"))
    a = ap.parse_args(argv)
    build(a.snapshot, a.out)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
