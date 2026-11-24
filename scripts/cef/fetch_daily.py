"""Daily refresh of the credit CEF price and NAV panels.

Run after the US close. Appends only new dates, so it is safe to run repeatedly.

    python3 scripts/cef/fetch_daily.py                       # plain refresh
    python3 scripts/cef/fetch_daily.py --require-asof 2026-09-08 \
            --nav-fallback cefconnect --book ops/books/cef_discount_book.json

--require-asof D   exit 4 unless every deployed name has BOTH a close and a NAV
                   dated D after the refresh, naming the gaps. A row dated D
                   with no finite close is not a close (EMPTY ROWS below).
                   The session uses this so it trades on today's pair or not
                   at all. It checks the DATE only: Yahoo serves rows dated D
                   that carry D-1's NAV
                   (results/cef/LIVE_NAV_QUALITY_2026-10-12.md §5). The VALUE is
                   the session's stale-NAV gate's job (quantt/session/nav_gate.py),
                   which writes its CEFConnect replacements through
                   `merge_nav_fills` / `log_nav_fills` below.
--nav-fallback     for a deployed name whose NAV for D is not on yfinance, take
                   CEFConnect's dated row for D. Every such fill is printed and
                   appended to data/cef/nav_fallback_log.csv; the two sources
                   agree to the cent on every comparison made 2026-09-08.

A bar dated TODAY is dropped if the run starts before 16:05 local. yfinance
serves the partial session as a 'Close' (NZF 11.88 on 78k shares at 10:27 on
2026-09-08); written as a close it would put an intraday print in the panel
that the drop_duplicates(keep="last") below would overwrite only at the next
after-hours run.

NAV is the load-bearing input here -- the entire strategy is the gap between price
and NAV, so a stale or missing NAV silently turns the signal into noise. The
freshness of every fund's NAV is therefore checked and reported, and any fund
whose NAV has not updated in three business days is flagged so the sleeve can
drop it rather than trade on a stale number.

LOCKING (2026-09-29). Two things now run this script against the same two
panels: the trading session (`quantt/session/run.py`, step 1) and the nightly
data collector (`quantt/collect`, every 30 minutes). Each run READS both panels,
spends minutes fetching, then REPLACES them. `atomic_write` stops a reader
seeing half a file, but not two writers interleaving: run A reads, run B reads,
B writes its new rows, A writes its own copy -- and B's rows are gone, with no
error anywhere. So the whole read-modify-write runs under an exclusive
`fcntl.flock` on `data/cef/.fetch.lock`. A second run waits for it, at most
LOCK_WAIT_S, then exits 3 naming the lock rather than waiting forever: the
session has a cls cutoff and the collector has its next 30-minute slot, and
neither may be blocked indefinitely by a hung fetch. Exit 3 is a refusal to
refresh, never a partial write.

EMPTY ROWS (fix approved by the team lead 2026-10-28). When Yahoo's chart
response carries a dividend (or split) for a date with no bar, yfinance 0.2.66
emits a row for that date with every price NaN and volume 0: `safe_merge_dfs`
appends a "row of NaNs" for an out-of-range event (yfinance/utils.py:761-767),
`keepna=False` keeps any row whose only datum is that event
(scrapers/history.py:502-506), and Volume is then filled with 0
(scrapers/history.py:492). This script wrote such rows unchecked, and because
each run's row for a date replaces the last one, an empty row overwrote a good
bar. Measured 2026-10-28, read-only, on the laptop's cef_prices.parquet (to
2026-10-15) against its 2026-09-28 backup (cef_prices.parquet.pre-20261015.bak):
15 good 2026-09-15 bars had become empty rows -- BIT, HYT, JFR, MHD and MQY of
the live 13 among them -- and the panel held 65 empty-close rows against the
backup's 49, every one with volume 0. Bars four weeks old were emptied, so this
is not only a partial today. `--require-asof` counted such a row as the as-of
close.

Now (`merge_price_bars`): a fetched row with no close is never merged. It
cannot replace a bar that has a close, it is not written for a date the panel
lacks, and each one is printed as `NO CLOSE <ticker> <date> <why>`. A fetched
bar WITH a close does replace an empty panel row (the repair), printed as
`REPAIRED`; never the other way round. "No close" means the close is missing or
not finite (`has_close`), never volume 0: the panel holds 20 real zero-volume
days that carry a close (FCT 2026-08-10, 9.67), and an empty row's 0 is
yfinance's fill, not a measurement. Nothing is filled or invented; a name whose
only row for D is empty has no close for D and `--require-asof` refuses it.
These lines go to stdout, the record both callers already keep (the session and
the collector each store the last 40 lines), beside the ERR and CEFConnect lines.
With no empty rows the panel bytes are exactly what the old merge wrote
(scripts/cef/tests/test_fetch_daily_empty_rows.py).

EMPTY NAV ROWS (the second half of the same fix, approved by the team lead
2026-10-28; the reviewers of the price half found the NAV side unguarded). The
NAV is fetched by the same `history()` call on X<TK>X, and three places took
its rows unchecked: the NAV merge (an empty NAV would replace a good one, as an
empty bar did), the stale check (a fund was dated by its last fetched ROW, so an
empty row dated today would make a weeks-old NAV look fresh) and the
`--require-asof` NAV check (an empty row dated D counted as D's NAV, so the
CEFConnect fallback was never asked and the pair passed). Measured 2026-10-28,
read-only: the
laptop's cef_nav.parquet (to 2026-10-14) and its 2026-09-28 backup hold no NAV
that is not finite. Whether Yahoo ever attaches an event to a NAV symbol, which
is what makes yfinance emit the row, is not established [U]; this half is
ahead of an incident on the NAV panel, not behind one.

Now the price rules hold for the NAV exactly (`has_nav`, `merge_nav_rows`): a
fetched NAV that is missing or not finite is never merged and never replaces a
NAV (`NO NAV <ticker> <date> <why>`); a fetched NAV repairs an empty NAV row
(`NAV REPAIRED`); the stale check dates a fund by its last fetched row WITH a
NAV, and a fund whose fetched rows carry none is listed stale; and an empty row
dated D is not D's NAV, so `--require-asof` sends the name to the CEFConnect
fallback when it is asked for, as a missing row does, and otherwise refuses it.
A CEFConnect NAV that is not finite is not written either. With no empty rows
the panel bytes and the stale lines are exactly what they were (same test
file).

FOLLOW-UPS (independent review of the NAV half, 2026-10-28). (1) A usable NAV
is finite AND positive (`has_nav`), the session's own test: gate 5
(`quantt/session/run.py` `last_navs`), the stale-NAV gate (`panel_rows`) and its
CEFConnect reader (`read_cc`) all refuse a NAV of 0 or below. Before, a NAV of
0 dated D passed `--require-asof`, never went to the fallback and was written,
and gate 5 then refused the whole session; now it is an empty row like NaN.
(2) The stale age is counted to the ET date of this run (`today` below), not
the machine's: the VM runs in UTC, where from 20:00 ET (19:00 in winter) the
machine's date is already tomorrow and every fund read one business day older.
(3) A fund whose NAV fetch raised, or came back with no rows, was never put
through the stale check, and the closing line still said "all N NAV series
fresh". Such funds are now listed as UNCHECKED, by name and why, and are not
counted as fresh.

DATA BOOKS (C4 deployment plan step 3, DARK; team lead's fast-track 2026-10-28).
`--data-book` names whose panels to refresh; the book's directory, funds, NAV
symbols, lock and CEFConnect use come from its config (`resolve_data_book`,
`scripts/cef/data_books.py`).

  * none, or `cef`: THE CORE, exactly as at 29e5dc0 -- data/cef/, the price
    panel's own tickers, X<TK>X, the core lock, CEFConnect when asked for, the
    same lines and exit codes. Resolved at call time from this module's
    constants (PX_PATH, NAV_PATH, LOCK_PATH, FALLBACK_LOG), so everything that
    patches or imports them (the session's stale-NAV gate, the tests) sees no
    change. Proved byte for byte against 29e5dc0's file on fixtures
    (scripts/cef/tests/test_fetch_daily_books.py).
  * `c4`: data/cef_c4/ under its own lock data/cef_c4/.fetch.lock, so the
    core's refresh never waits on a 74-name fetch, nor the other way round. The
    74 frozen funds; each fund's NAV from the committed NAV-symbol map, the
    symbol the families panel the trial ran on was built from; every empty-row
    guard above unchanged. CEFConnect is DISABLED: `--nav-fallback cefconnect`
    raises `CefConnectDisabled` before the lock is taken or a panel is read
    (exit 2 from the command line). A panel holding a fund outside the 74, or
    a fund under another family, raises: a mis-seeded panel is refused, never
    fetched into. With `--book`, every deployed name must be one of the 74.
    THE SPIKE GUARD (plan row 3, `guard_closes`): after the write, the merged
    panel is scanned by `data_guards.guard_closes` over the fetched window
    (no split multipliers: yfinance's close is already split-adjusted; no
    rulings file yet). A split-like spike-and-revert bar there -- IGR's
    2026-07-29..08-11 shape, which cost the holdout -10.87% -- is printed as
    `SPIKE-REVERT` and the run exits 6. The panel is still written whole, as
    for exit 4: the fetch records what Yahoo served, and the exit code is the
    verdict a C4 session must refuse on. AN UNRULED SPIKE OUTRANKS AN INCOMPLETE
    PAIR: with both, the run exits 6, not 4, and prints both lines (release-check
    of 8b14298, 2026-11-02). Until then exit 4 outranked 6, and C4's book sets
    `data.missing_nav = "hold"`, under which gate 5 treats exit 4 at the final
    check as expected (quantt/session/gate.py missing_nav_hold): on any day one
    C4 NAV was late, the session decided and sent on a panel still holding the
    unruled bar, and nothing in the runner reads the SPIKE-REVERT line. Exit 6 is
    refused at every check. A caller still retries: a refused session is not a
    FAIL, and the next slot re-runs the refresh; the collector reads an exit 6
    whose output names INCOMPLETE_TAG as an unfinished step, not a done one. The
    core runs no spike guard, so its exits are what they always were.
    THE PRICE BASIS (2026-11-04; team lead 2026-11-03, "Hold C4 one day, fix IGR"):
    before anything is merged, each split ruled in data_books.C4_FETCH_SPLIT_RULINGS
    has its pre-ex fetched rows that Yahoo split-adjusted put back on the NAV's
    (unadjusted) basis, judged row by row against the NAV on every fetch; a split
    Yahoo declares with no ruling, a row the NAV cannot place, or a fetched close or
    NAV that steps against the stored value by a split-like ratio refuses the run,
    exit 7 (`BASIS-STEP`), and NOTHING is written (data_guards.py, THE LIVE FETCH'S
    PRICE BASIS). The core carries no rulings: none of this runs for it.
"""
from __future__ import annotations

