"""Leakage-free ML on the research harness: labels, purged splits, out-of-sample
predictions, and the gate a model must pass before anyone trusts it.

WHY THIS FILE EXISTS (2026-10-27). The team lead named "no ML pipeline" as one of
the two infrastructure gaps, and ruled that the harness may be restructured
to close it. Everything here is built so that the usual ways ML leaks cannot be
reached by accident:

1. THE LABEL IS THE HARNESS'S. `label_panel` uses `harness.label`, the return
   evaluate() credits to a holding decided at t (t+1 -> t+2). A model trained
   on t -> t+1 is trained on a return the desk cannot earn.

2. PURGING IS DERIVED FROM LABEL INTERVALS, NEVER A ROW COUNT. skfolio's
   splitters take `purged_size` and `embargo_size` as fixed row counts, and both
   default to 0, which leaks (skfolio 1.12.2, 3-0 verified 2026-10-27). Here a
   training row is dropped when its label interval [start, end] overlaps a test
   label's interval, using López de Prado's three overlap conditions with
   closed intervals ("The 10 Reasons Most Machine Learning Funds Fail", 2018,
   Solution #8). Under shift(2) that removes one decision date on each side of
   each test block.

3. THE EMBARGO HAS NO DEFAULT. López de Prado's h ~ 0.01T "often suffices" comes
   with no derivation (a grep of the paper found none, 2026-10-27). So the
   caller states it, and combinatorial CV refuses an embargo below 1 session.
   The embargo matters when features are long rolling windows: measure it by
   planting a known leak in synthetic data, not by the rule of thumb.

4. WALK-FORWARD IS THE BACKTEST; CPCV IS THE OVERFITTING DISTRIBUTION.
   `walk_forward_predict` asserts that every label a model trained on was
   realised by the close of the first decision it predicts. Its output is a
   series the desk could have traded, and the only one that goes to
   `harness.report` and the trial registry. Combinatorial purged CV trains on
   data from AFTER its test groups. That is legitimate for estimating how
   out-of-sample Sharpe is distributed over C(N-1, k-1) paths (3-0 verified),
   but it is never a tradable record. The paths share training data, so their
   spread understates the uncertainty.

5. A COMPLEX MODEL MUST RECOVER A KNOWN REVERSAL FIRST. Nagel (NBER WP 34104,
   2025) shows a high-complexity return model collapsing to volatility-timed
   momentum, and building momentum even on synthetic data where returns
   reverse. A discount-reversion desk cannot use a model with that failure.
   `reversal_gate` runs the candidate on a synthetic panel whose true
   relationship is reversal, through this pipeline, and fails it unless its
   out-of-sample predictions line up with the truth.

Default model: ridge in closed form. Arnott, Harvey & Markowitz (2019): "It is
always necessary to impose structure." With 13-17 names, start low-dimensional.
"""
from __future__ import annotations

from itertools import combinations
from math import comb
from typing import Callable

import numpy as np
import pandas as pd

from scripts.research import harness as hz

# ---------------------------------------------------------------------------
# Labels and their intervals.
# ---------------------------------------------------------------------------


def label_intervals(index: pd.DatetimeIndex) -> pd.DataFrame:
    """For each decision date t: the closes that bound the return its label is
    (start = index[t + EXEC_LAG - 1], end = index[t + EXEC_LAG]). Rows whose
    label has not happened yet have NaT and are never trained on."""
    idx = pd.DatetimeIndex(index)
    n = len(idx)
    start = pd.Series(pd.NaT, index=idx, dtype="datetime64[ns]")
    end = start.copy()
    k = n - hz.EXEC_LAG
    if k > 0:
        start.iloc[:k] = idx[hz.EXEC_LAG - 1:n - 1]
        end.iloc[:k] = idx[hz.EXEC_LAG:]
    return pd.DataFrame({"start": start, "end": end})


def label_panel(R: pd.DataFrame) -> pd.Series:
    """The harness label, stacked to (date, name). NaN where the return is
    unknown: the last EXEC_LAG decision dates, and names with no return."""
    y = hz.label(R).stack(future_stack=True)
    y.index.names = ["date", "name"]
    return y


# ---------------------------------------------------------------------------
# Purged splits.
# ---------------------------------------------------------------------------


def _purge(train: np.ndarray, test_blocks: list[np.ndarray], iv: pd.DataFrame,
           embargo: int) -> np.ndarray:
    """Drop training rows whose closed label interval overlaps any test row's,
    after extending each test block's end by `embargo` sessions (López de
    Prado: embargo after the test block only)."""
    s = iv["start"].to_numpy()
    e = iv["end"].to_numpy()
    idx = iv.index
    keep = np.ones(len(train), dtype=bool)
    ts, te = s[train], e[train]
    labelled = ~pd.isna(ts)
    keep &= labelled
    for blk in test_blocks:
        # pandas min/max skip NaT; numpy's propagate it, and a block holding the panel's
        # last (unlabelled) rows would then purge nothing (caught by test_ml).
        b0, b1 = pd.Series(s[blk]).min(), pd.Series(e[blk]).max()
        if pd.isna(b0):
            continue
        last = idx.searchsorted(b1)
        if embargo:
            last = min(last + embargo, len(idx) - 1)
        b1 = idx[last]
        overlap = (ts <= b1) & (te >= b0)
        keep &= ~overlap
    return train[keep]


