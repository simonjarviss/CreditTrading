"""Tests for the shared inference module.

WHY THESE. Each published figure below is a worked example from the paper that
defines the method, and reproducing it is the check that the formula was
transcribed correctly (`docs/REFERENCES.md` §12rm gives the sources). The parity
tests pin that this module and the desk's existing copies agree, so moving a
trial onto it changes no past number. The PBO, power-forecast and read_result
tests run on synthetic data, so they are statements about the code, never about
the market (CLAUDE.md data rules). The tests marked "review, 2026-10-27" pin
defects an independent review found in the first version. Each fails against
that version.
"""
from __future__ import annotations

import sys
from math import comb, log, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from scripts.research import inference as I

REPO = Path(__file__).resolve().parents[3]


def _validate():
    sys.path.insert(0, str(REPO / "scripts" / "cef"))
    import validate as V
    return V


# -- published worked examples ------------------------------------------------

def test_dsr_reproduces_bailey_lopez_de_prado_worked_example():
    # SR 2.5 annualised on 5y of daily data (T=1250, 250/yr), N=100, V[SR_n]=1/2
    # annualised, skew -3, raw kurtosis 10 -> SR0 0.1132, DSR 0.9004 (fails 95%).
    d, sr0 = I.dsr(2.5 / sqrt(250), 1250, -3, 10, 100, 0.5 / 250, bound="gumbel")
    assert sr0 == pytest.approx(0.1132, abs=5e-5)
    assert d == pytest.approx(0.9004, abs=5e-5)
    # ... the same strategy passes at N=46, and with normal returns up to N=88.
    assert I.dsr(2.5 / sqrt(250), 1250, -3, 10, 46, 0.5 / 250, bound="gumbel")[0] == pytest.approx(0.9505, abs=5e-5)
    assert I.dsr(2.5 / sqrt(250), 1250, 0, 3, 88, 0.5 / 250, bound="gumbel")[0] > 0.95
    assert I.dsr(2.5 / sqrt(250), 1250, 0, 3, 89, 0.5 / 250, bound="gumbel")[0] < 0.95


def test_bound_must_be_named():
    # Review, 2026-10-27: dsr defaulted to "gumbel" while p_pass_dsr defaulted to
    # "upper", so a realised DSR was judged on a looser bar than its forecast.
    with pytest.raises(TypeError):
        I.dsr(0.05, 1000, 0, 3, 10, 1e-3)
    with pytest.raises(TypeError):
        I.p_pass_dsr(1.0, 2520, 10)
    with pytest.raises(ValueError):
        I.dsr(0.05, 1000, 0, 3, 10, 1e-3, bound="loose")


def test_sharpe_power_matches_rej_seager_bouchaud():
    # True SR 0.5 over 20y: power 0.61 at 5% two-sided, 0.146 at 99.9%;
    # ~43y to reach 99.9% significance (50% power), ~68y for 80% power.
    assert I.sharpe_power(0.5, 20) == pytest.approx(0.609, abs=1e-3)
    assert I.sharpe_power(0.5, 20, alpha=0.001) == pytest.approx(0.146, abs=1e-3)
    assert I.years_needed(0.5, power=0.5, alpha=0.001) == pytest.approx(43.3, abs=0.1)
    assert I.years_needed(0.5, power=0.8, alpha=0.001) == pytest.approx(68.3, abs=0.1)


def test_events_needed_matches_kothari_warner():
    # Lowest-volatility decile (daily SD 0.014): 21 events detect 1% on day 0 with
    # 90% power. (Their highest-decile figure of 60 is not reproduced by the
    # formula, which gives 58.5; it is not pinned here.)
    assert np.ceil(I.events_needed(0.01, 0.014, 1, power=0.9)) == 21
    # Power falls with the window: the same AR spread over L days needs L times
    # the events.
    assert I.events_needed(0.01, 0.014, 20) == pytest.approx(20 * I.events_needed(0.01, 0.014, 1))


def test_cluster_inflation_matches_kothari_warner():
    assert I.cluster_se_inflation(100, 0.02) == pytest.approx(1.73, abs=5e-3)
    assert I.cluster_se_inflation(1, 0.5) == 1.0
    with pytest.raises(ValueError):                       # rho = -1/(n-1) gives SE 0
        I.cluster_se_inflation(11, -0.1)


def test_pbo_split_count_is_c_16_8_not_the_printed_12780():
    rng = np.random.default_rng(0)
    assert I.pbo_cscv(rng.normal(size=(320, 5)), S=16)["n_splits"] == comb(16, 8) == 12870


