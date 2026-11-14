"""`install_vm --reports`: the report-only units, and proof they change nothing else.

The team lead's ruling of 2026-11-08 gives the nightly data QA and risk report to VM
timers. The contract the installer must keep: the new units are checked as hard as
every other (clean clone, templates at the tag, drop-in scan, nothing busy, loaded as
written); they carry no broker key file and no panel lock; an install of them touches
no book's unit; and with report units on the machine, a book install neither refuses nor
disarms because of them. The core's and C4's plans are compared against origin/main's
installer (a5b94c8), read from git, byte for byte: every rendered unit and step.

Hermetic: test_install_vm's fake VM. Fails on origin/main: no `--reports`.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys

import pytest

from quantt.deploy import install_vm as iv
from quantt.deploy.tests.test_install_vm import REAL_REPO, git
from quantt.deploy.tests.test_install_vm_books import C4World, EOD, _run_with, _unit_bytes

BASE = "a5b94c8"          # origin/main when this mode was added: the book installs must equal it
SESSION_UNITS = ("quantt-cef-session", "quantt-cef-verify", "quantt-cef-collect", "quantt-secret",
                 "quantt-c4-session", "quantt-c4-verify", "quantt-c4-collect", "quantt-c4-secret")


class ReportsWorld(C4World):
    """The C4 world with the report units' files at the tag too."""

    def _make_repo(self):
        d = self.dev
        d.mkdir()
        git("init", "-q", "-b", "main", cwd=d)
        (d / ".gitignore").write_text("/data/\n__pycache__/\n")
        for rel in dict.fromkeys(iv.C4_VM.required_at_tag + iv.REPORT_VM.required_at_tag):
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            if rel.startswith(iv.TEMPLATE_DIR):
                (d / rel).write_text((REAL_REPO / rel).read_text())
            else:
                (d / rel).write_text(f"# stub {rel}\n")
        git("add", "-A", cwd=d)
        git("commit", "-q", "-m", "v1", cwd=d)
        git("tag", "-a", "v1", "-m", "release v1", cwd=d)
        subprocess.run(["git", "clone", "-q", "--bare", str(d), str(self.origin)], check=True, capture_output=True)
        git("remote", "add", "origin", str(self.origin), cwd=d)

    def reports(self, *extra, capsys=None, **kw):
        return self.run("--reports", *extra, seed=False, capsys=capsys, **kw)


@pytest.fixture
def rw(tmp_path):
    return ReportsWorld(tmp_path)


def _mutating_calls(rw):
    return [c for c in rw.cmds.calls if c[:1] == ["systemctl"] and c[1] in ("stop", "start", "enable", "disable", "restart")]


def test_reports_dry_run_renders_every_unit_and_writes_nothing(rw, capsys):
    rc, out = rw.reports(capsys=capsys)
    assert rc == 0, out
    for f in iv.REPORT_UNIT_FILES:
        assert f"{rw.layout.unit_path(f)} (rendered, not written)" in out
    assert not rw.layout.units_dir.exists() or not list(rw.layout.units_dir.iterdir())
    assert "alert-smtp-pass" in out and "team lead" in out           # the warning names the TL's step


def test_reports_apply_writes_units_as_contracted(rw, capsys):
    rc, out = rw.reports("--apply", capsys=capsys)
    assert rc == 0, out
    assert set(p.name for p in rw.layout.units_dir.iterdir()) == set(iv.REPORT_UNIT_FILES)
    for job in iv.REPORT_JOBS:
        memmax = iv.REPORT_PNL_MEMORY_MAX if job.unit.endswith("pnl") else iv.REPORT_MEMORY_MAX
        text = rw.layout.unit_path(job.service).read_text()
        body = "\n".join(ln for ln in text.splitlines() if not ln.startswith("#"))
        assert f"MemoryMax={memmax}" in body and "TimeoutStartSec=480" in body and "Nice=10" in body
        assert f"ReadOnlyPaths={rw.layout.prod_dir}" in body
        assert "QUANTT_ENV_FILE" not in body and "alpaca.env" not in body and "DRY_RUN" not in body
        book = job.unit.split("-")[1]
        assert f"QUANTT_STATE_DIR={rw.layout.state_root / book}" in body
        assert f"--book {book}" in body
        assert ("EnvironmentFile=-/run/quantt-reports/alert.env" in body) == job.unit.endswith("risk")
    for p in ("cef", "c4"):
        assert (rw.layout.state_root / p / "reports").is_dir() and (rw.layout.state_root / p / "logs").is_dir()
    timer = rw.layout.unit_path("quantt-cef-dataqa.timer").read_text()
    assert "OnCalendar=Mon,Tue,Wed,Thu,Fri *-*-* 21:45:00" in timer