import argparse
import fcntl
import os
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:            # run as a script, not -m
    sys.path.insert(0, str(REPO))
from ops.common import atomic_write      # noqa: E402
# Standard library only, no side effects at import (its docstring): the core
# path reads nothing from it but the name of an error it never raises.
from scripts.cef import data_books       # noqa: E402
from scripts.cef.data_books import CefConnectDisabled, DataBookError  # noqa: E402,F401
OUT = REPO / "data" / "cef"
PX_PATH = OUT / "cef_prices.parquet"
NAV_PATH = OUT / "cef_nav.parquet"
STALE_BD = 3
ET = ZoneInfo("America/New_York")


def before_close(now: datetime) -> bool:
    """True before 16:05 ET, when a bar dated today is still a partial session.

    ET, not the machine's zone (review 2026-09-29): prod will move to a cloud VM
    that may run in UTC, where 12:30 ET is 16:30 local and the old local-clock
    test would have written a morning's partial bar as that day's close."""
    t = now.astimezone(ET)
    return t.hour < 16 or (t.hour == 16 and t.minute < 5)
FALLBACK_LOG = OUT / "nav_fallback_log.csv"
CC_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
LOCK_PATH = OUT / ".fetch.lock"
# Bounded wait for the panel lock (module docstring, LOCKING). Ten minutes is
# longer than a healthy refresh and shorter than the collector's 30-minute slot.
LOCK_WAIT_S = 600.0
LOCK_POLL_S = 1.0
EXIT_LOCKED = 3
# A data book whose CEFConnect use is disabled was asked for the fallback
# (DATA BOOKS). The same code argparse gives a usage error: the command, not the
# data, is what is wrong. Never returned on the core path.
EXIT_REFUSED = 2
# C4 only (DATA BOOKS, THE SPIKE GUARD): the panel was written, and a split-like
# spike-and-revert bar in the fetched window has no ruling.
EXIT_SPIKE = 6
# The INCOMPLETE line's prefix. quantt/collect reads it from an exit 6's output to
# tell "spike, pair complete" (its step done) from "spike, pair incomplete" (not
# done, retried), since exit 6 now outranks exit 4 (THE SPIKE GUARD, above).
INCOMPLETE_TAG = "INCOMPLETE for"
# C4 only (DATA BOOKS, THE PRICE BASIS): a fetched close or NAV that could not be put on
# the stored panel's share basis. NOTHING is written: an unruled split Yahoo declares in
# the fetched window, a ruled split's row the NAV cannot place, or a split-like step
# between a fetched value and the stored one (data_guards.py, THE LIVE FETCH'S PRICE
# BASIS). Gate 5 refuses any exit but 0 (and 4 under the missing-NAV hold); the
# collector fails the step.
EXIT_BASIS = 7
BASIS_TAG = "BASIS-STEP"


