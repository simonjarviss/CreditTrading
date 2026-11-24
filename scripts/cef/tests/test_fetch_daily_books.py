"""fetch_daily's data books (C4 deployment plan step 3, DARK; team lead's fast-track 2026-10-28).

Two claims, and the tests for each:

THE CORE IS UNCHANGED. With no `--data-book`, or `--data-book cef`, fetch_daily
does what it did at cee16ad: the same panel bytes, fallback log, lock file,
printed lines, exit codes, yfinance symbols asked for and CEFConnect calls, on
seven scenarios that reach every branch the edit touched (a plain refresh with
empty rows, a repair, an empty NAV, a stale fund and a fetch error; the as-of
pair complete and incomplete; the CEFConnect fallback writing, and refusing a
NaN; no staged panel; the lock held). The base file is read from git
(`noop_base.py`). A second test pins every default, so a default that moves
fails here even where the scenarios happen not to look.

C4 HAS ITS OWN PATH. `--data-book c4`: data/cef_c4/ under its own lock, the
74 frozen funds, each NAV from the committed map, every empty-row guard, and
CEFConnect refused. Each such test fails on cee16ad, which has no data books.

Synthetic panels: the claims are about this code, not about any market (the
bar values in the guard tests are the 2026-10-28 incident's shapes, as in
test_fetch_daily_empty_rows.py). Hermetic: every path is in tmp_path (the root
conftest refuses a write under data/), yfinance and CEFConnect are fakes, and
netguard refuses any socket.
"""
import contextlib
import fcntl
import io
import os
import types
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from ops.common import atomic_write
from scripts.cef import data_books as db
from scripts.cef import fetch_daily as fd
from scripts.cef.tests.noop_base import load_at_base
from scripts.cef.tests.test_fetch_daily_empty_rows import NAN, bar, empty, navs_frame, panel, yf_frame

REPO = Path(__file__).resolve().parents[3]
D = pd.Timestamp("2026-09-29")                     # a Tuesday; the as-of day below
NOW = datetime(2026, 9, 30, 1, 30, tzinfo=timezone.utc)    # 21:30 ET on D: after the close


class Clock(datetime):
    """fetch_daily's clock pinned at NOW, so the stale ages, the lock file's
    stamp and the log's time are the same in every run being compared."""

    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


def fake_yf(frames, errors, asked):
    """yfinance by SYMBOL: a price ticker or a NAV symbol. A symbol in `errors`
    raises on `history`, as an outage does; one with no frame returns none."""
    class Ticker:
        def __init__(self, sym):
            self.sym = sym
            asked.append(sym)

        def history(self, period, auto_adjust):
            assert (period, auto_adjust) == ("6mo", False)
            if self.sym in errors:
                raise ConnectionError("fake yfinance outage")
            return frames.get(self.sym, pd.DataFrame())
    return types.SimpleNamespace(Ticker=Ticker)


def nav_rows(rows):
    return pd.DataFrame([{"date": pd.Timestamp(d), "nav": v, "ticker": t} for t, d, v in rows])


def point_core(mod, monkeypatch, d: Path):
    """Point one fetch_daily module's core constants into `d`."""
    for name, val in (("PX_PATH", d / "cef_prices.parquet"), ("NAV_PATH", d / "cef_nav.parquet"),
                      ("LOCK_PATH", d / ".fetch.lock"), ("FALLBACK_LOG", d / "nav_fallback_log.csv")):
        monkeypatch.setattr(mod, name, val)


