"""Stage companies priced near or below their net cash: month-end signals and daily rows. Research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_comp_net_cash.py

WHY: the niche hunt of 2026-11-15 (results/ideas/2026-11-15_niche_hunt.md) proposed buying
small biotechs priced below their cash, and its skeptic answered that this may be biotech
beta in a bear market. The general version is older than the hunt: a company whose market
value is less than its cash after every debt is, on paper, being given away. It lives only
in very small companies, which is the team lead's brief of 2026-11-15. The desk has the
data to read it point-in-time: Compustat quarterly balance sheets with their report dates,
the CRSP link, and CRSP prices with delisting returns.

WHAT IT BUILDS, fixed before any return was read:
  balance   Compustat `fundq` (INDL / STD / C / D, US dollars) from --start: cash and
            short-term investments (cheq), debt (dlttq + dlcq, a missing component counted as
            zero only when the other is present), total liabilities (ltq). Each quarter is
            usable from its REPORT DATE `rdq`, never from the quarter end; a quarter with no
            rdq is dropped.
  link      CCM `ccmxpf_lnkhist`, link types LU and LC, primary P or C, valid on the
            quarter end.
  month     for every CRSP US common share (EQTY / COM / NS, US incorporated), the last
            trading day of each month: market value, price, SIC code.
  signal    at each month end, the latest quarter with rdq on or before that day and not
            more than 200 days old: net_cash = cheq - debt; net_cash_strict = cheq - ltq;
            both over that day's market value.
  rows      daily rows, with CRSP's delisting-inclusive return, for every security whose
            net cash was ever at least half its market value (the book's names and the
            near misses that serve as its control).
WHERE IT WRITES: `~/quantt_research/comp_net_cash_monthly.parquet` (one row per security
and month with a usable quarter and a ratio of 0.25 or more) and
`crsp_net_cash_daily.parquet`. Licensed rows: never in the repository. Read-only at R2.
Prints counts only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
COMMON = "securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'NS' and usincflg = 'Y'"
MAX_AGE_DAYS = 200


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="1999-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--out", type=Path, default=Path.home() / "quantt_research")
    a = ap.parse_args(argv)
    out = a.out.expanduser().resolve()
    if REPO.resolve() == out or REPO.resolve() in out.parents:
        raise SystemExit(f"refusing {out}: licensed rows stay outside the repository")
    out.mkdir(parents=True, exist_ok=True)
    from src.data import r2
    con = r2.connect()
    fq, lk, dsf = (r2.r2_path("comp_na_daily_all", "fundq"), r2.r2_path("crsp_a_ccm", "ccmxpf_lnkhist"),
                   r2.r2_path("crsp_a_stock", "dsf_v2"))
    con.execute(f"""
        create temp table bal as
          select cast(l.lpermno as integer) as permno, f.gvkey, f.datadate, f.rdq,
                 cast(f.cheq as double) as cash,
                 case when f.dlttq is null and f.dlcq is null then null
                      else coalesce(cast(f.dlttq as double), 0) + coalesce(cast(f.dlcq as double), 0) end as debt,
                 cast(f.ltq as double) as liabilities
          from read_parquet('{fq}') f join read_parquet('{lk}') l
            on l.gvkey = f.gvkey and l.linktype in ('LU', 'LC') and l.linkprim in ('P', 'C')
           and f.datadate >= l.linkdt and (l.linkenddt is null or f.datadate <= l.linkenddt)
          where f.indfmt = 'INDL' and f.datafmt = 'STD' and f.consol = 'C' and f.popsrc = 'D' and f.curcdq = 'USD'
            and f.rdq is not null and f.cheq is not null and f.datadate >= cast(? as date) - interval 200 day
            and f.rdq >= f.datadate""", [a.start])
    con.execute(f"""
        create temp table mon as
          select permno, max(dlycaldt) as date, arg_max(cast(dlycap as double), dlycaldt) as cap,
                 arg_max(cast(dlyprc as double), dlycaldt) as prc, arg_max(siccd, dlycaldt) as siccd
          from read_parquet('{dsf}')
          where dlycaldt between cast(? as date) and cast(? as date) and {COMMON} and dlycap is not null
          group by permno, date_trunc('month', dlycaldt)""", [a.start, a.end])
    # ALIGNMENT: a quarter is joined to a month end only if its report date is on or before it.
    con.execute(f"""
        create temp table sig as
          select m.permno, m.date, m.cap, m.prc, m.siccd, b.datadate, b.rdq, b.cash, b.debt, b.liabilities
          from mon m asof join bal b on b.permno = m.permno and b.rdq <= m.date
          where m.date - b.rdq <= {MAX_AGE_DAYS} and m.cap > 0""")
    assert con.execute("select count(*) from sig where rdq > date").fetchone()[0] == 0
    mp, dp = out / "comp_net_cash_monthly.parquet", out / "crsp_net_cash_daily.parquet"
    # CRSP market value is in $ thousands, Compustat items in $ millions.
    con.execute(f"""
        copy (select *, (cash - debt) * 1000 / cap as net_cash_to_cap, (cash - liabilities) * 1000 / cap as strict_to_cap
              from sig where debt is not null and (cash - debt) * 1000 / cap >= 0.25 order by date, permno)
        to '{mp}' (format parquet)""")
    con.execute(f"""
        copy (select x.permno, x.dlycaldt as date, cast(x.dlyret as double) as ret, cast(x.dlyprc as double) as prc,
                     cast(x.dlyprcvol as double) as dollar_volume, cast(x.dlycap as double) as cap, x.dlydelflg as delflg
              from read_parquet('{dsf}') x
              where x.permno in (select distinct permno from sig where debt is not null and (cash - debt) * 1000 / cap >= 0.5)
                and x.dlycaldt between cast(? as date) and cast(? as date) order by date, permno)
        to '{dp}' (format parquet, compression zstd)""", [a.start, a.end])
    n = con.execute("select count(*), count(distinct permno) from sig").fetchone()
    k = con.execute(f"""select count(*), count(distinct permno), count(*) filter (where net_cash_to_cap >= 1),
                               count(distinct permno) filter (where net_cash_to_cap >= 1),
                               count(*) filter (where strict_to_cap >= 1), min(date), max(date) from read_parquet('{mp}')""").fetchone()
    by = con.execute(f"select year(date), count(distinct permno) from read_parquet('{mp}') where net_cash_to_cap >= 1 group by 1 order by 1").fetchall()
    d = con.execute(f"select count(*), count(distinct permno), max(date) from read_parquet('{dp}')").fetchone()
    print(f"month ends with a usable quarter: {n[0]:,} on {n[1]:,} securities")
    print(f"{mp.name}: {k[0]:,} rows (ratio >= 0.25) on {k[1]:,} securities, {k[5]} .. {k[6]}; net cash >= market value on "
          f"{k[2]:,} rows / {k[3]:,} securities; cash above ALL liabilities and market value on {k[4]:,} rows")
    print("securities below net cash, by year:", ", ".join(f"{y}: {c}" for y, c in by))
    print(f"{dp.name}: {d[0]:,} daily rows on {d[1]:,} securities, to {d[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
