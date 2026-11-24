#!/usr/bin/env python3
"""R3 (2026-10-26, zero trials, report only): is C4's ex-date P&L concentration real or an artifact?

    python3 -I r3_c4_exdate/exdate_screen.py          # from SCRATCH; ~3 min; writes r3_c4_exdate/out/

The design, thresholds and negative control are declared in NOTE.md §1, written before this ran.

WHAT IT REUSES. `scripts/cef/c4_families.py` (SCRATCH/tree, branch `simon` dff4b5c) unchanged:
`universes`, `qqqx_rule`, `crsp_pivot` (identity + calendar checks), `build_book`, `fit_slice`,
`run_book`, `check_held`, `crsp_ex_dates`, `ex_window_mask`, `ex_window_split`; and
`band_frontier.evaluate` / `band_gross_capped` / `build_targets` / `total_returns`. No backtester is
built: every P&L cell here is evaluate()'s own H.shift(2) * R (decide t, MOC fill t+1, earn t+2), and
every split of it is asserted to sum back to evaluate()'s P&L.

THE HOLDOUT STAYS SEALED. The price and NAV panels are copied to `_panels/` cut at 2022-12-30 before
anything is built (the signal is causal, so the fit rows are unchanged; the gate proves it by
reproducing the committed fit Sharpe to 1e-9). CRSP is read with a parquet filter date <= 2022-12-30,
so no 2023+ CRSP row is ever in memory. `_assert_fit` runs on every frame that reaches a statistic.

LICENSED DATA. CRSP values are read from the trial-c4 worktree's gitignored cache (read-only; the
export has none and restaging needs R2). They are never written: outputs are aggregates and counts.

NO SILENT FALLBACKS. A missing input raises naming it; an unmeasurable event is counted as such and
never filled.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parent
TREE = SCRATCH / "tree"
OUT = HERE / "out"
PANELS = HERE / "_panels"
CRSP_CACHE = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/.claude/worktrees/"
                  "trial-c4/results/cef/c4/_cache_c4/crsp_ret_families.parquet")
FIT_END = pd.Timestamp("2022-12-30")
HOLDOUT_START = pd.Timestamp("2023-01-01")
COMMITTED_FIT_SR = 1.216957834377122          # results/cef/c4/c4_fit_verdict_2026-10-14.json stage1.gross_sr
COMMITTED_SHARE, COMMITTED_GROSS = 0.331, 0.105   # C4_RESULT §7 (amendment 3 row, fit), 3 dp
PLACEBO_SHIFT = 5
LR_MIN = 2.0                                   # NOTE §1.5: log-likelihood margin for a decisive class
SIG_LOOKBACK, SIG_MIN = 63, 40                 # NOTE §1.5: sigma window and minimum usable values
MIN_PEERS = 3
NW_L = 21
PROFILE = range(-10, 13)

sys.path.insert(0, str(TREE))
os.chdir(TREE)                                 # relative data/... paths resolve inside the tree

from scripts.cef import band_frontier as bf    # noqa: E402
from scripts.cef import c4_families as c4      # noqa: E402
from scripts.cef import w4_artifacts as w4     # noqa: E402
from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS, SPEC_ID  # noqa: E402

LOG: list[str] = []


def say(s: str = "") -> None:
    print(s, flush=True)
    LOG.append(s)


def assert_fit(*frames) -> None:
    w4._assert_fit(*frames)
    for f in frames:
        idx = f.index if hasattr(f, "index") else f
        if len(idx) and pd.Timestamp(idx.max()) > FIT_END:
            raise AssertionError(f"a frame reaches {idx.max()}, beyond the fit end {FIT_END.date()}")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------------------------- panels (truncated)

def cut_panel(src: Path, dst: Path) -> Path:
    """Copy a price or NAV panel cut at FIT_END (parquet filter: no later row is read)."""
    d = pd.read_parquet(src, filters=[("date", "<=", FIT_END)])
    if d.empty:
        raise ValueError(f"{src}: no rows on or before {FIT_END.date()}")
    if pd.to_datetime(d["date"]).max() > FIT_END:
        raise AssertionError(f"{src}: the filter let a row after {FIT_END.date()} through")
    dst.parent.mkdir(parents=True, exist_ok=True)
    d.to_parquet(dst, index=False)
    return dst


def panels() -> dict:
    p = dict(fam_px=cut_panel(TREE / "data/cef_families/cef_prices.parquet", PANELS / "fam_prices.parquet"),
             fam_nav=cut_panel(TREE / "data/cef_families/cef_nav.parquet", PANELS / "fam_nav.parquet"),
             core_px=cut_panel(TREE / "data/cef/cef_prices.parquet", PANELS / "core_prices.parquet"),
             core_nav=cut_panel(TREE / "data/cef/cef_nav.parquet", PANELS / "core_nav.parquet"))
    return p


def load_crsp(pool) -> pd.DataFrame:
    if not CRSP_CACHE.exists():
        raise FileNotFoundError(f"{CRSP_CACHE} is missing; it is built by "
                                "`stage_crsp_cef_families.py --returns` (needs R2; not run here)")
    c = pd.read_parquet(CRSP_CACHE, filters=[("date", "<=", FIT_END)])
    c["date"] = pd.to_datetime(c["date"])
    if c["date"].max() > FIT_END:
        raise AssertionError("CRSP filter let a holdout row through")
    missing = sorted(set(pool) - set(c["ticker"]))
    if missing:
        raise ValueError(f"CRSP cache has no rows for pool funds {missing}")
    return c[c["ticker"].isin(pool)].copy()


# --------------------------------------------------------------------------- window bookkeeping

def ex_positions(index: pd.DatetimeIndex, cols, exd: pd.DataFrame) -> dict:
    """{ticker: sorted positions of its ex-dates on `index`}. An ex-date inside the span that is not
    a session raises (as c4.ex_window_mask does)."""
    out = {}
    e = exd[(exd["date"] >= index[0]) & (exd["date"] <= index[-1])]
    for t in cols:
        d = e.loc[e["ticker"] == t, "date"]
        pos = index.get_indexer(pd.DatetimeIndex(d))
        if (pos < 0).any():
            raise ValueError(f"{t}: ex-dates that are not sessions: {list(d[pos < 0].astype(str))[:5]}")
        out[t] = np.unique(pos)
    return out


def window_from_positions(index, cols, pos: dict, lo=0, hi=2) -> pd.DataFrame:
    W = np.zeros((len(index), len(cols)), dtype=bool)
    n = len(index)
    for j, t in enumerate(cols):
        for p in pos.get(t, []):
            a, b = p + lo, p + hi + 1
            if b <= 0 or a >= n:
                continue
            W[max(a, 0):min(b, n), j] = True
    return pd.DataFrame(W, index=index, columns=list(cols))


def owner_offsets(index, cols, pos: dict):
    """For each fund-day: sessions since the latest ex-date at or before it (NaN if none), and that
    ex-date's position (the event that owns the fund-day)."""
    n = len(index)
    off = np.full((n, len(cols)), np.nan)
    own = np.full((n, len(cols)), -1, dtype=np.int64)
    ii = np.arange(n)
    for j, t in enumerate(cols):
        p = pos.get(t, np.array([], dtype=int))
        if not len(p):
            continue
        k = np.searchsorted(p, ii, side="right") - 1
        ok = k >= 0
        own[ok, j] = p[k[ok]]
        off[ok, j] = ii[ok] - p[k[ok]]
    return (pd.DataFrame(off, index=index, columns=list(cols)),
            pd.DataFrame(own, index=index, columns=list(cols)))


