"""`below_min_names="trade_eligible"` and `build_targets(min_names=)`: the third thin-session rule.

THE RULE (results/backtests/thin-third-rule-2026-11-03/, a zero-trial report;
NOT the live rule): on a session with fewer than the spec's `min_names` but at
least `floor` eligible names, the book trades the eligible names with the
sleeve's own construction on that smaller set; below `floor` it goes FLAT, as
the live sleeve does. In the harness that is

    T    = build_targets(min_names=floor)
    thin = thin_sessions(T.index, min_names=floor)          # named "thin_below_<floor>"
    H    = band_gross_capped(T, b, cap, below_min_names="trade_eligible", thin=thin, floor=floor)

These tests pin:

  1. the defaults are unchanged: `min_names=None` is the spec's value, and the
     default mask is still named "thin";
  2. on a session with floor <= n < min_names eligible names, the target equals
     an independently written copy of the sleeve's construction on those n
     names (demean, gross 1, the vol scalar on their own trailing 63-session
     return); with n >= min_names it equals the default target exactly; below
     the floor it repeats the previous row (build_targets' hold);
  3. the derivation's facts about the construction: with 2 names both weights
     are +-scal/2 whatever the z magnitudes; with 3 names one side is a single
     fund holding exactly half the gross (scal/2);
  4. the book is FLAT below the floor and trades between the floor and
     min_names, and equals an independently written loop;
  5. "trade_eligible" and "flatten" run the same loop given the same mask, so
     the only difference between the rules is the targets and the mask;
  6. every argument mismatch raises: no floor, a floor out of range or of the
     wrong type, the spec mask, a mask counted at another floor, a floor under
     "hold" or "flatten", T built at another floor than the mask, and
     min_names below 2;
  7. the gross ceiling binds under "trade_eligible", on sessions between the
     floor and min_names too (added after the review of 2026-11-03: test 4's
     cap of 1.8 never bound on its panel, whose held gross peaked at 1.04, so a
     ceiling skipped or doubled under this option passed every test).

Synthetic panels: the claim is about the code, not the market.

Checked to fail against the old behaviour (2026-11-03), each mutation applied
to band_frontier.py and the file restored after (the record is in the report,
section 2):
  * "trade_eligible" removed from BELOW_MIN_NAMES: tests 4, 5 and 6 fail;
  * build_targets ignoring `min_names` (comparing against MIN_NAMES): tests 2,
    3, 4, 5 and 6 fail;
  * the trade_eligible path banding a below-floor row instead of zeroing it:
    tests 4 and 5 fail;
  * thin_sessions ignoring `min_names`: tests 1, 4, 5 and 6 fail;
  * the mask-name check removed: test 6 fails;
  * `_min_names_arg` accepting 1: test 6 fails.
Added after the review (2026-11-03), whose mutation run found two survivors:
  * the ceiling skipped under "trade_eligible" (the review's N3): test 7 fails;
  * the ceiling doubled under "trade_eligible" (the review's N12): test 7 fails.
The seven tests of test_band_below_min_names.py pass under every one of these
mutations (they pin "hold" and "flatten", which none of them touches).
"""
import inspect

import numpy as np
import pandas as pd
import pytest

from scripts.cef import band_frontier as bf
from scripts.cef.spec import MAX_GROSS_STRESS, MIN_NAMES, VOL_TARGET

FLOOR = 3          # a floor below the derived 4, so the fake panel exercises n = 3, 4 and 5


