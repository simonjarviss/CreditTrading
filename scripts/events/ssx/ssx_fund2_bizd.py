"""A9: BDC index-tracker demand. BIZD's constituent adds, deletes and reweights per quarterly review, in days of ADV (zero trials).

    export QUANTT_ENV_FILE=/abs/path/config/.env     # R2 (CRSP MF holdings, CRSP dsf/headers); never printed
    python3 scripts/events/ssx/ssx_fund2_bizd.py

WHY THIS EXISTS
---------------
Idea A9: VanEck BIZD tracks the MVIS US Business Development Companies Index
(MVBDC). An index fund must trade its index's changes at the review, so a
quarterly review is a dated, forced flow in BDCs, which have no AP of their
own. The kill gate (brief, 2026-10-19) is two numbers: fewer than 30 events a
year, or a median implied trade below one day of the BDC's ADV, kills it.

DATA, AND WHY NOT N-PORT
------------------------
The brief suggested BIZD's N-PORT-P filings (live EDGAR). The R2 mirror holds
CRSP's mutual-fund holdings for BIZD (`crsp_q_mutualfunds.holdings`,
crsp_portno 1032741 from `portnomap`; MONTHLY report dates 2013-07..2025-11,
read 2026-10-19), which needs no EDGAR request and is monthly rather than
quarterly. It is used instead (coordinator note, 2026-10-19).

EVENT CLOCK
-----------
MarketVector reviews MVBDC quarterly [S: search summaries; marketvector.com
returns HTTP 403 to fetches]. Recent review results name implementation on
2025-12-19 and 2026-06-19 (third Fridays) [S]. So each review is bracketed by
the month-end snapshots before and after it: end-Feb -> end-Mar,
end-May -> end-Jun, end-Aug -> end-Sep, end-Nov -> end-Dec. A bracket also
contains a month of creation/redemption flow, which moves every holding by
the same proportion; that common factor g (median share-count change of the
continuing names) is removed before a reweight is counted.

WHAT IS COUNTED (per review bracket)
------------------------------------
* add: a CUSIP held after and not before; implied trade = value after.
* delete: held before and not after; implied trade = value before.
* reweight: |dshares - g * shares_before| * price_after, for continuing names;
  "large" when it is at least 10% of the position (a stated threshold, not
  fitted).
Implied trade in days of ADV: the BDC's mean CRSP dollar volume over the 20
sessions ending two sessions before the review's third Friday, for reviews
dated <= 2022-12-31 only (time holdout), from dsf rows < 2023. Counts run to
2025-11 (counts only).

No price change, return or P&L of any BDC is computed: values are BIZD's own
reported market values, used as position sizes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.events.ssx.ssx_fund2_common import OUT, CACHE, now_utc  # noqa: E402

BIZD_PORTNO = 1032741
HOLD_CACHE = CACHE / "bizd_crsp_mf_holdings.parquet"     # licensed rows: gitignored cache only
TIME_HOLDOUT = pd.Timestamp("2023-01-01")
LARGE = 0.10


def third_friday(y: int, m: int) -> pd.Timestamp:
    d = pd.Timestamp(y, m, 15)
    return d + pd.Timedelta(days=(4 - d.weekday()) % 7)


def load_holdings() -> pd.DataFrame:
    if not HOLD_CACHE.exists():
        from src.data.r2 import connect, r2_path, q
        con = connect()
        h = r2_path("crsp_q_mutualfunds", "holdings")
        d = q(con, f"""SELECT crsp_portno, report_dt, eff_dt, percent_tna, nbr_shares, market_val, security_name,
                       cusip, permno, ticker FROM read_parquet('{h}') WHERE crsp_portno = {BIZD_PORTNO}""")
        if d.empty:
            raise RuntimeError("CRSP MF holdings: no rows for BIZD's crsp_portno")
        d.to_parquet(HOLD_CACHE)
    d = pd.read_parquet(HOLD_CACHE)
    d["report_dt"] = pd.to_datetime(d["report_dt"])
    # equity positions only (cash and money-market lines have no permno)
    return d[d["permno"].notna() & d["nbr_shares"].notna() & (d["nbr_shares"] > 0)].copy()


def brackets(d: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    dates = sorted(d["report_dt"].unique())
    me = {(t.year, t.month): t for t in map(pd.Timestamp, dates)}
    out = []
    for (y, m), t in sorted(me.items()):
        if m in (3, 6, 9, 12):
            pm = (y, m - 1)
            if pm in me:
                out.append((me[pm], t, third_friday(y, m)))
    return out


def main() -> int:
    d = load_holdings()
    rows, ev = [], []
    for b, a, eff in brackets(d):
        B = d[d["report_dt"] == b].groupby("cusip").agg(sh=("nbr_shares", "sum"), mv=("market_val", "sum"),
                                                         permno=("permno", "first"), name=("security_name", "first"))
        A = d[d["report_dt"] == a].groupby("cusip").agg(sh=("nbr_shares", "sum"), mv=("market_val", "sum"),
                                                         permno=("permno", "first"), name=("security_name", "first"))
        cont = B.index.intersection(A.index)
        g = float(np.median(A.loc[cont, "sh"] / B.loc[cont, "sh"] - 1)) if len(cont) else np.nan
        adds, dels = A.index.difference(B.index), B.index.difference(A.index)
        for c in adds:
            ev.append({"review": eff.date(), "kind": "add", "permno": int(A.loc[c, "permno"]), "name": A.loc[c, "name"],
                       "trade_usd": float(A.loc[c, "mv"]), "frac_of_position": 1.0})
        for c in dels:
            ev.append({"review": eff.date(), "kind": "delete", "permno": int(B.loc[c, "permno"]), "name": B.loc[c, "name"],
                       "trade_usd": float(B.loc[c, "mv"]), "frac_of_position": 1.0})
        for c in cont:
            resid = A.loc[c, "sh"] - (1 + g) * B.loc[c, "sh"]
            frac = abs(resid) / B.loc[c, "sh"]
            px = A.loc[c, "mv"] / A.loc[c, "sh"]
            if frac >= LARGE:
                ev.append({"review": eff.date(), "kind": "reweight_ge10pct", "permno": int(A.loc[c, "permno"]),
                           "name": A.loc[c, "name"], "trade_usd": float(abs(resid) * px), "frac_of_position": float(frac)})
        rows.append({"before": b.date(), "after": a.date(), "review_third_friday": eff.date(), "n_before": len(B),
                     "n_after": len(A), "flow_g": g, "adds": len(adds), "deletes": len(dels),
                     "aum_equity_after_usd": float(A["mv"].sum())})
    R = pd.DataFrame(rows)
    E = pd.DataFrame(ev)
    # pre-event ADV, reviews <= 2022-12-31 only, dsf rows < 2023 (holdout sealed)
    fit = E[pd.to_datetime(E["review"]) < TIME_HOLDOUT].copy()
    from src.data.r2 import connect, r2_path, q
    con = connect()
    dsf = r2_path("crsp_a_stock", "dsf")
    perm = ",".join(str(int(p)) for p in sorted(fit["permno"].unique()))
    px = q(con, f"""SELECT permno, date, abs(prc) * vol AS dv FROM read_parquet('{dsf}')
                    WHERE permno IN ({perm}) AND date < DATE '2023-01-01' AND prc IS NOT NULL AND vol IS NOT NULL""")
    px["date"] = pd.to_datetime(px["date"])
    if px["date"].max() >= TIME_HOLDOUT:
        raise RuntimeError("a 2023+ dsf row was read")
    by = {p: g.sort_values("date") for p, g in px.groupby("permno")}
    adv = []
    for r in fit.itertuples(index=False):
        g_ = by.get(r.permno)
        if g_ is None:
            adv.append(np.nan)
            continue
        pre = g_[g_["date"] < pd.Timestamp(r.review)].tail(22).head(20)   # 20 sessions ending 2 before review
        adv.append(float(pre["dv"].mean()) if len(pre) >= 15 else np.nan)
    fit["adv_usd"] = adv
    fit["days_of_adv"] = fit["trade_usd"] / fit["adv_usd"]
    E = E.merge(fit[["review", "permno", "kind", "adv_usd", "days_of_adv"]], on=["review", "permno", "kind"], how="left")
    E.to_csv(CACHE / "a9_bizd_events_rows.csv", index=False)          # names + BIZD values: cache only
    R.to_csv(OUT / "a9_bizd_reviews.csv", index=False)
    E["year"] = pd.to_datetime(E["review"]).dt.year
    per_year = E.groupby(["year", "kind"]).size().unstack("kind").fillna(0).astype(int)
    per_year.to_csv(OUT / "a9_bizd_events_by_year.csv")
    f = fit.dropna(subset=["days_of_adv"])
    summ = {"built_utc": now_utc(), "source": f"CRSP MF holdings, crsp_portno {BIZD_PORTNO}, R2 mirror",
            "holdings_report_dates": [str(d["report_dt"].min().date()), str(d["report_dt"].max().date())],
            "review_brackets": int(len(R)),
            "events_total_by_kind": E["kind"].value_counts().to_dict(),
            "events_per_year_mean": float(E.groupby("year").size().mean()),
            "events_per_year": E.groupby("year").size().to_dict(),
            "adds_deletes_per_year": E[E["kind"].isin(["add", "delete"])].groupby("year").size().to_dict(),
            "distinct_bdcs_with_event_per_year": E.groupby("year")["permno"].nunique().to_dict(),
            "fit_events_with_adv": int(len(f)),
            "fit_median_days_of_adv_all": float(f["days_of_adv"].median()) if len(f) else None,
            "fit_median_days_of_adv_by_kind": f.groupby("kind")["days_of_adv"].median().to_dict(),
            "fit_share_ge_1_day": float((f["days_of_adv"] >= 1).mean()) if len(f) else None,
            "fit_median_trade_usd": float(f["trade_usd"].median()) if len(f) else None,
            "bizd_equity_aum_2022_12": float(R.loc[R["after"] == pd.Timestamp("2022-12-31").date(), "aum_equity_after_usd"].sum()),
            "bizd_equity_aum_latest": [str(R["after"].iloc[-1]), float(R["aum_equity_after_usd"].iloc[-1])]}
    (OUT / "a9_bizd_summary.json").write_text(json.dumps(summ, indent=1, default=str) + "\n")
    print(R.to_string(index=False))
    print(per_year.to_string())
    print(json.dumps(summ, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
