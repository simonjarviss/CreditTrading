"""The exposure readout (`scripts/cef/exposure_readout.py`), on synthetic data only.

These test the CODE: the lookahead assert, the Dimson aggregation, the orthogonalisation,
the exposure arithmetic and its signs, the review flag, and every refusal path. They make
no claim about any fund or any market (CLAUDE.md: synthetic data tests a method, never
the world). No panel is read, no network is touched, and no account data is used.

Each test was run against a deliberately broken copy of the module (window including t,
lag 0 only, unsigned value, signed contribution, a default equity, the refusals and the
finite-data check removed, the orthogonalisation turned off) and failed there; the
session that built this recorded that check.

The review of 2026-11-02 (finding 2) found eight more broken copies that passed: price-only
returns, the distribution over today's close, the split ratio inverted or ignored, factor
vol not annualised or annualised by 360, a t-stat SE from the residual-covariance diagonal
only, group exposures on lag-0 betas, and P&L booked across a gap in the positions dates.
The tests under "arithmetic the first suite did not reach" kill each of them, and the tests
of the guard, equity, plateau, lag-rule and cross-check fixes each kill a copy with that fix
undone (checked 2026-11-02 by loading each broken copy in place of the module). One
survivor is equivalent, not missed: `total_factor_vol` with the covariance's diagonal only.
The orthogonal factors are uncorrelated on the window by construction, so the two agree.

THE RULE (the lead-placebo Dimson lag rule, declared 2026-11-02 before its first run): the
tests under "THE RULE" kill nine broken copies, checked by loading each in place of the
module: a tie counted as a pass, no stop at the first gap, the bound taken as the median
lead count, the bound taken as Binomial(52, 0.05), a censored L returned as K, the lag-0
check removed, the H13 cut removed (with and without its check), and the leads never
counted. Their synthetic fixture gave L = 2 on 19 of 20 other seeds and 3 on one, which is
what a 5% test should do.

AFTER THE RESULT (review of 2026-11-02): the tests under "diagnostics and the cache hash" pin
the cache the recorded counts came from and the diagnostics that frame the team lead's
choice (the episode mask, the year control, the trend test). They decide nothing: no test
there moves DIMSON_LAGS or touches THE RULE.

THE TEAM LEAD'S RULING (2026-11-03: keep DIMSON_LAGS = 0, MUNI the headline, TERM/CREDIT/LOANS
indicative): the tests under "the report's order" pin summary.md's order and the
muni-vs-taxable split. They were run against the first build's summary_md and failed there.
The ruling changed no computation; the session that recorded it diffed analyse's CSVs before
and after on synthetic positions files and found them byte-identical.
"""
from __future__ import annotations

import ast
import datetime as dt
import json
import math
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from dataclasses import replace

from scripts.cef import exposure_readout as ER

ETFS = list(ER.FACTOR_ETFS)
SESS = ER.nyse_sessions(dt.date(2020, 1, 2), dt.date(2020, 12, 31))
W, L = 60, 3


def _factor_returns(seed=0, sessions=SESS, corr=True):
    """Four ETF return series with realistic collinearity (MUB and HYG load on IEF; BKLN
    on HYG), so that the orthogonalisation has something to do."""
    rng = np.random.default_rng(seed)
    n = len(sessions)
    z = rng.normal(0, 0.004, size=(n, 4))
    ief = z[:, 0]
    hyg = z[:, 1] + (0.3 * ief if corr else 0)
    mub = z[:, 2] + (0.5 * ief + 0.2 * hyg if corr else 0)
    bkln = z[:, 3] + (0.6 * hyg if corr else 0)
    return pd.DataFrame({"IEF": ief, "HYG": hyg, "MUB": mub, "BKLN": bkln}, index=sessions)


def _lagged(s: pd.Series, l: int) -> pd.Series:
    return s.shift(l)


def _returns_with_names(seed=0):
    """R with the four ETFs and two names whose returns are exact lagged responses."""
    E = _factor_returns(seed)
    R = E.copy()
    # AAA: a pure TERM response spread over lags 0..3 (sum 1.1)
    R["AAA"] = (0.3 * E["IEF"] + 0.5 * _lagged(E["IEF"], 1) + 0.2 * _lagged(E["IEF"], 2)
                + 0.1 * _lagged(E["IEF"], 3))
    # BBB: a raw-MUB response at lag 1 plus small idiosyncratic noise
    rng = np.random.default_rng(seed + 1)
    R["BBB"] = 0.8 * _lagged(E["MUB"], 1) + rng.normal(0, 1e-4, len(E))
    return R


# --------------------------------------------------------------------------- H7

def test_assert_strictly_before_raises_on_a_window_reaching_t():
    t = SESS[100]
    ER.assert_strictly_before(SESS[40:100], t, "w")              # ends t-1: fine
    with pytest.raises(ER.LookaheadError, match="strictly before"):
        ER.assert_strictly_before(SESS[41:101], t, "w")          # includes t
    with pytest.raises(ER.LookaheadError):
        ER.assert_strictly_before(SESS[41:120], t, "w")          # runs past t
    with pytest.raises(ER.LookaheadError, match="empty"):
        ER.assert_strictly_before(SESS[:0], t, "w")


def test_window_rows_end_strictly_before_t_and_reach_the_lags():
    t = SESS[100]
    y, f = ER.window_rows(SESS, t, W, L)
    assert len(y) == W and len(f) == W + L
    assert y.max() < t and f.max() < t
    assert y[-1] == SESS[99] and f[0] == SESS[100 - W - L]


def test_fit_is_unchanged_by_any_data_on_or_after_t():
    """The readout's no-lookahead property, tested on output, not on the assert: scramble
    every return dated t or later and the fit used on t must not move by a bit."""
    R = _returns_with_names()
    t = SESS[150]
    a = ER.fit_window(R, SESS, t, ["AAA", "BBB"], window=W, lags=L)
    R2 = R.copy()
    rng = np.random.default_rng(99)
    R2.loc[t:] = rng.normal(0, 0.05, size=R2.loc[t:].shape)
    b = ER.fit_window(R2, SESS, t, ["AAA", "BBB"], window=W, lags=L)
    pd.testing.assert_frame_equal(a.beta, b.beta, check_exact=True)
    pd.testing.assert_frame_equal(a.M, b.M, check_exact=True)
    pd.testing.assert_series_equal(a.factor_vol, b.factor_vol, check_exact=True)
    assert a.y_dates.max() < t


# --------------------------------------------------------------------------- Dimson

def test_dimson_sum_recovers_a_response_spread_over_lags():
    R = _returns_with_names()
    fit = ER.fit_window(R, SESS, SESS[150], ["AAA"], window=W, lags=L)
    lags = [fit.beta.at["AAA", ("TERM", l)] for l in range(L + 1)]
    assert lags == pytest.approx([0.3, 0.5, 0.2, 0.1], abs=1e-9)
    assert fit.beta_sum.at["AAA", "TERM"] == pytest.approx(1.1, abs=1e-9)
    for k in ("CREDIT", "MUNI", "LOANS"):
        assert fit.beta_sum.at["AAA", k] == pytest.approx(0.0, abs=1e-9)


def test_dimson_sum_with_too_few_lags_misses_the_tail():
    """Guards the arithmetic, not the lag choice: with lags=1 the sum cannot see lags 2-3."""
    R = _returns_with_names()
    fit = ER.fit_window(R, SESS, SESS[150], ["AAA"], window=W, lags=1)
    assert fit.beta_sum.at["AAA", "TERM"] == pytest.approx(0.8, abs=0.05)


def test_ols_standard_error_identity_matches_statsmodels_for_one_name():
    sm = pytest.importorskip("statsmodels.api")
    R = _returns_with_names()
    t = SESS[150]
    fit = ER.fit_window(R, SESS, t, ["BBB"], window=W, lags=L)
    ex = ER.exposures(fit, pd.Series({"BBB": 1.0}), equity=None).set_index("factor")
    X, cols = ER.design((R.loc[fit.f_dates, ETFS] @ fit.M).set_axis(list(ER.FACTOR_NAMES), axis=1),
                        fit.y_dates, L)
    m = sm.OLS(R.loc[fit.y_dates, "BBB"].to_numpy(), X).fit()
    for k in ER.FACTOR_NAMES:
        a = np.array([1.0 if (c != "const" and c[0] == k) else 0.0 for c in cols])
        tt = m.t_test(a)
        assert ex.at[k, "t_stat"] == pytest.approx(float(np.ravel(tt.tvalue)[0]), rel=1e-8)


# --------------------------------------------------------------------------- orthogonalisation

def test_orthogonal_factors_are_uncorrelated_on_their_window():
    E = _factor_returns()
    M = ER.orthogonaliser(E.iloc[:W])
    F = E.iloc[:W] @ M
    C = np.cov(F.to_numpy().T)
    off = C - np.diag(np.diag(C))
    assert np.abs(off).max() < 1e-12 * np.abs(np.diag(C)).max() * 1e3
    assert list(M.columns) == list(ER.FACTOR_NAMES)
    assert all(M.at[e, f] == 1.0 for f, e in ER.FACTORS)
    # the raw ETFs here ARE correlated, so the orthogonaliser must have done something
    assert abs(np.corrcoef(E.iloc[:W]["IEF"], E.iloc[:W]["MUB"])[0, 1]) > 0.2


def test_total_factor_pnl_is_the_same_in_the_raw_basis():
    """Orthogonalising changes the split, never the total: E_orth . f_orth(t) equals the
    raw-ETF regression's summed betas . raw f(t), for any out-of-window day."""
    R = _returns_with_names()
    t = SESS[150]
    fit = ER.fit_window(R, SESS, t, ["BBB"], window=W, lags=L)
    v = pd.Series({"BBB": -2500.0})
    E = ER.exposures(fit, v, None).set_index("factor")["exposure_usd"]
    f_raw = R.loc[t, ETFS]
    total_orth = float(E.to_numpy() @ (f_raw.to_numpy() @ fit.M.to_numpy()))
    # the raw basis, fitted directly
    Er = R.loc[fit.f_dates, ETFS]
    Xr, cols = ER.design(Er, fit.y_dates, L)
    b = np.linalg.lstsq(Xr, R.loc[fit.y_dates, "BBB"].to_numpy(), rcond=None)[0]
    raw_sum = {e: sum(b[i] for i, c in enumerate(cols) if c != "const" and c[0] == e) for e in ETFS}
    total_raw = float(sum(-2500.0 * raw_sum[e] * f_raw[e] for e in ETFS))
    assert total_orth == pytest.approx(total_raw, rel=1e-9, abs=1e-12)


# --------------------------------------------------------------------------- exposure, signs, rule

def _fit_with(beta_sum: dict, vols: dict, names=("LNG", "SHT")):
    """A WindowFit with chosen summed betas (lag 0 only) and factor vols."""
    cols = ["const"] + [(k, l) for k in ER.FACTOR_NAMES for l in range(1)]
    idx = pd.MultiIndex.from_tuples(cols[1:], names=["factor", "lag"])
    beta = pd.DataFrame([[beta_sum[n][k] for k in ER.FACTOR_NAMES] for n in names],
                        index=list(names), columns=idx)
    bs = pd.DataFrame([[beta_sum[n][k] for k in ER.FACTOR_NAMES] for n in names],
                      index=list(names), columns=list(ER.FACTOR_NAMES))
    fv = pd.Series(vols)[list(ER.FACTOR_NAMES)]
    return ER.WindowFit(t=SESS[100], y_dates=SESS[40:100], f_dates=SESS[40:100],
                        M=pd.DataFrame(np.eye(4), index=ETFS, columns=list(ER.FACTOR_NAMES)),
                        beta=beta, beta_sum=bs, cols=cols, xtx_inv=np.eye(len(cols)),
                        resid_cov=pd.DataFrame(np.eye(len(names)) * 1e-4, index=list(names), columns=list(names)),
                        factor_vol=fv, factor_cov=pd.DataFrame(np.diag(fv ** 2), index=fv.index, columns=fv.index),
                        n_obs=60, lags=0)


BETAS = {"LNG": {"TERM": 0.1, "CREDIT": 1.0, "MUNI": 0.2, "LOANS": 0.5},
         "SHT": {"TERM": 0.6, "CREDIT": 0.5, "MUNI": 1.5, "LOANS": 0.1}}
VOLS = {"TERM": 0.05, "CREDIT": 0.06, "MUNI": 0.02, "LOANS": 0.03}


def test_exposure_is_signed_shares_times_close_times_beta():
    fit = _fit_with(BETAS, VOLS)
    shares = pd.Series({"LNG": 1000.0, "SHT": -2000.0})
    close = pd.Series({"LNG": 10.0, "SHT": 12.5})
    ex = ER.exposures(fit, shares * close, equity=100_000.0).set_index("factor")
    # MUNI: 10,000 x 0.2 + (-25,000) x 1.5 = -35,500: the short dominates, sign negative
    assert ex.at["MUNI", "exposure_usd"] == pytest.approx(10_000 * 0.2 - 25_000 * 1.5)
    assert ex.at["MUNI", "exposure_usd"] < 0
    assert ex.at["CREDIT", "exposure_usd"] == pytest.approx(10_000 * 1.0 - 25_000 * 0.5)
    assert ex.at["MUNI", "exposure_frac"] == pytest.approx(-35_500 / 100_000)
    # contribution uses |E|: a short exposure contributes risk, never negative risk
    assert ex.at["MUNI", "contrib_frac"] == pytest.approx(0.355 * 0.02)
    assert ex.at["MUNI", "contrib_usd"] == pytest.approx(35_500 * 0.02)
    assert ex.at["MUNI", "contrib_of_target"] == pytest.approx(0.355 * 0.02 / ER.VOL_TARGET)
    assert (ex["contrib_frac"] >= 0).all()


