"""The exporter: the runners' records in, a clean snapshot out; every gap a gap; nothing private."""
import datetime as dt
import json

import pytest

from dashboard import export as E, snapshot as S
from dashboard.tests import synth

NOW = dt.datetime(2026, 11, 23, 23, 20, tzinfo=dt.timezone.utc)


@pytest.fixture
def state(tmp_path):
    return synth.make_state(tmp_path)


def snap_of(state):
    st, sb = state
    return E.export(st, sb, NOW)


def book(snap, name):
    return next(b for b in snap["books"] if b["name"] == name)


def test_a_full_night_exports_clean(state):
    s = snap_of(state)
    assert E.check(s) == [], E.check(s)
    assert [b["name"] for b in s["books"]] == ["cef", "c4", "events"]
    assert s["exported_at_utc"] == "2026-11-23T23:20:00Z" and s["synthetic"] is False


def test_official_rows_are_alpacas_and_the_read_time_is_theirs(state):
    o = book(snap_of(state), "cef")["official"]
    assert o["label"] == "broker-confirmed" and o["read_at"] == "2026-11-21T08:40:04Z"
    assert o["value"]["rows"][0] == {"date": "2026-11-16", "equity": 100000.0, "change_usd": None}
    assert o["value"]["rows"][-1]["change_usd"] == -50.0


def test_the_session_is_the_newest_day_that_has_a_reconcile_not_a_plan_directory(state):
    v = book(snap_of(state), "cef")["session"]["value"]
    assert v["date"] == "2026-11-20" and v["verdict"] == "PASS"
    assert {p["symbol"]: (p["qty"], p["close"]) for p in v["positions"]} == {"AAA": (100.0, 10.0), "BBB": (-50.0, 20.0)}
    assert v["orders"] == [{"symbol": "AAA", "side": "buy", "qty": 5.0, "status": "filled", "filled_qty": 5.0,
                            "avg_price": 10.0}]
    assert v["equity_snapshot"]["change_usd"] == -40.0


def test_order_and_fill_ids_never_reach_the_snapshot(state):
    text = json.dumps(snap_of(state))
    for leak in ("client_order_id", "order_id", "b3a7e512", "cef-20261120-AAA-1", "2baa43f0", "/home/"):
        assert leak not in text, leak


def test_the_newest_risk_report_is_read_and_its_paths_are_not_copied(state):
    r = book(snap_of(state), "cef")["risk"]
    assert r["value"]["asof"] == "2026-11-20" and r["value"]["severity"] == "WATCH"
    assert r["value"]["gross"] == 1.5 and r["value"]["largest"]["symbol"] == "AAA"
    assert r["read_at"] == "2026-11-21T10:45:00Z" and r["label"] == "modelled"


def test_the_event_book_reads_verify_json_and_its_strategy_scores(state):
    ev = book(snap_of(state), "events")
    assert ev["official"] == {"absent": "no end-of-day equity history is recorded for this account yet"}
    v = ev["session"]["value"]
    assert v["date"] == "2026-11-23" and v["verdict"] == "PASS"
    assert v["positions"] == [{"symbol": "CCC", "qty": -7.0, "close": 30.0}]      # the zero line is not a position
    assert v["orders"][0]["avg_price"] == 30.5
    assert v["equity_snapshot"]["change_usd"] == 10.0
    slugs = [r["slug"] for r in ev["sleeves"]["value"]["rows"]]
    assert slugs == ["cef_exdate_after", "uit_termination", "_book"]
    assert "absent" in ev["risk"] and "absent" in ev["execution"]


def test_the_shadow_scoreboard_is_simulated_and_stops_at_its_first_table(state):
    sh = snap_of(state)["shadow"]
    assert sh["label"] == "simulated" and sh["value"]["asof"] == "2026-11-20"
    rows = sh["value"]["rows"]
    assert [r["book"] for r in rows] == ["month_end_ief", "units_exdate_after"]
    assert rows[0]["pnl_total"] is None and rows[1]["pnl_total"] == 20674.0
    assert rows[1]["max_drawdown"] == pytest.approx(-0.0197)


def test_a_corrupt_eod_file_is_unmeasured_never_a_number(state):
    st, _ = state
    (st / "cef" / "eod_equity.csv").write_text(synth.EOD_HEAD + "2026-11-16,abc,,2026-11-21T08:40:04+00:00\n")
    o = book(snap_of(state), "cef")["official"]
    assert S.UNMEASURED in o and "not a number" in o[S.UNMEASURED]


def test_a_missing_column_is_named(state):
    st, _ = state
    (st / "cef" / "eod_equity.csv").write_text("date,equity\n2026-11-16,1\n")
    assert "change_usd" in book(snap_of(state), "cef")["official"][S.UNMEASURED]


def test_a_missing_book_directory_is_unmeasured_in_every_section(state):
    st, _ = state
    import shutil
    shutil.rmtree(st / "c4")
    b = book(snap_of(state), "c4")
    assert all(S.UNMEASURED in b[k] for k in ("official", "session", "risk", "execution", "sleeves"))


def test_a_missing_scoreboard_is_unmeasured(state, tmp_path):
    st, _ = state
    sh = E.export(st, tmp_path / "nope.md", NOW)["shadow"]
    assert S.UNMEASURED in sh


def test_a_verdict_for_another_day_is_refused(state):
    st, _ = state
    p = st / "cef" / "2026-11-20" / "reconcile.json"
    r = json.loads(p.read_text())
    r["verdict"] = "2026-11-19 PASS cef traded"
    p.write_text(json.dumps(r))
    assert S.UNMEASURED in book(snap_of(state), "cef")["session"]


def test_problem_text_is_scrubbed_of_paths(state):
    st, _ = state
    p = st / "cef" / "2026-11-20" / "reconcile.json"
    r = json.loads(p.read_text())
    r["problems"] = ["could not read /home/quantt/quantt_state/cef/x.json"]
    p.write_text(json.dumps(r))
    s = snap_of(state)
    assert book(s, "cef")["session"]["value"]["problems"] == ["could not read <path>"]
    assert E.check(s) == []


def test_main_refuses_a_dirty_snapshot_and_writes_nothing(state, tmp_path, monkeypatch, capsys):
    st, sb = state
    real = E.export
    monkeypatch.setattr(E, "export", lambda *a, **k: {**real(*a, **k), "note": "PKABCDEFGHIJKLMNOPQRS"})
    out = tmp_path / "snap.json"
    assert E.main(["--state-root", str(st), "--shadow-scoreboard", str(sb), "-o", str(out)]) == 2
    assert not out.exists() and "refused" in capsys.readouterr().err


def test_main_writes_the_snapshot(state, tmp_path):
    st, sb = state
    out = tmp_path / "snap.json"
    assert E.main(["--state-root", str(st), "--shadow-scoreboard", str(sb), "-o", str(out)]) == 0
    assert S.validate(json.loads(out.read_text())) == []


def test_an_empty_change_after_funding_is_that_books_gap_not_a_failed_site(state):
    """Release-check review, 2026-11-23: one empty change_usd used to stop the whole site build."""
    st, _ = state
    p = st / "cef" / "eod_equity.csv"
    p.write_text(p.read_text().replace("2026-11-19,100100.0,200.0,", "2026-11-19,100100.0,,"))
    s = snap_of(state)
    assert S.UNMEASURED in book(s, "cef")["official"] and "no change_usd" in book(s, "cef")["official"][S.UNMEASURED]
    assert "value" in book(s, "c4")["official"]
    from dashboard import build as B
    assert "Fixed Income Book" in B.render(s)
