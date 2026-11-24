"""Tests for the C5 opening-cost re-open (scripts/research/reopen_c5/reopen_c5_open_cost.py).

WHY THESE. The script's figures rest on four pieces of arithmetic: the pairing that defines s_open, the
date-weighted series behind its clustered SE, the gain's SE taken from the trial's record, and the
combination read by `inference.read_result`. Each test below pins one of them on synthetic inputs, so
each is a statement about the code, never about the market (CLAUDE.md data rules). Where a plausible
wrong version exists (pairing unpaired rows, averaging date means instead of pooling, taking the
largest t instead of the smallest), the test also shows that the wrong version gives a different answer.
"""
from __future__ import annotations

import hashlib
import json
from math import sqrt

import numpy as np
import pandas as pd
import pytest

from scripts.research.reopen_c5 import reopen_c5_open_cost as M


def _cost_rows():
    """A tiny cost table in cost_table's shape: two dates, two names, both horizons."""
    rows = []
    vals = {  # (date, ticker): (close abs, open abs)
        ("2026-01-02", "AAA"): (5.0, 9.0),
        ("2026-01-02", "BBB"): (4.0, 4.0),
        ("2026-01-05", "AAA"): (6.0, 7.0),
        ("2026-01-05", "BBB"): (3.0, 11.0),
    }
    for h in ("h0", "h1", "h5"):
        for (d, t), (c, o) in vals.items():
            rows.append(dict(date=d, ticker=t, side="close", era="recent", h=h, method="nbbo", abs=c))
            rows.append(dict(date=d, ticker=t, side="open", era="recent", h=h, method="nbbo", abs=o))
    # an unpaired open (no close row) and an open on the prior-close fallback: both must be left out
    rows.append(dict(date="2026-01-05", ticker="CCC", side="open", era="recent", h="h1", method="nbbo", abs=50.0))
    rows.append(dict(date="2026-01-06", ticker="AAA", side="close", era="recent", h="h1", method="nbbo", abs=1.0))
    rows.append(dict(date="2026-01-06", ticker="AAA", side="open", era="recent", h="h1", method="prior_close",
                     abs=80.0))
    rows.append(dict(date="2026-01-06", ticker="BBB", side="close", era="recent", h="h1", method="unmeasured",
                     abs=np.nan))
    rows.append(dict(date="2026-01-06", ticker="BBB", side="open", era="recent", h="h1", method="nbbo", abs=2.0))
    return pd.DataFrame(rows)


def test_paired_diffs_pairs_like_stage6():
    d = M.paired_diffs(_cost_rows(), "recent", "h1")
    assert list(d.index) == [("2026-01-02", "AAA"), ("2026-01-02", "BBB"),
                             ("2026-01-05", "AAA"), ("2026-01-05", "BBB")]
    assert d.tolist() == [4.0, 0.0, 1.0, 8.0]
    assert d.mean() == pytest.approx(3.25)
    # the wrong version (every open minus every close, unpaired) gives another answer
    C = _cost_rows()
    g = C[(C.h == "h1")]
    wrong = g[g.side == "open"]["abs"].mean() - g[g.side == "close"]["abs"].mean()
    assert not np.isclose(wrong, d.mean())


def test_paired_diffs_raises_on_missing_era_or_columns():
    with pytest.raises(M.ReopenError):
        M.paired_diffs(_cost_rows(), "fit", "h1")
    with pytest.raises(M.ReopenError):
        M.paired_diffs(_cost_rows().drop(columns="method"), "recent", "h1")


