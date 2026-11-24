"""S1 -- year-end tax-loss selling in CEF discounts, orthogonal to the live z. Zero trials.

MECHANISM AND LOSER. Taxable retail holders sell their year-to-date losers in
December to harvest the loss (Starks, Yong & Zheng 2006 report it in muni CEFs
[S]). The selling is of the CEF SHARE, not of the fund's holdings, so it
should push PRICE below NAV for losers into the year end, and the concession
should reverse in January when the selling stops. The loser is the tax seller,
who accepts the concession because the tax value exceeds it; they persist
because the tax code repeats every year.

WHAT IS ALREADY KNOWN (graveyard / CLOSED, read first). CORE-b
(results/cef/CORE_SIGNAL_CANDIDATES_2026-10-12.md §4) closed the turn of year
as a sleeve or gate at zero trials on the DEPLOYED 13: the Dec-Jan concentration
sits in the deployed z's own slope, the loser/winner gradient holds in Feb-Nov
too (the calendar control), and 9 seasons is D7. What this screen adds: (i) the
loser score as its OWN regressor beside z (is it orthogonal?), (ii) the
discount/NAV split of the January return, (iii) 17 seasons on WIDE17 and 17 on
C4's 65 funds, (iv) the calendar control done as a like-for-like month-end
panel rather than a Feb-Nov slice.

NEGATIVE CONTROLS, DECLARED BEFORE THE RUN (H12):
  NC1 (where the mechanism cannot act): the NAV total-return leg. Tax selling
      of the share cannot move the holdings. If the loser coefficient is as
      large on the NAV leg as on the price leg, it is the underlying assets'
      own January effect (or stale marks), not CEF tax-loss selling.
  NC2 (when the mechanism cannot act): the identical construction decided at
      the penultimate session of every OTHER month (Jan-Nov decisions), with
      the same trailing-252-session loser score. Tax-loss predicts the
      December-decision cell is larger than the mean of the other eleven.
      Kill line: the December-minus-other difference has t over seasons < 2.

DESIGN. Decide at t = penultimate December session (fill at the last December
close, t+1), earn sessions t+2..t+21 (the first ~20 January sessions):
`alpha_common.fwd(r, 2, 21)`. Loser score L = trailing-252-session total
return through t, cross-sectional percentile rank, demeaned within group
(core: muni/multi/hy/loan; C4: family) so it is not a group bet. z is the
deployed z at t, demeaned the same way. One cross-sectional regression per
season, y = b_L L + b_z z; the season is the unit of independence, so t is
over seasons. Last season decided 2021-12-30 (its window ends in Jan 2022);
the 2022-12 season's window is in the 2023 holdout and is not computed.

Run (from the worktree root):  python3 -B results/cef/screens_2026-11-02/alpha_taxloss.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alpha_common as ac  # noqa: E402

H = 21          # earn t+2 .. t+21: about the first 20 sessions of the next month
LOOKBACK = 252  # trailing return window for the loser score (= YTD at a December decision)


def penultimate_sessions(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(idx, index=idx)
    g = s.groupby([idx.year, idx.month])
    out = g.apply(lambda x: x.iloc[-2] if len(x) >= 2 else pd.NaT).dropna()
    return pd.DatetimeIndex(out.values)


def season_coefs(D: dict, dates: pd.DatetimeIndex, leg: str, with_z: bool, by_group: bool):
    r = D[leg]
    y = ac.fwd(r, 2, H)
    lr = np.log1p(D["r_tr"]).rolling(LOOKBACK, min_periods=200).sum()   # through t (H7)
    by = D["grp"] if by_group else None
    rows = []
    for d in dates:
        ok = D["z"].loc[d].notna() & y.loc[d].notna() & lr.loc[d].notna()
        if ok.sum() < ac.MIN_NAMES:
            continue
        cols = ok[ok].index
        L = lr.loc[d, cols].rank(pct=True)
        Z = D["z"].loc[d, cols]
        Y = y.loc[d, cols]
        f = pd.DataFrame({"Y": Y, "L": -L, "Z": Z})   # L positive = bigger loser
        if by is not None:
            g = by.reindex(cols)
            f = f.groupby(g.values).transform(lambda s: s - s.mean())
        else:
            f = f - f.mean()
        X = f[["L", "Z"]] if with_z else f[["L"]]
        if (X.std() == 0).any():
            continue
        b = np.linalg.lstsq(X.to_numpy(), f["Y"].to_numpy(), rcond=None)[0]
        # the long-short return of unit-gross weights on L (residualised on Z when with_z)
        Lw = f["L"]
        if with_z:
            zz = f["Z"]
            Lw = Lw - (Lw @ zz) / (zz @ zz) * zz if (zz @ zz) > 0 else Lw
        w = Lw / Lw.abs().sum()
        rows.append(dict(date=d, month=d.month, bL=b[0] * 1e4, ls_bp=float((w * f["Y"]).sum() * 1e4 + 0.0),
                         n=int(ok.sum())))
    return pd.DataFrame(rows)


def t_of(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))) if len(x) > 2 else np.nan


def run(D: dict, label: str, by_group: bool) -> dict:
    pen = penultimate_sessions(D["idx"])
    pen = pen[pen <= ac.FIT_END]
    out = {}
    print(f"\n--- {label}; demeaned {'within group' if by_group else 'across all names'}; "
          f"earn t+2..t+{H}; t over seasons (one cross-section per decision date)")
    print(f"{'leg':<26}{'z in?':>6}{'Dec seasons':>12}{'b_L bp/rank':>12}{'t':>7}{'LS bp/season':>13}{'t':>7}"
          f"{'other-month b_L':>16}{'Dec-other':>10}{'t(diff)':>8}")
    for leg, lab in (("r_tr", "price total return"), ("r_nav_tr", "NC1: NAV total return"),
                     ("disc_leg", "discount leg (tr - nav)")):
        if leg == "disc_leg":
            D = dict(D, disc_leg=D["r_tr"] - D["r_nav_tr"])
        for wz in (False, True):
            c = season_coefs(D, pen, leg, wz, by_group)
            if c.empty:
                continue
            dec = c[c.month == 12].set_index(c[c.month == 12].date.dt.year)
            oth = c[c.month != 12]
            # NC2: per season-year, December minus that year's mean of the other months' coefficients
            om = oth.groupby(oth.date.dt.year)["bL"].mean()
            diff = (dec["bL"] - om.reindex(dec.index)).dropna()
            r = dict(seasons=len(dec), bL=dec.bL.mean(), t=t_of(dec.bL), ls=dec.ls_bp.mean(), t_ls=t_of(dec.ls_bp),
                     other=oth.bL.mean(), diff=diff.mean(), t_diff=t_of(diff), n_med=int(dec.n.median()))
            out[(leg, wz)] = r
            print(f"{lab:<26}{'yes' if wz else 'no':>6}{r['seasons']:>12d}{r['bL']:>12.1f}{r['t']:>7.2f}{r['ls']:>13.1f}"
                  f"{r['t_ls']:>7.2f}{r['other']:>16.1f}{r['diff']:>10.1f}{r['t_diff']:>8.2f}")
    return out


def harness_book(D: dict, by_group: bool = True, hold: int = H - 1):
    """The December overlay as a weight matrix on the canonical harness.

    H.loc[t] = unit-gross weights on L residualised on z (within group), set on
    each penultimate-December decision date t and held for `hold` rows, so under
    `harness.evaluate`'s shift(2) they earn sessions t+2 .. t+1+hold = t+2..t+21,
    the window `season_coefs` measures. Zero on every other row."""
    from scripts.research import harness
    pen = penultimate_sessions(D["idx"])
    pen = pen[(pen <= ac.FIT_END) & (pen.month == 12)]
    lr = np.log1p(D["r_tr"]).rolling(LOOKBACK, min_periods=200).sum()
    y = ac.fwd(D["r_tr"], 2, H)
    W = pd.DataFrame(0.0, index=D["idx"], columns=D["U"])
    for d in pen:
        ok = D["z"].loc[d].notna() & y.loc[d].notna() & lr.loc[d].notna()
        if ok.sum() < ac.MIN_NAMES:
            continue
        cols = ok[ok].index
        f = pd.DataFrame({"L": -lr.loc[d, cols].rank(pct=True), "Z": D["z"].loc[d, cols]})
        g = D["grp"].reindex(cols) if by_group else pd.Series("all", index=cols)
        f = f.groupby(g.values).transform(lambda s: s - s.mean())
        zz = f["Z"]
        Lw = f["L"] - (f["L"] @ zz) / (zz @ zz) * zz if (zz @ zz) > 0 else f["L"]
        w = Lw / Lw.abs().sum()
        i = D["idx"].get_loc(d)
        rows = D["idx"][i:i + hold]
        W.loc[rows, cols] = w.to_numpy()
    held = W.shift(harness.EXEC_LAG).fillna(0.0)
    R = D["r_tr"]
    bad = (held != 0) & R.isna()
    if bad.any().any():
        raise ValueError(f"a held name-day has no return: {bad.stack()[bad.stack()].index[:5].tolist()}")
    return W, R.fillna(0.0)     # safe: every NaN left multiplies a weight just proved zero


def print_report(lab: str, W: pd.DataFrame, R: pd.DataFrame) -> dict:
    from scripts.research import harness
    rep = harness.report(W, R)
    f = rep["full"]
    seasons = int((W.abs().sum(axis=1).diff() > 0).sum())
    ev = rep["evaluate"]
    per_season_bp = ev["pnl"].sum() / max(seasons, 1) * 1e4
    print(f"  {lab:<44} gross SR {f['gross_sr']:+.2f}  ann {f['ann_ret']*100:+.3f}%  vol {f['vol']*100:.3f}%  "
          f"turn/yr {f['turn']:.2f}  net SR @5/15/30 " + " / ".join(f"{v:+.2f}" for v in f['net_sr'].values()) +
          f"  flips {'YES' if f['sign_flips'] else 'no'};  {seasons} seasons, {per_season_bp:+.1f}bp/season gross")
    for e, r in rep["eras"].items():
        print(f"      era {e}: gross ann {r['ann_ret']*100:+.3f}%  SR {r['gross_sr']:+.2f}  turn {r['turn']:.2f}")
    return rep


def by_family(D: dict) -> None:
    pen = penultimate_sessions(D["idx"])
    pen = pen[(pen <= ac.FIT_END) & (pen.month == 12)]
    print("  by family (discount leg / price TR leg, z in, within family; t over seasons):")
    for fam in sorted(D["grp"].dropna().unique()):
        cols = D["grp"][D["grp"] == fam].index.tolist()
        if len(cols) < ac.MIN_NAMES:
            print(f"    {fam:<22} {len(cols)} names < MIN_NAMES; not split")
            continue
        sub = dict(D, U=cols, **{k: D[k][cols] for k in ("r_tr", "r_nav_tr", "z")}, grp=D["grp"][cols])
        sub["disc_leg"] = sub["r_tr"] - sub["r_nav_tr"]
        out = []
        for leg in ("disc_leg", "r_tr"):
            c = season_coefs(sub, pen, leg, True, True)
            out.append((c.bL.mean(), t_of(c.bL), len(c)) if len(c) else (np.nan, np.nan, 0))
        print(f"    {fam:<22} {len(cols):>3} names  disc {out[0][0]:+7.1f} (t {out[0][1]:+.2f}, {out[0][2]} s)   "
              f"price {out[1][0]:+7.1f} (t {out[1][1]:+.2f})")


def by_era(D: dict) -> None:
    pen = penultimate_sessions(D["idx"])
    pen = pen[(pen <= ac.FIT_END) & (pen.month == 12)]
    D = dict(D, disc_leg=D["r_tr"] - D["r_nav_tr"])
    cd = season_coefs(D, pen, "disc_leg", True, True).set_index("date")
    cp = season_coefs(D, pen, "r_tr", True, True).set_index("date")
    print("  by era of the December decision (z in, within group): mean b_L bp/rank, discount leg | price TR leg")
    for lab, a, b in (("2005-09", 2005, 2009), ("2010-14", 2010, 2014), ("2015-19", 2015, 2019), ("2020-21", 2020, 2021)):
        m = (cd.index.year >= a) & (cd.index.year <= b)
        print(f"    {lab}: {m.sum()} seasons  disc {cd.bL[m].mean():+7.1f}  price {cp.bL[m].mean():+7.1f}   "
              f"positive seasons disc {int((cd.bL[m] > 0).sum())}/{m.sum()}")


def main() -> int:
    cnt = ac.counters()
    b_cef = ac.bar(cnt["CEF"] + 1)
    print(ac.header("S1 YEAR-END TAX-LOSS x LIVE Z (zero trials)"))
    print(f"CEF counter {cnt['CEF']} -> a trial here would be N={cnt['CEF'] + 1}, bar {b_cef:.3f}")
    res = {}
    for loader in (ac.load_core, ac.load_c4):
        D = loader()
        print("\n" + D["name"] + f": {len(D['U'])} names, {D['idx'][0].date()} -> {D['idx'][-1].date()}")
        for bg in (True, False):
            res[(D["name"][:6], bg)] = run(D, D["name"][:6], bg)
    print("\nHARNESS P&L of the December overlay alone (harness.report; shift(2); total returns; unit gross while on):")
    for loader in (ac.load_core, ac.load_c4):
        D = loader()
        W, R = harness_book(D)
        print_report(D["name"][:6] + " L resid. on z, within group", W, R)
        if D["name"].startswith("C4"):
            by_family(D)
        by_era(D)
    print("\nPOWER (upper bound: in-sample t taken as the true effect):")
    for k, v in res.items():
        r = v.get(("r_tr", True))
        if r:
            print(f"  {k[0]} {'within-grp' if k[1] else 'all-names'}: Dec b_L t {r['t']:+.2f} (z in) -> P(t>=bar) "
                  f"{ac.p_pass(abs(r['t']), b_cef):.3f};  Dec-other t {r['t_diff']:+.2f} -> "
                  f"{ac.p_pass(abs(r['t_diff']), b_cef):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
