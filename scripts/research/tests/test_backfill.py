"""The backfill helper's guards: a re-run that does not reproduce is refused, nothing
from the 2023 holdout can be stored, a cut panel holds no later row, a staged cache is
never silently replaced, and the census covers each counter id by id.

Synthetic inputs only; nothing here reads data/ or a trial's cache, and the counter
table is never read (H14): coverage is tested against the census's own length.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.research.backfill import backfill as B  # noqa: E402
from scripts.research.backfill import census as C  # noqa: E402


# ---------------------------------------------------------------- compare

def test_compare_accepts_identical_and_counts_leaves():
    want = {"stage1": {"sharpe": 0.414, "nw_t21": 1.62, "pass_": False, "ci": [0.1, 0.9]}, "T": 3693, "v": "KILL D1"}
    got = {"stage1": {"sharpe": np.float64(0.414), "nw_t21": 1.62, "pass_": np.bool_(False), "ci": (0.1, 0.9)},
           "T": np.int64(3693), "v": "KILL D1", "extra": 1.0}
    r = B.compare(got, want, "x")
    assert r["compared"] == 7 and r["max_abs_diff"] == 0.0


@pytest.mark.parametrize("got, match", [
    ({"a": 1.0 + 2e-9, "b": True, "c": "s"}, "1 of 3"),        # beyond 1e-9
    ({"a": 1.0, "b": False, "c": "s"}, "1 of 3"),              # a flipped verdict flag
    ({"a": 1.0, "b": True, "c": "t"}, "1 of 3"),               # a different verdict string
    ({"a": 1.0, "b": True}, "missing"),                        # a committed figure not recomputed
])
def test_compare_refuses_any_mismatch(got, match):
    with pytest.raises(B.NotReproduced, match=match):
        B.compare(got, {"a": 1.0, "b": True, "c": "s"}, "x")


def test_compare_treats_bool_as_not_a_number():
    with pytest.raises(B.NotReproduced):
        B.compare({"p": 1}, {"p": True}, "x")


def test_compare_nan_follows_the_trials_json_convention():
    assert B.compare({"x": float("nan")}, {"x": None}, "x")["compared"] == 1


def test_compare_refuses_an_empty_check():
    with pytest.raises(B.NotReproduced, match="nothing to compare"):
        B.compare({"a": 1}, {}, "x")


def test_same_series():
    s = pd.Series([0.1, -0.2, 0.3], index=pd.bdate_range("2020-01-01", periods=3))
    B.same_series(s, s.copy(), "x")
    with pytest.raises(B.NotReproduced):
        B.same_series(s, s * (1 + 1e-15), "x")
    with pytest.raises(B.NotReproduced):
        B.same_series(s, s.iloc[:2], "x")


# ---------------------------------------------------------------- the holdout

def test_assert_fit_only_refuses_2023_and_nan():
    ok = pd.Series([0.01, -0.02], index=pd.to_datetime(["2022-12-29", "2022-12-30"]))
    B.assert_fit_only(ok, "x")
    with pytest.raises(AssertionError, match="holdout"):
        B.assert_fit_only(pd.Series([0.01, 0.02], index=pd.to_datetime(["2022-12-30", "2023-01-03"])), "x")
    with pytest.raises(ValueError, match="NaN"):
        B.assert_fit_only(pd.Series([0.01, np.nan], index=pd.to_datetime(["2022-12-29", "2022-12-30"])), "x")


def test_rebuilt_refuses_a_holdout_series():
    s = pd.Series([0.01, 0.02], index=pd.to_datetime(["2022-12-30", "2023-01-03"]))
    with pytest.raises(AssertionError):
        B._rebuilt("CEF", "CEF-1", "v", s, {}, {}, {}, "")


def test_cut_parquet_keeps_no_later_row(tmp_path):
    d = pd.DataFrame({"date": pd.to_datetime(["2022-12-29", "2022-12-30", "2023-01-03", "2026-10-09"]),
                      "x": [1.0, 2.0, 3.0, 4.0]})
    src, dst = tmp_path / "p.parquet", tmp_path / "cut" / "p.parquet"
    d.to_parquet(src)
    kept = B.cut_parquet(src, dst)
    out = pd.read_parquet(dst)
    assert kept == {"rows": 2, "last": "2022-12-30"} and out["date"].max() == pd.Timestamp("2022-12-30")
    late = tmp_path / "late.parquet"
    d.iloc[2:].to_parquet(late)
    with pytest.raises(ValueError, match="no row"):
        B.cut_parquet(late, tmp_path / "c2.parquet")
    assert B.cut_parquet(late, tmp_path / "c3.parquet", allow_empty=True)["rows"] == 0
    assert len(pd.read_parquet(tmp_path / "c3.parquet")) == 0


# ---------------------------------------------------------------- staging

def test_copy_verified_never_replaces_a_different_file(tmp_path):
    src, dst = tmp_path / "a.bin", tmp_path / "d" / "a.bin"
    src.write_bytes(b"one")
    assert B.copy_verified(src, dst) == "copied"
    assert B.copy_verified(src, dst) == "present"
    dst.write_bytes(b"two")
    with pytest.raises(FileExistsError, match="differs"):
        B.copy_verified(src, dst)
    with pytest.raises(FileNotFoundError):
        B.copy_verified(tmp_path / "missing.bin", tmp_path / "x.bin")


# ---------------------------------------------------------------- the census

@pytest.mark.parametrize("counter", ["EVENTS", "XASSET", "CEF"])
def test_census_rows_are_contiguous_and_complete(counter):
    rows = C.validate(counter, len(C.CENSUS[counter]))
    assert [r["id"] for r in rows] == [f"{counter}-{n}" for n in range(1, len(rows) + 1)]
    for r in rows:
        if r["status"] == C.REBUILD:
            assert r["rebuild"] in B.REBUILDERS, r["id"]


def test_census_refuses_a_count_it_does_not_cover():
    n = len(C.CENSUS["CEF"])
    with pytest.raises(ValueError, match="missing"):
        C.validate("CEF", n + 1)
    with pytest.raises(ValueError, match="extra"):
        C.validate("CEF", n - 1)


def test_every_rebuilder_has_a_census_row():
    named = {r["rebuild"] for rows in C.CENSUS.values() for r in rows if r["rebuild"]}
    assert named == set(B.REBUILDERS)


def test_not_rebuilt_rows_carry_reasons_and_the_holdout_reason_where_it_applies():
    for r in C.CENSUS["CEF"]:
        if r["status"] == C.NOT_REBUILT:
            assert r["reason"] and r["source"] and r["script"]
    # every pre-C4/C5 CEF trial's headline used 2023+ data
    assert all(C.R_HOLDOUT in r["reason"] for r in C.CENSUS["CEF"][:50])
