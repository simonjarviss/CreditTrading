"""The four optional C4 keys on the `cef_discount` sleeve, on synthetic panels.

WHY (results/cef/C4_DEPLOY_PLAN_2026-10-27.md §1 row 1). Trial C4 ran this
sleeve's z-score on other funds through `band_frontier.build_targets(universe=,
source=, mask=)`. The plan reuses the sleeve with a second spec instead of
copying the signal, so the sleeve must be able to do the three things the trial
did and it could not: read another panel (`panel_source`), take a fund-day's
discount away on a repeated NAV (M1, `nav_repeat_mask`) or a zero-volume day
(M2, `zero_volume_mask`; PREREG_C4_FAMILIES §4.3), and HOLD below `min_names`
where it flattened (`below_min_names`).

WHAT EACH TEST WOULD HAVE CAUGHT:

  1. THE NO-OP, SYNTHETICALLY. Each key set to its default is byte-identical
     to the key absent, on a flat book, a held book and a book below
     `min_names` -- so a default that drifted (a mask on by default, "hold" by
     default) fails here even where no real panel is present. The real-panel
     proof against the code BEFORE the keys is
     `quantt/session/tests/test_c4_keys_noop.py`.
  2. THE TRIAL'S MASKS, EXACTLY. On a panel with repeats and zero-volume days,
     on the decision date and in the z-window history, the sleeve's masks are
     cell for cell `c4_families.declared_mask`, and its weights are
     `build_targets(source=, mask=)`'s for the same day -- with the band off,
     because `build_targets` returns the PRE-band target and the trial bands it
     afterwards, and the dust filter off (`min_abs_weight`, a declared
     divergence, PREREG_C4 §3 item 5). The sleeve's copy of `repeat_mask`
     equals the trial's on a messy frame.
  3. EACH KEY DOES ITS ONE THING. M1 takes a repeated NAV's day out and says
     so; a past repeat moves the name's z only through its history; M2 takes a
     zero-volume day out; "hold" keeps every position where "flatten" closes
     the book, and decide then sends nothing; `panel_source` reads the named
     files -- prices, NAV and the group axis -- and refuses a missing one.
  4. REFUSAL. Every malformed value raises in the registry, naming the key and
     the value, and the sleeve refuses it too when built without the registry.

Synthetic data throughout: the conclusions are about this code, never about a
market (CLAUDE.md, data rules).
"""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

from src.deploy import registry
from src.deploy.sleeve import FLAT, LONG, SHORT, MarketState
from src.deploy.sleeves import cef_discount as cefmod
from src.deploy.sleeves.cef_discount import CEFDiscountSleeve
from src.deploy.tests.test_group_cap import (
    GRP,
    MUNI,
    NAV_USD,
    TAX,
    TICKERS,
    _fingerprint,
    _spec,
    _write_panel,
)
from src.deploy.tests.test_nav_hold import _orders

