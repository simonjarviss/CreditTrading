"""Alpaca corporate actions for the 17 credit CEFs, 2023-01-01 on: the ex-date drift trial's Stage 0 second source.

    python3 scripts/events/fetch_exdrift_corp_actions.py --dry-run   # the requests it would make; reads no key
    QUANTT_ENV_FILE=<env file> python3 scripts/events/fetch_exdrift_corp_actions.py   # the team lead runs this

WHY THIS EXISTS (EVENTS trial 3, approved 2026-10-27)
-----------------------------------------------------
`results/events/PREREG_EXDATE_DRIFT_2026-10-26.md` §8 asks Stage 0 for three things no tracked
panel holds for the test set (the 17 credit CEFs, 2023-01-01 to the last panel date):

* DG-X1: a SECOND dated source for every ex-date and amount. The panel is yfinance alone
  (`scripts/fetch_cef_distributions.py`), which on the fit missed 11 CRSP distributions, three
  of them large specials (`docs/REFERENCES.md`, row of 2026-10-11).
* DG-X2: a DECLARATION date for every ex-date, because the trade decides at the close of e-1
  and may only act on a distribution declared by then (`event_hold`'s `ann`).
* DG-X3: the RECORD date, to check the ex/record arithmetic of each settlement regime (§4.2).

Public routes were tried first on 2026-10-27 and gave nothing for these names:
`scripts/data/fetch_sponsor_notices.py` verifies a citation table of C4's funds only (none of
the 17), and CEFConnect answered a scripted request with a "request blocked" page. CRSP needs
the team lead's credential. So this reads Alpaca, on the cef book's paper key:

* `GET https://data.alpaca.markets/v1/corporate-actions`: cash dividends and capital-gains
  distributions (ex, record, payable and process dates; `rate`, or `long_term_rate` +
  `short_term_rate`), and splits. It has NO declaration date [V: docs, REFERENCES §12 row
  "Alpaca GET /v1/corporate-actions has no declaration or announcement date"]. Its start/end
  filter runs on the process date, which trails the ex-date, so the query runs past `end`.
* `GET https://paper-api.alpaca.markets/v2/corporate_actions/announcements`, `ca_types=Dividend`,
  `date_type=ex_date`: it carries `declaration_date`. It is DEPRECATED and takes at most 90 days
  per query [V: same row], so it is queried per symbol in windows of at most 90 days. Whether it
  still answers is [U]; each window's HTTP status is recorded, and Stage 0 reports a refusal as
  a failed gate. It is never replaced by a guess.
* `--bars-for FLAGS.csv` (the wrapper passes Stage 0's flag table): raw SIP daily bars
  (`GET data.alpaca.markets/v2/stocks/bars`, `adjustment=raw`) on exactly the (ticker, date)
  cells Stage 0 flagged `X4_no_bar`, so the team lead can rule on a fill from a second source
  (C4's precedent, 2026-10-14) without a second credentialed run. Presence only is read at
  Stage 0.

CREDENTIALS, the way `quantt/broker/alpaca_probe.py` loads them: `read_env_file` (python-dotenv,
nothing exported to the environment) on the file named by `QUANTT_ENV_FILE`, else the probe's
`config/.env`; `load_credentials("cef", env)` raises naming an unset VARIABLE, never a value.
Nothing here prints a key, a header or a request object; an HTTP error names the path, the
status and the first 200 characters of Alpaca's body. `--dry-run` never opens the env file.

READ-ONLY. Every request is a GET to one of the two hosts above; there is no order path.
The 17 names are the spec's 13 plus NAD, NEA, NVG and NZF (`exdrift_trial.NAMES`); the 27
sealed `cef_universe.csv` names are never requested. Output goes to the gitignored
`results/events/exdrift/_cache_exdrift/`.

Tests: `scripts/events/tests/test_fetch_exdrift_corp_actions.py` (a fake session; netguarded).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

CACHE = REPO / "results" / "events" / "exdrift" / "_cache_exdrift"
RAW = CACHE / "alpaca_corp_actions_raw.json"
DIVS = CACHE / "alpaca_cash_dividends.parquet"
ANN = CACHE / "alpaca_dividend_announcements.parquet"
BARS = CACHE / "alpaca_flagged_bars.parquet"
ADJ_BARS = CACHE / "alpaca_adjacent_bars.parquet"    # X4 basis check (ruling #4): bars around each flagged cell

DATA_BASE = "https://data.alpaca.markets"
PAPER_BASE = "https://paper-api.alpaca.markets"
V1_PATH = "/v1/corporate-actions"
ANN_PATH = "/v2/corporate_actions/announcements"
BARS_PATH = "/v2/stocks/bars"
BOOK = "cef"
START = dt.date(2023, 1, 1)                 # the test set's first day (prereg §5.1)
V1_TYPES = "cash_dividend,capital_gains_distribution,forward_split,reverse_split,unit_split"
V1_LIMIT = 1000                             # the reference's maximum (scripts/rv/alpaca_daily.py)
PROCESS_LAG_DAYS = 120                      # process date trails ex-date (max 47 days measured; alpaca_daily.py)
ANN_WINDOW_DAYS = 89                        # since..until inclusive stays inside the 90-day limit
MAX_PAGES = 200
RETRIES_429 = 5
PAUSE_S = 0.35                              # ~170 requests a minute for ~290 requests; Alpaca's limit is [U] (200/min is the usual figure), and a 429 is retried


class FetchError(RuntimeError):
    """A response that cannot be recorded as what it is."""


def names() -> list[str]:
    from scripts.events.exdrift_trial import NAMES
    return list(NAMES)


def plan(symbols, start: dt.date, end: dt.date) -> list[dict]:
    """Every request this run makes, as (label, base, path, params). Pure: no key, no network."""
    syms = sorted(set(symbols))
    reqs = [{"label": "v1", "base": DATA_BASE, "path": V1_PATH,
             "params": {"symbols": ",".join(syms), "types": V1_TYPES, "start": start.isoformat(),
                        "end": (end + dt.timedelta(days=PROCESS_LAG_DAYS)).isoformat(), "limit": V1_LIMIT,
                        "sort": "asc"}}]
    for s in syms:
        a = start
        while a <= end:
            b = min(a + dt.timedelta(days=ANN_WINDOW_DAYS), end)
            reqs.append({"label": "announcements", "base": PAPER_BASE, "path": ANN_PATH,
                         "params": {"ca_types": "Dividend", "since": a.isoformat(), "until": b.isoformat(),
                                    "symbol": s, "date_type": "ex_date"}})
            a = b + dt.timedelta(days=1)
    return reqs


def bar_requests(flags: pd.DataFrame) -> list[dict]:
    """Raw SIP daily bars on the flagged X4_no_bar cells, one request per date. Pure."""
    from scripts.rv.alpaca_daily import _ny        # RFC-3339 at New York time, DST-aware
    f = flags[flags["check"] == "X4_no_bar"]
    out = []
    for d, g in f.groupby("date"):
        day = dt.date.fromisoformat(str(d)[:10])
        out.append({"label": "bars", "base": DATA_BASE, "path": BARS_PATH,
                    "params": {"symbols": ",".join(sorted(set(g["ticker"]))), "timeframe": "1Day", "feed": "sip",
                               "adjustment": "raw", "start": _ny(day, 0), "end": _ny(day, 20), "limit": 1000,
                               "sort": "asc"}})
    return out


def adjacent_bar_requests(flags: pd.DataFrame) -> list[dict]:
    """Raw SIP daily bars for each X4_no_bar ticker over its cell +- 7 calendar days (so the sessions
    e-1 and e+1 are inside), one request per cell. Pure."""
    from scripts.rv.alpaca_daily import _ny
    f = flags[flags["check"] == "X4_no_bar"]
    out = []
    for t, d in zip(f["ticker"], f["date"]):
        day = dt.date.fromisoformat(str(d)[:10])
        out.append({"label": "adjacent_bars", "base": DATA_BASE, "path": BARS_PATH,
                    "params": {"symbols": t, "timeframe": "1Day", "feed": "sip", "adjustment": "raw",
                               "start": _ny(day - dt.timedelta(days=7), 0), "end": _ny(day + dt.timedelta(days=7), 20),
                               "limit": 1000, "sort": "asc"}})
    return out


def run_adjacent(session, flags: pd.DataFrame, *, sleep=time.sleep) -> pd.DataFrame:
    pages = []
    for r in adjacent_bar_requests(flags):
        sleep(PAUSE_S)
        st, body = get(session, r["base"], r["path"], r["params"], sleep=sleep)
        if st != 200:
            raise FetchError(f"GET {r['path']} -> HTTP {st}: {body}")
        pages.append(body.get("bars") or {})
    b = parse_bars(pages).drop_duplicates(["ticker", "date"])
    return b.assign(fetched_utc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


def get(session, base: str, path: str, params: dict, *, sleep=time.sleep) -> tuple[int, object]:
    """One GET. Returns (status, decoded JSON or the first 200 characters of the body).

    429 is retried RETRIES_429 times with a growing pause (3s, 6s, ...); any other status is returned as it is,
    for the caller to record. The request (which holds the key headers) is never echoed."""
    if base not in (DATA_BASE, PAPER_BASE) or not path.startswith("/"):
        raise ValueError(f"refusing {base}{path}: only Alpaca's data and paper hosts are read")
    for k in range(RETRIES_429 + 1):
        # never follow a redirect: the session carries the key headers (quantt.broker.alpaca.refuse_redirects)
        r = session.get(base + path, params=params, timeout=30, allow_redirects=False)
        if r.status_code != 429 or k == RETRIES_429:
            break
        sleep(3.0 * (k + 1))
    if r.status_code == 200:
        try:
            return 200, r.json()
        except ValueError as e:
            raise FetchError(f"GET {path}: HTTP 200 but the body is not JSON: {r.text[:200]!r}") from e
    return r.status_code, r.text[:200]


def fetch_v1(session, req: dict, *, sleep=time.sleep) -> list[dict]:
    """Every page of the v1 query. A non-200 raises: without it there is no second source at all."""
    pages, token = [], None
    for _ in range(MAX_PAGES):
        p = dict(req["params"])
        if token:
            p["page_token"] = token
        st, body = get(session, req["base"], req["path"], p, sleep=sleep)
        if st != 200:
            raise FetchError(f"GET {req['path']} -> HTTP {st}: {body}")
        if not isinstance(body, dict) or "corporate_actions" not in body or "next_page_token" not in body:
            raise FetchError(f"GET {req['path']}: the response lacks corporate_actions or next_page_token")
        pages.append(body["corporate_actions"] or {})
        token = body["next_page_token"]
        if not token:
            return pages
    raise FetchError(f"GET {req['path']}: more than {MAX_PAGES} pages")


def parse_v1(pages: list[dict], symbols) -> pd.DataFrame:
    """Cash dividends and capital-gains distributions -> one row per record (not summed). Pure.

    `amount` is a cash dividend's `rate`, or a capital-gains record's long_term_rate +
    short_term_rate (`quantt/broker/alpaca.py` `distributions` reads it the same way). A record
    with no ex-date or no amount raises; a record for a symbol not asked for raises."""
    want = set(symbols)
    rows = []
    for page in pages:
        for typ, items in page.items():
            for x in items or []:
                sym = x.get("symbol") or x.get("old_symbol") or x.get("new_symbol")
                if sym not in want:
                    raise FetchError(f"{typ}: a record for {sym!r}, which was not requested")
                if typ == "cash_dividends":
                    amt = x.get("rate")
                elif typ == "capital_gains_distributions":
                    parts = [x.get("long_term_rate"), x.get("short_term_rate")]
                    if all(v is None for v in parts):
                        raise FetchError(f"capital_gains_distribution with no rate: {x}")
                    amt = sum(float(v) for v in parts if v is not None)
                else:
                    rows.append(dict(kind=typ, ticker=sym, ex_date=x.get("ex_date") or x.get("effective_date"),
                                     record_date=x.get("record_date"), payable_date=x.get("payable_date"),
                                     process_date=x.get("process_date"), amount=None,
                                     special=None, sub_type=None, id=x.get("id")))
                    continue
                if not x.get("ex_date") or amt is None:
                    raise FetchError(f"{typ} record without an ex-date or an amount: {x}")
                rows.append(dict(kind=typ, ticker=sym, ex_date=x["ex_date"], record_date=x.get("record_date"),
                                 payable_date=x.get("payable_date"), process_date=x.get("process_date"),
                                 amount=float(amt), special=x.get("special"), sub_type=x.get("sub_type"),
                                 id=x.get("id")))
    cols = ["kind", "ticker", "ex_date", "record_date", "payable_date", "process_date", "amount", "special",
            "sub_type", "id"]
    df = pd.DataFrame(rows, columns=cols)
    for c in ("ex_date", "record_date", "payable_date", "process_date"):
        df[c] = pd.to_datetime(df[c])
    return df


def parse_announcements(windows: list[dict]) -> pd.DataFrame:
    """Each window's announcements -> one row per announcement, with that window's status. Pure.

    A window that did not answer 200 is kept as one row with `status` and no dates, so a refusal
    is recorded, not dropped."""
    rows = []
    for w in windows:
        if w["status"] != 200:
            rows.append(dict(window_symbol=w["symbol"], since=w["since"], until=w["until"], status=w["status"],
                             ticker=None, ca_type=None, ca_sub_type=None, declaration_date=None, ex_date=None,
                             record_date=None, payable_date=None, cash=None, id=None))
            continue
        if not isinstance(w["body"], list):
            raise FetchError(f"announcements {w['symbol']} {w['since']}..{w['until']}: the body is not a list")
        for x in w["body"]:
            rows.append(dict(window_symbol=w["symbol"], since=w["since"], until=w["until"], status=200,
                             ticker=x.get("initiating_symbol") or x.get("target_symbol"),
                             ca_type=x.get("ca_type"), ca_sub_type=x.get("ca_sub_type"),
                             declaration_date=x.get("declaration_date"), ex_date=x.get("ex_date"),
                             record_date=x.get("record_date"), payable_date=x.get("payable_date"),
                             cash=None if x.get("cash") in (None, "") else float(x["cash"]), id=x.get("id")))
    df = pd.DataFrame(rows, columns=["window_symbol", "since", "until", "status", "ticker", "ca_type", "ca_sub_type",
                                     "declaration_date", "ex_date", "record_date", "payable_date", "cash", "id"])
    for c in ("declaration_date", "ex_date", "record_date", "payable_date"):
        df[c] = pd.to_datetime(df[c])
    return df


def parse_bars(pages: list[dict]) -> pd.DataFrame:
    """Bar pages -> (ticker, date, close, volume). Pure. The trial reads presence only."""
    rows = []
    for page in pages:
        for sym, items in (page or {}).items():
            for b in items or []:
                rows.append(dict(ticker=sym, date=pd.Timestamp(b["t"]).tz_convert("America/New_York").tz_localize(None)
                                 .normalize(), close=float(b["c"]), volume=float(b["v"])))
    return pd.DataFrame(rows, columns=["ticker", "date", "close", "volume"])


def run(session, symbols, start: dt.date, end: dt.date, flags: pd.DataFrame | None = None,
        *, sleep=time.sleep, now=None) -> dict:
    """Make every request of `plan` (and of `bar_requests`), and return what came back."""
    t = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reqs = plan(symbols, start, end)
    out = {"fetched_utc": t, "start": start.isoformat(), "end": end.isoformat(), "symbols": sorted(set(symbols)),
           "v1": None, "announcements": [], "bars": []}
    out["v1"] = fetch_v1(session, reqs[0], sleep=sleep)
    for r in reqs[1:]:
        sleep(PAUSE_S)
        st, body = get(session, r["base"], r["path"], r["params"], sleep=sleep)
        out["announcements"].append({"symbol": r["params"]["symbol"], "since": r["params"]["since"],
                                     "until": r["params"]["until"], "status": st, "body": body})
    if flags is not None:
        for r in bar_requests(flags):
            pages, token = [], None
            for _ in range(MAX_PAGES):
                p = dict(r["params"])
                if token:
                    p["page_token"] = token
                st, body = get(session, r["base"], r["path"], p, sleep=sleep)
                if st != 200:
                    raise FetchError(f"GET {r['path']} -> HTTP {st}: {body}")
                pages.append(body.get("bars") or {})
                token = body.get("next_page_token")
                if not token:
                    break
            out["bars"].append({"params": r["params"], "pages": pages})
    return out


def write(raw: dict, symbols) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps(raw, default=str))
    d = parse_v1(raw["v1"], symbols).assign(fetched_utc=raw["fetched_utc"])
    a = parse_announcements(raw["announcements"]).assign(fetched_utc=raw["fetched_utc"])
    b = parse_bars([p for x in raw["bars"] for p in x["pages"]]).assign(fetched_utc=raw["fetched_utc"])
    d.to_parquet(DIVS, index=False)
    a.to_parquet(ANN, index=False)
    b.to_parquet(BARS, index=False)
    st = a.drop_duplicates(["window_symbol", "since"])["status"].value_counts().to_dict()
    return {"v1_records": int(len(d)), "announcement_rows": int((a["status"] == 200).sum() if len(a) else 0),
            "announcement_window_status": {int(k): int(v) for k, v in st.items()}, "bars": int(len(b))}


def session_from_env(env_file: Path):
    """The cef book's read-only session, keys loaded exactly as alpaca_probe loads them."""
    from quantt.broker.alpaca_probe import _session, load_credentials, read_env_file
    kid, sec = load_credentials(BOOK, read_env_file(env_file))
    return _session(kid, sec)


