"""CEF trial 55 (te4) in the runner: the paper declaration, the endpoint check, K0, and the gross pin.

results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md (approved 2026-11-03, PAPER ONLY), §1.2,
§1.3 items 5-6, §6.3, and the owner's terms in its "Approval" section. What the runner does is in
quantt/session/run.py, the `_thin_*` functions and `thin_rule_for`; the key-absent no-op is
tests/test_trade_eligible_noop.py.

Every test here sets the key (`TE4_SPEC`: the fixture spec of the no-op pins with
`below_min_names = "trade_eligible"` and floor 4, in memory) and each FAILS on the code before
this commit (29ba857), where the runner passes no declaration and the sleeve refuses every
decide under the key ("PAPER ONLY ... account=None"): the session is a FAIL there, whatever the
endpoint, the drawdown or the panel. The tests that must refuse also check WHERE they refuse
(before any sleeve is built), which the old code's refusal is not.

THE GROSS PIN (the owner's term 3: "a test pins that no drawdown status can increase gross").
On the thin panel at 5 and 4 eligible names and on the complete panel (12 eligible), flat and
held books, under every drawdown record (OK, HALVE, KILL, a stale series, no series, and a
K0 reading that RAISED), the projected gross after the plan (sum over names of |target shares
x as-of close|):
  * under any status but OK is at most the gross under OK, and equals the key-absent session's;
  * with the key absent it is the same under every status (report mode acts on nothing);
  * on a full session it is the key-absent session's under EVERY status, orders and targets
    included (K0 never touches a session the reduced build would not run on).

K0 READS THROUGH THE PREVIOUS SESSION (team lead's ruling 2026-11-03, E-2026-11-03-42). At
prod's 22:00 decide the as-of's own EOD row is never there yet (E-2026-11-03-41), so K0 reads
its own drawdown record through the session before the as-of, labelled one session stale. The
fixtures here (`K0_EOD`) are therefore what prod has at 22:00: no row dated the as-of
2026-09-25, the newest dated 2026-09-24 at OK / HALVE / KILL, or 2026-09-23 ("stale": two
sessions back, UNMEASURED), or no file. Every test that builds a reduced book at OK fails on
the commit before the read-through (a323971), where K0 read the as-of's row, found none, read
UNMEASURED and flattened; so do the K0 status assertions.

K0 FAILS CLOSED WHEN ITS READING RAISES (review finding after f3ad29f). `_thin_k0_drawdown`
records any error in K0's own reading, its read-through date included, as UNMEASURED, and K0
then stops the reduced build. No test covered that branch: with it changed to return an OK
record, every test here passed. The "raises" case (`K0_RAISES_OMITS`; in the K0 flatten test
and the gross pin) and `test_k0_fails_closed_when_its_reading_raises` fail on that fail-open
branch, where K0 reads OK and builds the reduced book; the rest of the module passes on it.

Hermetic: test_run's FakeClient (with `trading_endpoint` set where the key needs it), fixed
clocks, the refresh a fixture, no CEFConnect, netguard refuses any socket.
"""
import copy
import datetime as dt
import json
from pathlib import Path

import pytest

from quantt.broker import alpaca
from quantt.session import drawdown as ddm
from quantt.session import nav_gate as ng
from quantt.session import run as rn
from quantt.session.tests import test_missing_nav_hold as M
from quantt.session.tests import test_trade_eligible_noop as N
from quantt.session.tests.test_combine_noop import SYN_SPEC, _client
from quantt.session.tests.test_run import BOOK

LIVE = "https://api.alpaca.markets"           # Alpaca's live trading host: what must refuse
STATUSES = ("ok", "halve", "kill", "stale", "absent", "raises")
# K0's `<state>/eod_equity.csv` (module docstring): as at prod's 22:00 decide, no row for the
# as-of 2026-09-25. On the high of 101,000 (2026-09-22): OK 0.40% below it, HALVE 13.86%, KILL
# 20.79%, against the fixture spec's 12% / 18% lines; "stale" ends on 2026-09-23, two sessions
# before the as-of (UNMEASURED); "absent" has no file (UNMEASURED). "morning" is the backstop
# decide on the session day: the as-of's own row is there, at KILL, and K0 reads it (the
# freshest row, ruling 2026-11-04), so it flattens although the row before reads OK.
# "morning_bad" has the as-of's row present but unreadable: UNMEASURED, never a fall back to
# the row before it. "morning_ok" is the backstop with the as-of's row there at OK (0.20% below
# the high): K0 and the K1-K3 lines read it (the runner owner's review 2026-11-04, item 6).
# "raises" has "ok"'s rows and Alpaca's calendar without K0_RAISES_OMITS.
K0_EOD = {
    "ok": N._EOD_HEAD + [("2026-09-24", 100600.0)],
    "halve": N._EOD_HEAD + [("2026-09-24", 87000.0)],
    "kill": N._EOD_HEAD + [("2026-09-24", 80000.0)],
    "stale": list(N._EOD_HEAD),
    "absent": None,
    "morning": N._EOD_HEAD + [("2026-09-24", 100600.0), ("2026-09-25", 80000.0)],
    "morning_bad": N._EOD_HEAD + [("2026-09-24", 100600.0), ("2026-09-25", -1.0)],
    "morning_ok": N._EOD_HEAD + [("2026-09-24", 100600.0), ("2026-09-25", 100800.0)],
    "raises": N._EOD_HEAD + [("2026-09-24", 100600.0)],
}
K0_STATUS = {"ok": "OK", "halve": "HALVE", "kill": "KILL", "stale": "UNMEASURED",
             "absent": "UNMEASURED", "morning": "KILL", "morning_bad": "UNMEASURED",
             "morning_ok": "OK", "raises": "UNMEASURED"}
