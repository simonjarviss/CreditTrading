"""The live attribution (scripts/cef/live_attribution.py): its identity, its signs, its refusals.

WHY THESE TESTS
---------------
The attribution splits the paper account's P&L into hold, fill, fees, NAV,
discount and distributions. On 2026-11-02 that split moved the explanation of
the book's -$982.14 from "the signal failed" to "muni NAVs rose under two
shorts". A figure that moves a judgement like that must not rest on a sign
nobody checked. So the fixture below is small enough to work by hand. Two
names, AAA and BBB, go long and short; AAA flips from long to short; CCC is
bought on its own ex-date. Two distributions fall on the flip day, one falls the
day after, and one falls on a market holiday. AAA's first buy fills in two
partial activities. The account's equity is computed independently, as cash
plus positions marked at the close, less the fees, the way the paper account
was measured to behave. It is never computed from the attribution's own
formulas, sign table or fee rates, so the reconciliation test is a real check.

The suite was run against four deliberately wrong copies of the module, one
mutation at a time (2026-11-02). Each copy failed:
  * nav_part with its sign flipped (`-qp * c_p * ...`): 2 failures, the
    hand-computed short and long NAV tests. The identity test still passes, as
    it must, because disc_part absorbs the error;
  * `sell_short` signed +1: 7 failures, among them the reconciliation, the
    short-sign, the flip, the entitlement and the fetch round trip;
  * the distribution charged on q_end instead of q_prev: 1 failure, the
    entitlement test;
  * the fill sign flipped: 4 failures, among them the reconciliation.
That first run caught a weak fixture. Its equity series used the module's own
sign table, so a wrong `sell_short` sign moved both sides and the
reconciliation still passed. The fixture now has its own table
(FIXTURE_SIGN).

The review of 2026-11-02 found four more wrong copies that passed all 29
tests: fills dated in UTC, `cum_qty` read as the quantity (the fixture had
cum_qty == qty, while 218 of the account's 344 fills are partial), and the
data/ guard removed from write_outputs or from fetch (only the helper was
tested). Each has a test below that fails against it, and so do the review's
other findings: the fees, the second distribution source, the git-visible
output directory and the summary's distribution kinds. A test that guards a
write never writes where a broken module could do harm: data/ and the
repository are swapped for tmp_path first.

The fixture's sessions skip Monday 2026-01-19 (Martin Luther King Jr. Day), so an
ex-date or a bar on that date is off the session calendar.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import subprocess
import sys
from fractions import Fraction as F
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.cef import live_attribution as LA  # noqa: E402

D = dt.date
UTC = dt.timezone.utc
PRE = [D(2026, 1, 14), D(2026, 1, 15)]                      # sessions before funding
S0, S1, S2, S3, S4 = (D(2026, 1, 16), D(2026, 1, 20), D(2026, 1, 21),
                      D(2026, 1, 22), D(2026, 1, 23))
SESSIONS = [S0, S1, S2, S3, S4]
NEXT = D(2026, 1, 26)                                       # the session after the last EOD point
HOLIDAY = D(2026, 1, 19)
GRP = {"AAA": "muni", "BBB": "multi", "CCC": "hy"}
# NEXT closes at 16:00 EST = 21:00 UTC. The second source fetched after that can
# call both sources' silence on S4 a zero; one fetched before it cannot.
CHECK_AT = dt.datetime(2026, 1, 27, 12, tzinfo=UTC)

CLOSES = {
    "AAA": {S0: "9.90", S1: "10.10", S2: "10.30", S3: "10.25", S4: "10.00"},
    "BBB": {S0: "20.10", S1: "19.90", S2: "20.10", S3: "19.80", S4: "20.40"},
    "CCC": {S2: "5.10", S3: "5.00", S4: "5.20"},
}
NAVS = {
    "AAA": {S0: "11.00", S1: "11.10", S2: "11.20", S3: "11.20", S4: "11.00"},
    "BBB": {S0: "22.00", S1: "22.00", S2: "22.44", S3: "22.00", S4: "22.22"},
    "CCC": {S2: "6.00", S3: "6.10", S4: "6.05"},
}
# (id, symbol, side, qty, price, NY date, order id, cum_qty, seconds past 20:52 UTC).
# 15:52 ET is 20:52 UTC in January (EST). `qty` is each activity's own increment;
# `cum_qty` is the order's running total, as Alpaca reports partial fills.
FILLS = [
    ("f1a", "AAA", "buy", "60", "10.00", S1, "o-1", "60", 4),     # a partial fill...
    ("f1b", "AAA", "buy", "40", "10.00", S1, "o-1", "100", 5),    # ...and the rest of o-1
    ("f2", "BBB", "sell_short", "50", "20.00", S1, "o-2", "50", 6),
    ("f3", "CCC", "buy", "10", "5.00", S2, "o-3", "10", 4),       # bought on its ex-date
    ("f4", "AAA", "sell", "100", "10.20", S3, "o-4", "100", 4),   # the flip, as two orders
    ("f5", "AAA", "sell_short", "50", "10.20", S3, "o-5", "50", 5),
    ("f6", "BBB", "buy", "50", "20.50", S4, "o-6", "50", 4),      # the short is closed
]
DISTS = [
    ("d1", "AAA", S3, "0.05"),      # held long 100 into S3 -> credited +5.00
    ("d2", "BBB", S3, "0.10"),      # held short 50 into S3 -> charged -5.00
    ("d3", "AAA", S4, "0.04"),      # short 50 after the flip -> charged -2.00
    ("d4", "CCC", S2, "0.02"),      # bought on the ex-date -> nothing
]


def raw_fills():
    return [{"id": i, "activity_type": "FILL", "symbol": s, "side": side, "qty": q,
             "price": px, "transaction_time": f"{d.isoformat()}T20:52:{sec:02d}.123456Z",
             "type": "partial_fill" if i == "f1a" else "fill", "order_id": oid,
             "cum_qty": cq, "leaves_qty": "0" if i != "f1a" else "40",
             "order_status": "filled" if i != "f1a" else "partially_filled"}
            for i, s, side, q, px, d, oid, cq, sec in FILLS]


FIXTURE_SIGN = {"buy": 1, "sell": -1, "sell_short": -1}   # the fixture's own, not LA.SIDE_SIGN
FIXTURE_SEC = F("0.0000206")                              # the fixture's own, not LA's constants
FIXTURE_CAT = F("0.000003")


def fixture_fees(d):
    """The session's fees, computed here from the fixture's own rates: SEC on the
    value sold plus CAT on every share, each summed over the session and rounded
    up to the cent (the rule the paper account was measured to follow)."""
    sold = sum((int(q) * F(px) for _, _, side, q, px, fd, *_ in FILLS
                if fd == d and side != "buy"), F(0))
    shares = sum(int(q) for _, _, _, q, _, fd, *_ in FILLS if fd == d)
    up = lambda x: F(math.ceil(x * 100), 100)               # noqa: E731
    return up(FIXTURE_SEC * sold) + up(FIXTURE_CAT * shares)


def equity_series():
    """Cash plus positions at the close, less the fees, per session: how the paper
    account was measured to mark equity. Independent of the attribution's
    formulas, sign table and fee constants, so a wrong one in the module cannot
    also move the fixture."""
    cash, q, out = F(100000), {}, []
    for d in SESSIONS:
        for _, s, side, qty, px, fd, *_ in FILLS:
            if fd == d:
                sq = FIXTURE_SIGN[side] * int(qty)
                cash -= sq * F(px)
                q[s] = q.get(s, 0) + sq
        cash -= fixture_fees(d)
        out.append((d, cash + sum(x * F(CLOSES[s][d]) for s, x in q.items() if x)))
    return out


def table(src):
    return {(s, d): F(v) for s, days in src.items() for d, v in days.items()}


def check_rows(rows=None):
    """The second distribution source: by default it lists what Alpaca lists."""
    rows = [(s, d, a) for _, s, d, a in DISTS] if rows is None else rows
    return LA.parse_dist_check(pd.DataFrame(
        [{"ticker": s, "ex_date": d.isoformat(), "amount": a} for s, d, a in rows],
        columns=["ticker", "ex_date", "amount"]))


def inputs(**over):
    kw = dict(fills=LA.parse_fills(raw_fills()), eod=equity_series(), closes=table(CLOSES),
              navs=table(NAVS),
              dists=LA.parse_distributions([{"id": i, "symbol": s, "ex_date": d.isoformat(),
                                             "amount": a, "kind": "cash_dividend"}
                                            for i, s, d, a in DISTS]),
              corp=[], grp=dict(GRP), flat_start=S0, fills_from=PRE[0],
              corp_types=LA.SPLIT_TYPES, dist_kinds=LA.DIST_KINDS,
              dist_check=check_rows(), dist_check_at=CHECK_AT, next_session=NEXT)
    kw.update(over)
    return LA.Inputs(**kw)


def row(res, s, d):
    r = res.name_day[(res.name_day["symbol"] == s) & (res.name_day["date"] == d)]
    assert len(r) == 1, (s, d, len(r))
    return r.iloc[0]


def daily(res, col):
    return res.daily.set_index("date")[col].to_dict()


# --- the identity and the reconciliation -------------------------------------

def test_nav_plus_disc_equals_hold_exactly():
    res = LA.attribute(inputs())
    nd = res.name_day
    assert len(nd) > 0
    for r in nd.itertuples():
        assert isinstance(r.hold, F) and isinstance(r.nav_part, F)
        assert r.nav_part + r.disc_part == r.hold          # exact, not approximately
    assert sum(nd["nav_part"]) + sum(nd["disc_part"]) == sum(nd["hold"])


def test_daily_sum_matches_equity_change_exactly():
    res = LA.attribute(inputs())
    eq = dict(equity_series())
    assert list(res.daily["date"]) == SESSIONS[1:]
    assert all(r == 0 for r in res.daily["residual"])
    assert sum(res.daily["rebuilt"]) == eq[S4] - eq[S0]
    assert not [ln for ln in LA.reconcile_lines(res.daily) if ln.startswith("WARN")]


def test_warn_line_on_a_residual_above_threshold():
    eod = [(d, e + (10 if d == S2 else 0)) for d, e in equity_series()]
    res = LA.attribute(inputs(eod=eod))
    r = res.daily.set_index("date")["residual"]
    assert r[S2] == 10 and r[S3] == -10
    warns = [ln for ln in LA.reconcile_lines(res.daily) if ln.startswith("WARN")]
    assert len(warns) == 2 and warns[0].startswith(f"WARN {S2}")


# --- fees: paper charged them after all (review 2026-11-02) -------------------

def test_fees_by_hand():
    res = LA.attribute(inputs())
    # S1: sold 50 x 20.00 = 1,000 -> SEC 0.0206 -> 0.03; 150 shares -> CAT 0.00045 -> 0.01.
    # S2: nothing sold; 10 shares -> 0.01. S3: sold 150 x 10.20 = 1,530 -> 0.031518 -> 0.04,
    # plus 0.01. S4: nothing sold; 50 shares -> 0.01.
    assert daily(res, "fees") == {S1: F("-0.04"), S2: F("-0.01"), S3: F("-0.05"), S4: F("-0.01")}
    assert daily(res, "sold_usd") == {S1: F(1000), S2: 0, S3: F(1530), S4: 0}
    assert daily(res, "shares_traded") == {S1: 150, S2: 10, S3: 150, S4: 50}
    for r in res.daily.itertuples():
        assert r.rebuilt == r.hold + r.fill + r.fees


def test_session_fees_rate_and_rounding():
    def fill(q, px):
        return LA.Fill(id="x", symbol="X", date=S1, time="t", signed_qty=q, price=F(px))
    # $100,000 sold and 10,000 shares: SEC 2.06 exactly, CAT 0.03 exactly.
    assert LA.session_fees([fill(-10000, "10")]) == (F("-2.09"), F(100000), 10000)
    # Rounded UP per session, not per fill: two $1 sales owe 0.01, not 0.02.
    assert LA.session_fees([fill(-1, "1"), fill(-1, "1")])[0] == F("-0.02")   # SEC 0.01 + CAT 0.01
    assert LA.session_fees([fill(1, "1")])[0] == F("-0.01")                   # a buy: CAT only
    assert LA.session_fees([]) == (0, 0, 0)


def test_fee_rates_match_real_money_costs():
    from scripts.cef import real_money_costs as RMC
    assert LA.SEC_FEE_PER_USD_SOLD == F(str(RMC.SEC_FEE_PER_DOLLAR_SOLD))
    assert LA.CAT_FEE_PER_SHARE == F(str(RMC.CAT_FEE_PER_SHARE))


def test_summary_does_not_say_paper_charges_no_fees(tmp_path):
    res = LA.attribute(inputs())
    text = LA.write_outputs(res, tmp_path / "out")["summary"].read_text()
    assert "no fees" not in text and "fill + fees" in text
    assert "rebuilt: hold + fill + fees" in text
    assert "fees (modelled)" in LA.report(res)


# --- signs, by hand ------------------------------------------------------------

def test_short_side_signs():
    res = LA.attribute(inputs())
    b = row(res, "BBB", S2)                 # short 50; price 19.90 -> 20.10; NAV +2%
    assert b.side == "short" and b.q_prev == -50
    assert b.hold == F("-10")               # -50 * 0.20
    assert b.nav_part == F("-19.90")        # -50 * 19.90 * 0.02
    assert b.disc_part == F("9.90")         # the discount widened under a short: a gain
    b3 = row(res, "BBB", S3)                # price falls under the short: a gain
    assert b3.hold == F("15") and b3.nav_part > 0


def test_long_nav_part_by_hand():
    res = LA.attribute(inputs())
    a = row(res, "AAA", S2)                 # long 100; NAV 11.10 -> 11.20
    assert a.side == "long"
    assert a.hold == F("20")
    assert a.nav_part == 100 * F("10.10") * (F("11.20") / F("11.10") - 1)
    assert a.nav_part > 0


def test_fill_against_the_close():
    res = LA.attribute(inputs())
    assert row(res, "AAA", S1).fill == F("10")       # bought 60 + 40 at 10.00, closed 10.10
    assert row(res, "BBB", S1).fill == F("5")        # shorted 50 at 20.00, closed 19.90
    assert row(res, "AAA", S3).fill == F("-7.5")     # sold 150 at 10.20, closed 10.25
    assert row(res, "AAA", S1).hold == 0             # opened that day: nothing held into it
    assert row(res, "BBB", S1).side == "short"       # a name opened that day takes its side


def test_flip_long_to_short():
    res = LA.attribute(inputs())
    a3, a4 = row(res, "AAA", S3), row(res, "AAA", S4)
    assert (a3.q_prev, a3.q_end, a3.side) == (100, -50, "long")
    assert (a4.q_prev, a4.side) == (-50, "short")
    assert a4.hold == F("12.5")                      # -50 * (10.00 - 10.25)
    pos = res.positions_end.set_index("symbol")["qty"].to_dict()
    assert pos == {"AAA": -50, "CCC": 10}            # BBB closed on S4


def test_partial_fills_count_qty_not_cum_qty():
    fs = {f.id: f for f in LA.parse_fills(raw_fills())}
    assert (fs["f1a"].signed_qty, fs["f1b"].signed_qty) == (60, 40)   # cum_qty says 60, then 100
    assert row(LA.attribute(inputs()), "AAA", S1).q_end == 100


def test_fill_is_dated_in_new_york_not_utc():
    raw = dict(raw_fills()[0], id="late", transaction_time="2026-01-21T01:15:00Z")
    assert LA.parse_fills([raw])[0].date == S1           # 20:15 EST on 01-20; 01-21 in UTC
    raw = dict(raw, transaction_time="2026-07-01T00:30:00.5Z")
    assert LA.parse_fills([raw])[0].date == D(2026, 6, 30)   # 20:30 EDT


# --- distributions: the holder at the previous close is entitled --------------------

def test_ex_date_entitlement():
    res = LA.attribute(inputs())
    assert row(res, "AAA", S3).dist == F("5")        # long 100 at S2's close; sold on S3
    assert row(res, "BBB", S3).dist == F("-5")       # short pays the lender
    assert row(res, "AAA", S4).dist == F("-2")       # short 50 after the flip
    assert row(res, "CCC", S2).dist == 0             # bought on its ex-date: trades ex
    ev = res.events.set_index("id")
    assert ev.loc["d4", "q_prev"] == 0 and ev.loc["d1", "q_prev"] == 100
    assert sum(res.daily["dist"]) == F("-2")
    # No event in either source, the second current: every other name-day is zero.
    others = res.name_day[~res.name_day.apply(
        lambda r: (r.symbol, r.date) in {(s, d) for _, s, d, _ in DISTS}, axis=1)]
    assert all(x == 0 for x in others["dist"])
    assert not res.dist_unmeasured


# --- distributions: Alpaca's silence is not a zero (review 2026-11-02) ----------

def test_alpaca_silence_is_not_a_zero():
    # The second source lists a BBB ex-date on S2 that Alpaca does not (BBB is short 50).
    res = LA.attribute(inputs(dist_check=check_rows([(s, d, a) for _, s, d, a in DISTS]
                                                    + [("BBB", S2, "0.07")])))
    b = row(res, "BBB", S2)
    assert b.dist is None and "Alpaca's silence is not a zero" in b.dist_status
    assert daily(res, "dist")[S2] is None and daily(res, "dist")[S3] == 0   # S3: +5 - 5
    assert LA.totals(res)["dist"] is None and LA.totals(res)["with_dist"] is None
    assert [(d, s) for d, s, *_ in res.dist_unmeasured] == [(S2, "BBB")]
    assert any("UNMEASURED" in g for g in res.gaps)


def test_one_silent_source_is_not_two():
    # The second source has no row for CCC at all: CCC held into S3 and S4 has only
    # Alpaca's silence behind a zero.
    res = LA.attribute(inputs(dist_check=check_rows([(s, d, a) for _, s, d, a in DISTS
                                                     if s != "CCC"])))
    assert [(d, s) for d, s, *_ in res.dist_unmeasured] == [(S3, "CCC"), (S4, "CCC")]
    assert "only one source is silent" in row(res, "CCC", S3).dist_status
    assert row(res, "CCC", S2).dist == 0             # not held into S2: not entitled


def test_a_zero_needs_a_current_second_source():
    # Fetched before the close of NEXT (21:00 UTC): S4's silences cannot be zeros yet.
    res = LA.attribute(inputs(dist_check_at=dt.datetime(2026, 1, 26, 20, tzinfo=UTC)))
    assert [(d, s) for d, s, *_ in res.dist_unmeasured] == [(S4, "BBB"), (S4, "CCC")]
    assert row(res, "AAA", S4).dist == F("-2")       # Alpaca lists it: measured
    assert daily(res, "dist")[S3] == 0               # S3 is current
    # And without the session after the last point, the last point cannot be judged.
    res2 = LA.attribute(inputs(next_session=None))
    assert [(d, s) for d, s, *_ in res2.dist_unmeasured] == [(S4, "BBB"), (S4, "CCC")]


def test_no_second_source_is_unmeasured():
    res = LA.attribute(inputs(dist_check=None, dist_check_at=None))
    held_silent = res.name_day[(res.name_day["q_prev"] != 0) & ~res.name_day.apply(
        lambda r: (r.symbol, r.date) in {(s, d) for _, s, d, _ in DISTS}, axis=1)]
    assert len(held_silent) and all(x is None for x in held_silent["dist"])
    assert row(res, "AAA", S3).dist == F("5")        # Alpaca's record still counts


def test_sources_disagree_or_round():
    far = [(s, d, "0.06" if s == "AAA" and d == S3 else a) for _, s, d, a in DISTS]
    res = LA.attribute(inputs(dist_check=check_rows(far)))
    assert row(res, "AAA", S3).dist is None and "disagree" in row(res, "AAA", S3).dist_status
    near = [(s, d, "0.0504" if s == "AAA" and d == S3 else a) for _, s, d, a in DISTS]
    res = LA.attribute(inputs(dist_check=check_rows(near)))
    assert row(res, "AAA", S3).dist == F("5")        # within 0.0005: Alpaca's amount, exactly


def test_unmeasured_prints_as_unmeasured_never_zero(tmp_path):
    res = LA.attribute(inputs(dist_check=check_rows([(s, d, a) for _, s, d, a in DISTS]
                                                    + [("BBB", S2, "0.07")])))
    by_name = LA.group_table(res.name_day, ["symbol", "grp"]).set_index("symbol")
    assert math.isnan(by_name.loc["BBB", "dist"]) and math.isnan(by_name.loc["BBB", "with_dist"])
    assert by_name.loc["AAA", "dist"] == 3.0          # +5 - 2, all measured
    text = LA.write_outputs(res, tmp_path / "o")["summary"].read_text()
    assert "| UNMEASURED |" in text and "UNMEASURED" in LA.report(res)


def test_summary_kinds_come_from_the_cache(tmp_path):
    res = LA.attribute(inputs(dist_kinds=("cash_dividend",)))
    text = LA.write_outputs(res, tmp_path / "o")["summary"].read_text()
    assert "not credited by paper (cash_dividend)" in text


def test_periods_split_after_the_equity_peak():
    res = LA.attribute(inputs())
    eq = dict(equity_series())
    # By hand: 100,000 / 100,015 / 100,026 / 100,027.50 / 100,007 before fees, and
    # fees to date 0.04 / 0.05 / 0.10 / 0.11 (test_fees_by_hand) -> the peak is S3.
    assert [eq[d] for d in SESSIONS] == [F(100000), F("100014.96"), F("100025.95"),
                                         F("100027.40"), F("100006.89")]
    assert [(p[1], p[2]) for p in res.periods] == [(S1, S3), (S4, S4)]
    assert "peak on 2026-01-22" in res.period_rule
    res2 = LA.attribute(inputs(), breaks=[S3, S3])
    assert [(p[1], p[2]) for p in res2.periods] == [(S1, S2), (S3, S4)]
    with pytest.raises(LA.AttributionError, match="a break must be a session"):
        LA.attribute(inputs(), breaks=[HOLIDAY])


def test_capital_gains_not_queried_is_a_stated_gap():
    res = LA.attribute(inputs(dist_kinds=("cash_dividend",)))
    assert res.gaps and "capital-gains" in res.gaps[0]


# --- refusals ------------------------------------------------------------------

def _drop(tbl, key):
    t = dict(tbl)
    del t[key]
    return t


def test_raises_on_missing_close_for_a_held_name():
    with pytest.raises(LA.AttributionError, match=f"missing close for AAA on {S2}"):
        LA.attribute(inputs(closes=_drop(table(CLOSES), ("AAA", S2))))


def test_a_nan_close_is_missing_not_filled():
    closes = _drop(table(CLOSES), ("BBB", S2))
    with pytest.raises(LA.AttributionError, match="missing close for BBB.*'nan'"):
        LA.attribute(inputs(closes=closes, bad_closes={("BBB", S2): "nan"}))


def test_raises_on_missing_nav_on_a_held_name_day():
    with pytest.raises(LA.AttributionError, match=f"missing NAV for BBB on {S2}"):
        LA.attribute(inputs(navs=_drop(table(NAVS), ("BBB", S2))))
    with pytest.raises(LA.AttributionError, match=f"missing NAV for AAA on {S1}"):
        LA.attribute(inputs(navs=_drop(table(NAVS), ("AAA", S1))))   # the previous NAV


def test_a_nav_is_not_needed_on_a_day_nothing_is_held():
    # AAA and BBB open on S1, so nothing needs their S0 NAV; BBB is closed on S4,
    # so nothing needs its S4 NAV... except hold on S4, which does (held into S4).
    LA.attribute(inputs(navs=_drop(_drop(table(NAVS), ("AAA", S0)), ("BBB", S0))))
    with pytest.raises(LA.AttributionError, match=f"missing NAV for BBB on {S4}"):
        LA.attribute(inputs(navs=_drop(table(NAVS), ("BBB", S4))))


def test_raises_on_fill_on_a_day_with_no_bar():
    with pytest.raises(LA.AttributionError, match="fill f3 in CCC .*no bar for that day"):
        LA.attribute(inputs(closes=_drop(table(CLOSES), ("CCC", S2))))


def test_raises_on_duplicate_activity_ids():
    raw = raw_fills()
    raw.append(dict(raw[0]))
    with pytest.raises(LA.AttributionError, match="duplicate FILL activity ids.*f1a"):
        LA.parse_fills(raw)


def test_raises_on_a_split_in_the_window():
    split = {"id": "x1", "type": "reverse_split", "date": S3, "parties": [("AAA", "subject")]}
    with pytest.raises(LA.AttributionError, match="share-count corporate action.*reverse_split"):
        LA.attribute(inputs(corp=[split]))
    # A split on a name never traded, or outside the window, is not ours.
    LA.attribute(inputs(corp=[dict(split, parties=[("ZZZ", "subject")]),
                              dict(split, date=D(2026, 2, 2))]))


def test_raises_when_splits_were_not_queried():
    with pytest.raises(LA.AttributionError, match="cannot show that no split"):
        LA.attribute(inputs(corp_types=("cash_merger",)))


def test_raises_when_the_flat_start_is_not_shown():
    with pytest.raises(LA.AttributionError, match="cannot assert a flat start"):
        LA.attribute(inputs(fills_from=S1))
    raw = raw_fills()
    raw[0] = dict(raw[0], transaction_time=f"{PRE[1].isoformat()}T20:52:00Z")
    with pytest.raises(LA.AttributionError, match="before flat_start"):
        LA.attribute(inputs(fills=LA.parse_fills(raw)))


def test_raises_on_a_fill_at_the_first_eod_point():
    raw = raw_fills()
    raw[0] = dict(raw[0], transaction_time=f"{S0.isoformat()}T20:52:00Z")
    with pytest.raises(LA.AttributionError, match="on or before the first EOD point"):
        LA.attribute(inputs(fills=LA.parse_fills(raw)))


def test_raises_on_ex_date_off_the_session_calendar():
    d = LA.parse_distributions([{"id": "h", "symbol": "AAA", "ex_date": HOLIDAY.isoformat(),
                                 "amount": "0.05", "kind": "cash_dividend"}])
    with pytest.raises(LA.AttributionError, match="is not a session of the EOD history"):
        LA.attribute(inputs(dists=d))
    with pytest.raises(LA.AttributionError, match="second distribution source: AAA ex 2026-01-19"):
        LA.attribute(inputs(dist_check=check_rows([("AAA", HOLIDAY, "0.05")])))


def test_raises_on_a_bar_the_eod_history_lacks():
    with pytest.raises(LA.AttributionError, match="fall on no session"):
        LA.attribute(inputs(closes=table(CLOSES) | {("AAA", HOLIDAY): F("10.2")}))


def test_raises_on_a_symbol_with_no_grp():
    with pytest.raises(LA.AttributionError, match=r"\['CCC'\] have no grp"):
        LA.attribute(inputs(grp={"AAA": "muni", "BBB": "multi"}))


def test_raises_on_identical_distribution_records():
    with pytest.raises(LA.AttributionError, match="identical distribution records"):
        LA.parse_distributions([{"id": i, "symbol": "AAA", "ex_date": "2026-01-22",
                                 "amount": "0.05", "kind": "cash_dividend"} for i in ("a", "b")])


def test_fills_after_asof_are_excluded_and_counted():
    res = LA.attribute(inputs(), asof=S3)
    assert res.excluded_after_asof == 1 and res.daily["date"].max() == S3


# --- the cache round trip, and fetch against a fake client ---------------------

class FakeClient:
    """The read methods `fetch` calls, answering from the fixture. No network."""

    def __init__(self):
        self.calls = []

    def eod_equity_history(self, start, end):
        self.calls.append("eod")
        return [(d, float(e), dt.datetime.combine(d + dt.timedelta(days=1), dt.time(0), UTC))
                for d, e in equity_series() if start <= d <= end]

    def calendar(self, start, end):
        self.calls.append("calendar")
        return [{"date": d} for d in PRE + SESSIONS + [NEXT] if start <= d <= end]

    def activities_fills(self, date):
        self.calls.append("fills")
        return [a for a in raw_fills() if a["transaction_time"][:10] == date.isoformat()]

    def distributions(self, symbols, start, end):
        return [{"id": i, "symbol": s, "ex_date": d, "amount": float(a), "kind": "cash_dividend",
                 "special": False, "sub_type": None} for i, s, d, a in DISTS if s in symbols]

    def corporate_actions(self, symbols, start, end):
        return []

    def _get(self, base, path, params):
        assert path == "/v2/stocks/bars" and params["feed"] == "sip" and params["adjustment"] == "raw"
        bars = {s: [{"t": f"{d.isoformat()}T05:00:00Z", "o": float(c), "h": float(c), "l": float(c),
                     "c": float(c), "v": 1000} for d, c in sorted(CLOSES[s].items())]
                for s in params["symbols"].split(",")}
        return {"bars": bars, "next_page_token": None}


def fake_navs(symbols, start, end):
    rows = [{"date": d.isoformat(), "ticker": s, "nav": v}
            for s in symbols for d, v in NAVS[s].items() if start <= d <= end]
    return pd.DataFrame(rows, columns=["date", "ticker", "nav"]), []


def fake_dividends(symbols):
    rows = [{"ticker": s, "ex_date": d.isoformat(), "amount": repr(float(a))}
            for _, s, d, a in DISTS if s in symbols]
    return pd.DataFrame(rows, columns=["ticker", "ex_date", "amount"]), []


def _fetch(cache, now=CHECK_AT, client=None, since=PRE[0]):
    return LA.fetch(cache, since=since, asof=S4, client=FakeClient() if client is None else client,
                    nav_fetcher=fake_navs, dist_check_fetcher=fake_dividends, now=now)


def test_fetch_then_analyse_reproduces_the_in_memory_result(tmp_path):
    man = _fetch(tmp_path / "cache")
    assert man["flat_start"]["date"] == S0.isoformat()
    assert man["eod"]["next_session"] == NEXT.isoformat()
    assert man["distributions_check"]["fetched_at_utc"] == CHECK_AT.isoformat()
    assert "reverse_split" in man["corporate_actions"]["types"]
    res, paths = LA.analyse(tmp_path / "cache", tmp_path / "out", grp=dict(GRP))
    mem = LA.attribute(inputs())
    for k in LA.MONEY:
        assert sum(res.name_day[k]) == sum(mem.name_day[k]), k
    assert list(res.daily["fees"]) == list(mem.daily["fees"])
    assert all(r == 0 for r in res.daily["residual"])
    assert not res.dist_unmeasured
    for k in ("summary", "name_day", "daily", "by_name", "by_side", "by_grp", "by_period"):
        assert paths[k].is_file() and paths[k].parent == tmp_path / "out" / S4.isoformat()
    text = paths["summary"].read_text()
    assert "nav_part" in text and "NAV alignment" in text
    assert json.loads((tmp_path / "cache" / "manifest.json").read_text())["fills"]["n"] == len(FILLS)


def test_load_cache_refuses_a_cache_without_the_second_source(tmp_path):
    _fetch(tmp_path / "c")
    (tmp_path / "c" / "distributions_check.csv").unlink()
    with pytest.raises(LA.AttributionError, match="files missing.*distributions_check.csv"):
        LA.load_cache(tmp_path / "c", grp=dict(GRP))
    _fetch(tmp_path / "d")
    man = json.loads((tmp_path / "d" / "manifest.json").read_text())
    man["eod"].pop("next_session")
    (tmp_path / "d" / "manifest.json").write_text(json.dumps(man))
    with pytest.raises(LA.AttributionError, match="eod.next_session"):
        LA.load_cache(tmp_path / "d", grp=dict(GRP))


def test_fetch_refuses_when_the_flat_start_cannot_be_shown(tmp_path):
    with pytest.raises(LA.AttributionError, match="pass an earlier --since"):
        _fetch(tmp_path / "c", since=S0)
    assert not (tmp_path / "c").exists()


class FundedEarlyClient(FakeClient):
    """The real cef account's shape (read 2026-11-02): funded with $100,000 months
    before its first fill, so every --since already has a funded EOD point. `pre`
    funded sessions are prepended at `pre_equity` (a list, one per session)."""

    def __init__(self, pre_equity):
        super().__init__()
        self.pre = [(D(2026, 1, 2) + dt.timedelta(days=i), F(e)) for i, e in enumerate(pre_equity)]

    def eod_equity_history(self, start, end):
        self.calls.append("eod")
        series = self.pre + equity_series()     # S0 is funded and has no fill
        return [(d, float(e), dt.datetime.combine(d + dt.timedelta(days=1), dt.time(0), UTC))
                for d, e in series if start <= d <= end]

    def calendar(self, start, end):
        self.calls.append("calendar")
        days = [d for d, _ in self.pre] + SESSIONS + [NEXT]
        return [{"date": d} for d in days if start <= d <= end]


def test_fetch_accepts_a_flat_start_shown_by_constant_equity(tmp_path):
    """Funded before --since: flat is shown by equity unchanged to the cent on
    every session before the first fill (a held name would be marked), with no
    fill from --since until then. The first build demanded an unfunded session
    and so could never run on the real account (2026-11-02)."""
    client = FundedEarlyClient(["100000"] * LA.MIN_FLAT_SESSIONS)
    since = client.pre[0][0]
    man = _fetch(tmp_path / "c", client=client, since=since)
    assert man["flat_start"]["date"] == since.isoformat()
    assert "unchanged" in man["flat_start"]["evidence"]
    res, _ = LA.analyse(tmp_path / "c", tmp_path / "out", grp=dict(GRP))
    assert all(r == 0 for r in res.daily["residual"])
    mem = LA.attribute(inputs())
    for k in LA.MONEY:
        assert sum(res.name_day[k]) == sum(mem.name_day[k]), k


def test_fetch_refuses_a_flat_start_when_equity_moved_before_the_first_fill(tmp_path):
    client = FundedEarlyClient(["100000"] * (LA.MIN_FLAT_SESSIONS - 1) + ["100000.01"])
    with pytest.raises(LA.AttributionError, match="equity moved.*pass an earlier --since"):
        _fetch(tmp_path / "c", client=client, since=client.pre[0][0])
    assert not (tmp_path / "c").exists()


def test_fetch_refuses_too_few_constant_sessions(tmp_path):
    client = FundedEarlyClient(["100000"] * (LA.MIN_FLAT_SESSIONS - 2))   # + S0: one short
    with pytest.raises(LA.AttributionError, match="pass an earlier --since"):
        _fetch(tmp_path / "c", client=client, since=client.pre[0][0])
    assert not (tmp_path / "c").exists()


def test_fetch_refuses_an_unfinished_eod_point(tmp_path):
    with pytest.raises(LA.AttributionError, match="not final yet"):
        _fetch(tmp_path / "c", now=dt.datetime(2026, 1, 23, 22, tzinfo=UTC))


# --- where it writes: never data/, never anywhere git can see -------------------

def test_never_writes_under_data():
    with pytest.raises(LA.AttributionError, match="under data/"):
        LA._refuse_data_dir(LA.DATA_DIR / "cef" / "live_attribution")


@pytest.fixture
def fake_data_dir(tmp_path, monkeypatch):
    """data/ swapped for an empty tmp directory, so that a module whose guard is
    broken writes there and not into the real panels."""
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setattr(LA, "DATA_DIR", d)
    return d


def test_write_outputs_refuses_data_dir(fake_data_dir):
    res = LA.attribute(inputs())
    with pytest.raises(LA.AttributionError, match="under data/"):
        LA.write_outputs(res, fake_data_dir / "cef" / "out")
    assert not any(fake_data_dir.iterdir())


def test_fetch_refuses_data_dir_before_any_call(fake_data_dir):
    client = FakeClient()
    with pytest.raises(LA.AttributionError, match="under data/"):
        _fetch(fake_data_dir / "cache", client=client)
    assert client.calls == [] and not any(fake_data_dir.iterdir())


def test_default_directories_are_ignored_by_git():
    # The real repository, read-only: every file either step writes by default, both books.
    files = ([(LA.DEFAULT_CACHE / n) for n in LA.FILES.values()]
             + [(LA.DEFAULT_OUT / "2026-10-30" / f"{k}.csv") for k in LA.OUTPUT_TABLES]
             + [LA.DEFAULT_OUT / "2026-10-30" / "summary.md"]
             + [(LA.DEFAULT_CACHE_C4 / n) for n in LA.FILES.values()]
             + [LA.DEFAULT_OUT_C4 / "2026-10-30" / "summary.md"])
    rel = [p.relative_to(REPO).as_posix() for p in files]
    r = subprocess.run(["git", "-C", str(REPO), "check-ignore", *rel], capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr
    assert sorted(set(rel) - set(r.stdout.splitlines())) == []


@pytest.fixture
def sandbox_repo(tmp_path, monkeypatch):
    """A throwaway git repository standing in for this one: `ignored/` is ignored,
    `visible/` is not. A module whose git guard is broken writes in here."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / ".gitignore").write_text("ignored/\n")
    monkeypatch.setattr(LA, "REPO", root)
    return root


