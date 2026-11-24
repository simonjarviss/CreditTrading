"""Thin sessions, a THIRD rule: trade the eligible names (report only, 2026-11-03).

ZERO TRIALS, NO SPEC CHANGE, NOTHING CHOSEN. On a decision date with fewer than
the spec's `min_names` eligible names the live sleeve FLATTENS (PR #33,
results/backtests/thin-days-2026-11-03/REPORT.md section 1) and the harness's
default HOLDS the previous target. The team lead (2026-11-02) asked for a third
rule to be screened: trade the eligible names, with the sleeve's own
construction on the smaller set. Every book here is the canonical path:
`build_targets` -> `band_gross_capped` -> `evaluate` (shift(2): decide t, fill
t+1, earn t+2), total returns cut at DIST_END (PR #33's `thin_days.load`, which
asserts the cut and the live sleeve's thin set), the spec read through
`scripts/cef/spec.py`.

DECLARED BEFORE ANY OF THIS RAN (REPORT.md section 1 holds the derivation):
  * the floor is 4, DERIVED from what the construction does at each count
    (1 name: 0/0; 2: only the sign of z1 - z2; 3: one side is always a single
    fund holding half the gross; 4: the first count with none of those). The
    plateau is checked at 3, 4 and 5 on the FIT period only. Nothing is chosen
    from any row, and nothing from the 2023+ rows (H13);
  * below the floor the rule does what the live sleeve does: FLAT;
  * rules scored: hold, flatten, trade_eligible at 3 / 4 / 5 (te3, te4, te5),
    each with instant and deferred flips; te4 is the row the questions ask about;
  * the leave-one-name-out runs PHK and PTY first, because PR #33 found them the
    two largest contributors to hold's thin-day P&L; every other name is printed
    beside them so nothing is selected by the ranking;
  * the direction control (H12): on every thin session the rule trades, the
    reduced-set target's weights are reassigned among THAT session's eligible
    names by a random order drawn once per thin stretch (same names, same gross,
    same weight distribution, stable within a stretch, direction random). SEED
    20261103, 500 draws, instant flips;
  * borrow: the IBKR FEE_RATE panel where it exists (2021-09-13 on); before
    that it is unmeasured and the report says so; never charged in the headline.

ADDED AFTER A FIRST (SMOKE) RUN, stated so the order is visible: that run
printed the scoreboard, the paired gaps, the plateau, the matched rows, the
leave-outs, the borrow and the forward block, and showed te4 ahead of both rules
in the fit period. The ATTACKS on that result were then added, before any of
them ran: (a) the thin-day P&L split between eligible names and the band's
residues in ineligible names; (b) the stale-price signature; (c) the
distribution leg and the beta; (d) the stretches as the unit; (e) the gap
without its best 10 days; (f) the deflated bar at N = 52 / 53 / 54; the
per-traded-session plateau; and the replay of the two degenerate sessions. The
direction control had not yet run. A fix to the hypothetical in step 5 (one 0/0
target, 2025-04-07, made its median cosine NaN) was made at the same time.

CHANGED AND ADDED AFTER THE REVIEW AND THE BETA-DETECTOR PASS (2026-11-03), after
the first full run, stated so the order is visible. Nothing below chooses a
parameter; each item is a check the two passes made in scratch, moved here so
the report can cite committed code:
  * H2 (the review's finding 1): `matched` now prints the paired gap, its NW t,
    the bar and `read_result` at the matched turnover, not only ann% and SR. The
    HEADLINE is the device declared before the smoke run (te4 re-banded to each
    reference's FIT turnover); each reference re-banded to te4's FIT turnover
    is printed beside it as a sensitivity, declared at the same time;
  * `read_result`'s `meaningful` is now the cost hurdle its docstring asks for:
    te4's extra FIT turnover over the reference at the spec band, times the
    grid's middle cost (15bp). It was the observed estimate, which made ABSENT
    unreachable (the review's open question 4);
  * borrow (the review's finding 4) goes through `bf.borrow_charge`, the
    harness's one definition (fee at t-1, 102% collateral, actual/360 on the
    shift(2) held book); the simple annual rate on short weight is gone;
  * the forward estimate (the review's finding 3) adds the one out-of-sample
    analogue (2023+ itself) as a base, and sizes the book at m the way trial 53
    is activated (m x band_gross_capped(T, band, max_gross_stress / m)) rather
    than ignoring the ceiling;
  * the beta-detector's attacks, re-run here (`review_attacks`): the gap by fund
    sponsor (every sponsor printed); te4's own two largest contributors (PHK,
    PDI) left out by attribution and by rebuilt universe; the FIT stretches
    merged into independent episodes when fewer than 63 sessions apart (the
    ADV window in `build_panel`); the gap without its three largest stretches;
    the recent-books placebo (PR #33's lagged books, adapted) and a static
    tilt; extra execution delay; a Dimson factor regression on the repo's ETF
    panel; and the power of a forward test by independent episodes.

CHANGED IN THE FINISHING PASS (2026-11-03), after the second full run, stated so
the order is visible:
  * the Dimson lag in attack l is DERIVED, not copied. The second run used lags
    0..2, the beta-detector's scratch choice, which nothing derived (the team
    lead, 2026-11-02: re-derive the exposure readout's Dimson lag properly
    before its next reading). The rule, declared before it ran: regress the
    universe's equal-weight return (the instruments, never the gap under test)
    on the four factors at lags 0..DIMSON_MAX over the FIT window; K is the
    last lag of the unbroken run of lags 1, 2, ... whose four coefficients are
    jointly significant (HAC Wald, p < 0.05). The gap is regressed at lags
    0..K; lags 0, 1 (the repo's convention: W4 section 6, the portfolio
    framework's risk model) and 2 (the second run's) are printed beside it as
    sensitivities, and nothing is chosen from them.

SECOND METHODS, all asserted:
  * the reduced-set targets equal the LIVE SLEEVE's own output on every thin
    session (sleeve_reduced.csv, from sleeve_reduced_check.py), after its gross
    ceiling, wherever its min-weight block does not act;
  * the trade_eligible books equal an independently written pandas loop
    (PR #33's `independent_flatten`, given the floor's targets and mask);
  * `scripts.research.harness.report` (nan_policy="raise") reproduces te4's fit
    and holdout Sharpe ratios.

    python3 results/backtests/thin-third-rule-2026-11-03/third_rule.py     # about 5-8 min

Writes run.log (gitignored) and results.json beside this file. Reads data/ only.
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]          # the worktree root
TD = REPO / "results" / "backtests" / "thin-days-2026-11-03"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TD))

import numpy as np                                    # noqa: E402
import pandas as pd                                   # noqa: E402

import attack as ak                                   # noqa: E402  (PR #33; imports thin_days)
import thin_days as td                                # noqa: E402
from scripts.cef import band_frontier as bf           # noqa: E402
from scripts.cef.spec import (BAND_WIDTH, MAX_GROSS_STRESS, MIN_ADV_USD,   # noqa: E402
                              MIN_NAMES, SPEC_ID, UNIVERSE, spec)
from scripts.research.harness import ERAS, HOLDOUT_START, report   # noqa: E402
from src.deploy.registry import cef_below_min_names   # noqa: E402
from src.deploy.sleeves.cef_discount import _cap_gross   # noqa: E402

FLOOR = 4                    # derived (REPORT.md section 1), not swept
PLATEAU = (3, 4, 5)          # the floor and one either side
SEED, N_DRAWS = 20261103, 500
COSTS = (5, 15, 30)
HURDLE_BP = 15               # the cost grid's middle: read_result's `meaningful` is the extra turnover at this cost
P = 252
FLIPS = ("instant", "deferred")
MAIN = ("hold", "flatten", "te4")
NS = (52, 53, 54)            # the CEF counter on main (52), at the release tag (53), and the next trial (54)
ADV_WINDOW = 63              # build_panel's ADV rolling window (asserted in review_attacks): the episode merge gap
DIMSON_MAX = 10              # the derivation's bound (two trading weeks); it RAISES if the derived lag reaches it
DIMSON_P = 0.05              # a lag counts while its four factor coefficients are jointly significant at this level
LOG, OUT = [], {}


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def nwt(x):
    return ak.nwt(x)


def te(f):
    return f"te{f}"


# --------------------------------------------------------------------------- inputs
def eligible_count(panel, index, universe=None):
    U = UNIVERSE if universe is None else universe
    z, adv = panel["z"].reindex(index)[U], panel["adv"].reindex(index)[U]
    return (z.notna() & (adv >= MIN_ADV_USD)).sum(axis=1)


def inputs():
    T, R, thin, panel, dist_end, keep, Rt = td.load()
    cnt = eligible_count(panel, T.index)
    if not (thin.to_numpy() == (cnt < MIN_NAMES).to_numpy()).all():
        raise AssertionError("thin_sessions and the eligible count disagree")
    TF, BF = {}, {}
    for f in PLATEAU:
        TF[f], Rf = bf.build_targets(min_names=f)
        if not (Rf.equals(R) and TF[f].index.equals(T.index)):
            raise AssertionError(f"build_targets(min_names={f}) changed R or the index")
        BF[f] = bf.thin_sessions(T.index, min_names=f)
        if not (BF[f].to_numpy() == (cnt < f).to_numpy()).all():
            raise AssertionError(f"the floor-{f} mask is not 'fewer than {f} eligible'")
        if (BF[f] & ~thin).any():
            raise AssertionError(f"the floor-{f} mask flags a session the spec calls active")
        act = (~thin).to_numpy()
        if not (TF[f].values[act] == T.values[act]).all():
            raise AssertionError(f"floor {f}: a session with >= {MIN_NAMES} eligible has another target")
    for f in PLATEAU[1:]:
        rows = (cnt >= f).to_numpy()
        if not (TF[f].values[rows] == TF[PLATEAU[0]].values[rows]).all():
            raise AssertionError(f"floor {f} and floor {PLATEAU[0]} built different targets on a session both trade")
    p(f"targets at floors {PLATEAU}: identical to the spec targets on every session with >= {MIN_NAMES} eligible, "
      "and identical to each other wherever both floors trade (the construction does not read the floor)")
    return T, R, thin, panel, dist_end, keep, Rt, TF, BF, cnt


def sleeve_check(T, thin, TF, cnt):
    """Second method 1: the live sleeve's own reduced-set targets (sleeve_reduced.csv)."""
    s = pd.read_csv(HERE / "sleeve_reduced.csv", parse_dates=["date"]).set_index("date")
    dates = T.index[thin.to_numpy()]
    if not s.index.equals(dates):
        raise AssertionError("sleeve_reduced.csv is not on the thin sessions; re-run sleeve_reduced_check.py")
    below = (s["status"] == "below").to_numpy()
    c = cnt.loc[dates].to_numpy()
    if not (below == (c < PLATEAU[0])).all():
        raise AssertionError("the sleeve's below-floor set differs from the eligible count")
    if not (s["n_below"].to_numpy()[below] == c[below]).all():
        raise AssertionError("the sleeve's count differs from the harness's on a below-floor session")
    tr = dates[~below]
    W = s.loc[tr, UNIVERSE]
    ref = pd.DataFrame([_cap_gross(TF[PLATEAU[0]].loc[d], MAX_GROSS_STRESS)[0].reindex(UNIVERSE).values
                        for d in tr], index=tr, columns=UNIVERSE)
    diff = (W - ref).abs().max(axis=1)
    # The sleeve's min-weight block acts on an eligible name whose weight is under min_abs_weight, before the
    # ceiling (re-neutralise, l.926-933) or after it (FLAT, l.1195). The ceiling only scales down, so a weight
    # under the threshold before it is under it after: flag on the capped harness target.
    minw = bf_minw()
    small = ((ref != 0) & (ref.abs() < minw)).any(axis=1)
    dropped = ((ref != 0) & (W == 0)).any(axis=1)          # an eligible name the sleeve sent FLAT
    clean = ~small
    mx_clean = float(diff[clean].max())
    if mx_clean > 1e-12:
        raise AssertionError(f"the sleeve's reduced-set target differs from the harness's by {mx_clean}")
    if (dropped & clean).any():
        raise AssertionError("the sleeve sent an eligible name FLAT on a session with no weight under min_abs_weight")
    cs = pd.Series(c[~below], index=tr)
    out = dict(thin=len(dates), below=int(below.sum()), traded=len(tr), clean=int(clean.sum()),
               max_abs_diff_clean=mx_clean, minw_rows=int(small.sum()), minw_dropped_rows=int(dropped.sum()),
               max_abs_diff_minw=float(diff[small].max()) if small.any() else 0.0,
               minw_by_n={int(k): int(v) for k, v in cs[small].value_counts().sort_index().items()},
               minw_by_n_floor4={int(k): int(v) for k, v in cs[small & (cs >= FLOOR)].value_counts().sort_index().items()})
    p(f"second method 1 [live sleeve, min_names {MIN_NAMES} -> {PLATEAU[0]} in memory, on all {len(dates)} thin "
      f"sessions]: below the floor on {out['below']} (count identical); traded on {len(tr)}; on the {out['clean']} "
      f"with no eligible weight under min_abs_weight ({minw}) the sleeve's target after its ceiling equals "
      f"_cap_gross(build_targets row) to {mx_clean:.1e}; on the other {out['minw_rows']} its min-weight block acts "
      f"(an eligible name sent FLAT on {out['minw_dropped_rows']}; max abs weight diff {out['max_abs_diff_minw']:.4f}); "
      f"by eligible count {out['minw_by_n']}")
    OUT["sleeve_check"] = out


