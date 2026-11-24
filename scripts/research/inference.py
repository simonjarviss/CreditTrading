"""The desk's one implementation of research inference.

WHY THIS FILE EXISTS. Until 2026-10-27 every trial carried its own copy of its
statistics: a Newey-West t in `scripts/cef/c4_families.py`,
`scripts/events/e1_merger_pair.py` and `scripts/gamma/vrp_summary.py`; a deflated
Sharpe in `scripts/cef/validate.py` and `e1_merger_pair.py`; and power arithmetic
in four feasibility scripts, each with its own conventions. Two trials could
then reach different answers to one question. A zero-trial audit of 82 kills
(`results/research/DESK_METHOD_2026-10-27.md`) found the larger failure:

- power was forecast and then ignored. The NAV-tender pre-registration put
  P(pass) at 0.02, E1's at 0.15. Both trials were spent, and both "failed";
- a null was recorded as "no edge" whether or not the test could have seen one.

This module is to inference what `band_frontier.evaluate()` is to backtests.
Extend it visibly; never fork a private copy into a trial script.

CONVENTIONS, because a units slip here is invisible downstream:
- A Sharpe ratio is PER PERIOD (non-annualised) unless its name ends `_annual`.
- Kurtosis is RAW kurtosis: 3 for a normal distribution, which is pandas
  `.kurt()` + 3.
- `T` counts return observations, not years.
- Every function raises on input it cannot use. None of them returns a
  default (CLAUDE.md: no silent fallbacks).

Sources: `docs/REFERENCES.md` §12rm. That section names each paper and the
worked example each test reproduces.
"""
from __future__ import annotations

import argparse
from itertools import combinations
from math import comb, e, log, sqrt
from statistics import NormalDist

import numpy as np

_N = NormalDist()
EULER_GAMMA = 0.5772156649015329


def z_crit(alpha: float = 0.05, two_sided: bool = True) -> float:
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    return _N.inv_cdf(1 - alpha / 2) if two_sided else _N.inv_cdf(1 - alpha)


# -- power: before any data is seen ------------------------------------------

def power_of_z(expected_z: float, alpha: float = 0.05, two_sided: bool = True) -> float:
    """P(the test rejects) when its statistic is ~ N(expected_z, 1).

    Everything else in this section reduces to this. The expected z of a true
    effect is effect / SE, so power is a property of the design (n, sigma, the
    window), and it can be computed before any return is looked at.
    """
    c = z_crit(alpha, two_sided)
    p = 1 - _N.cdf(c - expected_z)
    if two_sided:
        p += _N.cdf(-c - expected_z)
    return p


def p_clear_bar(expected_t: float, bar: float) -> float:
    """P(observed t >= bar) when the t is ~ N(expected_t, 1).

    This is the chance that a one-sided gate passes: alpha t >= 3.0 for D4, a
    net t >= 2.0, and so on. E1's pre-registration forecast 0.28 for its D4 gate
    at a true Sharpe of 0.67 over 13 years: expected t 0.67·√13 = 2.42. The trial
    was spent, and the gate failed. A gate whose pass chance at a plausible
    effect is below a half is more likely to kill a real effect than to find it.
    """
    return 1 - _N.cdf(bar - expected_t)


def sharpe_power(sr_annual: float, years: float, alpha: float = 0.05,
                 two_sided: bool = True) -> float:
    """Power of a t-test that a strategy's Sharpe is non-zero.

    Under IID returns the expected t of an annualised Sharpe over Y years is
    SR·√Y (the ½SR² term in the SE is negligible at per-period scale). At a true
    0.5 over 20 years this gives 0.61 at 5% two-sided and 0.146 at 99.9%
    (Rej, Seager & Bouchaud 2018). A Sharpe-0.5 sleeve is a coin toss to detect
    in a lifetime.
    """
    if years <= 0:
        raise ValueError(f"years must be positive, got {years}")
    return power_of_z(sr_annual * sqrt(years), alpha, two_sided)


def years_needed(sr_annual: float, power: float = 0.8, alpha: float = 0.05,
                 two_sided: bool = True) -> float:
    """Years of data for `power` to detect a true annualised Sharpe."""
    if sr_annual <= 0:
        raise ValueError(f"sr_annual must be positive, got {sr_annual}")
    return ((z_crit(alpha, two_sided) + _N.inv_cdf(power)) / sr_annual) ** 2


