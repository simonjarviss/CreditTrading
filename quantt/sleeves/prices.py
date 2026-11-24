"""The official daily close of one session for a list of symbols, from Alpaca's daily bars.

WHY THIS MODULE. The sleeves trade whatever the shadow books name: operating companies, units,
closed-end funds, IWM. No panel in this repository covers that set, and the runner must size on
the as-of session's close and mark on the session's own close. Alpaca's `/v2/stocks/bars`
(1Day, raw, SIP) is the one source that covers every symbol the account can trade.

WHY THE CLIENT'S PRIVATE GET. `AlpacaClient` has no public daily-bar method and this stage may
not edit the client. The request goes through `client._get(client._data, ...)`, exactly as
`results/ideas/reverse_splits/borrow_now.py` does, and never through a session of this module's
own, because three protections live in that method and must stay the client's: the key headers
are attached there and nowhere else, a redirect is refused before a second request is built
(`alpaca.refuse_redirects`: `requests` would carry the two key headers to another host), and
every error message is scrubbed of the keys before it leaves the object. A second transport
here would be a second place to get each of those wrong. A public method on the client is the
right home once the team lead allows the edit.

WHAT IS RETURNED, AND WHAT IS NOT. `{symbol: close}` for every symbol whose bar for `day` exists.
A symbol with no bar that day is ABSENT: a halted or unlisted name has no close, and this module
never substitutes another day's (CLAUDE.md: no silent fallbacks, no lookahead). The caller
decides what a missing price means: at PLAN a sleeve naming that symbol holds; at VERIFY a
sleeve holding it is not scored that day.

ALIGNMENT. `start` and `end` are both `day`, and every bar returned must be dated `day` in New
York or the read raises: a bar for any other date is never used, so a close can never come from
after the date it is used on. `adjustment=raw`: the price is the one printed that day, the basis
the broker's share counts are on (paper processes no splits; CLAUDE.md landmine 1).

`start = end = day` returns exactly that day's bar, stamped 05:00Z, midnight in New York
[V 2026-11-16: the coordinator's GET-only read; this module's author has run nothing against
Alpaca]. The stamp is a UTC instant, so the bar's date is read by CONVERTING it to New York,
never by slicing the string: a midnight-New-York stamp is 04:00Z in summer and 05:00Z in
winter, and any stamp before 04:00Z/05:00Z belongs to the previous New York day.

THE SAME-DAY READ, AND WHY `end` IS A TIMESTAMP THEN. These paper accounts' data plan refuses any
SIP query whose window reaches into the last 15 minutes: HTTP 403 "subscription does not permit
querying recent SIP data". A date-only `end` means the END of that day, so on the evening of
`day` itself `end=day` is refused, and the book's first VERIFY failed on exactly that at 17:35 ET
on 2026-11-20 (results/report/EVIDENCE_LOG.md). Measured the same evening on the core account's
keys, GET only [V 2026-11-20 17:43 ET]: `end=<day>` 403; `end=now-14min` 403; `end=now-16min`
200 with the day's bar; the day before with `end=<day>` 200. So while `day` is not yet
`SIP_DELAY` in the past, `end` is the instant `utcnow - SIP_DELAY`; once it is, `end` stays the
date, as before. The bar is the same either way, and the date check below still refuses any
other day's. Measured, GET only [V 2026-11-22]: for 2026-11-19 and 2026-11-20, eight symbols,
`end` as the date, as 21:00Z and as 22:15Z of that day returned the same close and volume; and
the IWM and EIM closes served at 17:43 ET on 2026-11-20 were unchanged two days later.

A DAY THAT HAS NOT CLOSED HAS NO CLOSE. Before the fix the 403 also, by accident, stopped a read
of today's bar at midday, when its `c` is only the last trade so far. That protection is now
explicit: a same-day read before `CLOSE_ET` + `SIP_DELAY` raises. 16:00 is the latest close the
exchange has; on a half day the bar is final earlier and the read simply waits longer than it
must.

NOT VERIFIED: that a daily bar is never revised after the evening it is first served (two symbols
on one day is not a rule), and that the bar is final as early as 16:20 ET, the first minute a
same-day read is allowed; the scheduled VERIFY runs at 17:35 ET. VERIFY marks on what is served
when it runs.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
SYMBOL = re.compile(r"[A-Z][A-Z0-9.]{0,9}")      # as inputs.SYMBOL and the client's _SYMBOL_RE
CHUNK = 100                                      # symbols per request: keeps the URL short
PAGE_LIMIT = 10000                               # /v2/stocks/bars: limit max 10000 [S: Alpaca docs, not re-read]
MAX_PAGES = 50                                   # one bar a symbol: more pages than this is a bug
SIP_DELAY = dt.timedelta(minutes=20)             # the plan refuses the last 15 minutes [V 2026-11-20]; 5 spare
                                                 # for a machine clock that runs ahead of Alpaca's
CLOSE_ET = dt.time(16, 0)                        # the latest regular close; a half day closes earlier


class PriceError(RuntimeError):
    """The bars response cannot be trusted; the message names the symbol and the field."""


def _bar_close(sym: str, bar, day: dt.date) -> float:
    if not isinstance(bar, dict) or "t" not in bar or "c" not in bar:
        raise PriceError(f"{sym}: bar {bar!r} lacks t or c")
    try:
        t = dt.datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00"))
    except ValueError:
        raise PriceError(f"{sym}: bar time {bar['t']!r} is not a timestamp") from None
    if t.tzinfo is None:
        raise PriceError(f"{sym}: bar time {bar['t']!r} has no time zone")
    # ALIGNMENT: the bar must be the asked session's own, read in the exchange's zone.
    if t.astimezone(NY).date() != day:
        raise PriceError(f"{sym}: bar dated {t.astimezone(NY).date()} returned for {day}; "
                         "never used for another day")
    c = bar["c"]
    if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) or c <= 0:
        raise PriceError(f"{sym}: close {c!r} on {day} is not a finite number > 0")
    return float(c)


def _end_param(day: dt.date, utcnow: dt.datetime) -> str:
    """The `end` to send for `day` at `utcnow` (module docstring, "THE SAME-DAY READ")."""
    if not isinstance(utcnow, dt.datetime) or utcnow.tzinfo is None:
        raise PriceError(f"utcnow {utcnow!r} must be a datetime with a time zone")
    cutoff = utcnow.astimezone(dt.timezone.utc) - SIP_DELAY
    day_end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0), NY)
    if day_end <= cutoff:
        return day.isoformat()                    # the whole day is old enough: the date, as before
    closed = dt.datetime.combine(day, CLOSE_ET, NY)
    if cutoff < closed:
        raise PriceError(f"the close of {day} is not readable at {utcnow.astimezone(NY):%Y-%m-%d %H:%M} ET: "
                         f"the data plan serves SIP data only {int(SIP_DELAY.total_seconds() // 60)} minutes old, "
                         f"and the session is not over before {CLOSE_ET:%H:%M} ET; no partial day's bar is "
                         "used as a close")
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def closes(client, symbols, day: dt.date, utcnow: dt.datetime) -> dict:
    """{symbol: close of `day`} from `/v2/stocks/bars`; a symbol with no bar that day is absent.
    `utcnow` is the caller's clock: it decides only the `end` of the request, never the price."""
    if not isinstance(day, dt.date) or isinstance(day, dt.datetime):
        raise PriceError(f"day {day!r} must be a datetime.date")
    end = _end_param(day, utcnow)
    syms = sorted(set(symbols))
    for s in syms:
        if not isinstance(s, str) or not SYMBOL.fullmatch(s):
            raise PriceError(f"symbol {s!r} is not an upper-case equity symbol")
    out: dict = {}
    for i in range(0, len(syms), CHUNK):
        chunk = syms[i:i + CHUNK]
        token, seen_tokens = None, set()
        for _ in range(MAX_PAGES):
            params = {"symbols": ",".join(chunk), "timeframe": "1Day", "adjustment": "raw",
                      "feed": "sip", "start": day.isoformat(), "end": end,
                      "limit": PAGE_LIMIT}
            if token is not None:
                params["page_token"] = token
            body = client._get(client._data, "/v2/stocks/bars", params)
            if not isinstance(body, dict) or "bars" not in body:
                raise PriceError(f"/v2/stocks/bars for {day}: the response has no 'bars'")
            bars = body["bars"]
            if bars is None:                      # Alpaca sends null when no symbol has a bar
                bars = {}
            if not isinstance(bars, dict):
                raise PriceError(f"/v2/stocks/bars for {day}: 'bars' is {type(bars).__name__}, not an object")
            for sym, rows in bars.items():
                if sym not in chunk:
                    raise PriceError(f"/v2/stocks/bars for {day}: bars for {sym!r}, which was not asked for")
                if not isinstance(rows, list):
                    raise PriceError(f"{sym}: bars are {type(rows).__name__}, not a list")
                for bar in rows:
                    c = _bar_close(sym, bar, day)
                    if sym in out:
                        raise PriceError(f"{sym}: two daily bars for {day}")
                    out[sym] = c
            token = body.get("next_page_token")
            if not token:
                break
            if token in seen_tokens:
                raise PriceError(f"/v2/stocks/bars for {day}: next_page_token did not advance")
            seen_tokens.add(token)
        else:
            raise PriceError(f"/v2/stocks/bars for {day}: more than {MAX_PAGES} pages")
    return out
