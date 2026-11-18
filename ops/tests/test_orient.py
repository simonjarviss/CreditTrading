"""`ops.orient` replaces remembered numbers with measured ones. So it must not
invent one, and it must not die trying.

WHY THIS FILE EXISTS
--------------------
An orientation tool has a failure mode worse than being absent: being confidently
wrong. It is the first thing a new agent runs, its output looks authoritative,
and every number in it is about to be quoted. The two properties that matter are
therefore not "does it produce a number" but:

  1. when it CANNOT measure something, it says so by name and produces no value
     (the repo's NO SILENT FALLBACKS rule, applied to a report rather than a
     calculation);
  2. one broken section does not take the other eight down with it.

The `ib_insync` check gets the most tests because it is the one whose prescribed
recipe was provably unable to express the property it checked. `CLAUDE.md` says
to run

    grep -rn '^ *from ib_insync' ops/ src/ scripts/ | grep -v ImportError

and asserts the answer is zero. On 2026-09-11 that grep returned 5 and the true
answer was 2 — the `except ImportError:` that makes an import safe is on a
different LINE from the import, so the filter filters nothing. Three imports are
correctly guarded and two are not. `.claude/rules/live-order-path.md` says "Two
legacy scripts still import it; do not add a third", which is the reading this
check must reproduce.

NO NETWORK, NO BROKER, NO PROD TREE. The classifier tests build Python source in
`tmp_path`; the degradation tests point the module's constants at paths that do
not exist.
"""
from __future__ import annotations

import json

import pytest

from ops import orient


def _src(tmp_path, rel: str, body: str):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


# ------------------------------------------------- the ib_insync classifier --
class TestIbInsyncClassifier:
    def test_guarded_fallback_is_not_flagged(self, tmp_path):
        """The safe shape, as `src/deploy/broker/ibkr.py:333` writes it."""
        _src(tmp_path, "ops/x.py", "def f():\n"
                                   "    try:\n"
                                   "        from ib_async import IB, util\n"
                                   "    except ImportError:\n"
                                   "        from ib_insync import IB, util\n")
        assert orient._unguarded_ib_insync(tmp_path) == []

    def test_bare_try_without_an_ib_async_preference_is_flagged(self, tmp_path):
        """THE REAL DEFECT, and the one the grep cannot see: `try:` alone does
        not help. ib_insync still hangs on Python 3.12+; nothing falls back."""
        _src(tmp_path, "scripts/y.py", "def f():\n"
                                       "    try:\n"
                                       "        from ib_insync import IB\n"
                                       "    except ImportError:\n"
                                       "        return 1\n")
        assert orient._unguarded_ib_insync(tmp_path) == ["scripts/y.py:3"]

    def test_top_level_import_is_flagged(self, tmp_path):
        _src(tmp_path, "src/z.py", "from ib_insync import IB\n")
        assert orient._unguarded_ib_insync(tmp_path) == ["src/z.py:1"]

    def test_plain_import_statement_is_flagged_too(self, tmp_path):
        """`import ib_insync` hangs exactly the same as `from ib_insync import`,
        and a pattern written for one spelling misses the other."""
        _src(tmp_path, "src/z.py", "import ib_insync\n")
        assert orient._unguarded_ib_insync(tmp_path) == ["src/z.py:1"]

    def test_the_grep_in_claude_md_would_disagree(self, tmp_path):
        """Pins WHY this is an AST walk. Both files below match
        `^ *from ib_insync` and neither contains 'ImportError' on that line, so
        the documented grep counts 2. Exactly one is actually unsafe."""
        _src(tmp_path, "ops/good.py", "def f():\n"
                                      "    try:\n"
                                      "        from ib_async import IB\n"
                                      "    except ImportError:\n"
                                      "        from ib_insync import IB\n")
        _src(tmp_path, "ops/bad.py", "def f():\n"
                                     "    from ib_insync import IB\n")
        assert orient._unguarded_ib_insync(tmp_path) == ["ops/bad.py:2"]

    def test_syntax_error_in_one_file_does_not_hide_the_rest(self, tmp_path):
        _src(tmp_path, "ops/broken.py", "def f( :\n")
        _src(tmp_path, "ops/bad.py", "from ib_insync import IB\n")
        assert orient._unguarded_ib_insync(tmp_path) == ["ops/bad.py:1"]

    def test_matches_the_live_tree(self):
        """Against the real repo. Two legacy scripts imported bare `ib_insync`
        until 2026-09-28, when both were deleted with IBKR. Zero now: any
        new one is a regression, not a legacy."""
        assert orient._unguarded_ib_insync() == []


