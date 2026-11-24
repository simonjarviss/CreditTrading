"""scripts/ops/data_qa.py: each check fires on its injected defect and stays silent on a clean panel.

Synthetic panels test the code, never a market claim (CLAUDE.md). Every test here fails
on origin/main, which has no scripts/ops/data_qa.py.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.ops import data_qa as q

ASOF = dt.date(2026, 11, 5)
TH = {"q2_z": 8.0, "q3_delta": 1, "q5_line": 0.5, "q6_margin": 0.05}


def clean_panels(names=("AAA", "BBB", "CCC"), days=450, end=ASOF):
    """Small independent daily NAV noise, close at a steady discount, liquid volumes."""
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=days)
    rng = np.random.default_rng(7)
    nav, close, vol = {}, {}, {}
    for i, t in enumerate(names):
        n = 20.0 * np.exp(np.cumsum(rng.normal(0, 0.003, days)))
        nav[t] = np.round(n, 2)
        close[t] = np.round(n * (0.92 + 0.002 * i), 2)
        vol[t] = np.full(days, 2.0e5 + 5e4 * i)
    return q.Panels(pd.DataFrame(close, index=idx), pd.DataFrame(vol, index=idx), pd.DataFrame(nav, index=idx))


def run(p, *, universe=None, thresholds=TH, plan=None, plan_path=None, splits=None, seed_dir=None, asof=ASOF,
        expected=ASOF, min_names=2, floor=1e5, tmp=Path(".")):
    spec = {"frozen": {"min_adv_usd": floor, "min_names": min_names}}
    return q.run_checks("t", p, universe or list(p.nav.columns), thresholds, asof, expected, spec, plan, plan_path,
                        splits, seed_dir, data_dir=tmp)


def test_a_clean_panel_flags_nothing():
    res = run(clean_panels())
    assert {k: v["status"] for k, v in res.items() if k not in ("Q7", "Q8")} == \
        {"Q1": "OK", "Q2": "OK", "Q3": "OK", "Q4": "OK", "Q5": "OK", "Q6": "OK"}
    assert res["Q7"]["status"] == "UNMEASURED" and "plan" in res["Q7"]["why"]
    assert res["Q8"]["status"] == "NOT_RUN" and "seed" in res["Q8"]["why"]


# ------------------------------------------------------------------ Q1

def test_q1_flags_a_stale_panel_once_not_per_name():
    p = clean_panels(end=dt.date(2026, 11, 4))
    res = run(p)
    assert res["Q1"]["status"] == "FLAG"
    assert len([f for f in res["Q1"]["flags"] if f["ticker"] is None and "last date" in f["rule"]]) == 2
    assert not [f for f in res["Q1"]["flags"] if f["ticker"]]


def test_q1_flags_a_name_whose_own_series_lags():
    p = clean_panels()
    p.nav.iloc[-1, 1] = np.nan                   # BBB's NAV is missing tonight (the 2026-10-22 shape)
    res = run(p)
    flagged = [f for f in res["Q1"]["flags"] if f["ticker"] == "BBB"]
    assert flagged and "NAV" in flagged[0]["rule"] and res["Q1"]["status"] == "FLAG"
    assert any("row count" in f["rule"] and f["evidence"]["panel"] == "NAV" for f in res["Q1"]["flags"])


# ------------------------------------------------------------------ Q2

def misprint(p, name="AAA", at=-5, factor=1.2):
    i = p.nav.index[at]
    p.nav.loc[i, name] = round(p.nav.loc[i, name] * factor, 2)


def test_q2_flags_a_reverting_misprint_and_marks_it_confirmed():
    p = clean_panels()
    misprint(p, at=-2)
    res = run(p)
    f = [x for x in res["Q2"]["flags"] if x["ticker"] == "AAA"]
    assert res["Q2"]["status"] == "FLAG" and len(f) == 1
    assert f[0]["confirmed"] is True and f[0]["date"] == str(p.nav.index[-2].date())
    # the reversion step the next day is the same event, not a second flag
    assert len(res["Q2"]["flags"]) == 1


def test_q2_flags_tonights_row_as_suspect_before_it_can_revert():
    p = clean_panels()
    misprint(p, at=-1)
    res = run(p)
    f = res["Q2"]["flags"]
    assert len(f) == 1 and f[0]["confirmed"] is False and "open" in f[0]["rule"]


def test_q2_ignores_a_nav_move_the_close_followed():
    p = clean_panels()
    i = p.nav.index[-2]
    p.nav.loc[i, "AAA"] = round(p.nav.loc[i, "AAA"] * 1.2, 2)
    p.close.loc[i, "AAA"] = round(p.close.loc[i, "AAA"] * 1.2, 2)
    assert run(p)["Q2"]["status"] == "OK"


def test_q2_uses_only_rows_before_t_for_its_scale():
    """No lookahead: changing NAVs AFTER t cannot change t's z (a candidate exists at t)."""
    p = clean_panels()
    misprint(p, at=-60)
    c1 = q.q2_candidates(p.nav.iloc[:-30], p.close)
    p2 = clean_panels()
    misprint(p2, at=-60)
    p2.nav.iloc[-20:] = p2.nav.iloc[-20:] * 3.0
    c2 = q.q2_candidates(p2.nav, p2.close)
    t = p.nav.index[-60]
    z1 = c1[(c1["ticker"] == "AAA") & (c1["date"] == t)]["z"].iloc[0]
    z2 = c2[(c2["ticker"] == "AAA") & (c2["date"] == t)]["z"].iloc[0]
    assert z1 == z2


