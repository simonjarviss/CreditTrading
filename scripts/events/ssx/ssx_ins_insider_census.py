"""Census of open-market insider purchases (Form 4 code P): D1 clusters in operating companies, A2 in CEFs/BDCs.

    export QUANTT_ENV_FILE=/abs/path/config/.env     # R2 for the CRSP part; never printed
    python3 scripts/events/ssx/ssx_ins_fetch.py extract --offline        # first: row-level code-P tables
    python3 scripts/events/ssx/ssx_ins_insider_census.py fundset          # EDGAR master indexes, offline
    python3 scripts/events/ssx/ssx_ins_insider_census.py census           # counts, lags, clusters, fund-events
    python3 scripts/events/ssx/ssx_ins_insider_census.py crsp             # symbol -> permno, pre-event ADV (<= 2022)

ZERO TRIALS. Nothing here reads a return. The CRSP part reads `dsf` price x
volume for sessions BEFORE each event, for events dated <= 2022-12-31, and
raises if a 2023+ `dsf` row comes back. Counts may run to 2025-12-31 (the
brief's rule: event counts are not returns). No statistic of any kind is
computed for a `data/cef/cef_universe.csv` name beyond a count.

RULES FIXED BEFORE ANY OUTCOME WAS LOOKED AT (2026-10-19; there is no outcome in
this script to look at, but the rules are written here so a later trial
inherits them rather than re-choosing them):

* A PURCHASE is a NONDERIV_TRANS row on an ORIGINAL Form 4 (DOCUMENT_TYPE '4';
  4/A and Form 5 are counted separately and never enter an event, so an
  amendment cannot double-count a trade), TRANS_CODE 'P', TRANS_ACQUIRED_DISP_CD
  'A', shares > 0 and price > 0. TRANS_DATE must lie in [FILING_DATE - 365d,
  FILING_DATE]; rows outside are counted as date errors and dropped.
* D1 equity filter: SECURITY_TITLE matches COMMON|ORDINARY|CLASS [A-Z]|SHARES|STOCK
  and does not match PREFERRED|PFD|NOTE|DEBENTURE|BOND|WARRANT|RIGHT|UNIT|DEPOSITARY.
  (Units are excluded on purpose: MLP common units are a separate wrapper.)
* D1 insiders are DIRECTORS and OFFICERS only (RPTOWNER_RELATIONSHIP contains
  'Director' or 'Officer'; the string is comma-joined and sometimes missing the
  comma, e.g. 'TenPercentOwnerOther', so flags are substring tests). A
  ten-percent holder who is neither is excluded: that population is activist
  funds and blockholders, the graveyard's "following activist 13Ds".
* D1 CLUSTER: for each issuer, walk its filing dates f in order. The qualifying
  set at f is every D/O purchase FILED on or before f with TRANS_DATE in
  [f - 30d, f]. An event fires at the first f where the set holds >= 3 distinct
  reporting-owner CIKs AND >= 3 distinct accession numbers (the second
  condition stops one joint filing from counting as several insiders). The
  event's PIT date is f, the filing date of the filing that completed it.
  After an event, that issuer cannot fire again until f > event + 90d
  (independence: one event per issuer per quarter at most).
* A cluster whose qualifying purchases ALL carry one price (to the cent) on ONE
  trade date is labelled 'single_price': the signature of an offering,
  directed-share or private-placement purchase, not open-market buying. The
  clean count excludes them.
* A2 fund issuers: ISSUERCIK in the repo's fund-CIK set
  (`scripts/data/fetch_edgar_events.py::fund_set`, marker forms or N-CSR plus
  Form 3/4, from the 2008Q1-2025Q4 master indexes, offline). SIC 6726 is NOT
  used (the index carries no SIC). BDC = filed N-54A/N-54C (BDC election or
  withdrawal) or files 10-K with no N-CSR; CEF = files N-CSR; else
  'fund_other'. A2 uses the D1 equity-title filter (fund preferreds out).
  A2 owner classes (REVISED 2026-10-19 after reading the first pass's owner
  names, before any outcome existed: the first rule's 'adviser_entity' class
  was mostly activists -- Saba, Bulldog, the Horejsi trusts, City of London --
  because it accepted any entity that was a ten-percent holder):
    'DO'             director or officer;
    'adviser'        not DO, and the owner NAME matches ADVIS[EO]R/ADVISORY or the
                     relationship's 'other' text matches ADVIS (e.g. 'Investment
                     adviser to issuer', 'Affiliate of investment adviser');
    'other_person'   relationship 'Other', not ten-percent, no adviser text, and a
                     natural person (no ENTITY_RE word): usually portfolio
                     managers and trustees, who report under 1940 Act s30(h) as
                     affiliated persons of the adviser;
    'ten_pct_only'   ten-percent holder with no adviser text (activists and
                     blockholders: excluded from A2 events, the graveyard's
                     'following activist 13Ds');
    'other_entity'   anything else (insurance companies, group members): excluded.
  A2 is reported with and without a $10,000 floor per purchase, declared
  before the counts: 41% of CEF and 55% of BDC code-P purchases on the first
  pass were under $10k, and BDC purchases under $1k (32%) look like dividend
  reinvestment reported as P.
* A2 FUND-EVENT: per fund, the first filing date with >= 1 qualifying purchase
  (classes DO, adviser_entity, other_person) after a >= 90-day gap since the
  fund's previous event. A stricter variant needs >= 2 distinct owners within
  30 days. Cross-fund dependence (one owner buying several funds of a family
  on one day) is reported as distinct (triggering owner, month) groups.

FILING LAG is counted in SEC business days (US federal holidays, pandas'
USFederalHolidayCalendar; EDGAR follows the federal calendar [S]), from
TRANS_DATE to FILING_DATE. Form 4 has been due within two business days since
29 Aug 2002 (Sarbanes-Oxley s403 [S]); all data here post-date it.

OUTPUTS (aggregates in results/events/ssx/ssx_ins/; row-level CRSP-matched
rows in results/events/ssx/_cache_ssx_ins/ only).
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events" / "ssx" / "ssx_ins"
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_ins"
FORM345 = CACHE / "form345"
TIME_HOLDOUT = pd.Timestamp("2023-01-01")
COUNT_END = pd.Timestamp("2025-12-31")
CLUSTER_WINDOW_D, CLUSTER_MIN, COOLDOWN_D = 30, 3, 90
EQUITY_RE = re.compile(r"COMMON|ORDINARY|CLASS [A-Z]\b|SHARES|STOCK")
NON_EQUITY_RE = re.compile(r"PREFERRED|PFD|NOTE|DEBENTURE|BOND|WARRANT|RIGHT|\bUNITS?\b|DEPOSITARY")
ADVISER_NAME_RE = re.compile(r"ADVIS[EO]RS?\b|ADVISORY")
ADVISER_TXT_RE = re.compile(r"ADVIS|INV\.? ADV")
ENTITY_RE = re.compile(r"\b(?:LLC|L\.L\.C|L\.?P|INC|CORP|CORPORATION|CO|COMPANY|LTD|PLC|GROUP|TRUST|PARTNERS|"
                       r"PARTNERSHIP|FUND|HOLDINGS|MANAGEMENT|CAPITAL|ADVISORS?|ADVISERS?|BANK|INSURANCE|N\.A|S\.A)\b")
A2_FLOOR_USD = 10_000.0
ERAS = [(2006, 2009), (2010, 2014), (2015, 2019), (2020, 2022), (2023, 2025)]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _meta(part: str, rec: dict) -> None:
    p = OUT / "census_meta.json"
    m = json.loads(p.read_text()) if p.exists() else {}
    m[part] = rec
    p.write_text(json.dumps(m, indent=1, default=str) + "\n")


# ------------------------------------------------------------------ fund set

def fundset() -> None:
    """Fund-issuer CIKs from the offline EDGAR master indexes (no live request)."""
    from scripts.data.edgar_client import EdgarClient
    from scripts.data import fetch_edgar_events as fe
    c = EdgarClient(offline=True)
    keep = fe.MARKER_FORMS | fe.NCSR_FORMS | fe.INSIDER_FORMS | {"10-K", "N-54A", "N-54C"}
    frames = []
    for y in range(2008, 2026):
        for q in (1, 2, 3, 4):
            text = c.get_text(fe.INDEX_URL.format(y=y, q=q))
            df = fe.parse_master_index(text, label=f"{y}Q{q}", keep_forms=keep)
            frames.append(df[["cik", "form"]].drop_duplicates())
    idx = pd.concat(frames, ignore_index=True).drop_duplicates()
    rule = fe.fund_set(idx)
    forms = idx.groupby("cik").form.agg(lambda s: set(s))
    rows = []
    for cik, r in rule.items():
        f = forms.get(cik, set())
        if f & {"N-54A", "N-54C"} or ("10-K" in f and "N-CSR" not in f):
            kind = "BDC"
        elif "N-CSR" in f:
            kind = "CEF"
        else:
            kind = "fund_other"
        rows.append({"cik": int(cik), "set_rule": r, "kind": kind})
    fs = pd.DataFrame(rows)
    CACHE.mkdir(parents=True, exist_ok=True)
    fs.to_parquet(CACHE / "fund_set.parquet", index=False)
    rec = {"ran_utc": _now(), "index_quarters": "2008Q1-2025Q4 (offline cache)", "live_requests": c.n_requests,
           "n_fund_ciks": int(len(fs)),
           "by_rule_kind": {f"{a}|{b}": int(n) for (a, b), n in fs.groupby(["set_rule", "kind"]).size().items()}}
    _meta("fundset", rec)
    print(json.dumps(rec, indent=1, default=str))


# ------------------------------------------------------------------ load

def load_purchases() -> tuple[pd.DataFrame, dict]:
    fs = sorted(glob.glob(str(FORM345 / "*_ptrans.parquet")))
    if len(fs) != 80:
        raise RuntimeError(f"expected 80 quarterly code-P tables (2006Q1-2025Q4), found {len(fs)}: run the extract")
    p = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    diag = {"p_rows_x_owner_all_docs": int(len(p)),
            "p_trans_by_doctype": p.drop_duplicates(["ACCESSION_NUMBER", "NONDERIV_TRANS_SK"])
                                   .DOCUMENT_TYPE.value_counts().to_dict()}
    p = p[p.DOCUMENT_TYPE == "4"]
    n0 = p.drop_duplicates(["ACCESSION_NUMBER", "NONDERIV_TRANS_SK"]).shape[0]
    p = p[(p.TRANS_ACQUIRED_DISP_CD == "A") & (p.TRANS_SHARES > 0) & (p.TRANS_PRICEPERSHARE > 0)]
    n1 = p.drop_duplicates(["ACCESSION_NUMBER", "NONDERIV_TRANS_SK"]).shape[0]
    lag_d = (p.FILING_DATE - p.TRANS_DATE).dt.days
    bad = p.TRANS_DATE.isna() | (lag_d < 0) | (lag_d > 365)
    diag.update({"form4_p_trans": n0, "after_A_shares_price_gt0": n1,
                 "date_error_rows_dropped": int(bad.sum())})
    p = p[~bad].copy()
    rel = p.RPTOWNER_RELATIONSHIP.fillna("")
    p["is_dir"] = rel.str.contains("Director")
    p["is_off"] = rel.str.contains("Officer")
    p["is_ten"] = rel.str.contains("TenPercent")
    p["is_oth"] = rel.str.contains("Other")
    p["title_u"] = p.SECURITY_TITLE.fillna("").str.upper()
    p["equity_title"] = p.title_u.str.contains(EQUITY_RE) & ~p.title_u.str.contains(NON_EQUITY_RE)
    p["issuercik"] = pd.to_numeric(p.ISSUERCIK, errors="raise").astype("int64")
    p["ownercik"] = pd.to_numeric(p.RPTOWNERCIK, errors="raise").astype("int64")
    p["usd"] = p.TRANS_SHARES * p.TRANS_PRICEPERSHARE
    p["fyear"] = p.FILING_DATE.dt.year
    return p, diag


def _bdays(start: pd.Series, end: pd.Series) -> np.ndarray:
    from pandas.tseries.holiday import USFederalHolidayCalendar
    hol = USFederalHolidayCalendar().holidays("2005-01-01", "2026-12-31").values.astype("datetime64[D]")
    return np.busday_count(start.values.astype("datetime64[D]"), end.values.astype("datetime64[D]"), holidays=hol)


# ------------------------------------------------------------------ clusters

def clusters(d: pd.DataFrame, min_n: int, window_d: int, cooldown_d: int) -> pd.DataFrame:
    """Events per the module docstring's D1 rule. `d`: one row per (accession, trans SK, owner)."""
    out = []
    for cik, g in d.groupby("issuercik", sort=False):
        g = g.sort_values(["FILING_DATE", "TRANS_DATE"])
        fdates = g.FILING_DATE.drop_duplicates().values
        fd = g.FILING_DATE.values
        td = g.TRANS_DATE.values
        own = g.ownercik.values
        acc = g.ACCESSION_NUMBER.values
        last_event = None
        for f in fdates:
            if last_event is not None and f <= last_event + np.timedelta64(cooldown_d, "D"):
                continue
            m = (fd <= f) & (td >= f - np.timedelta64(window_d, "D")) & (td <= f)
            if last_event is not None:
                m &= fd > last_event      # nothing filed before the previous event re-enters
            if len(set(own[m])) >= min_n and len(set(acc[m])) >= min_n:
                q = g[m]
                trig = q[q.FILING_DATE == q.FILING_DATE.max()]   # the latest qualifying filing (f itself unless f is the first date after a cooldown)
                prices = q.TRANS_PRICEPERSHARE.round(2).unique()
                out.append({"issuercik": cik, "event_date": pd.Timestamp(f),
                            "symbol": str(trig.ISSUERTRADINGSYMBOL.iloc[-1]).strip().upper(),
                            "issuername": trig.ISSUERNAME.iloc[-1],
                            "n_insiders": int(len(set(own[m]))), "n_filings": int(len(set(acc[m]))),
                            "first_trans": q.TRANS_DATE.min(), "last_trans": q.TRANS_DATE.max(),
                            "usd": float(q.drop_duplicates(["ACCESSION_NUMBER", "NONDERIV_TRANS_SK"]).usd.sum()),
                            "single_price": bool(len(prices) == 1 and q.TRANS_DATE.nunique() == 1)})
                last_event = f
    return pd.DataFrame(out)


