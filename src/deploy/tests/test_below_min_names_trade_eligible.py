"""`below_min_names = "trade_eligible"` on the core sleeve (CEF trial 55, te4, PAPER ONLY).

THE RULE (results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md §1.1-§1.3, approved by the team
lead 2026-11-03 with every recommended answer in §10). On a session with fewer than `min_names`
eligible names but at least `below_min_names_floor`, and no NAV holds, the sleeve builds the book
on the eligible names with its own construction instead of going FLAT. The harness version, which
the live build must equal, is `band_frontier.band_gross_capped(below_min_names="trade_eligible",
floor=)` on `build_targets(min_names=floor)`.

WHAT EACH GROUP WOULD CATCH:

  1. THE PAPER-ONLY REFUSAL (§1.2, Q14). `account` is None or exactly "paper" at construction,
     whatever the spec says; under the key every decide raises, naming it, without the paper
     declaration or without a well-formed `extras["thin_rule"]` -- on a full session too. With
     the key absent neither is read.
  2. THE REDUCED BUILD. 5 and 4 eligible build on the set: the unit target equals the harness's
     `_target_row` then `_cap_gross` (flat book, opening session) and the band's one step from a
     held book; 3 eligible (below the floor) goes FLAT, as today.
  3. WHAT IS DELIBERATELY NOT CHANGED. Any hold leaves the build off, the tag in place, reduced
     False (Q10). The min-weight guard stays at `min_names` (Q12): a 4-name set with one name
     under `min_abs_weight` is not re-neutralised and that name is FLAT. On a session with at
     least `min_names` eligible the targets are the key-absent targets apart from
     `meta["cef_thin"]`.
  4. THE NEW REFUSAL AND THE STOPS. 0/0 (every eligible z equal) raises on the reduced path and
     only there. A stop (K0 or gate 7) sends a session that would have built the reduced book to
     the flatten path and records `stopped_by`; nowhere else does it record anything.
  5. THE CALLERS THAT BUILD WITHOUT DECIDING. With the key set, the sleeve is still constructed
     the way `quantt/session/run.py::spec_panel` (`CEFDiscountSleeve(spec, 0.0).panel_paths()`),
     `ops/common.py::deployed_tickers` and `quantt/session/combine.py::load_sleeves` build it
     every session (the owner's requirement). run.py is not imported here: it holds the code that
     sends orders; its one line is reproduced.
  6. THE HARNESS ON THE REAL PANEL. Every reduced fit date (floor <= n < min_names eligible,
     before 2023-01-01): the sleeve's unit target equals `_cap_gross(_target_row(...))` with
     `opening_session` True, and the sleeve's band step from the harness's own previous held book
     equals the harness's next row, at 1e-12, except names under `min_abs_weight` (the dust
     filter, a declared divergence, §8 item 1). Skipped, saying why, when `data/` lacks the panel.

Synthetic panels for groups 1-5 (`test_group_cap._write_panel`, 12 funds): the conclusions are
about this code, never about a market.

FAILS ON ac15d09 (the code before te4): there the sleeve's constructor takes no `account`, the
registry refuses "trade_eligible", and nothing builds a reduced book; every test here fails or
errors on it except the real-panel group when `data/` is absent (it skips).
"""
import copy
import json
import math

import numpy as np
import pandas as pd
import pytest

from src.deploy import registry
from src.deploy.sleeve import FLAT, MarketState
from src.deploy.sleeves import cef_discount as cefmod
from src.deploy.sleeves.cef_discount import CEFDiscountSleeve, _cap_gross
from src.deploy.tests.test_group_cap import (MUNI, NAV_USD, TAX, TICKERS, _fingerprint,
                                             _write_panel)
from src.deploy.tests.test_group_cap import _spec as _gc_spec

KEY = "below_min_names"
THIN = "cef_thin"
NO_STOP = {"stop": None}
ABSENT = object()
M = 1.3                      # a multiplier on the synthetic spec, so m is exercised everywhere


def _spec(rule="trade_eligible", floor=4, m=M, cap=1.8, **frozen):
    s = copy.deepcopy(_gc_spec(max_gross_stress=cap) if cap is not None else _gc_spec())
    s["spec_id"], s["status"] = "synthetic-te4", "test"
    if m is not None:
        s["frozen"]["sizing_multiplier"] = m
    if rule is not None:
        s["frozen"][KEY] = rule
    if floor is not None and rule == "trade_eligible":
        s["frozen"]["below_min_names_floor"] = floor
    if rule == "trade_eligible":     # K3's run length: required under the rule (registry)
        s.setdefault("risk", {}).update(
            thin_k3_run_sessions=3,
            _thin_k3_run_sessions_note="test only: §6.3's 3 consecutive reduced closes")
    s["frozen"].update(frozen)
    return s


