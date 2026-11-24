"""Nightly closes and volumes for a shadow universe, from Yahoo Finance.

    SHADOW_STATE_DIR=<dir> python3 -m shadow.fetch.yf_px cef_v1 [--days 120]

Writes <state>/panels/<universe>_px.parquet: [date, symbol, close, volume], unadjusted
closes. It is what a signal reads to judge price level and liquidity; the P&L is marked on
the official auction print, not on this (shadow/marks.py).

Rows dated after the last closed session are dropped (`common.last_closed_date`). A symbol
Yahoo returns nothing for is left out and printed; the signal then has no price for it and
cannot hold it. The whole window is refetched each night, so a correction Yahoo makes to an
old bar reaches the panel, and every decision records the hash of the panel it read.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

import pandas as pd

from . import common


def fetch(symbols: list, days: int, last: dt.date) -> pd.DataFrame:
    import yfinance as yf
    raw = yf.download(symbols, start=(last - dt.timedelta(days=days)).isoformat(),
                      end=(last + dt.timedelta(days=1)).isoformat(),
                      auto_adjust=False, progress=False, group_by="column", threads=False)
    if raw is None or raw.empty:
        raise RuntimeError("Yahoo returned no rows at all")
    out = (raw["Close"].stack().rename("close").to_frame()
           .join(raw["Volume"].stack().rename("volume")).reset_index())
    out.columns = ["date", "symbol", "close", "volume"]
    out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None)
    out = out.dropna(subset=["close"])
    return out[out["date"].dt.date <= last].sort_values(["date", "symbol"]).reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("universe")
    ap.add_argument("--days", type=int, default=120)
    a = ap.parse_args(argv)
    syms = common.universe(a.universe)
    last = common.last_closed_date()
    df = fetch(syms, a.days, last)
    missing = sorted(set(syms) - set(df["symbol"]))
    path = common.write(df, f"{a.universe}_px.parquet")
    print(f"{path.name}: {len(df):,} rows, {df['date'].min().date()} .. {df['date'].max().date()}, "
          f"{df['symbol'].nunique()} of {len(syms)} symbols" + (f"; none for {missing}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
