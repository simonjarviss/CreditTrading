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
from dashboard.layout import (BOOK_COLOURS, BOOK_TEXT, COMBINED_COLOUR, fmt_short, page, page_head, pct, tone,
                              usd, when)

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


PORTFOLIO_COLOUR = COMBINED_COLOUR

# The portfolio's record starts with this session (team lead, 2026-11-24: "we should use today as the
# first day for all books, but keep the old records too"). It is the first session on which all three
# books trade a full plan: the event book's first send, on 2026-11-23, placed 46 of its 219 orders
# before Alpaca's rate limit refused the rest (fixed in release-20261123-2). Every figure of the
# portfolio and of each book counts from the close of the session before it; each book's record before
# it is kept and shown apart, as the earlier record, never merged into the figures from this date.
RECORD_START = "2026-11-24"


def portfolio(snap: dict, before: str | None = None) -> dict:
    """The books that trade and their composite, from RECORD_START; with `before`, the earlier record
    instead: each book from its first traded session to the last session before that date.

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
        if before is not None and first >= before:
            excluded.append((b, f"it began trading on {fmt_short(first)}"))
            continue
        # From RECORD_START, or from the first send when that is later; the base is the close before.
        start = first if before is not None else max(first, RECORD_START)
        try:
            tr = M.trading_rows(rows, start)
            if before is not None:
                tr = [r for r in tr if r["date"] < before]
            dated = M.daily(tr)
        except ValueError as e:
            blocked.append((b, str(e)))
            continue
        if not dated:
            excluded.append((b, "its first traded session has no closing record yet" if start == first
                             else f"its first session from {fmt_short(start)} has not closed yet"))
            continue
        books.append({"b": b, "kind": kind, "first": start, "rows": tr, "base": tr[0]["date"], "dated": dated,
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


# The key figures, one column per series: the standard return and risk measures of a fund factsheet
# (team lead, 2026-11-24: "the portfolio results is too many analytics", then "it should still
# demonstrate the live trading, risk etc. (all regular metrics) for our portfolio and books").
# metrics.profile computes more than the page shows.
STAT_GROUPS = (
    ("Return", (
        ("Sessions", lambda p: f'{p["n"]}'),
        ("Return, time-weighted", lambda p: _sgn(p["cum_return"])),
        ("Annualised return", lambda p: _num(p["ann_return"], p, _sgn)),
        ("P&L", lambda p: f'<span class="{tone(p["pnl"])}">{usd(p["pnl"], True)}</span>'),
        ("Sessions with a gain", lambda p: "none" if p["hit_rate"] is None else
         f'{pct(p["hit_rate"], dp=0)} <span class="meta">of sessions that moved</span>'),
    )),
    ("Risk", (
        ("Volatility, annualised", lambda p: _num(p["vol"], p, pct)),
        ("Sharpe ratio", lambda p: _num(p["sharpe"], p, _ratio_s)),
        ("Sortino ratio", lambda p: _num(p["sortino"], p, _ratio_s)),
        ("Maximum drawdown", lambda p: "0.00%" if p["max_drawdown_date"] is None
         else _dated_pct((p["max_drawdown_date"], p["max_drawdown"]), False)),
        ("Current drawdown", lambda p: pct(p["drawdown"])),
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
    """Each book's newest verified session, in aggregates: its P&L, positions, gross and net exposure at the
    closing price, orders filled and the reconciliation check; and the portfolio's totals when every book
    has a priced reading for the same session. The live trading and risk view of the page (team lead,
    2026-11-24: "it should still demonstrate the live trading, risk etc. ... for our portfolio and
    books"). A P&L is Alpaca's official figure when it has landed, else the after-close reading, labelled."""
    rows, total, gross, net, eq, n_pos, dates, complete = [], 0.0, 0.0, 0.0, 0.0, 0, set(), True
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
            total += ch
            gross += p["gross_usd"] or 0.0
            net += p["net_usd"] or 0.0
            eq += e["equity"]
            n_pos += p["n"]
        else:
            complete = False
        orders = f'{o["n_filled"]} of {o["n"]}' if o["n"] else "none needed"
        check = "Reconciled" if v["verdict"] == "PASS" else '<span class="neg">Flagged for review</span>'
        rows.append((name, fmt_short(v["date"]), pnl, held, ex, orders, check))
    if complete and len(dates) == 1 and eq:
        rows.append(("<b>Portfolio</b>", fmt_short(next(iter(dates))), f'<b class="{tone(total)}">{usd(total, True)}</b>',
                     str(n_pos), f'{gross / eq:.2f}x / ' + f'{net / eq:+.2f}x'.replace("-", "−"), "", ""))
    return ('<div class="latest">' + tbl(["Book", "Session", "P&L", "Positions", "Gross / net exposure", "Orders filled",
                                          "Check"], rows, right=(2, 3, 4, 5, 6))
            + '<p class="meta">Exposure is the market value of long and short positions at the closing price, as a '
              'multiple of the account\'s equity. Individual holdings and orders are not published.</p></div>')


def portfolio_section(snap: dict) -> str:
    """The page's top (team lead, 2026-11-24: "overall portfolio (shown as one line), can split into
    3 lines (our sleeves)"; later the same day: "the portfolio results is too many analytics"). Four
    headline figures, the portfolio's line with its books' on a switch, and one table of key figures
    for the portfolio and each book; then the latest session's P&L. Each book's own session, exposure and
    execution follow below."""
    pf = portfolio(snap)
    tail = ('<h3 class="block-title">Latest session</h3>' + latest_sessions(snap["books"]) + earlier_record(snap)
            + '<p class="meta">Returns are time-weighted: each session\'s return is the books\' combined P&amp;L over '
              'their combined equity at the previous close, compounded. A session\'s P&amp;L is the after-close '
              'reading until Alpaca publishes its official end-of-day figure overnight.</p></div></section>')
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
               if pf["blocked"] else
               f'<p class="narrow">The portfolio\'s record starts with the {fmt_short(RECORD_START)} session, the first '
               'on which all three books trade a full plan. Its figures appear once that session has closed: the '
               'after-close readings in the evening, Alpaca\'s end-of-day figures overnight.</p>')
        return ('<section class="section"><div class="wrap"><div class="eyebrow">Portfolio</div>'
                f'<h2>Portfolio results</h2>{why}' + tail)
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
            fig(pct(p["max_drawdown"]), "Maximum drawdown")]
    growth = [{"name": "Portfolio", "color": PORTFOLIO_COLOUR, "bold": True,
               "points": M.index_points(pf["dated"], pf["base"])}]
    for x in pf["books"]:
        growth.append({"name": x["b"]["title"], "color": colour(x), "cls": "bk",
                       "points": M.index_points(x["dated"], x["base"])})
    switch = ('<div class="view-switch" role="group" aria-label="Chart view" hidden>'
              '<button type="button" data-view="portfolio" aria-pressed="true">Portfolio</button>'
              '<button type="button" data-view="books" aria-pressed="false">By book</button></div>')
    cols = [("Portfolio", PORTFOLIO_COLOUR, p)] + [(x["b"]["title"], colour(x), x["p"]) for x in pf["books"]]
    return (f'<section class="section"><div class="wrap">'
            f'<div class="eyebrow">Portfolio &middot; to {fmt_short(p["last_date"])}</div>'
            f'<h2>Portfolio results</h2><p class="narrow">A composite of the books that are trading, from the '
            f'{fmt_short(RECORD_START)} session, the first on which all three trade a full plan: {members}.'
            f'{left}{out_txt}</p>{warn}'
            f'<div class="figures kpis">{"".join(kpis)}</div>'
            f'<div class="chart-head"><h3 class="chart-title">Growth since inception</h3>{switch}</div>'
            + charts.line_chart(growth, "Cumulative return of the portfolio and of each book", fmt="pct")
            + '<h3 class="block-title">Key figures</h3>' + stats_table(cols) + tail)


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