# -- parity with the desk's existing copies -----------------------------------

def test_desk_dsr_is_validate_dsr_exactly():
    V = _validate()
    for obs, T, sk, ku, n in [(1.2, 2520, -0.5, 6, 52), (0.6, 1500, 0.2, 4, 10),
                              (0.9, 800, -1, 9, 6), (0.9, 800, -1, 9, 1)]:
        assert I.desk_dsr(obs, T, sk, ku, n) == pytest.approx(V._dsr(obs, T, sk, ku, n)[0], abs=1e-12)


def test_desk_dsr_takes_the_series_frequency():
    # Review, 2026-10-27: a monthly calendar-time sleeve de-annualised by sqrt(252)
    # read 0.074 where its own scale reads 0.839.
    assert I.desk_dsr(1.0, 120, 0, 3, 10, periods=12) == pytest.approx(
        I.dsr(1.0 / sqrt(12), 120, 0, 3, 10, 1 / 120, bound="upper")[0])
    assert I.desk_dsr(1.0, 120, 0, 3, 10, periods=12) > 5 * I.desk_dsr(1.0, 120, 0, 3, 10)


def test_desk_bar_is_the_upper_bound_and_stricter_than_the_expected_max():
    for n in (6, 10, 52, 162):
        assert I.upper_bound_max_z(n) > I.expected_max_z(n)
    assert I.upper_bound_max_z(52) == pytest.approx(2.811, abs=1e-3)   # orient's CEF bar
    assert I.expected_max_z(52) == pytest.approx(2.291, abs=1e-3)
    assert I.expected_max_z(1) == I.upper_bound_max_z(1) == 0.0       # one draw: exactly 0


def test_newey_west_matches_vrp_summary_and_statsmodels():
    from scripts.gamma.vrp_summary import newey_west_t as nw_desk
    import statsmodels.api as sm
    rng = np.random.default_rng(7)
    x = rng.normal(0.05, 1, 600)
    x = x + 0.5 * np.r_[0, x[:-1]]                       # MA(1): HAC matters
    t = I.newey_west_t(x, 5)
    assert t == pytest.approx(nw_desk(pd.Series(x), 5), abs=1e-12)
    fit = sm.OLS(x, np.ones_like(x)).fit(cov_type="HAC",
                                         cov_kwds={"maxlags": 5, "use_correction": False})
    assert t == pytest.approx(fit.tvalues[0], abs=1e-9)


def test_newey_west_refuses_impossible_lags():
    # Review, 2026-10-27: lags >= n were accepted (n 50, lags 200 -> t 2.51 vs 0.51).
    x = np.random.default_rng(2).normal(size=50)
    for bad in (-1, 50, 200):
        with pytest.raises(ValueError):
            I.newey_west_t(x, bad)


def test_p_clear_bar_reproduces_the_e1_preregistration_forecast():
    # PREREG_E1_MERGER_PAIR_2026-10-19.md (branch trial-events-e1): at a true
    # Sharpe 0.67 over 13 years, P(alpha t >= 3.0) ~= 0.28.
    assert I.p_clear_bar(0.67 * sqrt(13), 3.0) == pytest.approx(0.28, abs=5e-3)


# -- the power forecast against the gate it forecasts --------------------------

def _simulated_pass_rate(sr_annual, years, n, draw, sims, seed):
    """Fraction of simulated track records whose desk DSR clears 0.95."""
    rng = np.random.default_rng(seed)
    T = int(years * 252)
    hits = 0
    for _ in range(sims):
        x = sr_annual / sqrt(252) + draw(rng, T)
        hits += I.desk_dsr(x.mean() / x.std() * sqrt(252), T, stats.skew(x),
                           stats.kurtosis(x, fisher=False), n) > 0.95
    return hits / sims


def test_p_pass_dsr_matches_simulation_of_the_desk_gate():
    T = 8 * 252
    normal = _simulated_pass_rate(1.5, 8, 10, lambda r, T: r.normal(size=T), 1500, 3)
    assert I.p_pass_dsr(1.5, T, 10, bound="upper") == pytest.approx(normal, abs=0.035)
    # Review, 2026-10-27: a negatively skewed payoff (1 - Exp(1): skew -2, raw
    # kurtosis 9) passes less often than the normal forecast says. The forecast
    # must take the payoff's moments.
    negexp = _simulated_pass_rate(1.5, 8, 10, lambda r, T: 1 - r.exponential(size=T), 1500, 4)
    assert I.p_pass_dsr(1.5, T, 10, bound="upper", skew=-2, kurt=9) == pytest.approx(negexp, abs=0.035)
    assert I.p_pass_dsr(1.5, T, 10, bound="upper") - negexp > 0.04