def _run(spec, asof, holdings=None, *, account="paper", thin_rule=NO_STOP, opening=False,
         extras=None):
    sl = CEFDiscountSleeve(spec, NAV_USD, account=account)
    ex = {"sleeve_nav": NAV_USD, "opening_session": opening, **(extras or {})}
    if thin_rule is not ABSENT:
        ex["thin_rule"] = thin_rule
    ms = MarketState(asof=pd.Timestamp(asof), prices=pd.DataFrame(),
                     holdings=dict(holdings or {}), extras=ex)
    return sl.target_positions(pd.Timestamp(asof), ms)


def _strip(targets):
    """The targets with `meta["cef_thin"]` removed and nothing else touched."""
    import dataclasses
    return [dataclasses.replace(t, meta={k: v for k, v in t.meta.items() if k != THIN})
            for t in targets]


def _thin_of(targets):
    recs = [t.meta.get(THIN) for t in targets]
    assert all(r is not None for r in recs), "a target without meta['cef_thin']"
    assert all(r == recs[0] for r in recs), "targets disagree on meta['cef_thin']"
    return recs[0]


def _keep_liquid(keep):
    """Every name outside `keep` illiquid for the last 70 sessions (ADV about $1m under the $3m
    floor), so exactly `keep` is eligible on the last date."""
    P = pd.read_parquet(cefmod.PX_PATH)
    last70 = sorted(P["date"].unique())[-70:]
    P.loc[~P["ticker"].isin(keep) & P["date"].isin(last70), "volume"] = 100_000.0
    P.to_parquet(cefmod.PX_PATH)


def _unit(targets, closes):
    """{name: the UNIT weight}: weight / m for a weight target, qty x close / (nav x m) for a
    band HOLD (a share count), 0 for FLAT."""
    out = {}
    for t in targets:
        if t.side == FLAT:
            out[t.instrument] = 0.0
        elif t.qty is not None:
            out[t.instrument] = float(t.signed_qty()) * closes[t.instrument] / (NAV_USD * M)
        else:
            out[t.instrument] = float(t.weight) / M
    return out


def _harness(asof):
    """The harness on the synthetic panel: (eligible row, the unit target `_target_row` builds
    on it, ret, the panel's index position). `band_frontier` reads the spec's z_window,
    vol target and ADV floor; the synthetic spec must agree with them, which is asserted."""
    from scripts.cef import band_frontier as bf
    f = _gc_spec()["frozen"]
    assert (bf.Z_WINDOW, bf.VOL_TARGET, bf.MIN_ADV, bf.MIN_PERIODS, bf.VOL_LOOKBACK) == \
        (f["z_window"], f["vol_target_annual"], f["min_adv_usd"], 120, 63)
    p = bf.build_panel(universe=TICKERS, source=(cefmod.PX_PATH, cefmod.NAV_PATH))
    i = p["z"].index.get_loc(pd.Timestamp(asof))
    row = bf._eligible(p["z"].iloc[i], p["adv"].iloc[i], bf.MIN_ADV)
    return row, bf._target_row(row, p["ret"], i), p


@pytest.fixture
def panel(tmp_path, monkeypatch):
    return _write_panel(tmp_path, monkeypatch)


# ---------------------------------------------------------------------------
# 1. the paper-only refusal
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("account", ["live", "Paper", "paper ", "", "PAPER", 1, True, b"paper",
                                     ["paper"]])
@pytest.mark.parametrize("rule", [None, "trade_eligible"])
def test_any_account_but_none_or_paper_refuses_at_construction(account, rule):
    with pytest.raises(ValueError, match="must be None or exactly 'paper'"):
        CEFDiscountSleeve(_spec(rule=rule), NAV_USD, account=account)


@pytest.mark.parametrize("rule", [None, "flatten", "hold", "trade_eligible"])
def test_none_and_paper_construct_under_every_rule(rule):
    for account in (None, "paper"):
        CEFDiscountSleeve(_spec(rule=rule), NAV_USD, account=account)


@pytest.mark.parametrize("n_liquid", [12, 4])
def test_the_key_without_the_paper_declaration_refuses_every_decide(panel, n_liquid):
    asof, _ = panel
    if n_liquid == 4:
        _keep_liquid(MUNI[:2] + TAX[:2])
    with pytest.raises(ValueError, match=r"below_min_names='trade_eligible' is PAPER ONLY"):
        _run(_spec(), asof, account=None)


@pytest.mark.parametrize("n_liquid", [12, 4])
def test_the_key_without_thin_rule_refuses_every_decide(panel, n_liquid):
    asof, _ = panel
    if n_liquid == 4:
        _keep_liquid(MUNI[:2] + TAX[:2])
    with pytest.raises(ValueError, match=r"needs extras\['thin_rule'\]"):
        _run(_spec(), asof, thin_rule=ABSENT)


