"""scripts/cef/data_books.py: C4's frozen funds, its NAV-symbol map and its seed builder (plan step 3).

What these pin:
  * The tracked frozen file and the committed map are what the book fetches:
    74 funds, 15 with a NAV symbol other than X<TK>X, EVT on XEVTX.
  * Every loader refuses a file that is not exactly the book (a count, a
    duplicate, a missing fund, a price ticker given as a NAV, a shared symbol).
  * The map is DERIVED by the families build's own rule and checked against
    the symbol that build used; a disagreement, or a fund it gave no NAV, raises.
  * The seed builder (documented, never run here on real data) keeps the 74,
    refuses every defect it checks for, refuses an unruled split-like spike,
    applies a recorded ruling to the close only and lists it, and never writes
    inside data/ or over an existing seed.

Synthetic inputs in tmp_path except the two tracked files, which are read
as committed. No data/ file is read or written; netguard refuses any socket.
"""
import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.cef import data_books as db
from scripts.cef.data_guards import SpikeRevertError

REPO = Path(__file__).resolve().parents[3]


def test_the_tracked_frozen_file_and_committed_map_are_the_book():
    fam = db.c4_universe()
    syms = db.c4_nav_symbols()
    assert len(fam) == 74 == len(syms) and set(fam) == set(syms)
    other = sorted(t for t, s in syms.items() if s != f"X{t}X")
    assert other == ["ADX", "BCX", "BMEZ", "BSTZ", "BTX", "GRX", "HGLB", "NBXG", "NMAI", "NPFD",
                     "QQQX", "RLTY", "SPXX", "TBLD", "TY"]
    rows = list(csv.DictReader(open(db.C4_NAV_MAP)))
    by = {r["ticker"]: r for r in rows}
    assert by["EVT"]["nav_symbol"] == "XEVTX" and by["EVT"]["source"] == "x_tk_x"
    assert by["EVT"]["nav_ticker_cefconnect"] == ""          # CEFConnect names none for EVT
    assert sum(r["source"] == "cefconnect_nav_ticker" for r in rows) == 73
    assert all(r["nav_symbol"] == r["families_nav_symbol"] for r in rows)


def write_csv(path, rows, cols=None):
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)
    return path


FUNDS = {"ADX": "equity_domestic", "EVT": "multi_asset", "IGR": "equity_sector"}


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "C4_N", 3)
    return write_csv(tmp_path / "frozen.csv", [{"ticker": t, "family": f} for t, f in FUNDS.items()])


def test_the_frozen_file_must_hold_exactly_the_book(tmp_path, frozen):
    assert db.c4_universe(frozen) == FUNDS
    with pytest.raises(db.DataBookError, match="holds 2 funds"):
        db.c4_universe(write_csv(tmp_path / "short.csv", [{"ticker": "ADX", "family": "x"},
                                                          {"ticker": "EVT", "family": "y"}]))
    with pytest.raises(db.DataBookError, match="listed twice"):
        db.c4_universe(write_csv(tmp_path / "dup.csv", [{"ticker": "ADX", "family": "x"}] * 3))
    with pytest.raises(db.DataBookError, match="does not exist"):
        db.c4_universe(tmp_path / "absent.csv")


def nav_map(tmp_path, syms, name="map.csv"):
    return write_csv(tmp_path / name, [{"ticker": t, "nav_symbol": s, "source": "", "nav_ticker_cefconnect": "",
                                        "families_nav_symbol": s, "families_nav_status": ""}
                                       for t, s in syms.items()], list(db.NAV_MAP_COLUMNS))


