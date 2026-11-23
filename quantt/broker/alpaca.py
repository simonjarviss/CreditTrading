"""The Alpaca REST client for the runner: reads the paper account, sends one kind of order.

WHY THIS EXISTS, AND WHY IT IS THIS SMALL
-----------------------------------------
`docs/RUNNER.md` gives this module one job: be the only thing in `quantt/` that
speaks HTTP to Alpaca, and decide nothing. The session (`quantt/session/run.py`)
decides what to send and whether the gates allow it; `verify.py` decides what a
fill means. This client turns Alpaca's JSON into checked Python and back, and it
refuses every shape it was not built for. Two failure histories shape it:

  * Confident wrong numbers. The IBKR-era book once sized every displayed target
    against an invented $500k equity because a missing field had a default
    (CLAUDE.md). Alpaca documents only `id` and `status` as required on the
    account (docs, fetched 2026-09-28), and sends every number as a string. So
    every field the runner reads is required here, parsed here, and a missing or
    unparseable one raises naming the endpoint and the field. There is no
    `.get(field, default)` on any value that reaches a decision.
  * The doubled book. The trade phase is not idempotent and the broker does not
    dedupe: `client_order_id` is unique only among ACTIVE orders (Alpaca Learn,
    [V] 2026-09-28), and an open MOC order is not yet a position. A client that
    "helpfully" retried a POST after a read timeout could put a second copy of
    the order into the same auction. So `submit_order` is called once and never
    retried by this module; a transport failure after the request may have left
    raises `AmbiguousSubmit`, whose message tells the caller to look the id up
    with `order_by_client_id` and never to resend blind.

WHAT IT WILL NOT DO
-------------------
  * Talk to anything but `https://paper-api.alpaca.markets` for trading and
    `https://data.alpaca.markets` for market data. Neither is configurable to
    another value: the constructor raises, and `submit_order` checks again,
    because a live endpoint anywhere is a test failure (RUNNER.md).
  * Send anything but `type=market, time_in_force=cls` (CLAUDE.md order-path
    rule 3: overnight market orders realised 100.5bp against a 32.6bp
    breakeven on 2026-07-31). There is no parameter for either. If Alpaca
    rejects `cls` -- Alpaca Learn says OPG/CLS are "only available to Elite
    Smart Router users" and nobody has yet shown what paper does [U] -- the
    rejection is raised as `OrderRejected`; nothing falls back to `day`.
  * Send a fractional or non-positive quantity. Alpaca cannot short fractions
    or send them `cls` [V: docs]; the sign of a trade lives in `side`, never in
    a negative qty.
  * Cancel or replace. There is no DELETE or PATCH in this module; the runner's
    design does not need one, and a cancel path is a second way to lose track of
    what is headed for the auction.
  * Retry a write. Only GETs retry, on 429/5xx/transport errors, a bounded
    number of times, because a GET changes nothing at the broker.

CREDENTIALS
-----------
Loaded with `dotenv_values` from the file the caller names -- in the runner,
the path in the required env var `QUANTT_ENV_FILE` (`from_environment`) -- as
`ALPACA_<BOOK>_KEY_ID` / `ALPACA_<BOOK>_SECRET_KEY`. They go into the HTTP
session's headers and nowhere else: not an attribute, not `repr`, not a log
line, not an exception message (every message is scrubbed of both values
before it is raised, in case Alpaca ever echoes a header back). A missing key
raises naming the variable; another book's key is never substituted, because
two books on one key would share one account, which is the wash-trade
collision the per-book accounts exist to prevent (CLAUDE.md landmine 2).

Uncertain API facts are coded defensively, never assumed: see the docstrings of
`positions` (short qty sign), `orders` (time-cursor pagination), `calendar`
(timezone), `closing_auction_prints` (which print is "the" official close),
`eod_equity_history` (which session a daily stamp belongs to, and whether it is final)
and `corporate_actions` (which field the `symbols` filter matches on a merger).
Source for every [V]/[S]/[U] claim: `results/ops/ALPACA_API_FACTS_2026-09-28.md`.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
import os
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo

from quantt.broker.alpaca_probe import MissingCredential, env_names

NY = ZoneInfo("America/New_York")   # the exchange clock; auction windows are ET days


def refuse_redirects(session) -> None:
    """Make `session` unable to follow an HTTP redirect. Call it on every session that
    carries the Alpaca key headers.

    WHY (security review, 2026-11-10). `requests` follows a 3xx by default, and on a
    redirect to ANOTHER HOST it removes only the `Authorization` header. Alpaca's keys
    travel in two custom headers, `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY`, which
    `requests` keeps: a 301/302/303/307/308 from either Alpaca host (or from anything
    that can answer in its place) would hand both keys to whatever host the `Location`
    names. The client checks which host it ADDRESSES (PAPER_BASE, DATA_BASE) and, until
    this change, nothing checked where a response sent it next. Neither Alpaca API
    documents a redirect, so following one buys nothing.

    Two layers, because either alone can be forgotten:
      * this function sets `max_redirects = 0`. `requests` then raises
        `TooManyRedirects` on ANY 3xx, BEFORE it builds the second request, whatever the
        call passed (measured: it raises even with `allow_redirects=False`, because
        `requests` still resolves the next hop to fill `response.next`). So a research
        script that borrows `client._session` and calls it bare is covered too. The
        client turns that exception into its own error, naming the status;
      * every call in this package also passes `allow_redirects=False`, which is what
        protects a session that is not a `requests.Session` or lost the setting, and
        each caller has an explicit 3xx branch for that case.
    `quantt/tests/test_alpaca_redirects.py` runs the real `requests` redirect code against
    a recording transport and shows the second host receives nothing either way.
    """
    session.max_redirects = 0

# The only two hosts this client will ever address. Not configurable on
# purpose: the constructor accepts the arguments RUNNER.md names so a caller
# can SAY which endpoint it expects, and raises if that is anything else.
PAPER_BASE = "https://paper-api.alpaca.markets"
DATA_BASE = "https://data.alpaca.markets"

# GET retry schedule, seconds slept BEFORE attempts 2..N. Five attempts, about
# a minute in total: Alpaca throttles at "200 requests per minute, per account"
# [S: support page dated Dec 2022], so a 429 can need most of a minute to
# clear. Bounded, because the session has a 15:45 ET deadline to meet and a
# client that retries forever turns a broker outage into a silent miss.
GET_BACKOFF_S = (2, 5, 15, 30)

# PACING ON THE TRADING HOST (2026-11-23). The events book's first armed send POSTed 219
# orders after reading 219 assets, with nothing pacing either, and Alpaca answered HTTP 429
# "rate limit exceeded" to 173 of the orders (`docs/SYSTEM.md` §5, 2026-11-23; EVIDENCE_LOG
# E-2026-11-23-03). The GETs survived on the retry above; the POSTs, which are never retried
# here, did not. So every request to the trading host first takes a token from a bucket of
# TRADING_BURST tokens refilled at TRADING_MAX_PER_MIN a minute: no 60 s window can hold
# more than TRADING_BURST + TRADING_MAX_PER_MIN requests, 190, under Alpaca's 200 [S], with
# room for a GET retry. A book that sends a few dozen orders never waits (the core and C4
# are unchanged); a large set is smoothed to one request every 0.4 s. The data host is not
# paced: the send path does not use it, and its jobs keep their timing. The limit is per
# client object, and the runner makes one per process and account.
TRADING_MAX_PER_MIN = 150
TRADING_BURST = 40

# (connect, read) timeout for every request. A read timeout on a GET is retried;
# on the POST it is AmbiguousSubmit.
TIMEOUT_S = (10, 30)

ORDERS_MAX_LIMIT = 500          # GET /v2/orders: "limit ... max 500" [V]
FILL_PAGE_SIZE = 100            # GET /v2/account/activities: page_size max 100 [V]
AUCTIONS_MAX_LIMIT = 10000      # GET /v2/stocks/auctions: limit max 10000 [V]
MAX_PAGES = 1000                # a pagination loop that runs this long is a bug, not data

# Symbols as Alpaca writes US equities (e.g. PDI, BRK.B). Anything else is
# refused before it can reach a URL path or an order.
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")
# client_order_id: Alpaca documents only "<= 128 characters" [V]; the allowed
# characters are undocumented [U]. The runner's ids are
# `cef-<YYYYMMDD>-<SYMBOL>-<leg>`, so this conservative set is all it needs,
# and anything outside it is refused rather than discovered at the broker.
_CID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HHMM_RE = re.compile(r"^\d{2}:\d{2}$")


# --------------------------------------------------------------------- errors

class AlpacaError(RuntimeError):
    """Base for everything this client raises about Alpaca. Messages never hold a key."""


class UnexpectedResponse(AlpacaError):
    """Alpaca answered 2xx with a body this client was not built for (a missing
    field, a wrong type, a sign conflict). Raised instead of guessing."""


class AlpacaHTTPError(AlpacaError):
    """A non-2xx answer to a GET (after retries, for the retryable ones)."""

    def __init__(self, msg: str, *, status: int | None):
        super().__init__(msg)
        self.status = status


class AssetNotFound(AlpacaHTTPError):
    """GET /v2/assets/<sym> returned 404: Alpaca does not list the symbol."""


class OrderRejected(AlpacaError):
    """Alpaca answered the POST with a 4xx: the order was NOT accepted.

    `status` and `body` are Alpaca's (e.g. 403 buying power / wash trade, 422
    duplicate client_order_id). Whether and how to try again is the session's
    decision, never this client's.
    """

    def __init__(self, msg: str, *, status: int, client_order_id: str):
        super().__init__(msg)
        self.status = status
        self.client_order_id = client_order_id


class AmbiguousSubmit(AlpacaError):
    """The POST may or may not have reached Alpaca: a timeout, a dropped
    connection, a 5xx, or an unreadable 2xx body.

    The one thing the caller must not do is send it again: if the first copy
    was accepted, the second fills in the same auction and the position
    doubles (CLAUDE.md order-path rule 2). Look the id up with
    `order_by_client_id`; only an answer of "not found" says it did not land.
    """

    def __init__(self, msg: str, *, client_order_id: str):
        super().__init__(msg)
        self.client_order_id = client_order_id


class SubmitResponseInvalid(AlpacaError):
    """Alpaca ACCEPTED the order (2xx) but echoed something other than what was
    sent -- a different symbol, side, qty, type or time_in_force. The order
    exists at the broker; do not resend. Stop and look at it."""

    def __init__(self, msg: str, *, client_order_id: str, order_id: str | None):
        super().__init__(msg)
        self.client_order_id = client_order_id
        self.order_id = order_id


class MissingAuctionPrint(AlpacaError):
    """No official closing-auction print for these symbols on the date asked.
    A bar close is never substituted: it is updated by condition 6, not M
    [V: bars reference], and is not the same number."""

    def __init__(self, msg: str, *, symbols: list[str]):
        super().__init__(msg)
        self.symbols = symbols


class AmbiguousAuctionPrint(AlpacaError):
    """The primary exchange reported the requested condition at more than one
    price (Alpaca shows each price/exchange/condition triplet once [V], so one
    exchange CAN appear twice with different prices)."""


class UnmappedExchange(AlpacaError):
    """A symbol's primary listing exchange could not be turned into exactly one
    SIP exchange code. Raised rather than scoring against another venue."""


# Asset `exchange` (GET /v2/assets) -> the exact NAME that GET
# /v2/stocks/meta/exchanges gives that market; the live endpoint then supplies
# the code. ONLY verified pairs are here (docs/REFERENCES.md §12bl):
#   * "NYSE": every name in the book's universe has asset exchange "NYSE" [V: probe
#     results/ops/alpaca_probe/2026-09-28_cef.json, all 17 names];
#     "N": "New York Stock Exchange" is the example in Alpaca's reference for
#     /v2/stocks/meta/exchanges [V: docs.alpaca.markets/us/reference/
#     stockmetaexchanges-1, fetched 2026-09-28].
#   * "AMEX" (NYSE American; Alpaca's asset label, e.g. DHY, EAD, GGN) and
#     "NASDAQ" (e.g. CHW, QQQX), added 2026-10-29 for C4's nine non-NYSE funds
#     and prod's DHY/EAD. The code each prints under as PRIMARY:
#       - NYSE American is participant "A" on the CTA tape (CTS Pillar output
#         spec v2.11b, §4.3 "Participant ID": "A NYSE American, LLC"); its
#         names are tape B, which CTA carries with tape A's condition codes.
#       - Nasdaq is market center "Q" on the UTP tape (UTP Data Feed Services
#         spec v4.1, Sept 2026, §3.1 "Market Center Originator ID": "Nasdaq,
#         Inc. Q"); Nasdaq-listed names are tape C. The CTS's "T" (NASDAQ
#         Stock Market) is Nasdaq's prints in CTA-listed names, NOT a
#         Nasdaq-listed name's primary: Alpaca labels it "NASDAQ Int".
#       - The live table names those codes "A": "NYSE American (AMEX)" and
#         "Q": "NASDAQ OMX", one code per name; "NASDAQ Small Cap" (S) and
#         "NASDAQ Int" (T) are different rows [V: GET /v2/stocks/meta/exchanges,
#         read 2026-10-29 on the cef paper key, 24 entries].
#     The closing condition is "M" on both tapes, as for NYSE: Alpaca names tape
#     B's and tape C's "M" "Market Center Official Close" [V: GET
#     /v2/stocks/meta/conditions/trade?tape=B and ?tape=C, read 2026-10-29];
#     UTP §3.14.5 Note 3: "M" is "the 'official' closing value as determined by
#     a market center"; Nasdaq's Closing Cross price is its official close (SEC
#     Rel. 34-103341, SR-NASDAQ-2025-047). Tape C names its closing cross "6"
#     "Closing Prints" rather than "Market Center Closing Trade"; same code.
#     Checked 2026-10-29 on the 11 such funds (7 AMEX, 4 NASDAQ) x 4 sessions
#     (2026-10-14, 10-15, 10-26, 10-27): the primary's "M" equalled
#     Nasdaq.com's published close on 44 of 44, and another venue's "M" (Arca
#     "P", or "T") differed from it by half a cent or more on 29 of 44 -- the
#     primary-only filter is what makes the price right (REFERENCES §12bl).
# Any other asset exchange (ARCA, BATS, ...) raises UnmappedExchange: a name
# that moves listing needs a new, sourced row here, never a guessed one.
ASSET_EXCHANGE_SIP_NAME = {"NYSE": "New York Stock Exchange",
                           "AMEX": "NYSE American (AMEX)",
                           "NASDAQ": "NASDAQ OMX"}


# ------------------------------------------------------------ small parsers

def _require(obj: dict, fields, where: str) -> None:
    if not isinstance(obj, dict):
        raise UnexpectedResponse(f"{where}: expected a JSON object, got {type(obj).__name__}")
    missing = [f for f in fields if f not in obj]
    if missing:
        raise UnexpectedResponse(f"{where}: missing field(s) {missing}")


def _num(obj: dict, field: str, where: str) -> float:
    """A numeric field Alpaca sends as a string (or number). None/''/junk raises."""
    v = obj[field]
    if v is None or isinstance(v, bool):
        raise UnexpectedResponse(f"{where}: field {field!r} is {v!r}, not a number")
    try:
        return float(Decimal(str(v)))
    except InvalidOperation:
        raise UnexpectedResponse(f"{where}: field {field!r} = {v!r} is not a number") from None


def _whole(obj: dict, field: str, where: str) -> int:
    """A share count that must be a whole number (the runner never holds a fraction)."""
    v = obj[field]
    try:
        d = Decimal(str(v))
    except InvalidOperation:
        raise UnexpectedResponse(f"{where}: field {field!r} = {v!r} is not a number") from None
    if v is None or isinstance(v, bool) or d != d.to_integral_value():
        raise UnexpectedResponse(f"{where}: field {field!r} = {v!r} is not a whole number of shares")
    return int(d)


def _bool(obj: dict, field: str, where: str) -> bool:
    v = obj[field]
    if not isinstance(v, bool):
        raise UnexpectedResponse(f"{where}: field {field!r} = {v!r} is not a JSON boolean")
    return v


def parse_ts(s, where: str) -> dt.datetime:
    """RFC-3339 -> aware datetime. Alpaca can send nanoseconds, which
    `fromisoformat` rejects, so the fraction is cut to microseconds. A
    timestamp with no offset raises: a naive time is a guess about the zone."""
    if not isinstance(s, str):
        raise UnexpectedResponse(f"{where}: timestamp {s!r} is not a string")
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})$", s)
    if not m:
        raise UnexpectedResponse(f"{where}: timestamp {s!r} is not RFC-3339 with an offset")
    frac = (m.group(2) or "")[:7]          # '.' + at most 6 digits
    off = "+00:00" if m.group(3) == "Z" else m.group(3)
    return dt.datetime.fromisoformat(m.group(1) + frac + off)


def _iso_param(v, name: str) -> str:
    """A time filter for Alpaca. Aware datetimes and RFC-3339 strings pass;
    a naive datetime raises rather than being read in some default zone."""
    if isinstance(v, dt.datetime):
        if v.tzinfo is None:
            raise ValueError(f"{name}={v!r} is naive; pass a timezone-aware datetime")
        return v.isoformat()
    if isinstance(v, str):
        parse_ts(v, name)
        return v
    raise ValueError(f"{name}={v!r} must be an aware datetime or an RFC-3339 string")


def _date_param(v, name: str) -> dt.date:
    if isinstance(v, dt.datetime) or not isinstance(v, dt.date):
        raise ValueError(f"{name}={v!r} must be a datetime.date")
    return v


class Positions(NamedTuple):
    """`qty` is {symbol: signed whole shares}, long > 0, short < 0; `raw` is
    Alpaca's list as received, for the record."""
    qty: dict
    raw: list


