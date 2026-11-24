"""Attacks on hold's extra return over flatten (report only, 2026-11-03).

ZERO TRIALS, NO SPEC CHANGE. `thin_days.py` found that the harness's HOLD rule
earned more than the live FLATTEN rule in the fit period (+1.71pp/yr, NW t 2.13)
and the same in the 2023 holdout. Three independent passes then attacked that
result: a review, a re-derivation and a beta-detector pass. Their scratch work
was not committed. This script re-runs on the canonical path every attack whose
answer the final report states as [V], so each of those figures has a committed
source:

  A. concentration by name: the gap with each universe name's own P&L taken
     out (attribution: H[d-2] x R[d] by name, which sums to the paired gap), and
     the books REBUILT on the universe without PHK, without PTY and without both
     (targets, thin set and books recomputed: a different, thinner book);
  B. concentration in days: the gap without its best and worst days;
  C. the thin stretches as the unit of inference (a stretch is one decision to
     keep a frozen book; days inside it are not independent): run-level t, an
     exact sign-flip p over all 2^n sign vectors, and frozen SHARES against the
     harness's frozen WEIGHTS (what the live `below_min_names: "hold"` key would
     hold);
  D. a random-name control: each stretch's frozen weights reassigned at random
     across the names that traded, 5,000 draws, seed declared below. The lagged
     books of thin_days.py (placebo L = 21..252) are the SAME strategy at an
     earlier date, so they test "is it this frozen book" and not "is it the
     signal's direction"; this control tests the second;
  E. the deflated bar and the power, from `scripts/research/inference.py`;
  F. borrow: the uniform fee that erases the gap; the IBKR fee panel where it
     exists (2021-09-13 onward); and later fee regimes applied to 2015-19 as a
     SENSITIVITY, not as history (borrow before 2021-09 is unmeasured);
  G. the Sharpe gap's stationary-bootstrap interval (the desk's draw);
  H. the two DEGENERATE sessions (found by the re-derivation): on 2020-03-18 and
     2025-04-07 every eligible z sat at the -4 clip, so the weights are 0/0.
     `build_targets` fills them with 0 and the band cuts every name to the edge;
     the live sleeve gets NaN gaps, `abs(nan) > band` is False, and it HOLDS
     every name under the reason "cef band hold: |gap|<=band", which is not
     true. Both rules are replayed with the sleeve's behaviour, and the sleeve
     itself is called (read-only) on both dates to confirm it;
  I. how close the live book sits to a thin session today (the rule still
     binds if the eligible count dips under min_names).

NOT RE-RUN HERE (quoted [S] in the report, from the beta-detector pass): the
factor regression on ETF returns and the hand-read of the event days' prints.

DECLARED BEFORE RUNNING: SEED 20261103; 5,000 random-name draws; the bootstrap's
mean block 21 sessions and 4,000 draws; trial counts N = 52 (main), 53 (the
release tag that records trial 53) and 54 (what a thin-rule trial would be).
The PHK / PTY leave-outs name the two largest fit-period contributors to the
gap, chosen BY that ranking; the full leave-one-name-out table is printed beside
them so the choice is visible. Leaving the top contributor out can only weaken
a result; it is an attack, never a selection.

    python3 results/backtests/thin-days-2026-11-03/attack.py     # about 1-2 min

Reads data/ only. Writes attack.log (gitignored) and attack.json beside this file.
Imports the live sleeve read-only for H (no network, no order code).
"""
import json
import sys
import warnings
from itertools import product
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]          # the worktree root
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import numpy as np                                    # noqa: E402
import pandas as pd                                   # noqa: E402

import thin_days as td                                # noqa: E402
from scripts.cef import band_frontier as bf           # noqa: E402
from scripts.cef.spec import (BAND_WIDTH, MAX_GROSS_STRESS, MIN_ADV_USD, MIN_NAMES,   # noqa: E402
                              UNIVERSE, spec)
from scripts.research.harness import HOLDOUT_START    # noqa: E402
from scripts.research.inference import (newey_west_t, p_clear_bar, read_result,   # noqa: E402
                                        stationary_bootstrap_indices, upper_bound_max_z)

SEED = 20261103
N_PERM = 5000
BOOT_BLOCK, BOOT_REPS = 21, 4000
N_TRIALS = (52, 53, 54)
P = 252
LOG, OUT = [], {}


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


def ann(x, n):
    """Sum over the selected days, per day of the window, annualised."""
    return float(x.sum() / n * P)


