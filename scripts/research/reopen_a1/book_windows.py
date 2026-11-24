"""A1 re-open: do the live CEF book's SHORTS lose money inside share-issuance programme windows?

    # the caches A1's own reproducer names (results/events/A1_CEF_ISSUANCE_GATE_2026-10-20.md)
    W="$(git rev-parse --path-format=absolute --git-common-dir)/../.claude/worktrees"
    python3 -m scripts.research.reopen_a1.book_windows \\
      --edgar-cache "$W/ss-cef-events/results/events/_cache_edgar" \\
      --crsp-cache "$W"/{research-ss-expansion,ss-cef-events,research-cef-events,ss-e1-hedge,trial-events-e1,research-edgar}/results/events/_cache_crsp
    python3 -m pytest scripts/research/tests/test_reopen_a1.py

ZERO TRIALS. REPORT ONLY. FIT PERIOD ONLY. No counter, spec or RESEARCH_STATE edit.
The team lead approved this measurement on 2026-10-28 (`docs/SYSTEM.md` §5, row
"Re-opens (3) and (4)": "A1: run the zero-trial live-book measurement"). It is
item 1 of §7 of `results/events/A1_CEF_ISSUANCE_GATE_2026-10-20.md`, built the way
`scripts/events/g6_corporate_action_shorts.py` measured tenders and mergers.

Nothing here opens a network connection (`ops.netguard` is installed first), reads a
credential, touches R2, or calls a broker. The A1 census is re-run from the cached
EDGAR indexes and CRSP extracts exactly as A1's reproducer runs it; a missing cache
raises, naming it. The CRSP check reads the same cached extracts.

WHY THE QUESTION
----------------
A1 found that 18.1% of the fit-period book's short name-days fell inside a deployed
name's programme window (A1 §5.4) and did not ask what they earned: its brief
excluded strategy P&L. Two stories predict opposite signs. (a) An at-the-market
programme runs only while the fund trades at a premium the sponsor can sell into,
so a window marks persistent excess demand: the z-score reads the premium as rich
and shorts into a price that demand keeps up. Shorts lose. (b) The sponsor's sales
cap and compress the premium (A1 §4: 6 of 7 lower 63 sessions on). Shorts gain.
The measurement does not pick between them in advance; it measures the sign.

WHAT IS FIXED BEFORE ANY RETURN IS READ (the code computes holdings-only quantities
first and records them before it builds a single P&L figure)
---------------------------------------------------------------------------------
1. **The windows are A1's, not redefined.** `a1.census` on the caches, then exactly
   `a1.book_exposure`'s "programme_episode" selection: an EDGAR supplement episode
   of a deployed name, first supplement before 2023-01-01, at least
   `a1.PROGRAMME_MIN_SUPPLEMENTS` supplements, not classed `rights`; window = first
   supplement .. last supplement, cut at the fit panel's last session. The list is
   asserted equal to the one A1 committed (`a1_levels_2026-10-20.json`), and A1's
   two counts (all short name-days; those inside) are re-measured on this book and
   asserted equal to the committed ones. If either moves, the run stops.
2. **The book** is the live policy on the harness: `build_targets` on the price and
   NAV panels CUT AT 2022-12-30 before any computation (`source=`), `fit_only`,
   then `band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)` from the frozen spec.
   Two return views, each labelled, never mixed:
   * TOTAL (H15): `total_returns`, whose distribution and split inputs are proved
     unchanged by a cut at 2022-12-30 (`assert_return_inputs_cut`);
   * PAPER: price returns, because Alpaca paper pays no distributions (CLAUDE.md
     landmine 1; the team lead's 2026-10-28 ruling makes paper's own P&L decide
     paper admission). A short pays the distribution in the first and not in the
     second, and the windows sit in high-distribution PIMCO funds.
3. **The unit.** A short name-day is (decision session t, name i) with H[t, i] < 0,
   t from the book's first live decision. Its P&L is H[t, i] * label(R)[t, i] =
   H[t, i] * R[t+2, i] (`harness.label`, H1): the position decided at t, filled at
   t+1's close, earning t+2. Summed over names that is `evaluate()`'s P&L moved back
   two rows (asserted). The two last decisions earn in 2023 and are dropped.
4. **Inside** means the window covers the DECISION session: first supplement <= t
   <= end. A filing dated t is public by 17:30 ET and the book decides in the
   evening (G6's alignment). The START is therefore causal. THE END AND THE
   PROGRAMME LABEL ARE NOT: the window ends at the episode's last supplement, and
   "programme" counts the episode's later filings (A1 §3: "an ex-post label, fit for
   description and not for trading"). Four of the seven windows end only because
   the fit period ends; their last supplements are 2024-26 EDGAR filings (dates, not
   prices). So the block below is an ex-post-window counterfactual, not a tradable
   rule; a tradable one would read the first supplement's cover (A1 §7 item 2).
5. **The statistic** (`inference.clustered_mean_diff`, SEs clustered by decision
   date, H6): mean P&L per short name-day inside and outside, and
   estimate = mean_outside - mean_inside, signed so that POSITIVE means the
   in-window shorts earn LESS (the question's direction). `read_result(estimate,
   se, meaningful, n_trials=1)`: one zero-trial conditioner measurement.
6. **`meaningful`**, declared here: the smallest difference that could pay for
   acting on it. Acting is the block (item 7); its cost is the turnover it adds,
   which is a property of holdings, not returns. So
       meaningful = 15bp x (turnover the block adds) / (in-window short name-days),
   in book return per name-day: the block's round-trip cost per name-day it
   blocks, at the grid's middle point. It is computed before any return. A block
   that adds no turnover has no cost hurdle and the run raises rather than invent one.

   **REVISION 1 (2026-10-28, after the first run and BEFORE any return was read).**
   The first run raised exactly there: the block REMOVES turnover (-10.0 turns over
   the window, about -1.05 a year). The book trades its in-window shorts inside the
   windows, at the band's edges and whenever the 1.80x gross ceiling rescales the
   book, and blocking them deletes those trades along with adding the entry and
   exit. So acting on the conditioner has no cost to clear, and the rule above
   cannot be formed. The run stopped before the first P&L line (the code computes
   holdings-only quantities first), so no return informed the replacement, which is
   the round-trip cost of the positions themselves, at the grid's middle point,
   per name-day they span:
       meaningful = 15bp x 2 x sum over spells of mean|w| / (in-window name-days),
   where a spell is a maximal run of consecutive decision sessions on which the name
   is held on that side inside a window. A per-name-day difference smaller than
   what one open and one close of the position costs, spread over its spell, cannot
   pay for any rule that trades on it. The unit-return split uses the same rule per
   unit of weight (15bp x 2 x spells / name-days), and each side (shorts; the long
   control) gets its own hurdle by the same rule. A1 §7's kill line is reported as
   computed; with negative added turnover it cannot bind, and the JSON says so.
7. **The block**, fixed and not tuned: G6's filter. Where the book would be short a
   name on a decision session inside its window, hold it flat
   (`H.where(~((H < 0) & M), 0.0)`); everything else is the book's. On exit it trades
   back to what the book holds. Because `evaluate` is linear, the block's daily
   gross P&L is the book's minus the in-window shorts' (asserted to 1e-15). Gross
   Sharpe and net at 5 / 15 / 30bp (the harness's `_row_stats`, the formula
   `report()` uses) for both, the change, and the H5 eras, on the window from the
   first session the book holds a position to 2022-12-30 (the sibling note
   `results/research/REOPEN_BOOK_NAVTENDER_E1_2026-10-28.md`'s window, so the book
   row can be checked against it). The comparison is not turnover-matched (H2): the
   block's added turnover IS its cost, charged in the net columns.
8. **The negative control** (H12): the same split on the book's LONGS. Story (a)
   says only shorts are hurt: in-window longs should do no worse (the price is held
   up). A long split as adverse as the short split says the effect is the names or
   the years, not the windows.
9. **Second methods.** (i) Within-date: on each decision date holding shorts both
   inside and outside, d_t = mean_outside(t) - mean_inside(t); its mean and
   Newey-West t (`inference.newey_west_t`). This removes every date effect, which
   matters because the windows sit in 2016-17 and 2018-22 only. (ii) An independent
   price source: the same positions priced on CRSP daily `ret` (total) and `retx`
   (price), pre-2023 by construction. Each must agree with the panel in sign; if
   they disagree, both are printed and neither is picked.
10. **Borrow** (H4), real money only: what the in-window shorts would have paid at
   IBKR's fee panel (`band_frontier.borrow_charge`), on the panel's own span only
   (2021-09-13 onward, cut at 2022-12-30). Paper charges none.

A1 §7's kill line, re-measured here (H14): if the in-window short P&L a year is
smaller than the block's added turnover x 5bp, the filter is immaterial.

ADDED AFTER THE SECOND RUN, descriptive only (`in_window_short_sources`,
`largest_in_window_short_days`): the in-window short P&L by calendar year; without
2020-02-15..04-30 (the crash span the sibling note excludes, reused rather than
chosen); on the borrow panel's own span, gross and net of the borrow item 10
measures, so the two net on like dates; and the five largest in-window short days
with CRSP's return for the same cell. None of them enters a reading or the block's rows.

PUBLIC REPOSITORY. Tracked outputs carry aggregates and EDGAR facts only. No CRSP
row or permno is written to a tracked file; the CRSP check reports totals, as G6's
did.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:  # run as a script, not -m
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "research" / "reopen_a1"
CACHE = OUT / "_cache_reopen_a1"                 # gitignored (results/**/_cache_*)
SUMMARY_OUT = OUT / "reopen_a1_2026-10-28.json"
WINDOWS_OUT = OUT / "reopen_a1_windows.csv"      # EDGAR facts only: tracked
A1_LEVELS = REPO / "results" / "events" / "a1" / "a1_levels_2026-10-20.json"
FIT_LAST = pd.Timestamp("2022-12-30")            # the last session before the 2023-01-01 holdout
MEANINGFUL_COST_BP = 15.0                        # the grid's middle point (item 6)
KILL_LINE_BP = 5.0                               # A1 §7 item 1
N_TRIALS = 1                                     # a zero-trial conditioner measurement
# The crash span `results/research/REOPEN_BOOK_NAVTENDER_E1_2026-10-28.md` excludes in its
# rho sensitivity; reused, not chosen from this measurement's P&L (added after run 2).
CRASH_SPAN = (pd.Timestamp("2020-02-15"), pd.Timestamp("2020-04-30"))
TOP_DAYS = 5                                     # largest in-window short days listed (added after run 2)
BP = 1e4


class ReopenA1Error(RuntimeError):
    """An input is missing or does not reproduce. Names what, never guesses."""


# ============================================================ windows (A1's, reused)

def programme_windows(eps: pd.DataFrame, universe, last: pd.Timestamp) -> pd.DataFrame:
    """A1's programme windows on the deployed names, selected exactly as
    `a1_cef_issuance_gate.book_exposure` selects them ("programme_episode").

    `eps` is `a1.census(...)["_eps"]`. One row per (episode, deployed ticker); the
    end is the last supplement, cut at `last` (the fit panel's last session)."""
    from scripts.events import a1_cef_issuance_gate as a1
    dep = eps[eps["deployed"].notna() & (eps["first_date"] < a1.TIME_HOLDOUT)]
    sel = (dep["programme"] & (dep["crsp_class"] != "rights")).to_numpy()
    rows = []
    for r in dep[sel].itertuples():
        for t in str(r.deployed).split(";"):
            if t not in universe:            # book_exposure skips a ticker the book does not hold
                continue
            end = min(pd.Timestamp(r.last_date), last)
            rows.append({"ticker": t, "company": r.company, "first_supplement": pd.Timestamp(r.first_date),
                         "last_supplement": pd.Timestamp(r.last_date), "start": pd.Timestamp(r.first_date),
                         "end": end, "first_filing": pd.Timestamp(r.first_date),
                         "n_supplements": int(r.n_supplements),
                         "end_basis": "fit period ends" if pd.Timestamp(r.last_date) > last else "last supplement"})
    return pd.DataFrame(rows)


def window_labels(w: pd.DataFrame) -> list[str]:
    """The windows as A1's JSON writes them: 'TICKER first..end'."""
    return [f"{x.ticker} {x.start.date()}..{x.end.date()}" for x in w.itertuples()]


def assert_matches_a1(w: pd.DataFrame, H: pd.DataFrame, M: pd.DataFrame, first_live: pd.Timestamp,
                      committed: dict) -> dict:
    """The windows and A1's two counts must reproduce the committed A1 output."""
    want = committed["book_exposure_fit_period"]
    got_w = window_labels(w)
    if sorted(got_w) != sorted(want["programme_episode"]["windows"]):
        raise ReopenA1Error(f"the rebuilt windows {got_w} differ from A1's committed "
                            f"{want['programme_episode']['windows']}")
    short = (H < 0).loc[first_live:]
    n_all = int(short.sum().sum())
    n_in = int((short & M.loc[first_live:]).sum().sum())
    if n_all != want["short_name_days_total"] or n_in != want["programme_episode"]["short_name_days_in_windows"]:
        raise ReopenA1Error(f"short name-days {n_all} (inside {n_in}) do not reproduce A1's committed "
                            f"{want['short_name_days_total']} ({want['programme_episode']['short_name_days_in_windows']}): "
                            "this is not the book A1 counted")
    if str(first_live.date()) != want["book_first_live"]:
        raise ReopenA1Error(f"first live decision {first_live.date()} is not A1's {want['book_first_live']}")
    return {"windows_equal_a1_committed": True, "short_name_days_all": n_all, "short_name_days_inside": n_in,
            "first_live_decision": str(first_live.date())}


# ============================================================ the book (fit-cut panels)

def assert_return_inputs_cut(bf, R: pd.DataFrame, cut_prices: Path) -> dict:
    """`total_returns` reads the full distribution, split and price panels. Prove that
    cutting each at 2022-12-30 changes no cell it builds on the fit index. The same
    check as `scripts/research/reopen_book/reopen_book.py` (branch research-reopen-book,
    not on main), restated because that module is not importable from here."""
    from scripts.research.harness import HOLDOUT_START
    dist = pd.read_parquet(bf.DATA_DIR / "cef_distributions.parquet")
    dist_cut = dist[pd.to_datetime(dist["ex_date"]) < HOLDOUT_START]
    y_full = bf.distribution_yield(R.index, R.columns)
    y_cut = bf.distribution_yield(R.index, R.columns, dist=dist_cut, prices=cut_prices)
    sp = pd.read_parquet(bf.DATA_DIR / "cef_splits.parquet")
    sp_cut = sp[pd.to_datetime(sp["ex_date"]) < HOLDOUT_START]
    k_full = bf.split_factor(R.index, R.columns)
    k_cut = bf.split_factor(R.index, R.columns, splits=sp_cut)
    for lab, a, b in (("distribution yield", y_full, y_cut), ("split factor", k_full, k_cut)):
        if not (a.index.equals(b.index) and a.columns.equals(b.columns) and np.array_equal(a.values, b.values)):
            raise AssertionError(f"the {lab} changes when its inputs are cut at 2022-12-30: a 2023+ value reaches it")
    return {"distribution_rows_after_cut_ignored": int(len(dist) - len(dist_cut)),
            "split_rows_after_cut_ignored": int(len(sp) - len(sp_cut)),
            "yield_and_split_factor_identical_with_inputs_cut": True}


def book() -> tuple[pd.DataFrame, dict, dict]:
    """(H, {view: R}, provenance): the live policy on panels cut at 2022-12-30."""
    from scripts.cef import band_frontier as bf
    from scripts.cef.spec import BAND_WIDTH, LIVE_POLICY, MAX_GROSS_STRESS, SPEC_ID, summary
    from scripts.research.harness import HOLDOUT_START
    if MAX_GROSS_STRESS is None:
        raise ReopenA1Error("the spec has no max_gross_stress; the live policy label would not match")
    CACHE.mkdir(parents=True, exist_ok=True)
    prov = {"spec": SPEC_ID, "spec_summary": summary(), "live_policy": LIVE_POLICY}
    paths = []
    for name in ("cef_prices", "cef_nav"):
        df = pd.read_parquet(bf.DATA_DIR / f"{name}.parquet")
        d = pd.to_datetime(df["date"])
        prov[f"{name}_panel_last"] = str(d.max().date())
        cut = df[d < HOLDOUT_START]
        last = pd.to_datetime(cut["date"]).max()
        if last != FIT_LAST:
            raise ReopenA1Error(f"{name} cut at 2023-01-01 ends {last.date()}, not {FIT_LAST.date()}")
        prov[f"{name}_cut_last"] = str(last.date())
        p = CACHE / f"{name}_fit_cut.parquet"
        cut.to_parquet(p)
        paths.append(p)
    T, R = bf.build_targets(source=tuple(paths))
    T, R = bf.fit_only(T, R)                          # asserts nothing reaches 2023-01-01
    if T.index.max() != FIT_LAST:
        raise ReopenA1Error(f"targets end {T.index.max().date()}, not {FIT_LAST.date()}")
    prov["return_inputs"] = assert_return_inputs_cut(bf, R, paths[0])
    Rt = bf.total_returns(R)
    if Rt.index.max() >= HOLDOUT_START or R.index.max() >= HOLDOUT_START:
        raise AssertionError("holdout leak in a return matrix")
    H = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)
    prov.update({"targets_first": str(T.index[0].date()), "targets_last": str(T.index[-1].date()),
                 "band_width": BAND_WIDTH, "max_gross_stress": MAX_GROSS_STRESS})
    return H, {"total": Rt, "paper": R}, prov