def walk_forward_splits(index: pd.DatetimeIndex, *, min_train: int, test_size: int,
                        train_window: int | None = None) -> list[tuple[np.ndarray, np.ndarray]]:
    """Expanding (or rolling, with `train_window`) walk-forward splits over
    decision rows. Each test block is the next `test_size` rows. Training rows
    are those before it, purged of any whose label is not realised by the
    block's first decision. Rows whose own label is unknown are never trained
    on."""
    if min_train < 2 or test_size < 1:
        raise ValueError("min_train must be >= 2 and test_size >= 1")
    iv = label_intervals(index)
    n = len(iv)
    out = []
    a = min_train
    while a < n:
        b = min(a + test_size, n)
        lo = 0 if train_window is None else max(0, a - train_window)
        train = _purge(np.arange(lo, a), [np.arange(a, b)], iv, embargo=0)
        if len(train) >= 2:
            out.append((train, np.arange(a, b)))
        a = b
    if not out:
        raise ValueError("no split has two labelled training rows; the index is too short")
    return out


def cpcv_splits(index: pd.DatetimeIndex, *, n_groups: int, k_test: int,
                embargo: int) -> list[dict]:
    """Combinatorial purged CV: N contiguous groups, every choice of k as the
    test set, purged and embargoed. There are C(N, k) splits and
    C(N-1, k-1) complete paths (`cpcv_paths`).

    NOT A TRADABLE BACKTEST: training rows come from both sides of the test
    groups."""
    if not (1 <= k_test < n_groups):
        raise ValueError("need 1 <= k_test < n_groups (k_test = 1 is purged k-fold)")
    if embargo < 1:
        raise ValueError("combinatorial CV trains on data after its test groups, so it needs "
                         "an embargo of at least 1 session; measure it, do not assume it")
    iv = label_intervals(index)
    groups = np.array_split(np.arange(len(iv)), n_groups)
    out = []
    for test_g in combinations(range(n_groups), k_test):
        test_blocks = [groups[g] for g in test_g]
        train = np.concatenate([groups[g] for g in range(n_groups) if g not in test_g])
        out.append(dict(test_groups=test_g, test=np.concatenate(test_blocks),
                        train=_purge(train, test_blocks, iv, embargo)))
    return out


def cpcv_paths(n_groups: int, k_test: int) -> np.ndarray:
    """Which split supplies each group on each path: an array of shape
    (C(N-1, k-1), N). Path p takes group g's prediction from the p-th split,
    in `cpcv_splits` order, that tests g."""
    splits = list(combinations(range(n_groups), k_test))
    n_paths = comb(n_groups - 1, k_test - 1)
    A = np.full((n_paths, n_groups), -1)
    seen = np.zeros(n_groups, dtype=int)
    for s, gs in enumerate(splits):
        for g in gs:
            A[seen[g], g] = s
            seen[g] += 1
    assert (seen == n_paths).all() and (A >= 0).all()
    return A


# ---------------------------------------------------------------------------
# Fitting and predicting on a (date, name) panel.
# ---------------------------------------------------------------------------


def ridge(alpha: float) -> tuple[Callable, Callable]:
    """Closed-form ridge with an unpenalised intercept: (fit, predict). The
    default model, low-dimensional by design."""
    if alpha < 0:
        raise ValueError("alpha must be >= 0")

    def fit(X: np.ndarray, y: np.ndarray):
        mx, my = X.mean(axis=0), y.mean()
        Xc = X - mx
        beta = np.linalg.solve(Xc.T @ Xc + alpha * np.eye(X.shape[1]), Xc.T @ (y - my))
        return dict(beta=beta, a=my - mx @ beta)

    def predict(m, X: np.ndarray) -> np.ndarray:
        return X @ m["beta"] + m["a"]

    return fit, predict


def _rows(X: pd.DataFrame, y: pd.Series, dates: pd.DatetimeIndex):
    m = X.index.get_level_values("date").isin(dates)
    return X[m], y[m]


