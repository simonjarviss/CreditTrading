"""The trial registry: stored series come back byte-identical, a judged result
is never replaced, and the bar's inputs are measured from the series.

The counter table is replaced by a fixture, so these tests never depend on how
many trials the live table holds today (H14).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research import registry as rg  # noqa: E402


@pytest.fixture
def reg(tmp_path, monkeypatch):
    monkeypatch.setattr(rg, "_counters", lambda: {"CEF": {"trials": 4}, "MACRO": {"trials": 0}})
    monkeypatch.setattr(rg, "_slates", lambda: {})          # no declared slate unless a test sets one
    real_git = rg._git
    monkeypatch.setattr(rg, "_git", lambda *a: "" if a[0] == "status" else real_git(*a))
    return tmp_path


def _pnl(seed=0, n=600, start="2015-01-01", base=None, rho=0.0):
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0004, 0.01, n)
    if base is not None:
        x = rho * base.to_numpy() + np.sqrt(1 - rho ** 2) * x
    return pd.Series(x, index=pd.bdate_range(start, periods=n))


def test_round_trip_and_ledger(reg):
    s = _pnl()
    line = rg.record(s, counter="CEF", trial="CEF-1", variant="band_0.048", params={"b": 0.048}, root=reg)
    back = rg.load(line, root=reg)
    assert np.array_equal(back.to_numpy(), s.to_numpy()) and back.index.equals(s.index)
    ledger = [json.loads(x) for x in (reg / rg.LEDGER).read_text().splitlines()]
    assert len(ledger) == 1 and ledger[0]["sha256"] == line["sha256"]
    assert ledger[0]["kurt"] == pytest.approx(s.kurt() + 3)       # raw kurtosis, inference's convention
    assert ledger[0]["first"] == "2015-01-01" and ledger[0]["n"] == 600


def test_same_bytes_is_a_noop_different_bytes_refused(reg):
    s = _pnl()
    a = rg.record(s, counter="CEF", trial="CEF-1", variant="v", params={}, root=reg)
    b = rg.record(s.copy(), counter="CEF", trial="CEF-1", variant="v", params={}, root=reg)
    assert a == b and len((reg / rg.LEDGER).read_text().splitlines()) == 1
    with pytest.raises(ValueError, match="never replaced"):
        rg.record(s * 1.01, counter="CEF", trial="CEF-1", variant="v", params={}, root=reg)


@pytest.mark.parametrize("kw, match", [
    (dict(counter="NOPE"), "not in the canonical table"),
    (dict(trial="../x"), "must match"),
    (dict(trial="CEF-5"), "canonical count"),
    (dict(trial="E1-rerun"), "must be CEF-<n>"),
    (dict(variant="a b"), "must match"),
])
def test_refusals(reg, kw, match):
    args = dict(counter="CEF", trial="CEF-1", variant="v", params={}, root=reg)
    args.update(kw)
    with pytest.raises(ValueError, match=match):
        rg.record(_pnl(), **args)


def test_bad_series_refused(reg):
    s = _pnl()
    s.iloc[3] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        rg.record(s, counter="CEF", trial="CEF-1", variant="v", params={}, root=reg)
    with pytest.raises(ValueError, match="constant"):
        rg.record(s.fillna(0) * 0 + 0.001, counter="CEF", trial="CEF-1", variant="w", params={}, root=reg)
    with pytest.raises(TypeError, match="JSON"):
        rg.record(_pnl(), counter="CEF", trial="CEF-1", variant="x", params={"f": object()}, root=reg)


def test_dirty_tree_refused_unless_flagged(tmp_path, monkeypatch):
    monkeypatch.setattr(rg, "_counters", lambda: {"CEF": {"trials": 1}})
    real_git = rg._git
    monkeypatch.setattr(rg, "_git", lambda *a: " M x.py" if a[0] == "status" else real_git(*a))
    with pytest.raises(RuntimeError, match="uncommitted"):
        rg.record(_pnl(), counter="CEF", trial="CEF-1", variant="v", params={}, root=tmp_path)
    line = rg.record(_pnl(), counter="CEF", trial="CEF-1", variant="v", params={}, root=tmp_path,
                     allow_dirty=True)
    assert line["dirty"] is True


def test_tampered_series_refused(reg):
    line = rg.record(_pnl(), counter="CEF", trial="CEF-1", variant="v", params={}, root=reg)
    p = reg / line["path"]
    df = pd.read_parquet(p)
    df.iloc[0, 0] += 1e-9
    df.to_parquet(p)
    with pytest.raises(ValueError, match="altered"):
        rg.load(line, root=reg)


def test_matrix_reports_what_the_intersection_dropped(reg):
    rg.record(_pnl(1), counter="CEF", trial="CEF-1", variant="a", params={}, root=reg)
    rg.record(_pnl(2, n=500, start="2015-03-02"), counter="CEF", trial="CEF-1", variant="b", params={}, root=reg)
    M, info = rg.matrix("CEF", root=reg)
    assert M.shape[1] == 2 and info["common_sessions"] == len(M) == 500
    assert info["dropped"] == info["union_sessions"] - 500 > 0


def test_bar_inputs_measure_correlation_and_coverage(reg):
    base = _pnl(10)
    rg.record(base, counter="CEF", trial="CEF-1", variant="a", params={}, root=reg)
    rg.record(_pnl(11, base=base, rho=0.999), counter="CEF", trial="CEF-1", variant="b", params={}, root=reg)
    rg.record(_pnl(12, base=base, rho=0.999), counter="CEF", trial="CEF-1", variant="c", params={}, root=reg)
    b = rg.bar_inputs("CEF", root=reg)
    assert b["variants"] == 3 and b["n_effective"] < 1.1     # three near-copies are about one trial
    assert b["stored_trials"] == 1 and b["coverage"] == 0.25
    assert b["paper_bar_may_gate"] is False                  # 1 of the counter's 4 trials stored
    for n in (2, 3, 4):
        rg.record(_pnl(20 + n), counter="CEF", trial=f"CEF-{n}", variant="a", params={}, root=reg)
    b = rg.bar_inputs("CEF", root=reg)
    assert b["paper_bar_may_gate"] is True and b["sr_var"] > 0
    assert 3.5 < b["n_effective"] < 6


def test_independent_variants_count_fully(reg):
    for i in range(4):
        rg.record(_pnl(30 + i), counter="CEF", trial=f"CEF-{i + 1}", variant="a", params={}, root=reg)
    b = rg.bar_inputs("CEF", root=reg)
    assert b["n_effective"] == pytest.approx(4, abs=0.3)


def test_case_only_variant_cannot_overwrite(reg):
    """On a case-insensitive volume, 'wide' used to overwrite 'Wide.parquet'
    (quant-reviewer, 2026-10-28)."""
    line = rg.record(_pnl(1), counter="CEF", trial="CEF-1", variant="Wide", params={}, root=reg)
    with pytest.raises(ValueError, match="case-folded"):
        rg.record(_pnl(2), counter="CEF", trial="CEF-1", variant="wide", params={}, root=reg)
    assert rg.load(line, root=reg).equals(rg.load(line, root=reg))   # still loads, sha intact


def test_ids_outside_the_canonical_count_do_not_fake_coverage(tmp_path, monkeypatch):
    """Coverage once counted any distinct id: E1, E1-rerun and E1_fix covered a
    counter of 3 (quant-reviewer, 2026-10-28). Now only <COUNTER>-<n> with
    n <= the canonical count counts."""
    real_git = rg._git
    monkeypatch.setattr(rg, "_git", lambda *a: "" if a[0] == "status" else real_git(*a))
    monkeypatch.setattr(rg, "_counters", lambda: {"EVENTS": {"trials": 9}})
    for n in (1, 7, 8, 9):
        rg.record(_pnl(n), counter="EVENTS", trial=f"EVENTS-{n}", variant="a", params={}, root=tmp_path)
    monkeypatch.setattr(rg, "_counters", lambda: {"EVENTS": {"trials": 3}})
    b = rg.bar_inputs("EVENTS", root=tmp_path)
    assert b["stored_trials"] == 1 and b["paper_bar_may_gate"] is False


def test_an_untracked_runner_makes_the_tree_dirty(tmp_path, monkeypatch):
    monkeypatch.setattr(rg, "_counters", lambda: {"CEF": {"trials": 1}})
    real_git = rg._git

    def fake(*a):
        if a[0] == "status":
            return "?? scripts/research/new_trial/run.py" if "--untracked-files=all" in a else ""
        return real_git(*a)
    monkeypatch.setattr(rg, "_git", fake)
    with pytest.raises(RuntimeError, match="uncommitted"):
        rg.record(_pnl(), counter="CEF", trial="CEF-1", variant="v", params={}, root=tmp_path)


# -- the paper's bar with the team lead's 2026-10-28 safeguards ---------------
# Checked to fail against:
# - paper_sr0 built from bar_inputs' raw n_effective and sr_var (the floor test);
# - bar_inputs' old rho_bar = 1.0 for one series with no guard, which returned a
#   bar of zero (the one-trial test);
# - a desk bar at the canonical count rather than the declared N, and either bar
#   on the other's T (the bars test);
# - rho_bar and V measured across every stored variant rather than one series
#   per trial (the duplicates test);
# - a least N of the counter alone, ignoring the slates (the slate tests).

import json as _json  # noqa: E402

from scripts.research import inference as I  # noqa: E402


def _same_sharpe(seed, n=600):
    """Independent noise, rescaled so every series has the same sample Sharpe:
    the measured V[SR] is ~0, as EVENTS' two trials nearly were on 2026-10-28."""
    z = np.random.default_rng(seed).normal(size=n)
    x = (z - z.mean()) / z.std(ddof=1) * 0.01 + 0.0005
    return pd.Series(x, index=pd.bdate_range("2015-01-01", periods=n))


