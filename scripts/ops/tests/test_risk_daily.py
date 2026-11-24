"""scripts/ops/risk_daily.py: the wrappers reproduce the readers, and an ACT is never silent.

Fixtures are synthetic state directories; nothing opens a socket. Every test fails on
origin/main, which has no scripts/ops/risk_daily.py.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

import pytest

from quantt.session import drawdown as dd
from scripts.ops import risk_daily as r
from scripts.ops import report_notify as rn

ASOF = dt.date(2026, 11, 5)
SPEC = {"spec_id": "x.v1", "risk": {"halve_drawdown": 0.12, "kill_drawdown": 0.18},
        "frozen": {"max_gross_stress": 1.9, "sizing_multiplier": 1.26}}


def write_csv(path: Path, header, rows):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture
def state(tmp_path):
    st = tmp_path / "quantt_state" / "cef"
    st.mkdir(parents=True)
    days = [ASOF - dt.timedelta(days=k) for k in (4, 3, 2, 1, 0)]
    equity = [100000, 100500, 100200, 99800, 100100]
    write_csv(st / "eod_equity.csv", ["date", "equity", "change_usd", "read_at_utc"],
              [[d.isoformat(), e, "", "x"] for d, e in zip(days, equity)])
    write_csv(st / "equity.csv", ["date", "equity", "last_equity", "cash", "long_market_value", "short_market_value",
                                  "n_positions", "read_at_utc"],
              [[d.isoformat(), e + 50, e, 0, 0, 0, 3, "x"] for d, e in zip(days, equity)])
    write_csv(st / "scores.csv", ["date", "book", "verdict", "traded", "n_orders", "n_filled", "auction_pnl_usd"],
              [[d.isoformat(), "cef", "PASS", "True", 5, 5, "12.00"] for d in days])
    write_csv(st / "tca.csv", ["date", "book", "n_orders", "n_full", "fill_rate_shares", "slip_bp_all"],
              [[ASOF.isoformat(), "cef", 5, 5, "1.0000", "4.20"]])
    d = st / "data" / ASOF.isoformat()
    d.mkdir(parents=True)
    positions = [{"symbol": "HQH", "market_value": "-20000", "qty": "-1000", "side": "short"},
                 {"symbol": "AAA", "market_value": "30000", "qty": "1000", "side": "long"},
                 {"symbol": "BBB", "market_value": "-10000", "qty": "-500", "side": "short"},
                 {"symbol": "CCC", "market_value": "5000", "qty": "100", "side": "long"}]
    (d / "account.json").write_text(json.dumps({
        "date": ASOF.isoformat(), "read_at_utc": f"{ASOF.isoformat()}T21:10:04+00:00",
        "account": {"equity": "100000", "maintenance_margin": "30000"},
        "positions": {"qty": {"HQH": -1000}, "raw": positions}}))
    pd = st / ASOF.isoformat()
    pd.mkdir()
    (pd / "plan.json").write_text(json.dumps({"status": "decided", "orders": [{"symbol": "AAA"}],
                                              "refusals": [], "notes": {}, "targets": {"AAA": {}}}))
    return st


def test_drawdown_block_reproduces_the_reader_byte_for_byte(state):
    rec = dd.check(state, SPEC, ASOF, dd.REPORT)
    b = r.drawdown_block(state, SPEC, ASOF)
    assert b["data"]["reading"]["drawdown"] == rec["reading"]["drawdown"]
    assert [ln for ln in b["lines"] if ln in dd.lines(rec)] == dd.lines(rec)


def test_drawdown_block_acts_on_a_breached_line(state):
    write_csv(state / "eod_equity.csv", ["date", "equity", "change_usd", "read_at_utc"],
              [["2026-11-03", 100000, "", "x"], [ASOF.isoformat(), 85000, "", "x"]])
    b = r.drawdown_block(state, SPEC, ASOF)
    assert b["status"] == r.ACT and b["lines"][0].startswith("ACT: HALVE line reached")


def test_drawdown_block_acts_on_a_stale_row_and_says_so_and_carries_the_followup(state):
    write_csv(state / "eod_equity.csv", ["date", "equity", "change_usd", "read_at_utc"],
              [["2026-11-03", 100000, "", "x"], ["2026-11-04", 85000, "", "x"]])
    b = r.drawdown_block(state, SPEC, ASOF)
    assert b["status"] == r.ACT and "(stale)" in b["lines"][0]
    assert any("stale" in ln and "2026-11-04" in ln for ln in b["lines"])
    assert r.FOLLOWUP_DRAWDOWN in b["lines"]


def test_a_missing_input_is_unmeasured_and_named(tmp_path):
    st = tmp_path / "empty"
    st.mkdir()
    rep, code = r.run_report("cef", st, ASOF, now_utc=dt.datetime(2026, 11, 6, 3, 15, tzinfo=dt.timezone.utc))
    assert code == 0
    b = rep["blocks"]
    assert b["pnl"]["status"] == r.UNMEASURED and "eod_equity.csv" in " ".join(b["pnl"]["lines"])
    assert b["drawdown"]["status"] == r.UNMEASURED and "eod_equity.csv" in " ".join(b["drawdown"]["lines"])
    assert b["kill_rules"]["status"] == r.UNMEASURED and "scores.csv" in " ".join(b["kill_rules"]["lines"])
    assert b["exposure"]["status"] == r.UNMEASURED and "account.json" in " ".join(b["exposure"]["lines"])
    assert b["data_qa"]["status"] == r.UNMEASURED
    assert b["stops"]["status"] == r.UNMEASURED and "SCRATCH" in " ".join(b["stops"]["lines"])
    assert (st / "reports" / "risk" / f"{ASOF}.md").is_file()


def test_stops_block_passes_stops_py_output_through_verbatim(tmp_path):
    out = "core account x1.3 (from 2013-06-25): R1 D_R 10.14% (...) | R2 -3.06% | R3 12.07%\n"
    f = tmp_path / "stops_output.txt"
    f.write_text(out)
    b = r.stops_block("cef", {"frozen": {"sizing_multiplier": 1.3}}, f)
    assert b["status"] == r.INFO and b["lines"][1:] == [out.strip()] and b["data"]["stdout"] == out
    assert "not tonight" in b["lines"][0]


def test_stops_block_is_unmeasured_and_names_the_missing_series(tmp_path):
    b = r.stops_block("c4", {"frozen": {"sizing_multiplier": 1.26}}, None)
    assert b["status"] == r.UNMEASURED and "SCRATCH" in b["lines"][0] and "stops.py" in b["lines"][0]
    assert "--only c4" in b["lines"][0]
    b2 = r.stops_block("c4", {"frozen": {"sizing_multiplier": 1.26}}, tmp_path / "absent.txt")
    assert b2["status"] == r.UNMEASURED


def test_concentration_figures_on_a_fixture():
    raw = [{"symbol": "HQH", "market_value": "-20000", "side": "short"},
           {"symbol": "AAA", "market_value": "30000", "side": "long"},
           {"symbol": "BBB", "market_value": "-10000", "side": "short"},
           {"symbol": "CCC", "market_value": "5000", "side": "long"}]
    c = r.concentration(raw, 100000.0, {"HQH": "health", "AAA": "health", "BBB": "muni"})
    assert c["largest"] == {"symbol": "AAA", "share": 0.30, "signed": 0.30, "side": "long"}
    assert c["top3_share"] == pytest.approx(0.60)
    assert {x["symbol"]: x["share"] for x in c["per_name"]} == {"AAA": 0.30, "HQH": 0.20, "BBB": 0.10, "CCC": 0.05}
    assert c["group_share"] == {"health": pytest.approx(0.5), "muni": pytest.approx(0.1), "unknown": pytest.approx(0.05)}


def test_exposure_block_reports_gross_net_and_concentration_and_never_acts(state, monkeypatch):
    monkeypatch.setattr(r, "group_map", lambda b: ({}, None))
    b = r.exposure_block("cef", state, SPEC, ASOF)
    assert b["status"] == r.INFO
    assert b["data"]["gross"] == pytest.approx(0.65) and b["data"]["net"] == pytest.approx(0.05)
    assert b["data"]["maintenance_to_equity"] == pytest.approx(0.30)
    assert b["data"]["concentration"]["largest"]["symbol"] == "AAA"
    assert any("Concentration is measured" in ln for ln in b["lines"])


def test_exposure_watch_within_a_declared_distance_of_the_cap(state, monkeypatch):
    monkeypatch.setattr(r, "group_map", lambda b: ({}, None))
    spec = {**SPEC, "frozen": {"max_gross_stress": 0.66}}
    assert r.exposure_block("cef", state, spec, ASOF)["status"] == r.WATCH


def test_kill_rule_a_fires_at_60_sessions_with_a_negative_sharpe(state, monkeypatch):
    days = [ASOF - dt.timedelta(days=k) for k in range(70, -1, -1)]
    write_csv(state / "scores.csv", ["date", "book", "verdict", "traded", "n_orders", "n_filled", "auction_pnl_usd"],
              [[d.isoformat(), "cef", "PASS", "True", 5, 5, "0"] for d in days])
    eq = [100000 - 10 * i for i in range(len(days))]
    write_csv(state / "eod_equity.csv", ["date", "equity", "change_usd", "read_at_utc"],
              [[d.isoformat(), e, "", "x"] for d, e in zip(days, eq)])
    b = r.kill_rules_block("cef", state, {"frozen": {}}, ASOF)
    assert b["status"] == r.ACT and any(ln.startswith("ACT: core kill rule (a)") for ln in b["lines"])


def test_kill_rule_is_not_due_before_60_sessions(state):
    b = r.kill_rules_block("cef", state, {"frozen": {}}, ASOF)
    assert b["status"] == r.INFO and any("not due (5/60)" in ln for ln in b["lines"])


def test_c4_kill_rules_are_unmeasured_and_named_until_their_inputs_exist(state):
    b = r.kill_rules_block("c4", state, {"frozen": {}}, ASOF)
    text = " ".join(b["lines"])
    assert "not due (5/120)" in text and "h11_reference" in text and "L1" in text


def test_data_qa_flag_on_a_held_name_is_a_watch(state):
    p = state / "reports" / "data_qa"
    p.mkdir(parents=True)
    (p / f"{ASOF}.json").write_text(json.dumps({"status": "FLAG", "checks": {"Q2": {"flags": [
        {"check": "Q2", "ticker": "AAA", "date": str(ASOF), "rule": "NAV move", "held": True}]}}}))
    b = r.data_qa_block(state, ASOF)
    assert b["status"] == r.WATCH and "AAA" in b["lines"][0]


def test_a_fired_stop_with_no_channel_exits_non_zero_and_says_so(state, capsys):
    write_csv(state / "eod_equity.csv", ["date", "equity", "change_usd", "read_at_utc"],
              [["2026-11-03", 100000, "", "x"], [ASOF.isoformat(), 80000, "", "x"]])
    rep, code = r.run_report("cef", state, ASOF, now_utc=dt.datetime(2026, 11, 6, 3, 15, tzinfo=dt.timezone.utc),
                             send=lambda s, b: "not configured -- add ALERT_SMTP_USER and ALERT_SMTP_PASS")
    assert code == rn.EXIT_ACT_UNDELIVERED and code != 0
    err = capsys.readouterr().err
    assert "ACT: notification NOT delivered: not configured" in err
    assert rep["severity"] == r.ACT
    assert any(ln.startswith("ACT: notification NOT delivered: not configured") for ln in rep["act_lines"])
    md = (state / "reports" / "risk" / f"{ASOF}.md").read_text()
    assert "ACT: notification NOT delivered: not configured" in md


def test_a_fired_stop_with_a_channel_is_delivered_and_exits_zero(state):
    write_csv(state / "eod_equity.csv", ["date", "equity", "change_usd", "read_at_utc"],
              [["2026-11-03", 100000, "", "x"], [ASOF.isoformat(), 80000, "", "x"]])
    sent = []
    rep, code = r.run_report("cef", state, ASOF, now_utc=dt.datetime(2026, 11, 6, 3, 15, tzinfo=dt.timezone.utc),
                             send=lambda s, b: sent.append((s, b)) or True)
    assert code == 0 and len(sent) == 1 and "ACT" in sent[0][0] and rep["notification"]["delivered"] is True


def test_no_act_means_no_notification_at_all(state):
    sent = []
    _, code = r.run_report("cef", state, ASOF, now_utc=dt.datetime(2026, 11, 6, 3, 15, tzinfo=dt.timezone.utc),
                           send=lambda s, b: sent.append(1) or True)
    assert code == 0 and sent == []


def test_notify_test_reports_delivery_and_writes_no_report(tmp_path, capsys):
    st = tmp_path / "quantt_state" / "cef"
    st.mkdir(parents=True)
    assert r.main(["--book", "cef", "--state-dir", str(st), "--notify-test"], send=lambda s, b: True) == 0
    assert not (st / "reports").exists()
    rc = r.main(["--book", "cef", "--state-dir", str(st), "--notify-test"], send=lambda s, b: "not configured")
    assert rc == rn.EXIT_ACT_UNDELIVERED and "NOT delivered: not configured" in capsys.readouterr().err


def test_a_raising_channel_is_recorded_not_a_crash():
    res = rn.notify_act(["ACT: x"], book="cef", asof=ASOF, report_path="p",
                        send=lambda s, b: (_ for _ in ()).throw(OSError("smtp down")))
    assert res["delivered"] is False and "smtp down" in res["reason"]


def test_a_blocks_own_bug_is_unmeasured_and_the_others_still_run(state, monkeypatch):
    monkeypatch.setattr(r, "pnl_block", lambda *a: (_ for _ in ()).throw(ValueError("bad row")))
    rep, code = r.run_report("cef", state, ASOF, now_utc=dt.datetime(2026, 11, 6, 3, 15, tzinfo=dt.timezone.utc))
    assert rep["blocks"]["pnl"]["status"] == r.UNMEASURED and "ValueError" in rep["blocks"]["pnl"]["lines"][0]
    assert rep["blocks"]["exposure"]["status"] != r.UNMEASURED
    assert code == 0


# --- the P&L job's report (team lead, 2026-11-09) --------------------------------------

REBUILD = {"HQH": -1000}     # the fill rebuild's positions at the as-of close, the fixture's account record's own


def _pnl(state, *, reconciled=True, factor_status="OK", review="REVIEW", rebuild=REBUILD, session=ASOF):
    """The P&L job's JSON for the as-of. `rebuild` is the job's `rebuild_positions` qty at the
    as-of close (None: a JSON without the field, a job from before the third review of PR #82).
    `session` is the session the job read (`effective_session`, the factor block's close): the
    as-of, or an earlier one when Alpaca's EOD history had no point for the as-of yet."""
    d = state / "reports" / "pnl"
    d.mkdir(parents=True, exist_ok=True)
    rep = {"book": "cef", "asof": ASOF.isoformat(), "status": "OK",
           "attribution": {"status": "OK", "reconciled": reconciled, "first_trade": "2026-09-29",
                           "effective_session": session.isoformat(),
                           "lines": ["Session 2026-11-05: official +12.00; hold +10.00 = NAV part +4.00 + discount part +6.00",
                                     "Cumulative from the first trade (2026-09-29, 26 sessions): official -100.00"]
                           + (["RECONCILIATION FAILED on 1 session(s): 2026-10-01 residual +5.00. ..."] if not reconciled else [])},
           "factor": {"status": factor_status, "headline": "MUNI",
                      "lines": [f"MUNI (headline): E -30,000 USD (-0.300 of equity), c/target 0.25, t -1.0: {review}; "
                                "REVIEW on 3 of 20 date(s) so far"]}}
    if factor_status != "UNMEASURED":
        rep["factor"]["asof"] = session.isoformat()
    if rebuild is not None:
        rep["factor"]["rebuild_positions"] = {"session": session.isoformat(), "qty": rebuild, "source": "the fill rebuild"}
    (d / f"{ASOF.isoformat()}.json").write_text(json.dumps(rep))


def test_attribution_and_factor_blocks_are_unmeasured_and_named_without_the_job_report(state):
    blocks = {"a": r.attribution_block("cef", state, ASOF), "f": r.factor_block("cef", state, ASOF)}
    for b in blocks.values():
        assert b["status"] == r.UNMEASURED and "no P&L report at" in b["lines"][0] and ASOF.isoformat() in b["lines"][0]


def test_attribution_and_factor_blocks_read_the_jobs_json(state):
    _pnl(state)
    a = r.attribution_block("cef", state, ASOF)
    f = r.factor_block("cef", state, ASOF)
    assert a["status"] == r.INFO and a["lines"][0].startswith("Session 2026-11-05")
    assert f["status"] == r.INFO and f["lines"][0].startswith(f"Factor exposure at the close of {ASOF}, cross-checked")
    assert "MUNI (headline)" in f["lines"][1] and "REVIEW" in f["lines"][1]


def test_a_review_breach_never_reaches_act_or_the_notifier(state, tmp_path):
    _pnl(state, review="REVIEW")
    sent = []
    rep, code = r.run_report("cef", state, ASOF, now_utc=dt.datetime(2026, 11, 6, 3, 30, tzinfo=dt.timezone.utc),
                             send=lambda *a: sent.append(a) or True)
    assert code == 0 and rep["blocks"]["factor_exposure"]["status"] == r.INFO
    assert "REVIEW" in rep["blocks"]["factor_exposure"]["lines"][1]
    assert not rep["act_lines"] and rep["notification"] is None and sent == []


def test_an_unreconciled_attribution_is_a_watch_not_an_act(state):
    _pnl(state, reconciled=False)
    a = r.attribution_block("cef", state, ASOF)
    assert a["status"] == r.WATCH and any(ln.startswith("RECONCILIATION FAILED") for ln in a["lines"])
    assert not any(ln.startswith("ACT") for ln in a["lines"])


def test_a_factor_block_the_job_could_not_measure_stays_unmeasured_not_info(state):
    _pnl(state, factor_status="UNMEASURED")
    assert r.factor_block("cef", state, ASOF)["status"] == r.UNMEASURED


def _partial(state, **extra):
    _pnl(state, factor_status="PARTIAL")
    p = state / "reports" / "pnl" / f"{ASOF.isoformat()}.json"
    rep = json.loads(p.read_text())
    rep["factor"].update(extra)
    p.write_text(json.dumps(rep))


def test_a_partial_factor_block_is_a_watch_naming_the_names_and_their_share(state):
    """Ruling C (team lead, 2026-11-10): the job's PARTIAL block (a held name without a same-day
    price, left out) is a WATCH whose first line names what was left out and its share of the
    gross, then the job's lines verbatim; never an ACT. Fails on the parent commit (UNMEASURED)."""
    _partial(state, missing=[{"symbol": "LATE", "shares": -1000.0, "gross_usd": 9000.0, "reason": "no close"}],
             missing_gross_share=0.0912)
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.WATCH and b["data"]["missing"] == ["LATE"] and b["data"]["missing_gross_share"] == 0.0912
    assert b["lines"][0].startswith("Factor exposure PARTIAL: LATE left out at the last close, 9.1% of the book's gross")
    assert b["lines"][1].startswith(f"Factor exposure at the close of {ASOF}, cross-checked")
    assert b["lines"][2].startswith("MUNI (headline)")
    assert not any(ln.startswith("ACT") for ln in b["lines"])
    rep, code = r.run_report("cef", state, ASOF, now_utc=dt.datetime(2026, 11, 6, 3, 30, tzinfo=dt.timezone.utc),
                             send=lambda *a: True)
    assert rep["blocks"]["factor_exposure"]["status"] == r.WATCH and not rep["act_lines"]


def test_a_partial_block_without_its_share_says_unmeasured_never_a_number(state):
    _partial(state, missing=[{"symbol": "LATE"}])
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.WATCH and "share of the book's gross UNMEASURED" in b["lines"][0]


FLAT_LINE = (f"Factor exposure at the close of {ASOF}: FLAT, the book holds no position at that close, so there is "
             f"nothing to expose")


def _flat(state, **factor):
    """The job's FLAT block for the as-of close (scripts/ops/pnl_report.py `_factor_flat`), as the
    job wrote it before the third review of PR #82 (no `rebuild_positions`: a FLAT block's rebuild
    holds nothing at its as-of close by definition), unless `factor` passes the field."""
    _pnl(state, factor_status="FLAT", rebuild=None)
    p = state / "reports" / "pnl" / f"{ASOF.isoformat()}.json"
    rep = json.loads(p.read_text())
    rep["factor"].update({"asof": ASOF.isoformat(), "flat": True, "lines": [FLAT_LINE], **factor})
    p.write_text(json.dumps(rep))


def _record(state, day, qty, **over):
    """The collector's account record for `day` (quantt/collect/collect.py account_snapshot)."""
    d = state / "data" / day.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    rec = {"date": day.isoformat(), "read_at_utc": f"{day.isoformat()}T21:10:04+00:00",
           "account": {"equity": "100000", "maintenance_margin": "0"}, "positions": {"qty": qty, "raw": []}}
    rec.update(over)
    (d / "account.json").write_text(json.dumps(rec))
    return d / "account.json"


def test_a_flat_factor_block_is_info_when_the_account_record_holds_nothing(state):
    """A FLAT block (the book holds nothing at the as-of close; independent review of PR #82,
    2026-11-11) carries no factor risk, and it is INFO when the collector's account record for
    that close holds no position either (team lead, 2026-11-11): the cross-check's line first,
    then the job's lines verbatim, never an ACT. Fails on the parent d498c4f, which passed the
    job's lines as INFO without reading the account record."""
    _flat(state)
    path = _record(state, ASOF, {})
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.INFO and b["lines"][1:] == [FLAT_LINE]
    assert b["lines"][0] == (f"Factor exposure FLAT at the close of {ASOF}, cross-checked: the collector's account "
                             f"record for {ASOF} ({path}, read {ASOF}T21:10:04+00:00) holds no position either")
    assert b["data"]["flat_cross_check"]["status"] == r.INFO and b["data"]["flat_cross_check"]["positions"] == 0
    rep, code = r.run_report("cef", state, ASOF, now_utc=dt.datetime(2026, 11, 6, 3, 30, tzinfo=dt.timezone.utc),
                             send=lambda *a: True)
    assert rep["blocks"]["factor_exposure"]["status"] == r.INFO and not rep["act_lines"]


def test_a_flat_block_the_account_record_disagrees_with_is_a_watch(state):
    """Team lead, 2026-11-11 (second review of PR #82): the job reads FLAT from its fill rebuild,
    and a fill the account never made can flatten that rebuild. When the account record for the
    same close holds positions, the block is a WATCH naming the counts and the symbols (no
    quantity), never an ACT. Fails on the parent d498c4f, where the block was INFO."""
    _flat(state)
    _record(state, ASOF, {"HQH": -1000, "AAA": 1500, "BBB": -500})
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.WATCH, b["lines"][0]
    assert b["lines"][0].startswith(f"Factor exposure FLAT DISAGREES with the account at the close of {ASOF} (WATCH)")
    assert "shows 3 position(s), 1 long and 2 short (AAA, BBB, HQH)" in b["lines"][0]
    assert not any(q in b["lines"][0] for q in ("1000", "1500", "500"))
    assert b["lines"][1:] == [FLAT_LINE]
    assert {k: b["data"]["flat_cross_check"][k] for k in ("positions", "long", "short")} == {"positions": 3, "long": 1, "short": 2}
    rep, code = r.run_report("cef", state, ASOF, now_utc=dt.datetime(2026, 11, 6, 3, 30, tzinfo=dt.timezone.utc),
                             send=lambda *a: True)
    assert rep["blocks"]["factor_exposure"]["status"] == r.WATCH and not rep["act_lines"] and code == 0


@pytest.mark.parametrize("case", ["missing", "earlier_only", "other_session", "not_json", "no_qty", "no_asof"])
def test_a_flat_block_whose_account_record_cannot_be_read_is_unmeasured_never_info(state, case):
    """Team lead, 2026-11-11: a FLAT the account record cannot confirm is UNMEASURED for the
    cross-check, naming why, never INFO by default. The record read is the FLAT close's own,
    never the newest on or before it. Fails on the parent d498c4f, where every case was INFO."""
    path = state / "data" / ASOF.isoformat() / "account.json"
    _flat(state, **({"asof": None} if case == "no_asof" else {}))
    why = {"missing": f"no account record at {path}", "earlier_only": f"no account record at {path}",
           "other_session": f"the account record {path} is for session '2026-11-04', not {ASOF}",
           "not_json": f"the account record {path} is unreadable: JSONDecodeError",
           "no_qty": f"the account record {path} has no positions.qty of whole-share quantities",
           "no_asof": "the job's FLAT block names no as-of close (None)"}[case]
    if case in ("missing", "earlier_only"):
        path.unlink()                                  # the fixture's own record (it holds HQH)
    if case == "earlier_only":
        _record(state, ASOF - dt.timedelta(days=1), {})   # an earlier session that held nothing
    if case == "other_session":
        _record(state, ASOF, {}, date="2026-11-04")
    if case == "not_json":
        path.write_text("{not json")
    if case == "no_qty":
        _record(state, ASOF, {}, positions={"raw": []})
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.UNMEASURED, (case, b["lines"][0])
    assert b["lines"][0].startswith("Factor exposure FLAT") and "not cross-checked (UNMEASURED)" in b["lines"][0]
    assert why in b["lines"][0], (case, b["lines"][0])
    assert b["lines"][1:] == [FLAT_LINE]


def test_a_partial_block_with_nothing_missing_at_the_close_is_info_not_watch(state):
    """The severity follows the as-of reading (independent review of PR #82, 2026-11-11): a
    PARTIAL block whose `missing` is empty (every name held at the close read, one left out only
    on an earlier date: the JSON of a job from before the review) is INFO, saying so. Fails on
    the parent commit, where it was a WATCH every night from then on."""
    _partial(state, missing=[], missing_gross_share=0.0)
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.INFO and b["data"]["missing"] == []
    assert b["lines"][0].startswith("Factor exposure: every held name read at the last close; a name was left out "
                                    "only on an earlier date (history, no severity")
    assert b["lines"][2].startswith("MUNI (headline)")


def test_a_partial_block_that_does_not_say_what_was_missing_stays_a_watch_naming_it(state):
    """A PARTIAL block with no `missing` cannot say whether the as-of reading was complete, so it
    is never read as complete: WATCH, naming the gap. Fails on the parent commit, which read
    the absent list as empty and said every held name was read."""
    _partial(state, missing_gross_share=0.25)
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.WATCH and b["data"]["missing"] is None
    assert b["lines"][0].startswith("Factor exposure PARTIAL: names left out UNMEASURED (not in the job's JSON), "
                                    "25.0% of the book's gross")


# --- every factor status cross-checked against the account (team lead, 2026-11-11/12, third review of PR #82) ---

@pytest.mark.parametrize("status", ["OK", "PARTIAL", "UNMEASURED"])
def test_a_held_block_whose_positions_match_the_account_record_says_so(state, status):
    """The job's rebuild positions at the as-of close (HQH -1000) equal the collector's account
    record for that close: the cross-check is INFO, its line first after any PARTIAL line, and the
    block keeps its reading's own severity (OK INFO, PARTIAL WATCH, UNMEASURED UNMEASURED). Fails
    on the parent 8eb9ce1, which read no account record for a held block (no cross-check line)."""
    _pnl(state, factor_status=status)
    if status == "PARTIAL":
        p = state / "reports" / "pnl" / f"{ASOF.isoformat()}.json"
        rep = json.loads(p.read_text())
        rep["factor"].update(missing=[{"symbol": "LATE", "shares": -10.0, "gross_usd": 90.0, "reason": "no close"}],
                             missing_gross_share=0.01)
        p.write_text(json.dumps(rep))
    b = r.factor_block("cef", state, ASOF)
    want = {"OK": r.INFO, "PARTIAL": r.WATCH, "UNMEASURED": r.UNMEASURED}[status]
    assert b["status"] == want, b["lines"]
    line = [ln for ln in b["lines"] if ln.startswith(f"Factor exposure at the close of {ASOF}, cross-checked")]
    assert len(line) == 1 and "holds the same 1 position(s) as the fill rebuild the factor block reads" in line[0]
    assert b["data"]["positions_cross_check"]["status"] == r.INFO and b["data"]["positions_cross_check"]["differ"] == []


@pytest.mark.parametrize("account, differ, words", [
    ({"HQH": -2000}, ["HQH"], "a different quantity of HQH"),
    ({"HQH": -1000, "AAA": 4000}, ["AAA"], "in the account only: AAA"),
    ({}, ["HQH"], "in the rebuild only: HQH")], ids=["quantity", "account_only", "rebuild_only"])
@pytest.mark.parametrize("status", ["OK", "UNMEASURED"])
def test_a_held_block_the_account_record_disagrees_with_is_a_watch(state, account, differ, words, status):
    """Team lead, 2026-11-11/12 (third review of PR #82): the job's block reads the fill
    rebuild's positions, and a fill the account never made leaves them wrong while the block
    reads OK. When the collector's record for the same close holds other positions, the block is
    a WATCH naming the counts and the symbols that differ, no quantity, never an ACT; on an OK and
    an UNMEASURED block alike. Fails on the parent 8eb9ce1, where an OK block was INFO and an
    UNMEASURED one UNMEASURED."""
    _pnl(state, factor_status=status)
    _record(state, ASOF, account)
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.WATCH, b["lines"][0]
    assert b["lines"][0].startswith(f"Factor exposure at the close of {ASOF} DISAGREES with the account (WATCH): the "
                                    "P&L job's fill rebuild (the positions its factor block is read from) holds 1 "
                                    "position(s) there, 0 long and 1 short")
    assert f"they differ on {len(differ)} symbol(s) ({words})" in b["lines"][0]
    assert not any(q in b["lines"][0] for q in ("1000", "2000", "4000"))
    assert b["data"]["positions_cross_check"]["differ"] == differ
    assert not any(ln.startswith("ACT") for ln in b["lines"])
    rep, code = r.run_report("cef", state, ASOF, now_utc=dt.datetime(2026, 11, 6, 3, 30, tzinfo=dt.timezone.utc),
                             send=lambda *a: True)
    assert rep["blocks"]["factor_exposure"]["status"] == r.WATCH and not rep["act_lines"] and code == 0


@pytest.mark.parametrize("case", ["missing", "earlier_only", "other_session", "not_json", "no_qty", "fractional",
                                  "no_rebuild", "rebuild_not_whole", "no_session"])
def test_a_held_block_whose_cross_check_cannot_be_read_is_unmeasured_never_info(state, case):
    """Team lead, 2026-11-11/12: the rules of the FLAT check, for a held block. The record read is
    the block's own close's, never the newest on or before it; a record that is missing, for
    another session, unreadable or not whole shares, and a JSON without the job's positions,
    leave the cross-check UNMEASURED, naming why, so an OK block is UNMEASURED, never INFO.
    Fails on the parent 8eb9ce1, where every case was INFO."""
    path = state / "data" / ASOF.isoformat() / "account.json"
    rebuild = {"no_rebuild": None, "rebuild_not_whole": {"HQH": -1000.5}}.get(case, REBUILD)
    _pnl(state, rebuild=rebuild)
    if case == "no_session":
        p = state / "reports" / "pnl" / f"{ASOF.isoformat()}.json"
        rep = json.loads(p.read_text())
        rep["factor"]["rebuild_positions"]["session"] = None
        p.write_text(json.dumps(rep))
    why = {"missing": f"no account record at {path}", "earlier_only": f"no account record at {path}",
           "other_session": f"the account record {path} is for session '2026-11-04', not {ASOF}",
           "not_json": f"the account record {path} is unreadable: JSONDecodeError",
           "no_qty": f"the account record {path} has no positions.qty of whole-share quantities",
           "fractional": f"the account record {path} has no positions.qty of whole-share quantities",
           "no_rebuild": "the P&L job's JSON carries no rebuild positions for its factor block",
           "rebuild_not_whole": "the P&L job's rebuild positions are not {symbol: whole shares}",
           "no_session": "the job's factor block names no as-of close (None)"}[case]
    if case in ("missing", "earlier_only"):
        path.unlink()
    if case == "earlier_only":
        _record(state, ASOF - dt.timedelta(days=1), dict(REBUILD))
    if case == "other_session":
        _record(state, ASOF, dict(REBUILD), date="2026-11-04")
    if case == "not_json":
        path.write_text("{not json")
    if case == "no_qty":
        _record(state, ASOF, {}, positions={"raw": []})
    if case == "fractional":
        _record(state, ASOF, {"HQH": -1000.0})
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.UNMEASURED, (case, b["lines"][0])
    assert b["lines"][0].startswith("Factor exposure ") and "not cross-checked (UNMEASURED)" in b["lines"][0]
    assert why in b["lines"][0], (case, b["lines"][0])
    assert b["lines"][1].startswith("MUNI (headline)")


def test_an_unreconciled_held_block_is_at_least_a_watch_never_info(state):
    """Team lead, 2026-11-11/12: a held book read on a rebuild that does not reconcile is at
    least a WATCH, never INFO, even when its positions match the account record: the job's
    UNRECONCILED block, and an OK block from a job that predates the ruling. Fails on the parent
    8eb9ce1, where both were INFO or UNMEASURED."""
    _pnl(state, reconciled=False, factor_status="UNRECONCILED")
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.WATCH and b["data"]["positions_cross_check"]["status"] == r.INFO
    (state / "reports" / "pnl" / f"{ASOF.isoformat()}.json").unlink()
    _pnl(state, reconciled=False, factor_status="OK")
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.WATCH
    assert b["lines"][0].startswith("Factor exposure on a held close whose fill rebuild does not reconcile to the "
                                    "official EOD change (WATCH")


def test_a_flat_block_with_the_jobs_rebuild_positions_is_checked_the_same_way(state):
    """A FLAT block that carries the job's `rebuild_positions` (empty at its as-of close) reads as
    the FLAT check always did; one whose positions contradict its FLAT is UNMEASURED, never INFO.
    The contradiction case fails on the parent 8eb9ce1, which ignored the field (INFO)."""
    _flat(state, rebuild_positions={"session": ASOF.isoformat(), "qty": {}, "source": "x"})
    _record(state, ASOF, {})
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.INFO and b["lines"][0].startswith(f"Factor exposure FLAT at the close of {ASOF}, cross-checked")
    (state / "reports" / "pnl" / f"{ASOF.isoformat()}.json").unlink()
    _flat(state, rebuild_positions={"session": ASOF.isoformat(), "qty": {"HQH": -1000}, "source": "x"})
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.UNMEASURED and "the JSON contradicts itself" in b["lines"][0]


# --- a late EOD point: a reading of an earlier session (team lead, 2026-11-11/12, third review of PR #82) ---

PREV = ASOF - dt.timedelta(days=1)


@pytest.mark.parametrize("factor_status", ["OK", "FLAT"])
def test_a_reading_of_an_earlier_session_is_never_info(state, factor_status):
    """Alpaca's EOD history had no point for the as-of when the job ran, so its JSON is a reading
    of the close before. Both blocks are UNMEASURED for the as-of, never INFO, their first line
    saying the reading is the earlier session's, NOT the as-of's, and the earlier lines follow as
    history; the factor block's cross-check reads that earlier close's record. Fails on the parent
    8eb9ce1, where both were INFO."""
    _pnl(state, factor_status=factor_status, session=PREV, rebuild={} if factor_status == "FLAT" else REBUILD)
    _record(state, PREV, {} if factor_status == "FLAT" else dict(REBUILD))
    _record(state, ASOF, {"AAA": 4000})                 # the as-of's own record holds something else
    a = r.attribution_block("cef", state, ASOF)
    f = r.factor_block("cef", state, ASOF)
    want = f"the P&L job read the close of {PREV}, NOT {ASOF} (Alpaca's EOD history had no point for {ASOF} when it ran)"
    assert a["status"] == r.UNMEASURED and a["lines"][0] == (
        f"Attribution UNMEASURED for {ASOF}: {want}; nothing below is {ASOF}'s, and the lines below are {PREV}'s, "
        "shown as history (team lead, 2026-11-11/12)")
    assert a["lines"][1].startswith("Session 2026-11-05") and a["data"]["session_read"] == PREV.isoformat()
    assert f["status"] == r.UNMEASURED and f["lines"][0].startswith(f"Factor exposure UNMEASURED for {ASOF}: {want}")
    assert f"at the close of {PREV}" in f["lines"][1] and "cross-checked" in f["lines"][1]
    rep, code = r.run_report("cef", state, ASOF, now_utc=dt.datetime(2026, 11, 6, 3, 30, tzinfo=dt.timezone.utc),
                             send=lambda *a: True)
    assert rep["blocks"]["attribution"]["status"] == rep["blocks"]["factor_exposure"]["status"] == r.UNMEASURED


def test_a_watch_in_an_earlier_sessions_reading_stays_a_watch(state):
    """The louder of the two: an earlier session's unreconciled rebuild, or a cross-check that
    disagrees with that session's record, is still a WATCH on the as-of's report, labelled as the
    earlier session's. Fails on the parent 8eb9ce1, where the factor block was INFO."""
    _pnl(state, reconciled=False, session=PREV)
    _record(state, PREV, {"HQH": -900})
    a = r.attribution_block("cef", state, ASOF)
    f = r.factor_block("cef", state, ASOF)
    assert a["status"] == r.WATCH and a["lines"][0].startswith(f"Attribution UNMEASURED for {ASOF}: the P&L job read "
                                                               f"the close of {PREV}, NOT {ASOF}")
    assert f["status"] == r.WATCH and f["lines"][0].startswith(f"Factor exposure UNMEASURED for {ASOF}")


@pytest.mark.parametrize("case", ["no_session", "other_asof"])
def test_a_json_that_cannot_show_its_reading_is_the_as_ofs_is_unmeasured(state, case):
    """A JSON whose attribution names no session read, or that is filed under the as-of but says
    another, cannot be shown to be the as-of's reading: UNMEASURED, never INFO. Fails on the parent
    8eb9ce1, where both blocks were INFO."""
    _pnl(state)
    p = state / "reports" / "pnl" / f"{ASOF.isoformat()}.json"
    rep = json.loads(p.read_text())
    if case == "no_session":
        del rep["attribution"]["effective_session"]
    else:
        rep["asof"] = PREV.isoformat()
    p.write_text(json.dumps(rep))
    a = r.attribution_block("cef", state, ASOF)
    assert a["status"] == r.UNMEASURED and a["lines"][0].startswith(f"Attribution UNMEASURED for {ASOF}: ")
    if case == "other_asof":
        f = r.factor_block("cef", state, ASOF)
        assert f["status"] == r.UNMEASURED and "is for as-of '2026-11-04', not 2026-11-05" in f["lines"][0]


def test_a_held_block_whose_positions_are_of_another_close_is_unmeasured(state):
    """Independent review of the follow-up (2026-11-14), rd_probe.py: a held block read at the
    as-of with rebuild positions for the session before it is a JSON that contradicts itself;
    the cross-check read the earlier session's record and passed the block as INFO. Now any
    disagreement between the block's close and its positions' session is UNMEASURED, named, as
    the FLAT path already was. Fails on the parent bdf181e, where it was INFO."""
    _pnl(state)
    p = state / "reports" / "pnl" / f"{ASOF.isoformat()}.json"
    rep = json.loads(p.read_text())
    prev = (ASOF - dt.timedelta(days=1)).isoformat()
    rep["factor"]["rebuild_positions"]["session"] = prev
    p.write_text(json.dumps(rep))
    _record(state, ASOF - dt.timedelta(days=1), dict(REBUILD))
    b = r.factor_block("cef", state, ASOF)
    assert b["status"] == r.UNMEASURED, b["lines"][0]
    assert (f"the P&L job's factor block is read at '{ASOF.isoformat()}' but its rebuild positions are for "
            f"'{prev}'") in b["lines"][0]
