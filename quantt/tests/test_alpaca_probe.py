"""The Alpaca probe can only read, reads only paper, and never leaks a key.

Each test pins one property the probe's docstring promises, because each is the
kind of promise that rots silently: a later edit adds a `session.post` "just to
test an order", or a debug print of the session, and nothing else would notice.
Hermetic throughout -- a fake session stands in for `requests`, and the root
conftest's netguard would fail any test that reached the network.
"""
import ast
import json
from pathlib import Path

import pytest

from quantt.broker import alpaca_probe as ap

SECRET = "sekrit-value-that-must-never-appear"
KEY_ID = "key-id-that-must-never-appear"


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class FakeSession:
    """Answers GETs from a table. Has NO post/delete/patch/put attribute, so any
    such call from the probe fails with AttributeError."""

    def __init__(self, table):
        self.table = table
        self.urls = []
        self.headers = {"APCA-API-KEY-ID": KEY_ID, "APCA-API-SECRET-KEY": SECRET}

    def get(self, url, timeout, allow_redirects=None):
        self.redirect_flags = getattr(self, "redirect_flags", []) + [allow_redirects]
        self.urls.append(url)
        path = url[len(ap.PAPER_BASE):]
        status, payload = self.table.get(path, (404, {"message": "not found"}))
        return FakeResp(status, payload)


def _table(universe, missing=()):
    t = {
        "/v2/account": (200, {"status": "ACTIVE", "currency": "USD", "equity": "100000"}),
        "/v2/account/configurations": (200, {"no_shorting": False}),
        "/v2/positions": (200, []),
        "/v2/orders?status=open&limit=500": (200, []),
    }
    for s in universe:
        if s not in missing:
            t[f"/v2/assets/{s}"] = (200, {"symbol": s, "tradable": True,
                                          "shortable": True, "borrow_status": "easy_to_borrow"})
    return t


def test_the_module_contains_no_verb_but_get():
    """No attribute access to post/put/patch/delete/request anywhere in the source."""
    tree = ast.parse(Path(ap.__file__).read_text())
    verbs = {"post", "put", "patch", "delete", "request", "submit_order", "cancel_order"}
    hits = [n.attr for n in ast.walk(tree)
            if isinstance(n, ast.Attribute) and n.attr in verbs]
    assert hits == [], f"write-capable calls found in the probe: {hits}"


def test_every_request_goes_to_the_paper_endpoint(monkeypatch):
    monkeypatch.setattr(ap, "universe", lambda b: ["PDI", "PTY"])
    s = FakeSession(_table(["PDI", "PTY"]))
    ap.probe_book("cef", s)
    assert s.urls and all(u.startswith("https://paper-api.alpaca.markets/v2/") for u in s.urls)


def test_a_non_paper_url_is_refused():
    with pytest.raises(ValueError, match="non-paper"):
        ap._get(FakeSession({}), "@api.alpaca.markets/v2/account")


def test_a_missing_key_names_the_variable_and_substitutes_nothing():
    env = {"ALPACA_CEF_KEY_ID": KEY_ID, "ALPACA_CEF_SECRET_KEY": SECRET}
    with pytest.raises(ap.MissingCredential) as e:
        ap.load_credentials("b6", env)          # b6 unset; cef's keys must NOT be used
    msg = str(e.value)
    assert "ALPACA_B6_KEY_ID" in msg and "ALPACA_B6_SECRET_KEY" in msg
    assert SECRET not in msg and KEY_ID not in msg


def test_an_asset_alpaca_does_not_list_is_recorded_not_raised_or_invented(monkeypatch):
    monkeypatch.setattr(ap, "universe", lambda b: ["PDI", "ZZZZ"])
    snap = ap.probe_book("cef", FakeSession(_table(["PDI", "ZZZZ"], missing={"ZZZZ"})))
    assert snap["assets"]["ZZZZ"] == {"_probe": "NOT FOUND AT ALPACA (404)"}
    assert "NOT FOUND AT ALPACA" in ap.summarise(snap)


def test_a_field_alpaca_did_not_send_shows_as_absent_not_a_default(monkeypatch):
    monkeypatch.setattr(ap, "universe", lambda b: ["PDI"])
    snap = ap.probe_book("cef", FakeSession(_table(["PDI"])))
    row = [l for l in ap.summarise(snap).splitlines() if l.startswith("PDI")][0]
    assert "ABSENT" in row          # e.g. margin fields the fake did not send
    assert "False" not in row       # nothing was defaulted to a boolean


def test_any_other_http_error_raises_with_the_path(monkeypatch):
    monkeypatch.setattr(ap, "universe", lambda b: [])
    t = _table([])
    t["/v2/account"] = (401, {"message": "unauthorized"})
    with pytest.raises(RuntimeError, match=r"GET /v2/account -> HTTP 401"):
        ap.probe_book("cef", FakeSession(t))


