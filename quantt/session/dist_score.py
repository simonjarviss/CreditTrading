"""The third score: auction-marked P&L plus the distributions a real account would book.

WHY IT EXISTS
-------------
Alpaca paper credits no dividends [V: docs.alpaca.markets/us/docs/paper-trading,
fetched 2026-09-28]. On a CEF's ex-date its price drops by about the distribution.
So a paper LONG loses that drop with nothing credited back, and a paper SHORT
gains it without paying the distribution a real short owes its lender. Measured
2026-10-08 (`scripts/xasset/book_profile.py`): the book has recently been net
short distribution yield, a distribution leg of about −0.6 to −0.9%/yr. The two
existing scores (`score.py`) therefore flatter the book against a real account.
The team lead ruled on 2026-10-09 (`docs/SYSTEM.md` §5) to carry a third line
beside them. This module is that line.

THE RULE
--------
For session D, with `held` = the signed shares held at the START of D (verify's
`held_into_close`, q0, read back from `<state>/<D>/reconcile.json`):

    distribution_pnl_D = sum_s held[s] * cash_per_share[s, ex_date == D]
    auction_pnl_with_distributions_D = auction_pnl_D + distribution_pnl_D

The holder at the previous close is the one entitled on the ex-date. Under T+1
the record date is the ex-date, so a long is credited and a short is charged.
Shares bought or sold on D trade ex, so D's fills earn nothing here.
`auction_pnl_D` (from `scores.csv`) already carries the ex-date price drop, so
the sum is what a real account filled in the auction would have earned, gross of
borrow and fees.

WHY D IS SCORED TWO SESSIONS LATE (review 2026-10-09)
-----------------------------------------------------
The first build scored D at D's own 17:30 verify. It wrote 0.0 when neither
source listed D. But at 17:30 the second source often had not caught up:
- on at least 3 of 6 days measured (2026-09-30 to 10-07), the collector's
  `distributions` step finished after 17:30 ET;
- yfinance lists an ex-date only after it passes, and whether it lists it the
  same day is [U];
- the panel is not rewritten at all if any ticker's fetch fails.

So a zero written then could be "Alpaca is silent" alone, which is exactly what
Alpaca warns against ("may not be available immediately after they are
announced" [V]). Now:
- each verify run scores every session D at least `LAG_SESSIONS` sessions old
  (and at most `LOOKBACK_SESSIONS`) that does not yet have a MEASURED row;
- a zero is written only when the panel FILE was rewritten after the close of
  the session following D. That means two independent sources have both been
  silent for a full session after the ex-date. Otherwise the name is UNMEASURED,
  and a later run retries it.

WHERE THE AMOUNTS COME FROM, AND WHEN ONE IS UNMEASURED
-------------------------------------------------------
Primary: Alpaca's corporate actions (`AlpacaClient.distributions`). These are the
broker's own data and list DECLARED distributions weeks ahead.
Second source: the repo's yfinance panel, `data/cef/cef_distributions.parquet`.
It rounds to 3 decimals where Alpaca has 4. Measured 2026-10-09 on the 13 names,
June to August: 28 of the 40 common events differed, all by ≤ 0.0005 and none by
more. The resolution rules:

  both list D, |diff| ≤ ROUNDING_TOL per event  -> Alpaca's (more precise) amount
  both list D, |diff| > ROUNDING_TOL            -> UNMEASURED, naming both values
  only Alpaca lists D                           -> Alpaca's amount (noted)
  only the panel lists D                        -> UNMEASURED: Alpaca's silence is not a zero
  neither lists D, the panel is current and
    has rows for the name                       -> 0.0, naming the panel's write time
  neither lists D, the panel has no rows for
    the name                                    -> UNMEASURED: one silent source is not two
  neither lists D, the panel is not current     -> UNMEASURED; retried next run

WHY "HAS ROWS FOR THE NAME" (review 2026-10-11). A current panel FILE says the
fetch ran, not that it covered every name. `scripts/fetch_cef_distributions.py`
skips a ticker whose yfinance response is empty and still rewrites the panel, and
the panel never covers a name outside `data/cef/cef_universe.csv` (passing
sleeves run in the CEF account under the 2026-10-09 ruling). Both happen: the
2026-09-11 fetch listed FCT, a monthly payer, as empty, and that panel holds 43 of
44 tickers. Without this rule a held FCT on an Alpaca-silent ex-date was a
measured, final 0.0.

Never averaged. Every name's row records the rule that applied and the Alpaca
event ids and kinds behind its amount, so a payout listed under two types could
be audited. A name that is UNMEASURED makes the day's distribution P&L
UNMEASURED: a sum with a missing term is not the sum, as in `score.py`.

IT NEVER CHANGES THE VERDICT
----------------------------
It runs after verify has written the verdict, `scores.csv` and `reconcile.json`.
It writes only `<state>/distribution_scores.csv`, one row per session, upserted
atomically. A measured row is final. An UNMEASURED row is replaced by the next
run that can measure the day.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
LABEL = ("distribution-adjusted: auction-marked P&L plus distributions on shares held "
         "at the start of the ex-date (credited long, charged short); gross of borrow "
         "and fees; Alpaca paper credits none")
COLUMNS = ("date", "auction_pnl_usd", "distribution_pnl_usd",
           "auction_pnl_with_distributions_usd", "unmeasured", "per_symbol_json",
           "source", "label", "written_at_utc")
UNMEASURED = "UNMEASURED"

# yfinance serves 3 decimals, Alpaca 4: the largest rounding gap is 0.0005 per
# event (measured 2026-10-09, module docstring). Anything wider is a real conflict.
ROUNDING_TOL = 0.0005
# Score D only once this many sessions have closed after it (module docstring).
LAG_SESSIONS = 2
# Retry unmeasured days this far back; older gaps stay UNMEASURED, visibly.
LOOKBACK_SESSIONS = 15
# Alpaca's start/end filter is undocumented ("sorted by their process_date"), so the
# window is wide on both sides and the ex-date is filtered here.
QUERY_DAYS = 120
SESSION_CLOSE = dt.time(16, 0)

DEFAULT_PANEL = Path(__file__).resolve().parents[2] / "data" / "cef" / "cef_distributions.parquet"
# EACH BOOK'S SECOND SOURCE (C4 deploy plan row 8, 2026-10-29). The yfinance panel
# is the one its book's distribution fetcher writes: the core's
# `scripts/fetch_cef_distributions.py` into data/cef/, C4's `--data-book c4` into
# data/cef_c4/ (scripts/cef/data_books.py C4_DIR, the C4 spec's panel_source
# directory; quantt/session/tests/test_c4_book.py pins all three). Scoring C4's
# 74 against the core's panel would find "no rows for the name" for every fund and
# leave every C4 day UNMEASURED; a book not listed raises rather than borrow a
# panel that never covers its names.
PANELS = {"cef": DEFAULT_PANEL,
          "c4": Path(__file__).resolve().parents[2] / "data" / "cef_c4" / "cef_distributions.parquet"}


class DistError(RuntimeError):
    """A fact the distribution score needs is missing or contradictory. Names it."""


# ------------------------------------------------------------------ pure parts

def panel_for(book: str) -> Path:
    """The distributions panel `book`'s verify scores against (PANELS), or raise."""
    if book not in PANELS:
        raise DistError(f"no distributions panel for book {book!r}; the books are "
                        f"{sorted(PANELS)}")
    return PANELS[book]


