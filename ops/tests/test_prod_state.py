"""`ops.prod_state` says which machine is prod and whether it is armed.

WHY THIS FILE EXISTS
--------------------
From 2026-09-28 three surfaces told every session "no live book, nothing
trades" from string constants, through the first armed session on 2026-09-29
and every trading day after it (`docs/ROADMAP.md` 4.8). Their replacement is a
measurement, and a measurement can be wrong in the two ways that matter on this
desk: it can call a machine safe that is not (two armed schedulers on one
Alpaca account double the book, `CLAUDE.md` order-path rule 2), or it can
invent a state it could not read. These tests pin both directions:

  * armed, per-day, dry and off are told apart by the gates the runner uses
    (`docs/RUNNER.md` gates 1 and 2), not by what a document says;
  * a machine that cannot be read is UNMEASURED with the reason, and is never
    counted as safe (one armed + one unreadable says "not ruled out");
  * two armed machines raise the WARNING.

The OFF case is a real reading: on 2026-10-08, mid cut-over, the laptop's jobs
were unloaded and disabled while its plists still said DRY_RUN=0. A first
version of this module called that armed and raised a false two-schedulers
WARNING; `test_unloaded_and_disabled_is_off_with_a_caution` is that day.

HERMETIC. Every command is a fake `run`; the laptop is built under tmp_path;
the VM's reply is a canned string. No launchctl, git or ssh runs, and no figure
here is about the market: the equity values are synthetic and only test that
the file's own header is what gets read.
"""
from __future__ import annotations

import json
import plistlib
import subprocess

import pytest

from ops import prod_state as ps
from quantt.deploy import install_prod as ip

LABELS = [j.label for j in ip.JOBS]
SESSION_LABEL = next(j.label for j in ip.JOBS if j.log_stem == "session")


# ------------------------------------------------------------------ fakes --
class FakeRun:
    """Stands in for subprocess.run. Answers by command; records every argv."""

    def __init__(self, **answers):
        self.answers = answers
        self.calls = []

    def __call__(self, cmd, **kw):
        cmd = [str(c) for c in cmd]
        self.calls.append((cmd, kw))
        key = cmd[0] if cmd[0] != "launchctl" else f"launchctl {cmd[1]}"
        ans = self.answers.get(key.replace(" ", "_").replace("-", "_"))
        if ans is None:
            raise AssertionError(f"unexpected command {cmd}")
        if isinstance(ans, BaseException):
            raise ans
        rc, out, err = ans
        return subprocess.CompletedProcess(cmd, rc, out, err)


def launchctl_list(loaded=LABELS):
    rows = ["PID\tStatus\tLabel"] + [f"-\t0\t{lab}" for lab in loaded]
    return (0, "\n".join(rows) + "\n", "")


def print_disabled(disabled=()):
    body = "".join(f'\t"{lab}" => disabled\n' for lab in disabled)
    return (0, f"disabled services = {{\n{body}\t\"com.apple.x\" => enabled\n}}\n", "")


def laptop_run(loaded=LABELS, disabled=(), tag="release-test-1"):
    return FakeRun(git=(0, tag + "\n", ""), launchctl_list=launchctl_list(loaded),
                   launchctl_print_disabled=print_disabled(disabled))


# A header deliberately NOT in the collector's column order: the reader must
# use the file's own header, never a remembered layout.
EQUITY = ("read_at_utc,cash,equity,date,n_positions\n"
          "2026-01-05T21:10:00+00:00,1.0,111.11,2026-01-05,3\n"
          "2026-01-06T21:10:00+00:00,2.0,222.22,2026-01-06,4\n")


def make_laptop(home, dry_run="0", auto_armed=True, plists=True, equity=EQUITY):
    lay = ip.Layout(home)
    lay.prod_dir.mkdir(parents=True)
    lay.state_dir.mkdir(parents=True)
    if plists:
        lay.agents_dir.mkdir(parents=True)
        for job in ip.JOBS:
            env = {"QUANTT_STATE_DIR": str(lay.state_dir),
                   "QUANTT_ENV_FILE": "/nonexistent/never-read.env"}
            if dry_run is not None:
                env["DRY_RUN"] = dry_run
            lay.plist_path(job).write_bytes(
                plistlib.dumps({"Label": job.label, "EnvironmentVariables": env}))
    if auto_armed:
        (lay.state_dir / "AUTO_ARMED").write_text("test\n")
    (lay.state_dir / "verify.log").write_text(
        "2026-01-05 FAIL cef something\n2026-01-06 PASS cef traded 2 order(s), 2 filled\n")
    if equity is not None:
        (lay.state_dir / "equity.csv").write_text(equity)
    return lay


NEWEST_PLAN = ('{"session_date": "2026-01-07", "status": "decided", "orders": 4, "sent": false, '
               '"preflight": "ok", "shock_usd": 2074.61}')

# What the VM's P&L selector prints (synthetic values: they test the parse, not
# the market). eod_equity.csv absent is the state until the collector step that
# writes it is installed.
PNL_RAW = {"eod_equity": {"absent": "eod_equity.csv"},
           "scores": {"rows": [["2026-01-06", "PASS", "3.00", "2.00", "2.50"]], "n_rows": 1,
                      "file": "scores.csv"},
           "dist": {"rows": [["2026-01-06", "1.50"]], "n_rows": 1,
                    "file": "distribution_scores.csv"}}


