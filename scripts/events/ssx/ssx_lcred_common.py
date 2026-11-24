"""Shared plumbing for the listed-credit (preferreds and baby bonds) census, ssx_lcred.

WHAT THIS IS
------------
The special-situations expansion (team lead, 2026-10-19) asks the listed-credit
seat for zero-trial censuses of seven ideas (C1-C4, C6, C7 and the queued CR15
gate). Every script `scripts/events/ssx/ssx_lcred_*.py` imports this module so
that the classification regex, the EDGAR budget and the Alpaca client are
defined once.

ZERO TRIALS -- THE HARD LINE THIS MODULE ENFORCES
-------------------------------------------------
* `alpaca_volume_bars` returns VOLUME ONLY. The open/high/low/close/vwap fields
  of every Alpaca bar are dropped inside the function before anything else can
  see them, and the function raises if asked for a bar dated 2023-01-01 or
  later. Pre-event volume is allowed only for events on or before 2022-12-31;
  prices and returns are not allowed at all.
* The one exception is `alpaca_snapshot_prices`, the single labelled quote
  snapshot the brief allows for counting TODAY's opportunity set (idea C6). It
  refuses to run twice in one process.
* `EdgarBudget` wraps the shared `EdgarClient` with a hard cap on LIVE requests
  (the brief's 1,000, shared across the SEC's fair-access limit; capped here
  below that) and the brief's 1.5 s spacing. A cache hit costs nothing. When the
  cap is reached it RAISES; it never silently skips a document.

NO SILENT FALLBACKS. A missing file, column or key raises and names it.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

pd.set_option("compute.use_numexpr", False)     # scripts/events/numexpr_fault.py

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = REPO / "results" / "events" / "ssx" / "ssx_lcred"
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_lcred"      # licensed rows only (gitignored)
EDGAR_CACHE = REPO / "results" / "events" / "_cache_edgar"
MASTER_DIR = EDGAR_CACHE / "www.sec.gov" / "Archives" / "edgar" / "full-index"

HOLDOUT_START = dt.date(2023, 1, 1)             # H13: no price/return series on or after this
EDGAR_LIVE_CAP = 950                            # the brief's 1,000 live requests, with headroom
EDGAR_MIN_INTERVAL = 1.5                        # the brief's spacing, seconds

# ------------------------------------------------------------------ classification
# Reused from scripts/events/ss_credit_catalogue_counts.py (the 2026-10-15 census) and
# tightened after reading its 547 rows on 2026-10-19:
#  * "American Depositary Shares ... Preferred" are foreign preferred-share ADRs
#    (BBD, CIB, AXICY): equity of a foreign bank, not a $25-par listed preferred.
#  * "Preferred Bank Common Stock" (PFBC) matched on the word "Preferred".
#  * NYSE writes every preferred with ".PR" in Alpaca's symbol; a name that omits
#    "Preferred" (e.g. "... Series K Non-Cumulative Perpetual") was missed.
PREF_RE = re.compile(r"PREFERRED|PREFERENCE|\bPFD\b|\bPREF\b|PRFRD", re.I)
FUND_RE = re.compile(r"\bETF\b|\bETN\b|EXCHANGE-TRADED|\bFUND\b", re.I)
BABY_BOND_RE = re.compile(r"%\s*(SENIOR\s+|SUBORDINATED\s+|FIXED[- ]RATE\s+|"
                          r"FIXED[- ]TO[- ]FLOATING\s+)?(NOTES?|DEBENTURES?)\b|"
                          r"\bNOTES?\s+DUE\b|\bDEBENTURES?\s+DUE\b|"
                          r"\b(SENIOR|SUBORDINATED|JUNIOR)\b.*\b(NOTES?|DEBENTURES?)\b", re.I)
# "CONV" abbreviates convertible (WFC.PRL); "Corporate/Equity Units" are mandatory-convertible
# units (NEE.PRS); "Bifurcated Option Note Unit SecuritiES" is a convertible unit (FLG.PRU).
CONVERT_RE = re.compile(r"CONVERTIBLE|\bCONV\b|MANDATOR|EXCHANGEABLE|CORPORATE UNITS|EQUITY UNITS|"
                        r"UNIT SECURIT", re.I)
ADR_RE = re.compile(r"AMERICAN DEPOSITARY|\bADS\b|\bADR\b", re.I)
COMMON_RE = re.compile(r"COMMON STOCK|COMMON SHARES|ORDINARY SHARES", re.I)
NYSE_PREF_SYM = re.compile(r"\.PR[A-Z]?$")

FTF_RE = re.compile(r"FIXED[- ]?(RATE)?[- ]?(TO|/)[- ]?FLOAT|FIXED/FLOATING", re.I)
RESET_RE = re.compile(r"RESET", re.I)
FLOAT_RE = re.compile(r"FLOATING|VARIABLE RATE|ADJUSTABLE RATE", re.I)
NONCUM_RE = re.compile(r"NON[- ]?\s?CUMULATIVE|NONCUMULATIVE", re.I)
CUM_RE = re.compile(r"CUMULATIVE", re.I)
TERM_PREF_RE = re.compile(r"TERM PREFERRED", re.I)


def classify(symbol: str, name: str) -> tuple[str | None, str]:
    """(kind, rule) where kind is 'preferred', 'baby_bond' or None.

    `rule` names the branch that decided, so every row can be audited. The
    order matters: a convertible, a pooled vehicle, an ADR or a common stock is
    never an issue of either kind, whatever else its name says."""
    if CONVERT_RE.search(name):
        return None, "convertible/exchangeable"
    if FUND_RE.search(name):
        return None, "pooled vehicle"
    if ADR_RE.search(name):
        return None, "ADR"
    if COMMON_RE.search(name):
        return None, "common stock"
    if BABY_BOND_RE.search(name) or (NYSE_PREF_SYM.search(symbol) and re.search(r"\bNOTES?\b", name, re.I)):
        return "baby_bond", "name: notes/debentures"
    if PREF_RE.search(name):
        return "preferred", "name: preferred"
    if NYSE_PREF_SYM.search(symbol):
        return "preferred", "symbol: NYSE .PR"
    return None, "no match"


def tags(name: str) -> dict:
    """Coupon-structure and cumulative tags read from the NAME (a lower bound:
    many prospectuses say 'fixed-to-floating' where the listed name does not)."""
    ftf = bool(FTF_RE.search(name))
    reset = bool(RESET_RE.search(name))
    flo = bool(FLOAT_RE.search(name)) and not ftf
    if NONCUM_RE.search(name):
        cum = "non_cumulative"
    elif CUM_RE.search(name):
        cum = "cumulative"
    else:
        cum = "unstated"
    return {"name_fixed_to_float": ftf, "name_reset": reset, "name_floating": flo,
            "cumulative": cum, "term_preferred": bool(TERM_PREF_RE.search(name))}


# ------------------------------------------------------------------ Alpaca (read-only)

def env_file() -> str:
    p = os.environ.get("QUANTT_ENV_FILE", "")
    if not p:
        raise RuntimeError("QUANTT_ENV_FILE is not set: it must name the env file "
                           "holding the Alpaca keys (never printed)")
    return p


def alpaca():
    """The paper `cef` book's client: GETs only (the client refuses any trading
    endpoint other than paper, and nothing here calls submit_order)."""
    from quantt.broker.alpaca import AlpacaClient
    env_file()
    return AlpacaClient.from_environment("cef")


def alpaca_assets(c) -> list[dict]:
    from quantt.broker.alpaca import PAPER_BASE
    raw = c._get(PAPER_BASE, "/v2/assets", {"status": "active", "asset_class": "us_equity"})
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("GET /v2/assets returned no list")
    return raw


def alpaca_volume_bars(c, symbols: list[str], start: dt.date, end: dt.date,
                       timeframe: str = "1Day") -> pd.DataFrame:
    """Daily (or monthly) VOLUME for `symbols`, raw (unadjusted), SIP feed.

    Returns columns symbol, t (date), v (shares), n (trade count). Prices are
    DROPPED here, before the frame exists: the brief permits pre-2023 volume and
    no prices. Raises if `end` is on or after 2023-01-01 (H13)."""
    if end >= HOLDOUT_START:
        raise ValueError(f"end {end} is inside the 2023+ holdout: volume bars stop at 2022-12-31")
    if not symbols:
        raise ValueError("no symbols")
    rows = []
    for i in range(0, len(symbols), 50):
        chunk = symbols[i:i + 50]
        token = None
        for _ in range(2000):
            params = {"symbols": ",".join(chunk), "timeframe": timeframe,
                      "start": start.isoformat(), "end": end.isoformat(),
                      "adjustment": "raw", "feed": "sip", "limit": 10000}
            if token:
                params["page_token"] = token
            body = c._get(c._data, "/v2/stocks/bars", params)
            if "bars" not in body:
                raise RuntimeError("GET /v2/stocks/bars: no 'bars' key")
            for sym, bars in (body["bars"] or {}).items():
                for b in bars:
                    # keep timestamp, volume and trade count ONLY; o/h/l/c/vw never leave
                    rows.append((sym, b["t"][:10], int(b["v"]), int(b.get("n", 0))))
            token = body.get("next_page_token")
            if not token:
                break
        else:
            raise RuntimeError("bars pagination did not end")
    df = pd.DataFrame(rows, columns=["symbol", "t", "v", "n"])
    df["t"] = pd.to_datetime(df["t"]).dt.date
    if len(df) and max(df["t"]) >= HOLDOUT_START:
        raise RuntimeError("a 2023+ bar came back: refusing")
    return df


_SNAPSHOT_TAKEN = False


def alpaca_snapshot_prices(c, symbols: list[str], session: dt.date) -> pd.DataFrame:
    """THE one current price cross-section the brief allows (idea C6: count today's
    opportunity set), callable once per process; labelled by the caller.

    It is the SIP daily bar of ONE completed session (`session`, the last full
    session before the read), close and volume only. Why not the real-time
    snapshot: on 2026-10-19 `GET /v2/stocks/snapshots?feed=sip` answered HTTP 403
    "subscription does not permit querying recent SIP data" and returned no data;
    the Basic plan serves SIP history older than 15 minutes, so the last completed
    session's official close is the cleanest single cross-section available."""
    global _SNAPSHOT_TAKEN
    if _SNAPSHOT_TAKEN:
        raise RuntimeError("the single permitted snapshot has already been taken")
    _SNAPSHOT_TAKEN = True
    rows = []
    for i in range(0, len(symbols), 100):
        chunk = symbols[i:i + 100]
        token = None
        for _ in range(100):
            params = {"symbols": ",".join(chunk), "timeframe": "1Day", "start": session.isoformat(),
                      "end": session.isoformat(), "adjustment": "raw", "feed": "sip", "limit": 10000}
            if token:
                params["page_token"] = token
            body = c._get(c._data, "/v2/stocks/bars", params)
            for sym, bars in (body.get("bars") or {}).items():
                for b in bars:
                    rows.append({"symbol": sym, "session": b["t"][:10], "close": b["c"], "volume": b["v"]})
            token = body.get("next_page_token")
            if not token:
                break
    return pd.DataFrame(rows)


