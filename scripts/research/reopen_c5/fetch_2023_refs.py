"""Fetch the NBBO reference quotes C5's opening-cost re-open lacks: the 14-session stride over
2023-01-03 -> 2026-07-20. Read-only market data. Zero trials.

    # from the research-reopen-c5 worktree; drop --dry-run, and prefix
    # QUANTT_ENV_FILE=../../../config/.env, for the real fetch (the team lead runs that)
    python3 -m scripts.research.reopen_c5.fetch_2023_refs --dry-run \
        --cache results/research/reopen_c5/_cache_reopen_c5_2023 \
        --calendar ../research-exec-capacity/results/cef/exec_capacity/_cache_exec/calendar.parquet \
        --holdout-prints ../trial-c5/results/cef/c5/_cache_c5_holdout

WHY THIS EXISTS
---------------
results/research/REOPEN_C5_OPEN_COST_2026-10-28.md §2: `s_open` was re-measured only on the EXEC note's
60-session window of 2026, because the reference quotes for 2023-01-03 -> 2026-07-20 were never
fetched. The holdout gain it is set against spans 2023-26. This driver fetches exactly those quotes, so
that `reopen_c5_open_cost.py --stride-cache` can read the full period. The agent that wrote it may not
load the key file (CLAUDE.md order-path rule 5), so the fetch itself is the team lead's to run.

WHAT IT FETCHES, AND NOTHING ELSE
---------------------------------
For each session of the stride, it calls `exec_capacity_open_cross.fetch_refs` unchanged. That gives
the last valid consolidated NBBO before each of the six reference points `ref_points` defines (h0, h1
and h5, open and close), for the 13 spec names. Each reference point is one multi-symbol
GET /v2/stocks/quotes (more if it pages; 10,000 quotes per page), plus one wider look-back for any
name with no quote in the near window. The close-side points move with an early close, which is read
from the cached exec calendar (`close` column), never assumed to be 16:00.
  * The stride is every `FIT_SAMPLE_EVERY`-th session from the window's first session. That is the fit
    sample's own design (`exec_capacity_open_cross.fetch`, `fit[::FIT_SAMPLE_EVERY]`), so the two
    samples are alike.
  * The primary's tape is NOT fetched, so the re-open scores round-lot crosses from the auction prices
    alone (`reopen_c5_open_cost.independent_round_pairs`). Those prices are C5's holdout freeze,
    verified against `results/cef/c5/c5_holdout_inputs_2026-10-15.json` and copied, for the stride days
    only, into the cache as `auctions_stride.parquet`. That is a local read, and nothing about it is
    fetched.

GET-ONLY
--------
The client is built ONLY by `AlpacaClient.from_environment("cef")`, which needs `QUANTT_ENV_FILE`. The
driver refuses before any work if that variable is unset, and never names a default file. The
AlpacaClient itself has an order method (`submit_order`), so the driver never hands it on. It wraps it
in `QuotesOnly`, whose one method forwards GETs to the market-data host on /v2/stocks/quotes and
raises on any other host or path. `assert_get_only` checks, before the first request, that the object
passed to `fetch_refs` exposes no order-like attribute.

RESUMABLE
---------
A session whose file holds all six reference keys is skipped. A file missing some keys is completed
with `fetch_refs(..., have=<the file>)`, which fetches only the missing keys. Files are written
atomically (a temporary file, then a rename), so an interrupted run leaves no half-written session.

NO SILENT FALLBACKS
-------------------
A calendar that does not cover the window, a hash mismatch on the holdout prints, or an unset
`QUANTT_ENV_FILE` raises, naming it. A name with no quote at a reference point is stored as None
(exactly as the EXEC cache stores it) and is counted by the analysis, never filled.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research.reopen_c5.reopen_c5_open_cost import (  # noqa: E402
    STRIDE_ERA, STRIDE_FIRST, STRIDE_LAST, ReopenError, shown, stride_dates)

HOLDOUT_RECORD = REPO / "results" / "cef" / "c5" / "c5_holdout_inputs_2026-10-15.json"
PRINT_FILES = {"open": "w4/alpaca_opening_prints_holdout_2023_2026.parquet",
               "close": "w4/alpaca_closing_prints_holdout_2023_2026.parquet"}
ORDERISH = ("submit", "order", "cancel", "replace", "post", "delete", "patch", "put")
QUOTES_PATH = "/v2/stocks/quotes"


class QuotesOnly:
    """A GET-only view of an Alpaca client: the one call `fetch_refs` makes, and nothing else.

    `fetch_refs` -> `_quotes_before` -> `_window` -> `_paged` calls `c._get(DATA_BASE, path, params)`
    with path /v2/stocks/quotes. This object forwards exactly that and raises on anything else. The
    wrapped client is held under a name-mangled attribute and never returned."""

    def __init__(self, client, data_base: str):
        self.__client = client
        self._data_base = data_base
        self.requests = 0

    def _get(self, base: str, path: str, params: dict | None = None):
        if base != self._data_base or path != QUOTES_PATH:
            raise ReopenError(f"QuotesOnly refuses GET {base}{path}: only {self._data_base}{QUOTES_PATH}")
        self.requests += 1
        return self.__client._get(base, path, params)


def assert_get_only(obj) -> None:
    """Raise if `obj` exposes any attribute whose name looks like an order or write path."""
    bad = [n for n in dir(obj) if not n.startswith("__") and any(w in n.lower() for w in ORDERISH)]
    if bad:
        raise ReopenError(f"{type(obj).__name__} exposes order-like attributes {bad}; refusing to fetch with it")


def require_env() -> None:
    """Refuse, before any work, when QUANTT_ENV_FILE is unset. Reads only whether it is set."""
    if not os.environ.get("QUANTT_ENV_FILE"):
        raise ReopenError("QUANTT_ENV_FILE is not set: it must name the file holding the cef book's Alpaca "
                          "keys. This fetch is the team lead's to run; nothing was fetched.")


def make_client() -> QuotesOnly:
    """The only constructor: AlpacaClient.from_environment("cef"), wrapped GET-only. Refuses first,
    with a clear message, if QUANTT_ENV_FILE is unset; this module never names a key file."""
    require_env()
    from quantt.broker.alpaca import DATA_BASE, AlpacaClient
    c = QuotesOnly(AlpacaClient.from_environment("cef"), DATA_BASE)
    assert_get_only(c)
    return c


def ref_keys() -> list[str]:
    """The six reference keys fetch_refs writes, read from ref_points (never listed by hand)."""
    from scripts.cef import exec_capacity_open_cross as X
    return sorted(X.ref_points(dt.date(2023, 1, 3), "16:00"))


def sessions(calendar: pd.DataFrame) -> list[tuple[str, str]]:
    """[(date, close hh:mm)] of the stride, from the cached calendar (early closes included)."""
    from scripts.cef import exec_capacity_open_cross as X
    for k in ("date", "close"):
        if k not in calendar.columns:
            raise ReopenError(f"calendar lacks a {k!r} column")
    days = stride_dates(list(calendar.date), STRIDE_FIRST, STRIDE_LAST, X.FIT_SAMPLE_EVERY)
    close = dict(zip(calendar.date, calendar.close))
    return [(d, close[d]) for d in days]


def holdout_prints(root: Path, dates: list[str]) -> pd.DataFrame:
    """C5's frozen holdout auction prints for `dates`, in exec_capacity_open_cross's row shape (no
    size: the holdout fetch took prices only). Each file is verified against the holdout record first."""
    rec = json.loads(HOLDOUT_RECORD.read_text())
    out = []
    for side, rel in PRINT_FILES.items():
        p = root / rel
        if not p.exists():
            raise ReopenError(f"{rel} is missing under {shown(root)}")
        want = rec.get("files", {}).get(rel)
        if want is None:
            raise ReopenError(f"{HOLDOUT_RECORD.name} records no hash for {rel}")
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if h != want:
            raise ReopenError(f"{rel} does not match its recorded SHA-256")
        a = pd.read_parquet(p)
        a = a.assign(date=a.date.dt.strftime("%Y-%m-%d"))
        a = a[a.date.isin(dates)]
        out.append(pd.DataFrame(dict(date=a.date, ticker=a.ticker, side=side, x=a.exchange, c=a.condition,
                                     p=a.price, t=a.t)))
    return pd.concat(out, ignore_index=True)


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def fetch_all(client, cache: Path, sess: list[tuple[str, str]], syms: list[str]) -> dict:
    """Fetch every missing reference for every session into cache/days/<date>.json. Resumable."""
    from scripts.cef import exec_capacity_open_cross as X
    assert_get_only(client)
    keys = ref_keys()
    (cache / "days").mkdir(parents=True, exist_ok=True)
    log = dict(skipped=0, completed=0, new=0)
    for i, (ds, close) in enumerate(sess):
        f = cache / "days" / f"{ds}.json"
        rec = json.loads(f.read_text()) if f.exists() else {}
        if rec and (rec.get("date") != ds or rec.get("close") != close or rec.get("era") != STRIDE_ERA):
            raise ReopenError(f"{f.name}: cached as {rec.get('date')}/{rec.get('close')}/{rec.get('era')}, "
                              f"expected {ds}/{close}/{STRIDE_ERA}")
        if rec and all(k in rec for k in keys):
            log["skipped"] += 1
            continue
        had = bool(rec)
        add = X.fetch_refs(client, dt.date.fromisoformat(ds), close, syms, rec)
        rec = {**rec, **add, "date": ds, "close": close, "era": STRIDE_ERA}
        _write_atomic(f, json.dumps(rec))
        log["completed" if had else "new"] += 1
        if i % 10 == 0:
            print(f"  {i + 1}/{len(sess)} {ds} (close {close})", flush=True)
    return log


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, required=True, help="the cache this writes (and resumes)")
    ap.add_argument("--calendar", type=Path, required=True, help="the cached exec calendar.parquet")
    ap.add_argument("--holdout-prints", type=Path, required=True, help="C5's _cache_c5_holdout directory")
    ap.add_argument("--dry-run", action="store_true", help="list the sessions and requests; no client")
    a = ap.parse_args(argv)
    from scripts.cef.spec import UNIVERSE
    syms = sorted(UNIVERSE)
    if not a.dry_run:
        require_env()                       # fail fast, before any local work
    from scripts.cef import exec_capacity_open_cross as X
    if not a.calendar.exists():
        raise ReopenError(f"{a.calendar} is missing")
    cal = pd.read_parquet(a.calendar)
    sess = sessions(cal)
    keys = ref_keys()
    cached = sum(1 for d, _ in sess if (a.cache / "days" / f"{d}.json").exists())
    early = [(d, c) for d, c in sess if c != "16:00"]
    floor = len(sess) * len(keys)
    print(f"stride: every {X.FIT_SAMPLE_EVERY}th session of {STRIDE_FIRST}..{STRIDE_LAST}: {len(sess)} sessions, "
          f"{sess[0][0]}..{sess[-1][0]}; early closes on the stride: {early if early else 'none'}; "
          f"{len(syms)} names; {len(keys)} reference points per session")
    print(f"requests: at least {floor} GET /v2/stocks/quotes ({len(keys)} per session), more where a window "
          f"pages or a name needs the wider look-back; {cached} session file(s) already in {shown(a.cache)}")
    if a.dry_run:
        for d, c in sess:
            print(f"  {d} close {c}{'  (cached)' if (a.cache / 'days' / f'{d}.json').exists() else ''}")
        print("dry run: no client was built and nothing was fetched or written")
        return 0
    prints = holdout_prints(a.holdout_prints, [d for d, _ in sess])
    client = make_client()
    a.cache.mkdir(parents=True, exist_ok=True)
    cal.to_parquet(a.cache / "calendar.parquet", index=False)
    prints.to_parquet(a.cache / "auctions_stride.parquet", index=False)
    started = dt.datetime.now(dt.timezone.utc)
    log = fetch_all(client, a.cache, sess, syms)
    log.update(requests=client.requests, sessions=len(sess), started_utc=started.isoformat(),
               finished_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    _write_atomic(a.cache / "fetch_log.json", json.dumps(log, indent=1))
    print(f"done: {log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
