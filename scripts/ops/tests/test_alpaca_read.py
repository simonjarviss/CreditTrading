"""The GET-only reader: its parsed output equals AlpacaClient's on the same fixture responses.

WHY THESE TESTS (team lead, 2026-11-09)
--------------------------------------
`scripts/ops/alpaca_read.py` is the report job's copy of AlpacaClient's reads, kept apart
because the job's import closure must not reach `quantt.broker` (`AlpacaClient` holds
`submit_order`). The only licence for a copy is that it cannot drift unseen. So every read
here runs through BOTH clients against one fixture server, row for row and raise for raise:
the EOD series mapped to sessions, the FILL pages, the calendar, the SIP daily bars frame,
the distributions and the strict corporate-action read. If either side changes, the
equality test fails. The second half pins what makes the reader safe to give to a job: GET
only, two hosts only, keys from the process environment only, no key in any message, and a
public surface of exactly the reads attribution needs.

Hermetic: one fake server answers both a fake `requests`-like session (AlpacaClient) and a
fake transport (AlpacaReader). The root conftest's netguard fails any test that opens a
socket. The fixture keys are literals in this file; no real key file is read.
"""
from __future__ import annotations

import ast
import datetime as dt
import http.client
import io
import json
import urllib.request
import urllib.response
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from quantt.broker import alpaca as AL
from quantt.broker import alpaca_probe as PROBE
from scripts.ops import alpaca_read as AR
from scripts.rv import alpaca_daily as AD

REPO = Path(__file__).resolve().parents[3]
READER_FILE = REPO / "scripts" / "ops" / "alpaca_read.py"
NY = ZoneInfo("America/New_York")
KEY = "KEYID-must-never-appear-0123"
SECRET = "SECRET-must-never-appear-4567"
D = dt.date


class FakeResp:
    def __init__(self, status, text):
        self.status_code = status
        self.text = text

    def json(self):
        return json.loads(self.text)


class Server:
    """One table of canned answers, {path: payload or callable(params)}, for both clients.
    Unknown path: 404. `status` overrides the HTTP status of one call (a list, consumed)."""

    def __init__(self, table):
        self.table = table
        self.calls = []
        self.status_queue = []

    def respond(self, path, params):
        self.calls.append((path, {k: str(v) for k, v in params.items()}))
        if self.status_queue:
            status, text = self.status_queue.pop(0)
            return status, text
        v = self.table.get(path)
        if v is None:
            return 404, json.dumps({"message": "not found"})
        payload = v({k: str(val) for k, val in params.items()}) if callable(v) else v
        return 200, json.dumps(payload)

    # as AlpacaClient's requests.Session stand-in
    headers: dict = {}

    def get(self, url, params=None, timeout=None):
        base = next(b for b in (AL.PAPER_BASE, AL.DATA_BASE) if url.startswith(b + "/"))
        status, text = self.respond(url[len(base):], params or {})
        return FakeResp(status, text)


def reader_for(server, book="cef", sleep=lambda s: None):
    def transport(url, headers, timeout):
        parts = urlsplit(url)
        assert f"{parts.scheme}://{parts.netloc}" in (AR.PAPER_BASE, AR.DATA_BASE)
        assert headers["APCA-API-KEY-ID"] == KEY and headers["APCA-API-SECRET-KEY"] == SECRET
        return server.respond(parts.path, dict(parse_qsl(parts.query)))
    return AR.AlpacaReader(book, key_id=KEY, secret=SECRET, transport=transport, sleep=sleep)


def client_for(server, tmp_path, book="cef"):
    env = tmp_path / f"{book}.env"
    if not env.exists():
        kid, sec = PROBE.env_names(book)
        env.write_text(f"{kid}={KEY}\n{sec}={SECRET}\n")
    return AL.AlpacaClient(book, env, session=_Sess(server), sleep=lambda s: None)


class _Sess:
    """The minimum `requests.Session` shape AlpacaClient uses. `allow_redirects`: PR #79
    (2026-11-10) makes AlpacaClient pass allow_redirects=False on every call, and a fake
    without the keyword raises TypeError there. The fake server never redirects, so the value
    changes nothing it answers; accepting it keeps this equality proof valid on either side of
    that merge."""

    def __init__(self, server):
        self.server = server
        self.headers = {}

    def get(self, url, params=None, timeout=None, allow_redirects=True):
        return self.server.get(url, params=params, timeout=timeout)


def stamp(d: dt.date) -> int:
    """The 1D stamp Alpaca writes for a session: 20:00 New York on the session date."""
    return int(dt.datetime(d.year, d.month, d.day, 20, tzinfo=NY).timestamp())


