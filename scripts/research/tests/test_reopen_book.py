"""Tests for `scripts/research/reopen_book/` (the re-open of NAV tenders and E1).

WHY THESE. The re-open's verdict rests on mechanical steps: the common window
(a calendar mismatch must be reported, a 2023 date must raise), the active-spell
length that sets the bootstrap block, the non-overlapping sums behind the
21-session ρ, the combination arithmetic (P&L, turnover and gross add; nothing
nets), the ceiling's rescaling bound, and the two views `measure()` builds.
Each is tested on synthetic frames, so these are statements about the code,
never about the market.

The tests marked "review, 2026-10-28" pin defects an independent review found
in the first version (b43bf35). Each fails against that version:
- E1's harness turnover was the RAW H's, beside P&L on the sized and capped H
  (`check_same_h` would have refused it);
- the paper view swapped only the book's return convention, not the sleeve's
  (`measure()` must use `pnl_price` there);
- the capped row charged no rescaling trades (`capped` must bound them).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.research import inference as I
from scripts.research.reopen_book import extract_trial_series as X
from scripts.research.reopen_book import reopen_book as RB


def _frame(idx, pnl, held, turn=None, decided=None):
    return pd.DataFrame({"pnl": pnl, "turn": np.zeros(len(idx)) if turn is None else turn,
                         "held_gross": held, "decided_gross": held if decided is None else decided}, index=idx)


def test_common_window_starts_when_both_exist_and_reports_calendar_gaps():
    idx = pd.bdate_range("2012-01-02", periods=40)
    book = _frame(idx, np.arange(40.0), np.r_[np.zeros(10), np.ones(30)])        # holds from day 10
    s_idx = idx[5:].insert(3, pd.Timestamp("2012-01-21"))                        # a Saturday the book lacks, after day 10
    sleeve = _frame(s_idx.sort_values(), np.ones(len(s_idx)), np.ones(len(s_idx)))
    w, info = RB.common_window(sleeve, book)
    assert w[0] == idx[10] and w[-1] == idx[-1]
    assert info["sleeve_sessions_not_in_book"] == 1 and info["sleeve_pnl_on_those_sessions"] == 1.0
    late = _frame(pd.DatetimeIndex(["2022-12-30", "2023-01-03"]), [0.0, 0.0], [1.0, 1.0])
    with pytest.raises(AssertionError):
        RB.common_window(late, book)


def test_spells_and_block_sums():
    a = pd.Series([0, 1, 1, 0, 1, 1, 1, 0, 0, 1], dtype=bool)
    assert RB.spells(a).tolist() == [2, 3, 1]
    assert RB.spells(pd.Series([False] * 4)).size == 0
    x = pd.Series(np.arange(1.0, 23.0), index=pd.bdate_range("2020-01-01", periods=22))
    s = RB.block_sums(x, 5)                                   # 4 full blocks, 2 sessions dropped
    assert s.tolist() == [15.0, 40.0, 65.0, 90.0] and s.index[0] == x.index[4]
    with pytest.raises(ValueError):
        RB.block_sums(x, 6)                                   # only 3 blocks


def test_combine_adds_pnl_turnover_and_gross_and_refuses_misaligned_frames():
    idx = pd.bdate_range("2015-01-01", periods=5)
    b = _frame(idx, np.full(5, 0.001), np.full(5, 1.2), np.full(5, 0.05))
    s = _frame(idx, np.full(5, -0.002), np.full(5, 0.6), np.full(5, 0.01))
    c = RB.combine(b, s, 1.0)
    assert np.allclose(c["pnl"], -0.001) and np.allclose(c["turn"], 0.06) and np.allclose(c["held_gross"], 1.8)
    assert RB.leverage(c["held_gross"] + np.r_[0, 0, 0, 0, 0.1], 1.8)["share_days_above_cap"] == pytest.approx(0.2)
    with pytest.raises(ValueError):
        RB.combine(b, s.iloc[1:], 1.0)


def test_reading_keys_on_the_upper_end_of_rho_and_the_net_grid():
    assert RB.reading(0.1, 0.2, True).startswith("MEETS the paper-admission rule across")
    assert RB.reading(-0.1, 0.2, True).startswith("MEETS it only at the point")
    assert RB.reading(-0.2, -0.1, True).startswith("DOES NOT MEET (SR_sleeve")
    assert RB.reading(0.1, 0.2, False).startswith("DOES NOT MEET (the combined")
    assert I.marginal_gain(0.3, 1.0, 0.4) < I.marginal_gain(0.3, 1.0, 0.0)


def test_deflated_reports_both_bars_and_the_desk_bar_is_desk_dsr():
    rng = np.random.default_rng(2)
    pnl = pd.Series(rng.standard_normal(2_500) * 0.003 + 0.0002)
    s = RB.stats(pnl, pd.Series(np.zeros(2_500)))
    d = RB.deflated(s)
    assert d["desk_dsr"] == pytest.approx(d["upper"]["dsr"], abs=1e-12)
    assert d["gumbel"]["sr0_annual"] < d["upper"]["sr0_annual"]          # the paper's bar is the lower one
    assert d["gumbel"]["dsr"] > d["upper"]["dsr"]


# -- review, 2026-10-28 ------------------------------------------------------------

def test_check_same_h_refuses_pnl_and_turnover_from_different_h():
    # E1's defect: P&L on the sized, capped H, turnover on the raw H (k = 1, no cap).
    rng = np.random.default_rng(4)
    idx = pd.bdate_range("2016-01-01", periods=60)
    raw = pd.DataFrame(0.0, index=idx, columns=["a", "b"])
    raw.iloc[5:40, 0], raw.iloc[5:40, 1] = 1.0, -1.0
    R = pd.DataFrame(rng.standard_normal((60, 2)) * 0.01, index=idx, columns=["a", "b"])
    sized = raw * 0.35
    pnl = (sized.shift(2).fillna(0.0) * R).sum(axis=1)
    X.check_same_h(sized, R, pnl, sized.diff().abs().sum(axis=1))           # one H: passes
    with pytest.raises(ValueError, match="different weights"):
        X.check_same_h(sized, R, pnl, raw.diff().abs().sum(axis=1))         # the trial's mix: refused
    with pytest.raises(ValueError, match="P&L is not"):
        X.check_same_h(raw, R, pnl)


def test_capped_bounds_the_rescaling_trades_and_aligns_f_by_two_sessions():
    idx = pd.bdate_range("2018-01-01", periods=12)
    G = pd.Series([1.0, 1.0, 1.0, 2.0, 2.0, 3.6, 3.6, 1.0, 1.0, 1.0, 1.0, 1.0], index=idx)   # decided gross
    win = idx[2:]
    C = pd.DataFrame({"pnl": np.full(10, 0.001), "turn": np.full(10, 0.1),
                      "held_gross": G.shift(2).reindex(win).values, "decided_gross": G.reindex(win).values}, index=win)
    out = RB.capped(C, G, 1.8)
    f = np.minimum(1.0, 1.8 / G)
    extra = ((f - f.shift(1)).abs() * G.shift(1)).reindex(win)
    assert out["rescale_bound_turns_per_year"] == pytest.approx(extra.mean() * 252)
    assert extra.sum() == pytest.approx(abs(0.9 - 1) * 1.0 + abs(0.5 - 0.9) * 2.0 + abs(1 - 0.5) * 3.6)   # |Δf|·G[t-1]
    assert out["net30_at_bound"] < out["net30_no_rescale_cost"]
    bad = C.assign(held_gross=G.reindex(win).values)                          # held not lagged by two: refused
    with pytest.raises(AssertionError):
        RB.capped(bad, G, 1.8)


def test_measure_builds_both_views_and_the_paper_view_uses_the_sleeves_price_returns(monkeypatch):
    monkeypatch.setattr(RB, "REPS", 200)
    rng = np.random.default_rng(9)
    n = 800
    idx = pd.bdate_range("2013-01-01", periods=n)
    base = rng.standard_normal(n) * 0.004 + 0.0003
    held_b = np.r_[np.zeros(10), np.full(n - 10, 1.2)]                    # the book is flat for its first 10 sessions
    book = pd.DataFrame({"pnl": np.where(held_b > 0, base, 0.0), "turn": np.full(n, 0.05), "held_gross": held_b,
                         "decided_gross": np.r_[held_b[2:], 1.2, 1.2]}, index=idx)
    books = {"live_total": book, "live_price": book.assign(pnl=book["pnl"] - 0.0001), "band_only_total": book}
    on = (np.arange(n) // 50) % 2 == 0                                    # active in runs of 50
    s_tot = np.where(on, rng.standard_normal(n) * 0.003 + 0.0004, 0.0)
    dist = np.where(on, 0.0003, 0.0)                                       # a distribution leg paper does not pay
    sleeve = pd.DataFrame({"pnl": s_tot, "pnl_price": s_tot - dist, "dist_overlay": dist,
                           "turn": np.where(on, 0.02, 0.0), "held_gross": np.where(on, 0.6, 0.0),
                           "decided_gross": np.where(on, 0.6, 0.0)}, index=idx)
    sleeve["held_gross"] = sleeve["decided_gross"].shift(2).fillna(0.0)   # evaluate()'s convention
    meta = {"cost_convention": "test", "check": {}, "provenance": {}, "committed_fit_json": "-",
            "r_book_committed": None, "paper_view": {}}
    r = RB.measure("e1", sleeve, meta, books, 1.8)
    w = r["window"]
    tot, pap = r["views"]["total"], r["views"]["paper"]
    sl = sleeve.loc[w["start"]:]
    assert tot["sleeve"]["ann"] == pytest.approx(sl["pnl"].mean() * 252)
    assert pap["sleeve"]["ann"] == pytest.approx(sl["pnl_price"].mean() * 252)           # not the total-return P&L
    assert pap["book"]["ann"] == pytest.approx(books["live_price"].loc[w["start"]:, "pnl"].mean() * 252)
    assert r["distribution_leg"]["window_ann_method_A"] == pytest.approx(dist[sleeve.index >= w["start"]].mean() * 252)
    assert r["distribution_leg"]["window_max_abs_daily_diff_A_vs_B"] < 1e-15
    assert r["activity"]["median_spell_sessions"] == pytest.approx(50.0, abs=2)
    for v in (tot, pap):
        assert v["reading"] == RB.reading(v["marginal_gain"]["gross"]["at_hi"], v["marginal_gain"]["gross"]["at_point"],
                                          v["combined"]["nets_all_positive"])
        assert v["rho"]["range"][0] <= v["rho"]["daily_point"] <= v["rho"]["range"][1]
