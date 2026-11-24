"""`sizing_multiplier` (CEF trial 53): what the key does, and that a bad one refuses.

results/cef/PREREG_VOLTARGET_2026-10-30.md §1.1, approved 2026-11-01. With the key set to m, the
account holds m times the UNIT book, which this spec builds at its own `vol_target_annual`:
  * the band compares the unit target with held / m;
  * `_cap_gross` acts at max_gross_stress / m in unit weights, so at max_gross_stress x the
    account's NAV;
  * every weight target is m x the unit weight. HOLDs stay in shares.

The byte-for-byte no-op of the key ABSENT, through the whole session against 35b429f's code, is
quantt/session/tests/test_sizing_multiplier_noop.py. Here, on the sleeve itself:

  1. absent, null and 1.0 give identical targets, reasons included (the no-op at the sleeve);
  2. an opening book at m is m x the unit book when the cap does not bind;
  3. a held book at m x target is all band HOLDs (on 35b429f it trades down toward 1/m);
  4. when m x the unit gross is above the cap, the emitted gross is the cap, in the unit
     book's proportions;
  5. the registry refuses a malformed value, a near-miss spelling, a multiplier with no
     `max_gross_stress`, and an effective vol target outside the sane band;
  6. a combined book refuses the key (one sizing authority per book);
  7. orient's SPEC section reports it.

Tests 2-7 fail on 35b429f, where nothing reads the key. Test 1 passes there too, by design. The
panel is test_combine_noop.py's generated 13-fund panel, so these never skip.
"""
import copy
import json

import pandas as pd
import pytest

from quantt.session.tests.test_combine_noop import ASOF, SYN_SPEC, _synthetic_panel
from src.deploy.registry import build_sleeve, validate_spec
from src.deploy.sleeve import SHORT, MarketState
from src.deploy.tests.test_group_cap import _fingerprint

NAV = SYN_SPEC["capital_usd"]


def _spec(**frozen):
    s = copy.deepcopy(SYN_SPEC)
    s["frozen"].update(frozen)
    return s


def _targets(spec, held, opening):
    sl = build_sleeve(spec, spec["capital_usd"])
    ms = MarketState(asof=pd.Timestamp(ASOF), prices=pd.DataFrame(), holdings=dict(held),
                     extras={"sleeve_nav": NAV, "opening_session": opening})
    return sl.target_positions(pd.Timestamp(ASOF), ms)


def _closes(px_path):
    p = pd.read_parquet(px_path)
    p = p[pd.to_datetime(p["date"]) == pd.Timestamp(ASOF)]
    return dict(zip(p["ticker"], p["close"].astype(float)))


def _weights(targets):
    return {t.instrument: float(t.weight) for t in targets if t.weight}


def _held_at(targets, closes, m):
    """Whole shares of m x the targets' weights at the as-of closes."""
    held = {}
    for t in targets:
        if t.weight:
            q = int(m * NAV * abs(float(t.weight)) / closes[t.instrument])
            if q:
                held[t.instrument] = float(-q if t.side == SHORT else q)
    return held


def test_absent_null_and_one_are_byte_identical(tmp_path, monkeypatch):
    px, _, _ = _synthetic_panel(tmp_path, monkeypatch)
    base = _targets(SYN_SPEC, {}, True)
    held = _held_at(base, _closes(px), 0.5)                     # half the day-one book: trades and holds
    for opening, h in ((True, {}), (False, held)):
        want = _fingerprint(_targets(SYN_SPEC, h, opening))
        for v in (None, 1.0):
            assert _fingerprint(_targets(_spec(sizing_multiplier=v), h, opening)) == want, (v, opening)


def test_an_opening_book_at_m_is_m_times_the_unit_book(tmp_path, monkeypatch):
    _synthetic_panel(tmp_path, monkeypatch)
    m = 1.5
    unit = _targets(SYN_SPEC, {}, True)
    w0 = _weights(unit)
    assert m * sum(abs(v) for v in w0.values()) < SYN_SPEC["frozen"]["max_gross_stress"], \
        "precondition: the cap must not bind, so this test is about scaling alone"
    raised = _targets(_spec(sizing_multiplier=m), {}, True)
    w1 = _weights(raised)
    assert set(w1) == set(w0)
    for k, v in w0.items():
        assert w1[k] == v * m, k                              # the sleeve's own multiply, exact
    assert all("smult=1.5000" in t.reason for t in raised if t.weight)


def test_a_held_book_at_m_times_target_is_all_band_holds(tmp_path, monkeypatch):
    px, _, _ = _synthetic_panel(tmp_path, monkeypatch)
    m, band = 1.5, SYN_SPEC["frozen"]["band_width"]
    unit = _targets(SYN_SPEC, {}, True)
    w0 = _weights(unit)
    assert m * sum(abs(v) for v in w0.values()) < SYN_SPEC["frozen"]["max_gross_stress"]
    # Precondition that makes this test fail on 35b429f: read as unit weights there, at least
    # one held name is more than the band from its target, so the old sleeve trades it down.
    assert max((m - 1.0) * abs(v) for v in w0.values()) > band
    held = _held_at(unit, _closes(px), m)
    out = _targets(_spec(sizing_multiplier=m), held, False)
    for t in out:
        if t.instrument in held:
            assert t.qty == held[t.instrument] and "band hold" in t.reason, (t.instrument, t.reason)
    # and the unit book on the same holdings trades: the multiplier, not the data, holds them
    old = _targets(SYN_SPEC, held, False)
    assert any(t.weight for t in old if t.instrument in held)


