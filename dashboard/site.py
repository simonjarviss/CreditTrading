"""The public site: every page, built from one snapshot and the files in this repository.

    python3 -m dashboard.site --snapshot snapshot.json --out /srv/quantt-site

WHY (team lead, 2026-11-23): "a site that shows team overview, ... everything
someone who would want to give us capital would see", "our library (all literary sources)",
"anything any R&D website would have", hosted from the VM at event-driven.quantt.ca for anyone
to read. quantt.ca, the club's site, is the style reference only.

WHAT IS LIVE AND WHAT IS FIXED. The performance page and the figures on the overview come
from the night's snapshot (dashboard/export.py), so they are measured at build time. The
words, the team and the library are files in this repository
(dashboard/content/, dashboard/public/static/), so they change only with a site release. The public
address's Cloudflare Worker only relays and caches what the VM serves (dashboard/worker/index.js), so
a page and its styles always come from the same release. The research ledger count is read from
results/IDEA_LEDGER.md of the same release.

PUBLISHING IS ATOMIC. Pages are written into a new directory beside the served one, then a
symlink `current` is swapped to it with one rename, so a reader never sees half a site. The
last three builds are kept.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from html import escape
from pathlib import Path

from dashboard import build as perf, charts, metrics as M, snapshot as S
from dashboard.layout import (BOOK_COLOURS, BOOK_TEXT, CONTACT_EMAIL, REPO_URL, fmt_date, fmt_short, page, page_head, pct,
                              photo_style, tone, usd, when)

HERE = Path(__file__).resolve().parent
CONTENT = HERE / "content"
STATIC = HERE / "public" / "static"
REPO = HERE.parent
KEEP_BUILDS = 3


STAGES = (
    ("Idea", "Every idea starts from a mechanism and a counterparty: who loses money to the trade, and why they keep "
             "trading that way."),
    ("Explore", "A gross backtest on our single research harness, split into early and late periods and two or more "
                "market regimes, with a capacity check at $1 million, $5 million and $10 million."),
    ("Paper", "Ideas that clear Explore trade in a paper account or a simulated book on live data, scored every "
              "session."),
    ("Go-live proposal", "Costs measured from paper fills, borrow availability, capacity and a strategy-specific "
                         "bar, put to the team for a decision."),
    ("Live", "Real capital, market-on-close execution and the full set of pre-trade checks."),
)


def date_range(first: str, last: str) -> str:
    """"29 Sep to 20 Nov 2026"; both years when they differ."""
    a, b = fmt_short(first), fmt_short(last)
    return f"{a.rsplit(' ', 1)[0] if first[:4] == last[:4] else a} to {b}"


def stages_html() -> str:
    return '<div class="rows">' + "".join(
        f'<div class="row slim"><div class="num">0{i}</div><div><h3>{escape(t)}</h3><p>{escape(d)}</p></div></div>'
        for i, (t, d) in enumerate(STAGES, start=1)) + "</div>"


# ------------------------------------------------------------------- overview --

def overview(snap: dict) -> str:
    """The front page. Its figures are the portfolio's (build.portfolio: each book from its first
    traded session, the event book included once it trades; team lead, 2026-11-24). A portfolio
    withheld because a book's record could not be read shows no portfolio figure at all."""
    pf = perf.portfolio(snap)
    figs = []
    n_books = sum(1 for b in snap["books"] if "value" in b["session"] or "value" in b["official"])
    figs.append(perf.fig(str(n_books), "Books trading"))
    ev = next((b for b in snap["books"] if b["name"] == "events"), None)
    if ev is not None and "value" in ev["sleeves"]:
        n_strat = len({r["slug"] for r in ev["sleeves"]["value"]["rows"] if r["slug"] != "_book"})
        figs.append(perf.fig(str(n_strat + sum(1 for b in snap["books"] if b["name"] != "events")),
                             "Systematic strategies"))
    if pf["p"] and not pf["blocked"]:
        p = pf["p"]
        figs.append(perf.fig(pct(p["cum_return"], True),
                             f"Portfolio return, {date_range(pf['first'], p['last_date'])}"))
        figs.append(perf.fig(usd(p["pnl"], True), f"Portfolio P&amp;L over {p['n']} sessions"))
    hero = (f'<section class="hero"{photo_style("overview")}><div class="wrap">'
            '<div class="eyebrow">QUANTT &middot; Queen\'s University</div>'
            '<h1>Event Driven Trading</h1>'
            '<p class="lede">A systematic trading team. Three automated books trade closed-end fund discounts '
            'and scheduled corporate events, each in its own paper account.</p>'
            '<div class="buttons"><a class="btn primary" href="/team/">Meet the team</a>'
            '<a class="btn ghost" href="/performance/">Live performance</a></div>'
            '</div></section>')
    kf = (f'<section class="kf"><div class="wrap"><div class="figures">{"".join(figs)}</div>'
          f'<p class="meta note">Live figures, updated {escape(when(snap["exported_at_utc"]))} from the trading '
          'system\'s records. Paper trading only.</p></div></section>')
    traded = {x["b"]["name"]: x for x in pf["books"]}
    rows_html = []
    for i, b in enumerate(snap["books"], start=1):
        if b["name"] in traded:
            x = traded[b["name"]]
            stat = (f'<b class="{tone(x["p"]["pnl"])}">{usd(x["p"]["pnl"], True)}</b>'
                    f'<span>Paper P&amp;L since {fmt_short(x["first"])}</span>')
        else:
            why = next((w for bb, w in pf["excluded"] + pf["blocked"] if bb is b), perf.started_text(b))
            stat = f'<span>{escape(why[:1].upper() + why[1:])}</span>'
        stat += f'<a class="link-arrow" href="/performance/#{escape(b["name"])}">Results</a>'
        rows_html.append(f'<div class="row"><div class="num">0{i}</div><div><h3>'
                         f'<span class="dot" style="background:{BOOK_COLOURS.get(b["name"], "#111418")}"></span>'
                         f'{escape(b["title"])}</h3><p>{escape(BOOK_TEXT.get(b["name"], ""))}</p></div>'
                         f'<div class="stat">{stat}</div></div>')
    approach = ('<section class="section"><div class="wrap sec-grid"><div class="sec-label">'
                '<div class="eyebrow">Approach</div><h2>Three books, one portfolio</h2>'
                '<p class="lede">Each book runs a fully specified rule set. The system decides after the close, '
                'trades at the next close and reports each morning, with no manual intervention.</p>'
                '<a class="link-arrow" href="/research/">How we research</a></div>'
                f'<div class="sec-body"><div class="rows">{"".join(rows_html)}</div></div></div></section>')
    performance = ""
    if pf["p"] and not pf["blocked"]:
        line = [{"name": "Portfolio", "color": "#111418", "bold": True,
                 "points": M.index_points(pf["dated"], pf["base"])}]
        performance = ('<section class="section soft"><div class="wrap sec-grid"><div class="sec-label">'
                       '<div class="eyebrow">Performance</div><h2>Paper results to date</h2>'
                       '<p class="lede">The portfolio\'s cumulative return, each book from its first traded session, '
                       'from Alpaca\'s records, gross of the costs a paper account does not charge.</p>'
                       '<a class="link-arrow" href="/performance/">Performance and risk</a></div>'
                       '<div class="sec-body">' + charts.line_chart(line, "Cumulative return of the portfolio", fmt="pct")
                       + '</div><div class="sec-full">' + perf.summary_table(snap) + '</div></div></section>')
    opportunity = ('<section class="section"><div class="wrap split">'
                   '<img class="photo" src="/static/img/group-lights.webp" alt="QUANTT members at a firm visit, January 2026" loading="lazy">'
                   '<div><div class="eyebrow">The opportunity</div><h2>Why the mispricing persists</h2>'
                   '<div class="grid" style="margin-top:40px;gap:28px 36px">'
                   '<div><h3>No arbitrage link</h3><p class="meta">A closed-end fund has a fixed share count and no '
                   'creation or redemption, so nothing forces its price to net asset value.</p></div>'
                   '<div><h3>Income-driven holders</h3><p class="meta">Most holders buy for yield. Discounts track '
                   'their sentiment and their year-end tax-loss selling.</p></div>'
                   '<div><h3>Forced, scheduled flows</h3><p class="meta">Income buyers crowd distribution dates, and '
                   'unit trusts must sell their holdings by a fixed termination date.</p></div>'
                   '<div><h3>Too small for large funds</h3><p class="meta">A few million dollars a day of volume and '
                   'limited borrow keep institutional capital out.</p></div>'
                   '</div></div></div></section>')
    process = ('<section class="section soft"><div class="wrap sec-grid"><div class="sec-label">'
               '<div class="eyebrow">Process</div><h2>From idea to live capital</h2>'
               '<a class="link-arrow" href="/research/">How we research</a></div>'
               '<div class="sec-body">' + stages_html() + '</div></div></section>')
    members = json.loads((CONTENT / "team.json").read_text())["members"]
    people = "".join(person_card(m) for m in members)
    team = ('<section class="section"><div class="wrap sec-grid"><div class="sec-label">'
            '<div class="eyebrow">The team</div><h2>Who we are</h2>'
            '<p class="lede">Four Queen\'s University students at QUANTT, covering portfolio management, risk, '
            'research and data.</p><a class="link-arrow" href="/team/">The team</a></div>'
            f'<div class="sec-body"><div class="people">{people}</div></div></div></section>')
    return page("overview", "Overview", hero + team + kf + approach + performance + opportunity + process + contact_band(),
                "A systematic trading team at QUANTT, Queen's University, trading closed-end fund discounts "
                "and scheduled corporate events.")


