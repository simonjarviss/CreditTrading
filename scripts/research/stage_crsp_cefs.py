"""Stage every US-listed closed-end fund's daily rows from the R2 CRSP mirror, for research.

    QUANTT_ENV_FILE=<env file> python3 scripts/research/stage_crsp_cefs.py [--start 2000-01-01]

WHY: the desk's CEF ideas were tested on the funds alive today (13 to 74 names), which is
both narrow and survivorship-biased (docs/SYSTEM.md section 2, "Survivorship"). CRSP's CIZ
daily file tags closed-end funds (`securitysubtype = 'CEF'`) and keeps every fund that ever
listed, with its delisting return on its last row and each ordinary distribution on its
ex-date (`dlyorddivamt`). So one pull gives a full, dead-funds-included universe for the
ex-date and tax-loss ideas of the first hunt.

NO NAV: CRSP has prices and distributions only. Anything that needs a discount still needs
the NAV panels. Read-only at R2; rows go to `~/quantt_research/crsp_cef_daily.parquet`,
never into the repository or `data/` (licensed rows, docs/TEAM.md section 5).
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
    dest = out / "crsp_cef_daily.parquet"
    con.execute(f"""
        copy (
          select permno, ticker, siccd, primaryexch, dlycaldt as date,
                 cast(dlyret as double) as ret, cast(dlyretx as double) as retx,
                 cast(dlyprc as double) as prc, cast(dlycap as double) as cap,
                 cast(dlyprcvol as double) as dollar_volume,
                 cast(dlyorddivamt as double) as div, cast(dlynonorddivamt as double) as div_other
          from read_parquet('{r2.r2_path("crsp_a_stock", "dsf_v2")}')
          where dlycaldt >= cast(? as date) and securitysubtype = 'CEF'
            and conditionaltype = 'RW' and tradingstatusflg = 'A'
          order by date, permno
        ) to '{dest}' (format parquet, compression zstd)""", [a.start])
    s = con.execute(f"""select count(*), min(date), max(date), count(distinct permno),
                               count(*) * 1.0 / count(distinct date), sum(case when div > 0 then 1 else 0 end)
                        from read_parquet('{dest}')""").fetchone()
    print(f"{dest.name}: {s[0]:,} rows, {s[1]} .. {s[2]}, {s[3]:,} distinct funds, "
          f"{s[4]:.0f} funds a day on average, {s[5]:,} ex-dates with an ordinary distribution")
    return 0


if __name__ == "__main__":
    sys.exit(main())
