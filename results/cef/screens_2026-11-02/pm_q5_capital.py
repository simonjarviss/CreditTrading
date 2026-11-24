"""PM_TWO_ACCOUNTS.md §6: the capital split, the one lever outside the multipliers. ZERO TRIALS.

    python3 results/cef/screens_2026-11-02/pm_q5_capital.py --scratch SCRATCH
        -> pm_q5_output_2026-11-02.txt (this folder)

The core account cannot be resized without a reset that loses its record, so its $100k is fixed.
C4's account has never traded: its balance is set when it is reset before arming [doc: the
2026-10-29 four-sleeve note §0 item 5, docs.alpaca.markets/docs/paper-trading fetched 2026-10-29,
"arbitrary amount" on reset; not re-fetched here]. Each account keeps its approved multiplier, so
each account's own odds are unchanged; only the weights in "% return on all capital" move.

DERIVED, NOT SWEPT. With rho ~ 0 (pm_q1), the mean-variance optimal dollar risk ratio C4 : core is
S_c4 / S_core. On the EB-shrunk Sharpes of pm_q1 that gives K_c4 = 100k x (vol_core / vol_c4) x
(S_c4 / S_core). The fit Sharpes as measured and equal capital are shown beside it. Exact build,
W1, gross; the 5 / 15 / 30bp grid beside.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import pm_common as pc
from pm_common import W1_START, M_CORE, M_C4

STAMP = "2026-11-02"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    a = ap.parse_args()
    L = pc.Log()
    q1 = json.loads(Path(__file__).with_name(f"pm_q1_{STAMP}.json").read_text())
    C, K = pc.core_book(a.scratch), pc.c4_book(a.scratch)
    HC = M_CORE * pc.bf.band_gross_capped(C["T"], C["band"], C["cap"] / M_CORE)
    HK = M_C4 * pc.bf.band_gross_capped(K["T"], K["band"], K["cap"] / M_C4)
    for basis in ("pr", "tr"):
        lc, lk = pc.line(HC, C[f"R_{basis}"]), pc.line(HK, K[f"R_{basis}"])
        vc, vk = float(lc["pnl"].std() * np.sqrt(252)), float(lk["pnl"].std() * np.sqrt(252))
        S_fit = q1["joint"]["S"][basis.upper()]
        S_eb = q1["joint"]["eb"][basis.upper()]["S_shrunk"]
        ks = {"equal ($100k)": 100.0,
              "derived, EB-shrunk Sharpes": 100.0 * vc / vk * S_eb[1] / S_eb[0],
              "derived, fit Sharpes (not robust)": 100.0 * vc / vk * S_fit[1] / S_fit[0]}
        L(f"\n{basis.upper()}: account vols at the approved multipliers core {vc * 100:.2f}%, C4 {vk * 100:.2f}%")
        for lab, k4 in ks.items():
            w = k4 / (100.0 + k4)
            p = (1 - w) * lc["pnl"] + w * lk["pnl"]
            t = (1 - w) * lc["turn"] + w * lk["turn"]
            g = pc.grid_row(p, t)
            L(f"  {lab:34s} C4 ${k4:6.1f}k (all capital ${100 + k4:.0f}k): gross {g['ann'] * 100:5.2f}%/yr SR {g['sr']:.3f} vol "
              f"{g['vol'] * 100:.2f}% maxDD {g['mdd'] * 100:.2f}% | net {g['net'][5] * 100:+.2f} / {g['net'][15] * 100:+.2f} / "
              f"{g['net'][30] * 100:+.2f} at 5/15/30bp")
    L.write(Path(__file__).with_name(f"pm_q5_output_{STAMP}.txt"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
