"""`MarketState.extras["opening_session"]`: day one trades to FULL target.

THE DECISION (team lead, 2026-09-28, docs/RUNNER.md "Day one (flat book)"): the
first session of a book trades to full target, not to the band edge, so the book
opens dollar-neutral; the band applies from the second session. From a flat book
the band trades each name only to its EDGE, and that opening book came out net
-0.05 to -0.10 of NAV on the last three panel dates (docs/RUNNER.md 4.2).

WHAT EACH TEST WOULD HAVE CAUGHT:

  1. THE NO-OP. The flag is a new input on the live path, and the house rule is
     that absent must be today's behaviour, PROVED byte-for-byte. Checked on the
     REAL panels (`data/cef/`, the live frozen spec, the last three panel dates)
     for a flat book AND a held book -- the held book takes the band's HOLD
     branch, which a flat book never reaches -- and again on the synthetic panel
     of `test_group_cap.py` so the proof does not depend on data/ being present.
  2. FULL TARGET, NOT THE EDGE. With the flag True and a flat book, the emitted
     weights must EQUAL the pre-band target (built by the same sleeve with the
     band removed and the calendar at 1 day, so the signal date is identical),
     must be dollar-neutral, and must DIFFER from the band-edge book -- or the
     switch did nothing.
  3. ORDER OF OPERATIONS. The switch replaces only the band: the group cap still
     acts before it (synthetic panel, where the cap binds) and the gross/margin
     cap still acts after it (a deliberately tight cap, so it binds on any date).
  4. REFUSAL. The flag with a live book RAISES: re-targeting a held book past its
     band is a runner bug, and a sleeve that silently obeyed would churn every
     name. A non-bool flag raises too: whether the band exists must not be
     decided by Python truthiness.

`data/` is gitignored, so the real-panel tests SKIP, naming the missing file,
when the panel is absent; the synthetic tests always run.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.deploy.sleeve import FLAT, SHORT, MarketState
from src.deploy.sleeves import cef_discount as cefmod
from src.deploy.sleeves.cef_discount import CEFDiscountSleeve
from src.deploy.tests.test_group_cap import (
    NAV_USD as SYN_NAV,
    _fingerprint,
    _spec as _syn_spec,
    _write_panel,
)

REPO = Path(cefmod.__file__).resolve().parents[3]
LIVE_SPEC = json.loads((REPO / "ops/specs/cef_discount.frozen.json").read_text())
LIVE_NAV = float(LIVE_SPEC["capital_usd"])
TAG = "opening-session: full target, band skipped"
ABSENT = object()

needs_panel = pytest.mark.skipif(
    not (cefmod.PX_PATH.exists() and cefmod.NAV_PATH.exists()),
    reason=f"real CEF panels absent ({cefmod.PX_PATH}, {cefmod.NAV_PATH}); "
           f"data/ is gitignored -- the synthetic tests below still run")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _live_spec(drop=(), **set_):
    spec = json.loads(json.dumps(LIVE_SPEC))
    for k in drop:
        spec["frozen"].pop(k)
    spec["frozen"].update(set_)
    return spec


def _run(spec, nav, asof, holdings=None, opening=ABSENT):
    extras = {"sleeve_nav": nav}
    if opening is not ABSENT:
        extras["opening_session"] = opening
    sl = CEFDiscountSleeve(spec, nav)
    ms = MarketState(asof=pd.Timestamp(asof), prices=pd.DataFrame(),
                     holdings=dict(holdings or {}), extras=extras)
    return sl.target_positions(pd.Timestamp(asof), ms)


def _weights(targets):
    return {t.instrument: float(t.weight) for t in targets
            if t.side != FLAT and t.weight is not None}


def _pre_band_spec(spec):
    """The same book with the band removed and the calendar at one day.

    With `band_width` absent the sleeve falls back to the `rebalance_days`
    calendar, which would move the signal DATE; at 1 day `sig_pos == pos`, the
    band-on signal date, so the weights are the band's own pre-band target.
    """
    s = json.loads(json.dumps(spec))
    s["frozen"].pop("band_width")
    s["frozen"]["rebalance_days"] = 1
    return s


def _real_dates(n=3):
    d = pd.read_parquet(cefmod.PX_PATH, columns=["date"])["date"]
    return [str(x.date()) for x in sorted(pd.to_datetime(d).unique())[-n:]]


# PINNED for the HOLD-branch no-op test (2026-10-07). The latest panel dates are
# a function of today's market: after the vol scalar jumped 1.38 -> 2.15 the
# held book traded every name on 2026-10-05/06, the HOLD control failed, and the
# prod suite went red with nothing wrong in the code. Panels are append-only, so
# these dates are stable; each was checked to reach "band hold" on both the dev
# and the prod panels. The latest dates still run, byte-identity only.
HOLD_DATES = ("2026-09-23", "2026-09-24", "2026-09-25")
# CEF trial 53 amendment 1 (2026-11-02): the live spec holds 1.30 x the unit book. On 2026-09-23
# the day-one book at x1.30 is gross-capped (unit gross above 1.80 / 1.30), so the held book sits
# below target by the cap's factor and the band trades every name: no HOLD to control for. That
# date stays in the test on the UNIT book (the live spec without `sizing_multiplier`), where it
# still reaches "band hold". The live spec runs on the dates where it does. Checked 2026-11-02:
# unit 13 / 13 / 12 holds, x1.30 0 / 13 / 12.
HOLD_DATES_LIVE = ("2026-09-24", "2026-09-25")
UNIT_SPEC = json.loads(json.dumps(LIVE_SPEC))
UNIT_SPEC["frozen"].pop("sizing_multiplier", None)
UNIT_SPEC["frozen"].pop("_sizing_multiplier_note", None)


def _pinned_dates():
    """The HOLD_DATES the panel holds (other test files import this; it stays a list of dates)."""
    d = pd.read_parquet(cefmod.PX_PATH, columns=["date"])["date"]
    have = {str(x.date()) for x in pd.to_datetime(d).unique()}
    return [x for x in HOLD_DATES if x in have]


def _hold_cases():
    """(asof, which spec) pairs for this file's HOLD-branch test: the live spec on
    HOLD_DATES_LIVE, the unit book on every HOLD_DATES date (above)."""
    have = set(_pinned_dates())
    return ([(x, "live") for x in HOLD_DATES_LIVE if x in have]
            + [(x, "unit") for x in HOLD_DATES if x in have])


def _real_close(asof):
    P = pd.read_parquet(cefmod.PX_PATH, columns=["date", "ticker", "close"])
    P = P[pd.to_datetime(P.date) <= pd.Timestamp(asof)]
    return P.sort_values("date").groupby("ticker")["close"].last().to_dict()


def _held_book(targets, nav, close):
    """Whole shares the targets imply, sized `floor(nav*|w|/price)` as the
    executor sizes them, so the band's HOLD branch fires on the next call."""
    held = {}
    for t in targets:
        if t.weight is None or t.weight == 0.0:
            continue
        mag = math.floor(nav * abs(float(t.weight)) / float(close[t.instrument]))
        if mag:
            held[t.instrument] = float(-mag if t.side == SHORT else mag)
    return held


