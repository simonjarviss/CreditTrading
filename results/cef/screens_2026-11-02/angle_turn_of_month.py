"""Angle F, second stage: the turn-of-month narrowing that angle_quarter_end.py found instead of
a quarter-end reversal. Is it equity beta, DRIP buying on payable dates (agenda B3), or nothing a
book can earn? Zero trials; fit data only (<= 2022-12-30, asserted). Descriptive throughout.

WHAT angle_quarter_end.py SHOWED [V, its output file]. The discount leg r_price - r_NAV of the
credit 17 rises around EVERY month-end, k = -3..+2 (k = 0 the last session), cumulating about
+74bp over days >= 6 sessions from any month-end, with no reversal by k = +5; C4's 74 show
about +42bp by k = +1; the AP-arbitraged iShares ETFs show nothing. The quarter-end
'pump-and-reverse' hypothesis it was built for is therefore wrong in sign at k = +1.

THREE CHECKS, each named before it was run:
  1. EQUITY BETA (D4 in costume?). CEF prices carry equity sentiment, and equities have a
     turn-of-month effect of their own. Residualise the date-mean leg on same-day SPY and HYG
     total returns (fit-period OLS) and redo the profile. If the excess vanishes, it is beta.
  2. MECHANISM: DRIP. A plan agent buys in the open market "on or shortly after the payment
     date" when the fund trades at a DISCOUNT; at a premium the fund issues new shares instead
     (PDI's plan [V: REFERENCES row 521]). Most credit CEFs here pay on the first business day
     of the month [U: pay dates are not in the local panel]. So the excess should live in
     name-days whose discount at t-1 is negative, and be smaller or absent in premium name-days.
     That split is the control the agenda wrote for B3.
  3. WHAT A BOOK COULD EARN. The tradable form is a pre-scheduled MOC calendar trade: long the
     names at the close of k = -3, out at the close of k = +2 (5 sessions), on TOTAL returns
     (no ex-date window removed: a real holder cannot skip them), against HYG's total return.
     Placebo: the same 5-session trade centred 10 sessions earlier (mid-month).

Run from the repo root:  python3 -B results/cef/screens_2026-11-02/angle_turn_of_month.py
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
import angle_quarter_end as q                                    # noqa: E402
from scripts.cef import band_frontier as bf                     # noqa: E402

CRSP_W4 = (c.REPO.parent / "research-prereg-c5" / "results" / "cef" / "w4" / "_cache_w4"
           / "crsp_dsf_w4.parquet")   # scripts/data/stage_crsp_w4.py (R2 read 2026-10-11, stops 2022-12-30) [V]
ETF_XASSET = (c.REPO.parent / "trial-xasset" / "results" / "xasset" / "_cache_xasset"
              / "etf_daily_xasset.parquet")


def etf(names):
    x = pd.read_parquet(ETF_XASSET, columns=["date", "ticker", "ret_total"])
    x["date"] = pd.to_datetime(x["date"])
    x = x[x.ticker.isin(names) & (x.date <= c.FIT_END)]
    return c.assert_fit(x.pivot_table(index="date", columns="ticker", values="ret_total").sort_index(), "etf")


def month_end_positions(idx):
    s = pd.Series(idx, index=idx)
    last = (s.groupby([idx.year, idx.month]).transform("max") == s).values
    return [i for i in range(len(idx)) if last[i]]


def profile_series(dm, idx, ks=range(-3, 6)):
    ends = month_end_positions(idx)
    near = np.zeros(len(idx), bool)
    for i in ends:
        near[max(i - 5, 0):min(i + 7, len(idx))] = True
    base = dm[~near].dropna()
    rows = []
    for k in ks:
        v = pd.Series([dm.iloc[i + k] for i in ends if 0 <= i + k < len(idx)]).dropna()
        diff = v.mean() - base.mean()
        se = np.sqrt(v.var(ddof=1) / len(v) + base.var(ddof=1) / len(base))
        rows.append(dict(k=k, excess_bp=float(diff), t=float(diff / se), n=int(len(v))))
    p = pd.DataFrame(rows)
    p["cum_bp"] = p["excess_bp"].cumsum()
    return p, float(base.mean())


def window_trade(R, hedge, idx, offset=0, enter=-3, exit_=2):
    """Per month: equal-weight mean over names of the summed total return from close(k=enter) to
    close(k=exit_), minus the hedge's summed return. offset shifts the anchor (placebo -10)."""
    ends = month_end_positions(idx)
    rows = []
    for i in ends:
        a, b = i + offset + enter + 1, i + offset + exit_      # returns of sessions enter+1..exit_
        if a < 1 or b >= len(idx):
            continue
        blk = R.iloc[a:b + 1]
        names = blk.columns[blk.notna().all()]
        if len(names) < 3:
            continue
        cef = float(blk[names].sum().mean())
        h = float(hedge.iloc[a:b + 1].sum())
        rows.append(dict(month=str(idx[i].date()), cef_bp=1e4 * cef, hedged_bp=1e4 * (cef - h)))
    return pd.DataFrame(rows)


