"""CR15 gate, second source: PFF's MONTHLY holdings from CRSP Mutual Funds (R2 WRDS mirror, licensed).

    export QUANTT_ENV_FILE=<absolute path to the env file>       # R2 keys, never printed
    python3 scripts/events/ssx/ssx_lcred_pff_crsp.py pull         # PFF rows 2018-12..2022-12 -> licensed cache
    python3 scripts/events/ssx/ssx_lcred_pff_crsp.py additions    # offline: monthly additions, days of ADV

WHY
---
ICE rebalances PFF's index on the last calendar day of each month (ICE Rules &
Methodology, 2021-12-26 copy). N-PORT-P's public snapshots are quarterly, so an
issue added and dropped inside one quarter is invisible there, and the month of
an addition is unknown. CRSP MF holdings for PFF are monthly (data librarian's
R2 inventory, 2026-10-19), so the addition month -- the event date -- is known
to the month-end, and the pre-event ADV window can end strictly before it.
The two sources are reported side by side, never averaged.

Holdout: only report dates 2018-12-31..2022-12-31 are read; pre-event volume
comes from `ssx_lcred_volume.py`'s pre-2023 cache. Licensed rows stay in the
gitignored cache; only aggregates go to `results/`.
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
from scripts.events.ssx.ssx_lcred_common import CACHE, OUT, write_json

RAW = CACHE / "pff_crsp_holdings_2018_2022.parquet"
PORTS = CACHE / "pff_crsp_portno.csv"


def cmd_pull(args) -> None:
    from src.data import r2
    con = r2.connect()
    pm = r2.r2_path("crsp_q_mutualfunds", "portnomap")
    ports = r2.q(con, f"select crsp_fundno, crsp_portno, begdt, enddt, fund_name, ticker from read_parquet('{pm}') "
                      "where ticker = 'PFF'")
    if ports.empty:
        raise KeyError("no PFF row in crsp_q_mutualfunds.portnomap")
    ports.to_csv(PORTS, index=False)
    ids = sorted({int(x) for x in ports.crsp_portno.dropna()})
    h = r2.r2_path("crsp_q_mutualfunds", "holdings")
    df = r2.q(con, f"select crsp_portno, report_dt, eff_dt, security_name, cusip, ticker, nbr_shares, market_val, "
                   f"percent_tna, coupon from read_parquet('{h}') where crsp_portno in ({','.join(map(str, ids))}) "
                   "and report_dt between DATE '2018-12-31' and DATE '2022-12-31'")
    df.to_parquet(RAW, index=False)
    print(f"PFF portno {ids}; rows {len(df)}; report dates {df.report_dt.nunique()}")


def cmd_additions(args) -> None:
    df = pd.read_parquet(RAW)
    df["report_dt"] = pd.to_datetime(df.report_dt).dt.date
    df = df[df.cusip.notna() & (df.cusip.str.len() >= 8)]
    df = df[~df.security_name.fillna("").str.contains("CASH|TREASURY TRUST|BLK CSH|BLACKROCK", case=False)]
    dates = sorted(df.report_dt.unique())
    keys = {d: set(df[df.report_dt == d].cusip) for d in dates}
    rows, per = [], []
    for i in range(1, len(dates)):
        d, p = dates[i], dates[i - 1]
        add = keys[d] - keys[p]
        rem = keys[p] - keys[d]
        per.append({"report_dt": d, "prev": p, "gap_days": (d - p).days, "holdings": len(keys[d]),
                    "added": len(add), "removed": len(rem)})
        for c in add:
            r = df[(df.report_dt == d) & (df.cusip == c)].iloc[0]
            rows.append({"cusip": c, "report_dt": d, "prev": p, "ticker": r.ticker, "security_name": r.security_name,
                         "nbr_shares": r.nbr_shares, "percent_tna": r.percent_tna})
    per = pd.DataFrame(per)
    add = pd.DataFrame(rows)
    add.to_parquet(CACHE / "pff_crsp_additions.parquet", index=False)
    per["year"] = pd.to_datetime(per.report_dt).dt.year
    out = {"source": "R2 crsp_q_mutualfunds.holdings, PFF portno(s) in " + str(PORTS.name),
           "report_dates": len(dates), "first": str(dates[0]), "last": str(dates[-1]),
           "median_gap_days_between_reports": float(per.gap_days.median()),
           "additions_per_year": per.groupby("year").added.sum().to_dict(),
           "removals_per_year": per.groupby("year").removed.sum().to_dict(),
           "holdings_range": [int(per.holdings.min()), int(per.holdings.max())],
           "additions_with_ticker": int(add.ticker.notna().sum()) if len(add) else 0}
    # days of ADV: map by ticker to Alpaca symbols, volume from the pre-2023 cache
    vol_p = CACHE / "volume_daily_2016_2022.parquet"
    if vol_p.exists() and len(add):
        v = pd.read_parquet(vol_p)
        cen = pd.read_csv(OUT / "census_2026-10-19.csv")
        def to_sym(t):
            if not isinstance(t, str) or not t:
                return None
            t = t.strip().upper()
            cands = [t, t.replace("-P", ".PR"), t.replace("PR", ".PR", 1) if ".PR" not in t else t]
            for c in cands:
                if c in set(cen.symbol):
                    return c
            return None
        add["symbol"] = add.ticker.map(to_sym)
        res = []
        for r in add.dropna(subset=["symbol"]).itertuples():
            b = v[v.symbol == r.symbol].sort_values("t")
            pre = b[b.t <= r.prev].tail(20)          # strictly before the earliest possible addition date
            flag = "pre_event"
            if len(pre) < 10:
                pre = b[b.t <= r.report_dt].head(20)
                flag = "listed_inside_month"
            if pre.empty or not r.nbr_shares:
                continue
            adv = float(pre.v.mean())
            res.append({"symbol": r.symbol, "report_dt": r.report_dt, "flag": flag, "pff_shares": r.nbr_shares,
                        "adv_shares": adv, "days_of_adv": r.nbr_shares / adv if adv else None,
                        "first_bar": b.t.min()})
        res = pd.DataFrame(res)
        res.to_parquet(CACHE / "pff_crsp_additions_adv.parquet", index=False)
        ok = res.dropna(subset=["days_of_adv"])
        out.update({"additions_mapped_to_alpaca": int(add.symbol.notna().sum()), "with_volume": int(len(ok)),
                    "days_of_adv_median": round(float(ok.days_of_adv.median()), 2) if len(ok) else None,
                    "days_of_adv_quartiles": [round(float(x), 2) for x in ok.days_of_adv.quantile([.25, .5, .75])]
                    if len(ok) else None,
                    "share_ge_1_day": round(float((ok.days_of_adv >= 1).mean()), 3) if len(ok) else None,
                    "by_flag": {k: {"n": int(len(g)), "median": round(float(g.days_of_adv.median()), 2)}
                                for k, g in ok.groupby("flag")},
                    "by_year": {int(k): {"n": int(len(g)), "median": round(float(g.days_of_adv.median()), 2)}
                                for k, g in ok.groupby(pd.to_datetime(ok.report_dt).dt.year)}})
    write_json(OUT / "cr15_pff_crsp_summary.json", out)
    print(json.dumps(out, indent=1, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("pull")
    sp.add_parser("additions")
    a = ap.parse_args(argv)
    {"pull": cmd_pull, "additions": cmd_additions}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
