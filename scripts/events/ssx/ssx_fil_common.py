"""Shared plumbing for the SEC-filings seat's zero-trial censuses (prefix `ssx_fil`).

ZERO TRIALS. Nothing here computes a return, a P&L, a drift or a hit rate. It
counts filings, links filers to listed securities, measures PRE-event dollar
volume (events dated <= 2022-12-31, CRSP rows < 2023-01-01) and reads today's
Alpaca borrow flags. Every guard that enforces that raises; none warns.

WHY ONE MODULE
--------------
Four censuses (D4 late-filing notices, D6 8-K red flags, D9 report timing, D2
BDC NAV) ask the same three questions of different filings: which filer is a
listed common stock on the event date, how liquid was it before the event, and
can we short it today. Answering them three different ways would give three
different match rates for one desk. So the link, the ADV window and the borrow
read live here once.

THE SOURCES, IN THE ORDER CLAUDE.md RANKS THEM
----------------------------------------------
1. EDGAR, through `scripts/data/edgar_client.py` only (fair access, declared
   agent, disk cache). Three EDGAR products are used, all public:
   * the quarterly full indexes (`master.gz`), offline from the shared cache:
     every filing's form, filer CIK, filer name AT FILING and filing date;
   * the nightly bulk submissions archive (`submissions.zip`): per CIK, every
     filing's `reportDate` (period), `acceptanceDateTime` and, for 8-Ks, the
     item numbers the master index lacks. It is read from a cache passed in
     `--bulk-cache`; a live fetch is one request (1.5 GB);
   * filing headers (`{accession}.txt`), live and sampled, because the
     submissions API's acceptanceDateTime is one UTC offset late on 23 of 50
     sampled filings (REFERENCES §12y/§12z): the header is the authority.
   Live requests are spaced 1.5 s apart (the brief's shared-limit rule) and
   every one is appended to `edgar_live_requests.jsonl`; a call that would take
   the seat past LIVE_BUDGET raises before it is sent.
2. R2 (the WRDS mirror), read-only: Compustat `company` (gvkey -> CIK), the
   CRSP/Compustat link history (gvkey -> permno by date), CRSP `dsenames`
   (share and exchange codes by date) and CRSP `dsf` (dollar volume). Licensed
   rows stay under `results/events/ssx/_cache_ssx_fil/` (gitignored).
3. Alpaca, read-only GETs: `GET /v2/clock` and `GET /v2/assets`. Never an order,
   cancel or account call. Flags are true on the read date only (landmine 5).

THE CIK -> PERMNO ROUTE, AND WHY THIS ONE
-----------------------------------------
CRSP carries no CIK. Three routes were open: (a) the SEC ticker file, which
holds TODAY's tickers only and so drops every filer that later delisted -- the
late filers this desk most wants to see; (b) fuzzy name matching EDGAR's
conformed name to CRSP's 35-character abbreviated name, whose errors would be
silent; (c) Compustat's `company.cik` joined to the CRSP/Compustat link history
(`ccmxpf_lnkhist`, primary links LC/LU, P/C), which is dated, survivorship-free
and the standard academic link. (c) is used. Its blind spot is stated, not
patched: a CIK with no Compustat record, and a listed common with no CCM link,
count as UNLINKED. The match rate is reported per census and, as a recall
check, on the CIKs EDGAR lists today as exchange-traded.

THE ADV WINDOW
--------------
Mean of |prc| x vol over the 20 sessions t-21..t-2 before the event's EDGAR
filing date t (the corp catalogue's window, so capacities compare). At least 15
of the 20 sessions must exist or the event has no ADV (reported, not filled).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events" / "ssx" / "ssx_fil"
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_fil"   # gitignored: results/**/_cache_*
LEDGER = OUT / "edgar_live_requests.jsonl"
LIVE_BUDGET = 1200          # the brief's cap for this seat (shared SEC limit)
LIVE_INTERVAL_S = 1.5       # the brief's spacing: ten seats share one address

SHARED_EDGAR_CACHE = REPO / "results" / "events" / "_cache_edgar"
SUBMISSIONS_ZIP_URL = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
COMPANYFACTS_ZIP_URL = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
INDEX_URL = "https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/master.gz"

COUNT_START, COUNT_END = 2008, 2025          # event counts may run to 2025-12-31
TIME_HOLDOUT = dt.date(2023, 1, 1)           # no market row on or after this date is read
ADV_LAST_EVENT = dt.date(2022, 12, 31)
ADV_SESSIONS, ADV_SKIP, ADV_MIN = 20, 1, 15  # sessions t-21..t-2; >= 15 present
DV_PANEL_START = dt.date(2007, 10, 1)

LISTED_SHRCD = (10, 11)                      # CRSP ordinary common shares
LISTED_EXCHCD = (1, 2, 3, 4)                 # NYSE, NYSE American, Nasdaq, NYSE Arca
CCM_LINKTYPES = ("LC", "LU")
CCM_LINKPRIM = ("P", "C")


class CensusError(RuntimeError):
    """A required input is missing or contradicts itself."""


# ---------------------------------------------------------------- EDGAR

class BudgetedEdgar:
    """`EdgarClient` at 1.5 s spacing, with a ledger and a hard request budget.

    WHY: ten seats share one SEC address and one fair-access allowance. A seat
    that overran its share could lock the desk out of EDGAR (HTTP 403 for ~10
    minutes, edgar_client docstring). So the budget is checked BEFORE a live
    request: a cached URL is free, an uncached one raises once the ledger holds
    LIVE_BUDGET entries.
    """

    def __init__(self, offline: bool, cache: Path = SHARED_EDGAR_CACHE, budget: int = LIVE_BUDGET):
        from scripts.data.edgar_client import EdgarClient, RateLimiter, cache_path
        self._cache_path = cache_path
        self.cache = Path(cache)
        self.offline = offline
        self.budget = budget
        self.c = EdgarClient(offline=offline, cache=self.cache, limiter=RateLimiter(min_interval=LIVE_INTERVAL_S))

    @staticmethod
    def spent() -> int:
        if not LEDGER.exists():
            return 0
        return sum(1 for line in LEDGER.read_text().splitlines() if line.strip())

    def is_cached(self, url: str) -> bool:
        return self._cache_path(url, self.cache).exists()

    def _guard(self, url: str, max_age_s) -> None:
        p = self._cache_path(url, self.cache)
        fresh = p.exists() and (max_age_s is None or (dt.datetime.now().timestamp() - p.stat().st_mtime) < max_age_s)
        if not fresh and not self.offline and self.spent() >= self.budget:
            raise CensusError(f"live EDGAR budget {self.budget} spent ({LEDGER}); refusing {url}")

    def _log(self, url: str, before: int, purpose: str) -> None:
        n = self.c.n_requests - before
        if n <= 0:
            return
        OUT.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a") as f:
            for _ in range(n):
                f.write(json.dumps({"utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                    "url": url, "purpose": purpose}) + "\n")

    def get_text(self, url: str, purpose: str, max_age_s=None) -> str:
        self._guard(url, max_age_s)
        before = self.c.n_requests
        try:
            return self.c.get_text(url, max_age_s)
        finally:
            self._log(url, before, purpose)

    def get_bytes(self, url: str, purpose: str, max_age_s=None) -> bytes:
        self._guard(url, max_age_s)
        before = self.c.n_requests
        try:
            return self.c.get(url, max_age_s)
        finally:
            self._log(url, before, purpose)

    def get_json(self, url: str, purpose: str, max_age_s=None):
        return json.loads(self.get_text(url, purpose, max_age_s))


def master_index(forms: set[str], start_year: int = COUNT_START, end_year: int = COUNT_END,
                 cache: Path = SHARED_EDGAR_CACHE) -> pd.DataFrame:
    """Rows of the cached quarterly master indexes whose form is in `forms`.

    Offline only: a closed quarter's index is immutable, and 2008Q1-2025Q4 are
    already in the shared cache. Raises on a missing quarter rather than
    counting a year short.
    """
    from scripts.data import fetch_edgar_events as fe
    from scripts.data.edgar_client import EdgarClient
    c = EdgarClient(offline=True, cache=cache)
    frames = []
    for y in range(start_year, end_year + 1):
        for q in range(1, 5):
            text = c.get_text(INDEX_URL.format(y=y, q=q))
            frames.append(fe.parse_master_index(text, label=f"{y}Q{q}", keep_forms=forms))
    df = pd.concat(frames, ignore_index=True)
    df["year"] = df["date_filed"].dt.year
    return df


def bulk_zip(url: str, bulk_cache: Path | None, allow_live: bool = False) -> zipfile.ZipFile:
    """Open a nightly bulk archive from `bulk_cache` (an EDGAR-client cache root).

    WHY a path argument: the 1.5 GB archive was fetched once for the desk on
    2026-10-15 (ss-spac). Re-fetching it per seat would spend shared bandwidth
    for no new information on events dated <= 2025-12-31. With no cached copy,
    `allow_live` fetches it once (one request) into the shared cache.
    """
    from scripts.data.edgar_client import cache_path
    roots = [Path(bulk_cache)] if bulk_cache else []
    roots.append(SHARED_EDGAR_CACHE)
    for r in roots:
        p = cache_path(url, r)
        if p.exists():
            return zipfile.ZipFile(p)
    if not allow_live:
        raise CensusError(f"{url} is not cached under {roots}; pass --bulk-cache or --allow-live-bulk")
    BudgetedEdgar(offline=False).get_bytes(url, purpose="bulk archive")
    return zipfile.ZipFile(cache_path(url, SHARED_EDGAR_CACHE))


def bulk_zip_date(z: zipfile.ZipFile) -> str:
    """The archive's own snapshot date: the latest member timestamp."""
    return max(dt.datetime(*i.date_time) for i in z.infolist()[:2000]).date().isoformat()


