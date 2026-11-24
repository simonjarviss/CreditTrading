"""C4's corporate-action gate on a replica of the three unresolved rows of 2026-11-02: `halt` measured, `report` deployed.

WHY THIS EXISTS (2026-11-02). The core's release-check on 3478159 found three
market-wide rows in Alpaca's real corporate-action feed with a party symbol
missing, and under the team lead's 2026-11-02 unresolved-rows ruling each one
halts for every held fund, so the core shipped with its gate in `report`
(ops/books/cef_discount_book.json `_mode_report_note`). C4's book json then
kept `halt`, and this file measured what that would do to C4's dry sessions.

THE RULING IT INFORMED (team lead, 2026-11-02). C4's gate runs in REPORT, the
same as the core, until the ISIN fix and the re-ruling of the unresolved rows
land (ops/books/c4_families_book.json `_mode_report_note`, which says how to
RESTORE halt). `test_the_deployed_c4_book_sets_report_until_the_unresolved_rows_are_re_ruled`
pins that. The measurements below still name `halt` explicitly, because halt
is what the RESTORE line brings back, and they show what it will do then.

THE REPLICA. The three rows as the core's gate recorded them in its preview of
session 2026-11-03 (as-of 2026-11-02, read 2026-11-02 23:34-00:14Z, the record's
`unresolved` list; [V] on that date only):

  db0847b7-9523-4b2f-afba-ae51ddb77ec5  partial_call  symbol missing (subject)
      process_date 2026-10-30 (its market date; the type has no other)
  e34ddd44-1ed2-4b30-b668-be3f16e11dce  spin_off      new_symbol missing (new);
      source SNTI; ex_date 2026-10-30, process_date 2026-11-02
  6abeb209-f747-4bf3-a231-67b8c0984d4a  stock_merger  acquiree_symbol missing
      (acquiree); acquirer JAGX; effective and process date 2026-11-02

Ids, types, dates, the missing field and the present symbols are the record's.
Every other field (CUSIPs, rates, the call's price and lottery dates) is a
synthetic placeholder that passes the read's validators. A missing symbol is
`null`, which the read treats as "" (AlpacaClient.corporate_actions,
UNRESOLVED ROWS). The rows go through the REAL `AlpacaClient.corporate_actions`
parser over a fake HTTP session, then the runner's own step 3b
(`run._corporate_actions`), with C4's universe, state dir and book name, under
the mode each test names. Synthetic data: this is a statement about the code, not
about what Alpaca will list.

WHAT IT MEASURES. A FLAT C4 account (the dry sessions: DRY_RUN=1 sends nothing,
so the account the team lead says has never traded stays flat [U: not read
here]) gives every name the target-only window [as-of, session]: a missing
party is treated as each of those names, so a row blocks only while its date is
inside that window (corp_actions.blocking_events, UNRESOLVED ROWS). Of the three,
only the JAGX merger blocks, and only the session of 2026-11-03. A HELD account
(after arming) reaches back to each name's last fill (THE WINDOW), so all three
block every session until the team lead acknowledges each (`ca-ack`) or every
held name is traded after them, which under `halt` nothing does.

Hermetic: netguard refuses any socket; the key file holds test constants.
"""
import datetime as dt
import json
from types import SimpleNamespace

import pytest

from ops.schedule.nyse_calendar import is_trading_day, next_trading_day, previous_trading_day
from quantt.broker import alpaca as al
from quantt.session import corp_actions as cam
from quantt.session import run as rn
from quantt.tests.test_alpaca_client import KEY_ID, SECRET, FakeResp, FakeSession, route

