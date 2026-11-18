"""The unit-trust termination book: which decisions hold a fund (decided T-1, earning T+1..T+3,
nothing a day early or late), a termination date off a session, a calendar row that cannot be
read is refused by name, the card's floors read at T-10, the weights and the cap, the size
filter's point-in-time notices, and the prospectus parser behind the calendar. Synthetic."""
import csv
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from ops.schedule.nyse_calendar import next_trading_day
from shadow import book as book_mod
from shadow.fetch import uit_px
from shadow.signals import uit_termination as sig
from shadow.universes import build_uit_terminations_v1 as b

ROOT = Path(__file__).resolve().parents[1]


def _sessions(n, start=dt.date(2026, 4, 6)):
    out = [start]
    while len(out) < n:
        out.append(next_trading_day(out[-1]))        # the exchange's own calendar: Memorial Day is skipped
    return out


DAYS = _sessions(45)
T = DAYS[30]
I = DAYS.index(T)


def _px(syms=("AAA",), close=10.0, volume=20_000, skip=(), over=None):
    rows = [{"date": pd.Timestamp(d), "symbol": s, "close": close, "volume": volume}
            for s in syms for d in DAYS if (s, d) not in skip]
    px = pd.DataFrame(rows)
    for (s, d0, d1), (c, v) in (over or {}).items():
        m = (px["symbol"] == s) & (px["date"].dt.date >= d0) & (px["date"].dt.date <= d1)
        px.loc[m, ["close", "volume"]] = [c, v]
    return px


def _row(sym="AAA", term=T, filed="2024-04-10", acc="0001445546-24-000001", trust="Alpha Closed-End Portfolio, Series 1",
         pct="4.00", k="1", cik="111", series="FT 11111"):
    return {"sponsor": "First Trust", "series": series, "trust": trust, "cik": cik, "accession": acc, "url": "u",
            "filed": filed, "deposit_date": filed, "termination_date": term if isinstance(term, str) else term.isoformat(),
            "trusts_in_filing": k, "symbol": sym, "fund": "A Fund", "pct": pct, "shares": "100", "built": "2026-11-18"}


def _syms(n):
    return tuple("FA" + chr(65 + k) for k in range(n))            # FAA, FAB, ...: tickers are letters


def _w(asof, rows=None, px=None, notices=None):
    px = _px() if px is None else px
    px = px[px["date"].dt.date <= asof]                         # what the engine hands the signal
    cal = sig.read_calendar([_row()] if rows is None else rows)
    return sig._targets(asof, px, cal, None if notices is None else sig.read_notices(notices))


# ------------------------------------------------------------------ alignment

def test_a_termination_on_T_is_decided_on_T_minus_1_and_held_by_three_decisions_only():
    held = [d for d in DAYS[11:43] if not _w(d).empty]
    assert held == [DAYS[I - 1], DAYS[I], DAYS[I + 1]]
    assert _w(DAYS[I - 2]).empty                                 # a day early: nothing
    assert _w(DAYS[I + 2]).empty                                 # the decision that fills at T+3's close: flat


def test_those_decisions_fill_at_the_close_of_T_and_earn_T_plus_1_to_T_plus_3():
    # a weight decided on session index j fills at j + 1 and earns j + 2 (shadow/engine.py, next_close)
    held = [DAYS.index(d) for d in DAYS[11:43] if not _w(d).empty]
    assert held[0] + 1 == I                                      # the first fill is T's close
    assert [j + 2 for j in held] == [I + 1, I + 2, I + 3]        # T+1, T+2, T+3 and no other session
    assert held[-1] + 2 == I + 3                                 # the exit fills at T+3's close


def test_window_is_the_sessions_either_side_and_crosses_a_holiday():
    assert sig.window(DAYS[20]) == (DAYS[19], DAYS[20], DAYS[21])
    fri, tue = dt.date(2026, 5, 22), dt.date(2026, 5, 26)        # Memorial Day is Monday 2026-05-25
    assert sig.window(fri)[2] == tue and sig.window(tue)[0] == fri