def score(held: dict, per_share: dict, gaps: dict) -> tuple[float | None, list, list]:
    """(distribution_pnl, rows, unmeasured). Pure.

    held       {symbol: signed whole shares at the start of D}, non-zero ints.
    per_share  {symbol: cash per share with ex-date D}; 0.0 means "none on D".
    gaps       {symbol: reason the amount is unknown}.
    Every held symbol must be in exactly one of `per_share` and `gaps`: a symbol
    in neither was never resolved, which is a caller bug and raises.
    """
    rows, unmeasured, total = [], [], 0.0
    for sym in sorted(held):
        q = held[sym]
        if type(q) is not int or q == 0:
            raise DistError(f"held[{sym}] = {q!r} must be a non-zero int (whole shares)")
        if (sym in per_share) == (sym in gaps):
            raise DistError(f"{sym}: must be in exactly one of per_share and gaps "
                            f"({'both' if sym in per_share else 'neither'})")
        if sym in gaps:
            reason = gaps[sym]
            if not isinstance(reason, str) or not reason.strip():
                raise DistError(f"{sym}: gap has no reason")
            unmeasured.append(f"{sym}: {reason}")
            rows.append({"symbol": sym, "held_qty": q, "per_share": None, "dist_pnl": None})
            continue
        a = per_share[sym]
        if isinstance(a, bool) or not isinstance(a, (int, float)) or not math.isfinite(a) or a < 0:
            raise DistError(f"{sym}: per-share amount {a!r} must be a finite number >= 0")
        pnl = q * float(a)
        total += pnl
        rows.append({"symbol": sym, "held_qty": q, "per_share": float(a), "dist_pnl": pnl})
    return (None if unmeasured else total), rows, unmeasured


