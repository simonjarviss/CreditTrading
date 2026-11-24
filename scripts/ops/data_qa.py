"""Nightly data QA for one book: is tonight's panel fit to decide on, and which name-days look wrong?

    python3 -m scripts.ops.data_qa --book cef [--state-dir DIR] [--asof YYYY-MM-DD]

WHY THIS EXISTS (team lead, 2026-11-08; design results/ops/AGENT_DESK_DESIGN_2026-11-03.md, PR #46)
---------------------------------------------------------------------------------------------------
Six of the graveyard's thirteen deaths were stale-price artifacts. On 2026-11-03
trial 54's DG-L3 found 9 NAV misprints by hand, with no check that looks for a
misprint that is present and plausible-looking. Then the evening check itself
lived only in an open Claude session: it ran three days late and the 11-06 plans
sent unread (E-2026-11-08-03). So this is a deterministic script on a VM timer
(`quantt/deploy/install_vm.py --reports`), scheduled after the day's collect and
before the 22:00 decide.

WHAT IT IS, AND IS NOT
----------------------
REPORT ONLY. It reads panels and the runner's own records, computes flags and
writes `<state>/reports/data_qa/<asof>.{md,json}`. It never edits `data/`, never
writes into the git clone, never reads a credential, holds no broker client, and
imports nothing from `quantt.broker` or `quantt.session.run`
(scripts/ops/tests/test_report_no_order_path.py proves it). A flag is an item for
the evening brief; a held name's flag is a WATCH. ACT is reserved for a
pre-registered stop (`scripts/ops/risk_daily.py`): nothing here pushes a
notification.

A MISSING INPUT IS UNMEASURED, NAMED, NEVER INFERRED (CLAUDE.md: no silent
fallbacks). Every check returns status OK, FLAG or UNMEASURED (with `why`).

THE CHECKS (per name, on the book's deployed universe; the design's table)
--------------------------------------------------------------------------
Q1 panel freshness    the last price or NAV date is not the expected trading day,
                      a name's own last date lags it, or the row count on the last
                      date differs from the previous date's.
Q2 NAV misprint       a one-day NAV move far out in the name's own trailing
                      distribution, while the close did not follow. CONFIRMED when
                      it reverts by half within `Q2_REVERT_SESSIONS` NAV rows;
                      SUSPECT on a row whose reversion window has not closed
                      (tonight's own row cannot be confirmed before the decide).
Q3 stale NAV          the NAV unchanged (to the cent) for longer than the name's
                      own longest run over the trailing year.
Q4 split-like step    a close or NAV ratio near an integer split factor with no
                      corporate-action row naming it (tolerance: data_guards').
Q5 discount outlier   |close / NAV - 1| crossing the line tonight (first night only).
Q6 ADV-floor margin   an ADV dip of `q6_margin` would leave fewer than `min_names`
                      eligible names ("one ADV dip from thin"; the count, not the
                      least liquid name alone, for the reason in `q6_margin_flag`).
Q7 corporate actions  the runner's last corporate-action gate record: any blocking
                      event, any unresolved-party row, or UNMEASURED.
Q8 first-fetch vs seed (C4, first nights only) rows the fetch replaced differ from
                      the seed beyond half a cent. Needs `--seed-dir`.
Q9 NAV second source  the collector's own record of tonight's NAV cross-check
                      (`<state>/data/<asof>/report.json`): FLAG when the step had no
                      second source or did not complete, with the count of consecutive
                      data days it has been so. No threshold (`q9_second_source`).

THRESHOLDS (H14, H8): derived on fit data only, never swept and picked
----------------------------------------------------------------------
Every number in `THRESHOLDS` is produced by
`results/ops/data_qa_calibration/calibrate.py` on the panels before 2023-01-01
(the time holdout is not read) and each book's deployed names only (the untouched
CEFs outside the deployed universe are not read), to the design's false-alarm
budget: at most one flag per book per week on panels with no known defect. Each
check gets an equal share of that budget (`BUDGET_SHARE`, because a week holds
five checks that can fire). The derivation, inputs and recall on the known
positives are in `results/ops/DATA_QA_CALIBRATION_2026-11-08.md`.
`scripts/ops/tests/test_data_qa.py::test_thresholds_are_the_calibration_outputs`
fails if a value here drifts from that run's output.
Where the recall on the known positives is below the design's aim at the budget,
the note says so; nothing here was tuned until it passed.

Stock imports only at module level, plus numpy/pandas and two pure helpers
(`ops.schedule.nyse_calendar`, `scripts.cef.data_guards`).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ops.schedule.nyse_calendar import is_trading_day, previous_trading_day      # noqa: E402
from scripts.cef.data_guards import SPLIT_TOL                                     # noqa: E402

ET = ZoneInfo("America/New_York")

OK, FLAG, UNMEASURED, NOT_RUN = "OK", "FLAG", "UNMEASURED", "NOT_RUN"
CHECK_IDS = ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9")

# How much panel a nightly run reads: enough for the longest trailing window
# (Q2/Q3: 252 rows + Q2_MIN_OBS) at both ends of a weekend/holiday stretch.
NIGHTLY_LOOKBACK_DAYS = 1200

# Q2: fixed by the definition, not swept (design: "reverts within a few sessions
# while the price does not follow"). "Reverts" = back by at least half the move.
Q2_TRAIL, Q2_MIN_OBS, Q2_REVERT_SESSIONS = 252, 60, 3
Q2_REVERT_FRAC, Q2_PX_FOLLOW_MAX = 0.5, 0.5
# Q3: a run is "stale" against the name's own longest run in the trailing year.
Q3_TRAIL, Q3_MIN_OBS, Q3_CENT = 252, 60, 0.005
Q6_ADV_DAYS, Q6_ADV_MIN = 63, 21      # src/deploy/sleeves/cef_discount.py, the `adv` line
Q8_CENT = 0.005                       # "beyond rounding": half a cent (quantt/collect TOLERANCE_USD)

BUDGET_FLAGS_PER_WEEK = 1.0           # the design's budget, per book, jointly
BUDGET_SHARE = 0.2                    # each of Q2..Q6 gets a fifth of it (docstring)

# Derived by results/ops/data_qa_calibration/calibrate.py (docstring); a test pins
# these to that script's output JSON. `q5_line` is a fraction, |close/nav - 1|.
THRESHOLDS = {
    "cef": {"q2_z": 6.5, "q3_delta": 0, "q5_line": 0.22, "q6_margin": 0.025},
    "c4": {"q2_z": 10.0, "q3_delta": 1, "q5_line": 0.27, "q6_margin": 0.13},
}


class Unmeasured(Exception):
    """An input is missing or unreadable. The message names it."""


@dataclass(frozen=True)
class BookCfg:
    name: str
    data_dir: str
    spec_path: str
    universe_file: str | None    # None: the spec's frozen.universe
    # The collector step that compares the panel NAV with a second source (Q9), or
    # None for a book that has none by ruling. C4 reads no CEFConnect (team lead,
    # 2026-10-28; quantt/collect/collect.py THE C4 BOOK), so Q9 is NOT_RUN there.
    second_source_step: str | None = None


BOOKS = {
    "cef": BookCfg("cef", "cef", "ops/specs/cef_discount.frozen.json", None,
                   second_source_step="nav_crosscheck"),
    "c4": BookCfg("c4", "cef_c4", "ops/specs/c4_families.frozen.json",
                  "results/cef/c4/c4_universe_frozen_2026-10-14.csv"),
}


@dataclass
class Flag:
    check: str
    ticker: str | None
    date: str
    rule: str
    value: float | None = None
    threshold: float | None = None
    confirmed: bool | None = None       # Q2 only: reverted (True) or suspect (False)
    held: bool = False                  # the name is held or targeted (latest plan)
    evidence: dict = field(default_factory=dict)


# ------------------------------------------------------------------- inputs

def read_spec(cfg: BookCfg) -> dict:
    path = REPO / cfg.spec_path
    if not path.is_file():
        raise Unmeasured(f"no frozen spec at {path}")
    return json.loads(path.read_text())


def book_universe(cfg: BookCfg, spec: dict | None = None) -> list[str]:
    """The book's deployed names: the spec's frozen universe, or C4's frozen CSV
    (the 74 funds). Sealed holdout names are never in this list."""
    if cfg.universe_file is None:
        uni = ((spec or read_spec(cfg)).get("frozen") or {}).get("universe")
        if not uni:
            raise Unmeasured(f"{cfg.spec_path} has no frozen.universe")
        return list(uni)
    path = REPO / cfg.universe_file
    if not path.is_file():
        raise Unmeasured(f"no universe file at {path}")
    return sorted(pd.read_csv(path)["ticker"].astype(str).tolist())


def read_long(path: Path, cols: list[str], *, start=None, tickers=None) -> pd.DataFrame:
    """A long panel (date, ticker, ...), with `date` a normalized Timestamp.
    Reads only `cols` (and optionally `date >= start`) to keep the 950 MB VM's
    peak down; a missing file raises Unmeasured naming it."""
    if not Path(path).is_file():
        raise Unmeasured(f"no panel at {path}")
    filters = [("date", ">=", pd.Timestamp(start))] if start is not None else None
    df = pd.read_parquet(path, columns=cols, filters=filters)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    if tickers is not None:
        df = df[df["ticker"].astype(str).isin(set(tickers))]
    return df.drop_duplicates(["date", "ticker"], keep="last")


def wide(df: pd.DataFrame, col: str) -> pd.DataFrame:
    return df.pivot(index="date", columns="ticker", values=col).sort_index().astype(float)


@dataclass
class Panels:
    close: pd.DataFrame
    volume: pd.DataFrame
    nav: pd.DataFrame


def load_panels(data_dir: Path, tickers, start=None) -> Panels:
    """The book's wide price/volume/NAV panels. `data_dir` holds the two parquets."""
    px = read_long(Path(data_dir) / "cef_prices.parquet", ["date", "close", "volume", "ticker"],
                   start=start, tickers=tickers)
    nav = read_long(Path(data_dir) / "cef_nav.parquet", ["date", "nav", "ticker"],
                    start=start, tickers=tickers)
    return Panels(wide(px, "close"), wide(px, "volume"), wide(nav, "nav"))


