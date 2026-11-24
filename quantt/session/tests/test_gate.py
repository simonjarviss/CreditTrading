"""gate.py: every refusal, one at a time, from a baseline that passes all nine.

`good()` builds facts on which `evaluate` returns nothing; each test changes ONE
fact and asserts the refusal names the gate it belongs to. That is what makes a
mutation of any single gate visible: the baseline test fails if a gate refuses
too much, and the gate's own test fails if it refuses too little.
"""
import dataclasses
import datetime as dt

import pytest

from quantt.session import gate as gt
from quantt.session.decide import Order

ET = gt.ET
D = dt.date(2026, 9, 29)          # a Tuesday
ASOF = dt.date(2026, 9, 28)
UNI = ("AAA", "BBB", "CCC")


def order(sym, side, qty, leg=1, cur=0, tgt=None, px=10.0):
    if tgt is None:
        tgt = cur + (qty if side == "buy" else -qty)
    return Order(symbol=sym, side=side, qty=qty, leg=leg,
                 client_order_id=f"cef-{D:%Y%m%d}-{sym}-{leg}", current=cur, target=tgt,
                 est_price=px, reason="t")


def good(**over):
    f = gt.GateFacts(
        env_dry_run="0", approve_sha="abc", auto_armed=False, plan_sha="abc",
        halts=[],
        clock_ts=dt.datetime(2026, 9, 29, 8, 30, tzinfo=ET), session_date=D,
        calendar_today=[{"date": D, "open": "09:30", "close": "16:00"}],
        nyse_trading_today=True,
        asof=ASOF, refresh_exit=0, close_dates={s: ASOF for s in UNI},
        nav_dates={s: ASOF for s in UNI},
        started_exists=False, orders_recent=[], orders_open=[], cid_prefix="cef",
        orders=(order("AAA", "buy", 100), order("BBB", "sell", 50)),
        positions={}, shortable={s: True for s in UNI}, shorting_enabled=True,
        closes={"AAA": 10.0, "BBB": 20.0, "CCC": 30.0}, equity=100_000.0,
        sized_equity=100_000.0,
        buying_power=200_000.0, current_gross=0.0, maintenance_margin=0.0,
        max_gross_usd=260_000.0, max_gross_stress=1.8,
        universe=UNI,
        account_flags={"trading_blocked": False, "account_blocked": False,
                       "trade_suspended_by_user": False})
    return dataclasses.replace(f, **over)


def gates(f):
    return [r.gate for r in gt.evaluate(f)]


def test_baseline_passes_every_gate():
    assert gt.evaluate(good()) == []


def test_all_nine_are_evaluated_not_just_the_first():
    f = good(env_dry_run="1", approve_sha="nope", halts=[{"reason": "x", "scope": "global"}],
             refresh_exit=4, started_exists=True)
    assert {"dry_run", "arming", "halt", "data", "no_set_in_auction"} <= set(gates(f))


# ------------------------------------------------------------ 1 dry run

@pytest.mark.parametrize("v", [None, "", "1", "false", "False", "no", " 0", "0 ", "00", "O"])
def test_dry_run_everything_but_exact_zero_is_dry(v):
    assert gates(good(env_dry_run=v)) == ["dry_run"]


def test_dry_run_exact_zero_arms():
    assert "dry_run" not in gates(good(env_dry_run="0"))


# -------------------------------------------------------------- 2 arming

def test_approve_mismatch_refuses():
    assert gates(good(approve_sha="deadbeef")) == ["arming"]


def test_approve_mismatch_refuses_even_with_auto_armed():
    assert gates(good(approve_sha="deadbeef", auto_armed=True)) == ["arming"]


def test_auto_armed_arms_without_approve():
    assert gates(good(approve_sha=None, auto_armed=True)) == []


def test_neither_approve_nor_auto_armed_refuses():
    assert gates(good(approve_sha=None, auto_armed=False)) == ["arming"]


# ---------------------------------------------------------------- 3 halt

def test_halt_refuses():
    r = gt.evaluate(good(halts=[{"reason": "manual", "scope": "cef", "path": "ops/HALT_cef.md"}]))
    assert [x.gate for x in r] == ["halt"] and "manual" in r[0].detail


