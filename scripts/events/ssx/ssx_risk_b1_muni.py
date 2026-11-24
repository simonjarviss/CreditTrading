"""B1 census: how much of a muni CEF's NAV does a credit event touch in a quarter,
and does the fund's own mark of a distressed CUSIP lag? Zero trials.

WHY
---
The ssx_risk B1 idea is a subtract-only flag: when a muni credit event (a
payment default, an unscheduled reserve draw, a rating change; Rule 15c2-12's
listed events on EMMA) hits a bond a fund holds, its matrix-priced NAV may keep
the old mark while the listed price moves, and the discount z-score would buy
the "cheap" fund. Before anyone designs that flag, its kill gate asks one
number: the event-affected NAV weight per fund-quarter, at the median. Below
10bp the flag would almost never bind (kill number declared in the seat brief,
2026-10-19, before this script ran).

WHAT IS MEASURED (fit period only: N-PORT report dates 2019-09-30 .. 2022-12-31)
--------------------------------------------------------------------------------
From the funds' own public N-PORT filings (ssx_risk_nport.py):
  stock, per fund-quarter: weight flagged isDefault=Y, areIntrstPmntsInArrs=Y,
      fair-value Level 3, and the non-investment-grade share of credit-spread
      sensitivity (CS01, the fund's own IG / non-IG split; N-PORT carries no
      per-holding rating, so this is the only rating-like field it has);
  flow, per fund-quarter (the event the flag would key on): CUSIPs held at
      both t-1 and t whose default or arrears flag turned from N to Y between
      the two snapshots, weighted at t; and, as a broader upper-bound proxy for
      impairment, CUSIPs whose own mark fell >= 10 points more than the fund's
      median mark change over the quarter (an idiosyncratic mark drop; a level
      chosen as "a muni bond priced for distress", not fitted to anything);
  mark lag (descriptive, B1 d): for each newly flagged CUSIP, its mark at t-1
      and t; and for CUSIPs held by two or more of these funds on the same
      report date, the spread of their marks (same bond, different funds'
      pricing), against the same statistic for all shared CUSIPs as the control.

No fund return, NAV return, P&L or drift is computed. Bond marks are the fund's
own valuations of single CUSIPs, read as staleness statistics.

Reproduce (offline, after ssx_risk_nport.py --fetch/--parse):
    python3 scripts/events/ssx/ssx_risk_b1_muni.py
Output: results/events/ssx/ssx_risk/b1_muni_fund_quarters.csv, b1_muni_summary.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_risk"
OUT = REPO / "results" / "events" / "ssx" / "ssx_risk"
DEPLOYED_MUNI = ("MQY", "MHD")
CONTEXT_MUNI = ("NAD", "NEA", "NVG", "NZF", "NAN")
KILL_BP = 10.0           # the seat brief's kill number (declared before measuring)
IDIO_DROP_PTS = 10.0     # idiosyncratic mark drop, in points of par (see docstring)
LAST = pd.Timestamp("2022-12-31")


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    h = pd.read_parquet(CACHE / "nport_holdings_ssx_risk.parquet")
    m = pd.read_parquet(CACHE / "nport_fundinfo_ssx_risk.parquet")
    if h.report_dt.max() > LAST or m.report_dt.max() > LAST:
        raise AssertionError("a holdings snapshot after 2022-12-31 reached the census (H13)")
    return h, m


def fund_quarters(h: pd.DataFrame, m: pd.DataFrame, tickers) -> pd.DataFrame:
    rows = []
    for t in tickers:
        ht = h[h.ticker == t]
        dates = sorted(ht.report_dt.unique())
        prev = None
        for d in dates:
            cur = ht[(ht.report_dt == d) & ht.cusip.notna() & (ht.cusip != "000000000")]
            cur = cur.groupby("cusip").agg(pct=("pct_val", "sum"), dflt=("is_default", "max"),
                                           arr=("in_arrears", "max"), px=("price_per_100", "mean"),
                                           l3=("fair_val_level", lambda s: (s == "3").any()),
                                           cat=("issuer_cat", "first"), mat=("maturity_dt", "first"),
                                           cpn=("coupon", "first"))
            ytm = (pd.to_datetime(cur.mat, errors="coerce") - pd.Timestamp(d)).dt.days / 365.25
            cur["mbkt"] = pd.cut(ytm, [-1e9, 5, 10, 20, 1e9], labels=["<5", "5-10", "10-20", "20+"])
            cur["cbkt"] = pd.cut(cur.cpn, [-1e9, 3.0, 4.5, 1e9], labels=["<3", "3-4.5", "4.5+"])
            mi = m[(m.ticker == t) & (m.report_dt == d)].iloc[0]
            cs = (mi.cs01_ig or 0) + (mi.cs01_nonig or 0)
            r = {"ticker": t, "report_dt": pd.Timestamp(d).date(), "filing_date": mi.filing_date.date(),
                 "n_cusips": len(cur), "gross_pct": cur.pct.sum(), "muni_pct": cur.loc[cur.cat == "MUN", "pct"].sum(),
                 "stock_default_bp": 100 * cur.loc[cur.dflt == "Y", "pct"].sum(),
                 "stock_arrears_bp": 100 * cur.loc[cur.arr == "Y", "pct"].sum(),
                 "stock_level3_bp": 100 * cur.loc[cur.l3, "pct"].sum(),
                 "nonig_cs01_share": (mi.cs01_nonig / cs) if (cs and mi.cs01_nonig is not None) else np.nan}
            if prev is not None:
                both = cur.join(prev, rsuffix="_p", how="inner")
                newflag = both[((both.dflt == "Y") & (both.dflt_p != "Y")) | ((both.arr == "Y") & (both.arr_p != "Y"))]
                dpx = both.px - both.px_p
                med = dpx.median()
                # A rate sell-off moves long, low-coupon munis 10+ points with no
                # credit news (2022), so the expected change is the median within
                # the bond's own maturity x coupon bucket, not the fund median.
                bkt = both.mbkt.astype(str) + "|" + both.cbkt.astype(str)
                exp = dpx.groupby(bkt).transform("median")
                idio = both[(dpx - exp) <= -IDIO_DROP_PTS]
                r.update({"flow_newflag_n": len(newflag), "flow_newflag_bp": 100 * newflag.pct.sum(),
                          "flow_idio_drop_n": len(idio), "flow_idio_drop_bp": 100 * idio.pct.sum(),
                          "median_mark_change_pts": med, "n_held_both": len(both)})
            rows.append(r)
            prev = cur
    return pd.DataFrame(rows)


def mark_dispersion(h: pd.DataFrame, tickers) -> dict:
    """Same CUSIP, same report date, two or more funds: the spread of their marks."""
    x = h[h.ticker.isin(tickers) & h.price_per_100.notna() & (h.cusip != "000000000")]
    x = x.groupby(["cusip", "report_dt", "ticker"]).agg(px=("price_per_100", "mean"),
                                                         dflt=("is_default", "max"), arr=("in_arrears", "max")).reset_index()
    g = x.groupby(["cusip", "report_dt"]).agg(n=("ticker", "nunique"), lo=("px", "min"), hi=("px", "max"),
                                              flagged=("dflt", lambda s: (s == "Y").any()),
                                              arr=("arr", lambda s: (s == "Y").any()),
                                              mixed_flag=("dflt", lambda s: s.nunique() > 1))
    g = g[g.n >= 2]
    g["range_pts"] = g.hi - g.lo
    fl = g[g.flagged | g.arr]
    def q(s):
        return {"n": int(len(s)), "median": float(s.median()) if len(s) else None,
                "p90": float(s.quantile(0.9)) if len(s) else None, "max": float(s.max()) if len(s) else None}
    return {"all_shared": q(g.range_pts), "flagged_shared": q(fl.range_pts),
            "flagged_shared_mixed_default_flag": int(g.mixed_flag.sum())}


SPONSOR = {"MQY": "BlackRock", "MHD": "BlackRock", "NAD": "Nuveen", "NEA": "Nuveen", "NVG": "Nuveen",
           "NZF": "Nuveen", "NAN": "Nuveen"}


def cross_sponsor(h: pd.DataFrame, tickers) -> dict:
    """Same CUSIP, same report date, held by a BlackRock AND a Nuveen fund: the
    gap between the two sponsors' marks. Within one sponsor the marks are
    identical by construction (one pricing process), so only the cross-sponsor
    gap says anything about discretion in the marks (Cici, Gibson & Merrick)."""
    x = h[h.ticker.isin(tickers) & h.price_per_100.notna() & (h.cusip != "000000000")].copy()
    x["sp"] = x.ticker.map(SPONSOR)
    g = x.groupby(["cusip", "report_dt", "sp"]).agg(px=("price_per_100", "mean"),
                                                    f=("is_default", lambda s: (s == "Y").any()),
                                                    a=("in_arrears", lambda s: (s == "Y").any())).reset_index()
    w = g.pivot_table(index=["cusip", "report_dt"], columns="sp", values=["px", "f", "a"], aggfunc="first").dropna()
    if w.empty:
        return {"n_pairs": 0}
    gap = (w[("px", "BlackRock")] - w[("px", "Nuveen")]).abs()
    flagged = (w[("f", "BlackRock")].astype(bool) | w[("f", "Nuveen")].astype(bool)
               | w[("a", "BlackRock")].astype(bool) | w[("a", "Nuveen")].astype(bool))
    disagree = (w[("f", "BlackRock")].astype(bool) != w[("f", "Nuveen")].astype(bool))
    def q(s):
        return {"n": int(len(s)), "median": round(float(s.median()), 4) if len(s) else None,
                "p90": round(float(s.quantile(0.9)), 4) if len(s) else None,
                "max": round(float(s.max()), 4) if len(s) else None}
    return {"all_cross_sponsor": q(gap), "flagged_by_either": q(gap[flagged]),
            "default_flag_disagrees_between_sponsors": int(disagree.sum()),
            "share_gap_ge_1pt": round(float((gap >= 1).mean()), 4)}


def unchanged_marks(h: pd.DataFrame, tickers) -> dict:
    """Share of consecutive-quarter pairs in which a CUSIP's mark is EXACTLY
    unchanged, for default/arrears-flagged holdings against unflagged ones.
    An unchanged quarterly mark on a distressed bond is the staleness signature."""
    x = h[h.ticker.isin(tickers) & h.price_per_100.notna() & (h.cusip != "000000000")]
    x = x.groupby(["ticker", "cusip", "report_dt"]).agg(px=("price_per_100", "mean"),
                                                         fl=("is_default", lambda s: (s == "Y").any()),
                                                         ar=("in_arrears", lambda s: (s == "Y").any())).reset_index()
    x = x.sort_values(["ticker", "cusip", "report_dt"])
    x["px_p"] = x.groupby(["ticker", "cusip"]).px.shift()
    x["dt_p"] = x.groupby(["ticker", "cusip"]).report_dt.shift()
    x = x.dropna(subset=["px_p"])
    x = x[(x.report_dt - x.dt_p).dt.days.between(80, 100)]          # adjacent quarters only
    same = (x.px - x.px_p).abs() < 1e-9
    dist = x.fl | x.ar
    return {"flagged_pairs": int(dist.sum()), "flagged_unchanged_share": round(float(same[dist].mean()), 4),
            "unflagged_pairs": int((~dist).sum()), "unflagged_unchanged_share": round(float(same[~dist].mean()), 4)}


def newflag_marks(h: pd.DataFrame, tickers) -> pd.DataFrame:
    """Each new default/arrears flag: the fund's mark at t-1 and t (descriptive)."""
    out = []
    for t in tickers:
        ht = h[(h.ticker == t) & (h.cusip != "000000000")]
        piv = ht.groupby(["cusip", "report_dt"]).agg(px=("price_per_100", "mean"), d=("is_default", "max"),
                                                      a=("in_arrears", "max"), pct=("pct_val", "sum"),
                                                      name=("name", "first")).reset_index()
        dates = sorted(piv.report_dt.unique())
        for d0, d1 in zip(dates[:-1], dates[1:]):
            a = piv[piv.report_dt == d0].set_index("cusip")
            b = piv[piv.report_dt == d1].set_index("cusip")
            j = b.join(a, rsuffix="_p", how="inner")
            nf = j[((j.d == "Y") & (j.d_p != "Y")) | ((j.a == "Y") & (j.a_p != "Y"))]
            for c, r in nf.iterrows():
                out.append({"ticker": t, "cusip": c, "name": r["name"], "report_dt": pd.Timestamp(d1).date(),
                            "mark_prev": r.px_p, "mark_now": r.px, "weight_bp": 100 * r.pct})
    return pd.DataFrame(out)


