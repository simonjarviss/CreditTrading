"""Second pass: wide panels (one column per ticker) would be missed by an
identifier-column scan.  Intersect every parquet's column names with the BDC
tickers, and list every parquet with a NAV-like column.  Read-only."""
import os
from pathlib import Path
import pandas as pd, pyarrow.parquet as pq
DATA = Path("data").resolve()
WT = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/.claude/worktrees")
r = pd.read_parquet(WT / "research-ss-expansion/results/events/ssx/_cache_ssx_fil/d2_bdc_reports.parquet")
TICK = set(r[r.listed == True].ticker.dropna().unique())
for root, dirs, files in os.walk(DATA):
    if "bond_day_panel" in root:
        continue
    for fn in files:
        if not fn.endswith(".parquet"):
            continue
        p = Path(root) / fn
        names = pq.ParquetFile(p).schema_arrow.names
        w = set(names) & TICK
        nav = [c for c in names if "nav" in c.lower()]
        if w or nav:
            print(p.relative_to(DATA), "| BDC-named cols:", sorted(w)[:10], "| nav cols:", nav[:6], "| ncols", len(names))