# --------------------------------------------------------------- 4 clock

def test_clock_after_1545_refuses():
    assert gates(good(clock_ts=dt.datetime(2026, 9, 29, 15, 45, tzinfo=ET))) == ["clock"]


def test_clock_1544_passes():
    assert gates(good(clock_ts=dt.datetime(2026, 9, 29, 15, 44, 59, tzinfo=ET))) == []


def test_clock_early_close_uses_calendar_minus_ten():
    cal = [{"date": D, "open": "09:30", "close": "13:00"}]
    assert gates(good(calendar_today=cal,
                      clock_ts=dt.datetime(2026, 9, 29, 12, 50, tzinfo=ET))) == ["clock"]
    assert gates(good(calendar_today=cal,
                      clock_ts=dt.datetime(2026, 9, 29, 12, 49, tzinfo=ET))) == []


def test_clock_is_read_in_et_from_utc():
    # 19:46 UTC = 15:46 EDT
    assert gates(good(clock_ts=dt.datetime(2026, 9, 29, 19, 46,
                                           tzinfo=dt.timezone.utc))) == ["clock"]


def test_clock_evening_run_refuses_next_day_auction():
    # After 19:00 ET Alpaca queues cls for the NEXT day's auction [V].
    assert "clock" in gates(good(clock_ts=dt.datetime(2026, 9, 29, 20, 0, tzinfo=ET)))


# The evening side (team lead 2026-09-29): an order for D's auction may go from
# 19:15 ET on the as-of date. Alpaca rejects cls 15:50-19:00 and queues after
# 19:00 into the next day's auction [V].

def test_clock_evening_of_the_asof_date_passes():
    assert gates(good(clock_ts=dt.datetime(2026, 9, 28, 22, 0, tzinfo=ET))) == []
    assert gates(good(clock_ts=dt.datetime(2026, 9, 29, 0, 30, tzinfo=ET))) == []


def test_clock_evening_window_opens_at_1915_not_before():
    assert gates(good(clock_ts=dt.datetime(2026, 9, 28, 19, 15, tzinfo=ET))) == []
    assert gates(good(clock_ts=dt.datetime(2026, 9, 28, 19, 14, 59, tzinfo=ET))) == ["clock"]


def test_clock_between_asof_close_and_queue_open_refuses():
    # 15:50-19:00 ET Alpaca rejects cls outright [V]
    assert gates(good(clock_ts=dt.datetime(2026, 9, 28, 17, 0, tzinfo=ET))) == ["clock"]


def test_clock_before_the_asof_date_refuses():
    assert gates(good(clock_ts=dt.datetime(2026, 9, 27, 22, 0, tzinfo=ET))) == ["clock"]


def test_clock_friday_evening_for_monday_auction_passes():
    mon, fri = dt.date(2026, 10, 5), dt.date(2026, 10, 2)
    base = dict(session_date=mon, asof=fri,
                calendar_today=[{"date": mon, "open": "09:30", "close": "16:00"}],
                close_dates={s: fri for s in UNI}, nav_dates={s: fri for s in UNI},
                orders=())
    assert gates(good(clock_ts=dt.datetime(2026, 10, 2, 22, 0, tzinfo=ET), **base)) == []
    assert gates(good(clock_ts=dt.datetime(2026, 10, 3, 0, 59, tzinfo=ET), **base)) == []
    assert gates(good(clock_ts=dt.datetime(2026, 10, 5, 0, 0, tzinfo=ET), **base)) == []
    assert gates(good(clock_ts=dt.datetime(2026, 10, 5, 15, 45, tzinfo=ET), **base)) == ["clock"]


