"""The snapshot format (0.2) and the privacy table of dashboard/README.md section 2.

Carried over from 0.1-draft (Lucy, PR #62): the reading convention, every forbidden key name
and value pattern, and the nested-list reach of the privacy check."""
import json
from pathlib import Path

import pytest

from dashboard import snapshot as S
from dashboard.fixtures import make_fixture

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_snapshot.json"


@pytest.fixture
def snap():
    return json.loads(FIXTURE.read_text())


def cef(s):
    return s["books"][0]


def test_fixture_matches_schema(snap):
    assert S.validate(snap) == []


def test_fixture_carries_nothing_private(snap):
    assert S.find_private(snap) == []


def test_fixture_is_marked_synthetic(snap):
    assert snap["synthetic"] is True


def test_fixture_is_what_the_exporter_writes_today(snap):
    """The committed fixture is regenerated from the exporter, never hand-edited."""
    assert make_fixture.make() == snap, "run: python3 -m dashboard.fixtures.make_fixture"


def test_every_measured_figure_has_source_time_and_label(snap):
    n = 0

    def walk(node):
        nonlocal n
        if isinstance(node, dict) and "value" in node:
            assert node["source"] and node["read_at"] and node["label"] in S.LABELS
            n += 1
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(snap)
    assert n >= 10


def test_unmeasured_and_absent_are_valid_readings(snap):
    cef(snap)["official"] = {"UNMEASURED": "eod_equity.csv: not found"}
    cef(snap)["risk"] = {"absent": "no report"}
    assert S.validate(snap) == []


@pytest.mark.parametrize("mutate,expect", [
    (lambda s: s.pop("books"), "missing top-level key 'books'"),
    (lambda s: s.update({"books": []}), "non-empty"),
    (lambda s: s["books"].append(dict(s["books"][0])), "duplicate book"),
    (lambda s: s["books"][0].pop("risk"), "missing 'risk'"),
    (lambda s: s["books"][0]["official"].update({"UNMEASURED": "x"}), "exactly one"),
    (lambda s: s["books"][0]["official"].pop("source"), "names its source"),
    (lambda s: s["books"][0]["official"].pop("read_at"), "read_at"),
    (lambda s: s["books"][0]["official"].update({"label": "guess"}), "label"),
    (lambda s: s["books"][0]["official"]["value"]["rows"].append({"date": "2026-11-21", "equity": "1", "change_usd": 1}),
     "equity"),
    (lambda s: s["books"][0]["official"]["value"]["rows"].append({"date": "2026-11-21", "equity": float("nan"),
                                                                  "change_usd": 1}), "equity"),
    (lambda s: s["books"][0]["session"]["value"]["positions"].update({"n": -1}), "positions"),
    (lambda s: s["books"][0]["session"]["value"]["positions"].pop("gross_usd"), "positions"),
    (lambda s: s["books"][0]["session"]["value"]["orders"].update({"n_filled": 1.5}), "orders"),
    (lambda s: s["books"][0]["session"]["value"].update({"n_notes": "two"}), "n_notes"),
    (lambda s: s["books"][0]["session"]["value"].update({"verdict": "MAYBE"}), "verdict"),
    (lambda s: s.update({"schema_version": "0.1-draft"}), "schema_version"),
    (lambda s: s.update({"exported_at_utc": "Nov 6"}), "exported_at_utc"),
])
def test_bad_snapshots_are_named(snap, mutate, expect):
    mutate(snap)
    problems = S.validate(snap)
    assert any(expect in p for p in problems), problems


def test_a_gap_is_never_a_number(snap):
    cef(snap)["official"] = {"UNMEASURED": "why", "value": {"rows": []}}
    assert S.validate(snap)  # a value beside UNMEASURED is refused


@pytest.mark.parametrize("key", [
    "api_key", "ALPACA_SECRET_KEY", "token", "password", "account_number", "account_id", "key_id",
    "cusip", "permno", "hostname", "server", "vm_address", "vault", "subscription", "r2_endpoint",
    "client_order_id", "order_id",
])
def test_forbidden_key_names_are_caught(snap, key):
    cef(snap)["session"]["value"][key] = "x"
    assert any("forbidden key" in p for p in S.find_private(snap))


@pytest.mark.parametrize("value,what", [
    ("10.0.12.34", "IPv4"),
    ("2001:db8:85a3:0:0:8a2e:370:7334", "IPv6"),
    ("24c4da2f21d9064a4c02b26e92046258", "hex"),
    ("b3a7e512-14a7-41cd-9dc8-1e3c40b85b9e", "UUID"),
    ("PKABCDEFGHIJKLMNOP12", "Alpaca key"),
    ("PA3ABCDEF12345", "account number"),
    ("myvm.westus2.cloudapp.azure.com", "hostname"),
    ("https://example.com/x", "URL"),
    ("-----BEGIN PRIVATE KEY-----", "private key"),
    ("someone@example.com", "email"),
    ("/home/quantt/quantt_state/cef", "home directory"),
])
def test_forbidden_values_are_caught_anywhere(snap, value, what):
    cef(snap)["session"]["value"]["close_basis"] = f"note {value} end"
    found = S.find_private(snap)
    assert any(what.lower() in p.lower() for p in found), found


def test_privacy_check_reaches_nested_lists(snap):
    cef(snap)["official"]["value"]["rows"][0]["basis"] = "10.1.2.3"
    assert any("rows[0]" in p for p in S.find_private(snap))


@pytest.mark.parametrize("key", ["symbol", "qty", "positions_after", "problems", "reason", "fails", "marks"])
def test_a_per_name_or_note_field_is_refused(snap, key):
    """Team lead, 2026-11-23: the public site shows aggregates only."""
    cef(snap)["session"]["value"][key] = "x"
    assert any("aggregates only" in p for p in S.find_private(snap))


def test_a_time_is_not_mistaken_for_an_address(snap):
    # HH:MM:SS inside an ISO time must not trip the IPv6 rule (the same care as ops/prod_state.py)
    assert S.find_private({"t": "2026-11-06T20:55:10Z"}) == []
