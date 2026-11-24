"""Stage every CRSP exchange-traded fund's daily rows WITH closing quotes, for etf_twins.

    QUANTT_ENV_FILE=<env file> python3 results/ideas/etf_twins/stage.py

WHY A SECOND ETF PULL: the staged `crsp_exdate_etf_daily.parquet` has returns and dollar
volume only. The twins test stands or falls on stale last-trade prices, so it needs the
closing bid and ask (`dlybid`, `dlyask`), the share volume (to know a fund traded that day)
and the price flag (CRSP books a bid-ask average as the "price" on a no-trade day). Dead
funds are in: CRSP keeps every fund that ever listed. Read-only at R2; licensed rows go to
`~/quantt_research/etf_twins/`, never into the repository.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
START = "2001-01-01"


def main() -> int:
    out = Path.home() / "quantt_research" / "etf_twins"
    if REPO.resolve() in out.resolve().parents:
        raise SystemExit("licensed rows stay outside the repository")
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "crsp_etf_quotes_daily.parquet"
    if dest.exists():
        print(f"{dest} exists; delete it to refetch")
        return 0
    from src.data import r2
    con = r2.connect()
    con.execute(f"""
        copy (
          select permno, ticker, primaryexch, dlycaldt as date,
                 cast(dlyret as double) as ret, cast(dlyprc as double) as prc, dlyprcflg as prcflg,
                 cast(dlyvol as double) as vol, cast(dlyprcvol as double) as dollar_volume,
                 cast(dlybid as double) as bid, cast(dlyask as double) as ask,
                 cast(dlycumfacpr as double) as cumfacpr,
                 cast(dlyorddivamt as double) as div, cast(dlynonorddivamt as double) as div_other
          from read_parquet('{r2.r2_path("crsp_a_stock", "dsf_v2")}')
          where dlycaldt >= cast('{START}' as date) and securitytype = 'FUND' and securitysubtype = 'ETF'
          order by date, permno
        ) to '{dest}' (format parquet, compression zstd)""")
    s = con.execute(f"select count(*), min(date), max(date), count(distinct permno) from read_parquet('{dest}')").fetchone()
    print(f"{dest.name}: {s[0]:,} rows, {s[1]} .. {s[2]}, {s[3]:,} funds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
