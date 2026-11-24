"""The performance page: provenance shown, gaps shown as gaps, nothing that can reach a broker.

Carried over from 0.1-draft (Lucy, PR #62): provenance on every figure, gaps never printed as
numbers, markup from a record escaped, a dirty snapshot refused with no page written, and the
AST checks that the dashboard code has no route to a broker or the network."""
import ast
import json
import re
from pathlib import Path

import pytest

from dashboard import build as B

DASH = Path(__file__).resolve().parents[1]
FIXTURE = DASH / "fixtures" / "sample_snapshot.json"


@pytest.fixture
def snap():
    return json.loads(FIXTURE.read_text())


def page(snap):
    return B.render(snap)


def book(snap, name):
    return next(b for b in snap["books"] if b["name"] == name)


def test_every_book_has_its_section(snap):
    h = page(snap)
    for title in ("Fixed Income Book", "Equity Cross-Asset Book", "Event Book", "Combined paper results",
                  "Strategies in simulation"):
        assert title in h, title
    for sym in ("AAA", "BBB", "CCC"):                   # aggregates only (team lead, 2026-11-23)
        assert sym not in h, sym
    assert "2 (1 long, 1 short)" in h and "1 sent: 1 filled in full, 0 not filled" in h


def test_every_figure_shows_its_source_and_read_time(snap):
    h = page(snap)
    assert "Alpaca end-of-day portfolio history, cef/eod_equity.csv" in h
    assert "21 November 2026, 03:40 New York time" in h and "broker-confirmed" in h


def test_synthetic_banner_only_when_synthetic(snap):
    assert "Synthetic data" in page(snap)
    snap["synthetic"] = False
    assert "Synthetic data" not in page(snap)


def test_a_gap_is_shown_as_not_measured_never_as_a_number(snap):
    book(snap, "cef")["official"] = {"UNMEASURED": "eod_equity.csv: read failed"}
    h = page(snap)
    assert "not measured" in h and "read failed" in h
    assert "$100,050" not in h                               # the book's equity is gone, not carried


def test_a_book_without_history_is_named_and_left_out_of_the_combined_figures(snap):
    h = page(snap)
    assert "Not yet in the combined figures: Event Book" in h
    # the combined equity is the two books' sum on their common sessions: 100,050 + 100,300
    assert "$200,350" in h


def test_the_newest_session_shows_its_after_close_reading_until_the_official_point_lands(snap):
    s = book(snap, "cef")["session"]["value"]
    s["date"] = "2026-11-23"
    s["equity_snapshot"]["change_usd"] = 123.0
    h = page(snap)
    assert "23 Nov 2026 session, after-close reading" in h and "+$123" in h
    s["date"] = "2026-11-20"                                 # official already covers it: no snapshot tile
    assert "after-close reading" not in page(snap)


def test_text_from_a_record_cannot_inject_markup(snap):
    book(snap, "cef")["risk"]["value"]["groups"] = {"<script>alert(1)</script>": 0.5}
    h = page(snap)
    assert "<script>alert" not in h and "&lt;script&gt;" in h


def test_the_page_loads_nothing_from_another_origin(snap):
    h = page(snap)
    # what the page LOADS: src= and <link href=. A plain link to another site (LinkedIn, GitHub) loads nothing.
    assert not re.search(r"(\bsrc\s*=|<link\b[^>]*\bhref\s*=)\s*[\"']?(https?:)?//", h, re.I)
    assert not re.search(r"url\(\s*[\"']?(https?:)?//", h, re.I)
    assert re.findall(r"<script[^>]*>", h) == ['<script src="/static/site.js" defer>']


def test_build_refuses_a_snapshot_with_a_secret_and_writes_nothing(snap, tmp_path):
    book(snap, "cef")["session"]["value"]["close_basis"] = "key 24c4da2f21d9064a4c02b26e92046258"
    src, out = tmp_path / "s.json", tmp_path / "out" / "index.html"
    src.write_text(json.dumps(snap))
    with pytest.raises(SystemExit, match="refused"):
        B.build(src, out)
    assert not out.exists()


def test_build_refuses_a_malformed_snapshot(snap, tmp_path):
    del snap["shadow"]
    src = tmp_path / "s.json"
    src.write_text(json.dumps(snap))
    with pytest.raises(SystemExit, match="shadow"):
        B.build(src, tmp_path / "i.html")


def test_cli_builds_the_fixture(tmp_path):
    out = tmp_path / "index.html"
    assert B.main([str(FIXTURE), "-o", str(out)]) == 0
    assert "Live performance" in out.read_text()


# ------------------------------------------------------------ read-only ----
STDLIB = {"__future__", "argparse", "csv", "datetime", "json", "math", "os", "re", "shutil", "sys", "html",
          "pathlib", "tempfile", "zoneinfo", "dashboard"}
CODE = ["build.py", "snapshot.py", "export.py", "metrics.py", "charts.py", "layout.py", "site.py"]


def _imports(path: Path) -> set:
    mods = set()
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    return mods


@pytest.mark.parametrize("name", CODE)
def test_dashboard_code_imports_only_the_standard_library(name):
    assert _imports(DASH / name) <= STDLIB, _imports(DASH / name) - STDLIB


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


@pytest.mark.parametrize("name", CODE)
def test_dashboard_code_has_no_route_to_a_broker_or_the_network(name):
    bad = ("quantt", "ops", "alpaca", "socket", "urllib", "requests", "subprocess", "paramiko", "system",
           "dotenv", "environ", "getenv", "submit_order", "place_order", "cancel_order", "replace_order", "post",
           "urlopen", "http")
    used = _identifiers(DASH / name)
    assert not [w for w in bad if w in used], [w for w in bad if w in used]
