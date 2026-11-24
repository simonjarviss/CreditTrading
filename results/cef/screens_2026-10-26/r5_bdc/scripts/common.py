"""Shared loaders for the R5 BDC screen (zero trials, report only).

WHY ONE MODULE: the NAV table (Compustat ceqq/cshoq, known on rdq) feeds both the
validation gate and the IC run; two copies of the exclusion rules would drift.

Inputs (all read-only, licensed, gitignored; no value is copied into a tracked file):
  R2 pull 2026-10-27 (team lead): .claude/worktrees/simon/results/events/_cache_r7_r2_pull/bdc/
  D2 cache (ssx_fil): d2_bdc_reports.parquet, d2_bdc_navps_facts.parquet
  CRSP dsf cache: research-ss-expansion/results/events/_cache_crsp/dsf_44015b5199.parquet
Every frame that reaches a statistic is asserted to end <= 2022-12-30 (sealed holdout).
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

ROOT = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/.claude/worktrees")
PULL = ROOT / "simon/results/events/_cache_r7_r2_pull/bdc"
FIL = ROOT / "research-ss-expansion/results/events/ssx/_cache_ssx_fil"
DSF = ROOT / "research-ss-expansion/results/events/_cache_crsp/dsf_44015b5199.parquet"
FIT_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-01")


def assert_fit(*objs):
    """Nothing that reaches a statistic may carry a 2023+ date."""
    for o in objs:
        if isinstance(o, (pd.DataFrame, pd.Series)):
            idx = o.index
        else:
            idx = pd.DatetimeIndex(o)
        if len(idx) and pd.Timestamp(idx.max()) >= HOLDOUT_START:
            raise AssertionError(f"holdout leak: a frame reaches {idx.max()}")


def entities() -> pd.DataFrame:
    e = pd.read_parquet(PULL / "bdc_entities.parquet")
    e["cik"] = e["cik"].astype(int)
    e["permno"] = e["permno"].astype(int)
    if e.gvkey.duplicated().any() or e.permno.duplicated().any():
        raise ValueError("bdc_entities: a gvkey or permno maps to two entities")
    return e


def compustat_nav() -> tuple[pd.DataFrame, dict]:
    """Compustat NAV per share = ceqq / cshoq, one row per (gvkey, datadate).

    Exclusions are COUNTED and returned, never imputed (no fillna, no default):
    null rdq (unusable: the knowledge date is unknown), null ceqq or cshoq, cshoq <= 0,
    and duplicated (gvkey, datadate) whose values disagree (both dropped)."""
    f = pd.read_parquet(PULL / "bdc_fundq.parquet")
    counts = {"rows_in": int(len(f))}
    counts["null_rdq"] = int(f.rdq.isna().sum())
    f = f[f.rdq.notna()]
    counts["null_ceqq_or_cshoq_after_rdq"] = int((f.ceqq.isna() | f.cshoq.isna()).sum())
    f = f[f.ceqq.notna() & f.cshoq.notna()]
    counts["cshoq_nonpositive"] = int((f.cshoq <= 0).sum())
    f = f[f.cshoq > 0].copy()
    key = ["gvkey", "datadate"]
    dup = f[f.duplicated(key, keep=False)]
    agree = dup.groupby(key)[["rdq", "ceqq", "cshoq"]].nunique().le(1).all(axis=1)
    bad_keys = agree[~agree].index
    counts["dup_keys_collapsed"] = int(agree.sum())
    counts["dup_keys_disagree_dropped"] = int(len(bad_keys))
    if len(bad_keys):
        f = f.set_index(key).drop(index=bad_keys).reset_index()
    f = f.drop_duplicates(key)
    f["datadate"] = pd.to_datetime(f["datadate"]).astype("datetime64[ns]")
    f["rdq"] = pd.to_datetime(f["rdq"]).astype("datetime64[ns]")
    if not (f.rdq > f.datadate).all():
        n = int((f.rdq <= f.datadate).sum())
        raise AssertionError(f"{n} rows have rdq on or before the quarter end: the knowledge date is not after the period")
    f["nav"] = f.ceqq / f.cshoq            # $m / m shares = $ per share
    e = entities()
    f = f.merge(e[["gvkey", "cik", "permno"]], on="gvkey", how="left", validate="many_to_one",
                suffixes=("_comp", ""))
    if f.permno.isna().any():
        raise ValueError("a fundq gvkey has no entity row")
    counts["rows_usable"] = int(len(f))
    counts["gvkeys_usable"] = int(f.gvkey.nunique())
    return f[["gvkey", "cik", "permno", "datadate", "rdq", "ceqq", "cshoq", "nav", "tic"]], counts


def xbrl_navps() -> pd.DataFrame:
    """XBRL NetAssetValuePerShare facts (D2 cache), earliest-filed value per (cik, end)."""
    x = pd.read_parquet(FIL / "d2_bdc_navps_facts.parquet")
    x["end"] = pd.to_datetime(x["end"])
    x["filed"] = pd.to_datetime(x["filed"])
    x = x.sort_values("filed").drop_duplicates(["cik", "end"], keep="first")
    return x


def reports() -> pd.DataFrame:
    r = pd.read_parquet(FIL / "d2_bdc_reports.parquet")
    r["filingDate"] = pd.to_datetime(r["filingDate"]).astype("datetime64[ns]")
    r["reportDate"] = pd.to_datetime(r["reportDate"]).astype("datetime64[ns]")
    r["accepted"] = pd.to_datetime(r["acceptanceDateTime"], utc=True).dt.tz_convert("America/New_York")
    return r


def crsp(permnos, start="2009-01-01") -> pd.DataFrame:
    """CRSP daily rows for `permnos`, start..2022-12-30 only (filtered in the scan)."""
    sch = pq.ParquetFile(DSF).schema_arrow
    ty = sch.field("date").type
    if not (pa.types.is_timestamp(ty) and ty.tz is None):
        raise TypeError(f"unexpected CRSP date type {ty}")
    lo = pa.scalar(pd.Timestamp(start).to_pydatetime(), type=ty)
    hi = pa.scalar(_dt.datetime(2022, 12, 30), type=ty)
    t = ds.dataset(DSF).to_table(
        columns=["permno", "date", "prc", "ret", "vol", "cfacpr"],
        filter=ds.field("permno").isin(list(map(int, permnos))) & (ds.field("date") >= lo) & (ds.field("date") <= hi),
    ).to_pandas()
    t["date"] = pd.to_datetime(t["date"]).astype("datetime64[ns]")
    assert_fit(t.set_index("date"))
    if t.duplicated(["permno", "date"]).any():
        raise ValueError("CRSP cache holds duplicate (permno, date) rows")
    return t
