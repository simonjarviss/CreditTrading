"""A2: calendar vs signal. Benchmark-adjusted total returns; unconditional short-into-ex; decomposition of
C4's in-window P&L into benchmark, fund-specific ex-offset mean (calendar) and residual (selection)."""
import numpy as np, pandas as pd
from load import load, xs, c4
ctx = load()
H, sl, W, held, g, Ct, cols, pos, Wpm, fam, pool, idx, UF = (ctx[k] for k in ("H","sl","W","held","g","Ct","cols","pos","Wpm","fam","pool","idx","UF"))
RET, RETX = ctx["RETp"], ctx["RETXp"]
crsp, qr = ctx["crsp"], ctx["qr"]
cxp = c4.crsp_ex_dates(crsp, qr, pool)
posp = xs.ex_positions(idx, pool, cxp)
near = xs.window_from_positions(idx, pool, posp, -1, 3)        # own ex window widened: [-1,+3]
Y = (RET - RETX)
# benchmark: equal-weight mean total return of same-family pool funds not near their own ex-date (leave-one-out)
B = pd.DataFrame(np.nan, index=idx, columns=pool)
for fm in sorted(set(fam[t] for t in pool)):
    mem = [t for t in pool if fam[t] == fm]
    X = RET[mem].where(~near[mem])
    s, n = X.sum(axis=1, min_count=1).fillna(0.0), X.notna().sum(axis=1)
    for t in mem:
        xi = X[t]
        ss = s - xi.fillna(0.0); nn = n - xi.notna().astype(int)
        B[t] = (ss / nn).where(nn >= 3)
U = (RET - B)                                                    # abnormal total return
print("families of the 74:", pd.Series({t: fam[t] for t in UF}).value_counts().to_dict())
off, own = xs.owner_offsets(H.index, cols, pos); off, own = off.loc[sl], own.loc[sl]
Usl, Bsl = U[cols].loc[sl], B[cols].loc[sl]
hl = held.loc[sl]; R0 = ctx["R0"].loc[sl]
okU = Usl.notna()
inW = W & okU
print("window fund-days held with U defined:", float(g.where(W & okU,0).to_numpy().sum()/g.where(W,0).to_numpy().sum()))
# unconditional mean abnormal return by offset, all events of the 74 in the fit (not only held)
prof = {}
for k in range(-3, 6):
    vals = []
    for t in cols:
        p = pos[t]; p = p[(p + k >= 0) & (p + k < len(idx))]
        d = idx[p + k]; d = d[(d >= sl.start) & (d <= sl.stop)]
        v = U[t].reindex(d).dropna()
        vals.append(v)
    v = pd.concat(vals)
    prof[k] = (v.mean()*1e4, v.std()/np.sqrt(len(v))*1e4, len(v))
print("unconditional abnormal TOTAL return by offset, all 74, bp (mean, se, n):")
for k,(m,se,n) in prof.items(): print(f"  k {k:+d}: {m:+.2f} ({se:.2f}, {n})")
# fund-specific calendar: mean U at offset k for each fund (in-sample attribution)
cal = pd.DataFrame(0.0, index=Usl.index, columns=cols)
for t in cols:
    for k in (0,1,2):
        M = (off[t] == k) & W[t] & okU[t]
        mu = Usl[t][M].mean() if M.any() else 0.0
        # use the unconditional (all events, held or not) fund mean
        p = pos[t]; p = p[p + k < len(idx)]; d = idx[p + k]; d = d[(d >= sl.start) & (d <= sl.stop)]
        mu_all = U[t].reindex(d).mean()
        cal.loc[M, t] = mu_all if np.isfinite(mu_all) else 0.0