def test_refuses_to_write_where_git_can_see(sandbox_repo, tmp_path):
    res = LA.attribute(inputs())
    with pytest.raises(LA.AttributionError, match="git can see them"):
        LA.write_outputs(res, sandbox_repo / "visible" / "2026-01-23")
    assert not (sandbox_repo / "visible").exists()
    paths = LA.write_outputs(res, sandbox_repo / "ignored" / "2026-01-23")
    assert paths["summary"].is_file()
    LA.write_outputs(res, tmp_path / "outside")          # outside the repository: allowed


def test_fetch_refuses_a_cache_git_can_see(sandbox_repo):
    client = FakeClient()
    with pytest.raises(LA.AttributionError, match="git can see them"):
        _fetch(sandbox_repo / "visible_cache", client=client)
    assert client.calls == [] and not (sandbox_repo / "visible_cache").exists()
    _fetch(sandbox_repo / "ignored" / "cache")


# --- book c4 (team lead, 2026-11-09) ---------------------------------------------------

FAMILIES = {"AAA": "equity_domestic", "BBB": "preferred", "CCC": "multi_asset"}


def test_the_c4_groups_are_the_specs_family_map():
    frozen = json.loads((REPO / "ops/specs/c4_families.frozen.json").read_text())["frozen"]
    fam = LA.load_groups_for("c4")
    assert fam == frozen["level_signal"]["family_of"] and "ADX" in fam
    with pytest.raises(LA.AttributionError, match="unknown book"):
        LA.load_groups_for("xyz")


