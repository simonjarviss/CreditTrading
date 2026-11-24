"""Q1 of PM_TWO_ACCOUNTS.md: joint versus separate sizing of the core and C4 accounts. ZERO TRIALS.

    python3 results/cef/screens_2026-11-02/pm_q1_joint.py --scratch SCRATCH
        -> pm_q1_2026-11-02.json, pm_q1_output_2026-11-02.txt (this folder)

Fit window only (asserted). No spec is read for a decision and none is changed.

WHAT IT DOES, IN ORDER.
1. The core-C4 correlation of the unit books' daily gross P&L: W1 and its two eras, the H5 eras the
   core has, 21-session non-overlapping sums, the rolling 252-session distribution, and the tails
   (each sleeve's worst 5% of days). Through 2008 the core is the fixed-book proxy, labelled.
2. The jointly optimal split at the combined target the team lead accepted (5.25%), DERIVED, not
   swept: on the iso-vol line, the mean-variance risk weights x ∝ R^-1 S (R the correlation, S the
   unit books' Sharpes), from (i) the fit Sharpes as measured and (ii) an empirical-Bayes shrinkage
   of the two Sharpes toward their mean, tau^2 = max(0, var(S) - mean SE^2). The constraint that can
   bind on the line is each account's mean uncapped gross <= its own cap (the 2026-10-29 rule's term
   (d)); where the optimum breaks it, the account is held at its term-(d) multiplier and the other
   takes the rest of the risk.
3. The plateau along the whole 5.25% iso-vol line (C4 risk weight 0.30..0.70), on the house cap
   model, gross TR and PR, with the derived points marked. The argmax of the line is named and not
   chosen.
4. The exact build (route B, m x band_gross_capped(T, band, cap/m)) at the approved 1.13 / 1.27 and
   at the derived constrained optimum, rounded down to 2 dp as the declared rule rounds, with the
   5 / 15 / 30bp grid. Same policy at a different size, so H2's turnover match does not apply
   (the trial-53 note §4); turnover is shown and priced.
5. What binds: per account, the vol target, the stress cap (held-at-cap share; mean uncapped gross),
   Reg T 2x, and term (d).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import pm_common as pc
from pm_common import FIT_END, W1_START, W2_START, M_CORE, M_C4, S_COMB, assert_fit
from scripts.research.inference import stationary_bootstrap_corr
from scripts.research.resampling import sharpe_diff

STAMP = "2026-11-02"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    a = ap.parse_args()
    L, out = pc.Log(), {}
    C, K = pc.core_book(a.scratch), pc.c4_book(a.scratch)
    L(f"inputs: core unit book reproduces alloc_review/core_trpr to {C['repro']:.1e}; C4 spec book reproduces "
      f"alloc4/series/c4spec_trpr to {K['repro']:.1e}; caps core {C['cap']} / C4 {K['cap']}; band {C['band']} / {K['band']}")
    PT = pd.DataFrame({"core": C["pnl_tr"], "c4": K["pnl_tr"]})
    PP = pd.DataFrame({"core": C["pnl_pr"], "c4": K["pnl_pr"]})
    G = pd.DataFrame({"core": C["H"].abs().sum(axis=1), "c4": K["H"].abs().sum(axis=1)})
    assert_fit(PT, PP, G)
    w1 = slice(W1_START, FIT_END)

    # ---- 1. correlation ------------------------------------------------------------------------
    L("\n1. CORE-C4 CORRELATION, unit books, daily gross P&L (stationary bootstrap 95% CI, 2,000 draws)")
    corr = {}
    for basis, P in (("TR", PT), ("PR", PP)):
        o = P.loc[w1]
        for blk in (21, 63):
            r = stationary_bootstrap_corr(o.core.values, o.c4.values, blk, seed=20261102, reps=2000)
            r["ci"] = (r["lo"], r["hi"])
            corr[f"W1_{basis}_daily_b{blk}"] = r
        s21 = o.groupby(np.arange(len(o)) // 21).sum()
        r = stationary_bootstrap_corr(s21.core.values, s21.c4.values, 3, seed=20261102, reps=2000)
        r["ci"] = (r["lo"], r["hi"])
        corr[f"W1_{basis}_m21"] = r
        L(f"  W1 {basis}: daily {corr[f'W1_{basis}_daily_b21']['rho']:+.3f} "
          f"(CI b21 {corr[f'W1_{basis}_daily_b21']['ci'][0]:+.3f}..{corr[f'W1_{basis}_daily_b21']['ci'][1]:+.3f}; "
          f"b63 {corr[f'W1_{basis}_daily_b63']['ci'][0]:+.3f}..{corr[f'W1_{basis}_daily_b63']['ci'][1]:+.3f}) | "
          f"21-session sums {corr[f'W1_{basis}_m21']['rho']:+.3f} ({corr[f'W1_{basis}_m21']['ci'][0]:+.3f}..{corr[f'W1_{basis}_m21']['ci'][1]:+.3f}, n {len(s21)})")
    eras = {}
    for lab, s, e in pc.ERAS_W1 + (("2013-06..2014", "2013-06-25", "2014-12-31"),) + pc.ERAS_H5[2:]:
        o = PT.loc[s:e]
        o = o.loc[max(pd.Timestamp(s), W1_START):]
        eras[lab] = dict(rho_TR=float(o.core.corr(o.c4)), rho_PR=float(PP.loc[o.index].core.corr(PP.loc[o.index].c4)),
                         n=len(o), sr_core=pc.sr(o.core), sr_c4=pc.sr(o.c4))
        L(f"  era {lab:14s} n {len(o):4d}: rho TR {eras[lab]['rho_TR']:+.3f} PR {eras[lab]['rho_PR']:+.3f} | "
          f"unit SR core {eras[lab]['sr_core']:.2f} C4 {eras[lab]['sr_c4']:.2f}")
    roll = PT.loc[w1].core.rolling(252).corr(PT.loc[w1].c4).dropna()
    q = roll.quantile([0.0, 0.05, 0.5, 0.95, 1.0])
    L(f"  rolling 252-session rho (TR): min {q[0.0]:+.3f}, p5 {q[0.05]:+.3f}, median {q[0.5]:+.3f}, p95 {q[0.95]:+.3f}, "
      f"max {q[1.0]:+.3f} (min at {roll.idxmin().date()}, max at {roll.idxmax().date()})")
    o = PT.loc[w1]
    tails = {}
    for who, other in (("core", "c4"), ("c4", "core")):
        cut = o[who].quantile(0.05)
        bad = o[who] <= cut
        tails[who] = dict(other_mean_bp=float(o.loc[bad, other].mean() * 1e4), own_mean_bp=float(o.loc[bad, who].mean() * 1e4),
                          rho_in_tail=float(o.loc[bad].corr().iloc[0, 1]), n=int(bad.sum()))
        L(f"  on {who}'s worst 5% of W1 days (n {bad.sum()}): {who} {tails[who]['own_mean_bp']:+.1f}bp, "
          f"{other} {tails[who]['other_mean_bp']:+.1f}bp")
    prox = pc.proxy(a.scratch)
    w2 = []
    for sn in prox["t"].columns:
        x = PT["core"].copy()
        x.loc[prox["t"].index] = prox["t"][sn]
        w2.append(float(x.loc["2005-02-22":"2009-12-31"].corr(PT["c4"].loc["2005-02-22":"2009-12-31"])))
    L(f"  2005-02..2009 with the core PROXIED (fixed books, 10 snapshots): rho TR min {min(w2):+.3f} / "
      f"median {np.median(w2):+.3f} / max {max(w2):+.3f}  [a proxy, not the book]")
    out["corr"] = dict(W1={k: dict(rho=v["rho"], ci=list(v["ci"])) for k, v in corr.items()}, eras=eras,
                       rolling252=dict(q.to_dict()), tails=tails, proxy_2005_09=w2)

    # ---- 2. the joint optimum on the 5.25% iso-vol line ------------------------------------------
    L(f"\n2. JOINT OPTIMUM AT THE ACCEPTED COMBINED TARGET {S_COMB:.2%} (two $100k accounts; W1; unit books)")
    _, mA, sd, sdc = pc.multipliers(PT, S_COMB)
    if abs(mA["core"] - 1.1357) > 5e-5 or abs(mA["c4"] - 1.2712) > 5e-5:
        raise AssertionError(f"equal-risk multipliers do not reproduce trial 53's 1.1357 / 1.2712: {mA}")
    L(f"  equal risk reproduces trial 53: core {mA['core']:.4f}, C4 {mA['c4']:.4f} (written 1.13 / 1.27)")
    o = PT.loc[w1]
    rho = float(o.core.corr(o.c4))
    S = {b: np.array([pc.sr(P.loc[w1].core), pc.sr(P.loc[w1].c4)]) for b, P in (("TR", PT), ("PR", PP))}
    sdiff = {b: sharpe_diff(P.loc[w1].c4.values, P.loc[w1].core.values, block=21, M=999, seed=20261102)
             for b, P in (("TR", PT), ("PR", PP))}
    yrs = len(o) / 252
    from scripts.research.inference import psr  # noqa: F401  (SE from the PSR variance term below)
    eb = {}
    for b, P in (("TR", PT), ("PR", PP)):
        se2 = []
        for k in ("core", "c4"):
            x = P.loc[w1][k]
            s_ = x.mean() / x.std()
            v = (1 - x.skew() * s_ + (x.kurt() + 3 - 1) / 4 * s_ ** 2) / (len(x) - 1)
            se2.append(v * 252)
        tau2 = max(0.0, float(np.var(S[b], ddof=1)) - float(np.mean(se2)))
        shrink = [tau2 / (tau2 + s) for s in se2]
        mu = S[b].mean()
        eb[b] = dict(se=[float(np.sqrt(s)) for s in se2], tau2=tau2, S_shrunk=[float(mu + w * (x - mu)) for w, x in zip(shrink, S[b])])
    for b in ("TR", "PR"):
        L(f"  {b}: unit SR core {S[b][0]:.3f}, C4 {S[b][1]:.3f}; C4 - core {sdiff[b]['delta_annual']:+.3f} "
          f"(Boot-TS block 21: p {sdiff[b]['p_value']:.3f}, 95% CI {sdiff[b]['ci_annual'][0]:+.2f}..{sdiff[b]['ci_annual'][1]:+.2f}); "
          f"PSR-term SEs {eb[b]['se'][0]:.3f} / {eb[b]['se'][1]:.3f} -> EB tau^2 {eb[b]['tau2']:.4f}, shrunk SR "
          f"{eb[b]['S_shrunk'][0]:.3f} / {eb[b]['S_shrunk'][1]:.3f}")
    Rm = np.array([[1, rho], [rho, 1]])
    gmean = {"core": float(G.loc[w1].core.mean()), "c4": float(G.loc[w1].c4.mean())}
    m_d = {"core": C["cap"] / gmean["core"], "c4": K["cap"] / gmean["c4"]}
    L(f"  rho (W1, TR, daily) {rho:+.4f}; mean unit gross core {gmean['core']:.3f}, C4 {gmean['c4']:.3f} -> "
      f"term (d) multipliers core {m_d['core']:.4f}, C4 {m_d['c4']:.4f}")

    def m_of_b(b4: float) -> dict:
        _, mm, _, _ = pc.multipliers(PT, S_COMB, b=(1 - b4, b4))
        return mm

    def b4_from_x(x) -> float:
        # risk weights in unit-vol terms -> the (b_core, b_c4) the multipliers() helper takes
        x = np.asarray(x, float) / np.sum(x)
        return float(x[1])

    # b4 at which C4 sits exactly at its term-(d) multiplier on the 5.25% line (bisection; m_c4 rises in b4)
    lo, hi = 0.3, 0.8
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if m_of_b(mid)["c4"] < m_d["c4"] else (lo, mid)
    b4_d = lo
    pts = {"equal risk (the ruling)": 0.5}
    for b in ("TR", "PR"):
        for lab, Sv in (("fit", S[b]), ("EB-shrunk", np.array(eb[b]["S_shrunk"]))):
            x = np.linalg.solve(Rm, Sv)
            pts[f"MV, {lab} Sharpes, {b}"] = b4_from_x(x)
    pts["C4 at its term (d)"] = b4_d
    der = {}
    for lab, b4 in pts.items():
        mm = m_of_b(b4)
        feas = mm["c4"] <= m_d["c4"] + 1e-12 and mm["core"] <= m_d["core"] + 1e-12
        der[lab] = dict(b4=b4, m=mm, term_d_ok=bool(feas))
        L(f"  {lab:32s} C4 risk weight {b4:.3f}: m core {mm['core']:.4f}, C4 {mm['c4']:.4f} | term (d) "
          f"{'holds' if feas else 'FAILS (C4 above its cap in mean)'}")
    out["joint"] = dict(rho=rho, S=S, sharpe_diff={b: {k: (list(v) if isinstance(v, tuple) else v) for k, v in sdiff[b].items()} for b in sdiff},
                        eb=eb, gmean=gmean, m_term_d=m_d, points=der)

    # ---- 3. the plateau along the iso-vol line ------------------------------------------------------
    L(f"\n3. THE {S_COMB:.2%} ISO-VOL LINE, house cap model (m x unit book, one uniform cap factor per account), W1")
    rows = []
    for b4 in sorted(set(np.round(np.arange(0.30, 0.7001, 0.025), 4)) | {round(v, 4) for v in pts.values()}):
        mm = m_of_b(b4)
        r = dict(b4=b4, m_core=mm["core"], m_c4=mm["c4"], term_d=bool(mm["c4"] <= m_d["c4"] + 1e-12 and mm["core"] <= m_d["core"] + 1e-12))
        for basis, P in (("TR", PT), ("PR", PP)):
            xa, fa, _, _ = pc.account(P.core, G.core, mm["core"], C["cap"])
            xb, fb, _, _ = pc.account(P.c4, G.c4, mm["c4"], K["cap"])
            x = (0.5 * xa + 0.5 * xb).loc[w1]
            r[f"ann_{basis}"], r[f"sr_{basis}"], r[f"vol_{basis}"] = pc.ann(x), pc.sr(x), float(x.std() * np.sqrt(252))
            if basis == "TR":
                r["binds_core"], r["binds_c4"] = float((fa.loc[w1] < 1).mean()), float((fb.loc[w1] < 1).mean())
        rows.append(r)
    T3 = pd.DataFrame(rows)
    at = T3.loc[(T3.b4 - 0.5).abs().idxmin()]
    L(" C4 wt  m core  m C4  term(d)  gross TR  SR TR  gross PR  SR PR  vol TR  core cap binds  C4 cap binds")
    for _, r in T3.iterrows():
        tag = [k for k, v in pts.items() if abs(v - r.b4) < 5e-5]
        L(f" {r.b4:.3f}  {r.m_core:.3f}  {r.m_c4:.3f}  {'ok ' if r.term_d else 'FAIL'}   {r.ann_TR * 100:6.2f}%  {r.sr_TR:.3f}  "
          f"{r.ann_PR * 100:6.2f}%  {r.sr_PR:.3f}  {r.vol_TR * 100:.2f}%   {r.binds_core:6.1%}        {r.binds_c4:6.1%}"
          + (f"   <- {'; '.join(tag)}" if tag else ""))
    feas = T3[T3.term_d]
    span = dict(TR=[float(feas.ann_TR.min() - at.ann_TR), float(feas.ann_TR.max() - at.ann_TR)],
                PR=[float(feas.ann_PR.min() - at.ann_PR), float(feas.ann_PR.max() - at.ann_PR)])
    am = feas.loc[feas.ann_PR.idxmax()]
    L(f"  on the feasible part of the line (term (d) holds; C4 weight {feas.b4.min():.3f}..{feas.b4.max():.3f}), gross return "
      f"differs from equal risk by {span['TR'][0] * 100:+.2f}..{span['TR'][1] * 100:+.2f}%/yr TR and {span['PR'][0] * 100:+.2f}.."
      f"{span['PR'][1] * 100:+.2f}%/yr PR; Sharpe {feas.sr_TR.min():.3f}..{feas.sr_TR.max():.3f} TR")
    L(f"  NOT CHOSEN: the feasible line's PR-return argmax, C4 weight {am.b4:.3f} (m {am.m_core:.3f} / {am.m_c4:.3f}), "
      f"{am.ann_PR * 100:.2f}%/yr PR")
    T3.to_csv(Path(__file__).with_name(f"pm_q1_isovol_{STAMP}.csv"), index=False)
    out["isovol"] = dict(span_vs_equal=span, argmax_feasible=am.to_dict())

    # ---- 4. exact build at the approved pair and at the derived constrained point ------------------
    L("\n4. EXACT BUILD (route B) on W1, gross headline; the 5/15/30bp grid is the real-money view, beside it")
    pc.check_band_dyn(C["T"], C["band"], C["cap"], M_CORE)
    dC = der["C4 at its term (d)"]["m"]
    books = {"approved 1.13 / 1.27": (M_CORE, M_C4),
             "C4 at term (d), 2 dp down": (np.floor(dC["core"] * 100) / 100, np.floor(dC["c4"] * 100) / 100)}
    ex = {}
    for lab, (mc, m4) in books.items():
        HC = mc * pc.bf.band_gross_capped(C["T"], C["band"], C["cap"] / mc)
        HK = m4 * pc.bf.band_gross_capped(K["T"], K["band"], K["cap"] / m4)
        r = dict(m_core=mc, m_c4=m4)
        for basis in ("TR", "PR"):
            lc, lk = pc.line(HC, C[f"R_{basis.lower()}"]), pc.line(HK, K[f"R_{basis.lower()}"])
            comb = 0.5 * lc["pnl"] + 0.5 * lk["pnl"]
            ct = 0.5 * lc["turn"] + 0.5 * lk["turn"]
            r[basis] = dict(core=pc.grid_row(lc["pnl"], lc["turn"]), c4=pc.grid_row(lk["pnl"], lk["turn"]),
                            comb=pc.grid_row(comb, ct),
                            eras={e: pc.sr(comb.loc[s:t]) for e, s, t in pc.ERAS_W1})
        gC, gK = HC.abs().sum(axis=1).loc[W1_START:], HK.abs().sum(axis=1).loc[W1_START:]
        r["held_at_cap"] = dict(core=float((gC >= C["cap"] - 1e-9).mean()), c4=float((gK >= K["cap"] - 1e-9).mean()))
        r["mean_held_gross"] = dict(core=float(gC.mean()), c4=float(gK.mean()))
        ex[lab] = r
        for basis in ("PR", "TR"):
            c = r[basis]["comb"]
            L(f"  {lab:27s} {basis}: combined gross {c['ann'] * 100:5.2f}%/yr SR {c['sr']:.3f} vol {c['vol'] * 100:.2f}% maxDD "
              f"{c['mdd'] * 100:.2f}% turn {c['turn']:.1f}/yr | net {c['net'][5] * 100:+.2f} / {c['net'][15] * 100:+.2f} / "
              f"{c['net'][30] * 100:+.2f} %/yr at 5/15/30bp | core {r[basis]['core']['ann'] * 100:.2f}% C4 {r[basis]['c4']['ann'] * 100:.2f}% "
              f"| era SR {' / '.join(f'{v:.2f}' for v in r[basis]['eras'].values())}")
        L(f"  {'':27s} held at cap: core {r['held_at_cap']['core']:.1%}, C4 {r['held_at_cap']['c4']:.1%}; mean held gross "
          f"core {r['mean_held_gross']['core']:.3f}, C4 {r['mean_held_gross']['c4']:.3f}")
    d_ = {b: ex["C4 at term (d), 2 dp down"][b]["comb"]["ann"] - ex["approved 1.13 / 1.27"][b]["comb"]["ann"] for b in ("TR", "PR")}
    L(f"  difference (term-(d) point minus approved): {d_['PR'] * 100:+.2f}%/yr PR, {d_['TR'] * 100:+.2f}%/yr TR")
    out["exact"] = ex

    # ---- 5. what binds ------------------------------------------------------------------------------
    L("\n5. WHAT BINDS AT 1.13 / 1.27 (W1 unless named)")
    for who, m, Bk in (("core", M_CORE, C), ("c4", M_C4, K)):
        L(f"  {who}: mean uncapped gross {gmean[who] * m:.3f} against its cap {Bk['cap']} (term (d) limit m {m_d[who]:.3f}); "
          f"held at cap {ex['approved 1.13 / 1.27']['held_at_cap'][who]:.1%} of sessions; Reg T 2.0x is never reached: the stress "
          f"cap {Bk['cap']} sits inside it")
    (Path(__file__).with_name(f"pm_q1_{STAMP}.json")).write_text(json.dumps(out, indent=1, default=lambda v: v.tolist() if hasattr(v, "tolist") else float(v)))
    L.write(Path(__file__).with_name(f"pm_q1_output_{STAMP}.txt"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
