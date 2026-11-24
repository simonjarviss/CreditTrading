"""R2 -- do CEF discount moves on macro-release days revert more? Zero trials, report only.

    cd <SCRATCH>/tree && python3 -I ../r2_macro_days/r2_macro_days.py | tee ../r2_macro_days/out/r2_output.txt

The design, controls and verdict rule are declared in NOTE.md Part A, written before
this script computed anything. In short:

* sets: DEPLOYED (spec 13, W4's ADV + min_names mask, 2013-06 on) and WIDE17 (the 13 +
  NAD NEA NVG NZF, no ADV filter, 2007 on: the CPI/NFP panel starts 2007);
* x = the day's discount move in the book's z units, (disc_t - disc_t-1) / sd_t, sd
  through t-1; control zlag = z_t-1;
* forward legs over sessions t+2..t+3 (shift(2)), W4 §3c's log total-return split:
  price, NAV, discount = price - NAV, exactly;
* pooled OLS on within-date demeaned data, F = b0 x + b_any x R + p_any x P + c zlag,
  Driscoll-Kraay errors (5 session lags);
* controls: placebo weekdays +-7 days; size matching on the expanding decile of the
  date's mean |x|; the price/NAV split; robustness = Fama-MacBeth by date.

WHY THIS IS NOT A NEW BACKTESTER: there is no P&L here. The panel, z, sd, the return
filter and the total-return arithmetic all come from `scripts/cef/band_frontier.py`
(`build_panel`, `total_returns`); the forward-window helper and the holdout assertion
are W4's (`scripts/cef/w4_artifacts.py`: `fwd_log`, `_assert_fit`). Only the
regression and the event calendar are local.

HOLDOUTS. Time: `build_panel(end=FIT_END)` truncates the raw panels before anything is
computed, and `_assert_fit` checks every frame that reaches a statistic. Names: only
the 17 names above are read; the 27 other names of cef_universe.csv are counted, never
read. (`total_returns` -> `distribution_yield` reads the raw close panel to divide by
P_t-1 and reindexes it to this fit index; no 2023 price reaches a statistic. That is
the harness's own behaviour, identical to W4.)

Nothing is written outside ../r2_macro_days/out/.
"""
from __future__ import annotations

import bisect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TREE = HERE.parent / "tree"
sys.path.insert(0, str(TREE))

from scripts.cef.band_frontier import (  # noqa: E402
    HOLDOUT_START, MIN_ADV, SAMPLE_START, build_panel, total_returns,
)
from scripts.cef.spec import MIN_NAMES, UNIVERSE, summary  # noqa: E402
from scripts.cef.w4_artifacts import _assert_fit, fwd_log  # noqa: E402

FIT_END = "2022-12-30"
OUT = HERE / "out"
DK_LAGS = 5                      # forward windows of adjacent sessions overlap by one day
NW_LAGS = 5
MIN_PRIOR_DATES = 250            # size-decile burn-in (NOTE A5.2)
BONF_T = 2.39                    # three release types (NOTE A8)
V6_EXTRA = ["NAD", "NEA", "NVG", "NZF"]
WIDE_START = "2007-01-02"        # the CPI/NFP panel starts 2007-01 (NOTE A2)
ERAS = {"DEPLOYED": [("2013-06..14", "2013-01-01", "2014-12-31"), ("2015-19", "2015-01-01", "2019-12-31"),
                     ("2020-22", "2020-01-01", "2022-12-31")],
        "WIDE17": [("2007-09", "2007-01-01", "2009-12-31"), ("2010-14", "2010-01-01", "2014-12-31"),
                   ("2015-19", "2015-01-01", "2019-12-31"), ("2020-22", "2020-01-01", "2022-12-31")]}
TYPES = ("FOMC", "CPI", "NFP")


# ============================================================================ data

