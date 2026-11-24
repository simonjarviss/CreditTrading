"""stage_cef never writes a row with no close or no NAV (team lead's approval, 2026-10-28).

WHY. stage_cef builds a fresh `data/` from the same yfinance `history()` call as
fetch_daily, which emits a row with every price NaN and volume 0 for a dividend
or split dated where there is no bar (scripts/cef/fetch_daily.py, EMPTY ROWS: by
2026-10-15 such rows had replaced 15 good 2026-09-15 bars in the laptop panel).
It is not on the live path -- a human runs it once -- but a prod with no panels
is seeded by copying them (quantt/deploy, SEED_FILES), and fetch_daily only
revisits the last six months, so an empty row staged years back would stay in
what the sleeve reads (stage_cef docstring, WHO RUNS THIS).

The bar values are the 2026-09-15 rows of the price incident's fixtures
(test_fetch_daily_empty_rows.py) and synthetic NAVs. They pin the code's
behaviour; they are not a claim about the market. Hermetic: yfinance is a fake,
every file goes to tmp_path (the root conftest refuses a write under data/), and
no network is reached (netguard).
"""
import types

import pandas as pd
import pytest

from ops.common import atomic_write
from scripts.cef import stage_cef as sc
from scripts.cef.tests.test_fetch_daily_empty_rows import NAN, bar, empty, yf_frame

DAYS = ["2026-09-10", "2026-09-11", "2026-09-12", "2026-09-15", "2026-09-16"]


def hyt_bars():
    return [bar("HYT", "hy", d, 8.02, 8.06, 7.98, 7.98 + i / 100, 1_000_000 + i)
            for i, d in enumerate(DAYS)]


def bit_bars():
    return [bar("BIT", "multi", d, 11.55, 11.60, 11.48, 11.49 + i / 100, 600_000 + i)
            for i, d in enumerate(DAYS)]


def navs(pairs):
    return yf_frame([bar("", "", d, v, v, v, v, 0) for d, v in pairs])


@pytest.fixture
def stage(tmp_path, monkeypatch):
    """Run stage_cef.main on a two-name universe into tmp_path. Returns
    run(prices, navs, min_days=3, min_nav=3) -> (rc, out, dir)."""
    def run(prices, nav, capsys, min_days=3, min_nav=3, out_dir=None):
        d = out_dir or tmp_path
        monkeypatch.setattr(sc, "OUT", d)
        monkeypatch.setattr(sc, "UNIVERSE", {"hy": ["HYT"], "multi": ["BIT"]})
        monkeypatch.setattr(sc, "MIN_DAYS", min_days)
        monkeypatch.setattr(sc, "MIN_NAV", min_nav)

        class Ticker:
            def __init__(self, sym):
                self.sym = sym

            def history(self, period, auto_adjust):
                assert period == "max" and auto_adjust is False
                if self.sym.startswith("X") and self.sym.endswith("X"):
                    return nav.get(self.sym[1:-1], pd.DataFrame())
                return yf_frame(prices.get(self.sym, []))

        monkeypatch.setattr(sc, "yf", types.SimpleNamespace(Ticker=Ticker))
        rc = sc.main()
        return rc, capsys.readouterr().out, d
    return run


def lines(out, tag):
    return [ln.strip() for ln in out.splitlines() if ln.strip().startswith(tag)]


def test_an_empty_row_is_not_staged_and_is_logged(stage, capsys):
    """HYT's price history has an empty 2026-09-15 row, BIT's NAV history an
    empty 2026-09-15 NAV. Neither is written; each is named with its date and
    why. The old stage_cef wrote both."""
    px = {"HYT": [b if b["date"] != pd.Timestamp("2026-09-15") else empty("HYT", "hy", b["date"])
                  for b in hyt_bars()],
          "BIT": bit_bars()}
    nv = {"HYT": navs([(d, 8.70) for d in DAYS]),
          "BIT": navs([(d, NAN if d == "2026-09-15" else 12.31) for d in DAYS])}
    rc, out, d = stage(px, nv, capsys)
    assert rc == 0, out
    P, N = pd.read_parquet(d / "cef_prices.parquet"), pd.read_parquet(d / "cef_nav.parquet")
    assert P["close"].notna().all() and N["nav"].notna().all(), (P, N)
    assert not ((P.ticker == "HYT") & (P.date == "2026-09-15")).any()
    assert not ((N.ticker == "BIT") & (N.date == "2026-09-15")).any()
    (c,) = lines(out, "NO CLOSE")
    (n,) = lines(out, "NO NAV")
    assert " HYT " in c and "2026-09-15" in c and "not written" in c
    assert " BIT " in n and "2026-09-15" in n and "not written" in n