def test_report_schedule_is_clear_of_every_runner_slot():
    """Session :00/:30, collect :10/:40, verify 17:30, send 15:52/15:55/12:52/12:55.
    The pnl kind's times are the runner owner's (team lead, 2026-11-09: 20:30 and 20:35):
    20:30 is the session timer's idle tick, which decides nothing at that hour, so the
    pnl kind has its own test below; this grid still holds for every other kind."""
    busy = {(h, m) for h in range(24) for m in (0, 10, 30, 40)} | {(17, 30), (15, 52), (15, 55), (12, 52), (12, 55)}
    other = {k: v for k, v in iv.REPORT_SCHEDULE.items() if k[0] != "pnl"}
    times = list(other.values())
    assert not (set(times) & busy) and len(set(times)) == len(times)
    for (kind, book), (h, m) in other.items():
        before_decide = (h, m) < (22, 0)
        assert before_decide == (kind == "dataqa"), (kind, book)
        end_min = h * 60 + m + iv.REPORT_TIMEOUT_S / 60
        assert end_min < 22 * 60 or (kind == "risk" and end_min < 22 * 60 + 30), (kind, book)


def test_reports_touch_no_books_unit(rw, capsys):
    rc, _ = rw.reports("--apply", "--enable", capsys=capsys)
    assert rc == 0
    for c in _mutating_calls(rw):
        assert not any(u in " ".join(c) for u in SESSION_UNITS), c
    assert "--now" in " ".join(sum((c for c in _mutating_calls(rw) if c[1] == "enable"), []))
    # the units read back as loaded; a failed report fetch would still leave the timers armed by systemd
    assert rw.cmds.timer_active >= {j.timer for j in iv.REPORT_JOBS}


def test_a_failed_report_step_reports_only_report_timers_stopped(rw, capsys):
    assert rw.reports("--apply", "--enable", capsys=capsys)[0] == 0
    rw.cmds.fail[("systemctl", "daemon-reload")] = 1
    rc, out = rw.reports("--apply", capsys=capsys)
    assert rc == 2 and "REFUSED at step" in out and "No session timer was touched" in out
    for c in _mutating_calls(rw):
        assert not any(u in " ".join(c) for u in SESSION_UNITS), c


# ------------------------------------------------------------------ refusals

def test_reports_refuses_a_dirty_clone(rw, capsys):
    (rw.layout.prod_dir / "stray.txt").write_text("x")
    rc, out = rw.reports("--apply", capsys=capsys)
    assert rc == 2 and "local modifications" in out and not list((rw.layout.units_dir).glob("*.service"))


def test_reports_refuses_a_clone_not_at_the_tag(rw, capsys):
    rw.commit_and_tag("v2", lambda d: (d / "x.txt").write_text("x"))
    rc, out = rw.run("--reports", tag="v2", seed=False, capsys=capsys)
    assert rc == 2 and "install the core at v2 first" in out


def test_reports_refuses_a_tag_without_the_files(rw, capsys):
    git("rm", "-q", "scripts/ops/data_qa.py", cwd=rw.dev)
    git("commit", "-q", "-m", "no qa", cwd=rw.dev)
    git("tag", "-a", "v3", "-m", "v3", cwd=rw.dev)
    git("push", "-q", "origin", "main", "v3", cwd=rw.dev)
    git("fetch", "-q", "--tags", "origin", cwd=rw.layout.prod_dir)
    git("checkout", "-q", "--detach", "refs/tags/v3", cwd=rw.layout.prod_dir)
    rc, out = rw.run("--reports", tag="v3", seed=False, capsys=capsys)
    assert rc == 2 and "scripts/ops/data_qa.py" in out


