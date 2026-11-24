"""The band width re-derived from the measured execution cost, and its plateau check (2026-11-05).

    python3 -B results/cef/band_cost_2026-11-05/band_cost.py \\
        --data-root <a checkout's data/ (read only)> --cut-dir <a new folder OUTSIDE the repository>
        -> results/cef/band_cost_2026-11-05/band_cost_2026-11-05.{json,txt}

    Before the first run in a fresh worktree: `python3 scripts/cef/c4_paper_benchmark.py stage`
    (copies C4's gitignored CRSP extract into results/cef/c4/_cache_c4/, sha-checked).

ZERO TRIALS; FIT ONLY. This is the analysis behind `results/cef/BAND_COST_REDERIVATION_2026-11-05.md` (drafted as `PREREG_DRAFT_BAND_COST_2026-11-05.md`),
drafted as a pre-registration and CLOSED at zero trials by the team lead on 2026-11-05 (CEF stays 55). It changes no spec and nothing on the live path. Every panel
is copied with a parquet filter at 2022-12-30 into --cut-dir before anything is computed, so no row of
the 2023+ holdout is ever materialised, and every frame that reaches a statistic is asserted to end
by 2022-12-30. Nothing under data/ is written; --cut-dir must be outside the repository.

WHY (team lead, 2026-11-05: "pre-register a re-derivation of the rebalancing band using the measured
execution cost"). The 4.8% band was derived on 2026-09-06 by the cube-root law

    h* = (3 c sigma_w^2 / (2 kappa_w))^(1/3)

at an ASSUMED cost of 15-22bp (`_band_width_note`). The paper book's cost has now been measured:
B = 7.14bp per unit of notional traded against the official close
(`results/cef/EXEC_COST_STUDY_2026-11-05.md`, PR #58, commit 2476a16, not yet merged). This script
puts that c into the same law with sigma_w and kappa_w re-measured on the fit, for both books, then
checks whether the derived width lands on the fit's plateau. It does not pick a width from the grid.

THE COST INPUTS ARE READ, NOT TYPED (H14). They come from the study's output of record,
`results/cef/exec_cost_2026-11-05/aggregates_2026-11-05.json`, read at --cost-ref (default the pinned
commit 2476a16 of branch exec-cost-study; once PR #58 merges the same path on main is identical):
  * core c  = tables["all (core, late_market)"]["B_bp"]                      (pooled, notional-weighted)
  * its 95% interval = B_day_mean +- t(20 df, 0.975) x B_day_mean / B_day_t, the study's own arithmetic
  * C4 c    = core c x the quoted-half-spread ratio at 15:52 (the send minute), C4's 15 traded names over
              the core's 13, mean over 21 sessions (spread_profile ... half_spread_bp_mean["15:52:00"]).
              C4's own fill cost is ONE session (the opening build) and is not used (decision C in the
              draft). The median ratio is printed beside it as a sensitivity.

THE DEFINITIONS, DECLARED HERE BEFORE THE COMMITTED RUN. A scratch prototype of the same code was run
first, on 2026-11-05. The target-dynamics definitions below are the prototype's, unchanged. ITS PLATEAU
POINT ESTIMATES (the net-Sharpe columns by width, both books) WERE SEEN BEFORE THE PLATEAU READING
BELOW WAS WRITTEN; the paired tests (P2) had not been computed. So P1's 0.05 tolerance is descriptive,
chosen with the point estimates in view, and decides nothing alone; P2 is the test.

  The book whose target is measured: the UNIT target T, before the band and the cap.
    core: `band_frontier.build_targets()` on the spec's 13 names (the harness book every core study uses);
    C4:   `c4_paper_benchmark.spec_targets` = CEF trial 54's blend, the v5 sleeve's construction
          (DG-L4 matched it to the sleeve on 907 of 907 sessions), on trial 52's frozen 74.
  WHY UNIT AND NOT x m. Both specs apply the band to held / m against the unit target
  (`_sizing_multiplier_note`: "The band compares the unit target with held/m"), so `band_width` is a
  UNIT-weight quantity. Under mean-variance the multiplier is a change of risk aversion: the target, the
  deviation penalty and the cost all scale with m, and the optimal band in unit weights does not move.
  The cube-root law with kappa_w standing in for the penalty is not scale-free (h ~ m^(2/3) in account
  weights, so m^(-1/3) in unit weights). The account-weight reading is printed beside the primary as a
  sensitivity, and the draft explains the choice. The original derivation was at m = 1, where the two agree.

  Active pairs (t-1, t): sessions on which the book trades on BOTH days.
    core: neither session thin (`band_frontier.thin_sessions`, the live flatten rule's mask);
    C4:   neither row a hold (C4's spec holds on thin sessions; a hold repeats the previous row exactly,
          which an active row never does, `band_frontier._check_thin_matches_T`'s contract).
  WHY. On a thin session the core is flat and the target does not diffuse; on the hold book it is
  frozen. Counting those sessions dilutes sigma_w^2 but not kappa_w measured on active pairs, which
  biases h* down. sigma_w and kappa_w are both measured on the same active pairs.

  Name-days: the name has a non-zero unit target on both t-1 and t (it is in the book on both days).
  WHY. The law's sigma_w is a diffusion. An entry (0 -> w) or an exit (w -> 0) is a jump, which the
  band meets as one trade to its edge. "Non-zero on either day" is printed as a sensitivity.

  sigma_w = the pooled sample sd of dT over those name-days (per day).
  phi_w   = the pooled AR(1) coefficient through the origin, sum(T_t T_{t-1}) / sum(T_{t-1}^2), over the
            same name-days; kappa_w = -ln(phi_w); half-life ln 2 / kappa_w.
  The per-name mean of the sd is printed as a sensitivity.

  CALIBRATION. The 2026-09-06 inputs (sigma_w 0.04083/day, phi_w 0.95280) were measured on the
  17-name v6 book over the whole sample to 2026-09, by a script that is in neither main nor tag
  pre-clean-slate (searched 2026-11-05). This script runs the same definitions on the 17 names over the
  FIT ONLY and prints them beside the original. It cannot reproduce the original's window.

THE PLATEAU CHECK (fit, the book each account trades):
    core: m x band_gross_capped(T, b, cap / m, below_min_names="flatten", thin=thin_sessions(T.index))
          (trial 53's implementation B, `results/cef/prereg_voltarget/flatten_exact.py`);
    C4:   m x band_gross_capped(T_B, b, cap / m)  (C4 holds on thin sessions inside T_B;
          `c4_paper_benchmark.h11_reference`'s construction).
  Scored by `scripts/research/harness.evaluate` (shift(2), nan_policy "raise"), on total return and on
  price-only return (paper pays no distributions: its P&L of record is price only). Gross is the
  headline; net at the cost the width was derived at, and the 5/15/30bp grid, sit beside it, labelled.
  Widths: the derived h* x 2^(k/3), k = -3..3 (each step is the width the law gives at double or half
  the cost), unioned with the frontier's own sweep points 1.6-9.6% and the live 4.8%.
  Reading, declared:
    (P1) point estimate: is net Sharpe at c* at h* within 0.05 of the grid's best?
    (P2) paired test: is the grid argmax's net Sharpe at c* above h*'s with a two-sided HAC p < 0.05
         (`scripts/research/resampling.sharpe_diff`, block 21, M 999, seed 20261105)? If not, h* is not
         distinguishable from the top of the grid.
    The slope direction (is the best width narrower or wider than h*) is reported for each era.
  H2: two widths of one band cannot be matched on turnover without becoming the same width. The pair
  (h*, live 4.8%) is reported as an H2 pair only if their turnovers are within 5%; otherwise the
  comparison is priced at c (net), and the draft says so.

NO SILENT FALLBACKS. A missing input raises naming it. No number about the market is typed here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from scripts.cef import band_frontier as bf  # noqa: E402
from scripts.cef import c4_families as c4  # noqa: E402
from scripts.cef import c4_paper_benchmark as bm  # noqa: E402
from scripts.cef import spec as S  # noqa: E402
from scripts.research import harness as hz  # noqa: E402
from scripts.research.inference import newey_west_t  # noqa: E402
from scripts.research.resampling import sharpe_diff  # noqa: E402

STAMP = "2026-11-05"
FIT_END = pd.Timestamp("2022-12-30")
W1 = pd.Timestamp("2013-06-25")                  # trial 53's window: the core's first non-thin era
COST_REF = "2476a16000a0e513dca516e598c451b179f73cd2"   # exec-cost-study (PR #58) as read for the draft
COST_PATH = "results/cef/exec_cost_2026-11-05/aggregates_2026-11-05.json"
T_975_20DF = 2.086                               # the study's own t quantile (21 days, 20 df)
SEND_MINUTE = "15:52:00"                         # every late_market order went at 15:52:0x (the study)
GRID_BP = (5.0, 15.0, 30.0)                      # H3
ORIGINAL = {"sigma_w": 0.04083, "phi_w": 0.95280, "kappa_w": 0.04835, "half_life": 14.3,
            "h_15bp": 0.0426, "h_22bp": 0.0485,
            "source": "results/cef/PREREG_BAND_2026-09-06.md and the spec's _band_width_note [S]"}
V6_EXTRA = ("NAD", "NEA", "NVG", "NZF")          # the 17 = the 13 + these (PREREG_ALPACA_V7: trial 49)
FRONTIER_POINTS = (0.016, 0.024, 0.032, 0.048, 0.064, 0.096)   # band_frontier.BAND_SWEEP's 1.6-9.6% points
P1_TOL = 0.05
SD_BLOCK, SD_M, SD_SEED = 21, 999, 20261105
NW_LAG, NW_LAG_ALT = 21, 63                       # the pass rule's t: Newey-West on the daily difference
ERAS = (("2005-09", "2005-01-01", "2009-12-31"),
        ("2010-14", "2010-01-01", "2014-12-31"), ("2015-19", "2015-01-01", "2019-12-31"),
        ("2020-22", "2020-01-01", "2022-12-31"))


# --------------------------------------------------------------------------- guards

def _assert_fit(*frames) -> None:
    for f in frames:
        if len(f) and pd.Timestamp(f.index.max()) > FIT_END:
            raise AssertionError(f"holdout leak: a frame reaches {pd.Timestamp(f.index.max()).date()}")


def _outside_repo(p: Path) -> Path:
    p = p.resolve()
    if p == REPO or REPO in p.parents:
        raise ValueError(f"--cut-dir {p} is inside the repository; panel copies must never be where git can see them")
    if "data" in p.parts:
        raise ValueError(f"--cut-dir {p} has a 'data' component; nothing is written under a data/ tree")
    return p


# --------------------------------------------------------------------------- the cost inputs (H14: read)

def read_costs(ref: str) -> dict:
    """The study's aggregates at `ref` (git show), and the three cost figures this draft uses."""
    raw = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{COST_PATH}"], capture_output=True, text=True)
    if raw.returncode != 0:
        raise FileNotFoundError(f"git show {ref}:{COST_PATH} failed: {raw.stderr.strip()[:200]}")
    d = json.loads(raw.stdout)
    core = d["tables"]["all (core, late_market)"]
    c_core = float(core["B_bp"])
    half = T_975_20DF * float(core["B_day_mean_bp"]) / float(core["B_day_t"])
    ci = (float(core["B_day_mean_bp"]) - half, float(core["B_day_mean_bp"]) + half)
    ci_c = (c_core - half, c_core + half)          # the same half-width, centred on the pooled c* (review)
    sp = d["spread_profile"]
    qc, q4 = sp["core universe"], sp["c4 traded names"]
    r_mean = float(q4["half_spread_bp_mean"][SEND_MINUTE]) / float(qc["half_spread_bp_mean"][SEND_MINUTE])
    r_med = float(q4["half_spread_bp_median"][SEND_MINUTE]) / float(qc["half_spread_bp_median"][SEND_MINUTE])
    c4one = d["tables"]["c4, 2026-11-04 (opening build)"]
    return {"ref": ref, "path": COST_PATH,
            "core_B_bp": c_core, "core_B_day_mean_bp": float(core["B_day_mean_bp"]),
            "core_B_day_t": float(core["B_day_t"]), "core_B_ci95_day_mean_bp": ci,
            "core_B_ci95_centred_on_pooled_bp": ci_c,
            "core_QHS_bp": float(core["QHS_bp"]), "core_days": int(core["days"]), "core_orders": int(core["orders"]),
            "spread_core_mean_1552": float(qc["half_spread_bp_mean"][SEND_MINUTE]),
            "spread_c4_mean_1552": float(q4["half_spread_bp_mean"][SEND_MINUTE]),
            "spread_core_median_1552": float(qc["half_spread_bp_median"][SEND_MINUTE]),
            "spread_c4_median_1552": float(q4["half_spread_bp_median"][SEND_MINUTE]),
            "spread_name_days": {"core": int(qc["name_days"]), "c4": int(q4["name_days"])},
            "ratio_mean": r_mean, "ratio_median": r_med,
            "c4_B_bp": c_core * r_mean, "c4_B_bp_median_ratio": c_core * r_med,
            "c4_one_session": {"B_bp": float(c4one["B_bp"]), "QHS_bp": float(c4one["QHS_bp"]),
                               "days": int(c4one["days"])},
            "turnover_core_live": {k: float(v["turns_per_year"]) for k, v in d["turnover_core"].items()}}