# ============================================================ name-days and the split

def name_days(H: pd.DataFrame, R: pd.DataFrame, M: pd.DataFrame, first_live: pd.Timestamp,
              side: str) -> pd.DataFrame:
    """Long form: one row per (decision date, name) on `side` ('short' or 'long'), with
    w = H[t,i], pnl = w * R[t+2,i] (`harness.label`), unit = sign(w) * R[t+2,i], and
    inside = M[t,i]. Decisions from `first_live`; the last EXEC_LAG decisions, which
    earn after the fit period, are dropped (and only those)."""
    from scripts.research.harness import EXEC_LAG, label
    if side not in ("short", "long"):
        raise ValueError("side must be 'short' or 'long'")
    if not (H.index.equals(R.index) and H.index.equals(M.index) and list(H.columns) == list(R.columns) == list(M.columns)):
        raise ValueError("H, R and M must share index and columns")
    L = label(R)                                   # row t holds R[t+2]: H1's alignment, one definition
    nan_rows = L.index[L.isna().all(axis=1)]
    if not nan_rows.equals(L.index[-EXEC_LAG:]):
        raise AssertionError("label(R) is NaN on rows other than the last EXEC_LAG: the alignment moved")
    pos = (H < 0) if side == "short" else (H > 0)
    rows = pos.loc[first_live:].iloc[:-EXEC_LAG]
    st = rows.stack()
    st = st[st]
    idx = st.index
    w = H.stack().reindex(idx)
    r = L.stack(future_stack=True).reindex(idx)
    if r.isna().any():
        raise ValueError(f"{int(r.isna().sum())} {side} name-days have no t+2 return")
    out = pd.DataFrame({"date": idx.get_level_values(0), "ticker": idx.get_level_values(1),
                        "w": w.to_numpy(), "ret_t2": r.to_numpy(),
                        "inside": M.stack().reindex(idx).to_numpy(dtype=bool)})
    out["pnl"] = out["w"] * out["ret_t2"]
    out["unit"] = np.sign(out["w"]) * out["ret_t2"]
    return out


