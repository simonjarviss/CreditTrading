"""The XASSET slate's common protocol: inputs, pins, returns, and the declared statistics.

    from scripts.xasset import protocol as P

WHAT THIS IS
------------
`results/xasset/PREREG_XASSET_SLATE_2026-10-12.md` (revision 3, APPROVED by the
team lead 2026-10-14 with X5 withdrawn, N = 4) declares one protocol (§1) for
X1-X4. This module is that protocol written once, so the four trial scripts
(`scripts/xasset/x<k>_*.py`) cannot drift apart on an input, a window, an
estimator or a bar. It contains NO backtester: every P&L comes from
`scripts/cef/band_frontier.evaluate` (H1, shift(2)); every helper that touches
positions (`month_end_sessions`, `hold_from_refresh`, `block_shuffle`) was added
to `band_frontier.py` visibly, with tests, as P4 requires.

WHAT IS PINNED HERE, AND WHY IT IS A LITERAL
--------------------------------------------
Revision 3's fix 4 pins `vol_target_annual` = 0.06, `max_gross_stress` = 1.80
and the frozen spec's SHA-256 AT APPROVAL. They are written here as literals on
purpose: the run must READ the live values through `scripts/cef/spec.py` and
HALT if they differ from what was approved (`check_spec_pin`). This is the one
place in the repo where a spec value is a literal, and it exists to detect, not
to set. N = 4 is the approved slate size (the approval block of the prereg).

INPUTS ARE PINNED BY HASH (§1.1)
--------------------------------
Stage 0a ends with a commit of `results/xasset/stage0a/STAGE0A_MANIFEST_2026-10-14.json`,
the SHA-256 of every file a trial reads. `verify_inputs` re-hashes each before a
stage reads it and raises on any mismatch. After Stage 0a nothing is repaired,
dropped or substituted.

ALIGNMENT (H7), STATED ONCE
---------------------------
* r_f for session t is the last DGS3MO value published STRICTLY before t, /100
  /252 (P3); `risk_free` asserts it.
* A target decided at the close of t sits in H.loc[t]; `evaluate` earns it on
  t+2 (H1). Statistics use the P&L from the first decision + 2 sessions.
* Fit stages see nothing on or after 2023-01-01: the return panel is truncated
  BEFORE any signal is built (`fit_panel`), and `assert_fit` checks every
  series that reaches a statistic.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.cef.band_frontier import HOLDOUT_START, _stats, evaluate  # noqa: E402

CACHE = REPO / "results" / "xasset" / "_cache_xasset"
RESULTS = REPO / "results" / "xasset"
# The dated notes sit in RESULTS; each stage's data sits in a folder under it
# (the results/cef/ convention, team lead 2026-10-22). The trial verdicts moved
# with their files: `runner.refuse_rerun` and `runner.holdout_guard` look for a
# spent trial in TRIALS, so a guard pointed anywhere else would find nothing and
# let a spent test run again (`tests/test_spent_trials.py` holds them to the
# committed files).
STAGE0A_DIR = RESULTS / "stage0a"
TRIALS = RESULTS / "trials"
MANIFEST = STAGE0A_DIR / "STAGE0A_MANIFEST_2026-10-14.json"

# ---- the approved pins (revision 3 §1.3; approval block) ----------------------
PINNED_VOL_TARGET = 0.06
PINNED_MAX_GROSS = 1.80
PINNED_SPEC_SHA256 = "c05035e55eaa89172f65d38a3485cb1c68123217177343b38576edf56583c02e"
N_SLATE = 4                       # approval 2026-10-14: X5 withdrawn, N = 4
N_LEGACY = 162                    # printed beside the bar, never deciding (§1.6)
DSR_PASS = 0.95                   # ruling 2

# ---- windows (§1.5) ----------------------------------------------------------
FIT_END = pd.Timestamp("2022-12-30")
HOLDOUT_FIRST = pd.Timestamp("2023-01-03")
HOLDOUT_END = pd.Timestamp("2026-09-30")
ERAS = [("2005-09", "2005-01-01", "2009-12-31"), ("2010-14", "2010-01-01", "2014-12-31"),
        ("2015-19", "2015-01-01", "2019-12-31"), ("2020-22", "2020-01-01", "2022-12-31"),
        ("2023-26", "2023-01-01", "2026-12-31")]

# ---- inference (§1.6, §1.8) --------------------------------------------------
SEED = 20261012
NW_LAGS = 21
BOOT_BLOCK = 21
BOOT_BLOCK_ALT = 63
BOOT_REPS = 10_000
PLACEBO_DRAWS = 1_000
PLACEBO_BLOCK = 21
COSTS = (5, 15, 30)
MONTHLY_HAC = "floor(4 (T_m/100)^(2/9))"

# ---- question 2, RULED by the team lead 2026-10-14 (PREREG amendment block):
# the block-shuffled placebo shuffles ONLY inside the span where every fund in the
# test trades (from the latest first return among the test's funds), so no
# placebo position lands on a pre-inception date. Rows of H before that span keep
# their dates; every statistic stays on the declared P&L window (§1.6). For X2
# and X3 the span starts before the first decision, so their whole H is shuffled.
PLACEBO_PRE_INCEPTION_RULE = "span"
# ---- question 1, RULED by the team lead 2026-10-14 (PREREG amendment block):
# DG1 clears as measured. In the yfinance leg "unchanged" reads as <= 0.01bp (the
# measured maximum was 0.0074bp, inside the holdout only); the fit's CRSP leg is
# identical; the Stage 0a panel hash (STAGE0A_MANIFEST_2026-10-14.json) fixes
# exactly which data every test uses.
DG1_RULING = "cleared as measured (team lead, 2026-10-14): yfinance-leg ret_total within 0.01bp"

# ---- inputs ------------------------------------------------------------------
PANEL = CACHE / "etf_daily_xasset.parquet"            # DG1, staged outside data/
DGS3MO = CACHE / "dgs3mo.parquet"                       # DG3
AQR_TSMOM = CACHE / "aqr_tsmom_monthly.parquet"         # DG2
AQR_VME = CACHE / "aqr_vme_monthly.parquet"             # DG2
FF_DAILY = REPO / "results" / "cef" / "w4" / "_cache_w4" / "ff5_umd_daily.parquet"
FF_MONTHLY = REPO / "results" / "cef" / "w4" / "_cache_w4" / "ff5_umd_monthly.parquet"
INHOUSE = {"etf_panel": CACHE / "inhouse_etf_panel.parquet",              # copies taken at 0a
           "etf_ohlc_extended": CACHE / "inhouse_etf_ohlc_extended.parquet"}
INHOUSE_SRC = {"etf_panel": REPO / "data" / "rv" / "etf_panel.parquet",
               "etf_ohlc_extended": REPO / "data" / "rv" / "etf_ohlc_extended.parquet"}
SPEC_FILE = REPO / "ops" / "specs" / "cef_discount.frozen.json"
# P12 reads the CEF book through band_frontier.build_targets / total_returns, which
# read these in place (they are not copied: build_panel's paths are fixed).
CEF_INPUTS = [REPO / "data" / "cef" / f for f in
              ("cef_prices.parquet", "cef_nav.parquet", "cef_distributions.parquet",
               "cef_splits.parquet")]
QFLAGS = CACHE / "stage0a_flags.csv"                    # Q1-Q7 flag list with values (licensed rows)

# The instruments, as declared (§0; slate_feasibility.py holds the same lists).
X1_NAMES = ["HYG", "LQD", "IEF", "TLT", "EMB", "PFF", "MUB", "BKLN", "CWB"]
X4_NAMES = X1_NAMES + ["SPY", "EFA", "EEM", "GLD", "DBC"]
NOT_SHORTABLE = {"MUB"}           # P6: long-or-flat for the whole backtest (2026-10-12 snapshot)
SLATE_19 = X4_NAMES + ["SHY", "BIL", "IEI", "TLH", "AGG"]
FACTOR_NAMES = {"MKT": ("SPY", None), "TERM": ("IEF", None), "HY": ("HYG", "IEF"),
                "IG": ("LQD", "IEF"), "COMMOD": ("DBC", None), "GOLD": ("GLD", None),
                "INTL": ("EFA", "SPY"), "EM": ("EEM", "SPY")}


class ProtocolError(RuntimeError):
    """A declared condition of the pre-registration does not hold. Never caught."""


# =============================================================================
# hashes, pins and the manifest
# =============================================================================
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def rel(path: Path) -> str:
    """Repo-relative path WITHOUT resolving symlinks: `data/` is a symlink in a
    worktree, and resolving it would write a machine path into a tracked file."""
    p = Path(path)
    if not p.is_absolute():
        return str(p)
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        raise ProtocolError(f"{p} is outside the repository; refusing to record a machine path")


def check_spec_pin() -> dict:
    """§1.3: read both values through spec.py and hash the file; HALT on mismatch."""
    from scripts.cef import spec
    got = {"vol_target_annual": float(spec.VOL_TARGET),
           "max_gross_stress": None if spec.MAX_GROSS_STRESS is None else float(spec.MAX_GROSS_STRESS),
           "spec_sha256": sha256(spec.SPEC_PATH), "spec_path": rel(spec.SPEC_PATH)}
    want = {"vol_target_annual": PINNED_VOL_TARGET, "max_gross_stress": PINNED_MAX_GROSS,
            "spec_sha256": PINNED_SPEC_SHA256}
    bad = {k: (got[k], v) for k, v in want.items() if got[k] != v}
    if bad:
        raise ProtocolError(f"spec pin mismatch (got, pinned): {bad}. Stage 0a halts; "
                            "this goes to the team lead (PREREG §1.3).")
    return got


def verify_inputs(keys=None) -> dict:
    """Re-hash every manifest file (or the named keys) and raise on any mismatch."""
    if not MANIFEST.exists():
        raise ProtocolError(f"{rel(MANIFEST)} is missing: Stage 0a has not ended")
    man = json.loads(MANIFEST.read_text())
    files = man["files"]
    keys = list(files) if keys is None else list(keys)
    for k in keys:
        if k not in files:
            raise ProtocolError(f"manifest has no input {k!r}")
        p = REPO / files[k]["path"]
        if not p.exists():
            raise ProtocolError(f"input {k} ({files[k]['path']}) is missing")
        h = sha256(p)
        if h != files[k]["sha256"]:
            raise ProtocolError(f"input {k} ({files[k]['path']}) hash {h[:16]}.. != manifest "
                                f"{files[k]['sha256'][:16]}..: halt (PREREG §1.1)")
    return man


def git_tracked(path: Path) -> bool:
    """True only if `path` is in the COMMITTED tree at HEAD (§1.5 says "committed";
    a staged-but-uncommitted file must not open a holdout)."""
    r = subprocess.run(["git", "cat-file", "-e", f"HEAD:{rel(path)}"], cwd=REPO,
                       capture_output=True, text=True)
    return r.returncode == 0


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                          text=True, check=True).stdout.strip()


# =============================================================================
# returns, calendar, risk-free (P1, P3)
# =============================================================================
def load_panel(path: Path = PANEL) -> pd.DataFrame:
    p = pd.read_parquet(path)
    p["date"] = pd.to_datetime(p["date"])
    return p


def wide(panel: pd.DataFrame, col: str = "ret_total") -> pd.DataFrame:
    w = panel.pivot(index="date", columns="ticker", values=col).sort_index()
    return w


def master_calendar(panel: pd.DataFrame) -> pd.DatetimeIndex:
    """SPY's sessions (SPY trades every NYSE session from 1993-02-01). Every other
    instrument's dates must lie inside it; a date outside raises."""
    cal = pd.DatetimeIndex(sorted(panel.loc[panel.ticker == "SPY", "date"].unique()))
    extra = sorted(set(panel["date"].unique()) - set(cal))
    if extra:
        raise ProtocolError(f"{len(extra)} panel dates are not SPY sessions, e.g. {extra[:5]}")
    return cal