class SetData:
    """One universe's panel, fit period only, mirroring W4's `Data` construction."""

    def __init__(self, label: str, names: list[str], adv_filter: bool, start: str):
        self.label, self.U, self.start = label, list(names), pd.Timestamp(start)
        p = build_panel(end=FIT_END, universe=self.U)
        _assert_fit(p["px"])
        full = p["px"].index
        self.idx = full[full >= pd.Timestamp(SAMPLE_START)]
        U = self.U
        px, nav = p["px"][U], p["nav"][U]
        self.r_px = p["ret"][U].reindex(self.idx)
        self.r_tr = total_returns(self.r_px)                       # price TR (harness)
        # NAV total return: D/N_{t-1} on the same ex-dates (W4 Data, verbatim logic).
        dist = self._dist_amounts(U)
        r_nav = nav.pct_change(fill_method=None).where(lambda x: x.abs() < 0.5)
        y_nav = (dist / nav.shift(1)).reindex(index=full, columns=U)
        # count ex-dates that could not reach the NAV yield (no silent zero): an ex-date
        # absent from the NAV index, or with no prior NAV, would become a zero yield
        win = dist.loc[(dist.index >= self.idx[0]) & (dist.index <= self.idx[-1])]
        missed, silent = [], []
        for t in U:
            for dd in win[t].dropna().index:
                if dd not in self.idx:
                    silent.append((t, str(dd.date()), "ex-date is not a panel session"))
                elif pd.isna(y_nav.at[dd, t]):
                    # harmless only if that day's NAV return is itself NaN (no NAV that
                    # day or the day before), so no zero yield can be booked against a move
                    if pd.notna(r_nav.at[dd, t]):
                        silent.append((t, str(dd.date()), "NAV return exists but yield missed"))
                    else:
                        missed.append((t, str(dd.date())))
        if silent:
            raise ValueError(f"{label}: ex-dates whose NAV yield would be a silent zero: {silent}")
        self.nav_yield_missed = missed
        self.r_nav_tr = (r_nav + y_nav.fillna(0.0)).reindex(self.idx)   # 0 = no ex-date that day
        self.disc_full = p["disc"][U]                                 # full history, for the sd check
        self.disc = p["disc"][U].reindex(self.idx)
        self.disc_lag = p["disc"][U].shift(1).reindex(self.idx)       # previous panel session
        self.sd = p["sd"][U].reindex(self.idx)                        # rolling sd through t-1
        self.z = p["z"][U].reindex(self.idx)
        self.zlag = p["z"][U].shift(1).reindex(self.idx)
        self.nav = nav.reindex(self.idx)
        self.nav_lag = nav.shift(1).reindex(self.idx)
        if adv_filter:
            adv = p["adv"][U].reindex(self.idx)
            elig = self.z.notna() & (adv >= MIN_ADV)
        else:
            elig = self.z.notna()
        enough = elig.sum(axis=1) >= MIN_NAMES
        self.M = elig.apply(lambda c: c & enough)
        # ALIGNMENT: x_t = (disc_t - disc_{t-1}) / sd_t, where sd_t = rolling std of disc
        # through t-1 (build_panel: .shift(1)). disc_t is t-close information known after
        # t's NAV is published -- the same timing as z_t. Asserted: sd_t equals the rolling
        # std computed on the frame truncated at t-1, on a sample of cells below.
        self.x = (self.disc - self.disc_lag) / self.sd.replace(0, np.nan)
        _assert_fit(self.r_tr, self.r_nav_tr, self.disc, self.z, self.x, self.M)

    @staticmethod
    def _dist_amounts(U):
        d = pd.read_parquet(TREE / "data/cef/cef_distributions.parquet")
        d = d[d.ticker.isin(U)]
        d["ex_date"] = pd.to_datetime(d["ex_date"])
        d = d[d.ex_date < HOLDOUT_START]
        return d.groupby(["ex_date", "ticker"])["amount"].sum().unstack()


def assert_sd_is_lagged(S: SetData, n_checks: int = 25, seed: int = 7):
    """No-lookahead check on the regressor's scale: sd_t must equal the rolling-252 std
    (min 120) of disc over sessions strictly before t."""
    from scripts.cef.band_frontier import MIN_PERIODS
    from scripts.cef.spec import Z_WINDOW
    rng = np.random.default_rng(seed)
    cells = S.sd.stack()
    pick = cells.index[rng.choice(len(cells), size=min(n_checks, len(cells)), replace=False)]
    full_disc = S.disc_full
    done = 0
    for (d, t) in pick:
        # the harness's rolling window counts panel ROWS (sessions), not valid values;
        # the rows used for date d are the Z_WINDOW rows strictly before d
        rows = full_disc[t].loc[:d].iloc[:-1].tail(Z_WINDOW)
        if rows.notna().sum() < MIN_PERIODS:
            continue
        want = rows.std()
        if not np.isclose(want, S.sd.at[d, t], rtol=1e-9, atol=1e-12):
            raise AssertionError(f"sd lookahead check failed at {d.date()} {t}: {S.sd.at[d, t]} vs {want}")
        done += 1
    if done < 10:
        raise AssertionError(f"sd lookahead check ran on only {done} cells")
    print(f"{S.label}: sd_t == std of the {Z_WINDOW} sessions strictly before t on {done} random cells (no lookahead)")


# ============================================================================ events

def load_events():
    """FOMC from the Fed pages (fomc_fed.csv), CPI/NFP from data/events.parquet [S].

    Returns dict(type -> sorted list of ORIGINAL release dates), and the set of dates to
    drop (unscheduled FOMC actions: Fed pages + the repo panel's other emergency rows)."""
    F = pd.read_csv(HERE / "fomc_fed.csv", parse_dates=["statement_date"])
    sched = F[F.scheduled & ~F.cancelled].statement_date
    unsched_fed = F[~F.scheduled & F.statement_date.notna()].statement_date
    e = pd.read_parquet(TREE / "data/events.parquet")
    e["date"] = pd.to_datetime(e["date"])
    e = e[(e.date >= "2005-01-01") & (e.date <= FIT_END)]
    repo_sched = set(e[(e.event_type == "FOMC") & e.scheduled].date)
    if set(sched) != repo_sched:
        raise ValueError(f"Fed pages vs repo FOMC disagree: fed-only {sorted(set(sched) - repo_sched)}, "
                         f"repo-only {sorted(repo_sched - set(sched))}")
    repo_emerg = set(e[(e.event_type == "FOMC") & ~e.scheduled].date)
    drop = sorted(set(unsched_fed) | repo_emerg)
    ev = {"FOMC": sorted(sched)}
    for k in ("CPI", "NFP"):
        x = e[(e.event_type == k) & e.scheduled].date
        if (x.dt.to_period("M").value_counts() != 1).any():
            raise ValueError(f"{k}: a month without exactly one release")
        ev[k] = sorted(x)
    return ev, drop, dict(fomc_sched=len(sched), fomc_unsched_fed=len(unsched_fed),
                          repo_only_emergency=sorted(str(d.date()) for d in repo_emerg - set(unsched_fed)))


