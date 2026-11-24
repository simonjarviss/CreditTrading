"""B7: the regulatory compliance-date calendar for CEFs and BDCs, 2015-2026,
read from the SEC's own final-rule releases as published in the Federal Register.

WHY
---
A compliance date can force a fund to trade or delever on a date known months
ahead (a derivatives VaR limit, a names-rule 80% policy, a Treasury-repo
clearing mandate under a PIMCO fund's reverse-repo leverage). For the live CEF
discount book that is a RISK CALENDAR, never a signal: a flag that only
removes. This script collects each release's own DATES paragraph and every
sentence of the release that names a compliance date, so the calendar in the
ssx_risk cards rests on the primary text, not on a law-firm summary.

SOURCE AND TERMS
----------------
The Federal Register API (https://www.federalregister.gov/developers/documentation/api/v1),
no key. The Federal Register is a U.S. government publication; the card
records the API's terms as read on 2026-10-19 (see the cards' REFERENCES rows).
Two requests per document (the JSON record and the full-text XML), spaced 1s.

Every document number below was found with the API's search on 2026-10-19
(the search calls are not part of this script; the numbers are). Re-running
re-fetches nothing that is cached.

Reproduce:
    python3 scripts/events/ssx/ssx_risk_b7_fr_calendar.py            # fetch (cached) + extract
    python3 scripts/events/ssx/ssx_risk_b7_fr_calendar.py --offline  # extract from cache only
Output: results/events/ssx/ssx_risk/b7_fr_calendar.csv and b7_fr_compliance_sentences.txt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import html as _html
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_risk" / "federal_register"
OUT = REPO / "results" / "events" / "ssx" / "ssx_risk"
API = "https://www.federalregister.gov/api/v1/documents/{doc}.json"
UA = "QUANTT research (ssx_risk B7 compliance calendar)"

# doc number -> (short id, why it is on a CEF/BDC risk calendar)
DOCS = {
    "2016-25349": ("N-PORT reporting modernization", "creates N-PORT, the only free CUSIP-level holdings source (B1, B4)"),
    "2017-26922": ("N-PORT EDGAR filing delay", "moves when N-PORT reaches EDGAR"),
    "2019-03958": ("N-PORT filing timing (interim final)", "quarterly filing of monthly reports; which month is public"),
    "2018-18279": ("Rule 15c2-12 amendments (events 15, 16)", "adds financial-obligation events to the EMMA notice list (B1)"),
    "2018-12423": ("Rule 30e-3 notice and access", "shareholder-report delivery; no trading"),
    "2020-07790": ("Securities offering reform for CEFs", "shelf/ATM issuance for listed CEFs and BDCs: supply events"),
    "2020-23355": ("Rule 12d1-4 fund of funds", "limits and voting conditions on funds holding CEFs"),
    "2020-24781": ("Rule 18f-4 derivatives", "VaR limit; reverse repo / TOB treatment for levered CEFs and BDCs"),
    "2020-26971": ("Rule 2a-5 fair value", "valuation designee; NAV smoothing profile can change (BRIEF section 3)"),
    "2022-23756": ("Tailored shareholder reports", "open-end funds; CEF scope to check"),
    "2022-24292": ("Form N-PX proxy votes", "disclosure only"),
    "2023-03566": ("T+1 settlement", "ex-date = record date; recall and borrow timing for shorts"),
    "2023-20793": ("Names rule amendments", "80% policy for CEFs/BDCs whose names suggest a focus"),
    "2025-04705": ("Names rule: compliance extended", "moves the names-rule date"),
    "2026-03459": ("Names rule and N-PORT: compliance extended", "moves the names-rule and N-PORT dates again"),
    "2023-27860": ("Treasury clearing mandate", "repo clearing: PIMCO CEFs lever through reverse repo"),
    "2025-03351": ("Treasury clearing: compliance extended", "moves the cash and repo clearing dates"),
    "2024-19819": ("N-PORT monthly public / N-CEN amendments", "monthly public holdings with a 60-day lag"),
    "2025-06861": ("N-PORT amendments delayed", "moves the monthly-public date"),
    "2023-23050": ("Rule 13f-2 / Form SHO short reporting", "short-position reporting by managers (our side)"),
    "2023-23052": ("Rule 10c-1a securities-loan reporting", "public securities-lending data (borrow, B-side of the book)"),
}

_SENT = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")


def _get(url: str, path: Path, offline: bool) -> bytes:
    if path.exists():
        return path.read_bytes()
    if offline:
        raise FileNotFoundError(f"offline and not cached: {url}")
    import requests
    time.sleep(1.0)
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"GET {url} -> HTTP {r.status_code}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return r.content


def collect(offline: bool) -> tuple[pd.DataFrame, list[str]]:
    rows, sents = [], []
    for doc, (short, why) in DOCS.items():
        j = json.loads(_get(API.format(doc=doc), CACHE / f"{doc}.json", offline))
        xml_url = j.get("full_text_xml_url")
        if not xml_url:
            raise KeyError(f"{doc}: no full_text_xml_url in the API record")
        body = _get(xml_url, CACHE / f"{doc}.xml", offline).decode("utf-8", "replace")
        text = _html.unescape(re.sub(r"<[^>]+>", " ", body))
        text = re.sub(r"\s+", " ", text)
        hits = [s.strip() for s in _SENT.split(text)
                if re.search(r"compliance date|comply with|effective date", s, re.I)]
        rows.append({"document_number": doc, "short": short, "why_on_calendar": why,
                     "title": j.get("title"), "publication_date": j.get("publication_date"),
                     "effective_on": j.get("effective_on"), "dates": (j.get("dates") or "").replace("\n", " "),
                     "release_ids": "; ".join(j.get("docket_ids") or []), "html_url": j.get("html_url"),
                     "n_compliance_sentences": len(hits)})
        sents.append(f"##### {doc} | {short} | {j.get('publication_date')}\nDATES: {j.get('dates')}\n")
        sents += [f"  - {h[:700]}" for h in hits[:60]]
    return pd.DataFrame(rows), sents


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    df, sents = collect(a.offline)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "b7_fr_calendar.csv", index=False)
    (OUT / "b7_fr_compliance_sentences.txt").write_text("\n".join(sents))
    print(df[["document_number", "short", "publication_date", "effective_on"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
