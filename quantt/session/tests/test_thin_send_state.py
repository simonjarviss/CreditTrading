"""CEF trial 55 (te4): "was a reduced decision's send sent?", read from the records run.py really writes.

WHY THIS FILE (the runner owner's review of PR #55, 2026-11-04, item 10, a BLOCKER). te4 is PAPER
ONLY, and paper runs `execution.mode = late_market` (CLAUDE.md order-path rule 3's recorded
exception), so the late-market send is the only one K1-K3 will ever read. A reduced decision is
one whose targets were SENT (pre-registration §4.2), and `drawdown._send_state` decides that from
the session's own records: <D>/STARTED (the rule-2 marker, written before the first order) and
send.json (`exit`, `plan_sha`, `final`, `not_final`). The tests in test_thin_stop_lines.py hand-
write those records. If the hand-written shape differed from what `_send_planned` writes, every
K-line would count wrongly on the book it is for and every test would still pass. So here the
records are written by the REAL send (`run.run_session` in the late window, test_run's fake
client and its late-market fixtures), read back by the runner's own reader
(`run._thin_read_day`) and classified:

  late market (the case that runs)                 sent?
  ------------------------------------------------ -----------------------------------------
  SENT, every order filled                         yes
  SENT, partially filled                           yes (what filled is the account's)
  SENT, every order final with 0 shares filled     no: "sent, nothing filled" (round-2 answer
    (canceled, expired or rejected), none working  (b), 2026-11-05: sent requires a fill)
  FAIL in part, what `final` records filled nothing yes, in part: a FAIL's `final` omits any
                                                   order of unknown fate
  0 shares under another final state (replaced,    UNMEASURED, naming it
    done_for_day, filled)
  DRY (DRY_RUN=1)                                  no
  REFUSED (not armed)                              no
  NOTHING_TO_SEND (the only order skipped at send) no
  FAIL, `final` records what went (a rejection)    yes, in part (item 5: classified from final)
  FAIL, `final` records nothing (no confirm)       UNMEASURED: the orders DID reach the broker
  FAIL, `final` records nothing (all rejected)     UNMEASURED: send.json cannot tell it apart,
                                                   and orders.jsonl holds a `submit` per POST
  FAIL before the first POST (clock read failed,   no: "not sent: 0 submissions proved by
    or past the window), with or without verify's  <records>" (round-2 answer (a), 2026-11-05:
    reconcile.json                                 orders.jsonl with zero `submit`, and a
                                                   reconcile.json naming no order of D's prefix)
  the same, one piece of that proof taken away     UNMEASURED, naming it (orders.jsonl missing,
                                                   unreadable, empty or with a submit; a
                                                   reconcile.json unreadable or naming an order)
  STARTED missing beside a SENT                    UNMEASURED
  send.json of another plan_sha                    UNMEASURED
  a later manual run's REFUSED over a SENT         UNMEASURED (STARTED beside a refused record)

  cls (the decide is the send; no send.json)       sent?
  ------------------------------------------------ -----------------------------------------
  SENT                                             yes (STARTED)
  REFUSED (not armed)                              no (no STARTED)
  FAIL after a rejection, the rest sent            yes (STARTED)
  FAIL, every order rejected                       yes: STARTED is the only per-session record
                                                   a cls run writes (drawdown.py's `sent`)

Each case is also walked through `thin_stop_record` with the plan marked reduced, so the episode
reads OPEN, NONE or UNMEASURED from the same files. On 87ad4e9 (the head the review read) the
FAIL-with-final case reads UNMEASURED where it now reads a reduced decision sent in part, and
fails here; every other row reads the same on 87ad4e9, and pins that the hand-written shape in
test_thin_stop_lines.py is the runner's.

Hermetic: test_run's FakeClient, fixed clocks, state under tmp_path; netguard refuses any socket.
"""
import datetime as dt
import json

import pytest

from ops.schedule.nyse_calendar import previous_trading_day
from quantt.broker.alpaca import OrderRejected
from quantt.session import drawdown as ddm
from quantt.session import run as rn
from quantt.session.tests.test_run import (BOOK, D, ET, SPEC, decided, make, to_send_time)
from src.deploy.sleeve import FLAT, SHORT, PositionTarget