def test_p_pass_dsr_refuses_what_it_cannot_use():
    with pytest.raises(ValueError):
        I.p_pass_dsr(1.0, 2520, 10, bound="upper", sr_var=0.0)
    with pytest.raises(ValueError):
        I.p_pass_dsr(1.0, 1, 10, bound="upper")
    with pytest.raises(ValueError):
        I.p_pass_dsr(1.0, 2520, 10, bound="upper", conf=1.5)


# -- PBO ------------------------------------------------------------------------

def test_pbo_logits_on_a_worked_example():
    # Review, 2026-10-27: w = rank/N and an off-by-one rank both passed the older
    # tests. Two blocks (S=2), three trials, Sharpes chosen by hand:
    #   block A: trial 0 = 2, trial 1 = 1, trial 2 = 0
    #   block B: trial 0 = -1, trial 1 = 2, trial 2 = 1
    # IS = A picks trial 0, which ranks 1st of 3 OOS: w = 1/4, logit ln(1/3).
    # IS = B picks trial 1, which ranks 2nd of 3 OOS: w = 2/4, logit 0.
    a = np.array([[3, 2, 1], [1, 0, -1]] * 2, dtype=float)
    b = np.array([[0, 3, 2], [-2, 1, 0]] * 2, dtype=float)
    r = I.pbo_cscv(np.vstack([a, b]), S=2)
    assert r["logits"] == pytest.approx([log(1 / 3), 0.0])
    assert r["pbo"] == 1.0
    assert r["null_pbo"] == pytest.approx(2 / 3)                # odd N: not 1/2


def test_pbo_is_near_its_null_on_noise_and_near_zero_with_a_dominant_edge():
    # On noise PBO sits at its null only ON AVERAGE across datasets. One fixed
    # sample ranged 0.09-0.93 across 40 seeds (2026-10-27): a column that drew a
    # lucky full-sample mean looks good in both halves. So one PBO on one panel is
    # a noisy reading. Report it with N and S, never as a verdict on its own.
    v = [I.pbo_cscv(np.random.default_rng(s).normal(size=(400, 20)), S=8)["pbo"]
         for s in range(40)]
    assert 0.4 < np.mean(v) < 0.7
    noise = np.random.default_rng(11).normal(size=(1000, 40))
    edge = noise.copy()
    edge[:, 0] += 0.5
    assert I.pbo_cscv(edge)["pbo"] < 0.01


def test_pbo_refuses_what_it_cannot_rank():
    rng = np.random.default_rng(1)
    with pytest.raises(ValueError):
        I.pbo_cscv(rng.normal(size=(100, 1)))            # one trial
    with pytest.raises(ValueError):
        I.pbo_cscv(rng.normal(size=(100, 4)), S=7)        # odd S
    x = rng.normal(size=(100, 4))
    x[3, 2] = np.nan
    with pytest.raises(ValueError):
        I.pbo_cscv(x)


# -- multiple testing, reading, the book ------------------------------------------

def test_bh_is_step_up():
    assert I.bh_fdr([0.01, 0.02, 0.03, 0.5]).tolist() == [True, True, True, False]
    # 0.013 fails its own threshold (0.0125) but is rejected because 0.02 passes
    # a later one: the step-up property.
    assert I.bh_fdr([0.02, 0.013, 0.5, 0.5]).tolist() == [True, True, False, False]
    assert not I.bh_fdr([0.2, 0.3]).any()


def test_read_result_separates_absent_from_inconclusive():
    # Powered null: the interval excludes every effect worth trading.
    assert I.read_result(1.0, 2.0, 30.0, n_trials=1)["outcome"] == "ABSENT"
    # Wide null: cannot rule out the meaningful effect -> not a kill.
    assert I.read_result(-58.0, 104.0, 30.0, n_trials=1)["outcome"] == "INCONCLUSIVE"
    # A significant effect of the wrong sign is ABSENT for this hypothesis.
    assert I.read_result(-20.0, 5.0, 10.0, n_trials=1)["outcome"] == "ABSENT"