def env_path() -> Path:
    from quantt.broker.alpaca_probe import ENV_FILE
    p = os.environ.get("QUANTT_ENV_FILE", "")
    return Path(p) if p else ENV_FILE


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print the requests; read no key; no network")
    ap.add_argument("--end", type=dt.date.fromisoformat, default=None,
                    help="last ex-date asked for (default: today + 60 days, for declared future ex-dates)")
    ap.add_argument("--bars-for", type=Path, default=None, help="Stage 0's flag table: fetch bars on X4_no_bar cells")
    ap.add_argument("--adjacent-bars-for", type=Path, default=None,
                    help="only fetch raw SIP bars around each X4_no_bar cell (e-1 and e+1, ruling #4) into the cache")
    a = ap.parse_args(argv)
    syms = names()
    if a.adjacent_bars_for:
        fl = pd.read_csv(a.adjacent_bars_for, dtype=str)
        if a.dry_run:
            for r in adjacent_bar_requests(fl):
                print(f"GET {r['base']}{r['path']} {r['params']}")
            return 0
        b = run_adjacent(session_from_env(env_path()), fl)
        CACHE.mkdir(parents=True, exist_ok=True)
        b.to_parquet(ADJ_BARS, index=False)
        print(f"{len(b)} raw SIP bars around {fl[fl.check == 'X4_no_bar'].shape[0]} cells -> {ADJ_BARS.relative_to(REPO)}")
        return 0
    end = a.end or (dt.date.today() + dt.timedelta(days=60))
    flags = pd.read_csv(a.bars_for, dtype=str) if a.bars_for else None
    reqs = plan(syms, START, end) + (bar_requests(flags) if flags is not None else [])
    if a.dry_run:
        for r in reqs:
            print(f"GET {r['base']}{r['path']} {r['params']}")
        print(f"{len(reqs)} requests for {len(syms)} symbols; no key read, nothing sent")
        return 0
    raw = run(session_from_env(env_path()), syms, START, end, flags)
    s = write(raw, syms)
    print(f"fetched {raw['fetched_utc']}: v1 {s['v1_records']} records; announcements {s['announcement_rows']} rows, "
          f"window status {s['announcement_window_status']}; flagged bars {s['bars']} -> "
          f"{CACHE.relative_to(REPO)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
