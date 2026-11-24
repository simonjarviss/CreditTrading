"""Sponsor distribution releases for the 17 credit CEFs: the ex-date drift trial's declaration source (DG-X2).

    python3 scripts/events/fetch_exdrift_sponsor_releases.py fetch    # GET every release in SOURCES into the cache (public)
    python3 scripts/events/fetch_exdrift_sponsor_releases.py build    # offline: the declaration table for every test event
    python3 scripts/events/fetch_exdrift_sponsor_releases.py verify   # offline: every quote in the table is re-found

WHY THIS EXISTS (team lead's ruling, 2026-10-28)
-------------------------------------------------
Rule 1 of `results/events/PREREG_EXDATE_DRIFT_2026-10-26.md` §4.1 trades an event only if its
distribution was declared on or before e-1. The H-E basket also excludes funds whose ex-dates in
[e+1, e+8] were declared by e-1. Stage 0 found that Alpaca's announcement `declaration_date` is
derived from the record date and is not a declaration (PIMCO's own release of 2025-10-01
contradicts it). The team lead ruled on 2026-10-28:

> "Build a verified declaration table from the sponsors' own monthly distribution releases
> (PIMCO, BlackRock, Nuveen, DoubleLine, AllianceBernstein) for every test event. Keep each
> quote, its URL and fetch time, so it can be re-checked. A fund or event whose release cannot be
> found is excluded and counted, never guessed."

This module is that table's fetcher and builder.

SOURCES. `SOURCES` is a tracked CSV listing one row per release: sponsor, release date, URL,
host, and how it was found. The URLs are copies of each sponsor's own wire release, served to a
plain GET on 2026-10-28:
- markets.financialcontent.com (Business Wire and GlobeNewswire feeds);
- www.nasdaq.com/press-release;
- placera.se and prnewswire.com (PR Newswire).

businesswire.com, globenewswire.com and streetinsider.com refused scripted requests (HTTP 403),
and no block was worked around. Discovery used:
- FinancialContent's per-symbol press-release listing (PIMCO, BlackRock);
- Nasdaq's slug with the month's first business days (PIMCO's 2026 months);
- web search (Nuveen, DoubleLine, AllianceBernstein).
The table records the method per row.

HOW AN EVENT IS CONFIRMED (no guessing).
- Each document is reduced to plain text (`normalise`).
- Every date mention is found: "October 14, 2025", "Oct. 14, 2025", "10/14/2025" and "10/14/25".
- Every mention of one of the 17 tickers is found as a whole word.
- **Association.** A ticker mention is governed by the run of date mentions that ends nearest
  before it. A run is consecutive dates, at most RUN_GAP characters apart, with none of the 17
  tickers between them.
- Fund t's distribution with ex-date e is CONFIRMED by a release if e is a date in the run
  governing some mention of t.
- This fits every format read:
  - PIMCO and Nuveen state the record, ex and payable dates and then list the funds.
  - BlackRock gives a header of months and dates, then each group's funds.
  - DoubleLine and AllianceBernstein state the fund and then its dates. For those two sponsors the
    run that FOLLOWS the mention governs it (`FOLLOWS`).
- The release's date is its dateline or wire timestamp (`release_date_of`). It must equal the
  date the SOURCES row gives when the URL encodes one; a disagreement raises.
- **The declaration date** of (t, e) is the earliest confirming release. A release dated e-1
  passes (reading R4). A later one is "declared late". An event no release confirms is "not found".
  Both are excluded and counted, by the ruling.

QUOTES. Each row of the table carries three verbatim snippets of the normalised text: the
dateline, the governing date run, and the ticker's context. It also carries the document's URL,
sha256 prefix and fetch time. `verify` re-finds every snippet in the cached document, offline, and
raises on any miss.

READ-ONLY, PUBLIC. GETs only, with `scripts/data/fetch_sponsor_notices.UA`, paced. No credential.
Dates and quoted text only: no price, NAV or return is read. Tests:
`scripts/events/tests/test_fetch_exdrift_sponsor_releases.py` (synthetic documents).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT_DIR = REPO / "results" / "events" / "exdrift"
SOURCES = OUT_DIR / "exdrift_release_sources_2026-10-28.csv"
TABLE = OUT_DIR / "exdrift_sponsor_declarations_2026-10-28.csv"
CACHE = OUT_DIR / "_cache_exdrift" / "sponsor_releases"
MANIFEST = CACHE / "manifest.json"
PAUSE_S = 0.6
RUN_GAP = 400            # characters between two dates of one run (a table header or one sentence)
SPONSOR_OF = {**{t: "PIMCO" for t in ("PCN", "PDI", "PDO", "PFN", "PHK", "PTY")},
              **{t: "BlackRock" for t in ("BIT", "HYT", "MHD", "MQY")},
              **{t: "Nuveen" for t in ("JFR", "NAD", "NEA", "NVG", "NZF")},
              "DSL": "DoubleLine", "AWF": "AllianceBernstein"}
FOLLOWS = {"DoubleLine", "AllianceBernstein"}      # fund named first, its dates after
TABLE_COLUMNS = ["ticker", "ex_date", "sponsor", "status", "declared", "url", "sha16", "fetched_utc",
                 "association", "quote_dateline", "quote_dates", "quote_ticker", "releases_confirming"]

MONTHS = ("January February March April May June July August September October November December").split()
_ABBR = {m[:3]: i + 1 for i, m in enumerate(MONTHS)} | {"Sept": 9}
# A stray period after a full month name occurs ("March. 18, 2026", DoubleLine 2026-03); Nasdaq writes
# "Apr 1, 2026" without one; AP style writes "Sept. 13, 2023".
_LONG = r"(?<![A-Za-z])(?P<lm>" + "|".join(MONTHS) + r")\.?\s+(?P<ld>\d{1,2}),\s+(?P<ly>\d{4})"
_SHORT = r"(?<![A-Za-z])(?P<sm>Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?\s?(?P<sd>\d{1,2}),\s+(?P<sy>\d{4})"
_NUM = r"(?<![\d/])(?P<nm>\d{1,2})/(?P<nd>\d{1,2})/(?P<ny>\d{4}|\d{2})(?![\d/])"
DATE_RE = re.compile(f"{_LONG}|{_SHORT}|{_NUM}")
DATELINE_RES = [
    re.compile(r"(?P<d>(?:[A-Z][a-z]{2,8}\.?)\s\d{1,2},\s\d{4})\s*\(GLOBE NEWSWIRE\)"),
    re.compile(r"(?P<d>(?:[A-Z][a-z]{2,8}\.?)\s\d{1,2},\s\d{4})\s*/PRNewswire/"),
    re.compile(r"via (?:Business Wire|GlobeNewswire|PR Newswire|PRNewswire)\s+(?P<d>[A-Z][a-z]+\s\d{1,2},\s\d{4})\s+at"),
    re.compile(r"Published (?P<d>[A-Z][a-z]{2,8}\.?\s\d{1,2},\s\d{4})\s+\d{1,2}:\d{2}\s?[ap]m"),     # nasdaq.com
]


class ReleaseError(RuntimeError):
    """A release cannot be recorded as what it is; named, never filled."""


# --------------------------------------------------------------------------- text

def normalise(raw: bytes | str) -> str:
    """Plain text: PDF text or HTML without scripts, styles and tags; entities unescaped; quotes and
    dashes made plain; whitespace collapsed. Pure."""
    if isinstance(raw, bytes):
        if raw[:5] == b"%PDF-":
            import io
            import pypdf
            t = " ".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(raw)).pages)
        else:
            t = raw.decode("utf-8", errors="replace")
    else:
        t = raw
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = t.replace("–", "-").replace("—", "-").replace("\xa0", " ").replace("​", "")
    return re.sub(r"\s+", " ", t).strip()


def _to_date(m: re.Match) -> pd.Timestamp | None:
    g = m.groupdict()
    try:
        if g.get("lm"):
            return pd.Timestamp(int(g["ly"]), MONTHS.index(g["lm"]) + 1, int(g["ld"]))
        if g.get("sm"):
            return pd.Timestamp(int(g["sy"]), _ABBR[g["sm"][:4] if g["sm"] == "Sept" else g["sm"]], int(g["sd"]))
        y = int(g["ny"])
        return pd.Timestamp(y + 2000 if y < 100 else y, int(g["nm"]), int(g["nd"]))
    except ValueError:            # an impossible date (e.g. 2/30) is not a date mention
        return None


def date_mentions(text: str) -> list[tuple[int, int, pd.Timestamp]]:
    out = []
    for m in DATE_RE.finditer(text):
        d = _to_date(m)
        if d is not None:
            out.append((m.start(), m.end(), d))
    return out


def ticker_mentions(text: str, tickers) -> list[tuple[int, str]]:
    pat = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(sorted(tickers)) + r")(?![A-Za-z0-9])")
    return [(m.start(), m.group(1)) for m in pat.finditer(text)]


def release_date_of(text: str) -> tuple[pd.Timestamp | None, str | None]:
    """The release's own date (dateline or wire timestamp) and the snippet it was read from."""
    for rx in DATELINE_RES:
        m = rx.search(text)
        if m:
            dm = DATE_RE.search(m.group("d"))
            d = _to_date(dm) if dm else None
            if d is not None:
                return d, m.group(0)
    return None, None


