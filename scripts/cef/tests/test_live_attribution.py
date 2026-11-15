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

    def corporate_actions(self, symbols, start, end, *, rows=None):
        return []

    def corporate_action_activities(self):
        return []                                   # the cef account had none (2026-11-14)

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


# --- corporate actions (team lead, 2026-11-14: "narrow and handle it") ----------------------
# The investigation's synthetic fixture (scratch split_fixture.py), re-built here: a 1:3 reverse
# split of LNG (long 900) and SHS (short 600) ex CA_EX, under three hypotheses of how paper books
# it. H1 keeps the old count and marks it at the new-basis raw close (a phantom equity jump); H2
# freezes the old position at its last pre-split close; H3 processes the split (count x 1/3).
# Synthetic data tests the code's behaviour, never a claim about the market.

CA_S = [D(2026, 2, 2), D(2026, 2, 3), D(2026, 2, 4), D(2026, 2, 5), D(2026, 2, 6), D(2026, 2, 9),
        D(2026, 2, 10)]
CA_EX = CA_S[3]
CA_K = F(1, 3)                                           # new_rate / old_rate: shares x 1/3
CA_GRP = {"LNG": "equity_sector", "SHS": "equity_sector", "OTH": "preferred"}
CA_RAW = {"LNG": ["4.50", "4.52", "4.48", "13.38", "13.50", "13.41", "13.47"],
          "SHS": ["8.00", "8.05", "8.10", "24.45", "24.30", "24.36", "24.24"],
          "OTH": ["20.00", "20.10", "20.05", "20.20", "20.15", "20.30", "20.25"]}
CA_NAV = {"LNG": ["4.60", "4.61", "4.58", "13.71", "13.80", "13.74", "13.77"],
          "SHS": ["8.40", "8.42", "8.45", "25.38", "25.30", "25.33", "25.29"],
          "OTH": ["21.00", "21.05", "21.02", "21.10", "21.08", "21.20", "21.18"]}
CA_CLOSES = {(s, d): F(v) for s, vs in CA_RAW.items() for d, v in zip(CA_S, vs)}
CA_NAVS = {(s, d): F(v) for s, vs in CA_NAV.items() for d, v in zip(CA_S, vs)}
CA_SPLIT = [{"id": "ca-1", "type": "reverse_split", "date": CA_EX, "parties": [("LNG", "subject")],
             "rates": {"old_rate": F(3), "new_rate": F(1)}},
            {"id": "ca-2", "type": "reverse_split", "date": CA_EX, "parties": [("SHS", "subject")],
             "rates": {"old_rate": F(3), "new_rate": F(1)}}]


def _ca_fill(i, sym, side, qty, px, d):
    return {"id": i, "activity_type": "FILL", "symbol": sym, "side": side, "qty": str(qty), "price": px,
            "transaction_time": f"{d.isoformat()}T20:55:00.000000Z", "type": "fill", "order_id": f"o-{i}",
            "cum_qty": str(qty), "leaves_qty": "0", "order_status": "filled"}


CA_BASE_FILLS = [_ca_fill("f1", "LNG", "buy", 900, "4.51", CA_S[1]), _ca_fill("f2", "SHS", "sell_short", 600, "8.04", CA_S[1]),
                 _ca_fill("f3", "OTH", "buy", 100, "20.08", CA_S[1])]
# Under H1 the runner, sized on the account's count, re-sizes on CA_S[4]; under H2 and H3 nothing fills.
CA_RESIZE = {"H1": [_ca_fill("f4", "LNG", "sell", 600, "13.49", CA_S[4]), _ca_fill("f5", "SHS", "buy", 400, "24.31", CA_S[4])],
             "H2": [], "H3": []}
# H3's account rows, the documented SPLIT shape: the old count out at the old close, the new count in at
# the old close x 3 (value-neutral at the pre-split close), signed, fee-free.
CA_PREV = CA_S[CA_S.index(CA_EX) - 1]
CA_LEGS = [{"id": "ca-leg-1", "type": "SPLIT", "date": CA_EX, "symbol": "LNG", "qty": -900, "price": F("4.48"), "cash": F(0)},
           {"id": "ca-leg-2", "type": "SPLIT", "date": CA_EX, "symbol": "LNG", "qty": 300, "price": F("13.44"), "cash": F(0)},
           {"id": "ca-leg-3", "type": "SPLIT", "date": CA_EX, "symbol": "SHS", "qty": 600, "price": F("8.10"), "cash": F(0)},
           {"id": "ca-leg-4", "type": "SPLIT", "date": CA_EX, "symbol": "SHS", "qty": -200, "price": F("24.30"), "cash": F(0)}]


