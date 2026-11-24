"""A synthetic VM state directory in the runners' real file formats, for the exporter's tests.

Every number is invented. The FILE SHAPES are copied from one real night (2026-11-20 core and
C4 records, the events book's verify.json fields from quantt/sleeves/run.py, the shadow
SCOREBOARD.md table), so a change in a runner's record format shows up here as a failing test,
not as a blank page.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

FILE_TIME = 1795473600          # 2026-11-23T22:40:00Z

EOD_HEAD = "date,equity,change_usd,read_at_utc\n"


def eod(rows):
    """rows: [(date, equity, change or None)]"""
    return EOD_HEAD + "".join(f"{d},{e},{'' if c is None else c},2026-11-21T08:40:04+00:00\n" for d, e, c in rows)


CEF_EOD = [("2026-11-16", 100000.0, None), ("2026-11-17", 100250.0, 250.0), ("2026-11-18", 99900.0, -350.0),
           ("2026-11-19", 100100.0, 200.0), ("2026-11-20", 100050.0, -50.0)]
C4_EOD = [("2026-11-17", 0.0, None), ("2026-11-18", 100000.0, 100000.0), ("2026-11-19", 100400.0, 400.0),
          ("2026-11-20", 100300.0, -100.0)]

RECONCILE = {
    "auction_condition": "M",
    "auction_prints_d": {"gaps": {}, "prices": {"AAA": 10.0, "BBB": 20.0}},
    "fills": [{"activity_type": "FILL", "id": "20261120155202983::2baa43f0-a428-40ab-83f6-73e3a3f40e19",
               "order_id": "b3a7e512-14a7-41cd-9dc8-1e3c40b85b9e", "price": "10.0", "qty": "5", "side": "buy",
               "symbol": "AAA"}],
    "official_eod": {"pending": "no point yet"},
    "orders": [{"client_order_id": "cef-20261120-AAA-1", "events": ["submit"], "filled_avg_price": "10.0",
                "filled_qty": "5", "order_id": "b3a7e512-14a7-41cd-9dc8-1e3c40b85b9e", "qty": 5, "side": "buy",
                "status": "filled", "symbol": "AAA"}],
    "positions_after": {"AAA": 100, "BBB": -50},
    "problems": [],
    "read_at": "2026-11-20T17:30:00.942422-05:00",
    "snapshot": {"change_usd": -40.0, "clock_read_at": "2026-11-20T17:30:00-05:00", "equity": 100060.0,
                 "last_equity": 100100.0},
    "verdict": "2026-11-20 PASS cef traded 1 order(s), 1 filled; official PENDING",
}

RISK = {"book": "cef", "asof": "2026-11-20", "generated_at": "2026-11-21T05:45:00-05:00",
        "plan": "/home/quantt/quantt_state/cef/2026-11-23/plan.json", "severity": "WATCH",
        "blocks": {"exposure": {"data": {"gross": 1.5, "net": 0.05, "cap": 1.8,
                                         "concentration": {"largest": {"symbol": "AAA", "share": 0.3, "side": "long"},
                                                           "top3_share": 0.7,
                                                           "group_share": {"muni": 0.4, "hy": 0.3}}}},
                   "drawdown": {"data": {"levels": {"halve": 0.12, "kill": 0.18}}}}}

TCA = ("date,book,n_orders,n_full,shares_ordered,shares_filled,fill_rate_shares,slip_bp_buy,slip_bp_sell,"
       "slip_bp_all,slip_unmeasured,residual_gross_usd,residual_net_usd,residual_names,basis\n"
       "2026-11-20,cef,1,1,5,5,1.0000,-1.00,,-1.00,,0.00,0.00,,x\n")

VERIFY = {"session_date": "2026-11-23", "book": "events", "ok": True, "reason": "1 symbol(s) filled; ledger booked",
          "read_at": "2026-11-23T17:35:04-05:00", "orders": [
              {"client_order_id": "events-20261123-CCC-1", "symbol": "CCC", "side": "sell", "qty": 7,
               "events": ["submit"], "status": "filled", "filled_qty": "7", "order_id": "u"}],
          "fills_by_symbol": {"CCC": {"shares": -7, "avg_price": 30.5}},
          "positions_after": {"CCC": -7, "DDD": 0}, "marks": {"CCC": 30.0},
          "equity": {"equity": 100010.0, "last_equity": 100000.0, "change_usd": 10.0, "kind": "snapshot at verify"},
          "problems": [], "fails": [], "notes": [], "ledger_applied": True}

SLEEVES = ("date,slug,shares_value,cash,pnl,day_change,n_names,equity_change,residual,capital_usd\n"
           "2026-11-23,cef_exdate_after,-210.0,213.5,3.5,3.5,1,,,33000.0000\n"
           "2026-11-23,uit_termination,0,0,0,0,0,,,34750.0000\n"
           "2026-11-23,_book,0,0,3.5,3.5,1,10.0,6.5,\n")

SCOREBOARD = """# Shadow scoreboard — 2026-11-20

