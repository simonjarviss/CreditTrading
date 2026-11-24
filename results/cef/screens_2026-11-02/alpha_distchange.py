"""S2 -- distribution cuts and raises: does the live z read a re-rating as a dislocation? Zero trials.

MECHANISM AND LOSER (BRIEF §2, M7). Yield-screening retail holders re-rate a fund
when its regular distribution changes. A cut drops it out of their screens: the
price falls against NAV and stays down, so the 252-session z reads the wider
discount as CHEAP and the book buys a fund whose fair discount has moved. A
raise is the mirror image: the book shorts a fund that has re-rated up. The
loser of the book's trade is the book itself. The loser the trade would exploit
is the retail holder who sells after the cut, if the re-rating overshoots.

GRAVEYARD. "Distribution data" failed twice (a universe filter: 1 of 8 variants
beat baseline, chosen after looking at 8; inside the Kalman: 1.60 -> 1.28), and
M7 says "Tested twice, failed at a 2-day hold. Do not rebuild." This screen
builds nothing. It asks the zero-trial question those tests skipped: in the
weeks after a change, does the fund's return differ from what its z predicts,
on the discount leg, and does the z's own slope change sign there? A positive
answer would make a subtract-only flag a TC lever (a construction variant, CEF
counter). A null answer closes M7 for this desk.

EVENTS. A regular change at ex-date k: amount_k and amount_{k-1} are both
regular (each <= 1.5x the median of the six distributions before it), the gap
between them is 20-100 days (a monthly or quarterly payer), and |amount_k /
amount_{k-1} - 1| > 1% (the repo builder's own rule,
scripts/fetch_cef_distributions.py). A second, declared threshold of 10% marks
"material" cuts and raises. Control events: the same funds' unchanged regular
ex-dates (|change| <= 1%). The ex-date is LATE information: the change was
declared before it (declaration dates are not in the local panel; EXDRIFT
Stage 0 showed Alpaca's are derived). Measuring from the ex-date is therefore
conservative for a tradable signal and silent on the announcement drift.

DESIGN. Decide at the ex-date close k, fill k+1, earn k+2..k+h (H1). y = the
within-group demeaned return over that window; h = 10 and 42 sessions, both
declared here. Event OLS: y = a + b_cut*cut + b_raise*raise + b_z*z +
b_cz*(cut x z) + b_rz*(raise x z), with standard errors clustered by calendar month
(sponsors cut many funds on one date).

NEGATIVE CONTROLS, DECLARED BEFORE THE RUN (H12):
  NC1 (the leg the mechanism cannot use): the NAV total-return leg. A retail
      re-rating moves the discount, not the holdings. If b_cut is as large on the
      NAV leg, the cut is news about the holdings, and the price simply follows
      NAV: there is no discount trade.
  NC2 (the events the mechanism cannot use): unchanged ex-dates. They are the
      intercept and the base of every dummy, so a post-ex-date drift common to
      all ex-dates (r6's) cancels by construction.
Kill line: |t(b_cut)| and |t(b_raise)| < 2 on the discount leg at both horizons,
or NC1 as large as the discount leg.

Run (from the worktree root):  python3 -B results/cef/screens_2026-11-02/alpha_distchange.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alpha_common as ac  # noqa: E402

HORIZONS = (10, 42)
SPECIAL_MULT = 1.5
CHANGE = 0.01
MATERIAL = 0.10


def events(D: dict) -> pd.DataFrame:
    d = D["dist"].groupby(["ticker", "ex_date"])["amount"].sum().reset_index().sort_values(["ticker", "ex_date"])
    out = []
    for t, g in d.groupby("ticker"):
        a = g["amount"].to_numpy()
        ex = g["ex_date"].to_numpy()
        med6 = pd.Series(a).shift(1).rolling(6, min_periods=6).median().to_numpy()   # strictly before k
        for k in range(7, len(a)):
            reg_k = a[k] <= SPECIAL_MULT * med6[k]
            reg_p = a[k - 1] <= SPECIAL_MULT * med6[k - 1]
            gap = (pd.Timestamp(ex[k]) - pd.Timestamp(ex[k - 1])).days
            if not (reg_k and reg_p and 20 <= gap <= 100):
                continue
            ch = a[k] / a[k - 1] - 1.0
            out.append(dict(ticker=t, ex_date=pd.Timestamp(ex[k]), change=ch))
    e = pd.DataFrame(out)
    e = e[(e.ex_date >= ac.SAMPLE_START) & (e.ex_date <= ac.FIT_END)]
    e["kind"] = np.where(e.change < -CHANGE, "cut", np.where(e.change > CHANGE, "raise", "none"))
    return e.reset_index(drop=True)


def ols_cluster(y, X, cl):
    X = np.column_stack([np.ones(len(y)), X])
    XtX = X.T @ X
    b = np.linalg.solve(XtX, X.T @ y)
    e = y - X @ b
    meat = np.zeros((X.shape[1],) * 2)
    for c in np.unique(cl):
        m = cl == c
        s = X[m].T @ e[m]
        meat += np.outer(s, s)
    G = len(np.unique(cl))
    inv = np.linalg.inv(XtX)
    V = inv @ meat @ inv * G / (G - 1)
    return b, b / np.sqrt(np.diag(V)), G


def run(D: dict, thr: float) -> None:
    E = events(D)
    E["kind"] = np.where(E.change < -thr, "cut", np.where(E.change > thr, "raise",
                         np.where(E.change.abs() <= CHANGE, "none", "small")))
    E = E[E.kind != "small"]
    idx = D["idx"]
    E = E[E.ex_date.isin(idx)]
    legs = {"price TR": D["r_tr"], "NC1 NAV TR": D["r_nav_tr"], "discount leg": D["r_tr"] - D["r_nav_tr"]}
    zdm = ac.cs_demean(D["z"], D["grp"])
    print(f"\n  threshold |change| > {thr:.0%}: events cut {int((E.kind=='cut').sum())}, raise "
          f"{int((E.kind=='raise').sum())}, control (unchanged) {int((E.kind=='none').sum())}; "
          f"funds with a cut {E[E.kind=='cut'].ticker.nunique()}")
    print(f"  mean z at the ex-date (within-group demeaned): cut {zdm.stack().reindex(pd.MultiIndex.from_frame(E[E.kind=='cut'][['ex_date','ticker']])).mean():+.2f}, "
          f"raise {zdm.stack().reindex(pd.MultiIndex.from_frame(E[E.kind=='raise'][['ex_date','ticker']])).mean():+.2f}, "
          f"none {zdm.stack().reindex(pd.MultiIndex.from_frame(E[E.kind=='none'][['ex_date','ticker']])).mean():+.2f}")
    print(f"  {'leg':<14}{'h':>4}{'n':>6}{'clus':>6}{'b_cut bp':>10}{'t':>7}{'b_raise bp':>11}{'t':>7}"
          f"{'b_z bp/z':>10}{'t':>7}{'cut x z':>9}{'t':>7}{'raise x z':>10}{'t':>7}")
    for h in HORIZONS:
        for lab, r in legs.items():
            y = ac.cs_demean(ac.fwd(r, 2, h), D["grp"])
            v = E.copy()
            v["y"] = y.stack().reindex(pd.MultiIndex.from_frame(v[["ex_date", "ticker"]])).to_numpy()
            v["z"] = zdm.stack().reindex(pd.MultiIndex.from_frame(v[["ex_date", "ticker"]])).to_numpy()
            v = v.dropna(subset=["y", "z"])
            cut = (v.kind == "cut").astype(float).to_numpy()
            rai = (v.kind == "raise").astype(float).to_numpy()
            z = v.z.to_numpy()
            X = np.column_stack([cut, rai, z, cut * z, rai * z])
            b, t, G = ols_cluster(v.y.to_numpy() * 1e4, X, v.ex_date.dt.to_period("M").astype(str).to_numpy())
            print(f"  {lab:<14}{h:>4}{len(v):>6}{G:>6}{b[1]:>10.1f}{t[1]:>7.2f}{b[2]:>11.1f}{t[2]:>7.2f}"
                  f"{b[3]:>10.1f}{t[3]:>7.2f}{b[4]:>9.1f}{t[4]:>7.2f}{b[5]:>10.1f}{t[5]:>7.2f}")


def cut_book(D: dict, thr: float = CHANGE, h: int = 42, side: str = "cut") -> tuple[pd.DataFrame, pd.DataFrame]:
    """The cut-short as an event book on the canonical harness (report only).

    On each cut ex-date k (decided at the k close) the fund is shorted and its
    family's other eligible names are bought equally against it (a within-family
    hedge, as the test's demeaning implies), held for h-1 rows so that under
    shift(2) it earns k+2..k+h. Active events share unit gross equally. For
    side="raise" the signs flip (long the raised fund). Weights use only
    information at k (the ex-date amount and the panel through k)."""
    E = events(D)
    E = E[(E.change < -thr) if side == "cut" else (E.change > thr)]
    E = E[E.ex_date.isin(D["idx"])]
    sign = -1.0 if side == "cut" else 1.0
    idx = D["idx"]
    W = pd.DataFrame(0.0, index=idx, columns=D["U"])
    elig = D["z"].notna()
    for _, e in E.iterrows():
        i = idx.get_loc(e.ex_date)
        rows = idx[i:i + h - 1]
        fam = D["grp"].get(e.ticker)
        peers = [c for c in D["grp"][D["grp"] == fam].index if c != e.ticker and elig.loc[e.ex_date, c]]
        if not elig.loc[e.ex_date, e.ticker] or len(peers) < 2:
            continue
        leg = pd.Series(-sign / len(peers), index=peers)
        leg[e.ticker] = sign
        W.loc[rows, leg.index] += leg.to_numpy()
    g = W.abs().sum(axis=1)
    W = W.div(g.where(g > 0), axis=0).fillna(0.0)   # unit gross when anything is on; zero rows stay zero
    from scripts.research import harness
    held = W.shift(harness.EXEC_LAG).fillna(0.0)
    R = D["r_tr"]
    bad = (held != 0) & R.isna()
    # a fund can stop trading inside a hold (delisting, panel gap): report and drop those cells loudly
    nbad = int(bad.sum().sum())
    if nbad:
        print(f"  NOTE: {nbad} held name-days have no return in the panel; the weight is zeroed there "
              f"(they are listed: {bad.stack()[bad.stack()].index[:3].tolist()} ...)")
        W = W.mask(bad.shift(-harness.EXEC_LAG, fill_value=False), 0.0)
    return W, R.fillna(0.0)


def main() -> int:
    cnt = ac.counters()
    print(ac.header("S2 DISTRIBUTION CUTS AND RAISES x LIVE Z (zero trials)"))
    print(f"CEF counter {cnt['CEF']}: a flag would be trial N={cnt['CEF'] + 1}, bar {ac.bar(cnt['CEF'] + 1):.3f}")
    for loader in (ac.load_core, ac.load_c4):
        D = loader()
        print("\n" + D["name"])
        for thr in (CHANGE, MATERIAL):
            run(D, thr)
        from scripts.research import harness
        for side in ("cut", "raise"):
            W, R = cut_book(D, CHANGE, 42, side)
            rep = harness.report(W, R)
            f = rep["full"]
            on = (W.abs().sum(axis=1) > 0).mean()
            print(f"  HARNESS {side}-book (|chg|>1%, h 42, family-hedged, unit gross when on; on {on:.0%} of sessions): "
                  f"gross SR {f['gross_sr']:+.2f}  ann {f['ann_ret']*100:+.2f}%  vol {f['vol']*100:.2f}%  turn/yr {f['turn']:.1f}  "
                  f"net SR @5/15/30 " + " / ".join(f"{v:+.2f}" for v in f['net_sr'].values()) +
                  f"  flips {'YES' if f['sign_flips'] else 'no'}")
            print("     eras: " + "; ".join(f"{k} {v['gross_sr']:+.2f}" for k, v in rep["eras"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
