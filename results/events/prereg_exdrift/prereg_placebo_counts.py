"""r8: placebo survival COUNTS (calendar only; no return, price or amount is read for any period).
A placebo event at p+s (s = +5, -5, +10, -10) holds rows p+s+1..p+s+3. It survives only if no hold row lies within
[-3, +3] sessions of any REAL own ex-date of the fund (r3's rule: a placebo day inside a real window is removed)."""
import sys, json
from pathlib import Path
import pandas as pd
# TREE is the repo root (run 2026-10-27 from a scratch export of `simon` at dff4b5c)
HERE = Path(__file__).resolve().parent; TREE = HERE.parents[2]; sys.path.insert(0, str(TREE)); D = TREE / "data"
import scripts.cef.spec as spec
NAMES = list(spec.UNIVERSE) + ["NAD", "NEA", "NVG", "NZF"]
out = {}
for lab, lo, hi in (("fit", "2005-01-01", "2022-12-30"), ("test", "2023-01-01", None)):
    flt = [("date", ">=", pd.Timestamp(lo))] + ([("date", "<=", pd.Timestamp(hi))] if hi else [])
    s = pd.read_parquet(D / "cef/cef_prices.parquet", columns=["date", "ticker"], filters=flt)
    sess = pd.DatetimeIndex(sorted(pd.to_datetime(s[s.ticker.isin(NAMES)].date.unique())))
    fl = [("ex_date", ">=", pd.Timestamp(lo))] + ([("ex_date", "<=", pd.Timestamp(hi))] if hi else [])
    x = pd.read_parquet(D / "cef/cef_distributions.parquet", columns=["ticker", "ex_date"], filters=fl)
    x["ex_date"] = pd.to_datetime(x.ex_date); x = x[x.ticker.isin(NAMES)].drop_duplicates()
    sp = {d: i for i, d in enumerate(sess)}; x = x[x.ex_date.isin(sp)]; x["p"] = x.ex_date.map(sp)
    x = x[(x.p - 12 >= 0) & (x.p + 13 < len(sess))]
    own = {t: set(g.p) for t, g in x.groupby("ticker")}
    res = {"events": len(x)}
    for sft in (5, -5, 10, -10):
        ok = 0
        for _, r in x.iterrows():
            rows = [r.p + sft + k for k in (1, 2, 3)]
            if not any(abs(q - e) <= 3 for q in rows for e in own[r.ticker]): ok += 1
        res[sft] = ok
    out[lab] = res
    print(lab, res)
json.dump(out, open(HERE / "prereg_placebo_counts.json", "w"), indent=1)
