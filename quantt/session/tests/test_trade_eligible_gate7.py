"""CEF trial 55 (te4): a reduced decision that loses a short to gate 7 flattens; a full one is unchanged.

results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md §1.3 item 6, §7.5 and §10 Q7 (approved): if
`decide` drops an order that opens or increases a short (gate 7: not shortable today) on a
reduced decision, the reduced targets are not sent and the session takes today's flatten path,
with the reason recorded. A 4-5 name book without its short leg is not the book the trial
scored, and on a one-fund short side it is net long by the whole long side. On a session with
`min_names` or more eligible names today's skip-and-continue is unchanged.
(quantt/session/run.py `_thin_gate7`.)

Also here: the buying-power scaling rebuilds the Decision from its fields and, before this
commit, dropped `dropped_shorts` on the way (both reviews of the first te4 pass). It is carried
across now, and pinned.

Each test fails on the code before this commit (the C5 commit): there the reduced decision is
planned one-sided with the short skipped, and the scaled Decision reads `dropped_shorts` ().
"""
import pytest

from quantt.session import decide as dec
from quantt.session import nav_gate as ng
from quantt.session import run as rn
from quantt.session.tests import test_missing_nav_hold as M
from quantt.session.tests import test_trade_eligible_noop as N
from quantt.session.tests.test_trade_eligible_runner import TE4_SPEC, run

UNSHORTABLE = {"shortable": False, "borrow_status": "hard_to_borrow"}


@pytest.fixture
def books(tmp_path, monkeypatch):
    return N.thin_books(tmp_path / "books", monkeypatch)


def _shorts(plan, names) -> list:
    return sorted(s for s in names if plan["targets"][s]["target"] < 0)


@pytest.mark.parametrize("n", [5, 4])
def test_a_reduced_decision_that_loses_a_short_to_gate_7_flattens(tmp_path, monkeypatch,
                                                                   books, n):
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, n)
    # The reduced book from flat shorts these names (both sides; test_trade_eligible_runner).
    code, state, _, _ = run(tmp_path / "ok", TE4_SPEC, bk["flat"], "ok")
    shorts = _shorts(M._plan(state), N.THIN_ELIGIBLE[:n])
    assert code == rn.EXIT_PLANNED and shorts
    lost = shorts[-1]
    code, state, c, spy = run(tmp_path / "gate7", TE4_SPEC, bk["flat"], "ok",
                              client_attrs={"_assets": {lost: UNSHORTABLE}})
    plan = M._plan(state)
    ts = plan["thin_session"]
    assert ts["stopped_by"] == "gate7" and ts["reduced"] is False
    assert ts["gate7"] == {"dropped": [lost]}
    assert {t["target"] for t in plan["targets"].values()} == {0}    # today's flatten
    assert plan["orders"] == [] and code == rn.EXIT_NOTHING and not c.accepted
    assert [k["thin_rule"]["stop"]["by"] if k["thin_rule"]["stop"] else None
            for k in spy.calls] == [None, "gate7"]
    assert lost in spy.calls[1]["thin_rule"]["stop"]["why"]
    assert all("reduced build stopped by gate7" in t["reason"] for t in plan["targets"].values())


def test_a_held_reduced_book_that_loses_a_short_closes_every_position(tmp_path, monkeypatch,
                                                                      books):
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    unshortable = {s: UNSHORTABLE for s in N.THIN_ELIGIBLE}
    code, state, c, _ = run(tmp_path / "r", TE4_SPEC, bk["held"], "ok",
                            client_attrs={"_assets": unshortable})
    plan = M._plan(state)
    ts = plan["thin_session"]
    if not ts.get("gate7"):
        pytest.fail(f"the held reduced book increased no short, so gate 7 dropped nothing: {ts}")
    assert ts["stopped_by"] == "gate7"
    assert {t["target"] for t in plan["targets"].values()} == {0}
    assert code == rn.EXIT_PLANNED and plan["orders"]
    # Closing the book opens no short: every order covers a short or sells a long to zero.
    assert all(o["target"] == 0 for o in plan["orders"])