def run(mod, monkeypatch, d: Path, argv, P, N, frames, *, errors=(), cc=None, deployed=(),
        hold=False, core=True):
    """One fetch through `mod.main(argv)` with the panels in `d`: the core's
    (`core`, its constants pointed there) or C4's (the `c4` fixture has pointed
    `data_books.C4_DIR` there and the core elsewhere).

    Returns (exit, stdout with `d` replaced, {file: bytes} in `d` afterwards,
    yfinance symbols asked, CEFConnect names asked)."""
    d.mkdir(parents=True)
    if P is not None:
        atomic_write(P, d / "cef_prices.parquet")
    if N is not None:
        atomic_write(N, d / "cef_nav.parquet")
    if core:
        point_core(mod, monkeypatch, d)
    monkeypatch.setattr(mod, "datetime", Clock)
    monkeypatch.setattr(mod, "LOCK_WAIT_S", 0.2)
    monkeypatch.setattr(mod, "LOCK_POLL_S", 0.02)
    monkeypatch.setattr(pd.Timestamp, "utcnow", staticmethod(lambda: pd.Timestamp(NOW)))
    asked, calls = [], []
    monkeypatch.setattr(mod, "yf", fake_yf(frames, set(errors), asked))
    monkeypatch.setattr(mod, "_cefconnect_nav",
                        lambda tk, asof: calls.append((tk, str(asof.date()))) or (cc or {}).get(tk))
    monkeypatch.setattr(mod, "_deployed", lambda book: sorted(deployed))
    other = None
    if hold:
        other = os.open(d / ".fetch.lock", os.O_RDWR | os.O_CREAT)
        fcntl.flock(other, fcntl.LOCK_EX)
        os.write(other, b"pid 424242 since test")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = mod.main(list(argv))
    finally:
        if other is not None:
            os.close(other)
    files = {p.name: p.read_bytes() for p in sorted(d.iterdir())}
    return rc, buf.getvalue().replace(str(d), "<DIR>"), files, asked, calls


# --------------------------------------------------------------------------- the core's fixtures

def core_panels():
    """Four funds to 2026-09-28; CCC's 09-25 row is EMPTY, as pre-fix panels still hold."""
    P = panel([bar(t, g, dd, c, c, c, c, 1000) for t, g, c in
               (("AAA", "hy", 10.0), ("BBB", "muni", 20.0), ("CCC", "loan", 7.0), ("DDD", "hy", 5.0))
               for dd in ("2026-09-24", "2026-09-25", "2026-09-28")
               if not (t == "CCC" and dd == "2026-09-25")]
              + [empty("CCC", "loan", "2026-09-25")])
    N = nav_rows([(t, dd, v) for t, v in (("AAA", 10.5), ("BBB", 21.0), ("CCC", 7.5), ("DDD", 5.5))
                  for dd in ("2026-09-24", "2026-09-25", "2026-09-28")])
    return P, N


def core_frames():
    """AAA: a new bar for D and an EMPTY 09-25 row (refused, kept). BBB: D's
    bar, but its NAV for D is EMPTY (refused; the fallback's case). CCC: the
    09-25 bar that repairs the panel's empty row, nothing for D, and a NAV last
    struck 09-15 (stale). DDD's fetch raises (UNCHECKED)."""
    return {
        "AAA": yf_frame([empty("AAA", "hy", "2026-09-25"),
                         bar("AAA", "hy", "2026-09-28", 10.0, 10.1, 9.9, 10.0, 1000),
                         bar("AAA", "hy", D, 10.0, 10.2, 9.9, 10.1, 1200)]),
        "XAAAX": navs_frame([("2026-09-28", 10.5), (D, 10.55)]),
        "BBB": yf_frame([bar("BBB", "muni", "2026-09-28", 20.0, 20.0, 20.0, 20.0, 1000),
                         bar("BBB", "muni", D, 20.1, 20.1, 20.1, 20.1, 900)]),
        "XBBBX": navs_frame([("2026-09-28", 21.0), (D, NAN)]),
        "CCC": yf_frame([bar("CCC", "loan", "2026-09-25", 7.0, 7.1, 6.9, 7.05, 800),
                         bar("CCC", "loan", "2026-09-28", 7.0, 7.0, 7.0, 7.0, 800)]),
        "XCCCX": navs_frame([("2026-09-15", 7.5)]),
    }


