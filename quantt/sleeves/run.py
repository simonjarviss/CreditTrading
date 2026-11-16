"""The event sleeves' order phase: PLAN before the close, SEND in the late window, VERIFY after it.

PAPER ONLY. This is the second caller of `AlpacaClient.submit_order` in the repository, and it
reaches it only through the core runner's own `_transmit` (quantt/session/run.py), behind the
core's own gates (quantt/session/gate.py). Nothing here re-implements a gate, the transmit loop,
the STARTED record or the plan hash: each of those carries an incident in its docstring, and a
second copy would be a second place to get it wrong. What IS new here is what the core has no
word for: several books in one account, so one plan per sleeve, one net order per symbol, and a
ledger that says who owns what (`net.py`, `ledger.py`).

THE THREE PHASES, AND WHY THREE (the core's paper exception, docs/RUNNER.md "Paper execution":
paper runs no closing auction and under-fills `cls`, so the plan is decided first and sent as
market `day` orders minutes before the close; CLAUDE.md order-path rule 3).

  PLAN    on session F, before the send window OPENS (a plan written while a send may be
          running could replace the plan that send loaded; see STARTED below). F and D come from
          Alpaca's clock and calendar (checked against the repo's NYSE calendar), never from a
          decision file. Reads the ledger and the account, refuses unless they agree share for
          share, reads each enabled sleeve's decision for as-of D, the closes of D and today's
          asset flags, and writes `<state>/<F>/plan.json`: one plan per sleeve, the net targets,
          the orders (`quantt.session.decide.decide`, whole shares, `day`) and their `plan_sha`.
          SENDS NOTHING. May be run again until the window opens or STARTED exists.
  SEND    inside the window. Loads the saved plan and never re-decides (what was approved is
          what goes), re-reads the account, and runs the core's gates on fresh reads. Only then
          STARTED is created, exclusively, BEFORE the first order (rule 2), and `_transmit` sends.
  VERIFY  after the close. Reconciles this runner's order log to the broker's orders and FILL
          activities, books the session into the ledger (`ledger.apply`), checks the new ledger
          against the broker's positions, and appends one score row per sleeve.

WHAT STOPS A SEND (every one a refusal; nothing is sent, no STARTED is written):
  DRY_RUN not exactly "0"; no approval for THIS plan_sha and no `<state>/AUTO_ARMED`; a halt
  (ops/HALT.md, ops/HALT_<book>.md, or a file `<state>/HALT`, which exists so the VM's operator
  can stop this one book without a commit); the Alpaca clock outside the window or too late for
  the set to finish; STARTED already there, any order at Alpaca with this book's id prefix for
  F, any open order, or an order list that could not be read; a short the account or the asset
  does not allow; a set that adds gross above the limit (below), Reg T, or buying power; a
  malformed order; positions that moved since the plan; a client whose trading endpoint is not
  the paper one.

WHAT IS BOOKED IS WHAT WAS SENT (review of stage 2, 2026-11-16). STARTED holds the whole plan
the send loaded and its `record_sha`, as the core's does. VERIFY refuses to book unless
plan.json still carries that record_sha and every order in the log is an order of that plan:
the reviewer ran a PLAN between a send's load and its STARTED, and VERIFY booked the shares
to the wrong sleeves from the newer file. `record_sha` covers everything SEND and VERIFY read
from the plan (sleeve plans, net targets, each target's `current`, closes, equity, positions,
and the hash of the ledger the plan was built on: VERIFY books only from that same ledger).

THE GROSS LIMIT AT SEND is the core's `max_gross_stress` rule (`gate.stress_breach`), with
`max_gross_x_equity` as the multiple: a set is refused only if the book after it is above the
multiple x the LOWER of the plan's equity and live equity AND the set adds gross. A plan that
takes gross down always goes. Judging the multiple as a hard ceiling on live equity refused
every set, de-grossing ones included, after any fall in equity since PLAN (the core's
2026-10-09 incident). Reg T and buying power stay hard checks on live numbers. NOT BUILT: the
core's send-time re-fit (`fit_to_buying_power`), so a set that ADDS gross and was sized exactly
at the limit is still refused if equity is lower at the send.

A HELD NAME WITH NO CLOSE on D (no daily bar: halted, delisted) is held by every sleeve that
owns it (`net.py`) and valued in the gross at the last close THIS RUNNER recorded for it: the
newest earlier session's verify marks, else that session's plan closes. It is written to
plan.json under `stale_closes` with where it came from, never mixed into `closes`. With no
recorded price at all the plan is refused, naming the symbol. No other source is consulted.

WHAT THE LEDGER NEEDS FROM THE OPERATOR. VERIFY must run after every session that has a plan.
PLAN refuses while an earlier session's plan has not been booked: its fills and crosses are not
in the ledger yet, and a plan built on that ledger would be sized on shares the sleeves do not
hold. If VERIFY cannot book a session (a foreign order, a position the fills do not explain) it
FAILs, writes no ledger, and the book stops until a person has repaired `ledger.json`.

PRICES. Every close is the daily bar's (`prices.py`). VERIFY marks at the daily-bar close of F,
NOT at the closing-auction print: the client's auction-print methods raise `UnmappedExchange`
for ARCA and TXSE listings (IWM is ARCA), and every special-dividend sleeve holds IWM. The
official close and the daily bar's close are the same number for most listings but that is not
checked here; the score file is this runner's attribution of the account's P&L between sleeves,
and the P&L of record stays Alpaca's end-of-day equity (team lead, 2026-10-19).

EXIT CODES are the core's (`quantt.session.run.EXIT_NAMES`) for plan and send, and the core
verify's for verify (0 PASS, 1 FAIL).
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from quantt.session import decide as dec
from quantt.session import gate as gt
from quantt.session import records as rec
from quantt.session.run import (EXIT_DRY, EXIT_FAIL, EXIT_IDLE, EXIT_NAMES, EXIT_NOTHING,
                                EXIT_PLANNED, EXIT_PREVIEW, EXIT_REFUSED, EXIT_SENT,
                                FINAL_ORDER_STATES, SessionError, _finish, _gate6_orders,
                                _gross_now, _nyse_trading, _transmit,
                                approval_for, asof_for, hard_to_borrow_short_opens,
                                load_decided_plan, order_table)
from quantt.session.verify import DELIBERATE_GATES, RecordError, _session_window, parse_fill
from quantt.sleeves import config, inputs, ledger, net, prices
from src.deploy.sleeve import EQUITY, FLAT, LONG, SHORT, PositionTarget

REPO = Path(__file__).resolve().parents[2]
BOOK_PATH = REPO / "ops" / "sleeves" / "events_sleeves.json"
PAPER_BASE = "https://paper-api.alpaca.markets"      # quantt.broker.alpaca.PAPER_BASE; pinned by a test
CALENDAR_LOOKBACK_DAYS = 14                          # as verify.PREV_SESSION_LOOKBACK_DAYS
VERIFY_PASS, VERIFY_FAIL = 0, 1
SCORES_COLUMNS = ("date", "slug", "shares_value", "cash", "pnl", "day_change", "n_names",
                  "equity_change", "residual")
BOOK_ROW = "_book"
_DAY_DIR = re.compile(r"\d{4}-\d{2}-\d{2}")
# orders.jsonl events `_transmit` writes for an order BEFORE its `submit` line, so they can
# name an id that was never submitted (the batch stopped there). `verify.read_orders_jsonl`
# raises on such a line; `recorded_orders` below accepts exactly these three.
PRE_SUBMIT_EVENTS = ("cutoff", "clock_error", "skipped_after_rejection")
# A recorded order Alpaca does not hold is expected only when the submit did not land.
NOT_AT_BROKER_OK = ("rejected", "ambiguous", "error")


class Refused(RuntimeError):
    """This runner will not go on; the message says what was measured. Nothing was sent."""


REFUSALS = (Refused, config.ConfigError, ledger.LedgerError, net.NetError, prices.PriceError,
            dec.DecisionError, SessionError, rec.StateDirError, RecordError)


def _repo_halts(book: str) -> list:
    """The global halt (ops/HALT.md) or this book's scoped one (ops/HALT_<book>.md)."""
    from ops.halt import read_halt
    h = read_halt(book)
    return [h] if h else []


