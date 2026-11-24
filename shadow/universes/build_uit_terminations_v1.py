"""Build `uit_terminations_v1.csv`: when each unit trust of closed-end funds must be wound up.

    QUANTT_ENV_FILE=<env file> python3 -m shadow.universes.build_uit_terminations_v1 crawl
    python3 -m shadow.universes.build_uit_terminations_v1 write        # no network

WHY (results/ideas/2026-11-16_uit_cef_flows.md). A unit investment trust is a fixed portfolio
whose prospectus (EDGAR form 487) prints a Mandatory Termination Date about two years ahead;
the trustee sells every holding in the nine business days up to that date. Closed-end funds
held by such a trust fell about 40bp against other funds into the date and recovered about
33bp over the next three sessions. The shadow book `uit_termination` buys at the close of the
date, so it needs the dates and the funds, and nothing else, long before each one.

WHY A COMMITTED FILE AND NOT A NIGHTLY FETCH. The shadow runner on the VM holds one credential,
the Alpaca data key (shadow/deploy/install_shadow_vm.sh). EDGAR needs the desk's contact
header, which lives in the laptop's env file and is not on the VM, and this book is not a
reason to put it there. A termination date is public two years before it matters, so the
calendar is built here, on the laptop, and committed like `units_v1.csv`. Everything in it is
a fact printed in a public filing, with the filing's accession number beside it.

EVERY REQUEST goes through scripts/data/edgar_client.py (its contact header, its rate limit,
its back-off). The cache is outside the repository, shared with the idea's own crawl
(~/quantt_research/uit_cef_flows/edgar_cache) so that prospectuses already fetched are not
asked for twice; this builder's own working files are in ~/quantt_research/uit_terminations_v1/
and it never writes the idea's files (its idx.csv, filings.jsonl and parquet tables reproduce
the card and must not change).

THE CAP ON THE CRAWL, fixed before it ran:
  * sponsors: First Trust ("FT <n>") and Guggenheim Defined Portfolios, the two the card
    measured. Both print a ticker beside every holding. Invesco prints no tickers; SmartTrust
    and Advisors Disciplined Trust were not measured. None of the three is here.
  * forms 487 FILED from FIRST_FILED (2023-07-01) to the day of the crawl, EVERY one (the
    card read one First Trust filing in three). A trust that terminates on or after
    2026-01-01 and was filed before 2023-07-01 has a term over 30 months and is MISSING. In
    the card's sample 1,174 of 1,212 closed-end trusts had terms of 27 months or less and the
    last longer one was deposited in 2017 [V: computed 2026-11-18 from the idea's tables].
  * a filing is read in full only if "closed-end" appears MIN_MENTIONS (15) times or more in
    its main document, the card's own candidate rule; the rest are counted.
  * forms 24F-2NT (the annual notice of units sold and redeemed) only for registrants with a
    closed-end trust in the calendar.

WHAT IS A CLOSED-END FUND HERE. The card asked CRSP, which is licensed and ends 2025-12-31.
This file may hold public facts only, so the prospectus is asked instead: both sponsors head
each block of the schedule with its kind in capitals ("CLOSED-END FUNDS (50.01%):",
"COMMON STOCKS (49.99%):"). A holding is a closed-end fund when the last such heading above
it, inside its own trust's schedule, begins CLOSED-END FUND. A trust is a closed-end trust
when more than half of its holding lines are (the card's rule), and only the closed-end lines
of closed-end trusts are written. Checked on 2026-11-18 against the card's CRSP rule, locally,
on the trusts of the idea's crawl filed from 2023-07-01: the count is in the README.

NOTHING IS GUESSED AND NOTHING IS DROPPED SILENTLY. A date is read from the filing's text or
the trust is not written. Every candidate filing that yields no trust, and every trust left
out for a reason other than "it holds no closed-end fund", is a row of
`uit_terminations_v1_unparsed.csv` with its accession number and the reason.

The parser is the idea's (results/ideas/uit_cef_flows/parse.py, written before any return
was read), carried here with two changes: holdings are read trust by trust so that each line
knows its heading, and dates are plain `datetime.date`.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import html as _html
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path.home() / "quantt_research" / "uit_terminations_v1"
CACHE = Path.home() / "quantt_research" / "uit_cef_flows" / "edgar_cache"
OLD_LOG = Path.home() / "quantt_research" / "uit_cef_flows" / "filings.jsonl"    # read only
ARCHIVES = "https://www.sec.gov/Archives/"
FIRST_FILED = dt.date(2023, 7, 1)
FIRST_TERMINATION = dt.date(2026, 1, 1)
MIN_MENTIONS = 15
MAX_TERM_DAYS = 366 * 6
MIN_NOTICE_DAYS = 30            # the card asserts a prospectus is filed more than 30 days before T
CURRENT_INDEX_MAX_AGE_S = 6 * 3600
GATEWAY_TRIES, GATEWAY_PAUSE_S = 4, 30.0
SPONSORS = (("First Trust", "FT", re.compile(r"^FT \d+$")),
            ("Guggenheim", "GUGG", re.compile(r"^GUGGENHEIM DEFINED PORTFOLIOS,? SERIES \d+$", re.I)))
CAL_COLS = ["sponsor", "series", "trust", "cik", "accession", "url", "filed", "deposit_date", "termination_date",
            "trusts_in_filing", "symbol", "fund", "pct", "shares", "built"]
UNPARSED_COLS = ["accession", "url", "form", "sponsor", "series", "filed", "trust", "reason"]
NOTICE_COLS = ["cik", "series", "accession", "url", "form", "filed", "fiscal_year_end", "sold_usd", "redeemed_usd", "built"]

# ------------------------------------------------------------------ the prospectus parser (pure)

DATE = r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})"
# The percentage is "4.00%", "4.00" or "(4.00)"; a whole number counts only with its % sign
# ("1%": First Trust's Strategic Dividend Select schedules, which the idea's parser left out).
PCT = r"(?:\(?(\d{1,3}\.\d{1,3})\)?(?:\s?%)?|(\d{1,3})%)"       # "3.50 %" in the 2026 HTML
HOLD = re.compile(r"^[ \t]{0,12}([A-Z]{1,5}(?:[./][A-Z])?)[*+#\s]\s*(\S.*?\S)\s+" + PCT + r"\s+([\d,]+)\s+\$?\s*([\d,]+\.\d+)\s+\$?\s*([\d,]+)\s*$")
TICK = re.compile(r"^[ \t]{0,12}([A-Z]{1,5}(?:[./][A-Z])?)[*+#\s]\s*(\S.*?)\s*$")
CONT = re.compile(r"^[ \t]+(.*?)\s*" + PCT + r"\s+([\d,]+)\s+\$?\s*([\d,]+\.\d+)\s+\$?\s*([\d,]+)\s*$")
# A heading of the schedule: capitals only (no digit, so the registrant's own "FT 12342" line on
# a continued page is not one), then optionally its percentage, "(continued)" and a colon.
KIND = re.compile(r"^\s*([A-Z][A-Z&,'/.\- ]{4,}?)\s*(?:\(\s*\d{1,3}(?:\.\d+)?\s?%\s*\))?\s*(?:\((?:continued|cont'd\.?)\))?\s*:?\s*$")
# One filing in the check below (FT 11411) prints its heading in mixed case, "Closed-End Funds
# (100.00%):". Mixed-case lines are otherwise SUB-headings ("High-Yield Bond Funds (16.66%):")
# and must not count, so only these named kinds are read in any case.
KIND_NAMED = re.compile(r"^\s*(Closed-End Funds?|Common Stocks?|Exchange-Traded Funds?|Real Estate Investment Trusts?|"
                        r"Business Development Compan(?:y|ies)|Master Limited Partnerships?|Preferred Stocks?)"
                        r"\s*(?:\(\s*\d{1,3}(?:\.\d+)?\s?%\s*\))?\s*(?:\((?:continued|cont'd\.?)\))?\s*:?\s*$", re.I)
CLOSED_END = re.compile(r"^CLOSED-END FUNDS?\b", re.I)
FT_HEAD = re.compile(r"Schedule of Investments(?:\s*\(cont'd\.?\))?[ \t]*\n\s*\n((?:[^\n]*\S[^\n]*\n){1,4}?)\s*FT \d+[ \t]*\n(.{0,300}?)Initial\s+Date\s+of\s+Deposit\s*[-\u2013\u2014]\s*" + DATE, re.S)
FT_TERM = re.compile(r"Mandatory\s+Termination\s+Date\s+of\s+" + DATE)
FT_TERM_ANY = re.compile(r"Mandatory\s+Termination\s+Date[^\n]{0,80}?" + DATE)
GU_HEAD = re.compile(r"Trust Portfolio(?:\s*\(continued\))?[ \t]*\n\s*(?:Guggenheim|Claymore)[^\n]*Series\s+\d+[ \t]*\n((?:[^\n]*\S[^\n]*\n){1,3}?)\s*The Trust Portfolio as of the Inception Date,\s+" + DATE, re.S | re.I)
GU_TERM = re.compile(r"^\s*(?:Mandatory\s+)?Termination Date\s+" + DATE, re.M)


def day(s: str) -> dt.date | None:
    """'February 26,\\n2027' -> date. None when the words are not a date: the caller then has
    no date and says so; it never substitutes one."""
    try:
        return dt.datetime.strptime(re.sub(r"\s+", " ", s).strip(), "%B %d, %Y").date()
    except ValueError:
        return None


def main_doc(txt: str) -> str:
    """The first <DOCUMENT> of a complete submission: the prospectus itself."""
    a = txt.find("<DOCUMENT>")
    b = txt.find("</DOCUMENT>", a)
    return txt[a:b] if a >= 0 and b >= 0 else txt


def html_rows(t: str) -> str:
    """Guggenheim files HTML from mid-2020. Each table row becomes one text line (cells joined
    by three spaces, two leading spaces so a wrapped name's second line still reads as a
    continuation) and the plain-text rules then apply unchanged."""
    out = []
    for m in re.finditer(r"<TR[^>]*>(.*?)</TR>", t, re.S | re.I):
        cells = [re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ")).strip()
                 for c in re.findall(r"<TD[^>]*>(.*?)</TD>", m.group(1), re.S | re.I)]
        cells = [c for c in cells if c]
        if cells:
            out.append("  " + "   ".join(cells))
    return "\n".join(out) + "\n"


def html_text(t: str) -> str:
    """First Trust files HTML, not <PRE> text, from 2026 (31 candidate filings of that year had
    "no portfolio header" on the first build, 2026-11-18). A table row becomes one line, as in
    `html_rows`; outside tables a paragraph becomes one line (its own line breaks are layout,
    <br> is a real one) and paragraphs are separated by a blank line, which is what the header
    rule expects between "Schedule of Investments" and the trust's name."""
    def row(m):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<TD[^>]*>(.*?)</TD>", m.group(1), re.S | re.I)]
        cells = [c for c in cells if c and c != "&#160;" and c != "&nbsp;"]
        return "\n\x00" + "   ".join(cells) + "\n" if cells else "\n"
    t = re.sub(r"<TR[^>]*>(.*?)</TR>", row, t, flags=re.S | re.I)
    t = re.sub(r"[ \t\r\n]+", lambda m: "\n" if "\x00" in t[m.end():m.end() + 1] or m.group(0).endswith("\n") and t[m.start() - 1:m.start()] == "\n" else " ", t)
    t = re.sub(r"<BR\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</?(?:P|DIV|TABLE|H\d)\b[^>]*>", "\n\n", t, flags=re.I)
    t = _html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ").replace("\x00", "  ")
    return "\n".join(ln.rstrip() if ln.startswith("  ") else ln.strip() for ln in t.split("\n")) + "\n"


