"""The XASSET run-once guards, held to the COMMITTED verdicts at their real paths.

WHY THIS EXISTS
---------------
X1-X4 are spent: each has a committed fit verdict and an opened holdout
(`results/xasset/XASSET_RESULTS_2026-10-14.md`). Three guards in
`scripts/xasset/runner.py` keep them spent, and each decides by FINDING A FILE:

* `refuse_rerun` -- a test whose fit verdict exists (on disk or at HEAD) is
  never fitted again ("a test is run once");
* `counter_guard` -- a trial number already written into a fit verdict is never
  spent a second time;
* `holdout_guard` -- a holdout whose verdict exists is never opened again.

On 2026-10-22 the verdicts moved from `results/xasset/` to
`results/xasset/trials/` (the team lead's ruling: the dated note on top, its
data in a folder). A guard left pointing at the old folder finds nothing,
raises nothing, and lets a spent trial run again. That failure is SILENT: a
guard that does not fire looks exactly like a guard with nothing to stop, and
the synthetic pipeline tests in `test_trials.py` never touch these paths, so
nothing else in the suite would notice. The Stage 0a manifest moved with them
(`results/xasset/stage0a/`); `verify_inputs` must still find and read it before
any stage re-hashes an input.

These are claims about the code and the committed tree, not about the market.
They read the eight committed JSON verdicts, the committed manifest and git's
HEAD only: no panel, no cache, no `data/`, no network.
"""
import json
import subprocess

import pytest

from scripts.xasset import protocol as P, runner
from scripts.xasset import x1_credit_trend as x1, x2_rebalancing as x2
from scripts.xasset import x3_month_end as x3, x4_multi_trend as x4

SPECS = {"X1": x1.SPEC, "X2": x2.SPEC, "X3": x3.SPEC, "X4": x4.SPEC}


def test_the_specs_cover_the_slate():
    assert tuple(SPECS) == runner.TESTS
    assert all(SPECS[k].key == k for k in SPECS)


@pytest.mark.parametrize("key", runner.TESTS)
def test_each_verdict_is_committed_where_the_guards_look(key):
    """Both legs of `refuse_rerun` (the file on disk, the file at HEAD) and both
    files `holdout_guard` reads must be there, and must be this test's own."""
    for path in (runner.fit_json(key), runner.holdout_json(key)):
        assert path.parent == P.TRIALS, f"{P.rel(path)} is not under {P.rel(P.TRIALS)}"
        assert path.exists(), f"{P.rel(path)} is not on disk"
        assert P.git_tracked(path), f"{P.rel(path)} is not in the committed tree at HEAD"
        assert json.loads(path.read_text())["test"] == key


@pytest.mark.parametrize("key", runner.TESTS)
def test_a_spent_test_refuses_to_be_fitted_again(key):
    with pytest.raises(P.ProtocolError, match="already has a fit verdict") as exc:
        runner.refuse_rerun(SPECS[key])
    assert P.rel(runner.fit_json(key)) in str(exc.value)


@pytest.mark.parametrize("key", runner.TESTS)
def test_the_on_disk_leg_alone_refuses(key, monkeypatch):
    """With the committed-tree leg forced False, the file on disk still stops the
    rerun (an uncommitted verdict must count: the run wrote it, so it is spent)."""
    monkeypatch.setattr(P, "git_tracked", lambda path: False)
    with pytest.raises(P.ProtocolError, match="already has a fit verdict"):
        runner.refuse_rerun(SPECS[key])


@pytest.mark.parametrize("key", runner.TESTS)
def test_a_recorded_trial_number_is_not_spent_twice(key, monkeypatch):
    """`counter_guard` reads every fit verdict for the trial number it holds.

    Its first check (docs/RESEARCH_STATE.md has no uncommitted edit) is about the
    working copy, not about these files, and would make this test fail whenever
    someone is mid-edit on the counter table. Only that one git call is answered
    "clean" here; the committed counter (`git show HEAD:...`) is read for real."""
    real_run = subprocess.run
    clean = ["git", "diff", "--quiet", "HEAD", "--", "docs/RESEARCH_STATE.md"]

    class _Subprocess:
        @staticmethod
        def run(args, *a, **k):
            if list(args) == clean:
                return subprocess.CompletedProcess(args, 0)
            return real_run(args, *a, **k)

    monkeypatch.setattr(runner, "subprocess", _Subprocess)
    # The trial number is read from the committed verdict itself, NOT through
    # runner.fit_json: a guard looking in the wrong folder must show up here as a
    # guard that does not raise, not as this test failing to find its own input.
    trial = json.loads((P.TRIALS / f"{key.lower()}_fit_{runner.RUN_DATE}.json").read_text())["trial"]
    assert isinstance(trial, int)
    with pytest.raises(P.ProtocolError, match=rf"trial number {trial} is already recorded by \['{key}'\]"):
        runner.counter_guard(trial)


@pytest.mark.parametrize("key", runner.TESTS)
def test_an_opened_holdout_refuses_to_reopen(key):
    """`holdout_guard` first requires all four committed fit verdicts (else
    "holdout sealed"), then refuses because this holdout's verdict exists. The
    match is on the SECOND refusal: a guard looking in the wrong folder still
    refuses, but as "sealed", and never reaches the check that matters here."""
    with pytest.raises(P.ProtocolError, match="the holdout was already opened") as exc:
        runner.holdout_guard(SPECS[key])
    assert P.rel(runner.holdout_json(key)) in str(exc.value)


def test_the_stage0a_manifest_is_found_where_the_pin_check_reads_it():
    """`verify_inputs` halts with "Stage 0a has not ended" if it cannot find the
    manifest. Asking it for an input the manifest lacks gets a different refusal,
    one it can only give after reading the committed manifest at `P.MANIFEST`.
    The approval pins in the file must equal the protocol's."""
    assert P.MANIFEST.parent == P.STAGE0A_DIR
    assert P.MANIFEST.exists() and P.git_tracked(P.MANIFEST)
    man = json.loads(P.MANIFEST.read_text())
    assert man["stage"] == "0a"
    assert man["pins"] == dict(vol_target_annual=P.PINNED_VOL_TARGET, max_gross_stress=P.PINNED_MAX_GROSS,
                               spec_sha256=P.PINNED_SPEC_SHA256, n_slate=P.N_SLATE)
    with pytest.raises(P.ProtocolError, match="manifest has no input 'no_such_input'"):
        P.verify_inputs(keys=["no_such_input"])