def main():
    out = {}
    # rebuild the credit-17 leg exactly as angle_quarter_end does (same filters)
    ex17 = pd.read_parquet(c.REPO / "data" / "cef" / "cef_distributions.parquet")[["ticker", "ex_date"]]
    ex17["ex_date"] = pd.to_datetime(ex17["ex_date"]); ex17 = ex17[ex17.ex_date <= c.FIT_END]
    px, nav, vol = q.load(c.REPO / "data" / "cef" / "cef_prices.parquet", c.REPO / "data" / "cef" / "cef_nav.parquet", q.CREDIT17)
    x17, adv17, _ = q.leg(px, nav, vol, ex17)
    idx = x17.index
    F = etf(["SPY", "HYG"]).reindex(idx)

    # 1. residualise the date-mean leg on SPY and HYG (fit-period OLS, descriptive)
    dm = x17.mean(axis=1)
    d = pd.concat([dm.rename("y"), 1e4 * F["SPY"], 1e4 * F["HYG"]], axis=1).dropna()
    A = np.column_stack([np.ones(len(d)), d[["SPY", "HYG"]].values])
    b, *_ = np.linalg.lstsq(A, d["y"].values, rcond=None)
    resid = pd.Series(d["y"].values - A[:, 1:] @ b[1:], index=d.index).reindex(idx)
    p_raw, base_raw = profile_series(dm, idx)
    p_res, base_res = profile_series(resid, idx)
    out["beta"] = dict(spy=float(b[1]), hyg=float(b[2]))
    out["profile_raw"] = p_raw.to_dict(orient="records"); out["baseline_raw_bp_per_day"] = base_raw
    out["profile_resid"] = p_res.to_dict(orient="records"); out["baseline_resid_bp_per_day"] = base_res
    print(f"1. credit 17 leg on SPY/HYG: beta SPY {b[1]:+.3f}, HYG {b[2]:+.3f}; baseline raw {base_raw:+.2f} bp/day")
    print("   profile, raw vs residual (excess over days >= 6 sessions from a month-end):")
    print(pd.concat([p_raw.set_index("k").add_prefix("raw_"), p_res.set_index("k").add_prefix("resid_")], axis=1)
          [["raw_excess_bp", "raw_t", "raw_cum_bp", "resid_excess_bp", "resid_t", "resid_cum_bp"]].round(2).to_string())

    # 2. DRIP split: discount vs premium at t-1 (the harness's disc, known before t)
    with c.fit_panels():
        pnl = bf.build_panel(universe=q.CREDIT17)
    disc_prev = pnl["disc"].shift(1).reindex(index=idx, columns=x17.columns)
    res2 = {}
    for lab, m in (("discount at t-1", disc_prev < 0), ("premium at t-1", disc_prev > 0)):
        dmm = x17.where(m).mean(axis=1)
        pr, base = profile_series(dmm, idx)
        res2[lab] = dict(profile=pr.to_dict(orient="records"), baseline=base,
                         window_m3_p2_excess_bp=float(pr.set_index("k").loc[-2:2, "excess_bp"].sum()),
                         share_of_name_days=float(m.sum().sum() / disc_prev.notna().sum().sum()))
        print(f"\n2. {lab} (share of name-days {res2[lab]['share_of_name_days']:.2f}): k -2..+2 excess sum "
              f"{res2[lab]['window_m3_p2_excess_bp']:+.1f}bp")
        print(pr.round(2).to_string(index=False))
    out["drip_split"] = res2

    # 2b. by sponsor (data/cef/cef_facts.csv longName's first word, yfinance read 2026-09-11):
    # a sponsor-specific pay or DRIP convention would show as a sponsor-specific profile.
    facts = pd.read_csv(c.REPO / "data" / "cef" / "cef_facts.csv")[["ticker", "longName"]]
    spons = {t: str(n).split()[0].upper() for t, n in zip(facts.ticker, facts.longName)}
    res2b = {}
    for sp in sorted({spons[t] for t in x17.columns}):
        cols = [t for t in x17.columns if spons[t] == sp]
        pr, _ = profile_series(x17[cols].mean(axis=1), idx)
        v = pr.set_index("k").loc[-2:2]
        res2b[sp] = dict(names=cols, k_m2_p2_excess_bp=float(v.excess_bp.sum()), max_abs_t=float(v.t.abs().max()))
    out["sponsor_split"] = res2b
    print("\n2b. by sponsor, discount-leg excess summed over k -2..+2:",
          {k: (v["names"], round(v["k_m2_p2_excess_bp"], 1)) for k, v in res2b.items()})

    # 3. the tradable calendar form, on total returns (all name-days), against HYG
    with c.fit_panels():
        T, R = bf.build_targets(universe=list(c.UNIVERSE))       # only for the index/universe
    # total returns on the credit 17 from the harness's own reader (raises on any gap)
    rp = px.pct_change(fill_method=None).where(lambda z: z.abs() < 0.5)
    with c.fit_panels():
        y = bf.distribution_yield(rp.index, list(rp.columns))
    Rtr = (rp + y.reindex_like(rp)).loc[q.START:]
    c.assert_fit(Rtr, "Rtr")
    hy = F["HYG"].reindex(Rtr.index)
    res3 = {}
    for lab, off in (("turn-of-month (k -2..+2)", 0), ("PLACEBO: 10 sessions earlier", -10)):
        w = window_trade(Rtr, hy, Rtr.index, offset=off)
        w = w[w.month >= "2007-05-01"]                          # HYG exists from 2007-04
        res3[lab] = dict(months=int(len(w)), cef_bp=float(w.cef_bp.mean()), cef_t=float(w.cef_bp.mean() / (w.cef_bp.std() / np.sqrt(len(w)))),
                         hedged_bp=float(w.hedged_bp.mean()), hedged_t=float(w.hedged_bp.mean() / (w.hedged_bp.std() / np.sqrt(len(w)))),
                         hedged_by_era={e: float(w[(w.month >= a) & (w.month <= z)].hedged_bp.mean()) for e, a, z in c.ERAS})
        print(f"\n3. {lab}: months {len(w)}; CEF EW total return {res3[lab]['cef_bp']:+.1f}bp (t {res3[lab]['cef_t']:+.2f}); "
              f"minus HYG {res3[lab]['hedged_bp']:+.1f}bp (t {res3[lab]['hedged_t']:+.2f}); by era {({k: round(v, 1) for k, v in res3[lab]['hedged_by_era'].items()})}")
    out["calendar_trade"] = res3

    # 4. is the turn-of-month leg the pre-ex run-up in disguise? (a) where each name's ex-dates
    # fall in the month; (b) the trade on name-months with NO ex-date from k-8 to k+2 (so neither
    # the pre-ex run-up nor the ex-date itself is inside or just before the window).
    exd = ex17[ex17.ticker.isin(Rtr.columns) & (ex17.ex_date >= q.START)].copy()
    exd["dom"] = exd.ex_date.dt.day
    out["ex_day_of_month_median"] = exd.groupby("ticker")["dom"].median().to_dict()
    print("\n4a. median ex-date day of month:", out["ex_day_of_month_median"])
    idx2 = Rtr.index
    exflag = pd.DataFrame(False, index=idx2, columns=Rtr.columns)
    for tk, g in exd.groupby("ticker"):
        pos = idx2.searchsorted(g.ex_date.values)
        pos = pos[pos < len(idx2)]
        exflag.iloc[pos, exflag.columns.get_loc(tk)] = True
    ends = month_end_positions(idx2)
    rows = []
    for i in ends:
        a, b = i - 2, i + 2
        if i - 8 < 0 or b >= len(idx2) or idx2[i] < pd.Timestamp("2007-05-01"):
            continue
        clean = ~exflag.iloc[i - 8:b + 1].any()
        blk = Rtr.iloc[a:b + 1]
        names = [t for t in blk.columns[blk.notna().all()] if clean[t]]
        if len(names) < 3:
            continue
        rows.append(dict(month=str(idx2[i].date()), n=len(names),
                         hedged_bp=1e4 * (float(blk[names].sum().mean()) - float(hy.iloc[a:b + 1].sum()))))
    w4 = pd.DataFrame(rows)
    out["ex_clean_trade"] = dict(months=int(len(w4)), mean_names=float(w4.n.mean()),
                                 hedged_bp=float(w4.hedged_bp.mean()),
                                 t=float(w4.hedged_bp.mean() / (w4.hedged_bp.std() / np.sqrt(len(w4)))))
    print(f"4b. ex-clean name-months (no ex-date k-8..k+2): months {len(w4)}, mean names {w4.n.mean():.1f}; "
          f"minus HYG {out['ex_clean_trade']['hedged_bp']:+.1f}bp (t {out['ex_clean_trade']['t']:+.2f})")

    # 5. is it additive to the book? monthly correlation of the calendar trade with the fit book
    T, R_px, R_tr, H, _ = c.live_book()
    from scripts.research.harness import held
    book = (held(H) * R_tr).sum(axis=1)
    bm = book.groupby(book.index.to_period("M")).sum()
    w = window_trade(Rtr, hy, Rtr.index)
    w["m"] = pd.to_datetime(w.month).dt.to_period("M")
    j = pd.concat([w.set_index("m")["hedged_bp"], 1e4 * bm.rename("book_bp")], axis=1).dropna()
    j = j[j.book_bp != 0]
    out["corr_with_book_monthly"] = dict(corr=float(j.corr().iloc[0, 1]), months=int(len(j)))
    print(f"5. monthly corr(calendar trade, fit book gross TR) = {out['corr_with_book_monthly']['corr']:+.3f} over {len(j)} active months")
    # 6. SECOND SOURCE (decision-driving, so double-checked): CRSP `ret` (total return) for the
    # 13 deployed names and HYG, from the W4 stager's cache. Same window, same placebo.
    x = pd.read_parquet(CRSP_W4, columns=["date", "ticker", "ret", "prc"])
    x["date"] = pd.to_datetime(x["date"]); x = x[x.date <= c.FIT_END]
    c.assert_fit(x, "crsp")
    cr = x.pivot_table(index="date", columns="ticker", values="ret").sort_index()
    noclose = x.pivot_table(index="date", columns="ticker", values="prc").sort_index() < 0  # CRSP: no closing trade
    names13 = [t for t in c.UNIVERSE if t in cr.columns]
    Rc = cr[names13].mask(noclose[names13]).loc[q.START:]
    hc = cr["HYG"].reindex(Rc.index)
    res6 = {}
    for lab, off in (("CRSP turn-of-month (k -2..+2)", 0), ("CRSP PLACEBO: 10 sessions earlier", -10)):
        w = window_trade(Rc, hc, Rc.index, offset=off)
        w = w[w.month >= "2007-05-01"]
        lo, hi = w.hedged_bp.quantile([0.05, 0.95])
        trim = w.hedged_bp[(w.hedged_bp >= lo) & (w.hedged_bp <= hi)]
        res6_robust = dict(median_bp=float(w.hedged_bp.median()), share_positive=float((w.hedged_bp > 0).mean()),
                           trimmed_5pct_mean_bp=float(trim.mean()),
                           trimmed_t=float(trim.mean() / (trim.std() / np.sqrt(len(trim)))),
                           ex_2008_09_and_2020_H1_bp=float(w[~(w.month.str[:4].isin(["2008", "2009"]) |
                                                               w.month.str[:7].isin([f"2020-0{m}" for m in range(1, 7)]))].hedged_bp.mean()))
        print(f"   robust: {({k: round(v, 3) for k, v in res6_robust.items()})}")
        res6[lab + " | robust"] = res6_robust
        res6[lab] = dict(months=int(len(w)), hedged_bp=float(w.hedged_bp.mean()),
                         t=float(w.hedged_bp.mean() / (w.hedged_bp.std() / np.sqrt(len(w)))),
                         sd_bp=float(w.hedged_bp.std()),
                         hedged_by_era={e: float(w[(w.month >= a) & (w.month <= z)].hedged_bp.mean()) for e, a, z in c.ERAS})
        print(f"6. {lab}: months {len(w)}; minus HYG {res6[lab]['hedged_bp']:+.1f}bp (t {res6[lab]['t']:+.2f}, sd {res6[lab]['sd_bp']:.0f}); "
              f"by era {({k: round(v, 1) for k, v in res6[lab]['hedged_by_era'].items()})}")
    out["crsp_second_source"] = res6

    # 6b. group-matched hedge (CRSP): the muni names against MUB, the rest against HYG; and the
    # window's beta to IEF (TERM), since X3 found a month-end Treasury extension effect (D4, TERM).
    u2 = pd.read_csv(c.REPO / "data" / "cef" / "cef_universe.csv")[["ticker", "grp"]]
    g2 = dict(zip(u2.ticker, u2.grp))
    mun = [t for t in names13 if g2[t] == "muni"]; tax = [t for t in names13 if g2[t] != "muni"]
    rows6b = []
    for i in month_end_positions(Rc.index):
        a, b = i - 2, i + 2
        if a < 1 or b >= len(Rc.index) or Rc.index[i] < pd.Timestamp("2007-10-01"):
            continue
        blk = Rc.iloc[a:b + 1]
        ok = blk.columns[blk.notna().all()]
        m_ = [t for t in mun if t in ok]; t_ = [t for t in tax if t in ok]
        if len(t_) < 3:
            continue
        legm = (float(blk[m_].sum().mean()) - float(cr["MUB"].iloc[a:b + 1].sum())) if m_ else np.nan
        legt = float(blk[t_].sum().mean()) - float(cr["HYG"].iloc[a:b + 1].sum())
        n_m, n_t = len(m_), len(t_)
        comb = legt if not m_ else (n_m * legm + n_t * legt) / (n_m + n_t)
        rows6b.append(dict(month=str(Rc.index[i].date()), hedged_bp=1e4 * comb,
                           ief_bp=1e4 * float(cr["IEF"].iloc[a:b + 1].sum())))
    w6 = pd.DataFrame(rows6b)
    bI = np.polyfit(w6.ief_bp, w6.hedged_bp, 1)
    res6b = dict(months=int(len(w6)), hedged_bp=float(w6.hedged_bp.mean()),
                 t=float(w6.hedged_bp.mean() / (w6.hedged_bp.std() / np.sqrt(len(w6)))),
                 beta_to_ief_window=float(bI[0]), intercept_bp=float(bI[1]))
    out["crsp_group_hedge"] = res6b
    print(f"6b. CRSP, munis vs MUB and the rest vs HYG (from 2007-10, MUB's start): {res6b['hedged_bp']:+.1f}bp "
          f"(t {res6b['t']:+.2f}); beta to IEF's window return {res6b['beta_to_ief_window']:+.2f}, intercept {res6b['intercept_bp']:+.1f}bp")

    # 7. the paper artefact of the hedge: HYG's ex-date relative to the month-end (fit 2015-22).
    # Paper books no payment in lieu, so a short HYG held over its ex-date books the drop as a gain.
    e = pd.read_parquet(c.REPO / "data" / "etf_daily.parquet", columns=["date", "ticker", "ret_total", "ret_px"])
    e["date"] = pd.to_datetime(e["date"])
    e = e[(e.ticker == "HYG") & (e.date >= "2015-01-01") & (e.date <= c.FIT_END)].set_index("date")
    dy = (e.ret_total - e.ret_px)
    ends_e = month_end_positions(e.index)
    kk = []
    for d in dy[dy > 1e-4].index:
        i = e.index.get_loc(d)
        prev = [j for j in ends_e if j < i]
        kk.append(i - prev[-1] if prev else None)
    kk = pd.Series(kk)
    out["hyg_ex_k"] = dict(share_at_k1=float((kk == 1).mean()), n=int(len(kk)), mean_yield_bp=float(1e4 * dy[dy > 1e-4].mean()))
    print(f"7. HYG ex-date at k=+1 in {out['hyg_ex_k']['share_at_k1']:.0%} of {len(kk)} months (2015-22); "
          f"mean distribution {out['hyg_ex_k']['mean_yield_bp']:.1f}bp: a short HYG over k=+1 books that on paper")

    # 9. does the live book already sit on the cycle? Its daily gross TR P&L (unit book) in event
    # time around month-ends, and its mean net CEF exposure (sum of held weights) there.
    hb = held(H)
    bk = (hb * R_tr).sum(axis=1)
    bk = bk[hb.abs().sum(axis=1) > 0]
    prb, baseb = profile_series(1e4 * bk.reindex(R_tr.index), R_tr.index)
    netx = hb.sum(axis=1).reindex(R_tr.index)
    ends_b = month_end_positions(R_tr.index)
    net_tom = float(np.nanmean([netx.iloc[i + k] for i in ends_b for k in range(-2, 3) if 0 <= i + k < len(netx)]))
    out["book_in_event_time"] = dict(profile=prb.to_dict(orient="records"), baseline_bp=baseb,
                                     mean_net_weight_k_m2_p2=net_tom, mean_net_weight_all=float(netx[hb.abs().sum(axis=1) > 0].mean()))
    print("\n9. fit book gross TR P&L (bp of capital per day) in event time; mean net weight k-2..+2 "
          f"{net_tom:+.3f} vs all active days {out['book_in_event_time']['mean_net_weight_all']:+.3f}")
    print(prb.round(2).to_string(index=False))

    # 8. power of a later test (normal approximation; the effect sizes are the fit's, post hoc).
    from math import erf, sqrt, log
    Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))
    mu, sd = res6["CRSP turn-of-month (k -2..+2)"]["hedged_bp"], res6["CRSP turn-of-month (k -2..+2)"]["sd_bp"]
    bars = {"EVENTS, declared N=8": sqrt(2 * log(8)), "CEF, N=54": sqrt(2 * log(54))}
    pw = []
    for design, months in (("2023-01..2026-09 time holdout, the 13/17", 45), ("27 untouched names, 2007-05..2022-12 (sd assumed equal)", 187)):
        for frac in (1.0, 0.5):
            et = frac * mu / (sd / sqrt(months))
            pw.append(dict(design=design, effect=f"{frac:.0%} of fit", expected_t=et,
                           **{f"P(t>={b:.3f}) {k}": Phi(et - b) for k, b in bars.items()}))
    out["power"] = pw
    print("8. power"); print(pd.DataFrame(pw).round(3).to_string(index=False))
    (HERE / "angle_turn_of_month_output.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
