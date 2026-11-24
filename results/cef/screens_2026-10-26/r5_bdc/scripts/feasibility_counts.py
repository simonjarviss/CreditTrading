"""R5 BDC feasibility counts (read-only, no network, fit window 2012-2022 only).

WHY: the screen needs, for >= 20 listed BDCs over >= 5 years of 2012-22, a NAV per
share that is point-in-time (value + the date it became public) plus daily prices.
This script measures each ingredient from what is already on this machine:

  A. the BDC report index (10-Q/10-K accession, filingDate) -- the knowledge dates;
  B. XBRL NetAssetValuePerShare facts (companyfacts, cached by ssx_fil D2) -- values;
     both point-in-time (filed <= 2022-12-31) and a relaxed, NOT point-in-time
     reading (any later filing that restates an old period's NAV);
  C. Compustat fundq rdq rows for the same firms (local cache has gvkey/datadate/rdq
     only: no ceqq/cshoq) -- to size what an R2 read of ceqq/cshoq would cover;
  D. CRSP daily prices (local licensed cache) -- rows with date <= 2022-12-30 only.

Every figure printed is computed now from these files; nothing is assumed.
"""
import json, datetime as _dt
from pathlib import Path
import pandas as pd, pyarrow as pa, pyarrow.parquet as pq, pyarrow.dataset as ds

WT = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/.claude/worktrees")
FIL = WT / "research-ss-expansion/results/events/ssx/_cache_ssx_fil"
DSF = WT / "research-ss-expansion/results/events/_cache_crsp/dsf_44015b5199.parquet"
FIT0, FIT1 = pd.Timestamp("2012-01-01"), pd.Timestamp("2022-12-30")
out = {}

# A. report index
r = pd.read_parquet(FIL / "d2_bdc_reports.parquet")
r["filingDate"] = pd.to_datetime(r["filingDate"]); r["reportDate"] = pd.to_datetime(r["reportDate"])
A = r[(r.listed == True) & (r.filingDate >= FIT0) & (r.filingDate <= FIT1)].copy()
assert A.filingDate.max() <= FIT1
per = A.groupby("cik").agg(n=("filingDate", "size"), first=("filingDate", "min"), last=("filingDate", "max"))
per["yrs"] = (per["last"] - per["first"]).dt.days / 365.25
out["A_listed_bdcs_with_report_2012_22"] = int(len(per))
out["A_listed_bdc_reports_2012_22"] = int(len(A))
out["A_listed_bdcs_ge20_reports_and_ge5y"] = int(((per.n >= 20) & (per.yrs >= 5)).sum())
out["A_last_filing_date_used"] = str(A.filingDate.max().date())

# B. XBRL NAVPS facts
f = pd.read_parquet(FIL / "d2_bdc_navps_facts.parquet")
f["end"] = pd.to_datetime(f["end"]); f["filed"] = pd.to_datetime(f["filed"])
f = f[f.cik.isin(set(A.cik))]
fe = f[(f.end >= FIT0) & (f.end <= FIT1)]
pit = fe[fe.filed <= FIT1]                       # known inside the fit window
qe = lambda d: d[["cik", "end"]].drop_duplicates()
pit_q = qe(pit); any_q = qe(fe)
c_pit = pit_q.groupby("cik").size(); c_any = any_q.groupby("cik").size()
span = lambda d: d.groupby("cik").end.agg(lambda s: (s.max() - s.min()).days / 365.25)
out["B_pit_bdc_quarter_ends_2012_22"] = int(len(pit_q))
out["B_pit_share_of_listed_reports"] = round(len(pit_q) / len(A), 4)
out["B_pit_bdcs"] = int(pit_q.cik.nunique())
out["B_pit_bdcs_ge20_quarters"] = int((c_pit >= 20).sum())
out["B_pit_bdcs_span_ge5y"] = int((span(pit_q) >= 5).sum()) if len(pit_q) else 0
out["B_pit_by_end_year"] = {int(k): int(v) for k, v in pit_q.end.dt.year.value_counts().sort_index().items()}
out["B_relaxed_notPIT_bdc_period_ends_2012_22"] = int(len(any_q))
out["B_relaxed_bdcs_ge20_period_ends"] = int((c_any >= 20).sum())
out["B_relaxed_by_end_year"] = {int(k): int(v) for k, v in any_q.end.dt.year.value_counts().sort_index().items()}

# C. Compustat fundq rdq rows for these BDCs (values not cached locally)
ccm = pd.read_parquet(FIL / "cik_permno_ccm.parquet")
ccm["cik"] = pd.to_numeric(ccm["cik"], errors="coerce")
gv = set(ccm[ccm.cik.isin(set(A.cik))].gvkey)
cq = pd.read_parquet(FIL / "comp_fundq_rdq.parquet")
cq["datadate"] = pd.to_datetime(cq["datadate"]); cq["rdq"] = pd.to_datetime(cq["rdq"])
C = cq[cq.gvkey.isin(gv) & (cq.datadate >= FIT0) & (cq.datadate <= FIT1) & cq.rdq.notna() & (cq.rdq <= FIT1)]
cc = C.groupby("gvkey").size()
out["C_bdc_gvkeys_linked"] = int(len(gv))
out["C_fundq_rows_with_rdq_2012_22"] = int(len(C))
out["C_gvkeys_ge20_quarters"] = int((cc >= 20).sum())
out["C_local_fundq_columns"] = pq.ParquetFile(FIL / "comp_fundq_rdq.parquet").schema_arrow.names
rdq_lag = (C.rdq - C.datadate).dt.days
out["C_rdq_minus_datadate_days_p10_p50_p90"] = [float(rdq_lag.quantile(q)) for q in (0.1, 0.5, 0.9)]

# D. CRSP prices, fit window only
perm = sorted(int(p) for p in A.permno.dropna().unique())
sch = pq.ParquetFile(DSF).schema_arrow
lim = pa.scalar(_dt.datetime(2022, 12, 30), type=sch.field("date").type)
t = ds.dataset(DSF).to_table(columns=["permno", "date", "prc"],
        filter=ds.field("permno").isin(perm) & (ds.field("date") <= lim) & (ds.field("date") >= pa.scalar(_dt.datetime(2012, 1, 1), type=sch.field("date").type))).to_pandas()
assert t.date.max() <= FIT1, "holdout leak"
g = t.dropna(subset=["prc"]).groupby("permno").date.agg(["size", "min", "max"])
out["D_bdc_permnos"] = len(perm)
out["D_permnos_with_prices_2012_22"] = int(len(g))
out["D_permnos_ge1260_price_days"] = int((g["size"] >= 1260).sum())
out["D_price_last_date"] = str(t.date.max().date())

print(json.dumps(out, indent=1, default=str))
Path("feasibility_counts.json").write_text(json.dumps(out, indent=1, default=str))