# ------------------------------------------------------------------ Q3

def test_q3_flags_a_run_longer_than_the_name_has_had():
    p = clean_panels()
    freeze = p.nav.index[-12:]
    p.nav.loc[freeze, "AAA"] = p.nav.loc[freeze[0], "AAA"]
    res = run(p)
    assert res["Q3"]["status"] == "FLAG" and res["Q3"]["flags"][0]["ticker"] == "AAA"
    assert res["Q3"]["flags"][0]["value"] == 11


def test_q3_does_not_flag_a_run_the_name_has_had_before():
    p = clean_panels()
    # the same frozen stretch, twelve rows long, a year ago, sets the name's own norm
    old = p.nav.index[-200:-188]
    p.nav.loc[old, "AAA"] = p.nav.loc[old[0], "AAA"]
    freeze = p.nav.index[-12:]
    p.nav.loc[freeze, "AAA"] = p.nav.loc[freeze[0], "AAA"]
    assert run(p)["Q3"]["status"] == "OK"


# ------------------------------------------------------------------ Q4

def step(p, name="BBB", factor=3.0):
    i = p.close.index[-2]
    p.close.loc[i:, name] = p.close.loc[i:, name] * factor
    p.nav.loc[i:, name] = p.nav.loc[i:, name] * factor


def test_q4_flags_a_split_like_step_with_no_corporate_action_row():
    p = clean_panels()
    step(p)
    res = run(p, splits=None)
    assert res["Q4"]["status"] == "FLAG"
    f = res["Q4"]["flags"]
    assert {x["evidence"]["series"] for x in f} == {"close", "nav"} and f[0]["ticker"] == "BBB"
    assert all(abs(x["threshold"] - 3.0) < 1e-9 for x in f)
    assert "no corporate-action file" in f[0]["rule"]


def test_q4_is_silent_when_a_corporate_action_row_names_the_step():
    p = clean_panels()
    step(p)
    sp = pd.DataFrame({"ticker": ["BBB"], "ex_date": [p.close.index[-2]]})
    assert run(p, splits=sp)["Q4"]["status"] == "OK"


# ------------------------------------------------------------------ Q5

def test_q5_flags_a_discount_past_the_line():
    p = clean_panels()
    d = p.nav.index[-1]
    p.nav.loc[d, "CCC"] = round(p.close.loc[d, "CCC"] / 1.75, 2)    # a +75% discount (BME 2021-06-28's shape)
    res = run(p, thresholds={**TH, "q2_z": 1e9})
    assert res["Q5"]["status"] == "FLAG" and res["Q5"]["flags"][0]["ticker"] == "CCC"
    assert res["Q5"]["flags"][0]["value"] > 0.5


def test_q5_flags_a_crossing_once_and_names_a_standing_excursion():
    p = clean_panels()
    d = p.nav.index[-2:]
    p.nav.loc[d, "CCC"] = (p.close.loc[d, "CCC"] / 1.75).round(2)    # past the line on both of the last two days
    res = run(p, thresholds={**TH, "q2_z": 1e9})
    assert res["Q5"]["status"] == "OK" and "CCC" in res["Q5"]["why"] and "standing" in res["Q5"]["why"]


