"""The desk's one backtest accounting path, for every research family.

WHY THIS FILE EXISTS (2026-10-27). `scripts/cef/band_frontier.py::evaluate()` was
the canonical backtester, and it was wired to one target builder: the CEF
discount sleeve. Every other family -- events (mergers, tenders, ex-dates),
macro fixed-income ETFs, the cross-asset slate -- scored itself in a one-off
script, and there was no ML pipeline at all. The team lead named both gaps and
ruled on 2026-10-27 that evaluate() "may be restructured as necessary". This
module is that restructure. `band_frontier.evaluate` now delegates here, and its
output is byte-identical on the live book (proved by hashing; see
`results/research/HARNESS_RESTRUCTURE_2026-10-27.md`).

THE STAGES. This is the layering that Moonshot (quantrocket-llc/moonshot,
strategies/base.py) and pysystemtrade share. Both were read in the 2026-10-27
backtest-infrastructure research, 3-0 verified:

    1. targets   a family's target builder: weights DECIDED at t from data <= t
                 (`cross_sectional_weights`, `event_weights`,
                 `band_frontier.build_targets`)
    2. policy    how much of the target to trade (`band_frontier.band`,
                 `calendar`, `band_gross_capped`)
    3. held      `held(H)` = H.shift(EXEC_LAG). This is the ONLY place the lag
                 exists. A book that does not trade at the next close (it
                 decides and fills inside a session, or holds from one auction
                 to the next) is scored by `evaluate_window` instead, which takes
                 no lag: it takes each row's decision, entry and exit times and
                 asserts them.
    4. gross     `evaluate(H, R)["pnl"]`
    5. costs     `cost_grid`: turnover x bp, one labelled column per grid point,
                 never folded into gross (H3)
    6. borrow    `band_frontier.borrow_charge`: separate and labelled (H4)
    7. report    `report()`: the cost grid, the H5 eras, and the fit and
                 2023 holdout rows (H13)

WHY THE LAG IS A CONSTANT AND NOT AN ARGUMENT. Both frameworks above default to
the desk's timing, and both let a strategy override it. In Moonshot the lag is
two methods "intended to be overridden"; QuantRocket's own trend_day.py example
drops it. In pysystemtrade it is a keyword default, `delayfill=True`. The desk
has already paid for this once: from 2026-07-31 `validate.py` scored shift(1)
while every other number was shift(2) (gross 1.27 -> 0.94 when found). So
nothing here takes a lag. A target builder that wants a different one has to
edit this constant, and `scripts/research/tests/test_harness.py` fails if
anyone does. `scripts/cef/validate.py::EXEC_LAG` is pinned equal to it.

WHY NOT `src/backtest/engine.py`. That Phase-2 ETF engine applies a weight row
dated t "from day t+1's return", which is shift(1). It cannot see the defect H1
exists for. Nothing on the research path calls `run_backtest`, and it is not a
second canonical engine. Do not route a new family through it.

WHY THE STATISTICS CANNOT GUARD LOOKAHEAD. In Gençay (arXiv 2608.27734, 2026), a
deliberately leaky strategy with a Sharpe of 35 passed both the deflated Sharpe
and PBO tests. A multiple-testing bar cannot detect a leak, so the guard has to
be structural: `truncation_check` re-runs a target builder on data cut at each
probe date and refuses any row that moves.
"""
from __future__ import annotations

from typing import Callable, Iterable

import numpy as np
import pandas as pd

# H1. Decide at t, MOC fill at t+1's close, earn the t+2 return. Not a knob.
EXEC_LAG = 2
PERIODS = 252

# H13. Every estimated quantity is fitted before this date. band_frontier
# imports it from here, so there is one copy.
HOLDOUT_START = pd.Timestamp("2023-01-01")

# H5 eras, inclusive bounds. The last era is open-ended, so a panel that
# extends past 2026 stays in it rather than vanishing from every row.
ERAS = (("2005-09", "2005-01-01", "2009-12-31"),
        ("2010-14", "2010-01-01", "2014-12-31"),
        ("2015-19", "2015-01-01", "2019-12-31"),
        ("2020-22", "2020-01-01", "2022-12-31"),
        ("2023-", "2023-01-01", None))

