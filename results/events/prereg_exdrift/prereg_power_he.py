"""r8: power on the clean test set for the declared hedge H-E, from fit DISPERSION (prereg_inputs_b3.json)
and r6's published mean (CAR -20.454bp) as the assumed effect, scaled 1, 1/2, 1/4. Arithmetic only [U];
the _dsr bar and its sampling error come from scripts/xasset/slate_feasibility (which invert validate._dsr)."""
import sys, json, math
from pathlib import Path
from statistics import NormalDist
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent / "tree"))
from scripts.xasset.slate_feasibility import required_sharpe, power, p_alpha_t, alpha_t_bar
b3 = json.loads((HERE / "prereg_inputs_b3.json").read_text()); p1 = json.loads((HERE / "prereg_inputs.json").read_text())
Nd = NormalDist(); T = p1["test"]["sessions"]; M = p1["test"]["months"]
epm_fit = b3["he_events"] / b3["he_months"]; out = {}
print(f"T_test {T} sessions, {M} months; fit {b3['he_events']} events / {b3['he_months']} months = {epm_fit:.1f} per month")
for lab, nev in (("17", b3["test_traded"]), ("13", b3["test_traded_13"])):
    epm = nev / M; se = b3["he_sd_month_mean"] * math.sqrt(epm_fit / epm) / math.sqrt(M)
    for f in (1.0, 0.5, 0.25):
        mu = f * 20.454; t = mu / se
        out[f"event_{lab}_{f}"] = dict(mu=mu, se=se, t=t, p2=1 - Nd.cdf(2 - t))
        print(f"names {lab} ({nev} events, {epm:.1f}/month): true mean {mu:5.1f}bp, SE {se:.2f}bp, expected t {t:.2f}, P(t>=2) {1-Nd.cdf(2-t):.2f}")
for f in (1.0, 0.5, 0.25):
    sr = (f * 20.454 * epm_fit) / b3["he_sd_month_sum"] * math.sqrt(12)
    out[f"sleeve_{f}"] = dict(sr=sr, **{f"p_N{N}": power(sr, N, T) for N in (6, 7, 8)}, p_alpha3=p_alpha_t(sr, T))
    print(f"sleeve SR [U] {sr:.2f} (equal $ per event): P(_dsr>0.95) N6 {power(sr,6,T):.2f} N7 {power(sr,7,T):.2f} N8 {power(sr,8,T):.2f}; P(alpha t>=3) {p_alpha_t(sr,T):.2f}")
print("Sharpe needed:", {N: round(required_sharpe(N, T), 3) for N in (1, 6, 7, 8, 53)}, "; alpha-t bar IR", round(alpha_t_bar(T), 3))
for mths in (12, 24):
    for lab, nev in (("13", b3["test_traded_13"]),):
        epm = nev / M; se = b3["he_sd_month_mean"] * math.sqrt(epm_fit / epm) / math.sqrt(mths)
        t = 20.454 / se; Tm = 21 * mths
        sr = (20.454 * epm_fit) / b3["he_sd_month_sum"] * math.sqrt(12)
        out[f"fwd_{mths}"] = dict(t=t, p2=1 - Nd.cdf(2 - t), p2_half=1 - Nd.cdf(2 - t / 2), req6=required_sharpe(6, Tm), p6=power(sr, 6, Tm))
        print(f"forward paper {mths}m, 13 names: expected t {t:.2f}, P(t>=2) {1-Nd.cdf(2-t):.2f} (half {1-Nd.cdf(2-t/2):.2f}); N6 Sharpe needed {required_sharpe(6,Tm):.2f}, P(pass) at {sr:.2f}: {power(sr,6,Tm):.2f}")
json.dump(out, open(HERE / "prereg_power_he.json", "w"), indent=1)
