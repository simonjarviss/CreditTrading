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
from dashboard.layout import (BOOK_COLOURS, COMBINED_COLOUR, fmt_short, page, page_head, pct, tone,
                              usd, when)

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
# portfolio and of each book counts from the close of the session before it. The record before it was
# shown apart until the team lead took it off the page the same day ("this is replaced by new starting
# now"); it stays in each book's own records.
RECORD_START = "2026-11-24"


def portfolio(snap: dict) -> dict:
    """The books that trade and their composite, from RECORD_START (a book that starts later, from its
    first traded session).

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
        # From RECORD_START, or from the first send when that is later; the base is the close before.
        start = max(first, RECORD_START)
        try:
            tr = M.trading_rows(rows, start)
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


def stats_table(cols: list, first: str) -> str:
    """cols: [(title, colour, profile, its first session)]. A column that starts after `first`, the
    portfolio's start, says from when under its name, so a book that joined later is never read as
    having traded the whole period."""
    th = "".join(f'<th class="r"><span class="dot" style="background:{c}"></span>{escape(n)}'
                 + (f'<br><span class="meta">from {fmt_short(d)}</span>' if d != first else "") + '</th>'
                 for n, c, _, d in cols)
    body = []
    for group, rows in STAT_GROUPS:
        body.append(f'<tr class="grp"><td colspan="{len(cols) + 1}">{escape(group)}</td></tr>')
        body += [f'<tr><td>{escape(label)}</td>' + "".join(f'<td class="r">{f(p)}</td>' for _, _, p, _ in cols) + "</tr>"
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


def positioning(snap: dict) -> dict:
    """Each book's newest verified session in aggregates, and the portfolio's totals when every book has a
    priced reading for the same session: {rows: [...], total: {...} or None, date: str or None}.
    A P&L is Alpaca's official figure when it has landed, else the after-close reading (session_pnl)."""
    rows, complete, dates = [], True, set()
    for b in snap["books"]:
        sess = b["session"]
        if "value" not in sess:
            complete = False
            continue
        v = sess["value"]
        dates.add(v["date"])
        e = v.get("equity_snapshot") or {}
        ch, kind = session_pnl(b, v["date"])
        pos = v["positions"]
        priced = not pos["n"] or (not pos["n_unpriced"] and pos["gross_x"] is not None)
        rows.append({"b": b, "date": v["date"], "pnl": ch, "kind": kind, "equity": e.get("equity"), "pos": pos,
                     "priced": priced})
        complete = complete and ch is not None and e.get("equity") is not None and priced
    total = None
    if complete and rows and len(dates) == 1:
        eq = sum(r["equity"] for r in rows)
        total = {"pnl": sum(r["pnl"] for r in rows), "equity": eq,
                 "gross_x": sum(r["pos"]["gross_usd"] or 0.0 for r in rows) / eq,
                 "net_x": sum(r["pos"]["net_usd"] or 0.0 for r in rows) / eq,
                 "n_long": sum(r["pos"]["n_long"] for r in rows), "n_short": sum(r["pos"]["n_short"] for r in rows)}
    return {"rows": rows, "total": total, "date": next(iter(dates)) if len(dates) == 1 else None}


def _x(v: float, signed: bool = False) -> str:
    return (f"{v:+.2f}x" if signed else f"{v:.2f}x").replace("-", "−")


# Display names of the event strategies and of the core books' fund groups, in the investor deck's words.
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
}
GROUP_NAMES = {
    "hy": "High yield", "loan": "Loans", "multi": "Multi-sector", "muni": "Municipal",
    "equity_covered_call": "Covered call", "equity_domestic": "Domestic equity", "equity_sector": "Sector equity",
    "multi_asset": "Multi-asset", "preferred": "Preferred",
}


def _name(table: dict, key: str) -> str:
    return table.get(key) or key.replace("_", " ").capitalize()


