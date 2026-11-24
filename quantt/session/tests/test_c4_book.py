"""C4's own book on the runner: BOOKS["c4"], its book json, its panel, its refresh, its state dir.

WHAT THIS PINS (C4 integration, 2026-10-29; deploy plan rows 6A, 8 and 11).
Each test fails on 35b429f (origin/main when c4-integrate was cut), which has
no BOOKS["c4"], no ops/books/c4_families_book.json, a refresh that refuses
every panel but the core's, no per-book state-dir rule and one distributions
panel:

  * BOOKS["c4"] resolves to C4's spec and book json, its own order-id prefix,
    and its own keys (ALPACA_C4_KEY_ID / _SECRET_KEY, alpaca_probe's naming);
  * the C4 book json validates through every reader the runner has, and says
    what the team lead ruled (no stale-NAV gate, the missing-NAV hold, report
    drawdown, late-market paper execution, one sleeve, its own $100k), with a
    note on every block;
  * C4's refresh is fetch_daily --data-book c4 (row 6A's interface, filled by
    step 3), and fetch_daily's own command line takes it;
  * a C4 session in DRY, built BY default_deps from the C4 book json on a
    fixture panel at data/cef_c4/, decides from that panel only: every parquet
    it opens is under data/cef_c4/, the core's data/cef/ files are absent and
    never asked for, the client is C4's, the plan is C4's 74, and the send at
    15:52 sends nothing;
  * a C4 run in another book's state directory is refused before anything is
    written there (session and verify);
  * the mirrored C4 paths agree: run.DATA_BOOK_DIRS, data_books.C4_DIR, the
    spec's panel_source and dist_score.PANELS.

The core is proved unchanged elsewhere (test_panels_noop.py, against cee16ad
and 35b429f). Hermetic: no network (netguard), no key file (the client factory
is faked), the panel generated under tmp_path, data/ never written.
"""
import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from quantt.session import run as rn

ASOF = dt.date(2026, 9, 25)                                  # Friday; the session is Monday
SESSION = "2026-09-28"
ET = rn.gt.ET
EVE = dt.datetime(2026, 9, 25, 22, 0, tzinfo=ET)
SEND = dt.datetime(2026, 9, 28, 15, 52, 30, tzinfo=ET)
N_DAYS = 480


def _c4():
    """BOOKS["c4"], looked up per test (on a tree without it each test fails alone)."""
    return rn.BOOKS["c4"]


def _book_json() -> dict:
    return json.loads(_c4().book_path.read_text())


def _spec() -> dict:
    return rn.load_spec(_c4().spec_path)


# ------------------------------------------------------------------ BOOKS["c4"]

def test_books_c4_resolves_to_its_own_spec_book_prefix_and_keys():
    from quantt.broker.alpaca_probe import env_names
    assert _c4().name == "c4" and _c4().cid_prefix == "c4"
    assert _c4().spec_path == rn.REPO / "ops/specs/c4_families.frozen.json"
    assert _c4().book_path == rn.REPO / "ops/books/c4_families_book.json"
    assert _c4().spec_path.is_file() and _c4().book_path.is_file()
    assert env_names(_c4().name) == ("ALPACA_C4_KEY_ID", "ALPACA_C4_SECRET_KEY")
    # Nothing of the core's is shared.
    core = rn.BOOKS["cef"]
    assert {_c4().spec_path, _c4().book_path, _c4().cid_prefix} & {core.spec_path, core.book_path,
                                                          core.cid_prefix} == set()
    from quantt.session import decide
    assert decide.client_order_id(_c4().cid_prefix, dt.date(2026, 9, 28), "ADX", 1) == \
        "c4-20260928-ADX-1"
    # `run --book c4` parses (argparse choices are BOOKS).
    assert "c4" in rn.BOOKS and sorted(rn.BOOKS) == ["c4", "cef"]


# ------------------------------------------------------------------ the book json