# ------------------------------------------------------ honest degradation --
class TestNeverInventsAndNeverDies:
    def test_a_broken_section_is_named_not_skipped(self, monkeypatch):
        def boom():
            raise RuntimeError("panel fetch exploded")
        monkeypatch.setattr(orient, "panels", boom)
        monkeypatch.setattr(orient, "SECTIONS",
                            [("PANELS", boom), ("TRIALS", orient.trials)])
        d = orient.collect(run_tests=False)
        assert "UNMEASURED" in d["sections"]["PANELS"]
        assert "panel fetch exploded" in d["sections"]["PANELS"]["UNMEASURED"]
        assert "UNMEASURED" not in d["sections"]["TRIALS"], (
            "one broken section must not take the others down")

    def test_missing_counter_table_raises_rather_than_defaulting(self,
                                                                 tmp_path,
                                                                 monkeypatch):
        """A trial counter that quietly reads 0 would lower the deflated-Sharpe
        bar to nothing and turn every FAIL into a PASS. It must refuse."""
        monkeypatch.setattr(orient, "RESEARCH_STATE", tmp_path / "gone.md")
        with pytest.raises(orient.Unmeasured):
            orient.trials()

    def test_changed_counter_table_format_raises(self, tmp_path, monkeypatch):
        f = tmp_path / "RESEARCH_STATE.md"
        f.write_text("| counter | source | trials |\n| CEF | discounts | 48 |\n")
        monkeypatch.setattr(orient, "RESEARCH_STATE", f)
        with pytest.raises(orient.Unmeasured, match="table format changed"):
            orient.trials()

    def test_missing_panel_is_reported_as_a_gap_with_its_path(self, tmp_path,
                                                             monkeypatch):
        monkeypatch.setattr(orient, "PANELS", {"cef_prices": tmp_path / "no.parquet"})
        p = orient.panels()["panels"]["cef_prices"]
        assert p["last"] is None and "missing" in p["error"]

    def test_collect_is_json_serialisable(self, monkeypatch):
        # PROD reads this machine's launchd and would ssh to the VM; stub it so
        # the test does not depend on what happens to be installed here
        # (conftest.py) -- prod_state also refuses real ssh under netguard.
        monkeypatch.setattr(orient, "SECTIONS", [
            (n, (lambda: _prod_section(_m("DRY"), _m("ARMED"))) if n == "PROD" else f)
            for n, f in orient.SECTIONS])
        d = orient.collect(run_tests=False)
        assert json.loads(json.dumps(d, default=str))["sections"]

    def test_render_survives_a_fully_unmeasured_readout(self, monkeypatch,
                                                        capsys):
        """The empty-machine case: nothing measurable, and it must still print
        a readout rather than traceback."""
        def boom():
            raise RuntimeError("nothing here")
        monkeypatch.setattr(orient, "SECTIONS",
                            [(n, boom) for n, _ in orient.SECTIONS])
        orient.render(orient.collect(run_tests=False))
        out = capsys.readouterr().out
        assert out.count("UNMEASURED") == len(orient.SECTIONS)


# --------------------------------------------------------- derived, not copied --
class TestDerivedFigures:
    def test_dsr_bar_is_computed_from_the_counter(self, tmp_path, monkeypatch):
        """sqrt(2 ln N) is DERIVED here because it was wrong in three documents
        at once when it was written out by hand (2.15 at N=10 left standing
        while the counter read 48, where the bar is 2.783)."""
        import math
        f = tmp_path / "RESEARCH_STATE.md"
        f.write_text("| **CEF** | **discounts** | **48** |\n"
                     "| **GAMMA** | **options** | **0** |\n")
        monkeypatch.setattr(orient, "RESEARCH_STATE", f)
        c = orient.trials()["counters"]
        assert c["CEF"]["trials"] == 48
        assert c["CEF"]["dsr_bar"] == round(math.sqrt(2 * math.log(48)), 3)
        assert c["GAMMA"]["dsr_bar"] is None, "no bar is defined at N<=1"

    def test_counter_is_labelled_as_a_citation_not_a_measurement(self):
        """The only document-sourced figure in the tool, and it must say so."""
        t = orient.trials()
        assert "[doc" in t["reproducer"]
        assert "RESEARCH_STATE" in t["source"]


