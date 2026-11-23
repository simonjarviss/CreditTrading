"""The sleeves runner's order phase against a fake Alpaca: plan, send, verify, approve, prices.

No test here builds an `AlpacaClient` or opens a socket (the root conftest blocks one anyway).
The fake records every call it receives, fills `day` market orders at once at a canned price,
and moves its own positions, so a test can run whole sessions. Each test names the failure it
guards."""
import csv
import dataclasses
import datetime as dt
import io
import json
from types import SimpleNamespace

import pytest

from quantt.broker import alpaca
from quantt.session import gate as gt
from quantt.session import run as core
from quantt.sleeves import config, ledger, prices
from quantt.sleeves import run as sr

NY = sr.gt.ET
D, F = dt.date(2026, 11, 16), dt.date(2026, 11, 17)
SESSIONS = [dt.date(2026, 11, 13), D, F, dt.date(2026, 11, 18), dt.date(2026, 11, 19), dt.date(2026, 11, 20)]
BOOK = {"book": "events",
        "sleeves": [{"slug": "a", "family": "f", "backtest_vol_annual": 0.1, "full_capital_usd": 40000, "capital_usd": 10000, "enabled": True},
                    {"slug": "b", "family": "f", "backtest_vol_annual": 0.1, "full_capital_usd": 40000, "capital_usd": 10000, "enabled": True}],
        "min_order_usd": 100, "max_gross_x_equity": 1.0, "max_name_usd": 20000,
        "max_stale_sessions": 2, "max_orders": 100,
        "execution": {"mode": "late_market", "window_minutes_before_close": [8, 2]}}
PX = {"AAA": 20.0, "BBB": 50.0, "IWM": 250.0}
EXPECTED_CALLS = {"clock", "calendar", "account", "positions", "asset", "orders",
                  "order_by_client_id", "submit_order", "activities_fills", "_get"}


def at(day, hh, mm):
    return dt.datetime.combine(day, dt.time(hh, mm), tzinfo=NY)


def asset(sym, **over):
    return {"symbol": sym, "status": "active", "exchange": "NYSE", "tradable": True, "shortable": True,
            "marginable": True, "fractionable": True, "easy_to_borrow": True,
            "borrow_status": "easy_to_borrow", **over}


class FakeClient:
    """Canned reads; a `day` market order fills at once at `fill_px` (a share of it: `fill_frac`)."""
    trading_endpoint = alpaca.PAPER_BASE
    _data = "DATA-HOST"

    def __init__(self):
        self.now, self.is_open = at(F, 14, 0), True
        self.acct = {"id": "x", "equity": 100000.0, "last_equity": 100000.0, "cash": 100000.0,
                     "buying_power": 200000.0, "regt_buying_power": 200000.0, "initial_margin": 0.0,
                     "maintenance_margin": 0.0, "long_market_value": 0.0, "short_market_value": 0.0,
                     "shorting_enabled": True, "trading_blocked": False, "account_blocked": False,
                     "trade_suspended_by_user": False}
        self.pos, self.assets = {}, {s: asset(s) for s in PX}
        self.px, self.bar_over = dict(PX), {}          # bars: the same close every day unless overridden
        self.fill_px, self.fill_frac = dict(PX), {}
        self.order_list, self.fills, self.calls, self.submitted, self.get_params = [], [], [], [], []
        self.on_submit = lambda: None
        self.orders_error = None

    def clock(self):
        self.calls.append("clock")
        nxt = min(d for d in SESSIONS + [dt.date(2026, 11, 23)] if d > self.now.date() or
                  (d == self.now.date() and self.now.time() < dt.time(9, 30)))
        return {"timestamp": self.now, "is_open": self.is_open, "next_open": at(nxt, 9, 30),
                "next_close": at(nxt, 16, 0)}

    def calendar(self, start, end):
        self.calls.append("calendar")
        return [{"date": d, "open": "09:30", "close": "16:00"} for d in SESSIONS if start <= d <= end]

    def account(self):
        self.calls.append("account")
        return dict(self.acct)

    def positions(self):
        self.calls.append("positions")
        return SimpleNamespace(qty={s: q for s, q in self.pos.items() if q != 0}, raw=[])

    def asset(self, sym):
        self.calls.append("asset")
        if sym not in self.assets:
            raise alpaca.AssetNotFound(f"GET /v2/assets/{sym} -> HTTP 404", status=404)
        return dict(self.assets[sym])

    def orders(self, *, status, after=None, until=None):
        self.calls.append("orders")
        if self.orders_error:
            raise self.orders_error
        rows = [o for o in self.order_list
                if (after is None or o["_at"] > after) and (until is None or o["_at"] < until)]
        return [o for o in rows if status == "all" or (status == "open") == (o["status"] in ("new", "accepted"))]

    def order_by_client_id(self, cid):
        self.calls.append("order_by_client_id")
        return next((o for o in self.order_list if o["client_order_id"] == cid), None)

    def submit_order(self, symbol, qty, side, cid, *, time_in_force):
        self.calls.append("submit_order")
        self.on_submit()
        self.submitted.append({"symbol": symbol, "qty": qty, "side": side, "cid": cid, "tif": time_in_force})
        filled = int(qty * self.fill_frac.get(symbol, 1.0))
        o = {"id": f"oid-{len(self.order_list)}", "client_order_id": cid, "symbol": symbol, "side": side,
             "qty": str(qty), "type": "market", "time_in_force": time_in_force, "filled_qty": str(filled),
             "status": "filled" if filled == qty else "canceled", "submitted_at": self.now.isoformat(),
             "filled_avg_price": str(self.fill_px[symbol]), "_at": self.now}
        self.order_list.append(o)
        if filled:
            signed = filled if side == "buy" else -filled
            opens_short = side == "sell" and self.pos.get(symbol, 0) + signed < 0
            self.pos[symbol] = self.pos.get(symbol, 0) + signed
            self.fills.append({"id": f"f-{len(self.fills)}", "activity_type": "FILL", "order_id": o["id"],
                               "symbol": symbol, "side": "sell_short" if opens_short else side,
                               "qty": str(filled), "price": str(self.fill_px[symbol]), "type": "fill",
                               "_date": self.now.date()})
        return o

    def activities_fills(self, date):
        self.calls.append("activities_fills")
        return [f for f in self.fills if f["_date"] == date]

    def _get(self, base, path, params=None):
        self.calls.append("_get")
        assert base == self._data and path == "/v2/stocks/bars", (base, path)
        self.get_params.append(dict(params))
        day = dt.date.fromisoformat(params["start"])
        table = self.bar_over.get(day, self.px)
        return {"bars": {s: [{"t": f"{day}T05:00:00Z", "c": table[s]}]
                         for s in params["symbols"].split(",") if s in table}, "next_page_token": None}


def decision(ddir, slug, weights, asof=D, written=None, **over):
    d = ddir / slug / "decisions"
    d.mkdir(parents=True, exist_ok=True)
    written = written or dt.datetime.combine(asof, dt.time(23, 50), tzinfo=dt.timezone.utc).isoformat()
    (d / f"{asof}.json").write_text(json.dumps({"slug": slug, "asof": asof.isoformat(), "written_at": written,
                                               "fill": "next_close", "notional_usd": 1e6,
                                               "weights": weights, **over}))


@pytest.fixture
def w(tmp_path):
    """A world: fake client, a state dir named after the book, a decisions dir, DRY_RUN=0."""
    state, ddir = tmp_path / "events", tmp_path / "shadow_state"
    state.mkdir(); ddir.mkdir()
    book = tmp_path / "events_sleeves.json"
    book.write_text(json.dumps(BOOK))
    c = FakeClient()
    out = io.StringIO()
    deps = sr.Deps(client=c, env={"DRY_RUN": "0", "QUANTT_SLEEVES_DECISIONS_DIR": str(ddir)}, state=state,
                   utcnow=lambda: c.now, out=out, book_path=book, sleep=lambda s: None, halts=lambda b: [])
    decision(ddir, "a", {"AAA": 0.1, "IWM": -0.1})          # AAA +50, IWM -4
    decision(ddir, "b", {"BBB": 0.1, "IWM": -0.1})          # BBB +20, IWM -4
    return SimpleNamespace(c=c, deps=deps, state=state, ddir=ddir, book=book, out=out, day=state / str(F))


def set_book(w, **over):
    w.book.write_text(json.dumps({**BOOK, **over}))


def do_plan(w, day=F):
    w.c.now, w.c.is_open = at(day, 14, 0), True
    return sr.plan(w.deps)


def do_send(w, day=F, hh=15, mm=53):
    w.c.now, w.c.is_open = at(day, hh, mm), True
    return sr.send(w.deps)


def do_verify(w, day=F):
    w.c.now, w.c.is_open = at(day, 16, 30), False
    return sr.verify(w.deps)


def arm(w):
    (w.state / "AUTO_ARMED").write_text("armed by the test\n")


def read(p):
    return json.loads(p.read_text())


def led(w):
    return read(w.state / "ledger.json")


def session(w, day):
    """One armed session, start to finish; returns the three exit codes."""
    return do_plan(w, day), do_send(w, day), do_verify(w, day)


# ---------------------------------------------------------------------------- PLAN

def test_plan_writes_one_net_order_a_symbol_and_sends_nothing(w):
    assert do_plan(w) == core.EXIT_PLANNED
    p = read(w.day / "plan.json")
    assert p["asof"] == str(D) and p["session_date"] == str(F) and p["status"] == "decided"
    assert p["net_targets"] == {"AAA": 50, "BBB": 20, "IWM": -8}
    assert sorted((o["symbol"], o["side"], o["qty"], o["time_in_force"]) for o in p["orders"]) == [
        ("AAA", "buy", 50, "day"), ("BBB", "buy", 20, "day"), ("IWM", "sell", 8, "day")]
    assert all(o["client_order_id"].startswith("events-20261117-") for o in p["orders"])
    assert all(len(s["decision"]["sha256"]) == 64 for s in p["sleeves"])
    assert w.c.submitted == [] and "submit_order" not in w.c.calls
    assert not (w.day / "STARTED").exists()
    assert "plan_sha " + p["plan_sha"] in w.out.getvalue()


