"""Stage S&P 600 / 400 / 500 membership from index-ETF holdings, and CRSP daily rows. Research only.

    QUANTT_ENV_FILE=<env file> python3 results/ideas/sp600_changes/stage.py

WHY: the desk has no survivorship-free S&P membership history. Compustat `idxcst_his` on R2
holds today's members only (602 / 400 / 503 rows, no `thru` date: re-measured 2026-11-16),
S&P's announcement pages refuse robots (results/events/ssx/ssx_data/DATA_MAP_2026-10-19.md),
and Wikipedia's S&P 600 change table is incomplete. The in-house route named by the
2026-10-19 census is the MONTHLY holdings of the index ETFs in CRSP Mutual Funds: IJR
(S&P SmallCap 600), IJH (MidCap 400) and IVV (S&P 500), which replicate fully, so a share
that leaves the fund's month-end list left the index during that month.

WHAT THIS CANNOT GIVE: the effective DATE. A change is known only to the month, so a book
built on it enters between 1 and about 23 sessions after the change took effect. The card
says so; nothing here estimates the day.

WRITES (licensed rows, outside the repository), under ~/quantt_research/sp600_changes/:
  holdings.parquet   fund, report_dt, permno, ticker, percent_tna for IJR / IJH / IVV, and
                     VIOO (Vanguard's S&P 600 fund, a second source for a check), report
                     dates 2008-01-31 onward.
  daily.parquet      CRSP daily rows 2007-07-01 .. 2025-12-31 for every US common share:
                     delisting-inclusive return, price, market value, dollar volume, closing
                     bid and ask. All common shares, because the size-matched control is
                     drawn from shares that are NOT in any of the three funds.
Read-only at R2. Prints counts only.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = Path.home() / "quantt_research" / "sp600_changes"
FUNDS = ("IJR", "IJH", "IVV", "VIOO")
COMMON = "securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'NS' and usincflg = 'Y'"


def main() -> int:
    if REPO.resolve() in OUT.resolve().parents:
        raise SystemExit("licensed rows stay outside the repository")
    OUT.mkdir(parents=True, exist_ok=True)
    from src.data import r2
    con = r2.connect()
    pm, h, dsf = (r2.r2_path("crsp_q_mutualfunds", "portnomap"), r2.r2_path("crsp_q_mutualfunds", "holdings"),
                  r2.r2_path("crsp_a_stock", "dsf_v2"))
    hp, dp = OUT / "holdings.parquet", OUT / "daily.parquet"
    if not hp.exists():
        ports = con.execute(f"select distinct ticker, cast(crsp_portno as bigint) as portno from read_parquet('{pm}') "
                            f"where ticker in {FUNDS} and crsp_portno is not null").fetchdf()
        if set(ports["ticker"]) != set(FUNDS):
            raise KeyError(f"portnomap lacks {set(FUNDS) - set(ports['ticker'])}")
        # The portfolio numbers go in as literals: a join against them is not pushed down, and
        # the 11 GB holdings file is then read whole (first attempt, 2026-11-16: no result in 12 minutes).
        ids = ", ".join(str(int(x)) for x in sorted(set(ports["portno"])))
        df = con.execute(f"""
            select cast(crsp_portno as bigint) as portno, report_dt, cast(permno as integer) as permno, ticker, cusip,
                   cast(percent_tna as double) as percent_tna
            from read_parquet('{h}') where crsp_portno in ({ids}) and report_dt >= DATE '2008-01-31'""").fetchdf()
        df = df.merge(ports.rename(columns={"ticker": "fund"}), on="portno", validate="m:1")
        df.sort_values(["fund", "report_dt", "permno"]).to_parquet(hp, index=False)
    print(con.execute(f"select fund, count(distinct report_dt) reports, min(report_dt) first_dt, max(report_dt) last_dt, "
                      f"count(*) n, count(permno) with_permno from read_parquet('{hp}') group by 1 order by 1").fetchdf().to_string())
    if not dp.exists():
        con.execute(f"""
            copy (select permno, dlycaldt as date, cast(dlyret as double) as ret, cast(dlyprc as double) as prc,
                         cast(dlycap as double) as cap, cast(dlyprcvol as double) as dollar_volume,
                         cast(dlyvol as double) as vol, cast(dlybid as double) as bid, cast(dlyask as double) as ask
                  from read_parquet('{dsf}')
                  where dlycaldt between DATE '2007-07-01' and DATE '2025-12-31' and {COMMON}
                  order by date, permno)
            to '{dp}' (format parquet, compression zstd)""")
    print(con.execute(f"select count(*) n, count(distinct permno) permnos, min(date) first_dt, max(date) last_dt, "
                      f"count(bid) with_bid from read_parquet('{dp}')").fetchdf().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
