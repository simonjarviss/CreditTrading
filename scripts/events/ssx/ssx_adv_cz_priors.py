"""Literature priors for the 2026-10-19 special-situations expansion: decay and
factor loadings of the PUBLISHED anomalies nearest each candidate.

WHY this exists. The adversary seat (ssx_adv) must give each candidate an honest
prior before it spends an EVENTS trial. Where a candidate is a published anomaly,
the right prior is not the original paper's in-sample t but what the anomaly did
after its sample ended and after publication, and what it loads on. Chen and
Zimmermann's Open Source Asset Pricing release (October 2025, v2.0.0, data to
2024-12) publishes the long-short monthly returns of each replicated predictor.
This script reads that public file and Ken French's and Lubos Pastor's public
factor files, and prints, per predictor:

  * mean long-short return in the original sample, after the sample but before
    publication, and after publication (McLean-Pontiff's three windows);
  * the same over 2010-2024 (the era our desk would trade in);
  * an FF5 + UMD + ST_Rev + Pastor-Stambaugh traded-liquidity regression over
    2005-01..2024-12, with Newey-West (6 lags) t-statistics: the desk's D4 test
    (alpha t >= 3.0 and every |beta| <= 0.10) applied to the published version;
  * a piecewise market beta with a kink at Mkt-RF < -4% (Mitchell-Pulvino 2001's
    test, the one that killed merger arbitrage): a short index put shows up as a
    down-market beta well above the up-market beta, which no linear hedge removes.

ZERO TRIALS. Nothing here touches `data/` or any candidate's return on our data.
These are public datasets of published anomalies: literature, as the brief allows.
The CZ portfolios are decile (or paper-specific) sorts on all CRSP common stock,
mostly equal-weighted, before costs: they overstate what a $100k MOC book could
earn, and they say nothing about our event definitions. Read them as priors.

No lookahead question arises: nothing is estimated for use on a later date.

Usage:
    python3 scripts/events/ssx/ssx_adv_cz_priors.py --cache /abs/dir --fetch
    python3 scripts/events/ssx/ssx_adv_cz_priors.py --cache /abs/dir
Output: results/events/ssx/ssx_adv/cz_priors_2026-10-19.csv (and stdout).
"""
from __future__ import annotations

import argparse
import csv
import io
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "events" / "ssx" / "ssx_adv" / "cz_priors_2026-10-19.csv"

# Public sources, fetched 2026-10-19. The Drive id is the "Monthly long-short
# returns of 212 predictors (wide CSV)" link on https://www.openassetpricing.com/data/
# (October 2025 release, v2.0.0).
SOURCES = {
    "lsret.csv": "https://drive.google.com/uc?export=download&id=10sOryk_ddjkXagaajTKUk1nwJs2ZLRiI",
    "SignalDoc.csv": "https://raw.githubusercontent.com/OpenSourceAP/CrossSection/master/SignalDoc.csv",
    "ff5.zip": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip",
    "mom.zip": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip",
    "strev.zip": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_ST_Reversal_Factor_CSV.zip",
    "ps_liq.txt": "https://faculty.chicagobooth.edu/-/media/faculty/lubos-pastor/data/liq_data_1962_2024.txt",
}

# The predictors nearest each candidate (candidate ids are the expansion doc's).
PREDICTORS = {
    "CredRatDG": "CR3/B4/C2: equity after a rating downgrade",
    "OScore": "C2/D4: distress (Ohlson O-score)",
    "CustomerMomentum": "D7: customer-supplier links (Cohen-Frazzini)",
    "iomom_cust": "D7: customer-industry momentum (Menzly-Ozbas)",
    "iomom_supp": "D7: supplier-industry momentum (Menzly-Ozbas)",
    "IndIPO": "D5/K5: IPO underperformance (Ritter)",
    "AgeIPO": "D5/K5: young IPOs",
    "Spinoff": "B1-corp: spin-offs (Cusatis-Miles-Woolridge)",
    "ShareIss1Y": "A1/K6: net share issuance (Pontiff-Woodgate)",
    "CompEquIss": "A1/K6: composite equity issuance (Daniel-Titman)",
    "ShareRepurchase": "A3/F1: buyback announcements (Ikenberry et al.)",
    "DivOmit": "graveyard 'distribution-cut signals': dividend omission",
    "DivInit": "dividend initiation",
    "ExchSwitch": "K1: exchange listing switch",
    "AnnouncementReturn": "D2: post-earnings-announcement drift (return)",
    "EarningsSurprise": "D2: PEAD (SUE)",
    "EarningsStreak": "D2: earnings-surprise streak",
    "ChNAnalyst": "D5: analyst coverage change",
    "Activism1": "graveyard 'following activist 13Ds' (governance x blockholder)",
    "Activism2": "graveyard 'following activist 13Ds' (blockholder x governance)",
    "ShortInterest": "graveyard 'short-interest crowding'",
    "Recomm_ShortInterest": "short interest x analyst recommendations",
    "STreversal": "reference: short-term reversal (a D4 factor itself)",
}


