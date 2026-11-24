"""Checks on the reverse-split AFTER short. NONE of this was pre-specified: written after
explore.py had been run once (2026-11-15). Nothing here changes that book.

    python3 results/ideas/reverse_splits/checks.py

  regression   the book on IWM and SPY daily returns: alpha, its t, the betas.
  per event    each event's own summed return (name less IWM, sign of the short), no cap
               scaling: mean, median, share positive, tails. A short can lose more than 100%.
  best events  the book without its ten best events.
  split        the twenty earning sessions cut into the first five and the other fifteen.
  excess       the book less the mean of the two moved-window controls (60 sessions earlier
               and later): what the event adds to a share that is falling anyway.
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
_spec = importlib.util.spec_from_file_location("rs_explore", HERE / "explore.py")
ex = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ex)


def main() -> int:
    ev, ret, prc, dv, iwm, sessions = ex.load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy(); R["IWM"] = iwm
    yf = pd.read_parquet(ex.RES / "yf_daily.parquet")
    spy = yf[yf["ticker"] == "SPY"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"].reindex(sessions)
    rs = ex.place(ev[ev["facpr"] < 0], sessions, prc, adv)
    pnl, _ = ex.run(rs, "after", sessions, R)
    out = {"note": "not pre-specified; written after the first run", "panel_last_date": str(sessions[-1].date())}
    d = pd.concat([pnl.rename("y"), iwm.rename("IWM"), spy.rename("SPY")], axis=1).dropna()
    A = np.column_stack([np.ones(len(d)), d[["IWM", "SPY"]].to_numpy()])
    b, *_ = np.linalg.lstsq(A, d["y"].to_numpy(), rcond=None)
    e = d["y"].to_numpy() - A @ b
    cov = np.linalg.inv(A.T @ A) * (e @ e) / (len(d) - 3)
    out["regression"] = {"alpha_per_year": float(b[0] * 252), "alpha_t": float(b[0] / np.sqrt(cov[0, 0])),
                         "beta_IWM": float(b[1]), "beta_SPY": float(b[2])}
    L = harness.EXEC_LAG
    rn, im = ret.fillna(0.0).to_numpy(), iwm.to_numpy()
    el = rs[rs["ok_after"]]
    cp = ret.columns.get_indexer(el["permno"])
    ep = pd.Series({i: -float((rn[x + L:x + L + ex.HOLD, c] - im[x + L:x + L + ex.HOLD]).sum())
                    for i, x, c in zip(el.index, el["x"].to_numpy(), cp) if x + L < len(rn)})
    m = ep.groupby(sessions[el.loc[ep.index, "x"].to_numpy()].to_period("M")).mean()
    out["per_event_pct"] = {"n": int(len(ep)), "mean": float(ep.mean() * 100), "median": float(ep.median() * 100),
                            "share_positive": float((ep > 0).mean()), "p5": float(ep.quantile(.05) * 100),
                            "p95": float(ep.quantile(.95) * 100), "worst": float(ep.min() * 100), "best": float(ep.max() * 100),
                            "t_by_month": float(m.mean() / m.std() * np.sqrt(len(m)))}
    out["without_ten_best_events"] = explore.stats(ex.run(rs.drop(index=ep.nlargest(10).index), "after", sessions, R)[0])
    out["without_ten_worst_events"] = explore.stats(ex.run(rs.drop(index=ep.nsmallest(10).index), "after", sessions, R)[0])
    hold0 = ex.HOLD
    for label, (skip, n) in {"first_five_sessions": (0, 5), "other_fifteen": (5, 15)}.items():
        e2 = rs.copy(); e2["x"] = e2["x"] + skip      # eligibility flags stay the real ex-date's
        ex.HOLD = n
        out[label] = explore.stats(ex.run(e2, "after", sessions, R)[0])
        ex.HOLD = hold0
    later, earlier = ex.run(rs, "after", sessions, R, shift=60)[0], ex.run(rs, "after", sessions, R, shift=-60)[0]
    out["less_mean_of_moved_controls"] = explore.stats(pnl - (later + earlier) / 2)
    for k, v in out.items():
        if isinstance(v, dict) and "sharpe" in v:
            print(f"  {k}: SR {v['sharpe']:.2f} t {v['t']:.2f} ret/yr {v['ann_ret']:.2%}")
        elif isinstance(v, dict):
            print(f"  {k}:", {a: round(x, 3) for a, x in v.items()})
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
