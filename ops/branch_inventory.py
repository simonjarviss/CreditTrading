"""Every branch and worktree, with its reason to exist or "none": the measurer for `docs/STANDARD.md` A1.2.

WHY THIS EXISTS
---------------
On 2026-11-22 the team lead's laptop held 199 local branches, 102 remote branches
and 143 worktrees. Some held uncommitted work, some were trees a release wrapper
replays from, most were finished. Nobody could say which was which without
opening each one, so nothing was ever cleaned up, and a session opened in the
main folder loaded rules 841 commits old (A1.1).

The team lead's rule (2026-11-22, `docs/SYSTEM.md` §5): a branch or worktree
stays if it has a reason (an open pull request, a lane branch, or a commit in the
last 14 days); anything else is tagged `archive/<branch>` and then deleted. This
script measures that rule. **It is read-only**: it never tags, deletes, prunes or
fetches. The deleting is a separate, confirmed step.

REASONS
-------
Local branch: `lane` (`docs/TEAM.md` §3), `open PR #n`, `commit within 14 days`,
`uncommitted work in <worktree>` (deleting would lose it), `checked out in the
main folder`.
Worktree: `main folder`, `uncommitted work (n)`, `branch kept`, `newest release
tree` (a release wrapper replays from it), `directory missing` (prunable, no
work to lose). A worktree on a branch with no reason and nothing uncommitted has
none.
Remote branch: `lane` or `open PR #n` only. `docs/TEAM.md` §3: "GitHub holds five
branches and no others", plus a pull request's own branch while it is open.

NO SILENT FALLBACKS
-------------------
Open pull requests are read with `gh`. If that fails, a branch that has no other
reason is reported UNMEASURED, never "none": an unread pull request is not an
absent one.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: `docs/TEAM.md` §3 (team lead, 2026-10-22; renamed 2026-10-26). A test checks each
#: name still appears there, so this list cannot drift from the document silently.
LANE_BRANCHES = ("main", "simon", "ryan", "james", "lucy")

#: `docs/STANDARD.md` A1.2 (team lead, 2026-11-22): a policy choice, not a measurement.
RECENT_DAYS = 14


def _git(repo: Path, *args: str, timeout: int = 60) -> str:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])} failed in {repo}: {r.stderr.strip()[:200]}")
    return r.stdout


def open_prs(repo: Path) -> dict[str, int]:
    """{head branch: PR number} for open pull requests. Raises if gh cannot answer."""
    r = subprocess.run(["gh", "pr", "list", "--state", "open", "--limit", "500",
                        "--json", "number,headRefName"],
                       cwd=repo, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"gh pr list failed: {r.stderr.strip()[:200]}")
    return {p["headRefName"]: int(p["number"]) for p in json.loads(r.stdout)}


def _worktrees(repo: Path) -> list[dict]:
    """`git worktree list --porcelain`, one dict per tree; the first is the main folder."""
    out, cur = [], {}
    for line in _git(repo, "worktree", "list", "--porcelain").splitlines() + [""]:
        if not line:
            if cur:
                out.append(cur)
            cur = {}
            continue
        key, _, val = line.partition(" ")
        if key == "worktree":
            cur["path"] = val
        elif key == "HEAD":
            cur["head"] = val
        elif key == "branch":
            cur["branch"] = val.removeprefix("refs/heads/")
        elif key in ("detached", "prunable", "locked"):
            cur[key] = val or True
    return out


def _dirty(path: str) -> int | None:
    """Uncommitted paths in a worktree, or None when its directory is gone."""
    if not Path(path).is_dir():
        return None
    return len([l for l in _git(Path(path), "status", "--porcelain").splitlines() if l.strip()])


def measure(repo: Path = REPO, prs: dict[str, int] | None = None,
            prs_error: str | None = None, now: dt.datetime | None = None) -> dict:
    """The inventory. `prs` is open_prs(repo) or None with `prs_error` saying why."""
    now = now or dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=RECENT_DAYS)
    trees = _worktrees(repo)
    main_path = trees[0]["path"] if trees else None
    release_tags = _git(repo, "tag", "-l", "release-*", "--sort=-creatordate").split()
    newest_release = (_git(repo, "rev-list", "-n", "1", release_tags[0]).strip(), release_tags[0]) \
        if release_tags else None
    try:
        merged = {l.strip().lstrip("*+ ").strip() for l in
                  _git(repo, "branch", "--merged", "origin/main").splitlines()}
    except RuntimeError:
        merged = None

    for t in trees:
        # A registered worktree git cannot read (on 2026-11-22: the retired IBKR
        # tree, whose .git points at a repository path that no longer exists) has
        # an unknown amount of uncommitted work: UNMEASURED, never "none".
        try:
            t["dirty"] = _dirty(t["path"])
        except RuntimeError as e:
            t["dirty"], t["dirty_error"] = None, str(e)

    by_branch: dict[str, list[dict]] = {}
    for t in trees:
        if "branch" in t:
            by_branch.setdefault(t["branch"], []).append(t)

    branches = []
    fmt = "%(refname:short)%09%(committerdate:iso-strict)%09%(upstream:short)"
    for line in _git(repo, "for-each-ref", "refs/heads", f"--format={fmt}").splitlines():
        name, date, upstream = (line.split("\t") + ["", ""])[:3]
        when = dt.datetime.fromisoformat(date)
        reasons = []
        if name in LANE_BRANCHES:
            reasons.append("lane")
        if prs is not None and name in prs:
            reasons.append(f"open PR #{prs[name]}")
        if when >= cutoff:
            reasons.append(f"commit within {RECENT_DAYS} days")
        for t in by_branch.get(name, []):
            if t["path"] == main_path:
                reasons.append("checked out in the main folder")
            if t["dirty"]:
                reasons.append(f"uncommitted work in {t['path']}")
        status = "keep" if reasons else ("UNMEASURED" if prs is None else "none")
        branches.append({"name": name, "last_commit": when.date().isoformat(), "upstream": upstream or None,
                         "merged_into_main": None if merged is None else name in merged,
                         "worktrees": [t["path"] for t in by_branch.get(name, [])],
                         "reasons": reasons, "status": status})
    kept = {b["name"] for b in branches if b["status"] == "keep"}

    worktrees = []
    for t in trees:
        reasons = []
        if t["path"] == main_path:
            reasons.append("main folder")
        if "dirty_error" in t:
            reasons.append(f"git cannot read it ({t['dirty_error'][-120:]})")
        elif t["dirty"] is None:
            reasons.append("directory missing")
        elif t["dirty"]:
            reasons.append(f"uncommitted work ({t['dirty']})")
        if t.get("branch") in kept:
            reasons.append("branch kept")
        if newest_release and "detached" in t and t["head"] == newest_release[0]:
            reasons.append(f"newest release tree ({newest_release[1]})")
        unknown = prs is None and t.get("branch") and t["branch"] not in kept
        if "dirty_error" in t:
            status = "UNMEASURED"
        else:
            status = "keep" if [r for r in reasons if r != "directory missing"] else (
                "prunable" if t["dirty"] is None else ("UNMEASURED" if unknown else "none"))
        worktrees.append({"path": t["path"], "branch": t.get("branch"),
                          "head": t["head"][:7], "dirty": t["dirty"], "reasons": reasons, "status": status})

    remotes = []
    for line in _git(repo, "for-each-ref", "refs/remotes/origin",
                     "--format=%(refname:short)%09%(committerdate:short)").splitlines():
        ref, date = line.split("\t")
        name = ref.removeprefix("origin/")
        if name == "HEAD" or ref == "origin":
            continue
        reasons = (["lane"] if name in LANE_BRANCHES else []) + (
            [f"open PR #{prs[name]}"] if prs is not None and name in prs else [])
        remotes.append({"name": name, "last_commit": date, "reasons": reasons,
                        "status": "keep" if reasons else ("UNMEASURED" if prs is None else "none")})

    return {"measured_at": now.isoformat(timespec="seconds"), "repo": str(repo),
            "recent_days": RECENT_DAYS, "open_prs": prs, "open_prs_error": prs_error,
            "newest_release": newest_release[1] if newest_release else None,
            "branches": branches, "worktrees": worktrees, "remote_branches": remotes}


def _counts(items: list[dict]) -> str:
    c: dict[str, int] = {}
    for i in items:
        c[i["status"]] = c.get(i["status"], 0) + 1
    return ", ".join(f"{n} {k}" for k, n in sorted(c.items()))


def render(inv: dict) -> str:
    out = [f"BRANCH INVENTORY  {inv['repo']}  measured {inv['measured_at']}",
           f"rule: keep if lane, open PR or a commit within {inv['recent_days']} days "
           "(docs/STANDARD.md A1.2); uncommitted work is always kept",
           "open PRs: " + ("UNMEASURED — " + str(inv["open_prs_error"]) if inv["open_prs"] is None
                           else ", ".join(f"#{n} {b}" for b, n in sorted(inv["open_prs"].items(),
                                                                          key=lambda x: x[1])) or "none"),
           "",
           f"local branches   {len(inv['branches'])}: {_counts(inv['branches'])}",
           f"worktrees        {len(inv['worktrees'])}: {_counts(inv['worktrees'])}",
           f"remote branches  {len(inv['remote_branches'])}: {_counts(inv['remote_branches'])}", ""]
    for title, key, cols in (("LOCAL BRANCHES", "branches", ("name", "last_commit", "merged_into_main")),
                             ("WORKTREES", "worktrees", ("path", "branch", "dirty")),
                             ("REMOTE BRANCHES", "remote_branches", ("name", "last_commit"))):
        out.append(title)
        for i in sorted(inv[key], key=lambda x: (x["status"], str(x[cols[0]]))):
            out.append(f"  {i['status']:<10} " + "  ".join(str(i[c]) for c in cols)
                       + (f"  — {'; '.join(i['reasons'])}" if i["reasons"] else ""))
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the inventory as JSON")
    ap.add_argument("--repo", type=Path, default=REPO)
    a = ap.parse_args(argv)
    try:
        prs, err = open_prs(a.repo), None
    except (RuntimeError, OSError, subprocess.TimeoutExpired, ValueError) as e:
        prs, err = None, f"{type(e).__name__}: {e}"
    inv = measure(a.repo, prs, err)
    print(json.dumps(inv, indent=2) if a.json else render(inv))
    return 0


if __name__ == "__main__":
    sys.exit(main())