def test_the_c4_book_json_validates_through_every_runner_reader():
    from ops.common import deployed_tickers
    from quantt.session import combine as cmb
    spec, book = _spec(), _book_json()
    assert rn.execution_for(_c4()) == {"mode": "late_market", "window_minutes_before_close": (8, 2),
                                    "bp_shortfall": "scale"}
    assert rn.stale_nav_for(_c4()) is None and "stale_nav" not in book["data"]   # no CEFConnect
    assert rn.missing_nav_for(_c4()) == "hold" and rn.missing_nav_max_sessions_for(_c4()) == 2
    assert rn.drawdown_for(_c4()) == "report"
    assert rn.corporate_actions_for(_c4()) == "report"     # team lead 2026-11-02, as the core
    assert rn.halts_for(_c4()) == [] or all(h for h in rn.halts_for(_c4()))         # it reads, by book_id
    assert book["book_id"] == "c4_families_paper"
    # One sleeve, the C4 spec, at its own $100k, and no risk_budget: a single-spec book.
    (sl,) = book["sleeves"]
    assert sl["enabled"] and rn.REPO / sl["spec_path"] == _c4().spec_path
    assert sl["capital_usd"] == spec["capital_usd"] == 100_000.0 and "risk_budget" not in sl
    assert cmb.load_sleeves(_c4().book_path, _c4().spec_path, rn.REPO, rn._sleeve_target_fn,
                            panel_of=rn.spec_panel) is None
    assert deployed_tickers(_c4().book_path) == {sl["name"]: list(spec["frozen"]["universe"])}
    # Its own limits are the spec's, mirrored.
    lim = book["limits"]
    assert lim["max_gross_exposure_usd"] == spec["risk"]["max_gross_exposure_usd"]
    assert lim["per_sleeve_capital_band"] == [0.0, spec["capital_usd"]]
    assert lim["book_drawdown_suspend_pct"] == 99.0                          # whole-number percent
    # The halve/kill levels are the core's, read in report mode only (spec v3, team lead
    # 2026-10-30). Until v3 the spec named none and this asserted Unmeasured.
    from quantt.session import drawdown as ddm
    core_risk = rn.load_spec(rn.BOOKS["cef"].spec_path)["risk"]
    lv = ddm.levels(spec)
    assert (lv["halve"], lv["kill"]) == (core_risk["halve_drawdown"], core_risk["kill_drawdown"])
    # Every block carries its note; every top-level key is a block the runner reads or prose.
    for block in ("limits", "execution", "data", "risk", "corporate_actions"):
        assert any(k.startswith("_") for k in book[block]), block
    assert all("_note" in s for s in book["sleeves"]) and "_book_id_note" in book
    assert set(book) == {"book_id", "_book_id_note", "description", "sleeves", "limits",
                         "execution", "data", "risk", "corporate_actions"}


def test_default_deps_builds_c4_with_its_own_client_panel_and_refresh(monkeypatch):
    from quantt.broker import alpaca
    asked = []
    monkeypatch.setattr(alpaca.AlpacaClient, "from_environment",
                        classmethod(lambda cls, name, **kw: asked.append(name) or object()))
    spec = _spec()
    deps = rn.default_deps(_c4(), spec, {"QUANTT_ENV_FILE": "unused"})
    assert asked == ["c4"]                                   # ALPACA_C4_* keys, never the core's
    assert deps.stale_nav is None and deps.nav_gate is None and deps.sleeves is None
    assert deps.missing_nav == "hold" and deps.missing_nav_max_sessions == 2
    assert deps.drawdown == "report" and deps.corp_actions == "report"
    assert deps.execution["mode"] == "late_market"
    assert rn.spec_panel(spec) == rn.Panel(rn.REPO / "data/cef_c4/cef_prices.parquet",
                                           rn.REPO / "data/cef_c4/cef_nav.parquet")