def _fake_panel(monkeypatch, cols, seed=11, p_elig=0.5, ret_sd=0.01):
    """z with NaN holes and ADVs straddling the floor, tuned so that the eligible
    count visits every value from 1 to about 9 (10 names, about half eligible).
    `ret_sd` is the daily return sd: at the default the vol scalar keeps the
    target's gross near 1; test 7 lowers it so the scalar reaches its 2.5 clip."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2004-11-01", periods=320)
    z = pd.DataFrame(rng.normal(0, 1.2, (len(idx), len(cols))), index=idx, columns=cols).clip(-4, 4)
    z = z.mask(rng.random(z.shape) < 0.15)
    f = bf.MIN_ADV
    a = p_elig / 0.85                    # P(ADV >= floor), given z is present 85% of the time
    adv = pd.DataFrame(rng.choice([2 * f, f, 0.5 * f, np.nan], size=z.shape,
                                  p=[a - 0.05, 0.05, 1 - a - 0.05, 0.05]),     # exactly-at-floor passes
                       index=idx, columns=cols)
    # the first 80 sessions are fully eligible, so every book opens on the same prefix
    z.iloc[:80] = rng.normal(0, 1.2, (80, len(cols)))
    adv.iloc[:80] = 2 * f
    ret = pd.DataFrame(rng.normal(0, ret_sd, z.shape), index=idx, columns=cols)
    monkeypatch.setattr(bf, "build_panel",
                        lambda end=None, universe=None, source=None, mask=None: dict(ret=ret, z=z, adv=adv))
    ok = z.notna() & (adv >= f)
    return z, adv, ret, ok


def _sleeve_row(zrow, rets_upto_i):
    """The sleeve's construction (cef_discount.py l.911-920), written again in numpy:
    w = (mean(z) - z) / sum|z - mean(z)|, scaled by clip(VOL_TARGET / rv, 0.2, 2.5) where
    rv is the annualised sd of the last 63 rows of the eligible names' returns times w."""
    zz = zrow.to_numpy(dtype=float)
    d = zz.mean() - zz
    w = d / np.abs(d).sum()
    R = rets_upto_i[list(zrow.index)].to_numpy(dtype=float)
    hist = np.nansum(R * w, axis=1)[-63:]
    rv = hist.std(ddof=1) * np.sqrt(252)
    scal = float(np.clip(VOL_TARGET / rv, 0.2, 2.5)) if rv > 0 else 1.0
    return pd.Series(w * scal, index=zrow.index)


def _independent_book(T, b, cap, below, defer=False):
    """Zero on a below-floor row; otherwise band to the edge, ceiling, optional deferred flip."""
    prev = pd.Series(0.0, index=T.columns)
    out = []
    for d in T.index:
        if below.loc[d]:
            now = prev * 0.0
        else:
            tgt = T.loc[d]
            now = prev.copy()
            mv = (tgt - prev).abs() > b
            now[mv] = tgt[mv] - np.sign((tgt - prev)[mv]) * b
            g = now.abs().sum()
            if np.isfinite(cap) and g > cap:
                now = now * (cap / g)
            if defer:
                now[(prev * now) < 0] = 0.0
        out.append(now.values)
        prev = now
    return pd.DataFrame(out, index=T.index, columns=T.columns)


def test_1_defaults_are_unchanged(monkeypatch):
    for fn in (bf.build_targets, bf.thin_sessions):
        assert inspect.signature(fn).parameters["min_names"].default is None
    assert inspect.signature(bf.band_gross_capped).parameters["floor"].default is None
    assert bf.BELOW_MIN_NAMES[0] == "hold"
    cols = [f"N{i}" for i in range(10)]
    _fake_panel(monkeypatch, cols)
    T, R = bf.build_targets(universe=cols)
    T6, R6 = bf.build_targets(universe=cols, min_names=int(MIN_NAMES))
    pd.testing.assert_frame_equal(T, T6)
    pd.testing.assert_frame_equal(R, R6)
    th = bf.thin_sessions(T.index, universe=cols)
    assert th.name == "thin"
    th3 = bf.thin_sessions(T.index, universe=cols, min_names=FLOOR)
    assert th3.name == f"thin_below_{FLOOR}"
    # fewer sessions are below 3 than below min_names, and every one of them is below min_names too
    assert th3.sum() < th.sum() and not (th3 & ~th).any()


def test_2_reduced_set_targets_are_the_sleeve_construction(monkeypatch):
    cols = [f"N{i}" for i in range(10)]
    z, adv, ret, ok = _fake_panel(monkeypatch, cols)
    T, _ = bf.build_targets(universe=cols)
    T3, _ = bf.build_targets(universe=cols, min_names=FLOOR)
    cnt = ok.reindex(T.index).sum(axis=1)
    seen = {"reduced": 0, "full": 0, "below": 0}
    for i, d in enumerate(T.index):
        n = int(cnt.loc[d])
        if n >= MIN_NAMES:
            np.testing.assert_array_equal(T3.loc[d].values, T.loc[d].values)
            seen["full"] += 1
        elif n >= FLOOR:
            names = [c for c in cols if ok.loc[d, c]]
            ref = _sleeve_row(z.loc[d, names], ret.loc[:d]).reindex(cols).fillna(0.0)
            np.testing.assert_allclose(T3.loc[d].values, ref.values, rtol=0, atol=1e-12)
            assert abs(T3.loc[d].sum()) < 1e-12              # dollar-neutral on the smaller set
            seen["reduced"] += 1
        elif i > 0:
            np.testing.assert_array_equal(T3.loc[d].values, T3.iloc[i - 1].values)
            seen["below"] += 1
    assert min(seen.values()) >= 5, f"vacuous panel: {seen}"


