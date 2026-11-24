"""The VM installer's second book: C4 beside the core, the core byte for byte as it was.

THE CORE (no `--book`, or `--book cef`). The installer of cee16ad
(release-20261029-3, prod; its quantt/deploy is 35b429f's, origin/main when
c4-integrate was cut) is read from git (scripts/cef/tests/noop_base.py) and run
beside this one in the same fake VM: the dry run's whole printed output (every
check, step and rendered unit) is identical, and after `--apply` every unit file
is identical, byte for byte. A default run writes no C4 unit.

C4 (`--book c4`). Its own seven units (quantt-c4-*), rendered from templates at
the tag and checked key by key: its own state dir (quantt_state/c4), key file
(/run/quantt-c4/alpaca.env) and vault secret names (alpaca-c4-*), the core's
commands with `--book c4`, DRY_RUN=1 unless armed, and QUANTT_EOD_FROM from the
REQUIRED `--eod-from` (refused without it, and refused for the core). Its
panels are seeded only from a seed whose manifest names the tag's IGR ruling.
It never checks the shared clone out, and the core's install will not move the
clone while a C4 timer is live. The two books share no lock. Every C4 test fails
on 35b429f, whose installer has no `--book`.

Hermetic: test_install_vm's fake VM (local git, tmp dirs, a recording systemd).
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from quantt.deploy import install_vm as iv
from quantt.deploy.tests.test_install_vm import (CLOCK, NOW, REAL_REPO, FakeSystemd, World,
                                                  git, values)
from quantt.deploy.tests.test_install_vm import world  # noqa: F401  (the fixture)

EOD = "2026-09-29"


def _unit_bytes(world, names) -> dict:
    return {n: world.layout.unit_path(n).read_bytes() for n in names}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class C4Systemd(FakeSystemd):
    """test_install_vm's fake systemd, plus C4's key service: a restart writes
    /run/quantt-c4/alpaca.env (mode 0600) and leaves the service active."""

    def __init__(self, units_dir):
        super().__init__(units_dir)
        self.c4_secret_started = False

    def __call__(self, args):
        if list(args[:3]) == ["systemctl", "restart", iv.C4_SECRET_UNIT]:
            self.calls.append(list(args))
            f = self.sysroot / "run" / "quantt-c4" / "alpaca.env"
            f.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(f.parent, 0o700)
            f.write_text("ALPACA_C4_KEY_ID=x\nALPACA_C4_SECRET_KEY=y\n")
            os.chmod(f, 0o600)
            self.c4_secret_started = True
            return subprocess.CompletedProcess(args, 0, "", "")
        return super().__call__(args)

    def _show(self, unit, props):
        out = super()._show(unit, props)
        if unit == iv.C4_SECRET_UNIT and self.c4_secret_started:
            out = out.replace("ActiveState=inactive", "ActiveState=active")
        return out


class C4World(World):
    """A fake VM whose release carries C4's files too (templates real, the rest
    stubs), and a C4 seed directory whose manifest names the tag's ruling."""

    def __init__(self, tmp):
        super().__init__(tmp)
        self.cmds = C4Systemd(self.layout.units_dir)
        self.c4_seed = tmp / "c4_seed"
        self.write_c4_seed()

    def _make_repo(self):
        d = self.dev
        d.mkdir()
        git("init", "-q", "-b", "main", cwd=d)
        (d / ".gitignore").write_text("/data/\n")
        for rel in iv.C4_VM.required_at_tag:
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            if rel.startswith(iv.TEMPLATE_DIR):
                (d / rel).write_text((REAL_REPO / rel).read_text())
            else:
                (d / rel).write_text(f"# stub {rel}\n")
        git("add", "-A", cwd=d)
        git("commit", "-q", "-m", "v1", cwd=d)
        git("tag", "-a", "v1", "-m", "release v1", cwd=d)
        subprocess.run(["git", "clone", "-q", "--bare", str(d), str(self.origin)],
                       check=True, capture_output=True)
        git("remote", "add", "origin", str(self.origin), cwd=d)

    def write_c4_seed(self, *, ruling=True, tamper=None):
        s = self.c4_seed
        s.mkdir(exist_ok=True)
        files = {}
        for name in iv.C4_VM.seed_files:
            (s / name).write_bytes(f"seed-c4 bytes of {name}".encode())
            files[name] = {"sha256": _sha((s / name).read_bytes()), "rows": 1}
        man = {"files": files,
               "bar_rulings": ({"path": iv.C4_SEED_RULINGS,
                                "sha256": _sha((self.dev / iv.C4_SEED_RULINGS).read_bytes())}
                               if ruling else None),
               "universe": {"path": iv.C4_UNIVERSE,
                            "sha256": _sha((self.dev / iv.C4_UNIVERSE).read_bytes())}}
        (s / "seed_manifest.json").write_text(json.dumps(man))
        if tamper:
            (s / tamper).write_bytes(b"not what the manifest says")

    def c4(self, *extra, eod=EOD, seed=True, capsys=None, **kw):
        argv = ["--book", "c4", *(["--eod-from", eod] if eod else []), *extra]
        if seed:
            argv += ["--seed-from", str(self.c4_seed)]
        return self.run(*argv, seed=False, capsys=capsys, **kw)

    def unit_bytes(self, names):
        return _unit_bytes(self, names)