# "raises": K0's reading raises, and only the fail-closed branch of `_thin_k0_drawdown` flattens
# (module docstring). Alpaca's calendar omits 2026-09-24, the session before the as-of, as on an
# unannounced closure that nyse_calendar's SPECIAL_CLOSURES has not yet been told about. The
# session's own as-of (`asof_for(2026-09-28)` = 2026-09-25) still agrees, so the session goes
# on; K0's read-through date (`asof_for(2026-09-25)`) does not, and raises "previous trading day
# disagrees". The rows are "ok"'s, so a reading that did not raise would read OK and build.
K0_RAISES_OMITS = dt.date(2026, 9, 24)


def alpaca_calendar_without(day: dt.date, around: dt.date) -> list:
    """FakeClient calendar rows for the window the runner asks for (`around` +/- 14 days),
    NYSE trading days as FakeClient's default gives them, without `day`."""
    from ops.schedule.nyse_calendar import is_trading_day
    rows, d = [], around - dt.timedelta(days=14)
    while d <= around + dt.timedelta(days=14):
        if is_trading_day(d) and d != day:
            rows.append({"date": d, "open": "09:30", "close": "16:00"})
        d += dt.timedelta(days=1)
    return rows


def write_k0_eod(state: Path, which: str) -> None:
    """`<state>/eod_equity.csv` for K0_EOD[which], in the collector's shape (N.write_eod's);
    nothing for "absent"."""
    state.mkdir(parents=True, exist_ok=True)
    rows = K0_EOD[which]
    if rows is None:
        return
    lines, prev = ["date,equity,change_usd"], None
    for d, e in rows:
        lines.append(f"{d},{e},{'' if prev is None else round(e - prev, 2)}")
        prev = e
    (state / "eod_equity.csv").write_text("\n".join(lines) + "\n")


# K3's run length (the runner owner's review 2026-11-04, item 9): required under the rule, so
# every te4 spec here sets it, at the pre-registration's value (§6.3), with its note.
K3_RUN = {"thin_k3_run_sessions": 3,
          "_thin_k3_run_sessions_note": "test only: §6.3's 3 consecutive reduced closes"}


def te4(spec: dict, floor: int = 4) -> dict:
    s = copy.deepcopy(spec)
    s["frozen"].update(below_min_names="trade_eligible", below_min_names_floor=floor)
    s.setdefault("risk", {}).update(K3_RUN)
    return s


TE4_SPEC = te4(N.THIN_SPEC)


class _Spy:
    """deps.targets, recording every call's keywords."""

    def __init__(self, spec):
        self.spec, self.calls = spec, []

    def __call__(self, a, h, eq, op, **kw):
        self.calls.append(dict(kw))
        return rn.sleeve_targets(self.spec, rn.spec_params(self.spec)["capital_usd"], a, h, eq,
                                 op, **kw)


def run(work: Path, spec, holdings: dict, eod: str, *, endpoint=alpaca.PAPER_BASE,
        drawdown="report", now=None, execution=None, armed=False, key=None, sleeves=None,
        client_attrs=None):
    """One session as M._session builds it, with the drawdown mode, the client's endpoint
    (None: the attribute is absent) and the combiner's sleeves as arguments, and the sleeve
    call spied on. A flat book has a filled order in its history (not an opening session).
    `eod` names the K0_EOD rows; "raises" also gives the client Alpaca's calendar without
    K0_RAISES_OMITS, so K0's reading raises. Returns (exit, state, client, spy)."""
    from ops.schedule.nyse_calendar import previous_trading_day
    from src.deploy.sleeves import cef_discount as cefmod
    state = work / "state"
    write_k0_eod(state, eod)
    if key is not None:
        prev = previous_trading_day(M.SESSION)
        M._write_priors(state, {prev: M._prior_plan(prev)})
    if armed:
        (state / "AUTO_ARMED").touch()
    uni = rn.spec_params(spec)["universe"]
    closes = {s: v[0] for s, v in rn.last_closes(cefmod.PX_PATH, M.ASOF, uni).items()}
    now = now or M.EVE
    c = _client(state, holdings, closes, now)
    if eod == "raises":                       # K0's read-through date raises (K0_RAISES_OMITS)
        c._calendar = alpaca_calendar_without(K0_RAISES_OMITS, now.date())
    if not holdings:
        c._closed = list(N.FILLED_BEFORE)
    if endpoint is not None:
        c.trading_endpoint = endpoint
    for k, v in (client_attrs or {}).items():
        setattr(c, k, v)
    spy = _Spy(spec)
    deps = rn.Deps(
        client=c, env={"QUANTT_STATE_DIR": str(state), "DRY_RUN": "0"},
        refresh=lambda a, t: rn.RefreshResult(exit=0, tail="fixture"),
        closes=lambda a, u: rn.last_closes(cefmod.PX_PATH, a, u),
        navs=lambda a, u: rn.last_navs(cefmod.NAV_PATH, a, u),
        history=lambda a, u, r: rn.close_history(cefmod.PX_PATH, a, u, r),
        targets=spy, halts=lambda: [], utcnow=lambda: now.astimezone(dt.timezone.utc),
        out=M._Quiet(), execution=execution or M.LATE_SCALE, stale_nav=ng.REPORT,
        nav_gate=ng.PanelGate(nav_path=cefmod.NAV_PATH, reader=M._refused),
        drawdown=drawdown, sleeves=sleeves)
    if key is not None:
        deps.missing_nav, deps.missing_nav_max_sessions = key, M.MAX_SESSIONS
    return rn.run_session(BOOK, spec, deps), state, c, spy


