"""CEF/BDC structural census for the special-situations expansion, seat `ssx_fund1` (ZERO TRIALS).

    export QUANTT_ENV_FILE=/abs/path/config/.env     # R2 and the Alpaca keys; never printed
    python3 scripts/events/ssx/ssx_fund1_census.py index      # offline EDGAR indexes -> fund rows (cache)
    python3 scripts/events/ssx/ssx_fund1_census.py listed     # R2 CRSP names -> CIK->permno, listed-at-date
    python3 scripts/events/ssx/ssx_fund1_census.py a1         # issuance-supplement counts (A1)
    python3 scripts/events/ssx/ssx_fund1_census.py a7         # leverage events and the distribution-cut overlap (A7)
    python3 scripts/events/ssx/ssx_fund1_census.py alpaca     # today's flags on 2024-25 ATM filers (read-only GET)

WHY THIS EXISTS
---------------
The team lead asked on 2026-10-19 for more signals and an institutional-scale
event desk. Iteration 1 of that expansion is zero-trial censuses and
feasibility gates. This seat censuses three fund-structure ideas:

* **A1, issuance into premiums.** A CEF or BDC that trades above NAV can sell
  new shares (an at-the-market programme off a shelf, or an underwritten
  follow-on) and the sale caps the premium. The losers are buyers at the
  premium. The question here is only: how many such issuance events are
  there, how independent, and could the short side be borrowed today.
* **A3, BDC buyback plans that buy only below NAV** (Rule 10b5-1). The
  census question: how many plans, and are their terms (size, NAV trigger,
  expiry) disclosed point-in-time. The document sample lives in
  `ssx_fund1_docs.py`; this script supplies the BDC population it samples.
* **A7, fund leverage changes**: preferred redemptions (Rule 23c-2 notices),
  preferred and note offerings, rating actions on fund preferreds and notes.
  The graveyard risk is named in the brief: distribution data failed twice as
  a signal (M7). If leverage events are mostly distribution cuts in another
  coat, A7 is M7 again. So the overlap with the cut dates in
  `data/cef/cef_dist_features.parquet` is measured, against a base rate.

WHAT IT MAY AND MAY NOT READ (the brief's hard line)
---------------------------------------------------
No return, P&L, CAR, drift, Sharpe or hit rate of anything is computed, on any
data. Event COUNTS run to 2025-12-31. CRSP is used for NAME records only
(`dsenames`: who was listed when); no `dsf` price or return row is read by
this script. `cef_dist_features.parquet` is read for DATES and the `is_cut`
flag only (the 43 funds it covers are `cef_universe.csv` names: counted,
never priced). Alpaca: one read-only `GET /v2/assets`, true on its date only.

WHY THESE ROUTES
----------------
* **The fund set is the EDGAR fetcher's own rule** (`fetch_edgar_events.fund_set`:
  a CIK that filed a closed-end-only form, or N-CSR plus a Form 3/4), over the
  closed quarters 2008Q1-2025Q4 that `ss_catalogue_counts.py` also uses. Index
  lines are parsed by the fetcher's validating parser. Nothing is reinvented.
* **BDC versus registered CEF** is read from what each CIK files: a BDC files
  10-Q/10-K (it is not a registered investment company and files no N-CSR) or
  the BDC election N-54A/N-54C/N-6F; a registered CEF files N-CSR/N-CSRS.
  Interval funds (N-23C3A/B/C) are tagged: they are not exchange-listed.
* **Listed at the filing date** comes from CRSP name records, not from
  today's ticker file. Most of the funds that issued in 2010-22 and then
  merged away have no ticker today, and many BDCs filed continuous-offering
  supplements for years while NON-traded before listing (Owl Rock, CION, FS):
  counting those as listed-fund issuance would inflate A1 by the whole
  non-traded BDC industry. CRSP share codes 14/44 are closed-end funds and
  BDCs (checked 2026-10-19: ARCC, MAIN, PSEC, GBDC, TSLX, FSK, ORCC carry 14;
  BXSL 44; munis 44). CRSP carries no CIK, so each CIK's EDGAR names are
  matched to CRSP names by the merger study's matcher
  (`cef_corp_action_census.CrspMap`: ticker first, then name score >= 0.85
  with margin >= 0.02). A filing counts as LISTED if one of its CIK's
  permnos has a share-code 14/44 name record in force on the filing date.
  CRSP ends 2024-12-31, so for 2025 filings the rule is: a record in force on
  2024-12-31, or an exchange ticker (NYSE/Nasdaq/CBOE) in the SEC ticker file
  today. That is labelled wherever 2025 appears.
* **Which forms are issuance supplements.** Before 2020-08-01 a registered
  CEF filed its prospectus supplements under Rule 497; the 2020 offering
  reform (Release 33-10771, effective 2020-08-01) made Rule 424 "the exclusive
  rule" for registered CEFs and BDCs (K&L Gates alert 2020-04-10 [V]). So 497
  and 424B1-8 are both counted, by form family, and the switch is visible in
  the table (a second check of the rule). CORRECTION 2026-10-19, measured
  here: this docstring first said "BDCs always used Rule 424". They did not.
  Listed BDCs filed 0 supplements as 424B in 2010-2019 and 1,700 as 497; the
  switch to 424B happens for BDCs and registered CEFs alike in 2020-21
  (`a1_listed_supplements_by_year_family.csv`).
  A 497 is also a sticker supplement or a statement of additional
  information; a 424B can be a note or preferred offering. The index cannot
  tell: `ssx_fund1_docs.py supplements` classifies a seeded sample by text.

INDEPENDENCE
------------
Funds file in families and programmes: a BlackRock or Nuveen shelf covers
many funds, an ATM programme is refreshed by a new supplement each quarter.
So three counts are printed per year: filings (accessions), distinct funds,
and distinct fund-months; plus distinct calendar months with any event.
"Independent fund-events a year" in the gate is DISTINCT FUNDS A YEAR,
the most conservative of the three that still counts each issuer once.

OUTPUTS
-------
Aggregates (no CRSP identifiers) to `results/events/ssx/ssx_fund1/`.
Row-level tables carrying permnos to `results/events/ssx/_cache_ssx_fund1/`
(gitignored by `results/**/_cache_*`; CRSP is licensed, this repo is public).

NO SILENT FALLBACKS: a missing quarter, an unparseable line, an empty result
where events must exist, or a CRSP code that is not there raises, naming it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("compute.use_numexpr", False)     # scripts/events/numexpr_fault.py

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:  # run as a script, not -m
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events" / "ssx" / "ssx_fund1"
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_fund1"
INDEX_ROWS = CACHE / "index_fund_rows_2008Q1_2025Q4.parquet"
FUND_TYPES = CACHE / "fund_types.parquet"
CRSP_NAMES = CACHE / "crsp_dsenames_cef.parquet"          # licensed: cache only
CIK_PERMNO = CACHE / "cik_permno_map.csv"                  # licensed: cache only
LISTED_ROWS = CACHE / "fund_rows_listed.parquet"           # carries permnos: cache only

INDEX_FIRST, INDEX_LAST = (2008, 1), (2025, 4)             # closed quarters only (offline cache)
COUNT_START, COUNT_END = 2010, 2025                        # event counts (counts only after 2022)
TIME_HOLDOUT = pd.Timestamp("2023-01-01")
CRSP_LAST = pd.Timestamp("2024-12-31")                     # the R2 mirror's last CRSP date
REFORM_DATE = pd.Timestamp("2020-08-01")                   # Release 33-10771 effective date

SUPP_424 = ("424B1", "424B2", "424B3", "424B4", "424B5", "424B7", "424B8")
SUPP_FORMS = SUPP_424 + ("497",)
BDC_FORMS = frozenset({"N-54A", "N-54A/A", "N-54C", "N-54C/A", "N-6F", "N-6F/A"})
PERIODIC_CORP = frozenset({"10-Q", "10-K"})
NCSR = frozenset({"N-CSR", "N-CSRS"})
INTERVAL = frozenset({"N-23C3A", "N-23C3A/A", "N-23C3B", "N-23C3B/A", "N-23C3C", "N-23C3C/A"})
REDEMPTION_NOTICE = ("N-23C-2", "N-23C-2/A")
PROXY = ("DEF 14A",)
# Every form this seat counts or uses to type a fund. Forms 3/4 only build the set.
KEEP_ROWS = (frozenset(SUPP_FORMS) | BDC_FORMS | PERIODIC_CORP | NCSR | INTERVAL
             | frozenset(REDEMPTION_NOTICE) | frozenset(PROXY)
             | frozenset({"8-K", "8-A12B", "25-NSE", "POS 8C", "N-2", "N-2/A", "N-2ASR", "N-2 POSASR",
                          "N-2MEF", "40-APP", "40-APP/A", "N-8F", "N-14 8C"}))
EXCHANGES_LISTED = ("NYSE", "Nasdaq", "CBOE")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _meta(part: str, rec: dict) -> None:
    p = OUT / "run_meta.json"
    m = json.loads(p.read_text()) if p.exists() else {}
    m[part] = rec
    p.write_text(json.dumps(m, indent=1, sort_keys=True, default=str) + "\n")


# ------------------------------------------------------------------ index

def build_index() -> dict:
    """Fund-set rows of the kept forms, 2008Q1-2025Q4, from the OFFLINE cache.

    One pass over 72 quarters. Forms 3/4 and N-CSR only feed the fund-set
    rule (the fetcher's `fund_set`, applied to sets, not rows, so the pass
    holds no Form 4 rows in memory). A missing quarter raises in the client.
    """
    from scripts.data.edgar_client import EdgarClient
    from scripts.data import fetch_edgar_events as fe
    client = EdgarClient(offline=True)
    keep = KEEP_ROWS | fe.MARKER_FORMS | fe.NCSR_FORMS | fe.INSIDER_FORMS
    marker, ncsr, insider, frames = set(), set(), set(), []
    qs = [q for q in fe.quarters(date(*INDEX_FIRST[:1], 1, 1), date(INDEX_LAST[0], 12, 31))]
    for y, q in qs:
        text = client.get_text(fe.INDEX_URL.format(y=y, q=q))      # closed quarter: immutable
        df = fe.parse_master_index(text, label=f"{y}Q{q}", keep_forms=keep)
        marker |= set(df.loc[df["form"].isin(fe.MARKER_FORMS), "cik"])
        ncsr |= set(df.loc[df["form"].isin(fe.NCSR_FORMS), "cik"])
        insider |= set(df.loc[df["form"].isin(fe.INSIDER_FORMS), "cik"])
        frames.append(df[df["form"].isin(KEEP_ROWS | fe.MARKER_FORMS)])
    # The fetcher's rule, verbatim in effect (fund_set needs a frame; build the minimal one).
    probe = pd.DataFrame({"cik": list(marker) + list(ncsr) + list(insider),
                          "form": (["N-2"] * len(marker) + ["N-CSR"] * len(ncsr) + ["4"] * len(insider))})
    rule = fe.fund_set(probe)
    idx = pd.concat(frames, ignore_index=True)
    idx = idx[idx["cik"].isin(set(rule))].drop_duplicates(["cik", "accession", "form"]).reset_index(drop=True)
    idx["set_rule"] = idx["cik"].map(rule)
    CACHE.mkdir(parents=True, exist_ok=True)
    idx.to_parquet(INDEX_ROWS)

    forms_by = idx.groupby("cik")["form"].agg(set)
    ft = pd.DataFrame({"cik": forms_by.index})
    ft["bdc_election"] = [bool(s & BDC_FORMS) for s in forms_by]
    ft["files_10q"] = [bool(s & PERIODIC_CORP) for s in forms_by]
    ft["files_ncsr"] = [bool(s & NCSR) for s in forms_by]
    ft["interval"] = [bool(s & INTERVAL) for s in forms_by]
    ft["fund_type"] = np.select(
        [ft.bdc_election | (ft.files_10q & ~ft.files_ncsr), ft.files_ncsr],
        ["bdc", "rcef"], default="unknown")
    ft["set_rule"] = ft["cik"].map(rule)
    names = idx.sort_values("date_filed").groupby("cik")["company"].last()
    ft["company_last"] = ft["cik"].map(names)
    ft.to_parquet(FUND_TYPES)
    out = {"ran_utc": _now(), "quarters": [f"{qs[0][0]}Q{qs[0][1]}", f"{qs[-1][0]}Q{qs[-1][1]}"],
           "n_quarters": len(qs), "fund_set_ciks": len(rule),
           "fund_set_by_rule": pd.Series(rule).value_counts().to_dict(),
           "fund_rows_kept": int(len(idx)), "fund_type_counts": ft["fund_type"].value_counts().to_dict(),
           "interval_ciks": int(ft["interval"].sum()), "edgar_requests": client.n_requests,
           "edgar_cache_hits": client.n_cache_hits}
    _meta("index", out)
    print(json.dumps(out, indent=1, default=str))
    return out


# ------------------------------------------------------------------ CRSP listed status

def crsp_names(refresh: bool = False) -> pd.DataFrame:
    """Every `dsenames` record of a permno that ever carried share code 14 or 44.

    NAME records only: who was listed, under what name and ticker, when. No
    price, volume or return column is selected. Cached in this seat's
    gitignored cache (CRSP is licensed).
    """
    if CRSP_NAMES.exists() and not refresh:
        nm = pd.read_parquet(CRSP_NAMES)
    else:
        from src.data.r2 import connect, r2_path, q
        con = connect()
        p = r2_path("crsp_a_stock", "dsenames")
        nm = q(con, f"""SELECT permno, namedt, nameendt, shrcd, exchcd, ticker, comnam, ncusip
                        FROM read_parquet('{p}')
                        WHERE permno IN (SELECT DISTINCT permno FROM read_parquet('{p}') WHERE shrcd IN (14, 44))""")
        if nm.empty:
            raise RuntimeError("CRSP dsenames returned no share-code 14/44 permno")
        CACHE.mkdir(parents=True, exist_ok=True)
        nm.to_parquet(CRSP_NAMES)
    for c in ("namedt", "nameendt"):
        nm[c] = pd.to_datetime(nm[c])
    if nm["nameendt"].max() > CRSP_LAST + pd.Timedelta(days=1):
        raise RuntimeError(f"dsenames reaches {nm['nameendt'].max().date()}, past the mirror's stated end")
    return nm


def sec_tickers_now() -> pd.DataFrame:
    """The SEC ticker file as cached by the EDGAR fetcher (offline; fetched 2026-10-12)."""
    from scripts.data.edgar_client import EdgarClient
    from scripts.data import fetch_edgar_events as fe
    j = EdgarClient(offline=True).get_json(fe.TICKERS_URL, max_age_s=None)
    if j.get("fields") != ["cik", "name", "ticker", "exchange"]:
        raise ValueError(f"company_tickers_exchange.json fields changed: {j.get('fields')}")
    return pd.DataFrame(j["data"], columns=j["fields"])


def build_listed() -> dict:
    """CIK -> CRSP permnos by name, then a listed-at-filing-date flag per fund row.

    Only CIKs that filed a counted form in 2010-2025 are matched (the matcher
    is slow). Each distinct EDGAR name of a CIK is tried at the last date it
    was used (capped at CRSP's end), with today's exchange ticker first. A CIK
    can map to several permnos (a fund that changed CUSIP); all are kept.
    """
    from scripts.events.cef_corp_action_census import CrspMap
    idx = pd.read_parquet(INDEX_ROWS)
    ft = pd.read_parquet(FUND_TYPES)
    nm = crsp_names()
    tk = sec_tickers_now()
    tk_ex = tk[tk["exchange"].isin(EXCHANGES_LISTED)]
    # File order, not alphabetical. Measured 2026-10-19: sorted, the first ticker of 36 of the
    # 199 funds that filed in 2024-25 was a baby bond or preferred line (PFLA for PennantPark
    # Floating Rate's PFLT, SAJ for Saratoga's SAR), and the Alpaca gate read the wrong
    # security. The SEC file lists a company's common ticker first in every case checked.
    ticker_now = tk_ex.groupby("cik", sort=False)["ticker"].agg(lambda v: ";".join(dict.fromkeys(v)))
    counted = idx[(idx["date_filed"].dt.year >= COUNT_START) & (idx["date_filed"].dt.year <= COUNT_END)
                  & idx["form"].isin(set(SUPP_FORMS) | set(REDEMPTION_NOTICE) | set(PROXY) | PERIODIC_CORP | {"8-K"})]
    ciks = sorted(counted["cik"].unique())
    cmap = CrspMap(nm)
    names = (idx[idx["cik"].isin(ciks)].groupby(["cik", "company"])["date_filed"]
             .agg(first="min", last="max").reset_index())
    rows = []
    for r in names.itertuples(index=False):
        # Tried at the FIRST and the LAST date the name was used. Measured 2026-10-19: tried
        # at the last date only, a fund that had merged away (its N-8F filed months after
        # delisting) found no record of its own in the +-30-day window and took a sibling's
        # (NUVEEN GEORGIA DIVIDEND ADVANTAGE -> NAD's "NUVEEN DIVIDEND ADV MUN FUND", 0.88).
        # A ticker hit wins; else the higher name score; a tie keeps both permnos.
        t = ticker_now.get(r.cik)
        hits = []
        for when in sorted({min(pd.Timestamp(r.first), CRSP_LAST), min(pd.Timestamp(r.last), CRSP_LAST)}):
            p, how = cmap.permno(r.company, t, when)
            if p is not None:
                sc = re.search(r"score (-?[0-9.]+)", how)
                hits.append((how.startswith("ticker"), float(sc.group(1)) if sc else 0.0, int(p), how, when))
        if not hits:
            rows.append({"cik": int(r.cik), "company": r.company, "when": None, "permno": None, "how": how})
            continue
        best = max(h[:2] for h in hits)
        for h in hits:
            if h[:2] == best:
                rows.append({"cik": int(r.cik), "company": r.company, "when": h[4].date(), "permno": h[2], "how": h[3]})
    m = pd.DataFrame(rows).drop_duplicates(["cik", "company", "permno"])
    m.to_csv(CIK_PERMNO, index=False)
    perm_by_cik = m.dropna(subset=["permno"]).groupby("cik")["permno"].agg(lambda v: sorted({int(x) for x in v}))
    cef = nm[nm["shrcd"].isin((14, 44))]
    spans = {p: list(zip(g["namedt"], g["nameendt"])) for p, g in cef.groupby("permno")}
    in_force_end = set(cef.loc[cef["nameendt"] >= CRSP_LAST, "permno"])

    def listed(cik: int, d: pd.Timestamp) -> str:
        ps = perm_by_cik.get(cik, [])
        if d <= CRSP_LAST:
            for p in ps:
                if any(a <= d <= b for a, b in spans.get(p, [])):
                    return "listed_crsp"
            return "not_listed"
        # 2025: CRSP has ended. A record in force at its end, or an exchange ticker today.
        if any(p in in_force_end for p in ps):
            return "listed_crsp_end"
        if cik in ticker_now.index:
            return "listed_ticker_now"
        return "not_listed"

    rows = idx[(idx["date_filed"].dt.year >= COUNT_START) & (idx["date_filed"].dt.year <= COUNT_END)].copy()
    rows["listed"] = [listed(int(c), d) for c, d in zip(rows["cik"], rows["date_filed"])]
    rows = rows.merge(ft[["cik", "fund_type", "interval"]], on="cik", how="left")
    rows["ticker_now"] = rows["cik"].map(ticker_now)
    rows.to_parquet(LISTED_ROWS)
    # Recall check: the 44 universe funds must all map (they are all listed today).
    uni = pd.read_csv(REPO / "data" / "cef" / "cef_universe.csv")["ticker"]
    t2c = dict(zip(tk["ticker"], tk["cik"]))
    uni_ciks = {t: int(t2c[t]) for t in uni if t in t2c}
    uni_mapped = sorted(t for t, c in uni_ciks.items() if c in perm_by_cik.index)
    out = {"ran_utc": _now(), "ciks_matched_attempted": len(ciks), "names_tried": int(len(m)),
           "names_matched": int(m["permno"].notna().sum()),
           "ciks_with_permno": int(perm_by_cik.size),
           "match_how": m["how"].str.split(" ").str[0].value_counts().to_dict(),
           "universe44_with_sec_ticker": len(uni_ciks), "universe44_mapped": len(uni_mapped),
           "universe44_unmapped": sorted(set(uni_ciks) - set(uni_mapped)),
           "crsp_names_last": str(nm["nameendt"].max().date()),
           "rows_listed_counts": rows["listed"].value_counts().to_dict()}
    _meta("listed", out)
    print(json.dumps(out, indent=1, default=str))
    return out


# ------------------------------------------------------------------ A1

def universe_ciks() -> set[int]:
    """CIKs of the 44 `cef_universe.csv` funds (SEC ticker file). Every one must resolve."""
    tk = sec_tickers_now()
    uni = pd.read_csv(REPO / "data" / "cef" / "cef_universe.csv")["ticker"]
    t2c = dict(zip(tk["ticker"], tk["cik"]))
    missing = sorted(set(uni) - set(t2c))
    if missing:
        raise LookupError(f"universe tickers not in the SEC ticker file: {missing}")
    return {int(t2c[t]) for t in uni}


def per_year(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    d = df.assign(year=df["date_filed"].dt.year, month=df["date_filed"].dt.to_period("M").astype(str))
    d["fund_month"] = d["cik"].astype(str) + "|" + d["month"]
    return d.groupby(by + ["year"]).agg(filings=("accession", "nunique"), funds=("cik", "nunique"),
                                        fund_months=("fund_month", "nunique"),
                                        months=("month", "nunique")).reset_index()


def a1() -> dict:
    """Issuance-supplement counts by year, fund type and form family; listed at the filing date."""
    rows = pd.read_parquet(LISTED_ROWS)
    uni = universe_ciks()
    s = rows[rows["form"].isin(SUPP_FORMS)].copy()
    s["family"] = np.where(s["form"] == "497", "497", "424B")
    s["is_listed"] = s["listed"].str.startswith("listed")
    s["universe44"] = s["cik"].isin(uni)
    # Interval funds are not listed by construction; a listed flag on one is a matcher error.
    bad = s[s["is_listed"] & s["interval"].fillna(False)]
    s["era"] = np.where(s["date_filed"] < REFORM_DATE, "pre_reform", "post_reform")
    all_tab = per_year(s, ["fund_type", "family", "is_listed"])
    all_tab.to_csv(OUT / "a1_supplements_by_year_all.csv", index=False)
    L = s[s["is_listed"]]
    tab = per_year(L, ["fund_type"])
    tab.to_csv(OUT / "a1_listed_supplements_by_year.csv", index=False)
    tab_f = per_year(L, ["fund_type", "family"])
    tab_f.to_csv(OUT / "a1_listed_supplements_by_year_family.csv", index=False)
    both = per_year(L.assign(fund_type="cef_or_bdc"), ["fund_type"])
    ex44 = per_year(L[~L["universe44"]].assign(fund_type="cef_or_bdc_ex44"), ["fund_type"])
    pd.concat([both, ex44]).to_csv(OUT / "a1_listed_supplements_by_year_total.csv", index=False)
    # The sampling frame for the document classifier: listed supplements 2010-2025 (public EDGAR keys).
    frame = L[["cik", "company", "form", "date_filed", "accession", "fund_type", "family", "era", "universe44",
               "ticker_now", "listed"]].copy()
    frame.to_csv(CACHE / "a1_listed_supplement_frame.csv", index=False)

    def summ(t, col):
        t = t.set_index("year")[col].reindex(range(COUNT_START, COUNT_END + 1), fill_value=0)
        return {"per_year": {int(k): int(v) for k, v in t.items()},
                "mean_2010_2022": float(t.loc[2010:2022].mean()), "median_2010_2022": float(t.loc[2010:2022].median()),
                "min_2010_2022": int(t.loc[2010:2022].min()), "mean_2023_2025_counts_only": float(t.loc[2023:2025].mean())}
    out = {"ran_utc": _now(),
           "listed_supplements": {"filings": summ(both, "filings"), "distinct_funds": summ(both, "funds"),
                                  "fund_months": summ(both, "fund_months"), "months": summ(both, "months")},
           "listed_supplements_ex44_distinct_funds": summ(ex44, "funds"),
           "by_type_distinct_funds": {ft: summ(g, "funds") for ft, g in tab.groupby("fund_type")},
           "by_type_family_filings": {f"{a}|{b}": summ(g, "filings") for (a, b), g in tab_f.groupby(["fund_type", "family"])},
           "unlisted_supplement_filings_2010_2025": int((~s["is_listed"]).sum()),
           "listed_flag_on_interval_fund_rows": int(len(bad)),
           "listed_rule_mix": L["listed"].value_counts().to_dict()}
    (OUT / "a1_summary.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    _meta("a1", {"ran_utc": out["ran_utc"]})
    print(tab.pivot(index="year", columns="fund_type", values=["filings", "funds", "fund_months"]).to_string())
    print(json.dumps({k: v for k, v in out.items() if k.startswith("listed_supplements")}, indent=1)[:3000])
    return out


# ------------------------------------------------------------------ capacity and BDC listings

ADV_SESSIONS, ADV_LAG = 20, 2


def capacity() -> dict:
    """Pre-event ADV at listed-supplement filings dated <= 2022-12-31, outside the 44, and BDC listings a year.

    ADV is mean |prc| x vol over the 20 CRSP sessions ending two sessions before
    the filing date (the `ss_catalogue_counts` convention). Only `dsf` rows before
    2023-01-01 are pulled, and the result is asserted. Price x volume is a
    liquidity level, not a return; the 44 `cef_universe.csv` funds are excluded
    anyway. The capacity rule is the corporate catalogue's (§1): a position of 5%
    of book at <= 5% of one session's ADV is usable at book size B when ADV >= B.

    BDC listings a year: the first CRSP name record of each permno mapped to a
    BDC CIK, 2010-2024. Each listing is an occasion for the IPO-attached
    below-NAV 10b5-1 plan that A3 asks about (read in `ssx_fund1_docs.py`).
    """
    from src.data.r2 import connect, r2_path, q
    rows = pd.read_parquet(LISTED_ROWS)
    m = pd.read_csv(CIK_PERMNO).dropna(subset=["permno"])
    nm = crsp_names()
    cef = nm[nm["shrcd"].isin((14, 44))]
    spans = {p: list(zip(g["namedt"], g["nameendt"])) for p, g in cef.groupby("permno")}
    perms = m.groupby("cik")["permno"].agg(lambda v: sorted({int(x) for x in v}))
    uni = universe_ciks()
    s = rows[rows["form"].isin(SUPP_FORMS) & rows["listed"].eq("listed_crsp")
             & (rows["date_filed"] < TIME_HOLDOUT) & ~rows["cik"].isin(uni)].copy()

    def perm_at(cik, d):
        for p in perms.get(cik, []):
            if any(a <= d <= b for a, b in spans.get(p, [])):
                return p
        return None
    s["permno"] = [perm_at(int(c), d) for c, d in zip(s["cik"], s["date_filed"])]
    s = s.dropna(subset=["permno"])
    s["permno"] = s["permno"].astype(int)
    con = connect()
    plist = ",".join(map(str, sorted(s["permno"].unique())))
    px = q(con, f"""SELECT permno, date, abs(prc) * vol AS dv FROM read_parquet('{r2_path("crsp_a_stock", "dsf")}')
                    WHERE permno IN ({plist}) AND date >= DATE '2009-09-01' AND date < DATE '2023-01-01'
                      AND prc IS NOT NULL AND vol IS NOT NULL""")
    px["date"] = pd.to_datetime(px["date"])
    if px["date"].max() >= TIME_HOLDOUT:
        raise RuntimeError("a 2023+ dsf row was read: the time holdout is sealed")
    by = {p: g.sort_values("date") for p, g in px.groupby("permno")}
    adv = []
    for r in s.itertuples(index=False):
        g = by.get(r.permno)
        if g is None:
            adv.append(np.nan)
            continue
        pre = g[g["date"] < r.date_filed].tail(ADV_SESSIONS + ADV_LAG).head(ADV_SESSIONS)
        adv.append(float(pre["dv"].mean()) if len(pre) >= 15 else np.nan)
    s["adv"] = adv
    s[["cik", "accession", "form", "date_filed", "fund_type", "permno", "adv"]].to_csv(CACHE / "a1_supp_pre_event_adv.csv", index=False)

    def cap(a: pd.Series) -> dict:
        a = a.dropna()
        return {"n": int(len(a)), "median_adv_usd": float(a.median()) if len(a) else None,
                "share_ge_100k": float((a >= 1e5).mean()), "share_ge_1m": float((a >= 1e6).mean()),
                "share_ge_10m": float((a >= 1e7).mean())}
    # One row per fund-year (a programme's many supplements are one fund's liquidity, once).
    fy = s.assign(year=s["date_filed"].dt.year).sort_values("date_filed").drop_duplicates(["cik", "year"])
    out = {"ran_utc": _now(), "window": "listed supplements 2010-01-01..2022-12-31, ex-44; dsf rows < 2023",
           "per_filing": {ft: cap(g["adv"]) for ft, g in s.groupby("fund_type")},
           "per_fund_year_first_filing": {ft: cap(g["adv"]) for ft, g in fy.groupby("fund_type")}}
    # BDC listings a year (first CRSP name record of a BDC-mapped permno).
    ft = pd.read_parquet(FUND_TYPES)
    bdc_perms = set(int(p) for p in m[m["cik"].isin(set(ft.loc[ft["fund_type"] == "bdc", "cik"]))]["permno"])
    first = cef[cef["permno"].isin(bdc_perms)].groupby("permno")["namedt"].min()
    yr = first.dt.year.value_counts().sort_index()
    out["bdc_listings_per_year_2010_2024"] = {int(y): int(yr.get(y, 0)) for y in range(2010, 2025)}
    out["bdc_listings_2010_2024_mean"] = float(np.mean([yr.get(y, 0) for y in range(2010, 2025)]))
    (OUT / "a1_a3_capacity_listings.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))
    return out


def shares_crosscheck() -> dict:
    """Second method for A1: fund-years in which CRSP's shares outstanding ROSE, 2010-2025 (a count).

    Source: CRSP CIZ `stkshares` on the R2 mirror (to 2025-12-31 per the data
    librarian's inventory, results/events/ssx/ssx_data/R2_FULL_INVENTORY_TABLES_2026-10-19.md),
    for every permno that ever carried share code 14/44. A share count is not a
    price or a return, so 2023-25 rows may be COUNTED. A step between +0.5% and
    +30% is counted as issuance; a larger step is a merger or a rights offering and
    is excluded; a fall is a buyback or tender. A fund-year counts if its issuance
    steps sum to >= 2%. DRIP issuance at NAV is inside this measure by design: it
    is also new supply sold when the price is above NAV. CRSP updates shares from
    filings with a lag, so this dates the year, not the day.
    """
    from src.data.r2 import connect, r2_path, q
    nm = crsp_names()
    perms = sorted(nm.loc[nm["shrcd"].isin((14, 44)), "permno"].unique())
    con = connect()
    sh = q(con, f"""SELECT permno, shrstartdt, shrenddt, shrout FROM read_parquet('{r2_path("crsp_a_stock", "stkshares")}')
                    WHERE permno IN ({",".join(map(str, perms))}) AND shrenddt >= DATE '2009-01-01'""")
    if sh.empty:
        raise RuntimeError("stkshares returned no rows for share-code 14/44 permnos")
    sh["shrstartdt"] = pd.to_datetime(sh["shrstartdt"])
    sh = sh.sort_values(["permno", "shrstartdt"])
    sh["prev"] = sh.groupby("permno")["shrout"].shift()
    sh["chg"] = sh["shrout"] / sh["prev"] - 1.0
    sh = sh[(sh["shrstartdt"] >= "2010-01-01") & (sh["shrstartdt"] <= "2025-12-31")]
    up = sh[(sh["chg"] >= 0.005) & (sh["chg"] <= 0.30)].assign(year=lambda d: d["shrstartdt"].dt.year)
    fy = up.groupby(["permno", "year"])["chg"].sum().reset_index()
    fy = fy[fy["chg"] >= 0.02]
    m = pd.read_csv(CIK_PERMNO).dropna(subset=["permno"])
    uni_perm = set(int(p) for p in m[m["cik"].isin(universe_ciks())]["permno"])
    ft = pd.read_parquet(FUND_TYPES)
    bdc_perm = set(int(p) for p in m[m["cik"].isin(set(ft.loc[ft["fund_type"] == "bdc", "cik"]))]["permno"])
    out = {"ran_utc": _now(), "rows_last_shrstartdt": str(sh["shrstartdt"].max().date()),
           "fund_years_with_issuance_ge_2pct": {int(y): int(n) for y, n in fy.groupby("year").size().items()},
           "ex44": {int(y): int(n) for y, n in fy[~fy["permno"].isin(uni_perm)].groupby("year").size().items()},
           "bdc_mapped": {int(y): int(n) for y, n in fy[fy["permno"].isin(bdc_perm)].groupby("year").size().items()}}
    s = pd.Series(out["fund_years_with_issuance_ge_2pct"]).reindex(range(2010, 2026), fill_value=0)
    out["mean_2010_2022"] = float(s.loc[2010:2022].mean())
    out["min_2010_2022"] = int(s.loc[2010:2022].min())
    (OUT / "a1_crsp_shares_crosscheck.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("index", "listed", "a1", "a7", "alpaca", "capacity", "shares"))
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    if a.part == "index":
        build_index()
    elif a.part == "listed":
        build_listed()
    elif a.part == "a1":
        a1()
    elif a.part == "a7":
        from scripts.events.ssx.ssx_fund1_a7 import main as a7main
        a7main()
    elif a.part == "shares":
        shares_crosscheck()
    elif a.part == "capacity":
        capacity()
    elif a.part == "alpaca":
        from scripts.events.ssx.ssx_fund1_a7 import alpaca_flags
        alpaca_flags()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
