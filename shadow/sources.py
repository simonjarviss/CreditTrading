"""The two real price sources behind `marks.build`: Alpaca's auction prints, yfinance's close.

WHY A FACADE AND NOT THE CLIENT: `quantt.broker.alpaca.AlpacaClient` can also send an
order to its paper account. A shadow book must not be able to (shadow/__init__.py), so
this module wraps the client in `ReadOnlyData`, which holds it privately and offers only
three read calls. `shadow/tests/test_boundary.py` fails if this package ever names an
order method.

WHICH KEY: the core (`cef`) paper account's (team lead, 2026-11-09, docs/SYSTEM.md
section 5: "use the accounts we already have access to"; the first ruling that day, an
otherwise empty account, was superseded). That key CAN trade the core's paper account,
so this facade and the boundary test are the whole defence: keep both. On the VM the
shadow user holds its own copy of that one key. `book` names it: the client reads
ALPACA_<BOOK>_KEY_ID / _SECRET_KEY from the file QUANTT_ENV_FILE names, and raises if
either is missing. Nothing here prints or returns a credential.

Network imports happen inside the functions, so importing this module opens no socket
(pytest.ini's rule for a collected directory).
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

# Alpaca files a dividend under a process date near its PAYABLE date, weeks after the
# ex-date (the client's `distributions` docstring), so an ex-date window is queried this
# many days wider at the end and then filtered on ex_date itself.
DIST_WINDOW_PAD_DAYS = 75

# Asset `exchange` -> SIP exchange NAME, for listings the broker client's own map
# (ASSET_EXCHANGE_SIP_NAME: NYSE, AMEX, NASDAQ) does not cover. The client's map is the
# live path's and is not widened from here. Each entry is measured, never assumed:
#   ARCA -> "NYSE Arca" (SIP code P). [V 2026-11-09: /v2/assets/SPY says ARCA;
#   /v2/stocks/meta/exchanges names P "NYSE Arca"; SPY's 2026-11-06 closing prints carry
#   (P, condition M) = the official close.]
# A listing on any other exchange (Cboe BZX, IEX) raises, naming it, until someone
# measures its row and adds it here.
EXTRA_EXCHANGE_SIP_NAME = {"ARCA": "NYSE Arca"}

# Symbols whose official close is NOT on the exchange Alpaca's asset record names. Each is
# measured, never assumed, and an entry is the only way a print from another venue is used.
#   ET, SUN, SUNC, USAC -> "Texas Stock Exchange" (SIP code F). [V 2026-11-14: /v2/assets
#   says NYSE for all four; on 2026-11-13 none has a condition-M print under N; each has one
#   under F that equals Yahoo's close to the cent (19.40, 65.23, 66.00, 25.14), and they had
#   no N print on any of the six sessions 2026-11-06..13. They are one corporate family.]
# Found because the units shadow books hold them: without this every session those books
# were invested read UNMEASURED.
SYMBOL_PRIMARY_SIP_NAME = {"ET": "Texas Stock Exchange", "SUN": "Texas Stock Exchange",
                           "SUNC": "Texas Stock Exchange", "USAC": "Texas Stock Exchange"}


class ReadOnlyData:
    """Auction prints and distributions from Alpaca's data API. Read-only by construction."""

    def __init__(self, book: str):
        from quantt.broker.alpaca import AlpacaClient
        self.__client = AlpacaClient.from_environment(book)
        self.__exchanges = None
        self.__codes: dict = {}

    def prints(self, symbols: list, day: dt.date) -> dict:
        """{symbol: official closing-auction price} for the symbols that have one on `day`.
        A symbol whose primary exchange printed no auction is ABSENT, never filled from
        another venue or a bar close."""
        from quantt.broker.alpaca import MissingAuctionPrint
        c = self.__client
        if self.__exchanges is None:
            self.__exchanges = c.stock_exchanges()
        for s in symbols:
            if s not in self.__codes:
                self.__codes[s] = self._primary_code(s)
        want = list(symbols)
        try:
            got = c.closing_auction_prints(want, day, exchange_codes={s: self.__codes[s] for s in want})
        except MissingAuctionPrint as e:
            want = [s for s in want if s not in set(e.symbols)]
            if not want:
                return {}
            # the second call names only symbols the first did not report missing
            got = c.closing_auction_prints(want, day, exchange_codes={s: self.__codes[s] for s in want})
        return {s: float(v["price"]) for s, v in got.items()}

    def _primary_code(self, symbol: str) -> str:
        """The SIP code of the symbol's primary listing: the client's verified map first,
        then EXTRA_EXCHANGE_SIP_NAME. Exactly one code must carry the name, else raise."""
        from quantt.broker.alpaca import ASSET_EXCHANGE_SIP_NAME, UnmappedExchange
        ex = self.__client.asset(symbol)["exchange"]
        name = (SYMBOL_PRIMARY_SIP_NAME.get(symbol) or ASSET_EXCHANGE_SIP_NAME.get(ex)
                or EXTRA_EXCHANGE_SIP_NAME.get(ex))
        if name is None:
            raise UnmappedExchange(f"{symbol}: asset exchange {ex!r} has no measured SIP name "
                                   "(shadow/sources.py EXTRA_EXCHANGE_SIP_NAME)")
        codes = sorted(k for k, v in self.__exchanges.items() if v == name)
        if len(codes) != 1:
            raise UnmappedExchange(f"{symbol}: {len(codes)} SIP codes named {name!r}; need exactly one")
        return codes[0]

    def distributions(self, symbols: list, first: dt.date, last: dt.date) -> list:
        evs = self.__client.distributions(list(symbols), first,
                                          last + dt.timedelta(days=DIST_WINDOW_PAD_DAYS))
        return [{"symbol": e["symbol"], "ex_date": e["ex_date"], "amount": e["amount"]}
                for e in evs if first <= e["ex_date"] <= last]

    def asset_flags(self, symbol: str) -> dict | None:
        """{tradable, shortable, borrow_status, exchange} for one symbol, or None when Alpaca
        does not list it. Read on its date only: all of these change daily."""
        from quantt.broker.alpaca import AssetNotFound, _SYMBOL_RE
        # The spin-off feed names "new symbols" that are not tickers at all (a contingent value
        # right listed as '457CVR025', seen 2026-11-14). The client refuses to look such a
        # string up, rightly; here it simply is not a listed share.
        if not isinstance(symbol, str) or not _SYMBOL_RE.match(symbol):
            return None
        try:
            a = self.__client.asset(symbol)
        except AssetNotFound:
            return None
        return {"tradable": a["tradable"], "shortable": a["shortable"],
                "borrow_status": a.get("borrow_status"), "exchange": a["exchange"],
                "name": a.get("name") or "", "status": a["status"]}

    def spin_offs(self, first: dt.date, last: dt.date) -> tuple[list, int]:
        """Every spin-off row Alpaca's corporate-actions feed lists with a process date in
        [first, last], for the whole market: ([{id, source_symbol, new_symbol, ex_date,
        process_date}], number of rows left out as unreadable).

        WHY NOT `AlpacaClient.corporate_actions`. That method is the live gate's: it answers
        "does any action name one of OUR symbols" and validates every type for that purpose.
        This asks a different question, which symbols are NEW, so it requests the one type
        and reads five fields. It goes through the client's own GET, so the key headers,
        the redirect refusal and the error scrubbing are the client's, unchanged; the
        client has no public method for a bare request, hence the private call.
        `data_quality=all`: the default leaves out rows still missing a field, and a row
        that is late is exactly what the caller must count.
        A row is unreadable when its id, either symbol or its ex-date is missing or
        malformed. It is counted and left out, never guessed at: it cannot name a tradable
        new symbol, and the caller prints the count."""
        c = self.__client
        rows, bad, token = [], 0, None
        for _ in range(50):
            params = {"types": "spin_off", "start": first.isoformat(), "end": last.isoformat(),
                      "limit": 1000, "data_quality": "all"}
            if token:
                params["page_token"] = token
            body = c._get(c._data, "/v1/corporate-actions", params)
            if not isinstance(body, dict) or "corporate_actions" not in body:
                raise RuntimeError("corporate-actions: the response has no corporate_actions object")
            got = (body["corporate_actions"] or {}).get("spin_offs") or []
            if not isinstance(got, list):
                raise RuntimeError("corporate-actions: spin_offs is not a list")
            for r in got:
                try:
                    ok = (isinstance(r["id"], str) and r["id"] and isinstance(r["source_symbol"], str)
                          and isinstance(r["new_symbol"], str) and r["new_symbol"])
                    row = {"id": r["id"], "source_symbol": r["source_symbol"], "new_symbol": r["new_symbol"],
                           "ex_date": dt.date.fromisoformat(r["ex_date"]),
                           "process_date": dt.date.fromisoformat(r["process_date"])} if ok else None
                except (KeyError, TypeError, ValueError):
                    row = None
                if row is None:
                    bad += 1
                else:
                    rows.append(row)
            token = body.get("next_page_token")
            if not token:
                return rows, bad
        raise RuntimeError("corporate-actions: more than 50 pages of spin-offs; refusing to continue")

    def sessions(self, first: dt.date, last: dt.date) -> list:
        """Trading days from the exchange calendar Alpaca serves."""
        return [dt.date.fromisoformat(str(r["date"])[:10]) for r in self.__client.calendar(first, last)]


def yfinance_closes(symbols: list, first: dt.date, last: dt.date) -> pd.DataFrame:
    """Unadjusted daily closes, long: [date, symbol, close]. The CHECK source only.
    A symbol yfinance returns nothing for is simply absent, and `marks.build` then
    reports its rows as unchecked."""
    import yfinance as yf
    raw = yf.download(sorted(set(symbols)), start=first.isoformat(),
                      end=(last + dt.timedelta(days=1)).isoformat(),
                      auto_adjust=False, progress=False, group_by="column", threads=False)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["date", "symbol", "close"])
    close = raw["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(sorted(set(symbols))[0])
    out = close.stack().rename("close").reset_index()
    out.columns = ["date", "symbol", "close"]
    out["date"] = pd.to_datetime(out["date"]).dt.date
    return out.dropna(subset=["close"])
