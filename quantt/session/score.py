"""Score one session, gross: Alpaca's official end-of-day figure, a snapshot, and the auction mark.

WHY MORE THAN ONE NUMBER
------------------------
The paper account is the competition's official record, and it is scored on
gross P&L (team lead, D19/D20, 2026-09-15). But Alpaca paper does NOT run a
closing auction: staff say a paper MOC order is filled like a plain market
order at the current quote [S: forum staff posts 2021-05-18 and 2023-01-24;
`results/ops/ALPACA_API_FACTS_2026-09-28.md` §4]. So the account's P&L is a
number about Alpaca's simulator, and a real-money version of this book would
have been filled in the auction instead. The team lead's decision
(2026-09-28, `docs/RUNNER.md` "Scoring") is to carry both, side by side,
labelled, and never blended into one column.

WHICH ALPACA NUMBER IS OFFICIAL (team lead, 2026-10-19)
-------------------------------------------------------
Until 2026-10-19, (a) below was called "the official number". It is not. The
17:30 ET read is marked after the close. On the four days compared on
2026-10-19 (09-29, 10-05, 10-07, 10-16) it disagreed with Alpaca's own
end-of-day portfolio history on every one of them, by tens to hundreds of
dollars. On the same days the history agreed with (b), the auction-marked
score, to within fifty cents [V: main session, 2026-10-19, a live
portfolio-history read against verify.log and scores.csv; relayed, not re-read
here]. The team lead's ruling (`docs/SYSTEM.md` §5, 2026-10-19):

  (o) `OfficialPnL` -- Alpaca's end-of-day portfolio history
      (GET /v2/account/portfolio/history, timeframe 1D), EOD(D) - EOD(previous
      session). THE official daily P&L of record. Computed by
      `official_change` below from points the client has already checked
      (`AlpacaClient.eod_equity_history`). When D's point is missing, or its
      stamp is still in the future at the read, the figure is PENDING with the
      reason, and NOTHING stands in for it -- not the snapshot, not the
      auction mark. The series of record is `<state>/eod_equity.csv`, which
      the collector keeps (`quantt/collect/collect.py`, step `eod_equity`).
  (a) `alpaca_equity_change` -- the account's `equity - last_equity` as Alpaca
      reports it at the moment of the read: a SNAPSHOT, kept and labelled
      "snapshot HH:MM ET" on the verify line. It is whatever Alpaca marks the
      positions at when it is read (for a 17:30 ET read that may include
      after-hours quotes [U]). Its column in scores.csv keeps its name,
      `alpaca_equity_change_usd`, because other code reads that file by
      column name and its header is fixed.
  (b) `auction_pnl` -- every position held into D's close marked from the
      previous session's official closing-auction print to D's, plus every fill
      on D marked from its fill price to D's auction print:

          sum_held  q0 * (A_D - A_prev)  +  sum_fills  signed_qty * (A_D - fill_price)

      `q0` is the signed share count held at the START of D (before D's fills);
      `signed_qty` is +qty for a buy, -qty for a sell. The second term is
      exactly "the fill was not at the auction price": it is zero when a fill
      prints at A_D. Together they are the P&L of the end-of-D book at auction
      marks, which is what a live account's P&L would have been had every
      fill been an auction fill.

All three are GROSS. Alpaca paper charges no borrow and pays no dividends
[V: docs.alpaca.markets/us/docs/paper-trading, fetched 2026-09-28], and (b)
adds none either. The same page says paper does not account for regulatory
fees, but the account's own record disagrees: the core paper account carries
FEE activity rows (61 CAT fee rows, $12.01, 2026-09-29 to 2026-11-17, read
2026-11-18; 37 SEC and CAT rows, $6.16, to 2026-10-30, docs/JOURNAL.md). So (o)
and (a) are net of those few dollars and (b) is not; `COST_BASIS` below still
says "no fees" because every scores.csv row already written carries that text. `COST_BASIS` says so on every row. The
real-money view (the 5 / 15 / 30bp grid and borrow) is research's job, never
mixed in here (CLAUDE.md research rules).

FILL VERSUS AUCTION, IN BASIS POINTS, SIGNED SO POSITIVE IS WORSE FOR US
-----------------------------------------------------------------------
For each (symbol, side): VWAP of D's fills against D's auction print,
    buy:  (vwap - A_D) / A_D * 1e4     (paid more than the auction -> positive)
    sell: (A_D - vwap) / A_D * 1e4     (received less than the auction -> positive)
One sign convention for every row, so a column of positives reads as "paper
filled us worse than the auction would have", whatever the side. The day's
figure is the notional-weighted mean over those rows (weight = qty * A_D).

A MISSING PRINT IS A GAP, NEVER A SUBSTITUTE
--------------------------------------------
If a name that needs a print (held into the close: A_D and A_prev; filled on D:
A_D) has none, that name's auction P&L is UNMEASURED with the reason the
fetcher gave, and so is the day's total -- a sum with a missing term is not the
sum. No bar close, last trade or Alpaca `current_price` stands in: a daily bar
close is updated by condition 6, not M [V: bars reference], so it is a
different number, and a confident-looking total built on one is exactly the
IBKR-era failure CLAUDE.md names (a median fee charged to an unmeasured name).
The day's verdict is then FAIL-with-reason in `verify.py`.

PURE BY CONTRACT
----------------
No I/O, no clock, no broker. Everything arrives as arguments and every input is
checked: a zero or fractional share count, a non-positive or non-finite price,
a side other than buy/sell, or a needed print that is neither a price nor a
recorded gap raises naming it. A caller bug (forgetting to fetch a name) must
not be able to read as "UNMEASURED" -- only a gap the fetcher recorded may.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Mapping

# Printed on every score row. The paper account has no cost of any kind to
# charge; saying so on the row stops a reader taking a gross number for net.
COST_BASIS = ("gross; no borrow, no dividends, no fees "
              "(Alpaca paper charges and pays none; nothing added here)")
UNMEASURED = "UNMEASURED"
PENDING = "PENDING"
OFFICIAL_SOURCE = ("Alpaca end-of-day portfolio history, GET /v2/account/portfolio/history "
                   "timeframe 1D (P&L of record, team lead 2026-10-19)")


@dataclass(frozen=True)
class OfficialPnL:
    """Session D's official P&L: EOD(D) - EOD(previous session), from Alpaca's history.

    `change` is None exactly when the figure is PENDING, and then `pending`
    says why. Nothing is ever put in its place (module docstring, (o)).
    `points` is what the read returned for the two sessions, as
    {date: {"equity", "stamp"}}, kept for the record whether or not they made
    a figure. It answers an open question: does D's point exist at 17:30 ET,
    and does it change later? (`docs/REFERENCES.md` §12an.)
    """
    change: float | None
    equity_d: float | None
    equity_prev: float | None
    pending: str | None
    as_of: str
    points: dict = field(default_factory=dict)

    @property
    def measured(self) -> bool:
        return self.change is not None


def _at(t: dt.datetime, like: dt.datetime) -> str:
    """`t` in the read's own UTC offset, to the minute. No zone database is
    loaded here (that is a file read, and this module is pure); the read time
    verify passes is Alpaca's clock, which carries the New York offset."""
    return t.astimezone(like.tzinfo).isoformat(timespec="minutes")


