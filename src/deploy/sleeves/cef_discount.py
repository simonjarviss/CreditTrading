"""Credit closed-end fund discount reversion.

THE TRADE, IN ONE PARAGRAPH. A closed-end fund publishes what its portfolio is
worth (net asset value) every day, and its shares trade at whatever the market
pays. Unlike an ETF, a CEF's share count is FIXED -- there are no authorised
participants who can create or redeem shares against the basket, so nothing
mechanically drags the price back to NAV. Credit CEFs therefore sit at discounts
averaging -3.2% with a standard deviation near 6%, against roughly 0.04% for an
ETF. Those discounts wander and come back. We buy the funds trading unusually
cheap against their OWN history and sell the ones trading unusually rich, in
equal dollars, so a market-wide move in credit cancels out.

WHY AGAINST THEIR OWN HISTORY AND NOT EACH OTHER. A leveraged municipal CEF
structurally trades wider than a multi-sector one -- different fee, different
buyer, different leverage. Ranking on the raw discount would just be a permanent
long-muni/short-multisector bet dressed up as a signal. Ranking each fund against
its own normal level removes that and leaves the dislocation.

RISK SIZING IS VOLATILITY-TARGETED, and this is a measured decision, not a
default. Sorted by how dislocated the market is, this strategy's net Sharpe runs
1.24 / 0.59 / 0.80 / -0.23 / 0.68 from calm to stressed: it is BEST in calm
markets, because in stress the returns get bigger but the volatility grows faster.
A constant-notional book therefore takes its worst losses exactly when each unit
of risk pays least -- that is what produced a -31.5% drawdown at 35.8% volatility
in 2008. Scaling to constant risk on trailing realised volatility cut the
full-sample drawdown from -27% to -12%.

STALE NAV IS THE ONE THING THAT SILENTLY BREAKS THIS. The whole signal is
price-minus-NAV, so a fund whose NAV has not updated is not a cheap fund, it is a
blind one. Any fund whose NAV is older than `max_nav_age_bd` business days is
dropped for the day rather than traded. A NAV can also be stale and freshly
dated: Yahoo serves a row dated D carrying D-1's NAV
(results/cef/LIVE_NAV_QUALITY_2026-10-12.md §5). The runner's stale-NAV gate
(`quantt/session/nav_gate.py`) names the funds it could not verify by its final
pre-send check in `extras["nav_hold"]`: each keeps its current shares and leaves
the cross-section (`_nav_hold`). Absent, nothing changes.

TWO CONSTRAINTS SIT ON TOP OF THE SIGNAL, and both are OFF unless the frozen spec
turns them on. Neither is a return idea; each removes a way this book has been
measured to go wrong.

  `group_cap`         The cross-sectional demeaning above removes the market,
                      not the MANDATE. Measured on the live book at 2026-09-11,
                      92.5%-style concentration had become literal: the
                      rolling-252 R^2 of the book's own P&L to the in-panel
                      muni-minus-taxable spread was 0.746 (beta -0.62, NW
                      t -11.8) and effective breadth had fallen to 2.27 bets on
                      a nominal 17 names. `group_cap` bounds |sum(muni w) -
                      sum(taxable w)|. It buys risk and breadth, not return --
                      the paired return difference is statistically zero on
                      every window measured. `ng/05_research_group_neutrality.md`
                      (GN-N2: the nextgen branch's shadow "CEF trial 55", not
                      this repository's trial 55; see `_group_cap`).

  `max_gross_stress`  The vol scalar targets 6% of volatility; nothing targets
                      MARGIN, and margin is what this account is actually short
                      of. At the 2026-09-15 16:50 ET account read the fundable
                      gross under a worst-week buffer was 1.931x the $500k book,
                      and the book as it runs exceeds that on 17.0% of traded
                      days with nothing on the live path stopping it.
                      `max_gross_stress` scales the held book down -- never up,
                      never flat -- until it fits.
                      `ng/05_research_no_borrow_rescore.md` §6.2, §8.2.

FOUR MORE OPTIONAL KEYS LET A SECOND SPEC REUSE THIS SLEEVE (C4 deployment
plan, results/cef/C4_DEPLOY_PLAN_2026-10-27.md §1 row 1, added 2026-10-27).
Trial C4 (results/cef/PREREG_C4_FAMILIES_2026-10-13.md) ran this z-score on 74
other funds through `band_frontier.build_targets(universe=, source=, mask=)`.
Rather than copy the signal into a C4 module, the C4 spec will name:

  `panel_source`      which price and NAV parquet the sleeve reads
                      (`panel_paths`). Absent: `data/cef/`, as today.
  `nav_repeat_mask`   M1: a fund-day whose NAV equals its previous NAV row
                      exactly has no discount (`_discount_masks`).
  `zero_volume_mask`  M2: a fund-day with zero volume has no discount.
  `below_min_names`   "flatten" (absent; today's rule) or "hold" (the
                      trial's): what the book does when fewer than
                      `min_names` funds are eligible.

ALL FOUR ABSENT IS TODAY'S BOOK, BYTE FOR BYTE: the 13's plan.json, orders and
plan_sha were pinned from the code before the keys existed
(`quantt/session/tests/test_c4_keys_noop.py`), and the sleeve's targets were
diffed before and after on 1,758 real-panel date-books (the commit message).
Each key is parsed once, in `src/deploy/registry.py`, and a malformed value
raises naming it.

ONE MORE OPTIONAL KEY SIZES THE ACCOUNT, NOT THE STRATEGY: `sizing_multiplier`
(CEF trial 53, results/cef/PREREG_VOLTARGET_2026-10-30.md, approved 2026-11-01).
The account holds m times the UNIT book, which is the book this spec builds at its
own `vol_target_annual`, exactly as before. Three things change, and only when
the key is set:

  * the band compares the unit target with held / m;
  * `_cap_gross` acts at `max_gross_stress / m` in unit weights, so at
    `max_gross_stress` x the account's NAV: the same object gate 8 and
    `fit_to_buying_power` enforce;
  * every weight target is emitted as m x the unit weight. A band HOLD stays in
    shares, and the dust filter reads the unit weight.

WHY NOT RAISE `vol_target_annual`. On C4 it would break the fidelity gate
(scripts/cef/c4_paper_benchmark.py compares this sleeve's `w` at the
`min_abs_weight` read with the trial's T, and that key is its negative control).
On the core it would trade a different book from the one the multiplier was
derived on: the band would become 4.8% of a book m times larger. Measured on the
fit at m = 1.24, that is 19.2 turns a year against 17.1 (results/cef/prereg_voltarget/
impl_core.py). The unit book here IS that `w`, untouched. ABSENT (or null) the
code below is today's, byte for byte (quantt/session/tests/test_sizing_multiplier_noop.py
pins it against 35b429f's code; src/deploy/tests/test_sizing_multiplier.py tests
what the key does).

ONE MORE OPTIONAL KEY ADDS A SECOND SIGNAL: `level_signal` (CEF trial 54,
results/cef/PREREG_C4_LEVEL_2026-11-02.md §1, approved 2026-11-03; C4 only). The
z cannot see a fund that has sat rich of its peers for a year: standardised
against its own history, its z is near zero. Inside C4's families the discount
LEVEL against family peers predicts returns beyond the z, through the discount
and not the NAV (§2). With the key set, the UNIT target is no longer the z book
alone but an equal-risk blend, built on the date-t panel only:

  1. w_z: today's unit-gross z weights, exactly as before;
  2. w_L: on the SAME eligible names, -(disc - the family's mean disc), unit
     gross; a family with fewer than 2 eligible names contributes zero
     (`_level_weights`). `disc` is the masked discount the z is built from;
  3. s_z, s_L: each unit book's trailing realised vol, by the estimator the
     vol scalar has always used (`_book_vol`); mix = risk_share * w_z / s_z +
     (1 - risk_share) * w_L / s_L, renormalised to unit gross
     (`_blend_unit_book`);
  4. ONE vol scalar, the existing one, on s_mix;
  5. then today's path unchanged: the min-weight block, the band on held / m,
     `_cap_gross` at max_gross_stress / m, the dust filter on the unit weight.

C4's fidelity probe (scripts/cef/c4_paper_benchmark.py) reads `w` where it
always has, at the `min_abs_weight` read, so with the key set it reads the
blend. ABSENT, steps 2-3 do not run and the code is today's, byte for byte
(src/deploy/tests/test_level_signal.py pins it against f7f7be5's code; the
commit message diffs the real panels). Parsed and refused in
`registry.cef_level_signal`; the derivation and the REVERT are in C4's spec,
`_level_signal_note`.

ONE MORE VALUE OF `below_min_names`, "trade_eligible", WITH `below_min_names_floor`
(CEF trial 55, "te4", results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md,
approved by the team lead 2026-11-03, PAPER ONLY). On a session with fewer than
`min_names` eligible funds but at least the floor, and no NAV holds, the book is
built on the eligible funds with THIS sleeve's own construction instead of being
closed: the same demean and normalise, the same vol scalar on those funds' own
trailing 63 sessions, the band, the gross ceiling and m, all unchanged. Below the
floor every name is FLAT, today's rule. The harness version, which this must
equal, is `band_frontier.band_gross_capped(below_min_names="trade_eligible",
floor=)` on `build_targets(min_names=floor)`; the floor is derived there (one
name is 0/0, two carry only a sign, three force a side onto one fund).

  WHY PAPER ONLY, AND WHY THE SLEEVE ENFORCES IT. The rule was chosen because
  paper is scored on gross P&L with no borrow (D19/D20); net of measured 2023+
  borrow it LOSES to flatten (the pre-registration's §2.3). It is not shown to
  be alpha. So `target_positions` refuses to decide under the key unless the
  sleeve was built with `account="paper"` AND the runner passed
  `extras["thin_rule"]`, saying whether K0 (the account's drawdown record) or
  gate 7 (a short-open dropped as not shortable) stops the reduced build. A
  runner that knows nothing of the rule therefore gets a refusal, not a trade
  (§1.2: a runner revived from a tag, or written for another broker, would
  never reach a check that lived only in run.py). CONSTRUCTION CHECKS ONLY THE
  VALUE of `account` (None or exactly "paper"): the runner's `spec_panel`,
  `ops/common.py::deployed_tickers` and `quantt/session/combine.py` build this
  class every session without deciding, and must keep working with the key set.

  WHAT IS DELIBERATELY NOT CHANGED. With any NAV hold present the reduced build
  never runs, and today's `min_names` block runs as it is, tag included (§10
  Q10: the runner's missing-NAV refusal keys on that tag). The min-weight
  re-neutralisation still needs `min_names` survivors (Q12), so a reduced set is
  never re-neutralised: a name under `min_abs_weight` is flattened at the
  output and leaves a residual under that weight. A data shortfall still
  flattens (`strict` is set only by `panel_source` and "hold"). The one new
  refusal: on the reduced path a non-finite weight (every eligible z equal, so
  0/0) RAISES, naming the date and the names; a full session is untouched
  (PR #33 §5.H's silent hold is the owner's open question there).

  THE RECORD. Under the key, and only under it, every target carries
  `meta["cef_thin"]` = {eligible, n, min_names, floor, holds, reduced,
  stopped_by}: `reduced` is True exactly when the reduced build produced these
  targets (the trial's unit of evidence, §4.2, read as a structured field and
  never parsed from a reason), and `stopped_by` names K0 or gate 7 only where a
  stop removed a build that would otherwise have run. Reduced targets' reasons
  also say "reduced-set n=<n>/<min_names>". (The pre-registration's draft
  called the record `cef_reduced_set`; `cef_thin` is a superset of it.)

  ABSENT, "flatten" or "hold": byte for byte today's targets, meta included,
  proved on every real-panel decision date, flat and held books, against
  ac15d09's code under the same rule (results/cef/te4_impl/sleeve_noop_diff.py
  and the dated output beside it; "hold" was first run there after the reviews
  of f1d9f62, which found this sentence citing a comparison the script did not
  make; src/deploy/tests/test_te4_noop_proof_coverage.py pins the two together).
  `src/deploy/tests/test_below_min_names_trade_eligible.py` tests what the key
  does, the refusals, and the harness equality on the real panel.
"""
from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ..registry import (CEF_MASK_KEYS, cef_below_min_names, cef_below_min_names_floor,
                        cef_level_signal, cef_mask_flag, cef_optional_keys,
                        cef_panel_source, cef_sizing_multiplier, register)
