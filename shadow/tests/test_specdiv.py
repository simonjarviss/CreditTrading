"""The special-dividend book: which decisions hold a name, eligibility judged once at first
sight, never hindsight on a late row, what counts as a company, the cap, and the reader's
first-seen panel. Synthetic."""
import datetime as dt

import pandas as pd

from shadow.fetch import specdivs as fetch
from shadow.signals import specdiv as sig
from shadow.tests.test_engine import _days

DAYS = _days(30, start="2026-02-17")            # no exchange holiday inside (Presidents' Day is the 16th)
SEEN, EX = DAYS[10], DAYS[20]


def _px(syms=("ACME",), close=50.0, volume=100_000, upto=None, skip=()):
    rows = [{"date": pd.Timestamp(d), "symbol": "IWM", "close": 200.0, "volume": 1e7} for d in DAYS]
    rows += [{"date": pd.Timestamp(d), "symbol": s, "close": close, "volume": volume}
             for s in syms for d in DAYS if (s, d) not in skip]
    px = pd.DataFrame(rows)
    return px if upto is None else px[px["date"].dt.date <= upto]


def _ev(sym="ACME", seen=SEEN, ex=EX, amount=2.0, name="Acme Corp Common Stock", exchange="NYSE", i=0):
    return pd.DataFrame([{"first_seen": pd.Timestamp(seen), "first_run": False, "id": f"id-{sym}-{i}", "symbol": sym,
                          "ex_date": pd.Timestamp(ex), "amount": amount, "process_date": pd.Timestamp(ex),
                          "name": name, "exchange": exchange}])


def _w(asof, px=None, ev=None):
    ev = _ev() if ev is None else ev
    ev = ev[ev["first_seen"].dt.date <= asof]                   # what the engine does with a first_seen panel
    px = _px() if px is None else px
    return sig.wait(asof, {"px": px[px["date"].dt.date <= asof], "specdivs": ev})


def test_sessions_until_counts_sessions_and_stops_at_three():
    a = DAYS[5]
    assert [sig.sessions_until(a, DAYS[5 + k]) for k in (-1, 0, 1, 2, 3, 4, 9)] == [0, 0, 1, 2, 3, 3, 3]
    fri = dt.date(2026, 2, 20)
    assert sig.sessions_until(fri, dt.date(2026, 2, 21)) == 0     # an ex-date on a Saturday: no session reaches it
    assert sig.sessions_until(dt.date(2026, 2, 13), dt.date(2026, 2, 17)) == 1   # across Presidents' Day


def test_held_from_first_sight_until_three_sessions_before_the_ex_date_and_hedged():
    i, x = DAYS.index(SEEN), DAYS.index(EX)
    held = [d for d in DAYS[:28] if not _w(d).empty]
    assert held == DAYS[i:x - 2]                                 # decisions SEEN .. X-3
    assert _w(SEEN).to_dict() == {"ACME": 0.10, "IWM": -0.10}


def test_those_decisions_earn_up_to_the_session_before_the_ex_date_and_never_the_ex_date():
    # a weight decided on session index j earns index j + 2 (shadow/engine.py, next_close fill)
    x = DAYS.index(EX)
    earned = [DAYS.index(d) + 2 for d in DAYS[:28] if not _w(d).empty]
    assert earned[0] == DAYS.index(SEEN) + 2 and earned[-1] == x - 1 and x not in earned


def test_a_row_seen_late_is_a_shorter_trade_never_hindsight():
    late = _ev(seen=DAYS[15])
    assert _w(DAYS[14], ev=late).empty                           # not yet seen: nothing, though the ex-date is known later
    assert not _w(DAYS[15], ev=late).empty and not _w(DAYS[17], ev=late).empty
    assert _w(DAYS[18], ev=late).empty                           # X-2: too close to the ex-date
    assert _w(DAYS[18], ev=_ev(seen=DAYS[18])).empty             # first seen two sessions before: never traded


def test_eligibility_is_judged_once_on_prices_through_first_sight():
    assert _w(SEEN, px=_px(close=1.99)).empty                     # price floor
    assert _w(SEEN, px=_px(close=50.0, volume=9_999)).empty       # $499,950 a day
    assert not _w(SEEN, px=_px(close=50.0, volume=10_000)).empty  # exactly $500,000
    assert _w(SEEN, ev=_ev(amount=0.49)).empty                    # 0.98% of $50
    assert not _w(SEEN, ev=_ev(amount=0.50)).empty                # exactly 1%
    # the price doubles after first sight: the yield at first sight still decides
    px = _px()
    px.loc[(px["symbol"] == "ACME") & (px["date"].dt.date > SEEN), "close"] = 150.0
    assert not _w(DAYS[12], px=px, ev=_ev(amount=0.60)).empty
    # and a name that was too small at first sight does not become eligible later
    px = _px(volume=1_000)
    px.loc[(px["symbol"] == "ACME") & (px["date"].dt.date > SEEN), "volume"] = 10_000_000
    assert _w(DAYS[14], px=px).empty