def split(df: pd.DataFrame, value: str, meaningful: float) -> dict:
    """Inside vs outside, clustered by decision date; estimate = outside - inside
    (positive: the in-window positions earn LESS). Values in bp."""
    from scripts.research.inference import clustered_mean_diff, read_result
    c = clustered_mean_diff(df[value].to_numpy(), df["inside"].to_numpy(dtype=bool), df["date"].to_numpy())
    est, se = -c["diff"], c["se_diff"]
    rr = read_result(est, se, meaningful, n_trials=N_TRIALS)
    b = lambda x: round(float(x) * BP, 4)
    return {"inside": {"mean_bp": b(c["mean_a"]), "se_bp": b(c["se_a"]), "n": c["n_a"], "dates": c["clusters_a"]},
            "outside": {"mean_bp": b(c["mean_b"]), "se_bp": b(c["se_b"]), "n": c["n_b"], "dates": c["clusters_b"]},
            "estimate_out_minus_in_bp": b(est), "se_bp": b(se), "dates": c["clusters"],
            "meaningful_bp": b(meaningful),
            "read_result": {"outcome": rr["outcome"], "lo_bp": b(rr["lo"]), "hi_bp": b(rr["hi"]),
                            "t": round(rr["t"], 3), "alpha_adj": rr["alpha_adj"],
                            "power_at_meaningful": round(rr["power_at_meaningful"], 3),
                            "vs_meaningful": rr["vs_meaningful"]}}