def last_run(state: Path) -> dict:
    runs = sorted(state.rglob("runs/*.json"))
    return json.loads(runs[-1].read_text())


def gross(plan: dict, state_closes: dict) -> float:
    """Projected gross after the plan: sum of |target shares x as-of close|."""
    return sum(abs(t["target"]) * state_closes[s] for s, t in plan["targets"].items())


def closes_of(spec) -> dict:
    from src.deploy.sleeves import cef_discount as cefmod
    uni = rn.spec_params(spec)["universe"]
    return {s: v[0] for s, v in rn.last_closes(cefmod.PX_PATH, M.ASOF, uni).items()}


@pytest.fixture
def books(tmp_path, monkeypatch):
    return N.thin_books(tmp_path / "books", monkeypatch)


# --------------------------------------------------------------- the paper declaration

def test_the_runner_declares_paper_and_passes_k0_to_the_sleeve(tmp_path, monkeypatch, books):
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    code, state, _, spy = run(tmp_path / "r", TE4_SPEC, bk["held"], "ok")
    assert code == rn.EXIT_PLANNED
    assert spy.calls == [{"account": "paper", "thin_rule": {"stop": None}}]
    ts = M._plan(state)["thin_session"]
    assert ts["reduced"] is True and ts["stopped_by"] is None and ts["decided"] is True
    assert (ts["eligible"], ts["eligible_names"]) == (5, list(N.THIN_ELIGIBLE[:5]))
    assert (ts["rule"], ts["floor"], ts["min_names"]) == ("trade_eligible", 4, 6)
    k0 = {k: v for k, v in ts["k0"].items() if k != "drawdown"}
    assert k0 == {"status": "OK", "asof": M.ASOF.isoformat(), "read_through": "2026-09-24",
                  "stale": {"row_date": "2026-09-24", "sessions": 1}, "stop": None}


def test_a_non_paper_endpoint_refuses_before_any_sleeve_is_built(tmp_path, monkeypatch, books):
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    code, state, c, spy = run(tmp_path / "live", TE4_SPEC, bk["held"], "ok", endpoint=LIVE)
    assert code == rn.EXIT_FAIL
    err = last_run(state)["error"]
    assert "SessionError" in err and "trade_eligible" in err and LIVE in err
    assert spy.calls == [] and not c.accepted
    assert not (state / M.SESSION.isoformat() / "plan.json").exists()
    # The check is what refuses: the same session with the check's reference moved to that
    # endpoint (in this test only) builds the sleeve and plans.
    monkeypatch.setattr(alpaca, "PAPER_BASE", LIVE)
    code, _, _, spy = run(tmp_path / "moved", TE4_SPEC, bk["held"], "ok", endpoint=LIVE)
    assert code == rn.EXIT_PLANNED and spy.calls


def test_an_execution_mode_other_than_late_market_refuses_before_any_sleeve_is_built(
        tmp_path, monkeypatch, books):
    """The owner's release-check of 78e3483 (2026-11-09). K1-K3 count a reduced decision only if
    it filled, read from send.json, and a cls set writes none, so under cls an episode could open
    on STARTED alone. With the key set, cls refuses at session start. Fails on 9ca0b44, which
    never read the mode and planned."""
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    code, state, c, spy = run(tmp_path / "cls", TE4_SPEC, bk["held"], "ok",
                              execution={"mode": "cls", "bp_shortfall": "refuse"})
    assert code == rn.EXIT_FAIL
    err = last_run(state)["error"]
    assert "SessionError" in err and "trade_eligible" in err and "'cls'" in err
    assert spy.calls == [] and not c.accepted
    assert not (state / M.SESSION.isoformat() / "plan.json").exists()


def test_a_reduced_plan_the_buying_power_fit_scaled_to_nothing_was_not_sent(
        tmp_path, monkeypatch, books):
    """The owner's release-check of 78e3483 (2026-11-09), through the real decide: buying power
    too small for one whole share, so the fit takes every order out and the plan is empty.
    `plan.json` says so (`bp_scale` orders_in > 0, orders_out 0), the account did not move to the
    reduced build's targets, and the decision is not sent. Fails on 9ca0b44, which read any empty
    plan as "the account already held its targets"."""
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    code, state, c, spy = run(tmp_path / "r", TE4_SPEC, bk["flat"], "ok",
                              client_attrs={"bp": 1.0})
    plan = M._plan(state)
    assert plan["thin_session"]["reduced"] is True and plan["orders"] == []
    assert plan["bp_scale"]["orders_in"] > 0 and plan["bp_scale"]["orders_out"] == 0
    went, how = ddm._send_state(M.SESSION, {"plan": plan, "started": False, "send": None})
    assert went is False and "scaled the plan's" in how and "to none" in how


def test_an_empty_plan_without_a_fit_still_means_the_account_held_its_targets():
    """A PIN (9ca0b44 reads it the same): no `bp_scale` key at all."""
    day = {"plan": {"orders": [], "execution": "late_market"}, "started": False, "send": None}
    assert ddm._send_state(M.SESSION, day)[0] is True


@pytest.mark.parametrize("fit", [
    {"factor": 1.0, "binding": None, "orders_in": 0, "orders_out": 0},
    {"factor": 0.5, "binding": "buying_power", "orders_in": 5, "orders_out": 3},
    {"factor": 0.0, "binding": "buying_power", "orders_in": -1, "orders_out": 0},
    {"factor": 0.0, "binding": "buying_power", "orders_in": 2, "orders_out": 5}])
