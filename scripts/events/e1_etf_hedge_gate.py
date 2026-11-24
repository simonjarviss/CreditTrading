"""E1 revived: hedge the merger TARGET with a liquid ETF, not by shorting the acquirer.

    export QUANTT_ENV_FILE=/abs/path/config/.env   # R2 (CRSP), Alpaca cef key, SEC_USER_AGENT; never printed
    python3 scripts/events/e1_etf_hedge_gate.py                      # CRSP, EDGAR N-PORT, Alpaca today
    python3 scripts/events/e1_etf_hedge_gate.py --offline --today 2026-10-15   # the same, from the caches

WHY THIS EXISTS (team lead, 2026-10-15, special-situations sprint job 2)
-----------------------------------------------------------------------
E1 is the NAV-for-NAV CEF merger pair: long the target from the close of A+1,
short the acquirer, to completion. Its gross effect lives in munis (+167bp
median, t 2.41, `results/events/EDGAR_EVENTS_2026-10-12.md` §3), and gate G1a
failed there because Alpaca will not lend most muni acquirers
(`results/events/G1A_SHORTABILITY_2026-10-13.md`). The idea under test: keep the
long target and hedge it with a liquid, shortable ETF. This module measures
whether such a hedge is GOOD ENOUGH to keep the effect visible, and nothing
else.

ZERO TRIALS. HEDGE QUALITY ONLY.
* No ETF-hedged announcement->completion return is computed, for any deal.
  That return IS the trial. Every return this module computes on a target is
  dated inside a window that ends `GUARD_SESSIONS` target sessions before the
  EDGAR announcement date, so no measurement sees the deal.
* The ONLY deal-window figures read are the existing acquirer-pair returns
  (`pair_A1_to_close`, published 2026-10-12), and only per whole segment, to
  re-measure the effect's median, dispersion and clustered t at run time
  (H14: a gate never keys on a number written in a document). Nothing is
  computed on a sub-sample of those returns: the acquirer-shortable subset is
  compared on pre-announcement residuals only.
* Every date is before 2023-01-01: `crsp_events.daily` cannot return a later
  row, and `assert_pre_holdout` re-checks every window and N-PORT month.
* Only the 167 EDGAR-dated, priced deals are used. They exclude every
  `data/cef/cef_universe.csv` name by ticker and by CRSP permno, on both legs
  (`merger_pairs.pairable_events`); `assert_no_universe` re-checks that here
  and raises, so the 27-name comparison set is not consumed.
Alpaca (today's borrow flags and today's dollar volume) and IBKR's shortstock
file are COSTS AND AVAILABILITY, not returns.

THE WINDOWS (per target; all in the target's own valid CRSP sessions)
--------------------------------------------------------------------
    ... | estimation: EST_SESSIONS | test: h | guard: GUARD_SESSIONS | A (EDGAR date)
* `h` is the segment's median hold in sessions, re-measured at run time from
  the sample's `tdays_to_close` (sessions in (A, completion]).
* The GUARD exists because 93 of 186 EDGAR dates are upper bounds (the
  acquirer's N-14; the true announcement can be earlier), and the agent's
  board/press dates ran up to 40 calendar days ahead of EDGAR's
  (`EDGAR_EVENTS_2026-10-12.md` §3, §6). 42 sessions (about two months) covers
  that; it was set from that fact, before any residual was computed.
* The ESTIMATION window gives the hedge ratio. The TEST window, which has the
  length of a typical hold, is out of sample for that ratio: the realised
  hedged residual over it is the honest analogue of what the hedge would have
  left over a deal of median length.

THE MEASUREMENTS (per target x hedge)
-------------------------------------
* Returns are CRSP `ret` (total return). A day with no valid price has NaN
  `ret`; the next valid `ret` spans from the last valid price (CRSP's
  convention, tested on these extracts by `merger_pairs.bridging_check`). So
  each observation spans (previous valid target date, this date], and the
  hedge's return is taken over THE SAME SPAN from its own total-return index.
  A span longer than MAX_GAP missing days is dropped and counted.
* Hedge ratio: Dimson (1979) beta, the sum of the slopes on the hedge's
  same-span and previous-span returns. CEFs trade thinly and muni NAVs are
  matrix-priced, so a target's close can lag the ETF's; a lag-0 OLS beta would
  be biased toward zero and under-hedge. (`beta_ols` is reported beside it.)
* Correlation: lag-0 on daily spans, and on non-overlapping 5-span blocks
  (which absorbs the lag).
* RESIDUAL VOL OVER THE HOLD (time series, in sample): the standard deviation
  of the hedged residual R_T - beta * R_H on non-overlapping 5-span blocks of
  the estimation window, times sqrt(h / 5). Blocks, not days: with a lagged
  target, daily residuals carry lead-lag noise that cancels over a hold, so a
  daily sd times sqrt(h) overstates the hold's risk.
* REALISED OUT-OF-SAMPLE RESIDUAL: e = R_T(test) - beta_est * R_H(test), one
  number per target. Its CROSS-SECTIONAL dispersion is like-for-like with the
  dispersion of the deal returns themselves (also one number per deal).
* Unhedged: the same two figures with beta = 0, as the baseline.
* The acquirer as the hedge: the same procedure, with the acquirer's CRSP
  series in place of the ETF. In these windows the acquirer is just a similar
  fund; inside a deal it is tied to the target by the NAV ratio, so its
  in-deal residual is far smaller. That in-deal residual is what the existing
  pair's dispersion already measures, and it is shown beside.

NAV (the second view; `nport_monthly`)
--------------------------------------
No daily NAV history exists in this repo, or in any source found, for funds
that merged away in 2010-22 (`data/cef/` and `data/cef_families/` hold
today's listed funds only; CRSP's mutual-fund NAVs do not cover CEFs,
`docs/DATA.md` §3). The one primary source is Form N-PORT: each public
NPORT-P carries the fund's monthly total returns for the three months of its
fiscal quarter (Item B.5.a), "calculated in accordance with ... Instruction 13
to sub-Item 1 of Item 4 of Form N-2" for a closed-end fund, i.e. on NAV.
Public filings start in 2019, so only targets announced from about 2020 have
NAV months in their windows; that coverage is reported, never filled.
Month 1 is the earliest month of the quarter (readme: "First Month total
returns"; checked on BlackRock MuniYield California's filing for the quarter
ending 2020-04-30: +2.41 / -8.82 / -2.36, i.e. February, March, April 2020),
and `nport_alignment_check` re-tests the order against the hedge on every run.

THE GATE (proposed for the team lead; `gate_verdict`)
-----------------------------------------------------
Per segment, a hedge PASSES when all of these hold:
  (a) BUILDABLE: Alpaca says `shortable` and `easy_to_borrow` today and on
      every earlier read on file (borrow flags change daily; CLAUDE.md
      landmine 5);
  (b) CAPACITY: at a $1m long, the hedge's short (beta x $1m) is at most
      CAPACITY_MAX_PARTICIPATION of the hedge's dollar ADV today;
  (c) RESIDUAL: both the median time-series residual vol over the hold AND the
      cross-sectional sd of the realised out-of-sample residuals are at most
      GATE_X of the dispersion (sd) of the segment's deal returns.
GATE_X = 0.5 because added noise that is independent of the effect inflates a
trade's dispersion by sqrt(1 + X^2): 12% at X = 0.5. `t_ceiling_x` reports the
largest X that would keep the re-measured clustered t at or above E1's kill
line of 2, as a second reading; the verdict uses GATE_X.
A segment passes if any buildable hedge passes. The hedge named "best" is the
lowest median time-series residual among hedges measured on at least half the
segment's targets; with nine correlated muni candidates that is a mild
in-sample selection, which the report states.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:  # run as a script, not -m
    sys.path.insert(0, str(REPO))

from scripts.events import crsp_events as ce  # noqa: E402

OUT = REPO / "results" / "events"
CACHE = OUT / "_cache_e1_hedge"
SAMPLE = OUT / "merger_ann_sample_edgar.csv"          # merger_pairs.py --edgar-dates (gitignored)
EDGAR_DATES = OUT / "merger_edgar_dates.csv"          # edgar_merger_dates.py (gitignored): target CIKs
G1A_DEALS = OUT / "g1a" / "g1a_historical_deals.csv"  # g1a_shortability.py (gitignored): H3 flags
IBKR_FILE = OUT / "_cache_g1a" / "ibkr_usa_2026-10-13.txt"   # cached by g1a_shortability.py
# The earlier Alpaca read of ETF flags on file (tracked; XASSET slate check, 2026-10-12).
EARLIER_FLAGS = (REPO / "results" / "xasset" / "feasibility" / "slate_feasibility_2026-10-12.csv",)

TIME_HOLDOUT = pd.Timestamp("2023-01-01")
N_SAMPLE = 167
PRICED = ("ok", "bridged")

# Candidate hedges per segment, fixed before any residual was computed (the
# team lead's list, plus the short-duration SHM beside SUB, the long-duration
# MLN because leveraged muni CEFs run long effective duration, and the two
# state funds with an iShares ETF). Equity and BDC are not where the effect
# lives; they get broad, liquid proxies.
CANDIDATES = {
    "muni": ("MUB", "VTEB", "TFI", "HYD", "SUB", "SHM", "MLN"),
    "taxable_income": ("HYG", "JNK", "LQD", "BKLN", "PFF"),
    "equity_other": ("SPY", "EFA", "PFF"),
    "bdc": ("BIZD", "HYG", "BKLN", "SPY"),
}
# ADDED AFTER THE FIRST RUN (2026-10-15), and labelled so everywhere: that run
# found every muni ETF `hard_to_borrow` at Alpaca, so the only shortable rate
# hedges for a muni target are Treasury ETFs. They are measured and enter the
# gate (a pass would matter), but never the "best" selection, which stays on
# the candidates fixed in advance.
POST_HOC = {"muni": ("IEF", "TLT")}
# State-matched muni ETFs, applied to targets whose CRSP name names the state.
STATE_ETF = {"CMF": re.compile(r"\bCALIF|\bCA\b"), "NYF": re.compile(r"\bNEW YORK\b|\bN Y\b|\bNY\b")}
ETF_SHRCD = 73

EST_SESSIONS = 252
GUARD_SESSIONS = 42
BLOCK = 5
MAX_GAP = 10              # as merger_pairs.MAX_GAP: CRSP bridges at most 10 missing periods
MIN_EST_OBS = 200         # of 252: a hedge ratio on fewer aligned spans is not reported
MIN_TEST_FRAC = 0.8       # of h: the test window must be mostly priced
MIN_NAV_MONTHS = 9

GATE_X = 0.5
CAPACITY_MAX_PARTICIPATION = 0.01
LONG_NOTIONALS = (100_000.0, 1_000_000.0)
ADV_SESSIONS = 63
KILL_T = 2.0              # E1's pre-registered kill line on the clustered t (plan §3)
# H5 eras, by announcement year (2023-26 cannot occur: every deal completes by 2022).
ERA_BINS = (2004, 2009, 2014, 2019, 2022)
ERA_LABELS = ("2005-09", "2010-14", "2015-19", "2020-22")


class WindowError(ValueError):
    """A window reached into the deal or past the time holdout."""


# ----------------------------------------------------------------- guards

def assert_no_universe(sample: pd.DataFrame, nm: pd.DataFrame) -> dict:
    """Raise if any target or acquirer is a `cef_universe.csv` fund, by ticker
    or by any CRSP permno that carried a universe ticker (crsp_events)."""
    uni = ce.universe()
    tick = set(uni["ticker"])
    perm = {p for ps in ce.universe_permnos(nm).values() for p in ps}
    hit_t = sample[sample["permno"].isin(perm) | sample["ticker"].isin(tick)]
    hit_a = sample[sample["nwperm"].isin(perm) | sample["acq"].isin(tick)]
    if len(hit_t) or len(hit_a):
        raise AssertionError(
            f"the hedge study must not touch cef_universe.csv: targets {hit_t['ticker'].tolist()}, "
            f"acquirers {hit_a['acq'].tolist()}")
    return {"universe_tickers": len(tick), "universe_permnos": len(perm),
            "targets_checked": int(sample["permno"].nunique()),
            "acquirers_checked": int(sample["nwperm"].nunique())}


def assert_pre_holdout(when, what: str) -> None:
    w = pd.Timestamp(when)
    if w >= TIME_HOLDOUT:
        raise WindowError(f"{what} is dated {w.date()}: the 2023-01-01 time holdout is sealed")


# ----------------------------------------------------------- the sample

def load_sample(path: Path = SAMPLE) -> pd.DataFrame:
    """The 167 EDGAR-dated, priced deals, selected by `status` (as G1a does)."""
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing: run scripts/events/merger_pairs.py --edgar-dates")
    s = pd.read_csv(path)
    s = s[s["status"].isin(PRICED)].copy()
    if len(s) != N_SAMPLE:
        raise ValueError(f"expected the {N_SAMPLE} priced EDGAR-dated deals, got {len(s)}")
    s["ann"] = pd.to_datetime(s["ann"])
    s["completion"] = pd.to_datetime(s["completion"])
    for c in ("permno", "nwperm", "tdays_to_close"):
        s[c] = s[c].astype(int)
    if s["permno"].duplicated().any():
        raise ValueError("a target permno appears twice in the sample")
    return s.reset_index(drop=True)


def segment_holds(s: pd.DataFrame) -> dict:
    """Median hold per segment, in target sessions (A, completion], re-measured now."""
    return {c: int(round(float(g["tdays_to_close"].median()))) for c, g in s.groupby("cls")}


def effect_by_segment(s: pd.DataFrame) -> dict:
    """The existing acquirer-pair figure per WHOLE segment, re-measured at run
    time: median, sd, robust sd, clustered t. No sub-sample is ever taken."""
    from scripts.events.merger_pairs import clustered_t
    out = {}
    for c, g in s.groupby("cls"):
        v = g["pair_A1_to_close"].astype(float)
        if v.isna().any():
            raise ValueError(f"segment {c}: a priced deal has no pair return")
        grp = g["nwperm"].astype(str) + "@" + g["ann"].dt.date.astype(str)
        t = clustered_t(v, grp) if len(v) >= 3 else float("nan")
        out[c] = {"n": int(len(v)), "groups": int(grp.nunique()),
                  "median": float(v.median()), "mean": float(v.mean()),
                  "sd": float(v.std(ddof=1)) if len(v) > 1 else float("nan"),
                  "robust_sd": float(1.4826 * (v - v.median()).abs().median()),
                  "clustered_t": float(t)}
    return out


def t_ceiling_x(t_pair: float, kill_t: float = KILL_T) -> float:
    """Largest added-noise ratio X (noise sd / effect sd) that keeps t >= kill_t,
    if the noise is independent of the effect: t / sqrt(1 + X^2) >= kill_t."""
    if not np.isfinite(t_pair) or t_pair <= kill_t:
        return float("nan")
    return float(np.sqrt((t_pair / kill_t) ** 2 - 1))


def state_etf(name: str) -> str | None:
    hits = [etf for etf, rx in STATE_ETF.items() if rx.search(str(name).upper())]
    if len(hits) > 1:
        raise ValueError(f"{name!r} matches more than one state ETF: {hits}")
    return hits[0] if hits else None


# ------------------------------------------------------------ CRSP inputs

def etf_permnos(nm: pd.DataFrame, tickers, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Ticker -> the single ETF permno (share code 73) carrying it during [start, end]."""
    out = {}
    for tk in sorted(set(tickers)):
        r = nm[(nm["ticker"] == tk) & (nm["shrcd"] == ETF_SHRCD) & (nm["nameendt"] >= start) & (nm["namedt"] <= end)]
        ps = sorted(r["permno"].unique())
        if len(ps) != 1:
            raise LookupError(f"ETF {tk}: expected one share-code-73 permno over {start.date()}..{end.date()}, got {ps}")
        out[tk] = int(ps[0])
    return out


