"""Reverse splits: can the names the test would have shorted be borrowed at Alpaca, read today?

    QUANTT_ENV_FILE=<env> python3 results/ideas/reverse_splits/borrow_now.py

WHY: the October catalogue closed card G1 on "54 of 432 active 2025 reverse-split symbols are
shortable". That count took every reverse split of the year, whatever its size, and read the
flag months after most of them. The test in explore.py shorts only names with price >= $2 and
21-session dollar volume >= $500,000 at the close of the ex-date, and holds them for the next
twenty sessions. The question that decides the idea is narrower: of the reverse splits whose
ex-date is recent enough that the book would hold them NOW, and that pass those two floors,
how many does Alpaca mark shortable and easy to borrow today?

WHAT IT READS (read-only; the core account's key, as the shadow books do):
  /v1/corporate-actions types=reverse_split, ex-dates in the last --days calendar days;
  /v2/assets/{symbol} for each: status, shortable, easy_to_borrow;
  /v2/stocks/bars 1Day raw for the 21 sessions up to the ex-date: close and dollar volume
  (close x volume, the bar's own; an approximation of CRSP's dollar volume).
`borrow_status` and `shortable` are true on the day they are read only. The answer for an
event whose ex-date is weeks old is the flag today, not the flag on its ex-date: stated in
the output by age bucket.
Writes borrow_now.json beside this file (symbols and flags are public facts, not licensed rows).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
HERE = Path(__file__).resolve().parent
MIN_PRICE, MIN_ADV = 2.0, 500_000.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    a = ap.parse_args(argv)
    from quantt.broker.alpaca import AlpacaClient, AssetNotFound, _SYMBOL_RE
    c = AlpacaClient.from_environment("cef")
    today = dt.date.today()
    first = today - dt.timedelta(days=a.days)
    rows, token = [], None
    for _ in range(50):
        p = {"types": "reverse_split", "start": first.isoformat(), "end": today.isoformat(), "limit": 1000}
        if token:
            p["page_token"] = token
        body = c._get(c._data, "/v1/corporate-actions", p)
        rows += (body["corporate_actions"] or {}).get("reverse_splits") or []
        token = body.get("next_page_token")
        if not token:
            break
    else:
        raise RuntimeError("more than 50 pages of reverse splits")
    out = []
    for r in rows:
        sym, ex = r["symbol"], dt.date.fromisoformat(r["ex_date"])
        if ex > today:
            continue
        rec = {"symbol": sym, "ex_date": ex.isoformat(), "old_rate": r["old_rate"], "new_rate": r["new_rate"],
               "listed": False, "shortable": None, "easy_to_borrow": None, "close_x": None, "adv21": None}
        if _SYMBOL_RE.match(sym):
            try:
                asset = c.asset(sym)
                rec.update(listed=asset["status"] == "active" and asset["tradable"], shortable=asset["shortable"],
                           easy_to_borrow=asset.get("easy_to_borrow"), exchange=asset["exchange"])
            except AssetNotFound:
                pass
            # Bars on the raw basis: before the ex-date they are on the OLD ratio, so dollar
            # volume (close x volume, both raw) is comparable across the split and the close
            # used for the price floor is the ex-date's own.
            b = c._get(c._data, "/v2/stocks/bars", {"symbols": sym, "timeframe": "1Day", "adjustment": "raw", "feed": "sip",
                                                   "start": (ex - dt.timedelta(days=45)).isoformat(),
                                                   "end": ex.isoformat(), "limit": 1000})
            bars = (b.get("bars") or {}).get(sym) or []
            bars = [x for x in bars if x["t"][:10] <= ex.isoformat()][-21:]
            if bars and bars[-1]["t"][:10] == ex.isoformat() and len(bars) >= 10:
                rec["close_x"] = bars[-1]["c"]
                rec["adv21"] = sum(x["c"] * x["v"] for x in bars) / len(bars)
        rec["eligible"] = bool(rec["close_x"] is not None and rec["close_x"] >= MIN_PRICE and rec["adv21"] >= MIN_ADV)
        rec["age_days"] = (today - ex).days
        out.append(rec)

    def tally(sel):
        s = [r for r in out if sel(r)]
        return {"events": len(s), "listed_today": sum(r["listed"] for r in s),
                "shortable_today": sum(bool(r["listed"] and r["shortable"]) for r in s),
                "easy_to_borrow_today": sum(bool(r["listed"] and r["shortable"] and r["easy_to_borrow"]) for r in s)}

    summary = {"read_on": today.isoformat(), "window_days": a.days, "rows_in_feed": len(rows),
               "no_ex_day_bar_or_under_10_bars": sum(r["close_x"] is None for r in out)}
    for label, lo, hi in (("ex-date 0-30 days ago (held now)", 0, 30), ("31-90 days ago", 31, 90), ("91+ days ago", 91, 10_000)):
        for name, sel in (("all", lambda r: True), ("eligible at ex-date ($2, $500k)", lambda r: r["eligible"]),
                          ("eligible and $5M a day", lambda r: r["eligible"] and r["adv21"] >= 5e6)):
            summary[f"{label} | {name}"] = tally(lambda r, lo=lo, hi=hi, sel=sel: lo <= r["age_days"] <= hi and sel(r))
    print(json.dumps(summary, indent=1))
    (HERE / "borrow_now.json").write_text(json.dumps({"summary": summary, "events": out}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
