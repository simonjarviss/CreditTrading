"""Three research-path data guards (zero trials; team lead's rulings of 2026-10-19).

    python3 scripts/cef/data_guards.py scan          # every hit in data/cef/ and data/cef_families/; writes
                                                     # results/cef/data_guards/scan_output_2026-10-19.txt + hits CSV
    python3 scripts/cef/data_guards.py scan-splits   # every recorded split, labelled by basis (guard 3); writes
                                                     # results/cef/data_guards/split_basis_scan_2026-10-20.txt + CSV

WHY THIS EXISTS
---------------
C4's holdout (CEF trial 52, opened once on 2026-10-18) booked four IGR bars of
`data/cef_families/cef_prices.parquet` -- 2026-07-29, 08-04, 08-07 and 08-11 --
that were on the post-split basis (about 14.2) inside a raw pre-split series
(about 4.7), weeks before IGR's 1:3 reverse split of 2026-09-08, with the NAV
flat. The declared yfinance formula booked each as +200% and then -66.7%; the
band held a stale IGR short through them, and they cost -10.87% of capital
(`results/cef/C4_RESULT_2026-10-14.md` §8). Two failures let them through, and
each guard here closes one:

1. Nothing on the return path looked at them. `split_like_spikes` finds a close
   that jumps by a split-like factor and comes back within a short window while
   the NAV does not make the move; `guard_closes` RAISES (`SpikeRevertError`),
   naming every offending (ticker, date, ratio), unless a recorded rulings file
   says what to do with each bar. C4's `yf_total_returns` calls it.
2. Stage 0 had flagged all eight IGR rows (Q5) on 2026-10-14, and nobody ruled
   on the flags before P&L was formed. `require_stage0_rulings` refuses
   (`Stage0BlockError`), naming the flags, while any Stage-0 flag lacks a
   recorded ruling in the trial's rulings file. A trial script calls it before
   it forms any P&L.
3. (Added 2026-10-20.) A recorded split applied to a close the vendor had already
   split-adjusted books the factor k twice: BTO, TYG, NXG and EMO in C4's fit, at
   -75% to -80%, through the formula the spike guard leaves alone.
   `guard_split_basis` RAISES (`SplitBasisError`), naming (ticker, ex-date,
   factor), when the series makes no split-sized step on the ex-date, so k would
   create one. Only a recorded split rulings file overrides it.
   `band_frontier.total_returns` calls it, and so does C4's NAV catch-up.

NO SILENT REPAIR. Neither guard alters a number on its own. The only alteration
is a ruled treatment, read from a file that names who ruled, when, and why, and
the corrected series is re-scanned before it is returned. A ruling that names a
bar the scan no longer finds raises too (the data changed under the ruling).

Synthetic tests: `scripts/cef/tests/test_data_guards.py`. The hits in the
panels on 2026-10-19: `results/cef/DATA_GUARDS_2026-10-19.md`.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# --------------------------------------------------------------------------- the spike-and-revert rule
#
# THE TOLERANCE, DERIVED (not swept). A bar on the wrong basis is the true close
# times the split factor f exactly: a vendor's split-adjusted history is the raw
# print times the split ratio. So the close ratio the formula books on the bar is
#     C(t) / C(t-1) = f * (1 + e),
# where e is the fund's GENUINE one-day move that day. The tolerance around f
# must therefore admit any genuine one-day move the desk treats as ordinary, and
# no more. The desk already declares that line: P2's Q5 screen flags |r| > 15%
# as an outlier (`results/xasset/PREREG_XASSET_SLATE_2026-10-12.md` §Q5, cited by
# C4's pre-registration §4.5; `c4_families.Q5_ABS`, which a test pins equal to
# this constant). A move beyond it is not ordinary by the desk's own rule, so
#     tau = ln(1 + 0.15) = 0.1398 in log ratio,
# i.e. a ratio within [f / 1.15, f * 1.15]. Two checks on that value, neither of
# which chose it: (i) tau < ln(3/2) / 2 = 0.2027, so the bands around the two
# commonest split factors, 2 and 3, do not overlap and the factor a bar is ruled
# on is unambiguous; (ii) tau < ln 2, so a ratio of 1 (no defect) is never
# split-like. For factors of 4 and above the bands touch, and every jump of
# about x3.5 or more is split-like: no genuine one-day CEF move is that large.
#
# The same tau decides the two other comparisons, for the same reason:
# * NAV "makes the move" when its own one-day log ratio over the same two bars
#   is within tau of the price's. If it does, price and NAV agree, the bar is a
#   genuine (if extraordinary) day or a basis change in both panels, and this
#   guard is not the place to judge it. If it does not -- including a flat NAV,
#   the IGR case -- the price moved by a split factor that the fund's assets did
#   not. Where NAV is missing on either bar the price alone decides (the task's
#   "where available"), so a fund with no NAV is guarded, not exempted.
# * The spike REVERTS when a later step within the window is split-like in the
#   opposite direction AND brings the close back to within tau of its level
#   before the jump. The round trip, not the size of the return step, is the
#   test, so a genuine move on either bar cannot make the factors disagree.
#
# THE WINDOW is a choice, stated as one: REVERT_WINDOW = 5 sessions (one trading
# week) is the longest wrong-basis run this guard calls a spike. Each IGR bar
# reverted the next session. A wrong-basis run longer than a week is a level
# break, not a spike; it is still REPORTED by `split_like_spikes` (the
# `unreverted` table, which the scan prints), so nothing beyond the window is
# silent -- it is not raised, because an unrecorded genuine split looks the same
# from the price alone. The scan reports the hit count at W = 1 and W = 21 and
# at tau/2 and 2*tau beside the declared values, computed after the choice and
# never used to make it.
#
# SPLITS. Returns are booked on the split-corrected ratio C(t)/C(t-1) * k(t)
# (`band_frontier.total_returns`), with k the share-count multiplier of the
# actions file (yfinance codes IGR's 1:3 reverse split as 0.3333). The guard
# scans that same quantity: each close (and NAV) is multiplied by the product of
# the multipliers whose ex-date is on or before it, so a recorded split is not a
# jump, and a wrong-basis bar just before a split date is still a spike.
GENUINE_MOVE_MAX = 0.15
SPLIT_TOL = math.log1p(GENUINE_MOVE_MAX)
REVERT_WINDOW = 5
TREATMENTS = ("rebase", "book_as_is")
HIT_COLUMNS = ["ticker", "date", "run_end", "revert_date", "bars", "ratio", "factor", "revert_ratio",
               "round_trip", "nav_ratio"]


class SpikeRevertError(ValueError):
    """A split-like spike-and-revert bar with no recorded ruling, or a ruling that does not fit."""


class Stage0BlockError(RuntimeError):
    """A Stage-0 flag without a recorded ruling; no P&L may be formed."""


def _iso(d) -> str:
    return pd.Timestamp(d).strftime("%Y-%m-%d")


def _cum_split(dates: pd.DatetimeIndex, sp: pd.DataFrame | None, ticker: str) -> np.ndarray:
    """K(d) = the product of `ticker`'s share-count multipliers with ex-date <= d (1.0 before any)."""
    K = np.ones(len(dates))
    if sp is None or not len(sp):
        return K
    s = sp[sp["ticker"] == ticker]
    for e, k in zip(pd.to_datetime(s["ex_date"]), s["stock_split"].astype(float)):
        if not (k > 0):
            raise ValueError(f"{ticker}: split multiplier {k} on {_iso(e)} is not positive")
        K[dates >= e] *= k
    return K


