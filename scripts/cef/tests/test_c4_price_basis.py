"""C4's fetch keeps ONE share basis for its closes and NAVs, and refuses a basis step (2026-11-04).

THE DEFECT (team lead 2026-11-03: "Hold C4 one day, fix IGR"). C4's first nightly fetch
(`fetch_daily --data-book c4`) replaced IGR's pre-split closes for 2026-05-04..09-04 with
Yahoo's split-adjusted ones, x3.0 (IGR's 1:3 reverse split was 2026-09-08), while IGR's NAV
symbol stayed unadjusted: a +200% premium for four months, a 252-day z of -0.79 on the
artifact, and 520 IGR bought on it in the 11-04 plan. data_guards.py, THE LIVE FETCH'S
PRICE BASIS, is the fix; this file proves it on SYNTHETIC panels (a statement about the
code, not about Yahoo): the IGR shape reproduced and put back on the NAV's basis under the
ruling; the step guard refusing, with nothing written; a clean fetch unchanged; the core's
fetch byte-identical to cee16ad; and the repair of a panel the bad fetch already wrote.
Every test here fails on origin/main (2ebf3c3).

Hermetic: test_fetch_daily_books' `c4` fixture points C4 at tmp_path with a three-fund
universe (ADX, EVT, IGR); yfinance is faked; data/ is never written.
"""
import json

import pandas as pd
import pytest

from scripts.cef import data_books as db
from scripts.cef import data_guards as dg
from scripts.cef import fetch_daily as fd
from scripts.cef.tests.test_fetch_daily_books import (ASOF, C4_FUNDS, D, c4, c4_frames,  # noqa: F401
                                                      core_frames, core_panels, run)
from scripts.cef.tests.test_fetch_daily_empty_rows import bar, navs_frame, panel, yf_frame

EX = pd.Timestamp("2026-09-08")                       # IGR's 1:3 reverse split
F = 1.0 / 3.0                                         # yfinance's multiplier for it
DAYS = list(pd.bdate_range("2026-08-24", D))          # stored and fetched, through D
RAW_PRE, RAW_POST, NAV_PRE, NAV_POST = 4.70, 14.10, 4.63, 14.25   # premium about +1.5%, then -1%


def _nav_rows(rows):
    return pd.DataFrame(rows, columns=["date", "nav", "ticker"])


def stored_panels():
    """The seeded panel: raw (as-traded) closes, unadjusted NAVs, for the three funds."""
    px, nv = [], []
    for t, g in C4_FUNDS.items():
        for d in DAYS[:-1]:                           # the fetch brings D
            if t == "IGR":
                c, n = (RAW_PRE, NAV_PRE) if d < EX else (RAW_POST, NAV_POST)
            else:
                c, n = 10.0, 11.0
            px.append(bar(t, g, d, c, c, c, c, 3000 if (t == "IGR" and d < EX) else 1000))
            nv.append((d, n, t))
    return panel(px), _nav_rows(nv)


def yahoo_frames(*, adjusted=True, declare=True):
    """Yahoo's histories: IGR's pre-split closes split-adjusted (x3, volume /3) when
    `adjusted`, its split declared on the ex-date when `declare`; every NAV unadjusted."""
    out = {}
    for t, g in C4_FUNDS.items():
        rows, navs = [], []
        for d in DAYS:
            if t == "IGR":
                c = (RAW_PRE * (3 if adjusted else 1)) if d < EX else RAW_POST
                v = (1000 if adjusted else 3000) if d < EX else 1000
                n = NAV_PRE if d < EX else NAV_POST
            else:
                c, v, n = 10.0, 1000, 11.0
            rows.append(bar(t, g, d, c, c, c, c, v))
            navs.append((d, n))
        f = yf_frame(rows)
        if t == "IGR" and declare:
            f.loc[f.index.normalize().tz_localize(None) == EX, "Stock Splits"] = F
        out[t] = f
        out[{"ADX": "XADEX", "EVT": "XEVTX", "IGR": "XIGRX"}[t]] = navs_frame(navs)
    return out


def _igr(c4_dir):
    P = pd.read_parquet(c4_dir / "cef_prices.parquet")
    N = pd.read_parquet(c4_dir / "cef_nav.parquet")
    p = P[P.ticker == "IGR"].set_index("date")["close"]
    n = N[N.ticker == "IGR"].set_index("date")["nav"]
    return p, n, P


def _ruling_file(tmp_path, splits):
    doc = {"ruled_by": "test", "ruled_on": "2026-11-03", "record": "test", "splits": splits}
    p = tmp_path / "rulings.json"
    p.write_text(json.dumps(doc))
    return p


# ------------------------------------------------- 1. the IGR case, reproduced and fixed