def wstats(C: pd.DataFrame, g: pd.DataFrame, M: pd.DataFrame, base: pd.DataFrame | None = None) -> dict:
    """S, G, CR, the excess series' NW t, annualised in/rest. C = P&L cells, g = |held| cells, M =
    the window (bool). `base` (optional bool): the fund-days defining the baseline rate for a second
    excess (outside both real and placebo windows)."""
    M = M.reindex_like(C).fillna(False).astype(bool)
    inw, rest, tot = C.where(M, 0.0).sum(axis=1), C.where(~M, 0.0).sum(axis=1), C.sum(axis=1)
    if not np.allclose((inw + rest).to_numpy(), tot.to_numpy(), rtol=0, atol=1e-14):
        raise AssertionError("window split does not sum")
    gW = g.where(M, 0.0).sum(axis=1)
    G = float(gW.sum() / g.to_numpy().sum())
    S = float(inw.sum() / tot.sum())
    rho_out = float(rest.sum() / g.where(~M, 0.0).to_numpy().sum())
    e = inw - rho_out * gW
    out = dict(S=S, G=G, CR=S / G if G > 0 else np.nan, pnl_in_pct=float(inw.sum() * 100),
               pnl_all_pct=float(tot.sum() * 100), ann_in_pct=float(inw.mean() * 252 * 100),
               ann_rest_pct=float(rest.mean() * 252 * 100), sr_in=c4.sr_of(inw), sr_rest=c4.sr_of(rest),
               excess_pct=float(e.sum() * 100), excess_nw_t=float(w4.nw_t(e, NW_L)),
               rho_out_bp=rho_out * 1e4, fund_days=int(M.to_numpy().sum()))
    if base is not None:
        B = base.reindex_like(C).fillna(False).astype(bool)
        rho_b = float(C.where(B, 0.0).to_numpy().sum() / g.where(B, 0.0).to_numpy().sum())
        eb = inw - rho_b * gW
        out.update(rho_base_bp=rho_b * 1e4, excess_base_pct=float(eb.sum() * 100),
                   excess_base_nw_t=float(w4.nw_t(eb, NW_L)))
    return out


def fmt_w(lab: str, s: dict) -> str:
    x = (f"  {lab:<34} S {s['S']:7.1%}  G {s['G']:6.1%}  CR {s['CR']:5.2f}  in {s['pnl_in_pct']:+8.2f}% "
         f"of {s['pnl_all_pct']:+8.2f}%  in {s['ann_in_pct']:+5.2f}%/yr SR {s['sr_in']:+.3f}  rest "
         f"{s['ann_rest_pct']:+5.2f}%/yr SR {s['sr_rest']:+.3f}  excess {s['excess_pct']:+7.2f}% NW t "
         f"{s['excess_nw_t']:+5.2f}")
    if "excess_base_nw_t" in s:
        x += f"  [vs baseline: {s['excess_base_pct']:+7.2f}% t {s['excess_base_nw_t']:+5.2f}]"
    return x


# --------------------------------------------------------------------------- main

