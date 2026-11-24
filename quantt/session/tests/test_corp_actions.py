"""The corporate-action gate: which actions block, and what each mode does to a session.

Alpaca paper processes no corporate actions, so a held name that splits keeps
its old share count while its price moves to the new basis
(`quantt/session/corp_actions.py`). These tests pin the window that decides
which actions block (`blocking_events`, pure), the dating of each held name
from the account's own order history (`held_since`), and the three book-json
settings end to end through `run_session` with fake deps: absent (no gate,
today's behaviour), `report` (record and send) and `halt` (refuse, naming the
event; refuse too when the feed cannot be read).

Hermetic: the client is `test_run.FakeClient` with a `corporate_actions` method
added, state lives under tmp_path, and the root conftest blocks the network.
Events are synthetic; they test the code, never a claim about the market.
"""
import datetime as dt
import json
from pathlib import Path

import pytest

from quantt.session import corp_actions as cam
from quantt.session import run as rn
from quantt.session.tests.test_run import (ASOF, BOOK, D, EVE, LATE, SPEC, FakeClient, make,
                                           to_send_time)

L = dt.date(2026, 9, 21)           # a held name's window start, for the pure tests (a Monday)
HELD = {"CCC": 100}
# CCC's last fill: submitted 2026-09-21 19:30 ET (23:30Z), filled at the next auction.
CLOSED = [{"id": "o1", "client_order_id": "cef-20260922-CCC-1", "symbol": "CCC",
           "side": "buy", "status": "filled", "filled_qty": "100",
           "submitted_at": "2026-09-21T23:30:00Z"}]
# What `held_since` makes of CLOSED: the trading day before the 2026-09-21
# submission, the latest close that order can have been sized on (a Friday).
L_SET = dt.date(2026, 9, 18)


def ev(sym, date, *, typ="reverse_split", role="subject", process=None, other=None, i=None,
       date_field="ex_date"):
    parties = [[sym, role]] + ([list(other)] if other else [])
    return {"id": i or f"{typ}-{sym}-{date}", "type": typ, "date": date,
            "date_field": date_field, "process_date": process or date, "parties": parties}


# ---------------------------------------------------------------- the window

def test_windows_held_from_last_set_target_from_asof_both_through_the_session():
    w = cam.windows({"CCC": L}, ["AAA", "CCC"], ASOF, D)
    assert w == {"AAA": (ASOF, D), "CCC": (L, D)}


def test_a_held_name_set_after_the_asof_still_starts_at_the_asof():
    """A fill on the session morning (a person's) cannot narrow the window past
    the close every order is priced on."""
    assert cam.windows({"CCC": D}, [], ASOF, D) == {"CCC": (ASOF, D)}


def test_windows_refuse_an_asof_that_is_not_before_the_session():
    with pytest.raises(ValueError, match="before the session"):
        cam.windows({}, ["AAA"], D, D)


@pytest.mark.parametrize("date,process,blocks,why", [
    (dt.date(2026, 9, 25), None, True, "after the shares were last set, before the as-of"),
    (L, None, True, "on the day the shares were last set: the fill came after the open"),
    (L - dt.timedelta(days=1), None, False, "before the shares were last set"),
    (ASOF, None, True, "on the as-of date: close(A) on the new basis"),
    (D, None, True, "on the session date: before the fill"),
    (D + dt.timedelta(days=1), None, False, "after the fill: the next session's"),
    # process-date-only matches are judged on the SHORT window (as-of, session]
    (L - dt.timedelta(days=5), dt.date(2026, 9, 24), False,
     "processed inside the long window but before the as-of: a short-window match, so clear"),
    (L - dt.timedelta(days=5), ASOF, False, "processed on the as-of date: the short window is open there"),
    (L - dt.timedelta(days=5), D, True, "processed on the session date"),
])
def test_a_held_name_blocks_exactly_inside_its_window(date, process, blocks, why):
    out = cam.blocking_events([ev("CCC", date, process=process)], held={"CCC": L},
                              targets=[], asof=ASOF, session_date=D)
    assert bool(out) is blocks, why


@pytest.mark.parametrize("date,blocks", [
    (ASOF - dt.timedelta(days=1), False),    # fully in the past: close(A) and the fill agree
    (ASOF, True), (D, True), (D + dt.timedelta(days=1), False)])
def test_a_target_only_name_blocks_from_the_asof_through_the_session(date, blocks):
    out = cam.blocking_events([ev("AAA", date)], held={}, targets=["AAA"],
                              asof=ASOF, session_date=D)
    assert bool(out) is blocks


def test_calendar_days_between_the_asof_and_the_session_are_inside():
    """Friday as-of, Monday session: a Sunday process date blocks."""
    fri, mon, sun = dt.date(2026, 10, 2), dt.date(2026, 10, 5), dt.date(2026, 10, 4)
    out = cam.blocking_events([ev("AAA", mon + dt.timedelta(days=30), process=sun)],
                              held={}, targets=["AAA"], asof=fri, session_date=mon)
    assert [b["in_window"] for b in out] == [["process_date"]]


def test_a_held_acquirer_in_a_stock_merger_blocks_and_so_does_the_acquiree():
    """BE CONSERVATIVE: the acquirer's count does not change, but its price can
    jump on the deal's terms. Both sides of one merger block, each named."""
    m = ev("CCC", D, typ="stock_merger", role="acquiree", other=("AAA", "acquirer"),
           date_field="effective_date")
    out = cam.blocking_events([m], held={"CCC": L}, targets=["AAA"], asof=ASOF, session_date=D)
    assert [(b["symbol"], b["role"], b["held"]) for b in out] == [
        ("AAA", "acquirer", False), ("CCC", "acquiree", True)]
    only_acq = cam.blocking_events([m], held={"AAA": L}, targets=[], asof=ASOF, session_date=D)
    assert [(b["symbol"], b["role"]) for b in only_acq] == [("AAA", "acquirer")]


