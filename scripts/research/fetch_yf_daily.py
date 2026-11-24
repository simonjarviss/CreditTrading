"""Fetch daily bars for liquid ETFs from Yahoo Finance into the RESEARCH folder.

    python3 scripts/research/fetch_yf_daily.py SPY IEF TLT [--out <dir>]

WHY: the first hunt (results/ideas/2026-11-10_hunt_all.md) needs long, current histories of
index and Treasury ETFs, and the laptop's panels are months stale and start late (SPY from
2011). The team lead ruled on 2026-11-09 that the agent runs the free-source fetchers into
a research folder (docs/SYSTEM.md section 5).

WHERE IT WRITES: `<out>/yf_daily.parquet`, default `~/quantt_research`. NEVER under the
repository's `data/`: the live sleeve decides on those panels (CLAUDE.md landmine 9), and
this script refuses an output directory inside it.

WHAT IT STORES, per (date, ticker): `close` (unadjusted), `adj_close` (Yahoo's split- and
dividend-adjusted close), `volume`, `ret_total` = adj_close.pct_change() and `fetched_at`.
Yahoo's adjusted close is a total-return series BY ITS OWN CONSTRUCTION and is re-based on
every dividend, so stored levels change between fetches while the returns do not: use
`ret_total`, never the level. Source note: docs/REFERENCES.md section 12yf.

Today's bar is dropped while the session is open (see `fetch`). A ticker Yahoo returns
nothing for raises, naming it. A file from an earlier fetch is
replaced whole: this is a research cache, not a record.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

REPO = Path(__file__).resolve().parents[2]


def fetch(tickers: list, start: str = "1990-01-01") -> pd.DataFrame:
    import yfinance as yf
    frames = []
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for t in tickers:
        raw = yf.download(t, start=start, auto_adjust=False, progress=False, threads=False)
        if raw is None or raw.empty:
            raise RuntimeError(f"Yahoo returned no rows for {t}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        df = pd.DataFrame({"date": raw.index.tz_localize(None), "ticker": t, "close": raw["Close"].values,
                           "adj_close": raw["Adj Close"].values, "volume": raw["Volume"].values})
        df = df.dropna(subset=["close", "adj_close"])
        # Yahoo serves TODAY'S bar while the session is still open: a price that is not a
        # close, dated like one (seen on the first run, 2026-11-10 at 11:30 New York). Keep
        # a row only once its session has closed: an earlier date, or today from 16:30.
        ny = dt.datetime.now(ZoneInfo("America/New_York"))
        last_closed = ny.date() if ny.time() >= dt.time(16, 30) else ny.date() - dt.timedelta(days=1)
        df = df[df["date"].dt.date <= last_closed]
        df["ret_total"] = df["adj_close"].pct_change()
        df["fetched_at"] = now
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--out", type=Path, default=Path.home() / "quantt_research")
    a = ap.parse_args(argv)
    out = a.out.expanduser().resolve()
    data = (REPO / "data").resolve()
    if out == data or data in out.parents:
        raise SystemExit(f"refusing {out}: it is inside {data}, which the live sleeve decides on")
    out.mkdir(parents=True, exist_ok=True)
    df = fetch(sorted(set(a.tickers)))
    df.to_parquet(out / "yf_daily.parquet", index=False)
    print(df.groupby("ticker")["date"].agg(["min", "max", "size"]).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