def fetch(cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        dest = cache / name
        subprocess.run(["curl", "-sS", "-L", "-m", "120", "-o", str(dest), url], check=True)
        if dest.stat().st_size < 1000:
            raise RuntimeError(f"fetch of {url} returned {dest.stat().st_size} bytes")


def _french(zpath: Path) -> pd.DataFrame:
    """Monthly block of a Ken French CSV zip, in percent, indexed by Period."""
    with zipfile.ZipFile(zpath) as z:
        text = z.read(z.namelist()[0]).decode("latin-1")
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(","))
    rows = []
    for l in lines[start + 1:]:
        parts = [p.strip() for p in l.split(",")]
        if len(parts[0]) != 6 or not parts[0].isdigit():
            break
        rows.append(parts)
    cols = ["ym"] + [c.strip() for c in lines[start].split(",")[1:]]
    df = pd.DataFrame(rows, columns=cols)
    df["ym"] = pd.PeriodIndex(df["ym"].str[:4] + "-" + df["ym"].str[4:], freq="M")
    return df.set_index("ym").astype(float)


def _ps(path: Path) -> pd.Series:
    rows = []
    for l in path.read_text().splitlines():
        if l.startswith("%") or not l.strip():
            continue
        p = l.split()
        if len(p) < 4:
            continue
        v = float(p[3])
        if v == -99:
            continue
        rows.append((pd.Period(f"{p[0][:4]}-{p[0][4:]}", freq="M"), v * 100.0))
    s = pd.Series(dict(rows), name="LIQ")
    if s.empty:
        raise RuntimeError("Pastor-Stambaugh traded factor column is empty")
    return s


