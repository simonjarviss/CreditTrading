"""A1: per-day/per-side rates; day-2 split into carried vs traded-at-s; fund and year concentration."""
import numpy as np, pandas as pd
from load import load, xs, c4
ctx = load()
H, R0, sl, W, held, g, Ct, cols, pos, Wpm = (ctx[k] for k in ("H","R0","sl","W","held","g","Ct","cols","pos","Wpm"))
off, own = xs.owner_offsets(H.index, cols, pos); off, own = off.loc[sl], own.loc[sl]
gs = g.to_numpy().sum()
bp = lambda pnl, gg: pnl / gg * 1e4 if gg else np.nan
hl = held.loc[sl]
print("book avg bp/gross-day", bp(Ct.to_numpy().sum(), gs))
outM = ~W
for side, Ms in (("long", hl > 0), ("short", hl < 0)):
    M = Ms & outM
    print(f"OUT {side}: bp/gross-day {bp(Ct.where(M,0).to_numpy().sum(), g.where(M,0).to_numpy().sum()):+.2f}")
    for k in (0,1,2):
        M = Ms & W & (off == k)
        print(f"  day {k} {side}: {bp(Ct.where(M,0).to_numpy().sum(), g.where(M,0).to_numpy().sum()):+.2f}")
# day-2 decomposition: held at s+2 is H[s]; split into H[s-1] (carried) and H[s]-H[s-1] (traded on the ex-date's decision)
Hs1 = H.shift(3).fillna(0.0).loc[sl]       # H[t-3] on row t: for day-2 rows this is H[s-1]
dH = (held.loc[sl] - Hs1)
for k in (0,1,2):
    M = W & (off == k)
    car = (Hs1 * R0.loc[sl]).where(M, 0).to_numpy().sum() * 100
    trd = (dH * R0.loc[sl]).where(M, 0).to_numpy().sum() * 100
    print(f"day {k}: carried(H[t-3]) {car:+.2f}%  traded-at-(t-2) {trd:+.2f}%  |dH| sum {dH.abs().where(M,0).to_numpy().sum():.2f}")
# ordinary days: traded component share
M = ~W
print("out-of-window: carried", (Hs1*R0.loc[sl]).where(M,0).to_numpy().sum()*100, "traded", (dH*R0.loc[sl]).where(M,0).to_numpy().sum()*100,
      "|dH| per fund-day held", dH.abs().where(M,0).to_numpy().sum()/ (g.where(M,0)>0).to_numpy().sum())
for k in (0,1,2):
    M = W & (off == k)
    print(f"  |dH| per held fund-day, day {k}:", dH.abs().where(M,0).to_numpy().sum()/(g.where(M,0)>0).to_numpy().sum())
# excess by fund
rho_out = Ct.where(~W,0).to_numpy().sum()/g.where(~W,0).to_numpy().sum()
ex_f = (Ct.where(W,0) - rho_out*g.where(W,0)).sum()
tot_ex = ex_f.sum()
print("total excess %", tot_ex*100)
s = (ex_f/tot_ex).sort_values(ascending=False)
print("excess share by fund, top 10:", s.head(10).round(3).to_dict())
print("cum top5", s.head(5).sum(), "top10", s.head(10).sum(), "n funds with window P&L", (g.where(W,0).sum()>0).sum())
# by year
ex_y = (Ct.where(W,0) - rho_out*g.where(W,0)).sum(axis=1).groupby(lambda d: d.year).sum()
print("excess by year (% of capital):", (ex_y*100).round(2).to_dict())
# leave-one-fund-out CR and t, for the top 5 funds
def stats_drop(drop):
    keep = [c for c in cols if c not in drop]
    r = xs.wstats(Ct[keep], g[keep], W[keep]); p = xs.wstats(Ct[keep], g[keep], Wpm[keep])
    return r["CR"], r["excess_nw_t"], p["CR"]
for t in s.head(5).index:
    print("drop", t, [round(v,2) for v in stats_drop([t])])
print("drop top3", [round(v,2) for v in stats_drop(list(s.head(3).index))])
print("drop top5", [round(v,2) for v in stats_drop(list(s.head(5).index))])
# leave-one-year-out
for y in sorted(set(Ct.index.year)):
    m = Ct.index.year != y
    r = xs.wstats(Ct[m], g[m], W[m]); p = xs.wstats(Ct[m], g[m], Wpm[m])
    if y >= 2008: print("drop year", y, round(r["CR"],2), round(r["excess_nw_t"],2), round(p["CR"],2))
