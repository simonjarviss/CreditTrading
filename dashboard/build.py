"""The live performance page: every book, from one snapshot (dashboard/snapshot.py 0.2).

    python3 -m dashboard.build dashboard/fixtures/sample_snapshot.json -o /tmp/perf.html

Lucy's first draft (PR #62) set the rules this page keeps: every figure prints with its
source, read time and label; a gap prints as a gap, never as zero or blank; a snapshot
that fails validation or carries anything the README forbids is refused and no page is
written. 0.2 (team lead, 2026-11-23) widens it from one book to every active book, adds
the statistics an allocator reads (dashboard/metrics.py, the same definitions as
ops/orient.py) and puts it inside the public site's shell (dashboard/layout.py).

READ-ONLY BY CONSTRUCTION. It reads one JSON object and returns HTML. It imports only the
standard library and the dashboard package: no network, no subprocess, nothing from
quantt/ or ops/ (dashboard/tests pin that by AST).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from html import escape
from pathlib import Path

from dashboard import charts, metrics as M, snapshot as S
from dashboard.layout import (BOOK_COLOURS, COMBINED_COLOUR, fmt_date, fmt_short, page, page_head, pct, tone,
                              usd, when)

# Display names of the event strategies and the shadow books, in the investor deck's words.
STRATEGY_NAMES = {
    "cef_exdate_after": "Fund ex-date, short after",
    "cef_exdate_before_after": "Fund ex-date, both sides",
    "units_exdate_after": "Unit ex-date, short after",
    "units_exdate_before_after": "Unit ex-date, both sides",
    "specdiv_wait": "Special dividend",
    "specdiv_wait_small": "Special dividend, small caps",
    "pead_small_long": "Earnings drift",
    "uit_termination": "Unit trust termination",
    "uit_termination_big_sale": "Unit trust termination, large sales",
    "month_end_ief": "Month-end Treasuries",
    "spinoff_first_week": "Spin-off, first week",
}


def strategy_name(slug: str) -> str:
    return STRATEGY_NAMES.get(slug, slug)


def prov(r: dict) -> str:
    return (f'<p class="prov">Source: {escape(r["source"])} · read {escape(when(r["read_at"]))} · '
            f'{escape(r["label"])}</p>')


def gap(r: dict, what: str) -> str:
    if S.UNMEASURED in r:
        return f'<p><span class="gap">{escape(what)}: not measured.</span> <span class="meta">{escape(r[S.UNMEASURED])}</span></p>'
    return f'<p class="meta">{escape(what)}: {escape(r["absent"])}.</p>'


def fig(n: str, label: str, cls: str = "") -> str:
    return f'<div class="fig"><div class="n {cls}">{n}</div><div class="l">{label}</div></div>'


def tbl(head: list, rows: list, right: tuple = ()) -> str:
    th = "".join(f'<th class="{"r" if i in right else ""}">{escape(h)}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td class="{"r" if i in right else ""}">{c}</td>' for i, c in enumerate(row))
                   + "</tr>" for row in rows)
    return f'<div class="tbl-wrap"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def cum_points(rows: list) -> list:
    rows = M.funded(rows)
    base = rows[0]["equity"]
    return [(r["date"], r["equity"] - base) for r in rows]


# ------------------------------------------------------------------ sections --

def latest_figure(s: dict, sess: dict) -> str:
    """The newest session's after-close P&L, when it is newer than the official history.

    Alpaca publishes a session's end-of-day point during the night, so for a few hours after
    each close the official series ends one session behind. The verify step reads the account
    right after the close; that reading is shown, labelled, until the official point lands."""
    if "value" not in sess:
        return ""
    v = sess["value"]
    e = v.get("equity_snapshot")
    if not e or e.get("change_usd") is None or v["date"] <= s["last_date"]:
        return ""
    return fig(usd(e["change_usd"], True), f"{fmt_short(v['date'])} session, after-close reading "
                                           f"(official figure to follow)", tone(e["change_usd"]))


def stats_figures(s: dict, sess: dict | None = None) -> str:
    out = [fig(usd(s["equity"]), f"Account equity, {fmt_short(s['last_date'])}"),
           fig(usd(s["cum_pnl"], True), f"P&amp;L since {fmt_short(s['first_date'])} ({pct(s['cum_return'], True)})",
               tone(s["cum_pnl"])),
           fig(usd(s["last_change"], True) if s["last_change"] is not None else "none",
               f"Session of {fmt_short(s['last_date'])}", tone(s["last_change"]))]
    if sess is not None and latest_figure(s, sess):
        out.append(latest_figure(s, sess))
    if s["sharpe"] is not None:
        out.append(fig(f"{s['sharpe']:.2f}", f"Sharpe ratio, annualised ({s['n_returns']} sessions)"))
        out.append(fig(pct(s["vol"]), "Volatility, annualised"))
    else:
        out.append(fig("not yet", f"Sharpe ratio: needs {M.MIN_RETURNS_FOR_RATIOS} sessions, has {s['n_returns']}"))
    out.append(fig(pct(s["max_drawdown"]), f"Maximum drawdown ({fmt_short(s['max_drawdown_date'])})",
                   tone(s["max_drawdown"])))
    out.append(fig(pct(s["drawdown"]), f"Current drawdown from the peak of {usd(s['hwm'])}", tone(s["drawdown"])))
    return '<div class="figures">' + "".join(out) + "</div>"


def monthly_table(rows: list) -> str:
    ms = M.monthly(rows)
    if not ms:
        return ""
    body = [(dt.date.fromisoformat(m + "-01").strftime("%B %Y"),
             f'<span class="{tone(p)}">{usd(p, True)}</span>', f'<span class="{tone(r)}">{pct(r, True)}</span>')
            for m, p, r in ms]
    return "<h3>Monthly results</h3>" + tbl(["Month", "P&L", "Return"], body, right=(1, 2))


def risk_block(r: dict) -> str:
    if "value" not in r:
        return "<h3>Exposure</h3>" + gap(r, "Exposure")
    v = r["value"]
    rows = []
    if v["gross"] is not None:
        cap = f" (limit {v['cap']:.2f}x)" if v["cap"] is not None else ""
        rows.append(("Gross exposure", f"{v['gross']:.2f}x equity{cap}"))
    if v["net"] is not None:
        rows.append(("Net exposure", f"{v['net']:+.2f}x equity"))
    if v.get("largest"):
        lg = v["largest"]
        rows.append(("Largest position", f"{escape(str(lg['symbol']))}, {escape(str(lg['side']))}, "
                                         f"{pct(lg['share'], dp=1)} of equity"))
    if v["top3_share"] is not None:
        rows.append(("Three largest positions", f"{pct(v['top3_share'], dp=1)} of equity"))
    if v.get("halve_drawdown") is not None and v.get("kill_drawdown") is not None:
        rows.append(("Drawdown limits", f"size halved at {pct(v['halve_drawdown'], dp=0)}, "
                                        f"book closed at {pct(v['kill_drawdown'], dp=0)}"))
    groups = "".join(f"<tr><td>{escape(k.replace('_', ' '))}</td><td class=\"r\">{pct(x, dp=1)}</td></tr>"
                     for k, x in sorted(v["groups"].items(), key=lambda kv: -(kv[1] or 0)) if x is not None)
    return ("<h3>Exposure</h3>" + tbl(["Measure", "Value"], rows)
            + (f'<details class="data"><summary>Exposure by fund group (gross, as a share of equity)</summary>'
               f'<div class="tbl-wrap"><table><tbody>{groups}</tbody></table></div></details>' if groups else "")
            + prov(r) + f'<p class="meta">Risk report as of {fmt_date(v["asof"])}.</p>')


def execution_block(r: dict) -> str:
    if "value" not in r:
        return "<h3>Execution quality</h3>" + gap(r, "Execution record")
    rows = r["value"]["rows"][-10:]
    body = [(fmt_short(x["date"]), f"{x['n_orders']:.0f}", f"{x['n_full']:.0f}",
             "none" if x["fill_rate"] is None else pct(x["fill_rate"], dp=1),
             "none" if x["slip_bp"] is None else f"{x['slip_bp']:+.1f}") for x in reversed(rows)]
    return ("<h3>Execution quality</h3>"
            + tbl(["Session", "Orders", "Filled in full", "Fill rate", "Cost vs close (bp)"], body, right=(1, 2, 3, 4))
            + f'<p class="meta">{escape(r["value"]["basis"])}.</p>' + prov(r))


def positions_block(r: dict) -> str:
    if "value" not in r:
        return "<h3>Positions</h3>" + gap(r, "Positions")
    v = r["value"]
    pos = [p for p in v["positions"] if p["qty"]]
    if not pos:
        return f"<h3>Positions</h3><p>No positions after the close on {fmt_date(v['date'])}.</p>" + prov(r)
    priced = [p for p in pos if p["close"] is not None]
    gross = sum(abs(p["qty"] * p["close"]) for p in priced)
    body = []
    for p in sorted(pos, key=lambda p: -abs(p["qty"] * (p["close"] or 0))):
        mv = None if p["close"] is None else p["qty"] * p["close"]
        body.append((escape(p["symbol"]), "Long" if p["qty"] > 0 else "Short", f"{abs(p['qty']):,.0f}",
                     "none" if p["close"] is None else f"${p['close']:,.2f}",
                     "none" if mv is None else usd(mv),
                     "none" if mv is None or not gross else pct(abs(mv) / gross, dp=1)))
    unpriced = len(pos) - len(priced)
    one = unpriced == 1
    note = (f'<p class="meta">{unpriced} {"position has" if one else "positions have"} no close on record and '
            f'{"is" if one else "are"} left out of the gross total.</p>' if unpriced else "")
    return (f"<h3>Positions after the close, {fmt_date(v['date'])}</h3>"
            + tbl(["Symbol", "Side", "Shares", "Close", "Market value", "Share of gross"], body, right=(2, 3, 4, 5))
            + f'<p class="meta">Long {sum(1 for p in pos if p["qty"] > 0)}, short {sum(1 for p in pos if p["qty"] < 0)}. '
              f'Prices are the {escape(v["close_basis"])}.</p>' + note + prov(r))


def orders_block(r: dict) -> str:
    if "value" not in r:
        return ""
    v = r["value"]
    o = v["orders"]
    status = ("reconciled with the broker" if v["verdict"] == "PASS" else "flagged for review")
    probs = ""
    if v["problems"]:
        probs = ('<details class="data"><summary>Review notes</summary><ul>'
                 + "".join(f"<li>{escape(p)}</li>" for p in v["problems"]) + "</ul></details>")
    if not o:
        return (f"<h3>Orders, {fmt_date(v['date'])}</h3><p>No orders were needed. Session {status}.</p>" + probs)
    body = [(escape(x["symbol"]), x["side"].capitalize(), f"{x['qty']:,.0f}",
             "none" if x["filled_qty"] is None else f"{x['filled_qty']:,.0f}",
             "none" if x["avg_price"] is None else f"${x['avg_price']:,.2f}", escape(x["status"].replace("_", " ")))
            for x in o]
    return (f"<h3>Orders, {fmt_date(v['date'])}</h3>"
            + tbl(["Symbol", "Side", "Ordered", "Filled", "Average price", "Status"], body, right=(2, 3, 4))
            + f'<p class="meta">Session {status}.</p>' + probs)


def sleeves_block(r: dict) -> str:
    if "value" not in r:
        return "" if "absent" in r else "<h3>Strategies</h3>" + gap(r, "Strategy scores")
    rows = [x for x in r["value"]["rows"] if x["slug"] != "_book"]
    if not rows:
        return ""
    latest = {}
    for x in rows:
        latest[x["slug"]] = x                     # file order: the last row per strategy is its newest
    last_date = max(x["date"] for x in latest.values())
    body = [(escape(strategy_name(s)), "none" if x["capital_usd"] is None else usd(x["capital_usd"]),
             f"{x['n_names']:.0f}",
             "none" if x["day_change"] is None else f'<span class="{tone(x["day_change"])}">{usd(x["day_change"], True)}</span>',
             "none" if x["pnl"] is None else f'<span class="{tone(x["pnl"])}">{usd(x["pnl"], True)}</span>')
            for s, x in sorted(latest.items(), key=lambda kv: strategy_name(kv[0]))]
    return (f"<h3>Strategies, {fmt_date(last_date)}</h3>"
            + tbl(["Strategy", "Capital", "Positions", "Last session", "P&L to date"], body, right=(1, 2, 3, 4))
            + f'<p class="meta">{escape(r["value"]["basis"])}.</p>' + prov(r))


def book_section(b: dict) -> str:
    colour = BOOK_COLOURS.get(b["name"], COMBINED_COLOUR)
    o, sess = b["official"], b["session"]
    parts = [f'<section class="book" id="{escape(b["name"])}"><div class="book-head">'
             f'<span class="dot" style="background:{colour}"></span><h2>{escape(b["title"])}</h2></div>']
    if "value" in o:
        rows = o["value"]["rows"]
        s = M.summary(rows)
        parts.append(stats_figures(s, sess) + prov(o))
        if len(rows) >= 2:
            parts.append(charts.line_chart([{"name": b["title"], "color": colour, "points": cum_points(rows)}],
                                           f"{b['title']}: cumulative P&L, official"))
    else:
        parts.append(gap(o, "Official end-of-day history"))
        if "value" in sess and sess["value"].get("equity_snapshot"):
            e = sess["value"]["equity_snapshot"]
            parts.append('<div class="figures">'
                         + fig(usd(e["equity"]), f"Account equity, {fmt_short(sess['value']['date'])}")
                         + (fig(usd(e["change_usd"], True), "That session", tone(e["change_usd"]))
                            if e["change_usd"] is not None else "")
                         + f'</div><p class="meta">{escape(e["kind"])}.</p>' + prov(sess))
    parts.append(sleeves_block(b["sleeves"]))
    parts.append('<div class="cols"><div>' + risk_block(b["risk"]) + "</div><div>"
                 + execution_block(b["execution"]) + "</div></div>")
    parts.append(positions_block(sess))
    parts.append(orders_block(sess))
    if "value" in o:
        parts.append(monthly_table(o["value"]["rows"]))
    parts.append("</section>")
    return "".join(parts)


def summary_table(snap: dict) -> str:
    """One row per book with an official history: the figures an allocator reads first."""
    rows = []
    for b in snap["books"]:
        o = b["official"]
        if "value" not in o:
            started = (f'trading since {fmt_short(b["session"]["value"]["date"])}' if "value" in b["session"]
                       else "no record yet")
            rows.append((f'<span class="dot" style="background:{BOOK_COLOURS.get(b["name"], "#111418")}"></span>'
                         f'{escape(b["title"])}', f'<span class="meta">Official history to follow; {started}</span>',
                         "", "", "", "", ""))
            continue
        s = M.summary(o["value"]["rows"])
        rows.append((f'<span class="dot" style="background:{BOOK_COLOURS.get(b["name"], "#111418")}"></span>'
                     f'{escape(b["title"])}', fmt_short(s["first_date"]), usd(s["equity"]),
                     f'<span class="{tone(s["cum_pnl"])}">{usd(s["cum_pnl"], True)}</span>',
                     f'<span class="{tone(s["cum_return"])}">{pct(s["cum_return"], True)}</span>',
                     "n/a" if s["sharpe"] is None else f'{s["sharpe"]:.2f}', pct(s["max_drawdown"])))
    head = ["Book", "Since", "Equity", "P&L", "Return", "Sharpe", "Max drawdown"]
    th = "".join(f'<th class="{"r" if i >= 2 else ""}">{escape(h)}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td class="{"r" if i >= 2 else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f'<div class="tbl-wrap"><table class="summary"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def combined_section(books: list) -> str:
    series = {b["name"]: b["official"]["value"]["rows"] for b in books if "value" in b["official"]}
    if not series:
        return '<section class="section"><div class="wrap"><p class="gap">No account has an official history to show.</p></div></section>'
    rows, left_out = M.combined(series)
    s = M.summary(rows)
    names = ", ".join(b["title"] for b in books if b["name"] in series)
    lines = [{"name": b["title"], "color": BOOK_COLOURS.get(b["name"], COMBINED_COLOUR),
              "points": cum_points(series[b["name"]])} for b in books if b["name"] in series]
    if len(series) > 1:
        lines.append({"name": "Accounts combined", "color": COMBINED_COLOUR, "points": cum_points(rows), "bold": True})
    missing = [b for b in books if b["name"] not in series]
    miss_txt = ""
    if missing:
        miss_txt = ('<p class="meta">Not yet in the combined figures: '
                    + "; ".join(f"{escape(b['title'])} ({escape(b['official'].get('absent') or b['official'].get(S.UNMEASURED, ''))})"
                                for b in missing) + ".</p>")
    return (f'<section class="section"><div class="wrap"><div class="eyebrow">All accounts</div>'
            f'<h2>Combined paper results</h2>'
            f'<p class="narrow">The sum of the accounts with an official end-of-day history: {escape(names)}. '
            f'The combined figures use the {len(rows)} sessions every one of them has a record for'
            + (f', leaving out {left_out} {"session" if left_out == 1 else "sessions"} that only some of them have.'
               if left_out else '.') + '</p>'
            '<div class="figures">'
            + fig(usd(s["equity"]), f"Combined equity, {fmt_short(s['last_date'])}")
            + fig(usd(s["cum_pnl"], True), f"P&amp;L since {fmt_short(s['first_date'])} ({pct(s['cum_return'], True)})",
                  tone(s["cum_pnl"]))
            + fig(usd(s["last_change"], True) if s["last_change"] is not None else "none",
                  f"Session of {fmt_short(s['last_date'])}", tone(s["last_change"]))
            + fig(pct(s["drawdown"]), f"Drawdown from the peak of {usd(s['hwm'])}", tone(s["drawdown"]))
            + "</div>"
            + charts.line_chart(lines, "Cumulative P&L of each account and combined, official end-of-day equity")
            + summary_table({"books": books})
            + '<p class="meta">Cumulative P&amp;L in dollars from each account\'s first funded day. '
              'Hover for each session\'s values.</p>' + miss_txt + "</div></section>")


def shadow_section(r: dict) -> str:
    head = ('<section class="section soft"><div class="wrap"><div class="eyebrow">Incubation</div>'
            '<h2>Strategies in simulation</h2>'
            '<p class="narrow">New strategies run first as simulated books on live data before they receive a '
            'paper account. These figures are simulated and are not trading results.</p>')
    if "value" not in r:
        return head + gap(r, "Shadow scoreboard") + "</div></section>"
    v = r["value"]
    body = [(escape(strategy_name(x["book"])), fmt_short(x["started"]), f"{x['scored']:.0f}", f"{x['flat']:.0f}",
             "none" if x["pnl_total"] is None else f'<span class="{tone(x["pnl_total"])}">{usd(x["pnl_total"], True)}</span>',
             "none" if x.get("max_drawdown") is None else pct(x["max_drawdown"]))
            for x in v["rows"]]
    return (head + f"<h3>Scoreboard, {fmt_date(v['asof'])}</h3>"
            + tbl(["Strategy", "Started", "Sessions with a position", "Sessions flat", "Simulated P&L", "Maximum drawdown"],
                  body, right=(2, 3, 4, 5))
            + f'<p class="meta">{escape(v["basis"]).capitalize()}.</p>' + prov(r) + "</div></section>")


METHOD = """<section class="section"><div class="wrap narrow"><div class="eyebrow">Method</div><h2>How these figures are produced</h2>
<p><b>Official P&amp;L.</b> Each account's results come from Alpaca's end-of-day portfolio history, the record we report against. A paper account differs from a live account in three ways: it charges no stock borrow fees, it does not credit or debit distributions on positions, and it fills orders at the current quote rather than in the closing auction. A live account's results would differ for those reasons.</p>
<p><b>Statistics.</b> Daily return is the day's change in equity divided by the previous day's equity. Volatility and the Sharpe ratio are annualised with 252 sessions and shown once a book has 20 sessions; the Sharpe ratio subtracts no risk-free rate. Drawdown is measured from the running peak of end-of-day equity.</p>
<p><b>Positions and orders.</b> Taken from the trading system's reconciliation with the broker after each close. Market values use each fund's closing price.</p>
<p><b>Updates.</b> The page rebuilds automatically each evening after the close and each morning after the broker publishes the previous day's end-of-day equity. A figure the system could not read is marked as not measured; it is never estimated or carried forward.</p>
</div></section>"""


def render_body(snap: dict) -> str:
    exported = snap["exported_at_utc"]
    banner = ('<div class="wrap"><p class="gap" style="margin-top:20px">Synthetic data: every number on this page is '
              'invented for testing and is not the book.</p></div>') if snap["synthetic"] else ""
    head = page_head("Performance", "Live performance",
                     "Daily results of our three paper-trading accounts at Alpaca, built automatically from the "
                     "trading system's own records.",
                     f'<p class="meta" style="color:rgba(255,255,255,0.7);margin-top:14px">Updated {escape(when(exported))}. '
                     'Paper trading only: no client capital is invested.</p>')
    books = "".join(book_section(b) for b in snap["books"])
    return (head + banner + combined_section(snap["books"])
            + f'<section class="section" style="padding-top:0"><div class="wrap">{books}</div></section>'
            + shadow_section(snap["shadow"]) + METHOD)


def render(snap: dict) -> str:
    return page("performance", "Live performance", render_body(snap),
                "Live paper-trading results of the Event Driven Trading team's three books.")


def check(snap: dict) -> list:
    return S.validate(snap) + S.find_private(snap)


def build(path: Path, out: Path) -> None:
    snap = json.loads(Path(path).read_text())
    problems = check(snap)
    if problems:
        raise SystemExit("snapshot refused, no page written:\n  " + "\n  ".join(problems))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(snap), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("snapshot", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("dashboard/out/performance/index.html"))
    a = ap.parse_args(argv)
    build(a.snapshot, a.out)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