def to_session(d: pd.Timestamp, idx: pd.DatetimeIndex) -> pd.Timestamp:
    """First panel session at or after d (a release on a non-session hits the next close)."""
    i = idx.searchsorted(d)
    if i >= len(idx):
        return pd.NaT
    s = idx[i]
    if (s - d).days > 4:
        raise ValueError(f"{d.date()} maps to {s.date()}, {(s - d).days} days later: a gap in the panel index")
    return s


def day_flags(S: SetData, ev, drop):
    """Date-level dummies on S.idx: R_k, P_k, R_any, P_any, dropped. Plus counts."""
    idx = S.idx
    R = pd.DataFrame(False, index=idx, columns=list(TYPES))
    moved = []
    for k in TYPES:
        for d in ev[k]:
            s = to_session(d, idx)
            if pd.isna(s):
                continue
            if s != d:
                moved.append((k, str(d.date()), str(s.date())))
            R.at[s, k] = True
    dropped = pd.Series(False, index=idx)
    for d in drop:
        s = to_session(d, idx)
        if not pd.isna(s):
            dropped.at[s] = True
    # NOTE A2: a dropped (unscheduled-FOMC) session is neither event nor ordinary, so a
    # release that lands on one leaves the sample with it; listed, not hidden
    clash = [(k, str(d.date())) for k in TYPES for d in idx[(R[k] & dropped).values]]
    R = R & ~dropped.values[:, None]
    R_any = R.any(axis=1)
    P = pd.DataFrame(False, index=idx, columns=list(TYPES))
    idxset = set(idx)
    for k in TYPES:
        for d in ev[k]:
            for c in (d - pd.Timedelta(days=7), d + pd.Timedelta(days=7)):
                # exact same weekday; a holiday is NOT shifted (it would change the weekday)
                if c in idxset and not R_any.at[c] and not dropped.at[c]:
                    P.at[c, k] = True
    P_any = P.any(axis=1)
    # a release day must never also be a placebo or a dropped day
    assert not (R_any & P_any).any() and not (R_any & dropped).any()
    return R, P, R_any, P_any, dropped, moved + [("DROPPED-with-release",) + c for c in clash]


# ============================================================================ long panel

def long_panel(S: SetData, R, P, R_any, P_any, dropped, window=(2, 3)):
    """Name-date rows with x, zlag, F_P, F_N (bp), demeaned within date over complete names."""
    a, b = window
    FP = fwd_log(S.r_tr, a, b) * 1e4
    FN = fwd_log(S.r_nav_tr, a, b) * 1e4
    # ALIGNMENT: row t of FP/FN holds sessions t+a..t+b (fwd_log shifts by -k); with
    # (2,3) that is close t+1 -> close t+3, what a book decided at t earns (shift(2)).
    _assert_fit(FP, FN)
    ok = S.M & S.x.notna() & S.zlag.notna() & FP.notna() & FN.notna()
    ok = ok.loc[(ok.index >= S.start)]
    ok = ok.loc[~dropped.reindex(ok.index)]
    n = ok.sum(axis=1)
    ok = ok.loc[n >= MIN_NAMES]
    rows = []
    for nm, M in (("x", S.x), ("zlag", S.zlag), ("FP", FP), ("FN", FN)):
        v = M.reindex(index=ok.index, columns=S.U).where(ok)
        v = v.sub(v.mean(axis=1), axis=0)                         # within-date demeaning
        rows.append(v.stack().rename(nm))
    L = pd.concat(rows, axis=1)
    L.index.names = ["date", "ticker"]
    L = L.dropna()
    L["FD"] = L["FP"] - L["FN"]
    d = L.index.get_level_values("date")
    for k in TYPES:
        L[f"R_{k}"] = R[k].reindex(d).values.astype(float)
        L[f"P_{k}"] = P[k].reindex(d).values.astype(float)
    L["R_any"] = R_any.reindex(d).values.astype(float)
    L["P_any"] = P_any.reindex(d).values.astype(float)
    pos = pd.Series(np.arange(len(S.idx)), index=S.idx)
    L["pos"] = pos.reindex(d).values
    _assert_fit(L.reset_index().set_index("date"))
    return L


# ============================================================================ estimation

