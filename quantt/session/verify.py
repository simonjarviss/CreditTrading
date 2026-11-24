"""Post-close verification of one session: reconcile from the broker, score it, one verdict line.

WHY THIS EXISTS
---------------
`docs/ROADMAP.md` 4.5-4.7 and `docs/RUNNER.md` ("17:30 ET ... verify"). The
session job decides and transmits in the morning; nothing in that job can know
what actually happened in the afternoon auction. This module is the only place
that asks, and it asks the BROKER -- never a local ledger -- because the local
record is what the runner meant to do, and the two have diverged before on this
desk in every direction (an order that was never at the broker, a fill nobody
recorded, a second set of orders in the same auction). It writes exactly one
line per run to `<QUANTT_STATE_DIR>/verify.log`:

    YYYY-MM-DD PASS|FAIL <book> <reason summary>

and the runbook reads that file (`docs/RUNBOOK.md` §5). **Silence never reads
as success** (ROADMAP 4.7): a trading day with no line is a FAIL, a day the
runner did not trade still gets a line saying why, and a day with no record at
all is a FAIL -- never a PASS by omission. Any exception inside verification is
itself turned into a FAIL line naming it (the loud fallback, not a silent one),
so a crash cannot leave a day without a verdict. The only case with no line is
when there is nowhere to write it (`QUANTT_STATE_DIR` unset or missing); the
exit code is then 2 and the missing line is itself the FAIL.

READ-ONLY. This module calls only GETs on `quantt.broker.alpaca.AlpacaClient`
(clock, calendar, orders, order_by_client_id, activities_fills, positions,
account, eod_equity_history, stock_exchanges, asset via primary_sip_code,
closing_auction_prints, and -- through `dist_score.py` -- distributions). It never imports or calls `submit_order`; a
test walks this file's AST to keep it that way. An `AmbiguousSubmit` from the
morning is resolved here the only safe way: by looking the id up.

WHAT "RECONCILE" CHECKS, AND WHY EACH IS A FAIL
-----------------------------------------------
Local records (layout agreed through `docs/RUNNER.md`):
    <state>/<D>/STARTED       written by run.py before the first order
    <state>/<D>/orders.jsonl  run.py's event log: a `submit` line (client_order_id,
                              symbol, side, qty) before each POST, then
                              accepted/ambiguous/lookup/error/confirm lines
    <state>/<D>/plan.json     {"book", "session_date", "mode", "orders": [...],
                               "refusals": [{"gate", "detail"}, ...]}
    (both written by `quantt/session/run.py` through `records.py`)
Broker truth, for D:
  1. Every cid with a `submit` line in orders.jsonl is looked up by client
     id -- including one whose POST raised: a rejected order is not at
     Alpaca and says so, an ambiguous one is resolved here by the lookup. Not found -> FAIL
     (the runner believes it sent an order Alpaca does not have). Found but a
     different symbol/side/qty -> FAIL. Status other than `filled` with
     filled_qty == qty after the close -> FAIL naming the status (partially
     filled, canceled, expired, rejected, still open): the book is not where the
     plan put it, and the team lead must see that today, not at month end.
  2. Every order Alpaca shows in the window with this book's D prefix
     (`<book>-<YYYYMMDD>-`) must be in orders.jsonl, and every order WITHOUT a
     runner prefix is foreign -> FAIL. One account per book (CLAUDE.md
     landmine 2), so any order the runner did not place moves this book's P&L.
     The window runs from 00:00 ET on the previous trading day to 00:00 ET
     after D: a `cls` order placed after 19:00 ET is queued into the NEXT
     day's auction [V: orders-at-alpaca], so the evening before D matters. It is
     deliberately over-inclusive -- a foreign order on the previous day is
     flagged again on D -- because the error it risks is a false FAIL, never a
     false PASS.
  3. No STARTED, but Alpaca holds orders with D's prefix -> FAIL: something
     transmitted without recording first (CLAUDE.md order-path rule 2).
  4. Fills (account activities, FILL, for D): each must belong to one of the
     runner's orders for D, and per order the fills must sum to Alpaca's
     `filled_qty`. Paper splits fills at random ("partial fills for a random
     size 10% of the time" [V]), so a sum, never a single row, is compared.
  5. Positions after the close are read, and the book held INTO D's close is
     derived from them: q0 = positions_after - net fills on D. Both sides of
     that subtraction are broker data; no local ledger is consulted.

WHEN IT MAY RUN
---------------
Only between D's close and the next open, on D itself (ET), because two of its
inputs are "now" numbers: the snapshot `equity - last_equity` (Alpaca's
`last_equity` is "equity as of previous trading day at 16:00:00 ET" [V]) and
current positions. Run a day late and both describe a different session, and a
score would be a confident wrong number. So: the Alpaca clock's ET date must equal D, the market
must be closed, and `next_open` must be after D. Otherwise the line is a FAIL
saying so. A holiday (no `/v2/calendar` row for D) is PASS "not a trading day",
unless a STARTED file exists for it.

THE P&L ON THE LINE (team lead, 2026-10-19)
-------------------------------------------
Three figures, labelled, never blended (`quantt/session/score.py`):
    official +X USD (Alpaca EOD history, gross)    or    official PENDING (<why>)
    snapshot HH:MM ET +Y USD (gross)
    auction-marked +Z USD (gross)
"official" is Alpaca's end-of-day portfolio history, EOD(D) - EOD(previous
session): the P&L of record. It is PENDING when D's point has not been
published by this read, or is stamped after it (Alpaca stamped the 2026-10-16
point 20:00 ET, after a 17:30 verify; a half day's point is stamped 17:00 ET,
read 2026-11-14), or the history could not be read. The
snapshot is never put in its place. "snapshot" is the account's
`equity - last_equity` as read now. Until 2026-10-19 the line called it
"(official, gross)". HH:MM is this run's Alpaca clock read, seconds before the
account read. The official figure never changes the verdict: PASS and FAIL
are decided exactly as before, and a history Alpaca will not serve is a
PENDING reason, never a FAIL. reconcile.json keeps it under `official_eod`,
with the points read for D and the previous session. scores.csv is
append-only with a fixed header that other code reads by name, so it gains no
column; its `alpaca_equity_change_usd` is the snapshot. The series of record
is `<state>/eod_equity.csv`, kept by the collector.

SCORING is `quantt/session/score.py` (pure). Auction prints are fetched ONE
SYMBOL AT A TIME so a name without a print, or with prints that disagree across
exchanges, becomes that name's gap (with the client's reason) rather than
sinking every other name's measurement. Only the PRIMARY listing exchange's
print counts (asset exchange -> SIP code through Alpaca's live exchange table;
`fetch_prints`). Condition "M" vs "6" is still an open question the client
documents; `--condition` passes the choice through and it is recorded.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from quantt.session.records import StateDirError, require_book_state_dir
from quantt.session.score import (COST_BASIS, OFFICIAL_SOURCE, PENDING, UNMEASURED,
                                  AuctionPrints, DayScore, Fill, OfficialPnL,
                                  official_change, score_day)

# Every wall-clock boundary here is New York time: the auction is NYSE's, and
# RUNNER.md states the session in ET. Alpaca timestamps carry their own offset
# (the client refuses one that does not), so conversion is exact.
ET = ZoneInfo("America/New_York")

# How far back to look for the previous trading day. The longest US market
# closure since 1900 outside wartime was four sessions (2001); 14 calendar days
# covers any holiday cluster, and finding none raises rather than guessing.
PREV_SESSION_LOOKBACK_DAYS = 14

# The one line's reason is capped so verify.log stays one screen line per day;
# the full detail is in <state>/<D>/reconcile.json, which the cap message names.
REASON_MAX_CHARS = 1200

SCORES_COLUMNS = (
    "date", "book", "verdict", "traded", "n_orders", "n_filled",
    "alpaca_equity", "alpaca_last_equity", "alpaca_equity_change_usd",
    "auction_pnl_usd", "auction_hold_pnl_usd", "auction_fill_pnl_usd",
    "fill_vs_auction_bp", "unmeasured", "auction_condition", "cost_basis",
    "read_at", "per_symbol_json",
)


class RecordError(ValueError):
    """A local record (plan.json / orders.jsonl) is not in the agreed shape."""


@dataclass
class Verdict:
    date: dt.date
    book: str
    ok: bool
    reason: str
    score: DayScore | None = None
    traded: bool = False
    n_orders: int = 0
    n_filled: int = 0
    read_at: str = ""
    condition: str = ""
    detail: dict = field(default_factory=dict)
    official: OfficialPnL | None = None

    def line(self) -> str:
        reason = " ".join(self.reason.split())       # one line, whatever the message held
        if len(reason) > REASON_MAX_CHARS:
            reason = (reason[:REASON_MAX_CHARS]
                      + f" ...(truncated; see {self.date.isoformat()}/reconcile.json)")
        return f"{self.date.isoformat()} {'PASS' if self.ok else 'FAIL'} {self.book} {reason}"


# ------------------------------------------------------------ local records

def _read_json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise RecordError(f"{path.name} is not valid JSON: {e}") from None
    if not isinstance(obj, dict):
        raise RecordError(f"{path.name} is {type(obj).__name__}, not a JSON object")
    return obj


def read_orders_jsonl(path: Path) -> dict:
    """{client_order_id: {"symbol", "side", "qty", "events": [...]}} from run.py's log.

    The log is an event stream (`quantt/session/run.py::_transmit`): a
    `submit` line carrying the wire fields is appended BEFORE each POST, then
    `accepted` / `ambiguous` / `lookup` / `lookup_error` / `error` / `confirm`
    lines carrying only the id. So the order's identity comes from its `submit`
    line, and every other line must name an id that has one -- an event for an
    order that was never recorded as submitted means the log is not the log of
    what went. Two `submit` lines for one id must agree: two different orders
    under one id would make the broker lookup meaningless.
    """
    out: dict[str, dict] = {}
    lines = []
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RecordError(f"orders.jsonl line {n} is not JSON: {e}") from None
        if not isinstance(rec, dict):
            raise RecordError(f"orders.jsonl line {n} is not a JSON object")
        missing = [k for k in ("event", "client_order_id") if k not in rec]
        if missing:
            raise RecordError(f"orders.jsonl line {n} lacks {missing}")
        lines.append((n, rec))
    for n, rec in lines:
        if rec["event"] != "submit":
            continue
        missing = [k for k in ("symbol", "side", "qty") if k not in rec]
        if missing:
            raise RecordError(f"orders.jsonl line {n} (submit) lacks {missing}")
        qty = rec["qty"]
        if type(qty) is not int or qty <= 0:
            raise RecordError(f"orders.jsonl line {n}: qty {qty!r} is not a positive int")
        if rec["side"] not in ("buy", "sell"):
            raise RecordError(f"orders.jsonl line {n}: side {rec['side']!r} is not buy|sell")
        cid = rec["client_order_id"]
        key = {"symbol": rec["symbol"], "side": rec["side"], "qty": qty}
        if cid in out and {k: out[cid][k] for k in key} != key:
            raise RecordError(f"orders.jsonl: {cid} submitted as both "
                              f"{ {k: out[cid][k] for k in key} } and {key}")
        out.setdefault(cid, {**key, "events": []})
    for n, rec in lines:
        cid = rec["client_order_id"]
        if cid not in out:
            raise RecordError(f"orders.jsonl line {n}: event {rec['event']!r} for {cid}, "
                              f"which has no submit line")
        ev = rec["event"]
        if ev in ("error", "ambiguous", "lookup_error") and "error" in rec:
            ev = f"{ev}: {rec['error']}"
        out[cid]["events"].append(ev)
    return out


# A no-trade day is EXPLAINED (PASS) only when a human chose it: DRY_RUN, no
# arming (no approval for that day and no AUTO_ARMED), or a halt. Any other
# refusal -- exposure, data, shortability, sanity, clock, a set already at the
# broker -- means the book should have traded and did not. That is a FAIL.
# WHY (team lead 2026-10-09): on 2026-10-09 the exposure gate refused both
# sends, and the verify line read "PASS cef no trade: refused at send: ...".
# Nobody saw it until the team lead asked how Friday went. A missed day must
# never read as a pass.
DELIBERATE_GATES = frozenset({"dry_run", "arming", "halt"})


def _missed(texts: list[str], where: str) -> str:
    return (f"MISSED: the book should have traded and did not: refused {where}: "
            + "; ".join(texts))


def _fit_emptied(fit, where: str) -> str | None:
    """Why the fit left no order, when it is what emptied a plan that had orders.

    WHY (release-check 2026-10-11, follow-up A). `run.fit_to_buying_power`
    scales a plan that does not fit to the most of it that does. When that is
    nothing at all, the session ends NOTHING_TO_SEND with no refusal, and
    verify read the day as "nothing left to send" -- a PASS. That is a missed
    day by the team lead's 2026-10-09 rule: only DRY_RUN, arming or a halt
    explains one, and a limit the plan was fitted to is none of them; it is an
    exposure refusal in all but name. `fit` is the run's `bp_scale` (plan.json,
    at decide) or `bp_scale_at_send` (send.json): {"binding", "orders_in",
    "orders_out", ...}, or None when no fit ran.
    """
    if fit is None:
        return None
    need = ("binding", "orders_in", "orders_out")
    if not isinstance(fit, dict) or any(k not in fit for k in need):
        raise RecordError(f"the {where} fit record {fit!r} is not a dict with {list(need)}")
    if fit["binding"] and fit["orders_in"] and not fit["orders_out"]:
        return f"the {where} fit to {fit['binding']} kept 0 of {fit['orders_in']} order(s)"
    return None


def _refusal_text(r) -> str:
    """run.py records a refusal as {"gate", "detail"}; anything else is refused."""
    if not (isinstance(r, dict) and isinstance(r.get("gate"), str)
            and isinstance(r.get("detail"), str)):
        raise RecordError(f"plan.json refusal {r!r} is not {{'gate': str, 'detail': str}}")
    return f"[{r['gate']}] {r['detail']}"


def no_trade_reason(plan: dict, day: dt.date, book: str) -> tuple[str | None, str | None]:
    """(why, None) when plan.json explains a day without STARTED, else (None, problem).

    plan.json is written by run.py on every non-crashing run that reaches the
    gates, and overwritten by later runs the same day until STARTED exists
    (`quantt/session/records.py`). Its fields read here: `book`,
    `session_date`, `mode` (run|preview), `orders`, `refusals`
    ([{"gate", "detail"}]). The explanation is the plan's own refusals, when one
    of them is a human's choice (DELIBERATE_GATES), or an empty order list. Any
    other refusal is a missed day: FAIL (2026-10-09). A plan that HAS orders and
    NO refusal but no STARTED is not an explanation either: either only a
    `--preview` ran (nothing was ever going to trade) or the session stopped
    between deciding and recording, the one place a crash is dangerous. Both
    are FAIL.
    """
    missing = [k for k in ("book", "session_date", "mode", "orders", "refusals") if k not in plan]
    if missing:
        return None, f"plan.json lacks {missing}, so it cannot say why nothing traded"
    if plan["session_date"] != day.isoformat() or plan["book"] != book:
        return None, (f"plan.json is for {plan['book']!r} {plan['session_date']!r}, "
                      f"not {book!r} {day.isoformat()!r}")
    refusals, orders = plan["refusals"], plan["orders"]
    if not isinstance(refusals, list):
        return None, "plan.json refusals is not a list"
    if not isinstance(orders, list):
        return None, "plan.json orders is not a list"
    texts = [_refusal_text(r) for r in refusals]
    if texts:
        if {r["gate"] for r in refusals} & DELIBERATE_GATES:
            return "refused: " + "; ".join(texts), None
        return None, _missed(texts, "when the plan was decided")
    if not orders:
        emptied = _fit_emptied(plan.get("bp_scale"), "decide-time")
        if emptied:
            return None, f"MISSED: the book should have traded and did not: {emptied}"
        return "the plan had no orders", None
    if plan["mode"] == "preview":
        return None, (f"only a --preview ran: plan.json has {len(orders)} order(s), no "
                      f"refusal, and no armed or dry run followed")
    return None, (f"plan.json has {len(orders)} order(s) and no refusal, but there is no "
                  f"STARTED: the session stopped between deciding and recording")


def late_no_trade_reason(plan: dict, send: dict | None, day: dt.date,
                         book: str) -> tuple[str | None, str | None]:
    """The late-market analogue of `no_trade_reason` (paper execution,
    2026-09-29). The DECIDE phase writes plan.json; the SEND phase writes
    send.json with its own refusals. A day with no STARTED is explained by the
    plan's refusals (not decided), an empty plan, or the send's refusals. A
    decided plan with orders and NO send record means no send ran in the window
    (machine asleep or offline): FAIL, saying so. A send refused by anything but
    a human's choice (DELIBERATE_GATES) is a missed day: FAIL (2026-10-09). So
    is a send left with nothing to send, every order skipped or scaled to zero
    by the send-time fit, and an empty plan the decide-time fit emptied
    (`_fit_emptied`, 2026-10-13)."""
    if plan.get("status") != "decided":
        return no_trade_reason(plan, day, book)
    if not plan.get("orders"):
        emptied = _fit_emptied(plan.get("bp_scale"), "decide-time")
        if emptied:
            return None, f"MISSED: the book should have traded and did not: {emptied}"
        return "the plan had no orders", None
    if send is None:
        return None, (f"plan decided with {len(plan['orders'])} order(s) but no send ran in "
                      f"the late window {plan.get('send_window')} (machine asleep or offline?)")
    refusals = send.get("refusals") or []
    texts = [_refusal_text(r) for r in refusals]
    if texts and {r["gate"] for r in refusals} & DELIBERATE_GATES:
        # Release-check #7: a halt, a dry run or the arming gate explains the
        # no-trade day, and every refusal (a budget one included) is listed.
        return "refused at send: " + "; ".join(texts), None
    if send.get("budget_short") and all(r["gate"] == "clock" for r in refusals):
        # Release-check #6: a set refused only because the window had too little
        # time left for it (gate.gate_late_send_budget).
        return None, f"MISSED: refused at send for time: {send['budget_short']}"
    if texts:
        return None, _missed(texts, "at send")
    if send.get("exit") == "NOTHING_TO_SEND":
        # A decided plan WITH orders that reached the send with nothing left to
        # send is a missed day (release-check 2026-10-11, follow-up A): every
        # order was either skipped (shortable turned false since decide: a
        # shortability refusal, name by name) or scaled to zero by the
        # send-time fit (an exposure limit; `_fit_emptied`). Neither is a
        # human's choice. Until 2026-10-13 this read "nothing left to send" and
        # PASSED. NOTHING_TO_SEND is only ever written when the send recorded
        # no refusal at all, so a dry run, arming or halt never reaches here.
        why = [f"skipped at send: {s}" for s in send.get("skipped") or []]
        emptied = _fit_emptied(send.get("bp_scale_at_send"), "send-time")
        if emptied:
            why.append(emptied)
        if not why:
            why.append("send.json names no skipped order and no fit that emptied the plan "
                       "(a send.json from before 2026-10-13 does not record the fit)")
        return None, (f"MISSED: the book should have traded and did not: nothing was left "
                      f"to send of the plan's {len(plan['orders'])} order(s): " + "; ".join(why))
    return None, f"send.json says {send.get('exit')!r} but there is no STARTED"


# ------------------------------------------------------------ broker helpers

def _whole(v, what: str) -> int:
    try:
        d = Decimal(str(v))
    except InvalidOperation:
        raise ValueError(f"{what} = {v!r} is not a number") from None
    if v is None or isinstance(v, bool) or d != d.to_integral_value():
        raise ValueError(f"{what} = {v!r} is not a whole number of shares")
    return int(d)


def _price(v, what: str) -> float:
    try:
        x = float(Decimal(str(v)))
    except InvalidOperation:
        raise ValueError(f"{what} = {v!r} is not a number") from None
    if v is None or isinstance(v, bool) or not x > 0:
        raise ValueError(f"{what} = {v!r} is not a positive price")
    return x


# A FILL activity that opens or increases a short says side "sell_short" while
# its ORDER says "sell" [V: measured 2026-09-30 and 10-01 on the cef account --
# JFR, MHD, MQY, PTY fills "sell_short", their orders "sell"]. The docs' buy|sell
# was wrong for activities, and verify crashed on both of the first two
# market-order days, so neither was scored. It is a sell for every purpose here
# (quantity sign, matching the order); only this one value is mapped, anything
# else still raises.
FILL_SIDE_ALIASES = {"sell_short": "sell"}


def parse_fill(a: dict) -> Fill:
    """An Alpaca FILL activity row -> Fill. Side must be buy|sell after the one
    measured alias above; any other value raises rather than being guessed."""
    w = f"fill {a.get('id')!r}"
    side = FILL_SIDE_ALIASES.get(a["side"], a["side"])
    if side not in ("buy", "sell"):
        raise ValueError(f"{w}: side {a['side']!r} is not buy|sell|sell_short")
    qty = _whole(a["qty"], f"{w} qty")
    if qty <= 0:
        raise ValueError(f"{w}: qty {a['qty']!r} is not positive")
    return Fill(symbol=a["symbol"], side=side, qty=qty,
                price=_price(a["price"], f"{w} price"), order_id=a["order_id"])


def fetch_prints(client, symbols, day: dt.date, *, condition: str) -> AuctionPrints:
    """One call per symbol, so one name's gap is recorded as that name's gap.

    ALWAYS filtered to the name's PRIMARY listing exchange (review 2026-09-28):
    asset `exchange` -> SIP code via the live /v2/stocks/meta/exchanges table
    (`AlpacaClient.primary_sip_code`). Another venue's official close is never
    "the auction print", even when every venue agrees; a primary with no print
    is a gap.

    Every client error on the market-data path (no print, no primary code, two
    primary prices, the data API refusing the key's plan) becomes the gap's
    reason, verbatim. That is not a fallback: the name is UNMEASURED and the
    day FAILs with the reason on the line.
    """
    from quantt.broker.alpaca import AlpacaError
    prices, gaps = {}, {}
    syms = sorted(set(symbols))
    try:
        exchanges = client.stock_exchanges()
    except AlpacaError as e:
        return AuctionPrints(prices={}, gaps={s: f"exchange-code table: {type(e).__name__}: {e}"
                                              for s in syms})
    for sym in syms:
        try:
            code = client.primary_sip_code(sym, exchanges)
            got = client.closing_auction_prints([sym], day, condition=condition,
                                                exchange_codes={sym: code})
        except AlpacaError as e:
            gaps[sym] = f"{type(e).__name__}: {e}"
            continue
        if sym not in got:
            raise ValueError(f"closing_auction_prints returned no row and no error for {sym}")
        prices[sym] = got[sym]["price"]
    return AuctionPrints(prices=prices, gaps=gaps)


def read_official(client, day: dt.date, prev: dt.date, as_of: dt.datetime) -> OfficialPnL:
    """D's official P&L from Alpaca's end-of-day history, or PENDING with the reason.

    A client error (the endpoint refusing, a shape the client will not parse,
    a stamp it cannot place on a session) is a PENDING reason naming it, never
    a FAIL: the team lead's ruling made this the P&L of record, not a
    condition of the day's verdict. Anything that is not an `AlpacaError` is a
    bug here and propagates (main() turns it into a FAIL line naming it).
    """
    from quantt.broker.alpaca import AlpacaError
    try:
        points = client.eod_equity_history(prev, day)
    except AlpacaError as e:
        return OfficialPnL(change=None, equity_d=None, equity_prev=None,
                           pending=f"Alpaca EOD history unreadable: {type(e).__name__}: {e}",
                           as_of=as_of.isoformat())
    return official_change(points, day=day, prev=prev, as_of=as_of)


def pnl_text(official: OfficialPnL, score: DayScore, read_at: dt.datetime) -> str:
    """The P&L half of the verdict line: official, snapshot, auction-marked, in that order."""
    off = (f"official {official.change:+.2f} USD (Alpaca EOD history, gross)" if official.measured
           else f"official {PENDING} ({official.pending})")
    snap = read_at.astimezone(ET).strftime("%H:%M")
    return (f"{off}; snapshot {snap} ET {score.alpaca_equity_change:+.2f} USD (gross); "
            f"auction-marked " + (f"{score.auction_pnl:+.2f} USD" if score.auction_pnl is not None
                                  else UNMEASURED) + " (gross)")


def _session_window(clk: dict, day: dt.date) -> str | None:
    """None if `day`'s session is over and the next has not opened; else why not."""
    now_et = clk["timestamp"].astimezone(ET)
    if now_et.date() != day:
        return (f"verify for {day} must run on {day} (ET) after the close; the Alpaca clock "
                f"says {now_et.isoformat()}, so equity and positions describe another session")
    if clk["is_open"]:
        return f"the market is still open at {now_et.isoformat()}; the auction has not happened"
    if clk["next_open"].astimezone(ET).date() <= day:
        return (f"{day}'s session has not opened yet (next open "
                f"{clk['next_open'].astimezone(ET).isoformat()})")
    return None


# ----------------------------------------------------------------- the day

def verify_day(client, state_dir: Path, book: str, day: dt.date | None = None, *,
               condition: str = "M") -> Verdict:
    """Reconcile and score one session. Reads the broker; writes nothing.

    `day` None means "the Alpaca clock's ET date" -- the broker's clock, not
    this machine's, decides which session is being verified.
    """
    clk = client.clock()
    read_at = clk["timestamp"].astimezone(ET).isoformat()
    if day is None:
        day = clk["timestamp"].astimezone(ET).date()
    day_dir = state_dir / day.isoformat()
    started = (day_dir / "STARTED").exists()

    def verdict(ok, reason, **kw):
        return Verdict(date=day, book=book, ok=ok, reason=reason, read_at=read_at,
                       condition=condition, traded=started, **kw)

    cal = client.calendar(day - dt.timedelta(days=PREV_SESSION_LOOKBACK_DAYS), day)
    sessions = sorted(r["date"] for r in cal)
    if day not in sessions:
        if started:
            return verdict(False, f"{day} is not a trading day per Alpaca /v2/calendar, "
                                  f"yet {day}/STARTED exists")
        return verdict(True, "not a trading day (Alpaca /v2/calendar has no session)")
    earlier = [d for d in sessions if d < day]
    if not earlier:
        raise ValueError(f"no trading day in the {PREV_SESSION_LOOKBACK_DAYS} days before "
                         f"{day} per Alpaca /v2/calendar")
    prev = earlier[-1]

    why_not_now = _session_window(clk, day)
    if why_not_now:
        return verdict(False, f"not verifiable now: {why_not_now}")

    problems: list[str] = []
    detail: dict = {"read_at": read_at, "prev_session": prev.isoformat(), "started": started}

    # --- local records --------------------------------------------------
    recorded: dict = {}
    why_no_trade = None
    if started:
        path = day_dir / "orders.jsonl"
        if not path.exists():
            problems.append("STARTED exists but orders.jsonl does not")
        else:
            # A malformed record is a named problem, not an abort: the broker
            # side of the reconcile and the score still run, and every order
            # Alpaca holds for D then shows up as "not in orders.jsonl".
            try:
                recorded = read_orders_jsonl(path)
            except RecordError as e:
                problems.append(str(e))
            else:
                if not recorded:
                    problems.append("STARTED exists but orders.jsonl holds no order")
    else:
        plan_path = day_dir / "plan.json"
        if not plan_path.exists():
            problems.append("no STARTED and no plan.json: the session left no record")
        else:
            try:
                plan_d = _read_json(plan_path)
                if plan_d.get("execution") == "late_market":
                    send_path = day_dir / "send.json"
                    why_no_trade, problem = late_no_trade_reason(
                        plan_d, _read_json(send_path) if send_path.exists() else None,
                        day, book)
                else:
                    why_no_trade, problem = no_trade_reason(plan_d, day, book)
            except RecordError as e:
                why_no_trade, problem = None, str(e)
            if problem:
                problems.append(problem)

    # --- orders at the broker ------------------------------------------
    prefix_d = f"{book}-{day:%Y%m%d}-"
    prefix_prev = f"{book}-{prev:%Y%m%d}-"
    # The NEXT auction's set can already be at Alpaca when verify runs: the
    # runner decides in the evening from 22:00 ET (team lead 2026-09-29), so a
    # verify re-run late on D sees the runner's own orders for D's successor.
    # They are the runner's, not foreign; they are scored on their own day.
    from ops.schedule.nyse_calendar import next_trading_day
    prefix_next = f"{book}-{next_trading_day(day):%Y%m%d}-"
    after = dt.datetime.combine(prev, dt.time(0, 0), tzinfo=ET)
    until = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0, 0), tzinfo=ET)
    window = client.orders(status="all", after=after, until=until)
    ours_listed = {o["client_order_id"]: o for o in window
                   if o["client_order_id"].startswith(prefix_d)}
    foreign = sorted(o["client_order_id"] for o in window
                     if not (o["client_order_id"].startswith(prefix_d)
                             or o["client_order_id"].startswith(prefix_prev)
                             or o["client_order_id"].startswith(prefix_next)))
    if foreign:
        problems.append(f"{len(foreign)} order(s) at Alpaca not placed by the runner: {foreign}")
    if not started and ours_listed:
        problems.append(f"no STARTED, yet Alpaca holds {sorted(ours_listed)} for {day}")
    unrecorded = sorted(set(ours_listed) - set(recorded))
    if started and unrecorded:
        problems.append(f"at Alpaca but not in orders.jsonl: {unrecorded}")

    orders_by_id: dict[str, dict] = {o["id"]: o for o in ours_listed.values()}
    order_rows = []
    n_filled = 0
    for cid in sorted(recorded):
        rec = recorded[cid]
        o = client.order_by_client_id(cid)
        row = {"client_order_id": cid, **rec, "status": None, "filled_qty": None,
               "filled_avg_price": None, "order_id": None}
        order_rows.append(row)
        if o is None:
            row["status"] = "NOT_AT_ALPACA"
            problems.append(f"{cid}: submitted per orders.jsonl but Alpaca has no such order "
                            f"(runner's events: {rec['events']})")
            continue
        if cid in ours_listed and ours_listed[cid]["id"] != o["id"]:
            problems.append(f"{cid}: by-client-id lookup gave order {o['id']}, the order "
                            f"list gave {ours_listed[cid]['id']}")
        orders_by_id[o["id"]] = o
        row.update(order_id=o["id"], status=o["status"], filled_qty=o["filled_qty"],
                   filled_avg_price=o.get("filled_avg_price"))
        if "qty" not in o:
            problems.append(f"{cid}: Alpaca's order has no qty field")
            continue
        broker_qty = _whole(o["qty"], f"{cid} qty")
        mism = [f"{k} {o[k]!r} vs recorded {rec[k]!r}" for k in ("symbol", "side")
                if o[k] != rec[k]]
        if broker_qty != rec["qty"]:
            mism.append(f"qty {broker_qty} vs recorded {rec['qty']}")
        if mism:
            problems.append(f"{cid}: Alpaca's order differs from the record: {', '.join(mism)}")
        fq = _whole(o["filled_qty"], f"{cid} filled_qty")
        if o["status"] == "filled" and fq == broker_qty:
            n_filled += 1
        else:
            problems.append(f"{rec['symbol']} {cid}: status {o['status']}, "
                            f"filled {fq}/{broker_qty}")

    # --- fills ----------------------------------------------------------
    raw_fills = client.activities_fills(day)
    fills = [parse_fill(a) for a in raw_fills]
    fill_qty_by_order: dict[str, int] = {}
    for f in fills:
        fill_qty_by_order[f.order_id] = fill_qty_by_order.get(f.order_id, 0) + f.qty
        o = orders_by_id.get(f.order_id)
        if o is None:
            problems.append(f"fill {f.side} {f.qty} {f.symbol} belongs to order {f.order_id}, "
                            f"which is not one of the runner's orders for {day}")
        elif o["symbol"] != f.symbol or o["side"] != f.side:
            problems.append(f"fill on order {f.order_id} is {f.side} {f.symbol}, the order is "
                            f"{o['side']} {o['symbol']}")
    for oid, o in orders_by_id.items():
        fq = _whole(o["filled_qty"], f"{o['client_order_id']} filled_qty")
        if fill_qty_by_order.get(oid, 0) != fq:
            problems.append(f"{o['client_order_id']}: Alpaca says filled_qty {fq}, the day's "
                            f"FILL activities sum to {fill_qty_by_order.get(oid, 0)}")

    # --- positions: the book held INTO D's close ------------------------
    after_pos = client.positions().qty
    net = {}
    for f in fills:
        net[f.symbol] = net.get(f.symbol, 0) + f.signed_qty()
    q0 = {s: after_pos.get(s, 0) - net.get(s, 0) for s in set(after_pos) | set(net)}
    q0 = {s: q for s, q in q0.items() if q != 0}

    acct = client.account()
    # The official figure (team lead 2026-10-19). Judged against this run's
    # clock read, which is earlier than the history read: a point stamped
    # between the two is called PENDING, which can delay a figure but never
    # passes an unfinished one.
    official = read_official(client, day, prev, clk["timestamp"])

    # --- auction prints and the score -----------------------------------
    need_d = set(q0) | {f.symbol for f in fills}
    prints_d = fetch_prints(client, need_d, day, condition=condition) if need_d \
        else AuctionPrints()
    prints_prev = fetch_prints(client, q0, prev, condition=condition) if q0 else AuctionPrints()
    score = score_day(held=q0, fills=fills, auction_d=prints_d, auction_prev=prints_prev,
                      equity=acct["equity"], last_equity=acct["last_equity"])

    detail.update({
        "orders": order_rows,
        "fills": raw_fills,
        "positions_after": after_pos,
        "held_into_close": q0,
        "auction_condition": condition,
        "auction_prints_d": {"prices": dict(prints_d.prices), "gaps": dict(prints_d.gaps)},
        "auction_prints_prev": {"prices": dict(prints_prev.prices), "gaps": dict(prints_prev.gaps)},
        "official_eod": {"source": OFFICIAL_SOURCE, "change_usd": official.change,
                         "equity_d": official.equity_d, "equity_prev": official.equity_prev,
                         "pending": official.pending, "as_of": official.as_of,
                         "points_read": official.points},
        "snapshot": {"equity": acct["equity"], "last_equity": acct["last_equity"],
                     "change_usd": score.alpaca_equity_change, "clock_read_at": read_at},
        "problems": problems,
    })

    pnl = pnl_text(official, score, clk["timestamp"])
    if score.fill_vs_auction_bp is not None:
        pnl += f"; fill vs auction {score.fill_vs_auction_bp:+.1f}bp (+ = worse)"
    head = (f"traded {len(recorded)} order(s), {n_filled} filled" if started
            else f"no trade: {why_no_trade}" if why_no_trade else "no trade")
    fails = problems + [f"{UNMEASURED} {u}" for u in score.unmeasured]
    reason = f"{head}; {pnl}" if not fails else "; ".join(fails) + f" | {head}; {pnl}"
    return verdict(not fails, reason, score=score, n_orders=len(recorded),
                   n_filled=n_filled, detail=detail, official=official)


