"""The XASSET order of evaluation (PREREG §1.11), one pipeline for X1-X4.

Each trial script (`scripts/xasset/x<k>_*.py`) declares a `Spec`: its instruments,
its declared first decision and window length, how to build the RAW sleeve, its
named control (stage 2), whether shift(3) decides, its D4 regressions, its AQR
factors and its reported extras. This module runs the stages in the declared
order, on the declared series, and writes one verdict file per stage-set:

    python3 scripts/xasset/x1_credit_trend.py --trial 1          # fit stages 0b-6
    python3 scripts/xasset/x1_credit_trend.py --holdout          # stage 7 (and 8), once

GUARDS (each raises; none is a default)
---------------------------------------
* Stage 0b refuses to start unless the frozen spec still matches the approval
  pins, every Stage 0a input re-hashes to the manifest, and the XASSET counter
  in the COMMITTED docs/RESEARCH_STATE.md has already moved to this test's trial
  number (§0.2 item 3: the counter moves in a commit before 0b computes
  anything).
* The declared first decision and the declared P&L-session count T (PREREG §2.2
  Table A) must equal what the panel gives; a difference is a question, not a
  re-specification.
* The holdout refuses to open unless all four fit verdicts are committed
  (UNRUN counts), opens at most once per test, and asserts that the fit rows of
  the one continuous P&L equal the fit stage's P&L exactly.

WHAT DECIDES (revision 3): the SIZED, UNCAPPED sleeve, on the fit P&L window
(first decision + 2 sessions to 2022-12-30). The tradable (capped) sleeve is
reported beside every stage. Never `evaluate()['gross_sr']`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist
from typing import Callable

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.xasset import protocol as P  # noqa: E402

RUN_DATE = "2026-10-14"
TESTS = ("X1", "X2", "X3", "X4")


@dataclass
class Spec:
    key: str
    title: str
    names: list
    first_dec: str
    T_declared: int
    build: Callable            # (Rx, R, rf, source) -> raw H, rows from first_dec
    control: Callable          # (ctx) -> dict(pass_, rule, ...)
    control_kill: str          # verdict code if stage 2 fails
    shift3_decides: bool
    d4: list                   # [(label, [factors], start or None)]
    aqr: list
    extras: Callable = None    # (ctx) -> dict, reported only
    holdout_extras: Callable = None
    preflight: Callable = None  # (data) -> dict, zero-trial date/coverage checks of the test's own
    notes: list = field(default_factory=list)


# ----------------------------------------------------------------------------- paths
# The verdicts live in P.TRIALS (results/xasset/trials/, since 2026-10-22). These
# three paths ARE the run-once guards: `refuse_rerun`, `counter_guard` and
# `holdout_guard` decide that a trial is spent by finding its file here.
def fit_json(key: str) -> Path:
    return P.TRIALS / f"{key.lower()}_fit_{RUN_DATE}.json"


def holdout_json(key: str) -> Path:
    return P.TRIALS / f"{key.lower()}_holdout_{RUN_DATE}.json"


def unrun_json(key: str) -> Path:
    return P.TRIALS / f"{key.lower()}_unrun_{RUN_DATE}.json"


def fit_cache(key: str) -> Path:
    return P.CACHE / f"{key.lower()}_fit_series.parquet"


# ----------------------------------------------------------------------------- guards
def counter_value() -> int:
    """XASSET trials used, from the COMMITTED counter table (HEAD), never the
    working copy: the counter must move in a commit before 0b computes."""
    txt = subprocess.run(["git", "show", "HEAD:docs/RESEARCH_STATE.md"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    m = re.search(r"^\| \*\*XASSET\*\* \|.*\| \*\*(\d+)\*\* \|\s*$", txt, re.M)
    if not m:
        raise P.ProtocolError("no bold XASSET row in the committed counter table")
    return int(m.group(1))


def counter_guard(trial: int):
    dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "docs/RESEARCH_STATE.md"],
                           cwd=REPO).returncode
    if dirty:
        raise P.ProtocolError("docs/RESEARCH_STATE.md has uncommitted changes; commit the counter first")
    v = counter_value()
    if v < trial:
        raise P.ProtocolError(f"XASSET counter at HEAD is {v}; this run is trial {trial}. Move the "
                              f"counter in a commit BEFORE Stage 0b (PREREG §0.2 item 3).")
    taken = [k for k in TESTS if fit_json(k).exists() and json.loads(fit_json(k).read_text())
             .get("trial") == trial]
    if taken:
        raise P.ProtocolError(f"trial number {trial} is already recorded by {taken}")


def load(end: pd.Timestamp):
    """The primary panel truncated at `end` (fit: before 2023-01-01; holdout: 2026-09-30)."""
    panel = P.load_panel()
    R_full, cal_full = P.returns(panel)
    rf_full = P.risk_free(cal_full)
    keep = cal_full[cal_full <= end] if end != P.HOLDOUT_START else cal_full[cal_full < end]
    R = R_full.reindex(keep)
    rf = rf_full.reindex(keep)
    return panel, R, rf, P.excess(R, rf), keep


def inhouse_R(cal: pd.DatetimeIndex) -> pd.DataFrame:
    frames = {k: pd.read_parquet(v, columns=["date", "ticker", "ret_total"]) for k, v in P.INHOUSE.items()}
    out = {}
    for sym in P.SLATE_19:
        for k in ("etf_panel", "etf_ohlc_extended"):
            d = frames[k]
            s = d.loc[d.ticker == sym].assign(date=lambda x: pd.to_datetime(x.date)).set_index("date")["ret_total"].dropna()
            if len(s):
                out[sym] = s
                break
    return pd.DataFrame(out).reindex(cal)


# ----------------------------------------------------------------------------- stages
def d4_regressions(spec: Spec, pnl: pd.Series, F: pd.DataFrame, window: pd.DatetimeIndex) -> list:
    out = []
    for label, facs, start in spec.d4:
        first = max([window[0]] + [F[f].first_valid_index() for f in facs]
                    + ([pd.Timestamp(start)] if start else []))
        y = pnl.loc[first:window[-1]]
        r = P.ols_hac(y, F[facs], P.NW_LAGS, 252)
        r.update(label=label, factors=facs, declared_start=start)
        r["verdict"] = P.d4_verdict(r)
        out.append(r)
    return out


def r_q(pnl: pd.Series, names: list, flags: pd.DataFrame) -> dict:
    F = flags[flags.ticker.isin(names) & flags.check.isin(["Q2", "Q3", "Q4", "Q5", "Q6", "Q7"])]
    bad = set(F.date)
    x = pnl[~pnl.index.isin(bad)]
    return dict(excluded_sessions=int(len(pnl) - len(x)), sharpe=P.sharpe(x), nw_t21=P.nw_t(x))


def preflight(spec: Spec, data: dict) -> dict:
    """ZERO-TRIAL checks that depend only on dates and on WHERE data exist, run
    before the counter is checked and before anything is built (the review of
    2026-10-14: a halt after stage 1 has printed would spend the trial, show the
    headline, and leave no verdict).

    * the declared breadth rule, applied to the panel's first returns, gives the
      declared first decision (and the month-end before it does not qualify);
    * the P&L window has the declared T;
    * every D4 factor and the French daily file cover their regression windows,
      and the AQR factors named cover every month of the window (NaN masks only);
    * the placebo would not move a position onto a date with no return, unless
      the team lead has ruled on that case (open question 2);
    * the test's own checks (`spec.preflight`)."""
    from scripts.xasset import slate_feasibility as sf
    R, cal = data["R"], data["cal"]
    names, lag, rule = sf.TESTS[spec.key]
    firsts = {c: (R[c].first_valid_index().date() if R[c].notna().any() else None) for c in R.columns}
    need_names = list(dict.fromkeys(names))
    if any(firsts.get(n) is None for n in need_names):
        raise P.ProtocolError(f"{spec.key}: no returns for {[n for n in need_names if firsts.get(n) is None]}")
    fd, _, need = sf.fit_window(need_names, lag, rule, firsts, cal)
    if str(fd) != spec.first_dec:
        raise P.ProtocolError(f"{spec.key}: the breadth rule gives a first decision of {fd}; declared "
                              f"{spec.first_dec}. Halt: a question, not a re-specification.")
    first_dec = pd.Timestamp(spec.first_dec)
    window = P.pnl_window(first_dec, cal)
    if len(window) != spec.T_declared:
        raise P.ProtocolError(f"{spec.key}: P&L window has {len(window)} sessions; PREREG Table A "
                              f"declares {spec.T_declared}. Halt: a question, not a re-specification.")
    # factor coverage from the COMPONENTS' missing-value masks: no return is combined here
    present = {f: R[a].notna() & (R[b].notna() if b else data["rf"].notna())
               for f, (a, b) in P.FACTOR_NAMES.items()}
    for label, facs, start in spec.d4:
        first = max([window[0]] + [present[f].idxmax() for f in facs]
                    + ([pd.Timestamp(start)] if start else []))
        gap = [f for f in facs if not present[f].loc[first:window[-1]].all()]
        if gap:
            raise P.ProtocolError(f"{spec.key} {label}: factors {gap} have gaps in the window")
    if "ff_dates" in data:
        miss = window[~window.isin(data["ff_dates"])]
        if len(miss):
            raise P.ProtocolError(f"French daily factors miss {len(miss)} window sessions, e.g. {list(miss[:3])}")
    if "aqr_months" in data:
        months = pd.period_range(window[0], window[-1], freq="M")
        for c in spec.aqr:
            have = data["aqr_months"].get(c, set())
            miss = [m for m in months[1:-1] if m not in have]
            if miss:
                raise P.ProtocolError(f"AQR {c} misses {len(miss)} months of the window, e.g. {miss[:3]}")
    late = [n for n in spec.names if pd.Timestamp(firsts[n]) > window[0]]
    if late and P.PLACEBO_PRE_INCEPTION_RULE is None:
        raise P.ProtocolError(
            f"{spec.key}: the block-shuffled placebo would move positions in {late} onto dates before "
            f"their first return (first P&L {window[0].date()}). PREREG §1.8 does not say what such a "
            f"position earns: open question 2 to the team lead (results/xasset/XASSET_RESULTS_2026-10-14.md). "
            f"Stage 0b does not start.")
    out = dict(first_decision=str(fd), T=len(window), late_names=late,
               placebo_span_start=str(max(pd.Timestamp(firsts[n]) for n in spec.names).date()))
    if spec.preflight:
        out.update(spec.preflight(data))
    return out