def fund_events(d: pd.DataFrame, min_owners: int, window_d: int, gap_d: int) -> pd.DataFrame:
    out = []
    for cik, g in d.groupby("issuercik", sort=False):
        g = g.sort_values(["FILING_DATE", "TRANS_DATE"])
        fd, td, own = g.FILING_DATE.values, g.TRANS_DATE.values, g.ownercik.values
        last = None
        for f in g.FILING_DATE.drop_duplicates().values:
            if last is not None and f <= last + np.timedelta64(gap_d, "D"):
                continue
            m = (fd <= f) & (td >= f - np.timedelta64(window_d, "D"))
            if last is not None:
                m &= fd > last
            if len(set(own[m])) >= min_owners:
                q = g[m]
                trig = q[q.FILING_DATE == q.FILING_DATE.max()]   # the latest qualifying filing (f itself unless f is the first date after a cooldown)
                out.append({"issuercik": cik, "event_date": pd.Timestamp(f), "kind": g.kind.iloc[0],
                            "symbol": str(trig.ISSUERTRADINGSYMBOL.iloc[-1]).strip().upper(),
                            "issuername": trig.ISSUERNAME.iloc[-1],
                            "trigger_owner": int(trig.ownercik.iloc[0]),
                            "owner_classes": "|".join(sorted(set(q.oclass))),
                            "n_owners": int(len(set(own[m]))),
                            "usd": float(q.drop_duplicates(["ACCESSION_NUMBER", "NONDERIV_TRANS_SK"]).usd.sum())})
                last = f
    return pd.DataFrame(out)


