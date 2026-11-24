"""combine.py: what the multi-sleeve combiner DOES, on synthetic sleeves through the real session.

The sleeves here are fakes with fixed weights, so every expected share count is
arithmetic a reader can redo: shares = trunc(weight x sleeve_nav / close), and
sleeve_nav = equity x risk_budget x book vol / sleeve vol (combine.py, THE RISK
BUDGET). The account is test_run's FakeClient: equity $100,000, no network.
The proof that the released book json is untouched is test_combine_noop.py;
this file is the behaviour that only exists once a book turns the combiner on.

Against de6e9c5 every test here fails: there is no `combine` module, no
`Deps.sleeves`, no `gate.gate_data_by_sleeve` (the commit message shows the
run). `combine` is imported inside each test for that reason, so each one
fails on its own rather than the file failing to collect.
"""
import datetime as dt
import json
from types import SimpleNamespace

import pytest

from quantt.session import gate as gt
from quantt.session import nav_gate as ng
from quantt.session import run as rn
from quantt.session.tests.test_run import ASOF, BOOK, D, LATE, FakeClient, make
from src.deploy.sleeve import FLAT, LONG, SHORT, PositionTarget

ET = rn.gt.ET
CL = {"AAA": 10.0, "BBB": 20.0, "CCC": 30.0, "DDD": 40.0, "ZZZ": 50.0}
# The BOOK spec: the book-level limits and the book's vol target. Its own
# universe is not what a combined book trades (that is the union of the sleeves').
BOOK_SPEC = {"spec_id": "book.v1", "capital_usd": 100_000.0,
             "allocation": {"type": "cef_discount"},
             "frozen": {"universe": ["AAA", "BBB", "CCC"], "max_gross_stress": 1.8,
                        "vol_target_annual": 0.06},
             "rebalance": {"min_trade_usd": 0.0},
             "risk": {"max_gross_exposure_usd": 260_000.0}}
MORNING = dt.datetime(2026, 9, 29, 8, 30, tzinfo=ET)       # before the final check (14:30)
FINAL = dt.datetime(2026, 9, 29, 14, 45, tzinfo=ET)        # after it, before the cls cutoff


def sleeve(name, universe, wants, *, budget=1.0, vol=0.06, calls=None):
    """A fake sleeve. `wants` {sym: weight, or ("qty", n) for a held share
    count}; a name not in `wants` is FLAT. A name in `extras["nav_hold"]` keeps
    its current shares, as the real sleeve does (cef_discount._held_target).
    `calls` receives every call's inputs."""
    from quantt.session import combine as cmb

    def targets(asof, holdings, nav, opening, **kw):
        if calls is not None:
            calls.append({"asof": asof, "holdings": dict(holdings), "nav": nav,
                          "opening": opening, **kw})
        held = (kw.get("nav_hold") or {}).get("names", {})
        out = []
        for s in sorted(universe):
            w = wants.get(s, 0.0)
            if s in held:
                q = holdings.get(s, 0)
                out.append(PositionTarget(s, FLAT, reason=f"{name} nav hold") if q == 0 else
                           PositionTarget(s, LONG if q > 0 else SHORT, qty=q,
                                          reason=f"{name} nav hold"))
            elif isinstance(w, tuple):
                out.append(PositionTarget(s, LONG if w[1] > 0 else SHORT, qty=w[1],
                                          reason=f"{name} hold"))
            elif w == 0:
                out.append(PositionTarget(s, FLAT, reason=f"{name} flat"))
            else:
                out.append(PositionTarget(s, LONG if w > 0 else SHORT, weight=w,
                                          reason=f"{name} w={w:+.3f}"))
        return out
    return cmb.SleeveEntry(name=name, spec_id=f"{name}.v1", spec_path=f"ops/specs/{name}.json",
                           universe=tuple(sorted(universe)), risk_budget=budget, vol_target=vol,
                           targets=targets)


def run(tmp_path, sleeves, *, positions=None, clock=MORNING, execution=None, navs=None,
        closes=None, refresh_exit=0, preview=False, armed=True, bp=None, stale_nav=None,
        nav_gate=None):
    """One session of the combined book (cls by default, armed, DRY_RUN=0) on the
    fake account; `plan` is None when the session wrote none (a FAIL)."""
    c, deps, state, _, out = make(
        tmp_path, positions=positions or {}, clock_ts=clock,
        now_utc=clock.astimezone(dt.timezone.utc), refresh_exit=refresh_exit,
        execution=execution or {"mode": "cls", "bp_shortfall": "scale"},
        closes=closes or (lambda asof, uni: {s: (CL[s], ASOF) for s in uni}), navs=navs)
    if bp is not None:
        c.bp = bp
    deps.sleeves = tuple(sleeves)
    deps.stale_nav, deps.nav_gate = stale_nav, nav_gate
    if armed:
        (state / "AUTO_ARMED").touch()
    code = rn.run_session(BOOK, BOOK_SPEC, deps, preview=preview)
    p = state / D.isoformat() / "plan.json"
    return SimpleNamespace(code=code, client=c, deps=deps, state=state, out="".join(out),
                           plan=json.loads(p.read_text()) if p.exists() else None)