@dataclass
class Deps:
    """Everything a phase touches outside itself; tests pass fakes. `utcnow` and `sleep` are
    also what the core's `_transmit` and `_poll_final` read from the object they are handed,
    and they read nothing else from it."""
    client: object
    env: dict
    state: Path
    utcnow: Callable[[], dt.datetime] = field(default=lambda: dt.datetime.now(dt.timezone.utc))
    out: object = field(default_factory=lambda: sys.stdout)
    book_path: Path = BOOK_PATH
    sleep: Callable[[float], None] = time.sleep
    halts: Callable[[str], list] = _repo_halts


# ------------------------------------------------------------------ shared reads

def _setup(deps: Deps):
    """(config, state dir). The state directory must exist and be named after the book: every
    book keeps <state>/<F>/STARTED and plan.json under the same names, so this runner pointed
    at the core's directory would read the core's STARTED as its own and write a ledger there
    (the reason for `records.STATE_DIR_NAMES`; checked here because that table is the core's)."""
    cfg = config.load(deps.book_path)
    state = Path(deps.state)
    if not state.is_dir():
        raise rec.StateDirError(f"state directory {state} does not exist; create it deliberately, "
                                "the runner will not")
    if state.name != cfg.book:
        raise rec.StateDirError(f"book {cfg.book!r} needs its own state directory, named "
                                f"{cfg.book!r}; {state} is not (another book's STARTED and "
                                "plan.json for the same session would be read as this one's)")
    return cfg, state


def _session(client, cfg):
    """(clock, F, D, F's calendar row, send window) from Alpaca's clock and calendar, or
    (clock, None, ...) when the clock's New York date is not a session. D is the session before
    F by BOTH Alpaca's calendar and the repo's NYSE calendar (`asof_for` raises if they differ)."""
    clk = client.clock()
    today = clk["timestamp"].astimezone(gt.ET).date()
    cal = client.calendar(today - dt.timedelta(days=CALENDAR_LOOKBACK_DAYS), today)
    rows = [r for r in cal if r["date"] == today]
    if len(rows) > 1:
        raise Refused(f"Alpaca calendar has {len(rows)} rows for {today}")
    if _nyse_trading(today) != bool(rows):
        raise Refused(f"calendars disagree on {today}: Alpaca rows={len(rows)}, nyse_calendar "
                      f"trading={_nyse_trading(today)}; not choosing one")
    if not rows:
        return clk, None, None, None, None
    asof = asof_for(today, cal)
    win = gt.late_window_et(today, rows[0]["close"], cfg.window_minutes_before_close)
    return clk, today, asof, rows[0], win


def decisions_dir(env) -> Path:
    v = env.get("QUANTT_SLEEVES_DECISIONS_DIR", "")
    if not v:
        raise Refused("QUANTT_SLEEVES_DECISIONS_DIR is not set: it must name the shadow state "
                      "directory holding <slug>/decisions/<asof>.json")
    p = Path(v).expanduser()
    if not p.is_dir():
        raise Refused(f"QUANTT_SLEEVES_DECISIONS_DIR={v} is not an existing directory")
    return p


def check_ledger(led, where: str) -> dict:
    """The ledger file's shape, checked before a share of it is trusted."""
    if not isinstance(led, dict) or led.get("version") != 1 or not isinstance(led.get("sleeves"), dict):
        raise ledger.LedgerError(f"{where} is not a version-1 ledger")
    s = led.get("session")
    if s is not None and not (isinstance(s, str) and _DAY_DIR.fullmatch(s)):
        raise ledger.LedgerError(f"{where}: session {s!r} is not a date or null")
    for slug, r in led["sleeves"].items():
        if not isinstance(r, dict) or not isinstance(r.get("shares"), dict):
            raise ledger.LedgerError(f"{where}: sleeve {slug} has no shares table")
        for sym, q in r["shares"].items():
            if type(q) is not int:
                raise ledger.LedgerError(f"{where}: {slug} holds {q!r} shares of {sym}: not a whole number")
        cash, stale = r.get("cash"), r.get("stale_sessions")
        if isinstance(cash, bool) or not isinstance(cash, (int, float)) or not math.isfinite(cash):
            raise ledger.LedgerError(f"{where}: sleeve {slug} cash {cash!r} is not a finite number")
        if type(stale) is not int or stale < 0:
            raise ledger.LedgerError(f"{where}: sleeve {slug} stale_sessions {stale!r} is not a count")
    return led


def read_ledger(state: Path, positions: dict) -> tuple:
    """(ledger, whether the file exists). An absent file is an empty ledger ONLY when the
    account holds nothing: with positions and no ledger nobody knows whose they are, and
    starting from empty would book them to no sleeve and trade on top of them."""
    p = state / "ledger.json"
    if not p.exists():
        held = {s: q for s, q in positions.items() if q != 0}
        if held:
            raise ledger.LedgerError(f"no {p} and the account holds {held}; an absent ledger is "
                                     "an empty one only for an empty account")
        return ledger.empty(), False
    return check_ledger(json.loads(p.read_text()), str(p)), True


def _unbooked_sessions(state: Path, led: dict, before: dt.date) -> list:
    """Earlier sessions that have a plan.json and are later than the ledger's last booked one."""
    out = []
    for d in sorted(state.iterdir()):
        if d.is_dir() and _DAY_DIR.fullmatch(d.name) and (d / "plan.json").exists() \
                and d.name < before.isoformat() and (led["session"] is None or d.name > led["session"]):
            out.append(d.name)
    return out


def asset_flags(client, symbols) -> dict:
    """{symbol: {listed, can_buy, can_short, ...}} read from /v2/assets today (landmine 5: true
    on its date only).

      can_buy    the asset is active and tradable.
      can_short  can_buy, and `shortable`, and `easy_to_borrow` exactly True, and a
                 `borrow_status`, when Alpaca sends one, that says easy_to_borrow.
    /v2/assets/{symbol} returns both `easy_to_borrow` (bool) and `borrow_status` [V 2026-11-16:
    the coordinator's GET-only read of IWM, MHD and PDI; not re-read by this module's author].
    An absent `easy_to_borrow` is NOT easy to borrow: Alpaca requires a locate for a
    hard-to-borrow short and paper has none, so such an order is rejected, and a field that was
    not sent is not a measurement. An asset Alpaca does not list is neither buyable nor
    shortable. Any other failure of the read raises: an unread flag is not a False one.
    """
    from quantt.broker.alpaca import AssetNotFound
    out = {}
    for s in sorted(set(symbols)):
        try:
            a = client.asset(s)
        except AssetNotFound:
            out[s] = {"listed": False, "can_buy": False, "can_short": False}
            continue
        can_buy = a["status"] == "active" and a["tradable"] is True
        easy = a.get("easy_to_borrow") is True and a.get("borrow_status", "easy_to_borrow") == "easy_to_borrow"
        out[s] = {"listed": True, "can_buy": can_buy,
                  "can_short": can_buy and a["shortable"] is True and easy,
                  "status": a["status"], "tradable": a["tradable"], "shortable": a["shortable"],
                  "easy_to_borrow": a.get("easy_to_borrow"), "borrow_status": a.get("borrow_status")}
    return out


