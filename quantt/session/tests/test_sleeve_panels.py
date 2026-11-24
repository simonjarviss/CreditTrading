"""Plan row 6A: the runner sizes, gates and NAV-checks each sleeve on that sleeve's OWN panel.

WHAT IS TESTED (quantt/session/run.py PER-SLEEVE PANELS; C4 deploy plan §1 row
6A, §2 step 5). Every session here is built by `default_deps`, with only the
broker client, the clock, the halts, the log and (where named) the refresh
faked, so the readers under test are the ones prod runs.

THE FIXTURE. Two `cef_discount` sleeves on two panels:
  * A, test_combine_noop's synthetic spec on its generated 13-fund panel
    (`SYA`..`SYM`), with no `panel_source`: the core's paths, pointed at the copy;
  * B, the same spec on thirteen other names (`SBA`..`SBM`) with `panel_source`
    naming `data/cef_b/` under a scratch repository root: the same generator's
    rows under B's names, prices and NAVs x1.5.
A's (core) panel ALSO carries a DECOY for each of B's names: every row, prices
and NAVs x3, and every as-of NAV dated. Nothing may ever read a B name from
there; a reader that did would size B at the decoy's price, or pass gate 5 on
the decoy's NAV date, and each test below would see it.

EACH TEST FAILS ON 16e0c6e (release-20261029-2's code), where the runner read
every close and NAV of a combined book from the core paths, and refused a spec
on another panel in `default_deps` and `sleeve_targets` (`require_core_panel`):
  1. sleeve B's closes come only from its own panel (16e0c6e: gate 5 passes on
     the decoys, then the session FAILs in sleeve B's `require_core_panel`);
  2. gate 5, per sleeve, reads B's own NAV file (16e0c6e: the decoy's as-of
     NAV passes it, then FAIL as in 1);
  3. an absent panel file refuses, naming it (16e0c6e: FAIL with the row-6A
     message, which says nothing is absent; the single-spec book refused in
     `default_deps`);
  4. a universe its own panel does not cover refuses, naming the names and the
     file (16e0c6e: the row-6A message);
  5. the single-spec book's missing-NAV hold reads that spec's own NAV file
     (16e0c6e: refused in `default_deps`);
and the refresh and stale-NAV wiring row 6A adds: a panel this tree has no
fetcher for is refused at step 1 (gate 5, recorded), a book on two panels is
too, and data.stale_nav on another panel is refused before any client is built.

Hermetic: no network (netguard), no key file (the client factory is faked),
every panel generated under tmp_path; the real data/ is never read.
"""
import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from quantt.session import decide as dec
from quantt.session import run as rn
from quantt.session.tests.test_combine_noop import SYN_SPEC, SYN_TICKERS, _write_synthetic
from quantt.session.tests.test_missing_nav_hold import ASOF, EVE, FINAL, SESSION, _Quiet
from quantt.session.tests.test_run import FakeClient

B_TICKERS = tuple(f"SB{c}" for c in "ABCDEFGHIJKLM")
B_DIR = "data/cef_b"                     # under the scratch repository root
B_PANEL = {"prices": f"{B_DIR}/cef_prices.parquet", "nav": f"{B_DIR}/cef_nav.parquet"}
B_SCALE, DECOY_SCALE = 1.5, 3.0
CLS = {"mode": "cls", "bp_shortfall": "scale"}
SPEC_A = {**SYN_SPEC, "spec_id": "synthetic.sleeve-a.v1"}
SPEC_B = {**SYN_SPEC, "spec_id": "synthetic.sleeve-b.v1",
          "frozen": {**SYN_SPEC["frozen"], "universe": list(B_TICKERS),
                     "panel_source": dict(B_PANEL)}}
B_MISSING = "SBD"                        # whose as-of NAV B's own file lacks (test 2)