def test_a_date_off_a_session_means_the_last_session_before_it():
    fri = next(d for d in DAYS[20:] if d.weekday() == 4 and next_trading_day(d) == d + dt.timedelta(days=3))
    for off in (1, 2):                                           # Saturday, Sunday
        assert sig.termination_session(fri + dt.timedelta(days=off)) == fri
    assert sig.termination_session(dt.date(2026, 5, 25)) == dt.date(2026, 5, 22)    # a holiday Monday
    assert sig.termination_session(fri) == fri
    rows = [_row(term=fri + dt.timedelta(days=1))]
    j = DAYS.index(fri)
    assert [d for d in DAYS[11:43] if not _w(d, rows=rows).empty] == DAYS[j - 1:j + 2]


def test_the_decision_does_not_change_when_later_prices_are_removed_or_changed():
    px = _px(over={("AAA", DAYS[I], DAYS[-1]): (0.5, 1)})        # a collapse from T on
    for d in (DAYS[I - 1], DAYS[I]):
        assert _w(d, px=px).to_dict() == _w(d).to_dict() == {"AAA": sig.CAP}


def test_the_decision_date_must_be_a_session():
    with pytest.raises(ValueError, match="not a trading day"):
        _w(dt.date(2026, 5, 25))


# ------------------------------------------------------------------ the calendar is refused, never guessed

def test_a_row_with_an_unreadable_termination_date_is_refused_by_name():
    for bad in ("February 30, 2027", "", "2027-13-01", "02/26/2027"):
        with pytest.raises(sig.CalendarError) as e:
            sig.read_calendar([_row(), _row(sym="BBB", term=bad, trust="Beta Closed-End Portfolio, Series 9", acc="0001445546-24-000777")])
        msg = str(e.value)
        assert "Beta Closed-End Portfolio, Series 9" in msg and "0001445546-24-000777" in msg and "termination_date" in msg


def test_other_unusable_rows_are_refused_too():
    for kw in ({"filed": "last year"}, {"sym": "aaa"}, {"sym": ""}, {"pct": "n/a"}, {"pct": "0"}, {"k": "0"}, {"acc": ""}):
        with pytest.raises(sig.CalendarError):
            sig.read_calendar([_row(**kw)])


def test_a_prospectus_filed_within_30_days_of_its_date_raises():
    late = (T - dt.timedelta(days=30)).isoformat()
    with pytest.raises(sig.CalendarError, match="within 30 days"):
        _w(DAYS[I], rows=[_row(filed=late)])
    assert not _w(DAYS[I], rows=[_row(filed=(T - dt.timedelta(days=31)).isoformat())]).empty


# ------------------------------------------------------------------ eligibility: the card's floors at T-10

def test_floors_are_read_ten_sessions_before_T():
    ref = DAYS[I - 10]
    assert sig.sessions_before(T, sig.ELIGIBLE_AT) == ref
    d = DAYS[I]
    assert _w(d, px=_px(close=1.99, volume=200_000)).empty               # under $2
    assert _w(d, px=_px(close=10.0, volume=9_999)).empty                 # $99,990 a day
    assert not _w(d, px=_px(close=10.0, volume=10_000)).empty            # exactly $100,000
    # liquid only AFTER T-10 (the selling itself): still not eligible
    assert _w(d, px=_px(volume=100, over={("AAA", DAYS[I - 9], DAYS[-1]): (10.0, 1_000_000)})).empty
    # under the price floor after T-10: still eligible, the floors were read once
    assert not _w(d, px=_px(over={("AAA", DAYS[I - 9], DAYS[-1]): (1.50, 20_000)})).empty
    assert _w(d, px=_px(skip={("AAA", ref)})).empty                      # no close on T-10: cannot be read
    short = _px()
    assert _w(d, px=short[short["date"].dt.date >= DAYS[I - 15]]).empty  # 6 sessions of data at T-10, not 10


