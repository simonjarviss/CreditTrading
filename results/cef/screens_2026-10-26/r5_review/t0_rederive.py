"""T0: re-derive the headline from fundq + CRSP independently; compare with build_panel
on the author's cached panel, and with the note's +0.0258 (5.14)."""
import sys, json, pickle
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import rv
TREE = HERE.parent / "tree"; sys.path.insert(0, str(TREE))
from scripts.cef.spec import Z_WINDOW, MIN_NAMES, MIN_ADV_USD
from scripts.cef.band_frontier import MIN_PERIODS, build_panel
assert (Z_WINDOW, MIN_PERIODS, MIN_NAMES, MIN_ADV_USD) == (rv.ZW, rv.MINP, rv.MIN_N, rv.MIN_ADV), "spec drift"

P = rv.Panel()
nav, kk, dd = P.nav_daily("rdq")
disc = P.disc(nav); zT = rv.zs(disc); adv = P.adv(nav)
zC = rv.zs(np.log(P.close / P.cf))
ret = P.ret.where(P.ret.abs() < 0.5); F = rv.fwd(ret, 2, 3)
idx = P.CAL[P.CAL <= rv.END]; rv.afit(idx, zT, zC, F)
M = zT.notna() & zC.notna()
G0 = idx[idx >= "2012-01-01"][0::2]; G1 = idx[idx >= "2012-01-01"][1::2]
out = {"mine_treat_ph0": rv.eras(rv.ic(-zT, F, M, G0)), "mine_ctrl_ph0": rv.eras(rv.ic(-zC, F, M, G0)),
       "mine_partial_ph0": rv.eras(rv.pic(-zT, -zC, F, M, G0)),
       "mine_dep_treat_ph0": rv.eras(rv.ic(-zT, F, M & (adv >= rv.MIN_ADV), G0))}
# author's cached panel through build_panel
CA = HERE.parent / "r5_bdc/_cache_r5"
U = sorted(pd.read_parquet(CA / "bdc_nav_rdq.parquet").ticker.unique())
BP = build_panel(end="2022-12-30", universe=U, source=(CA / "bdc_prices_rdq.parquet", CA / "bdc_nav_rdq.parquet"))
zb = BP["z"].reindex(index=idx, columns=zT.columns)
both = zb.notna() & zT.reindex(idx).notna()
out["z_agree_cells"] = int(both.sum().sum())
out["z_only_mine"] = int((zT.reindex(idx).notna() & zb.isna()).sum().sum())
out["z_only_author"] = int((zb.notna() & zT.reindex(idx).isna()).sum().sum())
out["z_max_abs_diff"] = float((zb - zT.reindex(idx)).abs().where(both).max().max())
print(json.dumps(out, indent=1, default=str))
pickle.dump(dict(P=P, nav=nav, kk=kk, dd=dd, disc=disc, zT=zT, zC=zC, adv=adv, ret=ret, F=F, idx=idx, M=M, G0=G0, G1=G1),
            open(HERE / "_cache/panel.pkl", "wb"))
json.dump(out, open(HERE / "t0_rederive.json", "w"), indent=1, default=str)