def test_review_flag_fires_above_the_line_on_a_short_exposure_and_not_below():
    """The line is REVIEW_FRACTION x the vol target x the book's sizing multiplier (team lead,
    2026-11-10; the fit's book is the core's). Equity is chosen so the short MUNI exposure
    sits just above it, then just below it."""
    fit = _fit_with(BETAS, VOLS)
    value = pd.Series({"LNG": 0.0, "SHT": -25_000.0})        # MUNI E = -37,500
    line = ER.CORE.review_line
    assert line == ER.REVIEW_FRACTION * ER.VOL_TARGET * ER.CORE.multiplier
    E_muni = -25_000.0 * 1.5
    eq_at_line = abs(E_muni) * VOLS["MUNI"] / line
    above = ER.exposures(fit, value, equity=eq_at_line * 0.99).set_index("factor")
    below = ER.exposures(fit, value, equity=eq_at_line * 1.01).set_index("factor")
    assert above.at["MUNI", "review"] == "REVIEW"
    assert below.at["MUNI", "review"] == "within"
    m = ER.CORE.multiplier
    assert above.at["MUNI", "contrib_of_target"] > ER.REVIEW_FRACTION * m > below.at["MUNI", "contrib_of_target"]


def test_review_line_follows_the_vol_target_it_is_given():
    fit = _fit_with(BETAS, VOLS)
    value = pd.Series({"LNG": 0.0, "SHT": -25_000.0})
    eq = 100_000.0
    c = 37_500 / eq * VOLS["MUNI"]                            # 0.0075
    m = ER.CORE.multiplier
    lo = ER.exposures(fit, value, eq, vol_target=c / ER.REVIEW_FRACTION / m * 1.01).set_index("factor")
    hi = ER.exposures(fit, value, eq, vol_target=c / ER.REVIEW_FRACTION / m * 0.99).set_index("factor")
    assert lo.at["MUNI", "review"] == "within" and hi.at["MUNI", "review"] == "REVIEW"


def test_review_line_follows_the_multiplier_it_is_given():
    """Ruling A (team lead, 2026-11-10): the line is REVIEW_FRACTION x vol target x m. With the
    vol target fixed, a multiplier just below c / (REVIEW_FRACTION x target) flags and one just
    above does not; c/target is the same number either way (it stays over the target). Fails
    on the parent commit, whose `exposures` had no multiplier."""
    fit = _fit_with(BETAS, VOLS)
    value = pd.Series({"LNG": 0.0, "SHT": -25_000.0})
    eq = 100_000.0
    c = 37_500 / eq * VOLS["MUNI"]
    m_at = c / (ER.REVIEW_FRACTION * ER.VOL_TARGET)
    hi = ER.exposures(fit, value, eq, multiplier=m_at * 0.99).set_index("factor")
    lo = ER.exposures(fit, value, eq, multiplier=m_at * 1.01).set_index("factor")
    assert hi.at["MUNI", "review"] == "REVIEW" and lo.at["MUNI", "review"] == "within"
    assert hi.at["MUNI", "contrib_of_target"] == lo.at["MUNI", "contrib_of_target"] == pytest.approx(c / ER.VOL_TARGET)


def test_the_vol_target_default_is_the_fits_own_book_like_the_multiplier():
    """Nit of the independent review of PR #82 (2026-11-11): `exposures` took its default
    multiplier from the fit's book (`fit.fs`) but its default vol target from the core's
    VOL_TARGET, so a caller could read one book's line with two books' parameters. Both now
    come from `fit.fs`. A fit whose book's vol target is twice the core's shows it: called
    with no vol target, the readings equal those with the book's own passed explicitly, and
    MUNI's c/target is over that book's target. Fails on the parent commit."""
    import dataclasses
    other = dataclasses.replace(ER.CORE, book="other", vol_target=2 * ER.VOL_TARGET, sizing_multiplier=None)
    fit = dataclasses.replace(_fit_with(BETAS, VOLS), fs=other)
    value = pd.Series({"LNG": 0.0, "SHT": -25_000.0})
    eq = 100_000.0
    c = 37_500 / eq * VOLS["MUNI"]
    ex = ER.exposures(fit, value, eq).set_index("factor")
    explicit = ER.exposures(fit, value, eq, vol_target=other.vol_target, multiplier=other.multiplier).set_index("factor")
    pd.testing.assert_frame_equal(ex, explicit)
    assert ex.at["MUNI", "contrib_of_target"] == pytest.approx(c / other.vol_target)
    assert ex.at["MUNI", "review"] == ("REVIEW" if c > ER.REVIEW_FRACTION * other.vol_target * other.multiplier
                                       else "within")


def test_no_equity_means_unmeasured_never_a_default_capital():
    fit = _fit_with(BETAS, VOLS)
    ex = ER.exposures(fit, pd.Series({"LNG": 5_000.0, "SHT": -25_000.0}), equity=None)
    assert (ex["review"] == "UNMEASURED").all()
    assert ex["exposure_frac"].isna().all() and ex["contrib_of_target"].isna().all()
    assert ex["exposure_usd"].notna().all()                   # dollars need no equity


def test_total_factor_vol_is_the_root_sum_of_squared_contributions_when_orthogonal():
    fit = _fit_with(BETAS, VOLS)
    ex = ER.exposures(fit, pd.Series({"LNG": 10_000.0, "SHT": -25_000.0}), 100_000.0).set_index("factor")
    tv = ER.total_factor_vol(fit, ex["exposure_usd"])
    assert tv == pytest.approx(math.sqrt((ex["contrib_usd"] ** 2).sum()))


# --------------------------------------------------------------------------- end to end

def _px_from_returns(R: pd.DataFrame, base=50.0) -> pd.DataFrame:
    rows = []
    for tk in R.columns:
        r = R[tk].fillna(0.0).to_numpy()
        close = base * np.cumprod(1.0 + r)
        rows.append(pd.DataFrame({"date": R.index, "ticker": tk, "close": close, "adj_close": close,
                                  "dividend": 0.0, "split": 0.0}))
    return pd.concat(rows, ignore_index=True)


def _positions(dates, book, equity=100_000.0):
    return pd.DataFrame([dict(date=d, symbol=s, shares=q, equity=equity) for d in dates for s, q in book.items()])


def test_readout_factor_pnl_is_previous_exposure_times_todays_factor_return():
    R = _returns_with_names()
    px = _px_from_returns(R)
    dates = list(SESS[150:153])
    P = _positions(dates, {"AAA": 1000.0, "BBB": -400.0})
    ro = ER.readout(px, P, {"AAA": "multi", "BBB": "muni"}, window=W, lags=L)
    R2, C2, _ = ER.returns_panel(px)
    fp = ro.factor_pnl[ro.factor_pnl["scope"] == "book"]
    assert sorted(fp["date"].unique()) == dates[1:]           # needs the previous session's book
    for t_prev, t in zip(dates[:-1], dates[1:]):
        fit = ER.fit_window(R2, SESS, t_prev, ["AAA", "BBB"], window=W, lags=L)
        v = pd.Series({"AAA": 1000.0, "BBB": -400.0}) * C2.loc[t_prev, ["AAA", "BBB"]]
        E = v.to_numpy() @ fit.beta_sum.to_numpy()
        f = R2.loc[t, ETFS].to_numpy() @ fit.M.to_numpy()
        got = fp[fp["date"] == t].set_index("factor")["pnl_summed"].reindex(list(ER.FACTOR_NAMES))
        assert got.to_numpy() == pytest.approx(E * f, rel=1e-10, abs=1e-12)
    # group scopes add up to the book
    g = ro.factor_pnl[ro.factor_pnl["scope"] != "book"].groupby(["date", "factor"])[["pnl_summed", "pnl_lagdist"]].sum()
    b = fp.set_index(["date", "factor"])[["pnl_summed", "pnl_lagdist"]]
    pd.testing.assert_frame_equal(g.sort_index(), b.sort_index(), check_exact=False, rtol=1e-10)


def test_readout_lag_distributed_pnl_reproduces_an_exact_lagged_response():
    """AAA's return is an exact lag-0..3 function of IEF, so the lag-distributed factor
    P&L of a 1-share AAA book on t equals that share's price change on t."""
    R = _returns_with_names()
    px = _px_from_returns(R)
    dates = list(SESS[150:152])
    ro = ER.readout(px, _positions(dates, {"AAA": 1.0}), {"AAA": "multi"}, window=W, lags=L)
    R2, C2, _ = ER.returns_panel(px)
    fp = ro.factor_pnl[(ro.factor_pnl["scope"] == "book")]
    pnl = fp["pnl_lagdist"].sum()
    assert pnl == pytest.approx(C2.loc[dates[1], "AAA"] - C2.loc[dates[0], "AAA"], rel=1e-8)


# --------------------------------------------------------------------------- arithmetic the
# first suite did not reach (review 2026-11-02, finding 2: eight mutants of these lines passed)

def _flat_px(ticker="AAA", n=10, close=50.0):
    d = SESS[:n]
    return pd.DataFrame({"date": d, "ticker": ticker, "close": close, "adj_close": close,
                         "dividend": 0.0, "split": 0.0})


def test_total_return_adds_the_distribution_over_the_previous_close():
    """H15: r = close_t / close_{t-1} - 1 + D_t / close_{t-1}, on the ex-date."""
    px = _flat_px()
    m = px["date"] == SESS[5]
    px.loc[m, "close"] = 49.6
    px.loc[m, "dividend"] = 0.5
    R, _, _ = ER.returns_panel(px)
    assert R.at[SESS[5], "AAA"] == pytest.approx((49.6 + 0.5) / 50.0 - 1.0, rel=1e-12, abs=1e-15)
    assert R.at[SESS[6], "AAA"] == pytest.approx(50.0 / 49.6 - 1.0, rel=1e-12)
    assert R.at[SESS[4], "AAA"] == 0.0 and np.isnan(R.at[SESS[0], "AAA"])


def test_total_return_multiplies_by_the_split_ratio_on_a_raw_close():
    """A 2-for-1 split on a raw (unadjusted) close: 50 -> 25.2 is a +0.8% day, not -49.6%."""
    px = _flat_px()
    m = px["date"] == SESS[5]
    px.loc[m, "close"] = 25.2
    px.loc[m, "split"] = 2.0
    px.loc[px["date"] > SESS[5], "close"] = 25.2
    R, _, _ = ER.returns_panel(px)
    assert R.at[SESS[5], "AAA"] == pytest.approx(25.2 * 2.0 / 50.0 - 1.0, rel=1e-12)
    assert R.at[SESS[6], "AAA"] == 0.0


def test_factor_vol_is_the_window_sd_of_the_orthogonal_factors_annualised_by_252():
    """sigma_k = sd(F_k on the W sessions before t) x sqrt(252): on the y rows only (not the
    W + L lagged rows), and annualised exactly once, by the desk's 252."""
    R = _returns_with_names()
    t = SESS[150]
    fit = ER.fit_window(R, SESS, t, ["AAA"], window=W, lags=L)
    F = R.loc[fit.y_dates, ETFS] @ ER.orthogonaliser(R.loc[fit.y_dates, ETFS])
    want = F.std(ddof=1).to_numpy() * math.sqrt(252)
    assert fit.factor_vol.to_numpy() == pytest.approx(want, rel=1e-12)
    assert np.diag(fit.factor_cov.to_numpy()) == pytest.approx(want ** 2, rel=1e-12)
    # and the readout's contribution uses that annualised vol
    px = _px_from_returns(R)
    ro = ER.readout(px, _positions([t], {"AAA": 100.0}), {"AAA": "multi"}, window=W, lags=L)
    R2, C2, _ = ER.returns_panel(px)
    fit2 = ER.fit_window(R2, SESS, t, ["AAA"], window=W, lags=L)
    F2 = R2.loc[fit2.y_dates, ETFS] @ fit2.M
    ex = ro.exposure.set_index("factor")
    E = 100.0 * C2.at[t, "AAA"] * fit2.beta_sum.loc["AAA"]
    for j, k in enumerate(ER.FACTOR_NAMES):
        sig = float(F2.iloc[:, j].std(ddof=1)) * math.sqrt(252)
        assert ex.at[k, "factor_vol"] == pytest.approx(sig, rel=1e-12)
        assert ex.at[k, "contrib_frac"] == pytest.approx(abs(E[k]) / 100_000.0 * sig, rel=1e-10)


def _correlated_names(seed=7):
    """AAA and BBB plus two names CCC, DDD whose residuals share a common shock, so a
    portfolio's residual variance carries cross terms."""
    R = _returns_with_names(seed)
    rng = np.random.default_rng(seed + 10)
    common = rng.normal(0, 0.003, len(R))
    R["CCC"] = 0.5 * R["IEF"] + 0.2 * _lagged(R["HYG"], 1) + common + rng.normal(0, 0.001, len(R))
    R["DDD"] = 0.7 * _lagged(R["MUB"], 1) + 0.9 * common + rng.normal(0, 0.001, len(R))
    return R


