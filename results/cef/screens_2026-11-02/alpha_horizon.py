"""S4 -- a fast and a slow z on the same names: is the fast z's information new? Zero trials.

GRAVEYARD FIRST. This is a construction variant. `z_window = 63` was the argmax
of a swept column and failed out of sample (gross 1.75, net -0.298); the OU /
per-name kappa result says the live z already carries kappa^(1/2); price
reversal was 95% subsumed. A blend of z63 and z252 is a re-parameterisation of
the live signal, which fails this seat's bar 3 ("is the current signal provably
blind to it?") before any data. This screen measures ONE number to make the
kill concrete, not to choose a blend: the slope of the forward return on the
part of z63 orthogonal to z252, on WIDE17 and C4, fit only. 63 is the window
already in the graveyard, so nothing is swept.

NEGATIVE CONTROL (H12): the orthogonal part's slope on the NAV total-return
leg. A fast z that "predicts" through NAV is the stale-mark well.

The z63 panel comes from `band_frontier.build_panel` itself with its module
`Z_WINDOW` set to 63 inside this process only (restored after), so there is
still one definition of the signal. `MIN_PERIODS` (120, not spec-owned) cannot
exceed a 63-session window, so for z63 only it is set to the full window, 63,
and restored afterwards.

Run (from the worktree root):  python3 -B results/cef/screens_2026-11-02/alpha_horizon.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alpha_common as ac  # noqa: E402
from scripts.cef import band_frontier as bf  # noqa: E402


def z_with(window: int, universe, source=None, mask=None) -> pd.DataFrame:
    old, oldmp = bf.Z_WINDOW, bf.MIN_PERIODS
    try:
        bf.Z_WINDOW, bf.MIN_PERIODS = window, min(oldmp, window)
        return bf.build_panel(universe=universe, source=source, mask=mask, end=ac.FIT_END)["z"]
    finally:
        bf.Z_WINDOW, bf.MIN_PERIODS = old, oldmp


def main() -> int:
    print(ac.header("S4 FAST z63 ORTHOGONAL TO LIVE z252 (zero trials)"))
    from scripts.cef import c4_families as c4
    for loader in (ac.load_core, ac.load_c4):
        D = loader()
        if D["name"].startswith("C4"):
            m = c4.declared_mask(pd.read_csv(c4.FROZEN).ticker.tolist(), "M1M2")[D["U"]]
            z63 = z_with(63, D["U"], c4.FAM_SRC, m).reindex(D["idx"])
        else:
            z63 = z_with(63, D["U"]).reindex(D["idx"])
        ok = D["z"].notna() & z63.notna()
        z252 = ac.cs_demean(D["z"].where(ok))
        f63 = ac.cs_demean(z63.where(ok))
        rho = pd.Series([z252.loc[d].corr(f63.loc[d]) for d in D["idx"][::21]]).mean()
        # orthogonalise z63 on z252 date by date
        b = (f63 * z252).sum(axis=1) / (z252 ** 2).sum(axis=1)
        orth = f63.sub(z252.mul(b, axis=0))
        grid = D["idx"][::2]
        print(f"\n{D['name']}: mean cross-sectional corr(z63, z252) {rho:+.2f}")
        for lab, r in (("price TR", D["r_tr"]), ("NC NAV TR", D["r_nav_tr"])):
            y = ac.cs_demean(ac.fwd(r, 2, 3).where(ok)) * 1e4
            a = ac.pooled_ols(y, {"z252": z252, "z63_orth": orth}, grid, min_n=ac.MIN_NAMES)
            print(f"  {lab:<10} slope bp/z: z252 {a['z252']['coef']:+.2f} (t {a['z252']['t']:+.2f})   "
                  f"z63 orthogonal {a['z63_orth']['coef']:+.2f} (t {a['z63_orth']['t']:+.2f})   n {a['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