# ----------------------------------------------------- measured, not written --


class TestSpecFields:
    def test_vol_target_is_read_from_the_spec(self):
        f = orient.spec_fields({"frozen": {"vol_target_annual": 0.11}})
        assert f["vol_target_annual"] == 0.11 and f["vol_target_absent"] is False

    def test_absent_vol_target_is_absent_not_the_code_default(self, capsys):
        """The sleeve has a code default for this key. Printing it here would
        make a code constant read as a governance decision."""
        f = orient.spec_fields({"frozen": {"band_width": 0.048}})
        assert f["vol_target_annual"] is None and f["vol_target_absent"] is True
        d = {"measured_at": "t", "sections": {
            n: {"UNMEASURED": "not under test"} for n, _ in orient.SECTIONS}}
        d["sections"]["SPEC"] = {**f, "status": "X", "min_trade_usd": 1,
                                 "capital_usd": 1}
        orient.render(d)
        out = capsys.readouterr().out
        assert "ABSENT from the frozen spec" in out
        assert "0.06" not in out


class TestTheCounterTableReader:
    """`orient.trials` parses the RESEARCH_STATE counter table. It is the only
    reader left: `prompt_status.counters` and `gamma_status._trial_counters`
    were deleted on 2026-09-28 (the three-reader agreement test is at git tag
    `pre-clean-slate`). The file carries other
    tables of bold-cell rows; a reader that picked one up would move a
    deflated-Sharpe bar silently."""

    def test_reads_only_the_counter_rows_beside_other_bold_tables(
            self, tmp_path, monkeypatch):
        docs = tmp_path / "docs"
        docs.mkdir()
        f = docs / "RESEARCH_STATE.md"
        f.write_text(
            "| counter | source | trials used |\n|---|---|---|\n"
            "| **CEF** | **credit closed-end fund discounts** | **48** |\n"
            "| **GAMMA** | **options** | **0** |\n\n"
            "| code | what happened | what it means | what to do |\n"
            "| **D1** | No edge | x | Kill it |\n\n"
            "| id | hypothesis | phase | gate |\n"
            "| **CEF-DISC** | **reversion** | **DEPLOYED 2026-07-31, $500k paper** | none |\n"
            "| **KAPPA** | x | y | **12** | z |\n")
        monkeypatch.setattr(orient, "RESEARCH_STATE", f)
        got = {k: v["trials"] for k, v in orient.trials()["counters"].items()}
        assert got == {"CEF": 48, "GAMMA": 0}


# ------------------------------------------------------- PROD and ALPACA --
# Until 2026-10-08 TREES printed "prod none ... the Alpaca prod (cloud VM) is not
# built" and ALPACA "live book NONE -- nothing trades", both constants, through
# the first armed session (2026-09-29) and every one after; ALPACA also showed
# the 2026-09-28 probe snapshot's equity as if it were current. These pin the
# replacement: PROD measured (ops.prod_state), live equity from the armed
# machine's broker-confirmed equity.csv, the probe labelled with its age.

def _m(arming, equity="222.22", date="2026-01-06", where="x/equity.csv"):
    return {"machine": "?", "arming": arming, "arming_why": f"because {arming}",
            "cautions": [], "clone": "c", "state_dir": "s", "tag": {"value": "t"},
            "jobs": {}, "auto_armed": {"value": arming == "ARMED"},
            "verify_last": {"absent": "none"}, "dry_run": {"value": "0"},
            "timers": {"value": {}}, "timers_enabled": {"value": {}}, "alias": "quantt-vm",
            "equity": {"value": {"date": date, "equity": equity, "read_at_utc": None,
                                 "source": where}}}


def _prod_section(laptop, vm):
    from ops import prod_state
    machines = {"laptop": laptop, "vm": vm}
    return {"reproducer": "python3 -m ops.prod_state", "machines": machines,
            "verdict": prod_state.verdict(machines)}


def _render_with(capsys, **sections):
    d = {"measured_at": "t", "sections": {
        n: {"UNMEASURED": "not under test"} for n, _ in orient.SECTIONS}}
    d["sections"].update(sections)
    orient.render(d)
    return capsys.readouterr().out


