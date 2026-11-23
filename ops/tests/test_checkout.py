"""`docs/STANDARD.md` A1.1: a checkout behind `origin/main` is named at session start.

On 2026-11-22 the main dev folder was 841 commits behind `origin/main` and every
session opened there loaded a `CLAUDE.md` replaced on 2026-11-09; orient and the
banner printed only the branch and the dirty count. These tests pin the three
properties that would have caught it:

  1. the behind and ahead counts are measured from local refs, not assumed;
  2. a clone with no `origin/main` reads UNMEASURED, never "0 behind";
  3. orient TREES and the SessionStart banner both carry the reading, and the
     banner puts a WARNING first when the checkout is behind.

No network: each test builds a throwaway repository in `tmp_path` and makes
`origin/main` with `git update-ref`, which is what a fetch leaves behind.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

from ops import checkout, orient

GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, check=True,
                          capture_output=True, text=True).stdout.strip()


def _repo(tmp_path: Path, behind: int, ahead: int) -> Path:
    """A repo whose HEAD is `ahead` commits past, and `behind` commits short of, origin/main."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "work")
    _git(r, "commit", "-q", "--allow-empty", "-m", "base")
    base = _git(r, "rev-parse", "HEAD")
    for i in range(ahead):
        _git(r, "commit", "-q", "--allow-empty", "-m", f"mine {i}")
    _git(r, "switch", "-q", "-c", "upstream", base)
    for i in range(behind):
        _git(r, "commit", "-q", "--allow-empty", "-m", f"theirs {i}")
    _git(r, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(r, "switch", "-q", "work")
    return r


def test_counts_behind_and_ahead(tmp_path):
    a = checkout.against_main(_repo(tmp_path, behind=3, ahead=2))
    assert (a["behind"], a["ahead"]) == (3, 2)


def test_never_fetched_is_said(tmp_path):
    a = checkout.against_main(_repo(tmp_path, behind=1, ahead=0))
    assert a["last_fetch"] is None
    assert "never fetched" in checkout.describe(a)


def test_last_fetch_is_read_from_fetch_head(tmp_path):
    r = _repo(tmp_path, behind=0, ahead=0)
    (r / ".git" / "FETCH_HEAD").write_text("")
    assert checkout.against_main(r)["last_fetch"] is not None


def test_no_origin_main_is_unmeasured_not_zero(tmp_path):
    r = tmp_path / "bare"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "commit", "-q", "--allow-empty", "-m", "only")
    a = checkout.against_main(r)
    assert set(a) == {"UNMEASURED"}
    assert checkout.describe(a).startswith("UNMEASURED")
    assert checkout.warning(a) is None


def test_warning_only_when_behind(tmp_path):
    assert checkout.warning({"behind": 0, "ahead": 5, "last_fetch": None}) is None
    w = checkout.warning({"behind": 841, "ahead": 8, "last_fetch": "2026-11-22 12:00"})
    assert "841 commit(s) behind origin/main" in w and "CLAUDE.md" in w


def test_orient_trees_carries_the_reading(tmp_path, monkeypatch):
    """The property that failed on 2026-11-22: TREES said nothing about main."""
    monkeypatch.setattr(orient, "REPO", _repo(tmp_path, behind=4, ahead=1))
    t = orient.trees()
    assert t["dev"]["against_main"]["behind"] == 4


def _banner_module():
    path = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "session_context.py"
    spec = importlib.util.spec_from_file_location("session_context_a11", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_banner_warns_first_when_behind(monkeypatch, capsys):
    mod = _banner_module()
    monkeypatch.setattr(mod, "collect", lambda **k: {"git": {
        "branch": "research-alpha-leakage", "dirty": 148,
        "against_main": {"behind": 841, "ahead": 8, "last_fetch": "2026-11-22 12:00"}}})
    mod.main()
    lines = capsys.readouterr().out.splitlines()
    assert "WARNING" in lines[1] and "841 commit(s) behind origin/main" in lines[1]
    assert any("841 behind origin/main" in l for l in lines)


def test_banner_says_unmeasured_rather_than_nothing(monkeypatch, capsys):
    mod = _banner_module()
    monkeypatch.setattr(mod, "collect", lambda **k: {"git": {
        "branch": "x", "dirty": 0, "against_main": {"UNMEASURED": "no origin/main ref"}}})
    mod.main()
    out = capsys.readouterr().out
    assert "against origin/main UNMEASURED (no origin/main ref)" in out
    assert "WARNING" not in out