def read_splits(data_dir: Path) -> pd.DataFrame | None:
    """Corporate-action rows the panel directory carries, as (ticker, ex_date), or
    None if it carries none (Q4 then flags every split-like step and says why)."""
    data_dir = Path(data_dir)
    if (data_dir / "cef_splits.parquet").is_file():
        s = pd.read_parquet(data_dir / "cef_splits.parquet")
        return s[["ticker", "ex_date"]].assign(ex_date=lambda d: pd.to_datetime(d["ex_date"]))
    if (data_dir / "cef_actions.parquet").is_file():
        a = pd.read_parquet(data_dir / "cef_actions.parquet")
        a = a[a["stock_splits"].fillna(0) != 0]
        return pd.DataFrame({"ticker": a["ticker"].astype(str),
                             "ex_date": pd.to_datetime(a["date"])})
    return None


def expected_day(now_et: dt.datetime) -> dt.date:
    """The newest NYSE trading day whose close has settled by `now_et`. The 16:45
    cut is the collector's settle time (quantt/collect/collect.py CLOSE_SETTLE)."""
    d = now_et.date()
    if is_trading_day(d) and now_et.time() >= dt.time(16, 45):
        return d
    return previous_trading_day(d) if is_trading_day(d) else _prev_session(d)


def _prev_session(d: dt.date) -> dt.date:
    while not is_trading_day(d):
        d -= dt.timedelta(days=1)
    return d


