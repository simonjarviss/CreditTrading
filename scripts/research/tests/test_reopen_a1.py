"""Tests for the A1 re-open (`scripts/research/reopen_a1/book_windows.py`).

WHY THESE. The measurement's answer rests on four pieces of plumbing, each of which
could be wrong without anything erroring: which windows are selected (they must be
A1's, not a redefinition), which return a short name-day is credited with (H1: the
t+2 return, never t+1), the sign convention of the estimate (positive must mean the
in-window shorts earn LESS), and the block's identity with the in-window shorts'
P&L. All frames here are synthetic, so every test is a statement about the code,
never about the market. No test reads `data/` or a cache.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.research.reopen_a1 import book_windows as bw


def _eps():
    """Episodes in the census's schema: one of each kind the selection must sort."""
    d = pd.Timestamp
    return pd.DataFrame([
        # a deployed programme episode: kept
        {"deployed": "PCN", "first_date": d("2020-12-03"), "last_date": d("2024-08-20"), "programme": True,
         "crsp_class": "unconfirmed", "n_supplements": 10, "company": "A"},
        # too few supplements: not a programme
        {"deployed": "PTY", "first_date": d("2017-03-24"), "last_date": d("2017-03-24"), "programme": False,
         "crsp_class": "confirmed", "n_supplements": 1, "company": "B"},
        # a rights offering: excluded
        {"deployed": "HYT", "first_date": d("2015-01-05"), "last_date": d("2015-03-05"), "programme": True,
         "crsp_class": "rights", "n_supplements": 5, "company": "C"},
        # not a deployed name
        {"deployed": None, "first_date": d("2019-01-05"), "last_date": d("2019-09-05"), "programme": True,
         "crsp_class": "confirmed", "n_supplements": 8, "company": "D"},
        # starts in the holdout: excluded
        {"deployed": "PDI", "first_date": d("2023-09-29"), "last_date": d("2024-09-29"), "programme": True,
         "crsp_class": "after_crsp (2023+, count only)", "n_supplements": 6, "company": "E"},
        # a permno carrying two deployed tickers, one outside the universe passed in
        {"deployed": "PFN;XXX", "first_date": d("2018-09-10"), "last_date": d("2019-01-10"), "programme": True,
         "crsp_class": "unconfirmed", "n_supplements": 4, "company": "F"},
    ])


def test_programme_windows_select_exactly_a1s_set_and_cut_the_end():
    w = bw.programme_windows(_eps(), {"PCN", "PTY", "HYT", "PDI", "PFN"}, pd.Timestamp("2022-12-30"))
    assert bw.window_labels(w) == ["PCN 2020-12-03..2022-12-30", "PFN 2018-09-10..2019-01-10"]
    assert list(w["end_basis"]) == ["fit period ends", "last supplement"]
    assert (w["start"] == w["first_filing"]).all()          # the start is the first supplement: causal


def test_name_days_credit_the_t_plus_2_return_and_sum_to_evaluate():
    from scripts.research.harness import evaluate
    idx = pd.bdate_range("2020-01-01", periods=12)
    H = pd.DataFrame({"A": [0, -1, -1, -1, 0, 0, 1, 1, 0, 0, -1, -1.0],
                      "B": [0, 1, 1, 0.5, 0.5, -0.5, -0.5, 0, 0, 0, 1, 1.0]}, index=idx)
    R = pd.DataFrame({"A": np.arange(12) / 100.0, "B": -np.arange(12) / 200.0}, index=idx)
    M = pd.DataFrame(False, index=idx, columns=H.columns)
    M.loc[idx[2]:idx[3], "A"] = True
    df = bw.name_days(H, R, M, idx[1], "short")
    # A is short decided at rows 1..3 and 10..11; rows 10, 11 earn after the sample and are dropped
    a = df[df["ticker"] == "A"].set_index("date")
    assert list(a.index) == list(idx[1:4])
    assert a.loc[idx[1], "ret_t2"] == R.loc[idx[3], "A"]     # decided t, earns t+2 (H1)
    assert list(a["inside"]) == [False, True, True]
    S = H.where(H < 0, 0.0)
    assert df["pnl"].sum() == pytest.approx(evaluate(S, R)["pnl"].sum(), abs=1e-15)
    with pytest.raises(ValueError):
        bw.name_days(H, R, M, idx[1], "both")