def test_3_the_derivation_facts(monkeypatch):
    """Two names carry only a sign; three force a one-fund side holding half the gross."""
    cols = [f"N{i}" for i in range(10)]
    z, adv, ret, ok = _fake_panel(monkeypatch, cols, seed=12, p_elig=0.3)
    T2, _ = bf.build_targets(universe=cols, min_names=2)
    cnt = ok.reindex(T2.index).sum(axis=1)
    n2 = n3 = 0
    for d in T2.index:
        w = T2.loc[d][ok.loc[d]]
        g = w.abs().sum()
        if cnt.loc[d] == 2 and g > 0:
            np.testing.assert_allclose(w.abs().values, [g / 2, g / 2], rtol=0, atol=1e-12)
            n2 += 1
        if cnt.loc[d] == 3 and g > 0:
            pos, neg = (w > 0).sum(), (w < 0).sum()
            single = w[w > 0] if pos == 1 else w[w < 0]
            assert min(pos, neg) == 1
            np.testing.assert_allclose(abs(float(single.iloc[0])), g / 2, rtol=0, atol=1e-12)
            n3 += 1
    assert n2 >= 5 and n3 >= 5, f"vacuous panel: {n2} two-name rows, {n3} three-name rows"


@pytest.mark.parametrize("cap", [1.8, np.inf])
@pytest.mark.parametrize("defer", [False, True])
def test_4_trade_eligible_flat_below_the_floor_trading_above(monkeypatch, cap, defer):
    cols = [f"N{i}" for i in range(10)]
    _, _, _, ok = _fake_panel(monkeypatch, cols)
    T3, _ = bf.build_targets(universe=cols, min_names=FLOOR)
    below = bf.thin_sessions(T3.index, universe=cols, min_names=FLOOR)
    thin = bf.thin_sessions(T3.index, universe=cols)
    between = thin & ~below
    assert below.any() and between.any(), "vacuous panel"
    H = bf.band_gross_capped(T3, 0.048, cap, defer_flips=defer, below_min_names="trade_eligible",
                             thin=below, floor=FLOOR)
    np.testing.assert_allclose(H.values, _independent_book(T3, 0.048, cap, below, defer).values,
                               rtol=0, atol=1e-15)
    assert (H[below.values] == 0.0).all().all()
    assert (H[between.values].abs().sum(axis=1) > 0).mean() > 0.9     # it trades where flatten is flat
    T, _ = bf.build_targets(universe=cols)
    F = bf.band_gross_capped(T, 0.048, cap, defer_flips=defer, below_min_names="flatten", thin=thin)
    assert (F[between.values] == 0.0).all().all()
    first = int(np.argmax(thin.to_numpy()))
    pd.testing.assert_frame_equal(H.iloc[:first], F.iloc[:first])   # the same book until the first thin session


def test_5_trade_eligible_and_flatten_run_one_loop(monkeypatch):
    cols = [f"N{i}" for i in range(10)]
    _fake_panel(monkeypatch, cols)
    T3, _ = bf.build_targets(universe=cols, min_names=FLOOR)
    below = bf.thin_sessions(T3.index, universe=cols, min_names=FLOOR)
    for defer in (False, True):
        a = bf.band_gross_capped(T3, 0.048, 1.8, defer_flips=defer, below_min_names="trade_eligible",
                                 thin=below, floor=FLOOR)
        b = bf.band_gross_capped(T3, 0.048, 1.8, defer_flips=defer, below_min_names="flatten",
                                 thin=below.rename("thin"))
        pd.testing.assert_frame_equal(a, b)


