"""Shared plumbing for the `ssx_fund2` censuses (fund-structure and market-plumbing seat, 2026-10-19).

WHY THIS EXISTS
---------------
Five zero-trial censuses (A4 non-traded BDC listings, A5 adviser and sponsor
changes, A6 control-share provisions, A9 BDC index-tracker demand, A16
non-traded tender pressure) all start from the same object: the SEC's
quarterly `master.gz` full indexes, 2008Q1-2025Q4, already cached by the
`research-edgar` worktree. Parsing 72 quarters of ~400k lines each takes
minutes, so it is done ONCE here, through the repo's own validated parser
(`scripts/data/fetch_edgar_events.py::parse_master_index`) and the repo's
own fund rule (`fund_set`), and the filtered rows are written to the
gitignored cache `results/events/ssx/_cache_ssx_fund2/`. EDGAR index rows
are public data; nothing licensed goes there from this module.

It also holds the ONE constructor for a live EDGAR client in this seat:
`EdgarClient(limiter=RateLimiter(min_interval=1.5))`, with a hard budget
counter. Nine other agents share the SEC's per-IP limit on 2026-10-19 and a
lock-out would block the whole desk, so every live request in the seat goes
through `live_client()` and the budget (1,200 in total, brief) is enforced
across scripts by a counter file, not by good intentions.

NO SILENT FALLBACKS: a missing quarter raises (offline client), a budget
overrun raises, and nothing here guesses a CIK or a date.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events" / "ssx" / "ssx_fund2"
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_fund2"   # gitignored (results/**/_cache_*)
INDEX_ROWS = CACHE / "index_rows_2008_2025.parquet"
BUDGET_FILE = CACHE / "live_request_budget.json"
LIVE_BUDGET = 1200          # brief, 2026-10-19: at most 1,200 live EDGAR requests in total
FIRST_YEAR, LAST_YEAR = 2008, 2025   # closed quarters only; counts may run to 2025-12-31

# Forms kept from the index. Everything a census below reads, plus the fund
# rule's inputs (marker forms, N-CSR, Forms 3/4).
KEEP_FORMS = frozenset({
    # fund-rule inputs (fetch_edgar_events.MARKER_FORMS | NCSR | INSIDER are added at run time)
    "N-CSR", "N-CSRS", "3", "4",
    # A4: BDC listings
    "N-54A", "N-54C", "10-K", "10-Q", "10-12G", "10-12B", "8-A12B", "8-A12B/A", "8-A12G", "25-NSE",
    "424B1", "424B2", "424B3", "424B4", "424B5", "424B7", "497", "S-1", "N-2", "N-2/A", "N-2MEF",
    # A5: proxies and mergers
    "DEF 14A", "PRE 14A", "DEFA14A", "DEFR14A", "DEFC14A", "PREC14A", "DFAN14A", "DEFM14A",
    "N-14", "N-14 8C", "425",
    # A16: tenders and interval-fund notices
    "SC TO-I", "SC TO-I/A", "SC TO-C", "N-23C3A", "N-23C3A/A", "N-23C3B", "N-23C3C",
    # A6 / A5: current reports; A9: N-PORT
    "8-K", "NPORT-P", "N-8F", "SC 13D", "SC 13D/A",
})


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_index(rebuild: bool = False) -> pd.DataFrame:
    """Every kept index row 2008Q1-2025Q4, from the offline EDGAR cache, memoised to parquet.

    One row per (cik, accession, form): a filing indexed under several CIKs
    (a joint proxy, a 425 under acquirer and target) appears once per CIK,
    which is what the per-fund counts need. Per-filing counts must dedupe on
    accession; each caller says which it does.
    """
    if INDEX_ROWS.exists() and not rebuild:
        return pd.read_parquet(INDEX_ROWS)
    from scripts.data.edgar_client import EdgarClient
    from scripts.data import fetch_edgar_events as fe
    client = EdgarClient(offline=True)          # cache only: raises on a missing quarter
    keep = set(KEEP_FORMS) | fe.MARKER_FORMS | fe.NCSR_FORMS | fe.INSIDER_FORMS
    frames = []
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        for qn in (1, 2, 3, 4):
            text = client.get_text(fe.INDEX_URL.format(y=y, q=qn))
            frames.append(fe.parse_master_index(text, label=f"{y}Q{qn}", keep_forms=keep))
    idx = pd.concat(frames, ignore_index=True).drop_duplicates(["cik", "accession", "form"])
    CACHE.mkdir(parents=True, exist_ok=True)
    idx.to_parquet(INDEX_ROWS, index=False)
    (CACHE / "index_rows_meta.json").write_text(json.dumps(
        {"built_utc": now_utc(), "quarters": f"{FIRST_YEAR}Q1-{LAST_YEAR}Q4", "rows": len(idx),
         "cache_hits": client.n_cache_hits, "requests": client.n_requests}, indent=1) + "\n")
    return idx


def fund_rule(idx: pd.DataFrame) -> dict[int, str]:
    """The fetcher's own CEF/BDC rule, unchanged (marker form, else N-CSR + Form 3/4)."""
    from scripts.data import fetch_edgar_events as fe
    return fe.fund_set(idx)


