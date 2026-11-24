"""The ex-date books: which ex-dates a decision uses, eligibility, never one-sided, and,
through the engine, that the short earns exactly X+1..X+3 and the long X-3..X-1.
Also the point-in-time panel: an ex-date not yet seen cannot be traded. Synthetic data."""
import datetime as dt
import json

import pandas as pd
import pytest

from ops.schedule.nyse_calendar import is_trading_day
from shadow import book as book_mod
from shadow import engine
from shadow.fetch import exdates
from shadow.signals import cef_exdate as sig

D = dt.date
DAYS = [d.date() for d in pd.bdate_range("2026-03-02", "2026-04-17") if is_trading_day(d.date())]
SYMS = ["AAA", "BBB", "CCC", "DDD", "EEE"]


def _px(days=DAYS, syms=SYMS, close=10.0, volume=200_000):
    return pd.DataFrame([{"date": pd.Timestamp(d), "symbol": s, "close": close, "volume": volume}
                         for d in days for s in syms])


def _ex(rows):
    return pd.DataFrame([{"first_seen": pd.Timestamp(fs), "symbol": s, "ex_date": pd.Timestamp(x), "amount": 0.1}
                         for fs, s, x in rows], columns=["first_seen", "symbol", "ex_date", "amount"])


def test_the_dates_a_decision_uses_step_over_a_weekend():
    fri = D(2026, 3, 13)
    assert sig.post_dates(fri) == {D(2026, 3, 12), fri, D(2026, 3, 16)}
    assert sig.pre_dates(fri) == {D(2026, 3, 18), D(2026, 3, 19), D(2026, 3, 20)}


def test_eligibility_needs_price_liquidity_and_a_print_today():
    asof = DAYS[25]
    px = _px(DAYS[:26])
    px.loc[px["symbol"] == "AAA", "close"] = 1.5                         # under $2
    px.loc[px["symbol"] == "BBB", "volume"] = 10_000                     # $100k a day
    px = px[~((px["symbol"] == "CCC") & (px["date"] == pd.Timestamp(asof)))]   # no print today
    assert sig.eligible(px, asof) == ["DDD", "EEE"]
    assert sig.eligible(px[px["date"] < pd.Timestamp(asof)], asof) == []        # panel does not reach asof


def test_after_shorts_post_ex_funds_and_longs_the_rest():
    asof = DAYS[25]
    px = _px(DAYS[:26])
    ex = _ex([(DAYS[20], "AAA", asof), (DAYS[20], "BBB", DAYS[24]), (DAYS[20], "CCC", DAYS[22])])
    w = sig.after(asof, {"px": px, "exdates": ex})
    assert w[["AAA", "BBB"]].tolist() == [-0.25, -0.25]                  # X = D and X = D-1
    assert w[["CCC", "DDD", "EEE"]].tolist() == pytest.approx([1 / 6] * 3)   # X = D-3 is out of the window
    assert w.sum() == pytest.approx(0.0) and w.abs().sum() == pytest.approx(1.0)


def test_a_one_sided_day_is_flat():
    asof = DAYS[25]
    px = _px(DAYS[:26])
    assert sig.after(asof, {"px": px, "exdates": _ex([])}).empty                      # nothing to short
    ex = _ex([(DAYS[20], "AAA", asof)])
    assert sig.before_after(asof, {"px": px, "exdates": ex}).empty                    # a short, no long


def test_before_after_takes_both_sides_and_a_fund_in_both_windows_is_short():
    asof = DAYS[25]
    px = _px(DAYS[:26])
    ex = _ex([(DAYS[20], "AAA", asof), (DAYS[20], "BBB", DAYS[28]), (DAYS[20], "CCC", DAYS[30]),
              (DAYS[20], "AAA", DAYS[29])])                              # AAA: post-ex now and pre-ex for its next
    w = sig.before_after(asof, {"px": px, "exdates": ex})
    assert w.to_dict() == {"BBB": 0.25, "CCC": 0.25, "AAA": -0.5}


