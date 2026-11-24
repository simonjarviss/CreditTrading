"""Performance statistics from an official end-of-day equity series. Standard library only.

The definitions are the ones `ops/orient.py` PNL prints, so the site and orient agree to
the cent (dashboard/tests/test_metrics.py pins that on a recorded series):

  * daily return r_t = change_usd_t / equity_{t-1}  (Alpaca's own change, never a
    difference we compute: the change carries cash flows Alpaca knows about and we do not);
  * annualised volatility = sample standard deviation of r_t x sqrt(252);
  * cumulative P&L = last equity - first equity (the first row is the funded account);
  * drawdown is measured on equity from its running high-water mark.

The Sharpe ratio is mean(r) / sd(r) x sqrt(252), with no risk-free rate subtracted (the
paper accounts earn no interest on cash). The Sortino ratio is mean(r) / downside deviation x
sqrt(252), the downside deviation being sqrt(mean(min(r, 0)^2)) over every session (Sortino and
Price's definition, target 0). The correlation of two books is Pearson's on the daily returns of
the sessions both have. It is printed with its session count, because
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
        dd_dev = math.sqrt(sum(min(r, 0.0) ** 2 for r in rs) / len(rs))
        s["sortino"] = (mean / dd_dev) * math.sqrt(TRADING_DAYS) if dd_dev > 0 else None
    else:
        s["sortino"] = None
    return s


def return_points(rows: list) -> list:
    """[(date, cumulative return since the funded row, as a fraction)]: growth on one scale for
    books of different sizes."""
    rows = funded(rows)
    base = rows[0]["equity"]
    return [(r["date"], r["equity"] / base - 1.0) for r in rows]


def drawdown_points(rows: list) -> list:
    """[(date, drawdown from the running high-water mark, as a negative fraction)]."""
    return [(d, x) for d, x, _ in drawdowns(funded(rows))]


def pnl_points(rows: list) -> list:
    """[(date, the session's P&L in dollars)] for every session after the funded row."""
    rows = funded(rows)
    return [(r["date"], r["change_usd"]) for r in rows[1:]]


def correlation(a: list, b: list) -> tuple:
    """(Pearson correlation of two books' daily returns on their common sessions, n). The
    correlation is None below MIN_RETURNS_FOR_RATIOS common sessions or when either is constant."""
    ra, rb = dict(returns(funded(a))), dict(returns(funded(b)))
    common = sorted(set(ra) & set(rb))
    n = len(common)
    if n < MIN_RETURNS_FOR_RATIOS:
        return None, n
    xs, ys = [ra[d] for d in common], [rb[d] for d in common]
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None, n
    return sxy / math.sqrt(sxx * syy), n


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


# --------------------------------------------------------------- the portfolio --
# Team lead, 2026-11-24: "overall portfolio (shown as one line), can split into 3 lines (our sleeves)
# and analyze below (all things institutional investors would look at)". The portfolio is a
# composite of the books, each from its first traded session: the day's return is the sum of the
# active books' P&L over the sum of their equity at the previous close (asset-weighted, as a
# composite of accounts is measured), so an account's idle cash before it trades never dilutes it.

def trading_rows(rows: list, first_send) -> list:
    """A book's daily rows from the close before its first send (the base) on. None: never traded."""
    if first_send is None:
        return []
    rows = funded(rows)
    before = [r for r in rows if r["date"] < first_send]
    if not before:
        raise ValueError(f"no row before the first send {first_send}: the base equity is unknown")
    base = before[-1]
    return [dict(base, change_usd=None)] + [r for r in rows if r["date"] >= first_send]


def daily(rows: list) -> list:
    """[(date, return, P&L in dollars)] after the base row; a row without a change raises."""
    out = []
    for prev, cur in zip(rows, rows[1:]):
        if cur["change_usd"] is None:
            raise ValueError(f"{cur['date']}: a row after the base has no change_usd")
        out.append((cur["date"], cur["change_usd"] / prev["equity"], cur["change_usd"]))
    return out


def composite(books: dict) -> tuple:
    """books: {name: trading rows}. Returns ([(date, return, P&L, capital, active names)], dates left
    out). A session on which an active book has no row is left out whole, never summed over part
    of the portfolio; the count says how many were."""
    by = {b: {r["date"]: r for r in rows} for b, rows in books.items() if rows}
    order = {b: [r["date"] for r in rows] for b, rows in books.items() if rows}
    start = {b: d[0] for b, d in order.items()}                 # the base date of each book
    dates = sorted({d for b in order for d in order[b][1:]})
    out, left = [], 0
    for d in dates:
        active = [b for b in by if start[b] < d]
        if not all(d in by[b] for b in active):
            left += 1
            continue
        pnl = cap = 0.0
        for b in active:
            i = order[b].index(d)
            prev = by[b][order[b][i - 1]]
            pnl += by[b][d]["change_usd"]
            cap += prev["equity"]
        out.append((d, pnl / cap, pnl, cap, tuple(sorted(active))))
    return out, left


def _pct(xs: list, q: float) -> float:
    """The q-quantile by linear interpolation between order statistics (numpy's default)."""
    s = sorted(xs)
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def profile(dated: list) -> dict:
    """Every statistic of a daily return series, from [(date, return, P&L)].

    Returns and drawdowns compound the daily returns. Ratios, VaR, expected shortfall, skewness and
    kurtosis need MIN_RETURNS_FOR_RATIOS sessions and are None below it. VaR and expected shortfall
    are historical, one day, 95%: the 5th percentile of daily returns and the mean of the returns at
    or below it, both shown as losses."""
    n = len(dated)
    rs = [r for _, r, _ in dated]
    p = {"n": n, "first_date": dated[0][0] if dated else None, "last_date": dated[-1][0] if dated else None}
    idx, peak, dd_series, under, longest = 1.0, 1.0, [], 0, 0
    for d, r, _ in dated:
        idx *= 1.0 + r
        peak = max(peak, idx)
        dd = idx / peak - 1.0
        dd_series.append((d, dd))
        under = under + 1 if dd < 0 else 0
        longest = max(longest, under)
    p["cum_return"] = idx - 1.0
    p["pnl"] = sum(x for _, _, x in dated)
    p["max_drawdown"] = min((x for _, x in dd_series), default=0.0)
    p["max_drawdown_date"] = min(dd_series, key=lambda t: t[1])[0] if p["max_drawdown"] < 0 else None
    p["drawdown"] = dd_series[-1][1] if dd_series else 0.0
    p["longest_drawdown"] = longest
    p["sessions_in_drawdown"] = under
    p["last"] = dated[-1][1] if dated else None
    p["last5"] = (math.prod(1 + r for r in rs[-5:]) - 1.0) if n >= 5 else None
    if dated:
        m = dated[-1][0][:7]
        p["mtd"] = math.prod(1 + r for d, r, _ in dated if d[:7] == m) - 1.0
    else:
        p["mtd"] = None
    p["best"] = max(dated, key=lambda t: t[1])[:2] if dated else None
    p["worst"] = min(dated, key=lambda t: t[1])[:2] if dated else None
    ups, downs = [r for r in rs if r > 0], [r for r in rs if r < 0]
    p["hit_rate"] = len(ups) / (len(ups) + len(downs)) if ups or downs else None
    p["avg_gain"] = sum(ups) / len(ups) if ups else None
    p["avg_loss"] = sum(downs) / len(downs) if downs else None
    p["gain_loss_ratio"] = (p["avg_gain"] / -p["avg_loss"]) if ups and downs else None
    gp, gl = sum(x for _, _, x in dated if x > 0), -sum(x for _, _, x in dated if x < 0)
    p["profit_factor"] = gp / gl if gl > 0 else None
    for k in ("vol", "downside_dev", "sharpe", "sortino", "ann_return", "calmar", "var95", "es95", "skew", "kurt"):
        p[k] = None
    if n >= MIN_RETURNS_FOR_RATIOS:
        mean = sum(rs) / n
        sd = _sd(rs)
        dd_dev = math.sqrt(sum(min(r, 0.0) ** 2 for r in rs) / n)
        p["vol"] = sd * math.sqrt(TRADING_DAYS)
        p["downside_dev"] = dd_dev * math.sqrt(TRADING_DAYS)
        p["sharpe"] = mean / sd * math.sqrt(TRADING_DAYS) if sd > 0 else None
        p["sortino"] = mean / dd_dev * math.sqrt(TRADING_DAYS) if dd_dev > 0 else None
        p["ann_return"] = (1.0 + p["cum_return"]) ** (TRADING_DAYS / n) - 1.0
        p["calmar"] = p["ann_return"] / -p["max_drawdown"] if p["max_drawdown"] < 0 else None
        v = _pct(rs, 0.05)
        tail = [r for r in rs if r <= v]
        p["var95"], p["es95"] = -v, -sum(tail) / len(tail)
        if sd > 0:
            m3 = sum((r - mean) ** 3 for r in rs) / n
            m2 = sum((r - mean) ** 2 for r in rs) / n
            m4 = sum((r - mean) ** 4 for r in rs) / n
            p["skew"] = m3 / m2 ** 1.5
            p["kurt"] = m4 / m2 ** 2 - 3.0
    return p


def index_points(dated: list, base_date: str) -> list:
    """[(date, cumulative return)] from 0 at the base session, for a growth chart."""
    out, idx = [(base_date, 0.0)], 1.0
    for d, r, _ in dated:
        idx *= 1.0 + r
        out.append((d, idx - 1.0))
    return out


def drawdown_index(dated: list, base_date: str) -> list:
    """[(date, drawdown from the running peak of the compounded index)] from 0 at the base session."""
    out, idx, peak = [(base_date, 0.0)], 1.0, 1.0
    for d, r, _ in dated:
        idx *= 1.0 + r
        peak = max(peak, idx)
        out.append((d, idx / peak - 1.0))
    return out


def corr_dated(a: list, b: list) -> tuple:
    """(Pearson correlation of two dated return series on their common sessions, n); None below
    MIN_RETURNS_FOR_RATIOS common sessions or when either is constant there."""
    ra, rb = {d: r for d, r, _ in a}, {d: r for d, r, _ in b}
    common = sorted(set(ra) & set(rb))
    n = len(common)
    if n < MIN_RETURNS_FOR_RATIOS:
        return None, n
    xs, ys = [ra[d] for d in common], [rb[d] for d in common]
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx, syy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    return (None, n) if sxx == 0 or syy == 0 else (sxy / math.sqrt(sxx * syy), n)