NEXT = dt.date(2026, 9, 30)          # the session after D: its decide reads D's records back
LINES = {"thin_k1_episode_drawdown": 0.10, "thin_k2_max_name_frac": 0.9,
         "thin_k3_net_run": 0.25, "thin_k3_net_once": 0.8, "thin_k3_run_sessions": 3}


def _state_of(state, *, reduced=True):
    """(day, sent?) for D as the runner's reader reads it; `sent?` is `_send_state`'s answer,
    or the Unmeasured raised. The plan is marked as a reduced te4 decision and the session
    before it as decided with the key absent, so `thin_stop_record`'s walk ends there."""
    path = state / D.isoformat() / "plan.json"
    plan = json.loads(path.read_text())
    if reduced:
        plan["thin_session"] = {"reduced": True}
        plan["thin_stops"] = {"K3": {"verdict": ddm.NOT_APPLICABLE}}
        path.write_text(json.dumps(plan))
    before = state / previous_trading_day(D).isoformat()
    before.mkdir(parents=True, exist_ok=True)
    (before / "plan.json").write_text(json.dumps({"refusals": []}))     # the key absent then
    day = rn._thin_read_day(state, D, BOOK.cid_prefix)
    try:
        return day, ddm._send_state(D, day)
    except ddm.Unmeasured as e:
        return day, e


def _episode(state):
    """The next decide's episode, walked over the files run.py wrote (`_thin_read_day`)."""
    r = ddm.thin_stop_record(
        asof=D, session_date=NEXT, drawdown={"status": "HALVE", "asof": D.isoformat()},
        current={"reduced": False}, previous_session=previous_trading_day,
        read_day=lambda d: rn._thin_read_day(state, d, BOOK.cid_prefix),
        series=[(D, 100_000.0)],
        positions={}, closes={}, thresholds=LINES)
    return r["episode"], r["K0"]["verdict"]


def _late_send(tmp_path, *, armed=True, targets=None, before_send=None):
    """Decide D in the evening (late market), then run the send in the late window. Returns
    (exit, client, state, plan)."""
    kw = {} if targets is None else {"targets": targets}
    c, deps, state, plan = decided(tmp_path, **kw)
    if armed:
        (state / "AUTO_ARMED").touch()
    to_send_time(c, deps)
    deps.sleep = lambda s: None
    if before_send is not None:
        before_send(c, deps, plan)
    return rn.run_session(BOOK, SPEC, deps), c, state, plan


def _cids(plan):
    return [o["client_order_id"] for o in plan["orders"]]


def _send_json(state):
    return json.loads((state / D.isoformat() / "send.json").read_text())


# --------------------------------------------------------------- late market: sent

def test_late_market_sent_and_filled_is_sent(tmp_path):
    code, c, state, plan = _late_send(tmp_path)
    assert code == rn.EXIT_SENT and len(c.submits()) == len(plan["orders"]) == 2
    sj = _send_json(state)
    assert sj["exit"] == "SENT" and sorted(sj["final"]) == sorted(_cids(plan))
    day, st = _state_of(state)
    assert day["started"] is True
    assert st[0] is True and "exited SENT" in st[1] and "2 of the plan's 2" in st[1]
    ep, k0 = _episode(state)
    assert ep["status"] == "OPEN" and ep["reduced_sessions"] == [D] and k0 == ddm.KILLED
    assert "sent_in_part" not in ep


def test_late_market_partially_filled_is_sent(tmp_path):
    """Paper fills market `day` orders with random partials (team lead 2026-09-29). The set was
    sent; what filled is the account's, and K1-K3 read the broker's own figures."""
    def partial(c, deps, plan):
        c._lookup = lambda cid: ({**c.accepted[cid], "status": "canceled", "filled_qty": "1"}
                                 if cid in c.accepted else None)
    code, c, state, plan = _late_send(tmp_path, before_send=partial)
    assert code == rn.EXIT_SENT
    sj = _send_json(state)
    assert all(f["filled"] == 1 and f["unfilled"] > 0 for f in sj["final"].values())
    _, st = _state_of(state)
    assert st[0] is True and "unfilled at the deadline" in st[1]
    ep, _ = _episode(state)
    assert ep["status"] == "OPEN" and ep["reduced_sessions"] == [D]


