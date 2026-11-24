"""Trial 53 under the live thin rule: active-session vol, the multiplier it implies, and whether the
stops can fire spuriously (2026-11-02; zero trials, report only).

    python3 results/cef/prereg_voltarget/flatten_remeasure.py --flat-root FLAT --hold-root HOLD \\
        --m-core 1.13 --m-c4 1.27 --m-c4-rule 1.2642
        -> flatten_remeasure_2026-11-02.json, flatten_remeasure_output_2026-11-02.txt (this folder)

FLAT and HOLD are flatten_series.py's two roots. They have the same layout, and the core is the
flatten book and the hold book respectively. Fit window only (`_common.load` asserts it).

WHY ACTIVE-SESSION VOL. Under the live rule the core is FLAT on 1,353 of W1's 2,398 sessions. Its
calendar daily sd (0.002351) mixes those zeros with the sessions it trades. The 2026-10-29 rule
sizes for equal STANDALONE risk, and for b = 1/2, 1/2 its multipliers satisfy, exactly,

    m_core / m_c4 = sd_c4 / sd_core,

so a calendar sd that counts flat days sizes the core for risk it does not carry when it trades.
That is the units trap SCRATCH/alloc4/NOTE.md section 8 names for intermittent sleeves ('vol
target means active-session vol'). The live core trades now, so its risk while trading is what
the account carries.

WHAT IS COMPUTED.
1. The core unit book's daily sd, calendar and on its EARNING sessions (a book was held two
   sessions earlier), flatten and hold; the core-C4 correlation, both ways.
2. The multiplier the rule's identity gives on each: m_core = m_c4(rule) x sd_c4 / sd_core, with
   m_c4(rule) from `derive.py --remeasure` (section 4).
3. R1-R3 at --m-core on three calibration series: the hold book (what `stops.py` measured for the
   approval), the flatten book on every session, and the flatten book on its earning sessions only.
   The definitions are stops.py's. On the earning series the bootstrap draws only sessions on which
   the book traded, which is the live book while it is active.
4. THE SPURIOUS-FIRING MATRIX. For each truth series (fit edge, SB21, 10,000 paths) and each
   calibration, the probability that each stop fires within its horizon (R1: 252 sessions; R2: 120;
   R3: 60). By construction a stop fires 5% of the time on its own calibration series; any other
   cell is that stop's false-alarm rate when the live book behaves like the truth series.
5. P(HALVE) and P(KILL) in 12 months at --m-core on the earning series (zero edge and fit edge; the
   worst of SB21, SB63 and GAUSS; the worse of TR and PR): the live book's risk while it trades.
6. (added 2026-11-02, the x1.30 comparison) THROUGH 2008 ON TRADING SESSIONS. W2 = 2005-02-22 ->
   2022-12-30 with the core proxied before 2013-06-25 by each NON-THIN year-end flatten book. The
   5 thin ones are flat under the live rule and trade nothing. The account series keeps only the
   sessions on which a book earns. Reported: P(HALVE) and P(KILL) at zero edge, and the worst
   drawdown, as min / median / max over those books. Also the share of trading sessions on which the
   account's decided gross is above its cap (the house cap model).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from _common import (HALVE_DD, HERE, HORIZON, KILL_DD, W1_START, W2_START, Paths, account, c4_spec_from,
                     core_spec, draw, load, max_drawdown, odds, path_max_drawdown, stats, worst, with_proxy)

STAMP = "2026-11-02"


def thresholds(x_tr, x_pr, paths):
    """stops.py's R1-R3 on daily series (numpy), at the fit edge."""
    p95 = max(max(float(np.quantile(path_max_drawdown(v), 0.95)) for v in draw(x, paths, "fit").values())
              for x in (x_tr, x_pr))
    d_r = min(HALVE_DD, p95)
    I21 = paths.get(len(x_pr))[0]
    r2 = float(np.quantile(np.prod(1 + x_pr[I21[:, :120]], axis=1) - 1, 0.05))
    r3 = float(np.quantile(x_pr[I21[:, :60]].std(axis=1, ddof=1) * np.sqrt(252), 0.95))
    return dict(R1=d_r, R1_p95_raw=p95, R2=r2, R3=r3)


