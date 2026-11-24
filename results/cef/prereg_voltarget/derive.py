"""Where core x1.24 and C4 x1.41 come from, and whether they sit on a plateau (CEF trial 53, DRAFT).

    python3 results/cef/prereg_voltarget/derive.py --scratch SCRATCH
        -> derive_2026-10-30.json, derive_output_2026-10-30.txt (this folder)

ZERO TRIALS; fit window only (asserted). Reads the threshold declared before this ran
(declared_2026-10-30.json) and asserts it is older.

WHAT IT CHECKS, IN ORDER.
1. The 2026-10-28 declared rule (SCRATCH/alloc/declared_threshold.json, W6's form as written in
   results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md §2.6): sigma* = min(sigma_cap 20%, sigma_kill at
   p* 5%, sigma_margin, half-Kelly@15bp) on the combined two-sleeve book, rounded down to 0.25%.
   sigma_margin and the multipliers are RE-COMPUTED here from the series; sigma_kill and half-Kelly
   are read from that note's t9 table ([doc], its bootstrap is not re-run here).
2. The per-account conversion (the review's correction): two $100k accounts, so each account
   holds 2 x its sleeve's combined multiplier.
3. The same arithmetic on C4's SPEC book (cap 1.90), the book paper trades and H11 reads (team
   lead 2026-10-29), because the ruled 1.41 was computed on the trial's 1.80 book.
4. Each account's mean UNCAPPED gross at the ruled multipliers against its own cap: the 2026-10-29
   rule's term (d), which the 2026-10-28 rule did not have (it had one account and one cap).
5. The plateau: the two-account model at combined targets 2.00% .. 20.00%, gross Sharpe and gross
   return; the derived point is on a plateau if every point within +-0.50% has a Sharpe within
   0.05 of it. The argmax of each column is named and not chosen.

--remeasure (added 2026-11-02, results/cef/prereg_voltarget/FLATTEN_REMEASURE_2026-11-02.md). The
inputs are flatten_series.py's root, where the core is the LIVE thin-session rule (flatten).
Sections 1-2 (the 2026-10-28 rule on the trial book, asserted against its t8/t9 tables) and the
trial-book row of section 4 are not run: those tables were made on the hold book, and the trial-book
files are stand-ins there. Section 5's plateau is centred on the target that section 4 derives
(--remeasure), not on 5.75%. Section 6 holds C4 at --m-c4 and moves the core's multiplier,
which places the live pair. Outputs carry --stamp. Without the flag every line runs as before.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from _common import (FIT_END, HERE, NAV, W1_START, account, assert_fit, c4_spec_from, core_spec,
                     load, multipliers, stats)

STAMP = "2026-10-30"
RULED = {"core": 1.24, "c4": 1.41}          # team lead 2026-10-29/30, relayed in the drafting brief
S_RULED = 0.0575
GRID = np.round(np.arange(0.02, 0.20001, 0.0025), 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--remeasure", action="store_true", help="flatten inputs (module docstring)")
    ap.add_argument("--stamp", default=STAMP)
    ap.add_argument("--m-core", type=float, default=None, help="--remeasure: the live core multiplier")
    ap.add_argument("--m-c4", type=float, default=None, help="--remeasure: the live C4 multiplier")
    a = ap.parse_args()
    if a.remeasure and (a.m_core is None or a.m_c4 is None):
        raise SystemExit("--remeasure needs --m-core and --m-c4 (the live pair): inputs, never defaults")
    dec = json.loads((HERE / "declared_2026-10-30.json").read_text())
    if not datetime.fromisoformat(dec["declared_utc"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
        raise AssertionError("the declaration is not older than this run")
    D = load(a.scratch)
    out, say = {}, []

    def p(*x):
        s = " ".join(str(v) for v in x)
        print(s, flush=True)
        say.append(s)

    cap_core = float(core_spec.MAX_GROSS_STRESS)
    c4spec = c4_spec_from()
    cap_c4 = float(c4spec["frozen"]["max_gross_stress"])
    if float(c4spec["frozen"]["vol_target_annual"]) != float(core_spec.VOL_TARGET):
        raise ValueError("C4's spec vol target differs from the core's; the 6%-unit convention below assumes one")
    p(f"core spec {core_spec.SPEC_ID}: vol_target_annual {core_spec.VOL_TARGET}, max_gross_stress {cap_core}")
    p(f"C4 spec {c4spec['spec_id']} (c4-integrate): vol_target_annual {c4spec['frozen']['vol_target_annual']}, "
      f"max_gross_stress {cap_c4}")

    # ---- 1. the 2026-10-28 rule, re-computed where it can be ------------------------------------
    if a.remeasure:
        p("\n1-2. NOT RUN (--remeasure): the 2026-10-28 rule's t8/t9 and the trial book are the hold book's")
        sd = mA = None
    else:
        t8 = pd.read_csv(a.scratch / "alloc" / "tables" / "t8_vol_grid.csv")
        t9 = pd.read_csv(a.scratch / "alloc" / "tables" / "t9_sigma_star.csv")
        book2 = "2-sleeve core + C4, equal vol"
        t9r = t9[t9.book == book2].iloc[0]
        mC, mA, sd, sdc = multipliers(D["P_trial"], S_RULED)
        row = t8[(t8.book == book2) & np.isclose(t8.target_vol, S_RULED)].iloc[0]
        rep = abs(mC["core"] - row.m_core) + abs(mC["c4"] - row.m_c4)
        if rep > 1e-12:
            raise AssertionError(f"combined multipliers do not reproduce t8 at {S_RULED}: diff {rep}")
        m6, _, _, _ = multipliers(D["P_trial"], 0.06)
        g6 = (D["G_trial"]["core"] * m6["core"] + D["G_trial"]["c4"] * m6["c4"]).loc[W1_START:].mean()
        sig_margin = cap_core * 0.06 / g6
        if abs(sig_margin - t9r.sigma_margin) > 1e-12:
            raise AssertionError(f"sigma_margin {sig_margin} does not reproduce t9 {t9r.sigma_margin}")
        sig_star = np.floor(min(0.20, float(t9r.sigma_kill_p5), sig_margin, float(t9r.half_kelly_net15)) / 0.0025 + 1e-9) * 0.0025
        p("\n1. THE 2026-10-28 RULE (one account, one cap 1.80; equal standalone vol, b = 1/2, 1/2), W1",
          W1_START.date(), "->", FIT_END.date())
        p(f"   daily sd core {sd[0]:.6f}, C4 trial book {sd[1]:.6f}; sd of the unit-vol mix {sdc:.6f}")
        p(f"   sigma_cap 0.20 | sigma_kill(p*5%) {t9r.sigma_kill_p5} [doc t9; the grid stops at 20%] | "
          f"sigma_margin {sig_margin:.6f} [V: 1.80 x 0.06 / mean netted gross {g6:.4f} at 6%] | "
          f"half-Kelly@15 {t9r.half_kelly_net15:.4f} [doc t9]")
        p(f"   sigma* = {sig_star:.4f} (sigma_margin binds, rounded down to 0.25%)")
        p(f"   combined multipliers at {S_RULED}: core {mC['core']:.4f}, C4 {mC['c4']:.4f} (reproduce t8 to {rep:.1e})")
        p(f"   z_kill_worst (zero edge, one account) at {S_RULED}: {row.z_kill_worst:.4f}; at 20%: "
          f"{t8[(t8.book == book2) & np.isclose(t8.target_vol, 0.20)].z_kill_worst.iloc[0]:.4f} [doc t8]")
        out["rule_2026_10_28"] = dict(sigma_cap=0.20, sigma_kill_p5=float(t9r.sigma_kill_p5), sigma_margin=sig_margin,
                                      half_kelly_net15=float(t9r.half_kelly_net15), sigma_star=sig_star,
                                      m_combined=mC, sd_daily=dict(core=sd[0], c4_trial=sd[1]), sd_mix=sdc)

        # ---- 2. per account ------------------------------------------------------------------------
        p("\n2. PER ACCOUNT (two $100k accounts; m_account = m_combined x 200k/100k)")
        p(f"   trial-book series: core {mA['core']:.4f} -> written {np.floor(mA['core'] * 100) / 100:.2f}; "
          f"C4 {mA['c4']:.4f} -> written {np.floor(mA['c4'] * 100) / 100:.2f} (rounded DOWN); ruled {RULED}")
        out["per_account_trial_series"] = mA

    # ---- 3. on C4's spec book ------------------------------------------------------------------
    mCs, mAs, sds, sdcs = multipliers(D["PT"], S_RULED)
    mCs_p, mAs_p, _, _ = multipliers(D["PP"], S_RULED)
    p("\n3. THE SAME RULE ON C4's SPEC BOOK (cap 1.90), total return [price only beside]")
    p(f"   daily sd core {sds[0]:.6f}, C4 spec {sds[1]:.6f}" + ("" if sd is None else f" (trial {sd[1]:.6f})")
      + f"; mix sd {sdcs:.6f}")
    p(f"   per account at {S_RULED}: core {mAs['core']:.4f}, C4 {mAs['c4']:.4f}  "
      f"[price only: core {mAs_p['core']:.4f}, C4 {mAs_p['c4']:.4f}]")
    p(f"   written (2 dp, down): core {np.floor(mAs['core'] * 100) / 100:.2f}, C4 {np.floor(mAs['c4'] * 100) / 100:.2f}")
    out["per_account_spec_series"] = dict(TR=mAs, PR=mAs_p)

    # ---- 4. each account's own gross against its own cap ----------------------------------------
    p("\n4. EACH ACCOUNT'S MEAN UNCAPPED GROSS (W1) AT THE RULED MULTIPLIERS, against its own cap")
    gC, gT, gS = (D["G"]["core"].loc[W1_START:].mean(), D["G_trial"]["c4"].loc[W1_START:].mean(),
                  D["G"]["c4"].loc[W1_START:].mean())
    rows4 = {}
    ruled = RULED if not a.remeasure else {"core": a.m_core, "c4": a.m_c4}
    cases = [("core (cap 1.80)", gC, ruled["core"], cap_core),
             ("C4 trial book in its own account, cap 1.80", gT, ruled["c4"], cap_core),
             ("C4 spec book in its own account, cap 1.90", gS, ruled["c4"], cap_c4)]
    if a.remeasure:
        cases = [c for c in cases if "trial book" not in c[0]]
    for lab, g, m, cap in cases:
        rows4[lab] = dict(unit_mean_gross=g, at_m=g * m, cap=cap, over=bool(g * m > cap))
        p(f"   {lab}: unit book {g:.3f} x {m} = {g * m:.3f} against {cap} -> "
          f"{'ABOVE the cap (term d fails)' if g * m > cap else 'below'}")
    # the 2026-10-29 rule's term (d) alone, in closed form: m_a is linear in s
    _, mA1, _, _ = multipliers(D["PT"], 1.0)
    s_d = {"core": cap_core / (mA1["core"] * gC), "c4": cap_c4 / (mA1["c4"] * gS)}
    s_d_grid = np.floor(min(s_d.values()) / 0.0025 + 1e-9) * 0.0025
    _, mAd, _, _ = multipliers(D["PT"], s_d_grid)
    p(f"   term (d) per account, spec series: core passes to {s_d['core']:.4f}, C4 to {s_d['c4']:.4f} -> "
      f"grid {s_d_grid:.4f}, multipliers core {mAd['core']:.4f}, C4 {mAd['c4']:.4f}")
    p("   [doc SCRATCH/alloc4/tables/m_books.csv 'core + C4 only (2 accounts)', hold book: sigma* 0.0525, term_d, "
      "1.1357 / 1.2712]")
    p(f"   written (2 dp, down): core {np.floor(mAd['core'] * 100) / 100:.2f}, C4 {np.floor(mAd['c4'] * 100) / 100:.2f}")
    out["gross_vs_cap"] = rows4
    out["term_d_2026_10_29"] = dict(s_pass=s_d, sigma_grid=s_d_grid, m_account=mAd)

    # ---- 5. plateau -----------------------------------------------------------------------------
    p("\n5. PLATEAU: two accounts, own caps (core 1.80, C4 1.90), spec series, W1; combined = 1/2 + 1/2")
    rows = []
    for s in GRID:
        _, ma, _, _ = multipliers(D["PT"], s)
        r = dict(target=s, m_core=ma["core"], m_c4=ma["c4"])
        for basis, P in (("TR", D["PT"]), ("PR", D["PP"])):
            xa, fa, Ga, _ = account(P["core"], D["G"]["core"], ma["core"], cap_core)
            xb, fb, Gb, _ = account(P["c4"], D["G"]["c4"], ma["c4"], cap_c4)
            x = (0.5 * xa + 0.5 * xb).loc[W1_START:]
            assert_fit(x)
            st = stats(x)
            r.update({f"ann_{basis}": st["ann"], f"sr_{basis}": st["sr"], f"vol_{basis}": st["vol"]})
            if basis == "TR":
                r.update(binds_core=float((fa.loc[W1_START:] < 1).mean()), binds_c4=float((fb.loc[W1_START:] < 1).mean()),
                         gross_core=float(Ga.loc[W1_START:].mean()), gross_c4=float(Gb.loc[W1_START:].mean()))
        rows.append(r)
    T = pd.DataFrame(rows)
    T.to_csv(HERE / f"plateau_grid_{a.stamp}.csv", index=False)
    centre = s_d_grid if a.remeasure else S_RULED
    show = T[(T.target >= 0.04 - 1e-9) & (T.target <= 0.075 + 1e-9)]
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        p(show.round(4).to_string(index=False))
    at = T[np.isclose(T.target, centre)].iloc[0]
    near = T[(T.target >= centre - 0.005 - 1e-9) & (T.target <= centre + 0.005 + 1e-9)]
    plateau = bool((near.sr_TR - at.sr_TR).abs().max() <= 0.05 and (near.sr_PR - at.sr_PR).abs().max() <= 0.05)
    p(f"   within +-0.50% of {centre}: Sharpe TR {near.sr_TR.min():.3f}..{near.sr_TR.max():.3f}, "
      f"PR {near.sr_PR.min():.3f}..{near.sr_PR.max():.3f} (at the point {at.sr_TR:.3f} / {at.sr_PR:.3f}) -> plateau: {plateau}")
    aSR, aRet = T.loc[T.sr_TR.idxmax()], T.loc[T.ann_TR.idxmax()]
    p(f"   NOT CHOSEN: Sharpe argmax at {aSR.target:.4f} (SR {aSR.sr_TR:.3f}, {aSR.ann_TR * 100:.2f}%/yr); "
      f"return argmax at {aRet.target:.4f} ({aRet.ann_TR * 100:.2f}%/yr, SR {aRet.sr_TR:.3f}, "
      f"cap binds core {aRet.binds_core:.0%} / C4 {aRet.binds_c4:.0%})")
    # the reviewer's own (one-account, trial-series) grid beside, read not re-run
    if not a.remeasure:
        rv = t8[(t8.book == book2) & (t8.target_vol >= 0.04 - 1e-9) & (t8.target_vol <= 0.075 + 1e-9)]
        p("   [doc t8, one account, trial series] target / gross %/yr / SR / cap binds:")
        for _, q in rv.iterrows():
            p(f"     {q.target_vol:.4f}  {q.ann_gross_pct:6.2f}  {q.gross_sr:.3f}  {q.cap_binds_share:.2f}")
    out["plateau"] = dict(at=at.to_dict(), plateau=plateau, sr_TR_range=[float(near.sr_TR.min()), float(near.sr_TR.max())],
                          sr_PR_range=[float(near.sr_PR.min()), float(near.sr_PR.max())],
                          argmax_sr=aSR.to_dict(), argmax_return=aRet.to_dict())
    if a.remeasure:
        # ---- 6. the LIVE pair: C4 held at --m-c4, the core's multiplier moved ----------------------
        p(f"\n6. THE LIVE PAIR: C4 fixed at x{a.m_c4}, core multiplier moved; two accounts, W1, own caps")
        rows6 = []
        for mc in sorted(set(np.round(np.arange(0.50, 3.0001, 0.05), 2).tolist()) | {a.m_core}):
            r = dict(m_core=float(mc))
            for basis, P in (("TR", D["PT"]), ("PR", D["PP"])):
                xa, fa, Ga, _ = account(P["core"], D["G"]["core"], float(mc), cap_core)
                xb, _, _, _ = account(P["c4"], D["G"]["c4"], a.m_c4, cap_c4)
                x = (0.5 * xa + 0.5 * xb).loc[W1_START:]
                st = stats(x)
                r.update({f"ann_{basis}": st["ann"], f"sr_{basis}": st["sr"]})
                if basis == "TR":
                    r.update(core_binds=float((fa.loc[W1_START:] < 1).mean()), core_gross=float(Ga.loc[W1_START:].mean()),
                             core_vol=float(xa.loc[W1_START:].std() * np.sqrt(252)),
                             risk_share_core=float(np.var(0.5 * xa.loc[W1_START:]) / np.var(x)))
            rows6.append(r)
        T6 = pd.DataFrame(rows6)
        T6.to_csv(HERE / f"live_pair_grid_{a.stamp}.csv", index=False)
        live6 = T6[np.isclose(T6.m_core, a.m_core)].iloc[0]
        best = T6.loc[T6.sr_TR.idxmax()]
        on6 = bool(abs(live6.sr_TR - best.sr_TR) <= 0.05 and abs(live6.sr_PR - T6.sr_PR.max()) <= 0.05)
        with pd.option_context("display.width", 250, "display.max_columns", 30):
            p(T6[T6.m_core.isin([0.8, 1.0, 1.13, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5])].round(4).to_string(index=False))
        p(f"   live core x{a.m_core}: SR TR {live6.sr_TR:.3f} / PR {live6.sr_PR:.3f}, {live6.ann_TR * 100:.2f}%/yr; "
          f"the core's share of combined variance {live6.risk_share_core:.2f}. Max SR TR {best.sr_TR:.3f} at core "
          f"x{best.m_core}. Within 0.05 of the max: {on6}")
        out["live_pair"] = dict(at=live6.to_dict(), best_sr=best.to_dict(), on_plateau=on6)
    (HERE / f"derive_{a.stamp}.json").write_text(json.dumps(out, indent=1, default=float))
    (HERE / f"derive_output_{a.stamp}.txt").write_text("\n".join(say) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