def _mean_t(x: pd.Series) -> tuple[float, float, int]:
    x = x.dropna()
    if len(x) < 24:
        return (np.nan, np.nan, len(x))
    return (x.mean(), x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), len(x))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="also print the base rate over every predictor in the CZ file")
    a = ap.parse_args()
    if a.fetch:
        fetch(a.cache)

    ls = pd.read_csv(a.cache / "lsret.csv")
    ls["ym"] = pd.to_datetime(ls["date"]).dt.to_period("M")
    ls = ls.set_index("ym").drop(columns=["date"])
    doc = {r["Acronym"]: r for r in csv.DictReader(open(a.cache / "SignalDoc.csv", encoding="utf-8", errors="replace"))}

    ff5 = _french(a.cache / "ff5.zip")
    mom = _french(a.cache / "mom.zip")
    strev = _french(a.cache / "strev.zip")
    fac = ff5.join(mom, how="inner").join(strev, how="inner").join(_ps(a.cache / "ps_liq.txt"), how="inner")
    fac.columns = [c.strip() for c in fac.columns]
    momcol = [c for c in fac.columns if c.lower().startswith("mom")][0]
    strcol = [c for c in fac.columns if c.lower().startswith("st_rev")][0]
    X_cols = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", momcol, strcol, "LIQ"]

    out = []
    for sig, why in PREDICTORS.items():
        if sig not in ls.columns:
            raise KeyError(f"{sig} missing from the CZ long-short file")
        d = doc[sig]
        s0, s1, pub = int(d["SampleStartYear"]), int(d["SampleEndYear"]), int(d["Year"])
        r = ls[sig]
        yr = r.index.year
        ins = _mean_t(r[(yr >= s0) & (yr <= s1)])
        oos = _mean_t(r[(yr > s1) & (yr <= pub)])
        post = _mean_t(r[yr > pub])
        modern = _mean_t(r[(yr >= 2010) & (yr <= 2024)])
        j = pd.concat([r.rename("y"), fac[X_cols]], axis=1, join="inner").dropna()
        j = j[(j.index.year >= 2005) & (j.index.year <= 2024)]
        X = sm.add_constant(j[X_cols])
        m = sm.OLS(j["y"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
        # Piecewise market beta, Mitchell-Pulvino style kink at -4%/month.
        dn = (j["Mkt-RF"] < -4.0).astype(float)
        Xk = pd.DataFrame({"const": 1.0, "mkt_dn": j["Mkt-RF"] * dn, "mkt_up": j["Mkt-RF"] * (1 - dn)}, index=j.index)
        mk = sm.OLS(j["y"], Xk).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
        betas = {c: m.params[c] for c in X_cols}
        maxb = max(betas, key=lambda c: abs(betas[c]))
        out.append({
            "predictor": sig, "candidate_link": why, "paper": f"{d['Authors']} {pub}",
            "sample": f"{s0}-{s1}", "weight": d["Stock Weight"],
            "in_mean": ins[0], "in_t": ins[1], "oos_prepub_mean": oos[0], "oos_prepub_t": oos[1],
            "postpub_mean": post[0], "postpub_t": post[1], "postpub_n": post[2],
            "postpub_over_in": post[0] / ins[0] if ins[0] else np.nan,
            "m2010_24_mean": modern[0], "m2010_24_t": modern[1],
            "d4_alpha": m.params["const"], "d4_alpha_t": m.tvalues["const"],
            **{f"b_{c}": betas[c] for c in X_cols},
            "max_abs_beta": f"{maxb} {betas[maxb]:+.2f}",
            "d4_pass": bool(m.tvalues["const"] >= 3.0 and max(abs(v) for v in betas.values()) <= 0.10),
            "kink_beta_dn": mk.params["mkt_dn"], "kink_beta_up": mk.params["mkt_up"],
            "n_dn_months": int(dn.sum()), "reg_n": len(j),
        })
    df = pd.DataFrame(out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, float_format="%.4f")
    pd.set_option("display.width", 250)
    show = ["predictor", "paper", "sample", "weight", "in_mean", "in_t", "postpub_mean", "postpub_t",
            "postpub_over_in", "m2010_24_mean", "m2010_24_t", "d4_alpha", "d4_alpha_t", "max_abs_beta",
            "d4_pass", "kink_beta_dn", "kink_beta_up", "n_dn_months"]
    print(df[show].to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    print(f"\nfactor window {j.index.min()}..{j.index.max()}; LS file last month {ls.index.max()}; wrote {OUT}")
    if a.all:
        base_rate(ls, doc, fac, X_cols)
    return 0


def base_rate(ls: pd.DataFrame, doc: dict, fac: pd.DataFrame, X_cols: list[str]) -> None:
    """The desk's D4 bar applied to EVERY published predictor in the CZ file.

    WHY: a base rate for 'a published equity anomaly, built as the paper built
    it, clears alpha t >= 3.0 with every |beta| <= 0.10 over 2005-2024'. If almost
    none do, a candidate that is a published anomaly starts with that prior, and
    its pre-registration must say how it will be neutralised, not hope.
    """
    rows = []
    for sig in ls.columns:
        if sig not in doc:
            raise KeyError(f"{sig} has no SignalDoc row")
        d = doc[sig]
        s1, pub = int(d["SampleEndYear"]), int(d["Year"])
        s0 = int(d["SampleStartYear"])
        r = ls[sig]
        yr = r.index.year
        ins = _mean_t(r[(yr >= s0) & (yr <= s1)])
        post = _mean_t(r[yr > pub])
        j = pd.concat([r.rename("y"), fac[X_cols]], axis=1, join="inner").dropna()
        j = j[(j.index.year >= 2005) & (j.index.year <= 2024)]
        if len(j) < 120:
            continue
        m = sm.OLS(j["y"], sm.add_constant(j[X_cols])).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
        maxb = max(abs(m.params[c]) for c in X_cols)
        rows.append({"sig": sig, "ins": ins[0], "post": post[0], "post_t": post[1],
                     "alpha_t": m.tvalues["const"], "maxb": maxb})
    b = pd.DataFrame(rows)
    ok = b.dropna(subset=["ins", "post"])
    ok = ok[ok["ins"] > 0]
    print(f"\nBASE RATE over {len(b)} CZ predictors with >= 120 months in 2005-2024:")
    print(f"  median post-publication / in-sample mean: {(ok['post'] / ok['ins']).median():.2f} (n {len(ok)})")
    print(f"  share with post-publication t >= 1.96: {(ok['post_t'] >= 1.96).mean():.2f}")
    print(f"  share with 2005-24 alpha t >= 3.0: {(b['alpha_t'] >= 3.0).mean():.2f} ({int((b['alpha_t'] >= 3.0).sum())})")
    print(f"  share with every |beta| <= 0.10: {(b['maxb'] <= 0.10).mean():.2f} ({int((b['maxb'] <= 0.10).sum())})")
    both = b[(b['alpha_t'] >= 3.0) & (b['maxb'] <= 0.10)]
    print(f"  share passing BOTH legs of the desk's D4: {len(both) / len(b):.3f} ({len(both)}): {', '.join(both['sig'])}")


if __name__ == "__main__":
    sys.exit(main())