# ------------------------------------------------------------------ fixtures

SESSIONS = [D(2026, 9, 24), D(2026, 9, 25), D(2026, 9, 28), D(2026, 9, 29), D(2026, 9, 30),
            D(2026, 10, 1), D(2026, 10, 2)]
PRE_FUNDED = SESSIONS[:2]                       # equity 0: before funding
FUNDED = SESSIONS[2:]
EQUITY = {d: 100000.0 + i * 37.5 for i, d in enumerate(FUNDED)}


def calendar(params):
    lo, hi = D.fromisoformat(params["start"]), D.fromisoformat(params["end"])
    return [{"date": d.isoformat(), "open": "09:30", "close": "16:00"}
            for d in SESSIONS if lo <= d <= hi]


def eod():
    return {"timestamp": [stamp(d) for d in SESSIONS],
            "equity": [0.0 if d in PRE_FUNDED else str(EQUITY[d]) for d in SESSIONS],
            "profit_loss": [0.0] * len(SESSIONS), "profit_loss_pct": [0.0] * len(SESSIONS),
            "base_value": 100000.0, "timeframe": "1D"}


def fill_row(i, date=D(2026, 9, 29), side="buy"):
    return {"id": f"{i:06d}::x{i}", "activity_type": "FILL", "order_id": f"o{i}", "symbol": f"S{i % 7}",
            "side": side, "qty": "10", "price": "20.50", "cum_qty": "10", "leaves_qty": "0",
            "transaction_time": f"{date.isoformat()}T20:52:0{i % 10}.123456Z", "type": "fill",
            "order_status": "filled"}


# 250 rows across pages, with the last row of each full page served again as the
# first row of the next page: both readers must dedupe by id and never pass a repeated token.
FILL_ROWS = [fill_row(i) for i in range(250)]


def fills(params):
    rows = FILL_ROWS
    size = int(params["page_size"])
    start = 0
    if "page_token" in params:
        ids = [r["id"] for r in rows]
        start = ids.index(params["page_token"])       # repeat the token's own row
    page = rows[start:start + size]
    return page


def fee_row(i):
    return {"id": f"F{i:06d}", "activity_type": "FEE", "date": "2026-09-29", "net_amount": "-0.05",
            "description": "REG fee", "qty": None, "symbol": None, "status": "executed", "proceed": "100"}


FEE_ROWS = [fee_row(i) for i in range(130)]


def fees(params):
    size = int(params["page_size"])
    start = 0
    if "page_token" in params:
        ids = [r["id"] for r in FEE_ROWS]
        start = ids.index(params["page_token"]) + 1
    return FEE_ROWS[start:start + size]


def bars_response(params):
    symbols = params["symbols"].split(",")
    assert params["feed"] == "sip" and params["adjustment"] == "raw" and params["timeframe"] == "1Day"
    # 2026-09-28 04:00Z = midnight New York EDT
    days = [("2026-09-28T04:00:00Z", 10.0), ("2026-09-29T04:00:00Z", 10.5), ("2026-09-30T04:00:00Z", 11.25)]
    out = {}
    for s in symbols:
        out[s] = [{"t": t, "o": c, "h": c + 0.1, "l": c - 0.1, "c": c, "v": 12345, "n": 5, "vw": c}
                  for t, c in days]
    return {"bars": out, "next_page_token": None}


CA_DIV_PAGE_1 = {
    "corporate_actions": {
        "cash_dividends": [
            {"id": "div-1", "symbol": "AAA", "ex_date": "2026-09-15", "rate": "0.1250", "special": False,
             "foreign": False, "process_date": "2026-09-30", "record_date": "2026-09-16",
             "payable_date": "2026-09-30", "sub_type": "regular"},
            {"id": "div-2", "symbol": "BBB", "ex_date": "2026-09-16", "rate": 0.07, "process_date": "2026-09-30"},
        ],
        "capital_gains_distributions": [
            {"id": "cg-1", "symbol": "AAA", "ex_date": "2026-09-20",
             "long_term_rate": "0.20", "short_term_rate": "0.05", "process_date": "2026-09-30"},
        ],
    },
    "next_page_token": "tok-2"}
CA_DIV_PAGE_2 = {
    "corporate_actions": {
        "cash_dividends": [
            {"id": "div-3", "symbol": "AAA", "ex_date": "2026-09-29", "rate": 0.3, "special": True,
             "process_date": "2026-10-05"},
            {"id": "div-2", "symbol": "BBB", "ex_date": "2026-09-16", "rate": 0.07, "process_date": "2026-09-30"},
        ],
    },
    "next_page_token": None}

