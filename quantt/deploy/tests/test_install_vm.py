"""The VM installer reproduces the laptop's jobs exactly, from a tag, and enables nothing by accident.

Each test pins one promise from `install_vm`'s docstring. These rot silently:

  * a timer that fires a minute late, or that fires at boot after a missed
    15:52 (Persistent=true);
  * a schedule that drifts from the launchd plists;
  * a job unit with Requires= on the key service, which a key rotation would
    kill mid-send;
  * a timer read in UTC.

None of these would show up until a trading day went wrong.

Hermetic throughout, like test_install_prod:
  * the "origin" is a local bare repo, and the prod clone is a git clone of it;
    git over a file path opens no socket;
  * /home/quantt and /etc/systemd/system are tmp directories;
  * /etc/localtime is a fake symlink;
  * systemctl and systemd-analyze go through a recording stub;
  * root is simulated (`euid=0`), and the service user is the test user.

The REAL systemd templates are copied into the fake repo, so the checks run
against the templates that will ship.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import inspect
import os
import shutil
import sys
import plistlib
import re
import subprocess
from pathlib import Path

import pytest

from quantt.deploy import install_prod as ip
from quantt.deploy import install_vm as iv

REAL_REPO = Path(iv.__file__).resolve().parents[2]
NOW = dt.datetime(2026, 10, 7, 20, 0, tzinfo=dt.timezone.utc)
# The installer's wall clock in tests: Wednesday 10:00 ET, far from any late window.
CLOCK = dt.datetime(2026, 10, 7, 14, 0, tzinfo=dt.timezone.utc)
ET = dt.timezone(dt.timedelta(hours=-4))          # EDT on these October dates
VAULT = "example-vault-x1"
GITC = ["-c", "user.name=t", "-c", "user.email=t@example.invalid",
        "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")      # Python weekday order


def git(*args, cwd):
    r = subprocess.run(["git", *GITC, *args], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def normalize(expr):
    """A stand-in for systemd's calendar normalisation. It is deliberately not
    the identity, so the tests prove the installer compares against what
    systemd reports rather than against its own strings."""
    return expr.replace("Mon,Tue,Wed,Thu,Fri", "Mon..Fri")


class FakeSystemd:
    """A recording stand-in for systemctl and systemd-analyze that models what
    the installer must not trust a unit FILE for. systemd runs what it loaded
    at the last `daemon-reload`, plus any drop-ins.

      enabled       timers `is-enabled` reports as enabled
      fail          argv prefix -> return code, for the matching call
      active        service -> `is-active` state (default inactive; the key
                    service defaults to active, as RemainAfterExit makes it)
      drop_ins      unit -> drop-in paths reported from the start
      drop_ins_after_reload  unit -> drop-in paths reported after the next reload
      fragment      unit -> a FragmentPath other than the units dir
      reload_takes_effect    False: daemon-reload leaves the old definitions loaded
    """

    # systemd's unit search path, in priority order, under the fake sysroot
    # (shape of `systemd-analyze unit-paths` on a system manager [S])
    SEARCH = ("etc/systemd/system.control", "run/systemd/system.control",
              "run/systemd/transient", "run/systemd/generator.early", "etc/systemd/system",
              "etc/systemd/system.attached", "run/systemd/system",
              "run/systemd/system.attached", "run/systemd/generator",
              "usr/local/lib/systemd/system", "usr/lib/systemd/system",
              "run/systemd/generator.late")

    def __init__(self, units_dir: Path):
        self.units_dir = units_dir
        self.sysroot = units_dir.parents[2]
        self.search = [self.sysroot / d for d in self.SEARCH]
        self.enabled = set()
        self.fail = {}
        self.active = {}
        self.drop_ins = {}
        self.drop_ins_after_reload = {}
        self.fragment = {}
        self.reload_takes_effect = True
        self.loaded = {}
        self.calls = []
        self.timer_active = set()     # timers currently running (waiting for their next elapse)
        self.jobs = {}                # unit -> queued job id (`systemctl show -p Job`)
        self.pids = {}                # unit -> MainPID of a running job
        self.environ = {}             # pid -> {VAR: value}, or an exception to raise
        # race_fire: if the session timer is still active when daemon-reload
        # runs, it fires first and starts the OLD session unit (the release-check
        # race, 2026-10-08). start_at_reload: (unit, pid, env), started right
        # after the reload whatever the timers do (a manual start).
        self.race_fire = False
        self.fired = False
        self.start_at_reload = None
        # the key service: started? its restarts (the vault in the LOADED unit
        # at each restart), a failing fetch, the mode the file gets
        self.secret_started = False
        self.secret_restarts = []
        self.secret_fails = False
        self.secret_mode = 0o600
        self.start_refuses = set()    # timers that stay inactive when started
        self.raise_on = {}            # argv prefix -> exception raised by run_cmd

    def _cp(self, args, rc=0, out=""):
        return subprocess.CompletedProcess(args, rc, out, "")

    def key_file(self):
        return self.sysroot / "run" / "quantt" / "alpaca.env"

    def _start_secret(self):
        exec_start = [v for k, v in self.loaded.get(iv.SECRET_UNIT, {}).get("Service", [])
                      if k == "ExecStart"]
        vault = re.search(r"--config vault=(\S+)", exec_start[0]).group(1) if exec_start else None
        self.secret_restarts.append(vault)
        if self.secret_fails:
            self.active[iv.SECRET_UNIT] = "failed"
            return False
        f = self.key_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(f.parent, 0o700)
        f.write_text("ALPACA_CEF_KEY_ID=x\nALPACA_CEF_SECRET_KEY=y\n")
        os.chmod(f, self.secret_mode)
        self.active.pop(iv.SECRET_UNIT, None)
        self.secret_started = True
        return True

    def __call__(self, args):
        self.calls.append(list(args))
        for prefix, exc in self.raise_on.items():
            if tuple(args[:len(prefix)]) == prefix:
                raise exc
        for prefix, rc in self.fail.items():
            if tuple(args[:len(prefix)]) == prefix:
                return subprocess.CompletedProcess(args, rc, "", "rejected by stub")
        if args[:2] == ["systemd-analyze", "unit-paths"]:
            return self._cp(args, 0, "".join(f"{d}\n" for d in self.search))
        if args[:2] == ["systemd-analyze", "calendar"]:
            return self._cp(args, 0, f"  Original form: {args[2]}\n"
                                     f"Normalized form: {normalize(args[2])}\n"
                                     f"    Next elapse: Thu 2026-10-08 15:52:00 EDT\n")
        if args[:2] == ["systemctl", "daemon-reload"]:
            if self.race_fire and "quantt-cef-session.timer" in self.timer_active:
                old_env = dict(v.split("=", 1) for k, v in
                               self.loaded.get("quantt-cef-session.service", {}).get("Service", [])
                               if k == "Environment")
                self.active["quantt-cef-session.service"] = "activating"
                self.pids["quantt-cef-session.service"] = "4242"
                self.environ["4242"] = old_env
                self.fired = True
            if self.reload_takes_effect:
                self.loaded = {p.name: iv.parse_unit(p.read_text(), p.name)
                               for p in self.units_dir.iterdir()
                               if p.suffix in (".service", ".timer")} \
                    if self.units_dir.exists() else {}
                for u, paths in self.drop_ins_after_reload.items():
                    self.drop_ins.setdefault(u, []).extend(paths)
            if self.start_at_reload:
                unit, pid, env = self.start_at_reload
                self.active[unit] = "activating"
                if pid:
                    self.pids[unit] = pid
                    self.environ[pid] = env
                else:
                    self.active[unit] = "inactive"
                    self.jobs[unit] = "77"
            return self._cp(args)
        if args[:2] == ["systemctl", "stop"]:
            self.timer_active -= set(args[2:])
            return self._cp(args)
        if args[:2] == ["systemctl", "start"]:
            self.timer_active |= {u for u in args[2:] if u.endswith(".timer")} - self.start_refuses
            return self._cp(args)
        if args[:3] == ["systemctl", "restart", iv.SECRET_UNIT]:
            ok = self._start_secret()
            return subprocess.CompletedProcess(args, 0 if ok else 1, "",
                                               "" if ok else "Job failed. See journalctl")
        if args[:3] == ["systemctl", "enable", "--now"]:
            self.timer_active |= {u for u in args[3:] if u.endswith(".timer")} - self.start_refuses
            self.enabled |= set(args[3:])
            if iv.SECRET_UNIT in args[3:]:
                self._start_secret()
            return self._cp(args)
        if args[:2] == ["systemctl", "enable"]:
            self.enabled |= set(args[2:])
            return self._cp(args)
        if args[:2] == ["systemctl", "is-enabled"]:
            return self._cp(args, 0 if args[-1] in self.enabled else 1)
        if args[:2] == ["systemctl", "is-active"]:
            unit = args[-1]
            state = self.active.get(unit, "active" if unit == iv.SECRET_UNIT else "inactive")
            return self._cp(args, 0 if state == "active" else 3, state + "\n")
        if args[:2] == ["systemctl", "show"]:
            unit = args[2]
            props = [args[i + 1] for i, a in enumerate(args) if a == "-p"]
            return self._cp(args, 0, self._show(unit, props))
        return self._cp(args)

    def _show(self, unit, props):
        u = self.loaded.get(unit)
        lines = []
        for prop in props:
            if prop == "FragmentPath":
                frag = self.fragment.get(unit, str(self.units_dir / unit) if u else "")
                lines.append(f"FragmentPath={frag}")
            elif prop == "DropInPaths":
                lines.append("DropInPaths=" + " ".join(self.drop_ins.get(unit, [])))
            elif prop == "Environment":
                env = [v for k, v in (u or {}).get("Service", []) if k == "Environment"]
                lines.append("Environment=" + " ".join(env))
            elif prop == "ExecStart":
                for k, v in (u or {}).get("Service", []):
                    if k == "ExecStart":
                        lines.append(f"ExecStart={{ path={v.split()[0]} ; argv[]={v} ; "
                                     f"ignore_errors=no ; start_time=[n/a] ; pid=0 }}")
            elif prop == "ActiveState":
                if unit.endswith(".timer"):
                    state = "active" if unit in self.timer_active else "inactive"
                else:
                    default = "active" if unit == iv.SECRET_UNIT and self.secret_started else "inactive"
                    state = self.active.get(unit, default)
                lines.append(f"ActiveState={state}")
            elif prop == "Job":
                lines.append("Job=" + self.jobs.get(unit, ""))
            elif prop == "MainPID":
                lines.append("MainPID=" + self.pids.get(unit, "0"))
            elif prop == "LoadState":
                lines.append("LoadState=" + ("loaded" if u else "not-found"))
            elif prop == "TimersCalendar":
                for k, v in (u or {}).get("Timer", []):
                    if k == "OnCalendar":
                        lines.append(f"TimersCalendar={{ OnCalendar={normalize(v)} ; "
                                     f"next_elapse=Thu 2026-10-08 15:52:00 EDT }}")
            else:
                raise AssertionError(f"installer asked for unexpected property {prop}")
        return "\n".join(lines) + "\n"

    def read_environ(self, pid):
        got = self.environ.get(str(pid))
        if isinstance(got, Exception):
            raise got
        if got is None:
            raise FileNotFoundError(f"/proc/{pid}/environ")
        return dict(got)

    def mutating(self):
        read_only = {"is-enabled", "is-active", "show"}
        return [c for c in self.calls if c[0] == "systemctl" and c[1] not in read_only]


class World:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.layout = iv.Layout(tmp / "home" / "quantt", units_dir=tmp / "etc" / "systemd" / "system",
                                sysroot=tmp)
        self.layout.home.mkdir(parents=True)
        self.localtime = tmp / "localtime"
        self.set_tz("America/New_York")
        py = self.layout.venv_python
        py.parent.mkdir(parents=True)
        py.write_text("#!/bin/sh\n")
        os.chmod(py, 0o755)
        self.seed = tmp / "seed"
        self.seed.mkdir()
        for name in ip.SEED_FILES + ip.SEED_SUPPORT:
            (self.seed / name).write_bytes(f"laptop prod bytes of {name}".encode())
        self.cmds = FakeSystemd(self.layout.units_dir)
        self.dev = tmp / "dev"
        self.origin = tmp / "origin.git"
        self._make_repo()
        # what bootstrap.sh does: clone, detach at the tag
        git("clone", "-q", str(self.origin), str(self.layout.prod_dir), cwd=tmp)
        git("checkout", "-q", "--detach", "refs/tags/v1", cwd=self.layout.prod_dir)
        # what bootstrap.sh records after installing the tag's requirements.txt
        self.record_requirements()

    def record_requirements(self):
        digest = hashlib.sha256((self.layout.prod_dir / "requirements.txt").read_bytes()).hexdigest()
        self.layout.requirements_record.write_text(digest + "\n")

    def set_tz(self, zone):
        if self.localtime.is_symlink():
            self.localtime.unlink()
        os.symlink(f"/usr/share/zoneinfo/{zone}", self.localtime)

    def _make_repo(self):
        d = self.dev
        d.mkdir()
        git("init", "-q", "-b", "main", cwd=d)
        (d / ".gitignore").write_text("/data/\n")
        for rel in iv.REQUIRED_AT_TAG:
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            src = REAL_REPO / rel
            if rel.startswith(iv.TEMPLATE_DIR):
                (d / rel).write_text(src.read_text())
            else:
                (d / rel).write_text(f"# stub {rel}\n")
        git("add", "-A", cwd=d)
        git("commit", "-q", "-m", "v1", cwd=d)
        git("tag", "-a", "v1", "-m", "release v1", cwd=d)
        subprocess.run(["git", "clone", "-q", "--bare", str(d), str(self.origin)],
                       check=True, capture_output=True)
        git("remote", "add", "origin", str(self.origin), cwd=d)

    def commit_and_tag(self, tag, change, push=True):
        change(self.dev)
        git("add", "-A", cwd=self.dev)
        git("commit", "-q", "-m", tag, cwd=self.dev)
        git("tag", "-a", tag, "-m", tag, cwd=self.dev)
        if push:
            git("push", "-q", "origin", "main", tag, cwd=self.dev)

    def tag_commit(self, tag):
        return git("rev-parse", f"{tag}^{{commit}}", cwd=self.dev)

    def head(self):
        return git("rev-parse", "HEAD", cwd=self.layout.prod_dir)

    def run(self, *extra, tag="v1", vault=VAULT, seed=True, capsys=None, **kw):
        argv = ["--tag", tag, "--vault", vault, *extra]
        if seed:
            argv += ["--seed-from", str(self.seed)]
        opts = dict(layout=self.layout, origin_url=str(self.origin), localtime=self.localtime,
                    run_cmd=self.cmds, as_user=[], euid=0, dont_write_bytecode=True,
                    user_ids=lambda u: (os.getuid(), os.getgid()), now_utc=NOW,
                    read_environ=self.cmds.read_environ, clock=lambda: CLOCK)
        opts.update(kw)
        rc = iv.main(argv, **opts)
        out = capsys.readouterr().out if capsys else ""
        return rc, out

    def unit(self, name):
        return iv.parse_unit(self.layout.unit_path(name).read_text(), name)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def values(unit, section, key):
    return [v for k, v in unit[section] if k == key]


# -- schedule equivalence: the plists are the authority -----------------------

def fires_launchd(intervals) -> set:
    """(python weekday, hour, minute) for every firing in a week. launchd's
    Weekday 0 and 7 are Sunday, 1 is Monday; an omitted key is a wildcard."""
    out = set()
    for d in intervals:
        days = range(7) if "Weekday" not in d else [(d["Weekday"] - 1) % 7]
        hours = range(24) if "Hour" not in d else [d["Hour"]]
        mins = range(60) if "Minute" not in d else [d["Minute"]]
        out |= {(w, h, m) for w in days for h in hours for m in mins}
    return out


def fires_oncalendar(exprs) -> set:
    """The same set for systemd expressions of the shapes install_vm writes:
    `[Day,Day ]*-*-* HH|*:MM:00`. Anything else fails the test loudly."""
    out = set()
    for e in exprs:
        parts = e.split()
        days, (date, clock) = (parts[0].split(","), parts[1:]) if len(parts) == 3 \
            else (list(DAYS), parts)
        assert date == "*-*-*", e
        hh, mm, ss = clock.split(":")
        assert ss == "00", e
        hours = range(24) if hh == "*" else [int(hh)]
        out |= {(DAYS.index(dd), h, int(mm)) for dd in days for h in hours}
    return out


def real_plist(job: ip.Job, tmp: Path) -> dict:
    lay = ip.Layout(tmp)
    py = Path("/usr/bin/python3")
    env = ip.expected_env("1", lay, tmp / "k.env", py)
    text = ip.render((REAL_REPO / job.template).read_text(),
                     {"TAG": "vX", "PYTHON": py, "PROD_DIR": lay.prod_dir, "DRY_RUN": "1",
                      "STATE_DIR": lay.state_dir, "ENV_FILE": tmp / "k.env",
                      "PATH": env["PATH"], "LOG_DIR": lay.log_dir})
    return plistlib.loads(text.encode())


def test_translated_schedule_fires_exactly_when_the_launchd_plists_do(tmp_path):
    for vj in iv.VM_JOBS:
        plist = real_plist(vj.job, tmp_path)
        want = fires_launchd(plist["StartCalendarInterval"])
        assert fires_oncalendar(iv.oncalendar(vj.job.schedule)) == want, vj.timer


def test_installed_timers_fire_exactly_when_the_launchd_plists_do(world, capsys, tmp_path):
    assert world.run("--apply", capsys=capsys)[0] == 0
    for vj in iv.VM_JOBS:
        want = fires_launchd(real_plist(vj.job, tmp_path)["StartCalendarInterval"])
        got = fires_oncalendar(values(world.unit(vj.timer), "Timer", "OnCalendar"))
        assert got == want, vj.timer


def test_sunday_is_both_0_and_7_in_launchd():
    assert iv.oncalendar([{"Weekday": 0, "Hour": 1, "Minute": 2},
                          {"Weekday": 7, "Hour": 1, "Minute": 2}]) == ["Sun *-*-* 01:02:00"]
    assert iv.oncalendar([{"Hour": 9, "Minute": 5}]) == ["*-*-* 09:05:00"]


def test_every_launchd_job_has_a_vm_job():
    assert {vj.job.label for vj in iv.VM_JOBS} == {j.label for j in ip.JOBS}


def test_timers_are_not_persistent_and_second_accurate(world, capsys):
    world.run("--apply", capsys=capsys)
    for vj in iv.VM_JOBS:
        t = world.unit(vj.timer)
        assert values(t, "Timer", "Persistent") == ["false"], vj.timer
        assert values(t, "Timer", "AccuracySec") == ["1s"], vj.timer
        assert values(t, "Timer", "Unit") == [vj.service]


def test_no_calendar_line_carries_its_own_timezone(world, capsys):
    """One mechanism: the system zone. A per-line zone would be a second one."""
    world.run("--apply", capsys=capsys)
    for vj in iv.VM_JOBS:
        for expr in values(world.unit(vj.timer), "Timer", "OnCalendar"):
            assert re.fullmatch(r"\d\d:\d\d:00|\*:\d\d:00", expr.split()[-1]), expr


# -- commands and environment: the launchd jobs' -------------------------------

def test_job_units_run_the_launchd_commands_with_the_launchd_environment(world, capsys, tmp_path):
    assert world.run("--apply", capsys=capsys)[0] == 0
    py = world.layout.venv_python
    env = ip.expected_env("1", world.layout, iv.ENV_FILE, py)
    for vj in iv.VM_JOBS:
        s = world.unit(vj.service)
        plist_args = real_plist(vj.job, tmp_path)["ProgramArguments"][1:]
        assert values(s, "Service", "ExecStart") == [" ".join([str(py), *plist_args])]
        assert values(s, "Service", "Environment") == [f"{k}={v}" for k, v in env.items()]
        assert dict(x.split("=", 1) for x in values(s, "Service", "Environment"))["DRY_RUN"] == "1"
        assert values(s, "Service", "User") == [iv.SERVICE_USER]
        assert values(s, "Service", "WorkingDirectory") == [str(world.layout.prod_dir)]


def test_job_units_want_the_key_service_and_never_require_it(world, capsys):
    """Requires= would stop a running send when the key service is restarted."""
    world.run("--apply", capsys=capsys)
    for vj in iv.VM_JOBS:
        u = world.unit(vj.service)["Unit"]
        assert ("Wants", iv.SECRET_UNIT) in u and ("After", iv.SECRET_UNIT) in u
        assert not [k for k, _ in u if k in ("Requires", "BindsTo", "Requisite", "PartOf")]


def test_key_service_writes_the_file_the_jobs_read_into_a_private_tmpfs_dir(world, capsys):
    world.run("--apply", capsys=capsys)
    s = world.unit(iv.SECRET_UNIT)["Service"]
    assert ("RuntimeDirectory", "quantt") in s and ("RuntimeDirectoryMode", "0700") in s
    assert iv.ENV_FILE.parent == Path("/run") / "quantt"
    exec_start = [v for k, v in s if k == "ExecStart"][0].split()
    assert exec_start == iv.secret_command(world.layout.venv_python, VAULT)
    assert exec_start[exec_start.index("--out") + 1] == str(iv.ENV_FILE)
    for vj in iv.VM_JOBS:
        env = dict(x.split("=", 1) for x in values(world.unit(vj.service), "Service", "Environment"))
        assert env["QUANTT_ENV_FILE"] == str(iv.ENV_FILE)


def test_session_success_exits_match_run_py():
    """Normal outcomes are not 'failed'; REFUSED and FAIL still are."""
    from quantt.session import run
    normal = {run.EXIT_NOTHING, run.EXIT_PREVIEW, run.EXIT_IDLE, run.EXIT_PLANNED, run.EXIT_DRY}
    assert set(iv.SESSION_SUCCESS_EXIT) == normal
    assert run.EXIT_REFUSED not in normal and run.EXIT_FAIL not in normal


# -- dry run, apply, enable ----------------------------------------------------

def test_dry_run_writes_nothing_and_shows_every_unit(world, capsys):
    head = world.head()
    rc, out = world.run(capsys=capsys)
    assert rc == 0, out
    assert not world.layout.units_dir.exists()
    assert not world.layout.state_dir.exists()
    assert not (world.layout.prod_dir / "data").exists()
    assert world.head() == head
    assert "WOULD 1." in out and "DOING" not in out
    assert out.count("(rendered, not written)") == len(iv.ALL_UNIT_FILES) == 7
    assert world.cmds.mutating() == []
    analyzed = [c[2] for c in world.cmds.calls if c[:2] == ["systemd-analyze", "calendar"]]
    assert sorted(analyzed) == sorted(e for vj in iv.VM_JOBS for e in iv.oncalendar(vj.job.schedule))


def test_apply_writes_units_and_reloads_but_enables_nothing(world, capsys):
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 0, out
    for name in iv.ALL_UNIT_FILES:
        p = world.layout.unit_path(name)
        assert oct(p.stat().st_mode & 0o777) == "0o644", name
    assert sorted(p.name for p in world.layout.units_dir.iterdir()) == sorted(iv.ALL_UNIT_FILES)
    assert world.cmds.mutating() == [["systemctl", "daemon-reload"]]
    assert "NOT enabled" in out
    assert oct(world.layout.state_dir.stat().st_mode & 0o777) == "0o700"
    assert world.layout.log_dir.is_dir()


def test_enable_starts_the_key_service_then_the_timers(world, capsys):
    rc, _ = world.run("--apply", "--enable", capsys=capsys)
    assert rc == 0
    assert world.cmds.mutating() == [
        ["systemctl", "daemon-reload"],
        ["systemctl", "enable", iv.SECRET_UNIT],
        ["systemctl", "restart", iv.SECRET_UNIT],         # the keys match the loaded unit
        ["systemctl", "enable", "--now", *[vj.timer for vj in iv.VM_JOBS]]]


def test_enable_requires_apply(world, capsys):
    with pytest.raises(SystemExit):
        world.run("--enable", capsys=capsys)


def test_armed_renders_dry_run_zero_and_warns_and_reinstall_disarms(world, capsys):
    rc, out = world.run("--apply", "--armed", capsys=capsys)
    assert rc == 0 and "ARMED" in out and "AUTO_ARMED" in out
    env = lambda: dict(x.split("=", 1) for x in values(
        world.unit("quantt-cef-session.service"), "Service", "Environment"))
    assert env()["DRY_RUN"] == "0"
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 0 and "systemd currently runs DRY_RUN=0" in out
    assert env()["DRY_RUN"] == "1"
    # daemon-reload ran on both installs: systemd runs what the files say
    assert world.cmds.mutating().count(["systemctl", "daemon-reload"]) == 2


def test_enabled_timers_are_started_and_read_back(world, capsys):
    """Enabled means running after the install, read back from systemd."""
    world.cmds.enabled = {vj.timer for vj in iv.VM_JOBS}
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 0, out
    assert world.cmds.timer_active == set(TIMERS)
    assert "read back" in out and "their next firing" not in out


def test_installer_never_writes_auto_armed(world, capsys):
    world.run("--apply", "--enable", "--armed", capsys=capsys)
    assert not (world.layout.state_dir / "AUTO_ARMED").exists()


# -- what systemd runs, not what the file says (review 2026-10-07, finding 1) ----------

def test_a_drop_in_override_is_refused_before_anything_is_written(world, capsys):
    """`systemctl edit` writes override.conf; an Environment=DRY_RUN=0 there
    would survive a disarm-by-reinstall that only rewrites the unit file."""
    world.cmds.drop_ins["quantt-cef-session.service"] = [
        "/etc/systemd/system/quantt-cef-session.service.d/override.conf"]
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "drop-in" in out and "override.conf" in out, out
    assert not world.layout.units_dir.exists()
    assert world.cmds.mutating() == []


def test_a_prefix_drop_in_is_refused(world, capsys):
    world.cmds.drop_ins["quantt-cef-verify.service"] = [
        "/etc/systemd/system/quantt-.service.d/50-x.conf"]
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "quantt-.service.d" in out


def test_a_drop_in_on_a_timer_is_refused(world, capsys):
    world.cmds.drop_ins["quantt-cef-session.timer"] = [
        "/etc/systemd/system.control/quantt-cef-session.timer.d/50-Persistent.conf"]
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "drop-in" in out


def test_a_drop_in_that_appears_by_the_reload_is_refused_after_it(world, capsys):
    world.cmds.drop_ins_after_reload["quantt-cef-session.service"] = [
        "/run/systemd/system.control/quantt-cef-session.service.d/50-Environment.conf"]
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "REFUSED at step" in out and "drop-in" in out, out


def test_a_unit_loaded_from_another_file_is_refused(world, capsys):
    world.run("--apply", capsys=capsys)
    world.cmds.fragment["quantt-cef-session.service"] = \
        "/run/systemd/transient/quantt-cef-session.service"
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "/run/systemd/transient" in out


def test_disarm_is_confirmed_from_what_systemd_loaded(world, capsys):
    """If the reload did not take effect, systemd still runs DRY_RUN=0. The
    install must say so instead of reporting a disarm the file alone claims."""
    assert world.run("--apply", "--armed", capsys=capsys)[0] == 0
    world.cmds.reload_takes_effect = False
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "REFUSED at step" in out and "DRY_RUN=0" in out, out


def test_loaded_timers_are_checked_against_systemds_normal_form(world, capsys):
    """systemd reports `Mon..Fri`, not the template's `Mon,Tue,Wed,Thu,Fri`; the
    comparison goes through systemd-analyze's own normalisation."""
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 0, out
    shows = [c for c in world.cmds.calls if c[:2] == ["systemctl", "show"]]
    assert {c[2] for c in shows} == set(iv.ALL_UNIT_FILES)
    assert any("TimersCalendar" in c for c in shows)