def test_the_igr_case_is_put_back_on_the_navs_basis_under_the_ruling(c4):
    """Yahoo serves IGR's pre-split closes x3 against an unadjusted NAV. Under the ruling
    (results/cef/c4/c4_fetch_split_rulings_2026-11-03.json) the fetch writes them back on
    the NAV's basis: the premium stays about +1.5%, not +200%, and the run says so. On
    origin/main the fetch wrote 14.10 over 4.70."""
    assert db.C4_FETCH_SPLIT_RULINGS.name == "c4_fetch_split_rulings_2026-11-03.json"
    P, N = stored_panels()
    rc, out, *_ = c4(ASOF, P, N, yahoo_frames())
    assert rc == 0, out
    p, n, Pall = _igr(c4.core.parent / "cef_c4")
    pre = p[p.index < EX]
    assert pre.round(6).eq(RAW_PRE).all(), pre.head()
    prem = (p / n - 1).dropna()
    assert prem[prem.index < EX].between(0.0, 0.03).all()          # +1.5%, not +200%
    vol = Pall[(Pall.ticker == "IGR") & (Pall.date < EX)]["volume"]
    assert (vol == 3000).all()                                      # volume back on raw shares
    assert any(ln.strip().startswith("BASIS    IGR") for ln in out.splitlines()), out


def test_rows_yahoo_has_not_yet_adjusted_are_left_alone(c4):
    """Yahoo adjusts late (IGR was still raw in the 2026-10-12 build): rows the NAV judges
    raw are not touched, so the same ruling is right before and after Yahoo adjusts."""
    P, N = stored_panels()
    rc, out, *_ = c4(ASOF, P, N, yahoo_frames(adjusted=False))
    assert rc == 0, out
    p, _, _ = _igr(c4.core.parent / "cef_c4")
    assert p[p.index < EX].round(6).eq(RAW_PRE).all()


# ------------------------------------------------- 2. the step guard refuses, nothing written

def test_an_unruled_declared_split_refuses_and_writes_nothing(c4, tmp_path, monkeypatch):
    """The same fetch with no ruling for IGR's split: refused (exit 7), naming it; the
    panel files are byte-for-byte what they were."""
    monkeypatch.setattr(db, "C4_FETCH_SPLIT_RULINGS", _ruling_file(tmp_path, [
        {"ticker": "ADX", "ex_date": "2026-01-02", "factor": 0.5, "series": "close",
         "treatment": "to_nav_basis", "reason": "test: a ruling for another fund"}]))
    P, N = stored_panels()
    rc, out, files, *_ = c4(ASOF, P, N, yahoo_frames())
    assert rc == fd.EXIT_BASIS == 7, out
    assert fd.BASIS_TAG in out and "IGR" in out and "2026-09-08" in out and "unruled" in out
    p, _, _ = _igr(c4.core.parent / "cef_c4")
    assert p[p.index < EX].round(6).eq(RAW_PRE).all()               # nothing written


def test_a_split_like_step_against_the_stored_closes_refuses_even_undeclared(c4, tmp_path,
                                                                           monkeypatch):
    """The step the spike guard cannot see: Yahoo serves IGR's closes x3 with no split
    declared and no ruling. The fetched/stored ratio is a constant x3 with no NAV step:
    refused, naming the fund and the dates; nothing written."""
    monkeypatch.setattr(db, "C4_FETCH_SPLIT_RULINGS", _ruling_file(tmp_path, [
        {"ticker": "ADX", "ex_date": "2026-01-02", "factor": 0.5, "series": "close",
         "treatment": "to_nav_basis", "reason": "test: a ruling for another fund"}]))
    P, N = stored_panels()
    rc, out, *_ = c4(ASOF, P, N, yahoo_frames(declare=False))
    assert rc == fd.EXIT_BASIS, out
    line = [ln for ln in out.splitlines() if fd.BASIS_TAG in ln][0]
    assert "close IGR 2026-08-24..2026-09-07" in line and "x3.0000" in line, line
    p, _, _ = _igr(c4.core.parent / "cef_c4")
    assert p[p.index < EX].round(6).eq(RAW_PRE).all()


def test_basis_steps_flags_runs_on_either_series_and_not_a_revision():
    old = pd.DataFrame({"ticker": ["A"] * 4, "date": pd.bdate_range("2026-09-01", periods=4),
                        "close": [5.0, 5.0, 5.0, 5.0]})
    new = old.assign(close=[15.0, 15.0, 5.1, 5.0])                  # a x3 run, then a 2% revision
    hits = dg.basis_steps(new, old, None, None)
    assert [(h["series"], h["ticker"], h["rows"]) for h in hits] == [("close", "A", 2)]
    assert dg.basis_steps(old.assign(close=[5.1] * 4), old, None, None) == []


# ------------------------------------------------- 3. a clean fetch is unchanged

def test_a_clean_c4_fetch_is_the_same_bytes_with_and_without_the_basis_code(c4, tmp_path,
                                                                          monkeypatch):
    """Nothing to convert (Yahoo serves IGR raw, no split declared): the fetch's exit,
    output and panel bytes are those of the same fetch with the price-basis code off
    (`split_rulings` None, the old path)."""
    P, N = stored_panels()
    frames = yahoo_frames(adjusted=False, declare=False)
    rc, out, files, *_ = c4(ASOF, P, N, frames)
    monkeypatch.setattr(db, "C4_FETCH_SPLIT_RULINGS", None)
    monkeypatch.setattr(db, "C4_DIR", tmp_path / "off")
    assert fd.resolve_data_book("c4").split_rulings is None
    rc2, out2, files2, *_ = run(fd, monkeypatch, tmp_path / "off", list(ASOF) + ["--data-book", "c4"],
                                P, N, frames, core=False)
    assert (rc, out, files) == (rc2, out2, files2)
    assert "BASIS" not in out