def test_book_t_stat_equals_the_portfolio_return_regression_with_correlated_residuals():
    """t = E_k / SE with SE^2 = (v' S v) a' (X'X)^-1 a is the OLS t-test on the portfolio's
    own return series v'Y: the cross-name residual covariance counts, not just its diagonal."""
    sm = pytest.importorskip("statsmodels.api")
    R = _correlated_names()
    t = SESS[150]
    names = ["CCC", "DDD"]
    fit = ER.fit_window(R, SESS, t, names, window=W, lags=L)
    v = pd.Series({"CCC": 3_000.0, "DDD": 2_000.0})          # same sign: the common shock adds
    ex = ER.exposures(fit, v, equity=None).set_index("factor")
    X, cols = ER.design((R.loc[fit.f_dates, ETFS] @ fit.M).set_axis(list(ER.FACTOR_NAMES), axis=1),
                        fit.y_dates, L)
    port = R.loc[fit.y_dates, names].to_numpy() @ v[names].to_numpy()
    m = sm.OLS(port, X).fit()
    for k in ER.FACTOR_NAMES:
        a = np.array([1.0 if (c != "const" and c[0] == k) else 0.0 for c in cols])
        assert ex.at[k, "t_stat"] == pytest.approx(float(np.ravel(m.t_test(a).tvalue)[0]), rel=1e-8)
    # the residuals really are correlated, so a diagonal-only SE would differ
    S = fit.resid_cov.to_numpy()
    assert S[0, 1] / math.sqrt(S[0, 0] * S[1, 1]) > 0.5


def test_group_exposures_use_the_summed_dimson_betas_and_add_up_to_the_book():
    R = _correlated_names()
    px = _px_from_returns(R)
    dates = list(SESS[150:152])
    book = {"AAA": 1000.0, "CCC": 500.0, "DDD": -800.0}
    groups = {"AAA": "multi", "CCC": "multi", "DDD": "muni"}
    ro = ER.readout(px, _positions(dates, book), groups, window=W, lags=L)
    R2, C2, _ = ER.returns_panel(px)
    for t in dates:
        fit = ER.fit_window(R2, SESS, t, list(book), window=W, lags=L)
        v = pd.Series(book) * C2.loc[t, list(book)]
        g = ro.by_group[ro.by_group["date"] == t].set_index(["grp", "factor"])["exposure_usd"]
        for grp in ("multi", "muni"):
            mem = [s for s in book if groups[s] == grp]
            want = v[mem].to_numpy() @ fit.beta_sum.loc[mem].to_numpy()
            got = g.xs(grp, level="grp").reindex(list(ER.FACTOR_NAMES)).to_numpy()
            assert got == pytest.approx(want, rel=1e-10)
        tot = g.groupby(level="factor").sum().reindex(list(ER.FACTOR_NAMES)).to_numpy()
        ex = ro.exposure[ro.exposure["date"] == t].set_index("factor")["exposure_usd"]
        assert tot == pytest.approx(ex.reindex(list(ER.FACTOR_NAMES)).to_numpy(), rel=1e-10)
    # AAA's response is spread over lags, so a lag-0 beta would not be the sum
    assert abs(fit.beta.at["AAA", ("TERM", 0)] - fit.beta_sum.at["AAA", "TERM"]) > 0.5


def test_factor_pnl_needs_the_immediately_previous_session_in_the_positions():
    """E(t-1) x f(t) needs the book at t-1's close. Across a gap in the positions dates no
    P&L is booked: an older book is not t-1's book."""
    R = _returns_with_names()
    px = _px_from_returns(R)
    gap = [SESS[150], SESS[152]]
    ro = ER.readout(px, _positions(gap, {"AAA": 1.0}), {"AAA": "multi"}, window=W, lags=L)
    assert len(ro.factor_pnl) == 0
    some = [SESS[150], SESS[151], SESS[153]]
    ro = ER.readout(px, _positions(some, {"AAA": 1.0}), {"AAA": "multi"}, window=W, lags=L)
    assert sorted(ro.factor_pnl["date"].unique()) == [SESS[151]]
    assert set(ro.factor_pnl["prev"]) == {SESS[150]}


# --------------------------------------------------------------------------- plateau check