def by_symbol(orders):
    out = {}
    for o in orders:
        out.setdefault(o["symbol"], []).append(o)
    return out


# ------------------------------------------------------------------ overlapping universes

def test_load_sleeves_refuses_enabled_sleeves_that_share_a_symbol(tmp_path):
    """Release-check of 00ec423: accepted, the shared symbol nets from flat on day
    one and every later slot FAILs on the position day one built."""
    from quantt.session import combine as cmb
    a = _spec_file(tmp_path, "a", {"AAA": 0.05, "BBB": 0.04})
    b = _spec_file(tmp_path, "b", {"BBB": 0.30, "CCC": 0.20})
    both = _book_file(tmp_path, "both.json", [
        {"name": "A", "enabled": True, "spec_path": a, "risk_budget": 0.5},
        {"name": "B", "enabled": True, "spec_path": b, "risk_budget": 0.5}])
    with pytest.raises(cmb.CombineError, match=r"share \['BBB'\].*'BBB': \('A', 'B'\)"):
        cmb.load_sleeves(both, tmp_path / "book.json", tmp_path, _make_targets)
    # Disabled, the same sleeve is no overlap: only ENABLED universes count.
    one_off = _book_file(tmp_path, "one_off.json", [
        {"name": "A", "enabled": True, "spec_path": a, "risk_budget": 0.5},
        {"name": "B", "enabled": False, "spec_path": b, "risk_budget": 0.5}])
    assert [e.name for e in cmb.load_sleeves(one_off, tmp_path / "book.json", tmp_path,
                                             _make_targets)] == ["A"]


def test_a_session_whose_sleeves_share_a_symbol_fails_before_any_order(tmp_path):
    """However the sleeves were built: the day-one netting that 00ec423 sent
    (BBB +300 from flat) is refused, so no day-two lockout can follow."""
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05, "BBB": 0.10})
    b = sleeve("B", ("BBB", "CCC"), {"BBB": -0.04, "CCC": -0.03})
    r = run(tmp_path, [a, b])
    assert r.code == rn.EXIT_FAIL and r.client.accepted == {} and r.plan is None
    assert "share ['BBB']" in r.out and "sub-ledgers" in r.out


# --------------------------------------- netting across sleeves: NOT YET ALLOWED
# These exercise the cross-sleeve arithmetic kept for when per-sleeve sub-ledgers
# exist, behind combine.SHARED_SYMBOLS_ALLOWED (False in production; the two
# tests above prove it is refused). Not a supported configuration today.

@pytest.fixture
def shared_symbols_allowed(monkeypatch):
    from quantt.session import combine as cmb
    monkeypatch.setattr(cmb, "SHARED_SYMBOLS_ALLOWED", True)


def test_not_yet_allowed_a_long_and_a_short_in_one_symbol_net_to_one_order(
        tmp_path, shared_symbols_allowed):
    # A: BBB +0.10 -> +500 at $20 on $100k. B: BBB -0.04 -> -200. Net +300: ONE buy.
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05, "BBB": 0.10})
    b = sleeve("B", ("BBB", "CCC"), {"BBB": -0.04, "CCC": -0.03})
    r = run(tmp_path, [a, b])
    assert r.code == rn.EXIT_SENT
    got = by_symbol(r.plan["orders"])
    assert {s: [(o["side"], o["qty"]) for o in os_] for s, os_ in got.items()} == {
        "AAA": [("buy", 500)], "BBB": [("buy", 300)], "CCC": [("sell", 100)]}
    # One POST per symbol reached the broker.
    assert sorted(o["symbol"] for o in r.client.accepted.values()) == ["AAA", "BBB", "CCC"]
    assert r.plan["targets"]["BBB"]["target"] == 300
    assert "A +500" in r.plan["targets"]["BBB"]["reason"]
    assert "B -200" in r.plan["targets"]["BBB"]["reason"]


def test_not_yet_allowed_two_sleeves_that_cross_exactly_send_nothing_in_that_symbol(
        tmp_path, shared_symbols_allowed):
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05, "BBB": 0.04})
    b = sleeve("B", ("BBB", "CCC"), {"BBB": -0.04, "CCC": -0.03})
    r = run(tmp_path, [a, b])
    assert "BBB" not in by_symbol(r.plan["orders"])
    assert r.plan["targets"]["BBB"]["target"] == 0
    c = r.plan["combine"]["sleeves"]
    assert (c["A"]["targets"]["BBB"]["target"], c["B"]["targets"]["BBB"]["target"]) == (200, -200)


