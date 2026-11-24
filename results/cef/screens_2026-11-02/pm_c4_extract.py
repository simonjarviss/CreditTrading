"""C4's unit-book inputs for the two-account portfolio screens (PM_TWO_ACCOUNTS.md). ZERO TRIALS.

    python3 -I results/cef/screens_2026-11-02/pm_c4_extract.py --scratch SCRATCH --c4-tree C4TREE

WHY A SEPARATE PROCESS. C4's book is built by C4's own code on the clean worktree `c4-step2-spec`
(6f62527), which has its own `scripts.cef.band_frontier`. Importing that next to this tree's copy in
one interpreter would let one module shadow the other in silence, so this script runs alone, with
only the C4 tree on sys.path, and writes its outputs to SCRATCH/pm/c4/ (never to a tracked file:
C4's returns are CRSP-derived, licensed).

WHAT IT WRITES (all fit-only, asserted <= 2022-12-30):
  T.parquet          the trial's frictionless unit targets T (c4_paper_benchmark.trial_targets)
  R_tr.parquet       the H11 reference's total-return panel (CRSP ret, check_held)
  R_pr.parquet       the H11 reference's price-only panel (CRSP retx)
  opp.parquet        two opportunity aggregates per date, from the z the sleeve itself decides on
                     (band_frontier.build_panel with C4's declared M1|M2 mask and the ADV floor):
                     disp = cross-sectional sd of z over eligible names; absz = mean |z| over them;
                     n = eligible names. Date-t values use t's close and t's NAV (the decide-time
                     information); the screen lags them a further session (data < t).
It then ASSERTS that band_gross_capped(T, band, cap) reproduces SCRATCH/alloc4/series/c4spec_H to
1e-12, so the T here is the T behind the spec-book series every allocation figure was built on.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

FIT_END = pd.Timestamp("2022-12-30")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--c4-tree", type=Path, required=True)
    a = ap.parse_args()
    root = a.c4_tree.resolve()
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if dirty:
        raise RuntimeError(f"{root} is not clean: {dirty[:200]}")
    sys.path.insert(0, str(root))
    from scripts.cef import c4_paper_benchmark as pb
    from scripts.cef import c4_families as c4
    from scripts.cef import band_frontier as bf
    from scripts.cef.spec import MIN_ADV_USD, MIN_NAMES
    out = a.scratch / "pm" / "c4"
    out.mkdir(parents=True, exist_ok=True)
    spec = pb.load_spec()
    cut = a.scratch / "pm" / "_c4_cut"
    print("families cut on read:", pb.cut_families(cut))
    T, uinfo = pb.trial_targets(cut)
    tb = pb.trial_book(cut, T)                    # raises unless the committed 1.217 / 1.360 reproduce to 1e-9
    tb["T"] = T
    ref = pb.h11_reference(tb, spec)
    H = ref["H"]
    want = pd.read_parquet(a.scratch / "alloc4" / "series" / "c4spec_H.parquet")
    d = float((H.reindex_like(want) - want).abs().max().max())
    if d > 1e-12 or not H.index.equals(want.index):
        raise AssertionError(f"C4 spec book does not reproduce alloc4/series/c4spec_H: {d}")
    print(f"spec book reproduces alloc4/series/c4spec_H: max abs diff {d:.1e} (code {head[:7]})")
    with pb.trial_reads(cut):
        UF = [t for t in uinfo["with_rows"]]
        p = bf.build_panel(universe=UF, source=c4.FAM_SRC, mask=c4.declared_mask(UF))
    z, adv = p["z"], p["adv"]
    elig = z.notna() & (adv.reindex_like(z).fillna(-1.0) >= MIN_ADV_USD)   # build_targets' own rule: NaN ADV fails
    zz = z.where(elig)
    opp = pd.DataFrame({"disp": zz.std(axis=1, ddof=1), "absz": zz.abs().mean(axis=1), "n": elig.sum(axis=1)})
    opp = opp.loc[:FIT_END].reindex(T.index)
    opp.loc[opp["n"] < MIN_NAMES, ["disp", "absz"]] = np.nan     # below min_names the sleeve holds: no reading
    for nm, f in (("T", T), ("R_tr", ref["total"]), ("R_pr", ref["price"]), ("opp", opp)):
        if f.index.max() > FIT_END:
            raise AssertionError(f"holdout leak in {nm}")
        f.to_parquet(out / f"{nm}.parquet")
    print("written:", sorted(x.name for x in out.iterdir()), "| T", T.shape, T.index.min().date(), T.index.max().date(),
          "| band", spec["frozen"]["band_width"], "cap", spec["frozen"]["max_gross_stress"], "| spec", spec["spec_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