def mde(sigma: float, n: float, alpha: float = 0.05, power: float = 0.8,
        two_sided: bool = True) -> float:
    """Minimum detectable mean effect for n INDEPENDENT observations of sd sigma.

    n counts independent units: distinct issuer-months or event clusters, never
    raw rows. Use `cluster_se_inflation` on the SE when events share dates. At
    80% power and 5% two-sided this is ≈ 2.8·sigma/√n, the rule the SS desk's
    event-econometrician seat used.
    """
    if n <= 0 or sigma <= 0:
        raise ValueError(f"need sigma > 0 and n > 0, got sigma={sigma}, n={n}")
    return (z_crit(alpha, two_sided) + _N.inv_cdf(power)) * sigma / sqrt(n)


def events_needed(abnormal: float, sigma_daily: float, window_days: float = 1,
                  alpha: float = 0.05, power: float = 0.8,
                  two_sided: bool = True) -> float:
    """Events needed to detect a mean abnormal return spread over a window.

    Kothari & Warner (2007), assuming independent events:
    N ≈ ((z_{1-α/2} + z_power)·σ·√L / AR)². Power falls with the window length L
    and with σ. A long-hold event sleeve on volatile names needs far more events
    than a one-day reaction. σ must be MEASURED: non-event windows before
    2023-01-01, or a cited paper. Never assume it.
    """
    if abnormal == 0 or sigma_daily <= 0 or window_days <= 0:
        raise ValueError("need abnormal != 0, sigma_daily > 0, window_days > 0")
    return ((z_crit(alpha, two_sided) + _N.inv_cdf(power))
            * sigma_daily * sqrt(window_days) / abs(abnormal)) ** 2


def cluster_se_inflation(n: int, rho: float) -> float:
    """Factor by which a naive SE understates the true one for n events whose
    returns correlate at rho: √(1 + (n−1)ρ) (Kothari & Warner 2007). At n=100
    and rho=0.02 it is 1.73, so a naive t of 3.4 is really about 2.0. That is a
    false positive, which is why calendar-time portfolios are the headline."""
    if n < 1 or not -1 / max(n - 1, 1) < rho <= 1:
        raise ValueError(f"need n >= 1 and a feasible rho, got n={n}, rho={rho}")
    return sqrt(1 + (n - 1) * rho)


# -- multiple testing: the bar a best-of-N result must clear -----------------

def expected_max_z(n: float) -> float:
    """E[max of n IID N(0,1)] ≈ (1−γ)Z⁻¹(1−1/n) + γZ⁻¹(1−1/(ne)).

    Bailey & López de Prado (2014). The desk's counter bar √(2 ln N) is the
    UPPER BOUND on this quantity, not the quantity itself. At N=52 the two are
    2.29 and 2.81. A stricter bar is a choice, so state which one you used.
    """
    if n < 1:
        raise ValueError(f"expected maximum needs n >= 1, got {n}")
    if n == 1:
        return 0.0                      # exact: one draw's mean (the Gumbel form diverges)
    return ((1 - EULER_GAMMA) * _N.inv_cdf(1 - 1 / n)
            + EULER_GAMMA * _N.inv_cdf(1 - 1 / (n * e)))


def upper_bound_max_z(n: float) -> float:
    """√(2 ln N): the bar `ops/orient.py` and `validate._dsr` derive from the counter."""
    if n < 1:
        raise ValueError(f"bar needs n >= 1, got {n}")
    return sqrt(2 * log(n))


def effective_trials(m: int, rho_bar: float) -> float:
    """Independent trials implied by M correlated ones: N̂ = ρ̄ + (1−ρ̄)M.

    Bailey & López de Prado (2014). Twenty variants at correlation near one
    are about one trial (Arnott, Harvey & Markowitz 2019). The counter table
    records raw M. Counting correlated variants as independent raises the bar
    and rejects true effects. ρ̄ must come from the stored trial P&L series,
    never be guessed.
    """
    if m < 1 or not 0 <= rho_bar <= 1:
        raise ValueError(f"need m >= 1 and 0 <= rho_bar <= 1, got m={m}, rho={rho_bar}")
    return rho_bar + (1 - rho_bar) * m


