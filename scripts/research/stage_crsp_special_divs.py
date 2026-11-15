"""Stage special cash dividends on common stocks, and their daily panel, for research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_crsp_special_divs.py

WHY: the team lead's event list (docs/MISSION.md section 5, 2026-11-11) names special
dividends as an extension of the ex-date work. The desk counted them in October
(results/events/ssx/ssx_pm/HOW_WE_ADD_IT_2026-10-19.md: about 190 a year on common stocks)
and never read a return. A special dividend is large, announced one to three weeks ahead,
and paid once, so both the wait for the ex-date and the sessions after it can be tested.

WHAT IT SELECTS, from CRSP's own codes, fixed before any return was read:
  events   stkdistributions rows with distype 'SD' (special dividend), paid in US dollars,
           ex-date from --start, on common shares (securitytype EQTY, subtype COM,
           sharetype NS) as typed on the ex-date. Funds are left out: closed-end funds and
           ETFs pay year-end specials and belong to the fund books.
  controls every ordinary cash dividend (distype 'CD') of the same securities.
  panel    every daily row of those securities from --start, dead ones included.
           It carries CRSP's closing bid and ask (added 2026-11-15) so the spread a small
           book would pay in thin names can be measured rather than assumed.
CRSP's declaration date is kept as given; 1.9% of events have none (counted 2026-11-15)
and the test must leave those out rather than assume one.

WHERE IT WRITES: `~/quantt_research/crsp_specdiv_events.parquet` and
`crsp_specdiv_daily.parquet`. CRSP rows are licensed: never in the repository, never
under `data/`. Read-only at R2. Prints counts only.
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
    ev, px = out / "crsp_specdiv_events.parquet", out / "crsp_specdiv_daily.parquet"
    # An event is typed by the security's own codes ON its ex-date: a security that changed
    # type is judged as it was when the dividend went ex.
    con.execute(f"""
        copy (
          with sd as (
            select permno, disexdt as ex_date, disdeclaredt as declared, dispaydt as pay_date,
                   cast(disdivamt as double) as amount, distype, disdetailtype as detail,
                   distaxtype as tax
            from read_parquet('{dis}')
            where disexdt >= cast(? as date) and dispaymenttype = 'USD'
              and distype in ('SD', 'CD') and disdivamt > 0),
          typed as (
            select permno, dlycaldt from read_parquet('{dsf}')
            where dlycaldt >= cast(? as date) and {COMMON}),
          special as (
            select distinct s.permno from sd s join typed t
              on t.permno = s.permno and t.dlycaldt = s.ex_date where s.distype = 'SD')
          select s.* from sd s join typed t on t.permno = s.permno and t.dlycaldt = s.ex_date
          where s.permno in (select permno from special)
          order by permno, ex_date
        ) to '{ev}' (format parquet)""", [a.start, a.start])
    con.execute(f"""
        copy (
          select permno, ticker, siccd, dlycaldt as date, cast(dlyret as double) as ret,
                 cast(dlyprc as double) as prc, cast(dlyprcvol as double) as dollar_volume,
                 cast(dlycap as double) as cap, cast(dlyorddivamt as double) as div,
                 cast(dlybid as double) as bid, cast(dlyask as double) as ask
          from read_parquet('{dsf}')
          where dlycaldt >= cast(? as date)
            and permno in (select distinct permno from read_parquet('{ev}'))
          order by permno, date
        ) to '{px}' (format parquet)""", [a.start])
    n = con.execute(f"""select count(*) filter (where distype = 'SD'),
                               count(*) filter (where distype = 'CD'), count(distinct permno),
                               min(ex_date), max(ex_date) from read_parquet('{ev}')""").fetchone()
    m = con.execute(f"select count(*), min(date), max(date) from read_parquet('{px}')").fetchone()
    print(f"{ev.name}: {n[0]:,} special and {n[1]:,} ordinary cash dividends on {n[2]:,} "
          f"securities, ex-dates {n[3]} .. {n[4]}")
    print(f"{px.name}: {m[0]:,} daily rows, {m[1]} .. {m[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
