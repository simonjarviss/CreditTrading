"""Stage what the tax-loss test needs beyond the desk's CEF panel: closing quotes, and PCEF.

    QUANTT_ENV_FILE=<env file> python3 results/ideas/cef_tax_loss_january/stage.py

WHY: `~/quantt_research/crsp_cef_daily.parquet` (scripts/research/stage_crsp_cefs.py) holds
closing prices only. December closes in thin, heavily sold funds are where a close sits on the
bid, and a January close on the ask, so the test must be rescored on the mid of CRSP's closing
bid and ask (`dlybid`, `dlyask`). This pulls those two columns and share volume for the same
rows the panel holds (same filter, so the two files join one to one).

PCEF (Invesco CEF Income Composite ETF, listed 2010) is the tradable proxy for "the CEF
market". Yahoo's adjusted close is a total-return series; only its returns are used.

Licensed rows go to `~/quantt_research/cef_tax_loss_january/`, never into the repository.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = Path.home() / "quantt_research" / "cef_tax_loss_january"


def main() -> int:
    out = OUT.resolve()
    if REPO.resolve() == out or REPO.resolve() in out.parents:
        raise SystemExit(f"refusing {out}: licensed rows stay outside the repository")
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "cef_quotes.parquet"
    tmp = out / "cef_quotes.parquet.part"
    # FIX AFTER THE INTERRUPTION (2026-11-18): the first run was killed during this copy and left
    # a ZERO-BYTE cef_quotes.parquet, which `dest.exists()` accepted as staged. A file that does
    # not open as parquet is rebuilt, and the copy now lands under a .part name and is renamed
    # only once it is complete, so a kill cannot leave a file that looks finished.
    if dest.exists() and dest.stat().st_size == 0:
        dest.unlink()
    if not dest.exists():
        from src.data import r2
        con = r2.connect()
        con.execute(f"""
            copy (
              select permno, dlycaldt as date, cast(dlybid as double) as bid, cast(dlyask as double) as ask,
                     cast(dlyvol as double) as vol
              from read_parquet('{r2.r2_path("crsp_a_stock", "dsf_v2")}')
              where dlycaldt >= date '2000-01-01' and securitysubtype = 'CEF'
                and conditionaltype = 'RW' and tradingstatusflg = 'A'
              order by date, permno
            ) to '{tmp}' (format parquet, compression zstd)""")
        tmp.replace(dest)
        s = con.execute(f"select count(*), min(date), max(date) from read_parquet('{dest}')").fetchone()
        print(f"{dest.name}: {s[0]:,} rows, {s[1]} .. {s[2]}")
    pc = out / "pcef_yf.parquet"
    if not pc.exists():
        import yfinance as yf
        raw = yf.download("PCEF", start="2010-01-01", auto_adjust=False, progress=False, threads=False)
        if raw is None or raw.empty:
            raise SystemExit("Yahoo returned nothing for PCEF")
        if hasattr(raw.columns, "levels"):
            raw.columns = raw.columns.get_level_values(0)
        df = raw[["Close", "Adj Close"]].rename(columns={"Close": "close", "Adj Close": "adj_close"}).reset_index()
        df = df.rename(columns={"Date": "date"})
        df["ret_total"] = df["adj_close"].pct_change()
        df["fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        df.to_parquet(pc, index=False)
        print(f"{pc.name}: {len(df):,} rows, {df['date'].min().date()} .. {df['date'].max().date()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
