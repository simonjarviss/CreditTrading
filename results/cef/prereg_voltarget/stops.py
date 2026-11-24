"""The raise-specific stops R1-R3, re-measured on the read date (CEF trial 53, DRAFT; H14).

    python3 results/cef/prereg_voltarget/stops.py --scratch SCRATCH --m-core 1.24 --m-c4 1.39
        (prints; writes nothing)

No decision rule may key on a number written in a document (H14), so the pre-registration writes the
RULE and this computes the threshold when the rule is read. Definitions (declared_2026-10-30.json):
  R1  D_R = the LARGEST over SB21 / SB63 / GAUSS of the 95th percentile of the 252-session maximum
      drawdown of the account's raised fit series at the FIT edge, the worse of total return and price
      only, on the account's own fit window, never above the spec's risk.halve_drawdown.
  R2  the 5th percentile of 120-session cumulative PRICE-ONLY returns of the raised fit series (SB21).
  R3  the 95th percentile of the 60-session realised vol (annualised) of the raised PRICE-ONLY fit
      series (SB21).
The raised fit series is the house cap model at the account's multiplier (_common.account); the exact
implementation differs from it by the amounts impl_core.py / impl_c4.py report. Fit window only.

C4 ON WHATEVER BOOK ITS SPEC DEFINES (added 2026-11-03 for CEF trial 54, PREREG_C4_LEVEL §6.3: "the
trial-53 stops R1-R3, rebuilt on the blended book"). Without the flag below, C4's series is the fixed
scratch series SCRATCH/alloc4/series/c4spec_trpr.parquet: the z-only 1.90 book, built once from
c4-step2-spec, under the house cap model. That series cannot see a spec change, so with `level_signal`
set it would measure the wrong book. `--c4-exact PATH` reads instead the series that
`scripts/cef/c4_paper_benchmark.py run` writes for the LIVE spec. That is the account's book under
the exact construction, m x band_gross_capped(spec target, band, cap / m): the blend when the spec
carries level_signal, the z book when it does not. The P&L is CRSP total return and price only, m
already applied, so the house cap model is not applied again. The series' sidecar names the spec's
sha256, and a series made from any other spec file than the live ops/specs/c4_families.frozen.json is
refused. `--only c4` skips the core, which needs its own scratch series. Neither flag set is the
run as before.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from _common import HALVE_DD, W1_START, W2_START, Paths, account, c4_spec_from, core_spec, load
from risk import pctl_maxdd


def c4_exact_series(path: Path, m: float) -> dict:
    """C4's exact spec-book series (docstring), refused unless its sidecar names the LIVE spec file's
    sha256 and the multiplier given on the command line is the spec's own."""
    import hashlib
    import json
    from _common import REPO, assert_fit
    side = json.loads(path.with_suffix(".json").read_text())
    spec_path = REPO / "ops" / "specs" / "c4_families.frozen.json"
    live = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    if side.get("spec_sha256") != live:
        raise ValueError(f"{path.name} was built from spec sha256 {str(side.get('spec_sha256'))[:16]}..., not the live "
                         f"{spec_path.name} ({live[:16]}...); re-run scripts/cef/c4_paper_benchmark.py run")
    spec_m = json.loads(spec_path.read_text())["frozen"].get("sizing_multiplier")
    if spec_m is None or abs(float(spec_m) - m) > 1e-12:
        raise ValueError(f"--m-c4 {m} is not the live spec's sizing_multiplier {spec_m}; the exact series is at the spec's")
    d = pd.read_parquet(path)
    if set(d.columns) != {"tr", "pr"} or d.isna().any().any():
        raise ValueError(f"{path.name}: expected columns tr, pr with no NaN")
    assert_fit(d)
    return {"TR": d["tr"], "PR": d["pr"], "spec_id": side["spec_id"], "policy": side["policy"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--m-core", type=float, required=True)
    ap.add_argument("--m-c4", type=float, required=True)
    ap.add_argument("--c4-exact", type=Path, default=None,
                    help="the benchmark's h11_spec_book_<spec_id>.parquet: C4's live spec book, exact construction "
                         "(docstring); absent, the scratch c4spec series under the house cap model, as before")
    ap.add_argument("--only", choices=("core", "c4"), default=None, help="measure one account; absent, both")
    ap.add_argument("--core-earning-only", type=Path, default=None,
                    help="flatten_series.py's flatten_masks.parquet: calibrate the CORE's stops on the sessions its "
                         "book earns on (FLATTEN_REMEASURE_2026-11-02.md); absent, every session, as before")
    a = ap.parse_args()
    exact = None if a.c4_exact is None else c4_exact_series(a.c4_exact, a.m_c4)
    D = load(a.scratch) if (exact is None or a.only != "c4") else None
    cap = {"core": float(core_spec.MAX_GROSS_STRESS), "c4": float(c4_spec_from()["frozen"]["max_gross_stress"])}
    paths = Paths()
    for who, m, win in (("core", a.m_core, W1_START), ("c4", a.m_c4, W2_START)):
        if a.only is not None and who != a.only:
            continue
        if who == "c4" and exact is not None:
            x = {b: exact[b].loc[win:] for b in ("TR", "PR")}
            print(f"c4: the exact spec-book series {a.c4_exact.name} ({exact['spec_id']}, {exact['policy']})")
        else:
            x = {b: account((D["PT"] if b == "TR" else D["PP"])[who], D["G"][who], m, cap[who])[0].loc[win:]
                 for b in ("TR", "PR")}
        if who == "core" and a.core_earning_only is not None:
            earn = pd.read_parquet(a.core_earning_only)["earning"].reindex(x["TR"].index)
            if earn.isna().any():
                raise ValueError("the earning mask does not cover the core's window")
            x = {b: v[earn.to_numpy(dtype=bool)] for b, v in x.items()}
        x = {b: v.values for b, v in x.items()}
        p95 = {b: max(pctl_maxdd(x[b], paths, 0.95).values()) for b in ("TR", "PR")}
        d_r = min(HALVE_DD, max(p95.values()))
        I21 = paths.get(len(x["PR"]))[0]
        r2 = float(np.quantile(np.prod(1 + x["PR"][I21[:, :120]], axis=1) - 1, 0.05))
        r3 = float(np.quantile(x["PR"][I21[:, :60]].std(axis=1, ddof=1) * np.sqrt(252), 0.95))
        print(f"{who} account x{m} (from {win.date()}): R1 D_R {d_r * 100:.2f}% (p95 TR {p95['TR'] * 100:.2f}%, "
              f"PR {p95['PR'] * 100:.2f}%, HALVE {HALVE_DD * 100:.0f}%) | R2 {r2 * 100:+.2f}% | R3 {r3 * 100:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