class DataBook:
    """Where one book's price and NAV panels live and how they are fetched.

    `tickers`, `families` and `nav_symbols` None is the core's rule, unchanged
    since before data books existed: the price panel's own tickers, the
    panel's own `grp`, and the NAV symbol X<TK>X. `fallback_log` is where a
    CEFConnect fill is logged (None: no fill is possible).

    A plain class, not a dataclass: test_fetch_daily_clock.py loads this file
    without registering it in sys.modules, and `dataclass` looks the module up
    there."""
    __slots__ = ("name", "px_path", "nav_path", "lock_path", "fallback_log", "tickers",
                 "families", "nav_symbols", "cefconnect", "spike_guard", "split_rulings")

    def __init__(self, name, px_path, nav_path, lock_path, fallback_log, tickers, families,
                 nav_symbols, *, cefconnect: bool, spike_guard: bool, split_rulings=None):
        self.name, self.px_path, self.nav_path, self.lock_path = name, px_path, nav_path, lock_path
        self.fallback_log, self.tickers, self.families = fallback_log, tickers, families
        self.nav_symbols, self.cefconnect, self.spike_guard = nav_symbols, cefconnect, spike_guard
        # THE PRICE BASIS (C4): the live fetch's split rulings file, or None (the core:
        # no conversion, no step guard, its fetch exactly as it was).
        self.split_rulings = split_rulings

    def nav_symbol(self, tk: str) -> str:
        return f"X{tk}X" if self.nav_symbols is None else self.nav_symbols[tk]


def resolve_data_book(name: str | None = None) -> DataBook:
    """The config for `name` (DATA BOOKS). None or "cef" is the core, read from
    this module's constants NOW, at call time, as the code before data books
    read them; "c4" is read from `scripts/cef/data_books.py` and refuses any
    path it would share with the core."""
    if name in (None, data_books.CORE):
        return DataBook(data_books.CORE, PX_PATH, NAV_PATH, LOCK_PATH, FALLBACK_LOG,
                        None, None, None, cefconnect=True, spike_guard=False)
    if name != data_books.C4:
        raise DataBookError(f"no data book {name!r}; the books are {list(data_books.BOOK_NAMES)}")
    d = Path(data_books.C4_DIR)
    fam = data_books.c4_universe()
    cfg = DataBook(data_books.C4, d / "cef_prices.parquet", d / "cef_nav.parquet", d / ".fetch.lock",
                   None, tuple(sorted(fam)), dict(fam), data_books.c4_nav_symbols(universe=fam),
                   cefconnect=False, spike_guard=True,
                   split_rulings=data_books.C4_FETCH_SPLIT_RULINGS)
    shared = [p for p in (cfg.px_path, cfg.nav_path, cfg.lock_path)
              if os.path.realpath(p) in {os.path.realpath(q) for q in
                                         (PX_PATH, NAV_PATH, LOCK_PATH, FALLBACK_LOG)}]
    if shared or os.path.realpath(d) == os.path.realpath(PX_PATH.parent):
        raise DataBookError(f"data book c4 would share {shared or [d]} with the core's data/cef; "
                            f"C4 has its own directory and lock")
    return cfg


def _check_book_panel(P: pd.DataFrame, N: pd.DataFrame, cfg: DataBook) -> None:
    """A book with a fixed universe refuses a panel that is not that book's:
    a fund outside it, or a fund under another family than the frozen one.
    Either means the panel was seeded from the wrong place, and fetching into
    it would extend the mistake every night."""
    extra = sorted((set(P["ticker"]) | set(N["ticker"])) - set(cfg.tickers))
    if extra:
        raise DataBookError(f"{cfg.px_path.parent} holds {extra}, not in data book {cfg.name}'s "
                            f"{len(cfg.tickers)} funds: a mis-seeded panel (data_books.py, SEED)")
    wrong = {t: sorted(map(str, g)) for t, g in P.groupby("ticker")["grp"].unique().items()
             if list(g) != [cfg.families[t]]}
    if wrong:
        raise DataBookError(f"{cfg.px_path} gives {wrong} a grp other than the frozen family")


