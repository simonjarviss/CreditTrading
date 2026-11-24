"""The collector's books: the core unchanged since cee16ad, and C4's `BOOKS["c4"]` (plan step 3, DARK).

THE CORE IS UNCHANGED. cee16ad's collect.py (from git,
scripts/cef/tests/noop_base.py) and this one run the same days on the same fake
client, fake subprocess runner and fake CEFConnect, with `_utc_now` frozen:
every return code, printed line, subprocess command, client call and file
written under the state and panel directories (status.json, report.json,
data.log, equity.csv, eod_equity.csv, account.json, assets.parquet, the
official-close file, cefconnect_arrival.csv) is identical, byte for byte. Plus
a pin of the core's BOOKS entry and its build_ctx.

C4 IS READ-ONLY, CEFCONNECT-FREE AND OFF. `--book c4` runs its own steps (no
CEFConnect step at all; a reader that raises if one were reached), passes
`--data-book c4` to both fetchers, records official closes for the 74 alone,
reports M1's repeats from the panel, flags fetch_daily's spike exit, fails
`eod_equity` rather than invent an account start, refuses another book's state
directory, and is named by no deployment file. Each of these fails on cee16ad.

Hermetic: the fakes of test_collect.py (GETs only; no transmit method exists),
tmp_path only, and netguard refuses any socket.
"""
import datetime as dt
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from quantt.collect import collect as co
from quantt.collect.tests.test_collect import (D, DEPLOYED, PREV, FakeClient, FakeRun, et,
                                               write_panels)
from scripts.cef import data_books as db
from scripts.cef.tests.noop_base import load_at_base

REPO = Path(__file__).resolve().parents[3]
FROZEN_UTC = "2026-09-30T01:30:00+00:00"


def snapshot(*dirs) -> dict:
    return {str(p.relative_to(d.parent)): p.read_bytes()
            for d in dirs for p in sorted(d.rglob("*")) if p.is_file()}


def core_day(mod, monkeypatch, root: Path, plan):
    """Run `plan` -- a list of (FakeRun codes, cefconnect values, client kwargs)
    -- one collect() each, through module `mod`, in `root`."""
    state, cef = root / "state", root / "cef"
    state.mkdir(parents=True)
    cef.mkdir()
    write_panels(cef, close={"AAA": 9.50, "BBB": 19.10})
    pd.DataFrame([{"date": pd.Timestamp(PREV), "nav": 20.00, "ticker": "BBB"},
                  {"date": pd.Timestamp(D), "nav": 10.00, "ticker": "AAA"},
                  {"date": pd.Timestamp(D), "nav": 20.00, "ticker": "BBB"}]
                 ).to_parquet(cef / "cef_nav.parquet")
    monkeypatch.setattr(mod, "_utc_now", lambda: FROZEN_UTC)
    rcs, lines, cmds, calls = [], [], [], []
    for codes, cc, kw in plan:
        client, run = FakeClient(**kw), FakeRun(codes)

        def cefconnect(t, day, cc=cc):
            v = cc[t]
            if isinstance(v, Exception):
                raise v
            return v
        ctx = mod.Ctx(book="cef", client=client, state_dir=state, cef_dir=cef,
                      repo=Path("/nonexistent"), book_path="ops/books/cef_discount_book.json",
                      deployed=list(DEPLOYED), run=run, cefconnect_nav=cefconnect)
        rcs.append(mod.collect(ctx, out=lines.append))
        cmds.append(run.cmds)
        calls.append(client.calls)
    return rcs, lines, cmds, calls, snapshot(state, cef)


PLANS = {
    "complete, then idle": [({}, {"AAA": 10.02, "BBB": 20.00}, {}),
                            ({}, {"AAA": 10.02, "BBB": 20.00}, {})],
    "fetch_daily exits 4, then 0": [({"fetch_daily.py": 4}, {"AAA": 10.0, "BBB": None}, {}),
                                    ({}, {"AAA": 10.0, "BBB": 20.0}, {})],
    "a repeat CEFConnect cannot confirm, a missing print, CEFConnect down": [
        ({}, {"AAA": co.CefConnectError("down"), "BBB": None}, {"prints": {"AAA": 9.5}}),
        ({"fetch_cef_distributions.py": 1}, {"AAA": 10.0, "BBB": None}, {})],
    "the account no longer describes D": [({}, {"AAA": 10.0, "BBB": 20.0},
                                           {"is_open": True, "now": et(D, 21, 0)})],
}