def psr(sr: float, T: int, skew: float, kurt: float, sr_star: float = 0.0) -> float:
    """Probabilistic Sharpe ratio: P(true SR > sr_star) (Bailey & López de Prado 2012).

    sr and sr_star are per period, and kurt is raw. Fat tails and negative skew
    widen the SE, so the same Sharpe on a short-put-like payoff earns less
    confidence.
    """
    if T < 2:
        raise ValueError(f"PSR needs T >= 2, got {T}")
    denom = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    if denom <= 0:
        raise ValueError(f"PSR variance term is non-positive ({denom}); check skew/kurt units")
    return _N.cdf((sr - sr_star) * sqrt(T - 1) / sqrt(denom))


_BOUNDS = {"gumbel": expected_max_z, "upper": upper_bound_max_z}


def _bar(bound: str, n_trials: float) -> float:
    if bound not in _BOUNDS:
        raise ValueError(f"bound must be 'upper' (the desk's) or 'gumbel' (the paper's), got {bound!r}")
    return _BOUNDS[bound](n_trials)


def dsr(sr: float, T: int, skew: float, kurt: float, n_trials: float,
        sr_var: float, *, bound: str) -> tuple[float, float]:
    """Deflated Sharpe ratio. Returns (DSR, SR0), both on the per-period scale.

    SR0 = √V[SR_n]·E[max of N] is the best Sharpe that N skill-less trials are
    expected to produce. sr_var is the cross-trial variance of per-period
    Sharpes, measured from the stored trial series where they exist.
    `bound="gumbel"` is the paper's expected maximum. `bound="upper"` uses
    √(2 ln N), the desk's bar. There is deliberately no default: report both,
    labelled. The team lead rules which one gates.
    Reproduces the paper's worked example (DSR 0.9004) in the tests.
    """
    if sr_var <= 0:
        raise ValueError(f"sr_var must be positive, got {sr_var}")
    sr0 = sqrt(sr_var) * _bar(bound, n_trials)
    return psr(sr, T, skew, kurt, sr0), sr0


def desk_dsr(sr_annual: float, T: int, skew: float, kurt: float,
             n_trials: float, periods: int = 252) -> float:
    """`scripts/cef/validate.py::_dsr`, restated on the scale above.

    That function uses the upper bound and sets V[SR_n] = 1/T, the sampling
    variance of a single skill-less Sharpe, in place of a measured cross-trial
    spread. The parity test pins this equivalence at the daily 252 that
    validate assumes. Pass `periods` for a monthly calendar-time series (12):
    de-annualising a monthly Sharpe by √252 understates it about 4.6 times.
    Changing the desk's bar is a governance change, not a refactor.
    """
    return dsr(sr_annual / sqrt(periods), T, skew, kurt, n_trials, 1 / T, bound="upper")[0]


def p_pass_dsr(sr_true_annual: float, T: int, n_trials: float, *, bound: str,
               sr_var: float | None = None, skew: float = 0.0, kurt: float = 3.0,
               conf: float = 0.95, periods: int = 252) -> float:
    """Chance a strategy whose true annualised Sharpe is sr_true clears DSR > conf.

    SR_hat ~ N(SR, (1 − γ₃SR + (γ₄−1)/4·SR²)/(T−1)), the PSR variance term, and the
    gate passes iff SR_hat > SR0 + z_conf·SE. sr_var is the PER-PERIOD
    cross-trial variance. None means the desk's null-implied 1/T.
    **Pass the expected skew and raw kurtosis** for a short-premium or event
    payoff. Under normal returns the forecast was 0.620 where a
    skew −2.83 / kurtosis 15 payoff simulates to 0.531, which is enough to flip
    the 0.5 power gate (review, 2026-10-27). Matches simulation against
    `desk_dsr` (test). Compute this BEFORE spending a trial.
    """
    if T < 2 or not 0 < conf < 1 or periods < 1:
        raise ValueError(f"need T >= 2, 0 < conf < 1, periods >= 1; got T={T}, conf={conf}, periods={periods}")
    if sr_var is not None and sr_var <= 0:
        raise ValueError(f"sr_var must be positive (per period), got {sr_var}")
    sr = sr_true_annual / sqrt(periods)
    var = 1 / T if sr_var is None else sr_var
    sr0 = sqrt(var) * _bar(bound, n_trials)
    v = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    if v <= 0:
        raise ValueError(f"PSR variance term is non-positive ({v}); check skew/kurt units")
    se = sqrt(v / (T - 1))
    return 1 - _N.cdf((sr0 + _N.inv_cdf(conf) * se - sr) / se)