def test_paper_sr0_is_safeguarded_sr0_on_the_measured_inputs(reg):
    for n in range(1, 5):
        rg.record(_pnl(40 + n), counter="CEF", trial=f"CEF-{n}", variant="a", params={}, root=reg)
    b = rg.bar_inputs("CEF", root=reg)                   # one series per trial: the same inputs
    p = rg.paper_sr0("CEF", declared_n=6, root=reg)
    assert p["sr0"] == I.safeguarded_sr0(6, b["rho_bar"], b["sr_var"], b["T"])
    assert p["sr_var_used"] == max(b["sr_var"], 1 / b["T"])
    assert p["sr0"] == pytest.approx(np.sqrt(p["sr_var_used"]) * I.expected_max_z(p["n_effective"]))
    assert p["sr0_annual"] == pytest.approx(p["sr0"] * np.sqrt(252))
    assert p["T"] == b["T"] and p["declared_n"] == 6 and len(p["trials"]) == 4


def test_paper_sr0_floors_v_where_the_raw_inputs_collapse(reg):
    for n in range(1, 5):
        rg.record(_same_sharpe(50 + n), counter="CEF", trial=f"CEF-{n}", variant="a", params={}, root=reg)
    b = rg.bar_inputs("CEF", root=reg)
    p = rg.paper_sr0("CEF", declared_n=4, root=reg)
    assert p["floor_binds"] is True and p["sr_var_used"] == p["sr_var_floor"] == 1 / b["T"]
    floored = np.sqrt(1 / b["T"]) * I.expected_max_z(I.effective_trials(4, max(b["rho_bar"], 0.0)))
    assert p["sr0"] == pytest.approx(floored, rel=1e-12)
    raw = np.sqrt(b["sr_var"]) * I.expected_max_z(b["n_effective"])
    assert raw < p["sr0"] / 100                          # the 0.06-style collapse, avoided


