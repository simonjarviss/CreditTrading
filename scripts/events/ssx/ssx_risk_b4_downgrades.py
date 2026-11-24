"""B4 census: corporate downgrades (Moody's/Fitch Rule 17g-7 histories) and
N-PORT default flags mapped to the deployed TAXABLE CEFs' holdings. Zero trials.

WHY
---
A subtract-only flag would stop the discount z-score buying a taxable CEF
whose holdings have just been hit by a downgrade or default the NAV may not yet
mark. Before designing it, count how often it would bind and how much NAV it
would touch. The graveyard neighbour is `nport-trace-nav` (D7 infeasible: daily
TRACE covered 17-30% of HYG's weight, and the bonds that print are selected for
news), so this script also measures the rating panel's coverage of the funds'
credit weight -- the same question asked of a different event source.

KILL GATE (declared 2026-10-19 before this script first ran)
------------------------------------------------------------
KILL if the median point-in-time event-affected weight per fund-quarter is
below 10bp (B1's number, reused so the two cards are comparable), OR if the
17g-7 panel covers below 50% of the funds' CUSIP-identified credit weight.

DEFINITIONS
-----------
* Event: an issuer downgrade day = (cusip6, rating_action_date) with any
  instrument row is_dg=True, Corporate/Financial/Insurance, either agency;
  de-duplicated across agencies and instruments. IG->HY is the subset with
  is_ig_to_hy. S&P is NOT in the panel (data/agency_actions_17g7.parquet holds
  Moody's to 2023-12-15 and Fitch to 2025-06-30).
* Point in time: the fund's latest N-PORT whose FILING date is strictly before
  the event date (what a live flag could have known). "As-of" uses the latest
  REPORT date <= event date instead (not knowable live; shown to measure what
  the 60-day lag and quarterly snapshots cost).
* Affected weight: the fund's summed pctVal (percent of net assets) across all
  holdings sharing the event's cusip6, in bp; summed over distinct events in
  the calendar quarter.
* Window: events 2019-12-01 .. 2022-12-31 (every fund has a public snapshot by
  then; report dates <= 2022-12-31; the 2023 holdout is not touched).
* Defaults: N-PORT isDefault N -> Y between consecutive snapshots, as B1.

No return, P&L or price change of any fund is computed.

Reproduce (offline, after ssx_risk_nport.py):
    python3 scripts/events/ssx/ssx_risk_b4_downgrades.py
Output: results/events/ssx/ssx_risk/b4_fund_quarters.csv, b4_summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_risk"
OUT = REPO / "results" / "events" / "ssx" / "ssx_risk"
PANEL = REPO / "data" / "agency_actions_17g7.parquet"
TAXABLE = ("PDI", "PTY", "PDO", "PCN", "PHK", "PFN", "DSL", "HYT", "BIT", "JFR", "AWF")
EV_FROM, EV_TO = pd.Timestamp("2019-12-01"), pd.Timestamp("2022-12-31")
KILL_BP, KILL_COVER = 10.0, 0.50


def events(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel[panel.is_dg & panel.category.isin(["Corporate", "Financial", "Insurance"])]
    p = p[p.cusip6.fillna("").str.len() == 6]
    p = p[(p.rating_action_date >= EV_FROM) & (p.rating_action_date <= EV_TO)]
    # severity: into CCC+ or below (notch >= 17 on the panel's 1 = AAA scale) or a
    # drop of 3+ notches in one action. Chosen as "distress", not fitted: a
    # one-notch move inside IG is the bulk of is_dg rows and rarely moves a mark.
    p = p.assign(severe=(p.rating_notch >= 17) | ((p.rating_notch - p.prev_notch) >= 3))
    e = p.groupby(["cusip6", "rating_action_date"]).agg(agencies=("agency", lambda s: "+".join(sorted(set(s)))),
                                                        ig_to_hy=("is_ig_to_hy", "max"),
                                                        severe=("severe", "max")).reset_index()
    return e


def snapshot_index(h: pd.DataFrame) -> pd.DataFrame:
    x = h[h.ticker.isin(TAXABLE) & h.cusip.fillna("").str.match(r"^[0-9A-Z]{9}$") & (h.cusip != "000000000")].copy()
    x["cusip6"] = x.cusip.str[:6]
    return x.groupby(["ticker", "accession", "report_dt", "filing_date", "cusip6"]).pct_val.sum().reset_index()


def pick(snaps: pd.DataFrame, ticker: str, d: pd.Timestamp, mode: str):
    s = snaps[snaps.ticker == ticker]
    s = s[s.filing_date < d] if mode == "pit" else s[s.report_dt <= d]
    if s.empty:
        return None
    return s.sort_values("report_dt" if mode == "asof" else "filing_date").accession.iloc[-1]


def main() -> int:
    panel = pd.read_parquet(PANEL)
    ends = panel.groupby("agency").rating_action_date.max().astype(str).to_dict()
    h = pd.read_parquet(CACHE / "nport_holdings_ssx_risk.parquet")
    if h.report_dt.max() > pd.Timestamp("2022-12-31"):
        raise AssertionError("2023+ holdings reached B4")
    agg = snapshot_index(h)
    snaps = agg[["ticker", "accession", "report_dt", "filing_date"]].drop_duplicates()
    by_acc = {a: g.set_index("cusip6").pct_val for a, g in agg.groupby("accession")}
    ev = events(panel)

    # coverage: share of each fund's CUSIP-identified positive weight whose issuer
    # appears anywhere in the panel (any action, any date up to the window end)
    rated6 = set(panel.loc[(panel.rating_action_date <= EV_TO) & (panel.cusip6.fillna("").str.len() == 6), "cusip6"])
    cov_rows = []
    for t in TAXABLE:
        ht = h[h.ticker == t]
        pos = ht[ht.pct_val > 0]
        credit = pos[pos.asset_cat.isin(["DBT", "LON", "ABS-MBS", "ABS-CBDO", "ABS-O", "ABS-APCP"])]
        okc = credit.cusip.fillna("").str.match(r"^[0-9A-Z]{9}$") & (credit.cusip != "000000000")
        inrated = okc & credit.cusip.str[:6].isin(rated6)
        n = ht.report_dt.nunique()
        cov_rows.append({"ticker": t, "credit_pct_per_q": credit.pct_val.sum() / n,
                         "cusip_identified_share": credit.loc[okc, "pct_val"].sum() / credit.pct_val.sum(),
                         "panel_issuer_share_of_identified": credit.loc[inrated, "pct_val"].sum() / max(credit.loc[okc, "pct_val"].sum(), 1e-12),
                         "panel_issuer_share_of_credit": credit.loc[inrated, "pct_val"].sum() / credit.pct_val.sum()})
    cov = pd.DataFrame(cov_rows)

    rows = []
    for t in TAXABLE:
        for mode in ("pit", "asof"):
            hits = []
            for r in ev.itertuples():
                acc = pick(snaps, t, r.rating_action_date, mode)
                if acc is None:
                    continue
                w = by_acc[acc].get(r.cusip6)
                if w is not None and w > 0:
                    hits.append({"q": r.rating_action_date.to_period("Q"), "cusip6": r.cusip6, "bp": 100 * w,
                                 "ig_to_hy": bool(r.ig_to_hy), "severe": bool(r.severe)})
            hd = pd.DataFrame(hits, columns=["q", "cusip6", "bp", "ig_to_hy", "severe"])
            qs = pd.period_range(EV_FROM.to_period("Q"), EV_TO.to_period("Q"), freq="Q")
            for q in qs:
                g = hd[hd.q == q].drop_duplicates("cusip6")     # one issuer counted once a quarter
                rows.append({"ticker": t, "mode": mode, "quarter": str(q), "n_issuers": len(g),
                             "affected_bp": g.bp.sum(), "n_ig_to_hy": int(g.ig_to_hy.sum()),
                             "ig_to_hy_bp": g.loc[g.ig_to_hy, "bp"].sum(),
                             "n_severe": int(g.severe.sum()), "severe_bp": g.loc[g.severe, "bp"].sum()})
    fq = pd.DataFrame(rows)

    # default flags (flow), taxable funds
    dflt = []
    for t in TAXABLE:
        ht = h[(h.ticker == t) & (h.cusip != "000000000") & h.cusip.notna()]
        # non-debt rows carry no isDefault (None): a holding is flagged only on an explicit "Y"
        piv = ht.groupby(["report_dt", "cusip"]).agg(d=("is_default", lambda s: "Y" if (s == "Y").any() else "N"),
                                                     pct=("pct_val", "sum")).reset_index()
        ds = sorted(piv.report_dt.unique())
        for d0, d1 in zip(ds[:-1], ds[1:]):
            a = piv[piv.report_dt == d0].set_index("cusip")
            b = piv[piv.report_dt == d1].set_index("cusip")
            j = b.join(a, rsuffix="_p", how="inner")
            nf = j[(j.d == "Y") & (j.d_p != "Y")]
            dflt.append({"ticker": t, "report_dt": pd.Timestamp(d1).date(), "n_new_default": len(nf),
                         "new_default_bp": 100 * nf.pct.sum()})
    dd = pd.DataFrame(dflt)

    OUT.mkdir(parents=True, exist_ok=True)
    fq.to_csv(OUT / "b4_fund_quarters.csv", index=False)
    cov.to_csv(OUT / "b4_rating_panel_coverage.csv", index=False)
    dd.to_csv(OUT / "b4_new_default_flags.csv", index=False)

    def s(mode):
        f = fq[fq["mode"] == mode]
        return {"fund_quarters": int(len(f)),
                "events_per_fund_quarter_median": float(f.n_issuers.median()),
                "events_per_fund_quarter_mean": float(f.n_issuers.mean()),
                "affected_bp_median": float(f.affected_bp.median()),
                "affected_bp_mean": float(f.affected_bp.mean()),
                "affected_bp_p90": float(f.affected_bp.quantile(0.9)),
                "share_fq_ge_kill": float((f.affected_bp >= KILL_BP).mean()),
                "ig_to_hy_bp_median": float(f.ig_to_hy_bp.median()),
                "share_fq_any_ig_to_hy": float((f.n_ig_to_hy > 0).mean()),
                "severe_bp_median": float(f.severe_bp.median()), "severe_bp_mean": float(f.severe_bp.mean()),
                "share_fq_severe_ge_kill": float((f.severe_bp >= KILL_BP).mean()),
                "share_fq_any_severe": float((f.n_severe > 0).mean()),
                "per_fund_affected_bp_median": f.groupby("ticker").affected_bp.median().round(1).to_dict(),
                "per_quarter_affected_bp_median": f.groupby("quarter").affected_bp.median().round(1).to_dict(),
                "pairs_per_quarter_total_median": float(f.groupby("quarter").n_issuers.sum().median())}
    cover_med = float(cov.panel_issuer_share_of_credit.median())
    summ = {"panel_last_dates": ends, "events_window": [str(EV_FROM.date()), str(EV_TO.date())],
            "issuer_downgrade_days_in_window": int(len(ev)), "of_which_ig_to_hy": int(ev.ig_to_hy.sum()),
            "of_which_severe": int(ev.severe.sum()),
            "pit": s("pit"), "asof": s("asof"),
            "coverage": cov.round(4).to_dict(orient="records"),
            "coverage_panel_share_of_credit_median": cover_med,
            "new_default_flags": {"fund_quarters": int(len(dd)), "median_bp": float(dd.new_default_bp.median()),
                                  "mean_bp": float(dd.new_default_bp.mean()),
                                  "p90_bp": float(dd.new_default_bp.quantile(0.9)),
                                  "share_fq_any": float((dd.n_new_default > 0).mean())},
            "kill_bp": KILL_BP, "kill_cover": KILL_COVER}
    pit_med = summ["pit"]["affected_bp_median"]
    summ["verdict"] = ("KILL" if (pit_med < KILL_BP or cover_med < KILL_COVER) else "PASS")
    summ["verdict_legs"] = {"weight_leg": "pass" if pit_med >= KILL_BP else "kill",
                            "coverage_leg": "pass" if cover_med >= KILL_COVER else "kill"}
    (OUT / "b4_summary.json").write_text(json.dumps(summ, indent=1, default=str))
    print(json.dumps({k: v for k, v in summ.items() if k != "coverage"}, indent=1, default=str))
    print(cov.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