def contact_band() -> str:
    return ('<section class="section dark"><div class="wrap sec-grid"><div class="sec-label">'
            '<div class="eyebrow">Contact</div><h2>Speak with the team</h2></div>'
            '<div class="sec-body"><p class="lede">For questions about the strategies, the results or an allocation, '
            'contact Simon Jarvis, Portfolio Manager.</p>'
            f'<div class="buttons"><a class="btn primary" href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></div>'
            '</div></div></section>')


# ------------------------------------------------------------------- research --

def ledger_count(path: Path) -> tuple:
    """(rows, earliest date) of the idea ledger's tables, one row per idea tested or carded,
    including the backfill of everything tested before 2026-11-09. Raises if the file is
    missing or has no rows."""
    dates = [m.group(1) for ln in path.read_text().splitlines()
             if (m := re.match(r"^\|\s*(20\d\d-\d\d-\d\d)\s*\|", ln))]
    if not dates:
        raise ValueError(f"{path} has no ledger rows")
    return len(dates), min(dates)


PRINCIPLES = (
    ("The idea card", "Each idea is written up before it is tested: the mechanism that creates the mispricing, the "
                      "counterparty and why they keep trading that way, why the effect persists, where it has appeared "
                      "in past markets, the data that tests it, its capacity and its expected correlation with the books "
                      "we hold."),
    ("No lookahead", "A signal uses only information available at the moment of the decision: net asset values at "
                     "their publication lag, filings at their acceptance time, index membership as of the day and "
                     "macroeconomic data at its first release."),
    ("One execution convention", "Every backtest decides at the close of day t, trades at the close of day t+1 and "
                                 "earns the return from there, which is how the books trade."),
    ("Robustness", "Each result is split into early and late periods and into two or more market regimes, and reported "
                   "with its exposure to equity, rates and credit and its correlation with the books already held."),
)
TRADING_DAY = (
    ("Evening", "Collect", "Closing prices and net asset values are downloaded and checked."),
    ("22:00 ET", "Decide", "Each book computes its targets and the order list."),
    ("Pre-trade", "Check", "Nine pre-trade checks run before anything is sent."),
    ("Before the close", "Send", "Orders go to Alpaca for execution at the close."),
    ("17:30 ET", "Reconcile", "Fills and positions are reconciled with the broker."),
    ("Morning", "Report", "P&L, risk and data-quality reports are written for each book."),
)
CONTROLS = (
    ("Automated", "The books run on a cloud server from tagged releases of the code only. Every change runs the test "
                  "suite before it reaches the server."),
    ("Separate accounts", "Each book trades in its own paper account, because the broker rejects a buy and a sell in "
                          "the same symbol from one account."),
    ("Risk controls", "Each book has a gross exposure limit and drawdown limits at which its size is halved and then "
                      "closed, checked in a risk report every morning."),
)