def positioning_table(snap: dict, ps: dict) -> str:
    """One row per book and the portfolio: capital, positions, long and short market value, gross and net
    exposure as a multiple of equity, and the risk report's concentration (largest position and top three
    as a share of gross). Aggregates only; a figure that was not read says so."""
    nm = '<span class="meta">not measured</span>'
    rows = []
    for r in ps["rows"]:
        b, p = r["b"], r["pos"]
        risk = b.get("risk", {}).get("value") or {}
        long_usd = short_usd = None
        if r["priced"] and p["gross_usd"] is not None:
            long_usd, short_usd = (p["gross_usd"] + p["net_usd"]) / 2, (p["gross_usd"] - p["net_usd"]) / 2
        rows.append([f'<span class="dot" style="background:{BOOK_COLOURS.get(b["name"], COMBINED_COLOUR)}"></span>'
                     f'{escape(b["title"])}',
                     usd(r["equity"]) if r["equity"] is not None else nm,
                     f'{p["n"]} <span class="meta">({p["n_long"]} long, {p["n_short"]} short)</span>' if p["n"] else "none",
                     usd(long_usd) if long_usd is not None else (nm if p["n"] else "none"),
                     usd(short_usd) if short_usd is not None else (nm if p["n"] else "none"),
                     _x(p["gross_x"]) if r["priced"] and p["n"] else (nm if p["n"] else "none"),
                     _x(p["net_x"], True) if r["priced"] and p["n"] else (nm if p["n"] else "none"),
                     pct(risk["largest_share"], dp=0) if "largest_share" in risk else '<span class="meta">no report</span>',
                     pct(risk["top3_share"], dp=0) if "top3_share" in risk else '<span class="meta">no report</span>'])
    t = ps["total"]
    if t:
        g, n = t["gross_x"] * t["equity"], t["net_x"] * t["equity"]
        rows.append(["<b>Portfolio</b>", usd(t["equity"]),
                     f'{t["n_long"] + t["n_short"]} <span class="meta">({t["n_long"]} long, {t["n_short"]} short)</span>',
                     usd((g + n) / 2), usd((g - n) / 2), _x(t["gross_x"]), _x(t["net_x"], True), "", ""])
    return tbl(["Book", "Capital", "Positions", "Long", "Short", "Gross", "Net", "Largest position", "Top 3"],
               rows, right=(1, 2, 3, 4, 5, 6, 7, 8))