def preflight_data() -> dict:
    """The fit panel and the date/NaN masks the preflight needs (no P&L)."""
    panel, R, rf, Rx, cal = load(P.HOLDOUT_START)
    ff = pd.read_parquet(P.FF_DAILY, columns=["date"])
    ts = pd.read_parquet(P.AQR_TSMOM)
    vm = pd.read_parquet(P.AQR_VME)
    months = {}
    for df, cols, pre in ((ts, [c for c in ts.columns if c.startswith("TSMOM")], ""),
                          (vm, ["MOM", "MOMLS_VME_FI"], "VME_")):
        for c in cols:
            months[pre + c] = set(df.loc[df[c].notna(), "date"].dt.to_period("M"))
    return dict(panel=panel, R=R, rf=rf, Rx=Rx, cal=cal, ff_dates=pd.DatetimeIndex(pd.to_datetime(ff["date"])),
                aqr_months=months)


def refuse_rerun(spec: Spec):
    if fit_json(spec.key).exists() or P.git_tracked(fit_json(spec.key)):
        raise P.ProtocolError(f"{spec.key} already has a fit verdict ({P.rel(fit_json(spec.key))}); "
                              f"a test is run once")


def fit(spec: Spec, trial: int) -> dict:
    """The guarded entry point: pins, hashes, the zero-trial preflight and the
    counter; then stages 0b-5 (written at once); then the reported rows."""
    t0 = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    pin = P.check_spec_pin()
    man = P.verify_inputs()
    refuse_rerun(spec)
    data = preflight_data()
    pf = preflight(spec, data)
    if P.DG1_RULING is None:
        raise P.ProtocolError("DG1 is not ruled (open question 1, results/xasset/STAGE0A_2026-10-14.md §2): "
                              "no test enters Stage 0b")
    counter_guard(trial)
    print(f"{spec.key}: spec pin MATCH; {len(man['files'])} inputs re-hashed; preflight {pf}; XASSET "
          f"counter {counter_value()} >= trial {trial}. Stage 0b begins.")
    out, ctx = decide(spec, trial, data)
    out.update(run_utc=t0, git_head_at_start=P.git_head(), spec_pin=pin, manifest=P.rel(P.MANIFEST),
               preflight=pf)
    ser = out.pop("_series")
    ser.to_parquet(fit_cache(spec.key))
    out["fit_series_cache"] = dict(path=P.rel(fit_cache(spec.key)), sha256=P.sha256(fit_cache(spec.key)))
    out["reported"] = "PENDING: stages 0b-5 are written first; the reported rows follow"
    P.TRIALS.mkdir(parents=True, exist_ok=True)
    P.write_json(fit_json(spec.key), out)
    print(f"{spec.key} FIT VERDICT: {out['fit_verdict']}\nwrote {P.rel(fit_json(spec.key))} (decisions)")
    data.update(book=P.cef_book_pnl(), flags=pd.read_csv(P.QFLAGS, parse_dates=["date"]),
                R_inhouse=inhouse_R(data["R"].index))
    out["reported"] = report(spec, ctx, data)
    P.write_json(fit_json(spec.key), out)
    print(f"wrote {P.rel(fit_json(spec.key))} (decisions and reported rows)")
    return out