def _panels(tmp_path: Path, mp, *, b_nav_drop=(), b_uncovered=(), b_files=("prices", "nav")):
    """Write A's panel (with B's decoys) and B's, point the sleeve module at
    them, and return {"a": (px, nav), "b": (px, nav), "close_b", "close_decoy"}.
    `b_nav_drop`: B names whose as-of NAV row B's file lacks. `b_uncovered`: B
    names with no row at all in B's price file. `b_files`: which of B's two
    files exist."""
    from src.deploy.sleeves import cef_discount as cefmod
    gen = tmp_path / "gen"
    gen.mkdir()
    px, nv, _, _ = _write_synthetic(gen)
    P, N = pd.read_parquet(px), pd.read_parquet(nv)
    ren = dict(zip(SYN_TICKERS, B_TICKERS))
    PB = P.assign(ticker=P["ticker"].map(ren), close=P["close"] * B_SCALE)
    NB = N.assign(ticker=N["ticker"].map(ren), nav=N["nav"] * B_SCALE)
    decoy_P = PB.assign(close=PB["close"] / B_SCALE * DECOY_SCALE)
    decoy_N = NB.assign(nav=NB["nav"] / B_SCALE * DECOY_SCALE)
    a = tmp_path / "core"
    a.mkdir()
    a_px, a_nav = a / "cef_prices.parquet", a / "cef_nav.parquet"
    pd.concat([P, decoy_P], ignore_index=True).to_parquet(a_px)
    pd.concat([N, decoy_N], ignore_index=True).to_parquet(a_nav)
    mp.setattr(cefmod, "PX_PATH", a_px)
    mp.setattr(cefmod, "NAV_PATH", a_nav)
    mp.setattr(cefmod, "GRP_PATH", a_px)
    repo = tmp_path / "repo"
    mp.setattr(cefmod, "REPO", repo)
    b_px, b_nav = repo / B_PANEL["prices"], repo / B_PANEL["nav"]
    b_px.parent.mkdir(parents=True)
    ts = pd.Timestamp(ASOF)
    if b_nav_drop:
        m = (pd.to_datetime(NB["date"]) == ts) & NB["ticker"].isin(list(b_nav_drop))
        assert int(m.sum()) == len(b_nav_drop)
        NB = NB[~m].reset_index(drop=True)
    if b_uncovered:
        PB = PB[~PB["ticker"].isin(list(b_uncovered))].reset_index(drop=True)
    if "prices" in b_files:
        PB.to_parquet(b_px)
    if "nav" in b_files:
        NB.to_parquet(b_nav)

    def at(frame, col):
        return frame[pd.to_datetime(frame["date"]) == ts].set_index("ticker")[col].to_dict()
    return {"a": (a_px, a_nav), "b": (b_px, b_nav), "close_b": at(PB, "close"),
            "close_decoy": at(decoy_P, "close")}


def _spec_file(tmp_path: Path, spec: dict) -> Path:
    p = tmp_path / f"{spec['spec_id']}.frozen.json"
    p.write_text(json.dumps(spec))
    return p


def _two_sleeve_book(tmp_path: Path, **extra) -> tuple:
    """(Book, book spec): A and B enabled at risk_budget 0.5 each, `cls` with
    bp_shortfall "scale". The book spec is A's (the book's limits and vol target)."""
    a, b = _spec_file(tmp_path, SPEC_A), _spec_file(tmp_path, SPEC_B)
    bj = tmp_path / "two.json"
    bj.write_text(json.dumps({"book_id": "two", "sleeves": [
        {"name": "A", "enabled": True, "spec_path": str(a), "risk_budget": 0.5},
        {"name": "B", "enabled": True, "spec_path": str(b), "risk_budget": 0.5}],
        "execution": CLS, **extra}))
    return rn.Book("cef", "cef", a, bj), SPEC_A


def _b_only_book(tmp_path: Path) -> tuple:
    """(Book, spec): the single-spec book of a C4-shaped spec, B on its own panel."""
    b = _spec_file(tmp_path, SPEC_B)
    bj = tmp_path / "b_only.json"
    bj.write_text(json.dumps({"book_id": "b_only", "execution": CLS, "sleeves": [
        {"name": "B", "enabled": True, "spec_path": str(b)}]}))
    return rn.Book("cef", "cef", b, bj), SPEC_B


def _deps(tmp_path: Path, mp, book, spec, now, *, positions=None, armed=True,
          fake_refresh=True):
    from quantt.broker import alpaca
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    if armed:
        (state / "AUTO_ARMED").touch()
    c = FakeClient(state, positions=positions or {}, clock_ts=now)
    mp.setattr(alpaca.AlpacaClient, "from_environment", classmethod(lambda cls, name, **kw: c))
    deps = rn.default_deps(book, spec, {"QUANTT_ENV_FILE": "unused"})
    deps.env = {"QUANTT_STATE_DIR": str(state), "DRY_RUN": "0"}
    if fake_refresh:
        deps.refresh = lambda a, t: rn.RefreshResult(exit=0, tail="fixture")
    deps.halts = lambda: []
    deps.utcnow = lambda: now.astimezone(dt.timezone.utc)
    deps.out = _Quiet()
    return deps, c, state


