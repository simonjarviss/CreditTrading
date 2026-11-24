"""Shared loaders for the two-account portfolio screens (PM_TWO_ACCOUNTS.md, 2026-11-02). ZERO TRIALS.

Every frame that reaches a statistic ends by 2022-12-30 and is asserted to (`assert_fit`). The
2023-01-01 time holdout is not read: the core's panels are copied with a parquet filter at the fit
end (no later row is ever materialised), and C4's come from `pm_c4_extract.py`, which cuts on read.

WHAT IS LOADED, AND THE CHECK THAT TIES IT TO THE SIZING DERIVATION.
  core  the deployed 13 (spec read through scripts/cef/spec.py: band, cap), built here by the
        canonical path band_frontier.build_targets -> band_gross_capped -> evaluate on fit-cut
        panels in SCRATCH/pm/fitcut_cef. The unit book's TR and PR P&L must reproduce
        SCRATCH/alloc_review/core_trpr.parquet (the series the trial-53 multipliers were derived
        on) to 1e-12, or this raises.
  c4    C4's T, R_tr, R_pr and opportunity aggregates from SCRATCH/pm/c4 (pm_c4_extract.py, which
        asserts its spec book equals SCRATCH/alloc4/series/c4spec_H to 1e-12). The spec book is
        band_gross_capped(T, 0.048, 1.90), C4's own spec values, read from git (c4-integrate).
  proxy the core before 2013-06-25 as the house fixed-book group proxy at each of 10 year-end
        books (SCRATCH/alloc4/series/core_proxy_*), for W2 (through 2008) only.
  factors  FF5 + UMD (Ken French) and CRSP dsf ETF returns (HYG, IEF, MUB, BKLN) from the W4
        cache (`--factor-cache`, gitignored, licensed: read, never copied). The same definitions as
        scripts/cef/portfolio_baseline._factors: credit = HYG - IEF, rates = IEF - rf,
        muni = MUB - IEF, loans = BKLN - rf.

The account model and the odds are the trial-53 helpers, imported, not copied
(results/cef/prereg_voltarget/_common.py: account, multipliers, Paths, odds, worst, stats).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (str(REPO), str(REPO / "results" / "cef" / "prereg_voltarget")):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.cef import band_frontier as bf  # noqa: E402
from scripts.cef import spec as core_spec  # noqa: E402
from _common import (HALVE_DD, KILL_DD, W1_START, W2_START, Paths, account, multipliers,  # noqa: E402,F401
                     odds, stats, worst, draw, path_max_drawdown, max_drawdown)

FIT_END = pd.Timestamp("2022-12-30")
M_CORE, M_C4 = 1.13, 1.27        # CEF trial 53 as approved 2026-11-01 (PREREG_VOLTARGET §0.A); inputs, never derived here
S_COMB = 0.0525                  # the combined target those multipliers come from (derive.py §4) [doc]
ERAS_W1 = (("2013-06..2017", "2013-06-25", "2017-12-31"), ("2018-22", "2018-01-01", "2022-12-30"))
ERAS_H5 = (("2005-09", "2005-01-01", "2009-12-31"), ("2010-14", "2010-01-01", "2014-12-31"),
           ("2015-19", "2015-01-01", "2019-12-31"), ("2020-22", "2020-01-01", "2022-12-30"))
COSTS_BP = (5, 15, 30)


def assert_fit(*frames) -> None:
    for f in frames:
        if len(f.index) and pd.Timestamp(f.index.max()) > FIT_END:
            raise AssertionError(f"holdout leak: a frame reaches {f.index.max()}")


def need(p: Path) -> Path:
    if not p.exists():
        raise FileNotFoundError(f"missing input {p}")
    return p


def c4_spec() -> dict:
    r = subprocess.run(["git", "-C", str(REPO), "show", "c4-integrate:ops/specs/c4_families.frozen.json"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git show c4-integrate:ops/specs/c4_families.frozen.json failed: {r.stderr.strip()}")
    return json.loads(r.stdout)


def cut_core(dst: Path) -> dict:
    """The live core panels copied to dst with a parquet filter at FIT_END (data/ is only read)."""
    dst.mkdir(parents=True, exist_ok=True)
    info = {}
    for name, col in (("cef_prices", "date"), ("cef_nav", "date"), ("cef_distributions", "ex_date"),
                      ("cef_splits", "ex_date")):
        d = pd.read_parquet(REPO / "data" / "cef" / f"{name}.parquet", filters=[(col, "<=", FIT_END)])
        if len(d) and pd.to_datetime(d[col]).max() > FIT_END:
            raise AssertionError(f"{name}: the filter let a later row through")
        d.to_parquet(dst / f"{name}.parquet", index=False)
        info[name] = dict(rows=len(d), last=str(pd.to_datetime(d[col]).max().date()))
    return info


def core_book(scratch: Path) -> dict:
    """The core's unit book on the fit, cached in SCRATCH/pm/core after the first build."""
    cache = scratch / "pm" / "core"
    files = {k: cache / f"{k}.parquet" for k in ("T", "R_pr", "R_tr", "nav", "z", "adv")}
    if not all(f.exists() for f in files.values()):
        cut = scratch / "pm" / "fitcut_cef"
        info = cut_core(cut)
        print("core fit-cut panels:", info, flush=True)
        bf.DATA_DIR = cut
        T, R = bf.fit_only(*bf.build_targets())
        Rtr = bf.total_returns(R)
        p = bf.build_panel()
        cache.mkdir(parents=True, exist_ok=True)
        T.to_parquet(files["T"]); R.to_parquet(files["R_pr"]); Rtr.to_parquet(files["R_tr"])
        p["nav"].loc[:FIT_END].to_parquet(files["nav"]); p["z"].loc[:FIT_END].to_parquet(files["z"])
        p["adv"].loc[:FIT_END].to_parquet(files["adv"])
    T, R, Rtr = (pd.read_parquet(files[k]) for k in ("T", "R_pr", "R_tr"))
    nav, z, adv = (pd.read_parquet(files[k]) for k in ("nav", "z", "adv"))
    assert_fit(T, R, Rtr, nav, z, adv)
    cap = float(core_spec.MAX_GROSS_STRESS)
    H = bf.band_gross_capped(T, core_spec.BAND_WIDTH, cap)
    ref = pd.read_parquet(need(scratch / "alloc_review" / "core_trpr.parquet"))
    pt, pp = bf.evaluate(H, Rtr)["pnl"], bf.evaluate(H, R)["pnl"]
    d = max(float((pt.reindex(ref.index) - ref["tr"]).abs().max()), float((pp.reindex(ref.index) - ref["pr"]).abs().max()))
    if d > 1e-12:
        raise AssertionError(f"the core unit book does not reproduce alloc_review/core_trpr: {d}")
    return dict(T=T, R_pr=R, R_tr=Rtr, H=H, nav=nav, z=z, adv=adv, cap=cap, band=float(core_spec.BAND_WIDTH),
                pnl_tr=pt, pnl_pr=pp, repro=d)