def _ca_equity(hyp, fills_raw):
    """The account's EOD equity under each hypothesis, from cash and positions only (independent
    of `attribute`'s hold/fill formulas), the investigation's own construction."""
    parsed = LA.parse_fills(fills_raw)
    cash, q, out, frozen = F(100000), {}, [], {}
    for d in CA_S:
        day = [f for f in parsed if f.date == d]
        if d == CA_EX and hyp == "H3":
            for s in ("LNG", "SHS"):
                if q.get(s):
                    q[s] = q[s] * CA_K
        for f in day:
            cash -= f.signed_qty * f.price
            q[f.symbol] = q.get(f.symbol, 0) + f.signed_qty
        cash += LA.session_fees(day)[0]
        mark = {}
        for s, x in q.items():
            if not x:
                continue
            if hyp == "H2" and s in ("LNG", "SHS") and d >= CA_EX:
                frozen.setdefault(s, CA_CLOSES[(s, CA_PREV)])
                mark[s] = frozen[s]
            else:
                mark[s] = CA_CLOSES[(s, d)]
        out.append((d, cash + sum(x * mark[s] for s, x in q.items() if x)))
    return out


def _ca_inputs(hyp, *, corp=CA_SPLIT, acts=(), act_types=None, fills=None):
    fills_raw = CA_BASE_FILLS + CA_RESIZE[hyp] if fills is None else fills
    from scripts.ops import alpaca_read as AR
    return LA.Inputs(fills=LA.parse_fills(fills_raw), eod=_ca_equity(hyp, fills_raw), closes=dict(CA_CLOSES),
                     navs=dict(CA_NAVS), dists=[], corp=list(corp), grp=dict(CA_GRP), flat_start=CA_S[0],
                     fills_from=CA_S[0], corp_types=LA.SPLIT_TYPES, dist_kinds=LA.DIST_KINDS,
                     corp_acts=list(acts),
                     corp_act_types=AR.CORPORATE_ACTION_ACTIVITY_TYPES if act_types is None else act_types,
                     dist_check=[], dist_check_at=dt.datetime(2026, 2, 12, 12, tzinfo=UTC),
                     next_session=D(2026, 2, 11))


def _ca_row(res, s, d):
    r = res.name_day[(res.name_day["symbol"] == s) & (res.name_day["date"] == d)]
    assert len(r) == 1
    return r.iloc[0]


def test_h1_a_split_paper_did_not_process_reconciles_and_names_its_phantom():
    """H1 (paper keeps the old count, marked at the new-basis close): the rebuild from fills
    reconciles to the cent, as the investigation found, and the split is no longer refused.
    Each held subject's ex-date carries the labelled phantom (q_prev - q_prev x k) x close_t,
    LNG +8,028 and SHS -9,780, inside hold, and that name-day's NAV/discount split is UNMEASURED,
    named, instead of the phantom landing silently in nav_part or disc_part. Fails on the parent
    fa84045, which refused the whole attribution ("share-count corporate action(s) in the window")."""
    res = LA.attribute(_ca_inputs("H1"), breaks=[], nav_missing="raise")
    assert all(r == 0 for r in res.daily["residual"])
    ev = {c["symbol"]: c for c in res.corp_events}
    assert set(ev) == {"LNG", "SHS"}
    assert ev["LNG"]["phantom"] == (900 - 900 * CA_K) * F("13.38") == 8028
    assert ev["SHS"]["phantom"] == (-600 + 600 * CA_K) * F("24.45") == -9780
    assert ev["LNG"]["k"] == CA_K and ev["LNG"]["session"] == CA_EX
    for s in ("LNG", "SHS"):
        r = _ca_row(res, s, CA_EX)
        assert r["nav_part"] is None and r["disc_part"] is None and r["hold"] is not None
    assert _ca_row(res, "OTH", CA_EX)["nav_part"] is not None            # the name the split does not touch
    assert any("paper did not process it: phantom (q_prev - q_prev x k) x close = +8,028.00" in g for g in res.gaps)
    assert any("NAV/discount split is UNMEASURED" in g and "LNG" in g for g in res.gaps)


def test_the_market_feed_never_rebases_the_rebuild():
    """Rebasing positions from the market corporate-action feed gives wrong-sign positions under
    H1 (the investigation: LNG -300, SHS +200). The rebuild takes positions from FILLs alone:
    under H1 the ex-date leaves LNG 900 and SHS -600 as held, and the
    runner's re-sizing fills bring them to 300 and -200. Fails on the parent fa84045, which refused."""
    res = LA.attribute(_ca_inputs("H1"), breaks=[])
    r = _ca_row(res, "LNG", CA_EX)
    assert (r["q_prev"], r["q_end"]) == (900, 900) and (_ca_row(res, "SHS", CA_EX)["q_end"]) == -600
    assert dict(zip(res.positions_end["symbol"], res.positions_end["qty"])) == {"LNG": 300, "OTH": 100, "SHS": -200}


