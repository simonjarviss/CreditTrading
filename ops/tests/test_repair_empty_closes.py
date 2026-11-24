"""ops/repair_empty_closes.py: the one-off repair of prod's empty ex-date closes.

WHY. Until release-20261028-1, fetch_daily wrote yfinance's empty ex-date rows
(every price NaN, volume 0) over good bars; prod's panel kept 91 of them from
2026-02-12 to 2026-04-23, older than the fetcher's refetch window, so nothing
will repair them by itself. The tool that does writes the one file the live
sleeve decides on, on the prod VM, so every guard in its docstring is pinned
here: a dry run writes nothing; an apply fills only empty closes, only from the
collector's primary source (Alpaca's official closing print), logs each one,
and refuses on a filled cell, a backup collision, a running job, a held panel
lock or an unsafe minute; and a failed post-check puts the original bytes back.

Hermetic: every path is under tmp_path, the price source and systemctl are
fakes, the clock and the process table are injected, and the root conftest
blocks the network and any write to a live panel directory.

The rehearsal on a copy of prod's real panel runs only when
QUANTT_REPAIR_REHEARSAL_PANEL names one (the repo holds no market data).
"""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import ops.common as common
from ops import repair_empty_closes as rep
from quantt.broker import alpaca as al
from quantt.deploy import install_vm as iv

UTC = dt.timezone.utc
ET = rep.ET


def et(y, mo, d, h, mi, s=0):
    return dt.datetime(y, mo, d, h, mi, s, tzinfo=ET).astimezone(UTC)


# Wednesday 2026-10-28, 10:15 ET: the collector fired at 10:10 (5 minutes ago),
# the session fires at 10:30 (15 minutes ahead). Guard 8 passes even with the
# timers running.
SAFE = et(2026, 10, 28, 10, 15)

COLS = ["date", "open", "high", "low", "close", "volume", "ticker", "grp"]
EMPTY = (("AAA", "2026-02-12"), ("BBB", "2026-02-13"), ("CCC", "2026-02-13"))
PRINTS = {("AAA", "2026-02-12"): 10.01, ("BBB", "2026-02-13"): 12.02}   # CCC has none


def make_panel(path: Path, extra_dates=()) -> pd.DataFrame:
    """Prod's schema exactly (column order, dtypes, sorted by ticker then date,
    RangeIndex), with three empty rows in yfinance's signature."""
    dates = pd.to_datetime(["2026-02-11", "2026-02-12", "2026-02-13", "2026-02-17", *extra_dates])
    rows = []
    for tk, grp, base in (("AAA", "hy", 10.0), ("BBB", "muni", 12.0), ("CCC", "loan", 8.0)):
        for k, d in enumerate(dates):
            c = base + 0.01 * k
            rows.append(dict(date=d, open=c - 0.02, high=c + 0.03, low=c - 0.04, close=c,
                             volume=1000 + k, ticker=tk, grp=grp))
    P = pd.DataFrame(rows)[COLS]
    for tk, d in EMPTY:
        m = (P.ticker == tk) & (P.date == d)
        P.loc[m, ["open", "high", "low", "close"]] = np.nan
        P.loc[m, "volume"] = 0
    P = P.sort_values(["ticker", "date"]).reset_index(drop=True)
    assert str(P.volume.dtype) == "int64"
    P.to_parquet(path, index=False)
    return P


class FakeClient:
    """The GET surface the repair uses, in AlpacaClient's parsed shapes. No
    transmit method. Records every question it is asked."""

    def __init__(self, prints=None, no_asset=(), transient=(), on_print=None):
        self.prints = dict(PRINTS if prints is None else prints)
        self.no_asset, self.transient, self.on_print = set(no_asset), set(transient), on_print
        self.asked = []

    def stock_exchanges(self):
        return {"N": "New York Stock Exchange", "P": "NYSE Arca"}

    def primary_sip_code(self, symbol, exchanges):
        if symbol in self.no_asset:
            raise al.AssetNotFound(f"GET /v2/assets/{symbol} -> HTTP 404", status=404)
        return "N"

    def closing_auction_prints(self, symbols, date, *, exchange_codes, condition="M"):
        assert len(symbols) == 1 and exchange_codes == {symbols[0]: "N"} and condition == "M"
        sym = symbols[0]
        self.asked.append((sym, date.isoformat()))
        if self.on_print:
            self.on_print(sym, date)
        if (sym, date.isoformat()) in self.transient:
            raise al.AlpacaHTTPError("GET /v2/stocks/auctions failed after 5 attempts", status=503)
        p = self.prints.get((sym, date.isoformat()))
        if p is None:
            raise al.MissingAuctionPrint(f"no print for {symbols} on {date}", symbols=[sym])
        return {sym: {"price": p, "exchange": "N", "condition": "M",
                      "t": f"{date.isoformat()}T20:00:01.5Z"}}