@pytest.mark.parametrize("bad", [None, {}, "K0", {"stop": "K0"}, {"stop": {}},
                                 {"stop": None, "also": 1},
                                 {"stop": {"by": "K1", "why": "drawdown"}},
                                 {"stop": {"by": "K0"}}, {"stop": {"by": "K0", "why": ""}},
                                 {"stop": {"by": "K0", "why": "   "}},
                                 {"stop": {"by": "K0", "why": 7}},
                                 {"stop": {"by": "gate7", "why": "x", "extra": 1}}])
def test_a_malformed_thin_rule_refuses(panel, bad):
    asof, _ = panel
    with pytest.raises(ValueError, match=r"extras\['thin_rule'\] must be"):
        _run(_spec(), asof, thin_rule=bad)


@pytest.mark.parametrize("rule", [None, "flatten"])
def test_with_the_key_absent_neither_declaration_is_read(panel, rule):
    asof, _ = panel
    held = {"MUN1": 900.0, "TAX2": -700.0}
    want = _fingerprint(_run(_spec(rule=rule), asof, held, account=None, thin_rule=ABSENT))
    for account, tr in (("paper", ABSENT), (None, {"stop": {"by": "K0", "why": "x"}}),
                        ("paper", "not even a dict")):
        got = _run(_spec(rule=rule), asof, held, account=account, thin_rule=tr)
        assert _fingerprint(got) == want
        assert all(THIN not in t.meta for t in got)


# ---------------------------------------------------------------------------
# 2. the reduced build
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("keep", [MUNI[:3] + TAX[:2], MUNI[:2] + TAX[:2]], ids=["5", "4"])
def test_a_reduced_session_builds_the_harness_target_on_the_eligible_set(panel, keep):
    asof, close = panel
    _keep_liquid(keep)
    row, unit, _ = _harness(asof)
    assert sorted(row.index) == sorted(keep)
    want, _ = _cap_gross(unit, 1.8 / M)
    out = _run(_spec(), asof, opening=True)
    got = _unit(out, close)
    minw = _gc_spec()["frozen"]["min_abs_weight"]
    for tk in TICKERS:
        w = float(want.get(tk, 0.0))
        if abs(w) >= minw:
            assert abs(got[tk] - w) <= 1e-12, (tk, got[tk], w)
            assert f"reduced-set n={len(keep)}/6" in next(t.reason for t in out
                                                          if t.instrument == tk)
        else:
            assert got[tk] == 0.0, tk
    assert any(got[t] > 0 for t in keep) and any(got[t] < 0 for t in keep)
    assert _thin_of(out) == {"eligible": sorted(keep), "n": len(keep), "min_names": 6, "floor": 4,
                             "holds": False, "reduced": True, "stopped_by": None}
    # the key absent: today's rule on the same session, every name FLAT
    absent = _run(_spec(rule=None), asof, opening=True, account=None, thin_rule=ABSENT)
    assert {(t.side, t.reason) for t in absent} == {(FLAT, f"cef: only {len(keep)} eligible names")}


@pytest.mark.parametrize("ceiling", [1.8, 10.0], ids=["ceiling-binds", "ceiling-slack"])
def test_a_reduced_session_bands_from_the_held_book_as_the_harness_does(panel, ceiling):
    """One band step from a held book: the harness loop's body (band_frontier.band_gross_capped,
    the band to the EDGE, then `_cap_gross` on the held book) applied to the same held weights and
    the same unit target. The held book holds a name that is no longer eligible (cut toward zero
    by the band, not closed) and one inside the band (left alone, emitted in shares). At 1.8 the
    ceiling binds on this panel and every line becomes a trade (cef_discount.py, THE BAND'S HOLDS
    BECOME TRADES WHEN THIS BINDS); at 10 it does not, and the HOLDs stay in shares."""
    asof, close = panel
    keep = MUNI[:2] + TAX[:2]
    _keep_liquid(keep)
    _, unit, _ = _harness(asof)
    band, cap = _gc_spec()["frozen"]["band_width"], ceiling / M
    target = unit.reindex(TICKERS).fillna(0.0)
    held_w = {MUNI[0]: float(target[MUNI[0]]) + 0.01,       # inside the band: HOLD
              TAX[0]: float(target[TAX[0]]) - 0.20,         # outside: to the edge
              MUNI[4]: 0.15,                                # not eligible: cut to the edge
              TAX[5]: -0.03}                                # not eligible, inside: HOLD
    holdings = {tk: w * NAV_USD * M / close[tk] for tk, w in held_w.items()}
    cur = pd.Series({tk: held_w.get(tk, 0.0) for tk in TICKERS})
    gap = target - cur
    step = cur.where(gap.abs() <= band, target - np.sign(gap) * band)
    want, f = _cap_gross(step, cap)
    assert (f < 1.0) is (ceiling == 1.8)
    out = _run(_spec(cap=ceiling), asof, holdings)
    got = _unit(out, close)
    minw = _gc_spec()["frozen"]["min_abs_weight"]
    by = {t.instrument: t for t in out}
    for tk in TICKERS:
        if by[tk].side == FLAT and abs(float(want[tk])) < minw:
            continue                                         # the dust filter (§8 item 1)
        assert abs(got[tk] - float(want[tk])) <= 1e-12, (tk, got[tk], float(want[tk]))
    holds = [tk for tk in (MUNI[0], TAX[5]) if by[tk].qty is not None]
    assert holds == ([] if f < 1.0 else [MUNI[0], TAX[5]])                  # HOLDs are shares
    assert abs(got[MUNI[4]] - band * f) <= 1e-12             # cut to the edge, not closed
    assert _thin_of(out)["reduced"] is True


