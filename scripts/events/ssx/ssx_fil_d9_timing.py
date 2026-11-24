"""D9: report timing ("time will tell") -- a zero-trial census of firm-quarters filed later or earlier than their own habit.

    export QUANTT_ENV_FILE=/abs/path/config/.env
    python3 scripts/events/ssx/ssx_fil_d9_timing.py census     # offline after ssx_fil_build (R2 for the RDQ check)

ZERO TRIALS. Filing dates, links, pre-event ADV (<= 2022) and a date-agreement
check. No return of any kind.

WHY THIS EVENT
--------------
Johnson & So (JFQA 2018, 53(6):2431-64 [V abstract]): firms that SCHEDULE their
earnings announcement later than expected report worse news, and equity prices
do not reflect it until the announcement. Their signal is the scheduling
disclosure (vendor calendar data, weeks ahead). The free analogue here is
weaker and later: the expected date passes with no report. That is knowable at
t from the ABSENCE of a filing, so the point-in-time rule is

    late event fires at 22:00 ET on the 5th EDGAR business day after the
    expected date, if no report with filing date <= that day exists;

a report accepted after 17:30 ET carries the next business day's filing date
(17 CFR 232.13), so "filing date <= t" is exactly what was public by t's
evening decision (event engine §4).

THE EXPECTED DATE
-----------------
Per CIK and form (10-Q with 10-Q, 10-K with 10-K), the same fiscal period a
year earlier: a report whose period end (`reportDate`) is 355-375 days before
this one's. Expected filing date = last year's filing date + the period-end
shift (so a firm that filed 40 days after quarter end is expected 40 days after
this quarter end). Delta = weekdays between expected and actual (positive =
later). Weekdays, not EDGAR business days: a holiday moves a delta by one, which
the 5-day threshold absorbs (stated, not corrected).

THE TWO CLOCKS
--------------
The 10-Q/10-K is the machine-readable report, but most listed firms release
earnings first in an 8-K under item 2.02. The census therefore measures both:
the 10-Q/10-K date, and the first 2.02 8-K filed after period end and no later
than the report. Compustat's RDQ (earnings report date, R2) is the independent
check of the 2.02 clock on linked firms through 2022.

KNOWN CONFOUND, STATED
----------------------
A filer-status change moves the statutory deadline (10-Q: 40 or 45 days; 10-K:
60, 75 or 90 days), so part of any delta is mechanical. The census reports the
share of "late" 10-Qs still filed within 45 days of period end (late against
habit, not against any deadline).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx import ssx_fil_common as C  # noqa: E402

LATE_BD = 5
OUT = C.OUT


def wdays(a: pd.Series, b: pd.Series) -> np.ndarray:
    """Signed weekdays from a to b (positive when b is after a)."""
    a64 = a.values.astype("datetime64[D]")
    b64 = b.values.astype("datetime64[D]")
    fwd = np.busday_count(a64, b64)
    return fwd


def periodic() -> pd.DataFrame:
    s = pd.read_parquet(C.CACHE / "subs_rows.parquet", columns=["cik", "accessionNumber", "filingDate", "reportDate",
                                                                  "form", "items"])
    p = s[s["form"].isin(["10-Q", "10-K"])].copy()
    n0 = len(p)
    p = p[p["reportDate"].fillna("") != ""]
    p["rd"] = pd.to_datetime(p["reportDate"], errors="coerce")
    p["fd"] = pd.to_datetime(p["filingDate"])
    p = p.dropna(subset=["rd"])
    p = p[(p["fd"] > p["rd"]) & ((p["fd"] - p["rd"]).dt.days <= 400)]
    p = p.sort_values("fd").drop_duplicates(["cik", "form", "rd"], keep="first")
    p.attrs["dropped_no_or_bad_period"] = int(n0 - len(p))
    return p


def match_prior(p: pd.DataFrame) -> pd.DataFrame:
    p = p.sort_values("rd").copy()
    p["rd_target"] = p["rd"] - pd.Timedelta(days=365)
    prev = p[["cik", "form", "rd", "fd"]].rename(columns={"rd": "rd_prev", "fd": "fd_prev"}).sort_values("rd_prev")
    m = pd.merge_asof(p.sort_values("rd_target"), prev, left_on="rd_target", right_on="rd_prev",
                      by=["cik", "form"], direction="nearest", tolerance=pd.Timedelta(days=10))
    m = m.dropna(subset=["rd_prev"]).copy()
    m["expected"] = m["fd_prev"] + (m["rd"] - m["rd_prev"])
    m["delta_wd"] = wdays(m["expected"], m["fd"])
    m["late5"] = m["delta_wd"] >= LATE_BD
    m["early5"] = m["delta_wd"] <= -LATE_BD
    m["lag_days"] = (m["fd"] - m["rd"]).dt.days
    return m


def attach_202(m: pd.DataFrame) -> pd.DataFrame:
    """First 2.02 8-K after period end and on or before the report's filing date."""
    s = pd.read_parquet(C.CACHE / "subs_rows.parquet", columns=["cik", "filingDate", "form", "items"])
    e = s[(s["form"] == "8-K") & s["items"].fillna("").str.contains(r"(?:^|,)2\.02(?:,|$)")].copy()
    e["d202"] = pd.to_datetime(e["filingDate"])
    e = e[["cik", "d202"]].sort_values("d202")
    x = m[["cik", "form", "rd", "fd"]].copy().sort_values("rd")
    x = pd.merge_asof(x, e.rename(columns={"d202": "d202_first"}), left_on="rd", right_on="d202_first",
                      by="cik", direction="forward", allow_exact_matches=False)
    x.loc[~(x["d202_first"] <= x["fd"]), "d202_first"] = pd.NaT
    m = m.merge(x[["cik", "form", "rd", "d202_first"]], on=["cik", "form", "rd"], how="left")
    prev = m[["cik", "form", "rd", "d202_first"]].rename(columns={"rd": "rd_prev", "d202_first": "d202_prev"})
    m = m.merge(prev, on=["cik", "form", "rd_prev"], how="left")
    ok = m["d202_first"].notna() & m["d202_prev"].notna()
    m["delta202_wd"] = np.nan
    exp202 = m.loc[ok, "d202_prev"] + (m.loc[ok, "rd"] - m.loc[ok, "rd_prev"])
    m.loc[ok, "delta202_wd"] = wdays(exp202, m.loc[ok, "d202_first"])
    return m