class FakeSystemd:
    """`systemctl show <unit> -p ...` as install_vm parses it. Every job
    service idle and every timer `timers` unless told otherwise."""

    def __init__(self, timers="active", services=None, jobs=None, fail=False):
        self.timers, self.services = timers, dict(services or {})
        self.jobs, self.fail = dict(jobs or {}), fail
        self.calls = []

    def __call__(self, args):
        self.calls.append(list(args))
        assert args[:2] == ["systemctl", "show"], args
        if self.fail:
            return SimpleNamespace(returncode=1, stdout="", stderr="Failed to connect to bus")
        unit = args[2]
        props = [args[i + 1] for i, a in enumerate(args) if a == "-p"]
        if unit.endswith(".timer"):
            state = self.timers
        elif unit == iv.SECRET_UNIT:
            state = self.services.get(unit, "active")      # RemainAfterExit: normal
        else:
            state = self.services.get(unit, "inactive")
        vals = {"ActiveState": state, "Job": self.jobs.get(unit, ""), "MainPID": "0"}
        return SimpleNamespace(returncode=0, stderr="",
                               stdout="".join(f"{p}={vals[p]}\n" for p in props))


@pytest.fixture
def world(tmp_path):
    cef = tmp_path / "prod" / "data" / "cef"
    cef.mkdir(parents=True)
    panel = cef / "cef_prices.parquet"
    make_panel(panel)
    state = tmp_path / "state"
    (state / "logs").mkdir(parents=True)
    return SimpleNamespace(tmp=tmp_path, panel=panel, lock=cef / ".fetch.lock",
                           log=state / "logs" / rep.LOG_NAME, original=panel.read_bytes())


def make_ctx(w, **kw) -> rep.Ctx:
    base = dict(panel=w.panel, lock=w.lock, log=w.log, client=FakeClient(),
                run_cmd=FakeSystemd(), now=lambda: SAFE, procs=lambda: [],
                write=lambda frame, path: common.atomic_write(frame, path),
                live=frozenset({"AAA"}), code="test tree", lock_wait_s=0.2)
    base.update(kw)
    return rep.Ctx(**base)


def run(ctx, *argv):
    lines = []
    code = rep.main(list(argv), make_ctx=lambda env: ctx, env={}, out=lines.append)
    return code, "\n".join(lines)


def digest_of(text: str) -> str:
    [d] = [ln.split()[-1] for ln in text.splitlines() if ln.strip().startswith("plan digest")]
    return d


def dry_then_apply(w, **kw):
    code, out = run(make_ctx(w, **kw))
    assert code == 0, out
    return run(make_ctx(w, **kw), "--apply", "--plan", digest_of(out))


def tree(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}


def log_records(w) -> list:
    return [json.loads(ln) for ln in w.log.read_text().splitlines()] if w.log.exists() else []


def assert_untouched(w):
    assert w.panel.read_bytes() == w.original, "the panel was written"
    assert not list(w.panel.parent.glob("*.bak")), "a backup was made"
    assert not [r for r in log_records(w) if r["event"] == "REPAIRED"]


def cell(P, tk, d):
    r = P[(P.ticker == tk) & (P.date == d)]
    assert len(r) == 1
    return r.iloc[0]


# ---------------------------------------------------------------- guard 1: dry run

@pytest.mark.parametrize("argv", [(), ("--dry-run",)])
def test_dry_run_writes_nothing_and_lists_every_planned_cell(world, argv):
    before = tree(world.tmp)
    code, out = run(make_ctx(world), *argv)
    assert code == 0, out
    assert tree(world.tmp) == before, "a dry run created or changed a file"
    assert not world.lock.exists() and not world.log.exists()
    # every planned cell: date, ticker, the close it would write, the source
    assert "PLAN         2026-02-12 AAA*  close nan -> 10.01" in out
    assert "PLAN         2026-02-13 BBB   close nan -> 12.02" in out
    assert out.count("alpaca official close: GET /v2/stocks/auctions feed=sip, primary "
                     "exchange N, condition M") == 2
    assert "NO PRINT     2026-02-13 CCC   left empty: MissingAuctionPrint" in out
    assert "--apply --plan " in out


