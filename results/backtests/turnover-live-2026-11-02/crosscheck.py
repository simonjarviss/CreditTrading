"""Second-method checks for turnover_live.py (report only).

1. The era/fit/H13 figures through `scripts.research.harness.report`, an
   independent code path with nan_policy="raise" (a held name-day with no return
   raises instead of booking zero).
2. The deferred-flip book rebuilt with a loop written independently of
   `band_gross_capped(defer_flips=True)`, in the form the leakage report's
   parity script used (band, cap, then zero a sign change), compared exactly.

    python3 results/backtests/turnover-live-2026-11-02/crosscheck.py
"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
import numpy as np, pandas as pd
from scripts.cef import band_frontier as bf
from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS, UNIVERSE
from scripts.research.harness import report

T, Rp = bf.build_targets()
dist = pd.read_parquet(bf.DATA_DIR / "cef_distributions.parquet")
DIST_END = pd.to_datetime(dist.loc[dist.ticker.isin(UNIVERSE), "ex_date"]).max()
keep = T.index <= DIST_END
Rt = bf.total_returns(Rp.loc[keep])

Hi = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)
Hd = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS, defer_flips=True)

for lab, H in (("instant", Hi), ("deferred", Hd)):
    rep = report(H.loc[keep], Rt)
    print(f"[harness.report, {lab}]")
    for k in ("fit", "holdout"):
        s = rep[k]
        print(f"  {k:<8}{s['start']}..{s['end']} SR {s['gross_sr']:.2f} ann {s['ann_ret']*100:.2f}% "
              f"vol {s['vol']*100:.2f}% turn {s['turn']:.1f} net@5/15/30 "
              + " ".join(f"{v:.2f}" for v in s['net_sr'].values()))
    for e, s in rep["eras"].items():
        sr = s['gross_sr'] if np.isfinite(s['gross_sr']) else float('nan')
        print(f"  era {e:<8} SR {sr:.2f} ann {s['ann_ret']*100:.2f}% turn {s['turn']:.1f}")

# independent deferred-flip loop (parity.py form)
from src.deploy.sleeves.cef_discount import _cap_gross
A = T.values; cur = np.zeros(T.shape[1]); H = np.zeros_like(A)
for i in range(len(A)):
    gap = A[i] - cur; mv = np.abs(gap) > BAND_WIDTH
    new = cur.copy(); new[mv] = A[i][mv] - np.sign(gap[mv]) * BAND_WIDTH
    g = np.abs(new).sum()
    if g > MAX_GROSS_STRESS:
        new = _cap_gross(pd.Series(new, index=T.columns), MAX_GROSS_STRESS)[0].values
    new[(cur * new) < 0] = 0.0
    cur = new; H[i] = cur
H2 = pd.DataFrame(H, index=T.index, columns=T.columns)
print("independent deferred loop == band_gross_capped(defer_flips=True):",
      bool(np.array_equal(H2.values, Hd.values)), "max abs diff", float(np.abs(H2.values - Hd.values).max()))
