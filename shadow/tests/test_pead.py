"""The small-stock earnings-drift book: when a release's signal is live, what is eligible, the
top tenth, never hindsight on a late row; and the calendar reader's parsing and filters.
Synthetic: these test the code, never a market claim."""
import datetime as dt

import pandas as pd
import pytest

from shadow.fetch import earnings as fetch
from shadow.signals import pead as sig
from ops.schedule.nyse_calendar import next_trading_day


def _sessions(n, start=dt.date(2026, 2, 17)):
    """n real exchange sessions (the signal counts sessions on the NYSE calendar, holidays out)."""
    out = [start]
    while len(out) < n:
        out.append(next_trading_day(out[-1]))
    return out


DAYS = _sessions(80)
E = DAYS[15]                                   # the release's calendar day (15 sessions of price history before it)
T = DAYS[16]                                   # known: the first session strictly after it


def _ev(n=60, day=E, seen=None, est=1.0, base=1.0, step=0.01):
    """n companies S000.. with surprises rising in the symbol's number."""
    return pd.DataFrame([{"first_seen": pd.Timestamp(seen or T), "first_run": False, "symbol": f"S{i:03d}",
                          "day": pd.Timestamp(day), "call_time": "TAS", "eps_estimate": est,
                          "reported_eps": base + step * i, "market_cap_usd": 5e8, "name": f"Company {i} Inc",
                          "exchange": "NASDAQ"} for i in range(n)])


def _px(syms, days=DAYS, close=20.0, volume=100_000, skip=()):
    rows = [{"date": pd.Timestamp(d), "symbol": "IWM", "close": 200.0, "volume": 1e7} for d in days]
    rows += [{"date": pd.Timestamp(d), "symbol": s, "close": close, "volume": volume}
             for s in syms for d in days if (s, d) not in skip]
    return pd.DataFrame(rows)


def _w(asof, ev=None, px=None):
    ev = _ev() if ev is None else ev
    ev = ev[ev["first_seen"].dt.date <= asof]                 # what the engine does with a first_seen panel
    px = _px(sorted(set(ev["symbol"]))) if px is None else px
    return sig.small_long(asof, {"px": px[px["date"].dt.date <= asof], "earnings": ev})


def test_a_release_is_known_the_session_after_its_day_and_live_for_forty_sessions():
    assert sig.known_session(E) == T
    assert sig.known_session(dt.date(2026, 2, 21)) == dt.date(2026, 2, 23)        # a Saturday release: Monday
    live = [d for d in DAYS if sig.live(E, d)]
    assert live == DAYS[16:56] and len(live) == sig.HOLD


def test_the_book_is_the_top_tenth_equally_weighted_against_iwm():
    w = _w(T)
    longs = w[w > 0]
    assert sorted(longs.index) == [f"S{i:03d}" for i in range(54, 60)]             # 6 of 60: pct rank above 0.9
    assert longs.round(9).nunique() == 1 and longs.sum() == pytest.approx(1.0) and w["IWM"] == -1.0


def test_nothing_is_held_before_it_is_known_or_after_forty_sessions():
    assert _w(E).empty and not _w(T).empty and not _w(DAYS[55]).empty and _w(DAYS[56]).empty


def test_the_first_return_earned_is_two_sessions_after_the_release_is_known():
    # a weight decided on session index j earns index j + 2 (shadow/engine.py, next_close fill)
    earned = [DAYS.index(d) + 2 for d in DAYS[:70] if not _w(d).empty]
    assert earned[0] == DAYS.index(T) + 2 and DAYS.index(E) + 1 not in earned


def test_a_row_seen_late_starts_late_never_in_hindsight():
    late = _ev(seen=DAYS[20])
    assert _w(DAYS[19], ev=late).empty and not _w(DAYS[20], ev=late).empty
    assert _w(DAYS[56], ev=late).empty                                              # and still ends on its own day 40


def test_fewer_than_fifty_live_names_is_flat():
    assert _w(T, ev=_ev(n=49)).empty and not _w(T, ev=_ev(n=50)).empty


def test_price_volume_and_a_print_today_decide_eligibility():
    ev = _ev()
    syms = sorted(set(ev["symbol"]))
    assert _w(T, px=_px(syms, close=4.99)).empty                                    # under $5
    assert _w(T, px=_px(syms, volume=20_000)).empty                                 # $400k a day
    w = _w(T, px=_px(syms, skip={("S059", T)}))                                     # the best name did not print today
    assert "S059" not in w.index and (w > 0).sum() == 6 and "S053" in w.index
    no_hedge = _px(syms)
    assert _w(T, px=no_hedge[~((no_hedge["symbol"] == "IWM") & (no_hedge["date"] == pd.Timestamp(T)))]).empty


def test_a_forecast_near_zero_is_no_signal_and_the_later_release_wins():
    ev = _ev()
    ev.loc[ev["symbol"] == "S059", "eps_estimate"] = 0.04
    assert "S059" not in sig.surprises(ev, T)
    two = pd.concat([_ev(n=1, base=5.0), _ev(n=1, day=DAYS[30], seen=DAYS[31], base=0.5)])
    assert sig.surprises(two, DAYS[31])["S000"] == pytest.approx(-0.5)
    assert sig.surprises(two, DAYS[30])["S000"] == pytest.approx(4.0)             # the later one is not known yet


