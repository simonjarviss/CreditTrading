"""The snapshot format and the privacy table of dashboard/README.md section 2."""
import copy
import json
from pathlib import Path

import pytest

from dashboard import snapshot as S

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_snapshot.json"


@pytest.fixture
def snap():
    return json.loads(FIXTURE.read_text())


def test_fixture_matches_schema(snap):
    assert S.validate(snap) == []


def test_fixture_carries_nothing_private(snap):
    assert S.find_private(snap) == []


def test_fixture_is_marked_synthetic(snap):
    assert snap["synthetic"] is True


def test_every_measured_figure_has_source_time_and_label(snap):
    def walk(n):
        if isinstance(n, dict) and "value" in n:
            assert n["source"] and n["read_at"] and n["label"] in S.LABELS
        elif isinstance(n, dict):
            for v in n.values():
                walk(v)
    for k in ("account", "pnl", "equity_history", "positions", "trades", "system"):
        walk(snap[k])


def test_unmeasured_and_absent_are_valid_readings(snap):
    snap["account"]["equity"] = {"UNMEASURED": "Alpaca account read failed"}
    snap["positions"] = {"absent": "book is flat"}
    assert S.validate(snap) == []


@pytest.mark.parametrize("mutate,expect", [
    (lambda s: s.pop("system"), "missing section system"),
    (lambda s: s.pop("book"), "missing top-level key 'book'"),
    (lambda s: s["account"]["equity"].update({"UNMEASURED": "x"}), "exactly one"),
    (lambda s: s["account"]["equity"].pop("source"), "names its source"),
    (lambda s: s["account"]["equity"].pop("read_at"), "read_at"),
    (lambda s: s["account"]["equity"].update({"label": "guess"}), "label"),
    (lambda s: s["account"]["equity"].update({"value": "100"}), "finite number"),
    (lambda s: s["account"]["equity"].update({"value": float("nan")}), "finite number"),
    (lambda s: s["positions"]["value"].append({"symbol": "bad symbol", "qty": 1}), "ticker"),
    (lambda s: s["trades"]["value"]["orders"].append({"symbol": "AAA", "side": "hold", "qty": 1, "status": "x"}), "side"),
    (lambda s: s["system"]["value"].update({"verdict": "MAYBE"}), "verdict"),
    (lambda s: s.update({"schema_version": "9"}), "schema_version"),
    (lambda s: s.update({"session_date": "Nov 6"}), "session_date"),
])
def test_bad_snapshots_are_named(snap, mutate, expect):
    mutate(snap)
    problems = S.validate(snap)
    assert any(expect in p for p in problems), problems


def test_a_gap_is_never_a_number(snap):
    snap["account"]["equity"] = {"UNMEASURED": "why", "value": 0}
    assert S.validate(snap)  # a value beside UNMEASURED is refused


@pytest.mark.parametrize("key", [
    "api_key", "ALPACA_SECRET_KEY", "token", "password", "account_number", "account_id", "key_id",
    "cusip", "permno", "hostname", "server", "vm_address", "vault", "subscription", "r2_endpoint",
    "client_order_id",
])
def test_forbidden_key_names_are_caught(snap, key):
    snap["system"]["value"][key] = "x"
    assert any("forbidden key" in p for p in S.find_private(snap))


@pytest.mark.parametrize("value,what", [
    ("10.0.12.34", "IPv4"),
    ("2001:db8:85a3:0:0:8a2e:370:7334", "IPv6"),
    ("24c4da2f21d9064a4c02b26e92046258", "hex"),
    ("PKABCDEFGHIJKLMNOP12", "Alpaca key"),
    ("PA3ABCDEF12345", "account number"),
    ("myvm.westus2.cloudapp.azure.com", "hostname"),
    ("https://example.com/x", "URL"),
    ("-----BEGIN PRIVATE KEY-----", "private key"),
    ("someone@example.com", "email"),
])
def test_forbidden_values_are_caught_anywhere(snap, value, what):
    snap["system"]["value"]["reason"] = f"note {value} end"
    found = S.find_private(snap)
    assert any(what.lower() in p.lower() for p in found), found


def test_privacy_check_reaches_nested_lists(snap):
    snap["trades"]["value"]["fills"][0]["note"] = "10.1.2.3"
    assert any("fills[0]" in p for p in S.find_private(snap))


def test_a_time_is_not_mistaken_for_an_address(snap):
    # HH:MM:SS inside an ISO time must not trip the IPv6 rule (the same care as ops/prod_state.py)
    assert S.find_private({"t": "2026-11-06T20:55:10Z"}) == []
