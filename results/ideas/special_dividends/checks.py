"""Checks on the special-dividend result. NONE of this was pre-specified: it was written
after results/ideas/special_dividends/explore.py had been run once (2026-11-15), to find out
whether the WAIT and AFTER books are an artifact. Nothing here changes those books.

    python3 results/ideas/special_dividends/checks.py

  beta        each book regressed on IWM and SPY daily returns; alpha and its t.
  best events the book with its ten best events (by summed P&L contribution) removed.
  liquidity   the same book on events with 21-session dollar volume >= $5M and >= $20M
              (a $10M book at 10% a name is $1M a name: 5% of a $20M day).
  wait split  WAIT's earning sessions cut in two: the first three (drift after the news)
              and the rest (the run-up into the ex-date).
  per event   the distribution of WAIT's summed return less IWM, per event.
  bills       WAIT and AFTER less the 13-week bill are not computed: both books are
              dollar-neutral (IWM is the other side), so there is no cash leg to charge.
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
_spec = importlib.util.spec_from_file_location("sd_explore", HERE / "explore.py")
ex = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ex)


def ols(y: pd.Series, X: pd.DataFrame) -> dict:
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    A = np.column_stack([np.ones(len(d)), d[X.columns].to_numpy()])
    b, *_ = np.linalg.lstsq(A, d["y"].to_numpy(), rcond=None)
    e = d["y"].to_numpy() - A @ b
    cov = np.linalg.inv(A.T @ A) * (e @ e) / (len(d) - A.shape[1])
    return {"alpha_per_year": float(b[0] * 252), "alpha_t": float(b[0] / np.sqrt(cov[0, 0])),
            **{f"beta_{c}": float(v) for c, v in zip(X.columns, b[1:])}}


def event_pnl(e, which, sessions, R) -> pd.Series:
    """Each traded event's own summed contribution (name leg and its IWM hedge), no cap scaling."""
    L = harness.EXEC_LAG
    r, iwm = R.drop(columns="IWM"), R["IWM"].to_numpy()
    rn = r.fillna(0.0).to_numpy()
    cpos = r.columns.get_indexer(e["permno"])
    out = {}
    for i, x, d1, c, ok in zip(e.index, e["x"].to_numpy(), e["d1"].to_numpy(), cpos, e[f"ok_{which}"].to_numpy()):
        if not ok:
            continue
        first, last, side = (d1 + L, x - 1, 1.0) if which == "wait" else (x + 1, min(x + ex.AFTER_HOLD, len(rn) - 1), -1.0)
        if last < first or first - L < d1:
            continue
        out[i] = side * float((rn[first:last + 1, c] - iwm[first:last + 1]).sum())
    return pd.Series(out)


