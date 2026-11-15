"""Checks on the follow-on REBOUND book. NONE of this was pre-specified: written after
explore.py had been run once (2026-11-15) and showed the rebound in marketed deals only.

    python3 results/ideas/follow_ons/checks.py

  marketed by era     the REBOUND book on marketed deals (launched before the issue date), by
                      era and half: has it faded as the whole book has?
  marketed, liquid    the same on names trading $5M a day or more at the decision.
  marketed and large  marketed deals of 13% of market value and over.
  regression          the marketed book on IWM and SPY.
  per event           D+3..D+7 summed return less IWM for marketed and overnight deals by era.
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
from scripts.research import explore  # noqa: E402

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("fo_explore", HERE / "explore.py")
ex = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ex)


def main() -> int:
    ev, ret, prc, dv, iwm, sessions = ex.load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy(); R["IWM"] = iwm
    e = ex.place(ev, sessions, prc, adv)
    out = {"note": "not pre-specified; written after the first run", "panel_last_date": str(sessions[-1].date())}
    mk = e[~e["overnight"]]
    sets = {"marketed": mk, "marketed, $5M a day": mk[mk["adv_dec"] >= 5e6],
            "marketed, 13% of market value and over": mk[mk["rel_size"] >= 0.13],
            "marketed, 13% and over, $5M a day": mk[(mk["rel_size"] >= 0.13) & (mk["adv_dec"] >= 5e6)]}
    for k, sub in sets.items():
        p, m = ex.run(sub, "rebound", sessions, R)
        o = {"full": explore.stats(p), "events_traded": m["events_traded"], "share_of_days_invested": m["share_of_days_invested"],
             "by_era": {a: explore.stats(p.loc[lo:hi]) for a, (lo, hi) in ex.ERAS.items()}}
        if k == "marketed":
            yf = pd.read_parquet(ex.RES / "yf_daily.parquet")
            spy = yf[yf["ticker"] == "SPY"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"].reindex(sessions)
            d = pd.concat([p.rename("y"), iwm.rename("IWM"), spy.rename("SPY")], axis=1).dropna()
            A = np.column_stack([np.ones(len(d)), d[["IWM", "SPY"]].to_numpy()])
            b, *_ = np.linalg.lstsq(A, d["y"].to_numpy(), rcond=None)
            r = d["y"].to_numpy() - A @ b
            cov = np.linalg.inv(A.T @ A) * (r @ r) / (len(d) - 3)
            o["regression"] = {"alpha_per_year": float(b[0] * 252), "alpha_t": float(b[0] / np.sqrt(cov[0, 0])), "beta_IWM": float(b[1]), "beta_SPY": float(b[2])}
            print("  regression:", {a: round(v, 3) for a, v in o["regression"].items()})
        out[k] = o
        print(f"  {k}: SR {o['full']['sharpe']:.2f} t {o['full']['t']:.2f} n {o['events_traded']} invested {o['share_of_days_invested']:.0%} | " +
              " | ".join(f"{a}: {v['sharpe']:.2f} ({v['t']:.1f})" for a, v in o["by_era"].items()))
    rn, im = ret.to_numpy(), iwm.to_numpy()
    el = e[e["ok"] & (e["d"] + 7 < len(sessions))]
    cp = ret.columns.get_indexer(el["permno"])
    ep = pd.Series([float(np.nansum(rn[d + 3:d + 8, c] - im[d + 3:d + 8])) for d, c in zip(el["d"].to_numpy(), cp)], index=el.index)
    yr = pd.Series(sessions[el["d"].to_numpy()].year, index=el.index)
    month = pd.Series(sessions[el["d"].to_numpy()].to_period("M"), index=el.index)
    out["per_event_pct"] = {}
    for kind, mask in (("marketed", ~el["overnight"]), ("overnight", el["overnight"])):
        for a, (lo, hi) in ex.ERAS.items():
            s = mask & (yr >= int(lo)) & (yr <= int(hi))
            m = ep[s].groupby(month[s]).mean()
            out["per_event_pct"][f"{kind} {a}"] = {"n": int(s.sum()), "mean": float(ep[s].mean() * 100), "median": float(ep[s].median() * 100),
                                                   "t_by_month": float(m.mean() / m.std() * np.sqrt(len(m)))}
            v = out["per_event_pct"][f"{kind} {a}"]
            print(f"  per event {kind} {a}: n {v['n']} mean {v['mean']:+.2f}% median {v['median']:+.2f}% t {v['t_by_month']:+.1f}")
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__" and "--gap" not in sys.argv:
    sys.exit(main())


def by_gap() -> dict:
    """REBOUND by the number of sessions between SDC's launch date and its issue date (added
    2026-11-15, after the checks above). 'Launched before the issue date' turned out to mix
    deals announced the evening before pricing (gap 1) with deals marketed for days."""
    ev, ret, prc, dv, iwm, sessions = ex.load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy(); R["IWM"] = iwm
    e = ex.place(ev, sessions, prc, adv)
    gap = sessions.get_indexer(e["issue_date"]) - sessions.searchsorted(e["launch"].to_numpy(), side="left")
    e["g"] = pd.cut(gap, [-1, 0, 1, 3, 10, 10_000], labels=["0", "1", "2-3", "4-10", "11+"])
    out = {}
    for g in ["0", "1", "2-3", "4-10", "11+"]:
        p, m = ex.run(e[e["g"] == g], "rebound", sessions, R)
        out[g] = {**explore.stats(p), "events_traded": m["events_traded"],
                  "by_era": {a: explore.stats(p.loc[lo:hi])["sharpe"] for a, (lo, hi) in ex.ERAS.items()}}
        print(f"  gap {g}: SR {out[g]['sharpe']:.2f} t {out[g]['t']:.2f} n {m['events_traded']} | " +
              " | ".join(f"{a}: {v:.2f}" for a, v in out[g]["by_era"].items()))
    return out


if __name__ == "__main__" and "--gap" in sys.argv:
    j = json.loads((HERE / "checks.json").read_text())
    j["rebound_by_sessions_from_launch_to_issue"] = by_gap()
    (HERE / "checks.json").write_text(json.dumps(j, indent=1))
