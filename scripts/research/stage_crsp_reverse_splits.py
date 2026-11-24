"""Stage reverse and forward stock splits on common shares, and their daily panel, for research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_crsp_reverse_splits.py

WHY: the desk's October catalogue carries reverse splits as card G1 and never read a return
(the card stopped at borrow: most 2025 names were hard to short). The team lead's event list
(docs/MISSION.md section 5, 2026-11-11) asks for special situations in any asset class, and a
reverse split is a dated, public corporate action on a share that has usually fallen a long
way. Whether it keeps falling after the split takes effect is the question.

WHAT IT SELECTS, from CRSP's own codes, fixed before any return was read:
  events   stkdistributions rows with distype 'FRS' or 'SP' and a non-zero price factor
           (disfacpr), ex-date from --start, on common shares (securitytype EQTY, subtype COM,
           sharetype NS) as typed on the ex-date. A factor between -1 and 0 is a reverse split
           (1-for-10 is -0.9); a positive factor is a forward split and is kept as the control.
  panel    every daily row of those securities from --start, dead ones included, with CRSP's
           delisting-inclusive daily return.
CRSP's declaration date is kept as given (95% of reverse splits have one, counted 2026-11-15).

WHERE IT WRITES: `~/quantt_research/crsp_split_events.parquet` and `crsp_split_daily.parquet`.
CRSP rows are licensed: never in the repository, never under `data/`. Read-only at R2.
Prints counts only.
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
    ev, px = out / "crsp_split_events.parquet", out / "crsp_split_daily.parquet"
    con.execute(f"""
        copy (
          with sp as (
            select permno, disexdt as ex_date, disdeclaredt as declared,
                   cast(disfacpr as double) as facpr, cast(disfacshr as double) as facshr,
                   distype, disdetailtype as detail
            from read_parquet('{dis}')
            where disexdt >= cast(? as date) and distype in ('FRS', 'SP')
              and disfacpr is not null and disfacpr <> 0 and disfacpr > -1),
          typed as (
            select permno, dlycaldt from read_parquet('{dsf}')
            where dlycaldt >= cast(? as date) and {COMMON})
          select s.* from sp s join typed t on t.permno = s.permno and t.dlycaldt = s.ex_date
          order by permno, ex_date
        ) to '{ev}' (format parquet)""", [a.start, a.start])
    con.execute(f"""
        copy (
          select permno, ticker, dlycaldt as date, cast(dlyret as double) as ret,
                 cast(dlyprc as double) as prc, cast(dlyprcvol as double) as dollar_volume,
                 cast(dlycap as double) as cap
          from read_parquet('{dsf}')
          where dlycaldt >= cast(? as date)
            and permno in (select distinct permno from read_parquet('{ev}'))
          order by permno, date
        ) to '{px}' (format parquet)""", [a.start])
    n = con.execute(f"""select count(*) filter (where facpr < 0), count(*) filter (where facpr > 0),
                               count(distinct permno), min(ex_date), max(ex_date),
                               count(*) filter (where facpr < 0 and declared is null)
                        from read_parquet('{ev}')""").fetchone()
    m = con.execute(f"select count(*), min(date), max(date) from read_parquet('{px}')").fetchone()
    print(f"{ev.name}: {n[0]:,} reverse and {n[1]:,} forward splits on {n[2]:,} securities, "
          f"ex-dates {n[3]} .. {n[4]}; {n[5]:,} reverse splits with no declaration date")
    print(f"{px.name}: {m[0]:,} daily rows, {m[1]} .. {m[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