def test_three_eligible_is_below_the_floor_and_goes_flat(panel):
    asof, _ = panel
    keep = MUNI[:2] + TAX[:1]
    _keep_liquid(keep)
    for held in ({}, {"MUN1": 900.0, "TAX1": -700.0, "MUN5": 300.0}):
        out = _run(_spec(), asof, held)
        assert {(t.side, t.reason) for t in out} == {(FLAT, "cef: only 3 eligible names")}
        assert _thin_of(out) == {"eligible": sorted(keep), "n": 3, "min_names": 6, "floor": 4,
                                 "holds": False, "reduced": False, "stopped_by": None}
        assert _strip(out) == _run(_spec(rule=None), asof, held, account=None, thin_rule=ABSENT)


def test_the_floor_is_read_from_the_spec(panel):
    """A 4-name session trades at floor 4 and goes FLAT at floor 5: the sleeve reads the key, it
    does not carry a 4 of its own."""
    asof, _ = panel
    _keep_liquid(MUNI[:2] + TAX[:2])
    assert _thin_of(_run(_spec(floor=4), asof, opening=True))["reduced"] is True
    out = _run(_spec(floor=5), asof, opening=True)
    assert {(t.side, t.reason) for t in out} == {(FLAT, "cef: only 4 eligible names")}
    assert _thin_of(out)["floor"] == 5 and _thin_of(out)["reduced"] is False


# ---------------------------------------------------------------------------
# 3. what is deliberately not changed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("keep,whole", [(MUNI[:3] + TAX[:2], False),
                                        (MUNI[:4] + TAX[:2], True)], ids=["5-1", "6-1"])
def test_any_hold_leaves_the_build_off_and_today_s_path_on(panel, keep, whole):
    """A NAV hold on one eligible name leaves 4 (or 5) in the cross-section: at least the floor,
    but the reduced build must not run (Q10). Today's block runs, tag included: the whole book
    holds when the hold alone is why the count is short (6-1), else every name but the held one
    is FLAT (5-1)."""
    asof, _ = panel
    _keep_liquid(keep)
    held = {MUNI[0]: 900.0, TAX[0]: -700.0, MUNI[5]: 300.0}
    nav_hold = {"nav_hold": {"asof": asof, "names": {MUNI[0]: "CEFConnect unreachable"}}}
    out = _run(_spec(), asof, held, extras=nav_hold)
    want = _run(_spec(rule=None), asof, held, account=None, thin_rule=ABSENT, extras=nav_hold)
    assert _fingerprint(_strip(out)) == _fingerprint(want)
    assert all(cefmod.SHORT_OF_MIN_NAMES in t.meta for t in out)
    rec = _thin_of(out)
    assert rec["holds"] is True and rec["reduced"] is False and rec["stopped_by"] is None
    assert rec["n"] == len(keep) - 1 >= rec["floor"]
    by = {t.instrument: t for t in out}
    assert by[MUNI[0]].qty == 900.0                          # the held name keeps its shares
    assert (by[TAX[0]].qty == -700.0) is whole               # the rest hold only on 6-1


def test_one_name_under_min_abs_weight_is_flat_and_the_set_is_not_re_neutralised(panel):
    """Q12: the guard needs `min_names` survivors. A 4-name reduced set with one name under the
    threshold keeps the other three weights EXACTLY as built (no re-neutralising, no
    re-normalising), and the fourth is FLAT; the book is left net by that weight."""
    asof, _ = panel
    keep = MUNI[:2] + TAX[:2]
    _keep_liquid(keep)
    base = _run(_spec(cap=None, min_abs_weight=1e-9), asof, opening=True)
    w = {t.instrument: float(t.weight) for t in base if t.side != FLAT}
    assert sorted(w) == sorted(keep)
    order = sorted(w, key=lambda k: abs(w[k]))
    small, nxt = order[0], order[1]
    thr = (abs(w[small]) + abs(w[nxt])) / 2 / M              # in unit weight, as the guard reads
    out = _run(_spec(cap=None, min_abs_weight=thr), asof, opening=True)
    by = {t.instrument: t for t in out}
    assert by[small].side == FLAT and "below min weight" in by[small].reason
    for tk in order[1:]:
        assert float(by[tk].weight) == w[tk], tk             # bit for bit: not re-neutralised
    net = sum(float(by[tk].weight) for tk in order[1:])
    assert abs(net + w[small]) <= 1e-12 and abs(net) > 0     # the residual is the dropped weight


