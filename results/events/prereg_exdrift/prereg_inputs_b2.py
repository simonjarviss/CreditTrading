"""r8, second helper: added AFTER prereg_inputs.py showed the declared peer basket infeasible.

WHY IT EXISTS
-------------
prereg_inputs.py declared part (b)'s hedge as the equal-weight basket of the other universe
funds with no ex-date at positions [p-2, p+6], minimum 3. On the fit calendar 73.1% of
events have fewer than 3 such funds (median 1): credit-CEF ex-dates cluster (4.08 funds per
distinct ex-date; 88.9% of events share their date with at least 3 funds). That is a fact
about the distribution CALENDAR, not about returns, and it removes most events from the
test. So the draft's declared hedge becomes the named ETF.

DECLARED BEFORE THIS RAN (2026-10-27)
-------------------------------------
* Primary hedge: long HYG $1 for $1 against every short, for the hold rows p+1..p+3.
* Computed here for the HYG version: DISPERSION ONLY (per-event sd, sd of monthly means
  and of monthly sums, by group). No HYG-hedged mean is printed or used. Power uses the
  r6 statistic's mean (CAR -20.454bp, already published) as the assumed effect.
* Also printed: the looser basket rule (no own ex-date in [p-3, p+3]), as a calendar count;
  and r6's own statistic (same-date equal-weight benchmark) split by era and by group,
  which is the published number cut finer. All 2005-2022, descriptive, post-hoc.
* 2023+: dates only (event and month counts reused from prereg_inputs.json).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]  # the repo root (run 2026-10-27 from a scratch export of `simon` at dff4b5c)
sys.path.insert(0, str(TREE))
D = TREE / "data"
FIT_START, FIT_END = pd.Timestamp("2005-01-01"), pd.Timestamp("2022-12-30")
prev = json.loads((HERE / "prereg_inputs.json").read_text())


def say(*a):
    print(*a, flush=True)


def fit_frame(path, cols=None, date_col="date"):
    d = pd.read_parquet(path, columns=cols, filters=[(date_col, "<=", FIT_END)])
    d[date_col] = pd.to_datetime(d[date_col])
    assert d[date_col].max() <= FIT_END
    return d


import scripts.cef.spec as spec                                   # noqa: E402
CORE = list(spec.UNIVERSE)
MUNI = ["MHD", "MQY", "NAD", "NEA", "NVG", "NZF"]
NAMES = CORE + ["NAD", "NEA", "NVG", "NZF"]
px = fit_frame(D / "cef/cef_prices.parquet")
px = px[px.ticker.isin(NAMES)]
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
idx = ret.index
pos = {x: i for i, x in enumerate(idx)}
ab6 = ret.sub(ret.mean(axis=1), axis=0)
hyg = fit_frame(D / "etf_daily.parquet", cols=["date", "ticker", "ret_total"])
hyg = hyg[hyg.ticker == "HYG"].set_index("date").ret_total.reindex(idx)
exd = dist[(dist.amount > 0) & (dist.ex_date >= FIT_START)][["ticker", "ex_date"]]
near = pd.DataFrame(False, index=idx, columns=NAMES)
for _, r in exd.iterrows():
    if r.ex_date in pos:
        near.iloc[pos[r.ex_date], near.columns.get_loc(r.ticker)] = True

rows = []
for _, e in dist[dist.amount > 0].iterrows():
    if e.ex_date not in pos:
        continue
    i = pos[e.ex_date]
    if i < 2 or i + 5 >= len(idx):          # r6's own bounds
        continue
    a = ab6[e.ticker].values[[i + 1, i + 2, i + 3]]
    r3 = ret[e.ticker].values[[i + 1, i + 2, i + 3]]
    h3 = hyg.values[[i + 1, i + 2, i + 3]]
    blk = near.iloc[max(0, i - 3):i + 4]
    nb2 = sum(1 for j in NAMES if j != e.ticker and not blk[j].any())
    rows.append(dict(date=e.ex_date, ticker=e.ticker, car=a.sum() if np.isfinite(a).all() else np.nan,
                     hy=float(-(r3 - h3).sum()) if np.isfinite(r3).all() and np.isfinite(h3).all() else np.nan,
                     nb2=nb2))
ev = pd.DataFrame(rows)
ev = ev[ev.date >= FIT_START]
say(f"looser basket rule (no own ex-date in [p-3, p+3]): median size {ev.nb2.median():.0f}, share < 3 {float((ev.nb2 < 3).mean()):.3f}")


def month_t(g, col):
    m = g.groupby(g.date.dt.to_period("M"))[col].mean()
    return m.mean() / m.std() * np.sqrt(len(m)), len(m)


e6 = ev.dropna(subset=["car"])
assert len(e6) == 3226
say("\nr6's statistic (short P&L = -CAR(+1..+3) vs same-date EW of the 17), cut finer [descriptive]:")
for lab, a, b in (("2005-09", "2005", "2009"), ("2010-14", "2010", "2014"), ("2015-19", "2015", "2019"), ("2020-22", "2020", "2022")):
    g = e6[(e6.date >= a) & (e6.date <= f"{b}-12-31")]
    t, m = month_t(g, "car")
    say(f"   {lab}: events {len(g)}, short P&L {-1e4*g.car.mean():+.1f}bp, month t {-t:+.2f}")
for lab, g in (("taxable 11", e6[~e6.ticker.isin(MUNI)]), ("muni 6", e6[e6.ticker.isin(MUNI)]),
               ("deployed 13", e6[e6.ticker.isin(CORE)])):
    t, m = month_t(g, "car")
    say(f"   {lab}: events {len(g)}, short P&L {-1e4*g.car.mean():+.1f}bp, month t {-t:+.2f}")
ex08 = e6[~((e6.date >= "2008-09-01") & (e6.date <= "2009-06-30")) & ~((e6.date >= "2020-02-20") & (e6.date <= "2020-06-30"))]
t, m = month_t(ex08, "car")
say(f"   without 2008-09-01..2009-06-30 and 2020-02-20..2020-06-30: events {len(ex08)}, short P&L {-1e4*ex08.car.mean():+.1f}bp, month t {-t:+.2f}")

eh = ev.dropna(subset=["hy"])
mm = eh.groupby(eh.date.dt.to_period("M")).hy
sd_mean, sd_sum, n_m = mm.mean().std(), mm.sum().std(), mm.ngroups
say(f"\nHYG $1/$1 (DISPERSION ONLY): events {len(eh)} from {eh.date.min().date()}, months {n_m}; per-event sd "
    f"{1e4*eh.hy.std():.1f}bp; sd of monthly means {1e4*sd_mean:.1f}bp; sd of monthly sums {1e4*sd_sum:.1f}bp; "
    f"taxable sd {1e4*eh[~eh.ticker.isin(MUNI)].hy.std():.1f}bp, muni sd {1e4*eh[eh.ticker.isin(MUNI)].hy.std():.1f}bp; "
    f"r6 benchmark per-event sd on the same events {1e4*eh.car.std():.1f}bp")

from scripts.xasset.slate_feasibility import required_sharpe, power   # noqa: E402
from statistics import NormalDist                                     # noqa: E402
Nd = NormalDist()
Mt, T_test, ev_test = prev["test"]["months"], prev["test"]["sessions"], prev["test"]["events"]
ev13_test = prev["test"]["events_13"]
mu0 = 20.454e-4
epm_fit = len(eh) / n_m
out = {"hyg": dict(events=len(eh), months=n_m, sd_bp=1e4 * eh.hy.std(), sd_month_mean_bp=1e4 * sd_mean,
                   sd_month_sum_bp=1e4 * sd_sum, events_per_month=epm_fit)}
say(f"\nPOWER, HYG hedge, test set ({ev_test} events in {Mt} months, all 17; {ev13_test} on the 13):")
for frac in (1.0, 0.5, 0.25):
    mu = frac * mu0
    for lab, nev in (("17", ev_test), ("13", ev13_test)):
        # sd of a month's mean shrinks with events per month as the fit's did: scale by sqrt(fit epm / test epm)
        se = sd_mean * np.sqrt(epm_fit / (nev / Mt)) / np.sqrt(Mt)
        et = mu / se
        out.setdefault("power_event", {})[f"{lab}_{frac}"] = dict(mu_bp=1e4 * mu, exp_t=et, p_t2=1 - Nd.cdf(2 - et))
        say(f"   names {lab}, true mean {1e4*mu:4.1f}bp: expected month-clustered t {et:.2f}; P(t >= 2) {1-Nd.cdf(2-et):.2f}")
    # sleeve Sharpe, [U] arithmetic: monthly sum mean = mu * events per month; sd of monthly sums from the fit
    sr = (mu * epm_fit) / sd_sum * np.sqrt(12)
    out.setdefault("sleeve", {})[frac] = dict(sr=sr, **{f"p_N{N}": power(sr, N, T_test) for N in (6, 7, 8)})
    say(f"   sleeve SR [U arithmetic] {sr:.2f}: P(_dsr pass) N6 {power(sr, 6, T_test):.3f}, N7 {power(sr, 7, T_test):.3f}, N8 {power(sr, 8, T_test):.3f}")
for N in (6, 7, 8):
    say(f"   Sharpe needed at N {N}, T {T_test}: {required_sharpe(N, T_test):.3f}")
for mths in (12, 24):
    se = sd_mean * np.sqrt(epm_fit / (ev13_test / Mt)) / np.sqrt(mths)
    et = mu0 / se
    out.setdefault("forward_13", {})[mths] = dict(exp_t=et, p_t2=1 - Nd.cdf(2 - et), p_t2_half=1 - Nd.cdf(2 - et / 2))
    say(f"FORWARD paper, 13 names, {mths} months: expected t {et:.2f}, P(t >= 2) {1-Nd.cdf(2-et):.2f} (half effect {1-Nd.cdf(2-et/2):.2f})")
for mths in (12, 24):
    se = sd_mean * np.sqrt(epm_fit / (ev13_test / Mt)) / np.sqrt(Mt + mths)
    et = mu0 / se
    out.setdefault("pooled_13", {})[mths] = dict(exp_t=et, p_t2=1 - Nd.cdf(2 - et))
    say(f"TEST + {mths} forward months, 13 names: expected t {et:.2f}, P(t >= 2) {1-Nd.cdf(2-et):.2f}")
(HERE / "prereg_inputs_b2.json").write_text(json.dumps(out, indent=1, default=str))