def bf_minw():
    from scripts.cef.spec import MIN_ABS_WEIGHT
    return float(MIN_ABS_WEIGHT)


def books(T, thin, TF, BF, b=BAND_WIDTH, cap=MAX_GROSS_STRESS, rules=("hold", "flatten") + tuple(te(f) for f in PLATEAU),
          flips=FLIPS):
    H = {}
    for rule in rules:
        for fl in flips:
            d = fl == "deferred"
            if rule == "hold":
                H[(rule, fl)] = bf.band_gross_capped(T, b, cap, defer_flips=d)
            elif rule == "flatten":
                H[(rule, fl)] = bf.band_gross_capped(T, b, cap, defer_flips=d, below_min_names="flatten", thin=thin)
            else:
                f = int(rule[2:])
                H[(rule, fl)] = bf.band_gross_capped(TF[f], b, cap, defer_flips=d, below_min_names="trade_eligible",
                                                     thin=BF[f], floor=f)
    return H


# --------------------------------------------------------------------------- step 3
def thin_days_of(thin, idx):
    """Earning-day mask: the decision two sessions earlier was a thin session (H1)."""
    t = thin.shift(2).reindex(idx)
    return t.where(t.notna(), False).astype(bool)


def scoreboard(res, thin, dist_end, rules, title, key):
    W = td.windows(dist_end)
    rows = {}
    for (rule, fl), r in res.items():
        if rule not in rules:
            continue
        for lab, a, b in W:
            rows[(rule, fl, lab)] = td.stats(r["pnl"].loc[a:b], r["turn_series"].loc[a:b])
    p(f"\n=== {title} ===")
    p("gross total return is the headline; net = ann - turn x c is the real-money view, labelled; no borrow charged; "
      "vol-matched = scaled to 6% on its own ex-post vol (descriptive)")
    p(f"{'window':<11}{'rule':<8}{'flips':<9}{'SR':>6}{'ann%':>7}{'vol%':>6}{'maxDD%':>7}{'turn':>6} | "
      f"{'net%/yr @5/@15/@30':>22} | {'BE bp':>6} {'flip?':>6} | {'vm ann%':>8}{'vm @15':>7}")
    for lab, a, b in W:
        for rule in rules:
            for fl in FLIPS:
                s = rows.get((rule, fl, lab))
                if s is None:
                    continue
                if s["flat"]:
                    p(f"{lab:<11}{rule:<8}{fl:<9} flat: held nothing (turn {s['turn']:.1f})")
                    continue
                nets = "/".join(f"{s['net'][c] * 100:.2f}" for c in COSTS)
                fl_ = f"{s['flip_bp']}bp" if s["flip_bp"] else "no"
                p(f"{lab:<11}{rule:<8}{fl:<9}{s['sr']:6.2f}{s['ann'] * 100:7.2f}{s['vol'] * 100:6.2f}"
                  f"{s['maxdd'] * 100:7.1f}{s['turn']:6.1f} | {nets:>22} | {s['be']:6.1f} {fl_:>6} | "
                  f"{s['vm']['ann'] * 100:8.2f}{s['vm']['net'][15] * 100:7.2f}")
    OUT[key] = {f"{k[0]}/{k[1]}/{k[2]}": v for k, v in rows.items()}
    return rows


def paired(res, dist_end, rule, refs, key):
    W = td.windows(dist_end)
    p(f"\n--- paired daily difference {rule} minus each reference, same flips (pp/yr, NW t; Newey-West 1994 lag) ---")
    p(f"{'window':<11}" + "".join(f"{f'- {r} ({fl[:4]})':>22}" for r in refs for fl in FLIPS))
    out = {}
    for lab, a, b in W:
        cells = []
        for r in refs:
            for fl in FLIPS:
                d = (res[(rule, fl)]["pnl"] - res[(r, fl)]["pnl"]).loc[a:b]
                cells.append((float(d.mean() * P), nwt(d.to_numpy())))
                out[f"{r}/{fl}/{lab}"] = dict(pp=cells[-1][0], t=cells[-1][1])
        p(f"{lab:<11}" + "".join(f"{c[0] * 100:14.2f} ({c[1]:5.2f})" for c in cells))
    OUT[key] = out
    return out


def thin_only(res, thin, dist_end, rules):
    """Gross on thin-decision earning days and on active ones, ann% of the window."""
    W = td.windows(dist_end)
    p("\n--- gross P&L split by the decision behind each earning day: thin session (< min_names eligible) or active; "
      "ann% of the window [thin earning days] ---")
    p(f"{'window':<11}{'flips':<9}" + "".join(f"{r + ' thin':>12}{r + ' act':>11}" for r in rules))
    out = {}
    for fl in FLIPS:
        for lab, a, b in W:
            cells = []
            for r in rules:
                x = res[(r, fl)]["pnl"].loc[a:b]
                m = thin_days_of(thin, x.index)
                cells.append((float(x[m].sum() / len(x) * P), float(x[~m].sum() / len(x) * P), int(m.sum())))
                out[f"{r}/{fl}/{lab}"] = dict(thin=cells[-1][0], active=cells[-1][1], thin_days=cells[-1][2])
            p(f"{lab:<11}{fl:<9}" + "".join(f"{c[0] * 100:12.2f}{c[1] * 100:11.2f}" for c in cells)
              + f"   [{cells[0][2]}]")
    OUT["thin_only"] = out


def era_cv(rows, rules):
    labs = [("2023+" if lab == "2023-" else lab) for lab, _, _ in ERAS]
    p("\n--- era turnover sd/mean (H5), instant flips, over the eras in which the rule traded ---")
    out = {}
    for r in rules:
        t = np.array([rows[(r, "instant", e)]["turn"] for e in labs])
        tr = t[t > 0]
        out[r] = dict(eras=[float(x) for x in t], cv=float(tr.std(ddof=1) / tr.mean()), n_eras=int(len(tr)))
        p(f"{r:<8} turn/yr by era {' / '.join(f'{x:.1f}' for x in t)}  sd/mean {out[r]['cv']:.2f} over {len(tr)} eras")
    OUT.setdefault("era_turnover_cv", {}).update(out)


def _bisect_band(build, target, lo=0.002, hi=0.40):
    """The band width at which build(bw)'s FIT turnover equals `target`, by bisection on turnover only (never on
    P&L); turnover falls as the band widens. Raises if `target` lies outside the bracket."""
    tlo, thi = build(lo)[0], build(hi)[0]
    if not (thi <= target <= tlo):
        raise ValueError(f"fit turnover {target:.2f} outside [{thi:.2f}, {tlo:.2f}] for bands [{lo}, {hi}]")
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        if build(mid)[0] > target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def gap_read(x_res, y_res, hurdle, a, b):
    """x minus y over [a, b]: pp/yr, NW t, the extra turnover, the gap after the cost grid, and at each N the bar,
    whether the t clears it, and read_result (Sidak at N; `meaningful` = `hurdle`, the cost hurdle)."""
    from scripts.research.inference import read_result, upper_bound_max_z
    d = (x_res["pnl"] - y_res["pnl"]).loc[a:b]
    est, t = float(d.mean() * P), nwt(d.to_numpy())
    dturn = float((x_res["turn_series"] - y_res["turn_series"]).loc[a:b].mean() * P)
    o = dict(pp=est, t=t, extra_turn=dturn, net={c: est - dturn * c / 1e4 for c in COSTS}, hurdle=hurdle, reads={})
    for N in NS:
        bar = float(upper_bound_max_z(N))
        rr = read_result(est, abs(est / t), hurdle, n_trials=N)
        o["reads"][N] = dict(bar=bar, clears=bool(t > bar), read=rr["outcome"], lo=rr["lo"], hi=rr["hi"],
                             vs=rr["vs_meaningful"])
    return o


def fmt_read(o, N=53):
    r = o["reads"][N]
    return (f"{o['pp'] * 100:+.2f}pp/yr (NW t {o['t']:.2f}; bar {r['bar']:.3f} at N={N}: "
            f"{'clears' if r['clears'] else 'does not clear'}; read_result {r['read']} [{r['lo'] * 100:+.2f}, "
            f"{r['hi'] * 100:+.2f}], hurdle {o['hurdle'] * 100:.2f} {r['vs']}); extra turn {o['extra_turn']:+.2f}/yr; "
            "net @5/@15/@30 " + "/".join(f"{o['net'][c] * 100:+.2f}" for c in COSTS))


def matched(T, thin, TF, BF, keep, Rt, rows, res, hurdle):
    """H2: the comparison at matched FIT turnover, in both directions, by bisection on turnover only (never on
    P&L). The band widths are matching devices, not proposals.
      (i)  HEADLINE (declared before the smoke run): te4 (instant) re-banded so that its FIT turnover equals each
           reference's;
      (ii) SENSITIVITY (declared after the review, before it ran): each reference re-banded so that its FIT
           turnover equals te4's at the spec band.
    The first version printed only ann% and SR at the match; the paired gap, its t, the bar and read_result are
    the review's finding 1 (H2 allows turnover-matched comparisons only)."""
    fit = Rt.index < HOLDOUT_START
    WM = (("FIT <2023", pd.Timestamp(bf.SAMPLE_START), HOLDOUT_START - pd.Timedelta(days=1)),
          ("H13 2023+", HOLDOUT_START, Rt.index[-1]))

    def ev(h):
        r = bf.evaluate(h.loc[keep], Rt)
        return float(r["turn_series"][fit].mean() * P), r

    build = {"te4": lambda bw: ev(bf.band_gross_capped(TF[FLOOR], bw, MAX_GROSS_STRESS, below_min_names="trade_eligible",
                                                       thin=BF[FLOOR], floor=FLOOR)),
             "flatten": lambda bw: ev(bf.band_gross_capped(T, bw, MAX_GROSS_STRESS, below_min_names="flatten",
                                                           thin=thin)),
             "hold": lambda bw: ev(bf.band_gross_capped(T, bw, MAX_GROSS_STRESS))}
    out = {}
    te_turn = rows[(te(FLOOR), "instant", "FIT <2023")]["turn"]
    for ref in ("flatten", "hold"):
        target = rows[(ref, "instant", "FIT <2023")]["turn"]
        gap = te_turn / target - 1
        bw = _bisect_band(build["te4"], target)
        t_, r = build["te4"](bw)
        o = dict(ref_turn=target, te_turn_at_spec_band=te_turn, gap_at_spec_band=gap, band=bw, matched_turn=t_)
        p(f"\n=== H2 (i) HEADLINE: te{FLOOR} (instant) FIT turnover {te_turn:.2f}/yr vs {ref} {target:.2f}/yr at the "
          f"spec band ({gap * 100:+.1f}%); re-banded to {bw:.4f} it turns {t_:.2f}/yr ({(t_ / target - 1) * 100:+.2f}%) ===")
        for lab, a, b in WM:
            s = td.stats(r["pnl"].loc[a:b], r["turn_series"].loc[a:b])
            ref_s = rows[(ref, "instant", lab)]
            o[lab] = dict(te=s, ref=ref_s, gap=gap_read(r, res[(ref, "instant")], hurdle[ref], a, b))
            p(f"{lab:<10} te{FLOOR}@{bw:.4f}: SR {s['sr']:.2f} ann {s['ann'] * 100:.2f}% turn {s['turn']:.1f} net "
              + "/".join(f"{s['net'][c] * 100:.2f}" for c in COSTS) + f" BE {s['be']:.1f}bp | {ref}: SR "
              f"{ref_s['sr']:.2f} ann {ref_s['ann'] * 100:.2f}% turn {ref_s['turn']:.1f} net "
              + "/".join(f"{ref_s['net'][c] * 100:.2f}" for c in COSTS))
            p(f"{'':<10} te{FLOOR}@{bw:.4f} minus {ref}: " + fmt_read(o[lab]["gap"]))
        # (ii) needs the reference to reach te4's turnover; a band of 0 (trade to the target every session) is the
        # most a reference can turn over. If even that falls short, the direction is infeasible, and is reported
        # as such with the shortfall (not skipped)
        t0 = build[ref](0.0)[0]
        if t0 < te_turn:
            o["reverse"] = dict(feasible=False, target=te_turn, max_turn_at_band_0=t0)
            p(f"--- H2 (ii) sensitivity INFEASIBLE: {ref} turns at most {t0:.2f}/yr over FIT (band 0, trading to the "
              f"target every session), {(t0 / te_turn - 1) * 100:+.1f}% vs te{FLOOR}'s {te_turn:.2f}/yr; outside H2's "
              f"5% ---" if t0 < 0.95 * te_turn else
              f"--- H2 (ii) sensitivity: {ref} at band 0 turns {t0:.2f}/yr, within 5% of te{FLOOR}'s {te_turn:.2f} ---")
            if t0 < 0.95 * te_turn:
                out[ref] = o
                continue
            bw2 = 0.0
        else:
            bw2 = _bisect_band(build[ref], te_turn, lo=0.0)
        t2, r2 = build[ref](bw2)
        rv = dict(feasible=True, band=bw2, matched_turn=t2, target=te_turn)
        p(f"--- H2 (ii) sensitivity: {ref} re-banded to {bw2:.4f} turns {t2:.2f}/yr over FIT "
          f"({(t2 / te_turn - 1) * 100:+.2f}% vs te{FLOOR} at the spec band) ---")
        for lab, a, b in WM:
            s = td.stats(r2["pnl"].loc[a:b], r2["turn_series"].loc[a:b])
            rv[lab] = dict(ref=s, gap=gap_read(res[("te4", "instant")], r2, hurdle[ref], a, b))
            p(f"{lab:<10} {ref}@{bw2:.4f}: SR {s['sr']:.2f} ann {s['ann'] * 100:.2f}% turn {s['turn']:.1f}; te{FLOOR} "
              f"(spec band) minus it: " + fmt_read(rv[lab]["gap"]))
        o["reverse"] = rv
        out[ref] = o
    OUT["matched"] = out