def test_6_mismatches_raise(monkeypatch):
    cols = [f"N{i}" for i in range(10)]
    _fake_panel(monkeypatch, cols)
    T, _ = bf.build_targets(universe=cols)
    T3, _ = bf.build_targets(universe=cols, min_names=FLOOR)
    th = bf.thin_sessions(T.index, universe=cols)
    b3 = bf.thin_sessions(T3.index, universe=cols, min_names=FLOOR)
    b4 = bf.thin_sessions(T3.index, universe=cols, min_names=FLOOR + 1)
    run = lambda TT, **kw: bf.band_gross_capped(TT, 0.048, 1.8, **kw)          # noqa: E731
    run(T3, below_min_names="trade_eligible", thin=b3, floor=FLOOR)               # consistent: no raise
    with pytest.raises(ValueError, match="needs floor"):
        run(T3, below_min_names="trade_eligible", thin=b3)
    with pytest.raises(ValueError, match="needs thin"):
        run(T3, below_min_names="trade_eligible", floor=FLOOR)
    for bad in (1, int(MIN_NAMES), int(MIN_NAMES) + 1):
        with pytest.raises(ValueError, match="2 <= floor"):
            run(T3, below_min_names="trade_eligible", thin=b3.rename(f"thin_below_{bad}"), floor=bad)
    for bad in (True, 3.0, "3"):
        with pytest.raises(TypeError, match="floor must be an int"):
            run(T3, below_min_names="trade_eligible", thin=b3, floor=bad)
    with pytest.raises(ValueError, match="not counted at floor"):
        run(T3, below_min_names="trade_eligible", thin=th, floor=FLOOR)          # the spec mask
    with pytest.raises(ValueError, match="not counted at floor"):
        run(T3, below_min_names="trade_eligible", thin=b4, floor=FLOOR)          # another floor's mask
    with pytest.raises(ValueError, match="only read with below_min_names='trade_eligible'"):
        run(T3, floor=FLOOR)
    with pytest.raises(ValueError, match="only read with below_min_names='trade_eligible'"):
        run(T, below_min_names="flatten", thin=th, floor=FLOOR)
    # T built at the spec's min_names with the floor's mask: T held where the mask says active
    with pytest.raises(ValueError, match="repeats a nonzero row"):
        run(T, below_min_names="trade_eligible", thin=b3, floor=FLOOR)
    # T built at the floor with another floor's mask renamed to pass the name check
    with pytest.raises(ValueError, match="on which T moved"):
        run(T3, below_min_names="trade_eligible", thin=b4.rename(f"thin_below_{FLOOR}"), floor=FLOOR)
    with pytest.raises(ValueError, match="at least 2"):
        bf.build_targets(universe=cols, min_names=1)
    with pytest.raises(ValueError, match="at least 2"):
        bf.thin_sessions(T.index, universe=cols, min_names=1)
    for bad in (True, 3.0):
        with pytest.raises(TypeError, match="min_names must be an int"):
            bf.build_targets(universe=cols, min_names=bad)


@pytest.mark.parametrize("defer", [False, True])
def test_7_the_ceiling_binds_under_trade_eligible(monkeypatch, defer):
    """The gross ceiling after the band (band_frontier.band_gross_capped, the
    `_cap_gross` call; the sleeve's l.1113-1116) under "trade_eligible", at the
    spec's own max_gross_stress. The returns are quiet (daily sd 0.002), so the
    vol scalar reaches its 2.5 clip and the target's gross passes the ceiling,
    on sessions with floor <= n < min_names eligible names as well as on full
    ones. The book must equal the independent loop (which applies the ceiling),
    never exceed the ceiling, and sit exactly at it on reduced-set sessions."""
    cols = [f"N{i}" for i in range(10)]
    _fake_panel(monkeypatch, cols, ret_sd=0.002)
    cap = float(MAX_GROSS_STRESS)
    T3, _ = bf.build_targets(universe=cols, min_names=FLOOR)
    below = bf.thin_sessions(T3.index, universe=cols, min_names=FLOOR)
    between = (bf.thin_sessions(T3.index, universe=cols) & ~below).to_numpy()
    tg = T3.abs().sum(axis=1).to_numpy()
    assert (tg[between] > cap).sum() >= 5, "vacuous panel: the reduced-set target never passes the ceiling"
    H = bf.band_gross_capped(T3, 0.048, cap, defer_flips=defer, below_min_names="trade_eligible",
                             thin=below, floor=FLOOR)
    np.testing.assert_allclose(H.values, _independent_book(T3, 0.048, cap, below, defer).values,
                               rtol=0, atol=1e-15)
    g = H.abs().sum(axis=1).to_numpy()
    assert (g <= cap + 1e-12).all()
    at_cap = np.abs(g - cap) < 1e-12
    assert at_cap[between].sum() >= 5, f"the ceiling bound on only {at_cap[between].sum()} reduced-set sessions"