from ..sleeve import ETF, FLAT, LONG, OK, SHORT, HALVE, KILL
from ..sleeve import MarketState, PositionTarget, RiskVerdict, Sleeve

REPO = Path(__file__).resolve().parents[3]
PX_PATH = REPO / "data/cef/cef_prices.parquet"
NAV_PATH = REPO / "data/cef/cef_nav.parquet"

# The group axis is read from the SAME file the prices come from, because it is
# the same column the research harness read (`gn_common.load_groups()` ->
# `cef_prices.parquet` `grp`, itself the security master's STATIC_ASSUMED
# attribute, `ng/data/secmaster.py:142`). A second source for the grouping is a
# second thing to disagree; the point of naming it here is that it is one path,
# patchable in tests exactly like PX_PATH.
GRP_PATH = PX_PATH

# Float dust, not a parameter. A dollar-neutral target row where one group is
# entirely unheld has net group weight 0 - 0 == 0 in exact arithmetic and ~1e-17
# in floating point; without this the k=0 identity check reports hundreds of
# "breaches" that are all 1e-17. Same constant, same reason, as the research
# harness (`gn_common.soft_cap`).
_GROUP_TOL = 1e-12


def _cap_net_group_weight(w: pd.Series, side: dict, k: float) -> tuple[pd.Series, bool]:
    """Shrink |net muni-minus-taxable weight| to at most `k`, dollar-neutrally.

    THE OPERATOR, AND WHY IT IS THIS ONE. `g = sum(w over muni) - sum(w over
    taxable)`. Shift every HELD muni weight by `-d_m` and every HELD taxable
    weight by `+d_t`. Dollar neutrality (the row's signed sum must not move)
    forces `n_m*d_m == n_t*d_t`; the cap forces `g - 2*n_m*d_m == sign(g)*k`.
    With `D = |g| - k > 0` that gives::

        d_m = sign(g)*D/(2*n_m)     d_t = sign(g)*D/(2*n_t)

    Rows already inside the cap are returned UNTOUCHED, which is what makes this
    a cap and not a tilt. The shift is uniform within a group because any other
    allocation needs a second parameter (a per-name penalty), and this change is
    allowed one.

    THIS IS NOT A PROPORTIONAL RESCALING OF THE OFFENDING SIDE, and the
    difference is the whole point: a rescaling shrinks the names that carry the
    tilt AND the names that oppose it, so it throws away name selection to buy
    group neutrality. The uniform shift only moves the group's centre. It also
    never drops a name -- a name whose weight crosses zero keeps trading, it
    simply changes side, which is the signal's own instruction once the group
    bet is removed.

    `n_m` / `n_t` count names HELD IN THIS ROW (non-zero weight), not the 6/11
    nominal group sizes: shifting a name the book does not hold would open a
    position the signal never asked for.

    NO SILENT FALLBACK. If the row breaches the cap while one entire side is
    unheld, no dollar-neutral uniform shift exists -- there is nothing to shift
    it against. Raise, rather than leave the row uncapped wearing a capped
    label.

    THE SAME OPERATOR GN-N2 WAS SCORED WITH, and the agreement is measured
    rather than claimed (`ng/store/deploy/gc_score.py` pins 3a/3b/3c, run over
    the full panel before it will print a table):

      * against a ROW-WISE transcription of `gn_common.soft_cap`'s algebra,
        max abs difference **exactly 0.0** -- same arithmetic, same order;
      * against `gn_common.soft_cap` VECTORISED over the frame -- the call
        `gn_score.py` actually made -- **5.551e-17** on 1,608 of 92,769 cells.
        That residual is numpy's summation order, not semantics: `g` is a sum
        of 6 and of 11 floats, and reducing a (17 x 5457) block along axis 1
        orders the additions differently from a 17-element row. Control: the
        identical pandas expression on `build_targets()`'s C-contiguous frame
        and on `T.copy()`'s F-contiguous one disagrees by 4.441e-16.
      * no reported statistic moves (gross SR, annual return, vol, turnover all
        agree to exactly 0.0), and the resulting book reproduces GN-N2's
        published traded row.

    See `ng/08_strategy_change.md` §3 and `src/deploy/tests/test_group_cap.py`.

    Returns `(weights, bound)` where `bound` says whether the cap moved the row.
    """
    if k < 0:
        raise ValueError(f"group_cap must be >= 0, got {k}")
    muni = [t for t in w.index if side[t] == "muni"]
    tax = [t for t in w.index if side[t] == "taxable"]
    g = float(w[muni].sum() - w[tax].sum()) if (muni or tax) else 0.0
    if not np.isfinite(g):
        raise ValueError("cef group_cap: net group weight is not finite; "
                         "refusing to cap a book it cannot measure")
    if abs(g) <= k + _GROUP_TOL:
        return w, False
    held_m = int((w[muni] != 0).sum())
    held_t = int((w[tax] != 0).sum())
    if held_m == 0 or held_t == 0:
        raise ValueError(
            f"cef group_cap: net group weight {g:+.6f} breaches k={k} but "
            f"{'muni' if held_m == 0 else 'taxable'} side is entirely unheld "
            f"({held_m} muni / {held_t} taxable names held); no dollar-neutral "
            f"uniform shift exists. Decide, do not default.")
    D = abs(g) - k
    s = math.copysign(1.0, g)
    d_m = s * D / (2.0 * held_m)
    d_t = s * D / (2.0 * held_t)
    out = w.copy()
    for c in muni:
        if out[c] != 0:
            out[c] = out[c] - d_m
    for c in tax:
        if out[c] != 0:
            out[c] = out[c] + d_t
    return out, True


def _cap_gross(w: pd.Series, cap: float) -> tuple[pd.Series, float]:
    """Scale the whole book down until gross exposure is at most `cap` x NAV.

    WHY A CAP AND NOT A TARGET. This never scales the book UP. At the
    2026-09-15 16:50 ET account read the margin the account can fund is
    G_stress = 1.931x the $500k book, and the book as it runs today exceeds that
    on 17.0% of traded days with NOTHING on the live path enforcing it
    (`ng/05_research_no_borrow_rescore.md` §6.2/§8.2). Levering UP to the cap is
    a different construction -- book (b) in that note, +14.2% CAGR at 8.55% vol
    -- which is a sizing decision with its own evidence and its own trial. This
    key only removes the breach.

    WHY IT SCALES RATHER THAN DROPS NAMES. One uniform multiplier is the only
    reduction that leaves every relative bet, the dollar-neutrality and the net
    group weight's RATIO to gross exactly where the signal put them. Dropping
    names to fit a margin line would silently re-select the book against a
    constraint that has nothing to do with the signal.

    It cannot flatten the book: `f = cap/gross` is in (0, 1) whenever it binds,
    and a zero-gross book returns unscaled. A name can still be dropped
    downstream if scaling takes it under `min_abs_weight` -- that is the
    pre-existing dust rule, its effect here is to reduce gross slightly FURTHER
    (never to increase it), and it is disclosed rather than special-cased.

    Returns `(weights, f)`; `f == 1.0` exactly when the cap did not bind.
    """
    if not (cap > 0):
        raise ValueError(f"max_gross_stress must be > 0, got {cap}")
    gross = float(w.abs().sum())
    if not np.isfinite(gross):
        raise ValueError("cef max_gross_stress: gross exposure is not finite; "
                         "refusing to size against a book it cannot measure")
    if gross <= cap or gross == 0.0:
        return w, 1.0
    f = cap / gross
    return w * f, f


def _book_vol(ret: pd.DataFrame, w: pd.Series):
    """Annualised realised vol of the book `w` held over the last 63 sessions of `ret`.

    THE SLEEVE'S ONE VOL ESTIMATOR. It is the expression the vol scalar has used
    since the book went live, moved here unchanged so that `level_signal`'s two
    unit books and their blend are measured by the same estimator as the z book
    (PREREG_C4_LEVEL §1.2 step 3: "the estimator `build_targets` already uses for
    its vol scalar"; `band_frontier.build_targets` is the same sum, std and
    sqrt(252)). Today's weights on past returns: a NaN return (a gap, or a move
    of 50% or more, filtered by the caller) adds nothing to that day's P&L.

    ALIGNMENT is the caller's: every row of `ret` must be dated on or before the
    decision. `target_positions` passes returns through the signal date only.
    """
    hist = (ret[list(w.index)].mul(w, axis=1)).sum(axis=1).tail(63)
    return hist.std() * np.sqrt(252)


def _level_weights(disc_t: pd.Series, family_of: dict) -> pd.Series:
    """w_L: -(discount - its family's mean discount) on today's eligible names, unit gross.

    PREREG_C4_LEVEL §1.2 step 2, declared before the screen first ran
    (alpha_level.py) and never varied: within family, unit gross, the raw
    discount level, z-blind.

    WITHIN FAMILY, NEVER POOLED. A pooled level would be a permanent bet on one
    family's structural discount against another's (docs/SYSTEM.md; §3.2 "not
    chosen"). Each family is demeaned on its OWN eligible names today, so the
    level book is dollar-neutral inside every family.

    A FAMILY WITH FEWER THAN 2 ELIGIBLE NAMES CONTRIBUTES ZERO: one name has no
    peer to be rich or cheap against. (Its deviation from its own mean is 0.0
    exactly anyway; the zero is set explicitly so the rule does not rest on that.)

    `disc_t` is the date-t discount of the eligible names, in `target_positions`'
    row order, with C4's M1|M2 masks already applied (an eligible name has an
    unmasked, finite discount: its z is computed from it). The output has the
    same index, in the same order, so it lines up with w_z name for name.

    NO SILENT FALLBACK. An eligible ticker with no family, a non-finite discount
    and a level book with no gross (every family a singleton, or every family's
    discounts exactly equal) each RAISE, naming the cause. Unreachable for C4
    (74 names, 5 families, min_names 6: by pigeonhole at least one family has two
    eligible names), so a raise there means a broken input, not a quiet day.
    """
    missing = [t for t in disc_t.index if t not in family_of]
    if missing:
        raise ValueError(f"cef level_signal: no family for eligible ticker(s) {missing} in "
                         f"family_of; refusing to guess a family")
    if not np.isfinite(disc_t.to_numpy(dtype=float)).all():
        raise ValueError(f"cef level_signal: non-finite discount on the signal date for "
                         f"{list(disc_t.index[~np.isfinite(disc_t.to_numpy(dtype=float))])}")
    fam = pd.Series({t: family_of[t] for t in disc_t.index}, index=disc_t.index)
    dev = disc_t - disc_t.groupby(fam).transform("mean")
    n = fam.map(fam.value_counts())
    dev = dev.where(n >= 2, 0.0)
    w = -dev
    g = float(w.abs().sum())
    if not (np.isfinite(g) and g > 0.0):
        raise ValueError(f"cef level_signal: the level book has no gross on the signal date "
                         f"(families {fam.value_counts().to_dict()}); a unit-gross w_L does "
                         f"not exist")
    return w / g