def test_a_fund_with_no_close_on_the_decision_date_is_not_held_that_day():
    px = _px(skip={("AAA", DAYS[I])})
    assert not _w(DAYS[I - 1], px=px).empty and _w(DAYS[I], px=px).empty and not _w(DAYS[I + 1], px=px).empty
    assert _w(DAYS[I], px=_px(syms=("ZZZ",))).empty                       # no price at all


# ------------------------------------------------------------------ weights

def test_weights_follow_n_series_add_to_one_and_are_long_only():
    syms = _syms(26)                         # a trust holds 26 funds at the median
    rows = [_row(sym=s) for s in syms]
    w = _w(DAYS[I - 1], rows=rows, px=_px(syms=syms))
    assert len(w) == 26 and abs(w.sum() - 1.0) < 1e-12 and (w > 0).all() and abs(w["FAA"] - 1 / 26) < 1e-12
    # a second trust sells F00 on the same T: twice the weight of the others, 2/27
    rows.append(_row(sym="FAA", acc="0001445546-24-000002", trust="Beta Closed-End Portfolio, Series 2"))
    w = _w(DAYS[I - 1], rows=rows, px=_px(syms=syms))
    assert abs(w["FAA"] - 2 / 27) < 1e-12 and abs(w["FAB"] - 1 / 27) < 1e-12 and abs(w.sum() - 1.0) < 1e-12


def test_one_trust_listed_twice_for_a_fund_counts_once():
    assert len(sig.events(sig.read_calendar([_row(), _row()]), (T,))[("AAA", T)]) == 1


def test_no_fund_exceeds_the_cap_and_the_rest_is_cash():
    syms = _syms(4)
    w = _w(DAYS[I - 1], rows=[_row(sym=s) for s in syms], px=_px(syms=syms))
    assert w.to_dict() == {s: sig.CAP for s in syms} and abs(w.sum() - 0.40) < 1e-12
    syms = _syms(10)                         # ten funds: the cap is exactly not binding
    w = _w(DAYS[I - 1], rows=[_row(sym=s) for s in syms], px=_px(syms=syms))
    assert abs(w.sum() - 1.0) < 1e-12 and abs(w.max() - sig.CAP) < 1e-12


def test_a_fund_in_two_windows_is_one_position_with_both_counts():
    syms = _syms(12)
    rows = [_row(sym=s) for s in syms] + [_row(sym="FAA", term=DAYS[I + 1], acc="0001445546-24-000003", trust="Gamma, Series 3")]
    w = _w(DAYS[I], rows=rows, px=_px(syms=syms))                        # T and T+1 are both in the window of DAYS[I]
    assert w["FAA"] == sig.CAP and abs(w["FAB"] - 1 / 13) < 1e-12


# ------------------------------------------------------------------ the 5%-of-volume line

def _notice(filed, sold, redeemed=0.0, fy="2025-03-31", cik="111", acc="n1"):
    return {"cik": cik, "series": "FT 11111", "accession": acc, "url": "u", "form": "24F-2NT", "filed": filed if isinstance(filed, str) else filed.isoformat(),
            "fiscal_year_end": fy, "sold_usd": str(sold), "redeemed_usd": str(redeemed), "built": "2026-11-18"}


def test_big_sale_needs_five_per_cent_of_nine_sessions_volume_from_notices_filed_in_time():
    # nine sessions T-18..T-10 at $200,000 a day = $1.8M; a 4% holding of a $2.25M trust is $90,000 = 5.0%
    assert sig.sessions_before(T, 18) == DAYS[I - 18] and len(DAYS[I - 18:I - 9]) == 9
    d, early = DAYS[I - 1], T - dt.timedelta(days=200)
    assert not _w(d, notices=[_notice(early, 2_250_000)]).empty
    assert _w(d, notices=[_notice(early, 2_249_000)]).empty                       # 4.998%
    assert _w(d, notices=[_notice(early, 4_000_000, redeemed=1_800_000)]).empty   # net $2.2M
    assert _w(d, notices=[]).empty                                                # no notice: no size, left out
    assert not _w(d).empty                                                        # the primary line does not ask
    assert _w(d, notices=[_notice(early, 9_000_000, cik="222")]).empty            # another registrant's notice