def main() -> int:
    ev, ret, prc, dv, iwm, sessions = ex.load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy(); R["IWM"] = iwm
    yf = pd.read_parquet(ex.RES / "yf_daily.parquet")
    spy = yf[yf["ticker"] == "SPY"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"].reindex(sessions)
    sd = ex.place(ev[ev["distype"] == "SD"], sessions, prc, adv, min_yield=ex.MIN_YIELD)
    advn, cols = adv.to_numpy(), prc.columns.get_indexer(sd["permno"])
    out = {"note": "not pre-specified; written after the first run", "panel_last_date": str(sessions[-1].date())}
    for which, drow in (("wait", sd["d1"]), ("after", sd["x"] - 1)):
        pnl, meta = ex.run(sd, which, sessions, R)
        o = {"base": explore.stats(pnl), "regression": ols(pnl, pd.DataFrame({"IWM": iwm, "SPY": spy}))}
        ep = event_pnl(sd, which, sessions, R)
        o["per_event_pct"] = {"n": int(len(ep)), "mean": float(ep.mean() * 100), "median": float(ep.median() * 100),
                              "share_positive": float((ep > 0).mean()), "p5": float(ep.quantile(.05) * 100),
                              "p95": float(ep.quantile(.95) * 100), "worst": float(ep.min() * 100), "best": float(ep.max() * 100),
                              "t_by_decision_month": None}
        m = ep.groupby(sessions[drow.loc[ep.index].to_numpy()].to_period("M")).mean()
        o["per_event_pct"]["t_by_decision_month"] = float(m.mean() / m.std() * np.sqrt(len(m)))
        best = ep.nlargest(10).index
        o["without_ten_best_events"] = explore.stats(ex.run(sd.drop(index=best), which, sessions, R)[0])
        a_dec = advn[np.clip(drow.to_numpy(), 0, len(advn) - 1), cols]
        for label, floor in (("adv_5m", 5e6), ("adv_20m", 2e7)):
            sub = sd[a_dec >= floor]
            p2, m2 = ex.run(sub, which, sessions, R)
            o[label] = {**explore.stats(p2), "events_traded": m2["events_traded"], "share_of_days_invested": m2["share_of_days_invested"]}
        o["late_2023_on"] = explore.stats(pnl.loc["2023-01-01":])
        out[which] = o
        print(f"\n== {which}")
        print("  regression:", {k: round(v, 3) for k, v in o["regression"].items()})
        print("  per event %:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in o["per_event_pct"].items()})
        for k in ("base", "without_ten_best_events", "adv_5m", "adv_20m"):
            s = o[k]
            print(f"  {k}: SR {s['sharpe']:.2f} t {s['t']:.2f} ret/yr {s['ann_ret']:.2%} dd {s['max_drawdown']:.1%}" + (f" events {s['events_traded']} invested {s['share_of_days_invested']:.0%}" if "events_traded" in s else ""))
    # WAIT cut in two by earning session
    L = harness.EXEC_LAG
    for label, (a, b) in {"first_three_sessions": (0, 2), "the_rest": (3, 10_000)}.items():
        W = np.zeros((len(sessions), ret.shape[1]))
        for x, d1, c, ok in zip(sd["x"].to_numpy(), sd["d1"].to_numpy(), cols, sd["ok_wait"].to_numpy()):
            first, last = d1 + L + a, min(d1 + L + b, x - 1)
            if ok and last >= first and x - 1 >= d1 + L:
                W[first - L:last - L + 1, c] += ex.UNIT
        tot = W.sum(axis=1)
        W *= np.where(tot > ex.SIDE_CAP, ex.SIDE_CAP / np.where(tot > 0, tot, 1), 1.0)[:, None]
        H = pd.DataFrame(W, index=sessions, columns=ret.columns); H["IWM"] = -H.sum(axis=1)
        p = harness.evaluate(H, R.fillna(0.0))["pnl"].iloc[L:]
        out[f"wait_{label}"] = explore.stats(p)
        print(f"  wait, {label}: SR {out[f'wait_{label}']['sharpe']:.2f} t {out[f'wait_{label}']['t']:.2f} ret/yr {out[f'wait_{label}']['ann_ret']:.2%}")
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__" and "--shifted" not in sys.argv:
    sys.exit(main())


def shifted_controls() -> dict:
    """WAIT on the same names with the whole window moved in time (added 2026-11-15, after the
    checks above): do companies that pay specials simply beat IWM around then, whatever the
    date? Eligibility flags are the real event's, read at its own decision date; only the
    holding window moves, so the names and the window lengths are identical."""
    ev, ret, prc, dv, iwm, sessions = ex.load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy(); R["IWM"] = iwm
    sd = ex.place(ev[ev["distype"] == "SD"], sessions, prc, adv, min_yield=ex.MIN_YIELD)
    out = {}
    for k in (-60, -40, -20, 20, 40, 60):
        e = sd.copy()
        e["d1"] += k; e["x"] += k
        e = e[(e["d1"] >= 0) & (e["x"] < len(sessions) - 1)]
        p, m = ex.run(e, "wait", sessions, R)
        out[f"{k:+d}"] = {**explore.stats(p), "events_traded": m["events_traded"]}
        print(f"  wait window moved {k:+d} sessions: SR {out[f'{k:+d}']['sharpe']:.2f} t {out[f'{k:+d}']['t']:.2f} ret/yr {out[f'{k:+d}']['ann_ret']:.2%} events {m['events_traded']}")
    return out


if __name__ == "__main__" and "--shifted" in sys.argv:
    j = json.loads((HERE / "checks.json").read_text())
    j["wait_window_moved"] = shifted_controls()
    (HERE / "checks.json").write_text(json.dumps(j, indent=1))
