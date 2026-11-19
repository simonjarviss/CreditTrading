"""Checks after the fact on the leveraged-ETF footprint test. NOT PRE-SPECIFIED: written
after explore.py showed a next-day (t+1) give-back in the INDEX group that grows with the
flow share and nothing in the window the desk can trade (t+2..t+3).

    python3 results/ideas/levered_etf_reversal/checks.py

WHY: the t+1 result is the only live thing in the test, so before it is written down as
"real but untradable here" it should survive four questions.
  1. ERAS: is the t+1 give-back there in every era, for events (S >= 10%) and for the top
     bucket (S >= 25%), and absent in control A in the same eras?
  2. CONCENTRATION: is it a few underlyings? Mean by underlying, and the mean without the
     three with the most events.
  3. BOUNCE: is it bid-ask bounce in the underlying ETF's close? Rescore t+1 from t's
     closing MID quote to t+1's closing MID quote (CRSP closing bid and ask), which holds no
     bounce, less SPY's close-to-close return.
  4. SIZE IF IT COULD BE CAUGHT: the same 10%-per-event book held over t+1 only, as if it
     were filled at t's own close. The desk cannot do this (the flow is only known at the
     close it would have to trade in); it is here to size what is being left behind, and it
     is computed outside harness.evaluate on purpose, because the harness lag is not a knob.
Appends "checks" to results.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import explore as ex  # noqa: E402
from scripts.research import explore  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
START = "2007-01-03"


def main() -> int:
    etf = pd.read_parquet(ex.OUT / "etf_daily.parquet")
    etf["date"] = pd.to_datetime(etf["date"]); etf["year"] = etf["date"].dt.year
    etf["aum_lag"] = (etf["shrout"] * 1000.0 * etf["prc"]).groupby(etf["permno"]).shift(1)
    sessions = pd.DatetimeIndex(sorted(etf["date"].unique()))
    spy = etf[(etf["ticker"] == "SPY")].set_index("date")["ret"].reindex(sessions).fillna(0.0)
    pairs = pd.read_parquet(ex.OUT / "pairs.parquet")
    pi = pairs[(pairs["kind"] == "index") & pairs["lev"].isin(ex.INDEX_MULTIPLES)]
    P = ex.panel("index", etf, pi, sessions)
    R, DV, K = (P[x].loc[START:] for x in ("R", "DV", "K"))
    adv = P["DV"].rolling(63, min_periods=40).median().shift(1).loc[START:]
    q90 = P["R"].abs().rolling(252, min_periods=126).quantile(0.90).shift(1).loc[START:]
    elig = (adv >= ex.MIN_ADV) & (P["PX"].shift(1).loc[START:] >= ex.MIN_PRICE) & (DV > 0) & R.notna()
    S = (K * R.abs() / DV).where(elig)
    big = elig & (R.abs() >= q90) & (R != 0)
    fade = -np.sign(R)
    s1 = spy.loc[START:].shift(-1)
    f1 = (R.shift(-1).sub(s1, axis=0)) * fade
    T, TOP, A = elig & (S >= 0.10) & (R != 0), elig & (S >= 0.25) & (R != 0), big & (S < 0.025)
    out = {}
    # 1. eras
    eras = {}
    for a, b in explore.ERAS:
        sl = slice(max(a, START), b)
        if len(R.loc[sl]) == 0:
            continue
        eras[f"{max(a, START)[:4]}-{min(int(b[:4]), 2025)}"] = {n: ex.clustered(f1.where(M).loc[sl]) for n, M in (("T", T), ("S>=25%", TOP), ("A", A))}
    out["t+1 by era"] = eras
    print("1. t+1 fade less SPY by era (n, mean bp, t):")
    for e, d in eras.items():
        print("  ", e, {n: (v["events"], round(v["mean_bp"], 1), round(v["t_daily_mean"], 2)) for n, v in d.items()})
    # 2. concentration
    n_by = T.sum().sort_values(ascending=False)
    tick = etf.groupby("permno")["ticker"].last()
    top3 = list(n_by.index[:3])
    per = pd.DataFrame({"events": n_by, "mean_bp": (f1.where(T).mean() * 1e4).reindex(n_by.index)})
    per.index = [tick[i] for i in per.index]
    per = per[per["events"] >= 100]
    out["t+1 by underlying"] = {"underlyings_with_100_events": int(len(per)), "share_positive": float((per["mean_bp"] > 0).mean()),
                                "top3_share_of_events": float(n_by.iloc[:3].sum() / n_by.sum()),
                                "without_top3": ex.clustered(f1.where(T).drop(columns=top3)),
                                "table": {k: {"events": int(v["events"]), "mean_bp": round(float(v["mean_bp"]), 1)} for k, v in per.iterrows()}}
    print("2. underlyings with 100+ events:", len(per), "; share with a positive mean:", round(out["t+1 by underlying"]["share_positive"], 2),
          "; top-3 share of events:", round(out["t+1 by underlying"]["top3_share_of_events"], 2))
    print(per.round(1).T.to_string())
    w = out["t+1 by underlying"]["without_top3"]; print("   without the top 3:", w["events"], round(w["mean_bp"], 1), round(w["t_daily_mean"], 2))
    # 3. mid quotes
    u = etf[etf["permno"].isin(R.columns)]
    mid = ((u.pivot(index="date", columns="permno", values="bid") + u.pivot(index="date", columns="permno", values="ask")) / 2.0).reindex(sessions)
    px = u.pivot(index="date", columns="permno", values="prc").reindex(sessions)
    # the close-to-close return carries any dividend; move it onto the mid-to-mid return: r_mid = (1+r) * (mid1/px1) / (mid0/px0) - 1
    adj = (mid / px).where((mid > 0) & (px > 0))
    rmid = ((1.0 + P["R"].shift(-1)) * adj.shift(-1) / adj - 1.0).loc[START:]
    f1m = rmid.sub(s1, axis=0) * fade
    out["t+1 on closing mid quotes"] = {"T": ex.clustered(f1m.where(T)), "S>=25%": ex.clustered(f1m.where(TOP)), "A": ex.clustered(f1m.where(A))}
    print("3. t+1 from mid quote to mid quote:", {n: (v["events"], round(v["mean_bp"], 1), round(v["t_daily_mean"], 2)) for n, v in out["t+1 on closing mid quotes"].items()})
    # 4. size if it could be filled at t's close (NOT the desk's convention)
    H = fade.where(T, 0.0).fillna(0.0) * ex.UNIT
    H = H.div(H.abs().sum(axis=1).clip(lower=1.0), axis=0)
    pnl = (H.shift(1) * R.fillna(0.0)).sum(axis=1) - H.shift(1).sum(axis=1) * spy.loc[START:]
    pnl = pnl.iloc[1:]
    res = explore.summarise(pnl)
    out["hypothetical fill at t's close, hold one session (not tradable here)"] = res
    print("4. hypothetical fill at t's own close, one session, SPY hedged (NOT tradable under the desk's convention):")
    print(explore.table(res))
    f = HERE / "results.json"
    d = json.loads(f.read_text()); d["checks_not_pre_specified"] = out
    f.write_text(json.dumps(d, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
