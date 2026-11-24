"""IPO lifecycle census for the SS-desk expansion (seat ssx_ins): D5 quiet-period expiry and the K5 lock-up gate. Zero trials.

    export QUANTT_ENV_FILE=/abs/path/config/.env     # R2 and the Alpaca cef key; never printed
    python3 scripts/events/ssx/ssx_ins_ipo_census.py edgar    # IPO candidates from offline EDGAR master indexes
    python3 scripts/events/ssx/ssx_ins_ipo_census.py crsp     # D5: CRSP IPO counts 2010-24, ADV at quiet-period end (<= 2022)
    python3 scripts/events/ssx/ssx_ins_ipo_census.py alpaca   # K5: today's shortable/ETB share of recent IPOs

ZERO TRIALS. No return is read. `dsf` is read for price x volume only, for
IPOs whose ADV window ends before 2023-01-01, and the script raises on a 2023+
row. Alpaca: read-only GET /v2/assets (and /v2/clock) through the client's
retrying, key-scrubbing `_get`; no order, cancel or account call exists here.

TWO WAYS TO FIND AN IPO, BECAUSE NEITHER SOURCE FLAGS ONE
--------------------------------------------------------
CRSP has no IPO field (searched `metacolumninfo` for 'ipo'/'initial public',
2026-10-19: nothing). EDGAR has no IPO form either. So:

(1) EDGAR rule (`edgar`): an IPO candidate is the FIRST 424B4 or 424B1 filed by
    a CIK that (a) is not in the repo's fund-CIK set (`fetch_edgar_events.fund_set`),
    (b) filed an S-1 or F-1 (or amendment) before it, and (c) filed no 10-K,
    10-Q, 20-F, 40-F, 8-K, 10-12B, S-3 or F-3 before it, all from the 2008Q1
    master index on (so it was not already a reporting company). SPACs are
    flagged two ways and excluded: the CIK is in the SPAC census universe
    (`results/events/spac_trust_census_universe_2026-10-15.csv`), or the filer
    name matches SPAC_NAME_RE. Its blind spot: a company that filed a 10-K
    before its IPO (registered debt) is missed; a direct listing files no 424B.
(2) CRSP rule (`crsp`): a permno whose first `dsf` date (`dsfhdr.begdat`) falls
    in the year, whose name record at that date has shrcd 10/11 (ordinary
    common: excludes funds 14/44, REITs 18, ADRs 3x, units 7x) and exchcd 1/2/3,
    whose PERMCO first appears on that date too (not a new class of a listed
    issuer), that is not the new security of a CRSP spin-off (`stkdistributions`
    SECSO `dispermno`), and that is not a blank check (siccd 6770 or
    SPAC_NAME_RE on the CRSP name). Its blind spot: OTC uplistings and
    post-bankruptcy relistings also start a new permco. So each CRSP candidate
    is also checked against (1): CONFIRMED if an EDGAR candidate's normalised
    name equals the CRSP name's (or their first 12 characters agree) with the
    424B dated within [-30, +7] days of `begdat`.

D5 CLOCK (rule texts fetched 2026-10-19; see the cards): NASD/NYSE 25 calendar
days before 9 Jul 2002, 40 days from then (non-EGC), and FINRA 2241's minimum
10 days after an IPO for participating underwriters from 2015 (EGCs exempt
from the rule; the post-2012 EGC date is market practice [U]). The ADV here is
measured at three clocks: mean dollar volume over the sessions AFTER the first
trading day and BEFORE calendar day k (k = 10, 25, 40) after it, needing at
least 3 sessions. Day 0 (the IPO day's volume) is excluded on purpose.

K5 GATE (catalogue G-K5): today's Alpaca shortable / easy-to-borrow share of
recent IPOs, (a) those at day 150-210 today (the lock-up window), and (b) all
2025 IPOs still active. Survivorship runs one way: an IPO that has delisted is
absent from the active list and is reported as absent. Flags are true today only.
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

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events" / "ssx" / "ssx_ins"
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_ins"
TIME_HOLDOUT = pd.Timestamp("2023-01-01")
SPAC_NAME_RE = re.compile(r"ACQUISITION|\bACQ\b|BLANK CHECK|\bSPAC\b|MERGER CORP|MERGER SUB")
IPO_FORMS = {"424B4", "424B1"}
REG_FORMS = {"S-1", "S-1/A", "F-1", "F-1/A"}
SEASONED_FORMS = {"10-K", "10-Q", "20-F", "40-F", "8-K", "10-12B", "S-3", "S-3ASR", "F-3", "F-3ASR"}
CLOCKS = (10, 25, 40)
SUFFIX = re.compile(r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|HOLDINGS?|HLDGS|GROUP|GRP|PLC|"
                    r"LLC|L P|LP|SA|S A|NV|N V|AG|SE|THE|CLASS A|CL A|NEW|DE|BERMUDA|CAYMAN)\b")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _meta(part: str, rec: dict) -> None:
    p = OUT / "ipo_meta.json"
    m = json.loads(p.read_text()) if p.exists() else {}
    m[part] = rec
    p.write_text(json.dumps(m, indent=1, default=str) + "\n")


def norm_name(s: str) -> str:
    s = re.sub(r"/[A-Z]{2}/?$", " ", str(s).upper())        # EDGAR state suffix, e.g. 'FOO INC /DE/'
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


# ------------------------------------------------------------------ EDGAR

def edgar() -> None:
    from scripts.data.edgar_client import EdgarClient
    from scripts.data import fetch_edgar_events as fe
    c = EdgarClient(offline=True)
    keep = IPO_FORMS | REG_FORMS | SEASONED_FORMS | fe.MARKER_FORMS | fe.NCSR_FORMS | fe.INSIDER_FORMS
    frames = []
    for y in range(2008, 2027):
        for q in (1, 2, 3, 4):
            frames.append(fe.parse_master_index(c.get_text(fe.INDEX_URL.format(y=y, q=q)),
                                                label=f"{y}Q{q}", keep_forms=keep))
    idx = pd.concat(frames, ignore_index=True)
    funds = set(fe.fund_set(idx))
    last_seen = idx.date_filed.max()
    first = lambda forms: idx[idx.form.isin(forms)].groupby("cik").date_filed.min()
    f_ipo, f_reg, f_seas = first(IPO_FORMS), first(REG_FORMS), first(SEASONED_FORMS)
    cand = f_ipo.rename("ipo_filed").to_frame()
    cand["reg_first"] = f_reg.reindex(cand.index)
    cand["seasoned_first"] = f_seas.reindex(cand.index)
    names = idx[idx.form.isin(IPO_FORMS)].sort_values("date_filed").groupby("cik").company.first()
    cand["name"] = names.reindex(cand.index)
    cand = cand.reset_index()
    spac = pd.read_csv(REPO / "results" / "events" / "spac_trust_census_universe_2026-10-15.csv", usecols=["cik"])
    cand["is_fund"] = cand.cik.isin(funds)
    cand["is_spac"] = cand.cik.isin(set(spac.cik)) | cand.name.str.upper().str.contains(SPAC_NAME_RE)
    cand["has_reg_before"] = cand.reg_first.notna() & (cand.reg_first <= cand.ipo_filed)
    cand["seasoned_before"] = cand.seasoned_first.notna() & (cand.seasoned_first < cand.ipo_filed)
    # 2008 is look-back only: a CIK whose first 424B falls in 2008 may have filed one in 2007.
    cand["year"] = cand.ipo_filed.dt.year
    cand["ipo_candidate"] = ~cand.is_fund & ~cand.is_spac & cand.has_reg_before & ~cand.seasoned_before
    cand["norm"] = cand.name.map(norm_name)
    CACHE.mkdir(parents=True, exist_ok=True)
    cand.to_parquet(CACHE / "edgar_ipo_candidates.parquet", index=False)
    g = cand[cand.year >= 2009].groupby("year").agg(
        first_424b_ciks=("cik", "size"), funds=("is_fund", "sum"), spacs=("is_spac", "sum"),
        no_s1_f1_before=("has_reg_before", lambda s: int((~s).sum())),
        seasoned_before=("seasoned_before", "sum"), ipo_candidates=("ipo_candidate", "sum")).reset_index()
    g.to_csv(OUT / "edgar_ipo_candidates_by_year.csv", index=False)
    _meta("edgar", {"ran_utc": _now(), "index": "2008Q1-2026Q4 master.gz, offline cache (fetched 2026-10-12)",
                    "last_date_filed_seen": str(last_seen.date()), "live_requests": c.n_requests,
                    "fund_set_size": len(funds)})
    print(g.to_string(index=False))


# ------------------------------------------------------------------ CRSP (D5)

def crsp() -> None:
    from src.data.r2 import connect, r2_path, q
    con = connect()
    P = lambda t: r2_path("crsp_a_stock", t)
    h = q(con, f"SELECT permno, permco, begdat FROM read_parquet('{P('dsfhdr')}')")
    h["begdat"] = pd.to_datetime(h.begdat)
    permco_first = h.groupby("permco").begdat.min()
    h = h[(h.begdat >= "2010-01-01") & (h.begdat <= "2024-12-31")]
    nm = q(con, f"""SELECT permno, namedt, nameenddt, shrcd, exchcd, siccd, comnam, ticker
                    FROM read_parquet('{P('stocknames')}') WHERE nameenddt >= DATE '2009-12-01'""")
    nm["namedt"], nm["nameenddt"] = pd.to_datetime(nm.namedt), pd.to_datetime(nm.nameenddt)
    x = h.merge(nm, on="permno")
    x = x[(x.namedt <= x.begdat) & (x.nameenddt >= x.begdat)].drop_duplicates("permno")
    spin = set(q(con, f"""SELECT DISTINCT dispermno FROM read_parquet('{P('stkdistributions')}')
                          WHERE disdetailtype = 'SECSO' AND dispermno IS NOT NULL""").dispermno.astype(int))
    x["year"] = x.begdat.dt.year
    x["f_common"] = x.shrcd.isin([10, 11])
    x["f_exch"] = x.exchcd.isin([1, 2, 3])
    x["f_new_permco"] = x.permco.map(permco_first) == x.begdat
    x["f_not_spin"] = ~x.permno.isin(spin)
    x["f_not_spac"] = (x.siccd != 6770) & ~x.comnam.fillna("").str.upper().str.contains(SPAC_NAME_RE)
    steps = ["f_common", "f_exch", "f_new_permco", "f_not_spin", "f_not_spac"]
    x["crsp_ipo"] = x[steps].all(axis=1)
    # EDGAR confirmation
    ec = CACHE / "edgar_ipo_candidates.parquet"
    if not ec.exists():
        raise FileNotFoundError(f"{ec}: run the edgar part first")
    e = pd.read_parquet(ec)
    e = e[e.ipo_candidate]
    x["norm"] = x.comnam.map(norm_name)
    ipo = x[x.crsp_ipo].copy()
    conf = []
    for r in ipo.itertuples(index=False):
        w = e[(e.ipo_filed >= r.begdat - pd.Timedelta(days=30)) & (e.ipo_filed <= r.begdat + pd.Timedelta(days=7))]
        exact = (w.norm == r.norm).any()
        pref = (w.norm.str[:12] == r.norm[:12]).any() if len(r.norm) >= 4 else False
        conf.append("exact" if exact else ("prefix12" if pref else "none"))
    ipo["edgar_confirm"] = conf
    # funnel by year
    fun = []
    for y, g in x.groupby("year"):
        row = {"year": y, "new_permnos": len(g)}
        m = pd.Series(True, index=g.index)
        for s in steps:
            m &= g[s]
            row[f"after_{s}"] = int(m.sum())
        gi = ipo[ipo.year == y]
        row["edgar_confirmed"] = int((gi.edgar_confirm != "none").sum())
        row["edgar_confirmed_exact"] = int((gi.edgar_confirm == "exact").sum())
        fun.append(row)
    fun = pd.DataFrame(fun)
    # ADV at the quiet-period clocks, IPOs whose 40-day window ends before 2023.
    pre = ipo[ipo.begdat + pd.Timedelta(days=max(CLOCKS)) < TIME_HOLDOUT][["permno", "begdat"]].copy()
    con.register("ipo_tbl", pre)
    dv = q(con, f"""SELECT d.permno, d.date, abs(d.prc) * d.vol AS dv
                    FROM ipo_tbl i JOIN read_parquet('{P('dsf')}') d
                      ON d.permno = i.permno AND d.date > i.begdat AND d.date < i.begdat + INTERVAL {max(CLOCKS)} DAY
                    WHERE d.date < DATE '2023-01-01' AND d.prc IS NOT NULL AND d.vol IS NOT NULL""")
    dv["date"] = pd.to_datetime(dv.date)
    if len(dv) and dv.date.max() >= TIME_HOLDOUT:
        raise RuntimeError("a 2023+ dsf row was read: the time holdout is sealed")
    dv = dv.merge(pre, on="permno")
    advs = {}
    for k in CLOCKS:
        w = dv[dv.date < dv.begdat + pd.Timedelta(days=k)]
        a = w.groupby("permno").dv.agg(["mean", "size"])
        advs[k] = a.loc[a["size"] >= 3, "mean"]
    for k in CLOCKS:
        ipo[f"adv_d{k}"] = ipo.permno.map(advs[k])
    ipo.drop(columns=["norm"]).to_parquet(CACHE / "crsp_ipos.parquet", index=False)   # licensed: cache only
    rows = []
    for y, g in ipo.groupby("year"):
        r = {"year": y, "crsp_ipos": len(g), "edgar_confirmed": int((g.edgar_confirm != "none").sum())}
        for k in CLOCKS:
            s = g[f"adv_d{k}"]
            r[f"with_adv_d{k}"] = int(s.notna().sum())
            r[f"adv_ge_1m_d{k}"] = int((s >= 1e6).sum())
            r[f"adv_ge_1m_d{k}_confirmed"] = int(((s >= 1e6) & (g.edgar_confirm != "none")).sum())
            r[f"median_adv_d{k}"] = float(s.median()) if s.notna().any() else None
        rows.append(r)
    adv = pd.DataFrame(rows)
    fun.to_csv(OUT / "d5_crsp_ipo_funnel_by_year.csv", index=False)
    adv.to_csv(OUT / "d5_crsp_ipo_adv_by_year.csv", index=False)
    _meta("crsp", {"ran_utc": _now(), "count_window": "2010-01-01..2024-12-31 (counts)",
                   "adv_window": "IPOs with begdat + 40d < 2023-01-01; dsf < 2023 only",
                   "spin_off_children_excluded_total": int(len(spin))})
    pd.set_option("display.width", 250)
    print(fun.to_string(index=False))
    print(adv.to_string(index=False))


# ------------------------------------------------------------------ Alpaca (K5)

def alpaca() -> None:
    from quantt.broker.alpaca import AlpacaClient
    c = AlpacaClient.from_environment("cef")
    clock = c.clock()
    ts = clock["timestamp"]
    today = pd.Timestamp(ts.date() if hasattr(ts, "date") else str(ts)[:10])
    raw = c._get(c._base, "/v2/assets", {"status": "active", "asset_class": "us_equity"})   # read-only GET
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("GET /v2/assets returned no rows")
    A = pd.DataFrame([{k: a.get(k) for k in ("symbol", "name", "exchange", "tradable", "shortable",
                                              "easy_to_borrow", "attributes")} for a in raw])
    if A.symbol.duplicated().any():
        raise RuntimeError("GET /v2/assets: a symbol appears twice")
    A = A.set_index("symbol")
    tk_path = REPO / "results" / "events" / "_cache_edgar" / "www.sec.gov" / "files" / "company_tickers_exchange.json"
    tj = json.loads(tk_path.read_text())
    T = pd.DataFrame(tj["data"], columns=tj["fields"])
    e = pd.read_parquet(CACHE / "edgar_ipo_candidates.parquet")
    e = e[e.ipo_candidate].copy()
    e["age_days"] = (today - e.ipo_filed).dt.days
    e = e[(e.ipo_filed >= "2025-01-01")]
    m = e.merge(T, on="cik", how="left")
    # One CIK can carry several tickers (units, warrants, classes). Keep common-looking ones:
    # drop symbols ending in W/WS/U/R suffix forms and preferreds ('-P').
    common_like = m.ticker.notna() & ~m.ticker.fillna("").str.contains(r"(?:-P|\.U|\.WS|-WT|-UN)", regex=True)
    m = m[common_like | m.ticker.isna()]
    m["at_alpaca"] = m.ticker.isin(A.index)
    for f in ("tradable", "shortable", "easy_to_borrow", "exchange"):
        m[f] = m.ticker.map(A[f]) if f != "exchange" else m.ticker.map(A["exchange"])
    m["ipo_attr"] = m.ticker.map(A["attributes"]).map(lambda v: isinstance(v, list) and "ipo" in v)
    m.to_parquet(CACHE / "k5_ipo_alpaca_flags.parquet", index=False)

    def summ(d: pd.DataFrame) -> dict:
        per_cik = d.groupby("cik").agg(any_ticker=("ticker", lambda s: s.notna().any()),
                                       at_alpaca=("at_alpaca", "any"),
                                       shortable=("shortable", lambda s: bool((s == True).any())),   # noqa: E712
                                       etb=("easy_to_borrow", lambda s: bool((s == True).any())))    # noqa: E712
        n = len(per_cik)
        act = per_cik[per_cik.at_alpaca]
        return {"ipo_ciks": n, "with_sec_ticker_2026_10_12": int(per_cik.any_ticker.sum()),
                "active_at_alpaca": int(len(act)), "shortable": int(act.shortable.sum()),
                "easy_to_borrow": int(act.etb.sum()),
                "shortable_share_of_active": float(act.shortable.mean()) if len(act) else None,
                "etb_share_of_active": float(act.etb.mean()) if len(act) else None}

    near = m[(m.age_days >= 150) & (m.age_days <= 210)]
    y25 = m[m.ipo_filed.dt.year == 2025]
    by_month = {str(k): summ(g) for k, g in y25.groupby(y25.ipo_filed.dt.to_period("M"))}
    rec = {"ran_utc": _now(), "alpaca_clock": str(ts), "today": str(today.date()), "n_active_assets": int(len(A)),
           "sec_ticker_file": "company_tickers_exchange.json fetched 2026-10-12 (cached)",
           "near_day_150_210": {"ipo_window": [str((today - pd.Timedelta(days=210)).date()),
                                               str((today - pd.Timedelta(days=150)).date())], **summ(near)},
           "all_2025": summ(y25), "by_month_2025": by_month,
           "ipo_attribute_seen": int(m.ipo_attr.sum())}
    _meta("alpaca_k5", rec)
    print(json.dumps(rec, indent=1, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("edgar", "crsp", "alpaca"))
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    {"edgar": edgar, "crsp": crsp, "alpaca": alpaca}[a.part]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
