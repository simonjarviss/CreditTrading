"""A5: independent recomputation (own window from CRSP ret != retx, own Bartlett NW) and the day-2 spike by fund group."""
import numpy as np, pandas as pd
from load import load, xs, c4
ctx = load()
H, sl, held, cols, idx, crsp = (ctx[k] for k in ("H","sl","held","cols","idx","crsp"))
R0 = ctx["R0"]
c = crsp[crsp.ticker.isin(cols) & crsp.ret.notna() & crsp.retx.notna()]
if not ctx["qr"]["use_predecessor"]: raise SystemExit("qqqx rule differs")
ex = c.loc[c.ret != c.retx, ["ticker","date"]]
P = (H.shift(2).fillna(0.0) * R0).loc[sl]
G = H.shift(2).fillna(0.0).abs().loc[sl]
ip = pd.Series(np.arange(len(H.index)), index=H.index)
Wm = np.zeros(H.shape, bool); cj = {t:j for j,t in enumerate(cols)}
for t, d in zip(ex.ticker, ex.date):
    if d in ip.index: i = ip[d]; Wm[i:i+3, cj[t]] = True
Wd = pd.DataFrame(Wm, index=H.index, columns=cols).loc[sl]
S = P.where(Wd,0).to_numpy().sum()/P.to_numpy().sum(); Gs = G.where(Wd,0).to_numpy().sum()/G.to_numpy().sum()
rho = P.where(~Wd,0).to_numpy().sum()/G.where(~Wd,0).to_numpy().sum()
e = P.where(Wd,0).sum(axis=1) - rho*G.where(Wd,0).sum(axis=1)
def nw(x, L):
    x = x - x.mean(); n = len(x); v = (x*x).sum()/n
    for l in range(1, L+1): v += 2*(1-l/(L+1))*(x[l:]*x[:-l]).sum()/n
    return np.sqrt(v/n)
ev = e.to_numpy()
print(f"independent: S {S:.4f} G {Gs:.4f} CR {S/Gs:.2f} excess {e.sum()*100:+.2f}% NW(21) t {ev.mean()/nw(ev,21):+.2f} | NW(63) t {ev.mean()/nw(ev,63):+.2f}")
# the day-2 spike by group
off = xs.owner_offsets(H.index, cols, ctx["pos"])[0].loc[sl]
EV = ['EOI','ETB','ETJ','ETO','ETV','ETW','ETY','EVT','EXG']
for lab, grp in (("all", cols), ("non-EV", [t for t in cols if t not in EV]), ("EV9", EV)):
    for k in (0,1,2):
        M = Wd[grp] & (off[grp]==k)
        s_ = P[grp].where(M,0).to_numpy().sum()/P.to_numpy().sum(); g_ = G[grp].where(M,0).to_numpy().sum()/G.to_numpy().sum()
        exk = (P[grp].where(M,0) - rho*G[grp].where(M,0)).sum(axis=1).to_numpy()
        print(f"  {lab} day {k}: P&L {P[grp].where(M,0).to_numpy().sum()*100:+.2f}% gross share {g_:.4f} CR {s_/g_:.2f} excess t {exk.mean()/nw(exk,21):+.2f}")
# largest single days of day-2 P&L
d2 = P.where(Wd & (off==2), 0).sum(axis=1)
print("top 8 day-2 dates (% of capital):", (d2.sort_values(ascending=False).head(8)*100).round(2).to_dict())
print("day-2 total %:", round(d2.sum()*100,2), "without top 8 dates:", round((d2.sum()-d2.sort_values(ascending=False).head(8).sum())*100,2))
