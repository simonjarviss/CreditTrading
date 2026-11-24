"""The ML pipeline: labels from the harness, purging from label intervals, the
CPCV counts as golden numbers, and the reversal gate.

Checked to fail against the behaviour each test guards:
- the purge tests, against `_purge` returning `train` unchanged (skfolio's
  default, purge 0 and embargo 0);
- the path counts, against a path builder that indexes splits by group order;
- the gate, against a model that builds momentum on the state.
"""
from __future__ import annotations

import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research import harness as hz  # noqa: E402
from scripts.research import ml  # noqa: E402

IDX = pd.bdate_range("2010-01-04", periods=120)


def test_label_intervals_bound_the_credited_return():
    iv = ml.label_intervals(IDX)
    assert iv["start"].iloc[0] == IDX[1] and iv["end"].iloc[0] == IDX[2]
    assert iv["end"].iloc[-hz.EXEC_LAG:].isna().all()
    assert iv["end"].iloc[-hz.EXEC_LAG - 1] == IDX[-1]


def test_label_panel_is_the_harness_label():
    R = pd.DataFrame(np.arange(240.).reshape(120, 2), index=IDX, columns=["A", "B"])
    y = ml.label_panel(R)
    assert y.loc[(IDX[0], "A")] == R["A"].iloc[2]
    assert np.isnan(y.loc[(IDX[-1], "B")])


def test_walk_forward_trains_only_on_realised_labels():
    iv = ml.label_intervals(IDX)
    for train, test in ml.walk_forward_splits(IDX, min_train=30, test_size=20):
        a = test[0]
        assert train.max() <= a - hz.EXEC_LAG
        assert iv["end"].iloc[train].max() <= IDX[a]


def test_cpcv_counts_are_the_golden_numbers():
    s = ml.cpcv_splits(IDX, n_groups=6, k_test=2, embargo=2)
    assert len(s) == comb(6, 2) == 15
    P = ml.cpcv_paths(6, 2)
    assert P.shape == (comb(5, 1), 6) == (5, 6)
    assert ml.cpcv_paths(10, 5).shape[0] == 126
    for p in P:                                  # each path's group g comes from a split testing g
        for g, si in enumerate(p):
            assert g in s[si]["test_groups"]


def test_cpcv_purges_both_sides_and_embargoes_after():
    s = ml.cpcv_splits(IDX, n_groups=6, k_test=1, embargo=3)
    groups = np.array_split(np.arange(len(IDX)), 6)
    mid = s[2]                                   # test group 2
    a, b = groups[2][0], groups[2][-1]
    tr = set(mid["train"])
    assert a - 1 not in tr and a - 2 in tr       # before: purge one decision (closed intervals)
    # after: the last test label ends at row b+2; embargo 3 extends to b+5; a train row
    # starting at or before that is purged
    assert all(r not in tr for r in range(b + 1, b + 5)) and b + 6 in tr


def test_cpcv_refuses_no_embargo():
    with pytest.raises(ValueError, match="embargo"):
        ml.cpcv_splits(IDX, n_groups=6, k_test=2, embargo=0)


def test_walk_forward_predict_refuses_a_leaky_split():
    X, R, _ = ml.synthetic_reversal(n_days=300, n_names=5)
    y = ml.label_panel(R)
    bad = [(np.arange(0, 200), np.arange(150, 250))]     # trains on labels after the block starts
    fit, predict = ml.ridge(1.0)
    with pytest.raises(hz.LookaheadError):
        ml.walk_forward_predict(X, y, fit=fit, predict=predict, splits=bad)


def test_reversal_gate_passes_ridge():
    fit, predict = ml.ridge(1.0)
    g = ml.reversal_gate(fit, predict, seed=1)
    assert g["passed"] and g["mean_corr"] > 0.9 and g["gross_sr"] > 0


def test_reversal_gate_fails_a_model_that_builds_momentum():
    def fit(X, y):
        return None

    def predict(m, X):                           # long the high state: momentum, the Nagel failure
        return X[:, 0]
    g = ml.reversal_gate(fit, predict, seed=1)
    assert not g["passed"] and g["mean_corr"] < 0


def test_skipped_splits_are_counted_and_listed():
    X, R, _ = ml.synthetic_reversal(n_days=900, n_names=5, seed=3)
    early = X.index.get_level_values("date") < R.index[400]
    X.loc[early] = np.nan
    y = ml.label_panel(R)
    fit, predict = ml.ridge(1.0)
    splits = ml.walk_forward_splits(R.index, min_train=100, test_size=100)
    _, info = ml.walk_forward_predict(X, y, fit=fit, predict=predict, splits=splits)
    assert info["splits_run"] + len(info["splits_skipped"]) == info["splits"] == len(splits)
    assert len(info["splits_skipped"]) >= 2
