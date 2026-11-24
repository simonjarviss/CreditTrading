"""Feasibility scan: do any local (already-fetched) EDGAR caches hold BDC 10-Q/10-K
or 8-K documents for the listed BDCs in 2012-2022?  Read-only; no network.

WHY: the only way to get a point-in-time BDC NAV history 2012-22 without a new
EDGAR pull is if earlier desk work already cached the filings' text.  We match
cache paths /Archives/edgar/data/<cik>/<acc>/ against the listed-BDC report
accessions in the ssx_fil D2 cache (d2_bdc_reports.parquet).
"""
import sys, os, re, json
from pathlib import Path
import pandas as pd

WT = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/.claude/worktrees")
D2 = WT / "research-ss-expansion/results/events/ssx/_cache_ssx_fil/d2_bdc_reports.parquet"
r = pd.read_parquet(D2)
r["filingDate"] = pd.to_datetime(r["filingDate"])
fit = r[(r.filingDate >= "2012-01-01") & (r.filingDate <= "2022-12-31") & (r.listed == True)]
ciks = set(str(int(c)) for c in fit.cik.unique())
accs = set(a.replace("-", "") for a in fit.accessionNumber)
print("listed BDC ciks", len(ciks), "reports (accessions) 2012-22", len(accs))

pat = re.compile(r"/Archives/edgar/data/(\d+)/(\d{18})")
hits_cik = {}
hits_acc = set()
other_bdc_docs = 0
caches = [p for p in WT.glob("*/results/events/_cache_edgar")] + [p for p in WT.glob("*/results/events/_cache_event_engine")]
for c in caches:
    for root, dirs, files in os.walk(c):
        for fn in files:
            full = os.path.join(root, fn)
            m = pat.search(full)
            if not m:
                continue
            cik, acc = m.group(1), m.group(2)
            if cik in ciks:
                hits_cik.setdefault(cik, set()).add(acc)
                if acc in accs:
                    hits_acc.add(acc)
print("caches scanned", len(caches))
print("BDC ciks with any cached archive doc", len(hits_cik))
print("distinct BDC accessions cached", sum(len(v) for v in hits_cik.values()))
print("of which are listed-BDC 10-Q/10-K reports 2012-22", len(hits_acc))

# What forms are the cached BDC accessions?  subs_rows holds the submissions index.
SUBS = WT / "research-ss-expansion/results/events/ssx/_cache_ssx_fil/subs_rows.parquet"
import pyarrow.parquet as pq
print("subs_rows columns", pq.ParquetFile(SUBS).schema_arrow.names)
s = pd.read_parquet(SUBS, columns=["cik", "accessionNumber", "form", "filingDate", "items"])
s["acc"] = s.accessionNumber.str.replace("-", "")
cached = set(a for v in hits_cik.values() for a in v)
sc = s[s.acc.isin(cached)].copy()
sc["filingDate"] = pd.to_datetime(sc.filingDate)
sc["fit"] = (sc.filingDate >= "2012-01-01") & (sc.filingDate <= "2022-12-31")
print("cached BDC accessions found in subs_rows", len(sc))
print(sc.groupby(["fit", "form"]).size().sort_values(ascending=False).head(20))
e202 = sc[sc.fit & (sc.form == "8-K") & sc["items"].fillna("").str.contains("2.02")]
print("cached 8-K item 2.02 (earnings releases) in 2012-22:", len(e202), "ciks", e202.cik.nunique())
# total available universe of 2.02 releases for the listed BDCs in the fit window
allfit = s[s.cik.astype(str).isin(ciks)].copy()
allfit["filingDate"] = pd.to_datetime(allfit.filingDate)
allfit = allfit[(allfit.filingDate >= "2012-01-01") & (allfit.filingDate <= "2022-12-31")]
a202 = allfit[(allfit.form == "8-K") & allfit["items"].fillna("").str.contains("2.02")]
print("all 8-K item 2.02 for the 61 listed BDCs 2012-22 (index only):", len(a202), "ciks", a202.cik.nunique())