def test_split_is_positive_when_in_window_shorts_earn_less():
    rng = np.random.default_rng(5)
    dates = np.repeat(pd.bdate_range("2019-01-01", periods=200), 4)
    inside = np.tile([True, False, False, False], 200)
    pnl = rng.normal(0, 1e-3, dates.size) - np.where(inside, 5e-4, 0.0)     # inside earns less
    df = pd.DataFrame({"date": dates, "inside": inside, "pnl": pnl})
    s = bw.split(df, "pnl", meaningful=1e-5)
    assert s["estimate_out_minus_in_bp"] > 0
    assert s["inside"]["mean_bp"] < s["outside"]["mean_bp"]
    assert s["read_result"]["outcome"] == "PRESENT"
    wd = bw.within_date(df, "pnl")
    assert wd["mean_bp"] > 0 and wd["dates"] == 200


def test_block_flattens_only_in_window_shorts_and_its_pnl_is_the_identity():
    idx = pd.bdate_range("2021-01-01", periods=30)
    rng = np.random.default_rng(9)
    H = pd.DataFrame(rng.normal(0, 0.2, (30, 3)), index=idx, columns=["A", "B", "C"])
    R = pd.DataFrame(rng.normal(0, 0.01, (30, 3)), index=idx, columns=H.columns)
    M = pd.DataFrame(False, index=idx, columns=H.columns)
    M.loc[idx[5]:idx[20], "B"] = True
    Hb = bw.blocked(H, M)
    assert (Hb.where(M & (H < 0)).stack() == 0).all()             # in-window shorts flat
    assert Hb.where(~(M & (H < 0))).equals(H.where(~(M & (H < 0))))  # everything else untouched
    out = bw.block_counterfactual(H, R, M, idx[2])
    s = out["_series"]
    assert (s["book"] - s["block"] - s["in_window_short"]).abs().max() <= 1e-15
    assert "window" in out and out["window"]["book"]["n"] == 28


def test_a1_reproduction_check_refuses_a_different_window_or_count():
    idx = pd.bdate_range("2013-06-20", periods=5)
    H = pd.DataFrame({"PCN": [0, -0.1, -0.1, -0.1, 0.0]}, index=idx)
    w = pd.DataFrame([{"ticker": "PCN", "start": idx[2], "end": idx[3]}])
    M = pd.DataFrame({"PCN": [False, False, True, True, False]}, index=idx)
    committed = {"book_exposure_fit_period": {
        "book_first_live": str(idx[1].date()), "short_name_days_total": 3,
        "programme_episode": {"windows": [f"PCN {idx[2].date()}..{idx[3].date()}"], "short_name_days_in_windows": 2}}}
    assert bw.assert_matches_a1(w, H, M, idx[1], committed)["short_name_days_inside"] == 2
    committed["book_exposure_fit_period"]["programme_episode"]["short_name_days_in_windows"] = 1
    with pytest.raises(bw.ReopenA1Error):
        bw.assert_matches_a1(w, H, M, idx[1], committed)
    committed["book_exposure_fit_period"]["programme_episode"]["windows"] = ["PCN 2013-06-21..2013-06-26"]
    with pytest.raises(bw.ReopenA1Error):
        bw.assert_matches_a1(w, H, M, idx[1], committed)


def test_spell_hurdle_is_a_round_trip_per_spell_spread_over_its_name_days():
    # Revision 1's meaningful. A is short inside on decisions 1-3 (|w| 0.1, 0.2, 0.3)
    # and 6-7 (|w| 0.4, 0.4): two spells, round trips 2 x 0.2 and 2 x 0.4, over 5
    # name-days -> 15bp x 1.2 / 5. Per unit weight: 15bp x 2 x 2 / 5. The last two
    # decisions earn after the sample and are not counted.
    idx = pd.bdate_range("2020-01-01", periods=12)
    H = pd.DataFrame({"A": [0, -.1, -.2, -.3, 0, 0, -.4, -.4, 0, 0, -.5, -.5]}, index=idx)
    M = pd.DataFrame({"A": [True] * 12}, index=idx)
    h = bw.spell_hurdle(H, M, idx[1], "short")
    assert (h["spells"], h["name_days"]) == (2, 5)
    assert h["meaningful_pnl"] == pytest.approx(15e-4 * 1.2 / 5, abs=1e-15)
    assert h["meaningful_unit"] == pytest.approx(15e-4 * 4 / 5, abs=1e-15)
    with pytest.raises(bw.ReopenA1Error):
        bw.spell_hurdle(H, M, idx[1], "long")           # no in-window longs: no hurdle to invent