# --------------------------------------------------------------------------- the law's inputs

def dynamics(T: pd.DataFrame, inactive: np.ndarray, era=None, nonzero: str = "both", flat_ok: bool = False) -> dict:
    """sigma_w, phi_w, kappa_w on active pairs (see the module docstring). `inactive` is a bool per row
    of T: True where the book does not trade (thin, or a hold)."""
    if len(inactive) != len(T):
        raise ValueError("inactive must have one flag per row of T")
    A = T.to_numpy(dtype=float)
    idx = T.index[1:]
    ap = (~inactive[1:]) & (~inactive[:-1])
    if era is not None:
        ap &= (idx >= pd.Timestamp(era[0])) & (idx <= pd.Timestamp(era[1]))
    p, c = A[:-1][ap], A[1:][ap]
    sel = ((p != 0) & (c != 0)) if nonzero == "both" else ((p != 0) | (c != 0))
    if sel.sum() < 100 and flat_ok:
        # an ERA in which the book barely trades (the core before 2013 is thin: flat by the live rule). It is
        # returned labelled FLAT, printed as such, and never fed to the law; a whole-book call still raises.
        return {"flat": True, "active_pairs": int(ap.sum()), "name_days": int(sel.sum())}
    if sel.sum() < 100:
        raise ValueError(f"only {int(sel.sum())} name-days; too few to measure target dynamics")
    dT = (c - p)[sel]
    sigma = float(dT.std(ddof=1))
    phi = float((c[sel] * p[sel]).sum() / (p[sel] ** 2).sum())
    if not 0 < phi < 1:
        raise ValueError(f"phi_w {phi} is outside (0, 1); kappa_w is undefined")
    D = np.where(sel, c - p, np.nan)
    per_name = np.array([np.nanstd(D[:, j], ddof=1) for j in range(D.shape[1]) if np.isfinite(D[:, j]).sum() > 20])
    kappa = -math.log(phi)
    return {"active_pairs": int(ap.sum()), "name_days": int(sel.sum()), "sigma_w": sigma, "phi_w": phi,
            "kappa_w": kappa, "half_life": math.log(2) / kappa, "sigma_w_per_name_mean": float(per_name.mean()),
            "mean_abs_w": float(np.abs(c[sel]).mean()), "first_pair": str(idx[ap][0].date()),
            "last_pair": str(idx[ap][-1].date())}


