"""R1 -- does the deployed CEF discount signal's WITHIN-GROUP IC change with each
group's own macro state? Zero-trial screen (a preview of C2 Part D), 2026-10-26.

    cd <SCRATCH>/tree && python3 -B <SCRATCH>/r1_macro_state/r1_macro_state.py --prep   # once: copy raw rows
    cd <SCRATCH>/tree && python3 -B <SCRATCH>/r1_macro_state/r1_macro_state.py          # the screen

The declared design, controls and verdict rule are in NOTE.md beside this file,
written BEFORE the first run. Nothing here chooses a parameter: every constant
below is the declared one.

WHAT IS REUSED (imported, never copied)
---------------------------------------
* W4 (`scripts/cef/w4_artifacts.py`): `Data` (the deployed 13-name set M_dep, z,
  total returns, the non-overlapping grids), `fwd` (closes t+1 -> t+3), `ic_series`
  (per-date Spearman), `nw_t`, `_assert_fit` (raises on any 2023+ index).
* band_frontier: `build_panel` (the frozen-spec z) and `total_returns` for the
  17-name WIDE set, exactly as W4's 17-name reconciliation builds it.
* W10 Part B: the group labels (static `grp` of cef_universe.csv) and the
  within-group construction (Spearman inside a group is invariant to demeaning
  z and F inside it, so IC_{g,t} below IS W10's within part against the
  within-group forward return, one group at a time).

ALIGNMENT (H7), stated and asserted
-----------------------------------
* z_t: discount at t standardised by moments through t-1 (build_panel).
* F_t: total return close t+1 -> close t+3 (shift(2) convention).
* state_t: the last observation of X dated <= the PREVIOUS session t-1 (as-of,
  then shift(1)), ranked against every such value from 2005-01-03 to t. Every
  element of that window is dated <= t-1. `state_series` asserts source date < t
  on every state and re-derives the states from observations truncated at a
  cut date, asserting that nothing before the cut moves (a runtime no-lookahead
  check, not a comment).
* vol state: realised vol of W4's equal-weight 13-name total-return index over the
  63 sessions THROUGH s, fed to the same machinery, so at t it is through t-1.

NO SILENT FALLBACKS. A missing raw file raises naming `--prep`; a stale
observation gives no state (counted); a cell with no statistic is reported as
such, never filled.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TREE = HERE.parent / "tree"
sys.path.insert(0, str(TREE))

from scripts.cef.band_frontier import SAMPLE_START, build_panel, total_returns  # noqa: E402
from scripts.cef.spec import MIN_NAMES, UNIVERSE, summary  # noqa: E402
from scripts.cef.w4_artifacts import (  # noqa: E402
    DEPLOYED_WIN, ERAS, FIT_END, NW_LAGS, Data, _assert_fit, fwd, ic_series, nw_t,
)

RAW = HERE / "raw"
CACHE = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/.claude/worktrees/"
             "research-core-signal/results/cef/w10/_cache_w10/group_observables.parquet")
FIT_END_TS = pd.Timestamp(FIT_END)
V6_EXTRA = ["NAD", "NEA", "NVG", "NZF"]          # v6 17-name set = spec 13 + these (W4 reconciliation)

# ---- declared constants (NOTE.md) ----
WIN_START = pd.Timestamp(SAMPLE_START)           # expanding window start for every state
MIN_HIST = 252                                   # sessions of non-missing X' before a state exists
STALE_DAILY, STALE_WEEKLY = 7, 10                # calendar days at t-1
MIN_GROUP_NAMES = 2
BLOCK, N_DRAWS, SEED = 63, 20, 20261026
T_BONF, T_CTRL = 2.58, 2.0
RV_WIN, RV_MINP = 63, 40                         # W4's realised-vol definition
CUT_CHECK = pd.Timestamp("2015-06-30")           # truncation date for the runtime no-lookahead check
LABELS = {0: "bottom", 1: "middle", 2: "top"}


# =========================================================================== raw data

def prep():
    """Copy the fit-window rows of the repo fetcher's SIFMA and OFR repo series
    from its research cache into raw/ (read-only on the cache). The cache was
    written 2026-10-12 by scripts/data/fetch_group_observables.py; sifma.org is not
    on this task's fetch allowlist, so nothing is re-fetched."""
    if not CACHE.exists():
        raise FileNotFoundError(f"{CACHE} is missing; it is the only source of SIFMA allowed here")
    c = pd.read_parquet(CACHE)
    RAW.mkdir(exist_ok=True)
    lines = [f"copied {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC from {CACHE}"]
    for s in ("sifma", "repo_tri_corp", "hy_oas"):
        x = c[(c.series == s) & (pd.to_datetime(c.date) <= FIT_END_TS)].sort_values("date")
        if x.empty:
            raise ValueError(f"cache has no fit-window rows for {s}")
        out = RAW / f"{s}_le2022.csv"
        x.to_csv(out, index=False)
        lines.append(f"{out.name}: {len(x)} rows {x.date.min()}..{x.date.max()}; source(s) "
                     f"{sorted(x.source.unique())}; fetched_at_utc {sorted(x.fetched_at_utc.unique())}")
    (RAW / "PROVENANCE.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def _raw(name: str) -> pd.Series:
    p = RAW / f"{name}_le2022.csv"
    if not p.exists():
        raise FileNotFoundError(f"{p} is missing; run this script with --prep first")
    x = pd.read_csv(p, parse_dates=["date"])
    s = x.set_index("date")["value"].astype(float).sort_index()
    if s.index.duplicated().any():
        raise ValueError(f"{name}: duplicated dates")
    return s[s.index <= FIT_END_TS]


def observables() -> dict:
    """Each declared observable as a raw dated series, truncated to <= 2022-12-30."""
    sp = pd.read_parquet(TREE / "data/spreads_daily.parquet")
    sp = sp[sp.date <= FIT_END_TS]
    w = sp.pivot_table(index="date", columns="series", values="value").sort_index()
    need = ["bamlh0a0hym2", "bamlh0a3hycey", "bamlh0a1hybbey"]
    miss = [c for c in need if c not in w.columns]
    if miss:
        raise ValueError(f"spreads_daily has no {miss}")
    hy = w["bamlh0a0hym2"].dropna()
    both = w[["bamlh0a3hycey", "bamlh0a1hybbey"]].dropna()
    ccc_bb = (both["bamlh0a3hycey"] - both["bamlh0a1hybbey"])
    sif, repo = _raw("sifma"), _raw("repo_tri_corp")
    # second path for HY OAS: the fetcher's R2/FRED splice vs data/spreads_daily (crsp-mirror/FRED)
    hy2 = _raw("hy_oas")
    j = pd.concat([hy, hy2], axis=1, join="inner").dropna()
    xcheck = dict(n=int(len(j)), max_abs_diff=float((j.iloc[:, 0] - j.iloc[:, 1]).abs().max()))
    full = pd.read_parquet(TREE / "data/spreads_daily.parquet", columns=["date"])
    meta = {"spreads_daily_last_date": str(full.date.max().date()),
            "hy_oas_xcheck_vs_fetcher_cache": xcheck,
            "sifma_last_used": str(sif.index.max().date()),
            "repo_first": str(repo.index.min().date())}
    return dict(obs={"hy_oas": (hy, STALE_DAILY), "ccc_bb_ey": (ccc_bb.dropna(), STALE_DAILY),
                     "sifma": (sif, STALE_WEEKLY), "repo_tri_corp": (repo, STALE_DAILY)}, meta=meta)


# =========================================================================== states

def _aligned(obs: pd.Series, sessions: pd.DatetimeIndex, stale: int):
    """X'_t = last observation dated <= previous session; NaN if older than `stale`
    calendar days at t-1. Returns (value, source_date) on `sessions`."""
    o = obs.dropna().sort_index()
    left = pd.DataFrame({"s": sessions})
    right = pd.DataFrame({"d": o.index, "v": o.to_numpy()})
    m = pd.merge_asof(left, right, left_on="s", right_on="d", direction="backward")
    v = pd.Series(m.v.to_numpy(), index=sessions)
    d = pd.Series(m.d.to_numpy(), index=sessions)
    prev = pd.Series(sessions, index=sessions).shift(1)
    v, d = v.shift(1), d.shift(1)                       # dated <= t-1
    too_old = (prev - d).dt.days > stale
    v[too_old] = np.nan
    d[too_old] = pd.NaT
    return v, d, int(too_old.sum())


def _terciles(xp: pd.Series) -> tuple[pd.Series, pd.Series]:
    x = xp[xp.index >= WIN_START]
    pct = x.expanding(min_periods=MIN_HIST).rank(pct=True)
    st = pd.Series(np.where(pct.isna(), np.nan, np.where(pct <= 1 / 3, 0, np.where(pct <= 2 / 3, 1, 2))),
                   index=x.index)
    return st, pct


def state_series(obs: pd.Series, sessions: pd.DatetimeIndex, stale: int, name: str):
    """State 0/1/2 (bottom/middle/top tercile) on `sessions`, with the runtime
    no-lookahead assertions described in the module docstring."""
    xp, src, n_stale = _aligned(obs, sessions, stale)
    st, pct = _terciles(xp)
    have = st.notna()
    s_src = src.reindex(st.index)
    if not (s_src[have] < st.index[have]).all():
        raise AssertionError(f"{name}: a state uses an observation dated on or after its own date")
    # truncation check: states up to the first session after CUT_CHECK must not change
    # when every observation after CUT_CHECK is deleted
    nxt = sessions[sessions > CUT_CHECK][0]
    xp2, _, _ = _aligned(obs[obs.index <= CUT_CHECK], sessions[sessions <= nxt], stale)
    st2, _ = _terciles(xp2)
    a, b = st.loc[:nxt], st2.loc[:nxt]
    if not a.equals(b):
        raise AssertionError(f"{name}: states before {nxt.date()} move when later observations are removed")
    info = dict(first_state=str(st[have].index.min().date()) if have.any() else None,
                n_stale_dropped=n_stale,
                share=[float((st == k).sum() / have.sum()) for k in (0, 1, 2)] if have.any() else None)
    return st, pct, info


# =========================================================================== statistics

def welch(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or len(b) < 3:
        return np.nan
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return (a.mean() - b.mean()) / se if se > 0 else np.nan


def ols(y: np.ndarray, X: np.ndarray, nw_lags: int | None = None):
    """OLS coefficients with HC1 (nw_lags None) or Newey-West (Bartlett) covariance."""
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    u = X * e[:, None]
    if nw_lags is None:
        S = u.T @ u * n / (n - k)
    else:
        S = u.T @ u
        for L in range(1, nw_lags + 1):
            w = 1 - L / (nw_lags + 1)
            G = u[L:].T @ u[:-L]
            S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    return b, V


def diff_t(b, V, i, j):
    d = b[i] - b[j]
    v = V[i, i] + V[j, j] - 2 * V[i, j]
    return d, d / np.sqrt(v) if v > 0 else np.nan


def split_stats(ic: pd.Series, st: pd.Series) -> dict:
    """Per-tercile mean IC and Delta = top - bottom (Welch t; NW-5 t beside)."""
    s = st.reindex(ic.index)
    ok = s.notna()
    ic, s = ic[ok], s[ok]
    out = {"n": int(len(ic))}
    for k in (0, 1, 2):
        x = ic[s == k]
        out[f"n_{LABELS[k]}"] = int(len(x))
        out[f"ic_{LABELS[k]}"] = float(x.mean()) if len(x) else np.nan
        out[f"t_{LABELS[k]}"] = float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))) if len(x) > 2 else np.nan
    top, bot = ic[s == 2].to_numpy(), ic[s == 0].to_numpy()
    out["delta"] = float(top.mean() - bot.mean()) if len(top) and len(bot) else np.nan
    out["t_welch"] = float(welch(top, bot))
    tb = ic[(s == 0) | (s == 2)]
    if len(top) >= 3 and len(bot) >= 3:
        X = np.column_stack([np.ones(len(tb)), (s[tb.index] == 2).to_numpy(float)])
        b, V = ols(tb.to_numpy(), X, NW_LAGS)
        out["t_nw"] = float(b[1] / np.sqrt(V[1, 1]))
    else:
        out["t_nw"] = np.nan
    return out


