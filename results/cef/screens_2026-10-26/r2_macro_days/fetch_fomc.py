"""Fetch the Federal Reserve's own FOMC meeting pages, 2005-2022, into raw/fed/.

    python3 -I fetch_fomc.py

WHY: data/events.parquet's FOMC rows come from academic event-study spines
(Kuttner, USMPD, Bauer-Swanson) copied from an archive; the Fed's pages are the
primary record of when each statement was released and which actions were
unscheduled. This screen uses the Fed pages as the authority and reports every
disagreement with the repo panel (CLAUDE.md data rules: two sources, never
averaged, never picked silently).

Pages: fomchistorical{YEAR}.htm for 2005-2020 (the Fed's historical-materials
year pages) and fomccalendars.htm (the current calendar page, which carries the
most recent years). Each file's URL, UTC fetch time, size and sha256 go to
raw/fed/FETCH_LOG.csv. Nothing is written outside this folder.
"""
from __future__ import annotations

import csv
import hashlib
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "raw" / "fed"
UA = "Mozilla/5.0 (QUANTT research screen; python urllib)"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status != 200:
            raise RuntimeError(f"{url}: HTTP {r.status}")
        return r.read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    urls = [f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm" for y in range(2005, 2021)]
    urls.append("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    log = OUT / "FETCH_LOG.csv"
    rows = []
    for u in urls:
        b = get(u)
        name = u.rsplit("/", 1)[1]
        (OUT / name).write_bytes(b)
        rows.append(dict(url=u, file=f"raw/fed/{name}", fetched_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         bytes=len(b), sha256=hashlib.sha256(b).hexdigest()))
        print(rows[-1]["fetched_utc"], len(b), u)
        time.sleep(0.5)
    with log.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