def test_an_empty_plan_beside_a_fit_record_run_py_cannot_write_is_unmeasured(fit):
    """The independent review of PR #69 (2026-11-10): run.py writes `bp_scale` only for a decide
    that had orders and makes the fitted set the plan's orders, so beside an empty plan only
    orders_in > 0 with orders_out 0 can be its own record. Each of these read SENT ("already held
    its targets") on 0c5d747."""
    day = {"plan": {"orders": [], "execution": "late_market", "bp_scale": fit},
           "started": False, "send": None}
    with pytest.raises(ddm.Unmeasured, match="contradict each other"):
        ddm._send_state(M.SESSION, day)


@pytest.mark.parametrize("fit", [None, {"orders_in": True, "orders_out": False}])
def test_an_empty_plan_with_a_null_or_bool_fit_record_is_malformed(fit):
    """The independent review of PR #69 (2026-11-10): run.py never writes a null `bp_scale` or a
    bool count. On 0c5d747 the null read SENT and the bools read not sent."""
    day = {"plan": {"orders": [], "execution": "late_market", "bp_scale": fit},
           "started": False, "send": None}
    with pytest.raises(ddm.Unmeasured, match="malformed `bp_scale`"):
        ddm._send_state(M.SESSION, day)


@pytest.mark.parametrize("started,why", [(True, "contradict each other"),
                                         (None, "was not read")])
def test_a_fit_emptied_plan_beside_started_or_an_unread_started_is_unmeasured(started, why):
    """The independent review of PR #69 (2026-11-10): STARTED precedes the first order of a set
    (CLAUDE.md order-path rule 2), so a set with no orders never starts; on 0c5d747 this branch
    never looked at STARTED and read both as not sent."""
    fit = {"factor": 0.0, "binding": "buying_power", "orders_in": 5, "orders_out": 0}
    day = {"plan": {"orders": [], "execution": "late_market", "bp_scale": fit},
           "started": started, "send": None}
    with pytest.raises(ddm.Unmeasured, match=why):
        ddm._send_state(M.SESSION, day)


@pytest.mark.parametrize("fit", ["x", {"orders_in": 2}, {"orders_in": "2", "orders_out": 0}])
def test_an_empty_plan_with_a_malformed_fit_record_is_unmeasured(fit):
    """Fails on 9ca0b44, which never read the record."""
    day = {"plan": {"orders": [], "execution": "late_market", "bp_scale": fit}, "started": False,
           "send": None}
    with pytest.raises(ddm.Unmeasured, match="malformed `bp_scale`"):
        ddm._send_state(M.SESSION, day)


def test_a_client_that_names_no_endpoint_refuses(tmp_path, monkeypatch, books):
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    code, state, _, spy = run(tmp_path / "r", TE4_SPEC, bk["held"], "ok", endpoint=None)
    assert code == rn.EXIT_FAIL and spy.calls == []
    assert "trading_endpoint" in last_run(state)["error"]


def test_the_key_without_risk_drawdown_fails_at_session_start(tmp_path, monkeypatch, books):
    """The owner's answer 4: loud and closed, at the decide and at the late SEND alike."""
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    for label, now in (("decide", M.EVE), ("send", M.SEND)):
        code, state, c, spy = run(tmp_path / label, TE4_SPEC, bk["held"], "ok", drawdown=None,
                                  now=now, armed=True)
        assert code == rn.EXIT_FAIL and spy.calls == [] and not c.accepted, label
        err = last_run(state)["error"]
        assert "risk.drawdown" in err and "trade_eligible" in err, label
    # Key absent, the same book json is today's session.
    code, _, _, spy = run(tmp_path / "absent", N.THIN_SPEC, bk["held"], "ok", drawdown=None)
    assert code == rn.EXIT_PLANNED and spy.calls == [{}]


def test_a_combined_book_with_the_key_fails_and_a_combined_sleeve_with_it_refuses(
        tmp_path, monkeypatch, books):
    from quantt.session import combine as cmb
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    # The book spec sets it: refused at session start.
    sp = tmp_path / "plain.frozen.json"
    sp.write_text(json.dumps(N.THIN_SPEC))
    bj = tmp_path / "book.json"
    bj.write_text(json.dumps({"book_id": "t", "sleeves": [
        {"name": "cef_discount", "enabled": True, "spec_path": sp.name, "risk_budget": 1.0}]}))
    sleeves = cmb.load_sleeves(bj, sp, tmp_path, rn._sleeve_target_fn)
    code, state, c, spy = run(tmp_path / "book", TE4_SPEC, bk["held"], "ok", sleeves=sleeves)
    assert code == rn.EXIT_FAIL and spy.calls == [] and not c.accepted
    assert "combined book" in last_run(state)["error"]
    # Only a sleeve's own spec sets it: the combiner refuses it at load (the runner owner's
    # review 2026-11-04, item 1; the test below). Until then it built the sleeve and the sleeve
    # refused at its decide, because the combiner passes no declaration.
    tp = tmp_path / "te4.frozen.json"
    tp.write_text(json.dumps(TE4_SPEC))
    bj.write_text(json.dumps({"book_id": "t", "sleeves": [
        {"name": "cef_discount", "enabled": True, "spec_path": tp.name, "risk_budget": 1.0}]}))
    with pytest.raises(cmb.CombineError, match="trade_eligible"):
        cmb.load_sleeves(bj, tp, tmp_path, rn._sleeve_target_fn)


@pytest.mark.parametrize("key", ["rule", "below_min_names_floor", "thin_k1_episode_drawdown",
                                 "thin_k2_max_name_frac", "thin_k3_net_run", "thin_k3_net_once",
                                 "thin_k3_run_sessions"])