def positioning_section(snap: dict) -> str:
    """Positioning after each book's newest session (team lead, 2026-11-24: "the position could also be more
    detailed"): a table of capital, positions, long and short value, exposure and concentration; bar charts
    of each book's session P&L, positions, gross and net exposure; the core books' exposure by fund group
    (their risk reports); the event book's capital and names by strategy (its sleeve reading); and
    concentration. Books whose session could not be read are named; a book with an unpriced position has
    no exposure bar. Aggregates only, never a holding."""
    ps = positioning(snap)
    colour = lambda b: BOOK_COLOURS.get(b["name"], COMBINED_COLOUR)                        # noqa: E731
    t = ps["total"]
    pnl, gross, net, held = [], [], [], []
    if t:
        pnl.append(("Portfolio", PORTFOLIO_COLOUR, [(t["pnl"], 1.0)], usd(t["pnl"], True)))
        gross.append(("Portfolio", PORTFOLIO_COLOUR, [(t["gross_x"], 1.0)], _x(t["gross_x"])))
        net.append(("Portfolio", PORTFOLIO_COLOUR, [(t["net_x"], 1.0)], _x(t["net_x"], True)))
        held.append(("Portfolio", PORTFOLIO_COLOUR, [(t["n_long"], 1.0), (-t["n_short"], 0.45)],
                     f'{t["n_long"]} long · {t["n_short"]} short'))
    for r in ps["rows"]:
        b, p = r["b"], r["pos"]
        if r["pnl"] is not None:
            note = "" if r["kind"] == "official" else " (after close)"
            pnl.append((b["title"], colour(b), [(r["pnl"], 1.0)], usd(r["pnl"], True) + note))
        if r["priced"] and p["n"]:
            gross.append((b["title"], colour(b), [(p["gross_x"], 1.0)], _x(p["gross_x"])))
            net.append((b["title"], colour(b), [(p["net_x"], 1.0)], _x(p["net_x"], True)))
        held.append((b["title"], colour(b), [(p["n_long"], 1.0), (-p["n_short"], 0.45)],
                     f'{p["n_long"]} long · {p["n_short"]} short'))
    cell = lambda title, rows, label: (f'<div><h3 class="chart-title">{title}</h3>'                    # noqa: E731
                                        + charts.hbar_chart(rows, label) + '</div>')
    cells = [cell("Session P&amp;L", pnl, "P&L of the latest session by book"),
             cell("Positions, long and short", held, "Long and short positions by book"),
             cell("Gross exposure, x equity", gross, "Gross exposure by book"),
             cell("Net exposure, x equity", net, "Net exposure by book")]
    conc = []
    for b in snap["books"]:
        risk = b.get("risk", {}).get("value")
        if not risk:
            continue
        groups = sorted(risk.get("groups", {}).items(), key=lambda kv: -kv[1])
        if groups:
            cells.append(cell(f'{escape(b["title"])}: exposure by fund group, x equity',
                              [(_name(GROUP_NAMES, k), colour(b), [(v, 1.0)], _x(v)) for k, v in groups],
                              f"{b['title']} gross exposure by fund group"))
        if "largest_share" in risk and "top3_share" in risk:
            conc.append((b["title"], colour(b), [(risk["top3_share"], 0.45), (risk["largest_share"], 1.0)],
                         f'{pct(risk["largest_share"], dp=0)} largest · {pct(risk["top3_share"], dp=0)} top 3'))
    ev = next((b for b in snap["books"] if b["name"] == "events"), None)
    if ev is not None and "value" in ev["sleeves"] and ev["sleeves"]["value"]["rows"]:
        srows = ev["sleeves"]["value"]["rows"]
        last = max(r["date"] for r in srows)
        strat = sorted((r for r in srows if r["date"] == last and r["slug"] != "_book" and r["capital_usd"] is not None),
                       key=lambda r: -r["capital_usd"])
        if strat:
            cells.append(cell("Event Book: capital by strategy",
                              [(_name(STRATEGY_NAMES, r["slug"]), colour(ev), [(r["capital_usd"], 1.0)],
                                f'{usd(r["capital_usd"])} · {r["n_names"]:.0f} {"name" if r["n_names"] == 1 else "names"}') for r in strat],
                              "Event Book capital and names held by strategy"))
    if conc:
        cells.append(cell("Concentration, share of gross", conc, "Largest position and top three as a share of gross"))
    missing = [b for b in snap["books"] if "value" not in b["session"]]
    gap_txt = "".join(f'<p class="gap">{escape(b["title"])}: session not read.</p>' for b in missing)
    when_txt = fmt_short(ps["date"]) if ps["date"] else "each book's latest session"
    return ('<section class="section soft"><div class="wrap">'
            f'<h2>Positioning</h2><p class="meta">After the close of {when_txt}.</p>{gap_txt}'
            + positioning_table(snap, ps)
            + f'<div class="chart-grid">{"".join(cells)}</div></div></section>')


# The Portfolio / By book switch. Every switch on the page sets every chart (static/site.js).
SWITCH = ('<div class="view-switch" role="group" aria-label="Chart view" hidden>'
          '<button type="button" data-view="portfolio" aria-pressed="true">Portfolio</button>'
          '<button type="button" data-view="books" aria-pressed="false">By book</button></div>')