@pytest.mark.parametrize("opening,held", [(True, {}), (False, {}),
                                          (False, {"MUN1": 900.0, "TAX2": -700.0, "MUN5": 300.0,
                                                   "TAX6": -400.0})])
def test_with_min_names_eligible_the_targets_are_the_key_absent_targets(panel, opening, held):
    asof, _ = panel
    out = _run(_spec(), asof, held, opening=opening)
    want = _run(_spec(rule=None), asof, held, account=None, thin_rule=ABSENT, opening=opening)
    assert _fingerprint(_strip(out)) == _fingerprint(want)
    rec = _thin_of(out)
    assert rec["n"] == 12 and rec["reduced"] is False and rec["stopped_by"] is None
    assert not any("reduced-set" in t.reason for t in out)


# ---------------------------------------------------------------------------
# 4. the new refusal, and the stops
# ---------------------------------------------------------------------------

def _all_at_the_clip(names):
    """On the last date each named fund trades 50% over its NAV, far above its history, so its z
    is clipped at +4: every one equal."""
    P = pd.read_parquet(cefmod.PX_PATH)
    N = pd.read_parquet(cefmod.NAV_PATH)
    last = P["date"].max()
    for tk in names:
        nav = float(N.loc[(N.ticker == tk) & (N.date == last), "nav"].iloc[0])
        P.loc[(P.ticker == tk) & (P.date == last), "close"] = nav * 1.5
    P.to_parquet(cefmod.PX_PATH)


def test_zero_over_zero_raises_on_the_reduced_path(panel):
    asof, _ = panel
    keep = MUNI[:2] + TAX[:2]
    _keep_liquid(keep)
    _all_at_the_clip(keep)
    with pytest.raises(ValueError, match="not finite") as e:
        _run(_spec(), asof)
    assert str(pd.Timestamp(asof).date()) in str(e.value)
    assert str(sorted(keep)) in str(e.value)
    # the key absent: today's rule, FLAT, no raise
    absent = _run(_spec(rule=None), asof, account=None, thin_rule=ABSENT)
    assert {t.reason for t in absent} == {"cef: only 4 eligible names"}


def test_zero_over_zero_on_a_full_session_is_unchanged(panel):
    """Every one of 6 eligible names at the clip: a FULL session. Its path is today's (the
    owner's open question, PR #33 §5.H), under the key as without it."""
    asof, _ = panel
    keep = MUNI[:3] + TAX[:3]
    _keep_liquid(keep)
    _all_at_the_clip(keep)
    held = {"MUN1": 900.0, "TAX2": -700.0}
    out = _run(_spec(), asof, held)
    want = _run(_spec(rule=None), asof, held, account=None, thin_rule=ABSENT)
    assert _fingerprint(_strip(out)) == _fingerprint(want)
    assert _thin_of(out)["reduced"] is False


@pytest.mark.parametrize("by", ["K0", "gate7"])
def test_a_stop_takes_the_flatten_path_and_says_so(panel, by):
    asof, _ = panel
    keep = MUNI[:3] + TAX[:2]
    _keep_liquid(keep)
    stop = {"stop": {"by": by, "why": "drawdown record HALVE" if by == "K0"
                     else "PDI not shortable today"}}
    held = {"MUN1": 900.0, "TAX1": -700.0}
    out = _run(_spec(), asof, held, thin_rule=stop)
    assert all(t.side == FLAT for t in out)
    assert {t.reason for t in out} == {
        f"cef: only 5 eligible names (reduced build stopped by {by}: {stop['stop']['why']})"}
    assert _thin_of(out) == {"eligible": sorted(keep), "n": 5, "min_names": 6, "floor": 4,
                             "holds": False, "reduced": False, "stopped_by": by}


def test_a_stop_records_nothing_where_no_reduced_build_would_have_run(panel):
    asof, _ = panel
    stop = {"stop": {"by": "K0", "why": "drawdown record UNMEASURED"}}
    held = {"MUN1": 900.0, "TAX1": -700.0}
    # a full session: the stop removes nothing
    full = _run(_spec(), asof, held, thin_rule=stop)
    assert _fingerprint(full) == _fingerprint(_run(_spec(), asof, held))
    assert _thin_of(full)["stopped_by"] is None
    # below the floor: flat anyway, and the reason is today's
    _keep_liquid(MUNI[:2] + TAX[:1])
    below = _run(_spec(), asof, held, thin_rule=stop)
    assert {t.reason for t in below} == {"cef: only 3 eligible names"}
    assert _thin_of(below)["stopped_by"] is None


