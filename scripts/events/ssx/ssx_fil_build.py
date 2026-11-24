"""Build the SEC-filings seat's working tables once: index rows, submissions rows, links, ADV panel, borrow flags.

    export QUANTT_ENV_FILE=/abs/path/config/.env   # R2 + Alpaca keys; never printed
    python3 scripts/events/ssx/ssx_fil_build.py index
    python3 scripts/events/ssx/ssx_fil_build.py subs --bulk-cache <an EDGAR-client cache root holding submissions.zip>
    python3 scripts/events/ssx/ssx_fil_build.py r2          # CCM link, dsenames, dollar-volume panel (pre-2023)
    python3 scripts/events/ssx/ssx_fil_build.py alpaca      # today's flags, read-only GETs

ZERO TRIALS. Counts, links and pre-event liquidity only (`ssx_fil_common`).

WHY A SEPARATE BUILD STEP
-------------------------
The four censuses read the same ~1 million filings. Parsing the 1.5 GB bulk
archive once, and pulling the CRSP dollar-volume panel once, keeps each census
script a few seconds long and makes them re-runnable offline. Every table
written here is a cache (gitignored), not a result; results are the aggregates
the census scripts write to `results/events/ssx/ssx_fil/`.

FORMS KEPT, AND WHY
-------------------
* NT 10-K, NT 10-Q (and /A): D4, Rule 12b-25 notices.
* 10-K, 10-Q, 10-KT (and /A): D9 timing and D2 BDC reports. `reportDate` is the
  period end; it lives in the submissions archive, not the master index.
* 8-K (and /A): D6 items 4.01/4.02/5.02, D9/D2 item 2.02, D7 item 1.03.
* N-54A / N-54C: the BDC election and its withdrawal. Read over each CIK's
  whole EDGAR history (from 1996), because a BDC that elected before 2008
  never files N-54A again and the 2008+ index alone would miss it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx import ssx_fil_common as C  # noqa: E402

NT_FORMS = {"NT 10-K", "NT 10-Q", "NT 10-K/A", "NT 10-Q/A"}
PERIODIC = {"10-K", "10-Q", "10-KT", "10-K/A", "10-Q/A", "10-KT/A"}
EIGHTK = {"8-K", "8-K/A"}
BDC_FORMS = {"N-54A", "N-54C"}
INDEX_FORMS = NT_FORMS | PERIODIC | EIGHTK | BDC_FORMS


def build_index() -> dict:
    t0 = time.time()
    idx = C.master_index(INDEX_FORMS, C.COUNT_START, C.COUNT_END)
    C.CACHE.mkdir(parents=True, exist_ok=True)
    idx.to_parquet(C.CACHE / "index_rows.parquet")
    s = {"rows": int(len(idx)), "accessions": int(idx["accession"].nunique()), "ciks": int(idx["cik"].nunique()),
         "first": str(idx["date_filed"].min().date()), "last": str(idx["date_filed"].max().date()),
         "seconds": round(time.time() - t0, 1)}
    print(s)
    return s


def build_subs(bulk_cache: Path | None, allow_live: bool) -> dict:
    t0 = time.time()
    idx = pd.read_parquet(C.CACHE / "index_rows.parquet")
    ciks = sorted(idx["cik"].unique().tolist())
    z = C.bulk_zip(C.SUBMISSIONS_ZIP_URL, bulk_cache, allow_live)
    snap = C.bulk_zip_date(z)
    # Every form we count, from 2007 (D9 needs the prior year), plus the BDC
    # election forms over the whole history.
    rows, meta = C.submissions_rows(z, ciks, INDEX_FORMS, first_date="1996-01-01")
    rows = rows[(rows["filingDate"] >= "2007-01-01") | rows["form"].isin(BDC_FORMS)]
    rows.to_parquet(C.CACHE / "subs_rows.parquet")
    meta.to_parquet(C.CACHE / "subs_meta.parquet")
    s = {"archive_snapshot_date": snap, "ciks_requested": len(ciks),
         "ciks_in_archive": int(meta["in_archive"].sum()), "rows": int(len(rows)),
         "seconds": round(time.time() - t0, 1)}
    C.write_json(C.OUT / "build_subs_meta.json", s)
    print(s)
    return s


def build_r2() -> dict:
    t0 = time.time()
    links = C.cik_permno_links()
    names = C.crsp_names()
    dv = C.dv_panel()
    s = {"ccm_links": int(len(links)), "ccm_ciks": int(links["cik"].nunique()),
         "dsenames_rows": int(len(names)), "dv_rows": int(len(dv)), "dv_last": str(dv["date"].max().date()),
         "seconds": round(time.time() - t0, 1)}
    C.write_json(C.OUT / "build_r2_meta.json", s)
    print(s)
    return s


def build_alpaca() -> dict:
    a, clock = C.alpaca_assets(refresh=True)
    s = {"clock": clock, "active_assets": int(len(a)), "shortable": int(a["shortable"].sum()),
         "etb": int((a["easy_to_borrow"] == True).sum())}  # noqa: E712  (None is not ETB)
    C.write_json(C.OUT / f"build_alpaca_meta_{dt.date.today().isoformat()}.json", s)
    print(s)
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("index", "subs", "r2", "alpaca", "all"))
    ap.add_argument("--bulk-cache", type=Path, default=None)
    ap.add_argument("--allow-live-bulk", action="store_true")
    a = ap.parse_args(argv)
    if a.part in ("index", "all"):
        build_index()
    if a.part in ("subs", "all"):
        build_subs(a.bulk_cache, a.allow_live_bulk)
    if a.part in ("r2", "all"):
        build_r2()
    if a.part in ("alpaca", "all"):
        build_alpaca()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