ET = rn.gt.ET
PARTIAL_CALL = "db0847b7-9523-4b2f-afba-ae51ddb77ec5"
SNTI_SPIN = "e34ddd44-1ed2-4b30-b668-be3f16e11dce"
JAGX_MERGER = "6abeb209-f747-4bf3-a231-67b8c0984d4a"
REPLICA = {
    "partial_calls": [{"cusip": "SYNTH0001", "id": PARTIAL_CALL, "lottery_date": "2026-10-22",
                       "lottery_type": "original", "payable_date": "2026-10-30", "price": 1000,
                       "process_date": "2026-10-30", "record_date": "2026-10-21", "symbol": None}],
    "spin_offs": [{"ex_date": "2026-10-30", "id": SNTI_SPIN, "new_cusip": "SYNTH0002",
                   "new_rate": 1, "new_symbol": None, "payable_date": "2026-10-30",
                   "process_date": "2026-11-02", "record_date": "2026-10-29",
                   "source_cusip": "SYNTH0003", "source_rate": 1, "source_symbol": "SNTI"}],
    "stock_mergers": [{"acquiree_cusip": "SYNTH0004", "acquiree_rate": 1, "acquiree_symbol": None,
                       "acquirer_cusip": "SYNTH0005", "acquirer_rate": 1, "acquirer_symbol": "JAGX",
                       "effective_date": "2026-11-02", "id": JAGX_MERGER,
                       "process_date": "2026-11-02"}],
}
ALL3 = {PARTIAL_CALL, SNTI_SPIN, JAGX_MERGER}
# The trading sessions after the rows, through the end of the next week: the window
# in which the first dry sessions can fall (the installer refuses 15:30-16:00 ET).
SESSIONS = [d for d in (dt.date(2026, 11, 3) + dt.timedelta(days=i) for i in range(11))
            if is_trading_day(d)]


def _c4():
    return rn.BOOKS["c4"]


def _universe():
    return rn.spec_params(rn.load_spec(_c4().spec_path))["universe"]


def _parser(tmp_path, feed=REPLICA):
    """The real AlpacaClient corporate-action read, as C4's client builds it, over a
    fake HTTP session serving `feed` (one page)."""
    kf = tmp_path / "alpaca-test.env"              # test constants, never config/.env
    kf.write_text(f"ALPACA_C4_KEY_ID={KEY_ID}\nALPACA_C4_SECRET_KEY={SECRET}\n")
    session = FakeSession(route({"/v1/corporate-actions": lambda p: FakeResp(
        200, {"corporate_actions": feed, "next_page_token": None})}))
    return al.AlpacaClient("c4", kf, session=session, sleep=lambda s: None)


def _held_since_oct20(names):
    """{name: 10 shares} and one filled order each, submitted 2026-10-20 (L_X 2026-10-19)."""
    pos = {s: 10 for s in names}
    closed = [{"client_order_id": f"c4-20261020-{s}-1", "symbol": s, "side": "buy",
               "status": "filled", "filled_qty": "10", "submitted_at": "2026-10-20T19:53:00Z"}
              for s in names]
    return pos, closed


def _step_3b(tmp_path, session_date, positions, closed, targets, mode=cam.HALT):
    """run._corporate_actions for C4 under `mode`: (record, refusal or None)."""
    deps = SimpleNamespace(corp_actions=mode,
                           client=SimpleNamespace(corporate_actions=_parser(tmp_path).corporate_actions))
    state = tmp_path / "c4"
    state.mkdir(exist_ok=True)
    rec, refusal, _ = rn._corporate_actions(
        deps, lambda: closed, positions, targets, previous_trading_day(session_date), session_date,
        universe=_universe(), state=state, book_name="c4")
    return rec, refusal


def test_the_deployed_c4_book_sets_report_until_the_unresolved_rows_are_re_ruled():
    """Team lead 2026-11-02: C4's gate in REPORT, the same as the core, until the ISIN fix
    and the re-ruling of the unresolved rows land (this file's measurements decided it).
    The book json says how to restore halt; this pin makes the switch back a visible,
    tested edit (test_corp_actions.py pins the core's the same way). Fails on ebb73ab."""
    assert rn.corporate_actions_for(_c4()) == cam.REPORT
    block = json.loads(_c4().book_path.read_text())["corporate_actions"]
    note = block["_mode_report_note"]
    assert "RESTORE" in note and "halt" in note and "together with the core" in note
    assert rn.corporate_actions_for(rn.BOOKS["cef"]) == cam.REPORT      # the core's, as the note says