def test_the_sessions_come_from_the_exchange_calendar_never_the_decision_files(w):
    """A decision file dated for another session is not that session's: with only a file for
    2026-11-13, PLAN on F still asks for D's and holds."""
    for slug in ("a", "b"):
        (w.ddir / slug / "decisions" / f"{D}.json").unlink()
        decision(w.ddir, slug, {"AAA": 0.1}, asof=dt.date(2026, 11, 13))
    assert do_plan(w) == core.EXIT_PLANNED
    p = read(w.day / "plan.json")
    assert p["asof"] == str(D) and p["orders"] == []
    assert all(s["action"] == "hold" and "absent" in s["decision"]["missing"] for s in p["sleeves"])
    assert w.c.get_params == []                         # nothing held or named: no price was read


def test_preview_writes_nothing(w):
    w.c.now = at(F, 14, 0)
    assert sr.plan(w.deps, preview=True) == core.EXIT_PREVIEW
    assert not w.day.exists()


def test_two_sleeves_with_opposite_weights_make_one_order_or_none(w):
    decision(w.ddir, "b", {"IWM": 0.1})                 # +4 against a's -4: nets to zero
    do_plan(w)
    p = read(w.day / "plan.json")
    assert "IWM" not in p["net_targets"] and [o["symbol"] for o in p["orders"]] == ["AAA"]
    decision(w.ddir, "b", {"IWM": 0.05})                # +2 against -4: one sell of 2
    do_plan(w)
    iwm = [o for o in read(w.day / "plan.json")["orders"] if o["symbol"] == "IWM"]
    assert [(o["side"], o["qty"]) for o in iwm] == [("sell", 2)]


def test_the_decisions_dir_is_required(w):
    w.deps.env.pop("QUANTT_SLEEVES_DECISIONS_DIR")
    assert do_plan(w) == core.EXIT_REFUSED and "QUANTT_SLEEVES_DECISIONS_DIR is not set" in w.out.getvalue()
    w.deps.env["QUANTT_SLEEVES_DECISIONS_DIR"] = str(w.ddir / "nope")
    assert do_plan(w) == core.EXIT_REFUSED and "not an existing directory" in w.out.getvalue()
    assert not (w.day / "plan.json").exists()


def test_the_state_dir_must_be_named_after_the_book(w, tmp_path):
    other = tmp_path / "cef"
    other.mkdir()
    w.deps.state = other
    assert do_plan(w) == core.EXIT_REFUSED and "needs its own state directory" in w.out.getvalue()
    assert do_send(w) == core.EXIT_REFUSED and sr.verify(w.deps) == sr.VERIFY_FAIL
    assert list(other.iterdir()) == []


def test_a_core_book_name_is_refused(w):
    set_book(w, book="cef")
    assert do_plan(w) == core.EXIT_REFUSED and "another book" in w.out.getvalue()


def test_positions_with_no_ledger_and_a_ledger_that_disagrees_refuse_the_plan(w):
    w.c.pos = {"AAA": 5}
    assert do_plan(w) == core.EXIT_REFUSED and "absent ledger is an empty one only for an empty account" in w.out.getvalue()
    (w.state / "ledger.json").write_text(json.dumps(
        {"version": 1, "session": None, "sleeves": {"a": {"shares": {"AAA": 4}, "cash": 0.0, "stale_sessions": 0}}}))
    assert do_plan(w) == core.EXIT_REFUSED and "AAA: +4, +5" in w.out.getvalue()
    assert not (w.day / "plan.json").exists()


@pytest.mark.parametrize("change", [
    {"shortable": False}, {"easy_to_borrow": False}, {"easy_to_borrow": None},
    {"borrow_status": "hard_to_borrow"}, {"tradable": False}, {"status": "inactive"}, "unlisted", "no_field"])
def test_a_short_that_cannot_be_borrowed_is_not_opened_and_the_other_side_is_scaled(w, change):
    """`a` is long AAA against short IWM. With IWM not shortable AND easy to borrow, the short
    is not opened and a's long is scaled to nothing; an absent flag is not an easy one."""
    if change == "unlisted":
        del w.c.assets["IWM"]
    elif change == "no_field":
        del w.c.assets["IWM"]["easy_to_borrow"]
    else:
        w.c.assets["IWM"].update(change)
    decision(w.ddir, "b", {"BBB": 0.1})                 # long only: unaffected
    assert do_plan(w) == core.EXIT_PLANNED
    p = read(w.day / "plan.json")
    a = p["sleeves"][0]
    assert a["targets"] == {} and a["dropped"] == ["IWM"] and a["scale"]["long"] == 0.0
    assert [o["symbol"] for o in p["orders"]] == ["BBB"]


def test_a_missing_close_holds_that_sleeve_and_names_the_symbol(w):
    w.c.bar_over[D] = {"BBB": 50.0, "IWM": 250.0}        # no AAA bar on D
    do_plan(w)
    p = read(w.day / "plan.json")
    assert p["sleeves"][0]["action"] == "hold" and "AAA" in p["sleeves"][0]["why"]
    assert "AAA" not in p["closes"] and sorted(p["net_targets"]) == ["BBB", "IWM"]
    assert p["net_targets"]["IWM"] == -4                 # b's alone: a opened nothing


def test_more_orders_than_max_orders_refuses_the_plan(w):
    set_book(w, max_orders=2)
    assert do_plan(w) == core.EXIT_REFUSED and "above max_orders 2" in w.out.getvalue()
    assert not (w.day / "plan.json").exists()


def test_plan_may_be_rerun_before_started_and_never_after(w):
    arm(w)
    do_plan(w)
    first = read(w.day / "plan.json")["plan_sha"]
    decision(w.ddir, "b", {"BBB": 0.2, "IWM": -0.1})
    assert do_plan(w) == core.EXIT_PLANNED and read(w.day / "plan.json")["plan_sha"] != first
    sent_sha = read(w.day / "plan.json")["plan_sha"]
    assert do_send(w) == core.EXIT_SENT
    decision(w.ddir, "b", {"BBB": 0.1, "IWM": -0.1})
    assert do_plan(w) == core.EXIT_REFUSED and "never overwritten" in w.out.getvalue()
    assert read(w.day / "plan.json")["plan_sha"] == sent_sha


def test_plan_refuses_after_the_window_and_idles_on_a_non_session(w):
    w.c.now = at(F, 15, 58)
    assert sr.plan(w.deps) == core.EXIT_REFUSED and "past the send window" in w.out.getvalue()
    w.c.now = at(dt.date(2026, 11, 21), 14, 0)           # a Saturday
    assert sr.plan(w.deps) == core.EXIT_IDLE


# ---------------------------------------------------------------------------- SEND

@pytest.mark.parametrize("dry", [None, "1", "", "false", " 0"])
def test_dry_run_never_submits_even_when_armed(w, dry):
    arm(w)
    do_plan(w)
    w.deps.env.pop("DRY_RUN")
    if dry is not None:
        w.deps.env["DRY_RUN"] = dry
    assert do_send(w) == core.EXIT_DRY
    assert w.c.submitted == [] and not (w.day / "STARTED").exists()
    assert read(w.day / "send.json")["exit"] == "DRY"


def test_unarmed_refuses_and_a_wrong_approval_refuses_even_when_auto_armed(w):
    do_plan(w)
    assert do_send(w) == core.EXIT_REFUSED and "not armed" in w.out.getvalue()
    arm(w)
    (w.day / "APPROVED").write_text(json.dumps({"plan_sha": "0" * 64}))
    assert do_send(w) == core.EXIT_REFUSED and "does not match" in w.out.getvalue()
    assert w.c.submitted == [] and not (w.day / "STARTED").exists()


def test_approve_shows_the_list_and_binds_the_send_to_that_sha(w):
    do_plan(w)
    sha = read(w.day / "plan.json")["plan_sha"]
    assert sr.approve(w.deps, date=F) == core.EXIT_PREVIEW and not (w.day / "APPROVED").exists()
    assert "events-20261117-AAA-1" in w.out.getvalue() and "NOT APPROVED" in w.out.getvalue()
    assert sr.approve(w.deps, date=F, sha="f" * 64) == core.EXIT_REFUSED and not (w.day / "APPROVED").exists()
    assert sr.approve(w.deps, date=F, sha=sha) == 0
    assert do_send(w) == core.EXIT_SENT and len(w.c.submitted) == 3
    assert sr.approve(w.deps, date=F, sha=sha) == core.EXIT_REFUSED       # STARTED: nothing to approve


def test_an_approval_does_not_cover_a_replanned_list(w):
    do_plan(w)
    assert sr.approve(w.deps, date=F, sha=read(w.day / "plan.json")["plan_sha"]) == 0
    decision(w.ddir, "b", {"BBB": 0.2, "IWM": -0.1})
    do_plan(w)
    assert do_send(w) == core.EXIT_REFUSED and w.c.submitted == []


def test_started_is_written_before_the_first_submit_and_every_qty_is_a_positive_int(w):
    arm(w)
    do_plan(w)
    seen = []
    w.c.on_submit = lambda: seen.append((w.day / "STARTED").exists())
    assert do_send(w) == core.EXIT_SENT
    assert seen == [True, True, True]
    assert all(type(s["qty"]) is int and s["qty"] > 0 and s["tif"] == "day" for s in w.c.submitted)
    assert sorted((s["symbol"], s["side"], s["qty"]) for s in w.c.submitted) == [
        ("AAA", "buy", 50), ("BBB", "buy", 20), ("IWM", "sell", 8)]
    started = read(w.day / "STARTED")
    assert started["plan_sha"] == read(w.day / "plan.json")["plan_sha"]
    assert read(w.day / "send.json")["exit"] == "SENT"


def test_a_second_send_refuses_on_started_and_sends_nothing_more(w):
    arm(w)
    do_plan(w)
    assert do_send(w) == core.EXIT_SENT
    assert do_send(w, mm=55) == core.EXIT_REFUSED and "STARTED exists" in w.out.getvalue()
    assert len(w.c.submitted) == 3


