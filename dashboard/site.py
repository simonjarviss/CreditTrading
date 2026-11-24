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

from dashboard import build as perf, layout as L, snapshot as S
from dashboard.layout import BOOK_COLOURS, CONTACT_EMAIL, page, page_head

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


def books_trading(snap: dict) -> tuple:
    """(books that have sent an order, books whose start could not be read). WHY (release-check
    review, 2026-11-24): counting any book with a session counted the event book's dry runs as trading
    and dropped an unreadable book without a word. A book trades from its first STARTED record."""
    started = sum(1 for b in snap["books"] if "value" in b.get("start", {}))
    unread = sum(1 for b in snap["books"] if S.UNMEASURED in b.get("start", {}))
    return started, unread


def stages_html() -> str:
    return '<div class="rows">' + "".join(
        f'<div class="row slim"><div class="num">0{i}</div><div><h3>{escape(t)}</h3><p>{escape(d)}</p></div></div>'
        for i, (t, d) in enumerate(STAGES, start=1)) + "</div>"


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


# The research page shows "Under construction" while it is rebuilt (team lead, 2026-11-24: "make the
# research tab under construction right now"). Its content is kept below; set False to show it again.
RESEARCH_UNDER_CONSTRUCTION = True


def research_page(snap: dict, ledger_path: Path) -> str:
    if RESEARCH_UNDER_CONSTRUCTION:
        return under_construction()
    return research(snap, ledger_count(ledger_path))


def under_construction() -> str:
    head = page_head("Research", "Research", "Under construction.")
    body = (head + '<section class="section"><div class="wrap narrow"><p>This page is being rebuilt.</p>'
            '<p><a class="link-arrow" href="/performance/">Live performance</a></p></div></section>')
    return page("research", "Research", body, "The Event Driven Trading team's research.")


def research(snap: dict, ledger: tuple) -> str:
    """Pipeline, standards, the ledger, the trading day and the controls, each in the site's
    label-and-content grid (team lead, 2026-11-24: "re organize the library / research")."""
    n_ledger, first = ledger
    since = dt.date.fromisoformat(first).strftime("%B %Y")
    n_books, n_unread = books_trading(snap)
    head = page_head("Research", "Research",
                     "How we find, test and run our strategies.")
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
              'ideas we set aside.</p></div>'
              '<div class="sec-body"><div class="figures">'
              + perf.fig(str(n_ledger), f"Ideas recorded since {since}")
              + perf.fig(str(n_books), "Books trading on paper" + (f" ({n_unread} not read tonight)" if n_unread else ""))
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
                     f"The {len(entries)} sources behind our strategies.")
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
    """One team member: headshot, name, title and LinkedIn (team lead, 2026-11-23: "use the same
    headshots on quantt.ca"; "delete the teams bios, just name and linkedin"; 2026-11-24: "add
    portfolio manager under me, and quantitative trading analyst under the other 3")."""
    photo = (f'<img class="headshot" src="{escape(m["photo"])}" alt="{escape(m["name"])}" width="480" height="480" '
             'loading="lazy" decoding="async">' if m.get("photo") else "")
    li = (f'<p><a class="link-arrow" href="{escape(m["linkedin"])}" rel="noopener">LinkedIn</a></p>'
          if m.get("linkedin") else "")
    role = f'<p class="role">{escape(m["title"])}</p>' if m.get("title") else ""
    return f'<div class="person">{photo}<h3>{escape(m["name"])}</h3>{role}{li}</div>'


