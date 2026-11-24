"""Pre-2023 daily VOLUME for every listed preferred and baby bond in today's census (Alpaca SIP).

    export QUANTT_ENV_FILE=<absolute path to the env file>       # never printed
    python3 scripts/events/ssx/ssx_lcred_volume.py fetch          # one pass of /v2/stocks/bars, volume kept
    python3 scripts/events/ssx/ssx_lcred_volume.py summary        # offline: first bar, ADV, no-trade share

WHY
---
CRSP holds no preferreds (corp catalogue L1), so the only free pre-2023
volume history for $25-par listed credit is Alpaca's SIP bars, which start in
2016. Four ideas need it, and all four need VOLUME ONLY:
  * C1: the first exchange trading day of each surviving issue (its first bar)
    and its first-month volume;
  * C7: BDC baby bonds' ADV and the share of sessions with NO trade -- the
    direct measure of the stale-price trap that killed `leadlag` (a close on a
    no-trade day is a stale mark, not a transactable price);
  * CR15: days of ADV for PFF additions;
  * C4/C6: listing dates to locate prospectuses.
`alpaca_volume_bars` drops every price field before a frame exists and refuses
any bar from 2023-01-01 on (H13), so nothing here can compute a return.

Raw (unadjusted) volume. CORRECTED 2026-10-19: this docstring first said a
session with no bar is a session with no trade. Measured: Alpaca DOES emit
daily bars with v = 0 (e.g. GAINZ: 12% of its 2021-22 bars have fewer than 100
shares, some exactly 0), and every listed session had a bar, so "no bar" never
fired. A no-trade session is now a bar with v == 0 or n == 0, and a thin session
one with n <= 2 trades; both are counted against Alpaca's own calendar.

Survivorship: only issues listed TODAY are fetched; called and defaulted issues
are absent. First-bar dates on 2016-01-04 are left-censored (listed earlier).
ZERO TRIALS.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx.ssx_lcred_common import (CACHE, OUT, alpaca, alpaca_volume_bars, trading_sessions,
                                                 write_json)

START, END = dt.date(2016, 1, 1), dt.date(2022, 12, 31)
CENSUS = OUT / "census_2026-10-19.csv"
VOL = CACHE / "volume_daily_2016_2022.parquet"
SESS = CACHE / "sessions_2016_2022.parquet"


def cmd_fetch(args) -> None:
    cen = pd.read_csv(CENSUS)
    syms = sorted(cen[cen.exchange != "OTC"].symbol)
    c = alpaca()
    v = alpaca_volume_bars(c, syms, START, END)
    s = pd.DataFrame({"t": trading_sessions(c, START, END)})
    CACHE.mkdir(parents=True, exist_ok=True)
    v.to_parquet(VOL, index=False)
    s.to_parquet(SESS, index=False)
    print(f"symbols requested {len(syms)}; with any bar {v.symbol.nunique()}; rows {len(v)}; sessions {len(s)}")


def per_symbol() -> pd.DataFrame:
    v = pd.read_parquet(VOL)
    sess = pd.read_parquet(SESS).t.tolist()
    sess_idx = {d: i for i, d in enumerate(sess)}
    rows = []
    for sym, g in v.groupby("symbol"):
        g = g.sort_values("t")
        first, last = g.t.iloc[0], g.t.iloc[-1]
        n_sess = sess_idx[last] - sess_idx[first] + 1          # sessions while listed (within the window)
        rows.append({"symbol": sym, "first_bar": first, "last_bar": last, "censored_left": first <= dt.date(2016, 1, 6),
                     "sessions_listed": n_sess, "sessions_with_trade": int(((g.v > 0) & (g.n > 0)).sum()),
                     "no_trade_share": 1 - int(((g.v > 0) & (g.n > 0)).sum()) / n_sess,
                     "thin_share_n_le_2": float((g.n <= 2).sum() / n_sess),
                     "adv_shares_2022": float(g[g.t >= dt.date(2022, 1, 1)].v.sum()
                                              / max(1, sum(1 for d in sess if d >= max(first, dt.date(2022, 1, 1))))),
                     "first21_shares": int(g.head(21).v.sum()) if not (first <= dt.date(2016, 1, 6)) else None,
                     "first21_median_daily": float(g.head(21).v.median()) if not (first <= dt.date(2016, 1, 6)) else None})
    return pd.DataFrame(rows)


def cmd_summary(args) -> None:
    ps = per_symbol()
    cen = pd.read_csv(CENSUS)
    ps = ps.merge(cen[["symbol", "kind", "bdc_issuer", "shortable", "exchange"]], on="symbol", how="left")
    ps.to_csv(OUT / "volume_per_symbol_2016_2022.csv", index=False)
    out = {"window": [str(START), str(END)], "symbols_with_bars": int(len(ps)),
           "census_non_otc": int((cen.exchange != "OTC").sum()),
           "price_fields": "dropped at fetch (volume only)"}
    ps["first_year"] = pd.to_datetime(ps.first_bar).dt.year
    unc = ps[~ps.censored_left]
    out["first_bar_year_survivors"] = unc.groupby(["first_year", "kind"]).size().unstack(fill_value=0).to_dict(orient="index")
    out["left_censored_listed_by_2016_01"] = int(ps.censored_left.sum())
    out["first21_median_daily_shares_by_year"] = {int(k): round(float(g.first21_median_daily.median()), 0)
                                                  for k, g in unc.groupby("first_year")}
    out["first21_median_daily_par_usd_by_year"] = {int(k): round(float(g.first21_median_daily.median()) * 25, 0)
                                                   for k, g in unc.groupby("first_year")}
    write_json(OUT / "volume_summary.json", out)
    print(json.dumps(out, indent=1, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("fetch")
    sp.add_parser("summary")
    a = ap.parse_args(argv)
    {"fetch": cmd_fetch, "summary": cmd_summary}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