def _sec(cls: str, eyebrow: str, title: str, lede: str, body: str) -> str:
    return (f'<section class="section{cls}"><div class="wrap sec-grid"><div class="sec-label">'
            f'<div class="eyebrow">{escape(eyebrow)}</div><h2>{escape(title)}</h2>'
            + (f'<p class="lede">{escape(lede)}</p>' if lede else "")
            + f'</div><div class="sec-body">{body}</div></div></section>')


def research(snap: dict, ledger: tuple) -> str:
    """Pipeline, standards, the ledger, the trading day and the controls, each in the site's
    label-and-content grid (team lead, 2026-11-24: "re organize the library / research")."""
    n_ledger, first = ledger
    since = dt.date.fromisoformat(first).strftime("%B %Y")
    n_books = sum(1 for b in snap["books"] if "value" in b["session"] or "value" in b["official"])
    head = page_head("Research", "Research",
                     "How we find, test and promote trading strategies, and the infrastructure that runs them.")
    pipeline = _sec("", "Pipeline", "From idea to live capital",
                    "Every strategy passes through the same five stages. Breadth is the main lever: we keep many ideas "
                    "in testing and in paper trading at once.", stages_html())
    standards = _sec(" soft", "Standards", "How a result is tested",
                     "Four rules every backtest follows before a strategy reaches a paper account.",
                     '<div class="principles">' + "".join(
                         f'<div><span class="k">0{i}</span><h3>{escape(h)}</h3><p>{escape(d)}</p></div>'
                         for i, (h, d) in enumerate(PRINCIPLES, start=1)) + "</div>")
    record = ('<section class="section dark"><div class="wrap sec-grid"><div class="sec-label">'
              '<div class="eyebrow">Record</div><h2>The research ledger</h2>'
              '<p class="lede">Every idea we test is recorded with its data, gross result and status, including the '
              'ideas we set aside. The research code, notes and trading system are public.</p>'
              f'<div class="buttons"><a class="btn primary" href="{REPO_URL}/blob/main/results/IDEA_LEDGER.md" '
              'rel="noopener">Read the ledger</a>'
              f'<a class="btn ghost" href="{REPO_URL}" rel="noopener">Source code on GitHub</a></div></div>'
              '<div class="sec-body"><div class="figures">'
              + perf.fig(str(n_ledger), f"Ideas recorded since {since}")
              + perf.fig(str(n_books), "Books trading on paper")
              + perf.fig(str(len(STAGES)), "Stages from idea to live")
              + "</div></div></div></section>")
    day = _sec("", "Infrastructure", "The trading day",
               "One automated cycle each session, from the evening's data to the morning's reports.",
               '<div class="rows">' + "".join(
                   f'<div class="row slim timed"><div class="num">{escape(w)}</div><div><h3>{escape(a)}</h3>'
                   f'<p>{escape(d)}</p></div></div>' for w, a, d in TRADING_DAY) + "</div>")
    controls = _sec(" soft", "Controls", "Safeguards", "",
                    '<div class="principles three">' + "".join(
                        f'<div><h3>{escape(h)}</h3><p>{escape(d)}</p></div>' for h, d in CONTROLS) + "</div>")
    return page("research", "Research", head + pipeline + standards + record + day + controls,
                "How the Event Driven Trading team researches, tests and runs systematic strategies.")


