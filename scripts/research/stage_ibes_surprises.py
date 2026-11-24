"""Stage US quarterly earnings surprises from the R2 IBES mirror, linked to CRSP, for research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_ibes_surprises.py [--start 1999-06-01]

WHY: `pead_wide` (results/ideas/2026-11-10_hunt_all.md, card 3) needs, for every earnings
announcement, the surprise against the estimates as they stood BEFORE the announcement, and
the time of day it was released. IBES's surprise summary (`tr_ibes.surpsum`) holds the
first two: `surpmean` and `surpstdev` are the consensus before the release, and `suescore`
is (actual - surpmean) / surpstdev. The time of day is on the actuals file
(`tr_ibes.act_epsus.anntims`).

WHAT THE TEST MUST KNOW ABOUT THE TIME: `anntims` is never null but 00:00:00 is a
placeholder, common before 2000 and rare after 2005
(results/events/ssx/ssx_data/R2_FULL_INVENTORY_2026-10-19.md). This stage keeps the raw time
and a flag; the test decides what a placeholder means (it treats it as after the close, the
later of the two readings).

THE LINK: `wrdsapps_link_crsp_ibes.ibcrsphist`, scores 1 and 2 only (a CUSIP match, with or
without matching dates), and the announcement date inside the link's date range. An IBES
ticker that maps to two permnos on one date is dropped and counted, never picked between.

WHERE IT WRITES: `~/quantt_research/ibes_eps_surprises.parquet`. IBES rows are licensed:
they never go into the repository (docs/TEAM.md section 5), and never under `data/`.
Read-only at R2. Prints counts and date ranges; nothing row-level.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="1999-06-01")
    ap.add_argument("--out", type=Path, default=Path.home() / "quantt_research")
    a = ap.parse_args(argv)
    out = a.out.expanduser().resolve()
    data = (REPO / "data").resolve()
    if out == data or data in out.parents or REPO.resolve() in out.parents:
        raise SystemExit(f"refusing {out}: licensed rows stay outside the repository and data/")
    out.mkdir(parents=True, exist_ok=True)
    from src.data import r2
    con = r2.connect()
    sur, act, lnk = (r2.r2_path("tr_ibes", "surpsum"), r2.r2_path("tr_ibes", "act_epsus"),
                     r2.r2_path("wrdsapps_link_crsp_ibes", "ibcrsphist"))
    dest = out / "ibes_eps_surprises.parquet"
    con.execute(f"""
        create temp table s as
          select ticker, cast(pyear as int) as pyear, cast(pmon as int) as pmon, anndats,
                 actual, surpmean, surpstdev, suescore
          from read_parquet('{sur}')
          where measure = 'EPS' and fiscalp = 'QTR' and usfirm = 1 and anndats >= cast(? as date)
                and suescore is not null""", [a.start])
    n_raw = con.execute("select count(*) from s").fetchone()[0]
    # one time per (ticker, fiscal quarter, announcement date); the earliest if the file repeats it
    con.execute(f"""
        create temp table t as
          select ticker, year(pends) as pyear, month(pends) as pmon, anndats, min(anntims) as anntims
          from read_parquet('{act}')
          where measure = 'EPS' and pdicity = 'QTR' and usfirm = 1 and anndats >= cast(? as date)
          group by 1, 2, 3, 4""", [a.start])
    con.execute(f"""
        create temp table j as
          select s.*, t.anntims, cast(l.permno as bigint) as permno
          from s join t using (ticker, pyear, pmon, anndats)
                 join read_parquet('{lnk}') l
                   on l.ticker = s.ticker and l.score <= 2 and s.anndats between l.sdate and l.edate""")
    n_join = con.execute("select count(*) from j").fetchone()[0]
    # ambiguous: one IBES ticker-quarter on two permnos, or one permno with two rows on one date
    con.execute("""
        create temp table k as
          select * from j
          qualify count(*) over (partition by ticker, pyear, pmon, anndats) = 1
              and count(*) over (partition by permno, anndats) = 1""")
    con.execute(f"""copy (select permno, anndats, anntims, (anntims = time '00:00:00') as time_is_placeholder,
                                 pyear, pmon, actual, surpmean, surpstdev, suescore
                          from k order by anndats, permno)
                    to '{dest}' (format parquet, compression zstd)""")
    r = con.execute(f"""select count(*), min(anndats), max(anndats), count(distinct permno),
                               avg(case when time_is_placeholder then 1.0 else 0 end),
                               avg(case when not time_is_placeholder and anntims >= time '16:00:00' then 1.0 else 0 end)
                        from read_parquet('{dest}')""").fetchone()
    print(f"surprise rows from {a.start}: {n_raw:,}; with a time and a CRSP link: {n_join:,}; "
          f"kept after dropping ambiguous links: {r[0]:,}")
    print(f"{dest.name}: {r[1]} .. {r[2]}, {r[3]:,} stocks, placeholder time {r[4]:.1%}, "
          f"at or after 16:00 {r[5]:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
