"""C4's first armed session opens at full target in the shared spare account, and is refused only when the account is not clean.

WHY. The runner trades a book's first session to FULL target only when
`run.is_opening_session` is True (team lead 2026-09-28). C4 trades the EXISTING spare
paper account (no new account, ruled 2026-11-02; the opening rule below is the team lead's
2026-11-03 "just flat it", docs/SYSTEM.md section 5, PR #30), which the research loop may also
trade (CLAUDE.md rule 1's 2026-10-27 exception). Under the default rule ("any": no
position and no order EVER filled) the loop's past fills there, even flattened, would
open C4 from flat at the band EDGE: 28-42% of target and net long +4.7% to +11.1% (the
release-check of 336df9d, data/cef_families to 2026-10-09, spec v4), session after
session. So C4's book json sets `execution.opening_session_fills = "own_prefix"`: only
fills carrying C4's own order-id prefix count; POSITIONS count whatever their origin.
And the first-session gate (`run.OPENING_REQUIRED_BOOKS`) refuses an ARMED first session
that is not an opening one under that rule (a position) or that has another runner's
open order in the account; unarmed it records and prints only. The core sets no key:
its rule is "any" and it reads and records nothing new.

Every test here fails on f7f7be5 (no rule key, no gate: the armed send transmitted the
band-edge book). The core's decide is proved byte-identical by its pins
(test_panels_noop.py, built by default_deps from the core's book json, made on 862b1d0;
test_combine_noop, test_missing_nav_hold, test_sizing_multiplier_noop), unchanged.

Hermetic: test_c4_book's generated 74-fund panel under tmp_path (its `c4_world`),
test_run's FakeClient for the broker, netguard on; data/ is never written.
"""
import datetime as dt
import json

from quantt.session import run as rn
from quantt.session.tests.test_c4_book import EVE, SEND, SESSION, _c4, _spec, c4_world  # noqa: F401
from quantt.session.tests.test_run import FakeClient

# Two fills the research loop made in the shared account, both since flattened, and
# a cancel: a history like the one the arming read cannot see in positions.
LAB_FILLS = [
    {"id": "f1", "client_order_id": "lab-20260921-ADX-1", "symbol": "ADX", "side": "buy",
     "status": "filled", "filled_qty": "10", "submitted_at": "2026-09-21T19:53:00Z"},
    {"id": "f2", "client_order_id": "lab-20260924-ADX-2", "symbol": "ADX", "side": "sell",
     "status": "filled", "filled_qty": "10", "submitted_at": "2026-09-24T19:54:00Z"},
    {"id": "c1", "client_order_id": "lab-20260924-EVT-1", "symbol": "EVT", "side": "buy",
     "status": "canceled", "filled_qty": "0", "submitted_at": "2026-09-24T19:55:00Z"},
]


def _client(state, now, closed, positions=None, open_=None):
    class C(FakeClient):
        # **kw: main's corporate-action read passes `universe`, `skipped` (and `rows`).
        def corporate_actions(self, symbols, start, end, **kw):
            return []
    return C(state, clock_ts=now, closed=list(closed), positions=dict(positions or {}),
             open_=list(open_ or []))


def _session(state, now, monkeypatch, *, closed=(), armed: bool, positions=None, open_=None,
             key_absent: bool = False):
    """One C4 run built by default_deps from its book json on the fixture panel: the
    evening decide at EVE or the late-market send at SEND. Armed: DRY_RUN=0 and AUTO_ARMED
    in C4's state dir. `key_absent`: the book json's opening_session_fills as if deleted
    (its REVERT), i.e. the default "any" rule. Returns (exit, client)."""
    from quantt.broker import alpaca
    c = _client(state, now, closed, positions, open_)
    monkeypatch.setattr(alpaca.AlpacaClient, "from_environment",
                        classmethod(lambda cls, name, **kw: c))
    spec = _spec()
    deps = rn.default_deps(_c4(), spec, {"QUANTT_ENV_FILE": "unused"})
    assert deps.opening_session_fills == "own_prefix"           # C4's book json, as shipped
    if key_absent:
        deps.opening_session_fills = None
    deps.env = {"QUANTT_STATE_DIR": str(state), "DRY_RUN": "0" if armed else "1"}
    if armed:
        (state / "AUTO_ARMED").touch()
    deps.refresh = lambda a, t: rn.RefreshResult(exit=0, tail="fixture")
    deps.halts = lambda: []
    deps.utcnow = lambda: now.astimezone(dt.timezone.utc)
    deps.out = type("Quiet", (), {"write": lambda self, s: None, "flush": lambda self: None})()
    return rn.run_session(_c4(), spec, deps), c


