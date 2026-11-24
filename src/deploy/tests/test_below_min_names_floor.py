"""`below_min_names_floor` in the registry (CEF trial 55, te4): parsed, refused where nothing reads it.

WHY (results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md §1.1, approved 2026-11-03, PAPER
ONLY). The rule `below_min_names = "trade_eligible"` builds the book on the eligible funds on a
session with fewer than `min_names` but at least `below_min_names_floor` of them. The floor is a
count, read from the spec and nowhere else. These tests pin the parse before anything reads it:

  1. REQUIRED ONLY UNDER "trade_eligible", REFUSED ELSEWHERE. Under the key absent, "flatten" or
     "hold", a floor is refused at load and at the sleeve's construction, naming the key: a floor
     nothing reads is a spec that says one thing and trades another. The harness refuses `floor`
     the same way (`band_frontier.band_gross_capped`). Its note `_below_min_names_floor_note`
     is refused there too, named (review of 4e1ab0b: a revert that left it behind loaded).
  2. THE VALUE. An int with 2 <= floor < min_names; a bool, a float (4.0 included), a string,
     null, 1, and min_names itself all raise; a missing floor under "trade_eligible" raises; a
     missing `min_names` raises, because the bound cannot be checked without it.
  3. A MISSPELLING REFUSES. `below_min_names_flor` would otherwise validate as an unknown key
     while the spec reads as setting the floor (the near-miss guard, `cef_c4_near_miss`, review of
     11790b5). Its `_note` sibling is not a miss (and is read only beside the floor, group 1).
  4. `build_sleeve` FORWARDS KEYWORDS to the sleeve's constructor and adds none: the sleeve's
     paper declaration (`account="paper"`, the next commit) reaches it through the registry.
  5. THE LIVE SPECS ARE UNTOUCHED: neither the core's nor C4's carries the floor, both validate,
     and `cef_optional_keys` still returns C4's four keys only (pinned by
     scripts/cef/tests/test_c4_paper_benchmark.py).

"trade_eligible" is not an accepted value of `below_min_names` in the commit that adds these
tests (it arrives with the sleeve's reduced branch, the next commit). Group 2 therefore admits it
in the registry's tuple for the test's duration (`_admit_trade_eligible`) so the floor's own
checks are tested on their own; once the value is accepted the fixture changes nothing.

Every test here fails on ac15d09 (the code before the key): `cef_below_min_names_floor` does not
exist, the floor is an unknown key that validates under every rule, a near miss of it validates,
and `build_sleeve` takes no keywords. Group 5 passes there too, by design: it pins what must not
move.
"""
import copy
import json
from pathlib import Path

import pytest

from src.deploy import registry
from src.deploy.tests.test_group_cap import _spec as _gc_spec

REPO = Path(__file__).resolve().parents[3]
KEY = "below_min_names_floor"


def _spec(**frozen):
    s = copy.deepcopy(_gc_spec())
    s["spec_id"], s["status"] = "synthetic-floor", "test"
    s["frozen"].update(frozen)
    return s


@pytest.fixture
def _admit_trade_eligible(monkeypatch):
    if "trade_eligible" not in registry.CEF_BELOW_MIN_NAMES:
        monkeypatch.setattr(registry, "CEF_BELOW_MIN_NAMES",
                            (*registry.CEF_BELOW_MIN_NAMES, "trade_eligible"))


# ---------------------------------------------------------------------------
# 1. refused where nothing reads it
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rule", ["absent", "flatten", "hold"])
def test_a_floor_under_any_other_rule_is_refused_naming_it(rule):
    keys = {KEY: 4} if rule == "absent" else {"below_min_names": rule, KEY: 4}
    s = _spec(**keys)
    with pytest.raises(ValueError, match=KEY) as e:
        registry.validate_spec(s)
    assert "read only under 'trade_eligible'" in str(e.value)
    with pytest.raises(ValueError, match=KEY):
        registry.cef_below_min_names_floor(s["frozen"])
    from src.deploy.sleeves.cef_discount import CEFDiscountSleeve
    with pytest.raises(ValueError, match=KEY):        # built without the registry, too
        CEFDiscountSleeve(s, 100_000.0)


@pytest.mark.parametrize("rule", ["absent", "flatten", "hold"])
def test_no_floor_under_any_other_rule_is_none(rule):
    s = _spec() if rule == "absent" else _spec(below_min_names=rule)
    assert registry.cef_below_min_names_floor(s["frozen"]) is None
    registry.validate_spec(s)


# ---------------------------------------------------------------------------
# 2. the value, under "trade_eligible"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("v", [2, 3, 4, 5])
def test_an_int_between_2_and_min_names_is_the_floor(_admit_trade_eligible, v):
    got = registry.cef_below_min_names_floor(_spec(below_min_names="trade_eligible",
                                                    **{KEY: v})["frozen"])
    assert got == v and type(got) is int


@pytest.mark.parametrize("v", [True, False, 4.0, "4", None, 1, 0, -4, 6, 7, [4], {"n": 4}])
def test_anything_else_raises_naming_the_key(_admit_trade_eligible, v):
    f = _spec(below_min_names="trade_eligible", **{KEY: v})["frozen"]
    with pytest.raises(ValueError, match=KEY):
        registry.cef_below_min_names_floor(f)