def walk_forward_predict(X: pd.DataFrame, y: pd.Series, *, fit: Callable, predict: Callable,
                         splits: list[tuple[np.ndarray, np.ndarray]]) -> tuple[pd.DataFrame, dict]:
    """Out-of-sample scores, dates x names, from a model refitted on each walk-forward split.

    X is (date, name)-indexed features built from data <= date. Prove that with
    `harness.truncation_check` on the feature builder. y is `label_panel(R)` on
    the same index. Training rows with a NaN feature or label are excluded and
    counted. Nothing is filled. Prediction rows with a NaN feature get a NaN
    score, which the weight builder treats as ineligible.

    Raises LookaheadError if any training label ends after the first decision
    of the block it predicts.
    """
    if not X.index.equals(y.index):
        raise ValueError("X and y must share one (date, name) index")
    dates = pd.DatetimeIndex(X.index.get_level_values("date").unique()).sort_values()
    iv = label_intervals(dates)
    scores = []
    dropped = 0
    skipped = []
    for train, test in splits:
        tr_d, te_d = dates[train], dates[test]
        last_label = iv["end"].iloc[train].max()
        if not last_label <= te_d[0]:
            raise hz.LookaheadError(f"a training label ends {last_label.date()}, after the first "
                                    f"decision it predicts ({te_d[0].date()})")
        Xtr, ytr = _rows(X, y, tr_d)
        ok = Xtr.notna().all(axis=1) & ytr.notna()
        dropped += int((~ok).sum())
        if ok.sum() < X.shape[1] + 2:
            # Counted and listed, never silent: those dates get no score, so the
            # book is flat there (quant-reviewer, 2026-10-28).
            skipped.append((te_d[0].date().isoformat(), te_d[-1].date().isoformat()))
            continue
        model = fit(Xtr[ok].to_numpy(dtype=float), ytr[ok].to_numpy(dtype=float))
        Xte, _ = _rows(X, y, te_d)
        good = Xte.notna().all(axis=1)
        p = pd.Series(np.nan, index=Xte.index)
        if good.any():
            p[good] = predict(model, Xte[good].to_numpy(dtype=float))
        scores.append(p)
    if not scores:
        raise ValueError("no split had enough labelled training rows to fit")
    S = pd.concat(scores).unstack("name")
    return S, dict(train_rows_dropped_nan=dropped, first_oos=S.index[0].date().isoformat(),
                   splits=len(splits), splits_run=len(splits) - len(skipped),
                   splits_skipped=skipped)


# ---------------------------------------------------------------------------
# The gate: recover a reversal you were given.
# ---------------------------------------------------------------------------


def synthetic_reversal(n_days: int = 2500, n_names: int = 15, *, phi: float = 0.97,
                       kappa: float = 0.002, noise: float = 0.01, seed: int = 0):
    """A panel whose truth is discount-style reversal.

    Each name has a persistent state z (AR(1), coefficient phi), and its next
    return is -kappa * z plus noise. The expected label at t is therefore
    -kappa * phi * z_t: long the low state. Returns (X, R, truth): X is the
    (date, name) feature panel [z_t, r_t]; truth is the expected label,
    dates x names. Synthetic data tests the method, never the market."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2000-01-03", periods=n_days)
    z = np.zeros((n_days, n_names))
    for t in range(1, n_days):
        z[t] = phi * z[t - 1] + rng.normal(0, 1, n_names) * np.sqrt(1 - phi ** 2)
    r = np.zeros_like(z)
    r[1:] = -kappa * z[:-1] + rng.normal(0, noise, (n_days - 1, n_names))
    cols = [f"S{i:02d}" for i in range(n_names)]
    Z = pd.DataFrame(z, index=idx, columns=cols)
    R = pd.DataFrame(r, index=idx, columns=cols)
    X = pd.concat({"z": Z.stack(), "r": R.stack()}, axis=1)
    X.index.names = ["date", "name"]
    truth = -kappa * phi * Z
    return X, R, truth


def reversal_gate(fit: Callable, predict: Callable, *, seed: int = 0, n_days: int = 2500,
                  min_corr: float = 0.5) -> dict:
    """Run a candidate model through this pipeline on `synthetic_reversal`.
    Pass only if its out-of-sample scores line up with the true expected
    return (mean cross-sectional correlation >= min_corr) and the book built
    from them earns a positive gross Sharpe under the harness.

    A model that builds momentum whatever the data say, as in Nagel's RFF
    example, fails both checks."""
    X, R, truth = synthetic_reversal(n_days=n_days, seed=seed)
    y = label_panel(R)
    dates = R.index
    splits = walk_forward_splits(dates, min_train=500, test_size=250)
    S, info = walk_forward_predict(X, y, fit=fit, predict=predict, splits=splits)
    T = truth.reindex(S.index)
    corr = S.T.corrwith(T.T).mean()
    W = hz.cross_sectional_weights(S.reindex(dates), S.reindex(dates).notna(), direction=1,
                                   scheme="z", min_names=5, on_thin="flat")
    res = hz.evaluate(W.loc[S.index[0]:], R.loc[S.index[0]:])
    return dict(passed=bool(corr >= min_corr and res["gross_sr"] > 0), mean_corr=float(corr),
                gross_sr=float(res["gross_sr"]), **info)