SUB_COLS = ("accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "items",
            "primaryDocument", "isXBRL")


def submissions_rows(z: zipfile.ZipFile, ciks, forms: set[str] | None, first_date: str = "2007-01-01") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Filing rows (and entity metadata) for `ciks` from the bulk submissions archive.

    Follows each CIK's `files` pages, so a heavy filer's pre-recent history is
    not silently dropped. A CIK absent from the archive is listed in the
    metadata frame with `in_archive=False`, never skipped silently.
    """
    try:
        import orjson as _json
        loads = _json.loads
    except ImportError:  # stdlib json is slower, not different
        loads = json.loads
    names = set(z.namelist())
    rows, meta = [], []
    for cik in sorted(set(int(c) for c in ciks)):
        fn = f"CIK{cik:010d}.json"
        if fn not in names:
            meta.append({"cik": cik, "in_archive": False})
            continue
        j = loads(z.read(fn))
        blocks = [j["filings"]["recent"]]
        for p in j["filings"].get("files", []):
            if p["name"] not in names:
                raise CensusError(f"CIK {cik}: page {p['name']} missing from the archive")
            blocks.append(loads(z.read(p["name"])))
        for b in blocks:
            n = len(b["accessionNumber"])
            for i in range(n):
                f = b["form"][i]
                if forms is not None and f not in forms:
                    continue
                if b["filingDate"][i] < first_date:
                    continue
                rows.append((cik, *(b.get(k, [None] * n)[i] for k in SUB_COLS)))
        meta.append({"cik": cik, "in_archive": True, "name": j.get("name"), "sic": j.get("sic"),
                     "entityType": j.get("entityType"), "category": j.get("category"),
                     "tickers": "|".join(j.get("tickers") or []), "exchanges": "|".join(x or "" for x in (j.get("exchanges") or [])),
                     "fiscalYearEnd": j.get("fiscalYearEnd")})
    df = pd.DataFrame(rows, columns=["cik", *SUB_COLS])
    return df, pd.DataFrame(meta)


# ---------------------------------------------------------------- acceptance time

NY = None


def _ny():
    global NY
    if NY is None:
        from zoneinfo import ZoneInfo
        NY = ZoneInfo("America/New_York")
    return NY


def header_acceptance_et(txt: str) -> dt.datetime:
    """`<ACCEPTANCE-DATETIME>` from a submission header: Eastern wall-clock time (REFERENCES §12z)."""
    import re
    m = re.search(r"<ACCEPTANCE-DATETIME>(\d{14})", txt[:6000])
    if not m:
        raise CensusError("no <ACCEPTANCE-DATETIME> in the first 6,000 characters of the header")
    return dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S")


def api_as_et(value: str) -> dt.datetime:
    """The submissions API value read at its word (UTC) and expressed in Eastern wall-clock time."""
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CensusError(f"acceptanceDateTime {value!r} is not Z-suffixed")
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return t.astimezone(_ny()).replace(tzinfo=None)


# ---------------------------------------------------------------- R2: link and liquidity

def _r2():
    from src.data import r2
    con = r2.connect()
    con.execute("SET enable_progress_bar=false")
    return r2, con


def cik_permno_links(offline: bool = False) -> pd.DataFrame:
    """CIK -> permno with link dates: Compustat company.cik x CCM lnkhist (LC/LU, P/C). Cached."""
    p = CACHE / "cik_permno_ccm.parquet"
    if p.exists():
        return pd.read_parquet(p)
    if offline:
        raise CensusError(f"offline and {p} is not cached")
    r2, con = _r2()
    comp = r2.r2_path("comp_na_daily_all", "company")
    lnk = r2.r2_path("crsp_a_ccm", "ccmxpf_lnkhist")
    df = r2.q(con, f"""
        SELECT c.gvkey, CAST(c.cik AS BIGINT) AS cik, c.conm, l.lpermno AS permno, l.linktype, l.linkprim,
               l.linkdt, l.linkenddt
        FROM read_parquet('{comp}') c JOIN read_parquet('{lnk}') l ON c.gvkey = l.gvkey
        WHERE c.cik IS NOT NULL AND c.cik <> '' AND l.lpermno IS NOT NULL
          AND l.linktype IN {CCM_LINKTYPES} AND l.linkprim IN {CCM_LINKPRIM}""")
    df["linkdt"] = pd.to_datetime(df["linkdt"])
    df["linkenddt"] = pd.to_datetime(df["linkenddt"]).fillna(pd.Timestamp("2099-12-31"))  # CCM: open link = 'E' (still valid)
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)
    return df


def crsp_names(offline: bool = False) -> pd.DataFrame:
    """CRSP dsenames spells alive on or after 2007 (share code, exchange code, ticker). Cached."""
    p = CACHE / "crsp_dsenames_2007plus.parquet"
    if p.exists():
        return pd.read_parquet(p)
    if offline:
        raise CensusError(f"offline and {p} is not cached")
    r2, con = _r2()
    df = r2.q(con, f"""SELECT permno, permco, namedt, nameendt, shrcd, exchcd, ticker, comnam, siccd
                       FROM read_parquet('{r2.r2_path("crsp_a_stock", "dsenames")}')
                       WHERE nameendt >= DATE '2007-01-01'""")
    df["namedt"] = pd.to_datetime(df["namedt"])
    df["nameendt"] = pd.to_datetime(df["nameendt"])
    df.to_parquet(p)
    return df


def dv_panel(offline: bool = False) -> pd.DataFrame:
    """CRSP daily dollar volume |prc| x vol, 2007-10-01 .. 2022-12-30. Cached; licensed.

    The time holdout is enforced twice: the SQL stops at 2022-12-31 and the
    frame is checked after the read.
    """
    p = CACHE / "crsp_dv_2007_2022.parquet"
    if p.exists():
        df = pd.read_parquet(p)
    else:
        if offline:
            raise CensusError(f"offline and {p} is not cached")
        r2, con = _r2()
        df = r2.q(con, f"""SELECT permno, date, CAST(abs(prc) * vol AS FLOAT) AS dv
                           FROM read_parquet('{r2.r2_path("crsp_a_stock", "dsf")}')
                           WHERE date BETWEEN DATE '{DV_PANEL_START}' AND DATE '2022-12-31'
                             AND prc IS NOT NULL AND vol IS NOT NULL""")
        df["date"] = pd.to_datetime(df["date"])
        df["permno"] = df["permno"].astype("int32")
        df.to_parquet(p)
    if df["date"].max() >= pd.Timestamp(TIME_HOLDOUT):
        raise CensusError("a 2023+ CRSP row is in the dollar-volume panel: the time holdout")
    return df


def link_events(ev: pd.DataFrame, links: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    """Add permno, shrcd, exchcd and `listed_common` to events (columns cik, date).

    A permno is taken when a CCM link for the CIK covers the date. If more than
    one does (a dual-class issuer), the one whose CRSP spell on that date is an
    ordinary common share on a national exchange is kept; a tie keeps the
    lowest permno and the row is flagged `multi_permno` (reported, not hidden).
    """
    e = ev[["cik", "date"]].drop_duplicates().copy()
    e["date"] = pd.to_datetime(e["date"])
    m = e.merge(links[["cik", "permno", "linkdt", "linkenddt"]], on="cik", how="left")
    m = m[(m["permno"].isna()) | ((m["linkdt"] <= m["date"]) & (m["date"] <= m["linkenddt"]))]
    m = m.dropna(subset=["permno"])
    m["permno"] = m["permno"].astype("int64")
    n = names[["permno", "namedt", "nameendt", "shrcd", "exchcd", "ticker"]]
    m = m.merge(n, on="permno", how="left")
    m = m[(m["namedt"] <= m["date"]) & (m["date"] <= m["nameendt"])]
    m["listed_common"] = m["shrcd"].isin(LISTED_SHRCD) & m["exchcd"].isin(LISTED_EXCHCD)
    m = m.sort_values(["cik", "date", "listed_common", "permno"], ascending=[True, True, False, True])
    cnt = m.groupby(["cik", "date"])["permno"].transform("size")
    m["multi_permno"] = cnt > 1
    m = m.drop_duplicates(["cik", "date"], keep="first")
    out = ev.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.merge(m[["cik", "date", "permno", "shrcd", "exchcd", "ticker", "listed_common", "multi_permno"]],
                    on=["cik", "date"], how="left")
    out["linked"] = out["permno"].notna()
    out["listed_common"] = out["listed_common"].astype("boolean").fillna(False).astype(bool)
    return out


def pre_event_adv(ev: pd.DataFrame, dv: pd.DataFrame) -> pd.Series:
    """ADV over sessions t-21..t-2 for rows with a permno and a date <= 2022-12-31; NaN otherwise.

    Alignment: only sessions strictly before t-1 enter, so an event's own day
    and the day before (when an evening filing could already move the price)
    are excluded. Asserted below on every row computed.
    """
    out = pd.Series(np.nan, index=ev.index, dtype="float64")
    ok = ev["permno"].notna() & (pd.to_datetime(ev["date"]) <= pd.Timestamp(ADV_LAST_EVENT))
    if not ok.any():
        return out
    by = {int(p): g for p, g in dv.groupby("permno")}
    for idx, r in ev[ok].iterrows():
        g = by.get(int(r["permno"]))
        if g is None:
            continue
        d = np.searchsorted(g["date"].values, np.datetime64(pd.Timestamp(r["date"])), side="left")
        lo, hi = max(0, d - ADV_SKIP - ADV_SESSIONS), max(0, d - ADV_SKIP)
        w = g.iloc[lo:hi]
        if len(w) < ADV_MIN:
            continue
        assert w["date"].max() < pd.Timestamp(r["date"]), "ADV window reached the event date"
        out.at[idx] = float(w["dv"].mean())
    return out


def dv_by_permno(dv: pd.DataFrame) -> dict:
    """Sorted per-permno frames, built once for repeated ADV calls."""
    return {int(p): g.sort_values("date").reset_index(drop=True) for p, g in dv.groupby("permno")}


def pre_event_adv_fast(ev: pd.DataFrame, by: dict) -> np.ndarray:
    """`pre_event_adv` over a prebuilt per-permno dict (same window, same guard)."""
    out = np.full(len(ev), np.nan)
    dates = pd.to_datetime(ev["date"]).values
    perm = ev["permno"].values
    lim = np.datetime64(pd.Timestamp(ADV_LAST_EVENT))
    for i in range(len(ev)):
        p = perm[i]
        if p != p or dates[i] > lim:   # NaN permno, or after the last event date allowed
            continue
        g = by.get(int(p))
        if g is None:
            continue
        gd = g["date"].values
        d = np.searchsorted(gd, dates[i], side="left")
        lo, hi = max(0, d - ADV_SKIP - ADV_SESSIONS), max(0, d - ADV_SKIP)
        if hi - lo < ADV_MIN:
            continue
        assert gd[hi - 1] < dates[i], "ADV window reached the event date"
        out[i] = float(g["dv"].values[lo:hi].mean())
    return out


# ---------------------------------------------------------------- Alpaca (read-only)

def alpaca_assets(refresh: bool = False) -> tuple[pd.DataFrame, str]:
    """Today's active US-equity assets (GET /v2/assets) and the Alpaca clock, cached per day.

    Read-only: `clock()` and `assets()` only. The cache file is dated so a
    stale snapshot is never mistaken for today's flags (landmine 5).
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    p = CACHE / f"alpaca_assets_{today}.parquet"
    meta = CACHE / f"alpaca_assets_{today}.json"
    if p.exists() and meta.exists() and not refresh:
        return pd.read_parquet(p), json.loads(meta.read_text())["clock"]
    from quantt.broker.alpaca import AlpacaClient
    c = AlpacaClient.from_environment("cef")
    clock = c.clock()["timestamp"]
    clock = clock.isoformat() if hasattr(clock, "isoformat") else str(clock)
    a = pd.DataFrame(c.assets(status="active"))
    if a.empty:
        raise CensusError("GET /v2/assets returned no active assets")
    a.to_parquet(p)
    meta.write_text(json.dumps({"clock": clock, "endpoint": "GET /v2/assets?status=active&asset_class=us_equity",
                                "rows": int(len(a))}))
    return a, clock


