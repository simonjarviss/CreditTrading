"""A GET-only reader of one Alpaca paper account, for the nightly report jobs.

WHY A SECOND READER EXISTS (team lead, 2026-11-09)
--------------------------------------------------
The report job (`scripts/ops/pnl_report.py`, the daily P&L attribution and factor
readout of each paper book) has to read the account: the EOD equity series, the
FILL and FEE activities, the calendar, SIP daily bars and the corporate-action
records. The ruling for that job is that it reads the account with the broker
key from the VM's secret service at run time and "read-only code: a test pins
that no import path from the job reaches order-sending code"
(`scripts/ops/tests/test_report_no_order_path.py`).

`quantt/broker/alpaca.AlpacaClient` is the runner's client. It holds
`submit_order`, and it is imported by `quantt.session.run`. A report job that
imported it, even at function level, would have an import path to order code,
which the closure test forbids and the team lead ruled out. So this module is a
second reader, deliberately outside `quantt/broker` (it is not to be imported by
the runner either), with four properties:

  * GET ONLY. One HTTP verb, built in one place (`urllib_transport`), checked by a
    test against the request object it builds. There is no POST, PUT, PATCH or
    DELETE here, no order, no cancel and no replace, and no parameter that adds one.
  * PAPER ONLY. The two hosts are this module's own constants, compared with
    AlpacaClient's by a test. `_get` raises on any other base, and a redirect is never
    followed: urllib would re-send both key headers to whatever host a 3xx names
    (review, 2026-11-09), so `urllib_transport` refuses the hop and a 3xx comes back as
    an answer, for `_get`'s non-200 branch to raise on naming it. A host check on the
    first request only is not a paper-only guarantee.
  * KEYS FROM THE PROCESS ENVIRONMENT ONLY (`AlpacaReader.from_environment`):
    `ALPACA_<BOOK>_KEY_ID` / `_SECRET_KEY`, which systemd loads with
    `EnvironmentFile=` from the tmpfs file the secret service wrote
    (`install_vm --reports`, docs/RUNBOOK.md 8.12). This module opens no key file
    and no `config/.env`, and names no variable but those two. A missing key raises
    naming the variable; it never prints a value, and `_scrub` removes both values
    from every message `_get` builds. The one message `_scrub` could not reach is
    http.client's own, which quotes a header value that holds a line break, so a key
    that is not printable ASCII is refused in the constructor, naming only the variable
    (`MalformedCredential`; review, 2026-11-09).
  * EXACTLY THE READS ATTRIBUTION NEEDS (a test pins the public method list).

WHY ITS PARSING IS A COPY, AND WHY THAT IS SAFE
-----------------------------------------------
AlpacaClient's parsers carry most of this desk's Alpaca incident history in their
docstrings (the 20:00 New York stamp of a 1D point, the leading funding zeros, the
FILL type field, the corporate-action shape rules). They cannot be imported
(see above), and `quantt/broker/*` is the runner's and is not to be edited for
this. So the parsing here is a copy of that code, read for read, and
`scripts/ops/tests/test_alpaca_read.py` runs both clients on the SAME fixture
responses and requires equal parsed output, row for row, and equal raises on the
malformed shapes. That equality test is the licence for the copy: edit either side
and it fails. The copied docstrings are shortened to the reason and a pointer to
the original.

THE HALF-DAY EOD STAMP (team lead, 2026-11-14). A half day is stamped 17:00 New York, not the
20:00 of a full day: read 2026-11-14 on the cef paper account, `period=3A`, 754 points [V: the
runner owner's read-only GET], all 747 sessions with a 16:00 calendar close at 20:00:00 New
York and all 7 with a 13:00 close at 17:00:00 (2023-11-24, 2024-07-03, 2024-11-29, 2024-12-24,
2025-07-03, 2025-11-28, 2025-12-24; the last two funded); the main session's own GET found
2025-11-28T22:00:00Z the same day. The old every-stamp-is-20:00 rule refused the whole history,
and the report's lookback (`pnl_report.EOD_LOOKBACK_DAYS`) reaches back past 2025-11-28, so the
core's report would have failed on its first night. The rule here is AlpacaClient's from the
runner owner's PR #83 (cf3eac4, merged 2026-11-14): a stamp's New York time must be its date's
/v2/calendar `close` + EOD_STAMP_AFTER_CLOSE_H hours, and a date the calendar lists twice
raises. On a full day it is 20:00, the old rule. An equality test holds the two equal on half
days as on full days.

WHAT IT REFUSES (raises, naming what; never a default)
-------------------------------------------------------
Everything AlpacaClient refuses on these reads, and: a base URL that is not one of
the two hosts; a redirect; a key that is not in the environment or is not printable
ASCII; a page that does not advance.

This module is stdlib plus pandas (`fetch_bars` returns a frame, as
`scripts/rv/alpaca_daily.fetch_bars` does). It imports nothing from `quantt/`.
"""
from __future__ import annotations