def test_duplicate_variants_do_not_move_the_paper_bar(reg):
    """Eight near-copies of one trial moved EVENTS' bar from 0.363 to 0.239 when
    rho was measured across variants (quant-reviewer, 2026-10-28)."""
    base = _pnl(90)
    rg.record(base, counter="CEF", trial="CEF-1", variant="a", params={}, root=reg, judged=True)
    for n in range(2, 5):
        rg.record(_pnl(90 + n), counter="CEF", trial=f"CEF-{n}", variant="a", params={}, root=reg)
    before = rg.paper_sr0("CEF", declared_n=4, root=reg)
    for k in range(7):
        rg.record(_pnl(200 + k, base=base, rho=0.96), counter="CEF", trial="CEF-1", variant=f"dup{k}",
                  params={}, root=reg)
    after = rg.paper_sr0("CEF", declared_n=4, root=reg)
    assert after["sr0"] == before["sr0"] and after["trials"] == before["trials"]
    assert rg.bar_inputs("CEF", root=reg)["rho_bar"] > before["rho_bar"] + 0.1   # the raw input did move


def test_a_trial_with_several_variants_must_mark_one_judged(reg):
    for n in range(1, 5):
        rg.record(_pnl(110 + n), counter="CEF", trial=f"CEF-{n}", variant="a", params={}, root=reg)
    rg.record(_pnl(120), counter="CEF", trial="CEF-2", variant="b", params={}, root=reg)
    with pytest.raises(rg.PaperBarRefused, match="CEF-2 stores 2 variants and 0 are marked judged"):
        rg.paper_sr0("CEF", declared_n=4, root=reg)
    rg.record(_pnl(121), counter="CEF", trial="CEF-2", variant="c", params={}, root=reg, judged=True)
    with pytest.raises(ValueError, match="already has a judged variant"):
        rg.record(_pnl(122), counter="CEF", trial="CEF-2", variant="d", params={}, root=reg, judged=True)
    with pytest.raises(ValueError, match="never changed"):
        rg.record(_pnl(120), counter="CEF", trial="CEF-2", variant="b", params={}, root=reg, judged=True)
    assert rg.paper_sr0("CEF", declared_n=4, root=reg)["trials"][1] == "CEF-2/c"