def test_a_notice_filed_within_30_days_of_T_is_not_used():
    d = DAYS[I - 1]
    assert _w(d, notices=[_notice(T - dt.timedelta(days=30), 9_000_000)]).empty
    assert not _w(d, notices=[_notice(T - dt.timedelta(days=31), 9_000_000)]).empty


def test_size_is_split_between_the_trusts_of_a_filing_and_an_amendment_replaces_its_year():
    n = sig.read_notices([_notice("2025-05-01", 4_000_000, 500_000), _notice("2025-06-01", 3_000_000, 500_000, acc="n2"),
                          _notice("2026-01-10", 1_000_000, 200_000, fy="2025-12-31", acc="n3")])
    assert sig.trust_size("111", 1, T, n) == 2_500_000 + 800_000                  # the June amendment, plus the next year
    assert sig.trust_size("111", 2, T, n) == (2_500_000 + 800_000) / 2
    assert sig.trust_size("999", 1, T, n) is None
    assert sig.trust_size("111", 1, T, sig.read_notices([_notice("2025-05-01", 1.0, 5.0)])) == 0.0   # floored at zero


# ------------------------------------------------------------------ the price fetcher's list

def test_the_fetcher_asks_for_funds_near_a_date_else_the_next_date_else_raises():
    cal = sig.read_calendar([_row(sym="NEAR", term=T), _row(sym="PAST", term=DAYS[2]), _row(sym="FAR", term="2027-06-15")])
    assert uit_px.symbols_needed(cal, T - dt.timedelta(days=20)) == ["NEAR"]
    assert uit_px.symbols_needed(cal, T + dt.timedelta(days=uit_px.BACK_DAYS)) == ["NEAR"]     # still held to T+3
    assert uit_px.symbols_needed(cal, dt.date(2026, 9, 1)) == ["FAR"]                          # a quiet month: the next date
    with pytest.raises(RuntimeError, match="rebuild"):
        uit_px.symbols_needed(cal, dt.date(2027, 9, 1))


# ------------------------------------------------------------------ the prospectus parser behind the calendar

FT_TEXT = """
                           Summary of Essential Information

Mandatory Termination Date (6)                                 May 12, 2026

                            Schedule of Investments

               High-Yield Income Closed-End Portfolio, Series 109
                                    FT 11411

    At the Opening of Business on the Initial Date of Deposit-April 10, 2024

Ticker Symbol and                                               Percentage
Name of Issuer of Securities (1)                                of Aggregate    Number     Value      Cost
________________________________                                ______________  _________  _________  _____________
CLOSED-END FUNDS (75.00%):
High-Yield Bond Funds (50.00%):
EAD      Allspring Income Opportunities Fund                      25.00%         1,477      $ 6.55     $  9,674
FFC      Flaherty & Crumrine Preferred and Income Securities Fund
         Incorporated                                             25.00%           319       16.11        5,139
World Income Funds (25.00%):
FAX      abrdn Asia-Pacific Income Fund, Inc.                     25.00%           326       15.78        5,144
COMMON STOCKS (25.00%):
ED       Consolidated Edison, Inc.                                25.00%            50       90.00        4,500

(1) The Trust has a Mandatory Termination Date of April 10,
2026.

                            Schedule of Investments

                  Undated Closed-End Portfolio, Series 7
                                    FT 11411

    At the Opening of Business on the Initial Date of Deposit-April 10, 2024

CLOSED-END FUNDS (100.00%):
HYT      BlackRock Corporate High Yield Fund, Inc.                100.00%          987        9.80        9,673

(1) See the notes.
"""
FILING = {"path": "edgar/data/2011411/0001445546-24-002788.txt", "sponsor": "First Trust", "code": "FT", "series": "FT 11411",
          "cik": "2011411", "filed": "2024-04-10", "kept": True}


