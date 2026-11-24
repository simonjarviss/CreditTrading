"""The core account's exact flatten build at given multipliers: held-at-cap share, Sharpe, gross (2026-11-02).

    python3 -I results/cef/prereg_voltarget/flatten_exact.py --flat-root FLAT \\
        --harness-tree WORKTREES/research-thin-days --m 1.13 --m 1.30
        -> flatten_exact_2026-11-02.json, flatten_exact_output_2026-11-02.txt (this folder)

ZERO TRIALS; fit window only. This is the exact construction, implementation B, under the live
thin rule:

    m x band_gross_capped(T, band, 1.80 / m, below_min_names="flatten", thin=thin_sessions(T.index))

It is built on flatten_series.py's fit-cut panels (FLAT/fitcut_cef) with research-thin-days' harness
option, imported from its clean worktree (c7a1635) and not forked. `_common`'s house cap model
ignores the cap's feedback into the band; this build does not. Each figure is given over every W1
session and over the sessions the book earns on (a book held two sessions earlier).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
STAMP = "2026-11-02"
FIT_END = pd.Timestamp("2022-12-30")
W1 = pd.Timestamp("2013-06-25")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat-root", type=Path, required=True)
    ap.add_argument("--harness-tree", type=Path, required=True)
    ap.add_argument("--harness-sha", default="c7a163542ed4b1d278024ba5367e9f7ff1dce1b1")
    ap.add_argument("--m", type=float, action="append", required=True)
    a = ap.parse_args()
    root = a.harness_tree.resolve()
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if head != a.harness_sha or dirty:
        raise RuntimeError(f"{root} is at {head} (want {a.harness_sha}) or dirty")
    sys.path.insert(0, str(root))
    from scripts.cef import band_frontier as bf
    from scripts.cef import spec as hspec
    from scripts.cef.portfolio_baseline import max_drawdown
    bf.DATA_DIR = a.flat_root / "fitcut_cef"
    T, R = bf.fit_only(*bf.build_targets())
    thin = bf.thin_sessions(T.index)
    Rtr = bf.total_returns(R)
    BAND, CAP = float(hspec.BAND_WIDTH), float(hspec.MAX_GROSS_STRESS)
    ref = pd.read_parquet(a.flat_root / "alloc_review" / "core_trpr.parquet")
    H1 = bf.band_gross_capped(T, BAND, CAP, below_min_names="flatten", thin=thin)
    if float((bf.evaluate(H1, Rtr)["pnl"] - ref["tr"]).abs().max()) > 1e-12:
        raise AssertionError("the unit flatten book does not reproduce FLAT's core series")
    say, out = [], {}

    def p(*x):
        s = " ".join(str(v) for v in x)
        print(s, flush=True)
        say.append(s)

    for m in a.m:
        HB = m * bf.band_gross_capped(T, BAND, CAP / m, below_min_names="flatten", thin=thin)
        if HB.index.max() > FIT_END:
            raise AssertionError("holdout leak")
        g = HB.abs().sum(axis=1)
        earn = (g.shift(2).fillna(0.0) > 0).loc[W1:]
        held = (g > 0).loc[W1:]
        r = {}
        for b, RR in (("TR", Rtr), ("PR", R)):
            x = bf.evaluate(HB, RR)["pnl"].loc[W1:]
            xe = x[earn]
            r[b] = dict(ann=float(x.mean() * 252), sr=float(x.mean() / x.std() * np.sqrt(252)),
                        mdd=float(max_drawdown(x)["mdd"]), ann_trading=float(xe.mean() * 252),
                        vol_trading=float(xe.std() * np.sqrt(252)),
                        sr_trading=float(xe.mean() / xe.std() * np.sqrt(252)))
        at_cap = (g.loc[W1:] >= CAP - 1e-9)
        r["at_cap_all"] = float(at_cap.mean())
        r["at_cap_held"] = float(at_cap[held].mean())
        r["mean_gross_held"] = float(g.loc[W1:][held].mean())
        out[str(m)] = r
        p(f"x{m}: TR {r['TR']['ann'] * 100:.2f}%/yr SR {r['TR']['sr']:.3f} maxDD {r['TR']['mdd'] * 100:.2f}% | while trading "
          f"{r['TR']['ann_trading'] * 100:.2f}%/yr vol {r['TR']['vol_trading'] * 100:.2f}% SR {r['TR']['sr_trading']:.3f} | PR "
          f"{r['PR']['ann'] * 100:.2f}%/yr SR {r['PR']['sr']:.3f} | held at the cap {r['at_cap_held']:.1%} of sessions "
          f"with a book ({r['at_cap_all']:.1%} of all); mean gross when held {r['mean_gross_held']:.3f}")
    (HERE / f"flatten_exact_{STAMP}.json").write_text(json.dumps(out, indent=1))
    (HERE / f"flatten_exact_output_{STAMP}.txt").write_text("\n".join(say) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
