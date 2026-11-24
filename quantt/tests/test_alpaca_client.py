"""The runner's Alpaca client: parses strictly, pages completely, sends one kind of order once.

Each test pins a promise from `quantt/broker/alpaca.py`'s docstrings that would
rot silently: a later edit that retries the POST, defaults a missing field,
advances a time cursor one order too far, or prints the session. Hermetic
throughout: `FakeSession` stands in for `requests.Session`, a temporary .env
file stands in for the real one (which tests never read), and the root
conftest's netguard fails any test that reaches the network.
"""
import ast
import datetime as dt
import json
from pathlib import Path

import pytest
import requests

from quantt.broker import alpaca as al
from quantt.broker.alpaca_probe import MissingCredential

KEY_ID = "KEYID-must-never-appear-0123"
SECRET = "SECRET-must-never-appear-4567"
D = dt.date(2026, 9, 29)


# ------------------------------------------------------------------ fakes

class FakeResp:
    def __init__(self, status, payload=None, text=None):
        self.status_code = status
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    """GETs are answered by `get_handler(url, params) -> FakeResp | Exception`;
    POSTs by `post_handler(url, json) -> FakeResp | Exception`. Every call is
    recorded. There is no put/patch/delete/request attribute, so any such call
    from the client fails with AttributeError."""

    def __init__(self, get_handler=None, post_handler=None):
        self.headers = {}
        self.gets, self.posts = [], []
        self.redirect_flags = []      # every call's allow_redirects, as passed
        self._g, self._p = get_handler, post_handler

    def get(self, url, params=None, timeout=None, allow_redirects=None):
        self.redirect_flags.append(allow_redirects)
        self.gets.append((url, dict(params or {})))
        r = self._g(url, params or {})
        if isinstance(r, Exception):
            raise r
        return r

    def post(self, url, json=None, timeout=None, allow_redirects=None):
        self.redirect_flags.append(allow_redirects)
        self.posts.append((url, json))
        r = self._p(url, json)
        if isinstance(r, Exception):
            raise r
        return r


def route(table):
    """A get_handler from {path: FakeResp or callable(params)}; unknown -> 404."""
    def h(url, params):
        for base in (al.PAPER_BASE, al.DATA_BASE):
            if url.startswith(base + "/"):
                path = url[len(base):]
                break
        else:
            raise AssertionError(f"request to a non-Alpaca URL {url}")
        v = table.get(path)
        if v is None:
            return FakeResp(404, {"message": "not found"})
        return v(params) if callable(v) else v
    return h


@pytest.fixture
def env_file(tmp_path):
    p = tmp_path / "alpaca.env"
    p.write_text(f"ALPACA_CEF_KEY_ID={KEY_ID}\nALPACA_CEF_SECRET_KEY={SECRET}\n")
    return p


@pytest.fixture
def sleeps():
    return []


def client(env_file, sleeps, get=None, post=None):
    s = FakeSession(get or route({}), post)
    return al.AlpacaClient("cef", env_file, session=s, sleep=sleeps.append), s


ACCOUNT = {"id": "acct-1", "status": "ACTIVE", "currency": "USD", "multiplier": "2",
           "equity": "100000.5", "last_equity": "99999", "cash": "100000.5",
           "buying_power": "200001", "regt_buying_power": "200001",
           "initial_margin": "0", "maintenance_margin": "0",
           "long_market_value": "0", "short_market_value": "0",
           "shorting_enabled": True, "trading_blocked": False, "account_blocked": False,
           "trade_suspended_by_user": False}


def order(i, ts, cid=None, **kw):
    o = {"id": f"o{i}", "client_order_id": cid or f"cid-{i}", "status": "new",
         "symbol": "PDI", "side": "buy", "type": "market", "time_in_force": "cls",
         "submitted_at": ts, "filled_qty": "0", "qty": "10"}
    o.update(kw)
    return o


# ------------------------------------------------------ endpoints and keys

def test_a_live_or_any_non_paper_trading_endpoint_is_refused(env_file):
    for bad in ("https://api.alpaca.markets", "https://paper-api.alpaca.markets/",
                "https://paper-api.alpaca.markets.evil.com", "http://paper-api.alpaca.markets"):
        with pytest.raises(ValueError, match="paper"):
            al.AlpacaClient("cef", env_file, base_url=bad, session=FakeSession())


def test_trading_endpoint_reads_the_paper_endpoint_sends_nothing_and_cannot_be_set(env_file,
                                                                                 sleeps):
    """CEF trial 55 (te4): the runner declares the account paper only when this reads exactly
    PAPER_BASE (quantt/session/run.py `thin_rule_for`). Reading it is not a request, and it
    cannot be overwritten to make a client claim the paper endpoint."""
    c, s = client(env_file, sleeps)
    assert c.trading_endpoint == al.PAPER_BASE == "https://paper-api.alpaca.markets"
    assert s.gets == [] and s.posts == []
    with pytest.raises(AttributeError):
        c.trading_endpoint = "https://api.alpaca.markets"
    assert c.trading_endpoint == al.PAPER_BASE


def test_a_non_default_data_endpoint_is_refused(env_file):
    with pytest.raises(ValueError, match="data endpoint"):
        al.AlpacaClient("cef", env_file, data_url="https://example.com", session=FakeSession())


def test_every_request_goes_to_paper_or_data_hosts(env_file, sleeps):
    c, s = client(env_file, sleeps, route({"/v2/account": FakeResp(200, ACCOUNT),
                                           "/v2/clock": FakeResp(200, {
                                               "timestamp": "2026-09-29T09:00:00-04:00", "is_open": False,
                                               "next_open": "2026-09-29T09:30:00-04:00",
                                               "next_close": "2026-09-29T16:00:00-04:00"})}))
    c.account(); c.clock()
    assert all(u.startswith(al.PAPER_BASE + "/v2/") for u, _ in s.gets)


def test_keys_come_from_the_named_file_into_the_headers_only(env_file, sleeps):
    c, s = client(env_file, sleeps)
    assert s.headers == {"APCA-API-KEY-ID": KEY_ID, "APCA-API-SECRET-KEY": SECRET}
    attrs = json.dumps({k: str(v) for k, v in vars(c).items() if k != "_session"})
    assert KEY_ID not in attrs and SECRET not in attrs


def test_a_missing_key_names_the_variable_and_no_other_books_key_is_used(env_file):
    with pytest.raises(MissingCredential) as e:
        al.AlpacaClient("b6", env_file, session=FakeSession())
    msg = str(e.value)
    assert "ALPACA_B6_KEY_ID" in msg and "ALPACA_B6_SECRET_KEY" in msg
    assert KEY_ID not in msg and SECRET not in msg


def test_a_missing_key_file_raises(tmp_path):
    with pytest.raises(MissingCredential, match="does not exist"):
        al.AlpacaClient("cef", tmp_path / "nope.env", session=FakeSession())


def test_from_environment_requires_quantt_env_file(monkeypatch, env_file):
    monkeypatch.delenv("QUANTT_ENV_FILE", raising=False)
    with pytest.raises(MissingCredential, match="QUANTT_ENV_FILE"):
        al.AlpacaClient.from_environment("cef", session=FakeSession())
    monkeypatch.setenv("QUANTT_ENV_FILE", str(env_file))
    c = al.AlpacaClient.from_environment("cef", session=FakeSession())
    assert c.book == "cef"


def test_keys_never_reach_repr_or_any_error_message(env_file, sleeps):
    # Alpaca echoing a header value back in an error body is the worst case.
    echo = f"bad key {KEY_ID} / {SECRET}"
    c, s = client(env_file, sleeps,
                  route({"/v2/account": FakeResp(401, text=echo),
                         "/v2/clock": FakeResp(503, text=echo)}),
                  lambda u, j: FakeResp(403, text=echo))
    msgs = [repr(c), str(c)]
    for call in (c.account, c.clock, lambda: c.submit_order("PDI", 1, "buy", "cef-1", time_in_force="cls")):
        with pytest.raises(al.AlpacaError) as e:
            call()
        msgs.append(str(e.value))
    s._p = lambda u, j: requests.ReadTimeout(f"timeout {SECRET}")
    with pytest.raises(al.AmbiguousSubmit) as e:
        c.submit_order("PDI", 1, "buy", "cef-2", time_in_force="cls")
    msgs.append(str(e.value))
    blob = "\n".join(msgs)
    assert KEY_ID not in blob and SECRET not in blob
    assert "<redacted>" in blob


# --------------------------------------------------------------- parsing

def test_account_parses_every_number_and_bool(env_file, sleeps):
    c, _ = client(env_file, sleeps, route({"/v2/account": FakeResp(200, ACCOUNT)}))
    a = c.account()
    assert a["equity"] == 100000.5 and a["buying_power"] == 200001.0
    assert a["shorting_enabled"] is True and a["trading_blocked"] is False
    assert a["multiplier"] == "2" and a["raw"] == ACCOUNT


@pytest.mark.parametrize("field", ["equity", "last_equity", "buying_power", "shorting_enabled"])
def test_account_missing_field_raises_naming_it(env_file, sleeps, field):
    bad = {k: v for k, v in ACCOUNT.items() if k != field}
    c, _ = client(env_file, sleeps, route({"/v2/account": FakeResp(200, bad)}))
    with pytest.raises(al.UnexpectedResponse, match=field):
        c.account()


def test_account_rejects_a_null_number_and_a_string_boolean(env_file, sleeps):
    for f, v in (("equity", None), ("equity", ""), ("trading_blocked", "false")):
        c, _ = client(env_file, sleeps, route({"/v2/account": FakeResp(200, {**ACCOUNT, f: v})}))
        with pytest.raises(al.UnexpectedResponse, match=f):
            c.account()


def pos(sym, qty, side):
    return {"symbol": sym, "qty": qty, "side": side, "avg_entry_price": "10"}


def test_positions_are_signed_from_side_whichever_sign_convention_alpaca_uses(env_file, sleeps):
    raw = [pos("PDI", "100", "long"), pos("PTY", "-50", "short"), pos("NVG", "25", "short")]
    c, _ = client(env_file, sleeps, route({"/v2/positions": FakeResp(200, raw)}))
    p = c.positions()
    assert p.qty == {"PDI": 100, "PTY": -50, "NVG": -25}
    assert p.raw == raw


@pytest.mark.parametrize("row, match", [
    (pos("PDI", "-100", "long"), "negative"),
    (pos("PDI", "10.5", "long"), "whole"),
    (pos("PDI", "0", "long"), "qty 0"),
    (pos("PDI", "10", "flat"), "long\\|short"),
    ({"symbol": "PDI", "side": "long"}, "qty"),
])
def test_positions_raise_on_contradictions(env_file, sleeps, row, match):
    c, _ = client(env_file, sleeps, route({"/v2/positions": FakeResp(200, [row])}))
    with pytest.raises(al.UnexpectedResponse, match=match):
        c.positions()


def test_positions_raise_on_a_duplicate_symbol(env_file, sleeps):
    raw = [pos("PDI", "1", "long"), pos("PDI", "2", "long")]
    c, _ = client(env_file, sleeps, route({"/v2/positions": FakeResp(200, raw)}))
    with pytest.raises(al.UnexpectedResponse, match="twice"):
        c.positions()


def test_clock_parses_offsets_and_nanoseconds(env_file, sleeps):
    raw = {"timestamp": "2026-09-29T13:00:01.123456789Z", "is_open": True,
           "next_open": "2026-09-30T09:30:00-04:00", "next_close": "2026-09-29T16:00:00-04:00"}
    c, _ = client(env_file, sleeps, route({"/v2/clock": FakeResp(200, raw)}))
    k = c.clock()
    assert k["is_open"] is True
    assert k["timestamp"] == dt.datetime(2026, 9, 29, 13, 0, 1, 123456, tzinfo=dt.timezone.utc)
    assert k["next_close"].utcoffset() == dt.timedelta(hours=-4)


def test_clock_rejects_a_naive_timestamp(env_file, sleeps):
    raw = {"timestamp": "2026-09-29T13:00:01", "is_open": True,
           "next_open": "2026-09-30T09:30:00-04:00", "next_close": "2026-09-29T16:00:00-04:00"}
    c, _ = client(env_file, sleeps, route({"/v2/clock": FakeResp(200, raw)}))
    with pytest.raises(al.UnexpectedResponse, match="offset"):
        c.clock()


def test_calendar_rows_and_out_of_range_day(env_file, sleeps):
    rows = [{"date": "2026-09-29", "open": "09:30", "close": "16:00",
             "session_open": "0400", "session_close": "2000", "settlement_date": "2026-09-30"}]
    c, s = client(env_file, sleeps, route({"/v2/calendar": FakeResp(200, rows)}))
    out = c.calendar(D, D)
    assert out == [{"date": D, "open": "09:30", "close": "16:00", "raw": rows[0]}]
    assert s.gets[-1][1] == {"start": "2026-09-29", "end": "2026-09-29"}
    c, _ = client(env_file, sleeps, route({"/v2/calendar": FakeResp(200, [{**rows[0], "date": "2026-09-30"}])}))
    with pytest.raises(al.UnexpectedResponse, match="outside"):
        c.calendar(D, D)


def asset_row(**kw):
    a = {"symbol": "PDI", "status": "active", "exchange": "NYSE", "tradable": True,
         "shortable": True, "marginable": True, "fractionable": True,
         "borrow_status": "easy_to_borrow", "easy_to_borrow": True}
    a.update(kw)
    return a


def test_asset_404_raises_asset_not_found_and_bad_types_raise(env_file, sleeps):
    c, _ = client(env_file, sleeps, route({"/v2/assets/PDI": FakeResp(200, asset_row())}))
    assert c.asset("PDI")["shortable"] is True
    with pytest.raises(al.AssetNotFound):
        c.asset("ZZZZ")
    c, _ = client(env_file, sleeps, route({"/v2/assets/PDI": FakeResp(200, asset_row(shortable="true"))}))
    with pytest.raises(al.UnexpectedResponse, match="shortable"):
        c.asset("PDI")
    c, _ = client(env_file, sleeps, route({"/v2/assets/PDI": FakeResp(200, asset_row(borrow_status="locate"))}))
    with pytest.raises(al.UnexpectedResponse, match="borrow_status"):
        c.asset("PDI")


# ----------------------------------------------------------- pagination

def orders_server(all_orders):
    """Alpaca's documented semantics: after is exclusive, asc, at most limit."""
    def h(params):
        rows = sorted(all_orders, key=lambda o: al.parse_ts(o["submitted_at"], "t"))
        if "after" in params:
            a = al.parse_ts(params["after"], "after")
            rows = [o for o in rows if al.parse_ts(o["submitted_at"], "t") > a]
        return FakeResp(200, rows[: params["limit"]])
    return h