class FakeYF:
    """yfinance with the network replaced: records every Ticker asked for and returns a row a
    day, or none when the symbol is in `empty`."""

    def __init__(self, empty=()):
        self.asked = []
        self.empty = set(empty)

    def Ticker(self, symbol):
        self.asked.append(symbol)
        return self

    def history(self, start, end, auto_adjust):
        assert auto_adjust is False                  # the raw Close, as fetch_daily reads it
        if self.asked[-1] in self.empty:
            return pd.DataFrame({"Close": []})
        return pd.DataFrame({"Close": [10.0, 10.1]}, index=pd.DatetimeIndex(["2026-11-02", "2026-11-03"]))


@pytest.fixture
def fake_yf(monkeypatch):
    f = FakeYF()
    monkeypatch.setitem(sys.modules, "yfinance", f)
    return f


def test_c4_navs_are_read_at_the_maps_symbols_not_the_core_x_rule(fake_yf):
    """15 of C4's 74 funds are not on the X rule (the review's finding, 2026-11-09). Asking
    XADXX gets yfinance's nothing, and the name's split is then UNMEASURED for ever. Fails on
    the parent commit, which asked the X rule of every name."""
    frame, empty = LA.yf_navs(["ADX", "TY", "BME"], D(2026, 11, 2), D(2026, 11, 3), book="c4")
    assert fake_yf.asked == ["XADEX", "XBMEX", "XTYCX"]          # sorted by price ticker; the map's symbols
    assert "XADXX" not in fake_yf.asked and "XTYX" not in fake_yf.asked
    assert set(frame["ticker"]) == {"ADX", "TY", "BME"} and empty == []      # labelled by the price ticker