def complete_report(spec: Spec) -> dict:
    """Recovery path when a REPORTED row raised after the decisions were written.
    Rebuilds the deterministic decision series, asserts it equals the committed
    one bit for bit and that the verdict is unchanged, then computes the reported
    rows. It can never change a decision."""
    out = json.loads(fit_json(spec.key).read_text())
    if not (isinstance(out.get("reported"), str) and out["reported"].startswith("PENDING")):
        raise P.ProtocolError(f"{spec.key}: reported rows are not pending")
    P.check_spec_pin()
    P.verify_inputs()
    if P.sha256(fit_cache(spec.key)) != out["fit_series_cache"]["sha256"]:
        raise P.ProtocolError("the cached fit series changed since the verdict")
    data = preflight_data()
    out2, ctx = decide(spec, out["trial"], data)
    ser = pd.read_parquet(fit_cache(spec.key))
    if not np.array_equal(out2["_series"]["pnl_sized"].values, ser["pnl_sized"].values) \
            or out2["fit_verdict"] != out["fit_verdict"]:
        raise P.ProtocolError("the rebuilt decision series or verdict differs from the committed one")
    data.update(book=P.cef_book_pnl(), flags=pd.read_csv(P.QFLAGS, parse_dates=["date"]),
                R_inhouse=inhouse_R(data["R"].index))
    out["reported"] = report(spec, ctx, data)
    P.write_json(fit_json(spec.key), out)
    print(f"wrote {P.rel(fit_json(spec.key))} (reported rows completed)")
    return out