def test_orders_page_by_time_without_skipping_an_order_that_shares_a_boundary_timestamp(env_file, sleeps):
    # limit 3: page 1 = o1,o2,o3; o3 and o4 share t3 across the page-2 boundary.
    ts = ["2026-09-29T12:00:01Z", "2026-09-29T12:00:02Z", "2026-09-29T12:00:03Z",
          "2026-09-29T12:00:03Z", "2026-09-29T12:00:04Z"]
    allo = [order(i + 1, t) for i, t in enumerate(ts)]
    c, s = client(env_file, sleeps, route({"/v2/orders": orders_server(allo)}))
    got = c.orders(status="all", limit=3)
    assert [o["id"] for o in got] == ["o1", "o2", "o3", "o4", "o5"]
    assert all(p["direction"] == "asc" and p["status"] == "all" for _, p in s.gets)


def test_orders_full_page_all_one_timestamp_raises(env_file, sleeps):
    allo = [order(i, "2026-09-29T12:00:00Z") for i in range(4)]
    c, _ = client(env_file, sleeps, route({"/v2/orders": orders_server(allo)}))
    with pytest.raises(al.UnexpectedResponse, match="all submitted at"):
        c.orders(status="all", limit=3)


def test_orders_status_has_no_default_and_is_validated(env_file, sleeps):
    c, _ = client(env_file, sleeps)
    with pytest.raises(TypeError):
        c.orders()
    with pytest.raises(ValueError):
        c.orders(status="today")
    with pytest.raises(ValueError, match="naive"):
        c.orders(status="all", after=dt.datetime(2026, 9, 29))


def test_orders_passes_nested_and_time_filters(env_file, sleeps):
    c, s = client(env_file, sleeps, route({"/v2/orders": FakeResp(200, [])}))
    c.orders(status="closed", after="2026-09-29T00:00:00-04:00",
             until="2026-09-30T00:00:00-04:00", nested=True)
    p = s.gets[0][1]
    assert p["nested"] == "true" and p["after"].startswith("2026-09-29") and p["until"].startswith("2026-09-30")


def fill(i, **kw):
    a = {"id": f"20260929::{i:04d}", "activity_type": "FILL", "order_id": "o1", "symbol": "PDI",
         "side": "buy", "qty": "1", "price": "10", "cum_qty": "1", "leaves_qty": "0",
         "transaction_time": "2026-09-29T20:00:00Z", "type": "fill", "order_status": "filled"}
    a.update(kw)
    return a


def test_fills_page_with_the_last_id_as_page_token_until_a_short_page(env_file, sleeps):
    allf = [fill(i) for i in range(130)]

    def h(params):
        start = 0
        if "page_token" in params:
            start = [a["id"] for a in allf].index(params["page_token"]) + 1
        return FakeResp(200, allf[start: start + params["page_size"]])
    c, s = client(env_file, sleeps, route({"/v2/account/activities/FILL": h}))
    got = c.activities_fills(D)
    assert [a["id"] for a in got] == [a["id"] for a in allf]
    assert s.gets[1][1]["page_token"] == allf[99]["id"]
    assert all(p["date"] == "2026-09-29" for _, p in s.gets)


def test_fills_reject_an_unknown_type(env_file, sleeps):
    c, _ = client(env_file, sleeps, route({"/v2/account/activities/FILL": FakeResp(200, [fill(1, type="bust")])}))
    with pytest.raises(al.UnexpectedResponse, match="fill\\|partial_fill"):
        c.activities_fills(D)


# ------------------------------------------------ GET retry, 404 semantics

def test_get_retries_429_and_5xx_then_succeeds(env_file, sleeps):
    seq = [FakeResp(429, text="slow"), FakeResp(503, text="down"),
           requests.ConnectionError("reset"), FakeResp(200, ACCOUNT)]
    c, s = client(env_file, sleeps, lambda u, p: seq.pop(0))
    assert c.account()["equity"] == 100000.5
    assert len(s.gets) == 4 and sleeps == list(al.GET_BACKOFF_S[:3])


def test_get_retries_are_bounded(env_file, sleeps):
    c, s = client(env_file, sleeps, lambda u, p: FakeResp(503, text="down"))
    with pytest.raises(al.AlpacaHTTPError, match="after 5 attempts"):
        c.account()
    assert len(s.gets) == len(al.GET_BACKOFF_S) + 1


def test_a_4xx_get_is_not_retried(env_file, sleeps):
    c, s = client(env_file, sleeps, lambda u, p: FakeResp(401, text="unauthorized"))
    with pytest.raises(al.AlpacaHTTPError, match="HTTP 401"):
        c.account()
    assert len(s.gets) == 1 and sleeps == []


def test_order_by_client_id_404_is_none_every_other_failure_raises(env_file, sleeps):
    o = order(1, "2026-09-29T12:00:00Z", cid="cef-20260929-PDI-0")
    c, s = client(env_file, sleeps, route({"/v2/orders:by_client_order_id": FakeResp(200, o)}))
    assert c.order_by_client_id("cef-20260929-PDI-0") == o
    assert s.gets[0][1] == {"client_order_id": "cef-20260929-PDI-0"}
    c, _ = client(env_file, sleeps, route({}))
    assert c.order_by_client_id("cef-20260929-PDI-0") is None
    for status in (401, 500):
        c, _ = client(env_file, sleeps, route({"/v2/orders:by_client_order_id": FakeResp(status, text="x")}))
        with pytest.raises(al.AlpacaHTTPError):
            c.order_by_client_id("cef-20260929-PDI-0")
    c, _ = client(env_file, sleeps, route({"/v2/orders:by_client_order_id": FakeResp(200, {**o, "client_order_id": "other"})}))
    with pytest.raises(al.UnexpectedResponse, match="asked for"):
        c.order_by_client_id("cef-20260929-PDI-0")


# ---------------------------------------------------------------- submit

def echo_ok(url, j):
    return FakeResp(200, {**j, "id": "ord-1", "status": "accepted", "filled_qty": "0",
                          "submitted_at": "2026-09-29T13:00:00Z"})


def test_submit_sends_exactly_one_market_cls_whole_share_order(env_file, sleeps):
    c, s = client(env_file, sleeps, post=echo_ok)
    o = c.submit_order("PDI", 37, "sell", "cef-20260929-PDI-0", time_in_force="cls")
    assert o["id"] == "ord-1"
    assert s.posts == [(al.PAPER_BASE + "/v2/orders",
                        {"symbol": "PDI", "qty": "37", "side": "sell", "type": "market",
                         "time_in_force": "cls", "client_order_id": "cef-20260929-PDI-0"})]


def test_submit_day_is_the_paper_late_market_order(env_file, sleeps):
    """team lead 2026-09-29: paper only, market `day` in the last minutes."""
    c, s = client(env_file, sleeps, post=echo_ok)
    c.submit_order("PDI", 37, "sell", "cef-20260929-PDI-1", time_in_force="day")
    assert s.posts[0][1]["time_in_force"] == "day" and s.posts[0][1]["type"] == "market"


@pytest.mark.parametrize("tif", ["gtc", "opg", "ioc", "", None, "CLS"])
def test_submit_refuses_any_other_time_in_force(env_file, sleeps, tif):
    c, s = client(env_file, sleeps, post=echo_ok)
    with pytest.raises(ValueError, match="time_in_force"):
        c.submit_order("PDI", 1, "buy", "cef-1", time_in_force=tif)
    assert s.posts == []


def test_submit_has_no_default_time_in_force(env_file, sleeps):
    c, s = client(env_file, sleeps, post=echo_ok)
    with pytest.raises(TypeError):
        c.submit_order("PDI", 1, "buy", "cef-1")
    assert s.posts == []


@pytest.mark.parametrize("sym, qty, side, cid", [
    ("PDI", 0, "buy", "c1"), ("PDI", -5, "sell", "c1"), ("PDI", 10.0, "buy", "c1"),
    ("PDI", 2.5, "buy", "c1"), ("PDI", True, "buy", "c1"), ("PDI", "10", "buy", "c1"),
    ("PDI", 1, "sell_short", "c1"), ("pdi", 1, "buy", "c1"), ("PDI", 1, "buy", ""),
    ("PDI", 1, "buy", "x" * 129), ("PDI", 1, "buy", "cef 2026"),
])
def test_submit_refuses_bad_input_before_sending_anything(env_file, sleeps, sym, qty, side, cid):
    c, s = client(env_file, sleeps, post=echo_ok)
    with pytest.raises(ValueError):
        c.submit_order(sym, qty, side, cid, time_in_force="cls")
    assert s.posts == []


def test_submit_refuses_a_non_paper_base_even_if_tampered_after_construction(env_file, sleeps):
    c, s = client(env_file, sleeps, post=echo_ok)
    c._base = "https://api.alpaca.markets"
    with pytest.raises(ValueError, match="non-paper"):
        c.submit_order("PDI", 1, "buy", "cef-1", time_in_force="cls")
    assert s.posts == []


@pytest.mark.parametrize("exc", [requests.ReadTimeout("read timed out"),
                                 requests.ConnectionError("connection reset"),
                                 FakeResp(502, text="bad gateway"),
                                 FakeResp(200, ValueError("not json"), text="<html>")])
def test_an_ambiguous_submit_raises_once_and_is_never_retried(env_file, sleeps, exc):
    c, s = client(env_file, sleeps, post=lambda u, j: exc)
    with pytest.raises(al.AmbiguousSubmit) as e:
        c.submit_order("PDI", 5, "buy", "cef-20260929-PDI-0", time_in_force="cls")
    assert len(s.posts) == 1 and sleeps == [] and s.gets == []
    assert e.value.client_order_id == "cef-20260929-PDI-0"
    assert "do NOT resend" in str(e.value) and "order_by_client_id" in str(e.value)


@pytest.mark.parametrize("status", [403, 422, 429])
def test_a_4xx_submit_is_a_rejection_and_is_not_retried(env_file, sleeps, status):
    c, s = client(env_file, sleeps, post=lambda u, j: FakeResp(status, {"code": 40010001,
                                                                     "message": "client_order_id must be unique"}))
    with pytest.raises(al.OrderRejected) as e:
        c.submit_order("PDI", 5, "buy", "cef-1", time_in_force="cls")
    assert e.value.status == status and len(s.posts) == 1 and sleeps == []


@pytest.mark.parametrize("field, value", [("time_in_force", "day"), ("type", "limit"),
                                          ("qty", "5.5"), ("side", "sell"),
                                          ("client_order_id", "other"), ("id", None)])
def test_an_accepted_order_that_echoes_something_else_raises_but_says_it_exists(env_file, sleeps, field, value):
    c, s = client(env_file, sleeps, post=lambda u, j: FakeResp(200, {**echo_ok(u, j)._payload, field: value}))
    with pytest.raises(al.SubmitResponseInvalid, match="ACCEPTED") as e:
        c.submit_order("PDI", 5, "buy", "cef-1", time_in_force="cls")
    assert field in str(e.value) and len(s.posts) == 1


def test_the_module_has_no_cancel_replace_or_generic_request_path():
    tree = ast.parse(Path(al.__file__).read_text())
    verbs = {"put", "patch", "delete", "request", "cancel_order", "replace_order"}
    hits = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in verbs]
    assert hits == []
    posts = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "post"]
    assert len(posts) == 1, "exactly one POST call site: submit_order"