def test_paper_sr0_refusals(reg, monkeypatch):
    rg.record(_pnl(60), counter="CEF", trial="CEF-1", variant="a", params={}, root=reg)
    rg.record(_pnl(61), counter="CEF", trial="CEF-1", variant="b", params={}, root=reg, judged=True)
    with pytest.raises(rg.PaperBarRefused, match="does not qualify"):
        rg.paper_sr0("CEF", declared_n=4, root=reg)      # 1 of 4 trials stored
    for bad in (0, True, 2.5, "6"):
        with pytest.raises(ValueError, match="positive integer"):
            rg.paper_sr0("CEF", declared_n=bad, root=reg)
    monkeypatch.setattr(rg, "_counters", lambda: {"CEF": {"trials": 2}})
    rg.record(_pnl(62), counter="CEF", trial="CEF-2", variant="a", params={}, root=reg)
    assert rg.paper_sr0("CEF", declared_n=2, root=reg)["sr0"] > 0
    with pytest.raises(ValueError, match="below"):
        rg.paper_sr0("CEF", declared_n=1, root=reg)      # a slate smaller than the trials spent


def test_one_stored_trial_has_no_correlation_and_no_paper_bar(tmp_path, monkeypatch):
    """bar_inputs used to report rho_bar = 1.0 here. Fed to the safeguards, that
    is one effective trial and a bar of zero whatever the declared N."""
    monkeypatch.setattr(rg, "_counters", lambda: {"MACRO": {"trials": 1}})
    monkeypatch.setattr(rg, "_slates", lambda: {})
    real_git = rg._git
    monkeypatch.setattr(rg, "_git", lambda *a: "" if a[0] == "status" else real_git(*a))
    rg.record(_pnl(70), counter="MACRO", trial="MACRO-1", variant="a", params={}, root=tmp_path)
    b = rg.bar_inputs("MACRO", root=tmp_path)
    assert b["paper_bar_may_gate"] is True and b["rho_bar"] is None and b["sr_var"] is None
    assert b["n_effective"] == 1.0
    with pytest.raises(rg.PaperBarRefused, match="unmeasured"):
        rg.paper_sr0("MACRO", declared_n=6, root=tmp_path)


def test_bars_reports_both_bars_at_the_declared_n_each_on_its_own_t(reg, monkeypatch):
    """CEF-2 is 100 sessions longer than the others: the desk's bar uses its own T
    (700), the paper's floor the trials' common T (600). One shared index in
    every fixture would let a swap pass (quant-reviewer, 2026-10-28)."""
    for n in (1, 3, 4):
        rg.record(_pnl(80 + n), counter="CEF", trial=f"CEF-{n}", variant="a", params={}, root=reg)
    last = pd.bdate_range("2015-01-01", periods=600)[-1]
    start = pd.bdate_range(end=last, periods=700)[0].date().isoformat()     # same last day, 100 earlier
    rg.record(_pnl(82, n=700, start=start), counter="CEF", trial="CEF-2", variant="a", params={}, root=reg)
    r = rg.bars("CEF", trial="CEF-2", variant="a", declared_n=6, root=reg)
    x = rg.load(rg.entries("CEF", trials=["CEF-2"], root=reg)[0], root=reg).to_numpy()
    sr = x.mean() / x.std(ddof=1)
    skew, kurt = pd.Series(x).skew(), pd.Series(x).kurt() + 3
    assert len(x) == 700 == r["T"] == r["desk"]["T"] and r["paper"]["T_common"] == 600
    assert r["desk"]["n_trials"] == 6 and r["canonical_trials"] == 4
    assert r["desk"]["sr0"] == pytest.approx(np.sqrt(1 / 700) * I.upper_bound_max_z(6), rel=1e-12)
    assert r["desk"]["dsr"] == pytest.approx(I.desk_dsr(sr * np.sqrt(252), 700, skew, kurt, 6), rel=1e-12)
    p = rg.paper_sr0("CEF", declared_n=6, root=reg)
    assert p["T"] == 600 and r["paper"]["sr0"] == p["sr0"] and r["paper_refused"] is None
    assert r["paper"]["dsr"] == pytest.approx(I.psr(sr, 700, skew, kurt, p["sr0"]), rel=1e-12)
    with pytest.raises(ValueError, match="below"):
        rg.bars("CEF", trial="CEF-2", variant="a", declared_n=3, root=reg)
    monkeypatch.setattr(rg, "_counters", lambda: {"CEF": {"trials": 5}})   # CEF-5 has no series
    r = rg.bars("CEF", trial="CEF-2", variant="a", declared_n=6, root=reg)
    assert r["paper"] is None and "does not qualify" in r["paper_refused"]
    assert r["desk"]["dsr"] > 0                          # the desk's bar is still reported


