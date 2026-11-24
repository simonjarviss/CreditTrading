"""Q2 of PM_TWO_ACCOUNTS.md: dynamic risk shifting between the two accounts. ZERO-TRIAL SCREEN.

    python3 results/cef/screens_2026-11-02/pm_q2_dynamic.py --scratch SCRATCH
        -> pm_q2_2026-11-02.json, pm_q2_output_2026-11-02.txt (this folder); a few minutes

Fit window only (asserted). It spends no trial, changes no spec, and is not a candidate for one
unless it clears its negative control by a wide margin AND its power at the CEF bar is adequate.

THE GRAVEYARD FIRST. "Sizing up on |z|" lowered Sharpe at every threshold (0.81 -> 0.40 -> 0.29 ->
0.27) and "sizing up on dislocation" gave -12.9% at 35.8% vol in 2008 (docs/RESEARCH_STATE.md,
CEF construction KILLED). Those scaled ONE book's total risk with its own opportunity. This is the
relative version: total ex-ante risk is held constant and only the split between the two accounts
moves, so a common stress that lifts both sleeves' opportunity moves nothing. It is close enough
to the dead mechanism that the prior is against it, and the screen says so up front.

THE RULE, DECLARED BEFORE ANY RESULT IN THIS FILE (no parameter is tuned on the outcome):
  O_k,t   each sleeve's opportunity, from the z the sleeve itself decides on, over the names its
          ADV floor admits: (A) mean |z|; (B) the cross-sectional sd of z (dispersion). Below
          min_names there is no reading.
  data<t  the reading used at decide date t is O_k,t-1, and it is normalised by its own mean over
          the 252 readings ending t-1 (at least 126): rel_k,t = O_k,t-1 / mean(O_k,t-252..t-1).
  split   C4's risk weight b4_t = rel_c4,t / (rel_core,t + rel_c4,t); the core's 1 - b4_t. Where
          either rel is undefined, b4_t = 1/2 (the static split).
  size    m_k,t = m_k x (b_k,t / 1/2) x sqrt(1/2) / sqrt(b_core,t^2 + b4_t^2): each account's
          approved multiplier (1.13 / 1.27) moved by its weight, rescaled so the ex-ante combined
          vol stays at the accepted 5.25% (rho = 0 declared; measured +0.011 on W1, pm_q1).
  hold    each account trades it through route B with a moving m (pm_common.band_dyn: band on
          held / m_t, the cap at cap / m_t), so a re-split trades only names that leave their band.
  cadence daily (primary) and monthly (b refreshed on each month's first session and held), the
          second a turnover control for H2.
Four screen variants (2 measures x 2 cadences); all are shown.

NEGATIVE CONTROL (H12). The same rule with the b4 series circularly shifted by 200 random offsets
of at least 252 sessions (it keeps b's distribution and persistence and breaks its timing), on the
house cap model (the exact build is too slow for 200 runs; the model is checked against it on the
real series). A real effect beats the placebo's 95th percentile.

POWER. If a later trial claimed this overlay, it would be judged on the active series (dynamic
minus static). P(pass) = inference.p_pass_dsr at the desk bar, N = 54 (sqrt(2 ln 54) = 2.824),
at the fit's own active Sharpe and at the top of its 95% interval, over 1, 3 and 9.5 years.
"""
from __future__ import annotations

import argparse
import json
from math import log, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

import pm_common as pc
from pm_common import FIT_END, W1_START, M_CORE, M_C4, assert_fit
from scripts.cef.spec import MIN_ADV_USD, MIN_NAMES
from scripts.research.inference import p_pass_dsr, newey_west_t

STAMP = "2026-11-02"
N_CEF = 54


