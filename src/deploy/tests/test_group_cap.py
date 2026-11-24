"""The two v7 constraints: `group_cap` and `max_gross_stress`.

WHY THESE FIVE TESTS AND NOT OTHERS. The house rule is a test with any change to
the live path, and the useful ones are the ones that would have caught a real
class of defect in this repo:

  1. THE NO-OP.  `band_width` was activated on the promise that the code change
     alone did nothing, and that promise was verified by diffing sleeve output.
     Two new keys make the same promise. A no-op that is asserted and not tested
     rots the first time someone edits the block above it -- so this pins that
     the keys ABSENT and the keys PRESENT-BUT-NULL produce byte-identical
     targets, reasons included.
  2. THE CAP BINDS.  A constraint that silently never fires is worse than none:
     it reads as protection in every document and provides none. This builds a
     book whose net group weight is far outside k and requires that it comes
     back to exactly k, dollar-neutrally, with no name dropped.
  3. SCALING, NOT FLATTENING.  The failure mode a margin rule invites is
     "reduce" implemented as "get out". This requires the gross cap to land on
     the cap exactly, keep every name, keep every sign, and keep every RATIO
     between names.
  4. GROUPS COME FROM THE SPEC UNIVERSE'S STATED MANDATE, read from the panel's
     `grp` column -- not from returns, not from a hard-coded list in the sleeve.
     A grouping fitted to returns would be fitted to the thing being
     neutralised. This pins that relabelling a name in the panel moves which
     side of the cap it sits on.
  5. REFUSAL.  NO SILENT FALLBACKS. A missing `grp` must raise naming the
     names, not default them to one side. A defaulted mandate puts a name on
     the wrong side of the very constraint being applied and nothing downstream
     notices.

Synthetic panel throughout, in the house style of `test_band_hold_dust.py`: the
mechanism must be provably correct on toy inputs, independent of whatever the
live parquet happens to hold today. The ONE place the real numbers are checked
is `ng/store/deploy/gc_score.py`, which asserts the sleeve reproduces GN-N2's
published table on the pinned snapshot before it will print anything.
"""

import math

import numpy as np
import pandas as pd
import pytest

from src.deploy.sleeve import FLAT, SHORT, MarketState
from src.deploy.sleeves import cef_discount as cefmod
from src.deploy.sleeves.cef_discount import CEFDiscountSleeve

# Six "muni" and six "taxable" names, so neither side is a singleton and the
# dollar-neutral shift always exists.
MUNI = ["MUN1", "MUN2", "MUN3", "MUN4", "MUN5", "MUN6"]
TAX = ["TAX1", "TAX2", "TAX3", "TAX4", "TAX5", "TAX6"]
TICKERS = MUNI + TAX
GRP = {**{t: "muni" for t in MUNI}, **{t: "multi" for t in TAX}}
NAV_USD = 500_000.0
BAND = 0.048


def _spec(group_cap="omit", max_gross_stress="omit", band=True):
    """A CEF spec with the deployed knobs. "omit" means the key is ABSENT.

    `rebalance_days` is 1 so a band-off run signals on the same date as a
    band-on run, exactly as `test_band_hold_dust._spec` does.
    """
    spec = {
        "capital_usd": NAV_USD,
        "allocation": {"type": "cef_discount"},
        "rebalance": {"min_trade_usd": 0.0},
        "frozen": {
            "universe": list(TICKERS),
            "z_window": 252,
            "rebalance_days": 1,
            "vol_target_annual": 0.06,
            "min_adv_usd": 3_000_000.0,
            "max_nav_age_bd": 3,
            "min_names": 6,
            "min_abs_weight": 0.005,
            "gross_leverage": 1.0,
            "order_type": "MOC",
        },
        "risk": {},
    }
    if band:
        spec["frozen"]["band_width"] = BAND
    if group_cap != "omit":
        spec["frozen"]["group_cap"] = group_cap
    if max_gross_stress != "omit":
        spec["frozen"]["max_gross_stress"] = max_gross_stress
    return spec


