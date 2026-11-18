"""Checks on the S&P 600 change test. NONE OF THIS WAS PRE-SPECIFIED: written 2026-11-18 after
explore.py's results had been read. Run explore.py first (it writes the event list).

    python3 results/ideas/sp600_changes/checks.py

WHY EACH CHECK
  A  SECOND SOURCE. Membership is inferred from one fund's holdings (IJR). The count of 600
     OUT deletions jumps from about 10 a year to 58 / 45 / 24 in 2023 / 2024 / 2025, the
     years in which CRSP's holdings file carries many rows with no permno, CUSIP or ticker,
     which the guard in explore.py cannot see. VIOO (Vanguard's S&P 600 fund) is asked: at
     its first report on or after r1 (not more than 45 days later), does it still hold the
     share? CONFIRMED = it does not. STILL HELD = the "deletion" is a mapping gap in IJR,
     not an index change. Additions the same way round (CONFIRMED = VIOO holds it).
     Events with no VIOO report in the window (all of 2008-2010, and the months VIOO is
     missing) are UNCHECKED. The per-event figures are then re-read on CONFIRMED only.
  B  ERA TABLE PER EVENT, buy and hold (the calendar-time book is flat on most days, so its
     era Sharpes rest on few sessions).
  C  LIQUIDITY. Per event on price >= $5 and 21-session dollar volume >= $1M at d.
  D  A FEW WINNERS. Mean without the best and worst 1% of events.
  E  GONE SOON (uses the future: description only, not a rule). Events whose share has no
     CRSP return on some session in the 60 after the fill, i.e. it was delisted (taken
     over, or failed), against those that traded throughout.
All per-event figures are the share's compounded return over sessions d+2 .. d+1+H less
IWM's, exactly as in explore.py. Aggregates only are written (checks.json).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore  # noqa: E402,F401  (turns numexpr off)

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
OUT = RES / "sp600_changes"
HOLDS = (20, 60)
VIOO_WINDOW_DAYS = 45


def summ(v: pd.Series) -> dict:
    """v indexed by decision date. The t is on monthly cohort means, as in explore.py."""
    v = v.dropna()
    if len(v) < 5:
        return {"n": int(len(v))}
    cm = v.groupby(level=0).mean()
    return {"n": int(len(v)), "mean": float(v.mean()), "median": float(v.median()), "share_positive": float((v > 0).mean()),
            "cohort_t": float(cm.mean() / cm.std() * np.sqrt(len(cm))) if len(cm) > 2 and cm.std() > 0 else None}


def line(lab: str, s: dict) -> str:
    if s.get("n", 0) < 5:
        return f"   {lab}: n {s.get('n', 0)}"
    t = "n/a" if s["cohort_t"] is None else f"{s['cohort_t']:.2f}"
    return f"   {lab}: n {s['n']}, mean {s['mean']:+.2%}, median {s['median']:+.2%}, positive {s['share_positive']:.0%}, cohort t {t}"


def main() -> int:
    ev = pd.read_parquet(OUT / "events.parquet")
    ev = ev[(ev["index"] == "600") & (((ev["kind"] == "DEL") & (ev["cls"] == "OUT")) | ((ev["kind"] == "ADD") & (ev["cls"] == "NEW")))].copy()
    px = pd.read_parquet(OUT / "daily.parquet", columns=["permno", "date", "ret"], filters=[("permno", "in", sorted(set(ev["permno"])))])
    px["date"] = pd.to_datetime(px["date"])
    sessions = pd.DatetimeIndex(sorted(pd.read_parquet(OUT / "daily.parquet", columns=["date"])["date"].unique()))
    raw = px.pivot(index="date", columns="permno", values="ret").reindex(sessions)
    yf = pd.read_parquet(RES / "yf_daily.parquet")
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda x: pd.to_datetime(x["date"])).set_index("date")["ret_total"].reindex(sessions)
    pos = {d: i for i, d in enumerate(sessions)}
    R = raw.fillna(0.0).to_numpy(); M = iwm.fillna(0.0).to_numpy(); cp = {p: j for j, p in enumerate(raw.columns)}
    for H in HOLDS:
        vals, gone = [], []
        for r in ev.itertuples():
            i = pos[r.decided]; a, b = i + 2, i + 2 + H           # ALIGNMENT: first return earned is d+2
            if b > len(sessions):
                vals.append(np.nan); gone.append(np.nan); continue
            j = cp[r.permno]
            vals.append(np.prod(1 + R[a:b, j]) - 1 - (np.prod(1 + M[a:b]) - 1))
            gone.append(float(np.isnan(raw.iloc[a:b, j].to_numpy()).any()))
        ev[f"x{H}"] = vals; ev[f"gone{H}"] = gone

    # A: the second source
    h = pd.read_parquet(OUT / "holdings.parquet")
    h["report_dt"] = pd.to_datetime(h["report_dt"])
    v = h[(h["fund"] == "VIOO") & h["permno"].notna()]
    vl = {r: set(g["permno"].astype(int)) for r, g in v.groupby("report_dt")}
    vreps = sorted(vl)

    def vioo(r) -> str:
        nxt = [x for x in vreps if r.r1 <= x <= r.r1 + pd.Timedelta(days=VIOO_WINDOW_DAYS)]
        if not nxt:
            return "UNCHECKED"
        held = r.permno in vl[nxt[0]]
        return "CONFIRMED" if held == (r.kind == "ADD") else "NOT CONFIRMED"
    ev["vioo"] = [vioo(r) for r in ev.itertuples()]
    ev["year"] = ev["decided"].dt.year
    ev["era"] = pd.cut(ev["year"], [2001, 2008, 2015, 2019, 2022, 2030], labels=["2002-08", "2009-15", "2016-19", "2020-22", "2023-25"])

    out = {}
    for kind, name in (("DEL", "600 DEL OUT"), ("ADD", "600 ADD NEW")):
        g = ev[ev["kind"] == kind].set_index("decided", drop=False)
        o = {"vioo_by_year": {int(y): {k: int(n) for k, n in x["vioo"].value_counts().items()} for y, x in g.groupby("year")},
             "vioo_total": {k: int(n) for k, n in g["vioo"].value_counts().items()}}
        print(f"\n=== {name} (NOT PRE-SPECIFIED)\nA  VIOO: {o['vioo_total']}")
        print("   by year: " + "; ".join(f"{y} {d}" for y, d in o["vioo_by_year"].items()))
        for H in HOLDS:
            x = g[f"x{H}"]
            lo, hi = x.quantile(0.01), x.quantile(0.99)
            liquid = (g["prc_d"] >= 5) & (g["adv_d"] >= 1e6)
            oh = {"all": summ(x), "A vioo confirmed": summ(x[g["vioo"] == "CONFIRMED"]),
                  "A vioo not confirmed": summ(x[g["vioo"] == "NOT CONFIRMED"]), "A vioo unchecked": summ(x[g["vioo"] == "UNCHECKED"]),
                  "A confirmed or unchecked": summ(x[g["vioo"] != "NOT CONFIRMED"]),
                  "C price>=5 and adv>=1M": summ(x[liquid]), "C the rest": summ(x[~liquid]),
                  "D without best and worst 1%": summ(x[(x > lo) & (x < hi)]),
                  "E gone within the window (uses the future)": summ(x[g[f"gone{H}"] == 1]),
                  "E traded throughout (uses the future)": summ(x[g[f"gone{H}"] == 0])}
            for era, xe in x.groupby(g["era"], observed=True):
                oh[f"B era {era}"] = summ(xe)
            for era, xe in x[g["vioo"] != "NOT CONFIRMED"].groupby(g["era"][g["vioo"] != "NOT CONFIRMED"], observed=True):
                oh[f"B era {era}, confirmed or unchecked"] = summ(xe)
            o[f"hold_{H}"] = oh
            print(f"-- hold {H}, per event against IWM")
            for lab, s in oh.items():
                print(line(lab, s))
        out[name] = o
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