# -------------------------------------------------------------------- library --

TOPIC_ORDER = ("Closed-end fund discounts", "Stale pricing and NAV mechanics", "Market structure and the closing auction",
               "Short selling and borrow", "Corporate events and special situations",
               "Event-driven anomalies (ex-dates, dividends, earnings, index and fund flows)", "Options and volatility",
               "Statistical and research method", "Portfolio construction and risk", "Industry research",
               "Regulation and rules")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def library(lib: dict) -> str:
    """The sources by topic: a topic list with counts beside them, a search box (static/site.js),
    and one compact row per source: year, title, authors and venue, the note on how we use it, and
    its links (team lead, 2026-11-24: "re organize the library ... its ugly")."""
    entries = lib["entries"]
    topics = [t for t in TOPIC_ORDER if any(e["topic"] == t for e in entries)]
    topics += sorted({e["topic"] for e in entries} - set(topics))
    count = {t: sum(1 for e in entries if e["topic"] == t) for t in topics}
    side = "".join(f'<a href="#{_slug(t)}"><span>{escape(t)}</span><span class="c">{count[t]}</span></a>' for t in topics)
    groups = []
    for t in topics:
        items = sorted((e for e in entries if e["topic"] == t), key=lambda e: (e.get("year") or 0, e.get("authors") or ""))
        rows = []
        for e in items:
            src = ", ".join(x for x in (e.get("authors"), e.get("venue")) if x)
            title = (f'<a href="{escape(e["url"])}" rel="noopener">{escape(e["title"])}</a>' if e.get("url")
                     else escape(e["title"]))
            links = []
            if e.get("url"):
                links.append(f'<a href="{escape(e["url"])}" rel="noopener">Source</a>')
            if e.get("oa_pdf_url"):
                links.append(f'<a href="{escape(e["oa_pdf_url"])}" rel="noopener">Free copy</a>')
            text = " ".join(str(x) for x in (e["title"], e.get("authors"), e.get("venue"), e.get("year"),
                                             e.get("used_for")) if x).lower()
            rows.append(f'<div class="lib-row" data-text="{escape(text)}">'
                        f'<div class="yr">{escape(str(e["year"])) if e.get("year") else ""}</div>'
                        f'<div><div class="t">{title}</div><div class="src">{escape(src)}</div>'
                        + (f'<p class="use">{escape(e["used_for"])}</p>' if e.get("used_for") else "")
                        + '</div>' + f'<div class="links">{"".join(links)}</div></div>')
        groups.append(f'<div class="lib-group" id="{_slug(t)}"><h2>{escape(t)}<small>{count[t]} sources</small></h2>'
                      f'{"".join(rows)}</div>')
    n_pdf = sum(1 for e in entries if e.get("oa_pdf_url"))
    years = [e["year"] for e in entries if e.get("year")]
    head = page_head("Library", "Research library",
                     f"The {len(entries)} sources our strategies rest on: academic papers, industry research and the "
                     "rules that govern the markets we trade, each with a note on how we use it.")
    figs = ('<div class="figures lib-figs">' + perf.fig(str(len(entries)), "Sources")
            + perf.fig(str(n_pdf), "With a free, open-access copy") + perf.fig(str(len(topics)), "Topics")
            + (perf.fig(f"{min(years)}–{max(years)}", "Years of publication") if years else "") + "</div>")
    body = (head + '<section class="section"><div class="wrap">' + figs
            + '<p class="meta lib-note">Each entry links to the publisher or issuer. Each link was matched to its '
              'citation by title, first author and year.</p>'
            + '<div class="lib-layout"><aside class="lib-side" aria-label="Topics">'
              '<input class="lib-search" id="lib-search" type="search" placeholder="Search titles, authors, notes" '
              'aria-label="Search the library" hidden><p class="meta" id="lib-count" aria-live="polite"></p>'
              f'<div class="eyebrow">Topics</div><nav>{side}</nav></aside>'
            + f'<div class="lib-main">{"".join(groups)}</div></div></div></section>')
    return page("library", "Research library", body,
                "The academic literature, industry research and regulation behind the Event Driven Trading strategies.")


