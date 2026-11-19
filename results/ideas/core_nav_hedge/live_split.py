"""The cef paper book's P&L since it started, split into NAV part, discount part and fills.

    QUANTT_ENV_FILE=<env> python3 results/ideas/core_nav_hedge/live_split.py <data/cef/cef_universe.csv> <out.csv OUTSIDE the repo>

WHY: the desk's own tool for this (scripts/cef/live_attribution.py) takes its keys from the
process environment, which only the VM's report job has. This is a shorter rebuild through
the desk's broker client (GET-only calls: end-of-day equity, FILL activities), with Yahoo's
unadjusted closes and Yahoo's NAV symbols (X<ticker>X). It reconciles its own total to
Alpaca's end-of-day equity change and prints the gap, so its error is on the page: on
2026-11-15 the gap was $10 on a $97 change, and its figures to 2026-10-30 match the tool's
note (results/cef/LIVE_ATTRIBUTION_2026-11-02.md) to the dollar on hold and within 4% on
the NAV part (a different NAV read).
  hold      yesterday's shares x today's change in close
  NAV part  yesterday's shares x yesterday's close x today's NAV return
  discount  hold less the NAV part
  fill      shares traded x (that day's close less the fill price)
The per-session and per-name table goes to the path given, which must be outside the
repository (the per-name live table is not published; team lead's standing rule of
2026-11-02). Regulatory fees and distributions paper does not book are not rebuilt here.
"""
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
if len(sys.argv) != 3:
    raise SystemExit(__doc__)
_out = Path(sys.argv[2]).expanduser().resolve()
if REPO.resolve() == _out or REPO.resolve() in _out.parents:
    raise SystemExit(f"refusing {_out}: the per-name live table stays outside the repository")
from quantt.broker.alpaca import AlpacaClient  # noqa: E402

c = AlpacaClient.from_environment("cef")
S, E = dt.date(2026, 9, 25), dt.date.today() - dt.timedelta(days=1)
eod = pd.Series({p.date: p.equity for p in c.eod_equity_history(S, E)}); eod.index = pd.to_datetime(eod.index)
fills, d = [], S
while d <= E:
    fills += c.activities_fills(d); d += dt.timedelta(days=1)
f = pd.DataFrame(fills)
f["qty"] = f["qty"].astype(float) * np.where(f["side"].str.startswith("sell"), -1, 1)
f["price"] = f["price"].astype(float)
f["date"] = pd.to_datetime(f["transaction_time"]).dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
syms = sorted(f["symbol"].unique())
raw = yf.download(syms, start="2026-09-20", end=(E + dt.timedelta(days=1)).isoformat(), auto_adjust=False, progress=False, threads=False)["Close"]
nav = yf.download([f"X{s}X" for s in syms], start="2026-09-20", end=(E + dt.timedelta(days=1)).isoformat(), auto_adjust=False, progress=False, threads=False)["Close"]
nav.columns = [x[1:-1] for x in nav.columns]
days = eod.index
px = raw.reindex(days); nav = nav.reindex(days)
print("missing closes:", int(px.isna().sum().sum()), " missing NAVs:", nav.isna().sum()[nav.isna().sum() > 0].to_dict())
dq = f.pivot_table(index="date", columns="symbol", values="qty", aggfunc="sum").reindex(days).fillna(0.0)
q = dq.cumsum()
qprev = q.shift(1).fillna(0.0)
hold = qprev * px.diff()
fillpnl = pd.DataFrame(0.0, index=days, columns=syms)
for (dd, s), g in f.groupby(["date", "symbol"]):
    fillpnl.loc[dd, s] = (g["qty"] * (px.loc[dd, s] - g["price"])).sum()
navret = nav.pct_change(fill_method=None)
navpart = qprev * px.shift(1) * navret
disc = hold - navpart
tot = hold.sum(axis=1) + fillpnl.sum(axis=1)
rec = pd.DataFrame({"official": eod.diff(), "rebuilt": tot})
print("official change %.2f  rebuilt %.2f  worst daily gap %.2f" % (eod.iloc[-1] - eod.iloc[0], tot.sum(), (rec.official - rec.rebuilt).abs().max()))
grp = pd.read_csv(sys.argv[1]).set_index("ticker")["grp"]
def tab(mask_days, label):
    h, n, dsc, fl = hold[mask_days], navpart[mask_days], disc[mask_days], fillpnl[mask_days]
    print(f"\n== {label}: hold {h.sum().sum():+.0f}  NAV part {n.sum().sum():+.0f}  discount part {dsc.sum().sum():+.0f}  fill {fl.sum().sum():+.0f}")
    t = pd.DataFrame({"grp": grp.reindex(syms), "hold": h.sum(), "nav": n.sum(), "disc": dsc.sum(), "fill": fl.sum()})
    print(t.groupby("grp").sum().round(0).to_string())
    long = qprev[mask_days] > 0; short = qprev[mask_days] < 0
    for nm, m in (("long", long), ("short", short)):
        print(f"  {nm:5s} hold {h.where(m).sum().sum():+.0f}  NAV {n.where(m).sum().sum():+.0f}  disc {dsc.where(m).sum().sum():+.0f}")
    return t
allm = days >= days[0]
t = tab(allm, f"{days[0].date()}..{days[-1].date()}")
tab(days <= "2026-10-12", "to 10-12"); tab((days > "2026-10-12") & (days <= "2026-10-30"), "10-13..10-30"); tab(days > "2026-10-30", "11-02..11-13")
gross = (q.abs() * px).sum(axis=1); net = (q * px).sum(axis=1)
print("\ngross exposure mean $%.0f, net mean $%.0f, net min/max $%.0f/$%.0f" % (gross[gross > 0].mean(), net[gross > 0].mean(), net.min(), net.max()))
gnet = (q * px).T.groupby(grp.reindex(syms)).sum().T
print("mean net $ by group:\n", gnet[gross > 0].mean().round(0).to_string())
r = eod.pct_change().dropna(); r = r[r.index > "2026-09-28"]
print("\nsessions %d  total %.2f%%  ann vol %.1f%%  Sharpe %.2f  max dd %.2f%%" % (len(r), 100 * (eod.iloc[-1] / eod.iloc[0] - 1), 100 * r.std() * 252 ** .5, r.mean() / r.std() * 252 ** .5, 100 * (eod / eod.cummax() - 1).min()))
print("traded $%.0f, fill bp %.1f" % ((f.qty.abs() * f.price).sum(), 1e4 * fillpnl.sum().sum() / (f.qty.abs() * f.price).sum()))
pd.DataFrame({"eod": eod, "hold": hold.sum(axis=1), "nav": navpart.sum(axis=1), "disc": disc.sum(axis=1), "fill": fillpnl.sum(axis=1), "net_usd": net, "gross_usd": gross}).to_csv(_out)