def test_clock_refuses_the_daytime_of_an_intervening_non_trading_day():
    # review 2026-09-29: Alpaca documents no cls routing for a Saturday afternoon
    # or a holiday morning [U]; the window is only the as-of evening + session day.
    mon, fri = dt.date(2026, 10, 5), dt.date(2026, 10, 2)
    base = dict(session_date=mon, asof=fri,
                calendar_today=[{"date": mon, "open": "09:30", "close": "16:00"}],
                close_dates={s: fri for s in UNI}, nav_dates={s: fri for s in UNI},
                orders=())
    for t in (dt.datetime(2026, 10, 3, 1, 0, tzinfo=ET), dt.datetime(2026, 10, 3, 16, 30, tzinfo=ET),
              dt.datetime(2026, 10, 4, 22, 0, tzinfo=ET)):
        assert gates(good(clock_ts=t, **base)) == ["clock"], t
    fri_b, wed = dt.date(2026, 11, 27), dt.date(2026, 11, 25)       # Thanksgiving between
    base2 = dict(base, session_date=fri_b, asof=wed,
                 calendar_today=[{"date": fri_b, "open": "09:30", "close": "13:00"}],
                 close_dates={s: wed for s in UNI}, nav_dates={s: wed for s in UNI})
    assert gates(good(clock_ts=dt.datetime(2026, 11, 26, 10, 0, tzinfo=ET), **base2)) == ["clock"]
    assert gates(good(clock_ts=dt.datetime(2026, 11, 25, 22, 0, tzinfo=ET), **base2)) == []


def test_in_send_window_matches_the_gate():
    cut = gt.cutoff_et(D, "16:00")
    assert gt.in_send_window(dt.datetime(2026, 9, 28, 22, 0, tzinfo=ET), ASOF, cut)
    assert gt.in_send_window(dt.datetime(2026, 9, 29, 15, 44, tzinfo=ET), ASOF, cut)
    assert not gt.in_send_window(dt.datetime(2026, 9, 29, 15, 45, tzinfo=ET), ASOF, cut)
    assert not gt.in_send_window(dt.datetime(2026, 9, 28, 19, 0, tzinfo=ET), ASOF, cut)


def test_clock_not_a_trading_day_refuses():
    assert "clock" in gates(good(calendar_today=[], nyse_trading_today=False))


def test_clock_calendars_disagree_refuses():
    assert "clock" in gates(good(nyse_trading_today=False))
    assert "clock" in gates(good(calendar_today=[], nyse_trading_today=True))


def test_clock_wrong_date_refuses():
    assert "clock" in gates(good(clock_ts=dt.datetime(2026, 9, 30, 8, 30, tzinfo=ET)))


# ---------------------------------------------------------------- 5 data

def test_data_refresh_nonzero_refuses():
    assert gates(good(refresh_exit=4)) == ["data"]


def test_data_skip_refresh_still_needs_asof_closes():
    assert gates(good(refresh_exit=None)) == []
    stale = {**{s: ASOF for s in UNI}, "BBB": dt.date(2026, 9, 25)}
    assert gates(good(refresh_exit=None, close_dates=stale)) == ["data"]


def test_data_missing_close_refuses():
    cd = {"AAA": ASOF, "BBB": ASOF}
    assert gates(good(close_dates=cd)) == ["data"]


def test_data_skip_refresh_close_asof_but_nav_a_day_old_refuses():
    # Review 2026-09-28: a close dated as-of with the NAV one day older made the
    # sleeve emit that name FLAT ("below min weight"); --skip-refresh bypasses the
    # fetcher's completeness check, so gate 5 must see the NAV date itself.
    nd = {**{s: ASOF for s in UNI}, "BBB": dt.date(2026, 9, 25)}
    rs = gt.evaluate(good(refresh_exit=None, nav_dates=nd))
    assert [r.gate for r in rs] == ["data"]
    assert "NAV not dated 2026-09-28" in rs[0].detail and "BBB" in rs[0].detail


def test_data_missing_nav_refuses():
    nd = {"AAA": ASOF, "BBB": ASOF, "CCC": None}
    rs = gt.evaluate(good(nav_dates=nd))
    assert [r.gate for r in rs] == ["data"] and "no NAV at all for ['CCC']" in rs[0].detail


def test_data_refresh_timeout_string_refuses():
    rs = gt.evaluate(good(refresh_exit="timed out after 60s"))
    assert [r.gate for r in rs] == ["data"] and "did not complete" in rs[0].detail


# ---------------------------------------- 5, the missing-NAV hold (data.missing_nav)

