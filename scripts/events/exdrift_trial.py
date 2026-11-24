"""EVENTS trial 3: the post-ex-date drift in credit CEFs, part (b). Stage 0 (the data gates) and the block.

    python3 scripts/events/exdrift_trial.py stage0             # offline once the caches exist; writes results/events/exdrift/
    python3 scripts/events/exdrift_trial.py notices            # fetch + verify the sponsor notices DG-X2 checks Alpaca against (public)
    python3 scripts/events/exdrift_trial.py rulings-template   # the blank rulings form for the current flags
    python3 scripts/events/exdrift_trial.py fit-k              # REFUSES until every Stage-0 flag is ruled (stub)
    python3 scripts/events/exdrift_trial.py open               # REFUSES until Stage 0 is CLEAR (stub; opened once)

WHAT THIS IS
------------
The pre-registration is `results/events/PREREG_EXDATE_DRIFT_2026-10-26.md`, approved by the team
lead on 2026-10-27 with every recommended answer of its §14: part (b) is EVENTS trial 3, judged
at N = 7; part (a) is withdrawn on power before any data step. Part (b) shorts each eligible fund
at the close of its ex-date e and covers at the close of e+3, against H-E, the equal-weight
basket of the other universe funds with no ex-date declared at e-1 in [e+1, e+8] (§4). The test
set is the 17 credit CEFs (the spec's 13 plus NAD, NEA, NVG, NZF), 2023-01-01 to the last panel
date (§5). This file is the trial script §4.5 names. It holds Stage 0 (§8) now; the later stages
are stubs that refuse until Stage 0 clears, and are written, reviewed and run after it.

WHAT STAGE 0 MAY READ, AND WHAT IT MAY NOT
------------------------------------------
* 2023-01-01 ON: DATES, COUNTS, PRESENCE AND FLAGS ONLY. No 2023+ return, P&L, price change or
  NAV change is computed, printed or written. The test set is opened exactly once, later, by
  `open`, and not by Stage 0. Concretely:
  - ex-dates and amounts (not returns; the brief allows them) from the refreshed distribution
    panel, and the second source's ex, record and declaration dates and amounts;
  - the session calendar (`date, ticker` of the price panel);
  - PRESENCE of a close, a NAV and a volume, turned into booleans as soon as they are read
    (`_present`), and two equality tests: volume == 0 and NAV(D) == NAV(D-1) (DG-X4, DG-X5);
  - the spike-and-revert bar guard (`data_guards.split_like_spikes`), which forms close and
    NAV ratios INSIDE data_guards to classify a bar. Only its flag keys (ticker, first bar,
    run end, revert date, split factor) leave `bar_guard_flags`; its ratio columns are dropped
    unread. The split-basis guard takes returns as input, so it is NOT run at Stage 0. Its one
    test-window split is classified from the factor alone (`split_basis_class`: undecidable). The
    opening does not apply split factors at all: r6's ±5-session mask (R1) removes those returns,
    so no factor is ever multiplied in.
* FIT, 2005-01-01 .. 2022-12-30: prices, NAVs and distributions, read through parquet filters
  at FIT_END so no later row is loaded, and asserted. Stage 0 computes on them only the identity
  gate (DG-X7): r6's statistic and H-E's per-event dispersion, both already published. No new
  fit statistic is formed: the brief for this run (2026-10-27) is "no P&L, no fit statistic
  beyond the identity gate". k and the cap-binding share (§4.4, DG-X7) form fit P&L, so they are
  left to `fit-k`, which runs only after every flag is ruled.
* THE 27 SEALED NAMES (`data/cef/cef_universe.csv` minus the 17) are never loaded: every panel
  read passes a parquet filter `ticker in NAMES`, and `_only_names` asserts it on every frame.

DG-X2 AND ALPACA'S DECLARATION DATE (2026-10-28). The announcements endpoint's `declaration_date`
is tested before it is used: every verified sponsor notice (`NOTICES`, quotes re-found offline)
is compared with it, and the weekdays from it to the record date are printed. PIMCO's own release
of 2025-10-01 contradicts it (Alpaca: 2025-10-12), and it sits 1-3 weekdays before the record date
on almost every record, so it is derived, not observed. DG-X2 then FAILS with one class flag
(`X2_source_invalid`), and the per-event "declared late" test is printed, never flagged: a flag
raised on an invalid field would ask for rulings on dates nobody declared.

THE BLOCK. `require_stage0_clear` calls `data_guards.require_stage0_rulings` on the committed
flag table and the rulings file, and then reads the committed Stage-0 record. `fit-k` needs the
first; `open` needs both and a committed k. Each refuses, naming what is missing.

IMPLEMENTATION READINGS the pre-registration does not settle. Each is a flag (`R1`..`R9`) in the
flag table, so the team lead rules on it like any other; the text is `READINGS` below.

Environment: `compute.use_numexpr` is off at import (DG-X8, `scripts/events/numexpr_fault.py`).
Tests: `scripts/events/tests/test_exdrift_trial.py` (synthetic data only).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("compute.use_numexpr", False)          # DG-X8 (scripts/events/numexpr_fault.py)

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import scripts.cef.spec as spec                       # noqa: E402  (the only reader of the frozen spec)
from scripts.cef import data_guards as dg             # noqa: E402

# --------------------------------------------------------------------------- paths
STAMP = "2026-10-27"                                  # the approval date; this run's files carry it
PREREG = REPO / "results" / "events" / "PREREG_EXDATE_DRIFT_2026-10-26.md"
D = REPO / "data"
PRICES, NAVS = D / "cef" / "cef_prices.parquet", D / "cef" / "cef_nav.parquet"
DIST_DATA = D / "cef" / "cef_distributions.parquet"   # what the prereg counted on (yfinance, 2026-09-11 fetch)
ETF_DAILY = D / "etf_daily.parquet"
OUT_DIR = REPO / "results" / "events" / "exdrift"
CACHE = OUT_DIR / "_cache_exdrift"                    # gitignored (results/**/_cache_*)
REFRESH_DIR = CACHE / f"dist_refresh_{STAMP}"         # DG-X1: fetch_cef_distributions.py --out (never data/)
DIST_REFRESH = REFRESH_DIR / "cef_distributions.parquet"
SPLITS_REFRESH = REFRESH_DIR / "cef_splits.parquet"
ALPACA_DIVS = CACHE / "alpaca_cash_dividends.parquet"         # fetch_exdrift_corp_actions.py
ALPACA_ANN = CACHE / "alpaca_dividend_announcements.parquet"
ALPACA_BARS = CACHE / "alpaca_flagged_bars.parquet"
ALPACA_ADJ_BARS = CACHE / "alpaca_adjacent_bars.parquet"     # the X4 basis check's bars on e-1 and e+1
FF_DAILY = REPO / "results" / "cef" / "w4" / "_cache_w4" / "ff5_umd_daily.parquet"   # fetch_ff_factors.py
ETF_YF = {s: CACHE / f"etf_yf_{s}.parquet" for s in ("MUB", "IEF", "HYG")}        # fetch_exdrift_mub.py
FLAGS = OUT_DIR / f"exdrift_stage0_flags_{STAMP}.csv"
RULINGS = OUT_DIR / f"exdrift_stage0_rulings_{STAMP}.csv"
BAR_RULINGS = OUT_DIR / f"exdrift_bar_rulings_{STAMP}.json"
STAGE0_JSON = OUT_DIR / f"exdrift_stage0_{STAMP}.json"
STAGE0_TXT = OUT_DIR / f"exdrift_stage0_output_{STAMP}.txt"
FIT_TABLE = OUT_DIR / f"exdrift_fit_descriptive_{STAMP}.csv"
K_JSON = OUT_DIR / f"exdrift_k_{STAMP}.json"          # written by fit-k (not yet)
SPONSOR_TABLE = OUT_DIR / "exdrift_sponsor_declarations_2026-10-28.csv"
CRSP_DECL = CACHE / "crsp_decl"                       # fetch_exdrift_crsp_decl.py (gitignored: CRSP rows are licensed)
DECL_FINAL = CACHE / "exdrift_declarations_final.csv"  # stage0 writes it: release + CRSP dates (gitignored: CRSP-derived)
OPENED = OUT_DIR / "exdrift_test_set_OPENED.json"     # written by `open` before it computes anything; opened once
OPEN_RULINGS = OUT_DIR / "exdrift_open_rulings.csv"   # the team lead's rulings on O1-O4 and the GO row
OPEN_READINGS = [
    ("O1", "AS RULED (team lead, 2026-10-28, with one change): the P&L window runs from the first session on or after "
           "2023-01-01 to 2026-10-09, where IEF and HYG in data/etf_daily.parquet end (not the cover row 2026-10-15). "
           "Only events whose e+3 is on or before it are eligible. Every factor (French six and rf, IEF, HYG, MUB) "
           "must cover it and the session before it (the Dimson lag)."),
    ("O2", "R-D4's betas 'at the vol target' are the summed betas times VOL_TARGET / sigma(tradable sleeve over the "
           "window): the NAV-tender precedent, whose sizing rule (sigma on active sessions) §4.4 copies; the tradable "
           "sleeve's full-window vol is below the target. Alternative: unscaled betas (E1's reading, whose k used the "
           "full-series sigma). Both are printed."),
    ("O3", "Stage 3 compares the NAV-leg mean with the price-leg mean ON THE SAME EVENTS (those with a NAV leg after the "
           "X5 exclusions), as §4.6's 'the same events and baskets'. The comparison against the full set's price mean is "
           "printed beside."),
    ("O4", "The X4 fill's basis check (ruling #4): Alpaca's raw SIP close on e-1 and e+1 equals yfinance's within "
           "$0.01, as C4's adjacent-bar check; the bars come from the team lead's run (`run_exdrift_r2.sh`). A cell that "
           "fails raises (HALT)."),
]
TRIAL_CODE = [REPO / "scripts" / "events" / n for n in ("exdrift_trial.py", "exdrift_open.py", "fetch_exdrift_sponsor_releases.py",
                                                        "fetch_exdrift_crsp_decl.py", "fetch_exdrift_corp_actions.py")]
PINNED = {"prices": PRICES, "navs": NAVS, "dist_refresh": DIST_REFRESH, "splits_refresh": SPLITS_REFRESH,
          "declarations_final": DECL_FINAL, "alpaca_bars": ALPACA_BARS, "alpaca_adjacent_bars": ALPACA_ADJ_BARS,
          "alpaca_dividends": ALPACA_DIVS, "sponsor_table": SPONSOR_TABLE, "mub": ETF_YF["MUB"]}
REHEARSAL_JSON = OUT_DIR / "exdrift_rehearsal_fit_2021_22.json"
REHEARSAL_TXT = OUT_DIR / "exdrift_rehearsal_fit_2021_22.txt"
REHEARSAL_A1_JSON = OUT_DIR / "exdrift_rehearsal_fit_2021_22_amendment1_WITHDRAWN.json"   # the record of amendment 1
REHEARSAL_A1_TXT = OUT_DIR / "exdrift_rehearsal_fit_2021_22_amendment1_WITHDRAWN.txt"
POWER_JSON = OUT_DIR / "exdrift_power_2026-10-28.json"
HEDGE_JSON = OUT_DIR / "exdrift_amendment1_hedge_betas.json"   # amendment 1: frozen fit betas to MUB and IEF
O1_END = pd.Timestamp("2026-10-09")    # the team lead's O1 ruling (2026-10-28): the P&L window ends where IEF/HYG end
HEDGE_FIT_LO = pd.Timestamp("2007-09-11")   # MUB's first session with a previous close (yfinance cache)
B3_JSON = REPO / "results" / "events" / "prereg_exdrift" / "prereg_inputs_b3.json"   # fit dispersion (identity-gated)   # fetch_exdrift_sponsor_releases.py build
NOTICES = OUT_DIR / "exdrift_sponsor_notices_2026-10-28.csv"   # verified sponsor notices (DG-X2 check)
NOTICE_CACHE = CACHE / "sponsor_notices"              # `exdrift_trial.py notices` fills it (public GETs)
WRAPPER = "run_exdrift_ca.sh"                         # worktree root, excluded from git (info/exclude)

# --------------------------------------------------------------------------- the declaration (prereg)
FIT_START, FIT_END = pd.Timestamp("2005-01-01"), pd.Timestamp("2022-12-30")
TEST_START = pd.Timestamp("2023-01-01")               # = band_frontier.HOLDOUT_START (a test pins it)
T1_START = pd.Timestamp("2024-05-28")                 # T+1 settlement (prereg §4.2; SEC 2023-29 [V])
MUNIS = ("NAD", "NEA", "NVG", "NZF")
NAMES = tuple(spec.UNIVERSE) + MUNIS
CORE = tuple(spec.UNIVERSE)
N_BAR = 7                                             # decision 4
HOLD = 3                                              # return rows e+1..e+3 (§4.2)
HE_LO, HE_HI = 1, 8                                   # H-E: no own ex-date in [e+1, e+8] (§4.3)
BASKET_MIN = 3
SPLIT_MASK = 5                                        # r6: returns within +-5 sessions of a split are masked
NEXT_EX_WITHIN = 3                                    # rule 2: no other own ex-date in (e, e+3]
DIV_TOL = 0.001                                       # $/share; = c4_families.DIV_TOL (Yahoo rounds to 3dp; a test pins it)
# The identity gate (DG-X7): published figures, at the precision they were published.
R6_PUBLISHED = {"events": 3226, "car_bp": -20.454, "t_month": -6.765}
R6_TOL = 0.001                                        # the draft's own gate (prereg_inputs.py)
HE_SD_PUBLISHED_BP, HE_SD_TOL_BP = 150.3, 0.05        # printed to 0.1bp (prereg_inputs_b3_output.txt)
HE_SDM_PUBLISHED_BP = 41.4                            # printed beside, same helper
# §5.1's counts, reprinted beside the re-measured ones (H14). They decide nothing.
FIT_ERAS = (("2005-09", 2005, 2009), ("2010-14", 2010, 2014), ("2015-19", 2015, 2019), ("2020-22", 2020, 2022))
PREREG_TEST_COUNTS = {"events": 752, "events_13": 575, "dates": 169, "months": 45, "basket_ge3": 714,
                      "basket_ge3_13": 537}

GATES = ("DG-X1", "DG-X2", "DG-X3", "DG-X4", "DG-X5", "DG-X6", "DG-X7", "DG-X8")
FLAG_COLUMNS = ["check", "ticker", "date", "gate", "events", "note", "recommended"]

READINGS = [
    ("R1", "DG-X4", "Rule 3 (no event within +-5 sessions of the fund's own split, r6's mask) is read from the splits "
                    "panel (`cef_splits.parquet`), not from the distribution panel's `stock_split` column that r6's "
                    "code read: that column carries a split only when it falls on a distribution row, and is empty for "
                    "the 17 over the whole panel. In the fit both are empty (so r6 is unchanged); in the test the splits "
                    "panel holds BIT 2025-08-19 (factor 1.029). r6's mask is applied as r6 applies it: the fund's "
                    "returns on rows split-5..split+5 are masked, so an event or a basket leg with a masked hold row "
                    "drops out.",
     "Keep."),
    ("R2", "DG-X1", "The second source for DG-X1 is Alpaca's /v1/corporate-actions for the whole test set. The prereg "
                    "names CRSP (ret != retx) to 2024-12-31: CRSP needs the team lead's credential, and ret - retx is a "
                    "return, which Stage 0 may not read. Public sponsor notices give nothing for these names today: "
                    "fetch_sponsor_notices.py verifies C4's citation table only (none of the 17), and CEFConnect "
                    "answered a scripted request with a 'request blocked' page on 2026-10-27.",
     "Keep Alpaca as the second source; add CRSP's distribution table (dclrdt, exdt, rcrddt, divamt; no return) to "
     "2024-12-31 as a third where the two disagree, if the team lead wants it."),
    ("R3", "DG-X1", "An ex-date and amount AGREE when both sources list the ex-date and the amounts differ by at most "
                    "$0.001/share (c4_families.DIV_TOL: Yahoo rounds to 3dp). Alpaca's amount per ex-date is the sum of "
                    "its cash_dividend and capital_gains_distribution records on that ex-date, as yfinance sums them.",
     "Keep."),
    ("R4", "DG-X2", "'Declared on or before e-1' compares the announcement's declaration_date (a date, no time) with "
                    "the session before e; a declaration dated e-1 itself passes. The count declared on e-1 exactly is "
                    "printed (it may have come after that close), and 'declarations <= e-2' is the report-only stratum.",
     "Keep."),
    ("R5", "DG-X4", "The missing-bar and zero-volume checks flag the EVENT fund only: a bar on each of e..e+3, and "
                    "volume > 0 on the fill days e and e+3. A basket fund without a bar on e..e+3 leaves that event's "
                    "basket by the declared H-E rule (finite returns on e+1..e+3); those legs are counted, not flagged.",
     "Keep."),
    ("R6", "DG-X5", "NAV repeats (NAV(D) = NAV(D-1)) are flagged on the event fund's rows e+1..e+3. Basket funds' "
                    "repeats enter the NAV leg's basket mean and are counted, not flagged. The fit rate on the same "
                    "rows, by era, is printed beside the test rate by year, so a ruling can tell cent-rounding from "
                    "staleness. docs/DATA.md (correction of 2026-10-12) records that Yahoo serves a NAV row dated D "
                    "carrying D-1's NAV. A stale NAV moves the NAV leg toward zero, which is toward PASSING stage 3 "
                    "(the NAV control kills at half the price leg), so staleness here biases the test for the trade.",
     "If the test rate lies inside the range of the fit eras' rates, rule the class 'book as is'. If it lies above "
     "that range, check the flagged cells against a second NAV source (CEFConnect, as the stale-NAV gate does) "
     "before ruling, and rule each stale copy 'exclude from the NAV leg, counted'."),
    ("R7", "DG-X1", "The test set's end (§5.1) is frozen as the earlier of the refreshed panel's last ex-date and the "
                    "session 3 before the price panel's last session, both positional on the price panel's sessions, "
                    "so every event's cover row e+3 is a panel session.",
     "Keep."),
    ("R8", "DG-X6", "Factor coverage is checked on every session from the first test event's first return row to the "
                    "last event's e+3. Kenneth French's library lags by a month or more, so the French six end before "
                    "the test set does (X6 flags).",
     "Rule how stage 5 treats the uncovered sessions: wait for the next French vintage and run R-D4 on the full test "
     "window (recommended), or run it on the covered sessions and print the uncovered count."),
    ("R10", "DG-X2", "In the H-E declared calendar, a basket fund whose ex-date in [e+1, e+8] has no declaration found "
                     "(no sponsor release, no CRSP record) cannot be placed before or after e-1. The team lead ruled "
                     "on 2026-10-28 to KEEP it in the basket, as a stated limitation: the hedge basket's exclusion "
                     "window uses ex-dates that may not have been public at decide time. The opening's report names it. "
                     "The alternative (exclude) is printed beside.",
     "KEEP (team lead, 2026-10-28)."),
    ("R9", "DG-X7", "k (= spec.VOL_TARGET / sigma_active of the raw H-E sleeve on fit sessions with an event held) and "
                    "the cap-binding share are fit P&L. This run's brief (2026-10-27) forbade any fit statistic beyond "
                    "the identity gate, so neither is formed. `fit-k` computes and commits both, on the fit only, after "
                    "every flag is ruled and before `open`.",
     "Authorise `fit-k` once the flags are ruled."),
]
READINGS.sort(key=lambda r: int(r[0][1:]))


class Stage0Error(RuntimeError):
    """A Stage-0 input is missing or inconsistent; named, never filled."""


class IdentityGateFailure(RuntimeError):
    """DG-X7: a published fit figure did not reproduce. Stop and report."""


# =========================================================================== readers (no sealed name, no 2023+ value)

def _only_names(df: pd.DataFrame, what: str) -> pd.DataFrame:
    """Assert that no sealed name came through (the parquet filter should make this impossible)."""
    extra = sorted(set(df["ticker"]) - set(NAMES))
    if extra:
        raise Stage0Error(f"{what}: names outside the 17 were loaded: {extra}")
    return df


def read_fit(path: Path, cols=None, date_col: str = "date") -> pd.DataFrame:
    """A panel cut at FIT_END by a parquet filter, so no 2023+ row is loaded; asserted."""
    d = pd.read_parquet(path, columns=cols, filters=[(date_col, "<=", FIT_END), ("ticker", "in", list(NAMES))])
    d[date_col] = pd.to_datetime(d[date_col])
    if len(d) and d[date_col].max() > FIT_END:
        raise Stage0Error(f"{path.name}: a row after {FIT_END.date()} got through the fit filter")
    return _only_names(d, path.name)


def read_dates(path: Path, date_col: str = "date") -> pd.DataFrame:
    """`date_col, ticker` only, every date: the calendar, with no value of any kind."""
    d = pd.read_parquet(path, columns=[date_col, "ticker"], filters=[("ticker", "in", list(NAMES))])
    d[date_col] = pd.to_datetime(d[date_col])
    return _only_names(d, path.name)


def _present(path: Path, col: str, sessions: pd.DatetimeIndex, *, test: str) -> pd.DataFrame:
    """date x ticker booleans from one 2023+ column, built as the column is read; the values are dropped.

    test = "notna": a value exists. "zero": the value is 0. "repeat": the value equals the
    previous session's value for that ticker (a NAV repeat). Nothing but the boolean leaves."""
    d = pd.read_parquet(path, columns=["date", "ticker", col],
                        filters=[("date", ">=", TEST_START), ("ticker", "in", list(NAMES))])
    _only_names(d, path.name)
    d["date"] = pd.to_datetime(d["date"])
    if d.duplicated(["date", "ticker"]).any():
        raise Stage0Error(f"{path.name}: two rows for one (date, ticker)")
    W = d.pivot(index="date", columns="ticker", values=col).reindex(index=sessions, columns=list(NAMES))
    del d
    if test == "notna":
        out = W.notna()
    elif test == "zero":
        out = W.eq(0)
    elif test == "repeat":
        out = W.eq(W.shift(1)) & W.notna()
    else:
        raise ValueError(test)
    del W
    return out