def clean_frames():
    """Every fund's bar and NAV for D, no empty row, no error: the quiet night."""
    out = {}
    for t, g, c, v in (("AAA", "hy", 10.0, 10.5), ("BBB", "muni", 20.0, 21.0),
                       ("CCC", "loan", 7.0, 7.5), ("DDD", "hy", 5.0, 5.5)):
        out[t] = yf_frame([bar(t, g, dd, c, c, c, c, 1000) for dd in ("2026-09-28", D)])
        out[f"X{t}X"] = navs_frame([("2026-09-28", v), (D, v + 0.01)])
    return out


ASOF = ["--require-asof", str(D.date())]
SCENARIOS = {
    "a clean fetch, every NAV fresh, the pair complete": dict(argv=ASOF, clean=True),
    "plain refresh": dict(argv=[]),
    "as-of, incomplete": dict(argv=ASOF),
    "as-of, the fallback writes one NAV": dict(argv=ASOF + ["--nav-fallback", "cefconnect"],
                                               cc={"BBB": 21.05}),
    "as-of with --book, complete after the fallback": dict(
        argv=ASOF + ["--nav-fallback", "cefconnect", "--book", "b.json"],
        cc={"BBB": 21.05}, deployed=("AAA", "BBB")),
    "as-of with --book, a NaN from CEFConnect is not written": dict(
        argv=ASOF + ["--nav-fallback", "cefconnect", "--book", "b.json"],
        cc={"BBB": NAN}, deployed=("AAA", "BBB")),
    "no staged panel": dict(argv=[], no_panel=True),
    "the lock is held": dict(argv=ASOF, hold=True),
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_the_core_is_byte_identical_to_cee16ad_with_no_book_and_with_book_cef(
        name, tmp_path, monkeypatch):
    """THE NO-OP PROOF. cee16ad's fetch_daily (from git), this one with no
    --data-book, and this one with --data-book cef, each in its own directory
    on the same fixtures: exit code, every printed line, every file's bytes,
    and every yfinance and CEFConnect request are identical."""
    sc = SCENARIOS[name]
    base = load_at_base("scripts/cef/fetch_daily.py", "fetch_daily_cee16ad", tmp_path, monkeypatch)
    got = []
    for label, mod, extra in (("run_base", base, []), ("run_new", fd, []),
                              ("run_new_cef", fd, ["--data-book", "cef"])):
        P, N = (None, None) if sc.get("no_panel") else core_panels()
        clean = sc.get("clean", False)
        got.append(run(mod, monkeypatch, tmp_path / label, sc["argv"] + extra, P, N,
                       clean_frames() if clean else core_frames(), errors=() if clean else ("DDD",),
                       cc=sc.get("cc"), deployed=sc.get("deployed", ()), hold=sc.get("hold", False)))
    b, n, c = got
    for i, what in enumerate(("exit code", "stdout", "files", "yfinance requests",
                              "CEFConnect requests")):
        assert n[i] == b[i], f"{name}: {what} differs from cee16ad with no --data-book"
        assert c[i] == b[i], f"{name}: {what} differs from cee16ad with --data-book cef"
    # The fixtures do reach the branches the edit touched.
    rc, out, files, asked, calls = b
    want = {"a clean fetch, every NAV fresh, the pair complete": 0,
            "plain refresh": 0, "as-of, incomplete": 4, "as-of, the fallback writes one NAV": 4,
            "as-of with --book, complete after the fallback": 0,
            "as-of with --book, a NaN from CEFConnect is not written": 4,
            "no staged panel": 1, "the lock is held": 3}[name]
    assert rc == want, out
    if name == "a clean fetch, every NAV fresh, the pair complete":
        assert "  all 4 NAV series fresh within 3 bd" in out.splitlines(), out
        assert "today's pair complete" in out and "NO " not in out, out
    if name == "plain refresh":
        for tag in ("NO CLOSE", "REPAIRED", "NO NAV", "STALE NAV", "UNCHECKED NAV"):
            assert tag in out, (tag, out)
        assert "XAAAX" in asked and "nav_fallback_log.csv" not in files
    if name == "as-of, the fallback writes one NAV":
        assert calls == [("BBB", "2026-09-29"), ("CCC", "2026-09-29"), ("DDD", "2026-09-29")]
        assert "nav_fallback_log.csv" in files


def test_every_core_default_is_pinned():
    """Fails if any default of the core moves: where the core's files are, how
    its NAV symbol is formed, that it may read CEFConnect, that it runs no
    spike guard, its exit codes, its wait, and the CLI's defaults."""
    data = REPO / "data" / "cef"
    for name in (None, "cef"):
        cfg = fd.resolve_data_book(name)
        assert cfg.name == "cef"
        assert (cfg.px_path, cfg.nav_path, cfg.lock_path, cfg.fallback_log) == (
            fd.PX_PATH, fd.NAV_PATH, fd.LOCK_PATH, fd.FALLBACK_LOG) == (
            data / "cef_prices.parquet", data / "cef_nav.parquet", data / ".fetch.lock",
            data / "nav_fallback_log.csv")
        assert (cfg.tickers, cfg.families, cfg.nav_symbols) == (None, None, None)
        assert cfg.nav_symbol("PDI") == "XPDIX"
        assert cfg.cefconnect is True and cfg.spike_guard is False
    assert (fd.STALE_BD, fd.LOCK_WAIT_S, fd.LOCK_POLL_S, fd.EXIT_LOCKED) == (3, 600.0, 1.0, 3)
    with pytest.raises(fd.DataBookError, match="no data book"):
        fd.resolve_data_book("cef_c4")


def test_the_cli_without_a_data_book_makes_the_call_it_always_made(monkeypatch):
    seen = []
    monkeypatch.setattr(fd, "refresh", lambda *a, **k: seen.append((a, k)) or 0)
    assert fd.main([]) == 0
    assert fd.main(["--require-asof", "2026-09-29", "--book", "b.json"]) == 0
    assert fd.main(["--data-book", "cef"]) == 0
    assert seen == [(("6mo", None, None, None), {}),
                    (("6mo", "2026-09-29", None, "b.json"), {}),
                    (("6mo", None, None, None), {"data_book": "cef"})]


# --------------------------------------------------------------------------- C4

C4_FUNDS = {"ADX": "equity_domestic", "EVT": "multi_asset", "IGR": "equity_sector"}
C4_SYMBOLS = {"ADX": "XADEX", "EVT": "XEVTX", "IGR": "XIGRX"}   # ADX's is not X<TK>X


@pytest.fixture
def c4(tmp_path, monkeypatch):
    """C4 pointed into tmp_path/cef_c4 with a three-fund frozen file and map,
    and the core pointed into tmp_path/cef. Returns run(argv, P, N, frames, ...)."""
    uni, nav_map = tmp_path / "frozen.csv", tmp_path / "nav_map.csv"
    pd.DataFrame({"ticker": list(C4_FUNDS), "family": list(C4_FUNDS.values())}).to_csv(uni, index=False)
    pd.DataFrame([{"ticker": t, "nav_symbol": s, "source": "fixture", "nav_ticker_cefconnect": s,
                   "families_nav_symbol": s, "families_nav_status": "fixture"}
                  for t, s in C4_SYMBOLS.items()]).to_csv(nav_map, index=False)
    monkeypatch.setattr(db, "C4_DIR", tmp_path / "cef_c4")
    monkeypatch.setattr(db, "C4_UNIVERSE", uni)
    monkeypatch.setattr(db, "C4_NAV_MAP", nav_map)
    monkeypatch.setattr(db, "C4_N", len(C4_FUNDS))
    core = tmp_path / "cef"
    core.mkdir()
    point_core(fd, monkeypatch, core)
    P, N = core_panels()
    atomic_write(P, core / "cef_prices.parquet")
    atomic_write(N, core / "cef_nav.parquet")
    (core / ".fetch.lock").write_bytes(b"")          # as any core directory that has run holds
    before = {p.name: p.read_bytes() for p in core.iterdir()}

    def go(argv, P, N, frames, *, errors=(), deployed=(), hold=False):
        out = run(fd, monkeypatch, tmp_path / "cef_c4", list(argv) + ["--data-book", "c4"], P, N,
                  frames, errors=errors, deployed=deployed, hold=hold, core=False)
        assert {p.name: p.read_bytes() for p in core.iterdir()} == before, \
            "a C4 fetch touched the core's data/cef"
        return out
    go.core = core
    return go


def c4_panels(days=("2026-09-24", "2026-09-25", "2026-09-28")):
    P = panel([bar(t, g, dd, 10.0, 10.0, 10.0, 10.0, 1000) for t, g in C4_FUNDS.items() for dd in days])
    N = nav_rows([(t, dd, 11.0) for t in C4_FUNDS for dd in days])
    return P, N


def c4_frames():
    out = {}
    for t, g in C4_FUNDS.items():
        out[t] = yf_frame([bar(t, g, dd, 10.0, 10.0, 10.0, 10.0, 1000) for dd in ("2026-09-28", D)])
        out[C4_SYMBOLS[t]] = navs_frame([("2026-09-28", 11.0), (D, 11.1)])
    return out


def test_the_c4_book_is_the_frozen_74_in_its_own_directory_under_its_own_lock():
    """The REAL config, from the tracked frozen file and the committed map."""
    cfg = fd.resolve_data_book("c4")
    c4dir = REPO / "data" / "cef_c4"
    assert (cfg.px_path, cfg.nav_path, cfg.lock_path) == (
        c4dir / "cef_prices.parquet", c4dir / "cef_nav.parquet", c4dir / ".fetch.lock")
    assert cfg.lock_path != fd.LOCK_PATH and cfg.px_path.parent != fd.PX_PATH.parent
    assert cfg.fallback_log is None and cfg.cefconnect is False and cfg.spike_guard is True
    assert len(cfg.tickers) == 74 == len(set(cfg.tickers)) and list(cfg.tickers) == sorted(cfg.tickers)
    assert set(cfg.families) == set(cfg.tickers)
    other = {t: cfg.nav_symbol(t) for t in cfg.tickers if cfg.nav_symbol(t) != f"X{t}X"}
    assert len(other) == 15, other
    assert (other["ADX"], other["TY"], other["GRX"]) == ("XADEX", "XTYCX", "XXGRX")
    assert cfg.nav_symbol("EVT") == "XEVTX"     # CEFConnect names none; the families panel's series
    from scripts.cef.spec import frozen
    assert not set(cfg.tickers) & set(frozen("universe")), "a core name is in C4"


def test_c4_writes_only_its_own_panels_and_asks_for_the_mapped_nav_symbols(c4):
    P, N = c4_panels()
    rc, out, files, asked, calls = c4([], P, N, c4_frames())
    assert rc == 0, out
    assert asked == [s for t in sorted(C4_FUNDS) for s in (t, C4_SYMBOLS[t])]
    assert "XADXX" not in asked and calls == []
    got = pd.read_parquet(c4.core.parent / "cef_c4" / "cef_prices.parquet")
    assert sorted(got.loc[got["date"] == D, "ticker"]) == sorted(C4_FUNDS)
    assert dict(got.drop_duplicates("ticker")[["ticker", "grp"]].values) == C4_FUNDS
    nav = pd.read_parquet(c4.core.parent / "cef_c4" / "cef_nav.parquet")
    assert nav.loc[(nav["ticker"] == "ADX") & (nav["date"] == D), "nav"].tolist() == [11.1]
    assert "nav_fallback_log.csv" not in files and "SPIKE" not in out


def test_c4_refuses_cefconnect_before_the_lock_or_a_panel_is_read(c4, monkeypatch, capsys):
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: pytest.fail("CEFConnect was read for C4"))
    P, N = c4_panels()
    rc, out, files, asked, calls = c4(ASOF + ["--nav-fallback", "cefconnect"], P, N, c4_frames())
    assert rc == fd.EXIT_REFUSED == 2
    assert "REFUSED" in out and "CEFConnect is disabled" in out
    assert asked == [] and calls == [] and ".fetch.lock" not in files
    with pytest.raises(db.CefConnectDisabled):
        fd.refresh("6mo", str(D.date()), "cefconnect", None, data_book="c4")
    with pytest.raises(db.CefConnectDisabled):
        fd._refresh_locked("6mo", str(D.date()), "cefconnect", None, fd.resolve_data_book("c4"))
    with pytest.raises(db.CefConnectDisabled):
        db.refuse_cefconnect("c4")("ADX", D)


