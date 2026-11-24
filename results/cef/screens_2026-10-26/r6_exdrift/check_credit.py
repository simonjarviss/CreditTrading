"""Same post-ex drift measurement on the credit CEFs (deployed 13 + NAD/NEA/NVG/NZF = the wide 17).
Fit window only (<= 2022-12-30, asserted). The 27 sealed names are never loaded into the return panel."""
import numpy as np, pandas as pd, sys
ROOT = sys.argv[1]; sys.path.insert(0, f"{ROOT}/scripts/cef")
import spec
END = pd.Timestamp("2022-12-30")
names = list(spec.UNIVERSE) + ["NAD", "NEA", "NVG", "NZF"]
px = pd.read_parquet(f"{ROOT}/data/cef/cef_prices.parquet"); px = px[px.ticker.isin(names) & (px.date <= END)]
assert px.date.max() <= END and px.ticker.nunique() == 17
close = px.pivot(index="date", columns="ticker", values="close").sort_index()
d = pd.read_parquet(f"{ROOT}/data/cef/cef_distributions.parquet"); d = d[d.ticker.isin(names) & (d.ex_date <= END)]
div = d[d.amount > 0].pivot_table(index="ex_date", columns="ticker", values="amount", aggfunc="sum").reindex(close.index).fillna(0.0)  # absent = no distribution that day
ret = ((close + div) / close.shift(1) - 1)
bad = pd.DataFrame(False, index=ret.index, columns=ret.columns)
for _, r in d[d.stock_split > 0].iterrows():
    i = ret.index.searchsorted(r.ex_date); bad.iloc[max(0, i-5):i+6, bad.columns.get_loc(r.ticker)] = True
ret = ret.mask(bad | (ret.abs() > 0.30))
ab = ret.sub(ret.mean(axis=1), axis=0)
pos = {x: i for i, x in enumerate(ret.index)}; grp = px.drop_duplicates("ticker").set_index("ticker").grp
rows = []
for _, e in d[d.amount > 0].iterrows():
    if e.ex_date not in pos: continue
    i = pos[e.ex_date]
    if i < 2 or i + 5 >= len(ret): continue
    rec = {"date": e.ex_date, "ticker": e.ticker, "grp": grp[e.ticker]}
    for k in range(-2, 6): rec[k] = ab[e.ticker].values[i + k]
    rows.append(rec)
ev = pd.DataFrame(rows).dropna(subset=[1, 2, 3]); ev = ev[ev.date >= "2005-01-01"]
ev["car13"] = ev[[1, 2, 3]].sum(axis=1)
def tstat(g):
    m = g.groupby(g.date.dt.to_period("M"))["car13"].mean()
    return pd.Series({"n_ev": len(g), "mean_bp": 1e4 * g.car13.mean(), "t_month": m.mean() / m.std() * np.sqrt(len(m))})
print("credit CEFs, 2005-2022:", len(ev), "events on", ev.ticker.nunique(), "funds")
print((1e4 * ev[[-2, -1, 0, 1, 2, 3, 4, 5]].mean()).round(1).to_string())
print(tstat(ev).round(3).to_string())
print(ev.groupby("grp")[["car13"]].apply(tstat).round(3).to_string())
