"""CEF trial 55 (te4): the K0-K3 report lines (quantt/session/drawdown.py `thin_stop_record`), on synthetic records.

results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md §6.3 requires report lines for K0-K3 in the
activation release, "in report mode and tested", and the team lead's ruling of 2026-11-03 on a
short skipped at send ("accept it and label it") needs the label. Every input here is a literal:
a calendar of consecutive sessions, plan.json / send.json dicts per session, an equity series,
positions, closes and thresholds. Each test fails on the code before this commit, which has no
`thin_stop_record`.

K3's run (review fix after 7fcc2b7). The first build's K3 test hand-built the earlier records, and
not in the shape the runner writes them, so it passed with K3 reading one close too far back.
`_chain` now decides session after session as run.py does, storing each record where run.py
stores it, and the K3 tests read those records; a runner-level test does the same on plan.json
files. Those tests fail on 7fcc2b7.

A reduced decision is one whose targets were SENT (§4.2; review fix F2 after 7fcc2b7): a
decided reduced plan whose send did not go opens no episode, earns K1 nothing and is not a
reduced close; one whose send cannot be read leaves the episode UNMEASURED. Those tests fail
on the F3 commit.

K0 and the K1-K3 lines read eod_equity through the session before the as-of, labelled one
session stale (team lead's ruling 2026-11-03: at the 22:00 decide the as-of's row is never
there). `read_through` None is the as-of reading the earlier tests pin; the read-through tests
fail on the F2 commit (a323971), which has no `read_through`.

The send-skip label (review fix F3 after 7fcc2b7) reads whether the send went (`_send_state`:
plan.json's orders and plan_sha, send.json's exit, plan_sha, `final` and `not_final`,
<D>/STARTED). The prior plans and send records here therefore carry the fields run.py writes
(`plan`, `send`, `reader`'s `started`); test_thin_send_state.py checks that shape against the
records the real send writes. The tests of a send that did not go, or whose outcome is not
established, fail on the F1 commit, which labelled a refused or dry send's list a lost short.
A FAILed send whose `final` records what went is a reduced decision sent in part (the runner
owner's review 2026-11-04, items 5 and 10); that test fails on 87ad4e9.

The runner's side (plan.json carries `thin_stops` only with the key set, and the label read from
the previous session's send.json) is in tests/test_trade_eligible_runner.py.
"""
import datetime as dt
import json

import pytest

from quantt.session import drawdown as ddm

D0 = dt.date(2026, 1, 5)
CAL = [D0 + dt.timedelta(days=i) for i in range(400)]       # synthetic sessions, one a day
SESSION = CAL[300]                                          # this decide's session
ASOF = CAL[299]                                             # its as-of: the session before
LINES = {"thin_k1_episode_drawdown": 0.10, "thin_k2_max_name_frac": 0.9,
         "thin_k3_net_run": 0.25, "thin_k3_net_once": 0.8, "thin_k3_run_sessions": 3}
OK = {"status": "OK", "asof": ASOF.isoformat()}


def prev(d):
    return CAL[CAL.index(d) - 1]


def back(k):
    """The session k sessions before SESSION."""
    return CAL[300 - k]


ORDER = {"symbol": "A", "side": "buy", "qty": 10, "client_order_id": "cef-test-A"}
SHA = "sha-test"


def plan(reduced=False, *, refusals=(), execution="late_market", k3=None, key=True, orders=(),
         sha=SHA):
    """A prior plan.json as run.py writes it: its `orders` and `plan_sha` are what its send.json
    is matched against (`drawdown._send_state`); with no orders no send runs."""
    p = {"refusals": list(refusals), "execution": execution, "orders": list(orders),
         "plan_sha": sha}
    if key:
        p["thin_session"] = {"reduced": reduced}
        # A decide with the key set always records its K3 line: N/A when the session before it
        # was not a reduced one.
        p["thin_stops"] = {"K3": k3 if k3 is not None else {"verdict": ddm.NOT_APPLICABLE}}
    return p


FILLED = {"status": "filled", "filled": 10, "unfilled": 0, "filled_avg_price": "10.0"}


def send(exit="SENT", *, skipped=(), sha=SHA, final=None, not_final=()):
    """A send.json as `_send_planned` writes it (the fields read here). `final` / `not_final`
    are `_poll_final`'s: only orders Alpaca accepted and the confirm read found. Unless given,
    a SENT or FAIL send records ORDER filled, and any other exit records nothing, as run.py
    writes them."""
    if final is None:
        final = {ORDER["client_order_id"]: dict(FILLED)} if exit in ("SENT", "FAIL") else {}
    return {"plan_sha": sha, "exit": exit, "skipped": list(skipped), "final": dict(final),
            "not_final": list(not_final)}


def reader(days: dict, default="plain"):
    """read_day over `days` {session: {"plan", "send", "started"}}; other sessions get a plan
    with the key set and nothing reduced ("plain"), the key absent ("absent"), or no plan.json
    ("missing"). `started` (<D>/STARTED exists), unless given, is what run.py leaves: True
    exactly when a send went or failed part-way (exit SENT or FAIL)."""
    def read(d):
        if d in days:
            x = days[d]
            sd = x.get("send")
            went = isinstance(sd, dict) and sd.get("exit") in ("SENT", "FAIL")
            started = x.get("started", went)
            return {"plan": x.get("plan"), "send": sd, "started": started}
        if default == "plain":
            return {"plan": plan(), "send": None, "started": False}
        if default == "absent":
            return {"plan": plan(key=False), "send": None, "started": False}
        return {"plan": None, "send": None, "started": False}
    return read


def record(days=None, *, default="plain", dd=None, current=None, series=None, positions=None,
           closes=None, lines=None, **kw):
    return ddm.thin_stop_record(
        asof=ASOF, session_date=SESSION, drawdown=dd or OK, current=current or {"reduced": False},
        previous_session=prev, read_day=reader(days or {}, default),
        series=series if series is not None else [(ASOF, 100_000.0)],
        positions=positions or {}, closes=closes or {}, thresholds=lines or LINES, **kw)


# --------------------------------------------------------------- the episode and K0

def test_no_reduced_decision_reads_no_episode_and_nothing_applies():
    r = record()
    assert r["report_only"] is True
    assert r["episode"]["status"] == "NONE" and r["episode"]["reduced_sessions"] == []
    assert r["K0"]["verdict"] == ddm.CLEAR
    assert r["K1"]["verdict"] == r["K2"]["verdict"] == r["K3"]["verdict"] == ddm.NOT_APPLICABLE
    assert r["send_skip"]["applies"] is False


@pytest.mark.parametrize("status,want", [("HALVE", ddm.KILLED), ("KILL", ddm.KILLED),
                                         ("OK", ddm.CLEAR), ("UNMEASURED", ddm.CLEAR)])
def test_k0_kills_on_halve_or_kill_during_an_open_episode(status, want):
    r = record({back(5): {"plan": plan(True)}}, dd={"status": status, "asof": "x"})
    assert r["episode"]["status"] == "OPEN" and r["episode"]["reduced_sessions"] == [back(5)]
    assert r["K0"]["verdict"] == want


@pytest.mark.parametrize("k,want", [(62, "OPEN"), (63, "NONE")])
def test_an_episode_is_open_for_62_sessions_after_its_last_reduced_decision(k, want):
    """§4.2: completed 63 sessions after its last reduced decision with no new one."""
    r = record({back(k): {"plan": plan(True)}}, dd={"status": "HALVE", "asof": "x"})
    assert r["episode"]["status"] == want
    assert r["K0"]["verdict"] == (ddm.KILLED if want == "OPEN" else ddm.CLEAR)


def test_runs_fewer_than_63_sessions_apart_merge_into_one_episode():
    r = record({back(10): {"plan": plan(True)}, back(70): {"plan": plan(True)},
                back(132): {"plan": plan(True)}, back(200): {"plan": plan(True)}})
    assert r["episode"]["reduced_sessions"] == sorted([back(10), back(70), back(132)])


