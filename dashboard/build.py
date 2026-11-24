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
            parts.append('<div class="figures">'
                         + fig(usd(e["equity"]), f"Account equity, {fmt_short(sess['value']['date'])}")
                         + (fig(usd(e["change_usd"], True), "That session")
                            if e["change_usd"] is not None else "")
                         + f'</div><p class="meta">{escape(e["kind"])}.</p>')
    parts.append(sleeves_block(b["sleeves"]))
    parts.append('<div class="book-grid"><div>' + session_block(sess) + "</div><div>" + risk_block(b["risk"])
                 + "</div><div>" + execution_block(b["execution"]) + "</div></div>")
    parts.append("</section>")
    return "".join(parts)


def started_text(b: dict) -> str:
    """How long a book without an official history has traded, in words, from its session record.

    WHY (release-check review, 2026-11-23): this used to print the newest session's date as
    "trading since", a date that moves forward every session, and called a book whose record could
    not be read "no record yet". The start is the first session that sent an order (first_send,
    from the runner's STARTED record); an unreadable record says so."""
    s = b["session"]
    if S.UNMEASURED in s:
        return "its session record could not be read tonight"
    if "value" not in s:
        return "no session recorded yet"
    v = s["value"]
    if "first_send" not in v:
        return f"latest session {fmt_short(v['date'])}"
    if v["first_send"] is None:
        return "no order sent yet"
    return f"trading since {fmt_short(v['first_send'])}"


def sharpe_cell(s: dict) -> str:
    """The Sharpe ratio with the number of daily returns behind it (release-check review, 2026-11-23:
    a ratio from a few weeks of sessions must not read like a long record's)."""
    n = s["n_returns"]
    if s["sharpe"] is None:
        return f'n/a <span class="meta">({n} sessions)</span>'
    return f'{s["sharpe"]:.2f}'.replace("-", "\u2212") + f' <span class="meta">({n} sessions)</span>'


