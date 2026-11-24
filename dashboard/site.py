"""The public site: every page, built from one snapshot and the files in this repository.

    python3 -m dashboard.site --snapshot snapshot.json --out /srv/quantt-site

WHY (team lead, 2026-11-23): "a site that shows team overview, a slideshow ... everything
someone who would want to give us capital would see", "our library (all literary sources)",
"anything any R&D website would have", hosted from the VM at event-driven.quantt.ca for anyone
to read. quantt.ca, the club's site, is the style reference only.

WHAT IS LIVE AND WHAT IS FIXED. The performance page and the figures on the overview come
from the night's snapshot (dashboard/export.py), so they are measured at build time. The
words, the team, the slides and the library are files in this repository
(dashboard/content/, dashboard/public/static/), so they change only with a release; on the public
address Cloudflare serves dashboard/public/ from `main` (dashboard/worker/index.js). The research
ledger count is read from results/IDEA_LEDGER.md of the same release.

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
from dashboard.layout import (BOOK_COLOURS, CONTACT_EMAIL, REPO_URL, fmt_date, fmt_short, page, page_head, pct,
                              photo_style, tone, usd, when)

HERE = Path(__file__).resolve().parent
CONTENT = HERE / "content"
STATIC = HERE / "public" / "static"
REPO = HERE.parent
DECK_PDF = "QUANTT-Event-Driven-Trading.pdf"
KEEP_BUILDS = 3

BOOK_TEXT = {
    "cef": ("A dollar-neutral discount mean-reversion book on 13 leveraged credit closed-end funds. It buys funds "
            "trading at unusually wide discounts to their own history and shorts funds trading unusually rich, "
            "sized to a 6% annual volatility target."),
    "c4": ("The same discount signal, blended at equal risk with a relative-value signal against comparable funds, "
           "applied to 74 equity, preferred and multi-asset closed-end funds. Its returns are close to uncorrelated "
           "with the Fixed Income Book."),
    "events": ("Eight strategies around scheduled events: distribution ex-dates in closed-end funds and partnership "
               "units, special dividends, post-earnings drift in smaller companies, and unit trust terminations."),
}

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


def _official(snap: dict) -> dict:
    return {b["name"]: b["official"]["value"]["rows"] for b in snap["books"] if "value" in b["official"]}


def stages_html() -> str:
    return '<div class="rows">' + "".join(
        f'<div class="row slim"><div class="num">0{i}</div><div><h3>{escape(t)}</h3><p>{escape(d)}</p></div></div>'
        for i, (t, d) in enumerate(STAGES, start=1)) + "</div>"


# ------------------------------------------------------------------- overview --

def overview(snap: dict) -> str:
    series = _official(snap)
    figs = []
    n_books = sum(1 for b in snap["books"] if "value" in b["session"] or "value" in b["official"])
    figs.append(perf.fig(str(n_books), "Books trading"))
    ev = next((b for b in snap["books"] if b["name"] == "events"), None)
    if ev is not None and "value" in ev["sleeves"]:
        n_strat = len({r["slug"] for r in ev["sleeves"]["value"]["rows"] if r["slug"] != "_book"})
        figs.append(perf.fig(str(n_strat + sum(1 for b in snap["books"] if b["name"] != "events")),
                             "Systematic strategies"))
    if "cef" in series:
        s = M.summary(series["cef"])
        figs.append(perf.fig(str(s["n_returns"]), f"Sessions traded since {fmt_short(series['cef'][1]['date'])}"))
    if series:
        rows, _ = M.combined(series)
        c = M.summary(rows)
        figs.append(perf.fig(usd(c["cum_pnl"], True), f"Combined paper P&amp;L to {fmt_short(c['last_date'])}",
                             tone(c["cum_pnl"])))
    hero = (f'<section class="hero"{photo_style("overview")}><div class="wrap">'
            '<div class="eyebrow">QUANTT &middot; Queen\'s University</div>'
            '<h1>Event Driven Trading</h1>'
            '<p class="lede">A systematic trading team. Three automated books trade closed-end fund discounts '
            'and scheduled corporate events, each in its own paper account.</p>'
            '<div class="buttons"><a class="btn primary" href="/performance/">Live performance</a>'
            '<a class="btn ghost" href="/strategy/">Strategy presentation</a></div>'
            '</div></section>')
    kf = (f'<section class="kf"><div class="wrap"><div class="figures">{"".join(figs)}</div>'
          f'<p class="meta note">Live figures, updated {escape(when(snap["exported_at_utc"]))} from the trading '
          'system\'s records. Paper trading only.</p></div></section>')
    rows_html = []
    for i, b in enumerate(snap["books"], start=1):
        stat = ""
        if b["name"] in series:
            s = M.summary(series[b["name"]])
            stat = (f'<b class="{tone(s["cum_pnl"])}">{usd(s["cum_pnl"], True)}</b>'
                    f'<span>Paper P&amp;L since {fmt_short(s["first_date"])}</span>')
        elif "value" in b["session"]:
            stat = f'<b>New</b><span>Trading since {fmt_short(b["session"]["value"]["date"])}</span>'
        stat += f'<a class="link-arrow" href="/performance/#{escape(b["name"])}">Results</a>'
        rows_html.append(f'<div class="row"><div class="num">0{i}</div><div><h3>'
                         f'<span class="dot" style="background:{BOOK_COLOURS.get(b["name"], "#111418")}"></span>'
                         f'{escape(b["title"])}</h3><p>{escape(BOOK_TEXT.get(b["name"], ""))}</p></div>'
                         f'<div class="stat">{stat}</div></div>')
    approach = ('<section class="section"><div class="wrap sec-grid"><div class="sec-label">'
                '<div class="eyebrow">Approach</div><h2>Three books, one portfolio</h2>'
                '<p class="lede">Each book runs a fully specified rule set. The system decides after the close, '
                'trades at the next close and reports each morning, with no manual intervention.</p>'
                '<a class="link-arrow" href="/strategy/">Read the strategy</a></div>'
                f'<div class="sec-body"><div class="rows">{"".join(rows_html)}</div></div></div></section>')
    performance = ""
    if series:
        rows, _ = M.combined(series)
        lines = [{"name": b["title"], "color": BOOK_COLOURS.get(b["name"], "#111418"),
                  "points": perf.cum_points(series[b["name"]])} for b in snap["books"] if b["name"] in series]
        if len(series) > 1:
            lines.append({"name": "Accounts combined", "color": "#111418", "points": perf.cum_points(rows), "bold": True})
        performance = ('<section class="section soft"><div class="wrap sec-grid"><div class="sec-label">'
                       '<div class="eyebrow">Performance</div><h2>Paper results to date</h2>'
                       '<p class="lede">Cumulative profit and loss of each account, from Alpaca\'s official '
                       'end-of-day records, gross of the costs a paper account does not charge.</p>'
                       '<a class="link-arrow" href="/performance/">Performance and risk</a></div>'
                       '<div class="sec-body">' + charts.line_chart(lines, "Cumulative P&L of each account and combined")
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
    team = ('<section class="section"><div class="wrap sec-grid"><div class="sec-label">'
                '<div class="eyebrow">Team</div><h2>The team</h2>'
                '<p class="lede">Four Queen\'s University students covering portfolio management, risk, research '
                'and data.</p><a class="link-arrow" href="/team/">Meet the team</a></div>'
                '<div class="sec-body"><div class="people">'
                + "".join(f'<div class="person"><h3>{escape(m["name"])}</h3><div class="role">{escape(m["title"])}</div></div>'
                          for m in members) + '</div></div></div></section>')
    return page("overview", "Overview", hero + kf + approach + performance + opportunity + process + team + contact_band(),
                "A systematic trading team at QUANTT, Queen's University, trading closed-end fund discounts "
                "and scheduled corporate events.")


def contact_band() -> str:
    return ('<section class="section dark"><div class="wrap sec-grid"><div class="sec-label">'
            '<div class="eyebrow">Contact</div><h2>Speak with the team</h2></div>'
            '<div class="sec-body"><p class="lede">For questions about the strategies, the results or an allocation, '
            'contact Simon Jarvis, Portfolio Manager.</p>'
            f'<div class="buttons"><a class="btn primary" href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></div>'
            '</div></div></section>')


# ------------------------------------------------------------------- strategy --

def strategy(slides: list) -> str:
    first = slides[0]
    thumbs = "".join(
        f'<a href="/static/slides/slide-{s["n"]:02d}.webp" data-title="{escape(s["title"])}" id="t{i + 1}">'
        f'<img loading="lazy" src="/static/slides/slide-{s["n"]:02d}.webp" alt="">'
        f'<span>{i + 1}. {escape(s["title"])}</span></a>' for i, s in enumerate(slides))
    head = page_head("Strategy", "Strategy presentation",
                     "Our strategies in full: the opportunity, each book's rules and backtest, the event strategies, "
                     "portfolio construction, infrastructure and paper results to date.",
                     f'<div class="buttons"><a class="btn primary" href="/static/{DECK_PDF}">Download the PDF</a></div>')
    body = (head + '<section class="section"><div class="wrap">'
            f'<div class="deck" data-count="{len(slides)}"><div class="slide-frame">'
            f'<img src="/static/slides/slide-{first["n"]:02d}.webp" alt="{escape(first["title"])}"></div>'
            '<div class="deck-controls"><button class="prev" type="button">Previous</button>'
            f'<span class="deck-count">Slide 1 of {len(slides)}: {escape(first["title"])}</span>'
            '<button class="next" type="button">Next</button></div>'
            '<p class="meta">Use the arrow keys to move between slides. Backtest figures are gross of costs unless '
            'a slide states otherwise.</p></div>'
            f'<div class="thumbs">{thumbs}</div></div></section>')
    return page("strategy", "Strategy presentation", body,
                "The Event Driven Trading team's strategy presentation: rules, backtests and paper results.")


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


def research(snap: dict, ledger: tuple) -> str:
    n_ledger, first = ledger
    since = dt.date.fromisoformat(first).strftime("%B %Y")
    head = page_head("Research", "Research",
                     "How we find, test and promote trading strategies, and the infrastructure that runs them.")
    card = ('<section class="section"><div class="wrap"><div class="eyebrow">Method</div><h2>The research pipeline</h2>'
            '<p class="lede" style="margin-top:14px">Every strategy passes through the same five stages. Breadth is '
            'the main lever: we keep many ideas in testing and in paper trading at once.</p>' + stages_html()
            + '<div class="grid" style="margin-top:72px">'
            '<div><h3>The idea card</h3><p>Each idea is written up before it is tested: the mechanism that creates '
            'the mispricing, the counterparty and why they keep trading that way, why the effect persists, where it '
            'has appeared in past markets, the data that tests it, its capacity and its expected correlation with '
            'the books we hold.</p></div>'
            '<div><h3>No lookahead</h3><p>A signal uses only information available at the moment of the decision: '
            'net asset values at their publication lag, filings at their acceptance time, index membership as of '
            'the day and macroeconomic data at its first release.</p></div>'
            '<div><h3>One execution convention</h3><p>Every backtest decides at the close of day t, trades at the '
            'close of day t+1 and earns the return from there, which is how the books trade.</p></div>'
            '<div><h3>Robustness</h3><p>Each result is split into early and late periods and into two or more market '
            'regimes, and reported with its exposure to equity, rates and credit and its correlation with the books '
            'already held.</p></div>'
            '</div></div></section>')
    record = ('<section class="section soft"><div class="wrap split"><div><div class="eyebrow">Record</div>'
              '<h2>The research ledger</h2>'
              f'<p class="lede" style="margin-top:14px">Our research ledger records {n_ledger} ideas since {since}, '
              'each with its data, gross result and status, including every idea we set aside.</p>'
              f'<div class="buttons"><a class="btn blue" href="{REPO_URL}/blob/main/results/IDEA_LEDGER.md">Read the ledger</a>'
              f'<a class="btn line" href="{REPO_URL}">Source code on GitHub</a></div>'
              '<p class="meta" style="margin-top:14px">The research code, notes and trading system are public.</p>'
              '</div><img class="photo" src="/static/img/team-atrium.webp" alt="QUANTT members" loading="lazy">'
              '</div></section>')
    infra = ('<section class="section"><div class="wrap"><div class="eyebrow">Infrastructure</div>'
             '<h2>The trading day</h2><div class="stages">'
             + "".join(f'<div class="stage"><span class="k">{t}</span><b>{escape(a)}</b><p class="meta">{escape(d)}</p></div>'
                       for t, a, d in (
                           ("Evening", "Collect", "Closing prices and net asset values are downloaded and checked."),
                           ("22:00 ET", "Decide", "Each book computes its targets and the order list."),
                           ("Pre-trade", "Check", "Nine pre-trade checks run before anything is sent."),
                           ("Before the close", "Send", "Orders go to Alpaca for execution at the close."),
                           ("17:30 ET", "Reconcile", "Fills and positions are reconciled with the broker."),
                           ("Morning", "Report", "P&L, risk and data-quality reports are written for each book.")))
             + '</div><div class="grid" style="margin-top:72px">'
             '<div><h3>Automated</h3><p>The books run on a cloud server from tagged releases of the code only. '
             'Every change runs the test suite before it reaches the server.</p></div>'
             '<div><h3>Separate accounts</h3><p>Each book trades in its own paper account, because the broker rejects '
             'a buy and a sell in the same symbol from one account.</p></div>'
             '<div><h3>Risk controls</h3><p>Each book has a gross exposure limit and drawdown limits at which its size '
             'is halved and then closed, checked in a risk report every morning.</p></div>'
             '</div></div></section>')
    return page("research", "Research", head + card + record + infra,
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
    entries = lib["entries"]
    topics = [t for t in TOPIC_ORDER if any(e["topic"] == t for e in entries)]
    topics += sorted({e["topic"] for e in entries} - set(topics))
    toc = "".join(f'<a href="#{_slug(t)}">{escape(t)}</a>' for t in topics)
    groups = []
    for t in topics:
        items = sorted((e for e in entries if e["topic"] == t), key=lambda e: (e.get("year") or 0, e.get("authors") or ""))
        rows = []
        for e in items:
            src = ", ".join(x for x in (e.get("authors"), str(e["year"]) if e.get("year") else None, e.get("venue")) if x)
            links = []
            if e.get("url"):
                links.append(f'<a href="{escape(e["url"])}" rel="noopener">Source</a>')
            if e.get("oa_pdf_url"):
                links.append(f'<a href="{escape(e["oa_pdf_url"])}" rel="noopener">Free copy</a>')
            rows.append(f'<div class="lib-item"><div class="t">{escape(e["title"])}</div>'
                        f'<div class="src">{escape(src)}</div>'
                        + (f'<div class="use">{escape(e["used_for"])}</div>' if e.get("used_for") else "")
                        + (f'<div class="links">{"".join(links)}</div>' if links else "") + "</div>")
        groups.append(f'<div class="lib-group" id="{_slug(t)}"><h2>{escape(t)}</h2>{"".join(rows)}</div>')
    n_pdf = sum(1 for e in entries if e.get("oa_pdf_url"))
    head = page_head("Library", "Research library",
                     f"The {len(entries)} sources our strategies rest on: academic papers, industry research and the "
                     "rules that govern the markets we trade, each with a note on how we use it.")
    body = (head + '<section class="section"><div class="wrap narrow">'
            f'<p>Each entry links to the publisher or issuer, and {n_pdf} also link to a free, open-access copy. '
            'Each link was matched to its citation by title, first author and year.</p>'
            f'<nav class="toc" aria-label="Topics">{toc}</nav>{"".join(groups)}</div></section>')
    return page("library", "Research library", body,
                "The academic literature, industry research and regulation behind the Event Driven Trading strategies.")


# ----------------------------------------------------------------------- team --

def team(t: dict) -> str:
    cards = []
    for m in t["members"]:
        initials = "".join(w[0] for w in m["name"].split()[:2])
        li = (f'<p><a class="link-arrow" href="{escape(m["linkedin"])}" rel="noopener">LinkedIn</a></p>'
              if m.get("linkedin") else "")
        cards.append(f'<div class="person"><div class="avatar" aria-hidden="true">{escape(initials)}</div>'
                     f'<h3>{escape(m["name"])}</h3><div class="role">{escape(m["title"])}</div>'
                     f'<p>{escape(m["bio"])}</p>{li}</div>')
    head = page_head("Team", "The team",
                     "Four students at Queen's University, part of QUANTT, the Queen's University Algorithmic Network "
                     "and Trading Team.")
    body = (head + f'<section class="section"><div class="wrap"><div class="people">{"".join(cards)}</div></div></section>'
            + '<section class="section tight"><div class="wrap"><img class="photo" style="aspect-ratio:21/9" '
              'src="/static/img/team-atrium.webp" alt="QUANTT members" loading="lazy"></div></section>'
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
    slides = json.loads((content / "slides.json").read_text())
    return {
        "index.html": overview(snap),
        "performance/index.html": perf.render(snap),
        "strategy/index.html": strategy(slides),
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