# -- declared slates ----------------------------------------------------------

_SLATES = [
    dict(counter="EVENTS", declared_n=6, status="standing", ruled="2026-10-19", source="SYSTEM.md §5"),
    dict(counter="XASSET", declared_n=4, status="closed", ruled="2026-10-14", source="RESEARCH_STATE.md",
         closed_at=4),
]


@pytest.fixture
def slates(tmp_path, monkeypatch):
    monkeypatch.setattr(rg, "_counters", lambda: {"EVENTS": {"trials": 2}, "XASSET": {"trials": 4},
                                                  "MACRO": {"trials": 0}})
    f = tmp_path / "declared_slates.json"
    f.write_text(_json.dumps({"slates": _SLATES}))
    monkeypatch.setattr(rg, "SLATES", f)
    return f


def test_a_standing_slate_sets_the_least_n(slates):
    m = rg.minimum_declared_n("EVENTS", pending=1)
    assert m["counter_after"] == 3 and m["minimum"] == 6 and not m["needs_ruling"]
    assert rg.minimum_declared_n("MACRO", pending=1)["minimum"] == 1       # a running count
    # The quant-reviewer's case: an EVENTS trial declared at 3 is refused at the
    # choke point, before either bar is computed or any series is read.
    for f in (rg.paper_sr0, lambda c, **k: rg.bars(c, trial="EVENTS-1", variant="a", **k)):
        with pytest.raises(ValueError, match="below EVENTS's least N 6"):
            f("EVENTS", declared_n=3, root=slates.parent / "no_ledger")


def test_a_closed_slate_takes_no_new_trial(slates, monkeypatch):
    m = rg.minimum_declared_n("XASSET")
    assert m["minimum"] == 4 and not m["needs_ruling"]                    # X1-X4 keep their N
    m = rg.minimum_declared_n("XASSET", pending=1)
    assert m["needs_ruling"] and m["minimum"] is None and "team lead" in m["why"]
    monkeypatch.setattr(rg, "_counters", lambda: {"EVENTS": {"trials": 2}, "XASSET": {"trials": 5},
                                                  "MACRO": {"trials": 0}})
    with pytest.raises(ValueError, match="closed with 4 trials"):
        rg.paper_sr0("XASSET", declared_n=9, root=slates.parent / "no_ledger")


def test_slate_cli_exits_non_zero_on_a_refused_n(slates, capsys):
    assert rg.main(["slate", "EVENTS", "--pending", "1", "--declared-n", "5"]) == 1
    assert _json.loads(capsys.readouterr().out)["ok"] is False
    assert rg.main(["slate", "EVENTS", "--pending", "1", "--declared-n", "6"]) == 0
    assert rg.main(["slate", "XASSET", "--pending", "1", "--declared-n", "9"]) == 1