# ----------------------------------------------------------------------- team --

def person_card(m: dict) -> str:
    """One team member: headshot, name and LinkedIn (team lead, 2026-11-23: "use the same headshots
    on quantt.ca"; "delete the teams bios, just name and linkedin"; dashboard/content/team.json)."""
    photo = (f'<img class="headshot" src="{escape(m["photo"])}" alt="{escape(m["name"])}" width="480" height="480" '
             'loading="lazy" decoding="async">' if m.get("photo") else "")
    li = (f'<p><a class="link-arrow" href="{escape(m["linkedin"])}" rel="noopener">LinkedIn</a></p>'
          if m.get("linkedin") else "")
    return f'<div class="person">{photo}<h3>{escape(m["name"])}</h3>{li}</div>'


def team(t: dict) -> str:
    cards = [person_card(m) for m in t["members"]]
    head = page_head("Team", "The team",
                     "Four students at Queen's University, part of QUANTT, the Queen's University Algorithmic Network "
                     "and Trading Team.")
    body = (head + f'<section class="section"><div class="wrap"><div class="people">{"".join(cards)}</div></div></section>'
            + contact_band())
    return page("team", "Team", body, "The Event Driven Trading team at QUANTT, Queen's University.")


def contact() -> str:
    head = page_head("Contact", "Contact", "Questions about the strategies, the results or an allocation.")
    body = (head + '<section class="section"><div class="wrap narrow">'
            '<h2>Simon Jarvis</h2><p class="lede">Portfolio Manager</p>'
            f'<p><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></p>'
            '<p class="meta" style="margin-top:24px">The team trades paper accounts only. No client capital is '
            'accepted or invested.</p></div></section>')
    return page("contact", "Contact", body, "Contact the Event Driven Trading team.")