def test_the_parser_reads_dates_from_the_text_and_holdings_under_their_heading():
    trusts, bad = b.parse_document(FT_TEXT, "FT")
    assert [t["trust"] for t in trusts] == ["High-Yield Income Closed-End Portfolio, Series 109"]
    t = trusts[0]
    assert t["deposit"] == dt.date(2024, 4, 10) and t["termination"] == dt.date(2026, 4, 10)
    assert [(h["symbol"], h["closed_end"], h["pct"], h["shares"]) for h in t["holdings"]] == [
        ("EAD", True, 25.0, 1477), ("FFC", True, 25.0, 319), ("FAX", True, 25.0, 326), ("ED", False, 25.0, 50)]
    assert t["holdings"][1]["fund"].endswith("Securities Fund Incorporated")          # the wrapped name is joined
    assert b.is_closed_end_trust(t)
    # the filing prints two different dates and the second trust has none of its own: left out, named, not guessed
    assert bad == [("Undated Closed-End Portfolio, Series 7", "no termination date in the filing text")]


def test_a_mixed_case_closed_end_heading_counts_and_a_sub_heading_does_not_reset_it():
    seg = "Closed-End Funds (100.00%):\nMulti-Sector Bond Funds (3.34%):\nERC   Allspring Multi-Sector Income Fund   1.67%   275   9.35   2,570\n"
    assert [h["closed_end"] for h in b.holdings(seg)] == [True]
    seg = "COMMON STOCKS (100.00%):\nUTILITIES (10.00%):\nED   Consolidated Edison, Inc.   1.67%   275   9.35   2,570\n"
    assert [h["closed_end"] for h in b.holdings(seg)] == [False]
    assert [h["kind"] for h in b.holdings("ED   Consolidated Edison, Inc.   1.67%   275   9.35   2,570\n")] == [None]
    assert b.day("February 30, 2027") is None and b.day("February 26,\n2027") == dt.date(2027, 2, 26)


def test_a_trust_left_out_is_listed_with_its_accession_number_never_dropped():
    cal, unparsed, n = b.build_rows([FILING, {**FILING, "path": "edgar/data/1/0001445546-24-000009.txt", "kept": False}],
                                    read=lambda p: FT_TEXT, built="2026-11-18")
    assert {r["symbol"] for r in cal} == {"EAD", "FFC", "FAX"}                        # the common stock is not an event
    assert {r["termination_date"] for r in cal} == {"2026-04-10"} and {r["accession"] for r in cal} == {"0001445546-24-002788"}
    assert cal[0]["url"] == "https://www.sec.gov/Archives/edgar/data/2011411/0001445546-24-002788.txt"
    assert [(u["accession"], u["trust"], u["reason"]) for u in unparsed] == [
        ("0001445546-24-002788", "Undated Closed-End Portfolio, Series 7", "no termination date in the filing text")]
    assert n["not read: under 15 mentions of closed-end"] == 1 and n["closed-end trusts in the calendar"] == 1
    sig.read_calendar(cal)                                                             # what the builder writes, the book reads
    _, unparsed, _ = b.build_rows([FILING], read=lambda p: "nothing like a prospectus", built="x")
    assert [(u["accession"], u["reason"]) for u in unparsed] == [("0001445546-24-002788", "no portfolio header")]


def test_a_trust_with_no_heading_or_too_close_to_its_date_is_listed():
    text = FT_TEXT.replace("CLOSED-END FUNDS (75.00%):\n", "").replace("COMMON STOCKS (25.00%):\n", "")
    _, unparsed, _ = b.build_rows([FILING], read=lambda p: text, built="x")
    assert any("no heading above the holdings" in u["reason"] for u in unparsed)
    cal, unparsed, _ = b.build_rows([{**FILING, "filed": "2026-03-20"}], read=lambda p: FT_TEXT, built="x")
    assert not cal and any("within 30 days of the filing" in u["reason"] for u in unparsed)