def core_opp(C: dict) -> pd.DataFrame:
    z, adv = C["z"], C["adv"].reindex_like(C["z"])
    elig = z.notna() & (adv.fillna(-1.0) >= MIN_ADV_USD)          # build_targets' rule: a NaN ADV fails
    zz = z.where(elig)
    o = pd.DataFrame({"disp": zz.std(axis=1, ddof=1), "absz": zz.abs().mean(axis=1), "n": elig.sum(axis=1)})
    o.loc[o["n"] < MIN_NAMES, ["disp", "absz"]] = np.nan
    return o.reindex(C["T"].index)


def rel(o: pd.Series) -> pd.Series:
    x = o.shift(1)                                                 # data < t: the reading of t-1
    return x / x.rolling(252, min_periods=126).mean()              # its own trailing mean, also < t


def split(oc: pd.Series, o4: pd.Series, cadence: str) -> pd.Series:
    rc, r4 = rel(oc), rel(o4)
    b4 = (r4 / (rc + r4)).where(rc.notna() & r4.notna())
    if cadence == "monthly":
        first = ~b4.index.to_period("M").duplicated()
        b4 = b4.where(first).ffill()
    return b4.fillna(0.5)


def mults(b4: pd.Series) -> tuple[pd.Series, pd.Series]:
    bc = 1 - b4
    s = np.sqrt(0.5) / np.sqrt(bc ** 2 + b4 ** 2)
    return M_CORE * (bc / 0.5) * s, M_C4 * (b4 / 0.5) * s