def _run(tmp_path, mp, book, spec, now, **kw):
    skip = kw.pop("skip_refresh", False)
    deps, c, state = _deps(tmp_path, mp, book, spec, now, **kw)
    code = rn.run_session(book, spec, deps, skip_refresh=skip)
    day = state / SESSION.isoformat()
    plan = json.loads((day / "plan.json").read_text()) if (day / "plan.json").exists() else None
    runs = sorted((day / "runs").glob("*.json"))
    return code, plan, json.loads(runs[-1].read_text()), c, "".join(deps.out.text)


# ------------------------------------------------- 1. B's closes, from B's panel only

def test_sleeve_b_is_sized_on_its_own_panels_closes(tmp_path, monkeypatch):
    """Two sleeves, two panels, one account (an opening session: full targets).
    Every B name is priced at B's own as-of close -- never the decoy the core
    panel holds for it -- and B's whole-share targets are its weights sized
    on its own sleeve_nav at those closes."""
    from src.deploy.registry import build_sleeve
    from src.deploy.sleeve import MarketState
    pn = _panels(tmp_path, monkeypatch)
    book, spec = _two_sleeve_book(tmp_path)
    code, plan, run, c, log = _run(tmp_path, monkeypatch, book, spec, EVE)
    assert code == rn.EXIT_SENT, log
    for s in B_TICKERS:
        assert run["closes"][s] == {"close": pn["close_b"][s], "date": ASOF.isoformat()}, s
        assert pn["close_b"][s] != pn["close_decoy"][s]
    b = plan["combine"]["sleeves"]["B"]
    assert b["status"] == "decided" and b["sleeve_nav"] == 50_000.0
    sl = build_sleeve(SPEC_B, SPEC_B["capital_usd"])
    ms = MarketState(asof=pd.Timestamp(ASOF), prices=pd.DataFrame(), holdings={},
                     extras={"sleeve_nav": 50_000.0, "opening_session": True})
    want = {t.instrument: dec.target_shares(t, 50_000.0, pn["close_b"][t.instrument])[0]
            for t in sl.target_positions(pd.Timestamp(ASOF), ms)}
    assert {s: r["target"] for s, r in b["targets"].items()} == want
    traded = [s for s in B_TICKERS if want[s]]
    assert traded, "B traded nothing: the test would be vacuous"
    by = {o["symbol"]: o for o in plan["orders"]}
    for s in traded:
        assert by[s]["est_price"] == pn["close_b"][s], s
    assert {o["symbol"] for o in c.accepted.values()} & set(traded)
    # A, on the core panel, keeps the core's closes.
    assert plan["combine"]["sleeves"]["A"]["status"] == "decided"
    core = rn.last_closes(pn["a"][0], ASOF, SYN_TICKERS)
    assert {s: (run["closes"][s]["close"], run["closes"][s]["date"]) for s in SYN_TICKERS} == \
        {s: (v[0], v[1].isoformat()) for s, v in core.items()}


def test_the_readers_split_by_panel_and_keep_the_universes_order(tmp_path, monkeypatch):
    """The readers `default_deps` builds, called directly: each name from its own
    sleeve's file, in the order asked, and a name no sleeve owns refused."""
    pn = _panels(tmp_path, monkeypatch)
    book, spec = _two_sleeve_book(tmp_path)
    deps, _, _ = _deps(tmp_path, monkeypatch, book, spec, EVE)
    uni = tuple(sorted(SYN_TICKERS + B_TICKERS))
    closes = deps.closes(ASOF, uni)
    assert tuple(closes) == uni
    assert closes == {**rn.last_closes(pn["a"][0], ASOF, SYN_TICKERS),
                      **rn.last_closes(pn["b"][0], ASOF, B_TICKERS)}
    navs = deps.navs(ASOF, uni)
    assert tuple(navs) == uni
    assert navs == {**rn.last_navs(pn["a"][1], ASOF, SYN_TICKERS),
                    **rn.last_navs(pn["b"][1], ASOF, B_TICKERS)}
    hist = deps.history(ASOF, uni, 253)
    assert list(hist.columns) == list(uni) and len(hist) == 253
    assert hist["SBA"].iloc[-1] == closes["SBA"][0] and hist["SYA"].iloc[-1] == closes["SYA"][0]
    with pytest.raises(rn.SessionError, match="belong to no sleeve"):
        deps.closes(ASOF, ("SYA", "ZZZ"))


# ------------------------------------------------- 2. gate 5 per sleeve, B's own NAV file