def within_date(df: pd.DataFrame, value: str) -> dict:
    """Second method: d_t = mean_outside(t) - mean_inside(t) on dates with both; NW t."""
    from scripts.research.inference import newey_west_t
    g = df.groupby(["date", "inside"])[value].mean().unstack()
    both = g.dropna()
    if True not in both.columns or False not in both.columns or len(both) < 3:
        raise ReopenA1Error("fewer than three dates hold name-days both inside and outside")
    d = (both[False] - both[True]).sort_index()
    return {"dates": int(len(d)), "dates_dropped_one_side_only": int(len(g) - len(both)),
            "mean_bp": round(float(d.mean()) * BP, 4), "nw_t": round(newey_west_t(d.to_numpy()), 3)}


def by_group(df: pd.DataFrame, key: pd.Series, value: str) -> dict:
    """Mean (bp) and n inside / outside per group label: description, no test."""
    out = {}
    for k, g in df.groupby(key):
        rec = {}
        for lab, m in (("inside", g["inside"]), ("outside", ~g["inside"])):
            rec[lab] = {"n": int(m.sum()), "mean_bp": round(float(g.loc[m, value].mean()) * BP, 4) if m.any() else None}
        out[str(k)] = rec
    return out


def era_of(dates: pd.Series) -> pd.Series:
    from scripts.research.harness import ERAS
    lab = pd.Series(index=dates.index, dtype=object)
    for name, a, b in ERAS:
        m = (dates >= pd.Timestamp(a)) & (True if b is None else dates <= pd.Timestamp(b))
        lab[m] = name
    if lab.isna().any():
        raise ReopenA1Error("a date falls in no H5 era")
    return lab


