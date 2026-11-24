"""Gate 0 of PREREG_C4_LEVEL, pull 2: period-end NAVs of the DEAD C4-family CEFs from EDGAR N-CSR/N-CSRS.

    export QUANTT_ENV_FILE=<absolute path to the env file holding SEC_USER_AGENT>
    python3 results/cef/screens_2026-11-02/gate0_pull_ncsr.py --self-test        # no network
    python3 results/cef/screens_2026-11-02/gate0_pull_ncsr.py --plan \\
        --index-cache <path to the census's index_extra_*.parquet>                # counts only; no filing fetched
    python3 results/cef/screens_2026-11-02/gate0_pull_ncsr.py \\
        --index-cache <path to the census's index_extra_*.parquet>                # the pull (EDGAR, rate-limited)

WHY A SECOND PULL
-----------------
Pull 1 (`gate0_pull_crsp.py`, run 2026-11-02) found 36 CRSP mutual-fund NAV
matches. `gate0_coverage.py` showed 0 match on CUSIP. Only 2 are genuine: the
two First Trust Value Line funds, CEFs that later became ETFs. They give 9
fund-half-years against the survivors' 1,570, so the all-fund slope cannot move
and P(Gate 0 flags a halving) is 0.00. Dead CEFs' NAVs must come from
their own shareholder reports.

SOURCE: SEC EDGAR, the funds' N-CSR (annual) and N-CSRS (semi-annual) reports,
found in EDGAR's quarterly master indexes (https://www.sec.gov/Archives/edgar/
full-index/<y>/QTR<q>/master.gz) and read as complete-submission text. Each
report's CONFORMED PERIOD OF REPORT is its NAV date. The NAV is read with the
census's reader (`scripts/events/cef_corp_action_census.py::nav_beside_price`):
the NAV printed beside a market price equal, to the cent, to CRSP's close on that
period-end. An independent source pins the row, so a multi-fund report cannot
lend one fund's NAV to another. Amendments (/A) are not read.

SCOPE
-----
* Funds: every CRSP CEF permno (share code 14/44) listed inside 2005-01-03..
  2022-12-30 and delisted on or before 2022-12-30, minus C4's 74. Only those
  `gate0_coverage.classify` puts in "C4-candidate" or "unknown" are kept:
  credit, muni, convertible and global/country names are OUT. 190 funds on
  pull 1's data.
* Filers: each N-CSR/N-CSRS filer in the indexes is mapped by name to a
  candidate permno with the census's `CrspMap`, which takes no guesses.
  Unmapped candidates are listed for rulings.
* Filings: filed 2004-01-01..2023-06-30, from 400 days before the fund's
  first fit-window listing to 200 days after its delisting. Only periods
  2004-01-02..min(delisting, 2022-12-30) are kept. A report filed in 2023
  for a 2022 period is read for that period's NAV only; no 2023 return is
  formed anywhere.
* Calibration (the amendment in the slate's Gate 0 note): one report each for
  up to 40 of C4's survivors (seed 20261102). Its NAV is compared with the
  families panel's NAV on the same period-end, which tests whether the live
  funds' panel NAV and the dead funds' report NAV can share one statistic.

RUNTIME AND SIZE [U, estimated 2026-11-02 from the census's cached index]:
* 1,694 filings 2008-01..2023-06 map to 133 candidates. 2004-07 adds an
  estimated 600-900, plus 16 index quarters and about 40 calibration reports.
* At the census's 0.5 s spacing (2 requests a second, under the SEC's
  10/second), that is about 20-25 minutes of spacing.
* Complete submissions run to several MB, so expect 1-2 hours and a few GB of
  cache.
* The EDGAR client caches every response it completes, so a rerun resumes.

WRITES (gitignored by `results/**/_cache_*`; nothing under data/):
* `results/cef/screens_2026-11-02/_cache_gate0/`:
  * `ncsr_map.csv` (filer CIK -> candidate permno, with the reason);
  * `ncsr_unmapped.csv`;
  * `ncsr_navs.parquet` (permno cik accession period close nav layout reason);
  * `ncsr_calibration.parquet`;
  * `ncsr_manifest.json` (counts, the coverage of candidate fund-half-years for
    Gate 0's 80% rule, UTC time; no contact string).
* The raw EDGAR documents go to the shared client cache,
  `results/events/_cache_edgar/` (also gitignored).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

CACHE = HERE / "_cache_gate0"
FIT_START, FIT_END = pd.Timestamp("2005-01-03"), pd.Timestamp("2022-12-30")
PERIOD_START = pd.Timestamp("2004-01-02")
FILED_START, FILED_END = dt.date(2004, 1, 1), dt.date(2023, 6, 30)
FORMS = ("N-CSR", "N-CSRS")
PRE_DAYS, POST_DAYS, MAX_GAP = 400, 200, 5
N_CALIB, SEED = 40, 20261102


def candidates() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(candidate permnos with life and class, CRSP names, CRSP daily prices) from pull 1."""
    from gate0_coverage import classify
    nm = pd.read_parquet(CACHE / "cef_names.parquet")
    for c in ("namedt", "nameenddt"):
        nm[c] = pd.to_datetime(nm[c])
    dl = pd.read_parquet(CACHE / "cef_delist.parquet")
    dl["dlstdt"] = pd.to_datetime(dl["dlstdt"])
    fam = pd.read_csv(REPO / "data" / "cef_families" / "crsp_permno_map.csv")
    c4 = set(pd.read_csv(REPO / "results" / "cef" / "c4" / "c4_universe_frozen_2026-10-14.csv").ticker)
    c4perm = set(fam.loc[fam.ticker.isin(c4), "current_permno"].dropna().astype(int))
    life = nm.groupby("permno").agg(first=("namedt", "min"), last=("nameenddt", "max"), name=("comnam", "last"))
    life = life.join(dl.set_index("permno")[["dlstdt", "dlstcd"]])
    inwin = (life["last"] >= FIT_START) & (life["first"] <= FIT_END)
    dead = life[inwin & (life.dlstdt <= FIT_END) & (life.dlstcd != 100) & ~life.index.isin(c4perm)].copy()
    dead["cls"] = dead["name"].map(classify)
    cand = dead[dead.cls.isin(["C4-candidate", "unknown"])].copy()
    dsf = pd.read_parquet(CACHE / "cef_dsf.parquet", columns=["permno", "date", "prc"])
    dsf["date"] = pd.to_datetime(dsf["date"])
    if dsf["date"].max() > FIT_END:
        raise AssertionError("pull 1's dsf reaches past the fit end")
    survivors = fam[fam.ticker.isin(c4)][["ticker", "current_permno"]].dropna()
    return cand, nm, dsf, survivors