def test_trade_eligible_without_a_floor_raises(_admit_trade_eligible):
    with pytest.raises(ValueError, match=f"needs {KEY}"):
        registry.cef_below_min_names_floor(_spec(below_min_names="trade_eligible")["frozen"])


def test_a_missing_or_fractional_min_names_raises(_admit_trade_eligible):
    f = _spec(below_min_names="trade_eligible", **{KEY: 4})["frozen"]
    del f["min_names"]
    with pytest.raises(ValueError, match="no min_names"):
        registry.cef_below_min_names_floor(f)
    f["min_names"] = 6.5
    with pytest.raises(ValueError, match="not a whole number"):
        registry.cef_below_min_names_floor(f)
    f["min_names"] = 6.0                         # the sleeve reads int(min_names); 6.0 is 6
    assert registry.cef_below_min_names_floor(f) == 4


# ---------------------------------------------------------------------------
# 3. a misspelling refuses
# ---------------------------------------------------------------------------

NEAR = ["below_min_names_flor", "below_min_names_floors", "below_min_name_floor",
        "_below_min_names_floor", "belowminnamesfloor", "Below-Min-Names-Floor",
        "_below_min_names_flor_note"]


@pytest.mark.parametrize("key", NEAR)
def test_a_near_miss_of_the_floor_raises_naming_both(key):
    s = _spec(**{key: 4})
    with pytest.raises(ValueError, match="looks like a misspelling") as e:
        registry.validate_spec(s)
    assert repr(key) in str(e.value) and repr(KEY) in str(e.value)
    from src.deploy.sleeves.cef_discount import CEFDiscountSleeve
    with pytest.raises(ValueError, match="looks like a misspelling"):
        CEFDiscountSleeve(s, 100_000.0)


def test_the_floor_note_is_not_a_miss():
    """The note beside the floor, under the rule that reads the floor, validates. (As first
    written this validated the note with the rule absent; since the review of 4e1ab0b a floor
    note under any other rule is refused: the test below.)"""
    assert f"_{KEY}_note" in registry.CEF_C4_NOTES
    assert registry.cef_c4_near_miss(f"_{KEY}_note") is None
    s = _spec(below_min_names="trade_eligible", **{KEY: 4, f"_{KEY}_note": "the derivation"})
    s.setdefault("risk", {}).update(
        thin_k3_run_sessions=3, _thin_k3_run_sessions_note="test only: §6.3's 3")
    registry.validate_spec(s)
    assert registry.cef_below_min_names_floor(s["frozen"]) == 4


@pytest.mark.parametrize("rule", ["absent", "flatten", "hold"])
def test_the_floor_note_under_any_other_rule_is_refused_naming_it(rule):
    """Review of 4e1ab0b (low, robustness). te4's revert deletes the floor WITH its note, and the
    reverted spec must be byte-identical to the pre-te4 one (docs/RUNNER.md, te4's revert). The
    floor was refused under another rule, its note was not (the near-miss guard passes a
    `_<key>_note`), so a note left behind loaded cleanly. Now it is refused at load and at the
    sleeve's construction, naming it, as the floor is. Fails on 8e7f545, where all three
    accept it."""
    note = f"_{KEY}_note"
    keys = {note: "left behind by a revert"}
    if rule != "absent":
        keys["below_min_names"] = rule
    s = _spec(**keys)
    with pytest.raises(ValueError, match=note) as e:
        registry.validate_spec(s)
    assert "read only under 'trade_eligible'" in str(e.value)
    with pytest.raises(ValueError, match=note):
        registry.cef_below_min_names_floor(s["frozen"])
    from src.deploy.sleeves.cef_discount import CEFDiscountSleeve
    with pytest.raises(ValueError, match=note):       # built without the registry, too
        CEFDiscountSleeve(s, 100_000.0)


# ---------------------------------------------------------------------------
# 4. build_sleeve forwards keywords, and adds none
# ---------------------------------------------------------------------------

def test_build_sleeve_forwards_keywords_unchanged(monkeypatch):
    from src.deploy import sleeves  # noqa: F401  (registers the real classes first)
    seen = []

    class Recorder:
        def __init__(self, spec, capital_usd, **kw):
            seen.append((spec["spec_id"], capital_usd, kw))

    monkeypatch.setitem(registry._REGISTRY, "cef_discount", Recorder)
    registry.build_sleeve(_spec(), 1.0, account="paper")
    registry.build_sleeve(_spec(), 2.0)
    assert seen == [("synthetic-floor", 1.0, {"account": "paper"}),
                    ("synthetic-floor", 2.0, {})]


def test_a_keyword_the_sleeve_does_not_take_raises():
    with pytest.raises(TypeError, match="no_such_declaration"):
        registry.build_sleeve(_spec(), 1.0, no_such_declaration=True)


# ---------------------------------------------------------------------------
# 5. the live specs are untouched
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["cef_discount", "c4_families"])
def test_the_live_specs_carry_no_floor_and_validate(name):
    s = json.loads((REPO / f"ops/specs/{name}.frozen.json").read_text())
    assert KEY not in s["frozen"] and f"_{KEY}_note" not in s["frozen"]
    registry.validate_spec(s)
    assert set(registry.cef_optional_keys(s["frozen"])) == {
        "panel_source", "nav_repeat_mask", "zero_volume_mask", "below_min_names"}
