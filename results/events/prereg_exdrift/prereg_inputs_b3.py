"""r8, third helper (calendar feasibility + DISPERSION only; no mean is printed for any new hedge).

Declared before running (2026-10-27), after prereg_inputs_b2.py: the candidate basket H-E is the
equal-weight basket of the OTHER universe funds with no own ex-date in [p+1, p+8] (so no basket
fund's ex-day or run-up offsets -5..0 fall on the hold rows p+1..p+3: that contamination would
bias the test FOR the trade). Funds that went ex at or before p stay in: their own post-ex drift
on the hold rows biases the test AGAINST the trade (conservative). Minimum 3 funds. Also printed:
H-D, the equal-weight basket of all 17 on the same date (r6's own benchmark), dispersion only.
Fit 2005-22 only; 2023+ ex-date DATES only (for the test-set basket count)."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
# TREE is the repo root (run 2026-10-27 from a scratch export of `simon` at dff4b5c)
HERE = Path(__file__).resolve().parent; TREE = HERE.parents[2]; sys.path.insert(0, str(TREE)); D = TREE / "data"
FIT_START, FIT_END, TEST_START = pd.Timestamp("2005-01-01"), pd.Timestamp("2022-12-30"), pd.Timestamp("2023-01-01")
import scripts.cef.spec as spec
CORE = list(spec.UNIVERSE); NAMES = CORE + ["NAD", "NEA", "NVG", "NZF"]
def ff(path, cols=None, dc="date"):
    d = pd.read_parquet(path, columns=cols, filters=[(dc, "<=", FIT_END)]); d[dc] = pd.to_datetime(d[dc]); assert d[dc].max() <= FIT_END; return d
px = ff(D / "cef/cef_prices.parquet"); px = px[px.ticker.isin(NAMES)]
close = px.pivot(index="date", columns="ticker", values="close").sort_index()
dist = ff(D / "cef/cef_distributions.parquet", dc="ex_date"); dist = dist[dist.ticker.isin(NAMES)]
div = dist[dist.amount > 0].pivot_table(index="ex_date", columns="ticker", values="amount", aggfunc="sum").reindex(close.index).reindex(columns=close.columns).fillna(0.0)  # absent = no distribution
ret = (close + div) / close.shift(1) - 1.0
bad = pd.DataFrame(False, index=ret.index, columns=ret.columns)
for _, r in dist[dist.stock_split > 0].iterrows():
    i = ret.index.searchsorted(r.ex_date); bad.iloc[max(0, i-5):i+6, bad.columns.get_loc(r.ticker)] = True
ret = ret.mask(bad | (ret.abs() > 0.30)); idx = ret.index; pos = {x: i for i, x in enumerate(idx)}
exd = dist[(dist.amount > 0)][["ticker", "ex_date"]]
near = pd.DataFrame(False, index=idx, columns=NAMES)
for _, r in exd.iterrows():
    if r.ex_date in pos: near.iloc[pos[r.ex_date], near.columns.get_loc(r.ticker)] = True
R = ret[NAMES]; ew = R.mean(axis=1)
rec = []
for _, e in exd[exd.ex_date >= FIT_START].iterrows():
    if e.ex_date not in pos: continue
    i = pos[e.ex_date]
    if i < 2 or i + 9 >= len(idx): continue
    rows3 = [i+1, i+2, i+3]; ri = R[e.ticker].values[rows3]
    if not np.isfinite(ri).all(): continue
    blk = near.iloc[i+1:i+9]
    cand = [j for j in NAMES if j != e.ticker and not blk[j].any() and np.isfinite(R[j].values[rows3]).all()]
    he = float(-(ri - R[cand].values[rows3].mean(axis=1)).sum()) if len(cand) >= 3 else np.nan
    rec.append(dict(date=e.ex_date, ticker=e.ticker, nb=len(cand), he=he, hd=float(-(ri - ew.values[rows3]).sum())))
E = pd.DataFrame(rec)
mm = lambda c: E.dropna(subset=[c]).groupby(E.dropna(subset=[c]).date.dt.to_period("M"))[c]
print(f"H-E basket (no own ex in [p+1,p+8]), fit: events {len(E)}, size median {E.nb.median():.0f}, p10 {E.nb.quantile(.1):.0f}, share < 3 {float((E.nb<3).mean()):.3f}")
for c, lab in (("he", "H-E"), ("hd", "H-D (EW all 17, same date)")):
    g = E.dropna(subset=[c]); m = mm(c)
    print(f"  {lab} DISPERSION ONLY: events {len(g)}, per-event sd {1e4*g[c].std():.1f}bp, sd of monthly means {1e4*m.mean().std():.1f}bp over {m.ngroups} months, sd of monthly sums {1e4*m.sum().std():.1f}bp")
# test set, calendar only
xd = pd.read_parquet(D / "cef/cef_distributions.parquet", columns=["ticker", "ex_date"], filters=[("ex_date", ">=", TEST_START)])
xd["ex_date"] = pd.to_datetime(xd.ex_date); xd = xd[xd.ticker.isin(NAMES)].drop_duplicates()
sess = pd.DatetimeIndex(sorted(pd.to_datetime(pd.read_parquet(D / "cef/cef_prices.parquet", columns=["date", "ticker"], filters=[("date", ">=", TEST_START)]).query("ticker in @NAMES").date.unique())))
sp = {x: i for i, x in enumerate(sess)}; xd["p"] = xd.ex_date.map(sp); xd = xd.dropna(subset=["p"]); xd["p"] = xd.p.astype(int); xd = xd[xd.p + 3 < len(sess)]
nt = pd.DataFrame(False, index=range(len(sess)), columns=NAMES)
for _, r in xd.iterrows(): nt.loc[r.p, r.ticker] = True
# the last 8 sessions' baskets would need ex-dates after the panel; count them as unknown
xd["nb"] = [sum(1 for j in NAMES if j != r.ticker and not nt.loc[r.p+1:min(r.p+8, len(sess)-1), j].any()) for _, r in xd.iterrows()]
print(f"test (dates only): events {len(xd)}, H-E size median {xd.nb.median():.0f}, share < 3 {float((xd.nb<3).mean()):.3f}, traded {int((xd.nb>=3).sum())} ({int(((xd.nb>=3)&xd.ticker.isin(CORE)).sum())} on the 13)")
json.dump(dict(fit_events=len(E), fit_share_lt3=float((E.nb<3).mean()), fit_median=float(E.nb.median()),
               he_sd=1e4*E.he.std(), he_sd_month_mean=1e4*mm("he").mean().std(), he_months=int(mm("he").ngroups), he_events=int(E.he.notna().sum()),
               he_sd_month_sum=1e4*mm("he").sum().std(),
               hd_sd=1e4*E.hd.std(), hd_sd_month_mean=1e4*mm("hd").mean().std(), hd_months=int(mm("hd").ngroups),
               test_events=len(xd), test_traded=int((xd.nb>=3).sum()), test_traded_13=int(((xd.nb>=3)&xd.ticker.isin(CORE)).sum())),
          open(HERE / "prereg_inputs_b3.json", "w"), indent=1)