def load_index(client, index_cache: Path | None, today: dt.date) -> pd.DataFrame:
    """N-CSR/N-CSRS rows filed FILED_START..FILED_END: the census's cached index for
    2008-Q1 on (if given), EDGAR's quarterly master indexes for the rest."""
    from scripts.data import fetch_edgar_events as fe
    frames = []
    have_from = None
    if index_cache is not None:
        ix = pd.read_parquet(index_cache)
        ix["date_filed"] = pd.to_datetime(ix["date_filed"])
        frames.append(ix[ix["form"].isin(FORMS)])
        have_from = dt.date(2008, 1, 1)
    end = have_from - dt.timedelta(days=1) if have_from else FILED_END
    qs = fe.quarters(FILED_START, end)
    if client is None:                 # --plan: no request is made, so the uncached quarters are NOT counted
        if index_cache is None:
            raise RuntimeError("--plan needs --index-cache: without it every index quarter would need a request")
        print(f"plan: index quarters {qs[0][0]}Q{qs[0][1]}..{qs[-1][0]}Q{qs[-1][1]} are not cached and are "
              "NOT counted (the pull fetches them)")
        qs = []
    for y, q in qs:
        text = client.get_text(fe.INDEX_URL.format(y=y, q=q),
                               max_age_s=None if fe.quarter_is_closed(y, q, today) else fe.DAY)
        frames.append(fe.parse_master_index(text, label=f"{y}Q{q}", keep_forms=FORMS))
    ix = pd.concat(frames, ignore_index=True)
    ix = ix[(ix.date_filed >= pd.Timestamp(FILED_START)) & (ix.date_filed <= pd.Timestamp(FILED_END))]
    return ix.drop_duplicates("accession")


