# Hold (harness) vs a replica of the live sleeve's flatten-below-min_names rule
# (src/deploy/sleeves/cef_discount.py:892-895), cost grid. Report only; the reviewer's rv2.py,
# moved here from the session scratchpad 2026-11-02 so the REPORT.md flatten rows reproduce.
# Net cost grid for the reviewer's flatten-rule replica (rv2.py), same harness, same cut. Report-only arithmetic.
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]   # the worktree root
sys.path.insert(0, str(REPO))
import numpy as np, pandas as pd
from scripts.cef import band_frontier as bf
from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS, MIN_ADV_USD, MIN_NAMES, UNIVERSE
from src.deploy.sleeves.cef_discount import _cap_gross
T, R = bf.build_targets(); p = bf.build_panel()
ok = (p["z"].reindex(T.index).notna() & (p["adv"].reindex(T.index) >= MIN_ADV_USD))
thin = ok.sum(axis=1) < MIN_NAMES
def flat(T, b, cap, thin):
    A, cur = T.values, np.zeros(T.shape[1]); Hh = np.zeros_like(A); cols = T.columns; th = thin.values
    for i in range(len(A)):
        if th[i]:
            cur = np.zeros_like(cur); Hh[i] = cur; continue
        gap = A[i] - cur; mv = np.abs(gap) > b
        cur = cur.copy(); cur[mv] = A[i][mv] - np.sign(gap[mv]) * b
        cur = _cap_gross(pd.Series(cur, index=cols), cap)[0].values; Hh[i] = cur
    return pd.DataFrame(Hh, index=T.index, columns=cols)
dist = pd.read_parquet(bf.DATA_DIR / "cef_distributions.parquet"); dist["ex_date"] = pd.to_datetime(dist["ex_date"])
DIST_END = dist.loc[dist.ticker.isin(UNIVERSE), "ex_date"].max(); keep = T.index <= DIST_END
Rt = bf.total_returns(R.loc[keep])
print("DIST_END", DIST_END.date(), "spec band", BAND_WIDTH, "cap", MAX_GROSS_STRESS, "min_names", MIN_NAMES)
for name, H in (("hold", bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)), ("flatten", flat(T, BAND_WIDTH, MAX_GROSS_STRESS, thin))):
    r = bf.evaluate(H.loc[keep], Rt)
    for lab, a, b in (("2010-14","2010","2014"),("2015-19","2015","2019"),("2020-22","2020","2022"),("FIT","2005","2022"),("H13","2023","2026"),("full","2005","2026")):
        x = r["pnl"].loc[a:b]; tt = r["turn_series"].loc[a:b]
        an, vo, tu = x.mean()*252, x.std()*np.sqrt(252), tt.mean()*252
        eq = (1+x).cumprod(); dd = (eq/eq.cummax()-1).min()
        nets = [(an - tu*c/1e4) for c in (5,15,30)]
        print(f"{name:8}{lab:8} SR {an/vo:5.2f} ann {an*100:6.2f} vol {vo*100:5.2f} mdd {dd*100:6.1f} turn {tu:5.1f} BE {an/tu*1e4 if tu else float('nan'):6.1f} "
              f"netSR {' '.join(f'{n/vo:5.2f}' for n in nets)} net% {' '.join(f'{n*100:6.2f}' for n in nets)}")