def _price_basis(P, N, newp: list, newn: list, declared: list, cfg: DataBook):
    """THE PRICE BASIS (C4; data_guards.py, THE LIVE FETCH'S PRICE BASIS): (the fetched
    price frames, each ruled split's adjusted pre-ex rows put on the NAV's basis, and
    None) or (them unchanged, the refusal's text). Refused: a split Yahoo declares in the
    fetch that no ruling names; a ruled split whose rows cannot be judged; a fetched
    close or NAV whose ratio to the stored value of the same date is split-like. Every
    converted run is printed. Each fetched frame keeps its own rows and columns."""
    from scripts.cef.data_guards import (PriceBasisError, _factor_label, basis_steps,
                                         describe_basis_steps, load_fetch_split_rulings,
                                         to_nav_basis, unruled_declared_splits)
    rulings = load_fetch_split_rulings(cfg.split_rulings)
    unruled = unruled_declared_splits(declared, rulings)
    if unruled:
        return newp, ("unruled split(s) Yahoo declares in the fetched window, so its earlier closes "
                      "may be split-adjusted against an unadjusted NAV: "
                      + "; ".join(f"({t}, {d.date()}, factor {_factor_label(v)})" for t, d, v in unruled)
                      + f". Rule each in {Path(cfg.split_rulings).name} (to_nav_basis or book_as_is)")
    if not newp:
        return newp, None
    F = pd.concat(newp, ignore_index=True)
    FN = pd.concat(newn, ignore_index=True) if newn else pd.DataFrame(columns=["date", "nav", "ticker"])
    judge = pd.concat([N[["date", "nav", "ticker"]], FN[["date", "nav", "ticker"]]], ignore_index=True)
    try:
        G, log = to_nav_basis(F, judge, rulings, context=f"fetch_daily --data-book {cfg.name}")
    except PriceBasisError as e:
        return newp, str(e)
    hits = basis_steps(G, P, FN, N)
    if hits:
        return newp, ("a fetched value steps against the stored one by a split-like ratio, which is a "
                      "change of share basis, not a revision: " + describe_basis_steps(hits)
                      + ". Rule the split (to_nav_basis), or repair the stored rows "
                        "(scripts/cef/data_books.py repair-basis), before this panel is written")
    for e in log:
        if e["treatment"] == "to_nav_basis" and e["converted"]:
            print(f"  BASIS    {e['ticker']:<6} {e['first'].date()}..{e['last'].date()}: {e['converted']} "
                  f"fetched pre-split row(s) on the vendor's split-adjusted basis put on the NAV's "
                  f"(x{e['factor']:.6g}; split {e['ex_date'].date()}, {Path(cfg.split_rulings).name})")
        elif e["treatment"] == "book_as_is":
            print(f"  BASIS    {e['ticker']:<6} split {e['ex_date'].date()}: {e['as_served']} pre-ex row(s) "
                  f"kept as served (book_as_is, {Path(cfg.split_rulings).name})")
    # Back into one frame per fund, as merge_price_bars takes them.
    return [g.reset_index(drop=True) for _, g in G.groupby("ticker", sort=False)], None


def _spike_check(P: pd.DataFrame, N: pd.DataFrame, fetched: list, cfg: DataBook):
    """The C4 spike guard (DATA BOOKS): `data_guards.guard_closes`' message for
    the fetched window of the merged panel, or None when it is clean.

    In scope: any spike-and-revert run that touches [first fetched date, last
    panel date], so a bar rewritten tonight is judged tonight, and a run whose
    revert arrives tomorrow is judged tomorrow. No split multipliers (yfinance
    back-adjusts its close for every split it knows, so a recorded multiplier
    would create a step, data_guards.py guard 3), and no rulings file: C4's
    research ruling of 2026-10-19 was made on the families panel for the
    trial's holdout, not on this one. A close that is not positive raises
    from the guard itself, by design."""
    from scripts.cef.data_guards import SpikeRevertError, guard_closes
    dated = [p["date"].min() for p in fetched if len(p)]
    if not dated:
        return None
    close = P.pivot(index="date", columns="ticker", values="close")
    nav = N.pivot(index="date", columns="ticker", values="nav")
    try:
        guard_closes(close, cols=list(cfg.tickers), lo=min(dated), hi=P["date"].max(), nav=nav,
                     splits=None, rulings=None, context=f"fetch_daily --data-book {cfg.name}")
    except SpikeRevertError as e:
        return str(e)
    return None


class PanelLockTimeout(RuntimeError):
    """Another fetch held the panel lock for longer than the bounded wait."""


class panel_lock:
    """Exclusive `flock` on `path` for the life of the `with` block.

    Polls with LOCK_NB rather than blocking, because flock has no timeout of
    its own and an unbounded wait is the hang this exists to prevent. The
    holder writes its pid and start time into the file and a timeout names
    them, so a stuck run can be found. The kernel releases the lock if the
    holder dies, so a crash can never leave it held.
    """

    def __init__(self, path, wait_s: float = LOCK_WAIT_S, poll_s: float = LOCK_POLL_S):
        self.path, self.wait_s, self.poll_s = Path(path), float(wait_s), float(poll_s)
        self._fd = None

    def __enter__(self):
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        deadline = time.monotonic() + self.wait_s
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    holder = os.pread(fd, 200, 0).decode("utf-8", "replace").strip()
                    os.close(fd)
                    raise PanelLockTimeout(
                        f"panel lock {self.path} still held after {self.wait_s:.0f}s "
                        f"(holder: {holder or 'unrecorded'}); not refreshing") from None
                time.sleep(self.poll_s)
        os.ftruncate(fd, 0)
        os.pwrite(fd, f"pid {os.getpid()} since {datetime.now().isoformat()}\n".encode(), 0)
        self._fd = fd
        return self

    def __exit__(self, *exc):
        fd, self._fd = self._fd, None
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        return False