def test_the_cap_binds_at_the_accounts_nav(tmp_path, monkeypatch):
    _synthetic_panel(tmp_path, monkeypatch)
    m, cap = 3.0, SYN_SPEC["frozen"]["max_gross_stress"]
    w0 = _weights(_targets(SYN_SPEC, {}, True))
    assert m * sum(abs(v) for v in w0.values()) > cap, "precondition: the cap must bind"
    raised = _targets(_spec(sizing_multiplier=m), {}, True)
    w1 = _weights(raised)
    # One uniform factor on the unit book at cap / m (`_cap_gross`), then x m. A name the scaling
    # takes under min_abs_weight (in UNIT weight) is dropped by the existing dust rule, which only
    # lowers gross further (`_cap_gross` docstring).
    f = (cap / m) / sum(abs(v) for v in w0.values())
    minw = SYN_SPEC["frozen"]["min_abs_weight"]
    for k, v in w0.items():
        if abs(v * f) < minw:
            assert k not in w1, k
        else:
            assert w1[k] == pytest.approx(m * v * f, abs=1e-15), k
    gross = sum(abs(v) for v in w1.values())
    dropped = sum(abs(m * v * f) for k, v in w0.items() if k not in w1)
    assert gross <= cap + 1e-12 and gross == pytest.approx(cap - dropped, abs=1e-12)
    assert all("smult=3.0000" in t.reason and "gmax=1.8000*x" in t.reason for t in raised if t.weight)


@pytest.mark.parametrize("bad", [True, "1.13", 0, 0.0, -1.1, float("nan"), float("inf"), [1.13]])
def test_the_registry_refuses_a_malformed_multiplier(bad):
    with pytest.raises(ValueError, match="sizing_multiplier"):
        validate_spec(_spec(sizing_multiplier=bad))


@pytest.mark.parametrize("key", ["sizing_multipliers", "sizing_multiplyer", "_sizing_multiplier",
                                 "sizingmultiplier", "Sizing-Multiplier"])
def test_the_registry_refuses_a_near_miss_spelling(key):
    with pytest.raises(ValueError, match="misspelling of 'sizing_multiplier'"):
        validate_spec(_spec(**{key: 1.13}))


def test_the_note_is_not_a_near_miss():
    validate_spec(_spec(sizing_multiplier=1.13, _sizing_multiplier_note="the sibling note"))


def test_the_multiplier_needs_the_cap():
    s = _spec(sizing_multiplier=1.13)
    del s["frozen"]["max_gross_stress"]
    with pytest.raises(ValueError, match="max_gross_stress is not"):
        validate_spec(s)


def test_the_effective_vol_target_stays_in_the_sane_band():
    with pytest.raises(ValueError, match="effective vol target"):
        validate_spec(_spec(sizing_multiplier=7.0))              # 0.06 x 7 = 0.42 > 0.40
    validate_spec(_spec(sizing_multiplier=6.5))                  # 0.39: inside


def test_a_combined_book_refuses_the_multiplier(tmp_path):
    from quantt.session import combine as cmb
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(_spec(sizing_multiplier=1.13)))
    bj = tmp_path / "book.json"
    bj.write_text(json.dumps({"book_id": "t", "sleeves": [
        {"name": "s", "enabled": True, "spec_path": "s.json", "risk_budget": 1.0}]}))
    with pytest.raises(cmb.CombineError, match="sizing_multiplier"):
        cmb.load_sleeves(bj, sp, tmp_path, lambda spec: (lambda *a, **k: []))
    with pytest.raises(cmb.CombineError, match="sizing_multiplier"):
        cmb.book_vol_target(_spec(sizing_multiplier=1.13))
    assert cmb.book_vol_target(SYN_SPEC) == 0.06               # absent: unchanged


def test_orient_reports_the_multiplier():
    from ops import orient
    f = orient.spec_fields({"frozen": {"vol_target_annual": 0.06, "sizing_multiplier": 1.13}})
    assert f["sizing_multiplier"] == 1.13
    assert orient.spec_fields({"frozen": {"vol_target_annual": 0.06}})["sizing_multiplier"] is None


def test_the_live_spec_carries_the_approved_multiplier_with_its_note():
    """The activation, as amended: CEF trial 53 amendment 1 (team lead 2026-11-02;
    /spec-change steps 4-5). The core's spec carries 1.30 with its sibling note, under spec v9,
    which supersedes v8 (1.13, activated 2026-11-01), and it still validates. The note must name
    the derivation on the flatten book's trading sessions (1.3007) and the two values not chosen:
    1.13 (the hold book) and 1.96 (the calendar sd the flat sessions inflate). This test FAILS on
    8b14298 (v8, x1.13) and on the code commit f52a613 (the key absent), by design: it pins the
    activation, not the code. The REVERT is the note's, and this test's expectations with it."""
    from pathlib import Path
    from src.deploy.registry import cef_sizing_multiplier
    from src.deploy.sleeves import cef_discount as cefmod
    spec = json.loads((Path(cefmod.__file__).resolve().parents[3] /
                       "ops/specs/cef_discount.frozen.json").read_text())
    f = spec["frozen"]
    assert cef_sizing_multiplier(f) == 1.3
    note = f["_sizing_multiplier_note"]
    for word in ("AMENDMENT 1", "UNITS", "DERIVED", "NOT CHOSEN", "CONSEQUENCE", "READ BY", "REVERT",
                 "1.3007", "1.13", "1.96", "FLATTENS", "10.14%", "-3.06%", "12.07%", "CEF stays 53",
                 "spec-cef_discount.v8.20261101", "spec-cef_discount.v7.20260928"):
        assert word in note, word
    assert spec["spec_id"] == "cef_discount.v9.20261102"
    assert spec["_supersedes"] == "cef_discount.v8.20261101"
    assert f["vol_target_annual"] == 0.06                       # NOT moved: the unit book is v7's
    validate_spec(spec)
