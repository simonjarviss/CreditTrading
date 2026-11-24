"""fetch_daily never merges a fetched row with no close, or no NAV (fix approved by the team lead, 2026-10-28).

The price half is first; the NAV half (the NAV merge, the stale check and the
as-of NAV check, which the price half's reviewers found unguarded) follows THE
NAV HALF below.

WHY. When Yahoo's chart response carries a dividend (or split) for a date with no
bar, yfinance 0.2.66 emits a row for that date with every price NaN and volume
filled to 0 (`yfinance/utils.py` `safe_merge_dfs`, "row of NaNs";
`scrapers/history.py` `Volume.fillna(0)`). fetch_daily wrote it unchecked, and its
`drop_duplicates(keep="last")` let it replace a good bar. Measured 2026-10-28,
read-only, on the laptop's `data/cef/cef_prices.parquet` (to 2026-10-15) against
its 2026-09-28 backup: 15 good 2026-09-15 bars had become empty rows (BGT BIT EFR
EFT HYT JFR MHD MQY NAD NAN NEA NIM NVG NXP NZF; BIT HYT JFR MHD MQY are in the
live 13), and the panel held 65 empty-close rows against the backup's 49, every
one with volume 0. `--require-asof` counted such a row as the as-of close.

The bar values below are those panels' rows, copied as test fixtures (the
2026-09-15 bars from the backup; DHY's 2026-09-28 bar and empty 2026-09-30 row and
FCT's zero-volume 2026-08-10 bar from the current panel). They pin the code's
behaviour on the incident's own shapes; they are not a claim about the market.

Each test drives the real `refresh` with yfinance replaced by a fake that returns
frames in yfinance's own shape. Hermetic: every path is monkeypatched into
tmp_path (the root conftest refuses a write under data/) and no network is
reached (netguard).
"""
import math
import types
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from ops.common import atomic_write
from scripts.cef import fetch_daily as fd

PANEL_COLS = ["date", "open", "high", "low", "close", "volume", "ticker", "grp"]

# 2026-09-15 bars that the 2026-10-15 refresh turned into empty rows, read from
# data/cef/cef_prices.parquet.pre-20261015.bak: (ticker, grp, open, high, low, close, volume).
SEP15_LOST = [
    ("BGT", "loan", 10.81, 10.83, 10.72, 10.72, 137400),
    ("BIT", "multi", 11.55, 11.60, 11.48, 11.49, 616900),
    ("EFR", "loan", 10.32, 10.40, 10.28, 10.28, 153100),
    ("EFT", "loan", 10.45, 10.47, 10.43, 10.45, 128900),
    ("HYT", "hy", 8.02, 8.06, 7.98, 7.98, 1365200),
    ("JFR", "loan", 7.46, 7.48, 7.44, 7.44, 869300),
    ("MHD", "muni", 10.94, 10.94, 10.67, 10.83, 1128300),
    ("MQY", "muni", 10.49, 10.54, 10.32, 10.32, 2038400),
    ("NAD", "muni", 10.79, 10.91, 10.65, 10.73, 1845900),
    ("NAN", "muni", 10.34, 10.37, 10.10, 10.13, 212300),
    ("NEA", "muni", 10.62, 10.63, 10.49, 10.53, 2107600),
    ("NIM", "muni", 8.90, 9.02, 8.90, 8.97, 30100),
    ("NVG", "muni", 11.40, 11.43, 11.27, 11.28, 1125500),
    ("NXP", "muni", 13.63, 13.66, 13.42, 13.46, 304500),
    ("NZF", "muni", 11.39, 11.41, 11.24, 11.28, 1261700),
]
SEP15 = pd.Timestamp("2026-09-15")
NAN = float("nan")


def bar(ticker, grp, date, o, h, l, c, v):
    return {"date": pd.Timestamp(date), "open": o, "high": h, "low": l, "close": c,
            "volume": v, "ticker": ticker, "grp": grp}


def empty(ticker, grp, date, close=NAN):
    """The row yfinance emits for a corporate action with no bar: no prices, volume 0."""
    return bar(ticker, grp, date, NAN, NAN, NAN, close, 0)


def panel(rows) -> pd.DataFrame:
    P = pd.DataFrame(rows, columns=PANEL_COLS)
    P["volume"] = P["volume"].astype("int64")
    return P.sort_values(["ticker", "date"]).reset_index(drop=True)


def yf_frame(rows) -> pd.DataFrame:
    """Panel-shaped rows in the shape `yf.Ticker(tk).history(auto_adjust=False)`
    returns: a tz-aware 'Date' index, float prices, int64 Volume, and a nonzero
    Dividends on a row that has no prices (that dividend is why yfinance keeps it)."""
    if not rows:
        return pd.DataFrame()
    f = pd.DataFrame(rows)
    out = pd.DataFrame({
        "Open": f["open"].astype(float), "High": f["high"].astype(float),
        "Low": f["low"].astype(float), "Close": f["close"].astype(float),
        "Adj Close": f["close"].astype(float),
        "Volume": f["volume"].astype("int64"),
        "Dividends": np.where(np.isfinite(f["close"].astype(float)), 0.0, 0.06),
        "Stock Splits": 0.0, "Capital Gains": 0.0})
    out.index = pd.DatetimeIndex(f["date"]).tz_localize("America/New_York")
    out.index.name = "Date"
    return out


