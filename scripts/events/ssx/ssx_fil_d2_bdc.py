"""D2: BDC earnings and NAV -- the data-build census for the parked B5 idea.

    export QUANTT_ENV_FILE=/abs/path/config/.env
    python3 scripts/events/ssx/ssx_fil_d2_bdc.py census --bulk-cache <cache root holding companyfacts.zip>
    python3 scripts/events/ssx/ssx_fil_d2_bdc.py releases           # live, budgeted: does the 2.02 release print NAV?
    python3 scripts/events/ssx/ssx_fil_d2_bdc.py releases --offline

ZERO TRIALS. Filing counts, XBRL coverage, filing lags and release text. No
price, no return, no NAV-vs-price comparison.

WHY THIS CENSUS
---------------
B5 was parked because BDC NAV is quarterly and stale (results/cef/
RESEARCH_AGENDA_2026-10-08.md). The event version asks whether the NAV printed
AT earnings is news the price absorbs slowly. Before any test, three data
questions decide feasibility:
  1. how many BDC reports and earnings releases a year (who files, listed or not);
  2. is NAV per share machine-readable from XBRL for each BDC-quarter
     (us-gaap:NetAssetValuePerShare in the companyfacts archive, matched to the
     report's own accession AND period end -- a comparative-period value in a
     later filing does not count);
  3. when NAV becomes public: the 10-Q/10-K filing lag, and the 8-K item 2.02
     release lag, because a release that prints NAV days before the 10-Q moves
     the clock to the release (and the release's NAV is text, not XBRL).
Kill gate (brief): XBRL NAV coverage < 80% of BDC-quarters.

BDC status is the N-54A election, not withdrawn (ssx_fil_common.bdc_spells).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx import ssx_fil_common as C  # noqa: E402

NAV_TAG = "NetAssetValuePerShare"
SALT = "ssx_fil_d2_v1"
N_RELEASES = 20
OUT = C.OUT


def bdc_reports() -> tuple[pd.DataFrame, pd.DataFrame]:
    s = pd.read_parquet(C.CACHE / "subs_rows.parquet")
    spells = C.bdc_spells(s)
    s = s[s["cik"].isin(spells["cik"])].copy()
    s["date"] = pd.to_datetime(s["filingDate"])
    s["year"] = s["date"].dt.year
    rep = s[s["form"].isin(["10-Q", "10-K"]) & s["year"].between(C.COUNT_START, C.COUNT_END)].copy()
    rep = rep[C.is_bdc_on(rep, spells)]
    e = s[(s["form"] == "8-K") & s["items"].fillna("").str.contains(r"(?:^|,)2\.02(?:,|$)") & s["year"].between(C.COUNT_START, C.COUNT_END)].copy()
    e = e[C.is_bdc_on(e, spells)]
    return rep, e


def census(bulk_cache: Path | None) -> dict:
    rep, e = bdc_reports()
    z = C.bulk_zip(C.COMPANYFACTS_ZIP_URL, bulk_cache)
    names = set(z.namelist())
    facts = []
    for cik in sorted(rep["cik"].unique()):
        fn = f"CIK{int(cik):010d}.json"
        if fn not in names:
            continue
        j = json.loads(z.read(fn))
        node = j.get("facts", {}).get("us-gaap", {}).get(NAV_TAG)
        if not node:
            continue
        for unit, vals in node.get("units", {}).items():
            for v in vals:
                facts.append({"cik": int(cik), "unit": unit, "accn": v.get("accn"), "end": v.get("end"),
                              "filed": v.get("filed"), "form": v.get("form"), "val": v.get("val")})
    f = pd.DataFrame(facts)
    f.to_parquet(C.CACHE / "d2_bdc_navps_facts.parquet")
    own = f[["accn", "end"]].drop_duplicates()
    own["has_own"] = True
    rep = rep.merge(own, left_on=["accessionNumber", "reportDate"], right_on=["accn", "end"], how="left")
    rep["nav_xbrl_own_period"] = rep["has_own"].fillna(False).astype(bool)
    rep = rep.drop(columns=["accn", "end", "has_own"])
    rep["nav_xbrl_any"] = rep["accessionNumber"].isin(set(f["accn"]))
    links, cnames = C.cik_permno_links(offline=True), C.crsp_names(offline=True)
    rep = C.link_events(rep, links, cnames)
    rep["listed"] = rep["linked"] & rep["exchcd"].isin(C.LISTED_EXCHCD)
    rep.to_parquet(C.CACHE / "d2_bdc_reports.parquet")

    g = rep.groupby("year")
    yr = pd.DataFrame({"bdc_reports": g.size(), "bdc_filers": g["cik"].nunique(),
                       "xbrl_navps_own_period": g["nav_xbrl_own_period"].mean().round(4),
                       "xbrl_navps_any": g["nav_xbrl_any"].mean().round(4),
                       "listed_reports": g["listed"].sum(),
                       "listed_xbrl_navps_own_period": g.apply(lambda x: round(float(x.loc[x["listed"], "nav_xbrl_own_period"].mean()), 4) if x["listed"].any() else np.nan, include_groups=False),
                       "isxbrl_flag_share": g["isXBRL"].mean().round(4)})
    yr["bdc_202_releases"] = e.groupby("year").size()
    yr["bdc_202_filers"] = e.groupby("year")["cik"].nunique()
    yr.to_csv(OUT / "d2_bdc_by_year.csv")

    rep["rd"] = pd.to_datetime(rep["reportDate"], errors="coerce")
    lag = (rep["date"] - rep["rd"]).dt.days
    e2 = e[["cik", "date"]].rename(columns={"date": "d202"}).sort_values("d202")
    x = rep[["cik", "rd", "date", "form", "listed", "year"]].dropna(subset=["rd"]).sort_values("rd")
    x = pd.merge_asof(x, e2, left_on="rd", right_on="d202", by="cik", direction="forward", allow_exact_matches=False)
    x.loc[~(x["d202"] <= x["date"] + pd.Timedelta(days=3)), "d202"] = pd.NaT
    lag202 = (x["d202"] - x["rd"]).dt.days.dropna()
    gap = (x["date"] - x["d202"]).dt.days.dropna()
    def q(s):
        return {"n": int(len(s)), "p10": float(s.quantile(.1)), "median": float(s.median()), "p90": float(s.quantile(.9))} if len(s) else None
    meta = pd.read_parquet(C.CACHE / "subs_meta.parquet")
    assets, clock = C.alpaca_assets()
    live = rep.loc[rep["year"] == 2025, "cik"].unique()
    b = C.borrow_today(live, meta, assets)
    w = rep[rep["year"].between(2012, 2022)]
    wl = w[w["listed"]]
    summ = {
        "bdc_spells_n54a": int(C.bdc_spells(pd.read_parquet(C.CACHE / "subs_rows.parquet", columns=["cik", "form", "filingDate"])).shape[0]),
        "coverage_own_period_2012_22_all": round(float(w["nav_xbrl_own_period"].mean()), 4),
        "coverage_own_period_2012_22_listed": round(float(wl["nav_xbrl_own_period"].mean()), 4) if len(wl) else None,
        "coverage_own_period_2023_25_all": round(float(rep.loc[rep["year"].between(2023, 2025), "nav_xbrl_own_period"].mean()), 4),
        "lag_report_days_10q": q(lag[rep["form"] == "10-Q"].dropna()),
        "lag_report_days_10k": q(lag[rep["form"] == "10-K"].dropna()),
        "lag_202_days_listed": q((x.loc[x["listed"], "d202"] - x.loc[x["listed"], "rd"]).dt.days.dropna()),
        "share_listed_reports_with_202_before": round(float(x.loc[x["listed"], "d202"].notna().mean()), 4),
        "days_202_to_report_listed": q((x.loc[x["listed"], "date"] - x.loc[x["listed"], "d202"]).dt.days.dropna()),
        "borrow_today_2025_bdc_filers": {"alpaca_clock": clock, "filers": int(len(live)), "listed_today": int(len(b)),
                                         "at_alpaca": int(b["at_alpaca"].sum()), "shortable": int(b["shortable"].sum()),
                                         "etb": int(b["etb"].sum())},
    }
    C.write_json(OUT / "d2_bdc_summary.json", summ)
    print(yr.to_string())
    print(summ)
    return summ


def releases(offline: bool) -> dict:
    """Does a listed BDC's 2.02 release print NAV per share? A declared sample, read in full."""
    rep, e = bdc_reports()
    links, cnames = C.cik_permno_links(offline=True), C.crsp_names(offline=True)
    e = C.link_events(e, links, cnames)
    e = e[e["linked"] & e["exchcd"].isin(C.LISTED_EXCHCD) & e["year"].between(2015, 2022)]
    picks = C.declared_order(e["accessionNumber"].tolist(), SALT)[:N_RELEASES]
    E = C.BudgetedEdgar(offline=offline)
    from scripts.data.edgar_client import filing_txt_url
    rows = []
    for acc in picks:
        r = e.set_index("accessionNumber").loc[acc]
        txt = E.get_text(filing_txt_url(int(r["cik"]), acc), purpose="d2 BDC 2.02 release")
        low = re.sub(r"<[^>]+>", " ", txt).lower()
        rows.append({"accession": acc, "cik": int(r["cik"]), "filing_date": r["date"].date().isoformat(),
                     "accepted_et": C.header_acceptance_et(txt).isoformat(sep=" "),
                     "prints_navps": bool(re.search(r"net asset value(\s+\(\"nav\"\))?\s+per\s+(common\s+)?share|nav\s+per\s+share", low))})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "d2_bdc_release_sample.csv", index=False)
    k, n = int(df["prints_navps"].sum()), len(df)
    t = pd.to_datetime(df["accepted_et"])
    # After the close = accepted at or after 16:00 ET, or carrying the next business
    # day's filing date (accepted after 17:30). An OR, so no filing counts twice.
    after = int((((t.dt.hour * 100 + t.dt.minute) >= 1600) | (t.dt.date.astype(str) != df["filing_date"])).sum())
    summ = {"n": n, "prints_navps": k, "ci95": C.wilson(k, n), "after_close": after,
            "pre_open": int(((t.dt.hour * 100 + t.dt.minute) < 930).sum()),
            "live_requests_ledger_total": C.BudgetedEdgar.spent()}
    C.write_json(OUT / "d2_bdc_release_summary.json", summ)
    print(summ)
    return summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("census", "releases"))
    ap.add_argument("--bulk-cache", type=Path, default=None)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    census(a.bulk_cache) if a.part == "census" else releases(a.offline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
