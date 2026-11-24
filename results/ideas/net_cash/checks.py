"""Checks on the below-net-cash book. NONE pre-specified: written 2026-11-16 after explore.py's
first run, to see whether the result survives the obvious objections.

    python3 results/ideas/net_cash/checks.py

  liquid      the same book on price >= $2 and dollar volume >= $500,000: can it be traded?
  one month late   the lists one month stale: is it the news in the balance sheet, or a slow trait?
  by era, against the control   BELOW less NEAR on each era (the pre-specified comparison, split).
  no flat rule on the splits    the drug/other split in explore.py goes flat under 10 names,
                    which hid most of each side. Here every month with at least 3 names is held.
  beta        BELOW's daily P&L regressed on IWM and on the NEAR control.
  per name-month   the distribution of one-month excess returns of held names, and the book
                    without its 20 best name-months.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
ERAS = {"2002-08": ("2002", "2008"), "2009-15": ("2009", "2015"), "2016-19": ("2016", "2019"), "2020-22": ("2020", "2022"), "2023-25": ("2023", "2025")}
BIO = set(range(2833, 2837)) | {8731}


def main() -> int:
    sig = pd.read_parquet(RES / "comp_net_cash_monthly.parquet")
    px = pd.read_parquet(RES / "crsp_net_cash_daily.parquet", columns=["permno", "date", "ret", "prc", "dollar_volume"])
    px["date"] = pd.to_datetime(px["date"]); sig["date"] = pd.to_datetime(sig["date"])
    ret = px.pivot(index="date", columns="permno", values="ret")
    adv = px.pivot(index="date", columns="permno", values="dollar_volume").rolling(21, min_periods=10).mean()
    sessions = ret.index
    del px
    yf = pd.read_parquet(RES / "yf_daily.parquet")
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"].reindex(sessions)
    start = iwm.dropna().index.min()
    month_last = pd.Series(sessions, index=sessions).groupby(sessions.to_period("M")).max()
    sig = sig[sig["date"].isin(set(month_last)) & sig["permno"].isin(ret.columns)]
    sig = sig.merge(adv.stack().rename("adv").reset_index(), on=["date", "permno"], how="left")
    sic = pd.to_numeric(sig["siccd"], errors="coerce")
    sig = sig[~sic.between(6000, 6999).to_numpy()].copy()
    sig["bio"] = pd.to_numeric(sig["siccd"], errors="coerce").isin(BIO)
    R = ret.fillna(0.0).loc[start:]
    R["IWM"] = iwm.loc[start:]

    def book(rows, *, min_names=10, delay_months=0):
        w = rows.assign(one=1.0).pivot(index="date", columns="permno", values="one").reindex(month_last.values).fillna(0.0)
        w = w.shift(delay_months).fillna(0.0)
        n = w.sum(axis=1)
        w = w.div(n.where(n >= min_names), axis=0).fillna(0.0)
        H = w.reindex(sessions).ffill().fillna(0.0).reindex(columns=ret.columns, fill_value=0.0).loc[start:]
        H["IWM"] = -H.sum(axis=1)
        return harness.evaluate(H, R)["pnl"].iloc[harness.EXEC_LAG:], n

    def base(d, price=1.0, adv_min=100_000.0):
        return d[(d["prc"].abs() >= price) & (d["cap"] >= 10_000.0) & (d["adv"] >= adv_min)]

    def line(label, p, out, n=None):
        s = explore.stats(p)
        out[label] = {**{k: s[k] for k in ("sharpe", "t", "ann_ret", "ann_vol", "max_drawdown")},
                      "halves": [explore.stats(p.iloc[:len(p) // 2])["sharpe"], explore.stats(p.iloc[len(p) // 2:])["sharpe"]],
                      "by_era": {k: explore.stats(p.loc[a:b])["sharpe"] for k, (a, b) in ERAS.items()},
                      "names": None if n is None else float(n[n > 0].mean())}
        o = out[label]
        print(f"  {label:52s} SR {o['sharpe']:5.2f} (t {o['t']:5.2f}) ret {o['ann_ret']:7.2%} vol {o['ann_vol']:6.2%} dd {o['max_drawdown']:7.1%} | "
              f"{o['halves'][0]:.2f}/{o['halves'][1]:.2f} | " + " ".join(f"{k}:{v:.2f}" if v is not None else f"{k}:n/a" for k, v in o["by_era"].items())
              + (f" | names {o['names']:.0f}" if n is not None else ""))

    out = {"note": "not pre-specified", "panel_last_date": str(sessions[-1].date())}
    e = base(sig)
    below, near = e[e["net_cash_to_cap"] >= 1], e[(e["net_cash_to_cap"] >= 0.5) & (e["net_cash_to_cap"] < 1)]
    pb, nb = book(below); pn, nn = book(near)
    line("BELOW (as fixed)", pb, out, nb); line("NEAR (as fixed)", pn, out, nn)
    line("BELOW less NEAR", (pb - pn), out)
    liq = base(sig, 2.0, 500_000.0)
    pl, nl = book(liq[liq["net_cash_to_cap"] >= 1]); pln, nln = book(liq[(liq["net_cash_to_cap"] >= 0.5) & (liq["net_cash_to_cap"] < 1)])
    line("BELOW, price $2 and $500k a day", pl, out, nl); line("NEAR, price $2 and $500k a day", pln, out, nln)
    line("BELOW less NEAR, price $2 and $500k a day", pl - pln, out)
    p1, _ = book(below, delay_months=1); line("BELOW, lists one month late", p1, out)
    p3, _ = book(below, delay_months=3); line("BELOW, lists three months late", p3, out)
    for nm, m in (("drugs and biotech", True), ("everything else", False)):
        a, na = book(below[below["bio"] == m], min_names=3); b, _ = book(near[near["bio"] == m], min_names=3)
        on = (na.reindex(sessions, method="ffill").loc[a.index] >= 3)
        line(f"BELOW, {nm}, 3+ names", a, out, na)
        line(f"  less NEAR {nm}, on days BELOW is held", (a - b)[on.to_numpy()], out)
    x = pd.concat([pb.rename("y"), R["IWM"].reindex(pb.index).rename("iwm"), (pn + R["IWM"].reindex(pn.index)).rename("near_long")], axis=1).dropna()
    X = np.column_stack([np.ones(len(x)), x["iwm"], x["near_long"] - x["iwm"]])
    beta, *_ = np.linalg.lstsq(X, x["y"].to_numpy(), rcond=None)
    resid = x["y"].to_numpy() - X @ beta
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * resid.var(ddof=3))
    out["regression of BELOW (already less IWM) on IWM and NEAR-less-IWM"] = {"alpha_ann": float(beta[0] * 252), "alpha_t": float(beta[0] / se[0]),
                                                                              "beta_iwm": float(beta[1]), "beta_near": float(beta[2])}
    print("  regression:", {k: round(v, 3) for k, v in out["regression of BELOW (already less IWM) on IWM and NEAR-less-IWM"].items()})
    # per name-month: the held name's return from the fill (month end + 1) to the next fill, less IWM
    ml = list(month_last.values)
    cum = (1 + ret.fillna(0.0)).cumprod(); ci = (1 + iwm.fillna(0.0)).cumprod()
    pos = {d: i for i, d in enumerate(sessions)}
    rows = []
    for d, g in below.groupby("date"):
        k = ml.index(np.datetime64(d)) if np.datetime64(d) in ml else None
        if k is None or k + 1 >= len(ml) or d < start:
            continue
        a_, b_ = pos[pd.Timestamp(d)] + 1, pos[pd.Timestamp(ml[k + 1])] + 1
        if b_ >= len(sessions):
            continue
        r = cum.iloc[b_][g["permno"]].to_numpy() / cum.iloc[a_][g["permno"]].to_numpy() - 1
        rows += list(r - (ci.iloc[b_] / ci.iloc[a_] - 1))
    r = pd.Series(rows).dropna()
    out["per_name_month_less_iwm"] = {"n": int(len(r)), "mean": float(r.mean()), "median": float(r.median()), "share_positive": float((r > 0).mean()),
                                      "p5": float(r.quantile(0.05)), "p95": float(r.quantile(0.95)), "max": float(r.max()),
                                      "mean_without_20_best": float(r.sort_values().iloc[:-20].mean())}
    print("  per name-month less IWM:", {k: round(v, 4) for k, v in out["per_name_month_less_iwm"].items()})
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