def spell_hurdle(H: pd.DataFrame, M: pd.DataFrame, first_live: pd.Timestamp, side: str) -> dict:
    """Revision 1's `meaningful`, from holdings only: 15bp x a round trip (2 x mean|w|)
    per spell, over the in-window name-days of `side`. Spells are maximal runs of
    consecutive decision sessions held on that side inside a window, on the same
    decision rows `name_days` uses (from `first_live`, last EXEC_LAG dropped)."""
    from scripts.research.harness import EXEC_LAG
    pos = ((H < 0) if side == "short" else (H > 0)) & M
    P = pos.loc[first_live:].iloc[:-EXEC_LAG]
    W = H.abs().loc[P.index]
    rt_w, n_spells, n_days = 0.0, 0, int(P.sum().sum())
    lengths = []
    for c in P.columns:
        x = P[c].to_numpy()
        if not x.any():
            continue
        run_id = np.cumsum(np.r_[True, x[1:] != x[:-1]])
        for k in np.unique(run_id[x]):
            m = run_id == k
            rt_w += 2.0 * float(W[c].to_numpy()[m].mean())
            n_spells += 1
            lengths.append(int(m.sum()))
    if n_days == 0 or n_spells == 0:
        raise ReopenA1Error(f"no in-window {side} name-days: no hurdle, and nothing to split")
    c = MEANINGFUL_COST_BP / BP
    return {"spells": n_spells, "name_days": n_days, "median_spell_sessions": float(np.median(lengths)),
            "meaningful_pnl": c * rt_w / n_days, "meaningful_unit": c * 2.0 * n_spells / n_days}


# ============================================================ the block

def blocked(H: pd.DataFrame, M: pd.DataFrame) -> pd.DataFrame:
    """G6's filter: flat where the book would be short inside a window; else the book."""
    return H.where(~((H < 0) & M), 0.0)


def row_stats(pnl: pd.Series, turn: pd.Series) -> dict:
    """The harness's row formula (`harness._row_stats`, which `report()` calls), on a slice."""
    from scripts.research.harness import COST_GRID_BP, _row_stats
    s = _row_stats(pnl, turn, COST_GRID_BP)
    return {"start": s["start"], "end": s["end"], "n": s["n"], "gross_sr": round(s["gross_sr"], 4),
            "ann_ret_pct": round(s["ann_ret"] * 100, 4), "vol_pct": round(s["vol"] * 100, 4),
            "turn_per_yr": round(s["turn"], 4),
            "net_sr": {f"{int(c)}bp": round(v, 4) for c, v in s["net_sr"].items()}}


def block_counterfactual(H: pd.DataFrame, R: pd.DataFrame, M: pd.DataFrame, held_from: pd.Timestamp) -> dict:
    """Book vs block on [held_from, end]: full window and H5 eras, plus the change."""
    from scripts.research.harness import ERAS, evaluate, held
    Hb = blocked(H, M)
    S_in = H.where((H < 0) & M, 0.0)
    eb, ek, es = evaluate(H, R), evaluate(Hb, R), evaluate(S_in, R)
    gap = float((eb["pnl"] - ek["pnl"] - es["pnl"]).abs().max())
    if gap > 1e-15:
        raise AssertionError(f"book - block != in-window short P&L (max {gap:.2e}): evaluate is not linear here")
    win = eb["pnl"].index >= held_from
    out = {}
    for lab, a, b in (("window", None, None),) + tuple(ERAS):
        m = win.copy()
        if a is not None:
            m &= (eb["pnl"].index >= pd.Timestamp(a)) & (True if b is None else eb["pnl"].index <= pd.Timestamp(b))
        if m.sum() < 2:
            continue
        rb, rk = row_stats(eb["pnl"][m], eb["turn_series"][m]), row_stats(ek["pnl"][m], ek["turn_series"][m])
        out[lab] = {"book": rb, "block": rk,
                    "change": {"gross_sr": round(rk["gross_sr"] - rb["gross_sr"], 4),
                               "ann_ret_pct": round(rk["ann_ret_pct"] - rb["ann_ret_pct"], 4),
                               "turn_per_yr": round(rk["turn_per_yr"] - rb["turn_per_yr"], 4),
                               "net_sr": {k: round(rk["net_sr"][k] - rb["net_sr"][k], 4) for k in rb["net_sr"]}}}
    turns = {k: v["book"]["turn_per_yr"] for k, v in out.items() if k != "window"}
    tv = np.array(list(turns.values()))
    out["era_turn_cv_book"] = round(float(tv.std(ddof=1) / tv.mean()), 4) if len(tv) > 1 else None
    net_b = held(H).sum(axis=1)[win]
    net_k = held(Hb).sum(axis=1)[win]
    out["mean_net_held_weight"] = {"book": round(float(net_b.mean()), 5), "block": round(float(net_k.mean()), 5),
                                   "block_days_net_long_by_more_than_book": int((net_k > net_b + 1e-12).sum())}
    out["_series"] = pd.DataFrame({"book": eb["pnl"], "block": ek["pnl"], "in_window_short": es["pnl"],
                                   "turn_book": eb["turn_series"], "turn_block": ek["turn_series"]})
    return out


