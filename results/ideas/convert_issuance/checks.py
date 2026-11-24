"""Checks on the convertible-issue REBOUND book. NONE pre-specified: written after explore.py
had been run once (2026-11-15). Nothing here changes that book.

    python3 results/ideas/convert_issuance/checks.py

  regression    the book on IWM and SPY: alpha, t, betas.
  per event     D+3..D+7 summed return less IWM: mean, median, share positive, by era.
  best events   the book without its ten best events.
  late start    the same five-session hold begun one and two sessions later (D+4..D+8,
                D+5..D+9): SDC's issue date is a pricing date and the desk has no check of
                it against filings, so a result that needs the exact day is not usable.
  one earlier   D+2..D+6, descriptive: what the session the book cannot reach is worth.
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
_spec = importlib.util.spec_from_file_location("cv_explore", HERE / "explore.py")
cv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(cv)
fo = cv.fo


def main() -> int:
    ev, ret, prc, dv, iwm, sessions = cv.load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy(); R["IWM"] = iwm
    e = fo.place(ev, sessions, prc, adv)
    pnl, _ = fo.run(e, "rebound", sessions, R)
    out = {"note": "not pre-specified; written after the first run", "panel_last_date": str(sessions[-1].date())}
    yf = pd.read_parquet(fo.RES / "yf_daily.parquet")
    spy = yf[yf["ticker"] == "SPY"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"].reindex(sessions)
    d = pd.concat([pnl.rename("y"), iwm.rename("IWM"), spy.rename("SPY")], axis=1).dropna()
    A = np.column_stack([np.ones(len(d)), d[["IWM", "SPY"]].to_numpy()])
    b, *_ = np.linalg.lstsq(A, d["y"].to_numpy(), rcond=None)
    r = d["y"].to_numpy() - A @ b
    cov = np.linalg.inv(A.T @ A) * (r @ r) / (len(d) - 3)
    out["regression"] = {"alpha_per_year": float(b[0] * 252), "alpha_t": float(b[0] / np.sqrt(cov[0, 0])), "beta_IWM": float(b[1]), "beta_SPY": float(b[2])}
    rn, im = ret.to_numpy(), iwm.to_numpy()
    el = e[e["ok"] & (e["d"] + 7 < len(sessions))]
    cp = ret.columns.get_indexer(el["permno"])
    ep = pd.Series([float(np.nansum(rn[x + 3:x + 8, c] - im[x + 3:x + 8])) for x, c in zip(el["d"].to_numpy(), cp)], index=el.index)
    yr = pd.Series(sessions[el["d"].to_numpy()].year, index=el.index)
    month = pd.Series(sessions[el["d"].to_numpy()].to_period("M"), index=el.index)
    m = ep.groupby(month).mean()
    out["per_event_pct"] = {"n": int(len(ep)), "mean": float(ep.mean() * 100), "median": float(ep.median() * 100),
                            "share_positive": float((ep > 0).mean()), "t_by_month": float(m.mean() / m.std() * np.sqrt(len(m))),
                            "p5": float(ep.quantile(.05) * 100), "p95": float(ep.quantile(.95) * 100)}
    out["per_event_by_era"] = {}
    for a, (lo, hi) in fo.ERAS.items():
        s = (yr >= int(lo)) & (yr <= int(hi))
        mm = ep[s].groupby(month[s]).mean()
        out["per_event_by_era"][a] = {"n": int(s.sum()), "mean": float(ep[s].mean() * 100), "median": float(ep[s].median() * 100),
                                      "t_by_month": float(mm.mean() / mm.std() * np.sqrt(len(mm)))}
    out["without_ten_best_events"] = explore.stats(fo.run(e.drop(index=ep.nlargest(10).index), "rebound", sessions, R)[0])
    base = fo.BOOKS["rebound"]
    for label, (a, b_) in {"one_session_later": (4, 8), "two_sessions_later": (5, 9)}.items():
        fo.BOOKS["rebound"] = (a, b_, 1.0)
        try:
            p = fo.run(e, "rebound", sessions, R)[0]
        finally:
            fo.BOOKS["rebound"] = base
        out[label] = {**explore.stats(p), "by_era": {k: explore.stats(p.loc[lo:hi])["sharpe"] for k, (lo, hi) in fo.ERAS.items()}}
    # D+2..D+6: the pre-specified window moved one session earlier. Its first weight row is D
    # itself, before the decision row, so no book could hold it; `shift` lifts that guard.
    p = fo.run(e, "rebound", sessions, R, shift=-1)[0]
    out["one_session_earlier_not_reachable"] = {**explore.stats(p), "by_era": {k: explore.stats(p.loc[lo:hi])["sharpe"] for k, (lo, hi) in fo.ERAS.items()}}
    for k, v in out.items():
        if isinstance(v, dict) and "sharpe" in v:
            print(f"  {k}: SR {v['sharpe']:.2f} t {v['t']:.2f} ret/yr {v['ann_ret']:.2%}" + (" | " + " ".join(f"{a}:{x:.2f}" for a, x in v["by_era"].items()) if "by_era" in v else ""))
        elif isinstance(v, dict):
            print(f"  {k}:", json.dumps({a: (round(x, 3) if isinstance(x, float) else x) for a, x in v.items()}))
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