def nwt(x):
    x = np.asarray(x, dtype=float)
    return float(newey_west_t(x)) if (x != 0).any() else float("nan")


def runs_of(thin):
    """(first, last) positions of every run of consecutive thin decisions."""
    th, out, i = thin.to_numpy(), [], 0
    while i < len(th):
        if not th[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(th) and th[j + 1]:
            j += 1
        out.append((i, j))
        i = j + 1
    return out


def rule_kw(rule, thin):
    return {} if rule == "hold" else dict(below_min_names="flatten", thin=thin)


# --------------------------------------------------------------------------- A
def by_name(H, keep, Rt, d, W):
    Hh, Hf = H[("hold", "instant")], H[("flatten", "instant")]
    Dn = (Hh.loc[keep].shift(2).fillna(0.0) - Hf.loc[keep].shift(2).fillna(0.0)) * Rt   # first 2 rows: nothing held
    if not np.allclose(Dn.sum(axis=1).to_numpy(), d.to_numpy(), atol=1e-14):
        raise AssertionError("the name attribution does not sum to the paired gap")
    p("\n=== A1. hold minus flatten with each name's own P&L taken out (attribution; instant flips) ===")
    p("pp/yr of the window (NW t). 'none' is the full gap.")
    out = {}
    labs = [lab for lab, _, _ in W]
    p(f"{'left out':<10}" + "".join(f"{lab:>18}" for lab in labs))
    for drop in [[]] + [[t] for t in UNIVERSE] + [["PHK", "PTY"]]:
        cells = []
        for lab, a, b in W:
            X = Dn.loc[a:b]
            x = X.sum(axis=1) - (X[drop].sum(axis=1) if drop else 0.0)
            cells.append((float(x.mean() * P), nwt(x)))
        key = "+".join(drop) if drop else "none"
        out[key] = {lab: dict(pp=c[0], t=c[1]) for lab, c in zip(labs, cells)}
        p(f"{key:<10}" + "".join(f"{c[0] * 100:10.2f} ({c[1]:5.2f})" for c in cells))
    contrib = {lab: {t: float(Dn.loc[a:b][t].sum() / len(Dn.loc[a:b]) * P) for t in UNIVERSE} for lab, a, b in W}
    OUT["A1_attribution_leave_out"] = out
    OUT["A1_name_contribution"] = contrib
    fit = W[[w[0] for w in W].index("FIT <2023")]
    top = sorted(contrib[fit[0]].items(), key=lambda kv: -kv[1])[:4]
    p("largest fit contributors to the gap (pp/yr): " + ", ".join(f"{t} {v * 100:+.2f}" for t, v in top))
    return out


def rebuilt_without(dist_end, W):
    p("\n=== A2. books REBUILT on the universe without the name(s): targets, thin set and both books recomputed ===")
    p("(a smaller universe is thin more often, so this is a different book, not the same book minus a name)")
    out = {}
    for drop in (["PHK"], ["PTY"], ["PHK", "PTY"]):
        U = [u for u in UNIVERSE if u not in drop]
        T, R = bf.build_targets(universe=U)
        thin = bf.thin_sessions(T.index, universe=U)
        keep = T.index <= dist_end
        Rt = bf.total_returns(R.loc[keep])
        Hh = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)
        Hf = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS, **rule_kw("flatten", thin))
        ph, pf = bf.evaluate(Hh.loc[keep], Rt)["pnl"], bf.evaluate(Hf.loc[keep], Rt)["pnl"]
        dd = ph - pf
        key = "+".join(drop)
        row = dict(thin=int(thin.sum()), thin_fit=int(thin.loc[:HOLDOUT_START - pd.Timedelta(days=1)].sum()))
        for lab, a, b in W:
            x = dd.loc[a:b]
            row[lab] = dict(pp=float(x.mean() * P), t=nwt(x), hold=float(ph.loc[a:b].mean() * P),
                            flatten=float(pf.loc[a:b].mean() * P))
        out[key] = row
        p(f"without {key:<8} thin sessions {row['thin']} (fit {row['thin_fit']}): " + "  ".join(
            f"{lab} {row[lab]['pp'] * 100:+.2f} ({row[lab]['t']:+.2f}) [hold {row[lab]['hold'] * 100:.2f} / "
            f"flat {row[lab]['flatten'] * 100:.2f}]" for lab, _, _ in W))
    OUT["A2_rebuilt"] = out