def holdings(segment: str) -> list[dict]:
    """The holding lines of ONE trust's schedule, each with the heading it stands under.

    A holding line is a ticker of one to five capitals, a name, a percentage, a share count, a
    price and a cost, in that order. A long name wraps: the ticker and the start of the name on
    one line, the rest and the four numbers on the next; the two are joined."""
    lines = segment.split("\n")
    full = [HOLD.match(ln) for ln in lines]
    num = lambda dec, whole, sh: (float(dec if dec is not None else whole), int(sh.replace(",", "")))      # noqa: E731
    out, kind, seen = [], None, set()
    for i, ln in enumerate(lines):
        m, row = full[i], None
        if m:
            row = (m.group(1), m.group(2), *num(*m.groups()[2:5]))
        elif i + 1 < len(lines) and full[i + 1] is None:
            a, b = TICK.match(ln), CONT.match(lines[i + 1])
            if a and b and not re.search(r"\d\s*$", ln):
                row = (a.group(1), (a.group(2) + " " + b.group(1)).strip(), *num(*b.groups()[1:4]))
        if row is None:
            k = KIND.match(ln) or KIND_NAMED.match(ln)
            if k:
                kind = k.group(1).strip()
            continue
        if row[0] in seen:
            continue
        seen.add(row[0])
        out.append({"symbol": row[0], "fund": re.sub(r"\s+", " ", _html.unescape(row[1])), "pct": row[2], "shares": row[3],
                    "kind": kind, "closed_end": bool(kind and CLOSED_END.match(kind))})
    return out


