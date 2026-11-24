"""Fetch and parse the public N-PORT holdings of the deployed CEFs (plus the
Nuveen muni nationals and NAN), 2019-2022, for the ssx_risk censuses B1 and B4.

WHY
---
The ssx_risk seat (results/events/ssx/ssx_risk/CARDS_2026-10-19.md) asks whether
a credit event -- a muni default or impairment (B1), a corporate downgrade or
default (B4) -- touches enough of a fund's NAV that a subtract-only flag on the
live discount book is worth a CEF trial. That needs each fund's holdings at the
CUSIP level, which only N-PORT gives for free.

WHAT EDGAR ACTUALLY HOLDS (measured from the offline master indexes, not assumed)
--------------------------------------------------------------------------------
* The public part of N-PORT is filed as form `NPORT-P`, one per registrant and
  fiscal quarter (the third month of each fiscal quarter); months 1 and 2 are
  non-public. In the 2019Q2-Q3 indexes the public form is `NPORT-EX` only (an
  exhibit, no XML); `NPORT-P` first appears in 2019-10 (22 filings) and
  2019-11 (5,854). So the XML history starts with periods ending about
  Aug-Sep 2019. `ssx_risk_nport.py --index-census` reprints those counts.
* The holdings are `primary_doc.xml` in the filing folder, under
  formData/invstOrSecs/invstOrSec (schema as recorded by the pre-clean-slate
  parser `scripts/nport/parse_nport.py`, git tag `pre-clean-slate`).
* Debt rows carry the fund's own flags: `isDefault`, `areIntrstPmntsInArrs`,
  `isPaidKind`. N-PORT carries NO credit rating per holding. Part B carries
  credit-spread sensitivity (CS01) split into investment-grade and
  non-investment-grade buckets by the fund's own classification; this script
  records both, as the only rating-like field in the filing.

POINT IN TIME
-------------
Each row keeps `report_dt` (the holdings date) AND `filing_date` (when the
public could first see it). A live flag could only ever use holdings whose
filing_date is before the decision date; the censuses report both clocks.

ZERO TRIALS
-----------
No return of any fund is computed here. Holdings, weights and the fund's own
marks (value/par) are descriptive inputs to an event-weight census.

Reproduce:
    QUANTT_ENV_FILE=<abs path to config/.env> python3 scripts/events/ssx/ssx_risk_nport.py --fetch --max-requests 400
    python3 scripts/events/ssx/ssx_risk_nport.py --parse          # offline: cache -> parquet
    python3 scripts/events/ssx/ssx_risk_nport.py --index-census   # offline: NPORT form counts by month

Live requests go through scripts/data/edgar_client.py with
RateLimiter(min_interval=1.5) (the seat's brief: <= 800 live requests, shared
SEC limit). `--max-requests` RAISES before exceeding its cap; it never skips.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.data.edgar_client import EdgarClient, RateLimiter, EdgarNotFound  # noqa: E402
from scripts.data.fetch_edgar_events import parse_master_index, INDEX_URL, quarters  # noqa: E402

CACHE_OUT = REPO / "results" / "events" / "ssx" / "_cache_ssx_risk"
OUT = REPO / "results" / "events" / "ssx" / "ssx_risk"
HOLDINGS_PQ = CACHE_OUT / "nport_holdings_ssx_risk.parquet"
FUNDINFO_PQ = CACHE_OUT / "nport_fundinfo_ssx_risk.parquet"
FILINGS_CSV = OUT / "nport_filings_ssx_risk.csv"

# ticker -> CIK, from the SEC's company_tickers_exchange.json as cached on
# 2026-10-12 (results/events/_cache_edgar/www.sec.gov/files/). The deployed 13
# are read from the frozen spec at run time and checked against this map.
CIK = {
    "PDI": 1510599, "PTY": 1190935, "PDO": 1798618, "PCN": 1160990, "PHK": 1219360,
    "PFN": 1296250, "DSL": 1566388, "HYT": 1222401, "BIT": 1562818, "JFR": 1276533,
    "AWF": 906013, "MQY": 890196, "MHD": 1034665,
    # context: the four Nuveen muni nationals of the old 17 (not shortable at
    # Alpaca, so out of the deployed 13) and NAN, the only single-state fund in
    # the 44-name cef_universe.csv
    "NAD": 1083839, "NEA": 1195737, "NVG": 1090116, "NZF": 1137887, "NAN": 1074769,
}
CONTEXT = ("NAD", "NEA", "NVG", "NZF", "NAN")
FILED_FROM, FILED_TO = date(2019, 7, 1), date(2023, 3, 1)    # a 2022-12-31 period must be filed by 2023-03-01 (60 days); later filings hold 2023 periods and are not fetched
LAST_REPORT_DT = pd.Timestamp("2022-12-31")                    # fit period only (H13)
DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/primary_doc.xml"


def deployed() -> list[str]:
    from scripts.cef.spec import UNIVERSE
    u = list(UNIVERSE)
    missing = [t for t in u if t not in CIK]
    if missing:
        raise KeyError(f"deployed names with no CIK in the map: {missing}")
    return u


def nport_filings(client: EdgarClient, tickers: list[str]) -> pd.DataFrame:
    rows = []
    want = {CIK[t]: t for t in tickers}
    for y, q in quarters(FILED_FROM, FILED_TO):
        df = parse_master_index(client.get_text(INDEX_URL.format(y=y, q=q)), f"{y}Q{q}")
        df = df[df.form.isin(["NPORT-P", "NPORT-P/A"]) & df.cik.isin(want)]
        rows.append(df)
    f = pd.concat(rows, ignore_index=True)
    f["ticker"] = f.cik.map(want)
    f = f[(f.date_filed.dt.date >= FILED_FROM) & (f.date_filed.dt.date <= FILED_TO)]
    return f.sort_values(["ticker", "date_filed"]).reset_index(drop=True)


def index_census(client: EdgarClient) -> dict:
    out = {}
    for y, q in quarters(date(2019, 1, 1), date(2020, 3, 31)):
        df = parse_master_index(client.get_text(INDEX_URL.format(y=y, q=q)), f"{y}Q{q}")
        s = df[df.form.str.contains("NPORT")]
        g = s.groupby([s.date_filed.dt.strftime("%Y-%m"), "form"]).size()
        out[f"{y}Q{q}"] = {f"{m}|{fm}": int(n) for (m, fm), n in g.items()}
    return out


def fetch(max_requests: int) -> None:
    tick = deployed() + list(CONTEXT)
    off = EdgarClient(offline=True)
    f = nport_filings(off, tick)
    OUT.mkdir(parents=True, exist_ok=True)
    f.to_csv(FILINGS_CSV, index=False)
    live = EdgarClient(limiter=RateLimiter(min_interval=1.5))
    orig = f[f.form == "NPORT-P"]
    for r in orig.itertuples():
        url = DOC_URL.format(cik=r.cik, acc=r.accession.replace("-", ""))
        if live.n_requests >= max_requests:
            raise RuntimeError(f"request cap {max_requests} reached before {url}; "
                               f"raise --max-requests deliberately (seat budget 800)")
        try:
            live.get(url)
        except EdgarNotFound:
            print(f"404 {r.ticker} {r.accession}", flush=True)
    print(json.dumps({"filings_listed": int(len(f)), "originals": int(len(orig)),
                      "live_requests": live.n_requests, "cache_hits": live.n_cache_hits}), flush=True)


# ------------------------------------------------------------------ parsing

def _ln(el):
    from lxml import etree
    return etree.QName(el).localname


def _t(el):
    if el is None:
        return None
    s = (el.text or "").strip()
    return s or None


def _num(v):
    if v in (None, "", "N/A"):
        return None
    return float(v)


def _kids(el) -> dict:
    return {_ln(c): c for c in el} if el is not None else {}


def _find(root, name):
    for el in root.iter():
        if _ln(el) == name:
            return el
    return None


CS01_BUCKETS = ("period3Mon", "period1Yr", "period5Yr", "period10Yr", "period30Yr")


def _cs01(el) -> float | None:
    """Sum of the five maturity buckets of one CS01 block. They are XML
    ATTRIBUTES of the element (measured on MQY 0001752724-22-292736), not
    children. Absent block -> None (the fund did not report it), never 0."""
    if el is None:
        return None
    vals = [_num(el.get(b)) for b in CS01_BUCKETS]
    if all(v is None for v in vals):
        raise ValueError("CS01 element present with none of the five bucket attributes")
    return sum(v for v in vals if v is not None)


def parse_doc(body: bytes, ticker: str, accession: str, filing_date) -> tuple[list[dict], dict]:
    from lxml import etree
    root = etree.fromstring(body)
    g = _kids(_find(root, "genInfo"))
    fi = _kids(_find(root, "fundInfo"))
    report_dt = _t(g.get("repPdDate"))
    if report_dt is None:
        raise ValueError(f"{ticker} {accession}: no repPdDate")
    # Part B CS01 by the fund's own IG / non-IG classification (absent for some funds)
    ig = _find(root, "creditSprdRiskInvstGrade")
    nig = _find(root, "creditSprdRiskNonInvstGrade")
    meta = {"ticker": ticker, "accession": accession, "filing_date": pd.Timestamp(filing_date),
            "report_dt": pd.Timestamp(report_dt), "rep_pd_end": _t(g.get("repPdEnd")),
            "tot_assets": _num(_t(fi.get("totAssets"))), "tot_liabs": _num(_t(fi.get("totLiabs"))),
            "net_assets": _num(_t(fi.get("netAssets"))),
            "cs01_ig": _cs01(ig), "cs01_nonig": _cs01(nig)}
    rows = []
    for sec in root.iter():
        if _ln(sec) != "invstOrSec":
            continue
        c = _kids(sec)
        d = _kids(c.get("debtSec"))
        isin = None
        for i in (c.get("identifiers") if c.get("identifiers") is not None else []):
            if _ln(i) == "isin":
                isin = i.get("value") or _t(i)
        bal, val = _num(_t(c.get("balance"))), _num(_t(c.get("valUSD")))
        units, cur = _t(c.get("units")), _t(c.get("curCd"))
        price = 100.0 * val / bal if (bal and bal > 0 and val is not None and units == "PA" and cur == "USD") else None
        rows.append({
            "ticker": ticker, "accession": accession, "report_dt": meta["report_dt"],
            "filing_date": meta["filing_date"],
            "cusip": _t(c.get("cusip")), "isin": isin, "name": _t(c.get("name")), "title": _t(c.get("title")),
            "lei": _t(c.get("lei")), "balance": bal, "units": units, "cur_cd": cur, "val_usd": val,
            "pct_val": _num(_t(c.get("pctVal"))), "asset_cat": _t(c.get("assetCat")),
            "issuer_cat": _t(c.get("issuerCat")), "inv_country": _t(c.get("invCountry")),
            "payoff": _t(c.get("payoffProfile")), "fair_val_level": _t(c.get("fairValLevel")),
            "is_restricted": _t(c.get("isRestrictedSec")),
            "maturity_dt": _t(d.get("maturityDt")), "coupon_kind": _t(d.get("couponKind")),
            "coupon": _num(_t(d.get("annualizedRt"))), "is_default": _t(d.get("isDefault")),
            "in_arrears": _t(d.get("areIntrstPmntsInArrs")), "is_pik": _t(d.get("isPaidKind")),
            "price_per_100": price,
        })
    return rows, meta


def parse() -> None:
    f = pd.read_csv(FILINGS_CSV, parse_dates=["date_filed"])
    off = EdgarClient(offline=True)
    rows, metas, missing = [], [], []
    for r in f[f.form == "NPORT-P"].itertuples():
        url = DOC_URL.format(cik=r.cik, acc=r.accession.replace("-", ""))
        try:
            body = off.get(url)
        except Exception:
            missing.append(r.accession)
            continue
        rr, m = parse_doc(body, r.ticker, r.accession, r.date_filed)
        if m["report_dt"] > LAST_REPORT_DT:
            continue                       # 2023+ holdings: outside the fit period, not read
        rows += rr
        metas.append(m)
    if missing:
        raise RuntimeError(f"{len(missing)} listed NPORT-P documents are not cached "
                           f"(run --fetch first): {missing[:5]}")
    h = pd.DataFrame(rows)
    m = pd.DataFrame(metas)
    dup = m.duplicated(["ticker", "report_dt"], keep=False)
    if dup.any():
        # two originals for one period: keep the later filing, and say so
        print(f"duplicate periods (kept latest filing): {m[dup][['ticker','report_dt','accession']].values.tolist()}")
        keep = m.sort_values("filing_date").drop_duplicates(["ticker", "report_dt"], keep="last").accession
        m = m[m.accession.isin(keep)]
        h = h[h.accession.isin(keep)]
    CACHE_OUT.mkdir(parents=True, exist_ok=True)
    h.to_parquet(HOLDINGS_PQ, index=False)
    m.to_parquet(FUNDINFO_PQ, index=False)
    print(json.dumps({"holdings_rows": int(len(h)), "fund_periods": int(len(m)),
                      "by_ticker": m.groupby("ticker").size().to_dict(),
                      "first_report_dt": str(m.report_dt.min().date()),
                      "last_report_dt": str(m.report_dt.max().date())}, indent=1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--parse", action="store_true")
    ap.add_argument("--index-census", action="store_true")
    ap.add_argument("--max-requests", type=int, default=400)
    a = ap.parse_args(argv)
    if a.index_census:
        print(json.dumps(index_census(EdgarClient(offline=True)), indent=1))
    if a.fetch:
        fetch(a.max_requests)
    if a.parse:
        parse()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