def test_reports_refuses_a_dropin_on_a_report_unit(rw, capsys):
    d = rw.layout.units_dir / "quantt-cef-risk.service.d"
    d.mkdir(parents=True)
    (d / "override.conf").write_text("[Service]\nEnvironment=X=1\n")
    rc, out = rw.reports("--apply", capsys=capsys)
    assert rc == 2 and "override.conf" in out


def test_reports_refuses_while_a_session_job_runs(rw, capsys):
    rw.cmds.active["quantt-cef-session.service"] = "active"
    rc, out = rw.reports("--apply", capsys=capsys)
    assert rc == 2 and "quantt-cef-session.service" in out


def test_reports_flag_takes_no_book_options(rw, capsys):
    with pytest.raises(SystemExit):
        rw.run("--reports", "--book", "c4", seed=False, capsys=capsys)


# ------------------------------------------------------------------ the books' installs, with report units present

def test_a_book_install_refuses_only_at_planning_while_a_report_job_runs(rw, capsys):
    assert rw.reports("--apply", capsys=capsys)[0] == 0
    rw.cmds.active["quantt-cef-dataqa.service"] = "active"
    rc, out = rw.run("--apply", capsys=capsys)
    assert rc == 2 and "quantt-cef-dataqa.service" in out and "report job" in out
    rw.cmds.active.pop("quantt-cef-dataqa.service")
    assert rw.run("--apply", capsys=capsys)[0] == 0


def test_a_report_job_starting_mid_install_cannot_fail_the_book_install(rw, capsys):
    assert rw.reports("--apply", capsys=capsys)[0] == 0
    rw.cmds.start_at_reload = ("quantt-cef-dataqa.service", "4242", {})
    rc, out = rw.run("--apply", capsys=capsys)
    assert rc == 0, out
    assert "ALERT" not in out


def test_c4_install_is_not_refused_by_report_unit_files_on_disk(rw, capsys):
    assert rw.reports("--apply", capsys=capsys)[0] == 0
    rc, out = rw.c4("--apply", capsys=capsys)
    assert rc == 0, out


def test_book_installs_touch_no_report_unit(rw, capsys):
    assert rw.reports("--apply", "--enable", capsys=capsys)[0] == 0
    before = _unit_bytes(rw, iv.REPORT_UNIT_FILES)
    rw.cmds.calls.clear()
    assert rw.run("--apply", capsys=capsys)[0] == 0
    assert rw.c4("--apply", capsys=capsys)[0] == 0
    assert _unit_bytes(rw, iv.REPORT_UNIT_FILES) == before
    for c in _mutating_calls(rw):
        assert not any("dataqa" in x or "risk" in x or "reports" in x for x in c), c


def _load_base(tmp_path, monkeypatch):
    blob = subprocess.run(["git", "-C", str(REAL_REPO), "show", f"{BASE}:quantt/deploy/install_vm.py"],
                          capture_output=True, text=True)
    assert blob.returncode == 0, f"cannot read {BASE}'s installer from git: {blob.stderr}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "install_vm_base.py"
    path.write_text(blob.stdout)
    spec = importlib.util.spec_from_file_location("install_vm_base", path)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, mod)      # dataclasses look their module up there
    spec.loader.exec_module(mod)
    return mod


def test_the_books_rendered_units_are_byte_identical_to_origin_mains(tmp_path, monkeypatch, capsys):
    base = _load_base(tmp_path / "b", monkeypatch)
    w = C4World(tmp_path / "w")
    core_argv = ["--tag", "v1", "--vault", "example-vault-x1", "--seed-from", str(w.seed)]
    rc_b, out_b = _run_with(base, w, core_argv, capsys)
    rc_n, out_n = _run_with(iv, w, core_argv, capsys)
    assert rc_b == rc_n == 0 and out_b == out_n
    assert _run_with(base, w, core_argv + ["--apply"], capsys)[0] == 0
    core_b = _unit_bytes(w, iv.ALL_UNIT_FILES)
    assert _run_with(iv, w, core_argv + ["--apply"], capsys)[0] == 0
    assert _unit_bytes(w, iv.ALL_UNIT_FILES) == core_b
    c4_argv = ["--tag", "v1", "--vault", "example-vault-x1", "--book", "c4", "--eod-from", EOD,
               "--seed-from", str(w.c4_seed)]
    rc_b, out_b = _run_with(base, w, c4_argv, capsys)
    rc_n, out_n = _run_with(iv, w, c4_argv, capsys)
    assert rc_b == rc_n == 0 and out_b == out_n
    assert _run_with(base, w, c4_argv + ["--apply"], capsys)[0] == 0
    c4_b = _unit_bytes(w, iv.C4_VM.unit_files)
    assert _run_with(iv, w, c4_argv + ["--apply"], capsys)[0] == 0
    assert _unit_bytes(w, iv.C4_VM.unit_files) == c4_b