CA_PAGE_1 = {
    "corporate_actions": {
        "forward_splits": [
            {"id": "fs-1", "symbol": "AAA", "ex_date": "2026-09-10", "process_date": "2026-09-11",
             "new_rate": 2, "old_rate": 1, "record_date": "2026-09-11"},
            {"id": "fs-other", "symbol": "ZZZ", "ex_date": "2026-09-10", "process_date": "2026-09-11",
             "new_rate": 3, "old_rate": 1},
        ],
        "reverse_splits": [
            {"id": "rs-1", "symbol": "BBB", "new_symbol": "BBBX", "ex_date": "2026-09-12",
             "process_date": "2026-09-13", "old_rate": 4, "new_rate": 1},
        ],
        "reorganizations": [
            {"id": "ro-1", "symbol": "CCC", "effective_date": "2026-09-14", "process_date": "2026-09-15",
             "stock_movements": [{"symbol": "AAA", "cusip": "123456789", "new_rate": 1.5},
                                 {"symbol": "", "cusip": "987654321"}]},
        ],
    },
    "next_page_token": "ca-2"}
CA_PAGE_2 = {
    "corporate_actions": {
        "cash_mergers": [
            {"id": "cm-1", "acquiree_symbol": "AAA", "acquirer_symbol": "", "effective_date": "2026-09-20",
             "process_date": "2026-09-21", "rate": 25.0},
            {"id": "cm-2", "acquiree_symbol": "OTH", "acquirer_symbol": None, "effective_date": "2026-09-20",
             "process_date": "2026-09-21", "rate": 12.0},
        ],
        "name_changes": [
            {"id": "nc-1", "old_symbol": "OLD", "new_symbol": "AAA", "process_date": "2026-09-22"},
        ],
        "forward_splits": [
            {"id": "fs-1", "symbol": "AAA", "ex_date": "2026-09-10", "process_date": "2026-09-11",
             "new_rate": 2, "old_rate": 1, "record_date": "2026-09-11"},
        ],
    },
    "next_page_token": ""}


def corporate(params):
    types = params["types"]
    token = params.get("page_token")
    if "cash_dividend" in types:
        return CA_DIV_PAGE_2 if token == "tok-2" else CA_DIV_PAGE_1
    return CA_PAGE_2 if token == "ca-2" else CA_PAGE_1


def table():
    return {"/v2/calendar": calendar, "/v2/account/portfolio/history": eod(),
            "/v2/account/activities/FILL": fills, "/v2/account/activities/FEE": fees,
            "/v2/stocks/bars": bars_response, "/v1/corporate-actions": corporate}


# The DST change (2026-11-01): two EDT sessions, stamped 00:00Z the next day, then three EST
# sessions, stamped 01:00Z the next day. All five are 20:00 New York, by `stamp`.
WINTER = [D(2026, 10, 29), D(2026, 10, 30), D(2026, 11, 2), D(2026, 11, 3), D(2026, 11, 4)]


def _winter_table():
    def cal(params):
        lo, hi = D.fromisoformat(params["start"]), D.fromisoformat(params["end"])
        return [{"date": d.isoformat(), "open": "09:30", "close": "16:00"} for d in WINTER if lo <= d <= hi]

    return {"/v2/calendar": cal,
            "/v2/account/portfolio/history": {
                "timestamp": [stamp(d) for d in WINTER], "equity": [str(100000.0 + i) for i in range(5)],
                "profit_loss": [0.0] * 5, "profit_loss_pct": [0.0] * 5, "base_value": 100000.0, "timeframe": "1D"}}


@pytest.fixture
def both(tmp_path):
    server = Server(table())
    return server, reader_for(server), client_for(server, tmp_path)


# ------------------------------------------------------------------ equality

def test_eod_history_equals_the_clients_and_maps_stamps_to_ny_sessions(both):
    _, reader, client = both
    win = D(2026, 9, 1), D(2026, 10, 2)
    got, want = reader.eod_equity_history(*win), client.eod_equity_history(*win)
    assert [tuple(p) for p in got] == [tuple(p) for p in want]
    # the fixture funds on 2026-09-28; the leading zeros are dropped, and each stamp's
    # New York date is its session, independently of either client.
    assert [p.date for p in got] == FUNDED
    assert [p.equity for p in got] == [EQUITY[d] for d in FUNDED]