def test_submit_order_has_no_type_parameter_and_a_required_keyword_tif():
    """`type` is always market. `time_in_force` became a parameter on 2026-09-29
    (team lead: paper-only late market orders, a recorded exception to rule 3);
    it is keyword-only with NO default, and only cls/day pass (tests above)."""
    import inspect
    sig = inspect.signature(al.AlpacaClient.submit_order)
    assert set(sig.parameters) == {"self", "symbol", "qty", "side", "client_order_id",
                                   "time_in_force"}
    p = sig.parameters["time_in_force"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty


# ------------------------------------------------------ auction prints

def auction_body(rows, token=None):
    return FakeResp(200, {"auctions": rows, "next_page_token": token})


def day(prints, d="2026-09-29"):
    return {"d": d, "o": [], "c": prints}


def pr(x, p, c="M", t="2026-09-29T20:00:00Z"):
    return {"t": t, "x": x, "p": p, "s": 100, "c": c}


def test_auction_returns_the_official_close_not_the_closing_trade(env_file, sleeps):
    body = auction_body({"PDI": [day([pr("N", 18.51, "6"), pr("N", 18.50, "M")])]})
    c, s = client(env_file, sleeps, route({"/v2/stocks/auctions": body}))
    out = c.closing_auction_prints(["PDI"], D, exchange_codes={"PDI": "N"})
    assert out["PDI"]["price"] == 18.50 and out["PDI"]["condition"] == "M"
    url, params = s.gets[0]
    assert url == al.DATA_BASE + "/v2/stocks/auctions"
    # Timestamps, never a bare date: end=<date> means "up to now" at Alpaca and
    # the Basic plan 403s any SIP query touching the last 15 minutes (2026-09-28).
    # 2026-09-29 is EDT (UTC-4): 00:00 ET = 04:00Z, 16:30 ET = 20:30Z.
    assert params["feed"] == "sip"
    assert params["start"] == "2026-09-29T04:00:00Z" and params["end"] == "2026-09-29T20:30:00Z"


def test_auction_window_follows_the_ny_clock_in_winter(env_file, sleeps):
    """EST (UTC-5) shifts the window an hour; a fixed UTC end would cut the auction."""
    w = dt.date(2026, 12, 1)
    body = auction_body({"PDI": [day([pr("N", 18.50, "M", t="2026-12-01T21:00:00Z")], d="2026-12-01")]})
    c, s = client(env_file, sleeps, route({"/v2/stocks/auctions": body}))
    c.closing_auction_prints(["PDI"], w, exchange_codes={"PDI": "N"})
    _, params = s.gets[0]
    assert params["start"] == "2026-12-01T05:00:00Z" and params["end"] == "2026-12-01T21:30:00Z"


def test_auction_missing_symbols_raise_by_name_and_no_bar_close_is_used(env_file, sleeps):
    body = auction_body({"PDI": [day([pr("N", 18.5)])], "PTY": [day([pr("N", 14.0, "6")])]})
    c, s = client(env_file, sleeps, route({"/v2/stocks/auctions": body}))
    with pytest.raises(al.MissingAuctionPrint) as e:
        c.closing_auction_prints(["PDI", "PTY", "NVG"], D,
                                 exchange_codes={"PDI": "N", "PTY": "N", "NVG": "N"})
    assert e.value.symbols == ["NVG", "PTY"]
    assert all("bars" not in u for u, _ in s.gets)


# ---- two prices from the primary (team lead's ruling, 2026-11-22; SCD on 2026-11-20)

SCD_PRINTS = [pr("P", 14.348, t="2026-09-29T20:00:00.25131479Z"), pr("T", 14.18, t="2026-09-29T20:00:00.5Z"),
              pr("N", 14.348, t="2026-09-29T20:00:02.365804871Z"), pr("N", 14.28, t="2026-09-29T20:10:00.003842801Z")]


def bars_body(sym, c, t="2026-09-29T04:00:00Z"):
    return FakeResp(200, {"bars": {sym: [{"t": t, "c": c}]}, "next_page_token": None})


def test_two_primary_prints_take_the_later_one_when_the_daily_bar_agrees(env_file, sleeps):
    c, s = client(env_file, sleeps, route({"/v2/stocks/auctions": auction_body({"SCD": [day(SCD_PRINTS)]}),
                                           "/v2/stocks/bars": bars_body("SCD", 14.28)}))
    out = c.closing_auction_prints(["SCD"], D, exchange_codes={"SCD": "N"})["SCD"]
    assert out["price"] == 14.28 and out["exchange"] == "N" and out["t"] == "2026-09-29T20:10:00.003842801Z"
    assert out["superseded"] == [{"price": 14.348, "t": "2026-09-29T20:00:02.365804871Z"}]
    url, params = s.gets[-1]
    assert url == al.DATA_BASE + "/v2/stocks/bars"
    # the auction query's own timestamps: a bare date would be refused on the evening itself
    assert (params["start"], params["end"]) == ("2026-09-29T04:00:00Z", "2026-09-29T20:30:00Z")
    assert params["symbols"] == "SCD" and params["adjustment"] == "raw" and params["feed"] == "sip"


def test_the_later_print_is_the_later_by_time_not_by_its_place_in_the_list(env_file, sleeps):
    c, _ = client(env_file, sleeps, route({"/v2/stocks/auctions": auction_body({"SCD": [day(SCD_PRINTS[::-1])]}),
                                           "/v2/stocks/bars": bars_body("SCD", 14.28)}))
    assert c.closing_auction_prints(["SCD"], D, exchange_codes={"SCD": "N"})["SCD"]["price"] == 14.28


@pytest.mark.parametrize("bars, why", [
    (bars_body("SCD", 14.348), "daily bar closes at 14.348"),             # the bar sides with the EARLIER print
    (bars_body("SCD", 14.30), "daily bar closes at 14.3"),                # the bar is neither
    (FakeResp(200, {"bars": {}, "next_page_token": None}), "0 daily bar"),
    (FakeResp(200, {"bars": None, "next_page_token": None}), "0 daily bar"),
])
def test_two_primary_prints_the_bar_does_not_confirm_still_raise(env_file, sleeps, bars, why):
    c, _ = client(env_file, sleeps, route({"/v2/stocks/auctions": auction_body({"SCD": [day(SCD_PRINTS)]}),
                                           "/v2/stocks/bars": bars}))
    with pytest.raises(al.AmbiguousAuctionPrint, match=why):
        c.closing_auction_prints(["SCD"], D, exchange_codes={"SCD": "N"})


def test_two_primary_prints_at_one_instant_raise_without_reading_a_bar(env_file, sleeps):
    same = [pr("N", 14.348, t="2026-09-29T20:10:00Z"), pr("N", 14.28, t="2026-09-29T20:10:00Z")]
    c, s = client(env_file, sleeps, route({"/v2/stocks/auctions": auction_body({"SCD": [day(same)]}),
                                           "/v2/stocks/bars": bars_body("SCD", 14.28)}))
    with pytest.raises(al.AmbiguousAuctionPrint, match="share the timestamp"):
        c.closing_auction_prints(["SCD"], D, exchange_codes={"SCD": "N"})
    assert all("bars" not in u for u, _ in s.gets)


def test_a_bar_for_another_day_never_confirms_a_print(env_file, sleeps):
    c, _ = client(env_file, sleeps, route({"/v2/stocks/auctions": auction_body({"SCD": [day(SCD_PRINTS)]}),
                                           "/v2/stocks/bars": bars_body("SCD", 14.28, t="2026-09-28T04:00:00Z")}))
    with pytest.raises(al.UnexpectedResponse, match="bar dated 2026-09-28"):
        c.closing_auction_prints(["SCD"], D, exchange_codes={"SCD": "N"})


def test_a_confirmed_pair_beside_a_missing_symbol_names_only_the_missing_one(env_file, sleeps):
    c, _ = client(env_file, sleeps, route({"/v2/stocks/auctions": auction_body({"SCD": [day(SCD_PRINTS)]}),
                                           "/v2/stocks/bars": bars_body("SCD", 14.28)}))
    with pytest.raises(al.MissingAuctionPrint) as e:
        c.closing_auction_prints(["SCD", "NVG"], D, exchange_codes={"SCD": "N", "NVG": "N"})
    assert e.value.symbols == ["NVG"]


def test_two_prices_a_few_nanoseconds_apart_are_a_tie(env_file, sleeps):
    """parse_ts keeps microseconds; below that the order is not known, so nothing is chosen."""
    near = [pr("N", 14.348, t="2026-09-29T20:10:00.000000100Z"), pr("N", 14.28, t="2026-09-29T20:10:00.000000900Z")]
    c, _ = client(env_file, sleeps, route({"/v2/stocks/auctions": auction_body({"SCD": [day(near)]}),
                                           "/v2/stocks/bars": bars_body("SCD", 14.28)}))
    with pytest.raises(al.AmbiguousAuctionPrint, match="share the timestamp"):
        c.closing_auction_prints(["SCD"], D, exchange_codes={"SCD": "N"})


def test_a_refused_bar_read_returns_no_price(env_file, sleeps):
    c, _ = client(env_file, sleeps, route({"/v2/stocks/auctions": auction_body({"SCD": [day(SCD_PRINTS)]}),
                                           "/v2/stocks/bars": FakeResp(403, text="subscription does not permit")}))
    with pytest.raises(al.AlpacaError):
        c.closing_auction_prints(["SCD"], D, exchange_codes={"SCD": "N"})


def test_the_confirming_bar_is_dated_in_new_york_in_winter(env_file, sleeps):
    w = dt.date(2026, 11, 20)                              # the real case; midnight New York is 05:00Z
    prints = [pr("N", 14.348, t="2026-11-20T21:00:02.365804871Z"), pr("N", 14.28, t="2026-11-20T21:10:00.003842801Z")]
    c, s = client(env_file, sleeps, route({"/v2/stocks/auctions": auction_body({"SCD": [day(prints, d="2026-11-20")]}),
                                           "/v2/stocks/bars": bars_body("SCD", 14.28, t="2026-11-20T05:00:00Z")}))
    assert c.closing_auction_prints(["SCD"], w, exchange_codes={"SCD": "N"})["SCD"]["price"] == 14.28
    assert (s.gets[-1][1]["start"], s.gets[-1][1]["end"]) == ("2026-11-20T05:00:00Z", "2026-11-20T21:30:00Z")


def test_one_price_printed_twice_reads_no_bar_and_names_nothing_superseded(env_file, sleeps):
    twice = [pr("N", 18.50, t="2026-09-29T20:00:00Z"), pr("N", 18.50, t="2026-09-29T20:10:00Z")]
    c, s = client(env_file, sleeps, route({"/v2/stocks/auctions": auction_body({"PDI": [day(twice)]})}))
    out = c.closing_auction_prints(["PDI"], D, exchange_codes={"PDI": "N"})["PDI"]
    assert out["price"] == 18.50 and "superseded" not in out
    assert all("bars" not in u for u, _ in s.gets)


def test_auction_only_the_primary_exchange_counts(env_file, sleeps):
    body = auction_body({"PDI": [day([pr("N", 18.50), pr("P", 18.49)])]})
    c, _ = client(env_file, sleeps, route({"/v2/stocks/auctions": body}))
    assert c.closing_auction_prints(["PDI"], D, exchange_codes={"PDI": "P"})["PDI"]["price"] == 18.49
    assert c.closing_auction_prints(["PDI"], D, exchange_codes={"PDI": "N"})["PDI"]["price"] == 18.50


def test_auction_agreeing_non_primary_prints_are_not_the_auction(env_file, sleeps):
    # Review 2026-09-28: the primary (N) had no auction print; Arca and Nasdaq
    # agree. The first build returned their price as "the official close".
    body = auction_body({"PDI": [day([pr("P", 18.49), pr("Q", 18.49)])]})
    c, _ = client(env_file, sleeps, route({"/v2/stocks/auctions": body}))
    with pytest.raises(al.MissingAuctionPrint) as e:
        c.closing_auction_prints(["PDI"], D, exchange_codes={"PDI": "N"})
    assert e.value.symbols == ["PDI"]


def test_auction_requires_a_primary_code_for_every_symbol(env_file, sleeps):
    c, s = client(env_file, sleeps, route({}))
    with pytest.raises(TypeError):
        c.closing_auction_prints(["PDI"], D)
    with pytest.raises(ValueError, match="no primary-exchange SIP code for \\['PTY'\\]"):
        c.closing_auction_prints(["PDI", "PTY"], D, exchange_codes={"PDI": "N"})
    assert s.gets == []


def test_auction_two_primary_prices_are_ambiguous(env_file, sleeps):
    # pr() gives both prints one timestamp, so this is the tie: no later print, nothing chosen.
    # Distinct times are the "two prices from the primary" tests above.
    body = auction_body({"PDI": [day([pr("N", 18.50), pr("N", 18.52)])]})
    c, _ = client(env_file, sleeps, route({"/v2/stocks/auctions": body}))
    with pytest.raises(al.AmbiguousAuctionPrint, match="PDI"):
        c.closing_auction_prints(["PDI"], D, exchange_codes={"PDI": "N"})


def test_primary_sip_code_maps_nyse_through_the_live_exchange_table(env_file, sleeps):
    c, s = client(env_file, sleeps, route({
        "/v2/stocks/meta/exchanges": FakeResp(200, {"N": "New York Stock Exchange",
                                                    "P": "NYSE Arca", "V": "IEX"}),
        "/v2/assets/PDI": FakeResp(200, asset_row())}))
    ex = c.stock_exchanges()
    assert s.gets[0][0] == al.DATA_BASE + "/v2/stocks/meta/exchanges"
    assert c.primary_sip_code("PDI", ex) == "N"


@pytest.mark.parametrize("exch,table,match", [
    ("ARCA", {"N": "New York Stock Exchange"}, "no verified SIP name"),
    ("NYSE", {"P": "NYSE Arca"}, "0 SIP codes"),
    ("NYSE", {"N": "New York Stock Exchange", "X": "New York Stock Exchange"}, "2 SIP codes"),
])
def test_primary_sip_code_refuses_to_guess(env_file, sleeps, exch, table, match):
    c, _ = client(env_file, sleeps, route({"/v2/assets/PDI": FakeResp(200, asset_row(exchange=exch))}))
    with pytest.raises(al.UnmappedExchange, match=match):
        c.primary_sip_code("PDI", table)


# ------------------------------------------- NYSE American and Nasdaq (2026-10-29)
#
# Fixtures are Alpaca's own responses, read 2026-10-29 on the cef paper key
# (GET /v2/stocks/meta/exchanges; GET /v2/stocks/auctions feed=sip, one symbol a
# query, as the collector asks), copied with their exchange codes, conditions,
# order and prices; `s` and `t` as read. docs/REFERENCES.md §12bl.

LIVE_EXCHANGES_2026_10_29 = {
    "A": "NYSE American (AMEX)", "B": "NASDAQ OMX BX", "C": "National Stock Exchange",
    "D": "FINRA ADF", "E": "Market Independent", "F": "Texas Stock Exchange", "G": "24X",
    "H": "MIAX", "I": "International Securities Exchange", "J": "Cboe EDGA", "K": "Cboe EDGX",
    "L": "Long Term Stock Exchange", "M": "Chicago Stock Exchange",
    "N": "New York Stock Exchange", "P": "NYSE Arca", "Q": "NASDAQ OMX",
    "S": "NASDAQ Small Cap", "T": "NASDAQ Int", "U": "Members Exchange", "V": "IEX",
    "W": "CBOE", "X": "NASDAQ OMX PSX", "Y": "Cboe BYX", "Z": "Cboe BZ"}


def lp(c, p, s, t, x):
    return {"c": c, "p": p, "s": s, "t": t, "x": x}


# Closing prints, 2026-10-27 unless dated otherwise.
LIVE_CLOSES = {
    # NYSE: Arca and "T" print an M before the primary's cross.
    "PDI": [lp("M", 14.08, 100, "2026-10-27T20:00:00.137198707Z", "P"),
            lp("M", 14.075, 100, "2026-10-27T20:00:00.380730393Z", "T"),
            lp("6", 14.07, 7479, "2026-10-27T20:00:03.142178435Z", "N"),
            lp("M", 14.07, 7479, "2026-10-27T20:00:03.158212613Z", "N")],
    # NYSE American: the primary A crosses; T's M is a cent off.
    "DHY": [lp("6", 16.37, 1257, "2026-10-27T20:00:00.097683295Z", "A"),
            lp("M", 16.37, 1257, "2026-10-27T20:00:00.098474191Z", "A"),
            lp("M", 16.37, 1257, "2026-10-27T20:00:00.228813719Z", "P"),
            lp("M", 16.36, 189, "2026-10-27T20:00:00.389925202Z", "T")],
    # NYSE American with no closing cross ("6") at all; T's differing M comes first.
    "GLV": [lp("M", 5.765, 67, "2026-10-27T20:00:00.059187266Z", "T"),
            lp("M", 5.7651, 100, "2026-10-27T20:00:00.107542222Z", "A"),
            lp("M", 5.7651, 100, "2026-10-27T20:00:00.168350101Z", "P")],
    # Nasdaq: the primary is Q (UTP); Arca's M is a cent off and comes first.
    "CHW": [lp("M", 7.89, 355, "2026-10-27T20:00:00.064324471Z", "P"),
            lp("6", 7.88, 3891, "2026-10-27T20:00:00.211276351Z", "Q"),
            lp("M", 7.88, 3891, "2026-10-27T20:00:00.211577579Z", "Q")],
    # Nasdaq, 2026-10-26: Arca's M is five cents off.
    "CSQ": [lp("M", 19.81, 100, "2026-10-26T20:00:00.076500739Z", "P"),
            lp("6", 19.86, 1254, "2026-10-26T20:00:00.098412875Z", "Q"),
            lp("M", 19.86, 1254, "2026-10-26T20:00:00.562280698Z", "Q")],
}
LIVE_DATES = {"CSQ": "2026-10-26"}
LIVE_ASSET_EXCHANGE = {"PDI": "NYSE", "DHY": "AMEX", "GLV": "AMEX", "CHW": "NASDAQ",
                       "CSQ": "NASDAQ"}


def live_route(syms, extra=None):
    """Exchange table, asset rows and per-symbol auction answers for `syms`."""
    def auctions(params):
        s = params["symbols"]
        assert s in syms, f"unexpected auctions query {s}"
        return auction_body({s: [day(LIVE_CLOSES[s], d=LIVE_DATES.get(s, "2026-10-27"))]})
    t = {"/v2/stocks/meta/exchanges": FakeResp(200, LIVE_EXCHANGES_2026_10_29),
         "/v2/stocks/auctions": auctions}
    for s in syms:
        t[f"/v2/assets/{s}"] = FakeResp(200, asset_row(symbol=s, exchange=LIVE_ASSET_EXCHANGE[s]))
    t.update(extra or {})
    return route(t)


def test_nyse_resolution_and_print_are_byte_identical_to_29e5dc0(env_file, sleeps):
    """THE NO-OP PROOF for NYSE names: the code, the chosen print and the gap
    message, compared as bytes with what 29e5dc0's code returns on the same
    fixture (the strings below were printed by running 29e5dc0's alpaca.py on
    it, 2026-10-29). A no-op cannot fail against the old behaviour, so this test
    passes on 29e5dc0 by design; it exists to fail if a later edit to the AMEX or
    Nasdaq rows ever reaches a NYSE name."""
    c, _ = client(env_file, sleeps, live_route({"PDI"}))
    code = c.primary_sip_code("PDI", c.stock_exchanges())
    assert repr(code) == "'N'"
    got = c.closing_auction_prints(["PDI"], dt.date(2026, 10, 27), exchange_codes={"PDI": code})
    assert json.dumps(got, sort_keys=True) == (
        '{"PDI": {"condition": "M", "exchange": "N", "price": 14.07, '
        '"t": "2026-10-27T20:00:03.158212613Z"}}')
    no_n = auction_body({"PDI": [day([p for p in LIVE_CLOSES["PDI"] if p["x"] != "N"],
                                     d="2026-10-27")]})
    c2, _ = client(env_file, sleeps, route({"/v2/stocks/auctions": no_n}))
    with pytest.raises(al.MissingAuctionPrint) as e:
        c2.closing_auction_prints(["PDI"], dt.date(2026, 10, 27), exchange_codes={"PDI": code})
    assert str(e.value) == (
        "no closing-auction print with condition 'M' on 2026-10-27 for ['PDI'] from the "
        "primary exchange {'PDI': 'N'}; another venue's print and a bar close are not "
        "substituted")
    assert al.ASSET_EXCHANGE_SIP_NAME["NYSE"] == "New York Stock Exchange"


@pytest.mark.parametrize("sym,exch,code", [("DHY", "AMEX", "A"), ("CHW", "NASDAQ", "Q")])
def test_amex_and_nasdaq_resolve_to_the_verified_codes(env_file, sleeps, sym, exch, code):
    """NYSE American prints as CTA participant A (CTS spec §4.3); Nasdaq-listed
    names as UTP market center Q (UTP spec §3.1). Alpaca's live table names
    them "NYSE American (AMEX)" and "NASDAQ OMX". Nasdaq's CTA code (Alpaca's
    "T", "NASDAQ Int") and the legacy "S" are other rows, never the primary."""
    c, _ = client(env_file, sleeps, live_route({sym}))
    assert c.primary_sip_code(sym, c.stock_exchanges()) == code
    assert al.ASSET_EXCHANGE_SIP_NAME[exch] == LIVE_EXCHANGES_2026_10_29[code]


def test_unmapped_exchanges_still_raise_and_a_drifted_name_is_never_guessed(env_file, sleeps):
    """Arca, BZX and OTC listings stay unmapped. And if Alpaca ever renames the
    Nasdaq or NYSE American row, the lookup raises: it never falls to another
    Nasdaq-named row ("NASDAQ Small Cap", "NASDAQ Int", "NASDAQ OMX BX")."""
    for exch in ("ARCA", "BATS", "OTC"):
        c, _ = client(env_file, sleeps, route({"/v2/assets/PDI": FakeResp(200, asset_row(exchange=exch))}))
        with pytest.raises(al.UnmappedExchange, match="no verified SIP name"):
            c.primary_sip_code("PDI", LIVE_EXCHANGES_2026_10_29)
    for exch, code in (("NASDAQ", "Q"), ("AMEX", "A")):
        drifted = {k: v for k, v in LIVE_EXCHANGES_2026_10_29.items() if k != code}
        c, _ = client(env_file, sleeps, route({"/v2/assets/PDI": FakeResp(200, asset_row(exchange=exch))}))
        with pytest.raises(al.UnmappedExchange, match="0 SIP codes"):
            c.primary_sip_code("PDI", drifted)


@pytest.mark.parametrize("sym,price,exch", [
    ("DHY", 16.37, "A"),     # NYSE American, crossed; not T's 16.36
    ("GLV", 5.7651, "A"),    # NYSE American, no cross; not T's earlier 5.765
    ("CHW", 7.88, "Q"),      # Nasdaq; not Arca's earlier 7.89
    ("CSQ", 19.86, "Q"),     # Nasdaq; not Arca's earlier 19.81
])
def test_live_auction_fixture_selects_the_primary_official_close(env_file, sleeps, sym, price, exch):
    """Through the collector's own two calls. Each expected price equals
    Nasdaq.com's published close for that fund and day (fetched 2026-10-29)."""
    c, _ = client(env_file, sleeps, live_route({sym}))
    code = c.primary_sip_code(sym, c.stock_exchanges())
    d = dt.date.fromisoformat(LIVE_DATES.get(sym, "2026-10-27"))
    got = c.closing_auction_prints([sym], d, exchange_codes={sym: code}, condition="M")
    assert got[sym]["price"] == price and got[sym]["exchange"] == exch
    assert got[sym]["condition"] == "M"


def test_verify_fetch_prints_scores_amex_and_nasdaq_names(env_file, sleeps):
    """verify.fetch_prints over a mixed day: until 2026-10-29 DHY and CHW were
    UnmappedExchange gaps, so the day could not be scored on the official close."""
    from quantt.session import verify
    c, _ = client(env_file, sleeps, live_route({"PDI", "DHY", "CHW"}))
    out = verify.fetch_prints(c, ["PDI", "DHY", "CHW"], dt.date(2026, 10, 27), condition="M")
    assert out.gaps == {}
    assert out.prices == {"PDI": 14.07, "DHY": 16.37, "CHW": 7.88}


@pytest.mark.parametrize("body", [{}, [], {"stock_exchanges": {"N": "x"}}, {"N": ""}])
def test_stock_exchanges_strict_shape(env_file, sleeps, body):
    c, _ = client(env_file, sleeps, route({"/v2/stocks/meta/exchanges": FakeResp(200, body)}))
    with pytest.raises(al.UnexpectedResponse):
        c.stock_exchanges()


def test_auction_pages_on_next_page_token(env_file, sleeps):
    pages = {None: auction_body({"PDI": [day([pr("N", 18.5)])]}, token="tok1"),
             "tok1": auction_body({"PTY": [day([pr("N", 14.0)])]})}
    c, s = client(env_file, sleeps, route({"/v2/stocks/auctions": lambda p: pages[p.get("page_token")]}))
    out = c.closing_auction_prints(["PTY", "PDI"], D, exchange_codes={"PDI": "N", "PTY": "N"})
    assert {k: v["price"] for k, v in out.items()} == {"PDI": 18.5, "PTY": 14.0}
    assert len(s.gets) == 2


def test_auction_a_different_day_raises(env_file, sleeps):
    body = auction_body({"PDI": [day([pr("N", 18.5)], d="2026-09-28")]})
    c, _ = client(env_file, sleeps, route({"/v2/stocks/auctions": body}))
    with pytest.raises(al.UnexpectedResponse, match="not the requested"):
        c.closing_auction_prints(["PDI"], D, exchange_codes={"PDI": "N"})


# ------------------------------------------------------ distributions (corporate actions)

def ca_body(cash=(), cg=(), token=None):
    return FakeResp(200, {"corporate_actions": {"cash_dividends": list(cash),
                                                "capital_gains_distributions": list(cg)},
                          "next_page_token": token})


def cash(sym, ex, rate, i=None, **kw):
    r = {"id": i or f"{sym}-{ex}", "symbol": sym, "cusip": "x", "ex_date": ex, "rate": rate,
         "special": False, "foreign": False, "process_date": ex}
    r.update(kw)
    return r


def test_distributions_parse_cash_and_capital_gains_and_ask_for_both_types(env_file, sleeps):
    body = ca_body(cash=[cash("PDI", "2026-10-13", 0.2205)],
                   cg=[{"id": "cg1", "symbol": "PDI", "cusip": "x", "ex_date": "2026-12-26",
                        "process_date": "2027-01-08", "long_term_rate": 0.4, "short_term_rate": 0.1}])
    c, s = client(env_file, sleeps, route({"/v1/corporate-actions": body}))
    out = c.distributions(["PDI"], dt.date(2026, 9, 1), dt.date(2027, 2, 1))
    assert [(e["kind"], e["ex_date"], e["amount"]) for e in out] == [
        ("cash_dividend", dt.date(2026, 10, 13), 0.2205),
        ("capital_gains_distribution", dt.date(2026, 12, 26), pytest.approx(0.5))]
    url, params = s.gets[0]
    assert url == al.DATA_BASE + "/v1/corporate-actions"
    assert params["types"] == "cash_dividend,capital_gains_distribution"
    assert params["start"] == "2026-09-01" and params["end"] == "2027-02-01"


def test_distributions_refuse_an_unrequested_symbol(env_file, sleeps):
    c, _ = client(env_file, sleeps, route({"/v1/corporate-actions": ca_body(cash=[cash("PTY", "2026-10-13", 0.1)])}))
    with pytest.raises(al.UnexpectedResponse, match="unrequested symbol"):
        c.distributions(["PDI"], dt.date(2026, 9, 1), dt.date(2026, 12, 1))


@pytest.mark.parametrize("bad", [{"rate": None}, {"ex_date": "13/10/2026"}, {"rate": -0.1}])
def test_distributions_never_default_a_bad_field(env_file, sleeps, bad):
    r = cash("PDI", "2026-10-13", 0.2)
    r.update(bad)
    c, _ = client(env_file, sleeps, route({"/v1/corporate-actions": ca_body(cash=[r])}))
    with pytest.raises(al.UnexpectedResponse):
        c.distributions(["PDI"], dt.date(2026, 9, 1), dt.date(2026, 12, 1))


def test_distributions_a_missing_rate_raises_not_keyerror(env_file, sleeps):
    r = cash("PDI", "2026-10-13", 0.2)
    del r["rate"]
    c, _ = client(env_file, sleeps, route({"/v1/corporate-actions": ca_body(cash=[r])}))
    with pytest.raises(al.UnexpectedResponse, match="rate"):
        c.distributions(["PDI"], dt.date(2026, 9, 1), dt.date(2026, 12, 1))


def test_distributions_a_capital_gains_event_with_no_rate_raises(env_file, sleeps):
    cg = {"id": "cg1", "symbol": "PDI", "cusip": "x", "ex_date": "2026-12-26", "process_date": "2027-01-08"}
    c, _ = client(env_file, sleeps, route({"/v1/corporate-actions": ca_body(cg=[cg])}))
    with pytest.raises(al.UnexpectedResponse, match="neither"):
        c.distributions(["PDI"], dt.date(2026, 9, 1), dt.date(2027, 2, 1))


def test_distributions_page_on_next_page_token_and_drop_repeats(env_file, sleeps):
    pages = {None: ca_body(cash=[cash("PDI", "2026-10-13", 0.2205, i="e1")], token="t2"),
             "t2": ca_body(cash=[cash("PDI", "2026-10-13", 0.2205, i="e1"),
                                 cash("PDI", "2026-11-12", 0.2205, i="e2")])}
    c, s = client(env_file, sleeps, route({"/v1/corporate-actions": lambda p: pages[p.get("page_token")]}))
    out = c.distributions(["PDI"], dt.date(2026, 9, 1), dt.date(2026, 12, 1))
    assert [e["id"] for e in out] == ["e1", "e2"] and len(s.gets) == 2


def test_distributions_refuse_an_inverted_window(env_file, sleeps):
    c, _ = client(env_file, sleeps)
    with pytest.raises(ValueError, match="before start"):
        c.distributions(["PDI"], dt.date(2026, 12, 1), dt.date(2026, 9, 1))


# ------------------------------------------- non-dividend corporate actions (the gate's read)
#
# CA_REFERENCE is the response shape recorded from Alpaca's own reference: the
# `examples` of each type's schema in the Market Data API's GET
# /v1/corporate-actions, copied verbatim (fetched 2026-10-28 through the Alpaca
# docs tool; docs/REFERENCES.md §12pc). It is not a live read: the runner's
# keys are never used by a test, and no agent reads them. The reference gives no
# example for `reorganization` or `partial_call`; those two rows are built from
# the reference's field lists and are labelled so. Synthetic data tests whether
# the parser behaves, never a claim about the market (CLAUDE.md).

CA_REFERENCE = {
    "reverse_splits": [{"ex_date": "2023-08-24", "id": "913de862-c02c-46dc-a89c-fc8779a50d30",
                        "new_cusip": "60879E200", "new_rate": 1, "old_cusip": "60879E101",
                        "old_rate": 50, "process_date": "2023-08-24",
                        "record_date": "2023-08-24", "symbol": "MNTS"}],
    "forward_splits": [{"cusip": "816851109", "due_bill_redemption_date": "2023-08-23",
                        "ex_date": "2023-08-22", "id": "189bd849-ab9f-4b4d-aaaa-a6d415fd976d",
                        "new_rate": 2, "old_rate": 1, "payable_date": "2023-08-21",
                        "process_date": "2023-08-22", "record_date": "2023-08-14",
                        "symbol": "SRE"}],
    "unit_splits": [{"alternate_cusip": "G5391L110", "alternate_rate": 0.3333,
                     "alternate_symbol": "LVROW", "effective_date": "2023-03-01",
                     "id": "3e68e87e-ae95-4d68-91d1-715d52ef143a", "new_cusip": "G5391L102",
                     "new_rate": 1, "new_symbol": "LVRO", "old_cusip": "G8990L119",
                     "old_rate": 1, "old_symbol": "TPBAU", "process_date": "2023-03-01"}],
    "stock_dividends": [{"cusip": "605015106", "ex_date": "2023-05-19",
                         "id": "3ae94c30-2d37-473a-bf29-5f7b4ab6d3ca",
                         "payable_date": "2023-05-05", "process_date": "2023-05-19",
                         "rate": 0.05, "record_date": "2023-05-22", "symbol": "MSBC"}],
    "spin_offs": [{"ex_date": "2023-08-15", "id": "82e602f6-35bc-4651-a5dd-f6d88ff37c55",
                   "new_cusip": "85237B101", "new_rate": 1, "new_symbol": "SRM",
                   "process_date": "2023-08-15", "record_date": "2023-08-15",
                   "source_cusip": "48208F105", "source_rate": 19.35, "source_symbol": "JUPW"}],
    "cash_mergers": [{"acquiree_cusip": "Y2687W108", "acquiree_symbol": "GLOP",
                      "effective_date": "2023-07-17", "id": "3772bbd7-4ad5-44d4-9cc0-f69156a2f8f5",
                      "payable_date": "2023-07-17", "process_date": "2023-07-17", "rate": 5.37}],
    "stock_mergers": [{"acquiree_cusip": "53223X107", "acquiree_rate": 1, "acquiree_symbol": "LSI",
                       "acquirer_cusip": "30225T102", "acquirer_rate": 0.895,
                       "acquirer_symbol": "EXR", "effective_date": "2023-07-20",
                       "id": "728f8cb2-a00e-4bc7-ad14-d15fe82bbcff",
                       "payable_date": "2023-07-20", "process_date": "2023-07-20"}],
    "stock_and_cash_mergers": [{"acquiree_cusip": "561409103", "acquiree_rate": 1,
                                "acquiree_symbol": "MLVF", "acquirer_cusip": "31931U102",
                                "acquirer_rate": 0.7733, "acquirer_symbol": "FRBA",
                                "cash_rate": 7.8, "effective_date": "2023-07-18",
                                "id": "e5248356-2c06-42cf-aeb9-1595bd616cdb",
                                "payable_date": "2023-07-18", "process_date": "2023-07-18"}],
    "redemptions": [{"cusip": "687305102", "id": "395da031-0e57-4918-a6fb-64a7c713aca4",
                     "payable_date": "2023-06-13", "process_date": "2023-06-13",
                     "rate": 0.141134, "symbol": "ORPHY"}],
    "name_changes": [{"id": "5a774c35-edec-4532-a812-a56d0bbb623a", "new_cusip": "Y9390M103",
                      "new_symbol": "VFS", "old_cusip": "G11537100", "old_symbol": "BSAQ",
                      "process_date": "2023-08-15"}],
    "worthless_removals": [{"cusip": "078771300", "id": "106c2149-ee04-4d2e-a943-98dbb4d21a3c",
                            "process_date": "2024-12-19", "symbol": "BLPH"}],
    # built from the reference's field lists (no example given there):
    "reorganizations": [{"id": "reorg-schema-1", "symbol": "OLDF", "cusip": "x",
                         "effective_date": "2023-09-01", "process_date": "2023-09-01",
                         "cash_rate": 0.5,
                         "stock_movements": [{"symbol": "NEWF", "cusip": "y", "new_rate": 1.2,
                                              "source_rate": 1}]}],
    "partial_calls": [{"id": "pcall-schema-1", "symbol": "PCAL", "process_date": "2023-10-02",
                       "price": 25.0}],
}


def ca_page(actions=None, token=None):
    return FakeResp(200, {"corporate_actions": actions if actions is not None else CA_REFERENCE,
                          "next_page_token": token})


def ca_client(env_file, sleeps, page=None):
    return client(env_file, sleeps, route({"/v1/corporate-actions": page or ca_page()}))


W0, W1 = dt.date(2023, 1, 1), dt.date(2025, 1, 1)


def test_corporate_actions_ask_for_the_thirteen_types_and_send_no_symbols_filter(env_file, sleeps):
    """The reference does not say which field `symbols=` matches on a merger, a
    spin-off or a name change, so a server-side filter could drop a held
    acquirer in silence. The request carries types and the window only."""
    c, s = ca_client(env_file, sleeps)
    c.corporate_actions(["EXR"], W0, W1)
    url, params = s.gets[0]
    assert url == al.DATA_BASE + "/v1/corporate-actions"
    assert "symbols" not in params
    assert params["types"].split(",") == [
        "reverse_split", "forward_split", "unit_split", "stock_dividend", "spin_off",
        "cash_merger", "stock_merger", "stock_and_cash_merger", "redemption", "name_change",
        "worthless_removal", "reorganization", "partial_call"]
    assert "cash_dividend" not in params["types"] and "rights_distribution" not in params["types"]
    assert params["start"] == "2023-01-01" and params["end"] == "2025-01-01"
    # team lead's review 2026-10-29: the early, unprocessed records too
    assert params["data_quality"] == "all"


def test_corporate_actions_map_the_acquirer_and_the_acquiree_of_a_merger(env_file, sleeps):
    c, _ = ca_client(env_file, sleeps)
    acq = c.corporate_actions(["EXR"], W0, W1)            # held as the ACQUIRER
    assert [(e["type"], e["parties"]) for e in acq] == [
        ("stock_merger", [["LSI", "acquiree"], ["EXR", "acquirer"]])]
    tgt = c.corporate_actions(["MLVF"], W0, W1)           # held as the ACQUIREE
    assert [(e["type"], e["parties"]) for e in tgt] == [
        ("stock_and_cash_merger", [["MLVF", "acquiree"], ["FRBA", "acquirer"]])]
    assert tgt[0]["date"] == dt.date(2023, 7, 18) and tgt[0]["date_field"] == "effective_date"
    # a cash merger's acquirer is optional in the reference, and absent here
    cash_m = c.corporate_actions(["GLOP"], W0, W1)
    assert cash_m[0]["parties"] == [["GLOP", "acquiree"]]


@pytest.mark.parametrize("sym,typ,date_field,date,role", [
    ("MNTS", "reverse_split", "ex_date", "2023-08-24", "subject"),
    ("SRE", "forward_split", "ex_date", "2023-08-22", "subject"),
    ("LVROW", "unit_split", "effective_date", "2023-03-01", "alternate"),
    ("TPBAU", "unit_split", "effective_date", "2023-03-01", "old"),
    ("MSBC", "stock_dividend", "ex_date", "2023-05-19", "subject"),
    ("JUPW", "spin_off", "ex_date", "2023-08-15", "source"),
    ("SRM", "spin_off", "ex_date", "2023-08-15", "new"),
    ("ORPHY", "redemption", "process_date", "2023-06-13", "subject"),
    ("BSAQ", "name_change", "process_date", "2023-08-15", "old"),
    ("VFS", "name_change", "process_date", "2023-08-15", "new"),
    ("BLPH", "worthless_removal", "process_date", "2024-12-19", "subject"),
    ("OLDF", "reorganization", "effective_date", "2023-09-01", "subject"),
    ("NEWF", "reorganization", "effective_date", "2023-09-01", "allocated"),
    ("PCAL", "partial_call", "process_date", "2023-10-02", "subject"),
])
def test_corporate_actions_parse_every_type_of_the_reference(env_file, sleeps, sym, typ,
                                                             date_field, date, role):
    c, _ = ca_client(env_file, sleeps)
    out = c.corporate_actions([sym], W0, W1)
    assert len(out) == 1
    e = out[0]
    assert (e["type"], e["date_field"], e["date"]) == (typ, date_field, dt.date.fromisoformat(date))
    assert [sym, role] in e["parties"]
    assert isinstance(e["process_date"], dt.date)


def test_corporate_actions_return_only_events_naming_a_requested_symbol(env_file, sleeps):
    c, _ = ca_client(env_file, sleeps)
    assert c.corporate_actions(["PDI", "PTY"], W0, W1) == []
    out = c.corporate_actions(["EXR", "MNTS"], W0, W1)
    assert [e["id"] for e in out] == ["728f8cb2-a00e-4bc7-ad14-d15fe82bbcff",
                                      "913de862-c02c-46dc-a89c-fc8779a50d30"]   # oldest first


def test_a_cash_mergers_acquirer_is_mapped_when_the_row_names_one(env_file, sleeps):
    """Review 2026-10-29 (d). The reference's own cash-merger example has no
    acquirer (the field is optional there); this row, built from the
    reference's field list, has one, and both sides must be returned."""
    row = dict(CA_REFERENCE["cash_mergers"][0], acquirer_symbol="ACQR", acquirer_cusip="z")
    c, _ = ca_client(env_file, sleeps, ca_page({"cash_mergers": [row]}))
    out = c.corporate_actions(["ACQR"], W0, W1)
    assert [(e["type"], e["parties"]) for e in out] == [
        ("cash_merger", [["GLOP", "acquiree"], ["ACQR", "acquirer"]])]


# A reorganization row as the real feed serves it: read-only through the Alpaca
# connector, 2026-10-29, data_quality=complete (docs/REFERENCES.md §12pc). 29 of
# the twelve months' 103 reorganizations carry legs like these: a CUSIP and an
# empty symbol. The first commit's parser raised on the first one, which would
# have refused every session under `halt`.
REAL_REORG_NO_TICKER = {
    "id": "c0ae9bf6-e857-407a-91de-b675630d66d3", "symbol": "AIMTF",
    "effective_date": "2026-07-28", "process_date": "2026-07-31",
    "stock_movements": [{"cusip": "G0137D100", "new_rate": 1, "source_rate": 1, "symbol": ""},
                        {"cusip": "G0137D118", "new_rate": 0.5, "source_rate": 1, "symbol": ""}]}


def test_a_reorganization_leg_with_no_ticker_but_a_cusip_names_nobody(env_file, sleeps):
    c, _ = ca_client(env_file, sleeps, ca_page({"reorganizations": [REAL_REORG_NO_TICKER]}))
    out = c.corporate_actions(["AIMTF"], W0, W1)
    assert [(e["type"], e["parties"]) for e in out] == [("reorganization", [["AIMTF", "subject"]])]
    assert c.corporate_actions(["PDI"], W0, W1) == []                 # and never raises for others
    null_leg = dict(REAL_REORG_NO_TICKER, stock_movements=[{"cusip": "G0137D100", "symbol": None}])
    c, _ = ca_client(env_file, sleeps, ca_page({"reorganizations": [null_leg]}))
    assert c.corporate_actions(["AIMTF"], W0, W1)[0]["parties"] == [["AIMTF", "subject"]]


@pytest.mark.parametrize("leg", [{"symbol": "", "cusip": ""}, {"symbol": None},
                                 {"symbol": "", "cusip": None}, {"cusip": "G0137D100"},
                                 {"symbol": 7, "cusip": "G0137D100"}])
def test_a_reorganization_leg_that_cannot_be_identified_still_raises(env_file, sleeps, leg):
    """Neither a ticker nor a CUSIP, a missing symbol key, or a symbol that is
    not a string: the leg cannot be shown not to be ours, so the read fails."""
    row = dict(REAL_REORG_NO_TICKER, stock_movements=[leg])
    c, _ = ca_client(env_file, sleeps, ca_page({"reorganizations": [row]}))
    with pytest.raises(al.UnexpectedResponse, match="stock_movements"):
        c.corporate_actions(["PDI"], W0, W1)


# UNRESOLVED ROWS (docs/SYSTEM.md §5, team lead 2026-11-02 (unresolved
# corporate-action rows)): a row with a null or empty PARTY symbol is returned
# as an unresolved event, its missing fields named, never raised on when the
# caller records; the gate decides whether it blocks (test_ca_malformed_and_acks).
# Skip-and-record (team lead 2026-10-29) stays for a row whose every party is
# present and none ours, with a NON-party field malformed. The rows are the
# reference's examples with one field spoiled. The unresolved tests FAIL on
# 709d6cb, which refused every such row; the non-party tests on 04aca24.
UNI = ["PDI", "PTY"]                                  # the book's universe in these tests
NULL_ACQUIRER = dict(CA_REFERENCE["stock_mergers"][0], id="sm-null", acquirer_symbol=None)
EMPTY_SPLIT = dict(CA_REFERENCE["forward_splits"][0], id="fs-empty", symbol="")
NO_TICKER_LEG = dict(REAL_REORG_NO_TICKER, id="reorg-bad-leg",
                     stock_movements=[{"symbol": None, "new_rate": 1, "source_rate": 1}])


def _party_cases():
    """(key, row, field) for every REQUIRED party field of every type, from
    alpaca.CORPORATE_ACTION_TYPES itself, each set to None and to ""."""
    out = []
    for kind, (key, _, fields) in al.CORPORATE_ACTION_TYPES.items():
        for f, role, req in fields:
            if req:
                for v in (None, ""):
                    out.append(pytest.param(key, dict(CA_REFERENCE[key][0], id=f"{kind}-{f}",
                                                      **{f: v}), f,
                                            id=f"{kind}-{role}-{'null' if v is None else 'empty'}"))
    return out


@pytest.mark.parametrize("key,row,field", _party_cases())
def test_every_null_or_empty_party_symbol_is_returned_unresolved(env_file, sleeps, key, row,
                                                                 field):
    """Whatever else the row names (here nothing of ours), it is returned, not
    raised on: its id, the missing field and its role, the present parties.
    Without a record to go to, the read raises on it as it always did."""
    c, _ = ca_client(env_file, sleeps, ca_page({key: [row]}))
    got = c.corporate_actions(["PDI"], W0, W1, universe=UNI, skipped=[])
    kind = next(k for k, v in al.CORPORATE_ACTION_TYPES.items() if v[0] == key)
    role = next(r for f, r, _ in al.CORPORATE_ACTION_TYPES[kind][2] if f == field)
    assert [(e["id"], e["type"], e["missing"], e["row_id"]) for e in got] == [
        (row["id"], kind, [{"field": field, "role": role}], row["id"])]
    assert [field, role] not in got[0]["parties"]
    with pytest.raises(al.UnexpectedResponse, match="is not a symbol"):
        c.corporate_actions(["PDI"], W0, W1)


def test_the_null_acquirer_repro_is_returned_unresolved(env_file, sleeps):
    """The release-check's repro (2026-11-01): a stock merger, acquiree MYD
    outside the universe, acquirer null. Returned with its acquirer missing;
    whether it blocks is the gate's (it does, for a held MQY on its merger
    date: test_ca_malformed_and_acks)."""
    base = dict(CA_REFERENCE["stock_mergers"][0], acquiree_symbol="MYD",
                effective_date="2026-11-03", process_date="2026-11-03")
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": [dict(base, id="sm-None",
                                                                       acquirer_symbol=None)]}))
    skipped = []
    got = c.corporate_actions(["MQY"], dt.date(2026, 11, 2), dt.date(2026, 11, 3),
                              universe=["MQY", "MHD"], skipped=skipped)
    assert [(e["id"], e["parties"], e["missing"]) for e in got] == [
        ("sm-None", [["MYD", "acquiree"]], [{"field": "acquirer_symbol", "role": "acquirer"}])]
    assert skipped == []