import copy
import datetime as dt
import http.client
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Callable, NamedTuple
from zoneinfo import ZoneInfo

import pandas as pd

NY = ZoneInfo("America/New_York")

# The only two hosts this reader will ever address (AlpacaClient's own constants;
# a test holds them equal). There is no constructor argument for either.
PAPER_BASE = "https://paper-api.alpaca.markets"
DATA_BASE = "https://data.alpaca.markets"

GET_BACKOFF_S = (2, 5, 15, 30)          # AlpacaClient.GET_BACKOFF_S: a GET changes nothing
TIMEOUT_S = 30                          # urllib takes one timeout, connect and read together
FILL_PAGE_SIZE = 100                    # GET /v2/account/activities: page_size max 100 [V]
BARS_LIMIT = 10000                      # GET /v2/stocks/bars: limit max 10000 [V]
CA_LIMIT = 1000                         # GET /v1/corporate-actions: limit max 1000 [V]
SYMBOLS_PER_REQUEST = 20
MAX_PAGES = 1000                        # a pagination loop this long is a bug, not data
FEED = "sip"                            # scripts/rv/alpaca_daily.FEED
ADJUSTMENT = "raw"                      # scripts/rv/alpaca_daily.ADJUSTMENT

_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HHMM_RE = re.compile(r"^\d{2}:\d{2}$")
_BOOK_RE = re.compile(r"[a-z0-9]+")
_KEY_RE = re.compile(r"[\x21-\x7e]+")      # no space, control character or non-ASCII: `AlpacaReader.__init__`


class AlpacaReadError(RuntimeError):
    """A read could not be completed or its answer could not be believed. Names why."""


class UnexpectedResponse(AlpacaReadError):
    """Alpaca answered, but not in a shape this reader was built for."""


class AlpacaHTTPError(AlpacaReadError):
    def __init__(self, msg: str, *, status: int | None):
        super().__init__(msg)
        self.status = status


class MissingCredential(AlpacaReadError):
    """A book's key is not in the process environment. The message names the variable."""


class MalformedCredential(AlpacaReadError):
    """A book's key cannot be sent as a header. The message names the variable, never the value."""


def env_names(book: str) -> tuple[str, str]:
    """The two environment variables that hold one book's keys
    (quantt.broker.alpaca_probe.env_names; a test holds them equal)."""
    b = book.upper()
    return f"ALPACA_{b}_KEY_ID", f"ALPACA_{b}_SECRET_KEY"


# ------------------------------------------------------------ small parsers
# (AlpacaClient's, read for read; `test_alpaca_read.py` holds the output equal)

def _require(obj: dict, fields, where: str) -> None:
    if not isinstance(obj, dict):
        raise UnexpectedResponse(f"{where}: expected a JSON object, got {type(obj).__name__}")
    missing = [f for f in fields if f not in obj]
    if missing:
        raise UnexpectedResponse(f"{where}: missing field(s) {missing}")


def _num(obj: dict, field: str, where: str) -> float:
    v = obj[field]
    if v is None or isinstance(v, bool):
        raise UnexpectedResponse(f"{where}: field {field!r} is {v!r}, not a number")
    try:
        return float(Decimal(str(v)))
    except InvalidOperation:
        raise UnexpectedResponse(f"{where}: field {field!r} = {v!r} is not a number") from None


def _bool(obj: dict, field: str, where: str) -> bool:
    v = obj[field]
    if not isinstance(v, bool):
        raise UnexpectedResponse(f"{where}: field {field!r} = {v!r} is not a JSON boolean")
    return v