def record_table(pf: dict, span: bool = False) -> str:
    """The portfolio and each book of one record (a `portfolio` result), one row each: when it starts
    (and, with `span`, ends), P&L, time-weighted return, Sharpe and maximum drawdown."""
    dot = lambda c: f'<span class="dot" style="background:{c}"></span>'                    # noqa: E731
    rows = []

    def row(name, colour, since, p):
        n = f'{p["n"]} {"session" if p["n"] == 1 else "sessions"}'
        ratio = (f'{_ratio_s(p["sharpe"])} <span class="meta">({n})</span>' if p["sharpe"] is not None
                 else f'<span class="meta">{n}; needs {M.MIN_RETURNS_FOR_RATIOS}</span>')
        rows.append([dot(colour) + name, fmt_short(since)] + ([fmt_short(p["last_date"])] if span else [])
                    + [f'<span class="{tone(p["pnl"])}">{usd(p["pnl"], True)}</span>', _sgn(p["cum_return"]), ratio,
                       pct(p["max_drawdown"])])

    if pf["p"]:
        row("<b>Portfolio</b>", PORTFOLIO_COLOUR, pf["first"], pf["p"])
    for x in pf["books"]:
        row(escape(x["b"]["title"]), BOOK_COLOURS.get(x["b"]["name"], COMBINED_COLOUR), x["first"], x["p"])
    head = ["", "From"] + (["To"] if span else []) + ["P&L", "Return, time-weighted", "Sharpe", "Max drawdown"]
    for b, why in pf["excluded"] + pf["blocked"]:
        rows.append([dot(BOOK_COLOURS.get(b["name"], COMBINED_COLOUR)) + escape(b["title"]),
                     f'<span class="meta">{escape(why[:1].upper() + why[1:])}</span>'] + [""] * (len(head) - 2))
    num = len(head) - 4
    th = "".join(f'<th class="{"r" if i >= num else ""}">{escape(h)}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td class="{"r" if i >= num else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f'<div class="tbl-wrap"><table class="summary"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def summary_table(snap: dict) -> str:
    """The portfolio and each trading book from RECORD_START: the figures an allocator reads first (the
    overview's table)."""
    return record_table(portfolio(snap))


def earlier_record(snap: dict) -> str:
    """Each book's record before RECORD_START, from its first traded session, and their composite, as it
    stood (team lead, 2026-11-24: "keep the old records too"). Empty when no book traded before it."""
    old = portfolio(snap, before=RECORD_START)
    if not old["books"] and not old["blocked"]:
        return ""
    return (f'<h3 class="block-title">Record before {fmt_short(RECORD_START)}</h3>'
            '<p class="meta">Each book from its first traded session to the last session before the portfolio\'s '
            'record began, kept as it was. These sessions are not in the figures above.</p>' + record_table(old, span=True))


def n_strategies(snap: dict):
    """The systematic strategies the books run: one in each core book, and the event book's own (its
    sleeve reading's strategies). None when the event book's reading could not be read."""
    n = 0
    for b in snap["books"]:
        if b["name"] != "events":
            n += 1
        elif "value" in b["sleeves"]:
            n += len({r["slug"] for r in b["sleeves"]["value"]["rows"] if r["slug"] != "_book"})
        else:
            return None
    return n


def fund_facts(snap: dict) -> str:
    """The facts an investor reads first, in aggregate, from each book's newest verified session (team lead,
    2026-11-24: "intended for investors / public to view how we are performing and show our fund
    statistics"). Capital and exposure are summed only when every book's session was read and every
    position priced; otherwise they say so, never a partial sum."""
    books = snap["books"]
    sess = [b["session"]["value"] for b in books if "value" in b["session"]]
    pos = [s["positions"] for s in sess]
    eq = [(s.get("equity_snapshot") or {}).get("equity") for s in sess]
    whole = len(sess) == len(books) and all(e is not None for e in eq)
    priced = whole and all(p["n"] == 0 or (p["gross_usd"] is not None and not p["n_unpriced"]) for p in pos)
    capital = sum(eq) if whole else None
    dates = sorted({s["date"] for s in sess})
    asof = f"after the close of {fmt_short(dates[-1])}" if len(dates) == 1 else "after each book's latest session"
    nm = '<span class="meta">not measured</span>'
    n = n_strategies(snap)
    items = [("Record starts", fmt_short(RECORD_START)),
             ("Structure", f"{len(books)} systematic books, one portfolio"),
             ("Strategies", str(n) if n is not None else nm),
             ("Capital, paper", usd(capital) if capital else nm),
             ("Gross exposure", pct(sum(p["gross_usd"] or 0.0 for p in pos) / capital, dp=0) + " of capital"
              if priced and capital else nm),
             ("Net exposure", pct(sum(p["net_usd"] or 0.0 for p in pos) / capital, True, dp=0) + " of capital"
              if priced and capital else nm),
             ("Positions", f'{sum(p["n"] for p in pos)} ({sum(p["n_long"] for p in pos)} long, '
                           f'{sum(p["n_short"] for p in pos)} short)' if len(sess) == len(books) else nm),
             ("Trading", "Daily, near the close"),
             ("Broker", "Alpaca Markets, paper accounts")]
    cells = "".join(f'<div><dt>{escape(k)}</dt><dd>{v}</dd></div>' for k, v in items)
    return ('<section class="section soft"><div class="wrap"><div class="eyebrow">At a glance</div>'
            f'<h2>Fund facts</h2><dl class="facts">{cells}</dl>'
            f'<p class="meta">Capital, exposure and positions {asof}, from the trading system\'s reconciliation with '
            'the broker, in aggregate.</p></div></section>')


def books_list(snap: dict) -> str:
    """The three books in a sentence each, and when each began trading. Their figures are in the key
    figures above; their positions, risk reports and fills are not published here (team lead,
    2026-11-24: "no one really cares about some of the tables")."""
    def source(b):
        """Where the book's daily figures come from, read when, and how far to trust them; a record that is
        absent or could not be read says so."""
        o, ac = b["official"], b.get("after_close", {})
        if "value" in o:
            return prov(o)
        return gap(o, "Official end-of-day history") + (prov(ac) if "value" in ac else gap(ac, "After-close readings")
                                                       if ac else "")
    rows = "".join(
        f'<div class="row"><div class="num">0{i}</div><div><h3><span class="dot" style="background:'
        f'{BOOK_COLOURS.get(b["name"], COMBINED_COLOUR)}"></span>{escape(b["title"])}</h3>'
        f'<p>{escape(BOOK_TEXT.get(b["name"], ""))}</p>{source(b)}</div>'
        f'<div class="stat"><span>{escape(started_text(b)[:1].upper() + started_text(b)[1:])}</span></div></div>'
        for i, b in enumerate(snap["books"], start=1))
    return ('<section class="section"><div class="wrap"><div class="eyebrow">The books</div><h2>What each book trades</h2>'
            f'<div class="rows">{rows}</div></div></section>')


METHOD = """<section class="section" style="padding-top:0"><div class="wrap narrow"><details class="method"><summary>How these figures are produced</summary>
<p><b>Official P&amp;L.</b> Each account's results come from Alpaca's end-of-day portfolio history, the record we report against. A paper account differs from a live account in three ways: it charges no stock borrow fees, it does not credit or debit distributions on positions, and it fills orders at the current quote rather than in the closing auction. A live account's results would differ for those reasons.</p>
<p><b>The portfolio.</b> A composite of the books that are trading. Its record starts with the 24 Nov 2026 session, the first on which all three books trade a full plan, and every figure above counts from the close before it; each book's record before that date is shown apart and is not in those figures. A book that starts later joins from its first traded session, so an account's idle cash before it trades never dilutes the result. Each session's return is the books' combined P&amp;L divided by their combined equity at the previous close, and the returns compound: the return is time-weighted, the standard for a composite. Because a session counts by its return and not by its dollars, the portfolio's return and its dollar P&amp;L can differ, even in sign, when the capital trading changes, as it does when a book joins. A session on which a trading book has no record is left out, never filled. The event book counts from its first traded session; until Alpaca's end-of-day history is collected for it, its daily figures are the account equity read after each close.</p><p><b>Statistics.</b> Daily return is the day's change in equity divided by the previous day's equity. Volatility and the Sharpe ratio are shown once a series has 20 sessions and are annualised with 252 sessions; the Sharpe ratio subtracts no risk-free rate. Drawdown is measured on the compounded return from its running peak. A record of a few dozen sessions measures every ratio only loosely.</p>
<p><b>Capital and exposure.</b> Taken from the trading system's reconciliation with the broker after each close and reported in aggregate: account equity, the number of positions, and gross and net exposure at the closing price. Individual holdings and orders are not published.</p>
<p><b>Updates.</b> The page rebuilds automatically every 30 minutes from the trading system's records, so a session appears shortly after the close and its official figure after Alpaca publishes it overnight. A figure the system could not read is marked as not measured; it is never estimated or carried forward.</p>
</details></div></section>"""


def render_body(snap: dict) -> str:
    exported = snap["exported_at_utc"]
    banner = ('<div class="wrap"><p class="gap" style="margin-top:20px">Synthetic data: every number on this page is '
              'invented for testing and is not the book.</p></div>') if snap["synthetic"] else ""
    head = page_head("Performance", "Live performance",
                     "Daily results of our three paper-trading accounts at Alpaca, built automatically from the "
                     "trading system's own records.",
                     f'<p class="meta" style="color:rgba(255,255,255,0.7);margin-top:14px">Updated {escape(when(exported))}. '
                     'Paper trading only: no client capital is invested.</p>')
    return head + banner + portfolio_section(snap) + fund_facts(snap) + books_list(snap) + METHOD


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