# --------------------------------------------------------------- late market: sent, nothing filled

def _ended(status, filled=lambda cid: 0):
    """A `before_send` under which every accepted order is read back (confirm, then the poll)
    in the final `status` with `filled(cid)` shares filled."""
    def setup(c, deps, plan):
        c._lookup = lambda cid: ({**c.accepted[cid], "status": status,
                                  "filled_qty": str(filled(cid))}
                                 if cid in c.accepted else None)
    return setup


def _record(state):
    """The next decide's whole K-line record over the files run.py wrote."""
    return ddm.thin_stop_record(
        asof=D, session_date=NEXT, drawdown={"status": "HALVE", "asof": D.isoformat()},
        current={"reduced": False}, previous_session=previous_trading_day,
        read_day=lambda d: rn._thin_read_day(state, d, BOOK.cid_prefix),
        series=[(D, 100_000.0)], positions={}, closes={}, thresholds=LINES)


@pytest.mark.parametrize("status", ["canceled", "expired", "rejected"])
def test_late_market_sent_with_nothing_filled_is_not_a_reduced_decision(tmp_path, status):
    """The runner owner's round-2 answer (b), 2026-11-05: sent requires at least one fill. The
    real send exits SENT and every order ends final with 0 shares filled, none still working:
    "sent, nothing filled". The book did not change, so the decided reduced plan is NOT a
    reduced decision: no episode (K0 CLEAR on HALVE), nothing for K1 to compound, K2/K3 N/A
    naming it. Fails on f0bc22d (the commit before it), which read it SENT and opened an
    episode on it."""
    code, c, state, plan = _late_send(tmp_path, before_send=_ended(status))
    assert code == rn.EXIT_SENT and len(c.submits()) == 2
    sj = _send_json(state)
    assert sj["not_final"] == [] and sorted(sj["final"]) == sorted(_cids(plan))
    assert all(f["status"] == status and f["filled"] == 0 for f in sj["final"].values())
    _, st = _state_of(state)
    assert st[0] is False and st[1].startswith("sent, nothing filled"), st
    assert "exited SENT" in st[1] and "the book did not change" in st[1]
    r = _record(state)
    assert r["episode"]["status"] == "NONE" and r["episode"]["reduced_sessions"] == []
    assert r["K0"]["verdict"] == ddm.CLEAR and r["K1"]["verdict"] == ddm.NOT_APPLICABLE
    for k in ("K2", "K3"):
        assert r[k]["verdict"] == ddm.NOT_APPLICABLE and "changed nothing" in r[k]["why"], r[k]
    assert r["send_skip"]["applies"] is False


def test_late_market_fail_in_part_with_nothing_filled_stays_sent_in_part(tmp_path):
    """A FAIL whose `final` shows only 0 shares is NOT "sent, nothing filled": answer (b) names
    a SENT. Here one order is rejected at the POST and the other canceled at 0: the send stays
    sent in part, and it counts. Fails on fa9e101, which read it "sent, nothing filled"."""
    def setup(c, deps, plan):
        cid = next(x for x in _cids(plan) if "-BBB-" in x)
        c._submit = {cid: OrderRejected("403", status=403, client_order_id=cid)}
        _ended("canceled")(c, deps, plan)
    code, c, state, plan = _late_send(tmp_path, before_send=setup)
    assert code == rn.EXIT_FAIL and len(c.accepted) == 1
    sj = _send_json(state)
    assert sj["exit"] == "FAIL" and [f["filled"] for f in sj["final"].values()] == [0]
    _, st = _state_of(state)
    assert st[0] is True and "FAIL after part of the set went" in st[1]
    ep, k0 = _episode(state)
    assert ep["status"] == "OPEN" and list(ep["sent_in_part"]) == [D.isoformat()]
    assert k0 == ddm.KILLED


