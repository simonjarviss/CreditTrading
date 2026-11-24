"""Re-open (3): could a TERM-hedged X3 ever pass, judged on a forward record? Zero trials.

WHY. X3 (XASSET-2, month-end Treasury extension) is the slate's one real effect:
gross Sharpe 1.04, alpha t 4.54. It failed D4 on a TERM beta of 0.34, and is D2 at
15bp. Its fit and its holdout have both been seen (results/xasset/
XASSET_RESULTS_2026-10-14.md), so a hedged variant scored on that history is post
hoc. The only clean evidence is a forward record, so the power check is: what is
the chance that a forward record of Y years clears the XASSET deflated-Sharpe gate?
The gate is the team lead's 2026-10-28 safeguarded paper bar, as a fifth declared
test (inference.safeguarded_sr0, with rho and V from the registry's four stored
XASSET series). It reads no returns, only the registry's bar inputs.
"""
from __future__ import annotations

from math import sqrt

from scripts.research import inference as I
from scripts.research import registry as R

SLATE_N = 5                       # the closed slate of 4, plus this one test, declared
SHARPES = (0.44, 0.55, 1.0)       # X3 under T+1 / X3 net@5bp, unhedged / X3 gross: XASSET_RESULTS [S]
YEARS = (1, 2, 3, 5, 10)


def p_pass(sr_annual: float, years: float, rho: float, sr_var: float, conf: float = 0.95) -> float:
    """P(SR_hat clears SR0 + z_conf·SE) at a true annualised Sharpe, normal returns."""
    T = int(years * 252)
    sr = sr_annual / sqrt(252)
    sr0 = I.safeguarded_sr0(SLATE_N, rho, sr_var, T)
    se = sqrt((1 + 0.5 * sr ** 2) / (T - 1))
    return 1 - I._N.cdf((sr0 + I._N.inv_cdf(conf) * se - sr) / se)


def main() -> int:
    b = R.bar_inputs("XASSET")
    if not b["paper_bar_may_gate"]:
        raise SystemExit("XASSET is not fully covered in the registry; the safeguarded bar does not apply")
    print(f"XASSET bar inputs: rho {b['rho_bar']:.3f}, V {b['sr_var']:.3g}, declared N for the test {SLATE_N}")
    for sr in SHARPES:
        cells = ", ".join(f"{y}y {p_pass(sr, y, b['rho_bar'], b['sr_var']):.2f}" for y in YEARS)
        print(f"true SR {sr}: {cells} | 80% power, 5% two-sided: {I.years_needed(sr):.1f}y")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
