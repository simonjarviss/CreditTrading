"""Second-method check of the post-ex-date drift in C4's family CEFs (zero trials).
Independent of c4_families.py: own returns from close + cash distributions, own date benchmark.
Fit window only: every return <= 2022-12-30 (asserted). Read-only on data/.
Offset 0 = ex-date. Ex-dates are announced in advance, so a short decided at day -1 and
filled at the day-0 close (shift(2)-compatible) earns offsets +1..+3 and owes no distribution."""
import numpy as np, pandas as pd, sys
ROOT = sys.argv[1]
END = pd.Timestamp("2022-12-30")
px = pd.read_parquet(f"{ROOT}/data/cef_families/cef_prices.parquet")
ac = pd.read_parquet(f"{ROOT}/data/cef_families/cef_actions.parquet")
u = pd.read_csv(f"{ROOT}/data/cef_families/universe.csv")
u = u[u.included]
px = px[px.ticker.isin(u.ticker) & (px.date <= END)]
assert px.date.max() <= END
close = px.pivot(index="date", columns="ticker", values="close").sort_index()
ac = ac[ac.ticker.isin(close.columns) & (ac.date <= END)]
div = ac.pivot_table(index="date", columns="ticker", values="dividends", aggfunc="sum").reindex(close.index).fillna(0.0)  # 0 = no distribution that day (an absent row is a fact, not a gap)
spl = ac[ac.stock_splits > 0]
ret = (close + div) / close.shift(1) - 1          # total return, close-to-close
# exclude split days +-5 sessions and any |ret|>30% (bad bars, per the C4 IGR incident)
bad = pd.DataFrame(False, index=ret.index, columns=ret.columns)
for _, r in spl.iterrows():
    if r.ticker in bad.columns:
        i = ret.index.searchsorted(r.date)
        bad.iloc[max(0, i-5):i+6, bad.columns.get_loc(r.ticker)] = True
ret = ret.mask(bad | (ret.abs() > 0.30))
bench = ret.mean(axis=1)                         # equal-weight all included funds, same date
ab = ret.sub(bench, axis=0)
pos = {d: i for i, d in enumerate(ret.index)}
spon = u.set_index("ticker").sponsor; fam = u.set_index("ticker").family
rows = []
for _, e in ac[ac.dividends > 0].iterrows():
    if e.date not in pos: continue
    i = pos[e.date]; t = e.ticker
    if i < 2 or i + 5 >= len(ret): continue
    col = ab[t].values
    rec = {"date": e.date, "ticker": t, "yld": e.dividends / close[t].iloc[i-1],
           "spon": spon[t], "fam": fam[t]}
    for k in range(-2, 6): rec[k] = col[i + k]
    rows.append(rec)
ev = pd.DataFrame(rows).dropna(subset=[1, 2, 3])
ev["car13"] = ev[[1, 2, 3]].sum(axis=1)
ev["ev"] = ev.spon.str.contains("Eaton Vance")
ev["era"] = pd.cut(ev.date.dt.year, [2004, 2009, 2015, 2022], labels=["2005-09", "2010-15", "2016-22"])
def tstat(g):
    # cluster by calendar month: average events within a month, t over months
    m = g.groupby(g.date.dt.to_period("M"))["car13"].mean()
    return pd.Series({"n_ev": len(g), "mean_bp": 1e4 * g.car13.mean(), "t_month": m.mean() / m.std() * np.sqrt(len(m)), "share_neg": (g.car13 < 0).mean()})
print("events", len(ev), "funds", ev.ticker.nunique(), "first", ev.date.min().date(), "last", ev.date.max().date())
print("\nmean abnormal return by offset, bp (all events):")
print((1e4 * ev[[-2, -1, 0, 1, 2, 3, 4, 5]].mean()).round(1).to_string())
print("\nCAR(+1..+3), short from the ex-date close:")
print(tstat(ev).round(3).to_string())
for name, g in [("Eaton Vance", ev[ev.ev]), ("ex Eaton Vance", ev[~ev.ev])]:
    print(f"\n{name}:"); print(tstat(g).round(3).to_string())
print("\nby era (ex Eaton Vance):"); print(ev[~ev.ev].groupby("era", observed=True).apply(tstat).round(3).to_string())
print("\nby family (ex Eaton Vance):"); print(ev[~ev.ev].groupby("fam").apply(tstat).round(3).to_string())
ev["yq"] = pd.qcut(ev.yld, 4, labels=["Q1 low", "Q2", "Q3", "Q4 high"])
print("\nby distribution size quartile (all):"); print(ev.groupby("yq", observed=True).apply(tstat).round(3).to_string())

# Added 2026-10-27: the pooled figures above span every year in the panel (1982-2022).
# The same statistic on 2005-2022 only, the window the credit check and the eras use.
e05 = ev[ev.date >= "2005-01-01"]
print("\nCAR(+1..+3), 2005-2022 only (all funds):"); print(tstat(e05).round(3).to_string())
print("\nCAR(+1..+3), 2005-2022 only, ex Eaton Vance:"); print(tstat(e05[~e05.ev]).round(3).to_string())
