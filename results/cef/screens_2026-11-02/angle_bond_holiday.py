"""Angle E: close catalogue row CA9 (bond-holiday stale NAVs) with its own named kill test:
how many band trades were DECIDED on a bond-holiday evening, and what did they earn?
Zero trials; fit data only (<= 2022-12-30, asserted).

WHY IT IS STILL OPEN. W4 (results/cef/W4_ARTIFACTS_2026-10-11.md section 3e [S]) found the NAV
unchanged on 42% of name-days on Columbus/Veterans Day against 17.5% otherwise, and the IC barely
moving when those days are dropped. The catalogue (SPECIAL_SITUATIONS_CATALOGUE_CREDIT_2026-10-15
section 4.6) left one kill test unrun: "the number of band trades decided on them ... It ends the
discussion if ... the band decided no trades on them." The next live case is 2026-11-11, and the
live stale-NAV gate (quantt/session/nav_gate.py) will classify a bond-holiday repeat that
CEFConnect confirms as a GENUINE REPEAT and keep it, so the book WILL decide on it.

MEASURE. Decision dates t = SIFMA full-close days on which the NYSE trades (w4_artifacts.bond_holidays:
Columbus Day; Veterans Day, Monday when the 11th is a Sunday, none when a Saturday [U: SIFMA's
Saturday practice not fetched]). The trade decided at t is H[t] - H[t-1], filled at t+1's close;
its P&L over t+2..t+6 is sum_j (H[t]-H[t-1]) . R[t+j]. Per unit of turnover, against:
CONTROL (named first): the trades decided 5 sessions before and 5 sessions after each holiday
(same weekday, same season), and all trade dates.

Run from the repo root:  python3 -B results/cef/screens_2026-11-02/angle_bond_holiday.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import angle_common as c                                         # noqa: E402
from scripts.cef.w4_artifacts import bond_holidays              # noqa: E402

HORIZON = 5


def trade_pnl(H, R, dates):
    rows = []
    idx = H.index
    for d in dates:
        i = idx.get_loc(d)
        if i < 1 or i + 1 + HORIZON >= len(idx):
            continue
        dlt = H.iloc[i] - H.iloc[i - 1]
        tv = float(dlt.abs().sum())
        if tv <= 1e-12:
            rows.append(dict(date=d, turnover=0.0, pnl=0.0))
            continue
        fwd = R.iloc[i + 2:i + 2 + HORIZON]                      # t+2 .. t+6 (fill at t+1's close)
        rows.append(dict(date=d, turnover=tv, pnl=float((fwd * dlt).sum(axis=1).sum())))
    return pd.DataFrame(rows)


def summarise(df, lab):
    tr = df[df.turnover > 0]
    return dict(set=lab, dates=int(len(df)), dates_with_trades=int(len(tr)),
                turnover_total=float(df.turnover.sum()),
                pnl_bp_per_unit_turnover=float(1e4 * tr.pnl.sum() / tr.turnover.sum()) if len(tr) else float("nan"),
                pnl_total_pct_capital=float(100 * df.pnl.sum()))


def main():
    T, R, R_tr, H, p = c.live_book()
    act = H.abs().sum(axis=1) > 0
    idx = H.index
    bh = [d for d in bond_holidays(idx) if act.get(d, False)]
    ctrl = []
    for d in bh:
        i = idx.get_loc(d)
        ctrl += [idx[i - 5]] if i >= 5 else []
        ctrl += [idx[i + 5]] if i + 5 < len(idx) else []
    all_dates = [d for d in idx[1:] if act.get(d, False)]
    s = [summarise(trade_pnl(H, R_tr, bh), "bond-holiday decisions"),
         summarise(trade_pnl(H, R_tr, ctrl), "CONTROL: +/-5 sessions"),
         summarise(trade_pnl(H, R_tr, all_dates), "all active decision dates")]
    tab = pd.DataFrame(s)
    turn_all = H.diff().abs().sum(axis=1)[act]
    share = float(tab.loc[0, "turnover_total"] / turn_all.sum())
    out = dict(spec=c.SPEC_LINE, panel_last=str(idx.max().date()), holidays_active=[str(d.date()) for d in bh],
               table=tab.to_dict(orient="records"), holiday_share_of_turnover=share,
               holiday_share_of_dates=float(len(bh) / act.sum()))
    print(f"bond holidays with an active book, fit: {len(bh)}  ({[str(d.date()) for d in bh]})")
    print(tab.round(3).to_string(index=False))
    print(f"share of fit turnover decided on bond holidays: {share:.2%}; share of active dates: {len(bh) / act.sum():.2%}")
    (HERE / "angle_bond_holiday_output.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