# --------------------------------------------------------------------------- B
def by_day(d, W, k=10):
    p(f"\n=== B. the gap without its best and worst {k} days (instant flips) ===")
    out = {}
    for lab, a, b in W:
        if lab not in ("FIT <2023", "2015-19"):
            continue
        x = d.loc[a:b]
        s = x.sort_values(ascending=False)
        best, worst = s.head(k), s.tail(k)
        row = dict(total_pp=float(x.sum()), best_pp=float(best.sum()), worst_pp=float(worst.sum()),
                   without_best_pp=float(x.sum() - best.sum()),
                   t_without_best=nwt(x.drop(best.index)),
                   t_without_best_and_worst=nwt(x.drop(best.index).drop(worst.index)),
                   top=[(str(i.date()), float(v)) for i, v in best.items()])
        out[lab] = row
        p(f"{lab}: total {row['total_pp'] * 100:.2f}pp; best {k} days {row['best_pp'] * 100:.2f}pp, worst {k} "
          f"{row['worst_pp'] * 100:.2f}pp; without the best {k}: {row['without_best_pp'] * 100:.2f}pp "
          f"(t {row['t_without_best']:.2f}); without best and worst: t {row['t_without_best_and_worst']:.2f}")
        p("   best days: " + ", ".join(f"{dt} {v * 100:+.2f}" for dt, v in row["top"]))
    OUT["B_days"] = out


# --------------------------------------------------------------------------- C, D
def stretches(H, T, thin, keep, Rt, panel, fit_days):
    Hh = H[("hold", "instant")]
    idx = T.index
    held = Hh.loc[keep].shift(2).fillna(0.0)          # H1: decided t earns t+2; first 2 rows hold nothing
    pnl = (held * Rt).sum(axis=1)
    px = panel["px"].reindex(idx)[UNIVERSE]
    rows = []
    for i0, i1 in runs_of(thin):
        if idx[i0] >= HOLDOUT_START:
            continue
        gross = float(Hh.iloc[i0:i1 + 1].abs().sum(axis=1).mean())
        if gross == 0:
            continue                                  # a book that had never opened: nothing to attribute
        earn = idx[i0 + 2: i1 + 3]
        earn = earn[earn.isin(Rt.index) & (earn < HOLDOUT_START)]
        if not len(earn):
            continue
        W_run = held.loc[earn].to_numpy()
        R_run = Rt.loc[earn].to_numpy()
        # frozen SHARES from the first earning day: each name's value drifts with its own total return
        V, E, fs, gmax = W_run[0].copy(), 1.0, 0.0, float(np.abs(W_run[0]).sum())
        for r in R_run:
            x = float((V * r).sum())
            fs += x / E
            E += x
            V = V * (1 + r)
            gmax = max(gmax, float(np.abs(V).sum() / E))
        live = px.loc[earn[0]].notna().to_numpy()
        if not (np.abs(W_run[:, ~live]) == 0).all():
            raise AssertionError(f"run {idx[i0].date()}: a held name has no price on the run's first earning day")
        rows.append(dict(first=str(idx[i0].date()), last=str(idx[i1].date()), sessions=i1 - i0 + 1,
                         earn_days=len(earn), gross=gross, pnl=float(pnl.loc[earn].sum()), frozen_shares=fs,
                         max_gross_frozen_shares=gmax, live=live, W=W_run, R=R_run))
    x = np.array([r["pnl"] for r in rows])
    n = len(x)
    t_runs = float(x.mean() / x.std(ddof=1) * np.sqrt(n))
    # exact one-sided sign-flip p over all 2^n sign vectors (n is about 21: 2M vectors)
    if n > 24:
        raise AssertionError(f"{n} runs: the exact enumeration would be too large; use a sampled test")
    signs = ((np.arange(2 ** n)[:, None] >> np.arange(n)[None, :]) & 1).astype(np.int8) * 2 - 1
    sums = signs @ x
    p_flip = float((sums >= x.sum() - 1e-15).mean())
    srt = np.sort(x)[::-1]
    p("\n=== C. the thin stretches as the unit (hold instant; fit-period runs with a held book) ===")
    p(f"{'first':<12}{'last':<12}{'sessions':>9}{'earn':>6}{'gross':>7}{'P&L pp':>8}{'frozen shares pp':>17}{'max gross (shares)':>19}")
    for r in rows:
        p(f"{r['first']:<12}{r['last']:<12}{r['sessions']:9d}{r['earn_days']:6d}{r['gross']:7.3f}{r['pnl'] * 100:8.2f}"
          f"{r['frozen_shares'] * 100:17.2f}{r['max_gross_frozen_shares']:19.2f}")
    fs_tot = sum(r["frozen_shares"] for r in rows)
    out = dict(runs=n, sum_pp=float(x.sum()), mean_pp=float(x.mean()), t_runs=t_runs, positive=int((x > 0).sum()),
               p_signflip_exact=p_flip, largest=[float(v) for v in srt[:3]],
               without_largest_pp=float(x.sum() - srt[0]), frozen_shares_sum_pp=float(fs_tot),
               max_gross_frozen_shares=float(max(r["max_gross_frozen_shares"] for r in rows)),
               ann_thin=float(x.sum() / fit_days * P))
    p(f"runs {n}; thin-day P&L {x.sum() * 100:.2f}pp ({out['ann_thin'] * 100:.2f}%/yr of the fit window); "
      f"run-level t {t_runs:.2f}; positive {out['positive']}/{n}; exact sign-flip p (one-sided) {p_flip:.4f}")
    p(f"largest run {srt[0] * 100:.2f}pp ({srt[0] / x.sum() * 100:.0f}% of the total); without it {out['without_largest_pp'] * 100:.2f}pp")
    p(f"frozen SHARES (the live hold key) earn {fs_tot * 100:.2f}pp against the harness's frozen weights "
      f"{x.sum() * 100:.2f}pp; max gross under frozen shares {out['max_gross_frozen_shares']:.2f} (the cap is "
      f"{MAX_GROSS_STRESS}; the live hold key leaves it off)")
    OUT["C_stretches"] = dict(out, table=[{k: v for k, v in r.items() if k not in ("live", "W", "R")} for r in rows])

    # D. random-name control
    rng = np.random.default_rng(SEED)
    obs = float(sum((r["R"] * r["W"]).sum() for r in rows))
    sims = np.zeros(N_PERM)
    for r in rows:
        Wl, Rl = r["W"][:, r["live"]], r["R"][:, r["live"]]
        for k in range(N_PERM):
            perm = rng.permutation(Wl.shape[1])
            sims[k] += float((Rl * Wl[:, perm]).sum())
    oa, sa = obs / fit_days * P, sims / fit_days * P
    pv = float((sa >= oa).mean())
    p(f"\n=== D. random-name control: each run's held weights reassigned across its traded names, {N_PERM} draws, "
      f"seed {SEED} (fit window) ===")
    p(f"hold's thin-day P&L {oa * 100:.2f}%/yr; null mean {sa.mean() * 100:.2f}, sd {sa.std() * 100:.2f}, 95th pct "
      f"{np.percentile(sa, 95) * 100:.2f}; P(null >= hold) {pv:.4f}")
    OUT["D_random_names"] = dict(obs=oa, null_mean=float(sa.mean()), null_sd=float(sa.std()),
                                 null_p95=float(np.percentile(sa, 95)), p=pv, draws=N_PERM, seed=SEED)
    return out