def _state(tmp_path):
    state = tmp_path / "quantt_state" / "c4"
    state.mkdir(parents=True)
    return state


def _read(state, name):
    return json.loads((state / SESSION / name).read_text())


def _gross(plan):
    return sum(abs(o["qty"]) * float(plan["closes"][o["symbol"]]) for o in plan["orders"])


def _decide(tmp_path, monkeypatch, expect=rn.EXIT_PLANNED, **kw):
    state = _state(tmp_path)
    code, c = _session(state, EVE, monkeypatch, **kw)
    assert code == expect, _read(state, "plan.json")["refusals"]
    assert c.submits() == []                            # a late-market decide never sends
    return state, _read(state, "plan.json")


def _first_session_refusal(refusals):
    """The one first-session refusal: under its OWN gate name since the release-check of
    4f759a9 (it was `arming`, which verify counts as a human's choice)."""
    (r,) = [r for r in refusals if "first armed session" in r["detail"]]
    assert r["gate"] == "first_session", r
    return r


# ----------------------------------------------------- key ABSENT: today's rule

def test_key_absent_the_cores_rule_is_todays_and_it_reads_nothing_new():
    """The core sets no key: "any", today's is_opening_session, the same answer on every
    case; and it is not in OPENING_REQUIRED_BOOKS, so nothing is read or recorded for it."""
    core = rn.BOOKS["cef"]
    assert rn.opening_session_fills_for(core) is None
    assert rn.OPENING_REQUIRED_BOOKS == {"c4"}
    own = {"client_order_id": f"{core.cid_prefix}-20260929-PDI-1", "filled_qty": "1",
           "submitted_at": "2026-09-29T19:53:00Z"}
    for pos, closed in (({}, []), ({}, LAB_FILLS), ({"PDI": 1}, []), ({}, [own])):
        assert rn.is_opening_session(pos, closed) == rn.is_opening_session(
            pos, closed, fills=rn.OPENING_FILLS_ANY, cid_prefix=core.cid_prefix)
    assert rn.is_opening_session({}, LAB_FILLS) is False          # today's rule counts any fill
    assert rn.first_session_check(core, {}, LAB_FILLS, [], None) is None
    assert rn.first_session_gate(core, None, True) == (None, None, [])


def test_key_absent_c4_keeps_the_old_band_edge_open_and_armed_it_is_refused(
        c4_world, monkeypatch, tmp_path):
    """C4 with the key deleted (its REVERT) on the loop's two flattened fills: not an
    opening session, so the decide plans the band-edge book; armed, the decide itself
    refuses (gate `first_session`), naming the fills. Decided unarmed and armed by the
    15:52 send, the send refuses it and sends nothing."""
    state, plan = _decide(tmp_path / "armed", monkeypatch, expect=rn.EXIT_REFUSED,
                          closed=LAB_FILLS, armed=True, key_absent=True)
    assert plan["status"] == "refused" and plan["opening_session"] is False
    assert plan["first_session"]["fills_rule"] == "any"
    r = _first_session_refusal(plan["refusals"])
    assert "2 filled order(s)" in r["detail"] and "2026-09-24" in r["detail"]
    state, plan = _decide(tmp_path / "late", monkeypatch, closed=LAB_FILLS, armed=False,
                          key_absent=True)
    code, c = _session(state, SEND, monkeypatch, closed=LAB_FILLS, armed=True, key_absent=True)
    assert code == rn.EXIT_REFUSED and c.submits() == []
    _first_session_refusal(_read(state, "send.json")["refusals"])