def vm_reply(dry="DRY_RUN=0", auto="present", timers="active active active",
             enabled="enabled enabled enabled", end=True, load="loaded", newest=NEWEST_PLAN,
             pnl=(0, json.dumps(PNL_RAW))):
    rows = [("tag", 0, "release-vm-1"), ("load_state", 0, load), ("dry_run", 0, dry),
            ("timers", 0 if timers == "active active active" else 3, timers),
            ("timers_enabled", 0, enabled), ("auto_armed", 0, auto),
            ("verify", 0, "2026-01-06 PASS cef traded 2 order(s), 2 filled"),
            ("equity_header", 0, "date,equity,read_at_utc"),
            ("equity_last", 0, "2026-01-06,333.33,2026-01-06T21:10:00+00:00"),
            ("newest_plan", 0, newest)]
    if pnl is not None:
        rows.append(("pnl", *pnl))
    if end:
        rows.append(("END", 0, "quantt-prod-state"))
    return "".join(f"{k}\t{rc}\t{v}\n" for k, rc, v in rows)


@pytest.fixture
def ssh_config(tmp_path):
    # 203.0.113.0/24 is RFC 5737's documentation range: not the VM's address,
    # which never goes in a tracked file (docs/RUNBOOK.md section 8).
    p = tmp_path / "ssh_config"
    p.write_text(f"Host {ps.VM_ALIAS}\n    HostName 203.0.113.9\n    User someone\n")
    return p


def vm_run(stdout="", rc=0, stderr="", exc=None):
    return FakeRun(ssh=exc if exc is not None else (rc, stdout, stderr))


# ----------------------------------------------------------------- laptop --
class TestLaptop:
    def test_laptop_armed(self, tmp_path):
        make_laptop(tmp_path)
        m = ps.laptop(home=tmp_path, run=laptop_run(), uid=501)
        assert m["arming"] == ps.ARMED
        assert m["tag"] == {"value": "release-test-1"}
        assert m["auto_armed"]["value"] is True

    def test_laptop_disarmed(self, tmp_path):
        make_laptop(tmp_path, dry_run="1")
        m = ps.laptop(home=tmp_path, run=laptop_run(), uid=501)
        assert m["arming"] == ps.DRY and "DRY_RUN=1" in m["arming_why"]

    def test_unset_dry_run_is_dry_not_armed(self, tmp_path):
        """Gate 1: only exactly "0" transmits; unset is dry."""
        make_laptop(tmp_path, dry_run=None)
        m = ps.laptop(home=tmp_path, run=laptop_run(), uid=501)
        assert m["arming"] == ps.DRY and "unset" in m["arming_why"]

    def test_dry_run_0_without_auto_armed_is_per_day_approval_only(self, tmp_path):
        make_laptop(tmp_path, auto_armed=False)
        m = ps.laptop(home=tmp_path, run=laptop_run(), uid=501)
        assert m["arming"] == ps.PER_DAY

    def test_unloaded_and_disabled_is_off_with_a_caution(self, tmp_path):
        """2026-10-08, mid cut-over: jobs booted out and disabled, plists
        still DRY_RUN=0. Not armed -- but the leftover is said."""
        make_laptop(tmp_path, auto_armed=False)
        m = ps.laptop(home=tmp_path, run=laptop_run(loaded=(), disabled=LABELS), uid=501)
        assert m["arming"] == ps.OFF
        assert any("DRY_RUN=0" in c for c in m["cautions"])

    def test_unloaded_but_not_disabled_still_counts(self, tmp_path):
        """RUNBOOK 8.5 step 1: launchd loads it again at the next login."""
        make_laptop(tmp_path)
        m = ps.laptop(home=tmp_path, run=laptop_run(loaded=()), uid=501)
        assert m["arming"] == ps.ARMED
        assert "next login" in m["arming_why"]

    def test_unreadable_launchd_is_never_assumed_safe(self, tmp_path):
        make_laptop(tmp_path)
        run = FakeRun(git=(0, "t\n", ""),
                      launchctl_list=FileNotFoundError("launchctl"),
                      launchctl_print_disabled=FileNotFoundError("launchctl"))
        m = ps.laptop(home=tmp_path, run=run, uid=501)
        assert m["arming"] == ps.ARMED
        assert "counts as scheduled" in m["arming_why"]
        assert ps.UNMEASURED in m["jobs"]["session"]["loaded"]

    def test_no_plists_is_not_installed(self, tmp_path):
        make_laptop(tmp_path, plists=False)
        m = ps.laptop(home=tmp_path, run=laptop_run(), uid=501)
        assert m["arming"] == ps.NOT_INSTALLED

    def test_tag_failure_is_unmeasured_with_the_command(self, tmp_path):
        make_laptop(tmp_path)
        run = laptop_run()
        run.answers["git"] = (128, "", "fatal: No names found, cannot describe anything.")
        m = ps.laptop(home=tmp_path, run=run, uid=501)
        assert ps.UNMEASURED in m["tag"] and "describe --tags" in m["tag"][ps.UNMEASURED]

    def test_equity_is_read_by_the_files_own_header(self, tmp_path):
        make_laptop(tmp_path)
        e = ps.laptop(home=tmp_path, run=laptop_run(), uid=501)["equity"]["value"]
        assert (e["date"], e["equity"]) == ("2026-01-06", "222.22")
        assert e["read_at_utc"] == "2026-01-06T21:10:00+00:00"

    def test_equity_without_an_equity_column_is_unmeasured(self, tmp_path):
        make_laptop(tmp_path, equity="date,cash\n2026-01-06,1.0\n")
        e = ps.laptop(home=tmp_path, run=laptop_run(), uid=501)["equity"]
        assert ps.UNMEASURED in e and "equity" in e[ps.UNMEASURED]

    def test_missing_equity_file_is_absent_not_zero(self, tmp_path):
        make_laptop(tmp_path, equity=None)
        e = ps.laptop(home=tmp_path, run=laptop_run(), uid=501)["equity"]
        assert "absent" in e and "value" not in e

    def test_never_touches_the_retired_ibkr_tree(self, tmp_path):
        """`~/prod/QUANTT` is the retired IBKR tree, not the Alpaca prod."""
        make_laptop(tmp_path)
        (tmp_path / "prod" / "QUANTT").mkdir()
        run = laptop_run()
        ps.laptop(home=tmp_path, run=run, uid=501)
        assert not any(str(tmp_path / "prod" / "QUANTT") in " ".join(c) for c, _ in run.calls)

    def test_only_read_only_launchctl_verbs(self, tmp_path):
        make_laptop(tmp_path)
        run = laptop_run()
        ps.laptop(home=tmp_path, run=run, uid=501)
        verbs = {c[1] for c, _ in run.calls if c[0] == "launchctl"}
        assert verbs <= {"list", "print-disabled"}