def rdq_check(m: pd.DataFrame, links: pd.DataFrame) -> dict:
    """Compustat RDQ against the 2.02 date on linked 10-Qs, 2010-2022. Licensed; cached."""
    p = C.CACHE / "comp_fundq_rdq.parquet"
    if not p.exists():
        r2, con = C._r2()
        df = r2.q(con, f"""SELECT gvkey, datadate, rdq FROM read_parquet('{r2.r2_path('comp_na_daily_all', 'fundq')}')
                           WHERE datadate BETWEEN DATE '2009-01-01' AND DATE '2022-12-31' AND rdq IS NOT NULL
                             AND indfmt = 'INDL' AND datafmt = 'STD' AND consol = 'C' AND popsrc = 'D'""")
        df.to_parquet(p)
    f = pd.read_parquet(p)
    f["datadate"], f["rdq"] = pd.to_datetime(f["datadate"]), pd.to_datetime(f["rdq"])
    g = links[["cik", "gvkey"]].drop_duplicates()
    x = m[(m["form"] == "10-Q") & m["d202_first"].notna() & (m["fd"].dt.year.between(2010, 2022))]
    x = x.merge(g, on="cik").merge(f, left_on=["gvkey", "rd"], right_on=["gvkey", "datadate"], how="inner")
    d = (x["d202_first"] - x["rdq"]).dt.days
    return {"n_matched": int(len(x)), "same_day": round(float((d == 0).mean()), 4),
            "within_1_day": round(float((d.abs() <= 1).mean()), 4),
            "rdq_on_or_before_10q": round(float((x["rdq"] <= x["fd"]).mean()), 4)}