def plateau(res, dist_end):
    """H8: floors 3, 4, 5 against flatten and hold on the FIT period (H13 printed, not read)."""
    W = [w for w in td.windows(dist_end) if w[0] in ("2005-09", "2010-14", "2015-19", "2020-22", "FIT <2023",
                                                       "H13 2023+")]
    p("\n=== H8 plateau: te3 / te4 / te5 minus flatten and minus hold, instant flips (pp/yr, NW t) ===")
    p("(read on FIT and its eras; the H13 row is printed and not used)")
    out = {}
    for lab, a, b in W:
        cells = []
        for f in PLATEAU:
            for ref in ("flatten", "hold"):
                d = (res[(te(f), "instant")]["pnl"] - res[(ref, "instant")]["pnl"]).loc[a:b]
                cells.append((float(d.mean() * P), nwt(d.to_numpy()) if (d != 0).any() else float("nan")))
                out[f"te{f}-{ref}/{lab}"] = dict(pp=cells[-1][0], t=cells[-1][1])
        p(f"{lab:<11}" + "".join(f"  te{f}-{ref[:4]} {c[0] * 100:+6.2f} ({c[1]:+5.2f})"
                                 for (f, ref), c in zip([(f, r) for f in PLATEAU for r in ("flatten", "hold")], cells)))
    OUT["plateau"] = out


def plateau_per_session(res, thin, cnt, dist_end):
    """The same gaps per traded thin session: if the per-session edge is flat across floors, the floor sets how
    MANY sessions are traded, not what each earns."""
    fit = (pd.Timestamp(bf.SAMPLE_START), HOLDOUT_START - pd.Timedelta(days=1))
    p("\n--- H8 plateau per traded session (FIT): gap pp/yr / share of FIT sessions the floor trades and the spec "
      "does not ---")
    out = {}
    for f in PLATEAU:
        share = float((thin & (cnt >= f)).loc[fit[0]:fit[1]].mean())
        cells = {}
        for ref in ("flatten", "hold"):
            g = float((res[(te(f), "instant")]["pnl"] - res[(ref, "instant")]["pnl"]).loc[fit[0]:fit[1]].mean() * P)
            cells[ref] = dict(gap=g, per_share=g / share)
        out[f] = dict(share=share, **cells)
        p(f"te{f}: share {share * 100:.1f}%; per unit share vs flatten {cells['flatten']['per_share'] * 100:+.2f}pp/yr, "
          f"vs hold {cells['hold']['per_share'] * 100:+.2f}pp/yr")
    OUT["plateau_per_session"] = out


# --------------------------------------------------------------------------- attacks on te4's gap
def attack(H, T, thin, cnt, panel, keep, Rt, res, dist_end, hurdle):
    """Declared before reading any te4 result beyond the smoke run's scoreboard: where te4's thin-day P&L sits,
    whether it is stale prices, distributions or beta, the stretches as the unit, the best days, the bar."""
    from itertools import product as _prod
    from scripts.research.inference import p_clear_bar, read_result, upper_bound_max_z
    W = [w for w in td.windows(dist_end) if w[0] in ("2010-14", "2015-19", "2020-22", "FIT <2023", "H13 2023+")]
    out = {}
    H4 = H[("te4", "instant")]
    held = H4.loc[keep].shift(2).fillna(0.0)                       # H1: decided t earns t+2
    C = held * Rt
    if not np.allclose(C.sum(axis=1).to_numpy(), res[("te4", "instant")]["pnl"].to_numpy(), atol=1e-15):
        raise AssertionError("te4's name-day attribution does not sum to evaluate()'s P&L")
    z, adv = panel["z"].reindex(T.index)[UNIVERSE], panel["adv"].reindex(T.index)[UNIVERSE]
    elig = (z.notna() & (adv >= MIN_ADV_USD))
    elig_d = elig.shift(2).reindex(Rt.index)
    elig_d = elig_d.where(elig_d.notna(), False).astype(bool)      # eligibility AT THE DECISION behind the day
    thin_d = thin_days_of(thin, Rt.index)
    isheld = held != 0

    p("\n=== ATTACK a: te4's thin-day P&L by whether the held name was eligible at the decision (the band leaves "
      "an ineligible name at its band edge, as the live sleeve does) ===")
    p(f"{'window':<11}{'thin ann%':>10}{'eligible':>10}{'residue':>10}{'resid gross':>12}{'elig gross':>11}  [held name-days elig / resid]")
    for lab, a, b in W:
        m = thin_d.loc[a:b]
        n = len(C.loc[a:b])
        cc, ee, hh = C.loc[a:b][m], elig_d.loc[a:b][m], held.loc[a:b][m]
        o = dict(thin=float(cc.sum().sum() / n * P), elig=float(cc.where(ee, 0.0).sum().sum() / n * P),
                 resid=float(cc.where(~ee, 0.0).sum().sum() / n * P),
                 resid_gross=float(hh.where(~ee, 0.0).abs().sum(axis=1).mean()) if m.any() else float("nan"),
                 elig_gross=float(hh.where(ee, 0.0).abs().sum(axis=1).mean()) if m.any() else float("nan"),
                 nd_elig=int(((hh != 0) & ee).sum().sum()), nd_resid=int(((hh != 0) & ~ee).sum().sum()))
        out.setdefault("a_split", {})[lab] = o
        p(f"{lab:<11}{o['thin'] * 100:10.2f}{o['elig'] * 100:10.2f}{o['resid'] * 100:10.2f}{o['resid_gross']:12.3f}"
          f"{o['elig_gross']:11.3f}  [{o['nd_elig']} / {o['nd_resid']}]")
    cnt_d = cnt.shift(2).reindex(Rt.index)
    pn4 = res[("te4", "instant")]["pnl"]
    p("--- te4's thin-day P&L by the eligible count at the decision: ann% of the window, and per earning day x 252 "
      "(the floor's own count, 4, against 5) [earning days] ---")
    for lab, a, b in W:
        x, cd, m = pn4.loc[a:b], cnt_d.loc[a:b], thin_d.loc[a:b]
        cells = {}
        for k in (4, 5):
            sel = m & (cd == k)
            cells[k] = dict(days=int(sel.sum()), ann=float(x[sel].sum() / len(x) * P),
                            per_day=float(x[sel].mean() * P) if sel.any() else float("nan"),
                            t=nwt(x[sel].to_numpy()) if sel.sum() > 30 else float("nan"))
        out.setdefault("a_by_count", {})[lab] = cells
        p(f"{lab:<11}" + "  ".join(f"n={k}: {c['ann'] * 100:+.2f} ({c['per_day'] * 100:+.2f}/day-yr, t {c['t']:.2f}) "
                                   f"[{c['days']}]" for k, c in cells.items()))

    p("\n--- ATTACK b: stale-price signature on te4's held name-days: share with a total return of exactly 0, "
      "and with zero volume ---")
    zero = Rt[UNIVERSE] == 0
    v0 = panel["vol"].reindex(Rt.index)[UNIVERSE] == 0
    for lab, a, b in W:
        cells = {}
        for (nm, mk), (en, em) in _prod((("thin", thin_d.loc[a:b]), ("active", ~thin_d.loc[a:b])),
                                         (("elig", elig_d.loc[a:b]), ("resid", ~elig_d.loc[a:b]))):
            sel = isheld.loc[a:b][mk] & em[mk]
            nd = int(sel.sum().sum())
            cells[f"{nm}/{en}"] = dict(n=nd, zero=float((zero.loc[a:b][mk] & sel).sum().sum() / nd) if nd else float("nan"),
                                       vol0=float((v0.loc[a:b][mk] & sel).sum().sum() / nd) if nd else float("nan"))
        out.setdefault("b_stale", {})[lab] = cells
        p(f"{lab:<11}" + "  ".join(f"{k} {v['zero'] * 100:5.2f}% zero, {v['vol0'] * 100:4.2f}% vol0 [{v['n']}]"
                                   for k, v in cells.items()))

    y = bf.distribution_yield(Rt.index, Rt.columns).reindex_like(Rt)[UNIVERSE]
    Cd = held[UNIVERSE] * y
    ret_raw = panel["ret"].reindex(Rt.index)[UNIVERSE]
    ew = Rt[UNIVERSE].where(ret_raw.notna()).mean(axis=1)
    p("\n--- ATTACK c: te4's thin-day P&L, price leg and distribution leg, and its beta to the equal-weight universe "
      "total return on the same days ---")
    p(f"{'window':<11}{'thin ann%':>10}{'price':>8}{'dist':>8}{'beta':>8}{'alpha part':>11}{'NW t':>7}")
    for lab, a, b in W:
        m = thin_d.loc[a:b]
        n = len(C.loc[a:b])
        tot = float(C.loc[a:b][m].sum().sum() / n * P)
        dst = float(Cd.loc[a:b][m].sum().sum() / n * P)
        yv, xv = res[("te4", "instant")]["pnl"].loc[a:b][m], ew.loc[a:b][m]
        ok = xv.notna()
        yv, xv = yv[ok], xv[ok]
        if len(yv) > 30 and xv.var() > 0:
            beta = float(np.cov(yv, xv, ddof=1)[0, 1] / xv.var(ddof=1))
            resid = yv - beta * xv
            apart, ta = float(resid.sum() / n * P), nwt(resid.to_numpy())
        else:
            beta = apart = ta = float("nan")
        out.setdefault("c_legs_beta", {})[lab] = dict(thin=tot, price=tot - dst, dist=dst, beta=beta, alpha=apart, t=ta)
        p(f"{lab:<11}{tot * 100:10.2f}{(tot - dst) * 100:8.2f}{dst * 100:8.2f}{beta:8.3f}{apart * 100:11.2f}{ta:7.2f}")

    fit = (pd.Timestamp(bf.SAMPLE_START), HOLDOUT_START - pd.Timedelta(days=1))
    for ref in ("flatten", "hold"):
        d = (res[("te4", "instant")]["pnl"] - res[(ref, "instant")]["pnl"])
        x = d.loc[fit[0]:fit[1]]
        # stretches as the unit: each FIT run of thin sessions with a te4 book, the gap over its earning days
        idx = T.index
        runs = []
        for i0, i1 in ak.runs_of(thin & (cnt >= FLOOR)):
            if idx[i0] >= HOLDOUT_START:
                continue
            earn = idx[i0 + 2: i1 + 3]
            earn = earn[earn.isin(x.index)]
            if len(earn):
                runs.append((str(idx[i0].date()), str(idx[i1].date()), i1 - i0 + 1, float(x.loc[earn].sum())))
        v = np.array([r[3] for r in runs])
        nr = len(v)
        t_runs = float(v.mean() / v.std(ddof=1) * np.sqrt(nr))
        rng = np.random.default_rng(SEED)
        if nr <= 24:
            signs = ((np.arange(2 ** nr)[:, None] >> np.arange(nr)[None, :]) & 1).astype(np.int8) * 2 - 1
            p_flip, how = float(((signs @ v) >= v.sum() - 1e-15).mean()), "exact"
        else:
            signs = rng.choice([-1, 1], size=(200_000, nr))
            p_flip, how = float(((signs @ v) >= v.sum() - 1e-15).mean()), "200,000 sampled"
        srt = np.sort(v)[::-1]
        s = x.sort_values(ascending=False)
        o = dict(runs=nr, t_runs=t_runs, positive=int((v > 0).sum()), p_signflip=p_flip, p_how=how,
                 sum_pp=float(v.sum()), largest=float(srt[0]), largest_share=float(srt[0] / v.sum()),
                 largest_run=[r for r in runs if r[3] == srt[0]][0][:3],
                 t_without_best10=nwt(x.drop(s.head(10).index).to_numpy()),
                 best10_pp=float(s.head(10).sum()), total_pp=float(x.sum()),
                 table=[dict(first=r[0], last=r[1], sessions=r[2], pp=r[3]) for r in runs])
        p(f"\n=== ATTACK d-f: te4 minus {ref}, FIT, instant flips ===")
        p(f"d. stretches as the unit (the gap summed over each FIT thin stretch's earning days; {nr} stretches with a "
          f"te4 book): run t {t_runs:.2f}; positive {o['positive']}/{nr}; sign-flip p (one-sided, {how}) {p_flip:.4f}; "
          f"largest {srt[0] * 100:.2f}pp ({o['largest_share'] * 100:.0f}% of {v.sum() * 100:.2f}pp; "
          f"{o['largest_run'][0]}..{o['largest_run'][1]}). The rest of the gap ({(x.sum() - v.sum()) * 100:.2f}pp) "
          "is earned on active days after re-entry")
        p(f"e. the best 10 days sum to {o['best10_pp'] * 100:.2f}pp of {o['total_pp'] * 100:.2f}pp; without them NW t "
          f"{o['t_without_best10']:.2f}")
        est, t_day = float(x.mean() * P), nwt(x.to_numpy())
        o["bars"] = {}
        # meaningful = the cost hurdle (te4's extra FIT turnover at the spec band x 15bp), as read_result's
        # docstring asks; the first version passed the observed estimate, which made ABSENT unreachable
        for N in NS:
            bar = float(upper_bound_max_z(N))
            rr = read_result(est, abs(est / t_day), hurdle[ref], n_trials=N)
            o["bars"][N] = dict(bar=bar, p_clear_paired=float(p_clear_bar(t_day, bar)),
                                p_clear_runs=float(p_clear_bar(t_runs, bar)),
                                read=rr["outcome"], lo=rr["lo"], hi=rr["hi"], vs=rr["vs_meaningful"],
                                hurdle=hurdle[ref])
            b = o["bars"][N]
            p(f"f. N={N}: bar {bar:.3f}; paired t {t_day:.2f}, run t {t_runs:.2f}; P(clear | true t = observed) "
              f"{b['p_clear_paired']:.2f} / {b['p_clear_runs']:.2f}; read_result (Sidak at N, meaningful = the cost "
              f"hurdle {hurdle[ref] * 100:.2f}pp/yr) {b['read']} [{b['lo'] * 100:.2f}, {b['hi'] * 100:.2f}], "
              f"vs hurdle {b['vs']}")
        out[f"d_f_vs_{ref}"] = o
    OUT["attack"] = out