# --------------------------------------------------------------------- vm --
class TestVM:
    def test_vm_armed(self, ssh_config):
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply()))
        assert m["arming"] == ps.ARMED
        assert m["tag"] == {"value": "release-vm-1"}
        assert m["equity"]["value"]["equity"] == "333.33"

    def test_vm_shadow_is_dry(self, ssh_config):
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply(dry="DRY_RUN=1", auto="absent")))
        assert m["arming"] == ps.DRY

    def test_vm_timers_stopped_but_enabled_still_count(self, ssh_config):
        """RUNBOOK 8.5 step 2 stops the timers; enabled ones start at boot."""
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply(
            timers="inactive inactive inactive")))
        assert m["arming"] == ps.ARMED and "starts again at boot" in m["arming_why"]

    def test_vm_timers_inactive_and_disabled_is_off(self, ssh_config):
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply(
            timers="inactive inactive inactive", enabled="disabled disabled disabled")))
        assert m["arming"] == ps.OFF

    def test_vm_unreachable_is_unmeasured(self, ssh_config):
        run = vm_run(exc=subprocess.TimeoutExpired(["ssh"], 3))
        m = ps.vm(ssh_config=ssh_config, run=run, timeout=3)
        assert m["arming"] == ps.UNMEASURED
        assert "did not finish within 3s" in m[ps.UNMEASURED]
        assert run.calls[0][1]["timeout"] == 3

    def test_vm_ssh_failure_is_unmeasured_and_never_names_the_address(self, ssh_config):
        """The repo is public; ssh's error names the VM's address."""
        run = vm_run(rc=255, stderr="ssh: connect to host 203.0.113.9 port 22: Operation timed out\n")
        m = ps.vm(ssh_config=ssh_config, run=run)
        assert m["arming"] == ps.UNMEASURED
        assert "203.0.113.9" not in str(m) and "<address>" in m[ps.UNMEASURED]

    def test_scrub_removes_addresses_and_keeps_a_timestamp(self):
        s = ps.scrub("connect to host 203.0.113.9 or 2001:db8:0:1::5 or fe80::1 at 12:05:59\nmore")
        assert "203.0.113.9" not in s and "2001:db8" not in s and "fe80::1" not in s
        assert "12:05:59" in s and "more" not in s

    def test_vm_reply_cut_short_is_unmeasured(self, ssh_config):
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply(end=False)))
        assert m["arming"] == ps.UNMEASURED and "cut short" in m[ps.UNMEASURED]

    def test_no_alias_means_no_ssh_at_all(self, tmp_path):
        cfg = tmp_path / "ssh_config"
        cfg.write_text("Host somewhere-else\n")
        run = vm_run(vm_reply())
        m = ps.vm(ssh_config=cfg, run=run)
        assert m["arming"] == ps.UNMEASURED and "has no `Host quantt-vm`" in m[ps.UNMEASURED]
        assert run.calls == []

    def test_real_ssh_is_refused_under_netguard(self, ssh_config):
        """ssh is a child process: netguard cannot see it. A test that forgot
        to pass a fake `run` would otherwise connect to the real VM."""
        m = ps.vm(ssh_config=ssh_config)
        assert m["arming"] == ps.UNMEASURED and "netguard" in m[ps.UNMEASURED]

    def test_one_ssh_call_batch_mode_with_a_connect_timeout(self, ssh_config):
        run = vm_run(vm_reply())
        ps.vm(ssh_config=ssh_config, run=run)
        assert len(run.calls) == 1
        cmd, kw = run.calls[0]
        assert cmd[0] == "ssh" and "BatchMode=yes" in cmd
        assert f"ConnectTimeout={ps.SSH_CONNECT_TIMEOUT_S}" in cmd
        assert kw["input"] == ps.vm_script() + ps.SHADOW_SCRIPT
        assert kw["input"].startswith(ps.REMOTE_SCRIPT)

    def test_remote_script_never_reads_the_key_files(self):
        """/run/quantt holds the keys (RUNBOOK 8). The Environment line is cut
        to DRY_RUN on the VM, so even the key file's path stays there."""
        assert "/run/quantt" not in ps.REMOTE_SCRIPT
        assert "QUANTT_ENV_FILE" not in ps.REMOTE_SCRIPT
        env_line = next(ln for ln in ps.REMOTE_SCRIPT.splitlines() if "-p Environment" in ln)
        assert "grep '^DRY_RUN='" in env_line

    def test_two_dry_run_assignments_are_a_gap_not_a_pick(self, ssh_config):
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply(dry="DRY_RUN=1 DRY_RUN=0")))
        assert m["arming"] == ps.UNMEASURED


# ------------------------------------------------ the other VM books (2026-11-18)
def book_part(reply: str, book: str = "c4") -> str:
    """A fake reply's lines re-keyed `<book>.<key>`, as `remote_script(book,
    prefix)` prints them."""
    return "".join(f"{book}.{ln}\n" for ln in reply.splitlines())


