"""Q4 of PM_TWO_ACCOUNTS.md: idle capacity per account, and what using it costs in drawdown odds. ZERO TRIALS.

    python3 results/cef/screens_2026-11-02/pm_q4_capacity.py --scratch SCRATCH
        -> pm_q4_2026-11-02.json, pm_q4_output_2026-11-02.txt (this folder); about 10 minutes

Fit window only (asserted). The odds are the trial-53 helpers' (results/cef/prereg_voltarget/_common.py:
`odds`, `Paths`, `worst`), so every figure here is on the same footing as PREREG_VOLTARGET §5.3:
P(max drawdown >= risk.halve_drawdown) and P(>= risk.kill_drawdown) within 252 sessions, compounded
from a high-water mark; SB21 / SB63 / GAUSS, 10,000 paths, common random numbers; the WORST method
and the WORSE of total return and price only; zero edge (demeaned) decides, the fit edge is beside.
HALVE does not act (report mode). W1 = 2013-06-25..2022-12-30; W2 = 2005-02-22..2022-12-30 with the
core before W1 as the fixed-book proxy at each of the 10 year-end books (min / median / max), which is
an upper bound because a fixed book is not vol-targeted through 2008 [U].

THE QUESTION IS ONE ACCOUNT AT A TIME, the other held at its approved multiplier. A grid over m is
shown for the shape; the limits are DERIVED as the crossings of the declared 2026-10-29 terms
(SCRATCH/alloc4/declared_threshold.json): (c) the account's zero-edge P(KILL) <= p* = 5% on W1 and on
W2 (decision statistic: the median of the 10 books for the core), and (d) its mean uncapped decided
gross on W1 <= its own cap. Neither limit is a recommendation; PM_TWO_ACCOUNTS.md says which binds.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import pm_common as pc
from pm_common import FIT_END, W1_START, W2_START, M_CORE, M_C4, assert_fit

STAMP = "2026-11-02"
P_STAR = 0.05


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    a = ap.parse_args()
    dec = json.loads((a.scratch / "alloc4" / "declared_threshold.json").read_text())
    if float(dec["p_star"]) != P_STAR:
        raise ValueError(f"declared p* is {dec['p_star']}, not {P_STAR}")
    L, out = pc.Log(), {}
    C, K, X = pc.core_book(a.scratch), pc.c4_book(a.scratch), pc.proxy(a.scratch)
    PT = pd.DataFrame({"core": C["pnl_tr"], "c4": K["pnl_tr"]})
    PP = pd.DataFrame({"core": C["pnl_pr"], "c4": K["pnl_pr"]})
    G = pd.DataFrame({"core": C["H"].abs().sum(axis=1), "c4": K["H"].abs().sum(axis=1)})
    caps = {"core": C["cap"], "c4": K["cap"]}
    paths = pc.Paths()
    snaps = list(X["t"].columns)
    L(f"HALVE {pc.HALVE_DD}, KILL {pc.KILL_DD} (core spec); caps core {caps['core']}, C4 {caps['c4']}; p* {P_STAR}; "
      f"10 core books {snaps[0]}..{snaps[-1]}")

    def acc(who: str, m: float, basis: str, snap: str | None = None) -> pd.Series:
        P = PT if basis == "TR" else PP
        p, g = P[who].copy(), G[who].copy()
        if snap is not None:
            pt = X["t"] if basis == "TR" else X["p"]
            p.loc[pt.index] = pt[snap]
            g.loc[pt.index] = float(X["g"][snap])
        x, f, Gm, _ = pc.account(p, g, m, caps[who])
        return x, f, Gm

    def row(who: str, m: float, other_m: float) -> dict:
        r = dict(who=who, m=m)
        x_tr, f, Gm = acc(who, m, "TR")
        x_pr, _, _ = acc(who, m, "PR")
        r["ann_TR"], r["ann_PR"] = pc.ann(x_tr.loc[W1_START:]), pc.ann(x_pr.loc[W1_START:])
        r["sr_PR"], r["vol_PR"] = pc.sr(x_pr.loc[W1_START:]), float(x_pr.loc[W1_START:].std() * np.sqrt(252))
        r["mdd_W1"] = max(float(pc.max_drawdown(x.loc[W1_START:])["mdd"]) for x in (x_tr, x_pr))
        r["mean_uncapped_gross"] = float(Gm.loc[W1_START:].mean())
        r["decided_above_cap"] = float((f.loc[W1_START:] < 1).mean())
        for edge in ("zero", "fit"):
            o = [pc.odds(x.loc[W1_START:].values, paths, edge) for x in (x_tr, x_pr)]
            r[f"W1_{edge}"] = (max(pc.worst(v, 0) for v in o), max(pc.worst(v, 1) for v in o))
        if who == "c4":
            for edge in ("zero", "fit"):
                o = [pc.odds(x.loc[W2_START:].values, paths, edge) for x in (x_tr, x_pr)]
                r[f"W2_{edge}"] = (max(pc.worst(v, 0) for v in o), max(pc.worst(v, 1) for v in o))
            r["mdd_W2"] = max(float(pc.max_drawdown(x.loc[W2_START:])["mdd"]) for x in (x_tr, x_pr))
        else:
            hz, kz, hf, kf, md = [], [], [], [], []
            for sn in snaps:
                xs = [acc("core", m, b, sn)[0].loc[W2_START:] for b in ("TR", "PR")]
                oz = [pc.odds(x.values, paths, "zero") for x in xs]
                of = [pc.odds(x.values, paths, "fit") for x in xs]
                hz.append(max(pc.worst(v, 0) for v in oz)); kz.append(max(pc.worst(v, 1) for v in oz))
                hf.append(max(pc.worst(v, 0) for v in of)); kf.append(max(pc.worst(v, 1) for v in of))
                md.append(max(float(pc.max_drawdown(x)["mdd"]) for x in xs))
            mmm = lambda v: [float(np.min(v)), float(np.median(v)), float(np.max(v))]
            r["W2_zero"] = (mmm(hz), mmm(kz))
            r["W2_fit"] = (mmm(hf), mmm(kf))
            r["mdd_W2"] = mmm(md)
        # the combined $200k book with the other account at its approved multiplier (W2: median core book)
        mc, m4 = (m, other_m) if who == "core" else (other_m, m)
        ks, hs = [], []
        for sn in snaps:
            xs = [0.5 * acc("core", mc, b, sn)[0] + 0.5 * acc("c4", m4, b)[0] for b in ("TR", "PR")]
            o = [pc.odds(x.loc[W2_START:].values, paths, "zero") for x in xs]
            hs.append(max(pc.worst(v, 0) for v in o)); ks.append(max(pc.worst(v, 1) for v in o))
        r["comb_W2_zero_median"] = (float(np.median(hs)), float(np.median(ks)))
        xc = 0.5 * acc("core", mc, "PR")[0] + 0.5 * acc("c4", m4, "PR")[0]
        xct = 0.5 * acc("core", mc, "TR")[0] + 0.5 * acc("c4", m4, "TR")[0]
        r["comb_ann_PR"], r["comb_ann_TR"] = pc.ann(xc.loc[W1_START:]), pc.ann(xct.loc[W1_START:])
        r["comb_sr_PR"], r["comb_vol_PR"] = pc.sr(xc.loc[W1_START:]), float(xc.loc[W1_START:].std() * np.sqrt(252))
        return r

    def show(r):
        w2h, w2k = r["W2_zero"]
        w2 = (f"W2 H {'/'.join(f'{v * 100:.1f}' for v in w2h)} K {'/'.join(f'{v * 100:.1f}' for v in w2k)}"
              if isinstance(w2h, list) else f"W2 H {w2h * 100:.1f} K {w2k * 100:.1f}")
        L(f"  m {r['m']:.2f}: acct PR {r['ann_PR'] * 100:5.2f}% (TR {r['ann_TR'] * 100:5.2f}%) SR {r['sr_PR']:.3f} vol {r['vol_PR'] * 100:.2f}% "
          f"| uncapped gross {r['mean_uncapped_gross']:.3f} above cap {r['decided_above_cap']:5.1%} | zero edge W1 H {r['W1_zero'][0] * 100:.1f} "
          f"K {r['W1_zero'][1] * 100:.2f} | {w2} | maxDD W1 {r['mdd_W1'] * 100:.1f}% | combined PR {r['comb_ann_PR'] * 100:.2f}% "
          f"SR {r['comb_sr_PR']:.3f}, W2 median H {r['comb_W2_zero_median'][0] * 100:.1f} K {r['comb_W2_zero_median'][1] * 100:.2f}")

    grids = {"core": sorted({1.00, 1.05, 1.10, M_CORE, 1.15, 1.20, 1.25, 1.30, 1.35, 1.40, 1.45, 1.50, 1.55, 1.60}),
             "c4": sorted({1.00, 1.10, 1.20, M_C4, 1.30, 1.35, 1.40, 1.50})}
    res = {}
    for who, other in (("core", M_C4), ("c4", M_CORE)):
        L(f"\n{who.upper()} ACCOUNT, the other at its approved multiplier ({other}); zero-edge odds, % (HALVE / KILL)")
        res[who] = []
        for m in grids[who]:
            r = row(who, m, other)
            show(r)
            res[who].append(r)
    out["grid"] = res

    # ---- the derived limits: crossings of term (c) and term (d), linear between grid points ---------------
    def crossing(rows, key, thr):
        xs = [r["m"] for r in rows]
        ys = [key(r) for r in rows]
        for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
            if y0 <= thr < y1:
                return x0 + (thr - y0) * (x1 - x0) / (y1 - y0)
        return None if ys[0] > thr else float("inf")

    lim = {}
    for who in ("core", "c4"):
        rows = res[who]
        lim[who] = dict(
            term_d=crossing(rows, lambda r: r["mean_uncapped_gross"], caps[who]),
            term_c_W1=crossing(rows, lambda r: r["W1_zero"][1], P_STAR),
            term_c_W2=crossing(rows, (lambda r: r["W2_zero"][1][1]) if who == "core" else (lambda r: r["W2_zero"][1]), P_STAR),
            term_c_W2_worst_book=crossing(rows, lambda r: r["W2_zero"][1][2], P_STAR) if who == "core" else None,
            halve_W1_20pct=crossing(rows, lambda r: r["W1_zero"][0], 0.20))
        L(f"\n  {who} limits (m, linear between grid points): term (d) {lim[who]['term_d']}; term (c) W1 {lim[who]['term_c_W1']}; "
          f"term (c) W2 (decision: {'median book' if who == 'core' else 'own'}) {lim[who]['term_c_W2']}"
          + (f"; W2 worst book {lim[who]['term_c_W2_worst_book']}" if who == "core" else "")
          + f"; P(HALVE) W1 reaches 20% at {lim[who]['halve_W1_20pct']}")
    out["limits"] = lim

    # ---- the exact build at the binding core limit, rounded down, C4 at 1.27 -----------------------------
    binding = min(v for v in (lim["core"]["term_d"], lim["core"]["term_c_W1"], lim["core"]["term_c_W2"]) if v is not None)
    mb = float(np.floor(binding * 100) / 100)
    L(f"\nEXACT BUILD, core at its binding limit {binding:.4f} -> {mb:.2f} (2 dp, rounded down), C4 at {M_C4}; W1; gross headline, grid beside")
    ex = {}
    for lab, mc in (("approved", M_CORE), ("core at its own limit", mb)):
        HC = mc * pc.bf.band_gross_capped(C["T"], C["band"], C["cap"] / mc)
        HK = M_C4 * pc.bf.band_gross_capped(K["T"], K["band"], K["cap"] / M_C4)
        r = {}
        for basis in ("PR", "TR"):
            lc, lk = pc.line(HC, C[f"R_{basis.lower()}"]), pc.line(HK, K[f"R_{basis.lower()}"])
            r[basis] = dict(core=pc.grid_row(lc["pnl"], lc["turn"]), comb=pc.grid_row(0.5 * lc["pnl"] + 0.5 * lk["pnl"], 0.5 * lc["turn"] + 0.5 * lk["turn"]))
            c = r[basis]["comb"]
            L(f"  {lab:22s} m core {mc:.2f} {basis}: combined {c['ann'] * 100:5.2f}%/yr SR {c['sr']:.3f} turn {c['turn']:.1f} | net "
              f"{c['net'][5] * 100:+.2f} / {c['net'][15] * 100:+.2f} / {c['net'][30] * 100:+.2f} at 5/15/30bp | core account "
              f"{r[basis]['core']['ann'] * 100:.2f}% SR {r[basis]['core']['sr']:.3f} maxDD {r[basis]['core']['mdd'] * 100:.1f}%")
        g = HC.abs().sum(axis=1).loc[W1_START:]
        r["core_held_at_cap"] = float((g >= C["cap"] - 1e-9).mean())
        L(f"  {'':22s} core held at cap {r['core_held_at_cap']:.1%}")
        ex[lab] = r
    out["exact"] = ex
    out["binding_core"] = dict(m=binding, written=mb)
    (Path(__file__).with_name(f"pm_q4_{STAMP}.json")).write_text(json.dumps(out, indent=1, default=float))
    L.write(Path(__file__).with_name(f"pm_q4_output_{STAMP}.txt"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