def latest_plan(state_dir: Path, asof: dt.date) -> tuple[dict | None, str | None]:
    """The newest `<state>/<D>/plan.json` with D <= asof + 1 session, and its path.
    (The session dir is named for the session date, one trading day after the as-of
    it decided on.) None if there is none; a corrupt file raises Unmeasured."""
    latest = None
    for d in sorted(Path(state_dir).glob("20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]")):
        if (d / "plan.json").is_file() and dt.date.fromisoformat(d.name) <= asof + dt.timedelta(days=5):
            latest = d / "plan.json"
    if latest is None:
        return None, None
    try:
        return json.loads(latest.read_text()), str(latest)
    except (OSError, ValueError) as e:
        raise Unmeasured(f"{latest} unreadable: {type(e).__name__}: {e}") from None


def held_names(plan: dict | None) -> set[str]:
    """Names in the latest plan: targets (held or wanted) and order symbols."""
    if not plan:
        return set()
    names = set(plan.get("targets", {}))
    names |= {o.get("symbol") for o in plan.get("orders", []) if o.get("symbol")}
    return {n for n in names if n}


# ------------------------------------------------------------------- the checks

def q1_freshness(close: pd.DataFrame, nav: pd.DataFrame, universe, expected: dt.date) -> list[Flag]:
    """Q1: panel last dates vs the expected trading day, per panel and per name,
    and the row-count check. Row count = universe names with a value on the panel's
    last date vs the previous date (a name that stops printing shows here)."""
    flags, exp = [], pd.Timestamp(expected)
    for label, panel in (("price", close), ("NAV", nav)):
        names = [c for c in universe if c in panel.columns]
        last = panel.index.max() if len(panel.index) else None
        if last is None or pd.Timestamp(last) != exp:
            flags.append(Flag("Q1", None, expected.isoformat(),
                              f"the {label} panel's last date is {last}, not the expected {expected}",
                              evidence={"panel": label, "last_date": str(last)}))
        if last is None or pd.Timestamp(last) != exp:
            continue                     # the panel flag above covers every name; do not repeat it 13 or 74 times
        for t in names:
            s = panel[t].dropna()
            ldate = s.index.max() if len(s.index) else None
            if ldate is None or pd.Timestamp(ldate) < exp:
                flags.append(Flag("Q1", t, expected.isoformat(),
                                  f"{t}'s last {label} date is {ldate}, not {expected}",
                                  evidence={"panel": label, "last_date": str(ldate)}))
        if last is not None and len(panel.index) >= 2:
            dates = panel.index
            n_last = int(panel.loc[dates[-1], names].notna().sum())
            n_prev = int(panel.loc[dates[-2], names].notna().sum())
            if n_last != n_prev:
                flags.append(Flag("Q1", None, str(dates[-1].date()),
                                  f"{label} row count on the last date {n_last} differs from the "
                                  f"previous date's {n_prev}",
                                  value=n_last, threshold=n_prev,
                                  evidence={"panel": label, "n_last": n_last, "n_prev": n_prev}))
    return flags


