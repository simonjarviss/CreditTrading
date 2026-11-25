"""The page shell shared by every page of the public site: head, navigation, footer, disclaimer.

Standard library only. Every page is static HTML; the one script (static/site.js) only
draws chart tooltips. The Content-Security-Policy the web server sends
(dashboard/deploy/Caddyfile.tmpl) allows nothing from another origin.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
from html import escape
from pathlib import Path

SITE_NAME = "Event Driven Trading"
TEAM_LINE = "QUANTT · Queen's University"
CONTACT_EMAIL = "simon.jarvis@queensu.ca"       # team lead, 2026-11-23: the site's contact address
QUANTT_URL = "https://quantt.ca"                 # team lead, 2026-11-24: "add a link to quantt's website from ours"
# What QUANTT stands for, as quantt.ca writes it (its page title, fetched 2026-11-24; team lead, 2026-11-24:
# "spell out what QUANTT means").
QUANTT_NAME = "Queen's University Algorithmic Network & Trading Team"
# No link to the code: the repository is going private (team lead, 2026-11-24, through session 2027-bc), so the
# GitHub link in the header and the research page's ledger and source-code buttons were removed.
# The public address, for the share card's absolute URL: LinkedIn and others fetch og:image from outside.
SITE_URL = "https://event-driven.quantt.ca"
# The team page is the home page (team lead, 2026-11-24: "when we open the page, it should be the team
# page which shows first"); /team/ serves the same page so earlier links still work.
# The overview page was deleted (team lead, 2026-11-24: "delete overview page").
NAV = (("team", "/", "Team"), ("performance", "/performance/", "Performance"),
       ("research", "/research/", "Research"), ("library", "/library/", "Library"), ("contact", "/contact/", "Contact"))

DISCLAIMER = (
    "All performance on this site comes from paper-trading accounts at Alpaca Markets or from "
    "backtests. No client or outside capital is invested. Backtest results are hypothetical, are "
    "shown gross of transaction costs and borrow fees unless stated otherwise, and do not represent "
    "actual trading. Past performance does not guarantee future results. Nothing on this site is an "
    "offer to sell, or a solicitation of an offer to buy, any security or investment product. The "
    "team is part of QUANTT, the Queen's University Algorithmic Network & Trading Team, a student "
    "organisation at Queen's University.")

# Colours of the books, fixed by book and never by rank (validated together on white:
# dataviz validate_palette.js, 2026-11-23, all checks PASS).
BOOK_COLOURS = {"cef": "#295caa", "c4": "#d2691e", "events": "#2a9d8f"}
COMBINED_COLOUR = "#101213"


def fmt_date(d: str) -> str:
    """'2026-11-20' -> '20 November 2026'."""
    t = dt.date.fromisoformat(d)
    return f"{t.day} {t.strftime('%B')} {t.year}"


def when(iso_z: str) -> str:
    """'2026-11-23T22:37:35Z' -> '23 November 2026, 17:37 New York time'. The desk runs on New York time."""
    from zoneinfo import ZoneInfo
    t = dt.datetime.strptime(iso_z, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).astimezone(ZoneInfo("America/New_York"))
    return f"{t.day} {t.strftime('%B')} {t.year}, {t.strftime('%H:%M')} New York time"


def fmt_short(d: str) -> str:
    t = dt.date.fromisoformat(d)
    return f"{t.day} {t.strftime('%b')} {t.year}"


def usd(v: float, signed: bool = False, cents: bool = False) -> str:
    s = f"{abs(v):,.2f}" if cents else f"{abs(v):,.0f}"
    if signed:
        sign = "+" if v > 0 else "−" if v < 0 else ""
    else:
        sign = "−" if v < 0 else ""
    return f"{sign}${s}"


def pct(v: float, signed: bool = False, dp: int = 2) -> str:
    s = f"{abs(v) * 100:.{dp}f}%"
    if signed:
        return ("+" if v > 0 else "−" if v < 0 else "") + s
    return ("−" if v < 0 else "") + s


def tone(v) -> str:
    return "" if v is None or v == 0 else ("pos" if v > 0 else "neg")


STATIC = Path(__file__).resolve().parent / "public" / "static"


_ASSETS = [STATIC]          # where asset_version reads site.css and site.js; site.publish points it at its build


@contextlib.contextmanager
def assets_from(static: Path):
    """Hash the stylesheet and script in `static` while the pages are rendered: site.publish passes its
    build's own copy, so the `?v=` on a page always names the files that build serves (release-check
    review, 2026-11-24: a release checked out during a build could pair the old hash with new CSS)."""
    _ASSETS.append(static)
    try:
        yield
    finally:
        _ASSETS.pop()


def asset_version() -> str:
    """The first 12 hex digits of the SHA-256 of site.css and site.js, put on their URLs.

    WHY (2026-11-24, release-20261123-5): Cloudflare keeps a static file at the edge for an hour and
    a page for a minute, so for up to an hour after a release the new pages were served with the
    previous release's stylesheet. A URL that changes with the file's content is a different cache
    entry (the Worker keys /static/ on `v`), so a page always gets the styles it was built with."""
    h = hashlib.sha256()
    for name in ("site.css", "site.js"):
        h.update((_ASSETS[-1] / name).read_bytes())
    return h.hexdigest()[:12]


def page(active: str, title: str, body: str, description: str) -> str:
    cur = ' aria-current="page"'
    cta = ' class="nav-cta"'
    nav = "".join(f'<a href="{href}"{cur if key == active else ""}{cta if key == "contact" else ""}>'
                  f'{escape(label)}</a>' for key, href, label in NAV)
    foot_nav = "".join(f'<li><a href="{href}">{escape(label)}</a></li>' for key, href, label in NAV if key != "contact")
    full_title = SITE_NAME if active == "team" else f"{title} · {SITE_NAME}"
    return f"""<!doctype html>