@pytest.mark.parametrize("leg", [{"symbol": None, "new_rate": 1},
                                 {"symbol": "", "cusip": "", "new_rate": 1},
                                 {"symbol": "", "cusip": None, "new_rate": 1}],
                         ids=["null", "empty-empty-cusip", "empty-null-cusip"])
def test_a_null_reorganization_leg_is_returned_unresolved(env_file, sleeps, leg):
    """A leg with no ticker and no CUSIP: the allocated security could be one
    of ours. (A leg with no ticker but a CUSIP still names nobody: the
    measured exception, above.)"""
    c, _ = ca_client(env_file, sleeps,
                     ca_page({"reorganizations": [dict(NO_TICKER_LEG, stock_movements=[leg])]}))
    (e,) = c.corporate_actions(["PDI"], W0, W1, universe=UNI, skipped=[])
    assert e["missing"] == [{"field": "stock_movements[0].symbol", "role": "allocated"}]
    assert e["parties"] == [["AIMTF", "subject"]]


def test_an_unresolved_row_with_a_null_id_is_keyed_by_its_hash(
        env_file, sleeps):
    """A null id AND a null party: keyed by the SHA-256 of the raw row, so the
    team lead can acknowledge it; any change to the row is another key. Named
    one of `symbols` it is keyed the same way (2026-11-02; it raised until
    7df8926)."""
    row = dict(NULL_ACQUIRER, id=None)
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": [row]}))
    (e,) = c.corporate_actions(["PDI"], W0, W1, universe=UNI, skipped=[])
    assert e["id"] == al.ca_row_key(row) and e["id"].startswith("row-sha256:")
    assert e["row_id"] is None and al.ca_row_key(dict(row, acquiree_rate=2)) != e["id"]
    named = dict(row, acquiree_symbol="PDI")         # names ours: keyed by content too
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": [named]}))
    (e,) = c.corporate_actions(["PDI"], W0, W1, universe=UNI, skipped=[])
    assert e["id"] == al.ca_row_key(named) and e["parties"] == [["PDI", "acquiree"]]



