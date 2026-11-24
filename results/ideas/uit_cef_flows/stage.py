"""Stage what the CEF panel lacks for this idea: closing bid and ask, shares traded, issuer names.

    QUANTT_ENV_FILE=<env> python3 results/ideas/uit_cef_flows/stage.py

WHY: ~/quantt_research/crsp_cef_daily.parquet (scripts/research/stage_crsp_cefs.py) has no
quotes, and a thin-fund result smaller than the spread is not a result. Same filter as that
script, 2011-01-01 on (the form 487 crawl starts in 2012). Licensed rows: written only under
~/quantt_research/uit_cef_flows/, never in the repository. Read-only at R2.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = Path.home() / "quantt_research" / "uit_cef_flows"


def main() -> int:
    from src.data import r2
    con = r2.connect()
    OUT.mkdir(parents=True, exist_ok=True)
    con.execute(f"""copy (select permno, dlycaldt as date, cast(dlybid as double) as bid, cast(dlyask as double) as ask,
                                 cast(dlyvol as double) as vol
                          from read_parquet('{r2.r2_path("crsp_a_stock", "dsf_v2")}')
                          where dlycaldt >= date '2011-01-01' and securitysubtype = 'CEF'
                            and conditionaltype = 'RW' and tradingstatusflg = 'A' order by date, permno)
                    to '{OUT / "cef_quotes.parquet"}' (format parquet, compression zstd)""")
    cols = [r[0] for r in con.execute(f"describe select * from read_parquet('{r2.r2_path('crsp_a_stock', 'stocknames_v2')}')").fetchall()]
    print(cols)
    con.execute(f"""copy (select * from read_parquet('{r2.r2_path("crsp_a_stock", "stocknames_v2")}')
                          where permno in (select distinct permno from read_parquet('{OUT / "cef_quotes.parquet"}')))
                    to '{OUT / "cef_names.parquet"}' (format parquet, compression zstd)""")
    print(con.execute(f"select count(*), min(date), max(date), count(distinct permno) from read_parquet('{OUT / 'cef_quotes.parquet'}')").fetchone())
    return 0


if __name__ == "__main__":
    sys.exit(main())