def test_two_special_rows_for_one_ex_date_add_and_the_name_is_held_once():
    ev = pd.concat([_ev(amount=0.30, i=0), _ev(amount=0.25, i=1)], ignore_index=True)
    assert _w(SEEN, ev=ev).to_dict() == {"ACME": 0.10, "IWM": -0.10}   # 0.55 on $50 is 1.1%
    assert _w(SEEN, ev=_ev(amount=0.30)).empty


def test_a_name_with_no_close_today_is_not_held_today():
    px = _px(skip={("ACME", DAYS[12])})
    assert _w(DAYS[12], px=px).empty and not _w(DAYS[13], px=px).empty


def test_no_hedge_price_today_means_nothing_is_held():
    px = _px()
    assert _w(DAYS[12], px=px[~((px["symbol"] == "IWM") & (px["date"].dt.date == DAYS[12]))]).empty


def test_funds_units_receipts_other_books_and_unreadable_exchanges_are_left_out():
    for name in ("Acme Income Fund", "Acme Royalty Trust", "Acme Partners LP Common Units", "Acme 6% Preferred",
                 "Acme SA American Depositary Shares", "Acme Limited Partnership"):
        assert _w(SEEN, ev=_ev(name=name)).empty, name
    assert _w(SEEN, ev=_ev(exchange="OTC")).empty and _w(SEEN, ev=_ev(exchange="")).empty
    assert not _w(SEEN, ev=_ev(exchange="TXSE")).empty
    other = sorted(sig._other_books())[0]
    assert _w(SEEN, px=_px(syms=(other,)), ev=_ev(sym=other)).empty


def test_more_than_five_names_share_half_the_book():
    syms = tuple(f"S{k}" for k in range(8))
    ev = pd.concat([_ev(sym=s) for s in syms], ignore_index=True)
    w = _w(SEEN, px=_px(syms=syms), ev=ev)
    assert len(w) == 9 and abs(w.drop("IWM").sum() - 0.50) < 1e-12 and abs(w["IWM"] + 0.50) < 1e-12
    assert abs(w.sum()) < 1e-12


def test_merge_stamps_first_seen_never_rewrites_and_marks_the_first_run():
    describe = lambda s: {"name": f"{s} Inc", "exchange": "NYSE"}   # noqa: E731
    r1 = {"id": "a", "symbol": "ACME", "ex_date": EX, "amount": 2.0, "process_date": EX}
    first = fetch.merge(None, [r1], DAYS[3], describe)
    assert first["first_run"].tolist() == [True] and first["first_seen"].dt.date.tolist() == [DAYS[3]]
    r2 = {"id": "b", "symbol": "BETA", "ex_date": EX, "amount": 1.0, "process_date": EX}
    again = fetch.merge(first, [r1, r2, dict(r1, amount=2.5)], DAYS[6], describe)
    assert again["symbol"].tolist() == ["ACME", "BETA", "ACME"]
    assert again["first_seen"].dt.date.tolist() == [DAYS[3], DAYS[6], DAYS[6]]      # the old row is untouched
    assert again["first_run"].tolist() == [True, False, False]
    assert len(fetch.merge(again, [r1, r2], DAYS[7], describe)) == 3                # nothing new: nothing added
    empty = fetch.merge(None, [], DAYS[3], describe)
    assert empty.empty and fetch.merge(empty, [r1], DAYS[4], describe)["first_run"].tolist() == [False]


def test_live_symbols_keeps_future_and_just_past_ex_dates():
    describe = lambda s: {}   # noqa: E731
    rows = [{"id": k, "symbol": k, "ex_date": d, "amount": 1.0, "process_date": d}
            for k, d in (("OLD", DAYS[0]), ("NEAR", DAYS[12]), ("AHEAD", DAYS[25]), ("IWM", DAYS[25]))]
    panel = fetch.merge(None, rows, DAYS[3], describe)
    assert fetch.live_symbols(panel, DAYS[15]) == ["AHEAD", "NEAR"]


def test_the_small_name_book_takes_100k_to_under_5m_a_day_and_nothing_else():
    small = lambda **kw: sig.wait_small(SEEN, {"px": kw.get("px", _px())[lambda d: d["date"].dt.date <= SEEN], "specdivs": _ev()})  # noqa: E731
    assert small(px=_px(close=50.0, volume=1_999)).empty          # $99,950 a day: under the floor
    assert not small(px=_px(close=50.0, volume=2_000)).empty      # exactly $100,000
    assert not small(px=_px(close=50.0, volume=99_999)).empty     # $4,999,950
    assert small(px=_px(close=50.0, volume=100_000)).empty        # exactly $5,000,000: the large book's
    w = small(px=_px(close=50.0, volume=2_000))
    assert w["ACME"] == sig.SIZE and w[sig.HEDGE] == -sig.SIZE
    # the research book is unchanged by the band: $100,000 a day is still too small for it
    assert _w(SEEN, px=_px(close=50.0, volume=2_000)).empty
