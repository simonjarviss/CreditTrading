# Split of the hold book's fit-period P&L into thin (fewer than min_names eligible) and active
# sessions. Report only; the reviewer's rv3.py, moved here 2026-11-02.
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]   # the worktree root
sys.path.insert(0, str(REPO))
import numpy as np, pandas as pd
from scripts.cef import band_frontier as bf
from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS, MIN_ADV_USD, MIN_NAMES, UNIVERSE
T, R = bf.build_targets()
p = bf.build_panel()
ok = (p["z"].reindex(T.index).notna() & (p["adv"].reindex(T.index) >= MIN_ADV_USD))
thin = ok.sum(axis=1) < MIN_NAMES
dist = pd.read_parquet(bf.DATA_DIR / "cef_distributions.parquet"); dist["ex_date"] = pd.to_datetime(dist["ex_date"])
DIST_END = dist.loc[dist.ticker.isin(UNIVERSE), "ex_date"].max()
keep = T.index <= DIST_END
Rt = bf.total_returns(R.loc[keep])
H = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)
r = bf.evaluate(H.loc[keep], Rt); pnl, turn = r["pnl"], r["turn_series"]
# a P&L day t earns H[t-2]; tag it by whether the decision at t-2 was a thin (held) session
ht = thin.reindex(H.index).shift(2).reindex(pnl.index)
ht = ht.where(ht.notna(), False).astype(bool)
print(f"{'era':<9}{'n':>6}{'thin-held n':>12}{'ann% all':>9}{'ann% from thin-held':>20}{'ann% from active':>17}{'turn/yr on thin decisions':>26}")
for lab, a, b in (("2010-14","2010","2014"),("2015-19","2015","2019"),("2020-22","2020","2022"),("FIT","2005","2022"),("H13","2023","2026")):
    x, m = pnl.loc[a:b], ht.loc[a:b]
    tt = turn.loc[a:b]; th = thin.reindex(tt.index)
    print(f"{lab:<9}{len(x):6d}{int(m.sum()):12d}{x.mean()*25200:9.2f}{x[m].sum()/len(x)*25200:20.2f}{x[~m].sum()/len(x)*25200:17.2f}{tt[th].sum()/len(tt)*252:26.2f}")
# gross held on thin days
g = H.abs().sum(axis=1)
for lab, a, b in (("2010-14","2010","2014"),("2015-19","2015","2019"),("2020-22","2020","2022")):
    print(lab, "mean gross held on thin decisions %.2f, on active %.2f" % (g.loc[a:b][thin.loc[a:b]].mean(), g.loc[a:b][~thin.loc[a:b]].mean()))