def test_report_mode_records_the_same_rows_and_never_refuses(tmp_path):
    """The deployed mode on the same replica: every session's record lists the rows halt
    would block (flat: the JAGX merger on 11-03; held: all three), and none refuses."""
    names = sorted(_universe())[:10]
    pos, closed = _held_since_oct20(names)
    for d in SESSIONS:
        rec, refusal = _step_3b(tmp_path, d, {}, [], sorted(_universe()), mode=cam.REPORT)
        assert refusal is None and rec["mode"] == cam.REPORT
        assert {b["id"] for b in rec["blocking"]} == ({JAGX_MERGER} if d == dt.date(2026, 11, 3)
                                                     else set())
        rec, refusal = _step_3b(tmp_path, d, pos, closed, names, mode=cam.REPORT)
        assert refusal is None and {b["id"] for b in rec["blocking"]} == ALL3


@pytest.mark.parametrize("targets", ["all 74", "one name"])
def test_flat_c4_halt_refuses_only_the_session_of_the_jagx_merger(tmp_path, targets):
    """The dry sessions: nothing held. Only 2026-11-03 (as-of 11-02) refuses, on the JAGX
    merger's missing acquiree (effective 11-02, inside [11-02, 11-03]); from 11-04 the three
    are recorded only. Which names are targeted does not matter: every target-only name has
    the same window."""
    uni = _universe()
    tg = sorted(uni) if targets == "all 74" else sorted(uni)[:1]
    got = {}
    for d in SESSIONS:
        rec, refusal = _step_3b(tmp_path, d, {}, [], tg)
        assert {u["id"] for u in rec["unresolved"]} == ALL3, rec.get("unresolved")
        got[d] = ({b["id"] for b in rec["blocking"]}, refusal is not None)
        assert {u["id"] for u in rec["unresolved"] if u["blocks"]} == got[d][0]
    assert got[dt.date(2026, 11, 3)] == ({JAGX_MERGER}, True)
    assert all(got[d] == (set(), False) for d in SESSIONS if d != dt.date(2026, 11, 3)), got
    rec, refusal = _step_3b(tmp_path, dt.date(2026, 11, 3), {}, [], tg)
    assert JAGX_MERGER in refusal and "UNRESOLVED" in refusal
    assert PARTIAL_CALL not in refusal and SNTI_SPIN not in refusal


def test_held_c4_halt_refuses_every_session_on_all_three(tmp_path):
    """After arming: names held since a fill submitted 2026-10-20. Each held name's long
    window reaches back to 2026-10-19, so every one of the three rows blocks every session
    measured, as the core's did; under `halt` nothing trades, so nothing moves L_X."""
    names = sorted(_universe())[:10]
    pos, closed = _held_since_oct20(names)
    for d in SESSIONS:
        rec, refusal = _step_3b(tmp_path, d, pos, closed, names)
        assert {b["id"] for b in rec["blocking"]} == ALL3, (d, rec["blocking"][:2])
        assert refusal is not None and all(i in refusal for i in ALL3)


# ------------------------------------------------- the C4 runner end to end, DRY