# ------------------------------------------------------------------ the risk budgets

def test_the_risk_budgets_scale_each_sleeve(tmp_path):
    from quantt.session import combine as cmb
    ca, cb = [], []
    # Book vol 6%. A: budget 0.5, own vol 6%  -> sleeve_nav $50,000.
    #             B: budget 0.25, own vol 3% -> $100,000 x 0.25 x 0.06/0.03 = $50,000.
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05, "BBB": -0.05}, budget=0.5, calls=ca)
    b = sleeve("B", ("CCC", "DDD"), {"CCC": 0.09, "DDD": -0.09}, budget=0.25, vol=0.03,
               calls=cb)
    r = run(tmp_path, [a, b])
    assert [x["nav"] for x in ca] == [50_000.0] and [x["nav"] for x in cb] == [50_000.0]
    rec = r.plan["combine"]["sleeves"]
    assert rec["A"]["sleeve_nav"] == 50_000.0 and rec["B"]["sleeve_nav"] == 50_000.0
    # trunc(w x nav / close): AAA 0.05x50k/10 = 250; BBB -0.05x50k/20 = -125;
    # CCC 0.09x50k/30 = 150; DDD -0.09x50k/40 = -112.5 -> -112 (toward zero).
    assert {s: t["target"] for s, t in r.plan["targets"].items()} == \
        {"AAA": 250, "BBB": -125, "CCC": 150, "DDD": -112}
    # The same two at budget 1.0: A's nav doubles ($100,000) and B's quadruples
    # ($100,000 x 1.0 x 0.06/0.03 = $200,000), and so do their shares.
    full = run(tmp_path / "full", [sleeve("A", ("AAA", "BBB"), {"AAA": 0.05, "BBB": -0.05}),
                                   sleeve("B", ("CCC", "DDD"), {"CCC": 0.09, "DDD": -0.09},
                                          vol=0.03)])
    assert {s: t["target"] for s, t in full.plan["targets"].items()} == \
        {"AAA": 500, "BBB": -250, "CCC": 600, "DDD": -450}
    assert full.plan["combine"]["sleeves"]["B"]["sleeve_nav"] == 200_000.0
    # The arithmetic itself: one sleeve on the book's own vol at budget 1 is the equity.
    assert cmb.sleeve_nav(101_229.74, 1.0, 0.06, 0.06) == 101_229.74


# ------------------------------------------------------------------ the book-level cap

def _near_cap_sleeves():
    # Each sleeve alone at 0.95x gross (inside 1.80); together 1.90x > the book's 1.80.
    return [sleeve("A", ("AAA", "BBB"), {"AAA": 0.475, "BBB": -0.475}),
            sleeve("B", ("CCC", "DDD"), {"CCC": 0.475, "DDD": -0.475})]


def test_the_combined_cap_binds_and_scales_the_opening_orders(tmp_path):
    r = run(tmp_path, _near_cap_sleeves(), bp=1_000_000.0)   # buying power not the limit
    assert r.code == rn.EXIT_SENT
    want = {"AAA": 4750, "BBB": -2375, "CCC": 1583, "DDD": -1187}
    assert {s: t["target"] for s, t in r.plan["targets"].items()} == want
    gross_wanted = sum(abs(q) * CL[s] for s, q in want.items())
    assert gross_wanted > 1.8 * 100_000.0                    # 189,970 > 180,000
    sent = {o["symbol"]: o["qty"] for o in r.plan["orders"]}
    assert set(sent) == set(want) and all(sent[s] < abs(want[s]) for s in want)
    gross_after = sum(q * CL[s] for s, q in sent.items())    # from flat: |after| = qty
    assert gross_after <= 1.8 * 100_000.0
    assert "max_gross_stress" in r.plan["bp_scale"]["binding"]
    assert r.plan["refusals"] == []
    # What each sleeve WANTED is kept, unscaled, for the P&L split.
    rec = r.plan["combine"]["sleeves"]
    assert rec["A"]["targets"]["AAA"]["target"] == 4750
    assert rec["B"]["targets"]["DDD"]["target"] == -1187


def test_the_combined_cap_refuses_when_the_book_does_not_scale(tmp_path):
    r = run(tmp_path, _near_cap_sleeves(), bp=1_000_000.0, execution={"mode": "cls"})
    assert r.code == rn.EXIT_REFUSED and r.client.accepted == {}
    assert any(x["gate"] == "exposure" and "max_gross_stress" in x["detail"]
               for x in r.plan["refusals"])