def test_late_market_fail_with_an_order_of_unknown_fate_is_not_nothing_filled(tmp_path):
    """The review of fa9e101, through the real send: BBB is accepted and canceled at 0 shares,
    AAA is accepted by Alpaca but not found at the confirm read. send.json's `final` holds only
    BBB, at 0, yet AAA may have filled, so the book may have changed. It stays sent in part and
    K0 reads KILLED on a HALVE; fa9e101 read "the book did not change" and K0 CLEAR."""
    def setup(c, deps, plan):
        cid = next(x for x in _cids(plan) if "-AAA-" in x)
        c._submit = {cid: "noconfirm"}
        _ended("canceled")(c, deps, plan)
    code, c, state, plan = _late_send(tmp_path, before_send=setup)
    assert code == rn.EXIT_FAIL and len(c.submits()) == 2
    sj = _send_json(state)
    assert sj["exit"] == "FAIL" and [f["filled"] for f in sj["final"].values()] == [0]
    assert sj["not_final"] == []
    _, st = _state_of(state)
    assert st[0] is True and "FAIL after part of the set went" in st[1]
    ep, k0 = _episode(state)
    assert ep["status"] == "OPEN" and list(ep["sent_in_part"]) == [D.isoformat()]
    assert k0 == ddm.KILLED


def test_late_market_one_order_filled_in_part_and_one_with_nothing_is_sent(tmp_path):
    """A PIN (f0bc22d reads it the same): one share filled is a fill, so the send is SENT and the
    reduced decision counts (partial fills count, as before the round-2 answer)."""
    code, c, state, plan = _late_send(
        tmp_path, before_send=_ended("canceled", lambda cid: 1 if "-AAA-" in cid else 0))
    assert code == rn.EXIT_SENT
    assert sorted(f["filled"] for f in _send_json(state)["final"].values()) == [0, 1]
    _, st = _state_of(state)
    assert st[0] is True and "exited SENT" in st[1]
    assert _episode(state)[0]["reduced_sessions"] == [D]


@pytest.mark.parametrize("status", ["replaced", "done_for_day", "filled"])
def test_late_market_zero_fills_under_another_final_state_are_unmeasured(tmp_path, status):
    """Round-2 answer (b) names canceled, expired and rejected. A 0-share final under another
    state is not read as nothing filled: `replaced` means another order took its place (and may
    have filled); `done_for_day` and a `filled` with 0 shares are states the runner's day
    orders are not known to reach. UNMEASURED, naming it. Fails on f0bc22d, which read SENT."""
    code, c, state, plan = _late_send(tmp_path, before_send=_ended(status))
    assert code == rn.EXIT_SENT
    _, st = _state_of(state)
    assert isinstance(st, ddm.Unmeasured) and status in str(st) and "0 shares" in str(st), st
    assert _episode(state)[0]["status"] == ddm.UNMEASURED


# --------------------------------------------------------------- late market: not sent

@pytest.mark.parametrize("case", ["dry", "refused"])
def test_late_market_dry_or_refused_is_not_sent(tmp_path, case):
    def dry(c, deps, plan):
        deps.env["DRY_RUN"] = "1"
    code, c, state, _ = _late_send(tmp_path, armed=case == "dry",
                                   before_send=dry if case == "dry" else None)
    assert code == {"dry": rn.EXIT_DRY, "refused": rn.EXIT_REFUSED}[case] and c.submits() == []
    sj = _send_json(state)
    assert sj["exit"] == {"dry": "DRY", "refused": "REFUSED"}[case]
    assert sj["final"] == {} and sj["not_final"] == []
    day, st = _state_of(state)
    assert day["started"] is False
    assert st[0] is False and sj["exit"] in st[1]
    ep, k0 = _episode(state)
    assert ep["status"] == "NONE" and ep["reduced_sessions"] == [] and k0 == ddm.CLEAR


def test_late_market_nothing_to_send_is_not_sent(tmp_path):
    """The plan's only order opens a short, and the name stopped being shortable by the send:
    skipped (team lead 2026-09-28), nothing left, exit NOTHING_TO_SEND, no STARTED."""
    def short_only(asof, holdings, equity, opening):
        return [PositionTarget("BBB", SHORT, weight=-0.05, reason="z=+1"),
                PositionTarget("AAA", FLAT, reason="flat"),
                PositionTarget("CCC", FLAT, reason="flat")]

    def unshortable(c, deps, plan):
        c._assets = {"BBB": {"shortable": False}}
    code, c, state, plan = _late_send(tmp_path, targets=short_only, before_send=unshortable)
    assert code == rn.EXIT_NOTHING and c.submits() == [] and len(plan["orders"]) == 1
    sj = _send_json(state)
    assert sj["exit"] == "NOTHING_TO_SEND" and len(sj["skipped"]) == 1
    _, st = _state_of(state)
    assert st[0] is False and "NOTHING_TO_SEND" in st[1]
    assert _episode(state)[0]["status"] == "NONE"