def degenerate_replay(T, thin, TF, BF, keep, Rt, dist_end):
    """PR #33 section 5.H: on 2020-03-18 and 2025-04-07 every eligible z sat at the -4 clip; the harness cuts the
    book to the band edge, the live sleeve holds every name. Replay each rule with the sleeve's behaviour (a zero
    gap on those dates) and report what moves."""
    W = [w for w in td.windows(dist_end) if w[0] in ("2020-22", "FIT <2023", "H13 2023+")]
    nz = T.abs().sum(axis=1) > 0
    deg = T.index[~thin & ~nz & (nz.cumsum() > 0)]
    p(f"\n=== the degenerate sessions {[str(d.date()) for d in deg]} replayed with the sleeve's hold (PR #33 5.H) ===")
    out = {}
    pn = {}
    for rule, fl in [(r, f) for r in MAIN for f in FLIPS]:
        if rule == "hold":
            TT, kw = T, {}
        elif rule == "flatten":
            TT, kw = T, dict(below_min_names="flatten", thin=thin)
        else:
            TT, kw = TF[FLOOR], dict(below_min_names="trade_eligible", thin=BF[FLOOR], floor=FLOOR)
        kw["defer_flips"] = fl == "deferred"
        h0 = bf.band_gross_capped(TT, BAND_WIDTH, MAX_GROSS_STRESS, **kw)
        T2, h = TT.copy(), h0
        for dt in deg:
            i = TT.index.get_loc(dt)
            if (TT.iloc[i] != 0).any():
                raise AssertionError(f"{rule}: {dt.date()} is not a zero row of its targets")
            T2.iloc[i] = h.iloc[i - 1].to_numpy()          # a zero gap: the band holds every name
            h = bf.band_gross_capped(T2, BAND_WIDTH, MAX_GROSS_STRESS, **kw)
            if not np.array_equal(h.iloc[i].to_numpy(), h.iloc[i - 1].to_numpy()):
                raise AssertionError(f"the replay did not hold {rule} on {dt.date()}")
        r0, r1 = bf.evaluate(h0.loc[keep], Rt)["pnl"], bf.evaluate(h.loc[keep], Rt)["pnl"]
        pn[(rule, fl)] = r1
        out[f"{rule}/{fl}"] = {lab: dict(harness=float(r0.loc[a:b].mean() * P), sleeve=float(r1.loc[a:b].mean() * P))
                               for lab, a, b in W}
        p(f"{rule:<8}{fl:<9} ann% harness -> sleeve: " + "  ".join(
            f"{lab} {out[f'{rule}/{fl}'][lab]['harness'] * 100:.2f}->{out[f'{rule}/{fl}'][lab]['sleeve'] * 100:.2f}"
            for lab, _, _ in W))
    for ref in ("flatten", "hold"):
        for fl in FLIPS:
            dd = pn[("te4", fl)] - pn[(ref, fl)]
            out[f"te4-{ref}/{fl}"] = {lab: dict(pp=float(dd.loc[a:b].mean() * P), t=nwt(dd.loc[a:b].to_numpy()))
                                      for lab, a, b in W}
            p(f"te4 minus {ref} ({fl}) under the replay: " + "  ".join(
                f"{lab} {out[f'te4-{ref}/{fl}'][lab]['pp'] * 100:+.2f} ({out[f'te4-{ref}/{fl}'][lab]['t']:+.2f})"
                for lab, _, _ in W))
    OUT["degenerate_replay"] = dict(dates=[str(d.date()) for d in deg], **out)


# --------------------------------------------------------------------------- step 4
def concentration(H, T, thin, TF, cnt, dist_end):
    W = [w for w in td.windows(dist_end) if w[0] not in ("full",)]
    p("\n=== STEP 4: concentration on thin sessions (the book as decided; instant flips) ===")
    out = {}
    for rule in ("te4", "hold"):
        Hh = H[(rule, "instant")]
        n = (Hh.abs() > 0).sum(axis=1)
        mx = Hh.abs().max(axis=1)
        g = Hh.abs().sum(axis=1)
        p(f"{rule}: on thin sessions with a book held: names held / max single-name |w| / gross "
          "(mean, median, p90, max) [sessions]; active sessions for reference")
        for lab, a, b in W:
            for nm, msk in (("thin", thin.loc[a:b]), ("active", ~thin.loc[a:b])):
                held = msk & (g.loc[a:b] > 0)
                if not held.any():
                    continue
                q = lambda s: dict(mean=float(s.mean()), median=float(s.median()),            # noqa: E731
                                   p90=float(s.quantile(0.9)), max=float(s.max()))
                o = dict(sessions=int(held.sum()), names=q(n.loc[a:b][held]), maxw=q(mx.loc[a:b][held]),
                         gross=q(g.loc[a:b][held]))
                out[f"{rule}/{nm}/{lab}"] = o
                p(f"  {lab:<10}{nm:<7} names {o['names']['mean']:.2f}/{o['names']['median']:.0f}/"
                  f"{o['names']['p90']:.0f}/{o['names']['max']:.0f}  max|w| {o['maxw']['mean']:.3f}/"
                  f"{o['maxw']['median']:.3f}/{o['maxw']['p90']:.3f}/{o['maxw']['max']:.3f}  gross "
                  f"{o['gross']['mean']:.3f}/{o['gross']['median']:.3f}/{o['gross']['p90']:.3f}/{o['gross']['max']:.3f}"
                  f" [{o['sessions']}]")
    # the target itself on the sessions te4 trades and the spec does not
    T4 = TF[FLOOR]
    m = (thin & (cnt >= FLOOR)).to_numpy()
    tg = T4[m]
    side_min = np.minimum((tg > 0).sum(axis=1), (tg < 0).sum(axis=1))
    cn = cnt[m].to_numpy()
    out["target_reduced"] = dict(sessions=int(m.sum()),
                                 by_n={int(k): int(v) for k, v in cnt[m].value_counts().sort_index().items()},
                                 single_name_side_share=float((side_min == 1).mean()),
                                 single_name_side_share_by_n={int(k): float((side_min[cn == k] == 1).mean())
                                                              for k in sorted(set(cn))},
                                 maxw_median=float(tg.abs().max(axis=1).median()),
                                 maxw_p90=float(tg.abs().max(axis=1).quantile(0.9)),
                                 gross_median=float(tg.abs().sum(axis=1).median()),
                                 degenerate_zero_rows=int((tg.abs().sum(axis=1) == 0).sum()))
    o = out["target_reduced"]
    p(f"te{FLOOR} TARGET on the {o['sessions']} thin sessions it trades (eligible count: {o['by_n']}): one side is a "
      f"single fund on {o['single_name_side_share'] * 100:.1f}% (by count: "
      + ", ".join(f"n={k} {v * 100:.1f}%" for k, v in o["single_name_side_share_by_n"].items())
      + f"); max |w| median {o['maxw_median']:.3f}, p90 "
      f"{o['maxw_p90']:.3f}; gross median {o['gross_median']:.3f}; all-equal-z (0/0) rows {o['degenerate_zero_rows']}")
    OUT["concentration"] = out


def leave_out(H, keep, Rt, dist_end, ref):
    """te4 minus ref with one name's own P&L taken out (attribution), PHK and PTY first. Added after the
    beta-detector pass (2026-11-03): PHK and PTY were PR #33's two largest contributors to HOLD's thin-day P&L;
    te4's own two largest against flatten are PHK and PDI, so PHK+PDI and PHK+PDI+PTY are printed too."""
    W = [w for w in td.windows(dist_end) if w[0] in ("2010-14", "2015-19", "2020-22", "FIT <2023", "H13 2023+")]
    A, B = H[("te4", "instant")], H[(ref, "instant")]
    Dn = (A.loc[keep].shift(2).fillna(0.0) - B.loc[keep].shift(2).fillna(0.0)) * Rt   # H1; first 2 rows hold nothing
    d = Dn.sum(axis=1)
    chk = bf.evaluate(A.loc[keep], Rt)["pnl"] - bf.evaluate(B.loc[keep], Rt)["pnl"]
    if not np.allclose(d.to_numpy(), chk.to_numpy(), atol=1e-14):
        raise AssertionError("the name attribution does not sum to the paired gap")
    order = ["PHK", "PTY"] + [t for t in UNIVERSE if t not in ("PHK", "PTY")]
    p(f"\n=== STEP 4: te4 minus {ref} with each name's own P&L taken out (attribution; instant flips; pp/yr, NW t) ===")
    p(f"{'left out':<10}" + "".join(f"{lab:>18}" for lab, _, _ in W))
    out = {}
    for drop in [[]] + [[t] for t in order] + [["PHK", "PTY"], ["PHK", "PDI"], ["PHK", "PDI", "PTY"]]:
        cells = []
        for lab, a, b in W:
            X = Dn.loc[a:b]
            x = X.sum(axis=1) - (X[drop].sum(axis=1) if drop else 0.0)
            cells.append((float(x.mean() * P), nwt(x.to_numpy())))
        k = "+".join(drop) if drop else "none"
        out[k] = {lab: dict(pp=c[0], t=c[1]) for (lab, _, _), c in zip(W, cells)}
        p(f"{k:<10}" + "".join(f"{c[0] * 100:10.2f} ({c[1]:5.2f})" for c in cells))
    contrib = {lab: {t: float(Dn.loc[a:b][t].sum() / len(Dn.loc[a:b]) * P) for t in UNIVERSE} for lab, a, b in W}
    fitc = sorted(contrib["FIT <2023"].items(), key=lambda kv: -abs(kv[1]))[:5]
    p("largest FIT contributors by |pp/yr|: " + ", ".join(f"{t} {v * 100:+.2f}" for t, v in fitc))
    OUT[f"leave_out_vs_{ref}"] = out
    OUT[f"contrib_vs_{ref}"] = contrib


def rebuilt(dist_end):
    W = [w for w in td.windows(dist_end) if w[0] in ("2010-14", "2015-19", "2020-22", "FIT <2023", "H13 2023+")]
    p("\n=== STEP 4: books REBUILT on the universe without the name(s) (targets, masks and books recomputed; "
      "a smaller universe is thin more often, so this is a different book) ===")
    out = {}
    # PDI and PHK+PDI added after the beta-detector pass (te4's own two largest contributors vs flatten)
    for drop in (["PHK"], ["PTY"], ["PHK", "PTY"], ["PDI"], ["PHK", "PDI"]):
        U = [u for u in UNIVERSE if u not in drop]
        T, R = bf.build_targets(universe=U)
        thin = bf.thin_sessions(T.index, universe=U)
        T4, _ = bf.build_targets(universe=U, min_names=FLOOR)
        B4 = bf.thin_sessions(T.index, universe=U, min_names=FLOOR)
        keep = T.index <= dist_end
        Rt = bf.total_returns(R.loc[keep])
        pnl = {"hold": bf.evaluate(bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS).loc[keep], Rt)["pnl"],
               "flatten": bf.evaluate(bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS, below_min_names="flatten",
                                                           thin=thin).loc[keep], Rt)["pnl"],
               "te4": bf.evaluate(bf.band_gross_capped(T4, BAND_WIDTH, MAX_GROSS_STRESS,
                                                       below_min_names="trade_eligible", thin=B4,
                                                       floor=FLOOR).loc[keep], Rt)["pnl"]}
        k = "+".join(drop)
        row = dict(thin=int(thin.sum()), below_floor=int(B4.sum()))
        for lab, a, b in W:
            row[lab] = {f"te4-{r}": dict(pp=float((pnl["te4"] - pnl[r]).loc[a:b].mean() * P),
                                         t=nwt((pnl["te4"] - pnl[r]).loc[a:b].to_numpy()))
                        for r in ("flatten", "hold")}
            row[lab].update({r: float(pnl[r].loc[a:b].mean() * P) for r in pnl})
        out[k] = row
        p(f"without {k:<8} thin {row['thin']}, below floor {row['below_floor']}: " + "  ".join(
            f"{lab} te4-flat {row[lab]['te4-flatten']['pp'] * 100:+.2f} ({row[lab]['te4-flatten']['t']:+.2f}), "
            f"te4-hold {row[lab]['te4-hold']['pp'] * 100:+.2f} ({row[lab]['te4-hold']['t']:+.2f})"
            for lab, _, _ in W))
    OUT["rebuilt"] = out


