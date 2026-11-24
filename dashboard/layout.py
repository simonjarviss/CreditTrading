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
REPO_URL = "https://github.com/quanttqueensu/CreditTrading"
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
    "team is part of QUANTT, the Queen's University Algorithmic Network and Trading Team, a student "
    "organisation at Queen's University.")

# Colours of the books, fixed by book and never by rank (validated together on white:
# dataviz validate_palette.js, 2026-11-23, all checks PASS).
BOOK_COLOURS = {"cef": "#295caa", "c4": "#d2691e", "events": "#2a9d8f"}
COMBINED_COLOUR = "#101213"
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
<nav class="nav" aria-label="Main">{nav}<a class="nav-gh" href="{REPO_URL}" rel="noopener" aria-label="The team's code on GitHub">{GITHUB_MARK}<span>GitHub</span></a></nav>
</div></header>
<main id="main">
{body}
</main>
<footer class="site-footer"><div class="wrap">
<div class="foot-grid">
<div class="foot-brand"><img class="logo" src="/static/img/quantt-logo-white.png" alt="QUANTT" width="105" height="26">
<p><span class="foot-name">{SITE_NAME}</span>A systematic trading team at QUANTT, Queen's University.</p></div>
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
          "research": "toronto-financial-street", "library": "toronto-financial-day", "team": "toronto-skyline-day",
          "contact": "toronto-bay-street", "": "hero-office"}
# Photographs not taken by QUANTT, credited where they are shown (team lead, 2026-11-23: "proper Toronto
# views that fit the darker vibe"; 2026-11-24: "a darker type image of Toronto's skyline / financial
# district but it's day-ish"; "use toronto photos for research and contact pages"). All from Wikimedia
# Commons, fetched 2026-11-24 at 2400 px and re-encoded to WebP with their metadata removed. CC BY-SA
# requires the author and licence to be credited, so the credits are in the footer of every page
# (team lead, 2026-11-24: take the credit off the photographs); the CC0 one is credited as a courtesy.
PHOTO_CREDITS = {
    "toronto-skyline-day": ("Dlsz", "CC BY-SA 4.0",
                            "https://commons.wikimedia.org/wiki/File:View_of_Toronto_Skyline_from_Toronto_Islands.jpg"),
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
# GitHub's mark (Octicons, MIT licence), inline so the page loads nothing from another origin.
GITHUB_MARK = ('<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" focusable="false"><path fill="currentColor" '
               'd="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 '
               '0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 '
               '0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 '
               '1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 '
               '1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 '
               '1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"/></svg>')


def photo_credits() -> str:
    """One line naming every photograph not taken by QUANTT, its author and licence, linked to its page."""
    return "Photographs from Wikimedia Commons: " + "; ".join(
        f'<a href="{escape(url)}" rel="noopener">{escape(who)}</a> ({escape(lic)})'
        for who, lic, url in PHOTO_CREDITS.values()) + "."


def photo_style(key: str) -> str:
    return f' style="background-image:url(/static/img/{PHOTOS.get(key, "hero-office")}.webp)"'


def page_head(eyebrow: str, title: str, lede: str, extra: str = "", photo: str = "") -> str:
    key = photo or eyebrow.lower()
    return (f'<section class="page-head"{photo_style(key)}><div class="wrap">'
            f'<div class="eyebrow">{escape(eyebrow)}</div>'
            f'<h1>{escape(title)}</h1><p class="lede">{escape(lede)}</p>{extra}</div></section>')
