"""Gate 0 of PREREG_C4_LEVEL, step 1: does the team lead's CRSP pull give enough NAVs? Zero trials, fit only.

Reads the gitignored pull (`_cache_gate0/`, run by the team lead on 2026-11-02;
manifest.json) and answers, before any Gate 0 statistic is formed:

  Q1 How many of the CRSP mutual-fund NAV matches are GENUINE: the same fund,
     not a recycled ticker? A match is genuine only if (a) it matched on CUSIP,
     or (b) the MF fund's name scores >= 0.5 against the CEF's CRSP name (the
     census's own loose check, `edgar_merger_dates.name_score`) AND its NAV
     months overlap the CEF's own share-code 14/44 listing. Of the genuine,
     how many are DEAD (delisted <= 2022-12-30) and in C4's five families?
  Q2 The dead set: every CRSP CEF permno (shrcd 14/44) with a listing inside
     2005-01-03..2022-12-30 and a delisting <= 2022-12-30, minus C4's 74 and the
     44 credit universe names, classified by name keywords into C4-family
     candidates, OUT (credit, muni, global/country, convertible) or UNKNOWN.
     A proposal for Gate 0's family rulings, not a ruling.
  Q3 Power. With n_D dead funds added to the 65 survivors, P(Gate 0 flags) when
     the true all-fund slope is r x the survivor slope, under the pre-stated
     rule (PASS iff b_B < 0 and b_B / b_A >= 0.5). b_A's semiannual t is
     measured on the survivors' own panel NAV at June/December month-ends
     (the period-ends most N-CSRs report), forward CRSP-style total return
     t+2..t+127 from the yfinance leg, within-family demeaned, clustered by
     half-year. b_B = w b_A + (1 - w) b_D with w = the survivors' share of
     fund-half-years; b_D independent of b_A with variance V_A x n_A / n_D.
  Q4 The second pull's scope: N-CSR/N-CSRS filings in EDGAR's quarterly master
     indexes (the census's cached index, 2008-Q1 onward) whose filer maps to a
     dead candidate permno (the census's `CrspMap`), by year.

Run (from the worktree root):  python3 -B results/cef/screens_2026-11-02/gate0_coverage.py
Writes gate0_coverage_output.txt beside itself (aggregates only; no CRSP rows).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import alpha_common as ac  # noqa: E402

CACHE = HERE / "_cache_gate0"
FIT_START, FIT_END = pd.Timestamp("2005-01-03"), pd.Timestamp("2022-12-30")
OUT_RE = re.compile(r"MUNI|MUN\b|MUNICIPAL|TAX[- ]?FREE|TAX[- ]?EXEMPT|INSURED|BOND|INCOME OPP|HIGH YIELD|HI YLD|HIGH INC|"
                    r"HI INC|CREDIT|FLOAT|LOAN|SENIOR|MORTGAGE|MTG|GOVT|GOVERNMENT|TREASURY|INFLAT|DEBT|FIXED|INV GR|"
                    r"INVT GR|INVESTMENT GRADE|QUALITY|QLTY|TERM TR|TARGET TERM|STRATEGIC INC|INCOME TR|INCOME FD|"
                    r"INCM|DURATION|EMERGING MKTS DEBT|CONVERT|CONV\b", re.I)
GLOBAL_RE = re.compile(r"\bFUND INC\b.*\b(BRAZIL|KOREA|INDIA|CHINA|JAPAN|MEXICO|CHILE|TAIWAN|THAI|ISRAEL|IRISH|SWISS|"
                       r"GERMANY|FRANCE|ITALY|SPAIN|TURKISH|ASIA|EUROPE|LATIN|PACIFIC|EMERGING|GLOBAL|INTL|WORLD)|"
                       r"\b(BRAZIL|KOREA|INDIA|CHINA|JAPAN|MEXICO|CHILE|TAIWAN|THAI|ISRAEL|IRISH|SWISS|GERMANY|FRANCE|"
                       r"ITALY|SPAIN|TURKISH|ASIA|EUROPE|LATIN|PACIFIC|EMERGING|GLOBAL|INTL|INTERNATIONAL|WORLD)\b", re.I)
C4_RE = re.compile(r"EQUITY|EQTY|DIVIDEND|DIV\b|GROWTH|VALUE|REAL ESTATE|REIT|RLTY|REALTY|UTIL|ENERGY|MLP|INFRA|"
                   r"COVERED CALL|BUY.?WRITE|OPTION|PREMIUM|ENHANCED|TOTAL RETURN|TOTAL RET|PREFERRED|PFD|"
                   r"TECHNOLOGY|TECH\b|HEALTH|FINANCIAL|BANK|GOLD|NATURAL RES|RESOURCES|SMALL CAP|LARGE CAP|"
                   r"OPPORTUNIT|ALLOCATION|BALANCED|CAPITAL & INCOME|CAP & INC", re.I)


def classify(name: str) -> str:
    n = name or ""
    if OUT_RE.search(n) and not re.search(r"PREFERRED|PFD|EQUITY|EQTY|DIVIDEND", n, re.I):
        return "out:credit/muni/conv"
    if GLOBAL_RE.search(n):
        return "out:global/country"
    if C4_RE.search(n):
        return "C4-candidate"
    return "unknown"


def main() -> int:
    lines = []
    say = lambda s="": (print(s), lines.append(s))
    say(ac.header("GATE 0 COVERAGE: is the CRSP pull enough? (zero trials)"))
    nm = pd.read_parquet(CACHE / "cef_names.parquet")
    for c in ("namedt", "nameenddt"):
        nm[c] = pd.to_datetime(nm[c])
    dl = pd.read_parquet(CACHE / "cef_delist.parquet")
    dl["dlstdt"] = pd.to_datetime(dl["dlstdt"])
    mf = pd.read_parquet(CACHE / "mf_matches.parquet")
    nav = pd.read_parquet(CACHE / "mf_monthly_nav.parquet")
    nav["caldt"] = pd.to_datetime(nav["caldt"])
    from scripts.events.edgar_merger_dates import name_score, name_tokens

    # ---- Q1: genuine matches
    say(f"\nQ1. CRSP-MF matches {len(mf)}; NAV rows {len(nav)} for {nav.crsp_fundno.nunique()} funds")
    gen = []
    for _, r in mf.iterrows():
        cus = nm[nm.ncusip.isin([r.cusip8, r.ncusip])]
        tk = nm[(nm.ticker == r.ticker) | (nm.ticker == (r.ticker[1:-1] if isinstance(r.ticker, str) and len(r.ticker) == 5 else None))]
        cand = pd.concat([cus, tk]).drop_duplicates()
        months = nav[nav.crsp_fundno == r.crsp_fundno]["caldt"]
        best = None
        for _, c in cand.iterrows():
            sc = name_score(name_tokens(c.comnam or ""), name_tokens(r.fund_name or "")) if c.comnam and r.fund_name else -1
            inl = (months >= c.namedt) & (months <= c.nameenddt)
            ov = int(inl.sum())
            ov_fit = int((inl & (months >= FIT_START) & (months <= FIT_END)).sum())
            g = (len(cus) > 0) or (sc >= 0.5 and ov > 0)
            if best is None or (g, sc) > (best[0], best[1]):
                best = (g, sc, ov, int(c.permno), c.comnam, ov_fit)
        if best:
            gen.append(dict(fundno=int(r.crsp_fundno), mf=r.fund_name[:40], cef=best[4], permno=best[3],
                            score=round(best[1], 2), overlap_months=best[2], genuine=best[0], cusip=len(cus) > 0,
                            fit_months=best[5]))
    G = pd.DataFrame(gen)
    say(f"   matched on CUSIP: {int(G.cusip.sum())}; genuine (CUSIP, or name score >= 0.5 with NAV inside the CEF listing): "
        f"{int(G.genuine.sum())}")
    for _, r in G[G.score >= 0.3].iterrows():
        say(f"     {r.mf:<40} ~ {r.cef:<34} score {r.score:.2f}, NAV months inside the CEF listing {r.overlap_months}, "
            f"genuine {r.genuine}")
    gp = set(G.loc[G.genuine, "permno"])
    dead_g = dl[dl.permno.isin(gp) & (dl.dlstdt <= FIT_END) & (dl.dlstcd != 100)]
    say(f"   genuine and DEAD (delisted <= {FIT_END.date()}): {len(dead_g)}; of those in C4's families: see Q2's classes "
        f"({', '.join(classify(n) for n in nm[nm.permno.isin(dead_g.permno)].drop_duplicates('permno').comnam)})")

    # ---- Q2: the dead set
    fam = pd.read_csv(ac.WT / "data" / "cef_families" / "crsp_permno_map.csv")
    c4 = set(pd.read_csv(ac.WT / "results" / "cef" / "c4" / "c4_universe_frozen_2026-10-14.csv").ticker)
    pcol = "current_permno" if "current_permno" in fam.columns else "permno"
    c4perm = set(fam.loc[fam.ticker.isin(c4), pcol].dropna().astype(int))
    life = nm.groupby("permno").agg(first=("namedt", "min"), last=("nameenddt", "max"), name=("comnam", "last"))
    life = life.join(dl.set_index("permno")[["dlstdt", "dlstcd"]])
    inwin = (life["last"] >= FIT_START) & (life["first"] <= FIT_END)
    dead = life[inwin & (life.dlstdt <= FIT_END) & (life.dlstcd != 100) & ~life.index.isin(c4perm)].copy()
    dead["cls"] = dead["name"].map(classify)
    dead["years_in_fit"] = ((dead.dlstdt.clip(upper=FIT_END) - dead["first"].clip(lower=FIT_START)).dt.days / 365.25).clip(lower=0)
    say(f"\nQ2. CRSP CEF permnos {nm.permno.nunique()}; listed inside the fit window {int(inwin.sum())}; "
        f"C4's 74 mapped to {len(c4perm)} permnos (excluded)")
    say(f"   DEAD inside the fit window (delisted <= {FIT_END.date()}): {len(dead)}, by name class:")
    for k, g in dead.groupby("cls"):
        say(f"     {k:<22} {len(g):>4} funds, {g.years_in_fit.sum() * 2:>6.0f} fund-half-years in 2005-22; "
            f"delist codes {g.dlstcd.value_counts().head(4).to_dict()}")
    cand = dead[dead.cls.isin(["C4-candidate", "unknown"])]

    # ---- Q3: power, from the survivors' own semiannual slope
    D = ac.load_c4()
    elig = D["z"].notna() & D["disc"].notna()
    lvl = ac.cs_demean(D["disc"].where(elig), D["grp"])
    y = ac.cs_demean(ac.fwd(D["r_tr"], 2, 127).where(elig), D["grp"]) * 1e4
    idx = D["idx"]
    ends = pd.Series(idx, index=idx).groupby([idx.year, (idx.month - 1) // 6]).last().values
    ends = pd.DatetimeIndex(ends)
    ends = ends[(ends.month.isin([6, 12])) & (ends <= FIT_END - pd.Timedelta(days=190))]
    a = ac.pooled_ols(y, {"lvl": lvl}, ends, min_n=ac.MIN_NAMES)
    bA, tA, nA_fhy = a["lvl"]["coef"], a["lvl"]["t"], a["n"]
    say(f"\nQ3. survivors' semiannual slope (June/Dec month-ends, t+2..t+127, z out): b_A {bA:+.2f}bp/pp, t {tA:+.2f}, "
        f"{nA_fhy} fund-half-years on {a['dates']} dates")
    V_A = (bA / tA) ** 2
    n_pop = float(cand.years_in_fit.sum() * 2)          # every dead candidate fund-half-year, if all had a NAV
    w_pop = nA_fhy / (nA_fhy + n_pop)

    def p_flag(n_obs: float, r: float, thr: float) -> float:
        """P(b_B_hat / b_A_hat < thr) when the POPULATION all-fund slope is r x b_A.
        The dead funds' slope that implies it: b_D = (r - w_pop) / (1 - w_pop) x b_A. The
        estimator sees n_obs dead fund-half-years: E[b_B] = w_obs b_A + (1 - w_obs) b_D,
        b_D_hat independent of b_A_hat with variance V_A x n_A / n_obs."""
        bD = (r - w_pop) / (1 - w_pop) * bA
        if n_obs <= 0:
            return 0.0 if thr < 1 else 1.0
        w = nA_fhy / (nA_fhy + n_obs)
        V_D = V_A * nA_fhy / n_obs
        mean_x = w * bA + (1 - w) * bD - thr * bA        # flag if X > 0, since bA < 0
        var_x = (w - thr) ** 2 * V_A + (1 - w) ** 2 * V_D
        return float(stats.norm.sf(-mean_x / np.sqrt(var_x)))
    g_fhy = float(G.loc[G.genuine & G.permno.isin(cand.index), "fit_months"].sum() / 6)
    say(f"   population: survivors {nA_fhy} + dead candidates (C4-candidate + unknown) {n_pop:.0f} fund-half-years; "
        f"survivors' share {w_pop:.3f}")
    say("   P(Gate 0 flags, HALT or FAIL) for a true all-fund slope r x b_A:")
    say(f"     {'NAV coverage of the dead':<44}{'rule':>8}{'r=0.5 (halving)':>16}{'r=0.25':>8}{'r=0':>6}{'r=1 (false alarm)':>19}")
    for lab, n in ((f"this pull: CRSP-MF genuine ({g_fhy:.0f} fund-half-years)", g_fhy),
                   (f"EDGAR, full ({n_pop:.0f})", n_pop), (f"EDGAR, 80% ({0.8 * n_pop:.0f})", 0.8 * n_pop)):
        for thr in (0.5, 0.75):
            say(f"     {lab:<44}{('<' + str(thr)):>8}{p_flag(n, 0.5, thr):>16.2f}{p_flag(n, 0.25, thr):>8.2f}"
                f"{p_flag(n, 0.0, thr):>6.2f}{p_flag(n, 1.0, thr):>19.2f}")

    # ---- Q4: the second pull's scope, from the census's cached master index
    idxp = sorted((ac.WT.parent / "ss-cef-events" / "results" / "events" / "_cache_census").glob("index_extra_*.parquet"))
    if not idxp:
        say("\nQ4. the census's cached master index is not on this machine; scope not measured")
    else:
        ix = pd.read_parquet(idxp[-1])
        ix = ix[ix["form"].isin(["N-CSR", "N-CSRS", "N-CSR/A", "N-CSRS/A"])].copy()
        ix["date_filed"] = pd.to_datetime(ix["date_filed"])
        ix = ix[(ix.date_filed >= "2008-01-01") & (ix.date_filed <= "2023-06-30")]
        from scripts.events.cef_corp_action_census import CrspMap
        nm2 = nm.rename(columns={"nameenddt": "nameendt"})
        cm = CrspMap(nm2)
        filers = ix.drop_duplicates("cik")
        hit = {}
        for _, r in filers.iterrows():
            p, why = cm.permno(r["company"], None, r["date_filed"])
            if p is not None and p in cand.index:
                hit[int(r["cik"])] = p
        sub = ix[ix.cik.isin(hit)]
        say(f"\nQ4. EDGAR N-CSR/N-CSRS in the cached index ({idxp[-1].name}), filed 2008-01-01..2023-06-30: {len(ix)} filings, "
            f"{ix.cik.nunique()} filers. Filers mapped by name to a dead candidate: {len(hit)} CIKs -> "
            f"{len(set(hit.values()))} of {len(cand)} candidate permnos; their filings: {len(sub)}")
        say(f"   by year filed: {sub.date_filed.dt.year.value_counts().sort_index().to_dict()}")
        say(f"   candidates dead before 2008 (need 2004-07 indexes, not cached): "
            f"{int((cand.dlstdt < '2008-07-01').sum())}")
    (HERE / "gate0_coverage_output.txt").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
