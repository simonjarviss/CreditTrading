"""orient's SPEC section and `scripts/cef/spec.py` report `below_min_names` and its floor (CEF trial 55).

WHY (results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md §1.5). The first thing a session runs
is `python3 -m ops.orient`; if the core's spec ever sets `below_min_names = "trade_eligible"`
(paper only), the SPEC section must say so, with the floor, rather than leave it to be found in
the JSON. ABSENT is printed as absent, with what absent means (the registry reads "flatten"),
and never as an invented value. `scripts/cef/spec.py` exposes both beside SIZING_MULTIPLIER, as
the single reader of the spec, so research (results/cef/prereg_thin_te4/compose.py) reads the
floor from there.

ABSENT IS NOT NULL. The registry reads an absent `below_min_names` as "flatten" and REFUSES a
written null (`cef_below_min_names`; the floor's parse refuses null too). A reader that mapped
null to None would show a spec the book cannot load as today's rule. So orient keeps ABSENT as
its own flag (as it does `vol_target_absent`), and spec.py raises SpecError on a written null,
which orient's SPEC section reports as UNMEASURED with the message.

Mirrors `test_orient_reports_the_multiplier` (src/deploy/tests/test_sizing_multiplier.py) and
`TestSpecFields` (ops/tests/test_orient.py). Every test fails on ac15d09, where neither reader
knows the keys: `spec_fields` has no such field (KeyError), `render` prints no such line, and
spec.py has no BELOW_MIN_NAMES, BELOW_MIN_NAMES_FLOOR or `_as_written` (AttributeError).
"""
import pytest

from ops import orient


def _render(capsys, fields):
    d = {"measured_at": "t", "sections": {
        n: {"UNMEASURED": "not under test"} for n, _ in orient.SECTIONS}}
    d["sections"]["SPEC"] = {**fields, "status": "X", "min_trade_usd": 1, "capital_usd": 1}
    orient.render(d)
    return [l for l in capsys.readouterr().out.splitlines() if "below_min_names" in l]


def test_orient_reports_the_rule_and_the_floor():
    f = orient.spec_fields({"frozen": {"vol_target_annual": 0.06,
                                       "below_min_names": "trade_eligible",
                                       "below_min_names_floor": 4}})
    assert f["below_min_names"] == "trade_eligible" and f["below_min_names_floor"] == 4
    assert f["below_min_names_absent"] is False
    absent = orient.spec_fields({"frozen": {"vol_target_annual": 0.06}})
    assert absent["below_min_names"] is None and absent["below_min_names_floor"] is None
    assert absent["below_min_names_absent"] is True
    null = orient.spec_fields({"frozen": {"vol_target_annual": 0.06, "below_min_names": None}})
    assert null["below_min_names"] is None and null["below_min_names_absent"] is False


def test_orient_prints_trade_eligible_with_its_floor_and_paper_only(capsys):
    f = orient.spec_fields({"frozen": {"vol_target_annual": 0.06,
                                       "below_min_names": "trade_eligible",
                                       "below_min_names_floor": 4}})
    lines = _render(capsys, f)
    assert len(lines) == 1
    assert "trade_eligible   floor 4   PAPER ONLY (CEF trial 55)" in lines[0]


def test_orient_prints_absent_as_absent_and_says_what_it_means(capsys):
    lines = _render(capsys, orient.spec_fields({"frozen": {"vol_target_annual": 0.06}}))
    assert len(lines) == 1 and "absent (read as 'flatten'" in lines[0]
    assert "floor" not in lines[0] and "PAPER ONLY" not in lines[0]
    lines = _render(capsys, orient.spec_fields({"frozen": {"vol_target_annual": 0.06,
                                                           "below_min_names": "hold"}}))
    assert lines[0].split()[-1] == "hold"
    lines = _render(capsys, orient.spec_fields({"frozen": {"vol_target_annual": 0.06,
                                                           "below_min_names": "flatten"}}))
    assert lines[0].split()[-1] == "flatten" and "absent" not in lines[0]


def test_orient_never_prints_a_written_null_as_absent(capsys):
    lines = _render(capsys, orient.spec_fields({"frozen": {"vol_target_annual": 0.06,
                                                           "below_min_names": None}}))
    assert len(lines) == 1 and "absent" not in lines[0] and lines[0].split()[-1] == "None"


def test_spec_reader_exposes_both_as_written_or_none():
    from scripts.cef import spec as S
    fr = S.spec()["frozen"]
    assert S.BELOW_MIN_NAMES == fr.get("below_min_names")
    assert S.BELOW_MIN_NAMES_FLOOR == fr.get("below_min_names_floor")
    if "below_min_names" not in fr:
        assert S.BELOW_MIN_NAMES is None                    # absent stays absent: no default
    if "below_min_names_floor" not in fr:
        assert S.BELOW_MIN_NAMES_FLOOR is None


def test_spec_reader_returns_the_value_as_written_and_none_only_when_absent():
    from scripts.cef import spec as S
    assert S._as_written("below_min_names", {}) is None
    assert S._as_written("below_min_names", {"below_min_names": "trade_eligible"}) == "trade_eligible"
    got = S._as_written("below_min_names_floor", {"below_min_names_floor": 4})
    assert got == 4 and type(got) is int                    # not cast: the registry checks int


@pytest.mark.parametrize("key", ["below_min_names", "below_min_names_floor"])
def test_spec_reader_refuses_a_written_null_naming_the_key(key):
    from scripts.cef import spec as S
    with pytest.raises(S.SpecError, match=f"frozen {key} is null"):
        S._as_written(key, {key: None})
