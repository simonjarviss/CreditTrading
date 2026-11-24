"""Is variant A's Sharpe really different from B's? Ledoit & Wolf's studentized
circular block bootstrap.

WHY THIS FILE EXISTS (2026-10-27). The loop compares a candidate with the
deployed book every day, and the textbook tests are the wrong tool for it. In
Ledoit & Wolf (2008), "Robust performance hypothesis testing with the Sharpe
ratio", Journal of Empirical Finance 15, 850-859, a true null of equal Sharpe
ratios was tested at nominal 5% (T=120, 5,000 repetitions):
  - the Jobson-Korkie test in Memmel's form rejected it 10.7% of the time under
    t6-IID data, 9.5% under Normal-VAR and 14.5% under t6-VAR;
  - the IID bootstrap rejected it 8.5% under Normal-VAR;
  - this method (Boot-TS) stayed at 4.8-5.7%.
On two real fund pairs, JKM rejected equality (p 3.9% and 1.0%) and Boot-TS did
not (9.2% and 29.4%). Tables 1 and 3 were re-read from the PDF, 3-0 verified on
2026-10-27. Testing a variant as a PAIRED difference against the book also needs
far less data than testing its own Sharpe against a fixed bar, because the
correlated noise cancels (MinTRL, Bailey & López de Prado 2012).

THE PROCEDURE, from the paper's §3 (text re-read 2026-10-27):
  v = (mu_1, mu_2, g_1, g_2), with g the mean of r^2
  Delta = f(v) = mu_1/sqrt(g_1 - mu_1^2) - mu_2/sqrt(g_2 - mu_2^2)
  grad f = (g_1/(g_1-mu_1^2)^1.5, -g_2/(g_2-mu_2^2)^1.5,
            -mu_1/(2 (g_1-mu_1^2)^1.5), mu_2/(2 (g_2-mu_2^2)^1.5))
  s(Delta_hat) = sqrt(grad' Psi grad / T)                                   Eq. (5)
  Psi on the original data: the prewhitened QS-kernel HAC estimate of
    y_t = (r_1t-mu_1, r_2t-mu_2, r_1t^2-g_1, r_2t^2-g_2), with the T/(T-4)
    adjustment (Andrews & Monahan 1992)
  bootstrap: the circular block bootstrap of the PAIRS with block b, and in
    each resample the 'natural' estimator Psi* = (1/l) sum_j zeta_j zeta_j',
    where zeta_j = b^{-1/2} sum over block j of y*_t and l = floor(T/b)
    (Götze & Künsch 1996)
  d = |Delta_hat| / s(Delta_hat)
  d*_m = |Delta*_m - Delta_hat| / s(Delta*_m)
  p = (#{d*_m >= d} + 1) / (M + 1)                                          Eq. (9)
  CI = Delta_hat +/- z*_{|.|,1-alpha} s(Delta_hat)                          Eq. (7)

THE BLOCK SIZE HAS NO DEFAULT. Algorithm 3.1 picks it by calibration
(`calibrate_block`). The paper used candidates {1,2,4,6,8,10} for T=120 monthly
observations. That says nothing about daily data, so the caller supplies the
candidates. The paper's semi-parametric model for monthly data is a VAR(1) with
time-series-bootstrapped residuals, and for daily data it suggests a bivariate
GARCH. This module uses the VAR(1) model for daily data too, with a stationary
bootstrap of the residuals (mean block 5, as in the paper). That is a stated
divergence; the stationary bootstrap keeps some of the volatility clustering a
GARCH would model.

WHAT IS NOT VERIFIED HERE. The paper tests only T=120 and only the difference of
two Sharpe ratios. That its size stays near nominal on thousands of daily
observations is untested (3-0 verified as an open question, 2026-10-27).
`test_resampling.py` measures size on synthetic IID data. That is a check on
this code, not a claim about the market.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

# Andrews & Monahan prewhitening needs the VAR(1) to be well inside the unit
# circle. 0.97 is the cap as recalled from their paper [U: not re-read]. It is
# used only to REFUSE, never to adjust, so it cannot move a result. It is
# checked on the EIGENVALUES (the spectral radius), which do not depend on
# scale. Singular values do: y mixes returns (~1e-2) with squared returns
# (~1e-4), and IID data showed a singular value near 7 (test_resampling, first
# run 2026-10-28).
PREWHITEN_MAX_RADIUS = 0.97


def _check(r1, r2) -> tuple[np.ndarray, np.ndarray]:
    a, b = np.asarray(r1, dtype=float), np.asarray(r2, dtype=float)
    if a.ndim != 1 or a.shape != b.shape:
        raise ValueError("r1 and r2 must be 1-d and of equal length (paired, same sessions)")
    if len(a) < 20:
        raise ValueError(f"{len(a)} paired observations is too few for a block bootstrap")
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("r1 or r2 holds NaN or inf; align the two series on common sessions first")
    if a.std() == 0 or b.std() == 0:
        raise ValueError("a constant series has no Sharpe ratio")
    return a, b


def _v(a, b):
    return np.array([a.mean(), b.mean(), (a * a).mean(), (b * b).mean()])


def _delta(v):
    return v[0] / np.sqrt(v[2] - v[0] ** 2) - v[1] / np.sqrt(v[3] - v[1] ** 2)


def _grad(v):
    s1, s2 = (v[2] - v[0] ** 2) ** 1.5, (v[3] - v[1] ** 2) ** 1.5
    return np.array([v[2] / s1, -v[3] / s2, -0.5 * v[0] / s1, 0.5 * v[1] / s2])


def _y(a, b, v):
    return np.column_stack([a - v[0], b - v[1], a * a - v[2], b * b - v[3]])


def hac_psi(y: np.ndarray) -> np.ndarray:
    """Prewhitened QS-kernel long-run covariance of the centred 4-vector y_t.

    The VAR(1) prewhitening is Andrews & Monahan's: fit y_t = A y_{t-1} + e_t,
    estimate the long-run covariance of e with the QS kernel and automatic
    bandwidth (`arch`), then recolour with (I-A)^{-1} Psi_e (I-A)^{-T}.
    df_adjust=4 is the paper's T/(T-4) factor for the four estimated means."""
    from arch.covariance.kernel import QuadraticSpectral
    y0, y1 = y[:-1], y[1:]
    A = np.linalg.lstsq(y0, y1, rcond=None)[0].T
    radius = float(np.abs(np.linalg.eigvals(A)).max())
    if radius > PREWHITEN_MAX_RADIUS:
        raise ValueError(f"the prewhitening VAR(1) has spectral radius {radius:.3f} > "
                         f"{PREWHITEN_MAX_RADIUS}; the series is too persistent for this estimator")
    e = y1 - y0 @ A.T
    # Bandwidth: arch's automatic choice, which is Newey & West (1994). The paper
    # allows that ("Andrews (1991) and Newey and West (1994)"), but Andrews &
    # Monahan pair prewhitening with Andrews' AR(1) plug-in, so this is a stated
    # divergence (quant-reviewer, 2026-10-28).
    psi_e = np.asarray(QuadraticSpectral(e, df_adjust=4, center=False).cov.long_run)
    inv = np.linalg.inv(np.eye(4) - A)
    return inv @ psi_e @ inv.T


