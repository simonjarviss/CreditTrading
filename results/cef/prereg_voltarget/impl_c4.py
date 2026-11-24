"""The C4 account at its multiplier, built EXACTLY as implementation B would trade it (CEF trial 53, DRAFT).

    python3 -I results/cef/prereg_voltarget/impl_c4.py --scratch SCRATCH --c4-tree WORKTREES/c4-step2-spec --m 1.41 [--m 1.39]
        -> impl_c4_2026-10-30.json, impl_c4_output_2026-10-30.txt (this folder); about 4 minutes

ZERO TRIALS; fit window only. C4's code and spec are not on main, so this runs C4's OWN benchmark
functions from a clean C4 tree (c4-step2-spec at 6f62527, the tree the 2026-10-29 note built C4's
spec-book series from; asserted clean), never this tree's scripts, so no module from two trees
meets in one process. `-I` keeps the current directory off sys.path.

  cut_families -> trial_targets -> trial_book   (the reproduction gate: the committed 1.217 / 1.360 to 1e-9)
  h11_reference                                 the 1.90 spec book, the unit book here (= SCRATCH/alloc4 c4spec)
  model   m x unit, capped per row at 1.90 / (m x gross)            (what derive.py and risk.py assume)
  B       m x band_gross_capped(T, band, 1.90 / m)                  (`sizing_multiplier` on C4's spec)

The families panel is cut at 2022-12-30 ON READ into SCRATCH/prereg_voltarget/_c4_cut; the CRSP
values are read from the C4 tree's gitignored cache and never written; outputs are aggregates.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
STAMP = "2026-10-30"
FIT_END = pd.Timestamp("2022-12-30")
W1 = pd.Timestamp("2013-06-25")
OWN = pd.Timestamp("2005-02-22")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--c4-tree", type=Path, required=True)
    ap.add_argument("--m", type=float, action="append", required=True)
    ap.add_argument("--stamp", default=STAMP,
                    help="output stamp (2026-11-01: the approved x1.27 run writes its own files)")
    a = ap.parse_args()
    dec = json.loads((HERE / "declared_2026-10-30.json").read_text())
    if not datetime.fromisoformat(dec["declared_utc"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
        raise AssertionError("the declaration is not older than this run")
    root = a.c4_tree.resolve()
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if dirty:
        raise RuntimeError(f"{root} is not clean: {dirty[:200]}")
    sys.path.insert(0, str(root))
    from scripts.cef import band_frontier as bf
    from scripts.cef import c4_paper_benchmark as pb
    from scripts.cef.portfolio_baseline import max_drawdown

    say, out = [], dict(c4_tree=str(root.name), head=head)

    def p(*x):
        s = " ".join(str(v) for v in x)
        print(s, flush=True)
        say.append(s)

    spec = pb.load_spec()
    f = spec["frozen"]
    band, cap = float(f["band_width"]), float(f["max_gross_stress"])
    out.update(spec_id=spec["spec_id"], band=band, cap=cap)
    cut = a.scratch / "prereg_voltarget" / "_c4_cut"
    cut.mkdir(parents=True, exist_ok=True)
    p("families cut on read:", pb.cut_families(cut))
    T, _ = pb.trial_targets(cut)
    tb = pb.trial_book(cut, T)                      # raises unless the committed fit reproduces to 1e-9
    tb["T"] = T
    ref = pb.h11_reference(tb, spec)
    H1, RT, RP = ref["H"], ref["total"], ref["price"]
    chk = pd.read_parquet(a.scratch / "alloc4" / "series" / "c4spec_trpr.parquet")
    d = float((bf.evaluate(H1, RT)["pnl"].reindex(chk.index) - chk["tr"]).abs().max())
    if d > 1e-12:
        raise AssertionError(f"the unit spec book does not reproduce SCRATCH/alloc4 c4spec: {d}")
    p(f"{head[:7]} {spec['spec_id']}: gate passed (trial {tb['total_sr']:.6f} / {tb['price_sr']:.6f}); "
      f"unit spec book reproduces alloc4's series: max abs diff {d:.1e}")

    def line(H, R, win, refp=None):
        res = bf.evaluate(H, R)
        pnl, turn = res["pnl"].loc[win:], res["turn_series"].loc[win:]
        if pnl.index.max() > FIT_END:
            raise AssertionError("holdout leak")
        ann, vol, t = pnl.mean() * 252, pnl.std() * np.sqrt(252), turn.mean() * 252
        g = H.abs().sum(axis=1).loc[win:]
        o = dict(sr=ann / vol, ann=ann, vol=vol, mdd=max_drawdown(pnl)["mdd"], turn=t,
                 net_pct={bp: (ann - t * bp * 1e-4) * 100 for bp in (5, 15, 30)},
                 breakeven_bp=ann / t * 1e4, mean_gross=float(g.mean()), at_cap=float((g >= cap - 1e-9).mean()))
        if refp is not None:
            o["corr_with_model"] = float(pnl.corr(refp.loc[win:]))
            o["ann_minus_model_pct"] = float((pnl.mean() - refp.loc[win:].mean()) * 252 * 100)
        return o, res["pnl"]

    G1 = H1.abs().sum(axis=1)
    for m in a.m:
        fct = np.minimum(1.0, cap / (m * G1).where(G1 > 0, np.inf))
        HM = H1.mul(m * fct, axis=0)
        HB = m * bf.band_gross_capped(T, band, cap / m)
        for b, R in (("TR", RT), ("PR", RP)):
            for wl, win in (("own 2005-02-22", OWN), ("W1 2013-06-25", W1)):
                mod, mp = line(HM, R, win)
                rows = {"unit (x1.0)": line(H1, R, win)[0], "model": mod, "B sizing_multiplier": line(HB, R, win, mp)[0]}
                out[f"m{m}_{b}_{wl.split()[0]}"] = rows
                p(f"\nC4 account, m = {m}, {b}, {wl}..{FIT_END.date()}")
                for k, v in rows.items():
                    extra = (f" | corr with model {v['corr_with_model']:.4f}, ann - model {v['ann_minus_model_pct']:+.2f}%/yr"
                             if "corr_with_model" in v else "")
                    p(f"  {k:20s} SR {v['sr']:.3f} ann {v['ann'] * 100:5.2f}% vol {v['vol'] * 100:4.2f}% maxDD {v['mdd'] * 100:5.2f}% "
                      f"turn {v['turn']:5.1f}/yr mean gross {v['mean_gross']:.3f} at cap {v['at_cap']:.1%} | net "
                      + " / ".join(f"{x:+.2f}" for x in v["net_pct"].values()) + f" %/yr | breakeven {v['breakeven_bp']:.1f}bp" + extra)
    (HERE / f"impl_c4_{a.stamp}.json").write_text(json.dumps(out, indent=1, default=float))
    (HERE / f"impl_c4_output_{a.stamp}.txt").write_text("\n".join(say) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