# ------------------------------------------------------------------ gate 9

def test_gate_9_accepts_a_holding_in_any_enabled_sleeves_universe(tmp_path):
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05})
    b = sleeve("B", ("CCC", "DDD"), {"CCC": ("qty", -100)})
    r = run(tmp_path, [a, b], positions={"CCC": -100})
    assert r.code == rn.EXIT_SENT
    assert not [x for x in r.plan["refusals"] if x["gate"] == "sanity"]
    assert r.plan["combine"]["sleeves"]["B"]["targets"]["CCC"]["current"] == -100


def test_gate_9_still_refuses_a_holding_in_no_sleeves_universe(tmp_path):
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05})
    b = sleeve("B", ("CCC", "DDD"), {})
    r = run(tmp_path, [a, b], positions={"ZZZ": 10})
    assert r.code == rn.EXIT_REFUSED and r.client.accepted == {}
    assert {"gate": "sanity", "detail": "account holds non-universe symbol(s) ['ZZZ']"} \
        in r.plan["refusals"]


def test_the_send_gates_the_union_too(tmp_path):
    """Late-market: the 15:52 send re-reads the assets and gate 9 on the union,
    or an order in the second sleeve's name would be refused there."""
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05})
    b = sleeve("B", ("CCC", "DDD"), {"DDD": -0.04})
    eve = dt.datetime(2026, 9, 28, 22, 0, tzinfo=ET)
    r = run(tmp_path, [a, b], clock=eve, execution={**LATE, "bp_shortfall": "scale"})
    assert r.code == rn.EXIT_PLANNED and r.plan["status"] == "decided"
    send = dt.datetime(2026, 9, 29, 15, 52, 30, tzinfo=ET)
    c2 = FakeClient(r.state, clock_ts=send)
    r.deps.client, r.deps.utcnow = c2, (lambda: send.astimezone(dt.timezone.utc))
    assert rn.run_session(BOOK, BOOK_SPEC, r.deps) == rn.EXIT_SENT
    assert sorted(o["symbol"] for o in c2.accepted.values()) == ["AAA", "DDD"]
    assert ("asset", "DDD") in c2.calls


# ------------------------------------------------------------------ attribution

def test_per_sleeve_attribution_is_recorded_in_plan_json(tmp_path):
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05, "BBB": 0.10}, budget=0.8)
    b = sleeve("B", ("CCC", "DDD"), {"CCC": -0.03, "DDD": -0.04}, budget=0.5)
    r = run(tmp_path, [a, b])
    c = r.plan["combine"]
    assert c["book_vol_target"] == 0.06 and list(c["sleeves"]) == ["A", "B"]
    A, B = c["sleeves"]["A"], c["sleeves"]["B"]
    assert {k: A[k] for k in ("spec_id", "spec_path", "risk_budget", "vol_target",
                              "sleeve_nav", "status")} == {
        "spec_id": "A.v1", "spec_path": "ops/specs/A.json", "risk_budget": 0.8,
        "vol_target": 0.06, "sleeve_nav": 80_000.0, "status": "decided"}
    assert A["targets"] == {
        "AAA": {"current": 0, "target": 400, "kind": "weight", "reason": "A w=+0.050"},
        "BBB": {"current": 0, "target": 400, "kind": "weight", "reason": "A w=+0.100"}}
    assert B["targets"] == {
        "CCC": {"current": 0, "target": -50, "kind": "weight", "reason": "B w=-0.030"},
        "DDD": {"current": 0, "target": -50, "kind": "weight", "reason": "B w=-0.040"}}
    # The book is each symbol's one owner's target (universes are disjoint).
    assert {s: t["target"] for s, t in r.plan["targets"].items()} == \
        {"AAA": 400, "BBB": 400, "CCC": -50, "DDD": -50}
    assert "sleeve A: decided, budget 0.8" in r.out and "sleeve_nav $50,000.00" in r.out


# ------------------------------------------------------------------ a disabled sleeve

def _spec_file(dirpath, name, weights, vol=0.06):
    p = dirpath / f"{name}.frozen.json"
    p.write_text(json.dumps({"spec_id": f"{name}.v1", "status": "test", "capital_usd": 100_000.0,
                             "allocation": {"type": "static_weights", "weights": weights},
                             "frozen": {"vol_target_annual": vol}}))
    return p.name


def _book_file(dirpath, name, sleeves):
    p = dirpath / name
    p.write_text(json.dumps({"book_id": "t", "sleeves": sleeves}))
    return p


def _make_targets(spec):
    w = spec["allocation"]["weights"]
    return lambda asof, h, nav, op, **kw: [
        PositionTarget(s, LONG, weight=float(w[s]), reason=f"{spec['spec_id']} {w[s]}")
        for s in sorted(w)]


