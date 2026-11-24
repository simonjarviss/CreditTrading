"""S5 adversarial checks on C4's discount-level book (zero trials, fit only).

Each check is a way the S5 headline could be something other than Pontiff's
mechanism, named before it was run:
  K1 family split, and the fresh-NAV families alone: if the effect lives only in
     the stale-NAV families (preferred, multi_asset), it is the stale-mark well.
  K2 name concentration: if five funds carry the P&L, it is a few fund stories,
     not a cross-sectional effect.
  K3 persistence of the weights: a book that holds the same longs and shorts for
     years is a fixed-effect bet ("a permanent bet dressed as a signal").
  K4 overlap with C4's live z book: correlation of daily P&L, and the combined
     book. A new source must add to the z, not repeat it.
  K5 factor beta (D4, quick form): SPY and HYG total returns, same day and one
     lag summed (Dimson), on the daily P&L. A risk premium in costume would load.
  K6 the short side: share of short weight in funds Alpaca marked easy-to-borrow
     on C4's frozen read (2026-10-14) -- a one-day snapshot, true on that date only.
  K7 placebo: each fund's level replaced by that of a random other fund in its
     family on the same date (20 draws); the real book should rank above them.

Run (from the worktree root):  python3 -B results/cef/screens_2026-11-02/alpha_level_checks.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alpha_common as ac  # noqa: E402
from alpha_level import dist_yield  # noqa: E402

HOLD = 21
SEED = 20261102


def level_weights(D: dict, lvl: pd.DataFrame, cols=None) -> pd.DataFrame:
    cols = D["U"] if cols is None else cols
    W = pd.DataFrame(np.nan, index=D["idx"], columns=D["U"])
    for d in D["idx"][::HOLD]:
        w = -lvl.loc[d, cols].dropna()
        w = w[w != 0]
        W.loc[d] = 0.0
        if len(w) >= ac.MIN_NAMES:
            W.loc[d, w.index] = (w / w.abs().sum()).to_numpy()
    return W.ffill().fillna(0.0)


def score(W: pd.DataFrame, R: pd.DataFrame):
    from scripts.research import harness
    held = W.shift(harness.EXEC_LAG).fillna(0.0)
    bad = (held != 0) & R.isna()
    W = W.mask(bad.shift(-harness.EXEC_LAG, fill_value=False), 0.0)
    return harness.evaluate(W, R.fillna(0.0)), W


def main() -> int:
    print(ac.header("S5 CHECKS ON C4's LEVEL BOOK (zero trials)"))
    D = ac.load_c4()
    elig = D["z"].notna() & D["disc"].notna()
    lvl = ac.cs_demean(D["disc"].where(elig), D["grp"])
    W = level_weights(D, lvl)
    res, W = score(W, D["r_tr"])
    pnl = res["pnl"]
    print(f"headline (reproduces alpha_level.py): gross SR {res['gross_sr']:+.2f} ann {res['ann_ret']*100:+.2f}% "
          f"turn {res['turn']:.1f}")

    print("\nK1 by family (each family's own within-family book, unit gross):")
    for fam in sorted(D["grp"].unique()):
        cols = D["grp"][D["grp"] == fam].index.tolist()
        r, _ = score(level_weights(D, lvl, cols), D["r_tr"])
        print(f"  {fam:<22}{len(cols):>3} funds  gross SR {r['gross_sr']:+.2f}  ann {r['ann_ret']*100:+.2f}%  turn {r['turn']:.1f}")
    fresh = [c for c in D["U"] if D["grp"][c] in ("equity_domestic", "equity_sector", "equity_covered_call")]
    r, _ = score(level_weights(D, lvl, fresh), D["r_tr"])
    print(f"  {'FRESH-NAV families only':<22}{len(fresh):>3} funds  gross SR {r['gross_sr']:+.2f}  ann {r['ann_ret']*100:+.2f}%")
    stale = [c for c in D["U"] if c not in fresh]
    r, _ = score(level_weights(D, lvl, stale), D["r_tr"])
    print(f"  {'preferred+multi_asset':<22}{len(stale):>3} funds  gross SR {r['gross_sr']:+.2f}  ann {r['ann_ret']*100:+.2f}%")

    from scripts.research import harness
    held = W.shift(harness.EXEC_LAG).fillna(0.0)
    contrib = (held * D["r_tr"].fillna(0.0)).sum()
    tot = contrib.sum()
    top = contrib.sort_values(ascending=False)
    print(f"\nK2 name concentration: total {tot*100:+.2f}% over the fit; top 5 names "
          f"{top.head(5).sum()/tot:.0%} of it ({', '.join(f'{k} {v*100:+.1f}%' for k, v in top.head(5).items())}); "
          f"bottom 5 {', '.join(f'{k} {v*100:+.1f}%' for k, v in top.tail(5).items())}")
    drop5 = [c for c in top.head(5).index]
    r, _ = score(level_weights(D, lvl, [c for c in D["U"] if c not in drop5]), D["r_tr"])
    print(f"   without the top-5 contributors (book rebuilt without them): gross SR {r['gross_sr']:+.2f} ann {r['ann_ret']*100:+.2f}%")
    side = (held.where(held > 0, 0) * D["r_tr"].fillna(0)).sum().sum(), (held.where(held < 0, 0) * D["r_tr"].fillna(0)).sum().sum()
    print(f"   long side {side[0]*100:+.2f}%, short side {side[1]*100:+.2f}% of the fit total")

    dec = W.loc[D["idx"][::HOLD]]
    sgn = np.sign(dec)
    ac1 = [(sgn.iloc[i] * sgn.iloc[i + 12]).where((sgn.iloc[i] != 0) & (sgn.iloc[i + 12] != 0)).mean()
           for i in range(len(sgn) - 12)]
    rk = [dec.iloc[i].corr(dec.iloc[i + 12], method="spearman") for i in range(len(dec) - 12)]
    print(f"\nK3 persistence: P(same side 12 months later) {np.nanmean(ac1)*0.5+0.5:.2f}; rank corr of weights at 12 months "
          f"{np.nanmean(rk):.2f}; at 1 month {np.nanmean([dec.iloc[i].corr(dec.iloc[i+1], method='spearman') for i in range(len(dec)-1)]):.2f}")

    # K4: C4's live z book on the same panel (band, gross cap), the C4 book's own construction
    from scripts.cef import band_frontier as bf
    from scripts.cef import c4_families as c4
    from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS
    m = c4.declared_mask(pd.read_csv(c4.FROZEN).ticker.tolist(), "M1M2")[D["U"]]
    T, _ = bf.build_targets(universe=D["U"], source=c4.FAM_SRC, mask=m)
    T = T.loc[:ac.FIT_END]
    ac.assert_fit(T)
    Hz = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS).reindex(D["idx"]).fillna(0.0)
    rz, _ = score(Hz, D["r_tr"])
    a, b = rz["pnl"], pnl
    both = (a.index >= max(a.ne(0).idxmax(), b.ne(0).idxmax()))
    a, b = a[both], b[both]
    rho = a.corr(b)
    rho21 = a.rolling(21).sum()[20::21].corr(b.rolling(21).sum()[20::21])
    print(f"\nK4 C4 z book (band {BAND_WIDTH}, cap {MAX_GROSS_STRESS}) on this yfinance TR leg: gross SR {rz['gross_sr']:+.2f} "
          f"ann {rz['ann_ret']*100:+.2f}% vol {rz['vol']*100:.2f}%  [C4's committed fit used CRSP returns: 1.217]")
    print(f"   corr(daily P&L, z book vs level book) {rho:+.3f}; 21-session sums {rho21:+.3f}")
    sa, sb = a / a.std(), b / b.std()
    comb = (sa + sb) / 2
    print(f"   equal-risk combination: SR {comb.mean()/comb.std()*np.sqrt(252):+.2f} vs z alone {a.mean()/a.std()*np.sqrt(252):+.2f}")
    # the level signal's increment inside the z book's own cross-section
    rho_sig = pd.Series([lvl.loc[d].corr(D["z"].loc[d], method="spearman") for d in D["idx"][::HOLD]]).mean()
    print(f"   mean cross-sectional rank corr(level, z) on decision dates {rho_sig:+.2f}")

    etf = pd.read_parquet(ac.WT / "data" / "etf_daily.parquet")
    spy = pd.read_parquet(ac.WT / "data" / "benchmarks" / "spy_daily.parquet")["adj_close"].pct_change()
    spy.index = pd.to_datetime(spy.index)
    hyg = etf[etf.ticker == "HYG"].set_index("date")["ret_total"]
    X = pd.DataFrame({"spy": spy, "spy_l1": spy.shift(1), "hyg": hyg, "hyg_l1": hyg.shift(1)}).reindex(pnl.index)
    d = pd.concat([pnl.rename("p"), X], axis=1).dropna()
    d = d[d.p != 0]
    Z = np.column_stack([np.ones(len(d)), d[X.columns].to_numpy()])
    beta = np.linalg.lstsq(Z, d.p.to_numpy(), rcond=None)[0]
    e = d.p.to_numpy() - Z @ beta
    n = len(e)
    S = (Z * e[:, None]).T @ (Z * e[:, None]) / n
    for L in range(1, 6):
        G = (Z[L:] * e[L:, None]).T @ (Z[:-L] * e[:-L, None]) / n
        S += (1 - L / 6) * (G + G.T)
    Q = np.linalg.inv(Z.T @ Z / n)
    se = np.sqrt(np.diag(Q @ S @ Q / n))
    print(f"\nK5 factor loadings ({d.index[0].date()} -> {d.index[-1].date()}, SPY from {spy.dropna().index[0].date()}): "
          f"SPY sum {beta[1]+beta[2]:+.3f}, HYG sum {beta[3]+beta[4]:+.3f}; alpha {beta[0]*252*100:+.2f}%/yr "
          f"(NW t {beta[0]/se[0]:+.2f})")

    fz = pd.read_csv(c4.FROZEN).set_index("ticker")
    short = held.where(held < 0, 0).abs().sum()
    etb = fz["easy_to_borrow"].reindex(short.index).astype(bool)
    print(f"\nK6 short side on the frozen read {fz['read_utc'].iloc[0]}: {short[etb].sum()/short.sum():.0%} of short weight-days in "
          f"names then easy-to-borrow; top shorts: {', '.join(short.sort_values(ascending=False).head(6).index)}")

    rng = np.random.default_rng(SEED)
    plac = []
    for _ in range(20):
        L2 = lvl.copy()
        for fam, cols in D["grp"].groupby(D["grp"]).groups.items():
            cols = list(cols)
            perm = rng.permutation(len(cols))
            L2[cols] = lvl[cols].to_numpy()[:, perm]
        r, _ = score(level_weights(D, L2), D["r_tr"])
        plac.append(r["gross_sr"])
    print(f"\nK7 placebo (another fund's level, same family and date; 20 draws): gross SR mean {np.mean(plac):+.2f}, "
          f"max {np.max(plac):+.2f}; the real book {res['gross_sr']:+.2f} ranks above {sum(p < res['gross_sr'] for p in plac)} of 20")
    # K8: Fama-MacBeth rank IC, level residualised on z within each date
    y = ac.cs_demean(ac.fwd(D["r_tr"], 2, 22).where(elig), D["grp"])
    zz = ac.cs_demean(D["z"].where(elig), D["grp"])
    ics = {}
    for d in D["idx"][::HOLD]:
        v = pd.DataFrame({"l": lvl.loc[d], "z": zz.loc[d], "y": y.loc[d]}).dropna()
        if len(v) < ac.MIN_NAMES:
            continue
        bz = (v.l @ v.z) / (v.z @ v.z) if (v.z @ v.z) > 0 else 0.0
        v["lr"] = v.l - bz * v.z
        ics[d] = v.lr.corr(v.y, method="spearman")
    ic = pd.Series(ics)
    print(f"\nK8 Fama-MacBeth IC (level resid. on z vs 21-session fwd TR): mean {ic.mean():+.4f}, NW t {ac.nw_t(ic, 3):+.2f}, "
          f"months {len(ic)}, negative in {(ic < 0).mean():.0%}")
    for lab, a0, b0 in (("2005-09", "2005", "2009-12-31"), ("2010-14", "2010", "2014-12-31"),
                        ("2015-19", "2015", "2019-12-31"), ("2020-22", "2020", "2022-12-31")):
        x = ic[(ic.index >= a0) & (ic.index <= b0)]
        print(f"   {lab}: mean IC {x.mean():+.4f} (NW t {ac.nw_t(x, 3):+.2f}, {len(x)} months)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