def written(h: float) -> float:
    """The value the spec would hold: truncated to 0.1pp, as 2026-09-06 wrote its derived 4.85% as 0.048."""
    return math.floor(h * 1000 + 1e-9) / 1000


def h_star(c_bp: float, sigma: float, kappa: float) -> float:
    """The cube-root law, c in bp per unit of notional traded (one way, as `evaluate`'s turnover counts it)."""
    return (3.0 * (c_bp / 1e4) * sigma ** 2 / (2.0 * kappa)) ** (1.0 / 3.0)


# --------------------------------------------------------------------------- the plateau

def score(H: pd.DataFrame, R: pd.DataFrame, costs: dict) -> dict:
    r = hz.evaluate(H, R)
    ann, vol, turn = r["ann_ret"], r["vol"], r["turn"]
    out = {"gross_sr": float(r["gross_sr"]), "ann": float(ann), "vol": float(vol), "turn": float(turn),
           "net_sr": {k: float((ann - turn * c / 1e4) / vol) for k, c in costs.items()}}
    eras = {}
    for lab, a, b in ERAS:
        pn = r["pnl"].loc[a:b]
        tu = r["turn_series"].loc[a:b]
        e_ann, e_vol, e_t = pn.mean() * 252, pn.std() * np.sqrt(252), tu.mean() * 252
        eras[lab] = {"gross_sr": float(e_ann / e_vol) if e_vol > 0 else None, "ann": float(e_ann), "turn": float(e_t),
                     "net_sr": {k: (float((e_ann - e_t * c / 1e4) / e_vol) if e_vol > 0 else None)
                                for k, c in costs.items()}}
    out["eras"] = eras
    held = H.shift(2).abs().sum(axis=1) > 0
    w1 = r["pnl"].loc[W1:]
    tw = r["turn_series"].loc[W1:]
    trading = held.loc[W1:]
    xe = w1[trading]
    # Turnover is counted on DECISION sessions, every trade included: a session whose decided book is
    # non-zero or which traded (an exit to flat, a re-entry). Averaging it over the earn mask above, as
    # the first version did, dropped every re-entry after two or more thin sessions (review, 2026-11-05).
    dec = ((H.abs().sum(axis=1) > 0) | (r["turn_series"] > 0)).loc[W1:]
    out["w1_trading"] = {"sessions": int(trading.sum()), "ann": float(xe.mean() * 252),
                         "gross_sr": float(xe.mean() / xe.std() * np.sqrt(252)),
                         "decision_sessions": int(dec.sum()), "turn": float(tw.sum() * 252 / dec.sum())}
    out["_pnl"], out["_turn"] = r["pnl"], r["turn_series"]
    return out