def test_the_combiner_refuses_a_sleeve_that_sets_any_te4_key(tmp_path, key):
    """The runner owner's review (2026-11-04), item 1: `combine.load_sleeves` refuses a budgeted
    sleeve whose spec sets ANY te4 key, as it refuses `level_signal` (#41,
    src/deploy/tests/test_level_signal.py). The rule and its stops were measured on the core's
    own account; netted with another sleeve it is a book nobody scored. Each key alone (the rule
    with its required floor and run length; any other key without the rule) is refused with a
    CombineError naming it, before the sleeve is built; with every te4 key removed the same book
    loads, so the refusal is the key's own. Fails on 42f9bd7, which loads the rule (and refuses
    a lone key only through the registry's ValueError, not the combiner's)."""
    from quantt.session import combine as cmb
    from src.deploy.registry import CEF_THIN_KEYS
    base = copy.deepcopy(N.THIN_SPEC)
    assert base["frozen"].get("below_min_names") is None
    assert not set(CEF_THIN_KEYS) & set(base.get("risk") or {})
    note = "test only: compose_2026-12-01.json §E"
    if key == "rule":
        spec, named = TE4_SPEC, "frozen.below_min_names='trade_eligible'"
    elif key == "below_min_names_floor":
        spec, named = copy.deepcopy(base), f"frozen.{key}"
        spec["frozen"][key] = 4
    else:
        spec, named = copy.deepcopy(base), f"risk.{key}"
        spec.setdefault("risk", {}).update({key: 3 if key == "thin_k3_run_sessions" else 0.5,
                                            f"_{key}_note": note})
    bj = tmp_path / "book.json"
    bj.write_text(json.dumps({"book_id": "t", "sleeves": [
        {"name": "core", "enabled": True, "spec_path": "s.json", "risk_budget": 1.0}]}))
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(spec))
    with pytest.raises(cmb.CombineError, match="CEF trial 55") as e:
        cmb.load_sleeves(bj, sp, tmp_path, lambda s: (lambda *a, **k: []))
    assert named in str(e.value)
    sp.write_text(json.dumps(base))
    (entry,) = cmb.load_sleeves(bj, sp, tmp_path, lambda s: (lambda *a, **k: []))
    assert entry.universe == tuple(sorted(base["frozen"]["universe"]))


def test_the_callers_that_build_without_deciding_still_work_with_the_key_set(
        tmp_path, monkeypatch):
    """The owner's answer 1: run.py's spec_panel and ops/common.py's deployed_tickers build the
    sleeve every session without deciding, and must keep working with the key set.
    combine.py's load_sleeves refuses a budgeted sleeve with the key at load (the runner
    owner's review 2026-11-04, item 1; the test above). The target callable it would bind
    passes no declaration, so even built by hand it refuses rather than decide by default;
    the runner's own call passes the declaration explicitly (tests above)."""
    from ops.common import deployed_tickers
    from quantt.session import combine as cmb
    from src.deploy.registry import build_sleeve
    base, _ = N.thin_books(tmp_path / "b", monkeypatch)
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    from src.deploy.sleeves import cef_discount as cefmod
    assert rn.spec_panel(TE4_SPEC) == rn.Panel(cefmod.PX_PATH, cefmod.NAV_PATH)
    bj = tmp_path / "inline.json"
    bj.write_text(json.dumps({"sleeves": [{"name": "core", "spec": TE4_SPEC,
                                           "capital_usd": 100_000.0}]}))
    assert deployed_tickers(bj) == {"core": list(TE4_SPEC["frozen"]["universe"])}
    tp = tmp_path / "te4.frozen.json"
    tp.write_text(json.dumps(TE4_SPEC))
    bj.write_text(json.dumps({"book_id": "t", "sleeves": [
        {"name": "core", "enabled": True, "spec_path": tp.name, "risk_budget": 1.0}]}))
    with pytest.raises(cmb.CombineError, match="trade_eligible"):
        cmb.load_sleeves(bj, tp, tmp_path, rn._sleeve_target_fn, panel_of=rn.spec_panel)
    with pytest.raises(ValueError, match="PAPER ONLY"):
        rn._sleeve_target_fn(TE4_SPEC)(M.ASOF, {}, 100_000.0, False)
    # Declared but without the extra: still refused (the sleeve's `_thin_rule`).
    with pytest.raises(ValueError, match="thin_rule"):
        rn.sleeve_targets(TE4_SPEC, 100_000.0, M.ASOF, {}, 100_000.0, False, account="paper")
    assert build_sleeve(TE4_SPEC, 0.0).instruments() == list(TE4_SPEC["frozen"]["universe"])


# --------------------------------------------------------------- K0

@pytest.mark.parametrize("eod", ["halve", "kill", "stale", "absent", "raises"])
@pytest.mark.parametrize("n", [5, 4])
def test_k0_flattens_a_reduced_session_unless_the_drawdown_reads_ok(tmp_path, monkeypatch,
                                                                     books, n, eod):
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, n)
    for book in ("held", "flat"):
        code, state, c, spy = run(tmp_path / book, TE4_SPEC, bk[book], eod)
        assert code == (rn.EXIT_PLANNED if book == "held" else rn.EXIT_NOTHING), (book, code)
        plan = M._plan(state)
        ts = plan["thin_session"]
        assert ts["k0"]["status"] == K0_STATUS[eod]
        assert ts["k0"]["stop"]["by"] == "K0"
        assert spy.calls == [{"account": "paper", "thin_rule": {"stop": ts["k0"]["stop"]}}]
        assert ts["stopped_by"] == "K0" and ts["reduced"] is False
        assert {t["target"] for t in plan["targets"].values()} == {0}       # every name FLAT
        assert all("reduced build stopped by K0" in t["reason"] for t in plan["targets"].values())
        assert not c.accepted


