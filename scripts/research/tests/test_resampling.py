"""Ledoit-Wolf Boot-TS: the paper's formulas, its p-value convention, and size
measured on synthetic IID data (a check on this code, never on the market).

Checked to fail against:
- the p-value test, against p = #{d* >= d} / M;
- the block-scaling test, against a Psi* that drops the 1/sqrt(b) factor. (The
  b = 1 identity cannot catch that, since 1/sqrt(1) = 1; it pins footnote 9.)

NOT discriminating: the size test passes an UN-studentized bootstrap too (checked
2026-10-28). On IID normal data both are near nominal; the paper's case for
studentizing is fat tails and serial dependence (its t6-VAR and GARCH designs),
which this suite does not simulate. It checks this code's size, not the choice
of method.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research import resampling as rs  # noqa: E402


def _pair(T, rho=0.5, mu=(0.0005, 0.0005), seed=0):
    rng = np.random.default_rng(seed)
    z = rng.multivariate_normal([0, 0], [[1, rho], [rho, 1]], size=T) * 0.01
    return z[:, 0] + mu[0], z[:, 1] + mu[1]


def test_gradient_matches_finite_differences():
    a, b = _pair(500)
    v = rs._v(a, b)
    g = rs._grad(v)
    h = 1e-7
    for k in range(4):
        e = np.zeros(4)
        e[k] = h
        num = (rs._delta(v + e) - rs._delta(v - e)) / (2 * h)
        assert num == pytest.approx(g[k], rel=1e-5)


def test_block_one_psi_star_is_the_sample_covariance():
    """Paper footnote 9: with b = 1 the natural estimator is the plain sample
    covariance of y*. Pinned so a lost 1/sqrt(b) cannot pass."""
    a, b = _pair(300, seed=1)
    rng = np.random.default_rng(3)
    D, S = rs._boot_stats(a, b, 1, 5, rng)
    rng = np.random.default_rng(3)
    I = rs._cbb_index(len(a), 1, 5, rng)
    for m in range(5):
        A, B = a[I[m]], b[I[m]]
        v = rs._v(A, B)
        Y = rs._y(A, B, v)
        g = rs._grad(v)
        s = np.sqrt(g @ (Y.T @ Y / len(A)) @ g / len(A))
        assert S[m] == pytest.approx(s, rel=1e-10)
        assert D[m] == pytest.approx(rs._delta(v), rel=1e-12)


def test_block_sums_are_scaled_by_root_b():
    """On IID data the natural estimator at b = 4 must agree with the plain
    sample covariance on average. Without the 1/sqrt(b) factor it is about 4x
    larger, so S would be about 2x."""
    a, b = _pair(2000, seed=7)
    v = rs._v(a, b)
    g = rs._grad(v)
    Y = rs._y(a, b, v)
    s_iid = np.sqrt(g @ (Y.T @ Y / len(a)) @ g / len(a))
    _, S = rs._boot_stats(a, b, 4, 400, np.random.default_rng(0))
    assert S.mean() == pytest.approx(s_iid, rel=0.1)


def test_p_value_is_eq_9():
    a, b = _pair(400, seed=2)
    r = rs.sharpe_diff(a, b, block=4, M=199, seed=0)
    assert 1 / 200 <= r["p_value"] <= 1
    assert (r["p_value"] * 200) == pytest.approx(round(r["p_value"] * 200))


def test_a_large_difference_is_found():
    a, b = _pair(2000, rho=0.8, mu=(0.002, 0.0), seed=4)
    r = rs.sharpe_diff(a, b, block=4, M=499, seed=0)
    assert r["p_value"] < 0.01 and r["ci"][0] > 0


def test_size_is_near_nominal_on_iid_data():
    """Equal true Sharpe; 300 replications at nominal 5%. The binomial 99.9%
    band for p=0.05, n=300 is about [0.013, 0.10]."""
    rej = 0
    for s in range(300):
        a, b = _pair(250, rho=0.5, seed=100 + s)
        rej += rs.sharpe_diff(a, b, block=2, M=199, seed=s)["p_value"] <= 0.05
    assert 0.013 <= rej / 300 <= 0.10


def test_refusals():
    a, b = _pair(100)
    with pytest.raises(ValueError, match="equal length"):
        rs.sharpe_diff(a, b[:-1], block=2, M=199, seed=0)
    with pytest.raises(ValueError):
        rs.sharpe_diff(a, b, block=0, M=199, seed=0)
    bad = a.copy()
    bad[5] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        rs.sharpe_diff(bad, b, block=2, M=199, seed=0)
    with pytest.raises(ValueError, match="lower limit"):
        rs.calibrate_block(a, b, candidates=[1, 2], K=10, M=99, seed=0)


def test_a_block_longer_than_the_sample_is_refused():
    """T=30, block=40 used to return p = 1/(M+1), a false rejection
    (quant-reviewer, 2026-10-28)."""
    a, b = _pair(30, seed=9)
    with pytest.raises(ValueError, match="complete block"):
        rs.sharpe_diff(a, b, block=40, M=199, seed=0)
    with pytest.raises(ValueError, match="complete block"):
        rs.sharpe_diff(a, b, block=8, M=199, seed=0)          # 3 blocks < 4