# ------------------------------------------------------------------ Q6

def test_q6_flags_when_an_adv_dip_would_leave_the_sleeve_below_min_names():
    p = clean_panels(names=("A", "B", "C"))
    p.volume["A"] = 1.03e5 / p.close["A"]        # ADV about 1.03x the floor (the margin is 5%)
    p.volume["B"] = 1.04e5 / p.close["B"]        # 1.04x
    res = run(p, min_names=3, floor=1e5)
    assert res["Q6"]["status"] == "FLAG" and res["Q6"]["flags"][0]["value"] == 1.0


def test_q6_is_silent_when_the_sleeve_is_already_below_min_names():
    p = clean_panels(names=("A", "B", "C"))
    p.volume["A"] = 1.03e5 / p.close["A"]
    p.volume["B"] = 0.5e5 / p.close["B"]         # below the floor: already thin
    p.volume["C"] = 0.5e5 / p.close["C"]
    assert run(p, min_names=3, floor=1e5)["Q6"]["status"] == "OK"


# ------------------------------------------------------------------ Q7

UNRESOLVED_IDS = ("db0847b7-9523-4b2f-afba-ae51ddb77ec5", "e34ddd44-1ed2-4b30-b668-be3f16e11dce",
                  "6abeb209-f747-4bf3-a231-67b8c0984d4a")


def plan_with(ca):
    return {"asof": ASOF.isoformat(), "targets": {"AAA": {"target": 1}}, "orders": [], "corporate_actions": ca}


def test_q7_flags_the_three_unresolved_rows_by_id():
    ca = {"status": "CLEAR", "blocking": [],
          "unresolved": [{"id": i, "row_id": f"r{i[:4]}", "type": t, "date": "2026-11-02", "date_field": "process_date",
                          "parties": {"symbol": None}, "missing": ["symbol"], "blocks": False, "acknowledged": False}
                         for i, t in zip(UNRESOLVED_IDS, ("partial_call", "spin_off", "stock_merger"))]}
    res = run(clean_panels(), plan=plan_with(ca), plan_path="p.json")
    assert res["Q7"]["status"] == "FLAG"
    assert {f["evidence"]["id"] for f in res["Q7"]["flags"]} == set(UNRESOLVED_IDS)


def test_q7_flags_a_blocking_event_and_marks_it_held():
    ca = {"status": "BLOCKING", "blocking": [{"id": "x", "symbol": "AAA", "type": "reverse_split", "date": "2026-11-04",
                                              "date_field": "ex_date", "role": "held", "held": True}]}
    res = run(clean_panels(), plan=plan_with(ca), plan_path="p.json")
    assert res["Q7"]["status"] == "FLAG" and res["Q7"]["flags"][0]["held"] is True and res["Q7"]["n_held"] == 1


def test_q7_clear_is_ok_and_a_gate_that_could_not_see_is_unmeasured():
    assert run(clean_panels(), plan=plan_with({"status": "CLEAR", "blocking": []}))["Q7"]["status"] == "OK"
    res = run(clean_panels(), plan=plan_with({"status": "UNMEASURED", "why": "fetch 503"}), plan_path="p.json")
    assert res["Q7"]["status"] == "UNMEASURED" and "fetch 503" in res["Q7"]["why"]


# ------------------------------------------------------------------ Q8

def write_seed(dirpath: Path, p: q.Panels):
    px = p.close.stack().rename("close").reset_index().rename(columns={"level_0": "date", "level_1": "ticker"})
    px.columns = ["date", "ticker", "close"]
    px.to_parquet(dirpath / "cef_prices.parquet")
    nv = p.nav.stack().rename("nav").reset_index()
    nv.columns = ["date", "ticker", "nav"]
    nv.to_parquet(dirpath / "cef_nav.parquet")


def test_q8_flags_a_row_the_fetch_replaced_beyond_rounding(tmp_path):
    p = clean_panels()
    write_seed(tmp_path, p)
    p.close.loc[p.close.index[-3], "AAA"] += 0.02
    res = run(p, seed_dir=tmp_path)
    assert res["Q8"]["status"] == "FLAG" and res["Q8"]["n_flags"] == 1
    assert res["Q8"]["flags"][0]["ticker"] == "AAA"