def _dry_decide(tmp_path, monkeypatch, asof: dt.date, mode=None):
    """One evening DRY decide of the C4 book, built by default_deps from its book json on
    test_c4_book's generated panel (ending `asof`), with C4's client reading the replica
    through the real parser. `mode` overrides the book json's gate mode (None: as deployed).
    (exit code, plan.json)."""
    from quantt.session.tests import test_c4_book as t4
    from quantt.session.tests.test_run import FakeClient
    from src.deploy.sleeves import cef_discount as cefmod
    root = tmp_path / "repo"
    monkeypatch.setattr(t4, "ASOF", asof)                 # the generated panel ends at `asof`
    t4._write_c4_panel(root / "data" / "cef_c4")
    monkeypatch.setattr(cefmod, "REPO", root)
    for name in ("PX_PATH", "NAV_PATH", "GRP_PATH"):     # the core's panel: absent
        monkeypatch.setattr(cefmod, name, root / "data/cef" / "absent.parquet")
    monkeypatch.setitem(rn.DATA_BOOK_DIRS, "c4", root / "data" / "cef_c4")
    now = dt.datetime.combine(asof, dt.time(22, 0), tzinfo=ET)
    state = tmp_path / "quantt_state" / "c4"
    state.mkdir(parents=True)
    parser = _parser(tmp_path)

    class C(FakeClient):
        def corporate_actions(self, symbols, start, end, **kw):
            return parser.corporate_actions(symbols, start, end, **kw)

    c = C(state, clock_ts=now)
    monkeypatch.setattr(al.AlpacaClient, "from_environment", classmethod(lambda cls, n, **kw: c))
    spec = rn.load_spec(_c4().spec_path)
    deps = rn.default_deps(_c4(), spec, {"QUANTT_ENV_FILE": "unused"})
    if mode is not None:
        deps.corp_actions = mode
    deps.env = {"QUANTT_STATE_DIR": str(state), "DRY_RUN": "1"}
    deps.refresh = lambda a, t: rn.RefreshResult(exit=0, tail="fixture")
    deps.halts = lambda: []
    deps.utcnow = lambda: now.astimezone(dt.timezone.utc)
    deps.out = type("Quiet", (), {"write": lambda self, s: None, "flush": lambda self: None})()
    code = rn.run_session(_c4(), spec, deps)
    session = next_trading_day(asof)
    plan = json.loads((state / session.isoformat() / "plan.json").read_text())
    assert c.submits() == []                                   # DRY: nothing reaches the broker
    return code, plan


def test_under_halt_the_c4_dry_decide_refuses_on_the_merger_and_plans_the_next_day(
        tmp_path, monkeypatch):
    """The same answer through the whole runner, under halt (the RESTORE target): the
    evening decide for 2026-11-03 is REFUSED (exit 11), a gate-5 `data` refusal naming the
    JAGX row; the one for 2026-11-04 is PLANNED (exit 6), the three rows in the record as
    unresolved, blocking nothing."""
    code, plan = _dry_decide(tmp_path / "a", monkeypatch, dt.date(2026, 11, 2), mode=cam.HALT)
    assert code == rn.EXIT_REFUSED and plan["status"] == "refused"
    assert [r["gate"] for r in plan["refusals"]] == ["data"]
    assert JAGX_MERGER in plan["refusals"][0]["detail"]
    assert plan["corporate_actions"]["mode"] == "halt"
    code, plan = _dry_decide(tmp_path / "b", monkeypatch, dt.date(2026, 11, 3), mode=cam.HALT)
    assert code == rn.EXIT_PLANNED and plan["status"] == "decided", plan["refusals"]
    ca = plan["corporate_actions"]
    assert ca["status"] == "CLEAR" and ca["blocking"] == []
    assert {u["id"] for u in ca["unresolved"]} == ALL3 and not any(u["blocks"] for u in ca["unresolved"])


def test_as_deployed_the_c4_dry_decide_plans_and_records_the_merger(tmp_path, monkeypatch):
    """The book json as deployed (report): the evening decide for 2026-11-03 is PLANNED
    (exit 6) with no refusal, and its record carries the JAGX row as BLOCKING, recorded
    only, with the three listed as unresolved."""
    code, plan = _dry_decide(tmp_path, monkeypatch, dt.date(2026, 11, 2))
    assert code == rn.EXIT_PLANNED and plan["status"] == "decided" and plan["refusals"] == []
    ca = plan["corporate_actions"]
    assert ca["mode"] == "report" and ca["status"] == "BLOCKING"
    assert {b["id"] for b in ca["blocking"]} == {JAGX_MERGER}
    assert {u["id"] for u in ca["unresolved"]} == ALL3
