"""The PM/risk seat's arithmetic for adding event sleeves beside the CEF book. ZERO TRIALS.

WHY THIS EXISTS
---------------
`results/events/ssx/ssx_pm/HOW_WE_ADD_IT_2026-10-19.md` answers eight design
questions (archetype gross efficiency, a shared hedge overlay, capacity, power,
two brokers, sequencing, counters, the dashboard). Every number in it is either
copied from a repo note (the DOC table below, each with its path), measured by
`ssx_pm_risk_inputs.py` from CRSP before 2023 (residual vol, betas, tails, ADV),
or computed here from those two. Nothing here reads a return of any event
strategy, so no counter moves.

THE ONE IDEA THE TABLES REST ON
-------------------------------
Under Reg T the book has two budgets, vol (sigma*) and gross (G_stress = 1.80).
At the corner where both bind (the CEF book alone at ~10% vol, framework §2.6),
a small sleeve e enters only if, per unit of its vol budget,

    IR_e > max(rho * IR_c, nu * r_g,c / sigma1_e)

which is two conditions at once (derivation in `entry_bar`):
  (A) return per unit of gross: IR_e * sigma1_e / nu > IR_c * sigma1_c = r_g,c
      (5.15%/yr gross, 3.47% net of 15bp, framework §0.1, §6.2);
  (B) diversification: IR_e > rho * IR_c.
(A) is invariant to how many events the sleeve holds: per unit of gross a sleeve
earns what its average position earns. So the per-event breakeven edge
mu* = r_g,c * (gross per unit long) * h / 252 does not depend on breadth.
(B) does: a sleeve's IR grows with the square root of its independent bets.

Reproduce:
    python3 scripts/events/ssx/ssx_pm_arithmetic.py
    python3 -m pytest scripts/events/ssx/ssx_pm_test_arithmetic.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "results" / "events" / "ssx" / "ssx_pm"
RISK = OUT / "risk_inputs_2026-10-19.json"
ETF = OUT / "etf_inputs_2026-10-19.json"
ADV_CSV = REPO / "results" / "events" / "ss_catalogue" / "crsp_pre_event_adv.csv"

FW = "results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md"
E1 = "results/events/E1_ETF_HEDGE_GATE_2026-10-15.md"
# Figures copied from repo notes. Each is [doc]; none is re-run here.
DOC = {
    "r_g_gross": (0.0515, FW + " §0.1/§6.2: return per unit gross, 2013-06..2022, gross of costs"),
    "r_g_net15": (0.0347, FW + " §6.2: the same, net of 15bp"),
    "sigma1_c": (0.0565, FW + " §6.2: CEF book vol per unit gross"),
    "ir_c_gross": (0.96, FW + " §6.1: gross Sharpe, live 2013-06..2022"),
    "ir_c_net15": (0.64, FW + " §6.1: net Sharpe at 15bp"),
    "g_stress": (1.80, "ops spec max_gross_stress (docs/SYSTEM.md §5, 2026-09-28)"),
    "rho_c4_21d": (0.145, FW + " §2.4: C4 vs book, 21-session sums"),
    "rho_c4_stress": (0.317, FW + " §2.4: C4 vs book, HY-stress blocks"),
    "e1_muni_mean_bp": (126.0, E1 + " §3: muni acquirer pair, mean, 92 deals / 47 groups"),
    "e1_muni_median_bp": (167.0, E1 + " §3: median"),
    "e1_muni_sd_bp": (336.0, E1 + " §3: sd across deals"),
    "e1_muni_hold": (168, E1 + " §2: muni median hold, sessions"),
    "e1_tax_sd_bp": (750.0, E1 + " §4: taxable pair sd"),
    "e1_tax_hold": (95, E1 + " §2"),
    "e1_eq_sd_bp": (617.0, E1 + " §4: equity pair sd"),
    "e1_eq_hold": (116, E1 + " §2"),
    "e1_muni_etf_resid_bp": (789.0, E1 + " §3: muni target, MUB-hedged residual over 168 sessions"),
    "e1_eq_spy_resid_bp": (829.0, E1 + " §4: equity CEF target, SPY-hedged residual over 116 sessions"),
    "cef_cross_share": (0.0057, "results/cef/EXEC_CAPACITY_OPEN_CROSS_2026-10-13.md §2: closing cross / day's volume"),
    "per_session_alpha_note": (None, "r_g_gross / 252"),
}
COSTS_BP = (5, 15, 30)
CORP = "results/events/SPECIAL_SITUATIONS_CATALOGUE_CORP_2026-10-15.md"
MA = "results/events/MERGER_ARB_AND_IBKR_2026-10-15.md"
CRED = "results/events/SPECIAL_SITUATIONS_CATALOGUE_CREDIT_2026-10-15.md"
# (family, events/yr, independent-unit proxy/yr, hold sessions as the catalogue states it, archetype, source).
# A hold given as a range in the source is taken at a stated point and labelled.
FAMILIES = (
    ("B1 spin-off removal close", 21.0, 9.0, 20, "(i)", CORP + " §3 B: 21.0/yr, 9.0 months/yr; hold 5-30 (20 taken)"),
    ("G3 forward split >= 2:1", 22.6, 9.7, 60, "(i)", CORP + " §3 G: 22.6/yr, 9.7 months/yr; hold 'months' (60 taken)"),
    ("E1c special dividend, common", 191.9, 144.6, 2, "(i)", CORP + " §3 E: 191.9/yr, 144.6 issuers/yr; hold 2"),
    ("D1 CEF rights offering", 6.7, 4.7, 15, "(iii)", CORP + " §3 D: 6.7/yr, 4.7 months/yr; 'subscription period' (15 taken)"),
    ("merger arb, all listed targets", 210.0, 12.0, 120, "(ii)/(i)", MA + " verdict 1: ~210-270/yr (210 taken); hold [U] (120 taken)"),
    ("E1 CEF merger pair, muni", 92 / 13, 47 / 13, 168, "(ii)", E1 + " §3: 92 deals, 47 groups, 2010-22 (13 yrs); hold 168"),
    ("macro event days (flag)", 31.5, 31.5, 1, "(iv)", CRED + " §0 item 5: median 31.5 distinct days/yr"),
)


def d(k):
    return DOC[k][0]


# ---------------------------------------------------------------- Q1

def entry_bar(ir_c: float, rho: float, nu: float, r_g_c: float, sigma1_e: float) -> float:
    """Smallest IR for a small sleeve e to raise return at the both-binding corner.

    Add delta of e's vol budget; cut the CEF budget by D. Vol (to first order at
    b_e = 0): dV = D + rho*delta <= 0. Gross: D/sigma1_c + nu*delta/sigma1_e <= 0.
    So D = -delta * max(rho, nu*sigma1_c/sigma1_e), and the return change is
    delta*IR_e + IR_c*D = delta*(IR_e - max(rho*IR_c, nu*IR_c*sigma1_c/sigma1_e)).
    IR_c*sigma1_c is the CEF book's return per unit gross; the MEASURED r_g,c is
    passed in rather than the product of two separately measured numbers (0.96 x
    5.65% = 5.42%, not the measured 5.15%), so the gross branch is nu*r_g_c/sigma1_e.
    Vol-only binding is the rho branch, gross-only the other; this nests both."""
    return max(rho * ir_c, nu * r_g_c / sigma1_e)


def mu_star_bp(r_g: float, gross_per_long: float, hold: int, cost_bp: float = 0.0) -> float:
    """Per-event edge (bp of the long notional, over the hold) that earns r_g per unit
    gross per year, plus a round trip on every leg: 2 * cost * gross_per_long."""
    return 1e4 * r_g * gross_per_long * hold / 252 + 2 * cost_bp * gross_per_long


def edge_per_gross_yr(mu_bp: float, gross_per_long: float, hold: int) -> float:
    return mu_bp / 1e4 * 252 / hold / gross_per_long


# ---------------------------------------------------------------- Q2

def e_abs_normal(mu: float, sd: float) -> float:
    """E|X| for X ~ N(mu, sd^2) (folded normal mean)."""
    if sd == 0:
        return abs(mu)
    z = mu / sd
    Phi_neg = 0.5 * (1 + math.erf(-z / math.sqrt(2)))      # P(Z < -mu/sd)
    return sd * math.sqrt(2 / math.pi) * math.exp(-0.5 * z * z) + mu * (1 - 2 * Phi_neg)


def overlay_ratio(n_long: int, n_short: int, m_over_s: float, rho: float) -> float:
    """E|sum of hedge demands| / sum of E|each demand|, one factor.

    Sleeve i's hedge demand (fraction of NAV in one factor ETF) is N(+m, s^2) for a
    long-biased sleeve and N(-m, s^2) for a short-biased one, pairwise correlation
    rho. Netting at book level hedges the sum once; per-sleeve hedging hedges each.
    The saving is 1 minus this ratio."""
    n = n_long + n_short
    per = n * e_abs_normal(m_over_s, 1.0)
    tot = e_abs_normal((n_long - n_short) * m_over_s, math.sqrt(n * (1 + (n - 1) * rho)))
    return tot / per


# ---------------------------------------------------------------- Q3

def lognormal_share(median: float, p25: float, x: float) -> float:
    """Share of events with ADV >= x under a lognormal fitted to (median, p25)."""
    s = (math.log(median) - math.log(p25)) / 0.6744897501960817
    z = (math.log(x) - math.log(median)) / s
    return 0.5 * (1 - math.erf(z / math.sqrt(2)))


# ---------------------------------------------------------------- Q4, Q7

def mde(sigma: float, n: int, z_a: float = 1.959963984540054, z_b: float = 0.8416212335729143) -> float:
    return (z_a + z_b) * sigma / math.sqrt(n)


def n_required(sigma: float, mu: float) -> float:
    return ((1.959963984540054 + 0.8416212335729143) * sigma / mu) ** 2


def slate_bar(n: int) -> float:
    return math.sqrt(2 * math.log(n))


def bonferroni_z(n: int, alpha: float = 0.05) -> float:
    from statistics import NormalDist
    return NormalDist().inv_cdf(1 - alpha / n)


# ---------------------------------------------------------------- Q5

def k_max(u: float, maint: float = 0.30) -> float:
    """Largest short book / account equity that survives a uniform rally u of the
    shorts with no offsetting long IN THE ACCOUNT (FINRA 4210(c)(3): 30% for >= $5):
    E - kEu >= maint*kE(1+u)  =>  k <= 1 / (maint + (1+maint)u)."""
    return 1.0 / (maint + (1 + maint) * u)


def x_max_single(u: float, k: float, maint: float = 0.30) -> float:
    """Largest single short (fraction of account equity) that survives its own rally u
    while the rest of a short book of k x equity is flat: x <= (1 - maint*k)/((1+maint)u)."""
    return (1 - maint * k) / ((1 + maint) * u)


def g_stress(w5: float, m: float = 0.5) -> float:
    """The frozen rule's form per unit NLV with no other margin: 1 / (m + w5)."""
    return 1.0 / (m + w5)


