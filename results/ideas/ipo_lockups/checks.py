"""Descriptive checks on the lock-up result. NOT pre-specified: written after explore.py had
been run once (2026-11-15), to see whether the weak second half is in the events themselves
or in the book's construction. Nothing here is a trading rule.

    python3 results/ideas/ipo_lockups/checks.py

Per eligible event, the stock's return less IWM summed over two windows around L (the first
session on or after the lock-up date): the pre-specified L-1..L+1, and L-4..L, which is
where the event-time profile put the fall. Means by era, t clustered by expiry month.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("lock_explore", HERE / "explore.py")
ex = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ex)
ERAS = (("2000", "2008"), ("2009", "2015"), ("2016", "2019"), ("2020", "2022"), ("2023", "2025"))


def main() -> int:
    ev, ret, prc, dv, iwm, sessions = ex.load()
    adv = dv.rolling(21, min_periods=10).mean()
    e = ex.place(ev, sessions, prc, adv)
    e = e[e["ok"]]
    rel = ret.sub(iwm, axis=0).fillna(0.0).to_numpy()
    cpos = ret.columns.get_indexer(e["permno"])
    out = {"note": "not pre-specified; descriptive", "panel_last_date": str(sessions[-1].date())}
    for name, (a, b) in {"L-1..L+1": (-1, 1), "L-4..L": (-4, 0)}.items():
        s = pd.Series([rel[l + a:l + b + 1, c].sum() for l, c in zip(e["l"].to_numpy(), cpos)], index=sessions[e["l"].to_numpy()]).sort_index()
        rows = {}
        for lo, hi in (("2000", "2025"),) + ERAS:
            v = s.loc[lo:hi]
            m = v.groupby(v.index.to_period("M")).mean()
            rows[f"{lo}-{hi}"] = {"n": int(len(v)), "mean_pct": float(v.mean() * 100), "median_pct": float(v.median() * 100),
                                  "share_negative": float((v < 0).mean()),
                                  "t_by_month": float(m.mean() / m.std() * np.sqrt(len(m))) if len(m) > 2 else None}
        out[name] = rows
        print(name, " | ".join(f"{k}: {r['mean_pct']:+.2f}% (t {r['t_by_month']:+.1f}, n {r['n']}, {r['share_negative']:.0%} down)" for k, r in rows.items()))
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