# -- dormant drop-ins on disk (re-review 2026-10-07, N1) ------------------------------
#
# MEASURED on the VM (systemd 255.4-1ubuntu8.17, 2026-10-07): a drop-in written
# WITHOUT daemon-reload is invisible to `systemctl show` (DropInPaths empty, old
# Environment, NeedDaemonReload=no) until the next reload, which is the
# installer's own. So the fake systemd here does NOT report these files; only a
# scan of the disk can find them.

def units_written(world):
    d = world.layout.units_dir
    return sorted(p.name for p in d.iterdir() if p.is_file()) if d.exists() else []


def dormant(world, rel, body="[Service]\nEnvironment=DRY_RUN=0\n"):
    f = world.tmp / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body)
    return f


@pytest.mark.parametrize("rel", [
    "etc/systemd/system/quantt-cef-session.service.d/override.conf",        # systemctl edit
    "usr/lib/systemd/system/quantt-.service.d/50-x.conf",                   # dash prefix
    "run/systemd/system/quantt-cef-.service.d/50-x.conf",                   # longer prefix
    "etc/systemd/system/quantt-cef-session-.service.d/50-x.conf",           # full-stem prefix
    "run/systemd/system/service.d/50-x.conf",                               # every service
    "usr/local/lib/systemd/system/timer.d/50-x.conf",                       # every timer
    "etc/systemd/system.control/quantt-cef-session.service.d/50-Environment.conf",  # set-property
    "run/systemd/system.control/quantt-secret.service.d/50-x.conf",         # set-property --runtime
    "run/systemd/transient/quantt-cef-verify.service.d/50-x.conf",
])
def test_a_dormant_drop_in_on_disk_is_refused_before_anything_is_written(world, capsys, rel):
    f = dormant(world, rel)
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and str(f) in out, out
    assert "REFUSED at step" not in out          # at planning: nothing at all has run
    assert not world.layout.state_dir.exists()
    assert units_written(world) == []
    assert world.cmds.mutating() == []          # in particular, no daemon-reload ran


