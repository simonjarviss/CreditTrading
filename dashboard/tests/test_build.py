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


@pytest.fixture(autouse=True)
def record_from_the_fixtures_first_send(monkeypatch):
    """The fixture's books trade from 17 Nov 2026, before the shipped RECORD_START (24 Nov), which would
    leave them no session. Tests of the record start set their own."""
    monkeypatch.setattr(B, "RECORD_START", "2026-11-17")


def page(snap):
    return B.render(snap)


def book(snap, name):
    return next(b for b in snap["books"] if b["name"] == name)


def test_every_book_has_its_section(snap):
    h = page(snap)
    for title in ("Fixed Income Book", "Equity Cross-Asset Book", "Event Book", "Portfolio since", "Fund facts",
                  "Key figures", "Latest session", "Sources and method"):
        assert title in h, title
    for sym in ("AAA", "BBB", "CCC"):                   # aggregates only (team lead, 2026-11-23)
        assert sym not in h, sym
    # Team lead, 2026-11-24: an investor page, without each book's own tables or the simulation scoreboard.
    assert "Strategies in simulation" not in h and "Session of" not in h and "Gross exposure, risk report" not in h
    cef = h.split("Latest session", 1)[1].split("Fixed Income Book", 1)[1].split("</tr>", 1)[0]
    assert '2 <span class="meta">(1 long, 1 short)</span>' in cef and "1 of 1" in cef


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


def test_the_portfolio_takes_each_book_from_its_first_send_and_the_event_book_on_its_readings(snap):
    """Team lead, 2026-11-24: one portfolio line, the event book "included automatically". The event
    book has no end-of-day history, so it joins on its after-close readings, labelled; a session a
    trading book has no record for is left out and counted."""
    h = page(snap)
    assert "Portfolio since 17 Nov 2026" in h
    head = h.split("Key figures", 1)[1].split("</thead>", 1)[0]
    assert "Equity Cross-Asset Book<br><span class=\"meta\">from 19 Nov 2026" in head
    assert "Event Book<br><span class=\"meta\">from 23 Nov 2026" in head
    assert "Fixed Income Book<br>" not in head                       # it starts with the portfolio
    assert "1 session left out" in h and "The Event Book uses these readings" in h


def test_the_portfolio_view_switch_hides_the_books_until_chosen(snap):
    h = page(snap)
    assert 'class="view-switch" role="group" aria-label="Chart view" hidden' in h
    assert h.count('data-view="portfolio"') >= 2                  # the growth chart and its legend
    assert 'class="series bk"' in h and "By book" in h


def test_the_portfolio_shows_the_regular_figures_and_needs_twenty_sessions_for_ratios(snap):
    """Team lead, 2026-11-24: "the portfolio results is too many analytics", then "it should still demonstrate
    the live trading, risk etc. (all regular metrics) for our portfolio and books". Four headline figures,
    one chart, the factsheet's return and risk measures for the portfolio and each book, and the latest
    session's trading and exposure."""
    h = page(snap)
    labels = ("Sessions", "Return, time-weighted", "Annualised return", "P&amp;L", "Sessions with a gain",
              "Volatility, annualised", "Sharpe ratio", "Sortino ratio", "Maximum drawdown", "Current drawdown")
    table = h.split("Key figures", 1)[1].split("</table>", 1)[0]
    assert re.findall(r"<tr><td>([^<]+)</td>", table) == list(labels)
    assert re.findall(r'colspan="\d+">([^<]+)</td>', table) == ["Return", "Risk"]
    assert "needs 20 sessions, has 4" in h                       # the fixture's portfolio has 4 sessions
    kpis = h.split('class="figures kpis"', 1)[1].split("</div></div></div>", 1)[0]
    assert kpis.count('class="fig"') == 4
    for gone in ("Drawdown from the peak", "Monthly returns", "Correlation of daily returns", "Contribution to",
                 "Value at risk", "Skewness", "Profit factor", "Calmar"):
        assert gone not in h, gone

def test_an_unreadable_book_is_left_out_of_the_portfolio_and_named(snap):
    """Release-check review of 904bd35: withholding the whole portfolio over one unreadable record hid
    it until a hand repair. The other books are shown, and the missing one is named above them."""
    book(snap, "c4")["official"] = {"UNMEASURED": "eod_equity.csv: not a number"}
    h = page(snap)
    assert "Not included: Equity Cross-Asset Book, its record could not be read" in h
    assert "Cumulative return" in h and "Equity Cross-Asset Book<br>" not in h.split("Key figures", 1)[1].split("</thead>", 1)[0]


def test_the_newest_session_shows_its_after_close_reading_until_the_official_point_lands(snap):
    s = book(snap, "cef")["session"]["value"]
    s["date"] = "2026-11-23"
    s["equity_snapshot"]["change_usd"] = 123.0
    h = page(snap)
    latest = h.split("Latest session", 1)[1]
    assert "23 Nov 2026" in latest and "+$123</span> <span class=\"meta\">after-close reading" in latest
    s["date"] = "2026-11-20"                                 # official already covers it: no snapshot tile
    cef_row = page(snap).split("Latest session", 1)[1].split("Fixed Income Book", 1)[1].split("</tr>", 1)[0]
    assert "after-close reading" not in cef_row and "official" in cef_row


def test_text_from_a_record_cannot_inject_markup(snap):
    book(snap, "cef")["official"]["source"] = "<script>alert(1)</script>"
    h = page(snap)
    assert "<script>alert" not in h and "&lt;script&gt;" in h