<html lang="en-CA">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(full_title)}</title>
<meta name="description" content="{escape(description)}">
<meta name="robots" content="index, follow">
<meta property="og:title" content="{escape(full_title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:type" content="website">
<meta property="og:image" content="{SITE_URL}/static/img/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="627">
<meta property="og:image:alt" content="Event Driven Trading, an event-driven and special situations desk at QUANTT, Queen's University">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0f2547">
<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
<link rel="preload" href="/static/fonts/inter-latin-wght.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/static/fonts/source-serif-4-latin-wght.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/static/site.css?v={asset_version()}">
<script src="/static/site.js?v={asset_version()}" defer></script>
</head>
<body>
<header class="site-header"><div class="wrap">
<a class="brand" href="/" aria-label="{SITE_NAME}, home"><img src="/static/img/quantt-logo.png" alt="QUANTT" width="113" height="28"><span>{SITE_NAME}</span></a>
<nav class="nav" aria-label="Main">{nav}<a class="nav-ext" href="{QUANTT_URL}" rel="noopener">QUANTT<span aria-hidden="true"> ↗</span></a></nav>
</div></header>
<main id="main">
{body}
</main>
<footer class="site-footer"><div class="wrap">
<div class="foot-grid">
<div class="foot-brand"><img class="logo" src="/static/img/quantt-logo-white.png" alt="QUANTT" width="105" height="26">
<p><span class="foot-name">{SITE_NAME}</span>A systematic trading team at <a href="{QUANTT_URL}" rel="noopener">QUANTT</a>, the {QUANTT_NAME}.</p></div>
<nav class="foot-nav" aria-label="Footer"><h4>Site</h4><ul>{foot_nav}</ul></nav>
<div class="foot-contact"><h4>Contact</h4><p>Simon Jarvis<br>Portfolio Manager</p><p><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></p></div>
</div>
<p class="disclaimer">{escape(DISCLAIMER)}</p>
<p class="foot-credits">{photo_credits()}</p>
<p class="foot-base"><span>&copy; {dt.date.today().year} {SITE_NAME}</span><span>QUANTT &middot; Queen's University, Kingston, Ontario</span></p>
</div></footer>
</body>
</html>
"""


# quantt.ca's photographs (team lead, 2026-11-23: "use the same pictures"), one per page head.
PHOTOS = {"overview": "hero-office", "strategy": "presenting", "performance": "markets-ticker",
          "research": "toronto-financial-street", "library": "toronto-financial-day", "team": "campus",
          "contact": "toronto-bay-street", "": "hero-office"}
# Photographs not taken by QUANTT, credited where they are shown (team lead, 2026-11-23: "proper Toronto
# views that fit the darker vibe"; 2026-11-24: "a darker type image of Toronto's skyline / financial
# district but it's day-ish"; "use toronto photos for research and contact pages"). All from Wikimedia
# Commons, fetched 2026-11-24 at 2400 px and re-encoded to WebP with their metadata removed. CC BY-SA
# requires the author and licence to be credited, so the credits are in the footer of every page
# (team lead, 2026-11-24: take the credit off the photographs); the CC0 one is credited as a courtesy.
# The team page shows quantt.ca's campus photograph, Grant Hall from the air (team lead, 2026-11-24: "for the
# team tab lets use a queen's university campus picture instead"); like quantt.ca's other photographs it is
# not credited here. The Toronto skyline it replaced, and its credit, were removed.
PHOTO_CREDITS = {
    "toronto-financial-day": ("Gregory Karastergios", "CC0",
                              "https://commons.wikimedia.org/wiki/File:Toronto_Financial_District.jpg"),
    "toronto-financial-street": ("Ken Lund", "CC BY-SA 2.0",
                                 "https://commons.wikimedia.org/wiki/File:Financial_District,_Toronto,_Ontario_(29376117743).jpg"),
    "toronto-bay-street": ("Dillan Payne", "CC BY-SA 2.0",
                           "https://commons.wikimedia.org/wiki/File:Bay_Street,_Toronto,_March_8_2025.jpg"),
    # The performance page (team lead, 2026-11-24: "the live performance needs a more applicable picture").
    "markets-ticker": ("Francisco Gonzalez", "CC BY 2.0",
                       "https://commons.wikimedia.org/wiki/File:Tickers_(8085342806).jpg"),
}
def photo_credits() -> str:
    """One line naming every photograph not taken by QUANTT, its author and licence, linked to its page."""
    return "Photographs from Wikimedia Commons: " + "; ".join(
        f'<a href="{escape(url)}" rel="noopener">{escape(who)}</a> ({escape(lic)})'
        for who, lic, url in PHOTO_CREDITS.values()) + "."


def photo_style(key: str) -> str:
    return f' style="background-image:url(/static/img/{PHOTOS.get(key, "hero-office")}.webp)"'


# Titles in title case (team lead, 2026-11-24: "capitalize the titles (The Team)"): every page title and
# section heading goes through title_case, so they all follow one rule. Short words stay lower case
# unless first or last; a word that already has a capital (NAV, QUANTT, a name) is kept as written.
SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into", "nor", "of", "on", "or",
               "per", "the", "to", "vs", "with"}


def title_case(s: str) -> str:
    words = s.split(" ")
    out = []
    for i, w in enumerate(words):
        lead = ""
        while w and w[0] in "(\"'“‘":
            lead, w = lead + w[0], w[1:]
        parts = []
        for j, p in enumerate(w.split("-")):
            keep_small = j == 0 and p.lower() in SMALL_WORDS and 0 < i < len(words) - 1 and not lead
            if not p or any(c.isupper() for c in p):
                parts.append(p)
            elif keep_small:
                parts.append(p.lower())
            else:
                parts.append(p[:1].upper() + p[1:])
        out.append(lead + "-".join(parts))
    return " ".join(out)


def page_head(eyebrow: str, title: str, lede: str, extra: str = "", photo: str = "") -> str:
    key = photo or eyebrow.lower()
    return (f'<section class="page-head"{photo_style(key)}><div class="wrap">'
            f'<div class="eyebrow">{escape(eyebrow)}</div>'
            f'<h1>{escape(title_case(title))}</h1><p class="lede">{escape(lede)}</p>{extra}</div></section>')
