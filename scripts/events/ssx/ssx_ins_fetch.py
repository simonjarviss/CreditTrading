"""Fetch and extract the SEC Insider Transactions Data Sets (Forms 3/4/5), zero trials.

    export QUANTT_ENV_FILE=/abs/path/config/.env      # SEC_USER_AGENT; never printed
    python3 scripts/events/ssx/ssx_ins_fetch.py fetch --start 2006Q1 --end 2025Q4 [--max-live 120]
    python3 scripts/events/ssx/ssx_ins_fetch.py extract --start 2006Q1 --end 2025Q4 [--offline]

WHY THIS EXISTS
---------------
The SS-desk expansion (team lead, 2026-10-19; seat `ssx_ins`) asks for a census
of open-market insider purchases (Form 4, transaction code P) across US
equities (idea D1) and in closed-end funds and BDCs (idea A2). Until now the
desk only knew which CIKs had FILED a Form 3/4 (the EDGAR master index, used by
`scripts/data/fetch_edgar_events.py::fund_set`); it never read what was in
them. The SEC publishes the XML part of every Form 3/4/5 since January 2006 as
flattened quarterly tab-separated tables (the "Insider Transactions Data
Sets"). This script is the fetcher and source note for that new source.

SOURCE (verified 2026-10-19 through `scripts/data/edgar_client.py`)
------------------------------------------------------------------
* Page: https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets
  ("January 2006 - September 2026"; 83 quarterly ZIP links on 2026-10-19).
* ZIPs 2006Q1..2026Q1: https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{y}q{q}_form345.zip
  (2026Q2 and 2026Q3 sit under /files/datastandardsinnovation/...; not used.)
* Readme (table definitions, transaction-code list): https://www.sec.gov/files/insider_transactions_readme.pdf
* Quarter assignment is by FILING date: "Data contained in documents filed
  after 5:30PM Eastern on the last business day of a quarter will be included
  in the subsequent quarterly posting" (page and readme, 2026-10-19).

WHAT IS KEPT (row level, public EDGAR data, but large: gitignored cache)
-----------------------------------------------------------------------
`results/events/ssx/_cache_ssx_ins/form345/{y}q{q}_ptrans.parquet`:
    every NONDERIV_TRANS row with TRANS_CODE == 'P', joined to its SUBMISSION
    (filing date, document type, issuer CIK/name/symbol, period of report) and
    to its REPORTINGOWNER rows (one row per reporting owner: a joint filing by
    two owners is two rows; the census counts DISTINCT owner CIKs).
`results/events/ssx/_cache_ssx_ins/form345/{y}q{q}_issuers.parquet`:
    one row per (issuer CIK, document type) with filing counts, all codes, so
    the fund-issuer set can be cross-checked without re-reading the ZIP.
`results/events/ssx/ssx_ins/form345_extract_by_quarter.json`:
    per quarter: submissions, NONDERIV_TRANS rows, code-P rows, unparsed trade
    dates, orphan rows, and row counts by DOCUMENT_TYPE|TRANS_CODE (sanity table).

UNTRUSTED INPUT: the ZIPs are read in memory with `zipfile`; nothing is
extracted to disk and no member is executed or imported. A member whose name
is not one of the expected tables is ignored and listed.

NO SILENT FALLBACKS: a missing table in a ZIP, a missing column, an
unparseable date in a field the census keys on, or a live-request count over
`--max-live` raises naming what was wrong. Dates that fail to parse are
COUNTED and reported (the data set is "as filed"), never coerced to a value.

ZERO TRIALS: this script reads filings only. It touches no price.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

PAGE_URL = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
ZIP_URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{y}q{q}_form345.zip"
README_URL = "https://www.sec.gov/files/insider_transactions_readme.pdf"
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_ins" / "form345"
FIRST_QUARTER = (2006, 1)   # page: "January 2006 - ..."; readme §2 "from January 2006"

SUB_COLS = ["ACCESSION_NUMBER", "FILING_DATE", "PERIOD_OF_REPORT", "DOCUMENT_TYPE",
            "ISSUERCIK", "ISSUERNAME", "ISSUERTRADINGSYMBOL"]
OWN_COLS = ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNERNAME", "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE",
            "RPTOWNER_TXT"]
TR_COLS = ["ACCESSION_NUMBER", "NONDERIV_TRANS_SK", "SECURITY_TITLE", "TRANS_DATE", "DEEMED_EXECUTION_DATE",
           "TRANS_FORM_TYPE", "TRANS_CODE", "EQUITY_SWAP_INVOLVED", "TRANS_TIMELINESS", "TRANS_SHARES",
           "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD", "SHRS_OWND_FOLWNG_TRANS",
           "DIRECT_INDIRECT_OWNERSHIP", "NATURE_OF_OWNERSHIP"]
TABLES = {"SUBMISSION": SUB_COLS, "REPORTINGOWNER": OWN_COLS, "NONDERIV_TRANS": TR_COLS}


def quarters(start: str, end: str) -> list[tuple[int, int]]:
    def p(s):
        y, q = s.upper().split("Q")
        return int(y), int(q)
    (y0, q0), (y1, q1) = p(start), p(end)
    if (y0, q0) < FIRST_QUARTER:
        raise ValueError(f"{start} is before the first published quarter {FIRST_QUARTER}")
    out, y, q = [], y0, q0
    while (y, q) <= (y1, q1):
        out.append((y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def _client(offline: bool):
    from scripts.data.edgar_client import EdgarClient, RateLimiter
    # The brief's limit: 1.5 s between live requests (shared SEC budget across ten agents).
    return EdgarClient(limiter=RateLimiter(min_interval=1.5), offline=offline)


def fetch(start: str, end: str, max_live: int) -> dict:
    c = _client(offline=False)
    log = []
    for y, q in quarters(start, end):
        before = c.n_requests
        if c.n_requests >= max_live:
            raise RuntimeError(f"live-request cap {max_live} reached before {y}Q{q}; raise --max-live deliberately")
        body = c.get(ZIP_URL.format(y=y, q=q))     # closed quarter: immutable, cached once
        log.append({"quarter": f"{y}Q{q}", "bytes": len(body), "live": c.n_requests - before})
        print(log[-1], flush=True)
    rec = {"ran_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "live_requests": c.n_requests, "cache_hits": c.n_cache_hits, "quarters": log}
    return rec


def read_table(zf: zipfile.ZipFile, table: str, cols: list[str], label: str) -> pd.DataFrame:
    names = {Path(n).name.upper(): n for n in zf.namelist()}
    key = f"{table}.TSV"
    if key not in names:
        raise KeyError(f"{label}: ZIP has no {key} (members: {sorted(names)})")
    raw = zf.read(names[key])
    df = pd.read_csv(io.BytesIO(raw), sep="\t", dtype=str, keep_default_na=False, na_values=[""],
                     quoting=3, encoding="utf-8", encoding_errors="replace", on_bad_lines="error")
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"{label} {table}: columns {missing} absent (have {list(df.columns)})")
    return df[cols]


def _date(s: pd.Series) -> pd.Series:
    """DD-MON-YYYY (readme §5) -> Timestamp; unparseable stays NaT and is COUNTED by the caller."""
    return pd.to_datetime(s, format="%d-%b-%Y", errors="coerce")


def extract(start: str, end: str, offline: bool) -> dict:
    c = _client(offline=offline)
    CACHE.mkdir(parents=True, exist_ok=True)
    summary = {}
    for y, q in quarters(start, end):
        label = f"{y}Q{q}"
        out_p = CACHE / f"{y}q{q}_ptrans.parquet"
        body = c.get(ZIP_URL.format(y=y, q=q))
        zf = zipfile.ZipFile(io.BytesIO(body))
        expected = {f"{t}.TSV" for t in ("SUBMISSION", "REPORTINGOWNER", "NONDERIV_TRANS", "NONDERIV_HOLDING",
                                          "DERIV_TRANS", "DERIV_HOLDING", "FOOTNOTES", "OWNER_SIGNATURE")}
        other = [n for n in zf.namelist() if Path(n).name.upper() not in expected]
        sub = read_table(zf, "SUBMISSION", SUB_COLS, label)
        own = read_table(zf, "REPORTINGOWNER", OWN_COLS, label)
        tr = read_table(zf, "NONDERIV_TRANS", TR_COLS, label)
        if sub.empty or tr.empty:
            raise RuntimeError(f"{label}: empty SUBMISSION or NONDERIV_TRANS")
        if sub.ACCESSION_NUMBER.duplicated().any():
            raise RuntimeError(f"{label}: SUBMISSION has duplicate accession numbers (primary key)")
        # Sanity table: rows by code x document type, all codes.
        codes = (tr.merge(sub[["ACCESSION_NUMBER", "DOCUMENT_TYPE"]], on="ACCESSION_NUMBER", how="left")
                 .groupby(["DOCUMENT_TYPE", "TRANS_CODE"], dropna=False).size())
        codes_d = {f"{k[0]}|{k[1]}": int(v) for k, v in codes.items()}
        orphan_tr = int((~tr.ACCESSION_NUMBER.isin(sub.ACCESSION_NUMBER)).sum())
        # Issuer table (all filings), for the fund-issuer cross-check.
        iss = sub.groupby(["ISSUERCIK", "DOCUMENT_TYPE"]).agg(
            filings=("ACCESSION_NUMBER", "size"), issuername=("ISSUERNAME", "last"),
            symbol=("ISSUERTRADINGSYMBOL", "last")).reset_index()
        iss.to_parquet(CACHE / f"{y}q{q}_issuers.parquet", index=False)
        p = tr[tr.TRANS_CODE == "P"].merge(sub, on="ACCESSION_NUMBER", how="left", validate="many_to_one")
        if p.FILING_DATE.isna().any():
            raise RuntimeError(f"{label}: {int(p.FILING_DATE.isna().sum())} code-P rows have no SUBMISSION row")
        p = p.merge(own, on="ACCESSION_NUMBER", how="left", validate="many_to_many")
        for col in ("FILING_DATE", "PERIOD_OF_REPORT", "TRANS_DATE", "DEEMED_EXECUTION_DATE"):
            p[col] = _date(p[col])
        if p.FILING_DATE.isna().any():
            raise RuntimeError(f"{label}: unparseable FILING_DATE on a code-P row")
        for col in ("TRANS_SHARES", "TRANS_PRICEPERSHARE", "SHRS_OWND_FOLWNG_TRANS"):
            p[col] = pd.to_numeric(p[col], errors="coerce")
        p["quarter"] = label
        p.to_parquet(out_p, index=False)
        summary[label] = {"submissions": int(len(sub)), "nonderiv_rows": int(len(tr)),
                          "p_rows_x_owner": int(len(p)), "p_trans_rows": int(p.NONDERIV_TRANS_SK.nunique()),
                          "p_trans_date_unparsed": int(p.TRANS_DATE.isna().sum()),
                          "orphan_nonderiv_rows": orphan_tr, "other_members": other, "codes": codes_d}
        print(label, {k: v for k, v in summary[label].items() if k != "codes"}, flush=True)
    return {"ran_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "live_requests": c.n_requests, "cache_hits": c.n_cache_hits, "quarters": summary}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("fetch", "extract"))
    ap.add_argument("--start", default="2006Q1")
    ap.add_argument("--end", default="2025Q4")
    ap.add_argument("--max-live", type=int, default=120)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    out = REPO / "results" / "events" / "ssx" / "ssx_ins"
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "fetch_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    if a.part == "fetch":
        meta[f"fetch_{a.start}_{a.end}"] = fetch(a.start, a.end, a.max_live)
    else:
        rec = extract(a.start, a.end, a.offline)
        meta[f"extract_{a.start}_{a.end}"] = {k: v for k, v in rec.items() if k != "quarters"}
        (out / "form345_extract_by_quarter.json").write_text(json.dumps(rec["quarters"], indent=1) + "\n")
    meta_path.write_text(json.dumps(meta, indent=1, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