def test_an_event_naming_none_of_our_names_never_blocks():
    m = ev("XYZ", D, typ="stock_merger", role="acquiree", other=("QRS", "acquirer"))
    assert cam.blocking_events([m], held={"CCC": L}, targets=["AAA"], asof=ASOF,
                               session_date=D) == []


def test_a_held_name_with_no_date_raises_rather_than_assume_one():
    with pytest.raises(ValueError, match="CCC"):
        cam.windows({"CCC": None}, [], ASOF, D)


# ------------------------------------------------ when the shares were last set

def test_held_since_is_the_trading_day_before_the_et_submission_date_of_the_last_fill():
    closed = CLOSED + [
        # 2026-09-25 02:30Z is 2026-09-24 22:30 ET (Thursday): an evening cls send
        {"client_order_id": "b", "symbol": "CCC", "filled_qty": "5",
         "submitted_at": "2026-09-25T02:30:00Z"},
        {"client_order_id": "c", "symbol": "CCC", "filled_qty": "0",          # expired, unfilled
         "submitted_at": "2026-09-27T19:52:00Z"},
        {"client_order_id": "d", "symbol": "AAA", "filled_qty": "3",
         "submitted_at": "2026-09-26T19:52:00Z"}]
    # the trading day before Thursday 09-24 (ET; the UTC date is 09-25)
    assert cam.held_since(closed, ["CCC"]) == {"CCC": dt.date(2026, 9, 23)}
    assert cam.held_since(CLOSED, ["CCC"]) == {"CCC": L_SET}           # Monday -> Friday


def test_a_weekend_action_before_a_late_market_monday_fill_blocks_on_the_long_window():
    """Re-review 2026-10-29, the replay. A reorganization of a held name is
    effective Saturday 2026-10-03; the last fill was a late-market order
    submitted Monday 2026-10-05 15:52 ET (19:52Z), which was sized on Friday
    10-02's close. The window must start at that Friday, so the action is
    inside it. Sessions 10-06 and 10-07 both block, on the long window: the
    count is wrong until the name trades again. Starting the window at the
    submission date (the second commit) put Saturday outside it for good."""
    closed = [{"client_order_id": "cef-20261005-CCC-1", "symbol": "CCC", "filled_qty": "40",
               "submitted_at": "2026-10-05T19:52:00Z"}]
    sat = dt.date(2026, 10, 3)
    reorg = ev("CCC", sat, typ="reorganization", date_field="effective_date",
               process=dt.date(2026, 10, 8), i="reorg-sat")
    assert cam.held_since(closed, ["CCC"]) == {"CCC": dt.date(2026, 10, 2)}
    for asof, session in ((dt.date(2026, 10, 5), dt.date(2026, 10, 6)),
                          (dt.date(2026, 10, 6), dt.date(2026, 10, 7))):
        rec = cam.check(lambda *a: [reorg], closed, {"CCC": 40}, [], asof, session, cam.HALT)
        assert rec["status"] == cam.BLOCKING, session
        assert [(b["id"], b["rule"]) for b in rec["blocking"]] == [("reorg-sat", cam.LONG)]


@pytest.mark.parametrize("submitted,clears", [
    ("2026-10-08T19:52:00Z", False),   # Thu 15:52 ET: sized on Wed 10-07's close, the ex-date
    ("2026-10-09T19:52:00Z", True),    # Fri 15:52 ET: the second trading day after
])
def test_a_corrective_order_clears_a_split_only_from_the_second_trading_day_after(submitted,
                                                                                  clears):
    """Third review, 2026-10-29 (the window start stays inclusive). A held
    name reverse-splits ex Wednesday 10-07. A corrective order submitted on
    Thursday 10-08 has L_X = 10-07, the event's own close, so the halt stays
    on at the next session (Monday 10-12, as-of Friday 10-09). One submitted on
    Friday 10-09 has L_X = 10-08, after the event, and clears it."""
    ex = dt.date(2026, 10, 7)
    split = ev("CCC", ex, typ="reverse_split", i="rs-wed")
    closed = [{"client_order_id": "manual-CCC", "symbol": "CCC", "filled_qty": "25",
               "submitted_at": submitted}]
    rec = cam.check(lambda *a: [split], closed, {"CCC": 25}, [], dt.date(2026, 10, 9),
                    dt.date(2026, 10, 12), cam.HALT)
    assert rec["status"] == (cam.CLEAR if clears else cam.BLOCKING)
    if not clears:
        assert [(b["id"], b["rule"], b["window"][0]) for b in rec["blocking"]] == [
            ("rs-wed", cam.LONG, ex)]


def test_held_since_raises_for_a_held_name_with_no_fill_or_a_bad_order():
    with pytest.raises(ValueError, match=r"\['BBB'\]"):
        cam.held_since(CLOSED, ["BBB", "CCC"])
    with pytest.raises(ValueError, match="filled_qty"):
        cam.held_since([{"client_order_id": "x", "symbol": "CCC", "filled_qty": "lots",
                         "submitted_at": "2026-09-21T23:30:00Z"}], ["CCC"])


def test_check_with_nothing_held_or_targeted_is_clear_and_reads_nothing():
    calls = []
    rec = cam.check(lambda *a: calls.append(a) or [], [], {}, [], ASOF, D, cam.HALT)
    assert rec["status"] == cam.CLEAR and calls == []