class TestOtherBooks:
    """C4 has its own units, state dir and Alpaca account on the VM. Until
    2026-11-18 nothing read them, so its state was known only by hand over ssh."""

    def test_the_cores_script_is_untouched_and_names_no_other_book(self):
        assert ps.REMOTE_SCRIPT == ps.remote_script(ps.iv.BOOK)
        assert "c4" not in ps.REMOTE_SCRIPT and "q tag " in ps.REMOTE_SCRIPT
        assert ps.REMOTE_SCRIPT.rstrip().endswith("printf 'END\\t0\\tquantt-prod-state\\n'")

    def test_each_other_books_script_reads_its_own_units_and_state_dir(self):
        assert "c4" in ps.OTHER_VM_BOOKS
        sc = ps.remote_script("c4", prefix="c4.")
        assert "S=/home/quantt/quantt_state/c4\n" in sc
        assert "quantt-c4-session.service" in sc and "quantt-cef-" not in sc
        keyed = [ln.split()[1] for ln in sc.splitlines() if ln.startswith(("q ", "qw "))]
        assert keyed and all(k.startswith("c4.") for k in keyed)
        assert "printf 'c4.END" in sc and "/run/" not in sc

    def test_a_book_is_read_from_its_own_prefixed_lines(self, ssh_config):
        c4 = vm_reply(dry="DRY_RUN=1", auto="absent").replace(" cef traded", " c4 traded")
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply() + book_part(c4)))
        b = m["books"]["c4"]
        assert m["arming"] == ps.ARMED and b["arming"] == ps.DRY and b["book"] == "c4"
        assert b["state_dir"].endswith("/quantt_state/c4")
        assert "c4 traded" in str(b["verify_last"]) and "cef traded" in str(m["verify_last"])
        assert "quantt_state/c4/equity.csv" in str(b["equity"]) and "333.33" in str(b["equity"])

    def test_a_books_schedule_is_read_from_its_own_session_timer(self, ssh_config):
        """Read against the core's timer name, C4's timers never held the key
        and an armed C4 printed as 'whether the scheduler fires is UNMEASURED'."""
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply() + book_part(vm_reply())))
        b = m["books"]["c4"]
        assert b["scheduled"] == {"value": True, "why": "quantt-c4-session.timer active"}
        assert b["arming"] == ps.ARMED and "UNMEASURED" not in b["arming_why"]
        off = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply() + book_part(vm_reply(
            timers="inactive inactive inactive", enabled="disabled disabled disabled"))))
        assert off["arming"] == ps.ARMED and off["books"]["c4"]["arming"] == ps.OFF

    def test_a_reply_cut_inside_a_book_leaves_the_core_measured(self, ssh_config):
        cut = vm_reply() + book_part(vm_reply(end=False))
        m = ps.vm(ssh_config=ssh_config, run=vm_run(cut))
        assert m["arming"] == ps.ARMED
        assert m["books"]["c4"]["arming"] == ps.UNMEASURED
        assert "c4.END" in m["books"]["c4"][ps.UNMEASURED]

    def test_no_books_asked_sends_only_the_cores_script(self, ssh_config):
        run = vm_run(vm_reply())
        m = ps.vm(ssh_config=ssh_config, run=run, books=(), shadow=False)
        assert run.calls[0][1]["input"] == ps.REMOTE_SCRIPT and m["books"] == {}

    def test_render_prints_each_book_under_the_vm(self, tmp_path, ssh_config):
        make_laptop(tmp_path, auto_armed=False)
        lap_run = laptop_run(loaded=(), disabled=LABELS)
        run = FakeRun(**lap_run.answers, ssh=(0, vm_reply() + book_part(vm_reply(dry="DRY_RUN=1")), ""))
        d = ps.measure(run=run, home=tmp_path, ssh_config=ssh_config)
        lines = []
        ps.render_lines(d, lambda label, value="": lines.append(f"{label} {value}"))
        out = "\n".join(lines)
        assert "VM book c4" in out and "quantt_state/c4/AUTO_ARMED" in out
        assert d["verdict"]["prod"] == "vm"      # the one-prod verdict is still the core's


# ------------------------------------------------- the shadow books (2026-11-18)
SHADOW_OK = {"state": True, "books": {
    "aaa_book": {"status": {"FLAT": 1, "SCORED": 2}, "first": "2026-01-05", "last": "2026-01-07",
                 "pnl_price_usd": -12.5, "pnl_total_usd": None, "total_gaps": 1, "last_gross": "1.0"},
    "bad_book": {"error": "ValueError: scores.csv line 3 is not a whole row"}}}


def shadow_part(books=SHADOW_OK, timer="active enabled", end=True):
    rows = [("shadow.timer", 0, timer), ("shadow.books", 0, json.dumps(books))]
    if end:
        rows.append(("shadow.END", 0, "quantt-prod-state"))
    return "".join(f"{k}\t{rc}\t{v}\n" for k, rc, v in rows)