@pytest.mark.parametrize("hyp", ["H2", "H3"])
def test_h2_and_an_unrecorded_h3_do_not_reconcile_on_the_ex_date(hyp):
    """H2 (paper froze the old position) and H3 with no account row (support pushed the split by
    hand and the account shows no activity): the rebuild from fills misses the official change
    on the ex-date, so the residual says so (the report job's UNRECONCILED path names the
    session and the event, tests in test_pnl_report). Fails on the parent fa84045, which refused."""
    res = LA.attribute(_ca_inputs(hyp), breaks=[])
    resid = dict(zip(res.daily["date"], res.daily["residual"]))
    assert resid[CA_EX] == {"H2": 1800, "H3": 1752}[hyp] and resid[CA_S[2]] == 0
    assert {c["symbol"] for c in res.corp_events} == {"LNG", "SHS"}


def test_one_split_listed_twice_by_the_feed_is_one_event():
    """Review of the follow-up, 2026-11-14, finding 1 (ca_dup.py): the feed lists one split under
    two ids (docs/REFERENCES.md §12pc: the MQY pairs twice, an exact QQQ duplicate), and each
    record became its own event with the full phantom: four events and twice the phantom. Now one
    event per (symbol, session), its id joining the records'. Fails on the parent bdf181e (four
    events)."""
    corp = CA_SPLIT + [dict(e, id=e["id"] + "-dup") for e in CA_SPLIT]
    res = LA.attribute(_ca_inputs("H1", corp=corp), breaks=[])
    assert sorted((c["symbol"], c["id"], c["phantom"]) for c in res.corp_events) == [
        ("LNG", "ca-1+ca-1-dup", 8028), ("SHS", "ca-2+ca-2-dup", -9780)]


def test_two_records_of_one_split_that_disagree_on_the_rates_raise_naming_both():
    """The same: two records for one symbol and session with different rates cannot both be
    true, so the rebuild raises naming both ids, never picking one. Fails on the parent bdf181e,
    which booked two phantoms."""
    other = dict(CA_SPLIT[0], id="ca-1-other", rates={"old_rate": F(4), "new_rate": F(1)})
    with pytest.raises(LA.AttributionError, match=r"disagree on old_rate: 3 \(id ca-1\) and 4 \(id ca-1-other\)"):
        LA.attribute(_ca_inputs("H1", corp=[CA_SPLIT[0], other]), breaks=[])


def _late_legs(d):
    """The account's rows for a split support pushes by hand on session d, after the ex-date:
    paper's count goes 900 -> 300 and -600 -> -200 at value-neutral prices against d's previous
    close, which is already on the post-split basis."""
    prev = CA_S[CA_S.index(d) - 1]
    out = []
    for s, q in (("LNG", 900), ("SHS", -600)):
        po = CA_CLOSES[(s, prev)]
        out += [{"id": f"{s}-rm-{d}", "type": "SPLIT", "date": d, "symbol": s, "qty": -q, "price": po, "cash": F(0)},
                {"id": f"{s}-al-{d}", "type": "SPLIT", "date": d, "symbol": s, "qty": int(q * CA_K), "price": po * 3,
                 "cash": F(0)}]
    return out


def _late_equity(d_rows):
    """H1 until the rows' session, then the account holds the post-split count (case C)."""
    parsed = LA.parse_fills(CA_BASE_FILLS)
    cash, q, out = F(100000), {}, []
    for d in CA_S:
        if d == d_rows:
            for s in ("LNG", "SHS"):
                q[s] = q[s] * CA_K
        for f in [f for f in parsed if f.date == d]:
            cash -= f.signed_qty * f.price
            q[f.symbol] = q.get(f.symbol, 0) + f.signed_qty
        cash += LA.session_fees([f for f in parsed if f.date == d])[0]
        out.append((d, cash + sum(x * CA_CLOSES[(s, d)] for s, x in q.items() if x)))
    return out


def test_an_acquirer_merger_is_neither_refused_nor_a_phantom():
    """The core's muni shorts were acquirers in mergers effective inside the window (MHD
    2026-02-09, MQY 2026-02-23; docs/REFERENCES.md §12pc): an acquirer's count is unchanged, so
    the event touches nothing. Fails on the parent fa84045, which refused the attribution."""
    merger = {"id": "m-1", "type": "stock_merger", "date": CA_S[2],
              "parties": [("ABSORBED", "acquiree"), ("OTH", "acquirer")], "rates": {}}
    res = LA.attribute(_ca_inputs("H1", corp=[merger]), breaks=[])
    assert not res.corp_events and all(r == 0 for r in res.daily["residual"])
    assert all(x is not None for x in res.name_day["nav_part"])