DEFAULTS = {"nav_repeat_mask": False, "zero_volume_mask": False, "below_min_names": "flatten"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run(spec, asof, holdings=None, extras=None):
    sl = CEFDiscountSleeve(spec, NAV_USD)
    ms = MarketState(asof=pd.Timestamp(asof), prices=pd.DataFrame(),
                     holdings=dict(holdings or {}),
                     extras={"sleeve_nav": NAV_USD, **(extras or {})})
    return sl.target_positions(pd.Timestamp(asof), ms)


def _by(targets):
    return {t.instrument: t for t in targets}


def _w(targets):
    return {t.instrument: float(t.weight) for t in targets
            if t.side != FLAT and t.weight is not None}


def _with(spec, **keys):
    s = json.loads(json.dumps(spec))
    s["frozen"].update(keys)
    return s


def _frames():
    return pd.read_parquet(cefmod.PX_PATH), pd.read_parquet(cefmod.NAV_PATH)


def _rewrite(P, N):
    P.to_parquet(cefmod.PX_PATH)
    N.to_parquet(cefmod.NAV_PATH)


def _set(df, tk, day, col, value):
    hit = (df["ticker"] == tk) & (pd.to_datetime(df["date"]) == pd.Timestamp(day))
    assert hit.sum() == 1, f"no single {tk} row on {day}"
    df.loc[hit, col] = value


def _prev_nav(N, tk, day):
    n = N[(N["ticker"] == tk) & (pd.to_datetime(N["date"]) < pd.Timestamp(day))]
    return float(n.sort_values("date")["nav"].iloc[-1])


def _dates():
    return sorted(pd.to_datetime(pd.read_parquet(cefmod.PX_PATH, columns=["date"])["date"]).unique())


# ---------------------------------------------------------------------------
# 1. the no-op, synthetically: each key at its default == absent
# ---------------------------------------------------------------------------

def _below_min(P):
    """Seven of the twelve names illiquid for the last 70 sessions: ADV
    1e5 x ~$10 < $3m, so five are eligible, under `min_names` 6."""
    thin = TAX[1:] + MUNI[4:]
    last70 = sorted(P["date"].unique())[-70:]
    P.loc[P["ticker"].isin(thin) & P["date"].isin(last70), "volume"] = 100_000.0
    return P


@pytest.mark.parametrize("case", ["flat", "held", "below_min_names"])
def test_defaults_are_byte_identical_to_absent(tmp_path, monkeypatch, case):
    asof, _ = _write_panel(tmp_path, monkeypatch)
    if case == "below_min_names":
        P, N = _frames()
        _rewrite(_below_min(P), N)
    holdings = {} if case == "flat" else {"MUN1": 1000.0, "TAX1": -800.0, "TAX4": -500.0,
                                          "MUN6": 300.0}
    monkeypatch.setattr(cefmod, "REPO", tmp_path)
    explicit = _with(_spec(), panel_source={"prices": "px.parquet", "nav": "nav.parquet"},
                     **DEFAULTS)
    a = _fingerprint(_run(_spec(), asof, holdings))
    e = _fingerprint(_run(explicit, asof, holdings))
    assert a, "emitted nothing; the comparison would be vacuous"
    assert e == a
    if case == "below_min_names":
        assert "only 5 eligible names" in a        # the flatten branch was reached
    else:
        assert "cef discount z=" in a


# ---------------------------------------------------------------------------
# 2. the trial's masks, exactly
# ---------------------------------------------------------------------------

def test_nav_repeat_is_the_trials_repeat_mask():
    """The sleeve's `_nav_repeat` is `c4_feasibility.repeat_mask` on a frame the
    trial could have read: unsorted, several tickers, NaN NAVs, a fund's first
    row, a repeat across a gap in the dates."""
    from scripts.cef.c4_feasibility import repeat_mask
    rows = [("B", "2026-01-05", 10.0), ("A", "2026-01-06", 5.0), ("A", "2026-01-02", 5.0),
            ("B", "2026-01-02", 10.0), ("A", "2026-01-05", 5.0), ("B", "2026-01-06", np.nan),
            ("C", "2026-01-02", 7.0), ("B", "2026-01-07", 10.0), ("C", "2026-01-09", 7.0),
            ("A", "2026-01-07", 5.01), ("C", "2026-01-05", 7.5)]
    nav = pd.DataFrame(rows, columns=["ticker", "date", "nav"])
    nav["date"] = pd.to_datetime(nav["date"])
    got, want = cefmod._nav_repeat(nav), repeat_mask(nav)
    pd.testing.assert_series_equal(got, want)
    assert got.sum() == 3 and not got.isna().any()       # A 01-05, A 01-06, B 01-05


def _trial_panel(tmp_path, monkeypatch):
    """The synthetic panel with M1 and M2 cells planted where they matter:
    on the decision date (the name leaves the day) and inside the z-window
    (the name's history shrinks), and a NAV row with no price (still the
    'previous row' of the next one, as in the trial)."""
    asof, _ = _write_panel(tmp_path, monkeypatch)
    P, N = _frames()
    days = _dates()
    _set(N, "TAX3", asof, "nav", _prev_nav(N, "TAX3", asof))                  # M1 today
    for d in days[-60:-20:3]:                                                 # M1 history
        _set(N, "MUN2", d, "nav", _prev_nav(N, "MUN2", d))
    _set(P, "MUN4", asof, "volume", 0.0)                                       # M2 today
    for d in days[-90:-30:7]:                                                  # M2 history
        _set(P, "TAX5", d, "volume", 0.0)
    gap = days[-15]                                                            # NAV, no price
    P = P[~((P["ticker"] == "MUN3") & (pd.to_datetime(P["date"]) == gap))]
    _set(N, "MUN3", days[-14], "nav", float(N.loc[(N["ticker"] == "MUN3") &
                                                  (pd.to_datetime(N["date"]) == gap), "nav"].iloc[0]))
    _rewrite(P.reset_index(drop=True), N)
    return asof


def _trial_spec(**keys):
    """The sleeve with every signal parameter the trial read from the frozen
    spec (scripts/cef/spec.py); the band off and the calendar at one day, so the
    emitted weights are the pre-band target on the trial's signal date (what
    `build_targets` returns); and the dust filter off (`min_abs_weight`, PREREG_C4
    §3 item 5), so the two can be compared weight for weight."""
    from scripts.cef import spec as sp
    s = _spec(band=False)
    s["frozen"].update(z_window=sp.Z_WINDOW, min_names=sp.MIN_NAMES,
                       vol_target_annual=sp.VOL_TARGET, min_adv_usd=sp.MIN_ADV_USD,
                       min_abs_weight=1e-12, **keys)
    return s


def test_masks_and_weights_are_the_trials(tmp_path, monkeypatch):
    from scripts.cef import band_frontier as bf
    from scripts.cef import c4_families as c4
    asof = _trial_panel(tmp_path, monkeypatch)
    src = (cefmod.PX_PATH, cefmod.NAV_PATH)
    monkeypatch.setattr(c4, "FAM_SRC", src)
    trial_mask = c4.declared_mask(TICKERS, "M1M2")

    on = _trial_spec(nav_repeat_mask=True, zero_volume_mask=True)
    sl = CEFDiscountSleeve(on, NAV_USD)
    px, _nav, vol, navrows = sl._read_panel(asof)
    masks = sl._discount_masks(navrows, px, vol, asof)
    mine = masks["nav_repeat_mask"] | masks["zero_volume_mask"]
    assert len(sl._panel(asof)) == 3            # `_panel`'s contract is unchanged
    pd.testing.assert_frame_equal(mine, trial_mask.loc[:pd.Timestamp(asof)].reindex_like(mine),
                                  check_freq=False)
    # Not vacuous: both masks hit on the decision date and in the history.
    ts = pd.Timestamp(asof)
    assert masks["nav_repeat_mask"].loc[ts, "TAX3"] and masks["zero_volume_mask"].loc[ts, "MUN4"]
    assert masks["nav_repeat_mask"]["MUN2"].sum() >= 10 and masks["zero_volume_mask"]["TAX5"].sum() >= 8

    T, _ = bf.build_targets(universe=list(TICKERS), source=src, mask=trial_mask)
    want = T.loc[ts]
    got = _w(_run(on, asof))
    assert set(got) == set(want[want != 0].index)
    assert max(abs(got[t] - want[t]) for t in got) < 1e-12
    # ...and the unmasked sleeve is NOT the trial's book on this panel.
    off = _w(_run(_trial_spec(), asof))
    assert set(off) != set(got) or max(abs(off[t] - got[t]) for t in got) > 1e-6


# ---------------------------------------------------------------------------
# 3. each key does its one thing
# ---------------------------------------------------------------------------

def test_nav_repeat_mask_takes_a_repeated_nav_out_of_the_day(tmp_path, monkeypatch):
    asof, _ = _write_panel(tmp_path, monkeypatch)
    P, N = _frames()
    _set(N, "TAX3", asof, "nav", _prev_nav(N, "TAX3", asof))
    _rewrite(P, N)
    spec = _spec(band=False)
    off = _by(_run(spec, asof))
    on = _by(_run(_with(spec, nav_repeat_mask=True), asof))
    assert off["TAX3"].side != FLAT and off["TAX3"].weight      # unmasked: traded on the repeat
    assert on["TAX3"].side == FLAT
    assert on["TAX3"].reason == "cef: no discount today (nav_repeat_mask)"
    w = _w(on.values())
    assert len(w) == len(TICKERS) - 1 and abs(sum(w.values())) < 1e-12   # re-formed, neutral


def test_nav_repeat_mask_shrinks_the_history_not_the_day(tmp_path, monkeypatch):
    """Repeats in the z-window only (none today): the name stays eligible, and
    its weight moves because its mean and sd are taken over fewer days."""
    asof, _ = _write_panel(tmp_path, monkeypatch)
    P, N = _frames()
    for d in _dates()[-60:-20:3]:
        _set(N, "MUN2", d, "nav", _prev_nav(N, "MUN2", d))
    _rewrite(P, N)
    spec = _spec(band=False)
    off, on = _w(_run(spec, asof)), _w(_run(_with(spec, nav_repeat_mask=True), asof))
    assert "MUN2" in on and set(on) == set(off)
    assert abs(on["MUN2"] - off["MUN2"]) > 1e-6


def test_zero_volume_mask_takes_a_zero_volume_day_out(tmp_path, monkeypatch):
    asof, _ = _write_panel(tmp_path, monkeypatch)
    P, N = _frames()
    _set(P, "MUN4", asof, "volume", 0.0)
    _rewrite(P, N)
    spec = _spec(band=False)
    off = _by(_run(spec, asof))
    on = _by(_run(_with(spec, zero_volume_mask=True), asof))
    assert off["MUN4"].side != FLAT and off["MUN4"].weight      # ADV is through t-1: still liquid
    assert on["MUN4"].side == FLAT
    assert on["MUN4"].reason == "cef: no discount today (zero_volume_mask)"
    assert len(_w(on.values())) == len(TICKERS) - 1


HELD = {"MUN1": 1000.0, "TAX1": -800.0, "TAX4": -500.0, "MUN6": 300.0}


def test_hold_keeps_the_positions_where_flatten_closes_them(tmp_path, monkeypatch):
    asof, close = _write_panel(tmp_path, monkeypatch)
    P, N = _frames()
    _rewrite(_below_min(P), N)
    spec = _spec()                                             # band on, as the book runs
    flat = _by(_run(spec, asof, HELD))
    hold = _by(_run(_with(spec, below_min_names="hold"), asof, HELD))
    assert all(t.side == FLAT and t.reason == "cef: only 5 eligible names" for t in flat.values())
    for tk in TICKERS:
        t = hold[tk]
        if tk in HELD:
            assert (t.qty, t.side) == (HELD[tk], LONG if HELD[tk] > 0 else SHORT)
            assert t.reason == ("cef: held, book holds: only 5 eligible names, under min_names 6 "
                                "(below_min_names=hold)")
        else:
            assert t.side == FLAT and t.reason.startswith("cef: not opened, book holds")
    # What decide does with each: flatten closes all four, hold sends nothing.
    assert _orders(list(flat.values()), HELD, close, TICKERS) == {k: -int(v) for k, v in HELD.items()}
    assert _orders(list(hold.values()), HELD, close, TICKERS) == {}


def test_hold_names_the_stale_nav_holds_it_subsumes(tmp_path, monkeypatch):
    asof, _ = _write_panel(tmp_path, monkeypatch)
    P, N = _frames()
    _rewrite(_below_min(P), N)
    nav_hold = {"nav_hold": {"asof": asof, "names": {"MUN1": "no CEFConnect row"}}}
    hold = _by(_run(_with(_spec(), below_min_names="hold"), asof, HELD, nav_hold))
    assert hold["MUN1"].qty == HELD["MUN1"]
    assert hold["TAX1"].reason.endswith("NAV unverified for ['MUN1']")
    assert "only 4 eligible names" in hold["TAX1"].reason


def test_hold_does_nothing_at_or_above_min_names(tmp_path, monkeypatch):
    asof, _ = _write_panel(tmp_path, monkeypatch)
    a = _fingerprint(_run(_spec(), asof, HELD))
    h = _fingerprint(_run(_with(_spec(), below_min_names="hold"), asof, HELD))
    assert h == a and "cef discount z=" in a


def _second_panel(tmp_path, monkeypatch):
    """Panel A at the module's default paths, and a different panel B at
    <fake repo>/data/cef_c4/: B is A with each ticker's history moved to the
    next ticker and MUN1 relabelled `multi`, so every name's discount differs
    and the group axis differs on one name."""
    (tmp_path / "b_src").mkdir()
    asof, _ = _write_panel(tmp_path / "b_src", monkeypatch)
    P, N = _frames()
    nxt = dict(zip(TICKERS, TICKERS[1:] + TICKERS[:1]))
    P["ticker"], N["ticker"] = P["ticker"].map(nxt), N["ticker"].map(nxt)
    P["grp"] = P["ticker"].map({**GRP, "MUN1": "multi"})
    repo = tmp_path / "repo"
    (repo / "data" / "cef_c4").mkdir(parents=True)
    P.to_parquet(repo / "data/cef_c4/cef_prices.parquet")
    N.to_parquet(repo / "data/cef_c4/cef_nav.parquet")
    (tmp_path / "a").mkdir()
    _write_panel(tmp_path / "a", monkeypatch)                  # module paths -> A
    monkeypatch.setattr(cefmod, "REPO", repo)
    return asof, repo


SOURCE = {"prices": "data/cef_c4/cef_prices.parquet", "nav": "data/cef_c4/cef_nav.parquet"}


def test_panel_source_reads_the_named_files(tmp_path, monkeypatch):
    asof, repo = _second_panel(tmp_path, monkeypatch)
    spec = _spec()
    named = _with(spec, panel_source=SOURCE)
    sl = CEFDiscountSleeve(named, NAV_USD)
    assert sl.panel_paths() == (repo / SOURCE["prices"], repo / SOURCE["nav"])
    assert CEFDiscountSleeve(spec, NAV_USD).panel_paths() == (cefmod.PX_PATH, cefmod.NAV_PATH)
    on_a = _fingerprint(_run(spec, asof, HELD))
    on_b = _fingerprint(_run(named, asof, HELD))
    # The same sleeve with its module paths pointed at B decides exactly that book.
    monkeypatch.setattr(cefmod, "PX_PATH", repo / SOURCE["prices"])
    monkeypatch.setattr(cefmod, "NAV_PATH", repo / SOURCE["nav"])
    monkeypatch.setattr(cefmod, "GRP_PATH", repo / SOURCE["prices"])
    assert _fingerprint(_run(spec, asof, HELD)) == on_b
    assert on_b != on_a and "cef discount z=" in on_b


def test_panel_source_reads_the_group_axis_from_its_own_prices(tmp_path, monkeypatch):
    _second_panel(tmp_path, monkeypatch)
    assert CEFDiscountSleeve(_spec(), NAV_USD)._groups()["MUN1"] == "muni"           # A
    assert CEFDiscountSleeve(_with(_spec(), panel_source=SOURCE), NAV_USD)._groups()["MUN1"] == "taxable"


def test_panel_source_refuses_a_missing_or_empty_panel(tmp_path, monkeypatch):
    asof, repo = _second_panel(tmp_path, monkeypatch)
    gone = _with(_spec(), panel_source={**SOURCE, "nav": "data/cef_c4/nope.parquet"})
    with pytest.raises(FileNotFoundError, match="nope.parquet"):
        _run(gone, asof)
    with pytest.raises(ValueError, match="holds no paired price and NAV"):
        _run(_with(_spec(), panel_source=SOURCE), "2000-01-03")
    # Absent, a missing panel is still today's FLAT book, not a raise.
    monkeypatch.setattr(cefmod, "NAV_PATH", tmp_path / "missing.parquet")
    assert {t.reason for t in _run(_spec(), asof)} == {"cef: no price/NAV panel"}


# ---------------------------------------------------------------------------
# 4. refusal
# ---------------------------------------------------------------------------

def _live_like():
    spec = _spec()
    spec.update(spec_id="t.v1", status="paper")
    return spec


GOOD = [("panel_source", SOURCE), ("panel_source", {"nav": "x/n.parquet", "prices": "x/p.parquet"}),
        ("nav_repeat_mask", True), ("nav_repeat_mask", False),
        ("zero_volume_mask", True), ("zero_volume_mask", False),
        ("below_min_names", "flatten"), ("below_min_names", "hold")]

BAD = [("panel_source", None), ("panel_source", "data/cef_c4"), ("panel_source", ["a.parquet"]),
       ("panel_source", {"prices": "p.parquet"}),
       ("panel_source", {**SOURCE, "grp": "g.parquet"}),
       ("panel_source", {**SOURCE, "prices": "/abs/cef_prices.parquet"}),
       ("panel_source", {**SOURCE, "prices": "../outside.parquet"}),
       ("panel_source", {**SOURCE, "prices": "data\\cef\\p.parquet"}),
       ("panel_source", {**SOURCE, "prices": "data/cef_c4/cef_prices.csv"}),
       ("panel_source", {**SOURCE, "prices": " data/cef_c4/cef_prices.parquet"}),
       ("panel_source", {**SOURCE, "prices": ""}),
       ("panel_source", {**SOURCE, "prices": 7}),
       ("panel_source", {"prices": SOURCE["nav"], "nav": SOURCE["nav"]}),
       ("nav_repeat_mask", None), ("nav_repeat_mask", 1), ("nav_repeat_mask", 0),
       ("nav_repeat_mask", "true"), ("nav_repeat_mask", np.bool_(True)),
       ("zero_volume_mask", None), ("zero_volume_mask", 1), ("zero_volume_mask", "false"),
       ("below_min_names", None), ("below_min_names", "Hold"), ("below_min_names", "drop"),
       ("below_min_names", "flat"), ("below_min_names", True), ("below_min_names", "")]


def test_absent_validates():
    registry.validate_spec(_live_like())
    live = json.loads((cefmod.REPO / "ops/specs/cef_discount.frozen.json").read_text())
    assert not {"panel_source", "nav_repeat_mask", "zero_volume_mask",
                "below_min_names"} & set(live["frozen"])
    registry.validate_spec(live)


@pytest.mark.parametrize("key,value", GOOD)
def test_declared_values_validate(key, value):
    registry.validate_spec(_with(_live_like(), **{key: value}))


@pytest.mark.parametrize("key,value", BAD)
def test_any_other_value_raises_naming_it(key, value, tmp_path, monkeypatch):
    spec = _with(_live_like(), **{key: value})
    with pytest.raises(ValueError, match=key) as e:
        registry.validate_spec(spec)
    assert key in str(e.value)
    # The sleeve refuses it too when built without the registry.
    asof, _ = _write_panel(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match=key):
        _run(spec, asof)


# ---------------------------------------------------------------------------
# 5. review of 11790b5: a data shortfall never flattens; near-miss keys refuse
# ---------------------------------------------------------------------------

def _short(P, N, n=150):
    """The last `n` sessions only: under z_window + 20 = 272, too short to score."""
    keep = sorted(pd.to_datetime(P["date"]).unique())[-n:]
    return (P[pd.to_datetime(P["date"]).isin(keep)].reset_index(drop=True),
            N[pd.to_datetime(N["date"]).isin(keep)].reset_index(drop=True))


HELD2 = {"MUN1": 500.0, "TAX2": -800.0}       # the reviewer's shape: one long, one short


@pytest.mark.parametrize("keys", [{"panel_source": SOURCE}, {"below_min_names": "hold"},
                                  {"panel_source": SOURCE, "below_min_names": "hold"}])
def test_a_short_panel_raises_instead_of_flattening(tmp_path, monkeypatch, keys):
    """With `panel_source` or `hold`, a panel shorter than z_window + 20 raises,
    naming the shortfall, where 11790b5 emitted the held book FLAT "insufficient
    history" (the review reproduced it on the 13's last 150 sessions)."""
    asof, repo = _second_panel(tmp_path, monkeypatch)
    for paths in ((repo / SOURCE["prices"], repo / SOURCE["nav"]), (cefmod.PX_PATH, cefmod.NAV_PATH)):
        P, N = _short(pd.read_parquet(paths[0]), pd.read_parquet(paths[1]))
        P.to_parquet(paths[0])
        N.to_parquet(paths[1])
    with pytest.raises(ValueError, match=r"holds 150 paired sessions .* 252 \+ 20 = 272, 122 short"):
        _run(_with(_spec(), **keys), asof, HELD2)


def test_a_short_panel_with_the_keys_absent_is_still_flat(tmp_path, monkeypatch):
    asof, _ = _write_panel(tmp_path, monkeypatch)
    _rewrite(*_short(*_frames()))
    out = _run(_spec(), asof, HELD2)
    assert {(t.side, t.reason) for t in out} == {(FLAT, "cef: insufficient history")}


def test_a_missing_panel_with_hold_raises_and_absent_is_still_flat(tmp_path, monkeypatch):
    asof, _ = _write_panel(tmp_path, monkeypatch)
    monkeypatch.setattr(cefmod, "NAV_PATH", tmp_path / "missing.parquet")
    with pytest.raises(ValueError, match="refusing to flatten"):
        _run(_with(_spec(), below_min_names="hold"), asof, HELD2)
    assert {t.reason for t in _run(_spec(), asof, HELD2)} == {"cef: no price/NAV panel"}


NEAR_MISSES = [("nav_repeat_masks", "nav_repeat_mask"), ("below_min_name", "below_min_names"),
               ("_nav_repeat_mask", "nav_repeat_mask"), ("navrepeatmask", "nav_repeat_mask"),
               ("Zero-Volume-Mask", "zero_volume_mask"), ("zero_volume_mak", "zero_volume_mask"),
               ("panel_sources", "panel_source"), ("pannel_source", "panel_source"),
               ("_nav_repeat_masks_note", "nav_repeat_mask"), ("below_min_names_note", "below_min_names")]


@pytest.mark.parametrize("key,meant", NEAR_MISSES)
def test_a_near_miss_of_a_new_key_raises_naming_both(key, meant, tmp_path, monkeypatch):
    """11790b5 validated `nav_repeat_masks: true` and `below_min_name: "hold"`,
    and the sleeve then ran each key's DEFAULT -- no mask, flatten -- while the
    spec read as asking for the opposite."""
    spec = _with(_live_like(), **{key: True if "mask" in meant else "hold"})
    with pytest.raises(ValueError, match="looks like a misspelling") as e:
        registry.validate_spec(spec)
    assert repr(key) in str(e.value) and repr(meant) in str(e.value)
    asof, _ = _write_panel(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="looks like a misspelling"):
        _run(spec, asof)


def test_the_live_spec_validates_and_none_of_its_keys_is_a_near_miss():
    """The near-miss rule must not reject what the live spec, or any key the
    sleeve already reads, carries: every frozen key of
    `ops/specs/cef_discount.frozen.json`, the optional v7 keys and the `_note`
    siblings of the four new ones."""
    live = json.loads((cefmod.REPO / "ops/specs/cef_discount.frozen.json").read_text())
    registry.validate_spec(live)
    others = ["group_cap", "max_gross_stress", "band_width", "warmup_days", "min_names",
              *registry.CEF_C4_NOTES]
    assert [k for k in [*live["frozen"], *others] if registry.cef_c4_near_miss(k)] == []
    # C4's four notes validate beside the live-like spec. The fifth, the te4 floor's
    # `_below_min_names_floor_note`, is no near-miss either (asserted above), but since the
    # review of 4e1ab0b it is refused beside a rule that does not read the floor, as the floor
    # is (src/deploy/tests/test_below_min_names_floor.py), so it is left out here.
    floor_note = f"_{registry.CEF_FLOOR_KEY}_note"
    noted = _with(_live_like(), **{n: "a note" for n in registry.CEF_C4_NOTES
                                   if n != floor_note})
    registry.validate_spec(noted)
    with pytest.raises(ValueError, match=floor_note):
        registry.validate_spec(_with(_live_like(), **{floor_note: "a note"}))