# ----------------------------------------------------- key SET ("own_prefix"), as shipped

def test_key_set_foreign_fills_only_open_at_full_target_not_the_band_edge(
        c4_world, monkeypatch, tmp_path):
    """Today's fixture, the loop's two flattened fills and a flat account: with C4's key
    the session IS an opening one and plans exactly the fresh account's full-target book;
    with the key absent it plans the band-edge book, smaller. Armed, the full-target send
    goes."""
    _, fresh = _decide(tmp_path / "fresh", monkeypatch, armed=True)
    state, keyed = _decide(tmp_path / "keyed", monkeypatch, closed=LAB_FILLS, armed=True)
    _, edge = _decide(tmp_path / "edge", monkeypatch, closed=LAB_FILLS, armed=False, key_absent=True)
    assert fresh["opening_session"] is True and keyed["opening_session"] is True
    assert edge["opening_session"] is False
    assert keyed["orders"] == fresh["orders"] and keyed["plan_sha"] == fresh["plan_sha"]
    assert keyed["orders"] != edge["orders"] and _gross(edge) < _gross(keyed)
    fs = keyed["first_session"]
    assert (fs["action"], fs["fills_rule"], fs["foreign_fills"]) == ("clear", "own_prefix", 2)
    code, c = _session(state, SEND, monkeypatch, closed=LAB_FILLS, armed=True)
    assert code == rn.EXIT_SENT and c.submits(), _read(state, "send.json")["refusals"]


def test_key_set_a_c4_fill_is_not_an_opening_and_spends_the_gate():
    """A fill with C4's own prefix: its first session is behind it. Not an opening session
    (by design: later sessions trade from the band edge), and the gate reads nothing."""
    b = rn.BOOKS["c4"]
    own = {"client_order_id": f"{b.cid_prefix}-20260929-ADX-1", "symbol": "ADX",
           "filled_qty": "3", "submitted_at": "2026-09-29T19:53:00Z"}
    rule = rn.opening_session_fills_for(b)
    assert rule == "own_prefix"
    assert rn.is_opening_session({}, LAB_FILLS, fills=rule, cid_prefix=b.cid_prefix) is True
    assert rn.is_opening_session({}, [*LAB_FILLS, own], fills=rule, cid_prefix=b.cid_prefix) is False
    assert rn.first_session_check(b, {"ADX": 3}, [*LAB_FILLS, own], [], rule) is None


def test_key_set_a_foreign_position_is_refused_when_armed_and_reported_when_not(
        c4_world, monkeypatch, tmp_path):
    """Positions count whatever their origin: a position the loop left in the account
    makes the session not an opening one under either rule. Armed, refused before any
    order (at the decide, and at a send armed after an unarmed decide); unarmed,
    reported only."""
    pos, closed = {"ADX": 10}, LAB_FILLS[:1]            # the loop bought and never sold
    state, plan = _decide(tmp_path / "armed", monkeypatch, expect=rn.EXIT_REFUSED,
                          closed=closed, positions=pos, armed=True)
    assert plan["opening_session"] is False and plan["first_session"]["action"] == "refused"
    assert "1 position(s)" in _first_session_refusal(plan["refusals"])["detail"]
    state, plan = _decide(tmp_path / "late", monkeypatch, closed=closed, positions=pos, armed=False)
    code, c = _session(state, SEND, monkeypatch, closed=closed, positions=pos, armed=True)
    assert code == rn.EXIT_REFUSED and c.submits() == []
    assert "1 position(s)" in _first_session_refusal(_read(state, "send.json")["refusals"])["detail"]
    state, plan = _decide(tmp_path / "dry", monkeypatch, closed=closed, positions=pos, armed=False)
    assert plan["first_session"]["action"] == "reported"
    code, c = _session(state, SEND, monkeypatch, closed=closed, positions=pos, armed=False)
    assert code == rn.EXIT_DRY and c.submits() == []
    assert not any("first armed session" in r["detail"] for r in _read(state, "send.json")["refusals"])