# --------------------------------------------------------------------------- E
def bars(d, W, runs):
    fit = [w for w in W if w[0] == "FIT <2023"][0]
    x = d.loc[fit[1]:fit[2]]
    est, t_day = float(x.mean() * P), nwt(x)
    p("\n=== E. the deflated bar sqrt(2 ln N) and the power ===")
    out = dict(fit_pp=est, t_paired=t_day, t_runs=runs["t_runs"], runs=runs["runs"], by_N={})
    for N in N_TRIALS:
        bar = float(upper_bound_max_z(N))
        need = runs["runs"] * (bar / runs["t_runs"]) ** 2
        rr = read_result(est, est / t_day, est, n_trials=N)
        out["by_N"][N] = dict(bar=bar, p_clear_paired=float(p_clear_bar(t_day, bar)),
                              p_clear_runs=float(p_clear_bar(runs["t_runs"], bar)), runs_needed=float(need),
                              read=rr["outcome"], lo=float(rr["lo"]), hi=float(rr["hi"]),
                              power_at_observed=float(rr["power_at_meaningful"]))
        b = out["by_N"][N]
        p(f"N={N}: bar {bar:.3f}; paired t {t_day:.2f} and run t {runs['t_runs']:.2f} are "
          f"{'BELOW' if max(t_day, runs['t_runs']) < bar else 'AT OR ABOVE'} it; P(clear | true t = observed) "
          f"{b['p_clear_paired']:.2f} (paired) / {b['p_clear_runs']:.2f} (runs); runs needed at the observed per-run "
          f"effect {need:.0f} against {runs['runs']} in the fit period; read_result (meaningful = the observed "
          f"{est * 100:.2f}pp/yr, Sidak-adjusted) {b['read']} [{b['lo'] * 100:.2f}, {b['hi'] * 100:.2f}]pp/yr, power "
          f"{b['power_at_observed']:.2f}")
    OUT["E_bar"] = out


