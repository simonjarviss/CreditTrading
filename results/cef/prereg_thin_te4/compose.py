"""The thin-session rule `trade_eligible` (floor 4) composed with CEF trial 53, on the fit (2026-11-03).

    python3 results/cef/prereg_thin_te4/compose.py --k3-run-sessions N [--stamp YYYY-MM-DD] [--overwrite]
        -> compose_<stamp>.json, compose_output_<stamp>.txt (this folder); a few minutes.
        --stamp defaults to today's date, so a read-date re-measure writes its own dated files and never
        overwrites the drafting-day record (compose_2026-11-03.*). Writing to a stamp whose files exist
        raises unless --overwrite is given (reproduce the drafting day with --stamp 2026-11-03
        --k3-run-sessions 3 --overwrite, then `git diff` the two files).
        --k3-run-sessions is REQUIRED and has no default: K3's run length, the spec's
        `risk.thin_k3_run_sessions` (§6.3's 3). The drafting-day files were written before it existed
        and do not record it; a run with it records it.

REVISED 2026-11-05 (the runner owner's round-2 answer (c)): K3's run length was a literal 3 here (and 2
for the context line) while the spec carries it as `risk.thin_k3_run_sessions` (registry, required under
the rule since the owner's review of 2026-11-04, item 9). A literal here and a key there can drift apart
with nothing to say so. It is now the required argument --k3-run-sessions, used wherever §E counts K3
runs (runs of n above the fit p99, and runs of n - 1 as context), and written into compose_<stamp>.json
as `k3_run_sessions`. src/deploy/tests/test_thin_k3_run_provenance.py fails any committed spec whose
`risk.thin_k3_run_sessions` differs from the `k3_run_sessions` recorded in a compose_<stamp>.json its
threshold notes cite (a test, not a registry check: the live path never reads results/).

REVISED 2026-11-03, after the quant and PM reviews of the draft (both findings are in the draft's §12):
  * STAMP was the literal "2026-11-03", so every read-date run overwrote the drafting-day outputs with new
    numbers under the old date (quant review, finding 6). It is now --stamp, defaulting to today.
  * §A RAISED when the flatten book did not reproduce trial 53's 2026-11-02 json files or the screen's
    results.json. Those references were built at band 0.048, ceiling 1.8 and the 2026-10-15 panel, so a
    read date after a /spec-change of the band or the ceiling, or a vendor revision of a fit row, made the
    file raise, and the draft turned that into a mandatory revert: only a change in m got through (quant
    review, finding 6). §A now has two parts. A1, ASSERTED at every run: every book this file scores
    equals an independent row-by-row loop (`independent_book`) at the read date's spec, to 1e-12. That is
    a check on the code that holds at any band, ceiling or panel. A2, REPORTED, never raised: the
    drafting-day references, with the largest difference. A difference says the inputs or the fit rows
    have moved since 2026-11-03; the read date's values then govern, as the draft says.
  * FLOOR is read from the spec (`scripts/cef/spec.py`, BELOW_MIN_NAMES_FLOOR) once that key exists; until
    then it is the draft's proposed 4, and the output says which.
  * §G2 (new): the PRESENT rule read at every completed episode against the single-read p inflates the
    false-PRESENT rate (quant review, finding 4). G2 simulates the null and the fit effect under the
    draft's original reading and under the declared fix (looks at k = 5, 9, 13, 20 only, Bonferroni p/4),
    and prints the exact single-read power at k = 10, the first k past a coin flip (quant review, finding 5).

ZERO TRIALS. Written for `results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md` (drafted
as `PREREG_DRAFT_THIN_TRADE_ELIGIBLE_2026-11-03.md`; approved 2026-11-03 as CEF trial 55). FIT WINDOW ONLY: every frame is cut by `band_frontier.fit_only` (strictly before 2023-01-01,
asserted there and again here), so nothing in this file reads a 2023+ row. The screen
(`results/backtests/thin-third-rule-2026-11-03/REPORT.md`) has already printed te4's 2023+ rows; this
file adds nothing to that. It reads data/ and writes only beside itself (CLAUDE.md landmine 9).

WHY IT EXISTS. Trial 53's multiplier and stops were measured on the FLATTEN book's trading sessions
(`results/cef/prereg_voltarget/FLATTEN_REMEASURE_2026-11-02.md`, PR #35; amendment 1, PR #36). Under
te4 the core also trades on sessions with 4 or 5 eligible names, so the series those figures were
measured on changes. The owning session asked whether trial 53's figures move under te4. This
measures it, with trial 53's own definitions, rather than arguing it.

WHAT IT ANSWERS
  A. Reproduction. A1 (asserted; it raises): every scored book against `independent_book`. A2
     (reported; since the 2026-11-03 revision it no longer raises, see above):
       the flatten book at m = 1.00 / 1.13 / 1.30, instant flips, against trial 53's committed exact
       build (`prereg_voltarget/flatten_exact_2026-11-02.json`);
       the flatten unit book's trading-session daily sd against `flatten_remeasure_2026-11-02_m1.30.json`;
       the te4 unit book's fit episodes against the screen's `results.json` (review_attacks.h_episodes).
  B. flatten_exact.py's rows on the te4 book, at m read from the frozen spec (and at 1.00 / 1.13 /
     the spec's m), instant and deferred flips (the live runner defers: quantt/session/decide.py
     FLIP_SAME_SESSION = False).
  C. The 2026-10-29 rule's core multiplier fed te4's trading-session sd instead of flatten's. Its other
     inputs (sd_c4 and the rule's C4 multiplier) are read from `flatten_remeasure_2026-11-02_m1.30.json`
     ([S] there), never written here as literals.
  D. Trial 53's stops R1-R3, by their declared definitions (`prereg_voltarget/stops.py`'s docstring),
     calibrated on the exact build's trading sessions of each book at the spec's m; and how often the
     flatten-calibrated stops fire when te4 is the truth (fit edge, SB21; FLATTEN_REMEASURE §4's table).
     trial 53's own figures use the house cap model; the exact-build flatten row here is the
     like-for-like reference for the te4 row, and the difference between the two methods is printed.
  E. The draft's in-episode stops, at the spec's m, deferred flips:
       D_E(L)  the 95th percentile of the maximum drawdown over L reduced-session earning days, the
               largest of SB21 / SB63 / GAUSS, the worse of total return and price only (trial 53's R1
               construction on a shorter horizon), L = 21, 63, 126, 252;
       C*      the 99th percentile and the maximum, over reduced decisions, of the HELD book's largest
               single-name |weight| in account units; and the same for |net weight|.
  F. The draft's unit of inference at the spec's m, deferred: each fit episode's value (the account's
     P&L summed over the episode's thin earning days, where flatten earns exactly 0), its length and
     its within-episode drawdown; the per-episode effect (mean / sd) on price only, paper's basis; and
     P(pass) by number of forward episodes at bars for N = 53..55 (`inference.p_clear_bar`, as the
     screen's attack m).

DEFINITIONS (shared with the screen; asserted, not restated):
  reduced session  4 <= eligible < min_names: `thin_sessions(min_names=spec)` and not
                   `thin_sessions(min_names=FLOOR)`; te4 builds its reduced-set target there.
  earning day      the decision two sessions earlier (shift(2): decide t, fill t+1, earn t+2).
  episode          runs of reduced decisions merged when fewer than 63 sessions apart (build_panel's ADV
                   window), as `third_rule.episodes`; its value sums the daily P&L over the runs'
                   earning days (i0+2 .. i1+2).

H14. Every threshold the draft names is RE-MEASURED by re-running this file on the read date; the draft
quotes drafting-day values only. m, the band, the ceiling and min_names are read from the frozen spec
through scripts/cef/spec.py at run time. FLOOR is the draft's proposed value, not yet a spec key: when
the key exists, read it from the spec instead.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PV = REPO / "results" / "cef" / "prereg_voltarget"
SCREEN = REPO / "results" / "backtests" / "thin-third-rule-2026-11-03"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(PV))

from scripts.cef import band_frontier as bf                       # noqa: E402
from scripts.cef import spec as S                                  # noqa: E402
from scripts.cef.portfolio_baseline import (HALVE_DD, max_drawdown,  # noqa: E402
                                            path_max_drawdown)
from scripts.research.inference import p_clear_bar, upper_bound_max_z   # noqa: E402
from _common import Paths, draw, odds                              # noqa: E402  (trial 53's bootstrap)
from _common import worst as worst_of                              # noqa: E402

STAMP = None                 # set in main() from --stamp (default: today); never a literal (finding 6)
# The floor: the spec's, once `below_min_names_floor` exists and scripts/cef/spec.py exposes it; until then
# the draft's proposed value (screen REPORT.md section 1: derived, not swept). The output names the source.
_FLOOR_SPEC = getattr(S, "BELOW_MIN_NAMES_FLOOR", None)
FLOOR = int(_FLOOR_SPEC) if _FLOOR_SPEC is not None else 4
FLOOR_SOURCE = "the spec's below_min_names_floor" if _FLOOR_SPEC is not None else \
    "the draft's proposed value; not yet a spec key"
LOOKS = (5, 9, 13, 20)       # the draft's declared PRESENT reads (section 6.1, after the quant review)
W1 = pd.Timestamp("2013-06-25")   # trial 53's W1 start (the core's first P&L-bearing session)
ADV_WINDOW = 63              # build_panel's ADV window: the episode merge gap (asserted below)
LS = (21, 63, 126, 252)      # in-episode drawdown horizons, in reduced-session earning days
NS = (53, 54, 55)            # bars shown: the CEF counter on main (53) and the next two values
P = 252
LOG, OUT = [], {}


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def runs_of(mask: pd.Series) -> list:
    """(first, last) positions of every run of True; the same as the screen's `attack.runs_of`."""
    a, out, i = mask.to_numpy(), [], 0
    while i < len(a):
        if not a[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(a) and a[j + 1]:
            j += 1
        out.append((i, j))
        i = j + 1
    return out


def episodes(trade: pd.Series) -> list:
    """Runs of reduced decisions merged when fewer than ADV_WINDOW sessions apart (the screen's rule)."""
    eps = []
    for i0, i1 in runs_of(trade):
        if eps and i0 - eps[-1]["i1"] - 1 < ADV_WINDOW:
            eps[-1]["i1"] = i1
            eps[-1]["parts"].append((i0, i1))
        else:
            eps.append(dict(i0=i0, i1=i1, parts=[(i0, i1)]))
    return eps


def earn_days(idx, parts) -> pd.DatetimeIndex:
    days = [idx[i0 + 2: i1 + 3] for i0, i1 in parts]
    return days[0].append(days[1:]) if len(days) > 1 else days[0]


def independent_book(T: pd.DataFrame, below: pd.Series, band: float, cap: float, defer: bool) -> pd.DataFrame:
    """Second method for §A1 (2026-11-03, after the quant review's finding 6): the unit book written again,
    row by row in numpy, without `band_gross_capped`. PR #33's `independent_flatten`
    (results/backtests/thin-days-2026-11-03/thin_days.py) with the band and the ceiling as arguments, so it
    holds at the read date's spec: a `below` row is FLAT; any other row moves each name more than `band`
    from its target to the band EDGE, scales the whole book down to `cap` if its gross is above it, and,
    with `defer`, holds a name whose sign flipped at zero for that session. For flatten, `below` is the
    min_names mask; for te4, the floor's mask (the screen reproduced every te book this way, to 1e-12)."""
    Tv, bv = T.to_numpy(dtype=float), below.reindex(T.index).to_numpy(dtype=bool)
    prev, out = np.zeros(T.shape[1]), np.empty(Tv.shape)
    for i in range(len(Tv)):
        if bv[i]:
            now = np.zeros_like(prev)
        else:
            d = Tv[i] - prev
            now = prev.copy()
            o = np.abs(d) > band
            now[o] = Tv[i][o] - np.sign(d[o]) * band
            g = np.abs(now).sum()
            if g > cap:
                now = now * (cap / g)
            if defer:
                now[(prev * now) < 0] = 0.0
        out[i] = now
        prev = now
    return pd.DataFrame(out, index=T.index, columns=T.columns)


def rows(H, Rtr, R, cap, win=W1) -> dict:
    """flatten_exact.py's figures for one book (the same expressions), plus the trading-session sd."""
    g = H.abs().sum(axis=1)
    earn = (g.shift(2).fillna(0.0) > 0).loc[win:]
    held = (g > 0).loc[win:]
    r = {}
    for b, RR in (("TR", Rtr), ("PR", R)):
        x = bf.evaluate(H, RR)["pnl"].loc[win:]
        xe = x[earn]
        dd = max_drawdown(x)
        r[b] = dict(ann=float(x.mean() * P), sr=float(x.mean() / x.std() * np.sqrt(P)),
                    mdd=float(dd["mdd"]), mdd_peak=str(dd["peak"])[:10], mdd_trough=str(dd["trough"])[:10],
                    ann_trading=float(xe.mean() * P),
                    vol_trading=float(xe.std() * np.sqrt(P)), sd_trading=float(xe.std()),
                    sr_trading=float(xe.mean() / xe.std() * np.sqrt(P)), sd_calendar=float(x.std()))
    at_cap = g.loc[win:] >= cap - 1e-9
    r["at_cap_all"] = float(at_cap.mean())
    r["at_cap_held"] = float(at_cap[held].mean())
    r["mean_gross_held"] = float(g.loc[win:][held].mean())
    r["earn_share"] = float(earn.mean())
    r["earn_days"] = int(earn.sum())
    return r


def fmt(lab, r) -> str:
    return (f"{lab}: TR {r['TR']['ann'] * 100:.2f}%/yr SR {r['TR']['sr']:.3f} maxDD {r['TR']['mdd'] * 100:.2f}% | "
            f"while trading {r['TR']['ann_trading'] * 100:.2f}%/yr vol {r['TR']['vol_trading'] * 100:.2f}% "
            f"SR {r['TR']['sr_trading']:.3f} | PR {r['PR']['ann'] * 100:.2f}%/yr SR {r['PR']['sr']:.3f} "
            f"maxDD {r['PR']['mdd'] * 100:.2f}% ({r['PR']['mdd_peak']} .. {r['PR']['mdd_trough']}) | earns on {r['earn_share']:.1%} of W1 | held at the cap "
            f"{r['at_cap_held']:.1%} of sessions with a book; mean gross when held {r['mean_gross_held']:.3f}")


def stops(x: dict, paths: Paths) -> dict:
    """R1-R3 by trial 53's declared definitions (stops.py docstring), on daily series x = {TR, PR}."""
    p95 = {b: max(float(np.quantile(path_max_drawdown(pth), 0.95))
                  for pth in draw(x[b], paths, "fit").values()) for b in ("TR", "PR")}
    I21 = paths.get(len(x["PR"]))[0]
    r2 = float(np.quantile(np.prod(1 + x["PR"][I21[:, :120]], axis=1) - 1, 0.05))
    r3 = float(np.quantile(x["PR"][I21[:, :60]].std(axis=1, ddof=1) * np.sqrt(P), 0.95))
    return dict(R1=min(HALVE_DD, max(p95.values())), R1_p95_raw=max(p95.values()), R2=r2, R3=r3)


def fire(x: dict, th: dict, paths: Paths) -> dict:
    """P(each stop fires within its horizon) when x is the truth, fit edge, SB21 (FLATTEN_REMEASURE §4)."""
    I21 = {b: paths.get(len(x[b]))[0] for b in ("TR", "PR")}
    r1 = max(float((path_max_drawdown(x[b][I21[b]]) >= th["R1"]).mean()) for b in ("TR", "PR"))
    r2 = float(((np.prod(1 + x["PR"][I21["PR"][:, :120]], axis=1) - 1) < th["R2"]).mean())
    r3 = float(((x["PR"][I21["PR"][:, :60]].std(axis=1, ddof=1) * np.sqrt(P)) > th["R3"]).mean())
    return dict(R1=r1, R2=r2, R3=r3)


def q(s: pd.Series) -> dict:
    return dict(p50=float(s.quantile(0.5)), p90=float(s.quantile(0.9)), p99=float(s.quantile(0.99)),
                max=float(s.max()), n=int(len(s)))


def main() -> int:
    import argparse
    import datetime as dt
    import inspect
    global STAMP
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stamp", default=dt.date.today().isoformat(),
                    help="date in the output file names (default: today)")
    ap.add_argument("--overwrite", action="store_true", help="allow replacing this stamp's existing files")
    # REQUIRED, no default (the runner owner's round-2 answer (c), 2026-11-05): the spec's
    # `risk.thin_k3_run_sessions` is the only authority on K3's run length, so this file takes it as given
    # and records it, and never holds a literal of its own (module docstring, REVISED 2026-11-05).
    ap.add_argument("--k3-run-sessions", type=int, required=True, metavar="N",
                    help="K3's run length: the spec's risk.thin_k3_run_sessions (an int of at least 2)")
    args = ap.parse_args()
    STAMP = args.stamp
    K3N = args.k3_run_sessions
    if K3N < 2:
        # The registry's own rule for the key (`cef_thin_stop_levels`): one close is the once line's.
        raise SystemExit(f"--k3-run-sessions {K3N} must be at least 2: one close above the line is the once "
                         f"rule's (thin_k3_net_once)")
    outs = (HERE / f"compose_{STAMP}.json", HERE / f"compose_output_{STAMP}.txt")
    if any(f.exists() for f in outs) and not args.overwrite:
        raise SystemExit(f"{[f.name for f in outs if f.exists()]} exist: a dated record is not overwritten "
                         f"silently. Pass --overwrite to replace it, or another --stamp.")
    if "rolling(63," not in inspect.getsource(bf.build_panel):
        raise AssertionError("build_panel's ADV window is no longer 63 sessions; ADV_WINDOW is stale")
    BAND, CAP, M = float(S.BAND_WIDTH), float(S.MAX_GROSS_STRESS), S.SIZING_MULTIPLIER
    if M is None:
        raise AssertionError(f"{S.SPEC_ID} carries no sizing_multiplier; this file composes te4 with trial 53")
    M = float(M)
    if not 2 <= FLOOR < int(S.MIN_NAMES):
        raise AssertionError(f"FLOOR {FLOOR} must satisfy 2 <= FLOOR < min_names {S.MIN_NAMES}")
    p(f"spec {S.SPEC_ID}: sizing_multiplier {M}, band {BAND}, max_gross_stress {CAP}, min_names {S.MIN_NAMES}, "
      f"min_abs_weight {S.MIN_ABS_WEIGHT}; FLOOR {FLOOR} ({FLOOR_SOURCE}); stamp {STAMP}")
    p(f"K3 run length {K3N} (--k3-run-sessions: the spec's risk.thin_k3_run_sessions; §E counts runs of {K3N} "
      f"and, for context, {K3N - 1})")
    OUT["spec"] = dict(id=S.SPEC_ID, m=M, band=BAND, cap=CAP, min_names=int(S.MIN_NAMES), floor=FLOOR)
    # The run length this file counted K3's runs with (§E), as given: the drift test reads it here.
    OUT["k3_run_sessions"] = K3N

    # ---------------------------------------------------------------- the books, fit only
    T6, R = bf.build_targets()
    T4, R4 = bf.build_targets(min_names=FLOOR)
    if not (R4.equals(R) and T4.index.equals(T6.index)):
        raise AssertionError("build_targets(min_names=FLOOR) changed R or the index")
    thin6 = bf.thin_sessions(T6.index)
    thin4 = bf.thin_sessions(T4.index, min_names=FLOOR)
    T6, Rf = bf.fit_only(T6, R)
    T4, _ = bf.fit_only(T4, R)
    thin6, thin4 = thin6.loc[T6.index], thin4.loc[T4.index]
    if T6.index.max() >= pd.Timestamp("2023-01-01") or Rf.index.max() >= pd.Timestamp("2023-01-01"):
        raise AssertionError("holdout leak")
    act = (~thin6).to_numpy()
    if not (T4.values[act] == T6.values[act]).all():
        raise AssertionError("te4 and the spec build different targets on a session with >= min_names eligible")
    reduced = thin6 & ~thin4
    Rtr = bf.total_returns(Rf)
    p(f"fit panel {T6.index.min().date()} .. {T6.index.max().date()}: {len(T6)} sessions, {int(thin6.sum())} thin "
      f"(< {S.MIN_NAMES} eligible), {int(reduced.sum())} reduced ({FLOOR}..{int(S.MIN_NAMES) - 1} eligible), "
      f"{int(thin4.sum())} below the floor; W1 ({W1.date()} on): {int(thin6.loc[W1:].sum())} thin, "
      f"{int(reduced.loc[W1:].sum())} reduced")
    OUT["sessions"] = dict(fit=len(T6), thin=int(thin6.sum()), reduced=int(reduced.sum()),
                           below_floor=int(thin4.sum()), w1_thin=int(thin6.loc[W1:].sum()),
                           w1_reduced=int(reduced.loc[W1:].sum()))

    def book(rule, m, deferred):
        if rule == "flatten":
            H = bf.band_gross_capped(T6, BAND, CAP / m, defer_flips=deferred, below_min_names="flatten", thin=thin6)
        else:
            H = bf.band_gross_capped(T4, BAND, CAP / m, defer_flips=deferred, below_min_names="trade_eligible",
                                     thin=thin4, floor=FLOOR)
        return m * H

    ms = sorted({1.0, 1.13, M})
    H = {(r, m, fl): book(r, m, fl == "deferred") for r in ("flatten", "te4") for m in ms
         for fl in ("instant", "deferred")}

    # ---------------------------------------------------------------- A. reproduction
    # A1, ASSERTED (a code check valid at any band, ceiling or panel): every book scored below equals the
    # independent loop at the read date's spec.
    worst_ind = 0.0
    for (rule, m, fl), Hx in H.items():
        T_, below = (T6, thin6) if rule == "flatten" else (T4, thin4)
        ind = independent_book(T_, below, BAND, CAP / m, fl == "deferred")
        worst_ind = max(worst_ind, float((Hx / m - ind).abs().to_numpy().max()))
    if worst_ind > 1e-12:
        raise AssertionError(f"a scored book differs from the independent loop (largest difference {worst_ind:.3e})")
    p(f"A1. every scored book (flatten and te4, m {', '.join(f'{m:.2f}' for m in ms)}, instant and deferred) = "
      f"the independent row-by-row loop at this spec (largest difference {worst_ind:.1e})")
    # A2, REPORTED, never raised: the drafting-day references (built at band 0.048, ceiling 1.8 and the
    # 2026-10-15 panel). A difference means the inputs or the fit rows moved since 2026-11-03; the read
    # date's values then govern (draft section 6.3).
    ref = json.loads((PV / "flatten_exact_2026-11-02.json").read_text())
    worst = 0.0
    for m in (1.0, 1.13, 1.3):
        if (m in ms) and str(m) in ref:
            r = rows(H[("flatten", m, "instant")], Rtr, Rf, CAP)
            for k in ("ann", "sr", "mdd", "ann_trading", "vol_trading", "sr_trading"):
                worst = max(worst, abs(r["TR"][k] - ref[str(m)]["TR"][k]))
            for k in ("ann", "sr"):
                worst = max(worst, abs(r["PR"][k] - ref[str(m)]["PR"][k]))
            for k in ("at_cap_all", "at_cap_held", "mean_gross_held"):
                worst = max(worst, abs(r[k] - ref[str(m)][k]))
    rem = json.loads((PV / "flatten_remeasure_2026-11-02_m1.30.json").read_text())
    sd_flat = rows(H[("flatten", 1.0, "instant")], Rtr, Rf, CAP)["TR"]["sd_trading"]
    d_sd = abs(sd_flat - rem["sd_daily"]["flatten_active"])
    scr = json.loads((SCREEN / "results.json").read_text())["review_attacks"]["h_episodes"]["flatten"]
    eps = episodes(reduced)
    gap = (bf.evaluate(H[("te4", 1.0, "instant")], Rtr)["pnl"] - bf.evaluate(H[("flatten", 1.0, "instant")], Rtr)["pnl"])
    vals = [float(gap.loc[earn_days(T6.index, e["parts"]).intersection(gap.index)].sum()) for e in eps]
    d_ep = max(abs(a - b) for a, b in zip(vals, scr["values"])) if len(vals) == len(scr["values"]) else np.inf
    if max(worst, d_sd, d_ep) <= 1e-9:
        p(f"A2. reproduced: flatten at m 1.00 / 1.13 / 1.30 = trial 53's flatten_exact_2026-11-02.json (largest "
          f"difference {worst:.1e}); flatten trading-session unit sd {sd_flat:.6f} = flatten_remeasure's; te4's "
          f"{len(vals)} fit episodes = the screen's (largest difference {d_ep:.1e})")
    else:
        p(f"A2. NOT reproduced (reported, not raised): flatten_exact difference {worst:.3e}; trading-session sd "
          f"{sd_flat:.6f} against {rem['sd_daily']['flatten_active']:.6f}; episodes {len(vals)} against "
          f"{len(scr['values'])}, difference {d_ep:.3e}. The band, the ceiling, m or the fit rows have moved "
          f"since 2026-11-03; A1 passed, so the values below are this read date's and govern")
    OUT["reproduction"] = dict(independent_loop_max_diff=worst_ind, flatten_exact_max_diff=worst,
                               sd_flatten_active=sd_flat, sd_diff=d_sd, episodes_max_diff=d_ep,
                               drafting_day_references_reproduced=bool(max(worst, d_sd, d_ep) <= 1e-9))

    # ---------------------------------------------------------------- B. trial 53's rows under te4
    p("\nB. trial 53's exact-build rows (W1 2013-06-25 .. 2022-12-30), flatten against te4")
    OUT["rows"] = {}
    for m in ms:
        for fl in ("instant", "deferred"):
            for rule in ("flatten", "te4"):
                r = rows(H[(rule, m, fl)], Rtr, Rf, CAP)
                OUT["rows"][f"{rule}/{m}/{fl}"] = r
                p("  " + fmt(f"{rule:7s} x{m:.2f} {fl:8s}", r))

    # ---------------------------------------------------------------- C. the rule's multiplier fed te4
    sd = rem["sd_daily"]
    m_c4_rule = rem["implied_core_multiplier"]["flatten_active"] * sd["flatten_active"] / sd["c4"]
    sd_te4 = OUT["rows"]["te4/1.0/instant"]["TR"]["sd_trading"]
    m_te4 = m_c4_rule * sd["c4"] / sd_te4
    p(f"\nC. the 2026-10-29 rule (m_core = m_c4_rule x sd_c4 / sd_core; m_c4_rule {m_c4_rule:.4f}, sd_c4 "
      f"{sd['c4']:.6f}, both from flatten_remeasure_2026-11-02_m1.30.json [S]): flatten trading-session sd "
      f"{sd['flatten_active']:.6f} -> {rem['implied_core_multiplier']['flatten_active']:.4f}; te4 trading-session "
      f"sd {sd_te4:.6f} -> {m_te4:.4f} (rounded down to 2 dp: {np.floor(m_te4 * 100) / 100:.2f})")
    OUT["multiplier"] = dict(m_c4_rule=m_c4_rule, sd_c4=sd["c4"], sd_flatten_active=sd["flatten_active"],
                             sd_te4_active=sd_te4, m_flatten=rem["implied_core_multiplier"]["flatten_active"],
                             m_te4=m_te4, m_te4_2dp_down=float(np.floor(m_te4 * 100) / 100))

    # ---------------------------------------------------------------- D. trial 53's stops
    paths = Paths()
    ser = {}
    for rule in ("flatten", "te4"):
        for fl in ("instant", "deferred"):
            Hx = H[(rule, M, fl)]
            g = Hx.abs().sum(axis=1)
            earn = (g.shift(2).fillna(0.0) > 0).loc[W1:]
            ser[(rule, fl)] = {b: bf.evaluate(Hx, RR)["pnl"].loc[W1:][earn].to_numpy()
                               for b, RR in (("TR", Rtr), ("PR", Rf))}
    th = {k: stops(v, paths) for k, v in ser.items()}
    approved = rem["thresholds_core"]["flatten_active"]
    p(f"\nD. trial 53's R1 / R2 / R3 at m {M}, calibrated on each exact book's W1 trading sessions (fit edge; "
      f"stops.py definitions). Trial 53's approved values (house cap model, flatten, earning-only) "
      f"{approved['R1'] * 100:.2f}% / {approved['R2'] * 100:+.2f}% / {approved['R3'] * 100:.2f}%:")
    for k, v in th.items():
        p(f"  {k[0]:7s} {k[1]:8s}: R1 {v['R1'] * 100:.2f}% (p95 raw {v['R1_p95_raw'] * 100:.2f}%) | "
          f"R2 {v['R2'] * 100:+.2f}% | R3 {v['R3'] * 100:.2f}% | trading sessions {len(ser[k]['TR'])}")
    fm = {}
    for truth in ser:
        for cal in th:
            fm[f"{truth[0]}/{truth[1]} <- {cal[0]}/{cal[1]}"] = fire(ser[truth], th[cal], paths)
    fm["te4/deferred <- approved (flatten, cap model)"] = fire(ser[("te4", "deferred")], approved, paths)
    fm["flatten/deferred <- approved (flatten, cap model)"] = fire(ser[("flatten", "deferred")], approved, paths)
    p("  P(fire within horizon), truth <- calibration, fit edge SB21 (nominal 5%; R1 below 5% by construction):")
    for k, v in fm.items():
        p(f"    {k:52s} R1 {v['R1']:.1%}  R2 {v['R2']:.1%}  R3 {v['R3']:.1%}")
    OUT["stops"] = dict(thresholds={f"{k[0]}/{k[1]}": v for k, v in th.items()}, approved=approved, fire=fm,
                        n_trading={f"{k[0]}/{k[1]}": int(len(v["TR"])) for k, v in ser.items()})

    # D2. zero-edge P(HALVE) / P(KILL) in 12 months while trading (trial 53's statistic: worst of SB21 /
    # SB63 / GAUSS, worse of TR / PR, HALVE not acting), at the spec's m and at te4's own rule value
    m_alt = float(np.floor(m_te4 * 100) / 100)
    od = {}
    for rule in ("flatten", "te4"):
        for fl in ("instant", "deferred"):
            od[f"{rule}/{M}/{fl}"] = ser[(rule, fl)]
    for fl in ("instant", "deferred"):
        Hx = book("te4", m_alt, fl == "deferred")
        g = Hx.abs().sum(axis=1)
        earn = (g.shift(2).fillna(0.0) > 0).loc[W1:]
        od[f"te4/{m_alt}/{fl}"] = {b: bf.evaluate(Hx, RR)["pnl"].loc[W1:][earn].to_numpy()
                                   for b, RR in (("TR", Rtr), ("PR", Rf))}
    OUT["odds_zero_trading"] = {}
    p(f"\nD2. zero-edge P(HALVE {HALVE_DD:.0%}) / P(KILL) within 252 trading sessions, W1 trading sessions, worst method, "
      f"worse of TR / PR (trial 53 approved 15.9% / 1.5% on the hold book; amendment 1: 16.7% / 1.68% on the "
      f"flatten book's trading sessions, house cap model [S]):")
    for k, x in od.items():
        o = {b: odds(x[b], paths, "zero") for b in ("TR", "PR")}
        h, kl = max(worst_of(o[b], 0) for b in o), max(worst_of(o[b], 1) for b in o)
        OUT["odds_zero_trading"][k] = dict(halve=h, kill=kl)
        p(f"  {k:22s}: P(HALVE) {h:.1%}  P(KILL) {kl:.2%}")

    # ---------------------------------------------------------------- E. the draft's in-episode stops
    Hi = H[("te4", M, "instant")]
    Hd = H[("te4", M, "deferred")]
    first = reduced.index[reduced.to_numpy()].min()
    red_dec = reduced.loc[first:]
    red_earn = reduced.shift(2).reindex(Hd.index).fillna(False).astype(bool)
    xr = {b: bf.evaluate(Hd, RR)["pnl"][red_earn].to_numpy() for b, RR in (("TR", Rtr), ("PR", Rf))}
    de = {}
    for L in LS:
        pl = Paths(horizon=L)
        de[L] = {b: {lab: float(np.quantile(path_max_drawdown(pth), 0.95))
                     for lab, pth in draw(xr[b], pl, "fit").items()} for b in ("TR", "PR")}
        de[L]["D_E"] = max(max(de[L][b].values()) for b in ("TR", "PR"))
    gH = Hd.abs().sum(axis=1)
    mx = Hd.abs().max(axis=1)
    net = Hd.sum(axis=1).abs()
    rd = red_dec.index[red_dec.to_numpy()]
    ad = T6.index[(~thin6).to_numpy() & (T6.index >= first)]
    ad = ad[gH.loc[ad].to_numpy() > 0]
    tw = T4.loc[rd]
    single = ((tw > 0).sum(axis=1).eq(1) | (tw < 0).sum(axis=1).eq(1))
    conc = dict(reduced_max_w=q(mx.loc[rd]), active_max_w=q(mx.loc[ad]), reduced_net=q(net.loc[rd]),
                active_net=q(net.loc[ad]), reduced_gross=q(gH.loc[rd]),
                reduced_at_cap=float((gH.loc[rd] >= CAP - 1e-9).mean()),
                active_at_cap=float((gH.loc[ad] >= CAP - 1e-9).mean()),
                reduced_single_fund_side=float(single.mean()),
                reduced_net_instant=q(Hi.sum(axis=1).abs().loc[rd]),
                # the vol scalar IS the unit target's gross (sum|w| = 1 before it): clip(0.06 / rv, 0.2, 2.5)
                scalar_reduced=q(T4.loc[rd].abs().sum(axis=1)), scalar_active=q(T6.loc[ad].abs().sum(axis=1)),
                scalar_at_clip_reduced=int(((T4.loc[rd].abs().sum(axis=1) - 2.5).abs() < 1e-12).sum()
                                           + ((T4.loc[rd].abs().sum(axis=1) - 0.2).abs() < 1e-12).sum()),
                reduced_net_top_deferred={str(k.date()): float(v) for k, v in
                                          net.loc[rd].sort_values(ascending=False).head(5).items()})
    p(f"\nE. in-episode stops at m {M}, te4 deferred, fit from the first reduced decision {first.date()} "
      f"({len(rd)} reduced decisions, {int(red_earn.sum())} reduced earning days):")
    for L in LS:
        p(f"  D_E({L}) = {de[L]['D_E'] * 100:.2f}% (TR {', '.join(f'{k} {v * 100:.2f}' for k, v in de[L]['TR'].items())}; "
          f"PR {', '.join(f'{k} {v * 100:.2f}' for k, v in de[L]['PR'].items())})")
    for k in ("reduced_max_w", "active_max_w", "reduced_net", "active_net", "reduced_net_instant", "reduced_gross",
              "scalar_reduced", "scalar_active"):
        v = conc[k]
        p(f"  {k:14s} p50 {v['p50']:.3f}  p90 {v['p90']:.3f}  p99 {v['p99']:.3f}  max {v['max']:.3f}  [n {v['n']}]")
    p(f"  largest reduced |net| (deferred): {conc['reduced_net_top_deferred']}; vol scalar at a clip on "
      f"{conc['scalar_at_clip_reduced']} reduced decisions")
    p(f"  held at the cap ({CAP}x NAV): reduced {conc['reduced_at_cap']:.1%}, active {conc['active_at_cap']:.1%}; "
      f"a single-fund side in the reduced TARGET on {conc['reduced_single_fund_side']:.1%} of reduced decisions")
    # does the vol scalar hold the 6% unit target on 4-5 names? realised vol of the UNIT te4 book (instant)
    # on earning days after a reduced decision against earning days after a full one, fit from `first`
    pu = bf.evaluate(H[("te4", 1.0, "instant")], Rtr)["pnl"].loc[first:]
    gu = H[("te4", 1.0, "instant")].abs().sum(axis=1).shift(2).reindex(pu.index).fillna(0.0) > 0
    re_ = red_earn.reindex(pu.index).fillna(False).astype(bool)
    vol_split = dict(reduced=float(pu[re_ & gu].std() * np.sqrt(P)), full=float(pu[~re_ & gu].std() * np.sqrt(P)),
                     n_reduced=int((re_ & gu).sum()), n_full=int((~re_ & gu).sum()),
                     target=float(S.VOL_TARGET))
    p(f"  unit te4 (instant) realised vol, fit from {first.date()}: reduced earning days "
      f"{vol_split['reduced'] * 100:.2f}% [n {vol_split['n_reduced']}], full earning days "
      f"{vol_split['full'] * 100:.2f}% [n {vol_split['n_full']}] (the scalar targets vol_target_annual "
      f"{vol_split['target']})")
    conc["vol_split_unit"] = vol_split
    # how often the draft's persistence rule (K3N consecutive reduced decisions above the fit p99; §6.3's 3)
    # fires on the fit itself, per statistic: the false-alarm count of the rule on the book it was calibrated
    # on, with runs of K3N - 1 beside it for context. K3N is --k3-run-sessions, never a literal (REVISED
    # 2026-11-05); the keys carry the run length, so at 3 they are the drafting day's.
    def runs_above(stat: pd.Series, thr: float, k: int) -> int:
        a = (stat.loc[rd] > thr).to_numpy()
        n, c = 0, 0
        for v in a:
            c = c + 1 if v else 0
            n += int(c == k)
        return n
    run_keys = {k: f"runs_of_{k}_above_p99" for k in (K3N, K3N - 1)}
    persist = {lab: {"p99": float(st.loc[rd].quantile(0.99)), "max": float(st.loc[rd].max()),
                     **{key: runs_above(st, float(st.loc[rd].quantile(0.99)), k) for k, key in run_keys.items()}}
               for lab, st in (("max_w", mx), ("net", net))}
    p("  persistence on the fit (reduced decisions in sequence): " + "; ".join(
        f"{k}: runs of {K3N - 1} above p99 {v[run_keys[K3N - 1]]}, runs of {K3N} {v[run_keys[K3N]]}"
        for k, v in persist.items()))
    OUT["in_episode"] = dict(first_reduced=str(first.date()), D_E={str(L): de[L] for L in LS}, concentration=conc,
                             persistence=persist)

    # ---------------------------------------------------------------- F. the unit of inference at m
    OUT["episodes"] = {}
    for fl in ("instant", "deferred"):
        Hx = H[("te4", M, fl)]
        pn = {b: bf.evaluate(Hx, RR)["pnl"] for b, RR in (("TR", Rtr), ("PR", Rf))}
        tab = []
        for e in eps:
            d = earn_days(T6.index, e["parts"]).intersection(pn["TR"].index)
            dec = T6.index[e["i0"]: e["i1"] + 1]
            dec = dec[reduced.loc[dec].to_numpy()]
            tab.append(dict(first=str(T6.index[e["i0"]].date()), last=str(T6.index[e["i1"]].date()),
                            runs=len(e["parts"]), earn_days=int(len(d)),
                            TR=float(pn["TR"].loc[d].sum()), PR=float(pn["PR"].loc[d].sum()),
                            mdd_TR=float(max_drawdown(pn["TR"].loc[d])["mdd"]),
                            mdd_PR=float(max_drawdown(pn["PR"].loc[d])["mdd"]),
                            max_w=float(Hx.abs().max(axis=1).loc[dec].max())))
        v = {b: np.array([t[b] for t in tab]) for b in ("TR", "PR")}
        es = {b: float(v[b].mean() / v[b].std(ddof=1)) for b in ("TR", "PR")}
        pw = {N: {n: float(p_clear_bar(es["PR"] * np.sqrt(n), float(upper_bound_max_z(N)))) for n in (2, 3, 5, 9, 13)}
              for N in NS}
        OUT["episodes"][fl] = dict(table=tab, effect=es, p_pass_PR=pw,
                                   bars={N: float(upper_bound_max_z(N)) for N in NS})
        p(f"\nF. te4 fit episodes at m {M}, {fl} flips (pp of NAV over the episode's thin earning days; flatten "
          f"earns exactly 0 there):")
        for t in tab:
            p(f"  {t['first']}..{t['last']} ({t['runs']} runs, {t['earn_days']} earning days): TR {t['TR'] * 100:+.2f} "
              f"PR {t['PR'] * 100:+.2f} | within-episode maxDD TR {t['mdd_TR'] * 100:.2f}% PR {t['mdd_PR'] * 100:.2f}% "
              f"| largest single-name |w| {t['max_w']:.3f}")
        p(f"  per-episode effect (mean/sd): TR {es['TR']:.2f}, PR {es['PR']:.2f}; P(pass) at the PR effect by forward "
          f"episodes: " + " | ".join(f"N={N} (bar {upper_bound_max_z(N):.3f}): " + ", ".join(
              f"{n}: {pw[N][n]:.2f}" for n in (2, 3, 5, 9, 13)) for N in NS))

    # G. the declared pass and ABSENT rules, at the per-episode effect on paper's basis (PR, deferred, m) and at
    # the screen's holdout shrink (results.json review_attacks.m_power.shrink). PASS: one-sample t of k episode
    # values >= the t(k-1) critical value at the bar's one-sided p (the screen's attack h). Exact small-sample
    # power from the noncentral t, beside the screen's normal approximation (inference.p_clear_bar), which is
    # generous at small k. ABSENT: the first two episodes both negative, or the mean of the first three <= 0.
    from math import erf, sqrt as _sqrt
    from scipy import stats as sps
    shrink = json.loads((SCREEN / "results.json").read_text())["review_attacks"]["m_power"]["shrink"]
    es0 = OUT["episodes"]["deferred"]["effect"]["PR"]
    G = dict(effect_pr_deferred=es0, shrink=shrink, power={}, absent={})
    p(f"\nG. declared rules at per-episode effect {es0:.2f} (PR, deferred, m {M}) and shrunk x{shrink:.2f} "
      f"({es0 * shrink:.2f}), and at zero:")
    for N in NS:
        bar = float(upper_bound_max_z(N))
        pb = 0.5 * (1 - erf(bar / _sqrt(2)))
        G["power"][N] = {}
        for k in (3, 5, 9, 13, 20):
            crit = float(sps.t.ppf(1 - pb, k - 1))
            row = {}
            for lab, e in (("fit", es0), ("shrunk", es0 * shrink)):
                row[lab] = dict(normal=float(p_clear_bar(e * np.sqrt(k), bar)),
                                exact_t=float(1 - sps.nct.cdf(crit, k - 1, e * np.sqrt(k))))
            row["t_crit"] = crit
            G["power"][N][k] = row
        p(f"  N={N} (bar {bar:.3f}, one-sided p {pb:.5f}): P(PASS) normal / exact-t, fit | shrunk: " + "; ".join(
            f"k={k}: {G['power'][N][k]['fit']['normal']:.2f}/{G['power'][N][k]['fit']['exact_t']:.3f} | "
            f"{G['power'][N][k]['shrunk']['normal']:.2f}/{G['power'][N][k]['shrunk']['exact_t']:.3f} "
            f"(t crit {G['power'][N][k]['t_crit']:.2f})" for k in (3, 5, 9, 13, 20)))
    for lab, e in (("fit", es0), ("shrunk", es0 * shrink), ("zero", 0.0)):
        ph = 0.5 * (1 + erf(-e / _sqrt(2)))
        G["absent"][lab] = dict(first_two_negative=ph ** 2,
                                mean_of_three_le_0=0.5 * (1 + erf(-e * np.sqrt(3) / _sqrt(2))))
        # P(either) is simulated: the two events overlap, so their probabilities do not add
        rng = np.random.default_rng(20261103)
        z = rng.standard_normal((200_000, 3)) + e
        G["absent"][lab]["either"] = float((((z[:, 0] < 0) & (z[:, 1] < 0)) | (z.mean(axis=1) <= 0)).mean())
        p(f"  ABSENT at effect {lab} ({e:.2f}): first two negative {G['absent'][lab]['first_two_negative']:.3f}; mean "
          f"of three <= 0 {G['absent'][lab]['mean_of_three_le_0']:.3f}; either (simulated, 200,000) "
          f"{G['absent'][lab]['either']:.3f}")
    OUT["rules"] = G

    # G2. Repeated reads (quant review, findings 4 and 5). The draft first read PRESENT at EVERY completed
    # episode against the single-read one-sided p: the chance of a false PRESENT then accumulates over the
    # reads. Simulated here for k = 2..20 under the null and at the fit and shrunk effects, with the ABSENT
    # stop applied (an ABSENT ends the path; a futility stop can only lower the false-PRESENT rate), for:
    #   every     PRESENT read at every completed episode, at p (the draft as first written);
    #   declared  PRESENT read only at LOOKS = 5, 9, 13, 20, each at p / len(LOOKS) (Bonferroni): the
    #             family-wise false-PRESENT rate is at most p by construction, and the simulation shows it.
    # Episode values are N(effect, 1): the per-episode effect is mean / sd, as §F and §G. Also the exact
    # single-read power by k, to find the first k past a coin flip at the fit effect.
    N2 = NS[1]
    bar2 = float(upper_bound_max_z(N2))
    pb2 = 0.5 * (1 - erf(bar2 / _sqrt(2)))
    G2 = dict(N=N2, bar=bar2, p_single=pb2, looks=list(LOOKS), p_each=pb2 / len(LOOKS), sim={})
    REPS2, KMAX = 400_000, max(LOOKS)
    for lab, e in (("zero", 0.0), ("fit", es0), ("shrunk", es0 * shrink)):
        Z = np.random.default_rng(20261103).standard_normal((REPS2, KMAX)) + e
        res = {}
        for design, looks, a in (("every", tuple(range(2, KMAX + 1)), pb2),
                                 ("declared", LOOKS, pb2 / len(LOOKS))):
            alive = np.ones(REPS2, bool)
            present = np.zeros(REPS2, bool)
            byk = {}
            for k in range(2, KMAX + 1):
                z = Z[:, :k]
                mk = z.mean(axis=1)
                t = mk / (z.std(axis=1, ddof=1) / np.sqrt(k))
                ab = ((k == 2) & (z[:, 0] < 0) & (z[:, 1] < 0)) | ((k >= 3) & (mk <= 0))
                newp = (alive & (t >= float(sps.t.ppf(1 - a, k - 1))) & ~ab) if k in looks else np.zeros(REPS2, bool)
                present |= newp
                alive &= ~(newp | ab)
                byk[k] = float(present.mean())
            res[design] = {k: byk[k] for k in (3, 5, 9, 13, 20)}
        G2["sim"][lab] = res
    rates = json.loads((SCREEN / "results.json").read_text())["review_attacks"]["m_power"]
    single = {k: float(1 - sps.nct.cdf(float(sps.t.ppf(1 - pb2, k - 1)), k - 1, es0 * np.sqrt(k))) for k in range(3, 21)}
    k_half = min(k for k, v in single.items() if v >= 0.5)
    G2.update(exact_single_read_fit=single, first_k_past_half=k_half,
              years_first_k_past_half=dict(fit_rate=k_half / rates["rate_fit"], since_2023=k_half / rates["rate_since_2023"]),
              years_looks=dict(fit_rate={k: k / rates["rate_fit"] for k in LOOKS},
                               since_2023={k: k / rates["rate_since_2023"] for k in LOOKS}))
    p(f"\nG2. repeated reads at N={N2} (bar {bar2:.3f}, single-read one-sided p {pb2:.5f}); P(PRESENT by k), "
      f"simulated {REPS2:,} paths with the ABSENT stop; 'every' = read at every episode at p (the draft as first "
      f"written); 'declared' = read only at k in {LOOKS}, each at p/{len(LOOKS)} = {pb2 / len(LOOKS):.6f}:")
    for lab in ("zero", "fit", "shrunk"):
        for design in ("every", "declared"):
            p(f"  {lab:6s} {design:8s}: " + ", ".join(f"k={k} {v:.4f}" for k, v in G2['sim'][lab][design].items()))
    p(f"  exact single-read P(PRESENT) at the fit effect {es0:.2f}: " + ", ".join(
        f"k={k} {single[k]:.3f}" for k in (5, 9, 10, 13, 20)) + f"; first k at or past 0.5: {k_half} "
      f"({k_half / rates['rate_fit']:.1f} years at {rates['rate_fit']:.2f}/yr, {k_half / rates['rate_since_2023']:.1f} "
      f"at {rates['rate_since_2023']:.2f}/yr [S screen rates])")
    OUT["rules"]["repeated_reads"] = G2

    outs[0].write_text(json.dumps(OUT, indent=1, default=str))
    outs[1].write_text("\n".join(LOG) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