def nav_frame(ticker, dates, nav=10.0) -> pd.DataFrame:
    rows = [bar(ticker, "", d, nav, nav, nav, nav, 0) for d in dates]
    return yf_frame(rows)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Point every path fetch_daily touches into tmp_path, fake yfinance, and run
    `refresh` after the close. Returns run(P, N, fetched, navs, **kw) -> (rc, out)."""
    monkeypatch.setattr(fd, "PX_PATH", tmp_path / "cef_prices.parquet")
    monkeypatch.setattr(fd, "NAV_PATH", tmp_path / "cef_nav.parquet")
    monkeypatch.setattr(fd, "LOCK_PATH", tmp_path / ".fetch.lock")
    monkeypatch.setattr(fd, "FALLBACK_LOG", tmp_path / "nav_fallback_log.csv")
    monkeypatch.setattr(fd, "before_close", lambda now: False)

    def run(P, N, fetched, navs, errors=(), require_asof=None, capsys=None,
            nav_fallback=None):
        atomic_write(P, fd.PX_PATH)
        atomic_write(N, fd.NAV_PATH)

        class Ticker:
            def __init__(self, sym):
                self.sym = sym

            def history(self, period, auto_adjust):
                tk = self.sym[1:-1] if self.sym.startswith("X") and self.sym.endswith("X") else self.sym
                if tk in errors:
                    raise ConnectionError("fake yfinance outage")
                if self.sym == tk:
                    return yf_frame(fetched.get(tk, []))
                return navs.get(tk, pd.DataFrame())

        monkeypatch.setattr(fd, "yf", types.SimpleNamespace(Ticker=Ticker))
        rc = fd.refresh("6mo", require_asof, nav_fallback, None)
        out = capsys.readouterr().out if capsys is not None else ""
        return rc, out
    return run


def nav_panel(tickers, dates, nav=10.0) -> pd.DataFrame:
    return pd.DataFrame([{"date": pd.Timestamp(d), "nav": nav, "ticker": t}
                         for t in tickers for d in dates])


def lines(out, tag):
    return [ln.strip() for ln in out.splitlines() if ln.strip().startswith(tag)]


def row(P, ticker, date):
    r = P[(P["ticker"] == ticker) & (P["date"] == pd.Timestamp(date))]
    assert len(r) <= 1, f"duplicate {ticker} {date}"
    return None if r.empty else r.iloc[0]


# --------------------------------------------------------------------------------

def test_an_empty_row_does_not_overwrite_a_good_bar(env, capsys):
    """The 2026-10-15 incident replayed: the panel holds the 15 good 2026-09-15
    bars, the fetch returns an empty 2026-09-15 row for each. All 15 bars survive,
    and each refused row is named with its date and why."""
    P = panel([bar(t, g, SEP15, o, h, l, c, v) for t, g, o, h, l, c, v in SEP15_LOST])
    N = nav_panel([t for t, *_ in SEP15_LOST], [SEP15])
    fetched = {t: [empty(t, g, SEP15)] for t, g, *_ in SEP15_LOST}
    rc, out = env(P, N, fetched, {}, capsys=capsys)
    assert rc == 0
    got = pd.read_parquet(fd.PX_PATH)
    for t, g, o, h, l, c, v in SEP15_LOST:
        r = row(got, t, SEP15)
        assert r is not None and r["close"] == c and r["volume"] == v, \
            f"{t} 2026-09-15 bar {c} on {v} was overwritten by an empty row: {r}"
    refused = lines(out, "NO CLOSE")
    assert len(refused) == len(SEP15_LOST) == 15
    for t, *_ in SEP15_LOST:
        hit = [ln for ln in refused if f" {t} " in ln and "2026-09-15" in ln]
        assert len(hit) == 1 and "kept" in hit[0], (t, refused)


@pytest.mark.parametrize("close", [NAN, math.inf, -math.inf], ids=["nan", "inf", "-inf"])
def test_an_empty_row_for_a_new_date_is_not_written_and_is_logged(env, capsys, close):
    """DHY's 2026-09-30 row (empty in the laptop panel today). A close that is not
    finite is no close, whatever else the row carries."""
    good = bar("DHY", "hy", "2026-09-28", 1.62, 1.64, 1.61, 1.61, 949700)
    P = panel([bar("DHY", "hy", "2026-09-25", 1.62, 1.63, 1.61, 1.62, 1045100)])
    N = nav_panel(["DHY"], ["2026-09-25"])
    rc, out = env(P, N, {"DHY": [good, empty("DHY", "hy", "2026-09-30", close)]}, {},
                  capsys=capsys)
    assert rc == 0
    got = pd.read_parquet(fd.PX_PATH)
    assert row(got, "DHY", "2026-09-30") is None, "an empty row was written as a new date"
    assert row(got, "DHY", "2026-09-28")["close"] == 1.61, "the good bar beside it was lost"
    refused = lines(out, "NO CLOSE")
    assert len(refused) == 1
    assert " DHY " in refused[0] and "2026-09-30" in refused[0] and "not written" in refused[0]


def test_a_good_bar_replaces_an_existing_empty_row_and_is_logged(env, capsys):
    """HYT 2026-09-15 is empty in the laptop panel now. A later fetch that has the
    bar repairs it, and the repair is named; the empty row never wins the other way."""
    P = panel([bar("HYT", "hy", "2026-09-12", 8.05, 8.07, 8.01, 8.03, 900000),
               empty("HYT", "hy", SEP15)])
    N = nav_panel(["HYT"], ["2026-09-12", SEP15])
    t, g, o, h, l, c, v = next(x for x in SEP15_LOST if x[0] == "HYT")
    rc, out = env(P, N, {"HYT": [bar(t, g, SEP15, o, h, l, c, v)]}, {}, capsys=capsys)
    assert rc == 0
    r = row(pd.read_parquet(fd.PX_PATH), "HYT", SEP15)
    assert r["close"] == 7.98 and r["volume"] == 1365200
    repaired = lines(out, "REPAIRED")
    assert len(repaired) == 1, out
    assert " HYT " in repaired[0] and "2026-09-15" in repaired[0] and "7.98" in repaired[0]
    assert not lines(out, "NO CLOSE")


@pytest.mark.parametrize("fetch", ["returns_the_empty_row_again", "fails_for_that_name"])
def test_require_asof_refuses_an_empty_as_of_row(env, capsys, fetch):
    """The panel already holds an empty HYT 2026-09-15 row (it does on the laptop).
    Whether the fetch brings the same empty row again or brings nothing for HYT, the
    as-of check must refuse HYT for 2026-09-15 exactly as for a missing row: exit 4,
    the date in the INCOMPLETE line, HYT named as having no close. BIT is complete."""
    P = panel([bar("BIT", "multi", SEP15, 11.55, 11.60, 11.48, 11.49, 616900),
               empty("HYT", "hy", SEP15)])
    N = nav_panel(["BIT", "HYT"], [SEP15])
    fetched = {"BIT": [bar("BIT", "multi", SEP15, 11.55, 11.60, 11.48, 11.49, 616900)]}
    errors = ()
    if fetch == "returns_the_empty_row_again":
        fetched["HYT"] = [empty("HYT", "hy", SEP15)]
    else:
        errors = ("HYT",)
    rc, out = env(P, N, fetched, {}, errors=errors, require_asof="2026-09-15", capsys=capsys)
    assert rc == 4, out
    inc = lines(out, "INCOMPLETE")
    assert len(inc) == 1 and "2026-09-15" in inc[0] and "1 deployed name(s)" in inc[0], inc
    assert "HYT: no close" in inc[0] and "BIT" not in inc[0], inc


def test_a_real_zero_volume_day_with_a_close_is_kept(env, capsys):
    """Volume 0 is not 'empty'. FCT traded no shares on 2026-08-10 and printed 9.67
    (one of 20 such rows in the panel). That bar is written and is the as-of close;
    the empty row HYT brings in the same fetch is not. A fix keyed on volume would
    drop FCT; the old code writes HYT's empty row."""
    P = panel([bar("FCT", "loan", "2026-08-07", 9.66, 9.70, 9.66, 9.70, 1200),
               bar("HYT", "hy", "2026-08-07", 8.40, 8.42, 8.38, 8.40, 800000)])
    N = nav_panel(["FCT", "HYT"], ["2026-08-07", "2026-08-10"])
    fetched = {"FCT": [bar("FCT", "loan", "2026-08-10", 9.67, 9.67, 9.67, 9.67, 0)],
               "HYT": [bar("HYT", "hy", "2026-08-10", 8.41, 8.43, 8.39, 8.42, 700000),
                       empty("HYT", "hy", "2026-08-11")]}
    rc, out = env(P, N, fetched, {}, require_asof="2026-08-10", capsys=capsys)
    assert rc == 0, out
    got = pd.read_parquet(fd.PX_PATH)
    r = row(got, "FCT", "2026-08-10")
    assert r is not None and r["close"] == 9.67 and r["volume"] == 0
    assert row(got, "HYT", "2026-08-11") is None
    refused = lines(out, "NO CLOSE")
    assert len(refused) == 1 and " HYT " in refused[0] and "2026-08-11" in refused[0]
    assert not any(" FCT " in ln for ln in refused)


