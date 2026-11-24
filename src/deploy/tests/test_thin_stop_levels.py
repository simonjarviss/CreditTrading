"""CEF trial 55 (te4): the K1-K3 report thresholds, `risk.thin_*`, as the registry parses them.

The runner's owner (answer 3, 2026-11-03): the thresholds are report-only spec keys, set in the
ACTIVATION commit with a sibling note naming the compose_<stamp>.json that derived them; the
live path never reads results/. In this pass the registry accepts and validates them when
present, the misspelling guard knows them, and absent reads UNMEASURED
(src/deploy/registry.py `cef_thin_stop_levels`). Each test fails on the code before this commit,
which has no `cef_thin_stop_levels` and validates a spec carrying any of these keys without a
word.
"""
import copy
import json
from pathlib import Path

import pytest

from src.deploy import registry as R

ROOT = Path(__file__).resolve().parents[3]

# K3's run length is required under the rule (the runner owner's review 2026-11-04, item 9).
K3_RUN_NOTE = "test only: §6.3's 3 consecutive reduced closes"
SPEC = {
    "spec_id": "test.te4-lines.v1", "status": "test", "capital_usd": 100_000.0,
    "allocation": {"type": "cef_discount"},
    "risk": {"max_gross_exposure_usd": 260_000.0, "halve_drawdown": 0.12, "kill_drawdown": 0.18,
             "thin_k3_run_sessions": 3, "_thin_k3_run_sessions_note": K3_RUN_NOTE},
    "frozen": {"universe": [f"F{i}" for i in range(8)], "z_window": 252, "rebalance_days": 1,
               "vol_target_annual": 0.06, "min_adv_usd": 3_000_000.0, "max_nav_age_bd": 3,
               "min_names": 6, "min_abs_weight": 0.005, "gross_leverage": 1.0,
               "order_type": "MOC", "band_width": 0.048, "max_gross_stress": 1.8,
               "below_min_names": "trade_eligible", "below_min_names_floor": 4},
}
# Test values (the pre-registration's drafting-day figures, §6.3); never the live ones.
VALUES = {"thin_k1_episode_drawdown": 0.1052, "thin_k2_max_name_frac": 0.956,
          "thin_k3_net_run": 0.248, "thin_k3_net_once": 0.833}
NOTE = "derived by results/cef/prereg_thin_te4/compose.py --stamp 2026-12-01: compose_2026-12-01.json §E"


def spec_with(**kw) -> dict:
    s = copy.deepcopy(SPEC)
    for k, v in kw.items():
        s["risk"][k] = v
        s["risk"][f"_{k}_note"] = NOTE
    return s


def test_absent_reads_none_for_every_line_and_the_live_specs_validate():
    assert R.cef_thin_stop_levels(SPEC) == {**{k: None for k in R.CEF_THIN_STOP_KEYS},
                                            "thin_k3_run_sessions": 3}
    for f in ("cef_discount", "c4_families"):
        live = json.loads((ROOT / "ops" / "specs" / f"{f}.frozen.json").read_text())
        R.validate_spec(live)
        assert R.cef_thin_stop_levels(live) == {k: None for k in R.CEF_THIN_KEYS}


def test_present_values_are_read_with_their_notes():
    got = R.cef_thin_stop_levels(spec_with(**VALUES))
    assert got == {**VALUES, "thin_k3_run_sessions": 3}
    R.validate_spec(spec_with(**VALUES))


@pytest.mark.parametrize("key,bad", [
    ("thin_k1_episode_drawdown", 10.52),      # a percent
    ("thin_k1_episode_drawdown", 1.0),
    ("thin_k1_episode_drawdown", 0.0),
    ("thin_k2_max_name_frac", 95.6),          # a percent: above max_gross_stress
    ("thin_k2_max_name_frac", 1.8),           # at the cap
    ("thin_k3_net_once", float("nan")),
    ("thin_k3_net_run", True),
    ("thin_k3_net_run", "0.248"),
    ("thin_k2_max_name_frac", -0.1),
])
def test_a_bad_value_is_refused_naming_the_key(key, bad):
    with pytest.raises(ValueError, match=key):
        R.validate_spec(spec_with(**{key: bad}))


def test_the_run_line_must_be_below_the_once_line():
    with pytest.raises(ValueError, match="thin_k3_net_run"):
        R.cef_thin_stop_levels(spec_with(thin_k3_net_run=0.9, thin_k3_net_once=0.8))


def test_a_threshold_without_its_compose_note_is_refused():
    s = spec_with(**VALUES)
    del s["risk"]["_thin_k2_max_name_frac_note"]
    with pytest.raises(ValueError, match="_thin_k2_max_name_frac_note"):
        R.validate_spec(s)
    s["risk"]["_thin_k2_max_name_frac_note"] = "the fit maximum, from the draft"
    with pytest.raises(ValueError, match="compose_"):
        R.validate_spec(s)


