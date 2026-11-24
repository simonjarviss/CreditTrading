"""Diagnose the >1% misses of gate A: are they share-basis (split) differences?

For each miss, restate the Compustat NAV into the share basis on the XBRL filing date
with CRSP's cumulative price factor: NAV_q * cfacpr(filed) / cfacpr(datadate). If the
restated value matches XBRL, the miss is a split between the quarter end and the XBRL
filing, which the signal's cfacpr adjustment (NOTE §6a.C) already handles.
Aggregates only are written (validate_misses.json)."""
import json
from pathlib import Path
import pandas as pd
import common as C

nav, _ = C.compustat_nav()
r = C.reports()
A = r[(r.listed == True) & (r.filingDate >= "2012-01-01") & (r.filingDate <= C.FIT_END)]
x = C.xbrl_navps()
x = x[x.cik.isin(set(A.cik)) & (x.end >= "2012-01-01") & (x.end <= C.FIT_END)]
out = {}
for lab, xs in {"pit_175": x[x.filed <= C.FIT_END], "loose_505": x}.items():
    m = xs.rename(columns={"end": "datadate", "val": "xbrl"}).merge(nav, on=["cik", "datadate"])
    m["rel"] = m.nav / m.xbrl - 1
    miss = m[m.rel.abs() > 0.01].copy()
    px = C.crsp(miss.permno.unique(), start="2009-01-01")
    px = px.sort_values("date")
    def cf(perm, d):
        # last row with a factor on or before d (CRSP leaves cfacpr empty on rows with
        # no price; the factor changes only at a distribution event, so the last
        # stated factor is the one in force)
        s = px[(px.permno == perm) & (px.date <= d) & px.cfacpr.notna()]
        if s.empty or pd.isna(s.cfacpr.iloc[-1]):
            return float("nan")
        return float(s.cfacpr.iloc[-1])
    # XBRL filed after 2022-12-30 cannot be priced from the fit-window CRSP read; mark it
    miss["cf_d"] = [cf(p, d) for p, d in zip(miss.permno, miss.datadate)]
    miss["cf_f"] = [cf(p, min(f, C.FIT_END)) for p, f in zip(miss.permno, miss.filed)]
    miss["filed_after_fit"] = miss.filed > C.FIT_END
    miss["restated"] = miss.nav * miss.cf_f / miss.cf_d
    miss["rel2"] = miss.restated / miss.xbrl - 1
    out[lab] = {
        "misses": int(len(miss)),
        "bdcs_with_misses": int(miss.cik.nunique()),
        "ratio_comp_over_xbrl_rounded": sorted(set(round(v, 2) for v in (1 + miss.rel))),
        "explained_by_cfacpr_within_1pct": int((miss.rel2.abs() <= 0.01).sum()),
        "unexplained": int((miss.rel2.abs() > 0.01).sum()),
        "unexplained_with_xbrl_filed_after_fit_end": int(((miss.rel2.abs() > 0.01) & miss.filed_after_fit).sum()),
    }
print(json.dumps(out, indent=1))
Path("validate_misses.json").write_text(json.dumps(out, indent=1))