# H3. The real-money view beside the gross headline (team lead, 2026-09-28).
COST_GRID_BP = (5, 15, 30)


class LookaheadError(ValueError):
    """A weight that could have used data from after its own decision.

    Raised by `truncation_check` when a target row changes once the data after its
    date is removed, and by `evaluate_window` when a held row's declared inputs, its
    entry or its decision time are not where the window convention needs them (an
    input at or after the decision, an entry at or before it, a decision on another
    row's session). Both check what the caller's code and declared times say; neither
    can see a price whose own timestamp differs from the one declared."""


# ---------------------------------------------------------------------------
# Stage 3-4: the accounting. One definition of the lag.
# ---------------------------------------------------------------------------

def _check_frames(H: pd.DataFrame, R: pd.DataFrame, *, same_row: bool = False) -> None:
    """Refuse frames the accounting would otherwise misread without a sound.

    `H` with a NaN is refused because `.fillna(0.0)` below exists only to empty
    the first EXEC_LAG rows, which hold nothing yet. A NaN in the middle of `H`
    would become a flat position nobody decided on. A NaN in `R` where the book
    HOLDS the name is refused because pandas' `sum(axis=1)` skips it, and that
    books zero P&L for a day whose return is unknown. A NaN in `R` where nothing
    is held is fine: the book earned nothing there either way.

    `same_row` (added for `evaluate_window`, which shares these refusals rather than
    keeping a copy): the cells held are H's own non-zero cells on the same row, not
    `held(H)`, and the EXEC_LAG row count is not required, because a window book
    has no lag. Every other caller leaves it False and gets exactly the checks
    above, in the same order, with the same messages.
    """
    if not isinstance(H, pd.DataFrame) or not isinstance(R, pd.DataFrame):
        raise TypeError("H and R must be DataFrames (dates x names)")
    if not H.index.equals(R.index):
        raise ValueError("H and R must share one index, row for row")
    if not H.columns.equals(R.columns):
        raise ValueError("H and R must share one column set, in one order")
    if not H.index.is_monotonic_increasing or not H.index.is_unique:
        raise ValueError("the index must be sorted and unique")
    if not same_row and len(H) <= EXEC_LAG:
        raise ValueError(f"need more than {EXEC_LAG} rows, got {len(H)}")
    if H.isna().any().any():
        raise ValueError("H holds NaN; every weight must be decided (0.0 for flat)")
    if not np.isfinite(H.to_numpy(dtype=float)).all():
        raise ValueError("H holds an infinite weight")
    held_mask = H.ne(0.0) if same_row else held(H).ne(0.0)
    unknown = R.isna() & held_mask
    if unknown.any().any():
        i, j = np.argwhere(unknown.to_numpy())[0]
        raise ValueError(
            f"R is NaN on {int(unknown.sum().sum())} name-day(s) the book holds, first "
            f"{R.index[i].date()} {R.columns[j]}; a held position with no return "
            "cannot be booked as zero")


def held(H: pd.DataFrame) -> pd.DataFrame:
    """What the book holds over each return: the weights decided EXEC_LAG
    sessions earlier. Row s of the result earns R[s].

    The first EXEC_LAG rows are 0.0 because nothing has been decided that early.
    This is the only `.fillna` in the accounting, and `_check_frames` has
    already refused a NaN anywhere else in H.
    """
    return H.shift(EXEC_LAG).fillna(0.0)