def split_like_spikes(close: pd.DataFrame, nav: pd.DataFrame | None = None, splits: pd.DataFrame | None = None,
                      *, tol: float = SPLIT_TOL, window: int = REVERT_WINDOW) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(hits, unreverted) for a wide panel of RAW closes (date x ticker; NaN = no bar).

    Per ticker, on its own consecutive bars (so a bar after a gap is still seen), on
    the split-corrected log close a = ln(C * K):
      * a JUMP is a step x = a[t] - a[t-1] with |x| within `tol` of ln m for an
        integer m >= 2 (a factor m up, or 1/m down) whose NAV, where the NAV has
        both bars, does not make the same move (|y - x| > tol);
      * it is a HIT if a later step within `window` bars is split-like in the
        opposite direction and returns a to within `tol` of a[t-1]. The bars from
        the jump to the one before the revert are the wrong-basis run; the revert
        step is consumed, so the next bar is never read as a new jump;
      * a jump with no such revert is UNREVERTED (reported, never raised).
    `nav` is wide (date x ticker) or None; `splits` is `ex_date ticker stock_split`
    or None. A non-positive close raises: the log ratio is undefined, and skipping
    it would be the silent path this guard exists to close.

    `factor` is m (the jump went up by m) or 1/m (down); `ratio`, `revert_ratio`
    and `nav_ratio` are split-corrected one-day ratios; `round_trip` is the
    corrected close after the revert over the one before the jump."""
    hits, unrev = [], []
    for t in close.columns:
        s = close[t].dropna()
        if len(s) < 3:
            continue
        bad = s[~(s > 0)]
        if len(bad):
            raise ValueError(f"{t}: non-positive close on {[_iso(d) for d in bad.index[:10]]}; "
                             "a log ratio is undefined there and this guard will not skip it")
        K = _cum_split(s.index, splits, t)
        a = np.log(s.to_numpy(dtype=float) * K)
        x = np.diff(a)
        if nav is not None and t in nav.columns:
            nv = nav[t].reindex(s.index).to_numpy(dtype=float) * K
            with np.errstate(divide="ignore", invalid="ignore"):
                y = np.diff(np.log(np.where(nv > 0, nv, np.nan)))
        else:
            y = np.full(len(x), np.nan)
        m = np.rint(np.exp(np.abs(x)))
        like = (m >= 2) & (np.abs(np.abs(x) - np.log(np.maximum(m, 1.0))) <= tol)
        consumed: set[int] = set()
        for i in np.flatnonzero(like):
            if i in consumed:
                continue
            if np.isfinite(y[i]) and abs(y[i] - x[i]) <= tol:
                continue                                    # the NAV made the same move
            f = float(m[i]) if x[i] > 0 else 1.0 / float(m[i])
            rev = None
            for j in range(i + 1, min(i + window, len(x) - 1) + 1):
                if like[j] and np.sign(x[j]) == -np.sign(x[i]) and abs(a[j + 1] - a[i]) <= tol:
                    rev = j
                    break
            base = dict(ticker=t, date=s.index[i + 1], ratio=float(np.exp(x[i])), factor=f,
                        nav_ratio=float(np.exp(y[i])) if np.isfinite(y[i]) else np.nan)
            if rev is None:
                unrev.append(base)
                continue
            consumed.add(rev)
            hits.append(dict(base, run_end=s.index[rev], revert_date=s.index[rev + 1], bars=rev - i,
                             revert_ratio=float(np.exp(x[rev])), round_trip=float(np.exp(a[rev + 1] - a[i]))))
    H = pd.DataFrame(hits, columns=HIT_COLUMNS)
    U = pd.DataFrame(unrev, columns=["ticker", "date", "ratio", "factor", "nav_ratio"])
    return H, U


def describe_hits(H: pd.DataFrame) -> str:
    """Every hit as `(ticker, date, ratio x.xxx, factor f, reverts <date>, NAV ratio y.yyy|none)`."""
    out = []
    for r in H.itertuples():
        fl = f"{int(r.factor)}" if r.factor >= 1 else f"1/{int(round(1 / r.factor))}"
        nv = "no NAV" if pd.isna(r.nav_ratio) else f"NAV ratio {r.nav_ratio:.3f}"
        out.append(f"({r.ticker}, {_iso(r.date)}, ratio {r.ratio:.3f}, factor {fl}, {r.bars} bar(s), "
                   f"reverts {_iso(r.revert_date)}, {nv})")
    return "; ".join(out)


# --------------------------------------------------------------------------- the recorded rulings

def load_bar_rulings(path: Path | str) -> tuple[pd.DataFrame, dict]:
    """The rulings file: JSON with `ruled_by`, `ruled_on` (ISO date), `record` (where the
    ruling is written down) and `bars`, each {ticker, date, run_end, factor, treatment,
    reason}. `date` is the first wrong-basis bar, `run_end` the last; `factor` the
    detected split factor (m, or 1/m) the ruling was made on. Treatments:
      rebase      -- the bar is on the wrong basis: divide each close of the run by
                     `factor`. Exact when the vendor's bar is the true print times
                     the split ratio, which is what a basis mix is.
      book_as_is  -- book the close unchanged. For a bar ruled genuine, or for a
                     script whose purpose is to reproduce a committed computation
                     that booked it; the reason must say which.
    Anything missing or malformed raises: an unreadable ruling is not a ruling."""
    p = Path(path)
    if not p.exists():
        raise SpikeRevertError(f"bar rulings file {p} does not exist")
    doc = json.loads(p.read_text())
    for k in ("ruled_by", "ruled_on", "record", "bars"):
        if not doc.get(k):
            raise SpikeRevertError(f"{p.name}: `{k}` is missing or empty; a ruling names who ruled, when and where")
    pd.Timestamp(doc["ruled_on"])
    rows = []
    for b in doc["bars"]:
        miss = [k for k in ("ticker", "date", "run_end", "factor", "treatment", "reason") if not b.get(k)]
        if miss:
            raise SpikeRevertError(f"{p.name}: a bar ruling lacks {miss}: {b}")
        if b["treatment"] not in TREATMENTS:
            raise SpikeRevertError(f"{p.name}: treatment {b['treatment']!r} is not one of {TREATMENTS}")
        f = float(b["factor"])
        m = f if f >= 1 else 1.0 / f
        if not (m >= 2 and abs(m - round(m)) < 1e-9):
            raise SpikeRevertError(f"{p.name}: factor {b['factor']} is not an integer >= 2 or its reciprocal")
        rows.append(dict(ticker=str(b["ticker"]), date=pd.Timestamp(b["date"]), run_end=pd.Timestamp(b["run_end"]),
                         factor=f, treatment=b["treatment"], reason=str(b["reason"])))
    R = pd.DataFrame(rows)
    if R.duplicated(["ticker", "date"]).any():
        raise SpikeRevertError(f"{p.name}: two rulings for one (ticker, date)")
    return R, doc


def guard_closes(close: pd.DataFrame, *, cols, lo, hi, nav: pd.DataFrame | None, splits: pd.DataFrame | None,
                 ex_dates: pd.DataFrame | None = None, rulings: Path | str | None = None,
                 context: str = "") -> tuple[pd.DataFrame, pd.DataFrame]:
    """(close with the ruled treatments applied, the log of what was applied).

    Scans `cols` of the raw close panel. A hit is IN SCOPE when its run, jump to
    revert, touches [lo, hi] -- the window whose returns the caller books. Raises
    `SpikeRevertError`:
      * naming every in-scope hit that no ruling covers;
      * on a ruling whose bar is a hit but whose `run_end` or `factor` is not the
        hit's (it was made on other data);
      * on a ruling for a ticker in `cols` dated inside [lo, hi] that matches no
        hit (the bar changed under it; remove the ruling or rule again);
      * when a rebased close is the prior close of an ex-date in `ex_dates`
        (`ex_date ticker amount`): the yield's denominator is read from the
        price file, which this function does not rewrite, so the ruling does not
        cover it;
      * when, after the treatments, an in-scope hit remains that is not ruled
        `book_as_is` (the treatment did not clean the bar).
    With no in-scope hit and no ruling, the input frame is returned unchanged.
    """
    cols = [c for c in cols if c in close.columns]
    lo, hi = pd.Timestamp(lo), pd.Timestamp(hi)
    H, _ = split_like_spikes(close[cols], nav, splits)
    inscope = H[(H["revert_date"] >= lo) & (H["date"] <= hi)] if len(H) else H
    if rulings is None:
        R = pd.DataFrame(columns=["ticker", "date", "run_end", "factor", "treatment", "reason"])
        src = "no rulings file"
    else:
        R, _doc = load_bar_rulings(rulings)
        src = Path(rulings).name
    key = lambda df: set(zip(df["ticker"], pd.to_datetime(df["date"])))      # noqa: E731
    ruled = key(R)
    unruled = inscope[[(t, d) not in ruled for t, d in zip(inscope["ticker"], inscope["date"])]]
    if len(unruled):
        raise SpikeRevertError(
            f"{context}: {len(unruled)} split-like spike-and-revert bar(s) with no recorded ruling ({src}): "
            f"{describe_hits(unruled)}. Each is a close that jumped by a split factor and came back within "
            f"{REVERT_WINDOW} sessions while the NAV did not make the move; booked as is, it is a phantom "
            "return (C4's holdout, 2026-10-18: -10.87% of capital). Fix the bar in the fetcher, or record a "
            "ruling (`load_bar_rulings`) and pass its file.")
    hk = {(t, d): r for t, d, r in zip(H["ticker"], H["date"], H.itertuples())}
    for r in R.itertuples():
        h = hk.get((r.ticker, r.date))
        if h is None:
            if r.ticker in cols and lo <= r.date <= hi:
                raise SpikeRevertError(f"{context}: ruling ({r.ticker}, {_iso(r.date)}) in {src} matches no "
                                       "spike-and-revert bar in this panel; the data changed under it")
            continue
        if h.run_end != r.run_end or abs(h.factor - r.factor) > 1e-9:
            raise SpikeRevertError(f"{context}: ruling ({r.ticker}, {_iso(r.date)}) in {src} was made on a run to "
                                   f"{_iso(r.run_end)} at factor {r.factor:g}; the panel shows a run to "
                                   f"{_iso(h.run_end)} at factor {h.factor:g}")
    out = close
    log = []
    for r in R[R["treatment"] == "rebase"].itertuples():
        if (r.ticker, r.date) not in hk:
            continue
        if out is close:
            out = close.copy()
        s = out[r.ticker]
        run = s.loc[r.date:r.run_end].dropna().index
        if ex_dates is not None and len(ex_dates):
            e = pd.to_datetime(ex_dates.loc[ex_dates["ticker"] == r.ticker, "ex_date"])
            valid = s.dropna().index
            for d in run:
                nxt = valid[valid > d]
                if len(nxt) and ((e > d) & (e <= nxt[0])).any():
                    raise SpikeRevertError(f"{context}: ({r.ticker}, {_iso(d)}) is ruled `rebase` and is the prior "
                                           "close of an ex-date; the distribution yield reads that close from the "
                                           "price file, which the ruling does not cover")
        for d in run:
            out.at[d, r.ticker] = float(out.at[d, r.ticker]) / r.factor
            log.append(dict(ticker=r.ticker, date=d, treatment="rebase", factor=r.factor))
    for r in R[R["treatment"] == "book_as_is"].itertuples():
        if (r.ticker, r.date) in hk:
            log.append(dict(ticker=r.ticker, date=r.date, treatment="book_as_is", factor=r.factor))
    if out is not close:
        H2, _ = split_like_spikes(out[cols], nav, splits)
        left = H2[(H2["revert_date"] >= lo) & (H2["date"] <= hi)] if len(H2) else H2
        asis = key(R[R["treatment"] == "book_as_is"])
        left = left[[(t, d) not in asis for t, d in zip(left["ticker"], left["date"])]]
        if len(left):
            raise SpikeRevertError(f"{context}: after the ruled treatments these bars still spike and revert: "
                                   f"{describe_hits(left)}")
    return out, pd.DataFrame(log, columns=["ticker", "date", "treatment", "factor"])


# --------------------------------------------------------------------------- a recorded split on an adjusted series
#
# THE DEFECT (C4 holdout review, 2026-10-19; this guard built 2026-10-20 on the team lead's word of
# 2026-10-19). `band_frontier.total_returns` books r = (1 + r_px) * k - 1 on a recorded split's
# ex-date. That is right when the close is RAW: it steps by 1/k there and k undoes the step. It is
# wrong when the vendor had ALREADY split-adjusted the history, so the close has no step: k is then
# booked a second time, as a phantom return of k - 1. yfinance back-adjusts its close for every
# split it knows of on the day of the fetch (`scripts/data/cef_families_quality.split_factor` relies
# on that), while its actions file still records the split. In C4's fit this booked BTO 2008-12-30,
# TYG 2020-05-01, NXG 2020-06-15 and EMO 2020-07-28 at -74.7% to -80.3%. On each of those dates
# CRSP's raw print steps by 1/k and yfinance's close does not. Only the report-only R-yf row moved
# (1.131 -> 1.130), and nothing raised (results/cef/DATA_GUARDS_2026-10-19.md §6 item 2).
#
# THE RULE is applied to the step the formula actually books. It looks at each cell where a factor
# k != 1 multiplies a finite raw one-step return r: exactly the cells `total_returns` changes, so a
# split on a day with no return, which multiplies nothing, is not judged. With x = ln(1 + r):
#     raw basis:       x = -ln k + e
#     adjusted basis:  x = e
# Here e is the fund's genuine move that day, and |e| <= tau, the desk's line for an ordinary day.
# This is the spike guard's tau (SPLIT_TOL above), derived there and not re-chosen here. The two
# readings cannot both hold when |ln k| > 2 tau = ln(1.15^2), i.e. when k lies outside
# [0.756, 1.3225]: every reverse split, and every forward split of 4:3 or more. For such a split:
#     |x| <= tau          ADJUSTED. Applying k creates a step of about k (or 1/k) that the raw
#                         series did not have. RAISES `SplitBasisError`, naming (ticker, ex-date,
#                         factor), unless a recorded ruling treats the cell.
#     |x + ln k| <= tau   raw. k is right; nothing happens.
#     neither             the step fits neither basis (for example, a split recorded on the wrong
#                         day, or a genuine day beyond the desk's line on the ex-date). Reported by
#                         the scan, never raised: it is not this defect, and the guard was not asked
#                         to judge it.
# BELOW 2 tau THE GUARD HAS NO POWER, and says so rather than guess. A 1.029 split is smaller than
# an ordinary day, and the price alone cannot tell the two bases apart. `split_basis_check` labels
# such a cell `undecidable`, the scan prints every one, and nothing is raised. Raising there would
# raise on the live book's one recorded split (BIT 2025-08-19, 1.029), whose raw close does step
# (band_frontier.split_factor's docstring: 14.47 -> 13.84). It would raise on a correct series
# because of a test that cannot see.
#
# THE OVERRIDE is a recorded rulings file, as for the spike guard (`load_split_rulings`): who
# ruled, when, where it is written down, and one entry per (ticker, ex-date, series), with the
# factor the ruling was made on. The treatments:
#     drop_split   the series is already on the post-split basis on that day, so the cell's factor
#                  is set to 1 and the booked step is the series' own.
#     book_as_is   apply k as recorded. Used for a script whose purpose is to reproduce a committed
#                  computation that booked it; the reason must say so.
# `series` is "close" or "nav". The two can sit on different bases for one fund (AWP 2026-02-09:
# yfinance's close is adjusted, its NAV is not), so a ruling names the one it was made on.
SPLIT_DECIDABLE = 2 * SPLIT_TOL
# `to_nav_basis` (2026-11-04) is the LIVE FETCH's treatment only (THE LIVE FETCH'S PRICE BASIS,
# below): `guard_split_basis`, the research path, refuses a file that carries one.
SPLIT_TREATMENTS = ("drop_split", "book_as_is", "to_nav_basis")
SPLIT_SERIES = ("close", "nav")
SPLIT_COLUMNS = ["ticker", "ex_date", "factor", "raw_ratio", "booked_ratio", "basis"]


class SplitBasisError(ValueError):
    """A recorded split applied to a series already on the post-split basis, with no recorded ruling."""


def split_basis_check(R: pd.DataFrame, k: pd.DataFrame, *, tol: float = SPLIT_TOL) -> pd.DataFrame:
    """Every cell where `k` != 1 multiplies a finite raw one-step return of `R`, labelled.

    `R` is the raw one-step return the factor multiplies (`total_returns`'s `R`), `k` the
    share-count multipliers on the same index and columns (`band_frontier.split_factor`).
    `basis` is one of:
      * `adjusted`: |ln k| > 2 tol and |ln(1 + r)| <= tol. The series has no step and k makes
        one. This is the defect the guard raises on.
      * `raw`: |ln k| > 2 tol and |ln(1 + r) + ln k| <= tol.
      * `neither`: |ln k| > 2 tol and the step fits neither basis (reported only).
      * `undecidable`: |ln k| <= 2 tol, where the price cannot tell the two bases apart (reported
        only).
    `raw_ratio` is 1 + r. `booked_ratio` is (1 + r) * k, the ratio the formula books.
    A non-positive k, or 1 + r <= 0 on a split cell, raises: the log is undefined there, and
    skipping the cell would be the silent path this guard exists to close."""
    if not (R.index.equals(k.index) and R.columns.equals(k.columns)):
        raise ValueError("split_basis_check: R and k must share one index and one column set")
    kv, rv = k.to_numpy(dtype=float), R.to_numpy(dtype=float)
    cells = np.argwhere((kv != 1.0) & np.isfinite(rv))
    rows = []
    for i, j in cells:
        f, r = kv[i, j], rv[i, j]
        t, d = R.columns[j], R.index[i]
        if not (f > 0):
            raise ValueError(f"{t}: split multiplier {f} on {_iso(d)} is not positive")
        if not (1.0 + r > 0):
            raise ValueError(f"{t}: return {r} on the split date {_iso(d)} is <= -100%; a log ratio is undefined")
        x, lk = math.log1p(r), math.log(f)
        if abs(lk) <= 2 * tol:
            basis = "undecidable"
        elif abs(x) <= tol:
            basis = "adjusted"
        elif abs(x + lk) <= tol:
            basis = "raw"
        else:
            basis = "neither"
        rows.append(dict(ticker=t, ex_date=d, factor=float(f), raw_ratio=float(math.exp(x)),
                         booked_ratio=float(math.exp(x + lk)), basis=basis))
    return pd.DataFrame(rows, columns=SPLIT_COLUMNS)


def _factor_label(f: float) -> str:
    return f"{f:g}" if f >= 1 else f"1/{1 / f:.4g}"


def describe_split_hits(H: pd.DataFrame) -> str:
    """Every hit as `(ticker, ex-date, factor k, raw ratio x.xxx, booked ratio y.yyy)`."""
    return "; ".join(f"({r.ticker}, {_iso(r.ex_date)}, factor {_factor_label(r.factor)}, raw ratio "
                     f"{r.raw_ratio:.3f}, booked ratio {r.booked_ratio:.3f})" for r in H.itertuples())


def load_split_rulings(path: Path | str) -> tuple[pd.DataFrame, dict]:
    """The split rulings file: JSON with `ruled_by`, `ruled_on` (ISO date), `record` (where the
    ruling is written down) and `splits`, each {ticker, ex_date, factor, series, treatment, reason}.
    `factor` is the recorded multiplier the ruling was made on; `series` is "close" or "nav";
    `treatment` is `drop_split` or `book_as_is` (see the rule above). Anything missing or malformed
    raises: an unreadable ruling is not a ruling."""
    p = Path(path)
    if not p.exists():
        raise SplitBasisError(f"split rulings file {p} does not exist")
    doc = json.loads(p.read_text())
    for k in ("ruled_by", "ruled_on", "record", "splits"):
        if not doc.get(k):
            raise SplitBasisError(f"{p.name}: `{k}` is missing or empty; a ruling names who ruled, when and where")
    pd.Timestamp(doc["ruled_on"])
    rows = []
    for s in doc["splits"]:
        miss = [k for k in ("ticker", "ex_date", "factor", "series", "treatment", "reason") if not s.get(k)]
        if miss:
            raise SplitBasisError(f"{p.name}: a split ruling lacks {miss}: {s}")
        if s["treatment"] not in SPLIT_TREATMENTS:
            raise SplitBasisError(f"{p.name}: treatment {s['treatment']!r} is not one of {SPLIT_TREATMENTS}")
        if s["series"] not in SPLIT_SERIES:
            raise SplitBasisError(f"{p.name}: series {s['series']!r} is not one of {SPLIT_SERIES}")
        f = float(s["factor"])
        if not (f > 0):
            raise SplitBasisError(f"{p.name}: factor {s['factor']} is not positive")
        rows.append(dict(ticker=str(s["ticker"]), ex_date=pd.Timestamp(s["ex_date"]), factor=f,
                         series=s["series"], treatment=s["treatment"], reason=str(s["reason"])))
    R = pd.DataFrame(rows)
    if R.duplicated(["ticker", "ex_date", "series"]).any():
        raise SplitBasisError(f"{p.name}: two rulings for one (ticker, ex_date, series)")
    return R, doc


def guard_split_basis(R: pd.DataFrame, k: pd.DataFrame, *, rulings: Path | str | None = None,
                      series: str = "close", context: str = "") -> pd.DataFrame:
    """`k` with the ruled treatments applied: the factor the caller then multiplies `1 + R` by.

    Raises `SplitBasisError`:
      * naming every `adjusted` cell (`split_basis_check`) that no ruling for `series` covers;
      * on a ruling for `series` whose cell is in this frame but no longer carries its factor (the
        actions changed under it), or carries a finite return that is not `adjusted` (the series
        changed under it). Remove the ruling or rule again. A ruled cell with no return in this
        frame multiplies nothing, and is not judged here.
    With no hit and no `drop_split` ruling in the frame, the input `k` is returned as the same
    object, so the caller's arithmetic is the old formula's, bit for bit."""
    if series not in SPLIT_SERIES:
        raise ValueError(f"series {series!r} is not one of {SPLIT_SERIES}")
    C = split_basis_check(R, k)
    hits = C[C["basis"] == "adjusted"]
    if rulings is None:
        Rl = pd.DataFrame(columns=["ticker", "ex_date", "factor", "series", "treatment", "reason"])
        src = "no split rulings file"
    else:
        Rl, _doc = load_split_rulings(rulings)
        Rl = Rl[Rl["series"] == series]
        src = Path(rulings).name
    ruled = set(zip(Rl["ticker"], pd.to_datetime(Rl["ex_date"])))
    unruled = hits[[(t, d) not in ruled for t, d in zip(hits["ticker"], hits["ex_date"])]]
    if len(unruled):
        raise SplitBasisError(
            f"{context}: {len(unruled)} recorded split(s) applied to a {series} series already on the post-split "
            f"basis, with no recorded ruling ({src}): {describe_split_hits(unruled)}. On each ex-date the raw "
            f"{series} made no split-sized step (within ln(1.15) of none), so the factor would book a step of "
            "about k that the series did not have (C4's fit booked BTO, TYG, NXG and EMO at -75% to -80% this "
            "way). Fix the fetch, or record a ruling (`load_split_rulings`) and pass its file.")
    hk = {(t, d): r for t, d, r in zip(C["ticker"], C["ex_date"], C.itertuples())}
    out = k
    for r in Rl.itertuples():
        if r.treatment == "to_nav_basis":
            raise SplitBasisError(f"{context}: ruling ({r.ticker}, {_iso(r.ex_date)}) in {src} is `to_nav_basis`, "
                                  "the live fetch's treatment (load_fetch_split_rulings), not a return treatment")
        if r.ticker not in k.columns or r.ex_date not in k.index:
            continue
        kf = float(k.at[r.ex_date, r.ticker])
        if abs(kf - r.factor) > 1e-9 * max(1.0, abs(r.factor)):
            raise SplitBasisError(f"{context}: ruling ({r.ticker}, {_iso(r.ex_date)}, {series}) in {src} was made on "
                                  f"factor {_factor_label(r.factor)}; this frame applies {_factor_label(kf)} there")
        h = hk.get((r.ticker, r.ex_date))
        if h is None:
            continue                                            # no return on the cell: k multiplies nothing
        if h.basis != "adjusted":
            raise SplitBasisError(f"{context}: ruling ({r.ticker}, {_iso(r.ex_date)}, {series}) in {src} names a "
                                  f"split the {series} now reads as `{h.basis}` (raw ratio {h.raw_ratio:.3f}); "
                                  "the data changed under the ruling")
        if r.treatment == "drop_split":
            if out is k:
                out = k.copy()
            out.at[r.ex_date, r.ticker] = 1.0
    return out


# --------------------------------------------------------------------------- the live fetch's price basis (C4)
#
# THE DEFECT (2026-11-03, C4's first nightly fetch at release-20261103-5). yfinance's `Close` with
# `auto_adjust=False` is split-adjusted after the fact, and Yahoo applies the adjustment LATE and
# all at once: IGR's 1:3 reverse split of 2026-09-08 was not yet in the families build of
# 2026-10-12 (raw closes about 4.7, bar four), and by 2026-11-03 every pre-split close in the
# fetch's six-month window was served times 3.0 (14.04 on 05-04). IGR's NAV symbol was NOT
# adjusted (4.64 on 05-04). `fetch_daily --data-book c4` replaced the window with the adjusted
# closes, so IGR's discount read about +200% for four months, its 252-day z went to -0.79 on the
# artifact, and the 11-04 plan bought 520 IGR on it (team lead 2026-11-03: "Hold C4 one day, fix
# IGR"). The spike guard did not see it: the closes did not jump and revert, they STEPPED at the
# window's start and then ran flat across the split while the NAV stepped.
#
# THE RULE. Price and NAV must sit on ONE share basis for the discount. C4's panels are on the
# raw, as-traded basis, the NAV's: the seed's closes are raw, and the NAV symbols are served
# unadjusted. So a fetched close on a split's pre-ex dates that Yahoo has split-adjusted is put
# back on the NAV's basis, times the split's yfinance multiplier f (0.3333 for IGR: raw =
# adjusted x f; the volume / f), and ONLY under a recorded ruling (`load_fetch_split_rulings`:
# the split rulings file's schema, treatment `to_nav_basis`). Whether a given row is adjusted is
# MEASURED on every fetch, never assumed, because Yahoo's timing varies: each pre-ex row's
# ln(close / NAV) is compared with the fund's own on its first post-ex rows (`ref`, the same on
# either basis): a raw row sits near ref, an adjusted one near ref - ln f, and the row takes the
# nearer. A row nearer neither (within tau of the midpoint), and a split whose factor the NAV
# cannot decide (|ln f| <= 2 tau, `SPLIT_DECIDABLE`), refuse unless ruled `book_as_is` (accept the
# rows as served). A split Yahoo declares in the fetched window with no ruling refuses
# (`unruled_declared_splits`). Every converted row is logged.
#
# THE STEP GUARD (`basis_steps`). After the ruled conversion, a fetched close or NAV whose ratio to
# the STORED value of the same date is split-like (|ln r| > 2 tau = SPLIT_DECIDABLE) refuses the
# panel write, naming the series, the fund and the dates: the step the spike guard cannot see. A
# vendor's revision of a bar is a few percent at most; a ratio past x1.32 is a change of basis.

FETCH_SPLIT_TREATMENTS = ("to_nav_basis", "book_as_is")
BASIS_REF_ROWS = 10           # the first post-ex rows the reference ratio is the median of


class PriceBasisError(ValueError):
    """A fetched price that cannot be put on its NAV's share basis under a recorded ruling."""


def load_fetch_split_rulings(path: Path | str) -> pd.DataFrame:
    """The live fetch's split rulings: `load_split_rulings`' file and schema, every entry on
    the `close` series with treatment `to_nav_basis` or `book_as_is`. Anything else raises."""
    R, _doc = load_split_rulings(path)
    bad = R[(R["series"] != "close") | ~R["treatment"].isin(FETCH_SPLIT_TREATMENTS)]
    if len(bad):
        raise PriceBasisError(f"{Path(path).name}: the live fetch reads only `close` rulings treated "
                              f"{FETCH_SPLIT_TREATMENTS}; got {bad[['ticker', 'ex_date', 'series', 'treatment']].to_dict('records')}")
    return R


def unruled_declared_splits(declared: list, rulings: pd.DataFrame) -> list:
    """The (ticker, date, multiplier) splits Yahoo declares in a fetch (its `Stock Splits`
    column) that no ruling names on that ex-date with that multiplier (1e-6 relative)."""
    out = []
    for t, d, v in declared:
        m = rulings[(rulings["ticker"] == t) & (pd.to_datetime(rulings["ex_date"]) == pd.Timestamp(d))]
        if not len(m) or abs(float(m["factor"].iloc[0]) - float(v)) > 1e-6 * max(1.0, abs(float(v))):
            out.append((t, pd.Timestamp(d), float(v)))
    return out


def to_nav_basis(px: pd.DataFrame, nav: pd.DataFrame, rulings: pd.DataFrame, *,
                 context: str) -> tuple[pd.DataFrame, list]:
    """`px` (date, open, high, low, close, volume, ticker[, grp]) with each ruled split's
    adjusted pre-ex rows put back on the NAV's basis, and the log (THE LIVE FETCH'S PRICE
    BASIS, above). `nav` (date, nav, ticker) judges each row. A ruling applies to a fund
    only when its ex-date falls inside that fund's rows here (some row before it, some on
    or after it); otherwise it is not this frame's split. Raises `PriceBasisError`, naming
    the rows, on an undecidable row or factor not ruled `book_as_is`, or a ruled split with
    no post-ex row that has a NAV to judge against. Pure: no clock, no network."""
    out = px.copy()
    log = []
    if out.empty or rulings is None or rulings.empty:
        return out, log
    navs = nav.dropna(subset=["nav"]).drop_duplicates(["ticker", "date"], keep="last")
    navs = navs.set_index(["ticker", "date"])["nav"]
    for r in rulings.itertuples():
        t, ex, f = r.ticker, pd.Timestamp(r.ex_date), float(r.factor)
        m = out["ticker"] == t
        dates = pd.to_datetime(out.loc[m, "date"])
        if not len(dates) or not (dates.min() < ex <= dates.max()):
            continue
        pre = m & (pd.to_datetime(out["date"]) < ex)
        post = m & (pd.to_datetime(out["date"]) >= ex)
        if r.treatment == "book_as_is":
            log.append({"ticker": t, "ex_date": ex, "factor": f, "treatment": "book_as_is",
                        "converted": 0, "as_served": int(pre.sum())})
            continue
        lf = math.log(f)
        if abs(lf) <= SPLIT_DECIDABLE:
            raise PriceBasisError(f"{context}: {t}'s split of {_iso(ex)} (factor {_factor_label(f)}) is too small "
                                  "for the NAV to tell an adjusted close from a raw one; rule it `book_as_is` "
                                  "to keep the rows as served")
        def ratio(i):
            n = navs.get((t, pd.Timestamp(out.at[i, "date"])))
            c = out.at[i, "close"]
            if n is None or not (np.isfinite(c) and c > 0 and np.isfinite(n) and n > 0):
                return None
            return math.log(c / n)
        post_r = [x for x in (ratio(i) for i in out.index[post][:BASIS_REF_ROWS]) if x is not None]
        if not post_r:
            raise PriceBasisError(f"{context}: {t}'s split of {_iso(ex)} has no post-ex row with a close and a "
                                  "NAV to judge the pre-ex rows against")
        ref = float(np.median(post_r))
        adjusted, raw, undecided, unknown = [], [], [], []
        for i in out.index[pre]:
            y = ratio(i)
            if y is None:
                unknown.append(i)
                continue
            d_raw, d_adj = abs(y - ref), abs(y - ref + lf)
            if abs(d_raw - d_adj) <= SPLIT_TOL:
                undecided.append(i)
            elif d_adj < d_raw:
                adjusted.append(i)
            else:
                raw.append(i)
        if undecided:
            raise PriceBasisError(f"{context}: {t} ({_iso(ex)} split, factor {_factor_label(f)}): "
                                  f"{len(undecided)} pre-ex row(s) sit between the raw and the adjusted "
                                  f"basis against their NAV: " + ", ".join(_iso(out.at[i, 'date']) for i in undecided[:10]))
        if unknown:
            if adjusted and raw:
                raise PriceBasisError(f"{context}: {t}: {len(unknown)} pre-ex row(s) have no NAV to judge them, "
                                      f"and the judged rows are on both bases: "
                                      + ", ".join(_iso(out.at[i, 'date']) for i in unknown[:10]))
            if not adjusted and not raw:
                raise PriceBasisError(f"{context}: {t}: no pre-ex row of the {_iso(ex)} split has a NAV to judge "
                                      f"its basis: " + ", ".join(_iso(out.at[i, 'date']) for i in unknown[:10]))
            (adjusted if adjusted else raw).extend(unknown)
        if adjusted:
            idx = sorted(adjusted)
            for c in ("open", "high", "low", "close"):
                if c in out.columns:
                    out.loc[idx, c] = out.loc[idx, c].astype(float) * f
            if "volume" in out.columns:
                out.loc[idx, "volume"] = (out.loc[idx, "volume"].astype(float) / f).round().astype("int64")
        d = pd.to_datetime(out.loc[sorted(adjusted), "date"]) if adjusted else None
        log.append({"ticker": t, "ex_date": ex, "factor": f, "treatment": "to_nav_basis",
                    "converted": len(adjusted), "raw": len(raw), "judged_by_neighbours": len(unknown),
                    "first": None if d is None else d.min(), "last": None if d is None else d.max(),
                    "ref_premium": math.expm1(ref)})
    if "volume" in px.columns:
        out["volume"] = out["volume"].astype(px["volume"].dtype)
    return out, log


def basis_steps(new_px: pd.DataFrame, old_px: pd.DataFrame, new_nav: pd.DataFrame,
                old_nav: pd.DataFrame, *, tol: float = SPLIT_DECIDABLE) -> list:
    """Every run of dates on which a fetched close or NAV differs from the STORED value of the
    same (ticker, date) by a split-like ratio, |ln(new / old)| > tol: [{"series", "ticker",
    "first", "last", "rows", "ratio_lo", "ratio_hi"}]. Rows missing or non-positive on either
    side are not compared (the merge's own guards judge those)."""
    hits = []
    for series, col, new, old in (("close", "close", new_px, old_px), ("nav", "nav", new_nav, old_nav)):
        if new is None or old is None or new.empty or old.empty:
            continue
        a = new[["ticker", "date", col]].drop_duplicates(["ticker", "date"], keep="last")
        b = old[["ticker", "date", col]].drop_duplicates(["ticker", "date"], keep="last")
        j = a.merge(b, on=["ticker", "date"], suffixes=("_new", "_old"))
        x, y = j[f"{col}_new"].astype(float), j[f"{col}_old"].astype(float)
        ok = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
        j = j[ok].copy()
        j["lr"] = np.log(j[f"{col}_new"].astype(float) / j[f"{col}_old"].astype(float))
        j = j.sort_values(["ticker", "date"])
        for t, g in j.groupby("ticker", sort=True):
            flag = (g["lr"].abs() > tol).to_numpy()
            run = []
            for k, (d, lr) in enumerate(zip(g["date"], g["lr"])):
                if flag[k]:
                    run.append((pd.Timestamp(d), float(lr)))
                if run and (not flag[k] or k == len(g) - 1):
                    rs = [math.exp(v) for _, v in run]
                    hits.append({"series": series, "ticker": t, "first": run[0][0], "last": run[-1][0],
                                 "rows": len(run), "ratio_lo": min(rs), "ratio_hi": max(rs)})
                    run = []
    return hits


def describe_basis_steps(hits: list) -> str:
    return "; ".join(f"({h['series']} {h['ticker']} {_iso(h['first'])}..{_iso(h['last'])}, {h['rows']} row(s), "
                     f"fetched/stored x{h['ratio_lo']:.4f}..x{h['ratio_hi']:.4f})" for h in hits)


# --------------------------------------------------------------------------- Stage-0 flags block P&L

STAGE0_RULING_COLUMNS = ("ruling", "ruled_by", "ruled_on")


def _norm(df: pd.DataFrame, keys) -> pd.DataFrame:
    out = df.copy()
    for k in keys:
        if k == "date" or k.startswith("date"):
            out[k] = pd.to_datetime(out[k]).dt.strftime("%Y-%m-%d")
        else:
            out[k] = out[k].astype(str)
    return out


def require_stage0_rulings(flags: pd.DataFrame, rulings_path: Path | str, *, keys=("check", "ticker", "date"),
                           context: str = "") -> pd.DataFrame:
    """Refuse to let a trial form P&L while any Stage-0 flag lacks a recorded ruling.

    WHY. C4's Stage 0 flagged the four IGR bars (Q5, eight rows) on 2026-10-14, among
    1,304 Q5 flags and 5,142 rows in all; the pre-registration said a vendor defect is
    fixed before any P&L (§4.5), but nothing made the trial wait for the flags to be
    read, and the holdout booked them on 2026-10-18. A flag is information only if
    someone must answer it.

    `flags`: the trial's Stage-0 flag table (one row per flag; `keys` identify it).
    `rulings_path`: the trial's rulings CSV -- the `keys` plus `ruling` (the ruled
    treatment, in words), `ruled_by` and `ruled_on` (ISO date), one row per flag. Its
    path is declared in the pre-registration (`.claude/skills/prereg/SKILL.md`).
    `stage0_rulings_template` writes the empty form.

    Raises `Stage0BlockError`, naming every flag concerned, when: the file is missing
    (and there is any flag); a flag has no row, or a row with an empty field; a key
    is ruled twice; or a ruling matches no flag (the flags changed under it -- a
    fixed fetcher is the usual cause, and the stale row must go). Zero flags need no
    file. Returns the flags with their rulings joined, for the trial to print."""
    keys = list(keys)
    if not len(flags):
        return flags.assign(**{c: pd.Series(dtype=object) for c in STAGE0_RULING_COLUMNS})
    miss_k = [k for k in keys if k not in flags.columns]
    if miss_k:
        raise Stage0BlockError(f"{context}: the flag table has no column(s) {miss_k}")
    F = _norm(flags, keys)
    if F.duplicated(keys).any():
        raise Stage0BlockError(f"{context}: two flags share one key {keys}; the key does not identify a flag")
    p = Path(rulings_path)
    if not p.exists():
        raise Stage0BlockError(
            f"{context}: {len(F)} Stage-0 flag(s) and no rulings file at {p}. No P&L is formed until every flag "
            f"has a recorded ruling: {_name_flags(F, keys)}")
    R = pd.read_csv(p, dtype=str, keep_default_na=False)
    need = keys + list(STAGE0_RULING_COLUMNS)
    miss_c = [c for c in need if c not in R.columns]
    if miss_c:
        raise Stage0BlockError(f"{context}: {p.name} lacks column(s) {miss_c}")
    R = _norm(R[need], keys)
    if R.duplicated(keys).any():
        raise Stage0BlockError(f"{context}: {p.name} rules one flag twice: {_name_flags(R[R.duplicated(keys, keep=False)], keys)}")
    J = F.merge(R, on=keys, how="left", indicator=True)
    empty = J[list(STAGE0_RULING_COLUMNS)].fillna("").apply(lambda c: c.str.strip() == "").any(axis=1)
    lacking = J[(J["_merge"] == "left_only") | empty]
    if len(lacking):
        raise Stage0BlockError(
            f"{context}: {len(lacking)} of {len(F)} Stage-0 flag(s) lack a recorded ruling in {p.name}; no P&L "
            f"is formed until each has one: {_name_flags(lacking, keys)}")
    stale = R.merge(F[keys], on=keys, how="left", indicator=True)
    stale = stale[stale["_merge"] == "left_only"]
    if len(stale):
        raise Stage0BlockError(f"{context}: {p.name} rules on {len(stale)} flag(s) Stage 0 no longer raises: "
                               f"{_name_flags(stale, keys)}")
    bad_on = J[pd.to_datetime(J["ruled_on"], errors="coerce").isna()]
    if len(bad_on):
        raise Stage0BlockError(f"{context}: {p.name} has a `ruled_on` that is not a date for "
                               f"{_name_flags(bad_on, keys)}")
    return J.drop(columns="_merge")


def _name_flags(df: pd.DataFrame, keys) -> str:
    return "; ".join("(" + ", ".join(str(v) for v in row) + ")" for row in df[list(keys)].itertuples(index=False))


def stage0_rulings_template(flags: pd.DataFrame, path: Path | str, *, keys=("check", "ticker", "date")) -> Path:
    """Write the empty rulings form for `flags` (the keys, then blank ruling columns). Refuses to
    overwrite: a rulings file is a record, and a template written over it would erase rulings."""
    p = Path(path)
    if p.exists():
        raise Stage0BlockError(f"{p} exists; a rulings file is never overwritten by a template")
    T = _norm(flags[list(keys)], keys).drop_duplicates()
    for c in STAGE0_RULING_COLUMNS:
        T[c] = ""
    T.to_csv(p, index=False)
    return p


# --------------------------------------------------------------------------- the scan of the panels

SCAN_STAMP = "2026-10-19"
SCAN_DIR = REPO / "results" / "cef" / "data_guards"


def _wide(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """date x ticker of `col`. Exact duplicate rows collapse (the CEFConnect file repeats a day
    in its "All" and "1Y" windows, identically on 2026-10-19); two DIFFERENT values for one
    (date, ticker) raise -- `pivot_table` would average them into a number no source printed."""
    d = df.assign(date=pd.to_datetime(df["date"]))[["date", "ticker", col]].drop_duplicates()
    clash = d[d.duplicated(["date", "ticker"], keep=False)]
    if len(clash):
        raise ValueError(f"{col}: {clash[['date', 'ticker']].drop_duplicates().shape[0]} (date, ticker) pairs carry "
                         f"two different values, e.g. {clash.head(4).to_dict('records')}")
    return d.pivot(index="date", columns="ticker", values=col).sort_index()


def scan() -> int:
    """Run `split_like_spikes` over every price panel in data/cef/ and data/cef_families/.

    Writes the yfinance- and CEFConnect-sourced hits (ticker, dates, ratios: no price
    level) to results/cef/data_guards/; the CRSP-built panel is licensed, so only its
    counts are committed. Report only: nothing is altered, and no panel is written."""
    from scripts.cef.band_frontier import load_families_actions
    D, F = REPO / "data" / "cef", REPO / "data" / "cef_families"
    fam_div, fam_sp = load_families_actions(F / "cef_actions.parquet")
    live_sp = pd.read_parquet(D / "cef_splits.parquet")
    fam_nav = _wide(pd.read_parquet(F / "cef_nav.parquet"), "nav")
    cc = pd.read_parquet(F / "cef_nav_cefconnect.parquet")
    panels = [
        ("data/cef/cef_prices.parquet (live book, yfinance)", _wide(pd.read_parquet(D / "cef_prices.parquet"), "close"),
         _wide(pd.read_parquet(D / "cef_nav.parquet"), "nav"), live_sp, True),
        ("data/cef_families/cef_prices.parquet (yfinance)", _wide(pd.read_parquet(F / "cef_prices.parquet"), "close"),
         fam_nav, fam_sp, True),
        ("data/cef_families/cef_nav_cefconnect.parquet close_cc (CEFConnect)", _wide(cc, "close_cc"),
         _wide(cc, "nav"), fam_sp, True),
        ("data/cef_families/cef_prices_crsp.parquet (CRSP-built; licensed: counts only)",
         _wide(pd.read_parquet(F / "cef_prices_crsp.parquet"), "close"), fam_nav, fam_sp, False),
    ]
    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    lines, committed = [], []
    pr = lambda s="": lines.append(s)                                       # noqa: E731
    pr(f"SPLIT-LIKE SPIKE-AND-REVERT SCAN ({SCAN_STAMP}; report only; zero trials). Declared rule: tau = ln(1.15) = "
       f"{SPLIT_TOL:.4f}, window {REVERT_WINDOW} sessions; NAV makes the move if within tau of the price's step.")
    for name, close, nav, sp, publish in panels:
        H, U = split_like_spikes(close, nav, sp)
        pr()
        gaps = pd.concat([close[c].dropna().index.to_series().diff().dt.days for c in close.columns]).dropna()
        pr(f"[{name}] {close.shape[1]} tickers, {close.index.min().date()}..{close.index.max().date()}, "
           f"{int(close.notna().sum().sum())} bars; median gap between a ticker's bars {gaps.median():g} calendar "
           f"days" + (" -- NOT daily: tau is derived for one-day moves, so read these hits as leads" if gaps.median() > 3
                      else ""))
        pr(f"  HITS (raised by the guard): {len(H)} in {H['ticker'].nunique() if len(H) else 0} tickers; "
           f"unreverted split-like jumps the NAV did not make (reported only): {len(U)} in "
           f"{U['ticker'].nunique() if len(U) else 0} tickers")
        sens = []
        for lab, tol, w in (("tau/2", SPLIT_TOL / 2, REVERT_WINDOW), ("2 tau", 2 * SPLIT_TOL, REVERT_WINDOW),
                            ("W=1", SPLIT_TOL, 1), ("W=21", SPLIT_TOL, 21)):
            sens.append(f"{lab} {len(split_like_spikes(close, nav, sp, tol=tol, window=w)[0])}")
        pr(f"  beside it, never choosing: hits at {', '.join(sens)}")
        if publish:
            if len(H):
                pr("  every hit: ticker, first bar, last bar, revert, bars, ratio, factor, NAV ratio")
                for r in H.itertuples():
                    pr(f"    {r.ticker:<6} {_iso(r.date)} {_iso(r.run_end)} {_iso(r.revert_date)} {r.bars} "
                       f"{r.ratio:7.3f} {r.factor:7.4f} " + ("   none" if pd.isna(r.nav_ratio) else f"{r.nav_ratio:7.3f}"))
            if len(U):
                pr("  unreverted (reported only): ticker, date, ratio, factor, NAV ratio")
                for r in U.itertuples():
                    pr(f"    {r.ticker:<6} {_iso(r.date)} {r.ratio:7.3f} {r.factor:7.4f} " +
                       ("   none" if pd.isna(r.nav_ratio) else f"{r.nav_ratio:7.3f}"))
            if len(H):
                committed.append(H.assign(panel=name.split(" ")[0]))
        else:
            by = H.groupby(H["date"].dt.year).size().to_dict() if len(H) else {}
            pr(f"  counts by year (licensed panel; no ticker-dates committed): {by}")
    out = SCAN_DIR / f"scan_output_{SCAN_STAMP}.txt"
    out.write_text("\n".join(lines) + "\n")
    pd.concat(committed or [pd.DataFrame(columns=HIT_COLUMNS + ["panel"])]).to_csv(SCAN_DIR / f"scan_hits_{SCAN_STAMP}.csv", index=False, float_format="%.6f")
    print("\n".join(lines))
    print(f"\nwrote {out.relative_to(REPO)} and scan_hits_{SCAN_STAMP}.csv")
    return 0


SPLIT_SCAN_STAMP = "2026-10-20"


def _call_site_frames(wide: pd.DataFrame, sp: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(R, k) exactly as the call sites form them on a daily panel: the wide panel's
    `pct_change(fill_method=None)` (C4's `yf_total_returns`) and `split_factor` on its index."""
    from scripts.cef.band_frontier import split_factor
    R = wide.pct_change(fill_method=None)
    return R, split_factor(R.index, R.columns, splits=sp).reindex_like(R)


def _own_bar_frames(wide: pd.DataFrame, sp: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(R, k) on each ticker's OWN consecutive bars, the factor on its first bar on or after the
    ex-date. For a sparse panel (CEFConnect is weekly), where the wide panel's step is mostly NaN."""
    R = pd.DataFrame(np.nan, index=wide.index, columns=wide.columns)
    k = pd.DataFrame(1.0, index=wide.index, columns=wide.columns)
    for t in wide.columns:
        s = wide[t].dropna()
        R.loc[s.index, t] = s.pct_change().to_numpy()
        for e, f in sp.loc[sp["ticker"] == t].groupby("ex_date")["stock_split"].prod().items():
            on = s.index[s.index >= pd.Timestamp(e)]
            if len(on) and len(s.index[s.index < pd.Timestamp(e)]):
                k.loc[on[0], t] *= float(f)
    return R, k


def scan_splits() -> int:
    """Every recorded split in data/cef/ and data/cef_families/, labelled by basis on each panel.

    Writes the yfinance- and CEFConnect-sourced rows (ticker, ex-date, factor, ratios: no price
    level) to results/cef/data_guards/; the CRSP-built panel is licensed, so only its counts are
    committed. Report only: nothing is altered, and no panel is written."""
    from scripts.cef.band_frontier import load_families_actions
    D, F = REPO / "data" / "cef", REPO / "data" / "cef_families"
    _fam_div, fam_sp = load_families_actions(F / "cef_actions.parquet")
    live_sp = pd.read_parquet(D / "cef_splits.parquet")
    cc = pd.read_parquet(F / "cef_nav_cefconnect.parquet")
    panels = [
        ("data/cef/cef_prices.parquet close (live book, yfinance)", _wide(pd.read_parquet(D / "cef_prices.parquet"),
         "close"), live_sp, _call_site_frames, "public", "call site: every total_returns(R) on the live panel"),
        ("data/cef_families/cef_prices.parquet close (yfinance)", _wide(pd.read_parquet(F / "cef_prices.parquet"),
         "close"), fam_sp, _call_site_frames, "public", "call site: C4's yf_total_returns"),
        ("data/cef_families/cef_nav.parquet nav (yfinance)", _wide(pd.read_parquet(F / "cef_nav.parquet"), "nav"),
         fam_sp, _call_site_frames, "public", "call site: C4's NAV catch-up (fit diagnostic)"),
        ("data/cef_families/cef_nav_cefconnect.parquet close_cc (CEFConnect)", _wide(cc, "close_cc"), fam_sp,
         _own_bar_frames, "public", "not a call site; weekly, so own bars, read as leads"),
        ("data/cef_families/cef_prices_crsp.parquet close (CRSP-built; licensed: counts only)",
         _wide(pd.read_parquet(F / "cef_prices_crsp.parquet"), "close"), fam_sp, _call_site_frames, "counts",
         "not a call site; the raw second source"),
    ]
    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    lines, committed = [], []
    pr = lambda s="": lines.append(s)                                       # noqa: E731
    pr(f"RECORDED-SPLIT BASIS SCAN ({SPLIT_SCAN_STAMP}; report only; zero trials). Declared rule: tau = ln(1.15) = "
       f"{SPLIT_TOL:.4f} (the spike guard's); decidable iff |ln k| > 2 tau = {SPLIT_DECIDABLE:.4f} "
       f"(k outside [{math.exp(-SPLIT_DECIDABLE):.4f}, {math.exp(SPLIT_DECIDABLE):.4f}]); ADJUSTED (raised) iff "
       "decidable and |ln(1+r)| <= tau on the cell k multiplies.")
    for name, wide, sp, frames, publish, role in panels:
        sp = sp[sp["ticker"].isin(wide.columns)]
        R, k = frames(wide, sp)
        C = split_basis_check(R, k)
        n_rec = int(sp.groupby(["ticker", "ex_date"]).ngroups)
        pr()
        pr(f"[{name}] {role}; {wide.shape[1]} tickers, {wide.index.min().date()}..{wide.index.max().date()}; "
           f"{n_rec} recorded split ex-date(s) on its tickers; {len(C)} applied to a finite return")
        by = C["basis"].value_counts().to_dict() if len(C) else {}
        pr("  basis counts: " + ", ".join(f"{b} {by.get(b, 0)}" for b in ("adjusted", "raw", "neither", "undecidable")))
        if publish != "public":
            yrs = C[C["basis"] == "adjusted"]["ex_date"].dt.year.value_counts().sort_index().to_dict() if len(C) else {}
            pr(f"  adjusted, by year (licensed panel; no ticker-dates committed): {yrs}")
            continue
        for b, title in (("adjusted", "ADJUSTED -- the guard raises on these wherever k is applied to this series"),
                         ("neither", "neither basis (reported only)"), ("raw", "raw (k is right)"),
                         ("undecidable", "undecidable, |ln k| <= 2 tau (no power; reported only)")):
            sub = C[C["basis"] == b].sort_values(["ex_date", "ticker"])
            if len(sub):
                pr(f"  {title}: ticker, ex-date, factor, raw ratio, booked ratio")
                for r in sub.itertuples():
                    pr(f"    {r.ticker:<6} {_iso(r.ex_date)} {_factor_label(r.factor):>9} {r.raw_ratio:7.3f} "
                       f"{r.booked_ratio:7.3f}")
        applied = set(zip(C["ticker"], C["ex_date"]))
        lost = []
        for (t, e), _g in sp.groupby(["ticker", "ex_date"]):
            s = wide[t].dropna()
            if (frames is _call_site_frames and s.index.min() < pd.Timestamp(e) <= s.index.max()
                    and (t, pd.Timestamp(e)) not in applied):
                lost.append(f"{t} {_iso(e)}")
        if lost:
            pr(f"  inside the ticker's history but on no finite return here, so k multiplies nothing (reported "
               f"only): {', '.join(lost)}")
        committed.append(C.assign(panel=name.split(" ")[0] + " " + name.split(" ")[1]))
    out = SCAN_DIR / f"split_basis_scan_{SPLIT_SCAN_STAMP}.txt"
    out.write_text("\n".join(lines) + "\n")
    csv = SCAN_DIR / f"split_basis_scan_{SPLIT_SCAN_STAMP}.csv"
    pd.concat(committed).to_csv(csv, index=False, float_format="%.6f")
    print("\n".join(lines))
    print(f"\nwrote {out.relative_to(REPO)} and {csv.name}")
    return 0


if __name__ == "__main__":
    cmds = {"scan": scan, "scan-splits": scan_splits}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        raise SystemExit("usage: python3 scripts/cef/data_guards.py scan | scan-splits")
    raise SystemExit(cmds[sys.argv[1]]())