def test_a_dormant_unit_file_that_would_outrank_ours_is_refused(world, capsys):
    f = dormant(world, "run/systemd/transient/quantt-cef-session.timer", "[Timer]\n")
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and str(f) in out and "REFUSED at step" not in out, out
    assert not world.layout.units_dir.exists()


def test_a_lower_priority_copy_and_a_non_conf_file_are_not_overrides(world, capsys):
    dormant(world, "usr/lib/systemd/system/quantt-cef-session.service", "[Service]\n")
    dormant(world, "etc/systemd/system/quantt-cef-session.service.d/README", "notes\n")
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 0, out


def test_a_drop_in_appearing_after_planning_is_caught_before_the_units_change(world, capsys):
    seen = {"n": 0}
    real = world.cmds.__call__

    def racing(args):
        # plant it once planning's busy look at the collector is done
        if args[:3] == ["systemctl", "show", "quantt-cef-collect.service"] and "ActiveState" in args:
            seen["n"] += 1
            if seen["n"] == 1:
                dormant(world, "etc/systemd/system/quantt-cef-verify.service.d/late.conf")
        return real(args)
    rc, out = world.run("--apply", run_cmd=racing, capsys=capsys)
    assert rc == 2 and "late.conf" in out and "REFUSED at step" in out, out
    assert units_written(world) == []
    assert ["systemctl", "daemon-reload"] not in world.cmds.calls