def ols_dk(y: np.ndarray, X: np.ndarray, pos: np.ndarray, lags: int):
    """OLS without intercept; Driscoll-Kraay covariance (date score sums, Bartlett over
    `lags` sessions, G/(G-1)) and the date-clustered one (lags = 0)."""
    XtX = X.T @ X
    inv = np.linalg.inv(XtX)
    beta = inv @ (X.T @ y)
    e = y - X @ beta
    h = X * e[:, None]
    up, inv_pos = np.unique(pos, return_inverse=True)
    S = np.zeros((len(up), X.shape[1]))
    np.add.at(S, inv_pos, h)
    G = len(up)
    # place score sums on the full session grid so a lag is a SESSION lag, not a row lag
    grid = np.zeros((int(up.max() - up.min()) + 1, X.shape[1]))
    grid[(up - up.min()).astype(int)] = S
    om0 = grid.T @ grid
    om = om0.copy()
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1)
        g = grid[l:].T @ grid[:-l]
        om += w * (g + g.T)
    c = G / (G - 1)
    V_dk = c * inv @ om @ inv
    V_cl = c * inv @ om0 @ inv
    return beta, V_dk, V_cl, G


def selftest_dk(seed: int = 3):
    """Method check on SYNTHETIC data (a claim about the code, never the market): with
    lags=0 the DK covariance must equal a directly computed date-clustered sandwich, and
    on iid data its SE must be close to the iid SE."""
    rng = np.random.default_rng(seed)
    T, N = 1500, 12
    pos = np.repeat(np.arange(T), N)
    X = rng.standard_normal((T * N, 2))
    y = X @ np.array([0.5, -0.2]) + rng.standard_normal(T * N)
    b, Vdk0, Vcl, _ = ols_dk(y, X, pos, 0)
    inv = np.linalg.inv(X.T @ X)
    e = y - X @ b
    Sg = np.array([(X[pos == t] * e[pos == t, None]).sum(0) for t in range(T)])
    Vdirect = T / (T - 1) * inv @ (Sg.T @ Sg) @ inv
    if not np.allclose(Vdk0, Vdirect) or not np.allclose(Vcl, Vdirect):
        raise AssertionError("ols_dk lags=0 is not the date-clustered sandwich")
    _, Vdk5, _, _ = ols_dk(y, X, pos, 5)
    se_iid = np.sqrt(np.diag(inv) * e.var())
    ratio = np.sqrt(np.diag(Vdk5)) / se_iid
    if not np.all((ratio > 0.85) & (ratio < 1.15)):
        raise AssertionError(f"ols_dk on iid data: DK/iid SE ratio {ratio}")
    print(f"selftest_dk: lags=0 == clustered sandwich; iid DK(5)/iid SE ratio {ratio.round(3)} (synthetic, method check only)")


def lin(beta, V, w):
    w = np.asarray(w, float)
    est = float(w @ beta)
    se = float(np.sqrt(w @ V @ w))
    return est, est / se


def fit(L: pd.DataFrame, yname: str, cols: list[str]):
    X = np.column_stack([L[c].values for c in cols])
    beta, Vdk, Vcl, G = ols_dk(L[yname].values, X, L["pos"].values, DK_LAGS)
    return dict(cols=cols, beta=beta, Vdk=Vdk, Vcl=Vcl, G=G, n=len(L))


def design(L: pd.DataFrame, by_type: bool, size_q: pd.Series | None = None):
    """Build the regressor columns on L in place; return their names."""
    cols = []
    if size_q is None:
        cols.append("x")
    else:
        q = size_q.reindex(L.index.get_level_values("date")).values
        for k in range(1, 11):
            c = f"x_q{k}"
            L[c] = L["x"].values * (q == k)
            cols.append(c)
    types = TYPES if by_type else ("any",)
    for k in types:
        L[f"xR_{k}"] = L["x"] * L[f"R_{k}"]
        L[f"xP_{k}"] = L["x"] * L[f"P_{k}"]
        cols += [f"xR_{k}", f"xP_{k}"]
    cols.append("zlag")
    return cols


def coef(res, name, V="Vdk"):
    i = res["cols"].index(name)
    b = res["beta"][i]
    return b, b / np.sqrt(res[V][i, i])


def diff(res, a, b, V="Vdk"):
    w = np.zeros(len(res["cols"]))
    w[res["cols"].index(a)] = 1.0
    w[res["cols"].index(b)] = -1.0
    return lin(res["beta"], res[V], w)


# ============================================================================ size deciles

def size_deciles(S: SetData, dropped) -> tuple[pd.Series, pd.Series]:
    """D_t = mean |x demeaned| over the mask names with x and zlag (no forward data);
    q_t = decile of D_t among D_s, s < t (expanding, strictly prior, >= MIN_PRIOR_DATES)."""
    ok = S.M & S.x.notna() & S.zlag.notna()
    ok = ok.loc[ok.sum(axis=1) >= MIN_NAMES]
    x = S.x.reindex(ok.index).where(ok)
    x = x.sub(x.mean(axis=1), axis=0)
    D = x.abs().mean(axis=1).dropna()
    hist: list[float] = []
    q = {}
    for d, v in D.items():
        if len(hist) >= MIN_PRIOR_DATES:
            frac = bisect.bisect_left(hist, v) / len(hist)           # share of PRIOR D below v
            q[d] = min(10, 1 + int(np.floor(10 * frac)))
        bisect.insort(hist, v)                                         # v joins AFTER its own decile
    q = pd.Series(q, dtype=float)
    # assert strict priority on a sample of dates: recompute from an explicit prior slice
    rng = np.random.default_rng(11)
    for d in q.index[rng.choice(len(q), size=min(20, len(q)), replace=False)]:
        prior = D.loc[D.index < d].values
        want = min(10, 1 + int(np.floor(10 * (prior < D.at[d]).mean())))
        if want != q.at[d]:
            raise AssertionError(f"size decile lookahead check failed at {d.date()}: {q.at[d]} vs {want}")
    return D, q