def parse(txt: str, code: str) -> tuple[list[dict], list[tuple[str, str]]]:
    """Every trust in one prospectus: ([{trust, deposit, termination, holdings}], [(trust, why
    it was left out)]). `code` is FT or GUGG. A trust with no termination date by the rules
    below is LEFT OUT and named, never dated by guess:
      First Trust  the first "Mandatory Termination Date of <date>" after its schedule header
                   and before the next trust's, else the only such date in the filing;
      Guggenheim   the last "Termination Date <date>" between the previous trust's portfolio
                   and its own, else the only one in the filing."""
    heads, bad = [], []
    for m in (FT_HEAD if code == "FT" else GU_HEAD).finditer(txt):
        heads.append((m.start(), re.sub(r"\s+", " ", m.group(1)).strip(), day(m.group(3) if code == "FT" else m.group(2))))
    if not heads:
        return [], [("", "no portfolio header")]
    trusts: list[dict] = []
    for pos, nm, dep in heads:                    # a "continued" page repeats the header
        if trusts and trusts[-1]["trust"] == nm:
            continue
        trusts.append({"trust": nm, "deposit": dep, "pos": pos})
    all_terms = sorted({d for d in (day(m.group(1)) for m in (FT_TERM_ANY if code == "FT" else GU_TERM).finditer(txt)) if d})
    out = []
    for i, t in enumerate(trusts):
        end = trusts[i + 1]["pos"] if i + 1 < len(trusts) else len(txt)
        term = None
        if code == "FT":
            m = FT_TERM.search(txt, t["pos"], end)
            term = day(m.group(1)) if m else (all_terms[0] if len(all_terms) == 1 else None)
        else:
            prev = trusts[i - 1]["pos"] if i else 0
            ms = [m for m in GU_TERM.finditer(txt, 0, t["pos"]) if m.start() >= prev]
            term = day(ms[-1].group(1)) if ms else (all_terms[0] if len(all_terms) == 1 else None)
        lines = holdings(txt[t["pos"]:end])
        if t["deposit"] is None:
            bad.append((t["trust"], "deposit date is not a date"))
        elif term is None:
            bad.append((t["trust"], "no termination date in the filing text"))
        elif not lines:
            bad.append((t["trust"], "no holding line"))
        elif not (t["deposit"] < term <= t["deposit"] + dt.timedelta(days=MAX_TERM_DAYS)):
            bad.append((t["trust"], f"termination {term} is not within six years after deposit {t['deposit']}"))
        else:
            out.append({"trust": t["trust"], "deposit": t["deposit"], "termination": term, "holdings": lines})
    return out, bad


