"""Stage the licensed rows for the Russell bottom-edge test, outside the repository.

    QUANTT_ENV_FILE=<env file> python3 results/ideas/russell_micro_boundary/stage.py

WHY: the test needs (1) every US common share on each rank day, to rank companies by market
value as FTSE Russell does, and (2) daily rows of the predicted movers and their controls
around each reconstitution. Both come from the CRSP CIZ daily file on R2 (delisted names
included, so no survivorship), and the headquarters country from Compustat through the CCM
link. Writes ~/quantt_research/russell_micro_boundary/{rankdays,daily}.parquet; nothing
row-level is printed and nothing licensed goes into the repository. Read-only at R2.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(HERE))
import universe  # noqa: E402

OUT = Path.home() / "quantt_research" / "russell_micro_boundary"
TYPE = ("securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'NS' and primaryexch in ('N', 'A', 'Q') "
        "and conditionaltype = 'RW' and tradingstatusflg = 'A'")


def main() -> int:
    if REPO.resolve() in OUT.resolve().parents:
        raise SystemExit("licensed rows stay outside the repository")
    OUT.mkdir(parents=True, exist_ok=True)
    from src.data import r2
    con = r2.connect()
    dsf = r2.r2_path("crsp_a_stock", "dsf_v2")
    top = pd.read_parquet(Path.home() / "quantt_research" / "crsp_top4500_daily.parquet", columns=["date"])
    sessions = pd.DatetimeIndex(pd.to_datetime(top["date"]).unique()).sort_values()
    cal = universe.calendar(sessions)
    rk = OUT / "rankdays.parquet"
    if not rk.exists():
        days = ", ".join(f"date '{d.date()}'" for d in cal["rank_day"])
        rd = con.execute(f"""
            select permno, permco, dlycaldt as date, usincflg, issuertype, siccd, ticker,
                   cast(dlyprc as double) as prc, cast(dlycap as double) as cap,
                   cast(dlybid as double) as bid, cast(dlyask as double) as ask
            from read_parquet('{dsf}') where dlycaldt in ({days}) and {TYPE}""").df()
        lk = con.execute(f"""select cast(lpermno as integer) as permno, gvkey, linkdt, linkenddt
                             from read_parquet('{r2.r2_path('crsp_a_ccm', 'ccmxpf_lnkhist')}')
                             where linktype in ('LU', 'LC') and linkprim in ('P', 'C')""").df()
        co = con.execute(f"select gvkey, loc from read_parquet('{r2.r2_path('comp_na_daily_all', 'company')}')").df()
        rd["date"] = pd.to_datetime(rd["date"])
        m = rd[["permno", "date"]].merge(lk.merge(co, on="gvkey"), on="permno")
        m = m[(m["date"] >= pd.to_datetime(m["linkdt"])) & (m["linkenddt"].isna() | (m["date"] <= pd.to_datetime(m["linkenddt"])))]
        rd = rd.merge(m.drop_duplicates(["permno", "date"])[["permno", "date", "loc"]], on=["permno", "date"], how="left")
        rd.to_parquet(rk)
    rd = pd.read_parquet(rk)
    sets = universe.build_sets(rd, cal)
    want = pd.DataFrame({"permno": sorted(sets["permno"].unique())})
    con.register("want", want)
    dest = OUT / "daily.parquet"
    con.execute(f"""
        copy (select d.permno, d.dlycaldt as date, cast(d.dlyret as double) as ret, cast(d.dlyprc as double) as prc,
                     cast(d.dlybid as double) as bid, cast(d.dlyask as double) as ask,
                     cast(d.dlyprcvol as double) as dollar_volume, cast(d.dlyvol as double) as vol, d.dlyprcflg as prcflg
              from read_parquet('{dsf}') d semi join want w on d.permno = w.permno
              where d.dlycaldt >= date '2001-03-01' and month(d.dlycaldt) between 3 and 10
              order by date, permno) to '{dest}' (format parquet, compression zstd)""")
    s = con.execute(f"select count(*), min(date), max(date), count(distinct permno) from read_parquet('{dest}')").fetchone()
    print(f"rank days: {len(rd):,} rows on {rd['date'].nunique()} days; daily: {s[0]:,} rows, {s[1]} .. {s[2]}, {s[3]:,} shares")
    print(sets.groupby(["year", "set"]).size().unstack().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
