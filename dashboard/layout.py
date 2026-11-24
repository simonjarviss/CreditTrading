"""The page shell shared by every page of the public site: head, navigation, footer, disclaimer.

Standard library only. Every page is static HTML; the one script (static/site.js) only
draws chart tooltips. The Content-Security-Policy the web server sends
(dashboard/deploy/Caddyfile.tmpl) allows nothing from another origin.
"""
from __future__ import annotations

import datetime as dt
from html import escape

SITE_NAME = "Event Driven Trading"
TEAM_LINE = "QUANTT · Queen's University"
CONTACT_EMAIL = "simon.jarvis@queensu.ca"       # team lead, 2026-11-23: the site's contact address
REPO_URL = "https://github.com/quanttqueensu/CreditTrading"
NAV = (("overview", "/", "Overview"), ("team", "/team/", "Team"), ("performance", "/performance/", "Performance"),
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


def page(active: str, title: str, body: str, description: str) -> str:
    cur = ' aria-current="page"'
    cta = ' class="nav-cta"'
    nav = "".join(f'<a href="{href}"{cur if key == active else ""}{cta if key == "contact" else ""}>'
                  f'{escape(label)}</a>' for key, href, label in NAV if key != "overview")
    foot_nav = "".join(f'<li><a href="{href}">{escape(label)}</a></li>' for key, href, label in NAV if key != "contact")
    full_title = SITE_NAME if active == "overview" else f"{title} · {SITE_NAME}"
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
<link rel="stylesheet" href="/static/site.css">
<script src="/static/site.js" defer></script>
</head>
<body>
<header class="site-header"><div class="wrap">
<a class="brand" href="/" aria-label="{SITE_NAME}, home"><img src="/static/img/quantt-logo.png" alt="QUANTT" width="113" height="28"><span>{SITE_NAME}</span></a>
<nav class="nav" aria-label="Main">{nav}</nav>
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
<p class="foot-base"><span>&copy; {dt.date.today().year} {SITE_NAME}</span><span>QUANTT &middot; Queen's University, Kingston, Ontario</span></p>
</div></footer>
</body>
</html>
"""


# quantt.ca's photographs (team lead, 2026-11-23: "use the same pictures"), one per page head.
PHOTOS = {"overview": "hero-office", "strategy": "presenting", "performance": "hero-office", "research": "roundtable",
          "library": "group-lights", "team": "group-office", "contact": "hero-office", "": "hero-office"}


def photo_style(key: str) -> str:
    return f' style="background-image:url(/static/img/{PHOTOS.get(key, "hero-office")}.webp)"'


def page_head(eyebrow: str, title: str, lede: str, extra: str = "", photo: str = "") -> str:
    return (f'<section class="page-head"{photo_style(photo or eyebrow.lower())}><div class="wrap">'
            f'<div class="eyebrow">{escape(eyebrow)}</div>'
            f'<h1>{escape(title)}</h1><p class="lede">{escape(lede)}</p>{extra}</div></section>')
