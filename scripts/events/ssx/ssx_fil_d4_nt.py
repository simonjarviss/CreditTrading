"""D4: late-filing notices (Form 12b-25: NT 10-K, NT 10-Q). A zero-trial census and its kill gate.

    export QUANTT_ENV_FILE=/abs/path/config/.env
    python3 scripts/events/ssx/ssx_fil_build.py all --bulk-cache <cache root>   # once
    python3 scripts/events/ssx/ssx_fil_d4_nt.py census            # offline after the build
    python3 scripts/events/ssx/ssx_fil_d4_nt.py headers           # live, budgeted: acceptance-time sample
    python3 scripts/events/ssx/ssx_fil_d4_nt.py headers --offline # re-read the cached headers

ZERO TRIALS. Counts, links, pre-event ADV (events <= 2022-12-31, CRSP rows
< 2023), today's Alpaca flags and filing timestamps. No return of any kind.

WHY THIS EVENT
--------------
Rule 12b-25 lets a registrant that cannot file a 10-K or 10-Q on time file a
notice (Form NT) no later than one business day after the due date and gain 15
(10-K) or 5 (10-Q) calendar days. The notice must say why. The literature reads
it as bad news the price absorbs slowly: Bartov & Konchitchki (Accounting
Horizons; 2,115 firms) report a significant drop at the NT, larger when the
extended deadline is then missed, and declines that "can continue for months"
(NYU Stern summary [S]). The named loser is the holder who reads the notice as
clerical. The desk's question is narrower: are there enough LISTED, LIQUID,
SHORTABLE notices to test it, and when in the day do they arrive?

WHAT IS COUNTED, AND HOW
------------------------
* Notices per year: unique accessions of NT 10-K / NT 10-Q (and /A, separately)
  in the quarterly master indexes, 2008-2025 [primary]; the bulk submissions
  archive is the cross-check (both are EDGAR; they should agree to the filing).
* "Listed common, ADV >= $1m": the CIK is linked to a CRSP permno through
  Compustat x CCM (ssx_fil_common) on the filing date, the permno's CRSP spell
  that day is share code 10/11 on NYSE/American/Nasdaq/Arca, and mean dollar
  volume over sessions t-21..t-2 is >= $1m. Events after 2022 get no ADV.
* "Independent": unique filings; also unique issuer-years and unique filing
  dates, because notices cluster at the deadlines (a market shock on one
  deadline day hits every notice filed that day).
* BDC notices: the CIK was an elected BDC (N-54A, not withdrawn) that day.
* Borrow today: 2025 notice filers that EDGAR lists today with a national-
  exchange ticker, looked up in today's Alpaca asset list.
* Acceptance time: a declared, content-blind sample (sha256 order) of notices,
  read from each filing's own SEC header, because the submissions API is one
  UTC offset late on about half of filings (REFERENCES §12y/§12z).
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx import ssx_fil_common as C  # noqa: E402

NT = ("NT 10-K", "NT 10-Q")
NT_AMEND = ("NT 10-K/A", "NT 10-Q/A")
GATE_YEARS = (2010, 2022)
GATE_MIN_EVENTS = 250
SALT = "ssx_fil_d4_nt_v1"
N_HEADERS_LISTED = 150      # listed commons, 2015-2022
N_HEADERS_ALL = 100         # every notice filer, 2015-2025
OUT = C.OUT


def load_events() -> pd.DataFrame:
    idx = pd.read_parquet(C.CACHE / "index_rows.parquet")
    nt = idx[idx["form"].isin(NT + NT_AMEND)].drop_duplicates("accession").copy()
    nt["date"] = nt["date_filed"]
    return nt


def census() -> dict:
    nt = load_events()
    subs = pd.read_parquet(C.CACHE / "subs_rows.parquet")
    meta = pd.read_parquet(C.CACHE / "subs_meta.parquet")

    # 1. counts per year, both EDGAR products
    by_form = nt.groupby(["year", "form"]).size().unstack(fill_value=0)
    s_nt = subs[subs["form"].isin(NT + NT_AMEND)].drop_duplicates("accessionNumber").copy()
    s_nt["year"] = s_nt["filingDate"].str[:4].astype(int)
    by_form_subs = s_nt[s_nt["year"].between(C.COUNT_START, C.COUNT_END)].groupby(["year", "form"]).size().unstack(fill_value=0)
    orig = nt[nt["form"].isin(NT)].copy()
    yr = orig.groupby("year").agg(notices=("accession", "size"), issuers=("cik", "nunique"),
                                  filing_dates=("date", "nunique"))

    # 2. link and liquidity (originals only)
    links, names = C.cik_permno_links(offline=True), C.crsp_names(offline=True)
    ev = C.link_events(orig[["cik", "date", "form", "accession", "year"]], links, names)
    dv = C.dv_panel(offline=True)
    by = C.dv_by_permno(dv[dv["permno"].isin(ev["permno"].dropna().astype(int).unique())])
    ev["adv"] = C.pre_event_adv_fast(ev, by)
    ev["liquid"] = ev["listed_common"] & (ev["adv"] >= 1e6)
    spells = C.bdc_spells(subs)
    ev["bdc"] = C.is_bdc_on(ev, spells)
    ev.to_parquet(C.CACHE / "d4_nt_events_linked.parquet")

    g = ev.groupby("year")
    yr["linked_ccm"] = g["linked"].sum()
    yr["listed_common"] = g["listed_common"].sum()
    yr["listed_with_adv"] = g.apply(lambda x: int((x["listed_common"] & x["adv"].notna()).sum()), include_groups=False)
    yr["liquid_adv_ge_1m"] = g["liquid"].sum()
    yr["liquid_issuers"] = g.apply(lambda x: x.loc[x["liquid"], "cik"].nunique(), include_groups=False)
    yr["liquid_dates"] = g.apply(lambda x: x.loc[x["liquid"], "date"].nunique(), include_groups=False)
    yr["liquid_nt10k"] = g.apply(lambda x: int((x["liquid"] & (x["form"] == "NT 10-K")).sum()), include_groups=False)
    yr["bdc_notices"] = g["bdc"].sum()
    yr["bdc_issuers"] = g.apply(lambda x: x.loc[x["bdc"], "cik"].nunique(), include_groups=False)
    for c in ("liquid_adv_ge_1m", "liquid_issuers", "liquid_dates", "listed_with_adv", "liquid_nt10k"):
        yr.loc[yr.index > C.ADV_LAST_EVENT.year, c] = np.nan   # no ADV after 2022 by rule, not zero
    yr = yr.join(by_form, rsuffix="_idx")
    yr.to_csv(OUT / "d4_nt_by_year.csv")
    by_form_subs.to_csv(OUT / "d4_nt_by_year_submissions_crosscheck.csv")

    lo, hi = GATE_YEARS
    w = ev[(ev["year"] >= lo) & (ev["year"] <= hi)]
    gate_events = int(w["liquid"].sum())
    gate_issuer_years = int(w.loc[w["liquid"], ["cik", "year"]].drop_duplicates().shape[0])
    gate_dates = int(w.loc[w["liquid"], "date"].nunique())
    adv_l = w.loc[w["listed_common"] & w["adv"].notna(), "adv"]

    # 3. recall check of the link: CIKs EDGAR lists today on a national exchange
    t_today = C.sec_tickers_today(meta)
    nat = set(t_today.loc[t_today["exchange"].isin(C.NATIONAL_EXCHANGES), "cik"])
    w18 = ev[(ev["year"] >= 2018) & (ev["year"] <= 2022) & ev["cik"].isin(nat)]
    # An unlinked event whose CIK has a CCM link that starts LATER was not exchange-
    # listed on the event date (an uplisting); only a CIK with no CCM link at all
    # is a miss of the route itself.
    unl = w18[~w18["linked"]]
    recall = {"events_2018_22_by_ciks_listed_today": int(len(w18)), "linked_ccm": int(w18["linked"].sum()),
              "listed_common": int(w18["listed_common"].sum()),
              "unlinked_cik_has_ccm_link_at_another_date": int(unl["cik"].isin(set(links["cik"])).sum()),
              "unlinked_cik_absent_from_ccm": int((~unl["cik"].isin(set(links["cik"]))).sum()),
              "unlinked_ciks_absent_from_ccm": int(unl.loc[~unl["cik"].isin(set(links["cik"])), "cik"].nunique())}

    # 4. borrow today for 2025 filers
    assets, clock = C.alpaca_assets()
    c25 = orig.loc[orig["year"] == 2025, "cik"].unique()
    b = C.borrow_today(c25, meta, assets)
    borrow = {"alpaca_clock": clock, "filers_2025": int(len(c25)),
              "listed_today_national_exchange": int(len(b)), "at_alpaca": int(b["at_alpaca"].sum()),
              "shortable": int(b["shortable"].sum()), "etb": int(b["etb"].sum())}
    if borrow["at_alpaca"]:
        borrow["shortable_share_of_at_alpaca"] = round(borrow["shortable"] / borrow["at_alpaca"], 4)
        borrow["shortable_share_ci95"] = C.wilson(borrow["shortable"], borrow["at_alpaca"])
        borrow["etb_share_of_at_alpaca"] = round(borrow["etb"] / borrow["at_alpaca"], 4)
    b.to_csv(C.CACHE / "d4_borrow_2025_filers.csv", index=False)
    # Second read, survivorship-skewed and labelled so: issuers that had a LIQUID
    # notice in 2018-22 and are still exchange-listed today. It asks whether the
    # liquid end of the population borrows better than 2025's mostly small filers.
    c_liq = ev.loc[ev["liquid"] & ev["year"].between(2018, 2022), "cik"].unique()
    b2 = C.borrow_today(c_liq, meta, assets)
    borrow["liquid_2018_22_issuers"] = int(len(c_liq))
    borrow["liquid_2018_22_listed_today"] = int(len(b2))
    borrow["liquid_2018_22_at_alpaca"] = int(b2["at_alpaca"].sum())
    borrow["liquid_2018_22_shortable"] = int(b2["shortable"].sum())
    if len(b2):
        borrow["liquid_2018_22_shortable_ci95"] = C.wilson(int(b2["shortable"].sum()), int(b2["at_alpaca"].sum()))

    summ = {
        "source": "EDGAR master indexes 2008Q1-2025Q4 (offline); bulk submissions archive; CRSP/Compustat via R2; Alpaca GETs",
        "notices_2008_2025_originals": int(len(orig)), "issuers_2008_2025": int(orig["cik"].nunique()),
        "gate_window": GATE_YEARS,
        "gate_liquid_events": gate_events, "gate_liquid_issuer_years": gate_issuer_years,
        "gate_liquid_filing_dates": gate_dates,
        "gate_kill_line": GATE_MIN_EVENTS,
        "listed_common_2010_22": int(w["listed_common"].sum()), "linked_2010_22": int(w["linked"].sum()),
        "notices_2010_22": int(len(w)),
        "listed_adv_median_usd_2010_22": float(adv_l.median()) if len(adv_l) else None,
        "listed_share_adv_ge_1m_2010_22": round(float((adv_l >= 1e6).mean()), 4) if len(adv_l) else None,
        "link_recall_check": recall,
        "multi_permno_events": int(ev["multi_permno"].astype("boolean").fillna(False).sum()),
        "borrow_today": borrow,
        "bdc_spells": int(len(spells)),
        "bdc_notices_2008_2025": int(ev["bdc"].sum()),
    }
    C.write_json(OUT / "d4_nt_summary.json", summ)
    print(yr.to_string())
    print(summ)
    return summ


def headers(offline: bool) -> dict:
    """Acceptance time of a declared sample of notices, from each filing's SEC header."""
    ev = pd.read_parquet(C.CACHE / "d4_nt_events_linked.parquet")
    subs = pd.read_parquet(C.CACHE / "subs_rows.parquet", columns=["accessionNumber", "acceptanceDateTime"])
    api = dict(zip(subs["accessionNumber"], subs["acceptanceDateTime"]))
    L = ev[(ev["year"].between(2015, 2022)) & ev["listed_common"]]
    A = ev[ev["year"].between(2015, 2025)]
    pick_L = C.declared_order(L["accession"].tolist(), SALT + ":listed")[:N_HEADERS_LISTED]
    pick_A = C.declared_order(A["accession"].tolist(), SALT + ":all")[:N_HEADERS_ALL]
    E = C.BudgetedEdgar(offline=offline)
    from scripts.data.edgar_client import filing_txt_url
    rows = []
    for stratum, picks in (("listed_2015_22", pick_L), ("all_2015_25", pick_A)):
        sub = ev.set_index("accession").loc[picks]
        for acc, r in sub.iterrows():
            url = filing_txt_url(int(r["cik"]), acc)
            try:
                txt = E.get_text(url, purpose="d4 NT header")
            except Exception as e:  # recorded per filing, never dropped silently
                rows.append({"stratum": stratum, "accession": acc, "error": repr(e)[:200]})
                continue
            et = C.header_acceptance_et(txt)
            a = api.get(acc)
            api_et = C.api_as_et(a) if isinstance(a, str) else None
            rows.append({"stratum": stratum, "accession": acc, "cik": int(r["cik"]), "form": r["form"],
                         "filing_date": pd.Timestamp(r["date"]).date().isoformat(),
                         "accepted_et": et.isoformat(sep=" "), "api_as_et": api_et.isoformat(sep=" ") if api_et else None,
                         "api_offset_h": round((api_et - et).total_seconds() / 3600, 2) if api_et else None})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "d4_nt_acceptance_sample.csv", index=False)
    ok = df[df.get("error").isna()] if "error" in df else df
    ok = ok.copy()
    t = pd.to_datetime(ok["accepted_et"])
    ok["hhmm"] = t.dt.hour * 100 + t.dt.minute
    ok["same_day"] = t.dt.date.astype(str) == ok["filing_date"]
    def bins(g):
        n = len(g)
        k = {"pre_open_lt_0930": int((g["same_day"] & (g["hhmm"] < 930)).sum()),
             "market_0930_1600": int((g["same_day"] & (g["hhmm"] >= 930) & (g["hhmm"] < 1600)).sum()),
             "after_close_1600_1730": int((g["same_day"] & (g["hhmm"] >= 1600)).sum()),
             "after_1730_next_day_filing_date": int((~g["same_day"]).sum())}
        after = k["after_close_1600_1730"] + k["after_1730_next_day_filing_date"]
        return {"n": n, **k, "after_close_share": round(after / n, 4) if n else None,
                "after_close_ci95": C.wilson(after, n),
                "api_offset_h_counts": {str(x): int(v) for x, v in g["api_offset_h"].value_counts().sort_index().items()}}
    summ = {s: bins(g) for s, g in ok.groupby("stratum")}
    summ["errors"] = int(len(df) - len(ok))
    summ["live_requests_ledger_total"] = C.BudgetedEdgar.spent()
    C.write_json(OUT / "d4_nt_acceptance_summary.json", summ)
    print(summ)
    return summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("census", "headers"))
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    C.OUT.mkdir(parents=True, exist_ok=True)
    if a.part == "census":
        census()
    else:
        headers(a.offline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