def evaluate_fit(spec: Spec, trial: int, data: dict) -> dict:
    """decide + report on injected data (used by the synthetic tests)."""
    out, ctx = decide(spec, trial, data)
    out["reported"] = report(spec, ctx, data)
    return out


def decide(spec: Spec, trial: int, data: dict):
    """Stages 0b-5 on injected data (the fit panel), in the declared order."""
    panel, R, rf, Rx, cal = data["panel"], data["R"], data["rf"], data["Rx"], data["cal"]
    P.assert_fit(R, Rx)
    first_dec = pd.Timestamp(spec.first_dec)
    window = P.pnl_window(first_dec, cal)
    if len(window) != spec.T_declared:
        raise P.ProtocolError(f"{spec.key}: P&L window has {len(window)} sessions; PREREG Table A "
                              f"declares {spec.T_declared}. Halt: a question, not a re-specification.")
    H_raw = spec.build(Rx, R, rf, "primary")
    P.assert_fit(H_raw)
    if H_raw.index[0] != first_dec:
        raise P.ProtocolError(f"{spec.key}: raw sleeve starts {H_raw.index[0].date()}, declared {first_dec.date()}")
    s = P.size(H_raw, Rx, window, spec.key)
    rs, rt = P.run(s["H_sized"], Rx, spec.key), P.run(s["H_trad"], Rx, spec.key + " tradable")
    pnl, turn = rs["pnl"].reindex(window), rs["turn_series"]
    pnl_t, turn_t = rt["pnl"].reindex(window), rt["turn_series"]
    P.assert_fit(pnl, pnl_t)
    rows = s["H_sized"].index[s["H_sized"].index <= cal[cal.get_loc(window[-1]) - 2]]
    out = dict(test=spec.key, title=spec.title, trial=trial, n_slate=P.N_SLATE,
               first_decision=str(first_dec.date()), window=[str(window[0].date()), str(window[-1].date())],
               T=len(window), notes=spec.notes)
    out["stage0b"] = dict(k=s["k"], sigma_fit_raw=s["sigma_fit"],
                          turnover_per_yr_sized=float(turn.reindex(window).mean() * 252),
                          turnover_per_yr_tradable=float(turn_t.reindex(window).mean() * 252),
                          mean_gross_sized=float(s["H_sized"].loc[rows].abs().sum(axis=1).mean()),
                          mean_gross_tradable=float(s["H_trad"].loc[rows].abs().sum(axis=1).mean()),
                          cap_binding_share=P.cap_bind_share(s["H_sized"], window, cal),
                          mean_short_notional_sized=float((-s["H_sized"].loc[rows]).clip(lower=0).sum(axis=1).mean()))
    print("stage 0b:", {k: round(v, 4) for k, v in out["stage0b"].items()})

    # 1. headline
    st1 = P.headline(pnl)
    st1["pass_"] = st1["nw_t21"] >= 1.96
    out["stage1"] = st1
    out["stage1_tradable"] = P.headline(pnl_t, boot=False)
    print(f"stage 1: sized SR {st1['sharpe']:.3f}, NW t(21) {st1['nw_t21']:.2f} -> "
          f"{'pass' if st1['pass_'] else 'FAIL'}")

    ctx = dict(spec=spec, panel=panel, R=R, rf=rf, Rx=Rx, cal=cal, window=window, first_dec=first_dec,
               H_raw=H_raw, sized=s, pnl=pnl, turn=turn, pnl_t=pnl_t, turn_t=turn_t)
    # 2. named control
    st2 = spec.control(ctx)
    out["stage2"] = st2
    print(f"stage 2: {st2['rule']} -> {'pass' if st2['pass_'] else 'FAIL'}")
    # 3. placebo and shift(3)
    span = max(R[n].first_valid_index() for n in spec.names)      # every fund trades from here
    pl = P.placebo(s["H_sized"], Rx, window, st1["sharpe"], span_start=span)
    sh3 = P.sharpe(P.run(s["H_sized"].shift(1).fillna(0.0), Rx, spec.key + " shift3")["pnl"].reindex(window))
    st3 = dict(placebo=pl, shift3_sharpe=sh3, shift2_sharpe=st1["sharpe"],
               shift3_decides=spec.shift3_decides,
               shift3_pass=(sh3 >= 0.5 * st1["sharpe"]) if spec.shift3_decides else None)
    st3["pass_"] = pl["pass_"] and (st3["shift3_pass"] if spec.shift3_decides else True)
    out["stage3"] = st3
    print(f"stage 3: placebo p95 {pl['p95']:.3f} vs real {st1['sharpe']:.3f}; shift(3) {sh3:.3f} -> "
          f"{'pass' if st3['pass_'] else 'FAIL'}")
    # 4. D4
    Fac = P.factor_returns(R, rf)
    d4 = d4_regressions(spec, pnl, Fac, window)
    out["stage4"] = dict(regressions=d4, pass_=all(r["verdict"]["pass_"] for r in d4))
    out["stage4_tradable"] = d4_regressions(spec, pnl_t, Fac, window)
    for r in d4:
        print(f"stage 4 {r['label']}: alpha {r['alpha_pct_yr']:.2f}%/yr t {r['alpha_t']:.2f}; largest |beta| "
              f"{r['verdict']['largest_beta'][0]} {r['verdict']['largest_beta'][1]:+.3f} -> "
              f"{'pass' if r['verdict']['pass_'] else 'FAIL'}")
    # 5. the bar
    st5 = P.bar(pnl)
    out["stage5"] = st5
    print(f"stage 5: _dsr(N=4) {st5['dsr_N4']:.3f} -> {'pass' if st5['pass_'] else 'FAIL'}")

    # verdict: the first failing rule, in order
    order = [("stage1", "KILL D1 (stage 1: no detectable edge)"), ("stage2", spec.control_kill),
             ("stage3", "KILL D1 (stage 3: placebo or shift(3))"), ("stage4", "KILL D4 (stage 4: R-D4)"),
             ("stage5", "NEITHER (stage 5: below the deflated bar; the team lead rules WATCH or D5)")]
    verdict = next((code for k, code in order if not out[k]["pass_"]), "PASS-candidate (fit); holdout pending")
    out["fit_verdict"] = verdict
    cg = P.cost_grid(pnl, turn)
    out["stage8_label_if_pass"] = dict(net15_sized=cg["net15"], d2=cg["net15"] <= 0)
    out["_series"] = pd.DataFrame({"pnl_sized": pnl, "pnl_tradable": pnl_t})
    ctx.update(Fac=Fac, d4=d4)
    return out, ctx