def test_a_missing_or_unreadable_record_reads_unmeasured_and_k0_cannot_clear_a_halve():
    for days, default in (({}, "missing"),
                          ({back(3): {"plan": None}}, "plain")):
        r = record(days, default=default, dd={"status": "HALVE", "asof": "x"})
        assert r["episode"]["status"] == ddm.UNMEASURED
        assert r["K0"]["verdict"] == ddm.UNMEASURED
        assert r["K1"]["verdict"] == ddm.UNMEASURED
    # The as-of session's own record missing: whether K2, K3 and the send label apply is unknown.
    r = record({}, default="missing")
    assert r["K2"]["verdict"] == r["K3"]["verdict"] == ddm.UNMEASURED
    assert r["send_skip"]["applies"] == ddm.UNMEASURED
    assert any("SEND SKIP" in x and "UNMEASURED" in x for x in ddm.thin_stop_lines(r))

    def bad(d):
        raise ValueError("Expecting value: line 1 column 1 (char 0)")
    r = ddm.thin_stop_record(asof=ASOF, session_date=SESSION, drawdown=OK, current={},
                             previous_session=prev, read_day=bad, series=[], positions={},
                             closes={}, thresholds=LINES)
    assert r["episode"]["status"] == ddm.UNMEASURED and "ValueError" in r["episode"]["why"]


def test_a_session_with_no_record_is_a_named_gap_that_blinds_only_the_stops_that_read_it():
    """The runner owner's review (2026-11-04), item 5. A session with no plan.json, no send.json
    and no STARTED (the runner did not run, or its decide failed before writing a plan) is a
    NAMED GAP. It makes UNMEASURED only the stops whose read window holds it, not the whole
    walk for 63 sessions. On 87ad4e9 every case below read the whole episode UNMEASURED (K0
    could not read KILLED, K1 nothing, for up to 63 sessions), and fails here."""
    halve = {"status": "HALVE", "asof": "x"}
    pos, eq = {"A": 1000, "B": -400}, [(ASOF, 50_000.0)]    # K2 0.2, K3 net 0.04: no run
    # A gap inside the open episode's K1 window: the episode is still OPEN (a gap can only add a
    # reduced decision), K0 reads KILLED on HALVE, K1 is UNMEASURED naming the gap, and K2/K3
    # read the as-of's close (a reduced one) as usual.
    days = {back(1): {"plan": plan(True)}, back(5): {"plan": plan(True)},
            back(30): {"plan": None}}
    r = record(days, dd=halve, positions=pos, closes=PRICES, series=eq)
    ep = r["episode"]
    assert ep["status"] == "OPEN" and ep["gaps"] == [back(30)], ep
    assert ep["reduced_sessions"] == [back(5), back(1)]
    assert r["K0"]["verdict"] == ddm.KILLED
    assert r["K1"]["verdict"] == ddm.UNMEASURED and str(back(30)) in r["K1"]["why"]
    assert r["K2"]["stat"] == pytest.approx(0.2) and r["K2"]["verdict"] == ddm.CLEAR
    assert r["K3"]["net"] == pytest.approx(0.04) and r["K3"]["verdict"] == ddm.CLEAR
    # A gap 62 sessions before the oldest known reduced decision is still in K1's window (it
    # might extend the episode back); the walk reads past it.
    r = record({back(20): {"plan": plan(True)}, back(70): {"plan": None}}, dd=halve)
    assert r["episode"]["status"] == "OPEN" and r["episode"]["gaps"] == [back(70)]
    assert r["K0"]["verdict"] == ddm.KILLED and r["K1"]["verdict"] == ddm.UNMEASURED
    # No reduced decision known within 62 sessions and a gap there: the episode state is
    # UNMEASURED, so K0 cannot read CLEAR on HALVE; K1 too (the gap's day is read). K2/K3 and
    # the send skip read the as-of session, a full one: N/A, as without the gap.
    r = record({back(30): {"plan": None}}, dd=halve, positions=pos, closes=PRICES)
    assert r["episode"]["status"] == ddm.UNMEASURED and str(back(30)) in r["episode"]["why"]
    assert r["K0"]["verdict"] == ddm.UNMEASURED and r["K1"]["verdict"] == ddm.UNMEASURED
    assert r["K2"]["verdict"] == r["K3"]["verdict"] == ddm.NOT_APPLICABLE
    assert r["send_skip"]["applies"] is False
    # A gap 63 sessions back is outside every window: never read.
    r = record({back(63): {"plan": None}}, dd=halve)
    assert r["episode"]["status"] == "NONE" and "gaps" not in r["episode"]


def test_a_gap_on_the_asof_session_blinds_k2_k3_and_the_send_skip_not_k0_or_k1():
    """The as-of session's own record is missing: K2, K3 and the send skip read its close and
    its send, so they read UNMEASURED, named. Its earning day is this session, not read yet, so
    K1 is measured on the known episode, and K0 reads KILLED on it. Read through the session
    before the as-of (the 22:00 decide), a gap there is outside K1's window too. Fails on
    87ad4e9, which read the whole episode UNMEASURED."""
    halve = {"status": "HALVE", "asof": "x"}
    series = _series({6: 100.0, 5: 95.0}) + [(ASOF, 95.0)]
    r = record({back(1): {"plan": None}, back(6): {"plan": plan(True)}}, dd=halve,
               series=series)
    assert r["episode"]["status"] == "OPEN" and r["episode"]["gaps"] == [ASOF]
    assert r["K0"]["verdict"] == ddm.KILLED
    assert r["K1"]["earning_days"] == 1 and r["K1"]["drawdown"] == pytest.approx(0.05)
    for k in ("K2", "K3"):
        assert r[k]["verdict"] == ddm.UNMEASURED and f"no record for the session {ASOF}" in \
            r[k]["why"], r[k]
    assert r["send_skip"]["applies"] == ddm.UNMEASURED
    # Read through back(2): a gap on back(2) earns on the as-of, after the read-through date.
    r = record({back(2): {"plan": None}, back(6): {"plan": plan(True)}}, dd=halve,
               series=_series({6: 100.0, 5: 95.0, 2: 95.0}), read_through=back(2))
    assert r["episode"]["gaps"] == [back(2)]
    assert r["K1"]["verdict"] == ddm.CLEAR and r["K1"]["earning_days"] == 1


def test_a_session_with_a_send_or_a_started_and_no_plan_is_not_a_gap():
    """Something recorded as sent with no plan on record cannot be read as a session the runner
    skipped: the whole episode reads UNMEASURED, naming what is there."""
    for extra, word in (({"send": send()}, "a send.json"), ({"started": True}, "a STARTED")):
        r = record({back(3): {"plan": None, **extra}, back(5): {"plan": plan(True)}},
                   dd={"status": "HALVE", "asof": "x"})
        assert r["episode"]["status"] == ddm.UNMEASURED and word in r["episode"]["why"]
        assert r["K0"]["verdict"] == ddm.UNMEASURED and r["K1"]["verdict"] == ddm.UNMEASURED


def test_a_session_decided_with_the_key_absent_ends_the_walk():
    r = record({back(3): {"plan": plan(key=False)}, back(5): {"plan": plan(True)}},
               dd={"status": "KILL", "asof": "x"})
    assert r["episode"]["status"] == "NONE" and r["K0"]["verdict"] == ddm.CLEAR
    assert "key absent" in r["episode"]["why"]


def test_a_refused_reduced_plan_is_not_a_reduced_decision():
    r = record({back(4): {"plan": plan(True, refusals=[{"gate": "data", "detail": "x"}])}},
               dd={"status": "HALVE", "asof": "x"})
    assert r["episode"]["status"] == "NONE"