def test_eod_window_filter_equals_the_clients(both):
    _, reader, client = both
    win = D(2026, 9, 29), D(2026, 9, 30)
    got = reader.eod_equity_history(*win)
    assert [tuple(p) for p in got] == [tuple(p) for p in client.eod_equity_history(*win)]
    assert [p.date for p in got] == [D(2026, 9, 29), D(2026, 9, 30)]


def test_winter_stamps_are_equal_in_both_and_land_on_their_ny_sessions(tmp_path):
    """Pin (no code changes with it): the reader's 20:00 New York rule across the DST
    change. Every EOD stamp since 2026-11-01 is 01:00Z, and all the fixtures above are EDT
    (00:00Z), so a reader put back on "exactly 00:00 UTC" passed them while it refused every
    live winter point. Mutating `eod_equity_history` that way fails this test."""
    server = Server(_winter_table())
    win = D(2026, 10, 1), D(2026, 11, 6)
    got = reader_for(server).eod_equity_history(*win)
    assert [tuple(p) for p in got] == [tuple(p) for p in client_for(server, tmp_path).eod_equity_history(*win)]
    assert [p.date for p in got] == WINTER
    assert [p.stamp.hour for p in got] == [0, 0, 1, 1, 1]            # two EDT sessions, then EST


@pytest.mark.parametrize("day,shift,why", [
    (D(2026, 11, 3), -3600, "a winter 00:00Z stamp is 19:00 New York"),
    (D(2026, 10, 30), +3600, "a summer 01:00Z stamp is 21:00 New York"),
], ids=["winter-00Z", "summer-01Z"])
def test_a_stamp_off_20_00_new_york_raises_in_both_either_side_of_dst(tmp_path, day, shift, why):
    """Pin: as above, the refusal side. A stamp that is 20:00 in the other season's offset
    is exactly what would file a session under the wrong date."""
    t = _winter_table()
    t["/v2/account/portfolio/history"]["timestamp"] = [stamp(d) + (shift if d == day else 0) for d in WINTER]
    server = Server(t)
    win = D(2026, 10, 1), D(2026, 11, 6)
    with pytest.raises(AR.UnexpectedResponse, match="not 20:00:00 local"):
        reader_for(server).eod_equity_history(*win)
    with pytest.raises(AL.AlpacaError):
        client_for(server, tmp_path).eod_equity_history(*win)


def test_calendar_equals_the_clients(both):
    _, reader, client = both
    win = D(2026, 9, 28), D(2026, 10, 2)
    assert reader.calendar(*win) == client.calendar(*win)


def test_fills_pagination_equals_the_clients_and_dedupes(both):
    server, reader, client = both
    day = D(2026, 9, 29)
    got = reader.activities_fills(day)
    assert got == client.activities_fills(day)
    assert len(got) == 250 and len({a["id"] for a in got}) == 250
    pages = [p for p, _ in server.calls if p.endswith("activities/FILL")]
    assert len(pages) >= 6                                         # both clients paged 3 pages each


def test_fetch_bars_frame_equals_alpaca_dailys(both):
    server, reader, client = both
    syms = [f"S{i}" for i in range(25)]                             # two chunks of 20
    win = D(2026, 9, 28), D(2026, 9, 30)
    pd.testing.assert_frame_equal(AR.fetch_bars(reader, syms, *win), AD.fetch_bars(client, syms, *win))
    # and the module-level reads through the reader's own _get match AD's through it
    pd.testing.assert_frame_equal(AD.fetch_bars(reader, syms, *win), AR.fetch_bars(reader, syms, *win))
    assert any(p == "/v2/stocks/bars" and len(q["symbols"].split(",")) == 20 for p, q in server.calls)


def test_distributions_equal_the_clients_across_pages(both):
    _, reader, client = both
    win = D(2026, 6, 1), D(2026, 12, 1)
    got = reader.distributions(["AAA", "BBB"], *win)
    assert got == client.distributions(["AAA", "BBB"], *win)
    assert [e["id"] for e in got] == ["div-1", "cg-1", "div-3", "div-2"]
    cg = next(e for e in got if e["id"] == "cg-1")
    assert cg["amount"] == pytest.approx(0.25) and cg["kind"] == "capital_gains_distribution"


def test_corporate_actions_equal_the_clients_and_keep_parties(both):
    _, reader, client = both
    win = D(2026, 1, 1), D(2026, 12, 31)
    got = reader.corporate_actions(["AAA", "BBB"], *win)
    assert got == client.corporate_actions(["AAA", "BBB"], *win)
    ids = {e["id"] for e in got}
    assert ids == {"fs-1", "rs-1", "ro-1", "cm-1", "nc-1"}       # ZZZ's and OTH's rows are read and dropped
    ro = next(e for e in got if e["id"] == "ro-1")
    # the reorganization's ticker-less leg names nobody; its AAA leg is "allocated"
    assert ro["parties"] == [["CCC", "subject"], ["AAA", "allocated"]]