@pytest.fixture
def c4world(tmp_path):
    return C4World(tmp_path)


def _base_installer(tmp_path, monkeypatch):
    from scripts.cef.tests.noop_base import BASE, load_at_base
    assert BASE == "cee16ad"
    return load_at_base("quantt/deploy/install_vm.py", "install_vm_cee16ad", tmp_path, monkeypatch)


def _run_with(mod, world, argv, capsys):
    rc = mod.main(argv, layout=world.layout, origin_url=str(world.origin),
                  localtime=world.localtime, run_cmd=world.cmds, as_user=[], euid=0,
                  dont_write_bytecode=True, user_ids=lambda u: (os.getuid(), os.getgid()),
                  now_utc=NOW, read_environ=world.cmds.read_environ, clock=lambda: CLOCK)
    return rc, capsys.readouterr().out


# ------------------------------------------------------------------ the core, byte for byte

def test_the_cores_install_is_byte_identical_to_the_prod_releases_installer(
        world, capsys, tmp_path, monkeypatch):
    base = _base_installer(tmp_path / "base", monkeypatch)
    argv = ["--tag", "v1", "--vault", "example-vault-x1", "--seed-from", str(world.seed)]
    rc_b, out_b = _run_with(base, world, argv, capsys)
    rc_n, out_n = _run_with(iv, world, argv, capsys)
    rc_c, out_c = _run_with(iv, world, argv + ["--book", "cef"], capsys)
    assert rc_b == rc_n == rc_c == 0
    assert out_n == out_b and out_c == out_b                     # every check, step and unit
    assert out_b.count("(rendered, not written)") == len(iv.ALL_UNIT_FILES) == 7
    # --apply: the files written are the base's, byte for byte.
    assert _run_with(base, world, argv + ["--apply"], capsys)[0] == 0
    written = _unit_bytes(world, iv.ALL_UNIT_FILES)
    assert _run_with(iv, world, argv + ["--apply"], capsys)[0] == 0
    assert _unit_bytes(world, iv.ALL_UNIT_FILES) == written
    assert sorted(p.name for p in world.layout.units_dir.iterdir()) == sorted(iv.ALL_UNIT_FILES)
    # The core's constants are the ones they were.
    assert (base.SECRET_UNIT, base.ENV_FILE, base.SECRET_MAP, base.REQUIRED_AT_TAG) == \
        (iv.SECRET_UNIT, iv.ENV_FILE, iv.SECRET_MAP, iv.REQUIRED_AT_TAG)
    assert [(j.unit, j.job, j.success_exit) for j in base.VM_JOBS] == \
        [(j.unit, j.job, j.success_exit) for j in iv.VM_JOBS]


def test_by_default_only_the_core_is_installed(c4world, capsys):
    assert c4world.run("--apply", capsys=capsys)[0] == 0
    names = sorted(p.name for p in c4world.layout.units_dir.iterdir())
    assert names == sorted(iv.ALL_UNIT_FILES) and not [n for n in names if "c4" in n]
    assert not (c4world.layout.state_root / "c4").exists()


