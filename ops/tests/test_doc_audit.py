"""Every check in doc_audit must be able to FAIL. Otherwise it is decoration.

WHY THIS FILE EXISTS
--------------------
Twice in one session a test in this repo passed under the exact regression it
was written to catch: `test_panel_is_invariant_to_truncation` re-derived its
targets from the same panel it was checking, and
`test_invalid_option_transmits_nothing_at_all` exercised a validator rather
than the wiring that calls it. A document-audit tool is unusually prone to the
same fault, because "everything is fine" is its happy path and an audit that
can never say otherwise looks identical to one that has nothing to report.

So each test below constructs the defect and asserts the check SEES it, then
constructs the fix and asserts the check stops seeing it. Both directions,
every time.

"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops import doc_audit as M  # noqa: E402


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "ops").mkdir()
    (tmp_path / "results").mkdir()
    monkeypatch.setattr(M, "REPO", tmp_path)
    return tmp_path


# -- banners ---------------------------------------------------------------


# -- which ops modules reach the broker -----------------------------------

def _write_broker_module(d: Path, name: str, real: bool):
    d.joinpath(name).write_text(
        "from ib_async import IB\n" if real else
        "SEARCH_FOR = 'ib_async'   # a string, not an import\n")


# -- preregs ---------------------------------------------------------------

def test_prereg_falsifier_check_fails_on_a_prereg_with_none(fake_repo):
    p = fake_repo / "results/PREREG_EMPTY.md"
    p.write_text("# Pre-registration\n\nWe will do the thing. It will work.\n")
    rep = M.Report(); M.check_prereg_shape(rep)
    assert rep.findings[0].status == M.DRIFT

    p.write_text("# Pre-registration\n\nWe will do the thing.\n\n"
                 "## Known reasons this could fail, stated in advance\n"
                 "If the holdout coefficient drops below half, abandon it.\n")
    rep = M.Report(); M.check_prereg_shape(rep)
    assert rep.findings[0].status == M.OK


def test_a_prereg_is_not_asked_for_a_reproducer(fake_repo):
    """It precedes its own run, so it cannot cite output that does not exist."""
    (fake_repo / "results/PREREG_X.md").write_text("# Prereg\n\nNo script here.\n")
    (fake_repo / "results/MEASURED_X.md").write_text("# Note\n\nNo script here.\n")
    rep = M.Report(); M.check_results_notes_have_reproducers(rep)
    by = {f.key: f for f in rep.findings}
    assert "PREREG_X.md" not in by["results_reproducers"].detail
    assert "MEASURED_X.md" in by["results_reproducers"].detail
    assert by["results_reproducers"].status == M.NOTE


def _status(rep, key):
    return {f.key: f.status for f in rep.findings}[key]


# -- the manifest ----------------------------------------------------------

def _manifest(root: Path, rows: str):
    (root / "docs/INDEX.md").write_text(
        "# Index\n\n## Roles\n\n| role | meaning |\n|---|---|\n"
        "| **canonical** | owns a question |\n| **work-order** | a prompt |\n"
        "| **manifest** | this |\n\n## The index\n\n"
        "| path | role | owns | checked by |\n|---|---|---|---|\n"
        "| `docs/INDEX.md` | manifest | the index | x |\n" + rows)


def test_an_unregistered_document_is_drift(fake_repo):
    """The seventh 'how the system works' document starts life exactly like this."""
    _manifest(fake_repo, "| `docs/SYSTEM.md` | canonical | how it runs | x |\n")
    (fake_repo / "docs/SYSTEM.md").write_text("# System\n")
    (fake_repo / "docs/ANOTHER_OVERVIEW.md").write_text("# How it all works\n")
    rep = M.Report(); M.check_manifest(rep)
    assert _status(rep, "manifest:unregistered") == M.DRIFT
    assert "ANOTHER_OVERVIEW" in {f.key: f.detail for f in rep.findings}["manifest:unregistered"]
    (fake_repo / "docs/ANOTHER_OVERVIEW.md").unlink()
    rep = M.Report(); M.check_manifest(rep)
    assert _status(rep, "manifest:unregistered") == M.OK


def test_results_and_archive_need_no_row(fake_repo):
    _manifest(fake_repo, "")
    (fake_repo / "results/NOTE_2026-09-13.md").write_text("# dated\n")
    (fake_repo / "_archive/docs").mkdir(parents=True)
    (fake_repo / "_archive/docs/OLD.md").write_text("# old\n")
    (fake_repo / "ops/HALT_book.md").write_text("# halt\n")
    rep = M.Report(); M.check_manifest(rep)
    assert _status(rep, "manifest:unregistered") == M.OK


def test_a_ghost_row_is_drift(fake_repo):
    _manifest(fake_repo, "| `docs/MOVED_AWAY.md` | canonical | x | x |\n")
    rep = M.Report(); M.check_manifest(rep)
    assert _status(rep, "manifest:ghosts") == M.DRIFT


def test_an_unknown_role_is_drift(fake_repo):
    _manifest(fake_repo, "| `docs/A.md` | authoritative-ish | x | x |\n")
    (fake_repo / "docs/A.md").write_text("# A\n")
    rep = M.Report(); M.check_manifest(rep)
    assert _status(rep, "manifest:roles") == M.DRIFT


def test_one_question_two_owners_is_drift(fake_repo):
    _manifest(fake_repo, "| `docs/A.md` | canonical | how it runs | x |\n"
                         "| `docs/B.md` | canonical | How it runs | x |\n")
    (fake_repo / "docs/A.md").write_text("# A\n")
    (fake_repo / "docs/B.md").write_text("# B\n")
    rep = M.Report(); M.check_manifest(rep)
    assert _status(rep, "manifest:owners") == M.DRIFT


def test_exact_row_beats_glob_and_two_globs_are_ambiguous(fake_repo):
    (fake_repo / "docs/prompts/sub").mkdir(parents=True)
    (fake_repo / "docs/prompts/README.md").write_text("# index\n")
    (fake_repo / "docs/prompts/sub/W1.md").write_text("# w1\n")
    _manifest(fake_repo, "| `docs/prompts/README.md` | canonical | queue | x |\n"
                         "| `docs/prompts/**/*.md` | work-order | — | x |\n")
    rep = M.Report(); M.check_manifest(rep)
    assert _status(rep, "manifest:unregistered") == M.OK
    assert _status(rep, "manifest:ambiguous") == M.OK
    _manifest(fake_repo, "| `docs/prompts/**/*.md` | work-order | — | x |\n"
                         "| `docs/prompts/sub/*.md` | work-order | — | x |\n")
    rep = M.Report(); M.check_manifest(rep)
    assert _status(rep, "manifest:ambiguous") == M.DRIFT


def test_glob_double_star_spans_zero_or_more_directories():
    rx = M._glob_re("docs/prompts/**/*.md")
    assert rx.match("docs/prompts/W1.md")
    assert rx.match("docs/prompts/gamma/G1.md")
    assert not rx.match("docs/other/W1.md")
    assert not M._glob_re(".claude/rules/*.md").match(".claude/rules/sub/x.md")


# -- entry points and pointers ---------------------------------------------

def test_entry_file_must_point_at_orient_and_system(fake_repo):
    (fake_repo / "CLAUDE.md").write_text("Run `python3 -m ops.orient`.\n")
    (fake_repo / "README.md").write_text("`python3 -m ops.orient`, then `docs/SYSTEM.md`.\n")
    rep = M.Report(); M.check_entry_points(rep)
    assert _status(rep, "entry:CLAUDE.md") == M.DRIFT
    assert _status(rep, "entry:README.md") == M.OK
    (fake_repo / "CLAUDE.md").write_text("`python3 -m ops.orient` then `docs/SYSTEM.md`\n")
    rep = M.Report(); M.check_entry_points(rep)
    assert _status(rep, "entry:CLAUDE.md") == M.OK


def test_a_seventh_front_door_is_drift(fake_repo):
    for f in ("CLAUDE.md", "README.md"):
        (fake_repo / f).write_text("ops.orient docs/SYSTEM.md\n## Start here\n")
    (fake_repo / "docs/PROJECT_INTRO.md").write_text("# Intro\n\n**Start here.**\n")
    rep = M.Report(); M.check_entry_points(rep)
    assert _status(rep, "entry:others") == M.DRIFT
    (fake_repo / "docs/PROJECT_INTRO.md").write_text("# Intro\n\nSee README.md.\n")
    rep = M.Report(); M.check_entry_points(rep)
    assert _status(rep, "entry:others") == M.OK


def test_a_dead_pointer_in_an_owner_document_is_drift(fake_repo, monkeypatch):
    monkeypatch.setattr(M, "POINTER_SCOPE", ("docs/SYSTEM.md",))
    (fake_repo / "ops/real.py").write_text("")
    (fake_repo / "docs/SYSTEM.md").write_text(
        "Run `python3 -m ops.real`, read `docs/GONE.md` and `_archive/docs/X.md`.\n")
    rep = M.Report(); M.check_pointers(rep)
    detail = {f.key: f.detail for f in rep.findings}["pointers:docs/SYSTEM.md"]
    assert _status(rep, "pointers:docs/SYSTEM.md") == M.DRIFT
    assert "docs/GONE.md" in detail and "_archive/docs/X.md" in detail
    assert "ops.real" not in detail
    (fake_repo / "docs/SYSTEM.md").write_text("Run `python3 -m ops.real`.\n")
    rep = M.Report(); M.check_pointers(rep)
    assert _status(rep, "pointers:docs/SYSTEM.md") == M.OK


def test_a_lane_branch_name_is_not_a_dead_pointer(fake_repo, monkeypatch):
    """`dashboard/` is a pointer root, so the branch `dashboard/work` once read as a
    missing file (2026-10-22). Only the named branches are exempt: a real dead path
    under dashboard/ is still drift."""
    monkeypatch.setattr(M, "POINTER_SCOPE", ("docs/SYSTEM.md",))
    (fake_repo / "docs/SYSTEM.md").write_text(
        "Branches `main`, `simon`, `ryan`, `james`, `lucy`.\n")
    rep = M.Report(); M.check_pointers(rep)
    assert _status(rep, "pointers:docs/SYSTEM.md") == M.OK
    (fake_repo / "docs/SYSTEM.md").write_text("See `dashboard/app.py`.\n")
    rep = M.Report(); M.check_pointers(rep)
    assert _status(rep, "pointers:docs/SYSTEM.md") == M.DRIFT


def test_runtime_artefacts_placeholders_and_panels_are_not_dead(fake_repo, monkeypatch):
    """Halt files and probe snapshots are written at run time, data/ is
    gitignored, and `<book>` is a placeholder. None is a pointer into this tree.
    (The IBKR shadow ledgers under `ops/books/*_live/` were the run-time example
    here until they were archived on 2026-09-28.)"""
    monkeypatch.setattr(M, "POINTER_SCOPE", ("docs/SYSTEM.md",))
    (fake_repo / "docs/SYSTEM.md").write_text(
        "`ops/HALT_phase0.md` `results/ops/alpaca_probe/2026-09-29_cef.json` `data/cef/p.parquet` "
        "`ops/books/<book>/_order_map.csv` `config/.env`\n")
    rep = M.Report(); M.check_pointers(rep)
    assert _status(rep, "pointers:docs/SYSTEM.md") == M.OK


def test_a_missing_module_command_is_dead(fake_repo, monkeypatch):
    monkeypatch.setattr(M, "POINTER_SCOPE", ("docs/SYSTEM.md",))
    (fake_repo / "docs/SYSTEM.md").write_text("`python3 -m ops.no_such_tool --check`\n")
    rep = M.Report(); M.check_pointers(rep)
    assert _status(rep, "pointers:docs/SYSTEM.md") == M.DRIFT


# -- citing the archive ------------------------------------------------------


def test_code_citing_a_missing_document_is_a_note_never_drift(fake_repo):
    """The frozen spec and the live sleeve cite documents in comments and cannot
    be edited casually. Visible backlog, not a failing gate."""
    (fake_repo / "src").mkdir()
    (fake_repo / "src/sleeve.py").write_text("# see docs/PLAN.md Part 2\n")
    rep = M.Report(); M.check_code_doc_pointers(rep)
    f = rep.findings[0]
    assert f.status == M.NOTE and "(gone)" in f.detail
    assert not rep.drift
    (fake_repo / "docs/PLAN.md").write_text("now exists\n")
    rep = M.Report(); M.check_code_doc_pointers(rep)
    assert rep.findings[0].status == M.OK


# -- the severity split ----------------------------------------------------

def test_note_does_not_fail_the_gate_but_drift_does(fake_repo):
    rep = M.Report()
    rep.add("a", M.NOTE, "a standing backlog")
    assert rep.drift == [] and len(rep.notes) == 1
    rep.add("b", M.DRIFT, "a contradiction")
    assert len(rep.drift) == 1


def test_the_real_repo_has_no_drift():
    """The whole point. If this fails, a document contradicts the repo."""
    rep = M.run()
    assert not rep.drift, "\n".join(f"{f.key}: {f.detail}" for f in rep.drift)


# -- spec ids --------------------------------------------------------------

def test_an_old_spec_id_standing_alone_is_drift_anywhere_a_reader_starts(fake_repo, monkeypatch):
    (fake_repo / "ops/specs").mkdir()
    (fake_repo / "ops/specs/cef_discount.frozen.json").write_text(
        '{"spec_id": "cef_discount.v6.20260906"}')
    (fake_repo / "docs/SYSTEM.md").write_text("The sleeve runs cef_discount.v5.20260731.\n")
    rep = M.Report(); M.check_spec_id(rep)
    assert _status(rep, "spec_id:docs/SYSTEM.md") == M.DRIFT
    (fake_repo / "docs/SYSTEM.md").write_text(
        "cef_discount.v6.20260906 replaced cef_discount.v5.20260731.\n")
    rep = M.Report(); M.check_spec_id(rep)
    assert _status(rep, "spec_id:docs/SYSTEM.md") == M.OK


def test_a_spec_id_inside_a_filename_is_not_a_claim(fake_repo):
    (fake_repo / "ops/specs").mkdir()
    (fake_repo / "ops/specs/cef_discount.frozen.json").write_text(
        '{"spec_id": "cef_discount.v6.20260906"}')
    (fake_repo / "docs/SYSTEM.md").write_text(
        "Revert path: `ops/_archive/cef_discount.v5.20260731.frozen.json`.\n")
    rep = M.Report(); M.check_spec_id(rep)
    assert _status(rep, "spec_id:docs/SYSTEM.md") == M.OK


# -- rotting figures ---------------------------------------------------------

@pytest.mark.parametrize("line", [
    "The suite passes 211 tests.",
    "The book has armed on 5 of 29 sessions.",
    "Two counters: **CEF = 48**, **GAMMA = 0**.",
    "python3 scripts/cef/validate.py --trials 48",
    "Thirteen dead mechanisms are listed.",
    "Prod is detached at v2026.09.10.1.",
])
def test_each_rotting_shape_is_caught_in_claude_md(fake_repo, line):
    """Every one of these stood in CLAUDE.md or README.md and went wrong."""
    (fake_repo / "CLAUDE.md").write_text(f"# Rules\n\n{line}\n")
    rep = M.Report(); M.check_rotting_figures(rep)
    assert _status(rep, "figures:CLAUDE.md") == M.DRIFT, line


def test_a_dated_labelled_observation_is_allowed(fake_repo):
    (fake_repo / "docs/SYSTEM.md").write_text(
        "The ledger was re-seeded (2026-09-13 [V], prod manifest), CEF = 48 then.\n")
    rep = M.Report(); M.check_rotting_figures(rep)
    assert _status(rep, "figures:docs/SYSTEM.md") == M.OK


def test_decisions_and_commands_are_not_figures(fake_repo):
    (fake_repo / "README.md").write_text(
        "Keep the 17. Cap 20%. `python3 scripts/cef/validate.py --trials <CEF counter>`.\n"
        "Cost grid 5 / 15 / 30bp on every table.\n")
    rep = M.Report(); M.check_rotting_figures(rep)
    assert _status(rep, "figures:README.md") == M.OK


def test_the_agent_layer_is_held_to_the_same_bar(fake_repo):
    """Skills and subagents are read before any document. "115 tests" and
    "thirteen dead mechanisms" both stood in them after they were wrong."""
    (fake_repo / ".claude/skills/spec-change").mkdir(parents=True)
    skill = fake_repo / ".claude/skills/spec-change/SKILL.md"
    skill.write_text("python3 -m pytest -q   # 115 tests\nRead `docs/prompts/W4`.\n")
    rep = M.Report(); M.check_rotting_figures(rep); M.check_pointers(rep)
    assert _status(rep, "figures:.claude/skills/spec-change/SKILL.md") == M.DRIFT
    assert _status(rep, "pointers:.claude/skills/spec-change/SKILL.md") == M.DRIFT
    skill.write_text("python3 -m pytest   # never quote the count\n")
    rep = M.Report(); M.check_rotting_figures(rep); M.check_pointers(rep)
    assert _status(rep, "figures:.claude/skills/spec-change/SKILL.md") == M.OK
    assert _status(rep, "pointers:.claude/skills/spec-change/SKILL.md") == M.OK


def test_live_prompts_are_held_to_the_figure_bar(fake_repo):
    (fake_repo / "docs/prompts").mkdir()
    w = fake_repo / "docs/prompts/W3_x.md"
    w.write_text("**Lever:** reliability. The book armed on 3 of 26 sessions.\n")
    rep = M.Report(); M.check_rotting_figures(rep)
    assert _status(rep, "figures:docs/prompts/W3_x.md") == M.DRIFT
    w.write_text("**Lever:** reliability (`python3 -m ops.session_uptime`).\n")
    rep = M.Report(); M.check_rotting_figures(rep)
    assert _status(rep, "figures:docs/prompts/W3_x.md") == M.OK


def test_agent_worktrees_are_not_audited(tmp_path, monkeypatch):
    """A background agent's git worktree (.claude/worktrees/<agent>/) is a full
    second copy of the repo at some commit. Auditing it reported its old
    documents as this tree's drift (2026-10-07 and 2026-10-08: 12-13 DRIFT, all
    inside .claude/worktrees/). Its files are not this tree's documents."""
    import ops.doc_audit as da
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "INDEX.md").write_text("# index\n")
    wt = tmp_path / ".claude" / "worktrees" / "agent-x" / "docs"
    wt.mkdir(parents=True)
    (wt / "OLD.md").write_text("an unregistered copy\n")
    (tmp_path / ".claude" / "README.md").write_text("map\n")
    monkeypatch.setattr(da, "REPO", tmp_path)
    assert not [p for p in da._authored_markdown() if p.startswith(".claude/worktrees/")]
    assert not [p for p in da._agent_layer() if p.startswith(".claude/worktrees/")]


def test_the_evidence_packs_private_cache_is_a_runtime_artefact(tmp_path, monkeypatch):
    """The cache is gitignored by ruling (2026-11-03), so a fresh clone has none; naming it
    in CLAUDE.md, docs/SYSTEM.md or a rule file must not read as a pointer to nothing.
    REPO is an empty directory here, so the cache cannot pass by merely existing (it does
    on any machine that has run snapshot_live, which is how CI's failure went unseen)."""
    monkeypatch.setattr(M, "REPO", tmp_path)
    assert M._resolves("path", "results/report/_cache_live/")
    assert M._resolves("path", "results/report/_cache_live/cef/scores_by_symbol.csv")
    assert not M._resolves("path", "results/report/_cache_elsewhere/x.csv")