LATE_BBB = {**{s: ASOF for s in UNI}, "BBB": dt.date(2026, 9, 25)}


def hold(**over):
    """gate 5 with the key on, min_names 2 (so at most 1 of the 3 may be held)."""
    kw = dict(asof=ASOF, refresh_exit=4, close_dates={s: ASOF for s in UNI},
              nav_dates=LATE_BBB, universe=UNI, final=True, min_names=2, max_sessions=2,
              held_before={"BBB": 0})
    kw.update(over)
    return gt.missing_nav_hold(**kw)


def test_missing_nav_hold_from_the_final_check_holds_the_name_and_refuses_nothing():
    v = hold()
    assert v["action"] == "held" and v["refusals"] == [] and list(v["held"]) == ["BBB"]
    assert "no NAV dated 2026-09-28 (the panel's last is 2026-09-25)" in v["held"]["BBB"]
    assert v["missing"] == {"BBB": "2026-09-25"} and v["max_held"] == 1
    # evaluate sees the same gate 5: no data refusal at all.
    f = good(refresh_exit=4, nav_dates=LATE_BBB, missing_nav="hold", min_names=2,
             data_final=True, missing_nav_max_sessions=2, missing_nav_held_before={"BBB": 0})
    assert gates(f) == []


def test_missing_nav_hold_before_the_final_check_defers_with_todays_refusals():
    v = hold(final=False)
    today = gt.gate_data(ASOF, 4, {s: ASOF for s in UNI}, LATE_BBB, UNI)
    assert v["action"] == "deferred" and v["held"] == {}
    assert v["refusals"][:-1] == today and "deferred" in v["refusals"][-1].detail
    assert [r.gate for r in v["refusals"]] == ["data"] * (len(today) + 1)


@pytest.mark.parametrize("over, why", [
    ({"close_dates": {**{s: ASOF for s in UNI}, "BBB": dt.date(2026, 9, 25)}}, "close"),
    ({"close_dates": {"AAA": ASOF, "CCC": ASOF}}, "close"),
    ({"nav_dates": {**LATE_BBB, "CCC": None}}, "no NAV at all"),
    ({"refresh_exit": "timed out after 60s"}, "refresh failed"),
    ({"refresh_exit": 3}, "refresh failed"),
    ({"nav_dates": {s: ASOF for s in UNI}}, "disagree"),
    ({"nav_dates": {**LATE_BBB, "CCC": dt.date(2026, 9, 25)},
      "held_before": {"BBB": 0, "CCC": 0}}, "broken feed"),
])
def test_missing_nav_hold_refuses_what_it_is_not_for(over, why):
    """A missing price, a NAV never captured, a failed refresh, a fetcher/panel
    disagreement: gate 5's refusals, unchanged. More missing NAVs than
    n - min_names: refused, the reason added."""
    for final in (True, False):
        v = hold(final=final, **over)
        kw = {k: over.get(k, d) for k, d in (("refresh_exit", 4),
                                             ("close_dates", {s: ASOF for s in UNI}),
                                             ("nav_dates", LATE_BBB))}
        today = gt.gate_data(ASOF, kw["refresh_exit"], kw["close_dates"], kw["nav_dates"], UNI)
        assert v["action"] == "refused" and v["held"] == {} and why in v["why"], v
        if why == "broken feed":
            assert v["refusals"][:-1] == today and "at most 1 may be held" in \
                v["refusals"][-1].detail
        else:
            assert v["refusals"] == today


def test_missing_nav_hold_limit_is_n_minus_min_names_and_final_is_a_bool():
    assert gt.max_missing_nav_holds(13, 6) == 7 and gt.max_missing_nav_holds(5, 6) == 0
    for bad in (0, True, 6.0, None):
        with pytest.raises(ValueError):
            gt.max_missing_nav_holds(13, bad)
    for bad in (None, 1, "yes"):
        with pytest.raises(ValueError):
            hold(final=bad)
    assert hold(nav_dates={s: ASOF for s in UNI}, refresh_exit=0)["action"] == "none"


