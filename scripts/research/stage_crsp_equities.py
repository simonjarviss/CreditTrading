"""Stage a wide US common-stock daily panel from the R2 CRSP mirror, for research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_crsp_equities.py [--top 1500] [--start 2000-01-01]

WHY: the desk's book has too few independent bets (results/mission/PHASE0_2026-11-09.md),
and the cross-sectional equity ideas in the first hunt need hundreds of names a day. CRSP's
CIZ daily file on R2 (`crsp_a_stock.dsf_v2`) has every US listing with delisted names
included, so a panel built from it has no survivorship in the universe.

THE UNIVERSE, WITH NO LOOKAHEAD: each month, the `--top` largest US-incorporated common
stocks (securitytype EQTY, subtype COM, sharetype NS) with a regular-way, active listing on
NYSE, NYSE American or Nasdaq, ranked on market capitalisation at the PREVIOUS month's last
trading day. A stock's membership in month m therefore uses nothing dated in month m. A
name that delists mid-month stays to its last row: its CRSP return already carries the
delisting return on that row (the CIZ format's `dlyret`).

WHERE IT WRITES: `~/quantt_research/crsp_top<N>_daily.parquet`. CRSP rows are licensed:
they never go into the repository (docs/TEAM.md section 5), and never under `data/`.
Read-only at R2. Prints the row count, date range and names per day; nothing row-level.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

COLS = "permno, ticker, siccd, dlycaldt, dlyret, dlyretx, dlyprc, dlyopen, dlycap, dlyprcvol, dlyorddivamt"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=1500)
    ap.add_argument("--start", default="2000-01-01")
    ap.add_argument("--out", type=Path, default=Path.home() / "quantt_research")
    a = ap.parse_args(argv)
    out = a.out.expanduser().resolve()
    data = (REPO / "data").resolve()
    if out == data or data in out.parents or REPO.resolve() in out.parents:
        raise SystemExit(f"refusing {out}: licensed rows stay outside the repository and data/")
    out.mkdir(parents=True, exist_ok=True)
    from src.data import r2
    con = r2.connect()
    src = r2.r2_path("crsp_a_stock", "dsf_v2")
    dest = out / f"crsp_top{a.top}_daily.parquet"
    # one month of lead-in so the first month has a previous month-end to rank on
    con.execute(f"""
        copy (
          with base as (
            select {COLS}, date_trunc('month', dlycaldt) as m
            from read_parquet('{src}')
            where dlycaldt >= cast(? as date) - interval 1 month
              and securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'NS'
              and usincflg = 'Y' and primaryexch in ('N', 'A', 'Q')
              and conditionaltype = 'RW' and tradingstatusflg = 'A'
          ),
          me as (select permno, m, arg_max(dlycap, dlycaldt) as cap_me from base group by 1, 2),
          rk as (select permno, m + interval 1 month as m_use,
                        rank() over (partition by m order by cap_me desc) as cap_rank
                 from me where cap_me is not null)
          select b.permno, b.ticker, b.siccd, b.dlycaldt as date,
                 cast(b.dlyret as double) as ret, cast(b.dlyretx as double) as retx,
                 cast(b.dlyprc as double) as prc, cast(b.dlyopen as double) as open,
                 cast(b.dlycap as double) as cap, cast(b.dlyprcvol as double) as dollar_volume,
                 cast(b.dlyorddivamt as double) as div, rk.cap_rank
          from base b join rk on b.permno = rk.permno and b.m = rk.m_use
          where rk.cap_rank <= {int(a.top)} and b.dlycaldt >= cast(? as date)
          order by date, permno
        ) to '{dest}' (format parquet, compression zstd)""", [a.start, a.start])
    s = con.execute(f"""select count(*), min(date), max(date), count(distinct permno),
                               count(*) * 1.0 / count(distinct date), sum(case when ret is null then 1 else 0 end)
                        from read_parquet('{dest}')""").fetchone()
    print(f"{dest.name}: {s[0]:,} rows, {s[1]} .. {s[2]}, {s[3]:,} distinct stocks, "
          f"{s[4]:.0f} names a day on average, {s[5]:,} rows with no return")
    return 0


if __name__ == "__main__":
    sys.exit(main())
