"""The promotion and ladder report. Every state directory here is synthetic and built in
tmp_path: the tests are about the counting rules, never a claim about a book."""
from __future__ import annotations

import ast
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

from quantt.sleeves import promote as pm

FULL = 40000.0
EXEC = {"mode": "late_market", "window_minutes_before_close": [8, 2]}


def weekdays(n, start=dt.date(2026, 1, 5)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def book_file(tmp_path, capital=FULL / 4, enabled=True, full=FULL, cost_bp=None, vol=0.1):
    p = tmp_path / "events_sleeves.json"
    p.write_text(json.dumps({
        "book": "events", "min_order_usd": 25, "max_gross_x_equity": 1.5, "max_name_usd": 50000,
        "max_stale_sessions": 2, "max_orders": 300, "execution": EXEC,
        "sleeves": [{"slug": "a", "family": "f", "full_capital_usd": full, "capital_usd": capital,
                     "backtest_vol_annual": vol, "enabled": enabled,
                     **({} if cost_bp is None else {"modelled_fill_cost_bp": cost_bp})}]}))
    return p


def shadow_state(tmp_path, n, slug="a", late=(), unmeasured=(), no_decision=(), flat=()):
    """`n` sessions of a shadow book in the engine's own layout. Each session's decision is
    written at 23:50 UTC on the session before (an evening run); `late` rewrites it to 14:00
    New York on the fill session; indices count sessions from 0."""
    days = weekdays(n + 1)
    d = tmp_path / "shadow" / slug
    (d / "decisions").mkdir(parents=True)
    rows = []
    for i, (prev, day) in enumerate(zip(days, days[1:])):
        written = f"{prev.isoformat()}T23:50:00+00:00"
        if i in late:
            written = dt.datetime.combine(day, dt.time(14, 0), tzinfo=pm.NY).isoformat()
        if i not in no_decision:
            (d / "decisions" / f"{prev.isoformat()}.json").write_text(json.dumps(
                {"slug": slug, "asof": prev.isoformat(), "written_at": written, "notional_usd": 1_000_000,
                 "weights": {} if i in flat else {"AAA": 1.0}}))
        status = "UNMEASURED" if i in unmeasured else "FLAT" if i in flat else "SCORED"
        rows.append({"date": day.isoformat(), "prev": prev.isoformat(), "status": status,
                     "pnl_price_usd": "" if status == "UNMEASURED" else 0.0 if status == "FLAT" else 1000.0,
                     "detail": "no close for ['AAA']" if status == "UNMEASURED" else ""})
    with (d / "scores.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "prev", "status", "pnl_price_usd", "detail"])
        w.writeheader()
        w.writerows(rows)
    return tmp_path / "shadow"


def events_state(tmp_path, held, slug="a", empty_days=0, day_change="5.0000", pnl=None, capital=FULL / 4,
                 no_capital=()):
    """A sleeve_scores.csv in run.py's layout: `empty_days` rows with no position, then `held`
    rows with one. Dates are the shadow_state() sessions, so the two line up. Every sleeve row
    carries `capital` as the capital the plan sized it from, except the row indices in
    `no_capital`, whose cell is empty (a plan from before the column existed)."""
    days = weekdays(empty_days + held + 1)[1:]
    st = tmp_path / "events"
    st.mkdir()
    with (st / "sleeve_scores.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=pm.SCORES_COLUMNS)
        w.writeheader()
        for i, day in enumerate(days):
            n = 0 if i < empty_days else 3
            total = f"{5.0 * max(0, i + 1 - empty_days):.4f}" if pnl is None else pnl
            for s in (slug, pm.BOOK_ROW):
                w.writerow({"date": day.isoformat(), "slug": s, "shares_value": "0.0000", "cash": "0.0000",
                            "pnl": total, "day_change": day_change if n else "0.0000", "n_names": n,
                            "equity_change": "", "residual": "",
                            "capital_usd": "" if s == pm.BOOK_ROW or i in no_capital else f"{capital:.4f}"})
    return st


def bookings(st, n, usd=1000.0, slug="a", skip=(), unbooked=()):
    """A verify.json for each of the first `n` score sessions: the sleeve bought 10 shares
    at usd/10 by a fill and 10 more by a cross inside the account, and another sleeve traded."""
    for i, day in enumerate(weekdays(n + 1)[1:]):
        if i in skip:
            continue
        (st / day.isoformat()).mkdir()
        (st / day.isoformat() / "verify.json").write_text(json.dumps({
            "ledger_applied": i not in unbooked,
            "bookings": [{"slug": slug, "symbol": "AAA", "shares": 10, "price": usd / 20, "kind": "fill"},
                         {"slug": slug, "symbol": "BBB", "shares": -10, "price": usd / 20, "kind": "cross"},
                         {"slug": "zzz", "symbol": "AAA", "shares": 99, "price": 50.0, "kind": "fill"}]}))


def report(tmp_path, *, shadow_n=12, held=None, capital=FULL / 4, enabled=True, cost_bp=None, pnl=None,
           no_capital=(), **shadow_kw):
    sh = shadow_state(tmp_path, shadow_n, **shadow_kw)
    ev = (events_state(tmp_path, held, capital=capital, pnl=pnl, no_capital=no_capital)
          if held is not None else tmp_path / "events")
    if held and cost_bp is not None:
        bookings(ev, held)
    return pm.build(book_file(tmp_path, capital, enabled, cost_bp=cost_bp), sh, ev)


# ------------------------------------------------------------------ promotion

def test_nine_clean_sessions_are_not_eligible_and_ten_are(tmp_path):
    (tmp_path / "x").mkdir(); (tmp_path / "y").mkdir()
    nine = pm.shadow_book(shadow_state(tmp_path / "x", 9), "a")
    ten = pm.shadow_book(shadow_state(tmp_path / "y", 10), "a")
    assert (nine["clean_streak"], nine["eligible"]) == (9, False)
    assert (ten["clean_streak"], ten["eligible"], ten["first"], ten["last"]) == (10, True, "2026-01-06", "2026-01-19")


def test_a_flat_day_with_an_on_time_decision_is_a_clean_session(tmp_path):
    """The plumbing ran: panels fetched, an on-time decision with no weights. This is the
    reading the team lead ruled on 2026-11-18: "Any on-time day, ten in a row"."""
    b = pm.shadow_book(shadow_state(tmp_path, 10, flat=range(10)), "a")
    assert (b["clean_streak"], b["eligible"]) == (10, True)


def test_a_flat_day_with_no_decision_is_not_clean(tmp_path):
    """The engine writes FLAT when no on-time decision exists at all, so the status alone
    cannot count: the decision file is what shows the run happened."""
    b = pm.shadow_book(shadow_state(tmp_path, 12, flat=[7], no_decision=[7]), "a")
    assert (b["clean_streak"], b["eligible"], b["unclean"][0]["kind"]) == (4, False, "NO_DECISION")


@pytest.mark.parametrize("kw, kind", [({"late": [5]}, "LATE"), ({"unmeasured": [5]}, "UNMEASURED")])
def test_a_late_or_unmeasured_day_inside_the_last_ten_breaks_it(tmp_path, kw, kind):
    """14 sessions, 13 of them clean, and still not eligible: the unclean one is among the
    latest ten. The same day eleven sessions back no longer counts."""
    (tmp_path / "x").mkdir(); (tmp_path / "y").mkdir()
    b = pm.shadow_book(shadow_state(tmp_path / "x", 14, **kw), "a")
    assert (b["clean_total"], b["clean_streak"], b["eligible"]) == (13, 8, False)
    assert [u["kind"] for u in b["unclean"]] == [kind]
    older = pm.shadow_book(shadow_state(tmp_path / "y", 16, **kw), "a")
    assert (older["clean_streak"], older["eligible"]) == (10, True)


def test_the_on_time_cutoff_is_the_engines_to_the_second(tmp_path):
    from shadow import engine
    assert pm.ON_TIME_CUTOFF == engine.ON_TIME_CUTOFF and pm.NY == engine.NY
    assert pm.SHADOW_STATUSES == ("SCORED", "FLAT", "UNMEASURED")
    fill = dt.date(2026, 1, 6)
    for clock, kind in ((dt.time(12, 59, 59), "CLEAN"), (dt.time(13, 0), "LATE")):
        p = tmp_path / f"{kind}.json"
        written = dt.datetime.combine(fill, clock, tzinfo=pm.NY)
        p.write_text(json.dumps({"written_at": written.isoformat()}))
        assert pm._decision_kind(p, fill)[0] == kind
        assert engine.on_time({"_written": written}, fill) == (kind == "CLEAN")


def test_a_missing_or_malformed_shadow_record_is_unmeasured_naming_the_path(tmp_path):
    sh = shadow_state(tmp_path, 10)
    assert pm.shadow_book(sh, "nobody")["measured"] is False and "nobody" in pm.shadow_book(sh, "nobody")["why"]
    (sh / "a" / "scores.csv").unlink()
    b = pm.shadow_book(sh, "a")
    assert b["measured"] is False and b["eligible"] is None and "scores.csv" in b["why"]
    (sh / "a" / "scores.csv").write_text("date,prev,status,pnl_price_usd\n2026-01-06,2026-01-05,MAYBE,\n")
    assert "MAYBE" in pm.shadow_book(sh, "a")["why"]
    (sh / "a" / "scores.csv").write_text("date,prev,status,pnl_price_usd\n2026-01-06,2026-01-05,FLAT,0\n"
                                         "2026-01-08,2026-01-07,FLAT,0\n")
    assert "does not follow" in pm.shadow_book(sh, "a")["why"]


# ------------------------------------------------------------------ the ladder

@pytest.mark.parametrize("held, capital, verdict, code", [
    (0, FULL / 4, pm.AGREE, pm.EXIT_AGREE),
    (19, FULL / 4, pm.AGREE, pm.EXIT_AGREE),
    (19, FULL / 2, pm.CHANGE, pm.EXIT_CHANGE),
    (20, FULL / 4, pm.UNMEASURED, pm.EXIT_UNMEASURED),
    (59, FULL / 2, pm.UNMEASURED, pm.EXIT_UNMEASURED),
])
def test_the_ladder_at_its_boundaries(tmp_path, held, capital, verdict, code):
    """With no modelled cost in the file, 20 to 59 position sessions cannot be judged: the
    verdict names the key and nothing else (the capital column is there)."""
    rep = report(tmp_path, shadow_n=max(12, held), held=held, capital=capital)
    s = rep["sleeves"][0]
    assert (s["position_sessions"], s["verdict"], rep["exit_code"]) == (held, verdict, code)
    if held < 20:
        assert (s["stage_due"], s["capital_due"]) == ("QUARTER", FULL / 4)
    else:
        assert s["missing"] == [pm.NO_COST_KEY] and s["capital_due"] is None and "HALF" in s["stage_due"]


@pytest.mark.parametrize("cost_bp, capital, track, verdict, edit", [
    (50.0, FULL / 4, "PASS", pm.CHANGE, '"capital_usd": 20000.0 for a (now 10000.0)'),   # earns its half
    (50.0, FULL / 2, "PASS", pm.AGREE, None),
    (49.0, FULL / 4, "FAIL", pm.AGREE, None),                                            # stays a quarter
    (0.0, FULL / 4, "FAIL", pm.AGREE, None),
])
def test_twenty_five_sessions_reach_a_fills_track_verdict(tmp_path, cost_bp, capital, track, verdict, edit):
    """Team lead, 2026-11-19: the capital column, a modelled cost and real fills only. At
    $10,000 the sleeve made +$5 a session and its shadow book +$1,000 on $1,000,000, i.e.
    +$10 at this capital: over 25 sessions paper is $125 behind. It filled $500 in the market
    each session ($12,500) and crossed another $500 inside the account, which earns nothing:
    twice 50bp on the fills allows exactly $125 and passes, twice 49bp allows $122.50 and
    fails. (At $20,000 the shadow line doubles; the row below prices that with its own fills.)"""
    if capital == FULL / 2:
        cost_bp = 150.0                    # shortfall 25 x (20 - 5) = 375 = 2 x 150bp x 12,500
    rep = report(tmp_path, shadow_n=25, held=25, capital=capital, cost_bp=cost_bp)
    s = rep["sleeves"][0]
    t = s["tracking"]
    assert t["traded"] == {"usd": 25000.0, "fills_usd": 12500.0, "crosses_usd": 12500.0}
    assert t["allowance_usd"] == pytest.approx(2 * cost_bp / 1e4 * 12500) and t["verdict"] == track
    assert (s["verdict"], s["missing"], s["edits"]) == (verdict, [], [edit] if edit else [])
    assert s["capital_due"] == (FULL / 2 if track == "PASS" else FULL / 4)
    assert f"fills track {track}" in pm.render(rep)


def test_a_sleeve_whose_only_trades_were_crossed_earns_no_allowance(tmp_path):
    """Team lead, 2026-11-19: "No, only real fills". Every booking here is a cross inside the
    account, so the allowance is zero whatever the modelled cost, and a paper line $125 behind
    its shadow book fails."""
    sh = shadow_state(tmp_path, 25)
    ev = events_state(tmp_path, 25)
    for i, day in enumerate(weekdays(26)[1:]):
        (ev / day.isoformat()).mkdir()
        (ev / day.isoformat() / "verify.json").write_text(json.dumps({"ledger_applied": True, "bookings": [
            {"slug": "a", "symbol": "BBB", "shares": -10, "price": 100.0, "kind": "cross"}]}))
    t = pm.build(book_file(tmp_path, cost_bp=500.0), sh, ev)["sleeves"][0]["tracking"]
    assert t["traded"] == {"usd": 25000.0, "fills_usd": 0.0, "crosses_usd": 25000.0}
    assert (t["allowance_usd"], t["verdict"]) == (0.0, "FAIL")


def test_a_row_with_no_recorded_capital_is_unmeasured_naming_its_date(tmp_path):
    """A plan written before the column existed leaves an empty cell. The report never fills
    it from today's book file: 20 to 59 sessions and 60 on are both UNMEASURED, naming the date."""
    rep = report(tmp_path, shadow_n=25, held=25, cost_bp=50.0, no_capital=[3])
    s = rep["sleeves"][0]
    assert s["verdict"] == pm.UNMEASURED and "verdict" not in s["tracking"]
    # the empty cell is row 3's (2026-01-09); it is the capital carried into the NEXT session
    assert "empty capital_usd" in s["missing"][0] and "2026-01-12" in s["missing"][0]
    rep = report(tmp_path / "x", shadow_n=60, held=60, capital=FULL / 2, no_capital=[7])
    s = rep["sleeves"][0]
    assert s["verdict"] == pm.UNMEASURED and s["missing"][0].startswith("sigma x sqrt(T): sleeve_scores.csv has an empty")
    assert "2026-01-15" in s["missing"][0]


def test_a_change_names_the_exact_edit(tmp_path):
    s = report(tmp_path, held=19, capital=FULL / 2)["sleeves"][0]
    assert s["edits"] == ['"capital_usd": 10000.0 for a (now 20000.0)']
    assert "CHANGE NEEDED in ops/sleeves/events_sleeves.json" in pm.render(report(tmp_path / "x", held=3, capital=FULL))


def test_only_sessions_with_a_position_count(tmp_path):
    sh = shadow_state(tmp_path, 40)
    ev = events_state(tmp_path, 19, empty_days=15)
    s = pm.build(book_file(tmp_path), sh, ev)["sleeves"][0]
    assert (s["rows"], s["position_sessions"], s["verdict"]) == (34, 19, pm.AGREE)


def test_tracking_figures_with_no_modelled_cost_name_the_absent_key(tmp_path):
    """25 position sessions at a quarter ($10,000): paper +5 a day; the shadow book +$1,000 a
    day on $1,000,000, i.e. +$10 a day at this capital. With no modelled_fill_cost_bp there is
    no allowance and no verdict, and the report names the key."""
    rep = report(tmp_path, shadow_n=25, held=25)
    s = rep["sleeves"][0]
    t = s["tracking"]
    assert (t["sessions_compared"], t["paper_pnl_usd"], t["shadow_pnl_usd_at_shadow_notional"],
            t["shadow_pnl_usd_at_capital_usd"], t["difference_usd"]) == (25, 125.0, 25000.0, 250.0, -125.0)
    assert "allowance_usd" not in t and "verdict" not in t
    assert s["verdict"] == pm.UNMEASURED and "modelled_fill_cost_bp is absent" in pm.render(rep)


def test_the_shadow_line_is_scaled_by_the_capital_of_the_plan_that_sized_what_was_carried_in(tmp_path):
    """Ten sessions at $10,000 then fifteen at $20,000: the first row uses its own capital and
    every later row the row before it, so eleven sessions scale at $10,000 (+$10) and fourteen
    at $20,000 (+$20): $390, not 25 sessions at today's $20,000 ($500)."""
    sh = shadow_state(tmp_path, 25)
    ev = events_state(tmp_path, 25)
    lines = (ev / "sleeve_scores.csv").read_text().splitlines()
    out, seen = [lines[0]], 0
    for ln in lines[1:]:
        if ",a," in ln:
            seen += 1
            if seen > 10:
                ln = ln.rsplit(",", 1)[0] + ",20000.0000"
        out.append(ln)
    (ev / "sleeve_scores.csv").write_text("\n".join(out) + "\n")
    t = pm.build(book_file(tmp_path, capital=FULL / 2), sh, ev)["sleeves"][0]["tracking"]
    assert t["shadow_pnl_usd_at_capital_usd"] == pytest.approx(11 * 10.0 + 14 * 20.0)


@pytest.mark.parametrize("kw, word", [({"skip": [3]}, "verify.json"), ({"unbooked": [3]}, "ledger_applied")])
def test_dollars_traded_are_unmeasured_when_a_session_has_no_booked_verify_file(tmp_path, kw, word):
    sh = shadow_state(tmp_path, 25)
    ev = events_state(tmp_path, 25)
    bookings(ev, 25, **kw)
    s = pm.build(book_file(tmp_path, cost_bp=25.0), sh, ev)["sleeves"][0]
    assert s["tracking"]["traded"] is None and "allowance_usd" not in s["tracking"] and "verdict" not in s["tracking"]
    assert len(s["missing"]) == 1 and word in s["missing"][0] and "2026-01-09" in s["missing"][0]


def test_the_session_a_sleeve_sells_out_on_is_a_common_session(tmp_path):
    """It ends with no position and is not a position session, but it carries that day's P&L
    and the exit's cost, so the comparison keeps every session after the first position."""
    sh = shadow_state(tmp_path, 30)
    ev = events_state(tmp_path, 22, empty_days=2)
    rows = (ev / "sleeve_scores.csv").read_text().splitlines()
    last = weekdays(25)[-1].isoformat()
    rows += [f"{last},a,0.0000,0.0000,103.0000,-7.0000,0,,,10000.0000", f"{last},_book,0.0000,0.0000,103.0000,-7.0000,0,,,"]
    (ev / "sleeve_scores.csv").write_text("\n".join(rows) + "\n")
    s = pm.build(book_file(tmp_path), sh, ev)["sleeves"][0]
    assert (s["position_sessions"], s["tracking"]["sessions_compared"], s["tracking"]["paper_pnl_usd"]) == (22, 23, 103.0)


def test_track_verdict_is_twice_the_modelled_cost_on_the_dollars_traded():
    assert pm.track_verdict(20.0, 10.0, 10_000.0) == ("PASS", 20.0)       # at the allowance passes
    assert pm.track_verdict(20.01, 10.0, 10_000.0)[0] == "FAIL"
    assert pm.track_verdict(-500.0, 0.0, 10_000.0) == ("PASS", 0.0)       # paper ahead of the shadow book
    assert pm.track_verdict(0.01, 0.0, 10_000.0)[0] == "FAIL"             # a zero model allows nothing


def test_sigma_verdict_scales_the_backtest_vol_to_the_capital_traded_at():
    """60 sessions at $10,000 and 10% a year: sigma x sqrt(T) = 10,000 x 0.1 / sqrt(252) x
    sqrt(60) = $487.95. Twenty sessions at a quarter then forty at a half use the root of the
    summed squares, not T times one capital."""
    band = 10_000 * 0.1 / 252 ** 0.5 * 60 ** 0.5
    assert band == pytest.approx(487.95, abs=0.01)
    assert pm.sigma_verdict(0.0, 0.1, [10_000] * 60) == ("FULL", pytest.approx(band))
    assert pm.sigma_verdict(-band + 0.01, 0.1, [10_000] * 60)[0] == "FULL"
    assert pm.sigma_verdict(-band - 0.01, 0.1, [10_000] * 60)[0] == "HALF"
    assert pm.sigma_verdict(-2 * band + 0.01, 0.1, [10_000] * 60)[0] == "HALF"
    assert pm.sigma_verdict(-2 * band - 0.01, 0.1, [10_000] * 60)[0] == "STOPPED"
    mixed = pm.sigma_verdict(0.0, 0.1, [10_000] * 20 + [20_000] * 40)[1]
    assert mixed == pytest.approx(0.1 / 252 ** 0.5 * (20 * 1e8 + 40 * 4e8) ** 0.5)
    for bad in ([], [10_000, 0]):
        with pytest.raises(pm.PromoteError):
            pm.sigma_verdict(0.0, 0.1, bad)


@pytest.mark.parametrize("pnl, capital, due, verdict, edit", [
    (None, FULL / 2, "FULL", pm.CHANGE, '"capital_usd": 40000.0 for a (now 20000.0)'),   # +$300: above -1 sigma
    ("-1000.0000", FULL / 2, "HALF", pm.AGREE, None),                                     # between -1 and -2
    ("-1000.0000", FULL, None, None, None),                                               # (band differs: below)
    ("-2000.0000", FULL / 2, "STOPPED", pm.CHANGE, "enabled"),                            # below -2 sigma
])
def test_sixty_sessions_reach_the_sigma_verdict(tmp_path, pnl, capital, due, verdict, edit):
    """Sixty position sessions at $20,000 and 10% a year: sigma x sqrt(T) = 20,000 x 0.1 /
    sqrt(252) x sqrt(60) = $975.90. A live P&L of +$300 is FULL, -$1,000 a HALF, -$2,000
    STOPPED, and STOPPED is the edit `enabled: false`. At $40,000 the band is $1,951.80, so
    the same -$1,000 is FULL: the band is in the dollars the sleeve traded at."""
    rep = report(tmp_path, shadow_n=60, held=60, capital=capital, pnl=pnl)
    s = rep["sleeves"][0]
    if capital == FULL:
        assert s["sigma_band_usd"] == pytest.approx(1951.80, abs=0.01) and s["stage_due"].startswith("FULL")
        assert s["verdict"] == pm.AGREE
        return
    assert s["sigma_band_usd"] == pytest.approx(975.90, abs=0.01) and s["missing"] == []
    assert s["stage_due"].startswith(due) and s["verdict"] == verdict
    if edit == "enabled":
        assert s["edits"][0].startswith('"enabled": false for a') and s["capital_due"] is None
    else:
        assert s["edits"] == ([edit] if edit else [])
    assert "sigma x sqrt(T) over the position sessions = 975.90" in pm.render(rep)


def test_capital_off_the_ladder_is_refused_naming_the_sleeve(tmp_path, capsys):
    sh = shadow_state(tmp_path, 12)
    bf = book_file(tmp_path, capital=15000.0)
    with pytest.raises(pm.PromoteError, match=r"sleeve a: capital_usd 15,000.00 is not on the ladder"):
        pm.build(bf, sh, tmp_path / "events")
    assert pm.main(["--shadow-state", str(sh), "--events-state", str(tmp_path / "events"),
                    "--book-file", str(bf)]) == pm.EXIT_REFUSED
    assert "sleeve a" in capsys.readouterr().err
    for ok in (FULL / 4, FULL / 2, FULL):
        assert pm.stage_of(pm.config.load(book_file(tmp_path, capital=ok)).sleeve("a"))


def test_a_missing_sleeve_scores_file_is_unmeasured_not_zero(tmp_path, capsys):
    """Zero sessions would read as "a quarter, AGREE". With no file nothing was measured."""
    rep = report(tmp_path)                           # no events state at all
    s = rep["sleeves"][0]
    assert s["position_sessions"] is None and s["verdict"] == pm.UNMEASURED and rep["exit_code"] == pm.EXIT_UNMEASURED
    assert "sleeve_scores.csv" in s["missing"][0] and "stage_due" not in s
    (tmp_path / "events").mkdir()                    # the directory without the file is the same
    assert pm.build(book_file(tmp_path), tmp_path / "shadow", tmp_path / "events")["sleeves"][0]["verdict"] == pm.UNMEASURED
    (tmp_path / "events" / "sleeve_scores.csv").write_text("date,slug,pnl\n")
    assert "header" in pm.build(book_file(tmp_path), tmp_path / "shadow", tmp_path / "events")["sleeves"][0]["missing"][0]
    assert pm.main(["--shadow-state", str(tmp_path / "shadow"), "--events-state", str(tmp_path / "nowhere"),
                    "--book-file", str(book_file(tmp_path)), "--json"]) == pm.EXIT_UNMEASURED
    assert json.loads(capsys.readouterr().out)["sleeves"][0]["position_sessions"] is None


def test_a_sleeve_holding_an_unmarked_name_still_counts_and_its_pnl_is_unmeasured(tmp_path):
    sh = shadow_state(tmp_path, 12)
    ev = events_state(tmp_path, 3, day_change="", pnl="")
    s = pm.build(book_file(tmp_path), sh, ev)["sleeves"][0]
    assert s["position_sessions"] == 3 and s["live_pnl_usd"] is None and "UNMEASURED" in s["live_pnl_note"]


# ------------------------------------------------------------------ the promotion gate on a listed sleeve

def test_an_enabled_sleeve_that_never_traded_and_whose_book_is_not_eligible_must_be_disabled(tmp_path):
    rep = report(tmp_path, shadow_n=9, held=0)
    s = rep["sleeves"][0]
    assert s["verdict"] == pm.CHANGE and s["edits"][0].startswith('"enabled": false for a') and rep["exit_code"] == 30
    assert report(tmp_path / "off", shadow_n=9, held=0, enabled=False)["sleeves"][0]["verdict"] == pm.AGREE


def test_the_gate_is_not_applied_again_to_a_sleeve_that_has_traded(tmp_path):
    """enabled=false flattens a sleeve with shares, and no ruling demotes on a later unclean day."""
    assert report(tmp_path, shadow_n=12, held=5, late=[11])["sleeves"][0]["verdict"] == pm.AGREE


def test_shadow_books_outside_the_file_are_listed_and_never_change_the_exit_code(tmp_path):
    sh = shadow_state(tmp_path, 12)
    shadow_state(tmp_path, 3, slug="other")
    (sh / "panels").mkdir()                          # not a book: no decisions/ inside
    (sh / "empty" / "decisions").mkdir(parents=True)  # a book that has no scores.csv yet
    rep = pm.build(book_file(tmp_path), sh, events_state(tmp_path, 0))
    assert {b["slug"]: (b["is_sleeve"], b["eligible"]) for b in rep["shadow_books"]} == {
        "a": (True, True), "other": (False, False), "empty": (False, None)}
    assert rep["exit_code"] == pm.EXIT_AGREE and "empty: UNMEASURED" in pm.render(rep)


# ------------------------------------------------------------------ read-only, and pinned to the runner

def test_the_score_header_is_the_runners():
    from quantt.sleeves import run as sr
    assert pm.SCORES_COLUMNS == sr.SCORES_COLUMNS and pm.BOOK_ROW == sr.BOOK_ROW and pm.BOOK_PATH == sr.BOOK_PATH


def test_the_report_imports_no_order_code_and_writes_nothing():
    """AST, not a run: an import inside a function counts. The report and the one repository
    module it imports may import the standard library and each other, nothing else, so no
    route exists to the broker client, run.py's send path or `shadow` (which the live path
    never imports). It also names no call that writes or removes a file."""
    root = Path(pm.__file__).parent
    for f in (root / "promote.py", root / "config.py"):
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module or "."] if isinstance(node, ast.ImportFrom) else [])
            for m in mods:
                if isinstance(node, ast.ImportFrom) and m == "quantt.sleeves":
                    assert [a.name for a in node.names] == ["config"], f"{f.name} imports {m}.{node.names[0].name}"
                    continue
                assert m.split(".")[0] in sys.stdlib_module_names, f"{f.name} imports {m}"
                assert m.split(".")[0] not in ("subprocess", "socket", "urllib", "http", "importlib", "runpy"), m
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
                {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        banned = {"write_text", "write_bytes", "unlink", "mkdir", "rmdir", "rename", "touch", "writerow",
                  "writerows", "system", "popen", "eval", "exec", "__import__", "submit_order", "cancel_order",
                  "replace_order", "close_position"}
        assert not names & banned, f"{f.name} names {names & banned}"
        for node in ast.walk(tree):                   # every open() is the default read mode
            if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) == "open":
                assert not node.args and [k.arg for k in node.keywords] == ["newline"], f"{f.name}:{node.lineno}"


def test_the_released_book_file_is_on_the_ladder():
    cfg = pm.config.load(pm.BOOK_PATH)
    assert {pm.stage_of(s) for s in cfg.sleeves} == {"QUARTER"}