def _hold(path):
    fdesc = os.open(path, os.O_RDWR | os.O_CREAT)
    fcntl.flock(fdesc, fcntl.LOCK_EX)
    return fdesc


def test_the_core_and_c4_never_wait_on_each_others_lock(c4, monkeypatch):
    """Each lock held in turn by another descriptor, with a 0.2 s wait: a
    fetch that contended would exit 3."""
    P, N = c4_panels()
    held = _hold(c4.core / ".fetch.lock")             # the core's session or collector
    try:
        assert c4([], P, N, c4_frames())[0] == 0
    finally:
        os.close(held)
    c4dir = c4.core.parent / "cef_c4"
    held = _hold(c4dir / ".fetch.lock")               # C4's collector
    try:
        monkeypatch.setattr(fd, "datetime", Clock)
        monkeypatch.setattr(fd, "LOCK_WAIT_S", 0.2)
        monkeypatch.setattr(fd, "yf", fake_yf(core_frames(), {"DDD"}, []))
        with contextlib.redirect_stdout(io.StringIO()):
            assert fd.main([]) == 0, "the core waited on C4's lock"
            assert fd.main(["--data-book", "c4"]) == fd.EXIT_LOCKED
    finally:
        os.close(held)


def test_a_held_c4_lock_is_named_in_the_refusal(c4):
    P, N = c4_panels()
    rc, out, *_ = c4([], P, N, c4_frames(), hold=True)
    assert rc == 3 and "cef_c4/.fetch.lock" in out.replace("<DIR>", "cef_c4") and "pid 424242" in out