def test_a_disabled_sleeve_has_no_effect(tmp_path):
    from quantt.session import combine as cmb
    a = _spec_file(tmp_path, "a", {"AAA": 0.05, "BBB": 0.04})
    b = _spec_file(tmp_path, "b", {"CCC": 0.30, "DDD": 0.20})
    only = _book_file(tmp_path, "only_a.json",
                      [{"name": "A", "enabled": True, "spec_path": a, "risk_budget": 0.7}])
    with_b = _book_file(tmp_path, "a_and_b.json", [
        {"name": "A", "enabled": True, "spec_path": a, "risk_budget": 0.7},
        {"name": "B", "enabled": False, "spec_path": b, "risk_budget": 0.5},
        # A disabled entry is not read further: not even a spec that is not there.
        {"name": "A", "enabled": False, "spec_path": "no/such.json", "risk_budget": 9}])
    s1 = cmb.load_sleeves(only, tmp_path / "book.json", tmp_path, _make_targets)
    s2 = cmb.load_sleeves(with_b, tmp_path / "book.json", tmp_path, _make_targets)
    assert [e.name for e in s1] == [e.name for e in s2] == ["A"]
    r1, r2 = run(tmp_path / "1", s1), run(tmp_path / "2", s2)
    raw = [(x.state / D.isoformat() / "plan.json").read_bytes() for x in (r1, r2)]
    assert raw[0] == raw[1]
    assert r1.plan["orders"] and r1.client.accepted.keys() == r2.client.accepted.keys()
    # Enabled, B changes the book: the comparison above is not vacuous.
    with_b_on = _book_file(tmp_path, "b_on.json", [
        {"name": "A", "enabled": True, "spec_path": a, "risk_budget": 0.7},
        {"name": "B", "enabled": True, "spec_path": b, "risk_budget": 0.5}])
    r3 = run(tmp_path / "3", cmb.load_sleeves(with_b_on, tmp_path / "book.json", tmp_path,
                                               _make_targets))
    assert r3.plan["targets"] != r1.plan["targets"]


def test_a_disabled_sleeve_does_not_turn_the_combiner_on():
    """The released json plus a DISABLED budgeted sleeve is still the single-spec book."""
    from quantt.session import combine as cmb
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        released = json.loads(rn.BOOKS["cef"].book_path.read_text())
        released["sleeves"].append({"name": "c4", "enabled": False,
                                    "spec_path": "ops/specs/c4.frozen.json", "risk_budget": 0.3})
        bj = d / "book.json"
        bj.write_text(json.dumps(released))
        assert cmb.load_sleeves(bj, rn.BOOKS["cef"].spec_path, rn.REPO,
                                rn._sleeve_target_fn) is None


# ------------------------------------------------------------------ gate 5, per sleeve

UNI2 = {"A": ("AAA", "BBB"), "B": ("CCC", "DDD")}
FRESH = {s: ASOF for s in ("AAA", "BBB", "CCC", "DDD")}
STALE_CCC = {**FRESH, "CCC": dt.date(2026, 9, 25)}


def test_gate_5_per_sleeve_refuses_before_the_final_check_naming_the_sleeve():
    out, held = gt.gate_data_by_sleeve(ASOF, 0, FRESH, STALE_CCC, UNI2, False)
    assert held == {}
    assert out == [gt.Refusal("data", "sleeve B: NAV not dated 2026-09-28 for "
                                      "{'CCC': '2026-09-25'}")]


def test_gate_5_per_sleeve_holds_the_failing_sleeve_from_the_final_check():
    out, held = gt.gate_data_by_sleeve(ASOF, 0, FRESH, STALE_CCC, UNI2, True)
    assert out == [] and held == {"B": ["NAV not dated 2026-09-28 for {'CCC': '2026-09-25'}"]}
    # fetch_daily's INCOMPLETE is that same per-name condition: attributed, not book-wide.
    assert gt.gate_data_by_sleeve(ASOF, 4, FRESH, STALE_CCC, UNI2, True) == (out, held)
    # Every sleeve failing: nothing to decide, refused as today.
    both = {**STALE_CCC, "AAA": None}
    out2, held2 = gt.gate_data_by_sleeve(ASOF, 0, FRESH, both, UNI2, True)
    assert held2 == {} and {r.detail.split(":")[0] for r in out2} == {"sleeve A", "sleeve B"}