@pytest.mark.parametrize("syms, why", [
    ({"ADX": "XADEX", "EVT": "XEVTX"}, "does not cover"),
    ({"ADX": "XADEX", "EVT": "XEVTX", "IGR": "IGR"}, "is the price ticker"),
    ({"ADX": "XADEX", "EVT": "XADEX", "IGR": "XIGRX"}, "more than one fund"),
    ({"ADX": "XADEX", "EVT": "XEVTX", "IGR": "XIGRX", "PDI": "XPDIX"}, "does not cover"),
])
def test_the_nav_map_refuses_a_map_that_is_not_the_book(tmp_path, frozen, syms, why):
    with pytest.raises(db.DataBookError, match=why):
        db.c4_nav_symbols(nav_map(tmp_path, syms), db.c4_universe(frozen))


def test_the_nav_map_refuses_other_columns(tmp_path, frozen):
    bad = write_csv(tmp_path / "bad.csv", [{"ticker": t, "nav_symbol": f"X{t}X"} for t in FUNDS])
    with pytest.raises(db.DataBookError, match="columns"):
        db.c4_nav_symbols(bad, db.c4_universe(frozen))


def families_inputs(tmp_path, cc, used):
    uni = write_csv(tmp_path / "universe.csv", [{"ticker": t, "nav_ticker_cefconnect": cc.get(t)}
                                                for t in FUNDS])
    log = write_csv(tmp_path / "yf_fetch_log.csv", [{"ticker": t, "nav_symbol": used.get(t),
                                                     "nav_status": "one candidate returned rows"}
                                                    for t in FUNDS])
    return uni, log


def test_the_map_is_derived_by_the_families_rule_and_checked_against_what_it_used(tmp_path, frozen):
    uni, log = families_inputs(tmp_path, {"ADX": "XADEX", "IGR": "XIGRX"},
                               {"ADX": "XADEX", "EVT": "XEVTX", "IGR": "XIGRX"})
    rows = db.build_c4_nav_map(uni, log, frozen)
    assert [(r["ticker"], r["nav_symbol"], r["source"]) for r in rows] == [
        ("ADX", "XADEX", "cefconnect_nav_ticker"), ("EVT", "XEVTX", "x_tk_x"),
        ("IGR", "XIGRX", "cefconnect_nav_ticker")]
    assert db._map_text(rows).splitlines()[0] == ",".join(db.NAV_MAP_COLUMNS)


@pytest.mark.parametrize("used, why", [
    ({"ADX": "XADXX", "EVT": "XEVTX", "IGR": "XIGRX"}, "the families panel used XADXX"),
    ({"ADX": "XADEX", "EVT": None, "IGR": "XIGRX"}, "has no NAV"),
])
def test_the_map_refuses_a_fund_the_families_build_read_differently_or_not_at_all(
        tmp_path, frozen, used, why):
    uni, log = families_inputs(tmp_path, {"ADX": "XADEX", "IGR": "XIGRX"}, used)
    with pytest.raises(db.DataBookError, match=why):
        db.build_c4_nav_map(uni, log, frozen)


# --------------------------------------------------------------------------- the seed (never run on real data here)

def families_panels(src: Path, *, spike=False, extra=True):
    """Families-schema panels for the three funds (and a fund outside C4)."""
    src.mkdir(parents=True)
    days = pd.bdate_range("2026-07-20", periods=8)
    rows, navs = [], []
    for t, f in list(FUNDS.items()) + ([("ZZZ", "preferred")] if extra else []):
        for i, d in enumerate(days):
            c = 14.13 if (spike and t == "IGR" and i == 3) else 4.71
            rows.append({"date": d, "open": c, "high": c, "low": c, "close": c, "volume": 1000,
                         "ticker": t, "grp": f})
            navs.append({"date": d, "nav": 5.0, "ticker": t})
    P = pd.DataFrame(rows)[db.PX_COLUMNS]
    P["volume"] = P["volume"].astype("int64")
    P.to_parquet(src / "cef_prices.parquet", index=False)
    pd.DataFrame(navs)[db.NAV_COLUMNS].to_parquet(src / "cef_nav.parquet", index=False)
    return days