def evaluate(H: pd.DataFrame, R: pd.DataFrame, *, nan_policy: str = "raise") -> dict:
    """H.loc[t] = weights decided at t. MOC fills at t+1 -> earns the t+2 return.

    The same keys, the same expressions and the same values as
    `band_frontier.evaluate` before 2026-10-27. The live book's output hashes
    identically, and `test_harness.py` holds that on synthetic frames. The
    expression `(held(H) * R).sum(axis=1)` is the old `H.shift(2).fillna(0.0) *
    R`, unchanged except that the lag now has one name.

    nan_policy
      "raise" (the default, and the only choice for new code). A NaN weight,
          misaligned frames, or a missing return on a held name raise (see
          `_check_frames`) where the old line booked a zero.
      "legacy" is the pre-2026-10-27 body verbatim. Pandas aligns the frames,
          a NaN weight is flat, and a NaN return on a held name adds nothing to
          the sum. `band_frontier.evaluate` passes it so that every existing
          caller stays byte-identical. One caller DEPENDS on the skip, and it is
          deliberate and guarded, not a fallback: E1
          (`scripts/events/e1_merger_pair.py`) leaves a CRSP missing-price gap
          NaN after `hold_gaps` has proved that the next return spans it.
          `build_targets()` zero-fills its own panel instead, which on
          2026-10-27 covered 32 of 35,776 held name-days of the live band
          (`results/research/HARNESS_RESTRUCTURE_2026-10-27.md`).
    """
    if nan_policy == "legacy":
        held_ = H.shift(EXEC_LAG).fillna(0.0)
    elif nan_policy == "raise":
        _check_frames(H, R)
        held_ = held(H)
    else:
        raise ValueError("nan_policy must be 'raise' or 'legacy'")
    pnl = (held_ * R).sum(axis=1)
    turn = H.diff().abs().sum(axis=1).fillna(0.0)
    gross_v = H.abs().sum(axis=1).mean()
    return dict(
        gross_sr=pnl.mean() / pnl.std() * np.sqrt(PERIODS),
        ann_ret=pnl.mean() * PERIODS,
        vol=pnl.std() * np.sqrt(PERIODS),
        turn=turn.sum() * PERIODS / len(pnl),
        hold=gross_v / turn.mean() if turn.mean() > 0 else np.inf,
        turn_series=turn,
        pnl=pnl,
    )


def label(R: pd.DataFrame) -> pd.DataFrame:
    """The return a holding decided at t is credited with: R[t + EXEC_LAG].

    An ML target must be this frame and nothing else. A model trained on the
    t -> t+1 return would be scored on a return the desk cannot earn. Qlib's
    default label, Ref($close,-2)/Ref($close,-1)-1, is the same t+1 -> t+2 return
    (qlib.readthedocs.io, component/data, 3-0 verified 2026-10-27).
    `test_harness.py` checks that, row by row, (H * label(R)).sum(axis=1) is
    evaluate's pnl moved back EXEC_LAG rows.

    The last EXEC_LAG rows are NaN, because their return has not happened yet.
    A caller that fills them has invented a label.
    """
    return R.shift(-EXEC_LAG)


# ---------------------------------------------------------------------------
# A window inside or across sessions: the one convention here that is not
# shift(2).
# ---------------------------------------------------------------------------

# The exchange clock that session dates are read on. A window's decision and
# exit times are converted to this zone to find the session each falls on.
SESSION_TZ = "America/New_York"


def _session_date(ts: pd.Series) -> pd.Series:
    """Each tz-aware timestamp's calendar date in SESSION_TZ, as a naive midnight."""
    return ts.dt.tz_convert(SESSION_TZ).dt.normalize().dt.tz_localize(None)