def sec_tickers_today(meta: pd.DataFrame) -> pd.DataFrame:
    """(cik, ticker, exchange) rows from the bulk archive's entity metadata (its own snapshot date)."""
    rows = []
    for r in meta.itertuples():
        if not getattr(r, "in_archive", False) or not isinstance(r.tickers, str) or not r.tickers:
            continue
        ex = (r.exchanges or "").split("|")
        for i, t in enumerate(r.tickers.split("|")):
            rows.append({"cik": r.cik, "ticker": t, "exchange": ex[i] if i < len(ex) else ""})
    return pd.DataFrame(rows, columns=["cik", "ticker", "exchange"])


NATIONAL_EXCHANGES = ("NYSE", "Nasdaq", "CBOE", "NYSE American", "NYSE Arca", "NYSE MKT", "BATS")


def borrow_today(ciks, meta: pd.DataFrame, assets: pd.DataFrame) -> pd.DataFrame:
    """Per CIK: listed on a national exchange today (EDGAR), present at Alpaca, shortable, ETB.

    A CIK with several exchange tickers counts as shortable if ANY line is
    (the desk would short that line). Alpaca writes class shares as BRK.B and
    EDGAR as BRK-B; both are tried.
    """
    t = sec_tickers_today(meta[meta["cik"].isin(set(int(c) for c in ciks))])
    t = t[t["exchange"].isin(NATIONAL_EXCHANGES)]
    A = assets.set_index("symbol")
    out = []
    for cik, g in t.groupby("cik"):
        found = sh = etb = False
        for tk in g["ticker"]:
            for s in (tk, tk.replace("-", "."), tk.replace("-", "")):
                if s in A.index:
                    found = True
                    s_sh = bool(A.at[s, "shortable"])
                    sh = sh or s_sh
                    # ETB counts only on a shortable line: one active asset reads
                    # easy_to_borrow=True with shortable=False (2026-10-19 snapshot).
                    v = A.at[s, "easy_to_borrow"]
                    etb = etb or (s_sh and v is not None and v == v and bool(v))   # numpy bool: never `is True`
                    break
        out.append({"cik": cik, "listed_today": True, "at_alpaca": found, "shortable": sh, "etb": etb})
    return pd.DataFrame(out, columns=["cik", "listed_today", "at_alpaca", "shortable", "etb"])