def main() -> int:
    h, m = load()
    tick = list(DEPLOYED_MUNI) + list(CONTEXT_MUNI)
    fq = fund_quarters(h, m, tick)
    OUT.mkdir(parents=True, exist_ok=True)
    fq.to_csv(OUT / "b1_muni_fund_quarters.csv", index=False)
    nf = newflag_marks(h, tick)
    nf.to_csv(OUT / "b1_muni_newflags.csv", index=False)
    summ = {"window_report_dt": [str(fq.report_dt.min()), str(fq.report_dt.max())], "kill_bp": KILL_BP}
    for label, names in (("deployed_MQY_MHD", DEPLOYED_MUNI), ("context_NAD_NEA_NVG_NZF_NAN", CONTEXT_MUNI),
                         ("all_7", tuple(tick))):
        f = fq[fq.ticker.isin(names)]
        fl = f.dropna(subset=["flow_newflag_bp"])
        summ[label] = {
            "fund_quarters_with_flow": int(len(fl)),
            "flow_newflag_bp_median": float(fl.flow_newflag_bp.median()),
            "flow_newflag_bp_mean": float(fl.flow_newflag_bp.mean()),
            "flow_newflag_bp_p90": float(fl.flow_newflag_bp.quantile(0.9)),
            "share_fq_with_any_newflag": float((fl.flow_newflag_n > 0).mean()),
            "flow_idio_drop_bp_median": float(fl.flow_idio_drop_bp.median()),
            "flow_idio_drop_bp_p90": float(fl.flow_idio_drop_bp.quantile(0.9)),
            "share_fq_idio_drop_ge_kill": float((fl.flow_idio_drop_bp >= KILL_BP).mean()),
            "stock_default_bp_median": float(f.stock_default_bp.median()),
            "stock_arrears_bp_median": float(f.stock_arrears_bp.median()),
            "nonig_cs01_share_median": float(f.nonig_cs01_share.median()),
            "per_fund_nonig_cs01_share_median": f.groupby("ticker").nonig_cs01_share.median().round(4).to_dict(),
            "per_fund_flow_newflag_bp_median": fl.groupby("ticker").flow_newflag_bp.median().round(2).to_dict(),
            "verdict_vs_kill": "PASS" if fl.flow_newflag_bp.median() >= KILL_BP else "KILL",
        }
    summ["mark_dispersion_same_cusip_same_date"] = mark_dispersion(h, tick)
    summ["cross_sponsor_marks"] = cross_sponsor(h, tick)
    summ["unchanged_quarterly_marks"] = unchanged_marks(h, tick)
    if len(nf):
        summ["newflag_mark_timing"] = {
            "share_mark_prev_below_90": round(float((nf.mark_prev < 90).mean()), 4),
            "share_mark_unchanged_at_flag": round(float(((nf.mark_now - nf.mark_prev).abs() < 1e-9).mean()), 4),
            "share_mark_fell_ge_5_at_flag": round(float(((nf.mark_now - nf.mark_prev) <= -5).mean()), 4)}
    summ["newflag_events"] = {"n": int(len(nf)), "distinct_cusips": int(nf.cusip.nunique()) if len(nf) else 0,
                              "mark_prev_median": float(nf.mark_prev.median()) if len(nf) else None,
                              "mark_now_median": float(nf.mark_now.median()) if len(nf) else None}
    (OUT / "b1_muni_summary.json").write_text(json.dumps(summ, indent=1, default=str))
    print(json.dumps(summ, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
