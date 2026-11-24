"""T2: NAV placebos. If a wrong NAV scores like the right one, NAV is not what carries it.
(a) NAV lagged one extra quarter, same name-days; (b) pseudo-NAV = mean adjusted price over
the 63 sessions ending at datadate, same knowledge date (a quarterly-stepped price anchor,
no accounting information); (c) another fund's NAV (20 random derangements).
z(disc) is invariant to scaling NAV by a constant, so only NAV *changes* matter."""
import sys, json, pickle
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import rv
D = pickle.load(open(HERE / "_cache/panel.pkl", "rb")); P = D["P"]
zT, zC, F, M, G0, G1, idx, nav = (D[k] for k in ["zT", "zC", "F", "M", "G0", "G1", "idx", "nav"])
sT, sC = -zT, -zC
out = {}

def score(lab, navp):
    zP = rv.zs(P.disc(navp)); rv.afit(zP)
    MM = M & zP.notna()
    r = {}
    for ph, G in (("ph0", G0), ("ph1", G1)):
        r[ph] = {"placebo": rv.eras(rv.ic(-zP, F, MM, G)), "treat_same_sample": rv.eras(rv.ic(sT, F, MM, G)),
                 "placebo_partial_on_ctrl": rv.eras(rv.pic(-zP, sC, F, MM, G)),
                 "treat_partial_on_placebo": rv.eras(rv.pic(sT, -zP, F, MM, G))}
    r["rank_corr_placebo_treat_median"] = float(rv.ic(-zP, sT, MM, G0, 6).median())
    r["cells"] = int(MM.reindex(G0).sum().sum())
    out[lab] = r
    print(lab, json.dumps(r))
    return zP

navL, _, _ = P.nav_daily("rdq", lag_q=1)
navL = navL.where(nav.notna())          # same name-days as the treatment
score("nav_lag_1q", navL)

padj = P.close / P.cf
ma = padj.rolling(63, min_periods=40).mean()
ov = {}
for perm, g in P.fn.groupby("permno"):
    tk = f"P{perm}"
    for d in g.datadate:
        i = P.CAL.searchsorted(d, side="right") - 1
        ov[(perm, d)] = float(ma[tk].iloc[i]) if i >= 0 else np.nan
navPS, _, _ = P.nav_daily("rdq", override=ov)
navPS = navPS.where(nav.notna())
score("pseudo_nav_price_ma63_at_datadate", navPS)

rng = np.random.default_rng(20261027)
U = list(nav.columns)
res = []
for rep in range(20):
    while True:
        perm = rng.permutation(len(U))
        if not (perm == np.arange(len(U))).any(): break
    donor = nav.iloc[:, perm].copy(); donor.columns = U
    zP = rv.zs(P.disc(donor)); MM = M & zP.notna()
    a = rv.ic(-zP, F, MM, G0); b = rv.ic(sT, F, MM, G0); c = rv.pic(-zP, sC, F, MM, G0)
    res.append((rv.row(a.loc["2012":"2022"]), rv.row(b.loc["2012":"2022"]), rv.row(c.loc["2012":"2022"])))
out["donor_nav_20_derangements_fit_ph0"] = {
    "placebo_ic_mean": float(np.mean([r[0][1] for r in res])), "placebo_ic_max": float(np.max([r[0][1] for r in res])),
    "placebo_t_mean": float(np.mean([r[0][2] for r in res])), "placebo_t_max": float(np.max([r[0][2] for r in res])),
    "treat_same_sample_ic_mean": float(np.mean([r[1][1] for r in res])),
    "placebo_partial_on_ctrl_t_mean": float(np.mean([r[2][2] for r in res])),
    "placebo_partial_on_ctrl_t_max": float(np.max([r[2][2] for r in res])),
    "dates_min": int(min(r[0][0] for r in res))}
print(out["donor_nav_20_derangements_fit_ph0"])
json.dump(out, open(HERE / "t2_placebo.json", "w"), indent=1, default=str)