def _write_panel(tmp_path, monkeypatch, grp=None, drop_grp_for=()):
    """A price/NAV panel deep enough for a 252-day z-score, with a `grp` column.

    The discounts are given DELIBERATELY GROUPED levels -- the munis all sit
    cheap and the taxables all sit rich -- so the cross-sectional demeaning
    leaves a large net muni-minus-taxable weight and the group cap has
    something real to bite on. A panel with no group structure would let every
    one of these tests pass vacuously.
    """
    grp = dict(GRP if grp is None else grp)
    rng = np.random.default_rng(20260916)
    dates = pd.bdate_range("2024-09-02", periods=330)
    px_rows, nav_rows = [], []
    for i, tk in enumerate(TICKERS):
        nav = 10.0 + np.cumsum(rng.normal(0.0, 0.02, len(dates)))
        # munis drift CHEAP, taxables drift RICH, each around its own level
        level = (-0.06 + 0.004 * i) if tk in MUNI else (0.05 + 0.004 * i)
        d = np.zeros(len(dates))
        d[0] = level
        for t in range(1, len(dates)):
            d[t] = 0.97 * d[t - 1] + 0.03 * level + rng.normal(0, 0.004)
        # the last 40 sessions walk one way, so today's z-scores are grouped
        d[-40:] += np.linspace(0, -0.03 if tk in MUNI else 0.03, 40)
        close = nav * (1.0 + d)
        for dt, c, n in zip(dates, close, nav):
            row = {"date": dt, "ticker": tk, "close": float(c),
                   "volume": 1_000_000.0}
            if tk not in drop_grp_for:
                row["grp"] = grp[tk]
            else:
                row["grp"] = None
            px_rows.append(row)
            nav_rows.append({"date": dt, "ticker": tk, "nav": float(n)})
    px_path = tmp_path / "px.parquet"
    nav_path = tmp_path / "nav.parquet"
    pd.DataFrame(px_rows).to_parquet(px_path)
    pd.DataFrame(nav_rows).to_parquet(nav_path)
    monkeypatch.setattr(cefmod, "PX_PATH", px_path)
    monkeypatch.setattr(cefmod, "NAV_PATH", nav_path)
    monkeypatch.setattr(cefmod, "GRP_PATH", px_path)
    return str(dates[-1].date()), {r["ticker"]: r["close"] for r in px_rows
                                   if r["date"] == dates[-1]}


@pytest.fixture
def panel(tmp_path, monkeypatch):
    return _write_panel(tmp_path, monkeypatch)


def _targets(spec, asof, holdings=None):
    sl = CEFDiscountSleeve(spec, NAV_USD)
    ms = MarketState(asof=asof, prices=pd.DataFrame(),
                     holdings=dict(holdings or {}),
                     extras={"sleeve_nav": NAV_USD})
    return sl.target_positions(asof, ms)


def _signed(targets):
    """ticker -> signed weight, for weight-expressed targets only."""
    out = {}
    for t in targets:
        if t.side == FLAT or t.weight is None:
            continue
        out[t.instrument] = float(t.weight)
    return out


def _fingerprint(targets):
    """The byte-for-byte record of one session's book -- reasons included.

    `repr` on the floats, not a format string: a formatted float would hide a
    difference in the 16th digit, and 16th-digit differences are exactly what
    this repo has been bitten by.
    """
    return "\n".join(
        "|".join([t.instrument, t.side, t.kind,
                  "None" if t.qty is None else repr(float(t.qty)),
                  "None" if t.weight is None else repr(float(t.weight)),
                  t.reason, str(t.combo_id), repr(sorted(t.meta.items()))])
        for t in targets)