def test_the_core_keeps_the_x_rule_by_default(fake_yf):
    """Pin (passes before and after): the core's fetch asks exactly what it always did."""
    LA.yf_navs(["PDI", "AWF"], D(2026, 11, 2), D(2026, 11, 3))
    assert fake_yf.asked == ["XAWFX", "XPDIX"]


def test_a_c4_name_the_map_lacks_raises_naming_it(fake_yf):
    with pytest.raises(LA.AttributionError, match="ZZZZ") as e:
        LA.yf_navs(["ADX", "ZZZZ"], D(2026, 11, 2), D(2026, 11, 3), book="c4")
    assert "XZZZZX" not in str(e.value) and fake_yf.asked == []        # the X rule is not tried for it


def test_the_c4_nav_map_copy_equals_data_books():
    """The licence for the copy (`c4_nav_symbols` docstring): data_books cannot be imported
    from the job's closure, so the two read the same committed file and must agree."""
    from scripts.cef import data_books as DB
    assert LA.c4_nav_symbols() == DB.c4_nav_symbols()
    assert sum(1 for t, s in LA.c4_nav_symbols().items() if s != f"X{t}X") == 15


@pytest.mark.parametrize("rows,match", [
    ("ticker,nav_symbol\nADX,XADEX\nADX,XADEX\n", "listed twice"),
    ("ticker,nav_symbol\nADX,\n", "empty or is the price ticker"),
    ("ticker,nav_symbol\nADX,ADX\n", "empty or is the price ticker"),
    ("ticker,other\nADX,XADEX\n", "needs columns"),
    ("ticker,nav_symbol\nADX,XADEX\n", "does not cover"),
], ids=["dup", "empty", "self", "columns", "coverage"])
def test_a_bad_c4_nav_map_raises(tmp_path, rows, match):
    bad = tmp_path / "map.csv"
    bad.write_text(rows)
    with pytest.raises(LA.AttributionError, match=match):
        LA.c4_nav_symbols(bad)


