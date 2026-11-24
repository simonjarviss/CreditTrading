"""THE single current price cross-section (2026-10-19) used ONLY to count today's C6 opportunity set.

    export QUANTT_ENV_FILE=<absolute path to the env file>       # never printed
    python3 scripts/events/ssx/ssx_lcred_snapshot.py take        # once; refuses if today's file exists
    python3 scripts/events/ssx/ssx_lcred_snapshot.py count       # offline: the C6 upper bound

WHY
---
Idea C6 (short a preferred trading above its call price with a call date
inside 12 months: negative yield-to-worst, the loser yield-screening retail)
has a zero-trial kill gate that needs today's prices: fewer than 10 shortable
candidates today kills it. The brief allows ONE current quote snapshot for
exactly this count. It is not a series, no return is formed from it, and the
file is written under the licensed-rows cache.

THE ARITHMETIC THAT CAN KILL C6 WITHOUT CALL DATES
--------------------------------------------------
A $25-par preferred is redeemable at $25 (plus declared, unpaid dividends) on
or after its first call date. So the C6 set is a SUBSET of {shortable today}
AND {last trade > $25 par}. If that superset is already below the kill number,
C6 dies without reading a single prospectus. Par is read from the name where
the name gives it (a depositary fraction of a stated liquidation preference);
otherwise $25 is the listed-preferred convention and the row is flagged
`par_from_name=False` so a reader can check it. Rows whose name states a par
other than $25 are reported separately, never forced to $25.
ZERO TRIALS.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx.ssx_lcred_common import CACHE, OUT, alpaca, alpaca_snapshot_prices, write_json

CENSUS = OUT / "census_2026-10-19.csv"
SNAP = CACHE / "snapshot_2026-10-19.csv"
FRAC_RE = re.compile(r"1/\s?([\d,]+)\s*(th|st)?", re.I)
LIQ_RE = re.compile(r"liquidation preference \$?([\d,]+(\.\d+)?)", re.I)
PAR_RE = re.compile(r"\$(25|50|100|1,000|1000)(\.00)? (par|liquidation)", re.I)


def par_from_name(name: str):
    m = LIQ_RE.search(name)
    f = FRAC_RE.search(name)
    if m and f:
        return float(m.group(1).replace(",", "")) / float(f.group(1).replace(",", ""))
    if m and not f:
        return float(m.group(1).replace(",", ""))
    p = PAR_RE.search(name)
    if p:
        return float(p.group(1).replace(",", ""))
    return None


def cmd_take(args) -> None:
    if SNAP.exists():
        raise RuntimeError(f"{SNAP} exists: the single permitted snapshot was already taken")
    cen = pd.read_csv(CENSUS)
    syms = sorted(cen[cen.tradable & (cen.exchange != "OTC")].symbol)
    c = alpaca()
    taken = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    # the last completed session strictly before today (Alpaca's own calendar)
    cal = c.calendar(dt.date.today() - dt.timedelta(days=10), dt.date.today() - dt.timedelta(days=1))
    session = max(r["date"] for r in cal)
    s = alpaca_snapshot_prices(c, syms, session)
    s["taken_utc"] = taken
    CACHE.mkdir(parents=True, exist_ok=True)
    s.to_csv(SNAP, index=False)
    print(f"snapshot of {len(s)} symbols taken at {taken}")


def cmd_count(args) -> None:
    cen = pd.read_csv(CENSUS)
    s = pd.read_csv(SNAP)
    d = cen.merge(s, on="symbol", how="left")
    d["par_name"] = d.name.map(par_from_name)
    d["par_used"] = d.par_name.fillna(25.0)
    d["par_from_name"] = d.par_name.notna()
    d["above_par"] = d.close > d.par_used
    sh = d[d.shortable]
    out = {"snapshot_taken_utc": str(s.taken_utc.iloc[0]), "session": str(s.session.iloc[0]),
           "symbols_in_snapshot": int(s.close.notna().sum()),
           "label": ("single cross-section: Alpaca SIP daily close of the last completed session; used only to "
                     "count today's C6 set; no return formed. The real-time SIP snapshot was refused (HTTP 403)"),
           "shortable_today": int(len(sh)),
           "shortable_with_close": int(sh.close.notna().sum()),
           "shortable_above_par": int(sh.above_par.sum()),
           "shortable_above_par_symbols": sh[sh.above_par][["symbol", "close", "par_used", "par_from_name",
                                                             "kind"]].values.tolist(),
           "shortable_nonstd_par_in_name": sh[sh.par_from_name & (sh.par_name != 25)][["symbol", "par_name"]].values.tolist(),
           "all_tradable_above_par": int(d[d.tradable].above_par.sum()),
           "all_tradable_with_price": int(d[d.tradable].close.notna().sum())}
    d[d.shortable].to_csv(OUT / "c6_shortable_snapshot_view.csv", index=False)
    write_json(OUT / "c6_summary.json", out)
    print(json.dumps(out, indent=1, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("take")
    sp.add_parser("count")
    a = ap.parse_args(argv)
    {"take": cmd_take, "count": cmd_count}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