def test_the_c4_refresh_is_fetch_daily_data_book_c4_and_fetch_daily_takes_it(monkeypatch):
    """Row 6A's interface, filled: the refresh the C4 book's deps run is
    fetch_daily --data-book c4 with C4's book json, and no CEFConnect fallback
    (which fetch_daily refuses for C4). fetch_daily's own CLI parses exactly
    that command and hands it to its C4 data book."""
    from quantt.broker import alpaca
    from scripts.cef import fetch_daily as fd
    got = {}

    def fake_run(cmd, **kw):
        got["cmd"] = cmd
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(rn.subprocess, "run", fake_run)
    monkeypatch.setattr(alpaca.AlpacaClient, "from_environment",
                        classmethod(lambda cls, name, **kw: object()))
    deps = rn.default_deps(_c4(), _spec(), {"QUANTT_ENV_FILE": "unused"})
    r = deps.refresh(ASOF, 600.0)
    assert r.exit == 0 and r.incomplete is None
    assert got["cmd"][1].endswith("scripts/cef/fetch_daily.py")
    args = got["cmd"][2:]
    assert args == ["--require-asof", "2026-09-25", "--data-book", "c4",
                    "--book", "ops/books/c4_families_book.json"]
    assert "--nav-fallback" not in args
    seen = {}

    def fake_refresh(period, require_asof, nav_fallback, book, data_book=None):
        seen.update(period=period, asof=require_asof, fallback=nav_fallback, book=book,
                    data_book=data_book)
        return 0

    monkeypatch.setattr(fd, "refresh", fake_refresh)
    assert fd.main(args) == 0
    assert seen == {"period": "6mo", "asof": "2026-09-25", "fallback": None,
                    "book": "ops/books/c4_families_book.json", "data_book": "c4"}
    # And that data book is C4's own directory and lock, never the core's.
    cfg, core = fd.resolve_data_book("c4"), fd.resolve_data_book(None)
    assert cfg.lock_path != core.lock_path and not cfg.cefconnect
    assert cfg.px_path.parent == rn.DATA_BOOK_DIRS["c4"]


def test_the_mirrored_c4_paths_agree():
    from quantt.session import dist_score
    from scripts.cef import data_books
    spec = _spec()
    d = rn.DATA_BOOK_DIRS["c4"]
    assert d == Path(data_books.C4_DIR)
    assert {rn.REPO / p for p in spec["frozen"]["panel_source"].values()} == \
        {d / "cef_prices.parquet", d / "cef_nav.parquet"}
    assert dist_score.PANELS["c4"] == d / "cef_distributions.parquet"
    assert dist_score.panel_for("cef") == dist_score.DEFAULT_PANEL
    assert sorted(spec["frozen"]["universe"]) == sorted(data_books.c4_universe())
    with pytest.raises(dist_score.DistError, match="no distributions panel"):
        dist_score.panel_for("b6")


# ------------------------------------------------------------------ the C4 session, DRY, on a fixture panel

def _lcg(seed: int):
    x = seed
    while True:
        x = (1103515245 * x + 12345) % 2147483648
        yield x


def _write_c4_panel(dst: Path):
    """A generated panel for the 74 frozen funds, in the live schema, at `dst`
    (integer LCG and IEEE arithmetic only). Every fund liquid and dated as-of."""
    from scripts.cef import data_books
    fam = data_books.c4_universe()
    dates = pd.bdate_range(end=pd.Timestamp(ASOF), periods=N_DAYS)
    px, nv = [], []
    for i, tk in enumerate(sorted(fam)):
        g = _lcg(20261029 + i)
        u = lambda: ((next(g) % 20001) - 10000) / 10000.0          # noqa: E731, in [-1, 1]
        level = -0.10 + 0.002 * i
        nav, d = 10.0 + (i % 17) / 2.0, level
        for t, day in enumerate(dates):
            if t:
                nav = nav * (1.0 + 0.006 * u() + 0.0001)
                d = 0.97 * d + 0.03 * level + 0.02 * u()
            px.append({"date": day, "open": nav * (1 + d), "high": nav * (1 + d),
                       "low": nav * (1 + d), "close": nav * (1 + d),
                       "volume": int(800_000 + next(g) % 400_001), "ticker": tk,
                       "grp": fam[tk]})
            nv.append({"date": day, "nav": nav, "ticker": tk})
    dst.mkdir(parents=True)
    P, N = pd.DataFrame(px), pd.DataFrame(nv)
    P.to_parquet(dst / "cef_prices.parquet")
    N.to_parquet(dst / "cef_nav.parquet")
    return P