def _held_book(asof, signal_close, spec):
    """The share book the frictionless weights imply at the signal close.

    Sized exactly as the executor sizes a weight target
    (`floor(nav*|w|/price)`, `ibkr._resolve_qty`), so the band sees a realistic
    position and its HOLD branch fires.
    """
    held = {}
    for pt in _targets(spec, asof, {}):
        if pt.weight is None or pt.weight == 0.0:
            continue
        mag = math.floor(NAV_USD * abs(float(pt.weight)) / signal_close[pt.instrument])
        if mag:
            held[pt.instrument] = float(-mag if pt.side == SHORT else mag)
    return held


def _net_group(weights):
    return sum(w for t, w in weights.items() if t in MUNI) - \
        sum(w for t, w in weights.items() if t in TAX)


# ---------------------------------------------------------------------------
# 1. the no-op: keys ABSENT and keys PRESENT-BUT-NULL are byte-identical
# ---------------------------------------------------------------------------

def test_absent_and_null_are_byte_identical(panel):
    """A new frozen-spec key must default to current behaviour (/spec-change).

    Both the flat book (band trades everything) and a held book (band HOLDs)
    are checked, because the two take different branches through the emit loop
    and only one of them existed to be broken.
    """
    asof, close = panel
    held = _held_book(asof, close, _spec(band=False))
    assert len(held) >= 6, "the fixture must build a real book to hold"

    for holdings in ({}, held):
        absent = _fingerprint(_targets(_spec(), asof, holdings))
        null = _fingerprint(_targets(
            _spec(group_cap=None, max_gross_stress=None), asof, holdings))
        empty = _fingerprint(_targets(
            _spec(group_cap="", max_gross_stress=""), asof, holdings))
        assert absent == null, "present-but-null is not the same as absent"
        assert absent == empty, "an empty-string key is not the same as absent"
        assert absent, "the fixture emitted nothing; the test would be vacuous"

    # CONTROL: the proof is worthless if the keys cannot change anything.
    active = _fingerprint(_targets(
        _spec(group_cap=0.30, max_gross_stress=1.90), asof, held))
    assert active != _fingerprint(_targets(_spec(), asof, held)), (
        "the active keys changed nothing; test 1 is vacuous")


# ---------------------------------------------------------------------------
# 2. the group cap binds, dollar-neutrally, without dropping a name
# ---------------------------------------------------------------------------

def test_group_cap_binds_to_exactly_k_dollar_neutrally(panel):
    """The operator's contract, on the TARGET row it is defined on.

    Asserted on `_cap_net_group_weight` directly rather than on the emitted
    book, because `k` is defined on the target and two later stages move the
    emitted weights for reasons that have nothing to do with the cap: the band
    trades to its EDGE (every name shrinks by `band_width` toward zero) and
    `min_abs_weight` flattens dust. Testing "the emitted |g| equals k" would be
    testing the band, and would fail for a correct cap.
    """
    asof, _close = panel
    k = 0.10
    sl = CEFDiscountSleeve(_spec(group_cap=k), NAV_USD)
    side = sl._groups()
    base = pd.Series(_signed(_targets(_spec(band=False), asof)))
    g0 = float(base[[t for t in base.index if t in MUNI]].sum()
               - base[[t for t in base.index if t in TAX]].sum())
    assert abs(g0) > k + 0.05, (
        f"the fixture's net group weight is only {g0:+.4f}; the cap would not "
        f"bind and the test would be vacuous")

    capped, bound = cefmod._cap_net_group_weight(base, side, k)
    assert bound is True, "the operator did not report that it acted"
    g1 = float(capped[[t for t in capped.index if t in MUNI]].sum()
               - capped[[t for t in capped.index if t in TAX]].sum())
    assert abs(g1) == pytest.approx(k, abs=1e-12), (
        f"net group weight {g1:+.6f} was not brought to the cap {k}")
    assert math.copysign(1, g1) == math.copysign(1, g0), (
        "the cap changed the SIGN of the group tilt; it is a cap, not a flip")

    # dollar-neutral: the signed sum of the row is unchanged
    assert float(capped.sum()) == pytest.approx(float(base.sum()), abs=1e-12)
    # no name dropped, and the shift is UNIFORM within each side
    assert set(capped.index) == set(base.index), "the cap dropped or added a name"
    assert all(capped[t] != 0 for t in base.index if base[t] != 0), (
        "a held name was zeroed; the cap shifts, it does not drop")
    dm = {t: base[t] - capped[t] for t in base.index if t in MUNI}
    dt = {t: capped[t] - base[t] for t in base.index if t in TAX}
    assert len(set(round(v, 12) for v in dm.values())) == 1, (
        f"the muni shift is not uniform: {dm}")
    assert len(set(round(v, 12) for v in dt.values())) == 1, (
        f"the taxable shift is not uniform: {dt}")
    # a row already inside the cap is untouched, and says so
    wide, wide_bound = cefmod._cap_net_group_weight(base, side, 10.0)
    assert wide_bound is False
    assert wide.equals(base), "a cap the book is already inside changed the book"