def _blend_unit_book(w_z: pd.Series, w_L: pd.Series, ret: pd.DataFrame,
                     risk_share: float) -> tuple[pd.Series, dict]:
    """(mix, vols): the equal-risk blend of the unit-gross z and level books, unit gross.

    PREREG_C4_LEVEL §1.2 step 3. s_z and s_L are each book's trailing realised vol
    (`_book_vol`, today's weights on the last 63 sessions of price returns through
    t), and

        mix = risk_share * w_z / s_z + (1 - risk_share) * w_L / s_L,  / sum|.|

    so that, before the renormalisation (one positive factor on both), the z part
    and the level part each carry their share of the ex-ante vol: risk_share and
    1 - risk_share of a unit. At 0.50, the derived value (§3.1: the two-sleeve
    mean-variance rule gives 0.514 on z, and two Sharpes this noisy do not support
    0.514 over a half), the two parts have EQUAL standalone vol, which is also
    what makes their Euler risk contributions equal whatever their correlation.
    `vols["s_mix"]` is the blend's own vol by the same estimator, for the one vol
    scalar that follows.

    WHY RISK AND NOT GROSS. The two books have different vols per unit of gross
    (the level book's names are the structurally rich and cheap funds), so a gross
    split would hand the risk to whichever book is more volatile that quarter.

    NO SILENT FALLBACK. A non-finite or zero vol for either book or for the blend
    has no ratio to take, and raises naming which. The z path sized at scalar
    1.0 in that case until 2026-11-19; it raises too now (`target_positions`).
    """
    if not w_z.index.equals(w_L.index):
        raise ValueError("cef level_signal: w_z and w_L are not on the same names in the same order")
    vols = {"s_z": _book_vol(ret, w_z), "s_L": _book_vol(ret, w_L)}
    for k, s in vols.items():
        if not (np.isfinite(s) and s > 0.0):
            raise ValueError(f"cef level_signal: {k} = {s!r}; the risk-equalised blend needs a "
                             f"finite, positive trailing vol for both books")
    mix = risk_share * (w_z / vols["s_z"]) + (1.0 - risk_share) * (w_L / vols["s_L"])
    g = float(mix.abs().sum())
    if not (np.isfinite(g) and g > 0.0):
        raise ValueError(f"cef level_signal: the blend has gross {g!r}; nothing to renormalise")
    mix = mix / g
    vols["s_mix"] = _book_vol(ret, mix)
    if not (np.isfinite(vols["s_mix"]) and vols["s_mix"] > 0.0):
        raise ValueError(f"cef level_signal: s_mix = {vols['s_mix']!r}; the blend's vol scalar "
                         f"needs a finite, positive trailing vol")
    return mix, vols


def _nav_hold(market_state, last: pd.Timestamp, universe) -> dict:
    """{ticker: reason}: names whose NAV the runner's stale-NAV gate could not verify.

    WHY. Yahoo serves a NAV row dated D that still carries an older NAV and
    corrects it later; on the laptop's paper sessions 28 of 73 checkable
    name-days were decided on such a row and 11 submitted orders were sized on
    one (results/cef/LIVE_NAV_QUALITY_2026-10-12.md §5). The runner checks each
    suspect NAV against CEFConnect (`quantt/session/nav_gate.py`). A name still
    unverified at its final pre-send check is HELD (team lead 2026-10-13): it
    keeps its current shares -- no order in it -- and leaves the cross-section,
    so its unverified z moves no other name's weight.

    WHY HOLD AND NOT DROP. The first version dropped such a name (target zero,
    then the band). Replayed on the laptop's sessions, that would have cut held
    positions to the band edge on the strength of a missing CEFConnect row, and
    on 2026-10-05 left 4 eligible names, under `min_names`, where the rule
    below emits every name FLAT and decide closes the whole book. So a held
    name is never targeted to zero, and holds never trigger that flatten
    (`target_positions`, the `min_names` block): when the cross-section is short
    of `min_names` only because of holds, the whole book holds for the day.

    Held names stay out of the sleeve's band and gross cap: their shares are
    fixed, so nothing here may scale them. Their gross is judged with the rest
    of the book by gate 8 and the send-time fit (`quantt/session/run.py`).

    A SECOND SOURCE OF HOLDS (2026-10-29, dark): the runner's missing-NAV hold
    (book json `data.missing_nav`, `quantt/session/gate.py` `missing_nav_hold`)
    passes, through this same extra, a name with no NAV dated the decision
    date, from the final check. Same contract; such a name has no paired row
    on the date, so it is counted toward `min_names` as possibly eligible
    (`target_positions`, the loop that builds the cross-section).

    `extras["nav_hold"] = {"asof": <date>, "names": {ticker: reason}}`. ABSENT
    is today's behaviour, byte for byte: proved against the sleeve before this
    change on 56 real panel dates, flat and held books (2026-10-13, the commit
    message), and kept by `src/deploy/tests/test_nav_hold.py`. Present, it must
    be well formed, name only universe tickers, and carry the date the sleeve
    decides on: a gate run for another day than the signal date is a runner
    bug, and holding on it would act on a NAV the gate never looked at. Each
    violation raises.
    """
    extras = getattr(market_state, "extras", None) or {}
    if "nav_hold" not in extras:
        return {}
    spec = extras["nav_hold"]
    if not isinstance(spec, dict) or set(spec) != {"asof", "names"}:
        raise ValueError(f"cef: extras['nav_hold'] must be {{'asof', 'names'}}, got {spec!r}")
    names = spec["names"]
    if not isinstance(names, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v for k, v in names.items()):
        raise ValueError(f"cef: extras['nav_hold']['names'] must map ticker -> non-empty "
                         f"reason, got {names!r}")
    stray = sorted(set(names) - set(universe))
    if stray:
        raise ValueError(f"cef: extras['nav_hold'] names {stray}, not in the universe")
    if pd.Timestamp(spec["asof"]).normalize() != pd.Timestamp(last).normalize():
        raise ValueError(f"cef: the stale-NAV gate checked {spec['asof']} but the sleeve "
                         f"decides on {pd.Timestamp(last).date()}; refusing to hold on a "
                         f"NAV the gate did not look at")
    return dict(names)


# The tag on every target of a decide that HAD holds (`extras["nav_hold"]`) and
# fell short of `min_names` eligible names (release-check of 6d42f4f, 2026-10-29).
SHORT_OF_MIN_NAMES = "cef_short_of_min_names"

# The structured record every target carries under `below_min_names =
# "trade_eligible"` (CEF trial 55; module docstring, THE RECORD), and only then.
THIN_META = "cef_thin"
# What may stop a reduced build that would otherwise run (`extras["thin_rule"]`):
# K0, the account's drawdown record reading anything but OK (pre-registration
# §6.3), and gate 7, a short-open dropped as not shortable (§7.5).
THIN_STOPS = ("K0", "gate7")


def _hold_requested(market_state) -> bool:
    """True when the runner passed holds (a non-empty `extras["nav_hold"]["names"]`).
    Only decides whether to TAG an early return; `_nav_hold` validates the extra."""
    spec = (getattr(market_state, "extras", None) or {}).get("nav_hold")
    return isinstance(spec, dict) and bool(spec.get("names"))


def _tag_short(targets: list, info: dict) -> list:
    """`targets`, each with `meta[SHORT_OF_MIN_NAMES] = info`.

    WHY (release-check of 6d42f4f, execution-trader, reproduced). With holds,
    the sleeve's `min_names` rule holds the whole book (or, short without the
    holds, flattens the rest) and decide sends nothing: the plan reads
    NOTHING_TO_SEND, the day is marked DONE and the next slot idles, although
    no name was decided on its signal. The runner must be able to tell that
    day from a quiet one. This says so in a structured field, not a reason
    string: `info` = {"eligible": names in the cross-section, "min_names",
    "held_out": held names counted toward it, "excluded": {name: why the
    sleeve left it out}}. The runner's missing-NAV hold refuses on it
    (`quantt/session/run.py`); the stale-NAV gate's holds keep their ruled
    whole-book hold. `meta` reaches no order and no plan.json (decide reads
    reason, side, qty and weight only), and the tag is added only when holds
    were passed, so without them every target is byte-identical."""
    return [dataclasses.replace(t, meta={**t.meta, SHORT_OF_MIN_NAMES: dict(info)})
            for t in targets]


def _held_target(tk: str, market_state, reason: str, order_type: str) -> PositionTarget:
    """The target that keeps `tk` at exactly its current shares: a qty target
    (decide uses it as given, so the delta is zero and nothing is sent), or FLAT
    when nothing is held (a target of 0 against 0 sends nothing either). An
    unreadable holding raises: an unmeasured position is not a held one."""
    holds = getattr(market_state, "holdings", None) or {}
    try:
        q = float(holds.get(tk, 0.0) or 0.0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"cef: holding {tk!r} is {holds.get(tk)!r}; cannot hold it") from exc
    if not np.isfinite(q):
        raise ValueError(f"cef: holding {tk!r} is {q}; cannot hold it")
    if q == 0.0:
        return PositionTarget(instrument=tk, side=FLAT, kind=ETF,
                              reason=f"cef: not opened, {reason}")
    return PositionTarget(instrument=tk, side=LONG if q > 0 else SHORT, kind=ETF, qty=q,
                          meta={"order_type": order_type}, reason=f"cef: held, {reason}")


def _nav_repeat(nav: pd.DataFrame) -> pd.Series:
    """True where a fund's NAV equals its own PREVIOUS NAV ROW exactly; aligned to `nav`.

    THE TRIAL'S DEFINITION, OPERATION FOR OPERATION. M1 is declared in
    PREREG_C4_FAMILIES_2026-10-13 §4.3 ("a fund-day whose yfinance NAV equals
    that fund's previous yfinance NAV row exactly has no discount that day") and
    was computed by `scripts/cef/c4_feasibility.py::repeat_mask`, which
    `c4_families.declared_mask` applied. This is the same sort, the same
    per-ticker `diff`, the same `eq(0)` -- copied rather than imported because
    `scripts/` is never on the live path (CLAUDE.md layout).
    `src/deploy/tests/test_c4_sleeve_keys.py` holds the two equal on a messy
    frame, so the copy cannot drift silently.

    "Previous ROW" is the NAV file's previous row for the fund, not the previous
    session of the joined panel: a NAV row with no price that day, or one below
    the $0.50 floor, is still the NAV the next row is compared with, exactly as
    in the trial. A NaN NAV is never a repeat (NaN - x is NaN, and NaN == 0 is
    False), and neither is a fund's first row.

    No lookahead: the flag on row t reads row t and the row before it, both
    published by t's decision (the sleeve decides after t's NAV is out).
    """
    n = nav.sort_values(["ticker", "date"])
    rep = n.groupby("ticker")["nav"].diff().eq(0)
    return rep.reindex(nav.index)