def test_missing_nav_hold_age_limit_refuses_after_max_sessions_and_on_an_unread_count():
    """The age limit (team lead 2026-10-29, a policy): held through session
    max_sessions; the session after, refused with today's refusals plus a line
    naming the fund and its count; a count that could not be read refuses."""
    today = gt.gate_data(ASOF, 4, {s: ASOF for s in UNI}, LATE_BBB, UNI)
    v = hold(held_before={"BBB": 1})                      # this would be session 2 of 2
    assert v["action"] == "held" and "session 2 of at most 2" in v["held"]["BBB"]
    v = hold(held_before={"BBB": 2})                      # session 3: over the limit
    assert v["action"] == "refused" and v["held"] == {}
    assert v["refusals"][:-1] == today
    last = v["refusals"][-1].detail
    assert "BBB" in last and "2 consecutive sessions" in last and \
        "missing_nav_max_sessions = 2" in last
    v = hold(held_before={"BBB": "no plan.json for the session 2026-09-25"})
    assert v["action"] == "refused" and "cannot be counted" in v["refusals"][-1].detail
    assert v["refusals"][:-1] == today
    for bad_count in (-1, True, 1.0, None):
        with pytest.raises(ValueError):
            hold(held_before={"BBB": bad_count})
    with pytest.raises(ValueError):                       # a held name without its count
        hold(held_before={})
    for bad in (0, -1, True, 2.0, "2", None):
        with pytest.raises(ValueError):
            hold(max_sessions=bad)
    assert hold(final=False, held_before=None)["action"] == "deferred"   # not read before final


# ------------------------------------------------------ 6 no set in auction

def test_started_refuses():
    assert gates(good(started_exists=True)) == ["no_set_in_auction"]


def test_alpaca_order_with_todays_prefix_refuses_even_if_filled():
    o = {"client_order_id": "cef-20260929-AAA-1", "status": "filled",
         "time_in_force": "cls", "symbol": "AAA"}
    assert gates(good(orders_recent=[o])) == ["no_set_in_auction"]


def test_yesterdays_prefix_does_not_refuse():
    o = {"client_order_id": "cef-20260928-AAA-1", "status": "filled",
         "time_in_force": "cls", "symbol": "AAA"}
    assert gates(good(orders_recent=[o])) == []


def test_any_open_non_cls_order_refuses_too():
    o = {"client_order_id": "manual-probe", "status": "new", "time_in_force": "day",
         "symbol": "AAA"}
    assert gates(good(orders_open=[o])) == ["no_set_in_auction"]


def test_any_open_cls_order_refuses():
    o = {"client_order_id": "manual-xyz", "status": "new", "time_in_force": "cls",
         "symbol": "ZZZ"}
    assert gates(good(orders_open=[o])) == ["no_set_in_auction"]


# ------------------------------------------------------- 7 shortability

def test_short_open_on_unshortable_refuses():
    assert gates(good(shortable={"AAA": True, "BBB": False, "CCC": True})) == ["shortability"]


def test_short_open_with_shorting_disabled_refuses():
    assert gates(good(shorting_enabled=False)) == ["shortability"]


def test_cover_on_unshortable_passes():
    f = good(orders=(order("BBB", "buy", 50, cur=-100),), positions={"BBB": -100},
             shortable={"AAA": True, "BBB": False, "CCC": True})
    assert gates(f) == []


# ------------------------------------------------------------ 8 exposure

def test_gross_over_usd_cap_refuses():
    assert gates(good(max_gross_usd=1_000.0)) == ["exposure"]


def test_gross_over_stress_multiple_refuses():
    # gross = 100*10 + 50*20 = 2000; 0.01 * 100000 = 1000
    assert gates(good(max_gross_stress=0.01)) == ["exposure"]


def test_stress_cap_absent_is_not_applied():
    assert gates(good(max_gross_stress=None)) == []