# ------------------------------------------------------------------ C4

def test_book_c4_refuses_without_eod_from_and_writes_nothing(c4world, capsys):
    rc, out = c4world.c4("--apply", eod=None, capsys=capsys)
    assert rc == 2 and "REFUSED" in out and "--eod-from" in out and "no default" in out
    assert not c4world.layout.units_dir.exists() or not list(c4world.layout.units_dir.iterdir())
    assert not (c4world.layout.state_root / "c4").exists()
    for bad in ("2026-9-29", "29/09/2026", "2099-01-02"):
        rc, out = c4world.c4(eod=bad, capsys=capsys)
        assert rc == 2 and "--eod-from" in out, bad


def test_the_core_refuses_eod_from(c4world, capsys):
    rc, out = c4world.run("--eod-from", EOD, capsys=capsys)
    assert rc == 2 and "records its own" in out


def test_book_c4_installs_its_own_units_dry_and_leaves_the_cores_untouched(c4world, capsys):
    assert c4world.run("--apply", capsys=capsys)[0] == 0
    core = c4world.unit_bytes(iv.ALL_UNIT_FILES)
    rc, out = c4world.c4("--apply", capsys=capsys)
    assert rc == 0, out
    assert c4world.unit_bytes(iv.ALL_UNIT_FILES) == core           # the core's, byte for byte
    c4_units = iv.C4_VM.unit_files
    assert len(c4_units) == 7 and all(u.startswith("quantt-c4-") for u in c4_units)
    assert sorted(p.name for p in c4world.layout.units_dir.iterdir()) == \
        sorted(iv.ALL_UNIT_FILES + c4_units)
    state = c4world.layout.state_root / "c4"
    run_env = "/run/quantt-c4/alpaca.env"
    for vj in iv.C4_VM_JOBS:
        u = c4world.unit(vj.service)
        env = values(u, "Service", "Environment")
        assert env[:5] == ["DRY_RUN=1", f"QUANTT_STATE_DIR={state}", f"QUANTT_ENV_FILE={run_env}",
                           env[3], "PYTHONUNBUFFERED=1"]
        assert values(u, "Unit", "Wants") == [iv.C4_SECRET_UNIT]
        assert values(u, "Unit", "Requires") == []
        assert values(u, "Service", "StandardOutput") == [f"append:{state}/logs/"
                                                          f"{vj.job.log_stem}.out.log"]
        (cmd,) = values(u, "Service", "ExecStart")
        assert "--book c4" in cmd and "--book cef" not in cmd
        twin = next(j for j in iv.VM_JOBS if j.job.log_stem == vj.job.log_stem)
        assert vj.job.schedule == twin.job.schedule
        assert values(c4world.unit(vj.timer), "Timer", "OnCalendar") == \
            values(c4world.unit(twin.timer), "Timer", "OnCalendar")
    collect = c4world.unit("quantt-c4-collect.service")
    assert values(collect, "Service", "Environment")[-1] == f"QUANTT_EOD_FROM={EOD}"
    assert all("QUANTT_EOD_FROM" not in e for vj in iv.VM_JOBS
               for e in values(c4world.unit(vj.service), "Service", "Environment"))
    sec = c4world.unit(iv.C4_SECRET_UNIT)
    (cmd,) = values(sec, "Service", "ExecStart")
    assert "--secret alpaca-c4-key-id=ALPACA_C4_KEY_ID" in cmd
    assert "--secret alpaca-c4-secret-key=ALPACA_C4_SECRET_KEY" in cmd
    assert cmd.endswith(f"--out {run_env}") and "alpaca-cef" not in cmd
    assert values(sec, "Service", "RuntimeDirectory") == ["quantt-c4"]
    # Seeded from the manifest's files, logged with the ruling's sha; nothing enabled.
    data = c4world.layout.prod_dir / "data" / "cef_c4"
    for name in iv.C4_VM.seed_files:
        assert (data / name).read_bytes() == (c4world.c4_seed / name).read_bytes()
    log = (state / "seed.log").read_text()
    assert log.count("seeded") == 2 and "bar_rulings_sha256=" in log
    assert not [c for c in c4world.cmds.calls if c[:2] == ["systemctl", "enable"]]
    assert "WOULD" not in out and "DRY_RUN=1" in out
    # And with --enable, C4's key service is restarted into its own key file.
    rc, out = c4world.c4("--apply", "--enable", capsys=capsys)
    assert rc == 0, out
    assert c4world.cmds.c4_secret_started
    assert (c4world.tmp / "run" / "quantt-c4" / "alpaca.env").stat().st_mode & 0o777 == 0o600
    assert not [c for c in c4world.cmds.calls if c[:3] == ["systemctl", "restart", iv.SECRET_UNIT]]
    assert c4world.unit_bytes(iv.ALL_UNIT_FILES) == core