def resolve(symbols, day: dt.date, alpaca_events: list, panel, *, panel_current: bool,
            panel_note: str) -> tuple[dict, dict, dict, dict]:
    """(per_share, gaps, notes, events) for `symbols` on ex-date `day`, by the module's rules.

    alpaca_events  `AlpacaClient.distributions` output (any window containing D).
    panel          a DataFrame with ticker / ex_date / amount, or None if absent.
    panel_current  True only if the panel file was rewritten after the close of
                   the session following D; only then can "neither lists D" be 0.0.
    panel_note     how the panel was judged (write time, last ex-date), for the row.
    events         {symbol: [{"id", "kind", "amount"}]}, the Alpaca events used.
    """
    alp: dict[str, list] = {}
    for e in alpaca_events:
        if e["ex_date"] == day:
            alp.setdefault(e["symbol"], []).append(e)
    pan: dict[str, list] = {}
    covered: set = set()          # names the panel has any row for (module docstring)
    if panel is not None:
        covered = set(panel["ticker"])
        for sym, ex, amt in zip(panel["ticker"], panel["ex_date"], panel["amount"]):
            if hasattr(ex, "date"):
                ex = ex.date()
            if ex == day and float(amt) > 0:
                pan.setdefault(sym, []).append(float(amt))

    per_share, gaps, notes, events = {}, {}, {}, {}
    for sym in sorted(set(symbols)):
        a, p = alp.get(sym), pan.get(sym)
        events[sym] = [{"id": e["id"], "kind": e["kind"], "amount": float(e["amount"])}
                       for e in (a or [])]
        if a and p:
            sa, sp = sum(float(e["amount"]) for e in a), sum(p)
            tol = ROUNDING_TOL * max(len(a), len(p))
            if abs(sa - sp) <= tol + 1e-12:
                per_share[sym] = sa
                notes[sym] = f"Alpaca {sa:g} (panel {sp:g}, within rounding {tol:g}); Alpaca used"
            else:
                gaps[sym] = (f"sources disagree on ex {day}: Alpaca {sa:g}, yfinance panel "
                             f"{sp:g}; not averaged")
        elif a:
            sa = sum(float(e["amount"]) for e in a)
            per_share[sym] = sa
            notes[sym] = f"Alpaca {sa:g}; the panel does not list ex {day} ({panel_note})"
        elif p:
            gaps[sym] = (f"the yfinance panel lists ex {day} at {sum(p):g} but Alpaca lists "
                         f"none; Alpaca's silence is not a zero")
        elif panel_current and sym in covered:
            per_share[sym] = 0.0
            notes[sym] = f"none listed for ex {day} by Alpaca or the panel ({panel_note})"
        elif panel_current:
            gaps[sym] = (f"Alpaca lists none for ex {day} and the yfinance panel has no rows "
                         f"for {sym} at all (an empty fetch, or a name outside its universe), "
                         f"so only one source is silent; not a zero")
        else:
            gaps[sym] = (f"Alpaca lists none for ex {day} and the panel is not yet current "
                         f"({panel_note}); retried on a later run")
    return per_share, gaps, notes, events


# ------------------------------------------------------------------ inputs

def _session_close_utc(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, SESSION_CLOSE, ET).astimezone(dt.timezone.utc)


