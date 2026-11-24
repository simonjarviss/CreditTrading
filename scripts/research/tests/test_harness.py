"""The research harness: one lag, refusals where the old line booked zero, and
the target builders other families now share.

Each test was checked to FAIL against the behaviour it guards before it was kept:
- the foresight tests, against EXEC_LAG = 1;
- the NaN tests, against the pre-2026-10-27 body of evaluate(), which booked zero;
- the label test, against `R.shift(-1)`;
- the truncation test, against a centred rolling mean.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research import harness as hz  # noqa: E402


def _panel(n=3000, k=6, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2004-01-01", periods=n)
    cols = [f"N{i}" for i in range(k)]
    R = pd.DataFrame(rng.normal(0, 0.01, (n, k)), index=idx, columns=cols)
    H = pd.DataFrame(rng.normal(0, 0.1, (n, k)), index=idx, columns=cols)
    return H, R


def _old_evaluate(H, R):
    """The body of band_frontier.evaluate before 2026-10-27, verbatim."""
    pnl = (H.shift(2).fillna(0.0) * R).sum(axis=1)
    turn = H.diff().abs().sum(axis=1).fillna(0.0)
    gross_v = H.abs().sum(axis=1).mean()
    return dict(gross_sr=pnl.mean() / pnl.std() * np.sqrt(252), ann_ret=pnl.mean() * 252,
                vol=pnl.std() * np.sqrt(252), turn=turn.sum() * 252 / len(pnl),
                hold=gross_v / turn.mean() if turn.mean() > 0 else np.inf,
                turn_series=turn, pnl=pnl)


def test_lag_is_two_and_validate_agrees():
    from scripts.cef import validate as V
    assert hz.EXEC_LAG == 2
    assert V.EXEC_LAG == hz.EXEC_LAG


def test_evaluate_is_the_old_body_value_for_value():
    H, R = _panel()
    new, old = hz.evaluate(H, R), _old_evaluate(H, R)
    assert set(new) == set(old)
    for k in old:
        if isinstance(old[k], pd.Series):
            assert old[k].equals(new[k]), k
        else:
            assert old[k] == new[k], k


def test_band_frontier_delegates_here():
    from scripts.cef import band_frontier as bf
    H, R = _panel(400)
    a, b = bf.evaluate(H, R), hz.evaluate(H, R)
    assert a["pnl"].equals(b["pnl"]) and a["gross_sr"] == b["gross_sr"]
    assert bf.HOLDOUT_START is hz.HOLDOUT_START


def test_legacy_policy_is_the_old_body_even_on_nan_and_misaligned_frames():
    """band_frontier.evaluate's callers include E1, which leaves checked CRSP
    gaps NaN on purpose, and scripts that pass R with extra columns. The legacy
    policy must reproduce the old body on exactly those inputs."""
    from scripts.cef import band_frontier as bf
    H, R = _panel(300, seed=6)
    H.iloc[40, 2] = np.nan
    R.iloc[50, 1] = np.nan
    R = R.assign(EXTRA=0.001)
    old, new = _old_evaluate(H, R), bf.evaluate(H, R)
    for k in old:
        if isinstance(old[k], pd.Series):
            assert old[k].equals(new[k]), k
        else:
            assert old[k] == new[k], k
    with pytest.raises(ValueError):
        hz.evaluate(H, R)                      # the default refuses the same inputs


def test_tomorrows_return_earns_nothing():
    """A book that knows t+1's return at t is trading on information it can act
    on only at t+1's close, too late to earn it. Under shift(2) it earns noise.
    Under shift(1) it would earn a Sharpe in the tens."""
    _, R = _panel(20000, 4, seed=1)
    H = np.sign(R.shift(-1)).fillna(0.0)
    assert abs(hz.evaluate(H, R)["gross_sr"]) < 0.6


def test_the_credited_return_is_t_plus_two():
    _, R = _panel(20000, 4, seed=2)
    H = np.sign(R.shift(-hz.EXEC_LAG)).fillna(0.0)
    assert hz.evaluate(H, R)["gross_sr"] > 20


def test_nan_weight_raises():
    H, R = _panel(50)
    H.iloc[20, 1] = np.nan
    with pytest.raises(ValueError, match="H holds NaN"):
        hz.evaluate(H, R)


def test_missing_return_on_a_held_name_raises():
    H, R = _panel(50)
    R.iloc[20, 1] = np.nan                    # H.iloc[18, 1] != 0, so it is held
    with pytest.raises(ValueError, match="R is NaN on 1 name-day"):
        hz.evaluate(H, R)


def test_missing_return_on_an_unheld_name_is_fine():
    H, R = _panel(50)
    H.iloc[18, 1] = 0.0
    R.iloc[20, 1] = np.nan
    r = hz.evaluate(H, R)
    assert np.isfinite(r["pnl"]).all()


def test_misaligned_frames_raise():
    H, R = _panel(50)
    with pytest.raises(ValueError, match="share one index"):
        hz.evaluate(H, R.iloc[1:])
    with pytest.raises(ValueError, match="one column set"):
        hz.evaluate(H, R[R.columns[::-1]])


def test_label_is_what_evaluate_credits_row_by_row():
    H, R = _panel(500, seed=3)
    pnl = hz.evaluate(H, R)["pnl"]
    via_label = (H * hz.label(R)).sum(axis=1, min_count=1)
    # row t of via_label is the P&L H[t] earns, booked by evaluate on row t+2
    a = via_label.iloc[:-hz.EXEC_LAG].to_numpy()
    b = pnl.iloc[hz.EXEC_LAG:].to_numpy()
    assert np.allclose(a, b, rtol=0, atol=1e-15)
    assert hz.label(R).iloc[-hz.EXEC_LAG:].isna().all().all()


def test_cost_grid_flags_a_sign_flip():
    res = dict(gross_sr=0.5, ann_ret=0.02, vol=0.04, turn=10.0)
    g = hz.cost_grid(res, (5, 15, 30))         # 0.02 - 10*0.0005 > 0; - 10*0.003 < 0
    assert g["net_sr"][5.0] > 0 > g["net_sr"][30.0]
    assert g["sign_flips"] is True
    assert hz.cost_grid(dict(res, turn=1.0))["sign_flips"] is False


def test_report_splits_fit_holdout_and_eras():
    H, R = _panel(6000, seed=4)                # 2004-01-01 .. ~2027
    rep = hz.report(H, R)
    assert rep["fit"]["end"] < "2023-01-01" <= rep["holdout"]["start"]
    assert rep["fit"]["n"] + rep["holdout"]["n"] == rep["full"]["n"]
    assert list(rep["eras"]) == ["2005-09", "2010-14", "2015-19", "2020-22", "2023-"]
    assert rep["eras"]["2010-14"]["start"] >= "2010-01-01"
    assert set(rep["full"]["net_sr"]) == {5.0, 15.0, 30.0}


def test_cross_sectional_weights_are_neutral_and_gross_one():
    H, _ = _panel(100)
    elig = pd.DataFrame(True, index=H.index, columns=H.columns)
    for scheme in ("rank", "z"):
        W = hz.cross_sectional_weights(H, elig, direction=-1, scheme=scheme, min_names=3, on_thin="flat")
        assert np.allclose(W.sum(axis=1), 0, atol=1e-12)
        assert np.allclose(W.abs().sum(axis=1), 1, atol=1e-12)
    # direction -1 is long the lowest signal (the CEF sleeve: long the cheapest fund)
    W = hz.cross_sectional_weights(H, elig, direction=-1, scheme="z", min_names=3, on_thin="flat")
    t = H.index[10]
    assert W.loc[t].idxmax() == H.loc[t].idxmin()


def test_cross_sectional_thin_rows_follow_the_stated_rule():
    H, _ = _panel(10, k=4)
    elig = pd.DataFrame(True, index=H.index, columns=H.columns)
    elig.iloc[5] = [True, False, False, False]
    flat = hz.cross_sectional_weights(H, elig, direction=1, scheme="rank", min_names=2, on_thin="flat")
    hold = hz.cross_sectional_weights(H, elig, direction=1, scheme="rank", min_names=2, on_thin="hold")
    assert (flat.iloc[5] == 0).all()
    assert hold.iloc[5].equals(hold.iloc[4])
    with pytest.raises(TypeError):
        hz.cross_sectional_weights(H, elig.astype(float), direction=1, scheme="rank",
                                   min_names=2, on_thin="flat")


def test_event_weights_rows_sizes_and_refusals():
    idx = pd.bdate_range("2020-01-01", periods=20)
    ev = pd.DataFrame({"decided": [idx[2], idx[3], idx[3]], "ticker": ["A", "A", "B"], "side": [1, 1, -1]})
    W = hz.event_weights(ev, idx, ["A", "B", "C"], hold=3, sizing="fixed", unit=0.1)
    assert W["A"].iloc[2] == pytest.approx(0.1) and W["A"].iloc[3] == pytest.approx(0.2)
    assert W["A"].iloc[5] == pytest.approx(0.1) and W["A"].iloc[6] == 0.0
    assert W["B"].iloc[3:6].eq(-0.1).all() and W["C"].eq(0).all()
    ct = hz.event_weights(ev, idx, ["A", "B", "C"], hold=3, sizing="calendar_time")
    live = ct.abs().sum(axis=1)
    assert np.allclose(live[live > 0], 1.0)
    with pytest.raises(ValueError, match="non-session"):
        hz.event_weights(ev.assign(decided=pd.Timestamp("2020-01-04")), idx, ["A", "B", "C"],
                         hold=3, sizing="fixed", unit=0.1)
    with pytest.raises(ValueError, match="outside the column set"):
        hz.event_weights(ev, idx, ["A"], hold=3, sizing="fixed", unit=0.1)


def test_truncation_check_passes_a_causal_builder_and_catches_a_leak():
    _, R = _panel(400, k=3, seed=5)

    def causal(end):
        x = R if end is None else R.loc[:end]
        return x.rolling(20).mean().shift(1)

    def leaky(end):
        x = R if end is None else R.loc[:end]
        return x.rolling(21, center=True).mean()

    probes = R.index[[100, 250, 380]]
    assert hz.truncation_check(causal, probes)["passed"]
    with pytest.raises(hz.LookaheadError, match="reads the future"):
        hz.truncation_check(leaky, probes)


# --- quant-reviewer findings, 2026-10-28: each test reproduces the reviewer's failing input ---

def test_truncation_check_refuses_a_builder_that_ignores_end():
    _, R = _panel(400, k=3, seed=5)
    ignores = lambda end: R.rolling(21, center=True).mean()      # never truncates
    with pytest.raises(hz.LookaheadError, match="ignores `end`"):
        hz.truncation_check(ignores, R.index[[100, 250]])


def test_truncation_check_refuses_no_probes():
    _, R = _panel(100, k=3)
    with pytest.raises(ValueError, match="no probes"):
        hz.truncation_check(lambda end: R if end is None else R.loc[:end], [])


def test_truncation_check_compares_columns_the_cut_lacks():
    """A name that lists later, back-filled into the probe row, used to escape
    comparison because the cut has no such column."""
    _, R = _panel(400, k=3, seed=5)
    R = R.copy()
    R.iloc[:301, 2] = np.nan                                     # name N2 lists at row 301

    def leaky(end):
        x = R if end is None else R.loc[:end]
        x = x.dropna(axis=1, how="all")
        return np.sign(x.rolling(5).mean().bfill())

    with pytest.raises(hz.LookaheadError, match="no such column"):
        hz.truncation_check(leaky, [R.index[250]])


def test_an_infinite_signal_is_refused_not_zeroed():
    H, _ = _panel(10, k=4)
    elig = pd.DataFrame(True, index=H.index, columns=H.columns)
    H.iloc[2, 1] = np.inf
    for on_thin in ("flat", "hold"):
        with pytest.raises(ValueError, match="infinite"):
            hz.cross_sectional_weights(H, elig, direction=1, scheme="z", min_names=2, on_thin=on_thin)


def test_calendar_time_gross_is_one_after_netting():
    idx = pd.bdate_range("2020-01-01", periods=10)
    ev = pd.DataFrame({"decided": [idx[2]] * 3, "ticker": ["A", "A", "B"], "side": [1, -1, 1]})
    W = hz.event_weights(ev, idx, ["A", "B"], hold=3, sizing="calendar_time")
    assert W["A"].iloc[2:5].eq(0).all() and W["B"].iloc[2:5].eq(1.0).all()
    cancel = pd.DataFrame({"decided": [idx[2]] * 2, "ticker": ["A", "A"], "side": [1, -1]})
    assert hz.event_weights(cancel, idx, ["A", "B"], hold=3, sizing="calendar_time").eq(0).all().all()