@pytest.mark.parametrize("seed_kw, why", [
    ({"ruling": False}, "IGR ruling"),
    ({"tamper": "cef_nav.parquet"}, "not the seed the manifest describes"),
])
def test_book_c4_refuses_a_seed_not_built_as_ruled(c4world, capsys, seed_kw, why):
    c4world.write_c4_seed(**seed_kw)
    rc, out = c4world.c4("--apply", capsys=capsys)
    assert rc == 2 and why in out
    assert not (c4world.layout.prod_dir / "data" / "cef_c4").exists()


def test_book_c4_refuses_without_a_seed_and_a_half_seeded_pair(c4world, capsys):
    rc, out = c4world.c4(seed=False, capsys=capsys)
    assert rc == 2 and "seed-c4" in out
    data = c4world.layout.prod_dir / "data" / "cef_c4"
    data.mkdir(parents=True)
    (data / "cef_prices.parquet").write_bytes(b"prod's own")
    rc, out = c4world.c4(capsys=capsys)
    assert rc == 2 and "half-seeded" in out


def test_book_c4_never_checks_the_shared_clone_out(c4world, capsys):
    c4world.commit_and_tag("v2", lambda d: (d / "NOTES").write_text("v2\n"))
    before = c4world.head()
    rc, out = c4world.c4("--apply", tag="v2", capsys=capsys)
    assert rc == 2 and "never checks the clone out" in out and "Install the core at v2" in out
    assert c4world.head() == before
    assert not c4world.layout.units_dir.exists() or not list(c4world.layout.units_dir.iterdir())


def test_the_core_will_not_move_the_clone_under_live_c4_timers(c4world, capsys):
    assert c4world.run("--apply", capsys=capsys)[0] == 0
    assert c4world.c4("--apply", capsys=capsys)[0] == 0
    c4world.commit_and_tag("v2", lambda d: (d / "NOTES").write_text("v2\n"))
    before = c4world.head()
    c4world.cmds.enabled.add("quantt-c4-session.timer")
    rc, out = c4world.run(tag="v2", capsys=capsys)
    assert rc == 2 and "quantt-c4-session.timer is enabled" in out and "shared" in out
    assert c4world.head() == before
    c4world.cmds.enabled.discard("quantt-c4-session.timer")
    c4world.cmds.active["quantt-c4-collect.service"] = "active"            # a C4 job running
    rc, out = c4world.run(tag="v2", capsys=capsys)
    assert rc == 2 and "quantt-c4-collect.service is active" in out
    c4world.cmds.active.pop("quantt-c4-collect.service")
    rc, out = c4world.run("--apply", tag="v2", capsys=capsys)              # C4 quiet: allowed
    assert rc == 0, out
    assert c4world.head() == c4world.tag_commit("v2")
    # ...and C4 then re-installs at the tag the core moved to.
    assert c4world.c4("--apply", tag="v2", capsys=capsys)[0] == 0


