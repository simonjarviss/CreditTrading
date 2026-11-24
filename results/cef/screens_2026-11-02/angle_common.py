"""Shared plumbing for the 2026-11-02 unique-angle screens (zero trials).

WHY A FIT-ONLY PANEL COPY. The brief for these screens is "fit data only for any
return test (<= 2022-12-30, asserted)". Slicing T and R after `build_targets()` would
honour that in what is reported, but the 2023+ returns would still be computed in
memory. Instead every live panel the harness reads (prices, NAV, distributions,
splits) is copied here truncated at FIT_END, and `band_frontier.DATA_DIR` is pointed
at the copy for the duration of the build -- the same switch trial C5 used for its
frozen panels (band_frontier.py, DATA_DIR docstring). So no 2023+ price or NAV ever
enters the harness, and `assert_fit` checks every frame a screen reports from.

The copies go under `_cache_fit/` (gitignored: results/**/_cache_*). Nothing is
written under data/ (landmine 9).

THE BOOK. The unit book of the live policy, read from the frozen spec:
band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS). Trial 53's sizing multiplier is
not applied (the harness builds the unit book; spec.py says so). Screens that quote
"% of capital" say whether they scale by it.
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from scripts.cef import band_frontier as bf                      # noqa: E402
from scripts.cef.spec import (BAND_WIDTH, MAX_GROSS_STRESS,       # noqa: E402
                              SIZING_MULTIPLIER, UNIVERSE, summary)

FIT_END = pd.Timestamp("2022-12-30")
CACHE = HERE / "_cache_fit"
LIVE = REPO / "data" / "cef"

ERAS = (("2005-09", "2005-01-01", "2009-12-31"),
        ("2010-14", "2010-01-01", "2014-12-31"),
        ("2015-19", "2015-01-01", "2019-12-31"),
        ("2020-22", "2020-01-01", "2022-12-30"))


def assert_fit(obj, what: str):
    """Raise if any date in `obj` (index or a date column) is after FIT_END."""
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        idx = obj.index
        if isinstance(idx, pd.DatetimeIndex) and len(idx) and idx.max() > FIT_END:
            raise AssertionError(f"{what}: index reaches {idx.max().date()} > FIT_END {FIT_END.date()}")
        if isinstance(obj, pd.DataFrame):
            for c in ("date", "ex_date", "settlement_date"):
                if c in obj.columns and len(obj) and pd.to_datetime(obj[c]).max() > FIT_END:
                    raise AssertionError(f"{what}: column {c} reaches past FIT_END")
    return obj


def build_fit_cache() -> Path:
    """Write fit-truncated copies of the four panels the harness reads. Idempotent."""
    CACHE.mkdir(exist_ok=True)
    for name, col in (("cef_prices", "date"), ("cef_nav", "date"),
                      ("cef_distributions", "ex_date"), ("cef_splits", "ex_date")):
        src = LIVE / f"{name}.parquet"
        df = pd.read_parquet(src)
        df = df[pd.to_datetime(df[col]) <= FIT_END]
        assert_fit(df, name)
        df.to_parquet(CACHE / f"{name}.parquet", index=False)
    return CACHE


@contextlib.contextmanager
def fit_panels():
    """Point the harness at the fit-only copies, and always point it back."""
    build_fit_cache()
    old = bf.DATA_DIR
    bf.DATA_DIR = CACHE
    try:
        yield CACHE
    finally:
        bf.DATA_DIR = old


def live_book():
    """(T, R_px, R_tr, H, panel) for the deployed universe on fit data only.

    R_px is the harness's default price-return matrix; R_tr adds the distribution
    leg (band_frontier.total_returns). H is the unit book of the live policy."""
    with fit_panels():
        T, R = bf.build_targets()
        R_tr = bf.total_returns(R)
        panel = bf.build_panel()
    for k, v in (("T", T), ("R", R), ("R_tr", R_tr)):
        assert_fit(v, k)
    for k in ("px", "nav", "disc", "z", "ret"):
        assert_fit(panel[k], k)
    if MAX_GROSS_STRESS is None:
        raise RuntimeError("spec has no max_gross_stress; the live policy label says it should")
    H = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)
    return T, R, R_tr, H, panel


def era_of(ts):
    for lab, a, b in ERAS:
        if pd.Timestamp(a) <= ts <= pd.Timestamp(b):
            return lab
    return None


def nw_t(x: pd.Series, lags: int = 5) -> float:
    """Newey-West t of the mean of x (Bartlett kernel)."""
    x = pd.Series(x).dropna().values
    n = len(x)
    if n < 10:
        return float("nan")
    e = x - x.mean()
    s = e @ e / n
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        s += 2 * w * (e[L:] @ e[:-L]) / n
    return float(x.mean() / np.sqrt(s / n))


def ann_sharpe(x: pd.Series) -> float:
    x = pd.Series(x).dropna()
    return float(x.mean() / x.std() * np.sqrt(252)) if x.std() > 0 else float("nan")


SPEC_LINE = summary()