# The stress cap is judged on the equity the plan was SIZED on (incident 2026-10-09).
# Friday 2026-10-09, as recorded on the prod VM: plan.json (decided 22:00 ET
# 2026-10-08, plan_sha 146bb8b2...) and runs/20261009T195201Z-run.json (the 15:52
# send). Every number below is from those two files.
FRI_ORDERS = [("AWF", "buy", 3, -254), ("PDO", "sell", 3, 325), ("PTY", "buy", 3, -317),
              ("HYT", "buy", 6, -655), ("PFN", "sell", 30, 3364), ("MHD", "buy", 17, -1909),
              ("BIT", "sell", 20, 2248), ("PDI", "buy", 25, 54), ("PHK", "sell", 86, 3974),
              ("PCN", "buy", 59, 571), ("JFR", "buy", 215, -4081), ("DSL", "sell", 426, 2371),
              ("MQY", "sell", 468, -2596)]
FRI_CLOSES = {"AWF": 9.510000228881836, "BIT": 11.210000038146973, "DSL": 9.899999618530273,
              "HYT": 7.829999923706055, "JFR": 7.360000133514404, "MHD": 10.100000381469727,
              "MQY": 9.90999984741211, "PCN": 10.760000228881836, "PDI": 14.329999923706055,
              "PDO": 12.069999694824219, "PFN": 6.300000190734863, "PHK": 4.190000057220459,
              "PTY": 10.9399995803833}
FRI_SIZED_EQUITY = 101229.74          # plan.json "equity", the evening decide
FRI_LIVE_EQUITY = 100666.16           # account equity at the 15:52 send


def fri_orders():
    return tuple(Order(symbol=s, side=sd, qty=q, leg=1, client_order_id=f"cef-20261009-{s}-1",
                       current=cur, target=cur + (q if sd == "buy" else -q),
                       est_price=FRI_CLOSES[s], reason="t", time_in_force="day")
                 for s, sd, q, cur in FRI_ORDERS)


def fri_exposure(**over):
    kw = dict(orders=fri_orders(), positions={s: cur for s, _, _, cur in FRI_ORDERS},
              closes=FRI_CLOSES, equity=FRI_LIVE_EQUITY, buying_power=76188.45,
              max_gross_usd=260_000.0, max_gross_stress=1.8, sized_equity=FRI_SIZED_EQUITY,
              current_gross=97508.94 + 86752.25, maintenance_margin=81619.05)
    kw.update(over)
    return gt.gate_exposure(kw.pop("orders"), kw.pop("positions"), kw.pop("closes"),
                            kw.pop("equity"), kw.pop("buying_power"), kw.pop("max_gross_usd"),
                            kw.pop("max_gross_stress"), **kw)


def test_the_2026_10_09_plan_passes_gate_8():
    """Refused twice on 2026-10-09 ("projected gross $182,154.75 > max_gross_stress
    1.8 x equity $100,666.16"); the book did not trade. It was sized at 1.7994x
    its decide equity and took gross DOWN from $183,413.36."""
    assert fri_exposure() == []


def test_the_2026_10_09_numbers_are_what_the_incident_says():
    proj = gt.projected_positions(fri_orders(), {s: c for s, _, _, c in FRI_ORDERS})
    after = sum(abs(q) * FRI_CLOSES[s] for s, q in proj.items())
    before = sum(abs(c) * FRI_CLOSES[s] for s, _, _, c in FRI_ORDERS)
    assert round(after, 2) == 182154.75 and round(before, 2) == 183413.36
    assert after > 1.8 * FRI_LIVE_EQUITY            # what the old gate compared
    assert after <= 1.8 * FRI_SIZED_EQUITY          # what the spec's cap is about


def test_stress_cap_at_the_gate_is_on_the_lower_of_sized_and_live_equity():
    """Team lead's ruling 2026-10-11. From flat: AAA 9,000 x 10 + BBB 4,500 x 20 =
    180,000 = 1.8 x 100,000 exactly, a plan that adds gross. The gate itself never
    scales: with live equity 99,900 it refuses (the send's re-fit scales first,
    test_run.py), and it refuses equally when the SIZED equity is the lower one."""
    f = good(orders=(order("AAA", "buy", 9000), order("BBB", "sell", 4500)),
             buying_power=1e9, equity=100_000.0, sized_equity=100_000.0)
    assert gates(f) == []
    assert gates(dataclasses.replace(f, equity=99_900.0)) == ["exposure"]
    assert gates(dataclasses.replace(f, sized_equity=99_900.0)) == ["exposure"]