def test_the_index_keeps_the_two_sponsors_and_the_notice_parser_reads_xml():
    idx = ("487              FT 12662                                    2086969     2025-11-26  edgar/data/2086969/0001445546-25-007838.txt\n"
           "487              Invesco Unit Trusts, Series 2400            1999999     2025-11-26  edgar/data/1999999/0001999999-25-000001.txt\n"
           "24F-2NT          GUGGENHEIM DEFINED PORTFOLIOS, SERIES 2499  2060000     2026-08-20  edgar/data/2060000/0001528621-26-000700.txt\n"
           "10-K             FT 12662                                    2086969     2025-11-26  edgar/data/2086969/0001445546-25-000001.txt\n")
    rows = b.index_rows(idx)
    assert [(r["form"], r["code"], r["cik"]) for r in rows] == [("487", "FT", "2086969"), ("24F-2NT", "GUGG", "2060000")]
    assert b.accession_of(rows[0]["path"]) == "0001445546-25-007838"
    assert b.quarters(dt.date(2023, 7, 1), dt.date(2024, 2, 1)) == [(2023, 3), (2023, 4), (2024, 1)]
    xml = ("<edgarSubmission><lastDayOfFiscalYear>2025-06-30</lastDayOfFiscalYear><aggregateSalePriceOfSecuritiesSold>23900000.00"
           "</aggregateSalePriceOfSecuritiesSold><aggregatePriceOfSecuritiesRedeemedOrRepurchasedInFiscalYear>700000"
           "</aggregatePriceOfSecuritiesRedeemedOrRepurchasedInFiscalYear></edgarSubmission>")
    assert b.parse_notice(xml) == {"fiscal_year_end": dt.date(2025, 6, 30), "sold_usd": 23_900_000.0, "redeemed_usd": 700_000.0}
    assert b.parse_notice("<edgarSubmission><lastDayOfFiscalYear>2025-06-30</lastDayOfFiscalYear></edgarSubmission>") is None


# ------------------------------------------------------------------ the committed files

def _stored(name):
    with open(ROOT / "universes" / name, newline="") as f:
        return list(csv.DictReader(f))


def test_the_stored_calendar_is_well_formed_and_every_row_names_its_filing():
    rows = _stored("uit_terminations_v1.csv")
    cal = sig.read_calendar(rows)                                         # raises on any unreadable row
    assert len({r["trust_key"] for r in cal}) >= 50
    assert {r["sponsor"] for r in rows} <= {"First Trust", "Guggenheim"}
    for r in rows:
        assert r["url"] == f"https://www.sec.gov/Archives/edgar/data/{r['cik']}/{r['accession']}.txt"
        assert dt.date.fromisoformat(r["termination_date"]) >= b.FIRST_TERMINATION
        assert dt.date.fromisoformat(r["filed"]) >= b.FIRST_FILED
        assert (dt.date.fromisoformat(r["termination_date"]) - dt.date.fromisoformat(r["filed"])).days > 30
        assert dt.date.fromisoformat(r["deposit_date"]) < dt.date.fromisoformat(r["termination_date"])
    assert len({(r["accession"], r["trust"], r["symbol"]) for r in rows}) == len(rows)
    for u in _stored("uit_terminations_v1_unparsed.csv"):
        assert u["accession"] and u["reason"] and u["url"].startswith("https://www.sec.gov/Archives/edgar/data/")
    sig.read_notices(_stored("uit_notices_v1.csv"))


def test_both_book_files_load_and_name_the_two_lines():
    for slug, fn in (("uit_termination", sig.all_events), ("uit_termination_big_sale", sig.big_sale)):
        bk = book_mod.load(ROOT / "books" / f"{slug}.json")
        assert bk.signal_fn() is fn and bk.fill == "next_close" and bk.enabled
        assert [p.name for p in bk.panels] == ["px"] and bk.panels[0].required_asof
        assert bk.panels[0].path == uit_px.PANEL