# ------------------------------------------------------------------ the empty-row guards, on C4

def test_on_c4_an_empty_row_never_replaces_a_bar_and_a_good_bar_repairs_an_empty_one(c4):
    P = panel([bar("ADX", "equity_domestic", "2026-09-15", 10.0, 10.1, 9.9, 10.05, 5000),
               empty("EVT", "multi_asset", "2026-09-15"),
               bar("IGR", "equity_sector", "2026-09-15", 4.7, 4.7, 4.7, 4.7, 900)])
    N = nav_rows([(t, "2026-09-15", 11.0) for t in C4_FUNDS])
    frames = {"ADX": yf_frame([empty("ADX", "equity_domestic", "2026-09-15")]),
              "EVT": yf_frame([bar("EVT", "multi_asset", "2026-09-15", 13.0, 13.1, 12.9, 13.02, 700)])}
    rc, out, files, *_ = c4([], P, N, frames)
    got = pd.read_parquet(c4.core.parent / "cef_c4" / "cef_prices.parquet")
    adx = got[(got["ticker"] == "ADX") & (got["date"] == "2026-09-15")]
    evt = got[(got["ticker"] == "EVT") & (got["date"] == "2026-09-15")]
    assert adx["close"].tolist() == [10.05] and evt["close"].tolist() == [13.02]
    assert any(ln.strip().startswith("NO CLOSE") and " ADX " in ln and "kept" in ln
               for ln in out.splitlines()), out
    assert any(ln.strip().startswith("REPAIRED") and " EVT " in ln for ln in out.splitlines()), out


