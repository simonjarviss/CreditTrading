"""Explore: newly converted savings institutions, the first year after the first week.

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_thrift_listings.py
    python3 results/ideas/thrift_conversions/explore.py

WHY: ranked first by the niche hunt of 2026-11-15 (results/ideas/2026-11-15_niche_hunt.md).
A mutual savings bank that converts sells shares to its depositors at $10 and keeps its old
capital as well, so it lists below tangible book; it may not buy back shares for a year or
be taken over for three (12 CFR 239.63). Friesen and Swift (2009) report, on a sample before
2009, positive excess returns for twelve months after the first-day jump and a correction in
the following eighteen. No return on these has been read on this desk. A handful list a year
and they are too small for a fund, which is the team lead's brief of 2026-11-15.

FIXED BEFORE ANY RETURN WAS READ (2026-11-15). Only counts had been read: 169 new listings
with SIC 6035/6036 since 1995, 147 with a first close of $8 to $16.
  EVENT     a US common share whose first CRSP row has SIC 6035 or 6036 and a first close
            from $8 to $16 (the $10 conversions; the first close is known at entry). Day 1 is
            the first row.
  BOOK      YEAR1: decided at the close of day 4, filled at the close of day 5, earns days
            6 to 250. Each name 10% of the book, all scaled down together when more than
            ten are held. Long only, and hedged two ways, reported side by side:
              against IWM (tradable; from 2000-05-30, when IWM has returns), and
              against the equal-weighted return of SEASONED savings institutions (listed
              over 1,150 days; not tradable, but the control that says whether the result
              is about conversions or about small thrifts).
  CONTROLS  LATER: the same names on days 251 to 630, the window the paper says is weak.
            A thrift-specific result needs YEAR1 above LATER against the seasoned index.
  EXPECTED  YEAR1 positive against both hedges; LATER near zero or negative.
  DESCRIPTIVE ONLY: eras, per-event returns, first-week return, dollar volume and the
            closing spread at entry, capacity. A liquidity cut (21-session dollar volume of
            $100,000 or more at day 5) is shown and was not used to choose anything.
A name with no CRSP return on a held day earns zero that day and is counted. Gross; no cost.
Writes results.json beside this file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore as _explore  # noqa: E402,F401  turns numexpr off (see its header)

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
SIZE, ENTER, EXIT1, EXIT2, LO, HI = 0.10, 5, 250, 630, 8.0, 16.0
ERAS = (("1995", "2001"), ("2002", "2008"), ("2009", "2015"), ("2016", "2025"))


def st(p: pd.Series) -> dict:
    p = p.dropna()
    sd = p.std()
    return {"n_days": int(len(p)), "ann_ret_pct": round(100 * p.mean() * 252, 2), "vol_pct": round(100 * sd * 252 ** 0.5, 2),
            "sharpe": round(p.mean() / sd * 252 ** 0.5, 2) if sd > 0 else None,
            "t": round(p.mean() / sd * len(p) ** 0.5, 2) if sd > 0 else None,
            "max_dd_pct": round(100 * (p.cumsum() - p.cumsum().cummax()).min(), 1)}


def main() -> int:
    ev = pd.read_parquet(RES / "crsp_thrift_events.parquet")
    px = pd.read_parquet(RES / "crsp_thrift_daily.parquet")
    ix = pd.read_parquet(RES / "crsp_thrift_index.parquet").assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret"]
    yf = pd.read_parquet(RES / "yf_daily.parquet")
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"].dropna()
    px["date"] = pd.to_datetime(px["date"])
    px = px.sort_values(["permno", "date"])
    px["k"] = px.groupby("permno").cumcount() + 1               # day 1 = the first row
    ev = ev[(ev["first_close"] >= LO) & (ev["first_close"] <= HI)].copy()
    px = px[px["permno"].isin(ev["permno"])]
    sessions = ix.index                                          # every CRSP session the index has
    last = px["date"].max()

    def held(lo: int, hi: int, keep=None) -> pd.DataFrame:
        """1 on the sessions a name EARNS: its own days lo..hi. Entry is the close of day lo-1,
        decided at the close of day lo-2: nothing dated after the decision is used."""
        d = px[(px["k"] >= lo) & (px["k"] <= hi)]
        if keep is not None:
            d = d[d["permno"].isin(keep)]
        return d.assign(one=1.0).pivot(index="date", columns="permno", values="one").reindex(sessions).fillna(0.0)

    ret = px.pivot(index="date", columns="permno", values="ret").reindex(sessions)

    def book(lo, hi, keep=None):
        on = held(lo, hi, keep)
        n = on.sum(axis=1)
        w = on.mul(np.minimum(SIZE, 1.0 / n.where(n > 0)).fillna(0.0), axis=0)
        r = ret.reindex(columns=w.columns)
        miss = int(((w > 0) & r.isna()).sum().sum())
        gross = w.sum(axis=1)
        return (w * r.fillna(0.0)).sum(axis=1), gross, n, miss

    # liquidity at entry: 21-session dollar volume through day 5 (5 rows exist; use what there is), and spread on day 5
    d5 = px[px["k"] <= ENTER].groupby("permno").agg(adv=("dollar_volume", "mean"))
    e5 = px[px["k"] == ENTER].set_index("permno")
    d5["spread"] = (e5["ask"] - e5["bid"]) / ((e5["ask"] + e5["bid"]) / 2)
    adv20 = px[(px["k"] > ENTER) & (px["k"] <= 60)].groupby("permno")["dollar_volume"].median()
    liquid = set(d5.index[d5["adv"] >= 100_000])

    out = {"panel_last": str(last.date()), "events": int(len(ev)), "first_listing_range": [str(ev.first_date.min())[:10], str(ev.first_date.max())[:10]],
           "events_by_era": {f"{a}-{b}": int(((ev.first_date.astype(str) >= a) & (ev.first_date.astype(str) <= b + "-12-31")).sum()) for a, b in ERAS},
           "median_dollar_volume_days_6_60": round(float(adv20.median()), 0),
           "dollar_volume_days_6_60_quartiles": [round(float(adv20.quantile(q)), 0) for q in (0.25, 0.5, 0.75)],
           "median_spread_day5_pct": round(float(100 * d5["spread"].median()), 2),
           "events_liquid_100k_first_week": len(liquid), "books": {}}
    for name, lo, hi, keep in (("YEAR1", ENTER + 1, EXIT1, None), ("LATER", EXIT1 + 1, EXIT2, None),
                               ("YEAR1 liquid", ENTER + 1, EXIT1, liquid)):
        long, gross, n, miss = book(lo, hi, keep)
        on = gross > 0
        blk = {"mean_names": round(float(n[on].mean()), 1), "share_of_sessions_invested": round(float(on.mean()), 2),
               "mean_gross": round(float(gross[on].mean()), 2), "held_days_without_return": miss}
        for hname, h in (("vs seasoned thrifts", ix), ("vs IWM", iwm.reindex(sessions))):
            p = (long - gross * h)
            p = p[h.notna()] if hname == "vs IWM" else p
            p = p.loc[p.ne(0).idxmax():] if p.ne(0).any() else p
            blk[hname] = {"full": st(p), "halves": [st(p.iloc[:len(p) // 2])["sharpe"], st(p.iloc[len(p) // 2:])["sharpe"]],
                          "eras": {f"{a}-{b}": st(p.loc[a:b])["sharpe"] for a, b in ERAS if len(p.loc[a:b]) > 250}}
        blk["long only"] = st(long[on.cummax()])
        out["books"][name] = blk

    # per event, descriptive: cumulative return less the seasoned index over each window
    rows = []
    for pn, g in px.groupby("permno"):
        g = g.set_index("k")
        def cum(lo, hi, g=g):
            s = g.loc[(g.index >= lo) & (g.index <= hi)]
            if len(s) < (hi - lo + 1) * 0.5:
                return np.nan, np.nan, np.nan
            r = s["ret"].fillna(0.0)
            b = ix.reindex(s["date"]).fillna(0.0).values
            m = iwm.reindex(s["date"]).values
            return float((1 + r).prod() - 1), float((1 + r).prod() - (1 + b).prod()), (float((1 + r).prod() - np.prod(1 + m)) if not np.isnan(m).any() else np.nan)
        w1, y1, la = cum(2, ENTER), cum(ENTER + 1, EXIT1), cum(EXIT1 + 1, EXIT2)
        rows.append({"permno": pn, "first": g["date"].iloc[0], "week1": w1[0], "y1": y1[0], "y1_x": y1[1], "y1_iwm": y1[2], "later_x": la[1], "later_iwm": la[2]})
    pe = pd.DataFrame(rows)
    def desc(c, sub=None):
        s = (pe if sub is None else pe[sub])[c].dropna()
        return {"n": int(len(s)), "mean_pct": round(100 * s.mean(), 2), "median_pct": round(100 * s.median(), 2),
                "share_positive": round(float((s > 0).mean()), 2), "t": round(float(s.mean() / s.std() * len(s) ** 0.5), 2),
                "p5_pct": round(100 * s.quantile(0.05), 1), "p95_pct": round(100 * s.quantile(0.95), 1)}
    out["per_event"] = {"days 2-5, raw": desc("week1"), "days 6-250, raw": desc("y1"),
                        "days 6-250 less seasoned thrifts": desc("y1_x"), "days 6-250 less IWM": desc("y1_iwm"),
                        "days 251-630 less seasoned thrifts": desc("later_x"), "days 251-630 less IWM": desc("later_iwm")}
    for a, b in ERAS:
        m = (pe["first"] >= a) & (pe["first"] <= b + "-12-31")
        out["per_event"][f"days 6-250 less seasoned thrifts, listed {a}-{b}"] = desc("y1_x", m)
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