def paired(a: dict, b: dict, c_bp: float) -> dict:
    """sharpe_diff of a's net-at-c daily series minus b's (positive = a better)."""
    x = (a["_pnl"] - a["_turn"] * c_bp / 1e4).to_numpy()
    y = (b["_pnl"] - b["_turn"] * c_bp / 1e4).to_numpy()
    s = sharpe_diff(x, y, block=SD_BLOCK, M=SD_M, seed=SD_SEED)
    # THE PASS RULE'S STATISTIC: the claim is "earns more net at c", a RETURN difference, so its t is the
    # Newey-West t of the daily net-return difference (lag 21, one month; 63 beside it). The Sharpe
    # difference above is the plateau's test; both are printed and named.
    dn = x - y
    dg = (a["_pnl"] - b["_pnl"]).to_numpy()
    return {"delta_annual": float(s["delta_annual"]), "se_annual": float(s["se"] * np.sqrt(252)),
            "hac_p": float(s["hac_p_value"]), "boot_p": float(s["p_value"]),
            "ci_annual": [float(v) for v in s["ci_annual"]],
            "net_diff_pp_yr": float(dn.mean() * 252 * 100), "nw_t_net": float(newey_west_t(dn, NW_LAG)),
            "nw_t_net_lag63": float(newey_west_t(dn, NW_LAG_ALT)),
            "gross_diff_pp_yr": float(dg.mean() * 252 * 100), "nw_t_gross": float(newey_west_t(dg, NW_LAG))}


def model_change(a: dict, b: dict, c_bp: float, say, who: str = "h*") -> dict:
    """h* against the live width, as a MODEL on the fit: turnover, its cost at c, gross and net, over the
    fit calendar and in 2020-22 (the last fit era, the busiest). Account units (x m), %NAV a year."""
    out = {}
    for lab, ra, rb in (("fit", a, b), ("2020-22", a["eras"]["2020-22"], b["eras"]["2020-22"])):
        dt_ = ra["turn"] - rb["turn"]
        out[lab] = {"turn_h": ra["turn"], "turn_live": rb["turn"], "turn_rel": ra["turn"] / rb["turn"] - 1,
                    "d_turn": dt_, "d_cost_pct_nav": dt_ * c_bp / 1e4 * 100,
                    "d_gross_pct": (ra["ann"] - rb["ann"]) * 100,
                    "d_net_pct": ((ra["ann"] - rb["ann"]) - dt_ * c_bp / 1e4) * 100}
        o = out[lab]
        say(f"    MODEL, {who} vs live, {lab}: turn/yr {o['turn_h']:.1f} vs {o['turn_live']:.1f} ({o['turn_rel']:+.1%}); "
            f"cost at {c_bp:.2f}bp {o['d_cost_pct_nav']:+.3f}%NAV/yr; gross {o['d_gross_pct']:+.3f}pp/yr; net "
            f"{o['d_net_pct']:+.3f}pp/yr")
    return out


