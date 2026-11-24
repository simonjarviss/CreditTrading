"""`band_gross_capped(..., below_min_names=)` and `thin_sessions`: the live sleeve's thin-session rule.

THE LIVE RULE (read 2026-11-03): with fewer than `min_names` eligible names the
sleeve emits every name FLAT before the band and the ceiling run
(`src/deploy/sleeves/cef_discount.py` l.841, l.892-895), decide.py closes every
whole share (`quantt/session/decide.py` l.243-244; v7 `min_trade_usd` $0), and
the next session's band opens from flat to the EDGE. The harness default,
"hold", carries the previous target instead (`build_targets`, "hold; nothing
eligible"). These tests pin:

  1. the default is "hold" and is the pre-2026-11-03 loop, element for element
     (a copy of that loop lives here, so a change of default or of the hold path
     fails);
  2. "flatten" goes STRAIGHT TO ZERO on a thin session (not to within the band
     of zero) and re-enters at the band edge, by hand;
  3. "flatten" equals an independently written loop on random targets and thin
     masks, with and without the ceiling and the deferred flip;
  4. the argument checks raise rather than guess;
  5. `thin_sessions` and `build_targets` count eligibility with one rule: the
     sessions build_targets holds on are exactly the ones thin_sessions flags;
  6. flatten and hold agree up to the first thin session;
  7. a `thin` mask counted with other arguments than T raises, in both
     directions (added 2026-11-03 after review: the WIDE targets with the
     spec-floor mask were accepted and flattened 3,621 trading sessions).

Synthetic panels: the claim is about the code, not the market.

Checked to fail against the old behaviour (2026-11-03), each mutation applied
to band_frontier.py and the file restored after:
  * the pre-edit file (option, `thin_sessions` and `BELOW_MIN_NAMES` absent):
    every test fails;
  * the default changed to "flatten": tests 1, 2, 3, 4 and 6 fail (each calls
    the default without `thin`, which then raises, or passes `thin` to it,
    which then no longer raises);
  * the thin row banded toward a zero target instead of zeroed: tests 2, 3
    and 6 fail;
  * `thin_sessions` given its own floor test (`> floor` for `>= floor`):
    test 5 fails.
Test 7 and the guard it pins (`_check_thin_matches_T`), each mutation applied
and the file restored after (2026-11-03):
  * the guard's call removed: test 7 fails;
  * the "moved on a thin row" raise removed: test 7 fails;
  * the "held a nonzero row the mask calls active" raise removed: test 7 fails;
  * the zero-row exemption removed: test 7 fails.
Used by results/backtests/thin-days-2026-11-03/thin_days.py.
"""
import inspect

import numpy as np
import pandas as pd
import pytest

from scripts.cef import band_frontier as bf
from src.deploy.sleeves.cef_discount import _cap_gross


def _targets(seed=0, n=300, k=8, scale=1.0):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, k)).cumsum(axis=0) * 0.05
    x = x - x.mean(axis=1, keepdims=True)
    return pd.DataFrame(x * scale, index=pd.bdate_range("2020-01-01", periods=n),
                        columns=[f"T{i}" for i in range(k)])


def _thin(T, seed=0, p=0.15):
    """Random thin sessions in runs, as the panel has them."""
    rng = np.random.default_rng(seed + 100)
    on = np.zeros(len(T), bool)
    i = 0
    while i < len(T):
        if rng.random() < p / 5:
            k = int(rng.integers(1, 12))
            on[i:i + k] = True
            i += k
        i += 1
    return pd.Series(on, index=T.index)


def _hold_on_thin(T, thin):
    """T as `build_targets` would leave it: the previous row repeated on every
    thin session after the first row (the contract `_check_thin_matches_T`
    enforces on the flatten path)."""
    A = T.values.copy()
    th = thin.to_numpy()
    for i in range(1, len(A)):
        if th[i]:
            A[i] = A[i - 1]
    return pd.DataFrame(A, index=T.index, columns=T.columns)


def _old_loop(T, b, cap):
    """band_gross_capped before 2026-11-03 (no unshortable, no deferral), copied."""
    A, cur = T.values, np.zeros(T.shape[1])
    H = np.zeros_like(A)
    for i in range(len(A)):
        gap = A[i] - cur
        mv = np.abs(gap) > b
        cur = cur.copy()
        cur[mv] = A[i][mv] - np.sign(gap[mv]) * b
        if np.isfinite(cap):
            cur = _cap_gross(pd.Series(cur, index=T.columns), cap)[0].values
        H[i] = cur
    return pd.DataFrame(H, index=T.index, columns=T.columns)


