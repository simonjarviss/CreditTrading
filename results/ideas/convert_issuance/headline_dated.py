"""Convertible issues dated from the first news headline instead of SDC's issue date.

    QUANTT_ENV_FILE=<env> python3 results/ideas/convert_issuance/news_dating.py --year <each of 2015..2025>
    python3 results/ideas/convert_issuance/headline_dated.py

FIXED BEFORE ANY RETURN ON THESE DATES WAS READ (2026-11-15), but AFTER explore.py and
checks.py: this is a second look at the same events with better dates, not a fresh sample.
Counts read first: 430 of 1,286 SDC issues of 2015-2025 have a "convertible" headline on
Alpaca's feed in the eleven days around the issue date (8-30% a year to 2022, 46% in 2023,
69% and 73% in 2024 and 2025); in 2025 all but one first headline came outside trading hours.

  S0        the first session whose open (09:30 New York) comes after the first headline.
            It is the session the share reacts on.
  STRICT    the desk's convention applied to S0: decided at the close of S0 (price >= $2,
            21-session dollar volume >= $500,000, read at that close), filled at the close
            of S0+1, earns S0+2 through S0+6. Five sessions, as in explore.py.
  SAME DAY  filled at the close of S0 itself, earns S0+1 through S0+5. The headline is out
            before S0 opens, so an order for that close can be sent; but eligibility has to
            be read at the close of S0-1 and the harness's "decide at a close, fill at the
            next" does not describe it. Labelled as needing a morning decision.
  EXPECTED SIGN: positive for both, SAME DAY larger.
  POWER     about 430 events, 60% of them in 2023-2025: descriptive. It measures whether
            better dating helps; it cannot settle the size.

ALIGNMENT. follow_ons/explore.py's book earns d+3..d+7 and reads eligibility at row d+1.
STRICT sets d = S0-1 (decision row S0); SAME DAY sets d = S0-2 (weights from row S0-1).
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
from scripts.research import explore  # noqa: E402

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("cv_explore", HERE / "explore.py")
cv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(cv)
fo = cv.fo


def main() -> int:
    ev, ret, prc, dv, iwm, sessions = cv.load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy(); R["IWM"] = iwm
    news = pd.concat([pd.DataFrame(json.loads(f.read_text())["events"]) for f in sorted((HERE / "news").glob("news_dating_*.json"))])
    news = news[news["first_ny"].notna()].copy()
    news["issue_date"] = pd.to_datetime(news["issue_date"])
    t = pd.to_datetime(news["first_ny"], utc=True).dt.tz_convert("America/New_York")
    day = t.dt.tz_localize(None).dt.normalize()
    before_open = (t.dt.hour * 60 + t.dt.minute) < 9 * 60 + 30
    # S0: the headline's own date if it is a session and the headline precedes 09:30; else the next session
    pos = sessions.searchsorted(day.to_numpy(), side="left")
    same = (pos < len(sessions)) & (sessions[np.clip(pos, 0, len(sessions) - 1)] == day.to_numpy()) & before_open.to_numpy()
    news["s0"] = np.where(same, pos, sessions.searchsorted(day.to_numpy(), side="right"))
    e = fo.place(ev, sessions, prc, adv)
    # the staged event file has no ticker; join on (issue date, order within the date) is unsafe, so
    # the news file's ticker is matched through the events' permno-ticker pairs read at staging time
    tick = pd.read_parquet(fo.RES / "sdc_convertibles_tickers.parquet")
    e = e.merge(tick, on=["permno", "issue_date"], how="left").merge(
        news[["ticker", "issue_date", "s0"]].drop_duplicates(["ticker", "issue_date"]), on=["ticker", "issue_date"], how="inner")
    out = {"panel_last_date": str(sessions[-1].date()), "events_with_headline_placed": int(len(e)),
           "s0_minus_sdc_date_sessions": (e["s0"] - e["d"]).value_counts().sort_index().to_dict()}
    print(json.dumps(out, indent=1, default=int))
    P, A = prc.to_numpy(), adv.to_numpy()
    cols = prc.columns.get_indexer(e["permno"])
    for label, off in (("strict", 1), ("same_day", 2)):
        x = e.copy()
        x["d"] = x["s0"] - off
        x = x[(x["d"] >= 0) & (x["d"] + 1 < len(sessions))]
        c2 = prc.columns.get_indexer(x["permno"])
        row = x["d"].to_numpy() + 1
        x["ok"] = (P[row, c2] >= fo.MIN_PRICE) & (A[row, c2] >= fo.MIN_ADV)
        pnl, m = fo.run(x, "rebound", sessions, R)
        pnl = pnl.loc["2015-01-01":]
        s = explore.stats(pnl)
        yr = sessions[x["s0"].to_numpy()].year
        rn, im = ret.to_numpy(), iwm.to_numpy()
        el = x[x["ok"] & (x["d"] + 7 < len(sessions))]
        cp = ret.columns.get_indexer(el["permno"])
        ep = pd.Series([float(np.nansum(rn[d + 3:d + 8, c] - im[d + 3:d + 8])) for d, c in zip(el["d"].to_numpy(), cp)], index=el.index)
        mon = pd.Series(sessions[el["s0"].to_numpy()].to_period("M"), index=el.index)
        mm = ep.groupby(mon).mean()
        ely = pd.Series(sessions[el["s0"].to_numpy()].year, index=el.index)
        out[label] = {**s, "events_traded": m["events_traded"],
                      "sharpe_2015_22": explore.stats(pnl.loc[:"2022-12-31"])["sharpe"], "sharpe_2023_25": explore.stats(pnl.loc["2023-01-01":])["sharpe"],
                      "per_event_pct": {"n": int(len(ep)), "mean": float(ep.mean() * 100), "median": float(ep.median() * 100),
                                        "share_positive": float((ep > 0).mean()), "t_by_month": float(mm.mean() / mm.std() * np.sqrt(len(mm))),
                                        "mean_2015_22": float(ep[ely <= 2022].mean() * 100), "n_2015_22": int((ely <= 2022).sum()),
                                        "mean_2023_25": float(ep[ely >= 2023].mean() * 100), "n_2023_25": int((ely >= 2023).sum())}}
        o = out[label]
        print(f"  {label}: SR {o['sharpe']:.2f} t {o['t']:.2f} ret/yr {o['ann_ret']:.2%} n {o['events_traded']} | 2015-22 {o['sharpe_2015_22']:.2f} | 2023-25 {o['sharpe_2023_25']:.2f} | per event", {k: round(v, 2) for k, v in o["per_event_pct"].items()})
    # event-time profile from S0
    x = e.copy(); x["d"] = x["s0"]
    row = np.clip(x["s0"].to_numpy(), 0, len(sessions) - 1)
    x = x[(P[row, cols] >= fo.MIN_PRICE) & (A[row, cols] >= fo.MIN_ADV)]
    out["profile_from_s0"] = fo.profile(x, ret, iwm, -3, 10)
    print("  profile from S0 (bp, t by month):", " ".join(f"{a}:{v['mean_bp']:+.0f}({v['t_by_month']:+.1f})" for a, v in out["profile_from_s0"].items()))
    (HERE / "headline_dated.json").write_text(json.dumps(out, indent=1, default=int))
    return 0


if __name__ == "__main__":
    sys.exit(main())