# ============================================================ borrow (real money; H4)

def borrow_line(H: pd.DataFrame, M: pd.DataFrame) -> dict:
    """What the in-window shorts would have paid at IBKR's fees, on the fee panel's span."""
    from scripts.cef import band_frontier as bf
    from scripts.research.harness import HOLDOUT_START
    b = pd.read_parquet(bf.DATA_DIR / "cef_borrow_history.parquet")
    b["date"] = pd.to_datetime(b["date"])
    b = b[b["date"] < HOLDOUT_START]
    fee = b.pivot_table(index="date", columns="ticker", values="fee_rate_pct")
    first = fee.index.min()
    span = H.index > first                      # row t charges the fee of t-1
    S_in = H.where((H < 0) & M, 0.0)
    out = {"fee_panel_first": str(first.date()), "fee_panel_last_used": str(fee.index.max().date()),
           "_fee_first": first}
    for lab, X in (("in_window_shorts", S_in), ("all_book_shorts", H)):
        c = bf.borrow_charge(X, fee)
        sh, un = c["short"][span].sum(), c["uncovered"][span].sum()
        yrs = int(span.sum()) / 252.0
        out[lab] = {"cost_bp_per_yr": round(float(c["cost"][span].sum()) / yrs * BP, 2),
                    "covered_share_on_span": round(1.0 - float(un) / float(sh), 4) if sh > 0 else 1.0,
                    "sessions": int(span.sum())}
    return out


# ============================================================ CRSP: an independent price source

def crsp_returns(crsp_dirs, index: pd.DatetimeIndex, tickers, H: pd.DataFrame) -> dict:
    """CRSP `ret` and `retx` for the book's names on H's sessions. A ticker must map to
    one permno on every held session (two permnos pricing one date raise). A held
    name-day with no CRSP return raises: it would book zero."""
    import pyarrow.parquet as pq
    from scripts.events import a1_cef_issuance_gate as a1
    from scripts.research.harness import held
    dirs = [Path(d) for d in crsp_dirs]
    nm = pd.read_parquet(a1._first_existing(dirs, "dsenames.parquet"))
    for c in ("namedt", "nameendt"):
        nm[c] = pd.to_datetime(nm[c])
    lo, hi = index.min(), index.max()
    nn = nm[nm["ticker"].isin(tickers) & nm["shrcd"].isin(a1.CEF_SHRCD) & (nm["namedt"] <= hi) & (nm["nameendt"] >= lo)]
    missing = sorted(set(tickers) - set(nn["ticker"]))
    if missing:
        raise ReopenA1Error(f"no CRSP name record in the fit span for {missing}")
    perms = sorted(set(nn["permno"].astype(int)))
    frames, seen = [], set()
    for d in dirs:
        for p in sorted(d.glob("dsf_*.parquet")):
            if p.name in seen:
                continue
            seen.add(p.name)
            t = pq.read_table(p, columns=["permno", "date", "ret", "retx"], filters=[("permno", "in", perms)]).to_pandas()
            if len(t):
                frames.append(t)
    if not frames:
        raise ReopenA1Error("no CRSP daily rows for the book's permnos in the given caches")
    dsf = pd.concat(frames, ignore_index=True)
    dsf["date"] = pd.to_datetime(dsf["date"])
    a1.assert_pre_holdout(dsf["date"], "CRSP daily rows")
    dup = dsf[dsf.duplicated(["permno", "date"], keep=False)]
    if len(dup):
        g = dup.groupby(["permno", "date"])[["ret", "retx"]].nunique(dropna=False)
        if (g > 1).any(axis=1).any():
            raise ReopenA1Error("CRSP extracts disagree on a (permno, date) return")
    dsf = dsf.drop_duplicates(["permno", "date"])
    out, n_perm = {}, {}
    hold = held(H).ne(0.0)
    for col in ("ret", "retx"):
        Rc = pd.DataFrame(np.nan, index=index, columns=list(tickers))
        for tk in tickers:
            spans = nn[nn["ticker"] == tk]
            series = []
            for s in spans.itertuples():
                x = dsf[(dsf["permno"] == int(s.permno)) & (dsf["date"] >= s.namedt) & (dsf["date"] <= s.nameendt)]
                series.append(x.set_index("date")[col])
            ser = pd.concat(series)
            if ser.index.duplicated().any():
                raise ReopenA1Error(f"{tk}: two CRSP name spans price the same date")
            Rc[tk] = ser.reindex(index)
            n_perm[tk] = int(spans["permno"].nunique())
        gaps = int((hold & Rc.isna()).sum().sum())
        if gaps:
            raise ReopenA1Error(f"CRSP {col} has no return on {gaps} name-days the book holds")
        out[col] = Rc.fillna(0.0)            # only off the held cells (checked above)
    out["permnos_per_ticker"] = n_perm
    return out


# ============================================================ run

