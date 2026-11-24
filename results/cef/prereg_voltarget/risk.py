"""Risk at the raised targets, per account and combined, through 2008-09 (CEF trial 53, DRAFT).

    python3 results/cef/prereg_voltarget/risk.py --scratch SCRATCH
        -> risk_2026-10-30.json, risk_output_2026-10-30.txt (this folder); about 5 minutes

ZERO TRIALS; fit window only (asserted). Reads the declaration (declared_2026-10-30.json) and asserts
it is older than this run. Nothing here decides the multipliers (derive.py does, by the 2026-10-28
rule); this is the report the pre-registration's risk section quotes.

THE BOOKS (each a pair of account multipliers on the unit books, 6%-target sizing):
  today            core 1.00, C4 1.00
  ruled            core 1.24, C4 1.41  (team lead 2026-10-29/30)
  spec-derived     core 1.24, C4 1.39  (the same rule on C4's 1.90 spec book, rounded down; derive.py §3)
  rule-2026-10-29  core 1.13, C4 1.27  (the four-sleeve note's per-account term (d); derive.py §4)
C4's series is the SPEC book (cap 1.90) throughout: the book paper trades. The core account's cap is
the core spec's max_gross_stress, C4's its own spec's, both read from the specs.

THE WINDOWS. W1 = 2013-06-25 -> 2022-12-30, the core's own book. W2 = 2005-02-22 -> 2022-12-30, through
2008-09; before 2013-06-25 the core is the house fixed-book group proxy (portfolio_baseline.group_proxy)
at EACH of the 10 year-end core books 2013..2022, so every W2 figure for the core account or the
combined book is a min / median / max over the 10. A fixed book is not vol-targeted through 2008, so
the core's W2 figures are an upper bound on what the vol scalar would have let happen [U].

THE ODDS. P(max drawdown >= risk.halve_drawdown) and P(>= risk.kill_drawdown) within 252 sessions,
compounded from a high-water mark, SB21 / SB63 / GAUSS (10,000 paths, common random numbers across
books), the worst method shown; zero edge (demeaned) and fit edge; total return and price only (paper
is scored price only: Alpaca pays no distributions). HALVE does not act (report mode is today's
state). The raise-specific stop R1 (declaration) is calibrated here and its effect on P(KILL) is shown
as information: once a path's drawdown reaches D_R the rest of the path is held at 1/m of its size.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from _common import (FIT_END, HALVE_DD, HERE, HORIZON, KILL_DD, W1_START, W2_START, Paths, account,
                     assert_fit, c4_spec_from, core_spec, draw, load, max_drawdown, odds,
                     path_max_drawdown, stats, worst, with_proxy)

STAMP = "2026-10-30"
BOOKS = {"today": (1.00, 1.00), "ruled": (1.24, 1.41), "spec-derived": (1.24, 1.39), "rule-2026-10-29": (1.13, 1.27)}
GFC = ("2008-09-01", "2009-03-31")
COSTS_BP = (5, 15, 30)


def capped_turnover(H: pd.DataFrame, m: float, f: pd.Series) -> pd.Series:
    """One-way turnover of the account's capped decided book m x f_t x H_t (evaluate()'s units)."""
    Hc = H.mul(m * f, axis=0)
    return Hc.diff().abs().sum(axis=1).fillna(0.0)


def stop_paths(x: np.ndarray, paths: Paths, edge: str, d_stop: float, m: float) -> dict:
    """{method: P(KILL)} when every path is cut to 1/m of its size from the session after its drawdown
    first reaches d_stop (the R1 revert), HALVE not acting."""
    out = {}
    for lab, pth in draw(x, paths, edge).items():
        eq = np.cumprod(1 + pth, axis=1)
        peak = np.maximum.accumulate(np.concatenate([np.ones((len(eq), 1)), eq], axis=1), axis=1)[:, 1:]
        hit = (1 - eq / peak) >= d_stop
        first = np.where(hit.any(axis=1), hit.argmax(axis=1), HORIZON)
        scale = np.where(np.arange(HORIZON)[None, :] > first[:, None], 1.0 / m, 1.0)
        out[lab] = float((path_max_drawdown(pth * scale) >= KILL_DD).mean())
    return out


def pctl_maxdd(x: np.ndarray, paths: Paths, q: float) -> dict:
    return {lab: float(np.quantile(path_max_drawdown(p), q)) for lab, p in draw(x, paths, "fit").items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--stamp", default=STAMP)
    ap.add_argument("--books", default=None,
                    help="name=core,c4;... (2026-11-02, the flatten re-measure). Absent: the BOOKS above")
    a = ap.parse_args()
    books = BOOKS if a.books is None else {
        n: tuple(float(x) for x in v.split(",")) for n, v in (kv.split("=") for kv in a.books.split(";"))}
    dec = json.loads((HERE / "declared_2026-10-30.json").read_text())
    if not datetime.fromisoformat(dec["declared_utc"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
        raise AssertionError("the declaration is not older than this run")
    D = load(a.scratch)
    cap = {"core": float(core_spec.MAX_GROSS_STRESS), "c4": float(c4_spec_from()["frozen"]["max_gross_stress"])}
    snaps = list(D["prox_t"].columns)
    paths = Paths()
    say, out = [], {}

    def p(*x):
        s = " ".join(str(v) for v in x)
        print(s, flush=True)
        say.append(s)

    p(f"HALVE {HALVE_DD}, KILL {KILL_DD} (core spec risk, fractions); caps core {cap['core']}, C4 {cap['c4']}; "
      f"W1 {W1_START.date()}..{FIT_END.date()}, W2 {W2_START.date()}..{FIT_END.date()}; 10 core books {snaps[0]}..{snaps[-1]}")
    for name, (mc, m4) in books.items():
        p(f"\n=== {name}: core x{mc}, C4 x{m4}")
        r = dict(m_core=mc, m_c4=m4)
        acc = {}
        for basis in ("TR", "PR"):
            P = D["PT"] if basis == "TR" else D["PP"]
            xa, fa, Ga, _ = account(P["core"], D["G"]["core"], mc, cap["core"])
            xb, fb, Gb, _ = account(P["c4"], D["G"]["c4"], m4, cap["c4"])
            acc[basis] = dict(core=xa, c4=xb, comb=0.5 * xa + 0.5 * xb, f=dict(core=fa, c4=fb), G=dict(core=Ga, c4=Gb))
        # ---- W1 statistics, the cap, turnover and the cost grid (gross headline, net beside) ----
        tu = {"core": capped_turnover(D["H"]["core"], mc, acc["TR"]["f"]["core"]),
              "c4": capped_turnover(D["H"]["c4"], m4, acc["TR"]["f"]["c4"])}
        tu["comb"] = 0.5 * tu["core"] + 0.5 * tu["c4"]
        for who in ("core", "c4", "comb"):
            for basis in ("TR", "PR"):
                x = acc[basis][who].loc[W1_START:]
                assert_fit(x)
                st = stats(x)
                r[f"{who}_{basis}_W1"] = st
            t = float(tu[who].loc[W1_START:].mean() * 252)
            g = r[f"{who}_TR_W1"]["ann"]
            r[f"{who}_turn_yr"] = t
            r[f"{who}_net_pct"] = {bp: (g - t * bp * 1e-4) * 100 for bp in COSTS_BP}
            r[f"{who}_breakeven_bp"] = g / t * 1e4 if t > 0 else float("inf")
        for who in ("core", "c4"):
            f = acc["TR"]["f"][who].loc[W1_START:]
            r[f"{who}_cap_binds_W1"] = float((f < 1).mean())
            r[f"{who}_mean_uncapped_gross_W1"] = float(acc["TR"]["G"][who].loc[W1_START:].mean())
            r[f"{who}_mean_held_gross_W1"] = float((acc["TR"]["G"][who] * acc["TR"]["f"][who]).shift(2).fillna(0).loc[W1_START:].mean())
        fb2 = acc["TR"]["f"]["c4"].loc[W2_START:]
        r["c4_cap_binds_W2"] = float((fb2 < 1).mean())
        for who, lab in (("core", "core account"), ("c4", "C4 account"), ("comb", "combined ($200k)")):
            t, q = r[f"{who}_TR_W1"], r[f"{who}_PR_W1"]
            p(f"  {lab:17s} W1 gross TR {t['ann'] * 100:5.2f}%/yr vol {t['vol'] * 100:4.2f}% SR {t['sr']:.3f} maxDD {t['mdd'] * 100:5.2f}% | "
              f"PR {q['ann'] * 100:5.2f}% SR {q['sr']:.3f} maxDD {q['mdd'] * 100:5.2f}% | turn {r[f'{who}_turn_yr']:5.1f}/yr | net "
              + " / ".join(f"{v:+.2f}" for v in r[f"{who}_net_pct"].values()) + f" %/yr at 5/15/30bp | breakeven {r[f'{who}_breakeven_bp']:.1f}bp")
        p(f"  cap binds W1: core {r['core_cap_binds_W1']:.1%}, C4 {r['c4_cap_binds_W1']:.1%} (C4 on W2 {r['c4_cap_binds_W2']:.1%}); "
          f"mean uncapped gross core {r['core_mean_uncapped_gross_W1']:.3f} / C4 {r['c4_mean_uncapped_gross_W1']:.3f}; "
          f"held core {r['core_mean_held_gross_W1']:.3f} / C4 {r['c4_mean_held_gross_W1']:.3f}")
        # ---- the odds on W1 ----
        o = {}
        for who in ("core", "c4", "comb"):
            for basis in ("TR", "PR"):
                for edge in ("zero", "fit"):
                    o[(who, basis, edge)] = odds(acc[basis][who].loc[W1_START:].values, paths, edge)
        for edge in ("zero", "fit"):
            line = []
            for who in ("core", "c4", "comb"):
                h = max(worst(o[(who, b, edge)], 0) for b in ("TR", "PR"))
                k = max(worst(o[(who, b, edge)], 1) for b in ("TR", "PR"))
                r[f"W1_{who}_{edge}"] = dict(halve=h, kill=k, detail={b: o[(who, b, edge)] for b in ("TR", "PR")})
                line.append(f"{who} H {h * 100:5.2f}% K {k * 100:5.2f}%")
            p(f"  W1 odds, {edge} edge (worst method, worse of TR/PR): " + " | ".join(line))
        # ---- W2: C4 alone; core and combined at each of the 10 books ----
        c4w2 = {(b, e): odds(acc[b]["c4"].loc[W2_START:].values, paths, e) for b in ("TR", "PR") for e in ("zero", "fit")}
        for e in ("zero", "fit"):
            r[f"W2_c4_{e}"] = dict(halve=max(worst(c4w2[(b, e)], 0) for b in ("TR", "PR")),
                                   kill=max(worst(c4w2[(b, e)], 1) for b in ("TR", "PR")))
        r["W2_c4_mdd"] = {b: float(max_drawdown(acc[b]["c4"].loc[W2_START:])["mdd"]) for b in ("TR", "PR")}
        r["W2_c4_trough"] = str(max_drawdown(acc["TR"]["c4"].loc[W2_START:])["trough"].date())
        per = []
        for sn in snaps:
            row = dict(snap=sn)
            for b in ("TR", "PR"):
                Px, Gx = with_proxy(D, sn, b)
                xa, _, _, _ = account(Px["core"], Gx["core"], mc, cap["core"])
                xc = (0.5 * xa + 0.5 * acc[b]["c4"]).loc[W2_START:]
                xa = xa.loc[W2_START:]
                assert_fit(xa, xc)
                for e in ("zero", "fit"):
                    oa, oc = odds(xa.values, paths, e), odds(xc.values, paths, e)
                    row[f"core_H_{b}_{e}"], row[f"core_K_{b}_{e}"] = worst(oa, 0), worst(oa, 1)
                    row[f"comb_H_{b}_{e}"], row[f"comb_K_{b}_{e}"] = worst(oc, 0), worst(oc, 1)
                row[f"core_mdd_{b}"] = float(max_drawdown(xa)["mdd"])
                row[f"comb_mdd_{b}"] = float(max_drawdown(xc)["mdd"])
                row[f"core_gfc_{b}"] = float(max_drawdown(xa.loc[GFC[0]:GFC[1]])["mdd"])
                row[f"comb_gfc_{b}"] = float(max_drawdown(xc.loc[GFC[0]:GFC[1]])["mdd"])
            per.append(row)
        W2 = pd.DataFrame(per)
        r["W2_by_book"] = W2.to_dict(orient="records")
        for who in ("core", "comb"):
            for e in ("zero", "fit"):
                h = np.maximum(W2[f"{who}_H_TR_{e}"], W2[f"{who}_H_PR_{e}"])
                k = np.maximum(W2[f"{who}_K_TR_{e}"], W2[f"{who}_K_PR_{e}"])
                r[f"W2_{who}_{e}"] = dict(halve=[float(h.min()), float(h.median()), float(h.max())],
                                          kill=[float(k.min()), float(k.median()), float(k.max())],
                                          halve_last=float(h.iloc[-1]), kill_last=float(k.iloc[-1]),
                                          worst_book=str(W2.snap[int(k.values.argmax())]))
            md = np.maximum(W2[f"{who}_mdd_TR"], W2[f"{who}_mdd_PR"])
            gf = np.maximum(W2[f"{who}_gfc_TR"], W2[f"{who}_gfc_PR"])
            r[f"W2_{who}_mdd"] = [float(md.min()), float(md.median()), float(md.max())]
            r[f"W2_{who}_gfc"] = [float(gf.min()), float(gf.median()), float(gf.max())]
        for e in ("zero", "fit"):
            c, k = r[f"W2_core_{e}"], r[f"W2_comb_{e}"]
            p(f"  W2 odds, {e} edge: core account H {'/'.join(f'{v * 100:.2f}' for v in c['halve'])}% "
              f"K {'/'.join(f'{v * 100:.2f}' for v in c['kill'])}% (min/median/max over 10 books; worst {c['worst_book']}) | "
              f"C4 account H {r[f'W2_c4_{e}']['halve'] * 100:.2f}% K {r[f'W2_c4_{e}']['kill'] * 100:.2f}% | "
              f"combined H {'/'.join(f'{v * 100:.2f}' for v in k['halve'])}% K {'/'.join(f'{v * 100:.2f}' for v in k['kill'])}%")
        p(f"  W2 worst drawdown (worse of TR/PR): core account {'/'.join(f'{v * 100:.1f}' for v in r['W2_core_mdd'])}% "
          f"(GFC window {'/'.join(f'{v * 100:.1f}' for v in r['W2_core_gfc'])}%) | C4 account "
          f"{max(r['W2_c4_mdd'].values()) * 100:.1f}% (trough {r['W2_c4_trough']}) | combined "
          f"{'/'.join(f'{v * 100:.1f}' for v in r['W2_comb_mdd'])}% (GFC {'/'.join(f'{v * 100:.1f}' for v in r['W2_comb_gfc'])}%)")
        # ---- the raise-specific stops: calibration (information; re-measured on the read date) ----
        if mc != 1.0 or m4 != 1.0:
            st = {}
            for who, m_, win in (("core", mc, W1_START), ("c4", m4, W2_START)):
                p95 = {b: pctl_maxdd(acc[b][who].loc[win:].values, paths, 0.95) for b in ("TR", "PR")}
                d_r = min(HALVE_DD, max(max(v.values()) for v in p95.values()))
                xpr = acc["PR"][who].loc[win:].values
                I21 = paths.get(len(xpr))[0]
                c120 = np.prod(1 + xpr[I21[:, :120]], axis=1) - 1
                v60 = xpr[I21[:, :60]].std(axis=1, ddof=1) * np.sqrt(252)
                ks = {b: stop_paths(acc[b][who].loc[win:].values, paths, "zero", d_r, m_) for b in ("TR", "PR")}
                st[who] = dict(D_R=d_r, p95_maxdd_fit=p95, R2_p5_cum120_PR=float(np.quantile(c120, 0.05)),
                               R3_p95_vol60_PR=float(np.quantile(v60, 0.95)),
                               kill_zero_with_R1=max(max(v.values()) for v in ks.values()),
                               kill_zero_without=(r["W1_core_zero"]["kill"] if who == "core" else r["W2_c4_zero"]["kill"]))
                p(f"  stops, {who} account ({'W1' if who == 'core' else 'W2'}): D_R {d_r * 100:.2f}% (fit-edge p95 of 12m maxDD, "
                  f"max method: TR {max(p95['TR'].values()) * 100:.2f}% PR {max(p95['PR'].values()) * 100:.2f}%; capped at HALVE) | "
                  f"R2 p5 of 120-session PR return {st[who]['R2_p5_cum120_PR'] * 100:+.2f}% | R3 p95 of 60-session vol "
                  f"{st[who]['R3_p95_vol60_PR'] * 100:.2f}% | zero-edge P(KILL) {st[who]['kill_zero_without'] * 100:.2f}% -> "
                  f"{st[who]['kill_zero_with_R1'] * 100:.2f}% with R1 acting")
            # the core's R1 on the median W2 book (through 2008)
            k_med = W2.assign(k=np.maximum(W2.core_K_TR_zero, W2.core_K_PR_zero)).sort_values("k").iloc[len(W2) // 2]
            sn = k_med.snap
            kk = {}
            for b in ("TR", "PR"):
                Px, Gx = with_proxy(D, sn, b)
                xa, _, _, _ = account(Px["core"], Gx["core"], mc, cap["core"])
                kk[b] = stop_paths(xa.loc[W2_START:].values, paths, "zero", st["core"]["D_R"], mc)
            st["core"]["W2_book"] = sn
            st["core"]["W2_kill_zero_with_R1"] = max(max(v.values()) for v in kk.values())
            p(f"  stops, core account on W2 at the median book {sn}: zero-edge P(KILL) "
              f"{max(k_med.core_K_TR_zero, k_med.core_K_PR_zero) * 100:.2f}% -> {st['core']['W2_kill_zero_with_R1'] * 100:.2f}% with R1 acting")
            r["stops"] = st
        out[name] = r
    (HERE / f"risk_{a.stamp}.json").write_text(json.dumps(out, indent=1, default=float))
    (HERE / f"risk_output_{a.stamp}.txt").write_text("\n".join(say) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