def trading_sessions(c, start: dt.date, end: dt.date) -> list[dt.date]:
    cal = c.calendar(start, end)
    return [dt.date.fromisoformat(d["date"]) if isinstance(d["date"], str) else d["date"] for d in cal]


# ------------------------------------------------------------------ EDGAR

class EdgarBudget:
    """The shared EdgarClient with a hard live-request cap and the brief's spacing.

    `offline=True` reads the shared cache only and raises on a miss."""

    def __init__(self, offline: bool = False, cap: int = EDGAR_LIVE_CAP):
        from scripts.data.edgar_client import EdgarClient, RateLimiter
        if not offline:
            env_file()           # load_user_agent reads the same env file; never printed
        self.client = EdgarClient(limiter=RateLimiter(min_interval=EDGAR_MIN_INTERVAL),
                                  offline=offline)
        self.cap = cap

    @property
    def live(self) -> int:
        return self.client.n_requests

    def _check(self):
        if self.client.n_requests >= self.cap:
            raise RuntimeError(f"EDGAR live-request cap {self.cap} reached; stop and report")

    def text(self, url: str, max_age_s: float | None = None) -> str:
        self._check()
        return self.client.get_text(url, max_age_s)

    def json(self, url: str, max_age_s: float | None = None):
        self._check()
        return self.client.get_json(url, max_age_s)


