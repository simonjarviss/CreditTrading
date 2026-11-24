"""A7: recheck the two calendar-book t-stats with an own Bartlett NW."""
import numpy as np, pandas as pd
from load import load, xs, c4
ctx = load()
sl, W, g, cols, fam, pool, idx, UF, pos = (ctx[k] for k in ("sl","W","g","cols","fam","pool","idx","UF","pos"))
RET = ctx["RETp"]; crsp, qr = ctx["crsp"], ctx["qr"]
cxp = c4.crsp_ex_dates(crsp, qr, pool); posp = xs.ex_positions(idx, pool, cxp)
def nw(x, L=21):
    x = np.asarray(x, float); m = x.mean(); y = x - m; n = len(y); v = (y*y).sum()/n
    for l in range(1, L+1): v += 2*(1-l/(L+1))*(y[l:]*y[:-l]).sum()/n
    return m/np.sqrt(v/n)
# date benchmark
nearC = xs.window_from_positions(idx, pool, posp, -3, 3)
X = RET.where(~nearC & RET.notna()); b = X.mean(axis=1).where(X.notna().sum(axis=1) >= 10)
A = RET[cols].sub(b, axis=0).loc[sl]
# family benchmark (as A2)
near13 = xs.window_from_positions(idx, pool, posp, -1, 3)
B = pd.DataFrame(np.nan, index=idx, columns=pool)
for fm in sorted(set(fam[t] for t in pool)):
    mem = [t for t in pool if fam[t] == fm]; Xf = RET[mem].where(~near13[mem])
    s, n = Xf.sum(axis=1, min_count=1).fillna(0.0), Xf.notna().sum(axis=1)
    for t in mem:
        xi = Xf[t]; ss = s - xi.fillna(0.0); nn = n - xi.notna().astype(int); B[t] = (ss/nn).where(nn >= 3)
U = (RET - B)[cols].loc[sl]
ew_fam = (-(U.where(W & U.notna()))).mean(axis=1).dropna()
ew_date = (-(A.where(W & A.notna()))).mean(axis=1).dropna()
gw_date = (-(g.where(W,0.0) * A.where(W & A.notna(), 0.0))).sum(axis=1)
for lab, s in (("EW family bench", ew_fam), ("EW date bench", ew_date), ("C4-gross-weighted date bench", gw_date)):
    print(f"{lab}: mean {s.mean()*1e4:+.2f}bp/day, n {len(s)}, own NW21 t {nw(s):+.2f}, w4.nw_t {xs.w4.nw_t(s,21):+.2f}, ann SR {s.mean()/s.std()*np.sqrt(252):+.2f}")
# per-event cum [0,2] abnormal, date bench
evs = []
for t in cols:
    for p in pos[t]:
        if p + 2 < len(idx) and sl.start <= idx[p] <= sl.stop:
            v = A[t].reindex(idx[p:p+3])
            if v.notna().all(): evs.append(v.sum())
evs = pd.Series(evs)
print(f"per-event cum [0,2] abnormal (date bench): mean {evs.mean()*1e4:+.1f}bp, median {evs.median()*1e4:+.1f}bp, share < 0 {float((evs<0).mean()):.3f}, n {len(evs)}")
