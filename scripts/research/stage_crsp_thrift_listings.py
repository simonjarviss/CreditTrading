"""Stage newly listed savings institutions (thrift conversions) and a seasoned-thrift index. Research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_crsp_thrift_listings.py

WHY: the niche hunt of 2026-11-15 (results/ideas/2026-11-15_niche_hunt.md) ranked the
mutual-to-stock conversion of a savings institution first among its ideas. Depositors buy
the shares at $10 and the new company also keeps the capital it had before, so it lists
below its tangible book value; federal rules then bar buybacks for a year and a takeover
for three (12 CFR 239.63). The published pattern (Friesen and Swift, 2009, on a sample
before 2009) is a strong first year after the first-day jump and a weak second and third.
Nobody on this desk has read a return on them, and the trade is too small for a fund.

WHAT IT SELECTS, from CRSP's own codes, fixed before any return was read:
  events   US common shares (EQTY / COM / NS, US incorporated) whose FIRST daily row is in
           [--start, --end] and whose SIC code on that row is 6035 or 6036 (federal and
           state savings institutions). Kept with: the first row's date, close, exchange and
           ticker; `prior_listing`, true when the same company (permco) had another security
           whose last daily row is within 60 days before this one's first (a second-step
           conversion replaces the listed minority shares of a mutual holding company with
           a new security; a standard conversion has no earlier listing).
  rows     each event's daily rows for its first 1,150 calendar days (three years and a
           margin), with CRSP's delisting-inclusive return, closing bid and ask.
  index    for every date, the equal-weighted return and the count of SEASONED savings
           institutions: same codes, first daily row more than 1,150 days earlier. This is
           the control a thrift-specific result has to beat; no ETF of small thrifts exists.
CRSP's SIC code misses a savings bank whose holding company is coded as a bank holding
company (6712) and admits a thrift that listed by an ordinary IPO; the first-row close near
$10 is kept so the test can separate the $10 conversions, and that close is known at entry.

WHERE IT WRITES: `~/quantt_research/crsp_thrift_events.parquet`, `crsp_thrift_daily.parquet`
and `crsp_thrift_index.parquet`. CRSP rows are licensed: never in the repository. Read-only
at R2. Prints counts only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
COMMON = "securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'NS' and usincflg = 'Y'"
THRIFT = "siccd in (6035, 6036)"
DAYS = 1150


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="1995-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--out", type=Path, default=Path.home() / "quantt_research")
    a = ap.parse_args(argv)
    out = a.out.expanduser().resolve()
    if REPO.resolve() == out or REPO.resolve() in out.parents:
        raise SystemExit(f"refusing {out}: licensed rows stay outside the repository")
    out.mkdir(parents=True, exist_ok=True)
    from src.data import r2
    con = r2.connect()
    dsf = r2.r2_path("crsp_a_stock", "dsf_v2")
    con.execute(f"""
        create temp table span as
          select permno, any_value(permco) as permco, min(dlycaldt) as first_date, max(dlycaldt) as last_date
          from read_parquet('{dsf}') group by 1""")
    con.execute(f"""
        create temp table ev as
          select x.permno, s.permco, s.first_date, cast(x.dlyprc as double) as first_close, x.primaryexch as exch,
                 x.ticker, x.siccd,
                 exists (select 1 from span o where o.permco = s.permco and o.permno <> s.permno
                         and o.last_date between s.first_date - interval 60 day and s.first_date + interval 5 day
                         and o.first_date < s.first_date - interval 60 day) as prior_listing
          from read_parquet('{dsf}') x join span s on s.permno = x.permno and s.first_date = x.dlycaldt
          where s.first_date between cast(? as date) and cast(? as date) and {COMMON} and x.{THRIFT}""", [a.start, a.end])
    ev, px, ix = out / "crsp_thrift_events.parquet", out / "crsp_thrift_daily.parquet", out / "crsp_thrift_index.parquet"
    con.execute(f"copy (select * from ev order by first_date, permno) to '{ev}' (format parquet)")
    con.execute(f"""
        copy (
          select x.permno, x.dlycaldt as date, cast(x.dlyret as double) as ret, cast(x.dlyprc as double) as prc,
                 cast(x.dlyprcvol as double) as dollar_volume, cast(x.dlycap as double) as cap,
                 cast(x.dlybid as double) as bid, cast(x.dlyask as double) as ask, x.dlydelflg as delflg
          from read_parquet('{dsf}') x join ev e on e.permno = x.permno
               and x.dlycaldt between e.first_date and e.first_date + interval {DAYS} day
          where x.dlycaldt <= cast(? as date) order by date, permno
        ) to '{px}' (format parquet, compression zstd)""", [a.end])
    con.execute(f"""
        copy (
          select x.dlycaldt as date, avg(cast(x.dlyret as double)) as ret, count(x.dlyret) as n
          from read_parquet('{dsf}') x join span s on s.permno = x.permno
          where x.dlycaldt between cast(? as date) and cast(? as date) and {COMMON} and x.{THRIFT}
            and x.dlycaldt > s.first_date + interval {DAYS} day and x.dlyret is not null
          group by 1 order by 1
        ) to '{ix}' (format parquet)""", [a.start, a.end])
    n = con.execute("select count(*), sum(case when prior_listing then 1 else 0 end), "
                    "sum(case when first_close between 8 and 16 then 1 else 0 end), min(first_date), max(first_date) from ev").fetchone()
    by = con.execute("select year(first_date), count(*) from ev group by 1 order by 1").fetchall()
    m = con.execute(f"select count(*), max(date) from read_parquet('{px}')").fetchone()
    k = con.execute(f"select count(*), min(n), median(n), max(date) from read_parquet('{ix}')").fetchone()
    print(f"{ev.name}: {n[0]:,} newly listed savings institutions, first rows {n[3]} .. {n[4]}; "
          f"{n[1]:,} with a prior listing of the same company; {n[2]:,} with a first close of $8 to $16")
    print("by year:", ", ".join(f"{y}: {c}" for y, c in by))
    print(f"{px.name}: {m[0]:,} daily rows, to {m[1]}")
    print(f"{ix.name}: {k[0]:,} days, seasoned names per day min {k[1]} median {k[2]}, to {k[3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