def test_gate_5_per_sleeve_keeps_a_failed_fetch_book_wide():
    for bad in (3, 1, "did not complete: timed out", "not run: cutoff"):
        out, held = gt.gate_data_by_sleeve(ASOF, bad, FRESH, FRESH, UNI2, True)
        assert held == {} and out == gt.gate_data(ASOF, bad, FRESH, FRESH,
                                                  ["AAA", "BBB", "CCC", "DDD"])
        assert out
    # INCOMPLETE with every name complete on the panel: the sources disagree.
    out, held = gt.gate_data_by_sleeve(ASOF, 4, FRESH, FRESH, UNI2, True)
    assert held == {} and len(out) == 1 and "disagree" in out[0].detail
    assert gt.gate_data_by_sleeve(ASOF, 0, FRESH, FRESH, UNI2, True) == ([], {})
    with pytest.raises(ValueError, match="True or False"):
        gt.gate_data_by_sleeve(ASOF, 0, FRESH, FRESH, UNI2, None)


def test_refresh_incomplete_is_fetch_dailys_exit_4():
    src = (rn.REPO / "scripts/cef/fetch_daily.py").read_text()
    assert gt.REFRESH_INCOMPLETE == 4
    assert "--require-asof D   exit 4 unless every deployed name has BOTH a close and a NAV" in src
    assert "INCOMPLETE for" in src and "return 4" in src


def _two_with_b_stale():
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05, "BBB": -0.05})
    b = sleeve("B", ("CCC", "DDD"), {"CCC": 0.20, "DDD": -0.20})
    navs = lambda asof, uni: {s: (dt.date(2026, 9, 25) if s == "CCC" else asof) for s in uni}  # noqa: E731
    return [a, b], navs


def test_in_a_session_a_stale_sleeve_refuses_the_morning_and_is_held_at_the_final_check(tmp_path):
    sl, navs = _two_with_b_stale()
    early = run(tmp_path / "early", sl, navs=navs, positions={"CCC": 70}, refresh_exit=4)
    assert early.code == rn.EXIT_REFUSED and early.client.accepted == {}
    assert any(x["detail"].startswith("sleeve B: NAV not dated") for x in early.plan["refusals"])
    late = run(tmp_path / "late", sl, navs=navs, positions={"CCC": 70}, refresh_exit=4,
               clock=FINAL)
    assert late.code == rn.EXIT_SENT and late.plan["refusals"] == []
    assert sorted(o["symbol"] for o in late.client.accepted.values()) == ["AAA", "BBB"]
    rb = late.plan["combine"]["sleeves"]["B"]
    assert rb["status"] == "held" and "CCC" in rb["held_why"][0]
    assert rb["targets"]["CCC"] == {"current": 70, "target": 70, "kind": "held",
                                    "reason": rb["targets"]["CCC"]["reason"]}
    assert late.plan["targets"]["CCC"]["target"] == 70     # kept, not flattened
    assert late.plan["combine"]["sleeves"]["A"]["status"] == "decided"


# ------------------------------------------------------------------ the stale-NAV gate, per sleeve

class FakeNavGate:
    def __init__(self, hold):
        self._hold, self.universes = hold, []

    def run(self, asof, universe, mode, now, final, record=None):
        self.universes.append(tuple(universe))
        return SimpleNamespace(hold=dict(self._hold), deferred=False,
                               to_dict=lambda: {"mode": mode, "fake": True}, lines=lambda: [])

    def still_holds(self, res):
        return []


def test_a_stale_nav_hold_goes_only_to_the_sleeve_that_owns_the_name(tmp_path):
    ca, cb = [], []
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05}, calls=ca)
    b = sleeve("B", ("CCC", "DDD"), {"DDD": -0.05}, calls=cb)
    c, deps, state, _, _ = make(tmp_path, clock_ts=MORNING,
                                now_utc=MORNING.astimezone(dt.timezone.utc),
                                execution={"mode": "cls", "bp_shortfall": "scale"},
                                closes=lambda asof, uni: {s: (CL[s], ASOF) for s in uni})
    gate = FakeNavGate({"BBB": "CEFConnect has no row"})
    deps.sleeves, deps.stale_nav, deps.nav_gate = (a, b), ng.ON, gate
    assert rn.run_session(BOOK, BOOK_SPEC, deps, preview=True) == rn.EXIT_PREVIEW
    assert gate.universes == [("AAA", "BBB", "CCC", "DDD")]          # once, over the union
    assert ca[0]["nav_hold"] == {"asof": ASOF, "names": {"BBB": "CEFConnect has no row"}}
    assert "nav_hold" not in cb[0]
    plan = json.loads((state / D.isoformat() / "plan.json").read_text())
    assert plan["combine"]["sleeves"]["A"]["nav_hold"] == ["BBB"]
    assert "nav_hold" not in plan["combine"]["sleeves"]["B"]