def test_plateau_check_brackets_w_and_l_and_reports_review_counts():
    R = _returns_with_names()
    px = _px_from_returns(R)
    dates = list(SESS[150:153])
    P = _positions(dates, {"AAA": 20_000.0, "BBB": -40_000.0}, equity=100_000.0)
    groups = {"AAA": "multi", "BBB": "muni"}
    ro = ER.readout(px, P, groups, window=W, lags=L)
    rows = ER.plateau_check(px, P, groups, ro)
    runs = [(r["window"], r["lags"]) for r in rows]
    assert runs == [(W // 2, L), (W, L), (2 * W, L)] + [(W, l) for l in range(L + ER.PLATEAU_LAG_SPAN + 1)
                                                         if l != L]
    assert [r["adopted"] for r in rows] == [r == (W, L) for r in runs]
    adopted = rows[1]
    rev = ro.exposure[ro.exposure["review"] == "REVIEW"]
    assert adopted["review"] == {k: int(rev.loc[rev["factor"] == k, "date"].nunique()) for k in ER.FACTOR_NAMES}
    big = rev[rev["t_stat"].abs() >= 2.0]
    assert adopted["review_t2"] == {k: int(big.loc[big["factor"] == k, "date"].nunique()) for k in ER.FACTOR_NAMES}
    assert len(big) < len(rev)                                # the |t| filter bites on this book
    assert sum(adopted["review"].values()) > 0                # the book is large enough to flag
    assert adopted["book_summed"] == pytest.approx(
        ro.factor_pnl.loc[ro.factor_pnl["scope"] == "book", "pnl_summed"].sum())
    for r in rows[3:]:                                        # each lag row is its own readout
        other = ER.readout(px, P, groups, window=W, lags=r["lags"])
        assert r == dict(ER.plateau_summary(other), adopted=False)
    md = ER.summary_md(ro, {"asof": "x", "fetched_at_utc": "y"}, rows)
    assert "REVIEW dates TERM/CREDIT/MUNI/LOANS" in md and "(adopted)" in md


def test_plateau_counts_say_unmeasured_without_equity():
    R = _returns_with_names()
    px = _px_from_returns(R)
    P = _positions(list(SESS[150:152]), {"AAA": 1.0}).drop(columns=["equity"])
    ro = ER.readout(px, P, {"AAA": "multi"}, window=W, lags=L)
    s = ER.plateau_summary(ro)
    assert s["review"] is None and s["review_t2"] is None


# --------------------------------------------------------------------------- the report's order
# (team lead, 2026-11-03: keep DIMSON_LAGS = 0, MUNI is the headline, TERM/CREDIT/LOANS indicative)

def _two_group_book():
    """A book short two muni-group names and long two taxable ones, with equity, so MUNI has
    a muni side and a taxable side and the rule is measured."""
    R = _correlated_names()
    px = _px_from_returns(R)
    dates = list(SESS[150:153])
    book = {"AAA": 20_000.0, "CCC": 20_000.0, "BBB": -40_000.0, "DDD": -30_000.0}
    groups = {"AAA": "multi", "CCC": "hy", "BBB": "muni", "DDD": "muni"}
    return px, dates, book, groups


def test_summary_leads_with_muni_and_puts_term_credit_loans_under_indicative():
    """The first section after the header is MUNI's: its reading against the rule, its
    exposure, vol contribution and flag per date, and the muni-vs-taxable group reading, in
    that order. No TERM, CREDIT or LOANS reading appears before INDICATIVE_HEADING; after it
    each of the three has its rule line and a row per date. The plateau check stays last.
    The first build's summary (rule, then all four factors interleaved, TERM first) fails."""
    px, dates, book, groups = _two_group_book()
    ro = ER.readout(px, _positions(dates, book), groups, window=W, lags=L)
    md = ER.summary_md(ro, {"asof": "x", "fetched_at_utc": "y"},
                       [dict(ER.plateau_summary(ro), adopted=True)])
    lines = md.splitlines()
    h2 = [s for s in lines if s.startswith("## ")]
    assert h2[0] == "## Headline: MUNI"
    assert h2.count(f"## {ER.INDICATIVE_HEADING}") == 1
    assert ER.INDICATIVE_HEADING == "Indicative: depends on the lag choice (see DIMSON_LAGS docstring)"
    assert h2[-1].startswith("## Plateau check")
    cut = lines.index(f"## {ER.INDICATIVE_HEADING}")
    head, tail = lines[:cut], lines[cut:]

    # nothing of TERM, CREDIT or LOANS is read before the indicative heading
    assert ER.INDICATIVE_FACTORS == ("TERM", "CREDIT", "LOANS")
    for k in ER.INDICATIVE_FACTORS:
        assert not [s for s in head if f"| {k} |" in s or f"{k}: " in s or f"**{k}" in s], k

    # MUNI's rule line, then its per-date rows (exposure, vol contribution, flag), then the
    # group reading, all in the head and in that order
    ex = ro.exposure.set_index(["date", "factor"])
    rule_at = next(i for i, s in enumerate(head) if s.startswith(("- **MUNI: REVIEW", "- MUNI: within")))
    rows_at = []
    for d in dates:
        r = ex.loc[(d, "MUNI")]
        want = (f"| {d.date()} | MUNI | {ER._fmt_money(r['exposure_usd'])} | {r['exposure_frac']:+.3f} | "
                f"{r['factor_vol']:.4f} | {r['contrib_of_target']:.3f} | {r['t_stat']:+.2f} | "
                f"{r['d4_literal_breach']} | {r['review']} |")
        rows_at.append(head.index(want))
    grp_at = head.index("### MUNI exposure: the muni group against the taxable groups")
    assert rule_at < min(rows_at) and max(rows_at) < grp_at
    mv = ER.muni_vs_taxable(ro).set_index("date")
    for d in dates:
        assert any(s.startswith(f"| {d.date()} | {ER._fmt_money(mv.at[d, 'muni_usd'])} | ")
                   and f"| {ER._fmt_money(mv.at[d, 'book_usd'])} |" in s for s in head[grp_at:])

    # the three indicative factors, each read against the rule and on every date, after the cut
    for k in ER.INDICATIVE_FACTORS:
        assert [s for s in tail if s.startswith((f"- **{k}: REVIEW", f"- {k}: within"))], k
        for d in dates:
            assert [s for s in tail if s.startswith(f"| {d.date()} | {k} |")], (k, d)
    assert not [s for s in tail if "| MUNI |" in s and s.startswith("| 20")]

    # without equity MUNI still leads, and its UNMEASURED line comes before the cut
    P = _positions(dates, book).drop(columns=["equity"])
    md0 = ER.summary_md(ER.readout(px, P, groups, window=W, lags=L), {"asof": "x", "fetched_at_utc": "y"})
    l0 = md0.splitlines()
    assert [s for s in l0 if s.startswith("## ")][0] == "## Headline: MUNI"
    assert l0.index("- UNMEASURED on 3 date(s): no equity in the positions file.") < \
        l0.index(f"## {ER.INDICATIVE_HEADING}")


def test_muni_vs_taxable_adds_up_to_the_book_and_names_a_side_not_held():
    px, dates, book, groups = _two_group_book()
    ro = ER.readout(px, _positions(dates, book, equity=250_000.0), groups, window=W, lags=L)
    mv = ER.muni_vs_taxable(ro).set_index("date")
    bg = ro.by_group[ro.by_group["factor"] == "MUNI"]
    for d in dates:
        g = bg[bg["date"] == d].set_index("grp")["exposure_usd"]
        assert mv.at[d, "muni_usd"] == pytest.approx(g["muni"], rel=1e-12)
        assert mv.at[d, "taxable_usd"] == pytest.approx(g["hy"] + g["multi"], rel=1e-12)
        assert mv.at[d, "muni_usd"] + mv.at[d, "taxable_usd"] == pytest.approx(mv.at[d, "book_usd"], rel=1e-10)
        assert mv.at[d, "taxable_frac"] == pytest.approx(mv.at[d, "taxable_usd"] / 250_000.0, rel=1e-12)
        assert mv.at[d, "taxable_by_group"] == {"hy": g["hy"], "multi": g["multi"]}
    # no muni name held: that side says so, it is not printed as a measured exposure
    taxable_only = {k: v for k, v in book.items() if groups[k] != "muni"}
    ro2 = ER.readout(px, _positions(dates, taxable_only), groups, window=W, lags=L)
    mv2 = ER.muni_vs_taxable(ro2)
    assert not mv2["muni_held"].any() and mv2["taxable_held"].all()
    md = ER.summary_md(ro2, {"asof": "x", "fetched_at_utc": "y"})
    assert f"| {dates[0].date()} | none held | n/a | " in md
    # no equity: the fractions are NaN, never a sum of NaNs read as 0
    ro3 = ER.readout(px, _positions(dates, book).drop(columns=["equity"]), groups, window=W, lags=L)
    mv3 = ER.muni_vs_taxable(ro3)
    assert mv3["muni_frac"].isna().all() and mv3["taxable_frac"].isna().all()


# --------------------------------------------------------------------------- derive's lag rules

def test_lag_rule_helpers():
    single = {0: 43, 1: 14, 2: 10, 3: 7, 4: 2, 5: 12}
    assert ER._first_gap(single, 5) == 3
    assert ER._first_gap(single, 9) == 2
    assert ER._first_gap(single, 13) == 1
    assert ER._first_gap(single, 14) == 0
    assert ER._first_gap(single, 1) is None
    assert ER._smallest_within({0: 17, 1: 15, 2: 5, 3: 3}, 5) == 2
    assert ER._smallest_within({0: 17}, 5) is None
    assert ER._fmt_runs({b: ER._first_gap(single, b) for b in range(0, 16)}) == \
        "bound 0-1 -> L None; 2-6 -> L 3; 7-9 -> L 2; 10-13 -> L 1; 14+ -> L 0"


def test_lag_rule_counts_on_a_lagged_response():
    """A response at lags 0, 1 and (weakly) 2, none at 3. The lag-2 effect is set so its
    joint p-value sits well inside (0, 0.05), so the count follows the 5% level, not just a
    huge signal. Checks the counting, not any market."""
    pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(3)
    n = 2000
    F = pd.DataFrame(rng.normal(0, 0.01, (n, 4)), columns=list(ER.FACTOR_NAMES),
                     index=pd.RangeIndex(n))
    y = (2.0 * F["TERM"] + 1.5 * F["TERM"].shift(1) + 0.1 * F["TERM"].shift(2)
         + rng.normal(0, 0.011, n)).rename("y")
    m = ER._dimson_ols(y, F, 3)
    idx = list(m.params.index)
    Rm = np.zeros((4, len(idx)))
    for j, k in enumerate(ER.FACTOR_NAMES):
        Rm[j, idx.index(f"{k}_2")] = 1.0
    p2 = float(m.wald_test(Rm, scalar=True).pvalue)
    assert 1e-6 < p2 < 0.01                                   # moderate, by construction
    c = ER.lag_rule_counts({"X": m})
    assert c["joint"] == {0: 1, 1: 1, 2: 1, 3: 0}
    assert c["single"][0] >= 1 and c["single"][1] >= 1 and c["single"][2] >= 1
    assert c["tail"][0] == 1 and c["tail"][1] == 1             # lags 1..3 and 2..3 carry signal
    assert set(c["single"]) == {0, 1, 2, 3} and set(c["tail"]) == {0, 1, 2}


# --------------------------------------------------------------------------- THE RULE (lead placebo)

def test_placebo_lag_rule_includes_lags_while_they_strictly_exceed_the_largest_lead_count():
    leads = {1: 3, 2: 9, 3: 5}                                  # T = 9
    r = ER.placebo_lag_rule({0: 40, 1: 20, 2: 15, 3: 9, 4: 30}, leads)
    assert r == {"L": 2, "T": 9, "stop_lag": 3}                 # a tie stops; lag 4 is after the gap
    assert ER.placebo_lag_rule({0: 40, 1: 10, 2: 10, 3: 3, 4: 30}, leads)["L"] == 2
    assert ER.placebo_lag_rule({0: 40, 1: 9, 2: 30}, leads)["L"] == 0       # tie at lag 1
    assert ER.placebo_lag_rule({0: 40, 1: 10, 2: 9}, leads) == {"L": 1, "T": 9, "stop_lag": 2}
    # the bound is the MAXIMUM lead count, not a typical one
    assert ER.placebo_lag_rule({0: 40, 1: 8, 2: 30}, {1: 1, 2: 1, 3: 9})["L"] == 0


@pytest.mark.parametrize("lag, lead, msg", [
    ({0: 9, 1: 20, 2: 3}, {1: 9}, "lag 0 count"),                # lag 0 must clear the placebo
    ({0: 40, 1: 20, 2: 15}, {1: 9}, "censored"),                 # every lag clears: never K
    ({0: 40, 2: 15}, {1: 9}, "cover 0..K"),                      # a hole in the lags
    ({0: 40}, {1: 9}, "cover 0..K"),                             # no lag to decide
    ({0: 40, 1: 2}, {}, "no lead counts"),
])
def test_placebo_lag_rule_raises_rather_than_guess(lag, lead, msg):
    with pytest.raises(ER.LagRuleError, match=msg):
        ER.placebo_lag_rule(lag, lead)


def test_the_number_of_leads_makes_the_maximum_a_test_at_the_pair_level():
    """1/(J + 1) is the rank test's size; J = 19 is the fewest leads that reach 5%."""
    J, a = ER.DERIVE_RULE_LEADS, ER.DERIVE_RULE_ALPHA
    assert 1 / (J + 1) <= a < 1 / J
    assert ER.DERIVE_RULE_HAC == 5 and ER.DERIVE_MAX_LAG == 10


def _placebo_fixture(seed=21, n_names=8, weights=(1.0, 0.6, 0.4)):
    """Synthetic funds that respond to the factors at lags 0..len(weights) - 1 (by default
    0, 1 and 2) and share a common shock (so their t-statistics co-move, as 13 CEFs do),
    plus a strong lag-3 response that exists ONLY after the fit end. Tests the code; claims
    nothing about any fund."""
    sess = ER.nyse_sessions(dt.date(2004, 1, 2), dt.date(2011, 12, 30))
    E = _factor_returns(seed, sessions=sess)
    rng = np.random.default_rng(seed + 100)
    fit_end = sess[1300]
    post = np.asarray(sess > fit_end)
    common = rng.normal(0, 0.003, len(sess))
    R = E.copy()
    for i in range(n_names):
        x = E @ rng.uniform(0.3, 0.8, 4)                        # a mix of IEF, HYG, MUB, BKLN
        resp = sum(w * x.shift(l) for l, w in enumerate(weights))
        late = np.where(post, 0.8 * x.shift(3).to_numpy(), 0.0)
        R[f"N{i}"] = resp + late + common + rng.normal(0, 0.003, len(sess))
    return R, sess, fit_end, [f"N{i}" for i in range(n_names)]


def test_lead_placebo_rule_recovers_a_two_lag_response_on_the_fit_era_only():
    pytest.importorskip("statsmodels.api")
    R, sess, fit_end, names = _placebo_fixture()
    pc = ER.lead_placebo_counts(R, names, fit_end=fit_end)
    n = pc["n_pairs"]
    assert n == 4 * len(names)
    assert set(pc["lag"]) == set(range(ER.DERIVE_MAX_LAG + 1))
    assert set(pc["lead"]) == set(range(1, ER.DERIVE_RULE_LEADS + 1))
    assert pc["lag"][0] == pc["lag"][1] == pc["lag"][2] == n    # the response, every pair
    # H13: the last response row is exactly J sessions before the fit end
    i_end = int(sess.get_loc(fit_end))
    assert pc["last"] == sess[i_end - ER.DERIVE_RULE_LEADS]
    r = ER.placebo_lag_rule(pc["lag"], pc["lead"])
    assert r["L"] == 2 and r["stop_lag"] == 3
    assert pc["lag"][3] <= r["T"] < n
    # the leads are counted at the pair level (mean near alpha x pairs), and the shared shock
    # pushes their maximum past the Binomial 95% point: the dependence the placebo absorbs
    from scipy.stats import binom
    mean_lead = float(np.mean(list(pc["lead"].values())))
    assert 0.5 * ER.DERIVE_RULE_ALPHA * n < mean_lead < 2.0 * ER.DERIVE_RULE_ALPHA * n
    assert r["T"] > binom.ppf(0.95, n, ER.DERIVE_RULE_ALPHA)
    # the lag-3 response after the fit end is strong enough to matter if it were read
    full = ER.lead_placebo_counts(R, names, fit_end=sess[-1])
    assert ER.placebo_lag_rule(full["lag"], full["lead"])["L"] >= 3


def test_lead_placebo_rule_gives_zero_lags_to_a_same_day_response():
    """The rule's adopted output, L = 0, on a fixture built to have it: every fund responds
    on the day only. The fit-era lag-1 count must not clear the placebo."""
    pytest.importorskip("statsmodels.api")
    R, _, fit_end, names = _placebo_fixture(weights=(1.0,))
    pc = ER.lead_placebo_counts(R, names, fit_end=fit_end)
    assert pc["lag"][0] == pc["n_pairs"]
    r = ER.placebo_lag_rule(pc["lag"], pc["lead"])
    assert r["L"] == 0 and r["stop_lag"] == 1


# The fit-era counts `derive` recorded on 2026-11-02 (module docstring, THE RULE'S RESULT):
# public yfinance prices, 2011-03-18 .. 2022-12-02, 13 names, 52 pairs. No account data.
# They came from the cache whose prices.parquet hashes to ER.RULE_CACHE_SHA256 (asof
# ER.RULE_CACHE_ASOF); `derive` says whether the cache it reads is that one.
RECORDED_LAG_COUNTS = dict(enumerate([46, 18, 16, 8, 4, 12, 14, 13, 6, 7, 17]))
RECORDED_LEAD_COUNTS = dict(enumerate([12, 6, 12, 16, 8, 13, 13, 12, 14, 11, 7, 11, 19, 18, 3, 4, 1, 5, 5],
                                      start=1))


def test_dimson_lags_is_the_rules_output_on_the_recorded_fit_era_counts():
    assert len(RECORDED_LEAD_COUNTS) == ER.DERIVE_RULE_LEADS
    assert len(RECORDED_LAG_COUNTS) == ER.DERIVE_MAX_LAG + 1
    r = ER.placebo_lag_rule(RECORDED_LAG_COUNTS, RECORDED_LEAD_COUNTS)
    assert r == {"L": 0, "T": 19, "stop_lag": 1}
    assert ER.DIMSON_LAGS == r["L"]
    # the superseded Binomial first gap on the lags-only counts gave 3 (history)
    assert ER._first_gap({0: 43, 1: 14, 2: 10, 3: 7, 4: 2, 5: 12}, 5) == 3


def test_lead_placebo_counts_raise_on_a_missing_name():
    R, _, fit_end, names = _placebo_fixture(n_names=1)
    with pytest.raises(ER.LagRuleError, match="not in the returns panel"):
        ER.lead_placebo_counts(R, names + ["ZZZ"], fit_end=fit_end)


# --------------------------------------------------------------------------- diagnostics and the cache hash

def test_the_recorded_counts_name_the_cache_they_came_from(tmp_path):
    """Review 2026-11-02, finding 3: the recorded counts are literals, so a re-fetched cache
    could move L while every test passed. The cache's hash is recorded, and `derive` says
    whether its cache is that one."""
    assert len(ER.RULE_CACHE_SHA256) == 64 and set(ER.RULE_CACHE_SHA256) <= set("0123456789abcdef")
    assert ER.RULE_CACHE_ASOF == "2026-10-30"
    (tmp_path / "prices.parquet").write_bytes(b"not the recorded cache")
    import hashlib
    sha = ER.cache_sha256(tmp_path)
    assert sha == hashlib.sha256(b"not the recorded cache").hexdigest()
    assert "DIFFERS" in ER.cache_provenance_line(sha)
    assert "came from" in ER.cache_provenance_line(ER.RULE_CACHE_SHA256)
    assert "UNMEASURED" in ER.cache_provenance_line(None)
    with pytest.raises(ER.ReadoutError, match="missing"):
        ER.cache_sha256(tmp_path / "nowhere")


def test_episode_rows_drop_exactly_the_rows_whose_span_touches_the_window():
    idx = pd.DatetimeIndex(SESS[:60])
    got = ER.episode_rows(idx, idx[30], idx[32], max_lag=2, leads=3)
    # row p spans p-2 .. p+3; it touches 30..32 iff p + 3 >= 30 and p - 2 <= 32
    assert list(got) == list(idx[27:35])
    # a window between sessions (a weekend) holds no factor row: raise, never guess
    sat = idx[4] + pd.Timedelta(days=1)
    while sat in idx:
        sat += pd.Timedelta(days=1)
    with pytest.raises(ER.ReadoutError, match="no factor row"):
        ER.episode_rows(idx, sat, sat, max_lag=2, leads=3)


def test_trend_test_reads_an_ordered_and_a_degenerate_set_of_counts():
    pytest.importorskip("scipy")
    rho, p1, p2 = ER._trend_test({j: 20 - j for j in range(1, 20)}, n_perm=2000)
    assert rho == pytest.approx(-1.0) and p1 < 0.01 and p2 < 0.01
    rho, p1, _ = ER._trend_test({j: j for j in range(1, 20)}, n_perm=2000)
    assert rho == pytest.approx(1.0) and p1 > 0.99
    with pytest.raises(ER.ReadoutError, match="not all equal"):
        ER._trend_test({j: 5 for j in range(1, 20)}, n_perm=10)


def _episode_fixture(seed=21):
    """`_placebo_fixture`'s same-day funds, plus a fake lead-13 response confined to one
    60-session episode inside the fit era: the shape the review found in March-April 2020.
    Tests the code; claims nothing about any fund."""
    R, sess, fit_end, names = _placebo_fixture(seed=seed, weights=(1.0,))
    E = R[ETFS]
    rng = np.random.default_rng(seed + 7)
    i0 = 600
    ep = (sess[i0], sess[i0 + 59])
    in_ep = np.asarray((sess >= ep[0]) & (sess <= ep[1]))
    for n in names:
        x = E @ rng.uniform(0.3, 0.8, 4)
        R[n] = R[n] + np.where(in_ep, 8.0 * x.shift(-13).to_numpy(), 0.0)
    return R, sess, fit_end, names, ep


def test_placebo_diagnostics_reproduce_the_rule_and_remove_an_episode():
    """The diagnostics fit THE RULE's model (their full-sample counts equal
    `lead_placebo_counts`'), drop exactly the rows `episode_rows` names, and a lead response
    that lives only in the episode inflates T and goes when the episode is dropped, while
    the year control moves T only for the episode's year."""
    pytest.importorskip("statsmodels.api")
    R, sess, fit_end, names, ep = _episode_fixture()
    groups = {n: "g" for n in names}
    pc = ER.lead_placebo_counts(R, names, fit_end=fit_end)
    d = ER.placebo_diagnostics(R, names, groups, fit_end=fit_end, episode=ep, lead_cut=14)
    assert d["lag"] == pc["lag"] and d["lead"] == pc["lead"]
    assert d["at_T"] == [13] and d["lead"][13] >= 3 * ER.DERIVE_RULE_ALPHA * pc["n_pairs"]
    assert {t[0] for t in d["T_pairs"]} == {13} and len(d["T_pairs"]) == d["lead"][13]
    e = d["episode"]
    want = 60 + ER.DERIVE_MAX_LAG + ER.DERIVE_RULE_LEADS        # the window plus every span reaching it
    assert set(e["rows_dropped"].values()) == {want}
    assert e["lead"][13] < d["lead"][13] and e["T"] < max(d["lead"].values())
    assert d["per_name"]["lead_tests"].eq(4 * ER.DERIVE_RULE_LEADS).all()
    ep_year = pd.Timestamp(ep[0]).year
    assert set(d["years"]) == set(range(sess[0].year, pd.Timestamp(fit_end).year + 1))
    others = [T for y, (T, *_rest) in d["years"].items() if y != ep_year]
    assert d["years"][ep_year][0] < min(others)
    assert set(d["far"]) == {"11..14", "15..19", "11..19"}


def test_placebo_diagnostics_never_read_past_the_fit_end():
    """H13: data after the fit end cannot reach the diagnostics."""
    pytest.importorskip("statsmodels.api")
    R, sess, fit_end, names, ep = _episode_fixture()
    groups = {n: "g" for n in names}
    a = ER.placebo_diagnostics(R, names, groups, fit_end=fit_end, episode=ep, years=False)
    R2 = R.copy()
    R2.loc[R2.index > fit_end] = np.random.default_rng(3).normal(0, 0.05, R2.loc[R2.index > fit_end].shape)
    b = ER.placebo_diagnostics(R2, names, groups, fit_end=fit_end, episode=ep, years=False)
    assert a["lag"] == b["lag"] and a["lead"] == b["lead"] and a["episode"]["lead"] == b["episode"]["lead"]


# --------------------------------------------------------------------------- cross-check labels

def test_crosscheck_names_each_panels_vendor_and_splits_etf_daily_by_leg(tmp_path):
    """Review 2026-11-02, finding 6: agreeing with a yfinance panel checks the fetch, not the
    data. Every row says whose numbers it compared against."""
    R = _returns_with_names()[ETFS + ["AAA"]]
    px = _px_from_returns(R)
    R2, C2, _ = ER.returns_panel(px)
    d = tmp_path / "data"
    (d / "rv").mkdir(parents=True)
    (d / "cef").mkdir()
    etf = [e for e in ETFS if e != "MUB"]
    C2[etf].to_parquet(d / "rv" / "close_unadj_wide.parquet")
    R2[etf].to_parquet(d / "rv" / "returns_wide.parquet")
    long = px[px["ticker"].isin(ETFS)].merge(
        R2.stack().rename("ret_total").reset_index().rename(columns={"level_1": "ticker"}),
        on=["date", "ticker"])
    long[["date", "ticker", "close", "ret_total", "dividend"]].to_parquet(d / "rv" / "etf_ohlc_extended.parquet")
    ed = long[long["ticker"] == "IEF"][["date", "ticker", "ret_total"]].copy()
    ed["source"] = np.where(ed["date"] < SESS[100], "crsp", "yfinance")
    ed.to_parquet(d / "etf_daily.parquet")
    px[px["ticker"] == "AAA"][["date", "ticker", "close"]].to_parquet(d / "cef" / "cef_prices.parquet")
    pd.DataFrame({"ticker": ["AAA"], "ex_date": [SESS[10]], "amount": [0.0]}).to_parquet(
        d / "cef" / "cef_distributions.parquet")
    tab, notes = ER.crosscheck(px, data_dir=d)
    legs = tab[tab["panel"].str.startswith("etf_daily")].set_index("panel")
    assert set(legs.index) == {"etf_daily[crsp]", "etf_daily[yfinance]"}
    assert legs.at["etf_daily[crsp]", "independent_of_yfinance"] == "yes"
    assert legs.at["etf_daily[yfinance]", "independent_of_yfinance"] == "no"
    assert legs.at["etf_daily[crsp]", "last"] < SESS[100].date() <= legs.at["etf_daily[yfinance]", "first"]
    assert (tab.loc[tab["panel"].str.startswith("cef/"), "independent_of_yfinance"] == "no").all()
    assert tab["vendor"].notna().all()
    assert any("confirms the fetch, not the data" in n for n in notes)
    ed.loc[ed.index[0], "source"] = "bloomberg"
    ed.to_parquet(d / "etf_daily.parquet")
    with pytest.raises(ER.ReadoutError, match="bloomberg"):
        ER.crosscheck(px, data_dir=d)


# --------------------------------------------------------------------------- refusals

def test_fit_raises_naming_a_missing_return_in_a_held_names_window():
    R = _returns_with_names()
    t = SESS[150]
    R.loc[SESS[120], "BBB"] = np.nan
    with pytest.raises(ER.ReadoutError, match=r"BBB.*2020"):
        ER.fit_window(R, SESS, t, ["AAA", "BBB"], window=W, lags=L)
    # the same gap in a name that is not held does not block the fit
    ER.fit_window(R, SESS, t, ["AAA"], window=W, lags=L)


def test_fit_raises_on_a_missing_factor_return():
    R = _returns_with_names()
    R.loc[SESS[100], "MUB"] = np.nan
    with pytest.raises(ER.ReadoutError, match="MUB"):
        ER.fit_window(R, SESS, SESS[150], ["AAA"], window=W, lags=L)


def test_fit_raises_when_history_is_shorter_than_the_window():
    R = _returns_with_names()
    with pytest.raises(ER.ReadoutError, match="needs"):
        ER.fit_window(R, SESS, SESS[W + L - 1], ["AAA"], window=W, lags=L)


def test_readout_refuses_a_split_after_the_first_positions_date_on_a_held_name():
    R = _returns_with_names()
    px = _px_from_returns(R)
    px.loc[(px["ticker"] == "AAA") & (px["date"] == SESS[152]), "split"] = 2.0
    P = _positions(list(SESS[150:153]), {"AAA": 100.0})
    with pytest.raises(ER.ReadoutError, match="split"):
        ER.readout(px, P, {"AAA": "multi"}, window=W, lags=L)


def test_readout_refuses_a_missing_close_on_a_positions_date():
    R = _returns_with_names()
    px = _px_from_returns(R)
    px.loc[(px["ticker"] == "AAA") & (px["date"] == SESS[151]), "close"] = np.nan
    with pytest.raises(ER.ReadoutError, match=r"no close on 2020.*AAA"):
        ER.readout(px, _positions([SESS[151]], {"AAA": 1.0}), {"AAA": "multi"}, window=W, lags=L)


def test_readout_refuses_a_held_symbol_without_a_group_and_a_non_session_date():
    R = _returns_with_names()
    px = _px_from_returns(R)
    with pytest.raises(ER.ReadoutError, match="no group"):
        ER.readout(px, _positions(list(SESS[150:152]), {"AAA": 1.0}), {}, window=W, lags=L)
    sat = pd.Timestamp("2020-08-01")                         # a Saturday
    with pytest.raises(ER.ReadoutError, match="not cached sessions"):
        ER.readout(px, _positions([sat], {"AAA": 1.0}), {"AAA": "multi"}, window=W, lags=L)


def test_returns_panel_refuses_a_split_and_a_distribution_on_one_name_date():
    R = _returns_with_names()
    px = _px_from_returns(R)
    m = (px["ticker"] == "AAA") & (px["date"] == SESS[100])
    px.loc[m, "split"] = 1.01                                 # 'undecidable' size for the guard
    px.loc[m, "dividend"] = 0.05
    with pytest.raises(ER.ReadoutError, match="same name-date"):
        ER.returns_panel(px)


@pytest.mark.parametrize("mutate, msg", [
    (lambda P: pd.concat([P, P.iloc[[0]]]), "duplicate"),
    (lambda P: P.assign(equity=[100_000.0] + [np.nan] * (len(P) - 1)), "some rows"),
    (lambda P: P.assign(equity=[100_000.0 + i for i in range(len(P))]), "more than one equity"),
    (lambda P: P.assign(equity=-1.0), "finite positive"),
    (lambda P: P.assign(shares=[np.inf] + list(P["shares"].iloc[1:])), "non-finite"),
])
def test_positions_validation_raises(mutate, msg):
    P = _positions(list(SESS[150:152]), {"AAA": 1.0, "BBB": -2.0})
    with pytest.raises(ER.ReadoutError, match=msg):
        ER.validate_positions(mutate(P))


def test_positions_without_equity_are_accepted_and_carry_none():
    P = _positions(list(SESS[150:152]), {"AAA": 1.0}).drop(columns=["equity"])
    assert "equity" not in ER.validate_positions(P).columns


@pytest.mark.parametrize("value, msg", [("$100,000.00", "not plain numbers"),
                                        ("100,000", "not plain numbers"),
                                        ("", "empty on every row"),
                                        (np.nan, "empty on every row")])
def test_an_equity_that_does_not_parse_raises_naming_the_column(value, msg):
    """Review 2026-11-02, finding 4: the first build coerced an unparseable equity to NaN,
    dropped the column without a word, and the summary blamed a missing equity."""
    P = _positions(list(SESS[150:152]), {"AAA": 1.0, "BBB": -2.0}).assign(equity=value)
    with pytest.raises(ER.ReadoutError, match=f"equity.*{msg}|{msg}"):
        ER.validate_positions(P)


def test_an_equity_written_as_a_numeric_string_is_read():
    P = _positions(list(SESS[150:152]), {"AAA": 1.0}).assign(equity="100000.5")
    assert (ER.validate_positions(P)["equity"] == 100000.5).all()


def test_validate_prices_raises_on_a_missing_session_an_extra_row_and_a_bad_close():
    R = _returns_with_names()
    px = _px_from_returns(R)
    asof = SESS[-1].date()
    ER.validate_prices(px, asof)
    with pytest.raises(ER.ReadoutError, match="missing"):
        ER.validate_prices(px.drop(px.index[(px["ticker"] == "IEF") & (px["date"] == SESS[50])]), asof)
    extra = px.iloc[[0]].assign(date=pd.Timestamp("2020-01-04"))        # a Saturday
    with pytest.raises(ER.ReadoutError, match="extra"):
        ER.validate_prices(pd.concat([px, extra], ignore_index=True), asof)
    bad = px.copy()
    bad.loc[bad.index[5], "close"] = 0.0
    with pytest.raises(ER.ReadoutError, match="non-positive"):
        ER.validate_prices(bad, asof)


class _FakeTicker:
    """Stands in for yfinance.Ticker: no network. Rows on the given sessions."""
    def __init__(self, sessions):
        self.sessions = sessions

    def history(self, start, end, auto_adjust, actions):
        assert auto_adjust is False and actions is True
        d = self.sessions[(self.sessions >= pd.Timestamp(start)) & (self.sessions < pd.Timestamp(end))]
        idx = pd.DatetimeIndex(d).tz_localize("America/New_York")
        return pd.DataFrame({"Close": 50.0, "Adj Close": 50.0, "Dividends": 0.0, "Stock Splits": 0.0},
                            index=idx)


def test_fetch_refuses_a_last_row_that_is_not_the_asof(monkeypatch):
    import sys
    import types
    asof = SESS[-1].date()
    fake = types.SimpleNamespace(Ticker=lambda tk: _FakeTicker(SESS))
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    px, cg = ER.fetch_yf(["IEF"], SESS[0].date(), asof)
    assert px["date"].max().date() == asof and cg == {"IEF": "absent"}
    fake.Ticker = lambda tk: _FakeTicker(SESS[:-1])           # the vendor stops a session short
    with pytest.raises(ER.ReadoutError, match="not the asof session"):
        ER.fetch_yf(["IEF"], SESS[0].date(), asof)


def test_check_asof_refuses_today_and_a_non_session():
    now = dt.datetime(2026, 11, 2, 20, 0, tzinfo=ER.NY)
    with pytest.raises(ER.ReadoutError, match="not before today"):
        ER.check_asof(dt.date(2026, 11, 2), now=now)
    with pytest.raises(ER.ReadoutError, match="not an NYSE session"):
        ER.check_asof(dt.date(2026, 11, 1), now=now)             # a Sunday
    ER.check_asof(dt.date(2026, 10, 30), now=now)


def test_refuses_to_write_under_data(tmp_path):
    d = tmp_path / "data"
    (d / "cef").mkdir(parents=True)
    with pytest.raises(ER.ReadoutError, match="under data/"):
        ER._refuse_data_dir(d / "cef" / "out", data_dir=d)
    with pytest.raises(ER.ReadoutError, match="under data/"):
        ER._refuse_data_dir(d, data_dir=d)
    ER._refuse_data_dir(tmp_path / "elsewhere", data_dir=d)


def _git(*args, cwd):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                   cwd=str(cwd), check=True, capture_output=True)