def test_check_asks_for_the_padded_union_of_the_windows():
    calls = []
    cam.check(lambda *a: calls.append(a) or [], CLOSED, HELD, ["AAA"], ASOF, D, cam.REPORT)
    assert calls == [(["AAA", "CCC"], L_SET - dt.timedelta(days=31), D + dt.timedelta(days=731))]


def test_the_query_pads_are_the_measured_values():
    """Pinned by value, not by name, so a change cannot pass in silence (review
    2026-10-29). The API's window filters on process_date (all 3,443 rows of a
    twelve-month real read had a process date inside it). BEFORE: the earliest
    process date seen was 4 days before its market date, and 31 covers it.
    AFTER: 18 of 3,443 rows were processed more than 31 days after their market
    date; 731 covers every measured gap up to 668 days (docs/REFERENCES.md
    §12pc; the constants' comment in corp_actions.py)."""
    assert (cam.QUERY_PAD_BEFORE_DAYS, cam.QUERY_PAD_AFTER_DAYS) == (31, 731)


# ------------------------------------------- two windows (team lead, 2026-10-29)

NEXT = dt.date(2026, 9, 30)        # the session after D (Wednesday)
AFTER = dt.date(2026, 10, 1)       # and the one after that


def blocks(event, *, held=None, targets=(), asof=ASOF, session=D):
    return cam.blocking_events([event], held=held or {}, targets=list(targets), asof=asof,
                               session_date=session)


@pytest.mark.parametrize("typ,role,other,rule", [
    ("stock_merger", "acquirer", ("ZZZ", "acquiree"), cam.SHORT_ACQUIRER),
    ("stock_and_cash_merger", "acquirer", ("ZZZ", "acquiree"), cam.SHORT_ACQUIRER),
    ("cash_merger", "acquirer", ("ZZZ", "acquiree"), cam.SHORT_ACQUIRER),
    # re-review 2026-10-29: the allocated security's holders keep their count too
    ("reorganization", "allocated", ("ZZZ", "subject"), cam.SHORT_ALLOCATED)])
def test_a_held_acquirer_or_allocated_holder_halts_one_session_and_then_clears(typ, role,
                                                                                other, rule):
    """Team lead 2026-10-29: "a day at most" is ONE session. An acquirer event on
    trading day E blocks session E, whose window (E-1, E] holds it, and does NOT
    block session E+1, whose as-of is E: by then the as-of close is post-event
    and the acquirer's count was never touched. The shares were set long before.
    A reorganization's allocated leg is judged the same way."""
    m = ev("CCC", D, typ=typ, role=role, other=other, date_field="effective_date")
    held = {"CCC": L}
    hit = blocks(m, held=held)                                       # session E = D
    assert [(b["symbol"], b["rule"], b["window"]) for b in hit] == [
        ("CCC", rule, [D, D])]                                        # (ASOF, D] as calendar days
    assert blocks(m, held=held, asof=D, session=NEXT) == []          # session E+1: clear


def test_the_short_window_is_open_at_the_asof_and_spans_the_calendar_days_after_it():
    """(as-of, session] in whole calendar days: a Friday as-of and a Monday
    session hold Saturday, Sunday and Monday, and not the Friday."""
    fri, mon = dt.date(2026, 10, 2), dt.date(2026, 10, 5)
    for day, want in ((fri, False), (dt.date(2026, 10, 3), True), (dt.date(2026, 10, 4), True),
                      (mon, True)):
        m = ev("ZZZ", day, typ="stock_merger", role="acquiree", other=("CCC", "acquirer"),
               date_field="effective_date")
        assert bool(blocks(m, held={"CCC": L}, asof=fri, session=mon)) is want, day


def test_an_acquirer_dated_before_the_asof_never_blocks_even_inside_the_long_window():
    m = ev("ZZZ", dt.date(2026, 9, 24), typ="stock_merger", role="acquiree",
           other=("CCC", "acquirer"), date_field="effective_date")
    assert blocks(m, held={"CCC": L}) == []


@pytest.mark.parametrize("typ,role", [("stock_merger", "acquirer"),
                                       ("reorganization", "allocated")])
def test_an_acquirers_process_date_never_blocks_by_itself(typ, role):
    """Re-review 2026-10-29: an acquirer (and an allocated holder) is judged on
    the MARKET date only. Processed inside (as-of, session] with its effective
    date before it, it does not block. It must not reach the process-date-only
    rule either, which would block a long-window role on that date. Paper never
    applies a process date."""
    m = ev("CCC", ASOF - dt.timedelta(days=3), typ=typ, role=role, other=("ZZZ", "subject"),
           process=D, date_field="effective_date")
    assert blocks(m, held={"CCC": L}) == []


