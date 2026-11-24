"""A4: (i) calendar-removed concentration: subtract the all-74 mean abnormal return at offsets -3..+3 (one number
per offset, no per-fund fit) and recompute CR / excess t for the real window and the +-5 placebo; (ii) window
sensitivity; (iii) EV sponsor cluster defined by sponsor, not by P&L; (iv) ambiguous events: NAV slope and excess."""
import numpy as np, pandas as pd
from load import load, xs, c4
ctx = load()
H, sl, W, held, g, Ct, cols, pos, fam, pool, idx, UF, Wpm = (ctx[k] for k in ("H","sl","W","held","g","Ct","cols","pos","fam","pool","idx","UF","Wpm"))
RET, RETX, R0 = ctx["RETp"], ctx["RETXp"], ctx["R0"]
crsp, qr = ctx["crsp"], ctx["qr"]
cxp = c4.crsp_ex_dates(crsp, qr, pool); posp = xs.ex_positions(idx, pool, cxp)
nearC = xs.window_from_positions(idx, pool, posp, -3, 3)
X = RET.where(~nearC & RET.notna()); b = X.mean(axis=1).where(X.notna().sum(axis=1) >= 10)
A = RET[UF].sub(b, axis=0)
abar = {}
for k in range(-3, 4):
    v = []
    for t in UF:
        p = pos[t]; p = p[(p + k >= 0) & (p + k < len(idx))]; d = idx[p + k]; d = d[(d >= sl.start) & (d <= sl.stop)]
        v.append(A[t].reindex(d))
    abar[k] = float(pd.concat(v).dropna().mean())
print("all-74 mean abnormal by offset (bp):", {k: round(v*1e4, 1) for k, v in abar.items()})
# calendar return frame: abar[k] on the fund-day at offset k of an ex-date (nearest owner; offsets -3..+3)
CAL = pd.DataFrame(0.0, index=H.index, columns=cols)
for k, a in abar.items():
    Mk = xs.window_from_positions(H.index, cols, {t: p + k for t, p in pos.items()}, 0, 0)
    CAL = CAL.where(~Mk, a)
CAL = CAL.loc[sl]
hl = held.loc[sl]
Cc = hl * (R0.loc[sl] - CAL)          # calendar-removed P&L cells
Ccal = hl * CAL                       # the calendar part alone
print(f"calendar part of all P&L {Ccal.to_numpy().sum()*100:+.2f}%; in [0,2] {Ccal.where(W,0).to_numpy().sum()*100:+.2f}% of in-window {Ct.where(W,0).to_numpy().sum()*100:+.2f}%")
for lab, C in (("as is", Ct), ("calendar removed", Cc)):
    r = xs.wstats(C, g, W); p = xs.wstats(C, g, Wpm)
    print(f"  {lab}: real CR {r['CR']:.2f} excess {r['excess_pct']:+.2f}% t {r['excess_nw_t']:+.2f} | placebo CR {p['CR']:.2f} t {p['excess_nw_t']:+.2f}")
# a z-blind calendar overlay on the SAME held gross: in every [0,2] fund-day, short |held| against the date benchmark
gb = g.where(W, 0.0)
ov = (-(gb * A[cols].loc[sl].reindex_like(gb))).where(W, 0.0).fillna(0.0).sum(axis=1)
print(f"z-blind overlay: short the same in-window |held| gross vs date benchmark: {ov.sum()*100:+.2f}% total, {ov.mean()*252*100:+.2f}%/yr, NW t {xs.w4.nw_t(ov,21):+.2f}  (C4 in-window: {Ct.where(W,0).to_numpy().sum()*100:+.2f}%)")
# (ii) window sensitivity on return-date offsets
print("window sensitivity (return-date offsets): CR, excess t")
for lo, hi in ((0,0),(1,1),(2,2),(3,3),(0,1),(0,3),(1,3),(2,4),(-2,0),(-3,-1)):
    Wk = xs.window_from_positions(H.index, cols, pos, lo, hi).loc[sl]
    r = xs.wstats(Ct, g, Wk)
    print(f"  [{lo},{hi}]: S {r['S']:.3f} G {r['G']:.3f} CR {r['CR']:.2f} t {r['excess_nw_t']:+.2f}")