def series(dsf: pd.DataFrame) -> dict:
    """permno -> frame indexed by date with `ret`, `prc`, `vol` and the
    total-return index `idx` on valid-`ret` dates (NaN elsewhere)."""
    out = {}
    for p, g in dsf.groupby("permno"):
        g = g.sort_values("date").set_index("date")[["ret", "prc", "vol"]].copy()
        if len(g) and g.index.max() >= TIME_HOLDOUT:
            raise WindowError(f"permno {p}: CRSP rows reach {g.index.max().date()}")
        g["pos"] = np.arange(len(g))
        v = g["ret"].notna()
        g["idx"] = np.nan
        g.loc[v, "idx"] = (1 + g.loc[v, "ret"]).cumprod()
        out[int(p)] = g
    return out


def windows(valid_dates: pd.DatetimeIndex, ann: pd.Timestamp, h: int,
            est: int = EST_SESSIONS, guard: int = GUARD_SESSIONS):
    """(est_start, test_start, test_end) on the target's valid dates before `ann`,
    or None if the history is too short. Each is an anchor: returns run over
    (est_start, test_start] and (test_start, test_end]."""
    d = valid_dates[valid_dates < ann]
    need = est + h + guard + 1
    if len(d) < need:
        return None
    e = d[-1 - guard]
    s0 = d[-1 - guard - h]
    s_est = d[-1 - guard - h - est]
    if not (s_est < s0 < e < ann):
        raise WindowError(f"window anchors out of order: {s_est} {s0} {e} {ann}")
    assert_pre_holdout(e, "a test window end")
    return s_est, s0, e