def map_filers(ix: pd.DataFrame, nm: pd.DataFrame, targets: set) -> pd.DataFrame:
    """Each filer (cik) -> a permno in `targets`, by the census's CrspMap at its first filing date."""
    from scripts.events.cef_corp_action_census import CrspMap
    cm = CrspMap(nm.rename(columns={"nameenddt": "nameendt"}))
    rows = []
    for cik, g in ix.sort_values("date_filed").groupby("cik"):
        r = g.iloc[0]
        p, why = cm.permno(r["company"], None, r["date_filed"])
        if p is not None and p in targets:
            rows.append(dict(cik=int(cik), company=r["company"], permno=int(p), how=why))
    return pd.DataFrame(rows, columns=["cik", "company", "permno", "how"])


def close_at(dsf: pd.DataFrame, permno: int, d) -> tuple[float | None, pd.Timestamp | None]:
    """CRSP's last TRADE close (prc > 0) on or before d, within MAX_GAP days; else None."""
    x = dsf[(dsf.permno == permno) & (dsf.date <= pd.Timestamp(d)) & (dsf.prc > 0)]
    if x.empty:
        return None, None
    x = x.loc[x.date.idxmax()]
    if (pd.Timestamp(d) - x.date).days > MAX_GAP:
        return None, None
    return float(x.prc), x.date


def read_nav(raw: str, close: float) -> dict | None:
    from scripts.events.cef_corp_action_census import nav_beside_price, strip_binary
    from scripts.events.conditional_tender_census import plain
    return nav_beside_price(plain(strip_binary(raw)), close)


def period_of(raw: str) -> pd.Timestamp | None:
    import re
    m = re.search(r"CONFORMED PERIOD OF REPORT:\s*(\d{8})", raw)
    return pd.Timestamp(m.group(1)) if m else None


def run(args) -> int:
    from scripts.events.cef_corp_action_census import _client, fetch_raw
    cand, nm, dsf, survivors = candidates()
    client = None if args.plan else _client(offline=args.offline)
    ix = load_index(client, args.index_cache, dt.date.today())
    mp = map_filers(ix, nm, set(cand.index))
    CACHE.mkdir(parents=True, exist_ok=True)
    mp.to_csv(CACHE / "ncsr_map.csv", index=False)
    unm = cand[~cand.index.isin(set(mp.permno))][["name", "first", "dlstdt", "cls"]]
    unm.to_csv(CACHE / "ncsr_unmapped.csv")
    todo = []
    for _, m in mp.iterrows():
        life = cand.loc[m.permno]
        lo = max(life["first"], FIT_START) - pd.Timedelta(days=PRE_DAYS)
        hi = life["dlstdt"] + pd.Timedelta(days=POST_DAYS)
        f = ix[(ix.cik == m.cik) & (ix.date_filed >= lo) & (ix.date_filed <= hi)]
        todo += [(int(m.permno), int(m.cik), a) for a in f.accession]
    print(f"candidates {len(cand)}; filers mapped {len(mp)} -> {mp.permno.nunique()} permnos; unmapped {len(unm)}; "
          f"filings to read {len(todo)}")
    if args.plan:
        return 0
    rows = []
    for k, (perm, cik, acc) in enumerate(todo, 1):
        raw = fetch_raw(client, cik, acc)
        p = period_of(raw)
        life = cand.loc[perm]
        if p is None or p < PERIOD_START or p > min(life["dlstdt"], FIT_END):
            rows.append(dict(permno=perm, cik=cik, accession=acc, period=p, close=None, nav=None, layout=None,
                             reason="no period" if p is None else "period outside the fund's fit-window life"))
            continue
        px, _ = close_at(dsf, perm, p)
        hit = read_nav(raw, px) if px else None
        rows.append(dict(permno=perm, cik=cik, accession=acc, period=p, close=px,
                         nav=hit["nav"] if hit else None, layout=hit["layout"] if hit else None,
                         reason=None if hit else ("no CRSP trade close at the period-end" if px is None
                                                  else "CRSP close not found beside a NAV")))
        if k % 100 == 0:
            print(f"  {k}/{len(todo)} read; NAVs so far {sum(r['nav'] is not None for r in rows)}")
    out = pd.DataFrame(rows)
    if len(out) and pd.to_datetime(out.period).max() > FIT_END:
        raise AssertionError("a kept period is after the fit end")
    out.to_parquet(CACHE / "ncsr_navs.parquet", index=False)
    # calibration: survivors' report NAV vs the families panel NAV on the same date
    sv = map_filers(ix, nm, set(survivors.current_permno.astype(int)))
    rng = np.random.default_rng(SEED)
    pick = sv.iloc[rng.permutation(len(sv))[:N_CALIB]] if len(sv) else sv
    pnav = pd.read_parquet(REPO / "data" / "cef_families" / "cef_nav.parquet")
    pnav["date"] = pd.to_datetime(pnav["date"])
    tk_of = dict(zip(survivors.current_permno.astype(int), survivors.ticker))
    cal = []
    for _, m in pick.iterrows():
        f = ix[(ix.cik == m.cik) & (ix.date_filed <= pd.Timestamp(FILED_END))].sort_values("date_filed")
        for acc in f.accession[::-1]:
            raw = fetch_raw(client, int(m.cik), acc)
            p = period_of(raw)
            if p is None or p > FIT_END:
                continue
            px, _ = close_at(dsf, int(m.permno), p)
            hit = read_nav(raw, px) if px else None
            pv = pnav[(pnav.ticker == tk_of[int(m.permno)]) & (pnav.date == p)]["nav"]
            cal.append(dict(ticker=tk_of[int(m.permno)], period=p, report_nav=hit["nav"] if hit else None,
                            panel_nav=float(pv.iloc[0]) if len(pv) else None))
            break
    pd.DataFrame(cal).to_parquet(CACHE / "ncsr_calibration.parquet", index=False)
    got = out.dropna(subset=["nav"])
    cand_fhy = float(((cand.dlstdt.clip(upper=FIT_END) - cand["first"].clip(lower=FIT_START)).dt.days / 182.6).clip(lower=0).sum())
    man = {"pulled_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "candidates": int(len(cand)), "mapped_permnos": int(mp.permno.nunique()), "unmapped": int(len(unm)),
           "filings_read": int(len(out)), "navs": int(len(got)), "funds_with_a_nav": int(got.permno.nunique()),
           "reasons": out.reason.fillna("ok").value_counts().to_dict(),
           "candidate_fund_half_years": round(cand_fhy, 1),
           "nav_fund_half_years_in_fit": int((pd.to_datetime(got.period) >= FIT_START).sum()),
           "calibration_rows": int(len(cal)), "client_requests": int(client.n_requests),
           "client_cache_hits": int(client.n_cache_hits)}
    man["coverage_for_the_80pct_rule"] = round(man["nav_fund_half_years_in_fit"] / max(cand_fhy, 1e-9), 3)
    (CACHE / "ncsr_manifest.json").write_text(json.dumps(man, indent=1, default=str))
    print(json.dumps(man, indent=1, default=str))
    return 0


