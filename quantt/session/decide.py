"""Sleeve targets -> the whole-share MOC orders one session sends. Pure: no network, no disk.

WHY THIS IS ITS OWN MODULE
--------------------------
Everything that turns "the strategy wants weight w in PDI" into "sell 312 PDI
at the close" lives here, in one function with no I/O, so that the exact list a
human approves can be recomputed from the same inputs and hashed
(`plan_sha`, gate 2: what was approved is what is sent). The IBKR-era executor
spread this across a sizing helper, a ledger and the broker adapter, and the
two worst incidents in this book's history came from the seams:

  * Dust orders (2026-09-08, results/cef/DUST_ORDERS_2026-09.md): a band HOLD
    emitted as a weight made a round trip through two different closes and came
    back as a few shares of rounding drift, sent as live MOC orders. So a qty
    target (the sleeve's HOLD) is used EXACTLY as given here -- its diff against
    the holding it was computed from is zero by construction -- and never
    re-derived through a price.
  * The invented book size: targets once sized against a $500k default while the
    account was marked otherwise. So `equity` is a required input, from the
    broker, and a missing close for a name that must be sized raises naming it.

SIZING
------
weight target -> shares = int(trunc(w * equity / close)), i.e. rounded TOWARD
ZERO. Toward zero, not to nearest, because both errors it can make shrink the
book: a long is never bought past its weight and a short is never sold past
it, so rounding can never push gross over `max_gross_stress` (which the sleeve
enforced in weight space) or spend buying power the target did not. The cost is
at most one share per name of under-exposure (prereg v7 section 7, "whole
shares only").

`equity` is the Alpaca account's equity, the same number the runner passes the
sleeve as `extras["sleeve_nav"]`: the band compares held weight q*px/nav against
target, so sizing and banding must share one denominator.

`close` is each name's own last close on or before the as-of date,
`px.ffill().iloc[-1]` per name (CLAUDE.md landmine 6: HYT lags the panel by a
day, so the panel's last row can be NaN for one name). The runner records the
date of every close it passes; gate 5 refuses unless every one is the as-of
date, so the ffill can never silently size on an older print.

NETTING AND THE FLIP
--------------------
One order per symbol per session, because Alpaca rejects opposite-side orders
in one symbol as wash trades (CLAUDE.md landmine 2; docs "user-protection" [V]:
market buy vs market sell is "always rejected", paper included).

A long->short or short->long flip cannot be one order ([S] Alpaca staff 2020:
"you cannot flip position side in one order. You need to flatten the position
first"). RUNNER.md's design was two same-side orders in one session: close to
zero (leg 1), open the other side (leg 2). The verified facts say that second
order is likely rejected:

  [V] Alpaca Learn, "How to fix common trading API errors" (fetched
  2026-09-28): the shares tied to a pending sell "are reserved until the order
  is filled or canceled"; "Alpaca does not support holding long and short
  positions in the same symbol at the same time ... confirm the long position
  is fully closed before submitting a new order to open a short position."
  [S] staff 2023: "The first order to sell just to get the position to 0, and a
  second sell short ... Alpaca currently doesn't support creating two orders
  like that."

A cls close-to-zero is not filled until the auction, so the open leg cannot be
confirmed-closed-first within one session. IMPLEMENTED: `FLIP_SAME_SESSION =
False` -- a flip sends ONLY the closing leg today (client id `...-1`) and says
`flip deferred` in its note; the next session sees a flat position and the
sleeve's band opens the other side from there. The two-leg path is kept behind
the flag, tested, for the day probe 3.2 shows paper accepts it; turning it on is
a team-lead decision, not a code default. A deferred flip leaves the name flat
for one session, which is a small, bounded divergence from the backtest (which
flips instantly) and is logged every time it happens.

SHORTABILITY (gate 7, prereg v7 section 6)
------------------------------------------
Any order that opens or increases a short needs `shortable` exactly True for
that symbol today. If it is not, THAT SYMBOL SENDS NOTHING this session and the
note says why; no other name is substituted. A symbol that needs the check and
is missing from the map raises: an unmeasured borrow is not a shortable one.
Covering a short or selling a long never needs it.

Each symbol so skipped is also listed in `Decision.dropped_shorts`, in universe
order (added 2026-11-03 for CEF trial 55, te4: results/cef/
PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md §1.3 item 6, §7.5, §10 Q7). On a
reduced session of 4-5 names a skipped short can be the whole short side, and
the ruling is that such a decision flattens instead of trading a one-sided book
the harness never scored; the runner needs that fact as a field, not as the
note's prose. It is not in `to_dict` and not in `plan_sha`, so plan.json's
decision record and what is hashed are byte-identical to before.

TRANSMIT ORDER (review 2026-09-28)
----------------------------------
The runner stops the batch at the first rejection or ambiguous submit, and a
stopped day is not resumed (gate 6). So the ORDER of the list decides what
the book holds overnight when something fails part-way. Alphabetical order
(the first build) left an arbitrary slice -- on a flat day one, possibly all
the longs from A to H and no shorts. `transmit_sequence` instead orders
greedily so the running net dollar change (sum of signed qty x as-of close
over the orders sent so far) stays as close to zero as it can after every
order: at each step it takes the order that minimises |running net|,
breaking ties by larger notional, then SELL before BUY (a short-open is the
order most likely to be rejected -- Alpaca refuses an HTB short without a
locate and paper has no locates [V] -- and a rejection first means nothing
unhedged went), then symbol and leg. A flip's leg 2 is never placed before
its leg 1. This does not make a partial set neutral; it bounds how far from
neutral any stopping point can be. What to do after a stop is a team-lead
decision (docs/RUNBOOK.md), not something this ordering answers.

THE PLAN HASH
-------------
`plan_sha` is sha256 over a canonical JSON (sorted keys, no whitespace) of what
is TRANSMITTED and nothing else: client_order_id, symbol, side, qty, type,
time_in_force, in list order. Estimates (price, notional) and prose are
excluded on purpose, so a re-run that sends the same orders hashes the same,
and any change to what would be sent -- one share, one symbol, another date in
the id -- changes the hash and fails `--approve`.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from dataclasses import asdict, dataclass

from src.deploy.sleeve import FLAT, LONG, SHORT

# See "NETTING AND THE FLIP" above. False = close today, open next session.
FLIP_SAME_SESSION = False

ORDER_TYPE = "market"
TIME_IN_FORCE = "cls"
# "day" exists for the PAPER account only (team lead 2026-09-29, a recorded
# exception to CLAUDE.md rule 3): Alpaca paper runs no closing auction and
# treats `cls` as a market order at the close with random partial fills -- on
# 2026-09-29, 11 of 13 `cls` orders expired unfilled -- so on paper the book is
# sent as plain market orders in the last minutes before the close instead
# (docs/RUNNER.md "Paper execution"). The default stays `cls`.
ALLOWED_TIME_IN_FORCE = ("cls", "day")


class DecisionError(ValueError):
    """The inputs cannot be turned into orders without guessing. Names what is wrong."""


@dataclass(frozen=True)
class Order:
    """One order to transmit. `qty` is positive; the direction is `side`."""
    symbol: str
    side: str                # "buy" | "sell"
    qty: int
    leg: int                 # 1, or 2 for the open leg of a same-session flip
    client_order_id: str
    current: int             # signed shares held before this session
    target: int              # signed shares the sleeve wants after this session
    est_price: float         # the as-of close used for sizing/estimates (not sent)
    reason: str              # the sleeve's reason string + what this leg does
    time_in_force: str = TIME_IN_FORCE   # sent; "cls" unless the book's execution says otherwise

    def __post_init__(self):
        if self.time_in_force not in ALLOWED_TIME_IN_FORCE:
            raise DecisionError(f"{self.client_order_id}: time_in_force {self.time_in_force!r} "
                                f"not in {ALLOWED_TIME_IN_FORCE}")

    @property
    def signed_qty(self) -> int:
        return self.qty if self.side == "buy" else -self.qty

    @property
    def est_notional(self) -> float:
        return self.qty * self.est_price

    def wire(self) -> dict:
        """Exactly the fields that go to Alpaca (and into plan_sha)."""
        return {"client_order_id": self.client_order_id, "symbol": self.symbol,
                "side": self.side, "qty": self.qty, "type": ORDER_TYPE,
                "time_in_force": self.time_in_force}

    def to_dict(self) -> dict:
        d = asdict(self)
        d["est_notional"] = self.est_notional
        return d


@dataclass(frozen=True)
class Decision:
    orders: tuple            # of Order, in transmit order (`transmit_sequence`)
    targets: dict            # symbol -> {"current", "target", "kind", "reason"}
    notes: dict              # symbol -> list of strings (no trade, deferred, not shortable ...)
    plan_sha: str
    # Symbols whose short-opening (or short-increasing) order gate 7 skipped as not
    # shortable today, in universe order (SHORTABILITY above; CEF trial 55). LAST and
    # defaulted, so every keyword construction elsewhere still builds, and read by
    # neither `to_dict` nor `plan_sha`. A Decision rebuilt from another's fields must
    # carry it across explicitly, or it reads ().
    dropped_shorts: tuple = ()

    def to_dict(self) -> dict:
        return {"plan_sha": self.plan_sha,
                "orders": [o.to_dict() for o in self.orders],
                "targets": self.targets, "notes": self.notes}


def client_order_id(prefix: str, session_date: dt.date, symbol: str, leg: int) -> str:
    """`<prefix>-<YYYYMMDD>-<SYMBOL>-<leg>`. The session date is in the id so an
    id is never reused across sessions (client_order_id is unique only among
    ACTIVE orders at Alpaca [V]; reuse after a fill is undocumented [U])."""
    if not isinstance(session_date, dt.date) or isinstance(session_date, dt.datetime):
        raise DecisionError(f"session_date {session_date!r} must be a datetime.date")
    return f"{prefix}-{session_date:%Y%m%d}-{symbol}-{leg}"


def transmit_sequence(orders) -> tuple:
    """The orders in the sequence the runner sends them. See "TRANSMIT ORDER".

    Deterministic in its input set (the start is sorted by (symbol, leg), and
    every tie is broken by fields of the order), so the same orders always
    hash to the same plan_sha."""
    pending = sorted(orders, key=lambda o: (o.symbol, o.leg))
    out, net, placed = [], 0.0, set()
    while pending:
        ok = [o for o in pending if o.leg == 1 or (o.symbol, o.leg - 1) in placed]
        if not ok:
            raise DecisionError(f"flip leg ordering is unsatisfiable for "
                                f"{[o.client_order_id for o in pending]}")
        best = min(ok, key=lambda o: (abs(net + o.signed_qty * o.est_price),
                                      -o.est_notional, 0 if o.side == "sell" else 1,
                                      o.symbol, o.leg))
        out.append(best)
        pending.remove(best)
        placed.add((best.symbol, best.leg))
        net += best.signed_qty * best.est_price
    return tuple(out)


def plan_sha(orders) -> str:
    """sha256 of the canonical JSON of the transmitted fields, in order."""
    payload = json.dumps([o.wire() for o in orders], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_whole(x) -> bool:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f) and f == int(f)


def target_shares(t, equity: float, close: float | None) -> tuple[int, str]:
    """(signed target shares, kind) for one PositionTarget. kind is flat|qty|weight.

    FLAT -> 0. A qty target (the sleeve's band HOLD) is used as given, and must
    be whole: a fractional hold is something this runner never bought. A
    weight target is sized toward zero against `equity` at `close`; its sign
    must agree with its side (PositionTarget.weight is already signed --
    CLAUDE.md landmine 7 -- so it is never multiplied by the side again).
    """
    if t.side == FLAT:
        return 0, "flat"
    if t.qty is not None:
        q = t.signed_qty()
        if not _is_whole(q):
            raise DecisionError(f"{t.instrument}: qty target {t.qty!r} is not a whole number "
                                f"of shares")
        return int(q), "qty"
    w = t.weight
    if w is None or not math.isfinite(float(w)):
        raise DecisionError(f"{t.instrument}: weight target {w!r} is not a finite number")
    w = float(w)
    if (t.side == LONG and w <= 0) or (t.side == SHORT and w >= 0):
        raise DecisionError(f"{t.instrument}: side {t.side} disagrees with signed weight {w}")
    if close is None:
        raise DecisionError(f"{t.instrument}: weight target needs a close and none was given")
    return int(math.trunc(w * equity / close)), "weight"


def _opens_or_increases_short(cur: int, after: int) -> bool:
    """True if moving from `cur` to `after` leaves a short larger than any held now."""
    return after < 0 and after < min(cur, 0)


def decide(targets, positions: dict, equity: float, closes: dict, shortable: dict, *,
           session_date: dt.date, universe, cid_prefix: str, min_trade_usd: float,
           flip_same_session: bool = FLIP_SAME_SESSION,
           time_in_force: str = TIME_IN_FORCE) -> Decision:
    """Turn the sleeve's targets into this session's orders. See the module docstring.

    targets       the sleeve's PositionTargets, exactly one per universe symbol
    positions     {symbol: signed int} from Alpaca; a symbol absent is held flat
                  (that is what /v2/positions says, not a default)
    equity        Alpaca account equity, > 0
    closes        {symbol: float}, the as-of close; required for every symbol
                  that is weight-sized or has an order
    shortable     {symbol: bool} from /v2/assets today; required for every symbol
                  whose order would open or increase a short
    min_trade_usd the spec's rebalance.min_trade_usd; a delta whose estimated
                  notional is strictly below it is not sent (0 sends every whole share)
    """
    if isinstance(equity, bool) or not isinstance(equity, (int, float)) \
            or not math.isfinite(equity) or equity <= 0:
        raise DecisionError(f"equity {equity!r} must be a finite number > 0")
    if isinstance(min_trade_usd, bool) or not isinstance(min_trade_usd, (int, float)) \
            or not math.isfinite(min_trade_usd) or min_trade_usd < 0:
        raise DecisionError(f"min_trade_usd {min_trade_usd!r} must be a finite number >= 0")
    universe = sorted(universe)
    by_sym = {}
    for t in targets:
        if t.instrument in by_sym:
            raise DecisionError(f"the sleeve emitted two targets for {t.instrument}")
        if t.instrument not in universe:
            raise DecisionError(f"the sleeve emitted {t.instrument}, which is not in the "
                                f"frozen universe {universe}")
        by_sym[t.instrument] = t
    missing = [s for s in universe if s not in by_sym]
    if missing:
        raise DecisionError(f"the sleeve emitted no target for {missing}; refusing to "
                            f"treat a missing target as flat")
    for s, q in positions.items():
        if type(q) is not int:
            raise DecisionError(f"position {s}={q!r} is not an int number of shares")

    def close_of(sym):
        c = closes.get(sym)
        if c is None or isinstance(c, bool) or not math.isfinite(float(c)) or float(c) <= 0:
            raise DecisionError(f"{sym}: no usable close ({c!r}) for the as-of date")
        return float(c)

    orders, tgt_out, notes, dropped = [], {}, {}, []
    for sym in universe:
        t = by_sym[sym]
        cur = positions.get(sym, 0)
        need_close = t.side != FLAT and t.qty is None
        tgt, kind = target_shares(t, equity, close_of(sym) if need_close else None)
        tgt_out[sym] = {"current": cur, "target": tgt, "kind": kind, "reason": t.reason}
        sym_notes = notes.setdefault(sym, [])
        delta = tgt - cur
        if delta == 0:
            sym_notes.append("no trade: target equals holding")
            continue
        price = close_of(sym)
        if abs(delta) * price < min_trade_usd:
            sym_notes.append(f"no trade: |delta| {abs(delta)} x {price} below min_trade_usd "
                             f"{min_trade_usd}")
            continue

        side = "buy" if delta > 0 else "sell"
        flip = cur != 0 and tgt != 0 and (cur > 0) != (tgt > 0)
        if not flip:
            legs = [(1, abs(delta), cur, tgt, "trade to target")]
        elif flip_same_session:
            legs = [(1, abs(cur), cur, 0, "flip leg 1: close to zero"),
                    (2, abs(tgt), 0, tgt, "flip leg 2: open the other side")]
        else:
            legs = [(1, abs(cur), cur, 0, "flip deferred: closing leg only today; "
                                          "the open leg is left to the next session")]
            sym_notes.append(f"flip deferred: {cur:+d} -> 0 today, target {tgt:+d} "
                             f"(FLIP_SAME_SESSION=False)")

        needs_short = any(_opens_or_increases_short(a, b) for _, _, a, b, _ in legs)
        if needs_short:
            if sym not in shortable:
                raise DecisionError(f"{sym}: order opens or increases a short and no "
                                    f"shortable status was measured for it today")
            s = shortable[sym]
            if s is not True and s is not False:
                raise DecisionError(f"{sym}: shortable={s!r} is not a bool")
            if s is not True:
                sym_notes.append(f"not shortable today: no order sent for {sym} "
                                 f"(wanted {cur:+d} -> {tgt:+d}); no name substituted")
                dropped.append(sym)
                continue
        for leg, qty, a, b, what in legs:
            orders.append(Order(symbol=sym, side=side, qty=int(qty), leg=leg,
                                client_order_id=client_order_id(cid_prefix, session_date, sym, leg),
                                current=a, target=b, est_price=price,
                                reason=f"{what}; {t.reason}", time_in_force=time_in_force))
    orders = transmit_sequence(orders)
    return Decision(orders=orders, targets=tgt_out,
                    notes={k: v for k, v in notes.items() if v}, plan_sha=plan_sha(orders),
                    dropped_shorts=tuple(dropped))