def _cefconnect_navs(ticker: str, dates) -> dict:
    """{date: CEFConnect's NAV dated exactly that day, or None}, for each of
    `dates`. Daily rows, ONE request however many dates (2026-10-13: the
    session's stale-NAV gate needs D and D-1 for every deployed name). Rows are
    read newest first and the first row for a date wins, exactly as the
    single-date reader always did."""
    import requests
    out = {pd.Timestamp(d).normalize(): None for d in dates}
    r = requests.get(f"https://www.cefconnect.com/api/v3/pricinghistory/{ticker}/1Y",
                     headers=CC_HEADERS, timeout=20)
    rows = r.json()["Data"]["PriceHistory"]
    seen = set()
    for x in reversed(rows):
        d = pd.Timestamp(x["DataDate"]).normalize()
        if d in out and d not in seen:
            out[d] = float(x["NAVData"])
            seen.add(d)
            if len(seen) == len(out):
                break
    return out


def _cefconnect_nav(ticker: str, asof: pd.Timestamp):
    """CEFConnect's NAV dated exactly `asof`, or None. Daily rows, one request."""
    return _cefconnect_navs(ticker, [asof])[pd.Timestamp(asof).normalize()]


def merge_nav_fills(N: pd.DataFrame, F: pd.DataFrame) -> pd.DataFrame:
    """The NAV panel with the (date, ticker) rows of `F` written over it.

    The one way a NAV not taken from yfinance enters the panel: the
    `--nav-fallback cefconnect` fill below (a NAV yfinance does not have yet)
    and the session's stale-NAV gate (`quantt/session/nav_gate.py`: a yfinance
    row dated D that repeats D-1 while CEFConnect's D differs). Every such row
    is also appended to the fallback log (`log_nav_fills`)."""
    return (pd.concat([N, F], ignore_index=True)
              .drop_duplicates(subset=["date", "ticker"], keep="last")
              .sort_values(["ticker", "date"]))


def log_nav_fills(F: pd.DataFrame, source: str, log_path=None) -> None:
    """Append `F`'s rows to data/cef/nav_fallback_log.csv (columns date, nav,
    ticker, source, written_utc; header written when the file is absent).
    `source` says which path wrote the row: "cefconnect" for a missing NAV,
    "cefconnect_stale_copy" for the gate's replacement. The collector reads this
    log to know a panel NAV came from CEFConnect (`quantt/collect/collect.py`
    `_fallback_names`), so every non-yfinance NAV must be in it."""
    path = FALLBACK_LOG if log_path is None else Path(log_path)
    rec = F.assign(source=source, written_utc=pd.Timestamp.utcnow())
    rec.to_csv(path, mode="a", index=False, header=not path.exists())


def has_close(frame: pd.DataFrame) -> pd.Series:
    """True where a price row carries a close: present and finite.

    THE ONE TEST for an empty row (module docstring, EMPTY ROWS), shared by the
    merge and the as-of check so the two cannot disagree (and, from the second
    half of the fix, by scripts/cef/stage_cef.py). It keys on the close
    alone. Volume 0 does not make a row empty: real zero-volume days carry a
    close and are kept, and the 0 on an empty row is yfinance's fill. A close
    that is not numeric raises (`pd.to_numeric`), never coerced to "missing"."""
    c = pd.to_numeric(frame["close"]).to_numpy(dtype="float64", na_value=np.nan)
    return pd.Series(np.isfinite(c), index=frame.index)


def merge_price_bars(P: pd.DataFrame, fetched: list) -> tuple:
    """(panel, log): `fetched` merged into the price panel `P`, and one entry per
    row the merge refused or repaired.

    The merge is the one it always was -- concat, keep the LAST row for each
    (date, ticker), sort -- run on the fetched rows that have a close. A
    fetched row with no close is held back, so it can neither replace a panel
    bar nor become a new date (by 2026-10-15, 15 good 2026-09-15 bars had been
    emptied this way; module docstring, EMPTY ROWS). A fetched bar with a close
    that lands on a panel row with none replaces it, as keep="last" always did;
    that repair is now logged. A frame with no empty row is passed through
    untouched, so a fetch without one writes the same bytes as before.

    Each log entry is {"what": "NO CLOSE" | "REPAIRED", "ticker", "date",
    "why"}; the caller prints them. `why` says what the panel holds for that
    date, read from `P` BEFORE the merge."""
    dated = [p["date"].min() for p in fetched if len(p)]
    # Only rows inside the fetched window can be refused or repaired.
    W = P[P["date"] >= min(dated)] if dated else P.iloc[:0]
    w_has = has_close(W)
    panel_bar = set(zip(W.loc[w_has, "date"], W.loc[w_has, "ticker"]))
    panel_empty = set(zip(W.loc[~w_has, "date"], W.loc[~w_has, "ticker"]))
    keep, log = [], []
    for p in fetched:
        ok = has_close(p)
        for r in p.loc[~ok].itertuples(index=False):
            k = (r.date, r.ticker)
            why = ("not merged: the panel's bar for this date has a close and is kept"
                   if k in panel_bar else
                   "not merged: the panel's row for this date has no close either and is left as it was"
                   if k in panel_empty else
                   "not written: the panel has no row for this date")
            log.append({"what": "NO CLOSE", "ticker": r.ticker, "date": r.date,
                        "why": f"(close {r.close}, volume {r.volume}) {why}"})
        for r in p.loc[ok].itertuples(index=False):
            if (r.date, r.ticker) in panel_empty:
                log.append({"what": "REPAIRED", "ticker": r.ticker, "date": r.date,
                            "why": f"the panel's row had no close; yfinance's bar "
                                   f"(close {r.close:g}, volume {r.volume:,}) replaces it"})
        if ok.all():
            keep.append(p)            # as before, even a frame the clock emptied
        elif ok.any():
            keep.append(p.loc[ok])    # an all-empty frame is not concatenated at all
    out = (pd.concat([P] + keep, ignore_index=True)
             .drop_duplicates(subset=["date", "ticker"], keep="last")
             .sort_values(["ticker", "date"]))
    return out, log


