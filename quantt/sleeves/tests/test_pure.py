"""The sleeves runner's pure parts: book file, decision reader, netting, ledger.
Each test names the failure it guards."""
import datetime as dt
import json

import pandas as pd
import pytest

from quantt.sleeves import config, inputs, ledger, net

D, F = dt.date(2026, 11, 16), dt.date(2026, 11, 17)
BOOK = {"book": "events", "_note": "x",
        "sleeves": [{"slug": "a", "family": "f", "backtest_vol_annual": 0.1, "full_capital_usd": 40000, "capital_usd": 10000, "enabled": True},
                    {"slug": "b", "family": "f", "backtest_vol_annual": 0.1, "full_capital_usd": 40000, "capital_usd": 10000, "enabled": True}],
        "min_order_usd": 100, "max_gross_x_equity": 1.0, "max_name_usd": 20000,
        "max_stale_sessions": 2, "max_orders": 100,
        "execution": {"mode": "late_market", "window_minutes_before_close": [8, 2]}}


def cfg(tmp_path, **over):
    p = tmp_path / "events_sleeves.json"
    p.write_text(json.dumps({**BOOK, **over}))
    return config.load(p)


def decision(tmp_path, slug="a", asof=D, written="2026-11-16T23:50:00+00:00", **over):
    d = tmp_path / slug / "decisions"
    d.mkdir(parents=True, exist_ok=True)
    rec = {"slug": slug, "asof": asof.isoformat(), "written_at": written, "fill": "next_close",
           "notional_usd": 1e6, "weights": {"AAA": 0.1, "IWM": -0.1}, **over}
    (d / f"{asof.isoformat()}.json").write_text(json.dumps(rec))


YES = lambda s: True  # noqa: E731


# ---------------------------------------------------------------- config

@pytest.mark.parametrize("drop", config.REQUIRED)
def test_a_missing_key_raises_naming_it(tmp_path, drop):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({k: v for k, v in BOOK.items() if k != drop}))
    with pytest.raises(config.ConfigError, match=drop):
        config.load(p)


@pytest.mark.parametrize("drop", config.SLEEVE_KEYS)
def test_a_sleeve_missing_any_key_raises(tmp_path, drop):
    """`family` and `full_capital_usd` (2026-11-18) are required like every other key: a
    sleeve without its full size cannot be checked against the ladder, and a default would be
    a size nobody chose. Fails against the three-key loader, which refused these two keys."""
    sleeves = [{k: v for k, v in BOOK["sleeves"][0].items() if k != drop}, BOOK["sleeves"][1]]
    with pytest.raises(config.ConfigError, match="exactly the keys"):
        cfg(tmp_path, sleeves=sleeves)


def test_full_size_and_family_are_loaded_and_checked(tmp_path):
    c = cfg(tmp_path)
    assert (c.sleeve("a").full_capital_usd, c.sleeve("a").family, c.sleeve("a").capital_usd) == (40000.0, "f", 10000.0)
    for bad in (0, -1, True, "40000", float("nan")):
        with pytest.raises(config.ConfigError, match="full_capital_usd"):
            cfg(tmp_path, sleeves=[{**BOOK["sleeves"][0], "full_capital_usd": bad}])
    for bad in ("", "CEF ex-date", 3, None):
        with pytest.raises(config.ConfigError, match="family"):
            cfg(tmp_path, sleeves=[{**BOOK["sleeves"][0], "family": bad}])