# ------------------------------------------------------------------ writing

def _fmt(x) -> str:
    return UNMEASURED if x is None else f"{x:.2f}"


def score_row(v: Verdict) -> dict:
    s = v.score
    fills_exist = any(r["sides"] for r in s.per_symbol)
    return {
        "date": v.date.isoformat(), "book": v.book, "verdict": "PASS" if v.ok else "FAIL",
        "traded": str(v.traded), "n_orders": v.n_orders, "n_filled": v.n_filled,
        "alpaca_equity": f"{s.alpaca_equity:.2f}",
        "alpaca_last_equity": f"{s.alpaca_last_equity:.2f}",
        "alpaca_equity_change_usd": f"{s.alpaca_equity_change:.2f}",
        "auction_pnl_usd": _fmt(s.auction_pnl),
        "auction_hold_pnl_usd": _fmt(s.auction_hold_pnl),
        "auction_fill_pnl_usd": _fmt(s.auction_fill_pnl),
        "fill_vs_auction_bp": (_fmt(s.fill_vs_auction_bp) if fills_exist else "no fills"),
        "unmeasured": " | ".join(s.unmeasured),
        "auction_condition": v.condition, "cost_basis": COST_BASIS, "read_at": v.read_at,
        "per_symbol_json": json.dumps(s.per_symbol, sort_keys=True, separators=(",", ":")),
    }


