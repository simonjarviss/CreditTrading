"""The core's fit series under the LIVE thin-session rule (flatten), for trial 53's re-measure (2026-11-02).

    python3 -I results/cef/prereg_voltarget/flatten_series.py --scratch SCRATCH --out ROOT \\
        --harness-tree WORKTREES/research-thin-days
        -> ROOT/{alloc,alloc_review,alloc4}/...    the input layout _common.load reads, core = FLATTEN
        -> results/cef/prereg_voltarget/flatten_series_2026-11-02.json   checks and aggregates

ZERO TRIALS; fit window only. The live panels are copied with a parquet filter at 2022-12-30 into
ROOT/fitcut_cef. No later row is loaded, and nothing under data/ is written.

WHY. Trial 53's multipliers, odds and stops were derived on the canonical harness's book, which
HOLDS the previous target on a thin session (fewer than `min_names` eligible). The live sleeve
FLATTENS there instead (src/deploy/sleeves/cef_discount.py, the min_names block: every name FLAT,
before the band and the cap). The thin-days report
(results/backtests/thin-days-2026-11-03/REPORT.md, branch research-thin-days) gave the harness the
live rule: `band_gross_capped(..., below_min_names="flatten", thin=thin_sessions(...))`. Its default
is byte-identical, and it matches the live sleeve on all 5,480 dates.

THE HARNESS IS IMPORTED, NOT FORKED. That option is not on main yet, so this script runs the
harness from that branch's clean worktree, asserted at --harness-sha. `-I` keeps this script's
directory off sys.path, so no module from two trees meets in one process. The unit book's
parameters (vol target 0.06, band 0.048, cap 1.80) are read through that tree's spec.py. They are
v7's, and v8 differs from v7 only by `sizing_multiplier`, so the unit book is the same; this is
asserted below against this tree's spec.

C4 is NOT rebuilt. Its spec sets `below_min_names: "hold"`, so its live rule and its scored rule
are the same, and its series are copied from SCRATCH/alloc4 unchanged.

WHAT IS WRITTEN, in _common.load's layout, so derive.py, risk.py and stops.py run on it unchanged:
- alloc/series/core_{pnl,H}.parquet: the FLATTEN book, total return;
- alloc/series/c4_*: STAND-INS. The trial book's 1.80 files, which only the 2026-10-28 rule's
  sections of derive.py read, were cleared from SCRATCH on 2026-11-02. C4's SPEC book is written in
  their place so that `_common.load` runs. `derive.py --remeasure` does not run the sections that
  read them, and says so;
- alloc_review/core_trpr.parquet: flatten, total return and price only;
- alloc4/series/c4spec_*: copied;
- alloc4/series/core_proxy_*: the 2005-13 fixed-book proxy at the FLATTEN book's 10 year-end
  books. A book held on a thin session is flat, so its proxy is zero.

CHECKS, which raise on failure:
- the hold book here reproduces the derivation's core series to 0.0;
- the flatten book reproduces the thin-days report's W1 row (SR 0.799, 2.98%/yr, mean gross 0.465,
  daily sd 0.002351) to the printed digits;
- the m = 1.13 flatten B book reproduces that report's row (SR 0.795, maxDD 7.53%).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
THIS_REPO = HERE.parents[2]
STAMP = "2026-11-02"
FIT_END = pd.Timestamp("2022-12-30")
W1 = pd.Timestamp("2013-06-25")
PROXY = ("2005-02-22", "2013-06-24")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True, help="the allocation notes' scratch root (inputs)")
    ap.add_argument("--out", type=Path, required=True, help="a new root for the flatten inputs")
    ap.add_argument("--hold-out", type=Path, required=True,
                    help="a second root, the same layout with the core as the HOLD book (the reproduction check)")
    ap.add_argument("--harness-tree", type=Path, required=True)
    ap.add_argument("--harness-sha", default="c7a163542ed4b1d278024ba5367e9f7ff1dce1b1")
    a = ap.parse_args()
    root = a.harness_tree.resolve()
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if head != a.harness_sha or dirty:
        raise RuntimeError(f"{root} is at {head} (want {a.harness_sha}) or dirty: {dirty[:200]}")
    sys.path.insert(0, str(root))
    from scripts.cef import band_frontier as bf
    from scripts.cef import spec as hspec
    from scripts.cef.portfolio_baseline import group_proxy, max_drawdown
    from scripts.cef.w4_artifacts import groups

    # the unit book's parameters are the live spec's (v8 = v7 + sizing_multiplier only)
    live = json.loads((THIS_REPO / "ops/specs/cef_discount.frozen.json").read_text())["frozen"]
    for k, v in (("vol_target_annual", hspec.VOL_TARGET), ("band_width", hspec.BAND_WIDTH),
                 ("max_gross_stress", hspec.MAX_GROSS_STRESS), ("universe", list(hspec.UNIVERSE))):
        if (sorted(live[k]) if k == "universe" else float(live[k])) != (sorted(v) if k == "universe" else float(v)):
            raise ValueError(f"the harness tree's {k} {v} is not the live spec's {live[k]}")
    if "below_min_names" in live:
        raise ValueError("the live core spec sets below_min_names; this script assumes it is absent (flatten)")
    BAND, CAP = float(hspec.BAND_WIDTH), float(hspec.MAX_GROSS_STRESS)
    m_live = float(live["sizing_multiplier"])

    out, info = a.out, {"harness": f"research-thin-days @ {head}"}
    cut = out / "fitcut_cef"
    cut.mkdir(parents=True, exist_ok=True)
    for name, col in (("cef_prices", "date"), ("cef_nav", "date"), ("cef_distributions", "ex_date"),
                      ("cef_splits", "ex_date")):
        d = pd.read_parquet(THIS_REPO / "data" / "cef" / f"{name}.parquet", filters=[(col, "<=", FIT_END)])
        if len(d) and pd.to_datetime(d[col]).max() > FIT_END:
            raise AssertionError(f"{name}: the filter let a later row through")
        d.to_parquet(cut / f"{name}.parquet", index=False)
        info[f"cut_{name}_last"] = str(pd.to_datetime(d[col]).max().date()) if len(d) else None
    bf.DATA_DIR = cut
    T, R = bf.fit_only(*bf.build_targets())
    thin = bf.thin_sessions(T.index)
    Rtr = bf.total_returns(R)
    H_hold = bf.band_gross_capped(T, BAND, CAP)
    H_flat = bf.band_gross_capped(T, BAND, CAP, below_min_names="flatten", thin=thin)
    for f in (T, R, H_hold, H_flat):
        if f.index.max() > FIT_END:
            raise AssertionError("holdout leak")

    # alloc/series/core_pnl.parquet (the derivation's series) equals alloc_review's `tr` to 0.0
    # (_common.load asserts it); the former was cleared from SCRATCH, so the latter is the reference.
    ref = pd.read_parquet(a.scratch / "alloc_review" / "core_trpr.parquet")["tr"]
    p_hold = bf.evaluate(H_hold, Rtr)["pnl"]
    d = float((p_hold.reindex(ref.index) - ref).abs().max())
    if d > 1e-12 or not p_hold.index.equals(ref.index):
        raise AssertionError(f"the hold book does not reproduce the derivation's core series ({d})")
    ev_tr, ev_pr = bf.evaluate(H_flat, Rtr), bf.evaluate(H_flat, R)
    p_tr, p_pr = ev_tr["pnl"], ev_pr["pnl"]

    def row(p, H):
        x = p.loc[W1:]
        return dict(sr=float(x.mean() / x.std() * np.sqrt(252)), ann=float(x.mean() * 252),
                    vol=float(x.std() * np.sqrt(252)), mdd=float(max_drawdown(x)["mdd"]),
                    sd_daily=float(x.std()), mean_gross=float(H.abs().sum(axis=1).loc[W1:].mean()))
    rf = row(p_tr, H_flat)
    want = dict(sr=0.799, ann=0.0298, mean_gross=0.465, sd_daily=0.002351)
    for k, v in want.items():
        if round(rf[k], 3 if k in ("sr", "mean_gross") else (4 if k == "ann" else 6)) != v:
            raise AssertionError(f"flatten W1 {k} {rf[k]} does not reproduce the thin-days report's {v}")
    HB = m_live * bf.band_gross_capped(T, BAND, CAP / m_live, below_min_names="flatten", thin=thin)
    rb = row(bf.evaluate(HB, Rtr)["pnl"], HB)
    if (round(rb["sr"], 3), round(rb["mdd"] * 100, 2)) != (0.795, 7.53):
        raise AssertionError(f"flatten B at {m_live}: {rb} does not reproduce the report's SR 0.795 / maxDD 7.53%")
    w1thin = thin.loc[W1:]
    act = H_flat.abs().sum(axis=1).shift(2).fillna(0.0).loc[W1:] > 0          # sessions whose P&L is earned by a held book
    info.update(flatten_W1_TR=rf, flatten_W1_PR=row(p_pr, H_flat), hold_W1_TR=row(p_hold, H_hold),
                flatten_B_m=m_live, flatten_B_W1_TR=rb,
                thin_sessions_fit=int(thin.sum()), thin_sessions_W1=int(w1thin.sum()), W1_sessions=int(len(w1thin)),
                W1_share_earning_flatten=float(act.mean()))

    # ---- write the layout _common.load reads, for the flatten book and (the check) the hold book ----
    p = bf.build_panel(end="2022-12-30")
    rx = p["ret"][list(hspec.UNIVERSE)].reindex(H_flat.index)
    rt = bf.total_returns(rx)
    rpt, _ = group_proxy(rt.loc[PROXY[0]:PROXY[1]], groups())
    rpx, _ = group_proxy(rx.loc[PROXY[0]:PROXY[1]], groups())
    c4s = pd.read_parquet(a.scratch / "alloc4" / "series" / "c4spec_trpr.parquet")

    def write(rootdir, H, ptr, ppr):
        A, RV, B = rootdir / "alloc" / "series", rootdir / "alloc_review", rootdir / "alloc4" / "series"
        for dd in (A, RV, B):
            dd.mkdir(parents=True, exist_ok=True)
        ptr.rename("pnl").to_frame().to_parquet(A / "core_pnl.parquet")
        H.to_parquet(A / "core_H.parquet")
        c4s["tr"].rename("pnl").to_frame().to_parquet(A / "c4_pnl.parquet")            # stand-in (docstring)
        shutil.copy2(a.scratch / "alloc4" / "series" / "c4spec_H.parquet", A / "c4_H.parquet")
        pd.DataFrame({"tr": ptr, "pr": ppr}).to_parquet(RV / "core_trpr.parquet")
        for f in ("c4spec_trpr.parquet", "c4spec_H.parquet"):
            shutil.copy2(a.scratch / "alloc4" / "series" / f, B / f)
        # the 2005-13 proxy (SCRATCH/alloc4/proxy4.py's convention) at this book's 10 year-end books
        snaps = [H.index[H.index <= f"{y}-12-31"][-1] for y in range(2013, 2023)]
        tr_, pr_, g_ = {}, {}, {}
        for dte in snaps:
            w = H.loc[dte]
            tr_[str(dte.date())] = (rpt * w).sum(axis=1)
            pr_[str(dte.date())] = (rpx * w).sum(axis=1)
            g_[str(dte.date())] = float(w.abs().sum())
        pd.DataFrame(tr_).to_parquet(B / "core_proxy_tr.parquet")
        pd.DataFrame(pr_).to_parquet(B / "core_proxy_pr.parquet")
        pd.Series(g_).to_frame("gross").to_parquet(B / "core_proxy_gross.parquet")
        return g_

    g_ = write(out, H_flat, p_tr, p_pr)
    p_hold_pr = bf.evaluate(H_hold, R)["pnl"]
    gh = write(a.hold_out, H_hold, p_hold, p_hold_pr)
    # the hold root must BE the derivation's inputs: its proxies and price-only series equal
    # SCRATCH's to 0.0, so stops.py on it reproduces the published thresholds
    for f in ("core_proxy_tr.parquet", "core_proxy_pr.parquet"):
        x = pd.read_parquet(a.hold_out / "alloc4" / "series" / f)
        y = pd.read_parquet(a.scratch / "alloc4" / "series" / f)
        dd = float((x - y).abs().max().max())
        if dd > 1e-12:
            raise AssertionError(f"hold-root {f} does not reproduce SCRATCH/alloc4's ({dd})")
    pr0 = pd.read_parquet(a.scratch / "alloc_review" / "core_trpr.parquet")["pr"]
    if float((p_hold_pr.reindex(pr0.index) - pr0).abs().max()) > 1e-12:
        raise AssertionError("hold-root price-only series does not reproduce alloc_review's")
    info["year_end_books"] = {k: dict(gross=v, thin=bool(thin.loc[pd.Timestamp(k)]), hold_gross=gh[k])
                              for k, v in g_.items()}
    # active-session masks, for flatten_remeasure.py
    pd.DataFrame({"thin": thin, "earning": H_flat.abs().sum(axis=1).shift(2).fillna(0.0) > 0}).to_parquet(
        out / "flatten_masks.parquet")
    (HERE / f"flatten_series_{STAMP}.json").write_text(json.dumps(info, indent=1, default=float))
    print(json.dumps(info, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