def setup() -> dict:
    """Gate and cells, shared by main() and exdate_posthoc.py."""
    OUT.mkdir(parents=True, exist_ok=True)
    res: dict = dict(spec=SPEC_ID, crsp_cache=str(CRSP_CACHE), crsp_cache_sha256=sha256(CRSP_CACHE),
                     crsp_cache_mtime=pd.Timestamp(CRSP_CACHE.stat().st_mtime, unit="s").isoformat())
    say(f"R3 C4 ex-date screen (zero trials). spec {SPEC_ID}. Fit window only, <= {FIT_END.date()}.")
    say(f"CRSP cache (read-only, filtered <= {FIT_END.date()}): sha256 {res['crsp_cache_sha256'][:16]}..., "
        f"mtime {res['crsp_cache_mtime']}")
    P_ = panels()
    # The C4 book is built as the committed fit builds it: build_targets on the full families panel
    # (causal, H7), fit_slice at 2022-12-30 before band/cap/evaluate (NOTE §1.1, amended on the first
    # run: the truncated panel drops the nine funds with no pre-2023 data and build_targets raises).
    # c4.FAM_SRC is left as committed. This screen's own reads use the truncated copies.
    U = c4.universes()
    pool, UF, fam = U["pool"], U["frozen"], U["fam"]
    px = pd.read_parquet(P_["fam_px"]); nav = pd.read_parquet(P_["fam_nav"])
    px, nav = px[px["ticker"].isin(pool)].copy(), nav[nav["ticker"].isin(pool)].copy()
    for f in (px, nav):
        f["date"] = pd.to_datetime(f["date"])
    say(f"panels: families prices last {px['date'].max().date()}, NAV last {nav['date'].max().date()} "
        f"(cut copies of data/cef_families/, whose own last date is 2026-10-09)")
    crsp = load_crsp(pool)
    say(f"CRSP rows {len(crsp):,}, last {crsp['date'].max().date()}")
    qr = c4.qqqx_rule(crsp, px)
    if not qr["use_predecessor"]:
        raise RuntimeError("QQQX rule decision differs from the fit's")

    # ---------------- GATE: the declared book reproduces the committed fit
    T74 = c4.fit_slice(c4.build_book(UF))
    idx = T74.index
    R_ret = c4.crsp_pivot(crsp, pool, idx, qr, "ret", px=px)
    R_retx = c4.crsp_pivot(crsp, pool, idx, qr, "retx", px=px)
    assert_fit(idx, R_ret, R_retx)
    row, P, H, R0, p0, _ = c4.run_book("C4 (74, declared)", UF, R_ret, T=T74)
    if abs(row["sr"] - COMMITTED_FIT_SR) > 1e-9:
        raise RuntimeError(f"GATE FAIL: fit gross SR {row['sr']!r} != committed {COMMITTED_FIT_SR!r}")
    R0x = c4.check_held(H, R_retx[UF].reindex(T74.index), "price-only")
    Px = bf.evaluate(H, R0x)["pnl"].loc[p0:FIT_END]
    cx = c4.crsp_ex_dates(crsp, qr, UF)
    W_c4 = c4.ex_window_mask(H.index, H.columns, cx)
    ex_f = c4.ex_window_split(H, R0, W_c4, p0, FIT_END)
    if round(ex_f["share_in_window"], 3) != COMMITTED_SHARE or round(ex_f["held_gross_share_in_window"], 3) != COMMITTED_GROSS:
        raise RuntimeError(f"GATE FAIL: window share {ex_f['share_in_window']:.4f} / gross "
                           f"{ex_f['held_gross_share_in_window']:.4f} != committed 33.1% / 10.5%")
    say(f"\nGATE PASS: fit gross SR {row['sr']:.9f} (committed {COMMITTED_FIT_SR:.9f}); {p0.date()}..{P.index[-1].date()}, "
        f"{len(P)} sessions; amendment-3 window share {ex_f['share_in_window']:.4f} on held gross "
        f"{ex_f['held_gross_share_in_window']:.4f} (committed 33.1% / 10.5%)")
    say(f"  price-only (CRSP retx) on the same H: gross SR {c4.sr_of(Px):.3f}, {Px.mean() * 252 * 100:.2f}%/yr "
        f"(committed R-P row: 1.360, 8.33%/yr [doc]); total {row['sr']:.3f}, {P.mean() * 252 * 100:.2f}%/yr")
    res["gate"] = dict(fit_sr=row["sr"], first_held=str(p0.date()), sessions=len(P), ex_split=ex_f,
                       price_only_sr=c4.sr_of(Px), price_only_ann_pct=float(Px.mean() * 252 * 100),
                       total_ann_pct=float(P.mean() * 252 * 100))

    # ---------------- cells
    sl = slice(p0, FIT_END)
    held = H.shift(2).fillna(0.0)
    Ct = (held * R0).loc[sl]
    Cx = (held * R0x).loc[sl]
    Cd = Ct - Cx                                      # distribution leg = held * (ret - retx)
    g = held.abs().loc[sl]
    assert_fit(Ct, Cx, g)
    if not np.allclose(Ct.sum(axis=1).to_numpy(), P.to_numpy(), rtol=0, atol=1e-15):
        raise AssertionError("cells do not sum to evaluate()'s P&L")
    if not np.allclose(Cx.sum(axis=1).to_numpy(), Px.to_numpy(), rtol=0, atol=1e-15):
        raise AssertionError("price-only cells do not sum to evaluate()'s P&L")
    cols = list(H.columns)
    pos = ex_positions(H.index, cols, cx)
    W = window_from_positions(H.index, cols, pos, 0, 2)
    if not W.equals(W_c4.reindex(index=H.index, columns=cols)):
        raise AssertionError("own window differs from c4.ex_window_mask")
    W = W.loc[sl]
    # distribution leg lives only on ex-days (day 0), by construction
    D0 = window_from_positions(H.index, cols, pos, 0, 0).loc[sl]
    if np.abs(Cd.where(~D0, 0.0).to_numpy()).max() > 1e-15:
        raise AssertionError("distribution leg found off an ex-day")

    # placebo windows (shift +-5), real-window fund-days removed
    posp = {t: p + PLACEBO_SHIFT for t, p in pos.items()}
    posm = {t: p - PLACEBO_SHIFT for t, p in pos.items()}
    Wp = window_from_positions(H.index, cols, posp).loc[sl] & ~W
    Wm = window_from_positions(H.index, cols, posm).loc[sl] & ~W
    Wpm = Wp | Wm
    base = ~(W | Wpm)

    return dict(res=res, P_=P_, U=U, pool=pool, UF=UF, fam=fam, px=px, nav=nav, crsp=crsp, qr=qr, idx=idx, H=H, R0=R0, R0x=R0x, p0=p0, P=P, Px=Px, cx=cx, sl=sl, held=held, Ct=Ct, Cx=Cx, Cd=Cd, g=g, cols=cols, pos=pos, W=W, D0=D0, Wp=Wp, Wm=Wm, Wpm=Wpm, base=base)


