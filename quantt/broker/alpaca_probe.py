"""Read-only probe of the Alpaca PAPER accounts: can each book trade what its spec names?

WHY THIS EXISTS
---------------
The move to Alpaca (team lead, 2026-09-28) rests on facts the public docs do not
settle for OUR instruments. Fetched 2026-09-28 from docs.alpaca.markets: no page
mentions closed-end funds at all; `shortable` and `borrow_status`
(easy_to_borrow / hard_to_borrow) are per-asset fields; ETB shorts carry no
borrow fee, HTB shorts need a paid locate; fractional shares cannot be shorted
or sent `cls`. Whether PDI, PTY, NVG... are tradable and shortable at Alpaca is
therefore a per-symbol measurement, and this is the instrument that takes it.
Nothing downstream -- the broker adapter, the sizing, the v7 `max_gross_stress`
re-derivation -- may assume an answer this probe has not recorded.

WHAT IT DOES, AND THE ONE THING IT CANNOT DO
-------------------------------------------
For each book (one Alpaca paper account per book, team lead 2026-09-28) it
GETs the account, its configuration, every spec-universe asset, the open
positions and the open orders (and, for an opt-in book such as C4, one page of
closed orders for the opening-session read, recorded as a summary only), and
writes what came back, verbatim, to
`results/ops/alpaca_probe/<date>_<book>.json`. It cannot place, replace or
cancel anything: `_get` is the only function that talks to the network and it
issues GET and nothing else. There is no code path to a POST or DELETE here, and
`test_alpaca_probe.py` fails if one appears.

It refuses to run against anything but the paper endpoint. A live key pointed
at this probe would still only read, but the order path is not the only thing
worth separating: a live account's snapshot is not evidence about a paper one.

CREDENTIALS
-----------
Read from `config/.env` (never committed, never printed): per book,
`ALPACA_<BOOK>_KEY_ID` and `ALPACA_<BOOK>_SECRET_KEY`, e.g. `ALPACA_CEF_KEY_ID`.
Only whether each is SET is ever displayed. A missing key raises naming the
variable, never guessing another account's key: two books sharing one key would
silently put them in one account, which is exactly the wash-trade collision the
per-book accounts exist to prevent.

`borrow_status` CHANGES DAILY. A snapshot from this probe is true on its date
only; the adapter must re-read it before every session that shorts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENV_FILE = REPO / "config" / ".env"
OUT_DIR = REPO / "results" / "ops" / "alpaca_probe"

# The only endpoint this probe will talk to. Not configurable on purpose: see
# the module docstring.
PAPER_BASE = "https://paper-api.alpaca.markets"

# Book -> frozen spec. Only the two books the team lead kept (2026-09-28):
# the CEF strategy and the b6 equal-weight credit benchmark.
BOOK_SPECS = {
    "cef": REPO / "ops" / "specs" / "cef_discount.frozen.json",
    "b6": REPO / "ops" / "specs" / "bench_b6_ew_credit.frozen.json",
}
# Books read ONLY when named (`--book c4`), never by the default `all`, so the
# routine probe and ops.orient (which iterate BOOK_SPECS) are unchanged while
# C4 is dark. C4 (CEF trial 52) trades its own paper account, the spare
# connector account (team lead 2026-10-26); its keys are ALPACA_C4_KEY_ID /
# _SECRET_KEY. Its read is the input to re-deriving its gross cap before arming
# (ops/specs/c4_families.frozen.json _max_gross_stress_note, ruling 3;
# `scripts/cef/c4_paper_benchmark.py recap`).
OPT_IN_BOOK_SPECS = {
    "c4": REPO / "ops" / "specs" / "c4_families.frozen.json",
}

# THE OPENING-SESSION READ (quant-reviewer QR1 on the release-check of 336df9d,
# 2026-11-03). The runner trades a book's first session to FULL target only when
# `quantt.session.run.is_opening_session` is True: no position AND no order in the
# account's history EVER filled (team lead 2026-09-28). Otherwise it opens from
# flat at the band EDGE: for C4 on data/cef_families to 2026-10-09 that was 28-42%
# of target and net long +4.7% to +11.1% (the reviewer's measurement, spec v4).
# C4 arms on the spare paper account, which the research loop may also trade
# (CLAUDE.md rule 1's 2026-10-27 exception), so one fill there, even one since
# flattened, changes how C4 opens. Open orders and positions cannot show a past
# fill; this read can. Opt-in books only, so the routine probe of the core and b6
# makes exactly the requests it always made. The value is the runner's own
# function applied to the account's positions and its WHOLE closed-order history
# (release-check of 4f759a9, execution-trader 2: it read the newest 500 only, and the
# arming go reads this on the VM). `_closed_orders` pages it exactly as the runner's
# client does (`AlpacaClient.orders`: oldest first, a time cursor stepped back to the
# last timestamp strictly before a full page's final one, the overlap re-fetched and
# de-duplicated by id), with GET and nothing else. Past CLOSED_ORDERS_MAX_PAGES pages
# the read is UNMEASURED (None), never guessed: the authority is then the session's
# own reading, plan.json's `first_session`, which reads every page.
OPENING_READ_BOOKS = frozenset(OPT_IN_BOOK_SPECS)
CLOSED_ORDERS_PAGE = 500                 # Alpaca's maximum `limit` for GET /v2/orders [V: docs]
CLOSED_ORDERS_MAX_PAGES = 200            # 100,000 orders: far past this account's history
CLOSED_ORDERS_PATH = (f"/v2/orders?status=closed&limit={CLOSED_ORDERS_PAGE}&direction=asc"
                      f"&nested=false")


def _closed_orders_path(after: str | None) -> str:
    """The closed-order GET for one page; `after` (an ISO time, exclusive) URL-encoded."""
    if after is None:
        return CLOSED_ORDERS_PATH
    from urllib.parse import quote
    return f"{CLOSED_ORDERS_PATH}&after={quote(after, safe='')}"


def _closed_orders(session) -> tuple[list, bool]:
    """(every closed order, complete) of the account, oldest first, de-duplicated by id.

    The runner's own paging (`AlpacaClient.orders`), on `_get`: `after` is exclusive, so
    the cursor goes back to the last `submitted_at` strictly earlier than a full page's
    final one and the overlap is re-fetched. Raises, naming it, on what would make that
    skip orders: a page that is not a list, an order without an id or a readable
    submitted_at, a page not in ascending order, a full page all at one timestamp, or a
    cursor that does not advance. `complete` is False past CLOSED_ORDERS_MAX_PAGES."""
    from quantt.broker.alpaca import parse_ts
    out, seen, cursor, cursor_dt = [], set(), None, None
    for _ in range(CLOSED_ORDERS_MAX_PAGES):
        path = _closed_orders_path(cursor)
        page = _get(session, path)
        if not isinstance(page, list):
            raise RuntimeError(f"GET {path}: expected a list, got {type(page).__name__}")
        times = []
        for i, o in enumerate(page):
            if not isinstance(o, dict) or not o.get("id"):
                raise RuntimeError(f"GET {path}[{i}]: an order without an id")
            times.append(parse_ts(o.get("submitted_at"), f"GET {path}[{i}].submitted_at"))
            if o["id"] not in seen:
                seen.add(o["id"])
                out.append(o)
        if any(b < a for a, b in zip(times, times[1:])):
            raise RuntimeError(f"GET {path}: page not in ascending submitted_at order; "
                               f"time-cursor paging would skip orders")
        if len(page) < CLOSED_ORDERS_PAGE:
            return out, True
        earlier = [(t, o["submitted_at"]) for t, o in zip(times, page) if t < times[-1]]
        if not earlier:
            raise RuntimeError(f"GET {path}: a full page of {CLOSED_ORDERS_PAGE} orders all "
                               f"submitted at {page[-1]['submitted_at']}; cannot page on time")
        new_dt, new_cursor = earlier[-1]
        if cursor_dt is not None and new_dt <= cursor_dt:
            raise RuntimeError(f"GET {path}: paging made no progress")
        cursor, cursor_dt = new_cursor, new_dt
    return out, False


def spec_path(book: str) -> Path:
    """The frozen spec of `book`, default or opt-in; an unknown book raises."""
    if book in BOOK_SPECS:
        return BOOK_SPECS[book]
    if book in OPT_IN_BOOK_SPECS:
        return OPT_IN_BOOK_SPECS[book]
    raise KeyError(f"no book {book!r}; the books are {sorted({**BOOK_SPECS, **OPT_IN_BOOK_SPECS})}")

# Asset fields the migration decides on. Shown in the summary as returned, or
# as ABSENT when Alpaca did not send the field -- a missing field is itself a
# finding (the docs list `easy_to_borrow` only in an example payload, not the
# schema), so it is never filled in.
ASSET_FIELDS = ("status", "class", "exchange", "tradable", "shortable",
                "easy_to_borrow", "borrow_status", "marginable",
                "margin_requirement_long", "margin_requirement_short",
                "fractionable")

ACCOUNT_FIELDS = ("status", "currency", "equity", "cash", "buying_power",
                  "multiplier", "shorting_enabled", "trading_blocked",
                  "account_blocked", "transfers_blocked")


# Account identifiers are never written (team lead 2026-10-12). Snapshots land in
# results/ops/, which is tracked in a PUBLIC repository, and the 2026-09-28 one
# carried the paper account's number and ID. Nothing this probe decides on needs
# them. Asset `id`s are Alpaca's public asset UUIDs, the same for every account,
# and are kept.
ACCOUNT_IDENTIFIER_KEYS = ("account_number", "account_id")
REDACTED = "REDACTED (public repository; team lead 2026-10-12)"


def redact(obj, *, is_account: bool = False):
    """`obj` with every account identifier replaced by REDACTED, at any depth:
    keys in ACCOUNT_IDENTIFIER_KEYS anywhere, and `id` on the account object."""
    if isinstance(obj, dict):
        return {k: (REDACTED if k in ACCOUNT_IDENTIFIER_KEYS or (is_account and k == "id")
                    else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


class MissingCredential(RuntimeError):
    """A book's Alpaca key is not set. Names the variable, never a value."""