def test_refuses_to_write_a_file_git_can_see(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)       # no user excludes file
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    out = repo / "results" / "out"
    with pytest.raises(ER.ReadoutError, match="can see"):
        ER._refuse_git_visible(out, ["exposure.csv"])
    (repo / ".gitignore").write_text("results/out/\n")
    ER._refuse_git_visible(out, ["exposure.csv"])
    outside = tmp_path / "outside"
    if ER._enclosing_repo(outside) is None:                 # tmp dirs sit outside any repository
        ER._refuse_git_visible(outside, ["exposure.csv"])


def test_git_guard_checks_the_repository_enclosing_the_target_not_its_own(tmp_path, monkeypatch):
    """Review 2026-11-02, finding 3: a linked worktree inside the main checkout. Written from
    the worktree, a target in the MAIN checkout is visible to the main checkout's git, and
    the first build let it through because it checked only its own checkout."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    main = tmp_path / "main"
    main.mkdir()
    _git("init", "-q", cwd=main)
    (main / ".gitignore").write_text(".claude/worktrees/\n")
    _git("add", ".gitignore", cwd=main)
    _git("commit", "-q", "-m", "init", cwd=main)
    wt = main / ".claude" / "worktrees" / "wt"
    _git("worktree", "add", "-q", "-b", "wt", str(wt), cwd=main)
    assert (wt / ".git").is_file()                           # a linked worktree's .git is a file
    assert ER._enclosing_repo(wt / "results" / "x") == wt.resolve()
    assert ER._enclosing_repo(main / "results" / "x") == main.resolve()
    with pytest.raises(ER.ReadoutError, match="can see"):
        ER._refuse_git_visible(main / "results" / "cef" / "x", ["summary.md"])
    with pytest.raises(ER.ReadoutError, match="can see"):
        ER._refuse_git_visible(wt / "results" / "cef" / "x", ["summary.md"])
    (wt / ".gitignore").write_text("results/cef/x/\n")
    ER._refuse_git_visible(wt / "results" / "cef" / "x", ["summary.md"])
    with pytest.raises(ER.ReadoutError, match="can see"):   # ignoring it in the worktree
        ER._refuse_git_visible(main / "results" / "cef" / "x", ["summary.md"])  # does not cover main


def test_git_guard_refuses_when_git_cannot_answer(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    (repo / ".gitignore").write_text("out/\n")
    real = subprocess.run

    def failing(step):
        def run(args, *a, **k):
            if step in args:
                return subprocess.CompletedProcess(args, 128, "", "fatal: simulated")
            return real(args, *a, **k)
        return run
    ER._refuse_git_visible(repo / "out", ["x.csv"])           # ignored: allowed
    for step, msg in (("check-ignore", "exited 128"), ("rev-parse", "top level")):
        monkeypatch.setattr(ER.subprocess, "run", failing(step))
        with pytest.raises(ER.ReadoutError, match=msg):
            ER._refuse_git_visible(repo / "out", ["x.csv"])
        monkeypatch.setattr(ER.subprocess, "run", real)


def test_the_repository_defaults_are_gitignored():
    ER._refuse_git_visible(ER.DEFAULT_CACHE, ER.CACHE_FILES)
    ER._refuse_git_visible(ER.DEFAULT_OUT / "2026-10-30", ER.OUT_FILES)


# --------------------------------------------------------------------------- what it is not

def test_module_holds_no_order_code_no_keys_and_no_live_path_import():
    src = Path(ER.__file__).read_text()
    for needle in ("submit_order", "cancel_order", "replace_order", "cancel_all", "close_position",
                   "AlpacaClient", "QUANTT_ENV_FILE", "dotenv", "config/.env", "mcp__alpaca",
                   "paper-api.alpaca", "SECRET_KEY", "KEY_ID"):
        assert needle not in src, needle
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    assert not {m for m in mods if m.split(".")[0] in ("quantt", "src") or m.startswith("ops.books")}, mods
    assert {m for m in mods if m.startswith("scripts.")} <= {"scripts.cef.data_guards", "scripts.cef.spec"}


def test_review_constants_trace_to_d4_and_the_spec():
    assert ER.REVIEW_FRACTION == ER.D4_BETA_BAR == 0.10
    from scripts.cef.spec import VOL_TARGET, Z_WINDOW
    assert ER.VOL_TARGET == VOL_TARGET and ER.WINDOW == Z_WINDOW


# --------------------------------------------------------------------------- two books (team lead, 2026-11-09)

C4_NAMES = {"AAA": "equity_domestic", "BBB": "equity_covered_call", "CCC": "preferred"}


def _c4_fs():
    """C4's factor set with a lag supplied by hand: the set as the spec reads it, for tests
    of what the readout DOES with the set. Its lag is None until the rule has run."""
    return replace(ER.factor_set("c4"), dimson_lags=0)


def _c4_returns(seed=3):
    rng = np.random.default_rng(seed)
    n = len(SESS)
    z = rng.normal(0, 0.005, size=(n, 4))
    spy = z[:, 0]
    ief = z[:, 1] - 0.2 * spy
    hyg = z[:, 2] + 0.3 * spy + 0.2 * ief
    pff = z[:, 3] + 0.5 * hyg + 0.1 * spy
    R = pd.DataFrame({"SPY": spy, "IEF": ief, "HYG": hyg, "PFF": pff}, index=SESS)
    R["AAA"] = 0.9 * spy + rng.normal(0, 1e-4, n)
    R["BBB"] = 0.6 * spy + rng.normal(0, 1e-4, n)
    R["CCC"] = 0.7 * pff + rng.normal(0, 1e-4, n)
    return R


def test_the_core_factor_set_is_the_module_constants():
    """Pin (passes before and after this change): the default set is the core's."""
    assert ER.factor_set("cef") is ER.CORE
    assert ER.CORE.factors == ER.FACTORS and ER.CORE.headline == "MUNI" and ER.CORE.indicative == ER.INDICATIVE_FACTORS
    assert ER.CORE.vol_target == ER.VOL_TARGET and ER.CORE.window == ER.WINDOW and ER.CORE.dimson_lags == ER.DIMSON_LAGS