def test_the_two_books_never_share_a_lock(c4world, capsys, tmp_path, monkeypatch):
    """Separate locks per data book (the team lead's brief): C4's units point
    every job at its own state dir (so the collector locks
    quantt_state/c4/data/.collect.lock, never the core's), its refresh is
    fetch_daily --data-book c4 (data/cef_c4/.fetch.lock, never data/cef's), and
    holding one book's panel lock does not delay the other's."""
    assert c4world.run("--apply", capsys=capsys)[0] == 0
    assert c4world.c4("--apply", capsys=capsys)[0] == 0

    def state_of(unit):
        (s,) = [e.split("=", 1)[1] for e in values(c4world.unit(unit), "Service", "Environment")
                if e.startswith("QUANTT_STATE_DIR=")]
        return Path(s)
    core_states = {state_of(vj.service) for vj in iv.VM_JOBS}
    c4_states = {state_of(vj.service) for vj in iv.C4_VM_JOBS}
    assert len(core_states) == len(c4_states) == 1 and core_states != c4_states
    assert next(iter(c4_states)).name == "c4"
    from scripts.cef import data_books
    from scripts.cef import fetch_daily as fd
    # The real data books' locks are different files in different directories.
    assert fd.resolve_data_book("c4").lock_path != fd.resolve_data_book(None).lock_path
    assert fd.resolve_data_book("c4").lock_path.parent != fd.resolve_data_book(None).lock_path.parent
    # Both locks taken at once, with the paths moved under tmp (data/ is never written).
    monkeypatch.setattr(fd, "LOCK_PATH", tmp_path / "cef" / ".fetch.lock")
    monkeypatch.setattr(fd, "PX_PATH", tmp_path / "cef" / "cef_prices.parquet")
    monkeypatch.setattr(fd, "NAV_PATH", tmp_path / "cef" / "cef_nav.parquet")
    monkeypatch.setattr(fd, "FALLBACK_LOG", tmp_path / "cef" / "nav_fallback_log.csv")
    monkeypatch.setattr(data_books, "C4_DIR", tmp_path / "cef_c4")
    for d in ("cef", "cef_c4"):
        (tmp_path / d).mkdir()
    core, c4 = fd.resolve_data_book(None), fd.resolve_data_book("c4")
    with fd.panel_lock(core.lock_path, wait_s=0.0):
        with fd.panel_lock(c4.lock_path, wait_s=0.0):              # not delayed by the core's
            pass
        with pytest.raises(fd.PanelLockTimeout):                     # the core's is held
            with fd.panel_lock(core.lock_path, wait_s=0.0):
                pass
    # The C4 session's refresh names the C4 data book (and so its lock).
    from quantt.session import run as rn
    spec = rn.load_spec(rn.BOOKS["c4"].spec_path)
    assert rn.refresh_flags(rn.spec_panel(spec)) == ("--data-book", "c4")
    assert rn.refresh_flags(rn.core_panel()) == rn.CORE_REFRESH_FLAGS


def test_c4s_jobs_are_the_cores_with_book_c4():
    for core, c4 in zip(iv.VM_JOBS, iv.C4_VM_JOBS):
        assert c4.unit == core.unit.replace("quantt-cef-", "quantt-c4-")
        assert c4.success_exit == core.success_exit and c4.job.schedule == core.job.schedule
        a = list(core.job.args)
        a[a.index("--book") + 1] = "c4"
        assert list(c4.job.args) == a
    assert iv.C4_VM.env_file == Path("/run/quantt-c4/alpaca.env") != iv.ENV_FILE
    assert dict(iv.C4_VM.secret_map) == {"alpaca-c4-key-id": "ALPACA_C4_KEY_ID",
                                         "alpaca-c4-secret-key": "ALPACA_C4_SECRET_KEY"}
    assert set(iv.REQUIRED_AT_TAG) < set(iv.C4_VM.required_at_tag)
    for f in iv.C4_VM.required_at_tag:
        assert (REAL_REPO / f).is_file(), f
    from quantt.broker.alpaca_probe import env_names
    assert tuple(dict(iv.C4_VM.secret_map).values()) == env_names("c4")
    from quantt.collect import collect as co
    assert iv.EOD_FROM_ENV == co.EOD_FROM_ENV


# ------------------------------------- release-check of 336df9d, ET1: a C4 install scans every book

