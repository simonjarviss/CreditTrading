"""Unit trusts winding up: buy the closed-end funds they were forced to sell, at the close of
the termination date, and hold three sessions.

THE IDEA (results/ideas/2026-11-16_uit_cef_flows.md). A unit investment trust that holds
closed-end funds must sell them by a Mandatory Termination Date printed in its prospectus
about two years earlier. On 24,623 fund-events to 2025-12-31 the funds fell 39.9bp against
other closed-end funds over the nine sessions to that date T, most of it on T-2, T-1 and T,
and gained 19.8bp on T+1, 11.2bp on T+2 and 2.8bp on T+3, then nothing.

THE RULE, WRITTEN 2026-11-18 BEFORE ANY 2026 PRICE WAS READ
-----------------------------------------------------------
The independent review could not break the result but set this condition: the entry at T's
close was chosen after the daily profile had been seen, so the rule must be fixed in writing
before the out-of-sample year is looked at, as `checks.py` scored it. This is that rule. The
research panel ends 2025-12-31. Nothing in this module, its fetcher or its builder had read a
closed-end fund's 2026 price when this was written; the first prices this book reads are the
ones its own nightly fetch brings, from its start date on.

  Calendar   shadow/universes/uit_terminations_v1.csv: every closed-end trust of First Trust
             and Guggenheim whose prospectus (form 487) was filed from 2023-07-01, with the
             termination date read from the filing's text and the closed-end funds it held at
             deposit. A row whose date cannot be read is refused, naming the trust. A
             prospectus must be more than 30 days older than its date (asserted, as the card
             asserts it).
  Event      (fund, T). T is the last exchange session ON OR BEFORE the Mandatory Termination
             Date: the trustee sells "no later than" the date, so a date on a weekend or a
             holiday means the last session before it. This is what the card assumed
             (explore.py: "last session ON OR BEFORE T") and it is kept. Trusts that hold the
             same fund and share a T are one event; `n_series` is how many.
  Eligible   the card's floors, read where the card read them, 10 sessions before T (before
             the selling starts, so the selling cannot change who qualifies): a close on that
             session of $2 or more and a 21-session average dollar volume of $100,000 or more
             (at least 10 sessions of data).
  Decision   after the close of T-1. T has been public for about two years, so this is the
             desk's ordinary order: decide after one close, fill at the next.
  Entry      the close of T.
  Exit       the close of T+3. The book earns the sessions T+1, T+2 and T+3 and no other.
  Side       long only, against nothing. This is the primary line: the equal-weighted fund
             market the research subtracted cannot be bought. (Long-only Sharpe in the
             research 1.49, hedged 1.90; per event T+1..T+3 +33bp.)
  Weights    each night, every eligible event fund inside its window gets weight in
             proportion to its `n_series` (summed if it is in two windows), scaled so the
             weights add to 1: exactly `checks.py`'s book. Then no fund may exceed CAP = 10%
             of the book; what the cap removes stays in cash and is NOT handed to the other
             funds.
             WHY 10%, from the card's own numbers. The research book held 41 funds on an
             active day and a trust holds 26 at the median, so an ordinary weight is 2.4% to
             3.8%, and 7.7% for a fund that two trusts of 26 sell on one day (`n_series` is 1
             on 23,762 of 24,623 events). A 10% cap therefore does not touch the book the
             research scored: it binds only when fewer than ten funds are held, which is when
             an uncapped book would put a tenth or more of itself into one thin fund. The
             review found the result falls when single names are capped tightly, which is why
             the cap is set above every ordinary weight and not at the usual 2% or 5%.
  Second     `big_sale`: the same rule on events where the trusts' estimated sale is 5% or
  line       more of the fund's dollar volume over the nine sessions T-18..T-10. It is a named
             variant with its own book file, not a replacement. Size is the review's
             point-in-time one: units sold less units redeemed in the registrant's 24F-2NT
             notices FILED more than 30 days before T (shadow/universes/uit_notices_v1.csv),
             split equally between the trusts of one filing, times the fund's percentage at
             deposit. A trust with no such notice has no size; an event none of whose trusts
             has one is left out of this line (in the research: 15,273 of 24,341 sized events
             passed, +43.4bp over T+1..T+3 against +15.8bp for the rest).

WHICH DECISIONS HOLD A FUND. The engine fills a decision at the next close and the book then
earns the session after that: a weight decided on session D earns session D+2
(shadow/engine.py). To earn T+1, T+2 and T+3 the fund must be in the decisions of T-1, T and
T+1. So the decision on D holds the events with
    T in { the session after D, D, the session before D }.
The decision on T+2 no longer holds it and fills at T+3's close, which is the exit.

NO LOOKAHEAD. The calendar is a file of facts filed years before they are used; the function
asserts each prospectus is more than 30 days older than its T, and each notice used for size
more than 30 days older. Prices come from the engine, which has already removed every row
dated after the decision date; eligibility reads the session T-10, which is at least nine
sessions before any decision that uses it (asserted).

WHAT IS DIFFERENT FROM `checks.py`, AND WHY. Its book dropped a fund on any earning session
when the fund had failed the floors the session before; that is one day later than the
decision here could know. This book reads the floors once, at T-10, as the per-event figures
did. And a fund must have a close ON the decision date to be bought or kept.

THE AWKWARD DAYS
  Half day       T on an early-close day (the day after Thanksgiving, Christmas Eve): the fill
                 is that day's close, at 13:00. The decision was written the evening before,
                 so it is on time. Nothing changes.
  T not a        the date falls on a weekend or holiday: T is the last session before it (see
  session        Event). The decision is then made one session earlier still.
  Unscheduled    the exchange closes on T without notice. The calendar here is rule-based
  closure        (ops/schedule/nyse_calendar.py) and does not know. The decision made at T-1
                 fills at the next close the exchange does print, which is a day late; the
                 research says a day late keeps about 13bp of 33bp. It is left as it falls.
  Halted fund    a fund with no close on the decision date is not bought, and if held it is
                 dropped by that decision. If it then prints no closing auction the engine
                 scores the session UNMEASURED and names it; no other price is used.
  No price       a fund Yahoo returns nothing for (renamed, merged or liquidated since the
                 prospectus) cannot be judged and is not held. The fetcher prints its name.

Every figure this book produces is SIMULATED: decisions on live data, filled at the next
official close by assumption. The review's second condition stands: the fill at T's own close
is the whole trade, and a paper account that fills near the quote minutes earlier is a
different test, to be read separately.
"""
from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path