def runs(dates: list, ticks: list) -> list[tuple[int, int, list]]:
    """Maximal runs of date mentions: consecutive, at most RUN_GAP apart, no ticker between."""
    tpos = [p for p, _ in ticks]
    out, cur = [], []
    for s, e, d in dates:
        if cur:
            gap_ok = s - cur[-1][1] <= RUN_GAP
            tick_between = any(cur[-1][1] <= p < s for p in tpos)
            if not gap_ok or tick_between:
                out.append((cur[0][0], cur[-1][1], [x[2] for x in cur]))
                cur = []
        cur.append((s, e, d))
    if cur:
        out.append((cur[0][0], cur[-1][1], [x[2] for x in cur]))
    return out


def confirmations(text: str, tickers, sponsor: str) -> dict:
    """{(ticker, ex_date): (run snippet, ticker snippet)} for every (ticker, date) the release associates."""
    ticks = ticker_mentions(text, tickers)
    R = runs(date_mentions(text), ticks)
    out = {}
    for p, t in ticks:
        if sponsor in FOLLOWS:
            gov = next((r for r in R if r[0] > p), None)
        else:
            gov = next((r for r in reversed(R) if r[1] <= p), None)
        if gov is None:
            continue
        snip_run = text[gov[0]:gov[1]]
        snip_t = text[max(0, p - 60):p + 60]
        for d in gov[2]:
            out.setdefault((t, d), (snip_run, snip_t))
    return out