def _decimal(v, where: str) -> Decimal | None:
    """A finite Decimal from a decimal string, or None (the caller names the field). A number
    that is not a string is refused: the account's money fields are strings."""
    if not isinstance(v, str):
        return None
    try:
        d = Decimal(v)
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def _date_param(v, name: str) -> dt.date:
    if isinstance(v, dt.datetime) or not isinstance(v, dt.date):
        raise ValueError(f"{name}={v!r} must be a datetime.date")
    return v


class EODPoint(NamedTuple):
    """One session's end-of-day equity: (session date in New York, equity USD, Alpaca's
    stamp). The stamp is kept because whether a point is final is the caller's
    question (`quantt.broker.alpaca.EODPoint`)."""
    date: dt.date
    equity: float
    stamp: dt.datetime


# The corporate-action table, copied from quantt/broker/alpaca.py with every row
# intact (the docstring there gives the reference it was built from); a test holds
# the two equal, so a type added there fails here until it is added to both.
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
# The account's own corporate-action activity types (GET /v2/account/activities): the
# non-FILL types paper accepts in `activity_types`. Read-only on the cef account, 2026-11-14 (the
# team lead's investigation): each of these nine returned 0 rows; SSP and SSO answered HTTP 422,
# so they are not sent. `corporate_action_activities` reads them; the attribution rebuilds from
# FILLs plus these rows, never from the market feed (`live_attribution`, CORPORATE ACTIONS).
CORPORATE_ACTION_ACTIVITY_TYPES = ("SPLIT", "CIL", "MA", "NC", "SC", "SPIN", "REO", "REORG", "JNLS")
CA_CASH_ACTIVITY_TYPES = ("CIL",)          # cash in lieu: a cash amount, no position change

CORPORATE_ACTION_RESPONSE_KEYS = frozenset(
    [k for k, _, _ in CORPORATE_ACTION_TYPES.values()]
    + ["cash_dividends", "capital_gains_distributions", "rights_distributions"])


def _ca_parties(r, kind: str, fields, where: str) -> tuple[list[tuple[str, str]], list[dict]]:
    """([(symbol, role)], unread) for one corporate-action row: alpaca.py `_ca_parties`,
    read for read (a required symbol absent or not a string raises; present but null or
    "" is unread; a reorganization leg with no ticker but a CUSIP names nobody)."""
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
                    continue          # a security with no ticker names nobody
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


def _ca_strict(r: dict, kind: str, date_field: str, parties, where: str, seen: dict, out: list,
               raw_rows: dict | None = None) -> None:
    """A row naming one of `symbols`, read strictly: alpaca.py `_ca_strict` (a bad id or
    date, or one id with two different events, raises; an identical repeat is dropped).
    `raw_rows` (AlpacaClient's, read for read): each kept row's raw object, by id, so a caller
    can read a field the event dict does not carry (the attribution reads a split's
    old_rate/new_rate, `live_attribution.fetch`)."""
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


# ------------------------------------------------------------ transport

Transport = Callable[[str, dict, float], tuple]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx is an answer, never a second request. `urlopen`'s default handler follows
    it and re-sends the request's headers, both API keys among them, to whatever host the
    response names, so a redirect from the paper host could carry the keys to the live
    API or to plain http. Returning None makes urllib treat the 3xx like any other error
    status: it reaches `urllib_transport` as an HTTPError, and `_get` raises naming it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def urllib_transport(url: str, headers: dict, timeout: float) -> tuple[int, str]:
    """One HTTP GET: (status, body text). The only place this module speaks HTTP, and the
    method is written here, once. An HTTP error status is an answer (returned), and so is
    a redirect, which is refused (`_NoRedirect`); a transport failure raises (OSError or
    http.client.HTTPException) for `_get` to retry. Standard library only: `requests` is
    what the runner's client uses, and the job's import closure stays away from it
    (test_report_no_order_path.py)."""
    req = urllib.request.Request(url, headers=headers, method="GET")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


