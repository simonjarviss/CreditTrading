"""Shared loaders for the 2026-11-02 alpha pre-screens (zero trials, fit window only).

WHY THIS FILE EXISTS
--------------------
Every screen in this folder asks the same kind of question of the same two
universes -- the 17 credit CEFs the core has ever traded (the deployed 13 plus
the four Nuveen munis Alpaca will not lend, "WIDE17") and C4's frozen 74, of
which 65 have a paired price and NAV before 2023 -- so they share one loader
rather than five copies of a discount definition. The signal itself is NEVER
re-derived here: `z`, `disc`, `adv` and `ret` come from
`scripts/cef/band_frontier.build_panel`, the function the harness and the
sleeve's research mirror use, with every live parameter read from the frozen
spec. C4 uses the same call with its families panels and its declared M1|M2
mask (`scripts/cef/c4_families.declared_mask`), exactly as C4's book does.

THE HOLDOUT (hard limit for this session)
-----------------------------------------
`build_panel(end=FIT_END)` truncates the RAW price and NAV history before
anything is computed, so no z, mean, sd or ADV can see a 2023 row, and every
frame this module returns is asserted to end on or before FIT_END. A forward
return that would need a 2023 close is NaN, never filled. The 27 sealed
`cef_universe.csv` names are never loaded: WIDE17 is named explicitly.

RETURNS
-------
* core: `bf.total_returns` on the live distribution panel (H15; raises on a gap).
* C4: `bf.total_returns` on the families yfinance actions file with C4's split
  rulings. NOTE: C4's own fit used CRSP as the primary return to 2024; the CRSP
  cache is not in this tree, so C4 returns here are the yfinance leg -- a
  second source, labelled as such in every note. Name-days whose one-day
  distribution yield exceeds 15% (year-end capital-gain payouts of equity
  funds, e.g. GAM 2007-11-14) are kept: they are real cash.
* NAV total return: NAV change plus D / NAV_{t-1} on the same ex-dates. This is
  the leg the negative controls use: a mechanism that claims to act on the CEF
  SHARE (retail selling, sentiment) must not show up in the fund's HOLDINGS.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

WT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WT))

from scripts.cef import band_frontier as bf  # noqa: E402
from scripts.cef.spec import MIN_NAMES, UNIVERSE, summary  # noqa: E402

FIT_END = pd.Timestamp("2022-12-30")
SAMPLE_START = pd.Timestamp("2005-01-03")
HOLDOUT_START = pd.Timestamp("2023-01-01")
WIDE17 = list(UNIVERSE) + ["NAD", "NEA", "NVG", "NZF"]
OUT = Path(__file__).resolve().parent

# Trial counters, read from docs/RESEARCH_STATE.md's counter table on 2026-11-02
# (CEF 53 used, EVENTS 3 used). The NEXT trial on each is the one a screen here
# would become, so the bar is sqrt(2 ln (used + 1)). These are re-read by
# `counters()` at run time; the literals are only the expected values, and a
# mismatch raises rather than silently using a stale bar (H14).
def counters() -> dict:
    txt = (WT / "docs" / "RESEARCH_STATE.md").read_text()
    out = {}
    for name in ("CEF", "EVENTS"):
        for line in txt.splitlines():
            if line.startswith(f"| **{name}**"):
                out[name] = int(line.split("|")[3].strip().strip("*"))
    if set(out) != {"CEF", "EVENTS"}:
        raise RuntimeError(f"could not read the CEF/EVENTS counters from RESEARCH_STATE.md: {out}")
    return out


def bar(n: int) -> float:
    return float(np.sqrt(2.0 * np.log(n)))


def p_pass(t_expected: float, b: float) -> float:
    """P(observed t >= bar) when the true standardised effect is t_expected and the
    observed t is N(t_expected, 1). The plain power approximation the desk's
    power gates use; it ignores estimation error in t_expected itself, so it is
    an UPPER bound when t_expected is an in-sample figure."""
    return float(stats.norm.sf(b - t_expected))


def assert_fit(*frames) -> None:
    for f in frames:
        idx = f.index if not isinstance(f, pd.Series) or not isinstance(f.index, pd.MultiIndex) else f.index.get_level_values(0)
        if len(idx) and pd.Timestamp(idx.max()) > FIT_END:
            raise AssertionError(f"holdout leak: a frame reaches {pd.Timestamp(idx.max()).date()} > {FIT_END.date()}")


def _nav_tr(nav: pd.DataFrame, dist: pd.DataFrame) -> pd.DataFrame:
    """NAV total return: N_t/N_{t-1} - 1 + D_t/N_{t-1}. ALIGNMENT: uses N_{t-1}, N_t, D_t."""
    amt = dist.groupby(["ex_date", "ticker"])["amount"].sum().unstack()
    amt = amt.reindex(index=nav.index, columns=nav.columns)
    r = nav.pct_change(fill_method=None).where(lambda x: x.abs() < 0.5)
    return r + (amt / nav.shift(1)).fillna(0.0)


def load_core() -> dict:
    p = bf.build_panel(universe=WIDE17, end=FIT_END)
    g = pd.read_csv(WT / "data" / "cef" / "cef_universe.csv").set_index("ticker")["grp"]
    out = _finish(p, dist=pd.read_parquet(WT / "data" / "cef" / "cef_distributions.parquet"),
                  tr=lambda R: bf.total_returns(R))
    out["grp"] = g.reindex(WIDE17)
    out["name"] = "WIDE17 (credit core, deployed 13 + NAD NEA NVG NZF)"
    return out


def load_c4() -> dict:
    from scripts.cef import c4_families as c4
    fz = pd.read_csv(c4.FROZEN)
    U = fz["ticker"].tolist()
    m = c4.declared_mask(U, "M1M2")
    p0 = bf.build_panel(universe=U, source=c4.FAM_SRC, end=FIT_END)
    U65 = sorted(p0["px"].columns[p0["px"].notna().any()])
    p = bf.build_panel(universe=U65, source=c4.FAM_SRC, mask=m[U65], end=FIT_END)
    act = pd.read_parquet(c4.FAM_DIR / "cef_actions.parquet")
    dist, _ = bf.load_families_actions(c4.FAM_DIR / "cef_actions.parquet")
    out = _finish(p, dist=dist,
                  tr=lambda R: bf.total_returns(R, actions=c4.FAM_DIR / "cef_actions.parquet",
                                                prices=c4.FAM_SRC[0], split_rulings=c4.SPLIT_RULINGS))
    out["grp"] = fz.set_index("ticker")["family"].reindex(U65)
    out["name"] = "C4 (frozen 74; the 65 with fit data; yfinance return leg)"
    return out


def _finish(p: dict, dist: pd.DataFrame, tr) -> dict:
    idx = p["px"].index
    idx = idx[(idx >= SAMPLE_START) & (idx <= FIT_END)]
    cols = list(p["px"].columns)
    r_px = p["ret"].reindex(idx)
    r_tr = tr(r_px)
    dist = dist.copy()
    dist["ex_date"] = pd.to_datetime(dist["ex_date"])
    dist = dist[dist["ticker"].isin(cols) & (dist["ex_date"] < HOLDOUT_START)]
    r_nav = _nav_tr(p["nav"], dist).reindex(idx)
    o = dict(idx=idx, U=cols, r_px=r_px, r_tr=r_tr, r_nav_tr=r_nav[cols], dist=dist,
             **{k: p[k].reindex(idx) for k in ("px", "nav", "disc", "z", "mu", "sd", "adv", "vol")})
    assert_fit(*[v for v in o.values() if isinstance(v, pd.DataFrame)])
    return o


def fwd(r: pd.DataFrame, a: int, b: int) -> pd.DataFrame:
    """Compounded return over sessions t+a..t+b (NaN if any is NaN). a >= 2 is
    what a book decided at t earns under shift(2) (decide t, MOC fill t+1)."""
    if a < 2:
        raise ValueError("a book decided at t cannot earn before t+2 (shift(2), H1)")
    out = None
    for k in range(a, b + 1):
        x = 1.0 + r.shift(-k)
        out = x if out is None else out * x
    return out - 1.0


def cs_demean(x: pd.DataFrame, by: pd.Series | None = None) -> pd.DataFrame:
    """Cross-sectional demeaning on each date, optionally within groups `by` (ticker -> group)."""
    if by is None:
        return x.sub(x.mean(axis=1), axis=0)
    out = x.copy()
    for g, cols in by.groupby(by).groups.items():
        cols = [c for c in cols if c in x.columns]
        sub = x[cols]
        out[cols] = sub.sub(sub.mean(axis=1), axis=0)
    return out


def pooled_ols(y: pd.DataFrame, X: dict, dates, min_n: int = 2) -> dict:
    """Pooled OLS of y on the columns of X (each a date x name frame, already
    demeaned by the caller), on `dates` only, standard errors clustered by date
    (H6). Returns coef, t and n per regressor."""
    keys = list(X)
    rows = []
    for d in dates:
        if d not in y.index:
            continue
        v = pd.DataFrame({"y": y.loc[d], **{k: X[k].loc[d] for k in keys}}).dropna()
        if len(v) >= min_n:
            v["date"] = d
            rows.append(v)
    if not rows:
        return {k: dict(coef=np.nan, t=np.nan) for k in keys} | {"n": 0, "dates": 0}
    D = pd.concat(rows)
    Xm = D[keys].to_numpy()
    ym = D["y"].to_numpy()
    XtX = Xm.T @ Xm
    beta = np.linalg.solve(XtX, Xm.T @ ym)
    e = ym - Xm @ beta
    meat = np.zeros((len(keys), len(keys)))
    for _, g in D.assign(e=e).groupby("date"):
        s = g[keys].to_numpy().T @ g["e"].to_numpy()
        meat += np.outer(s, s)
    G = D["date"].nunique()
    inv = np.linalg.inv(XtX)
    V = inv @ meat @ inv * G / max(G - 1, 1)
    se = np.sqrt(np.diag(V))
    return {k: dict(coef=float(beta[i]), t=float(beta[i] / se[i])) for i, k in enumerate(keys)} | \
        {"n": int(len(D)), "dates": int(G)}


def nw_t(x: pd.Series, lags: int = 5) -> float:
    v = x.dropna().to_numpy()
    n = len(v)
    if n < 10:
        return np.nan
    e = v - v.mean()
    lrv = e @ e / n
    for L in range(1, lags + 1):
        lrv += 2 * (1 - L / (lags + 1)) * (e[L:] @ e[:-L]) / n
    return float(v.mean() / np.sqrt(lrv / n))


def header(title: str, D: dict | None = None) -> str:
    s = f"{'=' * 100}\n{title}\nspec: {summary()}\nfit window only: <= {FIT_END.date()} (asserted)"
    if D is not None:
        s += (f"\nuniverse: {D['name']}; {len(D['U'])} names; sessions {D['idx'][0].date()} -> {D['idx'][-1].date()}")
    return s + "\n" + "=" * 100
