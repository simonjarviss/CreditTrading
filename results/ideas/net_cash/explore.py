"""Explore: companies priced below their net cash.

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_comp_net_cash.py
    python3 results/ideas/net_cash/explore.py

WHY: a company whose market value is less than its cash after all debt is, on paper, being
given away. The niche hunt of 2026-11-15 proposed the biotech case and its skeptic answered
"biotech beta in a bear market" (results/ideas/2026-11-15_niche_hunt.md). It exists only in
very small companies, which is the team lead's brief of 2026-11-15, and no return on it
has been read on this desk.

FIXED BEFORE ANY RETURN WAS READ (2026-11-16). Only counts had been read: 100 to 580
securities a year with net cash at or above market value, 1999-2025.
  SIGNAL    at each month's last session, the latest Compustat quarter REPORTED on or before
            that day and not more than 200 days old: net cash = cash and short-term
            investments less all debt, over that day's market value.
  ELIGIBLE  on that day: not a financial company (SIC 6000-6999, where cash is the stock in
            trade), price $1 or more, market value $10M or more, 21-session average dollar
            volume $100,000 or more, and the share traded that day.
  BELOW     net cash at or above market value: all eligible names, equal weights, 100% long
            against IWM 100% short. Decided at the month's last close, filled at the next
            close, held to the next month's fill (shift(2)). Flat under 10 names.
  STRICT    cash above ALL liabilities and market value (the same book on the harder test).
  CONTROL   NEAR: net cash from half to under one times market value: cash-rich small
            companies that are NOT below cash. A result about being below cash needs BELOW
            above NEAR; a result that is small cash-rich companies in general does not.
  SPLITS    stated in advance because the skeptic named them: drug and biotech companies
            (SIC 2833-2836 and 8731) against the rest; and by era.
  EXPECTED  BELOW positive against IWM and above NEAR.
  DESCRIPTIVE ONLY: names held, turnover, dollar volume of the names held, the share of
            held name-days with no CRSP return (counted as zero).
Gross; no cost is modelled. Writes results.json beside this file.
"""
from __future__ import annotations

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
MIN_PRICE, MIN_CAP_K, MIN_ADV, MIN_NAMES = 1.0, 10_000.0, 100_000.0, 10
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
    sig = sig[sig["date"].isin(set(month_last))]                      # the share traded on the month's last session
    sig = sig[sig["permno"].isin(ret.columns)]
    sic = pd.to_numeric(sig["siccd"], errors="coerce")
    a = adv.stack().rename("adv").reset_index()
    sig = sig.merge(a, on=["date", "permno"], how="left")
    ok = (~sic.between(6000, 6999).to_numpy()) & (sig["prc"].abs() >= MIN_PRICE) & (sig["cap"] >= MIN_CAP_K) & (sig["adv"] >= MIN_ADV)
    sig = sig[ok.to_numpy()].copy()
    sig["bio"] = pd.to_numeric(sig["siccd"], errors="coerce").isin(BIO)
    R = ret.fillna(0.0).loc[start:]
    R["IWM"] = iwm.loc[start:]
    if R["IWM"].isna().any():
        raise ValueError("IWM has no return on a CRSP session inside its own range")

    def book(rows: pd.DataFrame):
        """Daily weights: each month-end's equal-weight list, carried to the next month end."""
        w = rows.assign(one=1.0).pivot(index="date", columns="permno", values="one").reindex(month_last.values).fillna(0.0)
        n = w.sum(axis=1)
        w = w.div(n.where(n >= MIN_NAMES), axis=0).fillna(0.0)
        H = w.reindex(sessions).ffill().fillna(0.0).reindex(columns=ret.columns, fill_value=0.0).loc[start:]
        H["IWM"] = -H.sum(axis=1)
        res = harness.evaluate(H, R)
        names = H.drop(columns="IWM")
        held = harness.held(names)
        miss = int(((held != 0) & ret.loc[start:].isna()).sum().sum())
        return res["pnl"], {"names_mean": float(n[n >= MIN_NAMES].mean()) if (n >= MIN_NAMES).any() else 0.0,
                            "months_invested": int((n >= MIN_NAMES).sum()), "months": int(len(n)),
                            "turnover_per_year": float(res["turn"]), "held_name_days": int((held != 0).sum().sum()),
                            "held_name_days_without_return": miss}

    sets = {"BELOW": sig[sig["net_cash_to_cap"] >= 1], "STRICT": sig[sig["strict_to_cap"] >= 1],
            "NEAR (control)": sig[(sig["net_cash_to_cap"] >= 0.5) & (sig["net_cash_to_cap"] < 1)],
            "BELOW, drugs and biotech": sig[(sig["net_cash_to_cap"] >= 1) & sig["bio"]],
            "BELOW, everything else": sig[(sig["net_cash_to_cap"] >= 1) & ~sig["bio"]],
            "NEAR, drugs and biotech": sig[(sig["net_cash_to_cap"] >= 0.5) & (sig["net_cash_to_cap"] < 1) & sig["bio"]],
            "NEAR, everything else": sig[(sig["net_cash_to_cap"] >= 0.5) & (sig["net_cash_to_cap"] < 1) & ~sig["bio"]]}
    out = {"panel_last_date": str(sessions[-1].date()), "first_return": str(start.date()),
           "fixed": {"min_price": MIN_PRICE, "min_cap_usd": MIN_CAP_K * 1000, "min_adv": MIN_ADV, "min_names": MIN_NAMES}}
    pnl = {}
    for name, rows in sets.items():
        p, info = book(rows)
        p = p.iloc[harness.EXEC_LAG:]
        pnl[name] = p
        res = explore.summarise(p)
        out[name] = {**info, "eligible_rows": int(len(rows)), "share_bio": float(rows["bio"].mean()) if len(rows) else None,
                     "median_adv_usd": float(rows["adv"].median()) if len(rows) else None,
                     "median_cap_usd": float(rows["cap"].median() * 1000) if len(rows) else None, **res}
        print(f"\n== {name}: {info['names_mean']:.0f} names, invested {info['months_invested']}/{info['months']} months, turnover {info['turnover_per_year']:.1f}/yr, "
              f"median ADV ${out[name]['median_adv_usd']:,.0f}, median cap ${out[name]['median_cap_usd'] / 1e6:,.0f}M, no-return name-days {info['held_name_days_without_return']} of {info['held_name_days']}")
        print(explore.table(res))
    for a_, b_ in (("BELOW", "NEAR (control)"), ("BELOW, drugs and biotech", "NEAR, drugs and biotech"), ("BELOW, everything else", "NEAR, everything else")):
        d = (pnl[a_] - pnl[b_]).dropna()
        s = explore.stats(d)
        out[f"{a_} less {b_}"] = {**s, "halves": [explore.stats(d.iloc[:len(d) // 2])["sharpe"], explore.stats(d.iloc[len(d) // 2:])["sharpe"]]}
        print(f"\n{a_} less {b_}: SR {s['sharpe']:.2f} (t {s['t']:.2f}), {s['ann_ret']:.2%} a year; halves {out[f'{a_} less {b_}']['halves']}")
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
