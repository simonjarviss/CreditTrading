"""The site's statistics agree with ops/orient.py's, and never fill a gap."""
import math
import random

import pytest

from dashboard import metrics as M


def series(n=30, seed=7, start=100000.0, unfunded=0):
    rnd = random.Random(seed)
    rows = [{"date": f"2026-09-{d:02d}", "equity": 0.0, "change_usd": None} for d in range(1, unfunded + 1)]
    eq = start
    for i in range(n):
        d = f"2026-10-{i + 1:02d}" if i < 31 else f"2026-11-{i - 30:02d}"
        if i == 0:
            rows.append({"date": d, "equity": eq, "change_usd": None if not unfunded else eq})
            continue
        ch = round(rnd.gauss(20, 300), 2)
        eq = round(eq + ch, 2)
        rows.append({"date": d, "equity": eq, "change_usd": ch})
    return rows


def test_agrees_with_orient_to_the_cent():
    """Parity with the desk's own reader of the P&L of record (ops/orient.py official_pnl)."""
    from ops import orient
    rows = series(n=45, unfunded=2)
    reading = {"value": {"where": "t", "file": "eod_equity.csv", "n_rows": len(rows),
                         "rows": [(r["date"], repr(r["equity"]), "" if r["change_usd"] is None else repr(r["change_usd"]))
                                  for r in rows]}}
    o = orient.official_pnl(reading)
    s = M.summary(rows)
    assert s["first_date"] == o["first_funded"]["date"]
    assert s["cum_pnl"] == pytest.approx(o["cumulative_usd"], abs=0.005)
    assert s["hwm"] == pytest.approx(o["hwm"]["equity"], abs=0.005) and s["hwm_date"] == o["hwm"]["date"]
    assert s["drawdown"] == pytest.approx(o["drawdown_frac"], abs=1e-9)
    assert s["vol"] == pytest.approx(o["vol"]["annual"], rel=1e-12) and s["n_returns"] == o["vol"]["n"]


def test_hand_computed_figures():
    rows = [{"date": "2026-11-02", "equity": 100.0, "change_usd": None},
            {"date": "2026-11-03", "equity": 110.0, "change_usd": 10.0},
            {"date": "2026-11-04", "equity": 99.0, "change_usd": -11.0},
            {"date": "2026-11-05", "equity": 104.0, "change_usd": 5.0}]
    s = M.summary(rows)
    assert s["cum_pnl"] == 4.0 and s["cum_return"] == pytest.approx(0.04)
    assert s["hwm"] == 110.0 and s["max_drawdown"] == pytest.approx(99 / 110 - 1) and s["max_drawdown_date"] == "2026-11-04"
    assert s["drawdown"] == pytest.approx(104 / 110 - 1)
    assert s["best_day"] == ("2026-11-03", pytest.approx(0.10)) and s["worst_day"][0] == "2026-11-04"
    assert s["sharpe"] is None and s["vol"] is None               # 3 returns: below the 20 the page needs
    assert M.monthly(rows) == [("2026-11", 4.0, pytest.approx(0.04))]


def test_sharpe_appears_at_twenty_returns():
    assert M.summary(series(n=20))["sharpe"] is None
    s = M.summary(series(n=21))
    assert s["n_returns"] == 20 and s["sharpe"] is not None and math.isfinite(s["sharpe"])


def test_unfunded_rows_are_dropped_and_zero_after_funding_raises():
    rows = series(n=5, unfunded=3)
    assert M.summary(rows)["first_date"] == "2026-10-01"
    rows[-1]["equity"] = 0.0
    with pytest.raises(ValueError, match="not positive after funding"):
        M.summary(rows)


def test_a_missing_change_after_the_first_row_raises():
    rows = series(n=5)
    rows[3]["change_usd"] = None
    with pytest.raises(ValueError, match="no change_usd"):
        M.summary(rows)


def test_combined_uses_only_common_sessions_and_says_how_many_it_left_out():
    a = series(n=6, seed=1)
    b = series(n=6, seed=2)[1:]                          # starts a session later
    rows, left = M.combined({"a": a, "b": b})
    assert [r["date"] for r in rows] == [r["date"] for r in b]
    assert left == 1
    assert rows[-1]["equity"] == pytest.approx(a[-1]["equity"] + b[-1]["equity"])
    assert rows[0]["change_usd"] is None


