"""Tests for the PM seat's arithmetic and the risk-input helpers (synthetic data only).

Run explicitly (the file is not under a `testpaths` directory, deliberately: it is a
research note's helper, and pytest.ini was not edited):
    python3 -m pytest scripts/events/ssx/ssx_pm_test_arithmetic.py
These test the code's behaviour, never a claim about the market.
"""
import math

import numpy as np
import pandas as pd
import pytest

from scripts.events.ssx import ssx_pm_arithmetic as A
from scripts.events.ssx import ssx_pm_risk_inputs as R


def test_entry_bar_nests_both_single_constraint_cases():
    # gross dominates when the sleeve is gross-light relative to rho
    assert A.entry_bar(0.96, 0.0, 1.0, 0.0515, 0.10) == pytest.approx(0.515)
    # vol dominates when rho*IR_c exceeds the gross branch
    assert A.entry_bar(0.96, 0.9, 1.0, 0.0515, 0.50) == pytest.approx(0.864)
    # netting (nu < 1) lowers the gross branch one for one
    assert A.entry_bar(0.96, 0.0, 0.5, 0.0515, 0.10) == pytest.approx(0.2575)


def test_mu_star_is_annual_rate_times_gross_times_hold_plus_round_trip():
    assert A.mu_star_bp(0.0504, 1.0, 252) == pytest.approx(504.0)
    assert A.mu_star_bp(0.0, 2.0, 5, 15) == pytest.approx(60.0)   # 2 legs-in-gross x 2 trades x 15bp
    assert A.edge_per_gross_yr(A.mu_star_bp(0.0515, 2.0, 168), 2.0, 168) == pytest.approx(0.0515)


def test_folded_normal_mean_matches_monte_carlo():
    rng = np.random.default_rng(1)
    for mu, sd in ((0.0, 1.0), (1.0, 1.0), (-2.0, 0.5), (3.0, 2.0)):
        x = rng.normal(mu, sd, 400_000)
        assert A.e_abs_normal(mu, sd) == pytest.approx(np.abs(x).mean(), rel=0.01)


def test_overlay_ratio_zero_mean_closed_form_and_mixed_monte_carlo():
    for n, rho in ((4, 0.0), (8, 0.2), (12, 0.5)):
        assert A.overlay_ratio(n, 0, 0.0, rho) == pytest.approx(math.sqrt((1 + (n - 1) * rho) / n))
    rng = np.random.default_rng(2)
    n_l, n_s, m, rho = 4, 2, 1.0, 0.2
    n = n_l + n_s
    C = np.full((n, n), rho) + (1 - rho) * np.eye(n)
    z = rng.multivariate_normal(np.zeros(n), C, 300_000)
    h = z + np.array([m] * n_l + [-m] * n_s)
    mc = np.abs(h.sum(1)).mean() / np.abs(h).sum(1).mean()
    assert A.overlay_ratio(n_l, n_s, m, rho) == pytest.approx(mc, rel=0.01)


def test_lognormal_share_hits_its_two_fitted_quantiles():
    assert A.lognormal_share(5e6, 1e6, 5e6) == pytest.approx(0.5)
    assert A.lognormal_share(5e6, 1e6, 1e6) == pytest.approx(0.75)


def test_power_and_slate_bars_match_the_desk_precedents():
    assert A.mde(1.0, 1) == pytest.approx(2.8016, abs=1e-4)
    assert A.n_required(2.0, 1.0) == pytest.approx(7.849 * 4, rel=1e-3)
    assert A.slate_bar(4) == pytest.approx(1.665, abs=5e-4)     # XASSET, docs/SYSTEM.md §5 2026-10-14
    assert A.slate_bar(52) == pytest.approx(2.811, abs=5e-4)    # CEF, docs/RESEARCH_STATE.md


def test_k_max_leaves_equity_exactly_at_maintenance():
    for u in (0.1, 0.3, 0.7):
        k = A.k_max(u)
        equity_after = 1 - k * u
        assert equity_after == pytest.approx(0.30 * k * (1 + u))
    x = A.x_max_single(0.4, 1.5)
    assert 1 - x * 0.4 == pytest.approx(0.30 * (1.5 + x * 0.4))


def test_block_returns_propagate_gaps_and_compound():
    r = np.array([[0.1], [0.1], [np.nan], [0.0], [0.05]])
    b = R.block_returns(r, 2)
    assert b.shape == (2, 1)
    assert b[0, 0] == pytest.approx(0.21)
    assert np.isnan(b[1, 0])


def test_ols_beta_recovers_slope_and_respects_min_obs():
    rng = np.random.default_rng(3)
    x = rng.normal(0, 0.02, 60)
    y = np.column_stack([1.5 * x + rng.normal(0, 1e-4, 60), 0.5 * x + rng.normal(0, 1e-4, 60)])
    y[:20, 1] = np.nan
    b = R.ols_beta(y, x, 45)
    assert b[0] == pytest.approx(1.5, abs=0.01)
    assert np.isnan(b[1])                      # 40 valid blocks < 45


def test_holdout_and_universe_guards_raise():
    with pytest.raises(R.WindowError):
        R.assert_pre_holdout(pd.Series(pd.to_datetime(["2022-12-30", "2023-01-03"])), "x")
    R.assert_pre_holdout(pd.Series(pd.to_datetime(["2022-12-30"])), "x")
    with pytest.raises(AssertionError):
        R.assert_no_universe([1, 2, 3], {3}, "x")
