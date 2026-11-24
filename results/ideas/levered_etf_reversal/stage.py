"""Stage the CRSP rows the leveraged-ETF footprint test needs (licensed: written only under
~/quantt_research/levered_etf_reversal/, never in the repository).

    QUANTT_ENV_FILE=<env> python3 results/ideas/levered_etf_reversal/stage.py

WHY A SEPARATE STEP: the pull is slow and the rows are licensed; explore.py then re-runs
from the cache without touching R2. Two files:
  etf_daily.parquet    every CRSP security of subtype ETF, 2006-01-01 to the end of CRSP:
                       return, price, shares outstanding, volume, dollar volume, closing
                       bid and ask. Dead funds are in (CRSP keeps them).
  stock_quotes.parquet the same columns for common stocks that were ever in the largest
                       1,000 by month (the candidate single-stock underlyings and their
                       no-leveraged-fund controls), 2015-01-01 on.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from src.data import r2  # noqa: E402

OUT = Path.home() / "quantt_research" / "levered_etf_reversal"
# CRSP's CIZ columns arrive as DECIMAL; cast here so nothing downstream does arithmetic on Decimal objects.
COLS = ("permno, ticker, dlycaldt as date, dlyret::double as ret, abs(dlyprc)::double as prc, shrout::double as shrout, "
        "dlyvol::double as vol, dlyprcvol::double as dollar_volume, dlybid::double as bid, dlyask::double as ask")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    con = r2.connect()
    dsf = r2.r2_path("crsp_a_stock", "dsf_v2")
    f = OUT / "etf_daily.parquet"
    if not f.exists():
        con.execute(f"copy (select {COLS} from '{dsf}' where securitysubtype = 'ETF' and dlycaldt >= date '2006-01-01' "
                    f"order by permno, dlycaldt) to '{f}' (format parquet)")
    d = pd.read_parquet(f, columns=["permno", "date"])
    print("etf_daily", len(d), d["permno"].nunique(), d["date"].min(), d["date"].max())
    g = OUT / "stock_quotes.parquet"
    if not g.exists():
        top = pd.read_parquet(Path.home() / "quantt_research" / "crsp_top4500_daily.parquet", columns=["permno", "date", "cap_rank"])
        top = top[(pd.to_datetime(top["date"]) >= "2015-01-01") & (top["cap_rank"] <= 1000)]
        ids = sorted(int(x) for x in top["permno"].unique())
        con.register("ids", pd.DataFrame({"permno": ids}))
        con.execute(f"copy (select {COLS} from '{dsf}' where permno in (select permno from ids) and dlycaldt >= date '2015-01-01' "
                    f"order by permno, dlycaldt) to '{g}' (format parquet)")
    d = pd.read_parquet(g, columns=["permno", "date"])
    print("stock_quotes", len(d), d["permno"].nunique(), d["date"].min(), d["date"].max())
    return 0


if __name__ == "__main__":
    sys.exit(main())
