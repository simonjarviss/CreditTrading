"""Second method for the figures that drive the band draft (2026-11-05). Fit only; zero trials.

    python3 -B results/cef/band_cost_2026-11-05/crosscheck.py --cut-dir <band_cost.py's --cut-dir>
        -> results/cef/band_cost_2026-11-05/crosscheck_2026-11-05.txt

WHY. CLAUDE.md: "double-check anything that drives a decision -- a second method". Four things drive
`results/cef/BAND_COST_REDERIVATION_2026-11-05.md` (drafted as `PREREG_DRAFT_BAND_COST_2026-11-05.md`), and each is re-derived here a different way:

  1. BOOK IDENTITY. The plateau's books must be the books the accounts trade, as the trials that set
     them measured them. Core: trial 53's implementation B at x1.30 under the flatten rule, whose W1
     while-trading total-return Sharpe and return are committed in
     `results/cef/prereg_voltarget/flatten_exact_2026-11-02.json`. C4: trial 54's v5 blend at x1.26, whose
     turnover over live sessions is committed in `results/cef/prereg_c4_level/activation_measures_2026-11-03.json`.
     Both must reproduce to 1e-9 from band_cost.py's JSON.
  2. sigma_w AND phi_w by a second implementation: long-format pandas (stack, mask, groupby-free pooled
     moments) instead of band_cost.py's array slicing, on targets rebuilt in this process from the same
     fit-cut panels. They must agree to 1e-12.
  3. THE LAW'S ARITHMETIC. The 2026-09-06 inputs must give the note's 4.26% at 15bp and 4.85% at 22bp,
     and h(30)/h(15) must be 2^(1/3); and band_cost.py's h* must equal the law on its own inputs.
  4. THE NET DIFFERENCE h* - live at c*, by the accounting written out by hand
     ((H.shift(2) * R).sum, sum|dH|) rather than through harness.evaluate. Same convention (shift(2)),
     different code.

Nothing here reads 2023+: it reads band_cost.py's fit-cut copies and asserts every frame ends by
2022-12-30.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from scripts.cef import band_frontier as bf  # noqa: E402
from scripts.cef import c4_paper_benchmark as bm  # noqa: E402
from scripts.cef import spec as S  # noqa: E402

STAMP = "2026-11-05"
FIT_END = pd.Timestamp("2022-12-30")
W1 = pd.Timestamp("2013-06-25")
TOL = 1e-9


def pandas_dynamics(T: pd.DataFrame, inactive: pd.Series) -> tuple[float, float]:
    """sigma_w and phi_w in long format: one row per (date, name), the pair (T_{t-1}, T_t)."""
    prev = T.shift(1)
    act = (~inactive) & (~inactive.shift(1, fill_value=True))
    long = pd.DataFrame({"p": prev.stack(future_stack=True), "c": T.stack(future_stack=True)})
    long = long[long.index.get_level_values(0).isin(act[act].index)]
    long = long[(long["p"] != 0) & (long["c"] != 0) & long["p"].notna()]
    d = long["c"] - long["p"]
    return float(d.std(ddof=1)), float((long["c"] * long["p"]).sum() / (long["p"] ** 2).sum())


def by_hand(H: pd.DataFrame, R: pd.DataFrame, c_bp: float) -> tuple[float, float]:
    """Weights decided at t earn R[t+2]; cost on sum|dH| at t. Returns two statistics:
    the desk's net Sharpe, (annual gross - annual turnover x c) / GROSS vol (`harness._row_stats`,
    `band_frontier.row`: the table's column), and the Sharpe of the net daily series itself (what
    `sharpe_diff` tests). They differ slightly because the daily cost varies; both are reported."""
    pnl = (H.shift(2).fillna(0.0) * R).sum(axis=1)
    turn = H.diff().abs().sum(axis=1).fillna(0.0)
    desk = (pnl.mean() * 252 - turn.mean() * 252 * c_bp / 1e4) / (pnl.std() * np.sqrt(252))
    net = pnl - turn * c_bp / 1e4
    return float(desk), float(net.mean() / net.std() * np.sqrt(252))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut-dir", type=Path, required=True)
    a = ap.parse_args()
    J = json.loads((HERE / f"band_cost_{STAMP}.json").read_text())
    lines: list[str] = []
    fails: list[str] = []

    def say(s=""):
        print(s, flush=True)
        lines.append(s)

    def check(label, got, want, tol=TOL):
        ok = abs(got - want) <= tol
        say(f"  {'PASS' if ok else 'FAIL'}  {label}: {got!r} vs {want!r}")
        if not ok:
            fails.append(label)

    say(f"CROSS-CHECK of band_cost_{STAMP}.json (run {J['run_utc']}, code {J['code_head'][:7]})")

    # 1. book identity -----------------------------------------------------------------------
    say("\n1. BOOK IDENTITY")
    fe = json.loads((REPO / "results/cef/prereg_voltarget/flatten_exact_2026-11-02.json").read_text())["1.3"]
    live_c = J["core"]["plateau"]["basis"]["total"]["rows"][f"{J['core']['live_band']:.5f}"]["w1_trading"]
    check("core x1.30 W1 while-trading TR Sharpe = trial 53 flatten_exact", live_c["gross_sr"], fe["TR"]["sr_trading"])
    check("core x1.30 W1 while-trading TR ann = trial 53 flatten_exact", live_c["ann"], fe["TR"]["ann_trading"])
    pr_c = J["core"]["plateau"]["basis"]["price-only"]["rows"][f"{J['core']['live_band']:.5f}"]["w1_trading"]
    check("core x1.30 W1 while-trading PR Sharpe = trial 53 flatten_exact", pr_c["gross_sr"], fe["PR"]["sr_trading"])

    # 2 and 4, core --------------------------------------------------------------------------
    bf.DATA_DIR = a.cut_dir.resolve() / "fitcut_cef"
    T, R = bf.fit_only(*bf.build_targets())
    thin = bf.thin_sessions(T.index)
    Rtr = bf.total_returns(R)
    for f in (T, R, Rtr):
        if f.index.max() > FIT_END:
            raise AssertionError("holdout leak")
    say("\n2. sigma_w AND phi_w, second implementation (long format)")
    s, ph = pandas_dynamics(T, thin)
    p = J["core"]["dynamics"]["primary"]
    check("core sigma_w", s, p["sigma_w"], 1e-12)
    check("core phi_w", ph, p["phi_w"], 1e-12)

    say("\n3. THE LAW'S ARITHMETIC")
    o = J["original"]
    law = lambda c, sg, k: (3 * c / 1e4 * sg ** 2 / (2 * k)) ** (1 / 3)      # noqa: E731
    check("2026-09-06 inputs at 15bp, to 4 dp", round(law(15, o["sigma_w"], o["kappa_w"]), 4), o["h_15bp"], 0)
    check("2026-09-06 inputs at 22bp, to 4 dp", round(law(22, o["sigma_w"], o["kappa_w"]), 4), o["h_22bp"], 0)
    check("-ln(phi_w) of the 2026-09-06 inputs, to 5 dp", round(-math.log(o["phi_w"]), 5), o["kappa_w"], 0)
    check("h(30)/h(15) = 2^(1/3)", law(30, p["sigma_w"], p["kappa_w"]) / law(15, p["sigma_w"], p["kappa_w"]),
          2 ** (1 / 3), 1e-12)
    check("core h* = the law on band_cost's inputs", law(J["costs"]["core_B_bp"], p["sigma_w"], p["kappa_w"]),
          J["core"]["h_star"]["c_star"], 1e-15)
    q = J["c4"]["dynamics"]["primary"]
    check("C4 h* = the law on band_cost's inputs", law(J["costs"]["c4_B_bp"], q["sigma_w"], q["kappa_w"]),
          J["c4"]["h_star"]["c_star"], 1e-15)
    check("C4 c = core c x mean spread ratio", J["costs"]["core_B_bp"] * J["costs"]["spread_c4_mean_1552"]
          / J["costs"]["spread_core_mean_1552"], J["costs"]["c4_B_bp"], 1e-12)

    say("\n4. NET DIFFERENCE h* - live at c*, accounting written out by hand")
    m, cap = float(S.SIZING_MULTIPLIER), float(S.MAX_GROSS_STRESS)
    h, live, c = J["core"]["h_star"]["c_star"], J["core"]["live_band"], J["costs"]["core_B_bp"]
    Hh = m * bf.band_gross_capped(T, h, cap / m, below_min_names="flatten", thin=thin)
    Hl = m * bf.band_gross_capped(T, live, cap / m, below_min_names="flatten", thin=thin)
    rows = J["core"]["plateau"]["basis"]["total"]["rows"]
    rk = min(rows, key=lambda k: abs(float(k) - h))
    dh, nh = by_hand(Hh, Rtr, c)
    dl, nl = by_hand(Hl, Rtr, c)
    check("core net@c* at h*, TR (desk formula)", dh, rows[rk]["net_sr"]["c_star"])
    check("core net@c* at live, TR (desk formula)", dl, rows[f"{live:.5f}"]["net_sr"]["c_star"])
    pt = J["core"]["plateau"]["basis"]["total"]["h_vs_live"]["delta_annual"]
    # sharpe_diff forms its Sharpes from population moments (ddof 0); pandas' std is ddof 1. Over 4,531
    # sessions the two differ by a factor sqrt(4530/4531) on each Sharpe, about 1e-6 on this difference.
    check("core h* - live, Sharpe of the net daily series = sharpe_diff's delta (ddof 0 vs 1)", nh - nl, pt, 1e-5)

    # C4 -------------------------------------------------------------------------------------
    say("\n1/2/4, C4")
    fdir = a.cut_dir.resolve() / "fitcut_families"
    spec = bm.load_spec()
    f = spec["frozen"]
    m4, cap4 = float(f["sizing_multiplier"]), float(f["max_gross_stress"])
    T4, _ = bm.trial_targets(fdir)
    TB = bm.spec_targets(fdir, T4, spec)
    if TB.index.max() > FIT_END:
        raise AssertionError("holdout leak")
    am = json.loads((REPO / "results/cef/prereg_c4_level/activation_measures_2026-11-03.json").read_text())
    Hlive = m4 * bf.band_gross_capped(TB, float(f["band_width"]), cap4 / m4)
    lv = TB.abs().sum(axis=1) > 0
    check("C4 v5 turnover over live sessions = trial 54 activation measures",
          float(Hlive.diff().abs().sum(axis=1)[lv].mean() * 252), am["section_3_3"]["blend_spec_book"]["turn_per_yr"])
    A = TB.to_numpy()
    same = np.zeros(len(A), dtype=bool)
    same[1:] = (A[1:] == A[:-1]).all(axis=1)
    first = int(np.argmax(np.abs(A).sum(axis=1) > 0))
    inactive = same.copy()
    inactive[:first] = True
    s4, ph4 = pandas_dynamics(TB, pd.Series(inactive, index=TB.index))
    check("C4 sigma_w", s4, q["sigma_w"], 1e-12)
    check("C4 phi_w", ph4, q["phi_w"], 1e-12)

    say(f"\n{'ALL PASS' if not fails else 'FAILED: ' + '; '.join(fails)}")
    (HERE / f"crosscheck_{STAMP}.txt").write_text("\n".join(lines) + "\n")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