def safeguarded_sr0(declared_n: float, rho_bar: float, sr_var_measured: float, T: int) -> float:
    """The paper's best-of-N bar with the team lead's 2026-10-28 safeguards. Per-period SR0.

    `docs/SYSTEM.md` §5, 2026-10-28. The bar is the Gumbel expected maximum,
    scaled by √V and evaluated at:
    - N = `effective_trials(declared_n, ρ̄)`. The counter's DECLARED slate size
      (EVENTS was declared at 6 while only 2 trials existed), adjusted by the
      measured mean correlation. A negative ρ̄ counts as 0: independence is the
      conservative case.
    - V = max(measured cross-trial variance, 1/T), floored at the variance a
      skill-less trial's Sharpe has by sampling alone. A spread measured from two
      to four trials has one to three degrees of freedom. EVENTS' two trials
      happened to have similar Sharpes, and unfloored the bar fell to an
      annualised 0.06 (2026-10-28).
    Pass `declared_n` from the counter's record, never as a literal (H14). CEF
    keeps the desk's √(2 ln N) bar under the same ruling: 50 of its 52 trials
    cannot be rebuilt.
    """
    if declared_n < 1 or T < 2 or sr_var_measured < 0 or not -1 <= rho_bar <= 1:
        raise ValueError(f"need declared_n >= 1, T >= 2, sr_var >= 0, -1 <= rho <= 1; "
                         f"got {declared_n}, {T}, {sr_var_measured}, {rho_bar}")
    n = effective_trials(declared_n, max(rho_bar, 0.0))
    return sqrt(max(sr_var_measured, 1 / T)) * expected_max_z(n)


def bh_fdr(pvals, q: float = 0.05) -> np.ndarray:
    """Benjamini-Hochberg (1995) step-up. Returns a boolean mask of discoveries.

    Use it across a DECLARED slate (XASSET, an SS census) in place of a family-
    wise bar. Harvey & Liu (2020) found BH came close to its target false-
    discovery rate on their strategy set, while stricter procedures missed
    true effects.
    """
    p = np.asarray(pvals, dtype=float)
    if p.ndim != 1 or p.size == 0 or np.isnan(p).any() or ((p < 0) | (p > 1)).any():
        raise ValueError("pvals must be a non-empty 1-D array of numbers in [0, 1]")
    m = p.size
    order = np.argsort(p)
    passed = p[order] <= q * np.arange(1, m + 1) / m
    out = np.zeros(m, dtype=bool)
    if passed.any():
        k = np.nonzero(passed)[0].max()
        out[order[: k + 1]] = True
    return out


# -- reading a result: what a null means -------------------------------------

def newey_west_t(x, lags: int | None = None) -> float:
    """HAC (Bartlett) t of a series' mean. lags=None uses ⌊4(T/100)^(2/9)⌋ (Newey-West 1994).

    The same estimator as `scripts/gamma/vrp_summary.py::newey_west_t`, pinned
    by a parity test, and checked against statsmodels as a second method.
    NaNs raise. Drop them yourself and say how many you dropped.
    """
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or x.size < 3:
        raise ValueError("newey_west_t needs a 1-D series of length >= 3")
    if np.isnan(x).any():
        raise ValueError("newey_west_t got NaNs; drop them explicitly and report the count")
    n = x.size
    L = int(4 * (n / 100) ** (2 / 9)) if lags is None else lags
    if not 0 <= L < n:
        raise ValueError(f"lags must be in [0, {n - 1}] for a series of length {n}, got {L}")
    u = x - x.mean()
    s = u @ u / n
    for k in range(1, L + 1):
        s += 2 * (1 - k / (L + 1)) * (u[k:] @ u[:-k]) / n
    if s <= 0:
        raise ValueError("long-run variance is non-positive")
    return x.mean() / sqrt(s / n)