def test_the_c4_factor_set_reads_c4s_own_spec_never_the_cores():
    frozen = json.loads((ER.REPO / "ops/specs/c4_families.frozen.json").read_text())["frozen"]
    fs = ER.factor_set("c4")
    assert fs.factors == (("EQUITY", "SPY"), ("TERM", "IEF"), ("CREDIT", "HYG"), ("PREFERRED", "PFF"))
    assert fs.headline == "EQUITY" and fs.indicative == ("TERM", "CREDIT", "PREFERRED")
    assert fs.vol_target == frozen["vol_target_annual"] and fs.window == frozen["z_window"]
    assert list(fs.universe) == frozen["universe"] and fs.group_split == "family"
    assert fs.spec_id != ER.SPEC_ID
    # the family map is the spec's frozen family_of, and every universe name has one
    fam = ER.c4_families()
    assert fam == frozen["level_signal"]["family_of"] and set(fam) == set(frozen["universe"])
    assert set(fam.values()) == {"equity_domestic", "equity_sector", "equity_covered_call", "preferred", "multi_asset"}
    # the frozen universe file agrees, name by name
    u = pd.read_csv(ER.REPO / "results/cef/c4/c4_universe_frozen_2026-10-14.csv", dtype=str)
    assert fam == dict(zip(u["ticker"], u["family"]))


def test_the_c4_review_line_moves_with_c4s_own_spec_not_the_cores(tmp_path, monkeypatch):
    """Pin (no code changes with it): the review line is REVIEW_FRACTION x C4's OWN vol target,
    read from C4's spec (team lead, 2026-11-09). Both specs hold the same target today, so a
    build that read the core's constant passed every other test (review, 2026-11-09); here C4's
    spec is moved alone, and the line, c/target and a REVIEW flag must move with it. Replace
    `float(f["vol_target_annual"])` in `factor_set` with `VOL_TARGET` and this test fails.
    Since 2026-11-10 the line also carries C4's own sizing multiplier (the next test); the
    equity here is placed against the whole line, so this one still moves the target alone."""
    R = _c4_returns()
    px = _px_from_returns(R)
    dates = list(SESS[150:152])
    held = {"AAA": 2000.0, "BBB": -1000.0, "CCC": 500.0}
    base = _c4_fs()
    probe = ER.readout(px, _positions(dates, held, equity=250_000.0), C4_NAMES, window=W, fs=base)
    c0 = probe.exposure.query("factor == 'EQUITY'").iloc[0]["contrib_frac"]
    # Equity set so that EQUITY sits between the two lines: above the spec's line, below the
    # line with the spec's target x 4/3. contrib_frac is linear in 1/equity.
    aim = base.review_line * 7 / 6
    P = _positions(dates, held, equity=250_000.0 * c0 / aim)
    alt = tmp_path / "c4.json"
    spec = json.loads(ER.C4_SPEC.read_text())
    spec["frozen"]["vol_target_annual"] = base.vol_target * 4 / 3
    alt.write_text(json.dumps(spec))

    before = ER.readout(px, P, C4_NAMES, window=W, fs=base).exposure.query("factor == 'EQUITY'").iloc[0]
    assert before["contrib_frac"] == pytest.approx(aim) and before["review"] == "REVIEW"
    monkeypatch.setattr(ER, "C4_SPEC", alt)
    moved = _c4_fs()
    assert moved.vol_target == pytest.approx(base.vol_target * 4 / 3) and moved.vol_target != ER.VOL_TARGET
    after = ER.readout(px, P, C4_NAMES, window=W, fs=moved).exposure.query("factor == 'EQUITY'").iloc[0]
    assert after["contrib_frac"] == pytest.approx(before["contrib_frac"])     # a fact of the book
    assert after["contrib_of_target"] == pytest.approx(before["contrib_of_target"] * 3 / 4)
    assert after["review"] == "within"
    # and the core's own set never read the C4 spec it was handed nothing about
    assert ER.factor_set("cef").vol_target == ER.VOL_TARGET


# --------------------------------------------------------------------------- ruling A (team lead,
# 2026-11-10): the line is REVIEW_FRACTION x vol_target_annual x sizing_multiplier, both books

def _outcome(fn, frozen):
    """("value", v) or ("raises", message): the registry raises ValueError, the copy
    ReadoutError, and both must say the same thing."""
    try:
        return ("value", fn(frozen))
    except (ValueError, ER.ReadoutError) as e:
        return ("raises", str(e))


SIZING_CASES = {
    "absent": {}, "null": {"sizing_multiplier": None}, "float": {"sizing_multiplier": 1.3},
    "int": {"sizing_multiplier": 2}, "with-its-note": {"sizing_multiplier": 1.26, "_sizing_multiplier_note": "x"},
    "zero": {"sizing_multiplier": 0}, "negative": {"sizing_multiplier": -1.0},
    "string": {"sizing_multiplier": "1.3"}, "bool": {"sizing_multiplier": True},
    "nan": {"sizing_multiplier": float("nan")}, "inf": {"sizing_multiplier": float("inf")},
    "list": {"sizing_multiplier": [1.3]}, "misspelt": {"sizing_multiplyer": 1.3},
    "plural": {"sizing_multipliers": 1.3}, "no-underscores": {"sizingmultiplier": 1.3},
    "as-a-comment": {"_sizing_multiplier": 1.3}, "a-misspelt-note": {"_sizing_multiplyer_note": "x"},
    "dashed": {"sizing-multiplier": 1.3}, "unrelated-keys": {"vol_target_annual": 0.06, "band_width": 0.048},
}


@pytest.mark.parametrize("frozen", list(SIZING_CASES.values()), ids=list(SIZING_CASES))
def test_the_sizing_multiplier_copy_equals_the_registrys(frozen):
    """The licence for the copy (`sizing_multiplier` docstring): the runner's parse,
    src/deploy/registry.cef_sizing_multiplier, cannot be imported here, so the two must agree
    on every kind of input, value or message. Fails on the parent commit (no copy)."""
    from src.deploy.registry import cef_sizing_multiplier
    assert _outcome(ER.sizing_multiplier, frozen) == _outcome(cef_sizing_multiplier, frozen)


def test_the_sizing_multiplier_copy_equals_the_registrys_on_both_live_specs():
    from src.deploy.registry import cef_sizing_multiplier
    for path in ("ops/specs/cef_discount.frozen.json", "ops/specs/c4_families.frozen.json"):
        frozen = json.loads((ER.REPO / path).read_text())["frozen"]
        assert _outcome(ER.sizing_multiplier, frozen) == _outcome(cef_sizing_multiplier, frozen), path


def test_each_books_line_is_the_fraction_x_its_own_target_x_its_own_multiplier():
    """Each book's line from its own spec file, read here from disk and parsed by the runner's
    function: never a number written in this test. Fails on the parent commit."""
    from src.deploy.registry import cef_sizing_multiplier
    for book, path in (("cef", "ops/specs/cef_discount.frozen.json"), ("c4", "ops/specs/c4_families.frozen.json")):
        frozen = json.loads((ER.REPO / path).read_text())["frozen"]
        fs = ER.factor_set(book)
        m = cef_sizing_multiplier(frozen)
        assert fs.sizing_multiplier == m and fs.multiplier == (1.0 if m is None else m), book
        assert fs.vol_target == frozen["vol_target_annual"], book
        assert fs.review_line == pytest.approx(ER.REVIEW_FRACTION * frozen["vol_target_annual"] * fs.multiplier,
                                               rel=1e-15), book