@pytest.mark.parametrize("spoil", [{"effective_date": None}, {"process_date": "2023-7-20"},
                                   {"effective_date": "", "id": None}],
                         ids=["date-null", "process-date-bad", "date-empty-id-null"])
def test_an_undated_unresolved_row_is_returned_keyed_by_its_hash(env_file, sleeps, spoil):
    """Release-check of d90e68f (2026-11-02): a null party AND an unreadable
    date used to raise, which only a release could unstick. It is returned,
    `undated` naming the bad fields and their values, its unreadable dates
    None, keyed by `ca_row_key` whatever its id, so ca-ack can clear it and a
    revision is a new key. (Corrected 2026-11-02: this test asserted the
    raise.) FAILS on d90e68f."""
    row = dict(NULL_ACQUIRER, **spoil)
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": [row]}))
    (e,) = c.corporate_actions(["PDI"], W0, W1, universe=UNI, skipped=[])
    bad = {k: v for k, v in spoil.items() if k != "id"}
    assert e["undated"] == bad and e["id"] == al.ca_row_key(row) and e["row_id"] == row["id"]
    assert (e["date"] is None) == ("effective_date" in bad)
    assert (e["process_date"] is None) == ("process_date" in bad)
    assert e["missing"] == [{"field": "acquirer_symbol", "role": "acquirer"}]