def test_key_set_another_runners_open_order_is_refused_when_armed():
    """An open order that is not C4's (the loop's, say) in the account: armed, refused."""
    b = rn.BOOKS["c4"]
    lab_open = [{"client_order_id": "lab-20261103-ADX-1", "symbol": "ADX", "status": "new"}]
    chk = rn.first_session_check(b, {}, LAB_FILLS, lab_open, rn.opening_session_fills_for(b))
    assert chk["opening"] is True and chk["foreign_open_orders"] == 1
    rec, refusal, _ = rn.first_session_gate(b, chk, armed=True)
    assert rec["action"] == "refused" and "1 open order(s) not c4's" in refusal
    rec, refusal, _ = rn.first_session_gate(b, chk, armed=False)
    assert rec["action"] == "reported" and refusal is None


def test_the_book_json_key_reads_and_refuses_a_wrong_value(tmp_path):
    b = rn.BOOKS["c4"]
    book = json.loads(b.book_path.read_text())
    assert book["execution"]["opening_session_fills"] == "own_prefix"
    assert "REVERT" in book["execution"]["_opening_session_fills_note"]
    book["execution"]["opening_session_fills"] = "own"
    bad = tmp_path / "c4_families_book.json"
    bad.write_text(json.dumps(book))
    import pytest
    with pytest.raises(rn.SessionError, match="opening_session_fills"):
        rn.opening_session_fills_for(rn.Book(b.name, b.cid_prefix, b.spec_path, bad))
    del book["execution"]["opening_session_fills"]
    bad.write_text(json.dumps(book))
    assert rn.opening_session_fills_for(rn.Book(b.name, b.cid_prefix, b.spec_path, bad)) is None


# ----------------------------------------------- release-check of 4f759a9 (2026-11-03)

def test_an_unreadable_open_order_list_is_unmeasured_and_armed_it_refuses():
    """quant-reviewer 2: gate 6's open-order read failed, and the check recorded CLEAR.
    Fail-open is wrong (CLAUDE.md: no silent fallbacks): UNMEASURED, naming the read;
    armed, refused; unarmed, recorded only. Fails on 61589a8 (CLEAR, no refusal)."""
    b = rn.BOOKS["c4"]
    why = "AlpacaHTTPError: GET /v2/orders -> HTTP 503"
    chk = rn.first_session_check(b, {}, LAB_FILLS, None, rn.opening_session_fills_for(b), why)
    assert chk["opening"] is True and chk["foreign_open_orders"] is None
    assert chk["open_orders_unread"] == why
    rec, refusal, lines = rn.first_session_gate(b, chk, armed=True)
    assert (rec["status"], rec["action"]) == ("UNMEASURED", "refused")
    assert refusal is not None and "UNMEASURED" in refusal and why in refusal
    rec, refusal, lines = rn.first_session_gate(b, chk, armed=False)
    assert (rec["status"], rec["action"], refusal) == ("UNMEASURED", "reported", None)
    assert any("UNMEASURED" in ln for ln in lines)


def test_an_unreadable_open_order_list_refuses_the_armed_c4_session(
        c4_world, monkeypatch, tmp_path):
    """The same through the runner: gate 6's read fails at the decide; armed, the decide is
    refused, its first_session record UNMEASURED and its refusal under `first_session` naming
    the failed read, beside gate 6's own; unarmed, recorded UNMEASURED and nothing refused by
    this gate. Fails on 61589a8."""
    def failing(monkeypatch):
        monkeypatch.setattr(rn, "_gate6_orders",
                            lambda c, after: (None, None, "AlpacaHTTPError: HTTP 503 (fixture)"))
    failing(monkeypatch)
    state, plan = _decide(tmp_path / "armed", monkeypatch, expect=rn.EXIT_REFUSED,
                          closed=LAB_FILLS, armed=True)
    fs = plan["first_session"]
    assert (fs["status"], fs["action"]) == ("UNMEASURED", "refused")
    r = _first_session_refusal(plan["refusals"])
    assert "HTTP 503 (fixture)" in r["detail"]
    # Unarmed: gate 6 still refuses its unread list, as it always has; this gate adds no
    # refusal of its own and records UNMEASURED.
    state, plan = _decide(tmp_path / "dry", monkeypatch, expect=rn.EXIT_REFUSED,
                          closed=LAB_FILLS, armed=False)
    fs = plan["first_session"]
    assert (fs["status"], fs["action"]) == ("UNMEASURED", "reported")
    assert [r["gate"] for r in plan["refusals"]] == ["no_set_in_auction"]


