"""D6: 8-K governance red flags (items 4.01, 4.02, 5.02), plus the item counts D7/D9/D2 reuse (1.03, 2.02).

    export QUANTT_ENV_FILE=/abs/path/config/.env
    python3 scripts/events/ssx/ssx_fil_d6_8k.py census          # offline after ssx_fil_build
    python3 scripts/events/ssx/ssx_fil_d6_8k.py texts           # live, budgeted: classify a declared sample
    python3 scripts/events/ssx/ssx_fil_d6_8k.py texts --offline # re-classify from the cache

ZERO TRIALS. Counts, links, pre-event ADV (<= 2022), today's borrow flags and
filing text read for classification. No return of any kind.

WHY A FULL CENSUS, NOT A SAMPLE
-------------------------------
The brief allowed sampled submissions JSON scaled with a CI. The nightly bulk
archive holds every CIK's submissions, items included, so the item counts here
are a census of every 8-K filed by the 24,296 CIKs that filed a 10-K, 10-Q, NT
or 8-K in 2008-2025 (an 8-K filer outside that set -- one that never filed a
periodic report or an NT in those years -- is not counted). Only the
sub-classifications that need the text (auditor resignation vs dismissal, 4.02
(a) vs (b), unplanned CEO/CFO departure) are sampled, and they carry Wilson CIs.

THE CLASSIFIERS, DECLARED BEFORE ANY TEXT WAS READ
--------------------------------------------------
4.01 (auditor change), on the 8-K's own document, first match wins:
  merger   - the audit firm combined, merged, joined or sold its practice
             ("practice ... (merged|combined|acquired|joined)") - benign;
  resign   - "resign" or "declined to stand for re-election/re-appointment"
             - auditor-initiated, the literature's bad-news case (Shu 2000);
  dismiss  - "dismiss" - client-initiated;
  other    - none of these.
4.02 (non-reliance): (b) if the text cites Item 4.02(b) or a notice/advice
  FROM the auditor; else (a), the company's own conclusion.
5.02: `ceo_cfo_departure` if a sentence names the CEO/CFO/principal executive
  or financial officer together with a departure verb; `unplanned` if such a
  departure carries no retirement word and has an interim successor, "effective
  immediately", or a termination. This is a proxy for Gentry et al. (SMJ 2021),
  whose eight-way hand coding is the reference; it is a census instrument, not
  a signal.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx import ssx_fil_common as C  # noqa: E402

ITEMS = ("4.01", "4.02", "5.02", "1.03", "2.02")
SALT = "ssx_fil_d6_v1"
N_TEXT = {"4.01": 60, "4.02": 40, "5.02": 80}
OUT = C.OUT


def load_8k() -> pd.DataFrame:
    s = pd.read_parquet(C.CACHE / "subs_rows.parquet", columns=["cik", "accessionNumber", "filingDate", "form",
                                                                  "items", "acceptanceDateTime", "primaryDocument"])
    e = s[s["form"] == "8-K"].drop_duplicates("accessionNumber").copy()
    e["date"] = pd.to_datetime(e["filingDate"])
    e["year"] = e["date"].dt.year
    e = e[e["year"].between(C.COUNT_START, C.COUNT_END)]
    its = e["items"].fillna("").str.split(",")
    for it in ITEMS:
        e["i" + it.replace(".", "")] = its.map(lambda xs, it=it: it in [x.strip() for x in xs])
    return e


def census() -> dict:
    e = load_8k()
    idx = pd.read_parquet(C.CACHE / "index_rows.parquet")
    idx8 = idx[idx["form"] == "8-K"].drop_duplicates("accession").groupby("year").size()
    yr = e.groupby("year").agg(n_8k=("accessionNumber", "size"))
    yr["n_8k_master_index"] = idx8
    for it in ITEMS:
        c = "i" + it.replace(".", "")
        yr[f"item_{it}"] = e.groupby("year")[c].sum()
        yr[f"item_{it}_issuers"] = e[e[c]].groupby("year")["cik"].nunique()

    links, names = C.cik_permno_links(offline=True), C.crsp_names(offline=True)
    dv = C.dv_panel(offline=True)
    sub = e[e[["i401", "i402", "i502", "i103"]].any(axis=1)].copy()
    sub = C.link_events(sub, links, names)
    by = C.dv_by_permno(dv[dv["permno"].isin(sub["permno"].dropna().astype(int).unique())])
    sub["adv"] = C.pre_event_adv_fast(sub, by)
    sub["liquid"] = sub["listed_common"] & (sub["adv"] >= 1e6)
    sub.to_parquet(C.CACHE / "d6_8k_flag_events_linked.parquet")
    for it in ("4.01", "4.02", "5.02", "1.03"):
        c = "i" + it.replace(".", "")
        g = sub[sub[c]].groupby("year")
        yr[f"item_{it}_listed"] = g["listed_common"].sum()
        yr[f"item_{it}_liquid"] = g["liquid"].sum()
        yr.loc[yr.index > C.ADV_LAST_EVENT.year, f"item_{it}_liquid"] = np.nan
    yr.to_csv(OUT / "d6_8k_items_by_year.csv")

    meta = pd.read_parquet(C.CACHE / "subs_meta.parquet")
    assets, clock = C.alpaca_assets()
    borrow = {"alpaca_clock": clock}
    for it in ("4.01", "4.02", "5.02", "1.03"):
        c = "i" + it.replace(".", "")
        ciks = e.loc[e[c] & (e["year"] == 2025), "cik"].unique()
        b = C.borrow_today(ciks, meta, assets)
        k, n = int(b["shortable"].sum()), int(b["at_alpaca"].sum())
        borrow[it] = {"filers_2025": int(len(ciks)), "listed_today": int(len(b)), "at_alpaca": n,
                      "shortable": k, "etb": int(b["etb"].sum()),
                      "shortable_share": round(k / n, 4) if n else None, "ci95": C.wilson(k, n)}
    gate = {}
    for it in ("4.01", "4.02", "5.02"):
        c = "i" + it.replace(".", "")
        w = sub[sub[c] & sub["year"].between(2010, 2022)]
        gate[it] = {"liquid_events_2010_22": int(w["liquid"].sum()),
                    "liquid_issuers_2010_22": int(w.loc[w["liquid"], "cik"].nunique()),
                    "listed_events_2010_22": int(w["listed_common"].sum())}
    summ = {"borrow_today": borrow, "gate_counts": gate,
            "census_note": "every 8-K (original) in the bulk archive of the 24,296 CIKs that filed 10-K/10-Q/NT/8-K in 2008-2025",
            "share_8k_with_items": round(float((e["items"].fillna("") != "").mean()), 6)}
    try:
        summ["ceo_turnover_r2"] = ceo_turnover_prior()
    except Exception as ex:   # reported, not hidden: the prior is context, not a gate input
        summ["ceo_turnover_r2"] = f"UNAVAILABLE: {ex!r}"[:300]
    C.write_json(OUT / "d6_8k_summary.json", summ)
    print(yr.to_string())
    print(summ)
    return summ


def ceo_turnover_prior() -> dict:
    """Forced share in R2's contributed CEO-turnover table (WRDS contrib_ceo_turnover), by era. Licensed; cached."""
    p = C.CACHE / "contrib_ceo_turnover.parquet"
    if not p.exists():
        r2, con = C._r2()
        df = r2.q(con, f"SELECT * FROM read_parquet('{r2.r2_path('contrib_ceo_turnover', 'ceo_turnover')}')")
        df.to_parquet(p)
    df = pd.read_parquet(p)
    df["y"] = pd.to_datetime(df["anndate"]).dt.year
    out = {"rows": int(len(df)), "anndate_range": [str(pd.to_datetime(df["anndate"]).min().date()),
                                                    str(pd.to_datetime(df["anndate"]).max().date())],
           "forced_values": {str(k): int(v) for k, v in df["forced"].value_counts(dropna=False).items()}}
    for lo, hi in ((1993, 2004), (2005, 2014), (2015, 2021)):
        w = df[df["y"].between(lo, hi)]
        out[f"{lo}_{hi}"] = {"n": int(len(w)), "forced": int((w["forced"] == 1).sum())}
    return out


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def main_doc_text(txt: str) -> str:
    """The 8-K's own document from a full submission, tags stripped, whitespace collapsed."""
    docs = re.split(r"<DOCUMENT>", txt)
    for d in docs[1:]:
        m = re.search(r"<TYPE>([^\n<]+)", d)
        if m and m.group(1).strip().upper() in ("8-K", "8-K/A"):
            t = _TAG.sub(" ", d)
            t = re.sub(r"&nbsp;|&#160;|&#xa0;", " ", t, flags=re.I)
            return _WS.sub(" ", t)
    raise C.CensusError("no 8-K document in the submission")