def parse_document(doc: str, code: str) -> tuple[list[dict], list[tuple[str, str]]]:
    """`parse` on the text as filed; when that finds no portfolio header and the document is
    HTML, on its table rows (Guggenheim from 2020), then on its paragraphs and rows (First
    Trust from 2026). First Trust's older <PRE> text parses as it is."""
    trusts, bad = parse(doc, code)
    no_header = [("", "no portfolio header")]
    if bad == no_header and re.search(r"<TR", doc, re.I):
        for as_text in (html_rows, html_text):
            trusts, bad = parse(as_text(doc), code)
            if bad != no_header:
                break
    return trusts, bad


def is_closed_end_trust(t: dict) -> bool:
    """More than half of the holding lines stand under a CLOSED-END FUNDS heading (the card's
    rule, with the prospectus's own heading in place of CRSP)."""
    h = t["holdings"]
    return sum(x["closed_end"] for x in h) > len(h) / 2


# ------------------------------------------------------------------ the 24F-2NT notice (pure)

AMT = r"\$?\s*(\(?\s*\$?\s*[\d,]+(?:\.\d+)?\s*\)?|-\s*0\s*-)"
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"


def _amount(s: str) -> float:
    s = s.replace("$", "").replace(",", "").replace("(", "").replace(")", "").replace(" ", "")
    return 0.0 if s in ("-0-", "") else float(s)