def read_dist(path: Path) -> pd.DataFrame:
    """The distribution panel for the 17: ticker, ex_date, amount (amounts are not returns)."""
    d = pd.read_parquet(path, columns=["ticker", "ex_date", "amount", "stock_split"],
                        filters=[("ticker", "in", list(NAMES))])
    d["ex_date"] = pd.to_datetime(d["ex_date"])
    return _only_names(d, path.name)


def sessions_calendar() -> pd.DatetimeIndex:
    """Every session of the 17's price panel (dates only), fit and test."""
    return pd.DatetimeIndex(sorted(read_dates(PRICES)["date"].unique()))


def nyse_mismatch(sessions: pd.DatetimeIndex, lo, hi) -> dict:
    """Panel sessions against ops/schedule/nyse_calendar.py on [lo, hi]: both differences, as dates."""
    from ops.schedule.nyse_calendar import is_trading_day
    days = pd.bdate_range(lo, hi)
    nyse = {d for d in days if is_trading_day(d.date())}
    have = {d for d in sessions if lo <= d <= hi}
    return {"panel_not_nyse": sorted(str(d.date()) for d in have - nyse),
            "nyse_not_panel": sorted(str(d.date()) for d in nyse - have)}


# =========================================================================== DG-X7: the identity gate (fit only)

def fit_returns(close: pd.DataFrame, dist: pd.DataFrame) -> pd.DataFrame:
    """r6's total return (check_credit.py, as prereg_inputs.py reproduced it), on fit rows only.

    ret = (close + D) / close.shift(1) - 1; masked within +-5 sessions of a `stock_split` > 0 row of
    the distribution panel and where |ret| > 30%. Alignment: row t's return uses closes t-1 and t."""
    if close.index.max() > FIT_END:
        raise Stage0Error("fit_returns was handed a row after FIT_END")
    div = (dist[dist.amount > 0].pivot_table(index="ex_date", columns="ticker", values="amount", aggfunc="sum")
           .reindex(close.index).reindex(columns=close.columns).fillna(0.0))  # no row = no distribution that day
    ret = (close + div) / close.shift(1) - 1.0
    bad = pd.DataFrame(False, index=ret.index, columns=ret.columns)
    for _, r in dist[dist.stock_split > 0].iterrows():
        i = ret.index.searchsorted(r.ex_date)
        bad.iloc[max(0, i - SPLIT_MASK):i + SPLIT_MASK + 1, bad.columns.get_loc(r.ticker)] = True
    return ret.mask(bad | (ret.abs() > 0.30))


def month_t(g: pd.DataFrame, col: str) -> tuple[float, int, float]:
    m = g.groupby(g.date.dt.to_period("M"))[col].mean()
    return float(m.mean() / m.std() * np.sqrt(len(m))), int(len(m)), float(m.std())


def r6_events(ret: pd.DataFrame, dist: pd.DataFrame) -> pd.DataFrame:
    """r6's events: CAR(+1..+3) of the abnormal return against the same-date mean of the 17."""
    ab = ret.sub(ret.mean(axis=1), axis=0)
    idx = ret.index
    pos = {x: i for i, x in enumerate(idx)}
    rows = []
    for _, e in dist[dist.amount > 0].iterrows():
        if e.ex_date not in pos:
            continue
        i = pos[e.ex_date]
        if i < 6 or i + 6 >= len(idx):
            continue
        rows.append({"date": e.ex_date, "ticker": e.ticker, 1: ab[e.ticker].values[i + 1],
                     2: ab[e.ticker].values[i + 2], 3: ab[e.ticker].values[i + 3]})
    ev = pd.DataFrame(rows).dropna(subset=[1, 2, 3])
    ev = ev[ev.date >= FIT_START].copy()
    ev["car13"] = ev[[1, 2, 3]].sum(axis=1)
    return ev


def he_events(ret: pd.DataFrame, dist: pd.DataFrame) -> pd.DataFrame:
    """H-E on the fit (prereg_inputs_b3.py): -(r_i - basket) summed over rows e+1..e+3, basket >= 3."""
    idx = ret.index
    pos = {x: i for i, x in enumerate(idx)}
    exd = dist[dist.amount > 0][["ticker", "ex_date"]]
    near = pd.DataFrame(False, index=idx, columns=list(NAMES))
    for _, r in exd.iterrows():
        if r.ex_date in pos:
            near.iloc[pos[r.ex_date], near.columns.get_loc(r.ticker)] = True
    R = ret[list(NAMES)]
    rec = []
    for _, e in exd[exd.ex_date >= FIT_START].iterrows():
        if e.ex_date not in pos:
            continue
        i = pos[e.ex_date]
        if i < 2 or i + 9 >= len(idx):
            continue
        rows3 = [i + 1, i + 2, i + 3]
        ri = R[e.ticker].values[rows3]
        if not np.isfinite(ri).all():
            continue
        blk = near.iloc[i + HE_LO:i + HE_HI + 1]
        cand = [j for j in NAMES if j != e.ticker and not blk[j].any() and np.isfinite(R[j].values[rows3]).all()]
        he = float(-(ri - R[cand].values[rows3].mean(axis=1)).sum()) if len(cand) >= BASKET_MIN else np.nan
        rec.append(dict(date=e.ex_date, ticker=e.ticker, p=i, nb=len(cand), he=he, basket=",".join(cand)))
    return pd.DataFrame(rec)


def assert_denormal_free(x) -> None:
    """DG-X8: no value is denormal-like (numexpr_fault.py found 1e-316-scale garbage in frame arithmetic)."""
    v = np.abs(np.asarray(x, dtype=float))
    if np.any((v > 0) & (v < 1e-250)):
        raise AssertionError("a value is denormal-like: the numexpr fault (DG-X8)")


def identity_gate(dist_path: Path) -> dict:
    """DG-X7 on the fit: r6 (3,226 events, -20.454bp, month t -6.765) and H-E's sd 150.3bp.

    Raises IdentityGateFailure, naming each figure that did not reproduce. Returns the table."""
    px = read_fit(PRICES, ["date", "ticker", "close"])
    if px.ticker.nunique() != len(NAMES):
        raise Stage0Error(f"fit prices hold {px.ticker.nunique()} of the {len(NAMES)} names")
    close = px.pivot(index="date", columns="ticker", values="close").sort_index()
    dist = read_fit(dist_path, ["ticker", "ex_date", "amount", "stock_split"], date_col="ex_date")
    ret = fit_returns(close, dist)
    assert ret.index.max() <= FIT_END
    ev = r6_events(ret, dist)
    assert_denormal_free(ev["car13"])
    t6, m6, _ = month_t(ev, "car13")
    E = he_events(ret, dist)
    g = E.dropna(subset=["he"])
    assert_denormal_free(g["he"])
    sdm = g.groupby(g.date.dt.to_period("M"))["he"].mean().std()
    rows = [
        ("r6 events (17, 2005-22)", len(ev), R6_PUBLISHED["events"], 0, abs(len(ev) - R6_PUBLISHED["events"]) == 0),
        ("r6 CAR(+1..+3), bp", 1e4 * ev.car13.mean(), R6_PUBLISHED["car_bp"], R6_TOL,
         abs(1e4 * ev.car13.mean() - R6_PUBLISHED["car_bp"]) < R6_TOL),
        ("r6 month-clustered t", t6, R6_PUBLISHED["t_month"], R6_TOL, abs(t6 - R6_PUBLISHED["t_month"]) < R6_TOL),
        ("H-E per-event sd, bp", 1e4 * g.he.std(), HE_SD_PUBLISHED_BP, HE_SD_TOL_BP,
         abs(1e4 * g.he.std() - HE_SD_PUBLISHED_BP) < HE_SD_TOL_BP),
    ]
    T = pd.DataFrame(rows, columns=["figure", "reproduced", "published", "tolerance", "ok"])
    beside = {"r6_months": m6, "he_events_with_return": int(len(E)), "he_events_traded": int(len(g)),
              "he_share_basket_lt3": float((E.nb < BASKET_MIN).mean()), "he_median_basket": float(E.nb.median()),
              "he_sd_month_mean_bp": float(1e4 * sdm), "he_sd_month_mean_published_bp": HE_SDM_PUBLISHED_BP}
    return {"table": T, "beside": beside, "pass": bool(T["ok"].all())}


# =========================================================================== the test calendar (dates only)

def splits_in(splits: pd.DataFrame, lo, hi) -> pd.DataFrame:
    s = splits[(splits.ex_date >= lo) & (splits.ex_date <= hi) & splits.ticker.isin(NAMES)]
    return s.sort_values(["ticker", "ex_date"]).reset_index(drop=True)


def split_basis_class(factor: float, tol: float = dg.SPLIT_TOL) -> str:
    """data_guards.split_basis_check's class where it needs no return: |ln k| <= 2 tol is
    `undecidable` (the price cannot tell the bases apart), whatever the return. Otherwise the
    class needs the return on the ex-date, which Stage 0 may not form: `needs_return`."""
    return "undecidable" if abs(math.log(factor)) <= 2 * tol else "needs_return"


def test_end(dist_last: pd.Timestamp, sessions: pd.DatetimeIndex, last_session: pd.Timestamp) -> pd.Timestamp:
    """§5.1 (reading R7): the earlier of the panel's last ex-date and the session 3 before the last."""
    i = sessions.get_loc(last_session)
    return min(pd.Timestamp(dist_last), sessions[i - HOLD])