# --------------------------------------------------------------------------- fetch

def _get(url: str):
    import requests
    from scripts.data.fetch_sponsor_notices import UA
    r = requests.get(url, headers={"User-Agent": UA}, timeout=40, allow_redirects=True)
    return r


def fetch(sources: Path = SOURCES, cache: Path = CACHE, sleep=time.sleep, get=_get) -> dict:
    """GET every URL into the cache. A non-200, a redirect to a 404 page, or a block page is
    recorded in the manifest as that, and its releases confirm nothing."""
    S = pd.read_csv(sources, dtype=str)
    cache.mkdir(parents=True, exist_ok=True)
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() and cache == CACHE else {}
    for u in S["url"].dropna().unique():
        if u in man and man[u].get("status") == 200:
            continue
        r = get(u)
        t = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        final = getattr(r, "url", u)
        rec = {"status": int(r.status_code), "fetched_utc": t, "final_url": final}
        if r.status_code == 200 and not str(final).rstrip("/").endswith("/404"):
            raw = r.content
            h = hashlib.sha256(raw).hexdigest()[:16]
            (cache / f"{h}.bin").write_bytes(raw)
            rec["sha16"] = h
        else:
            rec["status"] = int(r.status_code) if r.status_code != 200 else 404
        man[u] = rec
        sleep(PAUSE_S)
    (cache / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True))
    return man


# --------------------------------------------------------------------------- build

def slug_date(url: str) -> pd.Timestamp | None:
    """The release date a URL encodes: FinancialContent `<feed>-YYYY-M-D-`, Nasdaq `-YYYY-MM-DD`, placera `-YYYYMMDD`."""
    m = re.search(r"/article/[a-z]+-(\d{4})-(\d{1,2})-(\d{1,2})-", url)
    if m:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"nasdaq\.com/press-release/.+-(\d{4})-(\d{2})-(\d{2})$", url)
    if m:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"placera\.se/.+-(\d{4})(\d{2})(\d{2})$", url)
    if m:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def read_releases(sources: Path = SOURCES, cache: Path = CACHE) -> list[dict]:
    """Every fetched release: sponsor, url, date, text, sha16, fetched_utc. Raises on a date the
    text and the URL disagree on, and on a release whose date cannot be read at all."""
    S = pd.read_csv(sources, dtype=str)
    man = json.loads((cache / "manifest.json").read_text())
    out = []
    for r in S.drop_duplicates("url").itertuples():
        m = man.get(r.url)
        if m is None:
            raise ReleaseError(f"{r.url} is not in the manifest: run `fetch` first")
        if m.get("status") != 200:
            out.append(dict(sponsor=r.sponsor, url=r.url, date=None, text=None, sha16=None,
                            fetched_utc=m["fetched_utc"], dateline=None, error=f"HTTP {m.get('status')}"))
            continue
        text = normalise((cache / f"{m['sha16']}.bin").read_bytes())
        d_text, snip = release_date_of(text)
        d_url = slug_date(r.url)
        if d_text is not None and d_url is not None and abs((d_text - d_url).days) > 1:
            raise ReleaseError(f"{r.url}: the text dates the release {d_text.date()}, the URL {d_url.date()}")
        d = d_text if d_text is not None else d_url
        if d is None:
            raise ReleaseError(f"{r.url}: no dateline and no date in the URL; the release date is unknown")
        if d_text is None:
            snip = None                      # dated by its URL only; recorded as such
        out.append(dict(sponsor=r.sponsor, url=r.url, date=d, text=text, sha16=m["sha16"],
                        fetched_utc=m["fetched_utc"], dateline=snip, error=None))
    return out