@pytest.fixture
def c4_world(tmp_path, monkeypatch):
    """tmp_path stands in for the repository root: data/cef_c4/ holds the fixture
    panel; data/cef/ does not exist, so any read of the core's panel raises."""
    from src.deploy.sleeves import cef_discount as cefmod
    root = tmp_path / "repo"
    P = _write_c4_panel(root / "data" / "cef_c4")
    monkeypatch.setattr(cefmod, "REPO", root)                    # the spec's panel_source root
    monkeypatch.setattr(cefmod, "PX_PATH", root / "data/cef/cef_prices.parquet")    # absent
    monkeypatch.setattr(cefmod, "NAV_PATH", root / "data/cef/cef_nav.parquet")      # absent
    monkeypatch.setattr(cefmod, "GRP_PATH", root / "data/cef/cef_prices.parquet")   # absent
    monkeypatch.setitem(rn.DATA_BOOK_DIRS, "c4", root / "data" / "cef_c4")
    reads = []
    real = pd.read_parquet

    def recording(path, *a, **kw):
        reads.append(Path(path))
        return real(path, *a, **kw)

    monkeypatch.setattr(pd, "read_parquet", recording)
    return root, P, reads


class _C4Client:
    """test_run's FakeClient, a fresh account (nothing held, nothing ever
    filled), with the corporate-action read listing nothing."""
    def __new__(cls, state, clock_ts):
        from quantt.session.tests.test_run import FakeClient

        class C(FakeClient):
            # **kw: main's gate (a40170c and before) passes `universe`, `skipped` and,
            # with acknowledgements, `rows` (corp_actions.check); an empty feed
            # ignores them, as AlpacaClient.corporate_actions does for no rows.
            def corporate_actions(self, symbols, start, end, **kw):
                self.calls.append(("corporate_actions",))
                return []
        return C(state, clock_ts=clock_ts)


def _c4_session(root: Path, state: Path, now, monkeypatch, *, dry="1"):
    from quantt.broker import alpaca
    c = _C4Client(state, now)
    asked = []
    monkeypatch.setattr(alpaca.AlpacaClient, "from_environment",
                        classmethod(lambda cls, name, **kw: asked.append(name) or c))
    spec = _spec()
    deps = rn.default_deps(_c4(), spec, {"QUANTT_ENV_FILE": "unused"})
    assert deps.client is c and asked == ["c4"]
    flags = rn.refresh_flags(rn.spec_panel(spec))
    assert flags == ("--data-book", "c4")                        # the fixture panel IS C4's data book
    deps.env = {"QUANTT_STATE_DIR": str(state), "DRY_RUN": dry}
    deps.refresh = lambda a, t: rn.RefreshResult(exit=0, tail="fixture")   # the command: test above
    deps.halts = lambda: []
    deps.utcnow = lambda: now.astimezone(dt.timezone.utc)
    deps.out = type("Quiet", (), {"write": lambda self, s: None, "flush": lambda self: None})()
    return rn.run_session(_c4(), spec, deps), c