def measure(H: pd.DataFrame, Rv: dict, w: pd.DataFrame, committed: dict, crsp_dirs) -> dict:
    from scripts.events.g6_corporate_action_shorts import assert_causal, event_mask
    from scripts.research.harness import EXEC_LAG, evaluate
    assert_causal(w)
    M = event_mask(H.index, H.columns, w[["ticker", "start", "end"]])
    live = H.abs().sum(axis=1) > 0
    first_live = live.idxmax()
    held_from = H.index[H.index.get_loc(first_live) + EXEC_LAG]
    res = {"a1_reproduced": assert_matches_a1(w, H, M, first_live, committed),
           "first_held_session": str(held_from.date()), "fit_last_session": str(H.index[-1].date())}

    # ---- holdings only: the block's added turnover and `meaningful`, BEFORE any return
    turn_b = H.diff().abs().sum(axis=1).fillna(0.0)
    turn_k = blocked(H, M).diff().abs().sum(axis=1).fillna(0.0)
    act = H.index >= held_from
    years = int(act.sum()) / 252.0
    dturn_total = float((turn_k - turn_b)[act].sum())
    n_in = int(((H < 0) & M).loc[first_live:].iloc[:-EXEC_LAG].sum().sum())
    # Revision 1 (module docstring, item 6): the original rule needed dturn_total > 0
    # and the first run measured it negative, before any return. The hurdle is now the
    # positions' own round trip per spell; dturn is reported, not used as a hurdle.
    hurdle = {side: spell_hurdle(H, M, first_live, side) for side in ("short", "long")}
    if hurdle["short"]["name_days"] != n_in:
        raise AssertionError("the spell count and the name-day count disagree on the in-window shorts")
    res["declared_before_returns"] = {
        "block_added_turnover_total": round(dturn_total, 4), "block_added_turn_per_yr": round(dturn_total / years, 4),
        "in_window_short_name_days_with_fit_return": n_in,
        "original_rule_formable": bool(dturn_total > 0),
        "meaningful_rule": (f"{MEANINGFUL_COST_BP:g}bp x 2 x sum over in-window spells of mean|w| / in-window name-days "
                            "(per unit weight: x 2 x spells / name-days); revision 1"),
        "hurdle": {s: {"spells": h["spells"], "name_days": h["name_days"], "median_spell_sessions": h["median_spell_sessions"],
                       "meaningful_pnl_bp": round(h["meaningful_pnl"] * BP, 5),
                       "meaningful_unit_bp": round(h["meaningful_unit"] * BP, 5)} for s, h in hurdle.items()},
        "kill_line_bp_per_yr": round(dturn_total / years * KILL_LINE_BP, 3),
        "kill_line_rule": f"block's added turn/yr x {KILL_LINE_BP:g}bp (A1 §7 item 1)",
        "kill_line_can_bind": bool(dturn_total > 0)}

    # ---- returns
    borrow = borrow_line(H, M)
    views = {}
    for view, R in Rv.items():
        v = {}
        for side in ("short", "long"):
            df = name_days(H, R, M, first_live, side)
            S = H.where((H < 0) if side == "short" else (H > 0), 0.0)
            check = float(evaluate(S, R)["pnl"].sum())
            if abs(check - df["pnl"].sum()) > 1e-12:
                raise AssertionError(f"{side} name-day P&L {df['pnl'].sum()} != evaluate's {check}")
            rec = {"pnl_per_name_day": split(df, "pnl", hurdle[side]["meaningful_pnl"]),
                   "unit_return_per_name_day": split(df, "unit", hurdle[side]["meaningful_unit"]),
                   "within_date_pnl": within_date(df, "pnl"),
                   "mean_abs_weight": {"inside": round(float(df.loc[df["inside"], "w"].abs().mean()), 5),
                                       "outside": round(float(df.loc[~df["inside"], "w"].abs().mean()), 5)},
                   "by_era_pnl": by_group(df, era_of(df["date"]), "pnl"),
                   "by_name_pnl": by_group(df, df["ticker"], "pnl")}
            if side == "short":
                pin = df.loc[df["inside"]]
                rec["by_window_pnl_total_bp"] = {
                    lab: {"name_days": int(((pin["ticker"] == x.ticker) & pin["date"].between(x.start, x.end)).sum()),
                          "pnl_total_bp": round(float(pin.loc[(pin["ticker"] == x.ticker) & pin["date"].between(x.start, x.end), "pnl"].sum()) * BP, 2)}
                    for lab, x in zip(window_labels(w), w.itertuples())}
                rec["in_window_short_pnl_bp_per_yr"] = round(float(pin["pnl"].sum()) / years * BP, 3)
                # added after run 2 (descriptive): the largest in-window short days, so the
                # note's account of them is reproducible; CRSP's return for each is attached below
                top = pin.nlargest(TOP_DAYS, "pnl")
                rec["largest_in_window_short_days"] = [
                    {"decided": str(r.date.date()), "ticker": r.ticker, "w": round(float(r.w), 4),
                     "ret_t2_pct": round(float(r.ret_t2) * 100, 3), "pnl_bp": round(float(r.pnl) * BP, 1)}
                    for r in top.itertuples()]
            v[side] = rec
        bc = block_counterfactual(H, R, M, held_from)
        series = bc.pop("_series")
        series.to_parquet(CACHE / f"daily_series_{view}.parquet")
        from scripts.research.inference import newey_west_t
        x = series.loc[series.index >= held_from, "in_window_short"].to_numpy()
        v["block"] = bc
        v["in_window_short_daily_pnl"] = {"mean_bp_per_day": round(float(x.mean()) * BP, 4),
                                          "nw_t": round(newey_west_t(x), 3), "sessions": int(x.size)}
        v["kill_line"] = {"in_window_short_pnl_bp_per_yr": v["short"]["in_window_short_pnl_bp_per_yr"],
                          "block_gain_gross_bp_per_yr": round(-v["short"]["in_window_short_pnl_bp_per_yr"], 3),
                          "added_turn_x_5bp_bp_per_yr": res["declared_before_returns"]["kill_line_bp_per_yr"],
                          "immaterial": (bool(abs(v["short"]["in_window_short_pnl_bp_per_yr"])
                                              < res["declared_before_returns"]["kill_line_bp_per_yr"])
                                         if dturn_total > 0 else
                                         "cannot bind: the block lowers turnover, so it has no cost to clear")}
        # ADDED AFTER THE SECOND RUN (descriptive; decides nothing, changes no reading):
        # where the in-window short P&L came from, by calendar year and without the
        # 2020-02-15..04-30 crash (the span the sibling note excludes, not chosen here),
        # and on the borrow panel's own span so that borrow nets on like dates.
        xs = series.loc[series.index >= held_from, "in_window_short"]
        crash = (xs.index >= CRASH_SPAN[0]) & (xs.index <= CRASH_SPAN[1])
        on_fee = xs.index > borrow["_fee_first"]
        v["in_window_short_sources"] = {
            "by_year_bp": {str(y): round(float(g.sum()) * BP, 1) for y, g in xs.groupby(xs.index.year)},
            "crash_span": [str(CRASH_SPAN[0].date()), str(CRASH_SPAN[1].date())],
            "crash_span_total_bp": round(float(xs[crash].sum()) * BP, 1),
            "ex_crash_bp_per_yr": round(float(xs[~crash].sum()) / (int((~crash).sum()) / 252.0) * BP, 2),
            "on_borrow_span_gross_bp_per_yr": round(float(xs[on_fee].sum()) / (int(on_fee.sum()) / 252.0) * BP, 2),
            "on_borrow_span_net_of_borrow_bp_per_yr": round(
                float(xs[on_fee].sum()) / (int(on_fee.sum()) / 252.0) * BP
                - borrow["in_window_shorts"]["cost_bp_per_yr"], 2)}
        views[view] = v
    res["views"] = views
    res["borrow_real_money_only"] = {k: x for k, x in borrow.items() if not k.startswith("_")}

    # ---- CRSP, the independent price source, for the shorts split and the block's gross change
    Rc = crsp_returns(crsp_dirs, H.index, list(H.columns), H)
    res["crsp_check"] = {"permnos_per_ticker": Rc.pop("permnos_per_ticker")}
    for col, lab in (("ret", "total"), ("retx", "paper")):
        df = name_days(H, Rc[col], M, first_live, "short")
        sp = split(df, "pnl", hurdle["short"]["meaningful_pnl"])
        res["crsp_check"][lab] = {"inside_mean_bp": sp["inside"]["mean_bp"], "outside_mean_bp": sp["outside"]["mean_bp"],
                                  "estimate_out_minus_in_bp": sp["estimate_out_minus_in_bp"], "se_bp": sp["se_bp"],
                                  "outcome": sp["read_result"]["outcome"],
                                  "in_window_short_pnl_bp_per_yr": round(float(df.loc[df["inside"], "pnl"].sum()) / years * BP, 3)}
        panel = views[lab]
        from scripts.research.harness import label as _label
        Lc = _label(Rc[col])
        for r in panel["short"]["largest_in_window_short_days"]:
            r[f"crsp_{col}_t2_pct"] = round(float(Lc.loc[pd.Timestamp(r["decided"]), r["ticker"]]) * 100, 3)
        res["crsp_check"][lab]["agrees_in_sign_with_panel"] = {
            "estimate": bool(np.sign(sp["estimate_out_minus_in_bp"]) == np.sign(panel["short"]["pnl_per_name_day"]["estimate_out_minus_in_bp"])),
            "in_window_short_pnl": bool(np.sign(res["crsp_check"][lab]["in_window_short_pnl_bp_per_yr"])
                                        == np.sign(panel["short"]["in_window_short_pnl_bp_per_yr"]))}
    res["active_years"] = round(years, 3)
    return res


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--edgar-cache", required=True, type=Path)
    ap.add_argument("--crsp-cache", required=True, type=Path, nargs="+")
    a = ap.parse_args(argv)
    from ops import netguard
    netguard.install()                         # nothing below may open a connection
    for p in [a.edgar_cache, *a.crsp_cache]:
        if not p.is_dir():
            raise ReopenA1Error(f"cache directory {p} does not exist; it is not fetched here")
    from scripts.events import a1_cef_issuance_gate as a1
    from scripts.cef.spec import UNIVERSE
    committed = json.loads(A1_LEVELS.read_text())
    H, Rv, prov = book()
    c = a1.census(a.edgar_cache, a.crsp_cache, write=False)
    w = programme_windows(c["_eps"], set(UNIVERSE), H.index[-1])
    res = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "git_head": _git("rev-parse", "--short", "HEAD"), "git_clean": _git("status", "--porcelain") == "",
           "zero_trials": True, "n_trials_read_result": N_TRIALS, "book": prov,
           "a1_census_inputs": c["inputs"] if "inputs" in c else None}
    res.update(measure(H, Rv, w, committed, a.crsp_cache))
    OUT.mkdir(parents=True, exist_ok=True)
    w.drop(columns=["first_filing", "start"]).assign(
        first_supplement=lambda x: x["first_supplement"].dt.date, last_supplement=lambda x: x["last_supplement"].dt.date,
        end=lambda x: x["end"].dt.date).to_csv(WINDOWS_OUT, index=False)
    SUMMARY_OUT.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
