"""Gate 0 of PREREG_C4_LEVEL: is the NAV coverage loss random, or concentrated among DYING funds? Zero trials.

Pull 2 covered 64.2% of the dead candidates' fund-half-years (manifest
2026-11-03T03:59Z). That is below the 80% figure §4b first named, which the
team lead's ruling of 2026-11-02 turned into evidence rather than a halt. A
coverage loss biases the survivorship estimate only if it is related to both a
fund's discount level and its forward return. The level is what is missing, so
this script checks what CRSP still shows for the missed observations.

  M1 report level: inside each mapped fund's fit-window life, P(missed) by months
     to delisting and for the fund's LAST report before delisting. "Missed" means
     "CRSP close not found beside a NAV" or "no CRSP trade close".
  M2 outcomes: missed against found reports on the CRSP returns that need no NAV.
     These are the forward t+2..t+127 return (delisting return included, as in
     gate0_analysis.py) and the trailing 126-session return, each as an excess
     over the same period-end month's mean across every in-life dead report.
     Standard errors are clustered by month.
  M3 fund level: candidates never covered (no CIK mapped, or mapped with no NAV)
     against covered dead funds. Compared on delisting-code class and on the
     CRSP excess return over their last 252 sessions to delisting, dlret included.
  M4 the cheap fix, measured offline on the cached filings: a "close not found"
     report is re-read with `nav_beside_price` against the trade closes of the 3
     sessions before the period-end and against the close +-$0.01. The count
     recovered is a fix estimate only. Gate 0's numbers do NOT use it.

Run (from the worktree root):  python3 -B results/cef/screens_2026-11-02/gate0_missingness.py
Writes gate0_missingness_output.txt beside itself (aggregates only).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

CACHE = HERE / "_cache_gate0"
FIT_START, FIT_END = pd.Timestamp("2005-01-03"), pd.Timestamp("2022-12-30")
MISSED = ("CRSP close not found beside a NAV", "no CRSP trade close at the period-end")


def t_clustered(x: pd.Series, g: pd.Series) -> float:
    """t of the mean of x with SEs clustered by g."""
    x = x.astype(float)
    e = x - x.mean()
    s = e.groupby(g).sum()
    G = len(s)
    se = np.sqrt((s ** 2).sum() * G / (G - 1)) / len(x)
    return float(x.mean() / se) if se > 0 else np.nan


def main() -> int:
    lines = []
    say = lambda s="": (print(s), lines.append(s))
    import alpha_common as ac
    from gate0_pull_ncsr import candidates
    say(ac.header("GATE 0 MISSINGNESS: is the coverage loss random? (zero trials; fit only)"))
    cand, nm, dsf, _ = candidates()
    nav = pd.read_parquet(CACHE / "ncsr_navs.parquet")
    nav["period"] = pd.to_datetime(nav["period"])
    mp = pd.read_csv(CACHE / "ncsr_map.csv")
    dl = pd.read_parquet(CACHE / "cef_delist.parquet")
    dl["dlstdt"] = pd.to_datetime(dl["dlstdt"])
    dsf2 = pd.read_parquet(CACHE / "cef_dsf.parquet", columns=["permno", "date", "ret"])
    dsf2["date"] = pd.to_datetime(dsf2["date"])
    cal = pd.DatetimeIndex(sorted(dsf2.date.unique()))
    R = dsf2.pivot_table(index="date", columns="permno", values="ret")
    dlr = dl.set_index("permno")[["dlstdt", "dlret", "dlstcd"]]

    # ---- M1
    inlife = nav[nav.reason.isna() | nav.reason.isin(MISSED)].copy()
    inlife = inlife[(inlife.period >= FIT_START) & (inlife.period <= FIT_END)].drop_duplicates(["permno", "period"])
    inlife["missed"] = inlife.nav.isna()
    inlife["dlstdt"] = inlife.permno.map(dlr.dlstdt)
    inlife["m_to_delist"] = (inlife.dlstdt - inlife.period).dt.days / 30.44
    inlife["last"] = inlife.groupby("permno")["period"].transform("max") == inlife.period
    say(f"\nM1. in-life reports of mapped dead funds: {len(inlife)}; missed {int(inlife.missed.sum())} "
        f"({inlife.missed.mean():.1%})")
    b = pd.cut(inlife.m_to_delist, [-1, 6, 12, 24, 60, 1e9], labels=["<=6m", "6-12m", "12-24m", "24-60m", ">60m"])
    tab = inlife.groupby(b, observed=True)["missed"].agg(["mean", "size"])
    for k, r in tab.iterrows():
        say(f"    months to delisting {k:<7}: P(missed) {r['mean']:.1%} of {int(r['size'])}")
    say(f"    the fund's LAST report: P(missed) {inlife[inlife['last']].missed.mean():.1%} "
        f"(n {int(inlife['last'].sum())}) vs earlier {inlife[~inlife['last']].missed.mean():.1%}")
    yb = inlife.groupby(inlife.period.dt.year // 5 * 5)["missed"].mean()
    say(f"    by period year (5-year bins): {', '.join(f'{int(k)}: {v:.0%}' for k, v in yb.items())}")

    # ---- M2: forward and trailing CRSP returns, no NAV needed
    def fwd_ret(p, d):
        i = cal.searchsorted(d, side="right") - 1          # the last session on or before the period-end
        if i < 0 or i + 127 >= len(cal):
            return np.nan
        win = cal[i + 2:i + 128]
        r = R[p].reindex(win) if p in R.columns else pd.Series(np.nan, index=win)
        dd = dlr.dlstdt.get(p, pd.NaT)
        if pd.notna(dd) and win[0] <= dd <= win[-1]:
            dr = dlr.dlret.get(p, np.nan)
            if pd.isna(dr):
                return np.nan
            return float(np.prod(1 + r[r.index < dd].fillna(0).to_numpy()) * (1 + dr) - 1) * 1e4
        return float(np.prod(1 + r.fillna(0).to_numpy()) - 1) * 1e4

    def trail_ret(p, d, n=126):
        i = cal.searchsorted(d, side="right") - 1
        if i - n < 0:
            return np.nan
        r = R[p].reindex(cal[i - n + 1:i + 1]) if p in R.columns else None
        return float(np.prod(1 + r.fillna(0).to_numpy()) - 1) * 1e4 if r is not None else np.nan

    inlife["fwd"] = [fwd_ret(p, d) for p, d in zip(inlife.permno, inlife.period)]
    inlife["trail"] = [trail_ret(p, d) for p, d in zip(inlife.permno, inlife.period)]
    inlife["month"] = inlife.period.dt.to_period("M").astype(str)
    say("\nM2. missed vs found reports, excess over the same period-end month's mean of all in-life dead reports:")
    for c in ("fwd", "trail"):
        v = inlife.dropna(subset=[c]).copy()
        v["x"] = v[c] - v.groupby("month")[c].transform("mean")
        mi, fo = v[v.missed], v[~v.missed]
        d = v.assign(z=np.where(v.missed, 1.0, 0.0))
        # difference in means, clustered by month: regress x on missed
        X = d.z - d.z.mean()
        beta = float((X * d.x).sum() / (X ** 2).sum())
        e = d.x - d.x.mean() - beta * X
        s = (X * e).groupby(d.month).sum()
        G = len(s)
        se = np.sqrt((s ** 2).sum() * G / (G - 1)) / (X ** 2).sum()
        say(f"    {('forward t+2..t+127' if c == 'fwd' else 'trailing 126 sessions'):<22}: missed {mi.x.mean():+7.1f}bp "
            f"(n {len(mi)}), found {fo.x.mean():+7.1f}bp (n {len(fo)}); missed - found {beta:+7.1f}bp, t {beta / se:+.2f}")

    # ---- M3: funds never covered
    covered = set(nav.dropna(subset=["nav"]).permno.astype(int))
    mapped = set(mp.permno.astype(int))
    cand = cand.copy()
    cand["status"] = np.where(~cand.index.isin(mapped), "no CIK mapped",
                              np.where(cand.index.isin(covered), "covered", "mapped, no NAV"))
    cand["dclass"] = (cand.dlstcd // 100).map({2: "merger (2xx)", 3: "exchange (3xx)", 4: "liquidation (4xx)",
                                               5: "dropped (5xx)"}).fillna("other")

    def last_year(p):
        dd = dlr.dlstdt.get(p, pd.NaT)
        i = cal.searchsorted(min(dd, FIT_END), side="right") - 1
        if i - 252 < 0:
            return np.nan
        r = R[p].reindex(cal[i - 251:i + 1]) if p in R.columns else None
        if r is None:
            return np.nan
        dr = dlr.dlret.get(p, np.nan)
        return float(np.prod(1 + r.fillna(0).to_numpy()) * (1 + (0 if pd.isna(dr) else dr)) - 1) * 1e4

    cand["last_year"] = [last_year(p) for p in cand.index]
    cand["dyear"] = cand.dlstdt.dt.year
    cand["ly_x"] = cand.last_year - cand.groupby("dyear")["last_year"].transform("mean")
    say("\nM3. candidate funds by coverage status:")
    for st, g in cand.groupby("status"):
        dc = g.dclass.value_counts(normalize=True)
        say(f"    {st:<15} {len(g):>4} funds; delistings: " + ", ".join(f"{k} {v:.0%}" for k, v in dc.items()) +
            f"; last-year CRSP return, excess over same-delisting-year mean {g.ly_x.mean():+.0f}bp")
    nc = cand[cand.status != "covered"].ly_x.dropna()
    co = cand[cand.status == "covered"].ly_x.dropna()
    diff = nc.mean() - co.mean()
    se = np.sqrt(nc.var(ddof=1) / len(nc) + co.var(ddof=1) / len(co))
    say(f"    never covered - covered, last-year excess return: {diff:+.0f}bp (t {diff / se:+.2f}; n {len(nc)} vs {len(co)})")

    # ---- M4: the cheap fix, offline on cached filings
    from scripts.events.cef_corp_action_census import _client, fetch_raw
    from gate0_pull_ncsr import read_nav
    client = _client(offline=True)
    px = pd.read_parquet(CACHE / "cef_dsf.parquet", columns=["permno", "date", "prc"])
    px["date"] = pd.to_datetime(px["date"])
    px = px[px.prc > 0]
    miss = nav[nav.reason == "CRSP close not found beside a NAV"].dropna(subset=["period"])
    rec, err = 0, 0
    for _, r in miss.iterrows():
        try:
            raw = fetch_raw(client, int(r.cik), r.accession)
        except Exception:
            err += 1
            continue
        x = px[(px.permno == r.permno) & (px.date <= r.period)].sort_values("date").tail(4)
        closes = list(dict.fromkeys([round(c + dlt, 2) for c in x.prc[::-1] for dlt in (0.0, -0.01, 0.01)]))
        if any(read_nav(raw, c) is not None for c in closes[1:]):   # closes[0] is the original exact close
            rec += 1
    say(f"\nM4. cheap fix (offline, cached filings): of {len(miss)} 'close not found' reports, {rec} yield a NAV against the "
        f"3 prior sessions' closes or +-$0.01 ({rec / max(len(miss), 1):.0%}); {err} not in the cache")
    gain = rec / 2.0
    say(f"    if all were in-life and kept, coverage would rise by about {gain / 2626.8:.1%} of candidate fund-half-years "
        f"(each report is one half-year; upper bound)")
    (HERE / "gate0_missingness_output.txt").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
