"""Load a live-path file as it stood at BASE, for byte-for-byte no-op proofs.

WHY. C4 step 3 (results/cef/C4_DEPLOY_PLAN_2026-10-27.md §1 row 3) edits three
files on the core's live data path: scripts/cef/fetch_daily.py,
scripts/fetch_cef_distributions.py and quantt/collect/collect.py. The rule is
that with C4's options absent the core is unchanged, and the proof is the old
file and the new one run on the same fixtures, in the same process (so the same
pandas and pyarrow write the bytes), with every output compared. The old file
is read from git, not copied into the repo: a copy could drift from what was
released, git's object cannot. results/events/exdrift/noop_fetch_cef_distributions.py
did the same for that script's 2026-10-27 edit.

BASE was origin/main when step 3 was cut (29e5dc0, PR #19). When a reviewed change
to the core path lands after it, the proofs that use this are re-based on that
commit, deliberately, in the same commit as the change: they pin "unchanged since
BASE", and a core change is exactly what they exist to catch.

RE-BASED 2026-10-29 to cee16ad (release-20261029-3, prod's code), in the merge
that integrated step 3 with main (branch c4-integrate). Main had changed
collect.py after 29e5dc0 (the collector's SECOND SOURCE UNAVAILABLE status,
reviewed and released in cee16ad), so the collector's proof against 29e5dc0 no
longer pinned the released file. fetch_daily.py and fetch_cef_distributions.py
are byte-identical at 29e5dc0 and cee16ad (`git diff 29e5dc0 cee16ad` on them is
empty), so their proofs make the same claim as before; and cee16ad's three files
equal origin/main's (35b429f) too. If git cannot produce the
file (no history, a shallow clone), the test FAILS saying so; it is never
skipped, because a skipped no-op proof reads as a passed one.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BASE = "cee16ad"


def load_at_base(rel: str, name: str, tmp_path: Path, monkeypatch):
    """The module `rel` at BASE, imported under `name` from tmp_path/base/<rel>.

    The file sits at its own relative path under tmp_path/base, so its
    `Path(__file__).parents[...]` REPO resolves there, harmlessly; every
    import it makes resolves to this repo's modules, which the step does not
    touch. sys.path and sys.modules are restored by monkeypatch after the test
    (each of these files puts its REPO on sys.path)."""
    p = subprocess.run(["git", "-C", str(REPO), "show", f"{BASE}:{rel}"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"cannot read {rel} at {BASE} from git ({p.stderr.strip()}); the "
                             f"no-op proof needs the base commit in this clone's history")
    path = tmp_path / "base" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(p.stdout)
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, mod)      # `dataclass` looks the module up there
    spec.loader.exec_module(mod)
    return mod
