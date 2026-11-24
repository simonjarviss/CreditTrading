"""DG-L4 driver: runs INSIDE the sleeve's tree (branch c4-level-impl @ 3b4c963) with that tree's own
`scripts/cef/c4_paper_benchmark.py` fidelity machinery (cut_families, Probe, fidelity; TOL 1e-12, every
fifth session). It never edits the sleeve: it builds it from the spec through the registry, as the runner
does, and reads its `w` at the `min_abs_weight` read.

    python3 -B dgl4_driver.py <impl_root> <trial_cache_dir> <out_json>

(a) key ABSENT: C4's v4 spec as frozen -> the sleeve against the trial's own T_z (`c4.build_book`).
(b) key PRESENT: the same spec with `level_signal = {risk_share 0.5 (share on z), family_of: C4's frozen
    families}` -> the sleeve against the trial's blend unit target T_B, built WITHOUT the DG-L3 masks (the
    sleeve has none; those 9 name-days are a trial-only treatment of historical misprints).
"""
import json
import sys
import tempfile
from pathlib import Path

impl, cache, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(impl))
import pandas as pd  # noqa: E402
from scripts.cef import c4_paper_benchmark as cpb  # noqa: E402
from scripts.cef import c4_families as c4  # noqa: E402

res = {"impl_root_head": None}
spec = cpb.load_spec(impl / "ops" / "specs" / "c4_families.frozen.json")
fam = pd.read_csv(impl / "results" / "cef" / "c4" / "c4_universe_frozen_2026-10-14.csv").set_index("ticker")["family"]
Tz = pd.read_parquet(cache / "dgl4_Tz.parquet")
TB = pd.read_parquet(cache / "dgl4_TB_unmasked.parquet")
with tempfile.TemporaryDirectory(prefix="dgl4_cut_") as tmp:
    cut = Path(tmp)
    res["cut"] = cpb.cut_families(cut)
    for lab, sp, T in (("a_key_absent", spec, Tz),
                       ("b_key_present", cpb.with_keys(spec, level_signal={"risk_share": 0.5,
                                                                           "family_of": {t: fam[t] for t in spec["frozen"]["universe"]}}), TB)):
        T = T.reindex(columns=sorted(spec["frozen"]["universe"]), fill_value=0.0)
        dates = cpb.fidelity_dates(T)
        try:
            rep = cpb.fidelity(sp, cut, dates, T=T)
            res[lab] = {"breaks": 0, "report": rep}
        except cpb.FidelityBreak as e:
            rep = e.report
            res[lab] = {"breaks": rep["n_breaks"], "message": str(e)[:500], "report": rep}
        r = res[lab]["report"]
        print(lab, f"sessions {r['sessions']} ({r['first']}..{r['last']}), matched {r['sessions_matched']}, cells "
              f"{r['cells_matched']}/{r['cells_compared']}, largest gap {r['largest_gap']}, breaks {r['n_breaks']}")
        for b in r["breaks"][:8]:
            print("   break", b["date"], b["kind"], b["detail"][:180])
out.write_text(json.dumps(res, indent=1, default=str))