def has_nav(frame: pd.DataFrame) -> pd.Series:
    """True where a NAV row carries a NAV: present, finite and positive.

    `has_close` for the NAV (module docstring, EMPTY NAV ROWS): THE ONE TEST
    for an empty NAV row, shared by the NAV merge, the stale check, the as-of
    check and stage_cef so they cannot disagree. POSITIVE as well as finite
    (FOLLOW-UPS (1)): it is the session's test (`last_navs`, `panel_rows`,
    `read_cc`), so a NAV this script writes and counts is one gate 5 accepts.
    A NAV that is not numeric raises (`pd.to_numeric`), never coerced to
    "missing"."""
    v = pd.to_numeric(frame["nav"]).to_numpy(dtype="float64", na_value=np.nan)
    with np.errstate(invalid="ignore"):       # NaN > 0 is False, as wanted
        return pd.Series(np.isfinite(v) & (v > 0), index=frame.index)


def merge_nav_rows(N: pd.DataFrame, fetched: list) -> tuple:
    """(panel, log): the fetched NAV frames merged into the NAV panel `N`, and
    one entry per row the merge refused or repaired.

    `merge_price_bars` for the NAV, rule for rule (module docstring, EMPTY NAV
    ROWS; the price half's incident of 2026-10-28 is why). The merge is the one
    it always was -- concat, keep the LAST row for each (date, ticker), sort --
    run on the fetched rows that have a NAV. A fetched row with no NAV is held
    back, so it can neither replace a panel NAV nor become a new date. A
    fetched NAV that lands on a panel row with none replaces it, as keep="last"
    always did; that repair is now logged. A frame with no empty row is passed
    through untouched, so a fetch without one writes the same bytes as before.

    Each log entry is {"what": "NO NAV" | "NAV REPAIRED", "ticker", "date",
    "why"}; the caller prints them. `why` says what the panel holds for that
    date, read from `N` BEFORE the merge. This is the yfinance merge only: a
    CEFConnect NAV enters through `merge_nav_fills`, after its own check."""
    dated = [n["date"].min() for n in fetched if len(n)]
    # Only rows inside the fetched window can be refused or repaired.
    W = N[N["date"] >= min(dated)] if dated else N.iloc[:0]
    w_has = has_nav(W)
    panel_nav = set(zip(W.loc[w_has, "date"], W.loc[w_has, "ticker"]))
    panel_empty = set(zip(W.loc[~w_has, "date"], W.loc[~w_has, "ticker"]))
    keep, log = [], []
    for n in fetched:
        ok = has_nav(n)
        for r in n.loc[~ok].itertuples(index=False):
            k = (r.date, r.ticker)
            why = ("not merged: the panel's NAV for this date is kept"
                   if k in panel_nav else
                   "not merged: the panel's row for this date has no NAV either and is left as it was"
                   if k in panel_empty else
                   "not written: the panel has no NAV row for this date")
            log.append({"what": "NO NAV", "ticker": r.ticker, "date": r.date,
                        "why": f"(nav {r.nav}) {why}"})
        for r in n.loc[ok].itertuples(index=False):
            if (r.date, r.ticker) in panel_empty:
                log.append({"what": "NAV REPAIRED", "ticker": r.ticker, "date": r.date,
                            "why": f"the panel's row had no NAV; yfinance's NAV "
                                   f"{r.nav:g} replaces it"})
        if ok.all():
            keep.append(n)            # as before, even a frame the clock emptied
        elif ok.any():
            keep.append(n.loc[ok])    # an all-empty frame is not concatenated at all
    out = (pd.concat([N] + keep, ignore_index=True)
             .drop_duplicates(subset=["date", "ticker"], keep="last")
             .sort_values(["ticker", "date"]))
    return out, log


def nav_age(n: pd.DataFrame, today: pd.Timestamp) -> tuple:
    """(last NAV date as text, business days since it | None) for one fund's
    fetched NAV rows, for the stale check.

    Dated by the last row WITH a NAV (`has_nav`; module docstring, EMPTY NAV
    ROWS), never by the last row: before 2026-10-28 an empty row dated today
    would have made a fund whose real NAV was weeks old read as fresh, the one
    failure the stale check exists to catch. A fund whose fetched rows carry
    no NAV at all has no age to give: it is returned as (what was fetched,
    None), and the caller lists it stale. With no empty rows this is exactly
    the old `str(n.date.max().date())` and `len(bdate_range(n.date.max(),
    today)) - 1` -- including a frame with NO rows (the clock dropped its only,
    partial, row), whose NaT date makes `bdate_range` raise as it always did:
    that edge is unchanged here on purpose, not fixed."""
    good = n.loc[has_nav(n), "date"]
    if len(n) and good.empty:
        return f"none: no finite positive NAV in the {len(n)} row(s) fetched", None
    last = good.max()
    return str(last.date()), len(pd.bdate_range(last, today)) - 1


def _deployed(book_path) -> list:
    sys.path.insert(0, str(REPO))
    from ops.common import deployed_tickers
    return sorted({t for insts in deployed_tickers(Path(book_path)).values() for t in insts})


def _refuse_cefconnect(nav_fallback, cfg: DataBook) -> None:
    """Raise if `cfg` may not read CEFConnect and the fallback was asked for
    (DATA BOOKS): before the lock and before any panel is read."""
    if nav_fallback is not None and not cfg.cefconnect:
        raise CefConnectDisabled(
            f"--nav-fallback {nav_fallback} is refused for data book {cfg.name}: CEFConnect is "
            f"disabled for it (team lead, 2026-10-28; C4's NAV-repeat mask M1 catches a stale "
            f"NAV instead)")


def refresh(period: str = "6mo", require_asof=None, nav_fallback=None,
            book=None, data_book=None) -> int:
    cfg = resolve_data_book(data_book)
    _refuse_cefconnect(nav_fallback, cfg)
    if not cfg.px_path.exists():
        print("no staged panel; run scripts/cef/stage_cef.py first" if cfg.name == data_books.CORE
              else f"no {cfg.name} panel at {cfg.px_path}; seed it first "
                   f"(scripts/cef/data_books.py, SEED)")
        return 1
    # The read below and the write at its end are one transaction (LOCKING),
    # under this book's own lock (DATA BOOKS).
    with panel_lock(cfg.lock_path, LOCK_WAIT_S, LOCK_POLL_S):
        if cfg.name == data_books.CORE:
            return _refresh_locked(period, require_asof, nav_fallback, book)
        return _refresh_locked(period, require_asof, nav_fallback, book, cfg)