def borrow(H, keep, Rt, dist_end, res):
    """Borrow on the shorts each book holds, charged nowhere else. Every charge goes through `bf.borrow_charge`,
    the harness's one definition: the shift(2) held book, the fee in force at t-1, 102% collateral, actual/360 per
    calendar day. (The first version charged a simple annual rate on short weight with the fee at t, a second
    copy of the convention: the review's finding 4.) Returns the as-of fee frame for `forward`."""
    p("\n=== STEP 4: borrow on the shorts (bf.borrow_charge; charged nowhere else) ===")
    Hk = {r: H[(r, "instant")].loc[keep] for r in MAIN}
    W = [w for w in td.windows(dist_end) if w[0] in ("2010-14", "2015-19", "2020-22", "FIT <2023", "H13 2023+")]
    out = dict(breakeven={}, extra_by_name={}, measured={}, backcast={})
    # break-even: the canonical charge at a constant 1%/yr on every name; the fee that erases the gap is
    # gap / (extra charge per 1%)
    one = pd.DataFrame(1.0, index=Rt.index, columns=UNIVERSE)
    c1 = {r: bf.borrow_charge(Hk[r], one) for r in MAIN}
    for ref in ("flatten", "hold"):
        for lab, a, b in W:
            gap = float((res[("te4", "instant")]["pnl"] - res[(ref, "instant")]["pnl"]).loc[a:b].mean() * P)
            ex = float((c1["te4"]["short"] - c1[ref]["short"]).loc[a:b].mean())
            per1 = float((c1["te4"]["cost"] - c1[ref]["cost"]).loc[a:b].mean() * P)      # extra charge at 1%/yr
            fee = gap / per1 if per1 > 0 else float("nan")                                # in %/yr
            out["breakeven"][f"{ref}/{lab}"] = dict(gap=gap, extra_short=ex, extra_charge_per_1pct=per1, fee_pct=fee)
            p(f"te4 - {ref} {lab}: gap {gap * 100:+.2f}pp/yr; mean extra short weight {ex:+.3f}; uniform fee that "
              f"erases the gap {fee:.1f}%/yr" if per1 > 0 else
              f"te4 - {ref} {lab}: gap {gap * 100:+.2f}pp/yr; mean extra short weight {ex:+.3f} (no extra borrow "
              "charge: no break-even fee)")
        sh = {r: (-Hk[r].shift(2).fillna(0.0)).clip(lower=0.0) for r in ("te4", ref)}   # the held short, by name
        bn = (sh["te4"] - sh[ref]).loc[: HOLDOUT_START - pd.Timedelta(days=1)].mean()
        out["extra_by_name"][ref] = {t: float(v) for t, v in bn.items() if abs(v) > 0.005}
        p(f"FIT mean extra short weight by name vs {ref}: "
          + ", ".join(f"{t} {v:+.3f}" for t, v in bn.sort_values().items() if abs(v) > 0.005))
    bh = pd.read_parquet(bf.DATA_DIR / "cef_borrow_history.parquet")
    bh["date"] = pd.to_datetime(bh["date"])
    fee = bh.pivot_table(index="date", columns="ticker", values="fee_rate_pct")
    missing = [t for t in UNIVERSE if t not in fee.columns]
    if missing:
        raise AssertionError(f"the IBKR fee panel has no column for {missing}")
    fee = fee[UNIVERSE]
    p(f"IBKR FEE_RATE panel {fee.index.min().date()}..{fee.index.max().date()} (data/cef/cef_borrow_history.parquet; "
      "docs/REFERENCES.md: no independent source for its levels before 2026-09). Before "
      f"{fee.index.min().date()} borrow is UNMEASURED.")
    meas = Rt.index[(Rt.index >= fee.index.min()) & (Rt.index <= fee.index.max())]
    f_, n_stale = ak._asof_fee(fee, meas)                     # each name's fee at most 5 sessions old, else raises
    fee_full = pd.DataFrame(np.nan, index=Rt.index, columns=UNIVERSE)
    fee_full.loc[meas] = f_[UNIVERSE].to_numpy()
    BC = {r: bf.borrow_charge(Hk[r], fee_full) for r in MAIN}
    # the first measured row reads a fee at t-1 before the panel: start one session later
    for lab, a, b in ((f"{meas[1].date()}..2022-12-30", meas[1], pd.Timestamp("2022-12-30")),
                      ("2023-01-03..DIST_END", HOLDOUT_START, min(dist_end, fee.index.max()))):
        days = Rt.loc[a:b].index
        ch, cov = {}, {}
        for r in MAIN:
            ch[r] = float(BC[r]["cost"].loc[days].mean() * P)
            tot = float(BC[r]["short"].loc[days].sum())
            cov[r] = 1.0 - float(BC[r]["uncovered"].loc[days].sum()) / tot if tot > 0 else 1.0
            if cov[r] != 1.0:
                raise AssertionError(f"{r} {lab}: a short held on a name-day with no fee (covered {cov[r]:.4f})")
        gaps = {r: float((res[("te4", "instant")]["pnl"] - res[(r, "instant")]["pnl"]).loc[days].mean() * P)
                for r in ("flatten", "hold")}
        out["measured"][lab] = dict(borrow=ch, covered=cov, gap=gaps,
                                    net={r: gaps[r] - (ch["te4"] - ch[r]) for r in gaps}, days=len(days),
                                    stale_name_days=n_stale)
        m_ = out["measured"][lab]
        p(f"{lab} ({len(days)} days; every held short has a fee): borrow hold {ch['hold'] * 100:.2f}%, flatten "
          f"{ch['flatten'] * 100:.2f}%, te4 {ch['te4'] * 100:.2f}%/yr of NAV; te4 - flatten gap "
          f"{gaps['flatten'] * 100:+.2f} gross -> {m_['net']['flatten'] * 100:+.2f} net of the extra borrow; te4 - hold "
          f"{gaps['hold'] * 100:+.2f} -> {m_['net']['hold'] * 100:+.2f} (fee carried up to 5 sessions on {n_stale} "
          "name-days)")
    # BACK-CAST [U]: each name's median and p90 measured fee (the whole panel), constant, charged to the years
    # before the panel. Not a measurement: what the fees were before 2021-09-13 is unknown
    for q in ("median", "p90"):
        lvl = fee.median() if q == "median" else fee.quantile(0.9)
        fr = pd.DataFrame(np.tile(lvl.to_numpy(), (len(Rt.index), 1)), index=Rt.index, columns=UNIVERSE)
        cq = {r: bf.borrow_charge(Hk[r], fr)["cost"] for r in MAIN}
        for ref in ("flatten", "hold"):
            for lab, a, b in W:
                gap = float((res[("te4", "instant")]["pnl"] - res[(ref, "instant")]["pnl"]).loc[a:b].mean() * P)
                ex = float((cq["te4"] - cq[ref]).loc[a:b].mean() * P)
                out["backcast"][f"{q}/{ref}/{lab}"] = dict(gap=gap, extra_borrow=ex, net=gap - ex)
        p(f"BACK-CAST [U] at each name's {q} measured fee ("
          + ", ".join(f"{t} {v:.1f}" for t, v in lvl.items()) + "%/yr): te4 - flatten net "
          + "  ".join(f"{lab} {out['backcast'][f'{q}/flatten/{lab}']['net'] * 100:+.2f}" for lab, _, _ in W))
    OUT["borrow"] = out
    return fee_full


# --------------------------------------------------------------------------- H12 control
def direction_control(T, thin, TF, BF, cnt, keep, Rt, res, dist_end):
    """Reassign each traded thin session's target weights among that session's eligible names by a random
    order drawn once per thin stretch; everything else as te4. Declared before running (module docstring)."""
    T4, B4 = TF[FLOOR], BF[FLOOR]
    A = T4.values
    trade = (thin & (cnt >= FLOOR)).to_numpy()
    runs = ak.runs_of(pd.Series(trade, index=T4.index))
    below = B4.to_numpy()
    rng = np.random.default_rng(SEED)
    W = [w for w in td.windows(dist_end) if w[0] in ("2010-14", "2015-19", "2020-22", "FIT <2023", "H13 2023+")]
    thin_d = thin_days_of(thin, Rt.index)
    actual = {lab: float(res[("te4", "instant")]["pnl"].loc[a:b][thin_d.loc[a:b]].sum() / len(Rt.loc[a:b]) * P)
              for lab, a, b in W}
    draws = {lab: [] for lab, _, _ in W}
    for k in range(N_DRAWS):
        B = A.copy()
        for i0, i1 in runs:
            key = rng.random(A.shape[1])                    # one random order of the names per stretch
            for i in range(i0, i1 + 1):
                nz = np.flatnonzero(A[i] != 0)
                if len(nz) < 2:
                    continue
                by_w = nz[np.argsort(-A[i][nz], kind="stable")]       # names by weight, largest first
                by_key = nz[np.argsort(-key[nz], kind="stable")]      # the same names in the stretch's random order
                B[i, by_key] = A[i, by_w]
        for i in range(1, len(B)):                          # below-floor rows repeat the previous row, as build_targets does
            if below[i]:
                B[i] = B[i - 1]
        Tb = pd.DataFrame(B, index=T4.index, columns=T4.columns)
        h = bf.band_gross_capped(Tb, BAND_WIDTH, MAX_GROSS_STRESS, below_min_names="trade_eligible", thin=B4,
                                 floor=FLOOR).loc[keep]
        pnl = bf.evaluate(h, Rt)["pnl"]
        for lab, a, b in W:
            draws[lab].append(float(pnl.loc[a:b][thin_d.loc[a:b]].sum() / len(Rt.loc[a:b]) * P))
        if k % 100 == 0:
            p(f"  direction control draw {k}")
    out = {}
    p(f"\n=== H12 direction control: te4's thin-day P&L against {N_DRAWS} random within-session reassignments "
      f"(seed {SEED}; ann% of the window) ===")
    for lab, _, _ in W:
        x = np.array(draws[lab])
        o = dict(actual=actual[lab], null_mean=float(x.mean()), null_sd=float(x.std(ddof=1)),
                 p95=float(np.percentile(x, 95)), p_ge=float((x >= actual[lab]).mean()))
        out[lab] = o
        p(f"{lab:<10} te4 {o['actual'] * 100:+.2f}  null mean {o['null_mean'] * 100:+.2f} sd {o['null_sd'] * 100:.2f} "
          f"95th {o['p95'] * 100:+.2f}  P(null >= te4) {o['p_ge']:.3f}")
    OUT["direction_control"] = out


# --------------------------------------------------------------------------- review attacks
def sponsors():
    """Each universe name's sponsor: the first word of `longName` in data/cef/cef_facts.csv (yfinance fund facts,
    fetched 2026-09-11), upper-cased. Raises if a name is missing or has two different names."""
    f = pd.read_csv(bf.DATA_DIR / "cef_facts.csv")
    f = f[f["ticker"].isin(UNIVERSE)]
    nm = f.groupby("ticker")["longName"].agg(lambda x: set(x.dropna()))
    bad = [t for t in UNIVERSE if t not in nm.index or len(nm[t]) != 1]
    if bad:
        raise AssertionError(f"cef_facts.csv has no single longName for {bad}")
    return {t: next(iter(nm[t])).split()[0].upper() for t in UNIVERSE}


def episodes(trade, idx, gap_series):
    """Runs of traded thin sessions merged into one episode when fewer than ADV_WINDOW sessions separate them (two
    such runs share most of their trailing-ADV state, so they are not independent liquidity episodes). Never
    merged across HOLDOUT_START. Each episode's value is the gap summed over its runs' earning days (t+2)."""
    eps = []
    for i0, i1 in ak.runs_of(trade):
        fit = idx[i0] < HOLDOUT_START
        if eps and eps[-1]["fit"] == fit and i0 - eps[-1]["i1"] - 1 < ADV_WINDOW:
            eps[-1]["i1"] = i1
            eps[-1]["parts"].append((i0, i1))
        else:
            eps.append(dict(i0=i0, i1=i1, fit=fit, parts=[(i0, i1)]))
    for e in eps:
        v = 0.0
        for i0, i1 in e["parts"]:
            earn = idx[i0 + 2: i1 + 3]
            v += float(gap_series.loc[earn[earn.isin(gap_series.index)]].sum())
        e.update(first=str(idx[e["i0"]].date()), last=str(idx[e["i1"]].date()), value=v, runs=len(e["parts"]))
    return eps