def test_read_result_places_the_hurdle_against_the_interval():
    # Review, 2026-10-27: comparing the point estimate could not tell a hurdle
    # inside the interval from one the interval excludes.
    assert I.read_result(20.0, 8.0, 30.0, n_trials=1)["vs_meaningful"] == "STRADDLES"
    r = I.read_result(25.0, 2.0, 30.0, n_trials=1)
    assert r["outcome"] == "PRESENT" and r["vs_meaningful"] == "BELOW"
    assert I.read_result(60.0, 5.0, 30.0, n_trials=1)["vs_meaningful"] == "ABOVE"


def test_read_result_deflates_present_for_the_trial_count():
    # Review, 2026-10-27: t 2.1 read PRESENT at N=52, where 52 plain 5% tests give
    # at least one false PRESENT with probability 0.73.
    assert I.read_result(2.1, 1.0, 5.0, n_trials=1)["outcome"] == "PRESENT"
    assert I.read_result(2.1, 1.0, 5.0, n_trials=52)["outcome"] == "INCONCLUSIVE"
    assert 1 - 0.975 ** 52 == pytest.approx(0.73, abs=5e-3)
    with pytest.raises(TypeError):
        I.read_result(2.1, 1.0, 5.0)                       # N has no default


def test_combined_sharpe_never_admits_what_marginal_gain_rejects():
    # Review, 2026-10-27: the unconstrained optimum shorted weak sleeves, so a
    # losing sleeve "raised" the book (1.0, -0.5, 0 -> 1.118).
    assert I.combined_sharpe(1.0, -0.5, 0.0) == pytest.approx(1.0)
    assert I.combined_sharpe(1.0, 0.4, 0.5) == pytest.approx(1.0)
    for b in np.linspace(-0.5, 1.5, 21):
        for rho in (-0.3, 0.0, 0.3, 0.7):
            gain = I.marginal_gain(b, 1.0, rho)
            c = I.combined_sharpe(1.0, b, rho)
            assert (c > 1.0 + 1e-12) == (gain > 1e-12), (b, rho)
    # Uncorrelated: five 0.5s combine to sqrt(5)*0.5 ~= 1.12 (the D5 legend's "about 1.1").
    sr = 0.5
    for _ in range(4):
        sr = I.combined_sharpe(sr, 0.5, 0.0)
    assert sr == pytest.approx(sqrt(5) * 0.5)


def test_effective_trials_collapses_correlated_variants():
    assert I.effective_trials(20, 1.0) == pytest.approx(1.0)
    assert I.effective_trials(20, 0.0) == pytest.approx(20.0)
    with pytest.raises(ValueError):
        I.effective_trials(20, 1.5)


def test_inputs_it_cannot_use_raise():
    with pytest.raises(ValueError):
        I.psr(0.1, 100, skew=50, kurt=3)                  # non-positive variance term
    with pytest.raises(ValueError):
        I.newey_west_t(np.array([1.0, np.nan, 2.0, 3.0]))
    with pytest.raises(ValueError):
        I.mde(0.0, 10)
    with pytest.raises(ValueError):
        I.expected_max_z(0)


# -- clustered_mean_diff (added 2026-10-28 for the A1 re-open) -------------------

def _clustered_panel(seed=11, dates=60, per=5):
    """Synthetic name-days: a common date shock, so clustering matters. A statement
    about the code only."""
    rng = np.random.default_rng(seed)
    g = np.repeat(np.arange(dates), per)
    y = rng.normal(0, 1, g.size) + 2.0 * rng.normal(0, 1, dates)[g]
    a = rng.random(g.size) < 0.3
    return y, a, g


def test_clustered_mean_diff_matches_statsmodels_cluster_ols():
    # The second method: OLS of y on [1, 1(A)] with cov_type="cluster". statsmodels
    # applies G/(G-1) x (N-1)/(N-K); this module applies G/(G-1) only (the desk's
    # convention), so the variances differ by exactly (N-1)/(N-K).
    import statsmodels.api as sm
    y, a, g = _clustered_panel()
    r = I.clustered_mean_diff(y, a, g)
    N = y.size
    X = np.column_stack([np.ones(N), a.astype(float)])
    fit = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": g})
    assert r["diff"] == pytest.approx(fit.params[1], abs=1e-12)
    assert r["se_diff"] * sqrt((N - 1) / (N - 2)) == pytest.approx(fit.bse[1], rel=1e-10)
    for grp, key in ((a, "a"), (~a, "b")):
        f1 = sm.OLS(y[grp], np.ones(grp.sum())).fit(cov_type="cluster", cov_kwds={"groups": g[grp]})
        assert r[f"mean_{key}"] == pytest.approx(f1.params[0], abs=1e-12)
        assert r[f"se_{key}"] == pytest.approx(f1.bse[0], rel=1e-10)   # K = 1: no extra factor