def test_with_no_empty_rows_a_fetch_is_byte_identical_to_before(env, capsys, tmp_path):
    """The no-op proof. (a) A fetch with no empty rows writes exactly the bytes the
    pre-fix merge wrote (concat, drop_duplicates keep='last', sort), and logs
    nothing new. (b) Adding empty rows to that same fetch -- over good bars, over
    nothing, on dates the panel lacks -- changes not one byte of either panel."""
    P = panel([bar("BIT", "multi", "2026-09-12", 11.50, 11.56, 11.45, 11.52, 500000),
               bar("BIT", "multi", SEP15, 11.55, 11.60, 11.48, 11.49, 616900),
               bar("HYT", "hy", "2026-09-12", 8.05, 8.07, 8.01, 8.03, 900000),
               bar("HYT", "hy", SEP15, 8.02, 8.06, 7.98, 7.98, 1365200)])
    N = nav_panel(["BIT", "HYT"], ["2026-09-12", SEP15])
    clean = {"BIT": [bar("BIT", "multi", SEP15, 11.55, 11.60, 11.48, 11.50, 616900),   # restated
                     bar("BIT", "multi", "2026-09-16", 11.49, 11.53, 11.40, 11.41, 410000)],
             "HYT": [bar("HYT", "hy", "2026-09-16", 7.99, 8.00, 7.93, 7.95, 1100000)]}
    navs = {t: nav_frame(t, ["2026-09-16"]) for t in clean}

    # (a) against the pre-fix merge, done here by hand on the same rows.
    rc, out = env(P, N, clean, navs, capsys=capsys)
    assert rc == 0
    a_px, a_nav = fd.PX_PATH.read_bytes(), fd.NAV_PATH.read_bytes()
    new = [pd.DataFrame(rows, columns=PANEL_COLS).astype({"volume": "int64"})
           for rows in clean.values()]
    ref = (pd.concat([P] + new, ignore_index=True)
             .drop_duplicates(subset=["date", "ticker"], keep="last")
             .sort_values(["ticker", "date"]))
    ref_path = tmp_path / "reference.parquet"
    atomic_write(ref, ref_path)
    assert a_px == ref_path.read_bytes(), "a clean fetch no longer writes what it wrote before"
    assert not lines(out, "NO CLOSE") and not lines(out, "REPAIRED")

    # (b) the same fetch with empty rows mixed in.
    dirty = {"BIT": clean["BIT"] + [empty("BIT", "multi", "2026-09-12"),
                                    empty("BIT", "multi", "2026-09-17")],
             "HYT": [empty("HYT", "hy", SEP15)] + clean["HYT"]}
    rc, out = env(P, N, dirty, navs, capsys=capsys)
    assert rc == 0
    assert fd.PX_PATH.read_bytes() == a_px, "empty rows changed the price panel"
    assert fd.NAV_PATH.read_bytes() == a_nav, "empty rows changed the NAV panel"
    assert len(lines(out, "NO CLOSE")) == 3