def test_apply_needs_the_reviewed_plan(world):
    with pytest.raises(SystemExit):
        run(make_ctx(world), "--apply")                     # no digest: usage error
    code, out = run(make_ctx(world), "--apply", "--plan", "000000000000")
    assert code == rep.EXIT_REFUSED and "is not this run's plan" in out
    assert_untouched(world)


# ---------------------------------------------------------------- guards 4-7: the apply

def test_apply_fills_only_the_empty_closes_and_logs_each_one(world):
    old = pd.read_parquet(world.panel)
    code, out = run(make_ctx(world))
    plan = digest_of(out)
    # Between the dry run and the apply, the collector appends a day: rows are
    # inserted mid-panel (it is sorted by ticker), so cells must be found by
    # (date, ticker), never by row number.
    make_panel(world.panel, extra_dates=["2026-10-27"])
    old = pd.read_parquet(world.panel)
    original = world.panel.read_bytes()
    client = FakeClient()
    code, out = run(make_ctx(world, client=client), "--apply", "--plan", plan)
    assert code == 0, out
    # the source was asked about the empty cells and nothing else
    assert sorted(client.asked) == sorted(EMPTY)
    new = pd.read_parquet(world.panel)
    assert list(new.columns) == COLS and len(new) == len(old)
    assert (new.dtypes == old.dtypes).all()
    assert cell(new, "AAA", "2026-02-12").close == 10.01
    assert cell(new, "BBB", "2026-02-13").close == 12.02
    assert np.isnan(cell(new, "CCC", "2026-02-13").close)          # no print: left empty
    for tk, d in EMPTY:                     # the print has no open/high/low/volume
        r = cell(new, tk, d)
        assert np.isnan([r.open, r.high, r.low]).all() and r.volume == 0
    # every other cell byte-identical
    changed = ~np.isclose(new.close.fillna(-1), old.close.fillna(-1), rtol=0, atol=0)
    assert sorted(zip(new.ticker[changed], new.date[changed].dt.strftime("%Y-%m-%d"))) == \
        [("AAA", "2026-02-12"), ("BBB", "2026-02-13")]
    for c in COLS:
        keep = ~changed if c == "close" else slice(None)
        assert rep._same_cells(new[c][keep], old[c][keep]).all(), c
    # backup: the original bytes, beside the panel
    [bak] = world.panel.parent.glob("cef_prices.parquet.pre-repair-*.bak")
    assert bak.read_bytes() == original
    # one log line per written cell, with date, ticker, old row, new row, source, UTC time
    recs = log_records(world)
    rep_lines = [r for r in recs if r["event"] == "REPAIRED"]
    assert [(r["date"], r["ticker"]) for r in rep_lines] == [("2026-02-12", "AAA"),
                                                           ("2026-02-13", "BBB")]
    a = rep_lines[0]
    assert a["old"]["close"] == "nan" and a["new"]["close"] == 10.01
    assert a["old"]["volume"] == 0 == a["new"]["volume"] and a["new"]["open"] == "nan"
    assert a["source"].startswith("alpaca official close") and a["utc"].endswith("+00:00")
    [summary] = [r for r in recs if r["event"] == "RUN"]
    sha = lambda b: hashlib.sha256(b).hexdigest()               # noqa: E731
    assert summary["sha256_panel_before"] == summary["sha256_backup"] == sha(original)
    assert summary["sha256_panel_after"] == sha(world.panel.read_bytes()) != sha(original)
    assert summary["written"] == 2


def test_a_cell_filled_by_the_time_of_the_write_is_refused(world):
    """The collector (or anything) fills AAA's close after the plan was read:
    the re-read under the lock must refuse, not overwrite it."""
    code, out = run(make_ctx(world))
    plan = digest_of(out)

    def someone_fills_aaa(sym, date):
        if sym == "AAA":
            P = pd.read_parquet(world.panel)
            P.loc[(P.ticker == "AAA") & (P.date == "2026-02-12"), "close"] = 10.00
            common.atomic_write(P, world.panel)

    code, out = run(make_ctx(world, client=FakeClient(on_print=someone_fills_aaa)),
                    "--apply", "--plan", plan)
    assert code == rep.EXIT_REFUSED, out
    assert "2026-02-12 AAA: ALREADY FILLED at write time" in out
    P = pd.read_parquet(world.panel)
    assert cell(P, "AAA", "2026-02-12").close == 10.00              # theirs, not ours
    assert np.isnan(cell(P, "BBB", "2026-02-13").close)             # nothing else written
    assert not list(world.panel.parent.glob("*.bak"))
    assert not log_records(world)