def test_the_page_loads_nothing_from_another_origin(snap):
    h = page(snap)
    # what the page LOADS: src= and <link href=. A plain link to another site (LinkedIn, GitHub) loads nothing.
    assert not re.search(r"(\bsrc\s*=|<link\b[^>]*\bhref\s*=)\s*[\"']?(https?:)?//", h, re.I)
    assert not re.search(r"url\(\s*[\"']?(https?:)?//", h, re.I)
    assert re.fullmatch(r'<script src="/static/site\.js\?v=[0-9a-f]{12}" defer>', "".join(re.findall(r"<script[^>]*>", h)))


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
          "pathlib", "tempfile", "zoneinfo", "hashlib", "contextlib", "dashboard"}
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


def test_the_return_is_named_time_weighted_and_shown_apart_from_the_pnl(snap):
    """2026-11-24: the portfolio read "+0.06% (-$472)", both right and read as an error."""
    h = page(snap)
    kpis = h.split('class="figures kpis"', 1)[1].split("</div></div></div>", 1)[0]
    assert "Return, time-weighted" in kpis and '<div class="l">P&amp;L</div>' in kpis
    assert not re.search(r"Return since [^<]*\(", h)


def test_an_after_close_books_session_pnl_reads_the_same_in_its_tile_and_its_row(snap):
    """Release-check review of 596ba7f: the tile and the row took Alpaca's change, the record the move
    between readings, so one session read two ways."""
    ev = book(snap, "events")
    ev["session"]["value"]["equity_snapshot"]["change_usd"] = -90.0                   # Alpaca's, from its close
    ev["after_close"]["value"]["rows"][-1]["change_usd"] = 200.0                      # the record's, between readings
    h = page(snap)
    row = h.split("Latest session", 1)[1].split("Event Book", 1)[1].split("</tr>", 1)[0]
    assert "+$200" in row and "−$90" not in row and "−$90" not in h


def test_the_record_starts_on_the_ruled_date():
    """Team lead, 2026-11-24: "we should use today as the first day for all books, but keep the old records too"."""
    assert re.search(r'^RECORD_START = "2026-11-24"$', Path(B.__file__).read_text(), re.M)  # the shipped value


def test_the_record_counts_from_its_start_and_keeps_the_earlier_record_apart(snap, monkeypatch):
    """From 20 Nov: the Fixed Income Book's 20 Nov session (-$50) is the record; its 17-19 Nov sessions
    (+$250, -$350, +$200) are the earlier record, shown apart and summed apart."""
    monkeypatch.setattr(B, "RECORD_START", "2026-11-20")
    pf = B.portfolio(snap)
    cef = next(x for x in pf["books"] if x["b"]["name"] == "cef")
    assert cef["first"] == "2026-11-20" and cef["base"] == "2026-11-19" and cef["p"]["pnl"] == -50.0
    ev = next(x for x in pf["books"] if x["b"]["name"] == "events")
    assert ev["first"] == "2026-11-23"                                   # a book that starts later joins later
    old = B.portfolio(snap, before="2026-11-20")
    ocef = next(x for x in old["books"] if x["b"]["name"] == "cef")
    assert ocef["first"] == "2026-11-17" and ocef["p"]["last_date"] == "2026-11-19" and ocef["p"]["pnl"] == 100.0
    assert [why for b, why in old["excluded"]] == ["it began trading on 23 Nov 2026"]
    h = page(snap)
    assert "Portfolio since 20 Nov 2026" in h
    earlier = h.split("Record before 20 Nov 2026", 1)[1].split("</table>", 1)[0]
    assert "17 Nov 2026" in earlier and "19 Nov 2026" in earlier and "+$100" in earlier


def test_before_its_first_session_closes_the_record_says_when_it_starts(snap, monkeypatch):
    """24 Nov 2026, before the close: no session of the record yet. The page says when it starts, and
    shows the latest session and the earlier record; it never shows an empty figure."""
    monkeypatch.setattr(B, "RECORD_START", "2026-11-24")
    h = page(snap)
    assert "Portfolio since 24 Nov 2026" in h and "First figures after the close of 24 Nov 2026" in h
    assert "Latest session" in h and "Record before 24 Nov 2026" in h and "Key figures" not in h
    earlier = h.split("Record before 24 Nov 2026", 1)[1].split("</table>", 1)[0]
    for title in ("Fixed Income Book", "Equity Cross-Asset Book", "Event Book"):
        assert title in earlier, title


def test_the_fund_facts_sum_the_books_only_when_every_book_is_read_and_priced(snap):
    """Team lead, 2026-11-24: "show our fund statistics". Capital and exposure are the books' sums, or not
    measured; never a sum over part of the portfolio."""
    h = page(snap)
    facts = h.split('<dl class="facts">', 1)[1].split("</dl>", 1)[0]
    assert "Record starts" in facts and "Capital, paper" in facts and "Gross exposure" in facts
    assert "not measured" not in facts
    book(snap, "events")["session"] = {"UNMEASURED": "events/2026-11-23/verify.json: not JSON"}
    facts = page(snap).split('<dl class="facts">', 1)[1].split("</dl>", 1)[0]
    cap = facts.split("Capital, paper", 1)[1].split("</dd>", 1)[0]
    assert "not measured" in cap and "$" not in cap