def evaluate_window(H: pd.DataFrame, R: pd.DataFrame, *, info: pd.DataFrame,
                    decided: pd.Series, entered: pd.Series, exited: pd.Series) -> dict:
    """Score a book that decides inside a session and holds over a stated window.

    WHY. `evaluate` scores the close convention: decide at t, fill at t+1's close,
    earn t+2 (EXEC_LAG, which is not a knob). A book that decides at 15:29 on the
    day's move so far, buys at 15:30's quote and sells in that session's closing
    auction cannot be scored there; nor can one that buys in t's closing auction
    and sells in t+1's opening auction. So this convention is declared row by row,
    as timestamps, and asserted.

    INPUTS. One row per session of the book, flat rows included.
      H        weights decided on each row's session (0.0 for flat).
      R        each name's return from its price at entered[t] to its price at
               exited[t]: the entry and exit prices only.
      info     for each cell, the time of the newest datum its weight was built
               from (tz-aware).
      decided, entered, exited   one tz-aware time per row.
    A row whose weights are all zero holds nothing and earns nothing: its times
    and its info may be NaT. A row that holds anything must give all of them.

    REFUSALS, each naming the first offending row:
      * `_check_frames(same_row=True)`: frames not aligned, an index not sorted and
        unique, a NaN or infinite weight, a NaN return on a held cell;
      * an index that is not session dates (tz-naive midnights);
      * a time series not on H's index, not tz-aware, or NaT on a held row; info
        not on H's index and columns, not tz-aware, or NaT on a held cell;
      * decided[t] not on row t's session date in SESSION_TZ. Without this, a set
        of times shifted by one row passes every other check: the shift(1) bug of
        the close convention, in this one's clothing;
      * on a held row, decided >= entered, or entered >= exited;
      * a held row's window ending after the next held row's entry (two rows
        would hold the same capital at once);
      * a held weight whose info is at or after its decision;
      * a window ending on a date that is not a session of H's index. A window may
        end after the last row; that date is added to `pnl`.

    WHAT IT DOES NOT CHECK. It checks the times the caller declares, not each
    price's own timestamp. A caller that declares a quote time other than the one
    its code used, or that prices R from a print other than the one at `exited`,
    passes. The declared times are the contract; the caller proves R matches them,
    for instance by recomputing sample rows from the raw prices.

    OUTPUT. `pnl` is dated by the session each window ENDS on (exited's date in
    SESSION_TZ), as `evaluate` dates P&L by the session it is earned on: a window
    entered at t's close and exited at t+1's open is t+1's P&L. A session on which
    no window ends earns 0.0. `pnl_by_row` is the same P&L on its decision row, and
    `exit_session` the session each held row's window ends on. gross_sr, ann_ret
    and vol are annualised over every session of `pnl` (H's rows, plus any exit
    date after the last row), so the caller must pass the whole session index and
    not only the rows that hold something: a book on one session in five, passed
    as its held rows alone, would have its return and Sharpe overstated about
    five-fold and two-fold. Turnover counts both legs of each row (in at the entry,
    out at the exit), 2 x gross, annualised the same way.
    """
    _check_frames(H, R, same_row=True)
    idx = H.index
    if not isinstance(idx, pd.DatetimeIndex) or idx.tz is not None or not (idx == idx.normalize()).all():
        raise ValueError("H's index must be session dates: tz-naive midnights")
    held_cell = H.ne(0.0)
    held_row = held_cell.any(axis=1)
    for name, s in (("decided", decided), ("entered", entered), ("exited", exited)):
        if not isinstance(s, pd.Series) or not s.index.equals(idx):
            raise ValueError(f"{name} must be a Series on H's index")
        if not isinstance(s.dtype, pd.DatetimeTZDtype):
            raise ValueError(f"{name} must hold tz-aware timestamps")
        miss = s.isna() & held_row
        if miss.any():
            raise ValueError(f"{name} is NaT on {int(miss.sum())} row(s) that hold a position, "
                             f"first {idx[miss.to_numpy()][0].date()}")
    if not isinstance(info, pd.DataFrame) or not (info.index.equals(idx) and info.columns.equals(H.columns)):
        raise ValueError("info must be a frame on H's index and columns")
    naive = [c for c, dt_ in info.dtypes.items() if not isinstance(dt_, pd.DatetimeTZDtype)]
    if naive:
        raise ValueError(f"info must hold tz-aware timestamps in every column; {naive[:3]} do not")
    hr = held_row.to_numpy()
    rows = idx[hr]
    d, e, x = decided[hr], entered[hr], exited[hr]
    off_day = _session_date(d).to_numpy() != rows.to_numpy()
    if off_day.any():
        k = int(np.argmax(off_day))
        raise LookaheadError(f"row {rows[k].date()}: decided {d.iloc[k]} is not on that row's session "
                             f"in {SESSION_TZ}; the times are not this row's")
    if (d >= e).any():
        k = int(np.argmax((d >= e).to_numpy()))
        raise LookaheadError(f"row {rows[k].date()}: entered {e.iloc[k]} is not after decided {d.iloc[k]}")
    if (e >= x).any():
        k = int(np.argmax((e >= x).to_numpy()))
        raise ValueError(f"row {rows[k].date()}: exited {x.iloc[k]} is not after entered {e.iloc[k]}")
    nxt = e.shift(-1)
    over = ((x > nxt) & nxt.notna()).to_numpy()
    if over.any():
        k = int(np.argmax(over))
        raise ValueError(f"row {rows[k].date()}: its window ends at {x.iloc[k]}, after the next held "
                         f"row's entry {nxt.iloc[k]}")
    if (held_cell & info.isna()).any().any():
        i, j = np.argwhere((held_cell & info.isna()).to_numpy())[0]
        raise LookaheadError(f"row {idx[i].date()} {H.columns[j]}: info is NaT on a held cell; every "
                             "weight must say how old its newest datum is")
    late = held_cell & info.ge(decided, axis=0)
    if late.any().any():
        i, j = np.argwhere(late.to_numpy())[0]
        raise LookaheadError(f"row {idx[i].date()} {H.columns[j]}: built from data at {info.iat[i, j]}, "
                             f"not before its decision at {decided.iloc[i]}")
    exit_session = pd.Series(_session_date(x).to_numpy(), index=rows, name="exit_session")
    inside = exit_session[exit_session <= idx[-1]]
    stray = ~inside.isin(idx)
    if stray.any():
        k = inside.index[stray.to_numpy()][0]
        raise ValueError(f"row {k.date()}: its window ends on {inside[k].date()}, which is not a session "
                         "of H's index")
    pnl_by_row = (H * R.where(held_cell, 0.0)).sum(axis=1)
    dates = idx.union(pd.DatetimeIndex(exit_session[exit_session > idx[-1]].unique()))
    pnl = pd.Series(0.0, index=dates)
    if hr.any():
        by_exit = pnl_by_row[hr].groupby(exit_session.to_numpy()).sum()
        pnl.loc[by_exit.index] += by_exit.to_numpy()
    turn = 2.0 * H.abs().sum(axis=1)
    sd = pnl.std()
    return dict(gross_sr=pnl.mean() / sd * np.sqrt(PERIODS) if sd > 0 else np.nan,
                ann_ret=pnl.mean() * PERIODS, vol=sd * np.sqrt(PERIODS),
                turn=turn.sum() * PERIODS / len(pnl), turn_series=turn,
                pnl=pnl, pnl_by_row=pnl_by_row, exit_session=exit_session)