def _independent_flatten(T, b, cap, thin, defer=False):
    """Written separately from band_gross_capped: zero on a thin row, else band,
    ceiling, then (optionally) a sign change from yesterday held flat."""
    held = []
    prev = pd.Series(0.0, index=T.columns)
    for d in T.index:
        if thin.loc[d]:
            now = pd.Series(0.0, index=T.columns)
        else:
            tgt = T.loc[d]
            now = prev.copy()
            out = (tgt - prev).abs() > b
            now[out] = tgt[out] - np.sign((tgt - prev)[out]) * b
            g = now.abs().sum()
            if np.isfinite(cap) and g > cap:
                now = now * (cap / g)
            if defer:
                now[(prev * now) < 0] = 0.0
        held.append(now.values)
        prev = now
    return pd.DataFrame(held, index=T.index, columns=T.columns)


def test_1_default_is_hold_and_is_the_old_loop():
    assert inspect.signature(bf.band_gross_capped).parameters["below_min_names"].default == "hold"
    assert bf.BELOW_MIN_NAMES[0] == "hold"
    for seed, scale in ((0, 1.0), (1, 3.0)):
        T = _targets(seed=seed, scale=scale)
        for cap in (1.8, np.inf):
            ref = _old_loop(T, 0.048, cap)
            np.testing.assert_array_equal(bf.band_gross_capped(T, 0.048, cap).values, ref.values)
            np.testing.assert_array_equal(
                bf.band_gross_capped(T, 0.048, cap, below_min_names="hold").values, ref.values)


def test_2_flatten_goes_straight_to_zero_then_reopens_at_the_edge():
    idx = pd.bdate_range("2021-01-04", periods=6)
    # under hold, build_targets carries the target through the thin days 2-3
    # (day1 moves to 0.29 so that no ACTIVE day repeats its predecessor, which
    # the mask check would refuse; 0.29 is inside the band of day0's 0.25)
    a = [0.30, 0.29, 0.29, 0.29, 0.30, 0.02]
    T = pd.DataFrame({"A": a, "B": [-x for x in a]}, index=idx)
    thin = pd.Series([False, False, True, True, False, False], index=idx)
    b = 0.05
    F = bf.band_gross_capped(T, b, np.inf, below_min_names="flatten", thin=thin)["A"].round(12).tolist()
    # day0 from flat: edge 0.25; day1 inside the band, held; day2-3 thin: ZERO (a band toward a
    # zero target would stop at the edge 0.05); day4 from flat: edge 0.25;
    # day5: target 0.02, gap -0.23 > b -> edge 0.07
    assert F == [0.25, 0.25, 0.0, 0.0, 0.25, 0.07]
    Hh = bf.band_gross_capped(T, b, np.inf)["A"].round(12).tolist()
    assert Hh == [0.25, 0.25, 0.25, 0.25, 0.25, 0.07]


@pytest.mark.parametrize("cap", [1.8, np.inf])
@pytest.mark.parametrize("defer", [False, True])
def test_3_flatten_equals_an_independent_loop(cap, defer):
    for seed, scale in ((2, 1.0), (3, 3.0)):
        T0 = _targets(seed=seed, scale=scale)
        thin = _thin(T0, seed=seed)
        assert thin.any() and (~thin).any(), "vacuous mask"
        T = _hold_on_thin(T0, thin)
        got = bf.band_gross_capped(T, 0.048, cap, defer_flips=defer,
                                   below_min_names="flatten", thin=thin)
        ref = _independent_flatten(T, 0.048, cap, thin, defer=defer)
        np.testing.assert_allclose(got.values, ref.values, rtol=0, atol=1e-15)
        assert (got[thin.values] == 0.0).all().all()
        # a book with no thin session is the hold book exactly (on the random
        # targets, which repeat no row, so the mask check has nothing to refuse)
        none = pd.Series(False, index=T0.index)
        np.testing.assert_array_equal(
            bf.band_gross_capped(T0, 0.048, cap, defer_flips=defer, below_min_names="flatten",
                                 thin=none).values,
            bf.band_gross_capped(T0, 0.048, cap, defer_flips=defer).values)


def test_4_arguments_raise_rather_than_guess():
    T = _targets(seed=4)
    thin = _thin(T, seed=4)
    with pytest.raises(ValueError, match="needs thin"):
        bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten")
    with pytest.raises(ValueError, match="only read"):
        bf.band_gross_capped(T, 0.048, 1.8, thin=thin)
    with pytest.raises(ValueError, match="must be one of"):
        bf.band_gross_capped(T, 0.048, 1.8, below_min_names="close")
    with pytest.raises(ValueError, match="own index"):
        bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten", thin=thin.iloc[1:])
    with pytest.raises(TypeError, match="bool"):
        bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten", thin=thin.astype(int))
    with pytest.raises(ValueError, match="NaN"):
        bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten",
                             thin=thin.astype(object).where(thin.index != thin.index[3], None))
    with pytest.raises(TypeError, match="Series"):
        bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten", thin=thin.values)