@pytest.mark.parametrize("case", ["started", "own_prefix", "open_order", "unread"])
def test_a_set_that_may_already_be_out_refuses(w, case):
    arm(w)
    do_plan(w)
    row = {"id": "x1", "client_order_id": "manual-1", "symbol": "AAA", "side": "buy", "qty": "1",
           "type": "market", "time_in_force": "day", "filled_qty": "0", "status": "filled",
           "submitted_at": "", "_at": at(F, 10, 0)}
    if case == "started":
        (w.day / "STARTED").write_text("{}")
    elif case == "own_prefix":
        w.c.order_list.append({**row, "client_order_id": "events-20261117-AAA-1"})
    elif case == "open_order":
        w.c.order_list.append({**row, "status": "new"})
    else:
        w.c.orders_error = RuntimeError("orders endpoint down")
    assert do_send(w) == core.EXIT_REFUSED
    assert "[no_set_in_auction]" in w.out.getvalue() and w.c.submitted == []
    if case != "started":
        assert not (w.day / "STARTED").exists()


def test_positions_that_moved_since_the_plan_refuse(w):
    arm(w)
    do_plan(w)
    w.c.pos = {"AAA": 1}
    assert do_send(w) == core.EXIT_REFUSED and "positions moved since the plan" in w.out.getvalue()
    assert w.c.submitted == [] and not (w.day / "STARTED").exists()


def test_a_send_before_the_window_is_idle_and_writes_nothing_but_a_preview_still_shows_the_gates(w):
    """The early-close timer slots fire every day; on a normal day they must not mark the day
    refused (a REFUSED send.json reads as a missed day at VERIFY)."""
    arm(w)
    do_plan(w)
    w.c.now = at(F, 12, 41)
    before = sorted(p.name for p in w.day.iterdir())
    assert sr.send(w.deps) == core.EXIT_IDLE and "before the send window" in w.out.getvalue()
    assert w.c.submitted == [] and sorted(p.name for p in w.day.iterdir()) == before
    assert sr.send(w.deps, preview=True) == core.EXIT_PREVIEW and "outside the late-market send window" in w.out.getvalue()


@pytest.mark.parametrize("hh, mm, why", [(15, 58, "outside the late-market send window"),
                                         (15, 57, "SEND BUDGET")])
def test_outside_the_late_window_or_too_late_to_finish_refuses(w, hh, mm, why):
    arm(w)
    do_plan(w)
    w.c.now = at(F, hh, mm) + (dt.timedelta(seconds=30) if why == "SEND BUDGET" else dt.timedelta(0))
    assert sr.send(w.deps) == core.EXIT_REFUSED and why in w.out.getvalue()
    assert w.c.submitted == [] and not (w.day / "STARTED").exists()


def test_a_halt_refuses_from_the_repo_or_from_the_state_dir(w):
    arm(w)
    do_plan(w)
    (w.state / "HALT").write_text("operator says stop\n")
    assert do_send(w) == core.EXIT_REFUSED and "operator says stop" in w.out.getvalue()
    (w.state / "HALT").unlink()
    w.deps.halts = lambda book: [{"scope": book, "reason": "scoped halt", "path": "ops/HALT_events.md"}]
    assert do_send(w) == core.EXIT_REFUSED and "scoped halt" in w.out.getvalue()
    assert w.c.submitted == []


def test_a_client_that_is_not_the_paper_endpoint_refuses(w):
    arm(w)
    do_plan(w)
    w.c.trading_endpoint = "https://api.alpaca.markets"
    assert do_send(w) == core.EXIT_REFUSED and "paper only" in w.out.getvalue() and w.c.submitted == []


def test_a_name_whose_shortability_flipped_since_plan_is_skipped_and_the_rest_go(w):
    arm(w)
    do_plan(w)
    w.c.assets["IWM"]["easy_to_borrow"] = False
    assert do_send(w) == core.EXIT_SENT
    assert sorted(s["symbol"] for s in w.c.submitted) == ["AAA", "BBB"]
    assert "IWM" in read(w.day / "send.json")["skipped"][0]


def test_a_hand_edited_plan_is_never_sent(w):
    arm(w)
    do_plan(w)
    p = read(w.day / "plan.json")
    p["orders"][0]["qty"] += 1
    (w.day / "plan.json").write_text(json.dumps(p))
    assert do_send(w) == core.EXIT_REFUSED and w.c.submitted == []
    do_plan(w)
    p = read(w.day / "plan.json")
    p["sleeves"][0]["targets"]["AAA"] = 49                # the orders still hash; the booking would differ
    (w.day / "plan.json").write_text(json.dumps(p))
    assert do_send(w) == core.EXIT_REFUSED
    assert "sleeve plans hash" in w.out.getvalue() and w.c.submitted == []


def test_send_with_no_plan_refuses(w):
    arm(w)
    assert do_send(w) == core.EXIT_REFUSED and "no plan for" in w.out.getvalue() and w.c.submitted == []


# -------------------------------------------------------------------------- VERIFY

def conserved(w):
    """The ledger's shares sum to the broker's positions; its cash to what the account paid."""
    book = led(w)
    ledger.check_against_broker(book, {s: q for s, q in w.c.pos.items() if q != 0})
    paid = sum((1 if f["side"] == "buy" else -1) * int(f["qty"]) * float(f["price"]) for f in w.c.fills)
    assert sum(r["cash"] for r in book["sleeves"].values()) == pytest.approx(-paid)
    return book


def test_verify_books_full_fills_scores_each_sleeve_and_is_idempotent(w):
    arm(w)
    w.c.bar_over[F] = {"AAA": 21.0, "BBB": 50.0, "IWM": 250.0}      # AAA closes a dollar above its fill
    assert session(w, F) == (core.EXIT_PLANNED, core.EXIT_SENT, sr.VERIFY_PASS)
    book = conserved(w)
    assert book["session"] == str(F)
    assert ledger.shares_of(book) == {"a": {"AAA": 50, "IWM": -4}, "b": {"BBB": 20, "IWM": -4}}
    assert read(w.day / "ledger_before.json") == ledger.empty()
    rows = (w.state / "sleeve_scores.csv").read_text().splitlines()
    assert rows[0].split(",") == list(sr.SCORES_COLUMNS) and len(rows) == 4
    a = dict(zip(rows[0].split(","), rows[1].split(",")))
    assert (a["slug"], float(a["pnl"]), float(a["day_change"]), a["n_names"]) == ("a", 50.0, 50.0, "2")
    bk = dict(zip(rows[0].split(","), rows[3].split(",")))
    assert bk["slug"] == "_book" and float(bk["pnl"]) == 50.0 and float(bk["residual"]) == -50.0  # equity flat in the fake
    v = read(w.day / "verify.json")
    assert v["ok"] and v["ledger_applied"] and "daily bar" in v["marks_source"]
    before = {p.name: p.read_bytes() for p in (w.state / "ledger.json", w.state / "sleeve_scores.csv",
                                                w.day / "verify.json", w.day / "ledger_before.json")}
    assert do_verify(w) == sr.VERIFY_PASS and "already verified" in w.out.getvalue()
    assert before == {p.name: p.read_bytes() for p in (w.state / "ledger.json", w.state / "sleeve_scores.csv",
                                                       w.day / "verify.json", w.day / "ledger_before.json")}


def test_each_score_row_records_the_capital_the_plan_sized_the_sleeve_from(w):
    """Team lead, 2026-11-19: "Yes, add it now". The ladder's two tests (promote.py) need the
    capital a sleeve traded at on each session, and nothing recorded it. PLAN writes each
    sleeve's capital_usd into plan.json from the config it sized the targets with (inside
    record_sha, so it cannot be edited afterwards) and VERIFY copies it to the score row. It
    is NOT read from the book file at VERIFY: the file here changes between SEND and VERIFY,
    as a release in the afternoon would change it, and the row still says what was traded.
    Fails on 4ad01d0, which has no such column."""
    arm(w)
    assert (do_plan(w), do_send(w)) == (core.EXIT_PLANNED, core.EXIT_SENT)
    assert {s["slug"]: s["capital_usd"] for s in read(w.day / "plan.json")["sleeves"]} == {"a": 10000.0, "b": 10000.0}
    set_book(w, sleeves=[{**BOOK["sleeves"][0], "capital_usd": 20000}, BOOK["sleeves"][1]])
    assert do_verify(w) == sr.VERIFY_PASS
    rows = list(csv.DictReader((w.state / "sleeve_scores.csv").open()))
    assert sr.SCORES_COLUMNS[-1] == "capital_usd"
    assert {r["slug"]: r["capital_usd"] for r in rows} == {"a": "10000.0000", "b": "10000.0000", sr.BOOK_ROW: ""}


def test_a_sleeve_with_no_recorded_capital_gets_an_empty_cell_never_a_default():
    """A plan written before the column existed, or a ledger sleeve the plan does not list:
    the cell is empty, and promote.py reads empty as UNMEASURED."""
    new = {"sleeves": {"a": {"shares": {"AAA": 1}, "cash": -20.0}, "old": {"shares": {}, "cash": 3.0}}}
    rows, _ = sr.score_rows(F, new, {"AAA": 21.0}, {}, None, {"a": 10000.0})
    assert {r["slug"]: r["capital_usd"] for r in rows} == {"a": "10000.0000", "old": "", sr.BOOK_ROW: ""}
    rows, _ = sr.score_rows(F, new, {"AAA": 21.0}, {}, None, {"a": None})
    assert rows[0]["capital_usd"] == ""


def test_verify_books_a_partial_fill_and_conserves_shares_and_cash(w):
    arm(w)
    w.c.fill_frac["IWM"] = 0.5                          # 4 of 8 short
    assert session(w, F) == (core.EXIT_PLANNED, core.EXIT_SENT, sr.VERIFY_FAIL)   # unfilled: verify says so
    book = conserved(w)
    assert ledger.shares_of(book) == {"a": {"AAA": 50, "IWM": -2}, "b": {"BBB": 20, "IWM": -2}}
    v = read(w.day / "verify.json")
    assert v["ledger_applied"] and "filled 4/8" in v["reason"]