def not_found() -> str:
    return page("", "Page not found", page_head("Error 404", "Page not found",
                                                 "The page you asked for does not exist.",
                                                 '<div class="buttons"><a class="btn primary" href="/">Go to the overview</a></div>'),
                "Page not found.")


# ---------------------------------------------------------------------- build --

def pages(snap: dict, *, content: Path = CONTENT, repo: Path = REPO) -> dict:
    """{relative path: html}. Raises on a missing content file: a page is never built from a default."""
    return {
        "index.html": overview(snap),
        "performance/index.html": perf.render(snap),
        "research/index.html": research(snap, ledger_count(repo / "results" / "IDEA_LEDGER.md")),
        "library/index.html": library(json.loads((content / "library.json").read_text())),
        "team/index.html": team(json.loads((content / "team.json").read_text())),
        "contact/index.html": contact(),
        "404.html": not_found(),
    }


def publish(snap: dict, out_root: Path, now: dt.datetime | None = None, *, static: Path = STATIC,
            content: Path = CONTENT, repo: Path = REPO) -> Path:
    problems = S.validate(snap) + S.find_private(snap)
    if problems:
        raise SystemExit("snapshot refused, no page written:\n  " + "\n  ".join(problems))
    built = pages(snap, content=content, repo=repo)
    now = now or dt.datetime.now(dt.timezone.utc)
    builds = out_root / "builds"
    builds.mkdir(parents=True, exist_ok=True)
    target = builds / now.strftime("%Y%m%dT%H%M%S%fZ")
    tmp = builds / (".tmp-" + target.name)
    shutil.copytree(static, tmp / "static")
    for rel, html in built.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
    (tmp / "robots.txt").write_text("User-agent: *\nAllow: /\n")
    for d, _, files in os.walk(tmp):
        os.chmod(d, 0o755)
        for f in files:
            os.chmod(Path(d) / f, 0o644)
    tmp.rename(target)
    link = out_root / "current"
    tmp_link = out_root / ".current.tmp"
    tmp_link.unlink(missing_ok=True)
    os.symlink(Path("builds") / target.name, tmp_link)
    os.replace(tmp_link, link)
    old = sorted(p for p in builds.iterdir() if p.is_dir() and not p.name.startswith("."))[:-KEEP_BUILDS]
    for p in old:
        shutil.rmtree(p)
    return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True, help="site root: builds/ and the `current` link go here")
    a = ap.parse_args(argv)
    target = publish(json.loads(a.snapshot.read_text()), a.out)
    print(f"published {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