# ---------------------------------------------------------------------------
# Stage 5 and 7: costs, eras, fit and holdout. Labelled, never mixed.
# ---------------------------------------------------------------------------

def _row_stats(pnl: pd.Series, turn: pd.Series, bps: Iterable[float]) -> dict:
    """Gross Sharpe, return, vol and turnover on a slice, plus one net Sharpe
    per grid point. These are `band_frontier.row`'s formulas: the cost is turn/yr
    x bp, taken off the annual return."""
    if len(pnl) < 2:
        raise ValueError(f"a slice of {len(pnl)} rows has no Sharpe")
    ann, vol = pnl.mean() * PERIODS, pnl.std() * np.sqrt(PERIODS)
    t = turn.mean() * PERIODS
    return dict(start=pnl.index[0].date().isoformat(), end=pnl.index[-1].date().isoformat(),
                n=len(pnl), gross_sr=ann / vol, ann_ret=ann, vol=vol, turn=t,
                net_sr={float(c): (ann - t * c / 1e4) / vol for c in bps})


def cost_grid(res: dict, bps: Iterable[float] = COST_GRID_BP) -> dict:
    """Net Sharpe at each grid point, from an `evaluate` result, labelled by bp.

    `sign_flips` is True when the net Sharpe changes sign across the grid. H3
    says the answer must not do that, so a report has to state it.
    """
    bps = tuple(float(c) for c in bps)
    nets = {c: (res["ann_ret"] - res["turn"] * c / 1e4) / res["vol"] for c in bps}
    signs = {np.sign(v) for v in nets.values()}
    return dict(gross_sr=res["gross_sr"], net_sr=nets, sign_flips=len(signs) > 1)