def test_rows_that_name_nobody_of_ours_are_not_read_further(tmp_path):
    t = table()
    bad = json.loads(json.dumps(CA_PAGE_2))
    bad["corporate_actions"]["forward_splits"].append(
        {"id": None, "symbol": "NOBODY", "ex_date": "garbage", "process_date": "garbage"})
    t["/v1/corporate-actions"] = (lambda params: CA_PAGE_1 if params.get("page_token") != "ca-2"
                                  and "cash_dividend" not in params["types"] else bad)
    # the malformed row names NOBODY, so a held symbol's read is unaffected, in both
    server = Server(t)
    got = reader_for(server).corporate_actions(["AAA", "BBB"], D(2026, 1, 1), D(2026, 12, 31))
    want = client_for(server, tmp_path).corporate_actions(["AAA", "BBB"], D(2026, 1, 1), D(2026, 12, 31))
    assert got == want


# ------------------------------------------------------------------ both raise on the same shapes

def _bad_eod(**kw):
    body = eod()
    body.update(kw)
    return body


BAD_EOD = [
    {"timeframe": "1Min"},                                                   # asked for 1D
    {"timestamp": [stamp(d) + 3600 for d in SESSIONS]},                      # not 20:00 New York
    {"equity": [0.0, 0.0, 100000.0, 0.0, 100000.0, 100000.0, 100000.0]},     # a zero after funding
    {"equity": ["junk", 0.0, 100000.0, 100001.0, 100002.0, 100003.0, 100004.0]},
    {"profit_loss": [0.0]},                                                  # unequal lists
]


@pytest.mark.parametrize("patch", BAD_EOD, ids=[str(i) for i in range(len(BAD_EOD))])
def test_bad_eod_shapes_raise_in_both(tmp_path, patch):
    t = table()
    t["/v2/account/portfolio/history"] = _bad_eod(**patch)
    server = Server(t)
    win = D(2026, 9, 1), D(2026, 10, 2)
    with pytest.raises(AR.AlpacaReadError):
        reader_for(server).eod_equity_history(*win)
    with pytest.raises(AL.AlpacaError):
        client_for(server, tmp_path).eod_equity_history(*win)


def _ca_with(key, row, types=None):
    return lambda params: {"corporate_actions": {key: [row]}, "next_page_token": ""}


BAD_CA = [
    ("forward_splits", {"id": "x", "symbol": None, "ex_date": "2026-01-02", "process_date": "2026-01-03"}),
    ("forward_splits", {"id": "", "symbol": "AAA", "ex_date": "2026-01-02", "process_date": "2026-01-03"}),
    ("forward_splits", {"id": "x", "symbol": "AAA", "ex_date": "garbage", "process_date": "2026-01-03"}),
    ("mystery_action", {"id": "x"}),
]


@pytest.mark.parametrize("key,row", BAD_CA, ids=[f"{k}-{i}" for i, (k, _) in enumerate(BAD_CA)])
def test_bad_corporate_actions_raise_in_both(tmp_path, key, row):
    t = table()
    t["/v1/corporate-actions"] = _ca_with(key, row)
    server = Server(t)
    win = D(2026, 1, 1), D(2026, 12, 31)
    with pytest.raises(AR.AlpacaReadError):
        reader_for(server).corporate_actions(["AAA"], *win)
    with pytest.raises(AL.AlpacaError):
        client_for(server, tmp_path).corporate_actions(["AAA"], *win)


def test_a_repeated_id_with_different_content_raises_in_both(tmp_path):
    other = dict(CA_PAGE_1["corporate_actions"]["forward_splits"][0], ex_date="2026-09-11")
    t = table()
    t["/v1/corporate-actions"] = lambda params: {"corporate_actions": {
        "forward_splits": [CA_PAGE_1["corporate_actions"]["forward_splits"][0], other]}, "next_page_token": ""}
    server = Server(t)
    with pytest.raises(AR.AlpacaReadError, match="repeats with a different event"):
        reader_for(server).corporate_actions(["AAA"], D(2026, 1, 1), D(2026, 12, 31))
    with pytest.raises(AL.AlpacaError, match="repeats with a different event"):
        client_for(server, tmp_path).corporate_actions(["AAA"], D(2026, 1, 1), D(2026, 12, 31))