def test_deleting_later_rows_leaves_the_decision_unchanged():
    ev = pd.concat([_ev(), _ev(day=DAYS[30], seen=DAYS[31], base=3.0)])
    px = _px(sorted(set(ev["symbol"])))
    a = _w(DAYS[22], ev=ev, px=px)
    b = sig.small_long(DAYS[22], {"px": px[px["date"].dt.date <= DAYS[22]], "earnings": _ev()})
    pd.testing.assert_series_equal(a.sort_index(), b.sort_index())


# ---------------------------------------------------------------- the reader

PAGE = """<html><body><table><thead><tr><th>Symbol</th><th>Company</th><th>Event Name</th><th>Earnings Call Time</th>
<th>EPS Estimate</th><th>Reported EPS</th><th>Surprise (%)</th><th>Market Cap</th><th>Follow</th></tr></thead><tbody>
<tr><td>ACME</td><td>Acme Corp</td><td></td><td>TAS</td><td>1.00</td><td>1.25</td><td>25.0</td><td>850.3M</td><td></td></tr>
<tr><td>BIGG</td><td>Big Co</td><td></td><td>AMC</td><td>2.00</td><td>2.10</td><td>5.0</td><td>6.41B</td><td></td></tr>
<tr><td>WAIT</td><td>Not Yet Inc</td><td></td><td>TAS</td><td>0.50</td><td>-</td><td>-</td><td>300M</td><td></td></tr>
<tr><td>FUND</td><td>Acme Income Fund</td><td></td><td>TAS</td><td>0.50</td><td>0.60</td><td>20</td><td>300M</td><td></td></tr>
<tr><td>OTCX</td><td>Otc Co</td><td></td><td>TAS</td><td>0.50</td><td>0.60</td><td>20</td><td>300M</td><td></td></tr>
<tr><td>NEGS</td><td>Loss Co</td><td></td><td>BMO</td><td>-0.20</td><td>-0.35</td><td>-75</td><td>120.5M</td><td></td></tr>
</tbody></table></body></html>"""
ASSETS = {s: {"exchange": "NASDAQ", "tradable": True} for s in ("ACME", "BIGG", "WAIT", "FUND", "NEGS")} | \
         {"OTCX": {"exchange": "OTC", "tradable": True}}


def test_the_page_is_parsed_and_a_dash_is_missing_not_zero():
    df = fetch.parse_page(PAGE)
    assert list(df["Symbol"]) == ["ACME", "BIGG", "WAIT", "FUND", "OTCX", "NEGS"]
    assert df.loc[0, "Reported EPS"] == 1.25 and pd.isna(df.loc[2, "Reported EPS"]) and df.loc[5, "EPS Estimate"] == -0.20
    assert fetch.parse_page("<html><body>nothing today</body></html>") is None


def test_a_page_that_lost_a_column_or_holds_an_unreadable_figure_raises():
    with pytest.raises(RuntimeError, match="Reported EPS"):
        fetch.parse_page(PAGE.replace("<th>Reported EPS</th>", "<th>Actual</th>"))
    with pytest.raises(ValueError):
        fetch.parse_page(PAGE.replace("<td>1.25</td>", "<td>n.m.</td>"))


def test_keep_drops_the_large_the_unreported_the_fund_and_the_unlisted():
    rows = fetch.keep(fetch.parse_page(PAGE), E, ASSETS, 1.9e9)
    assert [r["symbol"] for r in rows] == ["ACME", "NEGS"]
    assert rows[0]["market_cap_usd"] == pytest.approx(850.3e6) and rows[1]["reported_eps"] == -0.35
    assert fetch.parse_cap("6.41B") == 6.41e9 and fetch.parse_cap("-") is None and fetch.parse_cap(float("nan")) is None


def test_merge_only_adds_and_stamps_the_day_first_seen():
    rows = fetch.keep(fetch.parse_page(PAGE), E, ASSETS, 1.9e9)
    first = fetch.merge(None, rows, DAYS[6])
    assert list(first["first_run"]) == [True, True] and len(first) == 2
    revised = [dict(rows[0], reported_eps=9.99)]
    again = fetch.merge(first, revised + [dict(rows[1], symbol="NEWW")], DAYS[8])
    assert len(again) == 3 and again.loc[again["symbol"] == "ACME", "reported_eps"].item() == 1.25     # never changed
    assert again.loc[again["symbol"] == "NEWW", ["first_seen", "first_run"]].values.tolist() == [[pd.Timestamp(DAYS[8]), False]]


def test_read_day_pages_until_a_short_page_and_refuses_an_endless_one():
    full = PAGE.replace("</tbody>", "".join(
        f"<tr><td>X{i:03d}</td><td>X Co</td><td></td><td>TAS</td><td>1</td><td>1</td><td>0</td><td>1M</td><td></td></tr>"
        for i in range(94)) + "</tbody>")
    calls = []
    def get(url):
        calls.append(url)
        return full if "offset=0&" in url else PAGE
    got = fetch.read_day(get, E)
    assert len(calls) == 2 and len(got) == 100                 # the second page repeats six symbols: kept once
    with pytest.raises(RuntimeError, match="pages"):
        fetch.read_day(lambda url: full.replace("X0", f"Y{len(url)}"), E)


def test_the_book_file_loads_and_names_this_signal():
    from shadow import book, engine
    b = book.load(engine.REPO / "shadow" / "books" / "pead_small_long.json")
    assert b.signal_fn() is sig.small_long and {p.name for p in b.panels} == {"px", "earnings", "earnings_seen"}