def report(H: pd.DataFrame, R: pd.DataFrame, *, bps: Iterable[float] = COST_GRID_BP) -> dict:
    """Everything a results table must show, from one `evaluate` call.

    - `full`: gross Sharpe as the headline, with the cost grid beside it.
    - `fit` / `holdout`: split at HOLDOUT_START (H13). Read the holdout row only
      once it has been opened under a pre-registration.
    - `eras`: the H5 eras the sample covers, and era turnover sd/mean (H5).

    Borrow is not here. It scales with holdings, not turnover (H4), so it is
    charged by `band_frontier.borrow_charge` and reported as its own line.

    There is no path here for a window book: `report` calls `evaluate`, which is
    shift(2). A book scored by `evaluate_window` takes its statistics from that
    function's own output, and its splits and eras from its `pnl`, by the caller.
    """
    bps = tuple(bps)
    res = evaluate(H, R)
    pnl, turn = res["pnl"], res["turn_series"]
    out = dict(full=dict(_row_stats(pnl, turn, bps), **{"sign_flips": cost_grid(res, bps)["sign_flips"]}))
    fit = pnl.index < HOLDOUT_START
    if fit.sum() >= 2:
        out["fit"] = _row_stats(pnl[fit], turn[fit], bps)
    if (~fit).sum() >= 2:
        out["holdout"] = _row_stats(pnl[~fit], turn[~fit], bps)
    eras = {}
    for lab, a, b in ERAS:
        m = (pnl.index >= pd.Timestamp(a)) & (True if b is None else pnl.index <= pd.Timestamp(b))
        if m.sum() >= 2:
            eras[lab] = _row_stats(pnl[m], turn[m], bps)
    out["eras"] = eras
    turns = [e["turn"] for e in eras.values()]
    out["era_turn_cv"] = (float(np.std(turns, ddof=1) / np.mean(turns))
                          if len(turns) > 1 and np.mean(turns) > 0 else None)
    out["evaluate"] = res
    return out


# ---------------------------------------------------------------------------
# Stage 1: target builders for families other than the CEF sleeve.
# ---------------------------------------------------------------------------

def cross_sectional_weights(signal: pd.DataFrame, eligible: pd.DataFrame, *,
                            direction: int, scheme: str, min_names: int,
                            on_thin: str) -> pd.DataFrame:
    """Dollar-neutral, gross-1 weights from a signal, one row per decision date.

    This is the CEF sleeve's construction made generic: demean across eligible
    names, then divide by the row's absolute sum. That way a macro-ETF or
    cross-asset idea is sized the way the live book is, instead of the way a
    one-off script happened to choose.

    signal    dates x names. Row t must be built from data <= t; run
              `truncation_check` on the builder to prove it.
    eligible  bool frame on signal's index and columns, with no NaN. True
              means the name may be held at t.
    direction +1 is long high signal, -1 is long low signal. There is no
              default, because the CEF sleeve is -1 (long the cheap fund) and a
              momentum idea is +1, and a default would silently pick one.
    scheme    "rank" (demeaned cross-sectional ranks) or "z" (the demeaned
              signal itself, as the CEF sleeve does).
    on_thin   what a row with fewer than `min_names` eligible names does:
              "flat" (all zero) or "hold" (yesterday's row, as build_targets
              does). There is no default.
    """
    if direction not in (1, -1):
        raise ValueError("direction must be +1 or -1")
    if scheme not in ("rank", "z"):
        raise ValueError("scheme must be 'rank' or 'z'")
    if on_thin not in ("flat", "hold"):
        raise ValueError("on_thin must be 'flat' or 'hold'")
    if min_names < 2:
        raise ValueError("min_names must be at least 2 for a dollar-neutral book")
    if not (eligible.index.equals(signal.index) and eligible.columns.equals(signal.columns)):
        raise ValueError("eligible must share signal's index and columns")
    if eligible.isna().any().any() or not all(dt == bool for dt in eligible.dtypes):
        raise TypeError("eligible must be a bool frame with no NaN")
    inf = np.isinf(signal.to_numpy(dtype=float)) & eligible.to_numpy()
    if inf.any():
        i, j = np.argwhere(inf)[0]
        # An inf (a z-score over a zero sd, i.e. a stale price) used to turn the
        # whole row into NaN, which fillna then zeroed, so on_thin="hold" did not
        # hold (quant-reviewer, 2026-10-28). Refuse it instead.
        raise ValueError(f"signal is infinite on {int(inf.sum())} eligible cell(s), first "
                         f"{signal.index[i].date()} {signal.columns[j]}; a stale input, not a signal")
    S = signal.where(eligible & signal.notna())
    X = S.rank(axis=1) if scheme == "rank" else S
    X = X.sub(X.mean(axis=1), axis=0) * direction
    W = X.div(X.abs().sum(axis=1), axis=0)
    thin = S.notna().sum(axis=1) < min_names
    flat_signal = X.abs().sum(axis=1) == 0           # every eligible name tied
    bad = thin | flat_signal
    W = W.fillna(0.0)
    if on_thin == "flat":
        W.loc[bad] = 0.0
    else:
        W.loc[bad] = np.nan
        W = W.ffill().fillna(0.0)
    return W