def _fy(s: str) -> dt.date | None:
    s = re.sub(r"\s+", " ", s).strip()
    for f in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%B %d %Y"):
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def parse_notice(t: str) -> dict | None:
    """Fiscal-year end, units sold (item 5(i)) and units redeemed (5(ii)) from one notice: the
    2022+ XML or the older text. None when any of the three cannot be read."""
    if "<edgarSubmission" in t or "aggregateSalePriceOfSecuritiesSold" in t:
        g = lambda tag: (re.search(rf"<(?:\w+:)?{tag}>\s*([^<]*)<", t) or [None, None])[1]      # noqa: E731
        fy, sold, red = g("lastDayOfFiscalYear"), g("aggregateSalePriceOfSecuritiesSold"), g("aggregatePriceOfSecuritiesRedeemedOrRepurchasedInFiscalYear")
        if fy is None or sold is None or red is None or _fy(fy) is None:
            return None
        try:
            return {"fiscal_year_end": _fy(fy), "sold_usd": abs(float(sold)), "redeemed_usd": abs(float(red))}
        except ValueError:
            return None
    fy = re.search(r"Last day of (?:the )?fiscal year for which this (?:Form|notice) is filed:?\s*(" + MONTH + r"\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})", t, re.I)
    sold = re.search(r"Aggregate sale price of securities sold.*?24\(f\)\s*:?\s*" + AMT, t, re.S | re.I)
    red = re.search(r"redeemed or\s+repurchased during the fiscal year\s*:?\s*" + AMT, t, re.S | re.I)
    if not (fy and sold and red) or _fy(fy.group(1)) is None:
        return None
    return {"fiscal_year_end": _fy(fy.group(1)), "sold_usd": _amount(sold.group(1)), "redeemed_usd": _amount(red.group(1))}


# ------------------------------------------------------------------ the form index (pure)

INDEX_ROW = re.compile(r"^(487|24F-2NT(?:/A)?)\s+(.+?)\s+(\d+)\s+(\d{4}-\d\d-\d\d)\s+(edgar/\S+)\s*$")


def sponsor_of(name: str) -> tuple[str, str] | None:
    for full, code, rx in SPONSORS:
        if rx.match(name.strip()):
            return full, code
    return None


def index_rows(text: str) -> list[dict]:
    """The 487 and 24F-2NT rows of one quarterly form index that belong to a crawled sponsor."""
    out = []
    for ln in text.splitlines():
        m = INDEX_ROW.match(ln)
        if not m:
            continue
        sp = sponsor_of(m.group(2))
        if sp is None:
            continue
        out.append({"form": m.group(1), "sponsor": sp[0], "code": sp[1], "series": m.group(2).strip(),
                    "cik": m.group(3), "filed": m.group(4), "path": m.group(5)})
    return out