def fire(x_tr, x_pr, thr, paths):
    """P(each stop fires within its horizon) when the truth is (x_tr, x_pr), fit edge, SB21."""
    I21 = paths.get(len(x_pr))[0]
    dd = max(float((path_max_drawdown(x[I21]) >= thr["R1"]).mean()) for x in (x_tr, x_pr))
    r2 = float(((np.prod(1 + x_pr[I21[:, :120]], axis=1) - 1) < thr["R2"]).mean())
    r3 = float(((x_pr[I21[:, :60]].std(axis=1, ddof=1) * np.sqrt(252)) > thr["R3"]).mean())
    return dict(R1=dd, R2=r2, R3=r3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat-root", type=Path, required=True)
    ap.add_argument("--hold-root", type=Path, required=True)
    ap.add_argument("--m-core", type=float, required=True)
    ap.add_argument("--m-c4", type=float, required=True)
    ap.add_argument("--m-c4-rule", type=float, required=True,
                    help="C4's multiplier from derive.py --remeasure section 4 (unrounded)")
    ap.add_argument("--stamp", default=STAMP)
    a = ap.parse_args()
    F, Hd = load(a.flat_root), load(a.hold_root)
    earn = pd.read_parquet(a.flat_root / "flatten_masks.parquet")["earning"]
    cap = float(core_spec.MAX_GROSS_STRESS)
    cap4 = float(c4_spec_from()["frozen"]["max_gross_stress"])
    paths = Paths()
    say, out = [], {}

    def p(*x):
        s = " ".join(str(v) for v in x)
        print(s, flush=True)
        say.append(s)

    w1 = F["PT"].index >= W1_START
    e = earn.reindex(F["PT"].index).fillna(False).to_numpy(dtype=bool) & w1
    p(f"W1 {W1_START.date()}..2022-12-30: {int(w1.sum())} sessions; the flatten core earns on {int(e.sum())} "
      f"({e.sum() / w1.sum():.1%})")
    # ---- 1-2. vols, correlation, the implied multipliers ----
    c4 = F["PT"]["c4"].to_numpy()
    sd = dict(hold=float(Hd["PT"]["core"][w1].std()), flatten_calendar=float(F["PT"]["core"][w1].std()),
              flatten_active=float(F["PT"]["core"][e].std()), c4=float(F["PT"]["c4"][w1].std()))
    rho = dict(hold=float(np.corrcoef(Hd["PT"]["core"][w1], c4[w1])[0, 1]),
               flatten_calendar=float(np.corrcoef(F["PT"]["core"][w1], c4[w1])[0, 1]),
               flatten_active=float(np.corrcoef(F["PT"]["core"][e], c4[e])[0, 1]))
    implied = {k: a.m_c4_rule * sd["c4"] / sd[k] for k in ("hold", "flatten_calendar", "flatten_active")}
    for k in implied:
        p(f"  core unit sd ({k}) {sd[k]:.6f} daily = {sd[k] * np.sqrt(252) * 100:.2f}%/yr; corr with C4 {rho[k]:+.3f}; "
          f"implied core multiplier {a.m_c4_rule} x {sd['c4']:.6f} / {sd[k]:.6f} = {implied[k]:.4f} "
          f"(written {np.floor(implied[k] * 100) / 100:.2f})")
    out.update(sd_daily=sd, corr_with_c4=rho, implied_core_multiplier=implied, earning_share_W1=float(e.sum() / w1.sum()))

    # ---- 3. thresholds on three calibration series, at m_core ----
    def core_series(D, basis):
        P = D["PT"] if basis == "TR" else D["PP"]
        return account(P["core"], D["G"]["core"], a.m_core, cap)[0]
    ser = {"hold": (core_series(Hd, "TR")[w1].to_numpy(), core_series(Hd, "PR")[w1].to_numpy()),
           "flatten_all": (core_series(F, "TR")[w1].to_numpy(), core_series(F, "PR")[w1].to_numpy()),
           "flatten_active": (core_series(F, "TR")[e].to_numpy(), core_series(F, "PR")[e].to_numpy())}
    thr = {k: thresholds(v[0], v[1], paths) for k, v in ser.items()}
    p(f"\n3. CORE ACCOUNT STOPS at x{a.m_core}, by the series they are calibrated on (fit edge)")
    for k, t in thr.items():
        p(f"  {k:15s} R1 D_R {t['R1'] * 100:5.2f}% (p95 {t['R1_p95_raw'] * 100:.2f}%) | R2 {t['R2'] * 100:+.2f}% | "
          f"R3 {t['R3'] * 100:.2f}%")
    out["thresholds_core"] = thr
    # ---- 4. spurious firing ----
    p("\n4. P(the stop fires within its horizon) | the truth series (rows) and the calibration (columns); SB21, "
      "fit edge. The nominal rate is 5% on the diagonal")
    mat = {}
    for truth, (xt, xp) in ser.items():
        mat[truth] = {cal: fire(xt, xp, t, paths) for cal, t in thr.items()}
        for st_ in ("R1", "R2", "R3"):
            p(f"  truth {truth:15s} {st_}: " + " | ".join(f"{cal} {mat[truth][cal][st_] * 100:5.1f}%" for cal in thr))
    out["fire_matrix"] = mat
    # ---- 5. risk while trading ----
    p(f"\n5. CORE ACCOUNT at x{a.m_core} on the EARNING sessions only (the live book while it trades)")
    for edge in ("zero", "fit"):
        o = {b: odds(ser["flatten_active"][i], paths, edge) for i, b in enumerate(("TR", "PR"))}
        h = max(worst(o[b], 0) for b in o)
        k = max(worst(o[b], 1) for b in o)
        oh = {b: odds(ser["hold"][i], paths, edge) for i, b in enumerate(("TR", "PR"))}
        of = {b: odds(ser["flatten_all"][i], paths, edge) for i, b in enumerate(("TR", "PR"))}
        out[f"odds_{edge}"] = dict(flatten_active=dict(halve=h, kill=k),
                                   hold=dict(halve=max(worst(oh[b], 0) for b in oh), kill=max(worst(oh[b], 1) for b in oh)),
                                   flatten_all=dict(halve=max(worst(of[b], 0) for b in of), kill=max(worst(of[b], 1) for b in of)))
        q = out[f"odds_{edge}"]
        p(f"  {edge} edge, P(HALVE) / P(KILL) in 12 months: flatten earning {q['flatten_active']['halve'] * 100:.2f}% / "
          f"{q['flatten_active']['kill'] * 100:.2f}% | flatten all sessions {q['flatten_all']['halve'] * 100:.2f}% / "
          f"{q['flatten_all']['kill'] * 100:.2f}% | hold {q['hold']['halve'] * 100:.2f}% / {q['hold']['kill'] * 100:.2f}%")
    st_e = stats(pd.Series(ser["flatten_active"][0]))
    out["flatten_active_stats_TR"] = st_e
    # cap binding on trading sessions (the house model: decided uncapped gross above the cap)
    _, fa, Ga, _ = account(F["PT"]["core"], F["G"]["core"], a.m_core, cap)
    dec = (Ga > 0).to_numpy() & w1
    out["cap_binds_decided_W1"] = dict(trading_days=float((fa.to_numpy()[dec] < 1).mean()),
                                       all_days=float((fa.to_numpy()[w1] < 1).mean()))
    p(f"  cap binding (decided gross above 1.80) at x{a.m_core}: {out['cap_binds_decided_W1']['trading_days']:.1%} of the "
      f"sessions with a decided book, {out['cap_binds_decided_W1']['all_days']:.1%} of all W1 sessions")
    # ---- 6. through 2008, trading sessions only, over the non-thin year-end books ----
    p(f"\n6. THROUGH 2008 ON TRADING SESSIONS (W2 {W2_START.date()}..2022-12-30; core proxied before "
      f"{W1_START.date()} by each non-thin year-end flatten book), x{a.m_core}")
    rows = []
    for sn in F["prox_t"].columns:
        if float(F["prox_g"][sn]) == 0.0:
            continue                                   # a thin year-end book: flat under the live rule
        r = {"book": sn}
        for b in ("TR", "PR"):
            Px, Gx = with_proxy(F, sn, b)
            x = account(Px["core"], Gx["core"], a.m_core, cap)[0]
            keep = pd.Series(e, index=x.index)
            keep.loc[x.index < W1_START] = True        # the fixed proxy book earns on every pre-2013 session
            keep.loc[x.index < W2_START] = False
            xs = x[keep.to_numpy()].to_numpy()
            o = odds(xs, paths, "zero")
            r[f"H_{b}"], r[f"K_{b}"] = worst(o, 0), worst(o, 1)
            r[f"mdd_{b}"] = float(max_drawdown(pd.Series(xs))["mdd"])
        rows.append(r)
    T6 = pd.DataFrame(rows)
    H6, K6 = np.maximum(T6.H_TR, T6.H_PR), np.maximum(T6.K_TR, T6.K_PR)
    M6 = np.maximum(T6.mdd_TR, T6.mdd_PR)
    out["w2_trading"] = dict(books=T6.to_dict(orient="records"),
                             halve=[float(H6.min()), float(H6.median()), float(H6.max())],
                             kill=[float(K6.min()), float(K6.median()), float(K6.max())],
                             mdd=[float(M6.min()), float(M6.median()), float(M6.max())],
                             worst_book=str(T6.book[int(K6.values.argmax())]))
    w = out["w2_trading"]
    p(f"  {len(T6)} non-thin books: zero-edge P(HALVE) {'/'.join(f'{v * 100:.2f}' for v in w['halve'])}% | P(KILL) "
      f"{'/'.join(f'{v * 100:.2f}' for v in w['kill'])}% | worst drawdown {'/'.join(f'{v * 100:.1f}' for v in w['mdd'])}% "
      f"(min/median/max; worst book {w['worst_book']})")
    p(f"  earning-session series at x{a.m_core}, TR: {st_e['ann'] * 100:.2f}%/yr while trading, vol {st_e['vol'] * 100:.2f}%, "
      f"SR {st_e['sr']:.3f}, maxDD {st_e['mdd'] * 100:.2f}% (sessions concatenated)")
    (HERE / f"flatten_remeasure_{a.stamp}.json").write_text(json.dumps(out, indent=1, default=float))
    (HERE / f"flatten_remeasure_output_{a.stamp}.txt").write_text("\n".join(say) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