class TestShadowBooks:
    """Simulated books on the VM, under their own user. Synthetic rows throughout:
    these test the reader, not any book."""

    def test_the_names_are_the_install_scripts(self):
        sh = (ps.REPO / "shadow" / "deploy" / "install_shadow_vm.sh").read_text()
        assert f'SVC_USER="{ps.SHADOW_USER}"' in sh
        assert 'STATE="${HOME_DIR}/shadow_state"' in sh and 'HOME_DIR="/home/${SVC_USER}"' in sh
        assert ps.SHADOW_STATE == f"/home/{ps.SHADOW_USER}/shadow_state"
        assert f"systemctl enable --now {ps.SHADOW_TIMER}" in sh

    def test_the_shadow_part_rides_in_the_one_call_after_every_book(self, ssh_config):
        run = vm_run(vm_reply() + shadow_part())
        m = ps.vm(ssh_config=ssh_config, run=run)
        assert len(run.calls) == 1 and run.calls[0][1]["input"].endswith(ps.SHADOW_SCRIPT)
        assert "/run/" not in ps.SHADOW_SCRIPT and "alpaca.env" not in ps.SHADOW_SCRIPT
        sh = m["shadow"]
        assert sh["timer"]["value"] == {"active": "active", "enabled": "enabled"}
        assert sh["books"]["value"]["aaa_book"]["pnl_price_usd"] == -12.5
        assert "line 3" in sh["books"]["value"]["bad_book"][ps.UNMEASURED]
        assert m["arming"] == ps.ARMED, "a shadow reading never changes the arming reading"

    def test_a_missing_or_cut_shadow_part_is_unmeasured_and_the_core_stands(self, ssh_config):
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply() + shadow_part(end=False)))
        assert m["arming"] == ps.ARMED and "shadow.END" in m["shadow"][ps.UNMEASURED]
        off = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply()), shadow=False)
        assert "shadow" not in off

    def test_render_says_simulated_and_never_passes_a_gap_off_as_a_total(self, ssh_config):
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply() + shadow_part()))
        text = "\n".join(f"{a} {b}" for a, b in ps.shadow_lines(m["shadow"]))
        assert "SIMULATED" in text and "price-only -$12.50" in text
        assert "total return UNMEASURED on 1 scored session(s)" in text
        assert "bad_book UNMEASURED" in text
        none = ps.shadow_lines(ps._shadow_from_readings(
            {"shadow.END": (0, ""), "shadow.timer": (0, "active enabled"),
             "shadow.books": (0, json.dumps({"state": False, "books": {}}))}, "vm"))
        assert "no /home/quantt-shadow/shadow_state" in none[1][1]

    def test_the_real_summary_line_runs_and_ships_no_name_or_weight(self, tmp_path):
        """The real python from SHADOW_SCRIPT, run locally on a state dir in the
        engine's own format (shadow/engine.py SCORE_FIELDS)."""
        import subprocess
        import sys as _sys
        head = ("date,prev,status,pnl_price_usd,pnl_total_usd,gross,net,n_names,turnover,"
                "decision_asof,detail,label\n")
        st = tmp_path / "shadow_state"
        (st / "aaa_book").mkdir(parents=True)
        (st / "aaa_book" / "scores.csv").write_text(
            head + "2026-01-05,2026-01-02,FLAT,0.0,0.0,0,0,0,0,2026-01-02,,SIMULATED\n"
            "2026-01-06,2026-01-05,SCORED,-20.5,-18.0,1.0,0.0,3,0.2,2026-01-05,,SIMULATED\n"
            "2026-01-07,2026-01-06,SCORED,8.0,,1.0,0.0,3,0.1,2026-01-06,no close for ZZQQ,SIMULATED\n")
        (st / "bad_book").mkdir()
        (st / "bad_book" / "scores.csv").write_text(head + "2026-01-05,2026-01-02\n")
        (st / "no_scores_yet").mkdir()
        r = subprocess.run([_sys.executable, "-I", "-c", ps._SHADOW_PY, str(st)],
                           capture_output=True, text=True, timeout=30)
        got = json.loads(r.stdout)
        assert got["state"] is True and sorted(got["books"]) == ["aaa_book", "bad_book"]
        assert got["books"]["aaa_book"] == {
            "status": {"FLAT": 1, "SCORED": 2}, "first": "2026-01-05", "last": "2026-01-07",
            "pnl_price_usd": -12.5, "pnl_total_usd": None, "total_gaps": 1, "last_gross": "1.0"}
        assert "line 2" in got["books"]["bad_book"]["error"]
        assert "ZZQQ" not in r.stdout, "the detail column names symbols; it never leaves"
        gone = subprocess.run([_sys.executable, "-I", "-c", ps._SHADOW_PY, str(tmp_path / "nope")],
                              capture_output=True, text=True, timeout=30)
        assert json.loads(gone.stdout) == {"state": False, "books": {}}


# ---------------------------------------------------------------- verdict --
def machine(arming, cautions=()):
    return {"arming": arming, "arming_why": f"because {arming}", "cautions": list(cautions),
            "equity": {"value": {"date": "2026-01-06", "equity": "1", "source": "x"}}}


class TestVerdict:
    def test_both_armed_warns(self):
        v = ps.verdict({"laptop": machine(ps.ARMED), "vm": machine(ps.ARMED)})
        assert v["warning"].startswith("WARNING: TWO ARMED SCHEDULERS")
        assert v["prod"] is None and "order-path rule 2" in v["warning"]

    def test_armed_beside_per_day_also_warns(self):
        """A per-day approval on one machine plus AUTO_ARMED on the other is
        two sends for that day."""
        v = ps.verdict({"laptop": machine(ps.ARMED), "vm": machine(ps.PER_DAY)})
        assert v["warning"]

    def test_one_armed_is_prod_and_its_equity_is_live(self):
        v = ps.verdict({"laptop": machine(ps.OFF), "vm": machine(ps.ARMED)})
        assert v["prod"] == "vm" and not v["warning"]
        assert v["equity"]["value"]["equity"] == "1"

    def test_one_armed_beside_unmeasured_is_not_ruled_out(self):
        v = ps.verdict({"laptop": machine(ps.ARMED), "vm": machine(ps.UNMEASURED)})
        assert v["prod"] == "laptop" and "not ruled out" in v["line"]

    def test_nothing_armed_is_said_and_carries_no_equity(self):
        v = ps.verdict({"laptop": machine(ps.DRY), "vm": machine(ps.OFF)})
        assert v["prod"] is None and "nothing is sent" in v["line"] and v["equity"] is None

    def test_cautions_are_collected_from_every_machine(self):
        v = ps.verdict({"laptop": machine(ps.OFF, ["left DRY_RUN=0"]), "vm": machine(ps.ARMED)})
        assert v["cautions"] == ["laptop: left DRY_RUN=0"]