def test_control_dirs_are_scanned_even_if_unit_paths_omits_them(world, capsys):
    """set-property's directories are checked whether or not systemd lists them."""
    world.cmds.search = [d for d in world.cmds.search
                         if not str(d).endswith((".control", "transient"))]
    f = dormant(world, "etc/systemd/system.control/quantt-cef-session.service.d/50-Environment.conf")
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and str(f) in out, out


def test_the_units_dir_must_be_on_systemds_search_path(world, capsys):
    world.cmds.search = [d for d in world.cmds.search if d != world.layout.units_dir]
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "search path" in out


def test_a_post_reload_refusal_says_systemd_is_now_running_it(world, capsys):
    world.cmds.drop_ins_after_reload["quantt-cef-session.service"] = [
        "/run/systemd/system.control/quantt-cef-session.service.d/50-Environment.conf"]
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "NOW running" in out and "AUTO_ARMED" in out and "HALT" in out, out


# -- Environment order is pinned at planning (re-review 2026-10-07, N2) ---------------

def test_a_template_with_reordered_environment_is_refused_before_anything_is_written(world, capsys):
    """systemd keeps Environment= in file order (measured on the VM), and the
    post-reload check compares the ordered list; planning must refuse first."""
    rel = iv.template_path("quantt-cef-session.service")

    def change(d):
        t = (d / rel).read_text()
        a = "Environment=DRY_RUN=${DRY_RUN}\n"
        b = "Environment=QUANTT_STATE_DIR=${STATE_DIR}\n"
        assert a + b in t
        (d / rel).write_text(t.replace(a + b, b + a))
    world.commit_and_tag("v2", change)
    rc, out = world.run("--apply", tag="v2", capsys=capsys)
    assert rc == 2 and "fails its checks" in out and "order" in out, out
    assert not world.layout.units_dir.exists()


# -- never under a running job (review 2026-10-07, finding 4) --------------------------

@pytest.mark.parametrize("state", ["active", "activating", "deactivating", "reloading"])
def test_install_is_refused_while_a_job_runs(world, capsys, state):
    world.cmds.active["quantt-cef-session.service"] = state
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "quantt-cef-session.service" in out and state in out, out
    assert not world.layout.units_dir.exists()
    assert world.head() == world.tag_commit("v1")


def test_a_job_that_starts_after_planning_stops_the_install_before_checkout(world, capsys):
    """And because the run had already stopped the timers, it says they are
    left stopped (RUNBOOK 8.6: an abandoned update must restart them)."""
    world.commit_and_tag("v2", lambda d: (d / "ops/halt.py").write_text("# v2\n"))
    world.run("--apply", "--enable", capsys=capsys)              # timers active
    seen = {"n": 0}
    real = world.cmds.__call__

    def racing(args):
        if args[:3] == ["systemctl", "show", "quantt-cef-verify.service"] and "ActiveState" in args:
            seen["n"] += 1
            if seen["n"] > 1:                                    # after planning's look
                world.cmds.active["quantt-cef-verify.service"] = "activating"
        return real(args)
    world.cmds.calls.clear()
    rc, out = world.run("--apply", tag="v2", run_cmd=racing, capsys=capsys)
    assert rc == 2 and "REFUSED at step" in out and "timers left STOPPED" in out, out
    assert world.head() == world.tag_commit("v1")
    assert world.cmds.timer_active == set()
    assert not [c for c in world.cmds.calls if c[:2] == ["systemctl", "start"]]


# -- the timers are stopped for the run (release-check NO-GO, 2026-10-08) -------------

TIMERS = [vj.timer for vj in iv.VM_JOBS]


def armed_and_running(world, capsys):
    """An armed VM with its timers running: the state a disarm starts from."""
    assert world.run("--apply", "--armed", "--enable", capsys=capsys)[0] == 0
    assert world.cmds.timer_active == set(TIMERS)
    world.cmds.calls.clear()


def test_a_firing_cannot_start_the_old_unit_between_the_last_look_and_the_reload(world, capsys):
    """The race: a 15:52 firing after the last busy look but before daemon-reload
    would start the OLD unit (DRY_RUN=0) while the disarm reports DRY_RUN=1."""
    armed_and_running(world, capsys)
    world.cmds.race_fire = True
    rc, out = world.run("--apply", capsys=capsys)            # the disarm
    assert rc == 0, out
    assert not world.cmds.fired                               # no job could start
    calls = world.cmds.mutating()
    stop = calls.index(["systemctl", "stop", *TIMERS])
    assert stop < calls.index(["systemctl", "daemon-reload"])
    assert calls[-1] == ["systemctl", "start", *TIMERS]       # restored, last
    assert world.cmds.timer_active == set(TIMERS)


def test_every_enabled_timer_is_running_at_the_end_even_one_stopped_by_hand(world, capsys):
    """The end state is set by ENABLEMENT, not by what happened to be running:
    a timer that is enabled is running after a successful install. To keep
    one off, disable it."""
    armed_and_running(world, capsys)
    world.cmds.timer_active.discard("quantt-cef-collect.timer")   # stopped by hand, still enabled
    running = [t for t in TIMERS if t != "quantt-cef-collect.timer"]
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 0, out
    calls = world.cmds.mutating()
    assert calls[0] == ["systemctl", "stop", *running]
    assert calls[-1] == ["systemctl", "start", *TIMERS]
    assert world.cmds.timer_active == set(TIMERS)


def test_enable_starts_every_timer_after_the_checks(world, capsys):
    armed_and_running(world, capsys)
    world.cmds.timer_active.clear()                          # an update stopped them (8.6)
    rc, out = world.run("--apply", "--armed", "--enable", capsys=capsys)
    assert rc == 0, out
    calls = world.cmds.mutating()
    assert ["systemctl", "stop", *TIMERS] not in calls       # nothing was running to stop
    assert calls[-1] == ["systemctl", "enable", "--now", *TIMERS]


@pytest.mark.parametrize("environ,shown", [({"DRY_RUN": "0"}, "DRY_RUN=0"),
                                           (PermissionError("denied"), "unreadable")])