def _panel(n_dates=40, unbalanced=True, seed=7):
    rng = np.random.default_rng(seed)
    idx, vals = [], []
    for i in range(n_dates):
        k = (3 + i % 4) if unbalanced else 5
        shock = rng.normal()
        for j in range(k):
            idx.append((f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", f"N{j}"))
            vals.append(1.0 + shock + rng.normal())
    return pd.Series(vals, index=pd.MultiIndex.from_tuples(idx, names=["date", "ticker"]))


def test_date_weighted_series_mean_is_the_pooled_mean():
    s = _panel(unbalanced=True)
    x = M.date_weighted_series(s)
    assert len(x) == 40
    assert x.mean() == pytest.approx(s.mean(), rel=1e-12)
    # the wrong version, the mean of per-date means, differs on an unbalanced panel
    assert not np.isclose(s.groupby(level="date").mean().mean(), s.mean(), rtol=1e-6)


def test_date_weighted_lag0_se_is_the_cluster_se_on_a_balanced_panel():
    s = _panel(unbalanced=False)
    x = M.date_weighted_series(s)
    se = M.se_of_mean(x, 0)
    u = s - s.mean()
    cr0 = sqrt((u.groupby(level="date").sum() ** 2).sum()) / len(s)
    assert se == pytest.approx(cr0, rel=1e-10)
    # and it is larger than the naive iid SE here, because each date carries a common shock
    assert se > s.std(ddof=0) / sqrt(len(s))


def test_date_weighted_series_raises():
    s = _panel()
    with pytest.raises(M.ReopenError):
        M.date_weighted_series(s.copy().where(s.index.get_level_values("ticker") != "N0"))
    with pytest.raises(M.ReopenError):
        M.date_weighted_series(s.iloc[:7])          # two dates only
    with pytest.raises(M.ReopenError):
        M.date_weighted_series(s.reset_index(drop=True))


def test_se_of_mean_raises_on_zero_mean():
    with pytest.raises(M.ReopenError):
        M.se_of_mean(np.array([1.0, -1.0, 2.0, -2.0]), 0)


def test_clustered_mean_takes_the_larger_se():
    d = M.clustered_mean(_panel())
    assert d["se"] == max(d["se_l0"], d["se_auto"])
    assert d["lag_auto"] == M.auto_lag(40) == 3


def test_s_open_point_is_the_max_over_h1_h5():
    a = pd.Series([1.0, 2.0])
    b = pd.Series([3.0, 4.0])
    r = M.s_open_point({"h1": a, "h5": b})
    assert r["s_open"] == 3.5 and r["h_star"] == "h5"
    r = M.s_open_point({"h1": b, "h5": a})
    assert r["s_open"] == 3.5 and r["h_star"] == "h1"
    with pytest.raises(M.ReopenError):
        M.s_open_point({"h1": a})


def test_gain_from_record_uses_the_smallest_t():
    rec = {"G": dict(bp_per_turn=8.0, t21=4.0, t5=3.2, t_auto=5.0, n=900, mean_bp_yr=320.0)}
    g = M.gain_from_record(rec)
    assert g["se_bp"] == pytest.approx(8.0 / 3.2) and g["t_which"] == "t5"
    assert g["turn_yr"] == pytest.approx(40.0)
    # the wrong version (largest t) would understate the SE
    assert g["se_bp"] > 8.0 / 5.0
    bad = {"G": dict(bp_per_turn=8.0, t21=4.0, t5=3.2, n=900, mean_bp_yr=320.0)}
    with pytest.raises(M.ReopenError):
        M.gain_from_record(bad)
    with pytest.raises(M.ReopenError):
        M.gain_from_record({})


def test_net_reading_combines_ses_and_reads_the_interval():
    g = dict(gain_bp=7.0, se_bp=1.5, turn_yr=44.0)
    r = M.net_reading(g, 2.0, 0.8, meaningful=1.0, n_trials=1)
    assert r["net_bp"] == pytest.approx(5.0)
    assert r["se_bp"] == pytest.approx(sqrt(1.5 ** 2 + 0.8 ** 2))
    assert r["lo"] == pytest.approx(5.0 - 1.959963984540054 * r["se_bp"], rel=1e-9)
    assert r["outcome"] == "PRESENT" and r["vs_meaningful"] == "ABOVE"
    assert r["net_bp_yr"] == pytest.approx(5.0 * 44.0)
    r2 = M.net_reading(g, 6.5, 0.8, meaningful=1.0, n_trials=1)
    assert r2["outcome"] == "INCONCLUSIVE"
    with pytest.raises(M.ReopenError):
        M.net_reading(g, np.nan, 0.8, meaningful=1.0, n_trials=1)


def test_independent_round_pairs_reads_raw_prints_and_mids():
    days = {"2026-01-02": {"q_open_p1": {"AAA": {"mid": 10.0}, "BBB": {"mid": 20.0}, "CCC": None},
                           "q_close_m1": {"AAA": {"mid": 10.0}, "BBB": {"mid": 20.0}, "CCC": {"mid": 5.0}}}}
    A = pd.DataFrame([
        dict(date="2026-01-02", ticker="AAA", side="open", x="N", c="O", p=10.02),
        dict(date="2026-01-02", ticker="AAA", side="open", x="N", c="Q", p=10.02),
        dict(date="2026-01-02", ticker="AAA", side="close", x="N", c="6", p=10.01),
        dict(date="2026-01-02", ticker="BBB", side="open", x="N", c="O", p=19.96),
        dict(date="2026-01-02", ticker="BBB", side="close", x="N", c="M", p=20.0),   # no 6: not scored
        dict(date="2026-01-02", ticker="CCC", side="open", x="N", c="O", p=5.0),
        dict(date="2026-01-02", ticker="CCC", side="close", x="N", c="6", p=5.0),
        dict(date="2026-01-02", ticker="AAA", side="open", x="P", c="O", p=11.0),    # not the primary
    ])
    s, skipped = M.independent_round_pairs(days, A, "q_open_p1", "q_close_m1")
    assert list(s.index) == [("2026-01-02", "AAA")]
    assert s.iloc[0] == pytest.approx(20.0 - 10.0)
    assert skipped == {"no_open_print": 0, "no_close_print": 1, "no_open_quote": 1, "no_close_quote": 0}
    dup = pd.concat([A, A.iloc[[0]]])
    with pytest.raises(M.ReopenError):
        M.independent_round_pairs(days, dup, "q_open_p1", "q_close_m1")


def test_verify_hashes(tmp_path):
    (tmp_path / "exec").mkdir()
    f = tmp_path / "exec" / "a.json"
    f.write_text(json.dumps({"x": 1}))
    good = {"exec/a.json": hashlib.sha256(f.read_bytes()).hexdigest(), "cef/z.parquet": "00"}
    assert M.verify_hashes(tmp_path, good, ("exec/",)) == 1
    with pytest.raises(M.ReopenError):
        M.verify_hashes(tmp_path, {"exec/a.json": "0" * 64}, ("exec/",))
    with pytest.raises(M.ReopenError):
        M.verify_hashes(tmp_path, {"exec/missing.json": "0" * 64}, ("exec/",))
    with pytest.raises(M.ReopenError):
        M.verify_hashes(tmp_path, good, ("w4/",))


def test_shown_keeps_home_directories_out_of_tracked_output():
    from pathlib import Path
    p = Path("/Users/someone/repo/.claude/worktrees/x/results/cef/_cache_exec")
    assert M.shown(p) == "<main checkout>/.claude/worktrees/x/results/cef/_cache_exec"
    assert M.shown(Path("/tmp/elsewhere")) == "/tmp/elsewhere"
