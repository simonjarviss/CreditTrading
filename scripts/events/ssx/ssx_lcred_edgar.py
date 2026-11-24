"""EDGAR submissions for the issuers of today's listed preferreds and baby bonds.

    export QUANTT_ENV_FILE=<absolute path to the env file>         # SEC contact, never printed
    python3 scripts/events/ssx/ssx_lcred_edgar.py fetch            # live: one submissions JSON per issuer
    python3 scripts/events/ssx/ssx_lcred_edgar.py extra --max-pages 4   # live: older pages, capped
    python3 scripts/events/ssx/ssx_lcred_edgar.py table            # offline: build the filings table
    python3 scripts/events/ssx/ssx_lcred_edgar.py c2               # offline: idea C2 distress counts
    python3 scripts/events/ssx/ssx_lcred_edgar.py c3               # offline: idea C3 bank-preferred counts

WHY
---
Idea C2 asks how often the issuers of exchange-listed $25-par paper hit
distress events that 8-K items date: 2.04 (triggering events that accelerate
or increase a direct financial obligation), 1.03 (bankruptcy or receivership)
and 3.01 (notice of delisting or failure to satisfy a listing rule; NOTE: 3.01
is also filed for voluntary exchange transfers, so it overstates distress).
`data.sec.gov/submissions/CIK##########.json` carries each 8-K's `items`
field, which the quarterly master index does not. It also carries the
issuer's SIC code (idea C3 tags banks with it) and every 8-A12B and 424B
filing (ideas C1, C4 and C6 date listings and find prospectuses with them).

SURVIVORSHIP (stated, not fixed). The issuer list is built from TODAY's
Alpaca assets. An issuer whose preferreds were delisted after a bankruptcy is
in this list only if Alpaca still carries an OTC row for it (15 such rows on
2026-10-19). So per-year distress counts are a LOWER bound on the event rate
among issuers of listed $25 paper, and the bias is worst in early years.

COVERAGE. The submissions JSON's `recent` block holds about the last 1,000
filings; older filings sit in extra pages. A year an issuer's fetched pages do
not cover is ABSENT for that issuer (reported), never a zero.

Budget: EDGAR live requests go through `EdgarBudget` (1.5 s spacing, hard cap).
ZERO TRIALS: filing metadata only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx.ssx_lcred_common import CACHE, OUT, EdgarBudget, write_json

SUB_URL = "https://data.sec.gov/submissions/CIK{:010d}.json"
PAGE_URL = "https://data.sec.gov/submissions/{}"
CENSUS_DATE = "2026-10-19"
YEARS = (2015, 2025)
DISTRESS_ITEMS = ("2.04", "1.03", "3.01")
# SIC codes for banks and bank holding companies (SEC's SIC list): 6021 national
# commercial banks, 6022 state commercial banks, 6029 commercial banks NEC, 6035/6036
# savings institutions, 6111 federal credit agencies excluded. 6211 (broker-dealers:
# GS, MS, Stifel...) is reported separately because GS and MS are stress-tested BHCs.
BANK_SIC = {"6021", "6022", "6029", "6035", "6036"}
BROKER_SIC = {"6211"}


def census() -> pd.DataFrame:
    p = OUT / f"census_{CENSUS_DATE}.csv"
    if not p.exists():
        raise FileNotFoundError(f"{p}: run ssx_lcred_census.py first")
    return pd.read_csv(p)


OTC_MAP = OUT / "c2_otc_cik_map.csv"


def ciks() -> list[int]:
    c = census()
    ks = {int(x) for x in c["cik"].dropna()}
    if OTC_MAP.exists():                       # the post-default OTC rows mapped by `otc` (EDGAR name search)
        ks |= {int(x) for x in pd.read_csv(OTC_MAP).cik.dropna()}
    return sorted(ks)


def cmd_otc(args) -> None:
    """Map today's unmatched OTC rows (post-default survivors, the very issuers C2
    is about) to CIKs with EDGAR's company search. The query is the issuer name as
    Alpaca writes it, cut at the first security word; the first hit is taken only
    if it is unique or its name starts with the query, else left unmatched."""
    import re as _re
    from urllib.parse import quote_plus
    eb = EdgarBudget(offline=False)
    c = census()
    u = c[(c.exchange == "OTC") & c.cik.isna()]
    rows = []
    for r in u.itertuples():
        q = _re.split(r"\s+(DEP\b|DEPOSITARY|PFD|PREFERRED|CUM\b|CUMULATIVE|\d|NEW\b|INC NV|CALIF)", r.name, maxsplit=1,
                      flags=_re.I)[0].strip(" ,.")
        q = _re.sub(r"\b(INC|CORP|TR|N Y)\b.*$", "", q, flags=_re.I).strip(" ,.") or q
        url = ("https://www.sec.gov/cgi-bin/browse-edgar?company=" + quote_plus(q)
               + "&type=&dateb=&owner=include&count=10&action=getcompany&output=atom")
        try:
            body = eb.text(url, max_age_s=None)
        except Exception as e:
            rows.append({"symbol": r.symbol, "query": q, "cik": None, "edgar_name": None, "note": str(e)[:80]})
            continue
        ents = _re.findall(r"<cik>(\d+)</cik>.*?<name>([^<]+)</name>", body, _re.S)
        if not ents:                                   # a single-company answer has a different shape
            m1 = _re.search(r"<cik>(\d+)</cik>", body)
            n1 = _re.search(r"<conformed-name>([^<]+)</conformed-name>", body)
            ents = [(m1.group(1), n1.group(1))] if m1 and n1 else []
        pick = [e for e in ents if e[1].upper().startswith(q.upper()[:12])]
        hit = pick[0] if len(pick) >= 1 else (ents[0] if len(ents) == 1 else None)
        rows.append({"symbol": r.symbol, "query": q, "cik": int(hit[0]) if hit else None,
                     "edgar_name": hit[1] if hit else None, "n_hits": len(ents)})
    df = pd.DataFrame(rows)
    df.to_csv(OTC_MAP, index=False)
    print(df.to_string())
    for k in sorted({int(x) for x in df.cik.dropna()}):
        eb.json(SUB_URL.format(k))
    print(f"live requests {eb.live}")


def cmd_fetch(args) -> None:
    eb = EdgarBudget(offline=False)
    done = 0
    for k in ciks():
        eb.json(SUB_URL.format(k))           # cached copies are accepted: history to 2025 is immutable
        done += 1
    print(f"submissions: {done} issuers; live requests {eb.live}; cache hits {eb.client.n_cache_hits}")


def _rows(cik: int, block: dict) -> list[dict]:
    keys = ("accessionNumber", "filingDate", "form", "items", "primaryDocument", "acceptanceDateTime")
    if "form" not in block:
        raise KeyError(f"CIK {cik}: filings block has no 'form'")
    n = len(block["form"])
    return [{"cik": cik, **{k: (block.get(k) or [None] * n)[i] for k in keys}} for i in range(n)]


def cmd_extra(args) -> None:
    eb = EdgarBudget(offline=False)
    need = []
    for k in ciks():
        j = eb.json(SUB_URL.format(k))
        rec = j["filings"]["recent"]
        if not rec["filingDate"]:
            continue
        earliest = min(rec["filingDate"])
        if earliest <= f"{YEARS[0]}-01-01":
            continue
        pages = [f for f in j["filings"].get("files", []) if f["filingTo"] >= f"{YEARS[0]}-01-01"]
        pages = sorted(pages, key=lambda f: f["filingTo"], reverse=True)
        need.append((k, earliest, pages))
    print(f"issuers whose recent block starts after {YEARS[0]}-01-01: {len(need)}; "
          f"pages needed in total: {sum(len(p) for _, _, p in need)}")
    for k, earliest, pages in need:
        for f in pages[: args.max_pages]:
            eb.json(PAGE_URL.format(f["name"]))
    print(f"live requests {eb.live}; cache hits {eb.client.n_cache_hits}")


def cmd_table(args) -> None:
    eb = EdgarBudget(offline=True)
    rows, meta = [], []
    for k in ciks():
        j = eb.json(SUB_URL.format(k))
        rows += _rows(k, j["filings"]["recent"])
        got_pages, miss_pages = 0, 0
        for f in j["filings"].get("files", []):
            try:
                rows += _rows(k, eb.json(PAGE_URL.format(f["name"])))
                got_pages += 1
            except Exception as e:                      # offline miss: the page was never fetched
                if "offline and not cached" not in str(e):
                    raise
                miss_pages += 1
        meta.append({"cik": k, "name": j.get("name"), "sic": j.get("sic"), "sicDescription": j.get("sicDescription"),
                     "entityType": j.get("entityType"), "tickers": ",".join(j.get("tickers") or []),
                     "pages_fetched": got_pages, "pages_missing": miss_pages})
    df = pd.DataFrame(rows).drop_duplicates("accessionNumber")
    df["filingDate"] = pd.to_datetime(df["filingDate"]).dt.date
    m = pd.DataFrame(meta)
    # coverage: the earliest filing date each issuer's fetched pages reach
    cov = df.groupby("cik").filingDate.min().rename("earliest_fetched")
    m = m.merge(cov, left_on="cik", right_index=True, how="left")
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE / "issuer_filings.parquet", index=False)
    m.to_csv(OUT / "issuer_meta.csv", index=False)
    print(f"filings rows {len(df)}; issuers {m.shape[0]}; "
          f"issuers covered back to {YEARS[0]}-01-01: {(m.earliest_fetched <= dt.date(YEARS[0], 1, 1)).sum()}")


def _load():
    f = pd.read_parquet(CACHE / "issuer_filings.parquet")
    m = pd.read_csv(OUT / "issuer_meta.csv")
    m["earliest_fetched"] = pd.to_datetime(m["earliest_fetched"]).dt.date
    return f, m


def cmd_c2(args) -> None:
    f, m = _load()
    c = census()
    k8 = f[f.form.isin(["8-K", "8-K/A"]) & (f.form == "8-K")].copy()
    k8["year"] = pd.to_datetime(k8.filingDate).dt.year
    k8["items"] = k8["items"].fillna("")
    out = {"census_date": CENSUS_DATE, "issuers": int(m.shape[0]), "years": list(YEARS),
           "survivorship": "issuers of TODAY's Alpaca listed preferreds/baby bonds only: a lower bound",
           "per_item": {}}
    years = range(YEARS[0], YEARS[1] + 1)
    # issuer-years covered: the issuer's fetched filings reach back to Jan 1 of that year
    covered = {y: set(m.loc[m.earliest_fetched <= dt.date(y, 1, 1), "cik"]) for y in years}
    out["issuers_covered_per_year"] = {y: len(covered[y]) for y in years}
    ev_rows = []
    for it in DISTRESS_ITEMS:
        hit = k8[k8["items"].str.split(",").apply(lambda xs: it in [x.strip() for x in xs])]
        per = {}
        for y in years:
            h = hit[(hit.year == y) & hit.cik.isin(covered[y])]
            per[y] = {"filings": int(len(h)), "issuers": int(h.cik.nunique())}
        out["per_item"][it] = per
        for r in hit.itertuples():
            ev_rows.append({"cik": r.cik, "date": r.filingDate, "item": it, "accession": r.accessionNumber,
                            "all_items": r.items})
    ev = pd.DataFrame(ev_rows)
    # any distress item (2.04 or 1.03), issuer-years: the independent unit
    core = ev[ev["item"].isin(["2.04", "1.03"])].copy()
    core["year"] = pd.to_datetime(core["date"]).dt.year
    out["issuer_years_2.04_or_1.03"] = {y: int(core[(core.year == y) & core.cik.isin(covered[y])].cik.nunique())
                                        for y in years}
    s = pd.Series(out["issuer_years_2.04_or_1.03"])
    out["issuer_years_2.04_or_1.03_summary"] = {"mean": round(float(s.mean()), 1), "median": float(s.median()),
                                                "min": int(s.min()), "max": int(s.max())}
    # cumulative vs non-cumulative: share of today's issues per issuer kind
    ev = ev.merge(m[["cik", "name", "sic"]], on="cik", how="left")
    cum = c.groupby("cik").cumulative.agg(lambda x: ",".join(sorted(set(x))))
    ev["issuer_issue_cumulative"] = ev.cik.map(cum)
    ev.to_csv(OUT / "c2_distress_8k_events.csv", index=False)
    # issuers of today's OTC rows (post-default survivors in Alpaca's list)
    otc = c[c.exchange == "OTC"]
    out["otc_rows_today"] = {"n": int(len(otc)), "symbols": sorted(otc.symbol)}
    out["cumulative_mix_today"] = c.groupby("kind").cumulative.value_counts().unstack(fill_value=0).to_dict(orient="index")
    write_json(OUT / "c2_summary.json", out)
    print(json.dumps(out, indent=1, default=str))


def cmd_c3(args) -> None:
    f, m = _load()
    c = census()
    c = c.merge(m[["cik", "sic", "sicDescription", "name"]].rename(columns={"name": "edgar_name"}),
                on="cik", how="left")
    c["sic"] = c["sic"].astype("Int64").astype(str)
    bank = c[c.sic.isin(BANK_SIC)]
    brok = c[c.sic.isin(BROKER_SIC)]
    out = {"census_date": CENSUS_DATE}
    for lab, g in (("bank_sic_6021_6022_6029_6035_6036", bank), ("broker_sic_6211", brok)):
        out[lab] = {"issues": int(len(g)), "preferred": int((g.kind == "preferred").sum()),
                    "baby_bond": int((g.kind == "baby_bond").sum()), "tradable": int(g.tradable.sum()),
                    "shortable": int(g.shortable.sum()), "issuers": int(g.cik.nunique()),
                    "issuers_list": sorted(g.edgar_name.dropna().unique().tolist()),
                    "name_fixed_to_float": int(g.name_fixed_to_float.sum()),
                    "name_reset": int(g.name_reset.sum()), "name_floating": int(g.name_floating.sum()),
                    "non_cumulative": int((g.cumulative == "non_cumulative").sum())}
    c[c.sic.isin(BANK_SIC | BROKER_SIC)].to_csv(OUT / "c3_bank_issues.csv", index=False)
    out["sic_mix_top15"] = c.groupby("sicDescription").size().sort_values(ascending=False).head(15).to_dict()
    write_json(OUT / "c3_bank_summary.json", out)
    print(json.dumps(out, indent=1, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("fetch")
    sp.add_parser("otc")
    e = sp.add_parser("extra")
    e.add_argument("--max-pages", type=int, default=4)
    sp.add_parser("table")
    sp.add_parser("c2")
    sp.add_parser("c3")
    a = ap.parse_args(argv)
    {"fetch": cmd_fetch, "otc": cmd_otc, "extra": cmd_extra, "table": cmd_table, "c2": cmd_c2, "c3": cmd_c3}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