def test_the_backtest_vol_is_required_and_the_modelled_cost_is_the_one_optional_key(tmp_path):
    """`backtest_vol_annual` is the ladder's sigma (team lead, 2026-11-18) and required.
    `modelled_fill_cost_bp` may be absent, and absent loads as None, never as zero: zero would
    mean "the model assumes no cost", which fails any sleeve that is a dollar behind."""
    a = cfg(tmp_path).sleeve("a")
    assert (a.backtest_vol_annual, a.modelled_fill_cost_bp) == (0.1, None)
    for bad in (0, -0.1, True, "0.1", float("inf")):
        with pytest.raises(config.ConfigError, match="backtest_vol_annual"):
            cfg(tmp_path, sleeves=[{**BOOK["sleeves"][0], "backtest_vol_annual": bad}])
    assert cfg(tmp_path, sleeves=[{**BOOK["sleeves"][0], "modelled_fill_cost_bp": 12.5}]).sleeve("a").modelled_fill_cost_bp == 12.5
    assert cfg(tmp_path, sleeves=[{**BOOK["sleeves"][0], "modelled_fill_cost_bp": 0}]).sleeve("a").modelled_fill_cost_bp == 0.0
    for bad in (-1, None, "10", True):
        with pytest.raises(config.ConfigError, match="modelled_fill_cost_bp"):
            cfg(tmp_path, sleeves=[{**BOOK["sleeves"][0], "modelled_fill_cost_bp": bad}])
    # `promotion_waived` (team lead's waiver, 2026-11-19): absent is False, true is True, and
    # anything else is refused, so a waiver is never switched off by a value that reads like a default
    assert a.promotion_waived is False
    assert cfg(tmp_path, sleeves=[{**BOOK["sleeves"][0], "promotion_waived": True}]).sleeve("a").promotion_waived is True
    for bad in (False, "true", 1, None):
        with pytest.raises(config.ConfigError, match="promotion_waived"):
            cfg(tmp_path, sleeves=[{**BOOK["sleeves"][0], "promotion_waived": bad}])
    with pytest.raises(config.ConfigError, match="exactly the keys"):
        cfg(tmp_path, sleeves=[{**BOOK["sleeves"][0], "sigma": 0.1}])


def test_the_core_books_account_is_refused(tmp_path):
    with pytest.raises(config.ConfigError, match="another book"):
        cfg(tmp_path, book="cef")


def test_only_late_market_is_accepted(tmp_path):
    with pytest.raises(config.ConfigError, match="late_market"):
        cfg(tmp_path, execution={"mode": "cls"})


def test_a_slug_listed_twice_is_refused(tmp_path):
    with pytest.raises(config.ConfigError, match="twice"):
        cfg(tmp_path, sleeves=BOOK["sleeves"] + [BOOK["sleeves"][0]])


# ---------------------------------------------------------------- inputs

def test_a_good_decision_is_read_with_its_hash(tmp_path):
    decision(tmp_path)
    r = inputs.read_one(tmp_path, "a", D, F)
    assert r["weights"] == {"AAA": 0.1, "IWM": -0.1} and len(r["sha256"]) == 64


@pytest.mark.parametrize("over, why", [
    ({"written": "2026-11-17T18:00:00+00:00"}, "late"),            # 13:00 New York on F: could have seen F
    ({"written": "2026-11-17T14:30:00+00:00"}, "late"),            # 09:30 New York on F, the open: the cutoff itself
    ({"written": "2026-11-17T17:30:00+00:00"}, "late"),            # 12:30 on F: before the engine's 13:00, after most of a half day
    ({"written": "2026-11-17T17:59:59"}, "time zone"),
    ({"slug_in_file": "b"}, "slug"),
    ({"fill": "next_open"}, "fill convention"),
    ({"weights": {"AAA": float("nan")}}, "weight for AAA"),
    ({"weights": {"AAA": 5.0}}, "beyond"),
    ({"weights": {"aaa bbb": 0.1}}, "not a symbol"),
    ({"weights": [1]}, "weights"),
])
def test_a_bad_decision_is_no_decision(tmp_path, over, why):
    kw = dict(over)
    if "slug_in_file" in kw:
        decision(tmp_path)
        p = tmp_path / "a" / "decisions" / f"{D}.json"
        rec = json.loads(p.read_text()); rec["slug"] = kw["slug_in_file"]; p.write_text(json.dumps(rec))
    else:
        decision(tmp_path, **kw)
    assert why in inputs.read_one(tmp_path, "a", D, F)["missing"]


def test_yesterdays_file_is_not_todays_decision(tmp_path):
    decision(tmp_path, asof=dt.date(2026, 11, 13), written="2026-11-13T23:50:00+00:00")
    assert "absent" in inputs.read_one(tmp_path, "a", D, F)["missing"]