TREES_SEC = {"reproducer": "git", "dev": {"path": "p", "branch": "b", "sha": "s",
                                         "uncommitted": 0},
             "ibkr_final": "ibkr-final", "legacy_prod_present": False}
ALPACA_SEC = {"reproducer": "probe", "books": {"cef": {
    "snapshot": "2026-09-28_cef.json", "fetched_at_utc": "2026-09-28T19:56:38+00:00",
    "age_days": 10, "equity_at_snapshot": "99999.99", "equity": "99999.99",
    "n_assets": 17, "not_found": [], "not_tradable": [], "not_shortable": ["NAD"],
    "hard_to_borrow": ["NAD"], "positions": 0, "open_orders": 0}}}


class TestProdIsMeasuredNotWritten:
    def test_trees_no_longer_says_prod_is_not_built(self, capsys):
        out = _render_with(capsys, TREES=TREES_SEC)
        assert "not built" not in out
        assert "PROD" in out

    def test_orient_has_a_prod_section(self):
        assert "PROD" in [n for n, _ in orient.SECTIONS]

    def test_laptop_armed_is_prod(self, capsys):
        out = _render_with(capsys, PROD=_prod_section(_m("ARMED"), _m("DRY")))
        assert "prod is the laptop: ARMED" in out

    def test_laptop_disarmed_is_not_prod(self, capsys):
        out = _render_with(capsys, PROD=_prod_section(_m("DRY"), _m("DRY")))
        assert "no machine is measured armed" in out and "nothing is sent" in out

    def test_both_armed_prints_the_warning(self, capsys):
        out = _render_with(capsys, PROD=_prod_section(_m("ARMED"), _m("ARMED")))
        assert "WARNING: TWO ARMED SCHEDULERS ON ONE ALPACA ACCOUNT" in out

    def test_vm_unreachable_reads_unmeasured(self, capsys):
        from ops import prod_state
        vm = prod_state.vm_unmeasured("`ssh ... quantt-vm 'sh -s'` did not finish within 10s")
        out = _render_with(capsys, PROD=_prod_section(_m("ARMED"), vm))
        assert "UNMEASURED — `ssh" in out and "not ruled out" in out

    def test_live_equity_is_the_armed_machines_not_the_probe_snapshots(self, capsys):
        out = _render_with(capsys, ALPACA=ALPACA_SEC,
                           PROD=_prod_section(_m("DRY", equity="1.00"),
                                              _m("ARMED", equity="222.22")))
        assert "live book" not in out and "nothing trades" not in out
        assert "$222.22 — snapshot read after the 2026-01-06 close" in out
        assert "close — broker-confirmed" not in out     # the 2026-10-19 ruling: a snapshot
        assert "99999.99" not in out and "99,999.99" not in out
        assert "snapshot 2026-09-28, 10 day(s) old — tradability/borrow only" in out

    def test_no_armed_machine_means_no_live_equity(self, capsys):
        out = _render_with(capsys, ALPACA=ALPACA_SEC,
                           PROD=_prod_section(_m("DRY"), _m("OFF")))
        assert "none — no machine is measured armed" in out

    def test_snapshot_age_is_measured_from_its_own_timestamp(self):
        import datetime as dt
        assert orient._snapshot_age_days("2026-09-28T19:56:38+00:00",
                                         today=dt.date(2026, 10, 8)) == 10
        assert orient._snapshot_age_days(None) is None


# --------------------------------------------------------------------- PNL --
# Team lead, 2026-10-19: Alpaca's end-of-day portfolio history is the official
# daily P&L of record; verify's after-the-close `equity - last_equity`, which
# verify.log had labelled "(official, gross)", is a snapshot, kept and never
# blended. These pin that the record leads, that the snapshot and the other two
# scores never stand in for it, and that every figure is arithmetic on the
# prod machine's file -- checked here against an independent computation on
# SYNTHETIC series (they test the code, not the market).

def _pnl_files(eod=None, scores=None, dist=None, eod_n=None, scores_n=None):
    """PROD's per-machine P&L readings, built through the real converter."""
    from ops import prod_state
    def f(key, rows, n):
        name = prod_state.PNL_FILES[key][0]
        return ({"absent": name} if rows is None else
                {"rows": rows, "n_rows": len(rows) if n is None else n, "file": name})
    raw = {"eod_equity": f("eod_equity", eod, eod_n), "scores": f("scores", scores, scores_n),
           "dist": f("dist", dist, None)}
    return prod_state.pnl_readings(raw, "quantt-vm:/s")