**Every figure is SIMULATED**.

| book | started | last | scored | flat | unmeasured | late decisions | P&L price | P&L total return | Sharpe | max drawdown | mean gross | turnover / yr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| month_end_ief | 2026-11-10 | 2026-11-20 | 0 | 8 | 0 | 0 | none | none | needs 20 (has 0) | none | none | none |
| units_exdate_after | 2026-11-11 | 2026-11-20 | 5 | 2 | 0 | 0 | +17,393 | +20,674 | needs 20 (has 5) | -1.97% | 1.00 | 156.67 |

## Correlation of daily P&L (price line)

| a | b |
|---|---|
| x | y |
"""


def make_state(root: Path) -> tuple:
    """(state root, scoreboard path) holding all three books and the shadow scoreboard."""
    st = root / "quantt_state"
    for b, rows in (("cef", CEF_EOD), ("c4", C4_EOD)):
        d = st / b
        (d / "2026-11-20").mkdir(parents=True)
        (d / "2026-11-24").mkdir()                       # tomorrow's plan directory: no reconcile yet
        first = "2026-11-17" if b == "cef" else "2026-11-19"   # each book's first send (C4 is funded 2026-11-18)
        (d / first).mkdir()
        (d / first / "STARTED").write_text("{}")
        (d / "2026-11-24" / "plan.json").write_text("{}")
        (d / "eod_equity.csv").write_text(eod(rows))
        rec = json.loads(json.dumps(RECONCILE))
        rec["verdict"] = rec["verdict"].replace(" cef ", f" {b} ")
        (d / "2026-11-20" / "reconcile.json").write_text(json.dumps(rec))
        (d / "reports" / "risk").mkdir(parents=True)
        (d / "reports" / "risk" / "2026-11-19.json").write_text(json.dumps({**RISK, "severity": "OK"}))
        (d / "reports" / "risk" / "2026-11-20.json").write_text(json.dumps(RISK))
        (d / "tca.csv").write_text(TCA)
    ev = st / "events"
    # 2026-11-20 is a dry run (a verify.json, no STARTED), 2026-11-23 the first send, as on the VM.
    (ev / "2026-11-20").mkdir(parents=True)
    (ev / "2026-11-20" / "verify.json").write_text(json.dumps(
        {**VERIFY, "session_date": "2026-11-20", "reason": "no trade: send ended DRY", "orders": [],
         "equity": {"equity": 100000.0, "last_equity": 100000.0, "change_usd": 0.0, "kind": "snapshot at verify"},
         "fills_by_symbol": {}, "positions_after": {}, "marks": {}}))
    (ev / "2026-11-23").mkdir(parents=True)
    (ev / "2026-11-23" / "verify.json").write_text(json.dumps(VERIFY))
    (ev / "2026-11-23" / "STARTED").write_text("{}")
    (ev / "sleeve_scores.csv").write_text(SLEEVES)
    sb = root / "SCOREBOARD.md"
    sb.write_text(SCOREBOARD)
    for p in [sb, *st.rglob("*")]:            # fixed file times, so a file-time read_at is reproducible
        os.utime(p, (FILE_TIME, FILE_TIME))
    return st, sb
