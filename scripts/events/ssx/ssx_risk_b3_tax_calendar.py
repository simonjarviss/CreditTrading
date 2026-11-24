"""B3: dated tax-policy episodes touching the muni exemption or state taxes,
2008-2025, as a RISK CALENDAR for the live CEF book. Zero trials.

WHY
---
A threat to the federal exemption (or a change to a state's taxes) re-prices
every muni fund at once: it is a level shift in M4/M5 fair value, not a
dislocation, and the discount z-score would fade it. The expected verdict is
D7 as a signal (a handful of episodes in 18 years) and a calendar only. This
script makes the calendar reproducible: federal bill milestones are parsed from
GovInfo's BILLSTATUS XML (primary, keyless, U.S. government work), and the
non-bill episodes are declared rows, each with its source and a label.

Reproduce:
    python3 scripts/events/ssx/ssx_risk_b3_tax_calendar.py     # fetches 5 XML files once, then cached
Output: results/events/ssx/ssx_risk/b3_tax_episodes.csv
"""
from __future__ import annotations

import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_risk" / "govinfo"
OUT = REPO / "results" / "events" / "ssx" / "ssx_risk"
BULK = "https://www.govinfo.gov/bulkdata/BILLSTATUS/{c}/{t}/BILLSTATUS-{c}{t}{n}.xml"

# (congress, type, number) -> (episode, why it touches munis; the muni content is
# from the bill's own record only where marked [V], else from secondary reading [S])
BILLS = {
    (112, "s", 1549): ("American Jobs Act of 2011", "28% cap on the value of exclusions incl. muni interest [S]"),
    (112, "hr", 8): ("American Taxpayer Relief Act of 2012", "top rate to 39.6%: raises the exemption's value [S]"),
    (113, "hr", 1): ("Tax Reform Act of 2014 (Camp)", "surtax reaching muni interest of high earners [S]"),
    (115, "hr", 1): ("TCJA 2017", "advance-refunding repeal for bonds issued after 2017-12-31; SALT cap [S]"),
    (119, "hr", 1): ("Reconciliation 2025 (P.L. 119-21)", "exemption debated early 2025 and kept [S]; SALT cap raised [S]"),
}
KEEP = ("Introduced in", "Passed/agreed to in House", "Passed/agreed to in Senate", "Conference report filed",
        "Became Public Law", "Signed by President")

DECLARED = [  # non-bill episodes: date, episode, source, label
    ("2008-05-19", "Dept. of Revenue of Kentucky v. Davis decided: states may tax out-of-state munis and exempt their own",
     "https://www.law.cornell.edu/supct/html/06-666.ZS.html (read 2026-10-19)", "V"),
    ("2010-12-01", "Simpson-Bowles commission final report (proposed taxing new muni interest)", "not fetched", "U"),
    ("2014-02-26", "Camp discussion draft released (before the 2014-12-10 bill)", "not fetched", "U"),
    ("2025-01", "Ways and Means revenue-options list reportedly includes repealing the exemption", "press reports, not fetched", "U"),
]


def bill_rows() -> list[dict]:
    rows = []
    for (c, t, n), (ep, why) in BILLS.items():
        url = BULK.format(c=c, t=t, n=n)
        path = CACHE / f"BILLSTATUS-{c}{t}{n}.xml"
        if not path.exists():
            import requests
            time.sleep(1.0)
            r = requests.get(url, headers={"User-Agent": "QUANTT research"}, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"GET {url} -> HTTP {r.status_code}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
        b = ET.parse(path).getroot().find(".//bill")
        if b is None:
            raise ValueError(f"{path.name}: no <bill> element")
        seen = set()
        for a in b.findall("./actions/item"):
            d, txt = a.findtext("actionDate"), (a.findtext("text") or "")
            k = next((k for k in KEEP if txt.startswith(k)), None)
            if k and (d, k) not in seen:
                seen.add((d, k))
                rows.append({"date": d, "episode": ep, "milestone": k, "muni_relevance": why,
                             "source": url, "label": "V (date); relevance as marked"})
    return rows


def main() -> int:
    rows = bill_rows()
    rows += [{"date": d, "episode": e, "milestone": "event", "muni_relevance": e, "source": s, "label": l}
             for d, e, s, l in DECLARED]
    df = pd.DataFrame(rows).sort_values("date")
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "b3_tax_episodes.csv", index=False)
    eps = df.groupby("episode").date.min().sort_values()
    print(df[["date", "episode", "milestone", "label"]].to_string(index=False))
    print(f"\ndistinct episodes 2008-2025: {eps.size}  (milestone rows: {len(df)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