def test_events(dist: pd.DataFrame, sessions: pd.DatetimeIndex, end_ex: pd.Timestamp,
                splits: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(events, ex-dates that are not sessions) for TEST_START <= e <= end_ex. Dates only.

    Columns: ticker, ex_date, p (session position), next_ex_within3 (rule 2), split_masked (rule 3,
    reading R1: a hold row e+1..e+3 within +-5 sessions of the fund's own split)."""
    x = dist[(dist.amount > 0) & (dist.ex_date >= TEST_START)][["ticker", "ex_date"]].drop_duplicates()
    spos = {d: i for i, d in enumerate(sessions)}
    not_sess = x[~x.ex_date.isin(spos)].copy()
    x = x[x.ex_date.isin(spos) & (x.ex_date <= end_ex)].copy()
    x["p"] = x.ex_date.map(spos).astype(int)
    allx = dist[(dist.amount > 0)][["ticker", "ex_date"]].drop_duplicates()
    allx = allx[allx.ex_date.isin(spos)]
    own = {t: np.array(sorted(spos[d] for d in g.ex_date)) for t, g in allx.groupby("ticker")}
    x["next_ex_within3"] = [bool(((own[t] > p) & (own[t] <= p + NEXT_EX_WITHIN)).any()) for t, p in zip(x.ticker, x.p)]
    sp = {t: [spos[d] for d in g.ex_date if d in spos] for t, g in splits.groupby("ticker")} if len(splits) else {}
    x["split_masked"] = [any(abs(p + k - q) <= SPLIT_MASK for q in sp.get(t, []) for k in range(1, HOLD + 1))
                         for t, p in zip(x.ticker, x.p)]
    return x.sort_values(["ex_date", "ticker"]).reset_index(drop=True), not_sess


def calendar_baskets(ev: pd.DataFrame, dist: pd.DataFrame, sessions: pd.DatetimeIndex,
                     close_ok: pd.DataFrame, splits: pd.DataFrame) -> pd.Series:
    """H-E basket size per event on the KNOWN calendar (every ex-date in the panel, not yet the
    declared-at-e-1 calendar, which waits on DG-X2), with a bar on e..e+3 and no split-masked
    hold row. Presence only: the |r| > 30% mask needs returns and is applied at the opening."""
    spos = {d: i for i, d in enumerate(sessions)}
    allx = dist[(dist.amount > 0)][["ticker", "ex_date"]].drop_duplicates()
    own = {t: set(spos[d] for d in g.ex_date if d in spos) for t, g in allx.groupby("ticker")}
    sp = {t: [spos[d] for d in g.ex_date if d in spos] for t, g in splits.groupby("ticker")} if len(splits) else {}
    ok = close_ok.reindex(index=sessions, columns=list(NAMES)).fillna(False).to_numpy()
    col = {t: j for j, t in enumerate(NAMES)}
    out = []
    for t, p in zip(ev.ticker, ev.p):
        n = 0
        for j in NAMES:
            if j == t or any((p + k) in own.get(j, set()) for k in range(HE_LO, HE_HI + 1)):
                continue
            if p + HOLD >= len(sessions) or not ok[p:p + HOLD + 1, col[j]].all():
                continue
            if any(abs(p + k - q) <= SPLIT_MASK for q in sp.get(j, []) for k in range(1, HOLD + 1)):
                continue
            n += 1
        out.append(n)
    return pd.Series(out, index=ev.index, name="basket_calendar")


def declared_baskets(ev: pd.DataFrame, ann: pd.DataFrame, sessions: pd.DatetimeIndex, close_ok: pd.DataFrame,
                     splits: pd.DataFrame, unknown: str = "exclude") -> tuple[pd.Series, dict]:
    """H-E basket size per event on the DECLARED calendar (prereg §4.3). Fund j leaves event i's
    basket if j has an ex-date in [e+1, e+8] whose earliest declaration is on or before e-1. Since
    the ruling of 2026-10-28, declarations come from the sponsor-release table.
    - An ex-date declared after e-1 stays in, as a trader would have held it. That is a calendar
      surprise, and it is counted.
    - An ex-date with NO release found (declaration NaT) cannot be placed before or after e-1.
      Keeping the fund would assume "not declared" and excluding it would assume "declared". The
      team lead's ruling of 2026-10-28 ("a fund or event whose release cannot be found is excluded
      and counted, never guessed") is applied as `unknown="exclude"` (reading R10): the fund leaves
      that event's basket, and the leg is counted.
    - Same presence and split-mask conditions as `calendar_baskets`. Dates only."""
    if unknown not in ("exclude", "keep"):
        raise ValueError(unknown)
    spos = {d: i for i, d in enumerate(sessions)}
    ok_ann = ann[(ann.status == 200) & ann.ex_date.notna() & ann.ticker.isin(NAMES)]
    dec = ok_ann.groupby(["ticker", "ex_date"])["declaration_date"].min()
    own = {}
    for (t, x_), dd in dec.items():
        if x_ in spos:
            own.setdefault(t, []).append((spos[x_], dd))
    sp = {t: [spos[d] for d in g.ex_date if d in spos] for t, g in splits.groupby("ticker")} if len(splits) else {}
    ok = close_ok.reindex(index=sessions, columns=list(NAMES)).fillna(False).to_numpy()
    col = {t: j for j, t in enumerate(NAMES)}
    out, surprises, unknown_n = [], 0, 0
    for t, p in zip(ev.ticker, ev.p):
        cutoff = sessions[p - 1]
        n = 0
        for j in NAMES:
            if j == t:
                continue
            inwin = [(q, dd) for q, dd in own.get(j, []) if HE_LO <= q - p <= HE_HI]
            if any(pd.notna(dd) and dd <= cutoff for _, dd in inwin):
                continue
            if any(pd.isna(dd) for _, dd in inwin):
                unknown_n += 1
                if unknown == "exclude":
                    continue
            surprises += int(any(pd.notna(dd) for _, dd in inwin))
            if p + HOLD >= len(sessions) or not ok[p:p + HOLD + 1, col[j]].all():
                continue
            if any(abs(p + k - q) <= SPLIT_MASK for q in sp.get(j, []) for k in range(1, HOLD + 1)):
                continue
            n += 1
        out.append(n)
    return pd.Series(out, index=ev.index, name="basket_declared"), {"declared_after_e_minus_1_legs_kept": surprises,
                                                                    "no_release_legs": unknown_n,
                                                                    "no_release_treatment": unknown}


def count_table(ev: pd.DataFrame, label: str) -> dict:
    """§5.1's counts (dates only)."""
    e = ev[~ev.next_ex_within3 & ~ev.split_masked]
    b = e[e.basket_calendar >= BASKET_MIN] if "basket_calendar" in e else e.iloc[0:0]
    return {"label": label, "events": int(len(e)), "events_13": int(e.ticker.isin(CORE).sum()),
            "dates": int(e.ex_date.nunique()), "months": int(e.ex_date.dt.to_period("M").nunique()),
            "basket_ge3": int(len(b)), "basket_ge3_13": int(b.ticker.isin(CORE).sum()),
            "by_year": {int(k): int(v) for k, v in e.groupby(e.ex_date.dt.year).size().items()},
            "T2": int((e.ex_date < T1_START).sum()), "T1": int((e.ex_date >= T1_START).sum()),
            "excluded_next_ex_within3": int(ev.next_ex_within3.sum()), "excluded_split_mask": int(ev.split_masked.sum())}


# =========================================================================== flags

def _flag(rows: list, check, ticker, date, gate, events, note, recommended):
    rows.append({"check": check, "ticker": ticker, "date": pd.Timestamp(date).strftime("%Y-%m-%d"), "gate": gate,
                 "events": events, "note": note, "recommended": recommended})


def bar_flags(ev: pd.DataFrame, sessions: pd.DatetimeIndex, close_ok: pd.DataFrame, vol_zero: pd.DataFrame,
              alpaca_bars: pd.DataFrame | None) -> list:
    """DG-X4 (reading R5): the event fund's bar on e..e+3 and volume > 0 on the fill days e, e+3."""
    rows = []
    C = close_ok.reindex(index=sessions, columns=list(NAMES)).fillna(False)
    V = vol_zero.reindex(index=sessions, columns=list(NAMES)).fillna(False)
    alp_show = {}
    if alpaca_bars is not None and len(alpaca_bars):
        for t, d, c, v in zip(alpaca_bars.ticker, pd.to_datetime(alpaca_bars.date), alpaca_bars.close, alpaca_bars.volume):
            alp_show[(t, d)] = (bool(np.isfinite(c) and c > 0), bool(np.isfinite(v) and v > 0))   # booleans only
    miss, zero = {}, {}
    for t, e, p in zip(ev.ticker, ev.ex_date, ev.p):
        for k in range(0, HOLD + 1):
            d = sessions[p + k]
            if not C.at[d, t]:
                miss.setdefault((t, d), []).append(f"{e.date()} (e+{k})")
            elif k in (0, HOLD) and V.at[d, t]:
                zero.setdefault((t, d), []).append(f"{e.date()} (e+{k})")
    for (t, d), evs in sorted(miss.items()):
        if alpaca_bars is None:
            alp = "Alpaca SIP not yet fetched"
        elif (t, d) in alp_show:
            c_ok, v_ok = alp_show[(t, d)]
            alp = (f"Alpaca raw SIP bar present: close {'yes' if c_ok else 'no'}, volume > 0 "
                   f"{'yes' if v_ok else 'no'}")
        else:
            alp = "no Alpaca raw SIP bar"
        _flag(rows, "X4_no_bar", t, d, "DG-X4", "; ".join(evs),
              f"no yfinance close on this session (volume 0 or missing); {alp}",
              "fill the close from Alpaca's raw SIP bar (C4 precedent, 2026-10-14) if present; else exclude the "
              "event and count it (rule 4: never filled with zero)")
    for (t, d), evs in sorted(zero.items()):
        _flag(rows, "X4_zero_volume_fill", t, d, "DG-X4", "; ".join(evs), "a close but zero volume on a fill day",
              "book as is if the close is a real print; else exclude the event and count it")
    return rows


def bar_guard_flags(sessions: pd.DatetimeIndex, splits: pd.DataFrame) -> tuple[list, dict]:
    """DG-X4: the spike-and-revert guard on the 17's closes over the test window. Flag keys only.

    `split_like_spikes` reads close and NAV ratios inside data_guards; this function keeps only
    (ticker, date, run_end, revert_date, factor) and drops the ratio columns unread."""
    lo = TEST_START
    px = pd.read_parquet(PRICES, columns=["date", "ticker", "close"],
                         filters=[("date", ">=", lo), ("ticker", "in", list(NAMES))])
    nv = pd.read_parquet(NAVS, columns=["date", "ticker", "nav"],
                         filters=[("date", ">=", lo), ("ticker", "in", list(NAMES))])
    _only_names(px, "prices")
    _only_names(nv, "navs")
    close = dg._wide(px, "close")
    nav = dg._wide(nv, "nav")
    del px, nv
    sp = splits[["ticker", "ex_date", "stock_split"]] if len(splits) else None
    H, U = dg.split_like_spikes(close, nav, sp)
    del close, nav
    keep = ["ticker", "date", "run_end", "revert_date", "factor"]
    H = H[[c for c in keep if c in H.columns]]
    U = U[[c for c in ("ticker", "date", "factor") if c in U.columns]] if len(U) else U
    rows = []
    for r in H.itertuples():
        _flag(rows, "X4_spike_revert", r.ticker, r.date, "DG-X4", "-",
              f"split-like spike-and-revert bar, run to {pd.Timestamp(r.run_end).date()}, revert "
              f"{pd.Timestamp(r.revert_date).date()}, factor {r.factor:g}",
              f"record a bar ruling in {BAR_RULINGS.name} (rebase or book_as_is); guard_closes raises without one")
    for r in (U.itertuples() if len(U) else []):
        _flag(rows, "X4_unreverted_jump", r.ticker, r.date, "DG-X4", "-",
              f"split-like jump the NAV did not make, not reverted within {dg.REVERT_WINDOW} sessions, factor "
              f"{r.factor:g}", "check against a second price source before the opening")
    return rows, {"spike_revert": int(len(H)), "unreverted": int(len(U))}


def x4_basis_check(sessions: pd.DatetimeIndex, tol: float = 0.01) -> tuple[list, dict]:
    """Ruling O4 (team lead, 2026-10-28), at Stage 0: for each filled X4 cell (ticker, e), Alpaca's raw
    SIP close and yfinance's close must both exist on e-1 and on e+1, and agree within $0.01.

    This is C4's adjacent-bar check. Two sources' closes on the same session are compared for share
    basis. No return and no price change is formed, and no level is printed: a pass/fail per cell
    and the largest gap in cents only. A failing cell is a flag (`X4_basis_mismatch`) for a ruling."""
    if not (ALPACA_BARS.exists() and ALPACA_ADJ_BARS.exists()):
        return [], {"status": "adjacent bars not fetched"}
    cells = pd.read_parquet(ALPACA_BARS, columns=["ticker", "date"])
    adj = pd.read_parquet(ALPACA_ADJ_BARS, columns=["ticker", "date", "close"])
    for f_ in (cells, adj):
        f_["date"] = pd.to_datetime(f_["date"])
    _only_names(cells, "x4 cells")
    _only_names(adj, "x4 adjacent bars")
    need = []
    for t, d in zip(cells.ticker, cells.date):
        i = sessions.get_loc(d)
        need += [(t, sessions[i - 1]), (t, sessions[i + 1])]
    days = sorted({d for _, d in need})
    yf = pd.read_parquet(PRICES, columns=["date", "ticker", "close"], filters=[("ticker", "in", sorted(set(cells.ticker))),
                                                                            ("date", "in", days)])
    yf["date"] = pd.to_datetime(yf["date"])
    yk = {(t, d): c for t, d, c in zip(yf.ticker, yf.date, yf.close)}
    ak = {(t, d): c for t, d, c in zip(adj.ticker, adj.date, adj.close)}
    rows, worst, n_ok = [], 0.0, 0
    for t, d in zip(cells.ticker, cells.date):
        i = sessions.get_loc(d)
        ok, why = True, []
        for nb in (sessions[i - 1], sessions[i + 1]):
            a, y = ak.get((t, nb)), yk.get((t, nb))
            if a is None or y is None or not (np.isfinite(a) and np.isfinite(y)):
                ok = False
                why.append(f"{nb.date()}: {'no Alpaca bar' if a is None else 'no yfinance close'}")
                continue
            gap = abs(float(a) - float(y))
            worst = max(worst, gap)
            if gap > tol:
                ok = False
                why.append(f"{nb.date()}: gap {100 * gap:.1f} cents")
        n_ok += int(ok)
        if not ok:
            _flag(rows, "X4_basis_mismatch", t, d, "DG-X4", str(d.date()), "; ".join(why),
                  "rule whether the Alpaca fill stands for this cell (ruling O4 requires agreement within $0.01)")
    return rows, {"cells": int(len(cells)), "pass": n_ok, "fail": int(len(cells)) - n_ok,
                  "largest_gap_cents": round(100 * worst, 2), "tolerance_usd": tol}


def missing_close_cells(close_ok: pd.DataFrame, test_sess: pd.DatetimeIndex, dist: pd.DataFrame) -> dict:
    """Every (ticker, session) of the test window with no close, and how many fall on that fund's
    own ex-date (presence only). A pattern here is a fetcher defect, not a market fact."""
    C = close_ok.reindex(index=test_sess, columns=list(NAMES)).fillna(False)
    miss = [(t, d) for t in NAMES for d in test_sess[~C[t].to_numpy()]]
    ex = set(zip(dist.ticker, dist.ex_date))
    return {"cells": len(miss), "on_own_ex_date": sum((t, d) in ex for t, d in miss),
            "dates": sorted({str(d.date()) for _, d in miss})}


def nav_flags(ev: pd.DataFrame, sessions: pd.DatetimeIndex, nav_ok: pd.DataFrame, nav_rep: pd.DataFrame) -> list:
    """DG-X5 (reading R6): the event fund's NAV on e..e+3, and repeats on e+1..e+3."""
    rows = []
    N = nav_ok.reindex(index=sessions, columns=list(NAMES)).fillna(False)
    P = nav_rep.reindex(index=sessions, columns=list(NAMES)).fillna(False)
    miss, rep, rep0 = {}, {}, {}
    for t, e, p in zip(ev.ticker, ev.ex_date, ev.p):
        for k in range(0, HOLD + 1):
            d = sessions[p + k]
            if not N.at[d, t]:
                miss.setdefault((t, d), []).append(f"{e.date()} (e+{k})")
            elif k == 0 and P.at[d, t]:
                rep0.setdefault((t, d), []).append(f"{e.date()} (e+0)")
            elif k >= 1 and P.at[d, t]:
                rep.setdefault((t, d), []).append(f"{e.date()} (e+{k})")
    for (t, d), evs in sorted(miss.items()):
        _flag(rows, "X5_nav_missing", t, d, "DG-X5", "; ".join(evs), "no NAV on this session; the NAV leg has no return",
              "exclude the event from the NAV leg only and count it (the price leg is unaffected)")
    for (t, d), evs in sorted(rep0.items()):
        _flag(rows, "X5_nav_repeat_on_e", t, d, "DG-X5", "; ".join(evs),
              "NAV on the ex-date equals the cum-distribution NAV of e-1: a stale copy, so the distribution's NAV drop "
              "lands on hold row e+1 of the NAV leg",
              "exclude the event from the NAV leg only, counted (left in, it pushes the NAV control towards a kill)")
    for (t, d), evs in sorted(rep.items()):
        _flag(rows, "X5_nav_repeat", t, d, "DG-X5", "; ".join(evs), "NAV equals the previous session's NAV",
              "book as is (class ruling, reading R6) unless the fit/test repeat rates differ")
    return rows


def repeat_rate_fit(dist: pd.DataFrame) -> dict:
    """The NAV-repeat rate on event funds' rows e+1..e+3 in the FIT (equality only), for R6."""
    nv = read_fit(NAVS, ["date", "ticker", "nav"])
    W = nv.pivot(index="date", columns="ticker", values="nav").sort_index()   # the NAV panel's own sessions
    rep = (W.eq(W.shift(1)) & W.notna()).to_numpy()
    ok = W.notna().to_numpy()
    navidx = W.index
    pos = {d: i for i, d in enumerate(navidx)}
    col = {t: j for j, t in enumerate(W.columns)}
    del W, nv
    x = dist[(dist.amount > 0) & (dist.ex_date >= FIT_START) & (dist.ex_date <= FIT_END)]
    n = r = n0 = r0 = 0
    by: dict = {}
    for t, e in zip(x.ticker, x.ex_date):
        if e not in pos or t not in col:
            continue
        i = pos[e]
        era = next(lab for lab, a, b in FIT_ERAS if a <= e.year <= b)
        if i >= 1 and ok[i, col[t]]:
            n0 += 1
            r0 += int(rep[i, col[t]])
        for k in range(1, HOLD + 1):
            if i + k < len(navidx) and ok[i + k, col[t]]:
                n += 1
                r += int(rep[i + k, col[t]])
                c = by.setdefault(era, [0, 0])
                c[0] += 1
                c[1] += int(rep[i + k, col[t]])
    return {"cells": n, "repeats": r, "rate": r / n if n else float("nan"),
            "by_era": {k: round(v[1] / v[0], 3) for k, v in by.items()},
            "on_e": {"cells": n0, "repeats": r0, "rate": r0 / n0 if n0 else float("nan")}}


def repeat_rate_test(ev: pd.DataFrame, sessions: pd.DatetimeIndex, nav_ok: pd.DataFrame, nav_rep: pd.DataFrame,
                     basket: bool = False) -> dict:
    N = nav_ok.reindex(index=sessions, columns=list(NAMES)).fillna(False)
    P = nav_rep.reindex(index=sessions, columns=list(NAMES)).fillna(False)
    n = r = 0
    by: dict = {}
    for t, p in zip(ev.ticker, ev.p):
        for k in range(1, HOLD + 1):
            d = sessions[p + k]
            for j in ([t] if not basket else [j for j in NAMES if j != t]):
                if N.at[d, j]:
                    n += 1
                    r += int(P.at[d, j])
                    c = by.setdefault(int(d.year), [0, 0])
                    c[0] += 1
                    c[1] += int(P.at[d, j])
    return {"cells": n, "repeats": r, "rate": r / n if n else float("nan"),
            "by_year": {k: round(v[1] / v[0], 3) for k, v in sorted(by.items())}}


# =========================================================================== DG-X1..X3: the second source

def yf_vs_alpaca(ev: pd.DataFrame, dist: pd.DataFrame, alp: pd.DataFrame, end_ex: pd.Timestamp) -> tuple[list, dict]:
    """DG-X1 (readings R2, R3): every test ex-date and amount, yfinance against Alpaca v1."""
    rows = []
    a = alp[alp.kind.isin(["cash_dividends", "capital_gains_distributions"])]
    a = a[(a.ex_date >= TEST_START) & (a.ex_date <= end_ex)]
    A = a.groupby(["ticker", "ex_date"]).agg(alp_amount=("amount", "sum"), alp_records=("amount", "size")).reset_index()
    y = dist[(dist.amount > 0) & (dist.ex_date >= TEST_START) & (dist.ex_date <= end_ex)]
    Y = y.groupby(["ticker", "ex_date"]).agg(yf_amount=("amount", "sum")).reset_index()
    M = Y.merge(A, on=["ticker", "ex_date"], how="outer", indicator="src")
    for r in M.itertuples():
        if r.src == "left_only":
            _flag(rows, "X1_alpaca_absent", r.ticker, r.ex_date, "DG-X1", str(r.ex_date.date()),
                  "yfinance lists this ex-date; Alpaca v1 has no distribution on it",
                  "confirm from a sponsor notice or CRSP, or exclude the event and count it")
        elif r.src == "right_only":
            _flag(rows, "X1_yf_absent", r.ticker, r.ex_date, "DG-X1", str(r.ex_date.date()),
                  "Alpaca v1 lists a distribution on this ex-date; the yfinance panel has none",
                  "a missed event: confirm, then add it to the event set and the H-E calendar, or rule it out")
        elif abs(r.yf_amount - r.alp_amount) > DIV_TOL:
            _flag(rows, "X1_amount_mismatch", r.ticker, r.ex_date, "DG-X1", str(r.ex_date.date()),
                  f"amounts differ by more than ${DIV_TOL}/share (yfinance {r.yf_amount:.4f}, Alpaca "
                  f"{r.alp_amount:.4f}, {int(r.alp_records)} record(s))",
                  "confirm the ex-date and keep the event: by construction no held cell carries a distribution "
                  "(prereg §4.5), so the amount enters no P&L of (b); use Alpaca's amount for the report-only "
                  "size strata")
    s = {"yf_ex_dates": int(len(Y)), "alpaca_ex_dates": int(len(A)),
         "agree": int(((M.src == "both") & ((M.yf_amount - M.alp_amount).abs() <= DIV_TOL)).sum()),
         "agree_exact": int(((M.src == "both") & ((M.yf_amount - M.alp_amount).abs() <= 1e-9)).sum())}
    return rows, s


def record_flags(ev: pd.DataFrame, alp: pd.DataFrame, sessions: pd.DatetimeIndex) -> tuple[list, dict]:
    """DG-X3: the record date of every test event and the regime arithmetic of prereg §4.2.

    T+2 (ex before 2024-05-28): record = the session after ex. T+1 (from 2024-05-28): record = ex.
    Sessions are the price panel's; a record date that is not a session is flagged, not shifted."""
    rows = []
    a = alp[alp.kind.isin(["cash_dividends", "capital_gains_distributions"])]
    rec = a.groupby(["ticker", "ex_date"])["record_date"].agg(lambda s: sorted(set(s.dropna())))
    spos = {d: i for i, d in enumerate(sessions)}
    n_ok = 0
    for t, e, p in zip(ev.ticker, ev.ex_date, ev.p):
        r = rec.get((t, e), [])
        if len(r) != 1:
            _flag(rows, "X3_no_record_date" if not r else "X3_record_dates_disagree", t, e, "DG-X3", str(e.date()),
                  "no Alpaca record date for this ex-date" if not r else f"Alpaca records disagree: {[str(x.date()) for x in r]}",
                  "read the record date from a sponsor notice, or rule the regime row as the evidence")
            continue
        rd = pd.Timestamp(r[0])
        want = sessions[p + 1] if e < T1_START else e
        if rd not in spos:
            _flag(rows, "X3_record_not_session", t, e, "DG-X3", str(e.date()), f"record date {rd.date()} is not a "
                  "panel session", "check the settlement calendar (bank holidays differ from NYSE's)")
        elif rd != want:
            _flag(rows, "X3_regime_break", t, e, "DG-X3", str(e.date()),
                  f"record {rd.date()}; the {'T+2' if e < T1_START else 'T+1'} row of prereg §4.2 gives {want.date()}",
                  "rule whether the short opened at e's close is still not a holder of record")
        else:
            n_ok += 1
    return rows, {"events": int(len(ev)), "regime_ok": n_ok}


def declaration_flags(ev: pd.DataFrame, ann: pd.DataFrame, sessions: pd.DatetimeIndex) -> tuple[list, dict]:
    """DG-X2 (reading R4): a declaration date <= e-1 for every test event."""
    rows = []
    ok = ann[(ann.status == 200) & ann.ex_date.notna()]
    dec = ok.groupby(["ticker", "ex_date"])["declaration_date"].agg(lambda s: sorted(set(s.dropna())))
    n_ok = n_eq = n_le2 = 0
    for t, e, p in zip(ev.ticker, ev.ex_date, ev.p):
        dd = dec.get((t, e), [])
        prev = sessions[p - 1]
        if len(dd) == 0:
            _flag(rows, "X2_no_declaration", t, e, "DG-X2", str(e.date()), "no Alpaca announcement with a declaration date",
                  "read the declaration from a sponsor notice, or exclude the event and count it (§4.1 rule 1)")
            continue
        d0 = pd.Timestamp(min(dd))
        if len(dd) > 1:
            _flag(rows, "X2_declarations_disagree", t, e, "DG-X2", str(e.date()),
                  f"announcements give {[str(x.date()) for x in dd]}; the earliest is tested", "rule which one stands")
        if d0 > prev:
            _flag(rows, "X2_declared_late", t, e, "DG-X2", str(e.date()), f"declared {d0.date()}, after e-1 {prev.date()}",
                  "exclude the event and count it (§4.1 rule 1)")
        else:
            n_ok += 1
            n_eq += int(d0 == prev)
            n_le2 += int(d0 <= sessions[p - 2])
    return rows, {"declared_by_e_minus_1": n_ok, "declared_on_e_minus_1": n_eq, "declared_by_e_minus_2": n_le2}


def fetch_notices(notices_path: Path = NOTICES, cache: Path = NOTICE_CACHE) -> dict:
    """Fetch every notice URL (scripts/data/fetch_sponsor_notices.fetch: a plain GET) into the cache,
    with a manifest {url: sha16}. Public; no credential."""
    import json as _json
    from scripts.data.fetch_sponsor_notices import fetch
    N = pd.read_csv(notices_path, dtype=str)
    cache.mkdir(parents=True, exist_ok=True)
    man = {}
    for u in N["url"].unique():
        raw, _ = fetch(u, edgar=None)
        h = hashlib.sha256(raw).hexdigest()[:16]
        (cache / f"{h}.bin").write_bytes(raw)
        man[u] = h
    (cache / "manifest.json").write_text(_json.dumps(man, indent=1))
    return man


def _doc_text(raw: bytes) -> str:
    if raw[:5] == b"%PDF-":
        import io
        import pypdf
        return " ".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(raw)).pages)
    return raw.decode("utf-8", errors="replace")