# The real MQY and MHD stock mergers, as the feed served them (read-only Alpaca
# connector, 2026-10-29; docs/REFERENCES.md §12pc): each MQY pair is listed twice,
# processed on 02-23 and on 02-24; MHD's rows once each.
REAL_ACQUIRER_ROWS = [
    ("46a647bb-9125-4578-a5dd-335531218f14", "BKN", "MQY", "2026-02-23", "2026-02-23"),
    ("fef37584-e4f9-411e-94c3-1a10ef5b68cb", "BKN", "MQY", "2026-02-23", "2026-02-24"),
    ("f5e7b9d7-57ea-453a-a6c9-07d22bd4454f", "MQT", "MQY", "2026-02-23", "2026-02-23"),
    ("00a73250-1561-4610-aa6b-f3c7ca33a01e", "MQT", "MQY", "2026-02-23", "2026-02-24"),
    ("93ab0fc0-30ce-4a62-92dc-afeb78e6b403", "MYD", "MQY", "2026-02-23", "2026-02-23"),
    ("0b1f4880-8917-445d-8501-b8a45bf0b992", "MYD", "MQY", "2026-02-23", "2026-02-24"),
    ("d0f3a574-e1dd-44bd-9e33-f344f0ea183d", "BFK", "MHD", "2026-02-09", "2026-02-09"),
    ("a28b4002-58b9-4072-bd6c-e69842e7d121", "BLE", "MHD", "2026-02-09", "2026-02-09"),
    ("25c980d1-c881-49f4-a19b-cbafdc03dbf8", "BYM", "MHD", "2026-02-09", "2026-02-09"),
    ("ab302437-1bb0-4a3c-8448-d7847bc9361c", "MUE", "MHD", "2026-02-09", "2026-02-09"),
]
REAL_ACQUIRER_EVENTS = [
    {"id": i, "type": "stock_merger", "date": dt.date.fromisoformat(eff),
     "date_field": "effective_date", "process_date": dt.date.fromisoformat(proc),
     "parties": [[tgt, "acquiree"], [acq, "acquirer"]]}
    for i, tgt, acq, eff, proc in REAL_ACQUIRER_ROWS]


@pytest.mark.parametrize("name,sessions", [
    # (as-of, session, blocks): 2026-02-20 was a Friday, 02-16 Presidents' Day
    ("MQY", [(dt.date(2026, 2, 20), dt.date(2026, 2, 23), True),
             (dt.date(2026, 2, 23), dt.date(2026, 2, 24), False),
             (dt.date(2026, 2, 24), dt.date(2026, 2, 25), False)]),
    ("MHD", [(dt.date(2026, 2, 6), dt.date(2026, 2, 9), True),
             (dt.date(2026, 2, 9), dt.date(2026, 2, 10), False)]),
])
def test_the_real_mqy_pair_listed_twice_blocks_one_session(name, sessions):
    """Held since before the deals. Under market-or-process (the third commit),
    MQY's second listing, processed 02-24, also blocked session 02-24: two
    sessions against the ruling's one. Market date only: 02-23 BLOCK, 02-24
    clear, 02-25 clear; MHD's single-dated rows block 02-09 only."""
    held = {name: dt.date(2026, 1, 2)}
    for asof, session, want in sessions:
        hit = cam.blocking_events(REAL_ACQUIRER_EVENTS, held=held, targets=[], asof=asof,
                                  session_date=session)
        assert bool(hit) is want, session
        assert all(b["rule"] == cam.SHORT_ACQUIRER and b["symbol"] == name for b in hit)


def test_an_acquiree_still_uses_the_long_window():
    m = ev("CCC", dt.date(2026, 9, 24), typ="stock_merger", role="acquiree",
           other=("ZZZ", "acquirer"), date_field="effective_date")
    hit = blocks(m, held={"CCC": L})
    assert [(b["rule"], b["window"]) for b in hit] == [(cam.LONG, [L, D])]
    assert blocks(m, held={"CCC": L}, asof=NEXT, session=AFTER)     # does not clear by itself


def test_an_acquiree_on_day_e_still_blocks_session_e_plus_one():
    """The long window keeps the as-of inside: the acquiree's paper count is
    wrong from E on, so session E+1 (as-of E) still blocks, unlike the
    acquirer's on the same merger."""
    m = ev("CCC", D, typ="stock_merger", role="acquiree", other=("ZZZ", "acquirer"),
           date_field="effective_date")
    assert [b["rule"] for b in blocks(m, held={"CCC": L})] == [cam.LONG]
    assert [b["rule"] for b in blocks(m, held={"CCC": L}, asof=D, session=NEXT)] == [cam.LONG]
    acq = ev("ZZZ", D, typ="stock_merger", role="acquiree", other=("CCC", "acquirer"),
             date_field="effective_date")
    assert blocks(acq, held={"CCC": L}, asof=D, session=NEXT) == []


def test_a_backfilled_row_on_a_held_name_blocks_one_session_only():
    """The real feed backfills: a 2016 split processed in 2025. Matched only
    through its process date, it blocks the session whose window (as-of,
    session] holds that date, and not the next one (as-of = the process date):
    the count was consistent all along."""
    old = dt.date(2016, 10, 7)
    on_d = ev("CCC", old, typ="forward_split", process=D)
    assert [b["rule"] for b in blocks(on_d, held={"CCC": L})] == [cam.SHORT_PROCESS]
    assert blocks(on_d, held={"CCC": L}, asof=D, session=NEXT) == []
    on_asof = ev("CCC", old, typ="forward_split", process=ASOF)
    assert blocks(on_asof, held={"CCC": L}) == []                   # on the as-of: outside
    before = ev("CCC", old, typ="forward_split", process=ASOF - dt.timedelta(days=1))
    assert blocks(before, held={"CCC": L}) == []                    # before the as-of


@pytest.mark.parametrize("typ,role", [
    ("reverse_split", "subject"), ("forward_split", "subject"), ("unit_split", "old"),
    ("stock_dividend", "subject"), ("spin_off", "source"), ("spin_off", "new"),
    ("reorganization", "subject"), ("name_change", "old"), ("name_change", "new"),
    ("redemption", "subject"), ("worthless_removal", "subject"), ("partial_call", "subject"),
    ("cash_merger", "acquiree"), ("stock_merger", "acquiree")])