def report(spec: Spec, ctx: dict, data: dict) -> dict:
    """Reported rows: never deciding, computed after the decisions are written."""
    panel, R, rf, cal, window = data["panel"], ctx["R"], ctx["rf"], ctx["cal"], ctx["window"]
    s, pnl, turn, pnl_t, turn_t = ctx["sized"], ctx["pnl"], ctx["turn"], ctx["pnl_t"], ctx["turn_t"]
    Fac, d4 = ctx["Fac"], ctx["d4"]
    rep = {}
    rep["cost_grid_sized"] = P.cost_grid(pnl, turn)
    rep["cost_grid_tradable"] = P.cost_grid(pnl_t, turn_t)
    rep["eras_sized"] = P.eras(pnl, turn)
    rep["eras_tradable"] = P.eras(pnl_t, turn_t)
    rep["r_ff"] = [P.ff_regression(pnl.loc[r["start"]:r["end"]], Fac[r["factors"]]) | dict(label=r["label"])
                   for r in d4]
    rep["r_aqr"] = P.aqr_regression(pnl, spec.aqr, cal) | dict(factors=spec.aqr)
    rep["capacity_sized"] = P.capacity(s["H_sized"], panel, window)
    rep["capacity_tradable"] = P.capacity(s["H_trad"], panel, window)
    rep["r_q"] = r_q(pnl, spec.names, data["flags"])
    try:
        Rih = data["R_inhouse"].reindex(R.index)
        Rxih = P.excess(Rih, rf)
        Hih = spec.build(Rxih, Rih, rf, "inhouse") * s["k"]
        rep["inhouse_source"] = dict(first_decision=str(Hih.index[0].date()),
                                     sharpe=P.sharpe(P.run(Hih, Rxih, "inhouse")["pnl"].reindex(window)))
    except P.ProtocolError as exc:
        rep["inhouse_source"] = dict(not_computable=str(exc))
    rep["cef_book_corr_fit"] = P.book_correlation(pnl, data["book"].loc[:P.FIT_END], R, rf)
    if spec.extras:
        rep.update(spec.extras(ctx))
    return rep


