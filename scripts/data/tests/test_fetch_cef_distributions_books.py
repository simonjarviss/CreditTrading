"""`--data-book` of scripts/fetch_cef_distributions.py (C4 deployment plan step 3, DARK, 2026-10-29).

THE CORE IS UNCHANGED: the bare run (the collector's) and `--out/--tickers`, run
by cee16ad's file (from git, `scripts/cef/tests/noop_base.py`), by this one, and
by this one with `--data-book cef`, write the same bytes to the same files and
print the same lines, on one fake yfinance with the clock frozen.

C4 HAS ITS OWN PANEL: `--data-book c4` fetches exactly the frozen funds, never
reads `cef_universe.csv`, writes only the actions panels, only into
data/cef_c4/, and refuses an unseeded directory before fetching anything. Each
of these fails on cee16ad, which has no `--data-book`.

Synthetic actions: the claim is about this code. Hermetic: tmp_path only (the
root conftest refuses a write under data/), and netguard refuses any socket.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path

import pandas as pd
import pytest

from scripts.cef import data_books as db
from scripts.cef.tests.noop_base import load_at_base

REPO = Path(__file__).resolve().parents[3]
IDX = pd.DatetimeIndex(["2024-01-12", "2024-02-13", "2024-03-12", "2025-08-19"]).tz_localize("America/New_York")


class FakeYF:
    """Actions for any ticker: AAA has a split, CCC has no actions (the
    `.dividends` branch), every other name two dividends."""

    def __init__(self):
        self.asked = []

    def Ticker(self, tk):
        self.asked.append(tk)

        class T:
            actions = (pd.DataFrame({"Dividends": [0.10, 0.10, 0.11, 0.0],
                                     "Stock Splits": [0.0, 0.0, 0.0, 0.3333]}, index=IDX) if tk == "AAA"
                       else pd.DataFrame(columns=["Dividends", "Stock Splits"]) if tk == "CCC"
                       else pd.DataFrame({"Dividends": [0.05, 0.06, 0.0, 0.07],
                                          "Stock Splits": [0.0] * 4}, index=IDX))
            dividends = (pd.Series([0.2, 0.21], index=IDX[:2], name="Dividends") if tk == "CCC"
                         else pd.Series(dtype=float))
            info = {"symbol": tk, "quoteType": "MUTUALFUND", "longName": f"{tk} Fund\nInc",
                    "longBusinessSummary": "uses leverage " * 50, "yield": 0.08}
        return T()


def tree(root: Path) -> Path:
    cef = root / "data" / "cef"
    cef.mkdir(parents=True)
    pd.DataFrame({"ticker": ["AAA", "BBB", "CCC"], "grp": ["taxable", "taxable", "muni"]}
                 ).to_csv(cef / "cef_universe.csv", index=False)
    d = pd.bdate_range("2024-01-02", "2025-09-01")
    pd.concat([pd.DataFrame({"date": d, "ticker": t, "close": 10.0 + i})
               for i, t in enumerate(["AAA", "BBB", "CCC"])]).to_parquet(cef / "cef_prices.parquet",
                                                                       index=False)
    return cef


def point(m, monkeypatch, root: Path):
    cef = tree(root)
    monkeypatch.setattr(m, "ROOT", str(root))
    monkeypatch.setattr(m, "CEF", str(cef))
    yf = FakeYF()
    monkeypatch.setattr(m, "yf", yf)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    monkeypatch.setattr(pd.Timestamp, "utcnow",
                        staticmethod(lambda: pd.Timestamp("2026-10-29 12:00:00", tz="UTC")))
    return cef, yf


def run(m, argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = m.main(list(argv))
    return rc, buf.getvalue()


def files(d: Path) -> dict:
    return {p.name: p.read_bytes() for p in sorted(d.iterdir())} if d.exists() else {}


@pytest.fixture
def new(tmp_path):
    spec = importlib.util.spec_from_file_location("fetch_cef_distributions_books",
                                                  REPO / "scripts" / "fetch_cef_distributions.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize("argv", [[], ["--out", "{root}/copy", "--tickers", "AAA,CCC"]],
                         ids=["bare run (the collector's)", "--out with --tickers"])
def test_the_core_is_byte_identical_to_cee16ad(argv, new, tmp_path, monkeypatch):
    base = load_at_base("scripts/fetch_cef_distributions.py", "fetch_cef_distributions_cee16ad",
                        tmp_path, monkeypatch)
    got = []
    for label, m, extra in (("run_base", base, []), ("run_new", new, []),
                            ("run_new_cef", new, ["--data-book", "cef"])):
        root = tmp_path / label
        cef, yf = point(m, monkeypatch, root)
        rc, out = run(m, [a.format(root=root) for a in argv] + extra)
        got.append((rc, out.replace(str(root), "<ROOT>"), files(cef), files(root / "copy"), yf.asked))
    b, n, c = got
    for i, what in enumerate(("exit", "stdout", "data/cef files", "--out files", "yfinance requests")):
        assert n[i] == b[i], f"{what} differs from cee16ad with no --data-book"
        assert c[i] == b[i], f"{what} differs from cee16ad with --data-book cef"
    assert b[0] == 0 and "cef_distributions.parquet" in (b[2] if not argv else b[3])


C4_FUNDS = {"ADX": "equity_domestic", "EVT": "multi_asset", "IGR": "equity_sector"}


@pytest.fixture
def c4(new, tmp_path, monkeypatch):
    uni = tmp_path / "frozen.csv"
    pd.DataFrame({"ticker": list(C4_FUNDS), "family": list(C4_FUNDS.values())}).to_csv(uni, index=False)
    monkeypatch.setattr(db, "C4_UNIVERSE", uni)
    monkeypatch.setattr(db, "C4_N", len(C4_FUNDS))
    monkeypatch.setattr(db, "C4_DIR", tmp_path / "data" / "cef_c4")
    cef, yf = point(new, monkeypatch, tmp_path)
    return new, cef, yf, tmp_path / "data" / "cef_c4"


def test_c4_writes_its_actions_panel_for_exactly_the_frozen_funds_and_nothing_else(c4):
    m, cef, yf, c4dir = c4
    c4dir.mkdir()
    before = files(cef)
    rc, out = run(m, ["--data-book", "c4"])
    assert rc == 0, out
    assert files(cef) == before, "a C4 run touched data/cef"
    assert sorted(yf.asked) == sorted(C4_FUNDS), "a name outside the frozen funds was fetched"
    assert sorted(files(c4dir)) == ["cef_distributions.parquet"]
    dist = pd.read_parquet(c4dir / "cef_distributions.parquet")
    assert dict(dist.drop_duplicates("ticker")[["ticker", "grp"]].values) == C4_FUNDS
    assert "universe: 3 tickers" in out and "--data-book c4: actions panels only" in out


def test_c4_refuses_an_unseeded_directory_before_fetching(c4):
    m, cef, yf, c4dir = c4
    with pytest.raises(SystemExit, match="seed it first"):
        run(m, ["--data-book", "c4"])
    assert yf.asked == [] and not c4dir.exists()


def test_c4_tickers_are_checked_against_the_frozen_file_not_cef_universe(c4, tmp_path):
    m, cef, yf, c4dir = c4
    with pytest.raises(SystemExit, match="frozen.csv"):
        run(m, ["--data-book", "c4", "--out", str(tmp_path / "copy"), "--tickers", "AAA"])
    with pytest.raises(SystemExit, match="requires --out"):
        run(m, ["--data-book", "c4", "--tickers", "ADX"])
    assert run(m, ["--data-book", "c4", "--out", str(tmp_path / "copy"), "--tickers", "ADX"])[0] == 0
    assert set(pd.read_parquet(tmp_path / "copy" / "cef_distributions.parquet")["ticker"]) == {"ADX"}
    assert not c4dir.exists()
