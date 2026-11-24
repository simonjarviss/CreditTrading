"""Tests for the 2023-26 reference-quote driver (scripts/research/reopen_c5/fetch_2023_refs.py) and
the analysis's stride path.

WHY THESE. The driver is the one piece of the C5 re-open that touches a broker host, and the team lead
runs it unseen. So each property the note promises is pinned on a FAKE client: the stride's dates, the
early close moving the close-side quotes, resuming without refetching, the cache shape the analysis
reads, the refusal without QUANTT_ENV_FILE, and the GET-only wrapper. No test sets QUANTT_ENV_FILE,
loads a key file or opens a socket (the root conftest blocks the network anyway). The figures are
synthetic, so they are statements about the code, never about the market.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from quantt.broker.alpaca import DATA_BASE
from scripts.cef import exec_capacity_open_cross as X
from scripts.research.reopen_c5 import fetch_2023_refs as F
from scripts.research.reopen_c5 import reopen_c5_open_cost as M

SYMS = ["AWF", "BIT"]


class FakeData:
    """Answers GET /v2/stocks/quotes with one valid quote per requested symbol, 1s before `end`."""

    def __init__(self):
        self.calls = []

    def _get(self, base, path, params=None):
        self.calls.append(dict(base=base, path=path, **(params or {})))
        end = pd.Timestamp(params["end"])
        t = (end - pd.Timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        syms = params["symbols"].split(",")
        return {"quotes": {s: [dict(t=t, bp=9.99, ap=10.01)] for s in syms}, "next_page_token": None}


class FakeWithOrder(FakeData):
    def submit_order(self, *a, **k):            # what a real AlpacaClient has
        raise AssertionError("never called")


def _calendar(n=30, early_index=14):
    d = pd.bdate_range("2023-01-03", periods=n).strftime("%Y-%m-%d")
    close = ["16:00"] * n
    close[early_index] = "13:00"
    return pd.DataFrame(dict(date=d, open="09:30", close=close))


@pytest.fixture
def short_window(monkeypatch):
    monkeypatch.setattr(F, "STRIDE_LAST", "2023-02-13")
    monkeypatch.setattr(M, "STRIDE_LAST", "2023-02-13")
    monkeypatch.setattr(X, "REQ_SLEEP_S", 0.0)


# ---------------------------------------------------------------- stride dates

def test_stride_dates_start_at_first_and_step():
    cal = [f"2023-01-{d:02d}" for d in range(3, 32)]
    assert M.stride_dates(cal, "2023-01-03", "2023-01-31", 14) == ["2023-01-03", "2023-01-17", "2023-01-31"]
    assert M.stride_dates(cal, "2023-01-03", "2023-01-30", 14) == ["2023-01-03", "2023-01-17"]
    with pytest.raises(M.ReopenError):
        M.stride_dates(cal, "2023-01-03", "2023-02-28", 14)       # calendar too short
    with pytest.raises(M.ReopenError):
        M.stride_dates([d for d in cal if d != "2023-01-03"], "2023-01-03", "2023-01-31", 14)


def test_sessions_carry_the_calendars_early_close(short_window):
    s = F.sessions(_calendar())
    assert [d for d, _ in s] == ["2023-01-03", "2023-01-23", "2023-02-10"]
    assert dict(s)["2023-01-23"] == "13:00" and dict(s)["2023-01-03"] == "16:00"
    # the real stride: 64 sessions on the cached-calendar shape is checked in the dry run, not here


# ---------------------------------------------------------------- GET-only

def test_quotes_only_forwards_quotes_and_nothing_else():
    q = F.QuotesOnly(FakeWithOrder(), DATA_BASE)
    F.assert_get_only(q)                        # the wrapper exposes no order method ...
    with pytest.raises(F.ReopenError):
        F.assert_get_only(FakeWithOrder())      # ... although the wrapped client does
    with pytest.raises(F.ReopenError):
        q._get(DATA_BASE, "/v2/stocks/trades", {})
    with pytest.raises(F.ReopenError):
        q._get("https://paper-api.alpaca.markets", "/v2/stocks/quotes", {})
    q._get(DATA_BASE, "/v2/stocks/quotes", dict(symbols="AWF", end="2023-01-03T14:31:00Z"))
    assert q.requests == 1


def test_refuses_without_quantt_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("QUANTT_ENV_FILE", raising=False)
    from quantt.broker.alpaca import AlpacaClient

    def boom(*a, **k):
        raise AssertionError("the client must not be constructed")
    monkeypatch.setattr(AlpacaClient, "from_environment", classmethod(boom))
    with pytest.raises(F.ReopenError, match="QUANTT_ENV_FILE is not set"):
        F.make_client()
    _calendar().to_parquet(tmp_path / "calendar.parquet", index=False)
    with pytest.raises(F.ReopenError, match="QUANTT_ENV_FILE is not set"):
        F.main(["--cache", str(tmp_path / "c"), "--calendar", str(tmp_path / "calendar.parquet"),
                "--holdout-prints", str(tmp_path)])
    assert not (tmp_path / "c").exists()


def test_dry_run_needs_no_client_and_writes_nothing(monkeypatch, tmp_path, capsys, short_window):
    monkeypatch.delenv("QUANTT_ENV_FILE", raising=False)
    monkeypatch.setattr(F, "make_client", lambda: (_ for _ in ()).throw(AssertionError("no client")))
    _calendar().to_parquet(tmp_path / "calendar.parquet", index=False)
    assert F.main(["--cache", str(tmp_path / "c"), "--calendar", str(tmp_path / "calendar.parquet"),
                   "--holdout-prints", str(tmp_path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "3 sessions" in out and "at least 18 GET" in out and "('2023-01-23', '13:00')" in out
    assert not (tmp_path / "c").exists()


# ---------------------------------------------------------------- fetch, resume, cache shape

def test_fetch_writes_six_refs_and_moves_the_close_side_on_an_early_close(tmp_path, short_window):
    fake = FakeData()
    c = F.QuotesOnly(fake, DATA_BASE)
    log = F.fetch_all(c, tmp_path, F.sessions(_calendar()), SYMS)
    assert log == dict(skipped=0, completed=0, new=3)
    assert c.requests == 3 * 6 == len(fake.calls)
    rec = json.loads((tmp_path / "days" / "2023-01-23.json").read_text())
    assert rec["era"] == M.STRIDE_ERA and rec["close"] == "13:00" and rec["date"] == "2023-01-23"
    assert sorted(k for k in rec if k.startswith("q_")) == F.ref_keys()
    assert set(rec["q_close_m1"]) == set(SYMS) and rec["q_close_m1"]["AWF"]["mid"] == pytest.approx(10.0)
    ends = sorted(x["end"] for x in fake.calls if x["start"].startswith("2023-01-23T1") and
                  x["end"] >= "2023-01-23T17")
    # 13:00 ET in January is 18:00Z: the close-side references are 12:55, 12:59 and 13:00 ET
    assert ends == ["2023-01-23T17:55:00.000000Z", "2023-01-23T17:59:00.000000Z", "2023-01-23T18:00:00.000000Z"]
    assert not any(x["end"].startswith("2023-01-23T21") for x in fake.calls)   # never a 16:00 close that day


def test_resume_skips_cached_sessions_and_refetches_nothing(tmp_path, short_window):
    sess = F.sessions(_calendar())
    F.fetch_all(F.QuotesOnly(FakeData(), DATA_BASE), tmp_path, sess, SYMS)
    before = {p.name: p.read_bytes() for p in (tmp_path / "days").iterdir()}
    c2 = F.QuotesOnly(FakeData(), DATA_BASE)
    assert F.fetch_all(c2, tmp_path, sess, SYMS) == dict(skipped=3, completed=0, new=0)
    assert c2.requests == 0
    assert {p.name: p.read_bytes() for p in (tmp_path / "days").iterdir()} == before
    # a session missing one key is completed with exactly that one request
    f = tmp_path / "days" / "2023-02-10.json"
    rec = json.loads(f.read_text())
    kept = rec.pop("q_postopen")
    f.write_text(json.dumps(rec))
    c3 = F.QuotesOnly(FakeData(), DATA_BASE)
    assert F.fetch_all(c3, tmp_path, sess, SYMS) == dict(skipped=2, completed=1, new=0)
    assert c3.requests == 1
    assert json.loads(f.read_text())["q_close_m1"] == rec["q_close_m1"]          # untouched
    assert set(json.loads(f.read_text())["q_postopen"]) == set(kept)
    # a file cached under another era or close is refused, not overwritten
    rec["era"] = "recent"
    f.write_text(json.dumps(rec))
    with pytest.raises(M.ReopenError):
        F.fetch_all(F.QuotesOnly(FakeData(), DATA_BASE), tmp_path, sess, SYMS)


def _prints(tmp_path, dates):
    """Synthetic holdout print files in the freeze's shape, and a record holding their hashes."""
    rows_o, rows_c = [], []
    for d in dates:
        for s in SYMS:
            rows_o.append(dict(date=pd.Timestamp(d), ticker=s, exchange="N", condition="O", price=10.02,
                               t=f"{d}T14:30:01Z", fetched_at_utc="x"))
            rows_o.append(dict(date=pd.Timestamp(d), ticker=s, exchange="N", condition="Q", price=10.02,
                               t=f"{d}T14:30:01Z", fetched_at_utc="x"))
            rows_c.append(dict(date=pd.Timestamp(d), ticker=s, exchange="N", condition="6", price=10.01,
                               t=f"{d}T21:00:02Z", fetched_at_utc="x"))
    (tmp_path / "w4").mkdir()
    rec = {"files": {}}
    for rel, rows in ((F.PRINT_FILES["open"], rows_o), (F.PRINT_FILES["close"], rows_c)):
        pd.DataFrame(rows).to_parquet(tmp_path / rel, index=False)
        rec["files"][rel] = hashlib.sha256((tmp_path / rel).read_bytes()).hexdigest()
    (tmp_path / "rec.json").write_text(json.dumps(rec))
    return tmp_path / "rec.json"