def plateau(book: str, build, R_by: dict, h: float, c_star: float, live: float, say) -> dict:
    """Score every width of the declared grid on each return basis; read P1/P2 at c_star."""
    ladder = [h] + [round(h * 2 ** (k / 3), 5) for k in (-3, -2, -1, 1, 2, 3)]   # k = 0 is h* itself, unrounded
    spec_value = written(h)
    widths = sorted(set(ladder) | set(FRONTIER_POINTS) | {live, spec_value})
    costs = {"c_star": c_star, **{f"{int(c)}bp": c for c in GRID_BP}}
    out = {"widths": widths, "c_star_bp": c_star, "h_star": h, "live": live, "basis": {}}
    books = {b: build(b) for b in widths}
    for H in books.values():
        _assert_fit(H)
    for basis, R in R_by.items():
        rows = {b: score(books[b], R(books[b]), costs) for b in books}
        say(f"\n  {book}, {basis} returns, fit to {FIT_END.date()}: gross SR is the headline; net at "
            f"c* = {c_star:.2f}bp and the 5/15/30bp grid beside it (labelled, never mixed); no borrow")
        say(f"    {'width':>7} {'gross SR':>9} {'ann%':>6} {'turn/yr':>8} {'net@c*':>8} {'net@5':>7} "
            f"{'net@15':>7} {'net@30':>7} {'flips?':>7}")
        for b in sorted(rows):
            r = rows[b]
            n = r["net_sr"]
            flip = "YES" if len({np.sign(n['5bp']), np.sign(n['15bp']), np.sign(n['30bp'])}) > 1 else "no"
            tag = ("  <- h* (derived)" if abs(b - h) < 1e-12 else ("  <- live" if abs(b - live) < 1e-12 else
                   ("  <- h* as the spec would hold it (0.1pp, truncated)" if abs(b - spec_value) < 1e-12 else "")))
            say(f"    {b * 100:6.2f}% {r['gross_sr']:9.3f} {r['ann'] * 100:6.2f} {r['turn']:8.1f} "
                f"{n['c_star']:8.3f} {n['5bp']:7.3f} {n['15bp']:7.3f} {n['30bp']:7.3f} {flip:>7}{tag}")
        grid = [b for b in widths]
        best = max(grid, key=lambda b: rows[b]["net_sr"]["c_star"])
        p1 = rows[best]["net_sr"]["c_star"] - rows[h]["net_sr"]["c_star"]
        test_best = paired(rows[best], rows[h], c_star) if abs(best - h) > 1e-12 else None
        test_live = paired(rows[h], rows[live], c_star)
        eras = {}
        for lab, _, _ in ERAS:
            vals = {b: rows[b]["eras"][lab]["net_sr"]["c_star"] for b in grid if rows[b]["eras"][lab]["net_sr"]["c_star"] is not None}
            if vals:
                eb = max(vals, key=vals.get)
                eras[lab] = {"argmax": eb, "side": "narrower" if eb < h else ("wider" if eb > h else "at h*"),
                             "net_at_h": rows[h]["eras"][lab]["net_sr"]["c_star"], "net_at_best": vals[eb],
                             "net_at_live": rows[live]["eras"][lab]["net_sr"]["c_star"],
                             "turn_at_h": rows[h]["eras"][lab]["turn"], "turn_at_live": rows[live]["eras"][lab]["turn"]}
        turn_gap = rows[h]["turn"] / rows[live]["turn"] - 1
        test_spec = paired(rows[spec_value], rows[live], c_star) if abs(spec_value - live) > 1e-12 else None
        say(f"    grid argmax of net@c*: {best * 100:.2f}% (NOT chosen; named so the draft can say so). "
            f"P1: best - h* = {p1:+.3f} ({'within' if p1 <= P1_TOL else 'OUTSIDE'} {P1_TOL}). "
            + (f"P2: argmax - h* {test_best['delta_annual']:+.3f}/yr, SE {test_best['se_annual']:.3f}, HAC p "
               f"{test_best['hac_p']:.3f}, boot p {test_best['boot_p']:.3f}" if test_best else "P2: h* is the argmax"))
        say(f"    h* - live at c*: {test_live['delta_annual']:+.3f}/yr (SE {test_live['se_annual']:.3f}, HAC p "
            f"{test_live['hac_p']:.3f}); turnover h* / live - 1 = {turn_gap:+.1%} "
            f"({'an H2 pair (within 5%)' if abs(turn_gap) <= 0.05 else 'NOT an H2 pair: priced at c instead'})")
        if test_spec:
            say(f"    spec value {spec_value * 100:.1f}% - live at c*: {test_spec['delta_annual']:+.3f}/yr (SE "
                f"{test_spec['se_annual']:.3f}, HAC p {test_spec['hac_p']:.3f}); turnover "
                f"{rows[spec_value]['turn'] / rows[live]['turn'] - 1:+.1%}")
            say(f"    PASS-RULE STATISTIC, spec value - live: net at c* {test_spec['net_diff_pp_yr']:+.4f}pp/yr, "
                f"Newey-West t (lag {NW_LAG}) {test_spec['nw_t_net']:.2f} (lag {NW_LAG_ALT}: "
                f"{test_spec['nw_t_net_lag63']:.2f}); gross {test_spec['gross_diff_pp_yr']:+.4f}pp/yr, NW t "
                f"{test_spec['nw_t_gross']:.2f}; against the bar sqrt(2 ln 56) = {math.sqrt(2 * math.log(56)):.3f}")
        for lab, e in eras.items():
            say(f"    {lab}: argmax {e['argmax'] * 100:.2f}% ({e['side']} than h*); net@c* at h* {e['net_at_h']:.3f}, "
                f"at live {e['net_at_live']:.3f}, at argmax {e['net_at_best']:.3f}; turn/yr h* {e['turn_at_h']:.1f}, "
                f"live {e['turn_at_live']:.1f}")
        out["basis"][basis] = {
            "rows": {f"{b:.5f}": {k: v for k, v in r.items() if not k.startswith("_")} for b, r in rows.items()},
            "argmax_c_star": best, "P1_best_minus_h": p1, "P1_on_plateau": bool(p1 <= P1_TOL),
            "P2_argmax_vs_h": test_best, "P2_on_plateau": (True if test_best is None else bool(test_best["hac_p"] >= 0.05)),
            "h_vs_live": test_live, "spec_value": spec_value, "spec_value_vs_live": test_spec,
            "turn_gap_spec_value_vs_live": rows[spec_value]["turn"] / rows[live]["turn"] - 1,
            "turn_gap_h_vs_live": turn_gap, "h2_pair": bool(abs(turn_gap) <= 0.05),
            "eras": eras, "model_change_h_vs_live": model_change(rows[h], rows[live], c_star, say),
            "model_change_spec_value_vs_live": model_change(rows[spec_value], rows[live], c_star, say, "spec value")}
    return out


# --------------------------------------------------------------------------- the books