# ---------------------------------------------------------------------------
# 1. the no-op: absent and False are byte-identical (real panels + synthetic)
# ---------------------------------------------------------------------------

@needs_panel
@pytest.mark.parametrize("asof,which", _hold_cases() if cefmod.PX_PATH.exists() else [])
def test_real_panel_absent_and_false_are_byte_identical(asof, which):
    # The held book is what day one would have bought (full target, gross-
    # capped), so on the next call the band sees gaps smaller than its width
    # and HOLDs -- the branch a flat book never reaches.
    spec = LIVE_SPEC if which == "live" else UNIT_SPEC
    day_one = _run(spec, LIVE_NAV, asof, {}, opening=True)
    held = _held_book(day_one, LIVE_NAV, _real_close(asof))
    assert len(held) >= 6, f"{asof}: the fixture built no real book to hold"
    for holdings in ({}, held):
        a = _fingerprint(_run(spec, LIVE_NAV, asof, holdings))
        f = _fingerprint(_run(spec, LIVE_NAV, asof, holdings, opening=False))
        assert a, "emitted nothing; the comparison would be vacuous"
        assert a == f, f"{asof}: opening_session=False is not byte-identical to absent"
        assert TAG not in a
    # CONTROL: the held book must actually reach the HOLD branch, or the second
    # comparison proves nothing about it.
    assert any("band hold" in t.reason
               for t in _run(spec, LIVE_NAV, asof, held)), \
        f"{asof} ({which}): no HOLD emitted for the held book; the no-op test is partial"


@needs_panel
@pytest.mark.parametrize("asof", _real_dates() if cefmod.PX_PATH.exists() else [])
def test_latest_panel_dates_absent_and_false_are_byte_identical(asof):
    """New data still exercises the switch: byte-identity on the latest dates,
    for a flat and a held book, without the HOLD control (see HOLD_DATES)."""
    day_one = _run(LIVE_SPEC, LIVE_NAV, asof, {}, opening=True)
    held = _held_book(day_one, LIVE_NAV, _real_close(asof))
    for holdings in ({}, held):
        a = _fingerprint(_run(LIVE_SPEC, LIVE_NAV, asof, holdings))
        assert a and a == _fingerprint(_run(LIVE_SPEC, LIVE_NAV, asof, holdings, opening=False))


def test_synthetic_absent_and_false_are_byte_identical(tmp_path, monkeypatch):
    asof, close = _write_panel(tmp_path, monkeypatch)
    for spec in (_syn_spec(), _syn_spec(group_cap=0.30, max_gross_stress=1.90)):
        held = _held_book(_run(spec, SYN_NAV, asof), SYN_NAV, close)
        assert held
        for holdings in ({}, held):
            assert _fingerprint(_run(spec, SYN_NAV, asof, holdings)) == \
                _fingerprint(_run(spec, SYN_NAV, asof, holdings, opening=False))