def holdout_guard(spec: Spec):
    missing = [k for k in TESTS if not (P.git_tracked(fit_json(k)) or P.git_tracked(unrun_json(k)))]
    if missing:
        raise P.ProtocolError(f"holdout sealed: no committed fit verdict for {missing} (PREREG §1.5)")
    if holdout_json(spec.key).exists():
        raise P.ProtocolError(f"{spec.key}: the holdout was already opened ({P.rel(holdout_json(spec.key))})")


def holdout(spec: Spec) -> dict:
    """Stage 7, opened once, after all four fit verdicts are committed."""
    holdout_guard(spec)
    fitres = json.loads(fit_json(spec.key).read_text())
    P.check_spec_pin()
    P.verify_inputs()
    if P.sha256(fit_cache(spec.key)) != fitres["fit_series_cache"]["sha256"]:
        raise P.ProtocolError("the cached fit series changed since the fit verdict")
    panel, R, rf, Rx, cal = load(P.HOLDOUT_END)
    data = dict(R=R, rf=rf, Rx=Rx, cal=cal, book=P.cef_book_pnl())
    out = evaluate_holdout(spec, fitres, pd.read_parquet(fit_cache(spec.key)), data)
    out.update(opened_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), git_head=P.git_head())
    P.TRIALS.mkdir(parents=True, exist_ok=True)
    P.write_json(holdout_json(spec.key), out)
    print(f"{spec.key} HOLDOUT: mean {out['ann_mean_pct']:.2f}%/yr, SR {out['sharpe']:.2f}, same sign "
          f"{out['same_sign_as_fit']} -> {out['final_verdict']}\nwrote {P.rel(holdout_json(spec.key))}")
    return out