def test_every_long_window_role_keeps_blocking_after_the_asof_passes(typ, role):
    e = ev("CCC", dt.date(2026, 9, 24), typ=typ, role=role)
    assert [b["rule"] for b in blocks(e, held={"CCC": L}, asof=NEXT, session=AFTER)] == [cam.LONG]


def test_refusal_text_names_the_event_and_unmeasured_never_reads_clear():
    b = cam.check(lambda *a: [ev("CCC", D, i="split-1")], CLOSED, HELD, [], ASOF, D, cam.HALT)
    text = cam.refusal_text(b)
    assert "CCC" in text and "reverse_split" in text and "split-1" in text and "held" in text
    u = cam.unmeasured_record(cam.HALT, ASOF, D, "AlpacaHTTPError: 503")
    assert "UNMEASURED" in cam.refusal_text(u) and "503" in cam.refusal_text(u)
    clear = cam.check(lambda *a: [], CLOSED, HELD, [], ASOF, D, cam.HALT)
    assert cam.refusal_text(clear) is None


# ------------------------------------------------------------ the book setting

def _book(tmp_path, block):
    b = tmp_path / "book.json"
    body = {"book_id": "x"}
    if block is not None:
        body["corporate_actions"] = block
    b.write_text(json.dumps(body))
    return rn.Book("cef", "cef", Path("s"), b)


def test_the_setting_absent_is_no_gate_and_a_bad_one_raises(tmp_path):
    assert rn.corporate_actions_for(_book(tmp_path, None)) is None
    assert rn.corporate_actions_for(_book(tmp_path, {"mode": "report"})) == "report"
    assert rn.corporate_actions_for(_book(tmp_path, {"mode": "halt"})) == "halt"
    for bad in ({"mode": "on"}, {"mode": "HALT"}, {}, "halt"):
        with pytest.raises(rn.SessionError, match="corporate_actions"):
            rn.corporate_actions_for(_book(tmp_path, bad))
    assert rn.Deps(client=None, env={}, refresh=None, closes=None, navs=None, targets=None,
                   halts=None).corp_actions is None


def test_the_deployed_book_sets_report_until_the_unresolved_rows_are_re_ruled():
    """Team lead 2026-10-28: a HALT guard for the paper runner. Team lead 2026-11-02:
    REPORT for the release that carries CEF trial 53, because three real market-wide
    rows with a missing party would halt every session under the unresolved-rows
    ruling (release-check on 3478159). The book json says how to restore halt; this
    pin makes the switch back a visible, tested edit rather than a silent one."""
    assert rn.corporate_actions_for(rn.BOOKS["cef"]) == cam.REPORT
    import json
    block = json.loads(rn.BOOKS["cef"].book_path.read_text())["corporate_actions"]
    assert "RESTORE" in block["_mode_report_note"] and "halt" in block["_mode_report_note"]


# ------------------------------------------------------------- run_session

class CAClient(FakeClient):
    """test_run.FakeClient plus Alpaca's non-dividend corporate-action read."""

    def __init__(self, state, *, events=(), ca_error=None, **kw):
        super().__init__(state, **kw)
        self.events = list(events)
        self.ca_error = ca_error

    def corporate_actions(self, symbols, start, end, *, universe=None, skipped=None, rows=None):
        # `universe`/`skipped` (AlpacaClient.corporate_actions, MALFORMED ROWS):
        # these synthetic events are well-formed, so nothing is ever skipped.
        # `rows` (RAW ROWS): a synthetic event has no raw row, so it stands as its own.
        self.ca_at = len(self.calls)          # where in the call log the read happened
        self.calls.append(("corporate_actions", tuple(symbols), start, end))
        if self.ca_error is not None:
            raise self.ca_error
        out = [e for e in self.events if any(s in symbols for s, _ in e["parties"])]
        if rows is not None:
            for e in out:
                rows.setdefault(e["id"], []).append(dict(e))
        return out


def run(tmp_path, mode, *, events=(), ca_error=None, positions=None, closed=None,
        armed=True, **kw):
    c = CAClient(tmp_path / "state", events=events, ca_error=ca_error,
                 positions=HELD if positions is None else positions,
                 closed=CLOSED if closed is None else closed, **kw.pop("ck", {}))
    c, deps, state, seen, out = make(tmp_path, client=c, **kw)
    deps.corp_actions = mode
    if armed:
        (state / "AUTO_ARMED").touch()
    return c, deps, state, out


def plan_of(state):
    return json.loads((state / D.isoformat() / "plan.json").read_text())


def test_halt_refuses_a_held_name_split_on_the_session_date_with_zero_transmits(tmp_path):
    c, deps, state, out = run(tmp_path, cam.HALT, events=[ev("CCC", D, i="split-1")])
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert c.submits() == []
    assert not (state / D.isoformat() / "STARTED").exists()
    plan = plan_of(state)
    data = [r["detail"] for r in plan["refusals"] if r["gate"] == "data"]
    assert len(data) == 1 and "CCC" in data[0] and "split-1" in data[0]
    assert plan["corporate_actions"]["status"] == cam.BLOCKING
    assert "CORPORATE ACTIONS (halt): BLOCKING" in "".join(out)


def test_halt_refuses_a_target_only_acquiree(tmp_path):
    m = ev("AAA", D, typ="stock_merger", role="acquiree", other=("ZZZ", "acquirer"),
           date_field="effective_date", i="merger-1")
    c, deps, state, out = run(tmp_path, cam.HALT, events=[m])
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert c.submits() == []
    assert "AAA (target) is the acquiree" in plan_of(state)["refusals"][0]["detail"]