@pytest.mark.parametrize("rows, match", [
    (_SLATES + [dict(_SLATES[0], declared_n=8)], "more than one standing"),
    ([dict(_SLATES[0], counter="EVENT")], "not a canonical counter"),
    ([dict(_SLATES[0], status="open")], "standing or closed"),
    ([dict(_SLATES[0], declared_n=0)], "positive integer"),
    ([{k: v for k, v in _SLATES[0].items() if k != "source"}], "lacks"),
    ([{k: v for k, v in _SLATES[1].items() if k != "closed_at"}], "closed_at must be"),
    ([dict(_SLATES[0], closed_at=3)], "only a closed slate"),
])
def test_a_malformed_slate_table_is_refused(slates, rows, match):
    slates.write_text(_json.dumps({"slates": rows}))
    with pytest.raises(ValueError, match=match):
        rg.minimum_declared_n("EVENTS")


def test_a_missing_slate_table_is_refused(slates):
    slates.unlink()
    with pytest.raises(FileNotFoundError):
        rg.minimum_declared_n("MACRO")


def test_the_tracked_slate_table_is_valid():
    """The real table parses against the real counters. Its contents are the
    team lead's rulings and are not asserted here (H14)."""
    for rows in rg._slates().values():
        assert all(r["source"].strip() for r in rows)


def test_verify_finds_a_missing_series(reg, capsys):
    a = rg.record(_pnl(1), counter="CEF", trial="CEF-1", variant="a", params={}, root=reg)
    rg.record(_pnl(2), counter="CEF", trial="CEF-2", variant="a", params={}, root=reg)
    assert rg.verify(root=reg)["ok"] is True
    (reg / a["path"]).unlink()
    v = rg.verify(root=reg)
    assert v["ok"] is False and v["lines"] == 2 and "CEF/CEF-1/a" in v["problems"][0]
    assert rg.main(["verify", "--root", str(reg)]) == 1


# -- the second review's findings (quant-reviewer, 2026-10-28) ----------------
# Checked to fail against: bars on any stored variant; trial ids grouped by
# spelling; coverage taken from the all-variant matrix; a closed slate's limit
# read from its N rather than the trials it held.

def test_bars_are_computed_only_on_the_judged_series(reg):
    for n in range(1, 5):
        rg.record(_pnl(300 + n), counter="CEF", trial=f"CEF-{n}", variant="a", params={}, root=reg,
                  judged=(n == 3))
    rg.record(_pnl(310), counter="CEF", trial="CEF-3", variant="best_of_sweep", params={}, root=reg)
    assert rg.bars("CEF", trial="CEF-3", variant="a", declared_n=4, root=reg)["paper"] is not None
    with pytest.raises(ValueError, match="not the series CEF-3 is judged on"):
        rg.bars("CEF", trial="CEF-3", variant="best_of_sweep", declared_n=4, root=reg)
    rg.record(_pnl(311), counter="CEF", trial="CEF-4", variant="b", params={}, root=reg)   # none judged
    with pytest.raises(rg.PaperBarRefused, match="CEF-4 stores 2 variants and 0"):
        rg.bars("CEF", trial="CEF-4", variant="a", declared_n=4, root=reg)


def test_a_trial_id_has_one_spelling(reg):
    """"CEF-03" used to be stored as a second trial 3 with its own judged series."""
    rg.record(_pnl(1), counter="CEF", trial="CEF-3", variant="a", params={}, root=reg, judged=True)
    for bad in ("CEF-03", "CEF-003"):
        with pytest.raises(ValueError, match="without leading zeros"):
            rg.record(_pnl(2), counter="CEF", trial=bad, variant="b", params={}, root=reg, judged=True)
    assert len(rg.entries("CEF", root=reg)) == 1


def test_a_stray_variant_on_its_own_window_breaks_neither_bar(reg):
    """A non-judged variant sharing no session with the others used to make rho
    NaN in bar_inputs and take both bars down after the trial was spent."""
    for n in range(1, 5):
        rg.record(_pnl(320 + n), counter="CEF", trial=f"CEF-{n}", variant="a", params={}, root=reg,
                  judged=(n == 2))
    rg.record(_pnl(330, n=300, start="2003-01-01"), counter="CEF", trial="CEF-2", variant="pre_sample",
              params={}, root=reg)
    b = rg.bar_inputs("CEF", root=reg)
    assert b["T"] == 0 and b["rho_bar"] is None and b["n_effective"] is None and b["paper_bar_may_gate"]
    r = rg.bars("CEF", trial="CEF-2", variant="a", declared_n=4, root=reg)
    assert r["paper"]["T_common"] == 600 and r["desk"]["dsr"] > 0