def test_clustered_mean_diff_by_hand_on_four_observations():
    # Two dates, each with one A and one B observation. A: 1, 3 (mean 2); B: 0, 4
    # (mean 2). Scores on the difference: date 0: (1-2)/2 - (0-2)/2 = +0.5;
    # date 1: (3-2)/2 - (4-2)/2 = -0.5. Var = 2/1 x (0.25 + 0.25) = 1.0.
    r = I.clustered_mean_diff([1.0, 0.0, 3.0, 4.0], np.array([True, False, True, False]), [0, 0, 1, 1])
    assert r["diff"] == 0.0
    assert r["se_diff"] == pytest.approx(1.0, abs=1e-15)
    # se_a: scores -0.5, +0.5 on two dates -> 2 x 0.5 = 1.0; se_b: -1, +1 -> 2 x 2 = 4
    assert r["se_a"] == pytest.approx(1.0) and r["se_b"] == pytest.approx(2.0)


def test_clustered_mean_diff_sees_the_covariance_a_naive_difference_misses():
    # Every date holds 2 A and 3 B observations and one shock moves them all, so the
    # two means co-move and the shock cancels from their difference: its SE is far
    # below sqrt(se_a^2 + se_b^2), which treats the two means as independent.
    y, _, g = _clustered_panel(seed=3)
    a = np.tile(np.array([True, True, False, False, False]), 60)
    r = I.clustered_mean_diff(y, a, g)
    assert r["se_diff"] < 0.5 * sqrt(r["se_a"] ** 2 + r["se_b"] ** 2)


def test_clustered_mean_diff_refuses_what_it_cannot_use():
    y, a, g = _clustered_panel()
    with pytest.raises(ValueError):
        I.clustered_mean_diff(np.r_[y[:-1], np.nan], a, g)
    with pytest.raises(TypeError):
        I.clustered_mean_diff(y, a.astype(float), g)
    with pytest.raises(ValueError):
        I.clustered_mean_diff(y, np.zeros_like(a), g)            # group A empty
    with pytest.raises(ValueError):
        I.clustered_mean_diff(y, a, np.zeros_like(g))            # one cluster
    one_date_a = np.zeros_like(a)
    one_date_a[:3] = True                                        # A on date 0 only
    with pytest.raises(ValueError):
        I.clustered_mean_diff(y, one_date_a, g)


# -- the range on rho (added 2026-10-28, scripts/research/reopen_book/) ----------

def _w4():
    sys.path.insert(0, str(REPO))
    from scripts.cef import w4_artifacts as W
    return W


def test_stationary_indices_are_the_w4_draw_exactly():
    # Parity: the correlation bootstrap must use the desk's existing stationary
    # draw, from the same random stream, so a mean resampled here equals
    # w4_artifacts.stationary_boot's at the same seed, draw for draw.
    W = _w4()
    x = pd.Series(np.random.default_rng(3).standard_normal(400))
    ref = W.stationary_boot(x, mean_block=21, reps=2_500, seed=20261013, chunk=1_000)
    got = np.concatenate([x.values[idx].mean(axis=1) for idx in
                          I.stationary_bootstrap_indices(400, 21, 2_500, seed=20261013, chunk=1_000)])
    assert np.array_equal(got, ref["means"])


def test_stationary_indices_have_geometric_blocks_of_the_stated_mean():
    idx = next(I.stationary_bootstrap_indices(20_000, 25, 1, seed=1, chunk=1))[0]
    breaks = np.count_nonzero(np.diff(idx) % 20_000 != 1) + 1
    assert 20_000 / breaks == pytest.approx(25, rel=0.1)
    assert idx.min() >= 0 and idx.max() < 20_000


