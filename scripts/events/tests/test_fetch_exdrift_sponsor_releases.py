"""Tests for scripts/events/fetch_exdrift_sponsor_releases.py: synthetic release texts only; no network."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from scripts.events import fetch_exdrift_sponsor_releases as f

PIMCO = ("NEW YORK, Jan. 02, 2024 (GLOBE NEWSWIRE) -- The Boards have declared a monthly distribution. The "
         "distributions are payable on February 1, 2024 to shareholders of record on January 12, 2024, with an "
         "ex-dividend date of January 11, 2024. Fund NYSE Symbol Amount PIMCO Corporate & Income Opportunity Fund "
         "( NYSE: PTY ) $0.118800 PIMCO High Income Fund ( NYSE: PHK ) $0.048000 Fund Distribution Information as of "
         "November 30, 2023: PTY 10.5%")
BLACKROCK = ("By: BlackRock Closed-End Funds via Business Wire September 10, 2026 at 17:23 PM EDT Municipal Funds: "
             "Distribution Month Ex- & Record Date Payable Date October October 15, 2026 November 2, 2026 November "
             "November 13, 2026 December 1, 2026 National Funds Ticker BlackRock MuniHoldings Fund MHD $0.059500 - "
             "Taxable Funds: Distribution Month Ex- & Record Date Payable Date October October 14, 2026 October 30, 2026 "
             "BlackRock Corporate High Yield Fund HYT $0.077900")
DSL = ("TAMPA, Fla., Feb. 1, 2026 /PRNewswire/ -- DoubleLine Income Solutions Fund (NYSE: DSL) declares the "
       "following distribution: Declaration Feb. 1, 2026 Ex-Dividend Feb. 18, 2026 Record Feb. 18, 2026 Payable "
       "Feb. 27, 2026")


def test_dates_in_every_written_form():
    got = [d for _, _, d in f.date_mentions("January 11, 2024; Jan. 2, 2024; Sept. 13, 2023; March. 18, 2026; "
                                             "Apr 1, 2026; 10/14/2025; 2/14/24; 2/30/2024")]
    assert got == [pd.Timestamp(x) for x in ("2024-01-11", "2024-01-02", "2023-09-13", "2026-03-18", "2026-04-01",
                                             "2025-10-14", "2024-02-14")]


def test_release_dates_from_datelines():
    assert f.release_date_of(PIMCO)[0] == pd.Timestamp("2024-01-02")
    assert f.release_date_of(BLACKROCK)[0] == pd.Timestamp("2026-09-10")
    assert f.release_date_of(DSL)[0] == pd.Timestamp("2026-02-01")
    assert f.release_date_of("Published Apr 1, 2026 6:09pm EDT NEW YORK --(BUSINESS WIRE)--")[0] == pd.Timestamp("2026-04-01")
    assert f.release_date_of("no date here")[0] is None


def test_association_takes_the_governing_run_only():
    c = f.confirmations(PIMCO, ["PTY", "PHK"], "PIMCO")
    assert ("PTY", pd.Timestamp("2024-01-11")) in c and ("PHK", pd.Timestamp("2024-01-11")) in c
    b = f.confirmations(BLACKROCK, ["MHD", "HYT"], "BlackRock")
    assert ("MHD", pd.Timestamp("2026-11-13")) in b and ("MHD", pd.Timestamp("2026-10-14")) not in b
    assert ("HYT", pd.Timestamp("2026-10-14")) in b and ("HYT", pd.Timestamp("2026-11-13")) not in b
    d = f.confirmations(DSL, ["DSL"], "DoubleLine")
    assert ("DSL", pd.Timestamp("2026-02-18")) in d


def _cache(tmp_path, docs: dict):
    cache = tmp_path / "c"
    cache.mkdir()
    man, rows = {}, []
    for i, (sponsor, url, text) in enumerate(docs):
        (cache / f"h{i}.bin").write_bytes(text.encode())
        man[url] = {"status": 200, "sha16": f"h{i}", "fetched_utc": "2026-10-28T00:00:00Z", "final_url": url}
        rows.append(dict(sponsor=sponsor, release_date="", url=url, host="test", found_by="test"))
    (cache / "manifest.json").write_text(json.dumps(man))
    src = tmp_path / "s.csv"
    pd.DataFrame(rows).to_csv(src, index=False)
    return src, cache


def test_build_marks_found_late_and_not_found_and_verify_re_finds_quotes(tmp_path):
    late = PIMCO.replace("Jan. 02, 2024", "Jan. 11, 2024")
    src, cache = _cache(tmp_path, [("PIMCO", "https://e.org/a", PIMCO), ("PIMCO", "https://e.org/b", late),
                                   ("DoubleLine", "https://e.org/c", DSL)])
    sessions = pd.bdate_range("2023-12-01", "2026-03-31")
    ev = pd.DataFrame({"ticker": ["PTY", "PCN", "DSL"],
                       "ex_date": pd.to_datetime(["2024-01-11", "2024-01-11", "2026-02-18"])})
    T = f.build(ev, sessions, src, cache)
    st = dict(zip(T.ticker, T.status))
    assert st == {"PTY": "declared_by_e_minus_1", "PCN": "not_found", "DSL": "declared_by_e_minus_1"}
    assert T.loc[T.ticker == "PTY", "declared"].iloc[0] == pd.Timestamp("2024-01-02")   # the earliest release
    assert int(T.loc[T.ticker == "PTY", "releases_confirming"].iloc[0]) == 2
    tp = tmp_path / "t.csv"
    T.to_csv(tp, index=False)
    assert len(f.verify(tp, cache)) == 3
    (cache / "h0.bin").write_bytes(b"tampered")
    (cache / "h1.bin").write_bytes(b"tampered")
    with pytest.raises(f.ReleaseError, match="not re-found"):
        f.verify(tp, cache)


def test_a_release_declared_after_e_minus_1_is_late(tmp_path):
    late = PIMCO.replace("Jan. 02, 2024", "Jan. 11, 2024")
    src, cache = _cache(tmp_path, [("PIMCO", "https://e.org/b", late)])
    T = f.build(pd.DataFrame({"ticker": ["PTY"], "ex_date": pd.to_datetime(["2024-01-11"])}),
                pd.bdate_range("2023-12-01", "2024-03-01"), src, cache)
    assert T.status.iloc[0] == "declared_late"


def test_fetch_records_a_404_redirect_and_never_caches_it(tmp_path):
    class R:
        def __init__(self, url, code, content=b"x"):
            self.url, self.status_code, self.content = url, code, content
    src = tmp_path / "s.csv"
    pd.DataFrame([dict(sponsor="PIMCO", release_date="", url="https://www.nasdaq.com/press-release/x-2026-01-02",
                       host="nasdaq", found_by="t")]).to_csv(src, index=False)
    cache = tmp_path / "c"
    man = f.fetch(src, cache, sleep=lambda s: None, get=lambda u: R("https://www.nasdaq.com/404", 200))
    m = man["https://www.nasdaq.com/press-release/x-2026-01-02"]
    assert m["status"] == 404 and "sha16" not in m


def test_the_url_and_the_text_must_agree_on_the_date(tmp_path):
    src, cache = _cache(tmp_path, [("PIMCO", "https://markets.financialcontent.com/x/article/gnwcq-2024-3-1-pimco", PIMCO)])
    with pytest.raises(f.ReleaseError, match="dates the release"):
        f.read_releases(src, cache)