def _dormant(world, rel, body="[Service]\nEnvironment=DRY_RUN=0\n"):
    f = world.tmp / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body)
    return f


@pytest.mark.parametrize("rel", [
    "etc/systemd/system/quantt-cef-session.service.d/override.conf",      # on the core's armed unit
    "run/systemd/system/quantt-cef-.service.d/50-x.conf",                 # the core's prefix
    "etc/systemd/system.control/quantt-secret.service.d/50-x.conf",       # the core's key service
    "run/systemd/transient/quantt-cef-session.timer",                     # a core unit outranking
])
def test_book_c4_refuses_a_dormant_override_on_the_cores_units(c4world, capsys, rel):
    """C4's daemon-reload applies to every unit, so a C4 install refuses, at planning, an
    override waiting on the CORE's units too, naming it. Fails on f27ef81 (C4 scanned only
    its own seven)."""
    assert c4world.run("--apply", capsys=capsys)[0] == 0           # the core, installed first
    f = _dormant(c4world, rel)
    before = c4world.unit_bytes(iv.ALL_UNIT_FILES)
    rc, out = c4world.c4("--apply", capsys=capsys)
    assert rc == 2 and str(f) in out and "REFUSED at step" not in out, out
    assert not any((c4world.layout.units_dir / u).exists() for u in iv.C4_VM.unit_files)
    assert c4world.unit_bytes(iv.ALL_UNIT_FILES) == before


def test_book_c4_refuses_a_quantt_unit_no_book_installs(c4world, capsys):
    """An unexpected `quantt-` unit file (here a stray C4-named service) would be loaded by
    C4's reload too: the C4 install refuses, naming it. Fails on f27ef81."""
    assert c4world.run("--apply", capsys=capsys)[0] == 0
    f = _dormant(c4world, "etc/systemd/system/quantt-c4-extra.service",
                 "[Service]\nExecStart=/bin/true\n")
    rc, out = c4world.c4("--apply", capsys=capsys)
    assert rc == 2 and str(f) in out and "no unit any book installs" in out, out


def test_book_c4_installs_beside_the_shadow_runners_units(c4world, capsys):
    """The shadow runner's three unit files (shadow/deploy/install_shadow_vm.sh) are the
    repository's own and no book's: a C4 install must not refuse on them. On 2026-11-18 it
    did, with C4's timers already disabled for the core's install, and C4 could not trade
    until the files were moved aside by hand (EVIDENCE_LOG E-2026-11-18-01). Fails on
    49b99db ("is no unit any book installs"). A stray unit beside them is still refused."""
    assert c4world.run("--apply", capsys=capsys)[0] == 0
    shadow = [_dormant(c4world, f"etc/systemd/system/{u}", "[Service]\nExecStart=/bin/true\n")
              for u in iv.SHADOW_UNIT_FILES]
    before = [f.read_bytes() for f in shadow]
    rc, out = c4world.c4("--apply", capsys=capsys)
    assert rc == 0 and "no unit any book installs" not in out, out
    assert all((c4world.layout.units_dir / u).exists() for u in iv.C4_VM.unit_files)
    assert [f.read_bytes() for f in shadow] == before          # never written by this installer
    stray = _dormant(c4world, "etc/systemd/system/quantt-shadow-extra.service",
                     "[Service]\nExecStart=/bin/true\n")
    rc, out = c4world.c4("--apply", capsys=capsys)
    assert rc == 2 and str(stray) in out and "no unit any book installs" in out, out


def test_shadow_unit_names_are_the_ones_the_shadow_installer_writes():
    """SHADOW_UNIT_FILES is a copy of names owned by a shell script. Pin it: every unit file
    that script writes under its UNIT_DIR, and nothing else."""
    import re
    from pathlib import Path
    sh = (Path(iv.__file__).resolve().parents[2] / "shadow" / "deploy" / "install_shadow_vm.sh").read_text()
    written = set(re.findall(r'cat > "\$\{UNIT_DIR\}/([^"]+)"', sh))
    assert written and written == set(iv.SHADOW_UNIT_FILES), written


