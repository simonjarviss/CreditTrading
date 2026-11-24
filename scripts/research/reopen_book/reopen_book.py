"""Zero-trial re-open: do NAV tenders (EVENTS 2) and E1 (EVENTS 1) add to the CEF book? Fit period only.

    python3 -m scripts.research.reopen_book.reopen_book                 # re-derive both series, then measure
    python3 -m scripts.research.reopen_book.reopen_book --no-extract    # reuse the cached series
    python3 -m pytest scripts/research/tests/test_reopen_book.py

WHAT THIS ANSWERS (team lead, 2026-10-27, `docs/SYSTEM.md` §5, "the research method")
------------------------------------------------------------------------------------
A sleeve that fails the standalone deflated Sharpe may join the PAPER book, labelled,
if it adds to the book, SR_sleeve > ρ·SR_book across ρ's plausible range, AND the
combined book's net is positive at 5, 15 and 30bp. Real capital keeps the standalone
gate. The audit (`results/research/DESK_METHOD_2026-10-27.md` §2) found both trials
had a near-zero correlation with the book that was never weighed. This script
measures the rule's inputs. It decides nothing, spends no trial, and edits no
counter, spec or `docs/RESEARCH_STATE.md`.

THE SERIES
----------
* Each sleeve: its tradable fit-period daily gross P&L, re-derived by its own
  branch's committed code (`extract_trial_series.py`, which refuses unless it
  reproduces the committed fit JSON to 1e-9). Neither trial stored a daily series.
  The series are CRSP-derived, so they stay in the gitignored cache, as the trials
  kept theirs. Only aggregates are tracked.
* The book: the live policy on the canonical harness. `build_targets` on the live
  price and NAV panels CUT AT 2022-12-30 before any computation (`source=`, the
  harness's own argument), `band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)`
  (spec.LIVE_POLICY), `evaluate()` (shift(2)) on `total_returns` (H15). Every
  target is causal (z, ADV and the vol scaler are `.shift(1)` or trailing), so the
  cut changes no fit-period value. `total_returns` itself reads the FULL
  distribution, split and price panels and reindexes them to the fit index; the
  script asserts that cutting those three inputs at 2022-12-30 too leaves the
  distribution yield and the split factor unchanged, cell for cell
  (`assert_return_inputs_cut`). So no 2023+ value reaches any figure.
  (Corrected 2026-10-28: the first version said nothing after 2022-12-30 entered
  the process, which was false for those three reads.)

TWO VIEWS (added 2026-10-28, after an independent review)
---------------------------------------------------------
* TOTAL: the book and each sleeve on total returns (H15). The first version's only view.
* PAPER: the book AND each sleeve on price returns, because Alpaca paper pays no
  distributions (CLAUDE.md landmine 1). The first version swapped only the book's leg.
  The sleeve's price-return P&L is built in the trial's tree on the same positions,
  by two methods that must agree (`extract_trial_series.py`'s docstring).

THE RULES FIXED BEFORE ANY NUMBER WAS SEEN (stated here, not chosen from output)
-------------------------------------------------------------------------------
* Common window: from the later of the sleeve's first P&L session and the book's
  first session holding a position, to 2022-12-30, on dates in both series. Idle
  sleeve days are zeros and stay in: that is what the sleeve earns.
* ρ's range: the union of every interval below. The rule must hold at its upper end.
  - daily ρ, stationary bootstrap (pairs resampled together; 10,000 draws), mean
    block = the sleeve's median ACTIVE-SPELL length in sessions (how long a run of
    held positions lasts: the persistence a resample must keep, measured from the
    sleeve's holdings, never from P&L), and 21 and 63 beside it (the blocks both
    trials declared);
  - non-overlapping weekly (Friday) sums and 21-session sums, Fisher intervals. The
    21-session sum is `results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md` §2.4's input,
    because daily correlations of thinly traded CEF books understate co-movement.
* The combined book's weight: EQUAL RISK BUDGETS. With fewer than four sleeves the
  framework sets b ∝ R̃⁻¹·1 (§2.3), which for two sleeves is equal budgets at any ρ.
  Each sleeve's own scalar targets its budget (§2.2), and an event sleeve's budget is
  a ceiling (§2.2, §2.8). So each enters at the sizing its own pre-registration
  derived: the book at `vol_target_annual` through build_targets' scaler, the sleeve
  at k = vol_target / σ_active (NAV tenders) or σ_raw (E1), capped at
  `max_gross_stress`. Combined = book + 1.0 × sleeve on capital. Nothing is
  optimised on the fit.
* Costs: each leg on its own convention, never netted between them (they trade
  different symbols): the book's `evaluate()` turnover; NAV tenders' notional on
  every leg; E1's event turnover (a conversion is not a trade), with the harness's
  count, measured on the SIZED and capped H, beside it (corrected 2026-10-28: the
  first version used the trial's harness count, which is the raw H's).
* The ceiling on the combined book (report-only): f = min(1, cap / gross) on each
  decision row, as `_cap_gross` scales a held book. P&L is scaled by the f decided
  two sessions earlier; turnover by the f of its own decision row. The rescaling
  trades are bounded by Σ|Δf|·G(t−1) (G the uncapped combined decided gross), so the
  capped nets are a range from no rescaling cost to that bound (added 2026-10-28).
* DSR: `desk_dsr` at the EVENTS counter's declared N = 6, and `dsr(...)` with
  sr_var = 1/T on both bounds, "upper" (the desk's √(2 ln N)) and "gumbel" (the
  paper's expected maximum), labelled.

ALIGNMENT (H7): every series is P&L earned on date t from weights decided at t−2
(evaluate()'s shift(2), in each trial's code and here). Nothing estimated here feeds
back into a weight; the bootstrap and the sums only describe realised P&L.
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
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research import inference as I  # noqa: E402

OUT = REPO / "results" / "research" / "reopen_book"
CACHE = OUT / "_cache_reopen"                    # gitignored (results/**/_cache_*): CRSP-derived daily series
OUT_JSON = OUT / "reopen_book_2026-10-28.json"
EXTRACTOR = Path(__file__).resolve().parent / "extract_trial_series.py"
HOLDOUT_START = pd.Timestamp("2023-01-01")
N_EVENTS = 6                                     # EVENTS' declared bar N (docs/RESEARCH_STATE.md, 2026-10-19)
COSTS_BP = (5, 15, 30)
BLOCKS_DECLARED = (21, 63)                       # both trials' declared bootstrap blocks
REPS = 10_000
SEED = 20261028
SUM_SESSIONS = 21                                # PORTFOLIO_FRAMEWORK §2.4
ERAS = (("2010-14", "2010-01-01", "2014-12-31"), ("2015-19", "2015-01-01", "2019-12-31"),
        ("2020-22", "2020-01-01", "2022-12-31"))
CRASH = ("2020-02-15", "2020-04-30")             # the reviewer's 2020 window (report-only: how much of ρ it carries)
TRIALS = {"navtender": "trial-events-navtender", "e1": "trial-events-e1"}
VIEWS = {"total": ("live_total", "pnl"), "paper": ("live_price", "pnl_price")}


# ============================================================ pure helpers (tested)

def common_window(sleeve: pd.DataFrame, book: pd.DataFrame) -> tuple[pd.DatetimeIndex, dict]:
    """Dates in both frames from max(sleeve's first P&L session, book's first held session).

    `book.held_gross` > 0 marks the book holding a position. Returns the index and
    what was dropped, so a calendar mismatch is reported, never silent."""
    if sleeve.index.max() >= HOLDOUT_START or book.index.max() >= HOLDOUT_START:
        raise AssertionError("a series reaches 2023-01-01: the time holdout is sealed")
    held = book.index[book["held_gross"] > 0]
    if not len(held):
        raise ValueError("the book never holds a position")
    start = max(sleeve.index[0], held[0])
    s_ix = sleeve.index[sleeve.index >= start]
    b_ix = book.index[book.index >= start]
    idx = s_ix.intersection(b_ix)
    lost = sleeve.loc[s_ix.difference(b_ix), "pnl"]
    return idx, {"start": str(start.date()), "end": str(idx[-1].date()), "T": int(len(idx)),
                 "sleeve_sessions_not_in_book": int(len(lost)),
                 "sleeve_pnl_on_those_sessions": float(lost.sum()),
                 "book_sessions_not_in_sleeve": int(len(b_ix.difference(s_ix)))}


def spells(active: pd.Series) -> np.ndarray:
    """Lengths (in sessions) of each run of consecutive True values."""
    a = np.asarray(active, dtype=bool)
    if not a.any():
        return np.array([], dtype=int)
    edges = np.diff(np.r_[0, a.astype(int), 0])
    return np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)


def block_sums(x: pd.Series, n: int) -> pd.Series:
    """Non-overlapping sums of n consecutive sessions from the first; a trailing partial block is dropped."""
    k = len(x) // n
    if k < 4:
        raise ValueError(f"{len(x)} sessions make {k} blocks of {n}; too few to correlate")
    v = np.asarray(x, dtype=float)[: k * n].reshape(k, n).sum(axis=1)
    return pd.Series(v, index=x.index[n - 1: k * n: n])


def stats(pnl: pd.Series, turn: pd.Series) -> dict:
    """`band_frontier._stats` (gross SR and nets at 5/15/30bp, annualised) plus the moments the DSR needs."""
    from scripts.cef.band_frontier import _stats
    st = _stats(pnl, turn)
    return {"gross": float(st["sr"]), "ann": float(st["ann"]), "vol": float(st["vol"]), "turn": float(st["turn"]),
            **{f"net{c}": float(v) for c, v in zip(COSTS_BP, st["nets"])},
            **{f"ann_net{c}": float(st["ann"] - st["turn"] * c / 1e4) for c in COSTS_BP},
            "T": int(len(pnl)), "skew": float(pnl.skew()), "kurt_raw": float(pnl.kurt() + 3.0)}


def deflated(s: dict, n: float = N_EVENTS) -> dict:
    """Both DSR bars on the sleeve's gross daily P&L, sr_var = 1/T (the desk's null spread)."""
    T, sk, ku = s["T"], s["skew"], s["kurt_raw"]
    sr_pp = s["gross"] / np.sqrt(252)
    up, sr0_up = I.dsr(sr_pp, T, sk, ku, n, 1 / T, bound="upper")
    gu, sr0_gu = I.dsr(sr_pp, T, sk, ku, n, 1 / T, bound="gumbel")
    desk = I.desk_dsr(s["gross"], T, sk, ku, n)
    if abs(desk - up) > 1e-12:
        raise AssertionError("desk_dsr and dsr(bound='upper', sr_var=1/T) disagree")
    return {"N": n, "desk_dsr": desk, "upper": {"dsr": up, "sr0_annual": sr0_up * np.sqrt(252)},
            "gumbel": {"dsr": gu, "sr0_annual": sr0_gu * np.sqrt(252)}}


def rho_range(rows: list[dict]) -> tuple[float, float]:
    return min(r["lo"] for r in rows), max(r["hi"] for r in rows)


def reading(gain_hi: float, gain_point: float, nets_positive: bool) -> str:
    """The rule's three outcomes. `gain_*` = marginal_gain at ρ's upper end and its point estimate."""
    if not nets_positive:
        return "DOES NOT MEET (the combined book's net is not positive at every cost on the grid)"
    if gain_hi > 0:
        return "MEETS the paper-admission rule across rho's range"
    if gain_point > 0:
        return "MEETS it only at the point estimate (fails at the upper end of rho's range)"
    return "DOES NOT MEET (SR_sleeve <= rho * SR_book at the point estimate)"


def combine(book: pd.DataFrame, sleeve: pd.DataFrame, w: float) -> pd.DataFrame:
    """Book + w × sleeve on common dates: P&L, turnover and gross add (no symbol is shared)."""
    if not book.index.equals(sleeve.index):
        raise ValueError("combine needs both frames on the same dates")
    return pd.DataFrame({k: book[k] + w * sleeve[k] for k in ("pnl", "turn", "held_gross", "decided_gross")})


def leverage(held: pd.Series, cap: float) -> dict:
    return {"mean": float(held.mean()), "p95": float(held.quantile(0.95)), "max": float(held.max()),
            "share_days_above_cap": float((held > cap + 1e-12).mean())}


def capped(C: pd.DataFrame, G_dec: pd.Series, cap: float) -> dict:
    """The ceiling applied to the combined book, as `_cap_gross` scales a held book (approximate).

    f[d] = min(1, cap / G[d]) on each decision row d (G = the uncapped combined decided
    gross). The P&L earned on t is scaled by f[t-2] (shift(2)); the turnover traded on
    decision row t by f[t]. Not rebuilt: the band's feedback from a scaled book into the
    next day's trade. The rescaling trade itself is (f[t] − f[t−1])·w[t−1], so the extra
    turnover is at most Σ|Δf|·G[t−1]; the nets are reported at both ends (no rescaling
    cost, and the bound). `G_dec` must cover the window and the two decision rows before it."""
    idx = C.index
    pos = G_dec.index.get_indexer(idx)
    if (pos < 2).any():
        raise ValueError("G_dec must start at least two sessions before the window")
    f = pd.Series(np.minimum(1.0, cap / G_dec.where(G_dec > 0)), index=G_dec.index).where(G_dec > 0, 1.0)
    f_held = f.shift(2).reindex(idx)
    from_held = pd.Series(np.minimum(1.0, cap / C["held_gross"].where(C["held_gross"] > 0)), index=idx)
    from_held = from_held.where(C["held_gross"] > 0, 1.0)
    if not np.allclose(f_held.values, from_held.values, rtol=0, atol=1e-12):
        raise AssertionError("held gross is not the decided gross two sessions earlier: calendars disagree")
    extra = ((f - f.shift(1)).abs() * G_dec.shift(1)).reindex(idx)
    pnl = C["pnl"] * f_held
    lo = stats(pnl, C["turn"] * f.reindex(idx))
    hi = stats(pnl, C["turn"] * f.reindex(idx) + extra)
    return {"gross": lo["gross"], "vol": lo["vol"], "ann": lo["ann"],
            **{f"net{c}_no_rescale_cost": lo[f"net{c}"] for c in COSTS_BP},
            **{f"net{c}_at_bound": hi[f"net{c}"] for c in COSTS_BP},
            "rescale_bound_turns_per_year": float(extra.mean() * 252),
            "share_days_capped": float((f_held < 1 - 1e-12).mean())}


def rho_without(x: pd.Series, y: pd.Series, a: str, b: str) -> dict:
    keep = ~((x.index >= pd.Timestamp(a)) & (x.index <= pd.Timestamp(b)))
    return {"window_dropped": [a, b], "sessions_dropped": int((~keep).sum()),
            "rho": float(np.corrcoef(x[keep], y[keep])[0, 1])}


# ============================================================ the series

def main_tree() -> Path:
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout.strip()
    return Path(common).parent


def extract(trees: dict) -> None:
    for trial, tree in trees.items():
        # -I: isolated (no caller env, no script dir on the path); -B: no bytecode written into the trial tree.
        subprocess.run([sys.executable, "-I", "-B", str(EXTRACTOR), trial, "--tree", str(tree), "--out", str(CACHE)],
                       check=True)


def load_sleeve(trial: str) -> tuple[pd.DataFrame, dict]:
    p, m = CACHE / f"{trial}_fit_series.parquet", CACHE / f"{trial}_fit_check.json"
    if not p.exists() or not m.exists():
        raise FileNotFoundError(f"{p.name} is missing: run without --no-extract")
    df = pd.read_parquet(p)
    need = {"pnl", "pnl_price", "dist_overlay", "turn", "held_gross", "decided_gross"}
    if need - set(df.columns):
        raise ValueError(f"{p.name} lacks {sorted(need - set(df.columns))}: re-run without --no-extract")
    return df, json.loads(m.read_text())


def assert_return_inputs_cut(bf, R: pd.DataFrame, cut_prices: Path) -> dict:
    """`total_returns` reads the full distribution, split and price panels. Prove that cutting
    each at 2022-12-30 changes no cell of what it builds on the fit index: the distribution
    yield (with the cut price panel as its denominator) and the split factor."""
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


def book_series() -> tuple[dict, dict]:
    """The live policy on the fit-cut panels. Returns {variant: frame(pnl, turn, held_gross, decided_gross)}."""
    from scripts.cef import band_frontier as bf
    from scripts.cef.spec import BAND_WIDTH, LIVE_POLICY, MAX_GROSS_STRESS, SPEC_ID
    if MAX_GROSS_STRESS is None:
        raise RuntimeError("the spec has no max_gross_stress; the live policy label would not match")
    CACHE.mkdir(parents=True, exist_ok=True)
    prov = {"spec": SPEC_ID, "live_policy": LIVE_POLICY}
    paths = []
    for name in ("cef_prices", "cef_nav"):
        df = pd.read_parquet(bf.DATA_DIR / f"{name}.parquet")
        d = pd.to_datetime(df["date"])
        prov[f"{name}_panel_last"] = str(d.max().date())
        cut = df[d < HOLDOUT_START]
        prov[f"{name}_cut_last"] = str(pd.to_datetime(cut["date"]).max().date())
        p = CACHE / f"{name}_fit_cut.parquet"
        cut.to_parquet(p)
        paths.append(p)
    T, R = bf.build_targets(source=tuple(paths))
    T, R = bf.fit_only(T, R)                          # asserts nothing reaches 2023-01-01
    prov["return_inputs"] = assert_return_inputs_cut(bf, R, paths[0])
    Rt = bf.total_returns(R)
    if Rt.index.max() >= HOLDOUT_START:
        raise AssertionError("holdout leak in the total-return matrix")
    out = {}
    Hc = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)
    for label, H, RR in (("live_total", Hc, Rt), ("live_price", Hc, R), ("band_only_total", bf.band(T, BAND_WIDTH), Rt)):
        ev = bf.evaluate(H, RR)
        out[label] = pd.DataFrame({"pnl": ev["pnl"], "turn": ev["turn_series"],
                                   "held_gross": H.shift(2).fillna(0.0).abs().sum(axis=1),
                                   "decided_gross": H.abs().sum(axis=1)})
    prov["targets_first"], prov["targets_last"] = str(T.index[0].date()), str(T.index[-1].date())
    prov["max_gross_stress"] = MAX_GROSS_STRESS
    return out, prov


# ============================================================ the measurement

def measure_view(S: pd.DataFrame, B: pd.DataFrame, active: pd.Series, cap: float, G_dec: pd.Series,
                 mech_block: int) -> dict:
    """Items 1-4 for one view. S and B carry pnl, turn, held_gross, decided_gross on the window."""
    out = {}
    s, b = stats(S["pnl"], S["turn"]), stats(B["pnl"], B["turn"])
    out["sleeve"] = {**s, "dsr": deflated(s), "nw_t_auto": I.newey_west_t(S["pnl"].values),
                     "nw_t_L21": I.newey_west_t(S["pnl"].values, 21)}
    out["book"] = b
    rho = float(np.corrcoef(S["pnl"], B["pnl"])[0, 1])
    boot = []
    for blk, why in ((mech_block, "median active spell of the sleeve"), *((k, "declared by both trials") for k in BLOCKS_DECLARED)):
        r = I.stationary_bootstrap_corr(S["pnl"].values, B["pnl"].values, blk, seed=SEED, reps=REPS)
        boot.append({"kind": f"daily, stationary bootstrap, mean block {blk} ({why})", **r})
    sums = []
    wk = pd.DataFrame({"s": S["pnl"], "b": B["pnl"]}).resample("W-FRI").sum()
    for label, x, y in (("weekly (W-FRI) sums", wk["s"], wk["b"]),
                        (f"{SUM_SESSIONS}-session sums", block_sums(S["pnl"], SUM_SESSIONS), block_sums(B["pnl"], SUM_SESSIONS))):
        r_ = float(np.corrcoef(x, y)[0, 1])
        lo_, hi_ = I.fisher_corr_ci(r_, len(x))
        sums.append({"kind": f"{label}, Fisher", "rho": r_, "lo": lo_, "hi": hi_, "n": int(len(x)),
                     "nonzero_sleeve_blocks": int((x != 0).sum())})
    lo, hi = rho_range(boot + sums)
    out["rho"] = {"daily_point": rho, "intervals": boot + sums, "range": [lo, hi],
                  "break_even_rho_gross": s["gross"] / b["gross"],
                  "without_2020_crash": rho_without(S["pnl"], B["pnl"], *CRASH)}
    mg = {}
    for lab, ss, bb in (("gross", s["gross"], b["gross"]), *((f"net{c}", s[f"net{c}"], b[f"net{c}"]) for c in COSTS_BP)):
        mg[lab] = {"sr_sleeve": ss, "sr_book": bb, "at_point": I.marginal_gain(ss, bb, rho),
                   "at_lo": I.marginal_gain(ss, bb, lo), "at_hi": I.marginal_gain(ss, bb, hi),
                   "long_only_optimum_sr_at_point": I.combined_sharpe(bb, ss, rho) if (bb > 0 or ss > 0) else None}
    out["marginal_gain"] = mg
    C = combine(B, S, 1.0)
    c = stats(C["pnl"], C["turn"])
    scale = b["vol"] / c["vol"]
    out["combined"] = {"w": 1.0, **c,
                       "change_vs_book": {k: c[k] - b[k] for k in ("gross", "net5", "net15", "net30")},
                       "nets_all_positive": all(c[f"ann_net{k}"] > 0 for k in COSTS_BP),
                       "leverage": {"cap_max_gross_stress": cap, "book": leverage(B["held_gross"], cap),
                                    "sleeve": leverage(S["held_gross"], cap),
                                    "combined": leverage(C["held_gross"], cap),
                                    "combined_on_sleeve_active_days": leverage(C.loc[active, "held_gross"], cap),
                                    "combined_rescaled_to_book_vol": {"scale": scale, **leverage(C["held_gross"] * scale, cap)}},
                       "capped_approx": capped(C, G_dec, cap)}
    out["return_per_unit_gross"] = {"book": b["ann"] / float(B["held_gross"].mean()),
                                    "sleeve": s["ann"] / float(S["held_gross"].mean())}
    out["reading"] = reading(mg["gross"]["at_hi"], mg["gross"]["at_point"], out["combined"]["nets_all_positive"])
    out["reading_at_each_cost"] = {f"net{k}": reading(mg[f"net{k}"]["at_hi"], mg[f"net{k}"]["at_point"],
                                                      out["combined"]["nets_all_positive"]) for k in COSTS_BP}
    return out


def measure(trial: str, sleeve_all: pd.DataFrame, meta: dict, books: dict, cap: float) -> dict:
    idx, win = common_window(sleeve_all, books["live_total"])
    active = sleeve_all.loc[idx, "held_gross"] > 0
    sp = spells(active)
    mech = max(1, int(round(float(np.median(sp)))))
    full = sleeve_all.index.intersection(books["live_total"].index)
    G_dec = books["live_total"].loc[full, "decided_gross"] + sleeve_all.loc[full, "decided_gross"]
    out = {"window": win, "cost_convention": meta["cost_convention"],
           "activity": {"active_days": int(active.sum()), "active_share": float(active.mean()),
                        "nonzero_pnl_days": int((sleeve_all.loc[idx, "pnl"] != 0).sum()), "spells": int(len(sp)),
                        "median_spell_sessions": float(np.median(sp)),
                        "book_flat_days": int((books["live_total"].loc[idx, "held_gross"] == 0).sum())},
           "views": {}}
    for view, (book_key, pnl_col) in VIEWS.items():
        S = sleeve_all.loc[idx, ["turn", "held_gross", "decided_gross"]].assign(pnl=sleeve_all.loc[idx, pnl_col])
        B = books[book_key].loc[idx]
        out["views"][view] = measure_view(S, B, active, cap, G_dec, mech)
    # the paper view's distribution leg, by both methods (built in the trial's tree)
    W = sleeve_all.loc[idx]
    out["distribution_leg"] = {"window_ann_method_A": float((W["pnl"] - W["pnl_price"]).mean() * 252),
                               "window_ann_method_B": float(W["dist_overlay"].mean() * 252),
                               "window_sleeve_total_ann": float(W["pnl"].mean() * 252),
                               "window_max_abs_daily_diff_A_vs_B": float(((W["pnl"] - W["pnl_price"]) - W["dist_overlay"]).abs().max()),
                               "own_span": meta["paper_view"]}
    S, B = sleeve_all.loc[idx], books["live_total"].loc[idx]
    s_own = stats(sleeve_all["pnl"], sleeve_all["turn"])
    out["sleeve_own_span"] = {**s_own, "dsr": deflated(s_own), "first": str(sleeve_all.index[0].date())}
    extra = {}
    Bb = books["band_only_total"].loc[idx]
    cc = stats(Bb["pnl"] + S["pnl"], Bb["turn"] + S["turn"])
    extra["band_only_book_plus_sleeve"] = {"book": stats(Bb["pnl"], Bb["turn"]), "combined": cc,
                                           "nets_all_positive": all(cc[f"ann_net{k}"] > 0 for k in COSTS_BP)}
    if "harness_turn" in S:
        hs = stats(S["pnl"], S["harness_turn"])
        cc = stats(B["pnl"] + S["pnl"], B["turn"] + S["harness_turn"])
        extra["harness_turn_sized"] = {"sleeve": hs, "combined": cc,
                                       "nets_all_positive": all(cc[f"ann_net{k}"] > 0 for k in COSTS_BP),
                                       "turn_own_span": float(sleeve_all["harness_turn"].mean() * 252),
                                       "trial_committed_raw_H_turn_own_span": meta.get("harness_turn_committed_raw_H_ann")}
    out["total_view_sensitivities"] = extra
    bs, ss_ = block_sums(B["pnl"], SUM_SESSIONS), block_sums(S["pnl"], SUM_SESSIONS)
    worst = bs <= bs.quantile(0.2)
    out["book_worst_quintile_blocks"] = {"blocks": int(worst.sum()), "sleeve_mean_in_worst": float(ss_[worst].mean()),
                                         "sleeve_mean_in_rest": float(ss_[~worst].mean()),
                                         "book_mean_in_worst": float(bs[worst].mean())}
    eras = {}
    for lab, a, z in ERAS:
        m = (idx >= pd.Timestamp(a)) & (idx <= pd.Timestamp(z))
        if m.sum() < 126:
            eras[lab] = {"T": int(m.sum()), "not computed": "fewer than 126 common sessions"}
            continue
        row = {"T": int(m.sum()), "active_share": float(active[m].mean())}
        for view, (book_key, pnl_col) in VIEWS.items():
            sx, bx = sleeve_all.loc[idx, pnl_col][m], books[book_key].loc[idx, "pnl"][m]
            se, be = stats(sx, S["turn"][m]), stats(bx, B["turn"][m])
            re_ = float(np.corrcoef(sx, bx)[0, 1])
            row[view] = {"sr_sleeve": se["gross"], "sr_book": be["gross"], "rho": re_,
                         "marginal_gain": I.marginal_gain(se["gross"], be["gross"], re_)}
        tq = B["turn"][m]
        row["book_turn_sd_over_mean"] = float(tq.std() / tq.mean())
        eras[lab] = row
    out["eras"] = eras
    # Second method for the BOOK series: each trial's own R-BOOK row (in its committed fit JSON)
    # correlated its sleeve with the book built on the FULL panel. Reproducing it from this
    # fit-cut book, on the trial's own rule for the dates, shows the cut changed no fit value.
    book_all = books["live_total"]
    if trial == "navtender":                 # nav_tender_trial.r_book: inner join, dropna, book != 0
        d = pd.concat([sleeve_all["pnl"].rename("s"), book_all["pnl"].rename("b")], axis=1, join="inner").dropna()
        d = d[d["b"] != 0]
        ours, n = float(d["s"].corr(d["b"])), int(len(d))
    else:                                    # e1_merger_pair.fit_core: book reindexed on the sleeve's dates
        d = pd.concat([sleeve_all["pnl"], book_all["pnl"].reindex(sleeve_all.index)], axis=1).dropna()
        ours, n = float(d.corr().iloc[0, 1]), int(len(d))
    out["book_parity_with_trial_r_book"] = {"ours": ours, "n": n, "trial_committed": meta.get("r_book_committed")}
    out["reproduction"] = {"check": meta["check"], "provenance": meta["provenance"],
                           "committed_fit_json": meta["committed_fit_json"]}
    return out


def _view_line(v: dict) -> str:
    s, ro, mg, c = v["sleeve"], v["rho"], v["marginal_gain"]["gross"], v["combined"]
    return (f"SR {s['gross']:+.3f} (nets {s['net5']:+.3f}/{s['net15']:+.3f}/{s['net30']:+.3f}); "
            f"rho {ro['daily_point']:+.3f} [{ro['range'][0]:+.3f}, {ro['range'][1]:+.3f}]; "
            f"gain {mg['at_point']:+.3f} / hi {mg['at_hi']:+.3f}; combined {c['gross']:+.3f} vs book "
            f"{v['book']['gross']:+.3f}, nets {c['net5']:+.3f}/{c['net15']:+.3f}/{c['net30']:+.3f} "
            f"(book {v['book']['net5']:+.3f}/{v['book']['net15']:+.3f}/{v['book']['net30']:+.3f})")


def report(res: dict) -> None:
    bp = res["book_provenance"]
    print(f"{bp['spec']} | {bp['live_policy']} | fit only, panels cut at {bp['cef_prices_cut_last']} (prices) / "
          f"{bp['cef_nav_cut_last']} (NAV); return inputs: {bp['return_inputs']}")
    for trial, r in res["sleeves"].items():
        w, a = r["window"], r["activity"]
        print(f"\n=== {trial}: {w['start']} .. {w['end']}, T {w['T']}; active {a['active_days']} days "
              f"({a['active_share']:.1%}), median spell {a['median_spell_sessions']:.0f}")
        dl = r["distribution_leg"]
        print(f"  distribution leg {dl['window_ann_method_A']:.2%}/yr (A) {dl['window_ann_method_B']:.2%}/yr (B) "
              f"of {dl['window_sleeve_total_ann']:.2%}/yr; max |A-B| daily {dl['window_max_abs_daily_diff_A_vs_B']:.1e}")
        for view in VIEWS:
            v = r["views"][view]
            print(f"  [{view}] {_view_line(v)}")
            ca = v["combined"]["capped_approx"]
            print(f"     DSR desk {v['sleeve']['dsr']['upper']['dsr']:.3f} / gumbel {v['sleeve']['dsr']['gumbel']['dsr']:.3f}; "
                  f"rho w/o 2020 crash {v['rho']['without_2020_crash']['rho']:+.3f}; capped gross {ca['gross']:+.3f}, "
                  f"net30 {ca['net30_no_rescale_cost']:+.3f}..{ca['net30_at_bound']:+.3f} "
                  f"(bound {ca['rescale_bound_turns_per_year']:.2f} turns/yr); above cap "
                  f"{v['combined']['leverage']['combined']['share_days_above_cap']:.1%}")
            print(f"     -> {v['reading']}; at 30bp: {v['reading_at_each_cost']['net30']}")
        ht = r["total_view_sensitivities"].get("harness_turn_sized")
        if ht:
            print(f"  E1 harness turnover on sized Ht {ht['sleeve']['turn']:.2f}/yr (trial's raw-H figure "
                  f"{ht['trial_committed_raw_H_turn_own_span']:.2f} own span): sleeve nets "
                  f"{ht['sleeve']['net5']:+.3f}/{ht['sleeve']['net15']:+.3f}/{ht['sleeve']['net30']:+.3f}; combined "
                  f"{ht['combined']['net5']:+.3f}/{ht['combined']['net15']:+.3f}/{ht['combined']['net30']:+.3f}")
        pb = r["book_parity_with_trial_r_book"]
        print(f"  book parity {pb['ours']:.6f} (n {pb['n']}) vs committed {pb['trial_committed']['corr']:.6f}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-extract", action="store_true", help="reuse the cached sleeve series")
    ap.add_argument("--navtender-tree", type=Path)
    ap.add_argument("--e1-tree", type=Path)
    a = ap.parse_args(argv)
    pd.set_option("compute.use_numexpr", False)
    root = main_tree()
    trees = {"navtender": a.navtender_tree or root / ".claude" / "worktrees" / TRIALS["navtender"],
             "e1": a.e1_tree or root / ".claude" / "worktrees" / TRIALS["e1"]}
    if not a.no_extract:
        extract(trees)
    from scripts.cef.spec import MAX_GROSS_STRESS
    books, bprov = book_series()
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    res = {"run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_head": _git("rev-parse", "HEAD"),
           "tracked_files_modified_at_run": dirty.splitlines(),
           "book_provenance": bprov, "seed": SEED, "reps": REPS, "n_events": N_EVENTS, "sleeves": {}}
    for trial in TRIALS:
        sl, meta = load_sleeve(trial)
        res["sleeves"][trial] = measure(trial, sl, meta, books, MAX_GROSS_STRESS)
    OUT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(res, indent=1, default=float) + "\n")
    report(res)
    print(f"\nwrote {OUT_JSON.relative_to(REPO)} (aggregates only; the daily series stay in {CACHE.relative_to(REPO)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