def test_c4_fetch_reads_the_map_and_says_so_in_the_manifest(tmp_path, monkeypatch, fake_yf):
    """`fetch` with no NAV source injected: book c4 reaches yf_navs for book c4, and the
    manifest names the map. FakeClient's fills are AAA, BBB and CCC, so the map is swapped for
    a small one. Fails on the parent commit (no such book argument reaches yf_navs)."""
    uni = tmp_path / "u.csv"
    uni.write_text("ticker,nav_symbol\nAAA,XAAPX\nBBB,XBBQX\nCCC,XCCRX\n")
    monkeypatch.setattr(LA, "C4_NAV_MAP", uni)
    monkeypatch.setattr(LA, "load_groups_for", lambda book: dict(FAMILIES))
    LA.fetch(tmp_path / "c4", since=PRE[0], asof=S4, client=FakeClient(), dist_check_fetcher=fake_dividends,
             now=CHECK_AT, book="c4")
    assert set(fake_yf.asked) == {"XAAPX", "XBBQX", "XCCRX"}
    man = json.loads((tmp_path / "c4" / LA.FILES["manifest"]).read_text())
    assert "u.csv" in man["nav"]["source"] and "X{tk}X" not in man["nav"]["source"]


def test_load_cache_reads_the_book_from_the_manifest_and_c4_fetch_needs_c4_keys(tmp_path, monkeypatch):
    # c4's cache records its book; its default groups would be the family map, and an
    # explicit grp is what `analyse` passes through
    LA.fetch(tmp_path / "c4", since=PRE[0], asof=S4, client=FakeClient(), nav_fetcher=fake_navs,
             dist_check_fetcher=fake_dividends, now=CHECK_AT, book="c4")
    inp = LA.load_cache(tmp_path / "c4", grp=dict(FAMILIES))
    assert inp.book == "c4" and inp.sources["book"] == "c4"
    # the default client reads C4's own keys, never the core's
    for k in ("ALPACA_C4_KEY_ID", "ALPACA_C4_SECRET_KEY", "ALPACA_CEF_KEY_ID", "ALPACA_CEF_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    from scripts.ops import alpaca_read as AR
    with pytest.raises(AR.MissingCredential, match="ALPACA_C4_KEY_ID"):
        LA.fetch(tmp_path / "c4b", since=PRE[0], asof=S4, nav_fetcher=fake_navs,
                 dist_check_fetcher=fake_dividends, now=CHECK_AT, book="c4")
    monkeypatch.setenv("ALPACA_CEF_KEY_ID", "x")
    monkeypatch.setenv("ALPACA_CEF_SECRET_KEY", "y")
    with pytest.raises(AR.MissingCredential, match="ALPACA_C4_KEY_ID"):   # never the core's key
        LA.fetch(tmp_path / "c4c", since=PRE[0], asof=S4, nav_fetcher=fake_navs,
                 dist_check_fetcher=fake_dividends, now=CHECK_AT, book="c4")


def test_c4_summary_names_the_book_and_the_family_grouping(tmp_path):
    res = LA.attribute(inputs(grp=dict(FAMILIES), book="c4"))
    assert res.book == "c4"
    text = LA.write_outputs(res, tmp_path / "out")["summary"].read_text()
    assert text.startswith("# Live P&L attribution, c4 paper account")
    assert "## By family (ops/specs/c4_families.frozen.json level_signal.family_of)" in text
    assert "## By group" not in text
    assert "measured on the cef account" in text and "equal this schedule on every" not in text


def test_the_core_summary_still_says_what_it_said(tmp_path):
    """Pin (passes before and after this change): the words the MUNI-era outputs were read in."""
    res = LA.attribute(inputs())
    text = LA.write_outputs(res, tmp_path / "out")["summary"].read_text()
    assert text.startswith("# Live P&L attribution, cef paper account")
    assert "## By group (data/cef/cef_universe.csv `grp`)" in text
    assert "the cef account's FEE activities are REG and CAT rows that equal this schedule on every" in text


def test_nav_missing_unmeasured_keeps_hold_fill_fees_and_the_reconciliation():
    # AAA has no NAV on S3 (held into S3 and into S4): the report job's 20:30 case
    navs = _drop(table(NAVS), ("AAA", S3))
    res = LA.attribute(inputs(navs=navs), nav_missing="unmeasured")
    full = LA.attribute(inputs())
    assert res.nav_unmeasured and {(d, s) for d, s, _ in res.nav_unmeasured} == {(S3, "AAA"), (S4, "AAA")}
    assert row(res, "AAA", S3)["nav_part"] is None and row(res, "AAA", S3)["disc_part"] is None
    assert row(res, "AAA", S4)["nav_part"] is None            # the p side of S4's return is S3's NAV
    # a session total over a missing term is UNMEASURED; the other sessions keep theirs
    assert daily(res, "nav_part")[S3] is None and daily(res, "nav_part")[S2] == daily(full, "nav_part")[S2]
    # hold, fill, fees, the official change and the reconciliation need no NAV and are complete
    for c in ("hold", "fill", "fees", "eod_change", "rebuilt", "residual"):
        assert daily(res, c) == daily(full, c), c
    t = LA.totals(res)
    assert t["nav_part"] is None and t["disc_part"] is None
    assert t["hold"] == LA.totals(full)["hold"] and t["max_abs_residual"] == 0.0
    # and the gap is said, naming each name-day
    assert any("NAV/discount split is UNMEASURED" in g and "AAA" in g for g in res.gaps)
    # the default mode still raises, naming the name and the day
    with pytest.raises(LA.AttributionError, match=f"missing NAV for AAA on {S3}"):
        LA.attribute(inputs(navs=navs))