# --------------------------------------------------------------- late market: FAIL

def test_late_market_fail_whose_final_records_what_went_is_sent_in_part(tmp_path):
    """Items 5 and 10: a rejection skips its symbol and the rest go (team lead 2026-09-28), so
    the send exits FAIL with the rest in `final`. Classified from `final`: sent, in part, and
    the episode names it. Fails on 87ad4e9, which read every FAIL UNMEASURED."""
    def reject_bbb(c, deps, plan):
        cid = next(x for x in _cids(plan) if "-BBB-" in x)
        c._submit = {cid: OrderRejected("403", status=403, client_order_id=cid)}
    code, c, state, plan = _late_send(tmp_path, before_send=reject_bbb)
    assert code == rn.EXIT_FAIL and len(c.accepted) == 1
    sj = _send_json(state)
    assert sj["exit"] == "FAIL" and list(sj["final"]) == list(c.accepted)
    _, st = _state_of(state)
    assert st[0] is True and "FAIL after part of the set went" in st[1]
    assert "1 of the plan's 2" in st[1]
    ep, k0 = _episode(state)
    assert ep["status"] == "OPEN" and ep["reduced_sessions"] == [D] and k0 == ddm.KILLED
    assert list(ep["sent_in_part"]) == [D.isoformat()]


@pytest.mark.parametrize("how", ["noconfirm", "all_rejected"])
def test_late_market_fail_whose_final_records_nothing_is_unmeasured(tmp_path, how):
    """`final` records only orders the confirm read found. When it found none, orders may have
    reached the broker anyway ("noconfirm": both POSTs were accepted), and send.json cannot
    tell that apart from a send whose every order was rejected: UNMEASURED, never NOT SENT."""
    def fail(c, deps, plan):
        c._submit = {cid: ("noconfirm" if how == "noconfirm"
                           else OrderRejected("422", status=422, client_order_id=cid))
                     for cid in _cids(plan)}
    code, c, state, plan = _late_send(tmp_path, before_send=fail)
    assert code == rn.EXIT_FAIL and len(c.submits()) == 2
    sj = _send_json(state)
    assert sj["exit"] == "FAIL" and sj["final"] == {} and sj["not_final"] == []
    _, st = _state_of(state)
    assert isinstance(st, ddm.Unmeasured) and "FAIL" in str(st) and "record no order" in str(st)
    # Round-2 answer (a): orders.jsonl holds a `submit` for each POST, so zero submissions are
    # not proved, and the reason names them.
    assert "2 `submit` event(s)" in str(st)
    ep, k0 = _episode(state)
    assert ep["status"] == ddm.UNMEASURED and k0 == ddm.UNMEASURED


# --------------------------------------------------------------- late market: FAIL before any POST

AFTER_WINDOW = dt.datetime(2026, 9, 29, 15, 59, tzinfo=ET)     # past the 15:52-15:58 window
PRE_POST = ("cutoff", "clock_error")


def _stop_before_first_post(how):
    """A `before_send` that lets the gate's clock read through, then makes `_transmit`'s first
    clock read (the one before every POST; STARTED exists by then) fail (`clock_error`) or
    land past the window (`cutoff`). The real send then exits FAIL having POSTed nothing, and
    writes exactly what it writes in prod: STARTED, one orders.jsonl event, send.json."""
    def setup(c, deps, plan):
        read = c.clock

        def clock():
            if (c.state / D.isoformat() / "STARTED").exists():
                if how == "clock_error":
                    raise RuntimeError("Alpaca clock read failed (test)")
                c._clock = AFTER_WINDOW
            return read()
        c.clock = clock
    return setup


def _fail_before_post(tmp_path, how="cutoff"):
    code, c, state, plan = _late_send(tmp_path, before_send=_stop_before_first_post(how))
    assert code == rn.EXIT_FAIL and c.submits() == []
    sj = _send_json(state)
    assert sj["exit"] == "FAIL" and sj["final"] == {} and sj["not_final"] == []
    return state, plan