def _incomplete_day(tmp_path):
    """A NAV panel on which the refresh exits 4: CCC (sleeve B) has no NAV dated
    ASOF. AAA (sleeve A) repeats its previous NAV and CEFConnect has no D row,
    so the stale-NAV gate finds it UNVERIFIED. BBB and DDD moved: no trigger."""
    import pandas as pd
    from quantt.session.tests.test_nav_gate import PREV, PREV2, FakeCC
    rows = {"AAA": (9.90, 10.00, 10.00), "BBB": (19.80, 20.00, 20.10),
            "CCC": (29.70, 30.00, None), "DDD": (39.60, 40.00, 40.20)}
    panel = tmp_path / "cef_nav.parquet"
    pd.DataFrame([{"date": pd.Timestamp(d), "nav": v, "ticker": t}
                  for t, vals in rows.items() for d, v in zip((PREV2, PREV, ASOF), vals)
                  if v is not None]).to_parquet(panel)
    cc = FakeCC({"AAA": (9.98, None), "BBB": (20.00, 20.10), "CCC": (30.00, None),
                 "DDD": (40.00, 40.20)})
    gate = ng.PanelGate(nav_path=panel, log_path=tmp_path / "nav_fallback_log.csv",
                        lock_path=tmp_path / ".fetch.lock", reader=cc, lock_wait_s=1.0)
    a = sleeve("A", ("AAA", "BBB"), {"AAA": 0.05, "BBB": -0.05})
    b = sleeve("B", ("CCC", "DDD"), {"CCC": 0.20, "DDD": -0.20})
    return [a, b], gate, (lambda asof, uni: rn.last_navs(panel, asof, uni)), panel


def test_on_an_incomplete_refresh_the_stale_nav_gate_still_checks_the_sleeves_that_decide(
        tmp_path):
    """Release-check of 00ec423: on exit 4 `_nav_gate` did not run, gate 5 held
    sleeve B at the final check, and sleeve A was sent with no stale-NAV check
    (AAA bought on an unverified NAV) under a plan.json that said "gate 5
    refuses the day". Now the gate runs over the union on a combined book."""
    sleeves, gate, navs, panel = _incomplete_day(tmp_path)
    before = panel.read_bytes()
    r = run(tmp_path / "s", sleeves, navs=navs, positions={"AAA": 40, "CCC": 70},
            refresh_exit=4, clock=FINAL, stale_nav=ng.ON, nav_gate=gate)
    assert r.code == rn.EXIT_SENT and r.plan["refusals"] == []
    g = r.plan["nav_gate"]
    assert "not_run" not in g and g["refresh_exit"].startswith("4 (INCOMPLETE)")
    acts = {c["ticker"]: (c["trigger"], c["action"]) for c in g["checks"]}
    assert acts["AAA"][1] == "held"                  # unverified at the final check
    assert acts["CCC"] == ("", "")                   # no NAV dated D: gate 5's, untouched
    assert panel.read_bytes() == before              # nothing replaced, nothing written
    c = r.plan["combine"]["sleeves"]
    assert c["A"]["status"] == "decided" and c["A"]["nav_hold"] == ["AAA"]
    assert c["B"]["status"] == "held"
    # AAA kept at its shares (no order on an unverified NAV); BBB traded; B untouched.
    assert sorted(o["symbol"] for o in r.client.accepted.values()) == ["BBB"]
    assert r.plan["targets"]["AAA"]["target"] == 40 and r.plan["targets"]["CCC"]["target"] == 70
    assert (r.state / ng.CSV_NAME).exists()          # the gate's own record, written first


def test_on_an_incomplete_refresh_before_the_final_check_the_record_says_what_happened(tmp_path):
    sleeves, gate, navs, _ = _incomplete_day(tmp_path)
    r = run(tmp_path / "s", sleeves, navs=navs, positions={"AAA": 40, "CCC": 70},
            refresh_exit=4, clock=MORNING, stale_nav=ng.ON, nav_gate=gate)
    assert r.code == rn.EXIT_REFUSED and r.client.accepted == {}
    g = r.plan["nav_gate"]
    assert "not_run" not in g and g["would_defer"] is True and g["final_check"] is False
    details = [x["detail"] for x in r.plan["refusals"]]
    assert any(d.startswith("sleeve B: NAV not dated") for d in details)    # gate 5, per sleeve
    assert any(d.startswith("stale-NAV gate: NAV unverified for ['AAA']") for d in details)


# ------------------------------------------------------------------ what it refuses to guess

