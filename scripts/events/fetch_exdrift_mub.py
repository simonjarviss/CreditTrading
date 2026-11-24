"""MUB daily closes and distributions from yfinance, for the ex-date drift trial's D4 MUNI factor (DG-X6).

    python3 scripts/events/fetch_exdrift_mub.py                    # MUB, 2007-09-01 to today
    python3 scripts/events/fetch_exdrift_mub.py --symbols MUB,IEF,HYG

WHY THIS EXISTS (EVENTS trial 3, approved 2026-10-27)
-----------------------------------------------------
Stage 5 of `results/events/PREREG_EXDATE_DRIFT_2026-10-26.md` regresses the sleeve on
MUNI = MUB - IEF among its D4 factors, and DG-X6 requires every factor to cover the test window.
MUB is not in `data/etf_daily.parquet` [V, 2026-10-27], and CLAUDE.md forbids a hand-copied
series: anything fetched gets a fetcher and a source note (`docs/REFERENCES.md`, row
"MUB daily closes and distributions (yfinance)").

WHAT IT FETCHES. `yfinance.Ticker(sym).history(start, end, auto_adjust=False, actions=True)`:
the raw `Close` (split-adjusted as of the fetch, not dividend-adjusted), `Adj Close`, `Volume`,
`Dividends` and `Stock Splits`, one row per session. It writes those columns as they come,
with the fetch time, to the gitignored `results/events/exdrift/_cache_exdrift/`.

WHAT IT DOES NOT DO. It computes no return. The trial's Stage 0 reads the DATES only, to check
coverage of the test window; 2023+ returns are formed once, at the opening, by the trial script.
Nothing is filled or interpolated: a session with no row is a session with no row, and Stage 0
names it. An empty history, a duplicate date, or a non-positive or missing close raises.

Tests: `scripts/events/tests/test_fetch_exdrift_mub.py` (a fake yfinance; no network).
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
CACHE = REPO / "results" / "events" / "exdrift" / "_cache_exdrift"
START = dt.date(2007, 9, 1)            # before MUB's first session (September 2007 [U]); the run prints the first row
COLUMNS = ["date", "ticker", "close", "adj_close", "volume", "dividend", "stock_split"]


class MubFetchError(RuntimeError):
    pass


def out_path(symbol: str) -> Path:
    return CACHE / f"etf_yf_{symbol}.parquet"


def parse_history(h: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """yfinance history -> COLUMNS. Pure. Raises on what it cannot record as it is."""
    need = ["Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]
    if h is None or h.empty:
        raise MubFetchError(f"{symbol}: yfinance returned no history")
    miss = [c for c in need if c not in h.columns]
    if miss:
        raise MubFetchError(f"{symbol}: history lacks {miss} (auto_adjust=False, actions=True expected)")
    idx = pd.DatetimeIndex(h.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    d = idx.normalize()
    if d.duplicated().any():
        raise MubFetchError(f"{symbol}: duplicate session(s) {sorted(set(d[d.duplicated()].date))[:5]}")
    c = pd.to_numeric(h["Close"], errors="coerce").to_numpy()
    if pd.isna(c).any() or (c <= 0).any():
        raise MubFetchError(f"{symbol}: a missing or non-positive close on {list(d[pd.isna(c) | (c <= 0)].date)[:5]}")
    out = pd.DataFrame({"date": d, "ticker": symbol, "close": c,
                        "adj_close": pd.to_numeric(h["Adj Close"], errors="coerce").to_numpy(),
                        "volume": pd.to_numeric(h["Volume"], errors="coerce").to_numpy(),
                        "dividend": pd.to_numeric(h["Dividends"], errors="coerce").to_numpy(),
                        "stock_split": pd.to_numeric(h["Stock Splits"], errors="coerce").to_numpy()})
    return out.sort_values("date").reset_index(drop=True)


def fetch(symbol: str, start: dt.date, end: dt.date, yf=None) -> pd.DataFrame:
    if yf is None:
        import yfinance as yf
    h = yf.Ticker(symbol).history(start=start.isoformat(), end=(end + dt.timedelta(days=1)).isoformat(),
                                  auto_adjust=False, actions=True)
    return parse_history(h, symbol)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--symbols", default="MUB")
    ap.add_argument("--start", type=dt.date.fromisoformat, default=START)
    ap.add_argument("--end", type=dt.date.fromisoformat, default=dt.date.today())
    a = ap.parse_args(argv)
    CACHE.mkdir(parents=True, exist_ok=True)
    t = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for s in [x.strip().upper() for x in a.symbols.split(",") if x.strip()]:
        f = fetch(s, a.start, a.end).assign(fetched_utc=t)
        f.to_parquet(out_path(s), index=False)
        print(f"{s}: {len(f)} sessions {f['date'].min().date()}..{f['date'].max().date()} "
              f"(fetched {t}) -> {out_path(s).relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
