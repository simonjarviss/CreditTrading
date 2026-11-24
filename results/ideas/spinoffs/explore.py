"""Explore: spin-offs. Is the new company weak at first and strong afterwards?

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_spinoffs.py
    python3 results/ideas/spinoffs/explore.py

THE CLAIM. Holders of the parent are handed shares in a company they did not choose. Index
funds and large-company mandates must sell them, and others sell what they do not know. So
the new company should be weak in its first weeks and strong once that selling is done. The
other side of the later trade is those early sellers.

FIXED BEFORE ANY RETURN WAS READ
  event        a NEW spin-off in CRSP (scripts/research/stage_crsp_spinoffs.py): the
               distributed company's first daily row is its first regular-way session, F.
               Life session 1 is F. CRSP gives no return for F, so nothing here uses it.
  profile      the company's return less IWM's (small companies; SPY is shown too), summed
               over life sessions 2-5, 6-20, 21-63, 64-126, 127-252 and 253-504; the mean
               across spin-offs, with a t from the means of spin-offs grouped by the month of
               F. A company that stops trading contributes its rows up to its delisting row.
  book         SEASONED: decisions run from the close of life session 21 to the close of
               session 252 (or delisting), so with shift(2) it EARNS sessions 23 to 254. Eligible once, at that decision: $5 or more and a 21-session
               average dollar volume of $1M or more (all from its own first 21 sessions).
               Half the book long across live spin-offs equally, half short IWM; flat with
               fewer than 5 spin-offs. shift(2) on the canonical harness; gross; no cost.
               The 21-session wait is the claim's own "after the first weeks", fixed here
               and not searched.
  CONTROLS     (1) the same profile and book on every OTHER US common share newly listed in
               the period (mostly IPOs): is it spin-offs, or any new listing?
               (2) the parents, from the ex-date, same windows: the literature says they do
               well too, and a parent is never force-sold.
An early-weakness BOOK was not pre-specified: at 16 spin-offs a year about one would be in
its first 20 sessions at a time. The profile is the evidence for that half of the claim.

ADDED AFTER THE FIRST RUN, so NOT pre-specified, and reported beside the fixed book
  The session-by-session profile showed the weakness is life sessions 2 to 6 and the
  recovery starts about session 9. Two event books follow that shape, with windows chosen
  from it (which is the reason they are labelled):
  FIRST WEEK   short the new company over life sessions 3 to 5, long IWM against it. The
               short is decided at the close of session 1 from that day's price ($5) and
               dollar volume ($1M), filled at session 2's close, and earns 3, 4 and 5:
               session 2's own fall cannot be earned under shift(2).
  REBOUND      long over life sessions 7 to 63, short IWM against it; decided at the close
               of session 5 ($5; $1M average over its first five sessions).
  Each live name takes a FIXED 10% of the book, with IWM the same size the other way, capped
  at 50% a side. A fixed size is used because one or two names are live at a time; an
  equal-weight book would put half the capital in a single new stock.
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

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
EVENTS, ROWS, CTL, MKT = (RES / "crsp_spinoff_events.parquet", RES / "crsp_spinoff_daily.parquet",
                          RES / "crsp_newlist_daily.parquet", RES / "yf_daily.parquet")
RF = Path.home() / "quantt_data" / "riskfree_daily.parquet"
BLOCKS = [(2, 5), (6, 20), (21, 63), (64, 126), (127, 252), (253, 504)]
WAIT, LAST, MIN_PRICE, MIN_ADV, MIN_NAMES = 21, 252, 5.0, 1_000_000.0, 5


def wide(rows: pd.DataFrame, sessions: pd.DatetimeIndex):
    rows = rows[rows["date"].isin(sessions)]
    f = lambda c: rows.pivot(index="date", columns="permno", values=c).reindex(sessions)  # noqa: E731
    return f("ret"), f("prc"), f("dollar_volume")


def starts(ret: pd.DataFrame, prc: pd.DataFrame, anchor: pd.Series | None = None) -> pd.Series:
    """Index of life session 1 per permno: its first row, or the first session on/after `anchor`."""
    has = prc.notna().to_numpy() | ret.notna().to_numpy()
    first = pd.Series(np.where(has.any(axis=0), has.argmax(axis=0), -1), index=ret.columns)
    if anchor is None:
        return first
    a = pd.Series(ret.index.searchsorted(anchor.reindex(ret.columns).values, side="left"), index=ret.columns)
    return a.where(a < len(ret.index), -1)


def profile(ret: pd.DataFrame, s0: pd.Series, bench: pd.Series, month_of: pd.Series) -> dict:
    """Mean summed return less the benchmark per life-session block, t clustered by start month."""
    R, b, n = ret.to_numpy(), bench.to_numpy(), len(ret.index)
    out = {}
    for lo, hi in BLOCKS:
        vals, months = [], []
        for j, p in enumerate(ret.columns):
            i0 = s0[p]
            if i0 < 0:
                continue
            a, z = i0 + lo - 1, min(i0 + hi - 1, n - 1)          # life session k is index i0 + k - 1
            if a > z or i0 + hi - 1 > n - 1:                      # the block must fit inside the panel's dates
                continue
            r = R[a:z + 1, j]
            ok = ~np.isnan(r)
            if ok.sum() == 0:
                continue                                          # it stopped trading before this block
            vals.append(float((r[ok] - b[a:z + 1][ok]).sum()))
            months.append(month_of[p])
        v = pd.Series(vals).groupby(pd.Series(months).values).mean()
        m = float(np.mean(vals))
        out[f"{lo}-{hi}"] = {"mean_pct": m * 100, "median_pct": float(np.median(vals) * 100),
                             "t_by_start_month": float(v.mean() / v.std(ddof=1) * np.sqrt(len(v))) if len(v) > 2 else None,
                             "n": int(len(vals)), "share_positive": float((np.array(vals) > 0).mean())}
    return out


def seasoned_book(ret, prc, dv, s0: pd.Series, hedge: str):
    """+0.5 across names between life sessions WAIT and LAST, -0.5 in the hedge column. Decision-dated."""
    n, cols = len(ret.index), list(ret.columns)
    adv = dv.rolling(21, min_periods=10).mean().to_numpy()
    P = prc.to_numpy()
    act = np.zeros((n, len(cols)), dtype=bool)
    n_elig = 0
    for j, p in enumerate(cols):
        i0 = s0[p]
        d0 = i0 + WAIT - 1                                        # ALIGNMENT: decided at the close of life session WAIT
        if i0 < 0 or d0 >= n:
            continue
        if not (np.nan_to_num(P[d0, j]) >= MIN_PRICE and np.nan_to_num(adv[d0, j]) >= MIN_ADV):
            continue
        rows = np.flatnonzero(~np.isnan(P[:, j]))
        d1 = min(i0 + LAST - 1, rows[-1])                         # held while it still has a price row
        if d1 >= d0:
            act[d0:d1 + 1, j] = True
            n_elig += 1
    k = act.sum(axis=1)
    live = k >= MIN_NAMES
    W = np.where(live[:, None], 0.5 * act / np.maximum(k, 1)[:, None], 0.0)
    H = pd.DataFrame(W, index=ret.index, columns=cols)
    H[hedge] = np.where(live, -0.5, 0.0)
    return H, n_elig, pd.Series(k, index=ret.index)


def event_book(ret, prc, dv, s0: pd.Series, earn_first: int, earn_last: int, side: float, adv_days: int,
               size: float = 0.10, cap: float = 0.50) -> tuple[pd.DataFrame, int]:
    """A fixed `size` per live name with the hedge the other way. The name earns life sessions
    earn_first..earn_last, so its weights are decided two sessions earlier (the harness adds the lag)."""
    n, cols = len(ret.index), list(ret.columns)
    P, V = prc.to_numpy(), dv.to_numpy()
    W = np.zeros((n, len(cols)))
    n_elig = 0
    for j, p in enumerate(cols):
        i0 = s0[p]
        d0, d1 = i0 + earn_first - 1 - harness.EXEC_LAG, i0 + earn_last - 1 - harness.EXEC_LAG
        if i0 < 0 or d0 < i0 or d0 >= n:
            continue
        v = V[i0:d0 + 1, j][-adv_days:]                          # ALIGNMENT: its own sessions up to the decision, no later
        if not (np.nan_to_num(P[d0, j]) >= MIN_PRICE and len(v) and np.nanmean(v) >= MIN_ADV):
            continue
        rows = np.flatnonzero(~np.isnan(P[:, j]))
        d1 = min(d1, rows[-1], n - 1)
        if d1 >= d0:
            W[d0:d1 + 1, j] = side * size
            n_elig += 1
    gross = np.abs(W).sum(axis=1)
    W *= np.where(gross > cap, cap / np.maximum(gross, 1e-12), 1.0)[:, None]
    H = pd.DataFrame(W, index=ret.index, columns=cols)
    H["__hedge__"] = -H.sum(axis=1)
    return H, n_elig


def run_event_book(ret, prc, dv, s0, bench_ret, **kw) -> tuple[dict, pd.Series]:
    H, n_elig = event_book(ret, prc, dv, s0, **kw)
    R = ret.fillna(0.0)
    R["__hedge__"] = bench_ret.fillna(0.0)
    ev = harness.evaluate(H, R)
    on = H.drop(columns="__hedge__").abs().sum(axis=1)
    pnl = ev["pnl"].loc[(on > 0).idxmax():].iloc[harness.EXEC_LAG:]
    held = on.shift(harness.EXEC_LAG).reindex(pnl.index).fillna(0.0)
    res = explore.summarise(pnl)
    res.update({"names_traded": int(n_elig), "invested_day_share": float((held > 0).mean()),
                "mean_gross_per_side_when_invested": float(held[held > 0].mean()),
                "return_per_name_pct": float(pnl.sum() / max(n_elig, 1) / kw.get("size", 0.10) * 100),
                "turnover_per_year": float(ev["turn"])})
    return res, pnl


def run_book(name, ret, prc, dv, s0, bench_ret: pd.Series, rf: pd.Series, mkt_x: pd.Series) -> tuple[dict, pd.Series]:
    H, n_elig, k = seasoned_book(ret, prc, dv, s0, "__hedge__")
    R = ret.fillna(0.0)
    R["__hedge__"] = bench_ret.fillna(0.0)
    ev = harness.evaluate(H, R)
    on = H.abs().sum(axis=1) > 0
    if not on.any():
        raise RuntimeError(f"{name}: the book never holds {MIN_NAMES} names")
    pnl = ev["pnl"].loc[on.idxmax():].iloc[harness.EXEC_LAG:]
    long_only = harness.evaluate(H.drop(columns="__hedge__") * 2, R.drop(columns="__hedge__"))["pnl"].reindex(pnl.index)
    inv = (H.drop(columns="__hedge__").shift(harness.EXEC_LAG).sum(axis=1) * 2).reindex(pnl.index).fillna(0.0)
    xs = long_only - rf.reindex(pnl.index) * inv
    df = pd.DataFrame({"y": xs, "m": mkt_x.reindex(pnl.index)}).dropna()
    beta = float(np.cov(df["y"], df["m"])[0, 1] / df["m"].var())
    res = explore.summarise(pnl)
    res.update({"names_eligible": int(n_elig), "names_live_median": float(k.reindex(pnl.index).median()),
                "flat_day_share": float((k.reindex(pnl.index) < MIN_NAMES).mean()), "turnover_per_year": float(ev["turn"]),
                "long_leg_over_bills": explore.stats(xs), "long_leg_beta_to_spy": beta})
    return res, pnl


def main() -> int:
    mk = pd.read_parquet(MKT)
    px = mk.pivot(index="date", columns="ticker", values="ret_total")
    sessions = px.index[(px.index >= "1999-12-01") & (px.index <= "2025-12-31") & px["SPY"].notna()]
    iwm, spy = px["IWM"].reindex(sessions), px["SPY"].reindex(sessions)
    rf = pd.read_parquet(RF).set_index("date")["rf_daily"].reindex(sessions).ffill()
    ev = pd.read_parquet(EVENTS)
    ev["ex_date"] = pd.to_datetime(ev["ex_date"])
    new = ev[~ev["child_already_listed"]]
    x = pd.read_parquet(ROWS)
    x["date"] = pd.to_datetime(x["date"])
    c = pd.read_parquet(CTL)
    c["date"] = pd.to_datetime(c["date"])
    out = {"panel_last_date": str(sessions.max().date()), "events_staged": int(len(ev)), "new_spinoffs": int(new["child"].nunique()),
           "children_already_listed_left_out": int(ev["child_already_listed"].sum())}

    groups = {}
    ch = x[x["permno"].isin(new["child"])]
    groups["spinoffs"] = (*wide(ch, sessions), None)
    pa = x[x["permno"].isin(new["parent"])]
    anchor = new.groupby("parent")["ex_date"].min()
    groups["parents"] = (*wide(pa, sessions), anchor)
    groups["other_new_listings"] = (*wide(c, sessions), None)

    series = {}
    for name, (ret, prc, dv, anc) in groups.items():
        s0 = starts(ret, prc, anc)
        # a life must start on a session IWM has a return for, or the benchmark is missing from the profile
        first_iwm = sessions.get_loc(iwm.first_valid_index())
        s0 = s0.where(s0 >= first_iwm, -1)
        month_of = pd.Series({p: sessions[i].to_period("M") for p, i in s0.items() if i >= 0})
        g = {"names": int((s0 >= 0).sum()),
             "profile_vs_iwm": profile(ret, s0, iwm.fillna(0.0), month_of),
             "profile_vs_spy": profile(ret, s0, spy.fillna(0.0), month_of)}
        res, pnl = run_book(name, ret, prc, dv, s0, iwm, rf, spy - rf)
        series[name] = pnl
        out[name] = {**g, "book": res}
        if name in ("spinoffs", "other_new_listings"):
            fw, p_fw = run_event_book(ret, prc, dv, s0, iwm, earn_first=3, earn_last=5, side=-1.0, adv_days=1)
            rb, p_rb = run_event_book(ret, prc, dv, s0, iwm, earn_first=7, earn_last=63, side=1.0, adv_days=5)
            both = p_fw.add(p_rb, fill_value=0.0)
            out[name]["variants_not_prespecified"] = {"first_week_short": fw, "rebound_long": rb, "both": explore.summarise(both)}
            series[f"{name}_first_week"], series[f"{name}_rebound"], series[f"{name}_both"] = p_fw, p_rb, both
            # the session-by-session shape the variants were read from
            out[name]["profile_by_session_vs_iwm"] = {}
            keep = BLOCKS[:]
            try:
                for k in list(range(2, 13)):
                    BLOCKS[:] = [(k, k)]
                    out[name]["profile_by_session_vs_iwm"].update(profile(ret, s0, iwm.fillna(0.0), month_of))
                BLOCKS[:] = [(3, 5), (7, 20), (7, 63)]
                out[name]["profile_windows_vs_iwm"] = profile(ret, s0, iwm.fillna(0.0), month_of)
            finally:
                BLOCKS[:] = keep
    base = series["spinoffs"]
    out["spinoffs"]["book"]["controls"] = {k: explore.stats(v.reindex(base.index).fillna(0.0)) for k, v in series.items()
                                           if k in ("parents", "other_new_listings")}
    out["spinoffs"]["book"]["corr_with_other_new_listings_book"] = float(np.corrcoef(base, series["other_new_listings"].reindex(base.index).fillna(0.0))[0, 1])
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=str))
    explore.write(HERE / "book", out["spinoffs"]["book"], base,
                  title=f"Spin-offs from life session 21 to 252, long vs IWM; shift(2), gross; to {out['panel_last_date']}",
                  controls={k: v for k, v in series.items() if k in ("parents", "other_new_listings")})
    explore.write(HERE / "variants", out["spinoffs"]["variants_not_prespecified"]["both"], series["spinoffs_both"],
                  title=f"Spin-offs: short sessions 3-5, long 7-63, 10% a name vs IWM (not pre-specified); to {out['panel_last_date']}",
                  controls={"same rules on other new listings": series["other_new_listings_both"]})
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=str))
    print("panel to", out["panel_last_date"], "| new spin-offs", out["new_spinoffs"], "| already-listed children left out", out["children_already_listed_left_out"])
    for name in groups:
        g = out[name]
        print(f"\n== {name}: {g['names']:,} names")
        for lab in ("profile_vs_iwm", "profile_vs_spy"):
            print(f"  {lab}, % (t; n; share>0): " + "  ".join(
                f"{k}: {v['mean_pct']:+.1f} ({v['t_by_start_month'] if v['t_by_start_month'] is None else round(v['t_by_start_month'], 1)}; {v['n']}; {v['share_positive']:.0%})"
                for k, v in g[lab].items()))
        b = g["book"]
        print(explore.table({**b, "controls": b.get("controls", {})}))
        print(f"  eligible {b['names_eligible']:,}, live (median) {b['names_live_median']:.0f}, flat days {b['flat_day_share']:.1%}, turnover/yr {b['turnover_per_year']:.1f} | "
              f"long leg over bills: {b['long_leg_over_bills']['ann_ret']:.2%}/yr, Sharpe {b['long_leg_over_bills']['sharpe']:.2f}, beta to SPY {b['long_leg_beta_to_spy']:.2f}")
        if "variants_not_prespecified" in g:
            print("  by session vs IWM, % (t):", " ".join(f"{k.split('-')[0]}:{v['mean_pct']:+.2f}({v['t_by_start_month']:+.1f})" for k, v in g["profile_by_session_vs_iwm"].items()))
            print("  windows vs IWM, % (t; share>0):", " ".join(f"{k}: {v['mean_pct']:+.2f} ({v['t_by_start_month']:+.1f}; {v['share_positive']:.0%})" for k, v in g["profile_windows_vs_iwm"].items()))
            for lab, v in g["variants_not_prespecified"].items():
                f_ = v["full"]
                extra = "" if lab == "both" else (f" | names {v['names_traded']}, invested {v['invested_day_share']:.0%} of days, "
                                                  f"{v['return_per_name_pct']:+.2f}% per name, gross a side when invested {v['mean_gross_per_side_when_invested']:.2f}")
                print(f"  variant {lab}: Sharpe {f_['sharpe']:.2f} (t {f_['t']:.2f}), {f_['ann_ret']:.2%}/yr at {f_['ann_vol']:.2%} vol, halves {v['early_half']['sharpe']:.2f} / {v['late_half']['sharpe']:.2f}, "
                      f"eras {', '.join(str(round(e['sharpe'], 2)) for e in v['eras'].values())}{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