class AlpacaReader:
    """One book's paper account, read-only. See the module docstring for the rules.

    Public surface (a test pins it): `from_environment`, `calendar`,
    `eod_equity_history`, `activities_fills`, `fee_activities`, `distributions`,
    `corporate_actions`. `_get` is shared with `fetch_bars`, as AlpacaClient's is
    with `scripts/rv/alpaca_daily.fetch_bars`."""

    def __init__(self, book: str, *, key_id: str, secret: str, transport: Transport = urllib_transport,
                 sleep=time.sleep):
        if not isinstance(book, str) or not _BOOK_RE.fullmatch(book):
            raise ValueError(f"book {book!r} must be a lowercase name like 'cef'")
        if not key_id or not secret:
            raise MissingCredential(f"book {book!r}: an empty key id or secret was passed")
        for value, name in zip((key_id, secret), env_names(book)):
            if not isinstance(value, str) or not _KEY_RE.fullmatch(value):
                raise MalformedCredential(f"book {book!r}: {name} is not one word of printable ASCII (a line "
                                          f"break, a space or a control character in it?); the value is not shown, "
                                          f"and no request was made")
        self.book = book
        self._key_id = key_id
        self._secret = secret
        self._transport = transport
        self._sleep = sleep

    @classmethod
    def from_environment(cls, book: str, *, environ: dict | None = None, **kw) -> "AlpacaReader":
        """Keys from the process environment only: `ALPACA_<BOOK>_KEY_ID` and
        `ALPACA_<BOOK>_SECRET_KEY`. On the VM systemd puts them there with
        `EnvironmentFile=` from the tmpfs file `install_vm --reports`'s key service wrote;
        this module opens no file. A missing one raises naming the variable; another
        book's key is never substituted (landmine 2: one account per book)."""
        env = os.environ if environ is None else environ
        kid_name, sec_name = env_names(book)
        missing = [n for n in (kid_name, sec_name) if not env.get(n)]
        if missing:
            raise MissingCredential(f"book {book!r}: {', '.join(missing)} not set in the process "
                                    f"environment. The report job reads each book's own keys from the "
                                    f"run-time env file systemd loads (docs/RUNBOOK.md 8.12); no other "
                                    f"book's key is substituted.")
        return cls(book, key_id=env[kid_name], secret=env[sec_name], **kw)

    def __repr__(self) -> str:
        return f"AlpacaReader(book={self.book!r}, base_url={PAPER_BASE!r}, data_url={DATA_BASE!r})"

    __str__ = __repr__

    def _scrub(self, text: str) -> str:
        for v in (self._key_id, self._secret):
            if v:
                text = text.replace(v, "<redacted>")
        return text

    def _get(self, base: str, path: str, params: dict | None = None, *, allow_404: bool = False):
        """GET with bounded retry on 429, 5xx and transport errors. A GET changes nothing
        at the broker, so retrying is safe. The base must be exactly one of the two hosts
        (a typo or an injected value raises, never a request). Any other non-200 or a body
        that is not JSON raises with the path and Alpaca's message, never the keys."""
        if base not in (PAPER_BASE, DATA_BASE):
            raise ValueError(f"refusing base {base!r}: this reader talks only to {PAPER_BASE} "
                             f"and {DATA_BASE}")
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError(f"refusing path {path!r}: it must start with '/'")
        qs = "?" + urllib.parse.urlencode({k: str(v) for k, v in params.items()}) if params else ""
        url = base + path + qs
        headers = {"APCA-API-KEY-ID": self._key_id, "APCA-API-SECRET-KEY": self._secret,
                   "Accept": "application/json", "User-Agent": "quantt-report-reader/1"}
        attempts = len(GET_BACKOFF_S) + 1
        last, status = "", None
        for i in range(attempts):
            if i:
                self._sleep(GET_BACKOFF_S[i - 1])
            try:
                status, text = self._transport(url, headers, TIMEOUT_S)
            except (OSError, http.client.HTTPException) as e:
                last = f"{type(e).__name__}: {e}"
                status = None
                continue
            if status == 404 and allow_404:
                return None
            if status == 429 or 500 <= status < 600:
                last = f"HTTP {status}: {text[:300]}"
                continue
            if status != 200:
                raise AlpacaHTTPError(self._scrub(f"GET {path} -> HTTP {status}: {text[:300]}"), status=status)
            try:
                return json.loads(text)
            except ValueError:
                raise UnexpectedResponse(self._scrub(
                    f"GET {path} -> HTTP 200 with a body that is not JSON: {text[:300]}")) from None
        raise AlpacaHTTPError(self._scrub(f"GET {path} failed after {attempts} attempts; last: {last}"),
                              status=status)

    # ---------------------------------------------------------- reads

    def calendar(self, start: dt.date, end: dt.date) -> list[dict]:
        """GET /v2/calendar for [start, end] inclusive, each date checked to lie inside it.
        AlpacaClient.calendar, read for read: `open`/`close` stay Alpaca's wall-clock strings."""
        start, end = _date_param(start, "start"), _date_param(end, "end")
        if end < start:
            raise ValueError(f"end {end} is before start {start}")
        raw = self._get(PAPER_BASE, "/v2/calendar", {"start": start.isoformat(), "end": end.isoformat()})
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

    EOD_LISTS = ("timestamp", "equity", "profit_loss", "profit_loss_pct")
    # A 1D point is stamped this many hours after its session's calendar close, New York
    # wall-clock time: AlpacaClient.EOD_STAMP_AFTER_CLOSE_H since PR #83 (cf3eac4; module
    # docstring, THE HALF-DAY EOD STAMP), the same constant under the same name.
    EOD_STAMP_AFTER_CLOSE_H = 4

    def eod_equity_history(self, start: dt.date, end: dt.date) -> list[EODPoint]:
        """AlpacaClient.eod_equity_history as PR #83 (cf3eac4) has it, read for read (module
        docstring, THE HALF-DAY EOD STAMP): every 1D stamp's New York date must be a
        trading day by one /v2/calendar read, and its New York wall-clock time must equal that
        day's calendar `close` + EOD_STAMP_AFTER_CLOSE_H hours exactly (20:00:00 on a 16:00
        close, 17:00:00 on a 13:00 half day), or the call raises naming it (a session filed
        under the wrong date is the failure this refuses). A date the calendar lists twice
        raises (its close is not known), and so does a close 4 hours after which is not a time
        on that date. The check runs after the calendar read, never inside the stamp loop.
        Leading zeros before funding are dropped by name; a zero after funding raises."""
        start, end = _date_param(start, "start"), _date_param(end, "end")
        if end < start:
            raise ValueError(f"end {end} is before start {start}")
        months = (end.year - start.year) * 12 + (end.month - start.month) + 2
        raw = self._get(PAPER_BASE, "/v2/account/portfolio/history",
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
            try:
                when = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
            except (ValueError, OverflowError, OSError):
                raise UnexpectedResponse(f"{w}: timestamp[{i}] = {ts} is outside the clock's range") from None
            x = _num({"equity": eq}, "equity", f"{w} [{i}]")
            if not math.isfinite(x):
                raise UnexpectedResponse(f"{w}: equity[{i}] = {eq!r} is not finite")
            stamps.append(when)
            equities.append(x)
        if any(b <= a for a, b in zip(stamps, stamps[1:])):
            raise UnexpectedResponse(f"{w}: timestamps are not strictly increasing")
        if not stamps:
            return []

        local = [s.astimezone(NY) for s in stamps]
        # One /v2/calendar read gives each session's close (AlpacaClient since PR #83, cf3eac4).
        cal = {}
        for row in self.calendar(local[0].date(), local[-1].date()):
            # A date served twice with two closes would let the later row pick the accepted time.
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
        later_zero = [local[i].date().isoformat() for i in range(funded, len(equities)) if equities[i] == 0]
        if later_zero:
            raise UnexpectedResponse(f"{w}: equity 0 on {later_zero}, after the account was funded; only "
                                     f"the days before funding may be 0")
        return [EODPoint(local[i].date(), equities[i], stamps[i])
                for i in range(funded, len(equities)) if start <= local[i].date() <= end]

    FILL_FIELDS = ("id", "activity_type", "order_id", "symbol", "side", "qty", "price",
                   "cum_qty", "leaves_qty", "transaction_time", "type", "order_status")

    def activities_fills(self, date: dt.date) -> list[dict]:
        """GET /v2/account/activities/FILL for one date, every page, oldest first.
        AlpacaClient.activities_fills, read for read: `page_token` = the last row's id,
        page_size 100, a short page ends it, a repeated token raises."""
        date = _date_param(date, "date")
        out, seen, token = [], set(), None
        for _ in range(MAX_PAGES):
            params = {"date": date.isoformat(), "direction": "asc", "page_size": FILL_PAGE_SIZE}
            if token is not None:
                params["page_token"] = token
            page = self._get(PAPER_BASE, "/v2/account/activities/FILL", params)
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

    def fee_activities(self) -> list[dict]:
        """GET /v2/account/activities/FEE, every page, oldest first: the raw rows.

        The check beside the attribution's modelled fees (`live_attribution`, FEES: the
        per-session totals equalled the model on 34 of 34 sessions, 2026-11-02). AlpacaClient
        has no such method, so there is nothing to hold this equal to; the paging is
        `activities_fills`'s. UNBOUNDED ON PURPOSE: with `until=2026-10-31` the 10-30 rows were
        missing (the live_attribution docstring: `until` appears to filter on posting time,
        not trade date), so no date filter is sent and the caller filters. Each row must be
        an object with `id` and `activity_type` == "FEE" [V: ALPACA_API_FACTS §activities];
        the amount and date fields are read by the caller, which names any that are absent."""
        out, seen, token = [], set(), None
        for _ in range(MAX_PAGES):
            params = {"direction": "asc", "page_size": FILL_PAGE_SIZE}
            if token is not None:
                params["page_token"] = token
            page = self._get(PAPER_BASE, "/v2/account/activities/FEE", params)
            if not isinstance(page, list):
                raise UnexpectedResponse(f"GET /v2/account/activities/FEE: expected a list, "
                                         f"got {type(page).__name__}")
            for i, a in enumerate(page):
                w = f"GET /v2/account/activities/FEE[{i}]"
                _require(a, ("id", "activity_type"), w)
                if a["activity_type"] != "FEE":
                    raise UnexpectedResponse(f"{w}: activity_type {a['activity_type']!r}")
                if a["id"] not in seen:
                    seen.add(a["id"])
                    out.append(a)
            if len(page) < FILL_PAGE_SIZE:
                return out
            nxt = page[-1]["id"]
            if nxt == token:
                raise UnexpectedResponse("GET /v2/account/activities/FEE: page_token did not advance")
            token = nxt
        raise UnexpectedResponse(f"GET /v2/account/activities/FEE: more than {MAX_PAGES} pages")

    def corporate_action_activities(self) -> list[dict]:
        """GET /v2/account/activities?activity_types=<CORPORATE_ACTION_ACTIVITY_TYPES>, every
        page, oldest first: the account's own corporate-action rows, each read strictly.

        WHY (team lead, 2026-11-14, on the corporate-action investigation). Alpaca paper does not
        process corporate actions (docs/REFERENCES.md §12pc), and when support pushes one by
        hand the account's activities are the only record of what moved: the attribution
        rebuilds positions from FILLs plus these rows, never from the market feed, whose rebase
        gives the wrong sign when paper kept the old count. The cef account had 0 such rows
        (2026-11-14), so this reads nothing today.

        STRICT, BECAUSE THE REST SHAPE OF THESE ROWS IS UNDOCUMENTED. Alpaca documents a SPLIT
        only in the Activity SSE (two legs per split: the old count out at the old price, the new
        count in at the new price, `qty` signed, `price` per share). This read accepts a row only
        if it has: `id` (a non-empty string), `activity_type` (one of the types asked for),
        `date` (YYYY-MM-DD) and `symbol` (an upper-case equity symbol); and, for a cash-in-lieu
        row (CA_CASH_ACTIVITY_TYPES), `net_amount`, a finite decimal string; for every other
        type, `qty`, a non-zero whole number of shares as a decimal string (signed: the
        position's change), and `price`, a positive decimal string. Anything else raises,
        naming the row and the field: a row this read cannot place is never skipped. Paging is
        `fee_activities`'s; unbounded on purpose, as there (the caller filters by date)."""
        types = ",".join(CORPORATE_ACTION_ACTIVITY_TYPES)
        w0 = "GET /v2/account/activities?activity_types=" + types
        out, seen, token = [], set(), None
        for _ in range(MAX_PAGES):
            params = {"activity_types": types, "direction": "asc", "page_size": FILL_PAGE_SIZE}
            if token is not None:
                params["page_token"] = token
            page = self._get(PAPER_BASE, "/v2/account/activities", params)
            if not isinstance(page, list):
                raise UnexpectedResponse(f"{w0}: expected a list, got {type(page).__name__}")
            for i, a in enumerate(page):
                w = f"{w0} [{i}]"
                _require(a, ("id", "activity_type", "date", "symbol"), w)
                if not isinstance(a["id"], str) or not a["id"].strip():
                    raise UnexpectedResponse(f"{w}: id {a['id']!r} is not a non-empty string")
                if a["activity_type"] not in CORPORATE_ACTION_ACTIVITY_TYPES:
                    raise UnexpectedResponse(f"{w}: activity_type {a['activity_type']!r} was not asked for")
                if not (isinstance(a["date"], str) and _DATE_RE.match(a["date"])):
                    raise UnexpectedResponse(f"{w}: date {a['date']!r} is not YYYY-MM-DD")
                if not (isinstance(a["symbol"], str) and _SYMBOL_RE.match(a["symbol"])):
                    raise UnexpectedResponse(f"{w}: symbol {a['symbol']!r} is not an upper-case equity symbol")
                if a["activity_type"] in CA_CASH_ACTIVITY_TYPES:
                    _require(a, ("net_amount",), w)
                    if _decimal(a["net_amount"], f"{w} net_amount") is None:
                        raise UnexpectedResponse(f"{w}: net_amount {a['net_amount']!r} is not a finite decimal string")
                else:
                    _require(a, ("qty", "price"), w)
                    q = _decimal(a["qty"], f"{w} qty")
                    if q is None or q == 0 or q != q.to_integral_value():
                        raise UnexpectedResponse(f"{w}: qty {a['qty']!r} is not a non-zero whole number of shares")
                    px = _decimal(a["price"], f"{w} price")
                    if px is None or px <= 0:
                        raise UnexpectedResponse(f"{w}: price {a['price']!r} is not a positive decimal string")
                if a["id"] not in seen:
                    seen.add(a["id"])
                    out.append(a)
            if len(page) < FILL_PAGE_SIZE:
                return out
            nxt = page[-1]["id"]
            if nxt == token:
                raise UnexpectedResponse(f"{w0}: page_token did not advance")
            token = nxt
        raise UnexpectedResponse(f"{w0}: more than {MAX_PAGES} pages")

    def distributions(self, symbols, start: dt.date, end: dt.date) -> list[dict]:
        """Cash dividends and capital-gains distributions for `symbols` from the data API,
        every page: AlpacaClient.distributions, read for read (`amount` is the cash per
        share; the window filters on process date, which the caller pads; absence is not
        proof of no distribution)."""
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
            body = self._get(DATA_BASE, "/v1/corporate-actions", params)
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

    def corporate_actions(self, symbols, start: dt.date, end: dt.date, *, rows: dict | None = None) -> list[dict]:
        """Every non-dividend corporate action naming one of `symbols`, in any role: the
        strict read of AlpacaClient.corporate_actions (no `skipped` record), read for read;
        `rows` collects each kept row's raw object by id, as AlpacaClient's `rows` does.
        No `symbols` filter is sent; `data_quality=all`; the window filters on process date,
        which the caller pads; an empty answer is what the feed holds now, not a measured
        zero. The attribution reads the events and, through `rows`, a split's old_rate/new_rate
        (`live_attribution`, CORPORATE ACTIONS)."""
        raw_rows = rows                          # the loop below reuses the name `rows` for a page's list
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
        w = "GET /v1/corporate-actions"
        out, seen = [], {}
        token = None
        for _ in range(MAX_PAGES):
            params = {"types": ",".join(CORPORATE_ACTION_TYPES),
                      "start": start.isoformat(), "end": end.isoformat(), "limit": 1000,
                      "data_quality": "all"}
            if token is not None:
                params["page_token"] = token
            body = self._get(DATA_BASE, "/v1/corporate-actions", params)
            _require(body, ("corporate_actions", "next_page_token"), w)
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
                    parties, unread = _ca_parties(r, kind, fields, where)
                    if unread:
                        raise UnexpectedResponse(unread[0]["error"])
                    if any(s in wanted for s, _ in parties):
                        _ca_strict(r, kind, date_field, parties, where, seen, out, raw_rows)
            nxt = body["next_page_token"]
            if nxt is None or nxt == "":
                break
            if not isinstance(nxt, str):
                raise UnexpectedResponse(f"{w}: next_page_token {nxt!r} is not a string or null")
            if nxt == token:
                raise UnexpectedResponse(f"{w}: next_page_token did not advance")
            token = nxt
        else:
            raise UnexpectedResponse(f"{w}: more than {MAX_PAGES} pages")
        return sorted(out, key=lambda e: (e["date"], e["type"], e["id"]))


# ------------------------------------------------------------ SIP daily bars
# scripts/rv/alpaca_daily.fetch_bars, read for read: that module's function-level
# import of the broker client would put `quantt.broker` in the job's closure, so
# the bars read lives here too. A test holds the two frames equal on one fixture.

def _ny(d: dt.date, hh: int) -> str:
    return dt.datetime(d.year, d.month, d.day, hh, tzinfo=NY).isoformat()


def _paged(client, path: str, params: dict, key: str):
    token = None
    for _ in range(MAX_PAGES):
        p = dict(params)
        if token:
            p["page_token"] = token
        body = client._get(DATA_BASE, path, p)
        if not isinstance(body, dict) or key not in body or "next_page_token" not in body:
            raise UnexpectedResponse(f"GET {path}: response lacks {key!r} or next_page_token")
        yield body[key] or {}
        token = body["next_page_token"]
        if not token:
            return
    raise UnexpectedResponse(f"GET {path}: more than {MAX_PAGES} pages")


def parse_bars(bars: dict, requested: set) -> list[dict]:
    rows = []
    for sym, items in bars.items():
        if sym not in requested:
            raise UnexpectedResponse(f"bars: symbol {sym!r} returned but not requested")
        for i, b in enumerate(items):
            missing = [f for f in ("t", "o", "h", "l", "c", "v") if f not in b or b[f] is None]
            if missing:
                raise UnexpectedResponse(f"bars {sym}[{i}]: missing {missing}")
            ts = pd.Timestamp(b["t"])
            if ts.tzinfo is None:
                raise UnexpectedResponse(f"bars {sym}[{i}]: timestamp {b['t']!r} has no offset")
            local = ts.tz_convert(NY)
            if (local.hour, local.minute, local.second, local.microsecond) != (0, 0, 0, 0):
                raise UnexpectedResponse(f"bars {sym}[{i}]: daily bar stamped {b['t']} = {local} NY, "
                                         f"not midnight; the date mapping would be wrong")
            rows.append({"date": pd.Timestamp(local.date()), "ticker": sym,
                         "open": float(b["o"]), "high": float(b["h"]), "low": float(b["l"]),
                         "close": float(b["c"]), "volume": float(b["v"])})
    return rows


BAR_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "volume"]