def test_group_cap_reaches_the_emitted_book(panel):
    """End to end: the constraint must survive the rest of the sleeve.

    An operator that is provably correct and then wired in at the wrong place
    is a defect the operator's own test cannot see. With the band off (so the
    emitted book IS the min-weight-filtered target) the emitted net group
    weight must come back inside the cap, not merely move.
    """
    asof, _close = panel
    k = 0.10
    base = _signed(_targets(_spec(band=False), asof))
    capped = _signed(_targets(_spec(group_cap=k, band=False), asof))
    g0, g1 = _net_group(base), _net_group(capped)
    assert abs(g0) > k + 0.05, "vacuous: the uncapped book is already inside k"
    # min_abs_weight can flatten a name the cap pushed into the dust, which can
    # only move |g| by less than min_abs_weight per name. Allow exactly that.
    assert abs(g1) <= k + len(base) * 0.005, (
        f"emitted net group weight {g1:+.6f} is outside the cap {k}")
    assert abs(g1) < abs(g0), "the cap did not reduce the tilt at all"
    assert all("gcap=" in t.reason for t in _targets(
        _spec(group_cap=k, band=False), asof)), (
        "the cap is not recorded on the reason line the ledger persists")


def test_group_cap_refuses_when_one_side_is_entirely_unheld():
    """No dollar-neutral uniform shift exists; raise rather than label it capped."""
    w = pd.Series({t: 0.0 for t in TICKERS})
    for t in MUNI:
        w[t] = 0.2                       # muni only: |g| = 1.2, taxable unheld
    side = {t: ("muni" if t in MUNI else "taxable") for t in TICKERS}
    with pytest.raises(ValueError, match="entirely unheld"):
        cefmod._cap_net_group_weight(w, side, 0.30)


# ---------------------------------------------------------------------------
# 3. the gross cap scales the book DOWN; it never flattens it
# ---------------------------------------------------------------------------

def test_gross_cap_scales_down_and_never_flattens(panel):
    asof, _close = panel
    base = _signed(_targets(_spec(), asof))
    g0 = sum(abs(v) for v in base.values())
    cap = g0 / 2.0                       # forces a hard bind
    capped = _signed(_targets(_spec(max_gross_stress=cap), asof))

    g1 = sum(abs(v) for v in capped.values())
    assert g1 == pytest.approx(cap, rel=1e-12), (
        f"gross {g1:.6f} did not land on the cap {cap:.6f}")
    assert g1 > 0, "the book was flattened, not scaled"
    assert set(capped) == set(base), (
        f"names were dropped rather than scaled: {sorted(set(base) - set(capped))}")
    for t in base:
        assert math.copysign(1, capped[t]) == math.copysign(1, base[t]), (
            f"{t} changed side under the gross cap")
        assert capped[t] == pytest.approx(base[t] * 0.5, rel=1e-12), (
            f"{t} was not scaled by the uniform factor")
    # every RATIO between names survives, which is what "scale" means
    names = sorted(base)
    a, b = names[0], names[1]
    assert capped[a] / capped[b] == pytest.approx(base[a] / base[b], rel=1e-12)

    # a cap the book is already inside must be a no-op, not a lever-up
    loose = _signed(_targets(_spec(max_gross_stress=g0 * 5), asof))
    assert loose == base, "the gross cap levered the book UP to the cap"