def test_not_yet_allowed_a_held_position_in_a_symbol_two_sleeves_trade_fails_naming_it(
        tmp_path, shared_symbols_allowed):
    """The check that stays behind SHARED_SYMBOLS_ALLOWED: even with it on, a held
    shared position is never split by a guess."""
    a = sleeve("A", ("AAA", "BBB"), {"BBB": 0.05})
    b = sleeve("B", ("BBB", "CCC"), {"BBB": -0.02})
    r = run(tmp_path, [a, b], positions={"BBB": 100})
    assert r.code == rn.EXIT_FAIL and r.client.accepted == {}
    assert "BBB" in r.out and "sub-ledger" in r.out


def test_each_sleeve_sees_only_its_own_holdings(tmp_path):
    ca, cb = [], []
    a = sleeve("A", ("AAA", "BBB"), {"AAA": ("qty", 30)}, calls=ca)
    b = sleeve("B", ("CCC", "DDD"), {"CCC": ("qty", -20)}, calls=cb)
    run(tmp_path, [a, b], positions={"AAA": 30, "CCC": -20})
    assert ca[0]["holdings"] == {"AAA": 30} and cb[0]["holdings"] == {"CCC": -20}
    assert ca[0]["opening"] is False and ca[0]["asof"] == ASOF


@pytest.mark.parametrize("sleeves, match", [
    ([{"name": "A", "spec_path": "a.json"}, {"name": "B", "spec_path": "b.json"}],
     "2 enabled sleeves and no risk_budget"),
    ([{"name": "A", "spec_path": "b.json"}], "must be the same file"),
    ([{"name": "A", "spec_path": "a.json", "risk_budget": 0.5},
      {"name": "B", "spec_path": "b.json"}], "carry no risk_budget"),
    ([{"name": "A", "spec_path": "a.json", "risk_budget": 0.0}], r"in \(0, 1\]"),
    ([{"name": "A", "spec_path": "a.json", "risk_budget": 1.5}], r"in \(0, 1\]"),
    ([{"name": "A", "spec_path": "a.json", "risk_budget": True}], r"in \(0, 1\]"),
    ([{"name": "A", "spec_path": "a.json", "risk_budget": "0.5"}], r"in \(0, 1\]"),
    ([{"name": "A", "spec_path": "a.json", "risk_budget": float("nan")}], r"in \(0, 1\]"),
    ([{"name": "A", "spec_path": "a.json", "enabled": "true"}], "is not a bool"),
    ([{"name": "A", "spec_path": "a.json", "risk_budget": 0.5},
      {"name": "A", "spec_path": "b.json", "risk_budget": 0.5}], "two enabled sleeves are named"),
    ([{"name": "A", "spec_path": "pct.json", "risk_budget": 0.5}], "outside"),
    ([{"name": "A", "spec_path": "novol.json", "risk_budget": 0.5}], "vol_target_annual is None"),
    ([{"name": "A", "spec_path": "missing.json", "risk_budget": 0.5}], "is not a file"),
    ([{"name": "A", "spec": {}, "spec_path": "a.json", "risk_budget": 0.5}], "inline"),
])
def test_a_book_json_the_combiner_cannot_read_raises_naming_why(tmp_path, sleeves, match):
    from quantt.session import combine as cmb
    _spec_file(tmp_path, "a", {"AAA": 0.1})
    _spec_file(tmp_path, "b", {"BBB": 0.1})
    _spec_file(tmp_path, "pct", {"AAA": 0.1}, vol=6)          # a percent, not a fraction
    (tmp_path / "novol.json").write_text(json.dumps(
        {"spec_id": "n", "status": "t", "capital_usd": 1.0,
         "allocation": {"type": "static_weights", "weights": {"AAA": 0.1}}}))
    for e in sleeves:
        e["spec_path"] = {"a.json": "a.frozen.json", "b.json": "b.frozen.json",
                          "pct.json": "pct.frozen.json"}.get(e["spec_path"], e["spec_path"])
    bj = _book_file(tmp_path, "book.json", sleeves)
    with pytest.raises(cmb.CombineError, match=match):
        cmb.load_sleeves(bj, tmp_path / "a.frozen.json", tmp_path, _make_targets)


def test_a_book_json_without_sleeves_is_the_single_spec_book(tmp_path):
    from quantt.session import combine as cmb
    bj = tmp_path / "book.json"
    bj.write_text(json.dumps({"book_id": "t"}))
    assert cmb.load_sleeves(bj, tmp_path / "x.json", tmp_path, _make_targets) is None


def test_the_book_vol_target_is_the_book_specs_and_must_be_a_fraction():
    from quantt.session import combine as cmb
    assert cmb.book_vol_target(BOOK_SPEC) == 0.06
    for bad in (None, 6.0, 0.0, True, "0.06"):
        spec = json.loads(json.dumps(BOOK_SPEC))
        spec["frozen"]["vol_target_annual"] = bad
        with pytest.raises(cmb.CombineError):
            cmb.book_vol_target(spec)