def clustered_mean_diff(y, in_a, clusters) -> dict:
    """Two group means of one pooled sample, and their difference, with SEs clustered.

    Added 2026-10-28 for the A1 re-open (`scripts/research/reopen_a1/`), which asks
    whether the book's short name-days inside share-issuance windows earn less than
    those outside. Name-days on one date share that date's market move, so a naive
    SE treats as independent what is one draw (H6: cluster by date). The desk had
    this estimator only as private copies (`a2_insider_buying.clustered`,
    `exec_capacity_open_cross`); this is the shared one.

    y         the per-observation values (e.g. P&L per short name-day), finite.
    in_a      bool, True for group A (e.g. inside a window); both groups need >= 2
              observations.
    clusters  one label per observation (e.g. the decision date); >= 2 clusters
              overall, and >= 2 within each group for its own SE.

    The estimator is the OLS sandwich of y on [1, 1(A)] with clustered scores, the
    CR0 sum times G/(G-1), which is the desk's convention (`a2_insider_buying.
    clustered`). Each observation's score on the difference is e_i/n_A in A and
    −e_i/n_B in B, where e_i is its deviation from its own group's mean; the
    variance is G/(G−1)·Σ_g (Σ_{i∈g} score_i)². A date holding name-days in both
    groups therefore enters once, with the covariance between the two means, which
    a difference of two separately clustered SEs would miss. statsmodels' cluster
    covariance multiplies by a further (N−1)/(N−K) (K = 2 here, 1 for one mean);
    the parity test pins that relation exactly, as the second method.

    Returns mean_a, se_a, n_a, clusters_a; the same for b; diff = mean_a − mean_b,
    se_diff, clusters (overall G). Raises on NaN, on a group too small to have a
    mean and a spread, and on fewer than two clusters: there is no default.
    """
    y = np.asarray(y, dtype=float)
    a = np.asarray(in_a)
    g = np.asarray(clusters)
    if y.ndim != 1 or a.shape != y.shape or g.shape != y.shape:
        raise ValueError("y, in_a and clusters must be 1-D and the same length")
    if a.dtype != bool:
        raise TypeError("in_a must be a bool array, not a number that might be a weight")
    if not np.isfinite(y).all():
        raise ValueError("y holds NaN or inf; drop them explicitly and report the count")
    n_a, n_b = int(a.sum()), int((~a).sum())
    if n_a < 2 or n_b < 2:
        raise ValueError(f"each group needs >= 2 observations, got {n_a} and {n_b}")
    _, gid = np.unique(g, return_inverse=True)
    G = int(gid.max()) + 1
    if G < 2:
        raise ValueError("fewer than two clusters: a clustered SE does not exist")
    m_a, m_b = float(y[a].mean()), float(y[~a].mean())
    e = np.where(a, y - m_a, y - m_b)

    def _cr(score: np.ndarray, mask: np.ndarray) -> tuple[float, int]:
        s = np.bincount(gid[mask], weights=score[mask], minlength=G)
        k = int(np.unique(gid[mask]).size)
        if k < 2:
            raise ValueError("a group spans fewer than two clusters: its clustered SE does not exist")
        return sqrt(k / (k - 1) * float(s @ s)), k

    se_a, G_a = _cr(e / n_a, a)
    se_b, G_b = _cr(e / n_b, ~a)
    se_d, _ = _cr(np.where(a, e / n_a, -e / n_b), np.ones_like(a))
    return {"mean_a": m_a, "se_a": se_a, "n_a": n_a, "clusters_a": G_a,
            "mean_b": m_b, "se_b": se_b, "n_b": n_b, "clusters_b": G_b,
            "diff": m_a - m_b, "se_diff": se_d, "clusters": G}


def read_result(estimate: float, se: float, meaningful: float, *, n_trials: float,
                alpha: float = 0.05) -> dict:
    """Read a result into PRESENT, ABSENT or INCONCLUSIVE. Never into "no edge" alone.

    `estimate` is signed so that positive is the hypothesised direction.
    `meaningful` (> 0) is the smallest effect that would matter: the cost hurdle,
    or the size the sleeve needs. `n_trials` is the counter's N, effective where
    it is measured, and it has no default. The interval is Šidák-adjusted to
    alpha_N = 1 − (1−alpha)^(1/N). At N = 52 a plain 5% test gives at least one
    false PRESENT with probability 0.73, so an unadjusted PRESENT would order a
    successor entry for noise (review, 2026-10-27). The same wider interval makes
    ABSENT harder, so fewer real effects are buried. With the adjusted
    interval [lo, hi]:
    - PRESENT: lo > 0. The effect is there, whatever later gates decide about its
      expression.
    - ABSENT: hi < meaningful. Every effect worth trading is ruled out. This is
      the strongest reading. Since 2026-11-08 even this idea can return if the
      agent says what is different (docs/SYSTEM.md §5).
    - INCONCLUSIVE: anything else. The test could not tell. Record it as
      underpowered, with what would make it decidable, not as a kill.
    The audit behind this module found 20 of 82 kills were underpowered in this
    sense but were recorded as dead.
    `vs_meaningful` places the hurdle against the same interval: ABOVE (lo ≥ it:
    the expression clears it), BELOW (hi < it: ruled out at this size), or
    STRADDLES.
    """
    if se <= 0 or meaningful <= 0 or n_trials < 1:
        raise ValueError(f"need se > 0, meaningful > 0, n_trials >= 1; "
                         f"got se={se}, meaningful={meaningful}, n_trials={n_trials}")
    a = 1 - (1 - alpha) ** (1 / n_trials)
    c = z_crit(a)
    lo, hi = estimate - c * se, estimate + c * se
    outcome = "PRESENT" if lo > 0 else "ABSENT" if hi < meaningful else "INCONCLUSIVE"
    vs = "ABOVE" if lo >= meaningful else "BELOW" if hi < meaningful else "STRADDLES"
    return {"outcome": outcome, "lo": lo, "hi": hi, "t": estimate / se, "alpha_adj": a,
            "power_at_meaningful": power_of_z(meaningful / se, a), "vs_meaningful": vs}