def test_on_a_full_session_skip_and_continue_is_unchanged(tmp_path, monkeypatch, books):
    """>= min_names eligible: the key changes nothing, gate 7's skip included."""
    base, bk = books
    M._scenario_panel(base, tmp_path / "full", monkeypatch, M.ASOF)
    code, state, _, _ = run(tmp_path / "probe", N.THIN_SPEC, bk["flat"], "ok")
    plan = M._plan(state)
    lost = _shorts(plan, plan["targets"])[0]
    got = {}
    for label, spec in (("absent", N.THIN_SPEC), ("te4", TE4_SPEC)):
        code, state, c, spy = run(tmp_path / label, spec, bk["flat"], "ok",
                                  client_attrs={"_assets": {lost: UNSHORTABLE}})
        got[label] = (code, M._plan(state), len(spy.calls))
    (ca, a, na), (ct, t, nt) = got["absent"], got["te4"]
    assert ca == ct == rn.EXIT_PLANNED and na == nt == 1
    assert any("not shortable today" in x for x in a["notes"][lost])
    assert t["orders"] == a["orders"] and t["targets"] == a["targets"] and t["notes"] == a["notes"]
    assert t["plan_sha"] == a["plan_sha"] and a["orders"]
    assert "gate7" not in t["thin_session"] and t["thin_session"]["stopped_by"] is None


def test_gate_7_re_reads_the_nav_gates_panel_check(tmp_path, monkeypatch, books):
    """The flatten re-runs the sleeve, which reads the panel again, so the stale-NAV gate's
    `still_holds` is asked again; a panel changed in between FAILs the session."""
    base, bk = books
    N.thin_panel(base, tmp_path / "p", monkeypatch, 5)
    code, state, _, _ = run(tmp_path / "probe", TE4_SPEC, bk["flat"], "ok")
    lost = _shorts(M._plan(state), N.THIN_ELIGIBLE)[-1]
    calls = []
    orig = ng.PanelGate.still_holds

    def counting(self, res):
        calls.append(1)
        return orig(self, res)
    monkeypatch.setattr(ng.PanelGate, "still_holds", counting)
    code, _, _, _ = run(tmp_path / "count", TE4_SPEC, bk["flat"], "ok",
                        client_attrs={"_assets": {lost: UNSHORTABLE}})
    assert code == rn.EXIT_NOTHING and len(calls) == 2

    def changed_on_second(self, res):
        calls.append(1)
        return [] if len(calls) % 2 else ["SYA: changed"]
    calls.clear()
    monkeypatch.setattr(ng.PanelGate, "still_holds", changed_on_second)
    code, state, c, _ = run(tmp_path / "changed", TE4_SPEC, bk["flat"], "ok",
                            client_attrs={"_assets": {lost: UNSHORTABLE}})
    assert code == rn.EXIT_FAIL and not c.accepted
    assert "NAV panel changed" in N.M._norm(
        sorted(state.rglob("runs/*.json"))[-1].read_bytes(), tmp_path).decode()


def test_the_buying_power_scaling_carries_dropped_shorts_across(tmp_path, monkeypatch, books):
    """`run_session` rebuilds the Decision when the buying-power fit binds; the rebuilt one
    must keep `dropped_shorts` (key absent: this is the core's path)."""
    base, bk = books
    M._scenario_panel(base, tmp_path / "full", monkeypatch, M.ASOF)
    code, state, _, _ = run(tmp_path / "probe", N.THIN_SPEC, bk["flat"], "ok")
    lost = _shorts(M._plan(state), M._plan(state)["targets"])[0]
    made = []

    class Recording(dec.Decision):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            made.append(self)
    monkeypatch.setattr(dec, "Decision", Recording)
    code, state, _, _ = run(tmp_path / "scaled", N.THIN_SPEC, bk["flat"], "ok",
                            client_attrs={"_assets": {lost: UNSHORTABLE}, "bp": 20_000.0})
    plan = M._plan(state)
    assert plan["bp_scale"]["binding"] is not None, plan["bp_scale"]   # the fit bound
    assert len(made) == 2                       # decide's, then the scaled rebuild
    assert made[0].dropped_shorts == (lost,)
    assert made[1].dropped_shorts == (lost,)