class EODPoint(NamedTuple):
    """One session's end-of-day equity from GET /v2/account/portfolio/history.

    `date` is the session's New York date and `equity` Alpaca's figure in USD,
    so `for d, eq, _ in points` reads as the (session date, equity) pairs the
    caller wants. `stamp` is Alpaca's own timestamp for the point, kept because
    whether a point is final is the caller's question: it is not final while
    its stamp is still in the future (`eod_equity_history`)."""
    date: dt.date
    equity: float
    stamp: dt.datetime


# ---------------------------------------------------------------- the client

class AlpacaClient:
    """One book's Alpaca paper account. See the module docstring for the rules."""

    def __init__(self, book: str, env_file, base_url: str = PAPER_BASE,
                 data_url: str = DATA_BASE, *, session=None, sleep=time.sleep,
                 monotonic=time.monotonic):
        # Exact equality, not startswith: "https://paper-api.alpaca.markets.evil"
        # and a trailing path both start with the paper host.
        if base_url != PAPER_BASE:
            raise ValueError(f"refusing trading endpoint {base_url!r}: this client "
                             f"talks only to the paper endpoint {PAPER_BASE}")
        if data_url != DATA_BASE:
            raise ValueError(f"refusing data endpoint {data_url!r}: expected {DATA_BASE}")
        if not isinstance(book, str) or not re.fullmatch(r"[a-z0-9]+", book):
            raise ValueError(f"book {book!r} must be a lowercase name like 'cef'")
        self.book = book
        self._base = base_url
        self._data = data_url
        self._sleep = sleep
        self._monotonic = monotonic
        self._tokens = float(TRADING_BURST)       # the trading-host bucket (TRADING_MAX_PER_MIN)
        self._last = monotonic()
        key_id, secret = _load_keys(book, Path(env_file))
        if session is None:
            import requests
            session = requests.Session()
        # Header names from Alpaca's authentication docs [V]. The keys live
        # here and only here; `_scrub` reads them back from this dict.
        session.headers.update({"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret})
        refuse_redirects(session)
        self._session = session

    @classmethod
    def from_environment(cls, book: str, **kw) -> "AlpacaClient":
        """The runner's constructor: keys from the file named by QUANTT_ENV_FILE,
        which is required (RUNNER.md) -- an unset variable raises rather than
        falling back to `config/.env`, so a prod clone never silently reads a
        dev tree's keys."""
        path = os.environ.get("QUANTT_ENV_FILE", "")
        if not path:
            raise MissingCredential("QUANTT_ENV_FILE is not set: it must name the file "
                                    "holding this book's Alpaca keys")
        return cls(book, path, **kw)

    @property
    def trading_endpoint(self) -> str:
        """The trading endpoint this client talks to: today always PAPER_BASE, which
        the constructor enforces. Read-only (no setter), and reading it sends nothing.

        WHY IT EXISTS (CEF trial 55, te4; the runner's owner, 2026-11-03).
        `below_min_names = "trade_eligible"` is PAPER ONLY. The runner declares the
        account paper to the sleeve only when this reads exactly PAPER_BASE
        (`quantt/session/run.py` `thin_rule_for`), so the declaration rests on what
        the client says it talks to, not on an assumption about which client it is.
        A live-money client, if one is ever written, must answer differently here."""
        return self._base

    def __repr__(self) -> str:
        return f"AlpacaClient(book={self.book!r}, base_url={self._base!r}, data_url={self._data!r})"

    __str__ = __repr__

    # ------------------------------------------------------------ transport

    def _scrub(self, text: str) -> str:
        """Remove both key values from any text before it leaves this object."""
        for h in ("APCA-API-KEY-ID", "APCA-API-SECRET-KEY"):
            v = self._session.headers.get(h)
            if v:
                text = text.replace(v, "<redacted>")
        return text

    def _pace(self, base: str) -> None:
        """Take one token for a request to `base`; sleep first if the bucket is empty.

        Only the trading host is paced (TRADING_MAX_PER_MIN). After a wait the bucket holds
        exactly the one token the wait refilled, and the clock is moved on by the wait even
        if the injected `sleep` did not pass real time, so a test's fake sleep paces the same
        way the real one does: one request every 60 / TRADING_MAX_PER_MIN seconds."""
        if base != self._base:
            return
        rate = TRADING_MAX_PER_MIN / 60.0
        now = self._monotonic()
        self._tokens = min(float(TRADING_BURST), self._tokens + max(0.0, now - self._last) * rate)
        self._last = max(now, self._last)
        if self._tokens < 1.0:
            wait = (1.0 - self._tokens) / rate
            self._sleep(wait)
            self._tokens = 1.0
            self._last = max(self._monotonic(), self._last + wait)
        self._tokens -= 1.0

    def _get(self, base: str, path: str, params: dict | None = None, *,
             allow_404: bool = False):
        """GET with bounded retry on 429, 5xx and transport errors.

        Retrying is safe only because a GET changes nothing at the broker; the
        POST path never comes through here. Returns decoded JSON, or None for a
        404 when `allow_404`. Any other non-200, or a body that is not JSON,
        raises with the path and Alpaca's message -- never the request headers.
        A 3xx is never followed (`refuse_redirects`) and never retried: it raises,
        naming the status, and the `Location` it pointed at is not printed.
        """
        import requests
        url = base + path
        attempts = len(GET_BACKOFF_S) + 1
        last = ""
        for i in range(attempts):
            if i:
                self._sleep(GET_BACKOFF_S[i - 1])
            self._pace(base)
            try:
                r = self._session.get(url, params=params, timeout=TIMEOUT_S, allow_redirects=False)
            except requests.TooManyRedirects as e:      # `refuse_redirects`: a 3xx, not followed
                st = getattr(e.response, "status_code", None)
                raise AlpacaHTTPError(self._scrub(
                    f"GET {path} -> HTTP {st}: a redirect, NOT followed (following one would "
                    f"send the key headers to another host)"), status=st) from None
            except (requests.Timeout, requests.ConnectionError) as e:
                last = f"{type(e).__name__}: {e}"
                status = None
                continue
            status = r.status_code
            if status == 404 and allow_404:
                return None
            if 300 <= status < 400:
                raise AlpacaHTTPError(self._scrub(
                    f"GET {path} -> HTTP {status}: a redirect, NOT followed (following one would "
                    f"send the key headers to another host)"), status=status)
            if status == 429 or 500 <= status < 600:
                last = f"HTTP {status}: {r.text[:300]}"
                continue
            if status != 200:
                cls = AssetNotFound if (status == 404 and path.startswith("/v2/assets/")) else AlpacaHTTPError
                raise cls(self._scrub(f"GET {path} -> HTTP {status}: {r.text[:300]}"), status=status)
            try:
                return r.json()
            except ValueError:
                raise UnexpectedResponse(self._scrub(
                    f"GET {path} -> HTTP 200 with a body that is not JSON: {r.text[:300]}")) from None
        raise AlpacaHTTPError(self._scrub(
            f"GET {path} failed after {attempts} attempts; last: {last}"), status=status)

    # -------------------------------------------------------------- account

    ACCOUNT_NUMERIC = ("equity", "last_equity", "cash", "buying_power", "regt_buying_power",
                       "initial_margin", "maintenance_margin", "long_market_value",
                       "short_market_value")
    ACCOUNT_BOOL = ("shorting_enabled", "trading_blocked", "account_blocked",
                    "trade_suspended_by_user")

    def account(self) -> dict:
        """GET /v2/account, every field the runner may read required and parsed.

        Returns {"id", "status", "currency", "multiplier" (str: 1|2|4 [V]),
        the ACCOUNT_NUMERIC fields as float, the ACCOUNT_BOOL fields as bool,
        "raw"}. Alpaca marks only id/status required [V], but all of these were
        present in the 2026-09-28 probe of the cef account; if one ever goes
        missing the session must stop, not size against a default.
        `equity` is "cash + long_market_value + short_market_value" [V].
        """
        raw = self._get(self._base, "/v2/account")
        w = "GET /v2/account"
        _require(raw, ("id", "status", "currency", "multiplier",
                       *self.ACCOUNT_NUMERIC, *self.ACCOUNT_BOOL), w)
        out = {"id": raw["id"], "status": raw["status"], "currency": raw["currency"],
               "multiplier": str(raw["multiplier"]), "raw": raw}
        out.update({f: _num(raw, f, w) for f in self.ACCOUNT_NUMERIC})
        out.update({f: _bool(raw, f, w) for f in self.ACCOUNT_BOOL})
        return out

    def positions(self) -> Positions:
        """GET /v2/positions -> Positions(qty={symbol: signed int}, raw=[...]).

        The sign comes from `side` (long|short, documented [V]); the docs do not
        say whether `qty` is itself negative for a short [U, open question]. So
        a short with qty "-100" or "100" both become -100, and the one
        combination that is a contradiction under either convention -- a
        negative qty on a `long` -- raises. A fractional or zero qty raises: the
        runner only ever sends whole shares, so either is something it did not
        do and must not trade on top of. A symbol listed twice raises.
        """
        raw = self._get(self._base, "/v2/positions")
        if not isinstance(raw, list):
            raise UnexpectedResponse(f"GET /v2/positions: expected a list, got {type(raw).__name__}")
        qty: dict[str, int] = {}
        for i, p in enumerate(raw):
            w = f"GET /v2/positions[{i}]"
            _require(p, ("symbol", "qty", "side"), w)
            sym, side = p["symbol"], p["side"]
            n = _whole(p, "qty", f"{w} ({sym})")
            if n == 0:
                raise UnexpectedResponse(f"{w}: {sym} listed with qty 0")
            if side == "long":
                if n < 0:
                    raise UnexpectedResponse(f"{w}: {sym} side=long but qty={p['qty']!r} is negative")
                signed = n
            elif side == "short":
                signed = -abs(n)
            else:
                raise UnexpectedResponse(f"{w}: {sym} side={side!r} is not long|short")
            if sym in qty:
                raise UnexpectedResponse(f"GET /v2/positions: {sym} listed twice")
            qty[sym] = signed
        return Positions(qty=qty, raw=raw)

    # --------------------------------------------------------------- orders

    ORDER_FIELDS = ("id", "client_order_id", "status", "symbol", "side", "type",
                    "time_in_force", "submitted_at", "filled_qty")

    def orders(self, *, status: str, after=None, until=None,
               limit: int = ORDERS_MAX_LIMIT, nested: bool = False) -> list[dict]:
        """GET /v2/orders, every page, oldest first.

        `status` has no default on purpose (Alpaca's is `open` [V]): gate 6 asks
        "any order TODAY", which is `all`, and a silent `open` would hide an
        order that already filled. `after`/`until` filter on submission time,
        exclusive [V].

        Alpaca has no page token here [V]. This pages by time with
        `direction=asc` and `after=<cursor>`. The trap: `after` is exclusive, so
        advancing the cursor to the LAST order's `submitted_at` would skip any
        order that shares that timestamp but fell past the page boundary. So
        the cursor goes back to the last timestamp STRICTLY earlier than the
        page's final one, the overlap is re-fetched, and orders are deduplicated
        by id. A full page whose orders all share one timestamp cannot be paged
        without that risk, and raises. A page not in ascending order raises
        (the method's correctness rests on it). `before_order_id` /
        `after_order_id` are not used: they may not be combined with after/until [V].
        """
        if status not in ("open", "closed", "all"):
            raise ValueError(f"status={status!r} must be open|closed|all")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= ORDERS_MAX_LIMIT:
            raise ValueError(f"limit={limit!r} must be an int in 1..{ORDERS_MAX_LIMIT}")
        base = {"status": status, "limit": limit, "direction": "asc",
                "nested": "true" if nested else "false"}
        if until is not None:
            base["until"] = _iso_param(until, "until")
        cursor = _iso_param(after, "after") if after is not None else None
        cursor_dt = parse_ts(cursor, "after") if cursor else None

        out: list[dict] = []
        seen: set[str] = set()
        for _ in range(MAX_PAGES):
            params = dict(base)
            if cursor is not None:
                params["after"] = cursor
            page = self._get(self._base, "/v2/orders", params)
            if not isinstance(page, list):
                raise UnexpectedResponse(f"GET /v2/orders: expected a list, got {type(page).__name__}")
            times = []
            for i, o in enumerate(page):
                w = f"GET /v2/orders[{i}]"
                _require(o, self.ORDER_FIELDS, w)
                times.append(parse_ts(o["submitted_at"], f"{w}.submitted_at"))
                if o["id"] not in seen:
                    seen.add(o["id"])
                    out.append(o)
            if any(b < a for a, b in zip(times, times[1:])):
                raise UnexpectedResponse("GET /v2/orders: page not in ascending submitted_at "
                                         "order; time-cursor pagination would skip orders")
            if len(page) < limit:
                return out
            last = times[-1]
            earlier = [(t, o["submitted_at"]) for t, o in zip(times, page) if t < last]
            if not earlier:
                raise UnexpectedResponse(
                    f"GET /v2/orders: a full page of {limit} orders all submitted at "
                    f"{page[-1]['submitted_at']}; cannot page on time without skipping")
            new_dt, new_cursor = earlier[-1]
            if cursor_dt is not None and new_dt <= cursor_dt:
                raise UnexpectedResponse("GET /v2/orders: pagination made no progress")
            cursor, cursor_dt = new_cursor, new_dt
        raise UnexpectedResponse(f"GET /v2/orders: more than {MAX_PAGES} pages")

    def order_by_client_id(self, client_order_id: str) -> dict | None:
        """The order with this client_order_id, or None if Alpaca has none (404).

        This is how an AmbiguousSubmit is resolved, so the two answers must
        never be confused: 404 -> None, and every other failure (401, 5xx after
        retries, a body with a different id) raises. Behaviour when an id was
        reused after a fill is undocumented [U]; the runner never reuses one.
        """
        if not isinstance(client_order_id, str) or not _CID_RE.match(client_order_id):
            raise ValueError(f"client_order_id {client_order_id!r} is not a valid id")
        o = self._get(self._base, "/v2/orders:by_client_order_id",
                      {"client_order_id": client_order_id}, allow_404=True)
        if o is None:
            return None
        w = "GET /v2/orders:by_client_order_id"
        _require(o, self.ORDER_FIELDS, w)
        if o["client_order_id"] != client_order_id:
            raise UnexpectedResponse(f"{w}: asked for {client_order_id!r}, got "
                                     f"{o['client_order_id']!r}")
        return o

    def submit_order(self, symbol: str, qty: int, side: str, client_order_id: str, *,
                     time_in_force: str) -> dict:
        """POST /v2/orders: one market order. Called once; never retried here.

        Always `type=market`. `time_in_force` is REQUIRED and is `cls` (CLAUDE.md
        rule 3) or `day` -- the latter only for the paper account's late-market
        execution (team lead 2026-09-29, recorded exception: paper runs no
        closing auction). Nothing else is accepted; there is no default, so a
        caller cannot send the wrong kind by omission. `qty` is a positive Python int -- a float, even
        100.0, is refused, because a float qty is how a fraction gets in. The
        refusals happen before anything is sent.

        Outcomes:
          2xx, echo matches          -> the order dict
          2xx, echo differs          -> SubmitResponseInvalid (the order EXISTS)
          4xx                        -> OrderRejected (not accepted)
          5xx / timeout / connection
          error / unreadable 2xx     -> AmbiguousSubmit (look it up; never resend)
        A 5xx is ambiguous rather than rejected because a gateway can fail
        after the order service has accepted the order.
        """
        # --- refusals: nothing has been sent yet -------------------------
        if self._base != PAPER_BASE:                   # constructor checks too; belt and braces
            raise ValueError(f"refusing to submit to non-paper endpoint {self._base!r}")
        if not isinstance(symbol, str) or not _SYMBOL_RE.match(symbol):
            raise ValueError(f"symbol {symbol!r} is not an upper-case equity symbol")
        if type(qty) is not int or qty <= 0:
            raise ValueError(f"qty {qty!r} must be a positive int (whole shares; "
                             f"the side carries the sign)")
        if side not in ("buy", "sell"):
            raise ValueError(f"side {side!r} must be 'buy' or 'sell'")
        if not isinstance(client_order_id, str) or not _CID_RE.match(client_order_id):
            raise ValueError(f"client_order_id {client_order_id!r} must be 1-128 of [A-Za-z0-9._-]")
        if time_in_force not in ("cls", "day"):
            raise ValueError(f"time_in_force {time_in_force!r} must be 'cls' or 'day'")
        tif = time_in_force

        import requests
        payload = {"symbol": symbol, "qty": str(qty), "side": side, "type": "market",
                   "time_in_force": tif, "client_order_id": client_order_id}
        cid = client_order_id
        look = f"look it up with order_by_client_id({cid!r}); do NOT resend"
        self._pace(PAPER_BASE)
        try:
            r = self._session.post(PAPER_BASE + "/v2/orders", json=payload, timeout=TIMEOUT_S,
                                   allow_redirects=False)
        except requests.TooManyRedirects as e:          # `refuse_redirects`: a 3xx, not followed
            raise AmbiguousSubmit(self._scrub(
                f"POST /v2/orders {cid}: HTTP {getattr(e.response, 'status_code', None)}, a redirect, "
                f"NOT followed (following one would send the key headers and the order to another "
                f"host) -- {look}"), client_order_id=cid) from None
        except (requests.Timeout, requests.ConnectionError) as e:
            raise AmbiguousSubmit(self._scrub(
                f"POST /v2/orders {cid}: {type(e).__name__} -- the order may or may not "
                f"be at Alpaca; {look}"), client_order_id=cid) from None
        status = r.status_code
        if 300 <= status < 400:
            # Not followed (`refuse_redirects`). Whether the order exists is not known from a
            # 3xx, so it is the ambiguous case, never a rejection and never a resend.
            raise AmbiguousSubmit(self._scrub(
                f"POST /v2/orders {cid}: HTTP {status}, a redirect, NOT followed (following one "
                f"would send the key headers and the order to another host) -- {look}"),
                client_order_id=cid)
        if 400 <= status < 500:
            raise OrderRejected(self._scrub(
                f"POST /v2/orders {cid} ({side} {qty} {symbol} {tif}) rejected: "
                f"HTTP {status}: {r.text[:300]}"), status=status, client_order_id=cid)
        if not 200 <= status < 300:
            raise AmbiguousSubmit(self._scrub(
                f"POST /v2/orders {cid}: HTTP {status}: {r.text[:300]} -- {look}"),
                client_order_id=cid)
        try:
            o = r.json()
        except ValueError:
            raise AmbiguousSubmit(self._scrub(
                f"POST /v2/orders {cid}: HTTP {status} with an unreadable body -- {look}"),
                client_order_id=cid) from None

        # --- the order exists; check Alpaca recorded what we sent ---------
        w = f"POST /v2/orders {cid}"
        oid = o.get("id") if isinstance(o, dict) else None
        problems = []
        if not isinstance(o, dict):
            problems.append(f"body is {type(o).__name__}, not an object")
        else:
            for f, want in (("client_order_id", cid), ("symbol", symbol), ("side", side),
                            ("type", "market"), ("time_in_force", tif)):
                if o.get(f) != want:
                    problems.append(f"{f}={o.get(f)!r} (sent {want!r})")
            try:
                if Decimal(str(o.get("qty"))) != qty:
                    problems.append(f"qty={o.get('qty')!r} (sent {qty})")
            except InvalidOperation:
                problems.append(f"qty={o.get('qty')!r} (sent {qty})")
            if not oid:
                problems.append("no order id")
        if problems:
            raise SubmitResponseInvalid(self._scrub(
                f"{w}: Alpaca ACCEPTED an order (HTTP {status}) but " + "; ".join(problems)
                + f" -- the order exists; {look}"), client_order_id=cid, order_id=oid)
        return o

    # ---------------------------------------------------------- clock etc.

    def clock(self) -> dict:
        """GET /v2/clock -> {"timestamp", "next_open", "next_close" (aware
        datetimes), "is_open" (bool), "raw"}.

        `is_open` means the market is open RIGHT NOW [V], not "today is a
        trading day"; gate 4 should use `calendar` for the latter.
        """
        raw = self._get(self._base, "/v2/clock")
        w = "GET /v2/clock"
        _require(raw, ("timestamp", "is_open", "next_open", "next_close"), w)
        return {"timestamp": parse_ts(raw["timestamp"], f"{w}.timestamp"),
                "is_open": _bool(raw, "is_open", w),
                "next_open": parse_ts(raw["next_open"], f"{w}.next_open"),
                "next_close": parse_ts(raw["next_close"], f"{w}.next_close"),
                "raw": raw}

    def calendar(self, start: dt.date, end: dt.date) -> list[dict]:
        """GET /v2/calendar for [start, end] inclusive [V] ->
        [{"date": date, "open": "HH:MM", "close": "HH:MM", "raw"}].

        `open`/`close` are returned as Alpaca's wall-clock strings and NOT
        attached to a timezone: the docs do not state one [U]. Presumably ET;
        the caller that turns them into a cutoff must say so explicitly. A day
        outside the range asked for raises.
        """
        start, end = _date_param(start, "start"), _date_param(end, "end")
        if end < start:
            raise ValueError(f"end {end} is before start {start}")
        raw = self._get(self._base, "/v2/calendar",
                        {"start": start.isoformat(), "end": end.isoformat()})
        if not isinstance(raw, list):
            raise UnexpectedResponse(f"GET /v2/calendar: expected a list, got {type(raw).__name__}")
        out = []
        for i, row in enumerate(raw):
            w = f"GET /v2/calendar[{i}]"
            _require(row, ("date", "open", "close"), w)
            if not (isinstance(row["date"], str) and _DATE_RE.match(row["date"])):
                raise UnexpectedResponse(f"{w}: date {row['date']!r} is not YYYY-MM-DD")
            d = dt.date.fromisoformat(row["date"])
            if not start <= d <= end:
                raise UnexpectedResponse(f"{w}: {d} is outside the requested {start}..{end}")
            for f in ("open", "close"):
                if not (isinstance(row[f], str) and _HHMM_RE.match(row[f])):
                    raise UnexpectedResponse(f"{w}: {f} {row[f]!r} is not HH:MM")
            out.append({"date": d, "open": row["open"], "close": row["close"], "raw": row})
        return out

    ASSET_BOOL = ("tradable", "shortable", "marginable", "fractionable")

    def asset(self, symbol: str) -> dict:
        """GET /v2/assets/<symbol>, required fields present and typed; the raw
        dict is returned. 404 raises AssetNotFound.

        `borrow_status` (easy_to_borrow|hard_to_borrow [V]) is checked against
        its enum when present but not required, and `easy_to_borrow` is not
        read: only the former is in the schema [V]. Whether gate 7 needs
        `easy_to_borrow` status as well as `shortable` is a team-lead question.
        Both change daily; a result is true on its date only.
        """
        if not isinstance(symbol, str) or not _SYMBOL_RE.match(symbol):
            raise ValueError(f"symbol {symbol!r} is not an upper-case equity symbol")
        raw = self._get(self._base, f"/v2/assets/{symbol}")
        w = f"GET /v2/assets/{symbol}"
        _require(raw, ("symbol", "status", "exchange", *self.ASSET_BOOL), w)
        for f in self.ASSET_BOOL:
            _bool(raw, f, w)
        if raw["symbol"] != symbol:
            raise UnexpectedResponse(f"{w}: returned symbol {raw['symbol']!r}")
        if "borrow_status" in raw and raw["borrow_status"] not in ("easy_to_borrow", "hard_to_borrow"):
            raise UnexpectedResponse(f"{w}: borrow_status {raw['borrow_status']!r} is not a documented value")
        return raw

    def assets(self, *, status: str = "active", asset_class: str = "us_equity") -> list[dict]:
        """GET /v2/assets: every asset in one response, as compact typed rows.

        One row per asset: symbol, exchange, status, the ASSET_BOOL flags, and,
        when Alpaca sends them, easy_to_borrow, borrow_status and the margin
        requirements. An absent optional field is None, never a guessed value.

        WHY. The daily borrow snapshot (collector step `borrow_snapshot`,
        `results/cef/RESEARCH_PLAN_2026-10-09.md` 0.3). Borrow flags change daily:
        AWF and MHD were shortable on 2026-09-28 and not on 2026-10-08. Research
        on short sleeves needs the history, and Alpaca keeps none. A row is true
        at its read time only.

        The response is one unpaged list [V: one call returned 14,392 rows,
        2026-10-08]. A repeated symbol raises: two rows for one name cannot both
        be the flag.
        """
        if status not in ("active", "inactive"):
            raise ValueError(f"status {status!r} must be active|inactive")
        if asset_class not in ("us_equity",):
            raise ValueError(f"asset_class {asset_class!r}: only us_equity is used here")
        raw = self._get(self._base, "/v2/assets", {"status": status, "asset_class": asset_class})
        w = "GET /v2/assets"
        if not isinstance(raw, list):
            raise UnexpectedResponse(f"{w}: expected a list, got {type(raw).__name__}")
        out, seen = [], set()
        for i, a in enumerate(raw):
            wi = f"{w}[{i}]"
            _require(a, ("symbol", "status", "exchange", *self.ASSET_BOOL), wi)
            sym = a["symbol"]
            if not isinstance(sym, str) or not sym:
                raise UnexpectedResponse(f"{wi}: symbol {sym!r} is not a non-empty string")
            if sym in seen:
                raise UnexpectedResponse(f"{wi}: symbol {sym!r} listed twice")
            seen.add(sym)
            row = {"symbol": sym, "exchange": a["exchange"], "status": a["status"]}
            for f in self.ASSET_BOOL:
                row[f] = _bool(a, f, wi)
            row["easy_to_borrow"] = _bool(a, "easy_to_borrow", wi) if a.get("easy_to_borrow") is not None else None
            bs = a.get("borrow_status")
            if bs is not None and bs not in ("easy_to_borrow", "hard_to_borrow"):
                raise UnexpectedResponse(f"{wi}: borrow_status {bs!r} is not a documented value")
            row["borrow_status"] = bs
            for f in ("maintenance_margin_requirement", "margin_requirement_long",
                      "margin_requirement_short"):
                row[f] = _num(a, f, wi) if a.get(f) not in (None, "") else None
            out.append(row)
        return out

    EOD_LISTS = ("timestamp", "equity", "profit_loss", "profit_loss_pct")
    # A 1D point is stamped this many hours of New York wall-clock time after its
    # session's calendar close (measured, `eod_equity_history` docstring).
    EOD_STAMP_AFTER_CLOSE_H = 4

    def eod_equity_history(self, start: dt.date, end: dt.date) -> list[EODPoint]:
        """Alpaca's end-of-day equity for every funded session in [start, end], oldest first.

        GET /v2/account/portfolio/history with `period` and `timeframe=1D` only,
        the request shape read live on 2026-10-19 (docs/REFERENCES.md §12an).
        Returns [EODPoint(date, equity, stamp)]: (session date in New York,
        equity in USD, Alpaca's timestamp for the point).

        WHY. The team lead ruled on 2026-10-19 that this series is the paper
        book's official daily P&L of record (`docs/SYSTEM.md` §5). The account's
        `equity - last_equity`, read at 17:30 ET, is a snapshot marked after
        the close. On the four days compared it disagreed with this series, which
        agreed with the auction-marked score (`quantt/session/score.py`).

        THE DATE OF A POINT. Alpaca documents 1D timestamps only as epoch
        seconds, "left-labeled (the beginning of time window)", with entries only
        for days the market is open [V: reference, fetched 2026-10-19]. What was
        actually read on 2026-10-19 contradicts "beginning": the 2026-10-16 close
        is stamped 2026-10-17T00:00Z, which is 2026-10-16 20:00 in New York.
        Alpaca's own 1D example agrees: every stamp is 00:00Z, and the last is a
        Saturday, which only a Friday session can carry. So two things are
        required of every stamp, or the call raises naming it:
          * its New York date, the session date, is a trading day by
            `calendar` (the client's own method, one more GET); and
          * its New York wall-clock time is exactly that day's calendar
            `close` plus 4 hours: 20:00:00 after a 16:00 close, 17:00:00 after
            a 13:00 close.
        HOW THE SECOND RULE WAS MEASURED. Until 2026-11-14 it was "exactly
        20:00:00 New York", from full days only (00:00Z on EDT, 01:00Z on EST
        [V: a peer's read-only GET, 2026-11-02 23:49Z]; before 2026-11-02 it
        was "exactly 00:00 UTC", which refused every winter point). A half day
        is stamped 17:00. Read 2026-11-14 on the cef paper account, `period=3A`,
        754 points [V]: all 747 sessions with a 16:00 calendar close are stamped
        20:00:00 New York, and all 7 with a 13:00 close (2023-11-24, 2024-07-03,
        2024-11-29, 2024-12-24, 2025-07-03, 2025-11-28, 2025-12-24; two on EDT,
        five on EST) are stamped 17:00:00. The five before 2025-11 carry the
        pre-funding equity 0, so the rule rests on two funded half-day points
        and five unfunded ones. A peer session found the first one the same day.
        The old rule would have refused the 2026-11-27 point, and every read
        whose window reached it, since every point is checked before the
        window is applied: the collector's EOD step would have raised on each
        run from that evening. No close other than 16:00 and 13:00 has been
        seen; another one is held to the same close + 4 hours and raises if
        Alpaca stamps it differently [U].
        NOT MEASURED: whether a half day's point is final at its 17:00 stamp.
        Both funded half-day points were read about a year later. A caller
        that treats "stamp has passed" as finished (the collector's EOD step,
        verify's official line) will take a half day's point from 17:00 ET, so
        a 17:30 verify can print it the same evening, where a full day's is
        PENDING until 20:00. The collector re-reads the whole history each data
        day and logs EOD_REVISED if it moved; 2026-11-27 is the first live case.
        This also reads `calendar`'s `close` as New York wall-clock time, which
        the calendar docs do not state; the 754 points agree with that reading.
        Each rule catches a change that would otherwise file sessions under the
        wrong date. A session stamped at New York midnight after it (04:00Z,
        or 05:00Z in winter) falls on the next date, which trades Monday to
        Thursday; the second rule refuses it. A session stamped at the start of
        its own UTC day ("left-labeled") is 20:00 the previous evening in
        summer and 19:00 in winter: the second rule refuses it in winter, and
        the first catches it on every Monday in summer, since every read spans
        months. The second rule also refuses an intraday reading, a stamp at the
        read time or at the close, which could pass for a finished day, a
        winter 00:00Z (19:00 EST), a 17:00 stamp on a full day and a 20:00
        stamp on a half day. Any other convention still raises from its
        first point, and the official figure is PENDING until a person looks:
        a loud stop, never a wrong date (`docs/REFERENCES.md` §12an). Every
        point in the response is checked, those after `end` included, before
        the window is applied.

        PRE-FUNDING ZEROS ARE DROPPED, BY NAME. Alpaca returns equity 0 for the
        days before the account was funded (read 2026-10-19). Those leading zeros
        are not sessions of this book and are removed here: every point before
        the first non-zero equity. A zero AFTER the account was funded is not
        that, and raises; so does a null, a non-finite number, a boolean, or a
        non-integer timestamp. The four lists must be the same length and the
        stamps strictly increasing.

        WHAT THIS DOES NOT DECIDE. Whether a point is final. Alpaca documents
        neither when a day's point first appears nor whether it can change later
        [V negative: reference, fetched 2026-10-19]. The stamp is returned so the
        caller can refuse a point whose stamp is still in the future at the time
        it was read: that day's window may not have closed. Points dated after
        `end` (an unfinished session, if Alpaca serves one) are validated and
        then left out, as are points before `start`.

        The window asked for is `period=<n>M`, enough whole months to reach
        `start` with a month to spare. A period is measured back from Alpaca's
        default end, which is at or after `end` for every caller here.
        """
        start, end = _date_param(start, "start"), _date_param(end, "end")
        if end < start:
            raise ValueError(f"end {end} is before start {start}")
        months = (end.year - start.year) * 12 + (end.month - start.month) + 2
        raw = self._get(self._base, "/v2/account/portfolio/history",
                        {"period": f"{months}M", "timeframe": "1D"})
        w = "GET /v2/account/portfolio/history"
        _require(raw, (*self.EOD_LISTS, "timeframe"), w)
        if raw["timeframe"] != "1D":
            raise UnexpectedResponse(f"{w}: timeframe {raw['timeframe']!r}, asked for '1D'")
        for k in self.EOD_LISTS:
            if not isinstance(raw[k], list):
                raise UnexpectedResponse(f"{w}: {k} is {type(raw[k]).__name__}, not a list")
        lengths = {k: len(raw[k]) for k in self.EOD_LISTS}
        if len(set(lengths.values())) != 1:
            raise UnexpectedResponse(f"{w}: lists of unequal length {lengths}")

        stamps, equities = [], []
        for i, (ts, eq) in enumerate(zip(raw["timestamp"], raw["equity"])):
            if type(ts) is not int:
                raise UnexpectedResponse(f"{w}: timestamp[{i}] = {ts!r} is not integer epoch seconds")
            # An integer outside datetime's range raises a bare ValueError,
            # OverflowError or OSError, which verify would report as a "verify
            # error" FAIL (review 2026-10-19). It is a bad response, so refuse it
            # like every other bad shape.
            try:
                when = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
            except (ValueError, OverflowError, OSError):
                raise UnexpectedResponse(
                    f"{w}: timestamp[{i}] = {ts} is outside the clock's range") from None
            x = _num({"equity": eq}, "equity", f"{w} [{i}]")      # None/bool/junk raise
            if not math.isfinite(x):
                raise UnexpectedResponse(f"{w}: equity[{i}] = {eq!r} is not finite")
            stamps.append(when)
            equities.append(x)
        if any(b <= a for a, b in zip(stamps, stamps[1:])):
            raise UnexpectedResponse(f"{w}: timestamps are not strictly increasing")
        if not stamps:
            return []

        local = [s.astimezone(NY) for s in stamps]
        # One /v2/calendar read gives each session's close. A stamp must sit on
        # a trading day, at that day's close + EOD_STAMP_AFTER_CLOSE_H hours of
        # New York wall-clock time (docstring: 20:00 full day, 17:00 half day).
        # Each date has exactly one accepted time, and the stamps are strictly
        # increasing, so no two points can share a session.
        cal = {}
        for row in self.calendar(local[0].date(), local[-1].date()):
            # A date served twice with two closes would let the later row pick
            # the accepted time (review 2026-11-14): a 17:00 stamp on a full day
            # would pass if a second row said 13:00.
            if row["date"] in cal:
                raise UnexpectedResponse(
                    f"{w}: /v2/calendar lists {row['date']} twice (closes {cal[row['date']]} "
                    f"and {row['close']}); the session's close is not known")
            cal[row["date"]] = row["close"]
        for s, t in zip(stamps, local):
            if t.date() not in cal:
                raise UnexpectedResponse(
                    f"{w}: stamp {s.isoformat()} is {t.isoformat()} in New York, and {t.date()} "
                    f"is not a trading day by /v2/calendar; the point cannot be given a session")
            close = cal[t.date()]
            ch, cm = int(close[:2]), int(close[3:])
            if ch + self.EOD_STAMP_AFTER_CLOSE_H > 23 or cm > 59:
                raise UnexpectedResponse(
                    f"{w}: /v2/calendar gives {t.date()} a {close} close; "
                    f"{self.EOD_STAMP_AFTER_CLOSE_H} hours after it is not a time on that "
                    f"date, and no such session has been seen. Refused rather than placed "
                    f"on a session")
            want = dt.time(ch + self.EOD_STAMP_AFTER_CLOSE_H, cm)
            if t.time() != want:
                raise UnexpectedResponse(
                    f"{w}: stamp {s.isoformat()} is {t.isoformat()} in New York, not "
                    f"{want.isoformat()} local, which is {t.date()}'s {close} close by "
                    f"/v2/calendar plus {self.EOD_STAMP_AFTER_CLOSE_H} hours; every 1D stamp "
                    f"seen is 20:00 New York on a full day and 17:00 on a 13:00 close (read "
                    f"2026-11-14, 754 points). Refused rather than placed on a session")

        funded = next((i for i, x in enumerate(equities) if x != 0), len(equities))
        later_zero = [local[i].date().isoformat() for i in range(funded, len(equities))
                      if equities[i] == 0]
        if later_zero:
            raise UnexpectedResponse(f"{w}: equity 0 on {later_zero}, after the account was "
                                     f"funded; only the days before funding may be 0")
        return [EODPoint(local[i].date(), equities[i], stamps[i])
                for i in range(funded, len(equities)) if start <= local[i].date() <= end]

    FILL_FIELDS = ("id", "activity_type", "order_id", "symbol", "side", "qty", "price",
                   "cum_qty", "leaves_qty", "transaction_time", "type", "order_status")

    def activities_fills(self, date: dt.date) -> list[dict]:
        """GET /v2/account/activities/FILL for one date, every page, oldest first.

        Pages with `page_token` = the id of the last row [V], `page_size` 100
        (the max [V]); a short page ends it, a repeated token raises. `date`
        filters on created_at, not settlement [V]. Rows are returned raw after
        their fields are checked; `qty`/`price` stay strings for the caller to
        parse with its own provenance. Partial fills are expected on paper
        ("a random size 10% of the time" [V]).
        """
        date = _date_param(date, "date")
        out, seen, token = [], set(), None
        for _ in range(MAX_PAGES):
            params = {"date": date.isoformat(), "direction": "asc", "page_size": FILL_PAGE_SIZE}
            if token is not None:
                params["page_token"] = token
            page = self._get(self._base, "/v2/account/activities/FILL", params)
            if not isinstance(page, list):
                raise UnexpectedResponse(f"GET /v2/account/activities/FILL: expected a list, "
                                         f"got {type(page).__name__}")
            for i, a in enumerate(page):
                w = f"GET /v2/account/activities/FILL[{i}]"
                _require(a, self.FILL_FIELDS, w)
                if a["activity_type"] != "FILL":
                    raise UnexpectedResponse(f"{w}: activity_type {a['activity_type']!r}")
                if a["type"] not in ("fill", "partial_fill"):
                    raise UnexpectedResponse(f"{w}: type {a['type']!r} is not fill|partial_fill")
                if a["id"] not in seen:
                    seen.add(a["id"])
                    out.append(a)
            if len(page) < FILL_PAGE_SIZE:
                return out
            nxt = page[-1]["id"]
            if nxt == token:
                raise UnexpectedResponse("GET /v2/account/activities/FILL: page_token did not advance")
            token = nxt
        raise UnexpectedResponse(f"GET /v2/account/activities/FILL: more than {MAX_PAGES} pages")

    # ---------------------------------------------------------- market data

    def stock_exchanges(self) -> dict:
        """GET {DATA_BASE}/v2/stocks/meta/exchanges: {SIP code: exchange name} [V,
        schema "additionalProperties: string"]. Every key and value must be a
        non-empty string; any other shape raises (including a wrapped object,
        which the reference does not show -- first live read is [U])."""
        w = "GET /v2/stocks/meta/exchanges"
        body = self._get(self._data, "/v2/stocks/meta/exchanges")
        if not isinstance(body, dict) or not body:
            raise UnexpectedResponse(f"{w}: expected a non-empty object, got "
                                     f"{type(body).__name__}")
        for k, v in body.items():
            if not (isinstance(k, str) and k and isinstance(v, str) and v):
                raise UnexpectedResponse(f"{w}: entry {k!r}: {v!r} is not code -> name strings")
        return dict(body)

    def primary_sip_code(self, symbol: str, exchanges: dict) -> str:
        """The SIP exchange code of `symbol`'s primary listing, today.

        WHY. "On open/on close orders are routed to the primary exchange" [V],
        so the official closing-auction print is the PRIMARY exchange's.
        Several market centers publish a condition-M "official close" each day
        [V], and on a day the primary had no auction trade another venue's M
        print may be the only one -- accepting it would score fills against a
        price the order never saw. Asset `exchange` -> name
        (ASSET_EXCHANGE_SIP_NAME) -> code (`exchanges`, from
        `stock_exchanges()`), with exactly one match or UnmappedExchange.
        The asset is read today; a listing move between the session and
        verify is not detected [U].
        """
        ex = self.asset(symbol)["exchange"]
        name = ASSET_EXCHANGE_SIP_NAME.get(ex)
        if name is None:
            raise UnmappedExchange(f"{symbol}: asset exchange {ex!r} has no verified SIP "
                                   f"name in ASSET_EXCHANGE_SIP_NAME")
        codes = sorted(k for k, v in exchanges.items() if v == name)
        if len(codes) != 1:
            raise UnmappedExchange(f"{symbol}: {len(codes)} SIP codes named {name!r} in "
                                   f"/v2/stocks/meta/exchanges ({codes}); need exactly one")
        return codes[0]

    def closing_auction_prints(self, symbols, date: dt.date, *, exchange_codes: dict,
                               condition: str = "M") -> dict:
        """The official closing-auction print per symbol on `date`, from the data API.

        GET {DATA_BASE}/v2/stocks/auctions, feed=sip ("Only sip is valid for
        auctions" [V]), start=end=date, every page. Returns
        {symbol: {"price": float, "exchange": x, "condition": c, "t": str}}.

        WHICH PRINT. Alpaca returns several closing prints per day from
        different exchanges [V]. `condition` defaults to "M", "Market Center
        Official Close" in Alpaca's condition table on tapes A, B and C alike
        [V: read 2026-10-29], so one default serves NYSE, NYSE American and
        Nasdaq listings (ASSET_EXCHANGE_SIP_NAME); "6" is "Market Center
        Closing Trade" (tape C: "Closing Prints") (M vs 6 is still a design
        choice [U]). `exchange_codes`
        is REQUIRED and must name the primary listing's SIP code for every
        symbol (`primary_sip_code`); only that exchange's prints count.
        (Review 2026-09-28: the first build accepted any exchange's print when
        they agreed, so a day the primary had no auction scored against
        another venue's close -- a confident wrong number.)

        A symbol with no matching print from its primary exchange raises
        MissingAuctionPrint naming every such symbol: another venue's print
        and a daily bar close are never substituted.

        TWO PRICES FROM THE PRIMARY (team lead's ruling, 2026-11-22, by question
        prompt: "Take the later print if the daily bar agrees"). On 2026-11-20
        NYSE sent two condition-M prints for SCD: 14.348 (1,400 shares,
        16:00:02 ET) and 14.28 (300 shares, 16:10:00 ET); the consolidated daily
        bar closed at 14.28 [V: GET only, 2026-11-22]. Until then two prices
        raised, and one such fund-day stalled C4's collector and the shadow
        books' marks for a weekend. The rule: the print with the LATEST
        timestamp is the official close if, and only if, its price equals the
        close of that day's raw SIP daily bar; the earlier prices are returned
        under "superseded" so a caller can say so. The bar never supplies the
        price, it only confirms which of the exchange's own prints stood. Any
        other case raises AmbiguousAuctionPrint, naming the prints and the bar:
        the latest two prints share a timestamp, there is no bar for the day,
        or the bar's close is not the later print.
        """
        date = _date_param(date, "date")
        if isinstance(symbols, str):
            raise ValueError("symbols must be a list of symbols, not one string")
        syms = sorted(set(symbols))
        if not syms:
            raise ValueError("symbols is empty")
        for s in syms:
            if not isinstance(s, str) or not _SYMBOL_RE.match(s):
                raise ValueError(f"symbol {s!r} is not an upper-case equity symbol")
        if not isinstance(exchange_codes, dict):
            raise ValueError("exchange_codes must be {symbol: primary SIP code}")
        no_code = [s for s in syms if not (isinstance(exchange_codes.get(s), str)
                                           and exchange_codes[s])]
        if no_code:
            raise ValueError(f"no primary-exchange SIP code for {no_code}; another venue's "
                             f"print is never used")

        # EXPLICIT TIMESTAMPS, NOT A BARE DATE. With end=<date> Alpaca reads the
        # window as running up to now, and the Basic plan refuses any SIP query
        # that touches the last 15 minutes: HTTP 403 "subscription does not
        # permit querying recent SIP data", for every symbol, every day [V: run
        # 2026-09-28 19:50 ET against the cef paper account]. The same query
        # with start/end as timestamps returned the day's prints. The window is
        # the whole ET calendar day up to 16:30 ET -- the closing auction prints
        # at 16:00 (13:00 on an early close), and verify runs at 17:30, so the
        # end is always more than 15 minutes old by then.
        start_ts = dt.datetime.combine(date, dt.time(0, 0), NY).astimezone(dt.timezone.utc)
        end_ts = dt.datetime.combine(date, dt.time(16, 30), NY).astimezone(dt.timezone.utc)
        days: dict[str, list] = {}
        token = None
        for _ in range(MAX_PAGES):
            params = {"symbols": ",".join(syms),
                      "start": start_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "end": end_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "feed": "sip", "limit": AUCTIONS_MAX_LIMIT}
            if token is not None:
                params["page_token"] = token
            body = self._get(self._data, "/v2/stocks/auctions", params)
            w = "GET /v2/stocks/auctions"
            _require(body, ("auctions",), w)
            auctions = body["auctions"]
            if auctions is None:           # a page with no data at all
                auctions = {}
            if not isinstance(auctions, dict):
                raise UnexpectedResponse(f"{w}: auctions is {type(auctions).__name__}, not an object")
            for sym, rows in auctions.items():
                if sym not in syms:
                    raise UnexpectedResponse(f"{w}: returned unrequested symbol {sym!r}")
                if not isinstance(rows, list):
                    raise UnexpectedResponse(f"{w}: auctions[{sym}] is not a list")
                days.setdefault(sym, []).extend(rows)
            nxt = body.get("next_page_token")
            if not nxt:
                break
            if nxt == token:
                raise UnexpectedResponse(f"{w}: next_page_token did not advance")
            token = nxt
        else:
            raise UnexpectedResponse(f"GET /v2/stocks/auctions: more than {MAX_PAGES} pages")

        out, missing = {}, []
        for sym in syms:
            prints = []
            for j, day in enumerate(days.get(sym, [])):
                w = f"GET /v2/stocks/auctions {sym}[{j}]"
                _require(day, ("d",), w)
                # `d` is documented as the date [V]; its exact format is not
                # shown, so only its first ten characters are compared.
                if not (isinstance(day["d"], str) and _DATE_RE.match(day["d"][:10])):
                    raise UnexpectedResponse(f"{w}: d {day['d']!r} does not start with YYYY-MM-DD")
                if day["d"][:10] != date.isoformat():
                    raise UnexpectedResponse(f"{w}: day {day['d']!r} is not the requested {date}")
                closes = day.get("c") or []
                if not isinstance(closes, list):
                    raise UnexpectedResponse(f"{w}: c is not a list")
                for k, p in enumerate(closes):
                    _require(p, ("t", "x", "p", "c"), f"{w}.c[{k}]")
                    if p["c"] == condition:
                        prints.append(p)
            prints = [p for p in prints if p["x"] == exchange_codes[sym]]
            if not prints:
                missing.append(sym)
                continue
            prices = {_num(p, "p", f"auction {sym}") for p in prints}
            if len(prices) > 1:
                p, superseded = self._later_print_the_bar_confirms(
                    sym, date, prints, condition, start_ts, end_ts)
                out[sym] = {"price": _num(p, "p", f"auction {sym}"), "exchange": p["x"],
                            "condition": p["c"], "t": p["t"], "superseded": superseded}
                continue
            p = prints[0]
            out[sym] = {"price": prices.pop(), "exchange": p["x"], "condition": p["c"],
                        "t": p["t"]}
        if missing:
            raise MissingAuctionPrint(
                f"no closing-auction print with condition {condition!r} on {date} for "
                f"{missing} from the primary exchange "
                f"{ {s: exchange_codes[s] for s in missing} }; another venue's print and a bar "
                f"close are not substituted", symbols=missing)
        return out

    def _later_print_the_bar_confirms(self, sym: str, date: dt.date, prints: list,
                                      condition: str, start_ts: dt.datetime,
                                      end_ts: dt.datetime) -> tuple[dict, list]:
        """(the later print, the superseded prices) when the primary sent more than one
        price at `condition` and the day's daily bar closes on the later one; otherwise
        raises AmbiguousAuctionPrint (`closing_auction_prints`, "TWO PRICES").

        The bar is asked for with the auction query's own timestamps, never a bare date:
        a date-only `end` reaches into the 15 minutes the data plan refuses on the
        evening of the day itself (the same 403 as above). ALIGNMENT: the one bar used
        must be dated `date` in New York; any other raises."""
        pairs = sorted((p["x"], p["p"], p["t"]) for p in prints)
        what = (f"{sym} {date}: primary exchange {prints[0]['x']!r} has more than one "
                f"condition {condition!r} price {[(x, px) for x, px, _ in pairs]}")
        timed = sorted(((parse_ts(p["t"], f"auction {sym}"), _num(p, "p", f"auction {sym}"), p)
                        for p in prints), key=lambda r: r[0])
        last_t, last_px, last = timed[-1]
        if any(t == last_t and px != last_px for t, px, _ in timed[:-1]):
            raise AmbiguousAuctionPrint(f"{what}; the latest two share the timestamp {last['t']}, "
                                        "so neither is the later print")
        w = f"GET /v2/stocks/bars {sym}"
        body = self._get(self._data, "/v2/stocks/bars",
                         {"symbols": sym, "timeframe": "1Day", "adjustment": "raw", "feed": "sip",
                          "start": start_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "end": end_ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "limit": 10})
        _require(body, ("bars",), w)
        bars = body["bars"]
        if bars is None:
            bars = {}
        if not isinstance(bars, dict):
            raise UnexpectedResponse(f"{w}: bars is {type(bars).__name__}, not an object")
        rows = bars.get(sym) or []
        if not isinstance(rows, list):
            raise UnexpectedResponse(f"{w}: bars[{sym}] is not a list")
        if len(rows) != 1:
            raise AmbiguousAuctionPrint(f"{what}; {len(rows)} daily bar(s) for {date} to confirm the "
                                        "later print with, so nothing is chosen")
        _require(rows[0], ("t", "c"), w)
        bar_day = parse_ts(rows[0]["t"], w).astimezone(NY).date()
        if bar_day != date:
            raise UnexpectedResponse(f"{w}: bar dated {bar_day} returned for {date}")
        bar_c = _num(rows[0], "c", w)
        if abs(bar_c - last_px) > 1e-9:
            raise AmbiguousAuctionPrint(f"{what}; the later print is {last_px} at {last['t']} but the "
                                        f"daily bar closes at {bar_c}, so nothing is chosen")
        superseded = [{"price": px, "t": p["t"]} for _, px, p in timed[:-1] if px != last_px]
        return last, superseded

    def distributions(self, symbols, start: dt.date, end: dt.date) -> list[dict]:
        """Cash dividends and capital-gains distributions for `symbols`, from the data API.

        GET {DATA_BASE}/v1/corporate-actions, types=cash_dividend,
        capital_gains_distribution, every page [V: endpoint reference, fetched
        2026-10-09]. Returns one dict per event:
            {"id", "symbol", "ex_date": date, "amount": float, "kind",
             "special": bool | None, "sub_type": str | None}
        `amount` is the cash per share: a cash dividend's `rate`, or a capital-gains
        event's `long_term_rate` + `short_term_rate` (the reference says at least one
        is always present; one that has neither raises).

        WHY. Alpaca paper credits no dividends [V: paper-trading docs], so the
        distribution-adjusted P&L line (team lead 2026-10-09, `docs/SYSTEM.md` §5)
        needs every ex-date and amount from somewhere other than the account.

        WHAT `start`/`end` FILTER IS NOT DOCUMENTED. The reference says only that results
        are "sorted by their process_date". A cash dividend's process date is near
        its PAYABLE date, weeks after the ex-date (the reference's own example: ex
        2023-05-04, process 2023-05-19). So the caller queries a wide window and
        filters on `ex_date` itself; this method returns what the window holds and
        never infers an ex-date.

        ABSENCE IS NOT PROOF. Alpaca: "Currently Alpaca has no guarantees on the
        creation time of corporate actions ... may not be available immediately
        after they are announced" [V]. A symbol with no event here may still have
        one; the caller must not treat absence as a measured zero without a second
        source (`quantt/session/dist_score.py`).
        """
        start = _date_param(start, "start")
        end = _date_param(end, "end")
        if end < start:
            raise ValueError(f"end {end} is before start {start}")
        if isinstance(symbols, str):
            raise ValueError("symbols must be a list of symbols, not one string")
        syms = sorted(set(symbols))
        if not syms:
            raise ValueError("symbols is empty")
        for s in syms:
            if not isinstance(s, str) or not _SYMBOL_RE.match(s):
                raise ValueError(f"symbol {s!r} is not an upper-case equity symbol")

        w = "GET /v1/corporate-actions"
        out, seen = [], set()
        token = None
        for _ in range(MAX_PAGES):
            params = {"symbols": ",".join(syms),
                      "types": "cash_dividend,capital_gains_distribution",
                      "start": start.isoformat(), "end": end.isoformat(), "limit": 1000}
            if token is not None:
                params["page_token"] = token
            body = self._get(self._data, "/v1/corporate-actions", params)
            _require(body, ("corporate_actions",), w)
            ca = body["corporate_actions"] or {}
            if not isinstance(ca, dict):
                raise UnexpectedResponse(f"{w}: corporate_actions is {type(ca).__name__}, not an object")
            for kind, key in (("cash_dividend", "cash_dividends"),
                              ("capital_gains_distribution", "capital_gains_distributions")):
                rows = ca.get(key) or []
                if not isinstance(rows, list):
                    raise UnexpectedResponse(f"{w}: {key} is not a list")
                for i, r in enumerate(rows):
                    where = f"{w} {key}[{i}]"
                    _require(r, ("id", "symbol", "ex_date"), where)
                    sym = r["symbol"]
                    if sym not in syms:
                        raise UnexpectedResponse(f"{where}: returned unrequested symbol {sym!r}")
                    if not (isinstance(r["ex_date"], str) and _DATE_RE.match(r["ex_date"])):
                        raise UnexpectedResponse(f"{where}: ex_date {r['ex_date']!r} is not YYYY-MM-DD")
                    if kind == "cash_dividend":
                        _require(r, ("rate",), where)
                        amount = _num(r, "rate", where)
                        special = _bool(r, "special", where) if "special" in r else None
                    else:
                        legs = [k for k in ("long_term_rate", "short_term_rate") if r.get(k) is not None]
                        if not legs:
                            raise UnexpectedResponse(f"{where}: neither long_term_rate nor short_term_rate")
                        amount = sum(_num(r, k, where) for k in legs)
                        special = None
                    if not math.isfinite(amount) or amount < 0:
                        raise UnexpectedResponse(f"{where}: amount {amount!r} is not a finite cash amount >= 0")
                    if r["id"] in seen:
                        continue          # the same event repeated across pages
                    seen.add(r["id"])
                    out.append({"id": r["id"], "symbol": sym,
                                "ex_date": dt.date.fromisoformat(r["ex_date"]),
                                "amount": float(amount), "kind": kind, "special": special,
                                "sub_type": r.get("sub_type")})
            nxt = body.get("next_page_token")
            if not nxt:
                break
            if nxt == token:
                raise UnexpectedResponse(f"{w}: next_page_token did not advance")
            token = nxt
        else:
            raise UnexpectedResponse(f"{w}: more than {MAX_PAGES} pages")
        return sorted(out, key=lambda e: (e["symbol"], e["ex_date"], e["kind"], e["id"]))

    def corporate_actions(self, symbols, start: dt.date, end: dt.date, *, universe=None,
                          skipped: list | None = None, rows: dict | None = None) -> list[dict]:
        """Every NON-dividend corporate action that names one of `symbols`, in any role.

        GET {DATA_BASE}/v1/corporate-actions, types = the thirteen in
        CORPORATE_ACTION_TYPES, every page. Returns one dict per event:
            {"id", "type", "date": date, "date_field": str,
             "process_date": date, "parties": [[symbol, role], ...]}
        `parties` lists EVERY symbol the event names, ours and the counterparty's,
        so the record shows both sides of a merger. `date` is the day the action
        takes effect in the market (`date_field` says which field it came from).

        WHY. Alpaca paper processes no corporate actions [V: two staff forum
        replies, docs/REFERENCES.md §12pc]. A held fund that reverse-splits 1:4
        keeps its old share count on paper while its price is four times higher,
        so the runner, which reads broker share counts as they are, would size
        the plan and its orders on the wrong exposure. The runner's
        corporate-action gate (quantt/session/corp_actions.py; team lead
        2026-10-28) reads this method to refuse such a session.

        WHY NO `symbols` FILTER IS SENT. The reference says only that `symbols`
        is "a comma-separated list of symbols". It does not say which field it
        matches on a type that names several: the acquirer or the acquiree of a
        merger, a spin-off's source or new symbol, a name change's old or new.
        If Alpaca matched only one of them, a held acquirer would be missing from
        the response and the gate would pass it in silence (CLAUDE.md: no silent
        fallbacks). So the request asks for the types and the window only, and
        every symbol field of every row is matched here. The cost is the rest of
        the US market's non-dividend actions in the window, a few pages at most.

        VALIDATION, and why it is split. Every row must carry its type's
        symbol fields as strings, or this raises: a row whose parties cannot be
        read might be ours. A row that names one of `symbols` must also carry
        its id as a non-empty string, its date field and process_date as
        YYYY-MM-DD, or this raises.
        ONE ID, ONE EVENT (release-check of 9630322, 2026-10-30, reproduced).
        Rows naming ours are de-duplicated by id, because a page boundary can
        repeat one. The check used to be the key's presence only, so two rows
        with `id: null` were one id, and every row after the first was dropped:
        a null-id split effective on the session date went unseen and the gate
        read CLEAR under `halt`. Now an id that is not a non-empty string raises,
        naming the row, and so does an id that repeats with a DIFFERENT event
        (type, dates or parties: what the gate reads), because which one is
        true cannot be told. Only an identical repeat is dropped.
        A row that names none of them is not read further, so a malformed date
        on some other issuer's action cannot halt this book. A response key
        outside the reference's sixteen raises (a renamed key would otherwise
        empty a type in silence); a documented key we did not ask for is
        ignored, as `distributions` ignores the types it does not read. Only a
        null `corporate_actions` (or a null list) reads as "none": an empty
        list or a string where an object belongs raises. `distributions` reads
        any falsy value as empty; a gate must not read a malformed answer as
        clear. For the same reason `next_page_token` is REQUIRED on every page
        (the reference lists it as required): only an explicit null or "" ends
        the paging. A body without it, or with a token that is not a string,
        raises; `distributions` would read a missing key as the last page and
        drop every page after it in silence.
        ONE MEASURED EXCEPTION (real feed, 2026-10-29, docs/REFERENCES.md
        §12pc): 29 of 103 reorganizations over twelve months carry
        `stock_movements` legs with symbol "" and a CUSIP, a security with no
        ticker, while the row's own `symbol` is valid. Such a leg names nobody,
        because a security with no ticker cannot be one of our names, and it is
        skipped rather than raised on (`_ca_parties`). A leg with neither a
        symbol nor a CUSIP still raises. Until this rule, the first such row
        raised and the whole read failed, which under `halt` refuses every
        session.

        UNRESOLVED ROWS (docs/SYSTEM.md §5, team lead 2026-11-02 (unresolved
        corporate-action rows); it supersedes the brief applied at 709d6cb,
        which refused every such row and was never a ruling). A row whose
        required party symbol is present but null or "" (a split's or
        dividend's own symbol, an acquiree, an acquirer, a unit split's old,
        new or alternate, a spin-off's source or new, a name change's old or
        new, a reorganization's own symbol), or a reorganization leg with no
        ticker and no CUSIP, is an UNRESOLVED event. With `skipped` (the
        recording caller) it is RETURNED, never raised on: its usual fields,
        `missing` (each missing field and its role), `row_id` (the id as sent),
        and `id`, which is that id or, when the id is null too, `ca_row_key`
        (a hash of the raw row) so that the team lead can still acknowledge
        it. It is returned whatever it names, because the missing party could
        be any of our funds. The gate decides what it means
        (corp_actions.blocking_events, UNRESOLVED ROWS): it blocks exactly when
        a well-formed row of the same type and dates would block for one of
        the gate's names in the missing role, and is otherwise recorded only.
        A row whose dates cannot be read is UNDATED (`_ca_event`): keyed by its
        hash and treated as inside every window, so it blocks until
        acknowledged. A row naming one of `symbols` with a null, empty or
        non-string id, and every row of an id listed with different content,
        is keyed by its hash too (`_ca_key_events`) and judged on the windows
        like any other; it names ours, so it halts whenever the gate would halt
        for that fund, and ca-ack clears it on its full raw content (team lead
        2026-11-02: never needs a release to unstick).
        EVERY FIELD VALIDATED, NOTHING RAISES (release-check of 1c64638,
        2026-11-02; `_ca_read`). With `skipped`, no value in any field of any
        row can make the read raise: each field the reader knows (the party
        symbols, `id`, every date, every ratio, rate, cash amount and price,
        every CUSIP, each reorganization leg, the row itself) goes through a
        validator that returns a value or a named fault. A party fault makes
        the row unresolved; a non-party fault on a row naming ours makes it
        fail-closed (inside every window) and keyed for ca-ack; on a row whose
        parties are all present and none ours it is skipped and recorded.
        quantt/session/tests/test_ca_read_property.py is the property test
        over every field of every type, held and outside, with each adversarial
        value.
        WHAT STILL RAISES, with `skipped` (the gate's and ca-ack's read): only
        transport and SHAPE failures of the response, before any row: a failed
        GET, a body that is not JSON or not an object, `corporate_actions` not
        an object, a type's list not a list, a response key outside the
        reference, a missing or bad next_page_token, too many pages. Without
        `skipped`, the strict read from before the rulings (`_ca_strict`). Without
        `skipped`, such a row raises, as before the ruling. Why not refuse
        every such row (709d6cb): one in the market, anywhere and of any date,
        then refused every session for good, and `ca-ack`, which reads the
        same way, could not clear it (release-check of 709d6cb, 2026-11-02,
        reproduced).
        SKIPPED AND RECORDED (team lead 2026-10-29, docs/SYSTEM.md §5: "skip it,
        and record it, unless it could concern one of our funds"), only with
        `skipped` and `universe` (the book's symbols; the two go together): a
        row whose every party symbol is present, none of them in `universe` or
        `symbols`, while a NON-party required field is malformed (its id not a
        non-empty string, or its date field or process_date absent or not
        YYYY-MM-DD). It is appended to `skipped` (id, type, the malformed fields
        and their values, the symbols and CUSIPs present, the dates); the gate
        records it in plan.json, the run record and one log line. The same
        fault on a row naming a fund of the universe raises. Without
        `skipped`, a row naming none of `symbols` is not read further.
        NOT UNRESOLVED: the two OPTIONAL party fields the reference documents,
        a reverse split's new_symbol ("Empty when the reverse split does not
        change the ticker") and a cash merger's acquirer_symbol, name nobody
        when absent, null or ""; so does a reorganization leg with no ticker
        but a CUSIP (ONE MEASURED EXCEPTION above).
        HISTORY (each reproduced by a release-check). 9cf5cf2 skipped a
        malformed row when no PRESENT symbol was ours, so a held fund's split
        with its symbol null was skipped and sent. 04aca24 skipped it when the
        subject side was present and not ours, so a null acquirer was skipped
        and sent for a held acquirer. 709d6cb refused every such row, so one
        outside row halted the book indefinitely.
        Identification is by SYMBOL only. The ruling also names a CUSIP or a
        name "if Alpaca provides it". The rows do carry CUSIPs, but the live
        path holds no CUSIP for any fund in the universe, so none can be
        compared, which is why a missing party is treated as possibly any of
        ours. A skipped row's CUSIPs are recorded for a person to read. The reference's schemas
        (test_alpaca_client.CA_REFERENCE) carry no issuer name. Still raises on any row, ours or not: a row that
        is not an object, a required symbol field ABSENT (a renamed field would
        empty a type for every issuer, ours included), a symbol that is present
        but not a string, a leg with no `symbol` key.

        RAW ROWS (`rows`, release-check of 9cf5cf2, 2026-11-01). When `rows` is
        a dict, each row returned as an event is also recorded there as Alpaca
        sent it, `rows[id] = [row, ...]` (a repeat appended too). The gate
        compares these with what the team lead acknowledged
        (corp_actions.py, ACKNOWLEDGEMENTS): an acknowledgement holds only
        while the row is unchanged, ratio and every other field included.

        THE WINDOW FILTERS ON process_date. The reference does not say what
        `start`/`end` filter (`distributions` docstring). Measured 2026-10-29 on
        twelve months of the real feed: all 3,443 rows had a process_date
        inside the query window, and 13 had a market date outside it
        (docs/REFERENCES.md §12pc). The caller pads its window and filters on
        the dates returned (corp_actions.QUERY_PAD_BEFORE_DAYS / _AFTER_DAYS).

        `data_quality=all` (team lead's review, 2026-10-29). The default,
        `complete`, leaves out records "still missing required fields ... and
        not yet processed" [V: reference], which are the early, unprocessed
        records a gate most needs. Measured 2026-07-31..2026-10-29: `all` held
        945 rows against `complete`'s 911 over the same process dates. The 34
        extra were 24 unit splits, 4 cash mergers, 4 stock mergers and 2 stock
        and cash mergers. None lacked its date fields, none made this parser
        raise, and none named a deployed name (§12pc). An incomplete row that
        names one of ours and lacks a date still raises, so under `halt` the
        session refuses until the record is complete. That is accepted: an
        action that cannot be placed in time cannot be cleared either.

        WHAT IS NOT ASKED FOR. `rights_distribution`: it changes no share count
        (it distributes a separate security, as a cash dividend distributes cash),
        and the gate exists for the share count.

        ABSENCE IS NOT PROOF. Alpaca: "no guarantees on the creation time of
        corporate actions" [V]. Its merger coverage is mostly effective actions:
        on 2026-10-13 it listed none of seven pending CEF/BDC pairs, nor one
        merger three days before it closed (docs/REFERENCES.md §12p). An empty
        answer is what the feed holds now, not a measured zero.
        """
        start = _date_param(start, "start")
        end = _date_param(end, "end")
        if end < start:
            raise ValueError(f"end {end} is before start {start}")
        if isinstance(symbols, str):
            raise ValueError("symbols must be a list of symbols, not one string")
        syms = sorted(set(symbols))
        if not syms:
            raise ValueError("symbols is empty")
        for s in syms:
            if not isinstance(s, str) or not _SYMBOL_RE.match(s):
                raise ValueError(f"symbol {s!r} is not an upper-case equity symbol")
        wanted = set(syms)
        if rows is not None and not isinstance(rows, dict):
            raise ValueError("rows must be a dict (RAW ROWS)")
        raw_rows = rows             # `rows` is each type's list in the loop below
        if (universe is None) != (skipped is None):
            raise ValueError("universe and skipped go together (MALFORMED ROWS): a skipped row "
                             "needs the universe it was judged against, and a record to go to")
        ours = set(wanted)
        if universe is not None:
            if isinstance(universe, str) or not isinstance(skipped, list):
                raise ValueError("universe must be a list of symbols and skipped a list")
            for s in universe:
                if not isinstance(s, str) or not _SYMBOL_RE.match(s):
                    raise ValueError(f"universe symbol {s!r} is not an upper-case equity symbol")
            ours |= set(universe)

        w = "GET /v1/corporate-actions"
        out, seen, seen_skipped = [], {}, set()       # seen: id -> the event read
        cands = []          # (id as sent, event without its key, raw row): `_ca_key_events`
        token = None
        for _ in range(MAX_PAGES):
            params = {"types": ",".join(CORPORATE_ACTION_TYPES),
                      "start": start.isoformat(), "end": end.isoformat(), "limit": 1000,
                      "data_quality": "all"}
            if token is not None:
                params["page_token"] = token
            body = self._get(self._data, "/v1/corporate-actions", params)
            _require(body, ("corporate_actions", "next_page_token"), w)
            # Only null reads as "no actions" (docstring, VALIDATION).
            ca = {} if body["corporate_actions"] is None else body["corporate_actions"]
            if not isinstance(ca, dict):
                raise UnexpectedResponse(f"{w}: corporate_actions is {type(ca).__name__}, not an object")
            unknown = sorted(set(ca) - CORPORATE_ACTION_RESPONSE_KEYS)
            if unknown:
                raise UnexpectedResponse(f"{w}: response keys {unknown} are not in the reference; "
                                         f"a renamed type could hide one of ours")
            for kind, (key, date_field, fields) in CORPORATE_ACTION_TYPES.items():
                rows = ca.get(key)
                rows = [] if rows is None else rows
                if not isinstance(rows, list):
                    raise UnexpectedResponse(f"{w}: {key} is {type(rows).__name__}, not a list")
                for i, r in enumerate(rows):
                    where = f"{w} {key}[{i}]"
                    if skipped is None:
                        # No record to go to: the read before the rulings, strict.
                        parties, unread = _ca_parties(r, kind, fields, where)
                        if unread:
                            raise UnexpectedResponse(unread[0]["error"])
                        if any(s in wanted for s, _ in parties):
                            _ca_strict(r, kind, date_field, parties, where, seen, out,
                                       raw_rows)
                        continue
                    # EVERY FIELD VALIDATED, NOTHING RAISES (docstring): a value
                    # or a named fault, field by field (`_ca_read`).
                    parties, unread, bad = _ca_read(r, kind, date_field, fields)
                    names_wanted = any(s in wanted for s, _ in parties)
                    if not unread and not names_wanted:
                        if not bad:
                            continue          # well-formed and not one of `symbols`
                        if not any(s in ours for s, _ in parties):
                            # SKIPPED AND RECORDED (docstring): every party present,
                            # none ours, a non-party field malformed.
                            rid = r.get("id")
                            if isinstance(rid, str) and rid in seen_skipped:
                                continue      # the same row repeated across pages
                            if isinstance(rid, str):
                                seen_skipped.add(rid)
                            skipped.append(_ca_skip_record(r, kind, date_field, bad, parties))
                            continue
                    # IRREGULAR or naming ours: judged by the gate (docstring).
                    cands.append((r.get("id") if isinstance(r, dict) else None,
                                  _ca_event(r, kind, date_field, parties, unread, bad),
                                  copy.deepcopy(r)))
            nxt = body["next_page_token"]          # required (docstring, VALIDATION)
            if nxt is None or nxt == "":
                break
            if not isinstance(nxt, str):
                raise UnexpectedResponse(f"{w}: next_page_token {nxt!r} is not a string or null")
            if nxt == token:
                raise UnexpectedResponse(f"{w}: next_page_token did not advance")
            token = nxt
        else:
            raise UnexpectedResponse(f"{w}: more than {MAX_PAGES} pages")
        if skipped is not None:
            _ca_key_events(cands, out, raw_rows)
        # An undated event (date None) sorts first.
        return sorted(out, key=lambda e: (e["date"] or dt.date.min, e["type"], e["id"]))


# The thirteen NON-dividend types `AlpacaClient.corporate_actions` asks for:
# type -> (response key, the field holding the date the action takes effect in
# the market, the symbol fields as (field, role, required)). From the endpoint
# reference's schemas [V: docs.alpaca.markets Market Data API, GET
# /v1/corporate-actions, fetched 2026-10-28; docs/REFERENCES.md §12pc]:
#   * the date field is the one the reference REQUIRES for that type: ex_date
#     for splits, stock dividends and spin-offs, effective_date for unit splits,
#     mergers and reorganizations; redemptions, name changes, worthless removals
#     and partial calls carry no ex or effective date, only process_date;
#   * `required` follows the reference's `required` list. Two symbol fields are
#     optional there: a reverse split's new_symbol ("Empty when the reverse split
#     does not change the ticker") and a cash merger's acquirer_symbol.
# A reorganization's stock legs (`stock_movements[].symbol`) are read in
# `_ca_parties`, as role "allocated"; a leg with no ticker but a CUSIP names nobody.
CORPORATE_ACTION_TYPES = {
    "reverse_split": ("reverse_splits", "ex_date",
                      (("symbol", "subject", True), ("new_symbol", "new", False))),
    "forward_split": ("forward_splits", "ex_date", (("symbol", "subject", True),)),
    "unit_split": ("unit_splits", "effective_date",
                   (("old_symbol", "old", True), ("new_symbol", "new", True),
                    ("alternate_symbol", "alternate", True))),
    "stock_dividend": ("stock_dividends", "ex_date", (("symbol", "subject", True),)),
    "spin_off": ("spin_offs", "ex_date",
                 (("source_symbol", "source", True), ("new_symbol", "new", True))),
    "cash_merger": ("cash_mergers", "effective_date",
                    (("acquiree_symbol", "acquiree", True), ("acquirer_symbol", "acquirer", False))),
    "stock_merger": ("stock_mergers", "effective_date",
                     (("acquiree_symbol", "acquiree", True), ("acquirer_symbol", "acquirer", True))),
    "stock_and_cash_merger": ("stock_and_cash_mergers", "effective_date",
                              (("acquiree_symbol", "acquiree", True),
                               ("acquirer_symbol", "acquirer", True))),
    "redemption": ("redemptions", "process_date", (("symbol", "subject", True),)),
    "name_change": ("name_changes", "process_date",
                    (("old_symbol", "old", True), ("new_symbol", "new", True))),
    "worthless_removal": ("worthless_removals", "process_date", (("symbol", "subject", True),)),
    "reorganization": ("reorganizations", "effective_date", (("symbol", "subject", True),)),
    "partial_call": ("partial_calls", "process_date", (("symbol", "subject", True),)),
}
# Every key the reference's `corporate_actions` object can hold: the thirteen
# above plus the three types the gate does not ask for.
CORPORATE_ACTION_RESPONSE_KEYS = frozenset(
    [k for k, _, _ in CORPORATE_ACTION_TYPES.values()]
    + ["cash_dividends", "capital_gains_distributions", "rights_distributions"])


def _ca_parties(r, kind: str, fields, where: str) -> tuple[list[tuple[str, str]], list[dict]]:
    """([(symbol, role)], unread) for one corporate-action row
    (`AlpacaClient.corporate_actions`, VALIDATION and MALFORMED ROWS).

    `unread` holds each REQUIRED symbol that is present but null or "", and
    each reorganization leg whose symbol is null or "" with no CUSIP, as
    {"field", "role", "error"}; `error` is the sentence the read raised with
    before the 2026-10-29 ruling, so a caller that keeps no record raises
    exactly as before. The caller decides what such a row means. This still
    raises, for any row: not a JSON object, a required symbol field absent, a
    symbol present but not a string, a leg with no `symbol` key. An optional
    field that is absent, null or "" names nobody."""
    if not isinstance(r, dict):
        raise UnexpectedResponse(f"{where}: expected a JSON object, got {type(r).__name__}")
    _require(r, [f for f, _, req in fields if req], where)
    out, unread = [], []
    for f, role, req in fields:
        v = r.get(f)
        if v is None or v == "":
            if req:
                unread.append({"field": f, "role": role,
                               "error": f"{where}: {f} {v!r} is not a symbol"})
            continue
        if not isinstance(v, str):
            raise UnexpectedResponse(f"{where}: {f} {v!r} is not a symbol")
        out.append((v, role))
    if kind == "reorganization":
        legs = r.get("stock_movements")
        if legs is not None:
            if not isinstance(legs, list):
                raise UnexpectedResponse(f"{where}: stock_movements is not a list")
            for j, m in enumerate(legs):
                leg = f"{where}.stock_movements[{j}]"
                _require(m, ("symbol",), leg)
                sym, cusip = m["symbol"], m.get("cusip")
                if sym in (None, "") and isinstance(cusip, str) and cusip:
                    # A security with no ticker, identified by its CUSIP: names
                    # nobody (corporate_actions docstring, ONE MEASURED EXCEPTION).
                    continue
                why = (f"{leg}: symbol {sym!r} is not a symbol, and the leg has no CUSIP "
                       f"({cusip!r}) to say it has no ticker")
                if sym is None or sym == "":
                    unread.append({"field": f"stock_movements[{j}].symbol", "role": "allocated",
                                   "error": why})
                    continue
                if not isinstance(sym, str):
                    raise UnexpectedResponse(why)
                out.append((sym, "allocated"))
    return out, unread


UNRESOLVED_KEY_PREFIX = "row-sha256:"


def ca_row_canonical(r) -> str:
    """The canonical JSON TEXT of one raw feed item, ANY JSON value (an object,
    a list, a string, a number, null): sorted keys, no spaces, ASCII, and a
    non-finite float written as its token (NaN, Infinity) inside this string.
    It is the ONE form an acknowledgement is matched on (corp_actions
    ACKNOWLEDGEMENTS; `ca-ack` writes it, `parse_acks` checks it, the gate
    compares it): a NaN equals itself here, which it never does as a float,
    and an item that is not an object has a form too (execution-trader,
    2026-11-02, reproduced: such a row was written as `"row": null` and then
    refused the whole file). An item parsed from JSON always serialises."""
    return json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=True)


def ca_row_key(r) -> str:
    """The key an irregular row is acknowledged by: the SHA-256 of
    `ca_row_canonical`. Any change to the row is a different key, so an
    acknowledgement of it cannot outlive a revision."""
    return UNRESOLVED_KEY_PREFIX + hashlib.sha256(ca_row_canonical(r).encode()).hexdigest()


def _ca_event(r: dict, kind: str, date_field: str, parties, unread: list, bad: dict) -> dict:
    """One row's event, before its key is assigned (`_ca_key_events`): the usual
    fields, plus `missing` (each missing party field and its role) when a party
    symbol is null or empty, and `undated` (each unreadable date field and its
    raw value) when a date is absent or not YYYY-MM-DD; an unreadable date is
    None. Never raises: what the gate cannot read it judges fail-closed
    (corp_actions.blocking_events: an undated event is inside every window)."""
    def day(f):
        return None if f in bad else _ca_date(r.get(f))[0]
    ev = {"type": kind, "date": day(date_field), "date_field": date_field,
          "process_date": day("process_date"), "parties": [[s, role] for s, role in parties]}
    if unread:
        ev["missing"] = [{"field": u["field"], "role": u["role"]} for u in unread]
    undated = {f: v for f, v in bad.items() if f in (date_field, "process_date")}
    if undated:
        ev["undated"] = undated
    faults = {f: v for f, v in bad.items() if f not in (date_field, "process_date", "id")}
    if faults:
        # Any other field unreadable (a ratio, a cash amount, a price, a CUSIP,
        # another date): its terms cannot be read, so it is fail-closed too.
        ev["faults"] = faults
    return ev


def _ca_key_events(cands: list, out: list, raw_rows: dict | None) -> None:
    """Give each candidate event its key and append it to `out` (ONE ID, ONE
    EVENT, and the 2026-11-02 rulings in the docstring).

    A row whose id is a non-empty string and whose dates are readable is keyed
    by that id; repeats of exactly the same raw row are one event. Every other
    row is keyed by `ca_row_key`, the SHA-256 of its raw content, and carries
    `row_id` (the id as sent): a null, empty or non-string id, an undated row,
    and every row of an id that Alpaca lists with DIFFERENT raw content
    (`conflict`, since which one is true cannot be told, so each is judged).
    None is dropped, none raises, and each can be acknowledged by its key;
    a revision of a hash-keyed row is a new key, so it halts again."""
    by_id, hashed = {}, []
    for rid, ev, raw in cands:
        if _ca_id(rid)[1] is None and "undated" not in ev:     # one token, dates readable
            by_id.setdefault(rid, []).append((ev, raw))
        else:
            hashed.append((rid, ev, raw))
    for rid, items in by_id.items():
        raws = []
        for _, raw in items:
            if raw not in raws:
                raws.append(raw)
        if len(raws) == 1:
            e = {"id": rid, **items[0][0]}
            if "missing" in e:
                e["row_id"] = rid
            out.append(e)
            if raw_rows is not None:
                raw_rows.setdefault(rid, []).extend(raw for _, raw in items)
        else:
            hashed.extend((rid, {**ev, "conflict": True}, raw) for ev, raw in items)
    keys = set()
    for rid, ev, raw in hashed:
        key = ca_row_key(raw)
        if raw_rows is not None:
            raw_rows.setdefault(key, []).append(raw)
        if key in keys:
            continue                  # the same raw row repeated
        keys.add(key)
        out.append({"id": key, **ev, "row_id": rid})


def _ca_strict(r: dict, kind: str, date_field: str, parties, where: str, seen: dict, out: list,
               raw_rows: dict | None) -> None:
    """A row naming one of `symbols`, read WITHOUT a record to go to (`skipped`
    None): the strict read from before the rulings. A bad id or date, or one id
    with two different events, raises."""
    _require(r, ("id", date_field, "process_date"), where)
    rid = r["id"]
    if not isinstance(rid, str) or not rid.strip():
        raise UnexpectedResponse(
            f"{where}: a {kind} naming {[list(p) for p in parties]} has id {rid!r}, not a "
            f"non-empty string; rows naming ours are told apart by id, so the read fails "
            f"rather than drop one")
    dates = {}
    for f in (date_field, "process_date"):
        if not (isinstance(r[f], str) and _DATE_RE.match(r[f])):
            raise UnexpectedResponse(f"{where}: {f} {r[f]!r} is not YYYY-MM-DD")
        dates[f] = dt.date.fromisoformat(r[f])
    ev = {"id": rid, "type": kind, "date": dates[date_field], "date_field": date_field,
          "process_date": dates["process_date"], "parties": [[s, role] for s, role in parties]}
    if raw_rows is not None:
        raw_rows.setdefault(rid, []).append(copy.deepcopy(r))
    if rid in seen:
        if seen[rid] != ev:
            raise UnexpectedResponse(f"{where}: id {rid!r} repeats with a different event: "
                                     f"{seen[rid]} and {ev}; which is true cannot be told")
        return
    seen[rid] = ev
    out.append(ev)


# EVERY FIELD VALIDATED, NOTHING RAISES (release-check of 1c64638, 2026-11-02,
# reproduced: "2026-02-30", "0000-00-00" and "2026-10-29\n" passed `_DATE_RE`,
# whose `$` also matches before a trailing newline, and then raised in
# `fromisoformat`, unnamed and un-ackable). Each validator returns
# (value, None) or (None, fault); none can raise, whatever JSON value it is
# handed. `_ca_read` applies them to every field of a row it knows the
# meaning of: the party symbols of its type, `id`, every `*_date`, every
# `rate` / `*_rate` / `price`, every `*cusip`, and each reorganization leg.
_CA_DATE_FULL = re.compile(r"\d{4}-\d{2}-\d{2}")
_CA_NUMBER_FULL = re.compile(r"\d+(\.\d+)?([eE][+-]?\d+)?")


def _ca_date(v):
    """A calendar date: a str that FULLY matches YYYY-MM-DD and is a real day."""
    if not (isinstance(v, str) and _CA_DATE_FULL.fullmatch(v)):
        return None, f"{v!r:.80} is not YYYY-MM-DD"
    try:
        return dt.date.fromisoformat(v), None
    except ValueError:
        return None, f"{v!r} is not a calendar date"


def _ca_symbol(v):
    """A ticker: a str that FULLY matches _SYMBOL_RE (no trailing newline)."""
    if isinstance(v, str) and _SYMBOL_RE.fullmatch(v):
        return v, None
    return None, f"{v!r:.80} is not a symbol"


def _ca_id(v):
    """An action id: a non-empty str with no whitespace (ca-ack takes it as one token)."""
    if isinstance(v, str) and v and not any(ch.isspace() for ch in v):
        return v, None
    return None, f"{v!r:.80} is not a usable id"


def _ca_number(v, *, zero_ok: bool):
    """A ratio, rate, cash amount or price: an int or float (never a bool), or a
    plain decimal string, finite, > 0 (>= 0 when `zero_ok`)."""
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        return None, f"{v!r:.80} is not a number"
    if isinstance(v, str) and not _CA_NUMBER_FULL.fullmatch(v):
        return None, f"{v!r:.80} is not a number"
    try:
        x = float(v)
    except (OverflowError, ValueError):
        return None, f"{v!r:.80} is not a number"
    if not math.isfinite(x) or x < 0 or (x == 0 and not zero_ok):
        return None, f"{v!r:.80} is not a finite number {'>= 0' if zero_ok else '> 0'}"
    return x, None


def _ca_text(v):
    """A CUSIP: a non-empty str with no surrounding whitespace and no control
    characters. (Never compared with anything: read so that garbage is named.)"""
    if isinstance(v, str) and v and v == v.strip() and v.isprintable():
        return v, None
    return None, f"{v!r:.80} is not a CUSIP"


def _ca_field_kind(k: str):
    if k == "id":
        return "id"
    if k.endswith("_date"):
        return "date"
    if k == "rate" or k.endswith("_rate") or k == "price":
        return "number"
    if k.endswith("cusip"):
        return "text"
    return None


def _ca_check_value(k: str, v, bad: dict) -> None:
    kind = _ca_field_kind(k)
    if kind == "date":
        if _ca_date(v)[1]:
            bad[k] = v
    elif kind == "number":
        if _ca_number(v, zero_ok=(k == "cash_rate"))[1]:
            bad[k] = v
    elif kind == "text":
        if _ca_text(v)[1]:
            bad[k] = v


def _ca_read(r, kind: str, date_field: str, fields) -> tuple[list, list, dict]:
    """(parties, unread, bad) for one row, and it NEVER raises.

    `parties`: [(symbol, role)] for each party symbol that validates.
    `unread`: each party that does not, as {"field", "role"}: a required party
    field absent, null, empty or not a ticker; an optional one (a reverse
    split's new_symbol, a cash merger's acquirer) only when present and not a
    ticker (absent, null or "" names nobody, as the reference says); a
    reorganization leg that is not an object, or whose symbol is not a ticker
    unless it is null or "" with a valid CUSIP (ONE MEASURED EXCEPTION); a
    `stock_movements` that is neither null nor a list.
    `bad`: {field: raw value} for each NON-party field that is malformed: `id`
    (`_ca_id`), the date field and process_date (required), and, when present
    and not null, every other date, number and CUSIP (`_ca_field_kind`). A row
    that is not an object has every required party unread and both dates bad."""
    if not isinstance(r, dict):
        unread = [{"field": f, "role": role} for f, role, req in fields if req]
        return [], unread, {"id": None, date_field: None, "process_date": None}
    parties, unread, bad = [], [], {}
    for f, role, req in fields:
        v = r.get(f)
        if not req and (v is None or v == ""):
            continue
        sym, fault = _ca_symbol(v)
        if fault:
            unread.append({"field": f, "role": role})
        else:
            parties.append((sym, role))
    if kind == "reorganization":
        legs = r.get("stock_movements")
        if legs is not None and not isinstance(legs, list):
            unread.append({"field": "stock_movements", "role": "allocated"})
        for j, m in enumerate(legs if isinstance(legs, list) else []):
            leg = f"stock_movements[{j}]"
            if not isinstance(m, dict):
                unread.append({"field": leg, "role": "allocated"})
                continue
            sym, cusip = m.get("symbol"), m.get("cusip")
            if cusip is not None and _ca_text(cusip)[1] and cusip != "":
                bad[f"{leg}.cusip"] = cusip
            for k in ("new_rate", "source_rate"):
                if m.get(k) is not None and _ca_number(m[k], zero_ok=False)[1]:
                    bad[f"{leg}.{k}"] = m[k]
            if (sym is None or sym == "") and not _ca_text(cusip)[1]:
                continue              # no ticker but a CUSIP: names nobody (measured)
            ok, fault = _ca_symbol(sym)
            if fault:
                unread.append({"field": f"{leg}.symbol", "role": "allocated"})
            else:
                parties.append((ok, "allocated"))
    if _ca_id(r.get("id"))[1]:
        bad["id"] = r.get("id")
    for f in (date_field, "process_date"):
        if _ca_date(r.get(f))[1]:
            bad[f] = r.get(f)
    party_fields = {f for f, _, _ in fields}
    for k, v in r.items():
        if k in party_fields or k in bad or k in ("id", date_field, "process_date"):
            continue
        if v is not None:
            _ca_check_value(k, v, bad)
    return parties, unread, bad


def _ca_nonparty_faults(r: dict, date_field: str) -> dict:
    """{field: raw value} for each NON-party required field that is malformed
    (MALFORMED ROWS): `id` not a non-empty string, the date field or
    process_date absent or not YYYY-MM-DD. An absent field reads None."""
    bad = {}
    rid = r.get("id")
    if not isinstance(rid, str) or not rid.strip():
        bad["id"] = rid
    for f in (date_field, "process_date"):
        v = r.get(f)
        if not (isinstance(v, str) and _DATE_RE.match(v)):
            bad[f] = v
    return bad


def _ca_skip_record(r: dict, kind: str, date_field: str, bad: dict, parties) -> dict:
    """The record of one skipped malformed row (`AlpacaClient.corporate_actions`,
    MALFORMED ROWS): enough for a person to find it and judge it. Raw values,
    unparsed: the row was not read further. `malformed` is each bad non-party
    field and its value. CUSIPs are every non-empty string field whose name
    ends in `cusip`, and each leg's; none is compared with the universe (the
    live path holds no CUSIP for it), so they are here to be read."""
    cusips = {k: v for k, v in sorted(r.items())
              if k.endswith("cusip") and isinstance(v, str) and v}
    if kind == "reorganization":
        for j, m in enumerate(r.get("stock_movements") or []):
            if isinstance(m.get("cusip"), str) and m["cusip"]:
                cusips[f"stock_movements[{j}].cusip"] = m["cusip"]
    return {"id": r.get("id"), "type": kind, "malformed": dict(sorted(bad.items())),
            "present": [[s, role] for s, role in parties], "cusips": cusips,
            "dates": {f: r.get(f) for f in (date_field, "process_date") if f in r}}


def _load_keys(book: str, env_file: Path) -> tuple[str, str]:
    """(key_id, secret) for `book` from `env_file`, or raise naming what is unset.

    Reads with `dotenv_values`, which does not export to os.environ, so a key
    loaded for one book is never visible to code reading another's. The
    message names the file and the variables, never a value.
    """
    if not env_file.is_file():
        raise MissingCredential(f"Alpaca key file {env_file} does not exist")
    from dotenv import dotenv_values
    env = dotenv_values(env_file)
    kid_name, sec_name = env_names(book)
    missing = [n for n in (kid_name, sec_name) if not env.get(n)]
    if missing:
        raise MissingCredential(
            f"book {book!r}: {', '.join(missing)} not set in {env_file}. Each book has "
            f"its own Alpaca paper account and keys; no other book's key is substituted.")
    return env[kid_name], env[sec_name]