def bdc_ciks(idx: pd.DataFrame) -> set[int]:
    """CIKs that filed an N-54A (the BDC election) 2008-2025.

    N-54A is filed only by a company electing BDC status under 1940 Act §54(a);
    a BDC that elected before 2008 and never re-filed is missed (stated in the
    note as a recall gap, measured against CRSP where possible)."""
    return set(idx.loc[idx["form"] == "N-54A", "cik"].astype(int))


class BudgetExceeded(RuntimeError):
    pass


def _budget_read() -> dict:
    if BUDGET_FILE.exists():
        return json.loads(BUDGET_FILE.read_text())
    return {"used": 0, "log": []}


def budget_used() -> int:
    return int(_budget_read()["used"])


def record_requests(n: int, what: str) -> None:
    b = _budget_read()
    b["used"] = int(b["used"]) + int(n)
    b["log"].append({"utc": now_utc(), "n": int(n), "what": what})
    if b["used"] > LIVE_BUDGET:
        BUDGET_FILE.write_text(json.dumps(b, indent=1) + "\n")
        raise BudgetExceeded(f"live EDGAR requests {b['used']} > budget {LIVE_BUDGET}")
    CACHE.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.write_text(json.dumps(b, indent=1) + "\n")


class BudgetedClient:
    """The repo's EdgarClient at 1.5 s spacing, refusing once the seat's budget would be passed.

    `get_text`/`get_json` check the remaining budget BEFORE each call (a cache
    hit costs nothing and is not counted) and record each real request after.
    """

    def __init__(self, what: str, max_new: int):
        from scripts.data.edgar_client import EdgarClient, RateLimiter
        self._c = EdgarClient(limiter=RateLimiter(min_interval=1.5))
        self.what, self.max_new, self._start = what, int(max_new), self._c.n_requests

    def _check(self):
        new = self._c.n_requests - self._start
        if new >= self.max_new:
            raise BudgetExceeded(f"{self.what}: this run's cap of {self.max_new} live requests reached")
        if budget_used() + 1 > LIVE_BUDGET:
            raise BudgetExceeded(f"seat budget {LIVE_BUDGET} reached")

    def _after(self, before: int):
        n = self._c.n_requests - before
        if n:
            record_requests(n, self.what)

    def get_text(self, url: str, max_age_s=None, encoding: str = "latin-1") -> str:
        self._check()
        before = self._c.n_requests
        try:
            return self._c.get_text(url, max_age_s=max_age_s, encoding=encoding)
        finally:
            self._after(before)

    def get_json(self, url: str, max_age_s=None):
        self._check()
        before = self._c.n_requests
        try:
            return self._c.get_json(url, max_age_s=max_age_s)
        finally:
            self._after(before)

    @property
    def n_requests(self) -> int:
        return self._c.n_requests - self._start

    @property
    def n_cache_hits(self) -> int:
        return self._c.n_cache_hits


def offline_client():
    from scripts.data.edgar_client import EdgarClient
    return EdgarClient(offline=True)
