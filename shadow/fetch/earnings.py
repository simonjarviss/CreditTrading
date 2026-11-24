"""Quarterly earnings releases for the small-stock drift book: Yahoo's calendar by the day we
first saw each result, and prices for the companies in play.

    SHADOW_STATE_DIR=<dir> QUANTT_ENV_FILE=<key file> python3 -m shadow.fetch.earnings

WHY (results/ideas/2026-11-15_pead_small.md). Stocks ranked 1,501 to 4,000 by size that beat
the analysts' forecast kept rising for 40 sessions, 2000-2025: the long tenth against IWM
was 1.27 gross on the licensed surprise score and 0.68 on the plain surprise a free feed
gives, (reported - forecast) / |forecast|, with every release taken as known one session
after its date. The shadow book runs that free version, so it needs each release's date,
forecast and reported figure, for the whole market, every night.

THE SOURCE. Yahoo Finance's earnings calendar, one page per day
(`finance.yahoo.com/calendar/earnings?day=YYYY-MM-DD`, 100 rows a page): symbol, company,
EPS estimate, reported EPS, market value. Read through yfinance's own session, as its
per-ticker reader does; there is no per-day call in the pinned yfinance. [V 2026-11-15: 530
rows for 2026-11-05 in six pages, 517 with a reported figure; a day seven weeks back still
serves its rows.] HOW GOOD IT IS, against the licensed surprises on five release days of
2025 (05-07, 08-06, 11-04, 11-05, 11-06) [V 2026-11-15]: 1,443 of 1,524 licensed releases
were on Yahoo's page for the same day; where both give a surprise (1,276), the rank
correlation is 0.80 and the sign agrees on 87%; among stocks ranked 1,501-4,000 the two top
tenths share 44 of 64 names. Close, not the same: Yahoo's vendor and its treatment of
one-off items differ, and the card's 0.68 was measured on the licensed figures.

POINT IN TIME. A row is stored the first night Yahoo shows BOTH an estimate and a reported
figure for (symbol, day), stamped `first_seen`, and never changed. The book reads only rows
seen by its decision date, so a result Yahoo posts late starts late, never in hindsight.
`first_run` marks rows stored by the very first fetch, which reaches back BACKFILL_DAYS so
the book does not start empty: those results were public weeks before they were stored,
and what Yahoo shows for them now may have been revised since. The scoreboard cannot tell
a backfilled row from a live one except by this flag.

WHICH COMPANIES. Kept at fetch: Alpaca lists the symbol as an active, tradable asset on an
exchange this desk can mark; Yahoo's company name does not read as a fund, trust, unit,
preferred or depositary receipt; and the market value on the page is at or under MAX_CAP,
scaled by IWM since the end of 2025. MAX_CAP is the size of the 1,500th largest US common
stock at the research panel's last month-end [V: $1.86bn to $1.89bn at ranks 1,500 and
1,501, CRSP, 2025-12-31]; the research used rank, which no free feed has. The price and
dollar-volume floors are the signal's, judged on the decision date.

Writes under <state>/panels/:
  earnings.parquet       [first_seen, first_run, symbol, day, call_time, eps_estimate,
                          reported_eps, market_cap_usd, name, exchange]; rows only added.
  earnings_seen.parquet  [date]: the heartbeat, one row per as-of session a fetch succeeded.
  pead_px.parquet        [date, symbol, close, volume] from Yahoo for IWM and every stored
                          symbol whose release is no more than PX_EVENT_DAYS behind.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys

import pandas as pd

from . import common, yf_px

URL = "https://finance.yahoo.com/calendar/earnings?day={day}&offset={offset}&size=100"
LOOKBACK_DAYS, BACKFILL_DAYS, PX_EVENT_DAYS, PX_DAYS, MAX_PAGES, CHUNK = 7, 75, 70, 45, 40, 250
HEDGE = "IWM"
MAX_CAP_USD, IWM_REF_CLOSE, IWM_REF_DATE = 1.9e9, 246.16, dt.date(2025, 12, 31)   # Yahoo close, fetched 2026-11-15
MARKABLE_EXCHANGES = frozenset({"NYSE", "NASDAQ", "AMEX", "ARCA", "TXSE"})
NOT_A_COMPANY = re.compile(r"\bfund\b|\betf\b|\btrust\b|\bunits?\b|preferred|depositary|\badr\b|\bnotes?\b|warrant|"
                           r"\brights?\b|limited partnership|\bl\.?p\.?\b", re.I)
COLS = ["first_seen", "first_run", "symbol", "day", "call_time", "eps_estimate", "reported_eps",
        "market_cap_usd", "name", "exchange"]
NEED = ("Symbol", "Company", "Earnings Call Time", "EPS Estimate", "Reported EPS", "Market Cap")
_UNIT = {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}


def parse_cap(x) -> float | None:
    """'6.41B' -> 6.41e9. None for a blank or anything else: the row is then left out."""
    if not isinstance(x, str):
        return None
    m = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)([TBMK])\s*", x)
    return float(m.group(1)) * _UNIT[m.group(2)] if m else None


def _num(x: str) -> float:
    """A cell's number; NaN for Yahoo's '-' or a blank. Anything else raises: a figure this
    reader cannot parse must not become a missing one in silence."""
    x = x.strip().replace(",", "")
    if x in ("", "-", "--", "N/A"):
        return float("nan")
    return float(x)


def parse_page(html: str) -> pd.DataFrame | None:
    """The page's one table, or None when it has none (a day with no releases). Raises if the
    table has lost a column this reader needs: a changed page must stop the fetch, not thin it.
    Parsed with BeautifulSoup's built-in parser, which yfinance already installs; pandas'
    `read_html` would need lxml, which the shadow venv's requirements do not carry."""
    from bs4 import BeautifulSoup
    table = BeautifulSoup(html, "html.parser").find("table")
    if table is None:
        return None
    head = [th.get_text(" ", strip=True) for th in table.find_all("th")]
    missing = [c for c in NEED if c not in head]
    if missing:
        raise RuntimeError(f"Yahoo's earnings table has no column(s) {missing}; got {head}")
    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if not cells:
            continue
        if len(cells) != len(head):
            raise RuntimeError(f"Yahoo's earnings table has a row of {len(cells)} cells under {len(head)} headers")
        r = dict(zip(head, cells))
        rows.append({"Symbol": r["Symbol"], "Company": r["Company"], "Earnings Call Time": r["Earnings Call Time"],
                     "EPS Estimate": _num(r["EPS Estimate"]), "Reported EPS": _num(r["Reported EPS"]),
                     "Market Cap": r["Market Cap"]})
    return pd.DataFrame(rows, columns=list(NEED))


