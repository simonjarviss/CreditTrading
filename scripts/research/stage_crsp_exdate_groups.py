"""Stage daily CRSP panels for three more groups of dividend payers, for research only.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_crsp_exdate_groups.py

WHY: closed-end funds keep falling for three sessions after an ex-date
(results/ideas/2026-11-10_cef_exdate_drift.md). The team lead asked on 2026-11-11 for event
ideas in every asset class, and the first question is whether that pattern is a closed-end
fund quirk or belongs to income wrappers in general. This stages the groups CRSP can tell
apart, with dead securities included:
  etf    securitytype FUND, subtype ETF
  reit   common shares (EQTY / COM / NS) with SIC code 6798
  units  EQTY / COM with sharetype UG (partnership and trust units)
Ordinary common stocks need no new panel: `crsp_top2000_daily.parquet` already carries the
distribution column (scripts/research/stage_crsp_equities.py).
The groups were fixed from CRSP's own type codes before any return was read. A security
that never paid an ordinary distribution in the window is left out: it can be neither an
event nor a useful control, and leaving it out keeps the ETF panel small.

WHERE IT WRITES: `~/quantt_research/crsp_exdate_<group>_daily.parquet`. CRSP rows are
licensed: never in the repository, never under `data/`. Read-only at R2. Prints counts only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

GROUPS = {
    "etf": "securitytype = 'FUND' and securitysubtype = 'ETF'",
    "reit": "securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'NS' and siccd = 6798",
    "units": "securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'UG'",
}


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
    src = r2.r2_path("crsp_a_stock", "dsf_v2")
    for g, where in GROUPS.items():
        dest = out / f"crsp_exdate_{g}_daily.parquet"
        con.execute(f"""
            copy (
              with base as (
                select permno, ticker, siccd, dlycaldt as date,
                       cast(dlyret as double) as ret, cast(dlyprc as double) as prc,
                       cast(dlyprcvol as double) as dollar_volume, cast(dlyorddivamt as double) as div
                from read_parquet('{src}')
                where dlycaldt >= cast(? as date) and {where}
                  and conditionaltype = 'RW' and tradingstatusflg = 'A'
              )
              select * from base
              where permno in (select permno from base where div > 0)
              order by date, permno
            ) to '{dest}' (format parquet, compression zstd)""", [a.start])
        s = con.execute(f"""select count(*), min(date), max(date), count(distinct permno),
                                   sum(case when div > 0 then 1 else 0 end)
                            from read_parquet('{dest}')""").fetchone()
        print(f"{dest.name}: {s[0]:,} rows, {s[1]} .. {s[2]}, {s[3]:,} securities, {s[4]:,} ex-dates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