def test_a_plan_that_takes_gross_down_passes_even_above_the_cap():
    # held 200,000 gross (2.0x); the plan cuts it to 190,000: still > 1.8x, but down
    f = good(positions={"AAA": 10_000, "BBB": -5_000},
             orders=(order("AAA", "sell", 500, cur=10_000), order("BBB", "buy", 250, cur=-5_000)),
             buying_power=1e9, current_gross=200_000.0, maintenance_margin=60_000.0)
    assert gates(f) == []


def test_a_plan_that_adds_gross_past_the_cap_is_still_refused():
    # held 170,000; the plan adds 20,000 -> 190,000 > 180,000 and > held
    f = good(positions={"AAA": 8_500, "BBB": -4_250},
             orders=(order("AAA", "buy", 2_000, cur=8_500),),
             buying_power=1e9, current_gross=170_000.0, maintenance_margin=51_000.0)
    r = [x for x in gt.evaluate(f) if x.gate == "exposure"]
    assert len(r) == 1 and "sized on" in r[0].detail and "adds to the gross" in r[0].detail


def test_stress_breach_edges():
    assert gt.stress_breach(180.0, 0.0, 1.8, 100.0, 100.0) is None          # at the cap: inside
    assert gt.stress_breach(180.01, 0.0, 1.8, 100.0, 100.0)                  # past it, from flat
    assert gt.stress_breach(190.0, 190.0, 1.8, 100.0, 100.0) is None        # past it, adds nothing
    assert gt.stress_breach(190.0, 189.99, 1.8, 100.0, 100.0)               # past it, adds a cent
    assert gt.stress_breach(1e9, 0.0, None, 100.0, 100.0) is None           # spec key absent


def test_stress_cap_is_on_the_lower_of_sized_and_live_equity():
    """Team lead's ruling 2026-10-11 (release-check review): equity 4% under the sized
    equity by the send; a plan that adds gross is held to 1.8 x LIVE, not 1.8 x sized.
    A plan that does not add gross still always passes; live above sized changes nothing."""
    assert gt.stress_breach(175.0, 0.0, 1.8, 100.0, 96.0)                       # 175 > 172.8
    assert "live equity" in gt.stress_breach(175.0, 0.0, 1.8, 100.0, 96.0)
    assert gt.stress_breach(172.8, 0.0, 1.8, 100.0, 96.0) is None               # at the live cap
    assert gt.stress_breach(175.0, 176.0, 1.8, 100.0, 96.0) is None             # takes gross down
    assert gt.stress_breach(180.0, 0.0, 1.8, 100.0, 110.0) is None              # sized is lower
    assert "sized on" in gt.stress_breach(180.01, 0.0, 1.8, 100.0, 110.0)


def test_fit_scales_an_adding_plan_to_the_live_cap_when_equity_has_fallen():
    """The other half of the ruling: the send's re-fit reads the same rule, so equity
    down 4% since decide scales an adding plan to 1.8 x live instead of refusing it."""
    from quantt.session import run as rn
    o = (order("AAA", "buy", 9_000, cur=0), order("BBB", "sell", 4_500, cur=0))     # 90k + 90k
    closes = {"AAA": 10.0, "BBB": 20.0}
    out, kept, why = rn.fit_to_buying_power(o, {}, closes, 96_000.0, 1e9, 0.0, 0.0,
                                            max_gross_stress=1.8, sized_equity=100_000.0)
    assert why == "max_gross_stress (on the lower of sized and live equity)"
    assert gt.gate_exposure(out, {}, closes, 96_000.0, 1e9, 1e12, 1.8, sized_equity=100_000.0,
                            current_gross=0.0, maintenance_margin=0.0) == []
    gross = sum(x.qty * closes[x.symbol] for x in out)
    assert 0 < gross <= 1.8 * 96_000.0


def test_gross_counts_held_positions_after_orders():
    f = good(positions={"CCC": 5000}, max_gross_usd=150_000.0)   # 5000*30 = 150k + 2k
    assert gates(f) == ["exposure"]


