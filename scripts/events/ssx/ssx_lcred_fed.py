"""Dated Federal Reserve stress-test and capital-rule releases, 2015-2026, from the Fed's own pages.

    python3 scripts/events/ssx/ssx_lcred_fed.py

WHY
---
Idea C3 asks whether bank stress-test results and capital-rule events move bank
preferred calls and issuance enough to be an event family. An event family
needs a dated, point-in-time calendar. The Fed publishes one page per exercise
year (DFAST 2015-2019 at `dfast-YYYY.htm`, 2020+ at `dfa-stress-tests-YYYY.htm`,
CCAR at `ccar-YYYY[-archive].htm`) and each links its press releases, whose URLs
encode the release date (`/newsevents/pressreleases/bcregYYYYMMDDa.htm`). This
script fetches those pages and extracts every linked press release with its
title, so the calendar is fetched, never hand-copied (CLAUDE.md).

Capital-rule events (Basel III endgame and its re-proposal, stress capital
buffer rules) are not on those pages; `CAPITAL_RULE_PAGES` lists the Fed pages
read for them, and the script extracts their press-release links the same way.

The output is a calendar (dates and titles), not a market series.
ZERO TRIALS. Network: federalreserve.gov only, GETs, polite spacing.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx.ssx_lcred_common import CACHE, OUT, write_json

BASE = "https://www.federalreserve.gov"
UA = "QUANTT research script (stress-test calendar; read-only)"
PAGES = ([f"/supervisionreg/dfast-{y}.htm" for y in range(2015, 2020)]
         + [f"/supervisionreg/dfa-stress-tests-{y}.htm" for y in range(2020, 2027)]
         + ["/supervisionreg/ccar-2015.htm", "/supervisionreg/ccar-2016.htm"]
         + [f"/supervisionreg/ccar-{y}-archive.htm" for y in range(2017, 2022)]
         + ["/supervisionreg/large-bank-capital-requirements.htm"])
# Capital-rule press releases are not linked from the exercise pages. These were
# located by search on 2026-10-19 and are FETCHED here, so the title and the date
# (encoded in the URL) come from the Fed, not from the search summary.
CAPITAL_RULE_URLS = ["/newsevents/pressreleases/bcreg20200304a.htm",   # SCB final rule
                     "/newsevents/pressreleases/bcreg20230727a.htm",   # Basel III endgame proposal
                     "/newsevents/pressreleases/bcreg20250417a.htm",   # stress-test averaging proposal
                     "/newsevents/pressreleases/bcreg20251024a.htm",   # stress-test transparency proposal
                     "/newsevents/pressreleases/bcreg20260319a.htm"]   # capital framework re-proposal
LINK_RE = re.compile(r'href="(?:https?://www\.federalreserve\.gov)?(/newsevents/(?:pressreleases/(?:bcreg|other)|press/bcreg/)'
                     r'(\d{8})[a-z]?\.htm)"[^>]*>([^<]+)<', re.I)
TITLE_RE = re.compile(r'<h3 class="title">([^<]+)')
RESULTS_RE = re.compile(r"results? of|releases? results|second round of bank stress test results|"
                        r"annual bank stress test (showed|confirms)|stress test showed", re.I)


def get(path: str) -> str:
    import requests
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / ("fed_" + path.strip("/").replace("/", "_"))
    if f.exists():
        return f.read_text()
    r = requests.get(BASE + path, headers={"User-Agent": UA}, timeout=60)
    time.sleep(1.0)
    if r.status_code == 404:
        raise FileNotFoundError(f"{BASE + path}: HTTP 404")
    r.raise_for_status()
    f.write_text(r.text)
    return r.text


def main() -> int:
    rows = []
    for p in PAGES:
        try:
            html = get(p)
        except FileNotFoundError as e:
            rows.append({"page": p, "url": None, "date": None, "title": f"PAGE MISSING: {e}"})
            continue
        for m in LINK_RE.finditer(html):
            d = dt.datetime.strptime(m.group(2), "%Y%m%d").date()
            rows.append({"page": p, "url": BASE + m.group(1), "date": d, "title": " ".join(m.group(3).split()),
                         "kind": "exercise page link"})
    for u in CAPITAL_RULE_URLS:
        html = get(u)
        t = TITLE_RE.search(html)
        if not t:
            raise ValueError(f"{u}: no title found")
        d = dt.datetime.strptime(re.search(r"(\d{8})", u).group(1), "%Y%m%d").date()
        rows.append({"page": u, "url": BASE + u, "date": d, "title": " ".join(t.group(1).split()),
                     "kind": "capital rule"})
    df = pd.DataFrame(rows)
    ok = df[df.url.notna()].sort_values("kind").drop_duplicates("url").sort_values("date")   # a capital-rule row wins a duplicate
    ok["results_release"] = ok.title.str.contains(RESULTS_RE) & ~ok.title.str.contains("schedule|will be released", case=False)
    ok.to_csv(OUT / "c3_fed_press_releases.csv", index=False)
    res = ok[ok.results_release]
    per_year = res.groupby(pd.to_datetime(res.date).dt.year).date.apply(lambda s: sorted({str(x) for x in s}))
    out = {"fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "pages": len(PAGES),
           "capital_rule_releases": ok[ok.kind == "capital rule"][["date", "title"]].astype(str).values.tolist(),
           "pages_missing": df[df.url.isna()].title.tolist(),
           "press_releases_linked": int(len(ok)),
           "results_release_dates_by_year": {int(k): v for k, v in per_year.items()},
           "distinct_results_dates_2015_2025": int(res[(pd.to_datetime(res.date).dt.year.between(2015, 2025))].date.nunique()),
           "distinct_results_or_capital_dates_2015_2025": int(ok[(ok.results_release | (ok.kind == "capital rule")
               | ok.title.str.contains("individual (?:large bank )?capital requirements|Large Bank Capital Requirements", case=False))
               & pd.to_datetime(ok.date).dt.year.between(2015, 2025)].date.nunique())}
    write_json(OUT / "c3_fed_summary.json", out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