def test_on_c4_an_empty_nav_is_not_merged_and_does_not_make_a_fund_fresh(c4):
    P, N = c4_panels()
    frames = {"XADEX": navs_frame([("2026-09-28", NAN)])}      # ADX's NAV symbol, empty
    rc, out, *_ = c4([], P, N, frames)
    nav = pd.read_parquet(c4.core.parent / "cef_c4" / "cef_nav.parquet")
    assert nav.loc[(nav["ticker"] == "ADX") & (nav["date"] == "2026-09-28"), "nav"].tolist() == [11.0]
    lines = out.splitlines()
    assert any(ln.strip().startswith("NO NAV") and " ADX " in ln for ln in lines), out
    assert "    ADX    last NAV none: no finite positive NAV in the 1 row(s) fetched" in lines, out


def test_on_c4_require_asof_refuses_an_empty_as_of_row(c4):
    P, N = c4_panels(("2026-09-25", "2026-09-28"))
    P = pd.concat([P, panel([empty("IGR", "equity_sector", D)])], ignore_index=True)
    frames = c4_frames()
    frames["IGR"] = yf_frame([bar("IGR", "equity_sector", "2026-09-28", 10.0, 10.0, 10.0, 10.0, 1000)])
    rc, out, *_ = c4(ASOF, P, N, frames)
    assert rc == 4, out
    assert f"IGR: no close (its {D.date()} row is empty)" in out, out