import pandas as pd

from ops.schedule.nyse_calendar import is_trading_day, next_trading_day, previous_trading_day

UNIVERSES = Path(__file__).resolve().parents[1] / "universes"
CALENDAR = UNIVERSES / "uit_terminations_v1.csv"
NOTICES = UNIVERSES / "uit_notices_v1.csv"
PX = "px"
MIN_PRICE, MIN_ADV, ADV_WINDOW, MIN_ADV_DAYS = 2.0, 100_000.0, 21, 10     # the card's floors
ELIGIBLE_AT = 10          # sessions before T
HOLD_SESSIONS = 3         # earn T+1..T+3
CAP = 0.10                # per fund; the remainder is cash (docstring: WHY 10%)
MIN_NOTICE_DAYS = 30      # a prospectus, and a notice used for size, must be older than this at T
SALE_FROM, SALE_TO = 18, 10                                                # dollar volume over T-18..T-10
MIN_SALE_SHARE = 0.05
_SYMBOL = re.compile(r"[A-Z]{1,5}(?:[./][A-Z])?")


class CalendarError(ValueError):
    """A row of the committed calendar that cannot be used, naming the trust and the filing."""


def _date(row: dict, key: str, who: str) -> dt.date:
    raw = (row.get(key) or "").strip()
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        raise CalendarError(f"{who}: {key} {raw!r} is not a date (YYYY-MM-DD); the row is refused, not guessed at") from None


def read_calendar(rows) -> list[dict]:
    """Validate calendar rows (dicts of strings, as csv gives them). Raises CalendarError on
    the first row that cannot be used: a calendar with one unreadable date is not a calendar
    with one fewer trust, it is a calendar somebody must look at."""
    out = []
    for r in rows:
        who = f"{r.get('series', '?')} / {r.get('trust', '?')} (accession {r.get('accession', '?')})"
        filed, term = _date(r, "filed", who), _date(r, "termination_date", who)
        sym = (r.get("symbol") or "").strip()
        if not _SYMBOL.fullmatch(sym):
            raise CalendarError(f"{who}: symbol {sym!r} is not a ticker")
        try:
            pct, k = float(r["pct"]), int(r["trusts_in_filing"])
        except (KeyError, TypeError, ValueError):
            raise CalendarError(f"{who}: pct or trusts_in_filing is missing or not a number") from None
        if not (0 < pct <= 100) or k < 1:
            raise CalendarError(f"{who}: pct {pct} or trusts_in_filing {k} is out of range")
        if not r.get("accession") or not r.get("cik"):
            raise CalendarError(f"{who}: no accession number or CIK; a row must name its filing")
        out.append({"trust_key": (r["accession"], r.get("trust", "")), "cik": str(r["cik"]), "filed": filed,
                    "termination": term, "symbol": sym, "pct": pct, "trusts_in_filing": k, "who": who})
    return out


def read_notices(rows) -> list[dict]:
    out = []
    for r in rows:
        who = f"notice {r.get('accession', '?')} of {r.get('series', '?')}"
        try:
            sold, red = float(r["sold_usd"]), float(r["redeemed_usd"])
        except (KeyError, TypeError, ValueError):
            raise CalendarError(f"{who}: sold_usd or redeemed_usd is missing or not a number") from None
        out.append({"cik": str(r["cik"]), "filed": _date(r, "filed", who),
                    "fiscal_year_end": _date(r, "fiscal_year_end", who), "sold": sold, "redeemed": red})
    return out