@pytest.mark.parametrize("name", list(PLANS))
def test_the_cef_collector_is_byte_identical_to_cee16ad(name, tmp_path, monkeypatch):
    base = load_at_base("quantt/collect/collect.py", "collect_cee16ad", tmp_path, monkeypatch)
    b = core_day(base, monkeypatch, tmp_path / "run_base", PLANS[name])
    n = core_day(co, monkeypatch, tmp_path / "run_new", PLANS[name])
    for i, what in enumerate(("exit codes", "printed lines", "subprocess commands",
                              "client calls", "files written")):
        assert n[i] == b[i], f"{name}: {what} differ from cee16ad"
    assert any("cefconnect_arrival.csv" in k or "report.json" in k for k in b[4])


def test_the_cef_book_entry_and_its_steps_are_pinned():
    assert co.STEPS == ("prices_nav", "nav_crosscheck", "official_closes", "close_crosscheck",
                        "account_snapshot", "distributions", "borrow_snapshot",
                        "cefconnect_arrival", "eod_equity")
    assert co.BOOKS["cef"] == {"book_path": "ops/books/cef_discount_book.json",
                               "eod_from": dt.date(2026, 9, 28), "steps": co.STEPS,
                               "data_book": None, "close_universe": "cef_universe.csv",
                               "spike_flag": False, "state_dir_name": None}
    assert co.WATCH_STEPS == ("cefconnect_arrival",)


class FakeAlpaca:
    @classmethod
    def from_environment(cls, book):
        return ("client for", book)


def test_build_ctx_for_the_core_is_unchanged_and_for_c4_reads_the_data_book(monkeypatch, tmp_path):
    from quantt.broker import alpaca
    from scripts.cef.spec import frozen
    monkeypatch.setattr(alpaca, "AlpacaClient", FakeAlpaca)
    core = co.build_ctx("cef", tmp_path)
    assert (core.client, core.cef_dir, core.book_path, core.deployed, core.cefconnect_nav) == (
        ("client for", "cef"), REPO / "data" / "cef", "ops/books/cef_discount_book.json",
        sorted(frozen("universe")), co.cefconnect_nav)
    c4 = co.build_ctx("c4", tmp_path)
    assert (c4.client, c4.cef_dir, c4.book_path) == (("client for", "c4"), REPO / "data" / "cef_c4", None)
    assert c4.deployed == sorted(db.c4_universe()) and len(c4.deployed) == 74
    with pytest.raises(db.CefConnectDisabled):
        c4.cefconnect_nav("ADX", D)


# --------------------------------------------------------------------------- C4

C4_DEP = ["ADX", "EVT"]


def c4_env(tmp_path, nav=None, prev_nav=None):
    """C4's state dir (named c4) and panel dir (no cef_universe.csv in it)."""
    state, cef = tmp_path / "c4", tmp_path / "cef_c4"
    state.mkdir(parents=True)
    cef.mkdir()
    nav = nav or {"ADX": 10.00, "EVT": 20.00}
    rows = [{"date": pd.Timestamp(D), "nav": v, "ticker": t} for t, v in nav.items()]
    rows += [{"date": pd.Timestamp(PREV), "nav": v, "ticker": t} for t, v in (prev_nav or {}).items()]
    pd.DataFrame(rows).to_parquet(cef / "cef_nav.parquet")
    pd.DataFrame([{"date": pd.Timestamp(D), "open": v, "high": v, "low": v, "close": v, "volume": 1,
                   "ticker": t, "grp": "x"} for t, v in {"ADX": 9.50, "EVT": 19.00}.items()]
                 ).to_parquet(cef / "cef_prices.parquet")
    return state, cef


def c4_client():
    """test_collect's fake, with the C4 names' prints and borrow flags."""
    c = FakeClient(prints={"ADX": 9.50, "EVT": 19.00})
    c.flags = {"ADX": (True, True, True), "EVT": (True, False, False)}
    return c


def c4_ctx(env, client=None, run=None):
    state, cef = env
    return co.Ctx(book="c4", client=client or c4_client(),
                  state_dir=state, cef_dir=cef, repo=Path("/nonexistent"), book_path=None,
                  deployed=list(C4_DEP), run=run or FakeRun(),
                  cefconnect_nav=db.refuse_cefconnect("c4"))


def status(state):
    import json
    return json.loads((state / "data" / D.isoformat() / "status.json").read_text())


