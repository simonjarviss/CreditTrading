"""C1 census: new exchange-listed $25-par issues per year (2015-2025), the pricing-to-listing gap,
first-month volume, and whether the pre-listing (grey-market) leg is reachable at Alpaca.

    python3 scripts/events/ssx/ssx_lcred_newissue.py candidates            # offline: EDGAR master index
    export QUANTT_ENV_FILE=<absolute path to the env file>                 # never printed
    python3 scripts/events/ssx/ssx_lcred_newissue.py sample --per-year 8   # live EDGAR: classify a sample
    python3 scripts/events/ssx/ssx_lcred_newissue.py estimate              # offline: counts, recall, gaps
    python3 scripts/events/ssx/ssx_lcred_newissue.py grey                  # live EDGAR + Alpaca: today's window

THE METHOD, AND ITS RECALL (stated because the count rests on it)
----------------------------------------------------------------
A new exchange-listed preferred or baby bond is a new class of security, so
its issuer must register it under Exchange Act s.12(b): Form 8-A12B. The
quarterly master index lists every 8-A12B with filer and date, offline. Most
8-A12Bs are not $25 paper -- ETFs (each new fund), SPAC units/warrants, IPO
common, exchange transfers -- so the candidate rule is:

  an 8-A12B by a filer that never files 485BPOS/485APOS/497K (open-end funds
  and ETFs), whose name is not a SPAC's, and which filed a 424B2 or 424B5
  (a shelf takedown) in the 45 days up to and including the 8-A12B date.

Precision: a stratified sample of candidates is read (the 8-A12B text names
the class: "Depositary Shares ... Preferred", "% Notes due ...") and the
per-year count is candidates x sample precision, with a Wilson interval.
Recall: measured on today's SURVIVORS -- issues in the 2026-10-19 census whose
first Alpaca bar falls in 2016-03..2022-12 -- as the share whose issuer has a
candidate 8-A12B within [-20, +10] days of that first bar. Survivor recall is
not population recall (called issues are absent), so it is labelled.

The pricing-to-listing gap is measured twice and both are reported:
  (a) 424B filing date -> 8-A12B filing date, for every candidate (registration
      gap; a 424B2/B5 is filed within two business days of pricing, Rule 424(b));
  (b) 424B filing date -> first Alpaca SIP bar (first exchange trade), for
      survivors in 2016-03..2022-12.

ZERO TRIALS: filing metadata, filing text and volume. No price, no return.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx.ssx_lcred_common import (CACHE, OUT, EdgarBudget, accession_from_filename,
                                                 master_range, write_json)
from scripts.data.edgar_client import filing_txt_url

YEARS = (2015, 2025)
LOOKBACK = 45
FUND_FORMS = ("485BPOS", "485APOS", "497K", "485BXT")
SPAC_RE = re.compile(r"ACQUISITION|MERGER (CORP|SUB)|\bSPAC\b|BLANK CHECK", re.I)
SEED = 20261019

PREF_TXT = re.compile(r"DEPOSITARY SHARES|PREFERRED|PREFERENCE SHARES|TRUST PREFERRED|PREFERRED UNITS", re.I)
NOTE_TXT = re.compile(r"\d\s*%\s*(SENIOR |SUBORDINATED |JUNIOR SUBORDINATED |FIXED[- ]RATE |FIXED[- ]TO[- ]FLOATING RATE )*"
                      r"(NOTES|DEBENTURES)\s+DUE|NOTES\s+DUE\s+\d{4}|DEBENTURES\s+DUE\s+\d{4}", re.I)
COMMON_TXT = re.compile(r"COMMON STOCK|ORDINARY SHARES|COMMON SHARES|CLASS A SHARES|COMMON UNITS", re.I)
WARR_TXT = re.compile(r"WARRANTS?|RIGHTS\b", re.I)
PAR25_TXT = re.compile(r"\$\s?25(\.00)?\s+(PER|LIQUIDATION|PRINCIPAL)|LIQUIDATION PREFERENCE OF \$\s?25\b|"
                       r"\$25\.00 PER DEPOSITARY|DENOMINATIONS OF \$25\b|\$\s?25 LIQUIDATION", re.I)


def cmd_candidates(args) -> None:
    m = master_range(YEARS[0] - 1, YEARS[1], ("8-A12B", "8-A12B/A", "424B2", "424B5") + FUND_FORMS)
    fund_ciks = set(m.loc[m.form.isin(FUND_FORMS), "cik"])
    a = m[(m.form == "8-A12B") & (pd.to_datetime(m.date).dt.year.between(*YEARS))].copy()
    a["fund"] = a.cik.isin(fund_ciks)
    a["spac"] = a.company.str.contains(SPAC_RE)
    b = m[m.form.isin(["424B2", "424B5"])][["cik", "date", "form", "filename"]]
    b = b.rename(columns={"date": "b_date", "form": "b_form", "filename": "b_file"})
    j = a[~a.fund & ~a.spac].merge(b, on="cik", how="left")
    j["gap"] = (pd.to_datetime(j.date) - pd.to_datetime(j.b_date)).dt.days
    j = j[(j.gap >= 0) & (j.gap <= LOOKBACK)]
    # the nearest preceding 424B for each 8-A12B
    j = j.sort_values("gap").drop_duplicates("filename")
    a["candidate"] = a.filename.isin(j.filename)
    a = a.merge(j[["filename", "b_date", "b_form", "b_file", "gap"]], on="filename", how="left")
    a["year"] = pd.to_datetime(a.date).dt.year
    CACHE.mkdir(parents=True, exist_ok=True)
    a.to_parquet(CACHE / "c1_8a12b.parquet", index=False)
    per = a.groupby("year").agg(all_8a12b=("filename", "size"), fund=("fund", "sum"), spac=("spac", "sum"),
                                candidates=("candidate", "sum"))
    out = {"years": list(YEARS), "lookback_days": LOOKBACK, "per_year": per.to_dict(orient="index"),
           "candidate_gap_days_median": float(a.loc[a.candidate, "gap"].median()),
           "candidate_gap_days_quartiles": [float(x) for x in a.loc[a.candidate, "gap"].quantile([.25, .5, .75])],
           "candidate_unique_issuers_per_year": a[a.candidate].groupby("year").cik.nunique().to_dict()}
    write_json(OUT / "c1_candidates_summary.json", out)
    print(json.dumps(out, indent=1, default=str))


def classify_8a(txt: str) -> dict:
    # the class title sits in the first part of the form ("Title of each class to be so registered")
    head = re.sub(r"<[^>]+>", " ", txt)
    head = re.sub(r"&#\d+;|&nbsp;|&amp;", " ", head)
    head = re.sub(r"\s+", " ", head)
    i = head.upper().find("TITLE OF EACH CLASS")
    seg = head[i: i + 1500] if i >= 0 else head[:6000]
    kind = ("preferred" if PREF_TXT.search(seg) else "baby_bond" if NOTE_TXT.search(seg)
            else "warrant_or_right" if WARR_TXT.search(seg) and not COMMON_TXT.search(seg)
            else "common" if COMMON_TXT.search(seg) else "other")
    return {"kind": kind, "par25": bool(PAR25_TXT.search(head[:60000])), "title_found": i >= 0,
            "title_snippet": seg[:220]}


def cmd_sample(args) -> None:
    a = pd.read_parquet(CACHE / "c1_8a12b.parquet")
    cand = a[a.candidate]
    rng = random.Random(SEED)
    picks = []
    for y, g in cand.groupby("year"):
        idx = list(g.index)
        rng.shuffle(idx)
        picks += idx[: args.per_year]
    eb = EdgarBudget(offline=args.offline)
    rows = []
    for i in picks:
        r = a.loc[i]
        acc = accession_from_filename(r.filename)
        txt = eb.text(filing_txt_url(int(r.cik), acc))
        rows.append({"filename": r.filename, "cik": int(r.cik), "company": r.company, "date": r.date,
                     "year": int(r.year), **classify_8a(txt)})
    s = pd.DataFrame(rows)
    s.to_csv(OUT / "c1_sample_classified.csv", index=False)
    print(s.groupby("year").kind.value_counts().unstack(fill_value=0))
    print(f"live requests {eb.live}")


DENOM25 = re.compile(r"denominations of \$\s?25(\.00)?\b|\$25(\.00)? principal amount|\$25(\.00)? per note|"
                     r"integral multiples of \$25(\.00)?\b|\$25(\.00)? (per share )?liquidation preference|"
                     r"liquidation preference of \$25|\$25\.00 per depositary share|\$25 per depositary share", re.I)
DENOM_INST = re.compile(r"denominations of (\$|U\.S\.\$|US\$)\s?(1,000|2,000|5,000|100,000|200,000)|"
                        r"denominations of (€|EUR|£|GBP)|minimum denominations of €|€\s?100,000", re.I)
CONV_ETN = re.compile(r"CONVERTIBLE|\bETN\b|ETRACS|X-LINKS|EXCHANGE[- ]TRADED NOTES|MEDIUM-TERM", re.I)


def cmd_adjudicate(args) -> None:
    """Read the matched 424B of every sampled 8-A12B and decide whether the issue is
    retail $25 paper. Preferreds: any non-convertible preferred/depositary share
    whose 424B states a $25 per-share (or per-depositary-share) amount. Notes: the
    424B must state $25 denominations. A 424B that never mentions the 8-A12B's
    coupon is a mismatch (the nearest 424B was another deal) and is reported."""
    a = pd.read_parquet(CACHE / "c1_8a12b.parquet").set_index("filename")
    s = pd.read_csv(OUT / "c1_sample_classified.csv")
    eb = EdgarBudget(offline=args.offline)
    out = []
    for r in s.itertuples():
        row = a.loc[r.filename]
        rec = {"filename": r.filename, "year": r.year, "company": r.company, "kind8a": r.kind}
        if CONV_ETN.search(r.title_snippet or "") or r.kind in ("common", "warrant_or_right"):
            rec.update({"retail25": False, "why": "convertible/ETN/MTN/common/warrant by 8-A title"})
            out.append(rec)
            continue
        if not isinstance(row.b_file, str):
            rec.update({"retail25": None, "why": "no 424B"})
            out.append(rec)
            continue
        txt = eb.text(filing_txt_url(int(r.cik), accession_from_filename(row.b_file)))
        t = re.sub(r"<[^>]+>", " ", txt)
        t = re.sub(r"&#\d+;|&nbsp;|&amp;", " ", t)
        cp = re.findall(r"(\d+\.\d{2,3})\s*%", r.title_snippet or "")
        coupon_seen = (not cp) or any(c in t for c in cp)
        d25 = bool(DENOM25.search(t))
        dinst = bool(DENOM_INST.search(t))
        rec.update({"coupon_in_424b": coupon_seen, "denom25": d25, "denom_inst": dinst,
                    "retail25": bool(coupon_seen and d25 and not (dinst and r.kind == "baby_bond" and not d25)),
                    "why": "424B text"})
        out.append(rec)
    o = pd.DataFrame(out)
    o.to_csv(OUT / "c1_sample_adjudicated.csv", index=False)
    print(o.groupby(["year"]).retail25.agg(["size", "sum"]))
    print(o.groupby(["kind8a"]).retail25.agg(["size", "sum"]))
    print(f"live requests {eb.live}")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def cmd_estimate(args) -> None:
    a = pd.read_parquet(CACHE / "c1_8a12b.parquet")
    s = pd.read_csv(OUT / "c1_sample_adjudicated.csv")
    s["hit"] = s.retail25.fillna(False).astype(bool)
    s["kind"] = s["kind8a"]
    per = a[a.candidate].groupby("year").size().rename("candidates").to_frame()
    pr = s.groupby("year").agg(n=("hit", "size"), k=("hit", "sum"))
    per = per.join(pr)
    k_all, n_all = int(s.hit.sum()), int(len(s))
    p_pool = k_all / n_all
    per["est_pooled_precision"] = (per.candidates * p_pool).round(0)
    per["est_lo"] = (per.candidates * wilson(k_all, n_all)[0]).round(0)
    per["est_hi"] = (per.candidates * wilson(k_all, n_all)[1]).round(0)
    out = {"sample_n": n_all, "sample_hits": k_all, "pooled_precision": round(p_pool, 3),
           "pooled_precision_wilson95": wilson(k_all, n_all),
           "sample_kinds": s.kind.value_counts().to_dict(),
           "sample_hits_by_8a_kind": s[s.hit].kind.value_counts().to_dict(),
           "sample_coupon_mismatch": int((s.get("coupon_in_424b") == False).sum()),
           "per_year": per.to_dict(orient="index")}
    # recall on survivors and gap (b), from the volume cache
    vp = OUT / "volume_per_symbol_2016_2022.csv"
    cen = pd.read_csv(OUT / "census_2026-10-19.csv")
    if vp.exists():
        v = pd.read_csv(vp, parse_dates=["first_bar"])
        v = v.merge(cen[["symbol", "cik"]], on="symbol", how="left")
        v = v[(~v.censored_left) & (v.first_bar >= "2016-03-01") & v.cik.notna()]
        c8 = a[a.candidate][["cik", "date", "b_date", "b_form"]].copy()
        c8["date"] = pd.to_datetime(c8.date)
        c8["b_date"] = pd.to_datetime(c8.b_date)
        hits, gaps_b, gaps_list = 0, [], []
        allc8 = a[["cik", "date"]].copy()
        allc8["date"] = pd.to_datetime(allc8.date)
        any8 = 0
        for r in v.itertuples():
            w = c8[(c8.cik == int(r.cik)) & ((c8.date - r.first_bar).dt.days.between(-20, 10))]
            w_any = allc8[(allc8.cik == int(r.cik)) & ((allc8.date - r.first_bar).dt.days.between(-20, 10))]
            any8 += int(len(w_any) > 0)
            if len(w):
                hits += 1
                g = w.iloc[(w.date - r.first_bar).abs().argsort()].iloc[0]
                gaps_b.append((r.first_bar - g.b_date).days)
                gaps_list.append((r.first_bar - g.date).days)
        out["recall_on_survivors"] = {"survivors_first_bar_2016_03_to_2022_12": int(len(v)),
                                      "with_candidate_8a12b": hits,
                                      "recall": round(hits / len(v), 3) if len(v) else None,
                                      "with_any_8a12b_same_window": any8}
        if gaps_b:
            sb = pd.Series(gaps_b)
            out["gap_424b_to_first_exchange_bar_days"] = {"n": int(len(sb)), "median": float(sb.median()),
                                                          "quartiles": [float(x) for x in sb.quantile([.25, .5, .75])],
                                                          "share_gt_5d": round(float((sb > 5).mean()), 3)}
            sl = pd.Series(gaps_list)
            out["gap_8a12b_to_first_exchange_bar_days"] = {"median": float(sl.median()),
                                                           "quartiles": [float(x) for x in sl.quantile([.25, .5, .75])]}
    cg = a[a.candidate].gap
    out["gap_424b_to_8a12b_days_candidates"] = {"n": int(len(cg)), "median": float(cg.median()),
                                                "quartiles": [float(x) for x in cg.quantile([.25, .5, .75])]}
    write_json(OUT / "c1_estimate.json", out)
    print(json.dumps(out, indent=1, default=str))


def cmd_grey(args) -> None:
    """Today's pre-listing window, tested directly.

    1. From the current-quarter master index (fetched fresh), take 424B2/424B5
       shelf takedowns filed in the last `--days` days by issuers of today's
       listed $25 paper (the census CIKs), excluding structured-note factories
       (issuers with more than 50 424B2s in 2026Q3).
    2. Read each prospectus: is it a $25 issue that the issuer intends to list,
       and has its 8-A12B been filed yet? Priced and not yet registered on an
       exchange = in the pre-listing (grey-market) window today.
    3. Search Alpaca's ACTIVE and INACTIVE asset lists for any asset carrying
       that issuer's name and that coupon. None = the leg is unreachable at
       Alpaca for that issue."""
    import gzip
    from scripts.events.ssx.ssx_lcred_common import alpaca, alpaca_assets
    from quantt.broker.alpaca import PAPER_BASE
    eb = EdgarBudget(offline=False)
    cur = eb.text("https://www.sec.gov/Archives/edgar/full-index/2026/QTR4/master.idx", max_age_s=3600)
    rows = [l.split("|") for l in cur.splitlines() if l.count("|") == 4 and l[:1].isdigit()]
    q4 = pd.DataFrame(rows, columns=["cik", "company", "form", "date", "filename"])
    q3p = (CACHE.parent.parent / "_cache_edgar" / "www.sec.gov" / "Archives" / "edgar" / "full-index" / "2026"
           / "QTR3" / "master.gz")
    t3 = gzip.decompress(q3p.read_bytes()).decode("latin-1")
    q3 = pd.DataFrame([l.split("|") for l in t3.splitlines() if l.count("|") == 4 and l[:1].isdigit()],
                      columns=q4.columns)
    for q in (q3, q4):
        q["cik"] = q.cik.astype(int)
        q["date"] = pd.to_datetime(q.date)
    last = q4.date.max()
    cen = pd.read_csv(OUT / "census_2026-10-19.csv")
    issuers = {int(x) for x in cen.cik.dropna()}
    factory = q3[q3.form == "424B2"].groupby("cik").size()
    factory = set(factory[factory > 50].index)
    b = q4[q4.form.isin(["424B2", "424B5"]) & q4.cik.isin(issuers) & ~q4.cik.isin(factory)
           & (q4.date >= last - pd.Timedelta(days=args.days))]
    a8 = q4[q4.form == "8-A12B"]
    out = {"index_last_date": str(last.date()), "window_days": args.days,
           "takedowns_by_census_issuers_in_window": int(len(b)), "structured_note_factories_excluded": len(factory)}
    recs = []
    for r in b.head(args.max_docs).itertuples():
        txt = eb.text(filing_txt_url(int(r.cik), accession_from_filename(r.filename)))
        t = re.sub(r"<[^>]+>", " ", txt)
        t = re.sub(r"&#\d+;|&nbsp;|&amp;", " ", t)
        t = re.sub(r"\s+", " ", t)
        d25 = bool(DENOM25.search(t))
        lst = re.search(r"(apply|applied|application) to list[^.]{0,200}(New York Stock Exchange|NYSE|Nasdaq)", t, re.I)
        within = re.search(r"trading[^.]{0,80}within (\d+|thirty|30) (business )?days", t, re.I)
        cps = re.findall(r"(\d{1,2}\.\d{2,3})\s*%", t[:20000])
        cp = max(set(cps), key=cps.count) if cps else None
        a8_after = a8[(a8.cik == r.cik) & (a8.date >= r.date)]
        recs.append({"company": r.company, "cik": int(r.cik), "form": r.form, "date": str(r.date.date()),
                     "denom25": d25, "intends_to_list": bool(lst), "within_n_days_clause": bool(within),
                     "coupon_mode": cp, "a8_filed_since": int(len(a8_after))})
    rec = pd.DataFrame(recs)
    c = alpaca()
    act = alpaca_assets(c)
    ina = c._get(PAPER_BASE, "/v2/assets", {"status": "inactive", "asset_class": "us_equity"})
    allassets = act + (ina if isinstance(ina, list) else [])
    hits = []
    for r in rec.itertuples():
        word = re.sub(r"[^A-Z ]", " ", r.company.upper()).split()[0]
        m = [x for x in allassets if word in (x.get("name") or "").upper()
             and (r.coupon_mode is None or str(r.coupon_mode).rstrip("0") in (x.get("name") or ""))]
        hits.append(";".join(f"{x['symbol']}|{x.get('exchange')}|{x.get('status')}|{x.get('tradable')}" for x in m))
    rec["alpaca_matches"] = hits
    rec.to_csv(OUT / "c1_grey_window_today.csv", index=False)
    pre = rec[rec.denom25 & rec.intends_to_list & (rec.a8_filed_since == 0)]
    out.update({"read": int(len(rec)), "retail25_listing_intended": int((rec.denom25 & rec.intends_to_list).sum()),
                "in_prelisting_window_today": int(len(pre)),
                "in_window_with_any_alpaca_asset": int((pre.alpaca_matches.str.len() > 0).sum()),
                "alpaca_active_assets": len(act), "alpaca_inactive_assets": len(ina) if isinstance(ina, list) else None,
                "alpaca_active_otc_named_pref_or_notes": sum(
                    1 for x in act if x.get("exchange") == "OTC"
                    and re.search(r"PFD|PREFERRED|%|NOTES", x.get("name") or "", re.I)),
                "live_edgar_requests": eb.live})
    write_json(OUT / "c1_grey_summary.json", out)
    print(rec.to_string())
    print(json.dumps(out, indent=1, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("candidates")
    s = sp.add_parser("sample")
    s.add_argument("--per-year", type=int, default=8)
    s.add_argument("--offline", action="store_true")
    j = sp.add_parser("adjudicate")
    j.add_argument("--offline", action="store_true")
    sp.add_parser("estimate")
    g = sp.add_parser("grey")
    g.add_argument("--max-docs", type=int, default=20)
    g.add_argument("--days", type=int, default=14)
    a = ap.parse_args(argv)
    {"candidates": cmd_candidates, "sample": cmd_sample, "adjudicate": cmd_adjudicate, "estimate": cmd_estimate, "grey": cmd_grey}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