def main() -> int:
    ctx = setup()
    (res, P_, U, pool, UF, fam, px, nav, crsp, qr, idx, H, R0, R0x, p0, P, Px, cx, sl, held, Ct, Cx, Cd, g, cols, pos, W, D0, Wp, Wm, Wpm, base) = (ctx[k] for k in ['res', 'P_', 'U', 'pool', 'UF', 'fam', 'px', 'nav', 'crsp', 'qr', 'idx', 'H', 'R0', 'R0x', 'p0', 'P', 'Px', 'cx', 'sl', 'held', 'Ct', 'Cx', 'Cd', 'g', 'cols', 'pos', 'W', 'D0', 'Wp', 'Wm', 'Wpm', 'base'])
    say("\n" + "=" * 110 + "\nA. THE WINDOW AND THE NEGATIVE CONTROL (C4 fit, 74 frozen funds)\n" + "=" * 110)
    A = {}
    for basis, C in (("total", Ct), ("price_only", Cx)):
        A[basis] = dict(real=wstats(C, g, W, base), placebo_plus5=wstats(C, g, Wp, base),
                        placebo_minus5=wstats(C, g, Wm, base), placebo_pooled=wstats(C, g, Wpm, base))
        say(f"\n {basis.upper()} basis ({'CRSP ret' if basis == 'total' else 'CRSP retx: what Alpaca paper books'}):")
        for k, lab in (("real", "real window [0,2]"), ("placebo_plus5", "placebo +5 [5,7]"),
                       ("placebo_minus5", "placebo -5 [-5,-3]"), ("placebo_pooled", "placebo pooled +-5")):
            say(fmt_w(lab, A[basis][k]))
    res["A_window"] = A

    # ---------------- decomposition by day, side, family
    off, own = owner_offsets(H.index, cols, pos)
    off, own = off.loc[sl], own.loc[sl]
    say("\n" + "=" * 110 + "\nB. EXPLANATION 2 -- TOTAL vs PRICE-ONLY, by window day and held side\n" + "=" * 110)
    B = {}
    tot_all = Ct.to_numpy().sum()
    for k in (0, 1, 2):
        Mk = (off == k) & W
        B[f"day{k}"] = dict(total_pct=float(Ct.where(Mk, 0).to_numpy().sum() * 100),
                            price_pct=float(Cx.where(Mk, 0).to_numpy().sum() * 100),
                            dist_leg_pct=float(Cd.where(Mk, 0).to_numpy().sum() * 100),
                            gross_share=float(g.where(Mk, 0).to_numpy().sum() / g.to_numpy().sum()))
    for side, Ms in (("long", held.loc[sl] > 0), ("short", held.loc[sl] < 0)):
        Mx = Ms & W
        B[f"{side}_in_window"] = dict(total_pct=float(Ct.where(Mx, 0).to_numpy().sum() * 100),
                                      price_pct=float(Cx.where(Mx, 0).to_numpy().sum() * 100),
                                      dist_leg_pct=float(Cd.where(Mx, 0).to_numpy().sum() * 100),
                                      gross_share=float(g.where(Mx, 0).to_numpy().sum() / g.to_numpy().sum()))
        Mo = Ms & ~W
        B[f"{side}_outside"] = dict(total_pct=float(Ct.where(Mo, 0).to_numpy().sum() * 100),
                                    price_pct=float(Cx.where(Mo, 0).to_numpy().sum() * 100),
                                    gross_share=float(g.where(Mo, 0).to_numpy().sum() / g.to_numpy().sum()))
    B["dist_leg_total_pct"] = float(Cd.to_numpy().sum() * 100)
    B["dist_leg_ann_pct"] = float(Cd.sum(axis=1).mean() * 252 * 100)
    exday_w = held.loc[sl].where(D0)
    B["mean_signed_weight_on_exdays"] = float(np.nanmean(exday_w.to_numpy()))
    B["sum_signed_weight_on_exdays"] = float(np.nansum(exday_w.to_numpy()))
    say(f"  distribution leg (total - price-only) over the fit: {B['dist_leg_total_pct']:+.2f}% "
        f"({B['dist_leg_ann_pct']:+.2f}%/yr); mean signed held weight on ex-days "
        f"{B['mean_signed_weight_on_exdays']:+.5f} (sum {B['sum_signed_weight_on_exdays']:+.2f})")
    for k in ("day0", "day1", "day2", "long_in_window", "short_in_window", "long_outside", "short_outside"):
        b = B[k]
        say(f"  {k:<16} total {b['total_pct']:+8.2f}%  price-only {b['price_pct']:+8.2f}%  "
            f"dist leg {b.get('dist_leg_pct', 0.0):+7.2f}%  held gross share {b['gross_share']:6.1%}")
    fams = {}
    for fm in sorted(set(fam[t] for t in cols)):
        ff = [t for t in cols if fam[t] == fm]
        Mf = W[ff]
        fams[fm] = dict(funds=len(ff),
                        in_total_pct=float(Ct[ff].where(Mf, 0).to_numpy().sum() * 100),
                        in_price_pct=float(Cx[ff].where(Mf, 0).to_numpy().sum() * 100),
                        all_total_pct=float(Ct[ff].to_numpy().sum() * 100),
                        in_gross_share=float(g[ff].where(Mf, 0).to_numpy().sum() / g.to_numpy().sum()))
    B["by_family"] = fams
    say("  by family (descriptive): " + "; ".join(
        f"{k} in-window total {v['in_total_pct']:+.2f}% / price {v['in_price_pct']:+.2f}% (all {v['all_total_pct']:+.2f}%, "
        f"in-window gross {v['in_gross_share']:.1%})" for k, v in fams.items()))
    # event-time profile (descriptive)
    prof = []
    for k in PROFILE:
        poss = {t: p + k for t, p in pos.items()}
        Mk = window_from_positions(H.index, cols, poss, 0, 0).loc[sl]
        gs = g.where(Mk, 0).to_numpy().sum()
        prof.append(dict(k=k, gross=float(gs),
                         total_bp_per_gross=float(Ct.where(Mk, 0).to_numpy().sum() / gs * 1e4) if gs else np.nan,
                         price_bp_per_gross=float(Cx.where(Mk, 0).to_numpy().sum() / gs * 1e4) if gs else np.nan))
    B["profile"] = prof
    rho_all_t = tot_all / g.to_numpy().sum() * 1e4
    rho_all_x = Cx.to_numpy().sum() / g.to_numpy().sum() * 1e4
    say(f"  event-time profile, P&L per unit held gross per fund-day, bp (book average: total {rho_all_t:.2f}, "
        f"price-only {rho_all_x:.2f}):")
    say("    " + "  ".join(f"{p['k']:+d}:{p['total_bp_per_gross']:+.1f}/{p['price_bp_per_gross']:+.1f}" for p in prof))
    res["B_accounting"] = B

    # ---------------- EXPLANATION 1: NAV alignment, per event
    say("\n" + "=" * 110 + "\nC. EXPLANATION 1 -- WHERE THE NAV DROP LANDS RELATIVE TO THE PRICE'S\n" + "=" * 110)
    ev = event_alignment(crsp, qr, pool, UF, fam, px, nav, idx, held.loc[sl], W, own, sl)
    res["C_alignment"] = ev["summary"]
    E = ev["events"]                                   # per-event frame (in memory only; holds CRSP-derived y)

    # ---------------- EXPLANATION 1b: stale prints
    prc = c4.crsp_pivot(crsp, pool, idx, qr, "prc", px=px, check_identity=False)[cols]
    vol = px.pivot_table(index="date", columns="ticker", values="volume").reindex(index=idx, columns=cols)
    notrade = (prc <= 0) | (vol == 0)
    stale = (notrade | notrade.shift(1, fill_value=False)).loc[sl] & W
    S1b = dict(in_window_fund_days=int(stale.to_numpy().sum()),
               share_total=float(Ct.where(stale, 0).to_numpy().sum() / Ct.where(W, 0).to_numpy().sum()),
               share_price=float(Cx.where(stale, 0).to_numpy().sum() / Cx.where(W, 0).to_numpy().sum()),
               share_gross=float(g.where(stale, 0).to_numpy().sum() / g.where(W, 0).to_numpy().sum()))
    say(f"\nEXPLANATION 1b (stale prints: CRSP prc <= 0 or yfinance volume 0 on t or t-1): {S1b['in_window_fund_days']} "
        f"in-window fund-days carry {S1b['share_total']:.1%} of in-window total P&L, {S1b['share_price']:.1%} of price-only, "
        f"on {S1b['share_gross']:.1%} of in-window held gross")
    res["C1b_stale"] = S1b

    # ---------------- EXPLANATION 3: disputes
    say("\n" + "=" * 110 + "\nD. EXPLANATION 3 -- DISPUTED AMOUNTS AND DISAGREEING INPUTS\n" + "=" * 110)
    rul = pd.read_csv(TREE / "results/cef/c4/c4_distribution_resolution_2026-10-18.csv", parse_dates=["date"])
    n_fit_rul = int((rul["date"] <= FIT_END).sum())
    if n_fit_rul:
        raise AssertionError(f"{n_fit_rul} amendment-4 rulings fall in the fit window; the design assumed none")
    say(f"  amendment-4 rulings: {len(rul)} disputed ex-dates, {rul['date'].min().date()}..{rul['date'].max().date()}; "
        f"in the fit window: {n_fit_rul} (asserted)")
    E = dispute_flags(E, idx, px, sl)
    res["D_disputes"] = dispute_summary(E, Ct, Cx, g, W, own, cols, sl)

    # ---------------- verdict inputs: data-cause share, CR_clean
    res["E_verdict"] = verdict(E, Ct, Cx, g, W, own, cols, stale, A, ev["summary"], res["D_disputes"])

    # ---------------- contrast: the 13-name core
    say("\n" + "=" * 110 + "\nF. CONTRAST -- THE DEPLOYED 13-NAME CORE BOOK, ITS OWN FIT\n" + "=" * 110)
    res["F_core"] = core_book(P_)

    (OUT / "exdate_screen_output.txt").write_text("\n".join(LOG) + "\n")
    (OUT / "exdate_screen_results.json").write_text(json.dumps(res, indent=1, default=float))
    say(f"\nwrote {OUT / 'exdate_screen_output.txt'} and exdate_screen_results.json")
    return 0