def test_a_c4_session_in_dry_decides_from_data_cef_c4_only(c4_world, monkeypatch, tmp_path):
    root, P, reads = c4_world
    state = tmp_path / "quantt_state" / "c4"
    state.mkdir(parents=True)
    code, c = _c4_session(root, state, EVE, monkeypatch)
    plan = json.loads((state / SESSION / "plan.json").read_text())
    assert code == rn.EXIT_PLANNED, plan.get("refusals")
    assert plan["status"] == "decided" and plan["refusals"] == []
    universe = set(_spec()["frozen"]["universe"])
    assert set(plan["targets"]) <= universe and len(plan["orders"]) > 0
    assert {o["symbol"] for o in plan["orders"]} <= universe
    assert all(o["client_order_id"].startswith("c4-20260928-") for o in plan["orders"])
    # DECIDED FROM data/cef_c4 ONLY: every parquet the session opened is C4's,
    # and the core's data/cef/ was never asked for (it does not even exist).
    c4_dir = root / "data" / "cef_c4"
    assert reads and all(p.parent == c4_dir for p in reads), sorted(set(reads))
    assert not (root / "data" / "cef").exists()
    # What the record says: C4's spec, no stale-NAV gate, the missing-NAV hold
    # on, the drawdown in report mode, the corporate-action gate clear.
    assert plan["spec_id"] == _spec()["spec_id"] and plan["book"] == "c4"
    assert "nav_gate" not in plan                                # no stale-NAV gate for _c4()
    mv = plan["missing_nav"]
    assert (mv["mode"], mv["action"], mv["missing"], mv["n_universe"], mv["max_held"]) == \
        ("hold", "none", {}, 74, 74 - 6)
    # The core's levels, report only (spec v3, team lead 2026-10-30): read, and UNMEASURED here
    # only because the fresh state dir has no eod_equity.csv yet (the collector writes it).
    dd = plan["drawdown"]
    assert dd["status"] == "UNMEASURED" and "eod_equity.csv" in dd["why"] and not dd["acted"]
    assert (dd["levels"]["halve"], dd["levels"]["kill"]) == (0.12, 0.18)
    assert plan["corporate_actions"]["status"] == "CLEAR"
    # CEF trial 53 (spec c4_families.v2.20261101; amendment 1, v4.20261102: 1.26): every weight
    # target is the account's, m x the unit weight, and says so (cef_discount.py, `smult`).
    weighted = [t for t in plan["targets"].values() if t["reason"].startswith("cef discount z=")]
    assert weighted and all(" smult=1.2600" in t["reason"] for t in weighted), weighted[:2]
    assert c.submits() == []
    # THE SEND at 15:52, still DRY: nothing reaches the broker.
    reads.clear()
    code, c2 = _c4_session(root, state, SEND, monkeypatch)
    assert code == rn.EXIT_DRY and c2.submits() == []
    assert not (state / SESSION / "STARTED").exists()
    assert all(p.parent == c4_dir for p in reads), sorted(set(reads))


def test_a_c4_session_refuses_another_books_state_dir_and_writes_nothing_there(
        c4_world, monkeypatch, tmp_path):
    root, _, _ = c4_world
    core_state = tmp_path / "quantt_state" / "cef"
    core_state.mkdir(parents=True)
    code, c = _c4_session(root, core_state, EVE, monkeypatch)
    assert code == rn.EXIT_FAIL
    assert list(core_state.iterdir()) == []                      # not even a run record
    assert c.calls == []                                         # nothing asked of the broker
    # verify: the same rule, exit 2, no verify.log line in the core's directory.
    from quantt.session import verify as vf
    monkeypatch.setenv("QUANTT_STATE_DIR", str(core_state))
    monkeypatch.setattr(vf, "_make_client", lambda book: pytest.fail("no client may be built"))
    assert vf.main(["--book", "c4"]) == 2
    assert list(core_state.iterdir()) == []
    # approve: refused the same way.
    assert rn.approve_main(["--book", "c4", "--date", SESSION, "--sha", "x"]) == rn.EXIT_REFUSED
    assert list(core_state.iterdir()) == []


def test_c4_ca_ack_refuses_another_books_state_dir_before_any_read(monkeypatch, tmp_path):
    """main's `ca-ack` (merged onto c4-integrate 2026-11-02) keeps the per-book
    state-dir rule too. Without it, `--book c4` with the core's QUANTT_STATE_DIR read
    the core's last gate record, asked the feed with C4's keys and wrote a c4 entry
    into the core's ca_acks.json, which the core's gate then refuses to parse
    (corp_actions.parse_acks: another book's entry) and, under `halt`, refuses on.
    The core's directory here holds a gate record that read the feed, so only the
    state-dir rule can stop ca-ack before its client is built. Fails on 8b001c9."""
    core_state = tmp_path / "quantt_state" / "cef"
    day = core_state / SESSION
    day.mkdir(parents=True)
    gate_rec = {"corporate_actions": {"query": ["2026-08-25", "2028-09-28"],
                                      "names": {"PDI": {}}, "blocking": []}}
    (day / "plan.json").write_text(json.dumps(gate_rec))
    before = sorted(p.relative_to(core_state) for p in core_state.rglob("*"))
    monkeypatch.setenv("QUANTT_STATE_DIR", str(core_state))
    monkeypatch.setattr(rn, "_ca_ack_client", lambda book: pytest.fail("no client may be built"))
    assert rn.ca_ack_main(["--book", "c4", "--id", "any-id", "--reason", "test"]) == \
        rn.EXIT_REFUSED
    assert sorted(p.relative_to(core_state) for p in core_state.rglob("*")) == before
    assert not (core_state / "ca_acks.json").exists()