def q2_candidates(nav: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    """All Q2 candidates over the panel: one row per (ticker, t) with |r_t| over
    the trailing mean |r| of the name's own NAV changes. No lookahead in `z`: the
    scale uses rows strictly before t. `reverted` looks at up to
    `Q2_REVERT_SESSIONS` NAV rows after t, which is why a row confirmed "by the
    night of t+k" is only known then (`confirm_date`). A close that follows the
    NAV (same sign and more than half the size) is no candidate.
    Columns: ticker date z r px_r reverted confirm_date n_after."""
    rows = []
    for tk in nav.columns:
        s = nav[tk].dropna()
        s = s[s > 0]
        if len(s) < Q2_MIN_OBS + 2:
            continue
        lv = np.log(s.to_numpy(dtype=float))
        r = pd.Series(np.diff(lv, prepend=lv[0]), index=s.index)
        r.iloc[0] = np.nan
        # the mean absolute change over the prior Q2_TRAIL rows, strictly before t
        scale = r.abs().rolling(Q2_TRAIL, min_periods=Q2_MIN_OBS).mean().shift(1)
        z = (r.abs() / scale.clip(lower=1e-5))
        cand_idx = np.flatnonzero(z.to_numpy(dtype=float) >= 3.0)   # a floor well below any threshold
        if not len(cand_idx):
            continue
        px = close[tk].reindex(s.index).ffill() if tk in close.columns else None
        n = len(s)
        for i in cand_idx:
            if i == 0 or not np.isfinite(scale.iat[i]):
                continue
            ri = float(r.iat[i])
            px_r = float("nan")
            if px is not None and np.isfinite(px.iat[i]) and np.isfinite(px.iat[i - 1]) and px.iat[i - 1] > 0 and px.iat[i] > 0:
                px_r = math.log(px.iat[i] / px.iat[i - 1])
            follow = (np.isfinite(px_r) and np.sign(px_r) == np.sign(ri)
                      and abs(px_r) > Q2_PX_FOLLOW_MAX * abs(ri))
            if follow:
                continue
            rev_j = None
            for j in range(1, Q2_REVERT_SESSIONS + 1):
                if i + j >= n:
                    break
                if abs(lv[i + j] - lv[i - 1]) <= (1 - Q2_REVERT_FRAC) * abs(ri):
                    rev_j = j
                    break
            rows.append({"ticker": tk, "date": s.index[i], "z": float(z.iat[i]), "r": ri, "px_r": px_r,
                         "reverted": rev_j is not None,
                         "confirm_date": s.index[i + rev_j] if rev_j else pd.NaT,
                         "span_end": s.index[i + rev_j - 1] if rev_j else pd.NaT,
                         "n_after": n - 1 - i})
    out = pd.DataFrame(rows, columns=["ticker", "date", "z", "r", "px_r", "reverted", "confirm_date",
                                      "span_end", "n_after"])
    # A misprint's reversion step is itself a huge "move the price did not follow"
    # (BME 2006-07-25 z 14.5 the day after the 07-24 print). It is the same event,
    # so the row that a confirmed candidate names as its confirm_date is dropped.
    conf = out.loc[out["reverted"], ["ticker", "confirm_date"]].rename(columns={"confirm_date": "date"})
    conf["is_echo"] = True
    out = out.merge(conf, on=["ticker", "date"], how="left")
    return out[out["is_echo"].isna()].drop(columns="is_echo").reset_index(drop=True)


def q2_flags(cand: pd.DataFrame, z_min: float, recent_dates) -> list[Flag]:
    """Tonight's Q2 flags from `q2_candidates`, for the NAV rows in `recent_dates`
    (the last `Q2_REVERT_SESSIONS` panel dates): a candidate with z >= `z_min` is
    flagged CONFIRMED when its confirm date is one of them (it just reverted), or
    SUSPECT while its window is open: it sits on one of them and has not
    reverted. Older confirmed misprints are in the calibration note, not tonight."""
    if cand.empty:
        return []
    recent = set(pd.Timestamp(d) for d in recent_dates)
    c = cand[cand["z"] >= z_min]
    flags = []
    for _, r in c.iterrows():
        d = pd.Timestamp(r["date"])
        confirmed = bool(r["reverted"]) and pd.Timestamp(r["confirm_date"]) in recent
        suspect = (not bool(r["reverted"])) and d in recent and int(r["n_after"]) < Q2_REVERT_SESSIONS
        if not (confirmed or suspect):
            continue
        flags.append(Flag("Q2", r["ticker"], str(d.date()),
                          "NAV move " + ("reverted" if confirmed else "unconfirmed (its reversion window is open)")
                          + " while the close did not follow",
                          value=float(r["z"]), threshold=float(z_min), confirmed=confirmed,
                          evidence={"z": float(r["z"]), "r": float(r["r"]), "px_r": float(r["px_r"]),
                                    "span_end": None if pd.isna(r["span_end"])
                                    else str(pd.Timestamp(r["span_end"]).date()),
                                    "confirm_date": None if pd.isna(r["confirm_date"])
                                    else str(pd.Timestamp(r["confirm_date"]).date())}))
    return flags


def nav_streaks(nav: pd.Series) -> pd.DataFrame:
    """For one name's NAV rows: L = consecutive rows unchanged to the cent ending
    at each row (0 on a changed row), and prior_max = the longest run in the
    Q3_TRAIL rows strictly before the run's start."""
    s = nav.dropna()
    s = s[s > 0]
    idx = s.index
    if len(s) < 2:
        return pd.DataFrame(columns=["L", "prior_max", "run_start"], index=idx)
    same = (s.diff().abs() <= Q3_CENT).to_numpy()
    L = np.zeros(len(s), dtype=int)
    for i in range(1, len(s)):
        L[i] = L[i - 1] + 1 if same[i] else 0
    run_start = np.array([i - L[i] for i in range(len(s))])   # the row the current run began on
    runs = pd.Series(L)
    # longest run END inside the trailing window, strictly before this run began
    rolling_max = runs.rolling(Q3_TRAIL, min_periods=Q3_MIN_OBS).max().to_numpy()
    prior_max = np.array([rolling_max[max(run_start[i] - 1, 0)] if run_start[i] > 0 else np.nan
                          for i in range(len(s))])
    return pd.DataFrame({"L": L, "prior_max": prior_max,
                         "run_start": [idx[j] for j in run_start]}, index=idx)


def q3_candidates(nav: pd.DataFrame, delta: int = 0) -> pd.DataFrame:
    """All rows on which the current run exceeds the prior year's longest run by
    more than `delta` (one row per run-day). `first` marks the first such day of
    each run, the unit the false-alarm count uses."""
    rows = []
    for tk in nav.columns:
        s = nav[tk]
        if s.notna().sum() < Q3_MIN_OBS + 2:
            continue
        st = nav_streaks(s)
        over = st[(st["L"] > 0) & (st["L"] > st["prior_max"] + delta)]
        if over.empty:
            continue
        first_days = over.groupby("run_start").head(1).index
        for d, r in over.iterrows():
            rows.append({"ticker": tk, "date": d, "L": int(r["L"]), "prior_max": float(r["prior_max"]),
                         "first": d in first_days, "run_start": r["run_start"]})
    return pd.DataFrame(rows, columns=["ticker", "date", "L", "prior_max", "first", "run_start"])


def q3_flags(cand: pd.DataFrame, delta: int, asof) -> list[Flag]:
    if cand.empty:
        return []
    today = cand[cand["date"] == pd.Timestamp(asof)]
    out = []
    for _, r in today.iterrows():
        out.append(Flag("Q3", r["ticker"], str(pd.Timestamp(r["date"]).date()),
                        f"NAV unchanged for {int(r['L'])} rows, longer than the name's longest "
                        f"run in the prior year ({int(r['prior_max'])}) + {delta}",
                        value=float(r["L"]), threshold=float(r["prior_max"]) + delta,
                        evidence={"run_start": str(pd.Timestamp(r["run_start"]).date())}))
    return out


def q4_candidates(close: pd.DataFrame, nav: pd.DataFrame, splits: pd.DataFrame | None) -> pd.DataFrame:
    """Every close or NAV step near an integer split factor (within SPLIT_TOL of
    ln m, m >= 2, either direction), unless a corporate-action row for that name
    falls within 3 calendar days of it. `step` is the ratio, `factor` the nearest m
    or 1/m. Both series are checked because a split-adjusted close with a raw NAV
    (or the reverse) shows the step on one side only."""
    rows = []
    sp_dates: dict[str, list] = {}
    if splits is not None:
        for t, g in splits.groupby("ticker"):
            sp_dates[str(t)] = [pd.Timestamp(x) for x in g["ex_date"]]

    def scan(frame: pd.DataFrame, label: str):
        for tk in frame.columns:
            s = frame[tk].dropna()
            s = s[s > 0]
            if len(s) < 2:
                continue
            a = np.log(s.to_numpy(dtype=float))
            x = np.diff(a)
            m = np.rint(np.exp(np.abs(x)))
            like = (m >= 2) & (np.abs(np.abs(x) - np.log(np.maximum(m, 1.0))) <= SPLIT_TOL)
            for i in np.flatnonzero(like):
                d = s.index[i + 1]
                if any(abs((d - e).days) <= 3 for e in sp_dates.get(str(tk), ())):
                    continue
                f = float(m[i]) if x[i] > 0 else 1.0 / float(m[i])
                rows.append({"ticker": tk, "date": d, "series": label,
                             "step": float(np.exp(x[i])), "factor": f})
    scan(close, "close")
    scan(nav, "nav")
    return pd.DataFrame(rows, columns=["ticker", "date", "series", "step", "factor"])


def q4_flags(cand: pd.DataFrame, asof, *, has_ca_rows: bool, lookback: int = 3) -> list[Flag]:
    if cand.empty:
        return []
    cut = pd.Timestamp(asof) - pd.Timedelta(days=lookback)
    today = cand[(cand["date"] >= cut) & (cand["date"] <= pd.Timestamp(asof))]
    out = []
    for _, r in today.iterrows():
        out.append(Flag("Q4", r["ticker"], str(pd.Timestamp(r["date"]).date()),
                        f"{r['series']} step x{r['step']:.3f}, near split factor {r['factor']:.3g}, "
                        f"with no corporate-action row"
                        + ("" if has_ca_rows else " (this panel directory carries no corporate-action file)"),
                        value=float(r["step"]), threshold=float(r["factor"]),
                        evidence={"series": r["series"]}))
    return out


def discounts(close: pd.DataFrame, nav: pd.DataFrame) -> pd.DataFrame:
    nav_ok = nav.where(nav > 0)
    px_ok = close.reindex(index=nav_ok.index, columns=nav_ok.columns).where(lambda d: d > 0)
    return px_ok / nav_ok - 1


def q5_flags(close: pd.DataFrame, nav: pd.DataFrame, line: float, asof) -> tuple[list[Flag], list[str]]:
    """(flags, standing names). Flag a name on the FIRST night its discount is
    beyond the line: yesterday's discount inside the line (or absent), today's
    outside. A misprint is a jump past the line, and a fund that simply stays at
    a wide discount or a standing premium is the sleeve's own signal, not a data
    defect. Flagging it every night would break the budget by itself (HGLB read
    -39.9% on 2026-10-09, past C4's line; on the core, counting every night past the
    design's flat +/-50pp line ran 0.84 flags per week on the fit panels). Standing names are
    returned so the report still names them."""
    d = discounts(close, nav)
    t = pd.Timestamp(asof)
    if t not in d.index:
        return [], []
    i = d.index.get_loc(t)
    today = d.iloc[i].dropna()
    prev = d.iloc[i - 1] if i > 0 else pd.Series(np.nan, index=d.columns)
    beyond = today[today.abs() > line]
    prev_in = prev.reindex(beyond.index).abs() <= line
    new_names = beyond[prev_in | prev.reindex(beyond.index).isna()]
    standing = sorted(set(beyond.index) - set(new_names.index))
    return [Flag("Q5", tk, str(t.date()), f"discount {v:+.1%} crossed the {line:.0%} line tonight",
                 value=float(v), threshold=float(line),
                 evidence={"previous": None if pd.isna(prev.get(tk)) else float(prev[tk])})
            for tk, v in new_names.items()], standing


def q5_result(close: pd.DataFrame, nav: pd.DataFrame, line: float, asof) -> tuple[list[Flag], str | None]:
    flags, standing = q5_flags(close, nav, line, asof)
    return flags, (f"standing beyond the {line:.0%} line (flagged on their first night only): "
                   f"{', '.join(standing)}" if standing else None)


def adv_panel(close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    """The sleeve's ADV rule: 63-session mean of close x volume, min 21, shifted
    one session (src/deploy/sleeves/cef_discount.py, the `adv` line)."""
    px = close.reindex(index=volume.index, columns=volume.columns)
    return (px * volume).rolling(Q6_ADV_DAYS, min_periods=Q6_ADV_MIN).mean().shift(1)


def q6_safe_count(adv_row: pd.Series, nav_ok: pd.Series, floor: float, margin: float) -> tuple[int, int, str | None, float | None]:
    """(n_eligible, n_safe, least liquid eligible name, its ADV / floor) for one date.
    Eligible = ADV at or above the floor with a NAV on the date (the ADV rule of
    `adv_panel`, read beside the spec's floor). Safe = ADV at or above
    floor x (1 + margin): the names that would still be eligible after an ADV
    dip of that size."""
    row = adv_row.dropna()
    ok = row[nav_ok.reindex(row.index).fillna(False).to_numpy(dtype=bool)]
    eligible = ok[ok >= floor]
    n_elig, n_safe = int(len(eligible)), int((ok >= floor * (1 + margin)).sum())
    if eligible.empty:
        return 0, 0, None, None
    return n_elig, n_safe, str(eligible.idxmin()), float(eligible.min() / floor)


def q6_margin_flag(close: pd.DataFrame, volume: pd.DataFrame, nav: pd.DataFrame, floor: float,
                   min_names: int, margin: float, asof, adv: pd.DataFrame | None = None) -> list[Flag]:
    """Q6: "one ADV dip from a thin session". WHY NOT simply "the least liquid
    eligible name is within a margin of the floor": on the 74-name C4 universe
    some name always sits at about 1.00x the floor (measured: the median minimum
    is 1.03x), so that statement carries no information. What matters for the
    book is the COUNT: fire when the sleeve is at or above `min_names` eligible
    names but fewer than `min_names` keep a margin above the floor, i.e. an ADV
    dip of `margin` would leave it below `min_names` and flat. A session already
    below `min_names` is not flagged: that is the sleeve's rule running, and the
    question here is the step before it. `margin` is derived to the budget."""
    adv = adv_panel(close, volume) if adv is None else adv
    d = pd.Timestamp(asof)
    if d not in adv.index:
        return []
    nav_ok = (nav.loc[d] > 0) if d in nav.index else pd.Series(False, index=adv.columns)
    n_elig, n_safe, least, ratio = q6_safe_count(adv.loc[d], nav_ok, floor, margin)
    if n_elig < min_names or n_safe >= min_names:
        # A session already below min_names is the sleeve's own business (it goes
        # flat by rule), not a data question; the margin is about the step before it.
        return []
    return [Flag("Q6", least, str(d.date()),
                 f"{n_safe} of {n_elig} eligible names keep a {margin:.1%} margin over the "
                 f"${floor:,.0f} floor (min_names {min_names}); the least liquid is {least} at "
                 f"{ratio:.3f}x the floor",
                 value=float(n_safe), threshold=float(min_names),
                 evidence={"n_eligible": n_elig, "n_safe": n_safe, "least": least,
                           "least_ratio": ratio})]


def q7_corporate_actions(plan: dict | None, plan_path: str | None) -> tuple[str, list[Flag], str | None]:
    """Q7: the runner's own last gate record. (status, flags, why)."""
    if plan is None:
        return UNMEASURED, [], "no plan.json under the state directory (no decide has run)"
    rec = plan.get("corporate_actions")
    if rec is None:
        return UNMEASURED, [], (f"{plan_path} has no corporate_actions record "
                                f"(the book's gate is off, or this plan predates it)")
    status = rec.get("status")
    if status == "UNMEASURED":
        return UNMEASURED, [], f"{plan_path}: the gate recorded UNMEASURED: {rec.get('why')}"
    flags = []
    for b in rec.get("blocking", []) or []:
        flags.append(Flag("Q7", b.get("symbol"), str(plan.get("asof")),
                          f"corporate action {b.get('type')} {b.get('id')} blocks "
                          f"{b.get('symbol')} (the gate's window)",
                          evidence={k: b.get(k) for k in ("id", "type", "date", "date_field", "role", "held")}))
    for u in rec.get("unresolved", []) or []:
        flags.append(Flag("Q7", None, str(plan.get("asof")),
                          f"unresolved-party corporate action {u.get('type')} {u.get('id')} "
                          f"(parties {u.get('parties')}, missing {u.get('missing')})"
                          + ("; it blocks" if u.get("blocks") else "; it does not block"),
                          evidence={k: u.get(k) for k in ("id", "row_id", "type", "date", "date_field",
                                                          "parties", "blocks", "acknowledged")}))
    return (FLAG if flags else OK), flags, None


def q8_seed_diff(close: pd.DataFrame, nav: pd.DataFrame, seed_dir: Path | None) -> tuple[str, list[Flag], str | None]:
    if seed_dir is None:                 # a first-nights check, so its absence is not a defect
        return NOT_RUN, [], "no --seed-dir given (a first-nights check, run by hand on C4's seed)"
    seed_dir = Path(seed_dir)
    missing = [n for n in ("cef_prices.parquet", "cef_nav.parquet") if not (seed_dir / n).is_file()]
    if missing:
        return UNMEASURED, [], f"seed dir {seed_dir} lacks {missing}"
    px = read_long(seed_dir / "cef_prices.parquet", ["date", "close", "ticker"])
    nv = read_long(seed_dir / "cef_nav.parquet", ["date", "nav", "ticker"])
    flags = []
    for label, seed, cur in (("close", wide(px, "close"), close), ("nav", wide(nv, "nav"), nav)):
        for t in set(seed.columns) & set(cur.columns):
            joint = pd.concat([seed[t], cur[t]], axis=1, keys=["seed", "now"]).dropna()
            moved = joint[(joint["seed"] - joint["now"]).abs() > Q8_CENT]
            for d, row in moved.iterrows():
                flags.append(Flag("Q8", t, str(pd.Timestamp(d).date()),
                                  f"{label} replaced by the fetch: {row['seed']:.4f} -> {row['now']:.4f}",
                                  value=float(row["now"]), threshold=float(row["seed"]),
                                  evidence={"series": label}))
    return (FLAG if flags else OK), flags, None


def _collector_report(state_dir: Path, day: dt.date) -> dict | None:
    """The collector's `<state>/data/<day>/report.json` (quantt/collect/collect.py
    `build_report`), or None when the file is absent. Unreadable raises Unmeasured."""
    path = Path(state_dir) / "data" / day.isoformat() / "report.json"
    if not path.is_file():
        return None
    try:
        rep = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise Unmeasured(f"{path} unreadable: {type(e).__name__}: {e}") from None
    if not isinstance(rep, dict) or not isinstance(rep.get("steps"), dict):
        raise Unmeasured(f"{path} is not a collector report (no `steps` object)")
    return rep


def _second_source_state(rep: dict, step: str) -> tuple[str, str | None]:
    """("ok" | "unavailable" | "not_ok" | "absent", the collector's own words).
    `unavailable` is the collector's SECOND SOURCE UNAVAILABLE status: the step is
    not ok and carries `unavailable` (collect.py `collect`, `build_report`)."""
    rec = rep["steps"].get(step)
    if not isinstance(rec, dict):
        return "absent", None
    if rec.get("ok"):
        return "ok", None
    if rec.get("unavailable"):
        return "unavailable", str(rec["unavailable"])
    return "not_ok", str(rec.get("err"))


def q9_second_source(state_dir: Path, asof: dt.date, step: str | None) -> tuple[str, list[Flag], str | None]:
    """Q9: did tonight's NAV cross-check have its second source? (status, flags, why).

    WHY THIS EXISTS (2026-11-18). CEFConnect answered every scripted request with a
    block page from 2026-10-21. On 2026-10-29 the collector was changed, rightly, to
    record that as "second source unavailable" without failing the day (a status
    that was always on said nothing: collect.py `SecondSourceUnavailable`). The
    result was the opposite failure: the fact lived only in the tail of a line that
    begins `DATA COMPLETE`, and the core book decided on single-source NAVs every
    night for three weeks (821 such lines by 2026-11-18) with no report saying so.
    The nightly QA report is what the evening brief reads, so the fact goes here.

    WHAT IT READS. Only the collector's own record for the as-of day,
    `<state>/data/<asof>/report.json`. It fetches nothing and compares no NAV: the
    cross-check is the collector's job, and this reports whether it happened.
      * the step is ok: OK.
      * the step carries `unavailable`: FLAG, quoting the collector's status, with
        the number of consecutive trading days (walking back from the as-of through
        each day's own report.json) it has been unavailable and the first of them.
      * the step is otherwise not ok (failed, or waiting on prices_nav): FLAG,
        quoting its error. Nothing was compared tonight either way.
      * no report.json for the as-of, or it has no such step: UNMEASURED, named.
        "The collector has not run" is not "the cross-check passed".

    NO THRESHOLD, ON PURPOSE. It flags from the first night. "Flag after N days"
    would need an N nobody has derived, and one unverified night is already a fact
    the brief should show; the count says how long. It is outside the false-alarm
    budget above for the same reason: this is a recorded fact about a source, not
    a statistical call that can be a false alarm. It stays FLAG every night until
    a second source answers, which is the point.

    THE STREAK IS MEASURED, NEVER ASSUMED. The walk back stops at the first earlier
    trading day whose report does not say `unavailable`. If it stops because that
    day's report is missing or unreadable, the count is reported as "at least"
    and the evidence names the day: a missing day is not counted either way.

    A book with no second source by ruling (`step` None: C4) is NOT_RUN, said so."""
    if step is None:
        return NOT_RUN, [], ("this book has no second NAV source by ruling (C4 reads no "
                             "CEFConnect, team lead 2026-10-28): single-source NAVs every night")
    try:
        rep = _collector_report(state_dir, asof)
    except Unmeasured as e:
        return UNMEASURED, [], str(e)
    if rep is None:
        return UNMEASURED, [], (f"no collector report at {Path(state_dir) / 'data' / asof.isoformat() / 'report.json'}"
                                f": whether {step} had a second source on {asof} is not known")
    state, words = _second_source_state(rep, step)
    if state == "absent":
        return UNMEASURED, [], f"the collector's report for {asof} has no {step} step"
    if state == "ok":
        return OK, [], None
    if state == "not_ok":
        return FLAG, [Flag("Q9", None, asof.isoformat(),
                           f"{step} did not complete on {asof} ({words}): no panel NAV was "
                           f"checked against a second source",
                           evidence={"step": step, "state": state, "collector": words})], None
    n, first, stopped = 1, asof, None
    d = previous_trading_day(asof)
    while True:
        try:
            prev = _collector_report(state_dir, d)
        except Unmeasured as e:
            stopped = f"{d}: {e}"
            break
        if prev is None:
            stopped = f"{d}: no collector report"
            break
        if _second_source_state(prev, step)[0] != "unavailable":
            break
        n, first = n + 1, d
        d = previous_trading_day(d)
    count = f"at least {n}" if stopped else str(n)
    return FLAG, [Flag("Q9", None, asof.isoformat(),
                       f"{step}: {words}. Unavailable on {count} consecutive trading day(s), "
                       f"since {first}" + (" or earlier" if stopped else "")
                       + ": the book decides on single-source NAVs",
                       value=float(n),
                       evidence={"step": step, "state": state, "collector": words,
                                 "consecutive_days": n, "first_day": first.isoformat(),
                                 "count_is_lower_bound": bool(stopped),
                                 "walk_stopped_at": stopped})], None


# ------------------------------------------------------------------- the run

def run_checks(book: str, panels: Panels, universe: list, thresholds: dict, asof: dt.date,
               expected: dt.date, spec: dict, plan: dict | None, plan_path: str | None,
               splits, seed_dir, *, data_dir: Path) -> dict:
    """The eight panel checks (Q1 to Q8) on `panels`; Q9 is `main`'s, from the collector's record. Pure except for reading `seed_dir` (Q8)."""
    names = held_names(plan)
    results: dict = {}

    def add(qid: str, status: str, flags: list, why: str | None = None):
        for f in flags:
            f.held = f.ticker in names if f.ticker else False
        results[qid] = {"status": status, "flags": [asdict(f) for f in flags], "why": why,
                        "n_flags": len(flags), "n_held": sum(1 for f in flags if f.held)}

    cut = pd.Timestamp(asof)            # nothing after the as-of is read by any check (no lookahead)
    close, volume, nav = panels.close.loc[:cut], panels.volume.loc[:cut], panels.nav.loc[:cut]

    def threshold(key: str):
        t = (thresholds or {}).get(key)
        if t is None:
            raise Unmeasured(f"no calibrated threshold {key!r} for book {book} "
                             f"(results/ops/DATA_QA_CALIBRATION_2026-11-08.md)")
        return t

    flags = q1_freshness(close, nav, universe, expected)
    add("Q1", FLAG if flags else OK, flags)

    if close.empty or nav.empty:
        for qid in ("Q2", "Q3", "Q4", "Q5", "Q6"):
            add(qid, UNMEASURED, [], "the panel is empty")
    else:
        for qid, fn in (("Q2", lambda: q2_flags(q2_candidates(nav, close), threshold("q2_z"),
                                                nav.index[-Q2_REVERT_SESSIONS:])),
                        ("Q3", lambda: q3_flags(q3_candidates(nav, int(threshold("q3_delta"))),
                                                int(threshold("q3_delta")), cut)),
                        ("Q4", lambda: q4_flags(q4_candidates(close, nav, splits), cut,
                                                has_ca_rows=splits is not None)),
                        ("Q5", lambda: q5_result(close, nav, threshold("q5_line"), cut)),
                        ("Q6", lambda: q6_margin_flag(close, volume, nav,
                                                      float(spec["frozen"]["min_adv_usd"]),
                                                      int(spec["frozen"]["min_names"]),
                                                      threshold("q6_margin"), cut))):
            try:
                got = fn()
                flags, note = got if isinstance(got, tuple) else (got, None)
                add(qid, FLAG if flags else OK, flags, note)
            except Unmeasured as e:
                add(qid, UNMEASURED, [], str(e))
            except Exception as e:      # a check's own bug: UNMEASURED, named, and the
                add(qid, UNMEASURED, [],                 # others still run
                    f"{type(e).__name__}: {e}")

    st, flags, why = q7_corporate_actions(plan, plan_path)
    add("Q7", st, flags, why)
    st, flags, why = q8_seed_diff(close, nav, seed_dir)
    add("Q8", st, flags, why)
    return results


def overall(results: dict) -> str:
    states = [r["status"] for r in results.values()]
    if FLAG in states:
        return FLAG
    if UNMEASURED in states:
        return UNMEASURED
    return OK


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def render_md(rep: dict) -> str:
    lines = [f"# Data QA, {rep['book']}, as-of {rep['asof']}",
             "", f"Generated {rep['generated_at']} (report only; nothing here touches an order).",
             f"Expected panel date: {rep['expected_day']}. Overall: **{rep['status']}**.", ""]
    for qid in CHECK_IDS:
        r = rep["checks"].get(qid)
        if r is None:
            continue
        lines.append(f"- **{qid}**: {r['status']}" + (f" ({r['why']})" if r.get("why") else "")
                     + (f", {r['n_flags']} flag(s), {r['n_held']} on held names" if r["n_flags"] else ""))
    flagged = [f for q in CHECK_IDS for f in rep["checks"].get(q, {}).get("flags", [])]
    if flagged:
        lines += ["", "## Flags", ""]
        for f in flagged:
            tag = " WATCH (held or targeted)" if f["held"] else ""
            lines.append(f"- {f['check']} {f.get('ticker') or ''} {f['date']}{tag}: {f['rule']}")
    return "\n".join(lines) + "\n"


def main(argv=None, *, now_utc: dt.datetime | None = None) -> int:
    ap = argparse.ArgumentParser(description="Nightly data QA for one book (report only).")
    ap.add_argument("--book", required=True, choices=sorted(BOOKS))
    ap.add_argument("--state-dir", type=Path, default=None,
                    help="the runner's state dir (default $QUANTT_STATE_DIR)")
    ap.add_argument("--asof", type=dt.date.fromisoformat, default=None,
                    help="report for this date (default: the newest settled trading day)")
    ap.add_argument("--data-dir", type=Path, default=None,
                    help="panel directory (default <repo>/data/<book's dir>)")
    ap.add_argument("--seed-dir", type=Path, default=None, help="C4's seed, for Q8 (first nights)")
    a = ap.parse_args(argv)
    cfg = BOOKS[a.book]
    state_dir = a.state_dir or (Path(os.environ["QUANTT_STATE_DIR"]) if os.environ.get("QUANTT_STATE_DIR") else None)
    if state_dir is None:
        print("REFUSED: no --state-dir and no QUANTT_STATE_DIR", file=sys.stderr)
        return 2
    now = (now_utc or dt.datetime.now(dt.timezone.utc)).astimezone(ET)
    # A run for a given --asof treats that date as the one the panel should end on.
    expected = a.asof or expected_day(now)
    asof = expected
    data_dir = a.data_dir or (REPO / "data" / cfg.data_dir)
    rep = {"book": a.book, "asof": asof.isoformat(), "expected_day": expected.isoformat(),
           "generated_at": now.isoformat(timespec="seconds"), "data_dir": str(data_dir)}
    plan, plan_path = None, None
    try:
        plan, plan_path = latest_plan(state_dir, asof)
        rep["plan"] = plan_path
    except Unmeasured as e:
        rep["plan_error"] = str(e)
    try:
        spec = read_spec(cfg)
        universe = book_universe(cfg, spec)
        start = pd.Timestamp(asof) - pd.Timedelta(days=NIGHTLY_LOOKBACK_DAYS)
        panels = load_panels(data_dir, universe, start=start)
        splits = read_splits(data_dir)
        rep["checks"] = run_checks(a.book, panels, universe, THRESHOLDS.get(a.book) or {}, asof, expected,
                                   spec, plan, plan_path, splits, a.seed_dir, data_dir=data_dir)
    except Unmeasured as e:
        rep["checks"] = {q: {"status": UNMEASURED, "flags": [], "why": str(e), "n_flags": 0, "n_held": 0}
                         for q in CHECK_IDS}
    # Q9 reads the collector's record, not the panels, so it is measured even when
    # the panels could not be read (and is never one of `run_checks`'s pure checks).
    st, q9, why = q9_second_source(state_dir, asof, cfg.second_source_step)
    rep["checks"]["Q9"] = {"status": st, "flags": [asdict(f) for f in q9], "why": why,
                           "n_flags": len(q9), "n_held": 0}
    rep["status"] = overall(rep["checks"])
    out_dir = state_dir / "reports" / "data_qa"
    write_atomic(out_dir / f"{asof.isoformat()}.json", json.dumps(rep, indent=1, default=str))
    write_atomic(out_dir / f"{asof.isoformat()}.md", render_md(rep))
    print(f"data_qa {a.book} {asof}: {rep['status']}; wrote {out_dir}/{asof.isoformat()}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