def test_a_stop_with_a_hold_records_nothing(panel):
    asof, _ = panel
    _keep_liquid(MUNI[:3] + TAX[:2])
    held = {MUNI[0]: 900.0, TAX[0]: -700.0}
    nav_hold = {"nav_hold": {"asof": asof, "names": {MUNI[0]: "unverified"}}}
    out = _run(_spec(), asof, held, thin_rule={"stop": {"by": "gate7", "why": "x"}},
               extras=nav_hold)
    assert _fingerprint(out) == _fingerprint(_run(_spec(), asof, held, extras=nav_hold))
    assert _thin_of(out)["stopped_by"] is None and _thin_of(out)["holds"] is True


@pytest.mark.parametrize("opening", [True, False], ids=["opening", "held"])
@pytest.mark.parametrize("nav", [ABSENT, 0.0, -1.0], ids=["missing", "zero", "negative"])
def test_the_nav_unknown_refusal_after_the_min_names_test_records_no_reduced_build(panel, opening,
                                                                                   nav):
    """The band's "sleeve NAV unknown" refusal (both branches: the opening session and a held
    book) returns every name FLAT AFTER the min_names test has decided the session could build
    the reduced book. The record must say what produced the targets: the refusal, not the reduced
    build. `reduced` is how the pre-registration counts a reduced decision (§4.2: "the sleeve's
    reduced build ran and its targets were sent"), so a True here would score a flattened session
    as one. Found by the quant and adversarial reviews of f1d9f62: there `reduced` was set at the
    min_names test and read True on this path."""
    asof, _ = panel
    keep = MUNI[:2] + TAX[:2]
    _keep_liquid(keep)
    held = {} if opening else {MUNI[0]: 900.0, TAX[0]: -700.0}
    ex = {"opening_session": opening, "thin_rule": NO_STOP}
    if nav is not ABSENT:
        ex["sleeve_nav"] = nav
    sl = CEFDiscountSleeve(_spec(), NAV_USD, account="paper")
    out = sl.target_positions(pd.Timestamp(asof),
                              MarketState(asof=pd.Timestamp(asof), prices=pd.DataFrame(),
                                          holdings=dict(held), extras=ex))
    assert {(t.side, t.reason) for t in out} == {(FLAT, "cef: band on but sleeve NAV unknown")}
    assert _thin_of(out) == {"eligible": sorted(keep), "n": 4, "min_names": 6, "floor": 4,
                             "holds": False, "reduced": False, "stopped_by": None}
    # the same session WITH its NAV is the reduced build, so the refusal is what moved the flag
    assert _thin_of(_run(_spec(), asof, held, opening=opening))["reduced"] is True


def test_a_reduced_set_is_recorded_on_every_return_under_the_key(panel, monkeypatch):
    """Under the key every target carries the record, the early returns included (no panel: no
    eligible names, no reduced build); under every other rule none does."""
    asof, _ = panel
    for rule in (None, "flatten", "hold"):
        assert all(THIN not in t.meta for t in _run(_spec(rule=rule), asof, account=None,
                                                    thin_rule=ABSENT))
    monkeypatch.setattr(cefmod, "NAV_PATH", cefmod.NAV_PATH.parent / "missing.parquet")
    out = _run(_spec(), asof)
    assert {t.reason for t in out} == {"cef: no price/NAV panel"}
    assert _thin_of(out) == {"eligible": [], "n": 0, "min_names": 6, "floor": 4,
                             "holds": False, "reduced": False, "stopped_by": None}


# ---------------------------------------------------------------------------
# 5. the callers that build the sleeve without deciding
# ---------------------------------------------------------------------------

def test_the_sleeve_still_builds_the_way_every_caller_builds_it(tmp_path, panel):
    """With the key set and no declaration: run.py's `spec_panel` line, ops.common's
    deployed_tickers and the registry all construct it (none decides). combine.load_sleeves
    refuses a budgeted sleeve with the key before building it (the runner owner's review
    2026-11-04, item 1: the rule was measured on the core's own account), naming the key."""
    from ops.common import deployed_tickers
    from quantt.session import combine as cmb
    te4 = _spec(m=None)
    # quantt/session/run.py::spec_panel, its one line (run.py is not imported: it sends orders)
    assert CEFDiscountSleeve(te4, 0.0).panel_paths() == (cefmod.PX_PATH, cefmod.NAV_PATH)
    assert registry.build_sleeve(te4, NAV_USD).instruments() == sorted(TICKERS)
    assert registry.build_sleeve(te4, NAV_USD, account="paper").instruments() == sorted(TICKERS)
    book = tmp_path / "book_inline.json"
    book.write_text(json.dumps({"sleeves": [{"name": "core", "spec": te4}]}))
    assert deployed_tickers(book) == {"core": sorted(TICKERS)}
    for name, uni in (("a", MUNI), ("b", TAX)):
        s = copy.deepcopy(te4)
        s["spec_id"], s["frozen"]["universe"] = f"synthetic-te4-{name}", list(uni)
        (tmp_path / f"{name}.json").write_text(json.dumps(s))
    combined = tmp_path / "book.json"
    combined.write_text(json.dumps({"sleeves": [
        {"name": "A", "spec_path": "a.json", "risk_budget": 0.5},
        {"name": "B", "spec_path": "b.json", "risk_budget": 0.5}]}))
    with pytest.raises(cmb.CombineError, match="trade_eligible"):
        cmb.load_sleeves(combined, tmp_path / "book_spec.json", tmp_path,
                         lambda spec: (lambda *a, **k: []),
                         panel_of=lambda spec: CEFDiscountSleeve(spec, 0.0).panel_paths())