def test_c4_verify_scores_distributions_against_its_own_panel(monkeypatch, tmp_path):
    """Plan row 8: verify's distribution hook reads the book's own panel."""
    from quantt.session import dist_score
    from quantt.session import verify as vf
    seen = {}

    def fake_pending(client, state_dir, today, *, now_utc, previous_trading_day,
                     next_trading_day, panel_path):
        seen["panel"] = panel_path
        return []

    monkeypatch.setattr(dist_score, "run_pending", fake_pending)
    vf.run_distributions(object(), tmp_path, dt.date(2026, 9, 28), book="c4")
    assert seen["panel"] == rn.REPO / "data" / "cef_c4" / "cef_distributions.parquet"
    vf.run_distributions(object(), tmp_path, dt.date(2026, 9, 28), book="cef")
    assert seen["panel"] == dist_score.DEFAULT_PANEL


# ------------------------------------- release-check of 8b14298: an unruled spike outranks the hold
#
# The REAL fetch_daily, on test_fetch_daily_books' C4 fixture (its `c4` fixture, imported
# below), gives the refresh's verdict: IGR's unruled spike-and-revert bar in the window and
# EVT's NAV for D (2026-09-29) late. The session then decides C4 at the FINAL CHECK of
# 2026-09-30 (as-of D) on test_c4_book's generated 74, with EVT's as-of NAV missing too:
# the same facts. Under data.missing_nav = "hold", gate 5 accepts an exit 4 there (EVT
# held, the rest decide), so before the fix (fetch_daily exited 4 over 6) C4 decided and
# would have sent on the unruled bar. Nothing in the runner reads the SPIKE-REVERT line.

from scripts.cef.tests.test_fetch_daily_books import c4  # noqa: E402,F401  (the fetch fixture)

SPIKE_ASOF = dt.date(2026, 9, 29)                           # test_fetch_daily_books.D
SPIKE_SESSION = "2026-09-30"


def _fetch_verdict(c4_fetch, spike: bool):
    """(exit, output) of the real fetch_daily --data-book c4 --require-asof D on its fixture,
    EVT's NAV for D absent, and IGR's spike in the window when `spike`."""
    from scripts.cef.tests import test_fetch_daily_books as tf
    # The stored panel at the levels the fetch serves (tf.spike_panels; the price-basis
    # guard of 2026-11-04 refuses a fixture stored at other levels than it fetches).
    P, N = tf.spike_panels() if spike else tf.c4_panels()
    f = tf.spike_frames() if spike else tf.c4_frames()
    del f["XEVTX"]
    rc, out, *_ = c4_fetch(tf.ASOF, P, N, f)
    return rc, out


