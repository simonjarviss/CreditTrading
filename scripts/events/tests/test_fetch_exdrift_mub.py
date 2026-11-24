"""Tests for scripts/events/fetch_exdrift_mub.py. A fake yfinance; no network."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from scripts.events import fetch_exdrift_mub as m


def _hist(n=3, close=None):
    idx = pd.DatetimeIndex(pd.bdate_range("2023-01-03", periods=n)).tz_localize("America/New_York")
    c = close if close is not None else [100.0 + i for i in range(n)]
    return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Adj Close": c, "Volume": [1e6] * n,
                         "Dividends": [0.0, 0.25, 0.0][:n], "Stock Splits": [0.0] * n}, index=idx)


def test_parse_history_keeps_raw_columns_and_forms_no_return():
    f = m.parse_history(_hist(), "MUB")
    assert list(f.columns) == m.COLUMNS
    assert not any("ret" in c for c in f.columns)
    assert f["date"].dt.tz is None and f["dividend"].iloc[1] == 0.25


@pytest.mark.parametrize("bad", ["empty", "dup", "nonpos", "nan", "cols"])
def test_parse_history_raises_on_what_it_cannot_record(bad):
    h = _hist()
    if bad == "empty":
        h = h.iloc[0:0]
    elif bad == "dup":
        h.index = pd.DatetimeIndex([h.index[0]] * 3)
    elif bad == "nonpos":
        h["Close"] = [1.0, 0.0, 2.0]
    elif bad == "nan":
        h["Close"] = [1.0, np.nan, 2.0]
    else:
        h = h.drop(columns=["Dividends"])
    with pytest.raises(m.MubFetchError):
        m.parse_history(h, "MUB")


def test_fetch_asks_for_unadjusted_history_with_actions():
    seen = {}

    class T:
        def __init__(self, s):
            seen["sym"] = s

        def history(self, **kw):
            seen.update(kw)
            return _hist()

    class YF:
        Ticker = T
    f = m.fetch("MUB", dt.date(2023, 1, 1), dt.date(2023, 1, 31), yf=YF)
    assert seen["sym"] == "MUB" and seen["auto_adjust"] is False and seen["actions"] is True
    assert seen["end"] == "2023-02-01" and len(f) == 3