# --------------------------------------------------------------------------- explanation 1

def event_alignment(crsp, qr, pool, UF, fam, px, nav, idx, held_sl, W, own, sl) -> dict:
    """NOTE §1.5. Per CRSP ex-date of the 74 (2005-01-03..2022-12-30): the peer-adjusted NAV return at
    s-1, s, s+1 against the expected drop q = -y * close/NAV (both at s-1), sigma from s-64..s-2."""
    n = len(idx)
    navp = nav.pivot_table(index="date", columns="ticker", values="nav").reindex(index=idx, columns=pool)
    clp = px.pivot_table(index="date", columns="ticker", values="close").reindex(index=idx, columns=pool)
    rN = navp / navp.shift(1) - 1.0                     # consecutive sessions; NaN if either side missing
    rep = rN.eq(0.0)
    retx = c4.crsp_pivot(crsp, pool, idx, qr, "retx", check_identity=False)
    ret = c4.crsp_pivot(crsp, pool, idx, qr, "ret", check_identity=False)
    cxp = c4.crsp_ex_dates(crsp, qr, pool)
    posp = ex_positions(idx, pool, cxp)
    near = window_from_positions(idx, pool, posp, -1, 1)   # within +-1 of an own ex-date
    # leave-one-out family median NAV return and price return, peers excluding near-ex and repeats
    uN = pd.DataFrame(np.nan, index=idx, columns=pool)
    uP = pd.DataFrame(np.nan, index=idx, columns=pool)
    for fm in sorted(set(fam[t] for t in pool)):
        mem = [t for t in pool if fam[t] == fm]
        XN = rN[mem].where(~near[mem] & ~rep[mem]).to_numpy()
        XP = retx[mem].where(~near[mem]).to_numpy()
        for j, t in enumerate(mem):
            others = [k for k in range(len(mem)) if k != j]
            if not others:
                continue
            with warnings.catch_warnings():         # all-NaN rows -> NaN, then masked by the peer count
                warnings.simplefilter("ignore", RuntimeWarning)
                mN = np.nanmedian(XN[:, others], axis=1)
                mP = np.nanmedian(XP[:, others], axis=1)
            cN = np.sum(~np.isnan(XN[:, others]), axis=1)
            cP = np.sum(~np.isnan(XP[:, others]), axis=1)
            mN[cN < MIN_PEERS] = np.nan
            mP[cP < MIN_PEERS] = np.nan
            uN[t] = rN[t].to_numpy() - mN
            uP[t] = retx[t].to_numpy() - mP
    rows = []
    lo_fit = idx.searchsorted(pd.Timestamp("2005-01-03"))
    pos74 = {t: posp[t] for t in UF}
    for t in UF:
        if navp[t].notna().sum() == 0:
            continue
        for s in pos74[t]:
            if s < lo_fit or s + 1 >= n or s - 2 < 0:
                continue
            y = ret[t].iat[s] - retx[t].iat[s]
            c_prev, n_prev = clp[t].iat[s - 1], navp[t].iat[s - 1]
            q = -y * c_prev / n_prev if (np.isfinite(c_prev) and np.isfinite(n_prev) and n_prev > 0) else np.nan
            u = [uN[t].iat[s + k] for k in (-1, 0, 1)]
            a = max(0, s - SIG_LOOKBACK - 1)
            hist = uN[t].iloc[a:s - 1]                        # s-64 .. s-2: strictly before the event
            okh = ~near[t].iloc[a:s - 1] & ~rep[t].iloc[a:s - 1] & hist.notna()
            hv = hist[okh]
            sig = float(hv.std()) if len(hv) >= SIG_MIN else np.nan
            r = dict(ticker=t, family=fam[t], s=int(s), date=idx[s], y=y, q=q, u_m1=u[0], u_0=u[1], u_p1=u[2],
                     u_m2=uN[t].iat[s - 2] if s - 2 >= 0 else np.nan,
                     u_p2=uN[t].iat[s + 2] if s + 2 < n else np.nan,
                     p_m2=uP[t].iat[s - 2], p_m1=uP[t].iat[s - 1], p_0=uP[t].iat[s], p_p1=uP[t].iat[s + 1],
                     p_p2=uP[t].iat[s + 2] if s + 2 < n else np.nan,
                     sigma=sig, nav_repeat_on_ex=bool(rep[t].iat[s]), nav_missing=bool(
                         navp[t].iloc[s - 2:s + 2].isna().any()))
            rows.append(r)
    E = pd.DataFrame(rows)
    # classification
    meas = E[["u_m1", "u_0", "u_p1", "q", "sigma"]].notna().all(axis=1) & (E["sigma"] > 0)
    E["cls"] = "unmeasurable"
    U3 = E.loc[meas, ["u_m1", "u_0", "u_p1"]].to_numpy()
    q = E.loc[meas, "q"].to_numpy()[:, None]
    s2 = 2 * E.loc[meas, "sigma"].to_numpy()[:, None] ** 2
    base = (U3 ** 2).sum(axis=1)[:, None]
    LLk = -(base - U3 ** 2 + (U3 - q) ** 2) / s2           # k = -1, 0, +1
    LLn = -base / s2
    LL = np.hstack([LLk, LLn])
    labs = np.array(["-1", "0", "+1", "none"])
    order = np.argsort(-LL, axis=1)
    best, second = LL[np.arange(len(LL)), order[:, 0]], LL[np.arange(len(LL)), order[:, 1]]
    cl = np.where(best - second >= LR_MIN, labs[order[:, 0]], "ambiguous")
    E.loc[meas, "cls"] = cl
    E["unmeas_reason"] = ""
    um = ~meas
    E.loc[um & E["nav_missing"], "unmeas_reason"] = "NAV missing s-2..s+1"
    E.loc[um & ~E["nav_missing"] & E["sigma"].isna(), "unmeas_reason"] = "sigma < 40 usable"
    E.loc[um & (E["unmeas_reason"] == ""), "unmeas_reason"] = "peers < 3 or q undefined"
    # held events: any owned window fund-day with held gross > 0
    sl_idx = held_sl.index
    cols = list(held_sl.columns)
    gW = held_sl.abs().where(W, 0.0)
    ownW = own.where(W, -1)
    ev_g = {}
    ev_ct = {}
    for j, t in enumerate(cols):
        o = ownW[t].to_numpy()
        gg = gW[t].to_numpy()
        m = o >= 0
        if m.any():
            sgrp = pd.Series(gg[m]).groupby(o[m]).sum()
            for s, v in sgrp.items():
                ev_g[(t, int(s))] = float(v)
    E["held_gross"] = [ev_g.get((t, s), 0.0) for t, s in zip(E["ticker"], E["s"])]
    E["held"] = E["held_gross"] > 0
    # CEFConnect weekly dated NAV on s-1..s+1
    fl = pd.read_parquet(TREE / "data/cef_families/nav_flags.parquet", columns=["ticker", "date", "cc_nav_All"],
                         filters=[("date", "<=", FIT_END)])
    fl["date"] = pd.to_datetime(fl["date"])
    flp = fl[fl["ticker"].isin(UF)].pivot_table(index="date", columns="ticker", values="cc_nav_All",
                                                aggfunc="first").reindex(index=idx)
    ccc = {}
    for t, s in zip(E["ticker"], E["s"]):
        if t not in flp.columns:
            continue
        for k in (-1, 0, 1):
            v = flp[t].iat[s + k]
            if isinstance(v, str):
                ccc[(k, v)] = ccc.get((k, v), 0) + 1
    # pooled slopes
    def slopes(cols_u, xcol, sub):
        out = {}
        for k, cu in zip((-2, -1, 0, 1, 2), cols_u):
            d = sub[[cu, xcol]].dropna()
            x, yv = d[xcol].to_numpy(), d[cu].to_numpy()
            b = float((x * yv).sum() / (x * x).sum())
            e = yv - b * x
            se = float(np.sqrt((x * x * e * e).sum()) / (x * x).sum())     # HC0
            out[k] = dict(beta=b, se=se, n=len(d))
        return out
    sub = E[meas].copy()
    sub["negy"] = -sub["y"]
    nav_sl = slopes(["u_m2", "u_m1", "u_0", "u_p1", "u_p2"], "q", sub)
    px_sl = slopes(["p_m2", "p_m1", "p_0", "p_p1", "p_p2"], "negy", sub)
    # P&L share by class
    cls_of = {(t, s): c for t, s, c in zip(E["ticker"], E["s"], E["cls"])}
    summary = dict(events_all=int(len(E)), events_held=int(E["held"].sum()),
                   counts_all=E["cls"].value_counts().to_dict(),
                   counts_held=E.loc[E["held"], "cls"].value_counts().to_dict(),
                   unmeasurable_reasons_held=E.loc[E["held"] & (E["cls"] == "unmeasurable"), "unmeas_reason"].value_counts().to_dict(),
                   nav_repeat_on_exday_all=int(E["nav_repeat_on_ex"].sum()),
                   nav_repeat_on_exday_held=int((E["nav_repeat_on_ex"] & E["held"]).sum()),
                   cefconnect_flags_on_s_m1_to_p1={f"{k:+d}:{v}": n for (k, v), n in sorted(ccc.items())},
                   pooled_nav_slope=nav_sl, pooled_price_slope=px_sl,
                   median_D_over_sigma=float((E.loc[meas, "q"].abs() / E.loc[meas, "sigma"]).median()))
    say(f"  events: {summary['events_all']:,} CRSP ex-dates of the 74 in 2005-01-03..{FIT_END.date()} on funds with NAV; "
        f"{summary['events_held']:,} held (held gross > 0 on an owned window day)")
    say(f"  class counts, all: {summary['counts_all']}")
    say(f"  class counts, held: {summary['counts_held']}")
    say(f"  unmeasurable (held) by reason: {summary['unmeasurable_reasons_held']}")
    say(f"  median |drop| / sigma on measurable events: {summary['median_D_over_sigma']:.2f} (how separable the classes are)")
    say(f"  deterministic: yfinance NAV repeats exactly on the ex-session: {summary['nav_repeat_on_exday_all']} events "
        f"({summary['nav_repeat_on_exday_held']} held)")
    say(f"  second method, CEFConnect weekly dated NAV on s-1..s+1 (offset:flag count): {summary['cefconnect_flags_on_s_m1_to_p1']}")
    say("  third method, pooled slope of the peer-adjusted NAV return at s+k on the expected drop q (aligned: b0~1, others~0):")
    say("    NAV:   " + "  ".join(f"k{k:+d} b {v['beta']:+.3f} (se {v['se']:.3f}, n {v['n']})" for k, v in nav_sl.items()))
    say("    price: " + "  ".join(f"k{k:+d} b {v['beta']:+.3f} (se {v['se']:.3f}, n {v['n']})" for k, v in px_sl.items()))
    return dict(events=E, summary=summary, cls_of=cls_of, uN=uN, uP=uP, near=near, rep=rep)