# (iii) sponsor cluster: every Eaton Vance fund in the 74 (by ticker family list, not by P&L)
EV = [t for t in UF if t in {"EOI","EOS","ETB","ETJ","ETV","ETW","ETY","EXG","EVT","ETG","ETO","EVV","EFT","EFR","EVF","EVG","EIM","EOT","EVN","EVM"}]
print("Eaton Vance funds in the 74:", EV)
names = ctx["U"]["names"]
for c in ("sponsor", "manager", "adviser", "name"):
    if c in names.columns:
        print(" names column", c, names.set_index("ticker").loc[EV, c].to_dict()); break
keep = [c for c in cols if c not in EV]
r = xs.wstats(Ct[keep], g[keep], W[keep]); p = xs.wstats(Ct[keep], g[keep], Wpm[keep])
print(f"without all {len(EV)} EV funds: real CR {r['CR']:.2f} t {r['excess_nw_t']:+.2f} S {r['S']:.3f} | placebo CR {p['CR']:.2f}")
for fm in sorted(set(fam[t] for t in cols)):
    k2 = [c for c in cols if fam[c] != fm]
    r = xs.wstats(Ct[k2], g[k2], W[k2]); p = xs.wstats(Ct[k2], g[k2], Wpm[k2])
    print(f"  without family {fm}: real CR {r['CR']:.2f} t {r['excess_nw_t']:+.2f} | placebo CR {p['CR']:.2f}")
# EV3 excess by year
rho_out = Ct.where(~W,0).to_numpy().sum()/g.where(~W,0).to_numpy().sum()
e3 = (Ct[["EXG","ETY","ETW"]].where(W[["EXG","ETY","ETW"]],0) - rho_out*g[["EXG","ETY","ETW"]].where(W[["EXG","ETY","ETW"]],0)).sum(axis=1)
print("EV3 window excess by year (%):", (e3.groupby(e3.index.year).sum()*100).round(2).to_dict())
# (iv) ambiguous events
own = xs.owner_offsets(H.index, cols, pos)[1].loc[sl]
ev = xs.event_alignment(crsp, qr, pool, UF, fam, ctx["px"], ctx["nav"], idx, hl, W, own, sl)
E = ev["events"]
def slope(sub, ycols, xcol):
    out = []
    for c in ycols:
        d = sub[[c, xcol]].dropna(); x, y = d[xcol].to_numpy(), d[c].to_numpy()
        bb = (x*y).sum()/(x*x).sum(); e = y - bb*x; se = np.sqrt((x*x*e*e).sum())/(x*x).sum()
        out.append(f"{bb:+.3f}({se:.3f})")
    return " ".join(out)
for lab, m in (("ambiguous, all", E.cls=="ambiguous"), ("ambiguous, held", (E.cls=="ambiguous") & E.held), ("aligned, held", (E.cls=="0") & E.held)):
    sub = E[m]
    print(f"{lab} n {len(sub)}: NAV slope k-2..+2 {slope(sub, ['u_m2','u_m1','u_0','u_p1','u_p2'], 'q')}; median |q|/sigma {(sub.q.abs()/sub.sigma).median():.2f}")
# held-gross-weighted slope for ambiguous held (weights = held gross)
sub = E[(E.cls=="ambiguous") & E.held]
w = sub.held_gross.to_numpy()
for c in ("u_m1","u_0","u_p1"):
    d = sub[[c,"q"]].assign(w=w).dropna()
    bb = (d.w*d.q*d[c]).sum()/(d.w*d.q*d.q).sum()
    print(f"  ambiguous held, gross-weighted NAV slope {c}: {bb:+.3f}")
# excess carried by each class
for c in ("0","ambiguous","unmeasurable","+1","-1","none"):
    M = xs._event_mask(E[E.cls==c], own, W, cols)
    exc = (Ct.where(M,0) - rho_out*g.where(M,0)).to_numpy().sum()
    print(f"  class {c}: window excess {exc*100:+.2f}% of {(Ct.where(W,0)-rho_out*g.where(W,0)).to_numpy().sum()*100:+.2f}%")
# analytical check: an exactly aligned event (u0=q, others 0) at |q|/sigma = z: LL_0 - LL_none = z^2/2
print("exactly aligned event is 'ambiguous' (LL0-LLnone < 2) when |q|/sigma <", np.sqrt(4.0))
print("share of measurable events with |q|/sigma < 2:", float(((E.q.abs()/E.sigma) < 2).sum() / (E.cls!='unmeasurable').sum()))
