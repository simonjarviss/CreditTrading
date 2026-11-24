"""Coverage and wording of the SEC's structured data-set pages, read through the EDGAR client.

    python3 scripts/events/ssx/ssx_data_sec_pages.py [--offline]

Writes `results/events/ssx/ssx_data/sec_pages_2026-10-19.json`: for each page,
the URL, its "Last Reviewed or Updated" line, every downloadable file link it
lists (name only), the first and last period those names encode, and any
sentences that mention terms of use, update cadence or a start date.

WHY THIS EXISTS
---------------
The event-driven expansion (2026-10-19) needs, for every free source, a
coverage start and end that was READ today, not recalled. Desk notes from
2026-10-15 quote "insider data sets January 2006 -> September 2026" and
"13F data sets from 2013Q2"; this re-reads the pages so the data map's dates
carry today's provenance, and adds the pages those notes did not read
(Financial Statement and Notes, N-CEN, the EDGAR full-text-search FAQ, the
SEC's own dissemination terms).

Every request goes through `scripts/data/edgar_client.py` at 1.5 s spacing
(nine other agents share the SEC's fair-access ceiling today; the brief caps
this seat at 150 live requests). Pages are cached by the client, so a re-run
with `--offline` reproduces the JSON without the network.

Coverage is derived from the FILE NAMES the page links to (e.g.
`2026q3_form345.zip`), because a page's prose and its file list have
disagreed before on other SEC pages; the prose sentences are kept beside it so
a reader can see both. A page whose links encode no recognisable period is
reported with `periods: []` -- never with a guessed range.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events" / "ssx" / "ssx_data" / "sec_pages_2026-10-19.json"

PAGES = {
    "insider_transactions": "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets",
    "financial_statements": "https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets",
    "financial_statement_notes": "https://www.sec.gov/data-research/sec-markets-data/financial-statement-notes-data-sets",
    "form_13f": "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets",
    "form_n_port": "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets",
    "form_n_cen": "https://www.sec.gov/data-research/sec-markets-data/form-n-cen-data-sets",
    "fails_to_deliver": "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data",
    "efts_faq": "https://www.sec.gov/edgar/search/efts-faq.html",
    "privacy_dissemination": "https://www.sec.gov/privacy",
    "edgar_apis": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
    # The post-2023-only list: when electronic Form 144 and the 10b5-1 disclosures began.
    "form144_compliance": "https://www.sec.gov/oit/announcement/form-144-electronic-filing-compliance-date",
    "rule10b5_1_guide": ("https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/"
                         "insider-trading-arrangements-and-related-disclosures"),
}

# Period encodings seen in SEC data-set file names.
_PATTERNS = [
    (re.compile(r"(?<!\d)(\d{4})q([1-4])(?!\d)", re.I), lambda m: f"{m[1]}Q{m[2]}"),
    (re.compile(r"(?<!\d)(\d{4})_?(\d{2})(?!\d)"), lambda m: f"{m[1]}-{m[2]}"),
    (re.compile(r"(\d{2})(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{4})", re.I),
     lambda m: f"{m[3]}-{m[2].lower()}"),
]
_KEYWORDS = re.compile(r"(terms|permission|public information|copied|redistribut|commercial|"
                       r"updated|quarterly|monthly|posted|begin|since|from \w+ \d{4}|"
                       r"cannot guarantee|fair access|delay|2001|2006|2009|2013)", re.I)


def _periods(links: list[str]) -> list[str]:
    out = set()
    for href in links:
        name = href.rsplit("/", 1)[-1]
        for rx, fmt in _PATTERNS:
            m = rx.search(name)
            if m:
                out.add(fmt(m))
                break
    return sorted(out)


def parse(html: str) -> dict:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.get_text(" ").split())
    upd = re.search(r"Last Reviewed or Updated:\s*([A-Z][a-z]+\.? \d{1,2}, \d{4})", text)
    links = sorted({a["href"] for a in soup.find_all("a", href=True)
                    if re.search(r"\.(zip|csv|txt|json|tsv)(\?|$)", a["href"], re.I)})
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text)
                 if _KEYWORDS.search(s) and 20 < len(s) < 600]
    per = _periods(links)
    return {"last_reviewed": upd[1] if upd else None, "n_file_links": len(links),
            "first_period": per[0] if per else None, "last_period": per[-1] if per else None,
            "periods": per, "file_links_sample": links[:5] + (links[-5:] if len(links) > 5 else []),
            "keyword_sentences": sentences[:60]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args(argv)
    from scripts.data.edgar_client import EdgarClient, RateLimiter, EdgarHTTPError
    cli = EdgarClient(limiter=RateLimiter(min_interval=1.5), offline=args.offline)
    out, failed = {}, 0
    for key, url in PAGES.items():
        try:
            # max_age_s: a day, so today's run reads today's page, and a re-run today is free.
            html = cli.get_text(url, max_age_s=86400, encoding="utf-8")
            out[key] = {"url": url, **parse(html)}
        except EdgarHTTPError as exc:   # recorded as unreachable, never filled in
            out[key] = {"url": url, "error": str(exc)}
            failed += 1
    out["_run"] = {"live_requests": cli.n_requests, "cache_hits": cli.n_cache_hits}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    for k, v in out.items():
        if k.startswith("_"):
            print(k, v)
        else:
            print(f"{k:28s} {v.get('last_reviewed')!s:22s} files={v.get('n_file_links')} "
                  f"{v.get('first_period')}..{v.get('last_period')} {v.get('error', '')}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