# ================================================================================
# THE NAV HALF (team lead's approval, 2026-10-28; fetch_daily docstring, EMPTY NAV
# ROWS). The reviewers of the price half found the NAV merge, the stale check and
# the as-of NAV check unguarded. The real NAV panel (laptop, to 2026-10-14) holds
# no NAV that is not finite, so the NAV values below are test fixtures in the
# panel's shape, not a claim that Yahoo has served such rows. Each test drives
# the real `refresh`, as above.

def navs_frame(pairs) -> pd.DataFrame:
    """A yfinance X<TK>X history frame from (date, nav) pairs; a nav that is not
    finite makes that row empty, as yfinance emits it (prices NaN, volume 0,
    an event on the row)."""
    return yf_frame([bar("", "", d, v, v, v, v, 0) for d, v in pairs])


def price_stub(tickers, dates) -> pd.DataFrame:
    """Price rows, so `refresh` has these tickers to fetch; no price is fetched."""
    return panel([bar(t, "x", d, 10.0, 10.0, 10.0, 10.0, 1000) for t in tickers for d in dates])


def nav_of(N, ticker, date):
    r = N[(N["ticker"] == ticker) & (N["date"] == pd.Timestamp(date))]
    assert len(r) <= 1, f"duplicate NAV {ticker} {date}"
    return None if r.empty else float(r["nav"].iloc[0])


def test_an_empty_nav_does_not_overwrite_a_good_nav(env, capsys):
    """The price incident's shape on the NAV panel: the panel holds good
    2026-09-15 NAVs and the fetch returns an empty 2026-09-15 row for each. Both
    NAVs survive, and each refused row is named with its date and why. The old
    merge wrote NaN over both."""
    P = price_stub(["BIT", "HYT"], [SEP15])
    N = pd.DataFrame([{"date": SEP15, "nav": 12.31, "ticker": "BIT"},
                      {"date": SEP15, "nav": 8.71, "ticker": "HYT"}])
    navs = {t: navs_frame([(SEP15, NAN)]) for t in ("BIT", "HYT")}
    rc, out = env(P, N, {}, navs, capsys=capsys)
    assert rc == 0
    got = pd.read_parquet(fd.NAV_PATH)
    assert nav_of(got, "BIT", SEP15) == 12.31 and nav_of(got, "HYT", SEP15) == 8.71, \
        f"a good NAV was overwritten by an empty row:\n{got}"
    refused = lines(out, "NO NAV")
    assert len(refused) == 2, out
    for t in ("BIT", "HYT"):
        hit = [ln for ln in refused if f" {t} " in ln and "2026-09-15" in ln]
        assert len(hit) == 1 and "kept" in hit[0], (t, refused)


