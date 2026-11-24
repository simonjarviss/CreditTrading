"""The month-end rule's dates, checked against months worked by hand, and through the
engine: the book must earn exactly the returns of E-2, E-1 and E."""
import datetime as dt
import json

import pandas as pd
import pytest

from ops.schedule.nyse_calendar import is_trading_day
from shadow import book as book_mod
from shadow import engine
from shadow.signals import month_end as me

D = dt.date


def test_november_2026_has_thanksgiving_inside_the_window():
    # sessions: Mon 23, Tue 24, Wed 25, (Thu 26 closed), Fri 27, Mon 30 = E
    assert me.month_end_session(D(2026, 11, 10)) == D(2026, 11, 30)
    assert me.decision_days(D(2026, 11, 10)) == [D(2026, 11, 23), D(2026, 11, 24), D(2026, 11, 25)]


def test_a_month_ending_on_a_weekend():
    # May 2026: Sat 30, Sun 31; Mon 25 is Memorial Day. Sessions back from E: Fri 29, Thu 28, Wed 27, Tue 26, Fri 22
    assert me.month_end_session(D(2026, 5, 4)) == D(2026, 5, 29)
    assert me.decision_days(D(2026, 5, 4)) == [D(2026, 5, 22), D(2026, 5, 26), D(2026, 5, 27)]


def test_weight_is_one_on_the_three_days_and_nothing_else():
    days = [d.date() for d in pd.bdate_range("2026-11-02", "2026-11-30") if is_trading_day(d.date())]
    on = [d for d in days if len(me.signal(d, {}))]
    assert on == [D(2026, 11, 23), D(2026, 11, 24), D(2026, 11, 25)]
    assert me.signal(on[0], {}).to_dict() == {"IEF": 1.0}
    with pytest.raises(ValueError, match="not a trading day"):
        me.signal(D(2026, 11, 26), {})


def test_through_the_engine_the_book_earns_e_minus_2_to_e_only(tmp_path):
    days = [d.date() for d in pd.bdate_range("2026-11-16", "2026-12-04") if is_trading_day(d.date())]
    px = pd.DataFrame({"date": [pd.Timestamp(d) for d in days], "symbol": "IEF",
                       "close": [100.0 * 1.001 ** i for i in range(len(days))], "dividend": 0.0})
    f = tmp_path / "month_end_ief.json"
    f.write_text((engine.REPO / "shadow" / "books" / "month_end_ief.json").read_text())
    b = book_mod.load(f)
    b = book_mod.Book(**{**b.__dict__, "started": days[0]})
    st = tmp_path / "state"
    for d in days[:-1]:
        when = dt.datetime.combine(d, dt.time(18, 50), tzinfo=engine.NY)
        engine.decide(b, st, d, now=when)
    rows = {r["date"]: r for r in engine.mark(b, st, px)}
    earning = [d for d, r in rows.items() if r["status"] == "SCORED"]
    assert earning == ["2026-11-25", "2026-11-27", "2026-11-30"]            # E-2, E-1, E
    assert all(float(rows[d]["pnl_price_usd"]) == pytest.approx(1000.0, abs=1.0) for d in earning)
    assert rows["2026-12-01"]["status"] == "FLAT"


def test_the_book_file_loads_and_names_this_signal():
    b = book_mod.load(engine.REPO / "shadow" / "books" / "month_end_ief.json")
    assert b.signal == "shadow.signals.month_end:signal" and b.panels == () and b.notional_usd == 1_000_000
    assert b.signal_fn() is me.signal