@pytest.mark.parametrize("spoil,bad", [
    ({"id": None}, {"id": None}),
    ({"id": ""}, {"id": ""}),
    ({"effective_date": "2023-7-20"}, {"effective_date": "2023-7-20"}),
    ({"process_date": None}, {"process_date": None}),
], ids=["null-id", "empty-id", "bad-date", "null-process-date"])
def test_a_row_with_every_party_present_and_not_ours_and_a_nonparty_fault_is_skipped_and_recorded(
        env_file, sleeps, spoil, bad):
    """The skip-and-record path, and the only one: LSI and EXR are present and
    not ours; the id or a date is spoiled. Recorded with the fault and its
    value. The same fault on a row naming a fund of the universe is returned
    keyed by its content, for the gate to judge (2026-11-02; it raised until
    7df8926), and without a record to go to such a row is not read at all."""
    row = dict(CA_REFERENCE["stock_mergers"][0], **spoil)
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": [row]}))
    skipped = []
    assert c.corporate_actions(["PDI"], W0, W1, universe=UNI, skipped=skipped) == []
    assert skipped == [{"id": row.get("id"), "type": "stock_merger", "malformed": bad,
                        "present": [["LSI", "acquiree"], ["EXR", "acquirer"]],
                        "cusips": {"acquiree_cusip": "53223X107", "acquirer_cusip": "30225T102"},
                        "dates": {f: row.get(f) for f in ("effective_date", "process_date")
                                  if f in row}}]
    ours = dict(row, acquirer_symbol="PTY")
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": [ours]}))
    skipped = []
    (e,) = c.corporate_actions(["PDI"], W0, W1, universe=UNI, skipped=skipped)
    assert skipped == [] and e["id"] == al.ca_row_key(ours) and e["row_id"] == ours.get("id")
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": [row]}))
    assert c.corporate_actions(["PDI"], W0, W1) == []


def test_well_formed_rows_read_exactly_as_before_with_the_record(env_file, sleeps):
    """The reference's rows, all well-formed: the same events with the record as
    without, and nothing skipped. The two keywords go together."""
    syms = ["EXR", "MLVF", "GLOP", "MNTS", "OLDF", "NEWF", "VFS", "PCAL"]
    c, _ = ca_client(env_file, sleeps)
    before = c.corporate_actions(syms, W0, W1)
    skipped = []
    c, _ = ca_client(env_file, sleeps)
    assert c.corporate_actions(syms, W0, W1, universe=UNI, skipped=skipped) == before
    assert skipped == [] and len(before) == 7          # OLDF and NEWF are one event
    for kw in ({"universe": UNI}, {"skipped": []}):
        with pytest.raises(ValueError, match="go together"):
            c.corporate_actions(syms, W0, W1, **kw)


# ONE ID, ONE EVENT (release-check of 9630322, 2026-10-30, reproduced by the
# reviewer). Rows naming ours were de-duplicated on the raw `id`, whose key was
# only required to be present, so two `id: null` rows were "one id" and the
# second was dropped: the probe's NVG split, effective on the session date,
# vanished and the gate read CLEAR under `halt`. Every test here FAILS on
# 9630322. Rows: the probe's two null-id reverse splits, otherwise the
# reference's reverse-split shape.
def _rsplit(sym, ex, i):
    return {"id": i, "symbol": sym, "ex_date": ex, "process_date": ex, "old_rate": 2,
            "new_rate": 1}


PROBE_NULL_IDS = [_rsplit("NAD", "2026-08-03", None), _rsplit("NVG", "2026-10-30", None)]


@pytest.mark.parametrize("rows", [PROBE_NULL_IDS, [_rsplit("NVG", "2026-10-30", "")],
                                  [_rsplit("NVG", "2026-10-30", "  ")],
                                  [_rsplit("NVG", "2026-10-30", 7)]],
                         ids=["probe-two-null-ids", "empty-id", "blank-id", "int-id"])
def test_a_row_naming_ours_without_a_string_id_is_keyed_by_its_content(env_file, sleeps, rows):
    """With a record to go to (the gate's and ca-ack's read), a row naming ours
    with a null, empty, blank or non-string id is returned keyed by
    `ca_row_key`, `row_id` the id as sent; none is dropped, so the probe's
    second null-id row stays in view (team lead 2026-11-02: nothing may need a
    release to unstick; it was a raise until 7df8926, which FAILS here).
    Without a record, the strict read raises as before."""
    c, _ = ca_client(env_file, sleeps, ca_page({"reverse_splits": rows}))
    got = c.corporate_actions(["NAD", "NVG"], W0, dt.date(2028, 1, 1),
                              universe=["NAD", "NVG"], skipped=[], rows={})
    assert sorted((e["id"], e["row_id"]) for e in got) == sorted(
        (al.ca_row_key(r), r["id"]) for r in rows)
    with pytest.raises(al.UnexpectedResponse, match="not a non-empty string"):
        c.corporate_actions(["NAD", "NVG"], W0, dt.date(2028, 1, 1))


def test_a_repeated_id_identical_is_dropped_and_different_refuses(env_file, sleeps):
    """A page boundary can repeat a row: an identical repeat, on one page or on
    the next, is one event, as before. The same id with a different event (a
    date, the type or the parties) cannot be resolved, and refuses."""
    one = _rsplit("NVG", "2026-10-30", "rs-1")
    c, _ = ca_client(env_file, sleeps, ca_page({"reverse_splits": [one, dict(one)]}))
    assert [e["id"] for e in c.corporate_actions(["NVG"], W0, dt.date(2028, 1, 1))] == ["rs-1"]
    pages = {None: ca_page({"reverse_splits": [one]}, token="p2"),
             "p2": ca_page({"reverse_splits": [dict(one)]})}
    c, _ = ca_client(env_file, sleeps, lambda p: pages[p.get("page_token")])
    assert len(c.corporate_actions(["NVG"], W0, dt.date(2028, 1, 1))) == 1
    for other in (dict(one, ex_date="2026-11-02"),                      # another date
                  dict(one, symbol="NAD")):                              # another party
        pages = {None: ca_page({"reverse_splits": [one]}, token="p2"),
                 "p2": ca_page({"reverse_splits": [other]})}
        c, _ = ca_client(env_file, sleeps, lambda p: pages[p.get("page_token")])
        with pytest.raises(al.UnexpectedResponse, match="repeats with a different event"):
            c.corporate_actions(["NAD", "NVG"], W0, dt.date(2028, 1, 1))
    as_split = dict(CA_REFERENCE["forward_splits"][0], id="rs-1", symbol="NVG")
    c, _ = ca_client(env_file, sleeps, ca_page({"reverse_splits": [one],
                                                "forward_splits": [as_split]}))
    with pytest.raises(al.UnexpectedResponse, match="repeats with a different event"):
        c.corporate_actions(["NVG"], W0, dt.date(2028, 1, 1))           # another type


def test_a_null_id_is_skipped_and_recorded_on_a_row_naming_none_of_ours(env_file, sleeps):
    """A null id on a row whose every party is present and none ours: skipped
    and recorded, each such row on its own (none dropped as a "duplicate").
    The same page with a null-id row naming ours refuses. (Corrected
    2026-11-01, twice: this test's rows were first no-symbol forward splits,
    then null-acquirer mergers; both now refuse as null parties.)"""
    theirs = [dict(CA_REFERENCE["stock_mergers"][0], id=None),
              dict(CA_REFERENCE["stock_mergers"][0], id=None, effective_date="2023-09-01")]
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": theirs}))
    skipped = []
    assert c.corporate_actions(["PDI"], W0, W1, universe=UNI, skipped=skipped) == []
    assert [(k["id"], k["malformed"], k["dates"]["effective_date"]) for k in skipped] == [
        (None, {"id": None}, "2023-07-20"), (None, {"id": None}, "2023-09-01")]
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": theirs,
                                                "reverse_splits": PROBE_NULL_IDS}))
    got = c.corporate_actions(["NAD", "NVG"], W0, dt.date(2028, 1, 1),
                              universe=UNI + ["NAD", "NVG"], skipped=[])
    assert sorted(e["id"] for e in got) == sorted(al.ca_row_key(r) for r in PROBE_NULL_IDS)


def test_next_page_token_is_required_and_only_null_or_empty_ends_paging(env_file, sleeps):
    """Review 2026-10-29, item 6. `distributions` reads a missing key as the
    last page, which would drop every later page in silence."""
    no_key = FakeResp(200, {"corporate_actions": {"stock_mergers": CA_REFERENCE["stock_mergers"]}})
    c, _ = ca_client(env_file, sleeps, no_key)
    with pytest.raises(al.UnexpectedResponse, match="next_page_token"):
        c.corporate_actions(["EXR"], W0, W1)
    c, _ = ca_client(env_file, sleeps, ca_page({}, token=5))
    with pytest.raises(al.UnexpectedResponse, match="not a string or null"):
        c.corporate_actions(["EXR"], W0, W1)
    c, s = ca_client(env_file, sleeps, ca_page({"stock_mergers": CA_REFERENCE["stock_mergers"]},
                                               token=""))
    assert len(c.corporate_actions(["EXR"], W0, W1)) == 1 and len(s.gets) == 1


def test_a_reverse_split_with_an_empty_new_symbol_names_nobody_new(env_file, sleeps):
    """The reference: new_symbol is "Empty when the reverse split does not change the ticker"."""
    row = dict(CA_REFERENCE["reverse_splits"][0], new_symbol="")
    c, _ = ca_client(env_file, sleeps, ca_page({"reverse_splits": [row]}))
    assert c.corporate_actions(["MNTS"], W0, W1)[0]["parties"] == [["MNTS", "subject"]]


def test_our_row_with_a_bad_or_missing_date_raises(env_file, sleeps):
    bad = dict(CA_REFERENCE["stock_mergers"][0], effective_date="20/07/2023")
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": [bad]}))
    with pytest.raises(al.UnexpectedResponse, match="effective_date"):
        c.corporate_actions(["EXR"], W0, W1)
    gone = {k: v for k, v in CA_REFERENCE["reverse_splits"][0].items() if k != "process_date"}
    c, _ = ca_client(env_file, sleeps, ca_page({"reverse_splits": [gone]}))
    with pytest.raises(al.UnexpectedResponse, match="process_date"):
        c.corporate_actions(["MNTS"], W0, W1)


def test_another_issuers_bad_date_does_not_halt_our_read(env_file, sleeps):
    """VALIDATION is split on purpose: a malformed date on an action that names
    none of our symbols is never read, so it cannot refuse our book."""
    malformed = dict(CA_REFERENCE["forward_splits"][0], ex_date=None)
    missing = {k: v for k, v in CA_REFERENCE["forward_splits"][0].items()
               if k not in ("ex_date", "process_date", "id")}
    c, _ = ca_client(env_file, sleeps, ca_page({"forward_splits": [malformed, missing],
                                                "reverse_splits": CA_REFERENCE["reverse_splits"]}))
    assert [e["type"] for e in c.corporate_actions(["MNTS"], W0, W1)] == ["reverse_split"]


@pytest.mark.parametrize("key,drop", [("stock_mergers", "acquirer_symbol"),
                                      ("stock_mergers", "acquiree_symbol"),
                                      ("spin_offs", "source_symbol"),
                                      ("name_changes", "old_symbol")])