def test_halt_sends_when_the_only_action_is_before_the_shares_were_last_set(tmp_path):
    c, deps, state, out = run(tmp_path, cam.HALT,
                              events=[ev("CCC", L_SET - dt.timedelta(days=3))])
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    assert len(c.submits()) == 3                       # BBB, AAA, and CCC flattened
    rec = plan_of(state)["corporate_actions"]
    assert rec["status"] == cam.CLEAR and len(rec["events"]) == 1 and rec["blocking"] == []


def test_report_records_the_blocking_event_and_sends(tmp_path):
    c, deps, state, out = run(tmp_path, cam.REPORT, events=[ev("CCC", D, i="split-1")])
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    assert len(c.submits()) == 3
    plan = plan_of(state)
    assert plan["refusals"] == []
    assert plan["corporate_actions"]["status"] == cam.BLOCKING
    assert plan["corporate_actions"]["blocking"][0]["id"] == "split-1"
    assert "CORPORATE ACTIONS (report): BLOCKING" in "".join(out)
    assert "report mode: nothing refused" in "".join(out)


def test_report_changes_nothing_that_trades(tmp_path):
    """Report mode, with a blocking event, against the key absent: the same exit,
    the same orders sent, and plan.json identical once `corporate_actions` is removed."""
    event = [ev("CCC", D)]
    c0, d0, s0, _ = run(tmp_path / "off", None, events=event)
    c1, d1, s1, _ = run(tmp_path / "report", cam.REPORT, events=event)
    assert rn.run_session(BOOK, SPEC, d0) == rn.run_session(BOOK, SPEC, d1) == rn.EXIT_SENT
    assert c0.submits() == c1.submits()
    p0, p1 = plan_of(s0), plan_of(s1)
    assert "corporate_actions" not in p0
    p1.pop("corporate_actions")
    assert p0 == p1


def test_the_key_absent_reads_nothing_and_records_nothing(tmp_path):
    """No-op guard for the default: with the key absent the session never calls
    the read (FakeClient has no such method, so a call would FAIL the run) and
    plan.json carries no `corporate_actions`."""
    c, deps, state, seen, out = make(tmp_path, positions=HELD, closed=CLOSED)
    (state / "AUTO_ARMED").touch()
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    assert not any(x[0] == "corporate_actions" for x in c.calls)
    assert "corporate_actions" not in plan_of(state)
    assert "CORPORATE ACTIONS" not in "".join(out)


def test_halt_refuses_when_the_feed_cannot_be_read_and_names_the_error(tmp_path):
    from quantt.broker.alpaca import AlpacaHTTPError
    err = AlpacaHTTPError("GET /v1/corporate-actions failed after 5 attempts; last: HTTP 503",
                          status=503)
    c, deps, state, out = run(tmp_path, cam.HALT, ca_error=err)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert c.submits() == []
    plan = plan_of(state)
    detail = plan["refusals"][0]["detail"]
    assert plan["refusals"][0]["gate"] == "data"
    assert "UNMEASURED" in detail and "AlpacaHTTPError" in detail and "HTTP 503" in detail
    assert plan["corporate_actions"]["status"] == cam.UNMEASURED


def test_report_records_a_failed_read_as_unmeasured_never_clear_and_sends(tmp_path):
    from quantt.broker.alpaca import UnexpectedResponse
    c, deps, state, out = run(tmp_path, cam.REPORT, ca_error=UnexpectedResponse("bad shape"))
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    rec = plan_of(state)["corporate_actions"]
    assert rec["status"] == cam.UNMEASURED and "bad shape" in rec["why"]
    assert "UNMEASURED: UnexpectedResponse: bad shape" in "".join(out)


def test_halt_refuses_a_held_name_the_order_history_cannot_date(tmp_path):
    c, deps, state, out = run(tmp_path, cam.HALT, closed=[])
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert c.submits() == []
    assert "UNMEASURED" in plan_of(state)["refusals"][0]["detail"]
    assert not any(x[0] == "corporate_actions" for x in c.calls)


# ------------------------------------------------------- late-market decide / send

def test_late_decide_under_halt_is_refused_not_decided(tmp_path):
    c, deps, state, out = run(tmp_path, cam.HALT, events=[ev("CCC", D)], execution=LATE,
                              ck={"clock_ts": EVE})
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    plan = plan_of(state)
    assert plan["status"] == "refused" and c.submits() == []
    assert any(r["gate"] == "data" and "CCC" in r["detail"] for r in plan["refusals"])


def test_late_send_under_halt_refuses_an_action_listed_after_the_decide(tmp_path):
    """The evening decide saw nothing; by 15:53 Alpaca lists a split effective
    today. The send re-reads and refuses: zero transmits, the reason in send.json."""
    c, deps, state, out = run(tmp_path, cam.HALT, execution=LATE, ck={"clock_ts": EVE})
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_PLANNED
    c.events = [ev("CCC", D, i="late-listed")]
    to_send_time(c, deps)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert c.submits() == []
    send = json.loads((state / D.isoformat() / "send.json").read_text())
    assert any(r["gate"] == "data" and "late-listed" in r["detail"] for r in send["refusals"])
    assert send["corporate_actions"]["status"] == cam.BLOCKING
    assert ("orders", "closed", None) in c.calls[-40:]           # a fresh history read


def test_late_send_under_report_records_and_sends(tmp_path):
    c, deps, state, out = run(tmp_path, cam.REPORT, execution=LATE, ck={"clock_ts": EVE})
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_PLANNED
    c.events = [ev("CCC", D, i="late-listed")]
    to_send_time(c, deps)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    assert len(c.submits()) == 3
    send = json.loads((state / D.isoformat() / "send.json").read_text())
    assert send["refusals"] == [] and send["corporate_actions"]["status"] == cam.BLOCKING


