"""T1: stale prices / illiquidity. Traded-on-both masks, ADV terciles, decay profile."""
import sys, json, pickle
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import rv
D = pickle.load(open(HERE / "_cache/panel.pkl", "rb")); P = D["P"]
zT, zC, F, M, G0, G1, adv, ret, idx = (D[k] for k in ["zT", "zC", "F", "M", "G0", "G1", "adv", "ret", "idx"])
sT, sC = -zT, -zC
out = {}
tr = ((P.prc > 0) & (P.vol > 0)).reindex(idx).fillna(False)
out["share_signal_namedays_untraded_t"] = float((~tr).where(M).stack().astype(float).mean())
out["share_signal_namedays_untraded_t1"] = float((~tr.shift(-1).fillna(False).astype(bool)).where(M).stack().astype(float).mean())
masks = {"all": M,
         "traded t & t+1": M & tr & tr.shift(-1).fillna(False).astype(bool),
         "traded t..t+3": M & tr & tr.shift(-1).fillna(False).astype(bool) & tr.shift(-2).fillna(False).astype(bool) & tr.shift(-3).fillna(False).astype(bool)}
for lab, MM in masks.items():
    for ph, G in (("ph0", G0), ("ph1", G1)):
        out[f"{lab}|{ph}|treat"] = rv.eras(rv.ic(sT, F, MM, G))
        out[f"{lab}|{ph}|ctrl"] = rv.eras(rv.ic(sC, F, MM, G))
        out[f"{lab}|{ph}|partial"] = rv.eras(rv.pic(sT, sC, F, MM, G))
# ADV terciles within the primary set, per date (ADV through t-1, build_panel's)
a = adv.reindex(idx).where(M)
pr = a.rank(axis=1, pct=True)
terc = {"low": pr <= 1 / 3, "mid": (pr > 1 / 3) & (pr <= 2 / 3), "high": pr > 2 / 3}
for lab, T in terc.items():
    MM = M & T.fillna(False)
    for ph, G in (("ph0", G0), ("ph1", G1)):
        out[f"ADV tercile {lab}|{ph}|treat"] = rv.eras(rv.ic(sT, F, MM, G))
        out[f"ADV tercile {lab}|{ph}|ctrl"] = rv.eras(rv.ic(sC, F, MM, G))
        out[f"ADV tercile {lab}|{ph}|partial"] = rv.eras(rv.pic(sT, sC, F, MM, G))
    out[f"ADV tercile {lab}|median ADV $m"] = float(a.where(T).stack().median() / 1e6)
# decay: single-day forward return k (k=1 is close t -> t+1, infeasible under shift(2))
dec = {}
for k in range(1, 11):
    Fk = rv.fwd(ret, k, k)
    dec[k] = {"treat": rv.row(rv.ic(sT, Fk, M, G0).loc["2012":"2022"]),
              "ctrl": rv.row(rv.ic(sC, Fk, M, G0).loc["2012":"2022"]),
              "treat_highADV": rv.row(rv.ic(sT, Fk, M & terc["high"].fillna(False), G0).loc["2012":"2022"])}
out["decay_single_day_fit_ph0"] = dec
for a_, b_ in [(3, 4), (4, 5), (6, 10), (11, 21)]:
    Fw = rv.fwd(ret, a_, b_)
    Gw = idx[idx >= "2012-01-01"][0::(b_ - a_ + 1)]
    out[f"window {a_}-{b_}|treat"] = rv.eras(rv.ic(sT, Fw, M, Gw))
    out[f"window {a_}-{b_}|ctrl"] = rv.eras(rv.ic(sC, Fw, M, Gw))
    out[f"window {a_}-{b_}|partial"] = rv.eras(rv.pic(sT, sC, Fw, M, Gw))
json.dump(out, open(HERE / "t1_stale.json", "w"), indent=1, default=str)
for k, v in out.items():
    print(k, v)