# ------------------------------------------------------------------ what C4 refuses

def test_c4_refuses_a_panel_seeded_with_a_fund_outside_the_74_or_another_family(c4):
    P, N = c4_panels()
    stray = pd.concat([P, panel([bar("PDI", "taxable", "2026-09-28", 18, 18, 18, 18, 1)])],
                      ignore_index=True)
    with pytest.raises(db.DataBookError, match="PDI"):
        c4([], stray, N, c4_frames())


def test_c4_refuses_a_fund_under_another_family(tmp_path, c4):
    P, N = c4_panels()
    P.loc[P["ticker"] == "IGR", "grp"] = "muni"
    with pytest.raises(db.DataBookError, match="IGR"):
        c4([], P, N, c4_frames())


def test_c4_with_no_seeded_panel_exits_1_naming_the_seed_and_takes_no_lock(c4):
    rc, out, files, asked, _ = c4([], None, None, c4_frames())
    assert rc == 1 and "seed it first" in out and files == {} and asked == []


def test_c4_refuses_a_book_that_deploys_a_fund_it_does_not_fetch(c4):
    P, N = c4_panels()
    with pytest.raises(db.DataBookError, match="PDI"):
        c4(ASOF + ["--book", "b.json"], P, N, c4_frames(), deployed=("ADX", "PDI"))


def test_c4_may_not_share_a_path_with_the_core(tmp_path, monkeypatch, c4):
    monkeypatch.setattr(db, "C4_DIR", c4.core)
    with pytest.raises(db.DataBookError, match="share"):
        fd.resolve_data_book("c4")


# ------------------------------------------------------------------ the spike guard (C4 only)

def spike_frames():
    """IGR's holdout shape: a close x3 for one session, back the next, NAV flat."""
    f = c4_frames()
    days = ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-28", D]
    close = [4.70, 4.71, 14.13, 4.72, 4.70, 4.71, 4.72]
    f["IGR"] = yf_frame([bar("IGR", "equity_sector", dd, c, c, c, c, 1000) for dd, c in zip(days, close)])
    f["XIGRX"] = navs_frame([(dd, 5.0) for dd in days])
    return f


def spike_panels():
    """c4_panels with IGR stored at the levels spike_frames serves on the stored dates
    (close 4.70-4.72, NAV 5.0). Until the price-basis guard (2026-11-04) the fixture stored
    IGR at 10 / 11 against a fetch at 4.7 / 5.0, a x0.47 step in both series that nothing
    read; that guard now refuses such a write (test_c4_price_basis.py), so the spike tests
    store what the fetch serves."""
    P, N = c4_panels()
    lv = {"2026-09-24": 4.72, "2026-09-25": 4.70, "2026-09-28": 4.71}
    for d, c in lv.items():
        m = (P["ticker"] == "IGR") & (P["date"] == pd.Timestamp(d))
        P.loc[m, ["open", "high", "low", "close"]] = c
        N.loc[(N["ticker"] == "IGR") & (N["date"] == pd.Timestamp(d)), "nav"] = 5.0
    return P, N