def load_panel(panel_path: Path):
    """(DataFrame or None, written_at_utc or None, last ex_date or None)."""
    if not panel_path.exists():
        return None, None, None
    import pandas as pd
    df = pd.read_parquet(panel_path, columns=["ticker", "ex_date", "amount"])
    written = dt.datetime.fromtimestamp(panel_path.stat().st_mtime, dt.timezone.utc)
    last = pd.to_datetime(df["ex_date"]).max() if len(df) else None
    return df, written, (last.date() if last is not None and not pd.isna(last) else None)


def panel_judgement(day: dt.date, written: dt.datetime | None, last_ex: dt.date | None,
                    next_session: dt.date) -> tuple[bool, str]:
    """(current, note). Current only if rewritten after the close of the session after D."""
    if written is None:
        return False, "panel absent"
    need = _session_close_utc(next_session)
    note = (f"panel written {written.isoformat(timespec='seconds')}, last ex-date "
            f"{last_ex}; needs a write after {need.isoformat(timespec='seconds')}")
    return written >= need, note


def held_for(state_dir: Path, day: dt.date) -> dict:
    """verify's `held_into_close` for D, from <state>/<D>/reconcile.json."""
    p = state_dir / day.isoformat() / "reconcile.json"
    if not p.exists():
        raise DistError(f"no {day}/reconcile.json: verify did not record the book held into {day}")
    rec = json.loads(p.read_text())
    if "held_into_close" not in rec:
        raise DistError(f"{day}/reconcile.json has no held_into_close (verify did not reach scoring)")
    held = rec["held_into_close"]
    if not isinstance(held, dict):
        raise DistError(f"{day}/reconcile.json held_into_close is not an object")
    return {str(k): v for k, v in held.items()}


def auction_pnl_for(state_dir: Path, day: dt.date) -> float | None:
    """D's auction_pnl_usd from scores.csv: a float, or None when UNMEASURED.

    verify may be re-run, so D can have several rows. Two different measured
    values raise naming both: neither is picked. An UNMEASURED row beside a
    measured one is a run that could not mark the auction (a re-run on D's
    evening before the print, a `--condition 6` re-run); it contradicts nothing,
    so the measured value stands. Until 2026-10-11 the pair counted as a
    disagreement: the whole day became an error row, including a distribution
    P&L that was measurable, and scores.csv is append-only, so the identical
    retry failed for every remaining session of the lookback (review 2026-10-11).
    """
    p = state_dir / "scores.csv"
    if not p.exists():
        raise DistError("no scores.csv")
    with p.open(newline="") as fh:
        vals = [r["auction_pnl_usd"] for r in csv.DictReader(fh) if r.get("date") == day.isoformat()]
    if not vals:
        raise DistError(f"scores.csv has no row for {day}")
    distinct = sorted(set(vals) - {UNMEASURED})
    if len(distinct) > 1:
        raise DistError(f"scores.csv rows for {day} disagree on auction_pnl_usd: {distinct}")
    if not distinct:
        return None
    v = distinct[0]
    try:
        x = float(v)
    except ValueError:
        raise DistError(f"scores.csv auction_pnl_usd for {day} = {v!r} is not a number") from None
    if not math.isfinite(x):
        raise DistError(f"scores.csv auction_pnl_usd for {day} = {v!r} is not finite")
    return x


# ------------------------------------------------------------------ records

def _fmt(x) -> str:
    return UNMEASURED if x is None else f"{x:.2f}"


def _read_rows(path: Path) -> list:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="") as fh:
        rd = csv.DictReader(fh)
        if tuple(rd.fieldnames or ()) != COLUMNS:
            raise DistError(f"{path} header {rd.fieldnames} is not {list(COLUMNS)}")
        return list(rd)


def measured_days(path: Path) -> set:
    return {r["date"] for r in _read_rows(path) if r["distribution_pnl_usd"] != UNMEASURED}