def census() -> dict:
    p = periodic()
    m = match_prior(p)
    m = attach_202(m)
    m["year"] = m["fd"].dt.year
    m = m[m["year"].between(2009, C.COUNT_END)]
    links, names = C.cik_permno_links(offline=True), C.crsp_names(offline=True)
    ev = m.rename(columns={"fd": "date"})
    ev = C.link_events(ev, links, names)
    dv = C.dv_panel(offline=True)
    by = C.dv_by_permno(dv[dv["permno"].isin(ev["permno"].dropna().astype(int).unique())])
    ev["adv"] = C.pre_event_adv_fast(ev, by)
    ev["liquid"] = ev["listed_common"] & (ev["adv"] >= 1e6)
    subs = pd.read_parquet(C.CACHE / "subs_rows.parquet", columns=["cik", "form", "filingDate"])
    ev["bdc"] = C.is_bdc_on(ev, C.bdc_spells(subs))
    ev.to_parquet(C.CACHE / "d9_firm_quarters.parquet")

    g = ev.groupby("year")
    yr = pd.DataFrame({
        "firm_quarters_matched": g.size(),
        "share_late5": g["late5"].mean().round(4), "share_early5": g["early5"].mean().round(4),
        "late5": g["late5"].sum(), "early5": g["early5"].sum(),
        "filers": g["cik"].nunique(),
        "listed_common": g["listed_common"].sum(),
        "liquid": g["liquid"].sum(),
        "late5_liquid": g.apply(lambda x: int((x["late5"] & x["liquid"]).sum()), include_groups=False),
        "late5_liquid_issuers": g.apply(lambda x: x.loc[x["late5"] & x["liquid"], "cik"].nunique(), include_groups=False),
        "early5_liquid": g.apply(lambda x: int((x["early5"] & x["liquid"]).sum()), include_groups=False),
        "with_202_before_report": g["d202_first"].apply(lambda s: round(float(s.notna().mean()), 4)),
        "late5_on_202_clock": g.apply(lambda x: int((x["delta202_wd"] >= LATE_BD).sum()), include_groups=False),
        "late5_on_202_clock_liquid": g.apply(lambda x: int(((x["delta202_wd"] >= LATE_BD) & x["liquid"]).sum()), include_groups=False),
        "bdc_reports": g["bdc"].sum(),
        "bdc_late5": g.apply(lambda x: int((x["late5"] & x["bdc"]).sum()), include_groups=False),
    })
    for c in ("liquid", "late5_liquid", "late5_liquid_issuers", "early5_liquid", "late5_on_202_clock_liquid"):
        yr.loc[yr.index > C.ADV_LAST_EVENT.year, c] = np.nan
    fq = ev.assign(q=ev["date"].dt.to_period("Q")).groupby("q")["cik"].nunique()
    yr["filers_per_quarter_mean"] = fq.groupby(fq.index.year).mean().round(0)
    yr.to_csv(OUT / "d9_timing_by_year.csv")

    w = ev[ev["year"].between(2010, 2022)]
    lq = w[w["late5"] & w["liquid"] & (w["form"] == "10-Q")]
    gap = (w["date"] - w["d202_first"]).dt.days.dropna()
    summ = {
        "matched_firm_quarters_2009_2025": int(len(ev)),
        "dropped_no_or_bad_period": p.attrs["dropped_no_or_bad_period"],
        "late5_liquid_per_year_2010_22_mean": round(float(yr.loc[2010:2022, "late5_liquid"].mean()), 1),
        "late5_liquid_per_year_2010_22_min": int(yr.loc[2010:2022, "late5_liquid"].min()),
        "late5_liquid_issuer_years_2010_22": int(w.loc[w["late5"] & w["liquid"], ["cik", "year"]].drop_duplicates().shape[0]),
        "late5_on_202_clock_liquid_per_year_2010_22_mean": round(float(yr.loc[2010:2022, "late5_on_202_clock_liquid"].mean()), 1),
        "late5_liquid_10q_within_45_days_share": round(float((lq["lag_days"] <= 45).mean()), 4) if len(lq) else None,
        "days_202_to_report_median_2010_22": float(gap.median()) if len(gap) else None,
        "days_202_to_report_p25_p75": [float(gap.quantile(.25)), float(gap.quantile(.75))] if len(gap) else None,
        "share_202_same_day_as_report": round(float((gap == 0).mean()), 4) if len(gap) else None,
        "late5_with_nt_between": None,
    }
    nt = pd.read_parquet(C.CACHE / "index_rows.parquet")
    nt = nt[nt["form"].isin(["NT 10-K", "NT 10-Q"])][["cik", "date_filed"]]
    L = w[w["late5"] & w["liquid"]][["cik", "expected", "date"]].reset_index()
    j = L.merge(nt, on="cik")
    j = j[(j["date_filed"] >= j["expected"]) & (j["date_filed"] <= j["date"])]
    summ["late5_liquid_2010_22_with_nt_between_share"] = round(j["index"].nunique() / len(L), 4) if len(L) else None
    try:
        summ["rdq_vs_202"] = rdq_check(ev.rename(columns={"date": "fd"}), links)
    except Exception as ex:   # the check is reported as unavailable, never assumed
        summ["rdq_vs_202"] = f"UNAVAILABLE: {ex!r}"[:300]
    C.write_json(OUT / "d9_timing_summary.json", summ)
    print(yr.to_string())
    print(summ)
    return summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("census",))
    ap.parse_args(argv)
    C.OUT.mkdir(parents=True, exist_ok=True)
    census()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