# --------------------------------------------------------------------------- F
def _asof_fee(fee, days, max_stale=5):
    """Each name's fee as of each day: the last panel row on or before it, at
    most `max_stale` sessions old (the panel's daily bars miss a few sessions).
    Older than that raises: a fee carried further would be a guess."""
    f = fee.reindex(fee.index.union(days)).sort_index()
    out = f.ffill().reindex(days)
    # rows since each name's last observation, on the union calendar
    pos = pd.Series(np.arange(len(f), dtype=float), index=f.index)
    last = f.notna().apply(lambda c: pos.where(c).ffill()).reindex(days)
    stale = pos.reindex(days).to_numpy()[:, None] - last.to_numpy()
    if np.isnan(stale).any() or (stale > max_stale).any():
        raise AssertionError("the fee panel lacks a value within "
                             f"{max_stale} sessions for some name-day; no fee is invented")
    return out, int((stale > 0).sum())


def borrow(H, keep, Rt, d, W, dist_end):
    Hh, Hf = H[("hold", "instant")], H[("flatten", "instant")]
    sh = Hh.loc[keep].clip(upper=0).abs().shift(2).fillna(0.0)    # held short weight, earning-day aligned
    sf = Hf.loc[keep].clip(upper=0).abs().shift(2).fillna(0.0)
    xs = sh - sf
    p("\n=== F. borrow on the shorts hold carries and flatten does not (no borrow is in any other figure) ===")
    out = dict(breakeven={})
    for lab, a, b in W:
        if lab not in ("FIT <2023", "2015-19", "2010-14"):
            continue
        gap, ex = float(d.loc[a:b].mean() * P), float(xs.loc[a:b].sum(axis=1).mean())
        out["breakeven"][lab] = dict(gap=gap, extra_short=ex, fee=gap / ex if ex > 0 else float("nan"))
        p(f"{lab}: gap {gap * 100:.2f}pp/yr; mean extra short weight {ex:.3f}; the uniform fee that erases the gap "
          f"{gap / ex * 100:.1f}%/yr")
    bn = xs.loc["2015":"2019"].mean()
    out["extra_short_2015_19"] = {t: float(v) for t, v in bn.items() if abs(v) > 0.005}
    p("2015-19 mean extra short weight by name: " + ", ".join(f"{t} {v:.3f}" for t, v in bn.items() if abs(v) > 0.005))

    bh = pd.read_parquet(bf.DATA_DIR / "cef_borrow_history.parquet")
    bh["date"] = pd.to_datetime(bh["date"])
    fee = bh.pivot_table(index="date", columns="ticker", values="fee_rate_pct")
    missing = [t for t in UNIVERSE if t not in fee.columns]
    if missing:
        raise AssertionError(f"the IBKR fee panel has no column for {missing}")
    fee = fee[UNIVERSE]
    p(f"IBKR FEE_RATE panel {fee.index.min().date()}..{fee.index.max().date()} (data/cef/cef_borrow_history.parquet; "
      "docs/REFERENCES.md: no independent source for levels before 2026-09)")
    measured = {}
    for lab, a, b in (("2021-09-13..2022-12-30", fee.index.min(), pd.Timestamp("2022-12-30")),
                      ("2023-01-03..DIST_END", HOLDOUT_START, min(dist_end, fee.index.max()))):
        days = Rt.loc[a:b].index
        f, n_stale = _asof_fee(fee, days)
        ch = float((sh.loc[days] * f / 100).sum(axis=1).mean())
        cf = float((sf.loc[days] * f / 100).sum(axis=1).mean())
        gap = float(d.loc[days].mean() * P)
        measured[lab] = dict(hold=ch, flatten=cf, extra=ch - cf, gap=gap, net=gap - (ch - cf), stale_name_days=n_stale)
        p(f"{lab}: borrow on short weight, simple annual rate: hold {ch * 100:.2f}%/yr, flatten {cf * 100:.2f}%/yr, "
          f"extra {(ch - cf) * 100:.2f}%/yr; gap {gap * 100:+.2f}pp/yr gross, {(gap - ch + cf) * 100:+.2f} net "
          f"(name-days on a fee up to 5 sessions old: {n_stale})")
    out["measured"] = measured

    snap = pd.read_csv(bf.DATA_DIR / "cef_borrow.csv")
    sd_ = snap["date"].max()
    s = snap[snap.date == sd_].set_index("ticker")["fee_rate_pct"]
    if s.index.duplicated().any() or set(UNIVERSE) - set(s.index):
        raise AssertionError(f"the borrow snapshot of {sd_} lacks or repeats a universe name")
    regimes = {"IBKR mean 2021-09-13..2022-12-30": fee.loc[:"2022-12-30"].mean(),
               "IBKR mean 2023-01-03..panel end": fee.loc[HOLDOUT_START:].mean(),
               f"snapshot {sd_} (cef_borrow.csv)": s.reindex(UNIVERSE)}
    p("SENSITIVITY, NOT HISTORY: a later fee regime applied to an earlier period (borrow before 2021-09 is unmeasured)")
    sens = {}
    for lab, a, b in W:
        if lab not in ("2015-19", "FIT <2023"):
            continue
        gap = float(d.loc[a:b].mean() * P)
        for k, f in regimes.items():
            if f.isna().any():
                raise AssertionError(f"fee missing for {list(f.index[f.isna()])} in {k}")
            cost = float((xs.loc[a:b] * f / 100).sum(axis=1).mean())
            sens[f"{lab} | {k}"] = dict(gap=gap, extra_cost=cost, net=gap - cost)
            p(f"{lab}: gap {gap * 100:.2f}pp/yr gross; extra borrow at '{k}' {cost * 100:.2f}%/yr -> net {(gap - cost) * 100:+.2f}")
    out["sensitivity"] = sens
    out["fee_means"] = {k: {t: float(v) for t, v in f.items()} for k, f in regimes.items()}
    p("fee means %/yr, PHK / PTY: " + "; ".join(f"{k}: {f['PHK']:.1f} / {f['PTY']:.1f}" for k, f in regimes.items()))
    OUT["F_borrow"] = out


