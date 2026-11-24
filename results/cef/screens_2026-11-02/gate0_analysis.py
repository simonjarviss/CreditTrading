"""Gate 0 of PREREG_C4_LEVEL: the survivorship evidence for the team lead's judgment. Zero trials, fit only.

THE RULING (team lead, 2026-11-02): "keep it flexible and make judgment off
results". Gate 0 is therefore a team-lead JUDGMENT on this output, recorded
post-data in docs/SYSTEM.md §5. It is not a mechanical gate. A gate decided
after its data are seen is not a pre-registered gate; this script supplies the
evidence, and nothing here passes or fails anything on its own. The trial's own
pass rule (PREREG §6.2) is unchanged.

WHAT IS COMPARED
----------------
At semiannual period-ends 2005-01-03 .. 2022-12-30, the slope of the forward
CRSP total return on the discount LEVEL against peers:
  A = survivors, C4's 65 fit funds. Level = CRSP trade close / the families
      panel NAV on the June/December period-end session.
  D = dead C4-family candidates. Level = CRSP trade close / the N-CSR or N-CSRS
      report NAV at the report's own period-end (pull 2,
      `ncsr_navs.parquet`).
  B = A and D together, the population the survivorship question is about.
y = compounded CRSP `ret` over sessions t+2 .. t+127 (H1: decide t, fill t+1),
in bp. On a delisting inside the window, `dlret` is added on the delisting day
and the position is cash afterwards. An observation whose delisting return is
missing is dropped and counted, never filled. Level and y are demeaned within
(family x calendar half-year) cells. Dead funds get their family from name
keywords, a proposal (`family_of`), and unmatched names are "unclassified".
The slope is pooled OLS on the demeaned values.

REPORTED (the team lead's list, 2026-11-02)
-------------------------------------------
* b_D / b_A and b_B / b_A, with 95% CIs from two bootstraps, each 2,000
  draws, seed 20261102. The headline is (1); the two are not averaged:
  - (1) by fund-half-year, as asked: rows resampled within A and within D;
  - (2) by calendar half-year, which keeps cross-sectional dependence.
* The sign test: the share of calendar half-years whose D-only slope is
  negative, with a two-sided binomial p. Also P(b_D >= 0) under bootstrap (1).
* The verdict under BOTH candidate rules, "b_B < 0 and b_B / b_A >= 0.5" (the
  original) and ">= 0.75" (amendment A1), each with its power P(flag | halving)
  and false-alarm rate P(flag | r = 1). These are recomputed at the realised NAV
  coverage with `gate0_coverage.py`'s formula.
* Coverage (NAV fund-half-years against candidate fund-half-years), the
  calibration agreement (report NAV against panel NAV for survivors), and the
  sensitivity with the "unclassified" dead funds excluded.

Run (from the worktree root):
    python3 -B results/cef/screens_2026-11-02/gate0_analysis.py              # after pull 2
    python3 -B results/cef/screens_2026-11-02/gate0_analysis.py --self-test  # code check: 15 survivors posing as "dead"
Writes gate0_analysis_output.txt and gate0_analysis.json beside itself (aggregates only).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

CACHE = HERE / "_cache_gate0"
FIT_START, FIT_END = pd.Timestamp("2005-01-03"), pd.Timestamp("2022-12-30")
A_H, B_H = 2, 127
SEED, DRAWS = 20261102, 2000
RULES = (0.5, 0.75)

FAMILY_RULES = (   # first match wins; a proposal for the family rulings, not a ruling
    ("equity_covered_call", r"COVERED CALL|BUY.?WRITE|OPTION|PREMIUM|ENHANCED"),
    ("preferred", r"PREFERRED|PFD"),
    ("equity_sector", r"REAL ESTATE|REIT|RLTY|REALTY|UTIL|ENERGY|MLP|INFRA|TECHNOLOGY|TECH\b|HEALTH|FINANCIAL|BANK|"
                      r"GOLD|NATURAL RES|RESOURCES|PETROLEUM|SCIENCE"),
    ("multi_asset", r"ALLOCATION|BALANCED|TOTAL RETURN|TOTAL RET|CAPITAL & INCOME|CAP & INC|INCOME"),
    ("equity_domestic", r"EQUITY|EQTY|DIVIDEND|DIV\b|GROWTH|VALUE|SMALL CAP|LARGE CAP|OPPORTUNIT|STOCK|FUND"),
)


def family_of(name: str) -> str:
    for fam, pat in FAMILY_RULES:
        if re.search(pat, name or "", re.I):
            return fam
    return "unclassified"


def crsp_frames():
    dsf = pd.read_parquet(CACHE / "cef_dsf.parquet", columns=["permno", "date", "prc", "ret"])
    dsf["date"] = pd.to_datetime(dsf["date"])
    dl = pd.read_parquet(CACHE / "cef_delist.parquet")
    dl["dlstdt"] = pd.to_datetime(dl["dlstdt"])
    if dsf.date.max() > FIT_END:
        raise AssertionError("dsf past the fit end")
    return dsf, dl


def forward(obs: pd.DataFrame, dsf: pd.DataFrame, dl: pd.DataFrame) -> pd.DataFrame:
    """y (bp) over global sessions t+2..t+127 after each observation's date t; delisting handled."""
    cal = pd.DatetimeIndex(sorted(dsf.date.unique()))
    R = dsf.pivot_table(index="date", columns="permno", values="ret")
    dlr = dl.set_index("permno")[["dlstdt", "dlret"]]
    out, dropped = [], {"window past the fit end": 0, "missing delisting return": 0, "no session": 0}
    for _, o in obs.iterrows():
        i = cal.searchsorted(o.date)
        if i >= len(cal) or cal[i] != o.date:
            dropped["no session"] += 1; continue
        lo, hi = i + A_H, i + B_H
        if hi >= len(cal):
            dropped["window past the fit end"] += 1; continue
        win = cal[lo:hi + 1]
        r = R[o.permno].reindex(win) if o.permno in R.columns else pd.Series(np.nan, index=win)
        dd = dlr.dlstdt.get(o.permno, pd.NaT)
        if pd.notna(dd) and win[0] <= dd <= win[-1]:
            d_ret = dlr.dlret.get(o.permno, np.nan)
            if pd.isna(d_ret):
                dropped["missing delisting return"] += 1; continue
            r = r[r.index < dd].fillna(0.0)
            g = float(np.prod(1 + r.to_numpy()) * (1 + d_ret) - 1)
        else:
            g = float(np.prod(1 + r.fillna(0.0).to_numpy()) - 1)   # an absent day: CRSP's next ret spans it
        out.append({**o.to_dict(), "y": g * 1e4})
    return pd.DataFrame(out), dropped


