"""Performance statistics from an official end-of-day equity series. Standard library only.

The definitions are the ones `ops/orient.py` PNL prints, so the site and orient agree to
the cent (dashboard/tests/test_metrics.py pins that on a recorded series):

  * daily return r_t = change_usd_t / equity_{t-1}  (Alpaca's own change, never a
    difference we compute: the change carries cash flows Alpaca knows about and we do not);
  * annualised volatility = sample standard deviation of r_t x sqrt(252);
  * cumulative P&L = last equity - first equity (the first row is the funded account);
  * drawdown is measured on equity from its running high-water mark.

The Sharpe ratio is mean(r) / sd(r) x sqrt(252), with no risk-free rate subtracted (the
paper accounts earn no interest on cash). It is printed with its session count, because
on a record of a few dozen sessions its standard error is about as large as the ratio.

No fallbacks: a statistic that needs more rows than the series has is None, and the page
prints why. Nothing is filled.
"""
from __future__ import annotations

import math

TRADING_DAYS = 252
MIN_RETURNS_FOR_RATIOS = 20       # fewer than this, vol and Sharpe are not shown


def funded(rows: list) -> list:
    """The rows from the first funded one on (ops/orient.py official_pnl's rule: days before an
    account is funded carry equity 0 in Alpaca's history). Equity 0 after funding raises."""
    i = next((k for k, r in enumerate(rows) if r["equity"] > 0), None)
    if i is None:
        raise ValueError("no funded row: every official row has equity 0")
    out = rows[i:]
    bad = [r["date"] for r in out if r["equity"] <= 0]
    if bad:
        raise ValueError(f"equity is not positive after funding on {bad}")
    return out


def returns(rows: list) -> list:
    """[(date, r)] from official rows; the first row (funding) has no return."""
    out = []
    for prev, cur in zip(rows, rows[1:]):
        if cur["change_usd"] is None:
            raise ValueError(f"{cur['date']}: an official row after the first has no change_usd")
        if prev["equity"] <= 0:
            raise ValueError(f"{prev['date']}: equity {prev['equity']} is not positive")
        out.append((cur["date"], cur["change_usd"] / prev["equity"]))
    return out


def _sd(xs: list) -> float:
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def drawdowns(rows: list) -> list:
    """[(date, drawdown as a negative fraction, high-water mark)] on equity."""
    out, hwm = [], None
    for r in rows:
        hwm = r["equity"] if hwm is None else max(hwm, r["equity"])
        out.append((r["date"], r["equity"] / hwm - 1.0, hwm))
    return out


def summary(rows: list) -> dict:
    if not rows:
        raise ValueError("no official rows")
    rows = funded(rows)
    first, last = rows[0], rows[-1]
    rets = returns(rows)
    rs = [r for _, r in rets]
    dd = drawdowns(rows)
    hwm_row = max(rows, key=lambda r: (r["equity"], r["date"]))
    worst = min(dd, key=lambda x: x[1])
    s = {
        "first_date": first["date"], "last_date": last["date"],
        "start_equity": first["equity"], "equity": last["equity"],
        "last_change": last["change_usd"] if len(rows) > 1 else None,
        "cum_pnl": last["equity"] - first["equity"],
        "cum_return": last["equity"] / first["equity"] - 1.0,
        "n_returns": len(rs),
        "hwm": hwm_row["equity"], "hwm_date": hwm_row["date"],
        "drawdown": dd[-1][1], "max_drawdown": worst[1], "max_drawdown_date": worst[0],
        "best_day": max(rets, key=lambda x: x[1]) if rets else None,
        "worst_day": min(rets, key=lambda x: x[1]) if rets else None,
        "share_up": (sum(1 for r in rs if r > 0) / sum(1 for r in rs if r != 0)) if any(rs) else None,
        "vol": None, "sharpe": None, "ann_return": None,
    }
    if len(rs) >= MIN_RETURNS_FOR_RATIOS:
        sd = _sd(rs)
        mean = sum(rs) / len(rs)
        s["vol"] = sd * math.sqrt(TRADING_DAYS)
        s["ann_return"] = mean * TRADING_DAYS
        s["sharpe"] = (mean / sd) * math.sqrt(TRADING_DAYS) if sd > 0 else None
    return s


def monthly(rows: list) -> list:
    """[(YYYY-MM, P&L in dollars, return on the month's opening equity)] from official rows."""
    rows = funded(rows)
    out, by = [], {}
    for prev, cur in zip(rows, rows[1:]):
        m = cur["date"][:7]
        if m not in by:
            by[m] = {"open": prev["equity"], "pnl": 0.0}
            out.append(m)
        by[m]["pnl"] += cur["change_usd"]
    return [(m, by[m]["pnl"], by[m]["pnl"] / by[m]["open"]) for m in out]


def combined(series: dict) -> tuple:
    """Sum of several books' official rows over the sessions EVERY book has a row for.

    Returns (rows, sessions left out). A session one book lacks is left out of the combined
    line, never filled with that book's previous equity; the count says how many were."""
    if not series:
        return [], 0
    by_book = {b: {r["date"]: r for r in funded(rows)} for b, rows in series.items()}
    common = sorted(set.intersection(*(set(d) for d in by_book.values())))
    union = set().union(*(set(d) for d in by_book.values()))
    out = []
    for i, d in enumerate(common):
        eq = sum(by_book[b][d]["equity"] for b in by_book)
        if i == 0:
            ch = None
        else:
            prev = common[i - 1]
            ch = eq - sum(by_book[b][prev]["equity"] for b in by_book)
        out.append({"date": d, "equity": eq, "change_usd": ch})
    return out, len(union) - len(common)