def verify_notices(notices_path: Path = NOTICES, cache: Path = NOTICE_CACHE) -> pd.DataFrame:
    """Every notice's three quotes must occur in its cached document (offline). Raises naming any
    that do not: a citation that cannot be re-found is an anecdote (.claude/rules/documents.md)."""
    from scripts.data.fetch_sponsor_notices import quote_found
    N = pd.read_csv(notices_path, dtype=str)
    man_p = cache / "manifest.json"
    if not man_p.exists():
        raise Stage0Error(f"{man_p} does not exist: run `python3 scripts/events/exdrift_trial.py notices` (public)")
    man = json.loads(man_p.read_text())
    texts = {}
    bad = []
    for r in N.itertuples():
        if r.url not in man:
            raise Stage0Error(f"notice {r.ticker} {r.ex_date}: {r.url[:60]}... is not in the notice cache")
        if r.url not in texts:
            texts[r.url] = _doc_text((cache / f"{man[r.url]}.bin").read_bytes())
        for q in (r.quote_declared, r.quote_dates, r.quote_fund):
            if not quote_found(q, texts[r.url]):
                bad.append((r.ticker, r.ex_date, q))
    if bad:
        raise Stage0Error(f"sponsor-notice quotes not found in their documents: {bad}")
    N["ex_date"] = pd.to_datetime(N["ex_date"])
    N["stated_declaration"] = pd.to_datetime(N["stated_declaration"])
    return N


def crsp_recover(decl: pd.DataFrame, alp: pd.DataFrame | None, sessions: pd.DatetimeIndex,
                 crsp_dir: Path = CRSP_DECL) -> tuple[pd.DataFrame, list, dict]:
    """Recover not-found declarations from CRSP `dsedist.dclrdt` (team lead's ruling, 2026-10-28).

    For each sponsor-table row with status `not_found`:
    - if CRSP holds a record for (ticker, exdt == ex_date), its earliest `dclrdt` becomes the
      declaration date, with source "CRSP dsedist";
    - R4 then applies: a declaration dated e-1 passes, a later one is "declared late".
    Every recovered event is cross-checked against Alpaca v1's record date (`rcrddt` against
    `record_date`). A disagreement is a flag (`X2_crsp_record_mismatch`) for a ruling, not a fix.
    The ex-date match is the join itself; no CRSP record on e leaves the row not found. Two CRSP
    records for one (ticker, exdt) with different record dates are flagged too. Dates only."""
    man_p = crsp_dir / "manifest.json"
    if not man_p.exists():
        return decl, [], {"status": "no CRSP extract"}
    man = json.loads(man_p.read_text())
    c = pd.read_parquet(crsp_dir / "crsp_dsedist_2023_2024.parquet")
    _only_names(c, "crsp dsedist")
    c = c[c.dclrdt.notna()]
    g = c.groupby(["ticker", "exdt"]).agg(dclrdt=("dclrdt", "min"), rcrddts=("rcrddt", lambda z: sorted(set(z.dropna()))))
    rec_alp = {}
    if alp is not None:
        a = alp[alp.kind.isin(["cash_dividends", "capital_gains_distributions"])]
        rec_alp = a.groupby(["ticker", "ex_date"])["record_date"].agg(lambda z: sorted(set(z.dropna()))).to_dict()
    spos = {d: i for i, d in enumerate(sessions)}
    out, flags = decl.copy(), []
    out["source"] = np.where(out.status == "not_found", "", "sponsor release")
    n = {"crsp_rows": int(len(c)), "attempted": 0, "recovered": 0, "recovered_late": 0, "no_crsp_row": 0,
         "record_mismatch": 0, "how": man.get("how"), "pulled_utc": man.get("source_pulled_utc") or man.get("written_utc")}
    for i, r in out[out.status == "not_found"].iterrows():
        if not (pd.Timestamp(r.ex_date) <= pd.Timestamp("2024-12-31")):
            continue
        n["attempted"] += 1
        k = (r.ticker, pd.Timestamp(r.ex_date))
        if k not in g.index:
            n["no_crsp_row"] += 1
            continue
        d0, rcs = g.loc[k, "dclrdt"], g.loc[k, "rcrddts"]
        prev = sessions[spos[k[1]] - 1] if k[1] in spos else None
        out.loc[i, ["declared", "source"]] = [d0, "CRSP dsedist dclrdt"]
        out.loc[i, "status"] = "declared_by_e_minus_1" if (prev is not None and d0 <= prev) else "declared_late"
        n["recovered" if out.loc[i, "status"] == "declared_by_e_minus_1" else "recovered_late"] += 1
        ar = rec_alp.get(k, [])
        if len(rcs) != 1 or (ar and [pd.Timestamp(x) for x in ar] != [pd.Timestamp(rcs[0])]):
            n["record_mismatch"] += 1
            flags.append((r.ticker, k[1], f"CRSP rcrddt {[str(pd.Timestamp(x).date()) for x in rcs]} vs Alpaca v1 "
                                          f"record {[str(pd.Timestamp(x).date()) for x in ar]}"))
    # Beside, never deciding: CRSP's dclrdt against the sponsor release date where both exist (2023-24).
    both = out[(out.source == "sponsor release") & (pd.to_datetime(out.ex_date) <= pd.Timestamp("2024-12-31"))]
    dd = [(pd.Timestamp(g.loc[(t, pd.Timestamp(e)), "dclrdt"]) - pd.Timestamp(d)).days
          for t, e, d in zip(both.ticker, both.ex_date, both.declared) if (t, pd.Timestamp(e)) in g.index]
    n["crsp_vs_release_where_both"] = {"events": len(dd), "same_day": int(sum(x == 0 for x in dd)),
                                       "within_1_day": int(sum(abs(x) <= 1 for x in dd)),
                                       "crsp_later": int(sum(x > 1 for x in dd)), "crsp_earlier": int(sum(x < -1 for x in dd))}
    return out, flags, n


def declaration_field_check(ann: pd.DataFrame, notices: pd.DataFrame) -> dict:
    """Is Alpaca's announcement `declaration_date` a declaration date? Dates only.

    Two measurements, printed: (i) weekdays from the announced declaration to the record date,
    over every announcement (a board declares days or weeks ahead; a field that sits inside the
    settlement window of the record date on almost every record is derived from it, not observed);
    (ii) each verified sponsor notice against Alpaca's value for the same (fund, ex-date). Any
    verified notice that contradicts the field shows that the field is not a declaration date, and
    DG-X2 then has no valid source on Alpaca alone."""
    a = ann[(ann.status == 200) & ann.ex_date.notna() & ann.declaration_date.notna() & ann.record_date.notna()]
    lead = pd.Series([int(np.busday_count(d.date(), r.date())) for d, r in zip(a.declaration_date, a.record_date)])
    m = notices.merge(a[["ticker", "ex_date", "declaration_date"]], on=["ticker", "ex_date"], how="left")
    agree = int((m.declaration_date == m.stated_declaration).sum())
    dis = m[m.declaration_date.notna() & (m.declaration_date != m.stated_declaration)]
    return {"announcements": int(len(a)),
            "record_minus_declaration_weekdays": {int(k): int(v) for k, v in lead.value_counts().sort_index().items()},
            "notices": int(len(m)), "notices_agree": agree, "notices_contradict": int(len(dis)),
            "contradictions": [f"{r.ticker} ex {r.ex_date.date()}: notice {r.stated_declaration.date()}, Alpaca "
                               f"{r.declaration_date.date()}" for r in dis.itertuples()]}


# =========================================================================== DG-X6: factor coverage (dates only)

