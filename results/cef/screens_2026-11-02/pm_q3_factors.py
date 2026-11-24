"""Q3 of PM_TWO_ACCOUNTS.md: does C4's factor exposure offset the core's, and is the core's NAV drag a
persistent factor tilt or noise? ZERO TRIALS.

    python3 results/cef/screens_2026-11-02/pm_q3_factors.py --scratch SCRATCH --factor-cache W4CACHE
        -> pm_q3_2026-11-02.json, pm_q3_output_2026-11-02.txt (this folder)

W4CACHE is the gitignored W4 cache (ff5_umd_daily.parquet, crsp_dsf_w4.parquet; CRSP is licensed:
read, never copied). Fit window only (asserted). Factors are scripts/cef/portfolio_baseline._factors'
own definitions: mktrf (equity), credit = HYG - IEF, rates = IEF - rf (term), muni = MUB - IEF,
loans = BKLN - rf. The regression is the framework's risk model (portfolio_baseline §4b): Dimson,
t and t-1, betas summed, HAC(5), gross, W1 2013-06-25..2022-12-30.

WHAT IT MEASURES.
1. Each account's summed factor betas (unit book, then x its approved multiplier), the combined
   book's, and whether C4's offset the core's: the factor variance of the combined book against the
   sum of the parts' (the cross term is the offset).
2. The core's ex-ante group tilt: the net weight it holds in each credit group (muni, multi, hy,
   loan) on the decided book, its mean, its sign persistence and its half-life. C4's net weight by
   family beside it.
3. The core's P&L split into a NAV component, sum_i H_{t-2,i} x r_nav_{i,t} (price-only NAV change,
   the same execution lag as evaluate()), and a discount component (the price-only P&L minus the NAV
   component), each split into muni names and the rest. The muni NAV component is split again into
   a PERSISTENT part (the window's mean net muni weight x the muni names' NAV return) and a
   TIME-VARYING part (the rest). The live 2026-09-15..10-30 attribution (another session, PR #26)
   is placed in the fit's distribution of 34-session sums of each component.
4. The most a factor hedge could buy: the in-sample Sharpe of each account and of the combined book
   with every summed beta hedged at its fit value (an upper bound: in-sample betas, no cost).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

import pm_common as pc
from pm_common import FIT_END, W1_START, M_CORE, M_C4, assert_fit
from scripts.research.inference import newey_west_t

STAMP = "2026-11-02"
FAC = ["mktrf", "credit", "rates", "muni", "loans"]
LIVE_SESSIONS = 34          # 2026-09-15..2026-10-30, NYSE sessions (12 in September, 22 in October)
LIVE = {"official": -982.0, "discount": 1583.0, "nav": -2251.0, "nav_muni": -1849.0, "fills": -309.0, "fees": -6.0}
LIVE_EQUITY = 100_000.0     # [U] the account's capital_usd; the attribution's own denominator is not restated here


def dimson(y: pd.Series, F: pd.DataFrame) -> dict:
    Xd = pd.concat([F, F.shift(1).add_suffix("_l1")], axis=1)
    d = pd.concat([y.rename("y"), Xd], axis=1).dropna()
    f = sm.OLS(d["y"], sm.add_constant(d.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    V = f.cov_params()
    b, t = {}, {}
    for k in F.columns:
        b[k] = float(f.params[k] + f.params[k + "_l1"])
        v = V.loc[k, k] + V.loc[k + "_l1", k + "_l1"] + 2 * V.loc[k, k + "_l1"]
        t[k] = b[k] / float(np.sqrt(v))
    return dict(beta=b, t=t, alpha_ann=float(f.params["const"] * 252), alpha_t=float(f.tvalues["const"]),
                r2=float(f.rsquared), n=int(len(d)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--factor-cache", type=Path, required=True)
    a = ap.parse_args()
    L, out = pc.Log(), {}
    C, K = pc.core_book(a.scratch), pc.c4_book(a.scratch)
    idx = C["T"].index
    F = pc.factors(a.factor_cache, idx)
    w1 = slice(W1_START, FIT_END)
    Fw = F.loc[w1]
    if Fw[FAC].isna().any().any():
        n = int(Fw[FAC].isna().any(axis=1).sum())
        L(f"  note: {n} W1 sessions lack a factor return (CRSP/French calendars); they are dropped from the regressions, not filled")

    # ---- 1. betas --------------------------------------------------------------------------------
    L("1. SUMMED FACTOR BETAS (Dimson t, t-1; HAC 5), unit books, W1, gross daily P&L")
    reg = {}
    for who, B in (("core", C), ("c4", K)):
        for basis in ("TR", "PR"):
            reg[(who, basis)] = dimson(B[f"pnl_{basis.lower()}"].loc[w1], Fw[FAC])
    for basis in ("PR", "TR"):
        for who in ("core", "c4"):
            r = reg[(who, basis)]
            L(f"  {who:4s} {basis}: " + "  ".join(f"{k} {r['beta'][k]:+.4f} (t {r['t'][k]:+.2f})" for k in FAC)
              + f" | R2 {r['r2']:.3f} | alpha {r['alpha_ann'] * 100:+.2f}%/yr t {r['alpha_t']:.2f}")
    Fx = Fw[FAC].dropna()
    Sf = Fx.cov().values * 252
    fv = {}
    for basis in ("PR", "TR"):
        bc = np.array([reg[("core", basis)]["beta"][k] for k in FAC]) * M_CORE
        b4 = np.array([reg[("c4", basis)]["beta"][k] for k in FAC]) * M_C4
        vc, v4 = 0.25 * bc @ Sf @ bc, 0.25 * b4 @ Sf @ b4
        cross = 2 * 0.25 * bc @ Sf @ b4
        bcomb = 0.5 * (bc + b4)
        tot_c = (C[f"pnl_{basis.lower()}"].loc[w1] * M_CORE).var() * 252
        tot_4 = (K[f"pnl_{basis.lower()}"].loc[w1] * M_C4).var() * 252
        fv[basis] = dict(beta_core_acct=dict(zip(FAC, bc)), beta_c4_acct=dict(zip(FAC, b4)), beta_comb=dict(zip(FAC, bcomb)),
                         fvar_core_part=float(vc), fvar_c4_part=float(v4), cross=float(cross),
                         offset_share=float(-cross / (vc + v4)) if vc + v4 > 0 else None,
                         factor_share_core_acct=float(4 * vc / tot_c), factor_share_c4_acct=float(4 * v4 / tot_4),
                         factor_vol_comb=float(np.sqrt(vc + v4 + cross)))
        same_sign = {k: bool(np.sign(bc[i]) == np.sign(b4[i])) for i, k in enumerate(FAC)}
        L(f"\n  {basis}, at the approved multipliers (core x{M_CORE}, C4 x{M_C4}), account betas:")
        L("    core " + "  ".join(f"{k} {v:+.4f}" for k, v in zip(FAC, bc)))
        L("    C4   " + "  ".join(f"{k} {v:+.4f}" for k, v in zip(FAC, b4)))
        L("    comb " + "  ".join(f"{k} {v:+.4f}" for k, v in zip(FAC, bcomb)) + "   (combined $200k = half of each)")
        L(f"    same sign: {same_sign}")
        L(f"    factor share of each account's variance: core {fv[basis]['factor_share_core_acct']:.1%}, C4 {fv[basis]['factor_share_c4_acct']:.1%}; "
          f"combined factor vol {fv[basis]['factor_vol_comb'] * 100:.2f}%/yr; cross term {cross * 1e4:+.3f} (x1e-4) = "
          f"{fv[basis]['offset_share'] * 100:+.1f}% of the parts' factor variance offset (positive = offset)")
    out["betas"] = {f"{w}_{b}": v for (w, b), v in reg.items()}
    out["factor_var"] = fv

    # ---- 2. ex-ante group tilts --------------------------------------------------------------------
    L("\n2. EX-ANTE NET WEIGHT BY GROUP, decided unit book H_t, W1 (a weight of +0.10 = long 10% of the account at x1.0)")
    grp = pd.read_csv(pc.REPO / "data" / "cef" / "cef_universe.csv").set_index("ticker")["grp"]
    Hc = C["H"].loc[w1]
    tilts = {}
    for g in sorted(set(grp.reindex(Hc.columns))):
        names = [t for t in Hc.columns if grp[t] == g]
        n = Hc[names].sum(axis=1)
        ac = float(n.autocorr(1))
        hl = float(np.log(0.5) / np.log(ac)) if 0 < ac < 1 else None
        tilts[g] = dict(names=names, mean=float(n.mean()), sd=float(n.std()), share_pos=float((n > 0).mean()),
                        mean_abs=float(n.abs().mean()), ar1=ac, half_life_sessions=hl,
                        mean_by_era={lab: float(n.loc[s:e].mean()) for lab, s, e in pc.ERAS_W1})
        L(f"  core {g:5s} {names}: mean {n.mean():+.3f} sd {n.std():.3f} | long on {tilts[g]['share_pos']:.0%} of sessions | "
          f"half-life {hl:.0f} sessions | era means " + " / ".join(f"{v:+.3f}" for v in tilts[g]["mean_by_era"].values()))
    fam = pd.read_csv(pc.REPO / "data" / "cef_families" / "universe.csv").set_index("ticker")["family"].reindex(K["H"].columns)
    Hk = K["H"].loc[w1]
    for g in sorted(fam.dropna().unique()):
        n = Hk[[t for t in Hk.columns if fam[t] == g]].sum(axis=1)
        tilts[f"c4_{g}"] = dict(mean=float(n.mean()), sd=float(n.std()), share_pos=float((n > 0).mean()))
        L(f"  C4   {g:20s}: mean {n.mean():+.3f} sd {n.std():.3f} | long on {(n > 0).mean():.0%} of sessions")
    out["tilts"] = tilts

    # ---- 3. NAV and discount components of the core's price-only P&L --------------------------------
    L("\n3. THE CORE'S PRICE-ONLY P&L SPLIT INTO NAV AND DISCOUNT COMPONENTS (unit book, W1, execution lag of evaluate())")
    nav = C["nav"].reindex(index=idx, columns=C["T"].columns)
    rnav = nav.pct_change(fill_method=None).where(lambda x: x.abs() < 0.5)
    Hl = C["H"].shift(2)
    held = Hl.fillna(0.0) != 0
    if (held & rnav.isna()).loc[w1].any().any():
        nmiss = int((held & rnav.isna()).loc[w1].sum().sum())
        L(f"  {nmiss} held name-sessions have no NAV return (NAV not published that day); their NAV component is 0 "
          f"and the whole price move falls in the discount component for that session (counted, not filled)")
    navc = (Hl * rnav).sum(axis=1, min_count=1).fillna(0.0)
    pr = C["pnl_pr"]
    disc = pr - navc
    muni = tilts["muni"]["names"]
    navm = (Hl[muni] * rnav[muni]).sum(axis=1, min_count=1).fillna(0.0)
    Nm = C["H"][muni].sum(axis=1).shift(2)
    rm = rnav[muni].mean(axis=1)                                   # the muni names' equal-weight NAV return
    Nbar = float(C["H"][muni].sum(axis=1).loc[w1].mean())
    pers = Nbar * rm
    comp = pd.DataFrame({"price-only P&L": pr, "NAV component": navc, "discount component": disc,
                         "NAV, muni names": navm, "NAV, other names": navc - navm,
                         "muni NAV: persistent tilt (mean net weight x muni NAV)": pers.fillna(0.0),
                         "muni NAV: time-varying": (navm - pers).fillna(0.0)}).loc[w1]
    assert_fit(comp)
    cs = {}
    for k, x in comp.items():
        cs[k] = dict(ann=pc.ann(x), vol=float(x.std() * np.sqrt(252)), nw_t=float(newey_west_t(x.values, lags=21)),
                     corr_pnl=float(x.corr(comp["price-only P&L"])))
        L(f"  {k:55s} {cs[k]['ann'] * 100:+6.2f}%/yr  vol {cs[k]['vol'] * 100:5.2f}%  NW t {cs[k]['nw_t']:+.2f}  corr with P&L {cs[k]['corr_pnl']:+.2f}")
    L(f"  corr(NAV component, discount component) daily {comp['NAV component'].corr(comp['discount component']):+.3f}; "
      f"on 21-session sums {comp['NAV component'].rolling(21).sum().iloc[::21].corr(comp['discount component'].rolling(21).sum().iloc[::21]):+.3f}")
    L(f"  mean net muni weight on W1 {Nbar:+.4f}; muni names' NAV return {pc.ann(rm.loc[w1]) * 100:+.2f}%/yr")
    rn = dimson(comp["NAV component"], Fw[FAC])
    rnm = dimson(comp["NAV, muni names"], Fw[FAC])
    L(f"  NAV component on the factors: R2 {rn['r2']:.3f}; muni beta {rn['beta']['muni']:+.4f} (t {rn['t']['muni']:+.2f}), rates "
      f"{rn['beta']['rates']:+.4f} (t {rn['t']['rates']:+.2f}); alpha {rn['alpha_ann'] * 100:+.2f}%/yr (t {rn['alpha_t']:+.2f})")
    L(f"  muni-names NAV component on the factors: R2 {rnm['r2']:.3f}; muni beta {rnm['beta']['muni']:+.4f} (t {rnm['t']['muni']:+.2f}); "
      f"rates {rnm['beta']['rates']:+.4f} (t {rnm['t']['rates']:+.2f})")
    # live window in the fit's 34-session distribution (unit book; the live window ran at x1.0, before trial 53)
    roll = comp.rolling(LIVE_SESSIONS).sum().dropna()
    live = {"NAV component": LIVE["nav"], "NAV, muni names": LIVE["nav_muni"], "discount component": LIVE["discount"],
            "price-only P&L": LIVE["official"]}
    pct = {}
    for k, v in live.items():
        x = v / LIVE_EQUITY
        pct[k] = dict(live=x, pctile=float((roll[k] <= x).mean()), sd=float(roll[k].std()), mean=float(roll[k].mean()), z=float((x - roll[k].mean()) / roll[k].std()))
        L(f"  live 09-15..10-30 {k:22s} {x * 100:+.2f}% of $100k [doc PR #26] | fit 34-session sums: mean {pct[k]['mean'] * 100:+.2f}%, "
          f"sd {pct[k]['sd'] * 100:.2f}% -> z {pct[k]['z']:+.2f}, percentile {pct[k]['pctile']:.1%}")
    # how much of a 34-session muni NAV component the persistent tilt explains
    rp = roll["muni NAV: persistent tilt (mean net weight x muni NAV)"]
    rv = roll["NAV, muni names"]
    share = float(1 - ((rv - rp).var() / rv.var()))
    L(f"  of the variance of 34-session muni NAV components on the fit, the persistent tilt explains {share:.1%}; "
      f"the rest is the time-varying tilt and name selection")
    out["components"] = cs
    out["nav_reg"] = dict(all=rn, muni=rnm)
    out["live_in_fit"] = pct
    out["persistent_share_34"] = share
    out["Nbar_muni"] = Nbar

    # ---- 4. the most a factor hedge could buy (in-sample upper bound) --------------------------------
    L("\n4. UPPER BOUND ON A FACTOR HEDGE: every summed beta hedged at its own in-sample fit value, no cost, W1")
    hv = {}
    for basis in ("PR", "TR"):
        xs = {}
        for who, B, m in (("core", C, M_CORE), ("c4", K, M_C4)):
            y = B[f"pnl_{basis.lower()}"].loc[w1] * m
            b = reg[(who, basis)]["beta"]
            hedge = sum(m * b[k] * (Fw[k].fillna(0.0) + Fw[k].shift(1).fillna(0.0)) / 2 for k in FAC)
            # Dimson betas are summed over t and t-1; the hedge holds half the summed beta in each leg (a static
            # approximation whose purpose is the variance bound, not a tradable rule)
            xs[who] = (y, y - hedge)
        comb0 = 0.5 * xs["core"][0] + 0.5 * xs["c4"][0]
        comb1 = 0.5 * xs["core"][1] + 0.5 * xs["c4"][1]
        hv[basis] = dict(core=(pc.sr(xs["core"][0]), pc.sr(xs["core"][1])), c4=(pc.sr(xs["c4"][0]), pc.sr(xs["c4"][1])),
                         comb=(pc.sr(comb0), pc.sr(comb1)), comb_vol=(float(comb0.std() * np.sqrt(252)), float(comb1.std() * np.sqrt(252))))
        L(f"  {basis}: Sharpe unhedged -> hedged: core {hv[basis]['core'][0]:.3f} -> {hv[basis]['core'][1]:.3f}; C4 "
          f"{hv[basis]['c4'][0]:.3f} -> {hv[basis]['c4'][1]:.3f}; combined {hv[basis]['comb'][0]:.3f} -> {hv[basis]['comb'][1]:.3f} "
          f"(vol {hv[basis]['comb_vol'][0] * 100:.2f}% -> {hv[basis]['comb_vol'][1] * 100:.2f}%)")
    out["hedge_bound"] = hv

    # ---- 5. what the fit book never held: the muni group, and thin sessions ----------------------------
    L("\n5. WHAT THE FIT BOOK NEVER HELD (the ADV floor, spec min_adv_usd, read through scripts/cef/spec.py)")
    from scripts.cef.spec import MIN_ADV_USD, MIN_NAMES
    z, adv = C["z"], C["adv"].reindex_like(C["z"])
    elig = (z.notna() & (adv.fillna(-1.0) >= MIN_ADV_USD)).loc[w1]
    by_year = elig[muni].groupby(elig.index.year).mean()
    thin = float((elig.sum(axis=1) < MIN_NAMES).mean())
    L(f"  share of W1 sessions on which each muni name clears the floor, by year: "
      + "; ".join(f"{y}: " + ", ".join(f"{t} {by_year.loc[y, t]:.0%}" for t in muni) for y in by_year.index))
    L(f"  sessions with fewer than min_names = {MIN_NAMES} eligible names (the harness HOLDS its last target; the live sleeve "
      f"flattens, docs/JOURNAL.md 2026-11-02): {thin:.1%} of W1")
    out["fit_never_held"] = dict(muni_eligible_by_year={int(y): {t: float(by_year.loc[y, t]) for t in muni} for y in by_year.index},
                                 thin_share_W1=thin)
    # the muni names' NAV risk, measured on the fit although the book did not hold them: the size of the bet
    # the live book now carries per unit of weight, and how much of it MUB hedges
    rm_w1 = rnav[muni].loc[w1].mean(axis=1)
    sig = float(rm_w1.std() * np.sqrt(252))
    hm = dimson(rm_w1, Fw[["muni", "rates"]])
    mub = (Fw["muni"] + Fw["rates"]).rename("MUB_minus_rf")       # MUB - rf = (MUB - IEF) + (IEF - rf)
    hb = dimson(rm_w1, mub.to_frame())
    L(f"  the two muni names' equal-weight NAV return on W1 (price-only NAV): vol {sig * 100:.2f}%/yr; on MUB - rf (Dimson): beta "
      f"{hb['beta']['MUB_minus_rf']:+.3f} (t {hb['t']['MUB_minus_rf']:+.1f}), R2 {hb['r2']:.3f}")
    for w in (0.10, 0.30):
        sd34 = w * sig * np.sqrt(LIVE_SESSIONS / 252)
        L(f"  a net muni weight of {w:.2f} of NAV carries a 34-session NAV-leg sd of {sd34 * 100:.2f}% of NAV unhedged, "
          f"{sd34 * np.sqrt(max(0.0, 1 - hb['r2'])) * 100:.2f}% after a MUB hedge at that beta (in-sample R2)")
    out["muni_nav_risk"] = dict(vol=sig, beta_mub=hb["beta"]["MUB_minus_rf"], r2_mub=hb["r2"], two_factor=hm)
    (Path(__file__).with_name(f"pm_q3_{STAMP}.json")).write_text(json.dumps(out, indent=1, default=float))
    L.write(Path(__file__).with_name(f"pm_q3_output_{STAMP}.txt"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