def env_names(book: str) -> tuple[str, str]:
    b = book.upper()
    return f"ALPACA_{b}_KEY_ID", f"ALPACA_{b}_SECRET_KEY"


def load_credentials(book: str, env: dict) -> tuple[str, str]:
    """Return (key_id, secret) for `book` from `env`, or raise naming what is unset.

    `env` is passed in (not read from os.environ here) so the tests can prove
    the refusal without a real `.env` and without touching the process
    environment.
    """
    kid_name, sec_name = env_names(book)
    missing = [n for n in (kid_name, sec_name) if not env.get(n)]
    if missing:
        raise MissingCredential(
            f"book {book!r}: {', '.join(missing)} not set in {ENV_FILE}. "
            f"Each book has its own Alpaca paper account and its own keys; "
            f"no other book's key is substituted.")
    return env[kid_name], env[sec_name]


def read_env_file(path: Path = ENV_FILE) -> dict:
    """The key=value pairs in config/.env, without exporting them to os.environ."""
    if not path.exists():
        raise MissingCredential(f"{path} does not exist")
    from dotenv import dotenv_values
    return {k: v for k, v in dotenv_values(path).items() if v}


def universe(book: str) -> list[str]:
    """The book's tradable names, from its frozen spec -- the only authority.

    The CEF spec is read through `scripts/cef/spec.py` (CLAUDE.md: never read a
    live parameter any other way). The benchmark specs have no accessor module,
    so b6 reads `frozen.universe` from its JSON and raises if it is absent.
    """
    if book == "cef":
        sys.path.insert(0, str(REPO / "scripts" / "cef"))
        import spec  # noqa: E402  (path set just above)
        return list(spec.frozen("universe"))
    d = json.loads(spec_path(book).read_text())
    try:
        return list(d["frozen"]["universe"])
    except KeyError as e:
        raise KeyError(f"{spec_path(book)} has no frozen.universe") from e


