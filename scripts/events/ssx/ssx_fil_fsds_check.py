"""One quarter of the SEC Financial Statement Data Sets as an independent check on three census inputs.

    python3 scripts/events/ssx/ssx_fil_fsds_check.py            # offline once the ZIP is cached
    python3 scripts/events/ssx/ssx_fil_fsds_check.py --live     # one live request (about 104 MB)

ZERO TRIALS. Filing metadata and XBRL dimension labels only.

WHY
---
CLAUDE.md asks for a second method on anything that drives a decision. The
Financial Statement Data Sets (DERA, quarterly ZIPs) are a different SEC
product from the submissions archive the censuses use, so they check:
  1. D9's clock: FSDS `filed`/`period` against submissions `filingDate`/`reportDate`;
  2. the acceptance-time question: FSDS `accepted` against the submissions
     API's `acceptanceDateTime` (the header sample in D4 found the API off by
     plus or minus one UTC offset);
  3. D7's free link route: how many 10-Ks tag a revenue-concentration fact on a
     customer member in num.txt's `segments` column.
URL pattern verified through the EDGAR client on 2026-10-19:
https://www.sec.gov/files/dera/data/financial-statement-data-sets/{YYYY}q{N}.zip
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx import ssx_fil_common as C  # noqa: E402

URL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets/2022q1.zip"


def run(live: bool) -> dict:
    from scripts.data.edgar_client import cache_path
    E = C.BudgetedEdgar(offline=not live)
    E.get_bytes(URL, purpose="FSDS check")
    z = zipfile.ZipFile(cache_path(URL, C.SHARED_EDGAR_CACHE))
    sub = pd.read_csv(z.open("sub.txt"), sep="\t", dtype=str)
    num = pd.read_csv(z.open("num.txt"), sep="\t", dtype=str, usecols=["adsh", "tag", "segments"])
    s = pd.read_parquet(C.CACHE / "subs_rows.parquet", columns=["accessionNumber", "filingDate", "reportDate", "acceptanceDateTime"])
    s = s.drop_duplicates("accessionNumber")
    m = sub[sub["form"].isin(["10-Q", "10-K"])].merge(s, left_on="adsh", right_on="accessionNumber")
    fd = pd.to_datetime(m["filed"], format="%Y%m%d")
    pr = pd.to_datetime(m["period"], format="%Y%m%d")
    acc = pd.to_datetime(m["accepted"].str[:19])
    api = pd.to_datetime(m["acceptanceDateTime"].map(lambda v: C.api_as_et(v) if isinstance(v, str) else None))
    off = ((api - acc).dt.total_seconds() / 3600).round(1)
    seg = num[num["segments"].notna()]
    cust = seg[seg["segments"].str.contains("MajorCustomer", case=False) & seg["tag"].str.contains("Concentration|Revenue", case=False)]
    k10 = set(sub.loc[sub["form"] == "10-K", "adsh"])
    out = {"zip": URL, "periodic_rows_matched": int(len(m)),
           "filed_equal_share": round(float((fd == pd.to_datetime(m["filingDate"])).mean()), 4),
           "period_equal_share": round(float((pr == pd.to_datetime(m["reportDate"])).mean()), 4),
           "api_minus_fsds_accepted_hours": {str(k): int(v) for k, v in off.value_counts().items()},
           "tenk_filings": len(k10), "tenk_with_majorcustomer_member": int(cust.loc[cust["adsh"].isin(k10), "adsh"].nunique())}
    C.write_json(C.OUT / "fsds_2022q1_check.json", out)
    print(out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--live", action="store_true")
    run(ap.parse_args().live)
