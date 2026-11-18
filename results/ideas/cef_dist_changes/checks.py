"""Checks on the distribution-change events. NONE OF THIS WAS PRE-SPECIFIED.

    python3 results/ideas/cef_dist_changes/checks.py        (after explore.py has staged the data)

Written on 2026-11-18, AFTER explore.py's returns had been read. explore.py's rule expected a
cut fund to REBOUND; it kept falling, and a raise kept rising. So the open question changed
from "is the rebound bigger than a control's" to "is a drift in the direction of the news
real, or is it the announcement itself leaking into the window". Each check below answers a
named doubt and is a reading of the same events, not a new rule to trade:

  1. LATE DATES. If CRSP's declaration date is EARLIER than the day the public learned the
     amount (a board date, say), a window that opens at K+2 holds the announcement move, and
     the "drift" is lookahead. Two answers that need no outside source:
       a. open the window later: 5, 10 and 20 sessions after K;
       b. anchor on the EX-DATE X, the first session the fund trades without the new amount.
          By X the amount is public beyond argument. Decide at X's close, fill at X+1, earn
          X+2 .. X+21; and again deciding at X+3 (earn X+5 .. X+24), which is past the desk's
          known fall over the three sessions after any ex-date. The control is the same
          funds' UNCHANGED declarations anchored on their ex-dates in the same way, so the
          ordinary ex-date cycle is in both and cancels in the difference.
  2. A FEW BIG EVENTS. Means with the top and bottom 1% of events removed.
  3. THE YEAR-END RAISES explore.py left out (ex-date 1 December to 15 January): do they
     drift? If they do not, leaving them out was right and the rule needs it live.
  4. THE FORM A BOOK COULD HOLD. Raises by TAXABLE funds only (the municipal split in
     explore.py was negative), long against the CEF market and against PCEF, on
     harness.evaluate. Chosen after seeing the split, so its Sharpe is flattered: it is shown
     to size the idea, not as a result.
  5. CUTS AS A LIST TO AVOID. The fund's return less the market over K+2 .. K+61 by tax class
     and payer type is already in explore.py. Here: how long the underperformance lasts
     (K+62 .. K+121), because the live discount book holds funds for weeks.

ALIGNMENT. Every window opens at least two sessions after the session it is decided on, and
eligibility uses price and volume through the session before the decision (as explore.py).
Licensed rows stay under ~/quantt_research/; this writes aggregates only (checks.json).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
spec = importlib.util.spec_from_file_location("cef_dist_changes_explore", HERE / "explore.py")
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)


def main() -> int:
    df = pd.read_parquet(ex.PANEL)
    df["date"] = pd.to_datetime(df["date"])
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc")
    dv = df.pivot(index="date", columns="permno", values="dollar_volume")
    idx, cols = ret.index, ret.columns
    T = len(idx)
    adv = dv.rolling(21, min_periods=10).mean()
    elig = ((prc >= ex.MIN_PRICE) & (adv >= ex.MIN_ADV)).shift(1, fill_value=False)   # through s-1 only
    R = ret.fillna(0.0)
    mkt = ret.where(elig).mean(axis=1).fillna(0.0)
    Rn, mk, eln, has_ret = R.to_numpy(), mkt.to_numpy(), elig.to_numpy(), ret.notna().to_numpy()
    col_of = {p: j for j, p in enumerate(cols)}

    g, _ = ex.declarations()
    g = g[g.permno.isin(cols) & g.decl.notna()].copy()
    g["d0"] = idx.searchsorted(g.decl.to_numpy(), side="left")
    g["k"] = g.d0 + 1
    g["x"] = idx.searchsorted(g.disexdt.to_numpy(), side="left")
    g["j"] = g.permno.map(col_of)
    g = g[(g.k + 2 < T) & (g.d0 >= 30) & (g.x + 2 < T)].copy()
    assert (idx[g.k.to_numpy()] > g.decl.to_numpy()).all(), "lookahead: K is not after the declaration date"
    assert (idx[g.x.to_numpy()] >= g.disexdt.to_numpy()).all(), "lookahead: X is before the ex-date"
    kk, jj, xx = g.k.to_numpy(), g.j.to_numpy(), g.x.to_numpy()
    g["elig_k"] = eln[kk, jj] & has_ret[kk, jj]
    g["elig_x"] = eln[xx, jj] & has_ret[xx, jj]
    g["elig_x3"] = eln[np.minimum(xx + 3, T - 1), jj] & has_ret[np.minimum(xx + 3, T - 1), jj]
    g["ym_k"] = idx[kk].to_period("M").astype(str)
    g["ym_x"] = idx[xx].to_period("M").astype(str)
    dec_dj = (g.disexdt.dt.month == 12) | ((g.disexdt.dt.month == 1) & (g.disexdt.dt.day <= 15))
    g["cut"] = g.event & (g.chg < 0)
    g["raise"] = g.event & (g.chg > 0) & ~dec_dj
    g["raise_yearend"] = g.event & (g.chg > 0) & dec_dj
    # the unchanged control, as explore.py: not within 60 sessions after one of the fund's own 5% changes
    flag = np.zeros((T, len(cols)), bool)
    a = g[g.any_change]
    flag[a.k.to_numpy(), a.j.to_numpy()] = True
    after_prev = (pd.DataFrame(flag).rolling(ex.BLOCK + 1, min_periods=1).max().astype(bool)
                  .shift(1, fill_value=False).to_numpy())
    g["unch"] = g.unchanged & ~after_prev[kk, jj]

    def bhar(anchor: np.ndarray, j: np.ndarray, start: int, h: int) -> pd.Series:
        """Fund's compounded return over anchor+start .. anchor+start+h-1 less the CEF market's."""
        assert start >= 2, "a window must open at least two sessions after its decision"
        out = np.full(len(anchor), np.nan)
        for i, (a_, j_) in enumerate(zip(anchor, j)):
            a0, a1 = a_ + start, a_ + start + h
            if a1 <= T:
                out[i] = np.prod(1 + Rn[a0:a1, j_]) - np.prod(1 + mk[a0:a1])
        return pd.Series(out)

    def row(x: pd.Series, cl: pd.Series) -> dict:
        return ex.ev_row(x.reset_index(drop=True), cl.reset_index(drop=True))

    def trimmed(x: pd.Series) -> float:
        x = x.dropna()
        lo, hi = x.quantile(0.01), x.quantile(0.99)
        return float(x[(x >= lo) & (x <= hi)].mean() * 1e4)

    out: dict = {"panel_last_date": str(idx[-1].date()), "not_pre_specified": True}
    for name in ("cut", "raise"):
        ev = g[g[name] & g.elig_k]
        un = g[g.unch & g.elig_k & g.permno.isin(ev.permno.unique())]
        sec: dict = {}
        # 1a. later entry from K
        for skip in (0, 5, 10, 20):
            b = bhar(ev.k.to_numpy(), ev.j.to_numpy(), 2 + skip, 20)
            c = bhar(un.k.to_numpy(), un.j.to_numpy(), 2 + skip, 20)
            sec[f"K: decide {skip} sessions late, hold 20"] = {"events": row(b, ev.ym_k), "unchanged control": row(c, un.ym_k),
                                                             "events_trimmed_1pct_mean_bp": trimmed(b)}
        # 1b. anchored on the ex-date
        evx, unx = g[g[name] & g.elig_x], g[g.unch & g.elig_x & g.permno.isin(ev.permno.unique())]
        evx3, unx3 = g[g[name] & g.elig_x3], g[g.unch & g.elig_x3 & g.permno.isin(ev.permno.unique())]
        for lab, e_, u_, start in (("X: decide at the ex-date close", evx, unx, 2), ("X: decide three sessions after the ex-date", evx3, unx3, 5)):
            for h in (20, 60):
                b = bhar(e_.x.to_numpy(), e_.j.to_numpy(), start, h)
                c = bhar(u_.x.to_numpy(), u_.j.to_numpy(), start, h)
                sec[f"{lab}, hold {h}"] = {"events": row(b, e_.ym_x), "unchanged control": row(c, u_.ym_x),
                                           "events_less_control_mean_bp": float((b.mean() - c.mean()) * 1e4),
                                           "events_trimmed_1pct_mean_bp": trimmed(b)}
        sec["sessions_from_K_to_ex_date"] = {"median": float((ev.x - ev.k).median()), "p10": float((ev.x - ev.k).quantile(0.1)),
                                             "p90": float((ev.x - ev.k).quantile(0.9)),
                                             "share_filled_after_the_ex_date (K+1 >= X)": float((ev.k + 1 >= ev.x).mean())}
        # 2. trimmed, at the pre-specified windows
        for h in (20, 60):
            b = bhar(ev.k.to_numpy(), ev.j.to_numpy(), 2, h)
            sec[f"pre-specified window, hold {h}: mean without top and bottom 1%, bp"] = trimmed(b)
        # 5. how long it lasts
        for lab, start, h in (("K+62..K+121", 62, 60), ("K+122..K+241", 122, 120)):
            sec[f"later: {lab}"] = {"events": row(bhar(ev.k.to_numpy(), ev.j.to_numpy(), start, h), ev.ym_k),
                                    "unchanged control": row(bhar(un.k.to_numpy(), un.j.to_numpy(), start, h), un.ym_k)}
        # by era at the ex-date anchor (the lookahead-proof form), hold 20
        b = bhar(evx.x.to_numpy(), evx.j.to_numpy(), 2, 20)
        kd = pd.Series(idx[evx.x.to_numpy()])
        for a0, a1 in explore.ERAS:
            m = ((kd >= a0) & (kd <= a1)).to_numpy()
            sec[f"X: decide at the ex-date close, hold 20, {a0[:4]}-{min(int(a1[:4]), 2025)}"] = row(b[m], evx.ym_x[m])
        for lab, m in (("taxable", ~evx.muni.astype(bool).to_numpy()), ("municipal", evx.muni.astype(bool).to_numpy())):
            sec[f"X: decide at the ex-date close, hold 20, {lab}"] = row(b[m], evx.ym_x[m])
        out[name] = sec
        print(f"\n== {name}")
        for a_, v in sec.items():
            if isinstance(v, dict) and "events" in v:
                e_, c_ = v["events"], v["unchanged control"]
                print(f"  {a_:58s} n {e_['n']:5d} mean {e_['mean_bp']:+7.1f} med {e_['median_bp']:+7.1f} pos {e_['share_positive']:.1%} t {e_['t_clustered_by_month']:+.2f}"
                      f" | control n {c_['n']:6d} mean {c_['mean_bp']:+6.1f} t {c_['t_clustered_by_month']:+.2f}")
            elif isinstance(v, dict) and "n" in v:
                print(f"  {a_:58s} n {v['n']:5d} mean {v['mean_bp']:+7.1f} med {v['median_bp']:+7.1f} pos {v['share_positive']:.1%} t {v['t_clustered_by_month']:+.2f}")
            else:
                print(f"  {a_}: {v}")

    # 3. the year-end raises that were left out
    ye = g[g.raise_yearend & g.elig_k]
    out["raises left out by the year-end rule"] = {f"hold {h}": row(bhar(ye.k.to_numpy(), ye.j.to_numpy(), 2, h), ye.ym_k) for h in (20, 60)}
    print("\nyear-end raises left out:", json.dumps(out["raises left out by the year-end rule"]))

    # 4. the form a book could hold: taxable raises, calendar time, harness.evaluate
    pc = ex.pcef().reindex(idx)
    books = {}
    for lab, evs, anchor in (("taxable raises, decided at K", g[g["raise"] & g.elig_k & ~g.muni.astype(bool)], "k"),
                             ("taxable raises, decided at the ex-date close", g[g["raise"] & g.elig_x & ~g.muni.astype(bool)], "x"),
                             ("all raises, decided at the ex-date close", g[g["raise"] & g.elig_x], "x")):
        for h in (20, 60):
            w = np.zeros((T, len(cols)), bool)
            for a_, j_ in zip(evs[anchor].to_numpy(), evs.j.to_numpy()):
                w[a_ + 2: min(a_ + 2 + h, T), j_] = True                     # EARNING sessions; decided two sessions before
            n = w.sum(axis=1)
            ne = eln.sum(axis=1)
            on = (n >= ex.MIN_NAMES) & (ne > 0)
            L = np.where(on[:, None], w / np.where(n > 0, n, 1)[:, None], 0.0)
            S = np.where(on[:, None], eln / np.where(ne > 0, ne, 1)[:, None], 0.0)
            H = pd.DataFrame(L - S, index=idx, columns=cols).shift(-harness.EXEC_LAG).fillna(0.0)
            Hl = pd.DataFrame(L, index=idx, columns=cols).shift(-harness.EXEC_LAG).fillna(0.0)
            pnl = harness.evaluate(H, R)["pnl"].iloc[30:-harness.EXEC_LAG]
            lo = harness.evaluate(Hl, R)["pnl"].reindex(pnl.index)
            res = explore.summarise(pnl, controls={"long leg alone, no hedge": lo},
                                    extra={"events": int(len(evs)), "names_long_mean": float(n[on].mean()), "share_days_on": float(on.mean()),
                                           "turnover_per_year_long_leg": float(harness.evaluate(Hl, R)["turn"])})
            vs = (lo - pc.reindex(pnl.index).where(lo != 0, 0.0))
            vs = vs[vs.index.isin(pc.dropna().index)]
            res["long_against_PCEF"] = explore.summarise(vs)
            books[f"{lab}, hold {h}"] = res
            f, p = res["full"], res["long_against_PCEF"]["full"]
            print(f"\n{lab}, hold {h}: n {len(evs)}, names {res['names_long_mean']:.1f}, on {res['share_days_on']:.0%}; vs CEF market Sharpe {f['sharpe']:.2f} t {f['t']:.2f} "
                  f"ret {f['ann_ret']:.2%} vol {f['ann_vol']:.2%} dd {f['max_drawdown']:.1%}; halves {res['early_half']['sharpe']:.2f}/{res['late_half']['sharpe']:.2f}; "
                  f"eras {' '.join(f'{k}:{v['sharpe']:.2f}' for k, v in res['eras'].items())}")
            print(f"   vs PCEF from {p['first']}: Sharpe {p['sharpe']:.2f} t {p['t']:.2f} ret {p['ann_ret']:.2%} vol {p['ann_vol']:.2%}; "
                  f"eras {' '.join(f'{k}:{v['sharpe']:.2f}' for k, v in res['long_against_PCEF']['eras'].items())}; long alone {res['controls']['long leg alone, no hedge']['sharpe']:.2f}")
    out["books_not_pre_specified"] = books
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