def classify_401(t: str) -> str:
    s = t.lower()
    if re.search(r"practice[^.]{0,200}\b(merged|combined|acquired|joined|sold)\b|\b(merged|combined)\b[^.]{0,120}practice", s):
        return "merger"
    if re.search(r"\bresign|declin(ed|e|ing) to stand for re-?(election|appointment)|will not stand for re-?(election|appointment)", s):
        return "resign"
    if re.search(r"\bdismiss", s):
        return "dismiss"
    return "other"


def classify_402(t: str) -> str:
    s = t.lower()
    if re.search(r"4\.02\s*\(b\)|(notice|advised|informed|notified)[^.]{0,80}\bby\b[^.]{0,80}(independent registered|auditor|accounting firm)", s):
        return "b_auditor"
    return "a_company"


_OFF = r"(chief executive officer|chief financial officer|principal executive officer|principal financial officer|\bceo\b|\bcfo\b)"
_DEP = r"(resign|retire|terminat|depart|step(ped|s|ping)? down|separat|will leave|cease|removed)"


def classify_502(t: str) -> dict:
    s = t.lower()
    sents = re.split(r"(?<=[.;])\s+", s)
    dep = [x for x in sents if re.search(_OFF, x) and re.search(_DEP, x)]
    if not dep:
        return {"ceo_cfo_departure": False, "unplanned": False}
    j = " ".join(dep)
    retire = bool(re.search(r"retire", j))
    abrupt = bool(re.search(r"\binterim\b|effective immediately|terminat", s))
    return {"ceo_cfo_departure": True, "unplanned": (not retire) and abrupt}


