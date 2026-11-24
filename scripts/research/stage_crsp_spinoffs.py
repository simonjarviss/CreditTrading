"""Stage spin-offs from CRSP: the events, the new and parent companies' daily rows, and a control. Research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_crsp_spinoffs.py

WHY: spin-offs are on the event list the team lead asked for on 2026-11-11
(docs/MISSION.md section 5), and the desk's catalogue
(results/events/SPECIAL_SITUATIONS_CATALOGUE_CORP_2026-10-15.md, B1) counted them and
stopped. The claim to test is the old one: holders who are handed shares they did not choose
sell them, so the new company is weak at first and strong afterwards.

THE EVENT (`crsp_a_stock.stkdistributions`), fixed before any return was read:
  a row with `distype = 'SP'` and `disdetailtype = 'SECSO'` (a distribution of another
  company's shares, CRSP's spin-off code), whose distributed security (`dispermno`) is a
  different permno from the payer and is a US common share (EQTY / COM / NS, US
  incorporated) in `stocknames_v2`.
  NEW means the distributed security's first daily row is no more than 10 days before the
  ex-date. A security that already traded (a parent handing out a listed subsidiary) is a
  different event and is flagged `child_already_listed`, staged, and left to the test.
Each (parent, child) pair is kept once, at its earliest ex-date.

THE CONTROL: every other US common share whose first daily row is in the same period, so
the test can ask whether what it finds is about spin-offs or about any new listing.
CRSP has no row for when-issued trading; a security's first row is its first regular-way
session, and that row has no return.

ROWS (`crsp_a_stock.dsf_v2`): children and control securities for their first 800 calendar
days; parents from 30 days before the ex-date to 800 after. To 2025-12-31.

WHERE IT WRITES: `~/quantt_research/crsp_spinoff_events.parquet`,
`crsp_spinoff_daily.parquet`, `crsp_newlist_daily.parquet`. CRSP rows are licensed: never in
the repository. Read-only at R2. Prints counts only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
COLS = ("x.permno, x.dlycaldt as date, cast(x.dlyret as double) as ret, cast(x.dlyprc as double) as prc, "
        "cast(x.dlycap as double) as cap, cast(x.dlyprcvol as double) as dollar_volume, x.dlydelflg as delflg")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2000-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--out", type=Path, default=Path.home() / "quantt_research")
    a = ap.parse_args(argv)
    out = a.out.expanduser().resolve()
    if REPO.resolve() == out or REPO.resolve() in out.parents:
        raise SystemExit(f"refusing {out}: licensed rows stay outside the repository")
    out.mkdir(parents=True, exist_ok=True)
    from src.data import r2
    con = r2.connect()
    dist, names, dsf = (r2.r2_path("crsp_a_stock", "stkdistributions"), r2.r2_path("crsp_a_stock", "stocknames_v2"),
                        r2.r2_path("crsp_a_stock", "dsf_v2"))
    con.execute(f"""
        create temp table common as
          select permno, min(namedt) as first_name from read_parquet('{names}')
          where securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'NS' and usincflg = 'Y'
          group by 1""")
    con.execute(f"""
        create temp table first_row as
          select permno, min(dlycaldt) as first_date from read_parquet('{dsf}')
          where permno in (select permno from common) group by 1""")
    con.execute(f"""
        create temp table raw as
          select permno as parent, cast(dispermno as integer) as child, min(disexdt) as ex_date,
                 min(disdeclaredt) as declared, count(*) as n_rows
          from read_parquet('{dist}')
          where distype = 'SP' and disdetailtype = 'SECSO' and dispermno is not null and dispermno <> 0
            and dispermno <> permno and disexdt between cast(? as date) and cast(? as date)
          group by 1, 2""", [a.start, a.end])
    n_raw = con.execute("select count(*) from raw").fetchone()[0]
    con.execute("""
        create temp table ev as
          select r.*, f.first_date as child_first,
                 (f.first_date < r.ex_date - interval 10 day) as child_already_listed
          from raw r join first_row f on f.permno = r.child""")
    events = out / "crsp_spinoff_events.parquet"
    con.execute(f"copy (select * from ev order by ex_date, child) to '{events}' (format parquet)")
    rows = out / "crsp_spinoff_daily.parquet"
    con.execute(f"""
        copy (
          with w as (select child as permno, min(least(child_first, ex_date)) - interval 5 day as lo,
                            max(ex_date) + interval 800 day as hi from ev group by 1
                     union all
                     select parent, min(ex_date) - interval 30 day, max(ex_date) + interval 800 day from ev group by 1),
               u as (select permno, min(lo) as lo, max(hi) as hi from w group by 1)
          select {COLS} from read_parquet('{dsf}') x join u on x.permno = u.permno and x.dlycaldt between u.lo and u.hi
          where x.dlycaldt <= cast(? as date) order by date, permno
        ) to '{rows}' (format parquet, compression zstd)""", [a.end])
    ctl = out / "crsp_newlist_daily.parquet"
    con.execute(f"""
        copy (
          with n as (select permno, first_date from first_row
                     where first_date between cast(? as date) and cast(? as date)
                       and permno not in (select child from ev))
          select {COLS} from read_parquet('{dsf}') x join n on x.permno = n.permno
                 and x.dlycaldt between n.first_date and n.first_date + interval 800 day
          where x.dlycaldt <= cast(? as date) order by date, permno
        ) to '{ctl}' (format parquet, compression zstd)""", [a.start, a.end, a.end])
    e = con.execute("""select count(*), sum(case when child_already_listed then 1 else 0 end), count(distinct parent),
                              min(ex_date), max(ex_date), sum(case when declared is null then 1 else 0 end) from ev""").fetchone()
    by = con.execute("""select year(ex_date), count(*) from ev where not child_already_listed group by 1 order by 1""").fetchall()
    r1 = con.execute(f"select count(*), count(distinct permno), max(date) from read_parquet('{rows}')").fetchone()
    r2_ = con.execute(f"select count(*), count(distinct permno), max(date) from read_parquet('{ctl}')").fetchone()
    print(f"spin-off (parent, child) pairs {a.start}..{a.end}: {n_raw:,}; child is a US common share with rows: {e[0]:,}; "
          f"of those the child already traded: {e[1]:,}; distinct parents {e[2]:,}; ex-dates {e[3]} .. {e[4]}; no declaration date {e[5]:,}")
    print("new spin-offs by year:", ", ".join(f"{y}: {n}" for y, n in by))
    print(f"{rows.name}: {r1[0]:,} rows, {r1[1]:,} permnos, to {r1[2]}")
    print(f"{ctl.name}: {r2_[0]:,} rows, {r2_[1]:,} other new listings, to {r2_[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
