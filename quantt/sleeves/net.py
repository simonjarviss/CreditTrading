"""Sleeve weights -> whole-share targets per sleeve -> ONE net target per symbol. Pure functions.

WHY NET. All event sleeves share one paper account, and Alpaca rejects opposite-side orders
in one symbol as wash trades (CLAUDE.md landmine 2). Two sleeves often want the same symbol
the opposite way: every special-dividend book shorts IWM, and the two closed-end fund
ex-date books hold the same funds on different days. So each sleeve's target is rounded to
whole shares FIRST, the sleeves are summed, and the account trades the difference between
that sum and what it holds: one order a symbol, or none. `ledger.py` keeps who owns what.

A SLEEVE'S TARGET, from its decision's weights w (fractions of the sleeve's capital):
    shares = trunc(w x capital / close)          toward zero; whole shares only
at the close of the decision's as-of session, the same price the core runner sizes on. A
symbol the sleeve holds and the decision no longer names is targeted to zero.

WHEN A SLEEVE HAS NO DECISION (missing, late, malformed: `inputs.py`) it HOLDS its shares,
as the shadow engine holds its latest on-time decision. After `max_stale_sessions` sessions
in a row it is FLATTENED: a book nobody is deciding must not sit in the account. A sleeve
the book file disables is flattened at once. A missing price for a symbol a decision names
is treated as no decision, naming the symbol: never sized on another day's price.

WHEN A HELD SYMBOL HAS NO CLOSE on the as-of session (a halt, a delisting: no daily bar), the
sleeve that holds it HOLDS everything it has, whatever its decision says, and a flatten
(disabled, or past the stale limit) is DEFERRED: nothing can be sized or valued in that name
today, and an order in it would be priced on nothing. Before 2026-11-16 one such symbol
refused the whole plan and stopped every sleeve (review of stage 2; coordinator's ruling). The
runner counts that position in the gross at the last close it recorded itself, labelled stale
(`run.py`), and `apply_limits` never scales it (`frozen`).

WHEN A LEG CANNOT BE OPENED. A short may be opened or increased only in a symbol Alpaca
marks shortable and easy to borrow today; a long only in an active, tradable asset. A leg
that fails stays at what the sleeve already holds on that side, and THE OTHER SIDE OF THAT
SLEEVE IS SCALED DOWN by the same proportion (dollars achieved over dollars wanted on the
blocked side). Every book here is long against short; a sleeve left long with no short
would be a different, unhedged strategy that nobody tested. A sleeve whose whole short
side is blocked therefore opens nothing. Dropped legs are returned and recorded.

THE BOOK'S LIMITS. If the gross of the netted targets exceeds `max_gross_x_equity` x equity,
every sleeve's targets are scaled by one factor (truncated again), so the mix is kept. The
gross is measured AGAIN after the truncation and, if it is still above the limit, the factor
is lowered and the ORIGINAL targets are scaled again, until it fits: truncating each sleeve
toward zero can leave the NET of two offsetting sleeves larger than the factor implies (+10
against -3 nets 7; at one half, 5 against -1 nets 4, not 3.5). Scale-again was chosen over a
fixed headroom because no headroom has a derivation here and the loop needs none.
A net position above `max_name_usd` REFUSES the plan, naming the symbol: one name that
large is a mistake upstream, not something to trim quietly.

Nothing here reads a file, a clock or a broker.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


class NetError(RuntimeError):
    """The plan is refused; the message names the sleeve or symbol and the limit."""


@dataclass(frozen=True)
class SleevePlan:
    slug: str
    action: str                 # decided | hold | flatten
    why: str
    targets: dict               # {symbol: signed whole shares}; zero targets are omitted
    stale_sessions: int         # sessions in a row with no usable decision, counting this one
    dropped: tuple = ()         # symbols whose opening leg was blocked today
    scale: dict = field(default_factory=dict)   # {"long": f, "short": f} applied after a blocked leg


def _price(closes: dict, sym: str) -> float | None:
    p = closes.get(sym)
    if p is None or isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or p <= 0:
        return None
    return float(p)


def sleeve_targets(weights: dict, capital: float, closes: dict, held: dict, can_short, can_buy) -> tuple:
    """({symbol: shares}, dropped symbols, {"long": f, "short": f}) for one decided sleeve.
    Raises KeyError naming a symbol with no usable close (the caller turns that into a hold)."""
    raw, px = {}, {}
    for sym, w in weights.items():
        p = _price(closes, sym)
        if p is None:
            raise KeyError(sym)
        px[sym] = p
        raw[sym] = int(math.trunc(w * capital / p))
    t, dropped = dict(raw), []
    for sym, q in raw.items():
        h = held.get(sym, 0)
        if q < min(h, 0) and not can_short(sym):          # would open or increase a short
            t[sym] = min(h, 0)
            dropped.append(sym)
        elif q > max(h, 0) and not can_buy(sym):          # would open or increase a long
            t[sym] = max(h, 0)
            dropped.append(sym)
    scale = {}
    if dropped:
        def side_usd(d, sign):
            return sum(abs(q) * px[s] for s, q in d.items() if q * sign > 0)
        want_s, got_s = side_usd(raw, -1), side_usd(t, -1)
        want_l, got_l = side_usd(raw, +1), side_usd(t, +1)
        # the factors are read BEFORE either side is scaled, so each side answers only for
        # the other side's blocked legs
        f_long = got_s / want_s if want_s > 0 and got_s < want_s else 1.0
        f_short = got_l / want_l if want_l > 0 and got_l < want_l else 1.0
        for sym, q in list(t.items()):
            if q > 0 and f_long < 1.0:
                t[sym] = int(math.trunc(q * f_long))
            elif q < 0 and f_short < 1.0:
                t[sym] = int(math.trunc(q * f_short))
        scale = {"long": round(f_long, 6), "short": round(f_short, 6)}
    return {s: q for s, q in sorted(t.items()) if q != 0}, tuple(sorted(dropped)), scale


def plan_sleeves(cfg, decisions: dict, ledger_shares: dict, stale_before: dict, closes: dict,
                 can_short, can_buy) -> list:
    """One SleevePlan per sleeve in the book file, in file order.

    decisions      {slug: {"weights": ...} | {"missing": reason}} from `inputs.read`
    ledger_shares  {slug: {symbol: shares}} from the ledger; a slug absent holds nothing
    stale_before   {slug: sessions in a row without a decision before this one}
    """
    # A sleeve that holds NOTHING may be dropped from the book file: its ledger record stays
    # (its cash is its realised P&L) and `ledger.shares_of` still lists it, with no shares.
    unknown = sorted(slug for slug, sh in ledger_shares.items()
                     if slug not in cfg.slugs and any(q != 0 for q in sh.values()))
    if unknown:
        raise NetError(f"the ledger holds shares for {unknown}, which the book file does not list; "
                       "list the sleeve (disabled, to flatten it) before running")
    out = []
    for s in cfg.sleeves:
        held = {k: v for k, v in ledger_shares.get(s.slug, {}).items() if v != 0}
        unpriced = sorted(sym for sym in held if _price(closes, sym) is None)
        if not s.enabled:
            if unpriced:
                out.append(SleevePlan(s.slug, "hold", f"disabled in the book file; flatten deferred: no "
                                      f"close for held {unpriced} on the as-of session", dict(sorted(held.items())), 0))
            else:
                out.append(SleevePlan(s.slug, "flatten", "disabled in the book file", {}, 0))
            continue
        d = decisions.get(s.slug)
        if d is None:
            raise NetError(f"no decision record was read for enabled sleeve {s.slug}")
        why = d.get("missing")
        if unpriced:
            n = int(stale_before.get(s.slug, 0)) + 1
            out.append(SleevePlan(s.slug, "hold", f"no close for held {unpriced} on the as-of session: "
                                  "the sleeve holds everything it has"
                                  + (f"; flatten deferred ({n} sessions, limit {cfg.max_stale_sessions})"
                                     if n > cfg.max_stale_sessions else "")
                                  + (f"; also: {why}" if why else ""), dict(sorted(held.items())), n))
            continue
        if why is None:
            try:
                t, dropped, scale = sleeve_targets(d["weights"], s.capital_usd, closes, held, can_short, can_buy)
                out.append(SleevePlan(s.slug, "decided", "", t, 0, dropped, scale))
                continue
            except KeyError as e:
                why = f"no usable close for {e.args[0]} on the as-of session"
        n = int(stale_before.get(s.slug, 0)) + 1
        if n > cfg.max_stale_sessions:
            out.append(SleevePlan(s.slug, "flatten", f"{why}; {n} sessions without a decision "
                                  f"(limit {cfg.max_stale_sessions})", {}, n))
        else:
            out.append(SleevePlan(s.slug, "hold", why, dict(sorted(held.items())), n))
    return out


def net_targets(plans) -> dict:
    net: dict = {}
    for p in plans:
        for sym, q in p.targets.items():
            net[sym] = net.get(sym, 0) + q
    return {s: q for s, q in sorted(net.items()) if q != 0}


MAX_RESCALES = 50


def apply_limits(cfg, plans: list, closes: dict, equity: float, frozen=()) -> tuple:
    """(plans, factor, gross_usd): scale to the gross limit, then refuse on the per-name limit.
    `frozen` symbols (held, with no close today) are valued but never scaled; if they alone
    are above the limit the plan is refused."""
    frozen = set(frozen)
    if isinstance(equity, bool) or not isinstance(equity, (int, float)) or not math.isfinite(equity) or equity <= 0:
        raise NetError(f"account equity {equity!r} must be a finite number > 0")

    def gross(ps):
        tot = 0.0
        for sym, q in net_targets(ps).items():
            p = _price(closes, sym)
            if p is None:
                raise NetError(f"no usable close for {sym}, which the plan holds; the gross cannot be measured")
            tot += abs(q) * p
        return tot

    def scaled(f):
        out = []
        for p in plans:
            t = {s: (q if s in frozen else int(math.trunc(q * f))) for s, q in p.targets.items()}
            out.append(SleevePlan(p.slug, p.action, p.why, {s: q for s, q in t.items() if q != 0},
                                  p.stale_sessions, p.dropped, p.scale))
        return out

    g, factor = gross(plans), 1.0
    cap = cfg.max_gross_x_equity * equity
    if g > cap:
        # the frozen part cannot shrink, so the first factor is the room left over what can
        held_usd = sum(abs(q) * _price(closes, s) for s, q in net_targets(plans).items() if s in frozen)
        factor = max(cap - held_usd, 0.0) / (g - held_usd) if g > held_usd else 0.0
        for _ in range(MAX_RESCALES):
            plans = scaled(factor)
            g = gross(plans)
            if g <= cap:
                break
            # measured again after truncation (module docstring): lower the factor, start over
            factor *= min(cap / g, 0.999)
        else:
            raise NetError(f"the plan's gross ${g:,.0f} cannot be scaled under max_gross_x_equity x equity "
                           f"${cap:,.0f}" + (f"; positions with no close today {sorted(frozen)} are not scaled"
                                             if frozen else ""))
    for sym, q in net_targets(plans).items():
        usd = abs(q) * _price(closes, sym)
        if usd > cfg.max_name_usd:
            raise NetError(f"{sym}: net position ${usd:,.0f} is above max_name_usd ${cfg.max_name_usd:,.0f}")
    return plans, factor, g