def test_c4_runs_its_own_steps_with_no_cefconnect_and_both_fetchers_get_its_data_book(tmp_path):
    env = c4_env(tmp_path)
    client, run = c4_client(), FakeRun()
    lines = []
    rc = co.collect(c4_ctx(env, client, run), out=lines.append)
    s = status(env[0])["steps"]
    assert set(s) == set(co.C4_STEPS) and len(co.C4_STEPS) == 8
    assert not {"nav_crosscheck", "cefconnect_arrival"} & set(s)
    assert all(s[k]["ok"] for k in co.C4_STEPS if k != "eod_equity"), s
    fd_cmd, dist_cmd = run.cmds
    assert fd_cmd[1:] == ["scripts/cef/fetch_daily.py", "--require-asof", D.isoformat(),
                          "--data-book", "c4"]
    assert "--nav-fallback" not in fd_cmd and "--book" not in fd_cmd
    assert dist_cmd[1:] == ["scripts/fetch_cef_distributions.py", "--data-book", "c4"]
    prints = [c[1] for c in client.calls if isinstance(c, tuple) and c[0] == "prints"]
    assert prints == C4_DEP, "official closes asked beyond the 74 (there is no cef_universe.csv here)"
    assert (env[1] / co.OFFICIAL_CLOSE_FILE).exists() and (env[0] / "equity.csv").exists()
    # eod_from is not recorded for C4: the step fails, naming it, and reads nothing.
    assert not s["eod_equity"]["ok"] and "eod_from" in s["eod_equity"]["err"]
    assert not [c for c in client.calls if isinstance(c, tuple) and c[0] == "eod"]
    assert rc == co.EXIT_INCOMPLETE and lines == [f"{D} DATA INCOMPLETE eod_equity flags=0 gaps=0"]


def test_c4_with_its_account_start_recorded_completes(tmp_path, monkeypatch):
    monkeypatch.setitem(co.BOOKS["c4"], "eod_from", dt.date(2026, 9, 28))
    env = c4_env(tmp_path)
    assert co.collect(c4_ctx(env)) == co.EXIT_OK
    assert (env[0] / "data.log").read_text() == f"{D} DATA COMPLETE flags=0 gaps=0\n"


def test_c4_nav_repeats_are_flags_and_a_missing_nav_a_gap(tmp_path):
    env = c4_env(tmp_path, nav={"ADX": 10.00}, prev_nav={"ADX": 10.00, "EVT": 19.90})
    co.collect(c4_ctx(env))
    d = status(env[0])["steps"]["nav_repeats"]
    assert d["ok"]
    (f,) = d["detail"]["flags"]
    assert (f["fund"], f["check"], f["value_a"], f["value_b"]) == ("ADX", "nav_repeat_m1", 10.0, 10.0)
    assert d["detail"]["gaps"] == [{"fund": "EVT", "reason": f"cef_nav.parquet has no NAV dated {D}"}]


def test_c4_spike_exit_is_a_flag_and_the_cross_checks_still_run(tmp_path):
    env = c4_env(tmp_path)
    co.collect(c4_ctx(env, run=FakeRun({"fetch_daily.py": 6})))
    s = status(env[0])["steps"]
    assert s["prices_nav"]["ok"] and s["nav_repeats"]["ok"] and s["close_crosscheck"]["ok"]
    (f,) = s["prices_nav"]["detail"]["flags"]
    assert f["check"] == "spike_revert" and s["prices_nav"]["detail"]["exit"] == 6


def test_c4_spike_exit_with_the_pair_incomplete_is_a_flag_and_a_failed_step(tmp_path):
    """fetch_daily's unruled spike outranks its INCOMPLETE since the release-check of 8b14298,
    so an exit 6 can carry an incomplete pair. Then the step is not done: it fails, as an
    exit 4 does, and the spike is still flagged. The prefix is fetch_daily's own."""
    from scripts.cef import fetch_daily as fd
    assert co.FETCH_INCOMPLETE_TAG == fd.INCOMPLETE_TAG

    class Run(FakeRun):
        def __call__(self, cmd, timeout_s):
            code, out = super().__call__(cmd, timeout_s)
            if Path(cmd[1]).name == "fetch_daily.py":
                out += f"\n  SPIKE-REVERT (data book c4; ...): IGR\n  {fd.INCOMPLETE_TAG} {D} on 1 " \
                       f"deployed name(s): EVT (no NAV dated {D})"
            return code, out
    env = c4_env(tmp_path)
    co.collect(c4_ctx(env, run=Run({"fetch_daily.py": 6})))
    p = status(env[0])["steps"]["prices_nav"]
    assert not p["ok"] and "INCOMPLETE" in p["err"], p
    (f,) = p["detail"]["flags"]
    assert f["check"] == "spike_revert" and p["detail"]["exit"] == 6


