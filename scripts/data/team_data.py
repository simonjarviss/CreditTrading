"""Copy the team's `data/` folder to and from the private R2 bucket, under `team-data/`.

WHY THIS EXISTS
---------------
On 2026-10-26 the team lead asked for the analysts to have the desk's own `data/`
(about 3.8 GB) instead of each rebuilding it. It cannot go on GitHub: the
repository is public, most of `data/` is built from WRDS (CRSP, TRACE), whose
licence forbids publishing row-level data (`docs/TEAM.md` §5), and one folder alone
is over 3 GB. The analysts already hold read-only tokens for the private R2 bucket
(team lead, 2026-10-22, `docs/SYSTEM.md` §5), so the copy goes there, beside the
WRDS mirror, and they pull it with the token they have.

    python3 scripts/data/team_data.py status          # what the team copy holds, and when it was pushed
    python3 scripts/data/team_data.py pull            # analysts: download into your own data/
    python3 scripts/data/team_data.py push            # team lead: show what would upload
    python3 scripts/data/team_data.py push --go       # team lead: upload it

WHAT IT GUARANTEES
------------------
  * **A manifest is the contract.** `push` uploads every changed file, then
    `team-data/MANIFEST.json` LAST: each file's path, size and sha256, and when it
    was pushed. `pull` downloads only what the manifest lists and checks every
    file's sha256 before it moves it into place, so a push that died halfway, or a
    file someone replaced by hand, raises instead of landing silently.
  * **`pull` never overwrites a file of yours that differs** unless you pass
    `--overwrite`. It checks every conflict first and names them all, before it
    downloads anything. Never run it in a prod clone: the live book decides on
    `data/cef/` (`CLAUDE.md`, landmine 9).
  * **`pull` writes only under `data/`.** A manifest path that is absolute or climbs
    out with `..` raises.
  * **Backups are not shared**: any file with `.bak` in its name, and dotfiles.
  * **Credentials** come from the env file through `src.data.r2.load_config` (the
    same four `R2_*` variables, read with `dotenv_values`, never printed). `push`
    needs a key with write access; a read-only key fails at the first upload with
    AccessDenied, which is the expected answer for an analyst's token.

Remote files that are no longer in the manifest are left in the bucket and ignored
by `pull`; nothing here deletes from R2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
PREFIX = "team-data/"
MANIFEST_KEY = PREFIX + "MANIFEST.json"


class TeamDataError(RuntimeError):
    """A push or pull that cannot be done safely. The message says what and why."""


def _shared(rel: PurePosixPath) -> bool:
    """Backups and dotfiles stay on the machine that made them."""
    return not any(part.startswith(".") or ".bak" in part for part in rel.parts)


def local_files(root: Path) -> list[PurePosixPath]:
    """Every shared file under `root`, as sorted POSIX paths relative to it."""
    if not root.is_dir():
        raise TeamDataError(f"{root} does not exist")
    rels = (PurePosixPath(p.relative_to(root).as_posix()) for p in root.rglob("*") if p.is_file())
    return sorted(r for r in rels if _shared(r))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_rel(raw: str) -> PurePosixPath:
    """A manifest path, refused if it could write outside data/."""
    rel = PurePosixPath(raw)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise TeamDataError(f"manifest path {raw!r} would write outside data/; refusing the pull")
    return rel


def read_manifest(client, bucket: str) -> dict | None:
    """The team copy's manifest, or None when nothing has been pushed yet."""
    try:
        obj = client.get_object(Bucket=bucket, Key=MANIFEST_KEY)
    except client.exceptions.NoSuchKey:
        return None
    return json.loads(obj["Body"].read())