# -- the book: judge a sleeve by what it adds --------------------------------

def marginal_gain(sr_new: float, sr_book: float, rho: float) -> float:
    """Positive iff a small allocation to the new sleeve raises the book's Sharpe.

    Algebra, not a market claim. For a book p and a sleeve k at weight w,
    d SR(p + w·k)/dw at w = 0 equals (σ_k/σ_p)·(SR_k − ρ·SR_p). A sleeve
    uncorrelated with the book helps at ANY positive Sharpe. This is the D5
    "inventory" principle in `docs/RESEARCH_STATE.md`, and the ρ·IR_c bar in
    `results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md`.
    """
    if not -1 <= rho <= 1:
        raise ValueError(f"rho must be in [-1, 1], got {rho}")
    return sr_new - rho * sr_book


def combined_sharpe(sr_book: float, sr_new: float, rho: float) -> float:
    """Maximum Sharpe of a book plus a new sleeve, both held LONG (weights ≥ 0).

    The unconstrained optimum, √((a² + b² − 2ρab)/(1 − ρ²)), is never below
    the book's Sharpe: it shorts any sleeve below ρ·SR_book. It therefore
    "admitted" a losing sleeve (1.0, −0.5, 0 → 1.118; review, 2026-10-27). So:
    if `marginal_gain(new, book, ρ) ≤ 0` the new sleeve gets zero weight and
    the answer is the book's own Sharpe, and symmetrically for the book.
    Otherwise use the unconstrained formula, whose weights are then both
    positive. At ρ = 0 that is √(a² + b²), so five unrelated 0.5s make about
    1.1. That holds before costs. Costs do not diversify (`pair-reversion` in
    the graveyard).
    """
    if not -1 < rho < 1:
        raise ValueError(f"rho must be in (-1, 1), got {rho}")
    if sr_book <= 0 and sr_new <= 0:
        raise ValueError("both Sharpes are non-positive; no long combination earns anything")
    if marginal_gain(sr_new, sr_book, rho) <= 0:
        return sr_book
    if marginal_gain(sr_book, sr_new, rho) <= 0:
        return sr_new
    return sqrt((sr_book ** 2 + sr_new ** 2 - 2 * rho * sr_book * sr_new) / (1 - rho ** 2))


# -- the range on rho: how sure we are of a sleeve's correlation with the book --

def stationary_bootstrap_indices(n: int, mean_block: float, reps: int, *, seed: int,
                                 chunk: int = 1_000):
    """Yield (k × n) index arrays of a Politis & Romano (1994) stationary bootstrap.

    Added 2026-10-28 for `scripts/research/reopen_book/` (the zero-trial re-open
    of NAV tenders and E1 by their contribution to the book). `marginal_gain`
    needs a RANGE on ρ, not a point, and a sparse event sleeve's correlation with
    the book is noisy, so the range has to come from a resample that keeps the
    series' dependence: blocks of geometric length with mean `mean_block`,
    wrapped circularly.

    The draw is the same as `scripts/cef/w4_artifacts.stationary_boot`'s, step
    for step and from the same random stream (a parity test pins it): the first
    index is uniform, each later one starts a new block with probability
    1/mean_block and otherwise continues the current block one step, modulo n.
    One implementation of the draw serves the mean, the Sharpe and the
    correlation, so the three cannot drift apart.
    """
    if n < 1 or mean_block < 1 or reps < 1 or chunk < 1:
        raise ValueError(f"need n, mean_block, reps, chunk >= 1; got n={n}, mean_block={mean_block}, "
                         f"reps={reps}, chunk={chunk}")
    rng = np.random.default_rng(seed)
    p = 1.0 / mean_block
    pos = np.arange(n)
    done = 0
    while done < reps:
        k = min(chunk, reps - done)
        starts = rng.integers(0, n, size=(k, n))
        new = rng.random((k, n)) < p
        new[:, 0] = True
        last = np.maximum.accumulate(np.where(new, pos[None, :], 0), axis=1)
        yield (np.take_along_axis(starts, last, axis=1) + (pos[None, :] - last)) % n
        done += k