def test_late_send_under_halt_refuses_when_the_history_read_fails(tmp_path):
    c, deps, state, out = run(tmp_path, cam.HALT, execution=LATE, ck={"clock_ts": EVE})
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_PLANNED
    to_send_time(c, deps)
    real = c.orders

    def orders(*, status, after=None, **kw):
        if status == "closed":
            raise ConnectionError("history unreachable")
        return real(status=status, after=after, **kw)
    c.orders = orders
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert c.submits() == []
    send = json.loads((state / D.isoformat() / "send.json").read_text())
    assert "history unreachable" in send["refusals"][0]["detail"]


def test_late_send_checks_the_plans_targets_not_only_the_held_names(tmp_path):
    """Review 2026-10-29 (a): at send, a target-only name (AAA: the plan buys
    it, the account holds none) listed with an action effective today refuses."""
    c, deps, state, out = run(tmp_path, cam.HALT, execution=LATE, ck={"clock_ts": EVE})
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_PLANNED
    assert "AAA" not in c._pos
    c.events = [ev("AAA", D, typ="reverse_split", i="target-split")]
    to_send_time(c, deps)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert c.submits() == []
    send = json.loads((state / D.isoformat() / "send.json").read_text())
    assert any("AAA (target)" in r["detail"] and "target-split" in r["detail"]
               for r in send["refusals"])


def _clock_reads(calls) -> int:
    return sum(1 for x in calls if x[0] == "clock")


def test_the_read_comes_before_the_gates_clock_read_at_decide_and_at_send(tmp_path):
    """Review 2026-10-29 (b): the slow read must come BEFORE the clock read the
    gate judges (gate 4 at decide, the late clock and send budget at send), so
    a slow read can only make the gate see a later time, never an earlier one.
    In each run, exactly one clock read (the session's first) precedes it."""
    c, deps, state, out = run(tmp_path, cam.HALT, execution=LATE, ck={"clock_ts": EVE})
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_PLANNED
    assert _clock_reads(c.calls[:c.ca_at]) == 1
    assert _clock_reads(c.calls[c.ca_at:]) >= 1                     # the gate's, after it
    n0 = len(c.calls)
    to_send_time(c, deps)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    assert _clock_reads(c.calls[n0:c.ca_at]) == 1
    first_submit = next(i for i, x in enumerate(c.calls) if x[0] == "submit")
    assert _clock_reads(c.calls[c.ca_at:first_submit]) >= 2         # the gate's, then the POST's


def test_late_send_with_the_key_absent_writes_the_same_send_json_keys(tmp_path):
    c, deps, state, seen, out = make(tmp_path, clock_ts=EVE, execution=LATE, positions=HELD,
                                     closed=CLOSED)
    (state / "AUTO_ARMED").touch()
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_PLANNED
    to_send_time(c, deps)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    send = json.loads((state / D.isoformat() / "send.json").read_text())
    assert "corporate_actions" not in send
    assert sum(1 for x in c.calls if x[:2] == ("orders", "closed")) == 1   # the decide's only


# ------------------------------------------- with the multi-sleeve combiner ON (combine.py)
#
# The combiner (main, 2026-10-28; dark) decides each sleeve on its own spec and
# nets their targets into ONE decide. The gate must see every name ANY sleeve
# wants, and every held name from the broker, and nothing on that path may skip
# it. The sleeves are test_combine's fakes with fixed weights; the account is
# CAClient (test_run.FakeClient plus the corporate-action read).

def run_combined(tmp_path, mode, sleeves, *, events=(), positions=None, closed=None,
                 clock=None, execution=None):
    from quantt.session.tests.test_combine import CL, MORNING
    clock = clock or MORNING
    c = CAClient(tmp_path / "state", events=events, positions=positions or {},
                 closed=closed or [], clock_ts=clock)
    c, deps, state, _, out = make(
        tmp_path, client=c, now_utc=clock.astimezone(dt.timezone.utc),
        execution=execution or {"mode": "cls", "bp_shortfall": "scale"},
        closes=lambda asof, uni: {s: (CL[s], ASOF) for s in uni})
    deps.sleeves, deps.corp_actions = tuple(sleeves), mode
    (state / "AUTO_ARMED").touch()
    return c, deps, state, out


def _two_sleeves():
    from quantt.session.tests.test_combine import sleeve
    return (sleeve("A", ("AAA", "BBB"), {"AAA": 0.05}),          # A buys AAA; BBB flat
            sleeve("B", ("CCC", "DDD"), {"DDD": -0.04}))         # B shorts DDD; CCC flat


def test_combined_book_halts_on_a_target_in_the_second_sleeve(tmp_path):
    """DDD is wanted only by sleeve B and held by no one: an action on it
    effective on the session date refuses the combined session, zero sent."""
    from quantt.session.tests.test_combine import BOOK_SPEC
    c, deps, state, out = run_combined(tmp_path, cam.HALT, _two_sleeves(),
                                       events=[ev("DDD", D, i="ddd-split")])
    assert rn.run_session(BOOK, BOOK_SPEC, deps) == rn.EXIT_REFUSED
    assert c.submits() == []
    plan = plan_of(state)
    assert "combine" in plan
    assert any(r["gate"] == "data" and "DDD (target)" in r["detail"] and "ddd-split" in r["detail"]
               for r in plan["refusals"])


