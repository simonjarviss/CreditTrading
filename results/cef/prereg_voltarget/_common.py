"""Shared loaders and the per-account cap model for the vol-target pre-registration (CEF trial 53, DRAFT).

ZERO TRIALS. Every frame that reaches a statistic ends by 2022-12-30 and is asserted to (`assert_fit`).
No 2023+ return is computed by anything in this folder.

WHERE THE INPUTS COME FROM, AND WHY THEY ARE NOT IN THE REPO. The multipliers were derived by the
2026-10-28 allocation note and checked by its independent review and by the 2026-10-29 four-sleeve
note. Their fit series live in the session scratch folder (SCRATCH, passed as --scratch; there is no
default, because a guessed path would read some other series in silence):

  SCRATCH/alloc/series/{core,c4}_{pnl,H}.parquet   core v7 book (band 4.8%, cap 1.80) and C4 at the
                                                    TRIAL's 1.80 book, total return (alloc/series.py)
  SCRATCH/alloc/tables/t8_vol_grid.csv, t9_sigma_star.csv   the 2026-10-28 rule's grid and sigma*
  SCRATCH/alloc_review/core_trpr.parquet            core, total return and price only (r2_series.py)
  SCRATCH/alloc4/series/c4spec_{trpr,H}.parquet     C4 at its SPEC cap 1.90, the book paper trades and
                                                    H11 reads (series4.py, c4-step2-spec @ 6f62527)
  SCRATCH/alloc4/series/core_proxy_{tr,pr,gross}.parquet   the core before 2013-06-25 as a fixed-book
                                                    group proxy at each of 10 year-end books (proxy4.py)

C4's are CRSP-derived (licensed), so they are read, never copied into a tracked file. What this folder
writes is portfolio aggregates only.

THE CAP MODEL (the 2026-10-28 note's, per account as the review requires; SCRATCH/alloc4/common4.py).
An account holding a sleeve at multiplier m holds m x that sleeve's decided book H (decided at t). Its
gross G_t = m x sum|H_t| is capped by one uniform factor f_t = min(1, cap / G_t), which is what
`_cap_gross` and `fit_to_buying_power` do, and the P&L earned at d is f_{d-2} x m x p_d (shift(2):
decided t, filled t+1, earned t+2). The cap's feedback into the next day's band is ignored here;
`impl_fit.py` runs the exact construction through `band_frontier.band_gross_capped` to measure what
that ignores. Combined P&L = the NAV-weighted mean of the accounts (two $100k accounts: one half each).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.cef.portfolio_baseline import (HALVE_DD, HORIZON, KILL_DD,  # noqa: E402
                                            max_drawdown, path_max_drawdown, stationary_index)
from scripts.cef import spec as core_spec  # noqa: E402

FIT_END = pd.Timestamp("2022-12-30")
W1_START = pd.Timestamp("2013-06-25")      # the core's first P&L-bearing session (first position 2013-06-21)
W2_START = pd.Timestamp("2005-02-22")      # C4's first session; the core is proxied before W1_START
REPS = 10_000
SEED = 20261030
NAV = {"core": 100_000.0, "c4": 100_000.0}  # [U] each spec's capital_usd; no broker is read here


def assert_fit(*frames) -> None:
    for f in frames:
        if len(f.index) and pd.Timestamp(f.index.max()) > FIT_END:
            raise AssertionError(f"holdout leak: a frame reaches {f.index.max()}")


def need(p: Path) -> Path:
    if not p.exists():
        raise FileNotFoundError(f"missing input {p} (build it with the SCRATCH script named in _common.py)")
    return p


def c4_spec_from(branch: str = "c4-integrate") -> dict:
    """C4's frozen spec, read from git (it is not on main). Raises if git cannot show it."""
    import subprocess
    r = subprocess.run(["git", "-C", str(REPO), "show", f"{branch}:ops/specs/c4_families.frozen.json"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git show {branch}:ops/specs/c4_families.frozen.json failed: {r.stderr.strip()}")
    return json.loads(r.stdout)


def load(scratch: Path) -> dict:
    """Every series on one calendar, asserted fit-only. Keys:
    P_trial  : DataFrame core / c4 (TRIAL 1.80 book), total return  (the 2026-10-28 derivation's inputs)
    H_trial  : {core, c4} decided holdings for P_trial
    PT, PP   : DataFrame core / c4 (SPEC 1.90 book), total return / price only
    H        : {core, c4} decided holdings for PT/PP
    prox_t, prox_p, prox_g : the core's 2005-02-22..2013-06-24 fixed-book proxies (10 snapshots)"""
    A, RV, B = scratch / "alloc" / "series", scratch / "alloc_review", scratch / "alloc4" / "series"
    P_trial = pd.concat({k: pd.read_parquet(need(A / f"{k}_pnl.parquet"))["pnl"] for k in ("core", "c4")}, axis=1)
    H_trial = {k: pd.read_parquet(need(A / f"{k}_H.parquet")) for k in ("core", "c4")}
    core = pd.read_parquet(need(RV / "core_trpr.parquet"))
    c4 = pd.read_parquet(need(B / "c4spec_trpr.parquet"))
    idx = core.index
    if not (c4.index.equals(idx) and P_trial.index.equals(idx)):
        raise ValueError("the series are not on one calendar")
    PT = pd.DataFrame({"core": core["tr"], "c4": c4["tr"]})
    PP = pd.DataFrame({"core": core["pr"], "c4": c4["pr"]})
    H = {"core": H_trial["core"], "c4": pd.read_parquet(need(B / "c4spec_H.parquet"))}
    for k, h in list(H.items()) + [("c4 trial", H_trial["c4"])]:
        if not h.index.equals(idx):
            raise ValueError(f"{k}: holdings calendar differs from the P&L's")
    if set(H["core"].columns) & set(H["c4"].columns):
        raise ValueError("the core and C4 share a symbol; they cannot be two disjoint accounts")
    if (PT["core"] - P_trial["core"]).abs().max() > 1e-15:
        raise ValueError("core total-return series differ between alloc and alloc_review")
    prox_t = pd.read_parquet(need(B / "core_proxy_tr.parquet"))
    prox_p = pd.read_parquet(need(B / "core_proxy_pr.parquet"))
    prox_g = pd.read_parquet(need(B / "core_proxy_gross.parquet"))["gross"]
    assert_fit(P_trial, PT, PP, prox_t, prox_p, *H.values(), H_trial["c4"])
    for df in (P_trial, PT, PP, prox_t, prox_p):
        if df.isna().any().any():
            raise ValueError("NaN in a fit series")
    if PT["core"].loc[:W1_START - pd.Timedelta(days=1)].abs().max() != 0.0:
        raise ValueError("the core earns before W1_START; the window constant is wrong")
    G = pd.DataFrame({k: H[k].abs().sum(axis=1) for k in H})
    G_trial = pd.DataFrame({k: H_trial[k].abs().sum(axis=1) for k in H_trial})
    TU = pd.DataFrame({k: H[k].diff().abs().sum(axis=1).fillna(0.0) for k in H})
    return dict(P_trial=P_trial, H_trial=H_trial, G_trial=G_trial, PT=PT, PP=PP, H=H, G=G, TU=TU,
                prox_t=prox_t, prox_p=prox_p, prox_g=prox_g, idx=idx)


def with_proxy(D: dict, snap: str, basis: str):
    """(P, G) with the core before W1_START replaced by the fixed-book proxy at `snap`."""
    P = (D["PT"] if basis == "TR" else D["PP"]).copy()
    G = D["G"].copy()
    pt = D["prox_t"] if basis == "TR" else D["prox_p"]
    P.loc[pt.index, "core"] = pt[snap]
    G.loc[pt.index, "core"] = float(D["prox_g"][snap])
    return P, G


def account(p: pd.Series, g: pd.Series, m: float, cap: float, turn: pd.Series | None = None):
    """One account holding one sleeve at multiplier m under its own cap. Returns (pnl, f, G, turnover)."""
    G = g * m
    # A session with no decided book has nothing to cap: f = 1 there (2026-11-02). Before, it read
    # cap / inf = 0, which left the P&L unchanged (no book, no P&L) but counted the session as
    # "the cap binds". The hold book is invested on every W1 session, so its figures do not move.
    # The flatten book is flat on 56% of them, and its binding shares need this.
    f = np.minimum(1.0, cap / G.where(G > 0, np.inf)).where(G > 0, 1.0)
    pnl = p * m * f.shift(2).fillna(1.0)
    tu = None
    if turn is not None:
        tu = turn * m          # turnover of m x H; the cap's own trades are added in impl_fit.py's exact run
    return pnl, f, G, tu


def multipliers(P: pd.DataFrame, s: float, start=W1_START, end=FIT_END, b=(0.5, 0.5)):
    """The 2026-10-28 rule's combined multipliers m_k = s b_k / (sd_k sd_c) on the window, and the
    per-account ones (x combined NAV / account NAV = x2 for two $100k accounts)."""
    o = P.loc[start:end, ["core", "c4"]]
    sd = o.std().values
    U = o.values / sd
    bb = np.asarray(b, float)
    sdc = (U @ bb).std(ddof=1) * np.sqrt(252)
    m = s * bb / sd / sdc
    N = sum(NAV.values())
    return dict(core=m[0], c4=m[1]), dict(core=m[0] * N / NAV["core"], c4=m[1] * N / NAV["c4"]), sd, sdc


def ann_sr(x) -> float:
    x = np.asarray(x, float)
    return float(x.mean() / x.std(ddof=1) * np.sqrt(252))


def stats(x: pd.Series) -> dict:
    x = pd.Series(x).dropna()
    return dict(ann=float(x.mean() * 252), vol=float(x.std() * np.sqrt(252)), sr=ann_sr(x),
                mdd=float(max_drawdown(x)["mdd"]))


class Paths:
    """Common random numbers per series length: SB21 and SB63 index paths and GAUSS draws."""

    def __init__(self, reps: int = REPS, seed: int = SEED, horizon: int = HORIZON):
        self.c, self.reps, self.seed, self.h = {}, reps, seed, horizon

    def get(self, n: int):
        if n not in self.c:
            rng = np.random.default_rng(self.seed)
            self.c[n] = (stationary_index(n, self.h, self.reps, 21, rng),
                         stationary_index(n, self.h, self.reps, 63, rng),
                         rng.standard_normal((self.reps, self.h)))
        return self.c[n]


def draw(x: np.ndarray, paths: Paths, edge: str):
    """{method: reps x horizon paths} of the daily series x at zero edge (demeaned) or the fit edge."""
    x = np.asarray(x, float)
    y = x - x.mean() if edge == "zero" else x
    I21, I63, GZ = paths.get(len(y))
    return {"SB21": y[I21], "SB63": y[I63], "GAUSS": y.mean() + y.std(ddof=1) * GZ}


def odds(x: np.ndarray, paths: Paths, edge: str = "zero") -> dict:
    """{method: (P(HALVE), P(KILL))} within the horizon, HALVE not acting."""
    out = {}
    for lab, pth in draw(x, paths, edge).items():
        dd = path_max_drawdown(pth)
        out[lab] = (float((dd >= HALVE_DD).mean()), float((dd >= KILL_DD).mean()))
    return out


def worst(o: dict, i: int) -> float:
    return max(v[i] for v in o.values())