# ============================================================================ Fama-MacBeth

def fm_by_date(L: pd.DataFrame, yname: str, by_type: bool = False):
    """Per-date OLS of y on [x, zlag] (demeaned, no intercept): beta_t on x; then beta_t on
    [1, R_any, P_any] (or [1, R_FOMC, R_CPI, R_NFP, P_any]) with Newey-West(NW_LAGS) errors.

    The NW covariance is `ols_dk` with one observation per date, lags counted in SESSIONS
    (statsmodels cannot be imported in this environment: its scipy `_lazywhere` import
    fails; the estimator is the same Bartlett HAC)."""
    out = []
    for d, g in L.groupby(level="date"):
        if len(g) < MIN_NAMES:
            continue
        X = g[["x", "zlag"]].values
        XtX = X.T @ X
        if np.linalg.cond(XtX) > 1e12:
            raise ValueError(f"{d.date()}: singular per-date design")
        b = np.linalg.solve(XtX, X.T @ g[yname].values)
        out.append((d, b[0], g["pos"].iat[0], g["R_any"].iat[0], g["P_any"].iat[0])
                   + tuple(g[f"R_{k}"].iat[0] for k in TYPES))
    B = pd.DataFrame(out, columns=["date", "beta", "pos", "R", "P"] + [f"R_{k}" for k in TYPES]).set_index("date")
    cols = ([f"R_{k}" for k in TYPES] + ["P"]) if by_type else ["R", "P"]
    X = np.column_stack([np.ones(len(B))] + [B[c].values for c in cols])
    beta, V, _, _ = ols_dk(B["beta"].values, X, B["pos"].values, NW_LAGS)
    se = np.sqrt(np.diag(V))
    if by_type:
        return {k: dict(R=float(beta[1 + i]), R_t=float(beta[1 + i] / se[1 + i])) for i, k in enumerate(TYPES)}
    rp, rp_t = lin(beta, V, [0.0, 1.0, -1.0])
    return dict(n_dates=len(B), ordinary=float(beta[0]), R=float(beta[1]), R_t=float(beta[1] / se[1]),
                P=float(beta[2]), P_t=float(beta[2] / se[2]), RminusP=rp, RminusP_t=rp_t,
                median_beta_R=float(B.loc[B.R == 1, "beta"].median()),
                median_beta_ord=float(B.loc[(B.R == 0) & (B.P == 0), "beta"].median()))


# ============================================================================ reporting

def fmt(b, t):
    return f"{b:+8.2f} ({t:+5.2f})"