@pytest.mark.parametrize("n", [5, 4])
def test_at_ok_the_reduced_book_is_built_on_both_sides(tmp_path, monkeypatch, books, n):
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, n)
    for book in ("held", "flat"):
        code, state, _, _ = run(tmp_path / book, TE4_SPEC, bk[book], "ok")
        assert code == rn.EXIT_PLANNED
        plan = M._plan(state)
        assert plan["thin_session"]["reduced"] is True
        tg = {s: t["target"] for s, t in plan["targets"].items() if s in N.THIN_ELIGIBLE[:n]}
        assert any(v > 0 for v in tg.values()) and any(v < 0 for v in tg.values()), tg


def test_k0_reads_the_previous_sessions_row_one_session_stale(tmp_path, monkeypatch, books):
    """The team lead's ruling (2026-11-03): at the 22:00 decide there is no row for the as-of,
    and K0 reads its status through the session before it, labelled one session stale, from
    the runner's calendar (2026-09-24 before Friday 2026-09-25). At OK the reduced book is
    built. HALVE/KILL's own record (step 2b, `plan["drawdown"]`) is unchanged: it reads the
    as-of's row, finds none and says UNMEASURED, as on prod. Fails on a323971, where K0 read
    that record and flattened."""
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    code, state, _, _ = run(tmp_path / "r", TE4_SPEC, bk["held"], "ok")
    assert code == rn.EXIT_PLANNED
    plan = M._plan(state)
    k0 = plan["thin_session"]["k0"]
    assert k0["status"] == "OK" and k0["stop"] is None and plan["thin_session"]["reduced"]
    assert k0["asof"] == "2026-09-25" and k0["read_through"] == "2026-09-24"
    assert k0["stale"] == {"row_date": "2026-09-24", "sessions": 1}
    assert k0["drawdown"]["reading"]["last_date"] == "2026-09-24"
    assert plan["drawdown"]["status"] == "UNMEASURED"
    assert "read_through" not in plan["drawdown"]
    assert "2026-09-24, not the as-of 2026-09-25" in plan["drawdown"]["why"]
    st = plan["thin_stops"]
    assert st["K0"]["read_through"] == "2026-09-24" and st["K0"]["verdict"] == "CLEAR"
    assert st["read_through"]["date"] == "2026-09-24"
    assert st["read_through"]["sessions_stale"] == 1


def test_the_runner_reads_back_a_fail_before_any_post_under_its_own_order_prefix(
        tmp_path, monkeypatch, books):
    """The runner owner's round-2 answer (a), at the runner: `_thin_stops` passes the book's own
    order-id prefix to the reader (`_thin_read_day(state, d, book.cid_prefix)`), so a reduced
    decision for 2026-09-25 whose send exited FAIL at the clock read before its first POST
    (STARTED; send.json FAIL with `final` / `not_final` empty; orders.jsonl holding only the
    `cutoff` event, as `_transmit` writes it; test_thin_send_state.py has the real send write
    these) reads NOT SENT, proved, at the next decide: no episode, K2/K3 N/A naming the proof.
    2026-09-24 was decided with the key absent, so the walk ends there. Fails on 9e83e63,
    which read the FAIL UNMEASURED and with it the whole episode."""
    from quantt.session import records as rec
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    state = tmp_path / "r" / "state"
    prior, before = M.ASOF, dt.date(2026, 9, 24)
    cid = f"{BOOK.cid_prefix}-{prior:%Y%m%d}-AAA-1"
    M._write_priors(state, {before: {"refusals": []}})          # the key absent then
    day = state / prior.isoformat()
    day.mkdir(parents=True)
    rec.write_json_atomic(day / "plan.json", {
        "execution": "late_market", "plan_sha": "s", "refusals": [],
        "orders": [{"client_order_id": cid}], "thin_session": {"reduced": True},
        "thin_stops": {"K3": {"verdict": "N/A"}}})
    assert rec.create_exclusive(day / "STARTED", {"plan_sha": "s"})
    rec.append_jsonl(day / "orders.jsonl", {"event": "cutoff", "at": "2026-09-25T19:58:01Z",
                                            "client_order_id": cid, "window": "test"})
    rec.write_json_atomic(day / "send.json", {"plan_sha": "s", "exit": "FAIL", "skipped": [],
                                              "final": {}, "not_final": []})
    code, state, _, _ = run(tmp_path / "r", TE4_SPEC, bk["held"], "ok")
    assert code == rn.EXIT_PLANNED
    st = M._plan(state)["thin_stops"]
    assert st["episode"]["status"] == "NONE", st["episode"]
    for k in ("K2", "K3"):
        assert st[k]["verdict"] == "N/A", st[k]
        assert "not sent: 0 submissions proved by" in st[k]["why"], st[k]
        assert "2026-09-25/orders.jsonl (1 event(s), 0 `submit`" in st[k]["why"]
        assert "2026-09-25/reconcile.json absent" in st[k]["why"]


def test_at_the_morning_backstop_k0_reads_the_asofs_own_row(tmp_path, monkeypatch, books):
    """The backstop decide on the session day: the as-of's own row is there (at KILL here).
    K0 reads the freshest row it has (ruling 2026-11-04), so it reads 2026-09-25 (KILL),
    labelled 0 sessions stale, and the session flattens although 2026-09-24 reads OK. Fails
    on 69fccf3, where K0 always read the session before the as-of (OK) and built."""
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    code, state, _, _ = run(tmp_path / "r", TE4_SPEC, bk["held"], "morning")
    assert code == rn.EXIT_PLANNED
    plan = M._plan(state)
    assert plan["drawdown"]["status"] == "KILL"
    k0 = plan["thin_session"]["k0"]
    assert k0["status"] == "KILL" and k0["read_through"] == "2026-09-25"
    assert k0["stale"]["sessions"] == 0
    assert k0["stop"]["by"] == "K0"
    assert plan["thin_session"]["reduced"] is False and plan["thin_session"]["stopped_by"] == "K0"


