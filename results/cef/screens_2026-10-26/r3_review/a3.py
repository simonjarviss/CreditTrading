"""A3: second method for the drift (yfinance raw close + yfinance dividends, cross-family date benchmark);
the book's net tilt by event time (does the z-score lean short into ex-dates?); EV-cluster breadth."""
import numpy as np, pandas as pd
from load import load, xs, c4
ctx = load()
H, sl, W, held, g, Ct, cols, pos, fam, pool, idx, px = (ctx[k] for k in ("H","sl","W","held","g","Ct","cols","pos","fam","pool","idx","px"))
RET, RETX = ctx["RETp"], ctx["RETXp"]
crsp, qr = ctx["crsp"], ctx["qr"]
cxp = c4.crsp_ex_dates(crsp, qr, pool); posp = xs.ex_positions(idx, pool, cxp)
nearC = xs.window_from_positions(idx, pool, posp, -3, 3)
# --- method 2: yfinance close (raw) + yfinance dividends on yfinance's own ex-dates, cross-family date benchmark
act = pd.read_parquet(xs.TREE / "data/cef_families/cef_actions.parquet", filters=[("date", "<=", xs.FIT_END)])
act["date"] = pd.to_datetime(act["date"])
dv = act[act["dividends"] > 0].pivot_table(index="date", columns="ticker", values="dividends", aggfunc="sum").reindex(index=idx, columns=pool).fillna(0.0)
cl = px.pivot_table(index="date", columns="ticker", values="close").reindex(index=idx, columns=pool)
ry_x = cl / cl.shift(1) - 1.0
ry_t = (cl + dv) / cl.shift(1) - 1.0                  # total return, yfinance
yex = dv.gt(0)
posY = {t: np.flatnonzero(yex[t].to_numpy()) for t in pool}
nearY = xs.window_from_positions(idx, pool, posY, -3, 3)
def bench(Rm, near):                                   # cross-family equal-weight, funds not within +-3 of own ex
    X = Rm.where(~near & Rm.notna())
    return X.mean(axis=1), X.notna().sum(axis=1)
for lab, Rm, near, P in (("CRSP ret, date bench (all families)", RET, nearC, posp), ("yfinance close+div, date bench", ry_t, nearY, posY),
                         ("yfinance PRICE-only (close), date bench", ry_x, nearY, posY), ("CRSP retx (price-only)", RETX, nearC, posp)):
    b, n = bench(Rm, near)
    A = Rm.sub(b.where(n >= 10), axis=0)
    out = []
    for k in range(-3, 6):
        v = []
        for t in xs.c4.universes()["frozen"] if False else ctx["UF"]:
            p = P[t]; p = p[(p + k >= 0) & (p + k < len(idx))]
            d = idx[p + k]; d = d[(d >= sl.start) & (d <= sl.stop)]
            v.append(A[t].reindex(d))
        v = pd.concat(v).dropna()
        out.append(f"{k:+d}:{v.mean()*1e4:+.1f}({v.std()/np.sqrt(len(v))*1e4:.1f})")
    print(f"{lab}: abnormal bp by offset: " + " ".join(out))
# |yield| and mean y on CRSP ex-dates of the 74
Y = (RET - RETX)[ctx["UF"]]
yv = pd.concat([Y[t].iloc[pos[t]] for t in ctx["UF"]]); yv = yv[(yv.index >= sl.start) & (yv.index <= sl.stop)]
print(f"CRSP y on ex-dates: n {len(yv)}, mean {yv.mean()*1e4:.1f}bp, median {yv.median()*1e4:.1f}bp, share < 1bp {float((yv.abs()<1e-4).mean()):.3f}")
# NAV abnormal by offset (equal-weight), date bench of NAV returns
nav = ctx["nav"].pivot_table(index="date", columns="ticker", values="nav").reindex(index=idx, columns=pool)
rN = nav / nav.shift(1) - 1.0
rNt = rN + (dv / nav.shift(1)).where(yex, 0.0)          # NAV total return using yfinance amount (NAV drop on ex)
b, n = bench(rNt, nearY)
A = rNt.sub(b.where(n >= 10), axis=0)
out = []
for k in range(-3, 6):
    v = []
    for t in ctx["UF"]:
        p = posY[t]; p = p[(p + k >= 0) & (p + k < len(idx))]
        d = idx[p + k]; d = d[(d >= sl.start) & (d <= sl.stop)]
        v.append(A[t].reindex(d))
    v = pd.concat(v).dropna(); v = v[v.abs() < 0.2]
    out.append(f"{k:+d}:{v.mean()*1e4:+.1f}({v.std()/np.sqrt(len(v))*1e4:.1f})")
print("yfinance NAV total (NAV + D/NAV on yf ex), date bench: " + " ".join(out))
# --- the book's net tilt by event time: sum signed held / sum |held| at offsets -10..+12 (held = H.shift(2), so offset k row earns R[s+k])
hl = held.loc[sl]
prof = []
for k in range(-12, 13):
    Mk = xs.window_from_positions(H.index, cols, {t: p + k for t, p in pos.items()}, 0, 0).loc[sl]
    prof.append(f"{k:+d}:{hl.where(Mk,0).to_numpy().sum()/g.where(Mk,0).to_numpy().sum():+.3f}")
print("net signed/gross of the held book by offset (row offset k = return date s+k):", " ".join(prof))
print("overall net signed/gross:", hl.to_numpy().sum()/g.to_numpy().sum())
# per-fund: in-window vs out-of-window net tilt for EV3 and rest
for grp_lab, grp in (("EV3", ["EXG","ETY","ETW"]), ("all 74", cols)):
    m = W[grp]
    print(f"  {grp_lab}: net/gross in-window {hl[grp].where(m,0).to_numpy().sum()/g[grp].where(m,0).to_numpy().sum():+.3f}, out {hl[grp].where(~m,0).to_numpy().sum()/g[grp].where(~m,0).to_numpy().sum():+.3f}")
# Eaton Vance funds in the 74 and pool
names = ctx["U"]["names"]
print("pool tickers in covered call:", sorted(t for t in pool if fam[t]=="equity_covered_call"))
print("74 covered call:", sorted(t for t in ctx["UF"] if fam[t]=="equity_covered_call"))
# do EXG/ETY/ETW share ex-dates?
s3 = [set(cxp.loc[cxp.ticker==t,"date"]) for t in ("EXG","ETY","ETW")]
print("EV3 ex-date overlap: |EXG|,|ETY|,|ETW|", [len(s) for s in s3], "common to all 3:", len(s3[0]&s3[1]&s3[2]))
# breadth: funds with positive vs negative window excess
rho_out = Ct.where(~W,0).to_numpy().sum()/g.where(~W,0).to_numpy().sum()
ex_f = (Ct.where(W,0) - rho_out*g.where(W,0)).sum()
ex_f = ex_f[g.where(W,0).sum() > 0]
print(f"funds with window exposure {len(ex_f)}: positive excess {int((ex_f>0).sum())}, negative {int((ex_f<0).sum())}; excess EV3 {ex_f[['EXG','ETY','ETW']].sum()*100:.2f}% of {ex_f.sum()*100:.2f}%")