# ------------------------------------------------------------- end to end --
def test_measure_and_render_end_to_end(tmp_path, ssh_config):
    """laptop OFF + VM ARMED, through measure() and the renderer orient uses."""
    make_laptop(tmp_path, auto_armed=False)
    lap_run = laptop_run(loaded=(), disabled=LABELS)
    run = FakeRun(**lap_run.answers, ssh=(0, vm_reply(), ""))
    d = ps.measure(run=run, home=tmp_path, ssh_config=ssh_config)
    assert d["verdict"]["prod"] == "vm"
    lines = []
    ps.render_lines(d, lambda label, value="": lines.append(f"{label} {value}"))
    out = "\n".join(lines)
    assert "prod is the VM: ARMED" in out and "caution" in out


# ------------------------------------------- the newest plan and its pre-flight (2026-10-09)
class TestNewestPlan:
    def test_ok_is_shown_and_raises_no_caution(self, ssh_config):
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply()))
        assert m["newest_plan"]["value"]["preflight"] == "ok"
        assert ps.plan_text(m["newest_plan"]) == ("2026-01-07: decided, 4 order(s), not sent yet; "
                                                  "pre-flight ok (worst-day shock $2,074.61)")
        assert not any("PRE-FLIGHT" in c for c in m["cautions"])

    def test_a_warning_on_an_unsent_plan_is_a_caution(self, ssh_config):
        w = NEWEST_PLAN.replace('"ok"', '"warning"')
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply(newest=w)))
        assert any("PRE-FLIGHT WARNING" in c and "2026-01-07" in c for c in m["cautions"])
        assert "pre-flight WARNING" in ps.plan_text(m["newest_plan"])

    def test_a_warning_on_a_sent_plan_is_history_not_a_caution(self, ssh_config):
        w = NEWEST_PLAN.replace('"ok"', '"warning"').replace("false", "true")
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply(newest=w)))
        assert not any("PRE-FLIGHT" in c for c in m["cautions"])

    def test_a_plan_from_before_the_preflight_says_so(self, ssh_config):
        old = NEWEST_PLAN.replace('"ok"', "null").replace("2074.61", "null")
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply(newest=old)))
        assert "pre-flight not run" in ps.plan_text(m["newest_plan"])

    def test_no_plan_is_absent_and_garbage_is_unmeasured(self, ssh_config):
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply(newest="NO-PLAN")))
        assert "value" not in m["newest_plan"] and ps.UNMEASURED not in m["newest_plan"]
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply(newest="{not json")))
        assert ps.UNMEASURED in m["newest_plan"]

    def test_the_remote_line_runs_and_its_quoting_survives_the_shell(self, tmp_path):
        """The real line from REMOTE_SCRIPT, `sudo -n` removed, run by sh on a state dir
        holding two days; the newest is summarised, and no position leaves it."""
        import shlex
        import subprocess
        state = tmp_path / "state"
        for d, plan in (("2026-01-06", {"status": "decided", "orders": [{}]}),
                        ("2026-01-07", {"session_date": "2026-01-07", "status": "decided",
                                        "orders": [{}, {}], "targets": {"AAA": {"current": 5}},
                                        "preflight": {"ok": False, "shock_usd": 9.5}})):
            (state / d).mkdir(parents=True)
            (state / d / "plan.json").write_text(json.dumps(plan))
        (state / "2026-01-06" / "STARTED").write_text("{}")
        lines = ps.REMOTE_SCRIPT.splitlines()
        line = next(ln for ln in lines if ln.startswith("q newest_plan")).replace("sudo -n ", "")
        script = f"{lines[0]}\nS={shlex.quote(str(state))}\n{line}\n"
        r = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=30)
        key, rc, out = r.stdout.rstrip("\n").split("\t")
        assert (key, rc) == ("newest_plan", "0"), r.stderr
        assert json.loads(out) == {"session_date": "2026-01-07", "status": "decided", "orders": 2,
                                   "sent": False, "preflight": "warning", "shock_usd": 9.5}
        assert "AAA" not in out

    def test_the_plan_shape_line_ships_counts_and_totals_and_no_position(self, tmp_path):
        """The real `plan_shape` line, `sudo -n` removed, run by sh. Synthetic
        plan: it tests the summary, not a book. Why it exists: on 2026-11-18
        nothing short of copying C4's plan off the VM could say why 74 names
        produced no order."""
        import shlex
        import subprocess
        hold = "cef band hold: |gap|<=0.0480 w=-0.0240 gmax=1.8000"
        plan = {"session_date": "2026-01-07", "equity": 1000.0,
                "closes": {"AAA": 10.0, "BBB": 20.0, "CCC": 5.0, "DDD": 1.0},
                "targets": {"AAA": {"current": 30, "target": 30, "reason": hold},
                            "BBB": {"current": -10, "target": -12,
                                    "reason": "cef discount z=-3.01 w=+0.2301 volscal=1.88 "
                                              "gmax=1.8000*x0.9700 smult=1.3000"},
                            "CCC": {"current": 0, "target": 0, "reason": "cef: illiquid gmax=1.8"},
                            "DDD": {"current": 0, "target": 0, "reason": "cef: illiquid gmax=1.8"}}}
        state = tmp_path / "state"
        (state / "2026-01-07").mkdir(parents=True)
        (state / "2026-01-07" / "plan.json").write_text(json.dumps(plan))
        lines = ps.REMOTE_SCRIPT.split("\n")
        i = next(k for k, ln in enumerate(lines) if ln.startswith("qw plan_shape"))
        j = next(k for k in range(i + 1, len(lines)) if lines[k].startswith("qw pnl"))
        line = "\n".join(lines[i:j]).replace("sudo -n ", "")
        script = f"{lines[1]}\nS={shlex.quote(str(state))}\n{line}\n"
        r = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=30)
        key, rc, out = r.stdout.rstrip("\n").split("\t")
        assert (key, rc) == ("plan_shape", "0"), r.stderr
        assert json.loads(out) == {
            "session_date": "2026-01-07", "names": 4, "held": 2, "long": 1, "short": 1,
            "target_differs": 1, "gross_cap_bound": 1, "gross_cap_scale": ["0.9700"], "gross_usd": 500.0, "net_usd": 100.0, "equity": 1000.0,
            "why": {"cef band hold": 1, "cef discount": 1, "cef illiquid": 2}}
        assert not any(sym in out for sym in ("AAA", "BBB", "CCC", "DDD"))
        text = ps.shape_text({"value": json.loads(out)})
        assert "4 name(s), 2 held (1 long, 1 short)" in text and "0.50x the plan's equity" in text
        assert "GROSS CAP BINDING on 1 name(s), book scaled x0.9700" in text
        assert "gross cap not binding" in ps.shape_text({"value": {**json.loads(out), "gross_cap_bound": 0}})

    def test_a_held_name_without_a_close_makes_the_totals_a_gap(self, tmp_path):
        import shlex
        import subprocess
        plan = {"closes": {}, "targets": {"AAA": {"current": 3, "target": 3, "reason": "x"}}}
        state = tmp_path / "state"
        (state / "2026-01-07").mkdir(parents=True)
        (state / "2026-01-07" / "plan.json").write_text(json.dumps(plan))
        lines = ps.REMOTE_SCRIPT.split("\n")
        i = next(k for k, ln in enumerate(lines) if ln.startswith("qw plan_shape"))
        j = next(k for k in range(i + 1, len(lines)) if lines[k].startswith("qw pnl"))
        line = "\n".join(lines[i:j]).replace("sudo -n ", "")
        r = subprocess.run(["sh", "-c", f"{lines[1]}\nS={shlex.quote(str(state))}\n{line}\n"],
                           capture_output=True, text=True, timeout=30)
        got = json.loads(r.stdout.rstrip("\n").split("\t")[2])
        assert got["gross_usd"] is None and got["net_usd"] is None and got["held"] == 1
        assert "UNMEASURED" in ps.shape_text({"value": got})