def core(cut: Path, data_root: Path, costs: dict, say) -> dict:
    cdir = cut / "fitcut_cef"
    cdir.mkdir(parents=True, exist_ok=True)
    info = {}
    for name, col in (("cef_prices", "date"), ("cef_nav", "date"), ("cef_distributions", "ex_date"),
                      ("cef_splits", "ex_date")):
        src = data_root / "cef" / f"{name}.parquet"
        if not src.exists():
            raise FileNotFoundError(f"{src} is missing")
        d = pd.read_parquet(src, filters=[(col, "<=", FIT_END)])
        if len(d) and pd.to_datetime(d[col]).max() > FIT_END:
            raise AssertionError(f"{name}: the filtered read let a later row through")
        d.to_parquet(cdir / f"{name}.parquet", index=False)
        info[name] = {"rows": int(len(d)), "last": (str(pd.to_datetime(d[col]).max().date()) if len(d) else None)}
    bf.DATA_DIR = cdir
    T, R = bf.fit_only(*bf.build_targets())
    thin = bf.thin_sessions(T.index)
    Rtr = bf.total_returns(R)
    _assert_fit(T, R, Rtr)
    m, cap, live = float(S.SIZING_MULTIPLIER), float(S.MAX_GROSS_STRESS), float(S.BAND_WIDTH)
    say(f"\nCORE  spec {S.SPEC_ID}: m {m}, cap {cap}, band {live}; {len(S.UNIVERSE)} names; targets "
        f"{T.index[0].date()}..{T.index[-1].date()} ({len(T)} sessions, {int(thin.sum())} thin)")
    say(f"  fit-cut panels: {info}")
    inactive = thin.to_numpy()
    dyn = {"primary": dynamics(T, inactive), "either_nonzero": dynamics(T, inactive, nonzero="either"),
           "eras": {lab: dynamics(T, inactive, era=(a, b), flat_ok=True) for lab, a, b in ERAS}}
    U17 = list(S.UNIVERSE) + list(V6_EXTRA)
    T17, _ = bf.fit_only(*bf.build_targets(universe=U17))
    thin17 = bf.thin_sessions(T17.index, universe=U17)
    _assert_fit(T17)
    dyn["calibration_v6_17"] = dynamics(T17, thin17.to_numpy())
    # The DILUTED reading, for the calibration only: every name-day of every session, in the book or not,
    # thin or not. It brackets the original's sigma_w from below (the draft's section 3.3); it is not a
    # candidate input, because it counts days on which no target can move.
    A17 = T17.to_numpy(dtype=float)
    d17, p17, c17 = A17[1:] - A17[:-1], A17[:-1], A17[1:]
    phi17 = float((c17 * p17).sum() / (p17 ** 2).sum())
    dyn["calibration_v6_17_diluted"] = {"sigma_w": float(d17.std(ddof=1)), "phi_w": phi17,
                                        "kappa_w": -math.log(phi17), "name_days": int(d17.size)}
    k17 = dyn["calibration_v6_17"]
    dyn["calibration_v6_17"]["h_15bp"] = h_star(15.0, k17["sigma_w"], k17["kappa_w"])
    dyn["calibration_v6_17"]["h_22bp"] = h_star(22.0, k17["sigma_w"], k17["kappa_w"])
    th = thin.to_numpy()
    pre = T.index < W1
    dyn["thin_counts"] = {"fit_thin": int(th.sum()), "fit_sessions": int(len(th)),
                          "non_thin_before_w1": int((~th[pre]).sum()), "w1_sessions": int((~pre).sum()),
                          "w1_thin": int(th[~pre].sum())}
    p = dyn["primary"]
    c_star = costs["core_B_bp"]
    lo, hi = costs["core_B_ci95_day_mean_bp"]
    lo2, hi2 = costs["core_B_ci95_centred_on_pooled_bp"]
    hs = {"c_star": h_star(c_star, p["sigma_w"], p["kappa_w"]),
          "ci_lo": h_star(lo, p["sigma_w"], p["kappa_w"]), "ci_hi": h_star(hi, p["sigma_w"], p["kappa_w"]),
          "ci_centred": [lo2, hi2, h_star(lo2, p["sigma_w"], p["kappa_w"]), h_star(hi2, p["sigma_w"], p["kappa_w"])],
          **{f"{int(c)}bp": h_star(c, p["sigma_w"], p["kappa_w"]) for c in GRID_BP + (22.0,)},
          "c_star_account_reading_in_unit_weights": h_star(c_star, m * p["sigma_w"], p["kappa_w"]) / m,
          "c_star_either_nonzero": h_star(c_star, dyn["either_nonzero"]["sigma_w"], dyn["either_nonzero"]["kappa_w"]),
          "c_star_per_name_sd": h_star(c_star, p["sigma_w_per_name_mean"], p["kappa_w"]),
          "c_star_by_era": {lab: h_star(c_star, e["sigma_w"], e["kappa_w"]) for lab, e in dyn["eras"].items()
                            if not e.get("flat")},
          "c_star_original_inputs": h_star(c_star, ORIGINAL["sigma_w"], ORIGINAL["kappa_w"])}
    _say_dyn("core", dyn, say)
    _say_h("core", hs, c_star, (lo, hi), m, say)
    h = hs["c_star"]

    def build(b):
        return m * bf.band_gross_capped(T, b, cap / m, below_min_names="flatten", thin=thin)
    pl = plateau("core (x%.2f, flatten, cap %.2f/m)" % (m, cap), build,
                 {"total": lambda H: Rtr, "price-only": lambda H: R}, h, c_star, live, say)
    return {"spec_id": S.SPEC_ID, "m": m, "cap": cap, "live_band": live, "cut": info, "dynamics": dyn,
            "h_star": hs, "plateau": pl, "sessions": len(T), "thin": int(thin.sum())}