# ---------------------------------------------------------------- BDC status

def bdc_spells(subs: pd.DataFrame) -> pd.DataFrame:
    """Per CIK: first N-54A (election as a BDC) and the first N-54C (withdrawal) after it.

    WHY these forms: Section 54 of the Investment Company Act makes BDC status
    an election filed on Form N-54A and withdrawn on N-54C, so the filings
    themselves date the status. A BDC that elected on paper before EDGAR
    (1996) has no N-54A on EDGAR and is missed; the count is reported, not
    padded.
    """
    s = subs[subs["form"].isin(["N-54A", "N-54C"])].copy()
    s["filingDate"] = pd.to_datetime(s["filingDate"])
    a = s[s["form"] == "N-54A"].groupby("cik")["filingDate"].min().rename("elected")
    w = s[s["form"] == "N-54C"][["cik", "filingDate"]].merge(a.reset_index(), on="cik")
    w = w[w["filingDate"] > w["elected"]].groupby("cik")["filingDate"].min().rename("withdrawn")
    out = a.to_frame().join(w, how="left").reset_index()
    out["withdrawn"] = out["withdrawn"].fillna(pd.Timestamp("2099-12-31"))  # not withdrawn: open spell
    return out


def is_bdc_on(ev: pd.DataFrame, spells: pd.DataFrame) -> pd.Series:
    """True where the event's CIK was an elected, not-withdrawn BDC on the event date."""
    m = ev[["cik", "date"]].reset_index().merge(spells, on="cik", how="left")
    ok = (m["elected"] <= pd.to_datetime(m["date"])) & (pd.to_datetime(m["date"]) < m["withdrawn"])
    return ok.groupby(m["index"]).any().reindex(ev.index, fill_value=False)


# ---------------------------------------------------------------- small helpers

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 4), round(c + h, 4))


def declared_order(keys, salt: str) -> list:
    """Keys sorted by sha256(salt:key): a content-blind sampling order declared before reading."""
    return sorted(keys, key=lambda k: hashlib.sha256(f"{salt}:{k}".encode()).hexdigest())


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str) + "\n")