def master_index(year: int, qtr: int) -> pd.DataFrame:
    """One quarterly EDGAR master index from the shared cache (offline; closed
    quarters are immutable). Columns cik, company, form, date, filename."""
    p = MASTER_DIR / str(year) / f"QTR{qtr}" / "master.gz"
    if not p.exists():
        raise FileNotFoundError(f"{p} is not cached; fetch it with scripts/data/edgar_client.py")
    t = gzip.decompress(p.read_bytes()).decode("latin-1")
    rows = [l.split("|") for l in t.splitlines() if l.count("|") == 4 and l[:1].isdigit()]
    df = pd.DataFrame(rows, columns=["cik", "company", "form", "date", "filename"])
    df["cik"] = df["cik"].astype(int)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def master_range(y0: int, y1: int, forms: tuple[str, ...]) -> pd.DataFrame:
    out = []
    for y in range(y0, y1 + 1):
        for q in (1, 2, 3, 4):
            p = MASTER_DIR / str(y) / f"QTR{q}" / "master.gz"
            if not p.exists():
                raise FileNotFoundError(p)
            m = master_index(y, q)
            out.append(m[m.form.isin(forms)])
    return pd.concat(out, ignore_index=True)


def accession_from_filename(fn: str) -> str:
    m = re.search(r"(\d{10}-\d{2}-\d{6})\.txt$", fn)
    if not m:
        raise ValueError(f"no accession in {fn!r}")
    return m.group(1)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str) + "\n")