@pytest.mark.parametrize("nav", [NAN, math.inf, -math.inf], ids=["nan", "inf", "-inf"])
def test_an_empty_nav_for_a_new_date_is_not_written_and_is_logged(env, capsys, nav):
    """A NAV that is not finite is no NAV. It is not written for a date the
    panel lacks, the good NAV fetched beside it is, and the refusal is named."""
    P = price_stub(["DHY"], ["2026-09-25"])
    N = nav_panel(["DHY"], ["2026-09-25"], nav=2.03)
    navs = {"DHY": navs_frame([("2026-09-28", 2.04), ("2026-09-30", nav)])}
    rc, out = env(P, N, {}, navs, capsys=capsys)
    assert rc == 0
    got = pd.read_parquet(fd.NAV_PATH)
    assert nav_of(got, "DHY", "2026-09-30") is None, "an empty NAV was written as a new date"
    assert nav_of(got, "DHY", "2026-09-28") == 2.04, "the good NAV beside it was lost"
    refused = lines(out, "NO NAV")
    assert len(refused) == 1, out
    assert " DHY " in refused[0] and "2026-09-30" in refused[0] and "not written" in refused[0]


def test_a_good_nav_repairs_an_empty_nav_row_and_is_logged(env, capsys):
    """A panel NAV row that is empty is replaced by a fetched NAV, and the
    repair is named (the old merge repaired it silently)."""
    P = price_stub(["HYT"], ["2026-09-12", SEP15])
    N = pd.DataFrame([{"date": pd.Timestamp("2026-09-12"), "nav": 8.70, "ticker": "HYT"},
                      {"date": SEP15, "nav": NAN, "ticker": "HYT"}])
    rc, out = env(P, N, {}, {"HYT": navs_frame([(SEP15, 8.71)])}, capsys=capsys)
    assert rc == 0
    assert nav_of(pd.read_parquet(fd.NAV_PATH), "HYT", SEP15) == 8.71
    repaired = lines(out, "NAV REPAIRED")
    assert len(repaired) == 1, out
    assert " HYT " in repaired[0] and "2026-09-15" in repaired[0] and "8.71" in repaired[0]
    assert not lines(out, "NO NAV")


@pytest.mark.parametrize("fetch", ["returns_the_empty_nav_again", "fails_for_that_name"])
def test_require_asof_refuses_an_empty_as_of_nav(env, capsys, fetch):
    """The panel holds an empty HYT NAV row for 2026-09-15. Whether the fetch
    brings the same empty row or nothing for HYT, with no fallback the as-of
    check refuses HYT exactly as for a missing NAV: exit 4, the date named, the
    row named as empty. BIT is complete. The old check counted the row as D's
    NAV and passed."""
    P = panel([bar("BIT", "multi", SEP15, 11.55, 11.60, 11.48, 11.49, 616900),
               bar("HYT", "hy", SEP15, 8.02, 8.06, 7.98, 7.98, 1365200)])
    N = pd.DataFrame([{"date": SEP15, "nav": 12.31, "ticker": "BIT"},
                      {"date": SEP15, "nav": NAN, "ticker": "HYT"}])
    navs, errors = {"BIT": navs_frame([(SEP15, 12.31)])}, ()
    if fetch == "returns_the_empty_nav_again":
        navs["HYT"] = navs_frame([(SEP15, NAN)])
    else:
        errors = ("HYT",)
    rc, out = env(P, N, {}, navs, errors=errors, require_asof="2026-09-15", capsys=capsys)
    assert rc == 4, out
    inc = lines(out, "INCOMPLETE")
    assert len(inc) == 1 and "2026-09-15" in inc[0] and "1 deployed name(s)" in inc[0], inc
    assert "HYT: no NAV (its 2026-09-15 row is empty)" in inc[0] and "BIT" not in inc[0], inc