# --------------------------------------------------------------------------- explanation 3

def dispute_flags(E: pd.DataFrame, idx, px, sl) -> pd.DataFrame:
    """NOTE §1.8 (a)-(d) per event."""
    E = E.copy()
    act = pd.read_parquet(TREE / "data/cef_families/cef_actions.parquet", filters=[("date", "<=", FIT_END)])
    act["date"] = pd.to_datetime(act["date"])
    dv = act[act["dividends"] > 0].groupby(["ticker", "date"])["dividends"].sum()
    clp = px.pivot_table(index="date", columns="ticker", values="close").reindex(index=idx)
    yyf, fa = [], []
    for t, s, y in zip(E["ticker"], E["s"], E["y"]):
        d = idx[s]
        D = dv.get((t, d), np.nan)
        cp = clp[t].iat[s - 1] if t in clp.columns else np.nan
        yf_y = D / cp if np.isfinite(D) and np.isfinite(cp) and cp > 0 else np.nan
        yyf.append(yf_y)
        tol = 0.001 / cp + 2e-6 if np.isfinite(cp) and cp > 0 else np.nan
        fa.append(bool((not np.isfinite(yf_y)) or abs(y - yf_y) > tol))
    E["flag_a_amount"] = fa
    E["flag_a_no_yf_dividend"] = [not np.isfinite(v) for v in yyf]
    for lab, f in (("b_nav", "nav_disagreements.csv"), ("c_disc", "discount_disagreements.csv"),
                   ("d_price", "price_disagreements.csv")):
        d = pd.read_csv(TREE / "data/cef_families" / f, parse_dates=["date"])
        d = d[d["date"] <= FIT_END]
        p = idx.get_indexer(pd.DatetimeIndex(d["date"]))
        keys = set(zip(d["ticker"], p))
        E[f"flag_{lab}"] = [any((t, s + k) in keys for k in (-1, 0, 1, 2)) for t, s in zip(E["ticker"], E["s"])]
    E["flag_any_dispute"] = E[["flag_a_amount", "flag_b_nav", "flag_c_disc", "flag_d_price"]].any(axis=1)
    return E