def upsert(path: Path, row: dict) -> None:
    """Replace D's row (or add it), one row per D, sorted. Temp file, fsync, rename.
    A MEASURED row is never replaced: refuse, since that is a caller bug."""
    rows = _read_rows(path)
    for r in rows:
        if r["date"] == row["date"] and r["distribution_pnl_usd"] != UNMEASURED:
            raise DistError(f"{row['date']} already has a measured row; not replaced")
    rows = [r for r in rows if r["date"] != row["date"]] + [{k: row[k] for k in COLUMNS}]
    rows.sort(key=lambda r: r["date"])
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _error_row(day: dt.date, err: str, now_utc: dt.datetime) -> dict:
    return {"date": day.isoformat(), "auction_pnl_usd": "", "distribution_pnl_usd": UNMEASURED,
            "auction_pnl_with_distributions_usd": UNMEASURED,
            "unmeasured": f"distribution score error: {err}", "per_symbol_json": "",
            "source": "", "label": LABEL, "written_at_utc": now_utc.isoformat()}


# ------------------------------------------------------------------ the run

def score_one(client, state_dir: Path, day: dt.date, *, next_session: dt.date,
              now_utc: dt.datetime, panel_path: Path = DEFAULT_PANEL) -> dict:
    """The row for D (measured or UNMEASURED). Raises DistError if an input is missing."""
    held = held_for(state_dir, day)
    auction_pnl = auction_pnl_for(state_dir, day)
    if held:
        alpaca = client.distributions(sorted(held), day - dt.timedelta(days=QUERY_DAYS),
                                      day + dt.timedelta(days=QUERY_DAYS))
        panel, written, last_ex = load_panel(panel_path)
        current, pnote = panel_judgement(day, written, last_ex, next_session)
        per_share, gaps, notes, events = resolve(held, day, alpaca, panel,
                                                 panel_current=current, panel_note=pnote)
        pnl, rows, unmeasured = score(held, per_share, gaps)
        for r in rows:
            r["source"] = notes.get(r["symbol"], gaps.get(r["symbol"], ""))
            r["alpaca_events"] = events.get(r["symbol"], [])
        source = f"Alpaca corporate actions (read {now_utc.isoformat()}); {pnote}"
    else:
        pnl, rows, unmeasured = 0.0, [], []
        source = "no positions held into D: nothing is entitled"
    combined = None if (pnl is None or auction_pnl is None) else auction_pnl + pnl
    return {"date": day.isoformat(), "auction_pnl_usd": _fmt(auction_pnl),
            "distribution_pnl_usd": _fmt(pnl),
            "auction_pnl_with_distributions_usd": _fmt(combined),
            "unmeasured": " | ".join(unmeasured),
            "per_symbol_json": json.dumps(rows, sort_keys=True, separators=(",", ":")),
            "source": source, "label": LABEL, "written_at_utc": now_utc.isoformat()}


def due_days(today: dt.date, *, previous_trading_day) -> list:
    """Sessions at least LAG_SESSIONS before `today` and at most LOOKBACK_SESSIONS back,
    oldest first. `today` itself is a session or not; only completed sessions count."""
    days, d = [], today
    for _ in range(LAG_SESSIONS):
        d = previous_trading_day(d)
    for _ in range(LOOKBACK_SESSIONS - LAG_SESSIONS + 1):
        days.append(d)
        d = previous_trading_day(d)
    return sorted(days)


def run_pending(client, state_dir: Path, today: dt.date, *, now_utc: dt.datetime,
                previous_trading_day, next_trading_day,
                panel_path: Path = DEFAULT_PANEL) -> list:
    """Score every due session that has no measured row. Returns [(date, status)]."""
    path = state_dir / "distribution_scores.csv"
    done = measured_days(path)
    out = []
    for day in due_days(today, previous_trading_day=previous_trading_day):
        if day.isoformat() in done:
            continue
        if not (state_dir / day.isoformat()).is_dir():
            continue          # no session folder at all: nothing was verified that day
        try:
            row = score_one(client, state_dir, day, next_session=next_trading_day(day),
                            now_utc=now_utc, panel_path=panel_path)
        except Exception as e:  # noqa: BLE001 -- recorded as an UNMEASURED row naming it
            row = _error_row(day, f"{type(e).__name__}: {e}", now_utc)
        upsert(path, row)
        out.append((day, row["distribution_pnl_usd"]))
    return out