def _prod_with_pnl(files, arming="ARMED"):
    vm = {**_m(arming), "pnl": files}
    return _prod_section(_m("OFF"), vm)


# F (2026-01-02) is the first funded row: the 0 -> 1000 jump is the funding.
EOD_UP_DOWN = [["2026-01-01", "0", "0"], ["2026-01-02", "1000.00", "1000.00"],
               ["2026-01-05", "1050.00", "50.00"], ["2026-01-06", "1020.00", "-30.00"],
               ["2026-01-07", "1030.00", "10.00"]]


class TestPnl:
    def test_orient_has_a_pnl_section_after_prod_and_alpaca(self):
        names = [n for n, _ in orient.SECTIONS]
        assert "PNL" in names
        assert names.index("PNL") > names.index("PROD")
        assert names.index("PNL") > names.index("ALPACA")

    def test_cumulative_hwm_drawdown_and_vol_on_a_synthetic_series(self):
        import numpy as np
        o = orient.official_pnl(_pnl_files(eod=EOD_UP_DOWN)["eod_equity"])
        assert o["first_funded"] == {"date": "2026-01-02", "equity": 1000.0}
        assert o["n_sessions"] == 3
        assert o["cumulative_usd"] == pytest.approx(30.0), "the funding day is not P&L"
        assert o["hwm"] == {"date": "2026-01-05", "equity": 1050.0, "cumulative_usd": 50.0}
        assert o["drawdown_usd"] == pytest.approx(-20.0)
        assert o["drawdown_frac"] == pytest.approx(-20.0 / 1050.0)
        r = np.array([50 / 1000, -30 / 1050, 10 / 1020])
        assert o["vol"]["n"] == 3
        assert o["vol"]["annual"] == pytest.approx(r.std(ddof=1) * np.sqrt(252))
        assert o["disagreements"] == []

    def test_fewer_than_two_returns_is_a_gap_not_a_zero_vol(self):
        o = orient.official_pnl(_pnl_files(eod=EOD_UP_DOWN[:3])["eod_equity"])
        assert o["vol"]["annual"] is None and "at least 2" in o["vol"]["why"]

    def test_change_and_equity_disagreeing_is_reported_and_change_is_used(self):
        """A deposit (or a file defect) shows as change_usd != the EOD equity
        difference. Both are said; neither is averaged or silently preferred."""
        eod = [["2026-01-02", "1000.00", "0"], ["2026-01-05", "1010.00", "10.00"],
               ["2026-01-06", "1520.00", "10.00"]]
        o = orient.official_pnl(_pnl_files(eod=eod)["eod_equity"])
        assert o["cumulative_usd"] == pytest.approx(20.0)
        assert o["disagreements"] == [{"date": "2026-01-06", "change_usd": 10.0,
                                       "equity_diff_usd": 510.0}]

    @pytest.mark.parametrize("eod,n,match", [
        (None, None, "no eod_equity.csv in quantt-vm:/s"),
        ([["2026-01-02", "1000", "0"], ["2026-01-05", "1010", "UNMEASURED"]], None,
         "2026-01-05 change_usd is 'UNMEASURED'"),
        ([["2026-01-05", "1000", "0"], ["2026-01-05", "1010", "10"]], None, "date order"),
        ([["2026-01-02", "0", "0"], ["2026-01-05", "0", "0"]], None, "no funded row"),
        ([["2026-01-02", "1000", "0"], ["2026-01-05", "0", "-1000"]], None, "after funding"),
        ([["2026-01-02", "1000", "0"]], 3000, "more than the 1"),
    ])
    def test_an_unreadable_official_series_is_unmeasured_naming_the_file(self, eod, n, match):
        with pytest.raises(orient.Unmeasured, match=match) as e:
            orient.official_pnl(_pnl_files(eod=eod, eod_n=n)["eod_equity"])
        assert "eod_equity.csv" in str(e.value)

    def test_the_snapshot_never_stands_in_for_a_missing_record(self, capsys):
        """eod_equity.csv absent (the state until its collector step is
        installed): the official column reads UNMEASURED on every row, and the
        snapshot's values appear only in their own column."""
        scores = [["2026-01-05", "PASS", "777.77", "11.11"], ["2026-01-06", "PASS", "888.88", "22.22"]]
        sec = orient.pnl(_prod_with_pnl(_pnl_files(scores=scores)))
        assert "UNMEASURED" in sec["official"]
        assert [r["official"] for r in sec["table"]["rows"]] == ["UNMEASURED", "UNMEASURED"]
        assert [r["snapshot"] for r in sec["table"]["rows"]] == [777.77, 888.88]
        assert sec["table"]["sums"]["official"] == "0 of 2"
        out = _render_with(capsys, PNL=sec)
        assert "UNMEASURED — no eod_equity.csv in quantt-vm:/s" in out
        assert "distribution_scores.csv: none" in out

    def test_the_record_is_unchanged_by_the_scores_beside_it(self):
        """Never blended: changing every score leaves every official figure alone."""
        a = [["2026-01-05", "PASS", "1.00", "2.00"], ["2026-01-06", "PASS", "3.00", "4.00"]]
        b = [[d, v, "9999.00", "-9999.00"] for d, v, _s, _a in a]
        oa = orient.pnl(_prod_with_pnl(_pnl_files(eod=EOD_UP_DOWN, scores=a)))["official"]
        ob = orient.pnl(_prod_with_pnl(_pnl_files(eod=EOD_UP_DOWN, scores=b)))["official"]
        assert oa == ob

    def test_table_columns_come_from_their_own_files(self, capsys):
        scores = [["2026-01-05", "PASS", "60.00", "49.00"],
                  ["2026-01-06", "FAIL", "-10.00", "UNMEASURED"],
                  ["2026-01-06", "PASS", "-12.00", "-31.00"],
                  ["2026-01-07", "PASS", "15.00", "10.50"]]
        dist = [["2026-01-05", "48.50"], ["2026-01-07", "UNMEASURED"]]
        sec = orient.pnl(_prod_with_pnl(_pnl_files(eod=EOD_UP_DOWN, scores=scores, dist=dist)))
        rows = {r["date"]: r for r in sec["table"]["rows"]}
        assert list(rows) == ["2026-01-05", "2026-01-06", "2026-01-07"], "the record's sessions"
        assert [rows[d]["official"] for d in rows] == [50.0, -30.0, 10.0]
        assert rows["2026-01-06"]["snapshot"] == "CONFLICT", "two snapshots: neither is picked"
        assert rows["2026-01-06"]["auction"] == -31.0, "UNMEASURED beside a value contradicts nothing"
        assert rows["2026-01-06"]["dist_adj"] == "no row"
        assert rows["2026-01-07"]["dist_adj"] == "UNMEASURED"
        assert rows["2026-01-06"]["verdict"] == "FAIL/PASS"
        assert sec["table"]["sums"]["official"] == pytest.approx(30.0)
        assert sec["table"]["sums"]["auction"] == pytest.approx(28.5)
        assert sec["table"]["sums"]["snapshot"] == "2 of 3"
        assert any("-10.00, -12.00" in n for n in sec["table"]["notes"])
        out = _render_with(capsys, PNL=sec)
        assert "a SNAPSHOT, not the record" in out
        assert "+$30.00 over 3 session(s)" in out
        assert "$1,050.00 at the 2026-01-05 close; drawdown from it -$20.00 (-1.90%)" in out

    def test_dates_before_a_cut_tail_are_not_read_never_no_row(self):
        scores = [["2026-01-07", "PASS", "15.00", "10.50"]]
        sec = orient.pnl(_prod_with_pnl(_pnl_files(eod=EOD_UP_DOWN, scores=scores, scores_n=40)))
        rows = {r["date"]: r for r in sec["table"]["rows"]}
        assert rows["2026-01-05"]["snapshot"] == "not read"
        assert rows["2026-01-07"]["snapshot"] == "not read", "the first carried date may be partial"

    @pytest.mark.parametrize("prod,match", [
        ({"UNMEASURED": "ssh timed out"}, "PROD could not be measured"),
        ("two", "two machines are armed"),
        ("none", "no machine is measured armed"),
    ])
    def test_no_single_prod_means_no_pnl(self, prod, match):
        files = _pnl_files(eod=EOD_UP_DOWN)
        if prod == "two":
            prod = _prod_section({**_m("ARMED"), "pnl": files}, {**_m("ARMED"), "pnl": files})
        elif prod == "none":
            prod = _prod_with_pnl(files, arming="DRY")
        with pytest.raises(orient.Unmeasured, match=match):
            orient.pnl(prod)

    def test_only_the_prod_machines_files_are_read(self):
        other = _pnl_files(eod=[["2026-01-02", "5.00", "0"], ["2026-01-05", "6.00", "1.00"]])
        sec = orient.pnl(_prod_section({**_m("OFF"), "pnl": other},
                                       {**_m("ARMED"), "pnl": _pnl_files(eod=EOD_UP_DOWN)}))
        assert sec["prod"] == "vm" and sec["official"]["cumulative_usd"] == pytest.approx(30.0)

    def test_collect_hands_prod_to_pnl_without_a_second_measurement(self, monkeypatch):
        prod = _prod_with_pnl(_pnl_files(eod=EOD_UP_DOWN))
        monkeypatch.setattr(orient, "SECTIONS", [("PROD", lambda: prod), ("PNL", orient.pnl)])
        d = orient.collect(run_tests=False)
        assert d["sections"]["PNL"]["official"]["cumulative_usd"] == pytest.approx(30.0)
        assert json.loads(json.dumps(d, default=str))["sections"]["PNL"]

    def test_other_vm_books_get_their_own_record_never_summed(self, capsys):
        """C4 is its own Alpaca account on the VM (team lead 2026-11-18: as
        reachable as the core). Synthetic rows: they test the reader, not C4."""
        c4 = _pnl_files(eod=[["2026-01-02", "500.00", "0"], ["2026-01-05", "493.00", "-7.00"]])
        vm = {**_m("ARMED"), "pnl": _pnl_files(eod=EOD_UP_DOWN),
              "books": {"c4": {**_m("ARMED"), "pnl": c4},
                        "x9": {"UNMEASURED": "its reply was cut short"}}}
        sec = orient.pnl(_prod_section(_m("OFF"), vm))
        assert sec["official"]["cumulative_usd"] == pytest.approx(30.0), "the core's, unchanged"
        b = sec["books"]["c4"]
        assert b["official"]["cumulative_usd"] == pytest.approx(-7.0) and "vol_target" not in b
        assert "cut short" in sec["books"]["x9"]["official"]["UNMEASURED"]
        out = _render_with(capsys, PNL=sec)
        assert "book c4: official P&L" in out and "-$7.00 over 1 session(s)" in out
        assert "book x9: official P&L" in out and out.count("vol target (spec)") == 1
        assert out.count("a SNAPSHOT, not the record") == 1, "one legend, under the core"

    def test_the_laptop_as_prod_lists_no_vm_books(self):
        vm = {**_m("OFF"), "pnl": _pnl_files(eod=EOD_UP_DOWN),
              "books": {"c4": {**_m("ARMED"), "pnl": _pnl_files(eod=EOD_UP_DOWN)}}}
        sec = orient.pnl(_prod_section({**_m("ARMED"), "pnl": _pnl_files(eod=EOD_UP_DOWN)}, vm))
        assert sec["prod"] == "laptop" and sec["books"] == {}


