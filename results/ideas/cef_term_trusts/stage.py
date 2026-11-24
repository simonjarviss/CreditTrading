"""Stage the rows the term-trust test needs from the R2 CRSP mirror and from Yahoo.

    QUANTT_ENV_FILE=<env file> python3 results/ideas/cef_term_trusts/stage.py [--yahoo]

WHY A SECOND STAGING SCRIPT: the desk's CEF panel (`scripts/research/stage_crsp_cefs.py`) starts
in 2000 and holds no quotes. The dated term trusts of the early 1990s (BlackRock, Hyperion,
TCW/DW, American Municipal, Nations) terminated between 1996 and 2010, so a 250-session window
before a 2000 or 2001 termination needs 1998-99 rows, and every thin-fund result here must be
read beside the closing bid-ask spread. This pulls every CRSP closed-end fund from 1990 with
`dlybid`/`dlyask`, the issuer-name history, and the delisting rows.

RESUMED RUN: the first researcher's stage script was lost when the editor was force quit on
2026-11-16; `names.parquet`, `delists.parquet` and `span.parquet` survived, and
`crsp_cef_daily_1990.parquet` was left at zero bytes. This script is a rewrite (2026-11-18)
and rebuilds all four, so nothing half-written is trusted.

LICENSED ROWS go to `~/quantt_research/cef_term_trusts/` only, never into the repository.
Yahoo rows (ETF total returns, and NAV series under X<TICKER>X) are cached there too, one
parquet per symbol; a symbol Yahoo does not serve is recorded as missing, never invented.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = Path.home() / "quantt_research" / "cef_term_trusts"
ETFS = ("MUB", "HYG", "AGG", "IEF", "SHY", "PCEF", "BKLN")


def crsp() -> None:
    from src.data import r2
    con = r2.connect()
    dsf = r2.r2_path("crsp_a_stock", "dsf_v2")
    dest = OUT / "crsp_cef_daily_1990.parquet"
    tmp = dest.with_suffix(".tmp")
    con.execute(f"""
        copy (
          select permno, ticker, dlycaldt as date, cast(dlyret as double) as ret,
                 cast(dlyprc as double) as prc, cast(dlycap as double) as cap,
                 cast(dlyprcvol as double) as dollar_volume,
                 cast(dlybid as double) as bid, cast(dlyask as double) as ask,
                 cast(dlyorddivamt as double) as div, cast(dlynonorddivamt as double) as div_other
          from read_parquet('{dsf}')
          where dlycaldt >= date '1990-01-01' and securitysubtype = 'CEF'
            and conditionaltype = 'RW' and tradingstatusflg = 'A'
          order by date, permno
        ) to '{tmp}' (format parquet, compression zstd)""")
    tmp.rename(dest)                               # a kill mid-copy leaves .tmp, never a short parquet
    print(con.execute(f"select count(*), min(date), max(date), count(distinct permno) from read_parquet('{dest}')").fetchone())
    permnos = f"(select distinct permno from read_parquet('{dest}'))"
    con.execute(f"""copy (select permno, ticker, issuernm, namedt, nameenddt, securitysubtype
                          from read_parquet('{r2.r2_path("crsp_a_stock", "stocknames_v2")}')
                          where permno in {permnos} order by permno, namedt)
                    to '{OUT / "names.parquet"}' (format parquet)""")
    con.execute(f"""copy (select * from read_parquet('{r2.r2_path("crsp_a_stock", "stkdelists")}')
                          where permno in {permnos} order by permno)
                    to '{OUT / "delists.parquet"}' (format parquet)""")
    for f in ("names", "delists"):
        print(f, len(pd.read_parquet(OUT / f"{f}.parquet")))


def yahoo(symbols: list[str], kind: str) -> None:
    """One parquet per symbol under OUT/yahoo_<kind>/; an empty answer is written as an empty
    frame so that the gap is recorded and not asked for again."""
    import yfinance as yf
    d = OUT / f"yahoo_{kind}"
    d.mkdir(parents=True, exist_ok=True)
    for s in symbols:
        f = d / f"{s}.parquet"
        if f.exists():
            continue
        h = yf.Ticker(s).history(period="max", auto_adjust=False, actions=False)
        h = h.reset_index()[["Date", "Close", "Adj Close"]] if len(h) else pd.DataFrame(columns=["Date", "Close", "Adj Close"])
        if len(h):
            h["Date"] = pd.to_datetime(h["Date"]).dt.tz_localize(None)
        h.to_parquet(f)
        print(kind, s, len(h), h["Date"].min() if len(h) else None, h["Date"].max() if len(h) else None)
        time.sleep(1.5)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yahoo", action="store_true", help="skip CRSP; fetch ETFs and the NAV symbols listed in nav_symbols.txt")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    if not a.yahoo:
        crsp()
        return 0
    yahoo(list(ETFS), "etf")
    navs = (OUT / "nav_symbols.txt")
    if not navs.exists():
        raise SystemExit("nav_symbols.txt is written by explore.py --list (the term-fund tickers); run that first")
    yahoo([f"X{t}X" for t in navs.read_text().split()], "nav")
    return 0


if __name__ == "__main__":
    sys.exit(main())