def test_a_name_flat_on_the_event_date_is_untouched():
    """A reverse split of a name the book traded but held nothing of at the previous close (OTH,
    bought 100 on CA_S[1] and sold before the split here) changes nothing. Fails on the parent
    fa84045, which refused any split of a symbol ever traded."""
    fills = CA_BASE_FILLS + [_ca_fill("f9", "OTH", "sell", 100, "20.05", CA_S[2])]
    split = {"id": "ca-9", "type": "reverse_split", "date": CA_EX, "parties": [("OTH", "subject")],
             "rates": {"old_rate": F(3), "new_rate": F(1)}}
    corp = [split] + [dict(e, parties=[("ZZZ", "subject")]) for e in CA_SPLIT]   # nobody of ours
    res = LA.attribute(_ca_inputs("H1", corp=corp, fills=fills), breaks=[])
    assert not res.corp_events
    assert all(x is not None for x in res.name_day["nav_part"])


def test_other_count_changing_types_held_into_their_date_still_refuse_named():
    """The narrowed refusal: a merger in which our held fund is the ACQUIREE is a type the rebuild
    measures no phantom for, so it refuses, naming the event, the name, its role and the shares
    held. Without the account's activities read, even a split refuses. A pin on the wording (the
    parent refused these too)."""
    acq = {"id": "m-2", "type": "stock_merger", "date": CA_EX,
           "parties": [("LNG", "acquiree"), ("BIG", "acquirer")], "rates": {}}
    with pytest.raises(LA.AttributionError, match=r"measures no phantom for \(only a forward or reverse split's\).*"
                                                  r"stock_merger 2026-02-05 LNG \(acquiree, id m-2\), 900 share"):
        LA.attribute(_ca_inputs("H1", corp=[acq]), breaks=[])
    with pytest.raises(LA.AttributionError, match="did not read the account's corporate-action activities"):
        LA.attribute(_ca_inputs("H1", act_types=()), breaks=[])


def test_a_split_record_without_rates_leaves_the_phantom_unmeasured_named():
    """k comes from the market record's old_rate/new_rate; a record without them leaves the
    phantom UNMEASURED, named, never a guessed ratio; the rebuild still reconciles."""
    corp = [dict(e, rates={}) for e in CA_SPLIT]
    res = LA.attribute(_ca_inputs("H1", corp=corp), breaks=[])
    assert all(c["phantom"] is None and "no old_rate/new_rate" in c["why"] for c in res.corp_events)
    assert all(r == 0 for r in res.daily["residual"])


def test_the_accounts_activity_rows_are_read_strictly():
    """parse_corp_activities: the account's rows, read only so `attribute` can name them when it
    stops (team lead, 2026-11-15); a fractional or zero quantity, a missing price or a duplicate
    id raises (the REST shape is undocumented), so a row it cannot read stops the job too."""
    good = [{"id": "a1", "activity_type": "SPLIT", "date": "2026-02-05", "symbol": "LNG", "qty": "-900", "price": "4.48"},
            {"id": "a2", "activity_type": "CIL", "date": "2026-02-05", "symbol": "LNG", "net_amount": "4.48"}]
    out = LA.parse_corp_activities(good)
    assert [(r["type"], r["qty"], r["price"], r["cash"]) for r in out] == [("SPLIT", -900, F("4.48"), 0),
                                                                         ("CIL", 0, None, F("4.48"))]
    for bad, why in ((dict(good[0], qty="0.5"), "whole number"), (dict(good[0], qty="0"), "whole number"),
                     ({k: v for k, v in good[0].items() if k != "price"}, "price"), (good[0], "duplicate id"),
                     (dict(good[0], activity_type="DIV"), "not a corporate-action type")):
        rows = [good[0], bad] if why == "duplicate id" else [bad]
        with pytest.raises(LA.AttributionError, match=why):
            LA.parse_corp_activities(rows)


