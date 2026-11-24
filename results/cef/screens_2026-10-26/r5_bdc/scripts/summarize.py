"""Print the R5 result tables from bdc_ic_results.json (aggregates only)."""
import json
R = json.load(open("bdc_ic_results.json"))
for k in ("spec", "nav_exclusions", "permnos", "calendar", "filing_sensitivity_unmatched_nav_rows",
          "filing_minus_rdq_days_p10_p50_p90", "filing_before_rdq_rows"):
    print(k, R.get(k))
def line(lab, e):
    return f"  {lab:<34}" + "".join(f"{e[x]['ic']:+8.4f} ({e[x]['t']:+5.2f}, nw {e[x]['t_nw']:+5.2f}, n{e[x]['n']:5d}) " for x in ("2012-17", "2018-22", "fit 2012-22"))
for run in ("rdq_primary", "filingdate_sensitivity"):
    print(f"\n=== {run}  panel:", R[run]["panel"])
    for ph in ("phase0", "phase1"):
        B = R[run][ph]
        print(f" {ph}: IC on s=-z (IC>0 = works)   2012-17 | 2018-22 | fit 2012-22    rank corr(T,C) median {B['rank_corr_treatment_control_median']:.3f}")
        for setlab in ("primary", "deployed_style_adv"):
            S = B[setlab]
            print(f" [{setlab}] names/date median {S['names_per_date_median_2012_22']}")
            for k in ("treatment", "control", "partial"):
                print(line(k, S[k]))
        P = B["post_filing"]
        print(" [post-filing split, primary]  dates with >= MIN_NAMES post names:", P["pooled_dates_post_ge_min_names"])
        for k in ("treatment_post", "treatment_rest", "control_post_context", "control_rest_context"):
            print(line(k, P[k]))