def test_cache_shape_is_what_the_analysis_reads(tmp_path, monkeypatch, short_window):
    cal = _calendar()
    sess = F.sessions(cal)
    cache = tmp_path / "cache"
    F.fetch_all(F.QuotesOnly(FakeData(), DATA_BASE), cache, sess, SYMS)
    src = tmp_path / "src"
    src.mkdir()
    monkeypatch.setattr(F, "HOLDOUT_RECORD", _prints(src, [d for d, _ in sess]))
    A = F.holdout_prints(src, [d for d, _ in sess])
    cal.to_parquet(cache / "calendar.parquet", index=False)
    A.to_parquet(cache / "auctions_stride.parquet", index=False)
    need = sorted({X.HORIZONS[h][s] for h in M.HORIZONS for s in ("open", "close")})
    days, A2, manifest = M.load_stride(cache, X.FIT_SAMPLE_EVERY, need)
    assert sorted(days) == [d for d, _ in sess] and len(manifest) == 3 + 2
    for h in M.HORIZONS:
        d, skipped = M.independent_round_pairs(days, A2, X.HORIZONS[h]["open"], X.HORIZONS[h]["close"])
        assert len(d) == 3 * 2 and np.allclose(d.values, 20.0 - 10.0)     # 10.02 and 10.01 vs a 10.00 mid
        assert skipped == {"no_open_print": 0, "no_close_print": 0, "no_open_quote": 0, "no_close_quote": 0}
    # a missing session or a tampered print file raises
    (cache / "days" / "2023-02-10.json").unlink()
    with pytest.raises(M.ReopenError, match="not cached"):
        M.load_stride(cache, X.FIT_SAMPLE_EVERY, need)
    (src / F.PRINT_FILES["open"]).write_bytes(b"tampered")
    with pytest.raises(F.ReopenError, match="SHA-256"):
        F.holdout_prints(src, [d for d, _ in sess])


def test_analysis_refuses_to_overwrite_the_recent_record(tmp_path):
    for d in ("r", "f", "s"):
        (tmp_path / d).mkdir()
    with pytest.raises(M.ReopenError, match="--stamp"):
        M.main(["--recent-cache", str(tmp_path / "r"), "--frozen", str(tmp_path / "f"),
                "--stride-cache", str(tmp_path / "s")])


def test_by_name_table():
    idx = pd.MultiIndex.from_tuples([(f"2023-01-{d:02d}", t) for d in range(3, 9) for t in ("AWF", "BIT")],
                                    names=["date", "ticker"])
    s = pd.Series(np.arange(12, dtype=float) + 1.0, index=idx)
    T = M.by_name({"h1": s, "h5": s * 2})
    assert list(T.index) == ["AWF", "BIT"]
    assert T.loc["AWF", "h1_mean"] == pytest.approx(np.mean([1, 3, 5, 7, 9, 11]))
    assert T.loc["BIT", "h5_n"] == 6