def portfolio_section(snap: dict) -> str:
    """Returns and risk since RECORD_START: four headline figures; the cumulative return of the portfolio
    and, on a switch, of each book; each session's P&L; the drawdown; and the overall statistics as a
    table (team lead, 2026-11-24: "graphs and bar charts demonstrate returns, risk and positioning ...
    with tables for overall stats")."""
    pf = portfolio(snap)
    warn = "".join(f'<p class="gap">Not included: {escape(b["title"])} ({escape(w)}).</p>' for b, w in pf["blocked"])
    if not pf["p"]:
        # Say why there is no portfolio (release-check review of 455eff4: with every book unreadable,
        # "no traded session yet" was false and dropped the reason).
        # Release-check review of b76a7f4: with one book unreadable, the others' reasons were dropped.
        why = (warn + "".join(f'<p class="meta">{escape(b["title"])} not included: {escape(w)}.</p>'
                              for b, w in pf["excluded"]) if pf["blocked"]
               else f'<p class="meta">First figures after the close of {fmt_short(RECORD_START)}.</p>')
        return f'<section class="section"><div class="wrap"><h2>Portfolio</h2>{why}</div></section>'
    p = pf["p"]
    colour = lambda x: BOOK_COLOURS.get(x["b"]["name"], COMBINED_COLOUR)                    # noqa: E731
    notes = "".join([f'<p class="meta">{pf["left"]} {"session" if pf["left"] == 1 else "sessions"} left out: a '
                     'book has no record for it yet.</p>'] if pf["left"] else []) + "".join(
        f'<p class="meta">{escape(b["title"])} not included: {escape(w)}.</p>' for b, w in pf["excluded"])
    # Return and P&L are shown apart and the return is named time-weighted: on 2026-11-24 the portfolio
    # read +0.06% beside -$472, both right, because its losses fell when three books were trading and
    # its gains when one was. A reader shown "+0.06% (-$472)" would read an error.
    kpis = [fig(pct(p["cum_return"], True), "Return, time-weighted"),
            fig(usd(p["pnl"], True), "P&amp;L"),
            fig(_ratio_s(p["sharpe"]) if p["sharpe"] is not None else "n/a", f"Sharpe ratio ({p['n']} sessions)"),
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
    switch = SWITCH
    cols = [("Portfolio", PORTFOLIO_COLOUR, p, pf["first"])] + [(x["b"]["title"], colour(x), x["p"], x["first"])
                                                              for x in pf["books"]]
    return (f'<section class="section"><div class="wrap"><h2>Portfolio</h2>'
            f'{warn}{notes}<div class="figures kpis">{"".join(kpis)}</div>'
            f'<div class="chart-head"><h3 class="chart-title">Returns: cumulative</h3>{switch}</div>'
            + charts.line_chart(growth, "Cumulative return of the portfolio and of each book", fmt="pct")
            + '<h3 class="chart-title">Returns: P&amp;L by session</h3>'
            + charts.bar_chart([(d, v) for d, _, v in pf["dated"]], "Portfolio P&L of each session")
            + '<h3 class="chart-title">Risk: drawdown from peak</h3>'
            + charts.line_chart(under, "Drawdown of the portfolio and of each book", fmt="pct", height=240)
            + '<h3 class="block-title">Key figures</h3>' + stats_table(cols, pf["first"]) + '</div></section>')


def render_body(snap: dict) -> str:
    exported = snap["exported_at_utc"]
    banner = ('<div class="wrap"><p class="gap" style="margin-top:20px">Synthetic data: every number on this page is '
              'invented for testing and is not the book.</p></div>') if snap["synthetic"] else ""
    head = page_head("Performance", "Performance", "Live results of our three paper-trading books.",
                     f'<p class="meta" style="color:rgba(255,255,255,0.7);margin-top:14px">Updated {escape(when(exported))}</p>')
    return head + banner + portfolio_section(snap) + positioning_section(snap)


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