def test_the_reader_matches_a_file_the_shadow_engine_writes(tmp_path, monkeypatch):
    """The format is restated in inputs.py, not imported: this pins it to the engine's."""
    from shadow import engine
    from shadow.book import Book
    # Stricter than the engine's scoring rule on purpose (inputs.py, THE ON-TIME RULE): the open.
    assert inputs.ON_TIME_CUTOFF == dt.time(9, 30) < engine.ON_TIME_CUTOFF == dt.time(13, 0)
    monkeypatch.setattr(Book, "signal_fn", lambda self: (lambda asof, panels: pd.Series({"AAA": 0.1, "IWM": -0.1})))
    b = Book("a", "card", "m:f", (), (), "next_close", 1e6, D, True)
    engine.decide(b, tmp_path, D, now=dt.datetime(2026, 11, 16, 23, 50, tzinfo=dt.timezone.utc))
    assert inputs.read_one(tmp_path, "a", D, F)["weights"] == {"AAA": 0.1, "IWM": -0.1}


# ---------------------------------------------------------------- net

def test_shares_are_whole_and_truncated_toward_zero():
    t, dropped, scale = net.sleeve_targets({"AAA": 0.1, "IWM": -0.1}, 10000, {"AAA": 30.0, "IWM": 230.0}, {}, YES, YES)
    assert t == {"AAA": 33, "IWM": -4} and dropped == () and scale == {}


def test_a_blocked_short_scales_the_longs_and_never_leaves_the_sleeve_one_sided():
    t, dropped, scale = net.sleeve_targets({"AAA": 0.1, "IWM": -0.1}, 10000, {"AAA": 30.0, "IWM": 230.0}, {},
                                           lambda s: False, YES)
    assert t == {} and dropped == ("IWM",) and scale["long"] == 0.0


def test_a_short_already_held_is_kept_but_not_increased():
    t, dropped, _ = net.sleeve_targets({"AAA": 0.1, "IWM": -0.1}, 10000, {"AAA": 30.0, "IWM": 230.0}, {"IWM": -2},
                                       lambda s: False, YES)
    assert t == {"AAA": 16, "IWM": -2} and dropped == ("IWM",)       # 2 of 4 shares short: longs halved


def test_a_name_the_decision_drops_is_targeted_to_zero_and_a_missing_price_is_a_hold(tmp_path):
    c = cfg(tmp_path)
    dec = {"a": {"weights": {"AAA": 0.1}}, "b": {"weights": {"ZZZ": 0.1}}}
    plans = net.plan_sleeves(c, dec, {"a": {"OLD": 5}, "b": {"OLD": -5}}, {}, {"AAA": 10.0, "OLD": 1.0}, YES, YES)
    assert plans[0].targets == {"AAA": 100} and plans[0].action == "decided"
    assert plans[1].action == "hold" and plans[1].targets == {"OLD": -5} and "ZZZ" in plans[1].why


def test_no_decision_holds_then_flattens_and_never_opens(tmp_path):
    c = cfg(tmp_path)
    dec = {"a": {"missing": "late"}, "b": {"missing": "late"}}
    led = {"a": {"AAA": 7}}
    p1 = net.plan_sleeves(c, dec, led, {"a": 1}, {"AAA": 9.0}, YES, YES)
    assert (p1[0].action, p1[0].targets, p1[0].stale_sessions) == ("hold", {"AAA": 7}, 2)
    p2 = net.plan_sleeves(c, dec, led, {"a": 2}, {"AAA": 9.0}, YES, YES)
    assert (p2[0].action, p2[0].targets) == ("flatten", {})
    assert p1[1].targets == {} and p2[1].targets == {}


def test_a_disabled_sleeve_is_flattened_and_an_unlisted_one_refuses(tmp_path):
    c = cfg(tmp_path, sleeves=[{"slug": "a", "family": "f", "backtest_vol_annual": 0.1, "full_capital_usd": 4, "capital_usd": 1, "enabled": False}])
    assert net.plan_sleeves(c, {}, {"a": {"AAA": 3}}, {}, {"AAA": 9.0}, YES, YES)[0].action == "flatten"
    with pytest.raises(net.NetError, match="does not list"):
        net.plan_sleeves(c, {}, {"ghost": {"AAA": 3}}, {}, {}, YES, YES)


def test_opposite_sleeves_net_to_one_target_or_none():
    a = net.SleevePlan("a", "decided", "", {"IWM": -4, "AAA": 10}, 0)
    b = net.SleevePlan("b", "decided", "", {"IWM": 4, "AAA": 5}, 0)
    assert net.net_targets([a, b]) == {"AAA": 15}                    # IWM crosses inside the account