def test_a_cache_without_the_activity_file_is_analysed_as_before_and_one_half_present_refuses(tmp_path):
    """A cache from before 2026-11-14 has no corporate-action activity file: it reads as "not
    read" and, with no event that needs it, analyses exactly as before; a file without its
    manifest section (or the reverse) refuses."""
    _fetch(tmp_path / "c")
    (tmp_path / "c" / LA.ACT_FILE).unlink()
    man = json.loads((tmp_path / "c" / "manifest.json").read_text())
    man.pop("corporate_action_activities")
    (tmp_path / "c" / "manifest.json").write_text(json.dumps(man))
    inp = LA.load_cache(tmp_path / "c", grp=dict(GRP))
    assert inp.corp_acts == [] and inp.corp_act_types == ()
    LA.attribute(inp)
    (tmp_path / "c" / LA.ACT_FILE).write_text("[]")
    with pytest.raises(LA.AttributionError, match="must come together"):
        LA.load_cache(tmp_path / "c", grp=dict(GRP))



# --- the second review of the follow-up (team lead, 2026-11-15) ----------------------------

def _ca_account(fills_raw, events=(), closes=None):
    """An account's EOD equity from cash and positions only, independent of `attribute`
    (fx.py's construction, the second review's judge): `events` [(session, fn)], fn(q, cash) ->
    (q, cash) applied at the start of that session, before its fills."""
    closes = CA_CLOSES if closes is None else closes
    parsed = LA.parse_fills(fills_raw)
    cash, q, out = F(100000), {}, []
    ev: dict = {}
    for d, fn in events:
        ev.setdefault(d, []).append(fn)
    for d in CA_S:
        for fn in ev.get(d, []):
            q, cash = fn(dict(q), cash)
        day = [f for f in parsed if f.date == d]
        for f in day:
            cash -= f.signed_qty * f.price
            q[f.symbol] = q.get(f.symbol, 0) + f.signed_qty
        cash += LA.session_fees(day)[0]
        out.append((d, cash + sum(x * closes[(s, d)] for s, x in q.items() if x)))
    return out


def _ca_split_at(syms, k=CA_K):
    def fn(q, cash):
        for s_ in syms:
            if q.get(s_):
                q[s_] = int(q[s_] * k) if q[s_] > 0 else -int(-q[s_] * k)
        return q, cash
    return fn


def _ca_run(fills, eod, corp, acts=(), closes=None, grp=None):
    inp = _ca_inputs("H1", corp=corp, acts=acts, fills=fills)
    inp.eod = eod
    if closes is not None:
        inp.closes = dict(closes)
        inp.navs = {k_: v * F(103, 100) for k_, v in closes.items()}
    if grp is not None:
        inp.grp = dict(grp)
    return LA.attribute(inp, breaks=[])


# closes for the extra symbols the second review's cases need (each the LNG series, or a flat one)
CA_CLOSES2 = dict(CA_CLOSES)
for _sym in ("LNGN", "NEW", "NEWU", "ALT", "SPN"):
    for _d, _v in zip(CA_S, CA_RAW["LNG"] if _sym in ("LNGN", "NEW", "NEWU") else ["5.00"] * len(CA_S)):
        CA_CLOSES2[(_sym, _d)] = F(_v)
CA_GRP2 = dict(CA_GRP, **{s_: "equity_sector" for s_ in ("LNGN", "NEW", "NEWU", "ALT", "SPN")})


def _rows(*legs_):
    return [{"id": i, "type": t, "date": d, "symbol": sy, "qty": q_, "price": None if px is None else F(px),
             "cash": F(0) if cash is None else F(cash)} for i, t, d, sy, q_, px, cash in legs_]


NAMED_CASES = ["acquirer_MA_leg", "split_to_a_new_ticker", "name_change", "unit_split", "spin_off",
               "cil_one_session_later", "cil_three_sessions_later"]