def test_a_job_running_after_the_reload_stops_the_run_with_its_own_code(world, capsys,
                                                                       environ, shown):
    armed_and_running(world, capsys)
    world.cmds.start_at_reload = ("quantt-cef-session.service", "4242", environ)
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == iv.EXIT_JOB_DURING_INSTALL != 2, out
    assert "quantt-cef-session.service" in out and "4242" in out and shown in out, out
    assert "8.6" in out and "timers left STOPPED" in out
    assert world.cmds.timer_active == set()
    assert not [c for c in world.cmds.mutating() if c[:2] == ["systemctl", "start"]]


def test_a_job_queued_after_the_reload_also_stops_the_run(world, capsys):
    armed_and_running(world, capsys)
    world.cmds.start_at_reload = ("quantt-cef-verify.service", None, None)
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == iv.EXIT_JOB_DURING_INSTALL and "quantt-cef-verify.service" in out
    assert "queued" in out, out


def test_a_queued_job_counts_as_busy(world, capsys):
    """MEASURED on the VM (2026-10-08): a start queued behind its After=
    dependency reads is-active `inactive`, but `show -p Job` is non-empty."""
    world.cmds.jobs["quantt-cef-session.service"] = "1234"
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "quantt-cef-session.service" in out and "queued" in out, out
    assert units_written(world) == []


def test_the_key_service_activating_counts_as_busy(world, capsys):
    """A job may be queued behind it (After=quantt-secret.service)."""
    world.cmds.active[iv.SECRET_UNIT] = "activating"
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and iv.SECRET_UNIT in out and "activating" in out, out


def test_a_refusal_before_stopping_leaves_the_timers_running(world, capsys):
    armed_and_running(world, capsys)
    world.cmds.active["quantt-cef-session.service"] = "activating"   # seen at planning
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "timers left STOPPED" not in out
    assert world.cmds.timer_active == set(TIMERS)
    assert world.cmds.mutating() == []


# -- release-check #2 (2026-10-08): no silent stop, no stale keys ---------------------

def test_a_rerun_after_a_refusal_restarts_every_enabled_timer(world, capsys):
    """The silent stop: a refusal after the stop leaves the timers stopped (and
    says so); the re-run the message asks for must leave them RUNNING, read
    back. Before the fix it exited 0 with all three still stopped."""
    world.commit_and_tag("v2", lambda d: (d / "ops/halt.py").write_text("# v2\n"))
    armed_and_running(world, capsys)
    seen = {"n": 0}
    real = world.cmds.__call__

    def racing(args):
        if args[:3] == ["systemctl", "show", "quantt-cef-verify.service"] and "ActiveState" in args:
            seen["n"] += 1
            if seen["n"] > 1:
                world.cmds.active["quantt-cef-verify.service"] = "activating"
        return real(args)
    rc, out = world.run("--apply", "--armed", tag="v2", run_cmd=racing, capsys=capsys)
    assert rc == 2 and "timers left STOPPED" in out
    world.cmds.active["quantt-cef-verify.service"] = "inactive"      # the job finished
    rc, out = world.run("--apply", "--armed", tag="v2", capsys=capsys)
    assert rc == 0, out
    assert world.cmds.timer_active == set(TIMERS)


def test_an_enabled_timer_that_will_not_start_refuses_loudly(world, capsys):
    armed_and_running(world, capsys)
    world.cmds.start_refuses = {"quantt-cef-verify.timer"}
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "quantt-cef-verify.timer" in out and "not active" in out, out
    assert "timers left STOPPED: quantt-cef-verify.timer" in out


def test_a_changed_vault_restarts_the_key_service(world, capsys):
    """The key service is oneshot + RemainAfterExit: never restarted, it would
    keep serving the old vault's keys after a successful install."""
    assert world.run("--apply", "--enable", vault="example-vault-x1", capsys=capsys)[0] == 0
    world.cmds.calls.clear()
    rc, out = world.run("--apply", vault="example-vault-x2", capsys=capsys)
    assert rc == 0, out
    assert world.cmds.secret_restarts[-1] == "example-vault-x2"
    calls = world.cmds.mutating()
    assert calls.index(["systemctl", "restart", iv.SECRET_UNIT]) > \
        max(i for i, c in enumerate(calls) if c == ["systemctl", "daemon-reload"])


def test_the_key_service_is_restarted_on_every_apply_while_the_timers_are_stopped(world, capsys):
    armed_and_running(world, capsys)
    n = len(world.cmds.secret_restarts)
    rc, out = world.run("--apply", "--armed", capsys=capsys)       # same vault
    assert rc == 0, out
    assert len(world.cmds.secret_restarts) == n + 1
    calls = world.cmds.mutating()
    assert calls.index(["systemctl", "stop", *TIMERS]) < \
        calls.index(["systemctl", "restart", iv.SECRET_UNIT]) < \
        calls.index(["systemctl", "start", *TIMERS])


def test_a_failing_key_fetch_refuses_with_the_timers_left_stopped(world, capsys):
    armed_and_running(world, capsys)
    world.cmds.secret_fails = True
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and iv.SECRET_UNIT in out, out
    assert "timers left STOPPED" in out and world.cmds.timer_active == set()


def test_a_key_file_with_the_wrong_mode_refuses(world, capsys):
    armed_and_running(world, capsys)
    world.cmds.secret_mode = 0o644
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "0o644" in out and "timers left STOPPED" in out, out


def test_a_first_install_without_enable_starts_no_key_service(world, capsys):
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 0, out
    assert world.cmds.secret_restarts == []


def test_an_unexpected_error_after_the_stop_still_reports_the_stopped_timers(world, capsys):
    armed_and_running(world, capsys)
    world.cmds.raise_on = {("systemctl", "daemon-reload"): RuntimeError("dbus went away")}
    with pytest.raises(RuntimeError, match="dbus went away"):
        world.run("--apply", capsys=capsys)
    out = capsys.readouterr().out
    assert "timers left STOPPED" in out, out


def test_a_venv_built_from_other_requirements_is_refused(world, capsys):
    world.commit_and_tag("v2", lambda d: (d / "requirements.txt").write_text("pandas==9.9.9\n"))
    rc, out = world.run("--apply", tag="v2", capsys=capsys)
    assert rc == 2 and "requirements.txt" in out and "uv pip install --no-build" in out, out
    assert world.head() == world.tag_commit("v1") and units_written(world) == []


def test_a_venv_with_no_requirements_record_is_refused(world, capsys):
    world.layout.requirements_record.unlink()
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and str(world.layout.requirements_record) in out, out


# -- the late-window guard (release-check #3, 2026-10-08) ----------------------------
#
# MEASURED on the VM [V, 2026-10-08 04:38-04:41 UTC]: an ENABLED Persistent=false
# timer stopped and restarted within one boot across a missed slot FIRES AT
# ONCE on the restart. An --apply stops the timers, so one that spans 15:52 or
# 15:55 (12:52/12:55 on an early close) would replay the send slot at its
# restart: a late, partial send. Hence the guard.

def et(h, m, s=0, day=7):
    """A UTC instant for h:m:s ET on 2026-10-<day> (the 7th is a Wednesday)."""
    return dt.datetime(2026, 10, day, h, m, s, tzinfo=ET).astimezone(dt.timezone.utc)


@pytest.mark.parametrize("t", [et(15, 30), et(15, 40), et(15, 52), et(15, 59, 59),
                               et(12, 30), et(12, 40), et(12, 59)])
def test_an_install_inside_a_late_window_is_refused_at_planning(world, capsys, t):
    armed_and_running(world, capsys)
    rc, out = world.run("--apply", clock=lambda: t, capsys=capsys)
    assert rc == 2 and "late" in out and "16:00" in out, out
    assert world.cmds.mutating() == []
    assert world.cmds.timer_active == set(TIMERS)


@pytest.mark.parametrize("t", [et(15, 29, 59), et(16, 0), et(12, 29, 59), et(13, 0),
                               et(15, 45, day=10)])                 # Saturday
def test_outside_the_late_windows_or_at_the_weekend_the_install_runs(world, capsys, t):
    rc, out = world.run("--apply", clock=lambda: t, capsys=capsys)
    assert rc == 0, out


def test_the_windows_cover_the_runners_late_ranges_and_the_books_send_window():
    """Mirrored, not imported: the installer never imports quantt.session.

      * planning refuses a SUPERSET of the runner's LATE_LOCAL_RANGES;
      * the restart guard starts exactly where the book's send window starts
        (close - window_minutes_before_close[0]) and runs to the close, for a
        16:00 and a 13:00 close.
    """
    from quantt.session import run
    for a, b in run.LATE_LOCAL_RANGES:
        assert any(pa <= a and b <= pb for pa, pb in iv.PLAN_REFUSE_RANGES_ET), (a, b)
    first = run.execution_for(run.BOOKS["cef"])["window_minutes_before_close"][0]
    want = tuple(((dt.datetime.combine(dt.date(2026, 10, 7), close)
                   - dt.timedelta(minutes=first)).time(), close)
                 for close in (dt.time(16, 0), dt.time(13, 0)))
    assert iv.RESTART_REFUSE_RANGES_ET == want


@pytest.mark.parametrize("extra", [(), ("--enable",)])
def test_a_restart_that_would_land_in_a_late_window_leaves_the_timers_stopped(world, capsys,
                                                                             extra):
    armed_and_running(world, capsys)
    times = iter([et(15, 29, 50)])            # planning; every later read is 15:52:00

    def clock():
        return next(times, et(15, 52))
    rc, out = world.run("--apply", "--armed", *extra, clock=clock, capsys=capsys)
    assert rc == 2 and "not restarting" in out and "16:00" in out, out
    assert "timers left STOPPED" in out
    assert world.cmds.timer_active == set()
    assert not [c for c in world.cmds.mutating()
                if c[:2] == ["systemctl", "start"] or c[:3] == ["systemctl", "enable", "--now"]]