def run_set(S: SetData, ev, drop, results: dict):
    lab = S.label
    print("\n" + "=" * 110 + f"\n{lab}: {len(S.U)} names {S.U}\n" + "=" * 110)
    R, P, R_any, P_any, dropped, moved = day_flags(S, ev, drop)
    L = long_panel(S, R, P, R_any, P_any, dropped)
    dates = L.index.get_level_values("date").unique()
    mt = sorted({t for t, _ in S.nav_yield_missed})
    print(f"sample {dates.min().date()} .. {dates.max().date()}: {len(dates)} sessions, {len(L)} name-days; "
          f"{len(S.nav_yield_missed)} ex-dates have no NAV that day (names {mt}, "
          f"{min((d for _, d in S.nav_yield_missed), default='-')} .. {max((d for _, d in S.nav_yield_missed), default='-')}); "
          f"their NAV return is NaN, so no zero yield is booked (checked; a silent case raises)")
    insample = pd.Index(dates)
    cnt = {k: int(R[k].reindex(insample).sum()) for k in TYPES}
    cnt["any"] = int(R_any.reindex(insample).sum())
    pc = {k: int(P[k].reindex(insample).sum()) for k in TYPES}
    pc["any"] = int(P_any.reindex(insample).sum())
    ndrop = int(dropped.loc[(dropped.index >= S.start)].sum())
    both = int((R.reindex(insample).sum(axis=1) > 1).sum())
    print(f"release sessions in sample: {cnt}  (sessions with two types: {both})")
    print(f"placebo sessions in sample: {pc}; dropped unscheduled-FOMC sessions (whole period from start): {ndrop}")
    mv = [m for m in moved if pd.Timestamp(m[2]) >= S.start]
    print(f"releases on a non-session, moved to the next session: {len(mv)} {mv}")
    print(f"scale: sd of demeaned x {L.x.std():.3f} z-units; of zlag {L.zlag.std():.3f}; of F_P {L.FP.std():.1f}bp")
    res = dict(sample=[str(dates.min().date()), str(dates.max().date())], sessions=len(dates), name_days=len(L),
               release_counts=cnt, placebo_counts=pc, moved=mv)

    # ---------------------------------------------------------------- headline: pooled
    print(f"\nPOOLED model, window t+2..t+3 (close t+1 -> t+3), bp of 2-day log TR per unit x; "
          f"DK({DK_LAGS}) t [date-clustered t]:")
    print(f"{'leg':<10}{'b0 ordinary':>20}{'b_any release':>20}{'p_any placebo':>20}{'b_any-p_any':>20}{'c zlag':>20}")
    pooled = {}
    for leg in ("FP", "FN", "FD"):
        cols = design(L, by_type=False)
        r = fit(L, leg, cols)
        b0, t0 = coef(r, "x"); br, tr = coef(r, "xR_any"); bp, tp = coef(r, "xP_any")
        _, trc = coef(r, "xR_any", "Vcl")
        dd, td = diff(r, "xR_any", "xP_any"); bc, tc = coef(r, "zlag")
        print(f"{leg:<10}{fmt(b0, t0):>20}{fmt(br, tr):>20}{fmt(bp, tp):>20}{fmt(dd, td):>20}{fmt(bc, tc):>20}"
              f"   [b_any clustered t {trc:+.2f}]")
        pooled[leg] = dict(b0=b0, t0=t0, b_any=br, t_any=tr, t_any_cl=trc, p_any=bp, t_p=tp, RmP=dd, t_RmP=td,
                           c=bc, t_c=tc, G=r["G"], n=r["n"])
    res["pooled"] = pooled

    # ---------------------------------------------------------------- by type
    print("\nBY-TYPE model (joint), same window; b_k = extra slope on type-k release days, p_k its placebo:")
    print(f"{'leg':<6}{'type':<6}{'b_k':>20}{'p_k':>20}{'b_k-p_k':>20}")
    bytype = {}
    for leg in ("FP", "FN", "FD"):
        cols = design(L, by_type=True)
        r = fit(L, leg, cols)
        for k in TYPES:
            bk, tk = coef(r, f"xR_{k}"); pk, tpk = coef(r, f"xP_{k}"); dk, tdk = diff(r, f"xR_{k}", f"xP_{k}")
            print(f"{leg:<6}{k:<6}{fmt(bk, tk):>20}{fmt(pk, tpk):>20}{fmt(dk, tdk):>20}")
            bytype[(leg, k)] = dict(b=bk, t=tk, p=pk, t_p=tpk, RmP=dk, t_RmP=tdk)
    res["bytype"] = {f"{a}|{b}": v for (a, b), v in bytype.items()}

    # ---------------------------------------------------------------- size-matched
    D, q = size_deciles(S, dropped)
    Lm = L.loc[L.index.get_level_values("date").isin(q.index)].copy()
    dm = Lm.index.get_level_values("date").unique()
    print(f"\nSIZE-MATCHED (control 2): slope by expanding decile of D_t = mean|x~| (>= {MIN_PRIOR_DATES} prior "
          f"sessions); sample {dm.min().date()} .. {dm.max().date()}, {len(dm)} sessions")
    qd = q.reindex(dm)
    for nm, flag in (("release", R_any), ("placebo", P_any)):
        f = flag.reindex(dm).astype(bool)
        mix = qd[f].value_counts(normalize=True).sort_index()
        print(f"  decile mix on {nm} days: " + " ".join(f"{int(k)}:{v:.2f}" for k, v in mix.items())
              + f"   (ordinary days are 0.10 each only if the size distribution were stable)")
    ordn = (~R_any.reindex(dm).astype(bool)) & (~P_any.reindex(dm).astype(bool))
    print(f"  mean D_t: release {D.reindex(dm)[R_any.reindex(dm).astype(bool)].mean():.3f}, placebo "
          f"{D.reindex(dm)[P_any.reindex(dm).astype(bool)].mean():.3f}, ordinary {D.reindex(dm)[ordn].mean():.3f}")
    print(f"{'leg':<10}{'unmatched b_any (same sample)':>32}{'matched b_any':>20}{'matched p_any':>20}"
          f"{'matched b-p':>20}{'kept':>8}")
    matched = {}
    for leg in ("FP", "FN", "FD"):
        r_u = fit(Lm, leg, design(Lm, by_type=False))
        bu, tu = coef(r_u, "xR_any")
        r_m = fit(Lm, leg, design(Lm, by_type=False, size_q=q))
        bm, tm = coef(r_m, "xR_any"); pm, tpm = coef(r_m, "xP_any"); dmm, tdm = diff(r_m, "xR_any", "xP_any")
        kept = bm / bu if bu != 0 else np.nan
        print(f"{leg:<10}{fmt(bu, tu):>32}{fmt(bm, tm):>20}{fmt(pm, tpm):>20}{fmt(dmm, tdm):>20}{kept:8.2f}")
        matched[leg] = dict(b_unm=bu, t_unm=tu, b_m=bm, t_m=tm, p_m=pm, t_pm=tpm, RmP=dmm, t_RmP=tdm, kept=kept)
        if leg == "FP":
            qs = [coef(r_m, f"x_q{k}") for k in range(1, 11)]
            print("   price-leg ordinary slope by decile b0_q (t): "
                  + " ".join(f"q{k + 1}:{b:+.0f}({t:+.1f})" for k, (b, t) in enumerate(qs)))
    res["matched"] = matched
    # by-type matched model (used only by the single-type route of the verdict, NOTE A8)
    r_mt = fit(Lm, "FP", design(Lm, by_type=True, size_q=q))
    r_ut = fit(Lm, "FP", design(Lm, by_type=True))
    mt = {}
    for k in TYPES:
        bm, tm = coef(r_mt, f"xR_{k}"); bu, tu = coef(r_ut, f"xR_{k}")
        mt[k] = dict(b_m=bm, t_m=tm, b_unm=bu, t_unm=tu, kept=bm / bu if bu else np.nan)
    print("  price leg by type, matched vs unmatched (same sample): "
          + "; ".join(f"{k} {fmt(v['b_m'], v['t_m'])} vs {fmt(v['b_unm'], v['t_unm'])}" for k, v in mt.items()))
    res["matched_bytype"] = mt

    # ---------------------------------------------------------------- Fama-MacBeth robustness
    print("\nROBUSTNESS (declared): Fama-MacBeth by date; per-date slope on x~ (with zlag~), then on [1, R_any, P_any], NW(5):")
    fmres = {}
    for leg in ("FP", "FN"):
        f = fm_by_date(L, leg)
        print(f"  {leg}: dates {f['n_dates']}, ordinary mean slope {f['ordinary']:+.1f}; release extra "
              f"{f['R']:+.1f} (t {f['R_t']:+.2f}); placebo extra {f['P']:+.1f} (t {f['P_t']:+.2f}); "
              f"R-P {f['RminusP']:+.1f} (t {f['RminusP_t']:+.2f}); median slope release {f['median_beta_R']:+.1f} vs "
              f"ordinary {f['median_beta_ord']:+.1f}")
        fmres[leg] = f
    res["fm"] = fmres
    fmt_ = fm_by_date(L, "FP", by_type=True)
    print("  FP by type, release extra: " + "; ".join(f"{k} {v['R']:+.1f} (t {v['R_t']:+.2f})" for k, v in fmt_.items()))
    res["fm_bytype"] = fmt_

    # ---------------------------------------------------------------- eras
    print("\nBY ERA, pooled model, price leg (F_P), re-estimated within each era:")
    eras = {}
    for elab, a, b in ERAS[lab]:
        Le = L.loc[(L.index.get_level_values("date") >= a) & (L.index.get_level_values("date") <= b)].copy()
        if Le.empty:
            continue
        ne = int(Le.R_any.groupby(level="date").first().sum())
        r = fit(Le, "FP", design(Le, by_type=False))
        b0, t0 = coef(r, "x"); br, tr = coef(r, "xR_any"); bp, tp = coef(r, "xP_any")
        print(f"  {elab:<12} sessions {Le.index.get_level_values('date').nunique():5d}, release {ne:4d}: "
              f"b0 {fmt(b0, t0)}  b_any {fmt(br, tr)}  p_any {fmt(bp, tp)}")
        eras[elab] = dict(b0=b0, t0=t0, b_any=br, t_any=tr, p_any=bp, t_p=tp, n_release=ne)
    res["eras"] = eras

    # ---------------------------------------------------------------- context: t+1 (infeasible)
    L1 = long_panel(S, R, P, R_any, P_any, dropped, window=(1, 1))
    print("\nCONTEXT (never decides): the same pooled model on t+1 only (close t -> t+1), INFEASIBLE for any book "
          "decided at t:")
    ctx = {}
    for leg in ("FP", "FN", "FD"):
        r = fit(L1, leg, design(L1, by_type=False))
        b0, t0 = coef(r, "x"); br, tr = coef(r, "xR_any"); bp, tp = coef(r, "xP_any")
        print(f"  {leg}: b0 {fmt(b0, t0)}  b_any {fmt(br, tr)}  p_any {fmt(bp, tp)}")
        ctx[leg] = dict(b0=b0, t0=t0, b_any=br, t_any=tr, p_any=bp, t_p=tp)
    res["ctx_t1"] = ctx

    # ---------------------------------------------------------------- context: release-day anatomy
    ok = S.M & S.x.notna()
    ok = ok.loc[insample]
    navflat = (S.nav.reindex(insample) == S.nav_lag.reindex(insample)).where(ok)
    dP = np.log1p(S.r_tr.reindex(insample)).where(ok)
    dN = np.log1p(S.r_nav_tr.reindex(insample)).where(ok)
    dP = dP.sub(dP.mean(axis=1), axis=0)
    dN = dN.sub(dN.mean(axis=1), axis=0)
    dD = dP - dN
    print("\nCONTEXT: release-day anatomy (same sessions):")
    anat = {}
    for nm, mask in (("release", R_any.reindex(insample)), ("placebo", P_any.reindex(insample)),
                     ("ordinary", ~R_any.reindex(insample) & ~P_any.reindex(insample))):
        m = mask.astype(bool)
        flat = float(navflat[m].stack().mean())
        J = pd.concat([dP[m].stack().rename("p"), dN[m].stack().rename("n")], axis=1).dropna()
        J["d"] = J.p - J.n
        share = float(np.cov(J.p.values, J.d.values)[0, 1] / J.d.var())
        absP, absN = float(J.p.abs().mean() * 1e4), float(J.n.abs().mean() * 1e4)
        print(f"  {nm:<9} sessions {int(m.sum()):5d}: NAV unchanged on {flat:6.1%} of name-days; mean |demeaned "
              f"price TR| {absP:5.1f}bp, |NAV TR| {absN:5.1f}bp; price share of the day's demeaned discount move "
              f"{share:5.2f}")
        anat[nm] = dict(nav_flat=flat, absP=absP, absN=absN, price_share=share)
    res["anatomy"] = anat
    results[lab] = res
    return res