def test_combined_book_halts_on_a_held_name_in_the_first_sleeve(tmp_path):
    """BBB sits in sleeve A's universe, held at the broker (the gate's held names
    come from positions, not from any sleeve), and sleeve A wants it flat."""
    from quantt.session.tests.test_combine import BOOK_SPEC
    closed = [{"client_order_id": "cef-20260922-BBB-1", "symbol": "BBB", "filled_qty": "50",
               "submitted_at": "2026-09-21T23:30:00Z"}]
    c, deps, state, out = run_combined(tmp_path, cam.HALT, _two_sleeves(),
                                       positions={"BBB": 50}, closed=closed,
                                       events=[ev("BBB", dt.date(2026, 9, 24), i="bbb-split")])
    assert rn.run_session(BOOK, BOOK_SPEC, deps) == rn.EXIT_REFUSED
    assert c.submits() == []
    assert any("BBB (held)" in r["detail"] for r in plan_of(state)["refusals"])


def test_combined_book_with_no_action_sends_and_records_every_sleeves_names(tmp_path):
    from quantt.session.tests.test_combine import BOOK_SPEC
    c, deps, state, out = run_combined(tmp_path, cam.HALT, _two_sleeves())
    assert rn.run_session(BOOK, BOOK_SPEC, deps) == rn.EXIT_SENT
    plan = plan_of(state)
    assert plan["corporate_actions"]["status"] == cam.CLEAR
    assert sorted(plan["corporate_actions"]["names"]) == ["AAA", "DDD"]
    assert sorted(o["symbol"] for o in c.accepted.values()) == ["AAA", "DDD"]


def test_combined_book_a_name_two_sleeves_net_to_zero_still_blocks(tmp_path, monkeypatch):
    """Behind combine.SHARED_SYMBOLS_ALLOWED (off today): A +0.04 and B -0.04 in
    BBB net to 0, so the netted decision wants nothing in BBB and nobody holds
    it. Each sleeve still sized its plan on BBB, so an action on it blocks."""
    from quantt.session import combine as cmb
    from quantt.session.tests.test_combine import BOOK_SPEC, sleeve
    monkeypatch.setattr(cmb, "SHARED_SYMBOLS_ALLOWED", True)
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05, "BBB": 0.04})
    b = sleeve("B", ("BBB", "CCC"), {"BBB": -0.04, "CCC": -0.03})
    c, deps, state, out = run_combined(tmp_path, cam.HALT, (a, b),
                                       events=[ev("BBB", D, i="bbb-netted")])
    assert rn.run_session(BOOK, BOOK_SPEC, deps) == rn.EXIT_REFUSED
    plan = plan_of(state)
    assert plan["targets"]["BBB"]["target"] == 0                   # the net
    assert any("BBB (target)" in r["detail"] for r in plan["refusals"])


def test_combined_late_send_a_name_two_sleeves_net_to_zero_still_blocks(tmp_path, monkeypatch):
    """Third review, 2026-10-29: the SEND's per-sleeve read, pinned. The decide
    is clear; by 15:52 Alpaca lists an action on BBB, which A (+0.04) and B
    (-0.04) net to zero, so the saved plan's netted targets do not hold it.
    Only the sleeves' own targets in plan.json's `combine` carry it there."""
    from quantt.session import combine as cmb
    from quantt.session.tests.test_combine import BOOK_SPEC, sleeve
    monkeypatch.setattr(cmb, "SHARED_SYMBOLS_ALLOWED", True)
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05, "BBB": 0.04})
    b = sleeve("B", ("BBB", "CCC"), {"BBB": -0.04, "CCC": -0.03})
    eve = dt.datetime(2026, 9, 28, 22, 0, tzinfo=rn.gt.ET)
    c, deps, state, out = run_combined(tmp_path, cam.HALT, (a, b), clock=eve,
                                       execution={**LATE, "bp_shortfall": "scale"})
    assert rn.run_session(BOOK, BOOK_SPEC, deps) == rn.EXIT_PLANNED
    plan = plan_of(state)
    assert plan["targets"]["BBB"]["target"] == 0 and "combine" in plan
    c.events = [ev("BBB", D, i="bbb-netted-late")]
    to_send_time(c, deps, dt.datetime(2026, 9, 29, 15, 52, 30, tzinfo=rn.gt.ET))
    assert rn.run_session(BOOK, BOOK_SPEC, deps) == rn.EXIT_REFUSED
    assert c.submits() == []
    send = json.loads((state / D.isoformat() / "send.json").read_text())
    assert any("BBB (target)" in r["detail"] and "bbb-netted-late" in r["detail"]
               for r in send["refusals"])


def test_combined_late_send_rechecks_every_sleeves_targets(tmp_path):
    """The evening decide is clear; by 15:52 Alpaca lists an action on DDD,
    which only sleeve B wants. The send refuses: zero transmits."""
    from quantt.session.tests.test_combine import BOOK_SPEC
    eve = dt.datetime(2026, 9, 28, 22, 0, tzinfo=rn.gt.ET)
    c, deps, state, out = run_combined(tmp_path, cam.HALT, _two_sleeves(), clock=eve,
                                       execution={**LATE, "bp_shortfall": "scale"})
    assert rn.run_session(BOOK, BOOK_SPEC, deps) == rn.EXIT_PLANNED
    assert "combine" in plan_of(state)
    c.events = [ev("DDD", D, i="ddd-late")]
    to_send_time(c, deps, dt.datetime(2026, 9, 29, 15, 52, 30, tzinfo=rn.gt.ET))
    assert rn.run_session(BOOK, BOOK_SPEC, deps) == rn.EXIT_REFUSED
    assert c.submits() == []
    send = json.loads((state / D.isoformat() / "send.json").read_text())
    assert any("DDD (target)" in r["detail"] and "ddd-late" in r["detail"]
               for r in send["refusals"])