def plan_push(root: Path, remote: dict | None) -> tuple[dict, list[dict]]:
    """The new manifest, and the entries whose bytes differ from the team copy."""
    have = {e["path"]: e["sha256"] for e in (remote or {}).get("files", [])}
    entries = []
    for rel in local_files(root):
        p = root / rel
        entries.append({"path": str(rel), "bytes": p.stat().st_size, "sha256": sha256(p)})
    changed = [e for e in entries if have.get(e["path"]) != e["sha256"]]
    manifest = {"pushed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "files": entries}
    return manifest, changed


def push(client, bucket: str, root: Path, go: bool) -> dict:
    """Upload the changed files, then the manifest. Without `go`, only report."""
    manifest, changed = plan_push(root, read_manifest(client, bucket))
    total = sum(e["bytes"] for e in manifest["files"])
    moving = sum(e["bytes"] for e in changed)
    print(f"{len(manifest['files'])} files ({total / 1e9:.2f} GB) in {root}; "
          f"{len(changed)} changed ({moving / 1e9:.2f} GB) to upload to {PREFIX}")
    if not go:
        print("nothing sent: run again with --go to upload")
        return manifest
    for i, e in enumerate(changed, 1):
        print(f"[{i}/{len(changed)}] {e['path']}")
        client.upload_file(str(root / e["path"]), bucket, PREFIX + e["path"])
    # Last, so a push that dies halfway leaves the previous manifest, whose
    # checksums no longer match, and pull raises rather than mixing two versions.
    client.put_object(Bucket=bucket, Key=MANIFEST_KEY,
                      Body=json.dumps(manifest, indent=1).encode(),
                      ContentType="application/json")
    print(f"pushed; manifest written at {manifest['pushed_at']}")
    return manifest


def pull(client, bucket: str, root: Path, overwrite: bool) -> int:
    """Download the team copy into `root`. Returns how many files were written."""
    manifest = read_manifest(client, bucket)
    if manifest is None:
        raise TeamDataError(f"no {MANIFEST_KEY} in the bucket: nothing has been pushed yet")
    todo, conflicts = [], []
    for e in manifest["files"]:
        dest = root / _safe_rel(e["path"])
        if dest.exists():
            if sha256(dest) == e["sha256"]:
                continue                         # already identical
            if not overwrite:
                conflicts.append(e["path"])
                continue
        todo.append((e, dest))
    if conflicts:
        raise TeamDataError(
            f"{len(conflicts)} file(s) in {root} differ from the team copy and would be "
            f"overwritten: {', '.join(conflicts[:10])}{' ...' if len(conflicts) > 10 else ''}. "
            "Move them aside, or pass --overwrite. Nothing was downloaded.")
    print(f"team copy pushed {manifest['pushed_at']}: {len(todo)} file(s) to download")
    for i, (e, dest) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {e['path']}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        client.download_file(bucket, PREFIX + e["path"], str(tmp))
        got = sha256(tmp)
        if got != e["sha256"]:
            tmp.unlink()
            raise TeamDataError(
                f"{e['path']}: checksum does not match the manifest. The team copy is "
                "mid-push or was changed by hand; ask the team lead to push again.")
        tmp.replace(dest)
    return len(todo)


def status(client, bucket: str) -> None:
    m = read_manifest(client, bucket)
    if m is None:
        print(f"no {MANIFEST_KEY}: nothing has been pushed yet")
        return
    total = sum(e["bytes"] for e in m["files"])
    print(f"team copy pushed {m['pushed_at']}: {len(m['files'])} files, {total / 1e9:.2f} GB")


def make_client():
    """An S3 client for the bucket in the env file. Imported here: no socket at import.

    From boto3 1.36 (pinned at 1.36.3 in requirements-research.txt) the client sends
    integrity-checksum headers on every request by default, which R2 has rejected;
    "when_required" sends them only where the S3 API requires one.
    """
    import boto3
    from botocore.config import Config
    from src.data.r2 import load_config
    cfg = load_config()
    client = boto3.client("s3", endpoint_url=f"https://{cfg.endpoint_host}",
                          aws_access_key_id=cfg.access_key_id,
                          aws_secret_access_key=cfg.secret_access_key,
                          region_name="auto",
                          config=Config(request_checksum_calculation="when_required",
                                        response_checksum_validation="when_required"))
    return client, cfg.bucket


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=Path, default=DATA,
                    help="the data/ folder to push from or pull into (absolute; default: this "
                         "checkout's data/). Lets the team lead push the main checkout's data/ "
                         "from a worktree")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="what the team copy holds, and when it was pushed")
    p = sub.add_parser("pull", help="download the team copy into data/")
    p.add_argument("--overwrite", action="store_true",
                   help="replace your files that differ from the team copy")
    q = sub.add_parser("push", help="team lead: upload data/ (shows the plan without --go)")
    q.add_argument("--go", action="store_true", help="actually upload")
    args = ap.parse_args(argv)
    if not args.data.is_absolute():
        ap.error("--data must be an absolute path")
    sys.path.insert(0, str(REPO))
    client, bucket = make_client()
    if args.cmd == "status":
        status(client, bucket)
    elif args.cmd == "pull":
        pull(client, bucket, args.data, args.overwrite)
    else:
        push(client, bucket, args.data, args.go)
    return 0


if __name__ == "__main__":
    sys.exit(main())