# ---------------------------------------------------------------------------
# 6. the harness, on the real panel, every reduced fit date
# ---------------------------------------------------------------------------

# The pre-registration's approved floor (§1.1, derived there, not here). Used only while the live
# spec does not decide under te4; once it does, the spec's own floor is the only authority.
PREREG_FLOOR = 4


def _te4_real_spec(spec):
    """(a deep copy of `spec` that decides under te4, the floor it decides with), for the
    real-panel harness equality (group 6). The spec passed in is never changed.

    WHY (the quant review of f1d9f62, finding 3). The fixture first asserted the live spec did
    NOT set `below_min_names`, while its own comment said it would read the spec's floor "once
    the activation commit sets it". The activation commit would then have turned the two
    harness-equality tests into errors, on the one check that most needs to keep running at
    activation. Now:
      * the spec already decides under "trade_eligible": used AS WRITTEN, floor included. The
        floor must be a plain int (not a bool, a float or a string): the harness is built on it
        too (`build_targets(min_names=floor)`), and an `int()` cast here would let the harness
        and the sleeve run on different floors;
      * the key absent, "flatten" (a revert) or "hold": te4 is set IN THE COPY with the
        pre-registration's floor. The tests compare two implementations of one rule, so they
        stay meaningful whatever the live spec trades (the sleeve's te4 code exists either way).
    """
    sp = copy.deepcopy(spec)
    fr = sp["frozen"]
    if fr.get(KEY) == "trade_eligible":
        floor = fr.get("below_min_names_floor")
        if type(floor) is not int:
            raise ValueError(f"the live spec sets {KEY}='trade_eligible' with "
                             f"below_min_names_floor={floor!r}; the real-panel equality needs "
                             f"the int floor the sleeve decides with")
        return sp, floor
    fr[KEY] = "trade_eligible"
    fr["below_min_names_floor"] = PREREG_FLOOR
    return sp, PREREG_FLOOR


def test_the_real_panel_spec_uses_an_activated_spec_as_written():
    live = {"spec_id": "x", "frozen": {"min_names": 6, KEY: "trade_eligible",
                                       "below_min_names_floor": 5, "band_width": 0.048}}
    before = copy.deepcopy(live)
    sp, floor = _te4_real_spec(live)
    assert (sp, floor) == (before, 5)
    assert sp is not live and sp["frozen"] is not live["frozen"] and live == before


@pytest.mark.parametrize("rule", [ABSENT, "flatten", "hold"])
def test_the_real_panel_spec_sets_te4_in_a_copy_otherwise(rule):
    live = {"spec_id": "x", "frozen": {"min_names": 6, "band_width": 0.048}}
    if rule is not ABSENT:
        live["frozen"][KEY] = rule
    before = copy.deepcopy(live)
    sp, floor = _te4_real_spec(live)
    assert floor == 4
    assert sp["frozen"] == {**before["frozen"], KEY: "trade_eligible",
                            "below_min_names_floor": 4}
    assert live == before


@pytest.mark.parametrize("bad", [None, 4.5, True, "4"])
def test_the_real_panel_spec_refuses_te4_without_an_integer_floor(bad):
    live = {"spec_id": "x", "frozen": {"min_names": 6, KEY: "trade_eligible"}}
    if bad is not None:
        live["frozen"]["below_min_names_floor"] = bad
    with pytest.raises(ValueError, match="below_min_names_floor"):
        _te4_real_spec(live)