def _event_mask(E_sel: pd.DataFrame, own: pd.DataFrame, W: pd.DataFrame, cols) -> pd.DataFrame:
    """Window fund-days owned by the events in E_sel."""
    M = pd.DataFrame(False, index=own.index, columns=cols)
    keys = {}
    for t, s in zip(E_sel["ticker"], E_sel["s"]):
        keys.setdefault(t, set()).add(int(s))
    for t, ss in keys.items():
        M[t] = own[t].isin(list(ss)).to_numpy() & W[t].to_numpy()
    return M


def _share(M, Ct, Cx, g, W) -> dict:
    inT, inX, inG = Ct.where(W, 0).to_numpy().sum(), Cx.where(W, 0).to_numpy().sum(), g.where(W, 0).to_numpy().sum()
    return dict(share_total=float(Ct.where(M, 0).to_numpy().sum() / inT),
                share_price=float(Cx.where(M, 0).to_numpy().sum() / inX),
                share_gross=float(g.where(M, 0).to_numpy().sum() / inG),
                pnl_total_pct=float(Ct.where(M, 0).to_numpy().sum() * 100),
                pnl_price_pct=float(Cx.where(M, 0).to_numpy().sum() * 100),
                CR_total=float((Ct.where(M, 0).to_numpy().sum() / Ct.to_numpy().sum()) /
                               (g.where(M, 0).to_numpy().sum() / g.to_numpy().sum())) if g.where(M, 0).to_numpy().sum() else np.nan)


def dispute_summary(E, Ct, Cx, g, W, own, cols, sl) -> dict:
    out = {}
    for f in ("flag_a_amount", "flag_a_no_yf_dividend", "flag_b_nav", "flag_c_disc", "flag_d_price", "flag_any_dispute"):
        M = _event_mask(E[E[f]], own, W, cols)
        out[f] = dict(events_all=int(E[f].sum()), events_held=int((E[f] & E["held"]).sum()), **_share(M, Ct, Cx, g, W))
        o = out[f]
        say(f"  {f:<24} events {o['events_all']:5d} (held {o['events_held']:5d}): in-window total P&L share "
            f"{o['share_total']:6.1%}, price-only {o['share_price']:6.1%}, on {o['share_gross']:6.1%} of in-window gross; CR {o['CR_total']:.2f}")
    M = _event_mask(E[~E["flag_any_dispute"]], own, W, cols)
    out["undisputed"] = dict(events_all=int((~E["flag_any_dispute"]).sum()), **_share(M, Ct, Cx, g, W))
    o = out["undisputed"]
    say(f"  {'undisputed':<24} events {o['events_all']:5d}: share total {o['share_total']:6.1%}, price {o['share_price']:6.1%}, "
        f"gross {o['share_gross']:6.1%}; CR {o['CR_total']:.2f}")
    return out


# --------------------------------------------------------------------------- verdict

