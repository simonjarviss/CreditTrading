"""Explore: post-earnings-announcement drift on the 1,500 largest US common stocks.

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_equities.py --top 2000
    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_ibes_surprises.py
    python3 results/ideas/pead_wide/explore.py

FIXED BEFORE LOOKING
  event         a US quarterly EPS announcement in IBES with a surprise score
                (actual less the consensus before the release, over the estimates' spread).
  known at      the session of the announcement if its time is before 16:00 New York; the
                NEXT session if it is at or after 16:00, or if the time is the 00:00
                placeholder, or if the date is not a session. Call that session t.
  signal at t   the stock's latest surprise score, for 40 sessions from t (the card said 20
                to 60; 40 is the middle and was not searched).
  book          among stocks with a live signal, ranked in the top 1,500 by the previous
                month-end's market value and priced at $5 or more: long the top tenth by
                surprise, short the bottom tenth, equal weights, unit gross. A day with
                fewer than 50 such stocks is flat.
  convention    shift(2) on the canonical harness: decided at t, filled at t+1's close,
                earns t+2. So the announcement day's own move is never earned.
Gross only; no cost is modelled (team lead, 2026-11-09).

CONTROLS: (1) the same surprise 126 sessions late (sessions 127 to 166 after the release),
where under-reaction to THIS release should be gone; (2) the two size halves, ranks 1 to 500
and 501 to 1,500, because the card expects the drift to be weaker in large stocks.

A held stock with no row has stopped trading; CRSP puts the delisting return on its last
row, so afterwards its return is zero, not missing. Those name-days are counted.
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
PANEL, EVENTS = RES / "crsp_top2000_daily.parquet", RES / "ibes_eps_surprises.parquet"
TRADE_RANK, MIN_PRICE, HOLD, TAIL, MIN_NAMES, STALE = 1500, 5.0, 40, 0.10, 50, 126


def known_session(ev: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.Series:
    """The first session at whose close the release is public. ALIGNMENT: a release before
    16:00 on a session is known at that session's close; anything else at the next one."""
    d = pd.to_datetime(ev["anndats"]).values
    secs = ev["anntims"].map(lambda x: x.hour * 3600 + x.minute * 60 + x.second).values
    late = ev["time_is_placeholder"].values | (secs >= 16 * 3600)
    i = np.where(late, sessions.searchsorted(d, side="right"), sessions.searchsorted(d, side="left"))
    out = pd.Series(pd.NaT, index=ev.index, dtype="datetime64[ns]")
    ok = i < len(sessions)
    out[ok] = sessions[i[ok]]
    assert (out[ok].values >= d[ok]).all()                       # never known before its own date
    return out


def book(sig: pd.DataFrame) -> pd.DataFrame:
    n = sig.notna().sum(axis=1)
    pct = sig.rank(axis=1, pct=True)
    w = (pct > 1 - TAIL).astype(float) - (pct <= TAIL).astype(float)
    w = w.where(sig.notna(), 0.0)
    w[n < MIN_NAMES] = 0.0
    gross = w.abs().sum(axis=1)
    return w.div(gross.where(gross > 0), axis=0).fillna(0.0)    # a day with no book is flat


def main() -> int:
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    last = df["date"].max().date()
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc")
    rank = df.pivot(index="date", columns="permno", values="cap_rank")
    dv = df.pivot(index="date", columns="permno", values="dollar_volume")
    ev = pd.read_parquet(EVENTS)
    ev = ev[ev["permno"].isin(ret.columns)].copy()
    ev["t"] = known_session(ev, ret.index)
    ev = ev.dropna(subset=["t"]).sort_values(["t", "anndats"])
    ev = ev.drop_duplicates(["t", "permno"], keep="last")        # two releases known the same session: the later one
    S = ev.pivot(index="t", columns="permno", values="suescore").reindex(index=ret.index, columns=ret.columns)
    live = S.ffill(limit=HOLD - 1)                               # the latest surprise, for HOLD sessions from t
    ok = (rank <= TRADE_RANK) & (prc >= MIN_PRICE)
    sig = live.where(ok)
    H = book(sig)
    R = ret.fillna(0.0)
    held = H.shift(harness.EXEC_LAG).fillna(0.0) != 0
    gone = int((held & ret.isna()).sum().sum())
    res_h = harness.evaluate(H, R)
    first = S.notna().any(axis=1).idxmax()
    pnl = res_h["pnl"].loc[first:].iloc[HOLD + harness.EXEC_LAG:]
    stale = harness.evaluate(book(S.shift(STALE).ffill(limit=HOLD - 1).where(ok)), R)["pnl"].reindex(pnl.index)
    big = harness.evaluate(book(live.where(ok & (rank <= 500))), R)["pnl"].reindex(pnl.index)
    small = harness.evaluate(book(live.where(ok & (rank > 500))), R)["pnl"].reindex(pnl.index)
    mkt = ret.where(rank <= TRADE_RANK).mean(axis=1).reindex(pnl.index)
    beta = float(np.cov(pnl, mkt)[0, 1] / mkt.var())
    vol = mkt.rolling(21).std().shift(harness.EXEC_LAG)
    hi = vol > vol.median()
    adv = dv.rolling(21, min_periods=10).mean()
    share = (H.abs() / adv).replace([np.inf, -np.inf], np.nan).loc["2024-01-01":]
    nz = share.where(H.loc["2024-01-01":] != 0).stack()
    # the two legs, each against the equal-weighted market, to see where the spread comes from
    long_leg = harness.evaluate(H.clip(lower=0) * 2, R)["pnl"].reindex(pnl.index) - mkt
    short_leg = harness.evaluate(H.clip(upper=0) * 2, R)["pnl"].reindex(pnl.index) + mkt
    res = explore.summarise(pnl, controls={"surprise 126 sessions late": stale, "ranks 1-500 only": big,
                                           "ranks 501-1500 only": small}, extra={
        "panel_last_date": str(last), "events_last_date": str(pd.to_datetime(ev["anndats"]).max().date()),
        "events_used": int(len(ev)), "names_per_day_mean": float((H != 0).sum(axis=1).loc[pnl.index].mean()),
        "turnover_per_year": float(res_h["turn"]), "beta_to_equal_weight_market": beta,
        "held_name_days_with_no_row": gone,
        "legs_vs_equal_weight_market": {"long": explore.stats(long_leg), "short": explore.stats(short_leg)},
        "regimes": {"market vol above median": explore.stats(pnl[hi.reindex(pnl.index).fillna(False)]),
                    "market vol below median": explore.stats(pnl[~hi.reindex(pnl.index).fillna(True)])},
        "capacity_2024_on": {f"position_pct_of_adv_at_{s // 10**6}M": {"median": float(nz.median() * s * 100),
                             "p95": float(nz.quantile(0.95) * s * 100)} for s in (10**6, 5 * 10**6, 10**7)}})
    explore.write(HERE, res, pnl, title=f"Earnings drift, top 1,500 US stocks, 40 sessions; shift(2), gross, unit gross; to {last}",
                  controls={"surprise 126 sessions late": stale})
    print("panel to", last, "| events", len(ev), "| names a day", round(res["names_per_day_mean"]),
          "| turnover/yr", round(res["turnover_per_year"], 1), "| beta", round(beta, 3), "| held name-days with no row", gone)
    print(explore.table(res))
    for grp in ("legs_vs_equal_weight_market", "regimes"):
        for k, v in res[grp].items():
            print(grp, k, "Sharpe", round(v["sharpe"], 2), "ret/yr", f"{v['ann_ret']:.2%}", "n", v["n_days"])
    print(res["capacity_2024_on"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
