"""T5b: is the declared price-only control the right one? Short-term reversal (1/5/21-day
past CRSP total return through t, sign = long losers) as alternative price-only controls;
multivariate Fama-MacBeth on cross-sectional ranks [s_T, s_C, STR]; IC on BDC-beta-adjusted
forward returns (beta from trailing 252 sessions through t-1 on the BDC EW return)."""
import sys, json, pickle
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import rv
D = pickle.load(open(HERE / "_cache/panel.pkl", "rb")); P = D["P"]
zT, zC, F, M, G0, G1, idx, adv, ret = (D[k] for k in ["zT", "zC", "F", "M", "G0", "G1", "idx", "adv", "ret"])
sT, sC = -zT, -zC
lr = np.log1p(ret)
STR = {h: -(lr.rolling(h).sum()).reindex(idx) for h in (1, 5, 21)}   # through close t (date-t info)
a = adv.reindex(idx).where(M); pr = a.rank(axis=1, pct=True)
sets = {"primary": M, "deployed_adv3m": M & (adv.reindex(idx) >= rv.MIN_ADV), "adv_low": M & (pr <= 1/3).fillna(False), "adv_high": M & (pr > 2/3).fillna(False)}
out = {}
for h, S in STR.items():
    for sl, MM in sets.items():
        MM2 = MM & S.notna()
        out[f"STR_{h}d|{sl}"] = {"str_ic": rv.eras(rv.ic(S, F, MM2, G0)), "treat_ic_same": rv.eras(rv.ic(sT, F, MM2, G0)),
                                 "treat_partial_on_str": rv.eras(rv.pic(sT, S, F, MM2, G0))}
        print(h, sl, out[f"STR_{h}d|{sl}"])
# multivariate FM on ranks, per date: F_rank ~ rank(sT) + rank(sC) + rank(STR5)
def fm(cols, MM, G, Fm=F):
    ok = MM.copy()
    for c in cols: ok &= c.notna()
    ok &= Fm.notna(); ok = ok.reindex(G).fillna(False).astype(bool)
    R = [c.reindex(G).where(ok).rank(axis=1) for c in cols]; Y = Fm.reindex(G).where(ok).rank(axis=1)
    rows = []; skipped = []
    for d in G:
        m = ok.loc[d]
        if m.sum() < 8: continue
        X = np.column_stack([np.ones(m.sum())] + [(r.loc[d][m] - r.loc[d][m].mean()) / r.loc[d][m].std() for r in R])
        y = (Y.loc[d][m] - Y.loc[d][m].mean()) / Y.loc[d][m].std()
        if not (np.isfinite(X).all() and np.isfinite(y.values).all()):
            skipped.append(d); continue            # a constant rank column that date: counted, not imputed
        b = np.linalg.lstsq(X, y.values, rcond=None)[0]; rows.append([d] + list(b[1:]))
    B = pd.DataFrame(rows).set_index(0)
    r = {era: [rv.row(B[i].loc[a_:b_]) for i in B.columns] for era, a_, b_ in rv.ERAS}; r['skipped_dates'] = len(skipped); return r
for sl in ("primary", "deployed_adv3m"):
    out[f"FM_ranks[sT,sC,STR5]|{sl}"] = fm([sT, sC, STR[5]], sets[sl], G0)
    out[f"FM_ranks[sT,sC,STR1,STR5,STR21]|{sl}"] = fm([sT, sC, STR[1], STR[5], STR[21]], sets[sl], G0)
    print(sl, out[f"FM_ranks[sT,sC,STR5]|{sl}"]); print(sl, out[f"FM_ranks[sT,sC,STR1,STR5,STR21]|{sl}"])
# beta-adjusted forward returns
ew = ret.where(ret.notna()).reindex(idx).mean(axis=1)
cov = ret.reindex(idx).rolling(252, min_periods=120).cov(ew)
var = ew.rolling(252, min_periods=120).var()
beta = cov.div(var, axis=0).shift(1)                       # through t-1
Few = rv.fwd(ew.to_frame("x"), 2, 3)["x"]
Fadj = F.sub(beta.mul(Few, axis=0))
for sl in ("primary", "deployed_adv3m"):
    MM = sets[sl] & beta.notna()
    out[f"beta_adj|{sl}"] = {"treat": rv.eras(rv.ic(sT, Fadj, MM, G0)), "treat_raw_same": rv.eras(rv.ic(sT, F, MM, G0)),
                             "ctrl": rv.eras(rv.ic(sC, Fadj, MM, G0)), "partial": rv.eras(rv.pic(sT, sC, Fadj, MM, G0)),
                             "rank_corr_sT_beta_med": round(float(rv.ic(sT, beta, MM, G0).median()), 3)}
    print(sl, out[f"beta_adj|{sl}"])
json.dump(out, open(HERE / "t5_str_beta.json", "w"), indent=1, default=str)