def test_at_the_morning_backstop_a_bad_asof_row_never_falls_back(tmp_path, monkeypatch, books):
    """The as-of's row is there but unreadable (a negative equity): UNMEASURED and the session
    flattens. K0 never falls back past a row it has to an older, readable one. A PIN, not a
    regression test: it passes on 69fccf3 too, because `drawdown.read_series` refuses a bad
    row anywhere in the file, so reading through D-1 was UNMEASURED there as well. It fails
    for an implementation that falls back to D-1 on any UNMEASURED and reads only rows up to
    the read-through date."""
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    code, state, _, _ = run(tmp_path / "r", TE4_SPEC, bk["held"], "morning_bad")
    assert code == rn.EXIT_PLANNED
    plan = M._plan(state)
    k0 = plan["thin_session"]["k0"]
    assert k0["status"] == "UNMEASURED"
    assert plan["thin_session"]["reduced"] is False and plan["thin_session"]["stopped_by"] == "K0"


@pytest.mark.parametrize("eod", ["stale", "absent"])
def test_k0_reads_unmeasured_on_an_older_row_or_no_file_and_flattens(tmp_path, monkeypatch,
                                                                     books, eod):
    """A newest row older than the session before the as-of (2026-09-23, two sessions stale),
    or no eod_equity.csv: UNMEASURED, and the session flattens, naming why."""
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    code, state, _, _ = run(tmp_path / "r", TE4_SPEC, bk["held"], eod)
    assert code == rn.EXIT_PLANNED
    ts = M._plan(state)["thin_session"]
    assert ts["k0"]["status"] == "UNMEASURED" and ts["stopped_by"] == "K0"
    # "stale": the as-of's row has not landed, so K0 falls back to the session before it, whose
    # row is missing too. "absent": no file, so there is no reading to fall back from; the
    # record names the as-of it tried first (ruling 2026-11-04: the freshest row first).
    assert ts["k0"]["read_through"] == ("2026-09-24" if eod == "stale" else "2026-09-25")
    if eod == "stale":
        assert ts["k0"]["stale"] == {"row_date": "2026-09-23", "sessions": 2}
        assert "read-through date 2026-09-24 is 2026-09-23" in ts["k0"]["stop"]["why"]
    else:
        assert ts["k0"]["stale"] is None and "no eod_equity.csv" in ts["k0"]["stop"]["why"]


class _CheckRaises:
    """`drawdown.check` that raises OSError on K0's call (the one with `read_through`) and is
    the real check on step 2b's: an error in K0's reading that is not about the dates."""

    def __init__(self, real):
        self.real, self.k0_calls = real, 0

    def __call__(self, *a, **kw):
        if kw.get("read_through") is not None:
            self.k0_calls += 1
            raise OSError("fixture: eod_equity.csv could not be read for K0")
        return self.real(*a, **kw)


@pytest.mark.parametrize("cause", ["calendar", "check"])
@pytest.mark.parametrize("n", [5, 4])
def test_k0_fails_closed_when_its_reading_raises(tmp_path, monkeypatch, books, n, cause):
    """§6.3: K0 "acts in code and fails closed". When K0's own reading raises, in the dates
    (`calendar`: Alpaca's calendar omits the session before the as-of, K0_RAISES_OMITS, and
    `asof_for` refuses to choose) or in the check itself (`check`: an OSError), the record is
    UNMEASURED naming the exception's type, it carries no read-through date, K0 passes the stop,
    the session takes today's flatten and nothing is sent. The EOD rows read OK, so a reading
    that did not raise would build the reduced book. Step 2b's record (HALVE/KILL's report) is
    still made, and the K-lines say K0's record names no read-through date.

    Fails on the fail-open branch (`_thin_k0_drawdown`'s except returning an OK record): K0
    reads OK there, the reduced book is built, and the status and stop assertions fail."""
    from quantt.session import drawdown as ddm
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, n)
    eod = "raises" if cause == "calendar" else "ok"
    if cause == "check":
        fake = _CheckRaises(ddm.check)
        monkeypatch.setattr(ddm, "check", fake)
    for book in ("held", "flat"):
        code, state, c, spy = run(tmp_path / book, TE4_SPEC, bk[book], eod)
        assert code == (rn.EXIT_PLANNED if book == "held" else rn.EXIT_NOTHING), (book, code)
        plan = M._plan(state)
        ts = plan["thin_session"]
        k0 = ts["k0"]
        assert k0["status"] == "UNMEASURED", (book, k0)
        assert k0["read_through"] is None and k0["stale"] is None
        why = k0["drawdown"]["why"]
        if cause == "calendar":
            assert why.startswith("SessionError: previous trading day disagrees"), why
            assert "nyse_calendar 2026-09-24, Alpaca calendar 2026-09-23" in why
        else:
            assert why.startswith("OSError: fixture: eod_equity.csv could not be read"), why
        assert k0["stop"]["by"] == "K0" and why in k0["stop"]["why"]
        assert spy.calls == [{"account": "paper", "thin_rule": {"stop": k0["stop"]}}]
        assert ts["stopped_by"] == "K0" and ts["reduced"] is False
        assert {t["target"] for t in plan["targets"].values()} == {0}       # every name FLAT
        assert all("reduced build stopped by K0" in t["reason"] for t in plan["targets"].values())
        assert not c.accepted
        assert plan["drawdown"]["status"] == "UNMEASURED"       # step 2b: no as-of row (prod)
        assert "2026-09-24, not the as-of 2026-09-25" in plan["drawdown"]["why"]
        assert "names no read-through date" in plan["thin_stops"]["unmeasured"]
    if cause == "check":
        assert fake.k0_calls == 2                                   # K0 read once per session