def test_a_threshold_under_another_rule_is_refused():
    for rule in ("flatten", "hold", None):
        s = spec_with(thin_k2_max_name_frac=0.956)
        for k in ("thin_k3_run_sessions", "_thin_k3_run_sessions_note"):
            s["risk"].pop(k)
        s["frozen"].pop("below_min_names_floor")
        if rule is None:
            s["frozen"].pop("below_min_names")
        else:
            s["frozen"]["below_min_names"] = rule
        with pytest.raises(ValueError, match="read only under 'trade_eligible'"):
            R.validate_spec(s)


NOTES = [f"_{k}_note" for k in R.CEF_THIN_KEYS]


def _reverted(rule) -> dict:
    """SPEC as te4's revert leaves it: no rule (absent) or "flatten"/"hold", no floor, no
    `risk.thin_*` key and no note of one."""
    s = copy.deepcopy(SPEC)
    for k in ("thin_k3_run_sessions", "_thin_k3_run_sessions_note"):
        s["risk"].pop(k)
    s["frozen"].pop("below_min_names_floor")
    if rule is None:
        s["frozen"].pop("below_min_names")
    else:
        s["frozen"]["below_min_names"] = rule
    return s


@pytest.mark.parametrize("note", NOTES)
@pytest.mark.parametrize("rule", ["flatten", "hold", None])
def test_a_note_left_under_another_rule_is_refused_naming_it(rule, note):
    """Review of 4e1ab0b (low, robustness). te4's revert deletes the floor, the five `risk.thin_*`
    keys AND their notes, and the reverted spec must be byte-identical to the pre-te4 one
    (docs/RUNNER.md, te4's revert; the runner owner's review 2026-11-04, item 2). The registry
    refused the keys under another rule but skipped the notes (the misspelling guard passes
    them, and the other-rule check counted keys only), so a revert that left a note behind
    loaded cleanly and only a manual diff would catch it. Now the note is refused, named. The
    clean reverted spec still validates. Fails on 8e7f545, which validates every case."""
    s = _reverted(rule)
    R.validate_spec(s)
    s["risk"][note] = "left behind by a revert"
    with pytest.raises(ValueError, match="read only under 'trade_eligible'") as e:
        R.validate_spec(s)
    assert repr(note) in str(e.value), str(e.value)
    with pytest.raises(ValueError, match="read only under 'trade_eligible'"):
        R.cef_thin_stop_levels(s)


@pytest.mark.parametrize("f", ["cef_discount", "c4_families"])
def test_a_te4_note_added_to_a_live_spec_is_refused(f):
    """The review's own probe: the live core spec (the rule absent) and C4's ("hold"), each with
    one te4 note added to `risk`, validated and read every line as None. Now each refuses, naming
    the note; the live files as committed still validate (test above). Fails on 8e7f545."""
    live = json.loads((ROOT / "ops" / "specs" / f"{f}.frozen.json").read_text())
    for note in NOTES:
        s = copy.deepcopy(live)
        s.setdefault("risk", {})[note] = "left behind by a revert"
        with pytest.raises(ValueError, match="read only under 'trade_eligible'") as e:
            R.validate_spec(s)
        assert repr(note) in str(e.value), (f, note, str(e.value))


@pytest.mark.parametrize("typo", ["thin_k1_episode_drawdwn", "thin_k2_max_name_fracs",
                                  "think3netrun", "_thin_k3_net_once", "Thin-K3-Net-Once"])
def test_a_misspelt_threshold_is_refused(typo):
    s = copy.deepcopy(SPEC)
    s["risk"][typo] = 0.2
    with pytest.raises(ValueError, match="looks like a misspelling"):
        R.validate_spec(s)


def test_a_threshold_written_in_frozen_is_refused():
    s = copy.deepcopy(SPEC)
    s["frozen"]["thin_k2_max_name_frac"] = 0.956
    with pytest.raises(ValueError, match="move it to risk"):
        R.validate_spec(s)


def test_the_live_keys_are_far_from_every_threshold():
    """No key either live spec carries is within the guard's reach of a threshold, so the guard
    cannot refuse a live spec (checked key by key, as test_c4_sleeve_keys does for C4's)."""
    for f in ("cef_discount", "c4_families"):
        live = json.loads((ROOT / "ops" / "specs" / f"{f}.frozen.json").read_text())
        for block in ("risk", "frozen"):
            for key in live.get(block) or {}:
                assert R._thin_stop_near_miss(key) is None, (f, block, key)


# ---------------------------------------------------------------------------
# K3's run length, `risk.thin_k3_run_sessions` (the runner owner's review 2026-11-04, item 9)
# ---------------------------------------------------------------------------

RUN_KEY = "thin_k3_run_sessions"


def _without_run(s: dict) -> dict:
    s = copy.deepcopy(s)
    for k in (RUN_KEY, f"_{RUN_KEY}_note"):
        s["risk"].pop(k, None)
    return s


