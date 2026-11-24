"""Feasibility scan of data/ (read-only): which panels mention any listed-BDC
ticker or permno, and does any of them carry a NAV column for a BDC?

WHY: the requirement is a point-in-time BDC NAV history; data/ is the first place
the house rules say to look.  We read only schemas and identifier columns.
"""
import os
from pathlib import Path
import pandas as pd, pyarrow.parquet as pq

DATA = Path("data").resolve()
WT = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/.claude/worktrees")
r = pd.read_parquet(WT / "research-ss-expansion/results/events/ssx/_cache_ssx_fil/d2_bdc_reports.parquet")
r["filingDate"] = pd.to_datetime(r["filingDate"])
L = r[(r.listed == True) & (r.filingDate <= "2022-12-31") & (r.filingDate >= "2012-01-01")]
TICK = set(L.ticker.dropna().unique())
PERM = set(int(p) for p in L.permno.dropna().unique())
print("BDC tickers", len(TICK), "permnos", len(PERM))
IDCOLS = {"ticker", "symbol", "tic", "sym", "fund", "nav_ticker", "permno"}
for root, dirs, files in os.walk(DATA):
    if "bond_day_panel" in root:
        continue
    for fn in files:
        p = Path(root) / fn
        rel = p.relative_to(DATA)
        try:
            if fn.endswith(".parquet"):
                names = pq.ParquetFile(p).schema_arrow.names
                cols = [c for c in names if c.lower() in IDCOLS]
                if not cols:
                    continue
                df = pd.read_parquet(p, columns=cols)
            elif fn.endswith(".csv") and p.stat().st_size < 200e6:
                df = pd.read_csv(p, low_memory=False)
                cols = [c for c in df.columns if str(c).lower() in IDCOLS]
                if not cols:
                    continue
                names = list(df.columns)
                df = df[cols]
            else:
                continue
        except Exception as e:  # report, never hide
            print("UNREADABLE", rel, type(e).__name__, str(e)[:80])
            continue
        hit = set()
        for c in cols:
            v = df[c].dropna().unique()
            if c.lower() == "permno":
                hit |= set(int(x) for x in v if str(x).replace('.0','').isdigit()) & PERM
            else:
                hit |= set(map(str, v)) & TICK
        if hit:
            navcols = [c for c in names if "nav" in c.lower()]
            print(f"HIT {rel}: {len(hit)} BDC ids, nav-like cols={navcols}, sample={sorted(map(str,hit))[:8]}")
