"""Second method for the headline (CLAUDE.md: double-check what drives a decision).

Same rdq panel (_cache_r5, written by bdc_ic.py), same build_panel z, same control code,
but (i) forward returns from split-adjusted PRICE (|prc|/cfacpr), not CRSP total `ret`,
and (ii) the Fama-MacBeth slope of demeaned forward return on demeaned s (w4's
fm_slopes) beside the Spearman IC. Phase 0 grid, primary set. Aggregates only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "tree"))
import common as C
from scripts.cef.band_frontier import build_panel
from scripts.cef.w4_artifacts import DEPLOYED_WIN, fwd, grid, ic_row, ic_series, fm_slopes
from bdc_ic_lib import zscore

CA = HERE.parent / "_cache_r5"
pp, npth = CA / "bdc_prices_rdq.parquet", CA / "bdc_nav_rdq.parquet"
U = sorted(pd.read_parquet(npth).ticker.unique())
P = build_panel(end="2022-12-30", universe=U, source=(pp, npth))
ent = C.entities(); px = C.crsp(ent.permno, start="2009-01-01")
px["ticker"] = "P" + px.permno.astype(str); px["padj"] = px.prc.abs() / px.cfacpr
idx = pd.DatetimeIndex(sorted(px.date.unique()))
padj = px.pivot(index="date", columns="ticker", values="padj").reindex(index=idx, columns=U)
zT = P["z"].reindex(index=idx, columns=U); zC = zscore(np.log(padj))
rpx = padj.pct_change(fill_method=None).where(lambda x: x.abs() < 0.5)
rtr = px.pivot(index="date", columns="ticker", values="ret").reindex(index=idx, columns=U).where(lambda x: x.abs() < 0.5)
FF = {"total_ret_crsp": fwd(rtr, *DEPLOYED_WIN), "price_ret_adj_DIAGNOSTIC": fwd(rpx, *DEPLOYED_WIN)}
C.assert_fit(zT, zC, *FF.values())
M = zT.notna() & zC.notna()
G = grid(idx[idx >= "2012-01-01"], 0)
out = {}
for flab, F in FF.items():
  for lab0, s in (("treatment", -zT), ("control", -zC)):
    lab = f"{flab}|{lab0}"
    ic = ic_series(s, F, M, G); fm = fm_slopes(s, F, M, G) * 1e4
    out[lab] = {}
    for e, a, b in (("2012-17", "2012", "2017"), ("2018-22", "2018", "2022"), ("fit 2012-22", "2012", "2022")):
        r = ic_row(ic.loc[a:b]); f = fm.loc[a:b]
        out[lab][e] = {"ic": float(r["ic"]), "t": float(r["t"]), "n": int(r["n"]),
                       "fm_bp_per_z": float(f.mean()), "t_fm": float(f.mean() / f.std(ddof=1) * np.sqrt(len(f)))}
print(json.dumps(out, indent=1)); Path(HERE.parent / "second_method.json").write_text(json.dumps(out, indent=1))
