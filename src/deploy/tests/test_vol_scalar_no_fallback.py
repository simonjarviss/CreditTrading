"""The z book never sizes on an invented number: a vol with no ratio raises, and a 0/0 book holds and says so
(team lead, 2026-11-19).

Until then `target_positions` sized the book at scalar 1.0 when the trailing realised vol was
zero or NaN: a silent fallback (CLAUDE.md, code rules) found by the review of
release-20261116-1. It never fired on a recorded session as far as anyone measured; this pins
that it cannot fire quietly.

  1. a zero, NaN or negative vol raises, naming the date and saying nothing was decided
     (each FAILS on 48ba372's sleeve, which returned a full set of targets at scalar 1.0);
  2. on a normal day the targets are what the old expression gives, reasons included: the
     new line is the old one with its fallback removed, so a positive vol changes nothing.

  3. a full session on which every eligible z is equal (the weights are 0/0) HOLDS, explicitly:
     each held name keeps exactly its shares as a qty target with the reason, an unheld name
     stays unopened, and a flat book opens nothing. On 48ba372 the held book also held, but
     under reasons that read like an ordinary band hold, and a flat book on its opening session
     was handed short targets with NaN weights (measured on the real panel's 2025-04-07,
     where every eligible z sat at the -4 clip). Team lead: "Hold, but say so".

The panel is test_combine_noop.py's generated 13-fund panel: it tests the code, not a market.
"""
import numpy as np
import pandas as pd
import pytest

from quantt.session.tests.test_combine_noop import ASOF, SYN_SPEC, _synthetic_panel
from src.deploy.registry import build_sleeve
from src.deploy.sleeve import MarketState
from src.deploy.sleeves import cef_discount
from src.deploy.tests.test_group_cap import _fingerprint

NAV = SYN_SPEC["capital_usd"]


def _targets():
    sl = build_sleeve(SYN_SPEC, NAV)
    ms = MarketState(asof=pd.Timestamp(ASOF), prices=pd.DataFrame(), holdings={},
                     extras={"sleeve_nav": NAV, "opening_session": True})
    return sl.target_positions(pd.Timestamp(ASOF), ms)


@pytest.mark.parametrize("bad", [0.0, float("nan"), -0.01, float("inf")])
def test_a_vol_with_no_ratio_to_take_raises_instead_of_sizing_at_one(tmp_path, monkeypatch, bad):
    _synthetic_panel(tmp_path, monkeypatch)
    monkeypatch.setattr(cef_discount, "_book_vol", lambda ret, w: bad)
    with pytest.raises(ValueError, match="trailing realised vol .* Nothing decided"):
        _targets()


def test_a_positive_vol_gives_exactly_the_old_expressions_targets(tmp_path, monkeypatch):
    _synthetic_panel(tmp_path, monkeypatch)
    seen = []
    real = cef_discount._book_vol

    def spy(ret, w):
        rv = real(ret, w)
        seen.append(float(rv))
        return rv
    monkeypatch.setattr(cef_discount, "_book_vol", spy)
    got = _targets()
    assert seen and all(np.isfinite(v) and v > 0 for v in seen), "the panel must give a real vol"
    assert any(t.weight for t in got), "and a real book"
    # the old expression on the same vol: `clip(vol_target / rv, 0.2, 2.5) if rv > 0 else 1.0`
    vt = float(SYN_SPEC["frozen"]["vol_target_annual"])
    old = float(np.clip(vt / seen[0], 0.2, 2.5)) if seen[0] > 0 else 1.0
    assert f"volscal={old:.2f}" in "".join(t.reason or "" for t in got)
    assert _fingerprint(got) == _fingerprint(_targets()), "and it is deterministic"


def _crash_last_close(px_path):
    """Every fund's last close cut to 30% of itself: every discount is then far below its own
    history, every z sits at the clip, and z - mean(z) is zero for every name."""
    p = pd.read_parquet(px_path)
    last = pd.to_datetime(p["date"]) == pd.Timestamp(ASOF)
    assert last.any()
    p.loc[last, "close"] = p.loc[last, "close"].astype(float) * 0.30
    p.to_parquet(px_path, index=False)


def _targets_with(held, opening):
    sl = build_sleeve(SYN_SPEC, NAV)
    ms = MarketState(asof=pd.Timestamp(ASOF), prices=pd.DataFrame(), holdings=dict(held),
                     extras={"sleeve_nav": NAV, "opening_session": opening})
    return sl.target_positions(pd.Timestamp(ASOF), ms)


def test_every_z_equal_holds_each_position_in_shares_and_says_why(tmp_path, monkeypatch):
    px, _, _ = _synthetic_panel(tmp_path, monkeypatch)
    names = [t.instrument for t in _targets() if t.weight][:3]
    _crash_last_close(px)
    held = {names[0]: 1500.0, names[1]: -900.0, names[2]: 40.0}
    got = _targets_with(held, opening=False)
    by = {t.instrument: t for t in got}
    assert {k: by[k].qty for k in held} == held, "exactly the shares held, as qty targets"
    assert all("every eligible z is equal" in (t.reason or "") for t in got)
    assert all(by[k].reason.startswith("cef: held, book holds") for k in held)
    others = [t for t in got if t.instrument not in held]
    assert others and all(t.side == "FLAT" or str(t.side).endswith("FLAT") for t in others)
    assert not any(t.weight for t in got), "no weight target: nothing can be resized or opened"


def test_every_z_equal_on_a_flat_book_opens_nothing(tmp_path, monkeypatch):
    px, _, _ = _synthetic_panel(tmp_path, monkeypatch)
    _crash_last_close(px)
    got = _targets_with({}, opening=True)
    assert got and not any(t.weight or getattr(t, "qty", None) for t in got)
    assert not any(t.weight != t.weight for t in got if t.weight is not None), "and no NaN weight"
    assert all("every eligible z is equal" in (t.reason or "") for t in got)