def fetch_bars(client, symbols, start: dt.date, end: dt.date) -> pd.DataFrame:
    """SIP daily bars, raw, for `symbols` on [start, end] (NY dates), through `client._get`
    (an AlpacaReader, or any object with the same `_get`). Raises on a duplicate or
    non-positive bar and on a symbol with no bars at all."""
    symbols = sorted(set(symbols))
    rows = []
    for i in range(0, len(symbols), SYMBOLS_PER_REQUEST):
        chunk = symbols[i:i + SYMBOLS_PER_REQUEST]
        params = {"symbols": ",".join(chunk), "timeframe": "1Day", "feed": FEED,
                  "adjustment": ADJUSTMENT, "start": _ny(start, 0), "end": _ny(end, 20),
                  "limit": BARS_LIMIT, "sort": "asc"}
        for page in _paged(client, "/v2/stocks/bars", params, "bars"):
            rows.extend(parse_bars(page, set(chunk)))
    df = pd.DataFrame(rows, columns=BAR_COLUMNS)
    if df.empty:
        raise UnexpectedResponse(f"bars: nothing returned for {symbols} on {start}..{end}")
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    dup = df[df.duplicated(["ticker", "date"], keep=False)]
    if not dup.empty:
        raise UnexpectedResponse(f"bars: duplicate (ticker, date): {dup[['ticker', 'date']].values.tolist()[:10]}")
    bad = df[(df[["open", "high", "low", "close"]] <= 0).any(axis=1) | (df["volume"] < 0)]
    if not bad.empty:
        raise UnexpectedResponse(f"bars: non-positive price or negative volume: {bad.head().to_dict('records')}")
    absent = sorted(set(symbols) - set(df["ticker"]))
    if absent:
        raise UnexpectedResponse(f"bars: no bars at all for {absent} on {start}..{end}")
    return df


def last_complete_date(now: dt.datetime | None = None) -> dt.date:
    """Yesterday in New York (scripts/rv/alpaca_daily.last_complete_date): a run during a
    session must not read a partial day."""
    now = dt.datetime.now(NY) if now is None else now.astimezone(NY)
    return now.date() - dt.timedelta(days=1)
