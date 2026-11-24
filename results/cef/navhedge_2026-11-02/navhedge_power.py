"""Stage-0 power arithmetic for the NAV-hedge screen. NO DATA IS READ.
Every input is a documented figure passed on the command line below; the output
is arithmetic on them through scripts/research/inference.py.

Paired Sharpe-difference under an oracle hedge (true beta, no estimation error):
  hedged r_H = a + e, unhedged r_B = a + b f + e, R2 = var(b f)/var(r_B), rho = sqrt(1-R2)
  H0 (exposure unpriced): dSR = SR_B (1/rho - 1)          (variance removed, mean unchanged)
  SE(dSR_annual) ~= sqrt(2 (1 - rho) / years)              (Memmel 2003 leading term; derived
                                                            here from the noise in mean(b f))
So the expected z = SR_B (1/rho - 1) / sqrt(2 (1-rho)/years). Upper bound: frozen betas
remove less than R2 (ex-date amendment 1 showed exactly that), and they cost estimation noise."""
import sys
from math import sqrt
sys.path.insert(0, ".")
from scripts.research import inference as inf

T = 2398                 # live 2013-06 -> 2022 sessions, PORTFOLIO_FRAMEWORK §6.4 [S]
Y = T / 252
KURT = 3 + 12.1          # deployed v7 excess kurtosis 12.1 on 2013-22, PORTFOLIO_FRAMEWORK §6.3 [S]

def paired(sr_b, r2, years=Y):
    rho = sqrt(1 - r2)
    d = sr_b * (1 / rho - 1)
    se = sqrt(2 * (1 - rho) / years)
    return d, se, d / se

print(f"years {Y:.2f}  T {T}  kurt(raw) {KURT}")
alpha54 = 1 - 0.95 ** (1 / 54)
z54 = inf.z_crit(alpha54)        # read_result's Sidak two-sided at N=54
alpha1 = 0.05
print(f"read_result Sidak z at N=54: {z54:.3f}; at N=1: {inf.z_crit(alpha1):.3f}")
print("\nA. paired dSR (hedged - unhedged), oracle hedge, H0 exposure unpriced")
print(" SR_B   R2     dSR    SE     E[z]  P(z>1.645) P(z>1.96) P(PRESENT,N=54)")
for sr_b in (0.67, 0.96):
    for r2 in (0.011, 0.018, 0.074, 0.091, 0.30, 0.50, 0.75):
        d, se, z = paired(sr_b, r2)
        print(f" {sr_b:.2f}  {r2:.3f}  {d:.4f} {se:.4f} {z:5.2f}  {inf.power_of_z(z, 0.05, False):.3f}"
              f"      {inf.p_clear_bar(z, 1.96):.3f}     {inf.p_clear_bar(z, z54):.3f}")

def r2_needed(sr_b, target_p, crit, years=Y):
    lo, hi = 1e-6, 0.999
    for _ in range(200):
        mid = (lo + hi) / 2
        _, _, z = paired(sr_b, mid, years)
        if inf.p_clear_bar(z, crit) < target_p: lo = mid
        else: hi = mid
    return hi
print("\nR2 the hedge must remove for P(pass)=0.5:")
for sr_b in (0.67, 0.96):
    print(f" SR_B {sr_b}: one-sided 5% {r2_needed(sr_b, 0.5, 1.645):.3f}; "
          f"t>=1.96 {r2_needed(sr_b, 0.5, 1.96):.3f}; Sidak N=54 {r2_needed(sr_b, 0.5, z54):.3f}")

print("\nB. DSR > 0.95 on the HEDGED book's own Sharpe (oracle uplift SR_B/rho), desk bar")
print(" SR_B  R2     SR_H   N=54(CEF) N=1(MACRO) [skew 0, kurt as above]")
for sr_b in (0.67, 0.96):
    for r2 in (0.0, 0.018, 0.091):
        srh = sr_b / sqrt(1 - r2)
        p54 = inf.p_pass_dsr(srh, T, 54, bound="upper", kurt=KURT)
        p1 = inf.p_pass_dsr(srh, T, 1, bound="upper", kurt=KURT)
        print(f" {sr_b:.2f}  {r2:.3f}  {srh:.3f}  {p54:.3f}     {p1:.3f}")