# ------------------------------------------- the daily P&L files (2026-10-19)
# The team lead ruled that day that Alpaca's EOD portfolio history is the
# official daily P&L of record and verify's after-the-close equity change is a
# snapshot. PROD's one ssh call now carries each P&L file's named columns, so
# orient's PNL section can print the record beside the three scores. These pin
# what crosses the wire: only the named columns, chosen by the file's own
# header, and never scores.csv's per_symbol_json, which holds the positions.

# A header NOT in verify's column order, with the positions column in the
# middle and a sentinel inside it: whatever leaves the selector must not hold it.
SECRET = "POSITION-SENTINEL-ZZQ"
SCORES = ("verdict,per_symbol_json,auction_pnl_usd,date,book,alpaca_equity_change_usd,auction_hold_pnl_usd\n"
          f'FAIL,"{{""{SECRET}"":5}}",UNMEASURED,2026-01-05,cef,1.00,UNMEASURED\n'
          f'PASS,"{{""{SECRET}"":6}}",2.00,2026-01-06,cef,3.00,2.50\n')
DIST = ("date,auction_pnl_usd,distribution_pnl_usd,auction_pnl_with_distributions_usd,"
        "unmeasured,per_symbol_json,source,label,written_at_utc\n"
        f'2026-01-06,2.00,-0.50,1.50,,"{{""{SECRET}"":1}}",alpaca,x,t\n')
EOD = "date,equity,change_usd,fetched_at_utc\n2026-01-05,0,0,t\n2026-01-06,100.00,100.00,t\n"


def _state(tmp_path, scores=SCORES, dist=DIST, eod=EOD):
    s = tmp_path / "state"
    s.mkdir()
    for name, body in (("scores.csv", scores), ("distribution_scores.csv", dist),
                       ("eod_equity.csv", eod)):
        if body is not None:
            (s / name).write_text(body)
    return s


def _run_remote_pnl_line(state):
    """The real `qw pnl` line from REMOTE_SCRIPT, run by sh on a local state dir
    with only `sudo -n -u <service user>` removed: proves the payload survives
    the shell's double quotes and the reply parses."""
    import shlex
    from quantt.deploy import install_vm as iv
    lines = ps.REMOTE_SCRIPT.split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.startswith("qw pnl "))
    end = next(i for i in range(start, len(lines)) if lines[i].endswith('"$S"'))
    block = "\n".join(lines[start:end + 1])
    assert block.startswith(f"qw pnl sudo -n -u {iv.SERVICE_USER} python3 -I -c "), (
        "the selector runs as the service user, which owns the state dir")
    block = block.replace(f"sudo -n -u {iv.SERVICE_USER} ", "", 1)
    qw = next(ln for ln in lines if ln.startswith("qw()"))
    script = f"{qw}\nS={shlex.quote(str(state))}\n{block}\n"
    r = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=30)
    key, rc, out = r.stdout.rstrip("\n").split("\t")
    assert (key, rc) == ("pnl", "0"), (r.stdout, r.stderr)
    return r.stdout, json.loads(out)