@pytest.mark.parametrize("row", [{"activity_type": "FILL", "id": "a"},                          # fields missing
                                 dict(fill_row(1), activity_type="DIV"),                         # another type
                                 dict(fill_row(1), type="other")])                              # unknown fill type
def test_bad_fill_rows_raise_in_both(tmp_path, row):
    t = table()
    t["/v2/account/activities/FILL"] = lambda params: [row]
    server = Server(t)
    with pytest.raises(AR.AlpacaReadError):
        reader_for(server).activities_fills(D(2026, 9, 29))
    with pytest.raises(AL.AlpacaError):
        client_for(server, tmp_path).activities_fills(D(2026, 9, 29))


# ------------------------------------------------------------------ the FEE read (no client to equal)

def test_fee_read_pages_and_dedupes(tmp_path):
    server = Server(table())
    rows = reader_for(server).fee_activities()
    assert len(rows) == 130 and len({r["id"] for r in rows}) == 130
    assert sum(1 for p, _ in server.calls if p.endswith("activities/FEE")) == 2
    # unbounded on purpose: no date or until filter is sent (the docstring's posting-time trap)
    assert all("until" not in q and "date" not in q for p, q in server.calls if p.endswith("activities/FEE"))


def test_fee_read_refuses_another_activity_type_and_a_stuck_page():
    t = table()
    t["/v2/account/activities/FEE"] = lambda params: [dict(fee_row(1), activity_type="DIV")]
    with pytest.raises(AR.UnexpectedResponse, match="activity_type"):
        reader_for(Server(t)).fee_activities()
    t["/v2/account/activities/FEE"] = lambda params: [fee_row(i) for i in range(100)]
    with pytest.raises(AR.UnexpectedResponse, match="did not advance"):
        reader_for(Server(t)).fee_activities()


# ------------------------------------------------------------------ what makes it safe to hand to a job

def _code_names(path: Path) -> tuple[set, set]:
    """(string constants, identifiers) in the module's CODE: docstrings do not count, because
    the module explains what it refuses in words, and only code can send anything."""
    tree = ast.parse(path.read_text())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    strings = {n.value for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs}
    ids = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {
        n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    return strings, ids


def fake_wire(monkeypatch, answers):
    """urllib with its socket layer replaced, and nothing else: every request is recorded and
    `answers[host]` (status, headers, body) is what comes back through the real handler chain
    (redirect handling included). `urlopen`'s cached opener is cleared so that old and new
    code alike are built on the fake; the root conftest's netguard would refuse a real socket."""
    seen = []

    def fake_open(self, req):
        status, headers, body = answers[req.host]
        seen.append({"host": req.host, "url": req.full_url, "method": req.get_method(), "data": req.data,
                     "headers": {k.lower(): v for k, v in req.header_items()}})
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        resp = urllib.response.addinfourl(io.BytesIO(body), msg, req.full_url, status)
        resp.msg = "fake"
        return resp

    monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open", fake_open)
    monkeypatch.setattr(urllib.request.HTTPHandler, "http_open", fake_open)
    monkeypatch.setattr(urllib.request, "_opener", None)
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {})
    return seen


def test_the_default_transport_sends_a_get_and_nothing_else(monkeypatch):
    seen = fake_wire(monkeypatch, {"paper-api.alpaca.markets": (200, {}, b"[]")})
    status, body = AR.urllib_transport("https://paper-api.alpaca.markets/v2/calendar", {"X": "y"}, 5)
    assert (status, body) == (200, "[]")
    assert len(seen) == 1
    assert (seen[0]["method"], seen[0]["data"], seen[0]["url"]) == (
        "GET", None, "https://paper-api.alpaca.markets/v2/calendar")


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_a_redirect_is_refused_and_the_keys_go_nowhere_else(monkeypatch, code):
    """A 3xx from the paper host, pointing at the live API. The module promises paper only,
    and the keys are in the headers, so the second host must receive nothing at all.
    Fails on the parent commit: the default handler followed it and sent both key headers."""
    answers = {"paper-api.alpaca.markets": (code, {"Location": "https://api.alpaca.markets/v2/calendar"}, b""),
               "api.alpaca.markets": (200, {}, b"[]")}
    seen = fake_wire(monkeypatch, answers)
    reader = AR.AlpacaReader("cef", key_id=KEY, secret=SECRET, sleep=lambda s: None)
    with pytest.raises(AR.AlpacaHTTPError, match=f"HTTP {code}") as e:
        reader.calendar(D(2026, 9, 28), D(2026, 9, 29))
    assert e.value.status == code
    assert [c["host"] for c in seen] == ["paper-api.alpaca.markets"]
    assert KEY not in str(e.value) and SECRET not in str(e.value)