def _verify(state, **client):
    """The real post-close reconcile over the runner's own state dir (verify.verify_day, then
    write_outputs, which writes <D>/reconcile.json), on test_verify's GET-only fake client at
    17:30 ET on D. Returns the reconcile.json it wrote."""
    from quantt.session.tests import test_verify as tv
    tv.run(state, tv.FakeClient(**client))
    return json.loads((state / D.isoformat() / "reconcile.json").read_text())


@pytest.mark.parametrize("verified", [False, True])
@pytest.mark.parametrize("how", PRE_POST)
def test_late_market_fail_before_any_post_is_not_sent_proved_by_its_records(tmp_path, how,
                                                                           verified):
    """The runner owner's round-2 answer (a), 2026-11-05: a FAIL whose send.json records no
    order is NOT SENT when the records prove no POST was made. Here the real send stops at the
    clock read before its first POST: orders.jsonl holds that one event and no `submit`. With
    verify's reconcile.json there too (the real verify, after the close) it names no order of
    the session's prefix; the one mention of an order is verify's own refusal of the log line
    ("... for <cid>, which has no submit line"), which is not an order. The decided reduced
    plan therefore opens no episode, and K0 reads CLEAR on HALVE. Fails on 9e83e63, which read
    every FAIL that records no order UNMEASURED."""
    state, plan = _fail_before_post(tmp_path, how)
    log = [json.loads(x) for x in (state / D.isoformat() / "orders.jsonl").read_text().splitlines()]
    assert [e["event"] for e in log] == [how] and log[0]["client_order_id"] in _cids(plan)
    if verified:
        rc = _verify(state)
        assert rc["started"] is True and rc["orders"] == []
        assert any(f"event '{how}' for" in p and "no submit line" in p for p in rc["problems"])
    else:
        assert not (state / D.isoformat() / "reconcile.json").exists()
    day, st = _state_of(state)
    assert not isinstance(st, ddm.Unmeasured), st
    assert st[0] is False and st[1].startswith("not sent: 0 submissions proved by"), st
    for name in ("send.json", "STARTED", "orders.jsonl", "reconcile.json"):
        assert f"{D}/{name}" in st[1], (name, st[1])
    assert ("reconcile.json (started" in st[1]) is verified
    assert ("reconcile.json absent" in st[1]) is (not verified)
    ep, k0 = _episode(state)
    assert ep["status"] == "NONE" and ep["reduced_sessions"] == [] and k0 == ddm.CLEAR


def _append(path, line: bytes):
    with open(path, "ab") as fh:
        fh.write(line + b"\n")


def _edit_reconcile(state, **kw):
    f = state / D.isoformat() / "reconcile.json"
    f.write_text(json.dumps({**json.loads(f.read_text()), **kw}))


WEAKER = {
    # orders.jsonl: missing, unreadable, empty, holding a submit or an event that needs one
    "log missing": (lambda s, p: (s / D.isoformat() / "orders.jsonl").unlink(),
                    "no 2026-09-29/orders.jsonl"),
    "log line not JSON": (lambda s, p: _append(s / D.isoformat() / "orders.jsonl", b'{"event": '),
                          "line 2 is not JSON"),
    "log not UTF-8": (lambda s, p: _append(s / D.isoformat() / "orders.jsonl", b"\xff\xfe"),
                      "not UTF-8"),
    "log empty": (lambda s, p: (s / D.isoformat() / "orders.jsonl").write_bytes(b""),
                  "holds no event"),
    "log holds a submit": (lambda s, p: _append(
        s / D.isoformat() / "orders.jsonl", json.dumps(
            {"event": "submit", "client_order_id": _cids(p)[0], "symbol": "AAA", "side": "buy",
             "qty": 1}).encode()), "1 `submit` event(s)"),
    "log holds an event that follows a submit": (lambda s, p: _append(
        s / D.isoformat() / "orders.jsonl", json.dumps(
            {"event": "accepted", "client_order_id": _cids(p)[0]}).encode()),
        "'accepted' event with no `submit`"),
    # reconcile.json: a session order at the broker, any order of the prefix, unreadable,
    # not written with STARTED, an order row
    "reconcile names a plan order at Alpaca": (lambda s, p: _verify(s, orders=[
        _vorder("AAA", "buy", 10, _cids(p)[0])]), "names order(s) of the session's prefix"),
    "reconcile names another order of the prefix": (lambda s, p: _verify(s, orders=[
        _vorder("ZZZ", "buy", 10, "cef-20260929-ZZZ-1")]), "cef-20260929-ZZZ-1"),
    "reconcile not JSON": (lambda s, p: (s / D.isoformat() / "reconcile.json").write_bytes(b"{"),
                           "reconcile.json is not JSON"),
    "reconcile without STARTED": (lambda s, p: (_verify(s), _edit_reconcile(s, started=False)),
                                  "written with started False"),
    "reconcile with an order row": (lambda s, p: (_verify(s), _edit_reconcile(
        s, orders=[{"client_order_id": "x-1"}])), "lists 1 order row(s)"),
}