def c4_book(scratch: Path) -> dict:
    src = scratch / "pm" / "c4"
    T, Rtr, Rpr, opp = (pd.read_parquet(need(src / f"{k}.parquet")) for k in ("T", "R_tr", "R_pr", "opp"))
    assert_fit(T, Rtr, Rpr, opp)
    f = c4_spec()["frozen"]
    band, cap = float(f["band_width"]), float(f["max_gross_stress"])
    H = bf.band_gross_capped(T, band, cap)
    want = pd.read_parquet(need(scratch / "alloc4" / "series" / "c4spec_H.parquet"))
    if float((H - want).abs().max().max()) > 1e-12:
        raise AssertionError("C4 spec book differs from alloc4/series/c4spec_H")
    ser = pd.read_parquet(need(scratch / "alloc4" / "series" / "c4spec_trpr.parquet"))
    pt, pp = bf.evaluate(H, Rtr)["pnl"], bf.evaluate(H, Rpr)["pnl"]
    d = max(float((pt - ser["tr"]).abs().max()), float((pp - ser["pr"]).abs().max()))
    if d > 1e-12:
        raise AssertionError(f"C4 P&L differs from alloc4/series/c4spec_trpr: {d}")
    return dict(T=T, R_tr=Rtr, R_pr=Rpr, H=H, opp=opp, cap=cap, band=band, pnl_tr=pt, pnl_pr=pp, repro=d)


def proxy(scratch: Path) -> dict:
    B = scratch / "alloc4" / "series"
    t = pd.read_parquet(need(B / "core_proxy_tr.parquet"))
    p = pd.read_parquet(need(B / "core_proxy_pr.parquet"))
    g = pd.read_parquet(need(B / "core_proxy_gross.parquet"))["gross"]
    assert_fit(t, p)
    return dict(t=t, p=p, g=g)