def official_change(points, *, day: dt.date, prev: dt.date, as_of: dt.datetime) -> OfficialPnL:
    """D's official P&L from Alpaca's EOD points, or PENDING saying why. Pure.

    points  (date, equity, stamp) triples (`AlpacaClient.eod_equity_history`),
            dates in New York, stamps aware.
    day     session D; `prev` the session before it (Alpaca's calendar).
    as_of   when the points were read, by Alpaca's clock (aware).

    A POINT STAMPED AFTER THE READ IS NOT YET A FIGURE. Alpaca stamps a
    session's point after its close: the 2026-10-16 point was stamped
    2026-10-17T00:00Z, 20:00 in New York (§12an). It documents neither when the
    point first appears nor whether it can change. A point read before its own
    stamp describes a day whose window has not ended, so it is PENDING, and
    the collector records it once its stamp has passed. This rule never yields
    a wrong figure, whichever way those two unknowns turn out; it only delays
    one. A revision after that is logged by the collector (`eod_equity.csv`).
    """
    if not isinstance(as_of, dt.datetime) or as_of.tzinfo is None:
        raise ValueError(f"as_of {as_of!r} must be a timezone-aware datetime")
    if not prev < day:
        raise ValueError(f"prev {prev} must be before day {day}")
    got: dict = {}
    for i, p in enumerate(points):
        d, eq, stamp = p
        if d in got:
            raise ValueError(f"points[{i}]: two EOD points for {d}")
        if not isinstance(stamp, dt.datetime) or stamp.tzinfo is None:
            raise ValueError(f"points[{i}] ({d}): stamp {stamp!r} is not an aware datetime")
        got[d] = (_finite(eq, f"EOD equity for {d}"), stamp)
    seen = {d.isoformat(): {"equity": got[d][0], "stamp": got[d][1].isoformat()}
            for d in (prev, day) if d in got}
    reasons = []
    for d, what in ((day, "D"), (prev, "the previous session")):
        if d not in got:
            reasons.append(f"Alpaca's EOD history has no point for {what} {d} "
                           f"(read {_at(as_of, as_of)})")
        elif got[d][1] > as_of:
            reasons.append(f"Alpaca's point for {what} {d} is stamped {_at(got[d][1], as_of)}, "
                           f"after this read at {_at(as_of, as_of)}: its day has not closed")
    if reasons:
        return OfficialPnL(change=None, equity_d=None, equity_prev=None,
                           pending="; ".join(reasons), as_of=as_of.isoformat(), points=seen)
    eq_d, eq_prev = got[day][0], got[prev][0]
    return OfficialPnL(change=eq_d - eq_prev, equity_d=eq_d, equity_prev=eq_prev,
                       pending=None, as_of=as_of.isoformat(), points=seen)