def test_a_reduced_decision_whose_send_did_not_go_opens_no_episode():
    """Review fix F2 after 7fcc2b7. §4.2: a reduced decision is one whose reduced build ran
    "and its targets were sent". A decided reduced plan whose late-market SEND was dry,
    refused, emptied or never ran left the account holding another book: it opens no episode
    (K0 cannot read KILLED on it), and its close is not a reduced close (K2 and K3 N/A, naming
    why). 7fcc2b7 counted it, and fails here."""
    for sd in (send("DRY"), send("REFUSED"), send("NOTHING_TO_SEND"), None):
        days = {back(1): {"plan": plan(True, orders=[ORDER]), "send": sd}}
        r = record(days, dd={"status": "HALVE", "asof": "x"}, positions={"A": 100},
                   closes=PRICES)
        assert r["episode"]["status"] == "NONE" and r["episode"]["reduced_sessions"] == [], sd
        assert r["K0"]["verdict"] == ddm.CLEAR
        assert r["K2"]["verdict"] == r["K3"]["verdict"] == ddm.NOT_APPLICABLE
        assert "was not sent" in r["K3"]["why"], r["K3"]
    # The same plan whose send went is a reduced decision.
    days = {back(1): {"plan": plan(True, orders=[ORDER]), "send": send()}}
    r = record(days, dd={"status": "HALVE", "asof": "x"})
    assert r["episode"]["reduced_sessions"] == [ASOF] and r["K0"]["verdict"] == ddm.KILLED


def test_a_send_that_cannot_be_read_leaves_the_episode_unmeasured_only_on_a_reduced_plan():
    """A decided reduced plan whose send exited FAIL with nothing in send.json's `final` or
    `not_final`: whether any order went is not established (an accepted POST the confirm read
    did not find is in neither), so the episode is UNMEASURED, named (7fcc2b7 read it OPEN). A
    FAIL on a full session's send changes nothing here: only a reduced plan's send is read."""
    fail_empty = send("FAIL", final={})
    r = record({back(3): {"plan": plan(True, orders=[ORDER]), "send": fail_empty}},
               dd={"status": "HALVE", "asof": "x"})
    assert r["episode"]["status"] == ddm.UNMEASURED and "FAIL" in r["episode"]["why"]
    assert r["K0"]["verdict"] == ddm.UNMEASURED and r["K1"]["verdict"] == ddm.UNMEASURED
    r = record({back(3): {"plan": plan(False, orders=[ORDER]), "send": fail_empty}},
               dd={"status": "HALVE", "asof": "x"})
    assert r["episode"]["status"] == "NONE" and r["K0"]["verdict"] == ddm.CLEAR


def test_a_failed_send_whose_final_records_what_went_is_a_reduced_decision_sent_in_part():
    """The runner owner's review (2026-11-04), items 5 and 10: a FAILed send whose send.json
    `final` records what went is classified from `final`. Part of the reduced book went (a
    rejected order skips its symbol and the rest are sent, team lead 2026-09-28), so the
    account holds it: the session is a reduced decision, the episode is OPEN and names it
    `sent_in_part`, K0 can read KILLED on it, and K2/K3 read the close it left. 87ad4e9 read
    every FAIL UNMEASURED, and fails here."""
    two = [ORDER, {**ORDER, "symbol": "B", "side": "sell", "client_order_id": "cef-test-B"}]
    days = {back(1): {"plan": plan(True, orders=two), "send": send("FAIL")}}
    r = record(days, dd={"status": "HALVE", "asof": "x"}, positions={"A": 100},
               closes=PRICES, series=[(ASOF, 50_000.0)])
    ep = r["episode"]
    assert ep["status"] == "OPEN" and ep["reduced_sessions"] == [ASOF], ep
    assert list(ep["sent_in_part"]) == [str(ASOF)]
    assert "FAIL" in ep["sent_in_part"][str(ASOF)] and "1 of the plan's 2" in \
        ep["sent_in_part"][str(ASOF)]
    assert r["K0"]["verdict"] == ddm.KILLED
    assert r["K2"]["stat"] == pytest.approx(0.02) and r["K3"]["net"] == pytest.approx(0.02)
    assert r["send_skip"]["applies"] is True and r["send_skip"]["lost_short"] is False
    # A send that went whole names nothing sent in part.
    r = record({back(1): {"plan": plan(True, orders=[ORDER]), "send": send()}})
    assert r["episode"]["status"] == "OPEN" and "sent_in_part" not in r["episode"]


# --------------------------------------------------------------- K1

def _k1_days():
    """Reduced decisions on the sessions 6 and 4 back: their earning days are 5 and 3 back."""
    return {back(6): {"plan": plan(True)}, back(4): {"plan": plan(True)}}


def _series(eq_by_k: dict):
    return sorted((back(k), v) for k, v in eq_by_k.items())


def test_k1_compounds_the_episodes_earning_days_and_trips_at_its_line():
    # earning day 5 back: 100 -> 95 (-5%); earning day 3 back: 96 -> 90.24 (-6%).
    series = _series({6: 100.0, 5: 95.0, 4: 96.0, 3: 90.24, 1: 90.0})
    r = record(_k1_days(), series=series + [(ASOF, 90.0)])
    want = 1.0 - (0.95 * 0.94)
    assert r["K1"]["earning_days"] == 2
    assert r["K1"]["drawdown"] == pytest.approx(want, abs=1e-8)
    assert r["K1"]["verdict"] == ddm.TRIPPED                       # 0.107 >= 0.10
    r = record(_k1_days(), series=series + [(ASOF, 90.0)],
               lines={**LINES, "thin_k1_episode_drawdown": 0.11})
    assert r["K1"]["verdict"] == ddm.CLEAR
    r = record(_k1_days(), series=series + [(ASOF, 90.0)],
               lines={**LINES, "thin_k1_episode_drawdown": None})
    assert r["K1"]["verdict"] == ddm.UNMEASURED and r["K1"]["drawdown"] == pytest.approx(want)


def test_k1_does_not_compound_the_earning_day_of_a_reduced_decision_that_was_not_sent():
    """Review fix F2: the reduced decision on back(4) has orders and its send was dry, so the
    account held another book on its earning day (back(3)): K1 compounds back(5)'s day only,
    -5%, under the 10% line. 7fcc2b7 compounded both (0.95 x 0.94, 10.7%: TRIPPED), and fails
    here."""
    series = _series({6: 100.0, 5: 95.0, 4: 96.0, 3: 90.24, 1: 90.0}) + [(ASOF, 90.0)]
    days = _k1_days()
    days[back(4)] = {"plan": plan(True, orders=[ORDER]), "send": send("DRY")}
    r = record(days, series=series)
    assert r["episode"]["reduced_sessions"] == [back(6)]
    assert r["K1"]["earning_days"] == 1
    assert r["K1"]["drawdown"] == pytest.approx(0.05, abs=1e-8)
    assert r["K1"]["verdict"] == ddm.CLEAR
    # Sent, it is compounded (the test above).
    days[back(4)] = {"plan": plan(True, orders=[ORDER]), "send": send()}
    assert record(days, series=series)["K1"]["earning_days"] == 2


def _k1_case_final_at_zero(exit_):
    """The K1 days with back(4)'s reduced decision sent, exit `exit_`, its only order in
    send.json's `final` canceled with 0 shares filled."""
    series = _series({6: 100.0, 5: 95.0, 4: 96.0, 3: 90.24, 1: 90.0}) + [(ASOF, 90.0)]
    days = _k1_days()
    none = {"status": "canceled", "filled": 0, "unfilled": ORDER["qty"],
            "filled_avg_price": None}
    days[back(4)] = {"plan": plan(True, orders=[ORDER]),
                     "send": send(exit_, final={ORDER["client_order_id"]: none})}
    return record(days, series=series)


def test_k1_does_not_compound_the_earning_day_of_a_reduced_decision_that_filled_nothing():
    """The runner owner's round-2 answer (b), 2026-11-05: sent requires at least one fill. The
    reduced decision on back(4) went to the broker (STARTED, exit SENT) and its only order ended
    canceled with 0 shares filled: the book did not change, so it is not a reduced decision for
    K1's compounding. K1 compounds back(5)'s day only, -5%, under the 10% line. f0bc22d (the
    commit before it) compounded both (0.95 x 0.94, 10.7%: TRIPPED), and fails here."""
    r = _k1_case_final_at_zero("SENT")
    assert r["episode"]["reduced_sessions"] == [back(6)]
    assert r["K1"]["earning_days"] == 1
    assert r["K1"]["drawdown"] == pytest.approx(0.05, abs=1e-8)
    assert r["K1"]["verdict"] == ddm.CLEAR