def texts(offline: bool) -> dict:
    ev = pd.read_parquet(C.CACHE / "d6_8k_flag_events_linked.parquet")
    pool = ev[ev["year"].between(2015, 2022) & ev["listed_common"]]
    E = C.BudgetedEdgar(offline=offline)
    from scripts.data.edgar_client import filing_txt_url
    rows = []
    for it, n in N_TEXT.items():
        c = "i" + it.replace(".", "")
        p = pool[pool[c]]
        picks = C.declared_order(p["accessionNumber"].tolist(), f"{SALT}:{it}")[:n]
        sub = p.set_index("accessionNumber").loc[picks]
        for acc, r in sub.iterrows():
            row = {"item": it, "accession": acc, "cik": int(r["cik"]), "filing_date": r["date"].date().isoformat(),
                   "liquid": bool(r["liquid"])}
            try:
                txt = E.get_text(filing_txt_url(int(r["cik"]), acc), purpose=f"d6 8-K {it} text")
                row["accepted_et"] = C.header_acceptance_et(txt).isoformat(sep=" ")
                t = main_doc_text(txt)
                if it == "4.01":
                    row["class"] = classify_401(t)
                elif it == "4.02":
                    row["class"] = classify_402(t)
                else:
                    row.update(classify_502(t))
            except Exception as ex:   # recorded per filing, never dropped silently
                row["error"] = repr(ex)[:200]
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "d6_8k_text_sample.csv", index=False)
    ok = df[df["error"].isna()] if "error" in df else df
    summ = {}
    for it, g in ok.groupby("item"):
        n = len(g)
        d = {"n": n}
        if it in ("4.01", "4.02"):
            for k, v in g["class"].value_counts().items():
                d[k] = {"k": int(v), "share": round(v / n, 4), "ci95": C.wilson(int(v), n)}
        else:
            k1 = int(g["ceo_cfo_departure"].sum())
            k2 = int(g["unplanned"].sum())
            d["ceo_cfo_departure"] = {"k": k1, "share": round(k1 / n, 4), "ci95": C.wilson(k1, n)}
            d["unplanned_ceo_cfo"] = {"k": k2, "share": round(k2 / n, 4), "ci95": C.wilson(k2, n)}
        t = pd.to_datetime(g["accepted_et"])
        same = t.dt.date.astype(str) == g["filing_date"]
        after = int(((t.dt.hour * 100 + t.dt.minute >= 1600) & same).sum() + (~same).sum())
        d["after_close"] = {"k": after, "share": round(after / n, 4), "ci95": C.wilson(after, n)}
        d["market_hours"] = int((same & (t.dt.hour * 100 + t.dt.minute >= 930) & (t.dt.hour * 100 + t.dt.minute < 1600)).sum())
        summ[it] = d
    summ["errors"] = int(len(df) - len(ok))
    summ["live_requests_ledger_total"] = C.BudgetedEdgar.spent()
    C.write_json(OUT / "d6_8k_text_summary.json", summ)
    print(summ)
    return summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("census", "texts"))
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    C.OUT.mkdir(parents=True, exist_ok=True)
    census() if a.part == "census" else texts(a.offline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