def c4book(cut: Path, data_root: Path, costs: dict, say) -> dict:
    fdir = cut / "fitcut_families"
    info = bm.cut_families(fdir, src_dir=data_root / "cef_families")
    spec = bm.load_spec()
    f = spec["frozen"]
    m, cap, live = float(f["sizing_multiplier"]), float(f["max_gross_stress"]), float(f["band_width"])
    T, _u = bm.trial_targets(fdir)
    TB = bm.spec_targets(fdir, T, spec)
    tb = bm.trial_book(fdir, T)                  # the gate: trial 52's committed fit Sharpes to 1e-9
    _assert_fit(T, TB, tb["R_raw"], tb["Rx_raw"])
    A = TB.to_numpy()
    same = np.zeros(len(A), dtype=bool)
    same[1:] = (A[1:] == A[:-1]).all(axis=1)
    nz = np.abs(A).sum(axis=1) > 0
    first = int(np.argmax(nz))
    inactive = same.copy()
    inactive[:first] = True                       # before the first book; the entry pair is a jump
    say(f"\nC4  spec {spec['spec_id']}: m {m}, cap {cap}, band {live}; {TB.shape[1]} names; the v5 blend "
        f"{TB.index[0].date()}..{TB.index[-1].date()}; first book {TB.index[first].date()}; "
        f"{int(same[first + 1:].sum())} hold rows after it; reproduction gate PASS (trial 52 fit SR "
        f"{tb['total_sr']:.6f} TR / {tb['price_sr']:.6f} PR)")
    dyn = {"primary": dynamics(TB, inactive), "either_nonzero": dynamics(TB, inactive, nonzero="either"),
           "eras": {lab: dynamics(TB, inactive, era=(a, b), flat_ok=True) for lab, a, b in ERAS}}
    p = dyn["primary"]
    c_c4, c_c4_med, c_core = costs["c4_B_bp"], costs["c4_B_bp_median_ratio"], costs["core_B_bp"]
    lo, hi = (x * costs["ratio_mean"] for x in costs["core_B_ci95_day_mean_bp"])
    hs = {"c_star": h_star(c_c4, p["sigma_w"], p["kappa_w"]),
          "median_ratio": h_star(c_c4_med, p["sigma_w"], p["kappa_w"]),
          "core_cost_unscaled": h_star(c_core, p["sigma_w"], p["kappa_w"]),
          "ci_lo": h_star(lo, p["sigma_w"], p["kappa_w"]), "ci_hi": h_star(hi, p["sigma_w"], p["kappa_w"]),
          **{f"{int(c)}bp": h_star(c, p["sigma_w"], p["kappa_w"]) for c in GRID_BP + (22.0,)},
          "c_star_account_reading_in_unit_weights": h_star(c_c4, m * p["sigma_w"], p["kappa_w"]) / m,
          "c_star_either_nonzero": h_star(c_c4, dyn["either_nonzero"]["sigma_w"], dyn["either_nonzero"]["kappa_w"]),
          "c_star_per_name_sd": h_star(c_c4, p["sigma_w_per_name_mean"], p["kappa_w"]),
          "c_star_by_era": {lab: h_star(c_c4, e["sigma_w"], e["kappa_w"]) for lab, e in dyn["eras"].items()
                            if not e.get("flat")}}
    _say_dyn("C4", dyn, say)
    _say_h("C4", hs, c_c4, (lo, hi), m, say)
    say(f"  C4 at the median spread ratio ({costs['ratio_median']:.3f} -> {c_c4_med:.2f}bp): h* "
        f"{hs['median_ratio'] * 100:.2f}%; at the core's unscaled {c_core:.2f}bp: {hs['core_cost_unscaled'] * 100:.2f}%")
    h = hs["c_star"]
    cols = TB.columns

    def build(b):
        return m * bf.band_gross_capped(TB, b, cap / m)

    def rets(key):
        return lambda H: c4.check_held(H, tb[key].reindex(columns=cols), f"C4 band book, {key}")
    pl = plateau("C4 (x%.2f, hold, cap %.2f/m, the v5 blend)" % (m, cap), build,
                 {"total (CRSP ret)": rets("R_raw"), "price-only (CRSP retx)": rets("Rx_raw")},
                 h, c_c4, live, say)
    return {"spec_id": spec["spec_id"], "m": m, "cap": cap, "live_band": live, "cut": info, "dynamics": dyn,
            "h_star": hs, "plateau": pl, "gate": {"total_sr": tb["total_sr"], "price_sr": tb["price_sr"]},
            "hold_rows": int(same[first + 1:].sum()), "first_book": str(TB.index[first].date())}


def _say_dyn(book, dyn, say):
    p = dyn["primary"]
    say(f"  {book} target dynamics (primary: active pairs, in the book both days, pooled): sigma_w "
        f"{p['sigma_w']:.5f}/day, phi_w {p['phi_w']:.5f}, kappa_w {p['kappa_w']:.5f}, half-life "
        f"{p['half_life']:.1f}d; {p['active_pairs']} active pairs, {p['name_days']} name-days, "
        f"{p['first_pair']}..{p['last_pair']}; mean |w| {p['mean_abs_w']:.4f}")
    e = dyn["either_nonzero"]
    say(f"    sensitivity: either-day non-zero sigma_w {e['sigma_w']:.5f}, phi_w {e['phi_w']:.5f}; per-name mean "
        f"sd {p['sigma_w_per_name_mean']:.5f}")
    for lab, x in dyn["eras"].items():
        if x.get("flat"):
            say(f"    {lab}: FLAT ({x['active_pairs']} active pairs, {x['name_days']} name-days); not measured")
            continue
        say(f"    {lab}: sigma_w {x['sigma_w']:.5f}, phi_w {x['phi_w']:.5f}, half-life {x['half_life']:.1f}d, "
            f"{x['active_pairs']} pairs")
    if "calibration_v6_17" in dyn:
        k = dyn["calibration_v6_17"]
        say(f"    CALIBRATION, the 17-name v6 book on the FIT only: sigma_w {k['sigma_w']:.5f}, phi_w {k['phi_w']:.5f}, "
            f"half-life {k['half_life']:.1f}d; the law at 15bp {k['h_15bp'] * 100:.2f}%, at 22bp {k['h_22bp'] * 100:.2f}%. "
            f"The 2026-09-06 inputs (17 names, whole sample to 2026-09, script not preserved) [S]: sigma_w "
            f"{ORIGINAL['sigma_w']}, phi_w {ORIGINAL['phi_w']}, half-life {ORIGINAL['half_life']}d")
        k = dyn["calibration_v6_17_diluted"]
        say(f"    the same 17 names, DILUTED (every name-day of every session): sigma_w {k['sigma_w']:.5f}, phi_w "
            f"{k['phi_w']:.5f} ({k['name_days']} name-days); not a candidate input")
    if "thin_counts" in dyn:
        k = dyn["thin_counts"]
        say(f"    thin sessions: {k['fit_thin']} of {k['fit_sessions']} on the fit; {k['non_thin_before_w1']} non-thin "
            f"session(s) before W1; W1 {k['w1_thin']} thin of {k['w1_sessions']}")