def survivors_obs(dsf: pd.DataFrame) -> pd.DataFrame:
    """C4's fit funds at June/December period-end sessions. The LEVEL is C4's own panel discount
    (`alpha_common.load_c4`: the families close over the families NAV, M1|M2 masked), so price and
    NAV share one share basis. CRSP's raw price over a yfinance NAV breaks around splits: the first
    build of this function gave b_B -3.07 against -27.24 on the panel's own basis. Returns are CRSP's
    (`forward`), the source the dead funds use."""
    import alpha_common as ac
    C = ac.load_c4()
    fz = pd.read_csv(REPO / "results" / "cef" / "c4" / "c4_universe_frozen_2026-10-14.csv")
    mp = pd.read_csv(REPO / "data" / "cef_families" / "crsp_permno_map.csv")
    mp = mp[mp.ticker.isin(C["U"])].dropna(subset=["current_permno"])
    perm = dict(zip(mp.ticker, mp.current_permno.astype(int)))
    fam = dict(zip(fz.ticker, fz.family))
    idx = C["idx"]
    ends = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).last()
    ends = pd.DatetimeIndex([d for d in ends.values if pd.Timestamp(d).month in (6, 12)])
    rows = []
    for t, p in perm.items():
        dsc = C["disc"][t]
        for d in ends:
            v = dsc.get(d, np.nan)
            if np.isfinite(v):
                rows.append(dict(permno=p, ticker=t, date=d, family=fam[t], level=float(v), src="A"))
    return pd.DataFrame(rows)


