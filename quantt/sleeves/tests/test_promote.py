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


def book_file(tmp_path, capital=FULL / 4, enabled=True, full=FULL):
    p = tmp_path / "events_sleeves.json"
    p.write_text(json.dumps({
        "book": "events", "min_order_usd": 25, "max_gross_x_equity": 1.5, "max_name_usd": 50000,
        "max_stale_sessions": 2, "max_orders": 300, "execution": EXEC,
        "sleeves": [{"slug": "a", "family": "f", "full_capital_usd": full, "capital_usd": capital,
                     "enabled": enabled}]}))
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


def events_state(tmp_path, held, slug="a", empty_days=0, day_change="5.0000", pnl=None):
    """A sleeve_scores.csv in run.py's layout: `empty_days` rows with no position, then `held`
    rows with one. Dates are the shadow_state() sessions, so the two line up."""
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
                            "equity_change": "", "residual": ""})
    return st


def report(tmp_path, *, shadow_n=12, held=None, capital=FULL / 4, enabled=True, **shadow_kw):
    sh = shadow_state(tmp_path, shadow_n, **shadow_kw)
    ev = events_state(tmp_path, held) if held is not None else tmp_path / "events"
    return pm.build(book_file(tmp_path, capital, enabled), sh, ev)


# ------------------------------------------------------------------ promotion

def test_nine_clean_sessions_are_not_eligible_and_ten_are(tmp_path):
    (tmp_path / "x").mkdir(); (tmp_path / "y").mkdir()
    nine = pm.shadow_book(shadow_state(tmp_path / "x", 9), "a")
    ten = pm.shadow_book(shadow_state(tmp_path / "y", 10), "a")
    assert (nine["clean_streak"], nine["eligible"]) == (9, False)
    assert (ten["clean_streak"], ten["eligible"], ten["first"], ten["last"]) == (10, True, "2026-01-06", "2026-01-19")


def test_a_flat_day_with_an_on_time_decision_is_a_clean_session(tmp_path):
    """The plumbing ran: panels fetched, an on-time decision with no weights. This is the
    reading the team lead is asked to confirm (promote.py docstring)."""
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
    (60, FULL / 2, pm.UNMEASURED, pm.EXIT_UNMEASURED),
])
def test_the_ladder_at_its_boundaries(tmp_path, held, capital, verdict, code):
    rep = report(tmp_path, shadow_n=max(12, held), held=held, capital=capital)
    s = rep["sleeves"][0]
    assert (s["position_sessions"], s["verdict"], rep["exit_code"]) == (held, verdict, code)
    if held < 20:
        assert (s["stage_due"], s["capital_due"]) == ("QUARTER", FULL / 4)
    elif held < 60:
        assert s["missing"] == [pm.NO_TRACK_RULE] and s["capital_due"] is None and "HALF" in s["stage_due"]
    else:
        assert s["missing"] == [pm.NO_SIGMA] and s["capital_due"] is None


def test_a_change_names_the_exact_edit(tmp_path):
    s = report(tmp_path, held=19, capital=FULL / 2)["sleeves"][0]
    assert s["edits"] == ['"capital_usd": 10000.0 for a (now 20000.0)']
    assert "CHANGE NEEDED in ops/sleeves/events_sleeves.json" in pm.render(report(tmp_path / "x", held=3, capital=FULL))


def test_only_sessions_with_a_position_count(tmp_path):
    sh = shadow_state(tmp_path, 40)
    ev = events_state(tmp_path, 19, empty_days=15)
    s = pm.build(book_file(tmp_path), sh, ev)["sleeves"][0]
    assert (s["rows"], s["position_sessions"], s["verdict"]) == (34, 19, pm.AGREE)


def test_tracking_figures_are_printed_without_a_pass_or_fail(tmp_path):
    """25 position sessions at a quarter ($10,000): paper +5 a day; the shadow book +$1,000 a
    day on $1,000,000, i.e. +$10 a day at this capital. The report gives both and the
    difference, and no verdict on them."""
    rep = report(tmp_path, shadow_n=25, held=25)
    t = rep["sleeves"][0]["tracking"]
    assert (t["sessions_compared"], t["paper_pnl_usd"], t["shadow_pnl_usd_at_shadow_notional"],
            t["shadow_pnl_usd_at_capital_usd"], t["difference_usd"]) == (25, 125.0, 25000.0, 250.0, -125.0)
    assert "No pass or fail" in pm.render(rep) and rep["sleeves"][0]["verdict"] == pm.UNMEASURED


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
