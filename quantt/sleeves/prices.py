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

NOT VERIFIED: how soon after the close the SIP daily bar for the same day is served on this
account's data plan. If it is not there yet the read is empty: symbols ABSENT, which holds or
leaves a sleeve unscored, never a wrong price.
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


def closes(client, symbols, day: dt.date) -> dict:
    """{symbol: close of `day`} from `/v2/stocks/bars`; a symbol with no bar that day is absent."""
    if not isinstance(day, dt.date) or isinstance(day, dt.datetime):
        raise PriceError(f"day {day!r} must be a datetime.date")
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
                      "feed": "sip", "start": day.isoformat(), "end": day.isoformat(),
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