def dead_obs(dsf: pd.DataFrame, names: pd.DataFrame, nav_rows: pd.DataFrame | None = None) -> pd.DataFrame:
    n = pd.read_parquet(CACHE / "ncsr_navs.parquet") if nav_rows is None else nav_rows
    n = n.dropna(subset=["nav", "close"]).copy()
    n["period"] = pd.to_datetime(n["period"])
    n = n[(n.period >= FIT_START) & (n.period <= FIT_END)]
    px = dsf[dsf.prc > 0].sort_values("date")
    rows = []
    last_name = names.sort_values("nameenddt").groupby("permno")["comnam"].last()
    for _, r in n.iterrows():
        x = px[(px.permno == r.permno) & (px.date <= r.period)].tail(1)
        if x.empty or abs(float(x.prc.iloc[0]) - float(r.close)) > 0.005:
            continue          # the NAV was read against this close; any other date would mismatch the pair
        rows.append(dict(permno=int(r.permno), ticker=None, date=x.date.iloc[0],
                         family=family_of(last_name.get(r.permno, "")), level=100 * (r.close / r.nav - 1), src="D"))
    return pd.DataFrame(rows).drop_duplicates(["permno", "date"])


CELLS = "month"   # declared 2026-11-02, before any dead-fund NAV was read; "half" is the sensitivity


def demeaned(df: pd.DataFrame) -> pd.DataFrame:
    """Demean within (family x period-end calendar MONTH) cells (primary), or (family x half-year).
    Dead funds report at their own fiscal period-ends; a same-month cell keeps every
    comparison on nearly the same forward window, a half-year cell mixes windows up to 5
    months apart (so market moves leak into the demeaned return)."""
    d = df.copy()
    d["half"] = d.date.dt.year.astype(str) + "H" + np.where(d.date.dt.month <= 6, "1", "2")
    key = d.date.dt.to_period("M").astype(str) if CELLS == "month" else d.half
    d["cell"] = d.family + "|" + key
    k = d.groupby("cell")["level"].transform("size")
    d = d[k >= 2].copy()
    for c in ("level", "y"):
        d[c + "_dm"] = d[c] - d.groupby("cell")[c].transform("mean")
    return d


def slope(d: pd.DataFrame) -> float:
    x, y = d.level_dm.to_numpy(), d.y_dm.to_numpy()
    sxx = x @ x
    return float((x @ y) / sxx) if sxx > 0 else np.nan


def slope_t(d: pd.DataFrame) -> tuple[float, float]:
    """Pooled slope with half-year-clustered SE."""
    b = slope(d)
    e = d.y_dm - b * d.level_dm
    sxx = (d.level_dm ** 2).sum()
    g = (d.level_dm * e).groupby(d.half).sum()
    G = len(g)
    se = np.sqrt((g ** 2).sum() * G / (G - 1)) / sxx
    return b, b / se


def three(A: pd.DataFrame, D: pd.DataFrame) -> tuple[float, float, float]:
    a, dd = demeaned(A), demeaned(D)
    bb = demeaned(pd.concat([A, D]))
    return slope(a), slope(dd), slope(bb)


def p_flag(bA, tA, nA, n_obs, n_pop, r, thr):
    """gate0_coverage.py's formula: P(b_B_hat / b_A_hat < thr) when the population all-fund slope is r x b_A."""
    w_pop = nA / (nA + n_pop)
    bD = (r - w_pop) / (1 - w_pop) * bA
    if n_obs <= 0:
        return 0.0
    w = nA / (nA + n_obs)
    VA = (bA / tA) ** 2
    VD = VA * nA / n_obs
    mx = w * bA + (1 - w) * bD - thr * bA
    vx = (w - thr) ** 2 * VA + (1 - w) ** 2 * VD
    return float(stats.norm.sf(-mx / np.sqrt(vx)) if bA < 0 else stats.norm.cdf(-mx / np.sqrt(vx)))