def shuffle_rank(ic: pd.Series, st: pd.Series, real_delta: float) -> dict:
    """Control 2: permute 63-date blocks of the cell's own state labels."""
    s = st.reindex(ic.index)
    ok = s.notna()
    ic, lab = ic[ok], s[ok].to_numpy()
    n = len(lab)
    blocks = [np.arange(i, min(i + BLOCK, n)) for i in range(0, n, BLOCK)]
    ds = []
    for k in range(N_DRAWS):
        rng = np.random.default_rng([SEED, k])
        order = rng.permutation(len(blocks))
        perm = np.concatenate([lab[blocks[o]] for o in order])
        top, bot = ic.to_numpy()[perm == 2], ic.to_numpy()[perm == 0]
        ds.append(top.mean() - bot.mean() if len(top) and len(bot) else np.nan)
    ds = np.array(ds)
    return dict(n_blocks=len(blocks), draws=[float(x) for x in ds],
                beats=int(np.sum(np.abs(ds) < abs(real_delta))) if np.isfinite(real_delta) else None,
                draw_abs_max=float(np.nanmax(np.abs(ds))), draw_abs_mean=float(np.nanmean(np.abs(ds))))


def joint(ic: pd.Series, sx: pd.Series, sv: pd.Series) -> dict:
    """Control 3: IC on [1, X_top, X_bot, V_top, V_bot]; HC1 headline, NW-5 beside."""
    a, b_ = sx.reindex(ic.index), sv.reindex(ic.index)
    ok = a.notna() & b_.notna()
    y, a, b_ = ic[ok], a[ok], b_[ok]
    X = np.column_stack([np.ones(len(y)), (a == 2), (a == 0), (b_ == 2), (b_ == 0)]).astype(float)
    if np.linalg.matrix_rank(X) < X.shape[1]:
        return dict(n=int(len(y)), note="design matrix rank-deficient: some X x V cells are empty")
    out = {"n": int(len(y))}
    for lab, L in (("hc1", None), ("nw5", NW_LAGS)):
        bb, V = ols(y.to_numpy(), X, L)
        dx, tx = diff_t(bb, V, 1, 2)
        dv, tv = diff_t(bb, V, 3, 4)
        out[f"x_delta"], out[f"x_t_{lab}"] = float(dx), float(tx)
        out[f"v_delta"], out[f"v_t_{lab}"] = float(dv), float(tv)
    cells = {}
    for i in (0, 1, 2):
        for j in (0, 1, 2):
            m = (a == i) & (b_ == j)
            cells[f"X{LABELS[i][0]}V{LABELS[j][0]}"] = (int(m.sum()), float(y[m].mean()) if m.any() else None)
    out["cells"] = cells
    out["same_tercile_share"] = float((a == b_).mean())
    # univariate vol split on the same sample, for comparison
    vt, vb = y[b_ == 2].to_numpy(), y[b_ == 0].to_numpy()
    out["v_delta_univariate"] = float(vt.mean() - vb.mean()) if len(vt) and len(vb) else np.nan
    out["v_t_univariate"] = float(welch(vt, vb))
    return out