def test_k1_compounds_the_earning_day_of_a_fail_whose_final_shows_zero_fills():
    """Answer (b) names a SENT. A FAIL's `final` leaves out any order of unknown fate, so zeros
    there cannot say the book did not change: the reduced decision still counts, and K1
    compounds its day (0.95 x 0.94, 10.7%: TRIPPED). fa9e101 read 5%, CLEAR, and fails here."""
    r = _k1_case_final_at_zero("FAIL")
    assert r["K1"]["earning_days"] == 2
    assert r["K1"]["verdict"] == ddm.TRIPPED


def test_k1_reads_unmeasured_on_a_missing_equity_row_and_never_reads_past_the_asof():
    r = record(_k1_days(), series=_series({6: 100.0, 5: 95.0, 4: 96.0}) + [(ASOF, 90.0)])
    assert r["K1"]["verdict"] == ddm.UNMEASURED and str(back(3)) in r["K1"]["why"]
    r = record(_k1_days(), series="no eod_equity.csv")
    assert r["K1"]["verdict"] == ddm.UNMEASURED and "no eod_equity.csv" in r["K1"]["why"]
    # A reduced decision on the as-of session earns on THIS session, after the as-of: not counted.
    r = record({back(1): {"plan": plan(True)}}, series=[(ASOF, 90.0)])
    assert r["K1"]["earning_days"] == 0 and r["K1"]["verdict"] == ddm.CLEAR
    with pytest.raises(AssertionError, match="lookahead"):
        record(_k1_days(), series=[(ASOF, 1.0), (SESSION, 1.0)])


# --------------------------------------------------------------- K2, K3

PRICES = {"A": 10.0, "B": 20.0, "C": 5.0}


def test_k2_and_k3_read_the_close_after_a_reduced_decision():
    days = {back(1): {"plan": plan(True)}}
    pos = {"A": 4000, "B": -1000, "C": 0}                  # +40k, -20k on 50k of equity
    r = record(days, positions=pos, closes=PRICES, series=[(ASOF, 50_000.0)])
    assert r["K2"]["stat"] == pytest.approx(0.8) and r["K2"]["verdict"] == ddm.CLEAR
    assert r["K3"]["net"] == pytest.approx(0.4) and r["K3"]["run"] == 1
    assert r["K3"]["verdict"] == ddm.CLEAR
    r = record(days, positions={"A": 5000, "B": -500}, closes=PRICES, series=[(ASOF, 50_000.0)])
    assert r["K2"]["stat"] == pytest.approx(1.0) and r["K2"]["verdict"] == ddm.TRIPPED
    # net exactly 0.8: AT the once line is not above it, and one close is not a run of three.
    assert r["K3"]["net"] == pytest.approx(0.8) and r["K3"]["verdict"] == ddm.CLEAR


def _chain(kinds: str, nets: list, lines=None):
    """Decide session after session exactly as run.py does, and return each decide's K3.

    Sessions S[0], S[1], ...: S[0] was decided with the key absent; S[j] (j >= 1) is a reduced
    decision ("R") or a full one ("F") as `kinds[j - 1]` says. The decide for S[j + 1] runs on
    as-of S[j], with the account's book at the S[j] close worth `nets[j - 1]` of equity, net;
    its record goes into plan(S[j + 1])["thin_stops"], as run.py `_thin_stops` stores it. So
    plan(X).thin_stops.K3 judges the close of the session BEFORE X: the records K3 reads back
    are the runner's own, never hand-built (the first build's test hand-built them and could
    not see the off-by-one; both reviews of 7fcc2b7)."""
    S = CAL[200:200 + len(kinds) + 2]
    days = {S[0]: {"plan": plan(key=False)}}
    for j, kind in enumerate(kinds, start=1):
        days[S[j]] = {"plan": plan(kind == "R")}
    days[S[-1]] = {"plan": plan(False)}
    out = []
    for j in range(1, len(kinds) + 1):
        asof, sd = S[j], S[j + 1]
        r = ddm.thin_stop_record(
            asof=asof, session_date=sd, drawdown=OK, current={"reduced": False},
            previous_session=prev, read_day=reader(days), series=[(asof, 100.0)],
            positions={"A": round(nets[j - 1] * 10)}, closes={"A": 10.0},
            thresholds=lines or LINES)
        days[sd]["plan"]["thin_stops"] = r
        assert r["K3"]["session"] == asof
        out.append(r["K3"])
    return out


def _runs(k3s):
    return [(k.get("run"), k["verdict"]) for k in k3s]


def test_k3_trips_on_exactly_the_third_reduced_close_in_a_row_above_its_run_line():
    """§6.3: above the run line (0.25) on 3 consecutive reduced sessions. Fails on 7fcc2b7,
    which read 1, 1, 2 here: it skipped the as-of session's own plan, the one holding the close
    before the as-of, and tripped a close late (1, 1, 2, 3 on four closes)."""
    k3 = _chain("RRR", [0.4, 0.4, 0.4])
    assert _runs(k3) == [(1, ddm.CLEAR), (2, ddm.CLEAR), (3, ddm.TRIPPED)]
    assert _runs(_chain("RRR", [0.3, 0.3, 0.4]))[-1] == (3, ddm.TRIPPED)


def test_k3s_run_length_is_the_specs_never_a_constant_here():
    """The runner owner's review (2026-11-04), item 9: K3's run length is the spec's
    `risk.thin_k3_run_sessions`, passed in with the lines; drawdown.py holds no constant. At 2
    the run trips on the second close above the line; at 4 the third does not. Without it K3
    reads UNMEASURED, naming it (no default); a value the registry would refuse raises. Fails on
    8527488, whose THIN_K3_RUN = 3 ignored the thresholds."""
    assert not hasattr(ddm, "THIN_K3_RUN")
    k3 = _chain("RRR", [0.4, 0.4, 0.4], {**LINES, "thin_k3_run_sessions": 2})
    # The count stops at the run length: the third close reads a run of 2, TRIPPED.
    assert _runs(k3) == [(1, ddm.CLEAR), (2, ddm.TRIPPED), (2, ddm.TRIPPED)]
    assert k3[0]["run_sessions"] == 2
    k3 = _chain("RRRR", [0.4, 0.4, 0.4, 0.4], {**LINES, "thin_k3_run_sessions": 4})
    assert _runs(k3) == [(1, ddm.CLEAR), (2, ddm.CLEAR), (3, ddm.CLEAR), (4, ddm.TRIPPED)]
    lines = {k: v for k, v in LINES.items() if k != "thin_k3_run_sessions"}
    r = record({back(1): {"plan": plan(True)}}, positions={"A": 3000}, closes=PRICES,
               series=[(ASOF, 50_000.0)], lines=lines)
    assert r["K3"]["net"] == pytest.approx(0.6) and r["K3"]["verdict"] == ddm.UNMEASURED
    assert "thin_k3_run_sessions" in r["K3"]["why"]
    for bad in (1, 3.0, True):
        with pytest.raises(ValueError, match="thin_k3_run_sessions"):
            record(lines={**LINES, "thin_k3_run_sessions": bad})


def test_k3_does_not_trip_on_a_run_broken_by_a_close_below_the_line():
    """above, above, below, above is a run of 1 at the last close. Fails on 7fcc2b7, which read
    3 and TRIPPED there: a false kill of the trial (the quant review's chain B)."""
    k3 = _chain("RRRR", [0.4, 0.4, 0.1, 0.4])
    assert _runs(k3) == [(1, ddm.CLEAR), (2, ddm.CLEAR), (0, ddm.CLEAR), (1, ddm.CLEAR)]


def test_a_full_session_between_reduced_closes_does_not_break_the_run():
    """compose.py's `runs_above` runs over reduced decisions only: a full session's close is
    not one of them (its K3 reads N/A) and neither breaks nor extends the run."""
    k3 = _chain("RFRR", [0.4, 0.9, 0.4, 0.4])
    assert _runs(k3) == [(1, ddm.CLEAR), (None, ddm.NOT_APPLICABLE), (2, ddm.CLEAR),
                         (3, ddm.TRIPPED)]