def stationary_bootstrap_corr(x, y, mean_block: float, *, seed: int, reps: int = 10_000,
                              alpha: float = 0.05) -> dict:
    """Pearson ρ of two aligned series, with a stationary-bootstrap percentile interval.

    The PAIRS are resampled together, so each draw keeps whatever co-movement the
    two series share on a day, and the blocks keep each series' own persistence
    (an event sleeve that is idle for months, a book whose positions last weeks).
    The plain Fisher interval treats every day as independent, which daily P&L of
    held positions is not, so on daily data it is too narrow.

    Inputs are the P&L on common dates, already aligned: NaNs raise, and so does
    a length mismatch. A draw in which either series has zero variance has no
    correlation; it raises rather than being dropped, because a dropped draw
    shifts the interval and nobody would see it. Choose `mean_block` from the
    mechanism (how long a position lasts) and state why; report more than one.
    """
    a, b = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if a.ndim != 1 or a.shape != b.shape:
        raise ValueError(f"x and y must be aligned 1-D series of equal length, got {a.shape} and {b.shape}")
    if np.isnan(a).any() or np.isnan(b).any():
        raise ValueError("stationary_bootstrap_corr got NaNs; align on common dates first and report the drop")
    n = a.size
    if n < 3 * mean_block:
        raise ValueError(f"{n} observations for a mean block of {mean_block}: fewer than three blocks")
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    if a.std() == 0 or b.std() == 0:
        raise ValueError("a series has zero variance; its correlation is undefined")
    rho = float(np.corrcoef(a, b)[0, 1])
    draws = np.empty(reps)
    done = 0
    for idx in stationary_bootstrap_indices(n, mean_block, reps, seed=seed):
        xa, yb = a[idx], b[idx]
        xa = xa - xa.mean(axis=1, keepdims=True)
        yb = yb - yb.mean(axis=1, keepdims=True)
        sxx, syy = (xa * xa).sum(axis=1), (yb * yb).sum(axis=1)
        bad = (sxx == 0) | (syy == 0)
        if bad.any():
            raise ValueError(f"{int(bad.sum())} bootstrap draws have a zero-variance series (mean block "
                             f"{mean_block}); the correlation is undefined there")
        draws[done:done + len(idx)] = (xa * yb).sum(axis=1) / np.sqrt(sxx * syy)
        done += len(idx)
    lo, hi = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"rho": rho, "lo": float(lo), "hi": float(hi), "n": int(n), "mean_block": float(mean_block),
            "reps": int(reps), "seed": int(seed), "alpha": float(alpha), "draw_sd": float(draws.std(ddof=1))}


