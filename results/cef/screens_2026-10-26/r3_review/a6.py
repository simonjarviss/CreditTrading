"""A6: date-level fragility: drop whole sessions (all cells) with the largest in-window P&L; and the 2015-08-24 cell."""
import numpy as np, pandas as pd
from load import load, xs
ctx = load()
Ct, g, W, Wpm = (ctx[k] for k in ("Ct","g","W","Wpm"))
inw = Ct.where(W,0).sum(axis=1)
top = inw.sort_values(ascending=False).index
for k in (1, 3, 5, 10):
    keep = ~Ct.index.isin(top[:k])
    r = xs.wstats(Ct[keep], g[keep], W[keep]); p = xs.wstats(Ct[keep], g[keep], Wpm[keep])
    print(f"drop top {k} sessions by in-window P&L: CR {r['CR']:.2f} t {r['excess_nw_t']:+.2f} | placebo CR {p['CR']:.2f}")
d = pd.Timestamp("2015-08-24")
print("2015-08-24 in-window P&L by fund (%):", (Ct.loc[d].where(W.loc[d],0)*100).round(2)[lambda s: s.abs()>0.05].to_dict())