def append_score(path: Path, row: dict) -> None:
    """Append one row; write the header only for a new file, and refuse a file
    whose header is not ours (appending under someone else's columns would
    shift every value into the wrong column without an error)."""
    new = not path.exists() or path.stat().st_size == 0
    if not new:
        with path.open(newline="") as fh:
            header = next(csv.reader(fh), None)
        if tuple(header or ()) != SCORES_COLUMNS:
            raise RecordError(f"{path} header {header} is not {list(SCORES_COLUMNS)}")
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SCORES_COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)


def write_outputs(state_dir: Path, v: Verdict) -> Verdict:
    """scores.csv row and reconcile.json first, the verify.log line LAST, so a
    PASS line never stands above records that failed to write. A write failure
    turns the verdict into a FAIL that names it; the line is still written."""
    try:
        if v.score is not None:
            append_score(state_dir / "scores.csv", score_row(v))
        if v.detail:
            day_dir = state_dir / v.date.isoformat()
            day_dir.mkdir(exist_ok=True)
            tmp = day_dir / "reconcile.json.tmp"
            tmp.write_text(json.dumps({"verdict": v.line(), **v.detail}, indent=2,
                                      sort_keys=True, default=str))
            tmp.replace(day_dir / "reconcile.json")
    except Exception as e:  # noqa: BLE001 -- converted into a FAIL line, never swallowed
        v.ok = False
        v.reason = f"could not write verify records: {type(e).__name__}: {e} | {v.reason}"
    # Daily TCA (quantt/session/tca.py), AFTER scores and reconcile.json so a TCA
    # failure can never cost those records (review 2026-10-07). Loud, not silent:
    # it turns the line FAIL naming it.
    if v.score is not None and v.detail and v.traded:
        try:
            from quantt.session import tca
            d = v.date.isoformat()
            tca.append(state_dir / "tca.csv",
                       tca.tca_row(d, v.book, v.detail, v.score.per_symbol,
                                   tca.plan_for(state_dir, d)))
        except Exception as e:  # noqa: BLE001 -- converted into a FAIL line, never swallowed
            v.ok = False
            v.reason = f"could not write tca.csv: {type(e).__name__}: {e} | {v.reason}"
    with (state_dir / "verify.log").open("a") as fh:
        fh.write(v.line() + "\n")
    return v