def test_the_redirect_fixture_can_see_a_followed_redirect(monkeypatch):
    """The control for the test above: urllib's default handler on the same fake wire does
    follow the 302 and does send the key to the second host, so "the second host received
    nothing" is a measurement, not an artifact of the fake."""
    answers = {"paper-api.alpaca.markets": (302, {"Location": "https://api.alpaca.markets/v2/calendar"}, b""),
               "api.alpaca.markets": (200, {}, b"[]")}
    seen = fake_wire(monkeypatch, answers)
    req = urllib.request.Request("https://paper-api.alpaca.markets/v2/calendar",
                                 headers={"APCA-API-KEY-ID": KEY}, method="GET")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
    assert [c["host"] for c in seen] == ["paper-api.alpaca.markets", "api.alpaca.markets"]
    assert seen[1]["headers"]["apca-api-key-id"] == KEY


def test_no_write_verb_appears_in_the_module():
    # a verb as a literal argument, an order path, or a key-file read would be the way to
    # add a write or a file read here: none appears in the module's code
    strings, ids = _code_names(READER_FILE)
    assert not (strings & {"POST", "PUT", "PATCH", "DELETE", "post", "put", "patch", "delete"})
    assert not any(s.startswith("/v2/orders") or s == "dotenv" or "QUANTT_ENV_FILE" in s for s in strings)
    assert not (ids & {"submit_order", "cancel_order", "replace_order", "close_position",
                       "close_all_positions", "dotenv"})
    # `open`: no builtin file open, and the only `.open` in the module is urllib_transport's opener
    tree = ast.parse(READER_FILE.read_text())
    assert "open" not in {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "open"]
    assert [getattr(n.value, "id", None) for n in attrs] == ["opener"]


def test_public_surface_is_exactly_the_reads_attribution_needs():
    public = {n for n in vars(AR.AlpacaReader) if not n.startswith("_") and n != "EOD_LISTS" and n != "FILL_FIELDS"}
    assert public == {"from_environment", "calendar", "eod_equity_history", "activities_fills",
                      "fee_activities", "distributions", "corporate_actions"}


def test_the_reader_refuses_any_other_host_and_a_relative_path():
    reader = AR.AlpacaReader("cef", key_id=KEY, secret=SECRET, transport=lambda *a: (200, "[]"))
    with pytest.raises(ValueError, match="refusing base"):
        reader._get("https://api.alpaca.markets", "/v2/account", None)
    with pytest.raises(ValueError, match="refusing base"):
        reader._get("https://paper-api.alpaca.markets.evil", "/v2/calendar", None)
    with pytest.raises(ValueError, match="refusing path"):
        reader._get(AR.PAPER_BASE, "v2/calendar", None)


def test_constants_equal_the_runner_clients():
    assert AR.PAPER_BASE == AL.PAPER_BASE and AR.DATA_BASE == AL.DATA_BASE
    assert AR.CORPORATE_ACTION_TYPES == AL.CORPORATE_ACTION_TYPES
    assert AR.CORPORATE_ACTION_RESPONSE_KEYS == AL.CORPORATE_ACTION_RESPONSE_KEYS
    assert AR.env_names("c4") == PROBE.env_names("c4") == ("ALPACA_C4_KEY_ID", "ALPACA_C4_SECRET_KEY")
    assert AR.FEED == AD.FEED and AR.ADJUSTMENT == AD.ADJUSTMENT
    assert AR.GET_BACKOFF_S == AL.GET_BACKOFF_S and AR.FILL_PAGE_SIZE == AL.FILL_PAGE_SIZE


