"""Explore: the Treasury auction concession. Short the matching-maturity ETF into a coupon
auction, long after it. Gross, shift(2), on the canonical harness.

    python3 results/ideas/ust_auction_cycle/explore.py

FIXED BEFORE LOOKING: with A the auction's session, the book is SHORT over the returns of
A-2 and A-1 and LONG over A+1 and A+2; the auction day itself is left out (the result
arrives at 13:00 and the day's return mixes before and after). 7- and 10-year note
auctions map to IEF; 20- and 30-year bond auctions to TLT. Overlapping windows net and are
clipped to one unit. Also printed, as description: the mean return on each session from
A-5 to A+5, which is how the shape is checked rather than assumed.

LOOKAHEAD: the weight that earns A-2 is decided at A-4, so the auction must be known four
sessions ahead. The panel here (Treasury FiscalData, `data/auction/auction_calendar.parquet`)
carries the auction date but NOT the announcement date. Coupon auctions follow a regular
published cycle, so this is likely safe, but it is [U] until the announcement dates are
fetched; the shadow book must use them.
Control: the same rule on placebo dates 10 sessions after each auction.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

HERE = Path(__file__).resolve().parent
MAP = {"IEF": (7.0, 10.0), "TLT": (20.0, 30.0)}
SHORT_OFFSETS, LONG_OFFSETS = (-2, -1), (1, 2)


def earn_frame(cal: pd.DatetimeIndex, auctions: dict, shift: int = 0) -> pd.DataFrame:
    """Signed exposure EARNED on each session, per ETF (before the harness's lag)."""
    pos = {d: i for i, d in enumerate(cal)}
    out = pd.DataFrame(0.0, index=cal, columns=list(auctions))
    for sym, dates in auctions.items():
        for A in dates:
            i = int(np.searchsorted(cal, A))             # first session on or after the auction date
            if i >= len(cal) or cal[i] != A:
                continue                                  # an auction on a day the ETF did not trade: skipped, counted below
            i += shift
            for k, sign in [(k, -1.0) for k in SHORT_OFFSETS] + [(k, 1.0) for k in LONG_OFFSETS]:
                if 0 <= i + k < len(cal):
                    out.iloc[i + k, out.columns.get_loc(sym)] += sign
    return out.clip(-1.0, 1.0)


def main() -> int:
    px = pd.read_parquet(Path.home() / "quantt_research" / "yf_daily.parquet")
    R = px[px["ticker"].isin(MAP)].pivot(index="date", columns="ticker", values="ret_total").dropna()
    cal = R.index
    a = pd.read_parquet(Path.home() / "quantt_data" / "auction" / "auction_calendar.parquet")
    a = a[(a["coupon_type"] == "nominal_coupon")]
    a_last = a["auction_date"].max().date()
    auctions, skipped = {}, 0
    for sym, terms in MAP.items():
        d = pd.DatetimeIndex(sorted(set(a.loc[a["term_years"].isin(terms), "auction_date"])))
        d = d[(d >= cal[10]) & (d <= cal[-10])]
        skipped += int((~d.isin(cal)).sum())
        auctions[sym] = d
    R = R.loc[:pd.Timestamp(a_last)]                      # no auction dates after the calendar's end
    cal = R.index
    # ALIGNMENT: harness.evaluate holds H.loc[t] over the return of t+2, so H = earn.shift(-2):
    # the decision is made two sessions before the session it earns, from the auction
    # schedule alone (see LOOKAHEAD above), never from a price.
    earn = earn_frame(cal, auctions) / len(MAP)
    H = earn.shift(-harness.EXEC_LAG).fillna(0.0)
    pnl = harness.evaluate(H, R)["pnl"].iloc[10:]
    plc = earn_frame(cal, auctions, shift=10) / len(MAP)
    ctrl = harness.evaluate(plc.shift(-harness.EXEC_LAG).fillna(0.0), R)["pnl"].iloc[10:]
    legs = {f"{s} only": harness.evaluate(H[[s]] * len(MAP), R[[s]])["pnl"].iloc[10:] for s in MAP}
    # CONFOUND CHECK: 7-year auctions fall in the last week of a month, so "long after the
    # auction" overlaps the month-end window that `month_end_ief` already trades (the last
    # three sessions of a month). The same P&L with those sessions zeroed says how much of
    # this idea is that one.
    s = pd.Series(cal, index=cal)
    last3 = set()
    for _, g in s.groupby([cal.year, cal.month]):
        last3 |= set(g.iloc[-3:])
    outside = pnl.where(~pnl.index.isin(last3), 0.0)
    legs["outside the month-end window"] = outside
    # description: mean return by session relative to the auction
    prof = {}
    for sym, dates in auctions.items():
        idx = [int(np.searchsorted(cal, A)) for A in dates if A in cal]
        for k in range(-5, 6):
            v = np.array([R[sym].iloc[i + k] for i in idx if 0 <= i + k < len(cal)])
            prof[f"{sym} A{k:+d}"] = {"mean_bp": float(v.mean() * 1e4), "t": float(v.mean() / v.std() * np.sqrt(len(v))), "n": int(len(v))}
    res = explore.summarise(pnl, controls={"placebo dates (A+10)": ctrl, **legs}, extra={
        "panel_last_date": str(cal.max().date()), "auction_calendar_last_date": str(a_last),
        "auctions": {s: int(len(d)) for s, d in auctions.items()}, "auctions_on_non_sessions_skipped": skipped,
        "event_time_profile": prof, "share_of_days_in_market": float((pnl != 0).mean())})
    explore.write(HERE, res, pnl, title=f"Short IEF/TLT two sessions into a coupon auction, long two after; shift(2), gross; to {cal.max().date()}",
                  controls={"placebo dates (A+10)": ctrl})
    print("prices to", cal.max().date(), "| auctions to", a_last, "|", res["auctions"], "| skipped", skipped)
    print(explore.table(res))
    for sym in MAP:
        print(sym, " ".join(f"A{k:+d}:{prof[f'{sym} A{k:+d}']['mean_bp']:+.1f}({prof[f'{sym} A{k:+d}']['t']:+.1f})" for k in range(-5, 6)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