def test_verify_books_a_full_cross_at_the_close_with_no_order(w):
    arm(w)
    decision(w.ddir, "b", {"IWM": 0.1})                 # b +4 against a -4
    w.c.bar_over[F] = {"AAA": 20.0, "BBB": 50.0, "IWM": 251.0}
    assert session(w, F) == (core.EXIT_PLANNED, core.EXIT_SENT, sr.VERIFY_PASS)
    assert [s["symbol"] for s in w.c.submitted] == ["AAA"] and "IWM" not in w.c.pos
    book = conserved(w)
    assert ledger.shares_of(book) == {"a": {"AAA": 50, "IWM": -4}, "b": {"IWM": 4}}
    crosses = [b for b in read(w.day / "verify.json")["bookings"] if b["kind"] == "cross"]
    assert {(b["slug"], b["shares"], b["price"]) for b in crosses} == {("a", -4, 251.0), ("b", 4, 251.0)}


def test_a_dry_day_still_rolls_the_ledger_for_crosses_and_stale_counts(w):
    """Nothing sent (DRY_RUN unset): no STARTED, a PASS explained by the gate, and the ledger
    still moves on, so the next plan is not refused for an unbooked session."""
    w.deps.env.pop("DRY_RUN")
    decision(w.ddir, "a", {"IWM": -0.1})
    decision(w.ddir, "b", {"IWM": 0.1}, written="2026-11-17T18:30:00+00:00")     # late: b holds, stale 1
    assert session(w, F) == (core.EXIT_PLANNED, core.EXIT_DRY, sr.VERIFY_PASS)
    book = led(w)
    assert book["session"] == str(F) and book["sleeves"]["b"]["stale_sessions"] == 1
    assert ledger.shares_of(book) == {"a": {}, "b": {}} and w.c.submitted == []
    assert "not sent by choice" in read(w.day / "verify.json")["notes"][0]
    assert do_plan(w, dt.date(2026, 11, 18)) == core.EXIT_PLANNED


def test_a_missed_send_is_a_fail_that_still_books(w):
    arm(w)
    do_plan(w)
    assert do_verify(w) == sr.VERIFY_FAIL
    assert "MISSED" in read(w.day / "verify.json")["reason"] and led(w)["session"] == str(F)


def test_a_send_refused_for_time_is_a_missed_day_not_an_explained_one(w):
    """Only DRY_RUN, arming and a halt explain a day with orders and no send (the core's rule)."""
    arm(w)
    do_plan(w)
    assert do_send(w, hh=15, mm=58) == core.EXIT_REFUSED            # after the window (8 to 2 minutes here)
    assert do_verify(w) == sr.VERIFY_FAIL
    assert "MISSED" in read(w.day / "verify.json")["reason"] and led(w)["session"] == str(F)


def test_plan_refuses_while_an_earlier_plan_is_unbooked_even_when_no_share_moved(w):
    """A dry day changes no position, so the ledger still equals the broker; its crosses and
    stale counts are unbooked all the same, and only this check sees it."""
    w.deps.env.pop("DRY_RUN")
    do_plan(w)
    do_send(w)
    assert do_plan(w, dt.date(2026, 11, 18)) == core.EXIT_REFUSED
    assert "VERIFY has not booked ['2026-11-17']" in w.out.getvalue()
    assert not (w.state / "2026-11-18" / "plan.json").exists()


def test_verify_fails_and_books_nothing_when_the_broker_and_the_fills_disagree(w):
    arm(w)
    do_plan(w)
    do_send(w)
    w.c.pos["AAA"] += 1                                  # a share no fill explains
    assert do_verify(w) == sr.VERIFY_FAIL
    v = read(w.day / "verify.json")
    assert not v["ledger_applied"] and "AAA: position +51" in v["reason"]
    assert not (w.state / "ledger.json").exists() and not (w.state / "sleeve_scores.csv").exists()
    # and the next session's plan refuses until a person has repaired it
    assert do_plan(w, dt.date(2026, 11, 18)) == core.EXIT_REFUSED
    assert "absent ledger" in w.out.getvalue() or "VERIFY has not booked" in w.out.getvalue()
    w.c.pos["AAA"] -= 1                                  # repaired: the same verify now books
    assert do_verify(w) == sr.VERIFY_PASS and led(w)["session"] == str(F)


@pytest.mark.parametrize("cid", ["events-20261117-ZZZ-9", "manual-probe"])
def test_verify_fails_on_an_order_and_fill_this_runner_did_not_record(w, cid):
    arm(w)
    do_plan(w)
    do_send(w)
    w.c.order_list.append({"id": "foreign", "client_order_id": cid, "symbol": "AAA", "side": "buy", "qty": "1",
                           "type": "market", "time_in_force": "day", "filled_qty": "1", "status": "filled",
                           "submitted_at": "", "_at": at(F, 15, 54)})
    w.c.fills.append({"id": "ff", "activity_type": "FILL", "order_id": "foreign", "symbol": "AAA", "side": "buy",
                      "qty": "1", "price": "20", "type": "fill", "_date": F})
    w.c.pos["AAA"] += 1
    assert do_verify(w) == sr.VERIFY_FAIL
    v = read(w.day / "verify.json")
    assert cid in v["reason"] and "belongs to order foreign" in v["reason"] and not v["ledger_applied"]
    assert not (w.state / "ledger.json").exists()


def test_verify_refuses_while_the_market_is_open_and_without_a_plan(w):
    arm(w)
    do_plan(w)
    do_send(w)
    w.c.now, w.c.is_open = at(F, 15, 59), True
    assert sr.verify(w.deps) == sr.VERIFY_FAIL and "still open" in w.out.getvalue()
    assert not (w.state / "ledger.json").exists()
    w.c.now, w.c.is_open = at(dt.date(2026, 11, 18), 16, 30), False
    assert sr.verify(w.deps) == sr.VERIFY_FAIL and "no plan.json for 2026-11-18" in w.out.getvalue()


def test_a_missed_verify_can_be_booked_the_next_day_and_plan_refuses_until_it_is(w):
    arm(w)
    do_plan(w)
    do_send(w)
    nxt = dt.date(2026, 11, 18)
    decision(w.ddir, "a", {"AAA": 0.1, "IWM": -0.1}, asof=F)
    decision(w.ddir, "b", {"BBB": 0.1, "IWM": -0.1}, asof=F)
    assert do_plan(w, nxt) == core.EXIT_REFUSED
    w.c.now, w.c.is_open = at(nxt, 9, 0), False
    assert sr.verify(w.deps, date=F) == sr.VERIFY_PASS
    assert led(w)["session"] == str(F)
    assert (w.state / "sleeve_scores.csv").read_text().splitlines()[-1].endswith(",,")   # equity not that day's
    assert do_plan(w, nxt) == core.EXIT_PLANNED and read(w.state / str(nxt) / "plan.json")["orders"] == []


def test_a_sleeve_with_no_close_on_the_day_is_not_scored_and_the_ledger_still_books(w):
    arm(w)
    w.c.bar_over[F] = {"BBB": 50.0, "IWM": 250.0}        # AAA has no bar on F
    assert session(w, F) == (core.EXIT_PLANNED, core.EXIT_SENT, sr.VERIFY_FAIL)
    rows = (w.state / "sleeve_scores.csv").read_text().splitlines()
    assert rows[1].startswith(f"{F},a,,") and "no close on" in read(w.day / "verify.json")["reason"]
    assert led(w)["session"] == str(F)


def test_no_decision_holds_never_opens_then_flattens_after_the_limit(w):
    """Day 1 trades. From day 2 sleeve `a` gets a late, a wrong-as-of and a malformed file:
    it holds for max_stale_sessions (2) sessions, opening nothing new, then is flattened."""
    arm(w)
    assert session(w, F)[2] == sr.VERIFY_PASS
    days = SESSIONS[3:]
    bad = [dict(written=f"{days[0]}T18:30:00+00:00"),                # 13:30 New York on the session: late
           dict(asof_in_file=str(D)),                                # names another as-of
           dict(weights={"AAA": "lots"})]                            # malformed
    seen = []
    for prev, day, over in zip(SESSIONS[2:], days, bad):
        decision(w.ddir, "b", {"BBB": 0.1, "IWM": -0.1}, asof=prev)
        kw = {k: v for k, v in over.items() if k != "asof_in_file"}
        decision(w.ddir, "a", kw.pop("weights", {"AAA": 0.5, "ZZZ": 0.5}), asof=prev, **kw)
        if "asof_in_file" in over:
            p = w.ddir / "a" / "decisions" / f"{prev}.json"
            r = read(p); r["asof"] = over["asof_in_file"]; p.write_text(json.dumps(r))
        n_before = len(w.c.submitted)
        codes = session(w, day)
        a = read(w.state / str(day) / "plan.json")["sleeves"][0]
        seen.append((a["action"], a["stale_sessions"], [s["symbol"] for s in w.c.submitted[n_before:]], codes[2]))
    assert seen[0] == ("hold", 1, [], sr.VERIFY_PASS)
    assert seen[1] == ("hold", 2, [], sr.VERIFY_PASS)
    assert seen[2][0:2] == ("flatten", 3) and sorted(seen[2][2]) == ["AAA", "IWM"]
    final = conserved(w)
    assert ledger.shares_of(final) == {"a": {}, "b": {"BBB": 20, "IWM": -4}}
    assert w.c.pos == {"AAA": 0, "BBB": 20, "IWM": -4}
    assert not any(s["symbol"] == "ZZZ" for s in w.c.submitted)


def test_a_batch_cut_off_by_the_window_can_still_be_read_and_booked(w, tmp_path):
    """`_transmit` writes `cutoff` for the order it stopped at, before any submit line for it;
    the core's reader raises on that line, this runner's does not."""
    log = tmp_path / "orders.jsonl"
    log.write_text(json.dumps({"event": "submit", "client_order_id": "events-1", "symbol": "AAA", "side": "buy", "qty": 1})
                   + "\n" + json.dumps({"event": "cutoff", "client_order_id": "events-2"}) + "\n")
    assert list(sr.recorded_orders(log)) == ["events-1"]
    from quantt.session.verify import read_orders_jsonl
    with pytest.raises(sr.RecordError):
        read_orders_jsonl(log)
    log.write_text(json.dumps({"event": "accepted", "client_order_id": "events-3"}) + "\n")
    with pytest.raises(sr.RecordError, match="no submit line"):
        sr.recorded_orders(log)


# ---------------------------------------------------------------- the boundary

