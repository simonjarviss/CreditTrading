"""Checks on etf_twins that were NOT pre-specified (run after explore.py's results were read).

    python3 results/ideas/etf_twins/checks.py

WHY: explore.py found about 1bp per event left after shift(2) against a 7.5bp closing
spread. Before closing the idea, three places an effect could still hide were looked at,
each scored on closing MIDS (signal and P&L), the only prices the first run showed can be
trusted:
  1. the thinnest funds only ($0.2M to $2M a day at formation), where big money is most absent;
  2. large gaps only (|z| >= 4);
  3. a slower signal: the 5-session cumulative gap (|z| >= 2 on 5-session return sums),
     in case the pair drifts apart over days and comes back, not over one close.
Each is a second look at the same data and is labelled as such on the card. Writes
checks.json (aggregates only).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import explore as X  # noqa: E402  (the idea's own explore.py; it imports scripts.research.explore)

assert pd.get_option("compute.use_numexpr") is False


def main() -> int:
    dates, permnos, ret, mret, prc, vol, dv, spread = X.load()
    allp, month_last = X.form_pairs(dates, ret, prc, vol, dv)
    twins = allp[(allp["kind"] == "thin") & (allp["corr"] >= X.CORR_MIN)]
    quoted = np.isfinite(mret)
    mfill = np.where(np.isnan(mret), ret, mret)
    ev = X.find_events(twins, month_last, mret, quoted)
    key = twins.set_index(["i", "thin"])["dv_thin"]
    # the formation month of an event: the last month-end strictly before t
    ev["i"] = month_last[np.searchsorted(month_last, ev["t"].to_numpy(), side="left") - 1]
    assert (ev["i"] < ev["t"]).all()
    ev["dv_form"] = key.reindex(pd.MultiIndex.from_frame(ev[["i", "thin"]])).to_numpy()
    if ev["dv_form"].isna().any():
        raise ValueError("an event has no formation row")
    # 5-session sums of mid returns, a session's sum uses sessions t-4 .. t
    s5 = pd.DataFrame(mret).rolling(5, min_periods=5).sum().to_numpy()
    ev5 = X.find_events(twins, month_last, s5, np.isfinite(s5))
    sets = {"B again (all twins, mids)": ev, "1. thin leg $0.2M-$2M a day": ev[ev["dv_form"] <= 2e6],
            "2. |z| >= 4": ev[ev["z"].abs() >= 4], "3. 5-session cumulative gap": ev5}
    out = {}
    for name, e in sets.items():
        e = e.reset_index(drop=True)
        p, info = X.book(e, dates, mfill)
        s = X.explore.summarise(p)
        t, a = e["t"].to_numpy(), e["thin"].to_numpy()
        pe = X.per_event(e, dates, mfill)
        out[name] = {"events": int(len(e)), "median_closing_spread_bp": float(np.nanmedian(spread[t, a]) * 1e4),
                     "median_dollar_volume": float(np.nanmedian(dv[t, a])), "median_abs_gap_bp": float(e["d"].abs().median() * 1e4),
                     "turnover_per_year": info["turnover_per_year"], "mean_gross_per_side": info["mean_gross_per_side"],
                     "sharpe": s["full"]["sharpe"], "t": s["full"]["t"], "ann_ret": s["full"]["ann_ret"], "ann_vol": s["full"]["ann_vol"],
                     "halves": [s["early_half"]["sharpe"], s["late_half"]["sharpe"]],
                     "eras": {k: v["sharpe"] for k, v in s["eras"].items()}, "per_event_mids_t+2..t+6": pe,
                     "decay_on_mids": X.decay(e, dates, mret)}
        o = out[name]
        print(f"\n{name}: {o['events']:,} events, spread {o['median_closing_spread_bp']:.1f}bp, ${o['median_dollar_volume']:,.0f}, gap {o['median_abs_gap_bp']:.0f}bp, "
              f"gross a side {o['mean_gross_per_side']:.2f}; SR {o['sharpe']:.2f} (t {o['t']:.2f}), {o['ann_ret']:.2%}/{o['ann_vol']:.2%}, halves {o['halves'][0]:.2f}/{o['halves'][1]:.2f}")
        print("  eras " + "  ".join(f"{k} {v:.2f}" for k, v in o["eras"].items()))
        print(f"  per event t+2..t+6 on mids: mean {pe['mean_bp']:.1f}bp, median {pe['median_bp']:.1f}bp, {pe['share_positive']:.1%} positive, t {pe['t_on_day_means']:.1f}")
        print("  decay on mids: " + "  ".join(f"{k} {v['mean_bp']:.1f} ({v['t_on_day_means']:.1f})" for k, v in o["decay_on_mids"].items()))
    (HERE / "checks.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