def _cbb_index(T: int, block: int, M: int, rng) -> np.ndarray:
    """M circular-block-bootstrap index rows of length T: block starts are drawn
    uniformly, and blocks wrap around the end (Politis & Romano 1992)."""
    nb = -(-T // block)
    starts = rng.integers(0, T, size=(M, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % T
    return idx.reshape(M, nb * block)[:, :T]


MIN_BLOCKS = 4      # Psi* is 4x4: fewer than 4 block sums cannot make it full rank


def _boot_stats(a, b, block, M, rng):
    """Delta* and s(Delta*) for M resamples, with the natural block estimator.

    Refuses a block with fewer than MIN_BLOCKS complete blocks in the sample. With
    T // block = 0, Psi* was 0/0, so every S* was NaN. Then `dstar >= d` was never
    true, and the p-value collapsed to 1/(M+1): a false rejection (T=30, block=40,
    equal true Sharpe: p 0.005 against 0.88 at block 5; quant-reviewer, 2026-10-28)."""
    T = len(a)
    if T // block < MIN_BLOCKS:
        raise ValueError(f"block {block} leaves {T // block} complete block(s) in {T} observations; "
                         f"the natural estimator needs at least {MIN_BLOCKS}")
    I = _cbb_index(T, block, M, rng)
    A, B = a[I], b[I]                                      # M x T
    V = np.stack([A.mean(1), B.mean(1), (A * A).mean(1), (B * B).mean(1)], axis=1)
    s1, s2 = V[:, 2] - V[:, 0] ** 2, V[:, 3] - V[:, 1] ** 2
    ok = (s1 > 0) & (s2 > 0)
    if not ok.all():
        raise ValueError(f"{int((~ok).sum())} resample(s) had a zero variance; the series "
                         "is too short or too discrete for this block size")
    D = V[:, 0] / np.sqrt(s1) - V[:, 1] / np.sqrt(s2)
    Y = np.stack([A - V[:, [0]], B - V[:, [1]], A * A - V[:, [2]], B * B - V[:, [3]]], axis=2)
    l = T // block
    Z = Y[:, :l * block].reshape(M, l, block, 4).sum(axis=2) / np.sqrt(block)   # M x l x 4
    Psi = np.einsum("mlk,mlj->mkj", Z, Z) / l
    G = np.stack([V[:, 2] / s1 ** 1.5, -V[:, 3] / s2 ** 1.5,
                  -0.5 * V[:, 0] / s1 ** 1.5, 0.5 * V[:, 1] / s2 ** 1.5], axis=1)
    S = np.sqrt(np.einsum("mk,mkj,mj->m", G, Psi, G) / T)
    if not np.isfinite(S).all() or (S <= 0).any():
        raise ValueError("a bootstrap standard error is not finite and positive; refusing a p-value built on it")
    return D, S


def sharpe_diff(r1, r2, *, block: int, M: int, seed: int, alpha: float = 0.05,
                periods: int = 252) -> dict:
    """Test H0: SR_1 = SR_2 on paired per-period returns (Boot-TS).

    Returns the per-period and annualised difference, s(Delta_hat), the
    studentized statistic d, the p-value of Eq. (9), and the symmetric 1-alpha
    interval of Eq. (7), per period and annualised. `block` comes from
    `calibrate_block`; `M` is the number of resamples (the paper used 499 in
    simulation and 4,999 in application). Neither has a default."""
    if block < 1 or M < 99:
        raise ValueError("block must be >= 1 and M >= 99")
    a, b = _check(r1, r2)
    T = len(a)
    v = _v(a, b)
    d_hat = _delta(v)
    g = _grad(v)
    s = float(np.sqrt(g @ hac_psi(_y(a, b, v)) @ g / T))
    if not np.isfinite(s) or s <= 0:
        raise ValueError("the HAC standard error is not positive; are the two series identical?")
    D, S = _boot_stats(a, b, block, M, np.random.default_rng(seed))
    dstar = np.abs(D - d_hat) / S
    d = abs(d_hat) / s
    p = (int((dstar >= d).sum()) + 1) / (M + 1)
    zq = float(np.quantile(dstar, 1 - alpha))
    k = np.sqrt(periods)
    return dict(delta=d_hat, delta_annual=d_hat * k, se=s, d=d, p_value=p,
                ci=(d_hat - zq * s, d_hat + zq * s), ci_annual=((d_hat - zq * s) * k, (d_hat + zq * s) * k),
                z_boot=zq, z_normal=float(norm.ppf(1 - alpha / 2)), block=block, M=M, T=T,
                hac_p_value=float(2 * norm.sf(d)))


def _var1_pseudo(a, b, T, rng, mean_block=5):
    """One pseudo sequence from the fitted VAR(1), with its residuals
    resampled by the stationary bootstrap (Politis & Romano 1994)."""
    X = np.column_stack([a, b])
    Z = np.column_stack([np.ones(T - 1), X[:-1]])
    coef = np.linalg.lstsq(Z, X[1:], rcond=None)[0]       # 3 x 2
    E = X[1:] - Z @ coef
    n = len(E)
    idx = np.empty(T, dtype=int)
    j = rng.integers(n)
    for t in range(T):
        if t == 0 or rng.random() < 1.0 / mean_block:
            j = rng.integers(n)
        else:
            j = (j + 1) % n
        idx[t] = j
    out = np.empty((T, 2))
    out[0] = X[rng.integers(T)]
    for t in range(1, T):
        out[t] = coef[0] + out[t - 1] @ coef[1:] + E[idx[t]]
    return out[:, 0], out[:, 1]


def calibrate_block(r1, r2, *, candidates, K: int, M: int, seed: int,
                    alpha: float = 0.05) -> dict:
    """Ledoit & Wolf's Algorithm 3.1: pick the block size whose interval
    covers the pseudo-parameter Delta_hat at a rate closest to 1-alpha, on K
    pseudo sequences drawn from a VAR(1) with stationary-bootstrapped residuals.

    The paper calls K = 1,000 the lower limit and K = 5,000 enough. Below 1,000
    this raises, because a calibration that cannot tell coverage 0.93 from
    0.95 picks noise."""
    if K < 1000:
        raise ValueError("K below 1,000 is under the paper's lower limit for calibration")
    a, b = _check(r1, r2)
    T = len(a)
    short = [c for c in candidates if T // int(c) < MIN_BLOCKS]
    if short:
        raise ValueError(f"candidate block(s) {short} leave fewer than {MIN_BLOCKS} blocks in {T} observations")
    target = _delta(_v(a, b))
    rng = np.random.default_rng(seed)
    hits = {int(c): 0 for c in candidates}
    for _ in range(K):
        pa, pb = _var1_pseudo(a, b, T, rng)
        v = _v(pa, pb)
        dh = _delta(v)
        g = _grad(v)
        s = np.sqrt(g @ hac_psi(_y(pa, pb, v)) @ g / T)
        for c in hits:
            D, S = _boot_stats(pa, pb, c, M, rng)
            zq = np.quantile(np.abs(D - dh) / S, 1 - alpha)
            hits[c] += int(abs(dh - target) <= zq * s)
    g_hat = {c: h / K for c, h in hits.items()}
    best = min(g_hat, key=lambda c: (abs(g_hat[c] - (1 - alpha)), c))
    return dict(block=best, coverage=g_hat, K=K, M=M, alpha=alpha)