# --------------------------------------------------------------------- CLI

def _make_client(book: str):
    from quantt.broker.alpaca import AlpacaClient
    return AlpacaClient.from_environment(book)


def main(argv=None) -> int:
    """`python3 -m quantt.session verify --book cef [--date YYYY-MM-DD] [--condition M|6]`.

    `argv` may start with the word "verify" (as __main__ receives it) or not.
    Exit 0 PASS, 1 FAIL, 2 nowhere to write the line (QUANTT_STATE_DIR).
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["verify"]:
        argv = argv[1:]
    ap = argparse.ArgumentParser(prog="quantt.session verify", description=__doc__.split("\n")[0])
    ap.add_argument("--book", required=True)
    ap.add_argument("--date", type=dt.date.fromisoformat, default=None,
                    help="session date (default: the Alpaca clock's ET date)")
    ap.add_argument("--condition", choices=("M", "6"), default="M",
                    help="auction print condition: M = Official Close (default), 6 = Closing Trade")
    args = ap.parse_args(argv)

    sd = os.environ.get("QUANTT_STATE_DIR", "")
    if not sd:
        print("QUANTT_STATE_DIR is not set: there is nowhere to write the verdict", file=sys.stderr)
        return 2
    state_dir = Path(sd)
    if not state_dir.is_dir():
        print(f"QUANTT_STATE_DIR {state_dir} is not a directory", file=sys.stderr)
        return 2
    try:
        # C4's state dir must be named c4 (records.STATE_DIR_NAMES): its line, scores
        # and reconcile.json must never land in the core's verify.log. Nothing is
        # written, as for an unset QUANTT_STATE_DIR. No entry for the core.
        require_book_state_dir(args.book, state_dir)
    except StateDirError as e:
        print(str(e), file=sys.stderr)
        return 2

    client = None
    try:
        client = _make_client(args.book)
        v = verify_day(client, state_dir, args.book, args.date,
                       condition=args.condition)
    except Exception as e:  # noqa: BLE001 -- every failure becomes a FAIL line naming it
        # The date labels the line only. Without the broker's clock the best
        # label is this machine's ET date, and the line says it crashed.
        day = args.date or dt.datetime.now(ET).date()
        v = Verdict(date=day, book=args.book, ok=False,
                    reason=f"verify error: {type(e).__name__}: {e}")
    v = write_outputs(state_dir, v)
    print(v.line())
    if client is not None:
        # Each post-verdict hook is guarded on its own (review 2026-10-09): a failure
        # inside a hook's own error recording must not escape and turn a PASS day's
        # exit code into 1, nor stop the next hook. The verdict line is already
        # written; the error goes to stderr (the job log), naming the hook.
        for name, hook in (
                ("shadow", lambda: run_shadow(client, state_dir, v.date, condition=args.condition)),
                ("distributions", lambda: run_distributions(client, state_dir, v.date,
                                                            book=args.book))):
            try:
                hook()
            except Exception as e:  # noqa: BLE001 -- reported on stderr; the verdict stands
                print(f"{name} hook error (verdict unaffected): {type(e).__name__}: {e}",
                      file=sys.stderr)
    return 0 if v.ok else 1


def run_distributions(client, state_dir: Path, today: dt.date, *, book: str) -> None:
    """The distribution-adjusted third score (quantt/session/dist_score.py), after
    the verdict is written and never able to change it (team lead 2026-10-09:
    Alpaca paper credits no dividends, so carry a third line). It scores every
    session at least two sessions old that has no measured row yet, from that
    day's reconcile.json and scores.csv, so the yfinance cross-check has caught
    up (review 2026-10-09). A day it cannot measure is an UNMEASURED row, retried.
    Its second source is `book`'s own distributions panel (`dist_score.panel_for`:
    data/cef/ for the core, as always; data/cef_c4/ for C4, plan row 8)."""
    from ops.schedule.nyse_calendar import is_trading_day, next_trading_day, previous_trading_day
    from quantt.session import dist_score
    if not is_trading_day(today):
        return
    panel = dist_score.panel_for(book)
    now = dt.datetime.now(dt.timezone.utc)
    for d, status in dist_score.run_pending(client, state_dir, today, now_utc=now,
                                            previous_trading_day=previous_trading_day,
                                            next_trading_day=next_trading_day,
                                            panel_path=panel):
        print(f"distributions {d}: {status} USD ({dist_score.LABEL.split(':')[0]})")


def run_shadow(client, state_dir: Path, day: dt.date, *, condition: str) -> None:
    """The MODELLED shadow score (quantt/session/shadow.py), after the verdict is
    written and never able to change it (team lead 2026-09-29: keep cls, compare
    against the intended book at official closes for a week). A failure here is
    recorded as an UNMEASURED shadow row naming it -- not swallowed, not a FAIL
    of the real session."""
    from ops.schedule.nyse_calendar import is_trading_day, previous_trading_day
    from quantt.session import shadow
    now = dt.datetime.now(dt.timezone.utc)
    if not is_trading_day(day):
        return
    prev = previous_trading_day(day)

    def fetch(symbols, d):
        r = fetch_prints(client, symbols, d, condition=condition)
        return r.prices, r.gaps
    try:
        row = shadow.run_day(client, state_dir, day, fetch=fetch, prev=prev, now_utc=now)
        print(f"shadow {day}: {row['shadow_pnl_usd']} USD ({shadow.LABEL})")
    except Exception as e:  # noqa: BLE001 -- recorded as an UNMEASURED shadow row
        shadow.record_error(state_dir, day, prev, f"{type(e).__name__}: {e}", now)
        print(f"shadow {day}: UNMEASURED ({type(e).__name__}: {e})")


if __name__ == "__main__":
    raise SystemExit(main())