def test_k3_trips_above_the_once_line_and_reads_unmeasured_on_an_unread_earlier_close():
    pos, eq = {"A": 3000, "B": -500}, [(ASOF, 50_000.0)]    # net 20k / 50k = 0.4 > run 0.25
    r = record({back(1): {"plan": plan(True)}}, positions={"A": 5000}, closes=PRICES, series=eq)
    assert r["K3"]["net"] == pytest.approx(1.0) and r["K3"]["verdict"] == ddm.TRIPPED
    # The as-of session's plan holds the K3 of the close before it (back(2)'s, a reduced one).
    for k3, why in (({"verdict": ddm.UNMEASURED, "why": "x", "session": back(2)}, "unmeasured"),
                    ({"net": 0.3, "verdict": ddm.CLEAR, "session": back(3)}, "names the close")):
        days = {back(1): {"plan": plan(True, k3=k3)}, back(2): {"plan": plan(True)}}
        r = record(days, positions=pos, closes=PRICES, series=eq)
        assert r["K3"]["verdict"] == ddm.UNMEASURED and why in r["K3"]["why"], r["K3"]
    # And read as JSON writes it (the session an ISO string), the same close counts.
    days = {back(1): {"plan": plan(True, k3={"net": 0.3, "verdict": ddm.CLEAR,
                                             "session": back(2).isoformat()})},
            back(2): {"plan": plan(True)}}
    assert record(days, positions=pos, closes=PRICES, series=eq)["K3"]["run"] == 2


def test_k3_is_not_clear_on_a_run_the_walk_could_not_finish_reading():
    """Two reduced closes above the run line are read (the as-of's and back(2)'s), and back(2)'s
    own plan holds a K3 above the line for back(3)'s close; back(3)'s record cannot be read, so
    whether that close was a reduced one, the run's third, is unknown. K3 reads UNMEASURED, not
    CLEAR. Fails on 7fcc2b7, which read a run of 2 and CLEAR there. back(3) with no record at
    all (a named gap, the owner's review item 5) is the same for K3, named, while the episode
    reads OPEN on the two reduced decisions it knows."""
    pos, eq = {"A": 3000, "B": -500}, [(ASOF, 50_000.0)]    # net 0.4 > run 0.25
    days = {back(1): {"plan": plan(True, k3={"net": 0.3, "verdict": ddm.CLEAR,
                                             "session": back(2).isoformat()})},
            back(2): {"plan": plan(True, k3={"net": 0.3, "verdict": ddm.CLEAR,
                                             "session": back(3).isoformat()})}}
    read = reader(days)

    def unreadable(d):
        if d == back(3):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return read(d)
    r = ddm.thin_stop_record(asof=ASOF, session_date=SESSION, drawdown=OK,
                             current={"reduced": False}, previous_session=prev,
                             read_day=unreadable, series=eq, positions=pos, closes=PRICES,
                             thresholds=LINES)
    assert r["episode"]["status"] == ddm.UNMEASURED
    assert r["K3"]["run"] == 2 and r["K3"]["verdict"] == ddm.UNMEASURED, r["K3"]
    assert "stopped before the run ended" in r["K3"]["why"]
    days[back(3)] = {"plan": None}                    # no record at all: a named gap
    r = record(days, positions=pos, closes=PRICES, series=eq)
    assert r["episode"]["status"] == "OPEN" and r["episode"]["gaps"] == [back(3)]
    assert r["K3"]["run"] == 2 and r["K3"]["verdict"] == ddm.UNMEASURED, r["K3"]
    assert f"no record for {back(3)}" in r["K3"]["why"]
    # A gap beyond where the run breaks is outside K3's window: back(2)'s close is below the
    # run line, so the run is 1 and CLEAR whatever back(4) was.
    beyond = {back(1): {"plan": plan(True, k3={"net": 0.1, "verdict": ddm.CLEAR,
                                               "session": back(2).isoformat()})},
              back(2): {"plan": plan(True)}, back(4): {"plan": None}}
    r = record(beyond, positions=pos, closes=PRICES, series=eq)
    assert r["episode"]["gaps"] == [back(4)]
    assert r["K3"]["run"] == 1 and r["K3"]["verdict"] == ddm.CLEAR, r["K3"]
    # The same records ending at a plan decided with the key absent: the run is complete, CLEAR.
    days[back(3)] = {"plan": plan(key=False)}
    r = record(days, positions=pos, closes=PRICES, series=eq)
    assert r["K3"]["run"] == 2 and r["K3"]["verdict"] == ddm.CLEAR, r["K3"]


def test_k2_k3_unmeasured_without_equity_a_close_or_a_line_and_n_a_after_a_full_session():
    days = {back(1): {"plan": plan(True)}}
    r = record(days, positions={"A": 1}, closes=PRICES, series=[(back(2), 1.0)])
    assert r["K2"]["verdict"] == r["K3"]["verdict"] == ddm.UNMEASURED
    r = record(days, positions={"Z": 1}, closes=PRICES, series=[(ASOF, 1.0)])
    assert "Z" in r["K2"]["why"]
    r = record(days, positions={"A": 1}, closes=PRICES, series=[(ASOF, 1.0)],
               lines={**LINES, "thin_k2_max_name_frac": None, "thin_k3_net_once": None})
    assert r["K2"]["verdict"] == r["K3"]["verdict"] == ddm.UNMEASURED
    assert r["K2"]["stat"] == pytest.approx(10.0)
    r = record({back(1): {"plan": plan(False)}}, positions={"A": 1}, closes=PRICES)
    assert r["K2"]["verdict"] == r["K3"]["verdict"] == ddm.NOT_APPLICABLE


# --------------------------------------------------------------- read through the previous session

def test_k1_k3_read_through_the_previous_session_labelled_one_session_stale():
    """The team lead's ruling (2026-11-03), applied to the report lines as to K0: at the 22:00
    decide there is no eod_equity row for the as-of, so read through the as-of K1, K2 and K3
    all read UNMEASURED. Read through the session before it (back(2)): K1 compounds the earning
    days whose rows are there and lists the as-of's own as earned, not yet read; K2 and K3 divide
    the as-of close's positions by back(2)'s equity, and say so. Fails on a323971, whose
    `thin_stop_record` takes no `read_through`."""
    below = {"net": 0.1, "verdict": ddm.CLEAR, "session": back(2).isoformat()}
    days = {back(4): {"plan": plan(True)}, back(2): {"plan": plan(True)},
            back(1): {"plan": plan(True, k3=below)}}
    # Earning days: back(3) for back(4) (100 -> 95: read); the as-of for back(2) (earned, its
    # row not there yet); this session for back(1) (not yet earned).
    series = _series({4: 100.0, 3: 95.0, 2: 50_000.0})
    pos = {"A": 4000, "B": -1000}                          # +40k, -20k on 50k: K2 0.8, K3 0.4
    r = record(days, series=series, positions=pos, closes=PRICES, read_through=back(2))
    assert r["read_through"]["date"] == back(2) and r["read_through"]["sessions_stale"] == 1
    assert r["K1"]["earning_days"] == 1 and r["K1"]["drawdown"] == pytest.approx(0.05)
    assert r["K1"]["read_through"] == back(2) and r["K1"]["earned_not_yet_read"] == [ASOF]
    assert r["K2"]["stat"] == pytest.approx(0.8) and r["K2"]["equity_date"] == back(2)
    assert r["K3"]["net"] == pytest.approx(0.4) and r["K3"]["equity_date"] == back(2)
    assert r["K2"]["verdict"] == r["K3"]["verdict"] == ddm.CLEAR
    text = "\n".join(ddm.thin_stop_lines(r))
    assert f"read through {back(2)}, 1 session(s) before the as-of" in text
    # The same series read through the as-of: no row for it, so K2 and K3 are UNMEASURED.
    r = record(days, series=series, positions=pos, closes=PRICES)
    assert r["K2"]["verdict"] == r["K3"]["verdict"] == ddm.UNMEASURED
    assert f"no eod_equity row for {ASOF}" in r["K3"]["why"]