# ------------------------------------------------- 4. the core's fetch, byte-identical

def test_the_cores_fetch_has_no_price_basis_code_and_is_cee16ads_on_a_step(tmp_path, monkeypatch):
    """The core's data book carries no rulings, so neither the conversion nor the step guard
    runs: on a fetch whose closes step x3 against the stored ones, it writes them, exactly as
    cee16ad's fetch_daily does (exit, output, files, requests)."""
    from scripts.cef.tests.noop_base import load_at_base
    assert fd.resolve_data_book(None).split_rulings is None
    base = load_at_base("scripts/cef/fetch_daily.py", "fetch_daily_cee16ad_basis", tmp_path, monkeypatch)
    frames = core_frames()
    f = frames["AAA"].copy()
    f[["Open", "High", "Low", "Close"]] = f[["Open", "High", "Low", "Close"]] * 3
    frames["AAA"] = f
    got = []
    for label, mod in (("run_base", base), ("run_new", fd)):
        P, N = core_panels()
        got.append(run(mod, monkeypatch, tmp_path / label, list(ASOF), P, N, frames, errors=("DDD",)))
    assert got[0] == got[1]


# ------------------------------------------------- 5. the repair of a panel the bad fetch wrote

def test_repair_basis_puts_the_written_window_back_and_then_the_fetch_passes(c4, tmp_path):
    """The VM's case: a panel whose IGR pre-split window a past fetch wrote x3. Without the
    repair the fixed fetch refuses it (a x1/3 step against the stored rows); `repair-basis`
    converts exactly those rows, logs each, is idempotent, and the next fetch passes."""
    P, N = stored_panels()
    bad = P.copy()
    m = (bad.ticker == "IGR") & (bad.date < EX)
    bad.loc[m, ["open", "high", "low", "close"]] = bad.loc[m, ["open", "high", "low", "close"]] * 3
    bad.loc[m, "volume"] = 1000
    d = tmp_path / "vm"
    d.mkdir()
    fd.atomic_write(bad, d / "cef_prices.parquet")
    fd.atomic_write(N, d / "cef_nav.parquet")
    out = db.repair_basis(panel_dir=d, lock_wait_s=1.0)
    assert out["repaired"] == int(m.sum()) and out["by_ticker"]["IGR"]["converted"] == int(m.sum())
    R = pd.read_parquet(d / "cef_prices.parquet")
    assert R[(R.ticker == "IGR") & (R.date < EX)]["close"].round(6).eq(RAW_PRE).all()
    assert (R[(R.ticker == "IGR") & (R.date < EX)]["volume"] == 3000).all()
    pd.testing.assert_frame_equal(R[R.ticker != "IGR"].reset_index(drop=True),
                                  bad[bad.ticker != "IGR"].reset_index(drop=True))
    log = pd.read_csv(d / db.REPAIR_LOG)
    assert len(log) == int(m.sum()) and set(log["ticker"]) == {"IGR"}
    assert db.repair_basis(panel_dir=d, lock_wait_s=1.0)["repaired"] == 0      # idempotent
    # The fixed fetch over the repaired panel passes; over the unrepaired one it refuses.
    rc, out, *_ = c4(ASOF, R, N, yahoo_frames())
    assert rc == 0, out


def test_the_fixed_fetch_refuses_a_panel_the_bad_fetch_wrote_until_repaired(c4):
    P, N = stored_panels()
    bad = P.copy()
    m = (bad.ticker == "IGR") & (bad.date < EX)
    bad.loc[m, ["open", "high", "low", "close"]] = bad.loc[m, ["open", "high", "low", "close"]] * 3
    rc, out, *_ = c4(ASOF, bad, N, yahoo_frames())
    assert rc == fd.EXIT_BASIS and "repair-basis" in out, out


def test_the_research_guard_refuses_a_fetch_treatment():
    """`to_nav_basis` is the live fetch's treatment; the research path's split guard
    refuses a rulings file that carries one, so it can never be booked as a return rule."""
    R, _ = dg.load_split_rulings(db.C4_FETCH_SPLIT_RULINGS)
    assert list(R["treatment"]) == ["to_nav_basis"] and list(R["ticker"]) == ["IGR"]
    k = pd.DataFrame({"IGR": [1.0, F]}, index=[EX - pd.Timedelta(days=1), EX])
    r = pd.DataFrame({"IGR": [0.0, 2.0]}, index=k.index)
    with pytest.raises(dg.SplitBasisError, match="live fetch"):
        dg.guard_split_basis(r, k, rulings=db.C4_FETCH_SPLIT_RULINGS, series="close")
