"""Part 2 of PLAN.md (at git tag pre-clean-slate: _archive/docs/PLAN.md) — the trading policy frontier.

Asks one question: at a given amount of trading, which policy keeps more of the
gross edge, a fixed rebalance calendar or a no-trade band?

Both policies run on an IDENTICAL signal (the live sleeve's z-score, ADV filter
and vol scalar) and identical execution (decide at t, MOC fill at t+1, so the
weights set at t earn the t+2 return). The only difference is when they trade.

  calendar(k)  ignore the signal for k days, then implement all of it
  band(b)      hold a position until it is more than b from target, then trade
               back only to the band EDGE -- the optimal form under proportional
               costs (Constantinides 1986, Davis & Norman 1990)

Costs are charged as bp per unit of turnover, swept rather than assumed, because
the realised figure is not yet known. `net` columns are therefore a sensitivity
surface, not a forecast.

IMPORTANT: this table characterises the POLICY CLASS. Do not read the argmax of a
column as the band width to deploy -- deriving a parameter from the cube-root law
and checking it lands on the plateau is legitimate; picking the top of a swept
column is how z_window=63 was selected, and it failed out of sample.

Usage:  python scripts/cef/band_frontier.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]

# Parameters the LIVE BOOK owns come from the frozen spec, never from a literal
# here. Until 2026-09-10 these were module constants that happened to agree with
# the spec; "happened to agree" stops being true at the next spec bump, and a
# baseline measured against a policy nobody deployed is worse than no baseline.
# See scripts/cef/spec.py for the full argument.
import sys                                                          # noqa: E402
sys.path.insert(0, str(REPO))
from scripts.cef.spec import (  # noqa: E402
    BAND_WIDTH, LIVE_POLICY, MIN_ADV_USD, MIN_NAMES,
    REBALANCE_DAYS, UNIVERSE, VOL_TARGET, Z_WINDOW, summary,
)
# The accounting (the execution lag, P&L, turnover) lives in the research
# harness so every family shares it (team lead, 2026-10-27). See evaluate().
from scripts.research.harness import (  # noqa: E402
    HOLDOUT_START, evaluate as _harness_evaluate,
)

MIN_ADV = MIN_ADV_USD

# Where the harness reads its panels (added 2026-10-14 for trial C5). The
# default is the repo's live `data/cef/`, and every production caller leaves it
# alone. A trial that must not move when the live panels are refreshed (the team
# lead's ruling of 2026-10-14 on C5: "your fit must use the frozen copy, so no
# later refresh can move it") points it, inside a context manager, at a frozen
# copy of the same files with the same schema. build_panel, distribution_yield
# and split_factor all read through it, so one switch moves every input at once
# and no reader is left on the live panel. The no-op with the default was proved
# by hashing build_targets() in a fresh process (first call 007e221b...7cdc,
# second c8291c1e...e599) and total_returns(R) before and after the edit.
DATA_DIR = REPO / "data" / "cef"
# Not spec-owned: estimation choices local to this harness.
MIN_PERIODS, VOL_LOOKBACK = 120, 63
SAMPLE_START = "2005-01-03"
COSTS_BP = [5, 10, 15, 20, 30]

# The width sweep is a DELIBERATE variation -- characterising the policy class is
# the entire point of this script, and H8 permits it explicitly. The live width
# is unioned in so the sweep always contains the deployed policy, whatever it is.
BAND_SWEEP = sorted({0.002, 0.004, 0.008, 0.016, 0.024, 0.032,
                     0.048, 0.064, 0.096, 0.128, BAND_WIDTH})




def build_panel(end=None, universe=None, source=None, mask=None):
    """The signal panel `build_targets` is built from: px, nav, ret, disc, z, adv.

    `end` truncates the RAW price and NAV history before anything is computed,
    so a caller can ask "what did this panel look like on date X" and get an
    answer that exercises the pivot, the return filter and the ADV window --
    not merely the rolling mean. `scripts/cef/tests/test_pnl_series.py` uses it
    to test no-lookahead end to end. `end=None` is the production path and is
    byte-identical to the version before this argument existed.

    WHY THIS IS SPLIT OUT (2026-09-11, W14 Part A)
    ----------------------------------------------
    `z` never left this function, so anything that needed the SIGNAL rather than
    the POSITIONS -- a conditional IC, a per-group split, a diagnostic on the
    clip -- had to re-derive the z-score from the panel. Two copies of a
    signal definition is the same class of defect as two copies of the
    execution convention: they agree until one of them is edited.

    `build_targets` now calls this and is otherwise UNCHANGED. The no-op was
    proved by hashing `pickle.dumps((T, R))` before and after the split:
    sha256 2ee89432...4ed5 both times (see
    scripts/cef/tests/test_pnl_series.py::test_build_panel_is_a_noop, which
    re-derives the targets from the panel and compares them element-wise).

    ALIGNMENT (H7): `mu`, `sd` and `adv` are all `.shift(1)` -- the z-score on
    date t is standardised against a window ending at t-1, and eligibility uses
    ADV through t-1. `disc` itself is date-t information (t's close against t's
    published NAV), which is why the execution convention is shift(2) and not
    shift(1): t's NAV is published AFTER t's close.

    `source` AND `mask` (added 2026-10-14, trial C4's data gate DG-C4-2)
    ---------------------------------------------------------------------
    C4 (`results/cef/PREREG_C4_FAMILIES_2026-10-13.md`) runs THIS signal, with
    every parameter from the frozen spec, on the CEF families panels. A second
    copy of the z-score for those funds would be the defect W14 Part A split
    this function out to prevent, so the harness takes the panel instead:

    * `source`: None (the live panels, unchanged) or a pair of paths
      (prices, NAV) in the live schema (`date open high low close volume
      ticker grp` / `date nav ticker`). `data/cef_families/` is built in that
      schema on purpose (`scripts/data/fetch_cef_families_yf.py`).
    * `mask`: None (unchanged) or a date x ticker boolean frame; True means the
      fund has NO DISCOUNT that day. The masked discount is NaN, so the day is
      not eligible (its z is NaN) and does not count toward the z-window
      history (`rolling(...).mean()` counts non-NaN rows only, and
      `MIN_PERIODS` is a count of them). Price, return, volume and ADV are NOT
      masked: a masked day still trades and still earns (PREREG_C4 §4.3). A
      cell absent from the frame is unmasked; a mask naming a ticker or date
      the panel does not hold raises, because a mask that silently misses its
      target is no mask.

    Both defaults reproduce the panel before the arguments existed byte for
    byte: sha256 of `pickle.dumps(build_targets())` 007e221b...7cdc before and
    after, on the live panels of 2026-10-14 (`results/cef/C4_RESULT_*.md`).
    """
    pp, npth = ((DATA_DIR / "cef_prices.parquet", DATA_DIR / "cef_nav.parquet") if source is None
                else (Path(source[0]), Path(source[1])))
    P = pd.read_parquet(pp)
    N = pd.read_parquet(npth)
    # `universe` (added 2026-09-28): a caller may score a candidate universe
    # before it is in the spec -- the Alpaca v7 derivation drops four names that
    # Alpaca will not let us short. None means the spec's universe, and the
    # production path is byte-identical to before the argument existed
    # (sha256 of pickle.dumps(build_targets()) 6fdd49b4...c09f both sides).
    U = UNIVERSE if universe is None else list(universe)
    P, N = P[P.ticker.isin(U)], N[N.ticker.isin(U)]
    d = P.merge(N, on=["date", "ticker"], how="inner")
    d["date"] = pd.to_datetime(d["date"])
    if end is not None:
        d = d[d["date"] <= pd.Timestamp(end)]
    d = d[(d.nav > 0.5) & (d.close > 0.5)]
    piv = lambda c: d.pivot_table(index="date", columns="ticker", values=c).sort_index()
    px, nav, vol = piv("close"), piv("nav"), piv("volume")

    ret = px.pct_change(fill_method=None).where(lambda x: x.abs() < 0.5)
    disc = 100.0 * (px - nav) / nav
    if mask is not None:
        if mask.isna().any().any():              # astype(bool) would turn NaN into True: a silent mask
            raise ValueError("mask holds NaN cells; a mask must say True or False for every cell it names")
        m = mask.astype(bool)
        extra_t = sorted(set(m.columns) - set(disc.columns))
        extra_d = m.index.difference(disc.index)
        if end is not None:                      # rows after `end` were truncated, not missed
            extra_d = extra_d[extra_d <= pd.Timestamp(end)]
        if extra_t or len(extra_d):
            raise ValueError(f"mask names {len(extra_t)} ticker(s) {extra_t[:5]} and {len(extra_d)} date(s) "
                             "the panel does not hold; a mask that misses its target is no mask")
        disc = disc.mask(m.reindex(index=disc.index, columns=disc.columns, fill_value=False))
    mu = disc.rolling(Z_WINDOW, min_periods=MIN_PERIODS).mean().shift(1)
    sd = disc.rolling(Z_WINDOW, min_periods=MIN_PERIODS).std().shift(1)
    z = ((disc - mu) / sd.replace(0, np.nan)).clip(-4, 4)
    adv = (px * vol).rolling(63, min_periods=21).mean().shift(1)
    return dict(px=px, nav=nav, vol=vol, ret=ret, disc=disc, mu=mu, sd=sd, z=z, adv=adv)


def _min_names_arg(min_names):
    """`min_names` as `build_targets` and `thin_sessions` read it (added 2026-11-03
    for `below_min_names="trade_eligible"`). None, the default, is the spec's
    `min_names`, read from the module's `MIN_NAMES` at call time, so the
    production path is unchanged. Otherwise an int of at least 2.

    WHY 2, AND NOT 1. The weights are w = -(z - zbar) / sum|z - zbar| over the
    eligible names. With one name z - zbar is exactly 0, so w is 0/0 = NaN, and
    `build_targets` would fill it with 0 on a session it calls active: a silent
    degenerate book, which this refuses. Two names are defined, but carry only
    the sign of z1 - z2 (w = +-1/2 whatever the z magnitudes); three force one
    side to a single fund holding half the gross. Those are the reasons the
    third-rule report derives its floor at 4
    (`results/backtests/thin-third-rule-2026-11-03/REPORT.md` section 1); this
    check refuses only the case that is undefined."""
    if min_names is None:
        return int(MIN_NAMES)
    if isinstance(min_names, bool) or not isinstance(min_names, (int, np.integer)):
        raise TypeError(f"min_names must be an int (or None for the spec's), got {min_names!r}")
    if int(min_names) < 2:
        raise ValueError(f"min_names must be at least 2, got {min_names}: with one eligible name "
                         "z - mean(z) is 0 and the weights are 0/0")
    return int(min_names)


def build_targets(universe=None, source=None, mask=None, min_adv=None, min_names=None):
    """Frictionless daily target weights, exactly as the sleeve would build them.

    `universe=None` is the spec's universe; `source` and `mask` are passed to
    `build_panel` (see there; added 2026-10-14 for C4's DG-C4-2).

    `min_adv` (added 2026-10-14 for trial C5, PREREG_C5_OPEN_AUCTION_2026-10-13
    DG-C5-4; the same flag C4's DG-C4-5 asks for): the ADV floor in USD. None
    (the default) is the spec's `min_adv_usd`, read from the module's `MIN_ADV`
    at call time, so the production path is unchanged (and
    `scripts/cef/c5_feasibility.py::adv_floor`, which patches `MIN_ADV`, still
    works). 0 is the WIDE set: the identical rule with the floor off, so a name
    needs a z-score and a defined ADV. A NaN ADV still fails at a floor of 0,
    because `nan or 0` is `nan` (NaN is truthy) and `nan >= 0` is False;
    `scripts/cef/tests/test_c5_harness.py` pins that. The no-op was proved by
    hashing `pickle.dumps(build_targets())` before and after the edit, on the
    panel as of 2026-10-14 (cef_prices to 2026-09-28, cef_nav to 2026-09-25):
    the FIRST call in a process hashes 007e221b...7cdc and the SECOND
    c8291c1e...e599, identically on both sides of the edit. (The bytes differ
    between first and second call although the frames are value-identical: a
    pickle memo quirk, present before this edit. Compare like with like.)

    `min_names` (added 2026-11-03 for `results/backtests/thin-third-rule-2026-11-03/`,
    a zero-trial report): the smallest eligible count on which a target is
    built; below it the previous target is held, as before. None (the default)
    is the spec's `min_names`, so the production path is unchanged: sha256 of
    the default T and R before and after the edit in that folder's
    noop_before.txt / noop_after.txt. A smaller value builds the target on the
    SMALLER eligible set with the unchanged construction (demean, normalise,
    the vol scalar on that set's own trailing 63-session return), which is
    what the live sleeve would do on that set: its construction (l.911-920)
    does not depend on how many names there are. The third-rule report runs the
    live sleeve on every such session to confirm it (`sleeve_reduced_check.py`).
    Pair it with `thin_sessions(..., min_names=)` at the same value and
    `band_gross_capped(below_min_names="trade_eligible", floor=)`."""
    U = UNIVERSE if universe is None else list(universe)
    floor = MIN_ADV if min_adv is None else float(min_adv)
    n_min = _min_names_arg(min_names)
    p = build_panel(universe=U, source=source, mask=mask)
    ret, z, adv = p["ret"], p["z"], p["adv"]

    tgt = pd.DataFrame(0.0, index=z.index, columns=U)
    start = z.index.searchsorted(pd.Timestamp(SAMPLE_START))
    for i in range(start, len(z.index)):
        row = _eligible(z.iloc[i], adv.iloc[i], floor)
        if len(row) < n_min:
            tgt.iloc[i] = tgt.iloc[i - 1]          # hold; nothing eligible
            continue
        tgt.iloc[i] = _target_row(row, ret, i).reindex(U).fillna(0.0).values
    T = tgt.iloc[start:]
    return T, ret.reindex(T.index)[U].fillna(0.0)


def _target_row(row, ret, i):
    """The target on one decision date from its eligible z-scores `row`: the
    sleeve's construction (`cef_discount.py::target_positions` l.911-920),
    w = -(z - mean z) / sum|z - mean z|, times the vol scalar
    clip(VOL_TARGET / rv, 0.2, 2.5), rv the annualised sd of the last
    VOL_LOOKBACK rows of these names' returns times w, through row i.

    Moved out of `build_targets`' loop VERBATIM on 2026-11-03 (the third-rule
    report), so that a caller asking "what would the book be on this smaller
    set" uses this one definition rather than a second copy of the signal.
    sha256 of the default T and R before and after: that report's
    noop_before.txt / noop_after.txt. ALIGNMENT (H7): `row` is date i of
    `build_panel` (z standardised on a window ending i-1; ADV through i-1) and
    `ret` through row i is known at i's close, which is when the sleeve
    decides. NaN weights (every z equal: 0/0) are returned as NaN; the caller
    decides what that means (`build_targets` fills 0)."""
    w = -(row - row.mean())
    w = w / w.abs().sum()
    hist = ret[list(row.index)].iloc[:i + 1].mul(w, axis=1).sum(axis=1).tail(VOL_LOOKBACK)
    rv = hist.std() * np.sqrt(252)
    scal = float(np.clip(VOL_TARGET / rv, 0.2, 2.5)) if rv > 0 else 1.0
    return w * scal


def _eligible(z_row, adv_row, floor):
    """The names eligible on one decision date: a z-score, and an ADV at or
    above `floor`. ONE definition, shared by `build_targets` and
    `thin_sessions` (added 2026-11-03), so the session the target holds on and
    the session the policy flattens on can never be two different sets.

    The expression is `build_targets`'s loop body before 2026-11-03, moved here
    verbatim. A NaN ADV fails at any floor: `nan or 0` is `nan` (NaN is truthy)
    and `nan >= floor` is False, which `scripts/cef/tests/test_c5_harness.py`
    pins. ALIGNMENT (H7): both rows are date-t rows of `build_panel`, whose z is
    standardised on a window ending t-1 and whose ADV ends t-1.

    WHY THIS IS THE LIVE SLEEVE'S TEST ON HISTORY, NOT A SUBSET OF IT. The
    sleeve (`src/deploy/sleeves/cef_discount.py::target_positions`) also drops
    a name with no NAV or a NAV older than `max_nav_age_bd` (l.829-834), but its
    `nav` is the pivot of the SAME inner join of prices and NAV (`_read_panel`),
    so a name with a finite z on t has a paired row on t and a NAV age of 0: that
    test cannot bind behind a finite z. The runner's stale-NAV and missing-NAV
    holds (`extras["nav_hold"]`, l.837) exist only at run time and have no
    history. `results/backtests/thin-days-2026-11-03/sleeve_thin_check.py` ran
    the sleeve itself on every decision date and compares its count."""
    row = z_row.dropna()
    return row[[t for t in row.index if (adv_row.get(t, 0) or 0) >= floor]]


def thin_sessions(index, universe=None, source=None, mask=None, min_adv=None, min_names=None):
    """Bool Series on `index`: True on a decision date with fewer than the
    spec's `min_names` eligible names (`_eligible`, the rule `build_targets`
    holds on). Added 2026-11-03 for `band_gross_capped(below_min_names=
    "flatten")`, the live sleeve's rule; the arguments are `build_targets`'s and
    must be the same ones the targets were built with.

    Every date of `index` must be a date of the panel: a date the panel does
    not hold has no eligibility to count, and treating it as thin or as active
    would be a guess, so it raises. Dates before `SAMPLE_START` are counted like
    any other (`build_targets` starts there; this does not need to).

    `min_names` (added 2026-11-03, the third-rule report): None, the default,
    counts against the spec's `min_names` and returns the Series named "thin",
    unchanged (noop_before.txt / noop_after.txt in that folder). An int counts
    against that floor instead and names the Series "thin_below_<n>", so that
    `band_gross_capped(below_min_names="trade_eligible", floor=n)` can refuse a
    mask counted at another floor."""
    U = UNIVERSE if universe is None else list(universe)
    floor = MIN_ADV if min_adv is None else float(min_adv)
    n_min = _min_names_arg(min_names)
    p = build_panel(universe=U, source=source, mask=mask)
    z, adv = p["z"], p["adv"]
    idx = pd.DatetimeIndex(index)
    missing = idx.difference(z.index)
    if len(missing):
        raise ValueError(f"thin_sessions: {len(missing)} date(s) the panel does not hold, "
                         f"first {missing[0].date()}")
    pos = z.index.get_indexer(idx)
    n = [len(_eligible(z.iloc[i], adv.iloc[i], floor)) for i in pos]
    name = "thin" if min_names is None else _below_name(n_min)
    return pd.Series(np.asarray(n) < n_min, index=idx, name=name)


def _below_name(n):
    """The name `thin_sessions(..., min_names=n)` gives its mask."""
    return f"thin_below_{int(n)}"


def calendar(T, k):
    """Refresh every k days, hold in between."""
    H = T.copy()
    keep = np.zeros(len(T), bool)
    keep[::k] = True
    H[~keep] = np.nan
    return H.ffill().fillna(0.0)


def band(T, b):
    """Hold unless a name is more than b from target; then trade to the EDGE."""
    A, cur = T.values, np.zeros(T.shape[1])
    H = np.zeros_like(A)
    for i in range(len(A)):
        gap = A[i] - cur
        mv = np.abs(gap) > b
        cur = cur.copy()
        cur[mv] = A[i][mv] - np.sign(gap[mv]) * b
        H[i] = cur
    return pd.DataFrame(H, index=T.index, columns=T.columns)


def _unshortable_mask(unshortable, T):
    """The `unshortable` argument of `band_gross_capped` as a bool array on T's
    grid, validated. Raises rather than aligning silently: a flag frame on a
    different calendar, naming a ticker T does not hold, or holding a NaN would
    otherwise become "lendable" on the cells it missed, which is no flag at all."""
    if not isinstance(unshortable, pd.DataFrame):
        raise TypeError("unshortable must be a date x ticker DataFrame of bools")
    if not unshortable.index.equals(T.index):
        raise ValueError("unshortable must be on T's own index, row for row")
    extra = sorted(set(unshortable.columns) - set(T.columns))
    if extra:
        raise ValueError(f"unshortable names {extra}, which T does not hold")
    if unshortable.isna().any().any():
        raise ValueError("unshortable holds NaN; every cell must say True or False")
    if not all(dt == bool for dt in unshortable.dtypes):
        raise TypeError("unshortable must be bool, not a number that might be a weight")
    # A column T holds and the frame omits is lendable on every day: that is the
    # declared meaning of "absent" (only the named names are ever blocked).
    return unshortable.reindex(columns=T.columns, fill_value=False).to_numpy(dtype=bool)


BELOW_MIN_NAMES = ("hold", "flatten", "trade_eligible")       # the first is the harness default


def _thin_mask(thin, T):
    """`band_gross_capped`'s `thin` argument as a bool array on T's grid,
    validated like `_unshortable_mask`: a mask on another calendar, a NaN, or a
    number where a bool belongs raises, because a mask that silently misses a
    session would hold that session where the live sleeve closes the book."""
    if not isinstance(thin, pd.Series):
        raise TypeError("thin must be a bool Series on T's index (thin_sessions(T.index))")
    if not thin.index.equals(T.index):
        raise ValueError("thin must be on T's own index, row for row")
    if thin.isna().any():
        raise ValueError("thin holds NaN; every session must say True or False")
    if thin.dtype != bool:
        raise TypeError(f"thin must be bool, got {thin.dtype}")
    return thin.to_numpy(dtype=bool)


def _check_thin_matches_T(flat, T):
    """Refuse a `thin` mask that was not built with T's own arguments (added
    2026-11-03, review of the thin-days report, defect 3).

    WHY. `_thin_mask` checks the calendar, NaNs and dtype, but cannot see the
    universe, source, mask or ADV floor a mask was counted with. The review
    built the WIDE targets (`build_targets(min_adv=0)`, which hold on NO
    session) and passed `thin_sessions(T.index)` at the spec floor: it was
    accepted and flattened 3,621 sessions on which the WIDE book was trading.
    The reverse mistake is as quiet: a mask counted on a larger universe than T
    (a leave-one-name-out run that forgets `universe=`) flags fewer sessions,
    so flatten silently returns the hold book on the rest.

    THE CHECK uses `build_targets`' own signature: on a session with fewer than
    `min_names` eligible names it copies the previous row ("hold; nothing
    eligible"), and on every other session it recomputes the row from that
    day's z-scores and vol scalar. So, from the second row on:
      * a row flagged thin must repeat the previous row exactly;
      * a NONZERO row that repeats the previous row exactly must be flagged
        thin. Zero rows are exempt: a book that has never opened repeats zero,
        and on 2020-03-18 and 2025-04-07 every eligible z sat at the -4 clip,
        the weights were 0/0 and `build_targets` filled them with 0 on an
        active session.
    On the panel of 2026-10-15 both hold on all 5,480 rows of the spec targets
    and of the WIDE targets (no active nonzero row repeats its predecessor), and
    the review's mismatch fails the first test on 3,621 rows. A hand-made T
    must satisfy the same contract: hold the row on a thin session, move it
    otherwise."""
    A = np.asarray(T.values)
    same = np.zeros(len(A), dtype=bool)
    if len(A) > 1:
        same[1:] = (A[1:] == A[:-1]).all(axis=1)
    nonzero = np.abs(A).sum(axis=1) > 0
    moved_on_thin = flat & ~same
    moved_on_thin[0] = False
    held_not_thin = same & nonzero & ~flat
    if moved_on_thin.any():
        bad = T.index[moved_on_thin]
        raise ValueError(f"thin flags {len(bad)} session(s) on which T moved, first {bad[0].date()}: "
                         "the mask was not counted with T's own arguments (universe, source, mask, "
                         "min_adv); build it with thin_sessions(T.index, <the same arguments>)")
    if held_not_thin.any():
        bad = T.index[held_not_thin]
        raise ValueError(f"T repeats a nonzero row on {len(bad)} session(s) that thin calls active, "
                         f"first {bad[0].date()}: build_targets held there, so the mask was counted "
                         "with other arguments than T")


def band_gross_capped(T, b, cap, unshortable=None, defer_flips=False,
                      below_min_names="hold", thin=None, floor=None):
    """`band()` with the frozen `max_gross_stress` ceiling applied to the HELD
    book after the band, exactly where the sleeve applies it (added 2026-09-28).

    The sleeve bands against what it actually HOLDS, and the ceiling scales that
    held book by one uniform `f = cap / gross` whenever gross exceeds `cap`
    (`src/deploy/sleeves/cef_discount.py::_cap_gross`, which this calls, so the
    operator has one definition). The scaled book is then tomorrow's `cur`, so a
    binding ceiling feeds back into the next day's band -- which is why this is
    not `band(T, b)` followed by a row-wise rescale.

    `cap = inf` reproduces `band(T, b)` exactly (tested in
    scripts/cef/tests/test_band_gross_capped.py).

    `unshortable` (added 2026-10-19 for `results/ops/IBKR_WORTH_IT_2026-10-19.md`,
    a zero-trial diagnostic): None, the default, is the code path above,
    unchanged (sha256 of the held book on the fit-cut panels identical before
    and after the edit, deployed and WIDE, with and without the cap; the test
    file pins `None` against the old loop). Otherwise a bool frame on T's index:
    True at (t, i) means the broker will not lend i at the decision of t. The
    live runner then SKIPS an order that would open or enlarge a short in i and
    lets a reduction or a close through ("skip that name, send the rest", team
    lead 2026-09-28; gate 7 in `docs/RUNNER.md`). An existing short is kept,
    because the broker does not close a short on a flag and a position never
    migrates (`results/ops/IBKR_SECOND_BROKER_2026-10-19.md` §2.2). So on a
    blocked day the held weight is floored at min(yesterday's held weight, 0):
    a long can be sold to flat but not through it (a flip is deferred live
    anyway), a short can shrink but not grow. The floor is applied after the
    band and before the ceiling, and the ceiling only ever scales a book down,
    so it cannot open a short either. Nothing here re-neutralises the book: a
    blocked short leaves it net long by that weight, which is what the runner
    does today (R13 of the IBKR note) and the beta the comparison must show.

    `defer_flips` (added 2026-11-02 for
    `results/backtests/turnover-live-2026-11-02/`, a zero-trial report): False,
    the default, is the code path above, unchanged: sha256 of the held book's
    values+index+columns on the panel of 2026-10-14, before and after the edit,
    173f767e...2432 with the v7 ceiling and 2c205883...70cc with cap=inf (equal
    to band(T, BAND_WIDTH)). True models the live runner's
    deferred flip, `quantt/session/decide.py` with `FLIP_SAME_SESSION =
    False`: when the book decided today would hold a name on the OTHER side of
    zero from what it held yesterday (long -> short or short -> long), only the
    closing leg is sent, so the name is held FLAT for this session; the next
    session sees flat and the band opens from there (to the same edge, A - b
    toward zero, if the target is still outside the band; not at all if it is
    not). It is applied LAST, after the band, the unshortable floor and the
    ceiling, because decide.py runs on the sleeve's output (band, then
    `_cap_gross`), and it does not rescale the other names: decide.py sends
    them as the sleeve sized them, so a deferred flip leaves the book's gross
    below the ceiling for that session. decide.py tests the flip in SHARES
    (`cur != 0 and tgt != 0` with opposite signs); in weight space that is
    `prev * cur < 0`. A target that truncates to zero shares is a close, not a
    flip, and ends flat either way, so the two agree on what is held.

    `below_min_names` and `thin` (added 2026-11-03 for
    `results/backtests/thin-days-2026-11-03/`, a zero-trial report): what the
    book does on a decision date with fewer than `min_names` eligible names.

      "hold" (the default) is the code path above, unchanged: `build_targets`
          has already carried the previous TARGET onto such a date ("hold;
          nothing eligible"), and the band and the ceiling act on it as on any
          other day. `thin` must be None. sha256 of the held book (values,
          index, columns) on the panel of 2026-10-15, before and after the
          edit, with the v7 ceiling, cap=inf and defer_flips:
          `results/backtests/thin-days-2026-11-03/noop_before.txt` and
          `noop_after.txt`.
      "flatten" is the LIVE rule, read from the code on 2026-11-03. The frozen
          spec carries no `below_min_names` key, which the registry reads as
          "flatten" (`src/deploy/registry.py::cef_below_min_names`). With fewer
          than `min_names` eligible and no stale-NAV holds, the sleeve returns
          every name FLAT before the band and the ceiling run
          (`src/deploy/sleeves/cef_discount.py` l.841, l.892-895). decide.py
          sizes FLAT as 0 shares (`target_shares`, l.243-244), a close is not a
          flip (l.332: `tgt != 0`) and never needs a borrow check (l.262-264),
          and v7's `min_trade_usd` is $0, so every whole share is closed: the
          book goes STRAIGHT TO ZERO, not to within the band of zero. The next
          session the sleeve bands against what the account holds, which is
          flat, so the band reopens from zero to the EDGE (l.1070-1091); the
          runner sets `opening_session` only when the account has never had a
          fill (`quantt/session/run.py::is_opening_session`), so re-entry after
          a thin day is NOT a full-target build. Here: on a row where `thin`
          is True the held book is zero and nothing else runs (a zero book has
          nothing to floor, scale or defer); on every other row the loop is
          the one above, from that zero. `thin` is required, a bool Series on
          T's index, normally `thin_sessions(T.index)` with the arguments T
          was built with. T's values on a thin row are not used, but they are
          CHECKED (`_check_thin_matches_T`, added 2026-11-03 after review):
          a mask built with other arguments than T raises.
      "trade_eligible" (added 2026-11-03 for
          `results/backtests/thin-third-rule-2026-11-03/`, a zero-trial report;
          NOT the live rule): on a session with fewer than `min_names` but at
          least `floor` eligible names, the book TRADES THE ELIGIBLE NAMES: the
          sleeve's own construction on the smaller set, then the band and the
          ceiling as on any other day. Below `floor` it does what the live
          sleeve does, FLAT (the "flatten" path above). The floor is derived in
          that report's section 1 from what the construction does at each count:
          one name is 0/0, two carry only the sign of z1 - z2, three force one
          side to a single fund holding half the gross, four is the first count
          with none of those. It is an argument, never a default, because it is
          not a spec key. Callers pass
              T     = build_targets(min_names=floor, <the same arguments>)
              thin  = thin_sessions(T.index, min_names=floor, <the same arguments>)
          so T already carries the reduced-set target on the sessions between
          `floor` and `min_names`, and `thin` flags only the sessions below
          `floor`. Three checks refuse a mismatch: `floor` must be an int with
          2 <= floor < the spec's `min_names` (at `min_names` it IS "flatten");
          `thin` must be named "thin_below_<floor>", the name thin_sessions
          gives a mask counted at that floor (the spec mask is named "thin");
          and `_check_thin_matches_T` must pass, so T was built at the mask's
          floor. `floor` is refused under "hold" and "flatten".
    """
    from src.deploy.sleeves.cef_discount import _cap_gross
    if below_min_names not in BELOW_MIN_NAMES:
        raise ValueError(f"below_min_names must be one of {BELOW_MIN_NAMES}, got {below_min_names!r}")
    if below_min_names != "trade_eligible" and floor is not None:
        raise ValueError(f"floor is only read with below_min_names='trade_eligible', not {below_min_names!r}")
    if below_min_names == "hold":
        if thin is not None:
            raise ValueError("thin is only read with below_min_names='flatten' or 'trade_eligible'; under "
                             "'hold' build_targets has already held the target on a thin session")
        flat = None
    else:
        if thin is None:
            raise ValueError(f"below_min_names={below_min_names!r} needs thin (thin_sessions(T.index)); "
                             "the harness will not guess which sessions were thin")
        if below_min_names == "trade_eligible":
            if floor is None:
                raise ValueError("below_min_names='trade_eligible' needs floor, the smallest eligible count "
                                 "it trades; it is not a spec key, so there is no default")
            if isinstance(floor, bool) or not isinstance(floor, (int, np.integer)):
                raise TypeError(f"floor must be an int, got {floor!r}")
            if not 2 <= int(floor) < int(MIN_NAMES):
                raise ValueError(f"floor must satisfy 2 <= floor < min_names ({MIN_NAMES}), got {floor}: "
                                 "one name is 0/0, and at min_names the rule is 'flatten'")
            if thin.name != _below_name(floor):
                raise ValueError(f"thin is named {thin.name!r}, not {_below_name(floor)!r}: it was not "
                                 f"counted at floor {floor}; build it with "
                                 f"thin_sessions(T.index, min_names={floor}, <T's arguments>)")
        flat = _thin_mask(thin, T)
        _check_thin_matches_T(flat, T)
    A, cur = T.values, np.zeros(T.shape[1])
    H = np.zeros_like(A)
    cols = T.columns
    blocked = None if unshortable is None else _unshortable_mask(unshortable, T)
    for i in range(len(A)):
        if flat is not None and flat[i]:
            # the live sleeve: every name FLAT, straight to zero (see above);
            # under "trade_eligible" only below `floor`, the rows thin flags
            cur = np.zeros(T.shape[1])
            H[i] = cur
            continue
        gap = A[i] - cur
        mv = np.abs(gap) > b
        prev = cur
        cur = cur.copy()
        cur[mv] = A[i][mv] - np.sign(gap[mv]) * b
        if blocked is not None:
            k = blocked[i]
            cur[k] = np.maximum(cur[k], np.minimum(prev[k], 0.0))
        if np.isfinite(cap):
            w, _ = _cap_gross(pd.Series(cur, index=cols), cap)
            cur = w.values
        if defer_flips:
            # decide.py: a long<->short flip sends only the closing leg today
            cur = cur.copy()
            cur[(prev * cur) < 0] = 0.0
        H[i] = cur
    return pd.DataFrame(H, index=T.index, columns=T.columns)


def evaluate(H, R):
    """H.loc[t] = weights decided at t. MOC fills at t+1 -> earns the t+2 return.

    Returns the summary statistics AND the daily P&L series that produced them
    (`pnl`), added 2026-09-11 for W14 Part A.

    WHY `pnl` IS RETURNED
    ---------------------
    Every number this function reports is a moment of one series, and until now
    that series was discarded at the return statement. Anything that asks a
    question about the SHAPE of the P&L rather than its first two moments -- a
    factor regression, a drawdown census, a conditional-state split -- therefore
    had to rebuild `(H.shift(2) * R).sum(axis=1)` for itself, and a second copy
    of the execution convention is exactly the defect `EXEC_LAG = 2` exists to
    prevent (see scripts/cef/tests/test_execution_convention.py, and the
    shift(1) incident of 2026-09-10 that cost gross 1.27 -> 0.94).

    This is an ADDITIVE extension: the existing keys and their values are
    untouched, and `pnl` is the identical object the statistics are computed
    from, not a recomputation. scripts/cef/tests/test_pnl_series.py holds that
    shut.

    `R` is whatever return matrix the caller supplies. The default from
    `build_targets()` is PRICE returns; `total_returns()` in this module adds
    the distribution leg. The choice belongs to the caller and is stated in
    every table, because the two conventions differ by era (RESEARCH_STATE.md,
    2026-09-09: -0.01%/yr full sample but -0.77%/yr in 2010-14).

    DELEGATES TO `scripts/research/harness.py` (2026-10-27). The team lead ruled
    that evaluate() may be restructured so that every research family and the
    ML pipeline share one accounting path. The body moved there unchanged, and
    the lag now has one name, `harness.EXEC_LAG`. This entry point passes
    `nan_policy="legacy"`, the old NaN semantics verbatim, because E1 relies on
    the skip for its `hold_gaps`-checked CRSP gaps (see harness.evaluate). New
    code calls `scripts.research.harness.evaluate` / `report`, which refuse a
    NaN weight or a missing held return. On the live book the output is
    byte-identical (sha256 of every key, before and after:
    `results/research/HARNESS_RESTRUCTURE_2026-10-27.md`).
    """
    return _harness_evaluate(H, R, nan_policy="legacy")


# =============================================================================
# THE OPENING-AUCTION FILL, ON THE SAME HOLDINGS PATH (added 2026-10-14, trial C5)
# =============================================================================
# results/cef/PREREG_C5_OPEN_AUCTION_2026-10-13.md §5 (DG-C5-3). C5 asks whether
# the trade decided in the evening of s-1 (on s-1's NAV) is worth filling at the
# OPENING auction of s instead of the closing auction of s. It changes WHEN a
# trade fills, never WHAT is held, so it is not a new backtester: it is the
# deployed book `evaluate(H, R)` plus one extra leg on the same H,
#
#     pnl_C5[s] = evaluate(H, R)["pnl"][s] + G[s]
#     G[s]      = sum_i (H[s-1,i] - H[s-2,i]) * (C[s,i] / O[s,i] - 1)
#
# i.e. the day's trade, times the session (open -> close of s) that the earlier
# fill holds it over and the MOC fill does not. `evaluate()` above is NOT
# edited; these two helpers sit beside it so there is still one definition of
# the execution convention.
#
# WHY THIS IS NOT shift(1) (the 2026-09-10 incident). shift(1) earned
# C[s-1] -> C[s] on H[s-1]: a fill at the close of the decision day, before its
# NAV existed. The extra leg here starts at O[s], after s-1's NAV was published
# the evening before, and the overnight C[s-1] -> O[s] stays with the book
# decided a day earlier (H[s-2]), exactly as in evaluate(). No decision ever
# earns an overnight gap that began before it was made.
# scripts/cef/tests/test_c5_harness.py pins the alignment, and each test there
# is shown to fail against the wrong versions (the trade at shift(2), at
# shift(0), and the overnight return in place of the session return).
SESSION_RETURN_LIMIT = 0.5      # the harness's own price filter (build_panel: |ret| < 0.5)


def session_returns(O, C):
    """The session return C[s,i] / O[s,i] - 1, and the mask of name-days that
    have none.

    ALIGNMENT (H7): row s reads row s of `O` and row s of `C` and nothing else,
    so a later open or an earlier close cannot move it (test (iii)).

    `O` is the opening-auction fill price and `C` the close the deployed harness
    fills at, both date x ticker frames on one index and one column set. Where
    either is missing the name-day has no session to earn: its trade is filled
    at that day's close, the same as the deployed book, so its return is 0.0
    and it is flagged in `no_cross` (PREREG_C5 §4.2: a no-cross name-day is
    counted and listed, never dropped). The CALLER classifies why (no `O`
    print, a declared defect class it set to NaN, or no close, class D-5) and
    counts each class on trade name-days; this function only refuses to invent
    a return.

    NO SILENT FILTER: a non-positive price, or a session return of 50% or more
    in magnitude (the harness's own price filter, which `build_panel` applies by
    dropping the day), RAISES here instead. PREREG_C5 §4.5 makes either a Stage 0
    halt, not a row to drop.

    Returns (RS, no_cross): RS a float frame with no NaN, no_cross a bool frame.
    """
    if not (O.index.equals(C.index) and O.columns.equals(C.columns)):
        raise ValueError("session_returns: O and C must share one index and one column set")
    if not O.index.is_monotonic_increasing:
        raise ValueError("session_returns: index must be sorted")
    bad = (O <= 0) | (C <= 0)
    if bad.any().any():
        where = [(str(O.index[i].date()), O.columns[j]) for i, j in zip(*np.where(bad.values))][:10]
        raise ValueError(f"session_returns: non-positive price at {where}")
    rs = C / O - 1.0
    big = rs.abs() >= SESSION_RETURN_LIMIT
    if big.any().any():
        where = [(str(rs.index[i].date()), rs.columns[j], float(rs.iat[i, j]))
                 for i, j in zip(*np.where(big.values))][:10]
        raise ValueError(f"session_returns: |C/O - 1| >= {SESSION_RETURN_LIMIT} at {where}; "
                         "a Stage 0 defect (PREREG_C5 §4.5), never filtered here")
    no_cross = rs.isna()
    return rs.fillna(0.0), no_cross


def open_fill_gain(H, RS, by_name=False):
    """G[s] = sum_i (H[s-1,i] - H[s-2,i]) * RS[s,i]: what filling the trade
    decided at s-1 in the OPENING auction of s adds to `evaluate(H, R)["pnl"]`.

    ALIGNMENT (H1/H7): the trade decided in the evening of s-1 is
    H[s-1] - H[s-2]; it fills at O[s] instead of C[s] and so also earns
    RS[s] = C[s]/O[s] - 1. This is `(H.diff().shift(1) * RS).sum(axis=1)`, the
    pre-registration's own expression. Rows 0 and 1 carry no trade (H.diff() is
    NaN on row 0, as in `evaluate()`'s `turn`), so the first build from H's very
    first row is not booked here, exactly as `evaluate()` books no turnover
    for it; every window the C5 trial reads starts later, and the trial script
    asserts that.

    `RS` must come from `session_returns` (no NaN; 0 on no-cross name-days),
    on H's index and columns. A stratum or a placebo is the same call with RS
    masked to 0 outside it, or with a lagged H -- never a second formula.

    by_name=True returns the name-day frame (H[s-1] - H[s-2]) * RS[s] instead
    of its row sum; with RS = 1 everywhere that frame is the trade matrix itself
    (row s: the trade that fills at the open of s), which is how the
    shuffled-trade placebo obtains it without a second copy of the lag.
    """
    if not (H.index.equals(RS.index) and H.columns.equals(RS.columns)):
        raise ValueError("open_fill_gain: H and RS must share one index and one column set")
    if not H.index.is_monotonic_increasing:
        raise ValueError("open_fill_gain: index must be sorted")
    if RS.isna().any().any():
        raise ValueError("open_fill_gain: RS has NaN; build it with session_returns, "
                         "which sets a no-cross name-day to 0 and flags it")
    contrib = H.diff().shift(1) * RS                  # row s: (H[s-1] - H[s-2]) * RS[s]
    assert contrib.iloc[:2].isna().all().all(), "the trade lag moved: rows 0-1 must hold no trade"
    contrib = contrib.fillna(0.0)
    return contrib if by_name else contrib.sum(axis=1)


def load_families_actions(path):
    """A yfinance actions file (`date ticker dividends stock_splits`, the schema
    `scripts/data/fetch_cef_families_yf.py` writes) as the two frames the live
    files hold: distributions (`ex_date ticker amount`) and splits (`ex_date
    ticker stock_split`).

    Added 2026-10-14 (C4's DG-C4-2: "`total_returns` takes the families'
    actions file"). yfinance codes "no split" as 0.0 and "no dividend" as 0.0,
    so a row is a distribution where `dividends` > 0 and a split where
    `stock_splits` != 0; a negative dividend or a negative split factor is not
    a convention, it is a defect, and raises."""
    a = pd.read_parquet(path)
    need = {"date", "ticker", "dividends", "stock_splits"}
    if not need <= set(a.columns):
        raise ValueError(f"{path}: expected columns {sorted(need)}, got {sorted(a.columns)}")
    if (a["dividends"] < 0).any() or (a["stock_splits"] < 0).any():
        raise ValueError(f"{path}: a negative dividend or split factor; refusing to book it")
    a = a.assign(ex_date=pd.to_datetime(a["date"]))
    dist = a.loc[a["dividends"] > 0, ["ex_date", "ticker", "dividends"]].rename(columns={"dividends": "amount"})
    sp = a.loc[a["stock_splits"] != 0, ["ex_date", "ticker", "stock_splits"]].rename(
        columns={"stock_splits": "stock_split"})
    return dist.reset_index(drop=True), sp.reset_index(drop=True)


def distribution_yield(index, columns, dist=None, prices=None):
    """D_it / P_i,t-1 on each ex-date -- the cash leg the price panel omits.

    `dist` (a frame `ex_date ticker amount`) and `prices` (a path to a price
    panel in the live schema) were added 2026-10-14 for C4 (DG-C4-2). None
    for both is the live distribution and price panels, unchanged.

    WHY THIS IS NOT OPTIONAL FOR A FACTOR REGRESSION
    ------------------------------------------------
    The price panel is RAW (unadjusted), which is CORRECT for the discount --
    NAV is unadjusted too and the two must share a convention -- but it is
    wrong for the RETURN: `px.pct_change()` books the ex-date price drop and
    never books the cash, so the long is never credited its distribution and
    the short is never debited its payment in lieu.

    On the band's holdings path the mean bias nets to -0.01%/yr over 2005-2026
    (RESEARCH_STATE.md, measured 2026-09-09 over 3,962 ex-dates) because the
    book is not systematically long or short yield. Its standard deviation is
    1.23%/yr and it swings by era. For a Sharpe that hardly matters; for a
    LOADING on any factor correlated with the distribution calendar it matters
    a great deal, which is why W14 Part A insists on the total-return series.

    ALIGNMENT (H7): the yield is booked on the ex-date `t` itself, divided by
    the close of `t-1`, which is the last price that contains the distribution.
    Nothing here reads a date later than `t`.

    NO SILENT FALLBACK: raises if the distribution panel cannot cover a name
    that the caller asked for, rather than returning zeros -- a zero here is
    indistinguishable from "this fund paid nothing", and the two have opposite
    meanings for the bias above.
    """
    dist = (pd.read_parquet(DATA_DIR / "cef_distributions.parquet") if dist is None
            else dist.copy())
    dist["ex_date"] = pd.to_datetime(dist["ex_date"])
    missing = sorted(set(columns) - set(dist["ticker"].unique()))
    if missing:
        raise ValueError(
            "the distribution panel has no rows for "
            f"{missing} -- cannot build a total-return series for the "
            "universe requested. Fix the panel; do not fall back to price "
            "returns silently (house rule: no silent fallbacks).")
    dist = dist[dist.ticker.isin(columns)]

    P = pd.read_parquet(DATA_DIR / "cef_prices.parquet" if prices is None else Path(prices))
    P = P[P.ticker.isin(columns)]
    P["date"] = pd.to_datetime(P["date"])
    px = P.pivot_table(index="date", columns="ticker", values="close").sort_index()
    prev = px.shift(1)                       # close of t-1, cum-distribution

    amt = (dist.groupby(["ex_date", "ticker"])["amount"].sum()
               .unstack().reindex(index=index, columns=list(columns)))
    y = amt / prev.reindex(index=index, columns=list(columns))

    # THE TWO SILENT PATHS, MADE LOUD. `.fillna(0.0)` below is correct for the
    # common case -- a date with no ex-date for a name IS a genuine zero cash
    # flow -- but it is indistinguishable from two real failures:
    #   (a) an ex-date that falls on a date absent from `index`, which
    #       `.reindex` drops with no trace;
    #   (b) an ex-date with no prior close, which divides to NaN and becomes a
    #       zero yield.
    # Landmine 4 (HYT lags the price panel by a day) is exactly shape (b). So
    # count what went in against what came out and raise on any gap, rather
    # than asserting the paths are unreachable.
    window = dist[(dist.ex_date >= index[0]) & (dist.ex_date <= index[-1])]
    expected = int(window.groupby(["ex_date", "ticker"]).ngroups)
    booked = int((y.notna() & (y != 0)).sum().sum())
    if booked != expected:
        raise ValueError(
            f"{expected - booked} of {expected} ex-dates in "
            f"{index[0].date()}..{index[-1].date()} did not reach the yield "
            "matrix — either the ex-date is not a session in this index, or "
            "the prior close is missing (landmine 4: HYT lags the price panel "
            "by a day). A zero here is indistinguishable from 'this fund paid "
            "nothing' and means the opposite, so this raises rather than "
            "filling.")
    return y.fillna(0.0)


def split_factor(index, columns, splits=None):
    """Share-count multiplier on each ex-split date; 1.0 everywhere else.

    `splits` (a frame `ex_date ticker stock_split`, added 2026-10-14 for C4's
    DG-C4-2): None reads the live `cef_splits.parquet`, unchanged.

    WHY THIS SITS BESIDE THE DISTRIBUTION LEG AND NOT SOMEWHERE ELSE
    ---------------------------------------------------------------
    `RESEARCH_STATE.md`'s 2026-09-09 amendment on the raw price panel makes TWO
    points, and only the first was ever acted on. The second: "the +-50% single
    day return filter in `build_targets` silently drops any day where an
    unadjusted split would appear as a jump, and `data/cef/cef_splits.parquet`
    (one row: BIT 2025-08-19) is not applied in the harness at all."

    A 2.9% split is nowhere near the +-50% filter, so nothing is dropped and
    nothing looks wrong -- the harness simply books the split as a loss. On
    2025-08-19 BIT's raw close went 14.47 -> 13.84, a -4.354% "return", of
    which -2.818% (= 1/1.029 - 1) is the split and only -1.578% is price. The
    band held w_BIT = +0.0335 that day, so the phantom half is about -9.4bp of
    a -18.0bp session -- inside the 2023-26 holdout.

    RAW PRICES STAY RAW FOR THE DISCOUNT. NAV is unadjusted too and drops by
    the same factor, so price/NAV is unaffected and `build_panel` is untouched.
    It is only the RETURN that needs this, which is why it lives here with the
    other return-convention correction rather than in the panel.

    NO SILENT FALLBACK: raises if a split and a distribution ever land on the
    same name-date, because the per-share amount is then ambiguous (pre- or
    post-split) and this function cannot tell which. That has never happened in
    this panel; if it does, someone must decide rather than inherit a guess.
    """
    if splits is None:
        path = DATA_DIR / "cef_splits.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing. The harness cannot build a split-correct "
                "return series without it, and booking a split as a return is a "
                "silent loss -- see this function's docstring.")
        sp = pd.read_parquet(path)
    else:
        sp = splits.copy()
    sp["ex_date"] = pd.to_datetime(sp["ex_date"])
    sp = sp[sp.ticker.isin(columns)]
    k = (sp.groupby(["ex_date", "ticker"])["stock_split"].prod()
           .unstack().reindex(index=index, columns=list(columns)))
    return k.fillna(1.0)


def total_returns(R, actions=None, prices=None, split_rulings=None):
    """Price returns corrected for splits, plus the distribution leg.

    Kept separate from `build_targets()` on purpose. Every baseline in this
    repo was measured on the raw price-return convention; silently switching
    what `build_targets` hands back would move nine scripts' numbers at once
    with nothing erroring. The caller opts in, and says which convention it
    used.

    r_total = (1 + r_px) * k - 1 + D/P_{t-1}, where k is the share-count
    multiplier. The two corrections never coincide on a name-date in this
    panel, and `split_factor` raises if they ever do.

    `actions` and `prices` (added 2026-10-14, C4's DG-C4-2): None for both is
    the live distribution, split and price panels, unchanged. Otherwise
    `actions` is a yfinance actions file (`load_families_actions`) and
    `prices` the price panel whose closes are the yield's denominator; both
    must be given together, because a yield on one panel's distributions over
    another panel's prices is a silent mismatch. The formula is the same.

    THE SPLIT-BASIS GUARD (added 2026-10-20; `scripts/cef/data_guards.py`,
    guard 3). k is right only on a RAW close, which steps by 1/k on the
    ex-date. A vendor that has already split-adjusted the history leaves no step
    there, and k then books a phantom return of k - 1. C4's fit booked BTO, TYG,
    NXG and EMO at -75% to -80% that way, and nothing raised. Before k is
    applied, `guard_split_basis` checks every cell it multiplies, and RAISES
    naming (ticker, ex-date, factor) where the raw step is an ordinary day
    and k would create a split-sized one. `split_rulings` (default None: no
    override) is a recorded rulings file that treats named cells (`drop_split`,
    or `book_as_is` to reproduce a committed computation). Where nothing is hit,
    k is passed through untouched and the result is the old formula's, bit for
    bit (hashes: results/cef/DATA_GUARDS_2026-10-19.md §7).
    """
    from scripts.cef.data_guards import guard_split_basis
    if (actions is None) != (prices is None):
        raise ValueError("total_returns: give `actions` and `prices` together, or neither")
    if actions is None:
        y = distribution_yield(R.index, R.columns).reindex_like(R)
        k = split_factor(R.index, R.columns).reindex_like(R)
    else:
        dist, sp = load_families_actions(actions)
        y = distribution_yield(R.index, R.columns, dist=dist, prices=prices).reindex_like(R)
        k = split_factor(R.index, R.columns, splits=sp).reindex_like(R)
    k = guard_split_basis(R, k, rulings=split_rulings, series="close", context="total_returns")
    clash = ((k != 1.0) & (y != 0.0))
    if clash.any().any():
        where = [(str(d.date()), c) for d, c in zip(*np.where(clash.values))]
        raise ValueError(
            f"a split and a distribution fall on the same name-date ({where}). "
            "The per-share distribution amount is then ambiguous -- pre- or "
            "post-split -- and this function will not guess.")
    return (1.0 + R) * k - 1.0 + y


# =============================================================================
# BORROW, CHARGED ON THE BOOK evaluate() HOLDS (added 2026-10-12, plan item 0.5)
# =============================================================================
# Both brokers this book could trade at accrue a short's fee per CALENDAR day on
# a 360-day year, on a collateral value of 102% of the prior close: IBKR's Borrow
# Fee Details guide and Alpaca's brokerage fee schedule (revised 2026-10-01),
# docs/REFERENCES.md §4 and §12l [V]. These are the two published conventions,
# not estimation choices; scripts/cef/tests/test_borrow_charge.py pins them as
# literals, so editing either constant fails a test.
#
# BOTH SOURCES ALSO SAY "rounded up to the nearest dollar", and neither says
# clearly whether that is per share or per position [U] (Alpaca's wording, "a
# per-share collateral value ... adjusted by 102% and rounded up", reads per
# share; IBKR's guide does not say). The default here is the flat 102%, i.e.
# no round-up. Per position the round-up is at most $1 and negligible; per
# share it is large on $4-15 funds (PHK at $4.13: ceil(4.21) = $5, +21%).
# `collateral_px` turns the per-share reading on as a labelled sensitivity.
BORROW_DAY_COUNT = 360
BORROW_COLLATERAL_MARKUP = 1.02


def borrow_charge(H, fee_pct, *, markup=BORROW_COLLATERAL_MARKUP,
                  day_count=BORROW_DAY_COUNT, collateral_px=None):
    """The daily stock-borrow charge on the SHORT book `evaluate(H, R)` holds.

    WHY THIS LIVES HERE AND NOT IN A CALLER
    ---------------------------------------
    H4 says borrow is charged separately and labelled, and that it scales with
    HOLDINGS, not turnover. The held book is `H.shift(2)` -- that is the
    execution convention itself (decide t, fill at close t+1, earn t+2). A
    borrow charge computed on `H` or `H.shift(1)` in some caller is a second
    copy of the convention that disagrees with the first, which is the shift(1)
    incident of 2026-09-10 in a new place. So the charge is defined once, next
    to `evaluate()`, on the same lag. `evaluate()` itself is untouched: every
    stored baseline is gross of borrow, and stays so.

    ALIGNMENT (H1/H7)
    -----------------
    Row t of `evaluate()["pnl"]` is sum_i H[t-2, i] * R[t, i]: the book decided
    at t-2, filled at the close of t-1 and held to the close of t. The short
    held over that interval is max(-H[t-2, i], 0). It is charged the fee in
    force at session t-1 (when the overnight holding starts) for every calendar
    day from session t-1 to session t -- a Friday-to-Monday row is 3 days,
    exactly as both brokers charge Friday, Saturday and Sunday. A fee is a cost
    of holding, not a decision input, so reading the t-1 fee is not lookahead;
    nothing here informs a position.

    `fee_pct` is an annualised fee in PERCENT (IBKR's FEERATE convention), a
    frame indexed by date with one column per name. A constant schedule is a
    frame with the same value on every row.

    `collateral_px` (default None: the flat `markup`, unchanged behaviour) is a
    frame of raw closes. When given, each name-day's collateral multiplier is
    ceil(markup * P[t-1]) / P[t-1]: the per-share "rounded up to the nearest
    dollar" reading, a SENSITIVITY (see the comment above the constants). A
    held short with no prior close is a gap, reported in `uncovered`.

    NO SILENT FALLBACK
    ------------------
    A name-day on which a short is held and `fee_pct` is NaN is NOT charged
    zero quietly: its short weight is returned in `uncovered`, and the caller
    must report coverage beside any figure built from `cost`. `cost` is the
    charge on the measured name-days only, so with gaps it is a LOWER bound.
    A name in `H` that `fee_pct` has no column for raises: that is a missing
    source, not a gap.

    Returns dict:
      cost           Series, row t: the charge as a fraction of capital (>= 0)
      short          Series, row t: sum of short weights held over (t-1, t]
      uncovered      Series, row t: short weight held on name-days with no fee
      covered_share  float: 1 - sum(uncovered)/sum(short) (1.0 if never short)
    """
    missing = sorted(set(H.columns) - set(fee_pct.columns))
    if missing:
        raise ValueError(
            f"fee_pct has no column for {missing}. A name the book can short with "
            "no fee source is a missing input, not a zero fee; supply it or say "
            "the figure excludes it.")
    held = (-H.shift(2).fillna(0.0)).clip(lower=0.0)        # short held over (t-1, t]
    fee = fee_pct.reindex(index=H.index, columns=H.columns).shift(1)   # fee at t-1 -> row t
    sessions = pd.Series(H.index, index=H.index)
    days = sessions.diff().dt.days                             # calendar days t-1 -> t
    has_short = held > 0
    gap = has_short & fee.isna()
    # Gaps are excluded from `cost` and reported in `uncovered`; a row with no
    # short at all is a genuine zero charge, not a gap.
    if collateral_px is None:
        mult = markup                                          # the flat 102%
    else:
        prev = collateral_px.reindex(index=H.index, columns=H.columns).shift(1)  # close t-1
        gap = gap | (has_short & prev.isna())
        # 1e-9 guards an exact multiple against a float overshoot (1.02 * 50 must give
        # $51, not $52); a search of cent prices $1-$1,000 found none, it is a guard
        mult = np.ceil(markup * prev - 1e-9) / prev
    rate = (fee / 100.0).where(has_short & ~gap, 0.0)
    if collateral_px is not None:
        rate = (rate * mult).where(has_short & ~gap, 0.0)
        mult = 1.0
    cost = (held * rate).sum(axis=1) * mult * days / day_count
    # Row 0 has no previous session, so `days` is NaN there; it also holds
    # nothing, because the held book is H.shift(2). Assert rather than fill.
    if len(cost):
        if held.iloc[0].sum() != 0.0:
            raise AssertionError("row 0 holds a short: the shift(2) alignment moved")
        cost.iloc[0] = 0.0
    short = held.sum(axis=1)
    uncovered = held.where(gap, 0.0).sum(axis=1)
    tot = float(short.sum())
    return dict(cost=cost, short=short, uncovered=uncovered,
                covered_share=1.0 - float(uncovered.sum()) / tot if tot > 0 else 1.0)


def row(label, H, R):
    r = evaluate(H, R)
    nets = [(r["ann_ret"] - r["turn"] * c / 1e4) / r["vol"] for c in COSTS_BP]
    print(f"{label:<22}{r['gross_sr']:8.2f}{r['ann_ret'] * 100:7.2f}"
          f"{r['vol'] * 100:7.2f}{r['turn']:9.1f}{r['hold']:9.1f}"
          + "".join(f"{n:11.2f}" for n in nets))
    return r, nets


# --- labels -----------------------------------------------------------------
# Which row is LIVE is read from the frozen spec, never asserted here. Three
# scripts in this directory labelled "calendar 2d (LIVE)" for four days after
# the band replaced it on 2026-09-06, and PLAN.md carried the same claim in five
# tables. A label that can go stale silently is the same bug as a hardcoded
# baseline, one layer up.
LIVE_TAG = "  <-- LIVE"


def _cal_is_live(k: int) -> bool:
    from scripts.cef.spec import BAND_IS_LIVE
    return (not BAND_IS_LIVE) and k == REBALANCE_DAYS


def _band_is_live(b: float) -> bool:
    from scripts.cef.spec import BAND_IS_LIVE
    return BAND_IS_LIVE and abs(b - BAND_WIDTH) < 1e-12


def _lab_cal(k: int) -> str:
    return f"calendar {k}d" + (LIVE_TAG if _cal_is_live(k) else "")


def _lab_band(b: float) -> str:
    return f"band {b * 100:.1f}%" + (LIVE_TAG if _band_is_live(b) else "")


def main():
    T, R = build_targets()
    print(summary())
    print(f"sample {T.index[0].date()} .. {T.index[-1].date()}  ({len(T)} days)\n")

    hdr = (f"{'policy':<22}{'grossSR':>8}{'ann%':>7}{'vol%':>7}{'turn/yr':>9}{'hold(d)':>9}"
           + "".join(f"{'net@' + str(c) + 'bp':>11}" for c in COSTS_BP))
    print(hdr, "-" * len(hdr), sep="\n")
    for k in (1, 2, 5, 10):
        row(f"calendar {k}d" + (LIVE_TAG if _cal_is_live(k) else ""), calendar(T, k), R)
    for b in BAND_SWEEP:
        row(f"band {b * 100:.1f}% of gross" + (LIVE_TAG if _band_is_live(b) else ""),
            band(T, b), R)

    print("\n\n=== matched on turnover: the only honest comparison ===")
    print("H2: pairs must match turn/yr within 5%. Note that pairing calendar 5d")
    print("with the LIVE band is a near-exact match, where the retired 6.4%")
    print("baseline this block used until 2026-09-10 was ~19% adrift -- i.e. that")
    print("row was violating the rule it exists to demonstrate.\n")
    print(f"{'policy':<22}{'turn/yr':>9}{'grossSR':>9}{'net@15bp':>10}")
    for lab, H in [("calendar 1d", calendar(T, 1)), ("band 0.2%", band(T, 0.002)),
                   (_lab_cal(2), calendar(T, 2)), (_lab_band(0.016), band(T, 0.016)),
                   ("calendar 5d", calendar(T, 5)), (_lab_band(BAND_WIDTH), band(T, BAND_WIDTH))]:
        r = evaluate(H, R)
        net = (r["ann_ret"] - r["turn"] * 15 / 1e4) / r["vol"]
        print(f"{lab:<22}{r['turn']:9.1f}{r['gross_sr']:9.2f}{net:10.2f}")

    print("\n\n=== turnover stability, 2015+ (universe stable; pre-2010 is degenerate) ===")
    print("Recorded against an earlier draft of PLAN.md, which claimed the band")
    print("would be MORE turnover-stable. It is not. See PLAN.md 0.3 and 2.3.\n")
    eras = [("2015-2019", "2015", "2019"), ("2020-2022", "2020", "2022"),
            ("2023-2026", "2023", "2026")]
    print(f"{'policy':<22}" + "".join(f"{e[0]:>11}" for e in eras) + f"{'mean':>8}{'sd/mean':>9}")
    era_widths = sorted({0.016, 0.024, BAND_WIDTH})
    for lab, H in ([("calendar 1d", calendar(T, 1)), (_lab_cal(2), calendar(T, 2)),
                    ("calendar 5d", calendar(T, 5))]
                   + [(_lab_band(b), band(T, b)) for b in era_widths]):
        t = evaluate(H, R)["turn_series"]
        v = np.array([t.loc[a:b].mean() * 252 for _, a, b in eras])
        print(f"{lab:<22}" + "".join(f"{x:11.1f}" for x in v)
              + f"{v.mean():8.1f}{v.std() / v.mean():9.1%}")

    print("\n\n=== sensitivity to being wrong about cost — the robustness that matters ===")
    print(f"{'policy':<22}{'turn/yr':>9}{'net@5bp':>10}{'net@30bp':>10}{'span':>8}{'flips?':>9}")
    widths = sorted({0.024, 0.064, BAND_WIDTH})
    for lab, H in ([("calendar 1d", calendar(T, 1)), (_lab_cal(2), calendar(T, 2)),
                    ("calendar 5d", calendar(T, 5))]
                   + [(_lab_band(b), band(T, b)) for b in widths]):
        r = evaluate(H, R)
        lo = (r["ann_ret"] - r["turn"] * 5 / 1e4) / r["vol"]
        hi = (r["ann_ret"] - r["turn"] * 30 / 1e4) / r["vol"]
        print(f"{lab:<22}{r['turn']:9.1f}{lo:10.2f}{hi:10.2f}{lo - hi:8.2f}"
              f"{('YES' if hi < 0 else 'no'):>9}")


# =============================================================================
# SLOWER POLICIES ON THE FIT PERIOD ONLY (added 2026-10-07, report, no trial)
# =============================================================================
# WHY THIS BLOCK EXISTS
# ---------------------
# Published CEF discount half-lives are 7.7-12 MONTHS (monthly data, mostly
# equity CEFs). Our measured target-weight half-life is 14.3 DAYS
# (PREREG_BAND_2026-09-06.md). If the literature's number were the relevant one
# for our credit panel, a much slower policy -- a monthly calendar, or a band
# wider than the 12.8% top of BAND_SWEEP -- should keep more of the edge per
# unit of trading than the live 4.8% band. This block asks that question.
#
# WHY FIT PERIOD ONLY
# -------------------
# These are NEW candidate policies. The 2023-01-01 time holdout (H13) is sealed
# and is opened once, by a pre-registered trial. So T and R are truncated BEFORE
# any policy is applied: no 2023+ number for these candidates is ever computed,
# not merely never printed. `fit_only` asserts it. (Truncating first is exact,
# not an approximation: `calendar`, `band` and `build_targets` are all causal --
# the targets on date t use data through t only, see build_panel's H7 note.)
#
# WHY THE WIDE-BAND WIDTHS ARE A SWEEP
# ------------------------------------
# 16 / 19.2 / 25.6% continue BAND_SWEEP's grid past its top. This is a
# deliberate characterisation of the policy class (H8 permits it; it is the
# point of this script), and no width here is a candidate for the spec. Nothing
# in this block selects anything on P&L. The turnover-matched partners ARE
# chosen -- by bisection on TURNOVER alone, which is the H2 procedure, never on
# Sharpe.
#
# RETURN CONVENTION: both are printed, labelled. Price returns are what every
# row above and PREREG_BAND_2026-09-06 used; total returns (splits +
# distributions, `total_returns`) are the convention the paper book is scored
# on (PREREG_ALPACA_V7 section 4).
# HOLDOUT_START (2023-01-01, H13) is imported from scripts/research/harness.py.
SLOW_CALENDARS = (21,)                       # monthly, ~21 sessions
SLOW_BANDS = (0.16, 0.192, 0.256)            # deliberate sweep beyond 12.8%
CONTEXT_CALENDARS = (5, 10)
CONTEXT_BANDS = (0.096, 0.128)
FIT_ERAS = [("fit 2005-22", None, "2022-12-31"),
            ("2015-2019", "2015-01-01", "2019-12-31"),
            ("2020-2022", "2020-01-01", "2022-12-31")]
MATCH_TOL = 0.05                             # H2


def fit_only(T, R):
    """Truncate to strictly before the 2023-01-01 holdout, and assert it."""
    Tf, Rf = T.loc[T.index < HOLDOUT_START], R.loc[R.index < HOLDOUT_START]
    assert Tf.index.max() < HOLDOUT_START and Rf.index.max() < HOLDOUT_START, \
        "holdout leak: a fit-period frame reaches 2023-01-01 or later"
    assert Tf.index.equals(Rf.index)
    return Tf, Rf


def calendar_offset(T, k, offset):
    """`calendar(T, k)` with the refresh dates shifted by `offset` sessions.

    A monthly calendar's result depends on WHICH day of the cycle it refreshes;
    the spread across all k offsets is the honest error bar on one phase, and
    reporting only phase 0 would be picking one draw of 21. Before the first
    refresh the book is flat (0.0), exactly as `calendar` is before index 0."""
    if not 0 <= offset < k:
        raise ValueError(f"offset {offset} outside [0, {k})")
    H = T.copy()
    keep = np.zeros(len(T), bool)
    keep[offset::k] = True
    H[~keep] = np.nan
    return H.ffill().fillna(0.0)


# =============================================================================
# XASSET SLATE HELPERS (added 2026-10-14; PREREG_XASSET_SLATE_2026-10-12 §1.2 P4)
# =============================================================================
# WHY THEY LIVE HERE. The slate's pre-registration says any new helper that
# touches positions -- "a month-end refresh or a block shuffle" -- is added to
# this file visibly, with a test, because a second copy of how a target becomes
# a held book is the shift(1) incident in a new place. None of them changes
# `evaluate()`, and none reads a return: they shape H only. Tests:
# scripts/cef/tests/test_xasset_helpers.py.

def month_end_sessions(index):
    """E_m: the last session of each calendar month in `index` (the primary
    panel's own calendar, PREREG P4). The final month of `index` counts only if
    `index` reaches that month's last session -- the caller cannot know that, so
    it is the caller's job not to treat a truncated panel's last row as a
    month-end (the slate's fit panel ends on 2022-12-30, a true month-end)."""
    idx = pd.DatetimeIndex(index)
    s = pd.Series(idx, index=idx)
    return pd.DatetimeIndex(s.groupby([idx.year, idx.month]).max().values)


def hold_from_refresh(targets, index):
    """Targets decided on refresh dates (the rows of `targets`), each held until
    the next refresh: H.loc[t] = the latest refresh row at or before t; 0.0
    before the first. `evaluate()` then applies shift(2), so a target decided at
    the close of E_m fills at E_m+1 and earns from E_m+2 (H1).

    Raises if a refresh date is not a session of `index`, or if `targets` holds
    a NaN: a NaN would be forward-filled from the previous refresh, which is a
    position nobody decided (the caller writes 0.0 for an ineligible name)."""
    idx = pd.DatetimeIndex(index)
    if not targets.index.isin(idx).all():
        bad = targets.index[~targets.index.isin(idx)][:5]
        raise ValueError(f"refresh dates not in the calendar: {list(bad)}")
    if targets.isna().any().any():
        raise ValueError("targets hold NaN; write 0.0 for an ineligible name")
    return targets.reindex(idx).ffill().fillna(0.0)


def block_shuffle(H, block, rng):
    """The rows of H permuted in contiguous blocks of `block` rows (the last block
    may be shorter), the index kept: the slate's block-shuffled-signal placebo
    (PREREG §1.8). Each row's positions, and the turnover inside each block, are
    kept; their timing against the returns is destroyed. `rng` is a
    numpy Generator, so the draw is reproducible from its seed."""
    n = len(H)
    starts = np.arange(0, n, block)
    order = rng.permutation(len(starts))
    take = np.concatenate([np.arange(starts[i], min(starts[i] + block, n)) for i in order])
    return pd.DataFrame(H.values[take], index=H.index, columns=H.columns)


# =============================================================================
# EVENT HELPERS (added 2026-10-19; results/events/PREREG_E1_MERGER_PAIR_2026-10-19.md §6.4)
# =============================================================================
# WHY THEY LIVE HERE. E1 holds a pair of legs per merger deal from the evening of
# its announcement to its conversion or failure. That is a held book like any
# other, so it is scored by `evaluate()` unchanged; what is new is (1) how a list
# of deal legs becomes H, and (2) what a conversion costs. Both are added beside
# `hold_from_refresh`, visibly and with tests (scripts/cef/tests/test_event_hold.py),
# because a second copy of how a target becomes a held book is the shift(1)
# incident in a new place. Neither reads a return.

def event_hold(legs, index):
    """H from deal legs: H.loc[t, p] = the sum of the weights of every leg on
    permno p whose decision rows [first, last] contain t; 0.0 elsewhere.

    `legs`: a frame with columns permno, first, last, weight, ann. `first` and
    `last` are DECISION rows (sessions of `index`): the leg's weight is decided
    on the evening of `first`, filled at the close of the next session and,
    through `evaluate()`'s shift(2), earns from the session after that; the
    last return it earns is that of the session two after `last`. `ann` is the
    announcement date A the leg trades on.

    ALIGNMENT (H1/H7), asserted: the fill session -- the session after `first`
    -- must be strictly after `ann`. A filing dated A is public by the evening
    of A, so the earliest fill is the close of A+1; a first row whose fill is
    on or before A would trade on a filing before it existed.

    Raises on a NaN weight, a leg whose first or last row is not a session of
    `index`, a last row before its first, a first row with no session after it,
    and a fill not after `ann`. Legs on one permno are summed (an acquirer in
    two active groups is netted, PREREG §6.2)."""
    idx = pd.DatetimeIndex(index)
    if not idx.is_monotonic_increasing or idx.has_duplicates:
        raise ValueError("event_hold: the calendar must be increasing and unique")
    L = pd.DataFrame(legs)
    need = {"permno", "first", "last", "weight", "ann"}
    if not need <= set(L.columns):
        raise ValueError(f"event_hold: legs lack columns {sorted(need - set(L.columns))}")
    if L["weight"].isna().any() or not np.isfinite(L["weight"].astype(float)).all():
        raise ValueError("event_hold: a leg has a NaN or infinite weight")
    cols = sorted(L["permno"].unique())
    pos = {p: j for j, p in enumerate(cols)}
    H = np.zeros((len(idx), len(cols)))
    for r in L.itertuples(index=False):
        f, la = pd.Timestamp(r.first), pd.Timestamp(r.last)
        if f not in idx or la not in idx:
            raise ValueError(f"event_hold: leg on {r.permno} has a row outside the calendar ({f.date()}, {la.date()})")
        i0, i1 = idx.get_loc(f), idx.get_loc(la)
        if i1 < i0:
            raise ValueError(f"event_hold: leg on {r.permno} ends ({la.date()}) before it starts ({f.date()})")
        if i0 + 1 >= len(idx):
            raise ValueError(f"event_hold: leg on {r.permno} is decided on the calendar's last session")
        fill = idx[i0 + 1]
        if not fill > pd.Timestamp(r.ann):
            raise AssertionError(f"event_hold: leg on {r.permno} fills {fill.date()}, not after its "
                                 f"announcement {pd.Timestamp(r.ann).date()} (lookahead)")
        H[i0:i1 + 1, pos[r.permno]] += float(r.weight)
    return pd.DataFrame(H, index=idx, columns=cols)


def event_turnover(H, conversions):
    """Turnover of an event book whose completed deals end in a CONVERSION, not
    a trade (PREREG_E1 §3.2 item 6, §6.4).

    At completion each target share becomes acquirer shares, which cover the
    short; only the residual (the received shares' value minus the short's)
    trades. `evaluate()`'s Σ|ΔH| would charge both legs' removal as trades.
    Here, per row t and name i,

        turnover_t = Σ_i |ΔH[t, i] - C[t, i]| + Σ residual_t

    where C is the position change the conversions themselves make on row t
    (-w on the target, +w on the acquirer: the long leg becomes shares that
    close w of the short). Subtracting C name by name before taking |.| keeps
    the rule exact when the acquirer is also netted against another group's
    leg on the same row (the change left over is a genuine trade).

    `conversions`: a frame with columns row (the session on which the legs
    leave H, i.e. the leg's last decision row + 1), target, acquirer, weight
    (> 0: the target weight held into the conversion) and residual (>= 0: the
    residual trade in weight units, booked on `row`). Raises if a row is not a
    session of H, if a target or acquirer is not a column of H, if the weight
    is not positive, or if H does not drop the target by exactly `weight` on
    `row` (the conversion would not be closing the leg it names)."""
    H = pd.DataFrame(H)
    C = pd.DataFrame(0.0, index=H.index, columns=H.columns)
    res = pd.Series(0.0, index=H.index)
    for r in pd.DataFrame(conversions).itertuples(index=False):
        t = pd.Timestamp(r.row)
        if t not in H.index:
            raise ValueError(f"event_turnover: conversion row {t.date()} is not a session of H")
        for p in (r.target, r.acquirer):
            if p not in H.columns:
                raise ValueError(f"event_turnover: {p} is not a column of H")
        w = float(r.weight)
        if not w > 0 or not float(r.residual) >= 0:
            raise ValueError(f"event_turnover: conversion of {r.target} has weight {w}, residual {r.residual}")
        i = H.index.get_loc(t)
        if i == 0:
            raise ValueError("event_turnover: a conversion on the first row has no leg to close")
        drop = float(H.iat[i - 1, H.columns.get_loc(r.target)] - H.iat[i, H.columns.get_loc(r.target)])
        if abs(drop - w) > 1e-12 * max(1.0, abs(w)):
            raise AssertionError(f"event_turnover: H drops {r.target} by {drop} on {t.date()}, "
                                 f"not by the converted weight {w}")
        C.at[t, r.target] -= w
        C.at[t, r.acquirer] += w
        res.at[t] += float(r.residual)
    dH = H.diff().fillna(0.0)
    return (dH - C).abs().sum(axis=1) + res


def _stats(pnl, turn):
    """Gross SR and the 5/15/30bp net SRs from a P&L and turnover slice."""
    ann, vol = pnl.mean() * 252, pnl.std() * np.sqrt(252)
    t = turn.mean() * 252
    nets = [(ann - t * c / 1e4) / vol for c in (5, 15, 30)]
    return dict(sr=ann / vol, ann=ann, vol=vol, turn=t, nets=nets)


def _era_stats(H, R):
    r = evaluate(H, R)
    out = {}
    for lab, a, b in FIT_ERAS:
        out[lab] = _stats(r["pnl"].loc[a:b], r["turn_series"].loc[a:b])
    return out


def match_band_width(T, R, target_turn, lo=0.0005, hi=0.60, iters=40):
    """Band width whose fit-period turnover equals `target_turn` (bisection).

    Chosen on TURNOVER ONLY -- the H2 matching procedure -- never on P&L.
    Raises if the bracket cannot reach the target rather than returning the
    nearest edge (no silent fallback)."""
    f = lambda b: evaluate(band(T, b), R)["turn"]
    tlo, thi = f(lo), f(hi)
    if not (thi <= target_turn <= tlo):
        raise ValueError(f"turnover {target_turn:.2f} outside the band bracket "
                         f"[{thi:.2f} @ {hi}, {tlo:.2f} @ {lo}]")
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if f(mid) > target_turn:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def nearest_calendar(T, R, target_turn, ks=range(1, 253)):
    """Integer calendar k with fit turnover nearest `target_turn`, and its gap."""
    best = min(((abs(evaluate(calendar(T, k), R)["turn"] / target_turn - 1), k)
                for k in ks))
    return best[1], best[0]


def slower_policy_report():
    """Print the fit-period slower-policy tables. Report only; spends no trial."""
    T, R_px = build_targets()
    T, R_px = fit_only(T, R_px)
    R_tr = total_returns(R_px)
    assert R_tr.index.max() < HOLDOUT_START
    print(summary())
    print(f"FIT PERIOD ONLY: {T.index[0].date()} .. {T.index[-1].date()} "
          f"({len(T)} days). 2023+ is the sealed H13 holdout and is not computed.\n")

    live = (_lab_band(BAND_WIDTH), band(T, BAND_WIDTH))
    rows = ([live]
            + [(f"calendar {k}d", calendar(T, k)) for k in CONTEXT_CALENDARS + SLOW_CALENDARS]
            + [(f"band {b * 100:.1f}%", band(T, b)) for b in CONTEXT_BANDS + SLOW_BANDS])

    for conv, R in (("TOTAL returns (splits + distributions; the paper score)", R_tr),
                    ("PRICE returns (the convention of every frontier row above)", R_px)):
        print(f"=== {conv} ===")
        print("GROSS SR is the headline; net@5/15/30bp is the real-money cost "
              "grid, labelled, not mixed in. No borrow charged.\n")
        hdr = (f"{'policy':<22}{'era':<13}{'grossSR':>8}{'ann%':>7}{'turn/yr':>9}"
               f"{'net@5':>8}{'net@15':>8}{'net@30':>8}{'flips?':>8}")
        print(hdr, "-" * len(hdr), sep="\n")
        for lab, H in rows:
            es = _era_stats(H, R)
            for era, s in es.items():
                n5, n15, n30 = s["nets"]
                flip = "YES" if (np.sign(n5) != np.sign(n30)) else "no"
                print(f"{lab:<22}{era:<13}{s['sr']:8.2f}{s['ann'] * 100:7.2f}"
                      f"{s['turn']:9.1f}{n5:8.2f}{n15:8.2f}{n30:8.2f}{flip:>8}")
            tv = np.array([es[e]["turn"] for e in ("2015-2019", "2020-2022")])
            print(f"{'':<22}{'turn sd/mean (2015-19, 2020-22)':<45}{tv.std() / tv.mean():8.1%}")
        print()

    # --- H2: matched pairs ---------------------------------------------------
    live_turn = evaluate(live[1], R_px)["turn"]
    print("=== H2 turnover matching (fit period; turnover is convention-free) ===")
    print(f"live {live[0].strip()} fit turnover {live_turn:.1f}/yr. Candidates "
          f"within {MATCH_TOL:.0%}:")
    any_match = False
    for lab, H in rows[1:]:
        t = evaluate(H, R_px)["turn"]
        ok = abs(t / live_turn - 1) <= MATCH_TOL
        any_match |= ok and (lab.startswith("calendar 21") or
                             any(lab == f"band {b * 100:.1f}%" for b in SLOW_BANDS))
        print(f"  {lab:<20}{t:7.1f}/yr  gap {t / live_turn - 1:+7.1%}  "
              f"{'MATCH' if ok else 'no match'}")
    print(f"  -> slower candidate matched to the live band: "
          f"{'yes' if any_match else 'NONE (they trade less by construction)'}\n")

    print("=== class comparison at the SLOWER policies' own turnover ===")
    print("Each slower candidate against a partner of the other class whose fit")
    print("turnover is matched by bisection on turnover alone (H2), never on P&L.\n")
    for conv, R in (("TOTAL", R_tr), ("PRICE", R_px)):
        print(f"[{conv} returns]")
        print(f"{'policy':<38}{'era':<13}{'grossSR':>8}{'turn/yr':>9}"
              f"{'net@5':>8}{'net@15':>8}{'net@30':>8}")
        for k in SLOW_CALENDARS:
            Hc = calendar(T, k)
            tc = evaluate(Hc, R_px)["turn"]
            b = match_band_width(T, R_px, tc)
            pairs = [(f"calendar {k}d", Hc), (f"band {b * 100:.2f}% (matched)", band(T, b))]
            for lab, H in pairs:
                for era, s in _era_stats(H, R).items():
                    print(f"{lab:<38}{era:<13}{s['sr']:8.2f}{s['turn']:9.1f}"
                          + "".join(f"{n:8.2f}" for n in s["nets"]))
            print()
        for bw in SLOW_BANDS:
            Hb = band(T, bw)
            tb = evaluate(Hb, R_px)["turn"]
            k, gap = nearest_calendar(T, R_px, tb)
            tag = "matched" if gap <= MATCH_TOL else f"NOT matched, gap {gap:.1%}"
            pairs = [(f"band {bw * 100:.1f}%", Hb), (f"calendar {k}d ({tag})", calendar(T, k))]
            for lab, H in pairs:
                for era, s in _era_stats(H, R).items():
                    print(f"{lab:<38}{era:<13}{s['sr']:8.2f}{s['turn']:9.1f}"
                          + "".join(f"{n:8.2f}" for n in s["nets"]))
            print()

    # --- phase robustness of the monthly calendar -----------------------------
    print("=== calendar 21d: spread across all 21 refresh phases (fit, TOTAL) ===")
    for k in SLOW_CALENDARS:
        res = [_era_stats(calendar_offset(T, k, o), R_tr)["fit 2005-22"] for o in range(k)]
        for key, f in (("grossSR", lambda s: s["sr"]), ("turn/yr", lambda s: s["turn"]),
                       ("net@15", lambda s: s["nets"][1]), ("net@30", lambda s: s["nets"][2])):
            v = np.array([f(s) for s in res])
            print(f"  calendar {k}d {key:<8} min {v.min():6.2f}  median "
                  f"{np.median(v):6.2f}  max {v.max():6.2f}")


if __name__ == "__main__":
    if "--slower" in sys.argv[1:]:
        slower_policy_report()
    else:
        main()
