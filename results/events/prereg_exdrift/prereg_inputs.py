"""r8: inputs for the ex-date drift pre-registration DRAFT (zero trials; no counter moves).

WHAT THIS MAY READ, AND WHAT IT MAY NOT
---------------------------------------
* Fit window, 2005-01-03 .. 2022-12-30: prices, NAVs, distributions and HYG returns, read
  with parquet filters `<= 2022-12-30`, so no later row is ever loaded. Every frame is
  asserted to end on or before FIT_END. These are DESCRIPTIVE: the effect was found after
  the fit was seen (results/cef/screens_2026-10-26/), so nothing here is evidence.
* 2023-01-01 onward: ONLY DATES. The `ticker, ex_date` columns of the distribution panel
  (no amount) and the `date, ticker` columns of the price panel (no price, no volume), to
  count events, sessions and basket sizes for the power figure. No 2023+ price, NAV,
  amount, return or fee is read.
* data/ is read through SCRATCH/tree/data (a symlink), never written. Cut copies of the
  fit panels go to this folder's _cache_panels/ (gitignored).

DECLARED BEFORE ANY RESULT WAS COMPUTED (2026-10-27)
----------------------------------------------------
* Part (b)'s hedge is the equal-weight basket of the OTHER universe funds that have no
  ex-date at session positions [p-2, p+6] (p = the event's ex-session), fixed for the hold
  (return rows p+1..p+3), with a valid return on all three rows; at least 3 funds, else
  the event is not traded (r3's peer rule). With that window no basket fund's own
  [-3, +3] ex-window touches any hold return row.
* The ETF alternative (HYG, $1 for $1; MUB is not in data/etf_daily.parquet) is computed
  for DISPERSION only. Its mean is not printed: the choice is made on a priori grounds
  and on dispersion, never on a mean.
* Part (a)'s deferral window is decision offsets j = d - e in [-2, +1], derived in the
  draft (section 3.1) from the record-date rule and shift(2), not from this output. The
  profile below is printed to CHECK it, and the draft says that it was seen.

Run: python3 -I -B prereg_inputs.py   (from anywhere; paths are absolute to this folder)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parent
TREE = HERE.parents[2]                      # the repo root (run 2026-10-27 from a scratch export of `simon` at dff4b5c)
sys.path.insert(0, str(TREE))
D = TREE / "data"
PANELS = HERE / "_cache_panels"
PANELS.mkdir(exist_ok=True)
FIT_START, FIT_END = pd.Timestamp("2005-01-01"), pd.Timestamp("2022-12-30")
TEST_START = pd.Timestamp("2023-01-01")
OUT = {}


def say(*a):
    print(*a, flush=True)


def fit_frame(path, cols=None, date_col="date"):
    """Read a panel with a parquet filter at FIT_END (no later row is loaded) and assert it."""
    d = pd.read_parquet(path, columns=cols, filters=[(date_col, "<=", FIT_END)])
    d[date_col] = pd.to_datetime(d[date_col])
    assert d[date_col].max() <= FIT_END, f"{path}: a row after {FIT_END.date()} got through"
    return d


import scripts.cef.spec as spec                      # noqa: E402  (the only reader of the frozen spec)
CORE = list(spec.UNIVERSE)
NAMES = CORE + ["NAD", "NEA", "NVG", "NZF"]
assert len(NAMES) == 17 and len(set(NAMES)) == 17
say(f"spec {spec.SPEC_ID}; deployed {len(CORE)}: {CORE}; +4 munis -> 17")

# ---------------------------------------------------------------- fit panels (cut copies)
px_all = fit_frame(D / "cef/cef_prices.parquet")
nav_all = fit_frame(D / "cef/cef_nav.parquet")
px_all.to_parquet(PANELS / "core_prices_fit.parquet")
nav_all.to_parquet(PANELS / "core_nav_fit.parquet")
px = px_all[px_all.ticker.isin(NAMES)]
assert px.ticker.nunique() == 17
close = px.pivot(index="date", columns="ticker", values="close").sort_index()
dist = fit_frame(D / "cef/cef_distributions.parquet", date_col="ex_date")
dist = dist[dist.ticker.isin(NAMES)]
div = (dist[dist.amount > 0].pivot_table(index="ex_date", columns="ticker", values="amount", aggfunc="sum")
       .reindex(close.index).reindex(columns=close.columns).fillna(0.0))  # absent row = no distribution that day
ret = (close + div) / close.shift(1) - 1.0
bad = pd.DataFrame(False, index=ret.index, columns=ret.columns)
for _, r in dist[dist.stock_split > 0].iterrows():
    i = ret.index.searchsorted(r.ex_date)
    bad.iloc[max(0, i - 5):i + 6, bad.columns.get_loc(r.ticker)] = True
ret = ret.mask(bad | (ret.abs() > 0.30))
assert ret.index.max() <= FIT_END
idx = ret.index
pos = {x: i for i, x in enumerate(idx)}
grp = px.drop_duplicates("ticker").set_index("ticker").grp

# ---------------------------------------------------------------- identity gate: r6 check_credit.py
ab6 = ret.sub(ret.mean(axis=1), axis=0)
rows = []
for _, e in dist[dist.amount > 0].iterrows():
    if e.ex_date not in pos:
        continue
    i = pos[e.ex_date]
    if i < 6 or i + 6 >= len(idx):
        continue
    rec = {"date": e.ex_date, "ticker": e.ticker, "p": i, "amount": e.amount,
           "yld": e.amount / close[e.ticker].iloc[i - 1]}
    for k in range(-5, 7):
        rec[k] = ab6[e.ticker].values[i + k]
    rows.append(rec)
ev = pd.DataFrame(rows)
ev6 = ev.dropna(subset=[1, 2, 3])
ev6 = ev6[ev6.date >= FIT_START].copy()
ev6["car13"] = ev6[[1, 2, 3]].sum(axis=1)


def month_t(g, col):
    m = g.groupby(g.date.dt.to_period("M"))[col].mean()
    return m.mean() / m.std() * np.sqrt(len(m)), len(m), m.std()


def date_t(g, col):
    m = g.groupby("date")[col].mean()
    return m.mean() / m.std() * np.sqrt(len(m)), len(m)


t6, M6, _ = month_t(ev6, "car13")
say(f"\nGATE (r6 check_credit.py): events {len(ev6)}, CAR(+1..+3) {1e4*ev6.car13.mean():+.3f}bp, month t {t6:+.3f}")
assert len(ev6) == 3226 and abs(1e4 * ev6.car13.mean() + 20.454) < 0.001 and abs(t6 + 6.765) < 0.001, "r6 not reproduced"
say("GATE PASS: reproduces r6 (3,226 events, -20.454bp, t -6.765)")
OUT["gate"] = dict(events=len(ev6), car_bp=1e4 * ev6.car13.mean(), t_month=t6)

# ---------------------------------------------------------------- profile -5..+6 (r6 benchmark), descriptive
prof = {}
for lab, g in (("17", ev6), ("deployed 13", ev6[ev6.ticker.isin(CORE)]), ("4 munis", ev6[~ev6.ticker.isin(CORE)])):
    p_ = {k: 1e4 * g[k].mean() for k in range(-5, 7)}
    se = {k: 1e4 * g[k].std() / np.sqrt(g[k].notna().sum()) for k in range(-5, 7)}
    prof[lab] = p_
    say(f"profile {lab:>11} (n {len(g)}): " + " ".join(f"{k:+d}:{p_[k]:+.1f}({se[k]:.1f})" for k in range(-5, 7)))
OUT["profile_bp"] = prof
# cumulative abnormal a buy decided at offset j earns through return row +3 (fill at e+j+1, first row e+j+2)
p17 = prof["17"]
cum = {j: sum(p17[k] for k in range(j + 2, 4)) for j in range(-7, 2)}
say("cum abnormal (bp) a buy decided at offset j earns over rows j+2..+3, 17 names: "
    + " ".join(f"j{j:+d}:{v:+.1f}" for j, v in cum.items() if j >= -7))
OUT["cum_from_decision_bp"] = cum

# ---------------------------------------------------------------- clustering of ex-dates
exd = dist[(dist.amount > 0) & (dist.ex_date >= FIT_START)][["ticker", "ex_date"]]
per_date = exd.groupby("ex_date").ticker.nunique()
say(f"\nfit ex-dates, 17 names, 2005-22: {len(exd)} fund-ex-dates on {len(per_date)} distinct dates; "
    f"funds per date mean {per_date.mean():.2f}, median {per_date.median():.0f}, max {per_date.max()}; "
    f"share of events on a date shared with >=3 funds {float((exd.ex_date.map(per_date) >= 3).mean()):.3f}")
OUT["fit_clustering"] = dict(fund_ex=len(exd), dates=len(per_date), mean_per_date=per_date.mean(),
                             share_shared3=float((exd.ex_date.map(per_date) >= 3).mean()))
# same fund, next ex-date inside (p, p+3]: the short would cross a record date
nxt = 0
for t, g in exd.groupby("ticker"):
    q = sorted(pos[x] for x in g.ex_date if x in pos)
    nxt += sum(1 for a, b in zip(q, q[1:]) if b - a <= 3)
say(f"fund-events whose next own ex-date is within 3 sessions (fit): {nxt}")
OUT["next_ex_within3_fit"] = nxt

# ---------------------------------------------------------------- the declared hedge (b), fit, descriptive
expos = {t: np.array(sorted(pos[x] for x in exd.ex_date[exd.ticker == t] if x in pos)) for t in NAMES}
near = pd.DataFrame(False, index=idx, columns=NAMES)          # True at row q if the fund has an ex-date at q
for t in NAMES:
    near.iloc[expos[t], near.columns.get_loc(t)] = True
R = ret[NAMES]
hyg = fit_frame(D / "etf_daily.parquet", cols=["date", "ticker", "ret_total"])
hyg = hyg[hyg.ticker == "HYG"].set_index("date").ret_total.reindex(idx)

recs = []
for _, e in ev6.iterrows():
    i, t = int(e.p), e.ticker
    rows3 = [i + 1, i + 2, i + 3]
    ri = R[t].values[rows3]
    if not np.isfinite(ri).all():
        continue
    blk = near.iloc[i - 2:i + 7]                                # positions p-2 .. p+6
    cand = [j for j in NAMES if j != t and not blk[j].any() and np.isfinite(R[j].values[rows3]).all()]
    nb = len(cand)
    bm = R[cand].values[rows3].mean(axis=1) if nb else np.full(3, np.nan)
    # NAV leg (control): NAV total return of the fund and of the same basket over the same rows
    recs.append(dict(date=e.date, ticker=t, p=i, nb=nb, yld=e.yld,
                     pnl=float(-(ri - bm).sum()) if nb >= 3 else np.nan,
                     pnl_hyg=float(-(ri - hyg.values[rows3]).sum()) if np.isfinite(hyg.values[rows3]).all() else np.nan,
                     basket=",".join(cand)))
E = pd.DataFrame(recs)
say(f"\n(b) declared hedge, fit 2005-22: events with a fund return {len(E)}; basket size median {E.nb.median():.0f}, "
    f"p10 {E.nb.quantile(.1):.0f}, share < 3 (not traded) {float((E.nb < 3).mean()):.3f}")
Eb = E[E.nb >= 3].copy()
tb, Mb, sdm = month_t(Eb, "pnl")
tdte, nd = date_t(Eb, "pnl")
say(f"(b) traded events {len(Eb)} on {Eb.date.nunique()} dates, {Mb} months: mean {1e4*Eb.pnl.mean():+.2f}bp "
    f"[descriptive, post-hoc], per-event sd {1e4*Eb.pnl.std():.1f}bp, month-clustered t {tb:+.2f}, "
    f"date-clustered t {tdte:+.2f}; sd of monthly means {1e4*sdm:.1f}bp; share > 0 {float((Eb.pnl>0).mean()):.3f}")
Eh = E.dropna(subset=["pnl_hyg"])
say(f"(b) ETF alternative (HYG $1/$1), dispersion only: events {len(Eh)}, per-event sd {1e4*Eh.pnl_hyg.std():.1f}bp "
    f"(declared basket {1e4*Eb.pnl.std():.1f}bp on its own events)")
for lab, g in (("deployed 13", Eb[Eb.ticker.isin(CORE)]), ("4 munis", Eb[~Eb.ticker.isin(CORE)])):
    tt, mm, _ = month_t(g, "pnl")
    say(f"   {lab}: events {len(g)}, mean {1e4*g.pnl.mean():+.2f}bp, sd {1e4*g.pnl.std():.1f}bp, month t {tt:+.2f}")
eras = [("2005-09", "2005", "2009"), ("2010-14", "2010", "2014"), ("2015-19", "2015", "2019"), ("2020-22", "2020", "2022")]
for lab, a, b in eras:
    g = Eb[(Eb.date >= a) & (Eb.date <= f"{b}-12-31")]
    tt, mm, _ = month_t(g, "pnl")
    say(f"   era {lab}: events {len(g)}, mean {1e4*g.pnl.mean():+.2f}bp, month t {tt:+.2f}")
OUT["b_fit"] = dict(events=len(Eb), dates=int(Eb.date.nunique()), months=Mb, mean_bp=1e4 * Eb.pnl.mean(),
                    sd_bp=1e4 * Eb.pnl.std(), t_month=tb, t_date=tdte, sd_month_mean_bp=1e4 * sdm,
                    share_lt3=float((E.nb < 3).mean()), sd_hyg_bp=1e4 * Eh.pnl_hyg.std(),
                    events_per_year=len(Eb) / 18.0)

# ---------------------------------------------------------------- the NAV leg (control), fit, descriptive
navp = nav_all[nav_all.ticker.isin(NAMES)].pivot(index="date", columns="ticker", values="nav").reindex(idx)
rN = (navp + div) / navp.shift(1) - 1.0                        # NAV total return (NAV drops by D on the ex-date)
rN = rN.mask(bad | (rN.abs() > 0.30))
nrec = []
for _, e in Eb.iterrows():
    i, t = int(e.p), e.ticker
    rows3 = [i + 1, i + 2, i + 3]
    cand = e.basket.split(",")
    a = rN[t].values[rows3]
    b = rN[cand].values[rows3]
    if not np.isfinite(a).all() or np.isfinite(b).sum(axis=1).min() < 3:
        continue
    nrec.append(dict(date=e.date, nav_pnl=float(-(a - np.nanmean(b, axis=1)).sum())))
NV = pd.DataFrame(nrec)
tn, Mn, _ = month_t(NV, "nav_pnl")
say(f"NAV leg, same events/basket (control; descriptive): events {len(NV)}, mean {1e4*NV.nav_pnl.mean():+.2f}bp, month t {tn:+.2f}")
OUT["nav_leg_fit"] = dict(events=len(NV), mean_bp=1e4 * NV.nav_pnl.mean(), t_month=tn)

# ---------------------------------------------------------------- the raw sleeve (b) through evaluate(), descriptive
from scripts.cef.band_frontier import evaluate           # noqa: E402  (the canonical shift(2) harness)
Hb = pd.DataFrame(0.0, index=idx, columns=NAMES)
for _, e in Eb.iterrows():
    i, t = int(e.p), e.ticker
    cand = e.basket.split(",")
    for d_ in (i - 1, i, i + 1):                           # decide e-1 -> fill close e -> earn e+1..e+3
        Hb.iloc[d_, Hb.columns.get_loc(t)] -= 1.0
        for j in cand:
            Hb.iloc[d_, Hb.columns.get_loc(j)] += 1.0 / len(cand)
held = Hb.shift(2).fillna(0.0)
assert np.isfinite(R.values[held.values != 0]).all(), "a held cell has no return: evaluate() would book it as 0"
res = evaluate(Hb, R.fillna(0.0))
pnl = res["pnl"]
first = pnl.ne(0).idxmax()
pf = pnl.loc[first:FIT_END]
check = sum(Eb.pnl)
assert abs(pf.sum() - check) < 1e-9, (pf.sum(), check)
active = held.abs().sum(axis=1).loc[first:FIT_END] > 0
sr = pf.mean() / pf.std() * np.sqrt(252)
say(f"(b) raw sleeve, $1 short + $1 basket per event, evaluate(): sessions {len(pf)} from {first.date()}, "
    f"gross SR {sr:.3f} [descriptive], ann {pf.mean()*252*100:+.2f}% per unit, active share {active.mean():.3f}, "
    f"turnover {res['turn']:.1f}/yr; per-event sum check passes")
sig_act = pf[active].std() * np.sqrt(252)
OUT["b_sleeve_fit"] = dict(T=len(pf), first=str(first.date()), sr=sr, sigma_active=sig_act,
                           active_share=float(active.mean()), turn=res["turn"],
                           k_scale=spec.VOL_TARGET / sig_act, by_era={})
for lab, a, b in eras:
    s = pf.loc[a:f"{b}-12-31"]
    OUT["b_sleeve_fit"]["by_era"][lab] = s.mean() / s.std() * np.sqrt(252)
say("   by era SR: " + ", ".join(f"{k} {v:.2f}" for k, v in OUT["b_sleeve_fit"]["by_era"].items())
    + f"; k = vol_target {spec.VOL_TARGET} / sigma_active {sig_act:.4f} = {spec.VOL_TARGET/sig_act:.2f}")

# ---------------------------------------------------------------- part (a): band buys in the deferral window (fit)
import scripts.cef.band_frontier as bf                    # noqa: E402
T, R0 = bf.build_targets(source=(PANELS / "core_prices_fit.parquet", PANELS / "core_nav_fit.parquet"))
assert T.index.max() <= FIT_END
Hd = bf.band_gross_capped(T, spec.BAND_WIDTH, spec.MAX_GROSS_STRESS if spec.MAX_GROSS_STRESS else np.inf)
dH = Hd.diff().fillna(Hd)
first_a = Hd.abs().sum(axis=1).ne(0).idxmax()
sl = slice(first_a, FIT_END)
ip = {x: i for i, x in enumerate(Hd.index)}
win = pd.DataFrame(np.nan, index=Hd.index, columns=Hd.columns)   # decision offset j to the nearest ex-date in [-2,+1]
for t in CORE:
    for x in exd.ex_date[exd.ticker == t]:
        if x not in ip:
            continue
        q = ip[x]
        for j in (-2, -1, 0, 1):
            if 0 <= q + j < len(Hd):
                win.iloc[q + j, Hd.columns.get_loc(t)] = j
buys = dH.clip(lower=0).loc[sl]
sells = (-dH).clip(lower=0).loc[sl]
inw = win.loc[sl].notna()
yrs = len(buys) / 252
tot_buy, in_buy = buys.to_numpy().sum(), buys.where(inw, 0).to_numpy().sum()
n_buy_in = int(((buys > 0) & inw).to_numpy().sum())
say(f"\n(a) live policy {spec.LIVE_POLICY} on the deployed 13, fit {first_a.date()}..{FIT_END.date()} ({yrs:.1f} yrs): "
    f"turnover {(buys+sells).to_numpy().sum()/yrs:.2f}/yr; buys in window [-2,+1]: {n_buy_in} "
    f"({n_buy_in/yrs:.1f}/yr), {in_buy/yrs:.3f} of capital/yr = {in_buy/tot_buy:.3f} of buy turnover; "
    f"window holds {float(inw.where(Hd.loc[sl].abs()>0, False).to_numpy().sum()/ (Hd.loc[sl].abs()>0).to_numpy().sum()):.3f} of held name-days")
# power arithmetic for (a): E[gain] = sum_b x_b * (-Abar_j); Var = sum_b x_b^2 * Var(A_j), A_j over all 13-name fit events
ev13 = ev6[ev6.ticker.isin(CORE)]
Aj = {j: ev13[[k for k in range(j + 2, 4)]].sum(axis=1, min_count=1) for j in (-2, -1, 0, 1)}
mean_j = {j: float(Aj[j].mean()) for j in Aj}
var_j = {j: float(Aj[j].var()) for j in Aj}
xb = buys.where(inw, 0)
jj = win.loc[sl]
eg = sum(float((xb.where(jj == j, 0)).to_numpy().sum()) * -mean_j[j] for j in Aj)
vg = sum(float((xb.where(jj == j, 0) ** 2).to_numpy().sum()) * var_j[j] for j in Aj)
say("(a) A_j = abnormal return a buy decided at j earns through +3, 13-name fit events (bp): "
    + " ".join(f"j{j:+d}:{1e4*mean_j[j]:+.1f} (sd {1e4*np.sqrt(var_j[j]):.0f})" for j in Aj))
ann_mu, ann_sd = eg / yrs, np.sqrt(vg / yrs)
say(f"(a) first-order gain if every in-window buy were moved past +3 [U arithmetic]: {1e4*ann_mu:+.2f}bp/yr of capital, "
    f"sd {1e4*ann_sd:.2f}bp/yr, 'Sharpe' {ann_mu/ann_sd:.2f}")
OUT["a_fit"] = dict(first=str(first_a.date()), years=yrs, n_buys_in=n_buy_in, buys_in_per_yr=n_buy_in / yrs,
                    buy_turn_in_per_yr=in_buy / yrs, share_buy_turn=in_buy / tot_buy,
                    turnover=(buys + sells).to_numpy().sum() / yrs, gain_bp_yr=1e4 * ann_mu,
                    gain_sd_bp_yr=1e4 * ann_sd, gain_sr=ann_mu / ann_sd,
                    A_mean_bp={j: 1e4 * mean_j[j] for j in Aj})

# ---------------------------------------------------------------- 2023+: DATES ONLY
dts = pd.read_parquet(D / "cef/cef_prices.parquet", columns=["date", "ticker"],
                      filters=[("date", ">=", TEST_START)])
dts = dts[dts.ticker.isin(NAMES)]
sess = pd.DatetimeIndex(sorted(pd.to_datetime(dts.date).unique()))
last_px = {t: pd.Timestamp(g.max()).date() for t, g in dts.groupby("ticker").date}
xd = pd.read_parquet(D / "cef/cef_distributions.parquet", columns=["ticker", "ex_date"],
                     filters=[("ex_date", ">=", TEST_START)])
xd["ex_date"] = pd.to_datetime(xd.ex_date)
xd = xd[xd.ticker.isin(NAMES)].drop_duplicates()
last_dist = xd.ex_date.max()
spos = {x: i for i, x in enumerate(sess)}
miss = xd[~xd.ex_date.isin(spos)]
xd = xd[xd.ex_date.isin(spos)].copy()
xd["p"] = xd.ex_date.map(spos)
xd = xd[xd.p + 3 < len(sess)]
nearT = pd.DataFrame(False, index=range(len(sess)), columns=NAMES)
for _, r in xd.iterrows():
    nearT.loc[r.p, r.ticker] = True
nbT = []
for _, r in xd.iterrows():
    lo, hi = max(0, r.p - 2), min(len(sess) - 1, r.p + 6)
    nbT.append(sum(1 for j in NAMES if j != r.ticker and not nearT.loc[lo:hi, j].any()))
xd["nb"] = nbT
nxtT = 0
for t, g in xd.groupby("ticker"):
    q = sorted(g.p)
    nxtT += sum(1 for a, b in zip(q, q[1:]) if b - a <= 3)
T_test = int(((sess >= TEST_START)).sum())
months = xd.ex_date.dt.to_period("M").nunique()
tr = xd[xd.nb >= 3]
say(f"\nTEST SET (dates only): sessions {sess[0].date()}..{sess[-1].date()} = {T_test}; distribution panel last ex-date "
    f"{last_dist.date()}; ex-dates of the 17 with a hold inside the price panel {len(xd)} "
    f"({xd.ticker.isin(CORE).sum()} on the deployed 13) on {xd.ex_date.nunique()} dates in {months} months; "
    f"not a session {len(miss)}; basket >= 3 by calendar {len(tr)} ({tr.ticker.isin(CORE).sum()} on the 13); "
    f"next own ex within 3 sessions {nxtT}")
say(f"   last price date by name: {sorted(set(last_px.values()))}")
yr_counts = xd.groupby(xd.ex_date.dt.year).size().to_dict()
say(f"   events by year: {yr_counts}")
t1 = xd[xd.ex_date >= "2024-05-28"]
say(f"   settlement regime: T+2 (ex <= 2024-05-27) {int((xd.ex_date < '2024-05-28').sum())}, T+1 {len(t1)}")
OUT["test"] = dict(sessions=T_test, first=str(sess[0].date()), last=str(sess[-1].date()),
                   last_dist=str(last_dist.date()), events=len(xd), events_13=int(xd.ticker.isin(CORE).sum()),
                   dates=int(xd.ex_date.nunique()), months=int(months), traded_calendar=len(tr),
                   traded_calendar_13=int(tr.ticker.isin(CORE).sum()), next_within3=nxtT,
                   T2=int((xd.ex_date < "2024-05-28").sum()), T1=len(t1), by_year=yr_counts,
                   not_session=len(miss))

# ---------------------------------------------------------------- power
from scripts.xasset.slate_feasibility import required_sharpe, power   # noqa: E402  (they invert validate._dsr)
from statistics import NormalDist                                     # noqa: E402
Nd = NormalDist()
bfit = OUT["b_fit"]
Mt = OUT["test"]["months"]
se_test = bfit["sd_month_mean_bp"] / np.sqrt(Mt)
scale_ev = np.sqrt(len(tr) / Mt / (bfit["events"] / bfit["months"]))   # events per month, test vs fit
say(f"\nPOWER (b), per-event, month-clustered: fit sd of monthly means {bfit['sd_month_mean_bp']:.1f}bp "
    f"(fit {bfit['events']/bfit['months']:.1f} events/month; test {len(tr)/Mt:.1f}); test months {Mt}")
pw = {}
for frac in (1.0, 0.5, 0.25):
    mu = frac * abs(bfit["mean_bp"])
    et = mu / se_test
    pw[frac] = dict(mu=mu, exp_t=et, p_t2=1 - Nd.cdf(2.0 - et), p_t1645=1 - Nd.cdf(1.645 - et))
    say(f"   true mean {mu:5.1f}bp ({frac:.2f} x fit): expected t {et:.2f}; P(t >= 2.0) {pw[frac]['p_t2']:.2f}; "
        f"P(t >= 1.645) {pw[frac]['p_t1645']:.2f}")
OUT["power_b_event"] = pw
srb = OUT["b_sleeve_fit"]["sr"]
OUT["power_b_sleeve"] = {}
for N in (6, 7, 8):
    req = required_sharpe(N, T_test)
    OUT["power_b_sleeve"][N] = dict(req=req, **{f"p_at_{f}": power(f * srb, N, T_test) for f in (1.0, 0.5, 0.25)})
    say(f"   sleeve bar at N {N}, T {T_test}: Sharpe needed {req:.3f}; P(pass) at fit SR {srb:.2f} "
        f"{power(srb, N, T_test):.2f}, at half {power(0.5*srb, N, T_test):.2f}, at a quarter {power(0.25*srb, N, T_test):.2f}")
for N in (53,):
    req = required_sharpe(N, T_test)
    say(f"   (CEF bar) N {N}: Sharpe needed {req:.3f}")
sra = OUT["a_fit"]["gain_sr"]
OUT["power_a"] = {}
for N in (6, 7, 8, 53):
    req = required_sharpe(N, T_test)
    OUT["power_a"][N] = dict(req=req, p=power(sra, N, T_test))
    say(f"POWER (a) gain series: N {N} needs {req:.3f}; P(pass) at the arithmetic SR {sra:.2f}: {power(sra, N, T_test):.3f}")
ta = sra * np.sqrt(T_test / 252)
say(f"POWER (a): expected t of the gain over the test {ta:.2f}; P(t >= 2) {1 - Nd.cdf(2 - ta):.2f}")
OUT["power_a_t"] = dict(exp_t=ta, p_t2=1 - Nd.cdf(2 - ta))
# forward paper: shortable-today names only is a live question; use the 13 at the fit rate per month
fw = {}
for mths in (12, 24):
    se_f = bfit["sd_month_mean_bp"] / np.sqrt(mths)
    et = abs(bfit["mean_bp"]) / se_f
    fw[mths] = dict(exp_t=et, p_t2=1 - Nd.cdf(2 - et), p_t2_half=1 - Nd.cdf(2 - et / 2),
                    req6=required_sharpe(6, 21 * mths), p6=power(srb, 6, 21 * mths), p6_half=power(srb / 2, 6, 21 * mths))
    say(f"FORWARD paper {mths} months: expected per-event t {et:.2f}, P(t >= 2) {fw[mths]['p_t2']:.2f} "
        f"(half effect {fw[mths]['p_t2_half']:.2f}); sleeve bar N 6 needs {fw[mths]['req6']:.2f}, "
        f"P(pass) {fw[mths]['p6']:.2f} (half {fw[mths]['p6_half']:.2f})")
OUT["forward"] = fw

(HERE / "prereg_inputs.json").write_text(json.dumps(OUT, indent=1, default=str))
say(f"\nwrote {HERE/'prereg_inputs.json'}")
