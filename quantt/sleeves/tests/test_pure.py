"""The sleeves runner's pure parts: book file, decision reader, netting, ledger.
Each test names the failure it guards."""
import datetime as dt
import json

import pandas as pd
import pytest

from quantt.sleeves import config, inputs, ledger, net

D, F = dt.date(2026, 11, 16), dt.date(2026, 11, 17)
BOOK = {"book": "events", "_note": "x",
        "sleeves": [{"slug": "a", "capital_usd": 10000, "enabled": True},
                    {"slug": "b", "capital_usd": 10000, "enabled": True}],
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
    assert inputs.ON_TIME_CUTOFF == engine.ON_TIME_CUTOFF
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
    p1 = net.plan_sleeves(c, dec, led, {"a": 1}, {}, YES, YES)
    assert (p1[0].action, p1[0].targets, p1[0].stale_sessions) == ("hold", {"AAA": 7}, 2)
    p2 = net.plan_sleeves(c, dec, led, {"a": 2}, {}, YES, YES)
    assert (p2[0].action, p2[0].targets) == ("flatten", {})
    assert p1[1].targets == {} and p2[1].targets == {}


def test_a_disabled_sleeve_is_flattened_and_an_unlisted_one_refuses(tmp_path):
    c = cfg(tmp_path, sleeves=[{"slug": "a", "capital_usd": 1, "enabled": False}])
    assert net.plan_sleeves(c, {}, {"a": {"AAA": 3}}, {}, {}, YES, YES)[0].action == "flatten"
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