def event_weights(events: pd.DataFrame, index: pd.DatetimeIndex, columns: Iterable[str], *,
                  hold: int, sizing: str, unit: float | None = None) -> pd.DataFrame:
    """Holdings for an event book, decided on each event's `decided` session.

    events  columns `decided` (the session on whose close the trade is decided,
            using only information public by then), `ticker` and `side` (+1 or
            -1). Mapping an announcement time to its decision session is the
            caller's job and belongs in the trial's own alignment note: an
            after-close announcement on day d is decided at d+1, not d. A
            `decided` date that is not a session in `index` raises. There is no
            snapping to the nearest session, because snapping forward hides a
            one-day lookahead.
    hold    sessions the position is held. Rows decided .. decided+hold-1 carry
            the weight. With the harness lag, that earns the returns of
            decided+2 .. decided+hold+1.
    sizing  "fixed": each live event carries `unit`, and book gross varies with
            the number of events.
            "calendar_time": book gross is 1 on every day with any NET exposure.
            Each name's netted side is divided by the sum of the absolute
            netted sides. This is the calendar-time portfolio of the
            event-study literature, and it is what makes an event book's
            returns a daily series that evaluate() and the trial registry can
            hold. It is normalised AFTER netting, so offsetting events cannot
            shrink the book: A +1, A -1, B +1 is all of B
            (quant-reviewer, 2026-10-28).
    Two live events in one ticker on one day sum. The weight is netted, as
    the runner nets a symbol into one order (CLAUDE.md landmine 2). A day
    whose events all cancel is flat.
    """
    need = {"decided", "ticker", "side"}
    if not need <= set(events.columns):
        raise ValueError(f"events needs columns {sorted(need)}")
    if hold < 1:
        raise ValueError("hold must be at least one session")
    if sizing not in ("fixed", "calendar_time"):
        raise ValueError("sizing must be 'fixed' or 'calendar_time'")
    if sizing == "fixed" and (unit is None or not np.isfinite(unit) or unit <= 0):
        raise ValueError("sizing='fixed' needs a positive unit weight")
    if sizing == "calendar_time" and unit is not None:
        raise ValueError("calendar_time sizing sets its own weights; do not pass unit")
    cols = list(columns)
    idx = pd.DatetimeIndex(index)
    if not idx.is_monotonic_increasing or not idx.is_unique:
        raise ValueError("index must be sorted and unique")
    ev = events.copy()
    ev["decided"] = pd.to_datetime(ev["decided"])
    if not ev["side"].isin([1, -1]).all():
        raise ValueError("side must be +1 or -1 on every event")
    off = ~ev["decided"].isin(idx)
    if off.any():
        raise ValueError(f"{int(off.sum())} event(s) decided on a non-session, first "
                         f"{ev.loc[off, 'decided'].iloc[0].date()}; map each to its decision session")
    unknown = sorted(set(ev["ticker"]) - set(cols))
    if unknown:
        raise ValueError(f"events name tickers outside the column set: {unknown[:5]}")
    side = np.zeros((len(idx), len(cols)))
    pos = idx.get_indexer(ev["decided"])
    cpos = pd.Index(cols).get_indexer(ev["ticker"])
    for p, c, s in zip(pos, cpos, ev["side"].to_numpy()):
        end = min(p + hold, len(idx))
        side[p:end, c] += s
    if sizing == "fixed":
        W = side * unit
    else:
        gross = np.abs(side).sum(axis=1)
        W = np.zeros_like(side)
        on = gross > 0
        W[on] = side[on] / gross[on][:, None]
    return pd.DataFrame(W, index=idx, columns=cols)


