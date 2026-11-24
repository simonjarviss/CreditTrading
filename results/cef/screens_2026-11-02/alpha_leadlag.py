"""S3 -- cross-universe lead-lag: does C4's discount move lead the core's? Executable closes only. Zero trials.

MECHANISM AND LOSER. CEF discounts share a retail-sentiment factor (Lee,
Shleifer & Thaler 1991 [S]). Equity CEFs carry FRESH NAVs (their holdings
print at 16:00), so their discount move on day t is a clean read of that
day's sentiment; credit CEF discounts are contaminated by stale NAVs. If
sentiment reaches the credit funds' slower, yield-focused holders a day or two
late, an equity-CEF discount move at t predicts the credit CEFs' PRICE at
t+2..t+3. The loser would be the late-moving credit-CEF holder. Nothing
arbitrages it because neither wrapper has APs.

GRAVEYARD. `leadlag` (KILLED, D1) was pure non-synchronous trading: measured
on (H+L)/2 it had mean t 5.20, and on executable close-to-close with T+1 it
was -0.50, with the Treasury control scoring higher. This screen therefore
uses only executable closes, the shift(2) window (decide t, MOC fill t+1,
earn t+2..t+3), a non-overlapping 2-session grid, and NW t (H6).

THE TRADABLE FORM FOR THIS BOOK. The core is dollar-neutral, so a common
timing signal cannot feed it. Two targets are tested: Y1, the core's
equal-weight price total return (a net-exposure timing leg, which would add
the beta the book avoids), and Y2, the core's taxable-minus-muni spread return
(M5, the group bet that is 92.5% of the book's risk by accident). Y2 is the
one a two-account book could actually use.

NEGATIVE CONTROLS, DECLARED BEFORE THE RUN (H12):
  NC1 (the stale-mark well): the core's equal-weight NAV total return over
      t+2..t+3. If C4's move predicts the core's NAV as strongly as its price,
      it is equity news leaking into stale credit marks, not sentiment, and it
      is the well six of thirteen graveyard entries died in.
  NC2 (a market that has no CEF holders): IEF's total return over t+2..t+3.
      If C4's discount move predicts Treasuries, it is a macro factor.
  NC3 (direction): the reverse regression, the core's discount move at t on
      C4's price at t+2..t+3. A symmetric result is a common autocorrelated
      factor, not a lead.
Kill line: |NW t| < 2 on Y1 and Y2, or NC1/NC2 as large as the target.

Regressors at t (all known at the t close): X = C4 fresh-NAV families'
equal-weight discount change (pp), with controls for the core's own
equal-weight discount change and price return at t, and C4's price return at t.

Run (from the worktree root):  python3 -B results/cef/screens_2026-11-02/alpha_leadlag.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alpha_common as ac  # noqa: E402

FRESH = ("equity_domestic", "equity_sector", "equity_covered_call")   # C4's own stale-NAV control set


def ew(frame: pd.DataFrame, cols, min_n=ac.MIN_NAMES) -> pd.Series:
    x = frame[cols]
    return x.mean(axis=1).where(x.notna().sum(axis=1) >= min_n)


def nw_ols(y: pd.Series, X: pd.DataFrame, lags: int = 5) -> pd.DataFrame:
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    Y = d["y"].to_numpy()
    Z = np.column_stack([np.ones(len(d)), d[X.columns].to_numpy()])
    b = np.linalg.lstsq(Z, Y, rcond=None)[0]
    e = Y - Z @ b
    n = len(Y)
    S = (Z * e[:, None]).T @ (Z * e[:, None]) / n
    for L in range(1, lags + 1):
        G = (Z[L:] * e[L:, None]).T @ (Z[:-L] * e[:-L, None]) / n
        S += (1 - L / (lags + 1)) * (G + G.T)
    Q = np.linalg.inv(Z.T @ Z / n)
    V = Q @ S @ Q / n
    return pd.DataFrame({"coef": b, "t": b / np.sqrt(np.diag(V))}, index=["const", *X.columns]).assign(n=n)


def main() -> int:
    print(ac.header("S3 C4 -> CORE LEAD-LAG ON EXECUTABLE CLOSES (zero trials)"))
    C, F = ac.load_core(), ac.load_c4()
    idx = C["idx"].intersection(F["idx"])
    fresh = [c for c in F["U"] if F["grp"][c] in FRESH]
    taxable = [c for c in C["U"] if C["grp"][c] != "muni"]
    muni = [c for c in C["U"] if C["grp"][c] == "muni"]
    elig_c = C["z"].notna()
    elig_f = F["z"].notna()
    dC = C["disc"].diff().where(elig_c)
    dF = F["disc"].diff().where(elig_f)
    X = pd.DataFrame({
        "dDisc_C4fresh": ew(dF, fresh),
        "dDisc_core": ew(dC, C["U"]),
        "ret_core": ew(C["r_tr"].where(elig_c), C["U"]),
        "ret_C4fresh": ew(F["r_tr"].where(elig_f), fresh),
    }).reindex(idx)
    ief = pd.read_parquet(ac.WT / "data" / "etf_daily.parquet")
    ief = ief[ief.ticker == "IEF"].set_index("date")["ret_total"].reindex(idx)
    f2 = lambda s: (1 + s.shift(-2)) * (1 + s.shift(-3)) - 1          # t+2..t+3 (H1)
    Y = {
        "Y1 core EW price TR": f2(ew(C["r_tr"].where(elig_c), C["U"]).reindex(idx)),
        "Y2 core taxable-muni spread": f2(ew(C["r_tr"].where(elig_c), taxable, 3).reindex(idx)) -
                                       f2(ew(C["r_tr"].where(elig_c), muni, 2).reindex(idx)),
        "NC1 core EW NAV TR": f2(ew(C["r_nav_tr"].where(elig_c), C["U"]).reindex(idx)),
        "NC2 IEF TR": f2(ief),
    }
    grid = idx[::2]
    print(f"sessions {idx[0].date()} -> {idx[-1].date()}; 2-session grid n={len(grid)}; C4 fresh-NAV funds {len(fresh)}; "
          f"core taxable {len(taxable)}, muni {len(muni)}")
    print(f"\n{'target (t+2..t+3)':<30}{'b on dDisc_C4fresh, bp per pp':>32}{'NW t':>8}{'own dDisc_core':>16}{'t':>7}{'n':>6}")
    for lab, y in Y.items():
        r = nw_ols(y.reindex(grid) * 1e4, X.reindex(grid))
        print(f"{lab:<30}{r.loc['dDisc_C4fresh','coef']:>32.2f}{r.loc['dDisc_C4fresh','t']:>8.2f}"
              f"{r.loc['dDisc_core','coef']:>16.2f}{r.loc['dDisc_core','t']:>7.2f}{int(r['n'].iloc[0]):>6d}")
    # NC3: the reverse direction
    Xr = pd.DataFrame({"dDisc_core": X["dDisc_core"], "dDisc_C4fresh": X["dDisc_C4fresh"],
                       "ret_core": X["ret_core"], "ret_C4fresh": X["ret_C4fresh"]})
    yr = f2(ew(F["r_tr"].where(elig_f), fresh).reindex(idx))
    r = nw_ols(yr.reindex(grid) * 1e4, Xr.reindex(grid))
    print(f"{'NC3 C4 fresh EW price TR':<30}{'(b on dDisc_core:)':>20}{r.loc['dDisc_core','coef']:>12.2f}"
          f"{r.loc['dDisc_core','t']:>8.2f}   own dDisc_C4fresh {r.loc['dDisc_C4fresh','coef']:+.2f} (t {r.loc['dDisc_C4fresh','t']:+.2f})")
    print("\nby era, Y2 (the M5 spread) on dDisc_C4fresh:")
    for lab, a, b in (("2005-09", "2005", "2009"), ("2010-14", "2010", "2014"), ("2015-19", "2015", "2019"),
                      ("2020-22", "2020", "2022")):
        g = grid[(grid >= a) & (grid <= f"{b}-12-31")]
        rr = nw_ols(Y["Y2 core taxable-muni spread"].reindex(g) * 1e4, X.reindex(g))
        r1 = nw_ols(Y["Y1 core EW price TR"].reindex(g) * 1e4, X.reindex(g))
        print(f"  {lab}: Y2 {rr.loc['dDisc_C4fresh','coef']:+7.2f} (t {rr.loc['dDisc_C4fresh','t']:+.2f})   "
              f"Y1 {r1.loc['dDisc_C4fresh','coef']:+7.2f} (t {r1.loc['dDisc_C4fresh','t']:+.2f})  n={int(rr['n'].iloc[0])}")
    sd = X["dDisc_C4fresh"].reindex(grid).std()
    print(f"\nscale: sd of dDisc_C4fresh on the grid = {sd:.3f}pp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