def test_the_c4_line_moves_with_c4s_own_multiplier_alone(tmp_path, monkeypatch):
    """Extends the pin above (R5, 76ab3c7) to ruling A: C4's spec's sizing_multiplier is moved
    alone (target untouched), and C4's line, and a REVIEW flag, move with it while c/target
    does not; with the key deleted the line is the unit line, REVIEW_FRACTION x target; a
    malformed value refuses. The core's set never moves. Fails on the parent commit, whose
    line had no multiplier."""
    R = _c4_returns()
    px = _px_from_returns(R)
    dates = list(SESS[150:152])
    held = {"AAA": 2000.0, "BBB": -1000.0, "CCC": 500.0}
    base = _c4_fs()
    core_line = ER.factor_set("cef").review_line
    probe = ER.readout(px, _positions(dates, held, equity=250_000.0), C4_NAMES, window=W, fs=base)
    c0 = probe.exposure.query("factor == 'EQUITY'").iloc[0]["contrib_frac"]
    aim = base.review_line * 7 / 6                    # above C4's line, below it with m x 4/3
    P = _positions(dates, held, equity=250_000.0 * c0 / aim)
    spec = json.loads(ER.C4_SPEC.read_text())

    def with_frozen(edit):
        doc = json.loads(json.dumps(spec))
        edit(doc["frozen"])
        alt = tmp_path / f"c4_{len(list(tmp_path.iterdir()))}.json"
        alt.write_text(json.dumps(doc))
        monkeypatch.setattr(ER, "C4_SPEC", alt)
        return _c4_fs()

    before = ER.readout(px, P, C4_NAMES, window=W, fs=base).exposure.query("factor == 'EQUITY'").iloc[0]
    assert before["contrib_frac"] == pytest.approx(aim) and before["review"] == "REVIEW"

    moved = with_frozen(lambda f: f.__setitem__("sizing_multiplier", base.multiplier * 4 / 3))
    assert moved.vol_target == base.vol_target and moved.multiplier == pytest.approx(base.multiplier * 4 / 3)
    assert moved.review_line == pytest.approx(base.review_line * 4 / 3)
    after = ER.readout(px, P, C4_NAMES, window=W, fs=moved).exposure.query("factor == 'EQUITY'").iloc[0]
    assert after["contrib_frac"] == pytest.approx(before["contrib_frac"])
    assert after["contrib_of_target"] == pytest.approx(before["contrib_of_target"])   # still over the target
    assert after["review"] == "within"

    unit = with_frozen(lambda f: f.pop("sizing_multiplier"))
    assert unit.sizing_multiplier is None and unit.multiplier == 1.0
    assert unit.review_line == ER.REVIEW_FRACTION * base.vol_target
    row = ER.readout(px, P, C4_NAMES, window=W, fs=unit).exposure.query("factor == 'EQUITY'").iloc[0]
    assert row["review"] == ("REVIEW" if row["contrib_frac"] > unit.review_line else "within")
    assert "absent (the unit book, 1)" in unit.line_inputs()

    with pytest.raises(ER.ReadoutError, match="must be a number"):
        with_frozen(lambda f: f.__setitem__("sizing_multiplier", "1.26"))
    assert ER.factor_set("cef") is ER.CORE and ER.CORE.review_line == core_line


def _fresh_readout_module(monkeypatch, edit):
    """A second copy of this module, loaded while scripts/cef/spec.py's spec document has its
    frozen block edited: how the core's set reads the core's spec at load (ER is untouched)."""
    import importlib.util
    import sys
    from scripts.cef import spec as SP
    doc = json.loads(json.dumps(SP.spec()))
    edit(doc["frozen"])
    monkeypatch.setattr(SP, "_SPEC", doc)
    name = "exposure_readout_reloaded_for_a_test"
    spec = importlib.util.spec_from_file_location(name, ER.__file__)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, mod)
    spec.loader.exec_module(mod)
    return mod


def test_the_cores_line_moves_with_the_cores_own_multiplier_alone(monkeypatch):
    """Ruling A for the core: its spec's sizing_multiplier moved alone moves its line (and a
    MUNI flag) and nothing else; deleted, the line is the unit line; malformed, the module
    refuses to load. A literal in place of the spec's value fails here. Fails on the parent
    commit, where the core's set had no multiplier."""
    m0 = ER.CORE.multiplier
    moved = _fresh_readout_module(monkeypatch, lambda f: f.__setitem__("sizing_multiplier", m0 * 4 / 3))
    assert moved.CORE.multiplier == pytest.approx(m0 * 4 / 3)
    assert moved.CORE.review_line == pytest.approx(ER.CORE.review_line * 4 / 3)
    assert moved.CORE.vol_target == ER.CORE.vol_target and moved.CORE.window == ER.CORE.window

    px, dates, book, groups = _two_group_book()
    probe = ER.readout(px, _positions(dates, book), groups, window=W, lags=L)
    c0 = probe.exposure.query("factor == 'MUNI'").iloc[0]["contrib_frac"]
    aim = ER.CORE.review_line * 7 / 6
    P = _positions(dates, book, equity=100_000.0 * c0 / aim)
    a = ER.readout(px, P, groups, window=W, lags=L).exposure.query("factor == 'MUNI'").iloc[0]
    b = moved.readout(px, P, groups, window=W, lags=L).exposure.query("factor == 'MUNI'").iloc[0]
    assert a["contrib_frac"] == pytest.approx(aim) and b["contrib_frac"] == pytest.approx(aim)
    assert a["review"] == "REVIEW" and b["review"] == "within"

    unit = _fresh_readout_module(monkeypatch, lambda f: f.pop("sizing_multiplier"))
    assert unit.CORE.sizing_multiplier is None and unit.CORE.review_line == ER.REVIEW_FRACTION * ER.VOL_TARGET
    with pytest.raises(RuntimeError, match="must be a number"):
        _fresh_readout_module(monkeypatch, lambda f: f.__setitem__("sizing_multiplier", "1.3"))


def test_the_summary_prints_the_line_and_its_three_inputs():
    """Ruling A: a reader of summary.md sees the line and what it is made of. Fails on the
    parent commit, which printed the target and the fraction only."""
    px, dates, book, groups = _two_group_book()
    ro = ER.readout(px, _positions(dates, book), groups, window=W, lags=L)
    md = ER.summary_md(ro, {"asof": "x", "fetched_at_utc": "y"})
    fs = ER.CORE
    assert f"The line for book cef: {fs.line_inputs()} a year" in md
    assert (f"REVIEW_FRACTION {ER.REVIEW_FRACTION} x vol_target_annual {fs.vol_target:.4g} x sizing_multiplier "
            in fs.line_inputs()) and fs.line_inputs().endswith(f"= {fs.review_line:.6g}")
    assert "x sizing_multiplier" in ER.REVIEW_RULE and ER.REVIEW_RULE in md


# --------------------------------------------------------------------------- ruling C (team lead,
# 2026-11-10): the report job's partial mode; the strict default unchanged

def _late_book():
    """The two-group book with DDD's rows stopping one session before the last positions date,
    as a late same-day price leaves them."""
    px, dates, book, groups = _two_group_book()
    late = px[~((px["ticker"] == "DDD") & (px["date"] >= dates[-1]))].reset_index(drop=True)
    return px, late, dates, book, groups


def test_partial_mode_leaves_a_late_name_out_only_on_the_date_it_lacks():
    """Ruling C: DDD is left out on the last date only, named with its reason and shares; that
    date's readout equals a strict readout of the same prices with DDD not held that day, and
    the earlier dates equal the full strict readout. Fails on the parent commit (no partial)."""
    px, late, dates, book, groups = _late_book()
    P = _positions(dates, book)
    ro = ER.readout(late, P, groups, window=W, lags=L, partial=True)
    ex = ro.excluded
    assert list(ex["symbol"]) == ["DDD"] and list(ex["date"]) == [dates[-1]] and ex["shares"].iloc[0] == book["DDD"]
    assert ex["reason"].iloc[0] == f"no close on {dates[-1].date()} (its price history ends {dates[-2].date()})"
    rest = {k: v for k, v in book.items() if k != "DDD"}
    direct = ER.readout(late, pd.concat([_positions(dates[:-1], book), _positions(dates[-1:], rest)]),
                        groups, window=W, lags=L)
    for name in ("exposure", "by_group", "betas", "factor_defs", "factor_pnl", "total_vol"):
        pd.testing.assert_frame_equal(getattr(ro, name), getattr(direct, name), check_exact=True)
    full = ER.readout(px, P, groups, window=W, lags=L)
    for name in ("exposure", "total_vol"):
        a, b = getattr(ro, name), getattr(full, name)
        pd.testing.assert_frame_equal(a[a["date"] < dates[-1]].reset_index(drop=True),
                                      b[b["date"] < dates[-1]].reset_index(drop=True), check_exact=True)
    # the last date's factor P&L is E(t-1) x f(t), and t-1's book had DDD: it equals the full one
    fa, fb = ro.factor_pnl, full.factor_pnl
    pd.testing.assert_frame_equal(fa.reset_index(drop=True), fb.reset_index(drop=True), check_exact=True)


def test_partial_mode_with_no_held_name_having_its_inputs_raises():
    px, dates, book, groups = _two_group_book()
    late = px[~(px["ticker"].isin(list(book)) & (px["date"] == dates[-1]))]
    with pytest.raises(ER.NoInputsError, match=f"no held name has every input the readout needs on {dates[-1].date()}"):
        ER.readout(late, _positions(dates, book), groups, window=W, lags=L, partial=True)


def test_partial_mode_still_raises_on_a_missing_factor_etf():
    """A factor ETF is not a held name: every exposure needs it, so its gap is never partial."""
    px, dates, book, groups = _two_group_book()
    late = px[~((px["ticker"] == "MUB") & (px["date"] == dates[-1]))]
    with pytest.raises(ER.ReadoutError, match="factor ETF returns"):
        ER.readout(late, _positions(dates, book), groups, window=W, lags=L, partial=True)
    gap = px[~((px["ticker"] == "MUB") & (px["date"] == SESS[145]))]       # inside every date's window
    assert len(gap) == len(px) - 1
    with pytest.raises(ER.ReadoutError, match="factor ETF returns on the window"):
        ER.readout(gap, _positions(dates, book), groups, window=W, lags=L, partial=True)


