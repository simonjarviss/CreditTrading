"""The shadow engine: no lookahead, written once, on time or unscored, nothing stands in
for missing data, and the P&L is the harness's shift(2). Synthetic data throughout."""
import csv
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

from scripts.research import harness
from shadow import book as book_mod
from shadow import engine, scoreboard

UTC = dt.timezone.utc
SYMS = ["AAA", "BBB", "CCC", "DDD"]


def _days(n, start="2026-01-05"):
    return [d.date() for d in pd.bdate_range(start, periods=n)]


def _px(days, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    level = {s: 20.0 + 5 * i for i, s in enumerate(SYMS)}
    for d in days:
        for s in SYMS:
            level[s] *= 1 + rng.normal(0, 0.01)
            rows.append({"date": pd.Timestamp(d), "symbol": s, "close": level[s], "dividend": 0.0})
    return pd.DataFrame(rows)


def _book(tmp_path, days, *, signal="shadow.tests._signals:last_return", started=None):
    f = tmp_path / "books" / "t1.json"
    f.parent.mkdir(exist_ok=True)
    f.write_text(json.dumps({
        "slug": "t1", "card": "results/ideas/none.md", "signal": signal, "fill": "next_close",
        "panels": {"px": {"path": "px.parquet", "date_col": "date", "required_asof": True}}, "refresh": [],
        "notional_usd": 1_000_000, "started": (started or days[1]).isoformat(), "enabled": True}))
    return book_mod.load(f)


def _state(tmp_path, px):
    st = tmp_path / "state"
    (st / "panels").mkdir(parents=True)
    px.to_parquet(st / "panels" / "px.parquet")
    return st


def _evening(d):
    """18:30 New York on d: after the close, long before the next session."""
    return dt.datetime.combine(d, dt.time(18, 30), tzinfo=engine.NY).astimezone(UTC)


def test_a_decision_does_not_change_when_later_rows_are_removed(tmp_path):
    days = _days(12)
    px = _px(days)
    asof = days[6]
    st_full = _state(tmp_path / "a", px)
    st_cut = _state(tmp_path / "b", px[px["date"].dt.date <= asof])
    b = _book(tmp_path, days)
    engine.decide(b, st_full, asof, now=_evening(asof))
    engine.decide(b, st_cut, asof, now=_evening(asof))
    w = [json.loads((s / "t1" / "decisions" / f"{asof}.json").read_text())["weights"] for s in (st_full, st_cut)]
    assert w[0] == w[1] and len(w[0]) == 4


def test_a_decision_is_written_once(tmp_path):
    days = _days(8)
    st = _state(tmp_path, _px(days))
    b = _book(tmp_path, days)
    assert engine.decide(b, st, days[3], now=_evening(days[3]))["status"] == "DECIDED"
    p = st / "t1" / "decisions" / f"{days[3]}.json"
    before = p.read_bytes()
    assert engine.decide(b, st, days[3], now=_evening(days[5]))["status"] == "EXISTS"
    assert p.read_bytes() == before


def test_a_stale_required_panel_does_not_decide(tmp_path):
    days = _days(8)
    px = _px(days)
    st = _state(tmp_path, px[px["date"].dt.date <= days[4]])
    b = _book(tmp_path, days)
    res = engine.decide(b, st, days[5], now=_evening(days[5]))
    assert res["status"] == "UNMEASURED" and str(days[4]) in res["reason"]
    assert not (st / "t1" / "decisions" / f"{days[5]}.json").exists()
    assert len(list(csv.DictReader(open(st / "t1" / "unmeasured.csv")))) == 1


def test_a_nan_weight_raises(tmp_path):
    days = _days(6)
    st = _state(tmp_path, _px(days))
    b = _book(tmp_path, days, signal="shadow.tests._signals:nan_weight")
    with pytest.raises(engine.ShadowError, match="NaN"):
        engine.decide(b, st, days[3], now=_evening(days[3]))


def test_before_the_start_date_raises(tmp_path):
    days = _days(6)
    st = _state(tmp_path, _px(days))
    b = _book(tmp_path, days, started=days[3])
    with pytest.raises(engine.ShadowError, match="before the book started"):
        engine.decide(b, st, days[2], now=_evening(days[2]))


def _run(tmp_path, days, px, *, late=()):
    st = _state(tmp_path, px)
    b = _book(tmp_path, days)
    for d in days[1:-1]:
        when = _evening(d) if d not in late else _evening(days[days.index(d) + 1])  # a day late
        engine.decide(b, st, d, now=when)
    engine.mark(b, st, px)
    return b, st, pd.read_csv(st / "t1" / "scores.csv")


def test_pnl_is_the_harness_shift2(tmp_path):
    days = _days(30)
    px = _px(days, seed=3)
    b, st, sc = _run(tmp_path, days, px)
    wide = px.pivot(index="date", columns="symbol", values="close")
    R = wide.pct_change().fillna(0.0)
    H = pd.DataFrame(0.0, index=wide.index, columns=wide.columns)
    for d in days[1:-1]:
        w = json.loads((st / "t1" / "decisions" / f"{d}.json").read_text())["weights"]
        H.loc[pd.Timestamp(d)] = pd.Series(w)
    want = harness.evaluate(H, R)["pnl"] * b.notional_usd
    got = sc.set_index("date")["pnl_price_usd"]
    for d in days[3:]:
        assert got[str(d)] == pytest.approx(want[pd.Timestamp(d)], abs=0.01)
    assert set(sc["label"]) == {"SIMULATED"}
    # the session after the first fill is the first one scored; before it the book is flat
    assert list(sc["status"].iloc[:1]) == ["FLAT"] and (sc["status"].iloc[1:] == "SCORED").all()


def test_a_late_decision_is_never_scored(tmp_path):
    days = _days(10)
    px = _px(days, seed=5)
    late_day = days[4]
    b, st, sc = _run(tmp_path, days, px, late=(late_day,))
    assert late_day.isoformat() not in set(sc["decision_asof"].dropna())
    # the book carried the decision before it over the session the late one would have earned
    carried = sc.set_index("date").at[str(days[6]), "decision_asof"]
    assert carried == days[3].isoformat()
    assert engine.late_decisions(b, st, days) == [late_day.isoformat()]


def test_a_missing_close_on_a_held_name_is_unmeasured_and_names_it(tmp_path):
    days = _days(10)
    px = _px(days, seed=7)
    marks = px[~((px["symbol"] == "CCC") & (px["date"].dt.date == days[6]))]
    st = _state(tmp_path, px)
    b = _book(tmp_path, days)
    for d in days[1:-1]:
        engine.decide(b, st, d, now=_evening(d))
    rows = {r["date"]: r for r in engine.mark(b, st, marks)}
    assert rows[str(days[6])]["status"] == "UNMEASURED" and "CCC" in rows[str(days[6])]["detail"]
    assert rows[str(days[6])]["pnl_price_usd"] == ""
    assert rows[str(days[8])]["status"] == "SCORED"


def test_an_unexplained_jump_is_unmeasured_until_a_split_row_explains_it(tmp_path):
    days = _days(10)
    px = _px(days, seed=9)
    jump = (px["symbol"] == "BBB") & (px["date"].dt.date >= days[6])
    px.loc[jump, "close"] *= 3.0          # a 1-for-3 reverse split on raw prices
    st = _state(tmp_path / "a", px)
    b = _book(tmp_path, days)
    for d in days[1:-1]:
        engine.decide(b, st, d, now=_evening(d))
    rows = {r["date"]: r for r in engine.mark(b, st, px)}
    assert rows[str(days[6])]["status"] == "UNMEASURED" and "BBB" in rows[str(days[6])]["detail"]
    marks = px.assign(split=1.0)
    marks.loc[(marks["symbol"] == "BBB") & (marks["date"].dt.date == days[6]), "split"] = 1 / 3
    st2 = _state(tmp_path / "b", px)
    for d in days[1:-1]:
        engine.decide(b, st2, d, now=_evening(d))
    rows2 = {r["date"]: r for r in engine.mark(b, st2, marks)}
    assert rows2[str(days[6])]["status"] == "SCORED"
    assert abs(float(rows2[str(days[6])]["pnl_price_usd"])) < 0.2 * b.notional_usd


def test_marking_twice_adds_nothing(tmp_path):
    days = _days(8)
    px = _px(days)
    b, st, sc = _run(tmp_path, days, px)
    assert engine.mark(b, st, px) == []
    assert len(pd.read_csv(st / "t1" / "scores.csv")) == len(sc)


def test_no_dividend_column_leaves_total_return_unmeasured(tmp_path):
    days = _days(8)
    px = _px(days)
    st = _state(tmp_path, px)
    b = _book(tmp_path, days)
    for d in days[1:-1]:
        engine.decide(b, st, d, now=_evening(d))
    rows = engine.mark(b, st, px.drop(columns="dividend"))
    scored = [r for r in rows if r["status"] == "SCORED"]
    assert scored and all(r["pnl_total_usd"] == "" and "UNMEASURED" in r["detail"] for r in scored)


def test_a_dividend_credits_a_long_and_charges_a_short(tmp_path):
    days = _days(8)
    px = _px(days, seed=2)
    px.loc[px["date"].dt.date == days[5], "dividend"] = 0.10
    b, st, sc = _run(tmp_path, days, px)
    row = sc.set_index("date").loc[str(days[5])]
    w = json.loads((st / "t1" / "decisions" / f"{days[3]}.json").read_text())["weights"]
    prev = px[px["date"].dt.date == days[4]].set_index("symbol")["close"]
    want = sum(w[s] * 0.10 / prev[s] for s in w) * b.notional_usd
    assert row["pnl_total_usd"] - row["pnl_price_usd"] == pytest.approx(want, abs=0.02)


def test_state_dir_is_required_and_never_under_data(tmp_path):
    with pytest.raises(engine.ShadowError, match="not set"):
        engine.state_dir({})
    with pytest.raises(engine.ShadowError, match="prod decides on"):
        engine.state_dir({"SHADOW_STATE_DIR": str(engine.REPO / "data" / "shadow")})
    assert engine.state_dir({"SHADOW_STATE_DIR": str(tmp_path)}) == tmp_path.resolve()


def test_a_book_file_missing_a_key_raises_naming_it(tmp_path):
    f = tmp_path / "x.json"
    f.write_text(json.dumps({"slug": "x"}))
    with pytest.raises(book_mod.BookError, match="notional_usd"):
        book_mod.load(f)


def test_scoreboard_withholds_sharpe_below_the_threshold_and_labels_simulated(tmp_path):
    days = _days(8)
    b, st, _ = _run(tmp_path, days, _px(days))
    page = scoreboard.render([b], st, late={}, today=days[-1])
    assert "SIMULATED" in page and f"needs {scoreboard.MIN_DAYS}" in page
    days = _days(40)
    b, st, _ = _run(tmp_path / "long", days, _px(days, seed=4))
    assert f"needs {scoreboard.MIN_DAYS}" not in scoreboard.render([b], st, late={}, today=days[-1])
