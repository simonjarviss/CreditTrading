"""CEF trial 55 (te4): K3's run length in the spec agrees with the compose run its thresholds cite.

WHY (the runner owner's round-2 answer (c), 2026-11-05). K3 trips on `risk.thin_k3_run_sessions`
reduced closes in sequence above `risk.thin_k3_net_run` (pre-registration §6.3: 3). The spec is
the only authority on that count (registry `cef_thin_stop_levels`, required under the rule since
the owner's review of 2026-11-04, item 9), and the thresholds are re-measured on the read date by
`results/cef/prereg_thin_te4/compose.py`, which counted the fit's runs with a literal 3 until this
answer. A spec could then say one run length while the compose run its notes cite measured the
rule at another, and nothing would say so. compose.py now takes the count as the REQUIRED argument
`--k3-run-sessions` and records it in compose_<stamp>.json as `k3_run_sessions`.

WHY A TEST, NOT A REGISTRY CHECK. The owner asked that "the registry refuses a spec whose
risk.thin_k3_run_sessions differs from the run length recorded in the compose file its threshold
notes cite". The owner also ruled (answer 3, round 1, 2026-11-03) that "the live path never reads
results/", and `src/deploy/registry.py` validates on the live path: the sleeve's constructor and
run.py call it on every session. So the guard is this test. CI runs it on every push
(.github/workflows/checks.yml), and prod installs only a release-checked tag (`/release-check`
runs the suite), so a spec and a compose file that disagree cannot reach a release together. The
owner can overrule this and move it into the registry; docs/RUNNER.md says the same.

`k3_run_drift(spec, compose_dir)` is the guard. For a spec that sets `risk.thin_k3_run_sessions`
it reads every `compose_<stamp>.json` named in a te4 note (the four K-line thresholds' notes, and
the run length's own note if it names one) and returns a problem, naming the note and the file,
for a cited file that is missing, unreadable, records no `k3_run_sessions` (every compose file
written before 2026-11-05) or records another count; and for a K-line threshold whose note names
no compose file (the registry already refuses that; the guard does not rely on it). A spec without
the key has nothing to agree with: [].

THE VALUES TOO (the owner's release-check of 78e3483, 2026-11-09). `compose_value_drift` holds the
four K-line values and the m and floor the compose run measured them at against the spec, so a stop
cannot be set at a level nobody measured. A line may be the compose value rounded, at 3 decimals or
more.

The AST test of compose.py fails on the commit before compose.py took --k3-run-sessions (01c7d79:
no such argument, and `runs_above` called with the literals 3 and 2). The committed-spec test is
a PIN today: no committed spec sets the key yet (te4 is dark), so it passes on the old code as
well; it bites from the activation commit. The guard's own logic is tested on synthetic specs and
compose files in tmp_path.
"""
import ast
import copy
import json
import re
from pathlib import Path

import pytest

from src.deploy import registry as R

ROOT = Path(__file__).resolve().parents[3]
COMPOSE_DIR = ROOT / "results" / "cef" / "prereg_thin_te4"
COMPOSE_PY = COMPOSE_DIR / "compose.py"
RUN_KEY = R.CEF_THIN_K3_RUN_KEY
RECORDED = "k3_run_sessions"           # compose.py's key in compose_<stamp>.json
# A compose run's JSON, as a note names it (with or without its folder): compose.py writes
# compose_<stamp>.json, and its text output is compose_output_<stamp>.txt, which never matches.
COMPOSE_JSON = re.compile(r"compose_[A-Za-z0-9][A-Za-z0-9._-]*?\.json")