def test_an_empty_as_of_nav_goes_to_the_cefconnect_fallback_like_a_missing_one(
        env, capsys, monkeypatch):
    """With --nav-fallback cefconnect, an empty NAV row for D is filled from
    CEFConnect exactly as a missing one is: written over the empty row, logged
    in the fallback log, and the line says why. The old check never asked."""
    P = panel([bar("HYT", "hy", SEP15, 8.02, 8.06, 7.98, 7.98, 1365200)])
    N = pd.DataFrame([{"date": SEP15, "nav": NAN, "ticker": "HYT"}])
    asked = []
    monkeypatch.setattr(fd, "_cefconnect_nav",
                        lambda tk, asof: asked.append((tk, asof)) or 8.71)
    rc, out = env(P, N, {}, {}, errors=("HYT",), require_asof="2026-09-15",
                  nav_fallback="cefconnect", capsys=capsys)
    assert rc == 0, out
    assert asked == [("HYT", SEP15)]
    assert nav_of(pd.read_parquet(fd.NAV_PATH), "HYT", SEP15) == 8.71
    log = pd.read_csv(fd.FALLBACK_LOG)
    assert log[["ticker", "nav", "source"]].values.tolist() == [["HYT", 8.71, "cefconnect"]]
    (ln,) = lines(out, "NAV HYT")
    assert "2026-09-15 = 8.71 from CEFConnect" in ln and "has no NAV" in ln, ln


@pytest.mark.parametrize("cc", [NAN, math.inf], ids=["nan", "inf"])
def test_a_cefconnect_nav_that_is_not_finite_is_not_written(env, capsys, monkeypatch, cc):
    """The fallback must not write the empty NAV it exists to replace. HYT stays
    incomplete (exit 4), nothing reaches the panel or the fallback log, and the
    refusal is named. The old fallback wrote it and passed the pair."""
    P = panel([bar("HYT", "hy", SEP15, 8.02, 8.06, 7.98, 7.98, 1365200)])
    N = nav_panel(["HYT"], ["2026-09-12"], nav=8.70)
    monkeypatch.setattr(fd, "_cefconnect_nav", lambda tk, asof: cc)
    rc, out = env(P, N, {}, {}, errors=("HYT",), require_asof="2026-09-15",
                  nav_fallback="cefconnect", capsys=capsys)
    assert rc == 4, out
    assert nav_of(pd.read_parquet(fd.NAV_PATH), "HYT", SEP15) is None
    assert not fd.FALLBACK_LOG.exists()
    (ln,) = lines(out, "NO NAV")
    assert " HYT " in ln and "2026-09-15" in ln and "CEFConnect" in ln and "not written" in ln


def et_today():
    """The date the stale check ages NAVs to: this run's ET date (fetch_daily
    FOLLOW-UPS (2)), so these tests agree with it on a UTC machine too."""
    return pd.Timestamp(datetime.now(fd.ET).date())


def _bd_age(d, today):
    """The stale check's own age arithmetic, as fetch_daily has always done it."""
    return len(pd.bdate_range(pd.Timestamp(d), today)) - 1


def test_an_empty_nav_row_never_makes_a_fund_look_fresh(env, capsys):
    """The stale check (fetch_daily docstring, EMPTY NAV ROWS). HYT's last real
    NAV is eight business days old and its fetch ends in an empty row dated
    yesterday; BIT's fetch is nothing but empty rows. The old check dated each
    fund by its last ROW and called both fresh. Both are stale now: HYT dated
    by its last real NAV, BIT listed first as having none. Dates are relative
    to today because the check reads today's date."""
    today = et_today()
    good, recent = today - pd.offsets.BDay(8), today - pd.offsets.BDay(1)
    P = price_stub(["BIT", "HYT"], [good])
    N = nav_panel(["BIT", "HYT"], [good], nav=10.0)
    navs = {"HYT": navs_frame([(good, 10.0), (recent, NAN)]),
            "BIT": navs_frame([(good, NAN), (recent, NAN)])}
    rc, out = env(P, N, {}, navs, capsys=capsys)
    assert rc == 0
    assert "NAV series fresh" not in out, out
    body = out.splitlines()
    i = next(k for k, ln in enumerate(body) if ln.startswith("  STALE NAV"))
    assert body[i] == ("  STALE NAV (2 funds, >3 business days old) — "
                       "the sleeve must not trade these:")
    assert body[i + 1] == ("    BIT    last NAV none: no finite positive NAV in the "
                           "2 row(s) fetched")
    assert body[i + 2] == (f"    HYT    last NAV {good.date()}  "
                           f"({_bd_age(good, today)} bd old)")


def _old_stale_block(navs, n_tickers, today):
    """What the pre-fix code printed after the NAV line, rebuilt by hand from
    its source (a8c3720..4487383, fetch_daily.py): date each fetched fund by
    its last row, list those older than STALE_BD sorted by -age, else 'all N
    fresh'. Used only on fetches with no empty row, where the fix must not
    change one character."""
    stale = []
    for tk in sorted(navs):
        last = pd.DatetimeIndex(navs[tk].index).tz_localize(None).normalize().max()
        age = _bd_age(last, today)
        if age > fd.STALE_BD:
            stale.append((tk, str(last.date()), age))
    if not stale:
        return [f"  all {n_tickers} NAV series fresh within {fd.STALE_BD} bd"]
    return ([f"  STALE NAV ({len(stale)} funds, >{fd.STALE_BD} business days old) — "
             f"the sleeve must not trade these:"]
            + [f"    {tk:<6} last NAV {d}  ({age} bd old)"
               for tk, d, age in sorted(stale, key=lambda x: -x[2])])