class TestPnlVolTargetIsReadFromTheSpec:
    def test_it_is_the_spec_readers_value(self):
        import importlib
        import sys
        sys.path.insert(0, str(orient.REPO / "scripts/cef"))
        sp = importlib.import_module("spec")
        vt = orient._vol_target()
        assert vt == {"value": sp.frozen("vol_target_annual"), "spec_id": sp.SPEC_ID}

    def test_a_missing_key_is_a_named_gap_and_no_default_is_printed(self, monkeypatch, capsys):
        import sys
        import types

        class SpecError(KeyError):
            pass

        def frozen(key):
            raise SpecError(f"frozen spec has no key '{key}'")
        monkeypatch.setitem(sys.modules, "spec", types.SimpleNamespace(frozen=frozen, SPEC_ID="x"))
        vt = orient._vol_target()
        assert "UNMEASURED" in vt and "vol_target_annual" in vt["UNMEASURED"]
        sec = {"official": {"UNMEASURED": "no eod_equity.csv"}, "prod": "vm", "vol_target": vt,
               "table": {"rows": [], "sums": {}, "notes": [], "file_gaps": []}}
        out = _render_with(capsys, PNL={**sec, "reproducer": "r"})
        assert "vol target (spec)             UNMEASURED" in out
        assert "0.06" not in out and "6.00%" not in out