def test_q8_passes_within_half_a_cent_and_is_not_run_without_a_seed(tmp_path):
    p = clean_panels()
    write_seed(tmp_path, p)
    p.close.loc[p.close.index[-3], "AAA"] += 0.004
    assert run(p, seed_dir=tmp_path)["Q8"]["status"] == "OK"
    assert run(p, seed_dir=None)["Q8"]["status"] == "NOT_RUN"
    res = run(p, seed_dir=tmp_path / "absent")
    assert res["Q8"]["status"] == "UNMEASURED" and "absent" in res["Q8"]["why"]


# ------------------------------------------------------------------ the report, and missing inputs

def test_held_tagging_uses_the_latest_plan():
    p = clean_panels()
    misprint(p, at=-2)
    res = run(p, plan=plan_with({"status": "CLEAR", "blocking": []}))
    assert res["Q2"]["flags"][0]["held"] is True
    res2 = run(p, plan={**plan_with({"status": "CLEAR", "blocking": []}), "targets": {"BBB": {}}})
    assert res2["Q2"]["flags"][0]["held"] is False


def test_q8_not_run_does_not_make_the_night_unmeasured():
    res = {"Q1": {"status": "OK"}, "Q8": {"status": "NOT_RUN"}}
    assert q.overall(res) == "OK"