def k3_run_drift(spec: dict, compose_dir: Path) -> list:
    """The problems ([] when there are none) between `spec`'s `risk.thin_k3_run_sessions` and
    the `k3_run_sessions` recorded in each compose_<stamp>.json its te4 notes cite, the files
    read from `compose_dir` (module docstring)."""
    risk = spec.get("risk") or {}
    if RUN_KEY not in risk:
        return []
    want = risk[RUN_KEY]
    cited, problems = {}, []
    for key in (*R.CEF_THIN_STOP_KEYS, RUN_KEY):
        note = risk.get(f"_{key}_note")
        names = COMPOSE_JSON.findall(note) if isinstance(note, str) else []
        if key in R.CEF_THIN_STOP_KEYS and key in risk and not names:
            problems.append(f"risk.{key} is set and its note _{key}_note names no "
                            f"compose_<stamp>.json ({note!r}): its run length cannot be checked")
        for name in names:
            cited.setdefault(name, []).append(f"_{key}_note")
    for name, notes in sorted(cited.items()):
        f = compose_dir / name
        if not f.is_file():
            problems.append(f"{name}, cited by {notes}, is not in {compose_dir}")
            continue
        try:
            rec = json.loads(f.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            problems.append(f"{name}, cited by {notes}, cannot be read: {type(e).__name__}: {e}")
            continue
        got = rec.get(RECORDED) if isinstance(rec, dict) else None
        if got is None:
            problems.append(f"{name}, cited by {notes}, records no {RECORDED}: it was written "
                            f"before compose.py took --k3-run-sessions; re-run compose.py with "
                            f"--k3-run-sessions {want!r} and cite that run")
        elif isinstance(got, bool) or not isinstance(got, int) or isinstance(want, bool) \
                or got != want:
            problems.append(f"{name}, cited by {notes}, records {RECORDED} {got!r}; the spec's "
                            f"risk.{RUN_KEY} is {want!r}")
        if isinstance(rec, dict):
            problems += compose_value_drift(spec, rec, name)
    return problems


# Where each of the spec's K-lines sits in compose_<stamp>.json (pre-registration §6.3).
COMPOSE_LINES = {
    "thin_k1_episode_drawdown": ("in_episode", "D_E", "252", "D_E"),
    "thin_k2_max_name_frac": ("in_episode", "persistence", "max_w", "max"),
    "thin_k3_net_run": ("in_episode", "persistence", "net", "p99"),
    "thin_k3_net_once": ("in_episode", "persistence", "net", "max"),
}
MIN_DECIMALS = 3                       # a line written more coarsely is another number


def _dig(rec, path):
    for k in path:
        if not isinstance(rec, dict) or k not in rec:
            return None
        rec = rec[k]
    return rec


def compose_value_drift(spec: dict, rec: dict, name: str) -> list:
    """The owner's release-check of 78e3483 (2026-11-09): beyond the run length, the four K-lines
    and the m and floor the compose run measured them at must be the spec's. So must the band,
    the gross ceiling and min_names (the independent review of PR #69, 2026-11-10): compose.py
    reads all five from the frozen spec and records them under `spec` (pre-registration §6.3),
    and a stop measured on another band, ceiling or set of reduced sessions is a level nobody
    measured for this book. compose records neither the universe nor the panel date, so those
    cannot be checked here. A line may be the
    compose value rounded, at MIN_DECIMALS or more, as the pre-registration quotes them (0.956);
    any other difference is a stop set at a level nobody measured."""
    problems, risk, frozen = [], spec.get("risk") or {}, spec.get("frozen") or {}
    for key, path in COMPOSE_LINES.items():
        if key not in risk:
            continue
        got, want = _dig(rec, path), risk[key]
        where = "/".join(path)
        if isinstance(got, bool) or not isinstance(got, (int, float)):
            problems.append(f"{name} records no {where} ({got!r}): risk.{key} cannot be checked")
            continue
        text = repr(float(want))
        places = len(text.split(".")[1]) if "." in text and "e" not in text else 0
        if places < MIN_DECIMALS:
            problems.append(f"risk.{key} is {want!r}, written to fewer than {MIN_DECIMALS} "
                            f"decimals; {name} records {where} {got!r}")
        elif round(got, places) != float(want):
            problems.append(f"risk.{key} is {want!r}; {name} records {where} {got!r}, which "
                            f"is {round(got, places)!r} at that precision")
    for label, have, path in (("frozen.sizing_multiplier", frozen.get("sizing_multiplier"), ("spec", "m")),
                              ("frozen.below_min_names_floor", frozen.get("below_min_names_floor"), ("spec", "floor")),
                              ("frozen.band_width", frozen.get("band_width"), ("spec", "band")),
                              ("frozen.max_gross_stress", frozen.get("max_gross_stress"), ("spec", "cap")),
                              ("frozen.min_names", frozen.get("min_names"), ("spec", "min_names"))):
        got = _dig(rec, path)
        if got is None or have is None or got != have:
            problems.append(f"{label} is {have!r}; {name} measured its lines at "
                            f"{'/'.join(path)} = {got!r}")
    return problems


# --------------------------------------------------------------- the committed files

def test_every_committed_spec_agrees_with_the_compose_runs_its_notes_cite():
    """The guard on every spec under ops/specs/. A PIN today (no committed spec sets the key:
    te4 is dark); from the activation commit it fails a spec whose run length differs from the
    compose run its thresholds cite."""
    specs = sorted((ROOT / "ops" / "specs").glob("*.json"))
    assert specs, "no spec under ops/specs/"
    for f in specs:
        spec = json.loads(f.read_text())
        assert k3_run_drift(spec, COMPOSE_DIR) == [], f.name


def test_the_2026_11_05_compose_run_records_its_run_length_and_the_drafting_day_one_does_not():
    """The committed compose files, read through the guard as the activation spec would cite
    them: the 2026-11-05 run (`--k3-run-sessions 3`, a126324) agrees with a spec at 3 and not
    with one at 4; the drafting-day run (2026-11-03) records no run length, so a spec citing it
    fails. Fails on 03d978b, the commit before the 2026-11-05 run (no such file)."""
    rec = json.loads((COMPOSE_DIR / "compose_2026-11-05.json").read_text())
    assert rec[RECORDED] == 3
    assert RECORDED not in json.loads((COMPOSE_DIR / "compose_2026-11-03.json").read_text())
    assert k3_run_drift(_spec("compose_2026-11-05.json", run=3), COMPOSE_DIR) == []
    bad = k3_run_drift(_spec("compose_2026-11-05.json", run=4), COMPOSE_DIR)
    assert len(bad) == 1 and "records k3_run_sessions 3" in bad[0] and "is 4" in bad[0]
    old = k3_run_drift(_spec("compose_2026-11-03.json", run=3), COMPOSE_DIR)
    assert len(old) == 1 and "records no k3_run_sessions" in old[0]


def _call_name(node) -> str:
    f = node.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


def test_compose_takes_the_run_length_as_a_required_argument_and_holds_no_literal():
    """compose.py's source, by AST (importing it would run its sys.path and warnings side
    effects inside the suite): `--k3-run-sessions` is an int argument, required, with no
    default; and no `runs_above(...)` call passes a literal run length. Fails on the commit
    before, which had neither the argument nor anything but literals (3 and 2)."""
    tree = ast.parse(COMPOSE_PY.read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    arg = [n for n in calls if _call_name(n) == "add_argument" and n.args
           and isinstance(n.args[0], ast.Constant) and n.args[0].value == "--k3-run-sessions"]
    assert len(arg) == 1, "compose.py has no --k3-run-sessions argument"
    kw = {k.arg: k.value for k in arg[0].keywords}
    assert isinstance(kw.get("required"), ast.Constant) and kw["required"].value is True
    assert "default" not in kw
    assert isinstance(kw.get("type"), ast.Name) and kw["type"].id == "int"
    runs = [n for n in calls if _call_name(n) == "runs_above"]
    assert runs, "compose.py no longer counts K3 runs with runs_above"
    literal = [ast.unparse(n) for n in runs
               if len(n.args) >= 3 and isinstance(n.args[2], ast.Constant)]
    assert literal == [], f"runs_above called with a literal run length: {literal}"


# --------------------------------------------------------------- the guard, on synthetic files

NOTE_RUN = "test only: §6.3's 3 consecutive reduced closes"
LINES = {"thin_k1_episode_drawdown": 0.1052, "thin_k2_max_name_frac": 0.956,
         "thin_k3_net_run": 0.248, "thin_k3_net_once": 0.833}


def _spec(*names, run=3, lines=LINES, run_note=NOTE_RUN):
    """A te4 risk block whose K-line notes each cite `names` (one note per line, all the same
    citation unless a name is a dict {key: name})."""
    risk = {"halve_drawdown": 0.12, "kill_drawdown": 0.18, RUN_KEY: run,
            f"_{RUN_KEY}_note": run_note}
    for k, v in lines.items():
        risk[k] = v
        cite = " and ".join(n[k] if isinstance(n, dict) else n for n in names)
        risk[f"_{k}_note"] = f"derived by compose.py: {cite} §E"
    return {"risk": risk, "frozen": {"below_min_names": "trade_eligible",
                                      "below_min_names_floor": 4, "max_gross_stress": 1.8,
                                      "sizing_multiplier": 1.3, "band_width": 0.048,
                                      "min_names": 6}}


# The record a compose run writes for LINES, at the spec's m, floor, band, ceiling and min_names.
GOOD = {"spec": {"id": "test", "m": 1.3, "band": 0.048, "cap": 1.8, "min_names": 6, "floor": 4},
        "in_episode": {"D_E": {"252": {"D_E": 0.10515826}},
                       "persistence": {"max_w": {"max": 0.95570082},
                                       "net": {"p99": 0.24831940, "max": 0.83333286}}}}


def _compose(tmp_path, name, **rec):
    (tmp_path / name).write_text(json.dumps({**GOOD, **rec}))


def _bump(path, value):
    """GOOD with one leaf replaced (a deep copy; `value` None deletes the leaf)."""
    rec = copy.deepcopy(GOOD)
    d = rec
    for k in path[:-1]:
        d = d[k]
    if value is None:
        del d[path[-1]]
    else:
        d[path[-1]] = value
    return rec


@pytest.mark.parametrize("key,path", list(COMPOSE_LINES.items()))
def test_the_guard_fails_a_k_line_that_differs_from_the_compose_run(tmp_path, key, path):
    """The owner's release-check of 78e3483: fails on the guard before it, which read only the
    run length."""
    (tmp_path / "compose_2026-12-01.json").write_text(json.dumps(
        {**_bump(path, 0.5), "k3_run_sessions": 3}))
    bad = k3_run_drift(_spec("compose_2026-12-01.json"), tmp_path)
    assert len(bad) == 1 and f"risk.{key}" in bad[0] and "/".join(path) in bad[0]


@pytest.mark.parametrize("key,path", list(COMPOSE_LINES.items()))
def test_the_guard_fails_a_compose_run_that_records_no_k_line(tmp_path, key, path):
    (tmp_path / "compose_2026-12-01.json").write_text(json.dumps(
        {**_bump(path, None), "k3_run_sessions": 3}))
    bad = k3_run_drift(_spec("compose_2026-12-01.json"), tmp_path)
    assert len(bad) == 1 and f"risk.{key} cannot be checked" in bad[0]


@pytest.mark.parametrize("path,label", [(("spec", "m"), "frozen.sizing_multiplier"),
                                        (("spec", "floor"), "frozen.below_min_names_floor"),
                                        (("spec", "band"), "frozen.band_width"),
                                        (("spec", "cap"), "frozen.max_gross_stress"),
                                        (("spec", "min_names"), "frozen.min_names")])
def test_the_guard_fails_a_compose_run_at_another_m_or_floor(tmp_path, path, label):
    """m and floor: the owner's release-check of 78e3483. band, cap and min_names: the
    independent review of PR #69 (2026-11-10), which passed a spec with each moved; those three
    cases fail on 0c5d747, whose guard compared only m and floor."""
    (tmp_path / "compose_2026-12-01.json").write_text(json.dumps(
        {**_bump(path, 2), "k3_run_sessions": 3}))
    bad = k3_run_drift(_spec("compose_2026-12-01.json"), tmp_path)
    assert len(bad) == 1 and label in bad[0]


def test_the_guard_fails_a_line_written_too_coarsely(tmp_path):
    _compose(tmp_path, "compose_2026-12-01.json", k3_run_sessions=3)
    bad = k3_run_drift(_spec("compose_2026-12-01.json",
                             lines={**LINES, "thin_k3_net_run": 0.25}), tmp_path)
    assert len(bad) == 1 and "fewer than 3 decimals" in bad[0]


def test_the_guard_accepts_a_line_at_full_precision(tmp_path):
    _compose(tmp_path, "compose_2026-12-01.json", k3_run_sessions=3)
    full = {**LINES, "thin_k3_net_run": GOOD["in_episode"]["persistence"]["net"]["p99"]}
    assert k3_run_drift(_spec("compose_2026-12-01.json", lines=full), tmp_path) == []


def test_the_guard_passes_a_spec_that_agrees(tmp_path):
    _compose(tmp_path, "compose_2026-12-01.json", k3_run_sessions=3)
    assert k3_run_drift(_spec("compose_2026-12-01.json"), tmp_path) == []
    # a note that names the file with its folder reads the same file
    assert k3_run_drift(_spec("results/cef/prereg_thin_te4/compose_2026-12-01.json"),
                        tmp_path) == []


def test_the_guard_has_nothing_to_check_without_the_key(tmp_path):
    s = _spec("compose_missing.json")
    del s["risk"][RUN_KEY]
    assert k3_run_drift(s, tmp_path) == []
    assert k3_run_drift({"risk": {}}, tmp_path) == []
    assert k3_run_drift({}, tmp_path) == []


def test_the_guard_fails_a_run_length_that_differs(tmp_path):
    _compose(tmp_path, "compose_2026-12-01.json", k3_run_sessions=3)
    bad = k3_run_drift(_spec("compose_2026-12-01.json", run=4), tmp_path)
    assert len(bad) == 1 and "compose_2026-12-01.json" in bad[0]
    assert "records k3_run_sessions 3" in bad[0] and "is 4" in bad[0]
    for k in R.CEF_THIN_STOP_KEYS:
        assert f"_{k}_note" in bad[0]
    # A recorded value of another type is not the spec's int.
    for got in (3.0, "3", True):
        _compose(tmp_path, "compose_2026-12-02.json", k3_run_sessions=got)
        assert k3_run_drift(_spec("compose_2026-12-02.json"), tmp_path), got


def test_the_guard_fails_a_cited_file_that_is_missing_unreadable_or_records_no_run_length(tmp_path):
    assert any("is not in" in p for p in k3_run_drift(_spec("compose_2026-12-01.json"), tmp_path))
    (tmp_path / "compose_2026-12-02.json").write_text("{")
    assert any("cannot be read" in p
               for p in k3_run_drift(_spec("compose_2026-12-02.json"), tmp_path))
    _compose(tmp_path, "compose_2026-12-03.json")          # the drafting day's shape
    assert any("records no k3_run_sessions" in p
               for p in k3_run_drift(_spec("compose_2026-12-03.json"), tmp_path))


def test_the_guard_reads_every_cited_file_and_the_run_lengths_own_note(tmp_path):
    """Two compose runs cited by different notes: each must agree. The run length's own note
    may cite one too, and is then held to it."""
    _compose(tmp_path, "compose_2026-12-01.json", k3_run_sessions=3)
    _compose(tmp_path, "compose_2026-12-02.json", k3_run_sessions=4)
    split = {k: ("compose_2026-12-02.json" if k == "thin_k3_net_run"
                 else "compose_2026-12-01.json") for k in LINES}
    bad = k3_run_drift(_spec(split), tmp_path)
    assert len(bad) == 1 and "compose_2026-12-02.json" in bad[0] and "_thin_k3_net_run_note" in bad[0]
    bad = k3_run_drift(_spec("compose_2026-12-01.json",
                             run_note="§6.3's 3; recorded in compose_2026-12-02.json"), tmp_path)
    assert len(bad) == 1 and f"_{RUN_KEY}_note" in bad[0]


def test_the_guard_fails_a_threshold_whose_note_cites_no_compose_run(tmp_path):
    _compose(tmp_path, "compose_2026-12-01.json", k3_run_sessions=3)
    s = _spec("compose_2026-12-01.json")
    s["risk"]["_thin_k3_net_run_note"] = "derived on the read date"
    bad = k3_run_drift(s, tmp_path)
    assert len(bad) == 1 and "thin_k3_net_run" in bad[0] and "names no" in bad[0]
    # A spec that sets the run length and no K-line: nothing cites a compose run, nothing to
    # disagree with (each absent line reads UNMEASURED in the report).
    assert k3_run_drift(_spec(lines={}), tmp_path) == []


def test_the_synthetic_spec_is_one_the_registry_accepts(tmp_path):
    """The guard is tested on the shape the registry validates: the synthetic te4 risk block
    loads through `cef_thin_stop_levels`, so the guard is not tested on a spec no release could
    carry."""
    got = R.cef_thin_stop_levels(copy.deepcopy(_spec("compose_2026-12-01.json")))
    assert got[RUN_KEY] == 3 and got["thin_k3_net_run"] == pytest.approx(0.248)
