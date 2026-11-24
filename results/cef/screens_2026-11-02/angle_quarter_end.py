"""Angle F: quarter-end 'leaning for the tape' in CEF closing prices. Zero trials; fit data only.

MECHANISM. Managers judged on quarter-end marks buy their illiquid holdings into the last close
of the quarter and the price gives it back the next session (Carhart, Kaniel, Musto & Reed 2002,
'Leaning for the tape' [U: recalled, not fetched; cite only after a fetch]). CEFs are small and
illiquid, and specialist funds-of-CEFs hold concentrated stakes (RiverNorth holds 11 of our 13,
Karpus 11.03% of MHD: SCALING_RESEARCH_2026-10-08.md section 7.3 [S]). If the CEF's closing
PRICE is pushed up while its NAV is not, the discount narrows at the quarter-end close and widens
back the next session. Who loses: the marking manager's investors (they buy at the pushed close).
Who gains: whoever sells into that close and buys back after -- a calendar trade that MOC can
express (decide days ahead, fill at the quarter-end close, reverse at the next close).
Why the z-score cannot see it: it is a dated one-session price distortion; the band decides on
it at t and fills at t+1, after the reversal, so at best it is a noise trade.

MEASURE. Per name-day, the discount leg x = r_price - r_NAV (bp), on the 17 credit CEFs
(data/cef) and C4's 74 frozen funds (data/cef_families), 2005-01-03 -> 2022-12-30. Day types:
the last NYSE session of Mar/Jun/Sep (QE), of December (YE, reported apart: it carries the
tax-loss season, which is alpha-finder's lane), of the other 8 months (ME), and the first session
after each. Statistic: the date's equal-weight mean x, minus the mean over 'other' days, with t
across dates (dates are the clusters). Name-days in [ex-1, ex+3] are excluded (ex-date mechanics
and the post-ex drift), as are |r| >= 0.5 and |x| > 0.2 (split-basis mismatches), all counted.
NEGATIVE CONTROLS (named first): (1) AP-arbitraged ETFs' premium change (HYG, LQD, IEF, TLT,
SHY: data/etf_daily.parquet prices x data/holdings/ishares_nav_daily.parquet NAVs) on the same
day types, where no pumping can persist; (2) the gradient: the effect must be larger in the
least liquid tercile (trailing 63-session $ADV, known at t-1) than in the most liquid.

Run from the repo root:  python3 -B results/cef/screens_2026-11-02/angle_quarter_end.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import angle_common as c                                         # noqa: E402

CREDIT17 = list(c.UNIVERSE) + ["NAD", "NEA", "NVG", "NZF"]
C4_FROZEN = c.REPO / "results" / "cef" / "c4" / "c4_universe_frozen_2026-10-14.csv"
START = pd.Timestamp("2005-01-03")


def load(prices, navs, names):
    P = pd.read_parquet(prices); N = pd.read_parquet(navs)
    P["date"] = pd.to_datetime(P["date"]); N["date"] = pd.to_datetime(N["date"])
    P = P[P.ticker.isin(names) & (P.date <= c.FIT_END) & (P.date >= START - pd.Timedelta(days=120))]
    N = N[N.ticker.isin(names) & (N.date <= c.FIT_END) & (N.date >= START - pd.Timedelta(days=120))]
    c.assert_fit(P, "prices"); c.assert_fit(N, "nav")
    px = P.pivot_table(index="date", columns="ticker", values="close").sort_index()
    vol = P.pivot_table(index="date", columns="ticker", values="volume").sort_index()
    nav = N.pivot_table(index="date", columns="ticker", values="nav").reindex(px.index)
    return px, nav, vol


def day_types(idx):
    s = pd.Series(idx, index=idx)
    last = s.groupby([idx.year, idx.month]).transform("max") == s
    t = pd.Series("other", index=idx)
    for d in idx[last.values]:
        t[d] = "YE" if d.month == 12 else ("QE" if d.month in (3, 6, 9) else "ME")
    nxt = t.shift(1)
    for lab in ("QE", "YE", "ME"):
        t[(nxt == lab).values & (t == "other").values] = lab + "+1"
    return t


def ex_mask(px, ex):
    """True on name-days in [ex-1, ex+3] sessions."""
    m = pd.DataFrame(False, index=px.index, columns=px.columns)
    idx = px.index
    for tk, g in ex.groupby("ticker"):
        if tk not in m.columns:
            continue
        for d in g["ex_date"]:
            i = idx.searchsorted(d)
            if i >= len(idx):
                continue
            m.iloc[max(i - 1, 0):min(i + 4, len(idx)), m.columns.get_loc(tk)] = True
    return m


def leg(px, nav, vol, ex):
    rp = px.pct_change(fill_method=None)
    rn = nav.pct_change(fill_method=None)
    x = (rp - rn)
    bad = (rp.abs() >= 0.5) | (rn.abs() >= 0.5) | (x.abs() > 0.2)
    exm = ex_mask(px, ex)
    n_total = int(x.notna().sum().sum())
    x = x.mask(bad).mask(exm)
    adv = (px * vol).rolling(63, min_periods=21).mean().shift(1)     # known at t-1
    x, adv = x.loc[START:], adv.loc[START:]
    return 1e4 * x, adv, dict(name_days=n_total, dropped_bad=int(bad.loc[START:].sum().sum()),
                              dropped_ex_window=int(exm.loc[START:].sum().sum()))


def table(x, types, adv=None):
    rows = []
    sub = {"all": x}
    if adv is not None:
        q = adv.rank(axis=1, pct=True)
        sub["least liquid third"] = x.where(q <= 1 / 3)
        sub["most liquid third"] = x.where(q > 2 / 3)
    for sl, xx in sub.items():
        dm = xx.mean(axis=1)                                     # equal-weight across names, per date
        base = dm[types == "other"]
        for lab in ("QE", "QE+1", "YE", "YE+1", "ME", "ME+1"):
            v = dm[types == lab].dropna()
            if len(v) < 3:
                continue
            diff = v.mean() - base.mean()
            se = np.sqrt(v.var(ddof=1) / len(v) + base.var(ddof=1) / len(base))
            rows.append(dict(slice=sl, day=lab, dates=int(len(v)), excess_bp=float(diff), t=float(diff / se)))
    return pd.DataFrame(rows)


def profile(x, which="all"):
    """Event-time profile of the date-mean discount leg around month-ends: k = -3..+5 sessions
    from the last session of the month (k = 0), excess over 'other' days (types computed on
    the same index). `which`: 'all' month-ends, or 'QE' (Mar/Jun/Sep) only. Descriptive."""
    idx = x.index
    dm = x.mean(axis=1)
    types = day_types(idx)
    s = pd.Series(idx, index=idx)
    last = (s.groupby([idx.year, idx.month]).transform("max") == s).values
    ends = [i for i, d in enumerate(idx) if last[i] and (which == "all" or d.month in (3, 6, 9))]
    # baseline: days at least 6 sessions from any month-end
    near = np.zeros(len(idx), bool)
    for i in [j for j in range(len(idx)) if last[j]]:
        near[max(i - 5, 0):min(i + 7, len(idx))] = True
    base = dm[~near].dropna()
    rows = []
    for k in range(-3, 6):
        v = pd.Series([dm.iloc[i + k] for i in ends if 0 <= i + k < len(idx)]).dropna()
        diff = v.mean() - base.mean()
        se = np.sqrt(v.var(ddof=1) / len(v) + base.var(ddof=1) / len(base))
        rows.append(dict(k=k, excess_bp=float(diff), t=float(diff / se), n=int(len(v))))
    p = pd.DataFrame(rows)
    p["cum_bp"] = p["excess_bp"].cumsum()
    return p


def etf_control():
    e = pd.read_parquet(c.REPO / "data" / "etf_daily.parquet", columns=["date", "ticker", "prc_adj"])
    h = pd.read_parquet(c.REPO / "data" / "holdings" / "ishares_nav_daily.parquet", columns=["date", "ticker", "nav_per_share"])
    names = ["HYG", "LQD", "IEF", "TLT", "SHY"]
    e["date"] = pd.to_datetime(e["date"]); h["date"] = pd.to_datetime(h["date"])
    e = e[e.ticker.isin(names) & (e.date <= c.FIT_END)]; h = h[h.ticker.isin(names) & (h.date <= c.FIT_END)]
    px = e.pivot_table(index="date", columns="ticker", values="prc_adj").sort_index().loc[START:]
    nav = h.pivot_table(index="date", columns="ticker", values="nav_per_share").reindex(px.index)
    # ex-dates move price and NAV together; prc_adj is split-adjusted, NAV is not: names here had no split
    x = 1e4 * (px.pct_change(fill_method=None) - nav.pct_change(fill_method=None))
    x = x.mask(x.abs() > 2000)
    return x


def main():
    out = {}
    ex17 = pd.read_parquet(c.REPO / "data" / "cef" / "cef_distributions.parquet")[["ticker", "ex_date"]]
    ex17["ex_date"] = pd.to_datetime(ex17["ex_date"])
    ex17 = ex17[ex17.ex_date <= c.FIT_END]
    px, nav, vol = load(c.REPO / "data" / "cef" / "cef_prices.parquet", c.REPO / "data" / "cef" / "cef_nav.parquet", CREDIT17)
    x17, adv17, cnt17 = leg(px, nav, vol, ex17)
    t17 = day_types(x17.index)

    c4 = pd.read_csv(C4_FROZEN)["ticker"].tolist()
    exc4 = pd.read_parquet(c.REPO / "data" / "cef_families" / "cef_actions.parquet")
    exc4 = exc4[exc4.dividends > 0].rename(columns={"date": "ex_date"})[["ticker", "ex_date"]]
    exc4["ex_date"] = pd.to_datetime(exc4["ex_date"])
    exc4 = exc4[exc4.ex_date <= c.FIT_END]
    pxc, navc, volc = load(c.REPO / "data" / "cef_families" / "cef_prices.parquet",
                           c.REPO / "data" / "cef_families" / "cef_nav.parquet", c4)
    xc4, advc4, cntc4 = leg(pxc, navc, volc, exc4)
    tc4 = day_types(xc4.index)

    xe = etf_control()
    te = day_types(xe.index)
    res = pd.concat([table(x17, t17, adv17).assign(set="credit 17"),
                     table(xc4, tc4, advc4).assign(set="C4 74"),
                     table(xe, te).assign(set="CONTROL: iShares ETFs")])
    out["counts"] = dict(credit17=cnt17, c4=cntc4)
    out["table"] = res.to_dict(orient="records")
    print("discount leg (r_price - r_NAV) on calendar days, excess over 'other' days, bp; t across dates")
    print(res[["set", "slice", "day", "dates", "excess_bp", "t"]].round(2).to_string(index=False))
    print("counts:", out["counts"])
    # event-time profiles and the price / NAV legs separately (descriptive)
    prof = {}
    for lab, xx in (("credit 17", x17), ("C4 74", xc4), ("CONTROL ETFs", xe)):
        for w in ("all", "QE"):
            pr = profile(xx, w)
            prof[f"{lab} | {w}"] = pr.to_dict(orient="records")
            print(f"\nprofile {lab}, month-ends: {w} (excess over days >= 6 sessions from any month-end)")
            print(pr.round(2).to_string(index=False))
    out["profiles"] = prof
    # legs separately on the credit 17: price return and NAV return, each against 'other' days
    rp = 1e4 * px.pct_change(fill_method=None).loc[START:]
    rn = 1e4 * nav.pct_change(fill_method=None).loc[START:]
    keep = x17.notna()
    legs = pd.concat([table(rp.where(keep), t17).assign(leg="price"), table(rn.where(keep), t17).assign(leg="NAV")])
    out["credit17_legs"] = legs.to_dict(orient="records")
    print("\ncredit 17, the two legs separately (same name-days), excess over 'other' days, bp")
    print(legs[["leg", "day", "dates", "excess_bp", "t"]].round(2).to_string(index=False))
    (HERE / "angle_quarter_end_output.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