def test_below_the_floor_k0_records_no_stop_on_the_build(tmp_path, monkeypatch, books):
    """At 3 eligible (under the floor) no reduced build could run, so `stopped_by` stays None
    even when K0 passes a stop: only a stop that removed a build is recorded as one."""
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 3)
    code, state, _, _ = run(tmp_path / "r", TE4_SPEC, bk["held"], "halve")
    ts = M._plan(state)["thin_session"]
    assert code == rn.EXIT_PLANNED
    assert ts["k0"]["stop"]["by"] == "K0" and ts["stopped_by"] is None and not ts["reduced"]
    assert ts["eligible"] == 3


def test_k0_reads_only_an_exact_ok():
    assert rn._thin_k0_stop({"status": "OK", "asof": "x"}) is None
    for status in ("HALVE", "KILL", "UNMEASURED", "ok", " OK", None, 0, True):
        stop = rn._thin_k0_stop({"status": status, "asof": "x"})
        assert stop["by"] == "K0" and repr(status) in stop["why"], status
    with pytest.raises(rn.SessionError, match="no drawdown record"):
        rn._thin_k0_stop(None)


def test_a_data_refusal_records_the_rule_and_k0_but_no_sleeve_answer(tmp_path, monkeypatch, books):
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    from src.deploy.sleeves import cef_discount as cefmod
    import pandas as pd
    nav = pd.read_parquet(cefmod.NAV_PATH)
    nav = nav[~((pd.to_datetime(nav["date"]) == pd.Timestamp(M.ASOF)) & (nav["ticker"] == "SYA"))]
    nav.to_parquet(cefmod.NAV_PATH)
    code, state, _, spy = run(tmp_path / "r", TE4_SPEC, bk["held"], "ok")
    assert code == rn.EXIT_REFUSED and spy.calls == []
    ts = M._plan(state)["thin_session"]
    assert ts["decided"] is False and ts["eligible"] is None and ts["reduced"] is False
    assert ts["k0"]["status"] == "OK"


def test_with_a_missing_nav_hold_the_reduced_build_never_runs_and_the_day_is_refused(
        tmp_path, monkeypatch, books):
    """§7.7 / Q10 at the runner: at the final check, a held fund out of the cross-section
    leaves the other four eligible; the sleeve takes today's min_names path with its tag, and
    the runner refuses the day as without the key (never a reduced book beside a hold)."""
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    from src.deploy.sleeves import cef_discount as cefmod
    import pandas as pd
    nav = pd.read_parquet(cefmod.NAV_PATH)
    nav = nav[~((pd.to_datetime(nav["date"]) == pd.Timestamp(M.ASOF)) & (nav["ticker"] == "SYE"))]
    nav.to_parquet(cefmod.NAV_PATH)
    code, state, c, _ = run(tmp_path / "r", TE4_SPEC, bk["held"], "ok", key=M.HOLD,
                            now=M.FINAL)
    assert code == rn.EXIT_REFUSED and not c.accepted
    plan = M._plan(state)
    ts = plan["thin_session"]
    assert ts["holds"] is True and ts["reduced"] is False and ts["stopped_by"] is None
    assert plan["missing_nav"]["action"] == "refused"


# --------------------------------------------------------------- the gross pin

def _gross_case(work: Path, mp, base, holdings, panel: str, spec, eod: str) -> tuple:
    if panel == "full":
        M._scenario_panel(base, work / "panel", mp, M.ASOF)
    else:
        N.thin_panel(base, work / "panel", mp, int(panel))
    code, state, _, _ = run(work / "run", spec, holdings, eod)
    plan = M._plan(state)
    return code, plan, gross(plan, closes_of(spec))


@pytest.mark.parametrize("panel", ["5", "4", "full"])
def test_no_drawdown_status_can_increase_gross(tmp_path, monkeypatch, books, panel):
    base, bk = books
    for book, holdings in bk.items():
        got = {}
        for rule, spec in (("absent", N.THIN_SPEC), ("te4", TE4_SPEC)):
            for eod in STATUSES:
                got[(rule, eod)] = _gross_case(tmp_path / f"{book}_{rule}_{eod}", monkeypatch,
                                               base, holdings, panel, spec, eod)
        g = {k: v[2] for k, v in got.items()}
        # Key absent: report mode acts on nothing, so every status gives one book.
        assert len({g[("absent", s)] for s in STATUSES}) == 1, (book, g)
        for s in STATUSES:
            assert g[("te4", s)] <= g[("te4", "ok")] + 1e-9, (book, s, g)
            if s != "ok":
                assert g[("te4", s)] == g[("absent", s)], (book, s, g)
        if panel == "full":
            # K0 never touches a full session: the plan is the key-absent one under every status.
            for s in STATUSES:
                a, t = got[("absent", s)][1], got[("te4", s)][1]
                assert t["orders"] == a["orders"] and t["targets"] == a["targets"], (book, s)
                assert t["thin_session"]["reduced"] is False
                assert t["thin_session"]["stopped_by"] is None
            assert g[("te4", "ok")] > 0
        else:
            assert g[("te4", "ok")] > 0 and g[("te4", "halve")] == 0, (book, g)
            assert g[("te4", "raises")] == 0, (book, g)      # K0's reading raised: flat