def review_attacks(H, T, thin, TF, BF, cnt, panel, keep, Rt, res, dist_end):
    """Declared after the review and the beta-detector pass (2026-11-03), before any of it ran here. Each item
    re-runs on committed code an attack that pass made in scratch:
      g. the gap by fund sponsor, every sponsor printed (sponsors());
      h. the FIT stretches merged into independent episodes (episodes()); t, exact sign-flip p, and the
         small-sample t critical value at the bar's one-sided p;
      i. the gap without its three largest FIT stretches;
      j. the recent-books placebo (PR #33's lagged books, adapted to te4): on every session te4 trades and the
         spec does not, the target is rebuilt on THE SAME eligible names from the z-scores of L sessions earlier
         (the vol scalar as of the decision date), L = 0 / 5 / 21 / 63 / 126 / 252; and a static tilt (each
         name's mean te4 FIT thin target, demeaned on the day's eligible names, at the day's te4 gross). The
         static tilt is IN-SAMPLE, which favours the placebo;
      k. extra execution delay: H.shift(k - 2) through evaluate(), k = 3, 4, 6 (k = 2 is the canonical shift(2));
      l. a Dimson factor regression of the daily gap on the repo's ETF panel (data/rv/etf_panel.parquet;
         docs/REFERENCES.md, the 2026-10-11 fetchers row): credit HYG-IEF, rates IEF, loans BKLN-IEF, equity SPY,
         lags 0..K summed, HAC with the Newey-West 1994 lag. K is DERIVED first, on the instruments and not on
         the gap (the finishing pass; the module docstring states the rule): Dimson's summed betas exist because
         a thinly traded close answers a factor move late, so the lag count is how late the universe's own
         equal-weight return answers the four factors over FIT. Lags 0, 1 and 2 are printed beside it. The
         beta-detector's fifth factor, MUB, came from a scratch yfinance pull with no fetcher, so it is not
         used (CLAUDE.md data rules);
      m. the power of a pre-registered forward test, by independent episodes."""
    import inspect
    from math import erf, sqrt as _sqrt
    from scipy import stats as sps
    import statsmodels.api as sm
    from scripts.research.inference import p_clear_bar, upper_bound_max_z
    if "rolling(63," not in inspect.getsource(bf.build_panel):
        raise AssertionError("build_panel's ADV window is no longer 63 sessions; ADV_WINDOW is stale")
    W = [w for w in td.windows(dist_end) if w[0] in ("2010-14", "2015-19", "2020-22", "FIT <2023", "H13 2023+")]
    fit = (pd.Timestamp(bf.SAMPLE_START), HOLDOUT_START - pd.Timedelta(days=1))
    out = {}
    idx = T.index
    trade = thin & (cnt >= FLOOR)
    gap = {r: res[("te4", "instant")]["pnl"] - res[(r, "instant")]["pnl"] for r in ("flatten", "hold")}

    # g. sponsor split
    sp = sponsors()
    fam = sorted(set(sp.values()))
    p("\n=== REVIEW ATTACK g: the gap by fund sponsor (attribution; instant; pp/yr, NW t) ===")
    p("sponsors (cef_facts.csv longName): " + "; ".join(f"{f}: {', '.join(t for t in UNIVERSE if sp[t] == f)}"
                                                       for f in fam))
    out["g_sponsor"] = dict(map=sp)
    for ref in ("flatten", "hold"):
        A = H[("te4", "instant")].loc[keep].shift(2).fillna(0.0)
        B = H[(ref, "instant")].loc[keep].shift(2).fillna(0.0)
        Dn = (A - B) * Rt
        for f in fam:
            cols = [t for t in UNIVERSE if sp[t] == f]
            x = Dn[cols].sum(axis=1)
            out["g_sponsor"][f"{ref}/{f}"] = {lab: dict(pp=float(x.loc[a:b].mean() * P), t=nwt(x.loc[a:b].to_numpy()))
                                              for lab, a, b in W}
            p(f"te4 - {ref}, {f} ({len(cols)}): " + "  ".join(
                f"{lab} {out['g_sponsor'][f'{ref}/{f}'][lab]['pp'] * 100:+.2f} ({out['g_sponsor'][f'{ref}/{f}'][lab]['t']:+.2f})"
                for lab, _, _ in W))

    # h. independent episodes; i. without the three largest stretches
    out["h_episodes"], out["i_top3"] = {}, {}
    for ref in ("flatten", "hold"):
        eps = episodes(trade, idx, gap[ref])
        v = np.array([e["value"] for e in eps if e["fit"]])
        vh = [e["value"] for e in eps if not e["fit"]]
        n = len(v)
        t = float(v.mean() / v.std(ddof=1) * np.sqrt(n))
        signs = ((np.arange(2 ** n)[:, None] >> np.arange(n)[None, :]) & 1).astype(np.int8) * 2 - 1
        pf = float(((signs @ v) >= v.sum() - 1e-15).mean())
        crit = {}
        for N in NS:
            bar = float(upper_bound_max_z(N))
            p1 = 0.5 * (1 - erf(bar / _sqrt(2)))           # the bar's one-sided normal p
            crit[N] = dict(bar=bar, p_bar=p1, t_crit=float(sps.t.ppf(1 - p1, n - 1)),
                           sign_pass=bool(pf <= p1), t_pass=bool(t >= float(sps.t.ppf(1 - p1, n - 1))))
        o = dict(n=n, values=[float(x) for x in v], t=t, positive=int((v > 0).sum()), p_signflip=pf,
                 effect=float(v.mean() / v.std(ddof=1)), h13=[float(x) for x in vh], crit=crit,
                 table=[dict(first=e["first"], last=e["last"], runs=e["runs"], pp=e["value"], fit=e["fit"]) for e in eps])
        out["h_episodes"][ref] = o
        p(f"\n=== REVIEW ATTACK h: te4 - {ref}, the FIT thin stretches merged when fewer than {ADV_WINDOW} sessions "
          f"apart: {n} episodes ===")
        p("  " + ", ".join(f"{e['first']}..{e['last']} ({e['runs']} runs) {e['value'] * 100:+.2f}pp" for e in eps if e["fit"]))
        p(f"  t {t:.2f}; positive {o['positive']}/{n}; exact sign-flip p {pf:.4f}; 2023+ episode(s) "
          f"{[round(x * 100, 2) for x in vh]}pp; " + "; ".join(
              f"N={N}: bar {c['bar']:.3f} (one-sided p {c['p_bar']:.5f}), t({n - 1}) critical {c['t_crit']:.2f} -> "
              f"t {'passes' if c['t_pass'] else 'fails'}, sign test {'passes' if c['sign_pass'] else 'fails'}"
              for N, c in crit.items()))
        runs = []
        x = gap[ref].loc[fit[0]:fit[1]]
        for i0, i1 in ak.runs_of(trade):
            if idx[i0] >= HOLDOUT_START:
                continue
            earn = idx[i0 + 2: i1 + 3]
            earn = earn[earn.isin(x.index)]
            runs.append((float(x.loc[earn].sum()), str(idx[i0].date()), earn))
        top = sorted(runs, key=lambda r: -r[0])[:3]
        y = x.drop(top[0][2].append([r[2] for r in top[1:]]))
        out["i_top3"][ref] = dict(dropped=[r[1] for r in top], pp=float(y.mean() * P), t=nwt(y.to_numpy()),
                                  days_dropped=int(len(x) - len(y)))
        p(f"i. te4 - {ref} FIT without its three largest stretches (starting {[r[1] for r in top]}): "
          f"{out['i_top3'][ref]['pp'] * 100:+.2f}pp/yr (NW t {out['i_top3'][ref]['t']:.2f})")

    # j. recent-books placebo and a static tilt
    zp, retp, adv = panel["z"], panel["ret"], panel["adv"]
    T4, B4 = TF[FLOOR], BF[FLOOR]
    elig = zp.reindex(idx)[UNIVERSE].notna() & (adv.reindex(idx)[UNIVERSE] >= MIN_ADV_USD)
    tr_dates = idx[trade.to_numpy()]
    below = B4.to_numpy()
    thin_d = thin_days_of(thin, Rt.index)

    def run_book(Tx):
        A_ = Tx.values.copy()
        for k in range(1, len(A_)):                  # below-floor rows repeat the previous row, as build_targets does
            if below[k]:
                A_[k] = A_[k - 1]
        h = bf.band_gross_capped(pd.DataFrame(A_, index=T4.index, columns=T4.columns), BAND_WIDTH, MAX_GROSS_STRESS,
                                 below_min_names="trade_eligible", thin=B4, floor=FLOOR)
        return bf.evaluate(h.loc[keep], Rt)["pnl"]

    def summ(x):
        g = x - res[("flatten", "instant")]["pnl"]
        return {lab: dict(thin=float(x.loc[a:b][thin_d.loc[a:b]].sum() / len(x.loc[a:b]) * P),
                          gap=float(g.loc[a:b].mean() * P), t=nwt(g.loc[a:b].to_numpy())) for lab, a, b in W}
    out["j_placebo"] = {}
    p("\n=== REVIEW ATTACK j: recent-books placebo (same names, z from L sessions earlier) and a static tilt; "
      "te4's thin-day ann% and te4 - flatten (NW t) ===")
    for L in (0, 5, 21, 63, 126, 252):
        Tx = T4.copy()
        kept = fell = 0
        for d in tr_dates:
            i = zp.index.get_loc(d)
            names = list(elig.columns[elig.loc[d].to_numpy()])
            row = zp.iloc[i - L][names].dropna()
            if len(row) < FLOOR:
                fell += 1                              # too few lagged z-scores: te4's own row is kept (counted)
                continue
            Tx.loc[d] = bf._target_row(row, retp, i).reindex(UNIVERSE).fillna(0.0).values
            kept += 1
        x = run_book(Tx)
        if L == 0 and not np.allclose(x.to_numpy(), res[("te4", "instant")]["pnl"].to_numpy(), atol=1e-12):
            raise AssertionError("the placebo at L = 0 does not reproduce te4")
        out["j_placebo"][str(L)] = dict(rebuilt=kept, kept_te4_row=fell, **summ(x))
        p(f"L={L:3d} (rebuilt {kept}, te4 row kept {fell}): " + "  ".join(
            f"{lab} thin {out['j_placebo'][str(L)][lab]['thin'] * 100:+.2f} gap {out['j_placebo'][str(L)][lab]['gap'] * 100:+.2f} "
            f"({out['j_placebo'][str(L)][lab]['t']:.2f})" for lab, _, _ in W))
    mw = T4[(trade & (idx < HOLDOUT_START)).to_numpy()].mean()
    Tx = T4.copy()
    for d in tr_dates:
        names = list(elig.columns[elig.loc[d].to_numpy()])
        w = mw[names] - mw[names].mean()
        if w.abs().sum() == 0:
            raise AssertionError(f"the static tilt is 0/0 on {d.date()}")
        Tx.loc[d] = (w / w.abs().sum() * T4.loc[d].abs().sum()).reindex(UNIVERSE).fillna(0.0).values
    out["j_placebo"]["static (in-sample)"] = summ(run_book(Tx))
    o = out["j_placebo"]["static (in-sample)"]
    p("static FIT-mean tilt (IN-SAMPLE): " + "  ".join(
        f"{lab} thin {o[lab]['thin'] * 100:+.2f} gap {o[lab]['gap'] * 100:+.2f} ({o[lab]['t']:.2f})" for lab, _, _ in W))

    # k. extra execution delay
    out["k_delay"] = {}
    p("\n=== REVIEW ATTACK k: extra execution delay, evaluate(H.shift(k - 2)) (k = 2 is shift(2)); te4 minus each, "
      "pp/yr (NW t) ===")
    for k in (2, 3, 4, 6):
        pk = {r: bf.evaluate(H[(r, "instant")].loc[keep].shift(k - 2).fillna(0.0), Rt)["pnl"] for r in MAIN}
        if k == 2 and not np.allclose(pk["te4"].to_numpy(), res[("te4", "instant")]["pnl"].to_numpy(), atol=1e-15):
            raise AssertionError("the delay at k = 2 does not reproduce te4")
        out["k_delay"][str(k)] = {f"{r}/{lab}": dict(pp=float((pk["te4"] - pk[r]).loc[a:b].mean() * P),
                                                     t=nwt((pk["te4"] - pk[r]).loc[a:b].to_numpy()))
                                  for r in ("flatten", "hold") for lab, a, b in W}
        p(f"k={k}: " + "  ".join(f"{lab} -flat {out['k_delay'][str(k)][f'flatten/{lab}']['pp'] * 100:+.2f} "
                                 f"({out['k_delay'][str(k)][f'flatten/{lab}']['t']:.2f})" for lab, _, _ in W))

    # l. Dimson factor regression on the ETF panel
    ep = pd.read_parquet(bf.DATA_DIR.parent / "rv" / "etf_panel.parquet")
    ep["date"] = pd.to_datetime(ep["date"])
    E = ep.pivot_table(index="date", columns="ticker", values="ret_total")
    if E.index.max() < dist_end:
        raise AssertionError(f"etf_panel ends {E.index.max().date()}, before DIST_END {dist_end.date()}")
    F = pd.DataFrame({"credit": E["HYG"] - E["IEF"], "rates": E["IEF"], "loans": E["BKLN"] - E["IEF"],
                      "equity": E["SPY"]})
    first_all = F.dropna().index.min()

    def ols(y, cols, lags):
        # the factor lags are taken on the ETF panel's own calendar BEFORE alignment, so a thin-days-only y still
        # sees each factor's return 1..lags sessions earlier, not the previous thin day's
        X = pd.concat({f"{c}_L{L}": F[c].shift(L) for c in cols for L in range(lags + 1)}, axis=1)
        d = pd.concat([y.rename("y"), X], axis=1).dropna()
        nwl = int(4 * (len(d) / 100) ** (2 / 9))
        return d, nwl, sm.OLS(d["y"], sm.add_constant(d.drop(columns="y"))).fit(cov_type="HAC",
                                                                                  cov_kwds={"maxlags": nwl})

    def reg(y, cols, lags):
        d, nwl, m = ols(y, cols, lags)
        betas = {}
        for c in cols:
            ks = [f"{c}_L{L}" for L in range(lags + 1)]
            b = float(m.params[ks].sum())
            se = float(np.sqrt(np.ones(len(ks)) @ m.cov_params().loc[ks, ks].to_numpy() @ np.ones(len(ks))))
            betas[c] = dict(beta=b, t=b / se)
        return dict(n=int(len(d)), alpha=float(m.params["const"] * P), alpha_t=float(m.tvalues["const"]),
                    r2=float(m.rsquared), betas=betas, nw_lag=nwl, first=str(d.index.min().date()))
    cols4 = ["credit", "rates", "loans", "equity"]
    # THE LAG, derived on the instruments before the gap is regressed (the rule is in the module docstring): the
    # equal-weight return of the universe names with a return that day, FIT from the first date all four factors
    # exist, on lags 0..DIMSON_MAX; each lag's four coefficients tested jointly (HAC Wald)
    ew = Rt[UNIVERSE].mean(axis=1).loc[first_all:fit[1]]
    _, nwl_k, mk = ols(ew, cols4, DIMSON_MAX)
    names_k = list(mk.params.index)
    pv = {}
    for L in range(1, DIMSON_MAX + 1):
        Rm = np.zeros((len(cols4), len(names_k)))
        for j, c in enumerate(cols4):
            Rm[j, names_k.index(f"{c}_L{L}")] = 1.0
        pv[L] = float(np.asarray(mk.wald_test(Rm, use_f=False, scalar=True).pvalue))
    K = 0
    while K < DIMSON_MAX and pv[K + 1] < DIMSON_P:
        K += 1
    if K == DIMSON_MAX:
        raise AssertionError(f"the derived Dimson lag reached its bound {DIMSON_MAX}; widen DIMSON_MAX, do not "
                             "truncate (the lag would be understated)")
    lag_rows = tuple(L for L in (0, 1, 2) if L != K)     # none: 1 is the repo's convention, 2 the second run's
    out["l_factors"] = dict(first_all_four=str(first_all.date()), etf_panel_last=str(E.index.max().date()),
                            lag_derivation=dict(K=K, bound=DIMSON_MAX, p_level=DIMSON_P, wald_p={str(L): v for L, v in pv.items()},
                                                n=int(mk.nobs), nw_lag=nwl_k, sample=f"{ew.index.min().date()}.."
                                                f"{ew.index.max().date()}", r2=float(mk.rsquared)))
    p(f"\n=== REVIEW ATTACK l: Dimson factor regression of the daily gap (lags 0..K summed, K DERIVED; HAC, NW 1994 "
      f"lag); ETF panel to {E.index.max().date()}; all four factors from {first_all.date()} ===")
    p(f"the lag: the universe's equal-weight return on the four factors at lags 0..{DIMSON_MAX}, "
      f"{ew.index.min().date()}..{ew.index.max().date()} (n {int(mk.nobs)}, HAC {nwl_k}, R2 {mk.rsquared:.3f}); joint "
      f"Wald p by lag: " + "  ".join(f"L{L} {v:.4f}" for L, v in pv.items())
      + f"  -> K = {K} (the last lag of the unbroken significant run from lag 1, p < {DIMSON_P})")
    l_rows = ((f"FIT (4 factors), lags 0..{K}", first_all, fit[1], cols4, K, "all"),
              (f"FIT (4 factors), lags 0..{K}, thin days", first_all, fit[1], cols4, K, "thin"),
              (f"FIT (3, no loans), lags 0..{K}", pd.Timestamp(bf.SAMPLE_START), fit[1],
               ["credit", "rates", "equity"], K, "all"),
              (f"H13 2023+ (4 factors), lags 0..{K}", HOLDOUT_START, dist_end, cols4, K, "all")) + tuple(
        (f"FIT (4 factors), lags 0..{L} [sensitivity]", first_all, fit[1], cols4, L, "all") for L in lag_rows)
    for ref in ("flatten", "hold"):
        for lab, a, b, cols, lags, days in l_rows:
            y = gap[ref].loc[a:b]
            if days == "thin":
                y = y[thin_d.loc[a:b]]
            r = reg(y, cols, lags)
            out["l_factors"][f"{ref}/{lab}"] = r
            p(f"te4 - {ref} {lab:<28} n {r['n']:5d} from {r['first']}: alpha {r['alpha'] * 100:+.2f}pp/yr "
              f"(t {r['alpha_t']:.2f}) R2 {r['r2']:.3f} | " + "  ".join(
                  f"{c} {v['beta']:+.3f} ({v['t']:+.1f})" for c, v in r["betas"].items()))

    # m. power of a forward test by independent episodes
    o = out["h_episodes"]["flatten"]
    es = o["effect"]
    x = gap["flatten"]
    trd = thin_days_of(trade, Rt.index)
    per_fit = float(x.loc[fit[0]:fit[1]][trd.loc[fit[0]:fit[1]]].mean())
    per_h13 = float(x.loc[HOLDOUT_START:dist_end][trd.loc[HOLDOUT_START:dist_end]].mean())
    shrink = per_h13 / per_fit
    first_te = idx[trade.to_numpy()].min()
    yrs_fit = (fit[1] - first_te).days / 365.25
    yrs_h13 = (dist_end - HOLDOUT_START).days / 365.25
    rate_fit, rate_h13 = o["n"] / yrs_fit, len(o["h13"]) / yrs_h13
    xx = x.loc[fit[0]:fit[1]][trd.loc[fit[0]:fit[1]]]
    sr_d = float(xx.mean() / xx.std() * np.sqrt(P))
    pw = {}
    for N in NS:
        bar = float(upper_bound_max_z(N))
        pw[N] = {nf: dict(fit=float(p_clear_bar(es * np.sqrt(nf), bar)),
                          shrunk=float(p_clear_bar(es * shrink * np.sqrt(nf), bar))) for nf in (2, 3, 5, 9, 13)}
    out["m_power"] = dict(effect=es, shrink=shrink, per_day_fit=per_fit * P, per_day_h13=per_h13 * P,
                          first_te4=str(first_te.date()), rate_fit=rate_fit, rate_since_2023=rate_h13,
                          years_for_5={"fit_rate": 5 / rate_fit, "since_2023_rate": 5 / rate_h13 if rate_h13 else None},
                          day_sr=sr_d, days_for_half={N: float((upper_bound_max_z(N) / sr_d) ** 2 * P) for N in NS},
                          p_pass=pw)
    p(f"\n=== REVIEW ATTACK m: power of a forward test of te4 - flatten, by independent episodes ===")
    p(f"per-episode effect (mean/sd, FIT) {es:.2f}; shrink = 2023+ / FIT gap per traded thin earning day "
      f"({per_h13 * P * 100:+.2f} / {per_fit * P * 100:+.2f}%/yr) = {shrink:.2f}; episodes per year: FIT {rate_fit:.2f} "
      f"(from {first_te.date()}), since 2023 {rate_h13:.2f}; years for 5 episodes {5 / rate_fit:.1f} / "
      + (f"{5 / rate_h13:.1f}" if rate_h13 else "never"))
    for N in NS:
        p(f"N={N}: P(pass) fit / shrunk effect by forward episodes: " + "; ".join(
            f"{nf}: {v['fit']:.2f} / {v['shrunk']:.2f}" for nf, v in pw[N].items()))
    p(f"day level: FIT thin-traded earning days {len(xx)}, gap SR {sr_d:.2f}; thin earning days for P(pass) = 0.5 at "
      f"N=54: {out['m_power']['days_for_half'][54]:.0f} (IID; overstated if the days are autocorrelated)")
    OUT["review_attacks"] = out