def test_on_the_cls_path_the_armed_first_session_is_refused_at_the_decide(
        c4_world, monkeypatch, tmp_path):
    """quant-reviewer 1: in `cls` mode the decide IS the send, so its own first-session
    refusal (run_session, `refusals.append(gt.Refusal("first_session", ...))`) is the only
    guard. A position left by the loop, armed: REFUSED, nothing submitted. Without that line
    the cls run sends (checked by deleting it). Fails on 61589a8 (gate `arming`)."""
    from quantt.broker import alpaca
    pos, closed = {"ADX": 10}, LAB_FILLS[:1]
    state = _state(tmp_path)
    c = _client(state, EVE, closed, pos)
    monkeypatch.setattr(alpaca.AlpacaClient, "from_environment",
                        classmethod(lambda cls, name, **kw: c))
    spec = _spec()
    deps = rn.default_deps(_c4(), spec, {"QUANTT_ENV_FILE": "unused"})
    deps.execution = {"mode": "cls", "bp_shortfall": "scale"}
    deps.env = {"QUANTT_STATE_DIR": str(state), "DRY_RUN": "0"}
    (state / "AUTO_ARMED").touch()
    deps.refresh = lambda a, t: rn.RefreshResult(exit=0, tail="fixture")
    deps.halts = lambda: []
    deps.utcnow = lambda: EVE.astimezone(dt.timezone.utc)
    deps.out = type("Quiet", (), {"write": lambda self, s: None, "flush": lambda self: None})()
    code = rn.run_session(_c4(), spec, deps)
    plan = _read(state, "plan.json")
    assert code == rn.EXIT_REFUSED and c.submits() == [], plan["refusals"]
    assert not (state / SESSION / "STARTED").exists()
    assert "1 position(s)" in _first_session_refusal(plan["refusals"])["detail"]


def test_verify_scores_a_first_session_refusal_as_a_missed_day_not_an_explained_one():
    """execution-trader 1: filed under `arming` (in verify's DELIBERATE_GATES), an armed
    C4 day the gate refused read "PASS ... refused". Its own gate is outside them: MISSED,
    at the decide and at the send. Fails on 61589a8 (the gate's name was `arming`)."""
    from quantt.session import gate as gt
    from quantt.session import verify as vf
    assert "first_session" in gt.GATES and "first_session" not in vf.DELIBERATE_GATES
    b = rn.BOOKS["c4"]
    chk = rn.first_session_check(b, {"ADX": 10}, LAB_FILLS[:1], [], "own_prefix")
    _, text, _ = rn.first_session_gate(b, chk, armed=True)
    refusal = {"gate": gt.Refusal("first_session", text).gate, "detail": text}
    day = dt.date.fromisoformat(SESSION)
    refused_plan = {"book": "c4", "session_date": SESSION, "mode": "run",
                    "execution": "late_market", "status": "refused", "orders": [{"x": 1}],
                    "refusals": [refusal]}
    ok, prob = vf.late_no_trade_reason(refused_plan, None, day, "c4")
    assert ok is None and prob.startswith("MISSED") and "[first_session]" in prob
    decided = {**refused_plan, "status": "decided", "refusals": [], "send_window": ["a", "b"]}
    ok, prob = vf.late_no_trade_reason(decided, {"exit": "REFUSED", "refusals": [refusal]}, day, "c4")
    assert ok is None and prob.startswith("MISSED") and "[first_session]" in prob