def test_any_row_whose_parties_cannot_be_read_raises(env_file, sleeps, key, drop):
    """A row missing a required symbol field might be ours, so it raises even
    when the symbols it does carry are someone else's."""
    row = {k: v for k, v in CA_REFERENCE[key][0].items() if k != drop}
    c, _ = ca_client(env_file, sleeps, ca_page({key: [row]}))
    with pytest.raises(al.UnexpectedResponse, match=drop):
        c.corporate_actions(["PDI"], W0, W1)


def test_a_non_string_symbol_raises(env_file, sleeps):
    row = dict(CA_REFERENCE["stock_mergers"][0], acquirer_symbol=7)
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": [row]}))
    with pytest.raises(al.UnexpectedResponse, match="acquirer_symbol"):
        c.corporate_actions(["PDI"], W0, W1)


def test_an_undocumented_response_key_raises_and_a_documented_unasked_one_is_ignored(env_file, sleeps):
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_merger": CA_REFERENCE["stock_mergers"]}))
    with pytest.raises(al.UnexpectedResponse, match="not in the reference"):
        c.corporate_actions(["EXR"], W0, W1)
    rights = [{"ex_date": "2024-04-17", "expiration_date": "2024-05-14", "id": "r1",
               "new_cusip": "454089111", "new_symbol": "IFN.RTWI", "payable_date": "2024-04-19",
               "process_date": "2024-04-19", "rate": 1, "record_date": "2024-04-18",
               "source_cusip": "454089103", "source_symbol": "IFN"}]
    c, _ = ca_client(env_file, sleeps, ca_page({"rights_distributions": rights}))
    assert c.corporate_actions(["IFN"], W0, W1) == []


def test_corporate_actions_page_on_next_page_token_and_drop_repeats(env_file, sleeps):
    one = CA_REFERENCE["stock_mergers"]
    pages = {None: ca_page({"stock_mergers": one}, token="t2"),
             "t2": ca_page({"stock_mergers": one, "reverse_splits": CA_REFERENCE["reverse_splits"]})}
    c, s = client(env_file, sleeps, route({"/v1/corporate-actions": lambda p: pages[p.get("page_token")]}))
    out = c.corporate_actions(["EXR", "MNTS"], W0, W1)
    assert [e["type"] for e in out] == ["stock_merger", "reverse_split"] and len(s.gets) == 2
    stuck = {None: ca_page({}, token="t2"), "t2": ca_page({}, token="t2")}
    c, _ = client(env_file, sleeps, route({"/v1/corporate-actions": lambda p: stuck[p.get("page_token")]}))
    with pytest.raises(al.UnexpectedResponse, match="did not advance"):
        c.corporate_actions(["EXR"], W0, W1)


def test_corporate_actions_refuse_bad_arguments(env_file, sleeps):
    c, _ = ca_client(env_file, sleeps)
    with pytest.raises(ValueError, match="before start"):
        c.corporate_actions(["EXR"], W1, W0)
    with pytest.raises(ValueError, match="empty"):
        c.corporate_actions([], W0, W1)
    with pytest.raises(ValueError, match="one string"):
        c.corporate_actions("EXR", W0, W1)
    with pytest.raises(ValueError, match="upper-case"):
        c.corporate_actions(["exr"], W0, W1)


def test_corporate_actions_a_malformed_body_raises_and_never_reads_as_clear(env_file, sleeps):
    """`distributions` reads any falsy `corporate_actions` as empty; a gate must
    not read an empty list or string as "no actions". Only null is empty."""
    for bad in ([], "", 0):
        c, _ = ca_client(env_file, sleeps, FakeResp(200, {"corporate_actions": bad,
                                                         "next_page_token": None}))
        with pytest.raises(al.UnexpectedResponse, match="not an object"):
            c.corporate_actions(["EXR"], W0, W1)
    c, _ = ca_client(env_file, sleeps, ca_page({"stock_mergers": {}}))
    with pytest.raises(al.UnexpectedResponse, match="not a list"):
        c.corporate_actions(["EXR"], W0, W1)
    c, _ = ca_client(env_file, sleeps, FakeResp(200, {"corporate_actions": None,
                                                     "next_page_token": None}))
    assert c.corporate_actions(["EXR"], W0, W1) == []
    c, _ = ca_client(env_file, sleeps, FakeResp(200, {"next_page_token": None}))
    with pytest.raises(al.UnexpectedResponse, match="corporate_actions"):
        c.corporate_actions(["EXR"], W0, W1)


# ------------------------------------------------------ the whole asset list

def bulk_asset_row(sym, **kw):
    r = {"symbol": sym, "status": "active", "exchange": "NYSE", "tradable": True,
         "shortable": True, "marginable": True, "fractionable": False,
         "easy_to_borrow": True, "borrow_status": "easy_to_borrow",
         "maintenance_margin_requirement": 30, "margin_requirement_long": "30",
         "margin_requirement_short": "30"}
    r.update(kw)
    return r


def test_assets_parse_flags_and_ask_for_active_us_equity(env_file, sleeps):
    body = FakeResp(200, [bulk_asset_row("PDI"), bulk_asset_row("AWF", shortable=False, easy_to_borrow=False,
                                                      borrow_status="hard_to_borrow")])
    c, s = client(env_file, sleeps, route({"/v2/assets": body}))
    out = c.assets()
    assert [(r["symbol"], r["shortable"], r["easy_to_borrow"]) for r in out] == [
        ("PDI", True, True), ("AWF", False, False)]
    assert out[0]["maintenance_margin_requirement"] == 30.0
    assert s.gets[0][1] == {"status": "active", "asset_class": "us_equity"}


def test_assets_absent_optional_fields_are_none_never_guessed(env_file, sleeps):
    r = bulk_asset_row("PDI")
    for k in ("easy_to_borrow", "borrow_status", "maintenance_margin_requirement"):
        del r[k]
    c, _ = client(env_file, sleeps, route({"/v2/assets": FakeResp(200, [r])}))
    row, = c.assets()
    assert row["easy_to_borrow"] is None and row["borrow_status"] is None
    assert row["maintenance_margin_requirement"] is None


@pytest.mark.parametrize("bad", [{"shortable": "true"}, {"borrow_status": "maybe"}])
def test_assets_refuse_an_untyped_flag(env_file, sleeps, bad):
    c, _ = client(env_file, sleeps, route({"/v2/assets": FakeResp(200, [bulk_asset_row("PDI", **bad)])}))
    with pytest.raises(al.UnexpectedResponse):
        c.assets()


def test_assets_refuse_a_symbol_listed_twice(env_file, sleeps):
    c, _ = client(env_file, sleeps, route({"/v2/assets": FakeResp(200, [bulk_asset_row("PDI"), bulk_asset_row("PDI")])}))
    with pytest.raises(al.UnexpectedResponse, match="twice"):
        c.assets()


# ------------------------------------- end-of-day equity history (2026-10-19)
# The team lead's P&L of record. The response shape is the one read live on
# 2026-10-19 (period=1M, timeframe=1D): parallel lists, each session's point
# stamped 00:00 UTC of the day after it. Every equity here is synthetic.

from ops.schedule.nyse_calendar import is_trading_day  # noqa: E402


def utc0(y, m, d):
    """00:00 UTC on a date, as epoch seconds: how Alpaca stamps the session before it."""
    return int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp())


def history(stamps, equities, **over):
    body = {"timestamp": list(stamps), "equity": list(equities),
            "profit_loss": [0.0] * len(stamps), "profit_loss_pct": [0.0] * len(stamps),
            "base_value": 100000.0, "base_value_asof": "2026-09-28", "timeframe": "1D"}
    body.update(over)
    return body


def nyse_calendar_route(early=()):
    """/v2/calendar from ops/schedule/nyse_calendar, honouring start/end like Alpaca;
    dates in `early` close at 13:00."""
    def h(params):
        d, end = dt.date.fromisoformat(params["start"]), dt.date.fromisoformat(params["end"])
        rows = []
        while d <= end:
            if is_trading_day(d):
                rows.append({"date": d.isoformat(), "open": "09:30",
                             "close": "13:00" if d in early else "16:00"})
            d += dt.timedelta(days=1)
        return FakeResp(200, rows)
    return h


def eod_client(env_file, sleeps, body, early=()):
    return client(env_file, sleeps, route({
        "/v2/account/portfolio/history": FakeResp(200, body) if isinstance(body, dict) else body,
        "/v2/calendar": nyse_calendar_route(early)}))


def test_eod_history_is_one_get_with_period_and_1d_only(env_file, sleeps):
    body = history([utc0(2026, 9, 30), utc0(2026, 10, 1)], [100000.0, 100012.5])
    c, s = eod_client(env_file, sleeps, body)
    out = c.eod_equity_history(dt.date(2026, 9, 28), dt.date(2026, 9, 30))
    url, params = s.gets[0]
    assert url == al.PAPER_BASE + "/v2/account/portfolio/history"
    assert params == {"period": "2M", "timeframe": "1D"}      # the shape read live on 2026-10-19
    assert [(d, eq) for d, eq, _ in out] == [(dt.date(2026, 9, 29), 100000.0),
                                            (dt.date(2026, 9, 30), 100012.5)]
    assert all(isinstance(p, al.EODPoint) for p in out)


def ny20(d):
    """20:00 New York on session date `d`, as epoch seconds: how Alpaca stamps a
    1D point (00:00Z on EDT, 01:00Z on EST) [V: read 2026-10-19; a peer's
    read-only GET 2026-11-02 23:49Z showed 2025-12-03T01:00:00Z in winter]."""
    return int(dt.datetime.combine(d, dt.time(20), tzinfo=al.NY).timestamp())


def ny_at(d, hour):
    """`hour`:00 New York on session date `d`, as epoch seconds."""
    return int(dt.datetime.combine(d, dt.time(hour), tzinfo=al.NY).timestamp())


HALF_2025 = (dt.date(2025, 11, 28), dt.date(2025, 12, 24))      # 13:00 closes, EST
HALF_2025_EDT = dt.date(2025, 7, 3)                             # 13:00 close, EDT


def test_eod_a_half_day_is_stamped_1700_new_york_and_is_accepted(env_file, sleeps):
    """The points read on 2026-11-14 (cef paper, period=3A): a 13:00 close is
    stamped 17:00 New York, its close + 4 hours, on EST (2025-11-28T22:00Z,
    2025-12-24T22:00Z) and on EDT (2025-07-03T21:00Z); full days either side
    stay at 20:00. FAILS on 8eb9ce1, which raised "not 20:00:00 local" for the
    first half day in any response."""
    full = [dt.date(2025, 7, 2), dt.date(2025, 11, 26), dt.date(2025, 12, 1), dt.date(2025, 12, 26)]
    half = [HALF_2025_EDT, *HALF_2025]
    sessions = sorted(full + half)
    stamps = [ny_at(d, 17 if d in half else 20) for d in sessions]
    assert at_utc(2025, 11, 28, 22) in stamps and at_utc(2025, 7, 3, 21) in stamps
    c, _ = eod_client(env_file, sleeps, history(stamps, [1.0 + i for i in range(len(sessions))]),
                      early=set(half))
    out = c.eod_equity_history(dt.date(2025, 7, 1), dt.date(2025, 12, 31))
    assert [p.date for p in out] == sessions
    assert {p.date: p.stamp.astimezone(al.NY).hour for p in out if p.date in half} == \
        {d: 17 for d in half}


def test_eod_a_half_day_point_outside_the_window_no_longer_stops_the_read(env_file, sleeps):
    """Every point is checked before the window is applied, so one half day
    anywhere in the months asked for used to refuse the whole read: the
    collector's window starts at funding and only grows. FAILS on 8eb9ce1."""
    sessions = [dt.date(2025, 11, 28), dt.date(2025, 12, 1), dt.date(2025, 12, 2)]
    stamps = [ny_at(sessions[0], 17), ny20(sessions[1]), ny20(sessions[2])]
    c, _ = eod_client(env_file, sleeps, history(stamps, [1.0, 2.0, 3.0]), early={sessions[0]})
    out = c.eod_equity_history(dt.date(2025, 12, 1), dt.date(2025, 12, 2))
    assert [(p.date, p.equity) for p in out] == [(sessions[1], 2.0), (sessions[2], 3.0)]


def test_eod_a_1700_stamp_on_a_full_day_raises(env_file, sleeps):
    """17:00 is right only after a 13:00 close. On a full day it could be an
    intraday reading."""
    d = dt.date(2025, 12, 1)
    c, _ = eod_client(env_file, sleeps, history([ny_at(d, 17)], [1.0]), early=set(HALF_2025))
    with pytest.raises(al.UnexpectedResponse, match="not 20:00:00 local.*16:00 close"):
        c.eod_equity_history(d, d)


def test_eod_a_2000_stamp_on_a_half_day_raises(env_file, sleeps):
    """Alpaca stamps a half day at 17:00. A 20:00 stamp there is a convention
    not seen, so it is refused, naming the time expected."""
    d = dt.date(2025, 11, 28)
    c, _ = eod_client(env_file, sleeps, history([ny20(d)], [1.0]), early=set(HALF_2025))
    with pytest.raises(al.UnexpectedResponse, match="not 17:00:00 local.*13:00 close"):
        c.eod_equity_history(d, d)


def test_eod_a_calendar_date_listed_twice_raises(env_file, sleeps):
    """Review 2026-11-14: with one date served as 16:00 then 13:00, the later
    row used to decide, and a 17:00 stamp on a full day was accepted."""
    d = dt.date(2025, 12, 1)
    cal = lambda params: FakeResp(200, [{"date": d.isoformat(), "open": "09:30", "close": x}
                                        for x in ("16:00", "13:00")])
    c, _ = client(env_file, sleeps, route({
        "/v2/account/portfolio/history": FakeResp(200, history([ny_at(d, 17)], [1.0])),
        "/v2/calendar": cal}))
    with pytest.raises(al.UnexpectedResponse, match="2025-12-01 twice"):
        c.eod_equity_history(d, d)


@pytest.mark.parametrize("close", ["20:00", "23:30", "13:75"])
def test_eod_a_calendar_close_with_no_time_four_hours_later_raises(env_file, sleeps, close):
    """A close whose + 4 hours is not a time on the same date has never been
    served. It raises UnexpectedResponse, not a bare ValueError from dt.time."""
    d = dt.date(2025, 12, 1)
    cal = lambda params: FakeResp(200, [{"date": d.isoformat(), "open": "09:30", "close": close}])
    c, _ = client(env_file, sleeps, route({
        "/v2/account/portfolio/history": FakeResp(200, history([ny20(d)], [1.0])),
        "/v2/calendar": cal}))
    with pytest.raises(al.UnexpectedResponse, match=f"{close} close"):
        c.eod_equity_history(d, d)