@register
class CEFDiscountSleeve(Sleeve):
    """Dollar-neutral, cross-sectional discount reversion in credit CEFs."""

    alloc_type = "cef_discount"

    def __init__(self, spec: dict, capital_usd: float, *, account=None):
        """Parses the four optional C4 keys at construction (absent: nothing to
        parse, and nothing else happens). Tests and tools build this class
        without the registry; a malformed key must refuse there too, and on
        every day rather than on the first day its branch is reached.

        `account` (CEF trial 55, PAPER ONLY): None, or exactly the string
        "paper", the caller's declaration that the account this sleeve decides
        for is a paper account. Anything else raises here. Only its VALUE is
        checked at construction, whatever the spec says: three callers build
        this class every session without deciding (module docstring), so the
        refusal of `below_min_names = "trade_eligible"` without the declaration
        is in `target_positions`, on every call. Absent, nothing changes."""
        super().__init__(spec, capital_usd)
        cef_optional_keys(self.frozen)
        cef_sizing_multiplier(self.frozen)      # a malformed multiplier refuses at construction
        cef_level_signal(self.frozen)           # so does a malformed level_signal or family map
        cef_below_min_names_floor(self.frozen)  # and a floor beside the wrong rule (CEF trial 55)
        if account is not None and not (type(account) is str and account == "paper"):
            raise ValueError(
                f"cef: account {account!r} must be None or exactly 'paper'. The only "
                f"declaration this sleeve takes is that its account is paper "
                f"(below_min_names='trade_eligible' is PAPER ONLY); there is no other value")
        self._account = account

    # ---- config ------------------------------------------------------------
    # Every knob below is REQUIRED in the frozen spec, and a missing one raises
    # naming the key. Until 2026-09-14 each was `frozen.get(key, <number>)`: a
    # spec that lost `vol_target_annual` would have sized the book at a 6%
    # target that no document or decision had set, silently, and the same for
    # the z window, the ADV floor, the name floor, leverage and the order type.
    # The live spec carries every one of these keys, so for it this is a
    # proven no-op (sleeve targets diffed byte-for-byte before and after on the
    # last six panel dates). `band_width` is the one deliberate exception:
    # ABSENT MEANS OFF, by design, and it keeps its `.get`.
    def _req(self, key: str):
        if key not in self.frozen:
            raise KeyError(
                f"cef_discount frozen spec has no '{key}'. Every sizing and "
                f"signal knob must be set in ops/specs/cef_discount.frozen.json; "
                f"the sleeve will not invent one (CLAUDE.md, no silent fallbacks).")
        return self.frozen[key]

    @property
    def _win(self) -> int:
        return int(self._req("z_window"))

    @property
    def _min_adv(self) -> float:
        return float(self._req("min_adv_usd"))

    @property
    def _vol_target(self) -> float:
        return float(self._req("vol_target_annual"))

    @property
    def _band_width(self) -> "float | None":
        """No-trade band half-width, in weight units. ABSENT MEANS OFF.

        When set, this REPLACES the `rebalance_days` calendar: the signal is
        computed every session and a position is left alone unless it is more
        than `band_width` from its target, in which case it is traded back to
        the BAND EDGE -- not to target. Constantinides (1986), Davis & Norman
        (1990): under proportional cost the optimal policy is a band, and the
        boundary is where you stop, not where you aim.

        Absent, this sleeve behaves exactly as before. That is deliberate --
        the code change alone must be a no-op, so that turning the policy on is
        a single visible edit to the frozen spec and nothing else.
        """
        v = self.frozen.get("band_width")
        return None if v in (None, "") else float(v)

    @property
    def _group_cap(self) -> "float | None":
        """Max |net muni-minus-taxable weight| on the final target. ABSENT MEANS OFF.

        Absent (or null), this sleeve behaves exactly as before -- the code
        change alone is a no-op, so that turning the constraint on is a single
        visible edit to the frozen spec and nothing else, exactly as
        `band_width` was activated. The no-op is PROVED, not asserted:
        `src/deploy/tests/test_group_cap.py::test_absent_and_null_are_byte_identical`.

        Adopted from GN-N2 (`ng/05_research_group_neutrality.md`), already
        spent. The nextgen branch numbered GN-N2 "CEF trial 55"; the team lead
        ruled on 2026-09-28 that the counter on `main` is authoritative and the
        nextgen trials (53-56) were shadow research (docs/RESEARCH_STATE.md, the
        CEF 48 -> 50 note). CEF trial 55 in this repository is te4, the
        thin-session rule `below_min_names = "trade_eligible"` (relabelled
        2026-11-03). What it buys is measured and is NOT a return improvement:
        the paired daily return difference against the uncapped band is
        statistically zero on every window (traded -0.71 %/yr, NW t -1.06). It
        buys lower vol (5.56% vs 6.57%), lower turnover (25.9 vs 28.8), lower
        gross (1.23x vs 1.44x) and two-thirds of the breadth recovery
        (last-12m ENB 2.27 -> 4.38, rolling-252 R^2 to the factor 0.746 -> 0.121).
        """
        v = self.frozen.get("group_cap")
        return None if v in (None, "") else float(v)

    @property
    def _max_gross_stress(self) -> "float | None":
        """Hard ceiling on gross exposure, as a multiple of sleeve NAV. ABSENT MEANS OFF.

        Absent (or null), this sleeve behaves exactly as before. This is a
        MARGIN constraint, not a sizing decision: it only ever scales the book
        down. See `_cap_gross`.

        NOT the same object as `risk.max_gross_exposure_usd` (a dollar limit
        read by the book-level risk layer). This one is a multiple of the
        sleeve's own marked NAV and is applied inside the sleeve, after the
        band, before anything is emitted.
        """
        v = self.frozen.get("max_gross_stress")
        return None if v in (None, "") else float(v)

    @property
    def _sizing_multiplier(self) -> "float | None":
        """m: the account holds m x this spec's unit book. ABSENT (or null) MEANS TODAY.

        Parsed by `registry.cef_sizing_multiplier` (a non-number, a value of zero or
        below, or a near-miss spelling raises). `_validate_cef_discount` also
        requires `max_gross_stress` alongside it and keeps 0.06 x m in the sane
        band. What the sleeve does with it is in the module docstring. The
        derivation, the value and the REVERT are in the spec's
        `_sizing_multiplier_note`.
        """
        return cef_sizing_multiplier(self.frozen)

    @property
    def _level_signal(self) -> "dict | None":
        """{"risk_share", "family_of"}: the within-family level blend. ABSENT MEANS TODAY.

        Parsed by `registry.cef_level_signal` on every read, so a spec edited
        under a built sleeve is refused on the next decide rather than half-read:
        null, a risk_share outside (0, 1), a family map that does not cover the
        universe exactly, the key without `band_width`, and a near-miss spelling
        all raise. `risk_share` is the share of ex-ante risk on the Z book. What
        the sleeve does with it is in the module docstring (`_level_weights`,
        `_blend_unit_book`); the derivation, the value and the REVERT are in the
        spec's `_level_signal_note`.
        """
        return cef_level_signal(self.frozen)

    @property
    def _rebal_days(self) -> int:
        return max(1, int(self._req("rebalance_days")))

    @property
    def _below_min_names(self) -> str:
        """"flatten" (ABSENT: today's rule), "hold" (trial C4's) or
        "trade_eligible" (CEF trial 55, paper only; `_thin_rule`). See the
        `min_names` block in `target_positions`; parsed in the registry."""
        return cef_below_min_names(self.frozen)

    def _thin_rule(self, market_state) -> "dict | None":
        """{"floor", "stop"} under `below_min_names = "trade_eligible"`; None otherwise.

        THE PAPER-ONLY REFUSAL, ON EVERY CALL (pre-registration §1.2, §10 Q14).
        Under the key this raises, naming it, unless the sleeve was built with
        `account="paper"` and the runner passed `extras["thin_rule"]` =
        {"stop": None | {"by": "K0" | "gate7", "why": <non-empty str>}}. The
        extra is required even when nothing stops the build: a runner that
        does not pass it has not measured K0, and a reduced build on an
        unmeasured account drawdown is the case K0 exists to stop (§6.3:
        UNMEASURED flattens). Any other shape raises rather than be read as
        "no stop". Under any other rule the extra is not read at all, so the
        key-absent path cannot depend on it."""
        if self._below_min_names != "trade_eligible":
            return None
        floor = cef_below_min_names_floor(self.frozen)
        if self._account != "paper":
            raise ValueError(
                f"cef: below_min_names='trade_eligible' is PAPER ONLY (CEF trial 55) and this "
                f"sleeve was built with account={self._account!r}. The runner declares "
                f"account='paper' only when its broker client's endpoint is the paper "
                f"endpoint; nothing decided")
        extras = getattr(market_state, "extras", None) or {}
        if "thin_rule" not in extras:
            raise ValueError(
                "cef: below_min_names='trade_eligible' needs extras['thin_rule'] = "
                "{'stop': None | {'by': 'K0'|'gate7', 'why': str}}: the runner must say "
                "whether K0 or gate 7 stops the reduced build; nothing decided")
        tr = extras["thin_rule"]
        well_formed = isinstance(tr, dict) and set(tr) == {"stop"}
        stop = tr["stop"] if well_formed else None
        if well_formed and stop is not None:
            well_formed = (isinstance(stop, dict) and set(stop) == {"by", "why"}
                           and stop["by"] in THIN_STOPS and isinstance(stop["why"], str)
                           and bool(stop["why"].strip()))
        if not well_formed:
            raise ValueError(
                f"cef: below_min_names='trade_eligible': extras['thin_rule'] must be "
                f"{{'stop': None | {{'by': one of {list(THIN_STOPS)}, 'why': non-empty str}}}}, "
                f"got {tr!r}; nothing decided")
        return {"floor": floor, "stop": None if stop is None else dict(stop)}

    def panel_paths(self) -> tuple[Path, Path]:
        """(prices, nav): the two parquet files this sleeve decides on.

        `panel_source` ABSENT: the module's PX_PATH and NAV_PATH, read at CALL
        time so the tests and the runner's no-op proofs can patch them, exactly
        as before the key existed -- `data/cef/`, the 13's panels. PRESENT:
        `REPO / <path>` for each (`registry.cef_panel_source` says what a valid
        path is). C4's will name the families panels that plan row 3 builds
        nightly, so the core's `data/cef/` is never written for it.

        READ BY THE RUNNER TOO (plan row 6A, 2026-10-29). `quantt/session/run.py`
        `spec_panel` calls this method, and the runner takes the closes it sizes
        on, the NAV dates gate 5 checks, the pre-flight's history and the
        stale-NAV gate's file from the panel it returns, so a sleeve is decided,
        sized and gated on one panel (run.py PER-SLEEVE PANELS). Until row 6A
        the runner read `data/cef/` whatever this returned and refused any
        other panel (C4 step 1's `require_core_panel`).
        """
        src = cef_panel_source(self.frozen)
        if src is None:
            return PX_PATH, NAV_PATH
        return REPO / src[0], REPO / src[1]

    def _groups(self) -> dict:
        """muni vs taxable by STATED MANDATE, read from the price panel's `grp`.

        ONE SOURCE, THE SAME ONE THE RESEARCH USED. `gn_common.load_groups()`
        read `cef_prices.parquet`'s `grp` column, which is the security master's
        STATIC_ASSUMED `grp` attribute (`ng/data/secmaster.py:142`, basis
        "cef_prices.parquet grp column (current mandate)"). Defining the groups
        by MANDATE rather than by a return clustering is the point: a grouping
        fitted to returns would be fitted to the very thing the cap exists to
        neutralise, and the neutrality would be circular.

        KNOWN CAVEAT, carried from the research and not re-derived here: `grp`
        is the CURRENT mandate applied over all history. Two of the 17 have
        recorded CRSP mandate changes (AWF 2007-01-29, PFN 2010-03-01) and
        NEITHER crosses the muni/taxable line, so the binary split is
        unaffected. A five-group split would not be.

        The axis is muni vs NOT-muni: the panel's `grp` takes the values
        muni / hy / loan / multi, and everything that is not `muni` is taxable.

        NO SILENT FALLBACK, three ways. A missing column, a ticker with two
        different `grp` values, or a universe name with no `grp` row all raise
        naming what is missing. A defaulted mandate would put a name on the
        wrong side of the very constraint being applied, and nothing downstream
        would notice.

        WITH `panel_source` SET the axis is read from THAT spec's price file,
        for the reason above: one path, the one the prices come from. Reading
        the core's `data/cef/` for another universe would raise on every name
        (no `grp` row), or worse, find a stale row for a ticker both panels
        hold. Absent, GRP_PATH as before.
        """
        grp_path = GRP_PATH if cef_panel_source(self.frozen) is None else self.panel_paths()[0]
        if not grp_path.exists():
            raise FileNotFoundError(
                f"cef group_cap is set but the group source {grp_path} does not "
                f"exist. The muni/taxable axis is read from the price panel's "
                f"`grp` column; there is no second source and no default.")
        try:
            P = pd.read_parquet(grp_path, columns=["ticker", "grp"])
        except Exception as exc:                      # noqa: BLE001 -- re-raised
            raise ValueError(
                f"cef group_cap is set but {grp_path} has no readable "
                f"ticker/grp columns ({exc}). Refusing to guess a mandate."
            ) from exc
        P = P.drop_duplicates()
        n = P.groupby("ticker")["grp"].nunique()
        ambiguous = sorted(n[n != 1].index)
        if ambiguous:
            raise ValueError(
                f"cef group_cap: {grp_path} gives more than one `grp` for "
                f"{ambiguous}; the mandate axis must be unique per name.")
        g = P.groupby("ticker")["grp"].first().to_dict()
        uni = self.instruments()
        missing = sorted(set(uni) - set(g))
        if missing:
            raise ValueError(
                f"cef group_cap: no `grp` for {missing} in {grp_path}; "
                f"refusing to guess a mandate.")
        return {t: ("muni" if g[t] == "muni" else "taxable") for t in uni}

    def instruments(self) -> list[str]:
        return sorted(self._req("universe"))

    def history_warmup_trading_days(self) -> int:
        return self._win + 80

    # ---- data --------------------------------------------------------------
    def _panel(self, asof) -> tuple[pd.DataFrame, ...] | None:
        """Price / NAV / ADV panels up to and including `asof`.

        Read from the staged parquet rather than MarketState because NAV is not
        a price and the book's loader has no concept of it.

        THE CONTRACT IS UNCHANGED: `(px, nav, vol)` or None.
        `scripts/cef/vol_scalar_history.py` and its test read it. Since the C4
        keys (2026-10-27) it is a view of `_read_panel`, which also returns the
        raw NAV rows M1 needs; the masks are not applied here.
        """
        got = self._read_panel(asof)
        return None if got is None else got[:3]

    def _read_panel(self, asof) -> tuple[pd.DataFrame, ...] | None:
        """`(px, nav, vol, navrows)` up to and including `asof`, or None.
        `navrows` is the NAV file's rows for the universe, every date, before
        the join with prices: M1 compares a NAV with its previous NAV ROW,
        priced or not (`_nav_repeat`). Which parquet: `panel_paths()`.

        A MISSING OR EMPTY PANEL: with `panel_source` absent this returns None
        and the caller emits every name FLAT, as it always has. With
        `panel_source` SET it raises, naming the file. A spec that names its
        own panel and finds none has a broken data step (for C4, plan row 3),
        and flattening the book on a missing file is the wrong answer to a
        missed refresh: a raise is a missed day, which the runner records.
        """
        explicit = cef_panel_source(self.frozen) is not None
        px_path, nav_path = self.panel_paths()
        if not (px_path.exists() and nav_path.exists()):
            if explicit:
                raise FileNotFoundError(
                    f"cef: panel_source names {px_path} and {nav_path}; "
                    f"{[str(p) for p in (px_path, nav_path) if not p.exists()]} do not exist. "
                    f"Not deciding, and not flattening, on a panel that is not there.")
            return None
        P = pd.read_parquet(px_path)
        N = pd.read_parquet(nav_path)
        uni = set(self.instruments())
        P, N = P[P.ticker.isin(uni)], N[N.ticker.isin(uni)]
        d = P.merge(N, on=["date", "ticker"], how="inner")
        d["date"] = pd.to_datetime(d["date"])
        d = d[(d.date <= pd.Timestamp(asof)) & (d.nav > 0.5) & (d.close > 0.5)]
        if d.empty:
            if explicit:
                raise ValueError(
                    f"cef: panel_source {px_path} / {nav_path} holds no paired price and NAV "
                    f"above $0.50 for {sorted(uni)} on or before {pd.Timestamp(asof).date()}")
            return None
        px = d.pivot_table(index="date", columns="ticker", values="close")
        nav = d.pivot_table(index="date", columns="ticker", values="nav")
        vol = d.pivot_table(index="date", columns="ticker", values="volume")
        px, nav, vol = px.sort_index(), nav.sort_index(), vol.sort_index()
        return px, nav, vol, N

    def _discount_masks(self, N: pd.DataFrame, px: pd.DataFrame, vol: pd.DataFrame,
                        asof) -> dict | None:
        """{mask key: date x ticker bool}: the fund-days with NO DISCOUNT. None
        when neither `nav_repeat_mask` nor `zero_volume_mask` is on.

        WHAT A MASK DOES, AND WHAT IT DOES NOT (PREREG_C4_FAMILIES §4.3, and the
        harness's `band_frontier.build_panel(mask=)` that scored it). A masked
        fund-day's DISCOUNT is NaN: that day the fund is not eligible (its z is
        NaN), and the day does not count toward its z-window history (the
        rolling mean and sd count non-NaN rows, and the 120 minimum is a count
        of them). Its price, return, volume and ADV are untouched -- a masked
        day still trades and still earns -- and so is its NAV, so the
        `max_nav_age_bd` check reads the same NAV dates as before.

          M1, `nav_repeat_mask`: `_nav_repeat` on the NAV file's rows for the
              universe, whatever their price, then on the panel's paired
              fund-days. Every vendor stale copy is such a repeat; most repeats
              are NOT stale copies, and the trial accepted that cost in breadth
              (4.1-8.4% of eligible fund-days per era, §4.3) for a rule that
              needs no second source and acts the same in every year.
          M2, `zero_volume_mask`: volume exactly 0 on a paired fund-day. The
              trial measured none among eligible fund-days over 2005-2026; it
              is a guard.

        Each is built exactly as `scripts/cef/c4_families.py::declared_mask`
        builds it (the pivot with `aggfunc="max"`, `eq(True)`, `& paired`), so
        the C4 spec decides on the masks the trial was scored with.

        ALIGNMENT (H7). Both read date-t data only: t's volume, and t's NAV with
        the NAV row before it. The sleeve decides after t's close and t's NAV,
        which is why execution is shift(2). The NAV rows are cut at `asof`
        BEFORE the repeat is computed, so no later row can reach the flag; for
        every row at or before `asof` the flag equals the trial's, which
        computed it on the whole file (a diff only looks back). The check below
        refuses a mask that reaches past `asof` at all.
        """
        on = [k for k in CEF_MASK_KEYS if cef_mask_flag(self.frozen, k)]
        if not on:
            return None
        ts = pd.Timestamp(asof)
        paired = px.notna()
        out = {}
        if "nav_repeat_mask" in on:
            n = N[["date", "ticker", "nav"]].copy()
            n["date"] = pd.to_datetime(n["date"])
            n = n[n["date"] <= ts]
            n["repeat"] = _nav_repeat(n)
            rep = n.pivot_table(index="date", columns="ticker", values="repeat", aggfunc="max")
            out["nav_repeat_mask"] = (rep.reindex(index=paired.index, columns=paired.columns)
                                      .eq(True) & paired)
        if "zero_volume_mask" in on:
            out["zero_volume_mask"] = vol.reindex_like(paired).eq(0) & paired
        for k, m in out.items():
            if len(m.index) and m.index.max() > ts:
                raise AssertionError(f"cef {k}: mask dated {m.index.max().date()} is after the "
                                     f"decision date {ts.date()}; lookahead")
        return out

    def _thin_record(self, out: list, thin: dict, rec: dict, market_state) -> list:
        """`out`, each target with `meta["cef_thin"]` (THIN_META): te4's record.

        Called only under `below_min_names = "trade_eligible"` (`target_positions`
        routes every return through `done`, which is the identity otherwise).
        `rec` is filled at the `min_names` test, except `reduced`, which only the
        final return of the built book writes; a return before the test (no
        panel, a panel too short to score) records no eligible names, and no
        return but the last records a reduced build. Each target gets its own
        copy, so no two share a list."""
        info = {"eligible": [], "n": 0, "min_names": int(self._req("min_names")),
                "floor": thin["floor"], "holds": _hold_requested(market_state),
                "reduced": False, "stopped_by": None, **rec}
        return [dataclasses.replace(t, meta={**t.meta, THIN_META: {
                    **info, "eligible": list(info["eligible"])}}) for t in out]

    # ---- signal ------------------------------------------------------------
    def target_positions(self, asof, market_state: MarketState) -> list[PositionTarget]:
        # CEF TRIAL 55 (te4). `_thin_rule` runs first, so the paper-only refusal
        # precedes every read of the panel. Every return below goes through
        # `done`: the identity unless the key is "trade_eligible", when it adds
        # te4's record (`_thin_record`). The body stays in THIS function on
        # purpose: scripts/cef/c4_paper_benchmark.py's Probe reads `w` from this
        # frame where `min_abs_weight` is read, and refuses any other frame.
        thin = self._thin_rule(market_state)
        rec = {}
        if thin is None:
            done = lambda out: out                                       # noqa: E731
        else:
            done = lambda out: self._thin_record(out, thin, rec, market_state)  # noqa: E731
        panel = self._read_panel(asof)
        uni = self.instruments()
        # A DATA SHORTFALL NEVER FLATTENS A C4-STYLE BOOK (review of 11790b5).
        # With `panel_source` or `below_min_names = "hold"` set, a missing panel
        # or one too short to score RAISES, naming the shortfall: the first
        # means a broken data step, and flattening on it is the wrong answer to
        # a missed refresh (`_read_panel`); the second asked for the book to
        # hold rather than close when the cross-section is short, and a FLAT
        # book on a data gap is the very close it asked not to make. Reproduced
        # on the 13's last 150 sessions with hold on: held PDI +500 / HYT -800
        # came out FLAT "insufficient history". A raise is a missed day, which
        # the runner records. Both keys ABSENT: the FLAT returns below, as ever.
        # "trade_eligible" does not set `strict` (CEF trial 55, pre-registration
        # §1.3 item 4): a data shortfall under it flattens, as under "flatten".
        strict = (cef_panel_source(self.frozen) is not None
                  or self._below_min_names == "hold")
        if panel is None:
            if strict:
                raise ValueError(
                    f"cef: no paired price/NAV panel at {self.panel_paths()} on or before "
                    f"{pd.Timestamp(asof).date()}; refusing to flatten a book that sets "
                    f"panel_source or below_min_names='hold' on a missing panel")
            out = [PositionTarget(instrument=t, side=FLAT, kind=ETF,
                                  reason="cef: no price/NAV panel") for t in uni]
            if _hold_requested(market_state):
                out = _tag_short(out, {"eligible": [], "min_names": int(self._req("min_names")),
                                       "held_out": [], "excluded": {t: "no price/NAV panel"
                                                                    for t in uni}})
            return done(out)
        px, nav, vol, navrows = panel
        if len(px) < self._win + 20:
            if strict:
                raise ValueError(
                    f"cef: the panel at {self.panel_paths()} holds {len(px)} paired sessions "
                    f"through {pd.Timestamp(asof).date()}; the z-score needs z_window "
                    f"{self._win} + 20 = {self._win + 20}, {self._win + 20 - len(px)} short. "
                    f"Not deciding, and not flattening, on a panel too short to score")
            out = [PositionTarget(instrument=t, side=FLAT, kind=ETF,
                                  reason="cef: insufficient history") for t in uni]
            if _hold_requested(market_state):
                out = _tag_short(out, {"eligible": [], "min_names": int(self._req("min_names")),
                                       "held_out": [], "excluded": {t: "insufficient history"
                                                                    for t in uni}})
            return done(out)

        disc = 100.0 * (px - nav) / nav
        no_disc = self._discount_masks(navrows, px, vol, asof)
        if no_disc is not None:
            # M1 / M2 (`_discount_masks`): a masked fund-day has no discount, so
            # it is neither eligible today nor part of anyone's z-window
            # history. Applied BEFORE mu and sd, as `band_frontier.build_panel`
            # applies the trial's mask, and to the discount only. ABSENT (both
            # keys off) this block is skipped and `disc` is today's, untouched.
            m = None
            for k in CEF_MASK_KEYS:
                if k in no_disc:
                    m = no_disc[k] if m is None else (m | no_disc[k])
            disc = disc.mask(m.reindex(index=disc.index, columns=disc.columns, fill_value=False))
        mu = disc.rolling(self._win, min_periods=120).mean().shift(1)
        sd = disc.rolling(self._win, min_periods=120).std().shift(1)
        z = ((disc - mu) / sd.replace(0, np.nan)).clip(-4, 4)
        adv = (px * vol).rolling(63, min_periods=21).mean().shift(1)

        # REBALANCE CADENCE. The cross-sectional weights are refreshed only every
        # `rebalance_days` trading days; on the days in between we re-derive the
        # SAME weight vector from the last rebalance date and let the executor
        # trade nothing. This reproduces the backtest exactly, which builds
        # weights on `idx[::HOLD]` and forward-fills them
        # (`scripts/cef/validate.py`, W.ffill(limit=HOLD-1)).
        #
        # Anchoring to position-in-the-trading-day-index rather than to a stored
        # last-rebalance date keeps this stateless and reproducible: the same
        # asof always yields the same signal date, so a re-run or a replay cannot
        # silently trade a different book.
        #
        # Deriving the weights from the signal date instead of persisting them
        # matters for a second reason -- a persisted vector would go stale if the
        # panel were ever revised, and we would have no way to detect it.
        #
        # Audited 2026-07-31 (`results/AUDIT_2026-07-31.md`): before this gate the
        # sleeve had NO cadence control and recomputed every session, while the
        # frozen spec declared 5 days -- spec, code and optimum were three
        # different things. Measured net Sharpe under real (MOC, T+1) execution:
        # hold=1 0.62, hold=2 0.73, hold=5 0.51, hold=21 0.20.
        pos = len(z.index) - 1
        # A band and a calendar are two answers to the same question, and running
        # both would compound them: the calendar would freeze the signal for k
        # days and the band would then refuse to close the gap it had just let
        # open. Under a band the signal is recomputed every session; the band
        # alone decides whether anything trades.
        band_w = self._band_width
        sig_pos = pos if band_w is not None else pos - (pos % self._rebal_days)
        last = z.index[sig_pos]
        max_age = int(self._req("max_nav_age_bd"))
        hold = _nav_hold(market_state, last, uni)
        row, dropped, held_out = {}, [], []
        for tk in px.columns:
            zi = z.loc[last, tk]
            if tk in hold and not np.isfinite(px.loc[last, tk]):
                # HELD WITH NO PAIRED ROW ON THE DECISION DATE (2026-10-29): the
                # runner's missing-NAV hold (book json data.missing_nav,
                # quantt/session/gate.py `missing_nav_hold`) passes a name whose
                # NAV for this date never landed. Its z cannot be computed, so
                # whether it would have been eligible is unmeasured, and it is
                # counted in `held_out` as if it were: the `min_names` block below
                # then holds the whole book rather than let the hold be the cause
                # of a flatten. Unreachable before that hold existed: the
                # stale-NAV gate holds only names with a NAV dated D, and gate 5
                # refuses a name without a close dated D, so every name it held
                # had a paired row here and takes the unchanged path below.
                held_out.append(tk); continue
            if not np.isfinite(zi):
                # A masked name says why it is out, rather than reading "below
                # min weight" downstream. Only reachable with a mask key on.
                if no_disc is not None:
                    why = [k for k in CEF_MASK_KEYS if k in no_disc and bool(no_disc[k].loc[last, tk])]
                    if why:
                        dropped.append((tk, f"no discount today ({', '.join(why)})"))
                continue
            # ADV is NaN when fewer than 21 of the last 63 sessions have a price x
            # volume. That is liquidity UNMEASURED, not a pass: `float(nan or 0.0)`
            # is nan and `nan < floor` is False, so until 2026-10-11 such a name
            # skipped the floor silently (found by the plan-0.9 re-run; on the
            # 1998-11..2026-09-25 panel it never happened, so this is a no-op on
            # history). It is dropped, and the reason says so.
            a = float(adv.loc[last, tk])
            if not np.isfinite(a):
                dropped.append((tk, "ADV unmeasured (<21 of 63 sessions)")); continue
            if a < self._min_adv:
                dropped.append((tk, "illiquid")); continue
            # a NAV that has not moved is a blind signal, not a cheap fund
            nav_tk = nav[tk].dropna()
            if nav_tk.empty:
                dropped.append((tk, "no NAV")); continue
            age = len(pd.bdate_range(nav_tk.index[-1], last)) - 1
            if age > max_age:
                dropped.append((tk, f"NAV {age}bd stale")); continue
            # Last, so `held_out` counts only names that were otherwise eligible:
            # the runner could not verify this NAV (_nav_hold).
            if tk in hold:
                held_out.append(tk); continue
            row[tk] = float(zi)

        # ---- CEF TRIAL 55, te4: THE REDUCED BUILD -----------------------------
        # Under `below_min_names = "trade_eligible"` (paper only; `_thin_rule`)
        # a session with floor <= n < min_names eligible names and NO holds does
        # not enter the block below: it falls through to the construction that
        # follows, on `row`, unchanged. With any hold present the block runs
        # exactly as before, tag included (§10 Q10), and below the floor it
        # flattens, as before. A stop (K0 or gate 7, from the runner) sends a
        # session that would have built the reduced book into the flatten path,
        # and only such a session records `stopped_by`. `thin` None (every other
        # rule): `reduced` is False and nothing here runs. `reduced` steers the
        # branch from here, but the RECORD's `reduced` is written only at the
        # final return (below): a refusal on the way (the band's "sleeve NAV
        # unknown") is not the reduced build's targets.
        reduced, stop_note = False, ""
        if thin is not None:
            could = (len(row) < int(self._req("min_names")) and not hold
                     and len(row) >= thin["floor"])
            stop = thin["stop"]
            reduced = could and stop is None
            if could and stop is not None:
                stop_note = f" (reduced build stopped by {stop['by']}: {stop['why']})"
            rec.update(eligible=sorted(row), n=len(row), holds=bool(hold),
                       stopped_by=stop["by"] if (could and stop is not None) else None)

        if len(row) < int(self._req("min_names")) and not reduced:
            # WITH HOLDS, every return in this block is tagged (`_tag_short`,
            # release-check of 6d42f4f): the runner must know that no name was
            # decided on its signal. Without holds `tag` is the identity, so the
            # targets below are byte-identical to before.
            if hold:
                why_out = dict(dropped)
                short = {"eligible": sorted(row), "min_names": int(self._req("min_names")),
                         "held_out": sorted(held_out),
                         "excluded": {t: why_out.get(t, "held" if t in hold else
                                                     "no z-score on the signal date")
                                      for t in uni if t not in row}}
                tag = lambda out: _tag_short(out, short)      # noqa: E731
            else:
                tag = lambda out: out                          # noqa: E731
            # `below_min_names = "hold"` (trial C4's rule; ABSENT is "flatten",
            # the code below, unchanged). `build_targets` HOLDS the previous
            # target when fewer than `min_names` are eligible
            # (band_frontier.py, "hold; nothing eligible"), and C4 was scored
            # that way (PREREG_C4 §4.2). The pre-registration's declared book
            # (shortable, masked) had fewer than 6 eligible on 10.5% of fit
            # sessions and 5.3% in 2023-26 (§11.1, `c4_feasibility.py`, measured
            # 2026-10-13, before the amendment froze the 74), and a rule that closes
            # the whole book on each such day and reopens it on the next would
            # trade round trips the trial never paid. Live, the
            # reference state is what the account HOLDS, not a stored target
            # (PREREG_C4 §3 item 6), so "hold" is: every name keeps its current
            # shares (`_held_target`: a qty target, so decide sends nothing),
            # and an unheld name stays unopened. The band and the gross cap do
            # not run: nothing is resized. Holds from the stale-NAV gate are
            # subsumed -- the whole book is held -- and named in the reason.
            #
            # DECLARED DIVERGENCE FROM THE TRIAL (review of 11790b5; listed for
            # step 2's fidelity test in C4_DEPLOY_PLAN_2026-10-27.md §2): WHILE
            # `hold` LASTS, `max_gross_stress` IS EFFECTIVELY OFF. Live, the book
            # is held in SHARES, so its gross moves with prices, and price drift
            # over a run of short days can leave it above the cap (1.8x in v7)
            # with nothing here trimming it. The trial holds a TARGET in weight
            # space and `band_gross_capped` re-applies the cap to the held book
            # every day, so it never sits above the cap. The cap acts again on
            # the first day the cross-section is back at `min_names` (the band,
            # then `_cap_gross`, on the book as held). Accepted: trimming a held
            # book for margin would be a resize on a day the rule says hold.
            if self._below_min_names == "hold":
                n_min = int(self._req("min_names"))
                why = (f"book holds: only {len(row)} eligible names, under min_names {n_min} "
                       f"(below_min_names=hold)")
                if held_out:
                    why += f"; NAV unverified for {sorted(held_out)}"
                order_type = str(self._req("order_type")).upper()
                return done(tag([_held_target(t, market_state, why, order_type) for t in uni]))
            if not hold:
                return done([PositionTarget(instrument=t, side=FLAT, kind=ETF,
                                            reason=f"cef: only {len(row)} eligible names{stop_note}")
                             for t in uni])
            order_type = str(self._req("order_type")).upper()
            if len(row) + len(held_out) >= int(self._req("min_names")):
                # Short of min_names only because of the gate's holds: the whole
                # book holds for the day. Holds never trigger the flatten (_nav_hold).
                why = (f"book holds: NAV unverified for {sorted(held_out)} leaves "
                       f"{len(row)} eligible names")
                return done(tag([_held_target(t, market_state, why, order_type) for t in uni]))
            # Short of min_names without the holds: today's rule for every name
            # but the held ones, which keep their shares.
            return done(tag([_held_target(t, market_state, f"NAV unverified: {hold[t]}", order_type)
                             if t in hold else
                             PositionTarget(instrument=t, side=FLAT, kind=ETF,
                                            reason=f"cef: only {len(row)} eligible names")
                             for t in uni]))

        s = pd.Series(row)
        w = -(s - s.mean())                       # cheap -> long, rich -> short
        w = w / w.abs().sum()
        if reduced and not np.isfinite(w.to_numpy(dtype=float)).all():
            # NO SILENT 0/0 ON THE REDUCED PATH (CEF trial 55, pre-registration
            # §1.3 new piece 1). Every eligible z equal makes z - mean(z) zero
            # and the weights 0/0 (on 2020-03-18 and 2025-04-07 every eligible z
            # sat at the -4 clip: band_frontier._check_thin_matches_T). A full session's path is not changed
            # here (it holds silently; PR #33 §5.H, the owner's question); the
            # reduced path refuses: a raise is a missed day, which the runner
            # records, and the book stays as it is in shares.
            raise ValueError(
                f"cef: below_min_names='trade_eligible' reduced build on {last.date()} "
                f"(as of {pd.Timestamp(asof).date()}): the weights on {sorted(row)} are not "
                f"finite (z {dict(sorted(row.items()))}): every eligible z is equal, so the "
                f"book is 0/0. Nothing decided")

        if not np.isfinite(w.to_numpy(dtype=float)).all():
            # EVERY ELIGIBLE Z EQUAL ON A FULL SESSION: THE BOOK HOLDS, AND SAYS SO
            # (team lead, 2026-11-19: "Hold, but say so"; PR #33 section 5.H's open
            # question, answered). z - mean(z) is then zero for every name and the
            # weights are 0/0. It has happened: on 2020-03-18 and 2025-04-07 every
            # eligible z sat at the -4 clip. Until this block the NaN weights ran on:
            # the trailing vol of a NaN book read 0.0, the scalar fell back to 1.0,
            # every band comparison against NaN was False, and the book held its
            # shares with reasons that read like an ordinary band hold. The outcome
            # is kept (every name keeps its current shares, an unheld name stays
            # unopened, nothing is sent) and is now written down: a qty target per
            # held name, as `below_min_names = "hold"` builds, with this reason. A
            # flat book on such a day opens nothing, where the old path handed NaN
            # weights to the opening session. The reduced (te4) path above still
            # refuses instead: its pre-registration says a raise there is a missed
            # day. Any OTHER non-finite weight is not this case and raises.
            zs = sorted(set(row.values()))
            if len(zs) != 1:
                raise ValueError(
                    f"cef: the weights on {sorted(row)} for {last.date()} (as of "
                    f"{pd.Timestamp(asof).date()}) are not finite although the eligible z are "
                    f"not all equal (z {dict(sorted(row.items()))}). Nothing decided")
            why = (f"book holds: every eligible z is equal ({zs[0]:+.2f} on {len(row)} names, "
                   f"{last.date()}), so the weights are 0/0")
            order_type = str(self._req("order_type")).upper()
            # No `tag`: that marks a short-of-min_names session for the runner's
            # missing-NAV refusal, and this is a full session.
            return done([_held_target(t, market_state, why, order_type) for t in uni])

        # constant-risk sizing off the sleeve's own trailing realised vol
        ret = px.pct_change(fill_method=None).where(lambda x: x.abs() < 0.5)
        level = self._level_signal
        level_vols = None
        if level is None:
            # THE Z BOOK'S OWN VOL, AND ITS SCALAR. NO SILENT FALLBACK (team lead,
            # 2026-11-19, after the review of release-20261116-1). Until then a
            # trailing vol that was zero or not a number sized the book at scalar
            # 1.0: `... if rv > 0 else 1.0`. That is an invented size on a day the
            # estimator has nothing to say (63 sessions of returns that are all
            # missing, or a book whose past P&L never moved). The one case in which
            # it is known to have fired, a 0/0 book on a day every eligible z is
            # equal, is the explicit hold just above and never reaches this line. The level-signal path below has always raised
            # for the same condition (`_blend_unit_book`); now both do, naming the
            # date and the names. On every day the vol is a positive number the
            # scalar is the expression it has always been, so those plans are
            # unchanged byte for byte (src/deploy/tests/test_vol_scalar_no_fallback.py
            # compares them with the old expression on the generated panel).
            # DECLARED DIVERGENCE FROM THE HARNESS: `band_frontier.build_targets`
            # keeps its `else 1.0`, because a backtest's first sessions have no
            # 63-day history and it must return a number for them; live, the
            # sleeve's warmup means that case is a data fault, never a start-up.
            rv = _book_vol(ret, w)
            if not (np.isfinite(rv) and rv > 0):
                raise ValueError(
                    f"cef: the z book's trailing realised vol on {last.date()} (as of "
                    f"{pd.Timestamp(asof).date()}) is {rv!r} over the last 63 sessions of returns "
                    f"for {sorted(w.index)}; the vol scalar is vol_target_annual / that vol and "
                    f"has no value. Nothing decided")
            scal = float(np.clip(self._vol_target / rv, 0.2, 2.5))
        else:
            # ---- LEVEL SIGNAL (CEF trial 54; module docstring, steps 2-4) --------
            # ALIGNMENT (H7). Everything below is read from the date-t panel, t =
            # `last`, the signal date: w_z from t's z (t's discount against a mean
            # and sd that end at t-1, the shift(1) above); w_L from t's masked
            # discount of the same eligible names; s_z, s_L and s_mix from today's
            # weights on price returns r_s = px_s / px_{s-1} - 1 for the 63
            # sessions s <= t, each known at s's close. The sleeve decides after
            # t's close and t's NAV, so the book earns from t+2 (shift(2)). The
            # registry requires `band_width` with this key, so the signal date is
            # the last paired session and the returns end exactly there; the two
            # checks below refuse anything else, including any row after t.
            if not (ret.index[-1] == last and last <= pd.Timestamp(asof)):
                raise AssertionError(
                    f"cef level_signal: returns end {ret.index[-1].date()}, signal date "
                    f"{last.date()}, decision {pd.Timestamp(asof).date()}; the blend reads "
                    f"returns through the signal date only (lookahead or a stale signal)")
            if disc.index.max() > last:
                raise AssertionError(f"cef level_signal: discount dated {disc.index.max().date()} "
                                     f"is after the signal date {last.date()}; lookahead")
            w_L = _level_weights(disc.loc[last, list(row)], level["family_of"])
            w, level_vols = _blend_unit_book(w, w_L, ret, level["risk_share"])
            rv = level_vols["s_mix"]
            # ONE vol scalar, the existing one (clip bounds and all), on the blend's
            # own vol: target = mix x clip(vol_target_annual / s_mix, 0.2, 2.5).
            scal = float(np.clip(self._vol_target / rv, 0.2, 2.5))
        w = w * scal * float(self._req("gross_leverage"))

        # Drop sub-threshold names FIRST, then re-neutralise and re-normalise on
        # the survivors. Filtering after neutralising leaves a small net
        # directional position -- the first dry run came out 0.37% net short --
        # which is exactly the credit beta this book exists to avoid carrying.
        minw = float(self._req("min_abs_weight"))
        keep = w[w.abs() >= minw]
        # DELIBERATELY `min_names`, NOT the te4 floor (CEF trial 55, §10 Q12):
        # a reduced set (n < min_names) is therefore never re-neutralised, and
        # a name under `min_abs_weight` is flattened by the dust filter at the
        # output, leaving a residual under that weight. Re-neutralising a 3-name
        # survivor set would recreate the degeneracy the floor excludes, and two
        # thresholds in one block would be a second rule.
        if len(keep) >= int(self._req("min_names")):
            keep = keep - keep.mean()
            denom = keep.abs().sum()
            if denom > 0:
                w = keep / denom * scal * float(
                    self._req("gross_leverage"))

        # ---- GROUP CAP (muni minus taxable) ---------------------------------
        # Applied HERE, to the FINAL target -- after normalisation, after the
        # vol scalar, after the min-weight re-neutralisation -- and BEFORE the
        # band. Two reasons, both load-bearing:
        #
        #  (1) k is DEFINED on the final target. The 0.30 was derived as the
        #      median |net group weight| the live book ran on its own targets
        #      over the traded era before 2023 (0.304953), which is the same
        #      object whose net group weight 05_verify measured at -1.24 over
        #      the last 12 months. Capping an intermediate vector would cap a
        #      different quantity wearing the same name.
        #  (2) It reproduces the scored construction. The research applied
        #      `soft_cap` to the target frame and then `band(.)`; anything else
        #      is not the thing that was measured.
        #
        # The cap is deliberately NOT followed by a re-normalisation: that would
        # undo it. The small change in gross is a consequence, is reported
        # rather than hidden, and is in the direction that helps (mean traded
        # gross 1.44x -> 1.23x).
        #
        # ADOPTION, NOT A NEW SEARCH. GN-N2 (the nextgen branch's shadow "CEF
        # trial 55", not this repository's trial 55, te4: see `_group_cap`) is
        # already spent on this operator and this k. What is claimed is risk
        # and breadth, not return: the paired return difference is
        # statistically zero on every window, including -1.13 %/yr (t -1.67) on
        # the only window that is out of sample for k. See
        # results/cef/PREREG_GROUP_CAP_2026-09-16.md.
        group_cap = self._group_cap
        gcap_bound = False
        if group_cap is not None:
            w, gcap_bound = _cap_net_group_weight(w, self._groups(), group_cap)

        # ---- NO-TRADE BAND ---------------------------------------------------
        # Applied HERE and not earlier: the min-weight block above re-neutralises
        # and re-normalises to unit gross, which would silently undo the band.
        #
        # Policy (Constantinides 1986; Davis & Norman 1990): hold unless a name
        # is more than `band_width` from target, then trade back to the BAND
        # EDGE, not to target. Measured over 5,452 sessions the band dominates
        # the rebalance calendar at every width tested AND at matched turnover
        # -- net Sharpe 0.33 -> 0.66 at 15bp on 43% less trading -- because a
        # calendar's information loss compounds with its interval while a band
        # only ever discards small moves. See docs/PLAN.md Part 2.
        #
        # THE COMPARISON IS AGAINST WHAT WE ACTUALLY HOLD, not against a stored
        # previous target. That is the deliberate difference from the backtest,
        # which has no failed fills. It makes the policy self-correcting: if a
        # session does not arm, or an order does not fill, the real position
        # simply sits further from target and the band closes it on a later day
        # rather than the sleeve believing in a book it never got.
        #
        # ---- OPENING SESSION: FULL TARGET, BAND SKIPPED ----------------------
        # Decision (team lead, 2026-09-28, docs/RUNNER.md "Day one (flat
        # book)"): the FIRST session of a book trades to FULL TARGET, not to the
        # band edge; the band applies from the second session on.
        #
        # WHY. From a flat book the band trades every name only to its EDGE,
        # i.e. target minus `band_width` toward zero, and names whose target is
        # inside the band not at all. The edge-shrink is not symmetric across
        # the long and short sides, so the opening book is NOT dollar-neutral:
        # measured on the last three panel dates at the time of the decision,
        # net -0.05 to -0.10 of NAV (docs/RUNNER.md 4.2; v6 on 17 names did the
        # same). A dollar-neutral book that opens 5-10% net short carries
        # exactly the credit beta it exists to avoid, and only drifts back as
        # the band happens to trade. Trading to target once removes that.
        #
        # WHERE. The switch replaces ONLY the band: every name goes to its full
        # target `w` as it stands here -- after normalisation, the vol scalar,
        # the min-weight re-neutralisation and the group cap -- and the gross /
        # margin cap below STILL applies, because margin is charged on the
        # opening book like any other.
        #
        # WHO SAYS IT IS THE OPENING SESSION. The runner, through
        # `MarketState.extras["opening_session"]`. The sleeve does not infer it
        # from empty holdings: a flat book is also what a failed day, a
        # manual flatten or a broker read that came back empty looks like, and
        # silently re-targeting in those cases would move the policy on a
        # guess. Conversely a runner that sets the flag against a LIVE book has
        # a bug -- full-target trading of a held book discards the band's
        # entire cost saving and churns every name -- so that RAISES rather
        # than trades.
        #
        # THE VALUE MUST BE EXACTLY `True` or `False`. Absent or False is the
        # unchanged path, byte-for-byte (proved by
        # `src/deploy/tests/test_opening_session.py`). Anything else -- 1,
        # "true", None, a numpy bool -- raises: a flag that decides whether the
        # band exists must not be decided by Python truthiness.
        extras = getattr(market_state, "extras", None) or {}
        opening = extras.get("opening_session", False)
        if opening is not True and opening is not False:
            raise TypeError(
                f"cef: extras['opening_session'] must be exactly True or False, "
                f"got {opening!r} ({type(opening).__name__}); refusing to decide "
                f"whether the band applies from a truthy value")
        if opening:
            holds0 = getattr(market_state, "holdings", None) or {}
            live = []
            for k, v in holds0.items():
                try:
                    q0 = float(v)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"cef: opening_session=True but holding {k!r} has "
                        f"quantity {v!r}; cannot prove the book is flat") from exc
                if q0 != 0.0:            # NaN != 0.0 too: unmeasurable is not flat
                    live.append(str(k))
            live.sort()
            if live:
                raise ValueError(
                    f"cef: opening_session=True but the book already holds "
                    f"{live}. The opening session trades a FLAT book to full "
                    f"target; re-targeting a live book past its band is a "
                    f"runner bug, not a policy. Nothing decided.")

        band_w = self._band_width
        band_note = {}
        held_q = {}          # ticker -> signed held qty, for the HOLD targets below
        # SIZING MULTIPLIER (module docstring). None is today's code: every line
        # that reads `m_size` below takes its unchanged branch, and the band's
        # denominator `nav_unit` is then `nav_now` itself.
        m_size = self._sizing_multiplier
        if band_w is not None and opening:
            # The book is flat (checked above), so there is no HOLD to express
            # and `held_q` stays empty; `w` passes through untouched. The NAV
            # check is kept on this path too: the runner sizes these weights
            # against the same `sleeve_nav`, and an unknown NAV must refuse on
            # day one exactly as it refuses on every other day.
            nav_now = float(extras.get("sleeve_nav", 0.0))
            if nav_now <= 0:
                return done([PositionTarget(instrument=t, side=FLAT, kind=ETF,
                                            reason="cef: band on but sleeve NAV unknown")
                             for t in uni])
        elif band_w is not None:
            nav_now = float((getattr(market_state, "extras", None) or {})
                            .get("sleeve_nav", 0.0))
            if nav_now <= 0:
                # No denominator, no band. Refusing is correct: sizing the band
                # off a guessed NAV would move real money on an invented number.
                return done([PositionTarget(instrument=t, side=FLAT, kind=ETF,
                                            reason="cef: band on but sleeve NAV unknown")
                             for t in uni])
            holds = getattr(market_state, "holdings", None) or {}
            held_w = {}
            # With m set, what the account holds is m x the unit book, so the band
            # reads it back in unit weights: held / (nav x m).
            nav_unit = nav_now if m_size is None else nav_now * m_size
            for tk in uni:
                if tk in hold:          # fixed shares: never banded (_nav_hold)
                    continue
                q = float(holds.get(tk, 0.0) or 0.0)
                pr = float(px[tk].iloc[-1]) if tk in px.columns else float("nan")
                if q and np.isfinite(pr) and pr > 0:
                    held_w[tk] = q * pr / nav_unit
                    held_q[tk] = q
            banded = {}
            for tk in set(w.index) | set(held_w):
                tgt = float(w.get(tk, 0.0))
                cur = float(held_w.get(tk, 0.0))
                gap = tgt - cur
                if abs(gap) > band_w:
                    banded[tk] = tgt - math.copysign(band_w, gap)   # to the EDGE
                    band_note[tk] = "trade"
                else:
                    banded[tk] = cur                                # leave alone
                    band_note[tk] = "hold"
            w = pd.Series(banded)

        # ---- GROSS / MARGIN CAP ----------------------------------------------
        # Applied AFTER the band, because the band is what decides what the book
        # will actually HOLD, and margin is charged on what is held, not on what
        # was wanted. A cap applied to the target would let the band carry a
        # stale position over the line and report itself compliant.
        #
        # THE BAND'S HOLDS BECOME TRADES WHEN THIS BINDS, and that is correct
        # rather than a regression of the 2026-09-08 dust fix. A HOLD is
        # expressed in shares precisely because "leave it alone" must cost
        # nothing; when the margin cap binds we are NOT leaving the book alone,
        # we are reducing it, so every line is a genuine order and belongs in
        # weight space where the executor sizes it against the close it trades
        # on. `rebalance.min_trade_usd` ($517) still drops the resize orders too
        # small to be worth sending, which is what keeps a hairline breach from
        # churning the whole book.
        #
        # This can only ever REDUCE exposure (f in (0,1) when it binds, and
        # exactly 1.0 otherwise). Nothing here levers the book up to the cap;
        # that is a different construction with its own evidence and its own
        # trial (`ng/05_research_no_borrow_rescore.md` §6.3 book (b)).
        gross_cap = self._max_gross_stress
        gross_scal = 1.0
        if gross_cap is not None:
            # In unit weights the account's cap is cap / m: m x the capped unit book
            # is then at most `max_gross_stress` x the account's NAV.
            w, gross_scal = _cap_gross(w, gross_cap if m_size is None else gross_cap / m_size)
            if gross_scal != 1.0:
                band_note = {tk: "trade" for tk in band_note}

        # Provenance tag on every reason string, and EMPTY when neither cap is
        # configured -- which is what keeps the code change a byte-for-byte
        # no-op with the keys absent.
        cap_tag = ""
        if group_cap is not None:
            cap_tag += f" gcap={group_cap:.4f}{'*' if gcap_bound else ''}"
        if gross_cap is not None:
            cap_tag += f" gmax={gross_cap:.4f}"
            if gross_scal != 1.0:
                cap_tag += f"*x{gross_scal:.4f}"
        # The multiplier is named in every reason when it changes the book; at
        # exactly 1.0 (and absent) the reasons are today's.
        if m_size is not None and m_size != 1.0:
            cap_tag += f" smult={m_size:.4f}"
        # The level blend names itself, and the two vols it equalised, in every
        # reason of a decide it shaped. Absent, the reasons are today's.
        if level_vols is not None:
            cap_tag += (f" level z_share={level['risk_share']:.4f}"
                        f" s_z={level_vols['s_z']:.4f} s_L={level_vols['s_L']:.4f}")
        # Opening-session targets say so in the log. Appended only when the
        # flag is True, so absent/False reasons are unchanged byte-for-byte.
        if opening:
            cap_tag += " opening-session: full target, band skipped"
        # te4's reduced build says so in every reason; appended only when it ran.
        if reduced:
            cap_tag += f" reduced-set n={len(row)}/{int(self._req('min_names'))}"

        out = []
        for tk in uni:
            if tk in hold:
                out.append(_held_target(tk, market_state, f"NAV unverified: {hold[tk]}",
                                        str(self._req("order_type")).upper()))
                continue
            wt = float(w.get(tk, 0.0))
            # A banded HOLD must survive the min-weight filter, or a small held
            # position would be flattened by the very rule that decided not to
            # trade it -- turning "leave it alone" into "sell all of it".
            #
            # A HOLD IS EXPRESSED IN SHARES, NOT IN WEIGHT (fixed 2026-09-08,
            # results/cef/DUST_ORDERS_2026-09.md). "Leave it alone" is a
            # statement about the position, and only a share count says it
            # exactly. Emitting the held WEIGHT instead sent the decision on a
            # round trip through two different prices: the band computes
            # cur = q * px[-1] / nav from the last close in the SIGNAL panel,
            # and the executor converts that weight back with
            # floor(nav * |w| / price) using the close it reads on the SIZING
            # date -- routinely one session newer, because price and NAV are
            # inner-joined and a fund's NAV publishes later than its close.
            # Different price, different floor, and a name the band told us to
            # leave alone emitted a few shares of rounding drift as a live MOC
            # order. Measured on the 2026-09-03 signal sized off the 09-04
            # close: 12 orders, $3,019 gross, ~$15/session in commission and
            # half-spread = ~0.75%/yr of a $500k book against a policy whose
            # whole expectation is ~2.3%/yr -- and every one of them counted as
            # turnover against the band's pre-registered primary readout.
            #
            # Expressed as qty the executor's diff is EXACTLY zero whatever
            # close it sizes on (`_resolve_qty` / `_target_shares_for` return a
            # qty target unchanged, never touching a price), which is the only
            # tolerance that is honest here: any tolerance in shares would be a
            # threshold below which we still trade.
            if band_note.get(tk) == "hold" and wt != 0.0:
                q = float(held_q.get(tk, 0.0))
                if q == 0.0:
                    # Cannot happen: wt != 0 for a HOLD means banded[tk] = cur =
                    # q*pr/nav_now was non-zero, so q was non-zero. Raise rather
                    # than emit a zero qty, which the executor would read as
                    # "sell the whole position" -- the exact opposite of a hold.
                    raise ValueError(
                        f"cef band HOLD for {tk} carries weight {wt:+.6f} but no "
                        f"held quantity; refusing to emit a zero-qty target")
                out.append(PositionTarget(
                    instrument=tk, side=LONG if q > 0 else SHORT, kind=ETF,
                    qty=q,
                    meta={"order_type": str(
                        self._req("order_type")).upper()},
                    reason=f"cef band hold: |gap|<={band_w:.4f} w={wt:+.4f}"
                           f"{cap_tag}"))
                continue
            # KNOWN INTERACTION, band mode: if the band EDGE lands inside
            # min_abs_weight the dust filter flattens the name instead, which
            # trades slightly more than the band asked for and lands outside the
            # band. The window is narrow (|edge| < min_abs_weight) and going flat
            # rather than holding a few hundred dollars of a $4 fund is the
            # behaviour we want, so the filter deliberately wins. Worth knowing
            # that it is a small, bounded divergence from the backtested policy,
            # which models no minimum weight at all.
            if abs(wt) < minw:
                why = dict(dropped).get(tk, "below min weight")
                out.append(PositionTarget(instrument=tk, side=FLAT, kind=ETF,
                                          reason=f"cef: {why}{cap_tag}"))
                continue
            wt_out = wt if m_size is None else wt * m_size     # the account's weight
            out.append(PositionTarget(
                instrument=tk, side=LONG if wt > 0 else SHORT, kind=ETF,
                weight=wt_out,
                # The signal is only computable after the close (the fund's NAV
                # does not exist until then), so this sleeve necessarily decides
                # in the evening. A plain market order would then rest overnight
                # and fill at the next open -- the worst liquidity of the day in
                # instruments trading $3-45m. MOC executes in the closing
                # auction instead, which is what the research measured.
                meta={"order_type": str(
                    self._req("order_type")).upper()},
                reason=f"cef discount z={row.get(tk, float('nan')):+.2f} "
                       f"w={wt_out:+.4f} volscal={scal:.2f}{cap_tag}"))
        # te4's record says `reduced` HERE, on the one return the reduced build
        # produces, and nowhere earlier (review of f1d9f62): set at the min_names
        # test, it read True on the band's "sleeve NAV unknown" FLAT refusals
        # above, and the pre-registration counts a reduced decision by this flag
        # (§4.2). Any return between the min_names test and this line keeps
        # `_thin_record`'s False.
        rec["reduced"] = reduced
        return done(out)

    # ---- risk --------------------------------------------------------------
    def risk_check(self, ledger_view) -> RiskVerdict:
        """OBSERVE-ONLY. This sleeve is never auto-killed or auto-halved.

        Standing instruction (2026-07-31): the paper deployment exists to
        GENERATE DATA, and a sleeve that suspends itself stops producing the
        very evidence we deployed it to collect. There is no real capital at
        risk, so the usual reason to cut a losing book does not apply.

        Drawdown is therefore reported loudly and acted on by a human, not by
        this function. The thresholds below are retained purely as labels on
        the message so the severity is still visible in the daily log.
        """
        try:
            dd = float(getattr(ledger_view, "drawdown", 0.0) or 0.0)
        except Exception:
            return RiskVerdict(OK, ["ledger drawdown unreadable; no action"])
        note = "backtested worst was -12.0%"
        if abs(dd) >= 0.18:
            return RiskVerdict(OK, [
                f"WATCH: CEF drawdown {dd:.1%} is past the -18% level that would "
                f"once have stopped it ({note}). Observe-only mode: NOT halted, "
                f"continuing to collect data. Human review warranted."])
        if abs(dd) >= 0.12:
            return RiskVerdict(OK, [
                f"WATCH: CEF drawdown {dd:.1%} past -12% ({note}). "
                f"Observe-only: NOT halted."])
        return RiskVerdict(OK, [f"CEF sleeve drawdown {dd:.1%}"])