@dataclass(frozen=True)
class Fill:
    """One broker-confirmed fill (an Alpaca FILL activity row, already parsed).
    `qty` is positive whole shares; the direction lives in `side`."""
    symbol: str
    side: str        # "buy" | "sell"
    qty: int
    price: float
    order_id: str

    def signed_qty(self) -> int:
        return self.qty if self.side == "buy" else -self.qty


@dataclass(frozen=True)
class AuctionPrints:
    """One session's official closing-auction prints.

    `prices` maps symbol -> price for every name that has one. `gaps` maps
    symbol -> the reason there is none (the fetcher's message: no print,
    exchanges disagree, data API refused). A name in neither was never asked
    for, which is a caller bug and raises in `score_day`.
    """
    prices: Mapping[str, float] = field(default_factory=dict)
    gaps: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DayScore:
    per_symbol: list            # list[dict], one per symbol held or filled, sorted by symbol
    alpaca_equity: float
    alpaca_last_equity: float
    alpaca_equity_change: float  # the SNAPSHOT, (a) above; not official since 2026-10-19
    auction_pnl: float | None   # None == UNMEASURED
    auction_hold_pnl: float | None
    auction_fill_pnl: float | None
    fill_vs_auction_bp: float | None   # notional-weighted over measured (symbol, side) rows; None if no fills measured
    unmeasured: list            # ["SYM: reason", ...] for every name whose auction P&L is UNMEASURED
    cost_basis: str = COST_BASIS

    @property
    def measured(self) -> bool:
        return not self.unmeasured


def _finite_positive(x, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"{what} = {x!r} is not a number")
    x = float(x)
    if not math.isfinite(x) or x <= 0:
        raise ValueError(f"{what} = {x!r} must be a finite price > 0")
    return x


def _finite(x, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"{what} = {x!r} is not a number")
    x = float(x)
    if not math.isfinite(x):
        raise ValueError(f"{what} = {x!r} is not finite")
    return x


def _print_for(prints: AuctionPrints, sym: str, label: str):
    """(price, None) or (None, reason). Neither -> the caller never fetched it."""
    if sym in prints.prices:
        if sym in prints.gaps:
            raise ValueError(f"{label} auction for {sym} is both a price and a gap")
        return _finite_positive(prints.prices[sym], f"{label} auction price for {sym}"), None
    if sym in prints.gaps:
        reason = prints.gaps[sym]
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{label} auction gap for {sym} has no reason")
        return None, reason
    raise ValueError(f"{label} auction print for {sym} was never fetched "
                     f"(not a price and not a recorded gap)")


def fill_vs_auction_bp(side: str, vwap: float, auction: float) -> float:
    """Signed so that positive is worse for us, whatever the side (module docstring)."""
    if side == "buy":
        return (vwap - auction) / auction * 1e4
    if side == "sell":
        return (auction - vwap) / auction * 1e4
    raise ValueError(f"side {side!r} must be buy|sell")