def summary_table(snap: dict) -> str:
    """One row per book with an official history: the figures an allocator reads first."""
    rows = []
    for b in snap["books"]:
        o = b["official"]
        if "value" not in o:
            lead = ("Official history could not be read tonight" if S.UNMEASURED in o
                    else "Official history to follow")
            rows.append((f'<span class="dot" style="background:{BOOK_COLOURS.get(b["name"], "#111418")}"></span>'
                         f'{escape(b["title"])}', f'<span class="meta">{lead}; {escape(started_text(b))}</span>',
                         "", "", "", "", ""))
            continue
        s = M.summary(o["value"]["rows"])
        rows.append((f'<span class="dot" style="background:{BOOK_COLOURS.get(b["name"], "#111418")}"></span>'
                     f'{escape(b["title"])}', fmt_short(s["first_date"]), usd(s["equity"]),
                     f'<span class="{tone(s["cum_pnl"])}">{usd(s["cum_pnl"], True)}</span>',
                     f'<span class="{tone(s["cum_return"])}">{pct(s["cum_return"], True)}</span>',
                     sharpe_cell(s), pct(s["max_drawdown"])))
    head = ["Book", "Since", "Equity", "P&L", "Return", "Sharpe", "Max drawdown"]
    th = "".join(f'<th class="{"r" if i >= 2 else ""}">{escape(h)}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td class="{"r" if i >= 2 else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f'<div class="tbl-wrap"><table class="summary"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def _official_series(books: list) -> dict:
    return {b["name"]: b["official"]["value"]["rows"] for b in books if "value" in b["official"]}


def _dated(v: tuple | None, signed: bool = True) -> str:
    """(date, fraction) -> "+0.52% (12 Nov 2026)"."""
    if v is None:
        return "none"
    return f'{pct(v[1], signed)} <span class="meta">({fmt_short(v[0])})</span>'


def _ratio(x, s: dict) -> str:
    if x is None:
        return f'<span class="meta">needs {M.MIN_RETURNS_FOR_RATIOS} sessions, has {s["n_returns"]}</span>'
    return f"{x:.2f}".replace("-", "\u2212")


# The comparison table: one row per statistic, one column per account (metrics.py has the definitions).
STAT_ROWS = (
    ("First session", lambda s: fmt_short(s["first_date"])),
    ("Sessions", lambda s: f'{s["n_returns"]}'),
    ("Equity", lambda s: usd(s["equity"])),
    ("P&L", lambda s: f'<span class="{tone(s["cum_pnl"])}">{usd(s["cum_pnl"], True)}</span>'),
    ("Return", lambda s: f'<span class="{tone(s["cum_return"])}">{pct(s["cum_return"], True)}</span>'),
    ("Volatility, annualised", lambda s: pct(s["vol"]) if s["vol"] is not None else _ratio(None, s)),
    ("Sharpe ratio, annualised", lambda s: _ratio(s["sharpe"], s)),
    ("Sortino ratio, annualised", lambda s: _ratio(s["sortino"], s)),
    ("Maximum drawdown", lambda s: _dated((s["max_drawdown_date"], s["max_drawdown"]), False)),
    ("Current drawdown", lambda s: pct(s["drawdown"])),
    ("Best session", lambda s: _dated(s["best_day"])),
    ("Worst session", lambda s: _dated(s["worst_day"])),
    ("Sessions with a gain", lambda s: "none" if s["share_up"] is None else
     f'{pct(s["share_up"], dp=0)} <span class="meta">of sessions that moved</span>'),
)


def stats_matrix(cols: list) -> str:
    """cols: [(title, colour, summary)]."""
    th = "".join(f'<th class="r"><span class="dot" style="background:{c}"></span>{escape(n)}</th>' for n, c, _ in cols)
    body = "".join(f'<tr><td>{escape(label)}</td>' + "".join(f'<td class="r">{f(s)}</td>' for _, _, s in cols) + "</tr>"
                   for label, f in STAT_ROWS)
    return (f'<div class="tbl-wrap"><table class="matrix"><thead><tr><th>Statistic</th>{th}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def monthly_grid(cols: list) -> str:
    """cols: [(title, colour, official rows)]. Monthly returns on each month's opening equity."""
    by = [(n, c, dict((m, r) for m, _, r in M.monthly(rows)), M.summary(rows)["cum_return"]) for n, c, rows in cols]
    months = sorted({m for _, _, d, _ in by for m in d})
    head = "".join(f'<th class="r">{charts.MONTHS[int(m[5:]) - 1]} {m[:4]}</th>' for m in months)
    cell = lambda v: "" if v is None else f'<span class="{tone(v)}">{pct(v, True)}</span>'   # noqa: E731
    body = "".join(f'<tr><td><span class="dot" style="background:{c}"></span>{escape(n)}</td>'
                   + "".join(f'<td class="r">{cell(d.get(m))}</td>' for m in months)
                   + f'<td class="r total">{cell(total)}</td></tr>' for n, c, d, total in by)
    return (f'<div class="tbl-wrap"><table class="matrix months"><thead><tr><th>Account</th>{head}'
            f'<th class="r">Since start</th></tr></thead><tbody>{body}</tbody></table></div>')


def latest_sessions(books: list) -> str:
    """Each book's newest verified session, side by side, in aggregates. The P&L is Alpaca's
    official figure when it has landed, else the after-close reading, labelled as such."""
    rows = []
    for b in books:
        sess = b["session"]
        name = (f'<span class="dot" style="background:{BOOK_COLOURS.get(b["name"], COMBINED_COLOUR)}"></span>'
                f'{escape(b["title"])}')
        if "value" not in sess:
            rows.append((name, '<span class="meta">not measured</span>' if S.UNMEASURED in sess
                         else '<span class="meta">none yet</span>', "", "", "", "", ""))
            continue
        v = sess["value"]
        off = {r["date"]: r for r in b["official"]["value"]["rows"]} if "value" in b["official"] else {}
        e = v.get("equity_snapshot")
        if v["date"] in off and off[v["date"]]["change_usd"] is not None:
            ch = off[v["date"]]["change_usd"]
            pnl = f'<span class="{tone(ch)}">{usd(ch, True)}</span> <span class="meta">official</span>'
        elif e and e.get("change_usd") is not None:
            pnl = (f'<span class="{tone(e["change_usd"])}">{usd(e["change_usd"], True)}</span> '
                   '<span class="meta">after-close reading</span>')
        else:
            pnl = '<span class="meta">not measured</span>'
        p, o = v["positions"], v["orders"]
        held = f'{p["n"]} <span class="meta">({p["n_long"]} long, {p["n_short"]} short)</span>' if p["n"] else "none"
        if p["n"] and p["n_unpriced"]:
            gross = net = '<span class="meta">not measured</span>'
        elif p["gross_x"] is not None:
            gross = f'{p["gross_x"]:.2f}x'
            net = f'{p["net_x"]:+.2f}x'.replace("-", "\u2212")
        else:
            gross = net = "none" if not p["n"] else '<span class="meta">not measured</span>'
        orders = f'{o["n_filled"]} of {o["n"]}' if o["n"] else "none needed"
        check = "Reconciled" if v["verdict"] == "PASS" else '<span class="neg">Flagged for review</span>'
        rows.append((name, fmt_short(v["date"]), pnl, held, f"{gross} / {net}", orders, check))
    return ('<div class="latest">' + tbl(["Book", "Session", "P&L", "Positions", "Gross / net exposure", "Orders filled",
                                          "Check"], rows, right=(2, 3, 4, 5, 6)) + "</div>")


def combined_section(books: list) -> str:
    """The page's top: the accounts together and side by side (team lead, 2026-11-24: "the performance
    needs to be displayed better ... detailed that matters"). A summary strip, growth and drawdown on
    one percentage scale, each session's P&L, the comparison table, monthly returns and the latest
    session of every book. Every figure is computed from Alpaca's official end-of-day rows."""
    series = _official_series(books)
    if not series:
        return '<section class="section"><div class="wrap"><p class="gap">No account has an official history to show.</p></div></section>'
    named = [b for b in books if b["name"] in series]
    rows_c, left_out = M.combined(series) if len(series) > 1 else (M.funded(series[named[0]["name"]]), 0)
    s_c = M.summary(rows_c)
    sums = {b["name"]: M.summary(series[b["name"]]) for b in named}
    names = ", ".join(b["title"] for b in named)
    multi = len(series) > 1
    corr = M.correlation(series[named[0]["name"]], series[named[1]["name"]]) if len(named) == 2 else (None, 0)

    kpis = [fig(usd(s_c["equity"]), f"{'Combined equity' if multi else 'Equity'}, {fmt_short(s_c['last_date'])}"),
            fig(pct(s_c["cum_return"], True), f"Return since {fmt_short(s_c['first_date'])} "
                                              f"({usd(s_c['cum_pnl'], True)})"),
            fig(_ratio(s_c["sharpe"], s_c) if s_c["sharpe"] is not None else "n/a",
                f"Sharpe ratio, annualised ({s_c['n_returns']} sessions)"),
            fig(pct(s_c["max_drawdown"]), f"Maximum drawdown ({fmt_short(s_c['max_drawdown_date'])})")]
    if corr[0] is not None:
        kpis.append(fig(f"{corr[0]:.2f}".replace("-", "\u2212"),
                        f"Correlation of the two books' daily returns ({corr[1]} sessions)"))

    colour = lambda b: BOOK_COLOURS.get(b["name"], COMBINED_COLOUR)                       # noqa: E731
    growth = [{"name": b["title"], "color": colour(b), "points": M.return_points(series[b["name"]])} for b in named]
    under = [{"name": b["title"], "color": colour(b), "points": M.drawdown_points(series[b["name"]])} for b in named]
    if multi:
        growth.append({"name": "Accounts combined", "color": COMBINED_COLOUR, "points": M.return_points(rows_c), "bold": True})
        under.append({"name": "Accounts combined", "color": COMBINED_COLOUR, "points": M.drawdown_points(rows_c), "bold": True})
    cols = [(b["title"], colour(b), sums[b["name"]]) for b in named]
    mcols = [(b["title"], colour(b), series[b["name"]]) for b in named]
    if multi:
        cols.append(("Accounts combined", COMBINED_COLOUR, s_c))
        mcols.append(("Accounts combined", COMBINED_COLOUR, rows_c))

    missing = [b for b in books if b["name"] not in series]
    miss_txt = ""
    if missing:
        miss_txt = ('<p class="meta">Not yet in the combined figures: '
                    + "; ".join(f"{escape(b['title'])} ({escape(b['official'].get('absent') or b['official'].get(S.UNMEASURED, ''))})"
                                for b in missing) + ".</p>")
    basis = (f'The sum of the accounts with an official end-of-day history: {escape(names)}. The combined figures '
             f'use the {len(rows_c)} sessions every one of them has a record for'
             + (f', leaving out {left_out} {"session" if left_out == 1 else "sessions"} that only some of them have.'
                if left_out else '.')) if multi else f'{escape(names)}.'
    return (f'<section class="section"><div class="wrap">'
            f'<div class="eyebrow">All accounts &middot; official figures to {fmt_short(s_c["last_date"])}</div>'
            f'<h2>Combined paper results</h2><p class="narrow">{basis}</p>'
            f'<div class="figures kpis">{"".join(kpis)}</div>'
            '<h3 class="chart-title">Growth since inception</h3>'
            + charts.line_chart(growth, "Cumulative return of each account and combined", fmt="pct")
            + '<h3 class="chart-title">Drawdown from the peak</h3>'
            + charts.line_chart(under, "Drawdown from the running peak of each account and combined", fmt="pct",
                                height=250)
            + f'<h3 class="chart-title">P&amp;L of each session{", accounts combined" if multi else ""}</h3>'
            + charts.bar_chart(M.pnl_points(rows_c), "P&L of each session in dollars", height=230)
            + '<h3 class="block-title">Statistics</h3>' + stats_matrix(cols)
            + '<h3 class="block-title">Monthly returns</h3>' + monthly_grid(mcols)
            + '<h3 class="block-title">Latest session</h3>' + latest_sessions(books)
            + '<p class="meta">Returns are on each account\'s equity at the start of the period. Hover over a chart for '
              'each session\'s values. A session\'s P&amp;L is shown from the after-close reading until Alpaca '
              'publishes its official end-of-day figure overnight.</p>' + miss_txt + "</div></section>")


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
<p><b>Statistics.</b> Daily return is the day's change in equity divided by the previous day's equity. Volatility, the Sharpe ratio and the Sortino ratio are annualised with 252 sessions and shown once a book has 20 sessions; neither ratio subtracts a risk-free rate, and the Sortino ratio divides by the downside deviation of daily returns. Drawdown is measured from the running peak of end-of-day equity. The correlation of the two books is measured on the daily returns of the sessions both have. A record of a few dozen sessions measures these ratios only loosely.</p>
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