def model_pnl(p: pd.Series, g: pd.Series, m: pd.Series, cap: float) -> pd.Series:
    G = g * m
    f = np.minimum(1.0, cap / G.where(G > 0, np.inf))
    return p * (m * f).shift(2).fillna(0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    a = ap.parse_args()
    L, out = pc.Log(), {}
    C, K = pc.core_book(a.scratch), pc.c4_book(a.scratch)
    O = {"core": core_opp(C), "c4": K["opp"].reindex(C["T"].index)}
    assert_fit(O["core"], O["c4"])
    for k in ("core", "c4"):
        o = O[k].loc[W1_START:]
        L(f"opportunity {k}: absz mean {o.absz.mean():.3f} (sd {o.absz.std():.3f}), disp mean {o.disp.mean():.3f}; "
          f"names eligible median {o.n.median():.0f}")
    for meas in ("absz", "disp"):
        cc = O["core"][meas].loc[W1_START:].corr(O["c4"][meas].loc[W1_START:])
        L(f"  corr of the two sleeves' {meas} on W1: {cc:+.3f}")
    G = {"core": C["H"].abs().sum(axis=1), "c4": K["H"].abs().sum(axis=1)}

    # the static book (approved), exact
    pc.check_band_dyn(K["T"], K["band"], K["cap"], M_C4)
    HS = {"core": pc.band_dyn(C["T"], C["band"], C["cap"], pd.Series(M_CORE, index=C["T"].index)),
          "c4": pc.band_dyn(K["T"], K["band"], K["cap"], pd.Series(M_C4, index=K["T"].index))}

    def book(H: dict, basis: str) -> tuple[pd.Series, pd.Series]:
        lc, lk = pc.line(H["core"], C[f"R_{basis}"]), pc.line(H["c4"], K[f"R_{basis}"])
        return 0.5 * lc["pnl"] + 0.5 * lk["pnl"], 0.5 * lc["turn"] + 0.5 * lk["turn"]

    stat = {b: book(HS, b) for b in ("pr", "tr")}
    rows, act = {}, {}

    def report(lab, pnl, turn, ref=None):
        g = pc.grid_row(pnl, turn)
        eras = {e: pc.sr(pnl.loc[s:t]) for e, s, t in pc.ERAS_W1}
        L(f"  {lab:34s} gross {g['ann'] * 100:5.2f}%/yr SR {g['sr']:.3f} vol {g['vol'] * 100:.2f}% maxDD {g['mdd'] * 100:.2f}% "
          f"turn {g['turn']:5.1f}/yr | net {g['net'][5] * 100:+.2f} / {g['net'][15] * 100:+.2f} / {g['net'][30] * 100:+.2f} %/yr "
          f"at 5/15/30bp | era SR {' / '.join(f'{v:.2f}' for v in eras.values())}"
          + (f" | turn vs static {g['turn'] / ref - 1:+.1%}" if ref else ""))
        return dict(g, eras=eras)

    L("\nEXACT BUILD, W1, combined $200k; price only (paper's P&L of record) first, total return beside")
    for basis in ("pr", "tr"):
        rows[f"static_{basis}"] = report(f"static 1.13 / 1.27 [{basis.upper()}]", *stat[basis])
    bser = {}
    for meas in ("absz", "disp"):
        for cad in ("daily", "monthly"):
            b4 = split(O["core"][meas], O["c4"][meas], cad)
            mc, m4 = mults(b4)
            bser[(meas, cad)] = b4
            H = {"core": pc.band_dyn(C["T"], C["band"], C["cap"], mc), "c4": pc.band_dyn(K["T"], K["band"], K["cap"], m4)}
            q = b4.loc[W1_START:]
            L(f"\n  {meas} / {cad}: C4 risk weight on W1 mean {q.mean():.3f}, p5 {q.quantile(0.05):.3f}, p95 {q.quantile(0.95):.3f}; "
              f"m core {mc.loc[W1_START:].min():.2f}..{mc.loc[W1_START:].max():.2f}, m C4 {m4.loc[W1_START:].min():.2f}..{m4.loc[W1_START:].max():.2f}")
            for basis in ("pr", "tr"):
                pnl, turn = book(H, basis)
                lab = f"{meas}/{cad} [{basis.upper()}]"
                rows[lab] = report(lab, pnl, turn, ref=rows[f"static_{basis}"]["turn"])
                d = (pnl - stat[basis][0]).loc[W1_START:]
                act[lab] = d
                ir = pc.sr(d) if d.std() > 0 else 0.0
                rows[lab]["active"] = dict(ann=pc.ann(d), ir=ir, nw_t=float(newey_west_t(d.values, lags=21)))
                L(f"  {'':34s} active (dynamic - static): {pc.ann(d) * 100:+.3f}%/yr, IR {ir:+.3f}, NW t {rows[lab]['active']['nw_t']:+.2f}")

    # ---- negative control on the house cap model -----------------------------------------------------
    L("\nNEGATIVE CONTROL: b4 circularly shifted by 200 random offsets (>= 252 sessions), house cap model, PR, W1")
    rng = np.random.default_rng(20261102)
    pr = {"core": C["pnl_pr"], "c4": K["pnl_pr"]}

    def model_comb(b4):
        mc, m4 = mults(b4)
        return (0.5 * model_pnl(pr["core"], G["core"], mc, C["cap"]) + 0.5 * model_pnl(pr["c4"], G["c4"], m4, K["cap"])).loc[W1_START:]

    base = model_comb(pd.Series(0.5, index=C["T"].index))
    plc = {}
    for (meas, cad), b4 in bser.items():
        real = pc.ann(model_comb(b4) - base)
        live = b4.loc[W1_START:].values
        draws = []
        for _ in range(200):
            k = int(rng.integers(252, len(live) - 252))
            sh = pd.Series(0.5, index=b4.index)
            sh.loc[W1_START:] = np.roll(live, k)
            draws.append(pc.ann(model_comb(sh) - base))
        draws = np.array(draws)
        plc[f"{meas}/{cad}"] = dict(real=real, p95=float(np.quantile(draws, 0.95)), p50=float(np.median(draws)),
                                    p05=float(np.quantile(draws, 0.05)), rank=float((draws < real).mean()))
        L(f"  {meas}/{cad}: model active {real * 100:+.3f}%/yr | placebo p5 / median / p95 {plc[f'{meas}/{cad}']['p05'] * 100:+.3f} / "
          f"{plc[f'{meas}/{cad}']['p50'] * 100:+.3f} / {plc[f'{meas}/{cad}']['p95'] * 100:+.3f} | real beats {plc[f'{meas}/{cad}']['rank']:.0%} of placebos")
    L("\nNEGATIVE CONTROL, EXACT BUILD (the same placebo, 100 offsets per variant, route B with a moving m), PR, W1")
    plc_x = {}
    rng2 = np.random.default_rng(20261103)
    for (meas, cad), b4 in bser.items():
        real = rows[f"{meas}/{cad} [PR]"]["active"]["ann"]
        live = b4.loc[W1_START:].values
        draws = []
        for _ in range(100):
            k = int(rng2.integers(252, len(live) - 252))
            sh = pd.Series(0.5, index=b4.index)
            sh.loc[W1_START:] = np.roll(live, k)
            mc, m4 = mults(sh)
            H = {"core": pc.band_dyn(C["T"], C["band"], C["cap"], mc), "c4": pc.band_dyn(K["T"], K["band"], K["cap"], m4)}
            draws.append(pc.ann((book(H, "pr")[0] - stat["pr"][0]).loc[W1_START:]))
        draws = np.array(draws)
        plc_x[f"{meas}/{cad}"] = dict(real=real, p95=float(np.quantile(draws, 0.95)), p50=float(np.median(draws)),
                                      p05=float(np.quantile(draws, 0.05)), rank=float((draws < real).mean()))
        v = plc_x[f"{meas}/{cad}"]
        L(f"  {meas}/{cad}: exact active {real * 100:+.3f}%/yr | placebo p5 / median / p95 {v['p05'] * 100:+.3f} / {v['p50'] * 100:+.3f} / "
          f"{v['p95'] * 100:+.3f} | real beats {v['rank']:.0%} of placebos")
    out["placebo_exact"] = plc_x
    exact_vs_model = {}
    for (meas, cad), b4 in bser.items():
        exact_vs_model[f"{meas}/{cad}"] = (rows[f"{meas}/{cad} [PR]"]["active"]["ann"], pc.ann(model_comb(b4) - base))
    L("  model vs exact active (PR, %/yr): " + "; ".join(f"{k} exact {v[0] * 100:+.3f} model {v[1] * 100:+.3f}" for k, v in exact_vs_model.items()))

    # ---- power ----------------------------------------------------------------------------------------
    bar = sqrt(2 * log(N_CEF))
    L(f"\nPOWER at the desk bar, N = {N_CEF} (sqrt(2 ln N) = {bar:.3f}), on the active series (PR):")
    pw = {}
    for lab, d in act.items():
        if not lab.endswith("[PR]"):
            continue
        ir = pc.sr(d)
        se = 1 / np.sqrt(len(d) / 252)
        hi = ir + 1.96 * se
        sk, ku = float(d.skew()), float(d.kurt() + 3)
        r = {}
        for yrs in (1, 3, 9.5):
            T = int(252 * yrs)
            r[yrs] = dict(at_fit=p_pass_dsr(max(ir, 0.0), T, N_CEF, bound="upper", skew=0.0, kurt=3.0),
                          at_ci_top=p_pass_dsr(max(hi, 0.0), T, N_CEF, bound="upper", skew=0.0, kurt=3.0))
        pw[lab] = dict(ir=ir, ci_top=hi, skew=sk, kurt=ku, p_pass=r)
        L(f"  {lab:24s} active IR {ir:+.3f} (95% top {hi:+.3f}; skew {sk:+.1f}, raw kurt {ku:.0f}) | P(pass) at the fit IR: "
          + ", ".join(f"{y}y {v['at_fit']:.3f}" for y, v in r.items()) + " | at the CI top: "
          + ", ".join(f"{y}y {v['at_ci_top']:.3f}" for y, v in r.items()))
    out.update(rows=rows, placebo=plc, power=pw, exact_vs_model=exact_vs_model)
    (Path(__file__).with_name(f"pm_q2_{STAMP}.json")).write_text(json.dumps(out, indent=1, default=float))
    L.write(Path(__file__).with_name(f"pm_q2_output_{STAMP}.txt"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