def test_the_k3_run_length_is_required_under_the_rule_with_no_default():
    """It was a module constant (drawdown.THIN_K3_RUN = 3). Now the spec states it, and under
    "trade_eligible" a spec without it refuses at load, as one without a floor does. Fails on
    8527488, which validates the spec without it."""
    with pytest.raises(ValueError, match=f"needs risk.{RUN_KEY}.*no default"):
        R.validate_spec(_without_run(SPEC))
    with pytest.raises(ValueError, match=RUN_KEY):
        R.cef_thin_stop_levels(_without_run(spec_with(**VALUES)))
    for v in (2, 3, 5):
        s = copy.deepcopy(SPEC)
        s["risk"][RUN_KEY] = v
        R.validate_spec(s)
        assert R.cef_thin_stop_levels(s)[RUN_KEY] == v


@pytest.mark.parametrize("bad", [True, 3.0, "3", 1, 0, -3, None])
def test_a_bad_k3_run_length_is_refused_naming_the_key_and_the_value(bad):
    s = copy.deepcopy(SPEC)
    s["risk"][RUN_KEY] = bad
    with pytest.raises(ValueError, match=RUN_KEY) as e:
        R.validate_spec(s)
    assert repr(bad) in str(e.value) or str(bad) in str(e.value)


@pytest.mark.parametrize("note", [None, "", "   ", 3])
def test_the_k3_run_length_needs_its_note(note):
    s = copy.deepcopy(SPEC)
    if note is None:
        s["risk"].pop(f"_{RUN_KEY}_note")
    else:
        s["risk"][f"_{RUN_KEY}_note"] = note
    with pytest.raises(ValueError, match=f"_{RUN_KEY}_note"):
        R.validate_spec(s)


def test_the_k3_run_length_under_another_rule_is_refused():
    """As the floor and the lines: a count nothing reads is a spec that says one thing and does
    another. The revert spec deletes it with them."""
    for rule in ("flatten", "hold", None):
        s = copy.deepcopy(SPEC)
        s["frozen"].pop("below_min_names_floor")
        if rule is None:
            s["frozen"].pop("below_min_names")
        else:
            s["frozen"]["below_min_names"] = rule
        with pytest.raises(ValueError, match=f"{RUN_KEY}.*read only under 'trade_eligible'"):
            R.validate_spec(s)
        R.validate_spec(_without_run(s))          # deleted with the rule: validates


@pytest.mark.parametrize("typo", ["thin_k3_run_session", "thin_k3_runs_sessions", "think3runsessions",
                                  "_thin_k3_run_sessions", "Thin-K3-Run-Sessions"])
def test_a_misspelt_k3_run_length_is_refused(typo):
    s = copy.deepcopy(SPEC)
    s["risk"][typo] = 3
    with pytest.raises(ValueError, match=f"looks like a misspelling of '{RUN_KEY}'"):
        R.validate_spec(s)


def test_the_k3_run_length_written_in_frozen_is_refused():
    s = copy.deepcopy(SPEC)
    s["frozen"][RUN_KEY] = 3
    with pytest.raises(ValueError, match=f"move it to risk.{RUN_KEY}"):
        R.validate_spec(s)


# ---------------------------------------------------------------------------
# K2 and K3 below max_gross_stress, at construction, naming both values (owner's review item 4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", ["thin_k2_max_name_frac", "thin_k3_net_run", "thin_k3_net_once"])
@pytest.mark.parametrize("over", [0.0, 0.2, 93.8])          # at the cap, above it, a percent
def test_k2_and_k3_at_or_above_the_cap_refuse_at_construction_naming_both_values(key, over):
    """The runner owner's review (2026-11-04), item 4: each K2/K3 threshold must be below
    frozen.max_gross_stress, validated at construction, and a violation refuses AND NAMES THE
    VALUES. Confirmed on 69ef368 (`cef_thin_stop_levels`, called by `validate_spec`, which
    `build_sleeve` calls before it constructs): the message names the key, its value and the
    cap. No code changed; this pins the confirmation, so it passes on 69ef368 by design. The
    once line is moved with the run line where needed, so the run-below-once check is not what
    refuses."""
    cap = SPEC["frozen"]["max_gross_stress"]
    v = cap + over
    lines = {key: v}
    if key == "thin_k3_net_run":
        lines["thin_k3_net_once"] = 0.5                     # below the run line: never reached
    s = spec_with(**lines)
    for build in (R.validate_spec, lambda spec: R.build_sleeve(spec, 100_000.0)):
        with pytest.raises(ValueError) as e:
            build(s)
        msg = str(e.value)
        assert f"risk.{key} {v!r}" in msg and f"max_gross_stress {cap}" in msg, msg
    # Just below the cap is accepted (with the run line below the once line).
    ok = {key: cap - 0.01}
    if key == "thin_k3_net_run":
        ok["thin_k3_net_once"] = cap - 0.005
    R.validate_spec(spec_with(**ok))