def test_k1_k3_read_the_asofs_own_row_at_the_morning_backstop_and_k0s_date_exactly():
    """The runner owner's review (2026-11-04), item 6, on the team lead's freshest-row ruling of
    the same day. At the morning backstop K0 reads the as-of's own row, so the K1-K3 lines read
    through the as-of too: K1 counts the as-of's own earning day (nothing is left unread), K2
    and K3 divide by the as-of's own equity (`equity_date` the as-of, no `equity_note`), and the
    label says 0 sessions stale and why. Read through D-1 (22:00) the same records divide by
    D-1's equity, labelled with an `equity_note`. A K0 record whose read-through date is not the
    lines' is refused: never two dates mixed silently. `equity_date` is recorded whatever the
    read-through. Fails on 69ef368 (its 0-stale label said the as-of's row was not there; it had
    no `equity_note`, no `equity_date` without a read-through, and no check against K0's date)."""
    below = {"net": 0.1, "verdict": ddm.CLEAR, "session": back(2).isoformat()}
    days = {back(4): {"plan": plan(True)}, back(2): {"plan": plan(True)},
            back(1): {"plan": plan(True, k3=below)}}
    # back(4) earns back(3): 100 -> 95; back(2) earns the as-of: 50,000 -> 50,000; back(1)
    # (the as-of session) earns this session, not yet.
    series = _series({4: 100.0, 3: 95.0, 2: 50_000.0, 1: 50_000.0})
    pos = {"A": 4000, "B": -1000}                          # +40k, -20k: K2 0.8, K3 0.4
    k0 = {"status": "OK", "asof": ASOF, "read_through": ASOF,
          "reading": {"stale": {"row_date": ASOF, "sessions": 0}}}
    r = record(days, dd=k0, series=series, positions=pos, closes=PRICES, read_through=ASOF)
    assert r["read_through"]["date"] == ASOF and r["read_through"]["sessions_stale"] == 0
    assert "the as-of's own row" in r["read_through"]["label"]
    assert "not there yet" not in r["read_through"]["label"]
    assert r["K0"]["read_through"] == ASOF and r["K0"]["stale"]["sessions"] == 0
    assert r["K1"]["earning_days"] == 2 and r["K1"]["earned_not_yet_read"] == []
    assert r["K1"]["drawdown"] == pytest.approx(0.05)
    for k, stat in (("K2", 0.8), ("K3", 0.4)):
        assert r[k]["equity_date"] == ASOF and "equity_note" not in r[k], r[k]
        assert r[k].get("stat", r[k].get("net")) == pytest.approx(stat)
    # The 22:00 decide on the same records: D-1's row, labelled, the as-of's day unread.
    k0_eve = {**k0, "read_through": back(2), "reading": {"stale": {"row_date": back(2),
                                                                   "sessions": 1}}}
    r = record(days, dd=k0_eve, series=series[:-1], positions=pos, closes=PRICES,
               read_through=back(2))
    assert r["K1"]["earning_days"] == 1 and r["K1"]["earned_not_yet_read"] == [ASOF]
    for k in ("K2", "K3"):
        assert r[k]["equity_date"] == back(2) and "1 session(s)" in r[k]["equity_note"]
    assert f"equity of {back(2)}" in "\n".join(ddm.thin_stop_lines(r))
    # Never K0's date and another: refused.
    for rt in (back(2), None):
        with pytest.raises(ValueError, match="must read the same row"):
            record(days, dd=k0, series=series[:-1] if rt else series, positions=pos,
                   closes=PRICES, read_through=rt)
    # No read-through at all: the as-of's equity, recorded.
    r = record(days, series=series, positions=pos, closes=PRICES)
    assert r["K2"]["equity_date"] == r["K3"]["equity_date"] == ASOF


def test_read_through_with_no_row_for_it_or_a_row_after_it():
    days = {back(1): {"plan": plan(True)}}
    r = record(days, series=[(back(3), 50_000.0)], positions={"A": 1}, closes=PRICES,
               read_through=back(2))
    assert r["K2"]["verdict"] == r["K3"]["verdict"] == ddm.UNMEASURED
    assert f"no eod_equity row for {back(2)}" in r["K2"]["why"]
    with pytest.raises(AssertionError, match="read-through"):    # no lookahead past it
        record(days, series=[(back(2), 1.0), (ASOF, 1.0)], read_through=back(2))
    with pytest.raises(ValueError, match="lookahead"):
        record(days, read_through=SESSION)


def test_k0s_line_names_the_row_it_read():
    dd = {"status": "HALVE", "asof": ASOF, "read_through": back(2),
          "reading": {"stale": {"row_date": back(2), "sessions": 1}}}
    r = record({back(5): {"plan": plan(True)}}, dd=dd, series=[(back(2), 1.0)],
               read_through=back(2))
    assert r["K0"]["verdict"] == ddm.KILLED and r["K0"]["read_through"] == back(2)
    assert r["K0"]["stale"] == {"row_date": back(2), "sessions": 1}
    line = [x for x in ddm.thin_stop_lines(r) if "K0" in x][0]
    assert f"read through {back(2)}, 1 session(s) stale" in line


# --------------------------------------------------------------- the send-time skip label

def test_the_send_time_skip_after_a_reduced_decision_is_labelled():
    skipped = ["cef-20260105-PDI-x: PDI shortable=False at send; skipped, the rest go"]
    r = record({back(1): {"plan": plan(True, orders=[ORDER]), "send": send(skipped=skipped)}})
    assert r["send_skip"] == {"session": ASOF, "applies": True, "skipped_at_send": skipped,
                              "lost_short": True}
    r = record({back(1): {"plan": plan(True, orders=[ORDER]), "send": send()}})
    assert r["send_skip"]["lost_short"] is False
    no_list = {k: v for k, v in send().items() if k != "skipped"}
    r = record({back(1): {"plan": plan(True, orders=[ORDER]), "send": no_list}})
    assert r["send_skip"]["lost_short"] == ddm.UNMEASURED
    r = record({back(1): {"plan": plan(True, execution=None, orders=[ORDER]), "send": None}})
    assert r["send_skip"]["applies"] is False and "cls" in r["send_skip"]["why"]
    r = record({back(1): {"plan": plan(False, orders=[ORDER]), "send": send(skipped=skipped)}})
    assert r["send_skip"]["applies"] is False


@pytest.mark.parametrize("exit_", ["DRY", "REFUSED", "NOTHING_TO_SEND"])
def test_a_send_that_did_not_go_labels_no_lost_short(exit_):
    """Review fix F3 after 7fcc2b7: `_send_planned` builds its skipped list BEFORE its gates,
    so a refused or dry send writes the list and sends nothing. 7fcc2b7 labelled it a lost
    short (lost_short True), and so fails here."""
    skipped = ["cef-20260105-PDI-x: PDI shortable=False at send; skipped, the rest go"]
    r = record({back(1): {"plan": plan(True, orders=[ORDER]),
                          "send": send(exit_, skipped=skipped)}})
    sk = r["send_skip"]
    assert sk["applies"] is False and sk.get("lost_short") is not True, sk
    assert "skipped_at_send" not in sk and exit_ in sk["why"]


def test_a_send_whose_outcome_is_not_established_reads_unmeasured():
    """A FAIL whose `final` records nothing (part of a set may have gone), another plan's
    send.json, a STARTED beside a refused or missing send record, a SENT without STARTED:
    never a guess. Whether that session was a reduced decision is unknown (review fix F2), so
    the episode and whether the label applies read UNMEASURED, naming the record. 7fcc2b7 read
    the skipped list in each (True, or False on an empty one), and fails here."""
    skipped = ["x: PDI shortable=False at send; skipped, the rest go"]
    for day in ({"send": send("FAIL", skipped=skipped, final={})},
                {"send": send(skipped=skipped, sha="another")},
                {"send": send("REFUSED"), "started": True},
                {"send": send(skipped=skipped), "started": False}):
        r = record({back(1): {"plan": plan(True, orders=[ORDER]), **day}})
        assert r["episode"]["status"] == ddm.UNMEASURED, day
        assert r["send_skip"]["applies"] == ddm.UNMEASURED, (day, r["send_skip"])
        assert "lost_short" not in r["send_skip"]
        assert str(ASOF) in r["send_skip"]["why"]