def evaluate_holdout(spec: Spec, fitres: dict, fit_ser: pd.DataFrame, data: dict) -> dict:
    """One continuous series from the first decision to 2026-09-30, k frozen; the
    fit rows must equal the fit P&L exactly; the holdout rows are sliced from it."""
    from src.deploy.sleeves.cef_discount import _cap_gross
    R, rf, Rx, cal = data["R"], data["rf"], data["Rx"], data["cal"]
    k = fitres["stage0b"]["k"]                                  # frozen (H13)
    H = spec.build(Rx, R, rf, "primary") * k
    Ht = pd.DataFrame([_cap_gross(H.loc[t], P.PINNED_MAX_GROSS)[0] for t in H.index], index=H.index,
                      columns=H.columns)
    r, rt = P.run(H, Rx, spec.key), P.run(Ht, Rx, spec.key + " tradable")
    full, turn = r["pnl"], r["turn_series"]
    w = fit_ser.index
    if not np.array_equal(full.reindex(w).values, fit_ser["pnl_sized"].values):
        raise P.ProtocolError("the fit rows of the continuous series differ from the fit P&L (PREREG §1.5)")
    hw = cal[(cal >= P.HOLDOUT_FIRST) & (cal <= P.HOLDOUT_END)]
    h, ht = full.reindex(hw), rt["pnl"].reindex(hw)
    fit_mean = fit_ser["pnl_sized"].mean()
    fit_sr = fitres["stage1"]["sharpe"]
    yrs = len(h) / 252
    mu, sr = P.stationary_bootstrap(h.values, P.BOOT_BLOCK, P.BOOT_REPS, P.SEED)
    obs_sign = float(np.sign(h.mean()))
    out = dict(test=spec.key, fit_verdict=fitres["fit_verdict"], k_frozen=k,
               window=[str(hw[0].date()), str(hw[-1].date())], T=len(h),
               mean_daily=float(h.mean()), ann_mean_pct=float(h.mean() * 252 * 100),
               sharpe=P.sharpe(h), nw_t21=P.nw_t(h),
               boot21_mean_ci_pct=[float(np.percentile(mu, 2.5) * 252 * 100), float(np.percentile(mu, 97.5) * 252 * 100)],
               boot21_sharpe_ci=[float(np.nanpercentile(sr, 2.5)), float(np.nanpercentile(sr, 97.5))],
               fit_mean_daily=float(fit_mean), same_sign_as_fit=bool(np.sign(h.mean()) == np.sign(fit_mean)),
               p_observed_sign_under_fit_sr=float(NormalDist().cdf(obs_sign * fit_sr * math.sqrt(yrs))),
               cost_grid_sized=P.cost_grid(h, turn), cost_grid_tradable=P.cost_grid(ht, rt["turn_series"]),
               tradable_sharpe=P.sharpe(ht))
    is_candidate = fitres["fit_verdict"].startswith("PASS")
    out["stage7"] = dict(applies=is_candidate,
                         pass_=out["same_sign_as_fit"] if is_candidate else None,
                         rule="holdout mean has the fit mean's sign (D3 if not); applies to a fit PASS-candidate")
    out["cef_book_corr_holdout"] = P.book_correlation(h, data["book"].loc[P.HOLDOUT_FIRST:], R, rf)
    if spec.holdout_extras:
        out.update(spec.holdout_extras(dict(pnl=h, full=full, cal=cal, R=R, rf=rf, Rx=Rx, turn=turn)))
    if is_candidate:
        final = "KILL D3 (stage 7: holdout sign)" if not out["same_sign_as_fit"] else "PASS"
        if final == "PASS" and fitres["stage8_label_if_pass"]["d2"]:
            final = "PASS, labelled D2 (stage 8: net at 15bp <= 0; paper only by team-lead ruling)"
    else:
        final = fitres["fit_verdict"] + " (holdout reported; it cannot rescue a failed fit)"
    out["final_verdict"] = final
    return out


def main(spec: Spec, argv=None) -> int:
    ap = argparse.ArgumentParser(description=spec.title)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--trial", type=int, help="XASSET trial number this run spends (counter must be there)")
    g.add_argument("--holdout", action="store_true", help="open this test's holdout, once")
    g.add_argument("--preflight", action="store_true",
                   help="zero-trial: pins, hashes and the date/coverage checks only; no P&L")
    g.add_argument("--complete-report", action="store_true",
                   help="only if a fit verdict's reported rows are PENDING (a reported row raised)")
    a = ap.parse_args(argv)
    if a.complete_report:
        complete_report(spec)
    elif a.preflight:
        P.check_spec_pin()
        P.verify_inputs()
        print(f"{spec.key} preflight:", preflight(spec, preflight_data()),
              "| DG1:", "OPEN (question 1)" if P.DG1_RULING is None else P.DG1_RULING)
    elif a.holdout:
        holdout(spec)
    else:
        fit(spec, a.trial)
    return 0