def _named_case(case):
    """(fills, eod, corp, rows) for one of the second review's finding-2a shapes: the account's
    rows on a symbol a record names in a role other than a held count party, or a cash in lieu
    after the split's legs; eod from `_ca_account` (rows change shares, CIL changes cash)."""
    po = CA_CLOSES[("LNG", CA_PREV)]
    lng_only = [_ca_fill("f1", "LNG", "buy", 900, "4.51", CA_S[1]), _ca_fill("f3", "OTH", "buy", 100, "20.08", CA_S[1])]
    ex = CA_EX
    def swap(new_sym, n):
        def fn(q, cash):
            q["LNG"] = 0
            q[new_sym] = q.get(new_sym, 0) + n
            return q, cash
        return fn
    if case == "acquirer_MA_leg":
        corp = [{"id": "m-1", "type": "stock_merger", "date": ex, "parties": [("LNG", "acquiree"), ("OTH", "acquirer")],
                 "rates": {}}]
        rows = _rows(("m1", "MA", ex, "LNG", -900, po, None), ("m2", "MA", ex, "OTH", 200, 900 * po / 200, None))
        events = [(ex, swap("OTH", 200))]
    elif case == "split_to_a_new_ticker":
        corp = [dict(CA_SPLIT[0], parties=[("LNG", "subject"), ("LNGN", "new")])]
        rows = _rows(("n1", "SPLIT", ex, "LNG", -900, po, None), ("n2", "SPLIT", ex, "LNGN", 300, po * 3, None))
        events = [(ex, swap("LNGN", 300))]
    elif case == "name_change":
        corp = [{"id": "nc-1", "type": "name_change", "date": ex, "parties": [("LNG", "old"), ("NEW", "new")], "rates": {}}]
        rows = _rows(("c1", "NC", ex, "LNG", -900, po, None), ("c2", "NC", ex, "NEW", 900, po, None))
        events = [(ex, swap("NEW", 900))]
    elif case == "unit_split":
        corp = [{"id": "u-1", "type": "unit_split", "date": ex,
                 "parties": [("LNG", "old"), ("NEWU", "new"), ("ALT", "alternate")], "rates": {}}]
        rows = _rows(("u1", "SPLIT", ex, "LNG", -900, po, None), ("u2", "SPLIT", ex, "NEWU", 300, po * 3 - 1, None),
                     ("u3", "SPLIT", ex, "ALT", 60, 5, None))
        def fn(q, cash):
            q["LNG"] = 0; q["NEWU"] = 300; q["ALT"] = 60
            return q, cash
        events = [(ex, fn)]
    elif case == "spin_off":
        corp = [{"id": "sp-1", "type": "spin_off", "date": ex, "parties": [("LNG", "source"), ("SPN", "new")], "rates": {}}]
        rows = _rows(("s1", "SPIN", ex, "SPN", 90, 5, None))
        def fn(q, cash):
            q["SPN"] = 90
            return q, cash
        events = [(ex, fn)]
    else:
        lag = 1 if case == "cil_one_session_later" else 3
        dcil = CA_S[CA_S.index(ex) + lag]
        lng_only = [_ca_fill("f1", "LNG", "buy", 901, "4.51", CA_S[1]), _ca_fill("f3", "OTH", "buy", 100, "20.08", CA_S[1])]
        corp = CA_SPLIT[:1]
        rows = _rows(("l1", "SPLIT", ex, "LNG", -901, po, None), ("l2", "SPLIT", ex, "LNG", 300, 901 * po / 300, None),
                     ("l3", "CIL", dcil, "LNG", 0, None, "4.40"))
        def split(q, cash):
            q["LNG"] = 300
            return q, cash
        def pay(q, cash):
            return q, cash + F("4.40")
        events = [(ex, split), (dcil, pay)]
    return lng_only, _ca_account(lng_only, events, CA_CLOSES2), corp, rows


@pytest.mark.parametrize("first", ["open", "crystallised"])
def test_a_second_record_of_a_handled_split_one_session_later_stops_the_attribution(first):
    """Second review of the follow-up, finding 3c, kept by the team lead's simplification
    (2026-11-15): a record of the same symbol, type and rates within CA_MATCH_SESSIONS of a split
    already handled stops the attribution, naming both ids; nothing is merged. With the first
    phantom crystallised by a trade on its own ex-date the second record would otherwise book a
    second phantom on the count the trade left; with it still open, this check names both ids
    before the second-open-phantom check can. A pin on kept behaviour (HEAD 09c452a raised
    too, through the account's rows)."""
    fills = [_ca_fill("f1", "LNG", "buy", 900, "4.51", CA_S[1])]
    if first == "crystallised":
        fills.append(_ca_fill("x1", "LNG", "sell", 600, "13.37", CA_EX))
    dup = dict(CA_SPLIT[0], id="ca-1-again", date=CA_S[CA_S.index(CA_EX) + 1])
    with pytest.raises(LA.AttributionError, match=r"two market records of one reverse_split of LNG with the same rates, "
                                                  r"2026-02-05 \(id ca-1\) and 2026-02-06 \(id ca-1-again\)"):
        _ca_run(fills, _ca_account(fills), [CA_SPLIT[0], dup])


def _phantom_upto(res, d):
    """The cumulative phantom as of session d, exactly: each unprocessed split's booking, its
    accruals, its crystallisation, and the crystallising sessions' fee terms."""
    tot = F(0)
    for c in res.corp_events:
        moves = [(c["session"], c["phantom"])] + list(c["accruals"])
        if c["crystallised"] is not None:
            moves.append((c["crystallised"]["session"], c["crystallised"]["amount"]))
        tot += sum((a for x, a in moves if x <= d), F(0))
    return tot + sum((t["amount"] for t in getattr(res, "phantom_fees", []) if t["session"] <= d), F(0))