def accession_of(path: str) -> str:
    return path.rsplit("/", 1)[-1].removesuffix(".txt")


def quarters(first: dt.date, last: dt.date) -> list[tuple[int, int]]:
    out, y, q = [], first.year, (first.month - 1) // 3 + 1
    while (y, q) <= (last.year, (last.month - 1) // 3 + 1):
        out.append((y, q))
        y, q = (y, q + 1) if q < 4 else (y + 1, 1)
    return out


# ------------------------------------------------------------------ the crawl (network, laptop only)

def _read_cached(path: str) -> str:
    from scripts.data.edgar_client import cache_path
    b = cache_path(ARCHIVES + path, CACHE).read_bytes()
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    return main_doc(b.decode("latin-1"))


def _load_jsonl(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []


def _get(c, url: str, max_age_s=None, text: bool = True):
    """One document through the client, asked for again after a pause when EDGAR's gateway
    times out (HTTP 502/504, seen on 2026-11-18: the client retries only the throttling
    statuses). A slow retry of one request is within the fair-access rules; after
    GATEWAY_TRIES it raises, and the crawl resumes from its log on the next run."""
    import time
    from scripts.data.edgar_client import EdgarHTTPError, EdgarNotFound
    for k in range(GATEWAY_TRIES):
        try:
            return c.get_text(url, max_age_s) if text else c.get(url, max_age_s)
        except EdgarNotFound:
            raise
        except EdgarHTTPError as e:
            if not re.search(r"HTTP 50[0-4]", str(e)) or k == GATEWAY_TRIES - 1:
                raise
            time.sleep(GATEWAY_PAUSE_S)


def crawl(today: dt.date) -> int:
    from scripts.data.edgar_client import EdgarClient, EdgarHTTPError, cache_path
    WORK.mkdir(parents=True, exist_ok=True)
    c = EdgarClient(cache=CACHE)
    # 1 the form indexes. A closed quarter is immutable; the current one is re-read.
    rows = []
    for y, q in quarters(FIRST_FILED, today):
        url = f"{ARCHIVES}edgar/full-index/{y}/QTR{q}/form.gz"
        current = (y, q) == (today.year, (today.month - 1) // 3 + 1)
        rows += index_rows(_get(c, url, CURRENT_INDEX_MAX_AGE_S if current else None))
    rows = [r for r in rows if r["filed"] >= FIRST_FILED.isoformat()]
    (WORK / "index.json").write_text(json.dumps({"read": today.isoformat(), "rows": rows}))
    p487 = [r for r in rows if r["form"] == "487"]
    print(f"index: {len(p487)} forms 487 and {sum(r['form'] != '487' for r in rows)} notices of the two sponsors, "
          f"filed {FIRST_FILED} .. {max(r['filed'] for r in rows)}", flush=True)
    # 2 the prospectuses. One line per filing in this builder's own log; a filing the idea's
    #   crawl already read and found to be no candidate (it deleted the text) is taken from
    #   that log, which is only read.
    log = WORK / "filings.jsonl"
    done = {r["path"] for r in _load_jsonl(log)}
    old = {r["path"]: r for r in _load_jsonl(OLD_LOG)}
    todo = sorted((r for r in p487 if r["path"] not in done), key=lambda r: (r["filed"], r["path"]))
    failed: list = []
    for i, r in enumerate(todo):
        url = ARCHIVES + r["path"]
        cp = cache_path(url, CACHE)
        if not cp.exists() and r["path"] in old and not old[r["path"]]["kept"]:
            n, src = int(old[r["path"]]["closed_end_mentions"]), "idea crawl log"
        else:
            try:
                doc = main_doc(_get(c, url))
            except EdgarHTTPError as e:
                # EDGAR would not serve this one (a gateway time-out on every try). It is NOT
                # logged as read: `write` lists it as unparsed with its accession number, and
                # the next crawl asks again.
                status = (re.search(r"HTTP \d+", str(e)) or [str(type(e).__name__)])[0]
                failed.append({**r, "error": status})
                print(f"  NOT FETCHED ({status}): {r['path']}", flush=True)
                continue
            n, src = len(re.findall(r"closed-end", doc, re.I)), "fetched"
            if n >= MIN_MENTIONS:
                cp.write_bytes(gzip.compress(doc.encode("latin-1"), 6))      # the main document only
            else:
                cp.unlink()
        with log.open("a") as f:
            f.write(json.dumps({**r, "closed_end_mentions": n, "kept": n >= MIN_MENTIONS, "from": src}) + "\n")
        if i % 100 == 0:
            print(f"  487 {i}/{len(todo)} {r['filed']} {r['series']} mentions {n} (requests so far {c.n_requests})", flush=True)
    (WORK / "not_fetched.json").write_text(json.dumps(failed))
    # 3 the notices of registrants with a closed-end trust
    ciks = {r["cik"] for r in _load_jsonl(log) if r["kept"] and _closed_end_in(r)}
    notices = [r for r in rows if r["form"] != "487" and r["cik"] in ciks]
    for i, r in enumerate(notices):
        url = ARCHIVES + r["path"]
        if not cache_path(url, CACHE).exists():
            _get(c, url, text=False)
    print(f"notices: {len(notices)} of {len(ciks)} registrants | requests {c.n_requests}, cache hits {c.n_cache_hits}")
    return 0


def _closed_end_in(r: dict) -> bool:
    trusts, _ = parse_document(_read_cached(r["path"]), r["code"])
    return any(is_closed_end_trust(t) for t in trusts)


# ------------------------------------------------------------------ write the files (no network)

def build_rows(filings: list[dict], read=_read_cached, built: str = "") -> tuple[list[dict], list[dict], Counter]:
    """Calendar rows and unparsed rows from the crawl log. `read(path)` returns a main document."""
    cal, unparsed, n = [], [], Counter()
    for r in sorted(filings, key=lambda r: (r["filed"], r["path"])):
        n["forms 487 in the index"] += 1
        if not r["kept"]:
            n["not read: under 15 mentions of closed-end"] += 1
            continue
        n["candidate filings read"] += 1
        acc, url = accession_of(r["path"]), ARCHIVES + r["path"]
        base = {"accession": acc, "url": url, "form": "487", "sponsor": r["sponsor"], "series": r["series"], "filed": r["filed"]}
        trusts, bad = parse_document(read(r["path"]), r["code"])
        filed = dt.date.fromisoformat(r["filed"])
        for name, why in bad:
            # a trust left out for want of a date or a line may be a closed-end trust: it is listed
            unparsed.append({**base, "trust": name, "reason": why})
            n["trusts unparsed"] += 1
        if not trusts and not bad:
            unparsed.append({**base, "trust": "", "reason": "no trust found"})
        for t in trusts:
            n["trusts parsed"] += 1
            if all(h["kind"] is None for h in t["holdings"]):
                unparsed.append({**base, "trust": t["trust"], "reason": "no heading above the holdings: cannot tell what they are"})
                n["trusts unparsed"] += 1
                continue
            if not is_closed_end_trust(t):
                n["trusts that are not closed-end trusts"] += 1
                continue
            n["closed-end trusts"] += 1
            if (t["termination"] - filed).days <= MIN_NOTICE_DAYS:
                unparsed.append({**base, "trust": t["trust"], "reason": f"termination {t['termination']} is within {MIN_NOTICE_DAYS} days of the filing"})
                n["trusts unparsed"] += 1
                continue
            if t["termination"] < FIRST_TERMINATION:
                n["closed-end trusts terminating before 2026-01-01"] += 1
                continue
            n["closed-end trusts in the calendar"] += 1
            for h in t["holdings"]:
                if h["closed_end"]:
                    cal.append({"sponsor": r["sponsor"], "series": r["series"], "trust": t["trust"], "cik": r["cik"], "accession": acc,
                                "url": url, "filed": r["filed"], "deposit_date": t["deposit"].isoformat(),
                                "termination_date": t["termination"].isoformat(), "trusts_in_filing": len(trusts),
                                "symbol": h["symbol"], "fund": h["fund"], "pct": h["pct"], "shares": h["shares"], "built": built})
    return cal, unparsed, n


def _write_csv(path: Path, cols: list, rows: list) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def write(today: dt.date) -> int:
    from scripts.data.edgar_client import cache_path
    filings = _load_jsonl(WORK / "filings.jsonl")
    index = json.loads((WORK / "index.json").read_text())
    failed = json.loads((WORK / "not_fetched.json").read_text())
    missing = {r["path"] for r in index["rows"] if r["form"] == "487"} - {r["path"] for r in filings} - {r["path"] for r in failed}
    if missing:
        raise SystemExit(f"{len(missing)} forms 487 in the index have not been read: run `crawl` to the end first")
    built = index["read"]
    cal, unparsed, n = build_rows(filings, built=built)
    for r in failed:
        unparsed.append({"accession": accession_of(r["path"]), "url": ARCHIVES + r["path"], "form": "487", "sponsor": r["sponsor"],
                         "series": r["series"], "filed": r["filed"], "trust": "",
                         "reason": f"not fetched: EDGAR answered {r['error']} on every try; not read, so it may hold a closed-end trust"})
        n["forms 487 EDGAR would not serve"] += 1
    if len({r["accession"] for r in cal}) < 50:
        raise SystemExit(f"only {len({r['accession'] for r in cal})} filings yield a closed-end trust; refusing to write a calendar this thin")
    ciks = {r["cik"]: r["series"] for r in cal}
    notices = []
    for r in sorted((r for r in index["rows"] if r["form"] != "487" and r["cik"] in ciks), key=lambda r: (r["filed"], r["path"])):
        url = ARCHIVES + r["path"]
        b = cache_path(url, CACHE).read_bytes()
        d = parse_notice((gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b).decode("latin-1"))
        if d is None:
            unparsed.append({"accession": accession_of(r["path"]), "url": url, "form": r["form"], "sponsor": r["sponsor"],
                             "series": r["series"], "filed": r["filed"], "trust": "", "reason": "notice not parsed: no size from it"})
            n["notices unparsed"] += 1
            continue
        n["notices parsed"] += 1
        notices.append({"cik": r["cik"], "series": r["series"], "accession": accession_of(r["path"]), "url": url, "form": r["form"],
                        "filed": r["filed"], "fiscal_year_end": d["fiscal_year_end"].isoformat(),
                        "sold_usd": round(d["sold_usd"], 2), "redeemed_usd": round(d["redeemed_usd"], 2), "built": built})
    _write_csv(HERE / "uit_terminations_v1.csv", CAL_COLS, cal)
    _write_csv(HERE / "uit_terminations_v1_unparsed.csv", UNPARSED_COLS, unparsed)
    _write_csv(HERE / "uit_notices_v1.csv", NOTICE_COLS, notices)
    for k, v in n.items():
        print(f"{v:>7,}  {k}")
    trusts = {(r["accession"], r["trust"]): r for r in cal}
    by = Counter(r["sponsor"] for r in trusts.values())
    print(f"calendar: {len(trusts)} closed-end trusts ({dict(by)}), {len(cal):,} trust-fund rows, "
          f"{len({(r['symbol'], r['termination_date']) for r in cal}):,} fund-events on {len({r['symbol'] for r in cal})} funds, "
          f"terminations {min(r['termination_date'] for r in cal)} .. {max(r['termination_date'] for r in cal)}; "
          f"{len(unparsed)} unparsed rows; index read {built}")
    return 0


def main(argv=None) -> int:
    what = (argv if argv is not None else sys.argv[1:]) or [""]
    today = dt.date.today()
    if what[0] == "crawl":
        return crawl(today)
    if what[0] == "write":
        return write(today)
    raise SystemExit("crawl | write")


if __name__ == "__main__":
    sys.exit(main())