def _refresh_locked(period, require_asof, nav_fallback, book, cfg: DataBook | None = None) -> int:
    # `cfg` None is the core, resolved now (DATA BOOKS): the four-argument call
    # is the one this function has always had.
    cfg = resolve_data_book(None) if cfg is None else cfg
    _refuse_cefconnect(nav_fallback, cfg)
    P, N = pd.read_parquet(cfg.px_path), pd.read_parquet(cfg.nav_path)
    now = datetime.now(ET)
    today = pd.Timestamp(now.date())
    session_open = before_close(now)
    if session_open:
        print(f"  {now:%H:%M} is before the close: any bar dated {today.date()} "
              f"is a partial session and will not be written")
    if cfg.tickers is None:
        tickers = sorted(P.ticker.unique())
        grp = P.drop_duplicates("ticker").set_index("ticker")["grp"].to_dict()
    else:
        # A fixed universe (C4): its own funds and families, and a panel that
        # holds anything else is refused (`_check_book_panel`).
        _check_book_panel(P, N, cfg)
        tickers = list(cfg.tickers)
        grp = dict(cfg.families)

    newp, newn, stale = [], [], []
    # Funds the stale check could not date (FOLLOW-UPS (3)): never "fresh".
    unchecked = []
    # THE PRICE BASIS (C4): every split Yahoo declares in a fetched price history.
    declared = []
    for tk in tickers:
        try:
            px = yf.Ticker(tk).history(period=period, auto_adjust=False)
            nav = yf.Ticker(cfg.nav_symbol(tk)).history(period=period, auto_adjust=False)
        except Exception as e:
            print(f"  ERR {tk:<6} {type(e).__name__}")
            unchecked.append((tk, f"fetch error: {type(e).__name__}"))
            continue
        if len(px):
            if cfg.split_rulings is not None and "Stock Splits" in px.columns:
                ev = px[px["Stock Splits"].fillna(0) != 0]
                declared += [(tk, pd.Timestamp(d).tz_localize(None).normalize(), float(v))
                             for d, v in zip(ev.index, ev["Stock Splits"])]
            p = px.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
            p.columns = ["date", "open", "high", "low", "close", "volume"]
            p["date"] = pd.to_datetime(p["date"]).dt.tz_localize(None).dt.normalize()
            if session_open:
                p = p[p["date"] < today]
            p["ticker"], p["grp"] = tk, grp.get(tk, "?")
            newp.append(p)
        if len(nav):
            n = nav.reset_index()[["Date", "Close"]]
            n.columns = ["date", "nav"]
            n["date"] = pd.to_datetime(n["date"]).dt.tz_localize(None).dt.normalize()
            if session_open:
                n = n[n["date"] < today]
            n["ticker"] = tk
            newn.append(n)
            # Dated by the last row WITH a NAV, so an empty row is never a
            # fresh NAV (module docstring, EMPTY NAV ROWS; `nav_age`), and aged
            # to this run's ET date, not the machine's (FOLLOW-UPS (2)).
            last, age = nav_age(n, today)
            if age is None or age > STALE_BD:
                stale.append((tk, last, age))
        else:
            unchecked.append((tk, "no NAV rows fetched"))

    # THE PRICE BASIS (C4 only; data_guards.py, THE LIVE FETCH'S PRICE BASIS): before
    # anything is merged, the ruled splits' adjusted pre-ex closes go back on the NAV's
    # basis, and a fetched value that still steps against the stored one refuses the
    # write. The core's `split_rulings` is None: this block does not run for it.
    if cfg.split_rulings is not None:
        newp, refused = _price_basis(P, N, newp, newn, declared, cfg)
        if refused is not None:
            print(f"  {BASIS_TAG} (data book {cfg.name}; NOTHING written): {refused}")
            return EXIT_BASIS

    # A fetched row with no close, or no NAV, is never merged; each refusal or
    # repair is printed (module docstring, EMPTY ROWS and EMPTY NAV ROWS).
    P, bar_log = merge_price_bars(P, newp)
    for e in bar_log:
        print(f"  {e['what']:<8} {e['ticker']:<6} {e['date'].date()} {e['why']}")
    N, nav_log = merge_nav_rows(N, newn)
    for e in nav_log:
        print(f"  {e['what']:<8} {e['ticker']:<6} {e['date'].date()} {e['why']}")

    incomplete = []
    if require_asof is not None:
        asof = pd.Timestamp(require_asof).normalize()
        names = _deployed(book) if book else sorted(tickers)
        if cfg.tickers is not None:
            # A deployed name this book never fetches could never be complete;
            # that is a wrong book json, said so, not an exit 4 every night.
            stray = sorted(set(names) - set(cfg.tickers))
            if stray:
                raise DataBookError(f"--book {book} deploys {stray}, which data book "
                                    f"{cfg.name} does not fetch")
        # A row dated D with no close is not D's close (EMPTY ROWS): the panel
        # can still hold one written before 2026-10-28, and the fetch may not
        # have brought the bar. Same test as the merge (`has_close`).
        at = P[P["date"] == asof]
        at_has = has_close(at)
        have_px = set(at.loc[at_has, "ticker"])
        empty_px = set(at.loc[~at_has, "ticker"])
        # Likewise a row dated D with no NAV is not D's NAV (EMPTY NAV ROWS):
        # it goes to the CEFConnect fallback, if asked for, like a missing row.
        at_n = N[N["date"] == asof]
        at_n_has = has_nav(at_n)
        have_nav = set(at_n.loc[at_n_has, "ticker"])
        empty_nav = set(at_n.loc[~at_n_has, "ticker"])
        need_nav = [t for t in names if t not in have_nav]
        if need_nav and nav_fallback == "cefconnect":
            filled = []
            for tk in need_nav:
                try:
                    v = _cefconnect_nav(tk, asof)
                except Exception as e:
                    print(f"  cefconnect {tk}: {type(e).__name__}")
                    continue
                if v is None:
                    continue
                if not (np.isfinite(v) and v > 0):
                    # The fallback must not write the empty NAV it exists to
                    # replace (EMPTY NAV ROWS; positive too, FOLLOW-UPS (1));
                    # the name stays incomplete.
                    print(f"  {'NO NAV':<8} {tk:<6} {asof.date()} (nav {v}) not written: "
                          f"CEFConnect's NAV for this date is not a finite positive number")
                    continue
                filled.append({"date": asof, "nav": v, "ticker": tk})
                print(f"  NAV {tk} {asof.date()} = {v:.2f} from CEFConnect "
                      + ("(yfinance's row for this date has no NAV)" if tk in empty_nav
                         else "(not on yfinance yet)"))
            if filled:
                F = pd.DataFrame(filled)
                N = merge_nav_fills(N, F)
                log_nav_fills(F, "cefconnect", cfg.fallback_log)
                have_nav |= set(F["ticker"])
        def gap(t):
            # A missing row reads exactly as it always did; an empty one says so.
            px = (f"no close (its {asof.date()} row is empty)" if t in empty_px
                  else "no close")
            nv = (f"no NAV (its {asof.date()} row is empty)" if t in empty_nav
                  else "no NAV")
            return "/".join(([px] if t not in have_px else [])
                            + ([nv] if t not in have_nav else []))
        incomplete = [f"{t}: {gap(t)}"
                      for t in names if t not in have_px or t not in have_nav]

    # Atomic: these two ARE what the sleeve prices from, and the session
    # holding them open overlaps this write. See ops.common.atomic_write.
    atomic_write(P, cfg.px_path)
    atomic_write(N, cfg.nav_path)
    # C4 only: judged after the write, so the panel is the record of what was
    # served either way (DATA BOOKS, THE SPIKE GUARD).
    spike = _spike_check(P, N, newp, cfg) if cfg.spike_guard else None

    tally = {w: sum(e["what"] == w for e in bar_log) for w in ("NO CLOSE", "REPAIRED")}
    print(f"  prices {len(P):,} rows -> {P.date.max().date()}"
          + (f" ({tally['NO CLOSE']} fetched row(s) with no close not merged, "
             f"{tally['REPAIRED']} empty row(s) repaired; listed above)" if bar_log else ""))
    nav_tally = {w: sum(e["what"] == w for e in nav_log) for w in ("NO NAV", "NAV REPAIRED")}
    print(f"  NAV    {len(N):,} rows -> {N.date.max().date()}"
          + (f" ({nav_tally['NO NAV']} fetched row(s) with no NAV not merged, "
             f"{nav_tally['NAV REPAIRED']} empty NAV row(s) repaired; listed above)"
             if nav_log else ""))
    if stale:
        print(f"  STALE NAV ({len(stale)} funds, >{STALE_BD} business days old) — "
              f"the sleeve must not trade these:")
        # A fund with no NAV in its fetch (age None) is listed first, the worst
        # case; with every age known the order is the old one (-age, stable).
        for tk, d, age in sorted(stale, key=lambda x: (x[2] is not None, -(x[2] or 0))):
            print(f"    {tk:<6} last NAV {d}  ({age} bd old)" if age is not None
                  else f"    {tk:<6} last NAV {d}")
    elif not unchecked:
        print(f"  all {N.ticker.nunique()} NAV series fresh within {STALE_BD} bd")
    else:
        print(f"  every NAV series checked is fresh within {STALE_BD} bd, "
              f"but not every series was checked:")
    if unchecked:
        # Never counted as fresh (FOLLOW-UPS (3)): the check never saw them.
        print(f"  UNCHECKED NAV ({len(unchecked)} funds, freshness not measured): "
              + "; ".join(f"{tk} ({why})" for tk, why in unchecked))
    if spike is not None:
        print(f"  SPIKE-REVERT (data book {cfg.name}; the panel is written, the bar is not "
              f"to be traded until ruled): {spike}")
    if incomplete:
        print(f"  {INCOMPLETE_TAG} {pd.Timestamp(require_asof).date()} on "
              f"{len(incomplete)} deployed name(s): " + "; ".join(incomplete))
    elif require_asof is not None:
        print(f"  today's pair complete: every deployed name has a close and a "
              f"NAV dated {pd.Timestamp(require_asof).date()}")
    if spike is not None:
        # AN UNRULED SPIKE OUTRANKS AN INCOMPLETE PAIR (module docstring, THE SPIKE
        # GUARD; release-check of 8b14298): exit 4 is what C4's missing-NAV hold
        # accepts at the final check, so 4 here would trade the unruled bar on any
        # day a NAV is late. Only a data book with the guard on reaches this line;
        # the core's `spike` is always None, so its exits below are unchanged.
        return EXIT_SPIKE
    return 4 if incomplete else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--period", default="6mo")
    ap.add_argument("--require-asof", default=None)
    ap.add_argument("--nav-fallback", choices=["cefconnect"], default=None)
    ap.add_argument("--book", default=None,
                    help="book json; with --require-asof, only its deployed "
                         "names must be complete (default: the whole panel)")
    ap.add_argument("--data-book", choices=sorted(data_books.BOOK_NAMES), default=None,
                    help="whose panels: cef (the default; data/cef) or c4 (data/cef_c4, the "
                         "74 frozen funds, its own lock, CEFConnect refused); module "
                         "docstring, DATA BOOKS")
    a = ap.parse_args(argv)
    try:
        if a.data_book is None:          # the call this command has always made
            return refresh(a.period, a.require_asof, a.nav_fallback, a.book)
        return refresh(a.period, a.require_asof, a.nav_fallback, a.book, data_book=a.data_book)
    except PanelLockTimeout as e:
        print(f"  LOCKED: {e}")
        return EXIT_LOCKED
    except CefConnectDisabled as e:
        print(f"  REFUSED: {e}")
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