def fisher_corr_ci(r: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Fisher-z interval for a Pearson correlation of n INDEPENDENT pairs: tanh(atanh r ± z/√(n−3)).

    Use it on non-overlapping sums (weekly, 21-session), whose pairs are close to
    independent. On daily P&L of held positions it is too narrow; use
    `stationary_bootstrap_corr` there. Checked against scipy's
    `pearsonr(...).confidence_interval()` as a second method (test).
    """
    if n < 4:
        raise ValueError(f"Fisher interval needs n >= 4 pairs, got {n}")
    if not -1 < r < 1:
        raise ValueError(f"r must be in (-1, 1), got {r}")
    half = z_crit(alpha) / sqrt(n - 3)
    z = float(np.arctanh(r))
    return float(np.tanh(z - half)), float(np.tanh(z + half))


# -- overfitting: how likely the in-sample winner is noise -------------------

def pbo_cscv(pnl, S: int = 16) -> dict:
    """Probability of backtest overfitting by CSCV (Bailey, Borwein, López de Prado & Zhu).

    pnl is a T×N array: one column per trial configuration, the per-period P&L
    of each, on common dates. That is why every trial must store its daily P&L
    series, not just a verdict. The rows are cut into S contiguous blocks. For
    every split of the blocks into halves, take the in-sample best Sharpe and
    record the logit of its relative out-of-sample rank. PBO is the share of
    logits at or below zero, i.e. the winner ranking at or below the OOS median.
    C(16, 8) = 12,870 splits (the paper misprints 12,780). A high PBO says the
    selection was unreliable. It does not say the family has no skill: N
    similar good strategies also score high (the paper's own caveat).
    **The noise baseline is not always ½.** At or below the median counts as
    overfit, so under pure noise E[PBO] = ⌊(N+1)/2⌋/N: 0.667 at N = 3 and 0.6 at
    N = 5. It is returned as `null_pbo`, so compare against it, not against ½.
    Splits are processed in chunks so memory stays bounded at large N.
    """
    X = np.asarray(pnl, dtype=float)
    if X.ndim != 2:
        raise ValueError("pnl must be a T×N array")
    T, N = X.shape
    if S < 2 or S % 2:
        raise ValueError(f"S must be an even integer >= 2, got {S}")
    if N < 2 or T < 2 * S:
        raise ValueError(f"need N >= 2 trials and T >= 2S rows, got T={T}, N={N}, S={S}")
    if np.isnan(X).any():
        raise ValueError("pnl has NaNs; align the trials on common dates first")
    blocks = np.array_split(np.arange(T), S)
    cnt = np.array([len(b) for b in blocks], dtype=float)
    s1 = np.stack([X[b].sum(axis=0) for b in blocks])          # S×N
    s2 = np.stack([(X[b] ** 2).sum(axis=0) for b in blocks])

    def sharpe(idx):
        n = cnt[idx].sum(axis=1)[:, None]
        mu = s1[idx].sum(axis=1) / n
        var = s2[idx].sum(axis=1) / n - mu ** 2
        if (var <= 0).any():
            raise ValueError("a trial has zero variance on a half; it cannot be ranked")
        return mu / np.sqrt(var)

    combos = np.array(list(combinations(range(S), S // 2)))
    rest = np.array([sorted(set(range(S)) - set(c)) for c in combos])
    logits = np.empty(len(combos))
    step = max(1, int(2e7 // (S * N)))                     # ~160MB of float64 per array
    for i in range(0, len(combos), step):
        is_sr, oos_sr = sharpe(combos[i:i + step]), sharpe(rest[i:i + step])
        best = is_sr.argmax(axis=1)
        b = oos_sr[np.arange(len(best)), best][:, None]
        rank = (oos_sr < b).sum(axis=1) + 0.5 * ((oos_sr == b).sum(axis=1) - 1) + 1
        w = rank / (N + 1)
        logits[i:i + step] = np.log(w / (1 - w))
    return {"pbo": float((logits <= 0).mean()), "n_splits": len(combos),
            "logits": logits, "n_trials": N, "T": T, "S": S,
            "null_pbo": ((N + 1) // 2) / N}


def main(argv=None) -> int:
    """`python3 -m scripts.research.inference bars 52 --years 13 --sr 0.67`

    Prints the desk's bar beside the paper's for a counter's N, and the chance a
    true Sharpe clears each. It is a calculator for the power gate and reads
    no data.
    """
    ap = argparse.ArgumentParser(description=main.__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bars", help="desk vs Gumbel best-of-N bar, and P(pass)")
    b.add_argument("n", type=float)
    b.add_argument("--years", type=float)
    b.add_argument("--sr", type=float, help="hypothesised true annualised Sharpe")
    p = sub.add_parser("power", help="power to detect a true annualised Sharpe")
    p.add_argument("--sr", type=float, required=True)
    p.add_argument("--years", type=float, required=True)
    p.add_argument("--alpha", type=float, default=0.05)
    a = ap.parse_args(argv)
    if a.cmd == "bars":
        print(f"N={a.n:g}: desk bar sqrt(2 ln N) = {upper_bound_max_z(a.n):.3f}; "
              f"Gumbel E[max] = {expected_max_z(a.n):.3f}")
        if a.years and a.sr is not None:
            T = int(round(a.years * 252))
            for bound in ("upper", "gumbel"):
                print(f"  P(DSR > 0.95 | true SR {a.sr}, {a.years:g}y, normal returns, {bound}) = "
                      f"{p_pass_dsr(a.sr, T, a.n, bound=bound):.3f}")
    else:
        print(f"power = {sharpe_power(a.sr, a.years, a.alpha):.3f}; "
              f"years for 80% = {years_needed(a.sr, 0.8, a.alpha):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
