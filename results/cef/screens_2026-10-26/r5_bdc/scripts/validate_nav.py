"""Gate A (NOTE.md §6a.A): is Compustat ceqq/cshoq the BDC's NAV per share?

Compared with the 175 point-in-time XBRL NetAssetValuePerShare values (filed by
2022-12-30), on (cik, period end == datadate). Match = |Comp/XBRL - 1| <= 1%.
Stop rule declared before running: < 90% matching -> stop, report both, pick neither.
Second check (labelled, not the gate): the 505 loosely-read XBRL values (later filings
restating 2012-22 period ends; not point-in-time, used here only as a value check).

Writes only aggregate statistics (no licensed values) to validate_nav.json.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import common as C

FIT0 = pd.Timestamp("2012-01-01")

nav, counts = C.compustat_nav()
r = C.reports()
A = r[(r.listed == True) & (r.filingDate >= FIT0) & (r.filingDate <= C.FIT_END)]
x = C.xbrl_navps()
x = x[x.cik.isin(set(A.cik)) & (x.end >= FIT0) & (x.end <= C.FIT_END)]
sets = {"pit_175": x[x.filed <= C.FIT_END], "loose_505": x}
out = {"exclusions": counts}
for lab, xs in sets.items():
    xs = xs[["cik", "end", "val", "filed"]].rename(columns={"end": "datadate", "val": "xbrl"})
    m = xs.merge(nav[["cik", "datadate", "nav", "rdq"]], on=["cik", "datadate"], how="left")
    comparable = m[m.nav.notna()].copy()
    comparable["rel"] = comparable.nav / comparable.xbrl - 1.0
    a = comparable.rel.abs()
    res = {
        "xbrl_values": int(len(xs)),
        "comparable_pairs": int(len(comparable)),
        "no_compustat_row": int(m.nav.isna().sum()),
        "match_le_1pct": float((a <= 0.01).mean()),
        "within_0p1pct": float((a <= 0.001).mean()),
        "within_5pct": float((a <= 0.05).mean()),
        "median_abs_rel": float(a.median()),
        "p90_abs_rel": float(a.quantile(0.9)),
        "max_abs_rel": float(a.max()),
        "n_over_1pct": int((a > 0.01).sum()),
        "bdcs": int(comparable.cik.nunique()),
        "by_end_year_match": {int(k): [int(v.size), float((v.abs() <= 0.01).mean())]
                              for k, v in comparable.groupby(comparable.datadate.dt.year).rel},
    }
    # sign of the misses (aggregate only)
    miss = comparable[a > 0.01]
    res["misses_comp_above_xbrl"] = int((miss.rel > 0).sum())
    res["misses_comp_below_xbrl"] = int((miss.rel < 0).sum())
    out[lab] = res

gate = out["pit_175"]["match_le_1pct"]
out["gate_pass"] = bool(gate >= 0.90)
print(json.dumps(out, indent=1))
Path("validate_nav.json").write_text(json.dumps(out, indent=1))
if not out["gate_pass"]:
    raise SystemExit(f"GATE FAILED: {gate:.1%} of point-in-time pairs match within 1% (< 90%). Stop; pick neither.")
