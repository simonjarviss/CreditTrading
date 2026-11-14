"""The spin-off book: which decisions hold a new share, what makes it new, eligible and a
share, never hindsight on a late row, the cap, and the fetcher's first-seen panel. Synthetic."""
import datetime as dt

import pandas as pd

from shadow.fetch import spinoffs as fetch
from shadow.signals import spinoff as sig
from shadow.tests.test_engine import _days

DAYS = _days(30)
D0 = DAYS[20]                                   # the new share's first session


def _px(new=("NEWCO",), first=D0, close=20.0, volume=200_000, old_days=None, upto=None):
    rows = [{"date": pd.Timestamp(d), "symbol": "IWM", "close": 200.0, "volume": 1e7} for d in DAYS]
    for s in new:
        for d in (old_days or [x for x in DAYS if x >= first]):
            rows.append({"date": pd.Timestamp(d), "symbol": s, "close": close, "volume": volume})
    px = pd.DataFrame(rows)
    return px if upto is None else px[px["date"].dt.date <= upto]


def _ev(new="NEWCO", source="PARENT", ex=D0, seen=None, name="Newco Inc Common Stock", exchange="NYSE"):
    return pd.DataFrame([{"first_seen": pd.Timestamp(seen or ex), "id": f"id-{new}", "source_symbol": source, "new_symbol": new,
                          "ex_date": pd.Timestamp(ex), "process_date": pd.Timestamp(ex), "name": name, "exchange": exchange}])


def _w(asof, px=None, ev=None):
    return sig.first_week(asof, {"px": _px(upto=asof) if px is None else px[px["date"].dt.date <= asof],
                                 "spinoffs": _ev() if ev is None else ev})


def test_held_on_the_decisions_of_life_sessions_1_to_3_and_hedged():
    i = DAYS.index(D0)
    for k in (0, 1, 2):
        w = _w(DAYS[i + k])
        assert w.to_dict() == {"NEWCO": -0.10, "IWM": 0.10}
    assert _w(DAYS[i - 1]).empty and _w(DAYS[i + 3]).empty and _w(DAYS[i + 4]).empty


def test_those_decisions_earn_life_sessions_3_4_5_under_next_close_fill():
    # the engine fills a decision at the next close and earns the session after (shadow/engine.py):
    # a weight decided on session index j earns index j + 2
    i = DAYS.index(D0)
    decided = [d for d in DAYS[i - 2:i + 6] if "NEWCO" in _w(d).index]
    assert [DAYS.index(d) + 2 - i + 1 for d in decided] == [3, 4, 5]


def test_a_share_that_already_traded_is_not_new():
    px = _px(old_days=DAYS)                                           # closes long before the ex-date
    assert _w(D0, px=px).empty


def test_when_issued_closes_before_the_ex_date_are_ignored():
    # Yahoo shows a few thin when-issued sessions before the first regular-way one (MSGR, 2026-10).
    i = DAYS.index(D0)
    px = _px(old_days=DAYS[i - 4:])                                    # closes from four sessions before the ex-date
    assert _w(DAYS[i - 1], px=px).empty                                # nothing before the ex-date
    for k in (0, 1, 2):
        assert _w(DAYS[i + k], px=px).to_dict() == {"NEWCO": -0.10, "IWM": 0.10}
    assert _w(DAYS[i + 3], px=px).empty
    # eligibility is judged on the first REGULAR-WAY session, not on a thin when-issued one
    thin = px.copy()
    thin.loc[(thin["symbol"] == "NEWCO") & (thin["date"].dt.date < D0), "volume"] = 10
    assert not _w(D0, px=thin).empty
    thin_day1 = px.copy()
    thin_day1.loc[(thin_day1["symbol"] == "NEWCO") & (thin_day1["date"].dt.date == D0), "volume"] = 10
    assert _w(D0, px=thin_day1).empty