@pytest.mark.parametrize("client, want", [
    (FakeClient(), {("CCC", "2026-02-13"): "NO PRINT"}),
    (FakeClient(no_asset={"BBB"}), {("CCC", "2026-02-13"): "NO PRINT",
                                    ("BBB", "2026-02-13"): "NO PRINT"}),
    (FakeClient(transient={("AAA", "2026-02-12")}), {("CCC", "2026-02-13"): "NO PRINT",
                                                     ("AAA", "2026-02-12"): "NOT MEASURED"}),
], ids=["no-print", "asset-not-found", "transient-error"])
def test_a_cell_with_no_print_is_left_empty_and_reported(world, client, want):
    code, out = run(make_ctx(world, client=client))
    for (tk, d), kind in want.items():
        assert f"{kind:<12} {d} {tk}" in out and "left empty" in out
    code, out = run(make_ctx(world, client=client), "--apply", "--plan", digest_of(out))
    assert code == 0, out
    P = pd.read_parquet(world.panel)
    for tk, d in want:
        assert np.isnan(cell(P, tk, d).close), f"{tk} {d} was filled without a print"
    [summary] = [r for r in log_records(world) if r["event"] == "RUN"]
    assert {(g["ticker"], g["date"]): g["kind"] for g in summary["left_empty"]} == want
    assert summary["written"] == len(EMPTY) - len(want)


# ---------------------------------------------------------------- guard 3: backup

def test_a_backup_collision_refuses(world):
    clash = rep.backup_path(world.panel, SAFE)
    clash.write_bytes(b"an earlier backup that must survive")
    code, out = run(make_ctx(world))
    code, out = run(make_ctx(world), "--apply", "--plan", digest_of(out))
    assert code == rep.EXIT_REFUSED and "already exists" in out, out
    assert clash.read_bytes() == b"an earlier backup that must survive"
    assert world.panel.read_bytes() == world.original
    assert not [r for r in log_records(world) if r["event"] == "REPAIRED"]


# ---------------------------------------------------------------- guard 7: post-check

def _also_corrupts(frame, path):
    """A writer with a bug: it writes the repair AND changes one other cell."""
    bad = frame.copy()
    bad.loc[(bad.ticker == "BBB") & (bad.date == "2026-02-11"), "volume"] += 1
    common.atomic_write(bad, path)


def _invents_ohl(frame, path):
    """A writer with the tempting bug: open = high = low = close on the repaired rows."""
    bad = frame.copy()
    m = bad.open.isna() & bad.close.notna()
    bad.loc[m, ["open", "high", "low"]] = bad.loc[m, "close"].to_numpy()[:, None]
    common.atomic_write(bad, path)


def _dies_half_way(frame, path):
    """A writer that leaves a damaged file and raises."""
    Path(path).write_bytes(b"PAR1 not a parquet file")
    raise OSError("disk full")


@pytest.mark.parametrize("writer", [_also_corrupts, _invents_ohl, _dies_half_way],
                         ids=["other-cell", "invented-ohl", "exception"])
def test_a_post_check_failure_restores_the_backup(world, writer):
    code, out = run(make_ctx(world))
    code, out = run(make_ctx(world, write=writer), "--apply", "--plan", digest_of(out))
    assert code == rep.EXIT_RESTORED, out
    assert "RESTORED the backup" in out
    assert world.panel.read_bytes() == world.original, "the original bytes are not back"
    [fail] = [r for r in log_records(world) if r["event"] == "POSTCHECK FAILED"]
    assert fail["restored"] is True and fail["sha256_now"] == fail["sha256_original"]
    assert not [r for r in log_records(world) if r["event"] == "REPAIRED"]


# ---------------------------------------------------------------- guard 2: jobs and lock

SESSION = "quantt-cef-session.service"
COLLECT = "quantt-cef-collect.service"