def verdict(res_dep, res_wide):
    p, m, f = res_dep["pooled"]["FP"], res_dep["matched"]["FP"], res_dep["fm"]["FP"]
    tests = {
        "1 price b_any<0, t<=-2": p["b_any"] < 0 and p["t_any"] <= -2.0,
        "2 beats placebo (b-p) t<=-2": p["RmP"] < 0 and p["t_RmP"] <= -2.0,
        "3 matched t<=-2 and kept>=50%": m["t_m"] <= -2.0 and m["kept"] >= 0.5,
        "4 FM release-minus-ordinary < 0": f["R"] < 0,
        "5 WIDE17 not opposite with |t|>=2": not (np.sign(res_wide["pooled"]["FP"]["b_any"]) != np.sign(p["b_any"])
                                                  and abs(res_wide["pooled"]["FP"]["t_any"]) >= 2.0),
    }
    d, n = res_dep["pooled"]["FD"], res_dep["pooled"]["FN"]
    art = (d["b_any"] < 0 and d["t_any"] <= -2.0 and not tests["1 price b_any<0, t<=-2"]
           and n["b_any"] > 0 and n["b_any"] >= 0.5 * abs(d["b_any"]))
    single = {}
    for k in TYPES:
        bt, mt, ft = res_dep["bytype"][f"FP|{k}"], res_dep["matched_bytype"][k], res_dep["fm_bytype"][k]
        single[k] = (bt["b"] < 0 and bt["t"] <= -BONF_T and bt["RmP"] < 0 and bt["t_RmP"] <= -BONF_T
                     and mt["t_m"] <= -BONF_T and mt["kept"] >= 0.5 and ft["R"] < 0)
    if all(tests.values()):
        v = "PROMISING"
    elif any(single.values()):
        v = f"PROMISING (single type: {[k for k, ok in single.items() if ok]})"
    elif art:
        v = "ARTIFACT"
    else:
        v = "NOTHING"
    return v, tests, art, single