# ---------------------------------------------------------------- report

def main() -> int:
    risk = json.loads(RISK.read_text())
    etf = json.loads(ETF.read_text())
    S = risk["summary"]
    L, J = [], {}
    p = L.append

    p("== DOC inputs (copied, not re-run) ==")
    for k, (v, src) in DOC.items():
        if v is not None:
            p(f"  {k:<24} {v}   [{src}]")

    # ---------------- Q1
    p("\n== Q1a  per position: gross per unit of idio vol, sigma1, and the both-binding IR bar ==")
    p("  sleeve sigma1 = sigma_e / (gross per long) / sqrt(K_eff); bar = max(rho*IR_c, nu*r_g,c/sigma1_sleeve), nu = 1")
    arche = []
    for key, lab in (("stocks|small|IWM", "(i)/(iii) small cap, IWM hedge"), ("stocks|mid|SPY", "(i)/(iii) mid cap, SPY"),
                     ("stocks|large|SPY", "(i)/(iii) large cap, SPY"), ("stocks|micro|IWM", "(i)/(iii) micro cap, IWM"),
                     ("bdc|bdc|HYG", "(i)/(iii) BDC, HYG [survivors]"), ("bdc|bdc|SPY", "(i)/(iii) BDC, SPY [survivors]")):
        r = S[key]
        arche.append((lab, r["idio_vol_ann_5d_median"], 1 + abs(r["beta_median"]), r["idio_vol_ann_5d_p25"], r["idio_vol_ann_5d_p75"]))
    for lab, sd, hold, hr in (("(ii) E1 muni pair [doc]", d("e1_muni_sd_bp"), d("e1_muni_hold"), 1.0),
                              ("(ii) taxable CEF pair [doc]", d("e1_tax_sd_bp"), d("e1_tax_hold"), 1.0),
                              ("(ii) equity CEF pair [doc]", d("e1_eq_sd_bp"), d("e1_eq_hold"), 1.0)):
        arche.append((lab, sd / 1e4 * math.sqrt(252 / hold), 1 + hr, None, None))
    p("  the per-position IR bar (A) is r_g,c / sigma1_pos; a sleeve of K independent positions has IR and bar both")
    p("  x sqrt(K), so (A) does not depend on K. (B), today's regime (vol binds, gross slack on average), is rho * IR_c.")
    p(f"  {'archetype':<34}{'sigma_e':>8}{'p25-p75':>12}{'gross/long':>11}{'gross/vol':>10}{'s1 K=1':>8}{'K=4':>7}{'K=16':>7}"
      f"{'(A) gross':>10}{'(A) net15':>10}")
    J["q1_positions"] = []
    for lab, se, g, lo, hi in arche:
        s1 = [se / g / math.sqrt(k) for k in (1, 4, 16)]
        bar_g = entry_bar(d("ir_c_gross"), 0.0, 1.0, d("r_g_gross"), s1[0])
        bar_n = entry_bar(d("ir_c_net15"), 0.0, 1.0, d("r_g_net15"), s1[0])
        rng = f"{lo:.2f}-{hi:.2f}" if lo is not None else "-"
        p(f"  {lab:<34}{se:>8.3f}{rng:>12}{g:>11.2f}{g/se:>10.1f}{s1[0]:>8.3f}{s1[1]:>7.3f}{s1[2]:>7.3f}"
          f"{bar_g:>10.2f}{bar_n:>10.2f}")
        J["q1_positions"].append({"archetype": lab, "sigma_e": se, "gross_per_long": g, "sigma1": s1,
                                  "bar_A_gross": bar_g, "bar_A_net15": bar_n, "sigma_e_p25": lo, "sigma_e_p75": hi})
    p("  (B) bars, today's regime: " + ", ".join(
        f"rho {r}: {r*d('ir_c_gross'):.2f} gross / {r*d('ir_c_net15'):.2f} net15" for r in (0.0, d("rho_c4_21d"), d("rho_c4_stress"))))
    p(f"  CEF book: gross/vol {1/d('sigma1_c'):.1f}, sigma1 {d('sigma1_c'):.4f}")

    p("\n== Q1b  per-event breakeven edge mu* (bp of the long leg, over the hold): earns the CEF book's return per unit gross ==")
    p("  gross basis uses r_g 5.15%; net columns use r_g 3.47% plus a round trip 2*c*(gross per long) at c = 5/15/30bp")
    J["q1_mu_star"] = []
    p(f"  {'gross per long':>15}{'hold':>6}{'gross':>8}{'net@5':>8}{'net@15':>8}{'net@30':>8}")
    for g in (1.0, 1.5, 2.0, 2.2):
        for h in (1, 5, 20, 60, 168):
            row = [mu_star_bp(d("r_g_gross"), g, h)] + [mu_star_bp(d("r_g_net15"), g, h, c) for c in COSTS_BP]
            p(f"  {g:>15.1f}{h:>6}" + "".join(f"{x:>8.0f}" for x in row))
            J["q1_mu_star"].append({"gross_per_long": g, "hold": h, "gross": row[0], "net5": row[1], "net15": row[2], "net30": row[3]})
    e1 = edge_per_gross_yr(d("e1_muni_mean_bp"), 2.0, d("e1_muni_hold"))
    e1m = edge_per_gross_yr(d("e1_muni_median_bp"), 2.0, d("e1_muni_hold"))
    p(f"  E1 muni pair, gross, per unit gross per year: mean {e1:.4f}, median {e1m:.4f}  vs CEF {d('r_g_gross')}  "
      f"(ratio {d('r_g_gross')/e1:.1f}x / {d('r_g_gross')/e1m:.1f}x)")
    J["q1_e1"] = {"mean": e1, "median": e1m}

    p("\n== Q1d  (iii) short event + ETF long: borrow added to mu* (bp of the short leg) and the IR drag fee/sigma_e ==")
    J["q1_borrow"] = []
    for fee in (0.005, 0.05, 0.20):
        adds = [1e4 * fee * h / 252 for h in (5, 20, 60)]
        drag = fee / S["stocks|small|IWM"]["idio_vol_ann_5d_median"]
        p(f"  fee {fee:>5.1%}/yr: +{adds[0]:.0f} / +{adds[1]:.0f} / +{adds[2]:.0f}bp at 5 / 20 / 60 sessions; "
          f"IR drag on a median small cap {drag:.2f}")
        J["q1_borrow"].append({"fee": fee, "add_bp_5_20_60": adds, "ir_drag_small": drag})

    p("\n== Q1c  (iv) subtract-only flags ==")
    a = d("r_g_gross") / 252 * 1e4
    p(f"  forgone CEF alpha per flagged session per unit gross held: {a:.2f}bp gross ({d('r_g_net15')/252*1e4:.2f}bp net@15)")
    for c in COSTS_BP:
        p(f"  a flag that forces an exit and re-entry pays 2c = {2*c}bp per unit gross: needs avoided loss > {2*c + a:.1f}bp for a 1-session flag at {c}bp")
    J["q1_flag_bp_per_session"] = a

    # ---------------- Q2
    p("\n== Q2  shared hedge overlay: E|net hedge| / sum E|per-sleeve hedge|  (saving = 1 - ratio) ==")
    J["q2"] = []
    p(f"  {'N':>3}{'longs':>6}{'shorts':>7}{'m/s':>5}" + "".join(f"{'rho '+str(r):>9}" for r in (0.0, 0.2, 0.5)))
    for n_l, n_s in ((2, 0), (4, 0), (8, 0), (2, 2), (4, 4), (6, 2), (12, 0), (6, 6)):
        for ms in (0.0, 1.0, 2.0):
            if ms == 0.0 and n_s:
                continue
            rr = [overlay_ratio(n_l, n_s, ms, r) for r in (0.0, 0.2, 0.5)]
            p(f"  {n_l+n_s:>3}{n_l:>6}{n_s:>7}{ms:>5.1f}" + "".join(f"{x:>9.3f}" for x in rr))
            J["q2"].append({"n_long": n_l, "n_short": n_s, "m_over_s": ms, "ratio": rr})
    p("  m/s = 0: demands with no fixed sign (closed form sqrt((1+(N-1)rho)/N)); m/s = 2: every long-biased sleeve's hedge is nearly always short")
    for sav in (0.0, 0.25, 0.5):
        g = 1 + (1 - sav) * 1.01
        p(f"  small-cap (i) with hedge saving {sav:.0%}: gross per long {g:.2f}, sigma1 K=1 {S['stocks|small|IWM']['idio_vol_ann_5d_median']/g:.3f}, "
          f"round trip at 15bp {2*15*g:.0f}bp, mu* 20-session net@15 {mu_star_bp(d('r_g_net15'), g, 20, 15):.0f}bp")

    # ---------------- Q3
    p("\n== Q3  capacity: share of 2018-22 events whose pre-event ADV >= book size (5% of book per name, 5% of ADV) ==")
    adv = pd.read_csv(ADV_CSV)
    J["q3"] = []
    p(f"  {'family':<46}{'n':>5}{'$0.1m':>7}{'$1m':>7}{'$10m':>7}{'$100m*':>8}{'fit err':>9}")
    for _, r in adv.iterrows():
        if r["n_events_with_adv"] < 9:
            continue
        fit = [lognormal_share(r["median_adv_usd"], r["p25_adv_usd"], x) for x in (1e5, 1e6, 1e7)]
        err = max(abs(f - m) for f, m in zip(fit, (r["share_adv_ge_100k"], r["share_adv_ge_1m"], r["share_adv_ge_10m"])))
        s100 = lognormal_share(r["median_adv_usd"], r["p25_adv_usd"], 1e8)
        lab = f"{r['cls']}/{r['sub']}"
        p(f"  {lab:<46}{int(r['n_events_with_adv']):>5}{r['share_adv_ge_100k']:>7.2f}{r['share_adv_ge_1m']:>7.2f}"
          f"{r['share_adv_ge_10m']:>7.2f}{s100:>8.2f}{err:>9.3f}")
        J["q3"].append({"family": lab, "n": int(r["n_events_with_adv"]), "s100m_lognormal": s100, "fit_err": err})
    p("  * $100m is a lognormal extrapolation from (median, p25); 'fit err' is its worst miss on the three measured columns")
    us = risk["adv_shares_median"]
    p(f"  all price>=$5 common stocks at year-end 2009-21 (median of 13 snapshots, measured): " +
      ", ".join(f"{k} {v:.3f}" for k, v in us.items()))
    p("  hedge ETFs: notional one session can absorb at 5% of 2022 ADV (measured, CRSP)")
    for t, v in etf.items():
        a22 = v["adv_usd"].get("2022")
        p(f"    {t:<5} ADV 2022 ${a22/1e6:,.0f}m -> ${0.05*a22/1e6:,.1f}m per session")
    J["q3_etf_5pct_2022"] = {t: 0.05 * v["adv_usd"]["2022"] for t, v in etf.items()}
    p(f"  MOC caveat: the cross is {d('cef_cross_share'):.2%} of a CEF's day [doc]; at P_max 10% of the cross a position is "
      f"{0.10*d('cef_cross_share'):.3%} of ADV, {0.05/(0.10*d('cef_cross_share')):.0f}x below the 5%-of-ADV rule")

    # ---------------- Q4
    p("\n== Q4  minimum detectable mean edge, MDE = 2.80 * sigma / sqrt(N), two-sided 5%, 80% power ==")
    sig = []
    for key, lab in (("stocks|small|IWM", "small cap, IWM-hedged"), ("stocks|mid|SPY", "mid cap, SPY-hedged"),
                     ("stocks|large|SPY", "large cap, SPY-hedged"), ("stocks|micro|IWM", "micro cap, IWM-hedged"),
                     ("bdc|bdc|HYG", "BDC, HYG-hedged [survivors]")):
        for h in (1, 3, 5, 20, 60):
            H = S[key]["holds"][str(h)]
            sig.append((f"{lab}, {h}d (raw sd)", H["sd_e"], "measured"))
            sig.append((f"{lab}, {h}d (robust sd)", H["robust_sd_e"], "measured"))
    for lab, k in (("E1 muni pair, 168d", "e1_muni_sd_bp"), ("taxable CEF pair, 95d", "e1_tax_sd_bp"),
                   ("equity CEF pair, 116d", "e1_eq_sd_bp"), ("muni CEF target MUB-hedged, 168d", "e1_muni_etf_resid_bp"),
                   ("equity CEF target SPY-hedged, 116d", "e1_eq_spy_resid_bp")):
        sig.append((lab, d(k) / 1e4, "doc"))
    p(f"  {'sigma source':<48}{'sigma bp':>9}" + "".join(f"{'N='+str(n):>8}" for n in (50, 100, 250, 500)))
    J["q4"] = []
    for lab, s, src in sig:
        m = [mde(s, n) * 1e4 for n in (50, 100, 250, 500)]
        p(f"  {lab:<48}{s*1e4:>9.0f}" + "".join(f"{x:>8.0f}" for x in m) + f"   [{src}]")
        J["q4"].append({"source": lab, "sigma_bp": s * 1e4, "mde_bp": m, "kind": src})
    p("  N required for a stated effect (literature or doc), N = 7.85*(sigma/mu)^2:")
    for lab, s, mu in (("lock-up -1.5% over 3d [S], small cap 3d raw sd", S["stocks|small|IWM"]["holds"]["3"]["sd_e"], 0.015),
                       ("lock-up, small cap 3d robust sd", S["stocks|small|IWM"]["holds"]["3"]["robust_sd_e"], 0.015),
                       ("SEO 2.5% recovery over ~5d [V abstract], mid cap 5d raw sd", S["stocks|mid|SPY"]["holds"]["5"]["sd_e"], 0.025),
                       ("spin-off >2% over 30d [S], mid cap 20d raw sd", S["stocks|mid|SPY"]["holds"]["20"]["sd_e"], 0.02),
                       ("E1 muni mean 126bp, sd 336bp [doc]", 0.0336, 0.0126),
                       ("E1 muni median 167bp, sd 336bp [doc]", 0.0336, 0.0167)):
        p(f"    {lab:<62} N = {n_required(s, mu):,.0f}")

    p("\n== Q4b  N needed to detect the BREAKEVEN edge mu* itself (net@15, gross per long 2.0): 7.85*(sigma_h/mu*)^2 ==")
    J["q4b"] = []
    for key, lab in (("stocks|small|IWM", "small cap"), ("stocks|mid|SPY", "mid cap"), ("stocks|large|SPY", "large cap"),
                     ("bdc|bdc|HYG", "BDC [survivors]")):
        row = []
        for h in (1, 5, 20, 60):
            H = S[key]["holds"][str(h)]
            ms = mu_star_bp(d("r_g_net15"), 2.0, h, 15) / 1e4
            row.append((h, ms, n_required(H["sd_e"], ms), n_required(H["robust_sd_e"], ms)))
        p(f"  {lab:<16}" + "  ".join(f"{h}d mu* {ms*1e4:.0f}bp: N {a:,.0f} (robust {b:,.0f})" for h, ms, a, b in row))
        J["q4b"].append({"sample": lab, "rows": row})
    ms = mu_star_bp(d("r_g_net15"), 2.0, d("e1_muni_hold"), 15) / 1e4
    p(f"  E1 muni pair: mu* {ms*1e4:.0f}bp vs mean {d('e1_muni_mean_bp'):.0f}bp; N to detect mu* {n_required(d('e1_muni_sd_bp')/1e4, ms):.1f}")

    p("\n== Q4c  families: years to the D7 floor (250 independent), live positions K = n*h/252, and the edge that adds 1%/yr of NAV at 5% per event ==")
    J["q4c"] = []
    p(f"  {'family':<34}{'arch':>9}{'n/yr':>7}{'indep/yr':>9}{'yrs to 250':>11}{'(indep)':>8}{'hold':>6}{'K live':>8}{'gross@5%':>9}{'mu for 1%':>10}")
    for lab, n, ind, h, arch, src in FAMILIES:
        gpl = 2.0 if arch.startswith("(i") or arch.startswith("(ii") else 0.0
        K = n * h / 252
        p(f"  {lab:<34}{arch:>9}{n:>7.1f}{ind:>9.1f}{250/n:>11.1f}{250/ind:>8.1f}{h:>6}{K:>8.1f}{K*0.05*gpl:>9.2f}"
          f"{1e4*0.01/(n*0.05):>9.0f}bp")
        J["q4c"].append({"family": lab, "n": n, "indep": ind, "years_250": 250 / n, "years_250_indep": 250 / ind,
                         "hold": h, "K_live": K, "gross_at_5pct": K * 0.05 * gpl, "mu_for_1pct_bp": 1e4 * 0.01 / (n * 0.05), "src": src})
    p("  gross@5% assumes 2.0 gross per long (a hedged long or a pair); the flag row uses none")

    # ---------------- Q7
    p("\n== Q7  slate bar sqrt(2 ln N) against single-test 1.96 and one-sided Bonferroni z(1-0.05/N) ==")
    J["q7"] = {}
    for n in (4, 6, 7, 8, 10, 12, 16, 20, 52):
        p(f"  N={n:>3}  bar {slate_bar(n):.3f}   Bonferroni {bonferroni_z(n):.3f}")
        J["q7"][n] = slate_bar(n)

    # ---------------- Q5
    p("\n== Q5  two brokers: a short book with its hedge at the OTHER broker ==")
    p("  k_max = short MV / account equity that survives a uniform rally u (FINRA 4210(c)(3), 30%): 1/(0.30 + 1.30u)")
    rallies = [("SPY 5d p99.9 (2008-22)", etf["SPY"]["r5_p99.9"]), ("IWM 5d p99.9", etf["IWM"]["r5_p99.9"]),
               ("IWM 5d max (2008-11)", etf["IWM"]["r5_max"]),
               ("large-cap single name 5d p99.9", S["stocks|large|SPY"]["holds"]["5"]["tail_raw"]["p99.9"]),
               ("mid-cap single name 5d p99.9", S["stocks|mid|SPY"]["holds"]["5"]["tail_raw"]["p99.9"]),
               ("small-cap single name 5d p99.9", S["stocks|small|IWM"]["holds"]["5"]["tail_raw"]["p99.9"]),
               ("micro-cap single name 5d p99.9", S["stocks|micro|IWM"]["holds"]["5"]["tail_raw"]["p99.9"]),
               ("BDC single name 5d p99.9 [survivors]", S["bdc|bdc|HYG"]["holds"]["5"]["tail_raw"]["p99.9"])]
    J["q5"] = []
    p("  x_max = largest single short (x equity) surviving its own rally while the rest of a k x equity short book is flat, capped at k")
    p(f"  {'rally u':<40}{'u':>7}{'k_max':>7}{'x k=1.0':>9}{'x k=1.5':>9}{'x k=2.0':>9}{'G=1/(0.5+u)':>12}")
    for lab, u in rallies:
        xs = [min(k, x_max_single(u, k)) for k in (1.0, 1.5, 2.0)]
        p(f"  {lab:<40}{u:>7.3f}{k_max(u):>7.2f}" + "".join(f"{x:>9.2f}" for x in xs) + f"{g_stress(u):>12.2f}")
        J["q5"].append({"rally": lab, "u": u, "k_max": k_max(u), "x_max_k1_15_2": xs, "g_split": g_stress(u)})
    for key, lab in (("stocks|small|IWM", "small-cap pair in one account, 5d residual p99.9 / 2"),
                     ("stocks|mid|SPY", "mid-cap pair in one account")):
        w5 = S[key]["holds"]["5"]["tail_e"]["p99.9"] / 2
        p(f"  {lab:<56} w5 {w5:.3f} -> G {g_stress(w5):.2f}")
    p(f"  CEF book's own G_stress {d('g_stress')} implies m + w5 = {1/d('g_stress'):.3f} at m = 0.5")

    (OUT / "arithmetic_2026-10-19.txt").write_text("\n".join(L) + "\n")
    (OUT / "arithmetic_2026-10-19.json").write_text(json.dumps(J, indent=1, default=float))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
