"""`--out` and `--tickers` of scripts/fetch_cef_distributions.py (added 2026-10-27, both default off).

The script is on the live path: the nightly collector runs it bare. These tests pin that a bare
run still writes the six live files into data/cef/, and that `--out` writes ONLY the actions
panels, ONLY to its directory, for ONLY the named tickers. They fail against the file as it
stood at 66ec3df, which had no `main`, ignored arguments and always wrote data/cef/. The
byte-for-byte proof that a bare run is unchanged is
`results/events/exdrift/noop_fetch_cef_distributions.py` (run 2026-10-27, PASS).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[3]


class FakeYF:
    def __init__(self):
        self.asked = []
        idx = pd.DatetimeIndex(["2024-01-12", "2024-02-13"]).tz_localize("America/New_York")
        self.acts = pd.DataFrame({"Dividends": [0.1, 0.11], "Stock Splits": [0.0, 0.0]}, index=idx)

    def Ticker(self, tk):
        self.asked.append(tk)
        y = self

        class T:
            actions = y.acts
            dividends = pd.Series(dtype=float)
            info = {"symbol": tk, "quoteType": "MUTUALFUND"}
        return T()


@pytest.fixture
def mod(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("fetch_cef_distributions_t", REPO / "scripts" / "fetch_cef_distributions.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)                       # importing runs nothing now (main() is guarded)
    cef = tmp_path / "data" / "cef"
    cef.mkdir(parents=True)
    pd.DataFrame({"ticker": ["AAA", "BBB", "CCC"], "grp": ["taxable", "taxable", "muni"]}).to_csv(cef / "cef_universe.csv", index=False)
    pd.DataFrame({"ticker": ["AAA"] * 3, "date": pd.bdate_range("2024-01-02", periods=3), "close": 10.0}
                 ).to_parquet(cef / "cef_prices.parquet", index=False)
    monkeypatch.setattr(m, "ROOT", str(tmp_path))
    monkeypatch.setattr(m, "CEF", str(cef))
    monkeypatch.setattr(m, "yf", FakeYF())
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    return m


def test_out_writes_only_the_actions_panels_for_the_named_tickers(mod, tmp_path):
    cef = Path(mod.CEF)
    before = {p.name: p.stat().st_mtime_ns for p in cef.iterdir()}
    out = tmp_path / "research_copy"
    assert mod.main(["--out", str(out), "--tickers", "AAA,BBB"]) == 0
    assert {p.name: p.stat().st_mtime_ns for p in cef.iterdir()} == before      # data/cef untouched
    assert sorted(p.name for p in out.iterdir()) == ["cef_distributions.parquet"]
    assert set(pd.read_parquet(out / "cef_distributions.parquet")["ticker"]) == {"AAA", "BBB"}
    assert sorted(mod.yf.asked) == ["AAA", "BBB"]                               # CCC never fetched


def test_bare_run_still_writes_the_live_files(mod):
    assert mod.main([]) == 0
    names = {p.name for p in Path(mod.CEF).iterdir()}
    assert {"cef_distributions.parquet", "cef_dist_features.parquet", "cef_facts.csv", "_raw_info.json",
            "_fetch_diagnostics.json"} <= names
    assert set(pd.read_parquet(Path(mod.CEF) / "cef_distributions.parquet")["ticker"]) == {"AAA", "BBB", "CCC"}


def test_tickers_without_out_is_refused(mod):
    with pytest.raises(SystemExit, match="requires --out"):
        mod.main(["--tickers", "AAA"])


def test_out_inside_data_is_refused(mod, tmp_path):
    with pytest.raises(SystemExit, match="inside"):
        mod.main(["--out", str(tmp_path / "data" / "x"), "--tickers", "AAA"])


def test_unknown_ticker_is_refused(mod, tmp_path):
    with pytest.raises(SystemExit, match="not in cef_universe"):
        mod.main(["--out", str(tmp_path / "o"), "--tickers", "AAA,ZZZ"])
