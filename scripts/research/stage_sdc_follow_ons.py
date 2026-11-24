"""Stage US follow-on share offerings (SDC) and the issuers' daily rows (CRSP), for research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_sdc_follow_ons.py

WHY: the desk's catalogue carries the follow-on (seasoned) offering as card K6 and never read
a return: it was ranked low on a published remark that most offerings are now overnight
(results/events/SPECIAL_SITUATIONS_CATALOGUE_CORP_2026-10-15.md). SDC's new-issues table on R2
dates 16,070 US public follow-ons since 2000 and says, for each, whether it was launched
before its pricing date (marketed) or on it (overnight). That is the list K6 lacked.

WHAT IT SELECTS, fixed before any return was read:
  events   wrds_ni_details rows with ipo = 'No', nation United States, market 'U.S. Public',
           issue date (master_deal_date) from --start; one event per (6-digit CUSIP, issue
           date), tranches summed. Matched to the CRSP security with that 6-digit CUSIP on
           the issue date, typed common (EQTY/COM/NS) that day. Kept: filing date, launch
           date, proceeds ($M), primary and secondary shares, and CRSP's price and market
           value on the issue date (used for relative size only, never for a decision).
  panel    the issuers' daily rows from 90 calendar days before to 120 after each issue date.

WHERE IT WRITES: `~/quantt_research/sdc_follow_ons.parquet` and `crsp_follow_on_daily.parquet`.
SDC and CRSP rows are licensed: never in the repository, never under `data/`. Read-only at R2.
Prints counts only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2000-01-01")
    ap.add_argument("--out", type=Path, default=Path.home() / "quantt_research")
    a = ap.parse_args(argv)
    out = a.out.expanduser().resolve()
    if REPO.resolve() == out or REPO.resolve() in out.parents:
        raise SystemExit(f"refusing {out}: licensed rows stay outside the repository")
    out.mkdir(parents=True, exist_ok=True)
    from src.data import r2
    con = r2.connect()
    ni = r2.r2_path("tr_sdc_ni", "wrds_ni_details")
    dsf = r2.r2_path("crsp_a_stock", "dsf_v2")
    ev, px = out / "sdc_follow_ons.parquet", out / "crsp_follow_on_daily.parquet"
    con.execute(f"""
        copy (
          with fo as (
            select substr(cusip, 1, 6) as c6, master_deal_date as issue_date, min(filingdate) as filed,
                   min(launch_date) as launch, sum(proceedsoversold) as proceeds_musd,
                   max(primaryshares) as primary_shares, max(seconshares) as secondary_shares,
                   count(*) as tranches
            from read_parquet('{ni}')
            where ipo = 'No' and nation = 'United States' and market = 'U.S. Public'
              and master_deal_date >= cast(? as date) and cusip is not null
            group by all)
          select s.permno, f.*, cast(s.dlyprc as double) as prc_issue, cast(s.dlycap as double) as cap_issue_k
          from fo f join read_parquet('{dsf}') s
            on substr(s.cusip, 1, 6) = f.c6 and s.dlycaldt = f.issue_date
           and s.securitytype = 'EQTY' and s.securitysubtype = 'COM' and s.sharetype = 'NS'
          order by issue_date, permno
        ) to '{ev}' (format parquet)""", [a.start])
    con.execute(f"""
        copy (
          select distinct d.permno, d.dlycaldt as date, cast(d.dlyret as double) as ret,
                 cast(d.dlyprc as double) as prc, cast(d.dlyprcvol as double) as dollar_volume
          from read_parquet('{dsf}') d join read_parquet('{ev}') e on e.permno = d.permno
          where d.dlycaldt between e.issue_date - interval 90 day and e.issue_date + interval 120 day
          order by permno, date
        ) to '{px}' (format parquet)""")
    n = con.execute(f"""select count(*), count(distinct permno), min(issue_date), max(issue_date),
                               count(*) filter (where launch < issue_date), count(*) filter (where launch = issue_date),
                               count(*) filter (where launch is null or launch > issue_date)
                        from read_parquet('{ev}')""").fetchone()
    m = con.execute(f"select count(*), min(date), max(date) from read_parquet('{px}')").fetchone()
    print(f"{ev.name}: {n[0]:,} follow-ons on {n[1]:,} securities, issue dates {n[2]} .. {n[3]}; "
          f"launched before the issue date {n[4]:,}, on it {n[5]:,}, neither {n[6]:,}")
    print(f"{px.name}: {m[0]:,} daily rows, {m[1]} .. {m[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