def test_gross_cap_binds_on_the_held_book_after_the_band(panel):
    """Margin is charged on what is HELD, so the cap acts after the band.

    The held book is scaled to sit on the band's own weights; the cap is then
    set below that gross and must pull the emitted book back to it -- which it
    can only do if it is applied to the banded weights and not to the target.
    """
    asof, close = panel
    held = _held_book(asof, close, _spec(band=False))
    banded = _targets(_spec(), asof, held)
    held_gross = sum(
        abs(t.signed_qty() * close[t.instrument] / NAV_USD)
        if t.qty is not None else abs(float(t.weight))
        for t in banded if t.side != FLAT)
    assert held_gross > 0.2, "fixture must hold a real book"

    cap = held_gross * 0.6
    out = _targets(_spec(max_gross_stress=cap), asof, held)
    assert all(t.qty is None for t in out if t.side != FLAT), (
        "a HOLD survived a binding margin cap; a scaled hold is a trade")
    emitted = sum(abs(float(t.weight)) for t in out if t.side != FLAT)
    assert emitted == pytest.approx(cap, rel=1e-9), (
        f"emitted gross {emitted:.6f} is not the cap {cap:.6f}")
    assert all("gmax=" in t.reason for t in out), (
        "the cap is not recorded on the reason line the ledger persists")


# ---------------------------------------------------------------------------
# 4. the groups come from the panel's stated mandate, not from a literal
# ---------------------------------------------------------------------------

def test_groups_are_read_from_the_spec_universes_stated_mandate(tmp_path, monkeypatch):
    """Relabel one name's `grp` and the cap must put it on the other side.

    If the sleeve carried its own list of muni tickers this would pass
    regardless, which is the whole point of checking it.
    """
    asof, _close = _write_panel(tmp_path, monkeypatch)
    sl = CEFDiscountSleeve(_spec(group_cap=0.30), NAV_USD)
    assert sl._groups() == {**{t: "muni" for t in MUNI},
                            **{t: "taxable" for t in TAX}}, (
        "the muni axis is not `grp == 'muni'` on the panel")

    moved = dict(GRP)
    moved["MUN1"] = "multi"                       # same fund, new stated mandate
    asof2, _ = _write_panel(tmp_path, monkeypatch, grp=moved)
    sl2 = CEFDiscountSleeve(_spec(group_cap=0.30), NAV_USD)
    g2 = sl2._groups()
    assert g2["MUN1"] == "taxable", "a relabelled name did not change side"
    assert g2["MUN2"] == "muni", "the relabel leaked to another name"

    # and it reaches the cap: the two labellings give different books
    a = _signed(_targets(_spec(group_cap=0.10), asof2))
    _write_panel(tmp_path, monkeypatch, grp=GRP)
    b = _signed(_targets(_spec(group_cap=0.10), asof))
    assert a != b, "the grouping does not reach the constraint"


# ---------------------------------------------------------------------------
# 5. no silent fallback: a missing group source refuses
# ---------------------------------------------------------------------------

def test_missing_grp_column_raises_naming_what_is_missing(tmp_path, monkeypatch):
    """A panel with no `grp` at all. The sleeve must refuse, not guess."""
    asof, _close = _write_panel(tmp_path, monkeypatch)
    px = pd.read_parquet(cefmod.PX_PATH).drop(columns=["grp"])
    nogrp = tmp_path / "px_nogrp.parquet"
    px.to_parquet(nogrp)
    monkeypatch.setattr(cefmod, "PX_PATH", nogrp)
    monkeypatch.setattr(cefmod, "GRP_PATH", nogrp)

    with pytest.raises(ValueError, match="ticker/grp"):
        _targets(_spec(group_cap=0.30), asof)
    # ... and with the cap OFF the same panel still works, which is what makes
    # the refusal a property of the constraint and not of the panel.
    assert _targets(_spec(), asof), "the cap-off path broke on a grp-less panel"