@pytest.mark.parametrize("case", ["resize", "full_exit", "partial"])
def test_the_first_trade_crystallises_the_phantom_at_official_minus_a_processed_account(case):
    """Second review of the follow-up, finding 1; the team lead's ruling, 2026-11-15: the accrual
    booked e x the close's move on every later session whatever the account held, so after the
    runner re-sized (CA_RESIZE) the phantom read -1,440 against an independent -1,630.18, and on a
    full exit +8,280 "still OPEN" against a constant +8,093.83. Now the first trade crystallises
    it: e x (the fill price - the last close) plus the session's fee term, then constant. On every
    session from the ex-date the cumulative phantom equals the official equity less that of an
    account that processed the split on its ex-date and traded to the same targets, exactly
    (Fraction). Fails on the parent f550da3, which kept accruing."""
    lng = [("LNG", "subject")]
    if case == "resize":                     # the runner's own re-size, both names (CA_RESIZE)
        fills, cf_fills, corp, syms = CA_BASE_FILLS + CA_RESIZE["H1"], CA_BASE_FILLS, CA_SPLIT, ["LNG", "SHS"]
    elif case == "full_exit":                # sells all 900; the processed account sells its 300
        fills = CA_BASE_FILLS + [_ca_fill("x1", "LNG", "sell", 900, "13.49", CA_S[4])]
        cf_fills = CA_BASE_FILLS + [_ca_fill("x1", "LNG", "sell", 300, "13.49", CA_S[4])]
        corp, syms = CA_SPLIT[:1], ["LNG"]
    else:                                    # sells 300 to a target of 600; the processed account buys 300
        fills = CA_BASE_FILLS + [_ca_fill("x1", "LNG", "sell", 300, "13.49", CA_S[4])]
        cf_fills = CA_BASE_FILLS + [_ca_fill("x1", "LNG", "buy", 300, "13.49", CA_S[4])]
        corp, syms = CA_SPLIT[:1], ["LNG"]
    assert corp[0]["parties"] == lng
    eod, cf = _ca_account(fills), _ca_account(cf_fills, [(CA_EX, _ca_split_at(syms))])
    res = _ca_run(fills, eod, corp)
    assert all(r == 0 for r in res.daily["residual"])
    for (d, e_paper), (_, e_cf) in zip(eod, cf):
        if d >= CA_EX:
            assert _phantom_upto(res, d) == e_paper - e_cf, (case, d, float(_phantom_upto(res, d)), float(e_paper - e_cf))
    for c in res.corp_events:
        assert c["crystallised"]["session"] == CA_S[4] and not c["open"] and c["accruals"] == []
    assert "crystallised by the trade on 2026-02-06" in LA.report(res)


def _rows_on_the_resized_count():
    """The reviewer's C' shape: the runner re-sized on 02-06 (CA_RESIZE), then paper applied the
    1:3 split on 02-10 to the re-sized 300 / -200, giving 100 / -66, the fraction dropped with no
    cash in lieu. (fills, eod, rows, the rows' session)."""
    fills = CA_BASE_FILLS + CA_RESIZE["H1"]
    d, p = CA_S[-1], CA_S[-2]
    rows = _rows(("a1", "SPLIT", d, "LNG", -300, CA_CLOSES[("LNG", p)], None),
                 ("a2", "SPLIT", d, "LNG", 100, 3 * CA_CLOSES[("LNG", p)], None),
                 ("a3", "SPLIT", d, "SHS", 200, "8.10", None), ("a4", "SPLIT", d, "SHS", -66, "24.30", None))
    def late(q, cash):
        q["LNG"], q["SHS"] = 100, -66
        return q, cash
    return fills, _ca_account(fills, [(d, late)]), rows, d


# --- the account's own rows stop the attribution (team lead, 2026-11-15: "simplify") ---------

