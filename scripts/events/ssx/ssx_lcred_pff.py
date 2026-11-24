"""CR15 gate: PFF's constituent additions per quarter (N-PORT-P, 2019-2022), in days of the issue's ADV.

    export QUANTT_ENV_FILE=<absolute path to the env file>       # SEC contact + Alpaca keys, never printed
    python3 scripts/events/ssx/ssx_lcred_pff.py fetch            # live EDGAR: series id, filing list, XMLs
    python3 scripts/events/ssx/ssx_lcred_pff.py additions        # offline: parse and diff snapshots
    python3 scripts/events/ssx/ssx_lcred_pff.py adv              # Alpaca volume bars (pre-2023), days of ADV

WHY (catalogue CR15, `SPECIAL_SITUATIONS_CATALOGUE_CREDIT_2026-10-15.md` §4.7)
---------------------------------------------------------------------------
The CR15 mechanism is index demand: PFF and its peers must buy an issue when
their index adds it, and thin $25-par issues cannot absorb that without a
concession. The gate that can kill it at zero trials is arithmetic: how many
additions a year, and how big each is against the issue's own trading. If
fewer than 30 additions a year, or the median addition is under one day of the
issue's ADV, there is no forced flow worth a trade.

HOW
---
* PFF files N-PORT-P per series; the PUBLIC part holds one month-end snapshot
  per fiscal quarter (the archived `pre-clean-slate:scripts/nport/fetch_nport.py`
  measured this). An "addition" is a security (CUSIP, else ISIN) present in a
  snapshot and absent from the previous one. Quarterly snapshots miss anything
  added and removed inside one quarter, so the count is a lower bound.
* PFF tracked the ICE transition index (PHGX) through 2019-10-31, which moved
  10% a month from PHGL to PHGY (ICE Rules & Methodology, 2021-12-26 copy). 2019
  additions therefore include transition buying, and are reported apart from
  2020-2022.
* ADV: Alpaca daily SIP volume, VOLUME ONLY, ending before 2023. The issue is
  mapped to today's Alpaca symbol by ticker if N-PORT carries one, else by
  issuer CIK-free name and coupon match to today's census. Issues called before
  today have no Alpaca symbol in today's list: they are reported as unmapped
  (survivorship), never guessed.
* Pre-event window: the 20 sessions ending on the previous snapshot date (the
  addition happened at one of the three month-ends after it). If the issue
  started trading inside the quarter, the window is its first <= 20 sessions up
  to the snapshot date, flagged `in_quarter_listing` (not strictly pre-event).

ZERO TRIALS: holdings and volume only; no price, no return.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx.ssx_lcred_common import (CACHE, OUT, EdgarBudget, alpaca, alpaca_volume_bars,
                                                 write_json)

MF_URL = "https://www.sec.gov/files/company_tickers_mf.json"
FEED = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={sid}&type=NPORT-P"
        "&dateb=&owner=include&count=100&start={start}&output=atom")
DOC = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/primary_doc.xml"
WINDOW = (dt.date(2018, 12, 31), dt.date(2022, 12, 31))
CENSUS = OUT / "census_2026-10-19.csv"


def _series(eb) -> tuple[int, str]:
    mf = eb.json(MF_URL)
    f = mf["fields"]
    rows = [dict(zip(f, r)) for r in mf["data"] if r[f.index("symbol")] == "PFF"]
    if len(rows) != 1:
        raise KeyError(f"PFF: {len(rows)} rows in company_tickers_mf.json")
    return int(rows[0]["cik"]), rows[0]["seriesId"]


def _filings(eb, sid) -> list[dict]:
    out = []
    for start in range(0, 1000, 100):
        body = eb.text(FEED.format(sid=sid, start=start), max_age_s=86400)
        ents = re.findall(r"<entry>(.*?)</entry>", body, re.S)
        for e in ents:
            acc = re.search(r"<accession-number>([\d-]+)</accession-number>", e)
            fdt = re.search(r"<filing-date>([\d-]+)</filing-date>", e)
            typ = re.search(r"<filing-type>([^<]+)</filing-type>", e)
            if acc and fdt:
                out.append({"accession": acc.group(1), "filing_date": fdt.group(1),
                            "form": typ.group(1) if typ else None})
        if len(ents) < 100:
            break
    return out


def cmd_fetch(args) -> None:
    eb = EdgarBudget(offline=args.offline)
    cik, sid = _series(eb)
    fl = _filings(eb, sid)
    print(f"PFF cik {cik} series {sid}: {len(fl)} NPORT-P filings listed")
    got = 0
    for f in fl:
        d = dt.date.fromisoformat(f["filing_date"])
        # a quarter's NPORT-P is filed within ~60 days of its report date
        if not (WINDOW[0] < d <= WINDOW[1] + dt.timedelta(days=75)):
            continue
        eb.text(DOC.format(cik=cik, acc=f["accession"].replace("-", "")))
        got += 1
    write_json(CACHE / "pff_filings.json", {"cik": cik, "series": sid, "filings": fl})
    print(f"documents in window: {got}; live requests {eb.live}")


def _strip(tag: str) -> str:
    return tag.split("}", 1)[-1]


def parse_doc(xml: str) -> tuple[dt.date, pd.DataFrame]:
    root = ET.fromstring(xml)
    rep = None
    for el in root.iter():
        if _strip(el.tag) == "repPdDate":
            rep = dt.date.fromisoformat(el.text.strip())
            break
    if rep is None:
        raise ValueError("no repPdDate")
    rows = []
    for sec in root.iter():
        if _strip(sec.tag) != "invstOrSec":
            continue
        r = {}
        for ch in sec:
            t = _strip(ch.tag)
            if t in ("name", "lei", "title", "cusip", "balance", "units", "valUSD", "pctVal", "assetCat",
                     "issuerCat", "invCountry"):
                r[t] = (ch.text or "").strip()
            elif t == "identifiers":
                for idn in ch:
                    it = _strip(idn.tag)
                    if it == "isin":
                        r["isin"] = idn.attrib.get("value")
                    elif it == "ticker":
                        r["ticker"] = idn.attrib.get("value")
                    elif it == "other":
                        r.setdefault("other_id", idn.attrib.get("value"))
            elif t == "debtSec":
                for d in ch:
                    if _strip(d.tag) in ("maturityDt", "couponKind", "annualizedRt"):
                        r[_strip(d.tag)] = (d.text or "").strip()
        rows.append(r)
    df = pd.DataFrame(rows)
    for c in ("balance", "valUSD", "pctVal"):
        df[c] = pd.to_numeric(df[c], errors="raise")
    df["key"] = df["cusip"].where(df["cusip"].str.fullmatch(r"[0-9A-Z]{9}") & (df["cusip"] != "000000000"),
                                  df.get("isin"))
    return rep, df


def cmd_additions(args) -> None:
    eb = EdgarBudget(offline=True)
    meta = json.loads((CACHE / "pff_filings.json").read_text())
    snaps = {}
    for f in meta["filings"]:
        d = dt.date.fromisoformat(f["filing_date"])
        if not (WINDOW[0] < d <= WINDOW[1] + dt.timedelta(days=75)):
            continue
        rep, df = parse_doc(eb.text(DOC.format(cik=meta["cik"], acc=f["accession"].replace("-", ""))))
        # an amendment (NPORT-P/A) for the same date replaces the original: keep the last filed
        if rep not in snaps or f["filing_date"] > snaps[rep][0]:
            snaps[rep] = (f["filing_date"], df)
    dates = sorted(d for d in snaps if WINDOW[0] <= d <= WINDOW[1])
    if not dates:
        raise RuntimeError("no snapshots in window")
    allrows, per = [], []
    for i, d in enumerate(dates):
        df = snaps[d][1]
        sec = df[~df["assetCat"].isin(["STIV"]) & df["key"].notna()]
        sec = sec[~sec["name"].str.contains("BLACKROCK CASH|BLK CSH|TREASURY TRUST", case=False, na=False)]
        sec = sec.assign(rep=d)
        allrows.append(sec)
        if i == 0:
            per.append({"rep": d, "holdings": len(sec), "added": None, "removed": None})
            continue
        prev = allrows[i - 1]
        add = sec[~sec.key.isin(prev.key)]
        rem = prev[~prev.key.isin(sec.key)]
        per.append({"rep": d, "prev": dates[i - 1], "holdings": len(sec), "added": len(add), "removed": len(rem),
                    "added_val_pct": round(float(add.pctVal.sum()), 3)})
    hold = pd.concat(allrows, ignore_index=True)
    hold.to_parquet(CACHE / "pff_holdings.parquet", index=False)
    per = pd.DataFrame(per)
    per.to_csv(OUT / "cr15_pff_additions_per_quarter.csv", index=False)
    first = hold.sort_values("rep").drop_duplicates("key")
    first = first[first.rep > dates[0]]
    first.to_csv(OUT / "cr15_pff_additions.csv", index=False)
    per["year"] = pd.to_datetime(per.rep).dt.year
    out = {"snapshots": [str(d) for d in dates], "n_snapshots": len(dates),
           "additions_per_year": per.groupby("year").added.sum().to_dict(),
           "removals_per_year": per.groupby("year").removed.sum().to_dict(),
           "holdings_range": [int(per.holdings.min()), int(per.holdings.max())],
           "asset_cats_of_additions": first.assetCat.value_counts().to_dict(),
           "has_ticker_identifier": int(first.get("ticker", pd.Series(dtype=str)).notna().sum()),
           "additions_total": int(len(first))}
    write_json(OUT / "cr15_pff_summary.json", out)
    print(json.dumps(out, indent=1, default=str))


_COUP = re.compile(r"(\d+\.\d+|\d+)\s*%?")


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _match(add: pd.DataFrame, cen: pd.DataFrame) -> pd.Series:
    """Map an N-PORT holding to today's Alpaca symbol. Ticker identifier first;
    else the issuer's first word plus the coupon in the N-PORT title must both
    appear in exactly one census name. Ambiguity is left unmapped."""
    out = {}
    cen = cen.assign(u=cen["name"].str.upper())
    for r in add.itertuples():
        t = getattr(r, "ticker", None)
        if isinstance(t, str) and t:
            tt = t.replace("-", ".PR").replace(" ", "")
            hit = cen[cen.symbol.isin([t, tt, t.replace("-P", ".PR")])]
            if len(hit) == 1:
                out[r.Index] = (hit.symbol.iloc[0], "ticker")
                continue
        title = f"{r.title} {r.name}".upper()
        cp = re.findall(r"(\d+\.\d{2,3})", title)
        w = [x for x in re.findall(r"[A-Z]{3,}", str(r.name).upper())
             if x not in ("THE", "INC", "CORP", "GROUP", "HOLDINGS", "FINANCIAL", "CAPITAL", "BANK", "COMPANY")]
        if not cp or not w:
            continue
        cand = cen[cen.u.str.contains(w[0], regex=False)]
        cand = cand[cand.u.str.contains("|".join(re.escape(c.rstrip("0").rstrip(".")) for c in cp))]
        if len(cand) == 1:
            out[r.Index] = (cand.symbol.iloc[0], "name+coupon")
    return pd.Series(out, dtype=object)


def cmd_adv(args) -> None:
    add = pd.read_csv(OUT / "cr15_pff_additions.csv")
    add["rep"] = pd.to_datetime(add["rep"]).dt.date
    per = pd.read_csv(OUT / "cr15_pff_additions_per_quarter.csv")
    prev_of = {dt.date.fromisoformat(r.rep): dt.date.fromisoformat(r.prev)
               for r in per.itertuples() if isinstance(r.prev, str)}
    cen = pd.read_csv(CENSUS)
    m = _match(add, cen)
    add["symbol"] = [m.get(i, (None, None))[0] for i in add.index]
    add["map"] = [m.get(i, (None, "unmapped"))[1] for i in add.index]
    # volume from the shared pre-2023 cache written by ssx_lcred_volume.py (volume only)
    bars = pd.read_parquet(CACHE / "volume_daily_2016_2022.parquet")
    rows = []
    for r in add.itertuples():
        if not isinstance(r.symbol, str):
            continue
        b = bars[bars.symbol == r.symbol].sort_values("t")
        prev = prev_of[r.rep]
        pre = b[b.t <= prev].tail(20)
        flag = "pre_event"
        if len(pre) < 10:
            pre = b[b.t <= r.rep].head(20)
            flag = "in_quarter_listing"
        if pre.empty:
            rows.append({"key": r.key, "symbol": r.symbol, "rep": r.rep, "flag": "no_bars"})
            continue
        adv = float(pre.v.mean())
        first_bar = b.t.min()
        rows.append({"key": r.key, "symbol": r.symbol, "rep": r.rep, "flag": flag, "pff_shares": r.balance,
                     "units": r.units, "adv_shares": adv, "adv_sessions": len(pre),
                     "days_of_adv": r.balance / adv if adv > 0 else None, "first_bar": first_bar,
                     "new_issue_le_95d": (r.rep - first_bar).days <= 95 if first_bar else None})
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "cr15_pff_additions_adv.csv", index=False)
    ok = res[res.days_of_adv.notna()]
    out = {"additions": int(len(add)), "mapped_to_alpaca_symbol": int(add.symbol.notna().sum()),
           "map_methods": add["map"].value_counts().to_dict(),
           "with_volume": int(len(ok)),
           "days_of_adv_median_all": round(float(ok.days_of_adv.median()), 2) if len(ok) else None,
           "days_of_adv_quartiles_all": [round(float(x), 2) for x in ok.days_of_adv.quantile([.25, .5, .75])] if len(ok) else None,
           "share_ge_1_day": round(float((ok.days_of_adv >= 1).mean()), 3) if len(ok) else None,
           "by_flag": {k: {"n": int(len(g)), "median_days_of_adv": round(float(g.days_of_adv.median()), 2)}
                       for k, g in ok.groupby("flag")},
           "new_issue_share": round(float(ok.new_issue_le_95d.mean()), 3) if len(ok) else None,
           "by_year": {int(k): {"n": int(len(g)), "median_days_of_adv": round(float(g.days_of_adv.median()), 2)}
                       for k, g in ok.groupby(pd.to_datetime(ok.rep).dt.year)}}
    write_json(OUT / "cr15_pff_adv_summary.json", out)
    print(json.dumps(out, indent=1, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("fetch")
    f.add_argument("--offline", action="store_true")
    sp.add_parser("additions")
    sp.add_parser("adv")
    a = ap.parse_args(argv)
    {"fetch": cmd_fetch, "additions": cmd_additions, "adv": cmd_adv}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