def test_on_the_core_exit_6_is_still_a_failure(tmp_path):
    state, cef = tmp_path / "state", tmp_path / "cef"
    state.mkdir()
    cef.mkdir()
    write_panels(cef)
    ctx = co.Ctx(book="cef", client=FakeClient(), state_dir=state, cef_dir=cef,
                 repo=Path("/nonexistent"), book_path="ops/books/cef_discount_book.json",
                 deployed=list(DEPLOYED), run=FakeRun({"fetch_daily.py": 6}),
                 cefconnect_nav=lambda t, d: {"AAA": 10.0, "BBB": 20.0}[t])
    co.collect(ctx)
    p = status(state)["steps"]["prices_nav"]
    assert not p["ok"] and p["err"] == "fetch_daily exited 6"


def test_c4_refuses_a_state_directory_that_is_not_its_own(tmp_path, capsys):
    core_state = tmp_path / "cef"
    core_state.mkdir()
    rc = co.main(["--book", "c4"], env={"QUANTT_STATE_DIR": str(core_state)},
                 make_ctx=lambda *a: pytest.fail("built a context in another book's state dir"))
    assert rc == co.EXIT_UNEXPECTED and list(core_state.iterdir()) == []
    assert "needs its own state directory" in capsys.readouterr().err
    own = tmp_path / "c4"
    own.mkdir()
    env = c4_env(tmp_path / "x")
    built = []

    def make(book, sd):
        built.append((book, sd))
        return c4_ctx((sd, env[1]))
    co.main(["--book", "c4"], env={"QUANTT_STATE_DIR": str(own)}, make_ctx=make)
    assert built == [("c4", own)]


def test_only_the_installers_opt_in_book_schedules_a_c4_collect():
    """DEFAULT OFF, as built at the installer step (C4 integration, 2026-10-29).
    Under quantt/deploy only install_vm.py's C4 entry and the quantt-c4-*
    templates name C4; the laptop installer names none; and install_vm installs
    C4's units only when told `--book c4` (its default is the core:
    quantt/deploy/tests/test_install_vm_books.py, which installs and checks it)."""
    from quantt.deploy import install_vm as iv
    named = []
    for p in sorted((REPO / "quantt" / "deploy").rglob("*")):
        if p.is_file() and "tests" not in p.parts and p.suffix != ".pyc":
            if re.search(r"\bc4\b|cef_c4", p.read_text(errors="replace"), re.I):
                named.append(str(p.relative_to(REPO)))
    c4_templates = sorted(f"{iv.TEMPLATE_DIR}/{u}.tmpl" for u in iv.C4_VM.unit_files)
    assert named == sorted(["quantt/deploy/install_vm.py", *c4_templates])
    assert iv.BOOK == "cef" and iv.CORE_VM.unit_files == iv.ALL_UNIT_FILES


def test_c4_reads_its_account_start_from_the_installers_environment(tmp_path):
    """The installer's --eod-from reaches the collector as QUANTT_EOD_FROM, and
    the official series is read from that date; a malformed value, or one set
    for the core (which records its own start), stops the run before anything
    is written."""
    own = tmp_path / "c4"
    own.mkdir()
    env = c4_env(tmp_path / "x")
    client = c4_client()

    def make(book, sd):
        return c4_ctx((sd, env[1]), client)
    rc = co.main(["--book", "c4"], env={"QUANTT_STATE_DIR": str(own),
                                         co.EOD_FROM_ENV: "2026-09-29"}, make_ctx=make)
    s = json.loads((own / "data" / D.isoformat() / "status.json").read_text())["steps"]
    assert s["eod_equity"]["ok"], s["eod_equity"]
    assert [c[1] for c in client.calls if isinstance(c, tuple) and c[0] == "eod"] == \
        [dt.date(2026, 9, 29)]
    assert rc == co.EXIT_OK
    for i, bad in enumerate(("2026-9-29", "yesterday", "")):
        other = tmp_path / f"bad{i}" / "c4"
        other.mkdir(parents=True)
        rc = co.main(["--book", "c4"], env={"QUANTT_STATE_DIR": str(other), co.EOD_FROM_ENV: bad},
                     make_ctx=lambda *a: pytest.fail("built a context on a malformed start"))
        assert rc == co.EXIT_UNEXPECTED and list(other.iterdir()) == [], bad
    core_state = tmp_path / "cef"
    core_state.mkdir()
    rc = co.main(["--book", "cef"], env={"QUANTT_STATE_DIR": str(core_state),
                                          co.EOD_FROM_ENV: "2026-09-29"},
                 make_ctx=lambda *a: pytest.fail("the core must refuse a second start"))
    assert rc == co.EXIT_UNEXPECTED and list(core_state.iterdir()) == []
    assert co.eod_from_from_env("cef", {}) is None and co.eod_from_from_env("c4", {}) is None