def test_a_universe_name_with_no_grp_row_raises_naming_it(tmp_path, monkeypatch):
    """One name present in the universe but absent from the group source."""
    asof, _close = _write_panel(tmp_path, monkeypatch)
    px = pd.read_parquet(cefmod.PX_PATH)
    px = px[px.ticker != "TAX6"]
    partial = tmp_path / "px_partial.parquet"
    px.to_parquet(partial)
    monkeypatch.setattr(cefmod, "GRP_PATH", partial)

    with pytest.raises(ValueError, match="TAX6"):
        _targets(_spec(group_cap=0.30), asof)


def test_an_ambiguous_grp_raises_rather_than_picking_one(tmp_path, monkeypatch):
    """Two different mandates for one ticker. Do not pick; refuse."""
    asof, _close = _write_panel(tmp_path, monkeypatch)
    px = pd.read_parquet(cefmod.PX_PATH)
    px.loc[px.index[px.ticker.values == "MUN1"][0], "grp"] = "multi"
    ambiguous = tmp_path / "px_ambiguous.parquet"
    px.to_parquet(ambiguous)
    monkeypatch.setattr(cefmod, "GRP_PATH", ambiguous)

    with pytest.raises(ValueError, match="MUN1"):
        _targets(_spec(group_cap=0.30), asof)


def test_a_missing_group_source_file_raises(tmp_path, monkeypatch):
    asof, _close = _write_panel(tmp_path, monkeypatch)
    monkeypatch.setattr(cefmod, "GRP_PATH", tmp_path / "does_not_exist.parquet")
    with pytest.raises(FileNotFoundError, match="group source"):
        _targets(_spec(group_cap=0.30), asof)


def test_nonsense_cap_values_raise(panel):
    """A negative cap or a non-positive gross ceiling is a spec error, not a shrug."""
    asof, _close = panel
    with pytest.raises(ValueError, match="group_cap must be >= 0"):
        _targets(_spec(group_cap=-0.1), asof)
    with pytest.raises(ValueError, match="max_gross_stress must be > 0"):
        _targets(_spec(max_gross_stress=0.0), asof)


# ---------------------------------------------------------------------------
# the frozen spec's own keys must be readable and the revert path must exist
# ---------------------------------------------------------------------------

def test_the_frozen_spec_carries_the_adopted_key_with_its_note():
    """/spec-change step 4: the adopted key has a `_<key>_note` naming how it was
    DERIVED and its REVERT. On Alpaca (v7.20260928) only `max_gross_stress` is
    adopted; `group_cap` is deliberately ABSENT -- its rule gives k = 0 on the
    13-name universe, which is the killed hard-neutrality variant (team lead,
    2026-09-28; results/cef/PREREG_ALPACA_V7_2026-09-28.md section 3a). A group_cap
    that appears in the spec without a new pre-registration fails this test."""
    import json
    from pathlib import Path
    repo = Path(cefmod.__file__).resolve().parents[3]
    spec = json.loads((repo / "ops/specs/cef_discount.frozen.json").read_text())
    frozen = spec["frozen"]
    assert "max_gross_stress" in frozen
    note = frozen.get("_max_gross_stress_note")
    assert note and "REVERT" in note and "DERIVED" in note
    assert "group_cap" not in frozen, (
        "group_cap is in the spec: that needs its own pre-registration, because "
        "its rule gives k = 0 (killed hard neutrality) on the 13-name universe")
    # 2026-11-01 (CEF trial 53): v8 added `sizing_multiplier` only and superseded v7; 2026-11-02
    # (amendment 1): v9 changes its value only and supersedes v8. group_cap is still absent
    # (asserted above). The multiplier's own note is tested in test_sizing_multiplier.py.
    assert spec["_supersedes"] == "cef_discount.v8.20261101"