def test_main_writes_the_report_outside_the_data_dir_and_names_a_missing_panel(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    rc = q.main(["--book", "cef", "--state-dir", str(state), "--data-dir", str(tmp_path / "nope"),
                 "--asof", ASOF.isoformat()], now_utc=dt.datetime(2026, 11, 6, 2, 45, tzinfo=dt.timezone.utc))
    assert rc == 0
    rep = json.loads((state / "reports" / "data_qa" / f"{ASOF}.json").read_text())
    assert rep["status"] == "UNMEASURED"
    assert all(rep["checks"][k]["status"] == "UNMEASURED" for k in q.CHECK_IDS)
    assert "cef_prices.parquet" in rep["checks"]["Q1"]["why"]
    assert (state / "reports" / "data_qa" / f"{ASOF}.md").is_file()


def test_a_missing_threshold_is_unmeasured_and_named():
    res = run(clean_panels(), thresholds={"q3_delta": 1, "q5_line": 0.5, "q6_margin": 0.05})
    assert res["Q2"]["status"] == "UNMEASURED" and "q2_z" in res["Q2"]["why"]


def test_expected_day_is_the_newest_settled_trading_day():
    et = q.ET
    assert q.expected_day(dt.datetime(2026, 11, 5, 21, 45, tzinfo=et)) == dt.date(2026, 11, 5)
    assert q.expected_day(dt.datetime(2026, 11, 5, 16, 30, tzinfo=et)) == dt.date(2026, 11, 4)
    assert q.expected_day(dt.datetime(2026, 11, 7, 21, 45, tzinfo=et)) == dt.date(2026, 11, 6)      # Saturday


def test_thresholds_are_the_calibration_outputs():
    """The constants in data_qa.py are the calibration run's values, not retyped ones."""
    cal = json.loads((q.REPO / "results/ops/data_qa_calibration/calibration_2026-11-08.json").read_text())
    assert cal["thresholds"] == q.THRESHOLDS


# ------------------------------------------------------------------ Q9: the NAV cross-check's second source
# Each test below fails on 8cac532 (origin/main, 2026-11-18): data_qa had no Q9, so a
# collector report that said "second source unavailable" left the night's QA status
# untouched. The report shape is quantt/collect/collect.py `build_report`'s.

UNAVAILABLE = "second source unavailable (cefconnect: JSONDecodeError)"


def collector_report(state: Path, day: dt.date, step: dict | None, *, raw: str | None = None):
    d = state / "data" / day.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    steps = {"prices_nav": {"ok": True, "err": None, "detail": {"flags": [], "gaps": []}}}
    if step is not None:
        steps["nav_crosscheck"] = step
    rep = {"date": day.isoformat(), "book": "cef", "complete": True, "failed_steps": [],
           "flags": [], "gaps": [], "steps": steps}
    (d / "report.json").write_text(raw if raw is not None else json.dumps(rep))


def down():
    return {"ok": False, "err": UNAVAILABLE, "unavailable": UNAVAILABLE,
            "detail": {"flags": [], "gaps": [], "fetch_errors": ["x"], "second_source": UNAVAILABLE}}


def up():
    return {"ok": True, "err": None, "detail": {"flags": [], "gaps": [], "fetch_errors": []}}


def test_q9_flags_an_unavailable_second_source_and_counts_the_days(tmp_path):
    # 2026-11-05 is a Thursday: 11-02..11-05 down (4 sessions), 10-30 (Friday) up.
    collector_report(tmp_path, dt.date(2026, 10, 30), up())
    for day in (2, 3, 4, 5):
        collector_report(tmp_path, dt.date(2026, 11, day), down())
    st, flags, why = q.q9_second_source(tmp_path, ASOF, "nav_crosscheck")
    assert st == "FLAG" and why is None and len(flags) == 1
    f = flags[0]
    assert f.check == "Q9" and f.ticker is None and f.value == 4.0
    assert UNAVAILABLE in f.rule and "4 consecutive" in f.rule and "since 2026-11-02" in f.rule
    assert "at least" not in f.rule
    assert f.evidence["first_day"] == "2026-11-02" and f.evidence["count_is_lower_bound"] is False


def test_q9_streak_is_a_lower_bound_when_an_earlier_report_is_missing(tmp_path):
    collector_report(tmp_path, dt.date(2026, 11, 4), down())
    collector_report(tmp_path, ASOF, down())                     # no report for 11-03
    st, flags, _ = q.q9_second_source(tmp_path, ASOF, "nav_crosscheck")
    f = flags[0]
    assert st == "FLAG" and f.value == 2.0 and "at least 2 consecutive" in f.rule
    assert f.evidence["count_is_lower_bound"] is True and "2026-11-03" in f.evidence["walk_stopped_at"]


def test_q9_is_ok_only_when_the_collector_says_the_step_was_ok(tmp_path):
    collector_report(tmp_path, ASOF, up())
    assert q.q9_second_source(tmp_path, ASOF, "nav_crosscheck") == ("OK", [], None)


def test_q9_flags_a_crosscheck_that_did_not_complete(tmp_path):
    collector_report(tmp_path, ASOF, {"ok": False, "err": "waiting on prices_nav",
                                      "detail": {"flags": [], "gaps": []}})
    st, flags, _ = q.q9_second_source(tmp_path, ASOF, "nav_crosscheck")
    assert st == "FLAG" and "waiting on prices_nav" in flags[0].rule and "did not complete" in flags[0].rule


def test_q9_missing_or_unreadable_record_is_unmeasured_and_named_never_ok(tmp_path):
    st, flags, why = q.q9_second_source(tmp_path, ASOF, "nav_crosscheck")
    assert st == "UNMEASURED" and not flags and "report.json" in why and str(ASOF) in why
    collector_report(tmp_path, ASOF, None)                       # a report with no such step
    st, _, why = q.q9_second_source(tmp_path, ASOF, "nav_crosscheck")
    assert st == "UNMEASURED" and "no nav_crosscheck step" in why
    collector_report(tmp_path, ASOF, None, raw="{not json")
    st, _, why = q.q9_second_source(tmp_path, ASOF, "nav_crosscheck")
    assert st == "UNMEASURED" and "unreadable" in why


def test_q9_is_not_run_for_a_book_with_no_second_source_by_ruling(tmp_path):
    assert q.BOOKS["c4"].second_source_step is None and q.BOOKS["cef"].second_source_step == "nav_crosscheck"
    st, flags, why = q.q9_second_source(tmp_path, ASOF, None)
    assert st == "NOT_RUN" and not flags and "single-source" in why


def test_main_reports_the_unavailable_second_source_in_the_nightly_report(tmp_path):
    """The defect itself: on 8cac532 this night's report had no Q9 and no line about
    the second source, whatever the collector had recorded."""
    state = tmp_path / "state"
    collector_report(state, ASOF, down())
    rc = q.main(["--book", "cef", "--state-dir", str(state), "--data-dir", str(tmp_path / "nope"),
                 "--asof", ASOF.isoformat()], now_utc=dt.datetime(2026, 11, 6, 2, 45, tzinfo=dt.timezone.utc))
    assert rc == 0
    rep = json.loads((state / "reports" / "data_qa" / f"{ASOF}.json").read_text())
    assert rep["checks"]["Q9"]["status"] == "FLAG" and rep["status"] == "FLAG"
    md = (state / "reports" / "data_qa" / f"{ASOF}.md").read_text()
    assert "**Q9**: FLAG" in md and UNAVAILABLE in md and "single-source NAVs" in md