def test_gate_5_per_sleeve_reads_each_sleeves_own_nav_file(tmp_path, monkeypatch):
    """B's own NAV file lacks SBD's as-of NAV; the decoy in the core panel has
    one. Before the final check the decide is refused, naming sleeve B and SBD;
    at the final check B is held at its shares and A decides and sends."""
    _panels(tmp_path, monkeypatch, b_nav_drop=(B_MISSING,))
    book, spec = _two_sleeve_book(tmp_path)
    prev = dt.date(2026, 9, 24)
    code, plan, run, c, log = _run(tmp_path / "eve", monkeypatch, book, spec, EVE)
    assert code == rn.EXIT_REFUSED, log
    assert run["nav_dates"][B_MISSING] == prev.isoformat()
    assert [r["detail"] for r in plan["refusals"]] == [
        f"sleeve B: NAV not dated {ASOF} for {{'{B_MISSING}': '{prev}'}}"]
    assert not c.accepted
    code, plan, run, c, log = _run(tmp_path / "final", monkeypatch, book, spec, FINAL)
    assert code == rn.EXIT_SENT, log
    sl = plan["combine"]["sleeves"]
    assert sl["B"]["status"] == "held" and B_MISSING in "; ".join(sl["B"]["held_why"])
    assert sl["A"]["status"] == "decided"
    sent = {o["symbol"] for o in c.accepted.values()}
    assert sent and sent <= set(SYN_TICKERS)


def test_the_missing_nav_hold_reads_the_specs_own_nav_file(tmp_path, monkeypatch):
    """The single-spec book's missing-NAV hold (data.missing_nav), on a spec on
    its own panel: B's NAV file lacks SBD's as-of NAV (the core panel's decoy
    has it), so at the final check SBD is held and the other twelve decide."""
    from ops.schedule.nyse_calendar import previous_trading_day
    from quantt.session.tests.test_missing_nav_hold import _prior_plan, _write_priors
    _panels(tmp_path, monkeypatch, b_nav_drop=(B_MISSING,))
    book, spec = _b_only_book(tmp_path)
    j = json.loads(book.book_path.read_text())
    j["data"] = {"missing_nav": "hold", "missing_nav_max_sessions": 2}
    book.book_path.write_text(json.dumps(j))
    prev = previous_trading_day(SESSION)
    _write_priors(tmp_path / "state", {prev: _prior_plan(prev)})
    code, plan, run, c, log = _run(tmp_path, monkeypatch, book, spec, FINAL,
                                   fake_refresh=False, skip_refresh=True)
    assert code == rn.EXIT_SENT, log
    assert plan["missing_nav"]["action"] == "held" and plan["missing_nav"]["held"] == [B_MISSING]
    assert plan["missing_nav"]["missing"] == {B_MISSING: "2026-09-24"}
    sent = {o["symbol"] for o in c.accepted.values()}
    assert sent and B_MISSING not in sent and sent <= set(B_TICKERS)


# ------------------------------------------------- 3. an absent panel refuses, naming it

def test_an_absent_sleeve_panel_file_refuses_naming_it(tmp_path, monkeypatch):
    """B's NAV file is absent (its price file is there). The session FAILs at the
    first read, naming exactly the absent file; nothing is decided or sent."""
    pn = _panels(tmp_path, monkeypatch, b_files=("prices",))
    book, spec = _two_sleeve_book(tmp_path)
    code, plan, run, c, log = _run(tmp_path, monkeypatch, book, spec, EVE)
    assert code == rn.EXIT_FAIL and plan is None and not c.accepted
    assert f"panel file(s) ['{pn['b'][1]}'] absent" in run["error"], run["error"]
    assert "sleeve 'B'" in run["error"]


def test_a_single_spec_book_on_an_absent_panel_is_built_and_refused_at_the_read(
        tmp_path, monkeypatch):
    """The C4 shape (one spec, its own panel_source) with neither file there:
    `default_deps` builds (it reads no panel: the 15:52 send builds it too), the
    refresh is refused at step 1 (no fetcher for that panel on this tree), and
    the decide FAILs at the first read, naming both files."""
    pn = _panels(tmp_path, monkeypatch, b_files=())
    book, spec = _b_only_book(tmp_path)
    code, plan, run, c, log = _run(tmp_path, monkeypatch, book, spec, EVE, fake_refresh=False)
    assert code == rn.EXIT_FAIL and plan is None and not c.accepted
    assert f"panel file(s) {[str(p) for p in pn['b']]} absent" in run["error"], run["error"]
    assert run["refresh"]["exit"] is None
    assert run["refresh"]["incomplete"].startswith("not run: no fetcher for the panel")
    # Step 3 is merged (c4-integrate): the refresh knows the core and the data
    # books, and this tmp panel is neither, so it is still refused, saying so.
    assert "the data books ['c4'] only" in run["refresh"]["incomplete"]


# ------------------------------------------------- 4. a universe its panel does not cover

