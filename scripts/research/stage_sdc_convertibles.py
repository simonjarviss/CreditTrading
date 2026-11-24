"""Stage US convertible issues (SDC) and the issuers' daily rows (CRSP), for research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_sdc_convertibles.py

WHY: the desk measured the convertible-issuance rebound once, as E2, on TRACE's first 144A
trade for 2011-22 (results/events/REPRO_CORP_EVENTS_2026-10-11.md: +0.54% over days 2 to 5,
+0.17% in 2020-22). SDC's new-issues table on R2 dates convertible issues from 2000 to 2025,
public and private, so the years before 2011 and after 2022 have not been seen. This stages
them in the same shape as the follow-on file so the follow-on test's rule runs unchanged.

WHAT IT SELECTS, fixed before any return was read:
  events   wrds_ni_details rows, nation United States, issue date from --start, with a
           conversion price or a security name containing 'conv' or 'cvt' (notes, bonds,
           debentures and convertible preferred; public, 144A and private markets); one event
           per (6-digit CUSIP, issue date). Matched to the CRSP common share (EQTY/COM/NS)
           with that 6-digit CUSIP on the issue date.
  panel    the issuers' daily rows from 90 calendar days before to 120 after each issue date.

WHERE IT WRITES: `~/quantt_research/sdc_convertibles.parquet` and `crsp_convertible_daily.parquet`
(the follow-on file's columns). Licensed rows: never in the repository. Read-only at R2.
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
    ev, px = out / "sdc_convertibles.parquet", out / "crsp_convertible_daily.parquet"
    con.execute(f"""
        copy (
          with cv as (
            select substr(cusip, 1, 6) as c6, master_deal_date as issue_date, min(filingdate) as filed,
                   min(launch_date) as launch, sum(proceedsoversold) as proceeds_musd,
                   cast(null as double) as primary_shares, cast(null as double) as secondary_shares,
                   count(*) as tranches, any_value(market) as market, any_value(security) as security
            from read_parquet('{ni}')
            where nation = 'United States' and master_deal_date >= cast(? as date) and cusip is not null
              and (cvtprice is not null or security ilike '%conv%' or security ilike '%cvt%')
            group by all)
          select s.permno, f.*, cast(s.dlyprc as double) as prc_issue, cast(s.dlycap as double) as cap_issue_k
          from cv f join read_parquet('{dsf}') s
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
                               count(*) filter (where market ilike '%public%'), count(*) filter (where launch is null)
                        from read_parquet('{ev}')""").fetchone()
    print(f"{ev.name}: {n[0]:,} convertible issues on {n[1]:,} securities, issue dates {n[2]} .. {n[3]}; "
          f"{n[4]:,} in a public market; {n[5]:,} with no launch date")
    yr = con.execute(f"select year(issue_date) y, count(*) from read_parquet('{ev}') group by 1 order by 1").fetchall()
    print("by year:", " ".join(f"{y}:{k}" for y, k in yr))
    return 0


if __name__ == "__main__":
    sys.exit(main())