@pytest.fixture
def seed(tmp_path, frozen):
    core = write_csv(tmp_path / "cef_universe.csv", [{"ticker": "PDI", "grp": "taxable"}])

    def go(src, out, **kw):
        return db.seed_c4(src, out, universe=frozen, core_universe=core, **kw)
    return go


def test_the_seed_keeps_the_book_and_records_what_it_wrote(tmp_path, seed):
    families_panels(tmp_path / "fam")
    man = seed(tmp_path / "fam", tmp_path / "seed")
    P = pd.read_parquet(tmp_path / "seed" / "cef_prices.parquet")
    N = pd.read_parquet(tmp_path / "seed" / "cef_nav.parquet")
    assert sorted(P["ticker"].unique()) == sorted(FUNDS) == sorted(N["ticker"].unique())
    assert list(P.columns) == db.PX_COLUMNS and list(N.columns) == db.NAV_COLUMNS
    assert man["files"]["cef_prices.parquet"]["rows"] == 24 and man["treated_closes"] == []
    assert json.loads((tmp_path / "seed" / db.SEED_MANIFEST).read_text()) == man
    with pytest.raises(db.DataBookError, match="never written over"):
        seed(tmp_path / "fam", tmp_path / "seed")


def test_the_seed_never_writes_inside_data(tmp_path, seed):
    families_panels(tmp_path / "fam")
    with pytest.raises(db.DataBookError, match="inside"):
        seed(tmp_path / "fam", REPO / "data" / "cef_c4")


@pytest.mark.parametrize("defect, why", [
    ("a core name", "core names"),
    ("a fund missing", "no price rows"),
    ("another family", "frozen family"),
    ("an empty close", "no close"),
    ("a duplicate row", "duplicate"),
])
def test_the_seed_refuses_each_defect(tmp_path, seed, frozen, defect, why):
    families_panels(tmp_path / "fam", extra=False)
    src = tmp_path / "fam"
    P = pd.read_parquet(src / "cef_prices.parquet")
    if defect == "a core name":
        write_csv(tmp_path / "cef_universe.csv", [{"ticker": "IGR", "grp": "x"}])
    elif defect == "a fund missing":
        P = P[P["ticker"] != "EVT"]
    elif defect == "another family":
        P.loc[P["ticker"] == "ADX", "grp"] = "muni"
    elif defect == "an empty close":
        P.loc[P.index[0], "close"] = float("nan")
    elif defect == "a duplicate row":
        P = pd.concat([P, P.iloc[:1]], ignore_index=True)
    P.to_parquet(src / "cef_prices.parquet", index=False)
    with pytest.raises(db.DataBookError, match=why):
        seed(src, tmp_path / "seed")
    assert not (tmp_path / "seed").exists()


def test_the_seed_refuses_an_unruled_spike_and_applies_a_recorded_ruling_to_the_close(tmp_path, seed):
    days = families_panels(tmp_path / "fam", spike=True)
    with pytest.raises(SpikeRevertError, match="IGR"):
        seed(tmp_path / "fam", tmp_path / "seed")
    assert not (tmp_path / "seed").exists()
    rulings = tmp_path / "rulings.json"
    rulings.write_text(json.dumps({"ruled_by": "fixture", "ruled_on": "2026-10-29", "record": "this test",
                                   "bars": [{"ticker": "IGR", "date": str(days[3].date()),
                                             "run_end": str(days[3].date()), "factor": 3,
                                             "treatment": "rebase", "reason": "fixture"}]}))
    man = seed(tmp_path / "fam", tmp_path / "seed", rulings=rulings)
    P = pd.read_parquet(tmp_path / "seed" / "cef_prices.parquet")
    bar = P[(P["ticker"] == "IGR") & (P["date"] == days[3])].iloc[0]
    assert bar["close"] == pytest.approx(4.71) and bar["open"] == 14.13      # close only
    assert man["treated_closes"] == [{"ticker": "IGR", "date": str(days[3].date()),
                                      "treatment": "rebase", "factor": 3.0}]