def test_a_universe_not_covered_by_its_own_panel_refuses(tmp_path, monkeypatch):
    """SBM has no row at all in B's price file (the decoy in the core panel has
    plenty). The session FAILs naming SBM, B and the file; nothing is sent."""
    pn = _panels(tmp_path, monkeypatch, b_uncovered=("SBM",))
    book, spec = _two_sleeve_book(tmp_path)
    code, plan, run, c, log = _run(tmp_path, monkeypatch, book, spec, EVE)
    assert code == rn.EXIT_FAIL and plan is None and not c.accepted
    assert (f"universe not covered by its own panel: ['SBM'] have no row in its price file "
            f"{pn['b'][0]}") in run["error"], run["error"]
    assert "sleeve 'B'" in run["error"]


# ------------------------------------------------- the refresh and the stale-NAV gate

def test_a_panel_with_no_fetcher_on_this_tree_is_refused_at_the_refresh(tmp_path,
                                                                         monkeypatch):
    """B alone on its own (present) panel: the refresh never runs fetch_daily
    (it is neither the core's nor a data book's) and gate 5 refuses the day, recorded.
    With --skip-refresh the book decides and sends on B's own closes."""
    def no_fetch(*a, **k):
        raise AssertionError("fetch_daily was run for a panel it does not write")
    monkeypatch.setattr(rn.subprocess, "run", no_fetch)
    pn = _panels(tmp_path, monkeypatch)
    book, spec = _b_only_book(tmp_path)
    code, plan, run, c, log = _run(tmp_path / "refresh", monkeypatch, book, spec, EVE,
                                   fake_refresh=False)
    assert code == rn.EXIT_REFUSED and not c.accepted, log
    assert plan["refusals"][0]["gate"] == "data"
    assert plan["refusals"][0]["detail"].startswith(f"refresh for as-of {ASOF} did not "
                                                    f"complete: not run: no fetcher")
    code, plan, run, c, log = _run(tmp_path / "skip", monkeypatch, book, spec, EVE,
                                   fake_refresh=False, skip_refresh=True)
    assert code == rn.EXIT_SENT, log
    assert plan["orders"] and all(o["est_price"] == pn["close_b"][o["symbol"]]
                                  for o in plan["orders"])


def test_a_book_on_two_panels_is_refused_at_the_refresh(tmp_path, monkeypatch):
    """One fetch_daily run refreshes one panel: the two-sleeve book's refresh is
    refused, naming both directories, and fetch_daily is never run."""
    monkeypatch.setattr(rn.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("fetch_daily was run")))
    pn = _panels(tmp_path, monkeypatch)
    book, spec = _two_sleeve_book(tmp_path)
    deps, _, _ = _deps(tmp_path, monkeypatch, book, spec, EVE, fake_refresh=False)
    r = deps.refresh(ASOF, 600.0)
    assert r.exit is None and r.incomplete.startswith("not run: the book's sleeves read 2 panels")
    assert str(pn["a"][0].parent) in r.incomplete and str(pn["b"][0].parent) in r.incomplete


def test_the_stale_nav_gate_on_another_panel_is_refused_before_any_client(tmp_path,
                                                                          monkeypatch):
    """data.stale_nav set on a book with a sleeve on another NAV file: refused in
    default_deps, naming the sleeve and the file, before the client is built."""
    from quantt.broker import alpaca
    pn = _panels(tmp_path, monkeypatch)
    book, spec = _two_sleeve_book(tmp_path, data={"stale_nav": "report"})
    built = []
    monkeypatch.setattr(alpaca.AlpacaClient, "from_environment",
                        classmethod(lambda cls, name, **kw: built.append(name)))
    with pytest.raises(rn.SessionError, match="data.stale_nav='report'") as e:
        rn.default_deps(book, spec, {"QUANTT_ENV_FILE": "unused"})
    assert "sleeve 'B'" in str(e.value) and str(pn["b"][1]) in str(e.value)
    assert not built


def test_spec_panel_is_the_sleeves_own_and_only_cef_discount_has_one(tmp_path, monkeypatch):
    pn = _panels(tmp_path, monkeypatch)
    assert rn.spec_panel(SPEC_A) == rn.core_panel() == pn["a"]
    assert rn.spec_panel(SPEC_B) == pn["b"]
    assert rn.refresh_flags(rn.core_panel()) == rn.CORE_REFRESH_FLAGS
    assert rn.refresh_flags(rn.spec_panel(SPEC_B)) is None
    other = {**SPEC_A, "allocation": {"type": "static_weights", "weights": {"SYA": 0.1}}}
    with pytest.raises(rn.SessionError, match="names no price and NAV panel"):
        rn.spec_panel(other)