# --------------------------------------------------------------------------- G
def sharpe_gap(H, res, W):
    ph, pf = res[("hold", "instant")]["pnl"], res[("flatten", "instant")]["pnl"]
    held_any = (H[("hold", "instant")].abs().sum(axis=1) + H[("flatten", "instant")].abs().sum(axis=1)) > 0
    first = held_any.idxmax()
    first_earn = ph.index[ph.index.get_loc(first) + 2]
    p(f"\n=== G. Sharpe gap flatten minus hold, stationary bootstrap (mean block {BOOT_BLOCK}, {BOOT_REPS} draws, "
      f"seed {SEED}; instant flips) ===")
    p(f"(the fit window starts at the first earning day of either book, {first_earn.date()}: before it both are flat)")
    sr = lambda v: v.mean() / v.std() * np.sqrt(P)                    # noqa: E731
    out = {}
    for lab, a, b in W:
        if lab not in ("2020-22", "H13 2023+", "FIT <2023"):
            continue
        a = max(a, first_earn)
        A, B = ph.loc[a:b].to_numpy(), pf.loc[a:b].to_numpy()
        diffs = []
        for ii in stationary_bootstrap_indices(len(A), BOOT_BLOCK, BOOT_REPS, seed=SEED):
            for row in ii:
                diffs.append(sr(B[row]) - sr(A[row]))
        diffs = np.array(diffs)
        out[lab] = dict(start=str(a.date()), gap=float(sr(B) - sr(A)), lo=float(np.percentile(diffs, 2.5)),
                        hi=float(np.percentile(diffs, 97.5)), p_le0=float((diffs <= 0).mean()))
        p(f"{lab} from {a.date()}: SR flatten - hold {out[lab]['gap']:+.2f}; 95% interval [{out[lab]['lo']:+.2f}, "
          f"{out[lab]['hi']:+.2f}]; share of draws <= 0 {out[lab]['p_le0']:.3f}")
    a, b = pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31")
    inv = (H[("flatten", "instant")].abs().sum(axis=1).shift(2).reindex(pf.index).fillna(0.0) > 0).loc[a:b]
    out["2020-22 invested days"] = dict(days=int(inv.sum()), sr_flatten=float(sr(pf.loc[a:b][inv])),
                                        sr_hold=float(sr(ph.loc[a:b][inv])))
    p(f"2020-22 on the {int(inv.sum())} earning days flatten held a book: SR flatten "
      f"{out['2020-22 invested days']['sr_flatten']:.2f}, hold {out['2020-22 invested days']['sr_hold']:.2f}")
    OUT["G_sharpe"] = out


