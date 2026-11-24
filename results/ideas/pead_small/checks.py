"""Checks on the small-stock earnings-drift LONG LEG (surprise sort). NONE pre-specified:
written 2026-11-15 after explore.py's first run and after an independent review, to store in
the repository the review's main probes and the version a free live feed could run.

    python3 results/ideas/pead_small/checks.py

  own universe   the long tenth less the equal-weighted return of its own eligible universe
                 (rank 1,501-4,000, $5, $500k), instead of IWM.
  late timing    every release treated as known only at the session AFTER its date (the
                 review found pre-open time stamps in 2000-08 that behave like after-close
                 releases); and the signal started one and two sessions later still.
  free feed      the sort a free feed can reproduce: (actual - consensus) / |consensus|,
                 consensus magnitude at least $0.05 a share (a free source gives the
                 estimate and the reported figure, not the analysts' dispersion). Both IBES
                 fields are split-adjusted to the same basis, so the ratio is safe; dividing
                 by an unadjusted price is NOT (the review measured that bug at 0.13).
  cost grid      the long leg's stock side at 5 / 15 / 30bp per unit traded: the real-money
                 view, labelled, never mixed with the gross figures.
  rank bands     1,501-2,500 and 2,501-4,000 separately, each less its own universe.
"""
from __future__ import annotations

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
_spec = importlib.util.spec_from_file_location("ps", HERE / "explore.py")
ps = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ps)
pw = ps.pw
ERAS = {"2002-08": ("2002", "2008"), "2009-15": ("2009", "2015"), "2016-19": ("2016", "2019"), "2020-22": ("2020", "2022"), "2023-25": ("2023", "2025")}


def main() -> int:
    df = pd.read_parquet(ps.PANEL, columns=["permno", "date", "ret", "prc", "cap_rank", "dollar_volume"])
    df["date"] = pd.to_datetime(df["date"])
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc").astype("float32")
    rank = df.pivot(index="date", columns="permno", values="cap_rank").astype("float32")
    adv = df.pivot(index="date", columns="permno", values="dollar_volume").rolling(21, min_periods=10).mean()
    del df
    band = (rank > ps.RANK_LO) & (rank <= ps.RANK_HI)
    ok = band & (prc >= ps.MIN_PRICE) & (adv >= ps.MIN_ADV)
    R = ret.fillna(0.0)
    yf = pd.read_parquet(ps.RES / "yf_daily.parquet")
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"].reindex(ret.index)
    L = harness.EXEC_LAG
    ev0 = pd.read_parquet(pw.EVENTS)
    ev0 = ev0[ev0["permno"].isin(ret.columns)].copy()
    sessions = ret.index

    def long_series(ev, field, ok_, *, delay=0):
        """(long tenth's own daily return, its weights) for one sort; the leg is NOT hedged here."""
        e = ev.dropna(subset=[field, "t"]).sort_values(["t", "anndats"]).drop_duplicates(["t", "permno"], keep="last")
        S = e.pivot(index="t", columns="permno", values=field).reindex(index=sessions, columns=ret.columns)
        H = pw.book(S.shift(delay).ffill(limit=ps.HOLD - 1).where(ok_))
        side = H.clip(lower=0.0)
        tot = side.sum(axis=1)
        side = side.div(tot.where(tot > 1e-12), axis=0).fillna(0.0)
        ev_ = harness.evaluate(side, R)
        return ev_["pnl"], side, float(ev_["turn"])

    def universe(ok_):
        w = ok_.astype(float)
        w = w.div(w.sum(axis=1).where(w.sum(axis=1) > 0), axis=0).fillna(0.0)
        return harness.evaluate(w, R)["pnl"]

    def report(label, long_pnl, bench, out):
        p = (long_pnl - bench).loc["2000-06-01":].dropna()
        s = explore.stats(p)
        out[label] = {**s, "by_era": {k: explore.stats(p.loc[a:b])["sharpe"] for k, (a, b) in ERAS.items()},
                      "halves": [explore.stats(p.iloc[:len(p) // 2])["sharpe"], explore.stats(p.iloc[len(p) // 2:])["sharpe"]]}
        print(f"  {label}: SR {s['sharpe']:.2f} t {s['t']:.2f} ret/yr {s['ann_ret']:.2%} | halves {out[label]['halves'][0]:.2f}/{out[label]['halves'][1]:.2f} | " +
              " ".join(f"{k}:{v:.2f}" for k, v in out[label]["by_era"].items()))

    out = {"note": "not pre-specified; after the first run and an independent review", "panel_last_date": str(sessions[-1].date())}
    iw = iwm.shift(0)                      # IWM's return on the earning session, as the hedge earns it
    ev = ev0.copy(); ev["t"] = pw.known_session(ev, sessions)
    uni = universe(ok)
    base, side, turn = long_series(ev, "suescore", ok)
    report("base, less IWM", base, iw, out)
    report("base, less own universe", base, uni, out)
    for k in (1, 2):
        report(f"signal {k} session(s) later, less IWM", long_series(ev, "suescore", ok, delay=k)[0], iw, out)
    late = ev0.copy()
    i = sessions.searchsorted(pd.to_datetime(late["anndats"]).values, side="right")
    late["t"] = pd.NaT
    good = i < len(sessions)
    late.loc[good, "t"] = sessions[i[good]]
    late["t"] = pd.to_datetime(late["t"])
    lp = long_series(late, "suescore", ok)[0]
    report("every release known the session after its date, less IWM", lp, iw, out)
    report("every release known the session after its date, less own universe", lp, uni, out)
    free = late.copy()                     # the free-feed version also takes the later timing
    free["pct"] = np.where(free["surpmean"].abs() >= 0.05, (free["actual"] - free["surpmean"]) / free["surpmean"].abs(), np.nan)
    fp, fside, fturn = long_series(free, "pct", ok)
    report("free-feed sort (surprise / |consensus|), late timing, less IWM", fp, iw, out)
    report("free-feed sort (surprise / |consensus|), late timing, less own universe", fp, uni, out)
    out["free_feed_events_with_signal"] = int(free["pct"].notna().sum())
    for label, lo, hi in (("rank 1,501-2,500", 1500, 2500), ("rank 2,501-4,000", 2500, 4000)):
        okb = ok & (rank > lo) & (rank <= hi)
        report(f"{label}, less its own universe", long_series(ev, "suescore", okb)[0], universe(okb), out)
    # cost grid on the stock side of the base long leg (real-money view)
    traded = side.diff().abs().sum(axis=1).shift(L)          # what the book traded to hold the weights that earn today
    out["long_leg_turnover_per_year"] = turn
    for bp in (5, 15, 30):
        p = (base - iw - traded.fillna(0.0) * bp / 1e4).loc["2000-06-01":].dropna()
        out[f"net_of_{bp}bp_less_IWM"] = explore.stats(p)
        print(f"  real-money view, {bp}bp per unit traded (stock side only): SR {out[f'net_of_{bp}bp_less_IWM']['sharpe']:.2f} ret/yr {out[f'net_of_{bp}bp_less_IWM']['ann_ret']:.2%}")
    print("  long-leg turnover a year:", round(turn, 1), "| free-feed events:", out["free_feed_events_with_signal"])
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