def test_no_send_ran_after_a_reduced_decision_with_or_without_orders():
    """No orders: a late-market decide with nothing to send exits NOTHING_TO_SEND and no send
    runs, so nothing could be skipped at one. With orders and no send.json (and no STARTED), no
    send ran in the window. Neither is a lost short. 7fcc2b7 read both UNMEASURED ("no
    send.json"), and fails here; a STARTED with no send.json stays UNMEASURED."""
    for orders in ((), (ORDER,)):
        r = record({back(1): {"plan": plan(True, orders=orders), "send": None}})
        assert r["send_skip"]["applies"] is False, (orders, r["send_skip"])
        assert "lost_short" not in r["send_skip"]
    r = record({back(1): {"plan": plan(True, orders=[ORDER]), "send": None, "started": True}})
    assert r["send_skip"]["applies"] == ddm.UNMEASURED and "STARTED" in r["send_skip"]["why"]


def test_the_lines_render_every_stop():
    days = {back(1): {"plan": plan(True, orders=[ORDER]), "send": send(skipped=["x"])}}
    lines = ddm.thin_stop_lines(record(days, positions={"A": 100}, closes=PRICES))
    text = "\n".join(lines)
    for word in ("episode OPEN", "K0", "K1", "K2", "K3", "SEND SKIP", "report only"):
        assert word in text, word
    assert ddm.thin_stop_lines(ddm.thin_unmeasured_record(ASOF, "boom")) == [
        "  TE4 STOPS (report only): UNMEASURED: boom"]


# --------------------------------------------------------------- in the session (run.py)

def _prior_session(state, d, plan_, send=None, *, started=False):
    day = state / d.isoformat()
    day.mkdir(parents=True, exist_ok=True)
    (day / "plan.json").write_text(json.dumps(plan_))
    if send is not None:
        (day / "send.json").write_text(json.dumps(send))
    if started:                     # run.py writes STARTED before the first order of a set
        (day / "STARTED").write_text("{}")


@pytest.mark.parametrize("eod,k0", [("ok", ddm.CLEAR), ("halve", ddm.KILLED)])
def test_the_next_decide_labels_a_short_skipped_at_the_reduced_sessions_send(
        tmp_path, monkeypatch, eod, k0):
    """The team lead's ruling (2026-11-03): a short skipped at the late SEND after a reduced
    decision is accepted and labelled. The send path is unchanged; the next decide reads that
    session's plan.json and send.json and records the label, with K0 and K2/K3 on its close."""
    from quantt.session import run as rn
    from quantt.session.tests import test_missing_nav_hold as M
    from quantt.session.tests import test_trade_eligible_noop as N
    from quantt.session.tests.test_trade_eligible_runner import TE4_SPEC, run
    base, bk = N.thin_books(tmp_path / "b", monkeypatch)
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    state = tmp_path / "r" / "state"
    skipped = ["cef-20260925-SYD-1: SYD shortable=False at send; skipped, the rest go"]
    _prior_session(state, M.ASOF, {"refusals": [], "execution": "late_market",
                                   "orders": [ORDER], "plan_sha": SHA,
                                   "thin_session": {"reduced": True},
                                   "thin_stops": {"K3": {"verdict": ddm.NOT_APPLICABLE}}},
                   send(skipped=skipped), started=True)
    _prior_session(state, dt.date(2026, 9, 24), {"refusals": []})        # the key absent then
    code, state, _, _ = run(tmp_path / "r", TE4_SPEC, bk["held"], eod)
    assert code == rn.EXIT_PLANNED
    plan = M._plan(state)
    st = plan["thin_stops"]
    assert st["report_only"] is True
    assert st["send_skip"] == {"session": "2026-09-25", "applies": True,
                               "skipped_at_send": skipped, "lost_short": True}
    assert st["episode"]["status"] == "OPEN" and st["episode"]["reduced_sessions"] == ["2026-09-25"]
    assert st["K0"]["verdict"] == k0
    assert plan["thin_session"]["stopped_by"] == (None if eod == "ok" else "K0")
    # K2/K3 on the 09-25 close: measured (the spec sets no line, so their verdicts are UNMEASURED).
    assert isinstance(st["K2"]["stat"], float) and isinstance(st["K3"]["net"], float)
    assert st["K2"]["verdict"] == st["K3"]["verdict"] == ddm.UNMEASURED
    assert st["K1"]["earning_days"] == 0              # 09-25's earning day is 09-28, after the as-of
    run_rec = json.loads(sorted((state / "2026-09-28" / "runs").glob("*.json"))[-1].read_text())
    assert run_rec["thin_stops"] == st


def test_the_next_decide_labels_nothing_after_a_reduced_send_that_did_not_go(
        tmp_path, monkeypatch):
    """The same session as above, but the 09-25 send was dry: send.json carries the skipped
    list `_send_planned` built before its gates, exit DRY, and no STARTED (nothing was sent).
    The label does not apply. Fails on 7fcc2b7, which labelled it a lost short."""
    from quantt.session import run as rn
    from quantt.session.tests import test_missing_nav_hold as M
    from quantt.session.tests import test_trade_eligible_noop as N
    from quantt.session.tests.test_trade_eligible_runner import TE4_SPEC, run
    base, bk = N.thin_books(tmp_path / "b", monkeypatch)
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    state = tmp_path / "r" / "state"
    skipped = ["cef-20260925-SYD-1: SYD shortable=False at send; skipped, the rest go"]
    _prior_session(state, M.ASOF, {"refusals": [], "execution": "late_market",
                                   "orders": [ORDER], "plan_sha": SHA,
                                   "thin_session": {"reduced": True},
                                   "thin_stops": {"K3": {"verdict": ddm.NOT_APPLICABLE}}},
                   send("DRY", skipped=skipped))
    _prior_session(state, dt.date(2026, 9, 24), {"refusals": []})        # the key absent then
    code, state, _, _ = run(tmp_path / "r", TE4_SPEC, bk["held"], "ok")
    assert code == rn.EXIT_PLANNED
    st = M._plan(state)["thin_stops"]
    sk = st["send_skip"]
    assert sk["applies"] is False and "lost_short" not in sk and "DRY" in sk["why"], sk
    # Review fix F2: nor is it a reduced decision (its targets were not sent): no episode,
    # and the 09-25 close is not a reduced close.
    assert st["episode"]["status"] == "NONE" and st["episode"]["reduced_sessions"] == []
    assert st["K3"]["verdict"] == ddm.NOT_APPLICABLE and "not sent" in st["K3"]["why"]


