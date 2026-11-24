"""Exploratory, post-hoc (console only, nothing written): are the late-price-drop events misdated?
Finding 2026-10-26: yfinance dates every one of them on the CRSP ex-date (offset 0), and most have an
aligned NAV; the largest coincide with market shocks (ETW 2015-08-20, s+2 = 2015-08-24)."""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import exdate_screen as xs
import exdate_posthoc as ph
ctx = xs.setup(); xs.LOG.clear()
Ct, Cx, g, W, held, sl, cols, idx = (ctx[k] for k in ("Ct","Cx","g","W","held","sl","cols","idx"))
off, own = xs.owner_offsets(ctx["H"].index, cols, ctx["pos"]); off, own = off.loc[sl], own.loc[sl]
ev = xs.event_alignment(ctx["crsp"], ctx["qr"], ctx["pool"], ctx["UF"], ctx["fam"], ctx["px"], ctx["nav"], idx, held.loc[sl], W, own, sl)
E, uP, near = ev["events"], ev["uP"], ev["near"]
E = xs.dispute_flags(E, idx, ctx["px"], sl)
n=len(idx)
# re-run price classification (same code as posthoc P1)
rows=[]
for t,s,y in zip(E.ticker,E.s,E.y):
    u=[uP[t].iat[s+k] if 0<=s+k<n else np.nan for k in (-1,0,1,2)]
    a=max(0,s-xs.SIG_LOOKBACK-1); h=uP[t].iloc[a:s-1]; ok=~near[t].iloc[a:s-1]&h.notna(); hv=h[ok]
    rows.append((u, float(hv.std()) if len(hv)>=xs.SIG_MIN else np.nan, -y))
U4=np.array([r[0] for r in rows]); sig=np.array([r[1] for r in rows]); q=np.array([r[2] for r in rows])
meas=np.isfinite(U4).all(1)&np.isfinite(sig)&(sig>0)
cls=np.array(["unmeasurable"]*len(E),dtype=object)
Um,qm,s2=U4[meas],q[meas][:,None],2*sig[meas][:,None]**2; base=(Um**2).sum(1)[:,None]
LL=np.hstack([-(base-Um**2+(Um-qm)**2)/s2,-base/s2]); labs=np.array(["-1","0","+1","+2","none"]); o=np.argsort(-LL,1)
b=LL[np.arange(len(LL)),o[:,0]]; s_=LL[np.arange(len(LL)),o[:,1]]
cls[meas]=np.where(b-s_>=xs.LR_MIN,labs[o[:,0]],"ambiguous"); E["pcls"]=cls
print("NAV cls x price cls (held events):"); print(pd.crosstab(E.loc[E.held,"cls"],E.loc[E.held,"pcls"]))
# yfinance dividend dates near CRSP s for late-drop events
act=pd.read_parquet(xs.TREE/"data/cef_families/cef_actions.parquet",filters=[("date","<=",xs.FIT_END)]); act["date"]=pd.to_datetime(act.date)
dvd=act[act.dividends>0][["ticker","date"]]
def yf_offset(t,s):
    d=dvd[dvd.ticker==t].date; p=idx.get_indexer(pd.DatetimeIndex(d)); p=p[p>=0]
    if not len(p): return None
    k=p-s; k=k[np.abs(k)<=5]
    return int(k[np.argmin(np.abs(k))]) if len(k) else None
for c in ("+1","+2"):
    sub=E[(E.pcls==c)]
    offs=[yf_offset(t,s) for t,s in zip(sub.ticker,sub.s)]
    print(f"\nprice class {c}: {len(sub)} events, held {int(sub.held.sum())}; yfinance dividend offset vs CRSP ex-date: {pd.Series(offs).value_counts(dropna=False).to_dict()}")
    print("  by fund:", sub.ticker.value_counts().head(10).to_dict())
    print("  by year:", sub.date.dt.year.value_counts().sort_index().to_dict())
    print("  y>2%:", int((sub.y>0.02).sum()), " month Dec:", int((sub.date.dt.month==12).sum()))
    # window P&L per event for the held ones, top 8 (P&L as % of capital; no CRSP values)
    ownW=own.where(W,-1)
    ep=[]
    for t,s in zip(sub.ticker,sub.s):
        m=(ownW[t]==s).to_numpy()
        ep.append((t,str(idx[s].date()),round(float(Ct[t].to_numpy()[m].sum()*100),3), round(float(Cx[t].to_numpy()[m].sum()*100),3)))
    ep=sorted(ep,key=lambda r:-abs(r[2]))[:8]; print("  top events (ticker, CRSP ex-date, window total %, price-only %):", ep)
# all-events overlap: overall yfinance offset distribution for comparison
offs_all=[yf_offset(t,s) for t,s in zip(E.ticker,E.s)]
print("\nall events: yfinance dividend offset vs CRSP:", pd.Series(offs_all).value_counts(dropna=False).to_dict())