# =========================================================================== universes

def universes(D: Data):
    """DEP13 (W4's deployed set) and WIDE17 (v6 17 names, z present, >= min_names)."""
    U13 = list(D.U)
    v6 = U13 + V6_EXTRA
    p6 = build_panel(end=FIT_END, universe=v6)
    _assert_fit(p6["px"])
    extra_dates = p6["px"].index[(p6["px"].index >= WIN_START)].difference(D.idx)
    z6 = p6["z"][v6].reindex(D.idx)
    r6 = total_returns(p6["ret"][v6].reindex(D.idx))
    # the 13 names' z and total return must be identical in the 17-name build (z is per-name)
    dz = (z6[U13] - D.z).abs().max().max()
    dr = (r6[U13] - D.r_tr).abs().max().max()
    if not (dz == 0 or np.isnan(dz)) or not (dr < 1e-15 or np.isnan(dr)):
        raise AssertionError(f"17-name build differs from W4 on the 13 names: z {dz}, r {dr}")
    if not ((z6[U13].isna() == D.z.isna()).all().all()):
        raise AssertionError("17-name build has a different z-availability pattern on the 13 names")
    M17 = z6.notna() & (z6.notna().sum(axis=1) >= MIN_NAMES).to_numpy()[:, None]
    g = pd.read_csv(TREE / "data/cef/cef_universe.csv").set_index("ticker")["grp"]
    grp17 = {t: g[t] for t in v6}
    sealed = sorted(set(g.index) - set(v6))
    F13, F17 = fwd(D.r_tr, *DEPLOYED_WIN), fwd(r6, *DEPLOYED_WIN)
    _assert_fit(D.z, D.r_tr, F13, z6, r6, F17)
    U = {"DEP13": dict(z=D.z, F=F13, M=D.M_dep, grp=D.grp),
         "WIDE17": dict(z=z6, F=F17, M=M17, grp=grp17)}
    meta = dict(extra_17name_dates_not_in_13_calendar=int(len(extra_dates)), sealed_names_excluded=len(sealed),
                z_check_max_abs_diff=float(0.0 if np.isnan(dz) else dz))
    return U, meta


