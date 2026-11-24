"""Design inputs for PREREG_C4_LEVEL (CEF trial 54 if approved). Zero trials, fit window only.

WHAT THIS COMPUTES, AND WHAT IT REFUSES TO
------------------------------------------
Two things the pre-registration must state before the trial runs:

  A. THE RISK SPLIT and its plateau. The split a is derived from the two-sleeve
     mean-variance rule on the inputs the screen already measured and saw
     (alpha_level_checks.py K4: the C4 z book and the level book's daily P&L on
     the fit). The plateau is the equal-weight-of-risk blend's Sharpe across
     a = 0.30 .. 0.70, from those SAME already-seen series. Nothing new is scored.

  B. THE SHARED CAP. How the blended target sits under C4's frozen 1.90 gross
     cap at the account multiplier 1.27 (spec c4_families.v3.20261102 on branch
     c4-rel). Gross, cap-binding share and turnover are construction properties
     of a weight path, not performance, and are computed for the z-only spec
     book and the blend through the canonical band and cap
     (`band_frontier.band_gross_capped`). NO P&L OF THE BLENDED BOOK IS
     COMPUTED: that is the trial's first stage, and computing it here would
     judge the trial on a number seen before its approval.

THE BLEND (as the pre-registration's section 1 specifies it)
------------------------------------------------------------
  w_z  = C4's unit z target, normalised to unit gross (from `bf.build_targets`)
  w_L  = the within-family level book, -(disc - family mean disc), unit gross
  s_k  = trailing realised vol of the unit-gross book k: current weights on the
         last VOL_LOOKBACK (63) sessions of PRICE returns through t, exactly the
         estimator `build_targets` uses for its vol scalar (H7: data through t)
  mix  = a * w_z / s_z + (1 - a) * w_L / s_L, renormalised to unit gross
  T_B  = mix * clip(VOL_TARGET / s_mix, 0.2, 2.5)  -- the sleeve's own scalar, once
Then the account holds m x band_gross_capped(T_B, BAND_WIDTH, cap / m), as the
sizing-multiplier implementation does for the z book today.

Run (from the worktree root):  python3 -B results/cef/screens_2026-11-02/prereg_c4_level_design.py
Writes prereg_c4_level_design_output.txt beside itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alpha_common as ac  # noqa: E402
from alpha_level_checks import level_weights, score  # noqa: E402
from scripts.cef import band_frontier as bf  # noqa: E402
from scripts.cef import c4_families as c4  # noqa: E402
from scripts.cef.spec import BAND_WIDTH, VOL_TARGET  # noqa: E402

# C4's cap and multiplier come from C4's FROZEN SPEC at a named git ref, never a literal (CLAUDE.md: the spec
# is the only authority). This worktree predates C4's spec on main, so the file is read with `git show <ref>:...`.
# Default: the release tag that carries c4_families.v4.20261102 (x1.26, cap 1.90). The first run (2026-11-02,
# prereg_c4_level_design_output.txt) used c4-rel 8b14298, c4_families.v3.20261102 (x1.27).
DEFAULT_SPEC_REF = "release-20261103-1"


def c4_spec(ref: str) -> tuple[str, float, float]:
    """(spec_id, max_gross_stress, sizing_multiplier) of ops/specs/c4_families.frozen.json at `ref`."""
    import json
    import subprocess
    txt = subprocess.run(["git", "-C", str(ac.WT), "show", f"{ref}:ops/specs/c4_families.frozen.json"],
                         check=True, capture_output=True, text=True).stdout
    d = json.loads(txt)
    f = d["frozen"]
    for k in ("max_gross_stress", "sizing_multiplier"):
        if k not in f:
            raise KeyError(f"C4 spec at {ref} has no frozen.{k}")
    return d["spec_id"], float(f["max_gross_stress"]), float(f["sizing_multiplier"])
VOL_LOOKBACK = bf.VOL_LOOKBACK
A_GRID = (0.30, 0.40, 0.50, 0.60, 0.70)


def trailing_vol(w: pd.DataFrame, r: pd.DataFrame) -> pd.Series:
    """sd of (w_t . r_s) for s in the last VOL_LOOKBACK sessions through t, annualised.
    The same estimator as build_targets (current weights on past returns, through t)."""
    W, Rv = w.to_numpy(), r.fillna(0.0).to_numpy()
    out = np.full(len(w), np.nan)
    for i in range(len(w)):
        if not np.any(W[i]):
            continue
        lo = max(0, i - VOL_LOOKBACK + 1)
        h = Rv[lo:i + 1] @ W[i]
        if len(h) > 1:
            out[i] = h.std(ddof=1) * np.sqrt(252)
    return pd.Series(out, index=w.index)


def unit(w: pd.DataFrame) -> pd.DataFrame:
    g = w.abs().sum(axis=1)
    return w.div(g.where(g > 0), axis=0).fillna(0.0)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-ref", default=DEFAULT_SPEC_REF, help="git ref whose C4 frozen spec sets the cap and multiplier")
    a = ap.parse_args(argv)
    spec_id, C4_CAP, C4_M = c4_spec(a.spec_ref)
    lines = []
    say = lambda s="": (print(s), lines.append(s))
    say(ac.header("PREREG_C4_LEVEL design inputs (zero trials; no P&L of the blended book)"))
    say(f"C4 spec at {a.spec_ref}: {spec_id}; max_gross_stress {C4_CAP}; sizing_multiplier {C4_M}")
    D = ac.load_c4()
    U = D["U"]
    m = c4.declared_mask(pd.read_csv(c4.FROZEN).ticker.tolist(), "M1M2")[U]
    Tz, _ = bf.build_targets(universe=U, source=c4.FAM_SRC, mask=m)
    Tz = Tz.loc[:ac.FIT_END].reindex(D["idx"]).fillna(0.0)
    ac.assert_fit(Tz)
    r_px = D["r_px"]

    # ---- A. the risk split, from the screen's already-seen series (K4)
    elig = D["z"].notna() & D["disc"].notna()
    lvl = ac.cs_demean(D["disc"].where(elig), D["grp"])
    WL_month = level_weights(D, lvl)
    rL, _ = score(WL_month, D["r_tr"])
    Hz = bf.band_gross_capped(Tz, BAND_WIDTH, C4_CAP / C4_M)
    rz, _ = score(Hz * C4_M, D["r_tr"])
    a_, b_ = rz["pnl"], rL["pnl"]
    on = a_.index >= max(a_.ne(0).idxmax(), b_.ne(0).idxmax())
    a_, b_ = a_[on], b_[on]
    s1 = a_.mean() / a_.std() * np.sqrt(252)
    s2 = b_.mean() / b_.std() * np.sqrt(252)
    rho = a_.corr(b_)
    w1, w2 = (s1 - rho * s2) / (1 - rho ** 2), (s2 - rho * s1) / (1 - rho ** 2)
    say(f"\nA. SPLIT INPUTS (fit {a_.index[0].date()} -> {a_.index[-1].date()}; total return; already seen in K4):")
    say(f"   z spec book (x{C4_M}, cap {C4_CAP}) SR {s1:.3f}; level book SR {s2:.3f}; daily corr {rho:+.3f}")
    say(f"   mean-variance risk weights (s1 - rho s2, s2 - rho s1)/(1 - rho^2): {w1:.3f} : {w2:.3f} "
        f"-> share on z {w1 / (w1 + w2):.3f}")
    say("   plateau, blend of the two unit-risk series (a = share of risk on z):")
    za, zb = a_ / a_.std(), b_ / b_.std()
    for a in A_GRID:
        c = a * za + (1 - a) * zb
        say(f"     a {a:.2f}: SR {c.mean() / c.std() * np.sqrt(252):.3f}")

    # ---- B. the shared cap: construction properties only
    wz = unit(Tz)
    WLd = pd.DataFrame(0.0, index=D["idx"], columns=U)
    for d in D["idx"]:
        x = -lvl.loc[d].dropna()
        x = x[x != 0]
        if len(x) >= ac.MIN_NAMES:
            WLd.loc[d, x.index] = (x / x.abs().sum()).to_numpy()
    sz, sL = trailing_vol(wz, r_px), trailing_vol(WLd, r_px)
    a = 0.5
    mix = unit(wz.div(sz, axis=0).fillna(0.0) * a + WLd.div(sL, axis=0).fillna(0.0) * (1 - a))
    smix = trailing_vol(mix, r_px)
    scal = (VOL_TARGET / smix).clip(0.2, 2.5).fillna(1.0)
    TB = mix.mul(scal, axis=0)
    ac.assert_fit(TB)
    rows = []
    for lab, T in (("z-only spec book", Tz), ("blend a = 0.5", TB)):
        H = bf.band_gross_capped(T, BAND_WIDTH, C4_CAP / C4_M) * C4_M
        Hu = bf.band(T, BAND_WIDTH) * C4_M
        live = T.abs().sum(axis=1) > 0
        tg = (T.abs().sum(axis=1) * C4_M)[live]
        hg = H.abs().sum(axis=1)[live]
        ug = Hu.abs().sum(axis=1)[live]
        turn = H.diff().abs().sum(axis=1)[live].mean() * 252
        rows.append((lab, tg.mean(), (tg > C4_CAP).mean(), ug.mean(), (ug > C4_CAP).mean(), hg.mean(),
                     (hg >= C4_CAP - 1e-9).mean(), turn))
    say(f"\nB. THE SHARED CAP (account x{C4_M}, cap {C4_CAP}; band {BAND_WIDTH}; fit sessions with a target):")
    say(f"   {'book':<18}{'target gross':>13}{'P(tgt>cap)':>11}{'uncapped held':>14}{'P(>cap)':>9}"
        f"{'held gross':>11}{'P(at cap)':>10}{'turn/yr':>9}")
    for r in rows:
        say(f"   {r[0]:<18}{r[1]:>13.3f}{r[2]:>11.1%}{r[3]:>14.3f}{r[4]:>9.1%}{r[5]:>11.3f}{r[6]:>10.1%}{r[7]:>9.1f}")
    say(f"\n   level book's own ex-ante scalar: median {(VOL_TARGET / sL).clip(0.2, 2.5).median():.2f}; "
        f"z: {(VOL_TARGET / sz).clip(0.2, 2.5).median():.2f}; blend: {scal.median():.2f}")
    out = "prereg_c4_level_design_output.txt" if spec_id == "c4_families.v3.20261102" else \
        f"prereg_c4_level_design_output_{spec_id.split('.')[1]}.txt"
    (Path(__file__).with_name(out)).write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