def _after_nav_line(out):
    body = out.splitlines()
    i = next(k for k, ln in enumerate(body) if ln.startswith("  NAV    "))
    return body[i + 1:]


def test_with_no_empty_navs_a_fetch_is_byte_identical_to_before(env, capsys, tmp_path):
    """The no-op proof for the NAV half. (a) A NAV fetch with no empty row writes
    exactly the bytes the pre-fix merge wrote (concat, drop_duplicates
    keep='last', sort), prints exactly the stale lines the pre-fix check printed
    (one fund fresh, two stale, one of them tied), and logs nothing new. (b)
    The same fetch with empty rows mixed in -- over a good NAV, on a date the
    panel lacks, and one dated yesterday after a stale fund's last NAV --
    changes not one byte of either panel and not one stale line. Part (b) is
    what the old code fails: it wrote the NaNs and called that fund fresh."""
    today = et_today()
    bd = lambda k: today - pd.offsets.BDay(k)                         # noqa: E731
    P = price_stub(["BIT", "HYT", "JFR"], [bd(12)])
    N = pd.DataFrame([{"date": bd(12), "nav": v, "ticker": t}
                      for t, v in (("BIT", 12.30), ("HYT", 8.70), ("JFR", 9.10))])
    clean = {"BIT": [(bd(12), 12.31), (bd(1), 12.35)],               # restated, then fresh
             "HYT": [(bd(7), 8.72)],                                 # stale, 7 bd
             "JFR": [(bd(7), 9.12)]}                                 # stale, tied with HYT
    navs = {t: navs_frame(v) for t, v in clean.items()}

    # (a) against the pre-fix merge and stale check, done here by hand.
    rc, out = env(P, N, {}, navs, capsys=capsys)
    assert rc == 0
    a_px, a_nav = fd.PX_PATH.read_bytes(), fd.NAV_PATH.read_bytes()
    new = [pd.DataFrame([{"date": d, "nav": v, "ticker": t} for d, v in rows])
           for t, rows in clean.items()]
    ref = (pd.concat([N] + new, ignore_index=True)
             .drop_duplicates(subset=["date", "ticker"], keep="last")
             .sort_values(["ticker", "date"]))
    ref_path = tmp_path / "reference_nav.parquet"
    atomic_write(ref, ref_path)
    assert a_nav == ref_path.read_bytes(), "a clean NAV fetch no longer writes what it wrote before"
    a_tail = _after_nav_line(out)
    assert a_tail == _old_stale_block(navs, 3, today), out
    assert not lines(out, "NO NAV") and not lines(out, "NAV REPAIRED")
    assert lines(out, "NAV    ") == [f"NAV    {len(ref):,} rows -> {ref.date.max().date()}"]

    # (b) the same fetch with empty rows mixed in.
    dirty = {"BIT": navs_frame(clean["BIT"] + [(bd(0), NAN)]),                # a new date
             "HYT": navs_frame([(bd(12), NAN)] + clean["HYT"]                 # over 8.70
                               + [(bd(1), NAN)]),                             # after its last NAV
             "JFR": navs_frame(clean["JFR"])}
    rc, out = env(P, N, {}, dirty, capsys=capsys)
    assert rc == 0
    assert fd.PX_PATH.read_bytes() == a_px, "empty NAV rows changed the price panel"
    assert fd.NAV_PATH.read_bytes() == a_nav, "empty NAV rows changed the NAV panel"
    assert _after_nav_line(out) == a_tail, "empty NAV rows changed the stale lines"
    assert len(lines(out, "NO NAV")) == 3


# ================================================================================
# FOLLOW-UPS (independent review of the NAV half, 2026-10-28; fetch_daily
# docstring, FOLLOW-UPS). Each failed on 377fe41.

@pytest.mark.parametrize("bad", [0.0, -1.0], ids=["zero", "negative"])
def test_a_nav_of_zero_or_below_is_no_nav(env, capsys, bad):
    """(1) A usable NAV is finite AND positive, gate 5's test. A fetched NAV of
    0 neither replaces BIT's good NAV nor counts; HYT's panel row of 0 dated D
    is not D's NAV, so with no fallback the as-of check refuses it as missing.
    On 377fe41 the 0 overwrote 12.31 and HYT passed, and gate 5 would then have
    refused the whole session."""
    P = panel([bar("BIT", "multi", SEP15, 11.55, 11.60, 11.48, 11.49, 616900),
               bar("HYT", "hy", SEP15, 8.02, 8.06, 7.98, 7.98, 1365200)])
    N = pd.DataFrame([{"date": SEP15, "nav": 12.31, "ticker": "BIT"},
                      {"date": SEP15, "nav": bad, "ticker": "HYT"}])
    rc, out = env(P, N, {}, {"BIT": navs_frame([(SEP15, bad)])}, errors=("HYT",),
                  require_asof="2026-09-15", capsys=capsys)
    assert nav_of(pd.read_parquet(fd.NAV_PATH), "BIT", SEP15) == 12.31
    (ln,) = lines(out, "NO NAV")
    assert " BIT " in ln and "2026-09-15" in ln and "kept" in ln, ln
    assert rc == 4, out
    (inc,) = lines(out, "INCOMPLETE")
    assert "HYT: no NAV (its 2026-09-15 row is empty)" in inc and "BIT" not in inc, inc


