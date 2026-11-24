"""R4 step 1: date and size fund-of-CEF index reconstitution events (YYY, PCEF, XMPT).

WHY this exists: the question is whether index reconstitutions push flows into CEFs
that are large against ADV (the A9 bar is >= 1 day of ADV) with a pre-effective window
a shift(2) book can enter. The ETFs' constituent histories are not in the repo (the
local N-PORT parquet holds HYG, JNK and LQD only), EDGAR is off limits here, and Nasdaq
GIW shows historical YLDA weights only to subscribers. What is left is the Wayback
Machine's captures of the issuers' holdings pages (fetch_wayback.py, parse_snapshots.py).

What it does
  1. Snapshot bound: for every archived snapshot, the ETF's FULL position in each
     allowed name in days of that name's ADV. A drop sells the whole position and an add
     buys about the same, so this bounds any single event's demand at that AUM.
  2. Events: consecutive snapshots that bracket exactly ONE scheduled rebalance give
     dated adds, drops and reweights. Pairs bracketing two or more are undatable and are
     counted as such; pairs bracketing none are the calendar check (composition should
     not change except through corporate actions).
  3. Demand = AUM x |dw| / ADV63, ADV63 = mean close x volume over the 63 sessions ending
     the session BEFORE the announcement proxy (no lookahead: asserted). For reweights dw
     includes price drift between snapshots, so it is an UPPER bound on rebalance flow.

Names: returns are never computed here. ADV (a volume statistic, not a return) is read
only for allowed names: the deployed 13 (scripts/cef/spec.py), the wide 17 (+NAD NEA NVG
NZF) and C4's families universe (included == True). The other 27 cef_universe.csv names
are the sealed holdout: their events are counted, never sized. Every date read is
<= 2022-12-30 (asserted); 2023+ snapshots, if any, are counted by date and name only.

Calendars (labelled in NOTE.md):
  YYY  effective at the open of the first session after the 3rd Friday of Jan/Jul; the
       ETF trades at the close of the 3rd Friday (E); announced after the close of the 6th
       session before the effective date (A) [V: Nasdaq Methodology_YLDA, 2025-26 text;
       U: whether the 2013-2021 index used the same calendar].
  PCEF effective at the close of the last session of each quarter (E) [V: S-Network
       methodology March 2024; U for 2010-2013]. Announcement proxy A = the Monday after the
       3rd Friday of the quarter's last month [U: described in search results of a 2020
       UBS 424B3 on EDGAR, not fetched]. A only sets the ADV window here.
  XMPT same as PCEF (CEFMX: rebalanced quarterly; reconstituted semiannually per the 2024
       text) [U for 2019-2021].

Run: cd SCRATCH/tree && python3 ../r4_index_rebal/size_events.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TREE = HERE.parent / "tree"
sys.path.insert(0, str(TREE))
from scripts.cef.spec import UNIVERSE  # noqa: E402  (the frozen spec is the authority)

FIT_END = pd.Timestamp("2022-12-30")
ADV_N = 63
BAR = 1.0  # days of ADV (declared in NOTE.md before anything was computed)

WIDE = list(UNIVERSE) + ["NAD", "NEA", "NVG", "NZF"]


def load_names() -> tuple[set, set, set, set]:
    cu = pd.read_csv(TREE / "data/cef/cef_universe.csv")
    fam = pd.read_csv(TREE / "data/cef_families/universe.csv")
    fam_inc = set(fam.loc[fam.included == True, "ticker"])  # noqa: E712
    dep = set(UNIVERSE)
    wide = set(WIDE)
    sealed = set(cu.ticker) - wide
    if len(sealed) != 27:
        raise ValueError(f"expected the 27-name sealed holdout, found {len(sealed)}")
    if fam_inc & set(cu.ticker):
        raise ValueError("a C4 families name is also in cef_universe.csv")
    return dep, wide, fam_inc, sealed


def load_adv(allowed: set) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    """Daily dollar volume for allowed names only, dates <= FIT_END."""
    a = pd.read_parquet(TREE / "data/cef/cef_prices.parquet", columns=["date", "ticker", "close", "volume"])
    a = a[a.ticker.isin(set(WIDE))]
    b = pd.read_parquet(TREE / "data/cef_families/cef_prices.parquet", columns=["date", "ticker", "close", "volume"])
    b = b[b.ticker.isin(allowed - set(WIDE))]
    px = pd.concat([a, b])
    px = px[px.date <= FIT_END]
    assert px.date.max() <= FIT_END, "a date after the fit window was read"
    px["dv"] = px.close * px.volume
    dv = px.pivot_table(index="date", columns="ticker", values="dv", aggfunc="first").sort_index()
    sessions = pd.DatetimeIndex(sorted(set(a.date[a.date <= FIT_END])))
    return dv, sessions


def adv_before(dv: pd.DataFrame, ticker: str, day: pd.Timestamp) -> float:
    """Mean dollar volume over the ADV_N sessions strictly before `day` (no lookahead).
    Returns NaN when the name has fewer than ADV_N observations then: the event is UNSIZED."""
    if ticker not in dv.columns:
        return np.nan
    s = dv[ticker]
    s = s[s.index < day].dropna().iloc[-ADV_N:]
    assert s.empty or s.index.max() < day
    return float(s.mean()) if len(s) == ADV_N else np.nan


def third_friday(y: int, m: int) -> pd.Timestamp:
    d = pd.Timestamp(y, m, 1)
    first_fri = d + pd.Timedelta(days=(4 - d.weekday()) % 7)
    return first_fri + pd.Timedelta(days=14)


def schedule(etf: str, sessions: pd.DatetimeIndex, years: range) -> pd.DataFrame:
    """Rebalance rows: E = last close at which the ETF trades the change, A = announcement
    (or its proxy). Both snapped to NYSE sessions from the CEF panel."""
    rows = []

    def prev_session(d):  # last session <= d
        return sessions[sessions <= d][-1]

    def next_session(d):  # first session > d
        return sessions[sessions > d][0]

    for y in years:
        if etf == "YYY":
            for m in (1, 7):
                f3 = third_friday(y, m)
                if f3 > sessions[-1]:
                    continue
                E = prev_session(f3)
                eff = next_session(f3)
                i = sessions.get_loc(eff)
                A = sessions[i - 6]
                rows.append((etf, E, A))
        else:
            for m in (3, 6, 9, 12):
                end = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)
                if end > sessions[-1] + pd.Timedelta(days=4):  # a quarter-end past the panel
                    continue
                E = prev_session(end)
                mon = third_friday(y, m) + pd.Timedelta(days=3)
                A = prev_session(mon) if mon not in sessions else mon
                rows.append((etf, E, A))
    df = pd.DataFrame(rows, columns=["etf", "E", "A"])
    df["window_sessions"] = [int(((sessions > a) & (sessions <= e)).sum()) - 1 for a, e in zip(df.A, df.E)]
    # window_sessions = sessions from the shift(2) fill (close A+1) to close E, exclusive of A+1
    return df


def classify(t: str, dep, wide, fam, sealed) -> str:
    if t in dep:
        return "deployed13"
    if t in wide:
        return "wide17"
    if t in fam:
        return "c4_family"
    if t in sealed:
        return "SEALED"
    return "outside_panels"


# Corporate actions found by hand in the dated pairs (a merger moves weight into the
# acquirer with no index trade: the ETF receives the acquirer's shares). Each row names
# the evidence in the snapshots themselves.
CORP_ACTION = {
    ("PCEF", "2013-09-30", "HYT"): "BlackRock HY merger: COY, CYE and HYV leave PCEF between 2013-08-05 "
                                   "and 2013-12-19 while HYT goes 0.46% -> 1.80% (sum of the four 1.47%)",
}


# NAV symbols whose listed ticker never appears plainly in a snapshot; the mapping is
# checked against the fund name the page prints in the same row.
NAV_SYMBOL_BY_NAME = {"XDLYX": "DLY"}  # "DOUBLELINE YIELD OPPORTUNITIES COM", YYY 2021-02-17


def normalise_tickers(H: pd.DataFrame) -> pd.DataFrame:
    """Issuer pages sometimes list a CEF under its NAV symbol X<T>X (PCEF 2012-05 .. 2013-05
    shows XETYX, XEXGX, XQQQX, ...; YYY shows XDLYX). Left alone, this fakes a drop and a
    re-add of the same fund. Map X<T>X -> T and record each mapping."""
    m = H.ticker.str.fullmatch(r"X([A-Z]{2,4})X")
    out = H.copy()
    plain = set(H.ticker[~m])
    def fix(x: str) -> str:
        mid = x[1:-1]
        # a 4-letter ticker ending in X shares its X with the NAV suffix: XQQQX is QQQX
        if mid in plain:
            return mid
        if mid + "X" in plain:
            return mid + "X"
        if x in NAV_SYMBOL_BY_NAME:  # verified by the fund name printed beside it
            return NAV_SYMBOL_BY_NAME[x]
        raise ValueError(f"NAV symbol {x}: neither {mid} nor {mid}X is listed in any snapshot")
    out.loc[m, "ticker"] = out.loc[m, "ticker"].map(fix)
    print("NAV-symbol mapping:", dict(sorted(set(zip(H.ticker[m], out.ticker[m])))))
    dup = out.duplicated(["etf", "asof", "ticker"], keep=False)
    if dup.any():
        raise ValueError(f"NAV-symbol mapping collides with a listed ticker: {out[dup][['etf','asof','ticker']].head()}")
    mapped = H.loc[m].groupby("etf").ticker.unique().to_dict()
    print(f"NAV-symbol tickers mapped back: { {k: sorted(v) for k, v in mapped.items()} }")
    return out


def main() -> None:
    dep, wide, fam, sealed = load_names()
    allowed = wide | fam
    dv, sessions = load_adv(allowed)
    H = pd.read_csv(HERE / "out/holdings_snapshots.csv", parse_dates=["asof"])
    aum = pd.read_csv(HERE / "out/aum_points.csv", parse_dates=["asof"])
    H = normalise_tickers(H)
    H["cls"] = [classify(t, dep, wide, fam, sealed) for t in H.ticker]
    post = H[H["asof"] > FIT_END]
    if len(post):
        print(f"2023+ snapshots (counted, not sized): {post.groupby('etf')['asof'].unique().to_dict()}")
    H = H[H["asof"] <= FIT_END].copy()

    def etf_aum(etf: str, day: pd.Timestamp, snap_na: float) -> tuple[float, int]:
        if etf in ("YYY", "XMPT"):
            if not np.isfinite(snap_na):
                raise ValueError(f"{etf} {day.date()}: snapshot carries no net assets")
            return snap_na, 0
        pts = aum[(aum.etf == etf)]
        gap = (pts["asof"] - day).abs().dt.days
        j = gap.idxmin()
        if gap[j] > 60:
            return np.nan, int(gap[j])
        return float(pts.mktval_musd[j] * 1e6), int(gap[j])

    # ---- 1. snapshot bound: full position / ADV ------------------------------------------
    rows = []
    for (etf, d), g in H.groupby(["etf", "asof"]):
        A_, gap = etf_aum(etf, d, g.net_assets.iloc[0])
        for _, r in g.iterrows():
            adv = adv_before(dv, r.ticker, d) if r.cls in ("deployed13", "wide17", "c4_family") else np.nan
            rows.append((etf, d, r.ticker, r.cls, r.weight_pct, A_, gap, adv, A_ * r.weight_pct / 100 / adv if adv > 0 else np.nan))
    S = pd.DataFrame(rows, columns=["etf", "asof", "ticker", "cls", "w_pct", "aum", "aum_gap_days", "adv63", "pos_days_adv"])
    S.to_csv(HERE / "out/snapshot_position_days.csv", index=False)

    # ---- 2. events from bracketing pairs ----------------------------------------------------
    sch = pd.concat([schedule(e, sessions, range(2010, 2023)) for e in ("YYY", "PCEF", "XMPT")])
    sch = sch[sch.E <= FIT_END]
    sch.to_csv(HERE / "out/rebalance_calendar.csv", index=False)
    ev, pairs, und = [], [], []
    for etf, g in H.groupby("etf"):
        dates = sorted(g["asof"].unique())
        for d0, d1 in zip(dates[:-1], dates[1:]):
            d0, d1 = pd.Timestamp(d0), pd.Timestamp(d1)
            reb = sch[(sch.etf == etf) & (sch.E >= d0) & (sch.E < d1)]
            if (reb.E == d0).any():
                raise ValueError(f"{etf}: snapshot {d0.date()} falls on a rebalance close; as-of semantics ambiguous")
            g0 = g[g["asof"] == d0].set_index("ticker")
            g1 = g[g["asof"] == d1].set_index("ticker")
            adds = sorted(set(g1.index) - set(g0.index))
            drops = sorted(set(g0.index) - set(g1.index))
            both = sorted(set(g0.index) & set(g1.index))
            pairs.append((etf, d0.date(), d1.date(), len(reb), len(adds), len(drops), len(both)))
            if len(reb) >= 2:
                # undatable: the change happened at one of len(reb) rebalances. Size the full
                # position at the near snapshot (s1 for adds, s0 for drops), ADV before that
                # snapshot, to show what a dated history would contain. Never event-studied.
                for kind, names, gg, dd in (("add", adds, g1, d1), ("drop", drops, g0, d0)):
                    a_, _ = etf_aum(etf, dd, gg.net_assets.iloc[0])
                    for t in names:
                        cls = classify(t, dep, wide, fam, sealed)
                        adv = adv_before(dv, t, dd) if cls in ("deployed13", "wide17", "c4_family") else np.nan
                        und.append((etf, d0.date(), d1.date(), len(reb), kind, t, cls, gg.weight_pct[t], a_, adv,
                                    a_ * gg.weight_pct[t] / 100 / adv if adv > 0 else np.nan))
            if len(reb) != 1:
                continue
            E, A, win = reb.E.iloc[0], reb.A.iloc[0], int(reb.window_sessions.iloc[0])
            aum0, gap0 = etf_aum(etf, E, g0.net_assets.iloc[0])
            aum1, gap1 = etf_aum(etf, E, g1.net_assets.iloc[0])
            for kind, names in (("add", adds), ("drop", drops), ("reweight", both)):
                for t in names:
                    w0 = g0.weight_pct.get(t, 0.0)
                    w1 = g1.weight_pct.get(t, 0.0)
                    dw = (w1 - w0) / 100
                    a_ = aum1 if kind == "add" else aum0
                    cls = classify(t, dep, wide, fam, sealed)
                    adv = adv_before(dv, t, A) if cls in ("deployed13", "wide17", "c4_family") else np.nan
                    assert not np.isfinite(adv) or dv.index[dv.index < A].max() < A
                    dem = a_ * abs(dw) / adv if (np.isfinite(adv) and adv > 0 and np.isfinite(a_)) else np.nan
                    ev.append((etf, E.date(), A.date(), win, d0.date(), d1.date(), kind, t, cls, w0, w1, a_, adv, dem))
    P = pd.DataFrame(pairs, columns=["etf", "snap0", "snap1", "n_rebalances", "n_new", "n_gone", "n_both"])
    P.to_csv(HERE / "out/snapshot_pairs.csv", index=False)
    EV = pd.DataFrame(ev, columns=["etf", "E", "A", "window_sessions", "snap0", "snap1", "kind", "ticker", "cls",
                                   "w0_pct", "w1_pct", "aum_usd", "adv63_usd", "demand_days_adv"])
    EV["corp_action"] = [CORP_ACTION.get((e, str(d), t), "") for e, d, t in zip(EV.etf, EV.E, EV.ticker)]
    EV.to_csv(HERE / "out/events_dated.csv", index=False)
    U = pd.DataFrame(und, columns=["etf", "snap0", "snap1", "n_rebalances", "kind", "ticker", "cls", "w_pct",
                                   "aum_usd", "adv63_usd", "pos_days_adv"])
    U.to_csv(HERE / "out/events_undatable.csv", index=False)

    # ---- report -----------------------------------------------------------------------------
    pd.set_option("display.width", 220)
    print(f"spec universe ({len(UNIVERSE)}): {', '.join(UNIVERSE)}")
    print(f"ADV panel last date read: {dv.index.max().date()} (fit window end {FIT_END.date()})")
    print("\n== snapshot pairs (n_rebalances: 1 = dated; 0 = calendar check; >=2 = undatable)")
    print(P.to_string(index=False))
    print("\n== snapshot bound: full position in allowed names, days of ADV63")
    al = S[S.cls.isin(["deployed13", "wide17", "c4_family"])]
    summ = al.groupby(["etf", "asof"]).agg(aum_musd=("aum", lambda x: x.iloc[0] / 1e6), gap=("aum_gap_days", "first"),
                                           n_names=("ticker", "size"), n_sized=("pos_days_adv", "count"),
                                           median=("pos_days_adv", "median"), p90=("pos_days_adv", lambda x: x.quantile(.9)),
                                           max=("pos_days_adv", "max"), n_ge1=("pos_days_adv", lambda x: int((x >= BAR).sum())))
    print(summ.round(2).to_string())
    print("\n  by class (all snapshots):")
    print(al.groupby(["etf", "cls"]).pos_days_adv.describe()[["count", "50%", "max"]].round(2).to_string())
    print("\n  names per snapshot by class:")
    print(S.groupby(["etf", "cls"]).size().unstack(fill_value=0).to_string())
    print("\n== dated events (one rebalance bracketed)")
    print(sch.groupby("etf").window_sessions.describe()[["min", "50%", "max"]].to_string())
    if EV.empty:
        print("no dated events")
        return
    EV["sized"] = EV.demand_days_adv.notna()
    EV["ge1"] = EV.demand_days_adv >= BAR
    tab = EV.groupby(["etf", "E", "kind", "cls"]).agg(n=("ticker", "size"), sized=("sized", "sum"), ge1=("ge1", "sum")).reset_index()
    print(tab.to_string(index=False))
    print("\n  totals by etf/kind/class:")
    print(EV.groupby(["etf", "kind", "cls"]).agg(n=("ticker", "size"), sized=("sized", "sum"), ge1=("ge1", "sum"),
                                                 med_days=("demand_days_adv", "median")).round(2).to_string())
    print("\n  corporate actions excluded:")
    print(EV[EV.corp_action != ""][["etf", "E", "kind", "ticker", "w0_pct", "w1_pct", "demand_days_adv", "corp_action"]].round(2).to_string(index=False))
    print("\n== UNDATABLE adds/drops (pair spans >= 2 rebalances): full position at the near snapshot, days of ADV")
    print(U.groupby(["etf", "kind", "cls"]).agg(n=("ticker", "size"), sized=("pos_days_adv", "count"),
                                                ge1=("pos_days_adv", lambda x: int((x >= BAR).sum())),
                                                med=("pos_days_adv", "median")).round(2).to_string())
    print("  by pair:")
    print(U[U.cls.isin(["deployed13", "wide17", "c4_family"])].groupby(["etf", "snap0", "snap1", "n_rebalances"]).agg(
        n_allowed=("ticker", "size"), ge1=("pos_days_adv", lambda x: int((x >= BAR).sum()))).to_string())
    print("  all names (any class) by pair:")
    print(U.groupby(["etf", "snap0", "snap1", "n_rebalances", "cls"]).size().unstack(fill_value=0).to_string())
    q = EV[EV.ge1 & EV.cls.isin(["deployed13", "wide17", "c4_family"]) & (EV.corp_action == "")].copy()
    q["year"] = pd.to_datetime(q.E).dt.year
    print(f"\n== GATE: dated, sized, >= {BAR} ADV, allowed names, fit window: {len(q)} (gate needs 30)")
    if len(q):
        print(q.groupby(["year", "etf", "kind"]).size().to_string())
        print(q[["etf", "E", "A", "window_sessions", "kind", "ticker", "cls", "w0_pct", "w1_pct", "aum_usd", "adv63_usd", "demand_days_adv"]]
              .sort_values(["E", "demand_days_adv"]).round(3).to_string(index=False))
    q.to_csv(HERE / "out/events_qualifying.csv", index=False)


if __name__ == "__main__":
    main()
