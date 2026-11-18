"""The reconstitution calendar and the predicted bottom-edge sets, shared by stage.py and explore.py.

WHY ONE MODULE: stage.py must know which shares to pull daily rows for and explore.py must
score exactly those sets; two copies of the rule would drift.

THE CALENDAR (rules, with their source; the sessions come from the CRSP calendar itself).
  rank day   2000-2016  the last session of May.  [S: FTSE Russell "Four decades of Russell
                        reconstitution", timeline: "2017 - rank day moved to an earlier date in
                        May"; the May 31 rule before that is the long-standing one, U from recall]
             2017-05-12, 2018-05-11, 2019-05-10, 2021-05-07, 2022-05-06, 2023-04-28
                        [V: FTSE Russell releases found by search 2026-11-16]
             2020-05-08 [U: recalled, fits the pattern, not confirmed by a fetched page]
             2024-04-30, 2025-04-30 [V: FTSE Russell pages, same search]
  reconstitution day F (the close at which funds trade; the new index is live next session)
             2001-2003  the last session of June ("previously June 30th")
             2004-2006  the last Friday of June
             2007-2012  the last Friday of June unless it is the 28th, 29th or 30th, then the Friday before
             2013-      the last Friday of June unless it is the 29th or 30th, then the Friday before
                        [V: same FTSE Russell paper, timeline of enhancements, fetched 2026-11-16]

THE PREDICTION (what a trader without the licensed lists can do at the rank-day close).
  universe   CRSP common shares (securitytype EQTY, subtype COM, sharetype NS) with an active
             regular-way listing on NYSE, NYSE American or Nasdaq, of companies that are either
             US-incorporated (CRSP usincflg) or headquartered in the US (Compustat header `loc`,
             through the CCM link valid on rank day). The header is today's, not rank day's: a
             small lookahead in the country test only, stated.
  company    share classes of one company (CRSP permco) are summed to a company market value
             and the company is represented by its largest class. Unlisted classes are invisible.
  eligible   rank-day close of $1 or more and company market value of $30M or more, every year
             (the simple version: Russell's $30M floor and its averaged-price test for members
             are newer than 2001 and not reproduced by year; float below 5% cannot be seen).
  rank       eligible companies by company market value, largest first. Predicted Russell 3000
             = ranks 1 to 3000; nearly all of the bottom 2000 of it is the Russell 2000.
  banding    FTSE Russell's 2007 band (an existing member within 2.5 percentage points of
             cumulative market value of a breakpoint stays where it is) is described by its own
             paper for the breakpoint BETWEEN the Russell 1000 and 2000. I could not fetch the
             ground rules to confirm whether any band applies at rank 3000 and recall that it
             does not [U]. Simple version used: NO band at rank 3000 (a hard cut on rank), plus
             a "clear" variant that drops names within 100 ranks of the cut, where a float or
             share-count difference I cannot see is most likely to flip the prediction.
  sets, year y (prior = rank day of y-1; a share must be in the universe on BOTH rank days):
    ADD        not predicted member at y-1, rank 2501-3000 at y      (enters from below)
    DEL        predicted member at y-1, eligible rank 3001-3500 at y (leaves to below)
    STAY_IN    predicted member at y-1, rank 2501-3000 at y          (control: same zone, no change)
    STAY_OUT   not predicted member at y-1, eligible rank 3001-3500 at y  (control)
    ADD_ALL    not predicted member at y-1, rank 1-3000 at y         (secondary)
    DEL_ALL    predicted member at y-1, not ranked 1-3000 at y, incl. ineligible (secondary)
    ADD_CLEAR  ADD with rank 2501-2900;  DEL_CLEAR  DEL with rank 3101-3500
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FIXED_RANK_DAYS = {2017: "2017-05-12", 2018: "2018-05-11", 2019: "2019-05-10", 2020: "2020-05-08",
                   2021: "2021-05-07", 2022: "2022-05-06", 2023: "2023-04-28", 2024: "2024-04-30", 2025: "2025-04-30"}
FIRST_YEAR, LAST_YEAR = 2001, 2025
MIN_PRICE, MIN_CAP_K, CUT = 1.0, 30_000.0, 3000
SETS = ("ADD", "DEL", "STAY_IN", "STAY_OUT", "ADD_ALL", "DEL_ALL", "ADD_CLEAR", "DEL_CLEAR")


def calendar(sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """year -> rank day and reconstitution day, both CRSP sessions. Raises if either is not one."""
    s = pd.DatetimeIndex(sessions).sort_values().unique()
    rows = []
    for y in range(FIRST_YEAR - 1, LAST_YEAR + 1):
        if y in FIXED_RANK_DAYS:
            r = pd.Timestamp(FIXED_RANK_DAYS[y])
        else:
            r = s[(s.year == y) & (s.month == 5)].max()
        june = s[(s.year == y) & (s.month == 6)]
        if y <= 2003:
            f = june.max()
        else:
            fri = pd.date_range(f"{y}-06-01", f"{y}-06-30", freq="W-FRI")
            f = fri[-1]
            if f.day in ((28, 29, 30) if y <= 2012 else (29, 30)):
                f = fri[-2]
        if r not in s or f not in s:
            raise ValueError(f"{y}: rank day {r} or reconstitution day {f} is not a CRSP session")
        rows.append({"year": y, "rank_day": r, "recon_day": f})
    return pd.DataFrame(rows).set_index("year")


def rank_universe(rd: pd.DataFrame) -> pd.DataFrame:
    """One rank day's rows (one per share class) -> one row per company with its predicted rank.

    `rank` is NaN for an ineligible company; such a company is still 'in the universe'.
    """
    d = rd[(rd["usincflg"] == "Y") | (rd["loc"] == "USA")].copy()
    d = d[d["cap"].notna() & d["prc"].notna()]
    d["co_cap"] = d.groupby("permco")["cap"].transform("sum")
    d = d.sort_values(["permco", "cap"], ascending=[True, False]).drop_duplicates("permco")
    elig = (d["prc"].abs() >= MIN_PRICE) & (d["co_cap"] >= MIN_CAP_K)
    d["rank"] = np.nan
    d.loc[elig, "rank"] = d.loc[elig, "co_cap"].rank(ascending=False, method="first")
    return d.set_index("permno")


def build_sets(rankdays: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    """Long table year, permno, set, rank, prior_rank and the rank-day liquidity fields."""
    out, prev = [], None
    for y in range(FIRST_YEAR - 1, LAST_YEAR + 1):
        cur = rank_universe(rankdays[rankdays["date"] == cal.loc[y, "rank_day"]])
        if len(cur) < 3500:
            raise ValueError(f"{y}: only {len(cur)} companies on rank day; the panel is short")
        if prev is not None:
            both = cur.join(prev[["rank"]].rename(columns={"rank": "prior_rank"}), how="inner")
            was = both["prior_rank"] <= CUT
            rk = both["rank"]
            near_in, near_out = rk.between(CUT - 499, CUT), rk.between(CUT + 1, CUT + 500)
            masks = {"ADD": ~was & near_in, "DEL": was & near_out, "STAY_IN": was & near_in, "STAY_OUT": ~was & near_out,
                     "ADD_ALL": ~was & (rk <= CUT), "DEL_ALL": was & ~(rk <= CUT),
                     "ADD_CLEAR": ~was & rk.between(CUT - 499, CUT - 100), "DEL_CLEAR": was & rk.between(CUT + 101, CUT + 500)}
            for name, m in masks.items():
                g = both[m].reset_index()[["permno", "rank", "prior_rank", "co_cap", "prc", "bid", "ask", "siccd"]]
                out.append(g.assign(year=y, set=name))
        prev = cur
    return pd.concat(out, ignore_index=True)
