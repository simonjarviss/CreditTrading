"""Cross-check for merger_arb: the plain premium on the desk's own EDGAR deal list.

    python3 results/ideas/merger_arb/crosscheck_edgar.py [--stage-dir <data/events/merger_targets>]

WHY. The SDC result (explore.py) rests on SDC's dates and on its 'Friendly' mark. The October
EDGAR census (scripts/events/merger_arb_feasibility.py, staged with CRSP rows by
scripts/data/stage_crsp_merger_targets.py on 2026-10-20) is an independent list: a one-step
cash merger is in it because the target filed a merger proxy, which only an agreed deal
does. It is also the only free, live source, so it is what a shadow book would have to use.

THE ONE RULE THAT MAKES IT HONEST. The census sees a deal at its first proxy filing (`a0`),
not at the announcement. Entering earlier would condition on the deal surviving to its
proxy. So the decision is made at the first session AFTER `a0`, and everything else is as in
explore.py: eligible once at entry ($5, $1M average daily volume), exit when the target stops
trading or 252 sessions after entry, equal weights, flat under 5 deals, shift(2), gross.
The census has no withdrawal date, so a broken deal is held until it delists or the cap.

RETURNS are the legacy CRSP file's `ret`, with the separate delisting return `dlret` placed
on the session after the target's last row (in this file the payment is not in `ret`).
A merger delisting with no `dlret` is counted and earns nothing on that day.

ONLY THE 2001-2009 DEALS CAN BE USED. The staged list keeps `a0` for the 2001-09 extension
and not for the 2010-22 census, whose committed file has only the first deal filing (`d0`,
which can precede the proxy) and the LAST proxy filing (`a1`, known only in hindsight).
Neither is an honest entry date, so those deals are left out and counted. Rebuilding `a0`
for them means re-running the EDGAR census; that is the open item, and a live book needs it.
The SDC friendly book over the same sessions is printed beside the result.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ma_explore", HERE / "explore.py")
ma = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ma)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage-dir", type=Path, default=REPO / "data" / "events" / "merger_targets")
    a = ap.parse_args(argv)
    d = pd.read_csv(a.stage_dir / "deals.csv", low_memory=False, parse_dates=["ann", "a0", "a1"])
    d = d[(d["link_status"] == "linked")].copy()
    n_no_a0 = int(d["a0"].isna().sum())
    d = d[d["a0"].notna()].copy()
    d["permno"] = d["permno"].astype(int)
    x = pd.read_parquet(a.stage_dir / "crsp_dsf_targets.parquet", columns=["permno", "date", "ret", "prc", "vol"])
    x["prc"] = x["prc"].abs()                                   # the legacy file marks a bid/ask midpoint with a minus sign
    x["dollar_volume"] = x["prc"] * x["vol"]
    dl = pd.read_parquet(a.stage_dir / "crsp_delist_targets.parquet")
    sessions = pd.DatetimeIndex(sorted(x["date"].unique()))
    ret = x.pivot(index="date", columns="permno", values="ret").reindex(sessions)
    prc = x.pivot(index="date", columns="permno", values="prc").reindex(sessions)
    dv = x.pivot(index="date", columns="permno", values="dollar_volume").reindex(sessions)
    trading = prc.notna()
    R = ret.fillna(0.0)
    # the delisting return goes on the session after the target's last row
    last_row = x.groupby("permno")["date"].max()
    n_no_dlret = 0
    for r in dl.itertuples():
        if r.permno not in R.columns or r.permno not in last_row.index:
            continue
        i = sessions.searchsorted(last_row[r.permno], side="right")
        if abs((pd.Timestamp(r.dlstdt) - last_row[r.permno]).days) > 10 or i >= len(sessions):
            continue                                            # the staged rows stop before the delisting: nothing to place
        if pd.isna(r.dlret):
            n_no_dlret += int(r.dlstcd // 100 == 2)
            continue
        R.iat[i, R.columns.get_loc(r.permno)] = r.dlret
    rf = pd.read_parquet(ma.RF).set_index("date")["rf_daily"].reindex(sessions).ffill()
    mk = pd.read_parquet(ma.MKT)
    mkt_x = mk[mk["ticker"] == "SPY"].set_index("date")["ret_total"].reindex(sessions) - rf
    out = {"panel_last_date": str(sessions.max().date()), "merger_delistings_with_no_dlret": n_no_dlret,
           "deals_left_out_no_first_proxy_date": n_no_a0, "sources_used": sorted(d["source"].unique())}
    adv = dv.rolling(21, min_periods=10).mean()
    pnl_keep = {}
    for name, uni in (("one_step", "CASH_1STEP"), ("tender", "TENDER_CASH")):
        g = d[d["universe"] == uni]
        col = prc.columns.get_indexer(g["permno"])
        g, col = g[col >= 0], col[col >= 0]
        i0 = sessions.searchsorted(g["a0"].values, side="right")          # ALIGNMENT: first session strictly after the first proxy filing
        ok = i0 < len(sessions)
        j = np.where(ok, i0, 0)
        elig = ok & trading.to_numpy()[j, col] & (np.nan_to_num(prc.to_numpy()[j, col]) >= ma.MIN_PRICE) \
            & (np.nan_to_num(adv.to_numpy()[j, col]) >= ma.MIN_ADV)
        T = trading.to_numpy()
        last_trade = np.array([np.flatnonzero(T[:, c])[-1] for c in col])
        i1 = np.minimum(i0 + ma.MAX_HOLD - 1, last_trade)
        act = np.zeros(ret.shape, dtype=bool)
        for a_, b_, c_, e_ in zip(i0, i1, col, elig):
            if e_ and b_ >= a_:
                act[a_:b_ + 1, c_] = True
        H = ma.long_only(act, sessions, ret.columns)
        ev = harness.evaluate(H, R)
        first = pd.Series(act.sum(axis=1) >= ma.MIN_NAMES, index=sessions).idxmax()
        last_live = pd.Series(act.sum(axis=1) >= ma.MIN_NAMES, index=sessions)[::-1].idxmax()
        pnl = ev["pnl"].loc[first:last_live].iloc[harness.EXEC_LAG:]
        pnl_keep[name] = pnl
        xs = pnl - rf.reindex(pnl.index) * H.shift(harness.EXEC_LAG).abs().sum(axis=1).reindex(pnl.index).fillna(0.0)
        n_act = pd.Series(act.sum(axis=1), index=sessions).reindex(pnl.index)
        lag = (g["a0"] - g["ann"]).dt.days
        out[name] = {**explore.summarise(pnl), "deals": int(len(g)), "eligible": int(elig.sum()),
                     "live_per_day_median": float(n_act.median()), "flat_day_share": float((n_act < ma.MIN_NAMES).mean()),
                     "first_proxy_days_after_announcement_median": float(lag.median()),
                     "excess_over_bills": explore.stats(xs), "market": ma.market_fit(xs, mkt_x)}
        r = out[name]
        print(f"\n== EDGAR census, {name}: deals {r['deals']:,}, eligible {r['eligible']:,}, live a day (median) {r['live_per_day_median']:.0f}, "
              f"flat days {r['flat_day_share']:.1%}, first proxy {r['first_proxy_days_after_announcement_median']:.0f} days after the announcement (median)")
        print(explore.table({**r, "controls": {}}))
        e, m = r["excess_over_bills"], r["market"]
        print(f"over bills: {e['ann_ret']:.2%}/yr, vol {e['ann_vol']:.2%}, Sharpe {e['sharpe']:.2f}, max drawdown {e['max_drawdown']:.2%} | "
              f"beta {m['beta']:.2f}, alpha {m['alpha_per_year']:.2%}/yr (NW t {m['alpha_t_newey_west']:.2f})")
    print("merger delistings with no delisting return:", n_no_dlret, "| deals left out for want of a first-proxy date:", n_no_a0)
    # the SDC friendly book on the same sessions, from explore.py's own functions
    sd, sret, sprc, sdv, strading = ma.load()
    sp = ma.spells(sd, sret.index, sprc, sdv, strading)
    g = sp[(sp["tender"] == "No") & (sp["attitude"] == "Friendly")]
    Hs = ma.long_only(ma.active_matrix(g, sret.shape), sret.index, sret.columns)
    ps = harness.evaluate(Hs, sret.fillna(0.0))["pnl"]
    lo, hi = out["one_step"]["full"]["first"], out["one_step"]["full"]["last"]
    both = pd.DataFrame({"edgar": pnl_keep["one_step"], "sdc": ps}).loc[lo:hi].dropna()
    out["sdc_friendly_same_sessions"] = {"stats": explore.stats(both["sdc"]), "edgar_stats_same_rows": explore.stats(both["edgar"]),
                                         "daily_correlation": float(both.corr().iloc[0, 1])}
    s = out["sdc_friendly_same_sessions"]
    print(f"same sessions {lo}..{hi}: SDC friendly one-step Sharpe {s['stats']['sharpe']:.2f} ({s['stats']['ann_ret']:.2%}/yr); "
          f"EDGAR one-step Sharpe {s['edgar_stats_same_rows']['sharpe']:.2f} ({s['edgar_stats_same_rows']['ann_ret']:.2%}/yr); daily correlation {s['daily_correlation']:.2f}")
    (HERE / "crosscheck_edgar.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