def test_keys_come_from_the_process_environment_only(monkeypatch):
    for k in ("ALPACA_CEF_KEY_ID", "ALPACA_CEF_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(AR.MissingCredential) as e:
        AR.AlpacaReader.from_environment("cef")
    assert "ALPACA_CEF_KEY_ID" in str(e.value) and "ALPACA_CEF_SECRET_KEY" in str(e.value)
    # a book's key is never read from another book's variable
    monkeypatch.setenv("ALPACA_C4_KEY_ID", "OTHER-BOOK-KEY")
    monkeypatch.setenv("ALPACA_C4_SECRET_KEY", "OTHER-BOOK-SECRET")
    with pytest.raises(AR.MissingCredential):
        AR.AlpacaReader.from_environment("cef")
    r = AR.AlpacaReader.from_environment("c4", environ={"ALPACA_C4_KEY_ID": KEY, "ALPACA_C4_SECRET_KEY": SECRET})
    assert KEY not in repr(r) and SECRET not in repr(r)
    assert r._key_id == KEY and r.book == "c4"


def test_no_key_ever_reaches_a_message():
    server = Server(table())
    reader = reader_for(server)
    server.status_queue = [(403, f"forbidden for {KEY} and {SECRET}")]
    with pytest.raises(AR.AlpacaHTTPError) as e:
        reader.calendar(D(2026, 9, 28), D(2026, 9, 29))
    assert KEY not in str(e.value) and SECRET not in str(e.value) and "<redacted>" in str(e.value)
    server.status_queue = [(200, f"not json {KEY}")]
    with pytest.raises(AR.UnexpectedResponse) as e:
        reader.calendar(D(2026, 9, 28), D(2026, 9, 29))
    assert KEY not in str(e.value)


def test_retries_are_bounded_and_get_only():
    server = Server(table())
    sleeps = []
    reader = reader_for(server, sleep=sleeps.append)
    server.status_queue = [(503, "down")] * 5
    with pytest.raises(AR.AlpacaHTTPError, match="failed after 5 attempts"):
        reader.calendar(D(2026, 9, 28), D(2026, 9, 29))
    assert sleeps == [2, 5, 15, 30] and len(server.calls) == 5
    server.calls.clear()
    server.status_queue = [(429, "slow down")]                  # one 429, then the fixture answers
    assert reader.calendar(D(2026, 9, 28), D(2026, 9, 28))[0]["date"] == D(2026, 9, 28)
    assert len(server.calls) == 2


def test_a_transport_failure_is_retried_then_named():
    calls = []

    def transport(url, headers, timeout):
        calls.append(url)
        raise OSError("reset by peer")

    reader = AR.AlpacaReader("cef", key_id=KEY, secret=SECRET, transport=transport, sleep=lambda s: None)
    with pytest.raises(AR.AlpacaHTTPError, match="reset by peer"):
        reader.calendar(D(2026, 9, 28), D(2026, 9, 29))
    assert len(calls) == 5


def test_invalid_book_and_empty_keys_are_refused():
    with pytest.raises(ValueError, match="lowercase"):
        AR.AlpacaReader("CEF!", key_id=KEY, secret=SECRET)
    with pytest.raises(AR.MissingCredential):
        AR.AlpacaReader("cef", key_id="", secret=SECRET)


@pytest.mark.parametrize("bad", ["FAKE\nSECRETVALUE", "FAKE\rSECRETVALUE", "FAKE\x00SECRETVALUE", "FAKE SECRETVALUE",
                                 "FAKE\u2028SECRETVALUE"], ids=["lf", "cr", "nul", "space", "non-ascii"])
def test_a_key_that_is_not_printable_ascii_is_refused_naming_only_the_variable(bad):
    """http.client's ValueError for a line break in a header quotes the whole header value,
    and `_get` catches only transport errors, so the secret reached the report's file. Refused
    here, before any request. Fails on the parent commit: the constructor accepted it."""
    with pytest.raises(AR.MalformedCredential, match="ALPACA_CEF_SECRET_KEY") as e:
        AR.AlpacaReader("cef", key_id=KEY, secret=bad)
    assert "SECRETVALUE" not in str(e.value)
    with pytest.raises(AR.MalformedCredential, match="ALPACA_C4_KEY_ID") as e:
        AR.AlpacaReader("c4", key_id=bad, secret=SECRET)
    assert "SECRETVALUE" not in str(e.value)


def test_a_key_with_a_line_break_never_reaches_the_report_files(tmp_path, monkeypatch):
    """The same input through the job, the path the review found: the report names the
    variable and holds no part of the value. Fails on the parent commit (`Invalid header
    value b'FAKE\\nSECRETVALUE'` was written to both files)."""
    from scripts.ops import pnl_report as P
    monkeypatch.setenv("ALPACA_CEF_KEY_ID", "FAKEKEYID")
    monkeypatch.setenv("ALPACA_CEF_SECRET_KEY", "FAKE\nSECRETVALUE")
    rep, code = P.run_report("cef", tmp_path, D(2026, 11, 6), groups={"AAA": "muni"},
                             nav_fetcher=lambda *a: None, dist_check_fetcher=lambda *a: None)
    assert code == P.EXIT_INCOMPLETE and rep["attribution"]["status"] == P.UNMEASURED
    assert "ALPACA_CEF_SECRET_KEY" in rep["attribution"]["why"]
    out = tmp_path / "reports" / "pnl"
    for name in ("2026-11-06.json", "2026-11-06.md"):
        assert "SECRETVALUE" not in (out / name).read_text(), name