def _target(sym: str, q: int) -> PositionTarget:
    """A net target as the qty-kind PositionTarget `decide` uses exactly as given (never
    re-derived through a price: decide.py, the dust-order incident)."""
    if q == 0:
        return PositionTarget(sym, FLAT, kind=EQUITY, reason="sleeves net flat")
    return PositionTarget(sym, LONG if q > 0 else SHORT, kind=EQUITY, qty=q, reason="sleeves net target")


SHA_FIELDS = ("book", "session_date", "asof", "equity", "positions", "closes", "stale_closes",
              "ledger_sha", "sleeves", "net_targets", "targets", "plan_sha")


def ledger_sha(led: dict) -> str:
    """Hash of a whole ledger: who holds what, each sleeve's cash and stale count, the session.
    PLAN records the ledger it was built on; VERIFY books only from that same ledger. The
    broker check compares TOTALS per symbol, so shares moved from one sleeve to another between
    PLAN and VERIFY would pass it and be booked to the wrong owner; this does not."""
    return hashlib.sha256(json.dumps(led, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _record_sha(record: dict) -> str:
    """Hash of everything SEND and VERIFY read from a plan besides the orders: the sleeve
    plans and net targets VERIFY books from, each target's `current` (SEND's moved-positions
    check), the closes and equity the gates value the book on, and the positions VERIFY
    reconciles to, bound to the orders' plan_sha. `plan_sha` covers only what is transmitted,
    so two sets of sleeve plans that net to the same orders hash alike there. Every value is
    JSON-native, so the hash is the same before the file is written and after it is read."""
    missing = [k for k in SHA_FIELDS if k not in record]
    if missing:
        raise Refused(f"the plan lacks {missing}; it is not a plan this runner wrote")
    payload = json.dumps({k: record[k] for k in SHA_FIELDS}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def last_recorded_close(state: Path, sym: str, before: dt.date):
    """The newest close THIS RUNNER recorded for `sym` in a session before `before`, as
    {"price", "session", "source"}, or None. Looked for, newest session first, in that
    session's verify.json marks (its own close) and then its plan.json closes (the close of
    the session before it). A stale price in an older plan is never passed on: only `closes`
    and `marks` are read, and both hold daily-bar closes only."""
    for d in sorted((x for x in state.iterdir() if x.is_dir() and _DAY_DIR.fullmatch(x.name)
                     and x.name < before.isoformat()), reverse=True):
        for name, key in (("verify.json", "marks"), ("plan.json", "closes")):
            f = d / name
            if not f.exists():
                continue
            v = (json.loads(f.read_text()).get(key) or {}).get(sym)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0:
                return {"price": float(v), "session": d.name, "source": f"{d.name}/{name} {key}"}
    return None


def load_plan(day: Path, session_date: dt.date, book: str) -> tuple:
    """(plan, orders): the core's `load_decided_plan` checks (decided, for this date, orders
    still hash to plan_sha, all `day`), then this runner's: the book, and the sleeve plans
    still hash to `record_sha`. A hand-edited plan is never sent and never booked."""
    plan, orders = load_decided_plan(day, session_date)
    if plan.get("book") != book:
        raise Refused(f"{day / 'plan.json'} is book {plan.get('book')!r}'s, not {book!r}'s")
    want = _record_sha(plan)
    if plan.get("record_sha") != want:
        raise Refused(f"{day / 'plan.json'}: its sleeve plans hash to {want}, the file says "
                      f"{plan.get('record_sha')}; refusing a plan that is not what was decided")
    return plan, orders


def _stamp(deps: Deps) -> str:
    return deps.utcnow().strftime("%Y%m%dT%H%M%SZ")


def _guard(fn, deps: Deps, mode: str, fail_code: int = EXIT_FAIL, refused_code: int = EXIT_REFUSED) -> int:
    """Run one phase. A named refusal prints REFUSED; anything else prints FAIL with its
    traceback. Neither is swallowed: the exit code is non-zero and the line names the cause."""
    try:
        return fn()
    except REFUSALS as e:
        print(f"REFUSED {mode}: {type(e).__name__}: {e}", file=deps.out)
        return refused_code
    except Exception as e:  # noqa: BLE001 -- reported with its traceback, exit FAIL
        print(f"FAIL {mode}: {type(e).__name__}: {e}", file=deps.out)
        print(traceback.format_exc(), file=deps.out)
        return fail_code


# ------------------------------------------------------------------------ PLAN

def sleeve_table(sleeves: list) -> str:
    rows = [f"{'sleeve':<28}{'action':<9}{'names':>6}{'stale':>6}  detail"]
    for s in sleeves:
        d = s["decision"]
        detail = s["why"] or (f"decision {d['sha256'][:12]} written {d['written_at']}" if "sha256" in d else "")
        if s["dropped"]:
            detail += f"; blocked legs {s['dropped']} scale {s['scale']}"
        rows.append(f"{s['slug']:<28}{s['action']:<9}{len(s['targets']):>6}{s['stale_sessions']:>6}  {detail}")
    return "\n".join(rows)


def plan(deps: Deps, *, preview: bool = False) -> int:
    """PLAN (module docstring). `preview` prints the plan and writes nothing."""
    return _guard(lambda: _plan(deps, preview), deps, "plan")


def _plan(deps: Deps, preview: bool) -> int:
    cfg, state = _setup(deps)
    c, out = deps.client, deps.out
    stamp = _stamp(deps)
    clk, F, D, cal_row, win = _session(c, cfg)
    now = clk["timestamp"].astimezone(gt.ET)
    if F is None:
        print(f"{cfg.book} PLAN: {now.date()} is not a trading day; nothing to plan", file=out)
        print(f"exit {EXIT_IDLE} {EXIT_NAMES[EXIT_IDLE]}", file=out)
        return EXIT_IDLE
    if now >= win[0]:
        raise Refused(f"Alpaca clock {now:%Y-%m-%d %H:%M:%S} ET is at or past the send window's start "
                      f"{win[0]:%H:%M} ET; a plan written now could replace the one a send has loaded")
    day = state / F.isoformat()
    if (day / "STARTED").exists():
        raise Refused(f"a set already STARTED for {F}; its plan is never overwritten")
    acct = c.account()
    pos = c.positions().qty
    led, led_present = read_ledger(state, pos)
    if led["session"] is not None and led["session"] >= F.isoformat():
        raise Refused(f"the ledger is already booked to {led['session']}; VERIFY has run for {F}")
    unbooked = _unbooked_sessions(state, led, F)
    if unbooked:
        raise Refused(f"VERIFY has not booked {unbooked} (ledger booked to {led['session']}); a "
                      "plan built on this ledger would be sized on shares the sleeves do not hold")
    ledger.check_against_broker(led, pos)

    enabled = [s.slug for s in cfg.sleeves if s.enabled]
    decs = inputs.read(decisions_dir(deps.env), enabled, D, F)
    held = set(ledger.totals(led)) | {s for s, q in pos.items() if q != 0}
    named = {sym for d in decs.values() for sym in d.get("weights", {})}
    symbols = sorted(held | named)
    # ALIGNMENT: sized on the close of D, the session strictly before F (asof_for); `closes`
    # raises on a bar dated anything else.
    assert D < F, (D, F)
    cl = prices.closes(c, symbols, D) if symbols else {}
    # A held name with no bar on D (module docstring): its sleeves hold, and it is valued at
    # the last close this runner recorded, kept apart from `closes` and labelled.
    stale = {}
    for sym in sorted(held - set(cl)):
        got = last_recorded_close(state, sym, F)
        if got is None:
            raise Refused(f"{sym} is held, has no daily bar on {D}, and this runner has recorded no "
                          "close for it in any earlier session; it cannot be valued, so nothing is planned")
        stale[sym] = got
    valued = {**{s: v["price"] for s, v in stale.items()}, **cl}
    flags = asset_flags(c, symbols)
    plans = net.plan_sleeves(cfg, decs, ledger.shares_of(led),
                             {slug: r["stale_sessions"] for slug, r in led["sleeves"].items()}, cl,
                             lambda s: flags[s]["can_short"], lambda s: flags[s]["can_buy"])
    plans, factor, gross = net.apply_limits(cfg, plans, valued, acct["equity"], frozen=stale)
    nt = net.net_targets(plans)
    universe = sorted(held | set(nt))
    shortable = {s: flags[s]["can_short"] for s in universe}
    decision = dec.decide([_target(s, nt.get(s, 0)) for s in universe], pos, acct["equity"], cl,
                          shortable, session_date=F, universe=universe, cid_prefix=cfg.book,
                          min_trade_usd=cfg.min_order_usd, time_in_force="day")
    orders = decision.orders
    if len(orders) > cfg.max_orders:
        raise Refused(f"the plan holds {len(orders)} orders, above max_orders {cfg.max_orders}; "
                      "nothing is planned (the send window fits about a hundred)")
    # The broker-facing gates on the plan as it stands, SHOWN and recorded, not enforced: SEND
    # judges them on fresh reads, and a plan refused here would leave VERIFY nothing to book.
    would = [*gt.gate_shortability(orders, pos, shortable, acct["shorting_enabled"]),
             *gt.gate_exposure(orders, pos, valued, acct["equity"], acct["buying_power"],
                               math.inf, cfg.max_gross_x_equity,
                               sized_equity=acct["equity"], current_gross=_gross_now(acct),
                               maintenance_margin=acct["maintenance_margin"]),
             *gt.gate_sanity(orders, universe, pos, cfg.book, F,
                             {k: acct[k] for k in ("trading_blocked", "account_blocked",
                                                   "trade_suspended_by_user")})]
    sleeves = [{"slug": p.slug, "action": p.action, "why": p.why, "targets": p.targets,
                "stale_sessions": p.stale_sessions, "dropped": list(p.dropped), "scale": p.scale,
                "decision": ({k: decs[p.slug][k] for k in ("sha256", "written_at")}
                             if "weights" in decs.get(p.slug, {})
                             else {"missing": decs.get(p.slug, {}).get("missing", "not read: disabled in the book file")})}
               for p in plans]
    record = {
        "book": cfg.book, "execution": "late_market", "status": "decided",
        "session_date": F.isoformat(), "asof": D.isoformat(), "decided_utc": deps.utcnow(),
        "send_window": [win[0].isoformat(), win[1].isoformat()],
        "equity": acct["equity"], "positions": pos, "closes": cl, "stale_closes": stale,
        "assets": flags,
        "ledger_present": led_present, "ledger_session": led["session"], "ledger_sha": ledger_sha(led),
        "sleeves": sleeves, "gross_factor": factor, "gross_usd": gross, "net_targets": nt,
        "targets": decision.targets, "notes": decision.notes,
        "dropped_shorts": list(decision.dropped_shorts),
        "orders": [o.to_dict() for o in orders], "plan_sha": decision.plan_sha,
        "would_refuse_at_send": [{"gate": r.gate, "detail": r.detail} for r in would],
    }
    record["record_sha"] = _record_sha(record)
    print(f"{cfg.book} PLAN {F} (as-of {D}), equity ${acct['equity']:,.2f}, gross after "
          f"${gross:,.2f} (limit {cfg.max_gross_x_equity} x equity, factor {factor:.4f}), "
          f"window {win[0]:%H:%M}-{win[1]:%H:%M} ET", file=out)
    print(sleeve_table(sleeves), file=out)
    print(order_table(orders), file=out)
    print(f"plan_sha {decision.plan_sha}", file=out)
    for sym, v in stale.items():
        print(f"  STALE PRICE {sym}: no daily bar on {D}; held, and valued at {v['price']} from {v['source']}", file=out)
    for sym, ns in sorted(decision.notes.items()):
        for n in ns:
            if not n.startswith("no trade: target equals holding"):
                print(f"  NOTE {sym}: {n}", file=out)
    for w in hard_to_borrow_short_opens(orders, pos, flags):
        print(f"  WARNING {w}", file=out)
    for r in would:
        print(f"  WOULD REFUSE AT SEND {r}", file=out)
    if preview:
        print(f"exit {EXIT_PREVIEW} {EXIT_NAMES[EXIT_PREVIEW]} (nothing written)", file=out)
        return EXIT_PREVIEW
    day = rec.day_dir(state, F)
    # Checked again at the write, on a fresh clock read: the reads above can take minutes, and
    # a SEND that may have loaded the old plan meanwhile must keep the plan it sent.
    late = c.clock()["timestamp"].astimezone(gt.ET)
    if late >= win[0]:
        raise Refused(f"the send window opened ({late:%H:%M:%S} ET) while this plan was being built; "
                      "not written")
    if (day / "STARTED").exists():
        raise Refused(f"a set STARTED for {F} while this plan was being built; not overwritten")
    rec.write_json_atomic(day / "plan.json", record)
    return _finish({"mode": "plan", "plan_sha": decision.plan_sha, "session_date": F, "asof": D},
                   day, stamp, "plan", EXIT_PLANNED, out)


# ------------------------------------------------------------------------ SEND

def _state_halt(state: Path, book: str) -> list:
    """`<state>/HALT`: the operator's stop for this one book on the machine it runs on."""
    p = state / "HALT"
    if not p.exists():
        return []
    text = p.read_text().strip()
    return [{"scope": book, "reason": (text.splitlines()[0] if text else "state-directory HALT file"),
             "path": str(p)}]


def send(deps: Deps, *, preview: bool = False) -> int:
    """SEND (module docstring). `preview` runs every read and gate and sends nothing."""
    return _guard(lambda: _send(deps, preview), deps, "send")


def _send(deps: Deps, preview: bool) -> int:
    cfg, state = _setup(deps)
    c, out = deps.client, deps.out
    stamp = _stamp(deps)
    clk, F, D, cal_row, win = _session(c, cfg)
    if F is None:
        raise Refused(f"{clk['timestamp'].astimezone(gt.ET).date()} is not a trading day; nothing is sent")
    # BEFORE THE WINDOW IS NOT A REFUSAL (2026-11-16). The timers fire SEND at the early-close
    # slots (12:41, 12:46) every day, because the unit cannot know the day's close; on a normal
    # day those runs are hours early. Refusing there marked the unit failed daily and wrote a
    # REFUSED send.json that VERIFY would read as a missed day if the real send never ran. So a
    # send that finds the Alpaca clock before the window's start says so, writes NOTHING and
    # exits IDLE. `--preview` still runs every read and gate, so a person can see them early.
    if not preview and clk["timestamp"] < win[0]:
        print(f"{cfg.book} SEND {F}: {clk['timestamp'].astimezone(gt.ET):%H:%M:%S} ET is before the send "
              f"window ({win[0]:%H:%M}-{win[1]:%H:%M} ET); nothing read, nothing written", file=out)
        print(f"exit {EXIT_IDLE} {EXIT_NAMES[EXIT_IDLE]}", file=out)
        return EXIT_IDLE
    day = state / F.isoformat()
    plan_d, orders = load_plan(day, F, cfg.book)
    if plan_d["asof"] != D.isoformat():
        raise Refused(f"the plan's as-of {plan_d['asof']} is not the session before {F} ({D})")
    record = {"mode": "send", "plan_sha": plan_d["plan_sha"], "session_date": F, "asof": D}
    acct = c.account()
    pos = c.positions().qty
    universe = sorted(plan_d["targets"])
    flags = asset_flags(c, universe)
    shortable = {s: flags[s]["can_short"] for s in universe}
    record.update(account={k: v for k, v in acct.items() if k != "raw"}, positions=pos)
    # The plan was sized on these holdings; if they moved, it is not the plan any more.
    moved = {s: {"plan": t["current"], "now": pos.get(s, 0)}
             for s, t in plan_d["targets"].items() if pos.get(s, 0) != t["current"]}
    # A name whose flags flipped since PLAN (landmine 5) is skipped and the rest go, as the
    # core does (team lead 2026-09-28: "skip that name, send the rest"). Arming still binds to
    # the PLANNED sha: what goes is a subset of what was approved. The sleeve that wanted the
    # skipped leg keeps its other side for this session, unscaled; VERIFY books what filled and
    # tomorrow's PLAN re-scales it (net.py, "WHEN A LEG CANNOT BE OPENED").
    skipped, keep = [], []
    for o in orders:
        cur = pos.get(o.symbol, 0)
        if not flags[o.symbol]["can_buy"]:
            skipped.append(f"{o.client_order_id}: {o.symbol} is not an active, tradable asset at "
                           "send; skipped, the rest go")
        elif o.side == "sell" and cur - o.qty < 0 and shortable[o.symbol] is not True:
            skipped.append(f"{o.client_order_id}: {o.symbol} is not shortable and easy to borrow "
                           "at send; skipped, the rest go")
        else:
            keep.append(o)
    orders = tuple(keep)
    record["skipped_at_send"] = skipped
    # Stale prices value a held, unpriced name in the gates only; no order is ever in one.
    closes = {**{s: float(v["price"]) for s, v in plan_d["stale_closes"].items()},
              **{k: float(v) for k, v in plan_d["closes"].items()}}
    approve_sha = approval_for(day)
    started_before = (day / "STARTED").exists()
    # Gate 6's lists: the last broker read before the gate's clock read (`_gate6_orders`).
    midnight = dt.datetime.combine(D - dt.timedelta(days=1), dt.time(0), tzinfo=gt.ET)
    orders_recent, orders_open, orders_unread = _gate6_orders(c, midnight)
    clock_gate = c.clock()
    record["clock_at_gate"] = clock_gate["timestamp"]
    budget_short = gt.gate_late_send_budget(clock_gate["timestamp"], win, len(orders))
    refusals = [
        *gt.gate_dry_run(deps.env.get("DRY_RUN")),
        *gt.gate_arming(approve_sha, plan_d["plan_sha"], (state / "AUTO_ARMED").exists()),
        *gt.gate_halt([*deps.halts(cfg.book), *_state_halt(state, cfg.book)]),
        *gt.gate_late_clock(clock_gate["timestamp"], F, [cal_row], _nyse_trading(F), win),
        *budget_short,
        *gt.gate_no_set_in_auction(started_before, orders_recent, orders_open,
                                   cfg.book, F, unread=orders_unread),
        *gt.gate_shortability(orders, pos, shortable, acct["shorting_enabled"]),
        # The gross limit is the core's stress rule on the multiple (module docstring, THE
        # GROSS LIMIT AT SEND); there is no separate dollar ceiling in the book file, so
        # `max_gross_usd` is infinite and Reg T is the hard limit on live equity.
        *gt.gate_exposure(orders, pos, closes, acct["equity"], acct["buying_power"],
                          math.inf, cfg.max_gross_x_equity,
                          sized_equity=float(plan_d["equity"]), current_gross=_gross_now(acct),
                          maintenance_margin=acct["maintenance_margin"]),
        *gt.gate_sanity(orders, universe, pos, cfg.book, F,
                        {k: acct[k] for k in ("trading_blocked", "account_blocked",
                                              "trade_suspended_by_user")}),
    ]
    if moved:
        refusals.append(gt.Refusal("sanity", f"positions moved since the plan was decided: {moved}"))
    endpoint = getattr(c, "trading_endpoint", None)
    if endpoint != PAPER_BASE:
        refusals.append(gt.Refusal("sanity", f"the client's trading endpoint is {endpoint!r}, not "
                                             f"the paper endpoint {PAPER_BASE}; this runner is paper only"))
    record["refusals"] = [{"gate": r.gate, "detail": r.detail} for r in refusals]
    print(f"{cfg.book} SEND {F} (plan decided on as-of {plan_d['asof']}), equity "
          f"${acct['equity']:,.2f}, window {win[0]:%H:%M}-{win[1]:%H:%M} ET", file=out)
    print(order_table(orders), file=out)
    print(f"plan_sha {plan_d['plan_sha']}", file=out)
    for x in skipped:
        print(f"  SKIPPED {x}", file=out)
    for r in refusals:
        print(f"  REFUSED {r}", file=out)
    if preview:
        print(f"exit {EXIT_PREVIEW} {EXIT_NAMES[EXIT_PREVIEW]} (nothing written)", file=out)
        return EXIT_PREVIEW

    def outcome(code):
        # VERIFY reads this to tell a day a person chose not to trade from a missed one.
        # A run that found STARTED already there is a RETRY of a set that went: it must not
        # replace that set's send.json with its own refusal (VERIFY would then FAIL a clean
        # day as "the send ended REFUSED"). Its own record is still kept under runs/.
        if started_before:
            return _finish(record, day, stamp, "send", code, out)
        rec.write_json_atomic(day / "send.json", {
            "session_date": F, "plan_sha": plan_d["plan_sha"], "at": stamp,
            "exit": EXIT_NAMES[code], "refusals": record["refusals"], "skipped": skipped,
            "sent": record.get("sent", []), "rejected": record.get("rejected", []),
            "final": record.get("final", {}), "unfilled": record.get("unfilled", {}),
            "not_final": record.get("not_final", []),
            "transmit_failure": record.get("transmit_failure"),
            "budget_short": "; ".join(r.detail for r in budget_short) or None})
        return _finish(record, day, stamp, "send", code, out)

    gates_hit = {r.gate for r in refusals}
    if refusals:
        return outcome(EXIT_DRY if ("dry_run" in gates_hit and gates_hit <= {"dry_run", "arming"})
                       else EXIT_REFUSED)
    if not orders:
        return outcome(EXIT_NOTHING)
    started = {"plan_sha": plan_d["plan_sha"], "session_date": F, "pid": os.getpid(),
               "written_utc": deps.utcnow(), "execution": "late_market", "book": cfg.book,
               "record_sha": plan_d["record_sha"],
               "client_order_ids": [o.client_order_id for o in orders], "plan": plan_d}
    # Rule 2: the record that a set started exists BEFORE the first order, exclusively.
    if not rec.create_exclusive(day / "STARTED", started):
        print("  REFUSED [no_set_in_auction] STARTED appeared between gate and record", file=out)
        return _finish(record, day, stamp, "send", EXIT_REFUSED, out)
    hh, mm = map(int, cal_row["close"].split(":"))
    poll_until = dt.datetime.combine(F, dt.time(hh, mm), tzinfo=gt.ET) - dt.timedelta(seconds=30)
    code = _transmit(c, orders, day / "orders.jsonl", record, deps, out,
                     in_window=lambda ts: win[0] <= ts < win[1],
                     window_text=f"late-market window {win[0]:%Y-%m-%d %H:%M}-{win[1]:%H:%M} ET",
                     poll_until=poll_until)
    return outcome(code)


# --------------------------------------------------------------------- APPROVE

def approve(deps: Deps, *, sha: str | None = None, date: dt.date | None = None) -> int:
    """Record the team lead's go for ONE decided plan (`<F>/APPROVED`, read by SEND through the
    core's `approval_for`): the core's `approve_main` mechanism. Prints the order table first.
    Without `sha` it prints the table and the sha and approves NOTHING: the go is for a list
    the team lead has seen, so the sha they saw is given back (CLAUDE.md order-path rule 1).
    Reads no broker; `date` defaults to today's New York date on this machine's clock, and a
    wrong clock can only refuse (the plan must exist for that date and hash to the sha)."""
    return _guard(lambda: _approve(deps, sha, date), deps, "approve")


def _approve(deps: Deps, sha, date) -> int:
    cfg, state = _setup(deps)
    out = deps.out
    F = date or deps.utcnow().astimezone(gt.ET).date()
    day = state / F.isoformat()
    if (day / "STARTED").exists():
        raise Refused(f"a set already STARTED for {F}; nothing to approve")
    plan_d, orders = load_plan(day, F, cfg.book)
    print(f"{cfg.book} plan for {F} (as-of {plan_d['asof']}), decided on equity ${plan_d['equity']:,.2f}", file=out)
    print(sleeve_table(plan_d["sleeves"]), file=out)
    print(order_table(orders), file=out)
    print(f"plan_sha {plan_d['plan_sha']}", file=out)
    if sha is None:
        print(f"NOT APPROVED: to approve this list, run approve --date {F} --sha {plan_d['plan_sha']}", file=out)
        return EXIT_PREVIEW
    if sha != plan_d["plan_sha"]:
        raise Refused(f"plan for {F} is {plan_d['plan_sha']}, not {sha}")
    rec.write_json_atomic(day / "APPROVED", {"plan_sha": sha, "session_date": F,
                                             "approved_utc": deps.utcnow(), "orders": len(orders)})
    print(f"APPROVED {F} plan_sha {sha} ({len(orders)} orders); it is sent in the window "
          f"{plan_d['send_window'][0]} -> {plan_d['send_window'][1]} if every gate passes", file=out)
    return 0


# ---------------------------------------------------------------------- VERIFY

def recorded_orders(path: Path) -> dict:
    """{client_order_id: {symbol, side, qty, events}} from `_transmit`'s log: the orders this
    runner TRIED to send (a `submit` line is written before each POST).

    Not `verify.read_orders_jsonl`, for one reason: that reader raises on any event whose id
    has no submit line, and `_transmit` writes `cutoff`, `clock_error` and
    `skipped_after_rejection` BEFORE the submit line of the order it stopped at. A batch cut
    off by the window would then be an unreadable log, VERIFY could not book the orders that
    did go, and the book would stop. Those three events are accepted for an unsubmitted id;
    every other check is the core reader's."""
    rows = rec.read_jsonl(path)
    out: dict = {}
    for n, r in enumerate(rows, 1):
        if not isinstance(r, dict) or "event" not in r or "client_order_id" not in r:
            raise RecordError(f"orders.jsonl line {n} lacks event or client_order_id")
        if r["event"] != "submit":
            continue
        key = {k: r.get(k) for k in ("symbol", "side", "qty")}
        if type(key["qty"]) is not int or key["qty"] <= 0 or key["side"] not in ("buy", "sell") \
                or not isinstance(key["symbol"], str):
            raise RecordError(f"orders.jsonl line {n}: submit {key} is not a whole-share order")
        cid = r["client_order_id"]
        if cid in out and {k: out[cid][k] for k in key} != key:
            raise RecordError(f"orders.jsonl: {cid} submitted as two different orders")
        out.setdefault(cid, {**key, "events": []})
    for n, r in enumerate(rows, 1):
        cid, ev = r["client_order_id"], r["event"]
        if cid in out:
            out[cid]["events"].append(ev)
        elif ev not in PRE_SUBMIT_EVENTS:
            raise RecordError(f"orders.jsonl line {n}: event {ev!r} for {cid}, which has no submit line")
    return out


def _last_pnl(path: Path) -> dict:
    """{slug: the pnl cell of its latest row}; refuses a file whose header is not ours."""
    if not path.exists() or path.stat().st_size == 0:
        return {}
    with path.open(newline="") as fh:
        rd = csv.DictReader(fh)
        if tuple(rd.fieldnames or ()) != SCORES_COLUMNS:
            raise RecordError(f"{path} header {rd.fieldnames} is not {list(SCORES_COLUMNS)}")
        rows = list(rd)
    return {r["slug"]: r for r in rows}


def _f(x) -> str:
    return "" if x is None else f"{x:.4f}"


def score_rows(day: dt.date, new: dict, marks: dict, last: dict, equity_change) -> tuple:
    """(rows, unmarked): one row per sleeve and the book row, marked at `day`'s closes.

    pnl = cash + shares at the marks (ledger.pnl's definition); day_change is against that
    sleeve's previous row, zero-based for a sleeve's first row (its cash starts at zero). A
    sleeve holding a symbol with no close that day gets EMPTY numbers, never another day's
    price, and so does its next row's day_change. The book row sums the sleeves and sets
    them against the change in account equity (Alpaca's `equity - last_equity`, a snapshot
    read at verify; empty when verify runs on a later day): the residual is what the
    ledger does not attribute (dividends, fees, and after-hours marks; ledger.py)."""
    rows, unmarked, tot = [], {}, {"sv": 0.0, "cash": 0.0, "pnl": 0.0, "chg": 0.0}
    whole = True
    for slug, r in sorted(new["sleeves"].items()):
        held = {s: q for s, q in r["shares"].items() if q != 0}
        miss = sorted(s for s in held if s not in marks)
        if miss:
            unmarked[slug] = miss
            sv = pnl = chg = None
        else:
            sv = sum(q * marks[s] for s, q in held.items())
            pnl = r["cash"] + sv
            prev = last.get(slug)
            chg = pnl if prev is None else (pnl - float(prev["pnl"]) if prev["pnl"] != "" else None)
        if sv is None or chg is None:
            whole = False
        else:
            tot["sv"] += sv; tot["cash"] += r["cash"]; tot["pnl"] += pnl; tot["chg"] += chg
        rows.append({"date": day.isoformat(), "slug": slug, "shares_value": _f(sv), "cash": _f(r["cash"]),
                     "pnl": _f(pnl), "day_change": _f(chg), "n_names": len(held),
                     "equity_change": "", "residual": ""})
    names = len({s for r in new["sleeves"].values() for s, q in r["shares"].items() if q != 0})
    rows.append({"date": day.isoformat(), "slug": BOOK_ROW,
                 "shares_value": _f(tot["sv"] if whole else None), "cash": _f(tot["cash"] if whole else None),
                 "pnl": _f(tot["pnl"] if whole else None), "day_change": _f(tot["chg"] if whole else None),
                 "n_names": names, "equity_change": _f(equity_change),
                 "residual": _f(equity_change - tot["chg"] if whole and equity_change is not None else None)})
    return rows, unmarked


def _append_scores(path: Path, rows: list) -> bool:
    """Append the rows unless rows for that date are already there (a re-run after a crash)."""
    new = not path.exists() or path.stat().st_size == 0
    if not new:
        with path.open(newline="") as fh:
            rd = csv.DictReader(fh)
            if tuple(rd.fieldnames or ()) != SCORES_COLUMNS:
                raise RecordError(f"{path} header {rd.fieldnames} is not {list(SCORES_COLUMNS)}")
            if any(r["date"] == rows[0]["date"] for r in rd):
                return False
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SCORES_COLUMNS)
        if new:
            w.writeheader()
        w.writerows(rows)
        fh.flush()
        os.fsync(fh.fileno())
    return True


def verify(deps: Deps, *, date: dt.date | None = None) -> int:
    """VERIFY (module docstring). `date` books an EARLIER session that was missed (its fills by
    date, its own closes); the equity comparison is then left empty, because the account's
    equity now is not that day's."""
    return _guard(lambda: _verify(deps, date), deps, "verify", VERIFY_FAIL, VERIFY_FAIL)


def _verify(deps: Deps, date) -> int:
    cfg, state = _setup(deps)
    c, out = deps.client, deps.out
    clk = c.clock()
    today = clk["timestamp"].astimezone(gt.ET).date()
    F = date or today
    if F > today:
        raise Refused(f"{F} is after the Alpaca clock's date {today}")
    day = state / F.isoformat()
    if not [r for r in c.calendar(F, F) if r["date"] == F]:
        if (day / "plan.json").exists():
            raise Refused(f"{F} is not a trading day on Alpaca's calendar, yet {day / 'plan.json'} exists")
        print(f"{F} PASS {cfg.book} not a trading day; nothing to verify", file=out)
        return VERIFY_PASS
    late = F < today
    if not late:
        why = _session_window(clk, F)
        if why:
            raise Refused(f"not verifiable now: {why}")
    if not (day / "plan.json").exists():
        raise Refused(f"no plan.json for {F}: PLAN left no record, so there is nothing to book; "
                      "the ledger is unchanged")
    plan_d, plan_orders = load_plan(day, F, cfg.book)
    started = (day / "STARTED").exists()

    # --- which ledger this session is booked FROM -----------------------------
    pos = c.positions().qty
    led_path = state / "ledger.json"
    led_now = check_ledger(json.loads(led_path.read_text()), str(led_path)) if led_path.exists() else None
    resumed = led_now is not None and led_now["session"] == F.isoformat()
    if resumed:
        if (day / "verify.json").exists() and json.loads((day / "verify.json").read_text()).get("ledger_applied"):
            v = json.loads((day / "verify.json").read_text())
            print(f"{F} {'PASS' if v['ok'] else 'FAIL'} {cfg.book} already verified; the ledger is "
                  f"booked to {F} and nothing was changed ({v['reason']})", file=out)
            return VERIFY_PASS if v["ok"] else VERIFY_FAIL
        # The ledger was written and the run died before verify.json: book again from the
        # kept copy and require the same answer.
        if not (day / "ledger_before.json").exists():
            raise Refused(f"the ledger is booked to {F} but {day / 'ledger_before.json'} is missing")
        before = check_ledger(json.loads((day / "ledger_before.json").read_text()), "ledger_before.json")
    elif led_now is None:
        if plan_d["ledger_present"]:
            raise Refused(f"{led_path} is missing, and the plan for {F} was built on a ledger file")
        before = ledger.empty()
    else:
        before = led_now
        if before["session"] is not None and before["session"] > F.isoformat():
            raise Refused(f"the ledger is booked to {before['session']}, after {F}")
    unbooked = _unbooked_sessions(state, before, F)
    if unbooked:
        raise Refused(f"earlier session(s) {unbooked} are not booked; verify them first, oldest first")
    # The plan was built on exactly this ledger (`ledger_sha`): sleeve by sleeve, not only in total.
    if ledger_sha(before) != plan_d["ledger_sha"]:
        raise Refused(f"the ledger this session would be booked from is not the one the plan for {F} was "
                      "built on (its hash differs); it was changed after PLAN, so nothing is booked")

    problems, fails, notes = [], [], []

    # --- this runner's orders, and the broker's ------------------------------
    recorded = {}
    if started:
        # What is booked is what was sent (module docstring): the plan on disk must be the
        # plan STARTED recorded, and every order in the log one of its orders.
        st = json.loads((day / "STARTED").read_text())
        if st.get("record_sha") != plan_d["record_sha"]:
            problems.append(f"STARTED was written for the plan with record_sha {st.get('record_sha')}, and "
                            f"plan.json now holds {plan_d['record_sha']}: the plan on disk is not the plan "
                            "that was sent")
        if not (day / "orders.jsonl").exists():
            notes.append("STARTED exists and orders.jsonl does not: no order was attempted")
        else:
            recorded = recorded_orders(day / "orders.jsonl")
        planned = {o.client_order_id: (o.symbol, o.side, o.qty) for o in plan_orders}
        for cid, r in sorted(recorded.items()):
            if planned.get(cid) != (r["symbol"], r["side"], r["qty"]):
                problems.append(f"{cid}: orders.jsonl records {r['side']} {r['qty']} {r['symbol']}, which is "
                                f"not an order of the plan ({planned.get(cid)})")
    prefix = f"{cfg.book}-{F:%Y%m%d}-"
    after = dt.datetime.combine(F, dt.time(0, 0), tzinfo=gt.ET)
    window = c.orders(status="all", after=after, until=after + dt.timedelta(days=1))
    by_id = {}
    for o in window:
        cid = o["client_order_id"]
        if cid not in recorded:
            ours = "carries this book's id prefix but " if cid.startswith(prefix) else ""
            problems.append(f"order {cid!r} ({o['side']} {o['symbol']}, {o['status']}) is at Alpaca for {F} and "
                            f"{ours}is not in this runner's orders.jsonl")
        else:
            by_id[o["id"]] = o
    order_rows = []
    for cid in sorted(recorded):
        r = recorded[cid]
        o = c.order_by_client_id(cid)
        row = {"client_order_id": cid, **r, "status": None, "filled_qty": None, "order_id": None}
        order_rows.append(row)
        if o is None:
            row["status"] = "NOT_AT_ALPACA"
            if not any(e in NOT_AT_BROKER_OK for e in r["events"]):
                problems.append(f"{cid}: submitted per orders.jsonl but Alpaca has no such order (events {r['events']})")
            continue
        by_id[o["id"]] = o
        row.update(order_id=o["id"], status=o["status"], filled_qty=o["filled_qty"])
        if o["symbol"] != r["symbol"] or o["side"] != r["side"]:
            problems.append(f"{cid}: Alpaca's order is {o['side']} {o['symbol']}, the record {r['side']} {r['symbol']}")
        if o["status"] not in FINAL_ORDER_STATES:
            problems.append(f"{cid}: status {o['status']!r} is not final; its fills are not all known yet")
        elif int(float(o["filled_qty"])) != r["qty"]:
            fails.append(f"{r['symbol']} {cid}: {o['status']}, filled {o['filled_qty']}/{r['qty']}")

    # --- fills ----------------------------------------------------------------
    raw_fills = c.activities_fills(F)
    qty_by_order, agg = {}, {}
    for a in raw_fills:
        f = parse_fill(a)
        o = by_id.get(f.order_id)
        if o is None:
            problems.append(f"fill {f.side} {f.qty} {f.symbol} on {F} belongs to order {f.order_id}, which is "
                            "not one of this runner's recorded orders")
            continue
        if o["symbol"] != f.symbol or o["side"] != f.side:
            problems.append(f"fill on order {f.order_id} is {f.side} {f.symbol}, the order is {o['side']} {o['symbol']}")
            continue
        qty_by_order[f.order_id] = qty_by_order.get(f.order_id, 0) + f.qty
        q, usd = agg.get(f.symbol, (0, 0.0))
        agg[f.symbol] = (q + f.signed_qty(), usd + f.qty * f.price)
    for oid, o in by_id.items():
        if qty_by_order.get(oid, 0) != int(float(o["filled_qty"])):
            problems.append(f"{o['client_order_id']}: Alpaca says filled_qty {o['filled_qty']}, the day's FILL "
                            f"activities sum to {qty_by_order.get(oid, 0)}")
    fills = {s: (q, usd / abs(q)) for s, (q, usd) in agg.items() if q != 0}

    # --- every position change is one of these fills --------------------------
    was = plan_d["positions"]
    for s in sorted(set(was) | set(pos) | set(fills)):
        want = was.get(s, 0) + fills.get(s, (0, None))[0]
        if pos.get(s, 0) != want:
            problems.append(f"{s}: position {pos.get(s, 0):+d}, but the plan's {was.get(s, 0):+d} and the "
                            f"day's fills {fills.get(s, (0, None))[0]:+d} give {want:+d}")

    # --- why nothing went, when nothing went ----------------------------------
    send_d = json.loads((day / "send.json").read_text()) if (day / "send.json").exists() else None
    if started:
        if send_d is None:
            fails.append("STARTED exists and send.json does not: the send did not finish")
        elif send_d.get("exit") != EXIT_NAMES[EXIT_SENT]:
            fails.append(f"the send ended {send_d.get('exit')}: {send_d.get('transmit_failure')}")
        head = f"sent {len(recorded)} order(s)"
    elif not plan_orders:
        head = "nothing to send"
    elif send_d is None:
        head = "no trade"
        fails.append(f"MISSED: the plan held {len(plan_orders)} order(s) and no send ran in the window")
    else:
        gates = {r["gate"] for r in send_d.get("refusals", [])}
        head = f"no trade: send ended {send_d.get('exit')}"
        if not (gates and gates <= DELIBERATE_GATES):
            fails.append(f"MISSED: the plan held {len(plan_orders)} order(s); send ended {send_d.get('exit')}: "
                         + ("; ".join(r["detail"] for r in send_d.get("refusals", []))
                            or f"skipped {send_d.get('skipped')}"))
        else:
            notes.append("not sent by choice: " + "; ".join(sorted(gates)))

    read_at = clk["timestamp"].astimezone(gt.ET).isoformat()

    def finish(ok, reason, **extra):
        rec.write_json_atomic(day / "verify.json", {
            "session_date": F, "book": cfg.book, "ok": ok, "reason": reason, "read_at": read_at,
            "late": late, "started": started, "orders": order_rows, "fills": raw_fills,
            "positions_after": pos, "problems": problems, "fails": fails, "notes": notes,
            "ledger_applied": False, **extra})
        print(f"{F} {'PASS' if ok else 'FAIL'} {cfg.book} {reason}", file=out)
        return VERIFY_PASS if ok else VERIFY_FAIL

    if problems:
        return finish(False, "; ".join(problems) + " | the ledger was NOT booked; repair it before the next plan")

    # --- book the session ------------------------------------------------------
    plans = [net.SleevePlan(s["slug"], s["action"], s["why"], dict(s["targets"]), s["stale_sessions"],
                            tuple(s["dropped"]), s["scale"]) for s in plan_d["sleeves"]]
    syms = sorted(set(ledger.totals(before)) | {s for p in plans for s in p.targets} | set(pos) | set(fills))
    # Marks and cross prices are F's own closes; a symbol with no bar on F has none.
    marks = prices.closes(c, syms, F) if syms else {}
    try:
        new, bookings = ledger.apply(before, plans, fills, marks, F.isoformat())
        ledger.check_against_broker(new, pos)
    except ledger.LedgerError as e:
        problems.append(str(e))
        return finish(False, f"{e} | the ledger was NOT booked; repair it before the next plan")
    if resumed and new != led_now:
        problems.append("booking again from ledger_before.json does not give the ledger on disk")
        return finish(False, problems[-1] + " | nothing was changed")
    equity_change = None
    acct = None
    if not late:
        acct = c.account()
        equity_change = acct["equity"] - acct["last_equity"]
    rows, unmarked = score_rows(F, new, marks, _last_pnl(state / "sleeve_scores.csv"), equity_change)
    for slug, miss in unmarked.items():
        fails.append(f"{slug} holds {miss} with no close on {F}: not scored (never marked at another day's price)")

    if not resumed:
        rec.write_json_atomic(day / "ledger_before.json", before)
        rec.write_json_atomic(led_path, new)
    wrote = _append_scores(state / "sleeve_scores.csv", rows)
    n_cross = sum(1 for b in bookings if b["kind"] == "cross")
    reason = (f"{head}; {len(fills)} symbol(s) filled, {len(bookings)} booking(s) ({n_cross} crossed inside the "
              f"account); ledger booked to {F}")
    if fails:
        reason = "; ".join(fails) + " | " + reason
    rec.write_json_atomic(day / "verify.json", {
        "session_date": F, "book": cfg.book, "ok": not fails, "reason": reason, "read_at": read_at,
        "late": late, "started": started, "orders": order_rows, "fills": raw_fills,
        "fills_by_symbol": {s: {"shares": q, "avg_price": p} for s, (q, p) in fills.items()},
        "bookings": bookings, "positions_after": pos, "marks": marks, "marks_source":
        "Alpaca daily bar close (1Day, raw, sip); not the closing-auction print",
        "equity": None if acct is None else {"equity": acct["equity"], "last_equity": acct["last_equity"],
                                             "change_usd": equity_change, "kind": "snapshot at verify"},
        "scores": rows, "scores_appended": wrote, "problems": problems, "fails": fails, "notes": notes,
        "ledger_applied": True})
    print(f"{F} {'PASS' if not fails else 'FAIL'} {cfg.book} {reason}", file=out)
    return VERIFY_PASS if not fails else VERIFY_FAIL


# ------------------------------------------------------------------------- CLI

def default_deps(env, *, need_client: bool = True) -> Deps:
    """The real dependencies. The client is the paper client for the book file's account
    (keys ALPACA_<BOOK>_KEY_ID / _SECRET_KEY in the file QUANTT_ENV_FILE names; this module
    never reads that file itself). The state directory is QUANTT_STATE_DIR, required."""
    state = rec.state_dir_from_env(env)
    client = None
    if need_client:
        from quantt.broker.alpaca import AlpacaClient
        if not env.get("QUANTT_ENV_FILE"):
            raise Refused("QUANTT_ENV_FILE is not set: it must name the key file")
        client = AlpacaClient.from_environment(config.load(BOOK_PATH).book)
    return Deps(client=client, env=dict(env), state=state)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python3 -m quantt.sleeves",
                                 description="The event sleeves' paper runner (paper only).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, text in (("plan", "decide today's plan; sends nothing"),
                       ("send", "send the saved plan inside the late window, if every gate passes")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--preview", action="store_true", help="print only; write and send nothing")
    p = sub.add_parser("verify", help="after the close: reconcile, book the ledger, score the sleeves")
    p.add_argument("--date", type=dt.date.fromisoformat, default=None,
                   help="an earlier session that was missed (default: the Alpaca clock's date)")
    p = sub.add_parser("approve", help="show a decided plan; with --sha, record the team lead's go for it")
    p.add_argument("--date", type=dt.date.fromisoformat, default=None)
    p.add_argument("--sha", default=None)
    a = ap.parse_args(argv)
    fail = VERIFY_FAIL if a.cmd == "verify" else EXIT_FAIL
    try:
        deps = default_deps(os.environ, need_client=a.cmd != "approve")
    except Exception as e:  # noqa: BLE001 -- named, exit non-zero
        print(f"FAIL before {a.cmd} could start: {type(e).__name__}: {e}")
        return fail
    if a.cmd == "plan":
        return plan(deps, preview=a.preview)
    if a.cmd == "send":
        return send(deps, preview=a.preview)
    if a.cmd == "verify":
        return verify(deps, date=a.date)
    return approve(deps, sha=a.sha, date=a.date)