# The pod in a line per book and four working rules, for the team page (team lead, 2026-11-24: "a brief
# overview of the multi strategy pod ... organized better", after the team's photographs). The event
# book's line starts with its strategy count, read from its record (event_strategies).
POD_BOOKS = {
    "cef": "Leveraged credit closed-end funds. Long the widest discounts, short the richest, dollar-neutral.",
    "c4": "Equity, preferred and multi-asset closed-end funds, on discount and relative-value signals.",
    "events": "strategies around scheduled corporate events, from fund distributions to trust terminations.",
}
def event_strategies(snap: dict):
    """How many strategies the event book runs, from its sleeve reading; None when that could not be read.
    WHY (release-check review of b76a7f4): "Eight strategies" was written into the text twice, and would
    have gone on saying eight after a sleeve was added or dropped."""
    ev = next((b for b in snap["books"] if b["name"] == "events"), None)
    if ev is None or "value" not in ev["sleeves"]:
        return None
    return len({r["slug"] for r in ev["sleeves"]["value"]["rows"] if r["slug"] != "_book"})


def pod_line(snap: dict, b: dict) -> str:
    text = POD_BOOKS.get(b["name"], "")
    if b["name"] != "events":
        return text
    n = event_strategies(snap)
    return f"{n} {text}" if n is not None else text[:1].upper() + text[1:]


def pod_overview(snap: dict) -> str:
    """The pod under the team: one line and a card per book (team lead, 2026-11-24: the four working rules
    taken out)."""
    cards = "".join(
        f'<div class="pod-card"><h3><span class="dot" style="background:{BOOK_COLOURS.get(b["name"], "#111418")}">'
        f'</span>{escape(b["title"])}</h3><p>{escape(pod_line(snap, b))}</p></div>'
        for b in snap["books"])
    return ('<section class="section soft"><div class="wrap"><div class="eyebrow">The pod</div>'
            '<h2>Event-driven trading and special situations</h2>'
            # Team lead, 2026-11-24: "we are a pod under QUANTT, running an event driven trading and special
            # situations desk".
            '<p class="lede narrow">A pod within QUANTT running an event-driven trading and special situations '
            'desk: three systematic books, managed as one portfolio.</p>'
            f'<div class="pod-grid">{cards}</div>'
            '<a class="link-arrow" href="/performance/">Live performance</a></div></section>')


def team(t: dict, snap: dict) -> str:
    cards = [person_card(m) for m in t["members"]]
    head = page_head("Team", "The team", "Four students at Queen's University, part of QUANTT.")
    body = (head + f'<section class="section"><div class="wrap"><div class="people">{"".join(cards)}</div></div></section>'
            + pod_overview(snap) + contact_band())
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
                                                 '<div class="buttons"><a class="btn primary" href="/">Go to the home page</a></div>'),
                "Page not found.")


# ---------------------------------------------------------------------- build --

def pages(snap: dict, *, content: Path = CONTENT, repo: Path = REPO) -> dict:
    """{relative path: html}. Raises on a missing content file: a page is never built from a default."""
    team_page = team(json.loads((content / "team.json").read_text()), snap)
    return {
        "index.html": team_page,                     # the home page (team lead, 2026-11-24)
        "performance/index.html": perf.render(snap),
        "research/index.html": research_page(snap, repo / "results" / "IDEA_LEDGER.md"),
        "library/index.html": library(json.loads((content / "library.json").read_text())),
        "team/index.html": team_page,                # earlier links to /team/
        "contact/index.html": contact(),
        "404.html": not_found(),
    }


def publish(snap: dict, out_root: Path, now: dt.datetime | None = None, *, static: Path = STATIC,
            content: Path = CONTENT, repo: Path = REPO) -> Path:
    problems = S.validate(snap) + S.find_private(snap)
    if problems:
        raise SystemExit("snapshot refused, no page written:\n  " + "\n  ".join(problems))
    now = now or dt.datetime.now(dt.timezone.utc)
    builds = out_root / "builds"
    builds.mkdir(parents=True, exist_ok=True)
    target = builds / now.strftime("%Y%m%dT%H%M%S%fZ")
    tmp = builds / (".tmp-" + target.name)
    shutil.copytree(static, tmp / "static")                # copied first: the pages hash this copy
    try:
        with L.assets_from(tmp / "static"):
            built = pages(snap, content=content, repo=repo)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
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
