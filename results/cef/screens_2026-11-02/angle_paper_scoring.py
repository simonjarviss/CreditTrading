"""Angle B: what the Alpaca paper account's scoring does to this book, separated from alpha.
Zero trials; fit data only for every return statistic (<= 2022-12-30, asserted).

Two paper mechanics move the P&L of record (Alpaca's EOD equity, SYSTEM.md section 5, 2026-10-19)
without being properties of the strategy:

  (1) DISTRIBUTIONS. Paper books no distribution on a long and no payment in lieu on a short
      (CLAUDE.md landmine 1 [V: docs]). The record is therefore the PRICE-return book; the
      real-money book earns the TOTAL return. The difference is the distribution leg
      sum_i Hs[t,i] * D[t,i]/P[t-1,i] on ex-dates (band_frontier.distribution_yield).
      Live, 09-29..10-30: +320.85 owed (long credited +956.04, short charged -635.19)
      [V, LIVE_ATTRIBUTION_2026-11-02.md].
  (2) LATE-MARKET FILLS. The paper book sends market `day` orders 8 to 2 minutes before the
      close (CLAUDE.md rule 3's recorded exception); paper fills them at the NBBO. Against the
      close the fills cost 5.1bp of notional, of which the half-spread paid at the fill is
      6.2bp [V, the 2026-11-02 fill-drift measurement, 344 fills; aggregates only; read here,
      not re-fetched]. A real-money MOC order pays the auction, not the half-spread.

WHAT THIS SCRIPT MEASURES
  a. the distribution leg on the fit-period unit book, by era, split into long and short,
     and the distribution of its 24-session sums (the live window's length), so the live
     +0.32% of capital can be placed in it;
  b. the part of the distribution leg a one-session deferral of the trade filled just before
     an ex-date could touch (the only 'construction-neutral' lever on paper);
  c. CRSP's closing quoted half-spread on the 13 names, 2020-22, beside the live 6.2bp;
  d. the paper fill cost per year implied by the fit book's turnover.

NEGATIVE CONTROL (H12, named first): for (a), a book that is not systematically long or short
yield should show a leg whose mean is indistinguishable from zero over long windows; the claim
that the live +0.32% is structural requires the fit mean to be significantly non-zero.

Run from the repo root:  python3 -B results/cef/screens_2026-11-02/angle_paper_scoring.py
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
from scripts.cef import band_frontier as bf                     # noqa: E402
from scripts.research.harness import held                       # noqa: E402

CRSP_W4 = (c.REPO.parent / "research-prereg-c5" / "results" / "cef" / "w4" / "_cache_w4"
           / "crsp_dsf_w4.parquet")   # scripts/data/stage_crsp_w4.py; REFERENCES 'CRSP daily for the W4 battery' [V]
FILL_DRIFT = Path("/private/tmp/claude-501/-Users-simonjarvis-Downloads-2027-Projects-Quant---PM2027-2027/"
                  "767b4ac8-7cb7-4bf6-953a-b785b037a5b4/scratchpad/fill_drift/aggregates.json")
LIVE_WINDOW_SESSIONS = 24           # 2026-09-29..2026-10-30, NYSE sessions (counted, no holiday in it)
LIVE_DIST_OWED_PCT = 100 * 320.85 / 100_000.0   # [V] LIVE_ATTRIBUTION_2026-11-02.md; account $100,000


def main():
    T, R, R_tr, H, p = c.live_book()
    with c.fit_panels():
        Y = bf.distribution_yield(R.index, R.columns)
    c.assert_fit(Y, "yield")
    Hs = held(H)
    leg = (Hs * Y).sum(axis=1)
    leg_long = (Hs.clip(lower=0) * Y).sum(axis=1)
    leg_short = (Hs.clip(upper=0) * Y).sum(axis=1)
    # identity check: the leg equals total-return pnl minus price pnl (no split in the fit)
    gap = ((Hs * R_tr).sum(axis=1) - (Hs * R).sum(axis=1) - leg).abs().max()
    assert gap < 1e-10, f"distribution leg does not reconcile with total_returns: {gap}"
    act = Hs.abs().sum(axis=1) > 0
    out = dict(spec=c.SPEC_LINE, panel_last=str(R.index.max().date()))

    rows = []
    for lab, a, b in c.ERAS + (("fit 2005-22", "2005-01-01", "2022-12-30"),):
        m = act & (leg.index >= a) & (leg.index <= b)
        if m.sum() < 30:
            continue
        pr = (Hs * R).sum(axis=1)[m]; tr = (Hs * R_tr).sum(axis=1)[m]
        rows.append(dict(era=lab, days=int(m.sum()),
                         leg_ann_pct=100 * leg[m].mean() * 252, leg_t=c.nw_t(leg[m], 21),
                         long_credit_ann_pct=100 * leg_long[m].mean() * 252,
                         short_charge_ann_pct=100 * leg_short[m].mean() * 252,
                         gross_sr_price=c.ann_sharpe(pr), gross_sr_total=c.ann_sharpe(tr),
                         gross_ann_price_pct=100 * pr.mean() * 252, gross_ann_total_pct=100 * tr.mean() * 252))
    era = pd.DataFrame(rows)
    out["distribution_leg_by_era"] = era.to_dict(orient="records")
    print("a. distribution leg the paper record omits (unit book, % of capital per year)")
    print(era.round(3).to_string(index=False))

    # 24-session sums on active days, overlapping (a distribution, not a test)
    s24 = (100 * leg[act]).rolling(LIVE_WINDOW_SESSIONS).sum().dropna()
    q = s24.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).to_dict()
    pct_live = float((s24 < LIVE_DIST_OWED_PCT).mean())
    out["leg_24_session_sums_pct"] = dict(quantiles=q, live=LIVE_DIST_OWED_PCT,
                                          live_percentile=pct_live, n_windows=int(len(s24)))
    print(f"\n   24-session sums (% of capital): quantiles {({k: round(v, 3) for k, v in q.items()})}; "
          f"live +{LIVE_DIST_OWED_PCT:.3f}% sits at percentile {pct_live:.3f}")

    # b. the part a one-session deferral of the pre-ex-date fill could touch
    # On ex-date t the held weight is Hs[t] = H[t-2], filled at the close of t-1. The trade
    # in it is H[t-2] - H[t-3]. Deferring that trade by one session moves only that piece.
    trade_in = (H.shift(2) - H.shift(3)).reindex_like(Hs).fillna(0.0)
    touch = (trade_in * Y).sum(axis=1)
    m = act
    out["deferrable"] = dict(
        share_of_abs_leg=float(touch[m].abs().sum() / leg[m].abs().sum()),
        deferrable_ann_pct=float(100 * touch[m].mean() * 252),
        leg_ann_pct=float(100 * leg[m].mean() * 252))
    print(f"\nb. trades filled at the close just before an ex-date carry "
          f"{out['deferrable']['share_of_abs_leg']:.1%} of |leg|; mean {out['deferrable']['deferrable_ann_pct']:+.3f}%/yr")

    # c. CRSP closing quoted half-spread, 2020-22, the 13 names
    x = pd.read_parquet(CRSP_W4, columns=["date", "ticker", "bid", "ask", "prc", "vol"])
    x["date"] = pd.to_datetime(x["date"])
    x = x[(x["date"] >= "2020-01-01") & (x["date"] <= c.FIT_END) & x["ticker"].isin(c.UNIVERSE)]
    c.assert_fit(x, "crsp w4")
    x = x[(x["bid"] > 0) & (x["ask"] > x["bid"])]
    x["hs_bp"] = 1e4 * (x["ask"] - x["bid"]) / 2 / ((x["ask"] + x["bid"]) / 2)
    u = pd.read_csv(c.REPO / "data" / "cef" / "cef_universe.csv")[["ticker", "grp"]]
    x = x.merge(u, on="ticker", how="left")
    hs = dict(all_median=float(x["hs_bp"].median()), all_mean=float(x["hs_bp"].mean()),
              by_group_median=x.groupby("grp")["hs_bp"].median().round(2).to_dict(),
              n=int(len(x)))
    out["crsp_closing_half_spread_2020_22_bp"] = hs
    print(f"\nc. CRSP closing quoted half-spread 2020-22: median {hs['all_median']:.2f}bp, mean {hs['all_mean']:.2f}bp; "
          f"by group {hs['by_group_median']} (n {hs['n']})")

    # d. paper fill cost per year from the fit book's turnover
    fd = json.loads(FILL_DRIFT.read_text())["tables"]["all"]["all"]
    turn = H.diff().abs().sum(axis=1)
    mult = c.SIZING_MULTIPLIER if c.SIZING_MULTIPLIER is not None else 1.0
    rowsd = []
    for lab, a, b in (("2015-19", "2015-01-01", "2019-12-31"), ("2020-22", "2020-01-01", "2022-12-30")):
        mm = act & (turn.index >= a) & (turn.index <= b)
        tpy = float(turn[mm].mean() * 252)
        rowsd.append(dict(era=lab, turn_per_yr_unit=tpy, multiplier=mult,
                          paper_fill_cost_pct_per_yr=100 * tpy * mult * fd["B_fill_vs_close_bp"] / 1e4,
                          half_spread_part_pct_per_yr=100 * tpy * mult * fd["E_fill_vs_fillmid_bp"] / 1e4))
    out["paper_fill_cost"] = dict(fill_drift_bp=fd, rows=rowsd)
    print("\nd. paper late-market fill cost implied by fit turnover (B = 5.1bp vs close [V fill-drift])")
    print(pd.DataFrame(rowsd).round(3).to_string(index=False))
    (HERE / "angle_paper_scoring_output.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