def _get(session, path: str, *, allow_404: bool = False):
    """GET `PAPER_BASE + path`. The ONLY network call in this module.

    Returns the decoded JSON, or None for a 404 when `allow_404` (an asset
    Alpaca does not list is a finding, recorded as such, not an error). Any
    other non-200 raises with the path, status and Alpaca's error body; the
    request headers, which hold the keys, are never included.
    """
    url = PAPER_BASE + path
    if not url.startswith(PAPER_BASE + "/"):
        raise ValueError(f"refusing non-paper URL {url!r}")
    # allow_redirects=False: the session carries the key headers, and `requests` would send
    # them to whatever host a 3xx named (quantt.broker.alpaca.refuse_redirects says why).
    try:
        r = session.get(url, timeout=20, allow_redirects=False)
    except Exception as e:
        # `max_redirects = 0` (see `_session`) makes requests raise TooManyRedirects on a 3xx
        # before it contacts the other host. Matched by name: requests is imported lazily here.
        if type(e).__name__ != "TooManyRedirects":
            raise
        st = getattr(getattr(e, "response", None), "status_code", None)
        raise RuntimeError(f"GET {path} -> HTTP {st}: a redirect, NOT followed") from None
    if r.status_code == 404 and allow_404:
        return None
    if r.status_code != 200:
        raise RuntimeError(f"GET {path} -> HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def opening_read(session, positions: list, book: str) -> dict:
    """The opening-session read for one account (OPENING_READ_BOOKS, above): the
    runner's `is_opening_session`, under the BOOK's own rule (its book json's
    `execution.opening_session_fills`, read by `run.opening_session_fills_for`; C4 sets
    "own_prefix": only fills carrying its own order-id prefix count, so the research
    loop's fills in the shared spare account do not make C4's first session open at the
    band edge), on the account's positions and its closed orders.

    Returns {"value": True | False | None, "why", "rule", "positions",
    "closed_orders_read", "filled_orders_read", "counted_fills", "newest_fill"}.
    `filled_orders_read` is every fill read, whoever sent it; `counted_fills` those the
    rule counts. `newest_fill` is the newest fill's symbol, submission time and
    client_order_id prefix (who sent it), or None; no order id, no account identifier.
    Every closed order is read (`_closed_orders`); past its page cap the read is UNMEASURED
    (None), naming plan.json `first_session` as the authority.
    Raises, naming it, on a page that is not a list or an order whose filled_qty cannot
    be read: an unreadable history is not a clean one."""
    from decimal import Decimal, InvalidOperation
    from quantt.session import run as rn
    b = rn.BOOKS[book]
    rule = rn.opening_session_fills_for(b) or rn.OPENING_FILLS_ANY
    own = f"{b.cid_prefix}-"
    page, complete = _closed_orders(session)
    held = {}
    for p in positions:
        if not isinstance(p, dict) or "symbol" not in p:
            raise RuntimeError(f"GET /v2/positions: a position without a symbol: {p!r:.120}")
        held[p["symbol"]] = p.get("qty")
    filled = []
    for o in page:
        try:
            if Decimal(str(o["filled_qty"])) > 0:
                filled.append(o)
        except (KeyError, TypeError, InvalidOperation):
            raise RuntimeError(f"closed order {o.get('client_order_id') if isinstance(o, dict) else o!r}"
                               f": unreadable filled_qty") from None
    counted = [o for o in filled if rule == rn.OPENING_FILLS_ANY
               or str(o.get("client_order_id") or "").startswith(own)]
    runner = rn.is_opening_session(held, page, fills=rule, cid_prefix=b.cid_prefix)
    if held or counted:
        value, why = False, (f"{len(held)} position(s)" if held else
                             f"{len(counted)} counted fill(s) among {len(page)} closed order(s)")
    elif complete:
        value, why = True, (f"no position, and no counted fill in all {len(page)} closed "
                            f"order(s) ({len(filled)} fill(s) read, rule {rule!r})")
    else:
        value, why = None, (f"UNMEASURED: no counted fill in the first {len(page)} closed "
                            f"orders ({CLOSED_ORDERS_MAX_PAGES} pages), and later ones were not "
                            f"read; the session's own plan.json `first_session` is the authority")
    if value is not None and value != runner:
        raise RuntimeError(f"opening read {value} disagrees with run.is_opening_session {runner}")
    newest = None
    if filled:
        o = max(filled, key=lambda x: str(x.get("submitted_at") or ""))
        cid = str(o.get("client_order_id") or "")
        newest = {"symbol": o.get("symbol"), "submitted_at": o.get("submitted_at"),
                  "client_order_id_prefix": cid.split("-")[0] if "-" in cid else "(none)"}
    return {"value": value, "why": why, "rule": rule, "positions": len(held),
            "closed_orders_read": len(page), "filled_orders_read": len(filled),
            "counted_fills": len(counted), "newest_fill": newest}


def probe_book(book: str, session) -> dict:
    """Everything this probe knows about one book's account, as fetched."""
    names = universe(book)
    assets = {}
    for sym in names:
        a = _get(session, f"/v2/assets/{sym}", allow_404=True)
        assets[sym] = a if a is not None else {"_probe": "NOT FOUND AT ALPACA (404)"}
    snap = {
        "book": book,
        "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "base_url": PAPER_BASE,
        "spec": str(spec_path(book).relative_to(REPO)),
        "universe": names,
        "account": redact(_get(session, "/v2/account"), is_account=True),
        "account_configurations": redact(_get(session, "/v2/account/configurations")),
        "assets": assets,
        "positions": redact(_get(session, "/v2/positions")),
        "open_orders": redact(_get(session, "/v2/orders?status=open&limit=500")),
    }
    if book in OPENING_READ_BOOKS:
        snap["opening_session"] = opening_read(session, snap["positions"], book)
    return snap


def summarise(snap: dict) -> str:
    acct = snap["account"]
    lines = [f"== {snap['book']}  ({snap['fetched_at_utc']}, {snap['base_url']})",
             "account: " + "  ".join(
                 f"{k}={acct[k] if k in acct else 'ABSENT'}" for k in ACCOUNT_FIELDS),
             f"positions: {len(snap['positions'])}   open orders: {len(snap['open_orders'])}"]
    if "opening_session" in snap:
        o = snap["opening_session"]
        v = {True: "True", False: "False", None: "UNMEASURED"}[o["value"]]
        lines.append(f"opening_session: {v}   ({o['why']}; the runner's rule {o['rule']!r}: no "
                     f"position and no counted fill ever)"
                     + (f"   newest fill: {o['newest_fill']}" if o["newest_fill"] else ""))
    lines.append("symbol  " + "  ".join(ASSET_FIELDS))
    for sym, a in snap["assets"].items():
        if "_probe" in a:
            lines.append(f"{sym:<7} {a['_probe']}")
            continue
        lines.append(f"{sym:<7} " + "  ".join(
            f"{a[k] if k in a else 'ABSENT'}" for k in ASSET_FIELDS))
    return "\n".join(lines)


def _session(key_id: str, secret: str):
    import requests
    s = requests.Session()
    # Header names from Alpaca's Trading API authentication docs. A wrong name
    # fails loudly with 401/403 on the first GET; nothing is sent otherwise.
    s.headers.update({"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret})
    s.max_redirects = 0   # = quantt.broker.alpaca.refuse_redirects (not imported: that module imports this one)
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--book", choices=[*BOOK_SPECS, *OPT_IN_BOOK_SPECS, "all"], default="all",
                    help="all = " + ", ".join(BOOK_SPECS) + "; an opt-in book ("
                         + ", ".join(OPT_IN_BOOK_SPECS) + ") is read only when named")
    ap.add_argument("--check-keys", action="store_true",
                    help="print only whether each book's keys are SET; no network")
    args = ap.parse_args(argv)
    books = list(BOOK_SPECS) if args.book == "all" else [args.book]
    env = read_env_file()

    if args.check_keys:
        for b in books:
            for n in env_names(b):
                print(f"{n}: {'SET' if env.get(n) else 'NOT SET'}")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rc = 0
    for b in books:
        try:
            kid, sec = load_credentials(b, env)
        except MissingCredential as e:
            print(f"SKIPPED {b}: {e}")
            rc = 2
            continue
        snap = probe_book(b, _session(kid, sec))
        out = OUT_DIR / f"{snap['fetched_at_utc'][:10]}_{b}.json"
        out.write_text(json.dumps(snap, indent=1, sort_keys=True))
        print(summarise(snap))
        print(f"-> {out.relative_to(REPO)}\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
