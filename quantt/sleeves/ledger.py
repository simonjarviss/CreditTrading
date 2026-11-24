"""Who owns which shares in the shared account, and what each sleeve has paid. Pure functions.

WHY A LEDGER. Orders are netted across sleeves (`net.py`), so one fill in IWM may belong to
three books and a sleeve's trade may never reach the broker at all, when another sleeve
takes the other side. The broker therefore cannot say what a sleeve holds or has earned;
only this runner's own book-keeping can. The ledger is that record:

    {"version": 1, "session": "<last session applied>",
     "sleeves": {slug: {"shares": {symbol: signed whole shares}, "cash": dollars,
                        "stale_sessions": n}}}

`cash` starts at zero and moves by -(shares booked x price) on every booking, so a sleeve's
running P&L at any marks is cash + sum(shares x mark). Dividends and fees are the account's
and are not attributed here (paper books none; CLAUDE.md landmine 1).

THE INVARIANT, checked before every plan and after every booking: for every symbol, the
sleeves' shares sum to the broker's position, exactly. If they do not, something traded
that this runner did not book (a manual order, a corporate action paper did not process, a
lost fill), and the runner refuses until a person has repaired the ledger.

HOW ONE SYMBOL'S FILL IS SHARED (`allocate`). Each sleeve wanted a signed change d_s; the
account sent the net D = sum(d_s) and F of it filled (F has D's sign, |F| <= |D|, or is 0).
  * Sleeves on the other side of the net are met in full: their shares come from the
    sleeves on the net's side, inside the account, with no order.
  * The net's side shares what is available, F plus what the other side supplied, in
    proportion to what each wanted. Shares are whole: the largest remainders get the odd
    ones, ties going to the slug that sorts first, so the split is deterministic.
  * Every share booked for that symbol that session is priced at the fills' average price
    when there was a fill, and at the caller's cross price (the official close) when the
    sleeves crossed completely and nothing was sent. Either way the sleeves' cash changes
    sum to what the account paid.
An unfilled remainder is not chased: the next session's plan sees the ledger as it is.
"""
from __future__ import annotations

import copy
import math


class LedgerError(RuntimeError):
    """The ledger and the broker disagree, or a booking is impossible; names the symbol."""


def empty() -> dict:
    return {"version": 1, "session": None, "sleeves": {}}


def shares_of(ledger: dict) -> dict:
    """{slug: {symbol: shares}} with zero rows left out."""
    return {slug: {s: q for s, q in sorted(rec["shares"].items()) if q != 0}
            for slug, rec in sorted(ledger["sleeves"].items())}


def totals(ledger: dict) -> dict:
    tot: dict = {}
    for rec in ledger["sleeves"].values():
        for sym, q in rec["shares"].items():
            if type(q) is not int:
                raise LedgerError(f"ledger holds {q!r} shares of {sym}: not a whole number")
            tot[sym] = tot.get(sym, 0) + q
    return {s: q for s, q in sorted(tot.items()) if q != 0}


def check_against_broker(ledger: dict, positions: dict) -> None:
    """Raise unless the sleeves' shares sum to the broker's position in every symbol."""
    mine = totals(ledger)
    theirs = {s: q for s, q in positions.items() if q != 0}
    bad = {s: (mine.get(s, 0), theirs.get(s, 0)) for s in sorted(set(mine) | set(theirs))
           if mine.get(s, 0) != theirs.get(s, 0)}
    if bad:
        raise LedgerError("the ledger and the broker disagree (symbol: ledger, broker): "
                          + ", ".join(f"{s}: {a:+d}, {b:+d}" for s, (a, b) in bad.items())
                          + ". Something traded that this runner did not book; repair the ledger before running")


