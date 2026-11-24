"""Stage dividend initiations and resumptions on common stocks, and their daily panel, for research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_crsp_div_initiations.py

WHY: the team lead's event list (docs/MISSION.md section 5) asks for corporate events in any
asset class. A company that has paid no cash dividend for two years and declares one is
telling the market something about its cash flow, and the published record is a drift that
lasts months, on the long side, in ordinary listed shares: no borrow, and slow enough that
the entry day cannot matter (the special-dividend test showed CRSP's declaration date can
run a few days ahead of the filing; results/ideas/2026-11-15_special_dividends.md).

WHAT IT SELECTS, from CRSP's own codes, fixed before any return was read:
  events   an ordinary cash dividend (distype 'CD', US dollars, amount > 0) on a common share
           (EQTY/COM/NS on the ex-date), ex-date from --start, where the same security has
           (a) no cash dividend of any kind ('CD' or 'SD') with an ex-date in the 730 calendar
           days before this one, and (b) a first CRSP daily row at least 730 days before the
           ex-date, so the two dividend-free years were observed and not a new listing.
  panel    those securities' daily rows from 150 calendar days before to 420 after the ex-date.

WHERE IT WRITES: `~/quantt_research/crsp_div_init_events.parquet` and
`crsp_div_init_daily.parquet`. CRSP rows are licensed: never in the repository, never under
`data/`. Read-only at R2. Prints counts only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

COMMON = "securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'NS'"


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
    dis = r2.r2_path("crsp_a_stock", "stkdistributions")
    dsf = r2.r2_path("crsp_a_stock", "dsf_v2")
    ev, px = out / "crsp_div_init_events.parquet", out / "crsp_div_init_daily.parquet"
    con.execute(f"""
        copy (
          with cash as (
            select permno, disexdt as ex_date, disdeclaredt as declared, distype,
                   cast(disdivamt as double) as amount, disfreqtype as freq,
                   lag(disexdt) over (partition by permno order by disexdt) as prev_ex
            from (select distinct permno, disexdt, disdeclaredt, distype, disdivamt, disfreqtype
                  from read_parquet('{dis}')
                  where dispaymenttype = 'USD' and distype in ('CD', 'SD') and disdivamt > 0)),
          born as (select permno, min(dlycaldt) as first_row from read_parquet('{dsf}') group by permno),
          typed as (select permno, dlycaldt from read_parquet('{dsf}')
                    where dlycaldt >= cast(? as date) and {COMMON})
          select c.permno, c.ex_date, c.declared, c.amount, c.freq, c.prev_ex, b.first_row
          from cash c join born b on b.permno = c.permno
               join typed t on t.permno = c.permno and t.dlycaldt = c.ex_date
          where c.distype = 'CD' and c.ex_date >= cast(? as date)
            and (c.prev_ex is null or c.prev_ex < c.ex_date - interval 730 day)
            and b.first_row <= c.ex_date - interval 730 day
          order by ex_date, permno
        ) to '{ev}' (format parquet)""", [a.start, a.start])
    con.execute(f"""
        copy (
          select distinct d.permno, d.dlycaldt as date, cast(d.dlyret as double) as ret,
                 cast(d.dlyprc as double) as prc, cast(d.dlyprcvol as double) as dollar_volume
          from read_parquet('{dsf}') d join read_parquet('{ev}') e on e.permno = d.permno
          where d.dlycaldt between e.ex_date - interval 150 day and e.ex_date + interval 420 day
          order by permno, date
        ) to '{px}' (format parquet)""")
    n = con.execute(f"""select count(*), count(distinct permno), min(ex_date), max(ex_date),
                               count(*) filter (where declared is null),
                               count(*) filter (where prev_ex is null),
                               median(ex_date - declared)
                        from read_parquet('{ev}')""").fetchone()
    m = con.execute(f"select count(*), min(date), max(date) from read_parquet('{px}')").fetchone()
    print(f"{ev.name}: {n[0]:,} events on {n[1]:,} securities, ex-dates {n[2]} .. {n[3]}; "
          f"{n[4]:,} with no declaration date; {n[5]:,} first-ever dividends, the rest resumptions; "
          f"median days from declaration to ex-date {n[6]}")
    print(f"{px.name}: {m[0]:,} daily rows, {m[1]} .. {m[2]}")
    yr = con.execute(f"select year(ex_date) y, count(*) from read_parquet('{ev}') group by 1 order by 1").fetchall()
    print("events by year:", " ".join(f"{y}:{k}" for y, k in yr))
    return 0


if __name__ == "__main__":
    sys.exit(main())
