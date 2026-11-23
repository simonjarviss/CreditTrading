"""The page generator: provenance shown, gaps shown as gaps, nothing active, nothing that can reach a broker."""
import ast
import copy
import datetime as dt
import json
import re
import sys
from pathlib import Path

import pytest

from dashboard import build as B

DASH = Path(__file__).resolve().parents[1]
FIXTURE = DASH / "fixtures" / "sample_snapshot.json"
NOW = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def snap():
    return json.loads(FIXTURE.read_text())


def page(snap):
    return B.render(snap, NOW)


def test_page_shows_each_required_section(snap):
    h = page(snap)
    for text in ("System status", "Account value and daily P&amp;L", "Positions", "Last day's trades and fills", "Data freshness"):
        assert text in h, text
    for sym in ("AAA", "BBB", "CCC", "DDD"):
        assert sym in h


def test_every_figure_shows_its_source_and_date(snap):
    h = page(snap)
    assert h.count("FIXTURE: invented") >= 7
    assert "read 2026-11-06T21:30:00Z" in h and "broker-confirmed" in h


def test_synthetic_banner_only_when_synthetic(snap):
    assert "SYNTHETIC FIXTURE" in page(snap)
    snap["synthetic"] = False
    assert "SYNTHETIC FIXTURE" not in page(snap)


def test_a_gap_is_shown_as_missing_never_as_a_number(snap):
    h = page(snap)
    assert "MISSING (unmeasured)" in h  # the fixture's auction P&L
    snap["account"]["equity"] = {"UNMEASURED": "Alpaca account read failed"}
    h2 = page(snap)
    assert "Alpaca account read failed" in h2
    assert "$100,412.50" not in h2.split("Account value and daily")[1].split("P&amp;L, official")[0]


def test_absent_positions_read_as_none_not_empty_table(snap):
    snap["positions"] = {"absent": "book is flat"}
    assert "book is flat" in page(snap)


def test_stale_snapshot_is_flagged(snap):
    snap["exported_at_utc"] = "2026-11-01T22:45:00Z"
    assert "STALE" in page(snap)
    assert "STALE" not in page(json.loads(FIXTURE.read_text()))


def test_text_from_a_snapshot_cannot_inject_markup(snap):
    snap["system"]["value"]["reason"] = "<script>alert(1)</script>"
    h = page(snap)
    assert "<script>alert" not in h and "&lt;script&gt;" in h


def test_page_has_no_script_and_loads_nothing_external(snap):
    h = page(snap)
    assert "<script" not in h.lower()
    assert not re.search(r"(src|href)\s*=\s*[\"']?(https?:)?//", h, re.I)
    assert "http" not in h.lower()


def test_build_refuses_a_snapshot_with_a_secret_and_writes_nothing(snap, tmp_path):
    snap["system"]["value"]["reason"] = "key 24c4da2f21d9064a4c02b26e92046258"
    src, out = tmp_path / "s.json", tmp_path / "out" / "index.html"
    src.write_text(json.dumps(snap))
    with pytest.raises(SystemExit, match="refused"):
        B.build(src, out, NOW)
    assert not out.exists()


def test_build_refuses_a_malformed_snapshot(snap, tmp_path):
    del snap["pnl"]
    src = tmp_path / "s.json"
    src.write_text(json.dumps(snap))
    with pytest.raises(SystemExit, match="missing section pnl"):
        B.build(src, tmp_path / "i.html", NOW)


def test_cli_builds_the_fixture(tmp_path):
    out = tmp_path / "index.html"
    assert B.main([str(FIXTURE), "-o", str(out)]) == 0
    assert "Credit book" in out.read_text()


# ------------------------------------------------------------ read-only ----
ALLOWED = {"__future__", "argparse", "datetime", "json", "re", "sys", "html", "pathlib", "dashboard"}


def _imports(path: Path) -> set:
    mods = set()
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    return mods


@pytest.mark.parametrize("name", ["build.py", "snapshot.py"])
def test_dashboard_code_imports_only_the_standard_library(name):
    assert _imports(DASH / name) <= ALLOWED, _imports(DASH / name) - ALLOWED


def _identifiers(path: Path) -> set:
    """Every name the code uses (variables, attributes, imports), not its prose or docstrings."""
    ids = set()
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, ast.Name):
            ids.add(n.id.lower())
        elif isinstance(n, ast.Attribute):
            ids.add(n.attr.lower())
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            ids |= {a.name.lower() for a in n.names} | {(getattr(n, "module", None) or "").lower()}
    return ids


@pytest.mark.parametrize("name", ["build.py", "snapshot.py"])
def test_dashboard_code_has_no_route_to_a_broker_or_the_network(name):
    bad = ("quantt", "ops", "alpaca", "socket", "urllib", "requests", "subprocess", "paramiko", "system",
           "dotenv", "environ", "getenv", "submit_order", "place_order", "cancel_order", "replace_order", "post", "urlopen")
    used = _identifiers(DASH / name)
    assert not [w for w in bad if w in used], [w for w in bad if w in used]