def group_ic(u: dict, g: str, dates, min_n=MIN_GROUP_NAMES) -> pd.Series:
    cols = [t for t in u["z"].columns if u["grp"][t] == g]
    ic = ic_series(u["z"][cols], u["F"][cols], u["M"][cols], dates, min_n=min_n)
    _assert_fit(ic)
    return ic


# =========================================================================== main

PRIMARY = {"hy": "hy_oas", "multi": "hy_oas", "muni": "sifma"}
MISMATCH = {"hy": "sifma", "multi": "sifma", "muni": "hy_oas"}
VARIANT = {"hy": "ccc_bb_ey", "multi": "repo_tri_corp"}
CELLS = [("DEP13", "multi"), ("DEP13", "hy"), ("WIDE17", "multi"), ("WIDE17", "hy"), ("WIDE17", "muni")]


def fmt(r: dict) -> str:
    return (f"n {r['n']:5d} | bot {r['ic_bottom']:+.4f} ({r['n_bottom']:4d}, t {r['t_bottom']:+.2f}) "
            f"mid {r['ic_middle']:+.4f} ({r['n_middle']:4d}) top {r['ic_top']:+.4f} ({r['n_top']:4d}, "
            f"t {r['t_top']:+.2f}) | Delta {r['delta']:+.4f} t_welch {r['t_welch']:+.2f} t_nw {r['t_nw']:+.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep", action="store_true")
    a = ap.parse_args()
    if a.prep:
        prep()
        return
    print(summary())
    print(f"R1 macro-state screen -- FIT PERIOD ONLY (<= {FIT_END}); 2023+ sealed. Run "
          f"{pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC. Zero trials.")
    P = pd.read_parquet(TREE / "data/cef/cef_prices.parquet", columns=["date"])
    N = pd.read_parquet(TREE / "data/cef/cef_nav.parquet", columns=["date"])
    print(f"panels: cef_prices last {P.date.max().date()}, cef_nav last {N.date.max().date()} (read-only; "
          f"truncated to {FIT_END} before use)")
    D = Data()
    U, umeta = universes(D)
    O = observables()
    print("universe meta:", umeta)
    print("observable meta:", O["meta"])
    sessions = D.p["px"].index                          # full 13-name session calendar through FIT_END
    _assert_fit(sessions)

    # states
    states, sinfo = {}, {}
    for k, (obs, stale) in O["obs"].items():
        st, pct, info = state_series(obs, sessions, stale, k)
        states[k], sinfo[k] = st, info
    ew = D.r_tr.mean(axis=1)
    rv = ew.rolling(RV_WIN, min_periods=RV_MINP).std() * np.sqrt(252)   # through s; machinery shifts to t-1
    _assert_fit(rv)
    st, pct, info = state_series(rv.dropna(), sessions, STALE_DAILY, "vol")
    states["vol"], sinfo["vol"] = st, info
    print("\nstates (first state date, stale observations dropped, share bottom/middle/top):")
    for k, v in sinfo.items():
        print(f"  {k:<14} {v}")
    # how alike are the observables' states? (fit window, every session with both)
    print("  share of sessions in the same tercile:", {f"{x}~{y}": round(float((states[x] == states[y])[
        states[x].notna() & states[y].notna()].mean()), 3) for x, y in
        (("hy_oas", "vol"), ("sifma", "vol"), ("hy_oas", "sifma"), ("ccc_bb_ey", "hy_oas"),
         ("repo_tri_corp", "sifma"))})

    out = {"run_utc": f"{pd.Timestamp.now(tz='UTC'):%Y-%m-%dT%H:%MZ}", "fit_end": FIT_END,
           "universe_meta": umeta, "observable_meta": O["meta"], "states": sinfo, "cells": {}}

    # regression checks against W10 (machinery, not the question)
    m4 = group_ic(U["DEP13"], "multi", D.G0, min_n=4)
    print(f"\nregression check vs W10 item 6: DEP13 multi within IC (>= 4 names) phase 0 "
          f"{m4.mean():+.4f} (t {m4.mean() / m4.std(ddof=1) * np.sqrt(len(m4)):.2f}, n {len(m4)}); "
          f"W10 reported -0.066 (t -2.78)")
    h2 = group_ic(U["DEP13"], "hy", D.G0)
    print(f"regression check vs W10 item 6: DEP13 hy pair, share IC = -1 (richer name underperforms) "
          f"{(h2 < 0).mean():.3f} on {len(h2)} dates; W10 reported 0.520 of 271")
    out["regression_checks"] = dict(dep13_multi_min4=float(m4.mean()), dep13_hy_share=float((h2 < 0).mean()),
                                    dep13_hy_n=int(len(h2)))

    print("\nunconditional within-group IC (min 2 names), phase 0 / phase 1:")
    for un, u in U.items():
        for g in ("multi", "hy", "muni", "loan"):
            for ph, G in (("p0", D.G0), ("p1", D.G1)):
                ic = group_ic(u, g, G)
                if len(ic) < 10:
                    print(f"  {un:<7}{g:<6}{ph}: {len(ic)} dates -- no statistic")
                    continue
                print(f"  {un:<7}{g:<6}{ph}: n {len(ic):5d} IC {ic.mean():+.4f} "
                      f"t {ic.mean() / ic.std(ddof=1) * np.sqrt(len(ic)):+.2f} NW {nw_t(ic):+.2f} "
                      f"first {ic.index.min().date()}")

    print("\n" + "=" * 110 + "\nPRIMARY CELLS\n" + "=" * 110)
    for un, g in CELLS:
        u = U[un]
        res = {}
        for ph, G in (("p0", D.G0), ("p1", D.G1)):
            ic = group_ic(u, g, G)
            r = {"own": split_stats(ic, states[PRIMARY[g]]),
                 "mismatch": split_stats(ic, states[MISMATCH[g]]),
                 "vol_univariate": split_stats(ic, states["vol"])}
            if g in VARIANT:
                r["variant"] = split_stats(ic, states[VARIANT[g]])
            if ph == "p1":
                # POST-HOC (added after the first run, NOT declared, NOT used by the verdict):
                # the joint regression on the other half of the grid, as a stability read
                r["joint_posthoc"] = joint(ic, states[PRIMARY[g]], states["vol"])
            if ph == "p0":
                r["shuffle"] = shuffle_rank(ic, states[PRIMARY[g]], r["own"]["delta"])
                r["joint"] = joint(ic, states[PRIMARY[g]], states["vol"])
                r["joint_mismatch"] = joint(ic, states[MISMATCH[g]], states["vol"])
                eras = {}
                for lab, a0, b0 in ERAS:
                    e = ic.loc[a0:b0]
                    if len(e) >= 10:
                        eras[lab] = split_stats(e, states[PRIMARY[g]])
                r["eras"] = eras
            res[ph] = r
        out["cells"][f"{un}|{g}"] = res
        p0 = res["p0"]
        print(f"\n--- {un} {g}   own = {PRIMARY[g]}, mismatch = {MISMATCH[g]}, variant = {VARIANT.get(g, '--')}")
        print(f"  own      p0  {fmt(p0['own'])}")
        print(f"  own      p1  {fmt(res['p1']['own'])}")
        print(f"  mismatch p0  {fmt(p0['mismatch'])}")
        print(f"  mismatch p1  {fmt(res['p1']['mismatch'])}")
        if "variant" in p0:
            print(f"  variant  p0  {fmt(p0['variant'])}")
            print(f"  variant  p1  {fmt(res['p1']['variant'])}")
        print(f"  vol      p0  {fmt(p0['vol_univariate'])}")
        sh = p0["shuffle"]
        print(f"  shuffle  p0  real |Delta| {abs(p0['own']['delta']):.4f} beats {sh['beats']} of {N_DRAWS} draws "
              f"({sh['n_blocks']} blocks); draw |Delta| mean {sh['draw_abs_mean']:.4f}, max {sh['draw_abs_max']:.4f}")
        j = p0["joint"]
        if "note" in j:
            print(f"  joint    p0  {j['note']}")
        else:
            print(f"  joint    p0  n {j['n']}: own top-bottom {j['x_delta']:+.4f} (t HC1 {j['x_t_hc1']:+.2f}, NW "
                  f"{j['x_t_nw5']:+.2f}); vol top-bottom {j['v_delta']:+.4f} (t HC1 {j['v_t_hc1']:+.2f}, NW "
                  f"{j['v_t_nw5']:+.2f}); univariate vol {j['v_delta_univariate']:+.4f} (t {j['v_t_univariate']:+.2f}); "
                  f"same-tercile share {j['same_tercile_share']:.3f}")
            print("               cells X(own)xV(vol) (n, mean IC): " + "  ".join(
                f"{k}:{v[0]},{'' if v[1] is None else f'{v[1]:+.3f}'}" for k, v in j["cells"].items()))
        jp = res["p1"]["joint_posthoc"]
        if "note" not in jp:
            print(f"  joint    p1  POST-HOC, not in the verdict: own top-bottom {jp['x_delta']:+.4f} (t HC1 "
                  f"{jp['x_t_hc1']:+.2f}); vol top-bottom {jp['v_delta']:+.4f} (t HC1 {jp['v_t_hc1']:+.2f})")
        jm = p0["joint_mismatch"]
        if "note" not in jm:
            print(f"  joint-mismatch p0: mismatch top-bottom {jm['x_delta']:+.4f} (t HC1 {jm['x_t_hc1']:+.2f}); vol "
                  f"{jm['v_delta']:+.4f} (t {jm['v_t_hc1']:+.2f})")
        print("  eras (own, p0): " + " | ".join(
            f"{k}: n {v['n']} Delta {v['delta']:+.3f} (t {v['t_welch']:+.2f}; nb {v['n_bottom']}, nt {v['n_top']})"
            for k, v in p0["eras"].items()))

    # ---- verdict, mechanically from the declared rule ----
    print("\n" + "=" * 110 + "\nVERDICT (declared rule)\n" + "=" * 110)
    verdicts = {}
    for un, g in CELLS:
        r = out["cells"][f"{un}|{g}"]
        p0, p1 = r["p0"], r["p1"]
        own = p0["own"]
        sgn = np.sign(own["delta"])
        a_ = abs(own["t_welch"]) >= T_BONF
        b_ = abs(p0["mismatch"]["t_welch"]) < T_CTRL and abs(p0["mismatch"]["delta"]) < abs(own["delta"])
        c_ = p0["shuffle"]["beats"] == N_DRAWS
        j = p0["joint"]
        d_ = ("note" not in j) and np.sign(j["x_delta"]) == sgn and abs(j["x_t_hc1"]) >= T_CTRL
        contra = []
        if np.sign(p1["own"]["delta"]) == -sgn and abs(p1["own"]["t_welch"]) >= T_CTRL:
            contra.append("phase 1")
        other = "WIDE17" if un == "DEP13" else "DEP13"
        if f"{other}|{g}" in out["cells"]:
            o = out["cells"][f"{other}|{g}"]["p0"]["own"]
            if np.sign(o["delta"]) == -sgn and abs(o["t_welch"]) >= T_CTRL:
                contra.append(other)
        if "variant" in p0 and np.sign(p0["variant"]["delta"]) == -sgn and abs(p0["variant"]["t_welch"]) >= T_CTRL:
            contra.append("variant")
        e_ = not contra
        vol_sig = ("note" not in j) and abs(j["v_t_hc1"]) >= T_CTRL
        if a_ and b_ and c_ and d_ and e_:
            v = "PROMISING"
        elif a_ and not d_ and vol_sig:
            v = "ARTIFACT"
        else:
            v = "NOTHING"
        verdicts[f"{un}|{g}"] = dict(a=bool(a_), b=bool(b_), c=bool(c_), d=bool(d_), e=bool(e_),
                                     contradictions=contra, vol_sig=bool(vol_sig), verdict=v)
        print(f"  {un:<7}{g:<6} (a) {a_!s:<5} (b) {b_!s:<5} (c) {c_!s:<5} (d) {d_!s:<5} (e) {e_!s:<5} "
              f"vol_sig {vol_sig!s:<5} -> {v}")
    vs = [v["verdict"] for v in verdicts.values()]
    screen = "PROMISING" if "PROMISING" in vs else ("ARTIFACT" if "ARTIFACT" in vs else "NOTHING")
    print(f"  untestable: DEP13 muni (never two eligible), loan (singleton JFR in every allowed set)")
    print(f"  SCREEN VERDICT: {screen}")
    out["verdicts"], out["screen_verdict"] = verdicts, screen
    (HERE / "r1_results.json").write_text(json.dumps(out, indent=1, default=lambda o: None if o is None else float(o)))
    print(f"\nwrote {HERE / 'r1_results.json'}")


if __name__ == "__main__":
    main()