# decomposition of in-window P&L where U defined
tot = (hl * R0).where(inW, 0).to_numpy().sum()
bm = (hl * Bsl).where(inW, 0).to_numpy().sum()
calp = (hl * cal).where(inW, 0).to_numpy().sum()
sel = (hl * (Usl - cal)).where(inW, 0).to_numpy().sum()
print(f"in-window P&L (U defined) {tot*100:+.2f}% = benchmark {bm*100:+.2f}% + calendar {calp*100:+.2f}% + selection {sel*100:+.2f}%  (check {(bm+calp+sel)*100:+.2f})")
outW = (~W) & okU
tot_o = (hl * R0).where(outW, 0).to_numpy().sum(); bm_o = (hl*Bsl).where(outW,0).to_numpy().sum(); sel_o = (hl*Usl).where(outW,0).to_numpy().sum()
go, gi = g.where(outW,0).to_numpy().sum(), g.where(inW,0).to_numpy().sum()
print(f"per gross-day bp: in total {tot/gi*1e4:+.2f} bench {bm/gi*1e4:+.2f} cal {calp/gi*1e4:+.2f} sel {sel/gi*1e4:+.2f} | out total {tot_o/go*1e4:+.2f} bench {bm_o/go*1e4:+.2f} idio(sel) {sel_o/go*1e4:+.2f}")
# same by fund group
EV3 = ["EXG","ETY","ETW"]
for lab, grp in (("EV3", EV3), ("rest", [c for c in cols if c not in EV3])):
    m = pd.DataFrame(False, index=hl.index, columns=cols); m[grp] = True
    f = lambda X, M: X.where(M & m, 0).to_numpy().sum()
    gi_ = g.where(inW & m,0).to_numpy().sum(); go_ = g.where(outW & m,0).to_numpy().sum()
    print(f" {lab}: in bp/gd total {f(hl*R0,inW)/gi_*1e4:+.2f} bench {f(hl*Bsl,inW)/gi_*1e4:+.2f} cal {f(hl*cal,inW)/gi_*1e4:+.2f} sel {f(hl*(Usl-cal),inW)/gi_*1e4:+.2f} | "
          f"out total {f(hl*R0,outW)/go_*1e4:+.2f} bench {f(hl*Bsl,outW)/go_*1e4:+.2f} idio {f(hl*Usl,outW)/go_*1e4:+.2f}; in-window net signed/gross {f(hl,inW)/gi_:+.3f}")
# per-fund: unconditional [0,2] abnormal for the top funds, and C4's net position in window
print("per fund: unconditional cum abnormal [0,2] bp per event (mean, t, n) | C4 in-window net/gross, window P&L %")
for t in EV3 + ["GGN","USA","GLO","RNP","BMEZ","HQH","RQI"]:
    p = pos[t]; ev = []
    for s in p:
        if s + 2 >= len(idx) or idx[s] < sl.start or idx[s] > sl.stop: continue
        v = U[t].iloc[s:s+3]
        if v.notna().all(): ev.append(v.sum())
    ev = pd.Series(ev)
    Mt = W[t]
    print(f"  {t} ({fam[t]}): {ev.mean()*1e4:+.1f} bp, t {ev.mean()/ev.std()*np.sqrt(len(ev)):+.2f}, n {len(ev)} | "
          f"net/gross {hl[t][Mt].sum()/g[t][Mt].sum():+.2f}, window P&L {Ct[t][Mt].sum()*100:+.2f}%, out P&L {Ct[t][~Mt].sum()*100:+.2f}%")
# all-74 unconditional short-into-ex calendar book: short 1 unit vs benchmark on every event-day [0,2]
cal_d = (-(Usl.where(W & okU))).mean(axis=1)    # mean over active event-days each date
n_d = (W & okU).sum(axis=1)
cs = cal_d.dropna()
print(f"calendar book (equal-weight short of every in-window fund-day vs family benchmark): mean {cs.mean()*1e4:+.2f} bp/day, ann SR {cs.mean()/cs.std()*np.sqrt(252):+.2f}, NW t {xs.w4.nw_t(cs, 21):+.2f}, days {len(cs)}")
for lab, grp in (("EV3", EV3), ("covered-call ex-EV3", [c for c in cols if fam[c]=="equity_covered_call" and c not in EV3]), ("non-cc", [c for c in cols if fam[c]!="equity_covered_call"])):
    x = (-(Usl[grp].where(W[grp] & okU[grp]))).stack().dropna()
    print(f"  {lab}: mean short-in-window abnormal {x.mean()*1e4:+.2f} bp/fund-day, n {len(x)}")