def factor_coverage(window: pd.DatetimeIndex) -> tuple[list, dict]:
    """Every test-window session covered by the French six, IEF, HYG and MUB? Dates only."""
    rows, cov = [], {}
    srcs = {}
    if FF_DAILY.exists():
        f = pd.read_parquet(FF_DAILY, columns=["date"])
        srcs["French FF5+UMD (fetch_ff_factors.py)"] = ("FF6", set(pd.to_datetime(f["date"])))
    else:
        srcs["French FF5+UMD (fetch_ff_factors.py)"] = ("FF6", None)
    e = pd.read_parquet(ETF_DAILY, columns=["date", "ticker"], filters=[("ticker", "in", ["IEF", "HYG", "MUB"])])
    e["date"] = pd.to_datetime(e["date"])
    for s in ("IEF", "HYG", "MUB"):
        srcs[f"{s} in data/etf_daily.parquet"] = (s, set(e.loc[e.ticker == s, "date"]))
    for s, p in ETF_YF.items():
        srcs[f"{s} yfinance (fetch_exdrift_mub.py)"] = (s, set(pd.to_datetime(pd.read_parquet(p, columns=["date"])["date"]))
                                                        if p.exists() else None)
    for name, (sym, have) in srcs.items():
        if have is None:
            cov[name] = {"status": "not fetched"}
            continue
        miss = [d for d in window if d not in have]
        cov[name] = {"first": str(min(have).date()) if have else None, "last": str(max(have).date()) if have else None,
                     "missing_in_window": len(miss), "first_missing": str(miss[0].date()) if miss else None,
                     "last_missing": str(miss[-1].date()) if miss else None}
    # The D4 legs as the prereg names them: French six; IEF, HYG from etf_daily; MUB from this trial's fetcher.
    decide = {"FF6": "French FF5+UMD (fetch_ff_factors.py)", "IEF": "IEF in data/etf_daily.parquet",
              "HYG": "HYG in data/etf_daily.parquet", "MUB": "MUB yfinance (fetch_exdrift_mub.py)"}
    for sym, name in decide.items():
        c = cov[name]
        if c.get("status") == "not fetched":
            _flag(rows, f"X6_{sym}_not_fetched", sym, window[0], "DG-X6", "-", f"{name} is not in this checkout",
                  "fetch it (public)")
        elif c["missing_in_window"]:
            alt = {"IEF": cov.get("IEF yfinance (fetch_exdrift_mub.py)"), "HYG": cov.get("HYG yfinance (fetch_exdrift_mub.py)")}.get(sym)
            alt_s = (f"; the yfinance copy misses {alt['missing_in_window']}" if alt and "missing_in_window" in alt else "")
            _flag(rows, f"X6_{sym}_uncovered", sym, c["first_missing"], "DG-X6", "-",
                  f"{name} misses {c['missing_in_window']} test-window session(s), {c['first_missing']}..{c['last_missing']}"
                  + alt_s, "see reading R8" if sym == "FF6" else
                  "refresh data/etf_daily.parquet (its Alpaca leg needs the team lead's key) or rule the yfinance copy "
                  "for the uncovered sessions")
    return rows, cov


# =========================================================================== DG-X8

def numexpr_gate() -> dict:
    from scripts.events.numexpr_fault import run
    r = run()
    fault = any(v for v in r[True].values()) or any(v for v in r[False].values())
    off_ok = not any(v for v in r[False].values())
    return {"use_numexpr_option": pd.get_option("compute.use_numexpr"), "numexpr": r["numexpr"],
            "fault_with_numexpr_on": bool(any(v for v in r[True].values())), "numpy_path_clean": bool(off_ok),
            "fault_any": bool(fault),
            "status": "PASS" if (pd.get_option("compute.use_numexpr") is False and off_ok) else "FAIL"}


# =========================================================================== Stage 0

def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else None


def _status(gate: str, flags: pd.DataFrame, awaiting: bool, fail: str | None = None) -> str:
    if fail:
        return "FAIL"
    if awaiting:
        return "AWAITING TEAM LEAD"
    return "FLAGGED" if (flags["gate"] == gate).any() else "PASS"