@pytest.mark.parametrize("short", ["price", "nav"])
def test_an_empty_row_is_not_a_day_of_history(stage, capsys, short):
    """MIN_DAYS / MIN_NAV count rows that carry a close / a NAV. HYT has five
    rows, two of them empty; with a minimum of four it is too short and is not
    staged. The old count took the empty rows as history and staged it."""
    hyt = hyt_bars()
    nv_hyt = [(d, 8.70) for d in DAYS]
    if short == "price":
        hyt = [empty("HYT", "hy", b["date"]) if i in (1, 3) else b for i, b in enumerate(hyt)]
    else:
        nv_hyt = [(dd, NAN) if i in (1, 3) else (dd, v) for i, (dd, v) in enumerate(nv_hyt)]
    px = {"HYT": hyt, "BIT": bit_bars()}
    nv = {"HYT": navs(nv_hyt), "BIT": navs([(d, 12.31) for d in DAYS])}
    rc, out, d = stage(px, nv, capsys, min_days=4, min_nav=4)
    assert rc == 0, out
    assert set(pd.read_parquet(d / "cef_prices.parquet").ticker) == {"BIT"}
    want = "price history too short" if short == "price" else "no usable NAV feed"
    assert any(" HYT " in ln and want in ln for ln in lines(out, "skip")), out


def test_with_no_empty_rows_stage_cef_is_byte_identical_to_before(stage, capsys, tmp_path):
    """The no-op proof. (a) With no empty row the two panels are exactly the
    frames the pre-fix code built (the same reshaping, done here by hand, then
    concatenated), and nothing new is logged. (b) The same histories with empty
    rows added -- one in the middle, one as the LAST row, which the universe
    file's `last` close is read from -- write the same bytes to all three files.
    Part (b) is what the old code fails."""
    px = {"HYT": hyt_bars(), "BIT": bit_bars()}
    nv = {"HYT": navs([(d, 8.70) for d in DAYS]), "BIT": navs([(d, 12.31) for d in DAYS])}
    a = tmp_path / "a"
    a.mkdir()
    rc, out, _ = stage(px, nv, capsys, out_dir=a)
    assert rc == 0, out
    assert not lines(out, "NO CLOSE") and not lines(out, "NO NAV")

    def old_shape(tk, grp):
        f = yf_frame(px[tk]).reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
        f.columns = ["date", "open", "high", "low", "close", "volume"]
        f["date"] = pd.to_datetime(f["date"]).dt.tz_localize(None).dt.normalize()
        f["ticker"], f["grp"] = tk, grp
        return f

    def old_nav(tk):
        f = nv[tk].reset_index()[["Date", "Close"]]
        f.columns = ["date", "nav"]
        f["date"] = pd.to_datetime(f["date"]).dt.tz_localize(None).dt.normalize()
        f["ticker"] = tk
        return f

    # UNIVERSE order: hy (HYT) then multi (BIT).
    ref_p = pd.concat([old_shape("HYT", "hy"), old_shape("BIT", "multi")], ignore_index=True)
    ref_n = pd.concat([old_nav("HYT"), old_nav("BIT")], ignore_index=True)
    atomic_write(ref_p, tmp_path / "ref_p.parquet")
    atomic_write(ref_n, tmp_path / "ref_n.parquet")
    assert (a / "cef_prices.parquet").read_bytes() == (tmp_path / "ref_p.parquet").read_bytes()
    assert (a / "cef_nav.parquet").read_bytes() == (tmp_path / "ref_n.parquet").read_bytes()

    # (b) the same histories with empty rows mixed in.
    b = tmp_path / "b"
    b.mkdir()
    dirty_px = {"HYT": hyt_bars()[:3] + [empty("HYT", "hy", "2026-09-14")] + hyt_bars()[3:]
                + [empty("HYT", "hy", "2026-09-17")],
                "BIT": bit_bars()}
    dirty_nv = {"HYT": nv["HYT"],
                "BIT": navs([(d, 12.31) for d in DAYS] + [("2026-09-17", NAN)])}
    rc, out, _ = stage(dirty_px, dirty_nv, capsys, out_dir=b)
    assert rc == 0, out
    for name in ("cef_prices.parquet", "cef_nav.parquet", "cef_universe.csv"):
        assert (b / name).read_bytes() == (a / name).read_bytes(), f"empty rows changed {name}"
    assert len(lines(out, "NO CLOSE")) == 2 and len(lines(out, "NO NAV")) == 1