# --------------------------------------------------------------------------- H
def degenerate(T, thin, panel, keep, Rt, W):
    nz = T.abs().sum(axis=1) > 0
    started = nz.cumsum() > 0
    deg = T.index[~thin & ~nz & started]
    z, adv = panel["z"].reindex(T.index), panel["adv"].reindex(T.index)
    p("\n=== H. degenerate sessions: active (not thin), yet build_targets' row is all zero ===")
    info = {}
    for dt in deg:
        el = z.loc[dt][(z.loc[dt].notna()) & (adv.loc[dt] >= MIN_ADV_USD)]
        info[str(dt.date())] = dict(eligible=int(len(el)), z_values=sorted(set(float(v) for v in el.round(6))))
        p(f"{dt.date()}: {len(el)} eligible names, their z-scores {info[str(dt.date())]['z_values']}")
        i = T.index.get_loc(dt)
        if i + 1 < len(T) and thin.iloc[i + 1]:
            raise AssertionError(f"{dt.date()} is followed by a thin session; the replay below would change "
                                 "what build_targets holds there")
    out = dict(dates=info, books={})
    for rule, flips in product(("hold", "flatten"), ("instant", "deferred")):
        kw = dict(rule_kw(rule, thin), defer_flips=(flips == "deferred"))
        h0 = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS, **kw)
        T2, h = T.copy(), h0
        for dt in deg:                                 # in date order: each replay sees the earlier ones
            i = T.index.get_loc(dt)
            T2.iloc[i] = h.iloc[i - 1].to_numpy()      # a zero gap: the band holds every name, as the sleeve does
            h = bf.band_gross_capped(T2, BAND_WIDTH, MAX_GROSS_STRESS, **kw)
            if not np.array_equal(h.iloc[i].to_numpy(), h.iloc[i - 1].to_numpy()):
                raise AssertionError(f"the replay did not hold the book on {dt.date()}")
        r0, r1 = bf.evaluate(h0.loc[keep], Rt)["pnl"], bf.evaluate(h.loc[keep], Rt)["pnl"]
        row = {lab: dict(harness=float(r0.loc[a:b].mean() * P), sleeve=float(r1.loc[a:b].mean() * P))
               for lab, a, b in W}
        row["turn_on_dates"] = float(h0.diff().abs().sum(axis=1).loc[deg].sum())
        out["books"][f"{rule}/{flips}"] = row
        out.setdefault("_pnl", {})[f"{rule}/{flips}"] = r1
        out.setdefault("_held", {})[f"{rule}/{flips}"] = h
        p(f"{rule:<8}{flips:<9} harness trades {row['turn_on_dates']:.2f} gross on these dates; ann % harness -> "
          f"sleeve: " + "  ".join(f"{lab} {row[lab]['harness'] * 100:.2f}->{row[lab]['sleeve'] * 100:.2f}"
                                  for lab, _, _ in W))
    g = {}
    for flips in ("instant", "deferred"):
        dd = out["_pnl"][f"hold/{flips}"] - out["_pnl"][f"flatten/{flips}"]
        g[flips] = {lab: dict(pp=float(dd.loc[a:b].mean() * P), t=nwt(dd.loc[a:b])) for lab, a, b in W}
        p(f"hold minus flatten ({flips}) with the sleeve's behaviour on these dates: " + "  ".join(
            f"{lab} {g[flips][lab]['pp'] * 100:+.2f} ({g[flips][lab]['t']:+.2f})" for lab, _, _ in W))
    out["gap_sleeve_replay"] = g

    # the live sleeve itself, read-only, on both dates: holdings = the replayed flatten book of the day before
    from src.deploy.sleeve import FLAT, MarketState
    from src.deploy.sleeves.cef_discount import CEFDiscountSleeve
    sl = CEFDiscountSleeve(spec(), 1.0)
    px = panel["px"]
    hf = out["_held"]["flatten/instant"]
    conf = {}
    for dt in deg:
        prev = hf.iloc[T.index.get_loc(dt) - 1]
        holds = {t: float(prev[t] / px.loc[dt, t]) for t in T.columns if prev[t] != 0}
        tg = sl.target_positions(dt, MarketState(asof=dt, prices=pd.DataFrame(), holdings=holds,
                                                 extras={"sleeve_nav": 1.0}))
        by = {t.instrument: t for t in tg}
        for tk, q in holds.items():
            t = by[tk]
            if not (t.reason.startswith("cef band hold") and t.qty == q):
                raise AssertionError(f"{dt.date()} {tk}: the sleeve did not hold ({t.side}, {t.qty}, {t.reason!r})")
        others = [t for tk, t in by.items() if tk not in holds and t.side != FLAT]
        if others:
            raise AssertionError(f"{dt.date()}: the sleeve opened {[t.instrument for t in others]}")
        conf[str(dt.date())] = dict(held=len(holds), reason=by[next(iter(holds))].reason)
        p(f"the live sleeve on {dt.date()} (read-only call, the day-before book as holdings): every one of "
          f"{len(holds)} held names held, e.g. reason {conf[str(dt.date())]['reason']!r}")
    out["sleeve_check"] = conf
    out.pop("_pnl")
    out.pop("_held")
    OUT["H_degenerate"] = out


