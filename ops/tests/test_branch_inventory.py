"""`docs/STANDARD.md` A1.2: every branch and worktree has a reason to exist, or is listed as having none.

The inventory decides what a later, confirmed clean-up deletes, so the tests pin
the cases where a wrong "none" would lose something:

  - uncommitted work in a worktree keeps its branch and the tree, however old;
  - an open pull request keeps an old branch; an UNREAD pull-request list makes
    an otherwise reasonless branch UNMEASURED, never "none";
  - a worktree git cannot read (the retired IBKR tree on 2026-11-22) is
    UNMEASURED, and the run does not crash on it;
  - the tree detached at the newest release tag is kept (a release wrapper
    replays from it);
  - the lane list matches `docs/TEAM.md` §3.

No network: a throwaway repository in `tmp_path`; remote refs are made with
`git update-ref`; the pull-request list is passed in.
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path

import pytest

from ops import branch_inventory as bi

NOW = dt.datetime(2026, 11, 22, 12, 0, tzinfo=dt.timezone.utc)
OLD = "2026-10-01T12:00:00+00:00"
RECENT = "2026-11-20T12:00:00+00:00"


def _git(repo: Path, *args: str, date: str = RECENT) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
           "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    return subprocess.run(["git", *args], cwd=repo, env=env, check=True,
                          capture_output=True, text=True).stdout.strip()


def _branch(repo: Path, name: str, date: str) -> None:
    _git(repo, "switch", "-q", "-c", name, "main")
    _git(repo, "commit", "-q", "--allow-empty", "-m", name, date=date)
    _git(repo, "switch", "-q", "main")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "commit", "-q", "--allow-empty", "-m", "base", date=OLD)
    _git(r, "update-ref", "refs/remotes/origin/main", "HEAD")
    _branch(r, "simon", OLD)            # a lane branch, old
    _branch(r, "stale", OLD)            # no reason
    _branch(r, "fresh", RECENT)         # recent commit
    _branch(r, "with-pr", OLD)          # old, but an open PR
    _branch(r, "has-work", OLD)         # old, but a dirty worktree
    _git(r, "worktree", "add", "-q", str(tmp_path / "wt-work"), "has-work")
    (tmp_path / "wt-work" / "scratch.txt").write_text("unsaved")
    _git(r, "worktree", "add", "-q", str(tmp_path / "wt-stale"), "stale")
    _git(r, "tag", "-a", "release-20261122-2", "main", "-m", "r", date=RECENT)
    _git(r, "worktree", "add", "-q", "--detach", str(tmp_path / "wt-rel"), "release-20261122-2")
    _git(r, "update-ref", "refs/remotes/origin/old-feature", "main")
    _git(r, "update-ref", "refs/remotes/origin/with-pr", "with-pr")
    return r


def _by(items, key, value):
    return next(i for i in items if i[key] == value)


def test_reasons_for_local_branches(repo):
    inv = bi.measure(repo, prs={"with-pr": 98}, now=NOW)
    b = inv["branches"]
    assert _by(b, "name", "simon")["reasons"] == ["lane"]
    assert "open PR #98" in _by(b, "name", "with-pr")["reasons"]
    assert _by(b, "name", "fresh")["reasons"] == ["commit within 14 days"]
    assert any(r.startswith("uncommitted work in") for r in _by(b, "name", "has-work")["reasons"])
    assert _by(b, "name", "stale")["status"] == "none"
    assert "checked out in the main folder" in _by(b, "name", "main")["reasons"]


def test_worktrees(repo, tmp_path):
    w = bi.measure(repo, prs={}, now=NOW)["worktrees"]
    work = _by(w, "path", str(tmp_path / "wt-work"))
    assert work["status"] == "keep" and work["dirty"] == 1
    assert _by(w, "path", str(tmp_path / "wt-stale"))["status"] == "none"
    rel = _by(w, "path", str(tmp_path / "wt-rel"))
    assert rel["status"] == "keep" and "newest release tree (release-20261122-2)" in rel["reasons"]
    assert w[0]["reasons"][0] == "main folder"


def test_unread_prs_make_reasonless_items_unmeasured_not_none(repo, tmp_path):
    inv = bi.measure(repo, prs=None, prs_error="gh: not logged in", now=NOW)
    assert _by(inv["branches"], "name", "stale")["status"] == "UNMEASURED"
    assert _by(inv["worktrees"], "path", str(tmp_path / "wt-stale"))["status"] == "UNMEASURED"
    assert _by(inv["remote_branches"], "name", "old-feature")["status"] == "UNMEASURED"
    assert all(i["status"] != "none" for k in ("branches", "worktrees", "remote_branches")
               for i in inv[k])
    assert "UNMEASURED — gh: not logged in" in bi.render(inv)


def test_remote_branches_follow_team_md(repo):
    r = bi.measure(repo, prs={"with-pr": 98}, now=NOW)["remote_branches"]
    assert _by(r, "name", "main")["reasons"] == ["lane"]
    assert _by(r, "name", "with-pr")["reasons"] == ["open PR #98"]
    assert _by(r, "name", "old-feature")["status"] == "none"


def test_unreadable_worktree_is_unmeasured_and_does_not_crash(repo, tmp_path):
    """2026-11-22: ~/prod/QUANTT's .git pointed at a repository path that no longer existed."""
    (tmp_path / "wt-stale" / ".git").write_text("gitdir: /nonexistent/.git/worktrees/x\n")
    w = bi.measure(repo, prs={}, now=NOW)["worktrees"]
    broken = _by(w, "path", str(tmp_path / "wt-stale"))
    assert broken["status"] == "UNMEASURED"
    assert broken["reasons"][0].startswith("git cannot read it")


def test_measure_is_read_only(repo):
    before = _git(repo, "for-each-ref"), _git(repo, "worktree", "list")
    bi.measure(repo, prs={}, now=NOW)
    assert (_git(repo, "for-each-ref"), _git(repo, "worktree", "list")) == before


def test_lane_list_matches_team_md():
    team = (Path(bi.REPO) / "docs" / "TEAM.md").read_text()
    section = team[team.index("## 3."):team.index("## 4.")]
    for name in bi.LANE_BRANCHES:
        assert f"`{name}`" in section, f"{name} is not a branch named in docs/TEAM.md §3"