def _vorder(sym, side, qty, cid):
    from quantt.session.tests import test_verify as tv
    return tv.order(sym, side, qty, c=cid)


@pytest.mark.parametrize("case", sorted(WEAKER))
def test_late_market_fail_before_any_post_on_weaker_evidence_stays_unmeasured(tmp_path, case):
    """Round-2 answer (a): anything weaker than positive proof of zero submissions stays
    UNMEASURED, fail-closed, naming the record. Each case starts from the real FAIL before the
    first POST (the proved case above) and takes one piece of the proof away. The UNMEASURED
    status (and the episode's) is a PIN: 9e83e63 read every one of these UNMEASURED too, since
    it read every FAIL that records no order so (checked with the reason assertion removed).
    The named reason is new and fails there."""
    state, plan = _fail_before_post(tmp_path)
    damage, want = WEAKER[case]
    damage(state, plan)
    _, st = _state_of(state)
    assert isinstance(st, ddm.Unmeasured), (case, st)
    assert "record no order" in str(st) and want in str(st), (case, str(st))
    ep, k0 = _episode(state)
    assert ep["status"] == ddm.UNMEASURED and k0 == ddm.UNMEASURED


# --------------------------------------------------------------- late market: records disagree

def test_late_market_sent_with_started_missing_is_unmeasured(tmp_path):
    code, _, state, _ = _late_send(tmp_path)
    assert code == rn.EXIT_SENT
    (state / D.isoformat() / "STARTED").unlink()
    _, st = _state_of(state)
    assert isinstance(st, ddm.Unmeasured) and "no STARTED" in str(st)
    assert _episode(state)[0]["status"] == ddm.UNMEASURED


def test_late_market_send_of_another_plan_sha_is_unmeasured(tmp_path):
    code, _, state, _ = _late_send(tmp_path)
    assert code == rn.EXIT_SENT
    f = state / D.isoformat() / "send.json"
    f.write_text(json.dumps({**json.loads(f.read_text()), "plan_sha": "0" * 64}))
    _, st = _state_of(state)
    assert isinstance(st, ddm.Unmeasured) and "plan_sha" in str(st)


def test_a_later_manual_run_refused_over_a_sent_set_is_unmeasured(tmp_path):
    """After a SENT, a manual run in the window is refused (STARTED exists: no set twice,
    rule 2) and its send.json replaces the SENT one. STARTED beside a REFUSED record: whether
    the set went is not established from send.json, so UNMEASURED, never NOT SENT."""
    c, deps, state, plan = decided(tmp_path)
    (state / "AUTO_ARMED").touch()
    to_send_time(c, deps)
    deps.sleep = lambda s: None
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert _send_json(state)["exit"] == "REFUSED"
    _, st = _state_of(state)
    assert isinstance(st, ddm.Unmeasured) and "STARTED" in str(st)


# --------------------------------------------------------------- cls

def _cls(tmp_path, *, armed=True, submit=None):
    c, deps, state, _, _ = make(tmp_path, submit=submit or {})
    if armed:
        (state / "AUTO_ARMED").touch()
    return rn.run_session(BOOK, SPEC, deps), c, state


