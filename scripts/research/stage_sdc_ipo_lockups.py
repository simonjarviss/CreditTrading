"""Stage US IPOs with a lock-up expiry date, and each one's first 500 days of prices, for
research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_sdc_ipo_lockups.py

WHY: at an IPO the insiders agree not to sell for a fixed time, usually 180 days, and the
date is in the prospectus. When it ends, supply arrives on a day everyone could have known.
The desk's catalogue listed this (K5, results/events/SPECIAL_SITUATIONS_CATALOGUE_CORP_2026-10-15.md)
and dropped it in October on a count of how many recent IPOs Alpaca would lend, without
reading a return (results/events/SS_DESK_EXPANSION_2026-10-19.md, row K5). The mission brief
(2026-11-09) asks for the gross result first.

WHAT IT SELECTS, fixed before any return was read:
  IPOs    SDC new issues (`tr_sdc_ni.wrds_ni_details`) with ipo = 'Yes', nation United
          States, an IPO date from --start and a lock-up expiry date (`min_lock_date`, the
          earliest when a deal has several). One row per (6-digit CUSIP, IPO date).
  match   a CRSP security with the same 6-digit CUSIP whose FIRST daily row falls on the
          IPO date or within 7 days after it, typed common (EQTY / COM / NS). Units,
          depositary receipts and funds are left out by CRSP's own codes. An IPO with no
          such security is counted and left out.
  panel   each matched security's daily rows for its first 500 calendar days, dead ones
          included.
SDC's lock-up date is the deal date plus the contract's days in 88% of rows (counted
2026-11-15: 4,529 of 5,121 are exactly 180 days), so it is the date the prospectus gave,
not a date learnt afterwards. An early release or an extension is not in this field.

WHERE IT WRITES: `~/quantt_research/sdc_ipo_lockups.parquet` and
`crsp_ipo_lockup_daily.parquet`. SDC and CRSP rows are licensed: never in the repository,
never under `data/`. Read-only at R2. Prints counts only.
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
    ev, px = out / "sdc_ipo_lockups.parquet", out / "crsp_ipo_lockup_daily.parquet"
    n_ipo = con.execute(f"""select count(*) from (select distinct cusip, ipodate from read_parquet('{ni}')
        where ipo = 'Yes' and nation = 'United States' and min_lock_date is not null
          and cusip is not null and ipodate >= cast(? as date))""", [a.start]).fetchone()[0]
    con.execute(f"""
        copy (
          with ipo as (
            select cusip, ipodate, min(min_lock_date) as lock_date, max(proceedsoversold) as proceeds_musd,
                   any_value(exchange) as sdc_exchange
            from read_parquet('{ni}')
            where ipo = 'Yes' and nation = 'United States' and min_lock_date is not null
              and cusip is not null and ipodate >= cast(? as date)
            group by cusip, ipodate),
          first as (
            select permno, min(dlycaldt) as first_date, arg_min(substr(cusip, 1, 6), dlycaldt) as c6,
                   arg_min(securitytype, dlycaldt) as st, arg_min(securitysubtype, dlycaldt) as sst,
                   arg_min(sharetype, dlycaldt) as sh, arg_min(siccd, dlycaldt) as siccd
            from read_parquet('{dsf}') where dlycaldt >= cast(? as date) - interval 40 day group by permno)
          select f.permno, i.cusip, i.ipodate as ipo_date, f.first_date, i.lock_date,
                 date_diff('day', i.ipodate, i.lock_date) as lock_days, i.proceeds_musd, i.sdc_exchange, f.siccd
          from ipo i join first f
            on f.c6 = i.cusip and f.first_date between i.ipodate and i.ipodate + interval 7 day
          where f.st = 'EQTY' and f.sst = 'COM' and f.sh = 'NS'
          order by i.ipodate, f.permno
        ) to '{ev}' (format parquet)""", [a.start, a.start])
    con.execute(f"""
        copy (
          select d.permno, d.ticker, d.dlycaldt as date, cast(d.dlyret as double) as ret,
                 cast(d.dlyprc as double) as prc, cast(d.dlyprcvol as double) as dollar_volume,
                 cast(d.dlycap as double) as cap
          from read_parquet('{dsf}') d join read_parquet('{ev}') e on e.permno = d.permno
          where d.dlycaldt between e.first_date and e.first_date + interval 500 day
          order by d.permno, d.dlycaldt
        ) to '{px}' (format parquet)""")
    n = con.execute(f"""select count(*), count(distinct permno), count(distinct cusip), min(ipo_date), max(ipo_date),
                               count(*) filter (where lock_days = 180) from read_parquet('{ev}')""").fetchone()
    m = con.execute(f"select count(*), min(date), max(date) from read_parquet('{px}')").fetchone()
    print(f"SDC: {n_ipo:,} US IPOs with a lock-up date from {a.start}")
    print(f"{ev.name}: {n[0]:,} matched to a CRSP common share ({n[1]:,} securities, {n[2]:,} CUSIPs), "
          f"IPO dates {n[3]} .. {n[4]}; {n[5]:,} with a 180-day lock-up")
    print(f"{px.name}: {m[0]:,} daily rows, {m[1]} .. {m[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
