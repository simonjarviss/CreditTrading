"""Gate 0 of PREREG_C4_LEVEL: a stress bound for the 42 dead candidates with no NAV. Zero trials, fit only.

`gate0_missingness.py` M3 found the non-coverage concentrated at fund level.
The 42 never-covered dead funds (36 with no CIK mapped, 6 mapped with no NAV)
earned -1,535bp against covered dead funds in their last year (t -2.70). If
they were cheap against peers, that is the wrong-way outcome for the level
signal, and leaving them out would flatter the dead-fund slope.

The bound adds each never-covered fund's last two half-years to the primary B
sample (family x period-end month cells; gate0_analysis.py), in demeaned units:
  y_dm     = its actual CRSP last-year excess return (dlret included; M3's ly_x),
             split equally over the two half-years. This is MEASURED;
  level_dm = an IMPUTED adverse level: the 5th, 25th or 50th percentile of the
             covered dead funds' demeaned level on their last two reports.
             Deep discounts are the adverse case.
It reports b_B / b_A for each. The worst-case direction is assumed, never
measured. It is a bound, not an estimate.

Run (from the worktree root):  python3 -B results/cef/screens_2026-11-02/gate0_stress.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate0_analysis as ga  # noqa: E402


def main() -> int:
    lines = []
    say = lambda s="": (print(s), lines.append(s))
    import alpha_common as ac
    say(ac.header("GATE 0 STRESS: the 42 never-covered dead funds, at adverse imputed levels (a bound)"))
    dsf, dl = ga.crsp_frames()
    names = pd.read_parquet(ga.CACHE / "cef_names.parquet")
    names["nameenddt"] = pd.to_datetime(names["nameenddt"])
    A, _ = ga.forward(ga.survivors_obs(dsf), dsf, dl)
    D, _ = ga.forward(ga.dead_obs(dsf, names), dsf, dl)
    ga.CELLS = "month"
    a = ga.demeaned(A)
    B = ga.demeaned(pd.concat([A, D]))
    bA, bB = ga.slope(a), ga.slope(B)
    Sxx, Sxy = float((B.level_dm ** 2).sum()), float((B.level_dm * B.y_dm).sum())
    dd = ga.demeaned(D)
    last2 = dd.sort_values("date").groupby("permno").tail(2)
    # the never-covered funds' measured last-year excess, recomputed exactly as gate0_missingness.py M3
    from gate0_pull_ncsr import candidates
    cand, _, _, _ = candidates()
    nav = pd.read_parquet(ga.CACHE / "ncsr_navs.parquet")
    covered = set(nav.dropna(subset=["nav"]).permno.astype(int))
    dsf2 = pd.read_parquet(ga.CACHE / "cef_dsf.parquet", columns=["permno", "date", "ret"])
    dsf2["date"] = pd.to_datetime(dsf2["date"])
    cal = pd.DatetimeIndex(sorted(dsf2.date.unique()))
    R = dsf2.pivot_table(index="date", columns="permno", values="ret")
    dlr = dl.set_index("permno")[["dlstdt", "dlret"]]
    ly = {}
    for p in cand.index:
        i = cal.searchsorted(min(dlr.dlstdt.get(p), ga.FIT_END), side="right") - 1
        if i - 252 < 0 or p not in R.columns:
            continue
        r = R[p].reindex(cal[i - 251:i + 1]).fillna(0).to_numpy()
        dr = dlr.dlret.get(p, np.nan)
        ly[p] = (float(np.prod(1 + r) * (1 + (0 if pd.isna(dr) else dr)) - 1) * 1e4, dlr.dlstdt.get(p).year)
    L = pd.DataFrame(ly, index=["ly", "dyear"]).T
    L["ly_x"] = L.ly - L.groupby("dyear")["ly"].transform("mean")
    nc = L[~L.index.isin(covered)].ly_x.dropna()
    say(f"B sample (primary cells): b_A {bA:+.2f}, b_B {bB:+.2f} bp/pp, ratio {bB / bA:+.3f}; Sxx {Sxx:.0f}, n {len(B)}")
    say(f"never-covered dead funds with a measured last-year return: {len(nc)}; their excess {nc.mean():+.0f}bp")
    for q in (0.05, 0.25, 0.50):
        lv = float(last2.level_dm.quantile(q))
        add_xy = float((lv * (nc / 2.0)).sum() * 2)       # two half-years per fund, each carrying half the year
        add_xx = float(2 * len(nc) * lv ** 2)
        b = (Sxy + add_xy) / (Sxx + add_xx)
        say(f"  imputed level = the {int(q * 100)}th percentile of covered dead funds' last two levels ({lv:+.2f}pp): "
            f"b_B {b:+.2f} bp/pp, ratio b_B/b_A {b / bA:+.3f}")
    (HERE / "gate0_stress_output.txt").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