# --------------------------------------------------------------------------- I
def nearness(T, thin, panel):
    z, adv = panel["z"].reindex(T.index)[UNIVERSE], panel["adv"].reindex(T.index)[UNIVERSE]
    cnt = (z.notna() & (adv >= MIN_ADV_USD)).sum(axis=1)
    last_thin = thin[thin].index.max()
    after = cnt.loc[last_thin + pd.Timedelta(days=1):]
    at = after[after == MIN_NAMES]
    lastd = cnt.index[-1]
    below = adv.loc[lastd][adv.loc[lastd] < MIN_ADV_USD]
    out = dict(last_thin=str(last_thin.date()), sessions_at_min=int(len(at)),
               first_at_min=str(at.index.min().date()) if len(at) else None,
               last_at_min=str(at.index.max().date()) if len(at) else None,
               min_since=int(after.min()), last_date=str(lastd.date()), eligible_last=int(cnt.iloc[-1]),
               below_floor_last={t: float(v) for t, v in below.items()},
               by_year={str(y): dict(min=int(g.min()), median=float(g.median()), at_min=int((g == MIN_NAMES).sum()))
                        for y, g in after.groupby(after.index.year)})
    p(f"\n=== I. how close the book sits to a thin session (min_names {MIN_NAMES}) ===")
    p(f"last thin session {out['last_thin']}; since then the eligible count sat at exactly {MIN_NAMES} on "
      f"{out['sessions_at_min']} sessions ({out['first_at_min']}..{out['last_at_min']}); its minimum since then "
      f"{out['min_since']}")
    p("by year (min / median / sessions at min_names): " + "; ".join(
        f"{y} {v['min']} / {v['median']:.0f} / {v['at_min']}" for y, v in out["by_year"].items()))
    p(f"on {out['last_date']} (last panel date): {out['eligible_last']} of {len(UNIVERSE)} eligible; under the "
      f"${MIN_ADV_USD / 1e6:.0f}m floor: " + ", ".join(f"{t} ${v / 1e6:.2f}m" for t, v in below.items()))
    OUT["I_nearness"] = out


def main():
    T, R, thin, panel, dist_end, keep, Rt = td.load()
    H = td.books(T, thin)
    res = {k: bf.evaluate(h.loc[keep], Rt) for k, h in H.items()}
    d = res[("hold", "instant")]["pnl"] - res[("flatten", "instant")]["pnl"]
    W = [w for w in td.windows(dist_end) if w[0] in ("2010-14", "2015-19", "2020-22", "FIT <2023", "H13 2023+")]
    fit = [w for w in W if w[0] == "FIT <2023"][0]
    fit_days = len(Rt.loc[fit[1]:fit[2]])
    p(f"attack.py: panels to {panel['px'].index.max().date()}, returns cut at DIST_END {dist_end.date()}; "
      f"hold - flatten FIT {d.loc[fit[1]:fit[2]].mean() * P * 100:+.2f}pp/yr (t {nwt(d.loc[fit[1]:fit[2]]):.2f})")
    by_name(H, keep, Rt, d, W)
    rebuilt_without(dist_end, W)
    by_day(d, W)
    runs = stretches(H, T, thin, keep, Rt, panel, fit_days)
    bars(d, W, runs)
    borrow(H, keep, Rt, d, W, dist_end)
    sharpe_gap(H, res, W)
    degenerate(T, thin, panel, keep, Rt, W)
    nearness(T, thin, panel)
    (HERE / "attack.log").write_text("\n".join(LOG) + "\n")
    (HERE / "attack.json").write_text(json.dumps(OUT, indent=1, default=str))


if __name__ == "__main__":
    main()