def _stop_case(name):
    """Inputs for each account-row scenario the earlier reviews built (the first review's H3 and
    cases B and C, the second's named-symbol cases, 900 -> 450, DA and C'): each now stops."""
    po = CA_CLOSES[("LNG", CA_PREV)]
    if name == "H3_split_legs_on_the_ex_date":
        return _ca_inputs("H3", acts=CA_LEGS)
    if name == "split_legs_and_cash_in_lieu":
        fills = [_ca_fill("f1", "LNG", "buy", 901, "4.51", CA_S[1])]
        rows = _rows(("l1", "SPLIT", CA_EX, "LNG", -901, po, None), ("l2", "SPLIT", CA_EX, "LNG", 300, 901 * po / 300, None),
                     ("l3", "CIL", CA_EX, "LNG", 0, None, "4.40"))
        return _ca_inputs("H3", acts=rows, fills=fills, corp=CA_SPLIT[:1])
    if name in ("late_rows_next_session", "late_rows_two_sessions_later", "rows_long_after_the_event"):
        d = {"late_rows_next_session": CA_S[4], "late_rows_two_sessions_later": CA_S[5],
             "rows_long_after_the_event": CA_S[-1]}[name]
        inp = _ca_inputs("H1", acts=_late_legs(d), fills=CA_BASE_FILLS)
        inp.eod = _late_equity(d)
        return inp
    if name == "rows_with_no_market_record":
        return _ca_inputs("H1", corp=[], acts=_late_legs(CA_S[4]), fills=CA_BASE_FILLS)
    if name in NAMED_CASES:
        fills, eod, corp, rows = _named_case(name)
        inp = _ca_inputs("H1", corp=corp, acts=rows, fills=fills)
        inp.eod, inp.closes, inp.grp = eod, dict(CA_CLOSES2), dict(CA_GRP2)
        return inp
    if name == "rows_900_to_450_against_a_1_for_3_record":
        fills = [_ca_fill("f1", "LNG", "buy", 900, "4.51", CA_S[1])]
        rows = _rows(("l1", "SPLIT", CA_EX, "LNG", -900, po, None), ("l2", "SPLIT", CA_EX, "LNG", 450, 2 * po, None))
        return _ca_inputs("H3", acts=rows, fills=fills, corp=CA_SPLIT[:1])
    if name == "rows_then_a_second_record_of_the_split":
        fills = [_ca_fill("f1", "LNG", "buy", 900, "4.51", CA_S[1])]
        rows = _rows(("l1", "SPLIT", CA_EX, "LNG", -900, po, None), ("l2", "SPLIT", CA_EX, "LNG", 300, po * 3, None))
        dup = dict(CA_SPLIT[0], id="ca-1-again", date=CA_S[CA_S.index(CA_EX) + 1])
        return _ca_inputs("H3", acts=rows, fills=fills, corp=[CA_SPLIT[0], dup])
    assert name == "rows_on_the_resized_count_after_the_trade"
    fills, eod, rows, _ = _rows_on_the_resized_count()
    inp = _ca_inputs("H1", acts=rows, fills=fills)
    inp.eod = eod
    return inp


STOP_CASES = ["H3_split_legs_on_the_ex_date", "split_legs_and_cash_in_lieu", "late_rows_next_session",
              "late_rows_two_sessions_later", "rows_long_after_the_event", "rows_with_no_market_record",
              *NAMED_CASES, "rows_900_to_450_against_a_1_for_3_record", "rows_then_a_second_record_of_the_split",
              "rows_on_the_resized_count_after_the_trade"]


@pytest.mark.parametrize("name", STOP_CASES)
def test_any_account_corporate_action_row_stops_the_attribution_named(name):
    """Team lead, 2026-11-15 ("simplify"), on the third review of the follow-up, which found four
    more defects in the path that applied the account's own corporate-action rows: paper has never
    written one and their REST format is undocumented, so any row on or before the as-of, for any
    symbol, stops the attribution, naming every row's symbol, type, date and share count (or
    cash). Every account-row scenario of the three reviews is here; none is applied. Fails on
    the parent 09c452a, which applied (or tied, checked and refused differently) each."""
    inp = _stop_case(name)
    assert inp.corp_acts
    with pytest.raises(LA.AttributionError) as e:
        LA.attribute(inp, breaks=[])
    msg = str(e.value)
    assert msg.startswith(f"{len(inp.corp_acts)} corporate-action activity row(s) of the account on or before ")
    for a in inp.corp_acts:
        what = f"qty {a['qty']:+d}" if a["qty"] else f"cash {float(a['cash']):,.2f}"
        assert f"{a['symbol']} {a['type']} {a['date']} {what} (id {a['id']})" in msg, (a, msg)
    assert msg.endswith("The account recorded a corporate-action row; its REST format has never been measured; the "
                        "report stops until one has been seen and the handling is built against it (team lead, "
                        "2026-11-15)")


def test_a_row_after_the_as_of_is_outside_the_window():
    """The stop reads the window the attribution reads: a row dated after the as-of is no more in
    it than a fill after the as-of, and the result is the one with no row at all. Fails on the
    parent 09c452a only if the rows had changed the result there (a pin of the window)."""
    inp = _stop_case("late_rows_two_sessions_later")
    res = LA.attribute(inp, asof=CA_S[4], breaks=[])
    plain = _stop_case("late_rows_two_sessions_later")
    plain.corp_acts = []
    res0 = LA.attribute(plain, asof=CA_S[4], breaks=[])
    assert res.daily.equals(res0.daily) and res.name_day.equals(res0.name_day)