def verdict(E, Ct, Cx, g, W, own, cols, stale, A, align, disp) -> dict:
    say("\n" + "=" * 110 + "\nE. EXPLANATION 1 SHARES AND THE DECLARED VERDICT INPUTS (NOTE §1.5, §1.9)\n" + "=" * 110)
    out = {}
    for c in ("0", "+1", "-1", "none", "ambiguous", "unmeasurable"):
        M = _event_mask(E[E["cls"] == c], own, W, cols)
        out[f"class_{c}"] = dict(events=int((E["cls"] == c).sum()), **_share(M, Ct, Cx, g, W))
        o = out[f"class_{c}"]
        say(f"  class {c:<13} events {o['events']:5d}: in-window total share {o['share_total']:6.1%}, price-only "
            f"{o['share_price']:6.1%}, gross {o['share_gross']:6.1%}; CR {o['CR_total']:.2f}")
    mis = E["cls"].isin(["+1", "-1", "none"])
    Mmis = _event_mask(E[mis], own, W, cols)
    out["misaligned"] = _share(Mmis, Ct, Cx, g, W)
    amb = E["cls"].isin(["ambiguous", "unmeasurable"])
    out["ambiguous_or_unmeasurable"] = _share(_event_mask(E[amb], own, W, cols), Ct, Cx, g, W)
    # union data-cause mask: misaligned events | disputed events | stale-print fund-days
    Mdisp = _event_mask(E[E["flag_any_dispute"]], own, W, cols)
    Mdata = (Mmis | Mdisp | stale.reindex_like(Mmis).fillna(False)) & W
    out["data_cause"] = _share(Mdata, Ct, Cx, g, W)
    Mclean = W & ~Mdata
    out["clean"] = _share(Mclean, Ct, Cx, g, W)
    cr_real = A["total"]["real"]["CR"]
    cr_plc = A["total"]["placebo_pooled"]["CR"]
    cr_real_x = A["price_only"]["real"]["CR"]
    cr_plc_x = A["price_only"]["placebo_pooled"]["CR"]
    t_ex = A["total"]["real"]["excess_nw_t"]
    Dp = out["data_cause"]["share_total"]
    cr_clean = out["clean"]["CR_total"]
    cr_aligned = out["class_0"]["CR_total"]
    amb_share = out["ambiguous_or_unmeasurable"]["share_total"]
    nav_sl = align["pooled_nav_slope"]
    slope_aligned = bool(nav_sl[0]["beta"] >= 0.8 and abs(nav_sl[-1]["beta"]) <= 0.2 and abs(nav_sl[1]["beta"]) <= 0.2)
    price_in = A["price_only"]["real"]["pnl_in_pct"]
    e1_explains = bool(out["misaligned"]["share_total"] >= 0.5 or (cr_aligned <= cr_plc))
    e1_undecided_by_class = bool(amb_share > 0.5)
    e3_explains = bool(disp["flag_any_dispute"]["share_total"] >= 0.5 and disp["undisputed"]["CR_total"] <= cr_plc)
    art = []
    if cr_real <= cr_plc:
        art.append("(i) not ex-date specific" + ("; price-only beats placebo: accounting transfer" if cr_real_x > cr_plc_x else ""))
    if Dp >= 0.5:
        art.append("(ii) data-cause share >= 50%")
    if cr_clean <= cr_plc:
        art.append("(iii) CR_clean <= placebo CR")
    if e1_undecided_by_class and not slope_aligned:
        art.append("explanation 1 undecided by class and the pooled slope is not aligned")
    real = (cr_real > cr_plc and t_ex >= 2.0 and Dp < 0.2 and cr_clean > cr_plc and price_in > 0
            and (slope_aligned or not e1_undecided_by_class))
    v = "ARTIFACT" if art else ("REAL" if real else "MIXED")
    out.update(CR_real_total=cr_real, CR_placebo_total=cr_plc, CR_real_price=cr_real_x, CR_placebo_price=cr_plc_x,
               excess_nw_t_total=t_ex, data_cause_share=Dp, CR_clean=cr_clean, CR_aligned=cr_aligned,
               ambiguous_unmeasurable_share=amb_share, pooled_slope_aligned=slope_aligned,
               e1_explains=e1_explains, e1_undecided_by_class=e1_undecided_by_class, e3_explains=e3_explains,
               price_only_in_window_pct=price_in, artifact_reasons=art, verdict_by_rule=v)
    say(f"\n  misaligned (-1, +1, none): in-window total share {out['misaligned']['share_total']:.1%}, price-only "
        f"{out['misaligned']['share_price']:.1%}, gross {out['misaligned']['share_gross']:.1%}")
    say(f"  ambiguous + unmeasurable: total share {amb_share:.1%}; pooled NAV slope aligned: {slope_aligned}")
    say(f"  data-cause union (misaligned | disputed | stale print): total share {Dp:.1%}, price-only "
        f"{out['data_cause']['share_price']:.1%}, gross {out['data_cause']['share_gross']:.1%}")
    say(f"  clean complement: total share {out['clean']['share_total']:.1%}, CR_clean {cr_clean:.2f}")
    say(f"  CR real {cr_real:.2f} vs placebo {cr_plc:.2f} (total); {cr_real_x:.2f} vs {cr_plc_x:.2f} (price-only); "
        f"excess NW t {t_ex:+.2f}; CR aligned-class {cr_aligned:.2f}")
    say(f"  E1 explains: {e1_explains}; E3 explains: {e3_explains}; artifact reasons: {art or 'none'}")
    say(f"  VERDICT BY THE DECLARED RULE: {v}")
    return out


# --------------------------------------------------------------------------- the 13-name core

def core_book(P_) -> dict:
    T, R = bf.build_targets(source=(P_["core_px"], P_["core_nav"]))
    assert_fit(T, R)
    H = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)
    Rt = bf.total_returns(R)
    assert_fit(Rt)
    held = H.shift(2).fillna(0.0)
    hs = held.abs().sum(axis=1)
    p0 = hs.index[hs > 0][0]
    sl = slice(p0, FIT_END)
    pt = bf.evaluate(H, Rt)["pnl"].loc[sl]
    pp = bf.evaluate(H, R)["pnl"].loc[sl]
    Ct, Cx, g = (held * Rt).loc[sl], (held * R).loc[sl], held.abs().loc[sl]
    if not np.allclose(Ct.sum(axis=1).to_numpy(), pt.to_numpy(), rtol=0, atol=1e-15):
        raise AssertionError("core cells do not sum")
    dist = pd.read_parquet(TREE / "data/cef/cef_distributions.parquet")
    dist["ex_date"] = pd.to_datetime(dist["ex_date"])
    exd = dist.loc[(dist["amount"] > 0) & (dist["ex_date"] <= FIT_END), ["ticker", "ex_date"]].rename(
        columns={"ex_date": "date"})
    cols = list(H.columns)
    pos = ex_positions(H.index, cols, exd)
    W = window_from_positions(H.index, cols, pos).loc[sl]
    Wc4 = c4.ex_window_mask(H.index, cols, exd).loc[sl]
    if not W.equals(Wc4):
        raise AssertionError("core window differs from c4.ex_window_mask")
    Wp = window_from_positions(H.index, cols, {t: p + PLACEBO_SHIFT for t, p in pos.items()}).loc[sl] & ~W
    Wm = window_from_positions(H.index, cols, {t: p - PLACEBO_SHIFT for t, p in pos.items()}).loc[sl] & ~W
    base = ~(W | Wp | Wm)
    out = dict(first_held=str(p0.date()), last=str(pt.index[-1].date()), sessions=len(pt),
               sr_total=c4.sr_of(pt), sr_price=c4.sr_of(pp), ann_total_pct=float(pt.mean() * 252 * 100),
               ann_price_pct=float(pp.mean() * 252 * 100))
    say(f"  core (spec v7, 13 names, band {BAND_WIDTH}, cap {MAX_GROSS_STRESS}): {p0.date()}..{pt.index[-1].date()}, "
        f"{len(pt)} sessions; gross SR total {out['sr_total']:.3f} ({out['ann_total_pct']:.2f}%/yr), price-only "
        f"{out['sr_price']:.3f} ({out['ann_price_pct']:.2f}%/yr); ex-dates from data/cef/cef_distributions.parquet")
    for basis, C in (("total", Ct), ("price_only", Cx)):
        out[basis] = dict(real=wstats(C, g, W, base), placebo_pooled=wstats(C, g, Wp | Wm, base))
        say(f"   {basis}:")
        say(fmt_w("real window [0,2]", out[basis]["real"]))
        say(fmt_w("placebo pooled +-5", out[basis]["placebo_pooled"]))
    return out


if __name__ == "__main__":
    sys.exit(main())
