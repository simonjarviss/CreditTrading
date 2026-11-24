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
from dashboard.layout import (BOOK_COLOURS, BOOK_TEXT, COMBINED_COLOUR, fmt_date, fmt_short, page, page_head, pct, tone,
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

def risk_block(r: dict) -> str:
    if "value" not in r:
        return "<h3>Exposure</h3>" + gap(r, "Exposure")
    v = r["value"]
    rows = []
    if v["gross"] is not None:
        cap = f" (limit {v['cap']:.2f}x)" if v["cap"] is not None else ""
        rows.append(("Gross exposure, risk report", f"{v['gross']:.2f}x equity{cap}"))
    if v["net"] is not None:
        rows.append(("Net exposure, risk report", f"{v['net']:+.2f}x equity".replace("-", "\u2212")))
    if v.get("largest_share") is not None:
        rows.append(("Largest position", f"{pct(v['largest_share'], dp=1)} of equity"))
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
    """Fill quality over the last 20 measured sessions, then each session in a collapsed table."""
    if "value" not in r:
        return "<h3>Execution</h3>" + gap(r, "Execution record")
    rows = r["value"]["rows"][-20:]
    n_orders = sum(x["n_orders"] for x in rows)
    n_full = sum(x["n_full"] for x in rows)
    slips = [x["slip_bp"] for x in rows if x["slip_bp"] is not None]
    summary = [("Sessions measured", f"{len(rows)}"),
               ("Orders", f"{n_orders:,.0f}"),
               ("Filled in full", "none" if not n_orders else f"{n_full:,.0f} ({pct(n_full / n_orders, dp=1)})"),
               ("Cost against the official close", "not measured" if not slips else
                f"{sum(slips) / len(slips):+.1f} bp a session on average".replace("-", "\u2212")
                + f' <span class="meta">({len(slips)} sessions; + is worse)</span>')]
    body = [(fmt_short(x["date"]), f"{x['n_orders']:.0f}", f"{x['n_full']:.0f}",
             "none" if x["fill_rate"] is None else pct(x["fill_rate"], dp=1),
             "none" if x["slip_bp"] is None else f"{x['slip_bp']:+.1f}".replace("-", "\u2212")) for x in reversed(rows)]
    return ("<h3>Execution, last 20 sessions</h3>" + tbl(["Measure", "Value"], summary)
            + '<details class="data"><summary>Each session</summary>'
            + tbl(["Session", "Orders", "Filled in full", "Shares filled", "Cost vs close (bp)"], body, right=(1, 2, 3, 4))
            + f'<p class="meta">{escape(r["value"]["basis"])}.</p></details>' + prov(r))


def session_block(r: dict) -> str:
    """The night's session in aggregates: the verdict, positions held, exposure and orders.

    WHY (team lead, 2026-11-23, "aggregates only"): the page used to list every position by symbol
    with its shares and close, every order line, and the runners' own notes; the notes put client
    order ids on the public page. The snapshot now carries counts and dollar figures only
    (dashboard/snapshot.py 0.3), so this is all a page can show."""
    if "value" not in r:
        return "<h3>Latest session</h3>" + gap(r, "Session record")
    v = r["value"]
    p, o = v["positions"], v["orders"]
    status = "reconciled with the broker" if v["verdict"] == "PASS" else "flagged for review"
    notes = (f' The trading system recorded {v["n_notes"]} {"note" if v["n_notes"] == 1 else "notes"} for review.'
             if v["n_notes"] else "")
    rows = [("Session", f"{escape(status.capitalize())}")]
    if p["n"]:
        rows.append(("Positions after the close", f'{p["n"]} ({p["n_long"]} long, {p["n_short"]} short)'))
        if p["n_unpriced"]:
            one = p["n_unpriced"] == 1
            rows.append(("Exposure at the close", f'not measured: {p["n_unpriced"]} '
                                                  f'{"position has" if one else "positions have"} no close on record'))
        elif p["gross_x"] is not None:
            rows.append(("Gross exposure at the close", f'{p["gross_x"]:.2f}x equity ({usd(p["gross_usd"])})'))
            net_x = f'{p["net_x"]:+.2f}'.replace("-", "\u2212")
            rows.append(("Net exposure at the close", f'{net_x}x equity ({usd(p["net_usd"], True)})'))
    else:
        rows.append(("Positions after the close", "none"))
    if o["n"]:
        part = f', {o["n_partial"]} partly' if o["n_partial"] else ""
        rows.append(("Orders", f'{o["n"]} sent: {o["n_filled"]} filled in full{part}, {o["n_unfilled"]} not filled'))
        if o["fill_rate_shares"] is not None:
            rows.append(("Shares filled", pct(o["fill_rate_shares"], dp=1)))
    else:
        rows.append(("Orders", "none needed"))
    return (f"<h3>Session of {fmt_date(v['date'])}</h3>" + tbl(["Measure", "Value"], rows)
            + f'<p class="meta">Prices are the {escape(v["close_basis"])}.{notes} Holdings and '
              'orders are reported in aggregate.</p>' + prov(r))


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
    """One book in detail: what it trades, its official record's source, the latest session, its
    exposure and its execution. The headline statistics are in the comparison table above."""
    colour = BOOK_COLOURS.get(b["name"], COMBINED_COLOUR)
    o, sess = b["official"], b["session"]
    parts = [f'<section class="book" id="{escape(b["name"])}"><div class="book-head">'
             f'<span class="dot" style="background:{colour}"></span><h2>{escape(b["title"])}</h2></div>'
             f'<p class="book-text">{escape(BOOK_TEXT.get(b["name"], ""))}</p>']
    if "value" in o:
        parts.append(prov(o))
    else:
        parts.append(gap(o, "Official end-of-day history"))
        started = started_text(b)
        parts.append(f'<p class="meta">{escape(started[:1].upper() + started[1:])}.</p>')
        if "value" in sess and sess["value"].get("equity_snapshot"):
            e = sess["value"]["equity_snapshot"]
            ch, _ = session_pnl(b, sess["value"]["date"])
            parts.append('<div class="figures">'
                         + fig(usd(e["equity"]), f"Account equity, {fmt_short(sess['value']['date'])}")
                         + (fig(usd(ch, True), "That session") if ch is not None else "")
                         + f'</div><p class="meta">{escape(e["kind"])}.</p>')
    parts.append(sleeves_block(b["sleeves"]))
    parts.append('<div class="book-grid"><div>' + session_block(sess) + "</div><div>" + risk_block(b["risk"])
                 + "</div><div>" + execution_block(b["execution"]) + "</div></div>")
    parts.append("</section>")
    return "".join(parts)


PORTFOLIO_COLOUR = COMBINED_COLOUR


def portfolio(snap: dict) -> dict:
    """The books that trade, each from its first traded session, and their composite.

    A book's daily record is its official end-of-day history, or, while it has none, its
    after-close readings (the event book), labelled as such. A book that has not sent an order is
    left out and named. A book whose record could not be read is left out too, and named in a
    warning above the figures and in every label that sums the books, so the composite never reads
    as the whole without saying so. (Release-check review of 904bd35, 2026-11-24: withholding the
    whole portfolio over one book's unreadable record hid it until someone repaired the record.)"""
    books, excluded, blocked = [], [], []
    for b in snap["books"]:
        o, ac, st = b["official"], b.get("after_close", {}), b.get("start", {})
        if "value" in o:
            rows, kind = o["value"]["rows"], "official"
        elif S.UNMEASURED in o:
            blocked.append((b, "its official history could not be read"))
            continue
        elif "value" in ac:
            rows, kind = ac["value"]["rows"], "after-close"
        elif S.UNMEASURED in ac:
            blocked.append((b, "its after-close readings could not be read"))
            continue
        else:
            excluded.append((b, o.get("absent") or "no daily record yet"))
            continue
        if S.UNMEASURED in st:
            blocked.append((b, "the start of its trading could not be read"))
            continue
        if "value" not in st:
            excluded.append((b, "it has not sent an order yet"))
            continue
        first = st["value"]["first_send"]
        try:
            tr = M.trading_rows(rows, first)
            dated = M.daily(tr)
        except ValueError as e:
            blocked.append((b, str(e)))
            continue
        if not dated:
            excluded.append((b, "its first traded session has no closing record yet"))
            continue
        books.append({"b": b, "kind": kind, "first": first, "rows": tr, "base": tr[0]["date"], "dated": dated,
                      "p": M.profile(dated)})
    out = {"books": books, "excluded": excluded, "blocked": blocked, "dated": [], "comp": [], "left": 0,
           "p": None, "base": None, "first": None}
    if books:
        comp, left = M.composite({x["b"]["name"]: x["rows"] for x in books})
        if comp:
            dated = [(d, r, pnl) for d, r, pnl, _, _ in comp]
            out.update(dated=dated, comp=comp, left=left, p=M.profile(dated), base=min(x["base"] for x in books),
                       first=min(x["first"] for x in books))
    return out


def _na(p: dict) -> str:
    return f'<span class="meta">needs {M.MIN_RETURNS_FOR_RATIOS} sessions, has {p["n"]}</span>'


def _num(x, p, fmt) -> str:
    return _na(p) if x is None else fmt(x)


def _ratio_s(x) -> str:
    return f"{x:.2f}".replace("-", "−")


def _sgn(x) -> str:
    return f'<span class="{tone(x)}">{pct(x, True)}</span>'


def _dated_pct(t, signed=True) -> str:
    if t is None:
        return "none"
    return f'{pct(t[1], signed)} <span class="meta">({fmt_short(t[0])})</span>'


# One table of statistics, in groups, one column per series (metrics.profile has the definitions).
STAT_GROUPS = (
    ("Returns", (
        ("Last session", lambda p: "none" if p["last"] is None else _sgn(p["last"])),
        ("Last 5 sessions", lambda p: "none" if p["last5"] is None else _sgn(p["last5"])),
        ("Month to date", lambda p: "none" if p["mtd"] is None else _sgn(p["mtd"])),
        ("Since inception, time-weighted", lambda p: _sgn(p["cum_return"])),
        ("Annualised, time-weighted", lambda p: _num(p["ann_return"], p, _sgn)),
        ("P&L since inception", lambda p: f'<span class="{tone(p["pnl"])}">{usd(p["pnl"], True)}</span>'),
    )),
    ("Risk", (
        ("Volatility, annualised", lambda p: _num(p["vol"], p, pct)),
        ("Downside deviation, annualised", lambda p: _num(p["downside_dev"], p, pct)),
        ("Maximum drawdown", lambda p: "0.00%" if p["max_drawdown_date"] is None
         else _dated_pct((p["max_drawdown_date"], p["max_drawdown"]), False)),
        ("Current drawdown", lambda p: pct(p["drawdown"])),
        ("Longest drawdown", lambda p: f'{p["longest_drawdown"]} {"session" if p["longest_drawdown"] == 1 else "sessions"}'),
        ("Value at risk, 95%, one day", lambda p: _num(p["var95"], p, pct)),
        ("Expected shortfall, 95%, one day", lambda p: _num(p["es95"], p, pct)),
    )),
    ("Risk-adjusted return", (
        ("Sharpe ratio", lambda p: _num(p["sharpe"], p, _ratio_s)),
        ("Sortino ratio", lambda p: _num(p["sortino"], p, _ratio_s)),
        ("Calmar ratio", lambda p: _num(p["calmar"], p, _ratio_s)),
    )),
    ("Daily returns", (
        ("Sessions", lambda p: f'{p["n"]}'),
        ("Sessions with a gain", lambda p: "none" if p["hit_rate"] is None else
         f'{pct(p["hit_rate"], dp=0)} <span class="meta">of sessions that moved</span>'),
        ("Average gain", lambda p: "none" if p["avg_gain"] is None else pct(p["avg_gain"], True)),
        ("Average loss", lambda p: "none" if p["avg_loss"] is None else pct(p["avg_loss"], True)),
        ("Gain to loss ratio", lambda p: "none" if p["gain_loss_ratio"] is None else _ratio_s(p["gain_loss_ratio"])),
        ("Profit factor", lambda p: "none" if p["profit_factor"] is None else _ratio_s(p["profit_factor"])),
        ("Best session", lambda p: _dated_pct(p["best"])),
        ("Worst session", lambda p: _dated_pct(p["worst"])),
        ("Skewness", lambda p: _num(p["skew"], p, _ratio_s)),
        ("Excess kurtosis", lambda p: _num(p["kurt"], p, _ratio_s)),
    )),
)


def stats_table(cols: list) -> str:
    """cols: [(title, colour, profile)]."""
    th = "".join(f'<th class="r"><span class="dot" style="background:{c}"></span>{escape(n)}</th>' for n, c, _ in cols)
    body = []
    for group, rows in STAT_GROUPS:
        body.append(f'<tr class="grp"><td colspan="{len(cols) + 1}">{escape(group)}</td></tr>')
        body += [f'<tr><td>{escape(label)}</td>' + "".join(f'<td class="r">{f(p)}</td>' for _, _, p in cols) + "</tr>"
                 for label, f in rows]
    return (f'<div class="tbl-wrap"><table class="matrix stats"><thead><tr><th>Measure</th>{th}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def monthly_table(cols: list) -> str:
    """cols: [(title, colour, dated returns, cumulative)]. Each month's return compounds its sessions."""
    def by_month(dated):
        out = {}
        for d, r, _ in dated:
            out[d[:7]] = out.get(d[:7], 1.0) * (1.0 + r)
        return {m: v - 1.0 for m, v in out.items()}
    rows = [(n, c, by_month(dated), cum) for n, c, dated, cum in cols]
    months = sorted({m for _, _, d, _ in rows for m in d})
    head = "".join(f'<th class="r">{charts.MONTHS[int(m[5:]) - 1]} {m[:4]}</th>' for m in months)
    cell = lambda v: "" if v is None else _sgn(v)                                       # noqa: E731
    body = "".join(f'<tr><td><span class="dot" style="background:{c}"></span>{escape(n)}</td>'
                   + "".join(f'<td class="r">{cell(d.get(m))}</td>' for m in months)
                   + f'<td class="r total">{cell(cum)}</td></tr>' for n, c, d, cum in rows)
    return (f'<div class="tbl-wrap"><table class="matrix months"><thead><tr><th>Series</th>{head}'
            f'<th class="r">Since inception</th></tr></thead><tbody>{body}</tbody></table></div>')


def correlation_table(books: list) -> str:
    """The books' daily returns against each other, on the sessions each pair shares."""
    if len(books) < 2:
        return '<p class="meta">One book is trading, so there is no correlation to show yet.</p>'
    head = "".join(f'<th class="r"><span class="dot" style="background:{BOOK_COLOURS.get(x["b"]["name"], COMBINED_COLOUR)}">'
                   f'</span>{escape(x["b"]["title"])}</th>' for x in books)
    body = []
    for a in books:
        cells = []
        for b in books:
            if a is b:
                cells.append('<td class="r meta">1.00</td>')
                continue
            rho, n = M.corr_dated(a["dated"], b["dated"])
            cells.append(f'<td class="r">{_ratio_s(rho)} <span class="meta">({n})</span></td>' if rho is not None
                         else f'<td class="r"><span class="meta">n/a ({n})</span></td>')
        body.append(f'<tr><td><span class="dot" style="background:{BOOK_COLOURS.get(a["b"]["name"], COMBINED_COLOUR)}">'
                    f'</span>{escape(a["b"]["title"])}</td>{"".join(cells)}</tr>')
    return (f'<div class="tbl-wrap"><table class="matrix"><thead><tr><th>Daily returns</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            f'<p class="meta">Pearson correlation of daily returns; the number of sessions both books traded in '
            f'brackets. Shown once a pair shares {M.MIN_RETURNS_FOR_RATIOS} sessions.</p>')


def contribution_table(pf: dict) -> str:
    """Each book's P&L over the portfolio's sessions, and its share of the portfolio's P&L."""
    dates = {d for d, _, _ in pf["dated"]}
    rows, total = [], pf["p"]["pnl"]
    for x in pf["books"]:
        pnl = sum(v for d, _, v in x["dated"] if d in dates)
        share = (pnl / total) if total else None
        rows.append((f'<span class="dot" style="background:{BOOK_COLOURS.get(x["b"]["name"], COMBINED_COLOUR)}"></span>'
                     f'{escape(x["b"]["title"])}', fmt_short(x["first"]),
                     f'<span class="{tone(pnl)}">{usd(pnl, True)}</span>',
                     "none" if share is None else pct(share, dp=0)))
    rows.append(("<b>Portfolio</b>", fmt_short(pf["first"]),
                 f'<b class="{tone(total)}">{usd(total, True)}</b>', "100%"))
    return tbl(["Book", "First traded session", "P&L", "Share of portfolio P&L"], rows, right=(2, 3))


def session_pnl(b: dict, date: str) -> tuple:
    """(P&L of one session, its kind) as every figure on the page shows it: Alpaca's official change when
    it has landed; else, for a book whose daily record is its after-close readings, that record's change
    (the move between readings, export.after_close); else the session's own after-close reading. None
    when none exists. WHY (release-check review of 596ba7f): the event book's tile and its row took
    Alpaca's change while its record took the move between readings, so the same session read twice."""
    off = {r["date"]: r for r in b["official"]["value"]["rows"]} if "value" in b["official"] else {}
    if date in off and off[date]["change_usd"] is not None:
        return off[date]["change_usd"], "official"
    ac = b.get("after_close", {})
    if "value" in ac:
        row = next((r for r in ac["value"]["rows"] if r["date"] == date), None)
        if row is not None and row["change_usd"] is not None:
            return row["change_usd"], "after-close reading"
    e = (b["session"].get("value") or {}).get("equity_snapshot") if "value" in b["session"] else None
    if e and e.get("change_usd") is not None and not ("value" in ac):
        return e["change_usd"], "after-close reading"
    return None, None


def latest_sessions(books: list) -> str:
    """Each book's newest verified session, side by side, in aggregates, and the portfolio's sum when
    every trading book has a reading for the same session. A P&L is Alpaca's official figure when it
    has landed, else the after-close reading, labelled as such."""
    rows, sums, gross, net, eq, dates, complete = [], 0.0, 0.0, 0.0, 0.0, set(), True
    for b in books:
        sess = b["session"]
        name = (f'<span class="dot" style="background:{BOOK_COLOURS.get(b["name"], COMBINED_COLOUR)}"></span>'
                f'{escape(b["title"])}')
        if "value" not in sess:
            rows.append((name, '<span class="meta">not measured</span>' if S.UNMEASURED in sess
                         else '<span class="meta">none yet</span>', "", "", "", "", ""))
            complete = False
            continue
        v = sess["value"]
        dates.add(v["date"])
        e = v.get("equity_snapshot")
        ch, kind = session_pnl(b, v["date"])
        if ch is not None:
            pnl = f'<span class="{tone(ch)}">{usd(ch, True)}</span> <span class="meta">{kind}</span>'
        else:
            pnl = '<span class="meta">not measured</span>'
            complete = False
        p, o = v["positions"], v["orders"]
        held = f'{p["n"]} <span class="meta">({p["n_long"]} long, {p["n_short"]} short)</span>' if p["n"] else "none"
        if p["n"] and (p["n_unpriced"] or p["gross_x"] is None):
            ex = '<span class="meta">not measured</span>'
            complete = False
        elif p["n"]:
            ex = f'{p["gross_x"]:.2f}x / ' + f'{p["net_x"]:+.2f}x'.replace("-", "−")
        else:
            ex = "none"
        if ch is not None and e and e.get("equity") is not None and (p["gross_usd"] is not None or not p["n"]):
            sums += ch
            gross += p["gross_usd"] or 0.0
            net += p["net_usd"] or 0.0
            eq += e["equity"]
        else:
            complete = False
        orders = f'{o["n_filled"]} of {o["n"]}' if o["n"] else "none needed"
        check = "Reconciled" if v["verdict"] == "PASS" else '<span class="neg">Flagged for review</span>'
        rows.append((name, fmt_short(v["date"]), pnl, held, ex, orders, check))
    if complete and len(dates) == 1 and eq:
        rows.append(("<b>Portfolio</b>", fmt_short(next(iter(dates))),
                     f'<b class="{tone(sums)}">{usd(sums, True)}</b>', "",
                     f'{gross / eq:.2f}x / ' + f'{net / eq:+.2f}x'.replace("-", "−"), "", ""))
    return ('<div class="latest">' + tbl(["Book", "Session", "P&L", "Positions", "Gross / net exposure", "Orders filled",
                                          "Check"], rows, right=(2, 3, 4, 5, 6)) + "</div>")


def portfolio_section(snap: dict) -> str:
    """The page's top (team lead, 2026-11-24: "overall portfolio (shown as one line), can split into
    3 lines (our sleeves) and analyze below (all things institutional investors would look at)").
    The portfolio's line, and its books' on a switch; drawdown; each session's P&L; then returns,
    risk, risk-adjusted return and the distribution of daily returns side by side; correlation;
    each book's contribution; monthly returns; and the latest session's positioning."""
    books = snap["books"]
    pf = portfolio(snap)
    warn = ""
    if pf["blocked"]:
        why = "; ".join(f"{escape(b['title'])}: {escape(w)}" for b, w in pf["blocked"])
        warn = (f'<p class="gap">Not included tonight, because its record could not be read: {why}. The portfolio '
                'below is the other books only.</p>')
    if not pf["p"]:
        # Say why there is no portfolio (release-check review of 455eff4: with every book unreadable,
        # "no traded session yet" was false and dropped the reason).
        why = ('<p class="gap">No portfolio tonight. '
               + "; ".join([f"{escape(b['title'])}: its record could not be read ({escape(w)})" for b, w in pf["blocked"]]
                           + [f"{escape(b['title'])}: {escape(w)}" for b, w in pf["excluded"]]) + ".</p>"
               if pf["blocked"] else '<p class="gap">No book has a traded session on record yet.</p>')
        return ('<section class="section"><div class="wrap"><div class="eyebrow">Portfolio</div>'
                f'<h2>Portfolio results</h2>{why}</div></section>')
    p = pf["p"]
    colour = lambda x: BOOK_COLOURS.get(x["b"]["name"], COMBINED_COLOUR)                    # noqa: E731
    members = "; ".join(f'{escape(x["b"]["title"])} from {fmt_short(x["first"])}'
                        + (" (after-close readings until its end-of-day history begins)" if x["kind"] == "after-close" else "")
                        for x in pf["books"])
    left = (f' {pf["left"]} {"session is" if pf["left"] == 1 else "sessions are"} left out because a trading book has no '
            'record for it yet.' if pf["left"] else "")
    out_txt = ("".join(f' {escape(b["title"])} is not included: {escape(w)}.' for b, w in pf["excluded"]))
    # Return and P&L are shown apart and the return is named time-weighted: on 2026-11-24 the portfolio
    # read +0.06% beside -$472, both right, because its losses fell when three books were trading and
    # its gains when one was. A reader shown "+0.06% (-$472)" would read an error.
    kpis = [fig(pct(p["cum_return"], True), f"Time-weighted return since {fmt_short(pf['first'])}"),
            fig(usd(p["pnl"], True), f"P&amp;L since {fmt_short(pf['first'])}"),
            fig(_ratio_s(p["sharpe"]) if p["sharpe"] is not None else "n/a", f"Sharpe ratio ({p['n']} sessions)"),
            fig(pct(p["vol"]) if p["vol"] is not None else "n/a", "Volatility, annualised"),
            fig(pct(p["max_drawdown"]), "Maximum drawdown")]
    growth = [{"name": "Portfolio", "color": PORTFOLIO_COLOUR, "bold": True,
               "points": M.index_points(pf["dated"], pf["base"])}]
    under = [{"name": "Portfolio", "color": PORTFOLIO_COLOUR, "bold": True,
              "points": M.drawdown_index(pf["dated"], pf["base"])}]
    for x in pf["books"]:
        growth.append({"name": x["b"]["title"], "color": colour(x), "cls": "bk",
                       "points": M.index_points(x["dated"], x["base"])})
        under.append({"name": x["b"]["title"], "color": colour(x), "cls": "bk",
                      "points": M.drawdown_index(x["dated"], x["base"])})
    switch = ('<div class="view-switch" role="group" aria-label="Chart view" hidden>'
              '<button type="button" data-view="portfolio" aria-pressed="true">Portfolio</button>'
              '<button type="button" data-view="books" aria-pressed="false">By book</button></div>')
    cols = [("Portfolio", PORTFOLIO_COLOUR, p)] + [(x["b"]["title"], colour(x), x["p"]) for x in pf["books"]]
    mcols = [("Portfolio", PORTFOLIO_COLOUR, pf["dated"], p["cum_return"])] + [
        (x["b"]["title"], colour(x), x["dated"], x["p"]["cum_return"]) for x in pf["books"]]
    return (f'<section class="section"><div class="wrap">'
            f'<div class="eyebrow">Portfolio &middot; to {fmt_short(p["last_date"])}</div>'
            f'<h2>Portfolio results</h2><p class="narrow">A composite of the books that are trading, each from its '
            f'first traded session: {members}. Each session\'s return is the books\' combined P&amp;L over their '
            f'combined equity at the previous close.{left}{out_txt}</p>{warn}'
            f'<div class="figures kpis">{"".join(kpis)}</div>'
            f'<div class="chart-head"><h3 class="chart-title">Growth since inception</h3>{switch}</div>'
            + charts.line_chart(growth, "Cumulative return of the portfolio and of each book", fmt="pct")
            + '<h3 class="chart-title">Drawdown from the peak</h3>'
            + charts.line_chart(under, "Drawdown of the portfolio and of each book", fmt="pct", height=250)
            + '<h3 class="chart-title">Portfolio P&amp;L of each session</h3>'
            + charts.bar_chart([(d, v) for d, _, v in pf["dated"]], "Portfolio P&L of each session", height=230)
            + '<h3 class="block-title">Performance and risk</h3>' + stats_table(cols)
            + '<h3 class="block-title">Monthly returns</h3>' + monthly_table(mcols)
            + '<h3 class="block-title">Contribution to portfolio P&amp;L</h3>' + contribution_table(pf)
            + '<h3 class="block-title">Correlation of daily returns</h3>' + correlation_table(pf["books"])
            + '<h3 class="block-title">Latest session</h3>' + latest_sessions(books)
            + '<p class="meta">Returns compound each session\'s return. Hover over a chart for each session\'s values. '
              'A session\'s P&amp;L is the after-close reading until Alpaca publishes its official end-of-day figure '
              'overnight.</p></div></section>')


def started_text(b: dict) -> str:
    """When a book began trading, in words, from its `start` reading (the first STARTED record).

    WHY (release-check review, 2026-11-23): this used to print the newest session's date as
    "trading since", a date that moves forward every session, and called a book whose record could
    not be read "no record yet"."""
    st = b.get("start", {})
    if S.UNMEASURED in st:
        return "the start of its trading could not be read tonight"
    if "value" not in st:
        return "no order sent yet"
    return f"trading since {fmt_short(st['value']['first_send'])}"


def summary_table(snap: dict) -> str:
    """The portfolio and each trading book, from each one's first traded session: the figures an
    allocator reads first (the overview's table; the performance page has the full set)."""
    pf = portfolio(snap)
    dot = lambda c: f'<span class="dot" style="background:{c}"></span>'                    # noqa: E731
    rows = []

    def row(name, colour, since, p):
        ratio = (f'{_ratio_s(p["sharpe"])} <span class="meta">({p["n"]} sessions)</span>' if p["sharpe"] is not None
                 else f'<span class="meta">{p["n"]} sessions; needs {M.MIN_RETURNS_FOR_RATIOS}</span>')
        rows.append((dot(colour) + name, fmt_short(since), f'<span class="{tone(p["pnl"])}">{usd(p["pnl"], True)}</span>',
                     _sgn(p["cum_return"]), ratio, pct(p["max_drawdown"])))

    if pf["p"]:
        row("<b>Portfolio</b>", PORTFOLIO_COLOUR, pf["first"], pf["p"])
    for x in pf["books"]:
        row(escape(x["b"]["title"]), BOOK_COLOURS.get(x["b"]["name"], COMBINED_COLOUR), x["first"], x["p"])
    for b, why in pf["excluded"] + pf["blocked"]:
        rows.append((dot(BOOK_COLOURS.get(b["name"], COMBINED_COLOUR)) + escape(b["title"]),
                     f'<span class="meta">{escape(why[:1].upper() + why[1:])}</span>', "", "", "", ""))
    head = ["", "From", "P&L", "Return, time-weighted", "Sharpe", "Max drawdown"]
    th = "".join(f'<th class="{"r" if i >= 2 else ""}">{escape(h)}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td class="{"r" if i >= 2 else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f'<div class="tbl-wrap"><table class="summary"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


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
<p><b>The portfolio.</b> A composite of the books that are trading, each from its first traded session, so an account's idle cash before it trades never dilutes the result. Each session's return is the books' combined P&amp;L divided by their combined equity at the previous close, and the returns compound: the return is time-weighted, the standard for a composite. Because a session counts by its return and not by its dollars, the portfolio's return and its dollar P&amp;L can differ, even in sign, when the capital trading changes, as it does when a book joins. A session on which a trading book has no record is left out, never filled. The event book counts from its first traded session; until Alpaca's end-of-day history is collected for it, its daily figures are the account equity read after each close.</p><p><b>Statistics.</b> Daily return is the day's change in equity divided by the previous day's equity. Volatility, downside deviation, the Sharpe, Sortino and Calmar ratios, value at risk, expected shortfall, skewness and kurtosis are shown once a series has 20 sessions, and are annualised with 252 sessions where they are rates. No ratio subtracts a risk-free rate. The Sortino ratio divides by the downside deviation of daily returns; the Calmar ratio divides the annualised return by the maximum drawdown. Value at risk and expected shortfall are historical and one-day: the 5th percentile of daily returns and the average of the returns at or below it. Drawdown is measured on the compounded return from its running peak. A record of a few dozen sessions measures every ratio only loosely.</p>
<p><b>Positions and orders.</b> Taken from the trading system's reconciliation with the broker after each close and reported in aggregate: how many positions each book holds, its gross and net exposure at the closing price, and how many orders were filled. Individual holdings and orders are not published.</p>
<p><b>Updates.</b> The page rebuilds automatically every 30 minutes from the trading system's records, so a session appears shortly after the close and its official figure after Alpaca publishes it overnight. A figure the system could not read is marked as not measured; it is never estimated or carried forward.</p>
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
    return (head + banner + portfolio_section(snap)
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