# ------------------------------------------------------------------ the pnl report kind (team lead, 2026-11-09)

def test_the_pnl_schedule_is_the_runner_owners():
    """Exactly the owner's times; after the 20:00 EOD stamp; clear of the real runner slots
    (the 21:40 collect, verify, the send windows, the 22:00 decide); no second report at
    the same minute. 20:30 is the session's idle half-hour tick, not a slot."""
    assert iv.REPORT_SCHEDULE[("pnl", "cef")] == (20, 30) and iv.REPORT_SCHEDULE[("pnl", "c4")] == (20, 35)
    times = list(iv.REPORT_SCHEDULE.values())
    assert len(set(times)) == len(times)
    slots = {(21, 40), (17, 30), (15, 52), (15, 55), (12, 52), (12, 55), (22, 0)}
    for book in ("cef", "c4"):
        h, m = iv.REPORT_SCHEDULE[("pnl", book)]
        assert (h, m) > (20, 0) and (h, m) not in slots
        assert h * 60 + m + iv.REPORT_TIMEOUT_S / 60 < 21 * 60 + 40        # done before the 21:40 collect


def test_the_pnl_job_needs_c4s_nav_map_at_the_tag():
    """`live_attribution.nav_symbols` reads the committed C4 NAV map; a tag without it would
    pass planning and then fail on every C4 run. Fails on the parent commit."""
    assert "results/cef/c4/c4_nav_symbols_2026-10-14.csv" in iv.REPORT_VM.required_at_tag


def test_the_pnl_units_read_only_their_own_book_key_file(rw, capsys):
    rc, out = rw.reports("--apply", capsys=capsys)
    assert rc == 0, out
    assert "alpaca-cef-key-id" in out and "alpaca-c4-key-id" in out       # the warning names the existing secrets
    for book, env in (("cef", "/run/quantt-reports-cef-pnl/broker.env"), ("c4", "/run/quantt-reports-c4-pnl/broker.env")):
        body = "\n".join(ln for ln in rw.layout.unit_path(f"quantt-{book}-pnl.service").read_text().splitlines()
                         if not ln.startswith("#"))
        key = iv.REPORT_PNL_KEY_UNITS[book]
        assert f"Wants={key}" in body and f"After={key}" in body and f"EnvironmentFile=-{env}" in body
        assert f"-m scripts.ops.pnl_report --book {book}" in body and f"QUANTT_STATE_DIR={rw.layout.state_root / book}" in body
        assert f"ReadOnlyPaths={rw.layout.prod_dir}" in body and "TimeoutStartSec=480" in body
        # the SMTP alert file and the runner's own key files are not this unit's
        assert "alert.env" not in body and "QUANTT_ENV_FILE" not in body and "/run/quantt/" not in body
        assert "DRY_RUN" not in body
        key_text = rw.layout.unit_path(key).read_text()
        other = "c4" if book == "cef" else "cef"
        assert f"alpaca-{book}-key-id=ALPACA_{book.upper()}_KEY_ID" in key_text
        assert f"alpaca-{other}-" not in key_text and "alert-smtp" not in key_text
        assert f"--out {env}" in key_text and f"RuntimeDirectory=quantt-reports-{book}-pnl" in key_text
        timer = rw.layout.unit_path(f"quantt-{book}-pnl.timer").read_text()
        h, m = iv.REPORT_SCHEDULE[("pnl", book)]
        assert f"OnCalendar=Mon,Tue,Wed,Thu,Fri *-*-* {h:02d}:{m:02d}:00" in timer