def read_day(get, day: dt.date) -> pd.DataFrame:
    """Every row Yahoo lists for `day`. `get(url)` returns the page's text."""
    pages = []
    for k in range(MAX_PAGES):
        df = parse_page(get(URL.format(day=day.isoformat(), offset=100 * k)))
        if df is None or df.empty:
            break
        pages.append(df)
        if len(df) < 100:
            break
    else:
        raise RuntimeError(f"{day}: more than {MAX_PAGES} pages of earnings rows; refusing to continue")
    if not pages:
        return pd.DataFrame(columns=list(NEED))
    out = pd.concat(pages, ignore_index=True)
    return out.drop_duplicates("Symbol", keep="first")


def keep(rows: pd.DataFrame, day: dt.date, assets: dict, max_cap: float) -> list:
    """The rows of one day that can be a small US company with a complete result."""
    out = []
    for r in rows.to_dict("records"):
        sym, est, rep, cap = r["Symbol"], r["EPS Estimate"], r["Reported EPS"], parse_cap(r["Market Cap"])
        a = assets.get(sym)
        name = r["Company"] if isinstance(r["Company"], str) else ""
        if (not isinstance(sym, str) or a is None or a["tradable"] is not True or a["exchange"] not in MARKABLE_EXCHANGES
                or pd.isna(est) or pd.isna(rep) or cap is None or cap > max_cap or not name or NOT_A_COMPANY.search(name)):
            continue
        ct = r["Earnings Call Time"]
        out.append({"symbol": sym, "day": pd.Timestamp(day), "call_time": ct if isinstance(ct, str) else "",
                    "eps_estimate": float(est), "reported_eps": float(rep), "market_cap_usd": cap,
                    "name": name, "exchange": a["exchange"]})
    return out