def test_c4_writes_a_spike_and_revert_bar_and_exits_6_naming_it(c4):
    P, N = spike_panels()
    rc, out, *_ = c4([], P, N, spike_frames())
    assert rc == fd.EXIT_SPIKE == 6, out
    (ln,) = [x for x in out.splitlines() if x.strip().startswith("SPIKE-REVERT")]
    assert "IGR" in ln and "2026-09-23" in ln, ln
    got = pd.read_parquet(c4.core.parent / "cef_c4" / "cef_prices.parquet")
    assert got.loc[(got["ticker"] == "IGR") & (got["date"] == D), "close"].tolist() == [4.72], \
        "the panel must still be written whole"


def test_on_c4_an_unruled_spike_outranks_an_incomplete_pair(c4):
    """Release-check of 8b14298 (2026-11-02): with IGR's unruled spike in the window AND
    EVT's NAV for D late, C4's fetch exits 6, not 4, and prints both lines. Exit 4 is what
    C4's missing-NAV hold accepts at the final check (gate.missing_nav_hold), so the old
    4-over-6 order (this test asserted rc == 4 until then) let the session decide and send
    on the unruled bar whenever a NAV was late. The INCOMPLETE line keeps the prefix the
    collector reads (fd.INCOMPLETE_TAG). Fails on 8b14298."""
    P, N = spike_panels()
    f = spike_frames()
    del f["XEVTX"]
    rc, out, *_ = c4(ASOF, P, N, f)
    assert rc == fd.EXIT_SPIKE == 6, out
    lines = [x.strip() for x in out.splitlines()]
    assert any(x.startswith("SPIKE-REVERT") and "IGR" in x for x in lines), out
    (inc,) = [x for x in lines if x.startswith(fd.INCOMPLETE_TAG)]
    assert "EVT" in inc, inc


def test_on_c4_a_late_nav_with_no_spike_is_still_exit_4(c4):
    """The order changed only where a spike is found: no spike and EVT's NAV late is still
    exit 4 (INCOMPLETE), the hold's case."""
    P, N = c4_panels()
    f = c4_frames()
    del f["XEVTX"]
    rc, out, *_ = c4(ASOF, P, N, f)
    assert rc == 4 and "SPIKE" not in out and fd.INCOMPLETE_TAG in out, out


def test_the_cores_incomplete_exit_is_unchanged_whatever_its_closes_look_like(tmp_path, monkeypatch):
    """The core (spike_guard off): the same IGR-shaped closes with one NAV for D missing is
    exit 4 and no SPIKE line, as at cee16ad, whose ordering the core never left (its full
    no-op proof is test_the_core_is_byte_identical_to_cee16ad_*, run against this code)."""
    P, N = c4_panels()
    f = {k: v for k, v in spike_frames().items() if not k.startswith("X")}
    f.update({f"X{t}X": navs_frame([("2026-09-28", 11.0), (D, 11.1)]) for t in C4_FUNDS
              if t != "EVT"})
    rc, out, *_ = run(fd, monkeypatch, tmp_path / "core", ASOF, P, N, f)
    assert rc == 4 and "SPIKE" not in out and "INCOMPLETE for" in out and "EVT" in out, out


def test_the_core_runs_no_spike_guard(tmp_path, monkeypatch):
    """The same IGR-shaped series in the core's panel: no guard, exit 0, as at cee16ad."""
    P, N = c4_panels()
    f = {k: v for k, v in spike_frames().items() if not k.startswith("X")}
    f.update({f"X{t}X": navs_frame([("2026-09-28", 11.0), (D, 11.1)]) for t in C4_FUNDS})
    rc, out, *_ = run(fd, monkeypatch, tmp_path / "core", [], P, N, f)
    assert rc == 0 and "SPIKE" not in out, out