def test_no_code_path_addresses_anything_but_the_client_it_was_given(w, monkeypatch):
    """A whole armed session: only the fake's expected methods are called, every price read goes
    to the client's own data host through its own GET, and no real client is ever built."""
    def boom(*a, **k):
        raise AssertionError("a real AlpacaClient was constructed")
    monkeypatch.setattr(alpaca.AlpacaClient, "__init__", boom)
    arm(w)
    assert session(w, F) == (core.EXIT_PLANNED, core.EXIT_SENT, sr.VERIFY_PASS)
    assert set(w.c.calls) <= EXPECTED_CALLS and w.c.calls.count("submit_order") == 3
    assert {p["start"] for p in w.c.get_params} == {str(D), str(F)}
    # PLAN asks for D by its date; VERIFY, at 16:30 on F, asks for F up to SIP_DELAY ago (prices.py).
    f_end = (at(F, 16, 30).astimezone(dt.timezone.utc) - prices.SIP_DELAY).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert {(p["start"], p["end"]) for p in w.c.get_params} == {(str(D), str(D)), (str(F), f_end)}
    assert all(p["timeframe"] == "1Day" and p["adjustment"] == "raw"
               and p["feed"] == "sip" for p in w.c.get_params)


def test_the_paper_endpoint_constant_is_the_clients_and_the_package_never_imports_shadow():
    import ast
    import pathlib
    assert sr.PAPER_BASE == alpaca.PAPER_BASE
    here = pathlib.Path(sr.__file__).parent
    for f in here.glob("*.py"):
        tree = ast.parse(f.read_text())
        mods = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names] + \
               [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
        assert not any(m == "shadow" or m.startswith("shadow.") for m in mods), f
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert "submit_order" not in names, f"{f.name} calls submit_order itself; only the core's _transmit may"
        assert not names & {"replace_order", "cancel_order"}, f


# ---------------------------------------------------------------------- book file

def test_the_released_book_file_loads_and_every_slug_is_a_shadow_book():
    """The values are pinned on purpose: they are the team lead's rulings (2026-11-16: seven
    books in a $1M account, gross to 1.5x, the small-name book capped at $25,000; 2026-11-18:
    equal risk per family, every new sleeve at a quarter of its full size) and the order
    limits derived from them, so a change to the file is a deliberate edit of this test too.
    The window must fit max_orders by the core's own send budget, or the first session, which
    builds every book, could never start."""
    cfg = config.load(sr.BOOK_PATH)
    assert cfg.book == "events" and len(cfg.sleeves) == 8 and all(s.enabled for s in cfg.sleeves)
    full = {"cef_exdate_after": 132000, "cef_exdate_before_after": 97000, "units_exdate_after": 52000,
            "units_exdate_before_after": 36000, "specdiv_wait": 105000, "specdiv_wait_small": 25000,
            "pead_small_long": 96000,
            # team lead, 2026-11-19: the unit-trust termination book, a fifth family, at the same
            # risk unit (11,232 / 0.0807); its vol is 225 sessions of 2026, not a long backtest
            "uit_termination": 139000}
    assert {s.slug: s.capital_usd for s in cfg.sleeves} == {k: v / 4 for k, v in full.items()}
    # 2026-11-18: the full sizes and the four families are in the file itself, no longer only in
    # the prose of _note_sleeves; the ladder report (promote.py) reads them from here
    assert {s.slug: s.full_capital_usd for s in cfg.sleeves} == full
    assert {s.slug: s.family for s in cfg.sleeves} == {
        "cef_exdate_after": "cef_exdate", "cef_exdate_before_after": "cef_exdate",
        "units_exdate_after": "units_exdate", "units_exdate_before_after": "units_exdate",
        "specdiv_wait": "special_dividends", "specdiv_wait_small": "special_dividends",
        "pead_small_long": "earnings_drift", "uit_termination": "unit_trust_terminations"}
    # 2026-11-18 (E-2026-11-18-24): the sigma of the 60-session test is each sleeve's backtest
    # volatility, the figures of E-2026-11-18-04; no modelled fill cost is set for any sleeve yet
    assert {s.slug: s.backtest_vol_annual for s in cfg.sleeves} == {
        "cef_exdate_after": 0.042, "cef_exdate_before_after": 0.057, "units_exdate_after": 0.107,
        "units_exdate_before_after": 0.154, "specdiv_wait": 0.053, "specdiv_wait_small": 0.053,
        "pead_small_long": 0.117, "uit_termination": 0.081}
    # team lead, 2026-11-19: the cards' measured half-spreads for the two special-dividend
    # books, 15bp as a labelled assumption for the other five (the file's _note says which)
    assert {s.slug: s.modelled_fill_cost_bp for s in cfg.sleeves} == {
        "specdiv_wait_small": 13.5, "specdiv_wait": 7.0, "cef_exdate_after": 15.0, "cef_exdate_before_after": 15.0,
        "units_exdate_after": 15.0, "units_exdate_before_after": 15.0, "pead_small_long": 15.0,
        "uit_termination": 15.0}
    # team lead, 2026-11-19: the ten-session promotion rule is waived for all eight
    assert all(s.promotion_waived for s in cfg.sleeves)
    assert (cfg.min_order_usd, cfg.max_gross_x_equity, cfg.max_name_usd, cfg.max_stale_sessions, cfg.max_orders,
            cfg.window_minutes_before_close) == (25, 1.5, 50000, 2, 300, (20, 2))
    # the shared IWM hedge at this stage fits under max_name_usd: pead 100%, each special-dividend book 50%
    c = {s.slug: s.capital_usd for s in cfg.sleeves}
    assert c["pead_small_long"] + 0.5 * (c["specdiv_wait"] + c["specdiv_wait_small"]) <= cfg.max_name_usd
    first, last = cfg.window_minutes_before_close
    assert gt.send_budget_s(cfg.max_orders) <= (first - last) * 60
    for slug in cfg.slugs:
        book = sr.REPO / "shadow" / "books" / f"{slug}.json"
        assert book.exists() and read(book)["slug"] == slug and read(book)["fill"] == "next_close"
    assert "PAPER ONLY" in read(sr.BOOK_PATH)["_note"]
    # the eighth sleeve at its quarter: a long-only book capped at 10% a fund, so its largest
    # name is far under max_name_usd, and the account's sleeves together are under its equity
    assert 0.10 * c["uit_termination"] <= cfg.max_name_usd and sum(c.values()) == 170500.0


# -------------------------------------------------------------------------- prices

class Bars:
    _data = "DATA-HOST"

    def __init__(self, pages):
        self.pages, self.seen = list(pages), []

    def _get(self, base, path, params=None):
        self.seen.append((base, path, dict(params)))
        return self.pages.pop(0)


OLD = dt.datetime(2026, 12, 1, tzinfo=dt.timezone.utc)      # a clock long after every day asked for: `end` is the date


def bar(day, c):
    return {"t": f"{day}T05:00:00Z", "c": c}


def test_closes_reads_every_page_through_the_clients_get_and_leaves_a_missing_symbol_absent():
    c = Bars([{"bars": {"AAA": [bar(D, 20.5)]}, "next_page_token": "t1"},
              {"bars": {"IWM": [bar(D, 250)]}, "next_page_token": None}])
    assert prices.closes(c, ["IWM", "AAA", "GONE"], D, OLD) == {"AAA": 20.5, "IWM": 250.0}
    (b0, p0, q0), (_, _, q1) = c.seen
    assert (b0, p0) == ("DATA-HOST", "/v2/stocks/bars")
    assert q0 == {"symbols": "AAA,GONE,IWM", "timeframe": "1Day", "adjustment": "raw", "feed": "sip",
                  "start": str(D), "end": str(D), "limit": prices.PAGE_LIMIT}
    assert q1["page_token"] == "t1"
    assert prices.closes(Bars([{"bars": None}]), ["AAA"], D, OLD) == {}


@pytest.mark.parametrize("body, why", [
    ({"bars": {"AAA": [bar(F, 20.0)]}}, "never used for another day"),
    ({"bars": {"AAA": [bar(D, 0)]}}, "not a finite number"),
    ({"bars": {"AAA": [bar(D, float("nan"))]}}, "not a finite number"),
    ({"bars": {"AAA": [bar(D, "20")]}}, "not a finite number"),
    ({"bars": {"AAA": [bar(D, 20.0), bar(D, 21.0)]}}, "two daily bars"),
    ({"bars": {"ZZZ": [bar(D, 20.0)]}}, "not asked for"),
    ({"bars": {"AAA": [{"c": 20.0}]}}, "lacks t or c"),
    ({"nothing": 1}, "no 'bars'"),
    ({"bars": {"AAA": [bar(D, 20.0)]}, "next_page_token": "same"}, "did not advance"),
])
def test_closes_raises_on_a_bar_it_cannot_trust(body, why):
    with pytest.raises(prices.PriceError, match=why):
        prices.closes(Bars([body, {"bars": {}, "next_page_token": "same"}, {"bars": {}, "next_page_token": "same"}]),
                      ["AAA"], D, OLD)


def test_closes_refuses_a_symbol_that_is_not_one():
    with pytest.raises(prices.PriceError, match="not an upper-case"):
        prices.closes(Bars([]), ["aaa/../x"], D, OLD)


# ===================================================== review of stage 2, 2026-11-16
# One test per defect the review found, then one per guard it could remove with the suite green.

NXT = dt.date(2026, 11, 18)


def decide_next(w, a=None, b=None, asof=F):
    decision(w.ddir, "a", a or {"AAA": 0.1, "IWM": -0.1}, asof=asof)
    decision(w.ddir, "b", b or {"BBB": 0.1, "IWM": -0.1}, asof=asof)


def sent_day(w):
    arm(w)
    assert (do_plan(w), do_send(w)) == (core.EXIT_PLANNED, core.EXIT_SENT)


def verify_reason(w, day=None):
    return read((day or w.day) / "verify.json")["reason"]


# ---- item 1: what is booked is what was sent

def test_verify_refuses_a_plan_that_replaced_the_one_that_was_sent(w):
    """The reviewer's race: plan B lands on disk after SEND loaded plan A. STARTED holds A."""
    arm(w)
    decision(w.ddir, "b", {"AAA": 0.1, "IWM": -0.1})                 # plan B: b owns the second AAA lot
    do_plan(w)
    plan_b = (w.day / "plan.json").read_bytes()
    decision(w.ddir, "b", {"BBB": 0.1, "IWM": -0.1})
    do_plan(w)                                                       # plan A, the one SEND loads
    sha_a = read(w.day / "plan.json")["record_sha"]
    w.c.on_submit = lambda: (w.day / "plan.json").write_bytes(plan_b)
    assert do_send(w) == core.EXIT_SENT
    st = read(w.day / "STARTED")
    assert st["record_sha"] == sha_a and st["plan"]["record_sha"] == sha_a
    assert do_verify(w) == sr.VERIFY_FAIL
    assert "not the plan that was sent" in verify_reason(w) and not (w.state / "ledger.json").exists()


def test_a_repeated_identical_submit_line_is_still_the_plans_order(w):
    sent_day(w)
    with (w.day / "orders.jsonl").open("a") as fh:
        fh.write(json.dumps({"event": "submit", "client_order_id": "events-20261117-AAA-1", "symbol": "AAA",
                             "side": "buy", "qty": 50}) + "\n")
    assert do_verify(w) == sr.VERIFY_PASS


def test_a_logged_order_with_another_quantity_than_the_plans_is_refused(w):
    sent_day(w)
    log = w.day / "orders.jsonl"
    log.write_text(log.read_text().replace('"qty": 50', '"qty": 51'))
    assert do_verify(w) == sr.VERIFY_FAIL
    assert "not an order of the plan" in verify_reason(w) and not (w.state / "ledger.json").exists()


@pytest.mark.parametrize("hh, mm", [(15, 52), (15, 55)])
def test_plan_refuses_from_the_moment_the_send_window_opens(w, hh, mm):
    w.c.now = at(F, hh, mm)
    assert sr.plan(w.deps) == core.EXIT_REFUSED and "send window's start" in w.out.getvalue()
    assert not (w.day / "plan.json").exists()


def test_plan_is_not_written_if_the_window_opened_while_it_was_being_built(w):
    w.c.now = at(F, 15, 51)
    real = w.c.asset

    def slow(sym):
        w.c.now = at(F, 15, 52)                                      # the reads took a minute
        return real(sym)
    w.c.asset = slow
    assert sr.plan(w.deps) == core.EXIT_REFUSED and "while this plan was being built" in w.out.getvalue()
    assert not (w.day / "plan.json").exists()


# ---- item 2: the gross limit

def test_a_plan_that_takes_gross_down_is_sent_after_equity_fell(w):
    """The core's 2026-10-09 incident: the limit judged on live equity refused a de-grossing set."""
    sent_day(w)
    assert do_verify(w) == sr.VERIFY_PASS                            # holds $4,000 gross
    set_book(w, max_gross_x_equity=0.03)                             # limit now $3,000: the plan scales down
    decide_next(w)
    assert do_plan(w, NXT) == core.EXIT_PLANNED
    p = read(w.state / str(NXT) / "plan.json")
    assert p["gross_usd"] <= 3000.0 and all(o["side"] != ("buy" if o["symbol"] != "IWM" else "sell") for o in p["orders"])
    w.c.acct["equity"] = 90000.0                                     # limit on live equity: $2,700 < the plan's gross
    n = len(w.c.submitted)
    assert do_send(w, NXT) == core.EXIT_SENT and len(w.c.submitted) > n


def test_a_set_that_adds_gross_above_the_limit_on_live_equity_is_refused(w):
    arm(w)
    set_book(w, max_gross_x_equity=0.03)
    do_plan(w)
    assert 0 < read(w.day / "plan.json")["gross_usd"] <= 3000.0
    w.c.acct["equity"] = 90000.0
    assert do_send(w) == core.EXIT_REFUSED and "[exposure]" in w.out.getvalue() and "max_gross_stress" in w.out.getvalue()
    assert w.c.submitted == []


def test_too_little_buying_power_refuses_the_send(w):
    arm(w)
    do_plan(w)
    w.c.acct["buying_power"] = 10.0
    assert do_send(w) == core.EXIT_REFUSED and "[exposure]" in w.out.getvalue() and w.c.submitted == []


# ---- item 3: a retry does not rewrite the day

def test_a_retry_send_that_finds_started_leaves_send_json_and_the_day_still_passes(w):
    sent_day(w)
    before = (w.day / "send.json").read_bytes()
    assert do_send(w, mm=55) == core.EXIT_REFUSED
    assert (w.day / "send.json").read_bytes() == before and read(w.day / "send.json")["exit"] == "SENT"
    assert len(list((w.day / "runs").glob("*-send.json"))) == 2      # the retry's own record is kept
    assert do_verify(w) == sr.VERIFY_PASS


# ---- item 4: a held name with no bar on the as-of session

def test_a_held_name_with_no_bar_holds_its_sleeve_and_is_valued_at_the_runners_last_close(w):
    sent_day(w)
    w.c.bar_over[F] = {"BBB": 50.0, "IWM": 250.0}                    # AAA: no bar on F, so no mark and no as-of close
    assert do_verify(w) == sr.VERIFY_FAIL and led(w)["session"] == str(F)      # a is unscored; the ledger books
    decide_next(w, a={"AAA": 0.2, "IWM": -0.1}, b={"BBB": 0.2, "IWM": -0.1})
    assert do_plan(w, NXT) == core.EXIT_PLANNED
    p = read(w.state / str(NXT) / "plan.json")
    a, b = p["sleeves"]
    assert a["action"] == "hold" and a["targets"] == {"AAA": 50, "IWM": -4} and "AAA" in a["why"]
    assert b["action"] == "decided" and b["targets"]["BBB"] == 40
    assert "AAA" not in p["closes"]
    assert p["stale_closes"] == {"AAA": {"price": 20.0, "session": str(F), "source": f"{F}/plan.json closes"}}
    assert p["gross_usd"] == 50 * 20.0 + 40 * 50.0 + 8 * 250.0
    assert [o["symbol"] for o in p["orders"]] == ["BBB"] and "STALE PRICE AAA" in w.out.getvalue()
    assert do_send(w, NXT) == core.EXIT_SENT and w.c.submitted[-1]["symbol"] == "BBB"


def test_a_held_name_this_runner_never_priced_refuses_the_plan_naming_it(w):
    w.c.pos = {"XXX": 5}
    (w.state / "ledger.json").write_text(json.dumps(
        {"version": 1, "session": None, "sleeves": {"a": {"shares": {"XXX": 5}, "cash": 0.0, "stale_sessions": 0}}}))
    assert do_plan(w) == core.EXIT_REFUSED
    assert "XXX is held, has no daily bar" in w.out.getvalue() and not (w.day / "plan.json").exists()


def test_the_last_recorded_close_prefers_the_newest_sessions_own_mark(w):
    for d, name, key, px in (("2026-11-13", "plan.json", "closes", 1.0), ("2026-11-16", "plan.json", "closes", 2.0),
                             ("2026-11-16", "verify.json", "marks", 3.0)):
        (w.state / d).mkdir(exist_ok=True)
        (w.state / d / name).write_text(json.dumps({key: {"AAA": px}, "stale_closes": {"AAA": {"price": 99.0}}}))
    assert sr.last_recorded_close(w.state, "AAA", F)["price"] == 3.0
    assert sr.last_recorded_close(w.state, "AAA", D)["price"] == 1.0          # strictly before
    assert sr.last_recorded_close(w.state, "ZZZ", F) is None


# ---- item 5: everything SEND and VERIFY read from the plan is under record_sha

@pytest.mark.parametrize("edit", ["current", "closes", "equity", "positions", "stale_closes", "net_targets", "ledger_sha"])
def test_an_edit_to_anything_send_or_verify_reads_from_the_plan_is_refused(w, edit):
    arm(w)
    do_plan(w)
    p = read(w.day / "plan.json")
    if edit == "current":
        p["targets"]["AAA"]["current"] = 1
    elif edit == "closes":
        p["closes"]["AAA"] = 0.01
    elif edit == "equity":
        p["equity"] = 1e9
    elif edit == "positions":
        p["positions"] = {"AAA": 1}
    elif edit == "ledger_sha":
        p["ledger_sha"] = "0" * 64
    elif edit == "stale_closes":
        p["stale_closes"] = {"AAA": {"price": 1.0, "session": "x", "source": "x"}}
    else:
        p["net_targets"]["AAA"] = 49
    (w.day / "plan.json").write_text(json.dumps(p))
    assert do_send(w) == core.EXIT_REFUSED and "hash to" in w.out.getvalue() and w.c.submitted == []
    assert do_verify(w) == sr.VERIFY_FAIL and not (w.state / "ledger.json").exists()


# ---- item 6: a sleeve that holds nothing can leave the book file

def test_an_emptied_sleeve_can_be_dropped_from_the_book_file_and_keeps_its_ledger_record(w):
    arm(w)
    decision(w.ddir, "b", {})
    assert session(w, F)[2] == sr.VERIFY_PASS and led(w)["sleeves"]["b"]["shares"] == {}
    set_book(w, sleeves=[BOOK["sleeves"][0]])
    decide_next(w)
    assert session(w, NXT) == (core.EXIT_PLANNED, core.EXIT_NOTHING, sr.VERIFY_PASS)
    assert set(led(w)["sleeves"]) == {"a", "b"}


# ---- item 8: the bar's date is its New York date

def test_a_bar_is_dated_by_its_new_york_day_not_by_the_utc_string():
    assert prices.closes(Bars([{"bars": {"AAA": [{"t": f"{F}T00:30:00Z", "c": 20.0}]}}]), ["AAA"], D, OLD) == {"AAA": 20.0}
    with pytest.raises(prices.PriceError, match="never used for another day"):
        prices.closes(Bars([{"bars": {"AAA": [{"t": f"{F}T00:30:00Z", "c": 20.0}]}}]), ["AAA"], F, OLD)
    assert prices.closes(Bars([{"bars": {"AAA": [{"t": "2026-07-01T04:00:00Z", "c": 20.0}]}}]), ["AAA"],
                         dt.date(2026, 7, 1), OLD) == {"AAA": 20.0}        # midnight New York in summer


# ---- the same-day read: the data plan refuses the last 15 minutes of SIP data (2026-11-20)

def test_the_evening_read_of_todays_close_ends_twenty_minutes_ago_not_at_the_date():
    """VERIFY at 17:35 ET on F asks for F's own bar. `end=F` means the end of F, inside the
    15 minutes the plan refuses (HTTP 403 on 2026-11-20); the request must end in the past."""
    c = Bars([{"bars": {"AAA": [bar(F, 20.5)]}}])
    assert prices.closes(c, ["AAA"], F, at(F, 17, 35)) == {"AAA": 20.5}
    q = c.seen[0][2]
    assert q["start"] == str(F)
    assert q["end"] == (at(F, 17, 35).astimezone(dt.timezone.utc) - prices.SIP_DELAY).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert prices.SIP_DELAY > dt.timedelta(minutes=15)


def test_a_day_long_past_is_still_asked_for_by_its_date():
    c = Bars([{"bars": {}}])
    prices.closes(c, ["AAA"], D, at(F, 11, 45))
    assert c.seen[0][2]["end"] == str(D)
    c = Bars([{"bars": {}}])                               # 00:21 the next day: the whole day is old enough
    prices.closes(c, ["AAA"], F, at(F + dt.timedelta(days=1), 0, 21))
    assert c.seen[0][2]["end"] == str(F)


@pytest.mark.parametrize("hh, mm", [(13, 0), (16, 0), (16, 19)])
def test_a_day_that_has_not_closed_has_no_close(hh, mm):
    """Today's bar before the close carries the last trade so far. No request is made."""
    c = Bars([])
    with pytest.raises(prices.PriceError, match="no partial day's bar"):
        prices.closes(c, ["AAA"], F, at(F, hh, mm))
    assert c.seen == []


def _z(when):
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_the_first_minute_a_same_day_read_is_allowed_ends_at_the_close():
    c = Bars([{"bars": {}}])
    prices.closes(c, ["AAA"], F, at(F, 16, 20))
    assert c.seen[0][2]["end"] == _z(at(F, 16, 0)) == f"{F}T21:00:00Z"        # winter: 16:00 ET is 21:00Z


def test_just_after_midnight_the_day_before_is_still_inside_the_refused_window():
    """00:10 the next day: the date-only end (midnight) is 10 minutes old, which the plan refuses."""
    c = Bars([{"bars": {}}])
    prices.closes(c, ["AAA"], F, at(F + dt.timedelta(days=1), 0, 10))
    assert c.seen[0][2]["end"] == _z(at(F, 23, 50))


def test_a_summer_day_converts_with_the_summer_offset():
    day = dt.date(2026, 7, 1)
    c = Bars([{"bars": {}}])
    prices.closes(c, ["AAA"], day, at(day, 17, 35))
    assert c.seen[0][2]["end"] == "2026-07-01T21:15:00Z"                     # 17:15 EDT
    with pytest.raises(prices.PriceError, match="no partial day's bar"):
        prices.closes(Bars([]), ["AAA"], day, at(day, 16, 19))


def test_the_clock_must_carry_a_time_zone():
    with pytest.raises(prices.PriceError, match="time zone"):
        prices.closes(Bars([]), ["AAA"], D, dt.datetime(2026, 12, 1))


# ---- guards at SEND

def test_an_account_with_shorting_disabled_refuses_the_send(w):
    arm(w)
    do_plan(w)
    w.c.acct["shorting_enabled"] = False
    assert do_send(w) == core.EXIT_REFUSED and "[shortability]" in w.out.getvalue() and w.c.submitted == []


def test_a_blocked_account_refuses_the_send(w):
    arm(w)
    do_plan(w)
    w.c.acct["trading_blocked"] = True
    assert do_send(w) == core.EXIT_REFUSED and "[sanity] account trading_blocked" in w.out.getvalue()
    assert w.c.submitted == []


def test_a_plan_whose_as_of_is_not_the_session_before_today_is_refused(w, monkeypatch):
    arm(w)
    do_plan(w)
    monkeypatch.setattr(sr, "asof_for", lambda day, cal: dt.date(2026, 11, 13))
    assert do_send(w) == core.EXIT_REFUSED and "is not the session before" in w.out.getvalue()
    assert w.c.submitted == []


def test_a_name_that_stopped_being_tradable_since_plan_is_skipped_and_the_rest_go(w):
    arm(w)
    do_plan(w)
    w.c.assets["AAA"]["tradable"] = False
    assert do_send(w) == core.EXIT_SENT
    assert sorted(s["symbol"] for s in w.c.submitted) == ["BBB", "IWM"]
    assert "not an active, tradable asset" in read(w.day / "send.json")["skipped"][0]


def test_started_is_created_exclusively_and_a_lost_race_sends_nothing(w, monkeypatch):
    """If another run's STARTED lands between the gate and the record, `create_exclusive`
    says so and nothing goes. A plain write could not tell, and this test would then submit."""
    arm(w)
    do_plan(w)
    asked = []
    monkeypatch.setattr(sr.rec, "create_exclusive", lambda path, obj: asked.append(path.name) or False)
    assert do_send(w) == core.EXIT_REFUSED and asked == ["STARTED"]
    assert "STARTED appeared between gate and record" in w.out.getvalue() and w.c.submitted == []


def test_another_books_plan_is_never_sent(w):
    arm(w)
    do_plan(w)
    p = read(w.day / "plan.json")
    p["book"] = "c4"
    (w.day / "plan.json").write_text(json.dumps(p))
    assert do_send(w) == core.EXIT_REFUSED and "is book 'c4''s" in w.out.getvalue() and w.c.submitted == []


# ---- guards at PLAN

def test_a_set_that_starts_while_the_plan_is_being_built_keeps_its_plan(w):
    real = w.c.asset

    def racing(sym):
        w.day.mkdir(exist_ok=True)
        (w.day / "STARTED").write_text("{}")
        return real(sym)
    w.c.asset = racing
    assert do_plan(w) == core.EXIT_REFUSED and "STARTED for 2026-11-17 while this plan was being built" in w.out.getvalue()
    assert not (w.day / "plan.json").exists()


def test_plan_refuses_a_session_the_ledger_is_already_booked_to(w):
    w.deps.env.pop("DRY_RUN")
    assert session(w, F) == (core.EXIT_PLANNED, core.EXIT_DRY, sr.VERIFY_PASS)
    before = (w.day / "plan.json").read_bytes()
    assert do_plan(w) == core.EXIT_REFUSED and "already booked to 2026-11-17" in w.out.getvalue()
    assert (w.day / "plan.json").read_bytes() == before


def test_a_calendar_with_two_rows_for_today_or_one_that_disagrees_with_nyse_refuses(w):
    real = w.c.calendar
    w.c.calendar = lambda s, e: real(s, e) + [r for r in real(s, e) if r["date"] == F]
    assert do_plan(w) == core.EXIT_REFUSED and "2 rows for 2026-11-17" in w.out.getvalue()
    w.c.calendar = lambda s, e: [r for r in real(s, e) if r["date"] != F]
    assert do_plan(w) == core.EXIT_REFUSED and "calendars disagree on 2026-11-17" in w.out.getvalue()
    assert not w.day.exists()


# ---- guards at VERIFY

def test_verify_refuses_a_date_after_today_and_a_non_session_that_has_a_plan(w):
    w.c.now, w.c.is_open = at(F, 16, 30), False
    assert sr.verify(w.deps, date=NXT) == sr.VERIFY_FAIL and "is after the Alpaca clock's date" in w.out.getvalue()
    sat = dt.date(2026, 11, 21)
    (w.state / str(sat)).mkdir()
    (w.state / str(sat) / "plan.json").write_text("{}")
    w.c.now = at(sat, 16, 30)
    assert sr.verify(w.deps) == sr.VERIFY_FAIL and "not a trading day on Alpaca's calendar, yet" in w.out.getvalue()
    (w.state / str(sat) / "plan.json").unlink()
    assert sr.verify(w.deps) == sr.VERIFY_PASS


def verified_day(w):
    sent_day(w)
    assert do_verify(w) == sr.VERIFY_PASS


def test_a_run_that_died_after_the_ledger_was_written_resumes_without_rewriting_anything(w, monkeypatch):
    verified_day(w)
    (w.day / "verify.json").unlink()
    keep = {p: p.read_bytes() for p in (w.state / "ledger.json", w.state / "sleeve_scores.csv",
                                        w.day / "ledger_before.json")}
    written, real = [], sr.rec.write_json_atomic
    monkeypatch.setattr(sr.rec, "write_json_atomic", lambda path, obj: written.append(path.name) or real(path, obj))
    assert do_verify(w) == sr.VERIFY_PASS and written == ["verify.json"]
    assert keep == {p: p.read_bytes() for p in keep}                 # no second ledger, no second score rows
    v = read(w.day / "verify.json")
    assert v["ledger_applied"] and v["scores_appended"] is False


def test_a_resumed_verify_that_does_not_reproduce_the_ledger_on_disk_fails_and_changes_nothing(w):
    verified_day(w)
    (w.day / "verify.json").unlink()
    book = led(w)
    book["sleeves"]["a"]["cash"] += 1.0
    (w.state / "ledger.json").write_text(json.dumps(book))
    keep = (w.state / "ledger.json").read_bytes()
    assert do_verify(w) == sr.VERIFY_FAIL and "does not give the ledger on disk" in verify_reason(w)
    assert (w.state / "ledger.json").read_bytes() == keep


def test_a_resumed_verify_without_the_kept_copy_refuses(w):
    verified_day(w)
    (w.day / "verify.json").unlink()
    (w.day / "ledger_before.json").unlink()
    assert do_verify(w) == sr.VERIFY_FAIL and "ledger_before.json is missing" in w.out.getvalue()


def test_verify_refuses_when_the_ledger_file_the_plan_was_built_on_is_gone(w):
    verified_day(w)
    decide_next(w)
    assert (do_plan(w, NXT), do_send(w, NXT)) == (core.EXIT_PLANNED, core.EXIT_NOTHING)
    (w.state / "ledger.json").unlink()
    assert do_verify(w, NXT) == sr.VERIFY_FAIL and "was built on a ledger file" in w.out.getvalue()


def test_verify_refuses_a_session_older_than_the_ledger(w):
    verified_day(w)
    decide_next(w)
    assert session(w, NXT)[2] == sr.VERIFY_PASS
    w.c.now, w.c.is_open = at(NXT, 17, 0), False
    assert sr.verify(w.deps, date=F) == sr.VERIFY_FAIL and "is booked to 2026-11-18, after 2026-11-17" in w.out.getvalue()


def test_verify_books_oldest_first(w, monkeypatch):
    w.deps.env.pop("DRY_RUN")
    do_plan(w)                                                       # F planned, never verified
    decide_next(w)
    with monkeypatch.context() as m:                                 # a plan for the next day, by force
        m.setattr(sr, "_unbooked_sessions", lambda *a: [])
        assert do_plan(w, NXT) == core.EXIT_PLANNED
    assert do_verify(w, NXT) == sr.VERIFY_FAIL and "['2026-11-17'] are not booked" in w.out.getvalue()
    assert not (w.state / "ledger.json").exists()


def test_verify_refuses_a_ledger_that_is_not_the_one_the_plan_was_built_on(w):
    w.deps.env.pop("DRY_RUN")
    do_plan(w)
    (w.state / "ledger.json").write_text(json.dumps(
        {"version": 1, "session": None, "sleeves": {"a": {"shares": {"AAA": 3}, "cash": 0.0, "stale_sessions": 0}}}))
    keep = (w.state / "ledger.json").read_bytes()
    assert do_verify(w) == sr.VERIFY_FAIL and "not the one the plan for 2026-11-17 was built on" in w.out.getvalue()
    assert (w.state / "ledger.json").read_bytes() == keep


def test_shares_moved_between_sleeves_after_plan_are_not_booked(w):
    """The totals still equal the broker's, so only the ledger's own hash can see it."""
    verified_day(w)
    decide_next(w)
    assert (do_plan(w, NXT), do_send(w, NXT)) == (core.EXIT_PLANNED, core.EXIT_NOTHING)
    book = led(w)
    book["sleeves"]["b"]["shares"]["AAA"] = book["sleeves"]["a"]["shares"].pop("AAA")
    (w.state / "ledger.json").write_text(json.dumps(book))
    ledger.check_against_broker(book, {s: q for s, q in w.c.pos.items() if q})       # the totals agree
    assert do_verify(w, NXT) == sr.VERIFY_FAIL and "was changed after PLAN" in w.out.getvalue()
    assert led(w) == book and led(w)["session"] == str(F)


def test_a_held_unpriced_name_is_not_scaled_when_the_gross_limit_binds(w):
    """Scaling it would make an order in a name with no price; the rest of the book takes the cut."""
    sent_day(w)
    w.c.bar_over[F] = {"BBB": 50.0, "IWM": 250.0}
    do_verify(w)
    set_book(w, max_gross_x_equity=0.03)                             # $3,000 against $4,000 held
    decide_next(w)
    assert do_plan(w, NXT) == core.EXIT_PLANNED
    p = read(w.state / str(NXT) / "plan.json")
    assert p["sleeves"][0]["targets"]["AAA"] == 50 and p["gross_usd"] <= 3000.0 and p["gross_factor"] < 1
    assert "AAA" not in [o["symbol"] for o in p["orders"]] and p["orders"]


def test_a_booking_that_does_not_match_the_broker_is_not_written(w, monkeypatch):
    sent_day(w)
    real = ledger.apply

    def wrong(*a, **k):
        new, bookings = real(*a, **k)
        new["sleeves"]["a"]["shares"]["AAA"] += 1
        return new, bookings
    monkeypatch.setattr(sr.ledger, "apply", wrong)
    assert do_verify(w) == sr.VERIFY_FAIL
    assert "AAA: +51, +50" in verify_reason(w) and not (w.state / "ledger.json").exists()


def order_of(w, sym):
    return next(o for o in w.c.order_list if o["symbol"] == sym)


@pytest.mark.parametrize("case, why", [
    ("gone", "Alpaca has no such order"),
    ("side", "Alpaca's order is sell AAA, the record buy AAA"),
    ("status", "is not final"),
    ("fill_side", "fill on order oid-"),
    ("filled_qty", "FILL activities sum to 50"),
])
def test_verify_fails_and_books_nothing_when_an_order_or_fill_is_not_what_was_recorded(w, case, why):
    sent_day(w)
    o = order_of(w, "AAA")
    if case == "gone":
        w.c.order_list.remove(o)
        w.c.fills[:] = [f for f in w.c.fills if f["order_id"] != o["id"]]
        w.c.pos["AAA"] = 0
    elif case == "side":
        o["side"] = "sell"
    elif case == "status":
        o["status"] = "partially_filled"
    elif case == "fill_side":
        next(f for f in w.c.fills if f["order_id"] == o["id"])["side"] = "sell"
    else:
        o["filled_qty"] = "49"
    assert do_verify(w) == sr.VERIFY_FAIL
    v = read(w.day / "verify.json")
    assert why in v["reason"] and not v["ledger_applied"] and not (w.state / "ledger.json").exists()


def test_score_rows_for_a_date_are_never_appended_twice(w, tmp_path):
    rows = [{c: "" for c in sr.SCORES_COLUMNS} | {"date": "2026-11-17", "slug": "a"}]
    p = tmp_path / "scores.csv"
    assert sr._append_scores(p, rows) is True and sr._append_scores(p, rows) is False
    assert len(p.read_text().splitlines()) == 2
    p.write_text("date,slug\n")
    with pytest.raises(sr.RecordError, match="header"):
        sr._append_scores(p, rows)


@pytest.mark.parametrize("bad, why", [
    ([], "not a version-1 ledger"),
    ({"version": 2, "session": None, "sleeves": {}}, "not a version-1 ledger"),
    ({"version": 1, "session": None, "sleeves": []}, "not a version-1 ledger"),
    ({"version": 1, "session": "yesterday", "sleeves": {}}, "is not a date or null"),
    ({"version": 1, "session": None, "sleeves": {"a": {"cash": 0.0, "stale_sessions": 0}}}, "no shares table"),
    ({"version": 1, "session": None, "sleeves": {"a": {"shares": {"AAA": 1.5}, "cash": 0.0, "stale_sessions": 0}}}, "not a whole number"),
    ({"version": 1, "session": None, "sleeves": {"a": {"shares": {"AAA": True}, "cash": 0.0, "stale_sessions": 0}}}, "not a whole number"),
    ({"version": 1, "session": None, "sleeves": {"a": {"shares": {}, "cash": float("nan"), "stale_sessions": 0}}}, "not a finite number"),
    ({"version": 1, "session": None, "sleeves": {"a": {"shares": {}, "cash": 0.0, "stale_sessions": -1}}}, "not a count"),
])
def test_a_malformed_ledger_is_refused_before_a_share_of_it_is_trusted(w, bad, why):
    with pytest.raises(ledger.LedgerError, match=why):
        sr.check_ledger(bad, "ledger.json")
    (w.state / "ledger.json").write_text(json.dumps(bad))
    assert do_plan(w) == core.EXIT_REFUSED and not (w.day / "plan.json").exists()


# ------------------------------------- a 429 on the send, then VERIFY (release check of 81e1071)
# A 429 to an order is waited out and the id read before any resend (core `_submit_one`, 2026-11-23).
# Whatever then happens, the order must end with an event VERIFY accepts for an order Alpaca does not
# hold, or VERIFY books nothing and the next PLAN refuses: the events book would stop until its
# records were repaired by hand. 81e1071 left two paths with no terminal event; these pinned them.

def _429_first(w, after_wait):
    real = w.c.submit_order
    hit = {"n": 0}

    def submit(symbol, qty, side, cid, *, time_in_force):
        if hit["n"] == 0:
            hit["n"] += 1
            w.c.calls.append("submit_order")
            raise alpaca.OrderRejected(f"POST {cid}: HTTP 429: rate limit exceeded", status=429,
                                       client_order_id=cid)
        return real(symbol, qty, side, cid, time_in_force=time_in_force)
    w.c.submit_order = submit
    w.deps = dataclasses.replace(w.deps, sleep=lambda s: after_wait(w))


def _books_and_next_plan_runs(w):
    assert do_verify(w) == sr.VERIFY_FAIL                  # the day is FAIL, loudly
    v = read(w.day / "verify.json")
    assert v["problems"] == [] and v["ledger_applied"] is True, v["problems"]
    assert read(w.state / "ledger.json")["session"] == str(F)
    nxt = dt.date(2026, 11, 18)
    decision(w.ddir, "a", {"AAA": 0.1, "IWM": -0.1}, asof=F)
    decision(w.ddir, "b", {"BBB": 0.1, "IWM": -0.1}, asof=F)
    assert do_plan(w, nxt) == core.EXIT_PLANNED, w.out.getvalue().splitlines()[-3:]


def test_a_429_then_the_window_closing_still_books_the_day(w):
    """The wait carries the batch to the window's end: the order is `rejected`, then the stop."""
    assert do_plan(w) == core.EXIT_PLANNED
    arm(w)
    _429_first(w, lambda w: setattr(w.c, "now", at(F, 15, 58)))
    assert do_send(w) == core.EXIT_FAIL
    rows = [json.loads(x) for x in (w.day / "orders.jsonl").read_text().splitlines()]
    first = rows[0]["client_order_id"]
    assert [r["event"] for r in rows if r["client_order_id"] == first][-1] == "rejected"
    _books_and_next_plan_runs(w)


def test_a_429_then_a_failed_read_still_books_the_day(w):
    """The read after the wait fails: a rejection (no resend), and the rest of the batch goes."""
    assert do_plan(w) == core.EXIT_PLANNED
    arm(w)
    real_lookup = w.c.order_by_client_id
    state = {"after_wait": False}

    def after(w):
        state["after_wait"] = True
    _429_first(w, after)

    def lookup(cid):
        if state["after_wait"]:
            state["after_wait"] = False
            raise alpaca.AlpacaHTTPError("GET failed after 5 attempts", status=503)
        return real_lookup(cid)
    w.c.order_by_client_id = lookup
    assert do_send(w) == core.EXIT_FAIL
    assert len(w.c.submitted) >= 1                         # the rest of the batch went
    _books_and_next_plan_runs(w)
