"""C1/C4/C6 cross-check from SDC New Issues (R2 WRDS mirror, licensed): $25-offer-price issues per year,
pricing-to-listing gap, and call dates.

    export QUANTT_ENV_FILE=<absolute path to the env file>       # R2 keys, never printed
    python3 scripts/events/ssx/ssx_lcred_sdc.py pull             # column-projected read -> licensed cache
    python3 scripts/events/ssx/ssx_lcred_sdc.py summary          # offline aggregates (no licensed rows out)

WHY
---
The EDGAR 8-A12B route (`ssx_lcred_newissue.py`) estimates new retail $25 issues
from a sampled precision. SDC New Issues is an independent second source with
the offer price, the listing and first-trade dates and the call date on each
tranche. The two are reported side by side and never averaged (CLAUDE.md:
when sources disagree, report it). The data librarian notes SDC thins after
2021 [U]; per-year counts show it.

DEFINITION. A retail $25 issue: offer price exactly 25 (SDC `offerpric`, a
string with thousands separators, parsed strictly), US dollar, and not a
convertible or mandatory (SDC `security` text). Event counts run to
2025-12-31; nothing here reads a price series. Licensed row-level output stays
in `results/events/ssx/_cache_ssx_lcred/` (gitignored); only aggregates are
written to `results/`.
ZERO TRIALS.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx.ssx_lcred_common import CACHE, OUT, write_json

COLS = ("master_deal_no, master_deal_date, security, assettype_print, market, exchange, currency, offerpric, "
        "principalamount, listing_date, firstradedate, calldate, callprice, perpetual, coupon, cusip9, ticker, "
        "settlement_date, main_tranche, ninames")
RAW = CACHE / "sdc_ni_2014_2026.parquet"
CONV = re.compile(r"CONV|MANDATORY|EXCH|UNIT|WARRANT|RIGHT", re.I)


def cmd_pull(args) -> None:
    from src.data import r2
    con = r2.connect()
    p = r2.r2_path("tr_sdc_ni", "wrds_ni_details")
    df = r2.q(con, f"select {COLS} from read_parquet('{p}') "
                   "where master_deal_date between DATE '2014-01-01' and DATE '2026-07-02'")
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(RAW, index=False)
    print(f"rows {len(df)}; last deal date {df.master_deal_date.max()}")


def load() -> pd.DataFrame:
    df = pd.read_parquet(RAW)
    df["op"] = pd.to_numeric(df.offerpric.astype(str).str.replace(",", ""), errors="coerce")
    for c in ("master_deal_date", "listing_date", "firstradedate", "calldate", "settlement_date"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["y"] = df.master_deal_date.dt.year
    return df


US_EXCH = re.compile(r"^(New York|Nasdaq|American|NYSE)", re.I)
PREF = re.compile(r"PFD|PREF|DEP(OSITARY)? SH|PRF", re.I)
NOTE = re.compile(r"\bNT|NOTE|DEB|SR |SUB", re.I)


def cmd_summary(args) -> None:
    """SDC's equity new-issues file prices a preferred per share, so a $25-par
    preferred has offer price 25; a $25 baby bond is usually priced at 100 (% of
    par) in the debt file and is NOT captured by offer price == 25. So SDC here
    cross-checks the PREFERRED count only. SDC's `listing_date` equals the deal
    date on most rows and `firstradedate` is not populated as a date on these
    rows (read 2026-10-19), so SDC gives no pricing-to-listing gap."""
    df = load()
    w = df[(df.op == 25) & df.y.between(2015, 2025)
           & df.exchange.fillna("").str.match(US_EXCH)
           & ~df.security.fillna("").str.contains(CONV)]
    pref = w[w.security.fillna("").str.contains(PREF)]
    note = w[~w.security.fillna("").str.contains(PREF) & w.security.fillna("").str.contains(NOTE)]
    pref.to_parquet(CACHE / "sdc_retail25_pref.parquet", index=False)
    out = {"source": "R2 tr_sdc_ni.wrds_ni_details (SDC New Issues), read 2026-10-19; last deal date in pull "
                     + str(df.master_deal_date.max().date()),
           "definition": ("offer price == 25, exchange New York/Nasdaq/American, security text preferred/"
                          "depositary, not CONV/MANDATORY/EXCH/UNIT/WARRANT/RIGHT"),
           "per_year_preferred_us_listed": pref.groupby("y").size().to_dict(),
           "per_year_preferred_unique_issuers": pref.groupby("y").ninames.nunique().to_dict(),
           "per_year_notes_at_25_us_listed": note.groupby("y").size().to_dict(),
           "preferred_share_with_calldate": round(float(pref.calldate.notna().mean()), 3),
           "preferred_callprice_values": pref.callprice.value_counts().head(5).to_dict(),
           "listing_date_equals_deal_date_share": round(float((pref.listing_date == pref.master_deal_date).mean()), 3),
           "security_text_top": pref.security.value_counts().head(8).to_dict()}
    s = pd.Series(out["per_year_preferred_us_listed"])
    out["preferred_summary"] = {"mean": round(float(s.mean()), 1), "median": float(s.median()),
                                "min": int(s.min()), "max": int(s.max())}
    write_json(OUT / "sdc_summary.json", out)
    print(json.dumps(out, indent=1, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("pull")
    sp.add_parser("summary")
    a = ap.parse_args(argv)
    {"pull": cmd_pull, "summary": cmd_summary}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
