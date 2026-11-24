"""Checks made AFTER the pre-specified run of explore.py (2026-11-18). NONE IS PRE-SPECIFIED.

    python3 results/ideas/cef_tax_loss_january/checks.py

WHY: the fixed test found no reliable loser-against-market rebound (+0.50% a season, t 0.97).
Three questions were left by its own table, and each is answered here on the same seasons:

  A. Is the fixed sort too weak a reading of "tax loss"? The worst fifth in an up year holds
     funds that are UP on the year (the cut was +27.7% in 2009), which nobody sells for a loss.
     So: funds actually down on the year, and down more than 10%, less all eligible; and the
     fixed spread in the seasons where the median eligible fund was down on the year.
  B. Does one season carry it? The fixed spread without formation 2008.
  C. The table's largest number is not the spread but the level: ALL eligible funds, equally
     weighted, rose 4.0% over the window. Is that a closed-end-fund turn-of-the-year effect or
     the stock market's? All eligible funds less IWM, SPY and PCEF over the fixed window, and
     the same 'all funds less IWM' over the same-length window started at the tenth session of
     EVERY month (a calendar placebo: twelve windows a year), by era.

ALIGNMENT is explore.season's: selection on rows dated <= F, first return counted is F+2's.
Writes checks.json (aggregates only).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import explore as ex  # noqa: E402  (turns numexpr off through scripts.research.explore)

assert pd.get_option("compute.use_numexpr") is False


def main() -> int:
    df = pd.read_parquet(ex.PANEL)
    df["date"] = pd.to_datetime(df["date"])
    ret, prc, dv = (df.pivot(index="date", columns="permno", values=c) for c in ("ret", "prc", "dollar_volume"))
    idx = ret.index
    yf = pd.read_parquet(ex.YF)
    yf["date"] = pd.to_datetime(yf["date"])
    bench = {t: yf[yf["ticker"] == t].set_index("date")["ret_total"] for t in ("IWM", "SPY")}
    pc = pd.read_parquet(ex.PCEF)
    pc["date"] = pd.to_datetime(pc["date"])
    bench["PCEF"] = pc.set_index("date")["ret_total"]

    S = {y: ex.season(ret, prc, dv, sig_first=ex.nth(idx, y, 1, 1), F=ex.nth(idx, y, 12, 10), floor=ex.FLOOR,
                      exits={"j10": ex.nth(idx, y + 1, 1, 10), "jend": ex.nth(idx, y + 1, 1, -1)}) for y in ex.YEARS}
    res = {"panel_last_date": str(idx.max().date()), "not_pre_specified": True}

    # ---- A. funds actually in loss ------------------------------------------------------------
    rows = {}
    for y, d in S.items():
        m = d["bh_j10"].mean()
        neg, neg10 = d["ytd"] < 0, d["ytd"] < -0.10
        rows[y] = {"down_lm": d.loc[neg, "bh_j10"].mean() - m if neg.sum() >= 10 else np.nan, "n_down": int(neg.sum()),
                   "down10_lm": d.loc[neg10, "bh_j10"].mean() - m if neg10.sum() >= 10 else np.nan, "n_down10": int(neg10.sum()),
                   "fixed_lm": d.loc[d["q"] == 1, "bh_j10"].mean() - m, "median_ytd": d["ytd"].median(), "mkt": m,
                   "fixed_lm_jend": d.loc[d["q"] == 1, "bh_jend"].mean() - d["bh_jend"].mean()}
    A = pd.DataFrame(rows).T
    res["A_down_on_year_less_all_j10"] = ex.ann(A["down_lm"]) | {"funds_mean": float(A.loc[A["down_lm"].notna(), "n_down"].mean())}
    res["A_down_over_10pct_less_all_j10"] = ex.ann(A["down10_lm"]) | {"funds_mean": float(A.loc[A["down10_lm"].notna(), "n_down10"].mean())}
    dn = A["median_ytd"] < 0
    res["A_fixed_spread_in_down_years"] = ex.ann(A.loc[dn, "fixed_lm"]) | {"years": [int(y) for y in A.index[dn]]}
    res["A_fixed_spread_in_up_years"] = ex.ann(A.loc[~dn, "fixed_lm"])
    # ---- B. without 2008 --------------------------------------------------------------------------
    res["B_fixed_spread_without_2008_j10"] = ex.ann(A["fixed_lm"].drop(2008))
    res["B_fixed_spread_without_2008_jend"] = ex.ann(A["fixed_lm_jend"].drop(2008))

    # ---- C. the level: all eligible funds against tradable benchmarks -----------------------------
    def bret(s, a, b):                       # compounded benchmark return over idx[a..b]; NaN if any day is missing
        w = s.reindex(idx[a:b + 1])
        return np.nan if w.isna().any() else float((1 + w).prod() - 1)

    lev = {}
    for y, d in S.items():
        iF, iX = idx.get_loc(d.attrs["F"]), idx.get_loc(d.attrs["exits"]["j10"])
        lev[y] = {"mkt": d["bh_j10"].mean(), **{f"mkt_less_{k}": d["bh_j10"].mean() - bret(s, iF + 2, iX) for k, s in bench.items()}}
    Lv = pd.DataFrame(lev).T
    res["C_all_funds_raw_j10"] = ex.ann(Lv["mkt"])
    for k in bench:
        res[f"C_all_funds_less_{k}_j10"] = ex.ann(Lv[f"mkt_less_{k}"])
    res["C_all_funds_less_IWM_without_2008"] = ex.ann(Lv["mkt_less_IWM"].drop(2008))
    res["C_per_season_all_funds_less"] = {int(y): {k: (None if pd.isna(v) else float(v)) for k, v in r.items()} for y, r in Lv.iterrows()}

    # the same-length window from the tenth session of every month: all eligible funds less IWM
    cal = {}
    for m in range(1, 13):
        rows = {}
        for y in range(2001, 2025):
            F = ex.nth(idx, y, m, 10)
            y2, m2 = (y, m + 1) if m < 12 else (y + 1, 1)
            X = ex.nth(idx, y2, m2, 10)
            iF, iX = idx.get_loc(F), idx.get_loc(X)
            a = dv.iloc[iF - 20:iF + 1]
            assert a.index.max() == F                                   # eligibility reads rows <= F only
            el = (prc.loc[F] >= ex.MIN_PRICE) & (a.mean().where(a.notna().sum() >= 10) >= ex.FLOOR)
            mk = ((1 + ret.iloc[iF + 2:iX + 1].loc[:, el[el].index].fillna(0.0)).prod() - 1).mean()
            rows[y] = mk - bret(bench["IWM"], iF + 2, iX)
        cal[m] = pd.Series(rows)
    C = pd.DataFrame(cal)
    res["C_calendar_placebo_all_funds_less_IWM_by_start_month"] = {
        int(m): {"mean": float(C[m].mean()), "t": float(C[m].mean() / C[m].std() * np.sqrt(C[m].notna().sum())),
                 "n_pos": int((C[m] > 0).sum()), "n": int(C[m].notna().sum()),
                 "mean_2001_12": float(C[m].loc[:2012].mean()), "mean_2013_24": float(C[m].loc[2013:].mean())} for m in C}

    (HERE / "checks.json").write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        if isinstance(v, dict) and "t" in v:
            print(f"{k:42s} n {v['n']:2d} mean {v['mean'] * 100:+.2f} med {v['median'] * 100:+.2f} t {v['t']:+.2f} pos {v['n_pos']:2d} "
                  f"halves {v['first_half_mean'] * 100:+.2f}/{v['second_half_mean'] * 100:+.2f} "
                  + " ".join(f"{n}:{x['mean'] * 100:+.2f}({x['n_pos']}/{x['n']})" for n, x in v["eras"].items()) + (f" funds {v['funds_mean']:.0f}" if "funds_mean" in v else "") + (f" {v['years']}" if "years" in v else ""))
    print("calendar placebo, all funds less IWM, window from the 10th session of month m (12 = the fixed window):")
    for m, v in res["C_calendar_placebo_all_funds_less_IWM_by_start_month"].items():
        print(f"  {m:2d}: mean {v['mean'] * 100:+.2f} t {v['t']:+.2f} pos {v['n_pos']}/{v['n']}  2001-12 {v['mean_2001_12'] * 100:+.2f}  2013-24 {v['mean_2013_24'] * 100:+.2f}")
    print((Lv * 100).round(2).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
