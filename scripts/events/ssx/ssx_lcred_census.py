"""Today's Alpaca census of listed preferreds and baby bonds, mapped to issuer CIKs.

    export QUANTT_ENV_FILE=<absolute path to the env file>      # never printed
    python3 scripts/events/ssx/ssx_lcred_census.py

WHY
---
Every listed-credit idea (C1-C4, C6, C7, CR15) starts from the same question:
which exchange-listed $25-par issues can this desk trade at Alpaca today, and
who issued them. The 2026-10-15 census (`ss_credit_catalogue_counts.py
--alpaca`) answered the first half by name regex: 388 preferreds and 159 baby
bonds. Reading its rows on 2026-10-19 found false positives (foreign
preferred-share ADRs such as BBD and CIB; "Preferred Bank Common Stock") and a
known miss (NYSE ".PR" symbols whose names omit "Preferred"). The classifier in
`ssx_lcred_common.classify` fixes both and records which rule fired.

ISSUER MAPPING (needed by C2 distress counts, C3 bank tagging, C7 BDC tagging)
-----------------------------------------------------------------------------
SEC's `company_tickers_exchange.json` (cached 2026-10-12 in the shared EDGAR
cache; CIKs do not change) lists issuers' common AND many preferred tickers,
written "BAC-PK" where Alpaca writes "BAC.PRK". Three methods, tried in order,
each recorded per row:
  1. `ticker`: the issue's own ticker in SEC's file (Alpaca ".PR" -> SEC "-P").
  2. `root+name`: a symbol prefix (".PR" root, or the 4-, 3-, 2-letter prefix of
     a Nasdaq/NYSE suffix symbol) that is an SEC ticker AND whose SEC name
     shares the issuer name's first significant word. The name check is what
     stops "ABXL" mapping to whichever company owns "ABX".
  3. `name`: the normalised issuer name (text before the coupon, "Depositary",
     "Series" ...) equals an SEC name after stripping legal suffixes.
Unmatched rows stay unmatched: they are reported, never guessed. Financing
subsidiaries (e.g. "Aegon Funding Company LLC", "Qwest Corporation") have
their own CIKs and no SEC ticker, so they are expected among the misses.

Flags are true on the date of the read only (CLAUDE.md landmine 5).
ZERO TRIALS: no price, no return; one GET /v2/assets.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx.ssx_lcred_common import (OUT, REPO, EDGAR_CACHE, alpaca, alpaca_assets,
                                                 classify, tags, write_json)

SEC_TICKERS = EDGAR_CACHE / "www.sec.gov" / "files" / "company_tickers_exchange.json"
UNIVERSE_MAP = REPO / "results" / "data" / "universe_2026-10-08" / "universe_map.csv"

_CUT = re.compile(r"\s+(\d+(\.\d+)?\s?%|DEPOSITARY|SERIES\b|FIXED|FLOATING|CLASS\b|PREFERRED|PFD|"
                  r"CUMULATIVE|NON[- ]|SENIOR|SUBORDINATED|JUNIOR|NOTES?\b|PERPETUAL|TERM\b|"
                  r"VARIABLE|\(|EACH\b|\d)", re.I)
_SUFFIX = re.compile(r"\b(INCORPORATED|INC|CORPORATION|CORP|CO|COMPANY|LTD|LIMITED|LLC|L ?P|PLC|N ?V|"
                     r"S ?A|THE|DE|MD|MN|NEW|/[A-Z]{2}/)\b")
_STOP = {"THE", "FIRST", "NATIONAL", "AMERICAN", "GLOBAL", "CAPITAL", "BANK", "GROUP"}


def issuer_name(name: str) -> str:
    m = _CUT.search(name)
    s = name[:m.start()] if m else name
    return s.strip(" ,.-")


def norm(s: str) -> str:
    s = re.sub(r"/[A-Z]{2,3}/?", " ", s.upper())
    s = re.sub(r"[^A-Z0-9& ]", " ", s).replace("&", " AND ")
    s = _SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def first_word(s: str) -> str:
    w = [x for x in norm(s).split() if x not in _STOP and len(x) > 1]
    return w[0] if w else ""


def load_sec() -> pd.DataFrame:
    if not SEC_TICKERS.exists():
        raise FileNotFoundError(f"{SEC_TICKERS}: fetch https://www.sec.gov/files/company_tickers_exchange.json "
                                "through scripts/data/edgar_client.py")
    d = json.loads(SEC_TICKERS.read_text())
    if d.get("fields") != ["cik", "name", "ticker", "exchange"]:
        raise KeyError(f"{SEC_TICKERS}: unexpected fields {d.get('fields')}")
    return pd.DataFrame(d["data"], columns=d["fields"])


def map_cik(symbol: str, name: str, sec: pd.DataFrame, by_ticker: dict, by_name: dict) -> dict:
    iname = issuer_name(name)
    # 1. the issue's own ticker
    cand = [symbol.replace(".PR", "-P")] if ".PR" in symbol else [symbol]
    for t in cand:
        if t in by_ticker:
            r = by_ticker[t]
            return {"cik": int(r["cik"]), "sec_name": r["name"], "sec_ticker": t, "match": "ticker",
                    "issuer_name": iname}
    # 2. a root ticker whose SEC name agrees on the first significant word
    roots = [symbol.split(".PR")[0]] if ".PR" in symbol else [symbol[:k] for k in (4, 3, 2) if k < len(symbol)]
    fw = first_word(iname)
    for t in roots:
        if t in by_ticker and fw and first_word(by_ticker[t]["name"]) == fw:
            r = by_ticker[t]
            return {"cik": int(r["cik"]), "sec_name": r["name"], "sec_ticker": t, "match": "root+name",
                    "issuer_name": iname}
    # 3. normalised name
    n = norm(iname)
    if n in by_name:
        r = by_name[n]
        return {"cik": int(r["cik"]), "sec_name": r["name"], "sec_ticker": r["ticker"], "match": "name",
                "issuer_name": iname}
    return {"cik": None, "sec_name": None, "sec_ticker": None, "match": "unmatched", "issuer_name": iname}


def main() -> int:
    asof = dt.date.today()
    c = alpaca()
    raw = alpaca_assets(c)
    read_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    sec = load_sec()
    by_ticker = {r["ticker"]: r for r in sec.to_dict("records")}
    by_name = {}
    for r in sec.to_dict("records"):
        by_name.setdefault(norm(r["name"]), r)
    rows, rejected = [], []
    for a in raw:
        kind, rule = classify(a["symbol"], a.get("name") or "")
        if kind is None:
            if rule in ("ADR", "common stock") and re.search(r"PREFERRED", a.get("name") or "", re.I):
                rejected.append({"symbol": a["symbol"], "name": a["name"], "rule": rule})
            continue
        r = {"symbol": a["symbol"], "name": a["name"], "kind": kind, "rule": rule,
             "exchange": a.get("exchange"), "tradable": bool(a.get("tradable")),
             "shortable": bool(a.get("shortable")), "easy_to_borrow": a.get("easy_to_borrow") is True,
             "borrow_status": a.get("borrow_status"), "fractionable": bool(a.get("fractionable"))}
        r.update(tags(a["name"]))
        r.update(map_cik(a["symbol"], a["name"], sec, by_ticker, by_name))
        rows.append(r)
    df = pd.DataFrame(rows).sort_values(["kind", "symbol"])
    # BDC tag: the issuer CIK is the CIK of a BDC common in the 2026-10-08 universe map.
    u = pd.read_csv(UNIVERSE_MAP)
    if not {"symbol", "family"} <= set(u.columns):
        raise KeyError(f"{UNIVERSE_MAP}: needs symbol, family")
    bdc_syms = set(u.loc[u.family == "bdc", "symbol"])
    bdc_ciks = {int(by_ticker[s]["cik"]) for s in bdc_syms if s in by_ticker}
    df["bdc_issuer"] = df["cik"].isin(bdc_ciks)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"census_{asof.isoformat()}.csv"
    df.to_csv(p, index=False)
    pd.DataFrame(rejected).to_csv(OUT / f"census_rejected_{asof.isoformat()}.csv", index=False)

    def block(g):
        return {"n": int(len(g)), "tradable": int(g.tradable.sum()), "shortable": int(g.shortable.sum()),
                "easy_to_borrow": int(g.easy_to_borrow.sum()),
                "nyse": int((g.exchange == "NYSE").sum()), "nasdaq": int((g.exchange == "NASDAQ").sum()),
                "otc": int((g.exchange == "OTC").sum()),
                "cik_matched": int(g.cik.notna().sum()),
                "cik_match_rate": round(float(g.cik.notna().mean()), 3),
                "unique_issuers": int(g.cik.nunique()),
                "match_methods": g["match"].value_counts().to_dict(),
                "by_rule": g["rule"].value_counts().to_dict()}
    out = {"run_date": asof.isoformat(), "read_at_utc": read_at, "active_us_equity_assets": len(raw),
           "zero_trials": True, "written": str(p.relative_to(REPO)),
           "rejected_preferred_named": len(rejected),
           "bdc_commons_in_map": len(bdc_syms), "bdc_ciks_resolved": len(bdc_ciks)}
    for k, g in df.groupby("kind"):
        out[k] = block(g)
        out[k]["cumulative"] = g["cumulative"].value_counts().to_dict()
        out[k]["name_fixed_to_float"] = int(g.name_fixed_to_float.sum())
        out[k]["name_reset"] = int(g.name_reset.sum())
        out[k]["name_floating"] = int(g.name_floating.sum())
        out[k]["bdc_issuer"] = int(g.bdc_issuer.sum())
        out[k]["bdc_issuer_shortable"] = int((g.bdc_issuer & g.shortable).sum())
    out["both_kinds"] = block(df)
    # comparison with the 2026-10-15 census (same regex family, different day)
    old = REPO / "results" / "events" / "ss_catalogue_credit" / "alpaca_listed_fixed_income_2026-10-15.csv"
    if old.exists():
        o = pd.read_csv(old)
        out["vs_2026_10_15"] = {"old_rows": int(len(o)), "new_rows": int(len(df)),
                                "in_old_not_new": sorted(set(o.symbol) - set(df.symbol)),
                                "in_new_not_old_n": len(set(df.symbol) - set(o.symbol)),
                                "shortable_old": int(o.shortable.sum()), "shortable_new": int(df.shortable.sum())}
    write_json(OUT / f"census_summary_{asof.isoformat()}.json", out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