def test_price_and_first_day_volume_floors():
    assert _w(D0, px=_px(close=4.99)).empty
    assert _w(D0, px=_px(close=20.0, volume=49_999)).empty            # $999,980 on day one
    assert not _w(D0, px=_px(close=20.0, volume=50_000)).empty        # exactly $1M


def test_not_a_share_or_not_markable_is_left_out():
    for name in ("Newco Inc Warrant", "Newco Contingent Value Rights", "Newco Units", "Newco 6% Preferred"):
        assert _w(D0, ev=_ev(name=name)).empty
    assert _w(D0, ev=_ev(exchange="BATS")).empty and _w(D0, ev=_ev(exchange="")).empty
    assert _w(D0, ev=_ev(source="NEWCO")).empty                       # a row whose source is the new symbol


def test_a_row_seen_late_is_a_shorter_trade_never_hindsight():
    i = DAYS.index(D0)
    late = _ev(seen=DAYS[i + 1])
    truncated = lambda asof: late[late["first_seen"].dt.date <= asof]      # what engine.load_panels leaves  # noqa: E731
    assert _w(DAYS[i], ev=truncated(DAYS[i])).empty                   # not known on day one
    assert not _w(DAYS[i + 1], ev=truncated(DAYS[i + 1])).empty       # known on day two: earns session 4
    assert not _w(DAYS[i + 2], ev=truncated(DAYS[i + 2])).empty
    assert _w(DAYS[i + 3], ev=truncated(DAYS[i + 3])).empty


def test_no_close_today_or_a_hole_in_its_first_days_means_no_trade():
    i = DAYS.index(D0)
    px = _px()
    hole = px[~((px["symbol"] == "NEWCO") & (px["date"].dt.date == DAYS[i + 1]))]
    assert _w(DAYS[i + 1], px=hole).empty                             # did not print today
    assert _w(DAYS[i + 2], px=hole).empty                             # printed today, but a session is missing
    no_hedge = px[~((px["symbol"] == "IWM") & (px["date"].dt.date == D0))]
    assert _w(D0, px=no_hedge).empty


def test_the_cap_is_fifty_percent_a_side():
    names = [f"N{k}" for k in range(7)]
    ev = pd.concat([_ev(new=n) for n in names], ignore_index=True)
    w = _w(D0, px=_px(new=names), ev=ev)
    assert abs(w.drop("IWM").sum() + 0.50) < 1e-12 and abs(w["IWM"] - 0.50) < 1e-12
    assert abs(w.sum()) < 1e-12 and len(w) == 8


def test_merge_keeps_the_first_seen_date_and_adds_a_corrected_row():
    rows = [{"id": "a", "source_symbol": "P", "new_symbol": "N", "ex_date": D0, "process_date": D0}]
    info = lambda s: {"name": "N Inc", "exchange": "NYSE"}            # noqa: E731
    one = fetch.merge(None, rows, DAYS[5], info)
    two = fetch.merge(one, rows, DAYS[9], info)
    assert len(two) == 1 and two["first_seen"].iloc[0] == pd.Timestamp(DAYS[5])
    moved = [{**rows[0], "ex_date": DAYS[22]}]
    three = fetch.merge(two, moved, DAYS[10], info)
    assert len(three) == 2 and list(three["first_seen"]) == [pd.Timestamp(DAYS[5]), pd.Timestamp(DAYS[10])]
    assert fetch.merge(None, rows, DAYS[5], lambda s: None)["exchange"].iloc[0] == ""     # Alpaca does not list it yet


def test_recent_symbols_window():
    p = fetch.merge(None, [{"id": "a", "source_symbol": "P", "new_symbol": "N", "ex_date": D0, "process_date": D0},
                           {"id": "b", "source_symbol": "Q", "new_symbol": "Q", "ex_date": D0, "process_date": D0}],
                    D0, lambda s: {"name": "", "exchange": "NYSE"})
    assert fetch.recent_symbols(p, D0 + dt.timedelta(days=10), 45) == ["N"]
    assert fetch.recent_symbols(p, D0 + dt.timedelta(days=60), 45) == []