def main():
    OUT.mkdir(exist_ok=True)
    print(summary())
    print(f"R2 macro-release-day screen -- FIT PERIOD ONLY (<= {FIT_END}); holdout sealed. "
          f"Run {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC.")
    Pp = pd.read_parquet(TREE / "data/cef/cef_prices.parquet", columns=["date"])
    Nn = pd.read_parquet(TREE / "data/cef/cef_nav.parquet", columns=["date"])
    Dd = pd.read_parquet(TREE / "data/cef/cef_distributions.parquet", columns=["ex_date"])
    e = pd.read_parquet(TREE / "data/events.parquet")
    print(f"panels: cef_prices last {Pp.date.max().date()}, cef_nav last {Nn.date.max().date()}, cef_distributions "
          f"last ex-date {Dd.ex_date.max().date()}, events.parquet CPI last {pd.to_datetime(e[e.event_type == 'CPI'].date).max().date()}"
          f" / NFP last {pd.to_datetime(e[e.event_type == 'NFP'].date).max().date()} (read-only; only <= {FIT_END} used)")
    uni = pd.read_csv(TREE / "data/cef/cef_universe.csv")
    v6 = list(UNIVERSE) + V6_EXTRA
    print(f"names: deployed {len(UNIVERSE)}, wide {len(v6)}; cef_universe.csv holds {len(uni)}, of which "
          f"{len(set(uni.ticker) - set(v6))} are the sealed name holdout and are NOT read")
    ev, drop, info = load_events()
    print(f"events: FOMC scheduled (Fed pages == repo panel) {info['fomc_sched']}; unscheduled statements on the Fed "
          f"pages {info['fomc_unsched_fed']}; extra repo-only emergency rows {info['repo_only_emergency']}; "
          f"CPI {len(ev['CPI'])}, NFP {len(ev['NFP'])} ({ev['CPI'][0].date()} .. {ev['NFP'][-1].date()})")
    selftest_dk()
    results = {}
    dep = SetData("DEPLOYED", list(UNIVERSE), adv_filter=True, start=SAMPLE_START)
    assert_sd_is_lagged(dep)
    wide = SetData("WIDE17", v6, adv_filter=False, start=WIDE_START)
    assert_sd_is_lagged(wide)
    rd = run_set(dep, ev, drop, results)
    rw = run_set(wide, ev, drop, results)
    v, tests, art, single = verdict(rd, rw)
    print("\n" + "=" * 110 + "\nVERDICT (NOTE A8; deciding set DEPLOYED, pooled, price leg, t+2..t+3)")
    for k, ok in tests.items():
        print(f"  {'PASS' if ok else 'fail'}  {k}")
    print(f"  ARTIFACT condition met: {art}; single-type Bonferroni passes: {single}")
    print(f"  => {v}")
    results["verdict"] = dict(verdict=v, tests=tests, artifact=art, single=single)
    def _js(o):
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, (np.floating, np.integer)):
            return float(o)
        return str(o)
    (OUT / "r2_results.json").write_text(json.dumps(results, indent=1, default=_js))


if __name__ == "__main__":
    main()