# --------------------------------------------------------------------------- step 5
def forward(T, thin, panel, cnt, H, res, keep, Rt, dist_end, TF, BF, fee_full):
    p("\n=== STEP 5: forward relevance ===")
    out = {}
    c23 = cnt.loc[HOLDOUT_START:]
    by_year = {}
    for y, g in c23.groupby(c23.index.year):
        by_year[str(y)] = {"sessions": int(len(g)), **{f"n={k}": int((g == k).sum()) for k in (4, 5, 6, 7)},
                           "n>=8": int((g >= 8).sum()), "min": int(g.min())}
    out["by_year"] = by_year
    p("eligible count since 2023-01-01, sessions by year: " + "; ".join(
        f"{y}: n=4 {v['n=4']}, 5 {v['n=5']}, 6 {v['n=6']}, 7 {v['n=7']}, >=8 {v['n>=8']} (of {v['sessions']}, min "
        f"{v['min']})" for y, v in by_year.items()))
    last_thin = thin[thin].index.max()
    after = cnt.loc[last_thin + pd.Timedelta(days=1):]
    out["since_last_thin"] = dict(last_thin=str(last_thin.date()), sessions=int(len(after)),
                                  n6=int((after == 6).sum()), n7=int((after == 7).sum()),
                                  last_n6=str(after[after == 6].index.max().date()) if (after == 6).any() else None,
                                  last_n7=str(after[after == 7].index.max().date()) if (after == 7).any() else None)
    o = out["since_last_thin"]
    p(f"since the last thin session ({o['last_thin']}): {o['sessions']} sessions, eligible count 6 on {o['n6']} "
      f"(last {o['last_n6']}), 7 on {o['n7']} (last {o['last_n7']})")

    # the margin: on n = 6 / 7 sessions since 2023, how far the least liquid eligible name sat above the floor
    z, adv = panel["z"].reindex(T.index)[UNIVERSE], panel["adv"].reindex(T.index)[UNIVERSE]
    ok = z.notna() & (adv >= MIN_ADV_USD)
    sel = c23[(c23 == 6) | (c23 == 7)].index
    marg, ratio = [], []
    for d in sel:
        a = adv.loc[d][ok.loc[d]].sort_values()
        marg.append(a.index[0])
        ratio.append(float(a.iloc[0] / MIN_ADV_USD))
    ratio = pd.Series(ratio, index=sel)
    out["margin"] = dict(sessions=int(len(sel)), ratio_min=float(ratio.min()), ratio_p10=float(ratio.quantile(0.1)),
                         ratio_median=float(ratio.median()),
                         marginal_name=pd.Series(marg).value_counts().head(5).to_dict())
    p(f"on the {len(sel)} sessions since 2023 with 6 or 7 eligible: the least liquid eligible name's ADV / floor "
      f"min {ratio.min():.2f}, p10 {ratio.quantile(0.1):.2f}, median {ratio.median():.2f}; most often the "
      f"marginal name: {out['margin']['marginal_name']}")

    # a HYPOTHETICAL [U]: had the least liquid eligible name(s) fallen out, what would each rule hold?
    zp, retp = panel["z"], panel["ret"]
    Hf = H[("flatten", "instant")]
    hyp = {}
    for target_n in (5, 4):
        cos, gross, mx, held, skipped = [], [], [], [], []
        for d in sel:
            a = adv.loc[d][ok.loc[d]].sort_values()
            keep_names = list(a.index[len(a) - target_n:])        # drop the least liquid until target_n remain
            i = zp.index.get_loc(d)
            row = zp.loc[d, keep_names]
            w = bf._target_row(row, retp, i).reindex(UNIVERSE).fillna(0.0)
            full = T.loc[d]
            nw, nf = float(np.linalg.norm(w)), float(np.linalg.norm(full))
            if nw == 0 or nf == 0:
                skipped.append(str(d.date()))                     # every z at the clip: 0/0 (PR #33 5.H)
                continue
            cos.append(float((w @ full) / (nw * nf)))
            gross.append(float(w.abs().sum()))
            mx.append(float(w.abs().max()))
            held.append(float(Hf.loc[d].abs().sum()))
        hyp[f"dip_to_{target_n}"] = dict(cos_median=float(np.median(cos)), cos_p10=float(np.percentile(cos, 10)),
                                          gross_median=float(np.median(gross)), maxw_median=float(np.median(mx)),
                                          maxw_p90=float(np.percentile(mx, 90)),
                                          live_held_gross_median=float(np.median(held)), skipped=skipped)
        h = hyp[f"dip_to_{target_n}"]
        p(f"HYPOTHETICAL [U] dip to {target_n} (drop the least liquid eligible names) on {len(cos)} of those "
          f"{len(sel)} sessions (skipped, a 0/0 target: {skipped}): flatten closes a held book of gross "
          f"{h['live_held_gross_median']:.3f} (median); te4's target on the {target_n} left has cosine "
          f"{h['cos_median']:.2f} (p10 {h['cos_p10']:.2f}) to the full target, gross {h['gross_median']:.3f}, "
          f"max |w| {h['maxw_median']:.3f} (p90 {h['maxw_p90']:.3f})")
    out["hypothetical"] = hyp

    # what the rule changed on the actual 2023+ thin sessions
    a, b = HOLDOUT_START, dist_end
    thin_d = thin_days_of(thin, Rt.index)
    m = thin_d.loc[a:b]
    on = {}
    for r in MAIN:
        x = res[(r, "instant")]["pnl"].loc[a:b]
        g = H[(r, "instant")].abs().sum(axis=1).loc[a:b][thin.loc[a:b]]
        on[r] = dict(pp_on_thin_days=float(x[m].sum()), gross_mean=float(g.mean()))
    out["h13_thin"] = dict(days=int(m.sum()), first=str(thin.loc[a:b][thin.loc[a:b]].index.min().date()),
                           last=str(thin.loc[a:b][thin.loc[a:b]].index.max().date()), **on)
    p(f"the 2023+ thin sessions ({out['h13_thin']['first']}..{out['h13_thin']['last']}, {int(m.sum())} earning days): "
      + "; ".join(f"{r} earned {v['pp_on_thin_days'] * 100:+.2f}pp over them, mean gross {v['gross_mean']:.3f}"
                  for r, v in on.items()))

    # expected annual effect [U]: (te4 - flatten) per unit share of traded thin sessions, times a forward share.
    # CHANGED AFTER THE REVIEW (finding 3): the one out-of-sample analogue, 2023+ itself (thin at a 15% share,
    # one stretch), is a base beside the fit-period ones, and leads; and the book at m is built the way trial 53
    # is activated at the tag (m x band_gross_capped(T, band, max_gross_stress / m), PR #33's reproduction of
    # impl_core), not by multiplying the unit gap and ignoring the ceiling
    tag = td._git_show_json(f"{td.RELEASE_TAG}:ops/specs/cef_discount.frozen.json")
    mult = float(tag["frozen"]["sizing_multiplier"])
    if cef_below_min_names(tag["frozen"]) != "flatten":
        raise AssertionError(f"{td.RELEASE_TAG} sets below_min_names; the comparison is not against its live rule")
    rm = {}
    for rule, TT, kw in (("flatten", T, dict(below_min_names="flatten", thin=thin)),
                         ("te4", TF[FLOOR], dict(below_min_names="trade_eligible", thin=BF[FLOOR], floor=FLOOR))):
        for fl in FLIPS:
            hm = mult * bf.band_gross_capped(TT, BAND_WIDTH, MAX_GROSS_STRESS / mult, defer_flips=fl == "deferred",
                                             **kw)
            rm[(rule, fl)] = dict(evaluate=bf.evaluate(hm.loc[keep], Rt), H=hm)
    trade = thin & (cnt >= FLOOR)
    h13 = (HOLDOUT_START, dist_end)
    bm = {(r, sz): bf.borrow_charge(rm[(r, "instant")]["H"].loc[keep] if sz == "m" else H[(r, "instant")].loc[keep],
                                    fee_full)["cost"]
          for r in ("te4", "flatten") for sz in ("unit", "m")}

    def per_share(lab, a_, b_):
        s_ = float(trade.loc[a_:b_].mean())
        o = dict(window=lab, share=s_)
        for sz, src in (("unit", {k: v for k, v in res.items()}),
                        ("m", {k: v["evaluate"] for k, v in rm.items()})):
            d = (src[("te4", "instant")]["pnl"] - src[("flatten", "instant")]["pnl"]).loc[a_:b_]
            dt = (src[("te4", "deferred")]["pnl"] - src[("flatten", "deferred")]["pnl"]).loc[a_:b_]
            tt = (src[("te4", "instant")]["turn_series"] - src[("flatten", "instant")]["turn_series"]).loc[a_:b_]
            o[sz] = dict(gap=float(d.mean() * P), t=nwt(d.to_numpy()), gap_deferred=float(dt.mean() * P),
                         per_share=float(d.mean() * P / s_), per_share_deferred=float(dt.mean() * P / s_),
                         extra_turn_per_share=float(tt.mean() * P / s_))
        return o
    bases = [per_share("H13 2023+ (the out-of-sample analogue)", *h13),
             per_share("FIT <2023", pd.Timestamp(bf.SAMPLE_START), HOLDOUT_START - pd.Timedelta(days=1)),
             per_share("2015-22 (thin = 4-5 names)", pd.Timestamp("2015-01-01"), pd.Timestamp("2022-12-31"))]
    sh13 = float(trade.loc[h13[0]:h13[1]].mean())
    days13 = Rt.loc[h13[0]:min(h13[1], fee_full.dropna(how="all").index.max())].index
    borrow_ps = {sz: float((bm[("te4", sz)] - bm[("flatten", sz)]).loc[days13].mean() * P / sh13)
                 for sz in ("unit", "m")}                  # extra borrow per unit share, at 2023+'s measured fees
    shares = {"0 (the state since 2023-08-30)": 0.0, "the 2023+ share": sh13}
    out["expected"] = dict(bases=bases, shares=shares, m=mult, tag=td.RELEASE_TAG, spec_id=tag.get("spec_id"),
                           borrow_per_share_2023=borrow_ps, rows=[])
    p(f"EXPECTED ANNUAL EFFECT [U] = (te4 - flatten gap per unit share of sessions te4 trades and flatten does not) x "
      f"(a forward share); the current book at {td.RELEASE_TAG} ({tag.get('spec_id')}) is built at m = {mult}: "
      f"m x band_gross_capped(T, band, {MAX_GROSS_STRESS} / m). Extra borrow per unit share at 2023+'s measured fees: "
      f"unit {borrow_ps['unit'] * 100:+.2f}, at m {borrow_ps['m'] * 100:+.2f}pp/yr")
    for bs in bases:
        p(f"  base {bs['window']}: share {bs['share'] * 100:.1f}%; " + "; ".join(
            f"{sz}: gap {bs[sz]['gap'] * 100:+.2f}pp/yr (t {bs[sz]['t']:.2f}; deferred {bs[sz]['gap_deferred'] * 100:+.2f}) "
            f"-> {bs[sz]['per_share'] * 100:+.2f} per unit share (deferred {bs[sz]['per_share_deferred'] * 100:+.2f}); "
            f"extra turnover {bs[sz]['extra_turn_per_share']:+.1f}/yr per unit share" for sz in ("unit", "m")))
        for sk, sv in shares.items():
            row = dict(base=bs["window"], share_key=sk, share=sv)
            for sz in ("unit", "m"):
                g = bs[sz]["per_share"] * sv
                c15 = bs[sz]["extra_turn_per_share"] * sv * 15 / 1e4
                br = borrow_ps[sz] * sv
                row[sz] = dict(gross=g, gross_deferred=bs[sz]["per_share_deferred"] * sv, cost15=c15, borrow=br,
                               net=g - c15 - br)
            out["expected"]["rows"].append(row)
            p(f"    forward share {sk} = {sv * 100:.1f}%: " + "; ".join(
                f"{sz} gross {row[sz]['gross'] * 100:+.2f} (deferred {row[sz]['gross_deferred'] * 100:+.2f}), extra "
                f"turnover @15bp {row[sz]['cost15'] * 100:.2f}, extra borrow at 2023+ fees {row[sz]['borrow'] * 100:.2f}, "
                f"net {row[sz]['net'] * 100:+.2f}pp/yr" for sz in ("unit", "m")))
    OUT["forward"] = out