def self_test() -> int:
    """The period, price-pinned NAV and holdout rules on synthetic report text (no network)."""
    raw = ("CONFORMED PERIOD OF REPORT: 20151231\n"
           "Net asset value, end of period $ 12.34 $ 11.10\nMarket value, end of period $ 11.05 $ 9.90\n")
    assert period_of(raw) == pd.Timestamp("2015-12-31")
    hit = read_nav(raw, 11.05)
    assert hit is not None and abs(hit["nav"] - 12.34) < 1e-9, hit
    assert read_nav(raw, 10.00) is None, "a close that is not printed must not yield a NAV"
    d = pd.DataFrame({"permno": [1, 1, 1], "date": pd.to_datetime(["2015-12-28", "2015-12-30", "2015-12-31"]),
                      "prc": [11.0, -11.02, 11.05]})
    assert close_at(d, 1, "2015-12-31")[0] == 11.05
    assert close_at(d, 1, "2015-12-30")[0] == 11.0, "a bid/ask midpoint (negative prc) is not a close"
    assert close_at(d, 1, "2016-01-20")[0] is None, "a stale close beyond MAX_GAP is refused"
    print("self-test passed: period, price-pinned NAV, trade-close rule, staleness")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--plan", action="store_true", help="counts only; no filing is fetched")
    ap.add_argument("--offline", action="store_true", help="EDGAR cache only; raise on a miss")
    ap.add_argument("--index-cache", type=Path, default=None,
                    help="the census's index_extra_*.parquet (2008-Q1 on); 2004-07 indexes are fetched")
    a = ap.parse_args(argv)
    return self_test() if a.self_test else run(a)


if __name__ == "__main__":
    raise SystemExit(main())