def spans(T: pd.DataFrame, H: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    """Aligned span returns over (a, b]: one row per valid target date t in
    (a, b], spanning (previous valid target date, t]. The hedge return is its
    index ratio over the same span. Drops (counted): a span bridging more than
    MAX_GAP missing target rows; a span whose ends the hedge does not price."""
    tv = T[T["idx"].notna()]
    tv = tv[(tv.index >= a) & (tv.index <= b)]
    if tv.empty or tv.index[0] != a:
        raise WindowError(f"window anchor {a.date()} is not a valid target date")
    t0, t1 = tv.index[:-1], tv.index[1:]
    gap = tv["pos"].values[1:] - tv["pos"].values[:-1] - 1
    rT = tv["idx"].values[1:] / tv["idx"].values[:-1] - 1
    hi = H["idx"].reindex(tv.index)
    rH = hi.values[1:] / hi.values[:-1] - 1
    df = pd.DataFrame({"start": t0, "end": t1, "gap": gap, "rT": rT, "rH": rH})
    drops = {"long_gap": int((df["gap"] > MAX_GAP).sum()),
             "hedge_unpriced": int(((df["gap"] <= MAX_GAP) & df["rH"].isna()).sum())}
    return df, drops


def dimson(rT: np.ndarray, rH: np.ndarray, rH_lag: np.ndarray) -> tuple[float, float]:
    """(Dimson beta = b0 + b1, lag-0 OLS beta), both with an intercept."""
    X = np.column_stack([np.ones_like(rH), rH, rH_lag])
    b = np.linalg.lstsq(X, rT, rcond=None)[0]
    X0 = np.column_stack([np.ones_like(rH), rH])
    b0 = np.linalg.lstsq(X0, rT, rcond=None)[0]
    return float(b[1] + b[2]), float(b0[1])


def block_returns(rT: np.ndarray, rH: np.ndarray, block: int = BLOCK) -> tuple[np.ndarray, np.ndarray]:
    """Compounded returns on non-overlapping blocks of `block` consecutive spans
    (a trailing partial block is dropped)."""
    n = (len(rT) // block) * block
    if n == 0:
        return np.array([]), np.array([])
    bT = np.prod(1 + rT[:n].reshape(-1, block), axis=1) - 1
    bH = np.prod(1 + rH[:n].reshape(-1, block), axis=1) - 1
    return bT, bH


def cum(S: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp) -> float:
    """Total return over (a, b] from the index, or NaN if either end is unpriced
    or a missing run inside is longer than MAX_GAP."""
    if a not in S.index or b not in S.index or pd.isna(S.at[a, "idx"]) or pd.isna(S.at[b, "idx"]):
        return float("nan")
    w = S.loc[(S.index > a) & (S.index <= b), "ret"]
    run = w.isna().astype(int).groupby(w.notna().cumsum()).sum()
    if len(run) and run.max() > MAX_GAP:
        return float("nan")
    return float(S.at[b, "idx"] / S.at[a, "idx"] - 1)


def hedge_stats(T: pd.DataFrame, H: pd.DataFrame, win: tuple, h: int) -> dict:
    """The per-target x hedge measurement (module docstring)."""
    s_est, s0, e = win
    est, d_est = spans(T, H, s_est, s0)
    # The lag of the first span is the span before the window: take it from one
    # extra span, never from a zero.
    tv = T.index[T["idx"].notna()]
    prev = tv[tv < s_est]
    rec = {"est_start": s_est, "test_start": s0, "test_end": e, "h": h,
           "est_drop_long_gap": d_est["long_gap"], "est_drop_hedge_unpriced": d_est["hedge_unpriced"]}
    if len(prev):
        pre, _ = spans(T, H, prev[-1], s_est)
        lag_first = pre["rH"].iloc[-1] if len(pre) else np.nan
    else:
        lag_first = np.nan
    est["rH_lag"] = np.concatenate([[lag_first], est["rH"].values[:-1]])
    ok = (est["gap"] <= MAX_GAP) & est["rH"].notna() & est["rH_lag"].notna()
    est_ok = est[ok]
    rec["n_est"] = int(len(est_ok))
    if len(est_ok) < MIN_EST_OBS:
        rec["status"] = f"estimation window has {len(est_ok)} aligned spans (< {MIN_EST_OBS})"
        return rec
    rT, rH, rL = (est_ok[c].values.astype(float) for c in ("rT", "rH", "rH_lag"))
    beta, beta_ols = dimson(rT, rH, rL)
    rec["beta"], rec["beta_ols"] = beta, beta_ols
    rec["corr_d"] = float(np.corrcoef(rT, rH)[0, 1])
    # Blocks are built on the full estimation spans (gaps <= MAX_GAP only), in order.
    eb = est[(est["gap"] <= MAX_GAP) & est["rH"].notna()]
    bT, bH = block_returns(eb["rT"].values.astype(float), eb["rH"].values.astype(float))
    rec["n_blocks"] = int(len(bT))
    rec["corr_5"] = float(np.corrcoef(bT, bH)[0, 1])
    scale = np.sqrt(h / BLOCK)
    rec["res_vol_hold"] = float(np.std(bT - beta * bH, ddof=1) * scale)
    rec["unhedged_vol_hold"] = float(np.std(bT, ddof=1) * scale)
    rec["res_vol_hold_daily_x_sqrt_h"] = float(np.std(rT - beta * rH, ddof=1) * np.sqrt(h))
    # Out of sample: the test window.
    RT, RH = cum(T, s0, e), cum(H, s0, e)
    test, _ = spans(T, H, s0, e)
    rec["n_test"] = int(((test["gap"] <= MAX_GAP) & test["rH"].notna()).sum())
    if not np.isfinite(RT) or not np.isfinite(RH) or rec["n_test"] < MIN_TEST_FRAC * h:
        rec["status"] = "test window not priced"
        return rec
    rec["R_T_test"], rec["R_H_test"] = RT, RH
    rec["resid_oos"] = RT - beta * RH
    tt = test[(test["gap"] <= MAX_GAP) & test["rH"].notna()]
    tt_l = np.concatenate([[est["rH"].values[-1]], tt["rH"].values[:-1]])
    m = np.isfinite(tt_l)
    rec["beta_test"] = dimson(tt["rT"].values[m], tt["rH"].values[m], tt_l[m])[0]
    rec["adv_hedge_window_usd"] = float((H["prc"] * H["vol"]).loc[s_est:e].median())
    rec["status"] = "ok"
    return rec


# ------------------------------------------------------- N-PORT monthly NAV

NPORT_FORMS = ("NPORT-P", "NPORT-P/A")
_RTN = re.compile(r"<monthlyTotReturn\b([^>]*)/?>")
_ATTR = re.compile(r'(\w+)="([^"]*)"')
_REPDATE = re.compile(r"<repPdDate>\s*(\d{4}-\d{2}-\d{2})\s*</repPdDate>")


def parse_nport_returns(xml: str) -> tuple[pd.Timestamp, list[float]]:
    """(reporting-period date, [month1, month2, month3] in decimals) from an
    NPORT-P primary_doc.xml. Raises on a missing date, a missing return block,
    or more than one class (a CEF has one)."""
    m = _REPDATE.search(xml)
    if not m:
        raise ValueError("N-PORT: no <repPdDate>")
    rets = _RTN.findall(xml)
    if len(rets) != 1:
        raise ValueError(f"N-PORT: expected one <monthlyTotReturn>, found {len(rets)}")
    a = dict(_ATTR.findall(rets[0]))
    try:
        vals = [float(a[f"rtn{i}"]) / 100.0 for i in (1, 2, 3)]
    except KeyError as k:
        raise ValueError(f"N-PORT: <monthlyTotReturn> lacks {k}") from None
    return pd.Timestamp(m.group(1)), vals


def nport_months(rep_date: pd.Timestamp, vals: list[float]) -> pd.Series:
    """Month 1 is the EARLIEST month of the quarter (module docstring): the
    three returns belong to the months ending rep_date-2, -1, 0."""
    me = pd.Timestamp(rep_date).to_period("M")
    return pd.Series(vals, index=[(me - 2).to_timestamp("M"), (me - 1).to_timestamp("M"), me.to_timestamp("M")])


def nport_monthly(client, cik: int, upto: pd.Timestamp) -> tuple[pd.Series, dict]:
    """All NPORT-P monthly NAV returns of `cik` for months ending on or before
    `upto`. One filing per reporting date: the last filed (an NPORT-P/A is a
    complete re-filing)."""
    from scripts.data.fetch_edgar_events import submissions
    s = submissions(client, cik)
    f = s[s["form"].isin(NPORT_FORMS)].copy()
    info = {"nport_filings": int(len(f))}
    if f.empty:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([])), info
    f["reportDate"] = pd.to_datetime(f["reportDate"])
    f = f[f["reportDate"] <= upto + pd.offsets.MonthEnd(2)]
    f = f.sort_values(["reportDate", "filingDate"]).groupby("reportDate").tail(1)
    parts = []
    for r in f.itertuples():
        acc = r.accessionNumber.replace("-", "")
        xml = client.get_text(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/primary_doc.xml")
        rep, vals = parse_nport_returns(xml)
        if rep != r.reportDate:
            raise ValueError(f"CIK {cik} {r.accessionNumber}: repPdDate {rep.date()} != index {r.reportDate.date()}")
        parts.append(nport_months(rep, vals))
    if not parts:
        info["nport_months"] = 0
        return pd.Series(dtype=float, index=pd.DatetimeIndex([])), info
    out = pd.concat(parts)
    if out.index.duplicated().any():
        raise ValueError(f"CIK {cik}: two N-PORT filings report the same month {out.index[out.index.duplicated()][:3].tolist()}")
    out = out.sort_index()
    out = out[out.index <= upto]
    info["nport_months"] = int(len(out))
    return out, info


def monthly_from_index(S: pd.DataFrame, months: pd.DatetimeIndex) -> pd.Series:
    """Calendar-month total return from the index: last valid date of month m
    over last valid date of month m-1. NaN if either month has no valid date."""
    v = S["idx"].dropna()
    last = v.groupby(v.index.to_period("M")).last()
    out = {}
    for m in months:
        p = m.to_period("M")
        out[m] = (last[p] / last[p - 1] - 1) if (p in last.index and (p - 1) in last.index) else np.nan
    return pd.Series(out)


def nav_stats(nav: pd.Series, T: pd.DataFrame, H: pd.DataFrame, win: tuple, h: int) -> dict:
    """Monthly NAV and price betas/residuals against one hedge, on identical months
    inside [estimation start, test end]."""
    s_est, _s0, e = win
    months = nav.index[(nav.index > s_est) & (nav.index <= e)]
    rec = {"nav_months_in_window": int(len(months))}
    if len(months) < MIN_NAV_MONTHS:
        rec["nav_status"] = f"{len(months)} N-PORT months in window (< {MIN_NAV_MONTHS})"
        return rec
    for m in months:
        assert_pre_holdout(m, "an N-PORT month")
    hm = monthly_from_index(H, months)
    pm = monthly_from_index(T, months)
    df = pd.DataFrame({"nav": nav.loc[months], "px": pm, "h": hm}).dropna()
    rec["nav_months_used"] = int(len(df))
    if len(df) < MIN_NAV_MONTHS:
        rec["nav_status"] = f"{len(df)} months with NAV, price and hedge (< {MIN_NAV_MONTHS})"
        return rec
    sc = np.sqrt(h / 21.0)
    for k in ("nav", "px"):
        b = float(np.polyfit(df["h"], df[k], 1)[0])
        rec[f"{k}_beta_m"] = b
        rec[f"{k}_corr_m"] = float(np.corrcoef(df["h"], df[k])[0, 1])
        rec[f"{k}_res_vol_hold_m"] = float(np.std(df[k] - b * df["h"], ddof=1) * sc)
        rec[f"{k}_unhedged_vol_hold_m"] = float(np.std(df[k], ddof=1) * sc)
    rec["nav_status"] = "ok"
    return rec


def nport_alignment_check(nav_by_target: dict, hedge_by_target: dict) -> dict:
    """Re-test the month order on every run. Under the documented order (month
    1 = earliest) each NAV month lines up with its hedge's same calendar month.
    Under the reversed order, months 1 and 3 of each quarter would really be
    two months away. So, pooled over every N-PORT month fetched, the NAV return
    must correlate with the same-month hedge return more than with the hedge
    two months away; otherwise this raises."""
    same, away = [], []
    for p, nav in nav_by_target.items():
        if nav.empty:
            continue
        H = hedge_by_target[p]
        months = nav.index
        shifted = pd.DatetimeIndex(sorted({(m.to_period("M") + k).to_timestamp("M") for m in months for k in (-2, 2)}))
        hm = monthly_from_index(H, months.union(shifted))
        for m, r in nav.items():
            v = hm.get(m, np.nan)
            if np.isfinite(v):
                same.append((r, v))
            for k in (-2, 2):
                w = hm.get((m.to_period("M") + k).to_timestamp("M"), np.nan)
                if np.isfinite(w):
                    away.append((r, w))
    if len(same) < 3 or len(away) < 3:
        return {"pooled_months": len(same)}
    same, away = np.array(same), np.array(away)
    fwd = float(np.corrcoef(same[:, 0], same[:, 1])[0, 1])
    rev = float(np.corrcoef(away[:, 0], away[:, 1])[0, 1])
    if not fwd > rev:
        raise ValueError(f"N-PORT month order: same-month corr {fwd:.3f} is not above the "
                         f"two-months-away corr {rev:.3f}; re-read the N-PORT readme")
    return {"pooled_months": int(len(same)), "corr_same_month": round(fwd, 3),
            "corr_two_months_away": round(rev, 3)}


# ----------------------------------------------------- Alpaca today, IBKR

def alpaca_flags(symbols, today: str, offline: bool) -> pd.DataFrame:
    """GET /v2/assets/{symbol}, cached as one JSON per day (read-only)."""
    p = CACHE / f"alpaca_assets_{today}.json"
    have = json.loads(p.read_text()) if p.exists() else {}
    want = sorted(set(symbols) - set(have))
    if want:
        if offline:
            raise FileNotFoundError(f"offline and {want} not in {p.name}")
        from quantt.broker.alpaca import AlpacaClient, AssetNotFound
        client = AlpacaClient.from_environment("cef")
        for s in want:
            t = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                a = client.asset(s)
                have[s] = {"read_utc": t, "found": True, **{k: a.get(k) for k in (
                    "name", "status", "exchange", "tradable", "shortable", "easy_to_borrow", "borrow_status")}}
            except AssetNotFound:
                have[s] = {"read_utc": t, "found": False}
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(have, indent=1, sort_keys=True))
    return pd.DataFrame([{"symbol": s, **have[s]} for s in sorted(set(symbols))])


def alpaca_adv(symbols, today: str, offline: bool) -> pd.DataFrame:
    """Median and mean dollar volume (close x volume, SIP, raw) over the last
    ADV_SESSIONS complete sessions before `today`. Volume, not a return."""
    p = CACHE / f"alpaca_bars_{today}.parquet"
    bars = pd.read_parquet(p) if p.exists() else pd.DataFrame(columns=["date", "ticker", "close", "volume"])
    want = sorted(set(symbols) - set(bars["ticker"]))
    if want:
        if offline:
            raise FileNotFoundError(f"offline and {want} not in {p.name}")
        from scripts.rv.alpaca_daily import fetch_bars, make_client
        end = date.fromisoformat(today) - timedelta(days=1)
        new = fetch_bars(make_client(), want, end - timedelta(days=130), end)
        bars = new if bars.empty else pd.concat([bars, new], ignore_index=True)
        CACHE.mkdir(parents=True, exist_ok=True)
        bars.to_parquet(p, index=False)
    missing = sorted(set(symbols) - set(bars["ticker"]))
    if missing:
        raise LookupError(f"no Alpaca bars for {missing}")
    rows = []
    for tk, g in bars.groupby("ticker"):
        g = g.sort_values("date").tail(ADV_SESSIONS)
        if len(g) < ADV_SESSIONS:
            raise ValueError(f"{tk}: {len(g)} sessions of bars (< {ADV_SESSIONS})")
        dv = g["close"] * g["volume"]
        rows.append({"symbol": tk, "adv_median_usd": float(dv.median()), "adv_mean_usd": float(dv.mean()),
                     "adv_first": str(g["date"].min().date()), "adv_last": str(g["date"].max().date())})
    return pd.DataFrame(rows)


def earlier_flags(symbols) -> pd.DataFrame:
    """Every earlier Alpaca read of these symbols on file (tracked files only)."""
    rows = []
    for f in EARLIER_FLAGS:
        x = pd.read_csv(f)
        for c in ("symbol", "shortable", "easy_to_borrow", "alpaca_read_utc"):
            if c not in x:
                raise KeyError(f"{f.name} lacks {c}")
        x = x[x["symbol"].isin(symbols)]
        for r in x.itertuples():
            rows.append({"symbol": r.symbol, "read_utc": r.alpaca_read_utc, "shortable": bool(r.shortable),
                         "easy_to_borrow": bool(r.easy_to_borrow), "source": str(f.relative_to(REPO))})
    return pd.DataFrame(rows, columns=["symbol", "read_utc", "shortable", "easy_to_borrow", "source"])


def ibkr_context(symbols) -> pd.DataFrame:
    """IBKR shortstock file (cached by G1a, 2026-10-13): availability and fee, context only."""
    if not IBKR_FILE.exists():
        raise FileNotFoundError(f"{IBKR_FILE} missing: run scripts/events/g1a_shortability.py first")
    from scripts.events.g1a_shortability import parse_ibkr_shortstock
    df, stamp = parse_ibkr_shortstock(IBKR_FILE.read_text(encoding="latin-1"))
    df = df[df["symbol"].isin(symbols)].drop_duplicates("symbol")
    df["ibkr_stamp"] = stamp
    return df[["symbol", "fee_rate_pct", "available", "available_gt", "ibkr_stamp"]]


# ------------------------------------------------------------ aggregation

def summarise(det: pd.DataFrame, eff: dict, holds: dict) -> dict:
    """Per segment x hedge: medians and cross-sectional dispersions."""
    out = {}
    ok = det[det["status"] == "ok"]
    for (seg, hedge), g in ok.groupby(["cls", "hedge"]):
        sd_eff = eff[seg]["sd"]
        r = {"targets": int(len(g)), "segment_targets": int(eff[seg]["n"]),
             "beta_median": float(g["beta"].median()), "beta_ols_median": float(g["beta_ols"].median()),
             "beta_test_median": float(g["beta_test"].median()),
             "corr_d_median": float(g["corr_d"].median()), "corr_5_median": float(g["corr_5"].median()),
             "res_vol_hold_median": float(g["res_vol_hold"].median()),
             "unhedged_vol_hold_median": float(g["unhedged_vol_hold"].median()),
             "res_vol_hold_daily_x_sqrt_h_median": float(g["res_vol_hold_daily_x_sqrt_h"].median()),
             "resid_oos_sd": float(g["resid_oos"].std(ddof=1)) if len(g) > 1 else float("nan"),
             "resid_oos_robust_sd": float(1.4826 * (g["resid_oos"] - g["resid_oos"].median()).abs().median()),
             "unhedged_oos_sd": float(g["R_T_test"].std(ddof=1)) if len(g) > 1 else float("nan"),
             "variance_removed_ts": float(1 - (g["res_vol_hold"] ** 2).median() / (g["unhedged_vol_hold"] ** 2).median()),
             "adv_hedge_window_usd_median": float(g["adv_hedge_window_usd"].median()),
             "adv_hedge_window_usd_min": float(g["adv_hedge_window_usd"].min()),
             "h": holds[seg]}
        r["k_ts"] = r["res_vol_hold_median"] / sd_eff
        r["k_xs"] = r["resid_oos_sd"] / sd_eff
        # If the hedge's residual were independent of the effect, the trade's
        # clustered t would shrink by sqrt(1 + k^2): arithmetic, not a return.
        r["implied_clustered_t"] = eff[seg]["clustered_t"] / np.sqrt(1 + r["k_ts"] ** 2)
        era = pd.cut(pd.to_datetime(g["ann"]).dt.year, bins=ERA_BINS, labels=ERA_LABELS, right=True)
        r["by_era"] = {str(e): {"targets": int(len(x)), "res_vol_hold_median": float(x["res_vol_hold"].median()),
                                "unhedged_vol_hold_median": float(x["unhedged_vol_hold"].median())}
                       for e, x in g.groupby(era, observed=True)}
        out.setdefault(seg, {})[hedge] = r
    return out


def nav_summary(det: pd.DataFrame) -> dict:
    out = {}
    if "nav_status" not in det:
        return out
    ok = det[det["nav_status"] == "ok"]
    for (seg, hedge), g in ok.groupby(["cls", "hedge"]):
        out.setdefault(seg, {})[hedge] = {
            "targets": int(len(g)), "months_median": float(g["nav_months_used"].median()),
            **{f"{k}_median": float(g[k].median()) for k in (
                "nav_beta_m", "nav_corr_m", "nav_res_vol_hold_m", "nav_unhedged_vol_hold_m",
                "px_beta_m", "px_corr_m", "px_res_vol_hold_m", "px_unhedged_vol_hold_m")},
            "nav_share_of_px_residual_median": float((g["nav_res_vol_hold_m"] / g["px_res_vol_hold_m"]).median())}
    return out


def buildable(flags: pd.DataFrame, earlier: pd.DataFrame, symbol: str) -> tuple[bool, str]:
    """Shortable and easy-to-borrow today AND on every earlier read on file."""
    f = flags.set_index("symbol")
    if symbol not in f.index or not bool(f.at[symbol, "found"]):
        return False, "not found at Alpaca today"
    now = bool(f.at[symbol, "shortable"]) and bool(f.at[symbol, "easy_to_borrow"])
    if not now:
        return False, f"today: shortable={f.at[symbol, 'shortable']}, easy_to_borrow={f.at[symbol, 'easy_to_borrow']}"
    e = earlier[earlier["symbol"] == symbol]
    bad = e[~(e["shortable"] & e["easy_to_borrow"])]
    if len(bad):
        return False, f"not shortable/easy on {bad['read_utc'].tolist()}"
    return True, f"shortable and easy today; earlier reads on file: {len(e)}"


def gate_verdict(seg_stats: dict, flags: pd.DataFrame, earlier: pd.DataFrame, adv: pd.DataFrame,
                 x: float = GATE_X, cap: float = CAPACITY_MAX_PARTICIPATION) -> dict:
    """The proposed rule (module docstring), per hedge and per segment."""
    advd = adv.set_index("symbol")["adv_median_usd"].to_dict()
    per = {}
    for hedge, r in seg_stats.items():
        ok_b, why_b = buildable(flags, earlier, hedge) if hedge in advd else (False, "acquirer / not an ETF")
        part = (abs(r["beta_median"]) * max(LONG_NOTIONALS) / advd[hedge]) if hedge in advd else float("nan")
        ok_c = bool(np.isfinite(part) and part <= cap)
        ok_r = bool(r["k_ts"] <= x and r["k_xs"] <= x)
        per[hedge] = {"buildable": ok_b, "buildable_why": why_b, "participation_at_1m": part,
                      "participation_at_100k": part * min(LONG_NOTIONALS) / max(LONG_NOTIONALS),
                      "capacity_ok": ok_c, "k_ts": r["k_ts"], "k_xs": r["k_xs"], "residual_ok": ok_r,
                      "implied_clustered_t": r["implied_clustered_t"],
                      "pass": bool(ok_b and ok_c and ok_r)}
    return {"x": x, "per_hedge": per, "segment_pass": any(v["pass"] for v in per.values())}


def best_hedge(seg_stats: dict, candidates) -> str | None:
    """Lowest median time-series residual among candidates measured on at least
    half the segment's targets (module docstring states the selection)."""
    elig = {h: r for h, r in seg_stats.items() if h in candidates and r["targets"] >= 0.5 * r["segment_targets"]}
    if not elig:
        return None
    return min(elig, key=lambda h: elig[h]["res_vol_hold_median"])


def paired(det: pd.DataFrame, a: str, b: str, seg: str, mask=None) -> dict:
    """Hedge a vs hedge b on the targets both measure: medians and the median ratio."""
    ok = det[(det["status"] == "ok") & (det["cls"] == seg)]
    if mask is not None:
        ok = ok[ok["permno"].isin(mask)]
    pa = ok[ok["hedge"] == a].set_index("permno")
    pb = ok[ok["hedge"] == b].set_index("permno")
    common = pa.index.intersection(pb.index)
    if len(common) == 0:
        return {"targets": 0}
    ra, rb = pa.loc[common], pb.loc[common]
    return {"targets": int(len(common)),
            f"res_vol_hold_median_{a}": float(ra["res_vol_hold"].median()),
            f"res_vol_hold_median_{b}": float(rb["res_vol_hold"].median()),
            f"ratio_median_{a}_over_{b}": float((ra["res_vol_hold"] / rb["res_vol_hold"]).median()),
            f"share_{a}_lower": float((ra["res_vol_hold"] < rb["res_vol_hold"]).mean()),
            f"resid_oos_sd_{a}": float(ra["resid_oos"].std(ddof=1)) if len(common) > 1 else float("nan"),
            f"resid_oos_sd_{b}": float(rb["resid_oos"].std(ddof=1)) if len(common) > 1 else float("nan"),
            f"corr_5_median_{a}": float(ra["corr_5"].median()), f"corr_5_median_{b}": float(rb["corr_5"].median())}


# ------------------------------------------------------------------- run

def run(today: str, offline: bool, nport: bool = True) -> dict:
    s = load_sample()
    nm = ce.names()
    guard = assert_no_universe(s, nm)
    holds = segment_holds(s)
    eff = effect_by_segment(s)
    tnames = {int(p): ce.name_at(nm, int(p), a) for p, a in zip(s["permno"], s["ann"])}
    unnamed = [tk for tk, p in zip(s["ticker"], s["permno"]) if tnames[int(p)] is None]
    if unnamed:   # the state match reads the name; a missing one is never treated as "no state"
        raise LookupError(f"no CRSP name record at announcement for targets {unnamed}")
    s["t_comnam"] = [tnames[int(p)]["comnam"] for p in s["permno"]]
    s["state_etf"] = [state_etf(n) if c == "muni" else None for n, c in zip(s["t_comnam"], s["cls"])]

    all_etfs = sorted({e for v in CANDIDATES.values() for e in v} | set(STATE_ETF)
                      | {e for v in POST_HOC.values() for e in v})
    lo = s["ann"].min() - pd.Timedelta(days=1000)
    hi = s["ann"].max()
    etf_perm = etf_permnos(nm, all_etfs, lo, hi)
    dsf = ce.daily(set(etf_perm.values()) | set(s["permno"]) | set(s["nwperm"]))
    if dsf["date"].max() >= TIME_HOLDOUT:
        raise WindowError("CRSP extract reaches the time holdout")
    S = series(dsf)

    rows = []
    skipped = {}
    for d in s.itertuples():
        T = S.get(d.permno)
        if T is None:
            skipped["target has no CRSP rows"] = skipped.get("target has no CRSP rows", 0) + 1
            continue
        h = holds[d.cls]
        win = windows(T.index[T["idx"].notna()], d.ann, h)
        if win is None:
            skipped["target history too short for the windows"] = skipped.get("target history too short for the windows", 0) + 1
            continue
        if win[2] >= d.ann:
            raise WindowError(f"{d.ticker}: test window reaches the announcement")
        hedges = (list(CANDIDATES[d.cls]) + list(POST_HOC.get(d.cls, ()))
                  + ([d.state_etf] if d.state_etf else []) + ["ACQ"])
        for hg in hedges:
            H = S.get(d.nwperm) if hg == "ACQ" else S[etf_perm[hg]]
            base = {"permno": d.permno, "ticker": d.ticker, "cls": d.cls, "ann": d.ann, "hedge": hg,
                    "state_etf": d.state_etf, "date_basis": d.date_basis}
            if H is None:
                rows.append({**base, "status": "hedge has no CRSP rows"})
                continue
            first_valid = H["idx"].first_valid_index()
            if first_valid is None or first_valid > win[0]:
                rows.append({**base, "status": "hedge not trading over the windows"})
                continue
            rows.append({**base, **hedge_stats(T, H, win, h)})
    det = pd.DataFrame(rows)

    # NAV (N-PORT), for targets whose windows reach 2019+.
    nav_info = {}
    if nport:
        from scripts.data.edgar_client import EdgarClient
        client = EdgarClient(offline=offline)
        dates = pd.read_csv(EDGAR_DATES).set_index("permno")
        win_ok = det[det["status"] == "ok"].drop_duplicates("permno").set_index("permno")
        navs = {}
        for p, r in win_ok.iterrows():
            if pd.Timestamp(r["test_end"]) < pd.Timestamp("2019-03-31"):
                continue      # no public N-PORT can reach this window (first public period: 2019)
            cik = dates.at[p, "t_cik"]
            if pd.isna(cik):
                raise LookupError(f"permno {p}: no target CIK in {EDGAR_DATES.name}")
            nav, info = nport_monthly(client, int(cik), pd.Timestamp(r["test_end"]))
            navs[int(p)] = nav
            nav_info[str(r["ticker"])] = info
        nav_rows = []
        for i, r in det[det["status"] == "ok"].iterrows():
            nav = navs.get(int(r["permno"]))
            if nav is None or nav.empty:
                continue
            H = S.get(int(s.set_index("permno").at[r["permno"], "nwperm"])) if r["hedge"] == "ACQ" else S[etf_perm[r["hedge"]]]
            st = nav_stats(nav, S[int(r["permno"])], H, (r["est_start"], r["test_start"], r["test_end"]), int(r["h"]))
            nav_rows.append({"_i": i, **st})
        if nav_rows:
            nr = pd.DataFrame(nav_rows).set_index("_i")
            det = det.join(nr)
        ref = {s_.permno: S[etf_perm[CANDIDATES[s_.cls][0]]] for s_ in s.itertuples() if s_.permno in navs}
        align = nport_alignment_check(navs, ref)
    else:
        align = {"skipped": True}

    stats = summarise(det, eff, holds)
    flags = alpaca_flags(all_etfs, today, offline)
    adv = alpaca_adv(all_etfs, today, offline)
    early = earlier_flags(all_etfs)
    ibkr = ibkr_context(all_etfs)
    gates, best, pairs = {}, {}, {}
    g1a = pd.read_csv(G1A_DEALS)
    short_now = set(g1a.loc[g1a["H3_alpaca_shortable_today"] == True, "permno"].astype(int))  # noqa: E712
    for seg, st in stats.items():
        # The segment gate is decided on the segment's own candidates. A state ETF
        # hedges its state's targets only, so it is reported beside (`state_matched`).
        gate_set = set(CANDIDATES[seg]) | set(POST_HOC.get(seg, ()))
        gates[seg] = gate_verdict({k: v for k, v in st.items() if k in gate_set}, flags, early, adv)
        gates[seg]["post_hoc_hedges"] = list(POST_HOC.get(seg, ()))
        cands = list(CANDIDATES[seg])
        b = best_hedge(st, cands)
        bb = best_hedge(st, [c for c in cands if gates[seg]["per_hedge"].get(c, {}).get("buildable")])
        best[seg] = {"best_any": b, "best_buildable": bb}
        if b:
            pairs[seg] = {"best_vs_acquirer_all": paired(det, b, "ACQ", seg),
                          "best_vs_acquirer_alpaca_shortable_today": paired(det, b, "ACQ", seg, mask=short_now),
                          "best_vs_MUB": paired(det, b, "MUB", seg) if seg == "muni" and b != "MUB" else None}
            if bb and bb != b:
                pairs[seg]["best_buildable_vs_acquirer_all"] = paired(det, bb, "ACQ", seg)
            # Every candidate against the segment's first-listed one, on the targets
            # both measure (VTEB, BKLN and BIZD start later, so their own medians
            # are on different, later windows).
            pairs[seg]["each_vs_first_listed"] = {c: paired(det, c, cands[0], seg)
                                                  for c in cands[1:] + list(POST_HOC.get(seg, ()))}
    state = {}
    m = det[(det["cls"] == "muni") & (det["status"] == "ok")]
    for etf in STATE_ETF:
        sub = set(m.loc[m["state_etf"] == etf, "permno"])
        if sub:
            state[etf] = {"vs_MUB": paired(det, etf, "MUB", "muni", mask=sub),
                          "vs_best": paired(det, etf, best["muni"]["best_any"], "muni", mask=sub)
                          if best.get("muni", {}).get("best_any") not in (None, "MUB") else None}

    target_adv = {c: float(g["adv63_T_pre"].median()) for c, g in s.groupby("cls")}
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": today,
        "zero_trials": True,
        "holdout_guard": guard,
        "params": {"EST_SESSIONS": EST_SESSIONS, "GUARD_SESSIONS": GUARD_SESSIONS, "BLOCK": BLOCK,
                   "MIN_EST_OBS": MIN_EST_OBS, "GATE_X": GATE_X,
                   "CAPACITY_MAX_PARTICIPATION": CAPACITY_MAX_PARTICIPATION, "KILL_T": KILL_T},
        "crsp_last_date": str(dsf["date"].max().date()),
        "windows_latest_test_end": str(pd.to_datetime(det.loc[det["status"] == "ok", "test_end"]).max().date()),
        "holds_sessions": holds,
        "effect_rem_measured": eff,
        "t_ceiling_x": {c: t_ceiling_x(v["clustered_t"]) for c, v in eff.items()},
        "targets_skipped": skipped,
        "rows_status": det["status"].value_counts().to_dict(),
        "rows_status_by_hedge": {h: g["status"].value_counts().to_dict() for h, g in det.groupby("hedge")},
        "state_matched_targets": s.loc[s["state_etf"].notna()].groupby("state_etf")["ticker"].count().to_dict(),
        "stats": stats,
        "nav": nav_summary(det),
        "nav_alignment": align,
        "nav_targets_fetched": len(nav_info),
        "gates": gates,
        "best": best,
        "paired": pairs,
        "state_matched": state,
        "alpaca_flags_today": flags.to_dict(orient="records"),
        "alpaca_adv_today": adv.to_dict(orient="records"),
        "alpaca_flags_earlier": early.to_dict(orient="records"),
        "ibkr_context": ibkr.to_dict(orient="records"),
        "target_adv63_pre_median_usd": target_adv,
        "acquirer_shortable_today_targets": int(len(short_now)),
    }
    det.to_csv(OUT / "e1_etf_hedge_detail.csv", index=False, float_format="%.8g")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true", help="caches only (CRSP, EDGAR, Alpaca)")
    ap.add_argument("--today", help="the Alpaca read date to use (YYYY-MM-DD); default: today")
    ap.add_argument("--no-nport", action="store_true", help="skip the N-PORT NAV view")
    a = ap.parse_args(argv)
    today = a.today or date.today().isoformat()
    res = run(today, a.offline, nport=not a.no_nport)
    p = OUT / f"e1_etf_hedge_summary_{today}.json"
    p.write_text(json.dumps(res, indent=1, default=str, sort_keys=False))
    print(json.dumps({k: res[k] for k in ("holds_sessions", "effect_rem_measured", "t_ceiling_x", "best",
                                           "gates", "rows_status")}, indent=1, default=str))
    print(f"wrote {p.relative_to(REPO)} and results/events/e1_etf_hedge_detail.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
