"""B1(b): muni distress-event notice counts per year, read from the MSRB's own
annual Fact Books (event disclosures by type, "By Number of Documents").

WHY THE SCRIPT DOES NOT DOWNLOAD
--------------------------------
The MSRB's website terms (emma.msrb.org/tradedata, "Last Updated: January 1,
2026", read 2026-10-19) cover msrb.org and EMMA and forbid "any data mining,
crawling, 'scraping', robot or similar automated or data gathering or
extraction method ... or otherwise systematically download or store Content",
while allowing a user to "view, print and make copies of Content". So the five
Fact Book PDFs were saved once each on 2026-10-19 -- five single curl requests
made by the research agent, the equivalent of a browser save, not a crawler --
into results/events/ssx/_cache_ssx_risk/msrb_factbook/, and this script only
PARSES those local copies. It makes no network request. Whether even that
single-copy save sits inside "view, print and make copies" is for the team lead
(cards, B1). Source URLs:
  2020 https://www.msrb.org/sites/default/files/MSRB-2020-Fact-Book.pdf
  2021 https://www.msrb.org/sites/default/files/MSRB-2021-Fact-Book.pdf
  2022 https://www.msrb.org/sites/default/files/2023-03/MSRB-2022-Fact-Book.pdf
  2023 https://www.msrb.org/sites/default/files/2024-02/MSRB-2023-Fact-Book.pdf
  2024 https://www.msrb.org/sites/default/files/2025-02/MSRB-2024-FactBook_1.pdf

Each book reports two years; overlapping years are checked to agree and the
script RAISES if two books disagree (never averages). Counts are DOCUMENTS
filed on EMMA, not distinct issuers or CUSIPs.

Reproduce:  python3 scripts/events/ssx/ssx_risk_b1_msrb_factbook.py   (needs pdftotext)
Output: results/events/ssx/ssx_risk/b1_msrb_event_notices.csv
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "results" / "events" / "ssx" / "_cache_ssx_risk" / "msrb_factbook"
OUT = REPO / "results" / "events" / "ssx" / "ssx_risk"
ROWS = ("P&I PAYMENT DELINQUENCY", "NON-PAYMENT RELATED DEFAULT", "UNSCHEDULED DRAW ON DEBT SERVICE RESERVE",
        "UNSCHEDULED DRAW ON CREDIT ENHANCEMENT", "BANKRUPTCY, INSOLVENCY, RECEIVERSHIP",
        "FINANCIAL OBLIGATION - EVENT REFLECTING FINANCIAL DIFFICULTIES")


def parse(pdf: Path) -> pd.DataFrame:
    txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    i = txt.find("Other Event Disclosures")
    if i < 0:
        raise ValueError(f"{pdf.name}: no 'Other Event Disclosures' table")
    block = txt[i:i + 8000]
    yrs = re.search(r"By Number of Documents\s+(\d{4})\s+(\d{4})", block)
    if not yrs:
        raise ValueError(f"{pdf.name}: no year header in the event table")
    y0, y1 = int(yrs.group(1)), int(yrs.group(2))
    out = []
    for r in ROWS:
        m = re.search(re.escape(r) + r"\s+([\d,]+)\s+([\d,]+)", block)
        if not m:
            raise ValueError(f"{pdf.name}: row {r!r} not found")
        out += [{"event": r, "year": y0, "documents": int(m.group(1).replace(",", "")), "book": pdf.name},
                {"event": r, "year": y1, "documents": int(m.group(2).replace(",", "")), "book": pdf.name}]
    return pd.DataFrame(out)


def main() -> int:
    pdfs = sorted(SRC.glob("MSRB-20*-Fact-Book.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"no Fact Book PDFs in {SRC} (save them by hand; see docstring)")
    df = pd.concat([parse(p) for p in pdfs], ignore_index=True)
    chk = df.groupby(["event", "year"]).documents.nunique()
    bad = chk[chk > 1]
    if len(bad):
        raise ValueError(f"two Fact Books disagree on: {bad.index.tolist()}")
    wide = df.drop_duplicates(["event", "year"]).pivot(index="event", columns="year", values="documents")
    OUT.mkdir(parents=True, exist_ok=True)
    wide.to_csv(OUT / "b1_msrb_event_notices.csv")
    print(wide.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
