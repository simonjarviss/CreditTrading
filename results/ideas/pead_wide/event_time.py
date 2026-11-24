"""Diagnostic for pead_wide: where in event time the drift sits. NOT the pre-specified test.

    python3 results/ideas/pead_wide/event_time.py

Run AFTER the fixed test in explore.py came out weak, to see why. For each release, t is the
session it is known at (explore.known_session). Two sorts, each into tenths within the
calendar quarter of t using only that quarter's releases (a description, not a tradable rule:
the breakpoints use the whole quarter): the IBES surprise score, and the stock's return less
the equal-weighted market over t-1..t (the announcement move). Prints the top-minus-bottom
mean market-adjusted return for sessions t+2..t+k, the earliest a shift(2) book can earn.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts.research import explore as _e  # noqa: F401  (numexpr off)
import explore as px

df = pd.read_parquet(px.PANEL); df["date"] = pd.to_datetime(df["date"])
ret = df.pivot(index="date", columns="permno", values="ret")
rank = df.pivot(index="date", columns="permno", values="cap_rank")
prc = df.pivot(index="date", columns="permno", values="prc")
mkt = ret.where(rank <= px.TRADE_RANK).mean(axis=1)
ab = ret.sub(mkt, axis=0)
ev = pd.read_parquet(px.EVENTS); ev = ev[ev.permno.isin(ret.columns)].copy()
ev["t"] = px.known_session(ev, ret.index); ev = ev.dropna(subset=["t"]).drop_duplicates(["t", "permno"], keep="last")
A = ab.to_numpy(); pos = {d: i for i, d in enumerate(ret.index)}; col = {p: j for j, p in enumerate(ret.columns)}
i = ev.t.map(pos).to_numpy(); j = ev.permno.map(col).to_numpy()
okv = ((rank <= px.TRADE_RANK) & (prc >= px.MIN_PRICE)).to_numpy()[i, j]
K = 62; keep = okv & (i + K < len(A)) & (i >= 1)
ev, i, j = ev[keep].copy(), i[keep], j[keep]
ev["ann_move"] = A[i - 1, j] + A[i, j]
path = np.stack([np.nan_to_num(A[i + k, j]) for k in range(2, K + 1)], axis=1).cumsum(axis=1)
q = ev.t.dt.to_period("Q")
print("releases:", len(ev), "|", ev.t.min().date(), "to", ev.t.max().date())
for name in ("suescore", "ann_move"):
    dec = ev.groupby(q)[name].transform(lambda s: pd.qcut(s.rank(method="first"), 10, labels=False))
    for lab, m in (("all", np.ones(len(ev), bool)), ("2000-2012", (ev.t < "2013-01-01").values), ("2013-2025", (ev.t >= "2013-01-01").values)):
        top, bot = path[(dec == 9).values & m], path[(dec == 0).values & m]
        row = {k: (top[:, k - 2].mean() - bot[:, k - 2].mean()) * 1e4 for k in (2, 3, 6, 11, 21, 41, 61)}
        print(f"{name:9s} {lab:10s} top-bottom bp, t+2..t+k: " + "  ".join(f"k={k}:{v:6.1f}" for k, v in row.items()))

# VARIANT, chosen after seeing the table above (so NOT pre-specified): the same book as
# explore.py, sorted on the announcement move instead of the surprise score. The move over
# t-1..t is known at t's close; the book is decided at t and earns from t+2 (shift(2)).
from scripts.research import harness
S = ev.pivot(index="t", columns="permno", values="ann_move").reindex(index=ret.index, columns=ret.columns)
ok = (rank <= px.TRADE_RANK) & (prc >= px.MIN_PRICE)
R = ret.fillna(0.0)
for hold in (20, 40):
    pnl = harness.evaluate(px.book(S.ffill(limit=hold - 1).where(ok)), R)["pnl"].loc["2000-03-03":]
    line = {lab: _e.stats(p) for lab, p in (("full", pnl), ("to 2012", pnl[:"2012-12-31"]), ("2013 on", pnl["2013-01-01":]), ("2023 on", pnl["2023-01-01":]))}
    print(f"variant ann_move, hold {hold}: " + " | ".join(f"{k} Sharpe {v['sharpe']:.2f} ret/yr {v['ann_ret']:.2%}" for k, v in line.items()))
