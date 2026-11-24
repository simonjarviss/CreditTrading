"""The nine pre-transmit gates (docs/RUNNER.md "The gates"). Pure: facts in, refusals out.

WHY PURE
--------
Every gate here stands between an automated job and an order that cannot be
taken back (CLAUDE.md order-path rule 2: the trade phase is not idempotent and
the broker does not dedupe). A gate that reads the clock, the disk or the broker
itself can only be tested against whatever the machine happens to say today. So
`run.py` measures every fact once, records it, and hands it here in `GateFacts`;
each gate is a function of those facts alone and is tested refusal by refusal
(`tests/test_gate.py`).

`evaluate` runs ALL nine and returns every refusal, never just the first: a
shadow session must show everything that would have stopped it, and the
operator fixing one refusal should not discover the next one tomorrow.

Each refusal carries the gate's name (`Refusal.gate`, one of `GATES`) and a
sentence saying what was measured. Any refusal means nothing is sent.

TIME
----
Every wall-clock comparison is done in America/New_York, converted from
Alpaca's `/v2/clock` timestamp (RFC-3339 with an offset [V]). Alpaca's
`/v2/calendar` `open`/`close` are "HH:MM" with NO documented timezone [U]; this
module reads them as America/New_York, the exchange's zone. That is an
assumption, stated here and in the refusal text, and it errs only one way: if
the calendar were in another zone the computed cutoff would be wrong by whole
hours, and the fixed 15:45 ET ceiling still applies regardless.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

GATES = ("dry_run", "arming", "halt", "clock", "data", "no_set_in_auction",
         "shortability", "exposure", "sanity",
         # run.py THE FIRST-SESSION GATE (C4; release-check of 4f759a9, execution-trader 1):
         # its own name, outside verify's DELIBERATE_GATES, so an armed day it refuses is
         # scored a MISSED day, not an explained one. Raised only by run.py, never by
         # `evaluate`.
         "first_session")

# Gate 4. Alpaca: "CLS orders submitted after 3:50pm but before 7:00pm ET will
# be rejected" [V, docs "orders-at-alpaca"]; 15:45 leaves five minutes (RUNNER.md).
CLS_CUTOFF_ET = dt.time(15, 45)
# Early-close days: no Alpaca page documents the cls cutoff [U]. RUNNER.md's
# own margin: the calendar's close minus ten minutes.
EARLY_CLOSE_MARGIN = dt.timedelta(minutes=10)
# The EVENING side of the window (team lead 2026-09-29: decide in the evening,
# once the day's NAVs are in, with a morning backstop). Alpaca: "CLS orders
# submitted after 3:50pm but before 7:00pm ET will be rejected. CLS orders
# submitted after 7:00pm will be queued and routed to the following day's
# closing auction" [V, docs "orders-at-alpaca"]. 19:15 leaves fifteen minutes
# after Alpaca's line, as 15:45 leaves five before 15:50. So an order for the
# auction on date S may be sent from 19:15 ET on the previous trading day
# (the as-of date) until the cutoff on S; outside that window it would be
# rejected, or -- worse -- queued into an auction nobody decided for.
# Whether paper honours the queue exactly as documented is [U] until the first
# evening send is confirmed at Alpaca.
QUEUE_OPEN_ET = dt.time(19, 15)

# Gate 8. Alpaca values a market short order at "(3% above the current ask
# price) * order quantity" for buying power [V, docs "orders-at-alpaca"]. The
# runner has no ask before the open; it applies the 3% to the as-of close, an
# ESTIMATE, recorded as such.
SHORT_ORDER_BP_MULTIPLIER = 1.03


@dataclass(frozen=True)
class Refusal:
    gate: str
    detail: str

    def __post_init__(self):
        if self.gate not in GATES:
            raise ValueError(f"unknown gate {self.gate!r}")

    def __str__(self) -> str:
        return f"[{self.gate}] {self.detail}"


@dataclass(frozen=True)
class GateFacts:
    """Everything the gates read, measured once by run.py. No field has a default
    that could stand in for a measurement."""
    # 1-2
    env_dry_run: str | None          # os.environ.get("DRY_RUN"): None when unset
    approve_sha: str | None          # --approve value, or None
    auto_armed: bool                 # <state>/AUTO_ARMED exists
    plan_sha: str
    # 3
    halts: list                      # the non-None results of ops.halt.read_halt(...)
    # 4
    clock_ts: dt.datetime            # Alpaca /v2/clock timestamp (aware)
    session_date: dt.date            # the auction the orders are for (ET)
    calendar_today: list             # Alpaca /v2/calendar rows whose date == session_date
    nyse_trading_today: bool         # ops/schedule/nyse_calendar.is_trading_day(session_date)
    # 5
    asof: dt.date
    refresh_exit: int | None         # fetch_daily exit code; None = --skip-refresh
    close_dates: dict                # symbol -> date of the close used (universe)
    nav_dates: dict                  # symbol -> date of the last finite, positive NAV <= as-of
    # 6
    started_exists: bool
    orders_recent: list | None       # Alpaca orders (status=all) since 00:00 ET the day before the as-of date
    orders_open: list | None         # Alpaca orders (status=open), any age; both None only with orders_unread
    cid_prefix: str
    # 7
    orders: tuple                    # decide.Order, the list that would be sent
    positions: dict                  # {symbol: signed int} from Alpaca
    shortable: dict                  # {symbol: bool} from /v2/assets today
    shorting_enabled: bool           # account.shorting_enabled
    # 8
    closes: dict                     # symbol -> as-of close
    equity: float                    # Alpaca's equity now (the live margin checks)
    sized_equity: float              # the equity the plan was sized on (the stress cap):
                                     # = equity at decide; the plan's own "equity" at send
    buying_power: float              # Alpaca's live `buying_power` (the order-time check)
    current_gross: float             # long_market_value + |short_market_value| now
    maintenance_margin: float        # Alpaca's maintenance_margin now (measured ratio)
    max_gross_usd: float             # spec risk.max_gross_exposure_usd
    max_gross_stress: float | None   # spec frozen.max_gross_stress (None = key absent)
    # 9
    universe: tuple
    account_flags: dict              # trading_blocked, account_blocked, trade_suspended_by_user
    # 5, per sleeve (quantt/session/combine.py; dark). None, the default, is the
    # single-sleeve book: gate 5 reads `universe` exactly as before. Set only by
    # the combiner: {sleeve: its universe} for every enabled sleeve, and whether
    # this decide is at or after the final check (nav_gate.final_check_at),
    # which gate_data_by_sleeve requires as a bool, never assumes.
    sleeve_universes: dict | None = None
    data_final: bool | None = None
    # 5, the missing-NAV hold (book json `data.missing_nav`; dark, team lead
    # 2026-10-29). None, the default, is gate 5 exactly as above. Set only by
    # run.py when the book json sets it, together with `data_final` and the
    # frozen spec's `min_names` (gate_data_missing_nav).
    missing_nav: str | None = None
    min_names: int | None = None
    # ... and its age limit (team lead 2026-10-29, a policy: book json
    # data.missing_nav_max_sessions) with, per name whose NAV is not dated
    # as-of, the consecutive prior sessions it went without one, read by run.py
    # from <state>/<session>/plan.json (`run.missing_nav_streaks`), or why that
    # count could not be read. Both None unless missing_nav is set.
    missing_nav_max_sessions: int | None = None
    missing_nav_held_before: dict | None = None
    # 6, a failed read (review 2026-10-29). None, the default: both order lists
    # were read, as the last broker read before the gate's clock read
    # (`run._gate6_orders`), and gate 6 judges them. Otherwise why that read
    # failed; both lists are then None and gate 6 refuses (gate_no_set_in_auction).
    orders_unread: str | None = None


# ----------------------------------------------------------------- the gates

def gate_dry_run(env_dry_run) -> list[Refusal]:
    """Gate 1. Transmit only if DRY_RUN is EXACTLY the string "0". Unset, empty,
    "1", "false", " 0", anything else is dry. A human hard halt that always
    wins (CLAUDE.md order-path rule 4), so it fails closed on every spelling
    nobody meant as "go"."""
    if env_dry_run == "0":
        return []
    shown = "unset" if env_dry_run is None else repr(env_dry_run)
    return [Refusal("dry_run", f"DRY_RUN is {shown}; only exactly '0' transmits")]


def gate_arming(approve_sha, plan_sha, auto_armed: bool) -> list[Refusal]:
    """Gate 2. `--approve <sha>` must equal the freshly recomputed plan_sha (what
    was approved is what is sent), OR `<state>/AUTO_ARMED` exists (created by
    the team lead after the first go). A WRONG --approve refuses even when
    AUTO_ARMED exists: someone approving a specific list and getting a
    different one is exactly the mistake this gate is for."""
    if approve_sha is not None:
        if approve_sha == plan_sha:
            return []
        return [Refusal("arming", f"--approve {approve_sha} does not match the recomputed "
                                  f"plan_sha {plan_sha}; the order list changed since it "
                                  f"was approved")]
    if auto_armed:
        return []
    return [Refusal("arming", "not armed: no --approve <plan_sha> and no <state>/AUTO_ARMED")]


def gate_halt(halts) -> list[Refusal]:
    """Gate 3. Any active halt (global ops/HALT.md or this book's scoped file) refuses."""
    return [Refusal("halt", f"halt active ({h.get('scope')}): {h.get('reason')} "
                            f"[{h.get('path')}]") for h in halts if h]


def cutoff_et(session_date: dt.date, calendar_close: str) -> dt.datetime:
    """The last moment (ET) a cls order may be sent on `session_date`:
    min(15:45 ET, calendar close - 10 min). The calendar close is read as ET
    (see module docstring: Alpaca does not document its zone)."""
    if not re.fullmatch(r"\d{2}:\d{2}", calendar_close or ""):
        raise ValueError(f"calendar close {calendar_close!r} is not HH:MM")
    hh, mm = map(int, calendar_close.split(":"))
    close = dt.datetime.combine(session_date, dt.time(hh, mm), tzinfo=ET)
    return min(dt.datetime.combine(session_date, CLS_CUTOFF_ET, tzinfo=ET),
               close - EARLY_CLOSE_MARGIN)


def queue_open_et(asof: dt.date) -> dt.datetime:
    """The first moment (ET) a cls order for the auction after `asof` may be
    sent: 19:15 ET on the as-of date (see QUEUE_OPEN_ET)."""
    return dt.datetime.combine(asof, QUEUE_OPEN_ET, tzinfo=ET)


# The evening part of the window ends at 01:00 ET the next calendar day (the end
# of the scheduled evening slot). Review 2026-09-29: a window running straight
# from the as-of evening to the session cutoff also covered the DAYTIME of any
# non-trading day in between (a Saturday afternoon, Thanksgiving morning), and
# what Alpaca does with a `cls` sent then is undocumented [U] -- it documents only
# "before 15:50 -> today's close, 15:50-19:00 rejected, after 19:00 -> the
# following day's close". So only the documented stretches are open.
EVENING_WINDOW_END = dt.time(1, 0)


def in_send_window(clock_ts: dt.datetime, asof: dt.date, cutoff: dt.datetime) -> bool:
    """True when an order sent at `clock_ts` joins the auction whose as-of date
    is `asof` and whose cutoff is `cutoff`: either the as-of evening
    [19:15 ET on `asof`, 01:00 ET the next day) or the session day itself
    [00:00 ET on the cutoff's date, cutoff)."""
    now = clock_ts.astimezone(ET)
    eve_end = dt.datetime.combine(asof + dt.timedelta(days=1), EVENING_WINDOW_END, tzinfo=ET)
    day_start = dt.datetime.combine(cutoff.astimezone(ET).date(), dt.time(0, 0), tzinfo=ET)
    return queue_open_et(asof) <= now < eve_end or day_start <= now < cutoff


def gate_clock(clock_ts, session_date, calendar_today, nyse_trading_today,
               asof) -> list[Refusal]:
    """Gate 4. The session date is a trading day by BOTH Alpaca's calendar and
    the repo's NYSE rules, and Alpaca's clock is inside that auction's send
    window: from 19:15 ET on the as-of date (the previous trading day) to the
    cls cutoff on the session date.

    `is_open` from /v2/clock is NOT used: it means "open right now" [V], and
    both the evening and the morning runs happen while the market is shut.
    Before 19:00 ET on the as-of date Alpaca rejects cls, and after the cutoff
    on the session date an order is rejected or queued for the auction AFTER
    this one [V] -- a real order nobody decided for that day -- so the window
    is enforced here, not left to the broker. (Until 2026-09-29 the window was
    the session date only; the team lead moved the decision to the evening.)
    """
    out = []
    if clock_ts.tzinfo is None:
        return [Refusal("clock", f"Alpaca clock timestamp {clock_ts!r} has no timezone")]
    now = clock_ts.astimezone(ET)
    qo = queue_open_et(asof)
    if now < qo:
        out.append(Refusal("clock", f"Alpaca clock {now:%Y-%m-%d %H:%M:%S} ET is before "
                                    f"{qo:%Y-%m-%d %H:%M} ET, when Alpaca starts queueing cls "
                                    f"for the {session_date} auction (as-of {asof})"))
    elif now.date() != session_date and not in_send_window(
            clock_ts, asof, dt.datetime.combine(session_date, CLS_CUTOFF_ET, tzinfo=ET)):
        out.append(Refusal("clock", f"Alpaca clock {now:%Y-%m-%d %H:%M:%S} ET is between the "
                                    f"as-of evening (ends 01:00 ET) and {session_date}; Alpaca "
                                    f"does not document where a cls sent now is routed [U]"))
    if len(calendar_today) > 1:
        out.append(Refusal("clock", f"Alpaca calendar has {len(calendar_today)} rows for "
                                    f"{session_date}"))
        return out
    alpaca_trading = len(calendar_today) == 1
    if alpaca_trading != nyse_trading_today:
        out.append(Refusal("clock", f"calendars disagree on {session_date}: Alpaca "
                                    f"trading={alpaca_trading}, nyse_calendar "
                                    f"trading={nyse_trading_today}"))
    if not alpaca_trading:
        out.append(Refusal("clock", f"{session_date} is not a trading day on Alpaca's calendar"))
        return out
    cut = cutoff_et(session_date, calendar_today[0]["close"])
    if now >= cut:
        out.append(Refusal("clock", f"Alpaca clock {now:%Y-%m-%d %H:%M:%S} ET is at/after the cls "
                                    f"cutoff {cut:%H:%M} ET (calendar close "
                                    f"{calendar_today[0]['close']}, read as ET)"))
    return out


# ------------------------------------------------ paper late-market execution

def late_window_et(session_date: dt.date, calendar_close: str,
                   minutes_before_close: tuple) -> tuple[dt.datetime, dt.datetime]:
    """[close - a, close - b) ET for the book's `execution.window_minutes_before_close`
    = (a, b). Measured from the CALENDAR close, so an early close (13:00) moves the
    window with it (12:52-12:58 for (8, 2)).

    WHY LATE MARKET ORDERS AT ALL (team lead 2026-09-29, a recorded exception to
    CLAUDE.md rule 3 for the PAPER account only): paper runs no closing auction;
    Alpaca staff say it treats `cls` as a market order at the close with random
    partial fills, and on 2026-09-29 eleven of thirteen `cls` orders expired
    unfilled. A plain market order sent in the last minutes fills at the quote
    (paper docs: matched against the NBBO; a partial fill's remainder is
    re-evaluated while marketable) -- the nearest paper gets to the close.
    """
    a, b = minutes_before_close
    if not (isinstance(a, int) and isinstance(b, int) and a > b > 0):
        raise ValueError(f"window_minutes_before_close {minutes_before_close!r} must be two "
                         f"ints a > b > 0")
    if not re.fullmatch(r"\d{2}:\d{2}", calendar_close or ""):
        raise ValueError(f"calendar close {calendar_close!r} is not HH:MM")
    hh, mm = map(int, calendar_close.split(":"))
    close = dt.datetime.combine(session_date, dt.time(hh, mm), tzinfo=ET)
    return close - dt.timedelta(minutes=a), close - dt.timedelta(minutes=b)


def gate_late_clock(clock_ts, session_date, calendar_today, nyse_trading_today,
                    window) -> list[Refusal]:
    """Gate 4 for late-market execution: the session date is a trading day by BOTH
    calendars and Alpaca's clock is inside the send window on that date. Before
    it, a market order fills at a quote too far from the close to stand for it;
    after it, too near the close to be sure it fills."""
    if clock_ts.tzinfo is None:
        return [Refusal("clock", f"Alpaca clock timestamp {clock_ts!r} has no timezone")]
    out = []
    alpaca_trading = len(calendar_today) == 1
    if alpaca_trading != nyse_trading_today:
        out.append(Refusal("clock", f"calendars disagree on {session_date}: Alpaca "
                                    f"trading={alpaca_trading}, nyse_calendar "
                                    f"trading={nyse_trading_today}"))
    now = clock_ts.astimezone(ET)
    lo, hi = window
    if not (lo <= now < hi):
        out.append(Refusal("clock", f"Alpaca clock {now:%Y-%m-%d %H:%M:%S} ET is outside the "
                                    f"late-market send window {lo:%Y-%m-%d %H:%M}-{hi:%H:%M} ET"))
    return out


# The late-send BUDGET (release-check #6, 2026-10-08). A set is not started
# unless the send window has room for all of it:
#     budget = n_orders x SEND_ALLOWANCE_PER_ORDER_S + SEND_MARGIN_S
# Provenance:
#   MEASURED_MAX_ORDER_CYCLE_S: the slowest per-order cycle the runner has
#     recorded. A cycle is one clock GET plus one POST, from one `submit`
#     event to the next in orders.jsonl. Over 33 cycles on the 4 real send
#     days (2026-09-29, 09-30, 10-01, 10-07; laptop prod orders.jsonl, read
#     2026-10-08) the slowest was 0.259 s, the median about 0.09 s, and the
#     largest batch, 13 orders, took 1.18 s.
#   SEND_ALLOWANCE_PER_ORDER_S = 2 + 1 = 3 s:
#     - 2 s is the client's own first retry backoff (alpaca.GET_BACKOFF_S[0]),
#       so each order may have its clock read retried once;
#     - 1 s is the measured worst cycle, rounded up to a whole second, about
#       four times what was seen.
#   SEND_MARGIN_S = 42 s = connect timeout 10 s + read timeout 30 s
#     (alpaca.TIMEOUT_S) + the first retry backoff 2 s (alpaca.GET_BACKOFF_S[0]),
#     so one request in the batch may stall through both timeouts and be retried
#     once and the set still ends inside the window. (Corrected 2026-10-08,
#     release-check #7: it was 30 s, the read timeout alone, which let a set
#     admitted in the last ~40 s be cut short by one stalled request.)
# They are not imported from quantt.broker (gate.py stays free of broker code);
# test_late_send_budget pins them to the client's constants.
# At the live size (13 orders) the budget is 81 s. A set may start until 15:56:39
# (12:56:39 on an early close), which leaves the 15:52 send and the 15:55 retry
# untouched.
MEASURED_MAX_ORDER_CYCLE_S = 0.259
SEND_ALLOWANCE_PER_ORDER_S = 2 + math.ceil(MEASURED_MAX_ORDER_CYCLE_S)
SEND_MARGIN_S = 10 + 30 + 2


def send_budget_s(n_orders: int) -> float:
    """Seconds of send window a set of `n_orders` needs (see the constants above)."""
    return n_orders * SEND_ALLOWANCE_PER_ORDER_S + SEND_MARGIN_S


def gate_late_send_budget(clock_ts, window, n_orders: int) -> list[Refusal]:
    """Gate 4, the late-market budget: refuse to START a set that the time left in
    the send window cannot finish.

    Why: once STARTED is written, a batch that runs past the window's end stops
    there (`_transmit` re-checks the clock before every POST). That leaves a
    partial book, a FAIL, and STARTED blocking any retry that day. Refusing here,
    before STARTED and before any POST, sends nothing instead. A decide that
    hangs until 15:57 and a timer firing queued behind it reach exactly this
    point. The time left is measured on Alpaca's clock, the same reading
    `gate_late_clock` uses. A set started before the window opens is that gate's
    refusal, not this one's.
    """
    if n_orders <= 0:
        return []
    now = clock_ts.astimezone(ET)
    hi = window[1]
    left = (hi - now).total_seconds()
    need = send_budget_s(n_orders)
    if left < need:
        return [Refusal("clock", (
            f"SEND BUDGET: {left:.0f}s left in the send window (until {hi:%H:%M:%S} ET, "
            f"Alpaca clock {now:%H:%M:%S} ET) for {n_orders} order(s); the set needs "
            f"{need:.0f}s ({n_orders} x {SEND_ALLOWANCE_PER_ORDER_S}s + {SEND_MARGIN_S}s). "
            f"Starting it would end in a partial batch: nothing sent, no STARTED written"))]
    return []


def gate_data(asof, refresh_exit, close_dates, nav_dates, universe) -> list[Refusal]:
    """Gate 5. The refresh exited 0 for the required as-of date (or was skipped
    by --skip-refresh), AND every universe name has BOTH a close and a NAV dated
    exactly the as-of date. Stale data never trades.

    WHY BOTH, measured on the real panels (review 2026-09-28): the sleeve
    inner-joins price and NAV (`CEFDiscountSleeve._panel`), so a name with an
    as-of close and no as-of NAV gets a NaN z on the last row, drops out of the
    signal, and is emitted FLAT with the reason "below min weight". With PDI's
    as-of NAV row removed (panels ending 2026-09-21) PDI went from LONG
    w=+0.064 to FLAT. With `--skip-refresh` the fetcher's own close+NAV
    completeness check (exit 4) never runs, so this gate is the only thing
    between a missing NAV and an order that closes (or never opens) that
    name. The close-date check additionally stops the per-name ffill
    (landmine 6) from sizing on an older print.

    `refresh_exit` is None (skipped), an int exit code, or a string saying why
    the refresh did not complete (a timeout, or not run); anything but None or
    0 refuses.
    """
    out = []
    if refresh_exit is not None and refresh_exit != 0:
        what = (f"exited {refresh_exit}" if isinstance(refresh_exit, int)
                else f"did not complete: {refresh_exit}")
        out.append(Refusal("data", f"refresh for as-of {asof} {what}"))
    for label, dates in (("close", close_dates), ("NAV", nav_dates)):
        missing = [s for s in universe if s not in dates or dates[s] is None]
        if missing:
            out.append(Refusal("data", f"no {label} at all for {missing}"))
        stale = {s: str(dates[s]) for s in universe
                 if s not in missing and dates[s] != asof}
        if stale:
            out.append(Refusal("data", f"{label} not dated {asof} for {stale}"))
    return out


# fetch_daily's exit for an INCOMPLETE as-of pair: "--require-asof D  exit 4
# unless every deployed name has BOTH a close and a NAV dated D" (its module
# docstring; `_refresh_locked` writes the panels first, then returns 4). It is
# the only refresh failure that is about NAMES rather than about the fetch, and
# gate 5's own per-name check measures the same thing on the panel it wrote.
# tests/test_combine.py pins this constant to fetch_daily's text.
REFRESH_INCOMPLETE = 4


def refresh_incomplete(refresh_exit) -> bool:
    """True when the refresh exited exactly REFRESH_INCOMPLETE (an int, never a
    bool or a string saying why it did not run)."""
    return (isinstance(refresh_exit, int) and not isinstance(refresh_exit, bool)
            and refresh_exit == REFRESH_INCOMPLETE)


def gate_data_by_sleeve(asof, refresh_exit, close_dates, nav_dates, universes: dict,
                        final) -> tuple[list[Refusal], dict]:
    """Gate 5 for a combined book (quantt/session/combine.py): (book-wide
    refusals, {sleeve: [why]} for each sleeve HELD instead of refused).

    Each sleeve's names are checked on their own, by `gate_data`'s per-name
    rule. WHAT FOLLOWS, and why each case:
      * a refresh failure other than INCOMPLETE (a timeout, a lock, a crash,
        "not run") is about the fetch, not about names: book-wide, exactly
        `gate_data` on the union, as for one sleeve;
      * no sleeve fails: nothing refused. If the refresh nonetheless said
        INCOMPLETE, the fetcher and the panel disagree, and the book is refused
        rather than either believed (CLAUDE.md: two sources that disagree are
        reported, never silently chosen);
      * a sleeve fails BEFORE the final check: the whole decide is refused,
        each refusal naming its sleeve, as the single-sleeve book is refused
        today, so the next slot retries. Holding the sleeve then would cost it
        the day for a NAV that is merely late (they land from ~21:30 ET);
      * a sleeve fails AT OR AFTER the final check, and another passes: the
        failing sleeve is HELD at its attributed shares and the rest decide. One
        sleeve's missing NAV no longer costs every other sleeve the day (C4
        deploy plan §0, the coupling through gate 5). If every sleeve fails,
        nothing can be decided: refused, as today.
    `final` must be exactly True or False: whether a hold is allowed is not
    decided by truthiness.
    """
    if final is not True and final is not False:
        raise ValueError(f"gate_data_by_sleeve: final {final!r} must be True or False")
    if not universes:
        raise ValueError("gate_data_by_sleeve: no enabled sleeve")
    union = sorted({s for u in universes.values() for s in u})
    incomplete = refresh_incomplete(refresh_exit)
    if refresh_exit is not None and refresh_exit != 0 and not incomplete:
        return gate_data(asof, refresh_exit, close_dates, nav_dates, union), {}
    failing = {}
    for name in sorted(universes):
        r = gate_data(asof, None, close_dates, nav_dates, sorted(universes[name]))
        if r:
            failing[name] = [x.detail for x in r]
    if not failing:
        if incomplete:
            return [Refusal("data", f"refresh for as-of {asof} exited {REFRESH_INCOMPLETE} "
                                    f"(INCOMPLETE), but every enabled sleeve's names have a close "
                                    f"and a NAV dated {asof} on the panel: the fetcher and the "
                                    f"panel disagree; not deciding on either")], {}
        return [], {}
    if final and len(failing) < len(universes):
        return [], failing
    out = [Refusal("data", f"refresh for as-of {asof} exited {REFRESH_INCOMPLETE}")] \
        if incomplete else []
    for name, details in failing.items():
        out.extend(Refusal("data", f"sleeve {name}: {d}") for d in details)
    return out, {}


# ------------------------------- gate 5's missing-NAV hold (on since 2026-10-29)

# The book json's `data.missing_nav` (run.missing_nav_for). ABSENT is gate 5 as
# it always was: one name without an as-of NAV refuses the whole day.
MISSING_NAV_HOLD = "hold"
MISSING_NAV_MODES = (MISSING_NAV_HOLD,)


def max_missing_nav_holds(n_names: int, min_names: int) -> int:
    """The most names gate 5 may hold for a missing NAV: n_names - min_names.

    THE DERIVATION (team lead 2026-10-29: "when min_names would bind anyway").
    A held name leaves the cross-section, so with k names held at most n - k
    can be in it. The frozen spec's `min_names` is its own floor on breadth:
    below it the sleeve forms no cross-section at all. With n - k < min_names,
    then, the decide could not trade a single name on its signal whatever the
    rest of the data said: the sleeve would hold the whole book (holds never
    trigger its flatten), and the plan would read "decided, nothing to send",
    a missed day that verify would score as a quiet one. That many missing
    NAVs is a broken feed, not a late NAV, and the day is refused, as without
    the key. For the live spec (13 names, min_names 6) at most 7 may be held:
    8 or more missing refuses. Both numbers are read from the frozen spec at
    run time (never a literal; CLAUDE.md, H14).
    """
    if not (isinstance(n_names, int) and isinstance(min_names, int)
            and not isinstance(min_names, bool) and 0 < min_names):
        raise ValueError(f"max_missing_nav_holds: n_names {n_names!r} and min_names "
                         f"{min_names!r} must be ints, min_names > 0")
    return max(0, n_names - min_names)


def max_sessions_ok(v) -> bool:
    """A held-session limit must be a positive int (not a bool, not a float)."""
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def missing_nav_hold(asof, refresh_exit, close_dates, nav_dates, universe, final,
                     min_names, max_sessions, held_before) -> dict:
    """Gate 5 with the book json's `data.missing_nav = "hold"`: what it refuses,
    what it holds, and why, for the single-sleeve book.

    THE RULE (team lead 2026-10-29). On 2026-10-22 PDO's NAV for 10-21 never
    reached the panel (the CEFConnect fallback has refused every scripted
    request since 10-21), gate 5 refused all 13 names on every slot, and the
    book missed the day. With the key, a name whose only fault is a NAV not
    dated the as-of date is, FROM THE FINAL CHECK, HELD: it keeps its current
    shares (no order in it, never targeted to zero), leaves the cross-section
    (`extras["nav_hold"]` in the sleeve, the stale-NAV gate's machinery), and
    the other names decide. Every other case is gate 5 exactly as without the
    key, refusal text for refusal text:
      * a refresh failure other than INCOMPLETE (a timeout, a lock, a crash):
        about the fetch, not about names, so the day is refused;
      * any name whose CLOSE is missing or not dated as-of: a fund missing its
        price, not just its NAV, keeps today's refusal (the team lead's guard);
      * any name with no NAV at all: never captured is not late;
      * every name has a NAV dated as-of, but the refresh said INCOMPLETE: the
        fetcher and the panel disagree, refused as today ("exited 4").
    And for names whose NAV is merely not dated as-of:
      * more than `max_missing_nav_holds` of them: refused, the reason added
        (a broken feed, not a late NAV; its docstring has the derivation);
      * BEFORE the final check: refused with today's refusals plus one line
        saying the decide is DEFERRED, because the NAV may still land (they
        land from ~21:30 ET; the morning backstop re-runs the refresh every
        30 minutes). Nothing is decided and nothing is marked, exactly as the
        stale-NAV gate defers (`nav_gate.py`, UNVERIFIED);
      * AT OR AFTER the final check: no refusal, and each such name is held.
        The refresh's INCOMPLETE (exit 4) is then expected, not a fault: it is
        fetch_daily's answer for exactly these names, and gate 5 measured them
        on the panel it wrote;
      * ... UNLESS a name has already gone `max_sessions` consecutive prior
        sessions without a dated NAV (`held_before[name] >= max_sessions`), or
        that count could not be read from the records (`held_before[name]` is
        a string saying why). Then the day is REFUSED, exactly as without the
        key, with one line naming the fund and how long it has been held.
    THE AGE LIMIT (team lead 2026-10-29: "limit it, then refuse the day").
    `max_sessions` is the book json's data.missing_nav_max_sessions, a POLICY
    of 2 consecutive sessions, not a measurement: PDO's 10-22 gap was one
    session, so a late NAV can land the next day; a fund held longer is
    trading blind on a frozen position. It was to be derived from how long the
    vendor's gaps last, but prod's NAV panel (copy of 2026-10-28) shows none in
    12 months: the vendor backfills dates, and a late NAV survives only as a
    repeated value. It is to be reviewed against the live gaps in the run
    records' `nav_dates`. The count survives across sessions because it is
    read from them (`run.missing_nav_streaks`), never kept in memory, and an
    unreadable record refuses rather than counting as zero.
    `final` must be exactly True or False. Returns {"action", "why",
    "missing", "held", "max_held", "refusals"}: `missing` maps each name whose
    NAV is not dated as-of to its last NAV date (None: no NAV at all); `held`
    maps each held name to the reason the sleeve records; `refusals` is
    Refusal objects. Pure, like every gate here."""
    if final is not True and final is not False:
        raise ValueError(f"missing_nav_hold: final {final!r} must be True or False")
    if not max_sessions_ok(max_sessions):
        raise ValueError(f"missing_nav_hold: max_sessions {max_sessions!r} must be a "
                         f"positive int")
    from quantt.session.nav_gate import FINAL_CHECK_BEFORE_CLOSE   # stdlib-only module
    universe = sorted(universe)
    max_held = max_missing_nav_holds(len(universe), min_names)
    base = gate_data(asof, refresh_exit, close_dates, nav_dates, universe)
    missing = {s: (None if nav_dates.get(s) is None else str(nav_dates[s]))
               for s in universe if nav_dates.get(s) != asof}
    out = {"missing": missing, "held": {}, "max_held": max_held}
    if not base:
        return {**out, "action": "none", "why": f"every name has a close and a NAV dated "
                                                f"{asof}", "refusals": []}
    incomplete = refresh_incomplete(refresh_exit)
    no_close = [s for s in universe if close_dates.get(s) != asof]
    never = [s for s, d in missing.items() if d is None]
    late = {s: d for s, d in missing.items() if d is not None}
    if refresh_exit is not None and refresh_exit != 0 and not incomplete:
        why = f"the refresh failed ({refresh_exit}), not a name: gate 5 refuses the day"
    elif no_close:
        why = (f"a close is missing or not dated {asof} for {no_close}: a missing price "
               f"keeps gate 5's refusal of the day")
    elif never:
        why = f"no NAV at all for {never}: never captured is not late; refused"
    elif not late:
        why = (f"the refresh said INCOMPLETE but every name has a NAV dated {asof}: the "
               f"fetcher and the panel disagree; refused")
    else:
        why = None
    if why is not None:
        return {**out, "action": "refused", "why": why, "refusals": base}
    if len(late) > max_held:
        why = (f"missing-NAV hold (data.missing_nav=hold): {len(late)} of {len(universe)} "
               f"names have no NAV dated {asof} ({late}); at most {max_held} may be held "
               f"(holding more leaves fewer than min_names {min_names} with a NAV): a broken "
               f"feed, not a late NAV; refused")
        return {**out, "action": "refused", "why": why,
                "refusals": base + [Refusal("data", why)]}
    if not final:
        mins = FINAL_CHECK_BEFORE_CLOSE.total_seconds() / 60
        why = (f"missing-NAV hold (data.missing_nav=hold): NAV not dated {asof} for {late}; "
               f"deferred to a later slot -- the NAV may still land, and from the final check "
               f"({mins:.0f} min before the close) each is held at its current shares and "
               f"the other names decide")
        return {**out, "action": "deferred", "why": why,
                "refusals": base + [Refusal("data", why)]}
    if not isinstance(held_before, dict) or set(late) - set(held_before):
        raise ValueError(f"missing_nav_hold: at the final check every name without a dated "
                         f"NAV needs its prior count; got {held_before!r} for {sorted(late)}")
    over = {}
    for s in sorted(late):
        n = held_before[s]
        if isinstance(n, str):
            over[s] = f"{s}: its prior sessions cannot be counted ({n})"
        elif not (isinstance(n, int) and not isinstance(n, bool) and n >= 0):
            raise ValueError(f"missing_nav_hold: held_before[{s!r}] {n!r} is not a count")
        elif n >= max_sessions:
            over[s] = (f"{s}: no NAV dated its as-of for the {n} consecutive sessions before "
                       f"this one, held for each")
    if over:
        why = (f"missing-NAV hold (data.missing_nav=hold): age limit "
               f"data.missing_nav_max_sessions = {max_sessions} consecutive sessions: "
               f"{'; '.join(over.values())}; refused, as without the key")
        return {**out, "action": "refused", "why": why,
                "refusals": base + [Refusal("data", why)]}
    held = {s: (f"no NAV dated {asof} (the panel's last is {d}); held at the final check "
                f"(data.missing_nav=hold), session {held_before[s] + 1} of at most "
                f"{max_sessions}") for s, d in sorted(late.items())}
    return {**out, "action": "held", "held": held, "refusals": [],
            "why": f"{sorted(held)} held at current shares from the final check; "
                   f"{len(universe) - len(held)} of {len(universe)} names decide"}


def gate_data_missing_nav(asof, refresh_exit, close_dates, nav_dates, universe, final,
                          min_names, max_sessions, held_before) -> tuple[list[Refusal], dict]:
    """(refusals, {held name: reason}): `missing_nav_hold` as a gate."""
    v = missing_nav_hold(asof, refresh_exit, close_dates, nav_dates, universe, final,
                         min_names, max_sessions, held_before)
    return v["refusals"], v["held"]


def _gate_data_for(f: GateFacts) -> list[Refusal]:
    """Gate 5 for `evaluate`: the single-sleeve rule, the missing-NAV hold when
    the book json sets it, or the combiner's per-sleeve rule."""
    if f.sleeve_universes is not None:
        return gate_data_by_sleeve(f.asof, f.refresh_exit, f.close_dates, f.nav_dates,
                                   f.sleeve_universes, f.data_final)[0]
    if f.missing_nav is None:
        return gate_data(f.asof, f.refresh_exit, f.close_dates, f.nav_dates, f.universe)
    if f.missing_nav not in MISSING_NAV_MODES:
        raise ValueError(f"GateFacts.missing_nav {f.missing_nav!r} is not one of "
                         f"{MISSING_NAV_MODES}")
    return gate_data_missing_nav(f.asof, f.refresh_exit, f.close_dates, f.nav_dates,
                                 f.universe, f.data_final, f.min_names,
                                 f.missing_nav_max_sessions, f.missing_nav_held_before)[0]


def gate_no_set_in_auction(started_exists, orders_recent, orders_open, cid_prefix,
                           session_date, unread: str | None = None) -> list[Refusal]:
    """Gate 6. Refuse if a set may already be headed for today's auction:
    `<state>/<date>/STARTED` exists, or Alpaca shows any order whose
    client_order_id starts with `<prefix>-<YYYYMMDD>-`, or ANY open order.

    WHY ALL THREE. Open positions exclude unfilled MOC orders, so a second run
    sees the same flat book and sends the same orders again; both fill in the
    same auction and the book doubles (CLAUDE.md rule 2). STARTED catches a
    second local run; the Alpaca order checks catch a run from another machine
    or a lost state dir. `status=all` for the prefix check, because an order
    already filled or cancelled today still means the set went.

    UNREAD (review 2026-10-29). run.py reads the two lists as the last broker
    read before the gate's clock read (`run._gate6_orders`), so they are as
    fresh as the gate can judge. `unread` is why that read failed; both lists
    are then None and the gate refuses, naming it: a list that cannot be read
    is not an empty one, and no earlier read may stand in for it, so a list
    passed with `unread` raises. STARTED is still checked.
    """
    out = []
    if started_exists:
        out.append(Refusal("no_set_in_auction", f"STARTED exists for {session_date}"))
    if unread is not None:
        if orders_recent is not None or orders_open is not None:
            raise ValueError(f"gate 6: order lists given together with unread={unread!r}; "
                             f"an earlier read never stands in for a failed one")
        out.append(Refusal("no_set_in_auction", f"Alpaca's orders could not be read at the "
                                                f"gate: {unread}; a list that cannot be read "
                                                f"is not an empty one, so nothing is sent"))
        return out
    if orders_recent is None or orders_open is None:
        raise ValueError(f"gate 6: an order list was not read (orders_recent "
                         f"{'None' if orders_recent is None else 'read'}, orders_open "
                         f"{'None' if orders_open is None else 'read'}) and no reason was given")
    pfx = f"{cid_prefix}-{session_date:%Y%m%d}-"
    ours = sorted({o.get("client_order_id") or "" for o in orders_recent
                   if (o.get("client_order_id") or "").startswith(pfx)})
    if ours:
        out.append(Refusal("no_set_in_auction", f"Alpaca already has order ids for the "
                                                f"{session_date} auction {ours}"))
    # ANY open order, not only cls (review 2026-09-28): a day/GTC order left by a
    # manual probe reserves shares (positions are read from `qty`, not
    # `qty_available`) and may fill against today's set. Each book has its own
    # account, so an open order this runner did not just send is never expected.
    any_open = sorted(f"{o.get('symbol')}:{o.get('client_order_id')}:{o.get('time_in_force')}"
                      for o in orders_open)
    if any_open:
        out.append(Refusal("no_set_in_auction", f"open order(s) at Alpaca: {any_open}"))
    return out


def gate_shortability(orders, positions, shortable, shorting_enabled) -> list[Refusal]:
    """Gate 7. Re-checks decide's per-symbol rule on the FINAL list (decide
    drops such a symbol and logs it; reaching here with one is a bug), and
    refuses if any order opens or increases a short while the account has
    shorting disabled."""
    out, running = [], dict(positions)
    for o in orders:
        cur = running.get(o.symbol, 0)
        after = cur + o.signed_qty
        running[o.symbol] = after
        if after < 0 and after < min(cur, 0):
            if shortable.get(o.symbol) is not True:
                out.append(Refusal("shortability", f"{o.client_order_id} opens/increases a "
                                                   f"short in {o.symbol}, shortable="
                                                   f"{shortable.get(o.symbol)!r}"))
            if shorting_enabled is not True:
                out.append(Refusal("shortability", f"{o.client_order_id} opens/increases a "
                                                   f"short but account shorting_enabled="
                                                   f"{shorting_enabled!r}"))
    return out


def projected_positions(orders, positions) -> dict:
    out = dict(positions)
    for o in orders:
        out[o.symbol] = out.get(o.symbol, 0) + o.signed_qty
    return {s: q for s, q in out.items() if q != 0}


def buying_power_needed(orders, positions, closes) -> float:
    """Estimated buying power the orders consume at submission, per Alpaca's
    documented rule [V, docs "orders-at-alpaca"]: open buy-long and sell-short
    orders reduce buying power (a short at 3% above the price); sell-to-close
    and buy-to-cover "do not replenish ... until they are executed", so they
    count zero here, not negative. Priced at the as-of close: an estimate."""
    need, running = 0.0, dict(positions)
    for o in orders:
        cur = running.get(o.symbol, 0)
        after = cur + o.signed_qty
        running[o.symbol] = after
        opening_long = max(0, after - max(cur, 0)) if o.side == "buy" else 0
        opening_short = max(0, min(cur, 0) - after) if o.side == "sell" else 0
        px = closes[o.symbol]
        need += opening_long * px + opening_short * px * SHORT_ORDER_BP_MULTIPLIER
    return need


REG_T_INITIAL = 0.5   # Reg T initial margin, 50% of gross [V: Alpaca margin docs;
                      # measured 2026-10-06: initial_margin = 50.0% of gross]


def margin_limits(positions_after: dict, closes: dict, equity: float, current_gross: float,
                  maintenance_margin: float) -> list[str]:
    """The OVERNIGHT check (review 2026-10-07): after the orders fill, Reg T
    initial margin (50% of projected gross) <= equity, and projected maintenance
    at the account's LIVE measured ratio (maintenance_margin / current gross,
    47.8% on 2026-10-06 [V], never a literal) <= equity. With no current gross
    the ratio cannot be measured; the initial-margin check then stands alone
    (on these names it is the stricter of the two: 50% > 47.8% measured)."""
    gross = sum(abs(q) * closes[s] for s, q in positions_after.items())
    out = []
    if REG_T_INITIAL * gross > equity:
        out.append(f"projected Reg T initial margin ${REG_T_INITIAL * gross:,.2f} "
                   f"(50% of gross ${gross:,.2f}) > equity ${equity:,.2f}")
    if current_gross > 0:
        if maintenance_margin <= 0:
            out.append(f"maintenance_margin {maintenance_margin} with current gross "
                       f"{current_gross:,.2f}: the ratio cannot be measured; not assumed")
            return out
        ratio = maintenance_margin / current_gross
        if ratio * gross > equity:
            out.append(f"projected maintenance ${ratio * gross:,.2f} (measured "
                       f"{ratio:.1%} of gross) > equity ${equity:,.2f}")
    return out


def stress_breach(gross_after: float, gross_before: float, max_gross_stress,
                  sized_equity: float, live_equity: float) -> str | None:
    """Why the book AFTER a plan breaks the spec's `max_gross_stress`, or None.

    It breaks it only when BOTH hold: gross after the plan > max_gross_stress x
    the LOWER of the equity the plan was SIZED on and the live equity, AND the
    plan adds to the gross held now. Both grosses are valued at the same as-of
    closes. At decide the two equities are the same number.

    WHY THE LOWER OF THE TWO (team lead's ruling 2026-10-11, after release-check
    review). The sized equity alone (below) left a gap: once live equity was
    more than 1 - 1.8/1.843 = 2.34% under the sized equity, a plan that ADDS
    gross could go out above the derived G_stress 1.843 x live equity, with only
    Reg T (2.0x) left to stop it. The 1.843 is a margin-survival limit on LIVE
    equity, so a plan that adds gross is now held to the cap on whichever equity
    is lower. This does not bring back the 2026-10-09 missed day: that plan took
    gross DOWN, which always passes, and a plan that adds gross is scaled to fit
    by `run.fit_to_buying_power`, which reads this same rule, instead of refused.

    WHY THE SIZED EQUITY (incident 2026-10-09, team lead's go the same day). The
    spec defines the cap in weight space: gross = sum|w| of the held book after
    the band, w = q x px / sleeve_nav, with sleeve_nav the equity at DECIDE
    (cef_discount.py `_cap_gross`; `_max_gross_stress_note`). This gate used to
    compare that plan, at the as-of closes, with the cap times Alpaca's LIVE
    equity at 15:52. When the cap binds, the plan sits at 1.80x the decide
    equity, so ANY fall in equity between the evening decide and the send
    refused the whole set. On 2026-10-09 the plan was $182,154.75 = 1.7994x
    $101,229.74 (decide); equity at 15:52 was $100,666.16, the cap $181,199.09,
    and both the 15:52 send and the 15:55 retry were refused. The book did not
    trade. The 0.043x of headroom up to the derived G_stress 1.843 exists for
    exactly this movement (spec note: "NOT CHOSEN: 1.843 itself (no room for
    its own movement)"). What the account can bear on the day is checked on
    LIVE numbers by the order-time and overnight checks below; they are unchanged.

    WHY A PLAN THAT DOES NOT ADD GROSS ALWAYS PASSES. The refused 2026-10-09
    plan took gross DOWN, from $183,413.36 to $182,154.75 at the as-of closes.
    Refusing it left the book at 1.83x at that close: above the cap, by more
    than the plan would have. A ceiling is there to stop the book adding gross
    past it. It must never block a plan that brings gross down.
    """
    if max_gross_stress is None:
        return None
    base = min(sized_equity, live_equity)
    cap = max_gross_stress * base
    if gross_after <= cap or gross_after <= gross_before:
        return None
    which = "the equity the plan was sized on" if sized_equity <= live_equity else "live equity"
    return (f"projected gross ${gross_after:,.2f} > max_gross_stress {max_gross_stress} x "
            f"${base:,.2f}, {which}, the lower of sized ${sized_equity:,.2f} and live "
            f"${live_equity:,.2f} (${cap:,.2f}), and the plan adds to the gross held now "
            f"(${gross_before:,.2f})")


def gate_exposure(orders, positions, closes, equity, buying_power, max_gross_usd,
                  max_gross_stress, *, sized_equity: float, current_gross: float,
                  maintenance_margin: float) -> list[Refusal]:
    """Gate 8. After the orders fill as sent: gross <= risk.max_gross_exposure_usd;
    `stress_breach` against the lower of the equity the plan was SIZED on and
    the live equity (when the spec sets max_gross_stress); the ORDER-TIME check -- buying power the opening orders
    consume <= Alpaca's live `buying_power`, which is what Alpaca enforces at
    submission [V]; and the OVERNIGHT check (`margin_limits`) on live equity. A
    name with a position or an order and no close refuses (it cannot be
    valued), never counts as 0.

    WHY TWO CHECKS (review 2026-10-07). Until then the gate compared opening
    notional with min(buying_power, regt_buying_power) -- the overnight Reg T
    HEADROOM left by today's book, with no credit for what the same plan
    closes. On 2026-10-06 that refused a catch-up plan ($82.8k opening vs
    $80.8k regt) that Alpaca would have accepted ($188.5k buying_power) and that
    ended at 1.57x gross, inside every limit. The overnight limit is now checked
    on the book AFTER the plan, which is what it is about.

    Why the stress cap uses the lower of the sized and the live equity
    (2026-10-09, 2026-10-11): `stress_breach`.
    """
    out = []
    proj = projected_positions(orders, positions)
    unpriced = sorted(s for s in set(proj) | set(positions) | {o.symbol for o in orders}
                      if not (isinstance(closes.get(s), (int, float))
                              and math.isfinite(closes[s]) and closes[s] > 0))
    if unpriced:
        return [Refusal("exposure", f"no close to value {unpriced}")]
    gross = sum(abs(q) * closes[s] for s, q in proj.items())
    if gross > max_gross_usd:
        out.append(Refusal("exposure", f"projected gross ${gross:,.2f} > spec "
                                       f"max_gross_exposure_usd ${max_gross_usd:,.2f}"))
    held = sum(abs(q) * closes[s] for s, q in positions.items())
    why = stress_breach(gross, held, max_gross_stress, sized_equity, equity)
    if why:
        out.append(Refusal("exposure", why))
    need = buying_power_needed(orders, positions, closes)
    if need > buying_power:
        out.append(Refusal("exposure", f"orders need ~${need:,.2f} of buying power "
                                       f"(est. at as-of closes) > Alpaca buying_power "
                                       f"${buying_power:,.2f}"))
    for m in margin_limits(proj, closes, equity, current_gross, maintenance_margin):
        out.append(Refusal("exposure", m))
    return out


def gate_sanity(orders, universe, positions, cid_prefix, session_date,
                account_flags) -> list[Refusal]:
    """Gate 9. Every qty a positive int, every symbol in the frozen universe, no
    symbol with opposite-side orders (the wash-trade 403, landmine 2), no
    duplicate client ids, every id this session's; no position the book does
    not trade (an account holding something this runner did not buy is not a
    state to trade on top of); the account not blocked. For a combined book
    (quantt/session/combine.py) `universe` is the UNION of the enabled sleeves'
    universes (`combine.book_params`): a holding in any of them is the book's,
    and a holding in none is still refused."""
    out = []
    uni = set(universe)
    stray = sorted(s for s in positions if s not in uni)
    if stray:
        out.append(Refusal("sanity", f"account holds non-universe symbol(s) {stray}"))
    for f in ("trading_blocked", "account_blocked", "trade_suspended_by_user"):
        if account_flags.get(f) is not False:
            out.append(Refusal("sanity", f"account {f}={account_flags.get(f)!r}"))
    sides, cids = {}, set()
    pfx = f"{cid_prefix}-{session_date:%Y%m%d}-"
    for o in orders:
        if type(o.qty) is not int or o.qty <= 0:
            out.append(Refusal("sanity", f"{o.client_order_id}: qty {o.qty!r} is not a "
                                         f"positive int"))
        if o.symbol not in uni:
            out.append(Refusal("sanity", f"{o.client_order_id}: {o.symbol} not in the "
                                         f"frozen universe"))
        if o.side not in ("buy", "sell"):
            out.append(Refusal("sanity", f"{o.client_order_id}: side {o.side!r}"))
        sides.setdefault(o.symbol, set()).add(o.side)
        if o.client_order_id in cids:
            out.append(Refusal("sanity", f"duplicate client_order_id {o.client_order_id}"))
        cids.add(o.client_order_id)
        if o.client_order_id != f"{pfx}{o.symbol}-{o.leg}":
            out.append(Refusal("sanity", f"client_order_id {o.client_order_id!r} is not "
                                         f"{pfx}{o.symbol}-{o.leg}"))
    both = sorted(s for s, v in sides.items() if len(v) > 1)
    if both:
        out.append(Refusal("sanity", f"opposite-side orders in {both}"))
    return out


def evaluate(f: GateFacts) -> list[Refusal]:
    """All nine gates, in RUNNER.md order; every refusal, not the first."""
    return [
        *gate_dry_run(f.env_dry_run),
        *gate_arming(f.approve_sha, f.plan_sha, f.auto_armed),
        *gate_halt(f.halts),
        *gate_clock(f.clock_ts, f.session_date, f.calendar_today, f.nyse_trading_today,
                    f.asof),
        *_gate_data_for(f),
        *gate_no_set_in_auction(f.started_exists, f.orders_recent, f.orders_open,
                                f.cid_prefix, f.session_date, unread=f.orders_unread),
        *gate_shortability(f.orders, f.positions, f.shortable, f.shorting_enabled),
        *gate_exposure(f.orders, f.positions, f.closes, f.equity, f.buying_power,
                       f.max_gross_usd, f.max_gross_stress, sized_equity=f.sized_equity,
                       current_gross=f.current_gross,
                       maintenance_margin=f.maintenance_margin),
        *gate_sanity(f.orders, f.universe, f.positions, f.cid_prefix, f.session_date,
                     f.account_flags),
    ]