def stage0(write: bool = True) -> dict:
    """Prereg §8. Every gate is reported; the run never stops at the first failure, except DG-X7."""
    out: list[str] = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    say(f"EXDRIFT STAGE 0 ({STAMP}; EVENTS trial 3, N = {N_BAR}; run {datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    say(f"spec {spec.SPEC_ID}; the 17: {', '.join(NAMES)}. 2023+: dates, counts, presence and flags only.")
    rec: dict = {"stamp": STAMP, "names": list(NAMES), "gates": {}}
    rows: list = []

    # ---------------------------------------------------------------- calendar
    sessions = sessions_calendar()
    last = sessions[-1]
    test_sess = sessions[sessions >= TEST_START]
    say(f"\nprice panel sessions (17): {sessions[0].date()}..{last.date()}; test {test_sess[0].date()}..{last.date()} "
        f"= {len(test_sess)} sessions")
    mm = nyse_mismatch(sessions, test_sess[0], last)
    say(f"  against ops/schedule/nyse_calendar.py: panel days NYSE closed {mm['panel_not_nyse'] or 'none'}; "
        f"NYSE sessions missing from the panel {mm['nyse_not_panel'] or 'none'}")
    for d in mm["panel_not_nyse"] + mm["nyse_not_panel"]:
        _flag(rows, "X0_calendar", "-", d, "DG-X4", "-", "panel session calendar differs from the NYSE calendar",
              "rule the session set positional offsets use")
    rec["calendar"] = {"first": str(sessions[0].date()), "last": str(last.date()), "test_sessions": int(len(test_sess)),
                       **mm}

    # ---------------------------------------------------------------- DG-X1: the refresh
    say("\n[DG-X1] distribution history, refreshed outside data/ (fetch_cef_distributions.py --out, 17 names)")
    if not DIST_REFRESH.exists():
        raise Stage0Error(f"{DIST_REFRESH} does not exist: run `python3 scripts/fetch_cef_distributions.py --out "
                          f"{REFRESH_DIR.relative_to(REPO)} --tickers {','.join(NAMES)}` (public; writes no data/ file)")
    dn = read_dist(DIST_REFRESH)
    do = read_dist(DIST_DATA)
    sp = pd.read_parquet(SPLITS_REFRESH) if SPLITS_REFRESH.exists() else pd.DataFrame(columns=["ticker", "ex_date", "stock_split"])
    sp["ex_date"] = pd.to_datetime(sp["ex_date"])
    sp = _only_names(sp, "splits")
    mt = datetime.fromtimestamp(DIST_REFRESH.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    M = do.merge(dn, on=["ticker", "ex_date"], how="outer", suffixes=("_data", "_ref"), indicator=True)
    fit_m = M[M.ex_date <= FIT_END]
    tst_m = M[M.ex_date >= TEST_START]
    same_fit = bool((fit_m._merge == "both").all() and (fit_m.amount_data - fit_m.amount_ref).abs().max() == 0)
    both_t = tst_m[tst_m._merge == "both"]
    overlap_same = bool((both_t.amount_data - both_t.amount_ref).abs().max() == 0) if len(both_t) else True
    dist_last = dn[dn.amount > 0].ex_date.max()
    say(f"  refreshed panel: {len(dn)} rows, last ex-date {dist_last.date()}, written {mt} (sha {_sha(DIST_REFRESH)})")
    say(f"  against data/cef/cef_distributions.parquet (yfinance, last ex-date {do.ex_date.max().date()}): fit rows "
        f"{'IDENTICAL' if same_fit else 'DIFFER'} ({int((fit_m._merge == 'both').sum())} in both, "
        f"{int((fit_m._merge != 'both').sum())} in one only); 2023+ overlap {len(both_t)} ex-dates "
        f"{'identical' if overlap_same else 'DIFFER'}; 2023+ only in data/ {int((tst_m._merge == 'left_only').sum())}, "
        f"only in the refresh {int((tst_m._merge == 'right_only').sum())}")
    end_ex = test_end(dist_last, sessions, last)
    say(f"  test set end (R7): earlier of the last ex-date {dist_last.date()} and the session 3 before {last.date()} "
        f"({sessions[sessions.get_loc(last) - HOLD].date()}) = {end_ex.date()}")
    say(f"  splits in the test window (refreshed splits panel): "
        f"{[(r.ticker, str(r.ex_date.date()), r.stock_split) for r in splits_in(sp, TEST_START, last).itertuples()] or 'none'}")
    rec["dg_x1_refresh"] = {"rows": int(len(dn)), "last_ex": str(dist_last.date()), "written_utc": mt,
                            "sha16": _sha(DIST_REFRESH), "fit_identical_to_data": same_fit,
                            "test_overlap_identical": overlap_same,
                            "test_only_in_refresh": int((tst_m._merge == "right_only").sum()),
                            "test_only_in_data": int((tst_m._merge == "left_only").sum()), "test_end_ex": str(end_ex.date())}

    ev, not_sess = test_events(dn, sessions, end_ex, sp)
    for r in not_sess.itertuples():
        _flag(rows, "X1_ex_not_session", r.ticker, r.ex_date, "DG-X1", str(r.ex_date.date()),
              "ex-date is not a panel session", "rule the session it maps to, or exclude and count")
    close_ok = _present(PRICES, "close", sessions, test="notna")
    vol_zero = _present(PRICES, "volume", sessions, test="zero")
    nav_ok = _present(NAVS, "nav", sessions, test="notna")
    nav_rep = _present(NAVS, "nav", sessions, test="repeat")
    ev["basket_calendar"] = calendar_baskets(ev, dn, sessions, close_ok, sp)
    E = ev[~ev.next_ex_within3 & ~ev.split_masked].copy()     # rules 2 and 3 exclude; counted
    ct_ref = count_table(ev, "refreshed panel, to the frozen end")
    ev_old, _ = test_events(do, sessions, test_end(do[do.amount > 0].ex_date.max(), sessions, last), sp)
    ev_old["basket_calendar"] = calendar_baskets(ev_old, do, sessions, close_ok, sp)
    ct_old = count_table(ev_old, "data/ panel, as §5.1 counted it")
    say("\n  §5.1's counts (dates only), re-measured beside the pre-registration's (H14: they decide nothing):")
    say("  | | events | on the 13 | dates | months | H-E >= 3 (calendar) | on the 13 |")
    say("  |---|---:|---:|---:|---:|---:|---:|")
    p_ = PREREG_TEST_COUNTS
    say(f"  | prereg §5.1 | {p_['events']} | {p_['events_13']} | {p_['dates']} | {p_['months']} | {p_['basket_ge3']} | {p_['basket_ge3_13']} |")
    for c in (ct_old, ct_ref):
        say(f"  | {c['label']} | {c['events']} | {c['events_13']} | {c['dates']} | {c['months']} | {c['basket_ge3']} | {c['basket_ge3_13']} |")
    say(f"  refreshed: by year {ct_ref['by_year']}; T+2 {ct_ref['T2']}, T+1 {ct_ref['T1']}; excluded by rule 2 "
        f"{ct_ref['excluded_next_ex_within3']}, by rule 3 (R1) {ct_ref['excluded_split_mask']}; ex-dates not a session "
        f"{len(not_sess)}")
    say("  (the §5.1 basket count used presence of an ex-date only; this one also needs a bar on e..e+3 and no "
        "split-masked row, so it can be lower)")
    rec["counts"] = {"prereg": PREREG_TEST_COUNTS, "data_panel": ct_old, "refreshed": ct_ref}

    # ---------------------------------------------------------------- DG-X1..X3: the second source
    have_v1 = ALPACA_DIVS.exists()
    have_ann = ALPACA_ANN.exists()
    alp = pd.read_parquet(ALPACA_DIVS) if have_v1 else None
    ann = pd.read_parquet(ALPACA_ANN) if have_ann else None
    if alp is not None:
        alp = _only_names(alp, ALPACA_DIVS.name)
        r1, s1 = yf_vs_alpaca(E, dn, alp, end_ex)
        rows += r1
        say(f"\n[DG-X1] second source, Alpaca v1 (fetched {alp['fetched_utc'].iloc[0] if len(alp) else '?'}): {s1}")
        mism = [r for r in r1 if r["check"] == "X1_amount_mismatch"]
        if mism:
            g = pd.DataFrame(mism).groupby("ticker")["date"].agg(["size", "min", "max"])
            say("  amount mismatches by fund (count, first, last ex-date): "
                + "; ".join(f"{t} {int(r['size'])} {r['min']}..{r['max']}" for t, r in g.iterrows()))
        r3, s3 = record_flags(E, alp, sessions)
        rows += r3
        say(f"[DG-X3] record dates and the regime arithmetic: {s3}")
        rec["dg_x1_second"], rec["dg_x3"] = s1, s3
    else:
        say(f"\n[DG-X1] second source: AWAITING TEAM LEAD. {ALPACA_DIVS.relative_to(REPO)} does not exist; the team "
            f"lead runs `{WRAPPER}` (fetch_exdrift_corp_actions.py, the cef paper key).")
        say("[DG-X3] record dates: AWAITING TEAM LEAD (same fetch).")
    ann_fail = None
    if ann is not None:
        st = ann.drop_duplicates(["window_symbol", "since"])["status"]
        if not (st == 200).any():
            ann_fail = (f"the announcements endpoint answered no window with 200 (statuses "
                        f"{sorted(set(int(x) for x in st))}): no declaration source")
            say(f"[DG-X2] FAIL: {ann_fail}")
        else:
            bad = int((st != 200).sum())
            if bad:
                ann_fail = f"{bad} announcement window(s) did not answer 200; their events have no declaration read"
            dchk = declaration_field_check(ann, verify_notices())
            say(f"[DG-X2] is Alpaca's declaration_date a declaration date? {dchk}")
            rec["dg_x2_field_check"] = dchk
            if dchk["notices_contradict"]:
                ann_fail = (f"Alpaca's announcement declaration_date is not a declaration date: "
                            f"{dchk['notices_contradict']} of {dchk['notices']} verified sponsor notice(s) contradict it, "
                            f"and it sits {dchk['record_minus_declaration_weekdays']} weekdays before the record date. "
                            "No valid declaration source; the per-event test below is printed, not flagged")
            r2, s2 = declaration_flags(E, ann, sessions)
            sup = " (superseded: the gate rests on the sponsor-release table below)" if SPONSOR_TABLE.exists() else ""
            say(f"[DG-X2] declaration dates on Alpaca's field{sup}: {s2}" + (f"\n  FAIL{sup}: {ann_fail}" if ann_fail else ""))
            late = [r for r in r2 if r["check"] == "X2_declared_late"]
            if late:
                g = pd.DataFrame(late).groupby("date")["ticker"].agg(lambda z: ",".join(sorted(z)))
                say(f"  events 'not declared by e-1' on Alpaca's field ({'printed only: the field is invalid' if ann_fail else 'excluded and counted, §4.1 rule 1'}): {len(late)}; by ex-date: "
                    + "; ".join(f"{d} {t}" for d, t in g.items()))
            s2["not_declared_by_e_minus_1"] = len(late)
            rec["dg_x2"] = s2
            if ann_fail:
                _flag(rows, "X2_source_invalid", "-", STAMP, "DG-X2", "-", ann_fail,
                      "rule a declaration source before the opening: a verified sponsor-notice table for every test "
                      "event (the sponsors' monthly releases; PIMCO's are fetchable), with CRSP dclrdt beside it to "
                      "2024-12-31 if wanted; the H-E declared calendar is rebuilt on it")
            else:
                rows += r2
    else:
        say("[DG-X2] declaration dates: AWAITING TEAM LEAD (same fetch; the deprecated announcements endpoint)")
    decl_cal = None
    if SPONSOR_TABLE.exists():
        from scripts.events import fetch_exdrift_sponsor_releases as sr
        decl = sr.verify()                                       # every quote re-found in its cached release
        decl, crsp_flags, crsp_n = crsp_recover(decl, alp, sessions)
        rec["dg_x2_crsp"] = crsp_n
        for t_, e_, note_ in crsp_flags:
            _flag(rows, "X2_crsp_record_mismatch", t_, e_, "DG-X2", str(pd.Timestamp(e_).date()), note_,
                  "rule whether the CRSP declaration stands for this event")
        say(f"\n[DG-X2] declarations from the sponsors' own releases ({SPONSOR_TABLE.name}; the team lead's ruling "
            f"of 2026-10-28): every quote re-found offline")
        say(f"  not-found events recovered from CRSP dsedist.dclrdt (ruling of 2026-10-28, 2023-24 only): {crsp_n}")
        found = decl[decl.status != "not_found"]
        if ann is not None:
            dchk2 = declaration_field_check(ann, found.rename(columns={"declared": "stated_declaration"})[
                ["ticker", "ex_date", "stated_declaration"]])
            say(f"  Alpaca's declaration_date against the sponsor table: {dchk2['notices_agree']} agree, "
                f"{dchk2['notices_contradict']} contradict, of {dchk2['notices']}")
            rec["dg_x2_alpaca_vs_sponsor"] = {k: v for k, v in dchk2.items() if k != "contradictions"}
        ek = set(zip(E.ticker, E.ex_date))
        d_e = decl[[k in ek for k in zip(decl.ticker, decl.ex_date)]]
        for r in d_e.itertuples():
            if r.status == "not_found":
                _flag(rows, "X2_not_found", r.ticker, r.ex_date, "DG-X2", str(r.ex_date.date()),
                      "no sponsor release found that declares this distribution",
                      "excluded and counted (the team lead's ruling of 2026-10-28: never guessed)")
            elif r.status == "declared_late":
                _flag(rows, "X2_declared_late", r.ticker, r.ex_date, "DG-X2", str(r.ex_date.date()),
                      f"the earliest release declaring it is dated {r.declared.date()}, after e-1",
                      "excluded and counted (§4.1 rule 1)")
        cov = (d_e.assign(col=np.where(d_e.status == "declared_by_e_minus_1",
                                        np.where(d_e.source == "CRSP dsedist dclrdt", "by_e-1_crsp", "by_e-1_release"),
                                        d_e.status))
               .groupby(["sponsor", "col"]).size().unstack(fill_value=0)
               .reindex(columns=["by_e-1_release", "by_e-1_crsp", "declared_late", "not_found"], fill_value=0))
        say("  coverage of the test events by sponsor:\n" + "\n".join("    " + l for l in cov.to_string().split("\n")))
        ok_ = d_e[d_e.status == "declared_by_e_minus_1"]
        lead = [sessions.get_loc(e) - sessions.searchsorted(d) for e, d in zip(ok_.ex_date, ok_.declared)]
        s2 = {"events": int(len(d_e)), "declared_by_e_minus_1": int(len(ok_)),
              "of_which_from_crsp": int((ok_.source == "CRSP dsedist dclrdt").sum()),
              "declared_on_e_minus_1": int(sum(x == 1 for x in lead)), "declared_by_e_minus_2": int(sum(x >= 2 for x in lead)),
              "not_found": int((d_e.status == "not_found").sum()), "declared_late": int((d_e.status == "declared_late").sum()),
              "lead_sessions_min_median_max": [int(min(lead)), float(np.median(lead)), int(max(lead))] if lead else None,
              "by_sponsor": {sp_: {k: int(v) for k, v in row.items()} for sp_, row in cov.iterrows()},
              "releases": int(decl.url.nunique())}
        say(f"  {s2}")
        rec["dg_x2"] = s2
        ann_fail = None                                          # the gate rests on the sponsor table
        rows = [r for r in rows if r["check"] != "X2_source_invalid"]
        if write:
            decl[["ticker", "ex_date", "sponsor", "status", "declared", "source"]].to_csv(DECL_FINAL, index=False)
        decl_cal = decl[["ticker", "ex_date", "declared"]].rename(columns={"declared": "declaration_date"}).assign(
            status=200)                                          # not-found ex-dates carry NaT: never "declared"

    # ---------------------------------------------------------------- DG-X4, DG-X5
    alp_bars = pd.read_parquet(ALPACA_BARS) if ALPACA_BARS.exists() else None
    rows += bar_flags(E, sessions, close_ok, vol_zero, alp_bars)
    gr, gs = bar_guard_flags(sessions, sp)
    rows += gr
    for r in splits_in(sp, TEST_START, last).itertuples():
        cls = split_basis_class(float(r.stock_split))
        _flag(rows, "X4_split", r.ticker, r.ex_date, "DG-X4", "-",
              f"recorded split factor {r.stock_split:g} in the test window; split-basis class from the factor alone: {cls}"
              + (" (|ln k| <= 2 tau: the guard cannot raise here)" if cls == "undecidable" else ""),
              "rule 3 (R1) masks the fund's returns within +-5 sessions, so no event or basket leg books it; confirm "
              "the factor is not a share-basis change of the close")
    n4 = sum(1 for r in rows if r["gate"] == "DG-X4")
    xb_rows, xb = x4_basis_check(sessions)
    rows += xb_rows
    rec["x4_basis_check_O4"] = xb
    say(f"  O4 basis check of the X4 fills (Alpaca vs yfinance on e-1 and e+1, within $0.01; presence and basis only): {xb}")
    mc = missing_close_cells(close_ok, test_sess, dn)
    say(f"  every missing close in the 17's test-window panel: {mc['cells']} cell(s), {mc['on_own_ex_date']} of them on "
        f"the fund's own ex-date; dates {mc['dates']}")
    rec["missing_close_cells"] = mc
    say(f"\n[DG-X4] bars: event-fund bars on e..e+3 and fill-day volume; the spike-and-revert guard ({gs}); "
        f"{n4} flag(s)")
    rows += nav_flags(E, sessions, nav_ok, nav_rep)
    rt = repeat_rate_test(E, sessions, nav_ok, nav_rep)
    rb = repeat_rate_test(E, sessions, nav_ok, nav_rep, basket=True)
    rf = repeat_rate_fit(read_fit(DIST_DATA, ["ticker", "ex_date", "amount"], date_col="ex_date"))
    say(f"[DG-X5] NAV on e..e+3: {sum(1 for r in rows if r['check'] == 'X5_nav_missing')} missing cell flag(s); "
        f"repeats on e+1..e+3: event funds {rt['repeats']} of {rt['cells']} ({rt['rate']:.3f}); fit, same rows "
        f"{rf['repeats']} of {rf['cells']} ({rf['rate']:.3f}); basket funds in the test {rb['repeats']} of {rb['cells']} "
        f"({rb['rate']:.3f}, counted, not flagged: R6)")
    say(f"  repeat rate by fit era {rf['by_era']}; by test year, event funds {rt['by_year']}, basket funds {rb['by_year']}")
    n_e = sum(1 for r in rows if r["check"] == "X5_nav_repeat_on_e")
    say(f"  NAV(e) = NAV(e-1) on the ex-date itself (a stale cum-distribution NAV): test {n_e} of {len(E)} events; "
        f"fit {rf['on_e']['repeats']} of {rf['on_e']['cells']} ({rf['on_e']['rate']:.4f})")
    rec["dg_x4_guard"] = gs
    rec["dg_x5"] = {"test_event_rows": rt, "fit_event_rows": rf, "test_basket_rows": rb}

    # ---------------------------------------------------------------- the eligible set, by ruling (dates only)
    filled = close_ok.copy()                                     # the X4 ruling: the 24 cells filled from Alpaca
    if alp_bars is not None and len(alp_bars):
        for t, d, c in zip(alp_bars.ticker, pd.to_datetime(alp_bars.date), alp_bars.close):
            if t in filled.columns and d in filled.index and np.isfinite(c) and c > 0:
                filled.at[d, t] = True                           # presence only: a bar exists, as ruled
    nobar_ev = {(t, e) for t, e, p in zip(E.ticker, E.ex_date, E.p)
                if not close_ok.reindex(index=sessions, columns=list(NAMES)).fillna(False).iloc[p:p + HOLD + 1][t].all()}
    excl2 = {(r["ticker"], pd.Timestamp(r["date"])) for r in rows if r["check"] in ("X2_not_found", "X2_declared_late")}
    elig = {}
    for lab, ok_, drop, unk in (("as ruled: X4 cells filled; no-declaration basket legs KEPT (R10, team lead 2026-10-28)",
                                 filled, False, "keep"),
                                ("beside: no-declaration basket legs excluded", filled, False, "exclude"),
                                ("beside: X4 cells not filled", close_ok, True, "keep")):
        if decl_cal is not None:
            nb, surpr = declared_baskets(E, decl_cal, sessions, ok_, sp, unknown=unk)
        else:
            nb, surpr = calendar_baskets(E, dn, sessions, ok_, sp), None
        keep = pd.Series([(t, e) not in excl2 and not (drop and (t, e) in nobar_ev)
                          and sessions[p + HOLD] <= O1_END                      # O1 as ruled: e+3 on or before 2026-10-09
                          for t, e, p in zip(E.ticker, E.ex_date, E.p)], index=E.index)
        k3 = keep & (nb >= BASKET_MIN)
        elig[lab] = {"events": int(k3.sum()), "events_13": int((k3 & E.ticker.isin(CORE)).sum()),
                     "dates": int(E.loc[k3, "ex_date"].nunique()),
                     "months": int(E.loc[k3, "ex_date"].dt.to_period("M").nunique()),
                     "excluded_declaration": int(sum((t, e) in excl2 for t, e in zip(E.ticker, E.ex_date))),
                     "excluded_no_bar": int(sum(drop and (t, e) in nobar_ev and (t, e) not in excl2
                                                for t, e in zip(E.ticker, E.ex_date))),
                     "basket_lt3": int((keep & (nb < BASKET_MIN)).sum()), "calendar_surprise_legs": surpr}
    cal_lab = "DECLARED calendar (sponsor releases)" if decl_cal is not None else "REALISED calendar (no declaration source)"
    say(f"\n  the eligible set on the {cal_lab}, rules 1-5 (dates only):")
    for lab, v in elig.items():
        say(f"    {lab}: {v}")
    rec["eligible"] = elig

    # ---------------------------------------------------------------- DG-X6
    p_last = int(E.p.max()) if len(E) else None
    window = sessions[int(E.p.min()) + 1:p_last + HOLD + 1] if len(E) else sessions[0:0]
    r6_, cov = factor_coverage(window)
    rows += r6_
    say(f"\n[DG-X6] factor coverage on the test window {window[0].date()}..{window[-1].date()} ({len(window)} sessions):")
    for k, v in cov.items():
        say(f"  {k}: {v}")
    rec["dg_x6"] = cov
    rec["factor_window"] = [str(window[0].date()), str(window[-1].date())] if len(window) else None

    # ---------------------------------------------------------------- DG-X7 (stops the run if it fails)
    say("\n[DG-X7] identity gate, fit 2005-01-01..2022-12-30 only (published figures, reproduced)")
    ig = identity_gate(DIST_DATA)
    ig_ref = identity_gate(DIST_REFRESH) if not same_fit else None
    T = ig["table"]
    for r in T.itertuples():
        say(f"  {r.figure:<28} reproduced {r.reproduced:>10.4f}  published {r.published:>9}  tol {r.tolerance:<6} "
            f"{'PASS' if r.ok else 'FAIL'}")
    say(f"  beside (not gated): {ig['beside']}")
    say(f"  on the refreshed panel's fit rows: {'identical rows, so the same result' if same_fit else ig_ref['pass']}")
    rec["dg_x7"] = {"table": T.to_dict("records"), "beside": ig["beside"], "pass": ig["pass"],
                    "k_and_cap_share": "not formed (reading R9)"}
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        T.assign(source=["r6 check_credit.py via prereg_inputs.py"] * 3 + ["prereg_inputs_b3.py"]).to_csv(FIT_TABLE, index=False)
    if not ig["pass"]:
        raise IdentityGateFailure(f"DG-X7: {T[~T['ok']]['figure'].tolist()} did not reproduce; stop and report")

    # ---------------------------------------------------------------- DG-X8
    nx = numexpr_gate()
    say(f"\n[DG-X8] numexpr: {nx}")
    rec["dg_x8"] = nx

    # ---------------------------------------------------------------- readings, flags, statuses
    for code, gate, text, recm in READINGS:
        _flag(rows, code, "-", STAMP, gate, "-", text, recm)
    F = pd.DataFrame(rows, columns=FLAG_COLUMNS)
    agg = (F.groupby(["check", "ticker", "date"], as_index=False)
           .agg(gate=("gate", "first"), events=("events", lambda s: "; ".join(dict.fromkeys(s))),
                note=("note", "first"), recommended=("recommended", "first")))
    F = agg[FLAG_COLUMNS].sort_values(["gate", "check", "ticker", "date"]).reset_index(drop=True)
    st = {
        "DG-X1": _status("DG-X1", F[~F.check.str.startswith("R")], not have_v1),
        "DG-X2": _status("DG-X2", F[~F.check.str.startswith("R")], not have_ann, ann_fail),
        "DG-X3": _status("DG-X3", F[~F.check.str.startswith("R")], not have_v1),
        "DG-X4": _status("DG-X4", F[~F.check.str.startswith("R")], False),
        "DG-X5": _status("DG-X5", F[~F.check.str.startswith("R")], False),
        "DG-X6": _status("DG-X6", F[~F.check.str.startswith("R")], False),
        "DG-X7": "PASS (identity; k committed by fit-k)" if K_JSON.exists() else "IDENTITY PASS; k PENDING (R9)",
        "DG-X8": nx["status"],
    }
    rec["gates"] = st
    rec["flags_by_check"] = {k: int(v) for k, v in F.groupby("check").size().items()}
    rec["flags"] = int(len(F))
    gates_ok = all(v in ("PASS", "FLAGGED") for k, v in st.items() if k != "DG-X7")
    try:
        dg.require_stage0_rulings(F, RULINGS, context="exdrift Stage 0")
        ruled = True
    except dg.Stage0BlockError:
        ruled = False
    rec["all_flags_ruled"] = ruled
    rec["k_committed"] = K_JSON.exists()
    # CLEAR = every gate passes or is flagged with every flag ruled. k is fit-k's output and `open`'s
    # precondition, not a data gate; so is the X6 ruling's wait for French's next vintage, which
    # `open` re-measures (`open_preconditions`).
    rec["stage0"] = "CLEAR" if (gates_ok and ruled) else "HALTED"
    say("\nGATES: " + "; ".join(f"{k} {v}" for k, v in st.items()))
    say(f"FLAGS: {len(F)} -> {FLAGS.relative_to(REPO)} " + json.dumps(rec["flags_by_check"]))
    say(f"STAGE 0: {rec['stage0']}. No 2023+ return, P&L, price change or NAV change was computed.")
    if write:
        F.to_csv(FLAGS, index=False)
        if RULINGS.exists() and _blank_form(RULINGS):
            RULINGS.unlink()                  # a form with no ruling in it is not a record; the flags may have changed
        if not RULINGS.exists() and len(F):
            dg.stage0_rulings_template(F, RULINGS)
            say(f"rulings form (blank) -> {RULINGS.relative_to(REPO)}")
        elif RULINGS.exists():
            say(f"rulings file exists with rulings in it ({RULINGS.relative_to(REPO)}); never overwritten")
        rec["input_pins_sha256"] = {k_: (hashlib.sha256(v.read_bytes()).hexdigest() if v.exists() else None)
                                    for k_, v in PINNED.items()}
        STAGE0_JSON.write_text(json.dumps(_jsonable(rec), indent=1, sort_keys=True))
        STAGE0_TXT.write_text("\n".join(out) + "\n")
    return {"rec": rec, "flags": F, "events": E}


def _blank_form(p: Path) -> bool:
    """True when the rulings file holds no ruling at all (every ruling column empty)."""
    R = pd.read_csv(p, dtype=str, keep_default_na=False)
    cols = [c for c in dg.STAGE0_RULING_COLUMNS if c in R.columns]
    return bool(cols) and bool((R[cols].apply(lambda c: c.str.strip()) == "").all().all())


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    return o


# =========================================================================== the block, and the later stages

def _committed(paths, check_git: bool = True) -> None:
    """The Stage-0 record a later stage reads must be committed: a working-tree edit is not a record."""
    if not check_git:
        return
    for p in paths:
        r = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", str(p)], capture_output=True, text=True)
        if r.returncode != 0 or r.stdout.strip():
            raise dg.Stage0BlockError(f"{p.relative_to(REPO)} is not committed as it stands; commit the Stage-0 record first")


def require_stage0_rulings_only(flags_path: Path = FLAGS, rulings_path: Path = RULINGS, *, check_git: bool = True):
    """Every Stage-0 flag has a recorded ruling (data_guards.require_stage0_rulings). `fit-k` needs this."""
    if not Path(flags_path).exists():
        raise dg.Stage0BlockError(f"{flags_path} does not exist: run `exdrift_trial.py stage0` first")
    _committed([Path(flags_path), Path(rulings_path)] if Path(rulings_path).exists() else [Path(flags_path)], check_git)
    F = pd.read_csv(flags_path, dtype=str, keep_default_na=False)
    return dg.require_stage0_rulings(F, rulings_path, context="exdrift Stage 0")


def require_stage0_clear(flags_path: Path = FLAGS, rulings_path: Path = RULINGS, record: Path = STAGE0_JSON,
                         k_path: Path = K_JSON, *, check_git: bool = True):
    """`open` needs: every flag ruled, the committed record saying CLEAR, and a committed k."""
    J = require_stage0_rulings_only(flags_path, rulings_path, check_git=check_git)
    if not Path(record).exists():
        raise dg.Stage0BlockError(f"{record} does not exist")
    _committed([Path(record)], check_git)
    rec = json.loads(Path(record).read_text())
    if rec.get("stage0") != "CLEAR":
        raise dg.Stage0BlockError(f"the Stage-0 record says {rec.get('stage0')!r}, not 'CLEAR': {rec.get('gates')}")
    if not Path(k_path).exists():
        raise dg.Stage0BlockError(f"{k_path} does not exist: k and the cap-binding share are committed by `fit-k` "
                                  "before the test set opens (prereg §4.4)")
    _committed([Path(k_path)], check_git)
    pre = open_preconditions(rec)
    if pre:
        raise dg.Stage0BlockError("open's preconditions are not met: " + "; ".join(pre))
    return J


def open_preconditions(rec: dict) -> list[str]:
    """What the rulings themselves make `open` wait for, re-measured now (H14: no number from a document).
    The X6 ruling (team lead 2026-10-28): wait for a French vintage that covers the test window."""
    out = []
    w = rec.get("dg_x6", {}).get("French FF5+UMD (fetch_ff_factors.py)", {})
    lo_hi = rec.get("factor_window")
    if lo_hi and FF_DAILY.exists():
        f = pd.to_datetime(pd.read_parquet(FF_DAILY, columns=["date"])["date"])
        win = sessions_calendar()
        win = win[(win >= pd.Timestamp(lo_hi[0])) & (win <= pd.Timestamp(lo_hi[1]))]
        miss = [d for d in win if d not in set(f)]
        if miss:
            out.append(f"French FF5+UMD miss {len(miss)} test-window session(s) from {miss[0].date()} (X6 ruling: wait "
                       "for the next vintage; `python3 scripts/data/fetch_ff_factors.py`)")
    elif w.get("missing_in_window"):
        out.append("French FF5+UMD coverage cannot be re-measured")
    return out


# --------------------------------------------------------------------------- the team lead's rulings (2026-10-28)
TL_RULING = ("Accept all: every recommended ruling in rows 2-17 [of EXDRIFT_STAGE0_RULINGS_PROPOSAL_2026-10-28.md], "
             "including the go on fit-k (R9). Declarations (row 1): sponsor releases. Build a verified declaration "
             "table from the sponsors' own monthly distribution releases (PIMCO, BlackRock, Nuveen, DoubleLine, "
             "AllianceBernstein) for every test event. Keep each quote, its URL and fetch time, so it can be re-checked. "
             "A fund or event whose release cannot be found is excluded and counted, never guessed.")
RULED_BY, RULED_ON = "team lead", "2026-10-28"
CLASS_RULINGS = {
    "X1_amount_mismatch": "keep the event: its ex-date is confirmed by both sources; Alpaca's amount is used in the "
                          "report-only size strata (proposal #2)",
    "X2_not_found": "excluded and counted: no sponsor release found, never guessed (row 1)",
    "X2_declared_late": "excluded and counted: declared after e-1 (rule 1, R4; row 1)",
    "X4_no_bar": "fill the close from Alpaca's raw SIP bar, logged per cell; the adjacent bars are checked on one "
                 "share basis at the opening (proposal #4)",
    "X4_split": "keep rule 3 (R1): BIT's returns masked within +-5 sessions; the factor is yfinance-only (proposal #5)",
    "X5_nav_repeat_on_e": "exclude the event from the NAV leg only, counted (proposal #6)",
    "X5_nav_repeat@12": "book as is: a repeat on e+1 or e+2 leaves the three-row NAV sum unchanged to first order "
                        "(proposal #7)",
    "X5_nav_repeat@3": "exclude the event from the NAV leg only, counted: a stale NAV(e+3) truncates the window "
                       "(proposal #7)",
    "X6_FF6_uncovered": "wait for French's 202610 vintage before the opening; `open` re-measures the coverage "
                        "(proposal #8)",
    "R1": "keep (proposal #9)", "R2": "keep (proposal #10)", "R3": "keep (proposal #11)",
    "R4": "keep, applied to the sponsor-release table (proposal #12)", "R5": "keep (proposal #13)",
    "R6": "superseded by the X5 rulings by position (proposal #14)", "R7": "keep (proposal #15)",
    "R8": "as X6: wait for the 202610 vintage (proposal #16)", "R9": "fit-k authorised (proposal #17)",
    "R10": "KEEP (team lead, 2026-10-28): a basket fund with no declaration found stays in the basket. Stated "
           "limitation, named in the opening's report: the hedge basket's exclusion window uses ex-dates that may "
           "not have been public at decide time",
    "X2_crsp_record_mismatch": "UNRULED: needs the team lead",
    "X4_basis_mismatch": "UNRULED: needs the team lead",
}


def ruling_for(check: str, events: str) -> str:
    """The class ruling for one flag. A class with no ruling raises: nothing is ruled by default."""
    if check == "X5_nav_repeat":
        pos = set(re.findall(r"\(e\+(\d)\)", events or ""))
        if pos and pos <= {"1", "2"}:
            return CLASS_RULINGS["X5_nav_repeat@12"]
        if pos == {"3"}:
            return CLASS_RULINGS["X5_nav_repeat@3"]
        raise Stage0Error(f"X5_nav_repeat with hold positions {sorted(pos)}: no class ruling covers it")
    if check not in CLASS_RULINGS:
        raise Stage0Error(f"flag class {check!r} has no ruling from the team lead")
    return CLASS_RULINGS[check]


def apply_rulings(flags_path: Path = FLAGS, rulings_path: Path = RULINGS, supersede=()) -> pd.DataFrame:
    """Write the team lead's class rulings into the rulings file, one row per flag.

    A flag that is in both the old file and the flag table keeps its ruling. Changing it raises,
    unless its class is in `supersede`, meaning the team lead re-ruled that class (R10 on 2026-10-28).
    A row whose flag Stage 0 no longer raises is dropped; `require_stage0_rulings` would refuse it
    as stale. A new flag takes its class ruling. A class with no ruling raises (`ruling_for`), and
    so does a ruling text marked UNRULED."""
    F = pd.read_csv(flags_path, dtype=str, keep_default_na=False)
    R = F[["check", "ticker", "date"]].copy()
    R["ruling"] = [ruling_for(c, e) for c, e in zip(F["check"], F["events"])]
    un = R[R.ruling.str.startswith("UNRULED")]
    if len(un):
        raise dg.Stage0BlockError(f"{len(un)} flag(s) await the team lead: {un[['check', 'ticker', 'date']].values.tolist()[:8]}")
    R["ruled_by"], R["ruled_on"] = RULED_BY, RULED_ON
    p = Path(rulings_path)
    if p.exists() and not _blank_form(p):
        old = pd.read_csv(p, dtype=str, keep_default_na=False)
        m = R.merge(old, on=["check", "ticker", "date"], how="inner", suffixes=("", "_old"))
        changed = m[(m.ruling != m.ruling_old) & ~m.check.isin(list(supersede))]
        if len(changed):
            raise dg.Stage0BlockError(f"{p.name}: {len(changed)} existing ruling(s) would change "
                                      f"({changed.check.unique().tolist()}); it is not rewritten")
        keep_old = m[~m.check.isin(list(supersede))][["check", "ticker", "date", "ruling_old", "ruled_by_old", "ruled_on_old"]]
        keep_old.columns = ["check", "ticker", "date", "ruling", "ruled_by", "ruled_on"]
        rest = R.merge(keep_old[["check", "ticker", "date"]], on=["check", "ticker", "date"], how="left", indicator=True)
        rest = rest[rest._merge == "left_only"].drop(columns="_merge")
        R = pd.concat([keep_old, rest], ignore_index=True)
    R = R.sort_values(["check", "ticker", "date"]).reset_index(drop=True)
    R.to_csv(p, index=False)
    return R


# --------------------------------------------------------------------------- fit-k (fit P&L only)

def fit_k_core(ret: pd.DataFrame, dist: pd.DataFrame, cap: float, vol_target: float) -> dict:
    """k and the cap-binding share of the raw H-E sleeve on the fit (prereg §4.4). Fit rows only.

    The raw sleeve: per eligible fit event, $1 short of the fund and $1 long of its H-E basket
    (equal weights), decided on rows e-1, e and e+1, so `evaluate()`'s shift(2) earns rows e+1..e+3.
    Built by `band_frontier.event_hold` (the fit has no declaration dates, so each leg's `ann` is
    e-1, the latest date R4 passes; the fill at e's close is asserted after it) and scored by
    `band_frontier.evaluate`. Eligibility as declared: rule 2 (no other own ex-date in (e, e+3]),
    rule 4 (finite returns on the hold rows, asserted on every held cell) and rule 5 (a basket of
    at least 3). sigma_active is the annualised sd of the daily P&L on sessions with an event held;
    k = vol_target / sigma_active. The cap share is the share of decision rows with a position on
    which `_cap_gross(k * H_t, cap)` binds. No mean, Sharpe or t is formed."""
    from scripts.cef.band_frontier import evaluate, event_hold
    from src.deploy.sleeves.cef_discount import _cap_gross
    if ret.index.max() > FIT_END:
        raise Stage0Error("fit_k_core was handed a row after FIT_END")
    E = he_events(ret, dist)
    E = E.dropna(subset=["he"]).copy()
    idx = ret.index
    pos = {d: i for i, d in enumerate(idx)}
    own = {t: sorted(pos[d] for d in g.ex_date if d in pos) for t, g in dist[dist.amount > 0].groupby("ticker")}
    E["next3"] = [any(p < q <= p + NEXT_EX_WITHIN for q in own.get(t, [])) for t, p in zip(E.ticker, E.p)]
    n_rule2 = int(E.next3.sum())
    E = E[~E.next3]
    legs = []
    for r in E.itertuples():
        f0, l0, a0 = idx[r.p - 1], idx[r.p + 1], idx[r.p - 1]
        legs.append(dict(permno=r.ticker, first=f0, last=l0, weight=-1.0, ann=a0))
        b = r.basket.split(",")
        for j in b:
            legs.append(dict(permno=j, first=f0, last=l0, weight=1.0 / len(b), ann=a0))
    H = event_hold(pd.DataFrame(legs), idx)
    R = ret.reindex(columns=H.columns)
    held = H.shift(2).fillna(0.0).to_numpy() != 0
    if not np.isfinite(R.to_numpy()[held]).all():
        raise Stage0Error("a held fit cell has no return: evaluate() would book it as 0")
    res = evaluate(H, R.fillna(0.0))
    pnl = res["pnl"]
    assert_denormal_free(pnl)
    if abs(float(pnl.sum()) - float(E.he.sum())) > 1e-9:
        raise Stage0Error("per-event P&Ls do not sum to evaluate()'s P&L: the legs are mis-built")
    active = pd.Series(held.any(axis=1), index=idx)
    sigma = float(pnl[active].std(ddof=1) * np.sqrt(252))
    k = vol_target / sigma
    rows_on = H.abs().sum(axis=1) > 0
    bind = 0
    for t in H.index[rows_on]:
        _, fct = _cap_gross(k * H.loc[t], cap)
        bind += int(fct < 1.0)
    n_on = int(rows_on.sum())
    return {"events": int(len(E)), "excluded_rule2": n_rule2,
            "active_sessions": int(active.sum()), "decision_rows_with_a_position": n_on,
            "sigma_active_annual": sigma, "vol_target": vol_target, "k": k, "cap": cap,
            "cap_binding_rows": bind, "cap_binding_share": bind / n_on if n_on else float("nan"),
            "first_active": str(idx[active.to_numpy()][0].date()), "last_active": str(idx[active.to_numpy()][-1].date())}


D4_FACTORS = ("mktrf", "smb", "hml", "rmw", "cma", "umd", "TERM", "HY", "MUNI")


def hedge_betas_core(R: pd.DataFrame, F: pd.DataFrame) -> dict:
    """Amendment 1: each fund's MUNI and TERM betas in STAGE 5's OWN factor model, from the fit only.

    r_i,t = a + sum over the nine D4 factors f of (b_f0 f_t + b_f1 f_{t-1}) + e, one OLS per fund.
    These are the factors R-D4 uses: French six, TERM = IEF - RF, HY = HYG - IEF, MUNI = MUB - IEF.
    The lags are summed, as R-D4 sums them. The rows are the fund's own finite returns after r6's
    masks, with every regressor present. All nine summed betas are recorded; only MUNI and TERM are
    hedged.

    WHY THIS MODEL. The hedge exists to remove what stage 5 measures, so its betas are stage 5's
    partial betas. A first derivation regressed each fund on MUB and IEF alone, and was disclosed in
    amendment 1. It omitted the factors stage 5 controls for, HY above all, so its MUB beta absorbed
    credit exposure (every fund about +1.0 to +2.4). On the fit rehearsal it left MUNI at -0.41.

    This is ONE declared specification, derived from the test it serves and not swept. The point
    estimates are frozen; the opening never re-estimates them."""
    cols = list(D4_FACTORS)
    X = pd.concat([F[cols], F[cols].shift(1).add_suffix("_l1")], axis=1)
    out = {}
    for t in R.columns:
        d = pd.concat([R[t].rename("y"), X], axis=1).dropna()
        if len(d) < 252:                     # one year of sessions at least (PDO listed in 2021: 483 fit rows)
            raise Stage0Error(f"hedge betas: {t} has only {len(d)} fit rows with every factor")
        A = np.column_stack([np.ones(len(d)), d[cols + [c + "_l1" for c in cols]].to_numpy()])
        b, *_ = np.linalg.lstsq(A, d["y"].to_numpy(), rcond=None)
        summed = {c: float(b[1 + i] + b[1 + len(cols) + i]) for i, c in enumerate(cols)}
        out[t] = {"beta_MUNI": summed["MUNI"], "beta_TERM": summed["TERM"], "all_summed": summed,
                  "rows": int(len(d)), "first": str(d.index[0].date()), "last": str(d.index[-1].date())}
    return out


def hedge_weights(t: str, basket: list, betas: dict) -> tuple[float, float]:
    """Positions in MUB and IEF per $1 event unit ($1 short of t, $1 long of the basket equally).

    The event's exposure is E_f = -beta_t,f + mean(beta_basket,f), for f = MUNI and TERM. Since
    MUNI = MUB - IEF and TERM = IEF - RF, holding h_MUB of MUB and h_IEF of IEF adds h_MUB to MUNI
    and h_MUB + h_IEF to TERM. HY (= HYG - IEF) is untouched. So the offsetting hedge is
    h_MUB = -E_MUNI and h_IEF = E_MUNI - E_TERM."""
    eM = -betas[t]["beta_MUNI"] + float(np.mean([betas[j]["beta_MUNI"] for j in basket]))
    eT = -betas[t]["beta_TERM"] + float(np.mean([betas[j]["beta_TERM"] for j in basket]))
    return -eM, eM - eT


def amend1_betas(args) -> int:
    """Estimate and freeze amendment 1's betas on the FIT window (2007-09-11 .. 2022-12-30)."""
    from scripts.events.exdrift_open import _factors
    px = read_fit(PRICES, ["date", "ticker", "close"])
    close = px.pivot(index="date", columns="ticker", values="close").sort_index()
    dist = read_fit(DIST_REFRESH, ["ticker", "ex_date", "amount", "stock_split"], date_col="ex_date")
    ret = fit_returns(close, dist)
    ff = pd.read_parquet(FF_DAILY, filters=[("date", "<=", FIT_END)])
    etf = pd.read_parquet(ETF_DAILY, columns=["date", "ticker", "ret_total"],
                          filters=[("ticker", "in", ["IEF", "HYG"]), ("date", "<=", FIT_END)])
    mub = pd.read_parquet(ETF_YF["MUB"], filters=[("date", "<=", FIT_END)])
    for f_ in (ff, etf, mub):
        f_["date"] = pd.to_datetime(f_["date"])
        assert f_["date"].max() <= FIT_END
    F = _factors(ff, etf, mub)
    idx = ret.index[(ret.index >= HEDGE_FIT_LO) & (ret.index <= FIT_END)]
    b = hedge_betas_core(ret.loc[idx, list(NAMES)], F.reindex(idx))
    out = {"stamp": "2026-10-28", "window": f"{HEDGE_FIT_LO.date()}..{FIT_END.date()} (fit only)",
           "spec": "per fund OLS of its r6 total return on the nine R-D4 factors at t and t-1, lags summed; "
                   "MUNI and TERM hedged with MUB and IEF (h_MUB = -E_MUNI, h_IEF = E_MUNI - E_TERM)",
           "sources": "data/cef panels (yfinance); French FF5+UMD (fetch_ff_factors.py); IEF, HYG data/etf_daily.parquet; "
                      "MUB yfinance (fetch_exdrift_mub.py)",
           "betas": b}
    HEDGE_JSON.write_text(json.dumps(out, indent=1, sort_keys=True))
    for t, v in b.items():
        print(f"{t}: beta_MUNI {v['beta_MUNI']:+.3f}  beta_TERM {v['beta_TERM']:+.3f}  HY {v['all_summed']['HY']:+.3f}  ({v['rows']} rows)")
    print(f"-> {HEDGE_JSON.relative_to(REPO)} (frozen: commit before any test return)")
    return 0


def fit_k(args) -> int:  # pragma: no cover - reads the real fit panels; its core is tested (fit_k_core)
    require_stage0_rulings_only()
    px = read_fit(PRICES, ["date", "ticker", "close"])
    close = px.pivot(index="date", columns="ticker", values="close").sort_index()
    dist = read_fit(DIST_REFRESH, ["ticker", "ex_date", "amount", "stock_split"], date_col="ex_date")
    ret = fit_returns(close, dist)
    cap = spec.MAX_GROSS_STRESS
    if not cap:
        raise Stage0Error("spec.MAX_GROSS_STRESS is not set; the cap-binding share needs it")
    out = fit_k_core(ret, dist, float(cap), float(spec.VOL_TARGET))
    out.update({"stamp": STAMP, "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "spec": spec.SPEC_ID, "fit": f"{FIT_START.date()}..{FIT_END.date()}",
                "note": "fit P&L dispersion only; no mean, Sharpe or t was formed (team lead's go, 2026-10-28, R9)"})
    K_JSON.write_text(json.dumps(_jsonable(out), indent=1, sort_keys=True))
    print(json.dumps(_jsonable(out), indent=1, sort_keys=True))
    print(f"-> {K_JSON.relative_to(REPO)}. Commit it before anything else.")
    return 0


def pnl_window(rec: dict, sessions: pd.DatetimeIndex) -> tuple:
    """O1 as ruled (team lead, 2026-10-28): the first session on or after TEST_START to the earlier of
    the frozen end's cover row and 2026-10-09, where IEF and HYG in data/etf_daily.parquet end."""
    end_ex = pd.Timestamp(rec["dg_x1_refresh"]["test_end_ex"])
    last = min(sessions[sessions.get_loc(end_ex) + HOLD], O1_END)
    return sessions[sessions.searchsorted(TEST_START)], sessions[sessions <= last][-1]


def factor_gaps(window: tuple, sessions: pd.DatetimeIndex) -> list[str]:
    """Every factor input present on every window session and the session before it (the Dimson
    lag). Presence only: no value is read beyond its being non-null."""
    i0 = sessions.get_loc(window[0])
    need = sessions[max(0, i0 - 1):sessions.get_loc(window[1]) + 1]
    out = []
    if not FF_DAILY.exists():
        return [f"{FF_DAILY.name} missing"]
    f = pd.read_parquet(FF_DAILY, columns=["date", "mktrf", "smb", "hml", "rmw", "cma", "umd", "rf"])
    f["date"] = pd.to_datetime(f["date"])
    ok = set(f.dropna()["date"])
    m = [d for d in need if d not in ok]
    if m:
        out.append(f"French FF5+UMD+rf miss {len(m)} session(s) from {m[0].date()}")
    e = pd.read_parquet(ETF_DAILY, columns=["date", "ticker", "ret_total"], filters=[("ticker", "in", ["IEF", "HYG"])])
    e["date"] = pd.to_datetime(e["date"])
    for t in ("IEF", "HYG"):
        okt = set(e[(e.ticker == t) & e.ret_total.notna()]["date"])
        m = [d for d in need if d not in okt]
        if m:
            out.append(f"{t} (data/etf_daily.parquet) misses {len(m)} session(s) from {m[0].date()}")
    if ETF_YF["MUB"].exists():
        mb = pd.read_parquet(ETF_YF["MUB"], columns=["date", "close"])
        mb["date"] = pd.to_datetime(mb["date"])
        okm = set(mb.dropna()["date"])
        prev = sessions[max(0, i0 - 2)]
        m = [d for d in list(need) + [prev] if d not in okm]
        if m:
            out.append(f"MUB misses {len(m)} session(s) from {min(m).date()}")
    else:
        out.append("MUB cache missing")
    return out


def open_gate(go: str | None, *, check_git: bool = True, opened: Path = OPENED, open_rulings: Path = OPEN_RULINGS,
              verify_pins: bool = True, **paths) -> tuple:
    """Every condition the opening needs, checked before it reads a 2023+ return. It refuses unless:
    - an explicit `--team-lead-go YYYY-MM-DD` is passed, dated today or earlier, and matching the GO row
      the team lead recorded in `exdrift_open_rulings.csv`;
    - the readings O1-O4 are ruled in that same file;
    - Stage 0 is CLEAR in the committed record, with every flag ruled;
    - fit-k's k is committed;
    - French, IEF, HYG and MUB cover the P&L window (O1) and the lag row;
    - every input the opening reads is byte-identical to what Stage 0 pinned (review B3);
    - the trial code is committed and clean (review S2);
    - the test set was never opened: OPENED is absent here and in every branch's history (review S1).
    Returns (go date, k record, the rulings, the window, the gate token)."""
    from scripts.events import exdrift_open as xo
    if not go:
        raise dg.Stage0BlockError("`open` needs --team-lead-go YYYY-MM-DD: the team lead's explicit go")
    try:
        gd = datetime.strptime(go, "%Y-%m-%d").date()
    except ValueError as e:
        raise dg.Stage0BlockError(f"--team-lead-go {go!r} is not a date YYYY-MM-DD") from e
    if gd > datetime.now(timezone.utc).date():
        raise dg.Stage0BlockError(f"--team-lead-go {gd} is in the future")
    if Path(opened).exists():
        raise dg.Stage0BlockError(f"the test set was already opened ({Path(opened).name}); it is opened once")
    if check_git:
        r = subprocess.run(["git", "-C", str(REPO), "log", "--all", "--oneline", "--", str(Path(opened).relative_to(REPO))],
                           capture_output=True, text=True)
        if r.returncode != 0 or r.stdout.strip():
            raise dg.Stage0BlockError(f"{Path(opened).name} exists in this repository's history: the test set was opened")
    if not Path(open_rulings).exists():
        raise dg.Stage0BlockError(f"{Path(open_rulings).name} does not exist: the team lead rules O1-O4 and records the GO row")
    if check_git:
        _committed([Path(open_rulings)] + TRIAL_CODE, True)      # amendment 1 withdrawn (2026-10-28): no hedge input
    O = pd.read_csv(open_rulings, dtype=str, keep_default_na=False)
    need = [c for c, _ in OPEN_READINGS] + ["GO"]
    for c in need:
        row = O[O.check == c]
        if len(row) != 1 or not row.ruling.iloc[0].strip() or row.ruled_by.iloc[0].strip() != "team lead":
            raise dg.Stage0BlockError(f"{Path(open_rulings).name}: {c} is not ruled by the team lead")
    g = O[O.check == "GO"].iloc[0]
    if g.ruled_on.strip() != str(gd) or not g.ruling.strip().upper().startswith("GO"):
        raise dg.Stage0BlockError(f"the GO row says {g.ruling!r} on {g.ruled_on!r}; --team-lead-go is {gd}")
    J = require_stage0_clear(check_git=check_git, **paths)
    rec = json.loads(Path(paths.get("record", STAGE0_JSON)).read_text())
    if verify_pins:
        pins = rec.get("input_pins_sha256") or {}
        bad = [k_ for k_, v in PINNED.items() if pins.get(k_) is None or not v.exists()
               or hashlib.sha256(v.read_bytes()).hexdigest() != pins[k_]]
        if bad:
            raise dg.Stage0BlockError(f"inputs differ from what Stage 0 pinned (re-run Stage 0, commit, re-rule): {bad}")
    window = pnl_window(rec, sessions_calendar())
    gaps = factor_gaps(window, sessions_calendar())
    if gaps:
        raise dg.Stage0BlockError("the factor inputs do not cover the P&L window (O1): " + "; ".join(gaps))
    k = json.loads(Path(paths.get("k_path", K_JSON)).read_text())
    return gd, k, J, window, xo._GATE_TOKEN


def open_test(args) -> int:  # pragma: no cover - THE ONE OPENING: run only on the team lead's go, never by an agent
    gd, kj, _, window, token = open_gate(args.team_lead_go)
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    with open(OPENED, "x") as fh:                                         # exclusive: a second shell cannot open too
        fh.write(json.dumps({"team_lead_go": str(gd), "opened_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "commit": head}, indent=1))                  # recorded before the first 2023+ return
    from scripts.events import exdrift_open as xo
    D = xo.load_test(token, kj["k"], kj["cap"], float(spec.VOL_TARGET), N_BAR, window)
    ev, _ = xo.build_events(D)
    rec = json.loads(STAGE0_JSON.read_text())
    ruled = rec["eligible"][next(k_ for k_ in rec["eligible"] if k_.startswith("as ruled"))]
    if (len(ev), int(ev.ticker.isin(CORE).sum())) != (ruled["events"], ruled["events_13"]):
        msg = (f"the opening's eligible set ({len(ev)}, {int(ev.ticker.isin(CORE).sum())} on the 13) differs from Stage 0's "
               f"({ruled['events']}, {ruled['events_13']}): HALT before any statistic, for a ruling")
        OPENED.write_text(json.dumps({**json.loads(OPENED.read_text()), "halted": msg}, indent=1))
        raise xo.OpenError(msg)
    out = xo.open_core(D)
    xo.write_report(out, OUT_DIR / f"exdrift_OPEN_result_{gd}.json", OUT_DIR / f"exdrift_OPEN_result_{gd}.txt")
    print(f"verdict {out['report']['verdict']} -> {OUT_DIR.relative_to(REPO)}/exdrift_OPEN_result_{gd}.json")
    return 0


def rehearse(args) -> int:  # the 2021-22 rehearsal; `--hedge` re-runs amendment 1's (withdrawn) record
    """The opening's code on FIT data only (2021-01-01 .. 2022-12-30), as C4 rehearsed. It needs
    fit-k's committed k. No 2023+ row is read (every frame is cut at FIT_END and asserted)."""
    from scripts.events import exdrift_open as xo
    if not K_JSON.exists():
        raise dg.Stage0BlockError(f"{K_JSON.name} does not exist: run fit-k first")
    kj = json.loads(K_JSON.read_text())
    D = xo.load_rehearsal(kj["k"], kj["cap"], float(spec.VOL_TARGET), N_BAR, hedge=bool(getattr(args, "hedge", False)))
    out = xo.open_core(D)
    hedged = bool(getattr(args, "hedge", False))
    xo.write_report(out, REHEARSAL_A1_JSON if hedged else REHEARSAL_JSON, REHEARSAL_A1_TXT if hedged else REHEARSAL_TXT)
    r = out["report"]
    print(f"{r['label']}: verdict {r['verdict']}; events {r['events']}; stage 1 {r['stage1_event_mean']}")
    print(f"-> {(REHEARSAL_A1_JSON if hedged else REHEARSAL_JSON).relative_to(REPO)}")
    return 0


FIT_D4_JSON = OUT_DIR / "exdrift_fit_d4_full_window.json"
FIT_D4_CSV = OUT_DIR / "exdrift_fit_d4_full_window.csv"
FIT_ERAS_D4 = (("2005-09", "2005-01-01", "2009-12-31"), ("2010-15", "2010-01-01", "2015-12-31"),
               ("2016-20", "2016-01-01", "2020-12-31"), ("2021-22", "2021-01-01", "2022-12-30"))


def fit_d4(args) -> int:
    """The team lead's check (2026-10-28): stages 1-5 of the opening's code on the FULL fit window, on
    FIT DATA ONLY. It runs (i) the original design, (ii) amendment 1 (post-hoc and in-sample: its
    betas were estimated on this window), and (iii) the original design by era. Stage 5 starts
    where every factor exists (MUB from 2007-09); the rehearsal windows otherwise match the
    2021-22 rehearsal's code exactly."""
    from scripts.events import exdrift_open as xo
    kj = json.loads(K_JSON.read_text())
    mub0 = pd.Timestamp("2007-09-12")                      # MUB's first total return (fetch_exdrift_mub.py)
    runs = [("(i) original, full fit", "2005-01-01", "2022-12-30", False),
            ("(ii) amendment 1, POST-HOC and IN-SAMPLE (betas estimated on this window)", "2007-09-12", "2022-12-30", True)]
    runs += [(f"(iii) original, era {lab}", a, b, False) for lab, a, b in FIT_ERAS_D4]
    rows, full = [], {}
    for lab, a, b, hedge in runs:
        D = xo.load_rehearsal(kj["k"], kj["cap"], float(spec.VOL_TARGET), N_BAR, lo=a, hi=b, hedge=hedge)
        if not hedge:
            D.hedge_betas = None
        out = xo.open_core(D, d4_from=max(mub0, D.window[0]))
        r = out["report"]
        d = r["stage5_d4"]
        rows.append({"run": lab, "window": f"{r['window'][0]}..{r['window'][1]}", "events": r["events"],
                     "mean_bp": r["stage1_event_mean"]["mean_bp"], "t_month": r["stage1_event_mean"]["t_month"],
                     "placebo_pooled_bp": r["stage2_placebo"]["pooled_mean_bp"],
                     "nav_leg_bp": r["stage3_nav_leg"]["mean_bp"],
                     "price_same_events_bp": r["stage3_nav_leg"]["price_mean_same_events_bp"],
                     "d4_window": f"{d['window'][0]}..{d['window'][1]}", "alpha_t": d["alpha_t"],
                     "MUNI_at_target": d["betas_summed_at_target"]["MUNI"], "MUNI_se": d["se_at_target_report_only"]["MUNI"],
                     "TERM_at_target": d["betas_summed_at_target"]["TERM"], "TERM_se": d["se_at_target_report_only"]["TERM"],
                     "max_abs_beta_at_target": d["max_abs_beta_at_target"], "d4_pass": d["pass"],
                     "cap_binding_share": r["sleeve"]["cap_binding_share"], "verdict_stages_1_6": r["verdict"]})
        full[lab] = r
    T = pd.DataFrame(rows)
    T.to_csv(FIT_D4_CSV, index=False)
    FIT_D4_JSON.write_text(json.dumps(_jsonable({"note": "FIT DATA ONLY (2005-01-01..2022-12-30); descriptive; moves no counter",
                                                  "runs": full}), indent=1, sort_keys=True, default=str))
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(T.round(3).to_string(index=False))
    print(f"-> {FIT_D4_CSV.relative_to(REPO)}")
    return 0


def power_at(events: int, events_13: int, months: int, sessions: int) -> dict:
    """§10's power, recomputed for a count (prereg_power_he.py's method, unchanged): the per-event
    SE is the fit's sd of monthly means scaled to the count's events per month; the sleeve Sharpe
    is r6's mean times the fit's events per month over the fit's sd of monthly sums [U]."""
    from statistics import NormalDist
    from scripts.xasset.slate_feasibility import p_alpha_t, power, required_sharpe
    b3 = json.loads(B3_JSON.read_text())
    Nd = NormalDist()
    epm_fit = b3["he_events"] / b3["he_months"]
    out = {"events": events, "events_13": events_13, "months": months, "T_sessions": sessions,
           "inputs": "fit H-E dispersion (prereg_inputs_b3.json, identity-gated at DG-X7) and r6's mean"}
    for lab, nev in (("17", events), ("13", events_13)):
        epm = nev / months
        se = b3["he_sd_month_mean"] * math.sqrt(epm_fit / epm) / math.sqrt(months)
        for f_ in (1.0, 0.5, 0.25):
            mu = f_ * abs(R6_PUBLISHED["car_bp"])
            out[f"event_{lab}_{f_}"] = {"mu_bp": mu, "se_bp": se, "t": mu / se, "p_t_ge_2": 1 - Nd.cdf(2 - mu / se)}
    for f_ in (1.0, 0.5):
        sr = (f_ * abs(R6_PUBLISHED["car_bp"]) * epm_fit) / b3["he_sd_month_sum"] * math.sqrt(12)
        out[f"sleeve_{f_}"] = {"sr": sr, "p_dsr_N7": power(sr, N_BAR, sessions), "p_alpha_t3": p_alpha_t(sr, sessions)}
    out["sharpe_needed_N7"] = required_sharpe(N_BAR, sessions)
    return out


def power_cmd(args) -> int:
    rec = json.loads(STAGE0_JSON.read_text())
    lab = next(k_ for k_ in rec["eligible"] if k_.startswith("as ruled"))
    e = rec["eligible"][lab]
    sessions = sessions_calendar()
    end_ex = pd.Timestamp(rec["dg_x1_refresh"]["test_end_ex"])
    w = pnl_window(rec, sessions)
    T = int(((sessions >= w[0]) & (sessions <= w[1])).sum())
    out = power_at(e["events"], e["events_13"], e["months"], T)
    out["eligible_label"] = lab
    POWER_JSON.write_text(json.dumps(_jsonable(out), indent=1, sort_keys=True))
    print(json.dumps(_jsonable(out), indent=1, sort_keys=True))
    return 0


def rulings_template(args) -> int:
    F = pd.read_csv(FLAGS, dtype=str, keep_default_na=False)
    p = dg.stage0_rulings_template(F, RULINGS)
    print(f"blank rulings form for {len(F)} flags -> {p.relative_to(REPO)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stage0")
    sub.add_parser("rulings-template")
    sub.add_parser("notices")
    ar = sub.add_parser("apply-rulings")
    ar.add_argument("--supersede", default="", help="classes the team lead re-ruled, e.g. R10")
    sub.add_parser("fit-k")
    op = sub.add_parser("open")
    op.add_argument("--team-lead-go", default=None, help="the team lead's explicit go, YYYY-MM-DD")
    rh = sub.add_parser("rehearse")
    rh.add_argument("--hedge", action="store_true", help="amendment 1's withdrawn hedge (the record only)")
    sub.add_parser("power")
    sub.add_parser("amend1-betas")
    sub.add_parser("fit-d4")
    a = ap.parse_args(argv)
    if a.cmd == "stage0":
        S = stage0()
        return 0 if S["rec"]["stage0"] == "CLEAR" else 2
    if a.cmd == "rulings-template":
        return rulings_template(a)
    if a.cmd == "apply-rulings":
        R = apply_rulings(supersede=tuple(x_.strip() for x_ in (a.supersede or "").split(",") if x_.strip()))
        print(f"{len(R)} rulings ({RULED_BY}, {RULED_ON}) -> {RULINGS.relative_to(REPO)}: "
              + json.dumps(R.groupby("ruling").size().rename(lambda x: x[:50]).to_dict()))
        return 0
    if a.cmd == "rehearse":
        return rehearse(a)
    if a.cmd == "power":
        return power_cmd(a)
    if a.cmd == "amend1-betas":
        return amend1_betas(a)
    if a.cmd == "fit-d4":
        return fit_d4(a)
    if a.cmd == "notices":
        print(f"notice cache: {fetch_notices()}")
        verify_notices()
        print("every quote re-found")
        return 0
    if a.cmd == "fit-k":
        return fit_k(a)
    return open_test(a)


if __name__ == "__main__":
    sys.exit(main())