def merge(old: pd.DataFrame | None, rows: list, today: dt.date) -> pd.DataFrame:
    """Add (symbol, day) pairs not already stored. A stored row is never changed: if Yahoo
    later revises a figure, the book keeps what it traded on."""
    first_run = old is None
    seen = set() if old is None or old.empty else set(zip(old["symbol"], pd.to_datetime(old["day"])))
    add = []
    for r in rows:
        k = (r["symbol"], r["day"])
        if k in seen:
            continue
        seen.add(k)
        add.append({"first_seen": pd.Timestamp(today), "first_run": first_run, **r})
    new = pd.DataFrame(add, columns=COLS)
    if old is None or old.empty:
        return new
    return old[COLS].copy() if new.empty else pd.concat([old[COLS], new], ignore_index=True)


def live_symbols(panel: pd.DataFrame, today: dt.date) -> list:
    if panel.empty:
        return []
    d = pd.to_datetime(panel["day"]).dt.date
    return sorted(set(panel.loc[d >= today - dt.timedelta(days=PX_EVENT_DAYS), "symbol"]) - {HEDGE})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="cef", help="whose key reads the asset list (shadow/sources.py WHICH KEY)")
    a = ap.parse_args(argv)
    from yfinance.data import YfData
    from .. import sources
    today = dt.datetime.now(common.NY).date()
    last = common.last_closed_date()
    d = common.panels_dir()
    p = d / "earnings.parquet"
    old = pd.read_parquet(p) if p.exists() else None
    assets = sources.ReadOnlyData(a.book).asset_table()
    hedge = yf_px.fetch([HEDGE], PX_DAYS, last)
    if hedge.empty:
        raise RuntimeError(f"Yahoo returned no rows for {HEDGE}; the size limit cannot be scaled or the book hedged")
    # the latest close on or before `last`: on a weekend run that is Friday's, and the book's
    # own freshness gate (a required px row dated as-of) decides whether anything is traded
    max_cap = MAX_CAP_USD * float(hedge["close"].iloc[-1]) / IWM_REF_CLOSE
    session = YfData()

    def get(url: str) -> str:
        r = session.get(url)
        if r.status_code != 200:
            raise RuntimeError(f"Yahoo returned HTTP {r.status_code} for the earnings calendar")
        return r.text

    back = BACKFILL_DAYS if old is None else LOOKBACK_DAYS
    rows, n_listed = [], 0
    for k in range(back, -1, -1):
        day = today - dt.timedelta(days=k)
        if day.weekday() >= 5:
            continue
        got = read_day(get, day)
        n_listed += len(got)
        rows += keep(got, day, assets, max_cap)
    out = merge(old, rows, today)
    common.write(out, p.name)
    n_new = len(out) - (0 if old is None else len(old))

    syms = live_symbols(out, today)
    parts = [hedge] + [yf_px.fetch(syms[i:i + CHUNK], PX_DAYS, last) for i in range(0, len(syms), CHUNK)]
    px = pd.concat(parts, ignore_index=True).drop_duplicates(["date", "symbol"])
    common.write(px, "pead_px.parquet")
    no_px = sorted(set(syms) - set(px["symbol"]))

    hp = d / "earnings_seen.parquet"            # last: it says every step above succeeded for this session
    stamp = pd.Timestamp(last)
    seen = pd.read_parquet(hp) if hp.exists() else pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]")})
    if stamp not in set(seen["date"]):
        seen = pd.concat([seen, pd.DataFrame({"date": [stamp]})], ignore_index=True)
    common.write(seen, hp.name)
    print(f"earnings.parquet: {len(out):,} rows ({n_new} new of {n_listed:,} listed over {back + 1} days; size limit "
          f"${max_cap / 1e9:.2f}bn); prices for {px['symbol'].nunique() - 1} of {len(syms)} live symbols"
          + (f", none for {len(no_px)} ({no_px[:8]}...)" if no_px else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