@pytest.mark.parametrize("case,want_exit,want", [
    ("sent", rn.EXIT_SENT, True),
    ("refused", rn.EXIT_REFUSED, False),
    ("one_rejected", rn.EXIT_FAIL, True),
    ("all_rejected", rn.EXIT_FAIL, True),
])
def test_cls_is_sent_exactly_when_a_set_started(tmp_path, case, want_exit, want):
    """cls writes no send.json: STARTED (before the first order) is the one per-session record
    of the set, so a set that began counts as sent, whatever then failed (drawdown.py's
    `sent`; its run record says what went). Not a mode te4 trades in: paper is late_market."""
    rej = lambda cid: OrderRejected("422", status=422, client_order_id=cid)
    submit = {"one_rejected": {"cef-20260929-BBB-1": rej("cef-20260929-BBB-1")},
              "all_rejected": {c: rej(c) for c in ("cef-20260929-BBB-1",
                                                   "cef-20260929-AAA-1")}}.get(case)
    code, c, state = _cls(tmp_path, armed=case != "refused", submit=submit)
    assert code == want_exit
    day, st = _state_of(state, reduced=False)
    assert day["send"] is None and "execution" not in day["plan"]
    assert day["started"] is want and st[0] is want and "cls" in st[1]


# --------------------------------------------------------------- shapes the runner cannot reach

A, B = "cef-20260929-AAA-1", "cef-20260929-BBB-1"
FILLED = {"status": "filled", "filled": 10, "unfilled": 0, "filled_avg_price": "10.0"}


def _day(exit_, *, started, final=None, not_final=(), extra=None):
    plan = {"execution": "late_market", "plan_sha": "s", "refusals": [],
            "orders": [{"client_order_id": A}, {"client_order_id": B}]}
    send = {"plan_sha": "s", "exit": exit_, "skipped": [], "final": dict(final or {}),
            "not_final": list(not_final), **(extra or {})}
    return {"plan": plan, "send": send, "started": started}


@pytest.mark.parametrize("day,want", [
    # Accepted and confirmed, still working at the poll's deadline: sent.
    (_day("SENT", started=True, not_final=[A, B]), True),
    (_day("FAIL", started=True, not_final=[A]), True),
    # Records that contradict themselves or the plan: UNMEASURED, naming the record.
    (_day("SENT", started=True), "record no order"),
    (_day("SENT", started=True, final={"cef-20260929-ZZZ-1": FILLED}), "does not hold"),
    (_day("DRY", started=False, final={A: FILLED}), "contradicts itself"),
    (_day("PREVIEW", started=False), "not one a send writes"),
    (_day("SENT", started=True, final={A: FILLED}, extra={"final": None}), "no `final`"),
    (_day("SENT", started=True, final={A: FILLED}, extra={"not_final": None}), "no `not_final`"),
    (_day("FAIL", started=False, final={A: FILLED}), "no STARTED"),
    # A FAIL that records no order, from a reader that did not read orders.jsonl and
    # reconcile.json: zero submissions cannot be proved (round-2 answer (a)).
    (_day("FAIL", started=True), "did not read"),
    # Round-2 answer (b): an order final at 0 shares beside one still working at the deadline
    # (which may yet fill) stays SENT, as the first review defined it (a PIN); a `final` entry
    # without a whole-number `filled` cannot say whether anything filled.
    (_day("SENT", started=True, not_final=[B],
          final={A: {**FILLED, "status": "expired", "filled": 0, "unfilled": 10}}), True),
    (_day("SENT", started=True, final={A: {"status": "filled"}}), "not a whole number"),
    (_day("SENT", started=True, final={A: {**FILLED, "filled": True}}), "not a whole number"),
    (_day("SENT", started=True, final={A: {**FILLED, "filled": -1}}), "not a whole number"),
])
def test_records_the_runner_does_not_write_are_never_guessed(day, want):
    """Shapes `_send_planned` does not write, each read as what it says or UNMEASURED, naming
    the record: never SENT or NOT SENT by default. On 87ad4e9 (which read no `final`) the SENT
    with nothing recorded, the stray order and the missing fields read SENT, and the DRY that
    records a fill read NOT SENT; they fail there."""
    if want is True:
        assert ddm._send_state(D, day)[0] is True
    else:
        with pytest.raises(ddm.Unmeasured, match=want):
            ddm._send_state(D, day)