def _per_year(ev: pd.DataFrame, extra: dict | None = None) -> pd.DataFrame:
    ev = ev.assign(year=ev.event_date.dt.year, month=ev.event_date.dt.to_period("M"))
    agg = {"events": ("issuercik", "size"), "issuers": ("issuercik", "nunique"), "months": ("month", "nunique")}
    agg.update(extra or {})
    return ev.groupby("year").agg(**agg).reset_index()


# ------------------------------------------------------------------ census

def census() -> None:
    p, diag = load_purchases()
    fsp = CACHE / "fund_set.parquet"
    if not fsp.exists():
        raise FileNotFoundError(f"{fsp}: run the fundset part first")
    fset = pd.read_parquet(fsp)
    kind = dict(zip(fset.cik, fset.kind))
    p["kind"] = p.issuercik.map(kind).fillna("operating")   # a CIK outside the fund set IS the operating class
    tx = p.drop_duplicates(["ACCESSION_NUMBER", "NONDERIV_TRANS_SK"])

    # 1. Per-year purchase counts (all Form 4 code-P purchases; then D/O equity, operating issuers).
    yr = tx.groupby("fyear").agg(p_trans=("NONDERIV_TRANS_SK", "size"), p_filings=("ACCESSION_NUMBER", "nunique"),
                                 issuers=("issuercik", "nunique"), usd_total=("usd", "sum")).reset_index()
    do = p[(p.is_dir | p.is_off) & p.equity_title & (p.kind == "operating")]
    dotx = do.drop_duplicates(["ACCESSION_NUMBER", "NONDERIV_TRANS_SK"])
    yr2 = dotx.groupby("fyear").agg(do_equity_trans=("NONDERIV_TRANS_SK", "size"),
                                    do_equity_filings=("ACCESSION_NUMBER", "nunique"),
                                    do_equity_issuers=("issuercik", "nunique"),
                                    do_equity_owners=("ownercik", "nunique")).reset_index()
    years = yr.merge(yr2, on="fyear", how="outer")
    years.to_csv(OUT / "d1_purchases_by_year.csv", index=False)

    # 2. Filing lag (business days), all Form 4 code-P purchases, by era.
    tx = tx.assign(lag_bd=_bdays(tx.TRANS_DATE, tx.FILING_DATE))
    lag_rows = []
    for a, b in ERAS + [(2006, 2025)]:
        s = tx[(tx.fyear >= a) & (tx.fyear <= b)].lag_bd
        lag_rows.append({"era": f"{a}-{b}", "n": int(len(s)), "share_le_2bd": float((s <= 2).mean()),
                         "share_le_1bd": float((s <= 1).mean()), "share_0bd": float((s == 0).mean()),
                         "p50": float(s.quantile(.5)), "p90": float(s.quantile(.9)), "p99": float(s.quantile(.99)),
                         "share_gt_10bd": float((s > 10).mean())})
    pd.DataFrame(lag_rows).to_csv(OUT / "form4_p_filing_lag_by_era.csv", index=False)

    # 3. D1 clusters (operating issuers, D/O, equity titles).
    ev = clusters(do, CLUSTER_MIN, CLUSTER_WINDOW_D, COOLDOWN_D)
    if ev.empty:
        raise RuntimeError("no D1 cluster events: the rule or the data is wrong")
    ev.to_parquet(CACHE / "d1_cluster_events.parquet", index=False)
    d1y = _per_year(ev, {"single_price": ("single_price", "sum"),
                         "median_usd": ("usd", "median")})
    clean = ev[~ev.single_price]
    d1c = _per_year(clean).rename(columns={"events": "clean_events", "issuers": "clean_issuers",
                                           "months": "clean_months"})
    d1y = d1y.merge(d1c, on="year", how="left")
    ev["lag_bd"] = _bdays(ev.last_trans, ev.event_date)
    d1y.to_csv(OUT / "d1_clusters_by_year.csv", index=False)

    # 4. A2: fund issuers.
    f = p[(p.kind != "operating") & p.equity_title].copy()
    nm = f.RPTOWNERNAME.fillna("").str.upper()
    txt = f.RPTOWNER_TXT.fillna("").str.upper()
    adv = nm.str.contains(ADVISER_NAME_RE) | txt.str.contains(ADVISER_TXT_RE)
    entity = nm.str.contains(ENTITY_RE)
    do_ = f.is_dir | f.is_off
    f["oclass"] = np.select(
        [do_, adv, f.is_oth & ~f.is_ten & ~entity, f.is_ten],
        ["DO", "adviser", "other_person", "ten_pct_only"], default="other_entity")
    f.to_parquet(CACHE / "a2_fund_purchases.parquet", index=False)
    ftx = f.drop_duplicates(["ACCESSION_NUMBER", "NONDERIV_TRANS_SK", "oclass"])
    a2y = ftx.groupby(["fyear", "kind", "oclass"]).agg(trans=("NONDERIV_TRANS_SK", "size"),
                                                       funds=("issuercik", "nunique"),
                                                       usd_total=("usd", "sum"),
                                                       usd_median=("usd", "median")).reset_index()
    a2y.to_csv(OUT / "a2_fund_purchases_by_year_kind_class.csv", index=False)
    q = f[f.oclass.isin(["DO", "adviser", "other_person"])]
    fev = fund_events(q, 1, CLUSTER_WINDOW_D, COOLDOWN_D)
    fev2 = fund_events(q, 2, CLUSTER_WINDOW_D, COOLDOWN_D)
    fevf = fund_events(q[q.usd >= A2_FLOOR_USD], 1, CLUSTER_WINDOW_D, COOLDOWN_D)
    fev.to_parquet(CACHE / "a2_fund_events.parquet", index=False)
    fev2.to_parquet(CACHE / "a2_fund_events_2owners.parquet", index=False)
    fevf.to_parquet(CACHE / "a2_fund_events_floor10k.parquet", index=False)
    fev["grp"] = fev.trigger_owner.astype(str) + "|" + fev.event_date.dt.to_period("M").astype(str)
    a2e = (fev.assign(year=fev.event_date.dt.year)
           .groupby(["year", "kind"]).agg(fund_events=("issuercik", "size"), funds=("issuercik", "nunique"),
                                          owner_month_groups=("grp", "nunique"),
                                          with_adviser=("owner_classes", lambda s: s.str.contains("adviser").sum()),
                                          median_usd=("usd", "median")).reset_index())
    a2e2 = (fev2.assign(year=fev2.event_date.dt.year).groupby(["year", "kind"])
            .agg(fund_events_2owners=("issuercik", "size")).reset_index())
    a2ef = (fevf.assign(year=fevf.event_date.dt.year).groupby(["year", "kind"])
            .agg(fund_events_floor10k=("issuercik", "size"),
                 floor10k_with_adviser=("owner_classes", lambda s: s.str.contains("adviser").sum())).reset_index())
    a2e = a2e.merge(a2e2, on=["year", "kind"], how="outer").merge(a2ef, on=["year", "kind"], how="outer")
    a2e.to_csv(OUT / "a2_fund_events_by_year_kind.csv", index=False)
    # dollar-size distribution of qualifying fund purchases (per transaction)
    qtx = q.drop_duplicates(["ACCESSION_NUMBER", "NONDERIV_TRANS_SK"])
    size = {k: {"n": int(len(g)), **{f"p{int(x*100)}": float(g.usd.quantile(x)) for x in (.1, .25, .5, .75, .9, .99)}}
            for k, g in qtx.groupby("kind")}
    # Holdout names: COUNT ONLY (symbol as filed, matched to the universe file's tickers).
    uni = set(pd.read_csv(REPO / "data" / "cef" / "cef_universe.csv").ticker.str.upper())
    in_uni = fev.symbol.isin(uni)
    _meta("census", {"ran_utc": _now(), "diag": diag,
                     "d1_rule": {"window_d": CLUSTER_WINDOW_D, "min_insiders": CLUSTER_MIN, "cooldown_d": COOLDOWN_D},
                     "d1_events_total": int(len(ev)), "d1_clean_total": int(len(clean)),
                     "d1_trigger_lag_bd_p50_p90": [float(ev.lag_bd.quantile(.5)), float(ev.lag_bd.quantile(.9))],
                     "a2_qualifying_purchase_usd_by_kind": size,
                     "a2_owner_class_trans": ftx.oclass.value_counts().to_dict(),
                     "a2_events_total": int(len(fev)), "a2_events_on_cef_universe_symbols_COUNT_ONLY": int(in_uni.sum()),
                     "a2_universe_symbols_with_events_COUNT_ONLY": int(fev[in_uni].symbol.nunique())})
    pd.set_option("display.width", 250)
    print(years.to_string(index=False))
    print(pd.DataFrame(lag_rows).to_string(index=False))
    print(d1y.to_string(index=False))
    print(a2e.to_string(index=False))
    print(json.dumps(size, indent=1))