@pytest.fixture(scope="module")
def real():
    """The harness's te4 book on the real panel, and the reduced fit dates. Skips, saying why,
    when `data/cef/` lacks the panel (a fresh checkout has no `data/`)."""
    px, nav = cefmod.PX_PATH, cefmod.NAV_PATH
    if not (px.exists() and nav.exists()):
        pytest.skip(f"REAL-PANEL HARNESS EQUALITY NOT RUN: {px} or {nav} is absent (data/ is "
                    f"gitignored); the synthetic groups above still run")
    from scripts.cef import band_frontier as bf
    from scripts.cef import spec as S
    sp, floor = _te4_real_spec(S.spec())
    m = 1.0 if S.SIZING_MULTIPLIER is None else float(S.SIZING_MULTIPLIER)
    cap = float(S.MAX_GROSS_STRESS) / m
    T, _ = bf.build_targets(min_names=floor)
    thin_f = bf.thin_sessions(T.index, min_names=floor)
    thin_n = bf.thin_sessions(T.index)
    H = bf.band_gross_capped(T, S.BAND_WIDTH, cap, below_min_names="trade_eligible",
                             thin=thin_f, floor=floor)
    p = bf.build_panel()
    fit = T.index < pd.Timestamp(bf.HOLDOUT_START)
    reduced = T.index[(~thin_f.to_numpy()) & thin_n.to_numpy() & fit]
    assert len(reduced) > 0
    return dict(bf=bf, T=T, H=H, p=p, reduced=reduced, spec=sp, m=m, cap=cap, floor=floor,
                nav=float(sp["capital_usd"]), minw=float(S.MIN_ABS_WEIGHT))


@pytest.fixture
def memo_parquet(monkeypatch):
    """pandas' parquet reader, memoised for one test: the same frames, each call its own copy.
    The sleeve re-reads the panel on every decide; 1,500-odd decides read it once."""
    import functools
    read = pd.read_parquet

    @functools.lru_cache(maxsize=None)
    def cached(path, columns):
        return read(path, columns=list(columns) if columns else None)

    def memo(path, columns=None, **kw):
        if kw:
            raise TypeError(f"unexpected read_parquet kwargs {kw}")
        return cached(str(path), tuple(columns) if columns else None).copy()

    monkeypatch.setattr(pd, "read_parquet", memo)


def _decide(r, d, holdings, opening):
    sl = CEFDiscountSleeve(r["spec"], r["nav"], account="paper")
    ms = MarketState(asof=d, prices=pd.DataFrame(), holdings=holdings,
                     extras={"sleeve_nav": r["nav"], "opening_session": opening,
                             "thin_rule": NO_STOP})
    return sl.target_positions(d, ms)


def test_every_reduced_fit_date_builds_the_harness_target(real, memo_parquet):
    r, bf = real, real["bf"]
    z, adv, ret = r["p"]["z"], r["p"]["adv"], r["p"]["ret"]
    worst, checked = 0.0, 0
    for d in r["reduced"]:
        i = z.index.get_loc(d)
        row = bf._eligible(z.iloc[i], adv.iloc[i], bf.MIN_ADV)
        want, _ = _cap_gross(bf._target_row(row, ret, i), r["cap"])
        out = _decide(r, d, {}, True)
        rec = _thin_of(out)
        assert rec["reduced"] is True and rec["eligible"] == sorted(row.index), d
        for t in out:
            w = float(want.get(t.instrument, 0.0))
            if abs(w) < r["minw"]:
                assert t.side == FLAT, (d, t.instrument)
                continue
            assert t.qty is None, (d, t.instrument)
            diff = abs(float(t.weight) / r["m"] - w)
            worst = max(worst, diff)
            checked += 1
            assert diff <= 1e-12, (d.date(), t.instrument, float(t.weight) / r["m"], w)
    assert checked > 0 and worst <= 1e-12


def test_every_reduced_fit_date_bands_as_the_harness_does(real, memo_parquet):
    """One step at a time: the sleeve is handed the harness's own held book of the day before
    (in shares at the day's close, so held / (nav x m) is the harness's weight) and must emit the
    harness's next row: the band to the edge from that book, then the ceiling."""
    r = real
    H, px = r["H"], r["p"]["px"]
    pos = {d: k for k, d in enumerate(H.index)}
    checked = dust = 0
    for d in r["reduced"]:
        k = pos[d]
        if k == 0:
            continue
        prev, want = H.iloc[k - 1], H.iloc[k]
        close = px.loc[d]
        unpriced = [tk for tk in H.columns if prev[tk] != 0 and not math.isfinite(close[tk])]
        assert not unpriced, (d.date(), unpriced)            # every held name has the day's close
        holdings = {tk: float(prev[tk]) * r["nav"] * r["m"] / float(close[tk])
                    for tk in H.columns if prev[tk] != 0}
        out = _decide(r, d, holdings, False)
        assert _thin_of(out)["reduced"] is True, d
        for t in out:
            w = float(want[t.instrument])
            if t.side == FLAT:
                if abs(w) < r["minw"]:
                    dust += w != 0.0
                    continue
                got = 0.0
            elif t.qty is not None:
                got = float(t.signed_qty()) * float(close[t.instrument]) / (r["nav"] * r["m"])
            else:
                got = float(t.weight) / r["m"]
            checked += 1
            assert abs(got - w) <= 1e-12, (d.date(), t.instrument, got, w)
    assert checked > 0
