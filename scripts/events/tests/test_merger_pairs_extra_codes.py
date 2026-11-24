"""`merger_pairs.build_events(extra_codes=...)` and `_announcement_row(stock_codes=...)` (added 2026-10-21
for E1's amendment 4) change nothing by default. Synthetic CRSP-shaped frames; no network."""
import pandas as pd

from scripts.events import merger_pairs as mp


def _nm_dl():
    nm = pd.DataFrame({"permno": [1, 2, 3, 4], "ticker": ["AAA", "BBB", "CCC", "DDD"],
                       "comnam": ["A FUND", "B FUND", "C FUND", "D FUND"], "shrcd": [14, 14, 14, 14],
                       "siccd": [0] * 4, "namedt": pd.to_datetime(["2000-01-01"] * 4),
                       "nameendt": pd.to_datetime(["2013-11-15", "2024-12-31", "2014-03-01", "2024-12-31"])})
    dl = pd.DataFrame({"permno": [1, 3], "dlstdt": pd.to_datetime(["2013-11-15", "2014-03-01"]),
                       "dlstcd": [331, 231], "nwperm": [2, 4], "dlpdt": pd.to_datetime(["2013-11-18", "2014-03-03"]),
                       "dlret": [0.001, 0.002], "dlamt": [10.0, 11.0]})
    return nm, dl


def test_default_is_unchanged_and_extra_codes_admit_331():
    nm, dl = _nm_dl()
    x0 = mp.build_events(nm, dl, pd.Timestamp("2010-01-01"), pd.Timestamp("2024-12-31"))
    assert list(x0["ticker"]) == ["CCC"] and list(x0["kind"]) == ["stock"]
    x1 = mp.build_events(nm, dl, pd.Timestamp("2010-01-01"), pd.Timestamp("2024-12-31"), extra_codes=(331,))
    assert sorted(x1["ticker"]) == ["AAA", "CCC"] and set(x1["kind"]) == {"stock"}
    assert x0.equals(x1[x1["dlstcd"] == 231].reset_index(drop=True))


def test_announcement_row_prices_331_only_when_asked():
    nm, dl = _nm_dl()
    x = mp.build_events(nm, dl, pd.Timestamp("2010-01-01"), pd.Timestamp("2024-12-31"), extra_codes=(331,))
    e = x[x["dlstcd"] == 331].iloc[0]
    d = pd.bdate_range("2013-06-03", "2013-11-29")
    px = {1: pd.DataFrame({"prc": 10.0, "ret": 0.001, "vol": 1.0, "cfacpr": 1.0}, index=d[d <= "2013-11-15"]),
          2: pd.DataFrame({"prc": 10.0, "ret": 0.0, "vol": 1.0, "cfacpr": 1.0}, index=d)}
    sk = {}
    r0 = mp._announcement_row(e, pd.Timestamp("2013-07-01"), {}, px, sk)
    assert r0["skip"].startswith("not a stock-only merger") and "pair_A1_to_close" not in r0
    r1 = mp._announcement_row(e, pd.Timestamp("2013-07-01"), {}, px, {}, stock_codes=(231, 331))
    assert "pair_A1_to_close" in r1
