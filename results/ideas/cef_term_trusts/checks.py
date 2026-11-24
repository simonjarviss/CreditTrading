"""Checks on the term-trust result. NONE of these was pre-specified: all were chosen on
2026-11-18 after the first read of `explore.py`'s output, to answer what that read raised.

    python3 results/ideas/cef_term_trusts/checks.py        # after explore.py; reads its per-event files

WHY EACH ONE
  1. reconcile   the per-event excess over the matched ETF (+1.8%) looked large beside the
                 calendar book (0.1% a year). Events entered the same December share one
                 book-year, so the mean of the decision-month means is the comparable figure.
  2. by cohort   which decision years carry the result, and what is left without the best one.
  3. cash        a fund winding down is close to cash, so the fair long-only benchmark is a
                 short Treasury fund (SHY, from 2002-07), not zero.
  4. entry cost  the trade pays the spread once (liquidation costs nothing on the way out):
                 per-event excess after half the closing spread on the fill day.
  5. where       the share of the T250 return that arrives on the last five sessions, and the
                 last-day return itself: a jump on the final CRSP row is the liquidating
                 payment against a stale last price, and is not capturable at that close.
  6. PCEF        the tradable proxy for the CEF market, from 2010.
  7. no-year     term funds with no year in the name appear only in the hindsight table; how
                 the year-named funds compare with them there.
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
sys.path.insert(0, str(HERE.parents[2]))
import explore as ex  # noqa: E402  (the idea's own module: same loaders, same list)

assert pd.get_option("compute.use_numexpr") is False


def main() -> int:
    df, P, names, dl = ex.load()
    cal = P["ret"].index
    R = P["ret"].fillna(0.0)
    etf = ex.etf_returns(cal)
    mid = (P["bid"] + P["ask"]) / 2
    spread = ((P["ask"] - P["bid"]) / mid).where((P["bid"] > 0) & (P["ask"] > P["bid"]))
    out = {}
    pe = pd.read_parquet(ex.STAGE / "per_event_T250_adv100k.parquet")
    pe["year"] = pd.to_datetime(pe["D"]).dt.year
    # 1 and 2
    g = pe.groupby("year")[["fund", "vs_mkt", "vs_etf", "vs_control"]].mean()
    cnt = pe.groupby("year").size()
    out["by_decision_year"] = {int(y): {"n": int(cnt[y]), **{c: (None if pd.isna(v) else float(v)) for c, v in g.loc[y].items()}} for y in g.index}
    cm = {}
    for c in ("fund", "vs_mkt", "vs_etf", "vs_control"):
        v = g[c].dropna()
        cm[c] = {"cohorts": int(len(v)), "mean_of_cohort_means": float(v.mean()), "t": float(v.mean() / v.std() * np.sqrt(len(v))),
                 "share_positive": float((v > 0).mean()), "without_best_cohort": float(v.drop(v.idxmax()).mean()), "best_cohort": int(v.idxmax())}
    out["cohort_means"] = cm
    # 3 and 4 and 5
    rows = []
    for k, e in pe.iterrows():
        D, end, p = pd.Timestamp(e["D"]), pd.Timestamp(e["end"]), e["permno"]
        i = cal.get_loc(D)
        a = cal[i + 2]
        seg = R[p].loc[a:end]
        shy = etf["SHY"].loc[a:end]
        fill = cal[i + 1]
        s = spread.at[fill, p]
        last5 = (1 + seg.iloc[-5:]).prod() - 1
        rows.append({"vs_shy": e["fund"] - ((1 + shy).prod() - 1) if np.isfinite(shy).all() else np.nan,
                     "half_spread_fill_day": s / 2 if np.isfinite(s) else np.nan,
                     "last5": last5, "last_day": seg.iloc[-1], "ex_last5": (1 + e["fund"]) / (1 + last5) - 1,
                     "max_drawdown_in_hold": float(((1 + seg).cumprod() / (1 + seg).cumprod().cummax() - 1).min())})
    x = pd.DataFrame(rows, index=pe.index)
    pe = pe.join(x)
    out["vs_shy"] = ex.clustered(pe["vs_shy"], pe["month"])
    out["half_spread_fill_day_bp"] = {"n": int(pe["half_spread_fill_day"].notna().sum()), "median": float(pe["half_spread_fill_day"].median() * 1e4),
                                      "mean": float(pe["half_spread_fill_day"].mean() * 1e4), "p90": float(pe["half_spread_fill_day"].quantile(0.9) * 1e4)}
    net = pe.dropna(subset=["half_spread_fill_day"])
    out["after_half_spread"] = {c: ex.clustered(net[c] - net["half_spread_fill_day"], net["month"]) for c in ("fund", "vs_etf", "vs_control", "vs_shy")}
    out["where_the_return_arrives"] = {"last5_mean": float(pe["last5"].mean()), "last5_median": float(pe["last5"].median()),
                                       "last_day_mean": float(pe["last_day"].mean()), "last_day_median": float(pe["last_day"].median()),
                                       "last_day_abs_over_1pct": int((pe["last_day"].abs() > 0.01).sum()),
                                       "fund_ex_last5": ex.clustered(pe["ex_last5"], pe["month"]),
                                       "worst_drawdown_in_hold": {"median": float(pe["max_drawdown_in_hold"].median()), "min": float(pe["max_drawdown_in_hold"].min())}}
    # by ETF class and era
    out["by_matched_etf"] = {t: {c: ex.clustered(pe.loc[pe["etf"] == t, c], pe["month"]) for c in ("fund", "vs_etf", "vs_control")} for t in pe["etf"].unique()}
    era = pd.cut(pe["year"] + 1, [1989, 2001, 2008, 2015, 2019, 2022, 2026], labels=["1995-2001", "2002-08", "2009-15", "2016-19", "2020-22", "2023-25"])
    out["by_era_of_scheduled_year"] = {str(k): {"n": int(len(v)), "fund": float(v["fund"].mean()), "vs_etf": None if v["vs_etf"].isna().all() else float(v["vs_etf"].mean()),
                                                "vs_control": None if v["vs_control"].isna().all() else float(v["vs_control"].mean())}
                                       for k, v in pe.groupby(era, observed=True)}
    # 6 PCEF
    rows = []
    for k, e in pe.iterrows():
        a = cal[cal.get_loc(pd.Timestamp(e["D"])) + 2]
        s = etf["PCEF"].loc[a:pd.Timestamp(e["end"])]
        rows.append(e["fund"] - ((1 + s).prod() - 1) if np.isfinite(s).all() else np.nan)
    pe["vs_pcef"] = rows
    out["vs_pcef"] = ex.clustered(pe["vs_pcef"], pe["month"])
    # 7 hindsight, year-named against the rest
    L = pd.read_parquet(ex.STAGE / "term_list.parquet")
    hs = {}
    for K in (250, 60):
        T = pd.read_parquet(ex.STAGE / f"hindsight_{K}.parquet")
        T = T[T["outcome"] == "liquidated"]
        has_year = L["year_at_end"].reindex(T.index).notna()
        hs[str(K)] = {"year_in_name": {c: ex.clustered(T.loc[has_year, c], T["month"]) for c in ("fund", "vs_etf", "vs_control")},
                      "no_year": {c: ex.clustered(T.loc[~has_year, c], T["month"]) for c in ("fund", "vs_etf", "vs_control")}}
    out["hindsight_by_name_year"] = hs
    (HERE / "checks.json").write_text(json.dumps(out, indent=1, default=str))
    r = lambda d: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()} if isinstance(d, dict) else d
    for k, v in out.items():
        print("\n" + k)
        if isinstance(v, dict) and all(isinstance(w, dict) for w in v.values()):
            for kk, w in v.items():
                print("  ", kk, {a: r(b) for a, b in w.items()} if any(isinstance(b, dict) for b in w.values()) else r(w))
        else:
            print("  ", r(v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