def returns(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    cal = master_calendar(panel)
    R = wide(panel).reindex(cal)
    return R, cal


def first_returns(R: pd.DataFrame) -> dict:
    return {c: R[c].first_valid_index() for c in R.columns}


def risk_free(cal: pd.DatetimeIndex, path: Path = DGS3MO) -> pd.Series:
    """P3: r_f(t) = last DGS3MO value published strictly before t, /100/252."""
    f = pd.read_parquet(path)
    s = pd.Series(f["value"].values, index=pd.to_datetime(f["date"])).sort_index()
    if s.index.duplicated().any() or s.isna().any():
        raise ProtocolError("DGS3MO cache has duplicate dates or NaN values")
    pos = s.index.searchsorted(cal, side="left") - 1
    if (pos < 0).any():
        raise ProtocolError(f"DGS3MO starts {s.index[0].date()}, after calendar session {cal[0].date()}")
    used = s.index[pos]
    assert (used < cal).all(), "H7: an r_f value is not strictly before its session"
    return pd.Series(s.values[pos] / 100.0 / 252.0, index=cal, name="rf")


def excess(R: pd.DataFrame, rf: pd.Series) -> pd.DataFrame:
    return R.sub(rf.reindex(R.index), axis=0)


def fit_panel(X: pd.DataFrame | pd.Series):
    """Everything strictly before the 2023-01-01 holdout (H13), asserted."""
    out = X.loc[X.index < HOLDOUT_START]
    assert out.index.max() < HOLDOUT_START
    return out


def assert_fit(*objs):
    for o in objs:
        if len(o) and pd.Timestamp(o.index.max()) >= HOLDOUT_START:
            raise AssertionError(f"holdout leak: a series reaches {o.index.max().date()}")


def assert_covered(H: pd.DataFrame, Rx: pd.DataFrame, what: str):
    """H15: every name-date the book HOLDS (H.shift(2) != 0) has a return."""
    held = H.shift(2).fillna(0.0) != 0
    miss = held & Rx.reindex(index=H.index, columns=H.columns).isna()
    if miss.any().any():
        where = [(str(H.index[i].date()), H.columns[j]) for i, j in zip(*np.where(miss.values))][:5]
        raise ProtocolError(f"{what}: {int(miss.values.sum())} held name-dates have no return, "
                            f"e.g. {where}")


def run(H: pd.DataFrame, Rx: pd.DataFrame, what: str) -> dict:
    """`evaluate` on the excess-return matrix, after the coverage assertion. A name
    the book does not hold on a date contributes 0 whatever its return, so filling
    the NaN of an unheld name-date with 0 changes no P&L (asserted above)."""
    if H.isna().any().any():
        raise ProtocolError(f"{what}: H holds NaN; every position must be a number (0.0 if flat)")
    R = Rx.reindex(index=H.index, columns=H.columns)
    assert_covered(H, R, what)
    return evaluate(H, R.fillna(0.0))


# =============================================================================
# eligibility and windows (P7, §2.2)
# =============================================================================
def month_ends(cal: pd.DatetimeIndex) -> pd.DatetimeIndex:
    from scripts.cef.band_frontier import month_end_sessions
    return month_end_sessions(cal)


def eligible_at(E: pd.Timestamp, names, firsts: dict, cal: pd.DatetimeIndex,
                me: pd.DatetimeIndex, lag_m: int) -> list:
    """Eligible at month-end E once the first return is on or before the first
    session after the month-end `lag_m` months earlier (a full lookback window),
    exactly `slate_feasibility.fit_window`'s rule."""
    i = me.get_loc(E)
    if i < lag_m:
        return []
    start = cal[cal > me[i - lag_m]][0]
    return [n for n in names if firsts.get(n) is not None and firsts[n] <= start]


def pnl_window(first_dec: pd.Timestamp, cal: pd.DatetimeIndex, end=FIT_END) -> pd.DatetimeIndex:
    """Sessions from first decision + 2 (H1; validate.EXEC_LAG) to `end`."""
    from scripts.cef.validate import EXEC_LAG
    i = cal.get_loc(first_dec)
    return cal[(cal >= cal[i + EXEC_LAG]) & (cal <= end)]


# =============================================================================
# sizing (P5)
# =============================================================================
def size(H_raw: pd.DataFrame, Rx: pd.DataFrame, window: pd.DatetimeIndex, what: str) -> dict:
    """k = vol_target / sigma_fit, sigma_fit the annualised sd of the raw sleeve's
    daily gross excess P&L over the fit P&L window. The sized sleeve is never
    capped; the tradable one is capped row by row by the sleeve's own operator."""
    from src.deploy.sleeves.cef_discount import _cap_gross
    assert_fit(H_raw)
    raw = run(H_raw, Rx, what + " raw")["pnl"].reindex(window)
    if raw.isna().any():
        raise ProtocolError(f"{what}: raw P&L has gaps inside the window")
    sig = float(raw.std() * np.sqrt(252))
    if not sig > 0:
        raise ProtocolError(f"{what}: raw sleeve has zero volatility on its window")
    k = PINNED_VOL_TARGET / sig
    Hs = H_raw * k
    rows = [_cap_gross(Hs.loc[t], PINNED_MAX_GROSS)[0] for t in Hs.index]
    Ht = pd.DataFrame(rows, index=Hs.index, columns=Hs.columns)
    return dict(k=k, sigma_fit=sig, H_sized=Hs, H_trad=Ht)


def cap_bind_share(Hs: pd.DataFrame, window: pd.DatetimeIndex, cal: pd.DatetimeIndex) -> float:
    """Share of the window's sessions whose HELD book (decided two sessions earlier)
    had sized gross above max_gross_stress."""
    g = Hs.abs().sum(axis=1).shift(2).reindex(window)
    return float((g > PINNED_MAX_GROSS + 1e-12).mean())


# =============================================================================
# statistics (P8)
# =============================================================================
def sharpe(x: pd.Series) -> float:
    return float(x.mean() / x.std() * np.sqrt(252))


def nw_auto_lag(T: int) -> int:
    return int(math.floor(4 * (T / 100.0) ** (2.0 / 9.0)))


def nw_t(x: pd.Series, lags: int = NW_LAGS) -> float:
    from scripts.cef.w4_artifacts import nw_t as _nw
    return float(_nw(x, lags=lags))


def stationary_indices(n: int, mean_block: int, reps: int, seed: int, chunk: int = 500):
    """Politis-Romano stationary bootstrap index draws (geometric block lengths
    with mean `mean_block`, circular), yielded in chunks of rows of length n."""
    rng = np.random.default_rng(seed)
    p = 1.0 / mean_block
    done = 0
    while done < reps:
        m = min(chunk, reps - done)
        idx = np.empty((m, n), dtype=np.int64)
        idx[:, 0] = rng.integers(0, n, m)
        new = rng.random((m, n)) < p
        jump = rng.integers(0, n, (m, n))
        for t in range(1, n):
            idx[:, t] = np.where(new[:, t], jump[:, t], (idx[:, t - 1] + 1) % n)
        yield idx
        done += m


def _sr_rows(s: np.ndarray) -> np.ndarray:
    sd = s.std(axis=1, ddof=1)
    return np.where(sd > 0, s.mean(axis=1) / np.where(sd > 0, sd, 1.0) * np.sqrt(252), np.nan)


def stationary_bootstrap(x: np.ndarray, mean_block: int, reps: int, seed: int,
                         chunk: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """Means and annualised Sharpes of stationary-bootstrap resamples of x."""
    x = np.asarray(x, dtype=float)
    means, srs = [], []
    for idx in stationary_indices(len(x), mean_block, reps, seed, chunk):
        s = x[idx]
        means.append(s.mean(axis=1))
        srs.append(_sr_rows(s))
    return np.concatenate(means), np.concatenate(srs)


def paired_sharpe_diff(x: np.ndarray, y: np.ndarray, mean_block: int = BOOT_BLOCK,
                       reps: int = BOOT_REPS, seed: int = SEED) -> np.ndarray:
    """SR(x) - SR(y) on the SAME stationary-bootstrap draws (paired by date)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) != len(y):
        raise ProtocolError("paired series differ in length")
    out = []
    for idx in stationary_indices(len(x), mean_block, reps, seed):
        out.append(_sr_rows(x[idx]) - _sr_rows(y[idx]))
    return np.concatenate(out)


def dsr(x: pd.Series, n_trials: int = N_SLATE) -> dict:
    """`validate._dsr` with its inputs pinned as validate.py:342 computes them."""
    from scripts.cef.validate import _dsr
    obs = sharpe(x)
    T = len(x)
    sk = pd.Series(x.values).skew()
    ku = pd.Series(x.values).kurt() + 3.0
    d, sr0, emax = _dsr(obs, T, sk, ku, n_trials)
    return dict(dsr=float(d), sr0=float(sr0), e_max=float(emax), obs=obs, T=T,
                skew=float(sk), kurt=float(ku))


def headline(x: pd.Series, boot: bool = True) -> dict:
    """Stage-1 statistics of one daily series (the decision window)."""
    T = len(x)
    out = dict(T=T, years=T / 252, start=str(x.index[0].date()), end=str(x.index[-1].date()),
               ann_mean_pct=float(x.mean() * 252 * 100), ann_vol_pct=float(x.std() * np.sqrt(252) * 100),
               sharpe=sharpe(x), nw_t21=nw_t(x, NW_LAGS), nw_lag_auto=nw_auto_lag(T),
               nw_t_auto=nw_t(x, nw_auto_lag(T)), skew=float(x.skew()), kurt=float(x.kurt() + 3),
               pos_years_share=float((x.groupby(x.index.year).sum() > 0).mean()))
    half = T // 2
    out["sharpe_first_half"], out["sharpe_second_half"] = sharpe(x.iloc[:half]), sharpe(x.iloc[half:])
    if boot:
        mu, sr = stationary_bootstrap(x.values, BOOT_BLOCK, BOOT_REPS, SEED)
        out["boot21_mean_ci_pct"] = [float(np.percentile(mu, 2.5) * 252 * 100),
                                     float(np.percentile(mu, 97.5) * 252 * 100)]
        out["boot21_sharpe_ci"] = [float(np.nanpercentile(sr, 2.5)), float(np.nanpercentile(sr, 97.5))]
        mu63, sr63 = stationary_bootstrap(x.values, BOOT_BLOCK_ALT, BOOT_REPS, SEED)
        out["boot63_mean_ci_pct"] = [float(np.percentile(mu63, 2.5) * 252 * 100),
                                     float(np.percentile(mu63, 97.5) * 252 * 100)]
        out["boot63_sharpe_ci"] = [float(np.nanpercentile(sr63, 2.5)), float(np.nanpercentile(sr63, 97.5))]
        from scripts.cef.w4_artifacts import block_boot_t
        t, lo, hi = block_boot_t(x, block=BOOT_BLOCK, reps=BOOT_REPS, seed=SEED)
        out["mbb21_t"], out["mbb21_mean_ci_pct"] = float(t), [float(lo * 252 * 100), float(hi * 252 * 100)]
    return out


def bar(x: pd.Series) -> dict:
    """Stage 5 (decision) and the labelled readings beside it (never deciding)."""
    d = dsr(x, N_SLATE)
    legacy = dsr(x, N_LEGACY)
    yrs = len(x) / 252
    return dict(dsr_N4=d["dsr"], pass_=d["dsr"] > DSR_PASS, sr0_N4=d["sr0"], e_max_N4=d["e_max"],
                skew=d["skew"], kurt=d["kurt"], T=d["T"],
                agenda_reading_sr_sqrt_years=d["obs"] * math.sqrt(yrs),
                agenda_reading_bar=math.sqrt(2 * math.log(N_SLATE)), dsr_N162_legacy=legacy["dsr"])


def cost_grid(pnl: pd.Series, turn: pd.Series) -> dict:
    s = _stats(pnl, turn.reindex(pnl.index))
    n5, n15, n30 = s["nets"]
    return dict(gross_sr=float(s["sr"]), turn_per_yr=float(s["turn"]), net5=float(n5),
                net15=float(n15), net30=float(n30),
                flips_sign=bool(np.sign(s["sr"]) != np.sign(n30) or np.sign(n5) != np.sign(n30)))


def eras(pnl: pd.Series, turn: pd.Series) -> list:
    out = []
    tv = []
    for lab, a, b in ERAS:
        p = pnl.loc[a:b]
        if len(p) < 21:
            continue
        g = cost_grid(p, turn)
        tv.append(g["turn_per_yr"])
        out.append(dict(era=lab, n=len(p), **g))
    tv = np.array(tv)
    return out + [dict(era="turnover sd/mean", value=float(tv.std() / tv.mean()) if len(tv) and tv.mean() else None)]


# =============================================================================
# regressions (P9)
# =============================================================================
def factor_returns(R: pd.DataFrame, rf: pd.Series) -> pd.DataFrame:
    """MKT, TERM, HY, IG, COMMOD, GOLD, INTL, EM, from the primary panel and P3's r_f."""
    out = {}
    for f, (a, b) in FACTOR_NAMES.items():
        out[f] = (R[a] - rf) if b is None else (R[a] - R[b])
    return pd.DataFrame(out)


def ols_hac(y: pd.Series, X: pd.DataFrame, lags: int, ann: int) -> dict:
    """OLS with HAC (Bartlett) covariance; alpha in %/yr (x `ann`), VIFs, 95% CIs.
    Raises if any regressor or the dependent variable is missing inside the window
    (no silent row-dropping)."""
    import statsmodels.api as sm
    from statsmodels.stats.outliers_influence import variance_inflation_factor as vif
    X = X.reindex(y.index)
    if y.isna().any() or X.isna().any().any():
        bad = X.columns[X.isna().any()].tolist() + (["y"] if y.isna().any() else [])
        raise ProtocolError(f"regression inputs missing inside the window: {bad}")
    Z = sm.add_constant(X)
    f = sm.OLS(y, Z).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    ci = f.conf_int(0.05)
    lab = (lambda v: str(v)) if isinstance(y.index, pd.PeriodIndex) else (lambda v: str(v.date()))
    out = dict(n=int(f.nobs), start=lab(y.index[0]), end=lab(y.index[-1]), lags=lags,
               alpha_pct_yr=float(f.params["const"] * ann * 100), alpha_t=float(f.tvalues["const"]),
               r2=float(f.rsquared), betas={}, )
    for j, c in enumerate(Z.columns):
        if c == "const":
            continue
        out["betas"][c] = dict(beta=float(f.params[c]), t=float(f.tvalues[c]),
                               ci95=[float(ci.loc[c, 0]), float(ci.loc[c, 1])],
                               vif=float(vif(Z.values, j)))
    return out


def d4_verdict(reg: dict) -> dict:
    """Ruling 4: alpha t >= 3.0 and every |beta| <= 0.10 (OLS point estimates)."""
    worst = max(reg["betas"].items(), key=lambda kv: abs(kv[1]["beta"]))
    ok_a = reg["alpha_t"] >= 3.0
    ok_b = all(abs(v["beta"]) <= 0.10 for v in reg["betas"].values())
    return dict(alpha_ok=ok_a, betas_ok=ok_b, pass_=ok_a and ok_b,
                largest_beta=(worst[0], worst[1]["beta"]))


def monthly(pnl: pd.Series) -> pd.Series:
    """Compounded calendar-month excess P&L, indexed by month period."""
    m = (1 + pnl).groupby(pnl.index.to_period("M")).prod() - 1
    return m


def aqr_regression(pnl: pd.Series, cols: list, cal: pd.DatetimeIndex) -> dict:
    """R-AQR (reported): monthly sleeve P&L on the named AQR factors, HAC L =
    floor(4(T_m/100)^(2/9)). Only calendar months whose every session (in `cal`)
    lies inside the P&L window are used: the first and last months of a window
    that starts or ends mid-month are partial (W4's convention)."""
    ts = pd.read_parquet(AQR_TSMOM)
    vm = pd.read_parquet(AQR_VME)
    F = pd.concat([ts.set_index(ts["date"].dt.to_period("M"))[[c for c in ts.columns if c.startswith("TSMOM")]],
                   vm.set_index(vm["date"].dt.to_period("M"))[["MOM", "MOMLS_VME_FI"]].add_prefix("VME_")],
                  axis=1)
    m = monthly(pnl)
    have = pnl.groupby(pnl.index.to_period("M")).size()
    c = cal[(cal >= pnl.index[0] - pd.offsets.MonthBegin(1)) & (cal <= pnl.index[-1] + pd.offsets.MonthEnd(1))]
    need = pd.Series(1, index=c).groupby(c.to_period("M")).size()
    full = [k for k in have.index if have[k] == need.get(k, -1)]
    m = m.loc[full]
    if F[cols].reindex(m.index).isna().any().any():
        raise ProtocolError(f"AQR factors {cols} do not cover every month of the window")
    lag = int(math.floor(4 * (len(m) / 100.0) ** (2.0 / 9.0)))
    vint = dict(tsmom_sha=ts["file_sha256"].iloc[0][:16], tsmom_last=ts["last_data_month"].iloc[0],
                vme_sha=vm["file_sha256"].iloc[0][:16], vme_last=vm["last_data_month"].iloc[0])
    r = ols_hac(m, F[cols], lag, 12)
    r["vintage"] = vint
    return r


def ff_regression(pnl: pd.Series, base: pd.DataFrame) -> dict:
    """R-FF (reported): R-D4's set plus French MKT-RF, SMB, HML, UMD, daily."""
    ff = pd.read_parquet(FF_DAILY)
    ff = ff.set_index(pd.to_datetime(ff["date"]))
    X = pd.concat([base, ff[["mktrf", "smb", "hml", "umd"]].reindex(pnl.index)], axis=1)
    r = ols_hac(pnl, X, NW_LAGS, 252)
    r["vintage"] = dict(crsp_vintage=str(ff["crsp_vintage"].iloc[0]),
                        fetched=str(ff["fetched_at_utc"].iloc[0]))
    return r


# =============================================================================
# placebo and shift(3) (P10)
# =============================================================================
def placebo(Hs: pd.DataFrame, Rx: pd.DataFrame, window: pd.DatetimeIndex, real_sr: float,
            span_start: pd.Timestamp = None, draws: int = PLACEBO_DRAWS, seed: int = SEED,
            block: int = PLACEBO_BLOCK) -> dict:
    """Block-shuffled-signal placebo: H's rows permuted in contiguous `block`-row
    blocks, returns fixed; Sharpe on the same window. KILL D1 if real <= p95.

    `span_start` (team lead, 2026-10-14): only the rows dated on or after it -- the
    first session on which every fund in the test has a return -- are shuffled,
    in blocks anchored at it; earlier rows keep their dates. None or a date on or
    before H's first row shuffles every row (X2, X3)."""
    from scripts.cef.band_frontier import block_shuffle
    if span_start is not None and PLACEBO_PRE_INCEPTION_RULE != "span":
        raise ProtocolError("a placebo span was passed but the span rule is not in force")
    rng = np.random.default_rng(seed)
    inside = Hs.index >= (span_start if span_start is not None else Hs.index[0])
    srs = np.empty(draws)
    for i in range(draws):
        Hp = Hs.copy()
        Hp.loc[inside] = block_shuffle(Hs.loc[inside], block, rng).values
        srs[i] = sharpe(run(Hp, Rx, "placebo")["pnl"].reindex(window))
    p95 = float(np.percentile(srs, 95))
    return dict(draws=draws, p95=p95, p50=float(np.median(srs)), real=real_sr,
                span_start=str(Hs.index[inside][0].date()), rows_shuffled=int(inside.sum()),
                rows_fixed=int((~inside).sum()),
                rank_share_below=float((srs < real_sr).mean()), pass_=real_sr > p95)


# =============================================================================
# capacity (P11, reported)
# =============================================================================
def capacity(H: pd.DataFrame, panel: pd.DataFrame, window: pd.DatetimeIndex) -> dict:
    """Reported only. Dollar volume = prc_adj x volume, 63-session median through
    t-1. On each rebalance day (any |dH| > 0) inside the window, the largest
    name's |dH| / DV63; the median of that across rebalance days is m. The sleeve
    capital at which the largest trade reaches 1% of DV63 is 0.01 / m; the
    participation at $1m / $10m / $100m is capital x m. [U reading: 'median
    rebalance day' taken as the median of the per-day maximum.]"""
    px = wide(panel, "prc_adj").reindex(H.index)
    vol = wide(panel, "volume").reindex(H.index)
    dv = (px * vol)[H.columns].rolling(63, min_periods=21).median().shift(1)
    dH = H.diff().abs()
    dH.iloc[0] = H.iloc[0].abs()
    rows = dH.loc[dH.index.isin(window)]
    rows = rows[rows.sum(axis=1) > 0]
    # only names TRADED that day count; a traded name with no 63-session dollar
    # volume yet makes the day "without dv63" (counted, not hidden)
    per = (rows / dv.reindex(rows.index)).where(rows > 0, 0.0)
    raw_ratio = per.max(axis=1, skipna=False)
    no_dv = int(raw_ratio.isna().sum())
    ratio = raw_ratio.dropna()
    if ratio.empty:
        return dict(rebalance_days=0, rebalance_days_without_dv63=no_dv)
    m = float(ratio.median())
    return dict(rebalance_days=int(len(ratio)), rebalance_days_without_dv63=no_dv,
                median_max_trade_over_dv63=m,
                capital_at_1pct_usd=float(0.01 / m) if m > 0 else None,
                participation_1m=1e6 * m, participation_10m=1e7 * m, participation_100m=1e8 * m)


# =============================================================================
# correlation with the CEF book (P12, reported only)
# =============================================================================
def cef_book_pnl() -> pd.Series:
    """The deployed book's daily gross total-return P&L, built as
    scripts/xasset/book_profile.py builds it (v7 band, gross-capped), from its
    first position. Reported only; never a kill (ruling 3)."""
    from scripts.cef.band_frontier import band_gross_capped, build_targets, total_returns
    from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS
    if MAX_GROSS_STRESS is None:
        raise ProtocolError("spec has no max_gross_stress; the live book is gross-capped")
    T, R = build_targets()
    H = band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)
    first = H.abs().sum(axis=1).gt(0).idxmax()
    tr = evaluate(H, total_returns(R))["pnl"]
    return tr.loc[first:]


def book_correlation(x: pd.Series, book: pd.Series, R: pd.DataFrame, rf: pd.Series) -> dict:
    """Daily rho; non-overlapping 21-session rho (Pearson, Spearman); 21-session rho
    in HY-stress windows (worst quintile of 21-session HY_XS, HY_XS = HYG - rf -
    beta63 (IEF - rf), beta shifted one session), as diversification_screen.py."""
    xh = R["HYG"] - rf
    xi = R["IEF"] - rf
    b = (xh.rolling(63).cov(xi) / xi.rolling(63).var()).shift(1)
    hyxs = xh - b * xi
    d = pd.concat([x.rename("x"), book.rename("book"), hyxs.rename("hyxs")], axis=1).dropna()
    if len(d) < 63:
        return dict(n=len(d))
    g = np.arange(len(d)) // 21
    m = d.groupby(g).sum()
    m = m.iloc[:-1] if (len(d) % 21) else m        # drop a trailing partial window
    q = m["hyxs"] <= m["hyxs"].quantile(0.2)
    return dict(n_daily=len(d), start=str(d.index[0].date()), end=str(d.index[-1].date()),
                rho_daily=float(d["x"].corr(d["book"])), n_21d=int(len(m)),
                rho_21d=float(m["x"].corr(m["book"])),
                rho_21d_spearman=float(m["x"].corr(m["book"], method="spearman")),
                n_stress=int(q.sum()), rho_21d_hy_stress=float(m[q]["x"].corr(m[q]["book"])))


# =============================================================================
# results I/O
# =============================================================================
def to_jsonable(o):
    if isinstance(o, dict):
        return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, float):
        return None if not math.isfinite(o) else o
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp,)):
        return str(o.date())
    return o


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(to_jsonable(obj), indent=1, sort_keys=False) + "\n")