def _fake_panel(monkeypatch, cols, seed=5):
    """z with NaN holes and ADVs straddling the floor (and some NaN), so that the
    eligible count crosses min_names in both directions many times."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2004-11-01", periods=260)
    z = pd.DataFrame(rng.normal(0, 1, (len(idx), len(cols))), index=idx, columns=cols)
    z = z.mask(rng.random(z.shape) < 0.10)
    floor = bf.MIN_ADV
    adv = pd.DataFrame(rng.choice([2 * floor, floor, 0.5 * floor, np.nan], size=z.shape,
                                  p=[0.60, 0.15, 0.20, 0.05]), index=idx, columns=cols)
    # the first 80 sessions (about 35 after SAMPLE_START) are fully eligible, so
    # the flatten and hold books share a prefix that test 6 can compare
    z.iloc[:80] = rng.normal(0, 1, (80, len(cols)))
    adv.iloc[:80] = 2 * floor
    ret = pd.DataFrame(rng.normal(0, 0.01, z.shape), index=idx, columns=cols)
    monkeypatch.setattr(bf, "build_panel",
                        lambda end=None, universe=None, source=None, mask=None: dict(ret=ret, z=z, adv=adv))
    return z, adv


def test_5_thin_sessions_is_build_targets_hold_set(monkeypatch):
    cols = [f"N{i}" for i in range(10)]
    z, adv = _fake_panel(monkeypatch, cols)
    T, _ = bf.build_targets(universe=cols)
    thin = bf.thin_sessions(T.index, universe=cols)
    assert thin.dtype == bool and thin.index.equals(T.index)
    assert thin.iloc[1:].any() and (~thin.iloc[1:]).any(), "vacuous panel"
    same_as_prev = (T.diff().abs().sum(axis=1) == 0).to_numpy()
    # every thin row (after the first) repeats the previous target; no active row does
    assert (same_as_prev[1:] == thin.to_numpy()[1:]).all()
    # the count, by hand: z present and ADV >= floor (NaN ADV fails); exactly-at-floor passes
    ok = z.reindex(T.index).notna() & (adv.reindex(T.index) >= bf.MIN_ADV)
    np.testing.assert_array_equal(thin.to_numpy(), (ok.sum(axis=1) < bf.MIN_NAMES).to_numpy())
    with pytest.raises(ValueError, match="does not hold"):
        bf.thin_sessions(T.index.append(pd.DatetimeIndex(["2031-01-02"])), universe=cols)


def test_6_flatten_with_the_real_mask_differs_from_hold_only_from_a_thin_session(monkeypatch):
    cols = [f"N{i}" for i in range(10)]
    _fake_panel(monkeypatch, cols, seed=6)
    T, _ = bf.build_targets(universe=cols)
    thin = bf.thin_sessions(T.index, universe=cols)
    Hh = bf.band_gross_capped(T, 0.048, 1.8)
    Hf = bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten", thin=thin)
    first = int(np.argmax(thin.to_numpy()))
    assert first > 20 and thin.iloc[first:].mean() < 0.6, "the fake panel no longer tests a prefix"
    pd.testing.assert_frame_equal(Hf.iloc[:first], Hh.iloc[:first])
    assert (Hf[thin.values] == 0.0).all().all()


def test_7_a_mask_counted_with_other_arguments_than_T_raises(monkeypatch):
    # by hand: the mask flags a session on which T moved
    T0 = _targets(seed=7)
    thin = _thin(T0, seed=7)
    T = _hold_on_thin(T0, thin)
    bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten", thin=thin)   # consistent: no raise
    extra = thin.copy()
    j = int(np.flatnonzero(~thin.to_numpy()[1:])[0]) + 1
    extra.iloc[j] = True
    with pytest.raises(ValueError, match="on which T moved"):
        bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten", thin=extra)
    # by hand: T held a nonzero row that the mask calls active
    missing = thin.copy()
    k = int(np.flatnonzero(thin.to_numpy()[1:])[0]) + 1
    missing.iloc[k] = False
    with pytest.raises(ValueError, match="repeats a nonzero row"):
        bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten", thin=missing)
    # zero rows are exempt: a book that has not opened repeats zero on active sessions
    Z = T.copy()
    Z.iloc[:5] = 0.0
    zthin = thin.copy()
    zthin.iloc[:5] = False
    bf.band_gross_capped(_hold_on_thin(Z, zthin), 0.048, 1.8, below_min_names="flatten", thin=zthin)

    # on a panel: T at the spec floor, the mask at another floor, both directions
    cols = [f"N{i}" for i in range(10)]
    _fake_panel(monkeypatch, cols, seed=6)
    T, _ = bf.build_targets(universe=cols)
    ok = bf.thin_sessions(T.index, universe=cols)
    bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten", thin=ok)
    looser = bf.thin_sessions(T.index, universe=cols, min_adv=0)
    stricter = bf.thin_sessions(T.index, universe=cols, min_adv=2 * bf.MIN_ADV)
    assert (looser != ok).any() and (stricter != ok).any(), "the floors no longer change the mask"
    with pytest.raises(ValueError, match="repeats a nonzero row"):
        bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten", thin=looser)
    with pytest.raises(ValueError, match="on which T moved"):
        bf.band_gross_capped(T, 0.048, 1.8, below_min_names="flatten", thin=stricter)