def _csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def termination_session(d: dt.date) -> dt.date:
    """T: the last session on or before the Mandatory Termination Date."""
    return d if is_trading_day(d) else previous_trading_day(d)


def sessions_before(d: dt.date, n: int) -> dt.date:
    for _ in range(n):
        d = previous_trading_day(d)
    return d


def window(asof: dt.date) -> tuple:
    """The termination sessions a decision on `asof` holds: T-1, T and T+1 are `asof`."""
    return (previous_trading_day(asof), asof, next_trading_day(asof))


def events(calendar: list[dict], sessions: tuple) -> dict:
    """{(symbol, T): [calendar rows]} for T in `sessions`, one row per trust."""
    out: dict = {}
    for r in calendar:
        t = termination_session(r["termination"])
        if t not in sessions:
            continue
        # ALIGNMENT: the prospectus was public more than 30 days before T (the card's assertion)
        if (t - r["filed"]).days <= MIN_NOTICE_DAYS:
            raise CalendarError(f"{r['who']}: filed {r['filed']}, within {MIN_NOTICE_DAYS} days of its termination session {t}")
        rows = out.setdefault((r["symbol"], t), [])
        if all(x["trust_key"] != r["trust_key"] for x in rows):
            rows.append(r)
    return out


def trust_size(cik: str, k: int, t: dt.date, notices: list[dict]) -> float | None:
    """Units sold less units redeemed, in dollars, from notices filed more than 30 days before
    T, split equally between the `k` trusts of the filing; None when there is no such notice.
    Two notices for one fiscal year (an amendment): the later one filed in time is used."""
    last: dict = {}
    for n in sorted((n for n in notices if n["cik"] == cik and (t - n["filed"]).days > MIN_NOTICE_DAYS), key=lambda n: n["filed"]):
        last[n["fiscal_year_end"]] = n
    if not last:
        return None
    assert all(n["filed"] < t for n in last.values())
    return max(sum(n["sold"] - n["redeemed"] for n in last.values()), 0.0) / k


def _targets(asof: dt.date, px: pd.DataFrame, calendar: list[dict], notices: list[dict] | None) -> pd.Series:
    if not is_trading_day(asof):
        raise ValueError(f"{asof} is not a trading day; the engine decides on sessions only")
    px = px.copy()
    px["date"] = pd.to_datetime(px["date"]).dt.date
    px = px[px["date"] <= asof].dropna(subset=["close"]).sort_values("date")
    by_sym = {s: g for s, g in px.groupby("symbol")}
    raw: dict = {}
    for (sym, t), rows in sorted(events(calendar, window(asof)).items()):
        g = by_sym.get(sym)
        if g is None or g["date"].iloc[-1] != asof:
            continue                                        # no close today: not bought, not kept
        ref = sessions_before(t, ELIGIBLE_AT)
        assert ref < asof, "eligibility must be read before the decision date"
        upto = g[g["date"] <= ref]
        if upto.empty or upto["date"].iloc[-1] != ref:
            continue                                        # no close on T-10: the floors cannot be read
        tail = upto.tail(ADV_WINDOW)
        dv = (tail["close"] * tail["volume"]).dropna()
        if not (len(dv) >= MIN_ADV_DAYS and tail["close"].iloc[-1] >= MIN_PRICE and dv.mean() >= MIN_ADV):
            continue
        if notices is not None:
            sizes = [(trust_size(r["cik"], r["trusts_in_filing"], t, notices), r["pct"]) for r in rows]
            sized = [s * pct / 100.0 for s, pct in sizes if s is not None]
            lo, hi = sessions_before(t, SALE_FROM), sessions_before(t, SALE_TO)
            nine = g[(g["date"] >= lo) & (g["date"] <= hi)]
            vol = float((nine["close"] * nine["volume"]).sum())
            if not sized or vol <= 0 or sum(sized) / vol < MIN_SALE_SHARE:
                continue
        raw[sym] = raw.get(sym, 0.0) + float(len(rows))     # n_series; summed if the fund is in two windows
    if not raw:
        return pd.Series(dtype=float)
    total = sum(raw.values())
    return pd.Series({s: min(v / total, CAP) for s, v in sorted(raw.items())})


def all_events(asof: dt.date, panels: dict) -> pd.Series:
    """The primary line: every eligible event, long only."""
    return _targets(asof, panels[PX], read_calendar(_csv(CALENDAR)), None)


def big_sale(asof: dt.date, panels: dict) -> pd.Series:
    """The second line: events whose estimated sale is 5% or more of nine sessions' volume."""
    return _targets(asof, panels[PX], read_calendar(_csv(CALENDAR)), read_notices(_csv(NOTICES)))