def build(events: pd.DataFrame, sessions: pd.DatetimeIndex, sources: Path = SOURCES,
          cache: Path = CACHE) -> pd.DataFrame:
    """One row per test event (ticker, ex_date): the earliest confirming release, or 'not found'."""
    rel = read_releases(sources, cache)
    tickers = sorted(SPONSOR_OF)
    conf: dict = {}
    for r in rel:
        if r["text"] is None:
            continue
        own = [t for t in tickers if SPONSOR_OF[t] == r["sponsor"]]
        for (t, d), (s_run, s_t) in confirmations(r["text"], own, r["sponsor"]).items():
            conf.setdefault((t, d), []).append((r["date"], r, s_run, s_t))
    spos = {d: i for i, d in enumerate(sessions)}
    rows = []
    for t, e in zip(events.ticker, events.ex_date):
        c = sorted(conf.get((t, e), []), key=lambda x: x[0])
        if not c:
            rows.append(dict(ticker=t, ex_date=e, sponsor=SPONSOR_OF[t], status="not_found", declared=None, url=None,
                             sha16=None, fetched_utc=None, association=None, quote_dateline=None, quote_dates=None,
                             quote_ticker=None, releases_confirming=0))
            continue
        d0, r, s_run, s_t = c[0]
        prev = sessions[spos[e] - 1]
        st = "declared_by_e_minus_1" if d0 <= prev else "declared_late"
        rows.append(dict(ticker=t, ex_date=e, sponsor=SPONSOR_OF[t], status=st, declared=d0, url=r["url"],
                         sha16=r["sha16"], fetched_utc=r["fetched_utc"],
                         association="date run after the ticker" if SPONSOR_OF[t] in FOLLOWS else "date run before the ticker",
                         quote_dateline=r["dateline"] or "(dated by its URL)", quote_dates=s_run[:400], quote_ticker=s_t,
                         releases_confirming=len(c)))
    return pd.DataFrame(rows, columns=TABLE_COLUMNS)


def verify(table: Path = TABLE, cache: Path = CACHE) -> pd.DataFrame:
    """Every quote of every found row re-found in its cached document (offline). Raises on a miss."""
    T = pd.read_csv(table, dtype=str, keep_default_na=False)
    texts, bad = {}, []
    for r in T[T.status != "not_found"].itertuples():
        if r.sha16 not in texts:
            p = cache / f"{r.sha16}.bin"
            if not p.exists():
                raise ReleaseError(f"{p} is not cached: run `fetch`")
            texts[r.sha16] = normalise(p.read_bytes())
        tx = texts[r.sha16]
        for q in (r.quote_dates, r.quote_ticker) + (() if r.quote_dateline == "(dated by its URL)" else (r.quote_dateline,)):
            if q not in tx:
                bad.append((r.ticker, r.ex_date, q[:60]))
    if bad:
        raise ReleaseError(f"{len(bad)} quote(s) not re-found in their cached releases: {bad[:5]}")
    T["ex_date"] = pd.to_datetime(T["ex_date"])
    T["declared"] = pd.to_datetime(T["declared"].replace("", None))
    return T


def coverage(T: pd.DataFrame) -> pd.DataFrame:
    return (T.groupby(["sponsor", "status"]).size().unstack(fill_value=0)
            .reindex(columns=["declared_by_e_minus_1", "declared_late", "not_found"], fill_value=0))


def _events_and_sessions():
    from scripts.events import exdrift_trial as x
    sessions = x.sessions_calendar()
    dn = x.read_dist(x.DIST_REFRESH)
    # Every ex-date from 2023-01-01 to the panel's last, not only the test set's: the H-E declared
    # calendar of an event near the end reads the funds' ex-dates up to e+8, beyond the frozen end.
    last_ex = dn[dn.amount > 0].ex_date.max()
    ev, _ = x.test_events(dn, sessions, last_ex, pd.DataFrame(columns=["ticker", "ex_date", "stock_split"]))
    return ev, sessions


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["fetch", "build", "verify"])
    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        man = fetch()
        st = pd.Series([m["status"] for m in man.values()]).value_counts().to_dict()
        print(f"{len(man)} releases in the manifest; HTTP status counts {st} -> {CACHE.relative_to(REPO)}")
        return 0
    if a.cmd == "build":
        ev, sessions = _events_and_sessions()
        T = build(ev, sessions)
        T.to_csv(TABLE, index=False)
        verify()
        print(coverage(T).to_string())
        print(f"{len(T)} events -> {TABLE.relative_to(REPO)}; every quote re-found")
        return 0
    verify()
    print("every quote re-found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