def _final_check_with_evt_late(tmp_path, monkeypatch, refresh_exit, refresh_tail):
    """C4's session at the final check of SPIKE_SESSION, built by default_deps from its book
    json on the generated 74 (ending SPIKE_ASOF) with EVT's as-of NAV removed. Returns
    (exit, plan.json)."""
    import sys
    from quantt.broker import alpaca
    from src.deploy.sleeves import cef_discount as cefmod
    me = sys.modules[__name__]
    root = tmp_path / "repo"
    monkeypatch.setattr(me, "ASOF", SPIKE_ASOF)              # the generated panel ends here
    _write_c4_panel(root / "data" / "cef_c4")
    nav_path = root / "data" / "cef_c4" / "cef_nav.parquet"
    nav = pd.read_parquet(nav_path)
    nav = nav[~((nav["ticker"] == "EVT") & (pd.to_datetime(nav["date"]) == pd.Timestamp(SPIKE_ASOF)))]
    nav.to_parquet(nav_path)                                 # EVT's NAV for the as-of is late
    monkeypatch.setattr(cefmod, "REPO", root)
    for name in ("PX_PATH", "NAV_PATH", "GRP_PATH"):        # the core's panel: absent
        monkeypatch.setattr(cefmod, name, root / "data/cef" / "absent.parquet")
    monkeypatch.setitem(rn.DATA_BOOK_DIRS, "c4", root / "data" / "cef_c4")
    from quantt.session.nav_gate import final_check_at
    now = final_check_at(dt.date.fromisoformat(SPIKE_SESSION), "16:00") + dt.timedelta(minutes=5)
    state = tmp_path / "quantt_state" / "c4"
    state.mkdir(parents=True)
    # The previous session's record, every NAV dated: the age limit's count starts at 0
    # (test_missing_nav_hold's fixture), so the hold is decided on this day's facts only.
    from quantt.session.tests.test_missing_nav_hold import _prior_plan, _write_priors
    _write_priors(state, {SPIKE_ASOF: _prior_plan(SPIKE_ASOF)})
    c = _C4Client(state, now)
    monkeypatch.setattr(alpaca.AlpacaClient, "from_environment",
                        classmethod(lambda cls, name, **kw: c))
    spec = _spec()
    deps = rn.default_deps(_c4(), spec, {"QUANTT_ENV_FILE": "unused"})
    assert deps.missing_nav == "hold"
    deps.env = {"QUANTT_STATE_DIR": str(state), "DRY_RUN": "1"}
    deps.refresh = lambda a, t: rn.RefreshResult(exit=refresh_exit, tail=refresh_tail)
    deps.halts = lambda: []
    deps.utcnow = lambda: now.astimezone(dt.timezone.utc)
    deps.out = type("Quiet", (), {"write": lambda self, s: None, "flush": lambda self: None})()
    code = rn.run_session(_c4(), spec, deps)
    plan = json.loads((state / SPIKE_SESSION / "plan.json").read_text())
    assert c.submits() == []
    return code, plan


def test_at_the_final_check_an_unruled_spike_refuses_c4_even_with_a_late_nav(
        c4, tmp_path, monkeypatch):
    """The defect: a late NAV must not let an unruled spike through the missing-NAV hold.
    fetch_daily now exits 6 over its INCOMPLETE, and gate 5 refuses 6 at every check: the
    final-check decide is REFUSED, a `data` refusal naming the exit. Fails on 8b14298 (the
    fetch exited 4, EVT was held and C4 decided)."""
    rc, out = _fetch_verdict(c4, spike=True)
    assert "SPIKE-REVERT" in out and "INCOMPLETE for" in out, out
    monkeypatch.undo()                                       # the fetch fixture's patches end here
    code, plan = _final_check_with_evt_late(tmp_path / "s", monkeypatch, rc, out)
    assert code == rn.EXIT_REFUSED and plan["status"] == "refused", plan["refusals"]
    # Gate 5 exactly as without the key (gate.missing_nav_hold: a refresh failure other than
    # INCOMPLETE refuses the day): the exit, and EVT's undated NAV, both `data`.
    assert {r["gate"] for r in plan["refusals"]} == {"data"}, plan["refusals"]
    assert any("exited 6" in r["detail"] for r in plan["refusals"]), plan["refusals"]
    assert plan["missing_nav"]["missing"] == {"EVT": "2026-09-28"}
    assert not plan["missing_nav"]["held"]                    # nothing held: the day is refused


def test_at_the_final_check_a_late_nav_alone_is_still_held(c4, tmp_path, monkeypatch):
    """The control, unchanged by the fix: EVT's NAV late and no spike is the fetch's exit 4,
    and at the final check gate 5 holds EVT and C4 decides the other 73."""
    rc, out = _fetch_verdict(c4, spike=False)
    assert rc == 4 and "SPIKE" not in out, out
    monkeypatch.undo()
    code, plan = _final_check_with_evt_late(tmp_path / "s", monkeypatch, rc, out)
    assert code == rn.EXIT_PLANNED and plan["status"] == "decided", plan["refusals"]
    assert plan["refusals"] == [] and set(plan["missing_nav"]["held"]) == {"EVT"}
