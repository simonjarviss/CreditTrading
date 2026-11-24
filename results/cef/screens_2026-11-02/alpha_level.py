"""S5 (added by this seat) -- the cross-sectional discount LEVEL against peers, slow. Zero trials.

MECHANISM AND LOSER. Pontiff (1995) [U on magnitude, docs/REFERENCES.md]: funds
at premiums earn negative abnormal returns and funds at discounts positive ones,
over months. The loser is the yield-chasing holder who pays a premium for a
brand or a distribution rate. It persists because the arbitrage is a SHORT of
the premium fund: the lendable pool cannot grow (no creation), borrow is
dearest exactly there, and idiosyncratic risk is the binding cost (Pontiff
2006 [S]).

WHY THE LIVE Z IS BLIND TO IT, BY CONSTRUCTION. z = (disc - own 252-session
mean) / own sd. A fund that has sat 10pp rich of its peers for a year has z
near zero, so the book never trades the level. docs/SYSTEM.md says ranking on
the raw discount "would be a permanent long-muni bet dressed as a signal";
that is ACROSS groups, so this screen demeans the level WITHIN group (core:
muni/multi/hy/loan) and within C4 family. It is not in KILLED or in "KILLED --
CEF construction variants" (checked 2026-11-02). It is not a horizon mix of
the z: it uses no own-history standardisation at all.

NEGATIVE CONTROLS, DECLARED BEFORE THE RUN (H12):
  NC1 (fair value in costume, M4/M8): the NAV total-return leg. If the level
      predicts the NAV return (premium funds' NAVs do better or worse because of
      fees, leverage or return of capital), the discount is a fair-value
      statement about the holdings and there is no convergence trade. The
      mechanism says the effect is on the DISCOUNT leg and NAV is flat.
  NC2 (mechanical carry, which paper cannot see): split the price total return
      into the price-only return and the distribution yield D/P. A discount
      fund's D/P is mechanically higher (D is paid on NAV), so part of any
      total-return effect is carry, not convergence. Alpaca paper credits no
      dividends, so only the price-only part would show in the P&L of record.
Kill line: |t| of the level coefficient < 2 on the discount leg at both
horizons with z in the regression, or NC1 as large as the discount leg.

DESIGN. Decide on every 21st session t (non-overlapping monthly grid; a
63-session grid for the 3-month horizon), y = within-group demeaned return
over t+2..t+h (H1), h = 21 and 63, declared here. Regressors: the
within-group demeaned discount level (pp) and the within-group demeaned z.
Pooled OLS, standard errors clustered by date (H6).

Run (from the worktree root):  python3 -B results/cef/screens_2026-11-02/alpha_level.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alpha_common as ac  # noqa: E402

HORIZONS = (21, 63)


def dist_yield(D: dict) -> pd.DataFrame:
    """D_t / P_{t-1} on each ex-date (the leg the price-only return omits)."""
    amt = D["dist"].groupby(["ex_date", "ticker"])["amount"].sum().unstack()
    amt = amt.reindex(index=D["idx"], columns=D["U"])
    return (amt / D["px"].shift(1)).fillna(0.0).where(D["r_tr"].notna())


def run(D: dict) -> dict:
    elig = D["z"].notna() & D["disc"].notna()
    lvl = ac.cs_demean(D["disc"].where(elig), D["grp"])
    zz = ac.cs_demean(D["z"].where(elig), D["grp"])
    y_div = dist_yield(D)
    legs = {"price TR": D["r_tr"], "NC1 NAV TR": D["r_nav_tr"], "discount leg (TR-NAV)": D["r_tr"] - D["r_nav_tr"],
            "NC2a price-only": D["r_tr"] - y_div, "NC2b distribution yield": y_div}
    out = {}
    print(f"\n{D['name']}")
    print(f"  {'leg':<26}{'h':>4}{'b_level bp/pp':>14}{'t':>7}{'(z out) b':>11}{'t':>7}{'b_z bp/z':>10}{'t':>7}{'n':>7}{'dates':>6}")
    for h in HORIZONS:
        grid = D["idx"][::h]
        for lab, r in legs.items():
            y = ac.cs_demean(ac.fwd(r, 2, h).where(elig), D["grp"]) * 1e4
            a = ac.pooled_ols(y, {"lvl": lvl, "z": zz}, grid, min_n=ac.MIN_NAMES)
            b = ac.pooled_ols(y, {"lvl": lvl}, grid, min_n=ac.MIN_NAMES)
            out[(lab, h)] = a
            print(f"  {lab:<26}{h:>4}{a['lvl']['coef']:>14.2f}{a['lvl']['t']:>7.2f}{b['lvl']['coef']:>11.2f}"
                  f"{b['lvl']['t']:>7.2f}{a['z']['coef']:>10.2f}{a['z']['t']:>7.2f}{a['n']:>7d}{a['dates']:>6d}")
    # era stability of the declared headline cell: discount leg, h = 63, z in
    print("  by era (discount leg / price TR, h 63, z in):")
    grid = D["idx"][::63]
    for lab, a0, b0 in (("2005-09", "2005", "2009-12-31"), ("2010-14", "2010", "2014-12-31"),
                        ("2015-19", "2015", "2019-12-31"), ("2020-22", "2020", "2022-12-31")):
        g = grid[(grid >= a0) & (grid <= b0)]
        rr = []
        for leg in ("discount leg (TR-NAV)", "price TR"):
            y = ac.cs_demean(ac.fwd(legs[leg], 2, 63).where(elig), D["grp"]) * 1e4
            rr.append(ac.pooled_ols(y, {"lvl": lvl, "z": zz}, g, min_n=ac.MIN_NAMES)["lvl"])
        print(f"    {lab}: disc {rr[0]['coef']:+7.2f} (t {rr[0]['t']:+.2f})   price TR {rr[1]['coef']:+7.2f} (t {rr[1]['t']:+.2f})")
    print(f"  cross-sectional sd of the within-group level (pp), median date: {lvl.std(axis=1).median():.2f}")
    return out


def harness_book(D: dict, hold: int = 21):
    """Report-only: monthly rebalanced within-group LEVEL book, unit gross, weights
    -level (buy the relatively cheap), decided on the 21-session grid and held to the
    next decision; scored by harness.report (shift(2)) on total returns."""
    from scripts.research import harness
    elig = D["z"].notna() & D["disc"].notna()
    lvl = ac.cs_demean(D["disc"].where(elig), D["grp"])
    W = pd.DataFrame(np.nan, index=D["idx"], columns=D["U"])
    for d in D["idx"][::hold]:
        w = -lvl.loc[d].dropna()
        w = w[w != 0]
        if len(w) < ac.MIN_NAMES:
            W.loc[d] = 0.0
            continue
        W.loc[d] = 0.0
        W.loc[d, w.index] = (w / w.abs().sum()).to_numpy()
    W = W.ffill().fillna(0.0)
    held = W.shift(harness.EXEC_LAG).fillna(0.0)
    bad = (held != 0) & D["r_tr"].isna()
    n = int(bad.sum().sum())
    W = W.mask(bad.shift(-harness.EXEC_LAG, fill_value=False), 0.0)
    rep = harness.report(W, D["r_tr"].fillna(0.0))
    f = rep["full"]
    print(f"  HARNESS level book (monthly, within group, unit gross; {n} held name-days without a return zeroed): "
          f"gross SR {f['gross_sr']:+.2f}  ann {f['ann_ret']*100:+.2f}%  vol {f['vol']*100:.2f}%  turn/yr {f['turn']:.1f}  "
          f"net SR @5/15/30 " + " / ".join(f"{v:+.2f}" for v in f['net_sr'].values()) +
          f"  flips {'YES' if f['sign_flips'] else 'no'}")
    print("     eras: " + "; ".join(f"{k} {v['gross_sr']:+.2f} ({v['ann_ret']*100:+.2f}%)" for k, v in rep["eras"].items()))
    # the same book on price-only returns: what Alpaca paper's P&L of record would see
    y_div = dist_yield(D).fillna(0.0)
    rep2 = harness.report(W, (D["r_tr"] - y_div).fillna(0.0))
    print(f"     on PRICE-ONLY returns (paper's view): gross SR {rep2['full']['gross_sr']:+.2f}  "
          f"ann {rep2['full']['ann_ret']*100:+.2f}%")
    return rep


def main() -> int:
    cnt = ac.counters()
    print(ac.header("S5 CROSS-SECTIONAL DISCOUNT LEVEL WITHIN GROUP (zero trials)"))
    print(f"CEF counter {cnt['CEF']}: a sleeve here would be trial N={cnt['CEF'] + 1}, bar {ac.bar(cnt['CEF'] + 1):.3f}")
    for loader in (ac.load_core, ac.load_c4):
        D = loader()
        run(D)
        harness_book(D)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
