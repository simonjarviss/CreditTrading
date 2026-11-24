"""Risk inputs for the event-desk PM design: residual volatility, hedge betas and
single-name tails of US common stocks and BDCs, CRSP, before 2023. ZERO TRIALS.

WHY THIS EXISTS
---------------
`results/events/ssx/ssx_pm/HOW_WE_ADD_IT_2026-10-19.md` (the PM/risk seat of the
2026-10-19 special-situations expansion) has to say how much gross an event
sleeve consumes per unit of idiosyncratic risk, how large a single-name short
squeeze can be, and what minimum detectable effect N events buy. Each needs a
volatility, and a volatility recalled from memory is a rumour (CLAUDE.md, data
rules). This script measures them from CRSP.

WHAT IT IS NOT
--------------
No event, no signal, no strategy and no event window is read. Every statistic is
over ALL sessions of liquid names, so it is a property of the instruments an
event sleeve would hold, not of any trade. It therefore spends no trial on any
counter (EVENTS stays 0). Because earnings days and other news are inside these
windows, the raw standard deviations are an UPPER bound on a quiet-window
residual; the MAD-based robust sigma is printed beside each as the lower bound.
Neither is averaged into the other.

HOLDOUTS
--------
- The 2023-01-01 time holdout: the dsf pull stops at 2022-12-30 in the SQL, and
  the frame is asserted on return (`assert_pre_holdout`).
- The 27-name CEF holdout (H9): common stocks are share codes 10/11 only (CEFs
  are 14/44), and every permno that ever carried a `data/cef/cef_universe.csv`
  ticker is asserted absent from both samples (`assert_no_universe`).

ALIGNMENT (no lookahead)
------------------------
Each name is admitted at year-end Y on data dated <= that session (price,
market cap, 63-session ADV, 250-session history). Its hedge beta is estimated on
the 250 sessions ending on that session. Every residual is measured on sessions
of year Y+1 only, strictly after the beta's window: the beta is out of sample.

BDCs
----
The BDC list is today's (`results/data/universe_2026-10-08/universe_map.csv`,
family `bdc`), so the BDC rows are survivors: BDCs that died before 2024 are
missing. Labelled wherever printed.

Reproduce:
    QUANTT_ENV_FILE=/abs/path/config/.env python3 scripts/events/ssx/ssx_pm_risk_inputs.py stage
    python3 scripts/events/ssx/ssx_pm_risk_inputs.py report
    python3 scripts/events/ssx/ssx_pm_risk_inputs.py etf
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events" / "ssx" / "ssx_pm"
CACHE = OUT / "_cache_crsp"          # gitignored by results/**/_cache_*
TIME_HOLDOUT = pd.Timestamp("2023-01-01")
PULL_START = "2008-11-01"            # 250 sessions before the first snapshot (2009-12-31)
UNIVERSE_MAP = REPO / "results" / "data" / "universe_2026-10-08" / "universe_map.csv"
UNIVERSE_CSV = REPO / "data" / "cef" / "cef_universe.csv"
HEDGE_TICKERS = ("SPY", "IWM", "HYG", "IEF", "PFF", "BKLN")
SNAP_YEARS = range(2009, 2022)       # admitted at year-end Y, measured in Y+1 (2010..2022)
HOLDS = (1, 3, 5, 10, 20, 60, 120)   # sessions
EST_LEN = 250
BETA_BLOCK = 5                       # 5-session blocks: thin trading biases a daily beta down
MIN_PRICE = 5.0
MIN_ADV = 1e6                        # the catalogue's tradable floor (corp catalogue §1)
BUCKETS = (("micro", 0, 3e8), ("small", 3e8, 2e9), ("mid", 2e9, 1e10), ("large", 1e10, np.inf))
ERAS = (("2010-14", 2010, 2014), ("2015-19", 2015, 2019), ("2020-22", 2020, 2022))


class WindowError(AssertionError):
    pass


def assert_pre_holdout(dates: pd.Series, what: str) -> None:
    if len(dates) and pd.Timestamp(dates.max()) >= TIME_HOLDOUT:
        raise WindowError(f"{what} reaches {pd.Timestamp(dates.max()).date()}: the 2023-01-01 "
                          "time holdout is sealed")


# ------------------------------------------------------------------ stage

def stage() -> None:
    """Pull dsenames (2009-2022 records) and dsf (to 2022-12-30) once, to the cache."""
    from src.data.r2 import connect, q, r2_path
    CACHE.mkdir(parents=True, exist_ok=True)
    con = connect()
    names_p = r2_path("crsp_a_stock", "dsenames")
    dsf_p = r2_path("crsp_a_stock", "dsf")
    nm = q(con, f"""SELECT permno, namedt, nameendt, shrcd, exchcd, ticker, comnam
                    FROM read_parquet('{names_p}')
                    WHERE nameendt >= DATE '2008-01-01' AND namedt < DATE '2023-01-01'""")
    nm.to_parquet(CACHE / "dsenames.parquet")
    bdc = pd.read_csv(UNIVERSE_MAP)
    bdc = bdc[(bdc["family"] == "bdc") & bdc["permno"].notna()]
    bdc_perm = sorted(int(p) for p in bdc["permno"])
    etf = nm[nm["ticker"].isin(HEDGE_TICKERS) & (nm["shrcd"] == 73)]
    etf_perm = sorted(int(p) for p in etf["permno"].unique())
    extra = ",".join(map(str, sorted(set(bdc_perm) | set(etf_perm))))
    sql = f"""SELECT permno, date, prc, ret, vol, shrout FROM read_parquet('{dsf_p}')
              WHERE date >= DATE '{PULL_START}' AND date < DATE '2023-01-01'
                AND (permno IN (SELECT DISTINCT permno FROM read_parquet('{names_p}')
                                WHERE shrcd IN (10, 11) AND nameendt >= DATE '2008-01-01'
                                  AND namedt < DATE '2023-01-01')
                     OR permno IN ({extra}))"""
    dsf = q(con, sql)
    dsf["date"] = pd.to_datetime(dsf["date"])
    assert_pre_holdout(dsf["date"], "the dsf pull")
    dsf.to_parquet(CACHE / "dsf.parquet")
    meta = {"pulled_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dsf_rows": int(len(dsf)), "dsf_first": str(dsf["date"].min().date()),
            "dsf_last": str(dsf["date"].max().date()), "names_rows": int(len(nm)),
            "bdc_permnos": len(bdc_perm), "etf_permnos": etf_perm}
    (CACHE / "_manifest.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


# ------------------------------------------------------------------ helpers

def universe_permnos(nm: pd.DataFrame) -> set[int]:
    """Every permno that carried a cef_universe.csv ticker as a CEF (shrcd 14/44)."""
    u = pd.read_csv(UNIVERSE_CSV)
    cef = nm[nm["shrcd"].isin((14, 44))]
    return set(int(p) for p in cef[cef["ticker"].isin(set(u["ticker"]))]["permno"].unique())


def assert_no_universe(permnos, uni: set[int], what: str) -> None:
    hit = sorted(set(int(p) for p in permnos) & uni)
    if hit:
        raise AssertionError(f"{what} touches cef_universe.csv permnos {hit}: H9 is not ours to open")


def block_returns(r: np.ndarray, h: int) -> np.ndarray:
    """Non-overlapping h-session compounded returns down axis 0. NaN if any session
    in the block is missing (a gap is not bridged: no assumption about the move)."""
    n = (r.shape[0] // h) * h
    if n == 0:
        return np.empty((0,) + r.shape[1:])
    x = r[:n].reshape((n // h, h) + r.shape[1:])
    return np.prod(1.0 + x, axis=1) - 1.0


def ols_beta(y: np.ndarray, x: np.ndarray, min_obs: int) -> np.ndarray:
    """Column-wise OLS slope of y (blocks x names) on x (blocks), NaN-aware."""
    X = np.broadcast_to(x[:, None], y.shape)
    m = np.isfinite(y) & np.isfinite(X)
    n = m.sum(0)
    xm = np.where(m, X, 0.0).sum(0) / np.maximum(n, 1)
    ym = np.where(m, y, 0.0).sum(0) / np.maximum(n, 1)
    cov = np.where(m, (X - xm) * (y - ym), 0.0).sum(0)
    var = np.where(m, (X - xm) ** 2, 0.0).sum(0)
    b = cov / np.where(var > 0, var, np.nan)
    b[n < min_obs] = np.nan
    return b


def robust_sd(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if len(x) else float("nan")


def tail(x: np.ndarray, qs=(0.001, 0.01, 0.99, 0.999)) -> dict:
    x = x[np.isfinite(x)]
    return {f"p{q*100:g}": float(np.quantile(x, q)) for q in qs} | {"max": float(x.max()), "min": float(x.min())}


# ------------------------------------------------------------------ report

def load():
    dsf = pd.read_parquet(CACHE / "dsf.parquet")
    nm = pd.read_parquet(CACHE / "dsenames.parquet")
    dsf["date"] = pd.to_datetime(dsf["date"])
    assert_pre_holdout(dsf["date"], "the cached dsf")
    for c in ("namedt", "nameendt"):
        nm[c] = pd.to_datetime(nm[c])
    for c in ("prc", "ret", "vol", "shrout"):
        dsf[c] = dsf[c].astype(float)
    dsf["prc"] = dsf["prc"].abs()
    return dsf, nm


def hedge_permnos(nm: pd.DataFrame) -> dict[str, int]:
    out = {}
    for t in HEDGE_TICKERS:
        p = nm[(nm["ticker"] == t) & (nm["shrcd"] == 73)]["permno"].unique()
        if len(p) != 1:
            raise LookupError(f"hedge {t}: expected one ETF permno in 2008-2022 dsenames, got {list(p)}")
        out[t] = int(p[0])
    return out


def name_on(nm: pd.DataFrame, d: pd.Timestamp) -> pd.DataFrame:
    """The dsenames record in force on session d, one row per permno."""
    x = nm[(nm["namedt"] <= d) & (nm["nameendt"] >= d)]
    return x.drop_duplicates("permno", keep="last").set_index("permno")


def measure(dsf: pd.DataFrame, nm: pd.DataFrame, sample: str, hedges: dict[str, int],
            hedge_set: tuple[str, ...], bdc_perm: set[int] | None, uni: set[int]) -> dict:
    ret = dsf.pivot(index="date", columns="permno", values="ret").sort_index()
    dv = (dsf["prc"] * dsf["vol"]).groupby([dsf["date"], dsf["permno"]]).sum(min_count=1).unstack()
    dv = dv.reindex(index=ret.index, columns=ret.columns)
    prc = dsf.pivot(index="date", columns="permno", values="prc").reindex_like(ret)
    shr = dsf.pivot(index="date", columns="permno", values="shrout").reindex_like(ret)
    # The session calendar is the hedge ETF's (SPY trades every NYSE session).
    cal = ret[hedges["SPY"]].dropna().index
    ret, dv, prc, shr = (f.reindex(cal) for f in (ret, dv, prc, shr))
    dates = ret.index
    R = ret.to_numpy(dtype=float)
    col = {p: i for i, p in enumerate(ret.columns)}
    rows, adv_shares, admitted = [], [], {}
    for Y in SNAP_YEARS:
        snap_i = int(np.searchsorted(dates, pd.Timestamp(f"{Y}-12-31"), side="right")) - 1
        snap = dates[snap_i]
        test = np.where(dates.year == Y + 1)[0]
        if snap_i + 1 - EST_LEN < 0 or len(test) == 0:
            raise WindowError(f"year {Y}: not enough sessions for the estimation or test window")
        assert dates[test[0]] > snap  # the residual window starts strictly after the beta's
        est = np.arange(snap_i + 1 - EST_LEN, snap_i + 1)
        rec = name_on(nm, snap)
        if bdc_perm is None:
            elig = rec[rec["shrcd"].isin((10, 11)) & rec["exchcd"].isin((1, 2, 3))].index
        else:
            elig = pd.Index([p for p in bdc_perm if p in rec.index])
        elig = [p for p in elig if p in col]
        p_snap = prc.iloc[snap_i][elig]
        cap = p_snap * shr.iloc[snap_i][elig] * 1000.0
        adv = dv.iloc[snap_i - 62: snap_i + 1][elig]
        adv63 = adv.mean().where(adv.notna().sum() >= 40)
        nvalid = ret.iloc[est][elig].notna().sum()
        base = (p_snap >= MIN_PRICE) & (nvalid >= 200)
        if bdc_perm is None:
            a = adv63[base].dropna()
            adv_shares.append({"year": Y, "n": int(len(a))} |
                              {f"ge_{lab}": float((a >= v).mean()) for lab, v in
                               (("0.1m", 1e5), ("1m", 1e6), ("10m", 1e7), ("100m", 1e8))})
        keep = base & (adv63 >= MIN_ADV)
        perms = list(keep[keep].index)
        assert_no_universe(perms, uni, f"{sample} {Y}")
        admitted[Y] = len(perms)
        if not perms:
            continue
        idx = [col[p] for p in perms]
        Rs_est, Rs_test = R[np.ix_(est, idx)], R[np.ix_(test, idx)]
        for hname in hedge_set:
            hcol = col[hedges[hname]]
            he, ht = R[est, hcol], R[test, hcol]
            if np.isnan(he).any() or np.isnan(ht).any():
                raise ValueError(f"hedge {hname} has a missing session in {Y}/{Y+1}")
            beta = ols_beta(block_returns(Rs_est, BETA_BLOCK), block_returns(he, BETA_BLOCK), 45)
            for h in HOLDS:
                ys, xs = block_returns(Rs_test, h), block_returns(ht, h)
                e = ys - beta[None, :] * xs[:, None]
                for j, p in enumerate(perms):
                    if not np.isfinite(beta[j]):
                        continue
                    cap_j = float(cap[p])
                    bucket = next(b for b, lo, hi in BUCKETS if lo <= cap_j < hi) if bdc_perm is None else "bdc"
                    rows.append((Y + 1, p, bucket, hname, h, float(beta[j]), ys[:, j], e[:, j]))
    return {"rows": rows, "adv_shares": adv_shares, "admitted": admitted}


def summarise(rows, sample: str) -> dict:
    out = {}
    df = pd.DataFrame(rows, columns=["year", "permno", "bucket", "hedge", "h", "beta", "y", "e"])
    for (bucket, hedge), g in df.groupby(["bucket", "hedge"]):
        key = f"{sample}|{bucket}|{hedge}"
        g1 = g[g["h"] == 1]
        g5 = g[g["h"] == 5]
        # per stock-year time-series residual vol (the typical position's idio vol)
        ts1 = np.array([np.nanstd(e, ddof=1) * np.sqrt(252) for e in g1["e"] if np.isfinite(e).sum() >= 100])
        ts5 = np.array([np.nanstd(e, ddof=1) * np.sqrt(252 / 5) for e in g5["e"] if np.isfinite(e).sum() >= 20])
        rec = {"stock_years": int(g1["permno"].count()), "names": int(g1["permno"].nunique()),
               "beta_median": float(g1["beta"].median()), "beta_p10": float(g1["beta"].quantile(0.1)),
               "beta_p90": float(g1["beta"].quantile(0.9)),
               "idio_vol_ann_daily_median": float(np.median(ts1)), "idio_vol_ann_daily_p25": float(np.quantile(ts1, 0.25)),
               "idio_vol_ann_daily_p75": float(np.quantile(ts1, 0.75)),
               "idio_vol_ann_5d_median": float(np.median(ts5)), "idio_vol_ann_5d_p25": float(np.quantile(ts5, 0.25)),
               "idio_vol_ann_5d_p75": float(np.quantile(ts5, 0.75)), "holds": {}}
        for h, gh in g.groupby("h"):
            e = np.concatenate(gh["e"].to_numpy())
            y = np.concatenate(gh["y"].to_numpy())
            fin = np.isfinite(e) & np.isfinite(y)
            e, y = e[fin], y[fin]
            rec["holds"][int(h)] = {"n_windows": int(len(e)), "sd_e": float(np.std(e, ddof=1)),
                                    "robust_sd_e": robust_sd(e), "sd_raw": float(np.std(y, ddof=1)),
                                    "var_removed": float(1 - np.var(e) / np.var(y)),
                                    "tail_e": tail(e), "tail_raw": tail(y)}
        eras = {}
        for lab, a, b in ERAS:
            ge = g5[(g5["year"] >= a) & (g5["year"] <= b)]
            ts = np.array([np.nanstd(e, ddof=1) * np.sqrt(252 / 5) for e in ge["e"] if np.isfinite(e).sum() >= 20])
            eras[lab] = {"stock_years": int(len(ts)), "idio_vol_ann_5d_median": float(np.median(ts)) if len(ts) else None}
        rec["eras"] = eras
        out[key] = rec
    return out


def report() -> None:
    dsf, nm = load()
    hedges = hedge_permnos(nm)
    uni = universe_permnos(nm)
    if not uni:
        raise LookupError("no cef_universe.csv ticker matched a CRSP CEF permno: the H9 guard would be empty")
    bdc = pd.read_csv(UNIVERSE_MAP)
    bdc_perm = set(int(p) for p in bdc[(bdc["family"] == "bdc") & bdc["permno"].notna()]["permno"])
    assert_no_universe(bdc_perm, uni, "the BDC list")
    stocks = measure(dsf, nm, "stocks", hedges, ("SPY", "IWM"), None, uni)
    bdcs = measure(dsf, nm, "bdc", hedges, ("SPY", "HYG"), bdc_perm, uni)
    summ = summarise(stocks["rows"], "stocks") | summarise(bdcs["rows"], "bdc")
    adv = pd.DataFrame(stocks["adv_shares"])
    # The tracked outputs carry no CRSP permno (team lead, 2026-10-22, before the
    # first push of this branch to the public repository). The gitignored cache
    # manifest keeps them, so the pull stays reproducible on this machine.
    manifest = {k: v for k, v in json.loads((CACHE / "_manifest.json").read_text()).items()
                if k != "etf_permnos"}
    res = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "manifest": manifest,
           "hedge_etfs": sorted(hedges), "universe_permnos_guarded": len(uni),
           "admitted_stocks": stocks["admitted"], "admitted_bdc": bdcs["admitted"],
           "adv_shares_by_year": stocks["adv_shares"],
           "adv_shares_median": {c: float(adv[c].median()) for c in adv.columns if c.startswith("ge_")},
           "summary": summ}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "risk_inputs_2026-10-19.json").write_text(json.dumps(res, indent=1))
    lines = [f"risk inputs (CRSP dsf {res['manifest']['dsf_first']} -> {res['manifest']['dsf_last']}; "
             f"pulled {res['manifest']['pulled_utc']}); residuals out of sample, years 2010-2022",
             f"hedge ETFs {sorted(hedges)}; cef_universe permnos guarded: {len(uni)}",
             "", "ADV shares of price>=$5 common stocks at year-end (median of 13 snapshots): " +
             ", ".join(f"{k} {v:.3f}" for k, v in res["adv_shares_median"].items()), ""]
    hdr = (f"{'sample|bucket|hedge':<24}{'st-yrs':>7}{'beta':>6}{'idio ann (5d) p25/med/p75':>28}"
           f"{'sd e 1d':>9}{'3d':>7}{'5d':>7}{'20d':>7}{'60d':>7}{'120d':>7}{'rob 5d':>8}{'VarRem 5d':>10}"
           f"{'raw 5d p99.9':>13}{'max':>7}")
    lines.append(hdr)
    for k, r in summ.items():
        H = r["holds"]
        lines.append(
            f"{k:<24}{r['stock_years']:>7}{r['beta_median']:>6.2f}"
            f"{r['idio_vol_ann_5d_p25']:>10.3f}/{r['idio_vol_ann_5d_median']:.3f}/{r['idio_vol_ann_5d_p75']:.3f}"
            f"{H[1]['sd_e']:>9.4f}{H[3]['sd_e']:>7.3f}{H[5]['sd_e']:>7.3f}{H[20]['sd_e']:>7.3f}"
            f"{H[60]['sd_e']:>7.3f}{H[120]['sd_e']:>7.3f}{H[5]['robust_sd_e']:>8.3f}{H[5]['var_removed']:>10.2f}"
            f"{H[5]['tail_raw']['p99.9']:>13.3f}{H[5]['tail_raw']['max']:>7.2f}")
    lines.append("")
    lines.append("eras (median annualised idio vol from 5-session residuals):")
    for k, r in summ.items():
        lines.append(f"  {k:<24}" + "  ".join(f"{e} {v['idio_vol_ann_5d_median']:.3f} (n {v['stock_years']})"
                                               if v['idio_vol_ann_5d_median'] is not None else f"{e} -"
                                               for e, v in r["eras"].items()))
    txt = "\n".join(lines)
    (OUT / "risk_inputs_2026-10-19.txt").write_text(txt + "\n")
    print(txt)


def etf() -> None:
    """The hedge ETFs themselves: dollar ADV by year and 5-session return tails.

    ADV sizes the shared hedge overlay's capacity (how much NAV one ETF can hedge
    at a participation limit); the 5-session tails size the cross-broker stress
    (a short book rallying while its hedge sits at the other broker). Both are
    pre-2023 (the cache is cut at 2022-12-30 and asserted)."""
    dsf, nm = load()
    hedges = hedge_permnos(nm)
    out = {}
    for t, p in hedges.items():
        g = dsf[dsf["permno"] == p].sort_values("date").set_index("date")
        assert_pre_holdout(g.index.to_series(), f"ETF {t}")
        dv = (g["prc"] * g["vol"])
        adv = {str(y): float(dv[dv.index.year == y].mean()) for y in (2015, 2019, 2022) if (dv.index.year == y).any()}
        r = g["ret"].dropna()
        r5 = (1 + r).rolling(5).apply(np.prod, raw=True) - 1      # overlapping: a tail, not a test statistic
        out[t] = {"first": str(g.index.min().date()), "last": str(g.index.max().date()),   # no permno: see report()
                  "adv_usd": adv, "r5_max": float(r5.max()), "r5_max_date": str(r5.idxmax().date()),
                  "r5_p99.9": float(r5.quantile(0.999)), "r5_min": float(r5.min()),
                  "r5_min_date": str(r5.idxmin().date()), "r1_max": float(r.max()), "r1_min": float(r.min())}
    (OUT / "etf_inputs_2026-10-19.json").write_text(json.dumps(out, indent=1))
    for t, v in out.items():
        print(f"{t:<5} {v['first']}..{v['last']}  ADV " +
              " ".join(f"{y} ${a/1e6:,.0f}m" for y, a in v["adv_usd"].items()) +
              f"  5d max {v['r5_max']:+.3f} ({v['r5_max_date']}) p99.9 {v['r5_p99.9']:+.3f} min {v['r5_min']:+.3f} ({v['r5_min_date']})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("step", choices=("stage", "report", "etf"))
    a = ap.parse_args(argv)
    {"stage": stage, "report": report, "etf": etf}[a.step]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