# ------------------------------------------------------------------ CRSP

def _norm_sym(s: str) -> tuple[str, str | None]:
    s = re.sub(r"\s+", "", s.upper())
    m = re.match(r"^([A-Z]+)[./\-]([A-Z])$", s)
    return (m.group(1), m.group(2)) if m else (s, None)


def crsp() -> None:
    """Symbol-as-filed -> CRSP permno at the event date; pre-event ADV for events <= 2022-12-31."""
    from src.data.r2 import connect, r2_path, q
    con = connect()
    names = q(con, f"""SELECT permno, namedt, nameenddt, shrcd, exchcd, ticker, shrcls
                       FROM read_parquet('{r2_path("crsp_a_stock", "stocknames")}')
                       WHERE nameenddt >= DATE '2005-06-01' AND ticker IS NOT NULL""")
    names["namedt"] = pd.to_datetime(names.namedt)
    names["nameenddt"] = pd.to_datetime(names.nameenddt)
    res = {}
    for label, path in (("d1", CACHE / "d1_cluster_events.parquet"), ("a2", CACHE / "a2_fund_events.parquet"),
                        ("a2floor", CACHE / "a2_fund_events_floor10k.parquet")):
        ev = pd.read_parquet(path)
        ev = ev[ev.event_date <= pd.Timestamp("2024-12-31")].reset_index(drop=True)   # CRSP mirror end
        ev["eid"] = np.arange(len(ev))
        rows = []
        for r in ev.itertuples(index=False):
            base, cls = _norm_sym(r.symbol)
            c = names[(names.ticker == base) & (names.namedt <= r.event_date) & (names.nameenddt >= r.event_date)]
            stage = "exact" if cls is None else "class_suffix"
            if cls is not None and len(c) > 1:
                c = c[c.shrcls.fillna("") == cls]
            if len(c) == 1:
                rows.append({"eid": r.eid, "permno": int(c.permno.iloc[0]), "shrcd": int(c.shrcd.iloc[0]),
                             "exchcd": int(c.exchcd.iloc[0]), "stage": stage})
            else:
                rows.append({"eid": r.eid, "permno": None, "shrcd": None, "exchcd": None,
                             "stage": "none" if len(c) == 0 else "ambiguous"})
        m = ev.merge(pd.DataFrame(rows), on="eid")
        pre = m[(m.event_date < TIME_HOLDOUT) & m.permno.notna()][["eid", "permno", "event_date"]].copy()
        pre["permno"] = pre.permno.astype("int64")
        con.register("ev_tbl", pre)
        adv = q(con, f"""
          WITH x AS (
            SELECT e.eid, d.date, abs(d.prc) * d.vol AS dv,
                   row_number() OVER (PARTITION BY e.eid ORDER BY d.date DESC) AS rn
            FROM ev_tbl e JOIN read_parquet('{r2_path("crsp_a_stock", "dsf")}') d
              ON d.permno = e.permno AND d.date < e.event_date AND d.date >= e.event_date - INTERVAL 45 DAY
            WHERE d.date < DATE '2023-01-01' AND d.prc IS NOT NULL AND d.vol IS NOT NULL)
          SELECT eid, avg(dv) AS adv, count(*) AS n, max(date) AS last_date FROM x
          WHERE rn BETWEEN 3 AND 22 GROUP BY eid""")
        if len(adv) and pd.to_datetime(adv.last_date).max() >= TIME_HOLDOUT:
            raise RuntimeError("a 2023+ dsf row entered the ADV: the time holdout is sealed")
        adv = adv[adv.n >= 15]
        m = m.merge(adv[["eid", "adv"]], on="eid", how="left")
        m.to_parquet(CACHE / f"{label}_events_crsp.parquet", index=False)   # licensed rows: cache only
        m["year"] = m.event_date.dt.year
        com = m.shrcd.isin([10, 11]) if label == "d1" else m.shrcd.notna()
        if label == "d1":
            m["clean"] = ~m.single_price
        else:
            m["clean"] = True
        g = m.groupby("year").agg(events=("eid", "size"), matched=("permno", lambda s: s.notna().sum()),
                                  ambiguous=("stage", lambda s: (s == "ambiguous").sum())).reset_index()
        sub = m[com & m.clean]
        g2 = sub.groupby("year").agg(
            matched_common_clean=("eid", "size"), with_adv=("adv", lambda s: s.notna().sum()),
            adv_ge_100k=("adv", lambda s: int((s >= 1e5).sum())), adv_ge_1m=("adv", lambda s: int((s >= 1e6).sum())),
            adv_ge_10m=("adv", lambda s: int((s >= 1e7).sum())), median_adv=("adv", "median")).reset_index()
        g = g.merge(g2, on="year", how="left")
        g.to_csv(OUT / f"{label}_crsp_match_adv_by_year.csv", index=False)
        win = g[(g.year >= 2010) & (g.year <= 2022)]
        res[label] = {"events_2010_2022": int(win.events.sum()), "matched_2010_2022": int(win.matched.sum()),
                      "match_rate_2010_2022": float(win.matched.sum() / win.events.sum()),
                      "matched_common_clean_2010_2022": int(win.matched_common_clean.sum()),
                      "adv_ge_1m_2010_2022": int(win.adv_ge_1m.sum()),
                      "stage_counts": m.stage.value_counts().to_dict(),
                      "shrcd_counts": m.shrcd.value_counts().to_dict()}
        pd.set_option("display.width", 250)
        print(label); print(g.to_string(index=False))
    _meta("crsp", {"ran_utc": _now(), **res})
    print(json.dumps(res, indent=1, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("fundset", "census", "crsp"))
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    {"fundset": fundset, "census": census, "crsp": crsp}[a.part]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
