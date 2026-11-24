"""The shared Explore report: figures are right on a series worked by hand, a NaN is
refused, and a short era is not reported. Synthetic data: this tests the code."""
import numpy as np
import pandas as pd
import pytest

from scripts.research import explore


def _pnl(n=600, seed=0):
    idx = pd.bdate_range("2019-01-01", periods=n)
    return pd.Series(np.random.default_rng(seed).normal(0.0004, 0.01, n), index=idx)


def test_stats_on_a_series_worked_by_hand():
    s = pd.Series([0.01, 0.0, -0.02, 0.03], index=pd.bdate_range("2024-01-01", periods=4))
    r = explore.stats(s)
    assert r["n_days"] == 4 and r["n_active_days"] == 3
    assert r["ann_ret"] == pytest.approx(0.005 * 252)
    assert r["sharpe"] == pytest.approx(0.005 / s.std() * np.sqrt(252))
    assert r["hit_rate_active_days"] == pytest.approx(2 / 3)
    assert r["max_drawdown"] == pytest.approx(-0.02)        # 0.01 -> -0.01
    assert r["mean_bp_per_active_day"] == pytest.approx(0.02 / 3 * 1e4)


def test_a_nan_is_refused_not_skipped():
    s = _pnl()
    s.iloc[10] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        explore.stats(s)


def test_halves_cover_the_sample_and_a_short_era_is_left_out():
    s = _pnl()                                           # 2019-01 to 2021-04
    res = explore.summarise(s, controls={"flat": s * 0.0})
    assert res["early_half"]["n_days"] + res["late_half"]["n_days"] == len(s) + 1   # the split day is in both
    assert "2016-2019" in res["eras"] and "2020-2021" in res["eras"]
    assert not any(k.startswith("2023") for k in res["eras"])
    assert res["controls"]["flat"]["sharpe"] is None     # zero variance: no ratio, not zero
    assert "| full |" in explore.table(res)