# ---------------------------------------------------------------------------
# 2. full target, not the band edge (real panels)
# ---------------------------------------------------------------------------

@needs_panel
@pytest.mark.parametrize("asof", _real_dates() if cefmod.PX_PATH.exists() else [])
def test_real_panel_opening_equals_pre_band_target(asof):
    """Before the gross cap: opening == pre-band target exactly, dollar-neutral,
    and different from the band-edge book the same flat account would get."""
    spec = _live_spec(drop=("max_gross_stress",))
    opening_t = _run(spec, LIVE_NAV, asof, {}, opening=True)
    opening = _weights(opening_t)
    ref = _weights(_run(_pre_band_spec(spec), LIVE_NAV, asof, {}))
    edge = _weights(_run(spec, LIVE_NAV, asof, {}))

    assert opening, "opening book is empty; the test would be vacuous"
    assert opening == ref, f"{asof}: opening weights are not the pre-band target"
    assert opening != edge, f"{asof}: opening book equals the band-edge book"
    # Dollar-neutral to 1e-9, allowing only for names the PRE-EXISTING dust rule
    # drops (|w| < min_abs_weight, flattened in the emit loop, which does not
    # re-neutralise). Each such name can move net by at most min_abs_weight.
    minw = float(LIVE_SPEC["frozen"]["min_abs_weight"])
    n_dust = sum(1 for t in opening_t if "below min weight" in t.reason)
    net = sum(opening.values())
    assert abs(net) <= 1e-9 + n_dust * minw, f"{asof}: net {net:+.3e}"
    if n_dust == 0:
        assert abs(net) <= 1e-9
    assert all(TAG in t.reason for t in opening_t)


# ---------------------------------------------------------------------------
# 3. order of operations: group cap before, gross cap after
# ---------------------------------------------------------------------------

@needs_panel
@pytest.mark.parametrize("asof", _real_dates() if cefmod.PX_PATH.exists() else [])
def test_real_panel_gross_cap_still_applies(asof):
    """A cap TIGHTER than any target's gross, so it binds on every date: the
    opening book must be the pre-band target scaled by one multiplier, with
    gross at the cap. 0.5 is a test lever, not a proposed value."""
    cap = 0.5
    spec = _live_spec(max_gross_stress=cap)
    ref = _weights(_run(_pre_band_spec(_live_spec(drop=("max_gross_stress",))),
                        LIVE_NAV, asof, {}))
    got_t = _run(spec, LIVE_NAV, asof, {}, opening=True)
    got = _weights(got_t)
    assert sum(abs(v) for v in ref.values()) > cap, "cap would not bind"
    assert got and set(got) <= set(ref)
    ratios = {got[k] / ref[k] for k in got}
    assert max(ratios) - min(ratios) < 1e-12, "not one uniform multiplier"
    assert 0 < min(ratios) < 1
    assert sum(abs(v) for v in got.values()) <= cap + 1e-12
    assert all(f"gmax={cap:.4f}*x" in t.reason for t in got_t)


def test_synthetic_group_cap_applies_before_opening(tmp_path, monkeypatch):
    """With the group cap binding, the opening book is the CAPPED target."""
    asof, _ = _write_panel(tmp_path, monkeypatch)
    spec = _syn_spec(group_cap=0.10)
    capped_t = _run(spec, SYN_NAV, asof, {}, opening=True)
    assert any("gcap=0.1000*" in t.reason for t in capped_t), "cap did not bind"
    assert _weights(capped_t) == _weights(_run(_pre_band_spec(spec), SYN_NAV, asof))
    assert _weights(capped_t) != _weights(
        _run(_syn_spec(), SYN_NAV, asof, {}, opening=True))


# ---------------------------------------------------------------------------
# 4. refusal
# ---------------------------------------------------------------------------

def test_opening_with_a_live_book_raises(tmp_path, monkeypatch):
    asof, close = _write_panel(tmp_path, monkeypatch)
    held = _held_book(_run(_syn_spec(), SYN_NAV, asof), SYN_NAV, close)
    one = dict([next(iter(held.items()))])
    for spec in (_syn_spec(), _syn_spec(band=False)):
        for holdings in (held, one, {"NOT_IN_UNIVERSE": 5.0}, {"MUN1": float("nan")}):
            with pytest.raises(ValueError, match="opening_session=True but"):
                _run(spec, SYN_NAV, asof, holdings, opening=True)
    # zero-quantity rows are a flat book, not a live one
    assert _run(_syn_spec(), SYN_NAV, asof, {"MUN1": 0.0}, opening=True)


@pytest.mark.parametrize("bad", [1, 0, "true", None, np.True_])
def test_non_bool_flag_raises(tmp_path, monkeypatch, bad):
    asof, _ = _write_panel(tmp_path, monkeypatch)
    with pytest.raises(TypeError, match="exactly True or False"):
        _run(_syn_spec(), SYN_NAV, asof, {}, opening=bad)
