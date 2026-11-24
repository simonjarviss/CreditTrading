"""Do local CRSP daily extracts hold the listed BDCs' prices in 2012-2022?
Reads only rows with date <= 2022-12-30 (fit window; the 2023 holdout stays sealed)
and only the BDC permnos.  Read-only; the files are licensed CRSP caches already on
this machine from earlier desk work."""
from pathlib import Path
import json
import pandas as pd, pyarrow.parquet as pq, pyarrow.dataset as ds
WT = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/.claude/worktrees")
r = pd.read_parquet(WT / "research-ss-expansion/results/events/ssx/_cache_ssx_fil/d2_bdc_reports.parquet")
r["filingDate"] = pd.to_datetime(r["filingDate"])
L = r[(r.listed == True) & (r.filingDate >= "2012-01-01") & (r.filingDate <= "2022-12-31")]
PERM = sorted(int(p) for p in L.permno.dropna().unique())
FIT_END = pd.Timestamp("2022-12-30")
cands = list(WT.glob("*/results/events/_cache_crsp/dsf*.parquet")) + list(WT.glob("*/results/events/ssx/ssx_pm/_cache_crsp/dsf*.parquet"))
seen = set()
for p in cands:
    key = (p.name, p.stat().st_size)
    if key in seen:
        continue
    seen.add(key)
    sch = pq.ParquetFile(p).schema_arrow
    names = sch.names
    if "permno" not in names or "date" not in names:
        print("skip", p, names[:6]); continue
    dset = ds.dataset(p)
    import pyarrow as pa, datetime as _dt
    dt = sch.field("date").type
    assert pa.types.is_timestamp(dt) and dt.tz is None, f"unexpected date type {dt} in {p}"
    lim = pa.scalar(_dt.datetime(2022, 12, 30), type=dt)
    filt = ds.field("permno").isin(PERM) & (ds.field("date") <= lim)
    t = dset.to_table(columns=["permno", "date"], filter=filt).to_pandas()
    t["date"] = pd.to_datetime(t["date"])
    if t.empty:
        print(f"{p.relative_to(WT)}: no BDC rows"); continue
    assert t.date.max() <= FIT_END, "holdout leak"
    t = t[t.date >= "2012-01-01"]
    g = t.groupby("permno").date.agg(["min", "max", "size"])
    print(f"{p.relative_to(WT)} cols={names[:12]} BDC permnos with 2012-22 rows: {len(g)}/{len(PERM)}; with >=5y of rows: {(g['size']>=1260).sum()}")