def allocate(wanted: dict, filled: int) -> dict:
    """{slug: shares booked} for one symbol. `wanted` is {slug: signed change}, zeros allowed."""
    for slug, d in wanted.items():
        if type(d) is not int:
            raise LedgerError(f"{slug} wanted {d!r} shares: not a whole number")
    if type(filled) is not int:
        raise LedgerError(f"filled {filled!r} is not a whole number of shares")
    net = sum(wanted.values())
    if filled != 0 and (net == 0 or (filled > 0) != (net > 0) or abs(filled) > abs(net)):
        raise LedgerError(f"filled {filled:+d} cannot come from a net order of {net:+d}")
    sign = 1 if net > 0 else -1
    same = {s: d for s, d in wanted.items() if d * sign > 0} if net != 0 else {}
    out = {s: d for s, d in wanted.items() if s not in same}       # the other side, and zeros: in full
    avail = abs(filled) + abs(sum(d for s, d in wanted.items() if s not in same))
    want = sum(abs(d) for d in same.values())
    if avail > want:
        raise LedgerError(f"{avail} shares available for sleeves that wanted {want}")
    base = {s: abs(d) * avail // want for s, d in same.items()} if want else {}
    left = avail - sum(base.values())
    order = sorted(same, key=lambda s: (-((abs(same[s]) * avail) % want), s)) if want else []
    for s in order[:left]:
        base[s] += 1
    out.update({s: sign * q for s, q in base.items()})
    assert sum(out.values()) == filled, (wanted, filled, out)
    return out


def apply(ledger: dict, plans: list, fills: dict, cross_prices: dict, session: str) -> tuple:
    """(new ledger, bookings) after a session's fills.

    plans         the SleevePlans the orders were built from (targets per sleeve)
    fills         {symbol: (signed shares filled, average fill price)} from the broker's FILL
                  activities for THIS runner's orders; a symbol with no fill is absent
    cross_prices  {symbol: official close} for symbols the sleeves crossed with no order
    bookings      [{slug, symbol, shares, price, kind: "fill" | "cross"}]
    """
    new = copy.deepcopy(ledger)
    for p in plans:
        rec = new["sleeves"].setdefault(p.slug, {"shares": {}, "cash": 0.0, "stale_sessions": 0})
        rec["stale_sessions"] = p.stale_sessions
    symbols = sorted({s for p in plans for s in p.targets} | {s for r in new["sleeves"].values() for s in r["shares"]})
    extra = sorted(set(fills) - set(symbols))
    if extra:
        raise LedgerError(f"fills in {extra}, which no sleeve holds or targets")
    bookings = []
    for sym in symbols:
        wanted = {p.slug: p.targets.get(sym, 0) - new["sleeves"][p.slug]["shares"].get(sym, 0) for p in plans}
        qty, vwap = fills.get(sym, (0, None))
        booked = allocate(wanted, qty)
        if not any(booked.values()):
            continue
        if qty != 0:
            price, kind = vwap, "fill"
        else:
            price, kind = cross_prices.get(sym), "cross"
        if price is None or isinstance(price, bool) or not math.isfinite(price) or price <= 0:
            raise LedgerError(f"{sym}: no usable {'fill' if qty else 'cross'} price ({price!r}) to book at")
        for slug, q in sorted(booked.items()):
            if q == 0:
                continue
            rec = new["sleeves"][slug]
            rec["shares"][sym] = rec["shares"].get(sym, 0) + q
            if rec["shares"][sym] == 0:
                del rec["shares"][sym]
            rec["cash"] -= q * float(price)
            bookings.append({"slug": slug, "symbol": sym, "shares": q, "price": float(price), "kind": kind})
    new["session"] = session
    return new, bookings


def pnl(ledger: dict, marks: dict) -> dict:
    """{slug: cash + shares at marks}. Raises naming a held symbol with no mark."""
    out = {}
    for slug, rec in sorted(ledger["sleeves"].items()):
        v = rec["cash"]
        for sym, q in rec["shares"].items():
            m = marks.get(sym)
            if m is None or not math.isfinite(m) or m <= 0:
                raise LedgerError(f"{slug} holds {sym} and there is no mark for it")
            v += q * float(m)
        out[slug] = v
    return out