# -- release-check #4 (2026-10-08): advice that starts timers, and the deps step -------

def test_the_stopped_timers_notice_warns_about_the_late_windows_and_names_the_loaded_dry_run(
        world, capsys):
    """A bare `systemctl start` inside 15:52-15:58 replays the send slot (M1).
    The notice must say so, prefer re-running the installer, and name the DRY_RUN
    systemd has LOADED, since that is what a start would run."""
    armed_and_running(world, capsys)
    world.cmds.secret_fails = True                       # refuses after the reload (DRY_RUN=1 loaded)
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "timers left STOPPED" in out, out
    for want in ("15:40-16:00", "12:40-13:00", "after 16:00", "re-run the installer",
                 "DRY_RUN=1 LOADED for quantt-cef-session.service"):
        assert want in out, (want, out)


def test_the_notice_says_unknown_when_the_loaded_dry_run_cannot_be_read(world, capsys):
    armed_and_running(world, capsys)
    world.cmds.secret_fails = True
    real = world.cmds.__call__
    after = {"restart": False}

    def flaky(args):
        if args[:3] == ["systemctl", "restart", iv.SECRET_UNIT]:
            after["restart"] = True
        if after["restart"] and args[:3] == ["systemctl", "show", "quantt-cef-session.service"]:
            world.cmds.calls.append(list(args))
            return subprocess.CompletedProcess(args, 1, "", "Failed to connect to bus")
        return real(args)
    rc, out = world.run("--apply", run_cmd=flaky, capsys=capsys)
    assert rc == 2 and "timers left STOPPED" in out
    assert "DRY_RUN UNKNOWN" in out and "DRY_RUN=0 LOADED" not in out \
        and "DRY_RUN=1 LOADED" not in out, out


def run_deps_script(world, tmp_path):
    """Run the dependency step's script as this user (the `sudo -u quantt`
    prefix is what makes it quantt's on the VM), with a stub uv."""
    uv = world.layout.home / ".uv" / "bin" / "uv"
    uv.parent.mkdir(parents=True, exist_ok=True)
    uv.write_text("#!/bin/sh\nexit 0\n")
    os.chmod(uv, 0o755)
    return subprocess.run(["bash", "-c", iv.deps_script(world.layout)], capture_output=True,
                          text=True, env=dict(os.environ, HOME=str(world.layout.home)))


def test_the_deps_command_hashes_as_quantt_and_writes_through_no_pipe():
    lay = iv.Layout(Path("/home/quantt"))
    cmd = iv.deps_command(lay)
    assert cmd.startswith("sudo -u quantt env HOME=/home/quantt bash -c ")
    assert "| sudo" not in cmd and "tee" not in cmd           # nothing hashed as azureuser
    script = iv.deps_script(lay)
    assert "set -euo pipefail" in script and "--no-build" in script


def test_the_deps_script_records_the_hash_when_it_succeeds(world, tmp_path):
    rec = world.layout.requirements_record
    rec.write_text("old\n")
    r = run_deps_script(world, tmp_path)
    assert r.returncode == 0, r.stderr
    want = hashlib.sha256((world.layout.prod_dir / "requirements.txt").read_bytes()).hexdigest()
    assert rec.read_text() == want + "\n"


def test_the_deps_script_never_truncates_the_record_when_the_hash_fails(world, tmp_path):
    rec = world.layout.requirements_record
    rec.write_text("old-record\n")
    req = world.layout.prod_dir / "requirements.txt"
    os.chmod(req, 0)                                          # unreadable: sha256sum fails
    try:
        r = run_deps_script(world, tmp_path)
    finally:
        os.chmod(req, 0o644)
    assert r.returncode != 0
    assert rec.read_text() == "old-record\n"


def test_a_restart_before_the_send_window_goes_ahead(world, capsys):
    """15:30-15:52 can only replay a :00/:30 session slot (decide or idle) or a
    :40 collect, never a send, so the restart is allowed."""
    armed_and_running(world, capsys)
    times = iter([et(15, 29, 50)])

    def clock():
        return next(times, et(15, 51, 59))
    rc, out = world.run("--apply", "--armed", clock=clock, capsys=capsys)
    assert rc == 0, out
    assert world.cmds.timer_active == set(TIMERS)


# -- one install at a time (release-check #5) ---------------------------------------