def test_book_c4_installs_beside_the_events_runners_units(c4world, capsys):
    """The event sleeves' seven unit files (quantt/sleeves/deploy/install_events_vm.sh) are
    the repository's own: a C4 install goes through beside them and leaves them byte-identical.
    Without EVENTS_UNIT_FILES it refuses as it did on the shadow runner's on 2026-11-18. A
    stray `quantt-events-*` unit that is not one of the seven is still refused, by name."""
    assert c4world.run("--apply", capsys=capsys)[0] == 0
    ev = [_dormant(c4world, f"etc/systemd/system/{u}", "[Service]\nExecStart=/bin/true\n")
          for u in iv.EVENTS_UNIT_FILES]
    before = [f.read_bytes() for f in ev]
    rc, out = c4world.c4("--apply", capsys=capsys)
    assert rc == 0 and "no unit any book installs" not in out, out
    assert [f.read_bytes() for f in ev] == before
    stray = _dormant(c4world, "etc/systemd/system/quantt-events-extra.service",
                     "[Service]\nExecStart=/bin/true\n")
    rc, out = c4world.c4("--apply", capsys=capsys)
    assert rc == 2 and str(stray) in out and "no unit any book installs" in out, out


def test_events_unit_names_are_the_ones_the_events_installer_writes():
    """EVENTS_UNIT_FILES is a copy of names owned by a shell script. Pin it: the units that
    script names literally (the key service and the three timers), a service for every timer
    (its job template writes `quantt-events-<job>.service`), and nothing else."""
    import re
    from pathlib import Path
    sh = (Path(iv.__file__).resolve().parents[2] / "quantt" / "sleeves" / "deploy" / "install_events_vm.sh").read_text()
    literal = set(re.findall(r"^\s*unit_file (quantt-events-[a-z]+\.(?:service|timer)) <<", sh, flags=re.M))
    assert 'unit_file "quantt-events-$1.service" <<' in sh
    timers = {u for u in literal if u.endswith(".timer")}
    assert len(timers) == 3 and literal - timers == {"quantt-events-secret.service"}, literal
    assert literal | {u[:-len(".timer")] + ".service" for u in timers} == set(iv.EVENTS_UNIT_FILES)


def test_site_unit_names_are_the_ones_the_site_installer_writes():
    """SITE_UNIT_FILES is a copy of names owned by a shell script (the public site's build).
    Pin it: exactly the units that script writes, and every one of them registered."""
    import re
    from pathlib import Path
    sh = (Path(iv.__file__).resolve().parents[2] / "dashboard" / "deploy" / "install_site_vm.sh").read_text()
    written = set(re.findall(r"^\s*unit_file (quantt-[a-z-]+\.(?:service|timer)) <<", sh, flags=re.M))
    assert written == set(iv.SITE_UNIT_FILES), written


def test_a_site_unit_beside_c4_is_known_not_refused(c4world, capsys):
    """The site's units on disk do not make a C4 install refuse (the SHADOW_UNIT_FILES lesson)."""
    for name in iv.SITE_UNIT_FILES:
        _dormant(c4world, f"etc/systemd/system/{name}", "[Unit]\n")
    rc, out = c4world.c4("--apply", capsys=capsys)
    assert rc == 0, out


def test_book_c4_installs_over_the_cores_own_units_and_its_lower_copies(c4world, capsys):
    """Not over-strict: the core's installed units, and a lower-priority copy of one, are
    known units, so a clean C4 install still goes through after the core's."""
    assert c4world.run("--apply", capsys=capsys)[0] == 0
    _dormant(c4world, "usr/lib/systemd/system/quantt-cef-session.service", "[Service]\n")
    rc, out = c4world.c4("--apply", capsys=capsys)
    assert rc == 0, out


def test_the_cores_install_still_scans_only_its_own_units():
    """The core's scan is what it was (its install is pinned to cee16ad's, byte for byte)."""
    assert iv.scan_units(iv.CORE_VM) == (iv.CORE_VM.unit_files, ())
    units, prefixes = iv.scan_units(iv.C4_VM)
    assert set(units) == set(iv.CORE_VM.unit_files) | set(iv.C4_VM.unit_files)
    assert prefixes == ("quantt-",)