def analyse(A: pd.DataFrame, D: pd.DataFrame, n_pop: float, say) -> dict:
    a, d, bpop = demeaned(A), demeaned(D), demeaned(pd.concat([A, D]))
    bA, tA = slope_t(a)
    bD, tD = slope_t(d) if len(d) > 2 else (np.nan, np.nan)
    bB, tB = slope_t(bpop)
    say(f"   levels beyond +-50pp (kept, flagged): A {int((A.level.abs() > 50).sum())}, D {int((D.level.abs() > 50).sum())}")
    say(f"   obs: A {len(a)} fund-half-years ({a.permno.nunique()} funds), D {len(d)} ({d.permno.nunique()} funds); "
        f"cells with >= 2 obs")
    say(f"   slopes, bp per pp (half-year-clustered t): b_A {bA:+.2f} (t {tA:+.2f}); b_D {bD:+.2f} (t {tD:+.2f}); "
        f"b_B {bB:+.2f} (t {tB:+.2f})")
    rng = np.random.default_rng(SEED)
    bs1, bs2 = [], []
    halves = sorted(set(A.date.dt.year.astype(str) + np.where(A.date.dt.month <= 6, "1", "2")) |
                    set(D.date.dt.year.astype(str) + np.where(D.date.dt.month <= 6, "1", "2")))
    hA = A.date.dt.year.astype(str) + np.where(A.date.dt.month <= 6, "1", "2")
    hD = D.date.dt.year.astype(str) + np.where(D.date.dt.month <= 6, "1", "2")
    for _ in range(DRAWS):
        A1 = A.iloc[rng.integers(0, len(A), len(A))]
        D1 = D.iloc[rng.integers(0, len(D), len(D))]
        x = three(A1, D1)
        bs1.append((x[1] / x[0], x[2] / x[0], x[1]))
        pick = rng.choice(halves, len(halves))
        A2 = pd.concat([A[hA == h] for h in pick])
        D2 = pd.concat([D[hD == h] for h in pick])
        y = three(A2, D2)
        bs2.append((y[1] / y[0], y[2] / y[0], y[1]))
    bs1, bs2 = np.array(bs1), np.array(bs2)
    ci = lambda v: (float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5)))
    rD, rB = bD / bA, bB / bA
    say(f"   ratio b_D/b_A {rD:+.3f}: 95% CI (1) fund-half-year {ci(bs1[:, 0])[0]:+.3f} .. {ci(bs1[:, 0])[1]:+.3f}; "
        f"(2) calendar half-year {ci(bs2[:, 0])[0]:+.3f} .. {ci(bs2[:, 0])[1]:+.3f}")
    say(f"   ratio b_B/b_A {rB:+.3f}: 95% CI (1) {ci(bs1[:, 1])[0]:+.3f} .. {ci(bs1[:, 1])[1]:+.3f}; "
        f"(2) {ci(bs2[:, 1])[0]:+.3f} .. {ci(bs2[:, 1])[1]:+.3f}")
    per = {h: slope(g) for h, g in d.groupby("half") if len(g) >= 3}
    neg = sum(v < 0 for v in per.values() if np.isfinite(v))
    tot = sum(np.isfinite(v) for v in per.values())
    p_sign = float(stats.binomtest(neg, tot, 0.5).pvalue) if tot else np.nan
    say(f"   sign test, D-only slope per calendar half-year: negative in {neg} of {tot} (two-sided binomial p {p_sign:.3f}); "
        f"P(b_D >= 0) under bootstrap (1) {float(np.mean(bs1[:, 2] >= 0)):.3f}")
    nA, nD = len(a), len(d)
    say(f"   the two candidate rules (b_B < 0 and b_B/b_A >= threshold); power and false-alarm at this coverage "
        f"(D {nD} of {n_pop:.0f} candidate fund-half-years):")
    verdicts = {}
    for thr in RULES:
        ok = bool(bB < 0 and rB >= thr)
        pw, fa = p_flag(bA, tA, nA, nD, n_pop, 0.5, thr), p_flag(bA, tA, nA, nD, n_pop, 1.0, thr)
        lo1 = ci(bs1[:, 1])[0]
        verdicts[str(thr)] = dict(met=ok, power_halving=pw, false_alarm=fa, ci1_low_above=bool(lo1 >= thr))
        say(f"     >= {thr:<5}: {'MET' if ok else 'NOT MET'} (point); CI (1) lower bound {'>=' if lo1 >= thr else '<'} {thr}; "
            f"P(flag | halving) {pw:.2f}, P(flag | r = 1) {fa:.2f}")
    return dict(bA=bA, tA=tA, bD=bD, tD=tD, bB=bB, tB=tB, ratio_D=rD, ratio_B=rB,
                ci_ratio_D_fhy=ci(bs1[:, 0]), ci_ratio_D_half=ci(bs2[:, 0]),
                ci_ratio_B_fhy=ci(bs1[:, 1]), ci_ratio_B_half=ci(bs2[:, 1]),
                sign_negative=neg, sign_total=tot, sign_p=p_sign, p_bD_nonneg=float(np.mean(bs1[:, 2] >= 0)),
                nA=nA, nD=nD, rules=verdicts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    lines = []
    say = lambda s="": (print(s), lines.append(s))
    import alpha_common as ac
    say(ac.header("GATE 0: survivorship evidence for the team lead's judgment (zero trials; post-data, NOT a mechanical gate)"))
    dsf, dl = crsp_frames()
    names = pd.read_parquet(CACHE / "cef_names.parquet")
    names["nameenddt"] = pd.to_datetime(names["nameenddt"])
    A = survivors_obs(dsf)
    A, dropA = forward(A, dsf, dl)
    if a.self_test:
        pose = sorted(A.permno.unique())[:15]
        D, A = A[A.permno.isin(pose)].assign(src="D"), A[~A.permno.isin(pose)]
        say(f"SELF-TEST: 15 survivors pose as 'dead' (their own panel NAV); the ratio should sit near 1 within its CI")
        res = analyse(A, D, n_pop=float(len(D)), say=say)
        lo, hi = res["ci_ratio_B_fhy"]
        assert lo < 1.0 < hi, f"no survivorship by construction, yet b_B/b_A's CI ({lo:.3f}, {hi:.3f}) excludes 1"
        print("self-test passed: survivors posing as dead give b_B/b_A's CI around 1")
        return 0
    man = json.loads((CACHE / "ncsr_manifest.json").read_text())
    D = dead_obs(dsf, names)
    D, dropD = forward(D, dsf, dl)
    say(f"inputs: pull 1 manifest {json.loads((CACHE / 'manifest.json').read_text())['pulled_utc']}; pull 2 manifest "
        f"{man['pulled_utc']}: {man['navs']} NAVs for {man['funds_with_a_nav']} of {man['candidates']} candidates; "
        f"coverage {man['coverage_for_the_80pct_rule']:.1%}")
    say(f"dropped: survivors {dropA}; dead {dropD}")
    cal = pd.read_parquet(CACHE / "ncsr_calibration.parquet").dropna()
    if len(cal):
        agree = float(((cal.report_nav / cal.panel_nav - 1).abs() <= 0.01).mean())
        say(f"calibration: report NAV vs panel NAV within 1% on {agree:.0%} of {len(cal)} survivor reports")
    n_pop = float(man["candidate_fund_half_years"])
    out = {}
    global CELLS
    for cells in ("month", "half"):
        CELLS = cells
        for lab, DD in (("ALL dead candidates", D), ("dead, unclassified names excluded", D[D.family != "unclassified"])):
            tag = f"{lab}; cells family x {'period-end month (PRIMARY)' if cells == 'month' else 'half-year (sensitivity)'}"
            say(f"\n{tag}:")
            out[tag] = analyse(A, DD, n_pop, say)
    CELLS = "month"
    say("\nREAD AS: evidence for the team lead's Gate 0 judgment, recorded post-data in docs/SYSTEM.md §5. "
        "The trial's own pass rule (PREREG §6.2) is unchanged.")
    (HERE / "gate0_analysis_output.txt").write_text("\n".join(lines) + "\n")
    (HERE / "gate0_analysis.json").write_text(json.dumps(out, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