def test_neither_key_reaches_the_snapshot_or_the_summary(monkeypatch):
    monkeypatch.setattr(ap, "universe", lambda b: ["PDI"])
    snap = ap.probe_book("cef", FakeSession(_table(["PDI"])))
    blob = json.dumps(snap) + ap.summarise(snap)
    assert SECRET not in blob and KEY_ID not in blob


def test_no_account_identifier_reaches_the_snapshot_or_the_summary(monkeypatch):
    """Team lead 2026-10-12: snapshots are committed to a PUBLIC repository, and the
    2026-09-28 one carried the paper account's number and ID."""
    monkeypatch.setattr(ap, "universe", lambda b: ["PDI"])
    t = _table(["PDI"])
    t["/v2/account"] = (200, {"status": "ACTIVE", "id": "acct-uuid-must-not-appear",
                              "account_number": "PA-NUMBER-MUST-NOT-APPEAR", "equity": "1"})
    t["/v2/positions"] = (200, [{"symbol": "PDI", "account_id": "acct-uuid-must-not-appear"}])
    snap = ap.probe_book("cef", FakeSession(t))
    blob = json.dumps(snap) + ap.summarise(snap)
    assert "acct-uuid-must-not-appear" not in blob and "PA-NUMBER-MUST-NOT-APPEAR" not in blob
    assert snap["account"]["status"] == "ACTIVE" and snap["assets"]["PDI"]["symbol"] == "PDI"


def test_the_books_are_exactly_the_two_the_team_lead_kept():
    assert set(ap.BOOK_SPECS) == {"cef", "b6"}
    assert all(p.exists() for p in ap.BOOK_SPECS.values())


def test_the_cef_universe_comes_from_the_frozen_spec():
    spec = json.loads(ap.BOOK_SPECS["cef"].read_text())
    assert ap.universe("cef") == list(spec["frozen"]["universe"])


def test_c4_is_read_only_when_named_and_never_by_default(monkeypatch, capsys):
    """C4 (dark) is an opt-in book: `--book c4` reads its own account with its
    own keys, from its own spec's universe; the default `all` is still the two
    books, so the routine probe and ops.orient are unchanged."""
    assert set(ap.OPT_IN_BOOK_SPECS) == {"c4"} and not set(ap.OPT_IN_BOOK_SPECS) & set(ap.BOOK_SPECS)
    spec = json.loads(ap.OPT_IN_BOOK_SPECS["c4"].read_text())
    assert ap.universe("c4") == list(spec["frozen"]["universe"]) and len(ap.universe("c4")) == 74
    assert ap.env_names("c4") == ("ALPACA_C4_KEY_ID", "ALPACA_C4_SECRET_KEY")
    monkeypatch.setattr(ap, "read_env_file", lambda: {"ALPACA_C4_KEY_ID": "k"})
    assert ap.main(["--check-keys", "--book", "c4"]) == 0
    out = capsys.readouterr().out
    assert out == "ALPACA_C4_KEY_ID: SET\nALPACA_C4_SECRET_KEY: NOT SET\n" and "k\n" not in out
    assert ap.main(["--check-keys"]) == 0
    assert "C4" not in capsys.readouterr().out
    with pytest.raises(KeyError):
        ap.spec_path("nope")


# ------------------------------------------- the opening-session read (QR1, release-check of 336df9d)

def _closed(n, filled_at=None, cid="lab-20261020-ADX-1"):
    """n closed orders, OLDEST first (one a minute from 2026-01-02, as Alpaca serves
    direction=asc); the one at index `filled_at` filled."""
    import datetime as dt
    t0 = dt.datetime(2026, 1, 2, 14, 30, tzinfo=dt.timezone.utc)
    return [{"id": f"o{i}", "client_order_id": cid if i == filled_at else f"x-{i}", "symbol": "ADX",
             "filled_qty": "5" if i == filled_at else "0", "status": "filled" if i == filled_at
             else "canceled",
             "submitted_at": (t0 + dt.timedelta(minutes=i)).isoformat().replace("+00:00", "Z")}
            for i in range(n)]


def _pages(closed):
    """{path: (200, page)} serving `closed` as the runner's client pages it: 500 a page,
    each later page asked `after` the last time strictly before the previous page's end."""
    out, start, after = {}, 0, None
    while True:
        page = closed[start:start + ap.CLOSED_ORDERS_PAGE]
        out[ap._closed_orders_path(after)] = (200, page)
        if len(page) < ap.CLOSED_ORDERS_PAGE:
            return out
        after = page[-2]["submitted_at"]              # times are distinct in `_closed`
        start += ap.CLOSED_ORDERS_PAGE - 1             # the overlap: the page's last order


def _c4_snap(closed, positions=()):
    t = _table(ap.universe("c4"))
    t["/v2/positions"] = (200, list(positions))
    t.update(_pages(closed))
    s = FakeSession(t)
    return ap.probe_book("c4", s), s