def test_the_gross_limit_scales_every_sleeve_by_one_factor_and_the_name_limit_refuses(tmp_path):
    c = cfg(tmp_path)
    a = net.SleevePlan("a", "decided", "", {"AAA": 100}, 0)
    b = net.SleevePlan("b", "decided", "", {"BBB": -100}, 0)
    plans, f, g = net.apply_limits(c, [a, b], {"AAA": 100.0, "BBB": 100.0}, 10000.0)
    assert f == 0.5 and plans[0].targets == {"AAA": 50} and plans[1].targets == {"BBB": -50} and g == 10000.0
    with pytest.raises(net.NetError, match="max_name_usd"):
        net.apply_limits(c, [net.SleevePlan("a", "decided", "", {"AAA": 300}, 0)], {"AAA": 100.0}, 1e6)
    with pytest.raises(net.NetError, match="no usable close"):
        net.apply_limits(c, [a], {}, 1e6)


# ---------------------------------------------------------------- ledger

def test_allocate_conserves_shares_in_full_partial_and_crossed_fills():
    assert ledger.allocate({"a": 10, "b": 5}, 15) == {"a": 10, "b": 5}
    assert ledger.allocate({"a": 10, "b": 5}, 7) == {"a": 5, "b": 2}            # 4.67 -> 5, 2.33 -> 2
    assert ledger.allocate({"a": 10, "b": -4}, 6) == {"a": 10, "b": -4}         # b's sale supplies a
    assert ledger.allocate({"a": 10, "b": -4}, 0) == {"a": 4, "b": -4}          # nothing filled: only the cross
    assert ledger.allocate({"a": 4, "b": -4}, 0) == {"a": 4, "b": -4}
    assert ledger.allocate({"a": -3, "b": -3}, -1) == {"a": -1, "b": 0}         # tie goes to the first slug


@pytest.mark.parametrize("wanted, filled", [({"a": 5}, 6), ({"a": 5}, -1), ({"a": 4, "b": -4}, 1)])
def test_an_impossible_fill_raises(wanted, filled):
    with pytest.raises(ledger.LedgerError):
        ledger.allocate(wanted, filled)


def test_apply_books_fills_and_crosses_and_the_cash_sums_to_what_the_account_paid():
    a = net.SleevePlan("a", "decided", "", {"AAA": 10, "IWM": -4}, 0)
    b = net.SleevePlan("b", "decided", "", {"IWM": 4}, 0)
    new, book = ledger.apply(ledger.empty(), [a, b], {"AAA": (10, 20.0)}, {"IWM": 230.0}, "2026-11-17")
    assert ledger.shares_of(new) == {"a": {"AAA": 10, "IWM": -4}, "b": {"IWM": 4}}
    assert sum(r["cash"] for r in new["sleeves"].values()) == pytest.approx(-200.0)   # the account bought 10 at 20
    assert {x["kind"] for x in book if x["symbol"] == "IWM"} == {"cross"}
    ledger.check_against_broker(new, {"AAA": 10})
    assert ledger.pnl(new, {"AAA": 21.0, "IWM": 230.0}) == {"a": pytest.approx(10.0), "b": pytest.approx(0.0)}


def test_a_cross_with_no_price_and_a_stray_fill_raise():
    a = net.SleevePlan("a", "decided", "", {"IWM": -4}, 0)
    b = net.SleevePlan("b", "decided", "", {"IWM": 4}, 0)
    with pytest.raises(ledger.LedgerError, match="cross price"):
        ledger.apply(ledger.empty(), [a, b], {}, {}, "2026-11-17")
    with pytest.raises(ledger.LedgerError, match="no sleeve"):
        ledger.apply(ledger.empty(), [a, b], {"ZZZ": (1, 1.0)}, {"IWM": 1.0}, "2026-11-17")


def test_a_position_the_runner_did_not_book_refuses():
    led = {"version": 1, "session": None, "sleeves": {"a": {"shares": {"AAA": 10}, "cash": 0.0, "stale_sessions": 0}}}
    with pytest.raises(ledger.LedgerError, match="AAA: \\+10, \\+9"):
        ledger.check_against_broker(led, {"AAA": 9})
    with pytest.raises(ledger.LedgerError, match="XYZ"):
        ledger.check_against_broker(led, {"AAA": 10, "XYZ": 1})


def test_the_package_never_imports_shadow_and_names_no_order_method_yet():
    """The boundary: decisions are read as data. (The order phase will add a send path in
    its own module; these four must stay free of one.)"""
    import pathlib
    here = pathlib.Path(net.__file__).parent
    for f in ("config.py", "inputs.py", "net.py", "ledger.py"):
        src = (here / f).read_text()
        assert "import shadow" not in src and "from shadow" not in src, f
        assert "submit_order" not in src, f