def hold_lock(world, pid="4242"):
    path = world.layout.sysroot / iv.INSTALL_LOCK.relative_to("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.ftruncate(fd, 0)
    os.write(fd, f"{pid}\n".encode())
    return fd


def lock_is_free(world):
    path = world.layout.sysroot / iv.INSTALL_LOCK.relative_to("/")
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False
    finally:
        os.close(fd)


def test_a_second_install_refuses_before_touching_anything(world, capsys):
    """The race: a disarm confirmed DRY_RUN=1 and exited 0 while an armed update
    was still running, which then wrote DRY_RUN=0 and restarted the timers."""
    head = world.head()
    fd = hold_lock(world)
    try:
        rc, out = world.run("--apply", capsys=capsys)
    finally:
        os.close(fd)
    assert rc == 2 and "another install" in out and "4242" in out, out
    assert world.cmds.calls == [] and world.head() == head and units_written(world) == []


def test_the_dry_run_takes_the_lock_too(world, capsys):
    fd = hold_lock(world)
    try:
        rc, out = world.run(capsys=capsys)
    finally:
        os.close(fd)
    assert rc == 2 and "another install" in out


def test_the_lock_is_released_on_success_refusal_and_exception(world, capsys):
    assert world.run("--apply", capsys=capsys)[0] == 0
    assert lock_is_free(world)
    assert world.run("--apply", euid=1000, capsys=capsys)[0] == 2      # refused
    assert lock_is_free(world)
    armed_and_running(world, capsys)
    world.cmds.raise_on = {("systemctl", "daemon-reload"): RuntimeError("boom")}
    with pytest.raises(RuntimeError):
        world.run("--apply", capsys=capsys)
    assert lock_is_free(world)


def test_the_bootstrap_takes_the_same_lock():
    assert _sh_var("LOCK_FILE") == str(iv.INSTALL_LOCK)


# -- a halt during an install (release-check #5, own pass) --------------------------

@pytest.mark.parametrize("extra", [(), ("--enable",)])
def test_a_timer_disabled_during_the_install_is_not_started_or_re_enabled(world, capsys, extra):
    """Halt step 4 (`systemctl disable --now` the timers) issued while an install
    runs must not be undone by the install's restart, nor by --enable."""
    armed_and_running(world, capsys)
    real = world.cmds.__call__

    def halting(args):
        if args[:2] == ["systemctl", "daemon-reload"]:
            world.cmds.enabled.discard("quantt-cef-session.timer")   # the operator's disable
        return real(args)
    rc, out = world.run("--apply", "--armed", *extra, run_cmd=halting, capsys=capsys)
    assert rc == 2 and "disabled during this install" in out, out
    assert "quantt-cef-session.timer" not in world.cmds.timer_active
    assert not [c for c in world.cmds.mutating() if c[:3] == ["systemctl", "enable", "--now"]]


def test_the_key_service_being_active_is_normal(world, capsys):
    world.cmds.active[iv.SECRET_UNIT] = "active"
    assert world.run("--apply", capsys=capsys)[0] == 0


# -- data ------------------------------------------------------------------------

def test_seed_copies_the_laptop_panels_once_and_records_provenance(world, capsys):
    world.run("--apply", capsys=capsys)
    data = world.layout.prod_dir / "data" / "cef"
    names = ip.SEED_FILES + ip.SEED_SUPPORT
    assert sorted(p.name for p in data.iterdir()) == sorted(names)
    for n in names:
        assert not (data / n).is_symlink()
        assert (data / n).read_bytes() == (world.seed / n).read_bytes()
    log = world.layout.seed_log.read_text().splitlines()
    assert len(log) == len(names)
    assert all("sha256=" in line and str(world.seed) in line and "release=v1" in line
               for line in log)
    assert git("status", "--porcelain", cwd=world.layout.prod_dir) == ""


def test_update_moves_to_the_new_tag_and_keeps_prods_panels(world, capsys):
    world.run("--apply", capsys=capsys)
    panel = world.layout.prod_dir / "data" / "cef" / ip.SEED_FILES[0]
    panel.write_bytes(b"prod appended newer rows")
    world.commit_and_tag("v2", lambda d: (d / "ops/halt.py").write_text("# v2\n"))
    rc, out = world.run("--apply", tag="v2", seed=False, capsys=capsys)
    assert rc == 0, out
    assert world.head() == world.tag_commit("v2")
    assert panel.read_bytes() == b"prod appended newer rows"
    assert "leave " in out


def test_missing_panels_without_seed_dir_is_refused(world, capsys):
    rc, out = world.run("--apply", seed=False, capsys=capsys)
    assert rc == 2 and "--seed-from" in out
    assert not world.layout.units_dir.exists()


# -- refusals ----------------------------------------------------------------------

@pytest.mark.parametrize("zone", ["UTC", "America/Toronto", "America/Chicago"])
def test_any_zone_but_new_york_is_refused(world, capsys, zone):
    world.set_tz(zone)
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and zone in out and "timedatectl" in out
    assert not world.layout.units_dir.exists()


def test_not_root_is_refused(world, capsys):
    rc, out = world.run("--apply", euid=1000, capsys=capsys)
    assert rc == 2 and "root" in out


def test_without_dash_B_is_refused(world, capsys):
    rc, out = world.run("--apply", dont_write_bytecode=False, capsys=capsys)
    assert rc == 2 and "-B" in out


@pytest.mark.parametrize("vault", ["evil.example/x", "a--b", "x"])
def test_bad_vault_name_is_refused(world, capsys, vault):
    rc, out = world.run("--apply", vault=vault, capsys=capsys)
    assert rc == 2 and "not a Key Vault name" in out
    assert not world.layout.units_dir.exists()


def test_vault_is_required(world, capsys):
    with pytest.raises(SystemExit):
        iv.main(["--tag", "v1"])


def test_missing_clone_is_refused(world, capsys):
    import shutil
    shutil.rmtree(world.layout.prod_dir)
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "bootstrap.sh" in out


@pytest.mark.parametrize("dirty", ["modified", "untracked"])
def test_dirty_clone_is_refused(world, capsys, dirty):
    prod = world.layout.prod_dir
    if dirty == "modified":
        (prod / "ops/halt.py").write_text("# hand edit in prod\n")
    else:
        (prod / "ops/stray.txt").write_text("x")
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "local modifications" in out


def test_clone_of_another_origin_is_refused(world, capsys):
    git("remote", "set-url", "origin", "/elsewhere.git", cwd=world.layout.prod_dir)
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "not of" in out


def test_a_clone_on_the_second_spelling_installs_and_reads_its_tag_there(world, capsys):
    """The repository went private (team lead, 2026-11-24), and the VM's clone moves from the
    https spelling to the ssh one, read with a deploy key. The installer must accept the second
    spelling AND read the tag from it. Reading the first spelling would fail once anonymous
    https reads stop. Here the first accepted spelling names nothing, so only a read from the
    clone's own origin can succeed. A moved tag is read there too (v2 below)."""
    nowhere = str(world.layout.prod_dir.parent / "no-such-https-spelling.git")
    spellings = (nowhere, str(world.origin))
    rc, out = world.run("--apply", origin_url=spellings, capsys=capsys)
    assert rc == 0, out
    assert f"(origin {world.origin})" in out
    world.commit_and_tag("v2", lambda d: (d / "ops/halt.py").write_text("# v2\n"))
    rc, out = world.run("--apply", tag="v2", origin_url=spellings, capsys=capsys)
    assert rc == 0, out
    assert world.head() == world.tag_commit("v2")


def test_a_clone_on_neither_spelling_is_refused_naming_both(world, capsys):
    git("remote", "set-url", "origin", "/elsewhere.git", cwd=world.layout.prod_dir)
    rc, out = world.run(origin_url=("/https-spelling.git", "/ssh-spelling.git"), capsys=capsys)
    assert rc == 2
    assert "'/https-spelling.git' or '/ssh-spelling.git'" in out


def test_the_accepted_spellings_name_one_repository():
    """https and ssh spellings of the same owner/name, and nothing else: accepting a second
    repository would let prod install a tag from code the team lead never released."""
    assert iv.ORIGIN_URLS == (iv.ORIGIN_URL, iv.ORIGIN_URL_SSH)
    https = iv.ORIGIN_URL.removeprefix("https://github.com/")
    ssh = iv.ORIGIN_URL_SSH.removeprefix("git@github.com:")
    assert https == ssh == "quanttqueensu/CreditTrading.git"
    assert inspect.signature(iv.main).parameters["origin_url"].default == iv.ORIGIN_URLS


def test_tag_not_on_origin_is_refused(world, capsys):
    world.commit_and_tag("v2", lambda d: (d / "ops/halt.py").write_text("# v2\n"), push=False)
    rc, out = world.run("--apply", tag="v2", capsys=capsys)
    assert rc == 2 and "not on origin" in out


def test_tag_that_moved_on_origin_is_refused(world, capsys):
    (world.dev / "ops/halt.py").write_text("# moved\n")
    git("commit", "-qam", "moved", cwd=world.dev)
    git("tag", "-f", "-a", "v1", "-m", "moved", cwd=world.dev)
    git("push", "-q", "-f", "origin", "main", "v1", cwd=world.dev)
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2
    assert world.head() != world.tag_commit("v1")


def test_systemd_rejecting_a_calendar_line_stops_the_install(world, capsys):
    world.cmds.fail = {("systemd-analyze", "calendar"): 1}
    rc, out = world.run("--apply", capsys=capsys)
    assert rc == 2 and "systemd-analyze rejects" in out
    assert not world.layout.units_dir.exists()


EDITS = {
    "persistent": ("quantt-cef-session.timer", "\nPersistent=false\n", "\nPersistent=true\n"),
    "schedule": ("quantt-cef-session.timer", "15:52:00", "15:53:00"),
    "requires": ("quantt-cef-session.service", "Wants=quantt-secret.service",
                 "Requires=quantt-secret.service"),
    "extra_exec": ("quantt-cef-session.service", "SuccessExitStatus=",
                   "ExecStartPre=/bin/true\nSuccessExitStatus="),
    "dry_run_literal": ("quantt-cef-verify.service", "DRY_RUN=${DRY_RUN}", "DRY_RUN=0"),
    "zone_suffix": ("quantt-cef-verify.timer", "17:30:00", "17:30:00 UTC"),
}


@pytest.mark.parametrize("edit", sorted(EDITS))
def test_a_template_edited_at_the_tag_is_refused(world, capsys, edit):
    unit, old, new = EDITS[edit]
    rel = iv.template_path(unit)

    def change(d):
        t = (d / rel).read_text()
        assert old in t
        (d / rel).write_text(t.replace(old, new, 1))
    world.commit_and_tag("v2", change)
    (world.dev / rel).write_text((REAL_REPO / rel).read_text())   # tree restored, tag not
    rc, out = world.run("--apply", tag="v2", capsys=capsys)
    assert rc == 2 and "fails its checks" in out, out
    assert not world.layout.units_dir.exists()


# -- rendering ---------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["a b", "50%", "$HOME", "a\"b", "a\\b", "x\ny"])
def test_values_a_unit_file_would_misread_are_refused(bad):
    with pytest.raises(iv.InstallRefused, match="misread"):
        iv.render("X=${A}\n", {"A": bad}, "t.service")


def test_missing_placeholder_value_raises():
    with pytest.raises(iv.InstallRefused, match="VAULT"):
        iv.render("X=${VAULT}\n", {"A": "b"}, "t.service")


def test_line_continuations_and_repeated_sections_are_refused():
    with pytest.raises(iv.InstallRefused, match="continuation"):
        iv.parse_unit("[Service]\nExecStart=/bin/a \\\n  --b\n", "t")
    with pytest.raises(iv.InstallRefused, match="repeated"):
        iv.parse_unit("[Service]\nType=oneshot\n[Service]\nUser=x\n", "t")


# -- import hygiene ------------------------------------------------------------------

def test_installer_has_no_broker_session_or_http_import():
    import ast
    tree = ast.parse(Path(iv.__file__).read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add(n.module or "")
    assert not {m for m in mods if m.startswith(("quantt.session", "quantt.broker",
                                                 "requests", "dotenv", "src"))}


# -- bootstrap.sh ----------------------------------------------------------------------

BOOTSTRAP = REAL_REPO / "quantt" / "deploy" / "vm" / "bootstrap.sh"


def _sh_var(name):
    m = re.search(rf'^{name}="([^"]*)"', BOOTSTRAP.read_text(), re.M)
    assert m, name
    return m.group(1)


def test_bootstrap_parses():
    r = subprocess.run(["bash", "-n", str(BOOTSTRAP)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_bootstrap_builds_the_layout_the_installer_expects():
    home = Path(_sh_var("HOME_DIR").replace("${SVC_USER}", _sh_var("SVC_USER")))
    lay = iv.Layout(home)
    assert _sh_var("SVC_USER") == iv.SERVICE_USER
    assert home == Path("/home") / iv.SERVICE_USER
    assert _sh_var("PROD").replace("${HOME_DIR}", str(home)) == str(lay.prod_dir)
    assert Path(_sh_var("VENV").replace("${HOME_DIR}", str(home))) / "bin" / "python" \
        == lay.venv_python
    assert _sh_var("ORIGIN") == iv.ORIGIN_URL_SSH          # the repository is private (RUNBOOK 8.14)
    assert _sh_var("TZ_NAME") == iv.REQUIRED_TZ


def test_bootstrap_never_reboots_pins_uv_and_never_pipes_to_a_shell():
    text = BOOTSTRAP.read_text()
    assert 'Unattended-Upgrade::Automatic-Reboot "false";' in text
    assert re.fullmatch(r"\d+\.\d+\.\d+", _sh_var("UV_VERSION"))
    assert _sh_var("PY_VERSION") == "3.13.5"
    assert _sh_var("SWAP_SIZE") == "2G"
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert not re.search(r"\|\s*(sudo\s+)?(ba)?sh\b", code)


# -- bootstrap.sh, run for real with stubs (review 2026-10-07, findings 5, 7, 8) -------

def bootstrap_fn(snippet: str, cwd: Path) -> subprocess.CompletedProcess:
    """Source bootstrap.sh (which then defines its steps without running them),
    stub `as_quantt` to run as this user, and run `snippet`."""
    script = f"""set -euo pipefail
source {str(BOOTSTRAP)!r}
as_quantt() {{ "$@"; }}
{snippet}
"""
    return subprocess.run(["bash", "-c", script], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def tagged_origin(tmp_path):
    """A bare origin with v1 and a later v2, and a clone detached at v1."""
    src = tmp_path / "src"
    src.mkdir()
    git("init", "-q", "-b", "main", cwd=src)
    (src / "f").write_text("1")
    git("add", "-A", cwd=src)
    git("commit", "-q", "-m", "1", cwd=src)
    git("tag", "-a", "v1", "-m", "v1", cwd=src)
    (src / "f").write_text("2")
    git("commit", "-qam", "2", cwd=src)
    git("tag", "-a", "v2", "-m", "v2", cwd=src)
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(src), str(origin)], check=True,
                   capture_output=True)
    prod = tmp_path / "home" / "prod" / "quantt-alpaca"
    prod.parent.mkdir(parents=True)
    git("clone", "-q", str(origin), str(prod), cwd=tmp_path)
    git("checkout", "-q", "--detach", "refs/tags/v1", cwd=prod)
    return origin, prod, src


def test_bootstrap_does_nothing_when_sourced(tmp_path):
    r = bootstrap_fn("echo sourced-ok", tmp_path)
    assert r.returncode == 0 and r.stdout.strip() == "sourced-ok", r.stderr


def test_bootstrap_refuses_to_move_an_existing_clone_to_another_tag(tagged_origin, tmp_path):
    """Moving prod between tags is install_vm's job, with its checks."""
    origin, prod, src = tagged_origin
    r = bootstrap_fn(f"ORIGIN={str(origin)!r}; PROD={str(prod)!r}; TAG=v2; step_clone", tmp_path)
    assert r.returncode == 2 and "install_vm" in r.stderr, (r.stdout, r.stderr)
    assert git("rev-parse", "HEAD", cwd=prod) == git("rev-parse", "v1^{commit}", cwd=src)


def test_bootstrap_rerun_at_the_same_tag_leaves_the_clone_alone(tagged_origin, tmp_path):
    origin, prod, src = tagged_origin
    r = bootstrap_fn(f"ORIGIN={str(origin)!r}; PROD={str(prod)!r}; TAG=v1; step_clone", tmp_path)
    assert r.returncode == 0, r.stderr
    assert git("rev-parse", "HEAD", cwd=prod) == git("rev-parse", "v1^{commit}", cwd=src)


def test_bootstrap_clones_fresh_at_the_tag(tagged_origin, tmp_path):
    origin, _, src = tagged_origin
    fresh = tmp_path / "new" / "prod" / "quantt-alpaca"
    r = bootstrap_fn(f"ORIGIN={str(origin)!r}; PROD={str(fresh)!r}; TAG=v2; step_clone", tmp_path)
    assert r.returncode == 0, r.stderr
    assert git("rev-parse", "HEAD", cwd=fresh) == git("rev-parse", "v2^{commit}", cwd=src)


def test_bootstrap_installs_wheels_only_and_loudly(tmp_path):
    """A source build on a 1 GiB VM would thrash or be killed. It must fail
    instead, and the failure must be visible."""
    rec = tmp_path / "uv-args"
    stub = tmp_path / "uv"
    stub.write_text(f"#!/bin/sh\necho \"$@\" >> {rec}\n")
    os.chmod(stub, 0o755)
    venv, prod = tmp_path / "v", tmp_path / "p"
    venv.mkdir()
    prod.mkdir()
    (prod / "requirements.txt").write_text("x==1\n")
    r = bootstrap_fn(f"UV={str(stub)!r}; VENV={str(venv)!r}; PROD={str(prod)!r}; TAG=t; "
                     f"step_requirements", tmp_path)
    assert r.returncode == 0, r.stderr
    args = rec.read_text().split()
    assert args[:2] == ["pip", "install"] and "--no-build" in args and "--quiet" not in args
    assert args[args.index("--python") + 1] == f"{venv}/bin/python"
    assert "--only-binary=:all:" in BOOTSTRAP.read_text()       # the pip that installs uv


def test_bootstrap_keeps_both_apt_timers_out_of_the_job_windows(tmp_path):
    root = tmp_path / "root"
    r = bootstrap_fn(f"ROOT={str(root)!r}; systemctl() {{ :; }}; step_apt", tmp_path)
    assert r.returncode == 0, r.stderr
    for timer in ("apt-daily.timer", "apt-daily-upgrade.timer"):
        conf = (root / f"etc/systemd/system/{timer}.d/quantt.conf").read_text()
        assert "OnCalendar=\nOnCalendar=*-*-* 02:00\n" in conf, timer
        assert "RandomizedDelaySec=30m" in conf and "Persistent=false" in conf, timer
    assert 'Automatic-Reboot "false"' in (root / "etc/apt/apt.conf.d/52quantt").read_text()


def test_bootstrap_records_the_requirements_it_installed(tmp_path):
    rec = tmp_path / "uv-args"
    stub = tmp_path / "uv"
    stub.write_text(f"#!/bin/sh\necho \"$@\" >> {rec}\n")
    os.chmod(stub, 0o755)
    venv, prod = tmp_path / "venv", tmp_path / "prod"
    venv.mkdir()
    prod.mkdir()
    (prod / "requirements.txt").write_text("pandas==2.3.3\n")
    r = bootstrap_fn(f"UV={str(stub)!r}; VENV={str(venv)!r}; PROD={str(prod)!r}; TAG=t; "
                     f"step_requirements", tmp_path)
    assert r.returncode == 0, r.stderr
    want = hashlib.sha256(b"pandas==2.3.3\n").hexdigest()
    assert (venv / iv.REQUIREMENTS_RECORD).read_text().strip() == want
    assert iv.Layout(Path("/home/quantt")).requirements_record == \
        Path("/home/quantt/venv") / iv.REQUIREMENTS_RECORD


def flock_path(tmp_path):
    """A PATH with util-linux `flock`, or (absent, as on macOS) a stand-in with
    the same semantics for `flock -n FD`: flock(2) on the inherited descriptor,
    whose open file description the calling shell keeps holding after the
    child exits."""
    if shutil.which("flock"):
        return os.environ["PATH"]
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "flock"
    stub.write_text(f"#!{sys.executable}\nimport fcntl, sys\nassert sys.argv[1] == '-n'\n"
                    f"try:\n    fcntl.flock(int(sys.argv[2]), fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                    f"except BlockingIOError:\n    sys.exit(1)\n")
    os.chmod(stub, 0o755)
    return f"{bindir}:{os.environ['PATH']}"


def bootstrap_locked(snippet, tmp_path):
    script = f"""set -euo pipefail
source {str(BOOTSTRAP)!r}
as_quantt() {{ "$@"; }}
ROOT={str(tmp_path / 'root')!r}
{snippet}
"""
    return subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True,
                          env=dict(os.environ, PATH=flock_path(tmp_path)))


def test_bootstrap_refuses_while_an_install_holds_the_lock(tmp_path):
    path = tmp_path / "root" / "run" / "lock" / "quantt-install.lock"
    path.parent.mkdir(parents=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.write(fd, b"4242\n")
    try:
        r = bootstrap_locked("step_lock", tmp_path)
    finally:
        os.close(fd)
    assert r.returncode == 2 and "another install" in r.stderr and "4242" in r.stderr, r.stderr


def test_bootstrap_takes_the_lock_and_records_its_pid(tmp_path):
    r = bootstrap_locked('step_lock; cat "${ROOT}${LOCK_FILE}"', tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().isdigit()


@pytest.mark.parametrize("live,want", [
    ('[[ "$1" == is-active && "$3" == quantt-cef-session.timer ]] && return 0; '
     '[[ "$1" == is-active ]] && return 3; return 0', 2),
    ('[[ "$1" == is-active ]] && return 3; '
     '[[ "$1" == list-jobs ]] && echo "77 quantt-cef-verify.service start waiting"; return 0', 2),
    ('[[ "$1" == is-active ]] && return 3; return 0', 0),
])
def test_bootstrap_refuses_on_a_live_vm(tmp_path, live, want):
    """Re-running bootstrap reinstalls packages into the venv; never under a
    running or queued job, and never with the timers running."""
    r = bootstrap_fn(f"systemctl() {{ {live}; }}; step_not_live", tmp_path)
    assert r.returncode == want, (r.stdout, r.stderr)
    if want:
        assert "live" in r.stderr


def test_halt_advice_names_the_per_day_approval_as_well_as_auto_armed():
    """release-check #8: on the cut-over day the VM sends from <D>/APPROVED with no
    AUTO_ARMED (RUNBOOK 8.5), so "remove AUTO_ARMED" alone halts nothing. Every
    halt instruction the installer prints must name the halt file first and the
    unsent day's APPROVED next to AUTO_ARMED."""
    advice = iv.HALT_ADVICE
    assert "ops/HALT.md" in advice
    assert "AUTO_ARMED" in advice and "APPROVED" in advice
    src = Path(iv.__file__).read_text()
    assert "remove AUTO_ARMED)" not in src, "a halt message still names AUTO_ARMED alone"



def test_the_deps_script_changes_to_the_service_home_before_uv_runs():
    """Measured on the VM, 2026-10-08: uv reads uv.toml from the working
    directory, and run from the admin's home (mode 750 to quantt) it failed
    "failed to open file /home/azureuser/uv.toml: Permission denied". The script
    must cd into the service user's own home before it calls uv."""
    script = iv.deps_script(iv.Layout(Path("/home/quantt")))
    before_uv = script.split("pip install")[0]
    assert "cd /home/quantt;" in before_uv, script
