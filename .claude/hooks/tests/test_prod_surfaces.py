"""The banner and the status line read which machine is prod from
`ops.prod_state`, through `book_state.collect`, and say it out loud.

WHY THIS FILE EXISTS
--------------------
From 2026-09-28 to 2026-10-08 the banner said "NO LIVE BOOK ... Nothing trades"
and the status line "no live book", both from constants, while the book armed
on 2026-09-29 and traded (`docs/ROADMAP.md` 4.8). These tests drive the real
`book_state.collect` with the two prod_state readers replaced, so they pin the
wiring as well as the words: laptop armed, laptop disarmed, VM unreachable
(UNMEASURED, never assumed safe), two armed machines (the WARNING, first), the
banner's ssh budget, and the rule that the status line never opens ssh.

HERMETIC: `ps.laptop` and `ps.vm` are fakes, and the VM cache file is under
tmp_path. No launchctl, git describe or ssh runs.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1]
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_undertest", HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _m(arming, equity="222.22"):
    return {"machine": "?", "arming": arming, "arming_why": f"because {arming}",
            "cautions": [], "tag": {"value": f"tag-{arming.lower()}"},
            "verify_last": {"value": {"date": "2026-01-06", "verdict": "PASS",
                                      "line": "2026-01-06 PASS cef ok"}},
            "equity": {"value": {"date": "2026-01-06", "equity": equity,
                                 "read_at_utc": None, "source": "x"}}}


@pytest.fixture
def book_state(monkeypatch, tmp_path):
    import book_state as bs
    monkeypatch.setattr(bs, "VM_CACHE", tmp_path / "vm-cache.json")
    monkeypatch.setattr(bs, "_git", lambda *a: "")
    return bs


def _wire(monkeypatch, bs, laptop, vm, behind=0):
    calls = {}

    def fake_vm(**kw):
        calls["vm"] = kw
        return vm
    monkeypatch.setattr(bs.ps, "laptop", lambda **kw: laptop)
    monkeypatch.setattr(bs.ps, "vm", fake_vm)
    # The real checkout's distance from origin/main is not this test's input (release check of
    # 93021c8: a branch behind main printed its stale-checkout WARNING above the one under test).
    monkeypatch.setattr(bs.checkout, "against_main",
                        lambda repo: {"behind": behind, "ahead": 0, "last_fetch": None})
    return calls


def _banner(monkeypatch, capsys, bs, laptop, vm, behind=0):
    calls = _wire(monkeypatch, bs, laptop, vm, behind)
    mod = _load("session_context")
    monkeypatch.setattr(mod, "collect", bs.collect)
    assert mod.main() == 0
    return capsys.readouterr().out, calls


class TestBanner:
    def test_laptop_armed(self, monkeypatch, capsys, book_state):
        out, _ = _banner(monkeypatch, capsys, book_state, _m("ARMED"), _m("DRY"))
        assert "Prod is the laptop: ARMED" in out
        assert "Live equity $222.22: snapshot read after the 2026-01-06 close" in out
        assert "broker-confirmed" not in out             # the 2026-10-19 ruling: a snapshot
        assert "NO LIVE BOOK" not in out

    def test_laptop_disarmed(self, monkeypatch, capsys, book_state):
        out, _ = _banner(monkeypatch, capsys, book_state, _m("DRY"), _m("DRY"))
        assert "No machine is measured armed" in out and "nothing is sent" in out

    def test_vm_unreachable_is_unmeasured(self, monkeypatch, capsys, book_state):
        vm = book_state.ps.vm_unmeasured("`ssh ... quantt-vm 'sh -s'` did not finish within 3s")
        out, _ = _banner(monkeypatch, capsys, book_state, _m("ARMED"), vm)
        assert "VM (systemd): UNMEASURED" in out and "did not finish within 3s" in out
        assert "not ruled out" in out

    def test_both_armed_warns_first(self, monkeypatch, capsys, book_state):
        out, _ = _banner(monkeypatch, capsys, book_state, _m("ARMED"), _m("ARMED"))
        first_state_line = out.splitlines()[1]
        assert first_state_line.strip().startswith("WARNING: TWO ARMED SCHEDULERS")

    def test_two_armed_outranks_a_stale_checkout(self, monkeypatch, capsys, book_state):
        out, _ = _banner(monkeypatch, capsys, book_state, _m("ARMED"), _m("ARMED"), behind=5)
        lines = out.splitlines()
        assert lines[1].strip().startswith("WARNING: TWO ARMED SCHEDULERS")
        assert any("5 commit(s) behind origin/main" in l for l in lines[2:])

    def test_vm_budget_is_short(self, monkeypatch, capsys, book_state):
        """A session start waits on the VM for at most ~3 s."""
        _, calls = _banner(monkeypatch, capsys, book_state, _m("DRY"), _m("DRY"))
        assert calls["vm"]["timeout"] <= 3


class TestStatusLine:
    def test_never_opens_ssh(self, monkeypatch, tmp_path, book_state):
        """It re-renders on every message; the VM part is the banner's cache."""
        def no_ssh(**kw):
            raise AssertionError("the status line called prod_state.vm")
        monkeypatch.setattr(book_state.ps, "laptop", lambda **kw: _m("DRY"))
        monkeypatch.setattr(book_state.ps, "vm", no_ssh)
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        sl = _load("statusline")
        state = sl.cached_book_state("test-session")
        assert state["prod"]["machines"]["vm"]["arming"] == "UNMEASURED"

    def test_shows_the_banners_vm_reading_with_its_age(self, book_state):
        book_state._write_vm_cache(_m("ARMED"), now=1000.0)
        got = book_state._read_vm_cache(now=1000.0 + 120)
        assert got["arming"] == "ARMED" and got["cached_age_s"] == 120

    def test_a_stale_vm_reading_is_not_shown_as_current(self, book_state):
        book_state._write_vm_cache(_m("ARMED"), now=1000.0)
        got = book_state._read_vm_cache(now=1000.0 + book_state.VM_CACHE_MAX_AGE_S + 1)
        assert got["arming"] == "UNMEASURED" and "min old" in got["UNMEASURED"]

    def test_laptop_armed_segment(self, monkeypatch, book_state):
        _wire(monkeypatch, book_state, _m("ARMED"), _m("DRY"))
        seg = _load("statusline").book_segment(book_state.collect(vm="live"))
        assert "prod" in seg and "laptop ARMED" in seg and "01-06 PASS" in seg

    def test_both_armed_segment(self, monkeypatch, book_state):
        _wire(monkeypatch, book_state, _m("ARMED"), _m("PER_DAY"))
        seg = _load("statusline").book_segment(book_state.collect(vm="live"))
        assert "TWO ARMED" in seg

    def test_unreadable_state_is_red_not_blank(self):
        seg = _load("statusline").book_segment({})
        assert "prod ?" in seg and "no live book" not in seg