def test_c4s_probe_reads_whether_its_first_session_opens_at_full_target():
    """QR1: the arming read must see a PAST fill, which positions and open orders cannot.
    Under C4's book-json rule (`execution.opening_session_fills = "own_prefix"`; team lead
    2026-11-03, "just flat it", docs/SYSTEM.md section 5, PR #30), the research loop's fill is read and named but
    does not count: still an opening session. A fill with C4's own prefix does count.
    Fails on 336df9d (no opening-session read) and on f7f7be5 (the lab fill counted)."""
    snap, s = _c4_snap(_closed(3))
    o = snap["opening_session"]
    assert o["value"] is True and o["closed_orders_read"] == 3 and o["newest_fill"] is None
    assert o["rule"] == "own_prefix"
    assert any(u.endswith(ap.CLOSED_ORDERS_PATH) for u in s.urls)
    assert "opening_session: True" in ap.summarise(snap)
    snap, _ = _c4_snap(_closed(3, filled_at=1))
    o = snap["opening_session"]
    assert o["value"] is True and (o["filled_orders_read"], o["counted_fills"]) == (1, 0)
    assert o["newest_fill"]["client_order_id_prefix"] == "lab" and "o1" not in json.dumps(o)
    snap, _ = _c4_snap(_closed(3, filled_at=1, cid="c4-20261020-ADX-1"))
    o = snap["opening_session"]
    assert o["value"] is False and o["counted_fills"] == 1
    assert "opening_session: False" in ap.summarise(snap)


def test_a_position_alone_makes_the_first_session_not_an_opening():
    snap, _ = _c4_snap([], positions=[{"symbol": "ADX", "qty": "3"}])
    assert snap["opening_session"]["value"] is False


def test_the_read_pages_through_every_closed_order_not_the_newest_500():
    """execution-trader 2 (release-check of 4f759a9): the read stopped at one page of 500.
    Now it pages as the runner's client does: a C4 fill on the third page is found (not an
    opening), and 1,200 foreign-only orders read whole are an opening. Fails on 61589a8."""
    n = 2 * ap.CLOSED_ORDERS_PAGE + 200
    snap, s = _c4_snap(_closed(n, filled_at=n - 3, cid="c4-20261020-ADX-1"))
    o = snap["opening_session"]
    assert o["value"] is False and o["counted_fills"] == 1 and o["closed_orders_read"] == n
    assert sum("status=closed" in u for u in s.urls) == 3
    snap, _ = _c4_snap(_closed(n, filled_at=n - 3))
    o = snap["opening_session"]
    assert o["value"] is True and o["closed_orders_read"] == n and o["filled_orders_read"] == 1


def test_past_the_page_cap_the_read_is_unmeasured_and_names_plan_json(monkeypatch):
    """Past CLOSED_ORDERS_MAX_PAGES the read is UNMEASURED, never True, and names the
    session's own plan.json `first_session` as the authority. Fails on 61589a8."""
    monkeypatch.setattr(ap, "CLOSED_ORDERS_MAX_PAGES", 1)
    snap, _ = _c4_snap(_closed(ap.CLOSED_ORDERS_PAGE + 10))
    o = snap["opening_session"]
    assert o["value"] is None and o["why"].startswith("UNMEASURED") and "plan.json" in o["why"]
    assert "opening_session: UNMEASURED" in ap.summarise(snap)


def test_a_page_the_runners_paging_cannot_trust_raises_naming_it():
    """Out of order, or a full page at one timestamp: raised, never read as complete."""
    bad = list(reversed(_closed(3)))
    with pytest.raises(RuntimeError, match="ascending"):
        _c4_snap(bad)
    same = _closed(ap.CLOSED_ORDERS_PAGE)
    for o in same:
        o["submitted_at"] = "2026-01-02T14:30:00Z"
    t = _table(ap.universe("c4"))
    t[ap.CLOSED_ORDERS_PATH] = (200, same)
    with pytest.raises(RuntimeError, match="one timestamp|cannot page"):
        ap.probe_book("c4", FakeSession(t))


def test_the_read_is_the_runners_rule_on_the_same_orders():
    from quantt.session import run as rn
    b = rn.BOOKS["c4"]
    rule = rn.opening_session_fills_for(b)
    for closed, pos in ((_closed(4), []), (_closed(4, filled_at=3), []),
                        (_closed(4, filled_at=2, cid="c4-20261020-ADX-1"), []),
                        ([], [{"symbol": "ADX", "qty": "1"}])):
        snap, _ = _c4_snap(closed, positions=pos)
        assert snap["opening_session"]["value"] == rn.is_opening_session(
            {p["symbol"]: p["qty"] for p in pos}, closed, fills=rule, cid_prefix=b.cid_prefix)


def test_an_unreadable_fill_raises_naming_the_order():
    bad = _closed(2)
    bad[0]["filled_qty"] = None
    with pytest.raises(RuntimeError, match="x-0"):
        _c4_snap(bad)


def test_the_routine_probe_makes_no_closed_orders_request():
    """The core and b6 snapshots are unchanged: no closed-order GET, no new key."""
    s = FakeSession(_table(ap.universe("cef")))
    snap = ap.probe_book("cef", s)
    assert "opening_session" not in snap and not any("status=closed" in u for u in s.urls)
