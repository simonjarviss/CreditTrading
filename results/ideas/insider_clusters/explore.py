"""Explore: clustered open-market insider buying, on the 2,000 largest US common stocks.

    python3 scripts/events/ssx/ssx_ins_fetch.py fetch && ... extract      # SEC Form 3/4/5 data sets (public)
    python3 scripts/events/ssx/ssx_ins_insider_census.py census           # writes d1_cluster_events.parquet
    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_equities.py --top 2000
    python3 results/ideas/insider_clusters/explore.py

THE EVENT was fixed on 2026-10-19, before any return existed, in
scripts/events/ssx/ssx_ins_insider_census.py: three or more distinct directors or officers,
on three or more original Form 4 filings, buying common stock on the open market within 30
days; one event per issuer per 90 days; clusters where every purchase is at one price on one
date (an offering or placement) are dropped. The event's date is the filing date of the
filing that completes the cluster. This script reads that file and changes nothing in it.

FIXED HERE BEFORE LOOKING
  known at      the first session AFTER the filing date. A Form 4 sent by 10 p.m. counts as
                filed that day, so the same evening is too early (the census card says so).
  match         the symbol as filed equals the CRSP ticker on that session, in the staged
                panel (ranks to 2,000 by the previous month-end's market value). No match,
                no event; the share matched is printed.
  book          long every matched stock for 21 sessions from that session (the literature's
                horizon is the month after), equal weights, half the book; short every other
                eligible stock equally, the other half. Eligible: in the panel that day and
                priced at $5 or more. A day with fewer than 5 cluster stocks is flat.
  convention    shift(2) on the canonical harness; gross; no cost modelled.

CONTROLS
  late          the same events 126 sessions late.
  losers        no insider data at all: long the tenth of eligible stocks with the worst
                trailing 21-session return, short the rest. Clusters bunch after sell-offs,
                so if this scores as well, the insider book is a reversal bet.
Also shown, labelled: the same book held 60 sessions (run alongside, not chosen from).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
PANEL, EVENTS = RES / "crsp_top2000_daily.parquet", RES / "sec_form345" / "d1_cluster_events.parquet"
HOLD, MIN_PRICE, MIN_NAMES, LATE = 21, 5.0, 5, 126


def book(live: pd.DataFrame, eligible: pd.DataFrame) -> pd.DataFrame:
    """+0.5 across live cluster stocks, -0.5 across the other eligible stocks; flat when thin."""
    lg = (live & eligible).astype(float)
    sh = (~live & eligible).astype(float)
    nl, ns = lg.sum(axis=1), sh.sum(axis=1)
    ok = (nl >= MIN_NAMES) & (ns > 0)
    return (lg.div(nl.where(ok), axis=0).mul(0.5) - sh.div(ns.where(ok), axis=0).mul(0.5)).fillna(0.0)


def main() -> int:
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    last = df["date"].max().date()
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc")
    dv = df.pivot(index="date", columns="permno", values="dollar_volume")
    sessions = ret.index
    ev = pd.read_parquet(EVENTS)
    ev = ev[~ev["single_price"]].copy()
    n_all = len(ev)
    # ALIGNMENT: t is the first session strictly after the filing date.
    i = sessions.searchsorted(ev["event_date"].values, side="right")
    ev = ev[i < len(sessions)].assign(t=sessions[i[i < len(sessions)]])
    assert (ev["t"] > ev["event_date"]).all()
    n_in_range = len(ev)
    tick = df[["date", "permno", "ticker"]].rename(columns={"date": "t", "ticker": "symbol"})
    m = ev.merge(tick, on=["t", "symbol"], how="inner")
    dup = m.duplicated(["t", "symbol"], keep=False)             # one symbol on two permnos that day: dropped, not chosen
    m = m[~dup].drop_duplicates(["t", "permno"])
    S = pd.DataFrame(False, index=sessions, columns=ret.columns)
    S.values[sessions.get_indexer(m["t"]), ret.columns.get_indexer(m["permno"])] = True

    def live_for(start: pd.DataFrame, hold: int) -> pd.DataFrame:
        return start.astype(float).rolling(hold, min_periods=1).max().fillna(0.0) > 0   # true for `hold` sessions from t

    eligible = prc.notna() & (prc >= MIN_PRICE)
    R = ret.fillna(0.0)
    H = book(live_for(S, HOLD), eligible)
    res_h = harness.evaluate(H, R)
    first = S.any(axis=1).idxmax()
    pnl = res_h["pnl"].loc[first:].iloc[HOLD + harness.EXEC_LAG:]
    run = lambda h: harness.evaluate(h, R)["pnl"].reindex(pnl.index)  # noqa: E731
    late = run(book(live_for(S.shift(LATE, fill_value=False), HOLD), eligible))
    r21 = ret.rolling(21, min_periods=21).sum().where(eligible)
    losers = run(book(r21.rank(axis=1, pct=True) <= 0.10, eligible))
    hold60 = run(book(live_for(S, 60), eligible))
    mkt = ret.where(eligible).mean(axis=1).reindex(pnl.index)
    beta = float(np.cov(pnl, mkt)[0, 1] / mkt.var())
    corr_losers = float(np.corrcoef(pnl, losers)[0, 1])
    # the part of the book the loser control does not explain
    b = float(np.cov(pnl, losers)[0, 1] / losers.var())
    resid = pnl - b * losers
    adv = dv.rolling(21, min_periods=10).mean()
    share = (H.clip(lower=0) / adv).where(H > 0).loc["2024-01-01":].stack()
    n_live = (H > 0).sum(axis=1).reindex(pnl.index)
    res = explore.summarise(pnl, controls={"events 126 sessions late": late, "losers, no insider data": losers,
                                           "held 60 sessions (shown, not chosen)": hold60,
                                           "book less its loading on the losers control": resid}, extra={
        "panel_last_date": str(last), "clean_clusters": int(n_all), "clusters_in_panel_dates": int(n_in_range),
        "clusters_matched": int(len(m)), "match_share": float(len(m) / n_in_range),
        "cluster_stocks_per_day_mean": float(n_live.mean()), "flat_day_share": float((n_live == 0).mean()),
        "turnover_per_year": float(res_h["turn"]), "beta_to_equal_weight_market": beta,
        "corr_with_losers_control": corr_losers, "loading_on_losers_control": b,
        "capacity_long_leg_2024_on": {f"pct_of_adv_at_{s // 10**6}M": {"median": float(share.median() * s * 100),
                                      "p95": float(share.quantile(0.95) * s * 100)} for s in (10**6, 5 * 10**6, 10**7)}})
    explore.write(HERE, res, pnl, title=f"Insider buying clusters, 21 sessions, long vs the rest; shift(2), gross; to {last}",
                  controls={"losers, no insider data": losers})
    print("panel to", last, "| clean clusters", n_all, "| matched", len(m), f"({res['match_share']:.0%})", "| cluster stocks a day",
          round(res["cluster_stocks_per_day_mean"], 1), "| flat days", f"{res['flat_day_share']:.0%}", "| turnover/yr", round(res["turnover_per_year"], 1),
          "| beta", round(beta, 3), "| corr with losers", round(corr_losers, 2))
    print(explore.table(res))
    print(res["capacity_long_leg_2024_on"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