def test_partial_mode_names_a_name_with_no_history_and_one_too_short_for_its_window():
    px, dates, book, groups = _two_group_book()
    short_from = SESS[150 - W // 2]
    cut = px[(px["ticker"] != "CCC") & ~((px["ticker"] == "AAA") & (px["date"] < short_from))]
    ro = ER.readout(cut, _positions(dates, book), groups, window=W, lags=L, partial=True)
    why = ro.excluded.groupby("symbol")["reason"].first()
    assert set(ro.excluded["symbol"]) == {"AAA", "CCC"} and len(ro.excluded) == 2 * len(dates)
    assert why["CCC"] == "no price history in the fetch"
    assert "missing return(s) in its" in why["AAA"] and str(short_from.date()) in why["AAA"]


def test_the_strict_default_is_unchanged_by_a_late_name():
    """The default refuses exactly as before the ruling, and a strict readout has no `excluded`
    frame (the CLI and research paths never see one). Fails on the parent commit only at the
    `excluded` line; the refusal is a pin."""
    px, late, dates, book, groups = _late_book()
    with pytest.raises(ER.ReadoutError, match=f"no close on {dates[-1].date()} for \\['DDD'\\]"):
        ER.readout(late, _positions(dates, book), groups, window=W, lags=L)
    assert ER.readout(px, _positions(dates, book), groups, window=W, lags=L).excluded is None


def test_fetch_each_keeps_a_late_held_name_only_in_partial_mode(monkeypatch):
    import sys
    import types
    asof = SESS[-1].date()
    fake = types.SimpleNamespace(Ticker=lambda tk: _FakeTicker(SESS[:-1] if tk == "LATE" else SESS))
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    px, cg, failed = ER.fetch_each(["IEF", "LATE"], SESS[0].date(), asof, required=("IEF",))
    assert set(failed) == {"LATE"} and "not the asof session" in failed["LATE"]     # the default: as before
    assert set(px["ticker"]) == {"IEF"}
    px, cg, failed = ER.fetch_each(["IEF", "LATE"], SESS[0].date(), asof, required=("IEF",), partial=True)
    assert failed == {} and set(px["ticker"]) == {"IEF", "LATE"}
    assert px.loc[px["ticker"] == "LATE", "date"].max() == SESS[-2] and px.loc[px["ticker"] == "IEF", "date"].max() == SESS[-1]
    fake.Ticker = lambda tk: _FakeTicker(SESS[:-1])          # a late factor ETF stays strict
    with pytest.raises(ER.ReadoutError, match="IEF: the last yfinance row"):
        ER.fetch_each(["IEF", "LATE"], SESS[0].date(), asof, required=("IEF",), partial=True)
    with pytest.raises(ER.ReadoutError, match="not the asof session"):
        ER.fetch_yf(["LATE"], SESS[0].date(), asof)          # fetch_yf's own default unchanged


def test_c4_without_a_lag_raises_naming_the_rule(monkeypatch):
    R = _c4_returns()
    px = _px_from_returns(R)
    P = _positions(list(SESS[150:152]), {"AAA": 1000.0})
    monkeypatch.setattr(ER, "C4_DIMSON_LAGS", None)     # (the state before the rule's result)
    with pytest.raises(ER.ReadoutError, match="lag rule has not been run"):
        ER.readout(px, P, {"AAA": "equity_domestic"}, fs=ER.factor_set("c4"))


def test_c4_orthogonalises_its_own_factors_in_its_own_order():
    R = _c4_returns()
    E = R[["SPY", "IEF", "HYG", "PFF"]].iloc[10:200]
    fs = _c4_fs()
    M = ER.orthogonaliser(E, fs)
    F = E @ M
    F.columns = list(fs.names)
    C = F.corr().to_numpy()
    assert abs(C - np.eye(4)).max() < 1e-9                                   # exactly uncorrelated in sample
    # EQUITY is SPY itself: the most general factor is not netted of anything (GS order)
    assert M.loc["SPY", "EQUITY"] == 1.0 and M.loc["IEF", "EQUITY"] == 0.0 and M.loc["PFF", "EQUITY"] == 0.0
    # PFF is netted of everything before it
    assert M.loc["PFF", "PREFERRED"] == 1.0 and M.loc["SPY", "PREFERRED"] != 0.0


def test_c4_exposure_and_review_line_use_the_set_they_are_given():
    R = _c4_returns()
    px = _px_from_returns(R)
    fs = _c4_fs()
    dates = list(SESS[150:152])
    P = _positions(dates, {"AAA": 2000.0, "BBB": -1000.0, "CCC": 500.0}, equity=250_000.0)
    ro = ER.readout(px, P, C4_NAMES, window=W, fs=fs)
    assert list(ro.exposure["factor"].unique()) == ["EQUITY", "TERM", "CREDIT", "PREFERRED"]
    assert ro.fs is fs and ro.lags == 0
    # the line is REVIEW_FRACTION x C4's vol target (the spec's), and c/target is what the set says
    ex = ro.exposure[ro.exposure["date"] == dates[0]].set_index("factor")
    eq_contrib = ex.at["EQUITY", "contrib_frac"] / fs.vol_target
    assert ex.at["EQUITY", "contrib_of_target"] == pytest.approx(eq_contrib)
    flag = "REVIEW" if ex.at["EQUITY", "contrib_frac"] > ER.REVIEW_FRACTION * fs.vol_target else "within"
    assert ex.at["EQUITY", "review"] == flag
    # the family split adds up to the book, date by date
    hg = ER.headline_by_group(ro)
    for d in dates:
        assert hg.loc[hg["date"] == d, "exposure_usd"].sum() == pytest.approx(ex.at["EQUITY", "exposure_usd"] if d == dates[0]
                                                                                else ro.exposure[(ro.exposure["date"] == d) & (ro.exposure["factor"] == "EQUITY")]["exposure_usd"].item())
    assert set(hg["grp"]) == {"equity_domestic", "equity_covered_call", "preferred"}


def test_c4_summary_leads_with_equity_and_splits_by_family():
    R = _c4_returns()
    px = _px_from_returns(R)
    fs = _c4_fs()
    P = _positions(list(SESS[150:152]), {"AAA": 2000.0, "BBB": -1000.0, "CCC": 500.0}, equity=250_000.0)
    ro = ER.readout(px, P, C4_NAMES, window=W, fs=fs)
    md = ER.summary_md(ro, {"asof": "2020-12-31", "fetched_at_utc": "x"})
    assert md.index("## Headline: EQUITY") < md.index("## Indicative")
    assert "TERM, CREDIT and PREFERRED" in md and "by family" in md and "equity_covered_call" in md
    assert "muni group" not in md and "MUNI" not in md
    assert fs.spec_id in md and f"{fs.vol_target:.4g}" in md
    assert "ALL four factors" in md


# --------------------------------------------------------------------------- THE C4 LAG RULE (synthetic only)

def _c4_placebo_fixture(seed=21, n_names=8, weights=(1.0, 0.6, 0.4), n_short=2):
    """Synthetic funds responding to C4's factors at lags 0..len(weights) - 1, sharing a
    common shock, plus a strong lag-3 response that exists ONLY after the fit end, and
    `n_short` names listed so late they have too few fit-era rows. Tests the code;
    claims nothing about any fund."""
    sess = ER.nyse_sessions(dt.date(2004, 1, 2), dt.date(2011, 12, 30))
    rng = np.random.default_rng(seed)
    n = len(sess)
    z = rng.normal(0, 0.005, size=(n, 4))
    spy = z[:, 0]
    ief = z[:, 1] - 0.2 * spy
    hyg = z[:, 2] + 0.3 * spy + 0.2 * ief
    pff = z[:, 3] + 0.5 * hyg + 0.1 * spy
    E = pd.DataFrame({"SPY": spy, "IEF": ief, "HYG": hyg, "PFF": pff}, index=sess)
    fit_end = sess[1300]
    post = np.asarray(sess > fit_end)
    common = rng.normal(0, 0.003, n)
    R = E.copy()
    names = [f"N{i}" for i in range(n_names)]
    for name in names:
        x = E @ rng.uniform(0.3, 0.8, 4)
        resp = sum(w * x.shift(l) for l, w in enumerate(weights))
        late = np.where(post, 0.8 * x.shift(3).to_numpy(), 0.0)
        R[name] = resp + late + common + rng.normal(0, 0.003, n)
    shorts = [f"SHORT{i}" for i in range(n_short)]
    for name in shorts:
        R[name] = (E @ rng.uniform(0.3, 0.8, 4)) + rng.normal(0, 0.003, n)
    return R, sess, fit_end, names, shorts


def test_c4_rule_runs_on_fit_rows_only_and_excludes_short_histories(capsys):
    pytest.importorskip("statsmodels.api")
    R, sess, fit_end, names, shorts = _c4_placebo_fixture()
    px = _px_from_returns(R)
    # the short names exist only over their last 100 fit-era sessions
    i_end = int(sess.get_loc(fit_end))
    cutoff = sess[i_end - 100]
    px = px[~px["ticker"].isin(shorts) | (px["date"] >= cutoff)].reset_index(drop=True)
    out = ER.derive_c4(px, names=names + shorts, fit_end=fit_end)
    assert out["L"] == 2 and out["stop_lag"] == 3
    assert set(out["excluded"]) == set(shorts) and all("usable rows" in v for v in out["excluded"].values())
    assert sorted(out["sample"]) == sorted(names)
    assert out["counts"]["n_pairs"] == 4 * len(names)
    # H13: the last response row is J sessions before the fit end; nothing later was read
    assert out["counts"]["last"] == sess[i_end - ER.DERIVE_RULE_LEADS]
    printed = capsys.readouterr().out
    assert "lag counts" in printed and "lead counts" in printed and "so L = 2" in printed
    assert "PLATEAU CHECK" in printed and "nothing is chosen" in printed
    # the lag-3 response after the fit end cannot have been read: over the full sample it would change L
    full = ER.derive_c4(px, names=names, fit_end=sess[-1])
    assert full["L"] >= 3


def test_c4_rule_declares_no_answer_rather_than_default(capsys):
    pytest.importorskip("statsmodels.api")
    # pure noise: every factor coefficient is noise, so lag 0 cannot beat the 19 leads' maximum
    sess = ER.nyse_sessions(dt.date(2004, 1, 2), dt.date(2011, 12, 30))
    rng = np.random.default_rng(5)
    E = pd.DataFrame(rng.normal(0, 0.005, size=(len(sess), 4)), index=sess, columns=["SPY", "IEF", "HYG", "PFF"])
    R = E.copy()
    names = [f"N{i}" for i in range(12)]
    for n in names:
        R[n] = rng.normal(0, 0.01, len(sess))
    px = _px_from_returns(R)
    out = ER.derive_c4(px, names=names, fit_end=sess[1300])
    assert out["L"] is None and "does not exceed" in out["why"]
    printed = capsys.readouterr().out
    assert "THE RULE HAS NO ANSWER" in printed and "UNMEASURED" in printed


def test_c4_rule_drops_a_split_read_as_adjusted_and_names_it():
    pytest.importorskip("statsmodels.api")
    R, sess, fit_end, names, _ = _c4_placebo_fixture(n_names=4, n_short=0)
    px = _px_from_returns(R)
    # a recorded 3:1 split on a close series with no step: yfinance's post-split Close
    day = sess[500]
    px.loc[(px["ticker"] == "N0") & (px["date"] == day), "split"] = 3.0
    from scripts.cef.data_guards import SplitBasisError
    with pytest.raises(SplitBasisError, match="already on the post-split"):
        ER.returns_panel(px)                                       # the core's path still raises
    out = ER.derive_c4(px, names=names, fit_end=fit_end)
    assert out["splits_dropped"] == [("N0", day.date().isoformat(), 3.0)]
    assert out["L"] == 2


def test_the_readout_applies_the_split_rule_only_for_c4():
    R = _c4_returns()
    px = _px_from_returns(R)
    day = SESS[100]                                  # inside the window, before the positions
    px.loc[(px["ticker"] == "AAA") & (px["date"] == day), "split"] = 3.0
    P = _positions(list(SESS[150:152]), {"AAA": 1000.0})
    fs = _c4_fs()
    ro = ER.readout(px, P, {"AAA": "equity_domestic"}, window=W, fs=fs)
    assert len(ro.exposure) == 8
    # a core-book readout over the same frames still refuses, naming the split
    core_like = replace(ER.CORE, factors=fs.factors, headline=fs.headline, universe=("AAA",))
    from scripts.cef.data_guards import SplitBasisError
    with pytest.raises(SplitBasisError):
        ER.readout(px, P, {"AAA": "x"}, window=W, lags=0, fs=core_like)


def test_c4_rule_constants_are_the_declared_ones():
    """Pin: THE C4 LAG RULE's declared numbers; a change must be a new declared rule."""
    assert ER.C4_RULE_MIN_SESSIONS == 252
    assert ER.DERIVE_MAX_LAG == 10 and ER.DERIVE_RULE_LEADS == 19 and ER.DERIVE_RULE_ALPHA == 0.05
    assert ER.FIT_END == pd.Timestamp("2022-12-30")


def test_fetch_each_excludes_a_failed_name_and_raises_on_a_failed_factor(monkeypatch):
    sess = ER.nyse_sessions(dt.date(2026, 1, 2), dt.date(2026, 1, 9))
    asof = sess[-1].date()

    def fake_fetch(tickers, start, asof_):
        tk = tickers[0]
        if tk == "BAD":
            raise ER.ReadoutError("yfinance returned no rows for BAD")
        return pd.DataFrame({"date": sess, "ticker": tk, "close": 10.0, "adj_close": 10.0,
                             "dividend": 0.0, "split": 0.0}), {tk: "absent"}

    monkeypatch.setattr(ER, "fetch_yf", fake_fetch)
    px, cg, failed = ER.fetch_each(["SPY", "AAA", "BAD"], sess[0].date(), asof, required=("SPY",))
    assert sorted(px["ticker"].unique()) == ["AAA", "SPY"] and set(failed) == {"BAD"}
    with pytest.raises(ER.ReadoutError, match="BAD"):
        ER.fetch_each(["BAD"], sess[0].date(), asof, required=("BAD",))


# The fit-era counts `derive --book c4` recorded on 2026-11-09 (module docstring, THE C4 RULE'S
# RESULT): keyless public prices, 2010-01-20 .. 2022-12-02, 72 names, 288 pairs. No account
# data. From the cache whose prices.parquet hashes to ER.C4_RULE_CACHE_SHA256 (asof 2026-11-06).
RECORDED_C4_LAG_COUNTS = dict(enumerate([254, 128, 83, 41, 36, 39, 48, 41, 35, 38, 29]))
RECORDED_C4_LEAD_COUNTS = dict(enumerate([56, 42, 47, 46, 24, 36, 25, 20, 26, 16, 44, 16, 65, 61, 36, 22, 25, 28, 16],
                                         start=1))


def test_c4_dimson_lags_is_the_rules_output_on_the_recorded_fit_era_counts():
    """Pin on a recorded result: the declared rule applied to the recorded counts gives the
    module constant; the counts are a record (they fail against the old constant None)."""
    r = ER.placebo_lag_rule(RECORDED_C4_LAG_COUNTS, RECORDED_C4_LEAD_COUNTS)
    assert r["T"] == 65 and r["stop_lag"] == 3
    assert ER.C4_DIMSON_LAGS == r["L"] == 2
    assert ER.factor_set("c4").dimson_lags == 2


def test_the_c4_crosscheck_reads_the_split_rule_and_the_core_keeps_its_guard(monkeypatch, tmp_path):
    R = _c4_returns()
    px = _px_from_returns(R)
    day = SESS[100]
    px.loc[(px["ticker"] == "AAA") & (px["date"] == day), "split"] = 3.0     # an already-adjusted recorded split
    monkeypatch.setattr(ER, "_panel", lambda path: (_ for _ in ()).throw(ER.ReadoutError("reached the panels")))
    with pytest.raises(ER.ReadoutError, match="reached the panels"):
        ER.crosscheck(px, tmp_path, fs=ER.factor_set("c4"))                  # the split does not stop C4's
    from scripts.cef.data_guards import SplitBasisError
    with pytest.raises(SplitBasisError, match="already on the post-split"):
        ER.crosscheck(px, tmp_path, fs=ER.CORE)                              # the core still refuses it


def test_cache_provenance_line_compares_the_cache_it_is_given():
    assert "the cache the recorded counts came from" in ER.cache_provenance_line(ER.C4_RULE_CACHE_SHA256,
                                                                                ER.C4_RULE_CACHE_SHA256, ER.C4_RULE_CACHE_ASOF)
    assert "DIFFERS" in ER.cache_provenance_line("0" * 64, ER.C4_RULE_CACHE_SHA256, ER.C4_RULE_CACHE_ASOF)
    assert ER.C4_RULE_CACHE_SHA256[:16] in ER.cache_provenance_line("0" * 64, ER.C4_RULE_CACHE_SHA256, ER.C4_RULE_CACHE_ASOF)