def score_day(*, held: Mapping[str, int], fills: list, auction_d: AuctionPrints,
              auction_prev: AuctionPrints, equity: float, last_equity: float) -> DayScore:
    """Score session D. See the module docstring for every formula and sign.

    held         {symbol: signed whole shares held at the START of D}, i.e. held
                 into D's close from before D's fills. Zero entries are refused
                 (a flat name is simply absent).
    fills        list[Fill] confirmed by the broker for D.
    auction_d    D's official closing-auction prints.
    auction_prev the previous session's prints (needed for held names only).
    equity, last_equity  Alpaca's account fields, as read: the snapshot (a). The
                 official figure (o) is `official_change`, from other inputs.
    """
    eq = _finite(equity, "equity")
    last_eq = _finite(last_equity, "last_equity")

    q0: dict[str, int] = {}
    for sym, q in held.items():
        if type(q) is not int or q == 0:
            raise ValueError(f"held[{sym}] = {q!r} must be a non-zero int (whole shares)")
        q0[sym] = q

    by_side: dict[tuple, list] = {}
    for i, f in enumerate(fills):
        if not isinstance(f, Fill):
            raise ValueError(f"fills[{i}] is {type(f).__name__}, not Fill")
        if f.side not in ("buy", "sell"):
            raise ValueError(f"fills[{i}] {f.symbol}: side {f.side!r} must be buy|sell")
        if type(f.qty) is not int or f.qty <= 0:
            raise ValueError(f"fills[{i}] {f.symbol}: qty {f.qty!r} must be a positive int")
        _finite_positive(f.price, f"fills[{i}] {f.symbol} price")
        by_side.setdefault((f.symbol, f.side), []).append(f)

    symbols = sorted(set(q0) | {s for s, _ in by_side})
    rows, unmeasured = [], []
    hold_total, fill_total = 0.0, 0.0
    bp_num, bp_den = 0.0, 0.0
    any_gap = False

    for sym in symbols:
        a_d, gap_d = _print_for(auction_d, sym, "D")
        row = {"symbol": sym, "held_qty": q0.get(sym, 0), "auction_d": a_d,
               "auction_prev": None, "hold_pnl": None, "fill_pnl": None,
               "auction_pnl": None, "sides": []}
        reasons = []
        if gap_d is not None:
            reasons.append(f"D print: {gap_d}")

        hold_pnl = 0.0
        if sym in q0:
            a_prev, gap_prev = _print_for(auction_prev, sym, "previous-session")
            row["auction_prev"] = a_prev
            if gap_prev is not None:
                reasons.append(f"previous-session print: {gap_prev}")
            if a_d is not None and a_prev is not None:
                hold_pnl = q0[sym] * (a_d - a_prev)

        fill_pnl = 0.0
        for side in ("buy", "sell"):
            fs = by_side.get((sym, side))
            if not fs:
                continue
            qty = sum(f.qty for f in fs)
            vwap = sum(f.qty * f.price for f in fs) / qty
            srow = {"side": side, "qty": qty, "vwap": vwap, "bp_vs_auction": None,
                    "order_ids": sorted({f.order_id for f in fs})}
            if a_d is not None:
                srow["bp_vs_auction"] = fill_vs_auction_bp(side, vwap, a_d)
                w = qty * a_d
                bp_num += srow["bp_vs_auction"] * w
                bp_den += w
                fill_pnl += sum(f.signed_qty() * (a_d - f.price) for f in fs)
            row["sides"].append(srow)

        if reasons:
            any_gap = True
            unmeasured.append(f"{sym}: " + "; ".join(reasons))
        else:
            row["hold_pnl"] = hold_pnl
            row["fill_pnl"] = fill_pnl
            row["auction_pnl"] = hold_pnl + fill_pnl
            hold_total += hold_pnl
            fill_total += fill_pnl
        rows.append(row)

    return DayScore(
        per_symbol=rows,
        alpaca_equity=eq,
        alpaca_last_equity=last_eq,
        alpaca_equity_change=eq - last_eq,
        auction_pnl=None if any_gap else hold_total + fill_total,
        auction_hold_pnl=None if any_gap else hold_total,
        auction_fill_pnl=None if any_gap else fill_total,
        fill_vs_auction_bp=(bp_num / bp_den) if bp_den > 0 else None,
        unmeasured=unmeasured,
    )
