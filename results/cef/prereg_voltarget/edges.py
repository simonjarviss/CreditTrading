"""What the raised book earns, gross and net, if the edge is lower than the fit path's (CEF trial 53, DRAFT).

    python3 results/cef/prereg_voltarget/edges.py      (after risk.py)
        -> edges_2026-10-30.json, edges_output_2026-10-30.txt

ARITHMETIC ON STATED ASSUMPTIONS [U], not a new statistic. Each account's fit-path gross return at the
ruled multipliers (risk.py, W1, the house cap model) is scaled by (assumed Sharpe / fit-path Sharpe):
the account's realised vol and turnover are held at their fit-path values. The edges, and where each
comes from:
  fit path      the W1 series themselves                                        [V risk.py]
  own window    C4 at its own 2005-02-22..2022-12-30 Sharpe (spec book)          [V SCRATCH/alloc4 c4spec_meta.json]
  C4 holdout    C4 at its committed holdout gross Sharpe 0.725                   [doc docs/RESEARCH_STATE.md, C4 row]
                (corrected book 1.434, the verdict; both shown)
  half          every sleeve at half its fit-path Sharpe
The core's only v7 Sharpe that excludes 2023+ is the fit path's (0.955); its 2024-26 holdout was opened
on 2026-07-31 for a different config (pre-clean-slate:results/cef/HOLDOUT_OPENED.json), so no out-of-
sample core edge is used. Net = gross - turnover x cost (evaluate()'s one-way turnover units).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAMP = "2026-10-30"
C4_OWN = {"TR": 1.2002684537305317, "PR": 1.3442086385730083}   # SCRATCH/alloc4/series/c4spec_meta.json [V there]
C4_HOLDOUT = {"committed": 0.725, "corrected": 1.434}             # [doc] docs/RESEARCH_STATE.md, C4 row (total return)


def main() -> int:
    R = json.loads((HERE / f"risk_{STAMP}.json").read_text())["ruled"]
    say, out = [], {}

    def p(*x):
        s = " ".join(str(v) for v in x)
        print(s, flush=True)
        say.append(s)

    for b in ("TR", "PR"):
        g = {k: R[f"{k}_{b}_W1"]["ann"] for k in ("core", "c4")}
        s = {k: R[f"{k}_{b}_W1"]["sr"] for k in ("core", "c4")}
        vol = R[f"comb_{b}_W1"]["vol"]
        t = {k: R[f"{k}_turn_yr"] for k in ("core", "c4")}
        cases = {"fit path": (s["core"], s["c4"]), "C4 own window": (s["core"], C4_OWN[b]),
                 "C4 holdout, corrected (the verdict)": (s["core"], C4_HOLDOUT["corrected"]),
                 "C4 holdout, as committed": (s["core"], C4_HOLDOUT["committed"]),
                 "half of fit path": (s["core"] / 2, s["c4"] / 2)}
        p(f"\n{b}: ruled core x{R['m_core']} / C4 x{R['m_c4']}; combined vol {vol * 100:.2f}% (W1); turnover core "
          f"{t['core']:.1f}, C4 {t['c4']:.1f}, combined {(t['core'] + t['c4']) / 2:.1f}/yr")
        for lab, (sc, s4) in cases.items():
            gc, g4 = g["core"] * sc / s["core"], g["c4"] * s4 / s["c4"]
            gg = 0.5 * gc + 0.5 * g4
            tt = 0.5 * t["core"] + 0.5 * t["c4"]
            net = {bp: (gg - tt * bp * 1e-4) * 100 for bp in (5, 15, 30)}
            be = gg / tt * 1e4
            be4 = g4 / t["c4"] * 1e4
            out[f"{b} {lab}"] = dict(sr_core=sc, sr_c4=s4, gross=gg, sharpe=gg / vol, net_pct=net, breakeven_bp=be,
                                     c4_account_breakeven_bp=be4)
            p(f"  {lab:36s} SR core {sc:.3f} C4 {s4:.3f} -> gross {gg * 100:5.2f}%/yr, Sharpe {gg / vol:.2f}; net "
              + " / ".join(f"{v:+.2f}" for v in net.values()) + f" %/yr at 5/15/30bp; breakeven {be:.1f}bp (C4 account {be4:.1f}bp)")
    (HERE / f"edges_{STAMP}.json").write_text(json.dumps(out, indent=1))
    (HERE / f"edges_output_{STAMP}.txt").write_text("\n".join(say) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