@pytest.mark.parametrize("bad", [0.0, -1.0], ids=["zero", "negative"])
def test_a_nav_of_zero_goes_to_the_fallback_and_a_cefconnect_zero_is_not_written(
        env, capsys, monkeypatch, bad):
    """(1), with --nav-fallback cefconnect. HYT's panel NAV of 0 dated D is sent
    to CEFConnect like a missing one and replaced by its NAV. A CEFConnect NAV
    of 0 is not written either (`read_cc` refuses it too): the name stays
    incomplete, and nothing reaches the panel or the fallback log."""
    P = panel([bar("HYT", "hy", SEP15, 8.02, 8.06, 7.98, 7.98, 1365200)])
    N = pd.DataFrame([{"date": SEP15, "nav": bad, "ticker": "HYT"}])
    monkeypatch.setattr(fd, "_cefconnect_nav", lambda tk, asof: 8.71)
    rc, out = env(P, N, {}, {}, errors=("HYT",), require_asof="2026-09-15",
                  nav_fallback="cefconnect", capsys=capsys)
    assert rc == 0, out
    assert nav_of(pd.read_parquet(fd.NAV_PATH), "HYT", SEP15) == 8.71
    (ln,) = lines(out, "NAV HYT")
    assert "has no NAV" in ln, ln

    fd.FALLBACK_LOG.unlink()
    N2 = nav_panel(["HYT"], ["2026-09-12"], nav=8.70)
    monkeypatch.setattr(fd, "_cefconnect_nav", lambda tk, asof: bad)
    rc, out = env(P, N2, {}, {}, errors=("HYT",), require_asof="2026-09-15",
                  nav_fallback="cefconnect", capsys=capsys)
    assert rc == 4, out
    assert nav_of(pd.read_parquet(fd.NAV_PATH), "HYT", SEP15) is None
    assert not fd.FALLBACK_LOG.exists()
    (ln,) = lines(out, "NO NAV")
    assert " HYT " in ln and "CEFConnect" in ln and "finite positive" in ln, ln


class _UtcNightClock(datetime):
    """fetch_daily's clock pinned at 2026-09-30 03:30 UTC: 23:30 ET on Tuesday
    2026-09-29, the hour the VM's machine date is already the 30th."""
    INSTANT = datetime(2026, 9, 30, 3, 30, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.INSTANT if tz is None else cls.INSTANT.astimezone(tz)


def test_the_stale_age_is_counted_to_the_runs_et_date(env, capsys, monkeypatch):
    """(2) HYT's last NAV is dated Thursday 2026-09-24. To the run's ET date,
    Tuesday the 29th, it is 3 business days old: fresh. To the UTC date (the
    30th) it would be 4, stale; and on 377fe41 the age was counted to whatever
    date the machine running this test has, which is later still."""
    monkeypatch.setattr(fd, "datetime", _UtcNightClock)
    P = price_stub(["HYT"], ["2026-09-24"])
    N = nav_panel(["HYT"], ["2026-09-24"], nav=8.70)
    rc, out = env(P, N, {}, {"HYT": navs_frame([("2026-09-23", 8.69), ("2026-09-24", 8.70)])},
                  capsys=capsys)
    assert rc == 0
    assert _after_nav_line(out) == ["  all 1 NAV series fresh within 3 bd"], out
    assert _bd_age("2026-09-24", pd.Timestamp("2026-09-29")) == 3       # the arithmetic


def test_a_fund_the_stale_check_never_saw_is_named_not_counted_fresh(env, capsys, monkeypatch):
    """(3) HYT's fetch raises and BIT's NAV fetch returns no rows: the stale
    check never dated either. On 377fe41 the run still printed "all 3 NAV
    series fresh". Now they are listed UNCHECKED, by name and why, and the
    fresh line says only that every series it CHECKED is fresh."""
    monkeypatch.setattr(fd, "datetime", _UtcNightClock)
    P = price_stub(["BIT", "HYT", "JFR"], ["2026-09-28"])
    N = nav_panel(["BIT", "HYT", "JFR"], ["2026-09-28"], nav=10.0)
    rc, out = env(P, N, {}, {"JFR": navs_frame([("2026-09-29", 10.0)])}, errors=("HYT",),
                  capsys=capsys)
    assert rc == 0
    assert "NAV series fresh within" not in out, out
    assert _after_nav_line(out) == [
        "  every NAV series checked is fresh within 3 bd, but not every series was checked:",
        "  UNCHECKED NAV (2 funds, freshness not measured): "
        "BIT (no NAV rows fetched); HYT (fetch error: ConnectionError)"]