def test_the_pnl_key_services_cannot_write_the_clone(rw, capsys):
    """The key services run python from the prod clone. The job they serve uses -B and a
    read-only clone; these wrote .pyc files into it (review, 2026-11-09; gitignored, so the
    clean-clone check never said). Fails on the parent commit. The SMTP service is #65's and
    is untouched, and the books' own key services stay byte-identical (the pin above)."""
    rc, out = rw.reports("--apply", capsys=capsys)
    assert rc == 0, out
    for book in ("cef", "c4"):
        text = rw.layout.unit_path(iv.REPORT_PNL_KEY_UNITS[book]).read_text()
        body = [ln for ln in text.splitlines() if not ln.startswith("#")]
        assert "Environment=PYTHONDONTWRITEBYTECODE=1" in body
        assert f"ReadOnlyPaths={rw.layout.prod_dir}" in body
    smtp = rw.layout.unit_path(iv.REPORT_SECRET_UNIT).read_text()
    assert "ReadOnlyPaths" not in smtp and "PYTHONDONTWRITEBYTECODE" not in smtp


def test_the_pnl_units_let_a_non_zero_exit_fail_the_unit(rw, capsys):
    """Pin (passes before and after; team lead, 2026-11-10): pnl_report exits 5 on an
    UNRECONCILED report and 4 when incomplete, and nothing in the rendered pnl units may turn
    either into a success: no SuccessExitStatus, no ignored ExecStart, nothing run after it."""
    rc, out = rw.reports("--apply", capsys=capsys)
    assert rc == 0, out
    for book in ("cef", "c4"):
        body = [ln for ln in rw.layout.unit_path(f"quantt-{book}-pnl.service").read_text().splitlines()
                if not ln.startswith("#")]
        assert not [ln for ln in body if ln.startswith(("SuccessExitStatus", "RestartPreventExitStatus", "Restart",
                                                        "OnFailure", "ExecStartPost", "ExecStopPost"))], body
        execs = [ln for ln in body if ln.startswith("ExecStart")]
        assert len(execs) == 1 and execs[0].split("=", 1)[1][:1] not in "-@:+!", execs


def test_a_pnl_unit_that_would_hide_a_non_zero_exit_is_refused(rw, capsys):
    """Pin, the other side: a pnl template at the tag that adds SuccessExitStatus fails the
    installer's checks (expected_report_service admits none), so a 4 or a 5 cannot be
    silenced by a template edit either."""
    rel = f"{iv.TEMPLATE_DIR}/{iv.REPORT_TEMPLATES['pnl']}"

    def change(d):
        t = (d / rel).read_text()
        assert "\nNice=10\n" in t
        (d / rel).write_text(t.replace("\nNice=10\n", "\nNice=10\nSuccessExitStatus=4 5\n", 1))
    rw.commit_and_tag("v2", change)
    (rw.dev / rel).write_text((REAL_REPO / rel).read_text())          # tree restored, tag not
    rc, out = rw.run("--apply", tag="v2", capsys=capsys)               # the core at v2 first (8.12)
    assert rc == 0, out
    rc, out = rw.reports("--apply", tag="v2", capsys=capsys)
    assert rc == 2 and "fails its checks" in out and "SuccessExitStatus" in out, out


def test_the_dataqa_and_risk_units_stay_key_free_and_smtp_is_only_for_risk(rw, capsys):
    rc, out = rw.reports("--apply", capsys=capsys)
    assert rc == 0, out
    for book in ("cef", "c4"):
        for kind in ("dataqa", "risk"):
            text = rw.layout.unit_path(f"quantt-{book}-{kind}.service").read_text()
            body = "\n".join(ln for ln in text.splitlines() if not ln.startswith("#"))
            assert "broker.env" not in text and "pnl-keys" not in text and "ALPACA_" not in text, (book, kind)
            assert "QUANTT_ENV_FILE" not in body and "/run/quantt/" not in body
    smtp = rw.layout.unit_path(iv.REPORT_SECRET_UNIT).read_text()
    assert "alert-smtp-user=ALERT_SMTP_USER" in smtp and "alpaca-" not in smtp
    assert iv.REPORT_SECRET_UNIT not in rw.layout.unit_path("quantt-cef-pnl.service").read_text()