def _hold_lock(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    os.pwrite(fd, b"pid 424242 since test\n", 0)
    return fd


@pytest.mark.parametrize("kw, why", [
    (dict(run_cmd=FakeSystemd(services={SESSION: "active"})), "a quantt job is running or queued"),
    (dict(run_cmd=FakeSystemd(jobs={COLLECT: "4711"})), "queued job 4711"),
    (dict(run_cmd=FakeSystemd(services={iv.SECRET_UNIT: "activating"})), "quantt-secret.service activating"),
    (dict(run_cmd=FakeSystemd(fail=True)), "systemd could not be read"),
    (dict(run_cmd=FakeSystemd(timers="deactivating")), "neither running nor stopped"),
    (dict(procs=lambda: [(4242, ["/home/quantt/venv/bin/python", "-m", "quantt.session", "run"])]),
     "a quantt process is running outside systemd"),
    (dict(procs=lambda: [(4243, ["python", "scripts/cef/fetch_daily.py", "--require-asof", "x"])]),
     "fetch_daily.py"),
    ("lock", "the panel lock is held"),
], ids=["session-active", "collect-queued", "keys-activating", "systemctl-fails",
        "timer-state-unknown", "hand-run-session", "hand-run-fetch", "panel-lock-held"])
def test_a_running_job_or_a_held_panel_lock_refuses(world, kw, why):
    code, out = run(make_ctx(world))
    plan = digest_of(out)
    held = None
    if kw == "lock":
        held, kw = _hold_lock(world.lock), {}
    try:
        code, out = run(make_ctx(world, **kw), "--apply", "--plan", plan)
    finally:
        if held is not None:
            os.close(held)
    assert code == rep.EXIT_REFUSED, out
    assert why in out, out
    assert_untouched(world)


def test_a_job_that_starts_after_the_first_check_is_caught_under_the_lock(world):
    """The guards are read again under the lock: a session that starts between
    the first check and the write must still refuse it."""
    code, out = run(make_ctx(world))
    sd = FakeSystemd()
    seen = {"n": 0}

    def show(args):
        r = sd(args)
        if args[2] == SESSION:
            seen["n"] += 1
            if seen["n"] > 1:                    # idle at the first look, active at the second
                r.stdout = r.stdout.replace("ActiveState=inactive", "ActiveState=active")
        return r

    code, out = run(make_ctx(world, run_cmd=show), "--apply", "--plan", digest_of(out))
    assert code == rep.EXIT_REFUSED and "under the lock" in out, out
    assert_untouched(world)


def test_the_real_context_uses_fetch_dailys_panel_and_lock(tmp_path, monkeypatch):
    """Guard 2 is only as good as the lock: it must be fetch_daily's own, the
    one the collector's and the session's refresh take (test_fetch_daily_lock)."""
    import scripts.cef.fetch_daily as fd
    keys = tmp_path / "alpaca.env"
    keys.write_text("ALPACA_CEF_KEY_ID=fake-id\nALPACA_CEF_SECRET_KEY=fake-secret\n")
    (tmp_path / "state").mkdir()
    env = {"QUANTT_STATE_DIR": str(tmp_path / "state"), "QUANTT_ENV_FILE": str(keys)}
    monkeypatch.setenv("QUANTT_ENV_FILE", str(keys))
    ctx = rep.build_ctx(env)                       # constructs only: nothing is read or sent
    assert ctx.lock == fd.LOCK_PATH and ctx.panel == fd.PX_PATH
    assert ctx.log == tmp_path / "state" / "logs" / rep.LOG_NAME
    assert "fake-secret" not in repr(ctx) and "fake-id" not in repr(ctx)
    with pytest.raises(rep.Refused, match="QUANTT_STATE_DIR"):
        rep.build_ctx({"QUANTT_ENV_FILE": str(keys)})


# ---------------------------------------------------------------- guard 8: the clock

@pytest.mark.parametrize("now, timers, why", [
    (et(2026, 10, 28, 15, 45), "inactive", "inside 15:30-16:00 ET"),
    (et(2026, 10, 28, 12, 40), "inactive", "inside 12:30-13:00 ET"),
    (et(2026, 10, 28, 10, 5), "active", "collect 10:10 ET"),
    (et(2026, 10, 28, 10, 25), "active", "session 10:30 ET"),
    (et(2026, 10, 28, 9, 55), "active", "session 10:00 ET"),
    (et(2026, 10, 28, 10, 31), "active", "session 10:30 ET"),       # fired a minute ago
    (et(2026, 10, 28, 17, 22), "active", "verify 17:30 ET"),
], ids=["late-window", "early-close-window", "before-collect", "before-session",
        "before-the-hour", "just-after-a-slot", "before-verify"])
def test_the_time_window_guard_refuses(world, now, timers, why):
    code, out = run(make_ctx(world, now=lambda: now, run_cmd=FakeSystemd(timers=timers)))
    assert "an apply would REFUSE" in out and why in out, out
    code, out = run(make_ctx(world, now=lambda: now, run_cmd=FakeSystemd(timers=timers)),
                    "--apply", "--plan", digest_of(out))
    assert code == rep.EXIT_REFUSED and why in out, out
    assert_untouched(world)


@pytest.mark.parametrize("now, timers", [
    (et(2026, 10, 28, 10, 15), "active"),       # between slots, timers running
    (et(2026, 10, 28, 10, 45), "active"),
    (et(2026, 10, 28, 10, 5), "inactive"),      # near a slot, but the timers are stopped
    (et(2026, 10, 31, 15, 45), "inactive"),     # a Saturday: no send window
], ids=["between-slots", "between-slots-2", "timers-stopped", "weekend"])
def test_the_time_window_guard_allows_the_safe_minutes(world, now, timers):
    code, out = run(make_ctx(world, now=lambda: now, run_cmd=FakeSystemd(timers=timers)))
    assert "guards now: " in out and "pass" in out, out
    code, out = run(make_ctx(world, now=lambda: now, run_cmd=FakeSystemd(timers=timers)),
                    "--apply", "--plan", digest_of(out))
    assert code == 0, out


def test_the_window_is_read_again_at_the_moment_of_writing(world):
    """10:19:30 passes (the 10:30 session is 10.5 minutes off); by the time the
    lock is taken it is 10:20:30, inside the margin, and the write is refused."""
    early, late = et(2026, 10, 28, 10, 19, 30), et(2026, 10, 28, 10, 20, 30)
    code, out = run(make_ctx(world, now=lambda: early))
    plan = digest_of(out)
    assert not world.lock.exists()
    # The clock moves on once the panel lock is taken (panel_lock creates the file).
    clock = lambda: late if world.lock.exists() else early      # noqa: E731
    code, out = run(make_ctx(world, now=clock), "--apply", "--plan", plan)
    assert code == rep.EXIT_REFUSED and "under the lock" in out and "session 10:30 ET" in out, out
    assert_untouched(world)


# ---------------------------------------------------------------- read-only at the broker

def test_the_tool_never_names_the_transmit_method():
    """Like the collector (quantt/collect/tests), this module only reads Alpaca."""
    src = Path(rep.__file__).read_text()
    assert "submit_order" not in src


# ---------------------------------------------------------------- rehearsal on prod's panel

REHEARSAL = os.environ.get("QUANTT_REPAIR_REHEARSAL_PANEL", "")


@pytest.mark.skipif(not (REHEARSAL and Path(REHEARSAL).is_file()),
                    reason="QUANTT_REPAIR_REHEARSAL_PANEL does not name a copy of prod's panel")
def test_rehearsal_on_a_copy_of_prods_panel(tmp_path):
    """A COPY of prod's real panel (read-only snapshot), a mocked source that
    has a print for every empty cell but one ticker's. Only those closes may
    change; the other 268k rows must come back byte-identical."""
    cef = tmp_path / "data" / "cef"
    cef.mkdir(parents=True)
    panel = cef / "cef_prices.parquet"
    shutil.copyfile(REHEARSAL, panel)
    (tmp_path / "state" / "logs").mkdir(parents=True)
    old = pd.read_parquet(panel)
    empty = old[~np.isfinite(old.close)]
    assert len(empty) > 0
    skip = sorted(empty.ticker.unique())[0]
    prints = {(r.ticker, r.date.date().isoformat()): 10.0 + i / 100
              for i, r in enumerate(empty.itertuples()) if r.ticker != skip}
    w = SimpleNamespace(tmp=tmp_path, panel=panel, lock=cef / ".fetch.lock",
                        log=tmp_path / "state" / "logs" / rep.LOG_NAME,
                        original=panel.read_bytes())
    code, out = run(make_ctx(w, client=FakeClient(prints=prints)))
    assert code == 0 and panel.read_bytes() == w.original
    code, out = run(make_ctx(w, client=FakeClient(prints=prints)), "--apply", "--plan",
                    digest_of(out))
    assert code == 0, out
    new = pd.read_parquet(panel)
    assert len(new) == len(old) and (new.dtypes == old.dtypes).all()
    filled = np.isfinite(new.close) & ~np.isfinite(old.close)
    assert filled.sum() == len(prints)
    keep = ~filled
    for c in old.columns:
        assert rep._same_cells(new[c][keep], old[c][keep]).all(), c
    assert len([r for r in log_records(w) if r["event"] == "REPAIRED"]) == len(prints)