def _say_h(book, hs, c, ci, m, say):
    say(f"  {book} DERIVED h* = (3 c sigma_w^2 / 2 kappa_w)^(1/3), unit weights (the spec key's units):")
    say(f"    at c* = {c:.2f}bp: {hs['c_star'] * 100:.2f}%   [95% interval of c {ci[0]:.2f}-{ci[1]:.2f}bp -> "
        f"{hs['ci_lo'] * 100:.2f}-{hs['ci_hi'] * 100:.2f}%]")
    if "ci_centred" in hs:
        a_, b_, ha, hb = hs["ci_centred"]
        say(f"    the same half-width centred on the pooled c* ({a_:.2f}-{b_:.2f}bp) -> {ha * 100:.2f}-{hb * 100:.2f}%")
    say(f"    grid: 5bp {hs['5bp'] * 100:.2f}%, 15bp {hs['15bp'] * 100:.2f}%, 30bp {hs['30bp'] * 100:.2f}%; "
        f"22bp (the 2026-09-06 mid-range) {hs['22bp'] * 100:.2f}%")
    say(f"    sensitivities at c*: account-weight reading (x{m}) {hs['c_star_account_reading_in_unit_weights'] * 100:.2f}%"
        f" in unit weights; either-day non-zero {hs['c_star_either_nonzero'] * 100:.2f}%; per-name sd "
        f"{hs['c_star_per_name_sd'] * 100:.2f}%; by era "
        + ", ".join(f"{k} {v * 100:.2f}%" for k, v in hs["c_star_by_era"].items()))
    if "c_star_original_inputs" in hs:
        say(f"    the 2026-09-06 inputs at c*: {hs['c_star_original_inputs'] * 100:.2f}% (the study's 'about 3.3%')")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True, help="a checkout's data/ directory, read only")
    ap.add_argument("--cut-dir", type=Path, required=True, help="a new folder OUTSIDE the repository")
    ap.add_argument("--cost-ref", default=COST_REF, help="the git ref holding the study's aggregates JSON")
    a = ap.parse_args()
    cut = _outside_repo(a.cut_dir)
    cut.mkdir(parents=True, exist_ok=True)
    data_root = a.data_root.resolve()
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    lines: list[str] = []

    def say(s=""):
        print(s, flush=True)
        lines.append(s)
    run = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    costs = read_costs(a.cost_ref)
    say(f"BAND WIDTH RE-DERIVED FROM THE MEASURED COST ({run}); code {head[:7]}"
        f"{' + uncommitted edits' if dirty else ''}; FIT ONLY (<= {FIT_END.date()}); zero trials")
    say(f"COST INPUTS, read from {COST_PATH} at {a.cost_ref[:7]} (H14):")
    say(f"  core paper B {costs['core_B_bp']:.2f}bp ({costs['core_orders']} orders, {costs['core_days']} days); "
        f"95% interval {costs['core_B_ci95_day_mean_bp'][0]:.2f}-{costs['core_B_ci95_day_mean_bp'][1]:.2f}bp "
        f"(day mean {costs['core_B_day_mean_bp']:.2f}, t {costs['core_B_day_t']:.2f}); quoted half-spread at send "
        f"{costs['core_QHS_bp']:.2f}bp")
    say(f"  quoted half-spread at {SEND_MINUTE} ET, mean over name-days: C4's traded names "
        f"{costs['spread_c4_mean_1552']:.2f}bp / core {costs['spread_core_mean_1552']:.2f}bp = ratio "
        f"{costs['ratio_mean']:.3f} -> C4 c = {costs['c4_B_bp']:.2f}bp; median ratio {costs['ratio_median']:.3f} -> "
        f"{costs['c4_B_bp_median_ratio']:.2f}bp")
    say(f"  C4's own fills: ONE session (the opening build), B {costs['c4_one_session']['B_bp']:.2f}bp, QHS "
        f"{costs['c4_one_session']['QHS_bp']:.2f}bp: not used (n = 1)")
    out = {"run_utc": run, "code_head": head, "uncommitted_edits": bool(dirty), "fit_end": str(FIT_END.date()),
           "costs": costs, "original": ORIGINAL,
           "definitions": {"p1_tol": P1_TOL, "sharpe_diff": {"block": SD_BLOCK, "M": SD_M, "seed": SD_SEED},
                           "frontier_points": FRONTIER_POINTS, "eras": ERAS, "w1": str(W1.date())}}
    out["core"] = core(cut, data_root, costs, say)
    out["c4"] = c4book(cut, data_root, costs, say)
    (HERE / f"band_cost_{STAMP}.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    (HERE / f"band_cost_{STAMP}.txt").write_text("\n".join(lines) + "\n")
    print(f"wrote {HERE.relative_to(REPO)}/band_cost_{STAMP}.{{json,txt}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