def test_the_portfolio_composite_weights_by_equity_and_starts_each_book_at_its_first_send():
    """Team lead, 2026-11-24: one portfolio line; release-check review: C4's idle sessions counted."""
    a = [{"date": f"2026-11-0{i}", "equity": e, "change_usd": c} for i, e, c in
         ((2, 100.0, None), (3, 110.0, 10.0), (4, 99.0, -11.0), (5, 99.0, 0.0))]
    b = [{"date": f"2026-11-0{i}", "equity": e, "change_usd": c} for i, e, c in
         ((2, 300.0, None), (3, 300.0, 0.0), (4, 330.0, 30.0), (5, 330.0, 0.0))]
    ta, tb = M.trading_rows(a, "2026-11-03"), M.trading_rows(b, "2026-11-04")
    assert [r["date"] for r in tb] == ["2026-11-03", "2026-11-04", "2026-11-05"]       # b's idle 11-03 is its base only
    comp, left = M.composite({"a": ta, "b": tb})
    assert left == 0
    assert comp[0][:4] == ("2026-11-03", 0.10, 10.0, 100.0)                            # only a is trading
    assert comp[1][1] == pytest.approx((-11.0 + 30.0) / (110.0 + 300.0))                # both, weighted by equity
    assert M.trading_rows(a, None) == []
    with pytest.raises(ValueError):
        M.trading_rows(a, "2026-11-02")                                               # no base before the first send


def test_a_session_a_trading_book_lacks_is_left_out_not_summed_over_part():
    a = [{"date": d, "equity": 100.0, "change_usd": c} for d, c in (("2026-11-02", None), ("2026-11-03", 1.0), ("2026-11-04", 1.0))]
    b = [{"date": d, "equity": 100.0, "change_usd": c} for d, c in (("2026-11-02", None), ("2026-11-03", 1.0))]
    comp, left = M.composite({"a": M.trading_rows(a, "2026-11-03"), "b": M.trading_rows(b, "2026-11-03")})
    assert [c[0] for c in comp] == ["2026-11-03"] and left == 1


def test_the_profile_on_a_known_series():
    rs = [0.01, -0.02, 0.015, -0.005, 0.0] * 5                                          # 25 sessions
    dated = [(f"2026-10-{i + 1:02d}", r, r * 100) for i, r in enumerate(rs)]
    p = M.profile(dated)
    n, mean = 25, sum(rs) / 25
    sd = (sum((r - mean) ** 2 for r in rs) / 24) ** 0.5
    assert p["n"] == n and p["vol"] == pytest.approx(sd * 252 ** 0.5)
    assert p["sharpe"] == pytest.approx(mean / sd * 252 ** 0.5)
    dd = (sum(min(r, 0) ** 2 for r in rs) / n) ** 0.5
    assert p["sortino"] == pytest.approx(mean / dd * 252 ** 0.5)
    assert p["hit_rate"] == pytest.approx(10 / 20)                                       # zero sessions do not count
    assert p["avg_gain"] == pytest.approx(0.0125) and p["avg_loss"] == pytest.approx(-0.0125)
    assert p["profit_factor"] == pytest.approx(sum(r for r in rs if r > 0) / -sum(r for r in rs if r < 0))
    assert p["var95"] == pytest.approx(0.02) and p["es95"] == pytest.approx(0.02)         # the 5th percentile is a -2% day
    assert p["worst"] == ("2026-10-02", -0.02) and p["best"] == ("2026-10-03", 0.015)
    assert p["cum_return"] == pytest.approx(math.prod(1 + r for r in rs) - 1)


def test_ratios_need_twenty_sessions():
    p = M.profile([(f"2026-10-{i + 1:02d}", 0.001 * (-1) ** i, 1.0) for i in range(19)])
    assert all(p[k] is None for k in ("vol", "sharpe", "sortino", "calmar", "var95", "es95", "skew", "kurt"))