def test_buying_power_refuses_with_short_multiplier():
    # need = 100*10 + 50*20*1.03 = 2030
    assert gates(good(buying_power=2029.0)) == ["exposure"]
    assert gates(good(buying_power=2030.0)) == []


def test_closing_orders_consume_no_buying_power():
    f = good(orders=(order("AAA", "sell", 100, cur=100),), positions={"AAA": 100},
             buying_power=0.0)
    assert gates(f) == []


def test_unpriced_position_refuses():
    f = good(positions={"CCC": 10}, closes={"AAA": 10.0, "BBB": 20.0})
    assert gates(f) == ["exposure"]


# -------------------------------------------------------------- 9 sanity

def test_opposite_side_orders_refuse():
    f = good(orders=(order("AAA", "buy", 10), order("AAA", "sell", 5, leg=2)))
    assert "sanity" in gates(f)


def test_non_universe_symbol_refuses():
    o = Order(symbol="ZZZ", side="buy", qty=1, leg=1, client_order_id="cef-20260929-ZZZ-1",
              current=0, target=1, est_price=10.0, reason="t")
    assert "sanity" in gates(good(orders=(o,), closes={"AAA": 10.0, "BBB": 20.0,
                                                        "CCC": 30.0, "ZZZ": 1.0}))


@pytest.mark.parametrize("q", [0, -5, 1.0, True])
def test_non_positive_int_qty_refuses(q):
    o = dataclasses.replace(order("AAA", "buy", 1), qty=q)
    assert "sanity" in gates(good(orders=(o,)))


def test_wrong_date_in_client_id_refuses():
    o = dataclasses.replace(order("AAA", "buy", 1), client_order_id="cef-20260928-AAA-1")
    assert "sanity" in gates(good(orders=(o,)))


def test_stray_position_refuses():
    assert "sanity" in gates(good(positions={"NAD": 10}, closes={"AAA": 10.0, "BBB": 20.0,
                                                                  "CCC": 30.0, "NAD": 5.0}))


@pytest.mark.parametrize("flag", ["trading_blocked", "account_blocked", "trade_suspended_by_user"])
def test_blocked_account_refuses(flag):
    flags = {"trading_blocked": False, "account_blocked": False, "trade_suspended_by_user": False}
    flags[flag] = True
    assert gates(good(account_flags=flags)) == ["sanity"]


def test_refusal_names_a_real_gate():
    with pytest.raises(ValueError):
        gt.Refusal("made_up", "x")


# ------------------------------------------- 8 overnight margin (review 2026-10-07)

def test_overnight_reg_t_initial_margin_on_the_book_after_the_plan():
    # held 1,000 AAA long and 1,000 BBB short; buying 1,000 more AAA -> gross 2,000*10+20,000
    f = good(positions={"AAA": 1000, "BBB": -1000}, orders=(order("AAA", "buy", 9000, cur=1000),),
             equity=50_000.0, buying_power=1e9)
    # projected gross = 10,000*10 + 1,000*20 = 120,000 -> 50% = 60,000 > equity 50,000
    r = gt.evaluate(f)
    assert any(x.gate == "exposure" and "Reg T initial margin" in x.detail for x in r)


def test_overnight_maintenance_uses_the_live_measured_ratio_not_a_literal():
    base = dict(positions={"AAA": 1000}, orders=(order("AAA", "buy", 500, cur=1000),),
                equity=14_000.0, buying_power=1e9, max_gross_stress=None)
    # projected gross 15,000; Reg T 7,500 <= 14,000 passes. Maintenance at a
    # measured 100% of gross (maintenance 10,000 on current gross 10,000) = 15,000 > 14,000.
    assert any("maintenance" in x.detail for x in gt.evaluate(
        good(current_gross=10_000.0, maintenance_margin=10_000.0, **base)))
    # at a measured 47.8% it passes
    assert gt.evaluate(good(current_gross=10_000.0, maintenance_margin=4_780.0, **base)) == []


def test_margin_limits_skip_maintenance_when_there_is_no_gross_to_measure():
    assert gt.margin_limits({"AAA": 100}, {"AAA": 10.0}, 10_000.0, 0.0, 0.0) == []
