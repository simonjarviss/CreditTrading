"""Explore: fading the closing footprint of leveraged ETFs, on daily data.

    QUANTT_ENV_FILE=<env> python3 results/ideas/levered_etf_reversal/stage.py
    python3 results/ideas/levered_etf_reversal/mapping.py
    python3 results/ideas/levered_etf_reversal/explore.py

WHY: a daily leveraged or inverse fund must trade b(b-1) x assets x the day's return in its
underlying near the close, in the direction of the move, whatever b's sign. If that forced
flow is large against the underlying's volume the close is pushed too far and some should
come back. The team lead asked on 2026-11-16 for niche event-driven ETF ideas that large
money cannot use; this is the one where the "event" is a mechanical, computable order.
The desk fills at the NEXT close, so only a reversal that continues AFTER t+1's close can
be traded; the t to t+1 part is reported as information and is not in any book.

FIXED BEFORE ANY FORWARD RETURN WAS READ (2026-11-16). Read first: the fund-to-underlying
fit (mapping.py, same-day returns only), event counts, and the distribution of the flow
share by year (index group: median about 1%, 90th percentile 9-16% of the underlying ETF's
dollar volume every year since 2008; single stocks: nothing above 0.1% before 2024, 90th
percentile about 1% in 2024-25, 123 stock-days at 5% or more, 91 of them one stock).
  FUNDS     pairs.parquet from mapping.py. SINGLE: every multiple. INDEX: only -3, -2, -1, 2,
            3 (a plain fund with beta 1.25-1.5 to a sector ETF is not a leveraged fund; the
            first listing showed about a hundred of those). Dead funds are in (CRSP).
  UNDERLYINGS  SINGLE: the mapped stocks. INDEX: mapping.INDEX_UNDERLYINGS less BROAD (SPY,
            QQQ, DIA: not small or narrow). Eligible on day t if its median dollar volume
            over the 63 sessions before t is $20M or more, it closed at $5 or more on t-1,
            and it traded on t.
  FLOW      k[t] = sum over the underlying's funds of b(b-1) x shares outstanding[t-1] x
            price[t-1] (CRSP; b is that calendar year's multiple). flow share S[t] =
            k[t] x |return[t]| / dollar volume[t] of the underlying. Everything is known at
            t's close. CRSP's ETF share counts move monthly for most NYSE Arca funds and
            daily for the Nasdaq-listed ones, so assets can be up to a month stale in shares.
  EVENT     S >= 10% (INDEX) or S >= 1% (SINGLE). The two levels are about the pooled 90th
            percentile of each group, read from the flow-share distribution above, not from
            returns. They differ because an index fund's flow lands in the index's stocks,
            whose volume is far larger than the sector ETF's own: the INDEX share is
            overstated by an unknown, underlying-specific factor and only ranks days.
  TRADE     fade: position -sign(return[t]) in the underlying, 10% of the book per event,
            decided at t's close, filled at t+1's close, held two sessions (earns t+2 and
            t+3), hedged dollar for dollar with SPY. Gross in underlyings capped at 100%
            (all positions scaled on a day that would exceed it).
  CONTROLS  BIG day = |return[t]| at or above the underlying's own 90th percentile of
            |return| over the 252 sessions before t.
            A  same kind of day, little or no forced flow: BIG days in the same group's
               underlyings with S under a quarter of the event level (under 2.5% / 0.25%),
               including days before any fund existed. Traded the same way.
            B  no leveraged fund: SINGLE, BIG days in stocks of the largest-1,000 set that
               never have a mapped fund; INDEX, BIG days in listed candidates with no fund
               alive that day (a subset of A; there is no cleaner one, most sectors have a
               fund and unlisted ETFs may be twins of listed ones).
            T-BIG  events that are also BIG days, the like-for-like row against A and B.
  DOSE      among BIG days with a fund alive, mean fade return by flow-share bucket.
  EXPECTED  T positive over t+2..t+3 and above A and B; larger in higher buckets and in
            years with more leveraged assets. If A or B score as well, it is the ordinary
            reversal after a large move and not the funds.
  PER EVENT (no daily rebalancing): the signed buy-and-hold return less SPY's over t+1
            (untradable here), t+2..t+3 (the trade), t+3..t+4 (one more day's skip) and
            t+4..t+6; t-statistics on the daily mean across events.
  DESCRIPTIVE ONLY: turnover, dollar volume, price and closing bid-ask spread of what is held.
Gross; no cost is modelled. CRSP ends 2025-12-31. Writes results.json beside this file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapping import INDEX_UNDERLYINGS  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
assert harness.EXEC_LAG == 2
HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
OUT = RES / "levered_etf_reversal"
BROAD = {"SPY", "QQQ", "DIA"}
INDEX_MULTIPLES = {-3.0, -2.0, -1.0, 2.0, 3.0}
EVENT_S = {"index": 0.10, "single": 0.01}
MIN_ADV, MIN_PRICE, UNIT, HOLD = 20e6, 5.0, 0.10, 2
BUCKETS = {"index": (0.0, 0.025, 0.10, 0.25, np.inf), "single": (0.0, 0.0025, 0.01, 0.025, np.inf)}
WINDOWS = {"t+1 (untradable)": (1, 1), "t+2..t+3 (the trade)": (2, 3), "t+3..t+4 (one more skip day)": (3, 4), "t+4..t+6": (4, 6)}


def window_ret(R: pd.DataFrame, a: int, b: int) -> pd.DataFrame:
    """Buy-and-hold return over sessions t+a..t+b, placed on row t. NaN if any day is missing."""
    out = None
    for h in range(a, b + 1):
        step = 1.0 + R.shift(-h)
        out = step if out is None else out * step
    return out - 1.0


def panel(kind: str, etf: pd.DataFrame, pairs: pd.DataFrame, sessions: pd.DatetimeIndex) -> dict:
    """Wide frames (sessions x underlyings) for one group: return, dollar volume, price,
    spread, k (b(b-1) x lagged fund assets, 0 where no fund is alive), funds alive."""
    f = etf.merge(pairs[["fund", "year", "under", "lev"]], left_on=["permno", "year"], right_on=["fund", "year"])
    f["k"] = f["lev"] * (f["lev"] - 1.0) * f["aum_lag"]            # aum_lag is t-1: no same-day asset figure is used
    f = f.dropna(subset=["k"])
    k = f.groupby(["date", "under"])["k"].sum().unstack()
    aum = f.groupby(["date", "under"])["aum_lag"].sum().unstack()
    if kind == "index":
        last = etf[etf["date"] == sessions[-1]].set_index("ticker")["permno"]
        ids = [int(last[t]) for t in INDEX_UNDERLYINGS if t not in BROAD]
        u = etf[etf["permno"].isin(ids)]
        ever = set(k.columns) & set(ids)
    else:
        u = pd.read_parquet(RES / "crsp_top4500_daily.parquet", columns=["permno", "date", "ret", "prc", "dollar_volume", "cap_rank"])
        u["date"] = pd.to_datetime(u["date"])
        u = u[u["date"] >= "2021-01-01"]
        ids = u.loc[u["cap_rank"] <= 1000, "permno"].unique()
        u = u[u["permno"].isin(ids)].assign(prc=lambda d: d["prc"].abs())
        q = pd.read_parquet(OUT / "stock_quotes.parquet", columns=["permno", "date", "bid", "ask"])
        q["date"] = pd.to_datetime(q["date"])
        u = u.merge(q, on=["permno", "date"], how="left")
        sessions = sessions[sessions >= "2021-01-01"]
        ever = set(k.columns) & set(ids)
    wide = lambda c: u.pivot(index="date", columns="permno", values=c).reindex(sessions)  # noqa: E731
    R, DV, PX = wide("ret"), wide("dollar_volume"), wide("prc")
    mid = (wide("bid") + wide("ask")) / 2.0
    SPR = ((wide("ask") - wide("bid")) / mid).where(mid > 0)
    K = k.reindex(index=sessions, columns=R.columns).fillna(0.0)   # no fund alive is a fact (zero forced flow), not a gap
    A = aum.reindex(index=sessions, columns=R.columns).fillna(0.0)
    return {"R": R, "DV": DV, "PX": PX, "SPR": SPR, "K": K, "AUM": A, "ever": sorted(ever)}


def clustered(x: pd.DataFrame) -> dict:
    """Event returns (sessions x names, NaN where no event) -> mean per event and a t on the daily means."""
    v = x.stack()
    if len(v) == 0:
        return {"events": 0}
    daily = x.mean(axis=1).dropna()
    return {"events": int(len(v)), "days": int(len(daily)), "mean_bp": float(v.mean() * 1e4), "median_bp": float(v.median() * 1e4),
            "hit": float((v > 0).mean()), "t_daily_mean": float(daily.mean() / daily.std() * np.sqrt(len(daily))) if len(daily) > 2 else None}


def book(E: pd.DataFrame, R: pd.DataFrame, spy: pd.Series, hedge: bool = True) -> tuple[pd.Series, dict]:
    """E = -sign(return) on event rows, 0 elsewhere. Weights decided at t and still wanted
    at t+1 (two sessions held); harness.evaluate applies the two-session lag."""
    H = sum(E.shift(h).fillna(0.0) for h in range(HOLD)) * UNIT
    g = H.abs().sum(axis=1)
    H = H.div(g.clip(lower=1.0), axis=0)                           # scale only on days above 100% gross
    Rf = R.copy()
    held = harness.held(H) != 0
    miss = int((held & Rf.isna()).sum().sum())
    Rf = Rf.where(~(held & Rf.isna()), 0.0)                        # counted and reported, as net_cash did
    H["SPY"], Rf["SPY"] = (-H.sum(axis=1) if hedge else 0.0), spy
    # alignment: an event decided at t must first earn on t+2
    t0 = E.abs().sum(axis=1).to_numpy().nonzero()[0]
    if len(t0):
        hh = harness.held(H).drop(columns="SPY").abs().sum(axis=1).to_numpy()
        assert hh[: t0[0] + 2].sum() == 0 and hh[t0[0] + 2] > 0, "an event earns before t+2"
    res = harness.evaluate(H, Rf)
    return res["pnl"].iloc[harness.EXEC_LAG:], {"turnover_per_year": float(res["turn"]), "mean_gross": float(g.clip(upper=1.0).mean()),
                                                 "days_scaled": int((g > 1.0).sum()), "held_name_days_without_return": miss}


def run(kind: str, P: dict, spy: pd.Series, start: str) -> dict:
    R, DV, PX, K = (P[x].loc[start:] for x in ("R", "DV", "PX", "K"))
    full = P["R"]
    # everything below is dated t or earlier; the shift(1) calls make the trailing statistics strictly before t
    adv = P["DV"].rolling(63, min_periods=40).median().shift(1).loc[start:]
    q90 = full.abs().rolling(252, min_periods=126).quantile(0.90).shift(1).loc[start:]
    elig = (adv >= MIN_ADV) & (P["PX"].shift(1).loc[start:] >= MIN_PRICE) & (DV > 0) & R.notna()
    S = (K * R.abs() / DV).where(elig)
    big = elig & (R.abs() >= q90) & (R != 0)
    fade = -np.sign(R)
    T = elig & (S >= EVENT_S[kind]) & (R != 0)
    lo = S < EVENT_S[kind] / 4.0
    ever = R.columns.isin(P["ever"])
    if kind == "index":
        sets = {"T (events)": T, "T-BIG": T & big, "A (big move, little or no flow)": big & lo, "B (big move, no fund alive)": big & (K == 0)}
    else:
        sets = {"T (events)": T, "T-BIG": T & big, "A (big move, little or no flow, same stocks)": (big & lo).loc[:, ever],
                "B (big move, stocks with no fund ever)": big.loc[:, ~ever]}
    spy_ = spy.loc[start:]
    out = {"first": str(R.index[0].date()), "last": str(R.index[-1].date()), "underlyings_ever_with_a_fund": int(ever.sum()),
           "fixed": {"event_flow_share": EVENT_S[kind], "min_adv": MIN_ADV, "min_price": MIN_PRICE, "unit": UNIT, "hold": HOLD}}
    wr = {w: window_ret(R, a, b).sub(window_ret(spy_.to_frame("s"), a, b)["s"], axis=0) * fade for w, (a, b) in WINDOWS.items()}
    raw = window_ret(R, 2, 3) * fade
    pnl = {}
    for name, M in sets.items():
        M = M.reindex(columns=R.columns, fill_value=False)
        E = fade.where(M, 0.0).fillna(0.0)
        p, info = book(E, R, spy_)
        pnl[name] = p
        m = M.to_numpy()
        ev = {w: clustered(x.where(M)) for w, x in wr.items()}
        ev["t+2..t+3, not hedged"] = clustered(raw.where(M))
        nxt_spr = P["SPR"].shift(-1).loc[start:].to_numpy()[m]           # the spread on the fill day (descriptive)
        liq = {"events": int(m.sum()), "underlyings": int(M.any().sum()),
               "median_dollar_volume": float(np.nanmedian(DV.to_numpy()[m])) if m.any() else None,
               "median_price": float(np.nanmedian(PX.to_numpy()[m])) if m.any() else None,
               "median_abs_move": float(np.nanmedian(R.abs().to_numpy()[m])) if m.any() else None,
               "median_flow_share": float(np.nanmedian(S.to_numpy()[m])) if m.any() else None,
               "median_closing_spread_bp": float(np.nanmedian(nxt_spr) * 1e4) if m.any() and np.isfinite(nxt_spr).any() else None,
               "p90_closing_spread_bp": float(np.nanquantile(nxt_spr, 0.9) * 1e4) if m.any() and np.isfinite(nxt_spr).any() else None}
        by_year = {int(y): clustered(g) for y, g in wr["t+2..t+3 (the trade)"].where(M).groupby(R.index.year)}
        out[name] = {**info, **liq, "per_event": ev, "per_event_by_year": by_year}
    head = pnl["T (events)"]
    out["book"] = explore.summarise(head, controls={k: v for k, v in pnl.items() if k != "T (events)"})
    p_un, _ = book(fade.where(sets["T (events)"], 0.0).fillna(0.0), R, spy_, hedge=False)
    out["book_not_hedged"] = explore.stats(p_un)
    for name in list(pnl)[1:]:
        d = (head - pnl[name]).dropna()
        out[f"T less {name}"] = explore.stats(d)
    alive = big & (K > 0)
    b = BUCKETS[kind]
    out["dose"] = {f"{b[i]:.2%} to {b[i + 1]:.2%}": {w: clustered(wr[w].where(alive & (S >= b[i]) & (S < b[i + 1]))) for w in ("t+1 (untradable)", "t+2..t+3 (the trade)")}
                   for i in range(len(b) - 1)}
    yr = R.index.year
    out["assets_by_year"] = {int(y): {"mean_leveraged_assets_usd": float(P["AUM"].loc[start:].sum(axis=1)[yr == y].mean()),
                                      "underlyings_with_a_fund": int((K[yr == y] > 0).any().sum()),
                                      "events": int(T[yr == y].sum().sum())} for y in sorted(set(yr))}
    # print
    print(f"\n================ {kind.upper()} {out['first']} to {out['last']} ================")
    for name in sets:
        o = out[name]
        print(f"\n-- {name}: {o['events']} events in {o['underlyings']} underlyings; turnover {o['turnover_per_year']:.0f}/yr, mean gross {o['mean_gross']:.2f}, "
              f"days scaled {o['days_scaled']}; median $vol ${(o['median_dollar_volume'] or 0) / 1e6:,.0f}M, price ${o['median_price'] or 0:,.0f}, |move| {(o['median_abs_move'] or 0):.2%}, "
              f"flow share {(o['median_flow_share'] or 0):.2%}, closing spread median {o['median_closing_spread_bp']} bp / p90 {o['p90_closing_spread_bp']} bp; no-return held days {o['held_name_days_without_return']}")
        for w, e in o["per_event"].items():
            if e["events"]:
                print(f"     {w:32s} n {e['events']:6d}  mean {e['mean_bp']:7.1f} bp  median {e['median_bp']:7.1f}  hit {e['hit']:.1%}  t {e['t_daily_mean'] if e['t_daily_mean'] is None else round(e['t_daily_mean'], 2)}")
    print("\nBOOK: T (events), hedged with SPY"); print(explore.table(out["book"]))
    s = out["book_not_hedged"]; print(f"not hedged: SR {s['sharpe']:.2f} (t {s['t']:.2f}) {s['ann_ret']:.2%} / {s['ann_vol']:.2%}")
    for name in list(pnl)[1:]:
        s = out[f"T less {name}"]; print(f"T less {name}: SR {s['sharpe']:.2f} (t {s['t']:.2f}), {s['ann_ret']:.2%} a year")
    print("\nDOSE (BIG days with a fund alive), fade less SPY:")
    for bk, o in out["dose"].items():
        print("  ", bk, {w: (e.get("events"), None if not e.get("events") else round(e["mean_bp"], 1), None if not e.get("events") or e["t_daily_mean"] is None else round(e["t_daily_mean"], 2)) for w, e in o.items()})
    print("\nPER EVENT BY YEAR, t+2..t+3 less SPY (n, mean bp, t): T | A | B ; leveraged assets $bn")
    names = list(sets)
    for y in sorted(out["assets_by_year"]):
        cells = []
        for nm in (names[0], names[2], names[3]):
            e = out[nm]["per_event_by_year"].get(y, {"events": 0})
            cells.append(f"{e['events']:5d} {e['mean_bp']:7.1f} {(e['t_daily_mean'] or 0):5.2f}" if e["events"] else "    0       .     .")
        print(f"  {y}: " + " | ".join(cells) + f" ; {out['assets_by_year'][y]['mean_leveraged_assets_usd'] / 1e9:6.1f}")
    return out


def main() -> int:
    etf = pd.read_parquet(OUT / "etf_daily.parquet")
    etf["date"] = pd.to_datetime(etf["date"])
    etf["year"] = etf["date"].dt.year
    etf["aum_lag"] = (etf["shrout"] * 1000.0 * etf["prc"]).groupby(etf["permno"]).shift(1)
    sessions = pd.DatetimeIndex(sorted(etf["date"].unique()))
    spy_id = etf.loc[(etf["ticker"] == "SPY") & (etf["date"] == sessions[-1]), "permno"]
    if len(spy_id) != 1:
        raise ValueError("SPY is not uniquely identified on the last CRSP day")
    spy = etf[etf["permno"] == int(spy_id.iloc[0])].set_index("date")["ret"].reindex(sessions)
    if spy.iloc[1:].isna().any():
        raise ValueError("SPY has no return on a CRSP session")
    spy = spy.fillna(0.0)                                             # only the panel's first row, which nothing earns on
    pairs = pd.read_parquet(OUT / "pairs.parquet")
    out = {"panel_last_date": str(sessions[-1].date())}
    pi = pairs[(pairs["kind"] == "index") & pairs["lev"].isin(INDEX_MULTIPLES)]
    ps = pairs[pairs["kind"] == "single"]
    out["funds"] = {"index": int(pi["fund"].nunique()), "single": int(ps["fund"].nunique())}
    out["index"] = run("index", panel("index", etf, pi, sessions), spy, "2007-01-03")
    out["single"] = run("single", panel("single", etf, ps, sessions), spy, "2022-01-03")
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