# --------------------------------------------------------------------------- main
def main():
    live_rule = cef_below_min_names(spec()["frozen"])
    p(f"spec {SPEC_ID}; band {BAND_WIDTH}, max_gross_stress {MAX_GROSS_STRESS}, min_names {MIN_NAMES}, "
      f"min_adv_usd {MIN_ADV_USD:,.0f}; live below_min_names (registry) {live_rule!r}; floor {FLOOR} (derived), "
      f"plateau {PLATEAU}")
    if live_rule != "flatten":
        raise AssertionError("the live rule is no longer 'flatten'; this report's labels are wrong")
    T, R, thin, panel, dist_end, keep, Rt, TF, BF, cnt = inputs()
    p(f"panels: prices to {panel['px'].index.max().date()}, targets {T.index[0].date()}..{T.index[-1].date()}, "
      f"returns cut at DIST_END {dist_end.date()}")
    for f in PLATEAU:
        tr = thin & (cnt >= f)
        p(f"floor {f}: trades {int(tr.sum())} of the {int(thin.sum())} thin sessions; by era "
          + ", ".join(f"{lab} {int(tr.loc[a:b].sum())}" for lab, a, b in td.windows(dist_end)[:5]))
        OUT.setdefault("traded_thin", {})[f] = {lab: int(tr.loc[a:b].sum()) for lab, a, b in td.windows(dist_end)}
    sleeve_check(T, thin, TF, cnt)
    H = books(T, thin, TF, BF)
    for f in PLATEAU:
        for defer in (False, True):
            ref = td.independent_flatten(TF[f], BF[f], defer)
            got = H[(te(f), "deferred" if defer else "instant")]
            diff = float(np.abs(ref.values - got.values).max())
            if diff > 1e-12:
                raise AssertionError(f"independent loop differs for te{f} by {diff}")
    p("second method 2 [independent pandas loop on the floor's targets and mask]: every te book matches (<= 1e-12)")
    res = {k: bf.evaluate(h.loc[keep], Rt) for k, h in H.items()}
    rep = report(H[(te(FLOOR), "instant")].loc[keep], Rt)
    for k, a, b in (("fit", None, HOLDOUT_START - pd.Timedelta(days=1)), ("holdout", HOLDOUT_START, None)):
        x = res[(te(FLOOR), "instant")]["pnl"].loc[a:b]
        if abs(rep[k]["gross_sr"] - x.mean() / x.std() * np.sqrt(P)) > 1e-12:
            raise AssertionError(f"harness.report disagrees on {k}")
    p(f"second method 3 [harness.report, nan_policy='raise', te{FLOOR} instant]: fit SR {rep['fit']['gross_sr']:.3f}, "
      f"holdout SR {rep['holdout']['gross_sr']:.3f}")

    rows = scoreboard(res, thin, dist_end, MAIN, "STEP 3: hold / flatten / te4, instant and deferred flips", "table")
    paired(res, dist_end, "te4", ("flatten", "hold"), "paired_te4")
    thin_only(res, thin, dist_end, MAIN)
    era_cv(rows, MAIN)
    prow = scoreboard(res, thin, dist_end, tuple(te(f) for f in PLATEAU), "H8 plateau rows: te3 / te4 / te5",
                      "table_plateau")
    era_cv(prow, tuple(te(f) for f in PLATEAU))
    plateau(res, dist_end)
    plateau_per_session(res, thin, cnt, dist_end)
    # the cost hurdle read_result is given: te4's extra FIT turnover over each reference at the spec band x 15bp
    hurdle = {r: (rows[("te4", "instant", "FIT <2023")]["turn"] - rows[(r, "instant", "FIT <2023")]["turn"])
              * HURDLE_BP / 1e4 for r in ("flatten", "hold")}
    OUT["hurdle"] = dict(bp=HURDLE_BP, **hurdle)
    p("\ncost hurdle for read_result (te4's extra FIT turnover at the spec band x "
      f"{HURDLE_BP}bp): " + ", ".join(f"vs {r} {v * 100:.2f}pp/yr" for r, v in hurdle.items()))
    matched(T, thin, TF, BF, keep, Rt, rows, res, hurdle)
    concentration(H, T, thin, TF, cnt, dist_end)
    leave_out(H, keep, Rt, dist_end, "flatten")
    leave_out(H, keep, Rt, dist_end, "hold")
    rebuilt(dist_end)
    fee_full = borrow(H, keep, Rt, dist_end, res)
    attack(H, T, thin, cnt, panel, keep, Rt, res, dist_end, hurdle)
    review_attacks(H, T, thin, TF, BF, cnt, panel, keep, Rt, res, dist_end)
    degenerate_replay(T, thin, TF, BF, keep, Rt, dist_end)
    forward(T, thin, panel, cnt, H, res, keep, Rt, dist_end, TF, BF, fee_full)
    direction_control(T, thin, TF, BF, cnt, keep, Rt, res, dist_end)

    (HERE / "run.log").write_text("\n".join(LOG) + "\n")
    (HERE / "results.json").write_text(json.dumps(OUT, indent=1, default=str))


if __name__ == "__main__":
    main()