def factors(cache: Path, idx: pd.DatetimeIndex) -> pd.DataFrame:
    """portfolio_baseline._factors' definitions on the W4 cache. Raises on a missing file."""
    ff = pd.read_parquet(need(cache / "ff5_umd_daily.parquet")).set_index("date")
    c = pd.read_parquet(need(cache / "crsp_dsf_w4.parquet"))
    E = c[c.ticker.isin(["HYG", "IEF", "MUB", "BKLN"])].pivot_table(index="date", columns="ticker", values="ret").reindex(idx)
    F = pd.DataFrame({"mktrf": ff["mktrf"]}).reindex(idx)
    rf = ff["rf"].reindex(idx)
    F["credit"] = E["HYG"] - E["IEF"]
    F["rates"] = E["IEF"] - rf
    F["muni"] = E["MUB"] - E["IEF"]
    F["loans"] = E["BKLN"] - rf
    assert_fit(F)
    return F


def ann(x) -> float:
    return float(np.nanmean(x) * 252)


def sr(x) -> float:
    x = pd.Series(x).dropna()
    return float(x.mean() / x.std(ddof=1) * np.sqrt(252))


class Log:
    def __init__(self):
        self.lines = []

    def __call__(self, *x):
        s = " ".join(str(v) for v in x)
        print(s, flush=True)
        self.lines.append(s)

    def write(self, path: Path):
        path.write_text("\n".join(self.lines) + "\n")


def band_dyn(T: pd.DataFrame, b: float, cap: float, m: pd.Series) -> pd.DataFrame:
    """The account's held book under `sizing_multiplier` route B with a multiplier m_t that may move
    by date: the band compares the unit target with held / m_t, `_cap_gross` acts at cap / m_t in unit
    weights, and the account holds m_t x that. It is band_frontier.band_gross_capped's loop with the
    one change, and `check_band_dyn` proves that at a constant m it reproduces
    m x band_gross_capped(T, b, cap / m), the trial-53 exact build (impl_core.py, impl_c4.py).
    m_t is decided at t from data before t (the caller asserts it); the P&L is evaluate()'s shift(2).
    Returned in ACCOUNT weights (a multiple of the account's NAV)."""
    from src.deploy.sleeves.cef_discount import _cap_gross
    if not m.index.equals(T.index) or m.isna().any() or (m <= 0).any():
        raise ValueError("m must be a positive series on T's own index")
    A, cols, mm = T.values, T.columns, m.values
    a = np.zeros(A.shape[1])
    H = np.zeros_like(A)
    for i in range(len(A)):
        u = a / mm[i]
        gap = A[i] - u
        mv = np.abs(gap) > b
        u = u.copy()
        u[mv] = A[i][mv] - np.sign(gap[mv]) * b
        w, _ = _cap_gross(pd.Series(u, index=cols), cap / mm[i])
        a = mm[i] * w.values
        H[i] = a
    return pd.DataFrame(H, index=T.index, columns=cols)


def check_band_dyn(T: pd.DataFrame, b: float, cap: float, m0: float) -> float:
    ref = m0 * bf.band_gross_capped(T, b, cap / m0)
    got = band_dyn(T, b, cap, pd.Series(m0, index=T.index))
    d = float((got - ref).abs().max().max())
    if d > 1e-12:
        raise AssertionError(f"band_dyn at constant m {m0} differs from m x band_gross_capped: {d}")
    return d


def line(H: pd.DataFrame, R: pd.DataFrame, start=W1_START, end=FIT_END) -> dict:
    """evaluate() on an account book: the P&L series and its turnover, cut to [start, end]."""
    r = bf.evaluate(H, R)
    p, t = r["pnl"].loc[start:end], r["turn_series"].loc[start:end]
    assert_fit(p, t)
    return dict(pnl=p, turn=t)


def grid_row(pnl: pd.Series, turn: pd.Series) -> dict:
    """Gross headline and the 5 / 15 / 30bp real-money grid (one-way turnover x bp), labelled apart."""
    a, v = ann(pnl), float(pnl.std() * np.sqrt(252))
    t = float(turn.mean() * 252)
    return dict(ann=a, vol=v, sr=a / v, turn=t, mdd=float(max_drawdown(pnl)["mdd"]),
                net={bp: a - t * bp * 1e-4 for bp in COSTS_BP}, net_sr={bp: (a - t * bp * 1e-4) / v for bp in COSTS_BP})
