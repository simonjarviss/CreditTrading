"""`band_gross_capped(..., defer_flips=True)` is the live runner's deferred flip.

`quantt/session/decide.py` with `FLIP_SAME_SESSION = False` sends only the
closing leg of a long<->short flip, so the name sits flat for one session and
the band opens the other side from flat on the next. These tests pin that the
harness model does exactly that, that the default path is unchanged, and that
the deferral never rescales the other names (decide.py sends them as sized).
Synthetic panels: the claim is about the code, not the market.

Checked to fail against the old behaviour (2026-11-02): with the deferral
removed from `band_gross_capped` (i.e. `defer_flips` ignored), the hand path and
the no-direct-flip property both fail (2 of 4; the other two pin the default and
the no-rescale property, which hold by construction without the deferral). Used
by results/backtests/turnover-live-2026-11-02/turnover_live.py.
"""
import numpy as np
import pandas as pd

from scripts.cef import band_frontier as bf


def _targets(seed=0, n=400, k=8, scale=1.0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, k)).cumsum(axis=0) * 0.05
    x = x - x.mean(axis=1, keepdims=True)
    return pd.DataFrame(x * scale, index=pd.bdate_range("2020-01-01", periods=n),
                        columns=[f"T{i}" for i in range(k)])


def test_default_is_unchanged():
    for seed, scale in ((0, 1.0), (1, 3.0)):
        T = _targets(seed=seed, scale=scale)
        for cap in (1.8, np.inf):
            pd.testing.assert_frame_equal(bf.band_gross_capped(T, 0.048, cap, defer_flips=False),
                                          bf.band_gross_capped(T, 0.048, cap))


def test_hand_path_flat_for_one_session_then_open_to_the_edge():
    idx = pd.bdate_range("2021-01-04", periods=6)
    # A: long, then a target far on the short side (a flip), still short,
    # then a short target inside the band from flat (never opened), then long.
    a = [0.30, -0.30, -0.30, -0.03, 0.30, 0.30]
    T = pd.DataFrame({"A": a, "B": [-x for x in a]}, index=idx)
    b = 0.05
    H = bf.band_gross_capped(T, b, np.inf, defer_flips=True)["A"].round(12).tolist()
    # day0 from flat: edge 0.25. day1 flip -> flat. day2 from flat: edge -0.25.
    # day3: gap +0.22 > b -> edge -0.08 (no flip). day4: flip -> flat.
    # day5 from flat: edge 0.25.
    assert H == [0.25, 0.0, -0.25, -0.08, 0.0, 0.25]
    # the instant book flips on day1 and day4 to the same edges
    I = bf.band_gross_capped(T, b, np.inf)["A"].round(12).tolist()
    assert I == [0.25, -0.25, -0.25, -0.08, 0.25, 0.25]


def test_no_direct_flip_and_only_flipping_names_differ_on_the_day():
    T = _targets(seed=2, scale=2.0)
    for cap in (1.8, np.inf):
        D = bf.band_gross_capped(T, 0.048, cap, defer_flips=True)
        prod = (D.shift(1).fillna(0.0) * D)
        assert (prod >= 0).all().all(), "a name went long<->short in one session"
    # without a ceiling, names are independent: D equals the instant book on
    # every name-day except where the paths have diverged through a deferral
    I = bf.band_gross_capped(T, 0.048, np.inf)
    D = bf.band_gross_capped(T, 0.048, np.inf, defer_flips=True)
    flips = ((I.shift(1).fillna(0.0) * I) < 0)
    assert flips.any().any(), "the instant book never flips -- vacuous test"
    first = flips.any(axis=1).values.argmax()
    pd.testing.assert_frame_equal(D.iloc[:first], I.iloc[:first])
    row = D.iloc[first]
    assert (row[flips.iloc[first]] == 0.0).all()
    pd.testing.assert_series_equal(row[~flips.iloc[first]], I.iloc[first][~flips.iloc[first]])


def test_a_deferral_does_not_rescale_the_rest_under_a_binding_cap():
    T = _targets(seed=3, scale=3.0)
    cap = 1.8
    I = bf.band_gross_capped(T, 0.048, cap)
    D = bf.band_gross_capped(T, 0.048, cap, defer_flips=True)
    assert (D.abs().sum(axis=1) <= cap + 1e-12).all()
    flips = ((I.shift(1).fillna(0.0) * I) < 0)
    first = flips.any(axis=1).values.argmax()
    assert flips.iloc[first].any()
    keep = ~flips.iloc[first]
    # same path up to that day, so the sleeve's sizing of the rest is identical
    np.testing.assert_allclose(D.iloc[first][keep].values, I.iloc[first][keep].values, rtol=0, atol=0)