@pytest.mark.parametrize("run_sessions,want", [(3, ddm.TRIPPED), (4, ddm.CLEAR)])
def test_the_session_counts_k3s_run_from_the_asof_sessions_own_plan(tmp_path, monkeypatch,
                                                                    run_sessions, want):
    """K3's run in the real session, on prior plan.json files in the runner's own shape: the
    decide for X records the K3 of the close BEFORE X (`session`), so the 09-24 close is in
    the 09-25 plan. Reduced decisions on 09-23, 09-24 and 09-25, each close above the run line,
    with 09-22 decided with the key absent: today's decide (as-of 09-25) reads a run of 3 and
    TRIPS. Fails on 7fcc2b7, which skipped the 09-25 plan and read 2, CLEAR. With the spec's
    `risk.thin_k3_run_sessions` at 4 the same run of 3 is CLEAR: the runner passes the spec's run
    length to the K-lines (the runner owner's review 2026-11-04, item 9); 8527488 used its own
    constant 3 whatever the spec said, and its 4 case fails."""
    import copy
    from quantt.session import run as rn
    from quantt.session.tests import test_missing_nav_hold as M
    from quantt.session.tests import test_trade_eligible_noop as N
    from quantt.session.tests.test_trade_eligible_runner import TE4_SPEC, run
    spec = copy.deepcopy(TE4_SPEC)
    note = "test only: compose_2026-12-01.json §E"
    spec["risk"].update(thin_k3_net_run=0.00005, _thin_k3_net_run_note=note,
                        thin_k3_net_once=1.7, _thin_k3_net_once_note=note,
                        thin_k3_run_sessions=run_sessions)
    base, bk = N.thin_books(tmp_path / "b", monkeypatch)
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    state = tmp_path / "r" / "state"
    d = [dt.date(2026, 9, 22), dt.date(2026, 9, 23), dt.date(2026, 9, 24), M.ASOF]

    def reduced(k3):
        return {"refusals": [], "execution": "late_market", "orders": [], "plan_sha": "s",
                "thin_session": {"reduced": True}, "thin_stops": {"K3": k3}}
    _prior_session(state, d[0], {"refusals": []})                        # the key absent then
    _prior_session(state, d[1], reduced({"verdict": ddm.NOT_APPLICABLE, "session": "2026-09-22"}))
    _prior_session(state, d[2], reduced({"net": 0.5, "verdict": ddm.CLEAR, "session": "2026-09-23"}))
    _prior_session(state, d[3], reduced({"net": 0.5, "verdict": ddm.CLEAR, "session": "2026-09-24"}))
    code, state, _, _ = run(tmp_path / "r", spec, bk["held"], "ok")
    assert code == rn.EXIT_PLANNED
    k3 = M._plan(state)["thin_stops"]["K3"]
    assert k3["session"] == "2026-09-25"
    # The held book is near neutral (net about 1.2e-4 of equity): the run line sits below it.
    assert 0.00005 < k3["net"] < 1.7                  # above the run line, below the once line
    assert k3["run"] == 3 and k3["verdict"] == want and k3["run_sessions"] == run_sessions


@pytest.mark.parametrize("clock", ["09:00", "22:00"])
@pytest.mark.parametrize("eod", ["ok", "morning_ok"])
def test_the_session_reads_k1_k3_through_k0s_own_row_evening_and_morning(tmp_path, monkeypatch,
                                                                          eod, clock):
    """The runner owner's review (2026-11-04), item 6, in the real session. Reduced decisions on
    09-24 (it earns 09-25) and 09-25, with 09-23 decided with the key absent. "ok" is what prod
    has at 22:00 (no 09-25 row): K0 reads 09-24, one session stale, and so do K1-K3, labelled;
    the 09-25 earning day is listed unread. "morning_ok" is the backstop with the 09-25 row
    there: K0 reads 09-25, 0 stale, and the lines read exactly that date: K1 counts the 09-25
    day, and K2/K3 divide by the 09-25 equity with no note. Fails on 69ef368 (its morning label
    said the as-of's row was not there yet, and the evening K2/K3 carried no `equity_note`).

    THE CLOCK (review of 4e1ab0b). Each case runs at the 22:00 decide on the as-of (M.EVE) AND
    at 09:00 ET on the session day, a true morning-backstop clock: the item-6 morning case
    ("morning_ok" at 09:00) had only ever run at 22:00. The numbers follow the data, never the
    clock, and pass on 4e1ab0b in all four cases (pins; the review found them right by probe).
    The `read_through` label must say what the data showed and name no slot, because the
    function is not told which slot ran. 4e1ab0b's named one in every case, inferred from the
    staleness: "the 22:00 decide" whenever the row was missing and "the morning backstop"
    whenever it was there, so ("ok", 09:00) and ("morning_ok", 22:00) named the slot that did
    not run. All four fail on 4e1ab0b on that assertion, and on nothing else."""
    from quantt.session import run as rn
    from quantt.session.tests import test_missing_nav_hold as M
    from quantt.session.tests import test_trade_eligible_noop as N
    from quantt.session.tests.test_trade_eligible_runner import K0_EOD, TE4_SPEC, run
    now = {"09:00": dt.datetime(2026, 9, 28, 9, 0, tzinfo=M.ET), "22:00": M.EVE}[clock]
    base, bk = N.thin_books(tmp_path / "b", monkeypatch)
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    state = tmp_path / "r" / "state"

    def reduced(k3):
        return {"refusals": [], "execution": "late_market", "orders": [], "plan_sha": "s",
                "thin_session": {"reduced": True}, "thin_stops": {"K3": k3}}
    _prior_session(state, dt.date(2026, 9, 23), {"refusals": []})        # the key absent then
    _prior_session(state, dt.date(2026, 9, 24),
                   reduced({"verdict": ddm.NOT_APPLICABLE, "session": "2026-09-23"}))
    _prior_session(state, M.ASOF, reduced({"net": 0.01, "verdict": ddm.UNMEASURED,
                                           "session": "2026-09-24"}))
    code, state, _, _ = run(tmp_path / "r", TE4_SPEC, bk["held"], eod, now=now)
    assert code == rn.EXIT_PLANNED
    plan = M._plan(state)
    st, k0 = plan["thin_stops"], plan["thin_session"]["k0"]
    assert plan["session_date"] == "2026-09-28" and plan["asof"] == "2026-09-25"
    want = "2026-09-25" if eod == "morning_ok" else "2026-09-24"
    stale = 0 if eod == "morning_ok" else 1
    assert k0["status"] == "OK" and k0["read_through"] == want
    assert st["K0"]["read_through"] == want
    assert st["read_through"]["date"] == want and st["read_through"]["sessions_stale"] == stale
    assert st["episode"]["status"] == "OPEN"
    assert st["episode"]["reduced_sessions"] == ["2026-09-24", "2026-09-25"]
    eq = dict(K0_EOD[eod])
    label = st["read_through"]["label"]
    text = "\n".join(ddm.thin_stop_lines(st))
    for slot in ("22:00", "morning", "backstop", "evening"):
        assert slot not in label and slot not in text, (slot, label)
    if eod == "morning_ok":
        assert "the as-of's own row, there at this decide" in label
        assert st["K1"]["earning_days"] == 1 and st["K1"]["earned_not_yet_read"] == []
        assert st["K1"]["drawdown"] == 0.0              # 100,600 -> 100,800: a gain
    else:
        assert "not there yet at this decide" in label
        assert st["K1"]["earning_days"] == 0
        assert st["K1"]["earned_not_yet_read"] == ["2026-09-25"]
    for k in ("K2", "K3"):
        assert st[k]["equity_date"] == want
        assert ("equity_note" in st[k]) is (eod == "ok")
    # K2 by hand: the largest held name at the as-of close, over that one date's equity.
    from src.deploy.sleeves import cef_discount as cefmod
    closes = {s: v[0] for s, v in rn.last_closes(cefmod.PX_PATH, M.ASOF,
                                                 list(bk["held"])).items()}
    top = max(abs(q * closes[s]) for s, q in bk["held"].items() if q)
    assert st["K2"]["stat"] == pytest.approx(top / eq[want], rel=1e-6)


def test_with_the_key_set_every_decide_carries_the_lines_and_a_failure_is_recorded(
        tmp_path, monkeypatch):
    from quantt.session import run as rn
    from quantt.session.tests import test_missing_nav_hold as M
    from quantt.session.tests import test_trade_eligible_noop as N
    from quantt.session.tests.test_trade_eligible_runner import TE4_SPEC, run
    base, bk = N.thin_books(tmp_path / "b", monkeypatch)
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    code, state, _, _ = run(tmp_path / "plain", TE4_SPEC, bk["held"], "ok")
    st = M._plan(state)["thin_stops"]
    # No earlier record in this state dir: every session the walk reads is a named gap, so the
    # episode state is UNMEASURED, naming them.
    assert st["episode"]["status"] == ddm.UNMEASURED and "have no record" in st["episode"]["why"]
    assert len(st["episode"]["gaps"]) == ddm.THIN_EPISODE_GAP - 1
    assert code == rn.EXIT_PLANNED

    def boom(**kw):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(ddm, "thin_stop_record", boom)
    code, state, _, _ = run(tmp_path / "boom", TE4_SPEC, bk["held"], "ok")
    assert code == rn.EXIT_PLANNED                    # report only: the session goes on
    assert M._plan(state)["thin_stops"] == {"report_only": True, "asof": "2026-09-25",
                                            "unmeasured": "RuntimeError: synthetic"}