def test_book_installs_are_untouched_by_the_pnl_units(rw, capsys):
    assert rw.reports("--apply", "--enable", capsys=capsys)[0] == 0
    before = _unit_bytes(rw, iv.REPORT_UNIT_FILES)
    rw.cmds.calls.clear()
    assert rw.run("--apply", capsys=capsys)[0] == 0
    assert _unit_bytes(rw, iv.REPORT_UNIT_FILES) == before
    for c in _mutating_calls(rw):
        assert not any("pnl" in x for x in c), c


def test_a_book_install_refuses_while_a_pnl_job_runs(rw, capsys):
    assert rw.reports("--apply", capsys=capsys)[0] == 0
    rw.cmds.active["quantt-c4-pnl.service"] = "active"
    rc, out = rw.run("--apply", capsys=capsys)
    assert rc == 2 and "quantt-c4-pnl.service" in out and "report job" in out


def test_the_reports_help_names_the_pnl_units_and_their_key_services(capsys, monkeypatch):
    """Finding 4 of the independent review of PR #82 (2026-11-11): the `--reports` help said it
    installs "the report-only data-QA and risk units", but it also installs each book's pnl
    unit and the two pnl key services, which read each book's Alpaca key from the vault. The
    help now names them, from the constants the install renders. Fails on the parent commit.
    Its kind list is REPORT_KINDS's own names since the second review of PR #82 (2026-11-11)."""
    monkeypatch.setenv("COLUMNS", "1000")            # one line: argparse would wrap at hyphens
    with pytest.raises(SystemExit) as e:
        iv.main(["--help"])
    assert e.value.code == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "the dataqa, risk and pnl units of each book (cef, c4; quantt-<book>-<kind>)" in out
    assert ("the two pnl key services quantt-reports-cef-pnl-keys.service and quantt-reports-c4-pnl-keys.service, "
            "which read each book's Alpaca key from the vault") in out
    assert f"the alert secret service {iv.REPORT_SECRET_UNIT}" in out
    assert "data-QA and risk units instead" not in out


def _help(capsys, monkeypatch) -> str:
    monkeypatch.setenv("COLUMNS", "1000")            # one line: argparse would wrap at hyphens
    with pytest.raises(SystemExit) as e:
        iv.main(["--help"])
    assert e.value.code == 0
    return " ".join(capsys.readouterr().out.split())


def test_the_reports_help_kind_list_is_report_kinds(capsys, monkeypatch):
    """Second review of PR #82 (2026-11-11): the `--reports` help's kind list was the literal
    "data-QA, risk and pnl" beside a comment saying its names come from the constants and
    "cannot drift". It is now built from REPORT_KINDS, so a kind added there is in the help.
    Fails on the parent 3ab5afd, whose literal has no fourth kind."""
    monkeypatch.setattr(iv, "REPORT_KINDS", {**iv.REPORT_KINDS, "extra": "scripts.ops.extra"})
    out = _help(capsys, monkeypatch)
    assert "the dataqa, risk, pnl and extra units of each book (cef, c4; quantt-<book>-<kind>)" in out


def test_the_vault_help_names_every_secret_the_key_services_read(capsys, monkeypatch):
    """Second review of PR #82 (2026-11-11): the `--vault` help named only alpaca-cef-key-id and
    alpaca-cef-secret-key, but --book c4 reads C4's two and --reports reads both books' (the pnl
    key services) and the two SMTP secrets (the alert secret service). It now names them all,
    from the maps the services render. Fails on the parent 3ab5afd, which names neither C4's
    secrets nor the SMTP ones."""
    out = _help(capsys, monkeypatch)
    names = lambda pairs: ", ".join(s for s, _ in pairs)
    for b, vm in iv.VM_BOOKS.items():
        assert f"--book {b}: {names(vm.secret_map)}" in out, b
    both = names(p for b in iv.REPORT_BOOKS for p in iv.REPORT_PNL_KEYS[b].secret_map)
    assert f"--reports: {both} (the pnl key services) and {names(iv.REPORT_SECRET_MAP)} ({iv.REPORT_SECRET_UNIT})" in out
    for secret in ("alpaca-c4-key-id", "alpaca-c4-secret-key", "alert-smtp-user", "alert-smtp-pass"):
        assert secret in out, secret
