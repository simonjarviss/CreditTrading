"""decide.py's `Decision.dropped_shorts`: which short-opens gate 7 dropped, as a structured field.

WHY (CEF trial 55, te4: results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md §1.3 item 6, §7.5,
§10 Q7, approved 2026-11-03). On a reduced session (4-5 names) a short that gate 7 skips as not
shortable today can be the whole short side, leaving the book net long by the whole long side: a
book the harness never scored. The ruling is that such a reduced decision flattens instead. The
runner (a later pass) must therefore know, from the decision itself, which symbols lost a
short-opening order to gate 7. Until now that existed only as prose in `notes` ("not shortable
today: no order sent ..."), and a rule that parses prose breaks the first time the prose is
reworded (docs/RUNNER.md: the scorer never parses a reason string).

What is pinned:
  1. A short-OPEN and a short-INCREASE that gate 7 skips are listed, in universe order; a cover,
     a long, a shortable short and a deferred flip (whose only order today closes the long) are
     not; a same-session flip whose open leg is unshortable is.
  2. NOTHING ELSE MOVES. `dropped_shorts` is the LAST field, with a default, so every existing
     construction (`Decision(orders=, targets=, notes=, plan_sha=)` in run.py) still builds; and
     neither `to_dict` (plan.json's `decision` record) nor `plan_sha` carries it. Both are pinned
     against values computed from ac15d09's code (the code before te4) on one fixture that has
     two dropped shorts, a deferred flip, a close and a buy.

Group 1 fails on ac15d09 (Decision has no `dropped_shorts`); group 2 passes there too, by design:
it pins what must not move.
"""
import dataclasses
import datetime as dt
import hashlib
import json

from quantt.session import decide as dec
from quantt.session.tests.test_decide import T, flat_rest, run
from src.deploy.sleeve import LONG, SHORT

SH_ALL = {"AAA": True, "BBB": True, "CCC": True}


# ---------------------------------------------------------------- 1. what is listed

def test_a_short_open_skipped_by_gate_7_is_listed():
    d = run(flat_rest(T("AAA", SHORT, w=-0.05), T("BBB", LONG, w=0.05)),
            shortable={**SH_ALL, "AAA": False})
    assert d.dropped_shorts == ("AAA",)
    assert [o.symbol for o in d.orders] == ["BBB"]
    assert any("not shortable" in n for n in d.notes["AAA"])         # the prose is unchanged


def test_a_short_increase_is_listed_and_a_cover_is_not():
    d = run(flat_rest(T("AAA", SHORT, q=-80), T("BBB", SHORT, q=-20)),
            positions={"AAA": -50, "BBB": -50}, shortable={**SH_ALL, "AAA": False, "BBB": False})
    assert d.dropped_shorts == ("AAA",)                              # BBB covers: no check needed
    assert [(o.symbol, o.side, o.qty) for o in d.orders] == [("BBB", "buy", 30)]


def test_nothing_is_listed_when_gate_7_drops_nothing():
    for kw in ({}, {"positions": {"AAA": 120}}):
        d = run(flat_rest(T("AAA", SHORT, w=-0.05), T("CCC", LONG, w=0.05)), shortable=SH_ALL,
                **kw)
        assert d.dropped_shorts == ()
    # a deferred flip sends only the closing leg today, so nothing needs the borrow check
    d = run(flat_rest(T("AAA", SHORT, w=-0.05)), positions={"AAA": 120},
            shortable={**SH_ALL, "AAA": False})
    assert d.dropped_shorts == () and [o.symbol for o in d.orders] == ["AAA"]


def test_a_same_session_flip_to_an_unshortable_name_is_listed():
    d = run(flat_rest(T("AAA", SHORT, w=-0.05)), positions={"AAA": 120},
            shortable={**SH_ALL, "AAA": False}, flip_same_session=True)
    assert d.orders == () and d.dropped_shorts == ("AAA",)


def test_dropped_shorts_are_in_universe_order():
    d = run(flat_rest(T("CCC", SHORT, w=-0.05), T("AAA", SHORT, w=-0.05)),
            shortable={"AAA": False, "BBB": True, "CCC": False})
    assert d.dropped_shorts == ("AAA", "CCC")


# ---------------------------------------------------------------- 2. nothing else moves

UNI5 = ("AAA", "BBB", "CCC", "DDD", "EEE")
# Computed from ac15d09's decide.py (the code before te4) on `_fixture()`, 2026-11-03.
PIN_PLAN_SHA = "4e75b9d93f084b9eff65a782b9378a43b8af58d57a8146be963562c794cd006c"
PIN_TO_DICT_SHA = "385306ca3d17012ebd2daea1c853ebbbd7d07b71bd778f20063732e34281a4cc"


def _fixture():
    targets = [T("AAA", SHORT, w=-0.05, reason="cef discount z=+1.20 w=-0.0500"),
               T("BBB", LONG, w=0.07, reason="cef discount z=-1.10 w=+0.0700"),
               T("CCC", SHORT, q=-80, reason="cef band hold"),
               T("DDD", SHORT, w=-0.03, reason="cef discount z=+0.90 w=-0.0300"),
               T("EEE", reason="cef: below min weight")]
    return dec.decide(targets, {"CCC": -50, "DDD": 40, "EEE": 25}, 100_000.0,
                      {"AAA": 10.0, "BBB": 20.0, "CCC": 30.0, "DDD": 12.5, "EEE": 8.0},
                      {"AAA": False, "BBB": True, "CCC": False, "DDD": True, "EEE": True},
                      session_date=dt.date(2026, 11, 3), universe=UNI5, cid_prefix="cef",
                      min_trade_usd=0.0)


def test_to_dict_and_plan_sha_are_unchanged():
    d = _fixture()
    td = d.to_dict()
    assert sorted(td) == ["notes", "orders", "plan_sha", "targets"]
    assert d.plan_sha == PIN_PLAN_SHA == dec.plan_sha(d.orders)
    blob = json.dumps(td, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(blob).hexdigest() == PIN_TO_DICT_SHA
    assert [(o.symbol, o.side, o.qty) for o in d.orders] == [
        ("EEE", "sell", 25), ("DDD", "sell", 40), ("BBB", "buy", 350)]


def test_the_field_is_last_and_defaulted():
    names = [f.name for f in dataclasses.fields(dec.Decision)]
    assert names == ["orders", "targets", "notes", "plan_sha", "dropped_shorts"]
    d = dec.Decision(orders=(), targets={}, notes={}, plan_sha=dec.plan_sha(()))
    assert d.dropped_shorts == ()
    assert _fixture().dropped_shorts == ("AAA", "CCC")