def test_bootstrap_corr_covers_the_truth_and_widens_with_dependence():
    # Synthetic: the claim is about the code (does the interval contain the true
    # rho, and is it wider when the pairs are persistent), never about a market.
    rng = np.random.default_rng(7)
    n, rho = 3_000, 0.3
    z = rng.standard_normal((n, 2))
    x = z[:, 0]
    y = rho * z[:, 0] + np.sqrt(1 - rho ** 2) * z[:, 1]
    r = I.stationary_bootstrap_corr(x, y, 21, seed=11, reps=2_000)
    assert r["rho"] == pytest.approx(np.corrcoef(x, y)[0, 1])
    assert r["lo"] < r["rho"] < r["hi"]
    # On iid pairs the block draw changes nothing material: its width matches
    # the Fisher interval's (the two methods agree where both apply).
    flo, fhi = I.fisher_corr_ci(r["rho"], n)
    assert (r["hi"] - r["lo"]) == pytest.approx(fhi - flo, rel=0.2)
    # Coverage of the true rho, over independent replications (each a fresh
    # sample): about 95%, and certainly not the 60-70% a too-narrow interval gives.
    hits = 0
    for s in range(40):
        g = np.random.default_rng(100 + s).standard_normal((600, 2))
        xx, yy = g[:, 0], rho * g[:, 0] + np.sqrt(1 - rho ** 2) * g[:, 1]
        q = I.stationary_bootstrap_corr(xx, yy, 10, seed=s, reps=400)
        hits += q["lo"] < rho < q["hi"]
    assert hits >= 34
    # Persistent on/off activity (a sparse event sleeve): the same days repeated
    # in runs of 50 make the effective sample ~50x smaller, and the interval must
    # be much wider than the iid one at the same n.
    xs, ys = np.repeat(x[:60], 50), np.repeat(y[:60], 50)
    wide = I.stationary_bootstrap_corr(xs, ys, 50, seed=11, reps=2_000)
    assert (wide["hi"] - wide["lo"]) > 3 * (r["hi"] - r["lo"])


def test_bootstrap_corr_refuses_what_it_cannot_use():
    x = np.arange(100.0)
    with pytest.raises(ValueError):
        I.stationary_bootstrap_corr(x, x[:-1], 5, seed=1, reps=10)       # misaligned
    with pytest.raises(ValueError):
        I.stationary_bootstrap_corr(np.r_[x[:-1], np.nan], x, 5, seed=1, reps=10)
    with pytest.raises(ValueError):
        I.stationary_bootstrap_corr(x, x, 50, seed=1, reps=10)          # fewer than 3 blocks
    with pytest.raises(ValueError):
        I.stationary_bootstrap_corr(np.zeros(100), x, 5, seed=1, reps=10)
    sparse = np.zeros(100)
    sparse[0] = 1.0                                                     # one active day: some draws miss it
    with pytest.raises(ValueError):
        I.stationary_bootstrap_corr(sparse, x, 5, seed=1, reps=500)


def test_fisher_interval_matches_scipy():
    rng = np.random.default_rng(5)
    x = rng.standard_normal(150)
    y = 0.4 * x + rng.standard_normal(150)
    r = stats.pearsonr(x, y)
    ci = r.confidence_interval(0.95)
    lo, hi = I.fisher_corr_ci(float(r.statistic), 150)
    assert lo == pytest.approx(ci.low, abs=1e-12) and hi == pytest.approx(ci.high, abs=1e-12)
    with pytest.raises(ValueError):
        I.fisher_corr_ci(0.2, 3)


def test_safeguarded_sr0_reproduces_the_2026_10_28_bars():
    # bar_inputs on the backfilled ledger (2026-10-28): EVENTS rho 0.006, V 5.27e-05,
    # T 3217, declared N 6; XASSET rho 0.187, V 4.99e-04, T 3693, N 4. The
    # annualised hurdles the team lead ruled on were 0.363 and 0.337.
    ev = I.safeguarded_sr0(6, 0.005956912823026237, 5.27284983388247e-05, 3217)
    xa = I.safeguarded_sr0(4, 0.18682479180006195, 0.0004994654446952893, 3693)
    assert ev * sqrt(252) == pytest.approx(0.363, abs=1e-3)
    assert xa * sqrt(252) == pytest.approx(0.337, abs=1e-3)
    # The floor binds for EVENTS (measured spread below sampling noise) and not for XASSET.
    assert I.safeguarded_sr0(6, 0.006, 0.0, 3217) == pytest.approx(ev, rel=1e-3)
    assert I.safeguarded_sr0(4, 0.187, 0.0, 3693) < xa
    # Negative correlation counts as independent, never as fewer than N trials.
    assert I.safeguarded_sr0(6, -0.3, 1e-4, 3000) == I.safeguarded_sr0(6, 0.0, 1e-4, 3000)
    with pytest.raises(ValueError):
        I.safeguarded_sr0(0, 0.0, 1e-4, 3000)