# ---------------------------------------------------------------------------
# The structural lookahead guard.
# ---------------------------------------------------------------------------

def truncation_check(build: Callable[[pd.Timestamp | None], pd.DataFrame],
                     probes: Iterable, *, atol: float = 0.0) -> dict:
    """Prove a target builder is causal. Rebuild it on data cut at each probe
    date, and require that row to equal the full-sample row.

    `build(end)` must return the targets computed from raw inputs truncated at
    `end` (inclusive); `build(None)` is the full sample. `band_frontier.build_panel(end=...)`
    is the pattern. The cut has to happen BEFORE anything is computed, so a
    rolling mean, a normaliser or a fitted scalar cannot see past it. This
    catches what pysystemtrade's default forecast-scalar backfill does: copy the
    first fitted estimate back over earlier history. Its author's code comment
    calls that "SLIGHTLY CHEATING" (3-0 verified, 2026-10-27).

    `atol` is 0.0 by default: a causal builder reproduces its row exactly.
    Raise it only with a stated reason, such as a solver's tolerance.
    Raises LookaheadError naming the first row that moved.

    Three ways a leaky builder used to pass (quant-reviewer, 2026-10-28), each
    now refused:
    - no probes at all;
    - a builder that ignores `end` (its cut reaches past d);
    - a full-sample column the cut lacks. A name that lists after d, filled
      backwards into d, carried a weight built only from future data and was
      never compared.
    """
    probes = list(probes)
    if not probes:
        raise ValueError("no probes: a check that compares nothing proves nothing")
    full = build(None)
    checked = []
    for d in probes:
        d = pd.Timestamp(d)
        if d not in full.index:
            raise ValueError(f"probe {d.date()} is not a row of the full-sample targets")
        cut = build(d)
        if len(cut.index) and cut.index.max() > d:
            raise LookaheadError(f"the build cut at {d.date()} returns rows up to "
                                 f"{cut.index.max().date()}; the builder ignores `end`")
        if d not in cut.index:
            raise ValueError(f"the build cut at {d.date()} has no row for {d.date()}")
        row = full.loc[d]
        live = row[row.notna() & row.ne(0.0)].index
        missing = sorted(set(live) - set(cut.columns))
        if missing:
            raise LookaheadError(f"row {d.date()} holds {missing[:5]} in the full sample, but the "
                                 "build cut at that date has no such column; the weight came from later data")
        a = row.reindex(cut.columns).to_numpy(dtype=float)
        b = cut.loc[d].to_numpy(dtype=float)
        if not np.allclose(a, b, rtol=0.0, atol=atol, equal_nan=True):
            k = int(np.argmax(~np.isclose(a, b, rtol=0.0, atol=atol, equal_nan=True)))
            raise LookaheadError(
                f"row {d.date()} changed when data after it was removed "
                f"({cut.columns[k]}: full {a[k]!r} vs cut {b[k]!r}); the builder reads the future")
        checked.append(d.date().isoformat())
    return dict(passed=True, probes=checked)
