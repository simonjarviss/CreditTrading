"""Checks on the thin-ETF catch-up test. NONE pre-specified: written 2026-11-16 after
explore.py's one run (MAIN 0.18, t 0.92), to show WHERE the catch-up goes, not to rescue it.

    python3 results/ideas/thin_etf_catchup/checks.py

WHY: explore.py says nothing is left after the fill delay. A null is only worth recording if
the effect it was looking for is visibly there on the day the desk cannot have. So:

  profile   event time. Funds sorted each day on S1 (yesterday's gap to the factor hedge)
            within a bucket; the mean gap of the bottom fifth less the top fifth on t+1 (the
            catch-up day: needs a fill AT t's close, which the desk's rule does not allow and
            which, in a fund whose close is stale, nobody gets at that price), on t+2 (the
            first day the desk earns), and summed over t+3..t+6. On trade prices and on
            closing mids. If t+1 is large on trades and small on mids, the catch-up is the
            stale or bouncing last trade, not a quote one could have dealt on.
  slope     the lane's literal question: after a strong market day, does a thin fund keep
            rising? Pooled slope of the fund's gap on t+1 and on t+2 on its factor-implied
            return on day t (beta'f), day-clustered standard errors. A slope of 0.10 on t+1
            means a tenth of the market's move reaches the thin fund's close a day late.
            Gaps are clipped at +/-20% so one bad print cannot set a slope.
  per unit  for the cells of explore.py's grid with t above 2, the gross return per unit of
            ETF turnover against half the median quoted spread.
Aggregates only; appends "checks" to results.json.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("thin_explore", HERE / "explore.py")
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)
assert pd.get_option("compute.use_numexpr") is False


def lead(A: np.ndarray, k: int) -> np.ndarray:
    """Row t holds A[t+k]; the last k rows are NaN."""
    out = np.full(A.shape, np.nan)
    out[:-k] = A[k:]
    return out


def daily_stat(x: np.ndarray):
    """Mean over days of a per-day series, in bp, with a plain t (days as observations)."""
    x = x[np.isfinite(x)]
    return {"mean_bp": float(x.mean() * 1e4), "t": float(x.mean() / x.std() * np.sqrt(len(x))), "days": int(len(x))}


def main() -> int:
    L = ex.Lab()
    out = {}
    print("== profile: bottom fifth less top fifth of S1, mean gap in bp a day (t)")
    prof = {}
    for label, G in (("trade prices", L.G), ("closing mids", L.Gmid)):
        for bucket in ("THIN-A", "THIN-B", "MID", "LARGE", "LIQUID"):
            el = L.eligible(G, bucket)
            W = ex.targets(G, el, ex.MIN_NAMES)
            Gc = np.clip(G, -0.2, 0.2)
            horizons = {"t+1 (not ours)": lead(Gc, 1), "t+2 (first day earned)": lead(Gc, 2),
                        "t+3..t+6": lead(Gc, 3) + lead(Gc, 4) + lead(Gc, 5) + lead(Gc, 6)}
            row = {}
            for hname, X in horizons.items():
                ok = np.isfinite(X)
                lo = np.where((W > 0) & ok, X, 0.0).sum(axis=1) / np.maximum(((W > 0) & ok).sum(axis=1), 1)
                hi = np.where((W < 0) & ok, X, 0.0).sum(axis=1) / np.maximum(((W < 0) & ok).sum(axis=1), 1)
                act = ((W > 0) & ok).any(axis=1) & ((W < 0) & ok).any(axis=1)
                row[hname] = daily_stat((lo - hi)[act])
            row["median_spread_bp"] = float(np.nanmedian(L.spread[W != 0]) * 1e4)
            prof[f"{label} | {bucket}"] = row
            print(f"{label:<13} {bucket:<7} " + "  ".join(f"{h}: {v['mean_bp']:+.1f} ({v['t']:+.1f})" for h, v in row.items() if isinstance(v, dict))
                  + f"  spread {row['median_spread_bp']:.0f}bp")
    out["profile"] = prof

    print("\n== slope of the gap on t+1 and t+2 on the factor-implied return of day t")
    pred = L.R - L.G                                     # beta'f where the fund has betas
    slopes = {}
    S5 = ex.roll_sum(L.G, 5)
    groups = {b: L.eligible(S5, b) for b in ("THIN-A", "THIN-B", "MID", "LARGE", "LIQUID")}
    for c in ex.CLASSES[:5]:
        groups[f"THIN {c}"] = L.eligible(S5, "THIN", classes=[c])
    groups["THIN traded on t"] = L.eligible(S5, "THIN", traded=True)
    groups["THIN no trade on t"] = L.eligible(S5, "THIN", traded=False)
    for label, G in (("trade prices", L.G), ("closing mids", L.Gmid)):
        Gc = np.clip(G, -0.2, 0.2)
        for gname, el in groups.items():
            row = {}
            for k in (1, 2):
                Y = lead(Gc, k)
                m = el & np.isfinite(Y) & np.isfinite(pred)
                x = np.where(m, pred, 0.0); y = np.where(m, Y, 0.0)
                sxx = (x * x).sum()
                b = (x * y).sum() / sxx
                u = (x * (y - b * x)).sum(axis=1)       # one score per day: clustered by day
                row[f"t+{k}"] = {"slope": float(b), "t": float(b / (np.sqrt((u * u).sum()) / sxx)), "fund_days": int(m.sum())}
            slopes[f"{label} | {gname}"] = row
            print(f"{label:<13} {gname:<22} t+1 {row['t+1']['slope']:+.3f} ({row['t+1']['t']:+.1f})   t+2 {row['t+2']['slope']:+.3f} ({row['t+2']['t']:+.1f})   n {row['t+1']['fund_days']:,}")
    out["slope_on_factor_implied_return"] = slopes

    res = json.loads((HERE / "results.json").read_text())
    per = {}
    print("\n== gross return per unit of ETF turnover against half the median spread")
    for name, b in res["books"].items():
        if "full" in b and b["full"]["t"] is not None and b["full"]["t"] > 2:
            per[name] = {"bp_per_unit_turnover": b["full"]["ann_ret"] / b["turnover_per_year_etf_legs"] * 1e4,
                         "half_median_spread_bp": b["median_spread_selected"] * 1e4 / 2, "t": b["full"]["t"]}
            print(f"{name:<34} {per[name]['bp_per_unit_turnover']:.2f}bp earned per unit traded; half spread {per[name]['half_median_spread_bp']:.1f}bp")
    out["per_unit_turnover"] = per
    res["checks"] = out
    (HERE / "results.json").write_text(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