class TestPnlFiles:
    def test_vm_reading_carries_the_pnl_files(self, ssh_config):
        """The key test: PROD's VM reading holds each P&L file as a reading."""
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply()))
        p = m["pnl"]
        assert p["where"].startswith(f"{ps.VM_ALIAS}:")
        assert "absent" in p["eod_equity"] and "eod_equity.csv" in p["eod_equity"]["absent"]
        assert p["scores"]["value"]["rows"] == [["2026-01-06", "PASS", "3.00", "2.00", "2.50"]]
        assert p["dist"]["value"]["rows"] == [["2026-01-06", "1.50"]]

    def test_the_remote_line_selects_by_header_and_never_ships_positions(self, tmp_path):
        stdout, raw = _run_remote_pnl_line(_state(tmp_path))
        assert SECRET not in stdout and "per_symbol_json" not in stdout
        assert raw["scores"] == {"rows": [["2026-01-05", "FAIL", "1.00", "UNMEASURED", "UNMEASURED"],
                                          ["2026-01-06", "PASS", "3.00", "2.00", "2.50"]],
                                 "n_rows": 2, "file": "scores.csv"}
        assert raw["dist"]["rows"] == [["2026-01-06", "1.50"]]
        assert raw["eod_equity"]["rows"] == [["2026-01-05", "0", "0"],
                                             ["2026-01-06", "100.00", "100.00"]]
        assert "fetched_at_utc" not in stdout, "an extra column is never carried"

    def test_absent_files_are_absent_by_name_on_the_wire_and_after(self, tmp_path):
        _stdout, raw = _run_remote_pnl_line(_state(tmp_path, scores=None, dist=None, eod=None))
        assert raw == {"eod_equity": {"absent": "eod_equity.csv"},
                       "scores": {"absent": "scores.csv"},
                       "dist": {"absent": "distribution_scores.csv"}}
        r = ps.pnl_readings(raw, "vm:/s")
        assert r["eod_equity"] == {"absent": "no eod_equity.csv in vm:/s"}
        assert all("value" not in r[k] and ps.UNMEASURED not in r[k] for k in ps.PNL_FILES)

    def test_a_missing_column_is_a_named_gap_not_a_shifted_value(self, tmp_path):
        s = _state(tmp_path, eod="date,equity\n2026-01-06,100.00\n")
        r = ps.pnl_readings(ps.pnl_tails(str(s), ps.PNL_FILES), str(s))
        assert ps.UNMEASURED in r["eod_equity"]
        assert "eod_equity.csv" in r["eod_equity"][ps.UNMEASURED]
        assert "change_usd" in r["eod_equity"][ps.UNMEASURED]

    def test_a_half_written_row_is_an_error_naming_its_line(self, tmp_path):
        """scores.csv is appended in place; a read mid-append must not quietly
        drop the row and return a shorter series."""
        s = _state(tmp_path, scores=SCORES + "PASS,{}\n")
        r = ps.pnl_readings(ps.pnl_tails(str(s), ps.PNL_FILES), str(s))
        assert ps.UNMEASURED in r["scores"] and "line 4" in r["scores"][ps.UNMEASURED]

    def test_only_the_tail_is_kept_and_the_full_count_is_said(self, tmp_path):
        """distribution_scores.csv feeds a 10-session table: a tail. scores.csv
        is kept whole since 2026-11-18, because its at-close column is summed
        over the book's life (orient `close_model`)."""
        head = "date,auction_pnl_with_distributions_usd\n"
        body = "".join(f"2026-{1 + i // 28:02d}-{1 + i % 28:02d},1.00\n" for i in range(40))
        sc = "date,verdict,alpaca_equity_change_usd,auction_pnl_usd,auction_hold_pnl_usd\n" + "".join(
            f"2026-{1 + i // 28:02d}-{1 + i % 28:02d},PASS,1.00,1.00,1.00\n" for i in range(40))
        s = _state(tmp_path, dist=head + body, scores=sc)
        got = ps.pnl_tails(str(s), ps.PNL_FILES)
        assert got["dist"]["n_rows"] == 40 and len(got["dist"]["rows"]) == ps.PNL_TAIL_ROWS
        assert got["dist"]["rows"][-1][0] == "2026-02-12"
        assert len(got["scores"]["rows"]) == 40, "the whole series, for a whole-life sum"

    def test_laptop_reads_its_own_state_dir_with_the_same_selector(self, tmp_path):
        lay = make_laptop(tmp_path)
        (lay.state_dir / "scores.csv").write_text(SCORES)
        m = ps.laptop(home=tmp_path, run=laptop_run(), uid=501)
        assert m["pnl"]["scores"]["value"]["n_rows"] == 2
        assert "absent" in m["pnl"]["eod_equity"] and "absent" in m["pnl"]["dist"]
        assert SECRET not in json.dumps(m, default=str)

    @pytest.mark.parametrize("pnl,why", [
        ((1, "sudo: a password is required"), "exited 1"),
        ((0, '{"eod_equity": {"rows": [["cut'), "not JSON"),
        (None, "no pnl line"),
    ])
    def test_a_failed_or_cut_reply_is_unmeasured_for_every_file(self, ssh_config, pnl, why):
        m = ps.vm(ssh_config=ssh_config, run=vm_run(vm_reply(pnl=pnl)))
        for k in ps.PNL_FILES:
            assert ps.UNMEASURED in m["pnl"][k] and why in m["pnl"][k][ps.UNMEASURED]
        assert m["arming"] == ps.ARMED, "a P&L gap never changes the arming reading"

    def test_a_reply_in_the_wrong_shape_is_not_trusted(self):
        raw = {**PNL_RAW, "scores": {"rows": [["2026-01-06", "PASS"]], "n_rows": 1}}
        r = ps.pnl_readings(raw, "vm:/s")
        assert ps.UNMEASURED in r["scores"] and "scores.csv" in r["scores"][ps.UNMEASURED]
        assert "value" in r["dist"]

    def test_prod_render_lists_each_machines_pnl_files(self, tmp_path, ssh_config):
        make_laptop(tmp_path, auto_armed=False)
        run = FakeRun(**laptop_run(loaded=(), disabled=LABELS).answers, ssh=(0, vm_reply(), ""))
        d = ps.measure(run=run, home=tmp_path, ssh_config=ssh_config)
        lines = []
        ps.render_lines(d, lambda label, value="": lines.append(f"{label} {value}"))
        pnl = [ln for ln in lines if ln.strip().startswith("P&L files")]
        assert len(pnl) == 2
        assert "eod_equity.csv none" in pnl[1] and "scores.csv 1 row(s), to 2026-01-06" in pnl[1]