def test_eod_stamps_map_to_the_new_york_session_either_side_of_the_dst_change(env_file, sleeps):
    """20:00 New York on each session: 00:00Z on EDT, 01:00Z on EST (after
    2026-11-01). The session date is the New York date, and an early close is
    stamped 17:00 (corrected 2026-11-14: this test had the half day at 20:00,
    which Alpaca does not serve). (Corrected 2026-11-02: this test had EST sessions at 00:00Z,
    19:00 EST, which Alpaca does not serve.) FAILS on 3478159, which refused
    every 01:00Z point."""
    sessions = [dt.date(2026, 10, 29), dt.date(2026, 10, 30),     # EDT
                dt.date(2026, 11, 2), dt.date(2026, 11, 3),        # EST, after 2026-11-01
                dt.date(2026, 11, 25), dt.date(2026, 11, 27)]      # 11-27 closes at 13:00
    stamps = [ny20(d) for d in sessions[:-1]] + [ny_at(sessions[-1], 17)]   # half day: 17:00
    eq = [100000.0 + i for i in range(len(sessions))]
    c, _ = eod_client(env_file, sleeps, history(stamps, eq), early={dt.date(2026, 11, 27)})
    out = c.eod_equity_history(dt.date(2026, 10, 29), dt.date(2026, 11, 27))
    assert [p.date for p in out] == sessions
    assert [p.equity for p in out] == eq
    assert out[1].stamp == dt.datetime(2026, 10, 31, 0, tzinfo=dt.timezone.utc)   # EDT: 00:00Z
    assert out[2].stamp == dt.datetime(2026, 11, 3, 1, tzinfo=dt.timezone.utc)    # EST: 01:00Z


def test_eod_a_winter_0100z_point_is_accepted_under_its_session_date(env_file, sleeps):
    """The point Alpaca will serve for Monday 2026-11-02: 2026-11-03T01:00Z,
    20:00 EST. FAILS on 3478159 ("not 00:00 UTC")."""
    c, _ = eod_client(env_file, sleeps, history([at_utc(2026, 11, 3, 1)], [100000.0]))
    (p,) = c.eod_equity_history(dt.date(2026, 11, 2), dt.date(2026, 11, 2))
    assert p.date == dt.date(2026, 11, 2) and p.equity == 100000.0


def test_eod_a_summer_0000z_point_is_still_accepted(env_file, sleeps):
    c, _ = eod_client(env_file, sleeps, history([utc0(2026, 10, 17)], [100000.0]))
    (p,) = c.eod_equity_history(dt.date(2026, 10, 16), dt.date(2026, 10, 16))
    assert p.date == dt.date(2026, 10, 16)


def test_eod_a_window_across_the_dst_change_reads_both_sides(env_file, sleeps):
    """Friday 10-30 at 00:00Z (EDT) and Monday 11-02 at 01:00Z (EST) in one
    response, and a point after `end` (11-03 at 01:00Z, validated then left
    out). FAILS on 3478159."""
    stamps = [utc0(2026, 10, 31), at_utc(2026, 11, 3, 1), at_utc(2026, 11, 4, 1)]
    c, _ = eod_client(env_file, sleeps, history(stamps, [1.0, 2.0, 3.0]))
    out = c.eod_equity_history(dt.date(2026, 10, 30), dt.date(2026, 11, 2))
    assert [(p.date, p.equity) for p in out] == [(dt.date(2026, 10, 30), 1.0),
                                                (dt.date(2026, 11, 2), 2.0)]


def test_eod_a_stamp_on_a_non_trading_day_raises_naming_it(env_file, sleeps):
    """A left-labelled Monday (2026-10-19T00:00Z, the start of its own UTC day)
    is 20:00 on Sunday in New York: no session to give it."""
    c, _ = eod_client(env_file, sleeps, history([utc0(2026, 10, 17), utc0(2026, 10, 19)],
                                                [1.0, 2.0]))
    with pytest.raises(al.UnexpectedResponse, match="2026-10-18 is not a trading day"):
        c.eod_equity_history(dt.date(2026, 10, 1), dt.date(2026, 10, 19))


def at_utc(y, m, d, h, mi=0, s=0):
    return int(dt.datetime(y, m, d, h, mi, s, tzinfo=dt.timezone.utc).timestamp())


@pytest.mark.parametrize("stamp,why", [
    (at_utc(2026, 11, 3, 5), "New York midnight after Monday 11-02 (EST): would file it on Tuesday"),
    (at_utc(2026, 10, 20, 4), "New York midnight after Monday 10-19 (EDT): would file it on Tuesday"),
    (at_utc(2026, 10, 19, 21, 29, 41), "an intraday reading at 17:29 ET, not a finished day"),
    (at_utc(2026, 10, 19, 20), "a stamp at the 16:00 ET close"),
    (at_utc(2026, 11, 3, 2), "02:00Z in winter: 21:00 EST"),
    (at_utc(2026, 11, 3, 0), "00:00Z in winter: 19:00 EST, the summer convention one zone off"),
    (at_utc(2026, 11, 3, 1, 0, 1), "a second past 20:00 EST"),
])
def test_eod_a_stamp_that_is_not_2000_new_york_raises_rather_than_being_placed(
        env_file, sleeps, stamp, why):
    """Every 1D stamp seen is 20:00 New York (00:00Z on EDT, 01:00Z on EST).
    Any other time is refused, loudly: some would silently move a session to
    the next date, the rest could be a day that has not finished."""
    c, _ = eod_client(env_file, sleeps, history([utc0(2026, 10, 16), stamp], [100000.0, 100001.0]))
    with pytest.raises(al.UnexpectedResponse, match="not 20:00:00 local"):
        c.eod_equity_history(dt.date(2026, 10, 1), dt.date(2026, 11, 3))


def test_eod_a_2000_stamp_on_a_non_trading_day_still_raises(env_file, sleeps):
    """Saturday 2026-11-07 at 20:00 EST (2026-11-08T01:00Z): the right hour on
    a day with no session."""
    c, _ = eod_client(env_file, sleeps, history([at_utc(2026, 11, 3, 1), at_utc(2026, 11, 8, 1)],
                                                [1.0, 2.0]))
    with pytest.raises(al.UnexpectedResponse, match="2026-11-07 is not a trading day"):
        c.eod_equity_history(dt.date(2026, 11, 2), dt.date(2026, 11, 9))


def test_eod_pre_funding_zeros_are_dropped_and_a_later_zero_raises(env_file, sleeps):
    stamps = [utc0(2026, 9, 26), utc0(2026, 9, 29), utc0(2026, 9, 30), utc0(2026, 10, 1)]
    c, _ = eod_client(env_file, sleeps, history(stamps, [0, 0, 100000.0, 100003.21]))
    out = c.eod_equity_history(dt.date(2026, 9, 1), dt.date(2026, 9, 30))
    assert [(p.date.isoformat(), p.equity) for p in out] == [("2026-09-29", 100000.0),
                                                            ("2026-09-30", 100003.21)]
    c, _ = eod_client(env_file, sleeps, history(stamps, [0, 100000.0, 0, 100003.21]))
    with pytest.raises(al.UnexpectedResponse, match=r"equity 0 on \['2026-09-29'\], after the account"):
        c.eod_equity_history(dt.date(2026, 9, 1), dt.date(2026, 9, 30))


def test_eod_points_outside_the_range_are_left_out(env_file, sleeps):
    stamps = [utc0(2026, 9, 30), utc0(2026, 10, 1), utc0(2026, 10, 2)]
    c, _ = eod_client(env_file, sleeps, history(stamps, [1.0, 2.0, 3.0]))
    assert [p.date for p in c.eod_equity_history(dt.date(2026, 9, 30), dt.date(2026, 9, 30))] == \
        [dt.date(2026, 9, 30)]


@pytest.mark.parametrize("over,match", [
    ({"equity": [100000.0]}, "unequal length"),
    ({"equity": [100000.0, None]}, "not a number"),
    ({"equity": [100000.0, True]}, "not a number"),
    ({"equity": [100000.0, float("inf")]}, "not finite"),
    ({"equity": [100000.0, "junk"]}, "not a number"),
    ({"timestamp": [utc0(2026, 9, 30), float(utc0(2026, 10, 1))]}, "integer epoch"),
    ({"timestamp": [utc0(2026, 10, 1), utc0(2026, 9, 30)]}, "strictly increasing"),
    ({"timeframe": "1H"}, "timeframe"),
    ({"profit_loss": None}, "not a list"),
])
def test_eod_history_parses_strictly(env_file, sleeps, over, match):
    body = history([utc0(2026, 9, 30), utc0(2026, 10, 1)], [100000.0, 100001.0], **over)
    c, _ = eod_client(env_file, sleeps, body)
    with pytest.raises(al.UnexpectedResponse, match=match):
        c.eod_equity_history(dt.date(2026, 9, 28), dt.date(2026, 9, 30))


@pytest.mark.parametrize("key", ["timestamp", "equity", "profit_loss", "profit_loss_pct", "timeframe"])
def test_eod_history_missing_key_raises_naming_it(env_file, sleeps, key):
    body = history([utc0(2026, 9, 30)], [100000.0])
    del body[key]
    c, _ = eod_client(env_file, sleeps, body)
    with pytest.raises(al.UnexpectedResponse, match=key):
        c.eod_equity_history(dt.date(2026, 9, 28), dt.date(2026, 9, 30))


def test_eod_history_is_a_get_and_retries_like_one(env_file, sleeps):
    seq = [FakeResp(503, text="down"),
           FakeResp(200, history([utc0(2026, 9, 30)], [100000.0]))]
    cal = nyse_calendar_route()

    def h(url, params):
        return cal(params) if url.endswith("/v2/calendar") else seq.pop(0)
    c, s = client(env_file, sleeps, h)
    assert [p.equity for p in c.eod_equity_history(D, D)] == [100000.0]
    assert sleeps == [al.GET_BACKOFF_S[0]] and s.posts == []


@pytest.mark.parametrize("stamp", [86400 * 10**9, 86400 * 10**13, -86400 * 10**9])
def test_eod_a_stamp_outside_the_clock_raises_unexpected_response(env_file, sleeps, stamp):
    """Review 2026-10-19: an integer stamp that is a whole number of days but
    outside datetime's range used to raise a bare ValueError/OverflowError/OSError,
    which verify reported as a 'verify error' FAIL. It is a response Alpaca should
    not send, so it is refused like every other bad shape."""
    c, _ = eod_client(env_file, sleeps, history([utc0(2026, 10, 16), stamp], [100000.0, 100001.0]))
    with pytest.raises(al.UnexpectedResponse, match=str(stamp)):
        c.eod_equity_history(dt.date(2026, 10, 1), dt.date(2026, 11, 3))


# ------------------------------------------------ pacing the trading host (2026-11-23)
# The events book's first armed send read 219 assets and POSTed 219 orders with nothing pacing
# them, and Alpaca answered HTTP 429 to 173 of the orders. Every request to the trading host now
# takes a token from a bucket (TRADING_BURST, refilled at TRADING_MAX_PER_MIN a minute).

CLOCK_OK = {"timestamp": "2026-09-29T15:45:00-04:00", "is_open": True,
            "next_open": "2026-09-30T09:30:00-04:00", "next_close": "2026-09-29T16:00:00-04:00"}


class VirtualTime:
    """A clock that only moves when the client sleeps, so pacing is measured, not timed."""

    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s

    def monotonic(self):
        return self.t


def paced_client(env_file, vt, get=None, post=None):
    s = FakeSession(get or route({"/v2/clock": FakeResp(200, CLOCK_OK)}), post)
    return al.AlpacaClient("cef", env_file, session=s, sleep=vt.sleep,
                           monotonic=vt.monotonic), s


def test_a_burst_goes_unpaced_and_the_rest_wait_their_turn(env_file):
    """Failed before 2026-11-23 (no pacing, and no `monotonic` to inject)."""
    vt = VirtualTime()
    c, s = paced_client(env_file, vt)
    for _ in range(al.TRADING_BURST):
        c.clock()
    assert vt.sleeps == []                      # the core's few dozen requests never wait
    for _ in range(20):
        c.clock()
    step = 60.0 / al.TRADING_MAX_PER_MIN
    assert vt.sleeps == pytest.approx([step] * 20)


def test_no_minute_holds_more_than_alpacas_limit(env_file):
    """219 asset reads, then 219 orders each with its clock read: the 2026-11-23 shape."""
    vt = VirtualTime()
    stamps = []

    def get(url, params):
        stamps.append(vt.t)
        if url.endswith("/v2/clock"):
            return FakeResp(200, CLOCK_OK)
        sym = url.rsplit("/", 1)[-1]
        return FakeResp(200, {"symbol": sym, "tradable": True, "shortable": True,
                              "easy_to_borrow": True, "marginable": True, "status": "active",
                              "class": "us_equity", "fractionable": True})

    def post(url, js):
        stamps.append(vt.t)
        return FakeResp(200, {**js, "id": "o-" + js["client_order_id"], "status": "accepted",
                              "filled_qty": "0", "submitted_at": "2026-09-29T19:45:00Z"})
    c, s = paced_client(env_file, vt, get=get, post=post)
    for i in range(219):
        c._get(c._base, f"/v2/assets/S{i}")
    for i in range(219):
        c.clock()
        try:
            c.submit_order(f"S{i}", 1, "buy", f"cid-{i}", time_in_force="day")
        except al.AlpacaError:
            pass                                  # the echo check is not what this test is about
    assert len(stamps) == 219 * 3
    worst = max(sum(1 for t in stamps if a <= t < a + 60.0) for a in stamps)
    assert worst <= al.TRADING_BURST + al.TRADING_MAX_PER_MIN < 200, worst


def test_the_data_host_is_not_paced(env_file):
    vt = VirtualTime()
    c, s = paced_client(env_file, vt, get=lambda url, params: FakeResp(200, {}))
    for _ in range(al.TRADING_BURST + 30):
        c._get(c._data, "/v2/stocks/bars")
    assert vt.sleeps == []


def test_an_order_is_paced_like_a_read(env_file):
    vt = VirtualTime()
    c, s = paced_client(env_file, vt, post=lambda url, js: FakeResp(422, {"message": "x"}))
    for _ in range(al.TRADING_BURST):
        c.clock()
    with pytest.raises(al.OrderRejected):
        c.submit_order("PDI", 1, "buy", "cid-1", time_in_force="day")
    assert vt.sleeps == pytest.approx([60.0 / al.TRADING_MAX_PER_MIN])


def test_the_send_budget_covers_the_pacing():
    """Gate 4 allows SEND_ALLOWANCE_PER_ORDER_S per order; each order is a clock read and a
    POST, so the pacing alone must fit inside that allowance once the burst is spent."""
    from quantt.session import gate as gt
    assert gt.SEND_ALLOWANCE_PER_ORDER_S >= 2 * 60.0 / al.TRADING_MAX_PER_MIN