def _run_book(tmp_path, signal, ex_rows):
    px = _px()
    st = tmp_path / "state"
    (st / "panels").mkdir(parents=True)
    px.to_parquet(st / "panels" / "px.parquet")
    _ex(ex_rows).to_parquet(st / "panels" / "ex.parquet")
    f = tmp_path / "bk.json"
    f.write_text(json.dumps({"slug": "bk", "card": "x", "signal": f"shadow.signals.cef_exdate:{signal}",
        "panels": {"px": {"path": "px.parquet", "date_col": "date", "required_asof": True},
                   "exdates": {"path": "ex.parquet", "date_col": "first_seen", "required_asof": False}},
        "refresh": [], "fill": "next_close", "notional_usd": 1_000_000, "started": DAYS[1].isoformat(), "enabled": True}))
    b = book_mod.load(f)
    for d in DAYS[21:-1]:
        engine.decide(b, st, d, now=dt.datetime.combine(d, dt.time(18, 50), tzinfo=engine.NY))
    marks = px.rename(columns={})[["date", "symbol", "close"]].assign(dividend=0.0)
    return b, st, {r["date"]: r for r in engine.mark(b, st, marks)}


def _weights_held_on(st, rows, day):
    asof = rows[str(day)]["decision_asof"]
    return json.loads((st / "bk" / "decisions" / f"{asof}.json").read_text())["weights"] if asof else {}


def test_through_the_engine_the_short_is_held_over_x_plus_1_to_x_plus_3(tmp_path):
    X = DAYS[26]
    b, st, rows = _run_book(tmp_path, "after", [(DAYS[10], "AAA", X)])
    short_days = [d for d in DAYS[24:-1] if _weights_held_on(st, rows, d).get("AAA", 0) < 0]
    assert short_days == [DAYS[27], DAYS[28], DAYS[29]]                  # X+1, X+2, X+3


def test_through_the_engine_the_long_is_held_over_x_minus_3_to_x_minus_1(tmp_path):
    X, Y = DAYS[30], DAYS[24]                                            # BBB's earlier ex-date supplies a short
    b, st, rows = _run_book(tmp_path, "before_after", [(DAYS[10], "AAA", X), (DAYS[10], "BBB", Y),
                            (DAYS[10], "CCC", DAYS[26]), (DAYS[10], "DDD", DAYS[28]), (DAYS[10], "EEE", DAYS[30])])
    long_days = [d for d in DAYS[24:-1] if _weights_held_on(st, rows, d).get("AAA", 0) > 0]
    assert long_days and set(long_days) <= {DAYS[27], DAYS[28], DAYS[29]}    # only ever X-3..X-1
    assert DAYS[29] in long_days


def test_an_ex_date_first_seen_after_the_decision_cannot_be_traded(tmp_path):
    X = DAYS[26]
    # first seen ON the ex-date: the decisions at X-1 (which earn X+1) never saw it
    b, st, rows = _run_book(tmp_path, "after", [(X, "AAA", X), (DAYS[10], "BBB", DAYS[40 % len(DAYS)])])
    assert _weights_held_on(st, rows, DAYS[27]).get("AAA", 0) == 0       # X+1 missed
    assert _weights_held_on(st, rows, DAYS[28]).get("AAA", 0) < 0        # X+2 caught: decided at X, after it was seen


def test_the_ex_date_panel_only_ever_adds_rows():
    t1, t2 = D(2026, 3, 2), D(2026, 3, 3)
    a = exdates.merge(None, [{"symbol": "AAA", "ex_date": D(2026, 3, 13), "amount": 0.1}], t1)
    b = exdates.merge(a, [{"symbol": "AAA", "ex_date": D(2026, 3, 13), "amount": 0.1},
                          {"symbol": "BBB", "ex_date": D(2026, 3, 16), "amount": 0.2}], t2)
    assert len(b) == 2 and b.iloc[0]["first_seen"] == pd.Timestamp(t1) and b.iloc[1]["first_seen"] == pd.Timestamp(t2)
    c = exdates.merge(b, [{"symbol": "AAA", "ex_date": D(2026, 3, 13), "amount": 0.12}], D(2026, 3, 4))
    assert len(c) == 3 and (c.iloc[:2].values == b.values).all()         # a revised amount is a new row


def test_both_book_files_load_and_point_at_these_signals():
    for slug, fn in (("cef_exdate_after", sig.after), ("cef_exdate_before_after", sig.before_after)):
        b = book_mod.load(engine.REPO / "shadow" / "books" / f"{slug}.json")
        assert b.signal_fn() is fn and b.notional_usd == 1_000_000 and len(b.refresh) == 2
        assert {p.name: (p.date_col, p.required_asof) for p in b.panels} == {
            "px": ("date", True), "exdates": ("first_seen", False), "exdates_seen": ("date", True)}