# ------------------------------------------------- review of stage 2, 2026-11-16

def test_a_decision_written_just_before_the_open_is_on_time(tmp_path):
    decision(tmp_path, written="2026-11-17T14:29:59+00:00")          # 09:29:59 New York on F
    assert "weights" in inputs.read_one(tmp_path, "a", D, F)


def test_a_sleeve_holding_a_name_with_no_close_holds_everything_and_a_flatten_is_deferred(tmp_path):
    """One halted name must not stop the book, and must never be sized or sold on no price."""
    c = cfg(tmp_path)
    dec = {"a": {"weights": {"BBB": 0.1}}, "b": {"weights": {"BBB": 0.1}}}
    plans = net.plan_sleeves(c, dec, {"a": {"AAA": 7, "BBB": 1}}, {}, {"BBB": 10.0}, YES, YES)
    assert (plans[0].action, plans[0].targets, plans[0].stale_sessions) == ("hold", {"AAA": 7, "BBB": 1}, 1)
    assert "AAA" in plans[0].why and plans[1].targets == {"BBB": 100}
    over = net.plan_sleeves(c, dec, {"a": {"AAA": 7}}, {"a": 5}, {"BBB": 10.0}, YES, YES)[0]
    assert (over.action, over.targets) == ("hold", {"AAA": 7}) and "flatten deferred" in over.why
    off = cfg(tmp_path, sleeves=[{"slug": "a", "family": "f", "backtest_vol_annual": 0.1, "full_capital_usd": 4, "capital_usd": 1, "enabled": False}])
    d = net.plan_sleeves(off, {}, {"a": {"AAA": 3}}, {}, {}, YES, YES)[0]
    assert (d.action, d.targets) == ("hold", {"AAA": 3}) and "flatten deferred" in d.why


def test_an_emptied_sleeve_may_be_dropped_from_the_book_file(tmp_path):
    """`ledger.shares_of` lists a sleeve that holds nothing as {slug: {}}; that is not a holding."""
    c = cfg(tmp_path, sleeves=[BOOK["sleeves"][0]])
    plans = net.plan_sleeves(c, {"a": {"weights": {"AAA": 0.1}}}, {"a": {}, "b": {}, "gone": {"X": 0}}, {},
                             {"AAA": 10.0}, YES, YES)
    assert [p.slug for p in plans] == ["a"]
    with pytest.raises(net.NetError, match="does not list"):
        net.plan_sleeves(c, {"a": {"weights": {}}}, {"b": {"AAA": 1}}, {}, {"AAA": 10.0}, YES, YES)


def test_the_gross_is_measured_again_after_truncation_and_scaled_until_it_fits(tmp_path):
    """Offsetting sleeves: +10 against -3 nets 7 ($700); at the first factor (0.5) each sleeve
    truncates toward zero and the net is 4 ($400), above the $350 limit."""
    c = cfg(tmp_path, max_gross_x_equity=0.035)
    a = net.SleevePlan("a", "decided", "", {"AAA": 10}, 0)
    b = net.SleevePlan("b", "decided", "", {"AAA": -3}, 0)
    plans, f, g = net.apply_limits(c, [a, b], {"AAA": 100.0}, 10000.0)
    assert g <= 350.0 and f < 0.5 and g == abs(sum(p.targets.get("AAA", 0) for p in plans)) * 100.0


def test_a_frozen_position_is_valued_but_never_scaled_and_refuses_if_it_alone_is_too_large(tmp_path):
    c = cfg(tmp_path)
    a = net.SleevePlan("a", "hold", "", {"HALT": 50}, 1)
    b = net.SleevePlan("b", "decided", "", {"BBB": 100}, 0)
    plans, f, g = net.apply_limits(c, [a, b], {"HALT": 100.0, "BBB": 100.0}, 10000.0, frozen={"HALT"})
    assert plans[0].targets == {"HALT": 50} and plans[1].targets == {"BBB": 50} and g == 10000.0
    with pytest.raises(net.NetError, match="not scaled"):
        net.apply_limits(c, [a, b], {"HALT": 300.0, "BBB": 100.0}, 10000.0, frozen={"HALT"})