def test_a_slate_closed_below_its_n_takes_no_new_trial(slates):
    """XASSET was declared at 5 and re-declared at 4: a slate can close with
    fewer trials than its N. Read from N, a fifth trial would have joined it."""
    rows = [_SLATES[0], dict(_SLATES[1], declared_n=6, closed_at=4)]
    slates.write_text(_json.dumps({"slates": rows}))
    past = rg.minimum_declared_n("XASSET")
    assert past["minimum"] == 6 and not past["needs_ruling"]
    new = rg.minimum_declared_n("XASSET", pending=1)
    assert new["needs_ruling"] and new["minimum"] is None


# -- an old trial that gains a variant (desk-research-method session, 2026-10-28)

def test_a_variant_added_to_a_judged_trial_keeps_its_judged_series(reg):
    """The backfilled trials are one series each, now marked judged. A later
    run that stores a second variant under one of them must not change which
    series the trial is judged on, and cannot claim the judgement itself."""
    for n in range(1, 5):
        rg.record(_pnl(400 + n), counter="CEF", trial=f"CEF-{n}", variant="orig", params={}, root=reg,
                  judged=True)
    before = rg.paper_sr0("CEF", declared_n=4, root=reg)
    rg.record(_pnl(410), counter="CEF", trial="CEF-2", variant="later", params={}, root=reg)
    assert rg.paper_sr0("CEF", declared_n=4, root=reg)["sr0"] == before["sr0"]
    with pytest.raises(ValueError, match="already has a judged variant"):
        rg.record(_pnl(411), counter="CEF", trial="CEF-2", variant="later2", params={}, root=reg, judged=True)


def test_an_unflagged_sole_series_counts_until_a_second_arrives(reg):
    """Why the backfill's lines were marked: unflagged, a trial's only series is
    its judged one, but a second variant leaves none judged and the bar is
    refused, with no way to add the flag afterwards."""
    for n in range(1, 5):
        rg.record(_pnl(420 + n), counter="CEF", trial=f"CEF-{n}", variant="orig", params={}, root=reg)
    assert rg.paper_sr0("CEF", declared_n=4, root=reg)["sr0"] > 0
    rg.record(_pnl(430), counter="CEF", trial="CEF-3", variant="later", params={}, root=reg)
    with pytest.raises(rg.PaperBarRefused, match="CEF-3 stores 2 variants and 0"):
        rg.paper_sr0("CEF", declared_n=4, root=reg)


def test_every_trial_in_the_tracked_ledger_has_one_judged_series():
    """The tracked ledger itself (no series are read): each stored trial has
    exactly one line marked judged."""
    rows = rg._read_ledger(rg.ROOT)
    trials = {(r["counter"], r["trial"]) for r in rows}
    for c, t in trials:
        judged = [r for r in rows if (r["counter"], r["trial"]) == (c, t) and r.get("judged") is True]
        assert len(judged) == 1, (c, t, len(judged))


# -- refusal codes (team lead, 2026-10-28, later) -----------------------------
# The desk's bar gates a qualifying counter with ONE stored trial until a second
# is stored; any other refusal closes the standalone route. The caller tells the
# two apart by code, never by parsing the message.

def test_refusals_carry_the_code_the_ruling_keys_on(tmp_path, monkeypatch, reg):
    monkeypatch.setattr(rg, "_counters", lambda: {"MACRO": {"trials": 1}})
    rg.record(_pnl(500), counter="MACRO", trial="MACRO-1", variant="a", params={}, root=reg, judged=True)
    with pytest.raises(rg.PaperBarRefused) as e:
        rg.paper_sr0("MACRO", declared_n=1, root=reg)
    assert e.value.code == "one_trial" and "desk's bar gates" in str(e.value)
    r = rg.bars("MACRO", trial="MACRO-1", variant="a", declared_n=1, root=reg)
    assert r["paper"] is None and r["paper_refused_code"] == "one_trial" and r["desk"]["dsr"] > 0
    monkeypatch.setattr(rg, "_counters", lambda: {"MACRO": {"trials": 2}})        # MACRO-2 not stored
    r = rg.bars("MACRO", trial="MACRO-1", variant="a", declared_n=2, root=reg)
    assert r["paper_refused_code"] == "not_qualified"
    rg.record(_pnl(501), counter="MACRO", trial="MACRO-2", variant="a", params={}, root=reg, judged=True)
    r = rg.bars("MACRO", trial="MACRO-1", variant="a", declared_n=2, root=reg)
    assert r["paper"] is not None and r["paper_refused_code"] is None             # two trials: the paper's bar
