"""Stage every CRSP ETF's daily rows, with the closing bid and ask, for thin_etf_catchup.

    QUANTT_ENV_FILE=<env> python3 results/ideas/thin_etf_catchup/stage.py

WHY A NEW PANEL: `~/quantt_research/crsp_exdate_etf_daily.parquet` keeps only ETFs that ever
paid a distribution (it was built for the ex-date test), so gold, commodity and currency
funds are missing from it, and it has neither share volume nor the closing quote. This test
is about whether a thin fund's close is a price at all, so it needs the volume (a day with
no trade is not a traded close) and CRSP's closing bid and ask (to rescore on the mid).

WHAT IS KEPT: securitytype FUND, subtype ETF, regular-way, actively trading rows from
2000-01-01. Dead funds are in, because CRSP keeps them. ETNs are a different subtype and are
out. Licensed rows: written only under ~/quantt_research/thin_etf_catchup/, never in the
repository. Read-only at R2. Prints counts only.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = Path.home() / "quantt_research" / "thin_etf_catchup"


def main() -> int:
    if REPO.resolve() in OUT.resolve().parents:
        raise SystemExit("licensed rows stay outside the repository")
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / "crsp_etf_all_daily.parquet"
    tmp = dest.with_suffix(".partial")
    if dest.exists():
        print(f"{dest} exists; delete it to restage")
        return 0
    from src.data import r2
    con = r2.connect()
    src = r2.r2_path("crsp_a_stock", "dsf_v2")
    con.execute(f"""
        copy (
          select permno, ticker, dlycaldt as date, cast(dlyret as double) as ret,
                 cast(dlyprc as double) as prc, cast(dlyprcvol as double) as dollar_volume,
                 cast(dlyvol as double) as vol, cast(dlybid as double) as bid,
                 cast(dlyask as double) as ask, cast(dlycap as double) as cap
          from read_parquet('{src}')
          where dlycaldt >= date '2000-01-01' and securitytype = 'FUND'
            and securitysubtype = 'ETF' and conditionaltype = 'RW' and tradingstatusflg = 'A'
          order by date, permno
        ) to '{tmp}' (format parquet, compression zstd)""")
    tmp.rename(dest)       # a run that dies leaves no file that looks finished
    s = con.execute(f"""select count(*), min(date), max(date), count(distinct permno),
                               avg(case when vol > 0 then 1.0 else 0.0 end),
                               avg(case when bid > 0 and ask >= bid then 1.0 else 0.0 end)
                        from read_parquet('{dest}')""").fetchone()
    print(f"{dest.name}: {s[0]:,} rows, {s[1]} .. {s[2]}, {s[3]:,} funds, "
          f"{s[4]:.1%} of rows traded, {s[5]:.1%} with a closing bid and ask")
    return 0


if __name__ == "__main__":
    sys.exit(main())
