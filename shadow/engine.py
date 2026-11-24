"""Decide and mark a shadow book. Every figure this writes is SIMULATED.

THE CONVENTION (the harness's shift(2), on live data)
-----------------------------------------------------
    decide on D   targets = signal(D, panels truncated to rows dated <= D)
    fill on F(D)  the first session after D, at its close
    earn          from F(D)'s close onward, until a later decision fills

So the book held over the return from session P to the next session S is the latest
ON-TIME decision whose fill session is <= P. With one decision a day that is the
decision made the session before P: `H.shift(2)` in `scripts/research/harness.py`.
Weights are fractions of a constant notional (no compounding), so a day's P&L is
    notional * sum_i w_i * (close_S[i] * split_S[i] / close_P[i] - 1)
and the total-return line adds notional * sum_i w_i * dividend_S[i] / close_P[i]
(a distribution credits a long and charges a short on its ex-date S).

THE RULE THAT KEEPS IT A FORWARD TEST: ON TIME, OR NOT SCORED
-------------------------------------------------------------
A decision counts only if it was written before the session it fills in could have
closed: before 13:00 New York time on F(D), the earliest close the exchange keeps (an
early-close day), so no calendar of early closes is needed and the rule is never
lenient. A decision written later is stored, labelled LATE, and never scored. Without
this, a machine that was off for a week would "decide" seven days in hindsight and the
shadow record would quietly become a backtest. The clock is this machine's, which is
why the runner belongs on a machine that is always on.

NO LOOKAHEAD BY CONSTRUCTION
----------------------------
The signal never sees a panel file. The engine reads each panel and removes every row
dated after the as-of date before the signal is called, and a test checks that deleting
later rows from the files leaves the decision unchanged. A panel whose rows are dated by
something other than when they became known (a period end, a revised macro series) is
the signal author's to lag: the data card says how (docs/MISSION.md section 5).

NOTHING STANDS IN FOR MISSING DATA
----------------------------------
  * A required panel with no row dated as-of: the book does not decide. The reason goes
    to `unmeasured.csv`, and the morning run may try again.
  * A held name with no close on P or S: that session is UNMEASURED, naming the names.
    No other price is used, and the book still advances.
  * A one-session price move beyond SPLIT_GUARD on a held name, with no `split` column
    saying why: UNMEASURED, naming it. Marks on raw prices cannot tell a split from a
    crash, and booking either wrongly is a confident wrong number (the IGR bars,
    results/cef/DATA_GUARDS_2026-10-19.md).

State, all under SHADOW_STATE_DIR/<slug>/: `decisions/<asof>.json` (written once, never
rewritten), `scores.csv` (append-only, one row per session), `unmeasured.csv`.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from .book import Book

REPO = Path(__file__).resolve().parents[1]
NY = ZoneInfo("America/New_York")
ON_TIME_CUTOFF = dt.time(13, 0)   # the earliest NYSE close (an early-close day)
SPLIT_GUARD = 0.40                # a one-session move beyond this needs a `split` row to explain it
LABEL = "SIMULATED"
SCORE_FIELDS = ("date", "prev", "status", "pnl_price_usd", "pnl_total_usd", "gross", "net",
                "n_names", "turnover", "decision_asof", "detail", "label")


class ShadowError(RuntimeError):
    """The engine refused, naming what was wrong."""


class Unmeasured(ShadowError):
    """A book could not decide because data was missing or stale. Not a crash: recorded."""


# ------------------------------------------------------------------ state

def state_dir(environ=None) -> Path:
    """SHADOW_STATE_DIR, required. No default: a default would be a place nobody chose,
    and under `data/` it could be the panels prod decides on (CLAUDE.md landmine 9)."""
    env = os.environ if environ is None else environ
    raw = env.get("SHADOW_STATE_DIR", "")
    if not raw:
        raise ShadowError("SHADOW_STATE_DIR is not set: it must name the shadow state directory")
    p = Path(raw).expanduser().resolve()
    data = (REPO / "data").resolve()
    if p == data or data in p.parents:
        raise ShadowError(f"refusing state directory {p}: it is inside {data}, which prod decides on")
    return p


def _book_dir(state: Path, book: Book) -> Path:
    d = state / book.slug
    (d / "decisions").mkdir(parents=True, exist_ok=True)
    return d


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _commit() -> str:
    """The code commit a decision was made at, for the record. UNMEASURED if git cannot
    say: it is provenance, and a decision does not depend on it."""
    try:
        out = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as e:
        return f"UNMEASURED ({type(e).__name__})"
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else "UNMEASURED (git)"


# ------------------------------------------------------------------ decide

def load_panels(book: Book, state: Path, asof: dt.date) -> tuple[dict, dict]:
    """Each panel, with every row dated after `asof` removed, and each file's sha256.
    Raises Unmeasured if a file is missing or a required panel has no row dated asof."""
    frames, hashes = {}, {}
    for p in book.panels:
        path = state / "panels" / p.path
        if not path.exists():
            raise Unmeasured(f"panel {p.name}: {path} does not exist")
        df = pd.read_parquet(path)
        if p.date_col not in df.columns:
            raise ShadowError(f"panel {p.name}: no column {p.date_col!r} in {path}")
        dates = pd.to_datetime(df[p.date_col]).dt.date
        # ALIGNMENT: the signal for asof sees rows dated <= asof and nothing later.
        kept = df.loc[dates <= asof].copy()
        assert kept.empty or pd.to_datetime(kept[p.date_col]).dt.date.max() <= asof
        if p.required_asof:
            last = dates[dates <= asof].max() if (dates <= asof).any() else None
            if last != asof:
                raise Unmeasured(f"panel {p.name} ends {last}, not {asof}")
        frames[p.name] = kept
        hashes[p.name] = _sha256(path)
    return frames, hashes


def _clean_weights(book: Book, w) -> dict:
    if not isinstance(w, pd.Series):
        raise ShadowError(f"{book.slug}: the signal must return a pandas Series of weights by symbol")
    if w.index.has_duplicates:
        raise ShadowError(f"{book.slug}: duplicate symbols in the signal's weights")
    out = {}
    for sym, v in w.items():
        if not isinstance(sym, str) or not sym:
            raise ShadowError(f"{book.slug}: symbol {sym!r} is not a non-empty string")
        v = float(v)
        if not math.isfinite(v):
            raise ShadowError(f"{book.slug}: weight for {sym} is {v}; a signal must not return NaN or inf")
        if v != 0.0:
            out[sym] = v
    return dict(sorted(out.items()))


def decide(book: Book, state: Path, asof: dt.date, *, now: dt.datetime | None = None) -> dict:
    """Write the decision for `asof` once. Returns {"status": DECIDED | EXISTS | UNMEASURED, ...}."""
    if asof < book.started:
        raise ShadowError(f"{book.slug}: {asof} is before the book started ({book.started})")
    d = _book_dir(state, book)
    path = d / "decisions" / f"{asof.isoformat()}.json"
    if path.exists():
        return {"status": "EXISTS", "path": str(path)}
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ShadowError("now must be timezone-aware")
    try:
        frames, hashes = load_panels(book, state, asof)
    except Unmeasured as e:
        _append(d / "unmeasured.csv", ("asof", "seen_at", "reason"),
                {"asof": asof.isoformat(), "seen_at": now.isoformat(), "reason": str(e)})
        return {"status": "UNMEASURED", "reason": str(e)}
    weights = _clean_weights(book, book.signal_fn()(asof, frames))
    rec = {"slug": book.slug, "asof": asof.isoformat(), "written_at": now.astimezone(dt.timezone.utc).isoformat(),
           "fill": book.fill, "notional_usd": book.notional_usd, "weights": weights,
           "panel_sha256": hashes, "commit": _commit(), "label": LABEL}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=1, sort_keys=True))
    os.replace(tmp, path)     # written once: the EXISTS branch above never reaches here again
    return {"status": "DECIDED", "path": str(path), "n_names": len(weights)}


# ------------------------------------------------------------------ mark

def _decisions(d: Path) -> list[dict]:
    out = []
    for p in sorted((d / "decisions").glob("*.json")):
        rec = json.loads(p.read_text())
        rec["_asof"] = dt.date.fromisoformat(rec["asof"])
        rec["_written"] = dt.datetime.fromisoformat(rec["written_at"])
        out.append(rec)
    return out


def fill_session(asof: dt.date, sessions: list[dt.date]) -> dt.date | None:
    """The first session after `asof`, or None if the marks do not reach it yet."""
    return next((s for s in sessions if s > asof), None)


def on_time(rec: dict, fill: dt.date) -> bool:
    """Written before 13:00 New York on the fill session (module docstring)."""
    cutoff = dt.datetime.combine(fill, ON_TIME_CUTOFF, tzinfo=NY)
    return rec["_written"] < cutoff


def _marks_wide(marks: pd.DataFrame) -> dict:
    need = {"date", "symbol", "close"}
    if not need <= set(marks.columns):
        raise ShadowError(f"marks need columns {sorted(need)}; got {sorted(marks.columns)}")
    m = marks.copy()
    m["date"] = pd.to_datetime(m["date"]).dt.date
    if m.duplicated(["date", "symbol"]).any():
        raise ShadowError("marks hold two rows for one (date, symbol)")
    wide = {"close": m.pivot(index="date", columns="symbol", values="close")}
    for col in ("dividend", "split"):
        wide[col] = m.pivot(index="date", columns="symbol", values=col) if col in m.columns else None
    return wide


def _append(path: Path, fields, row: dict) -> None:
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields))
        if new:
            w.writeheader()
        w.writerow(row)


def mark(book: Book, state: Path, marks: pd.DataFrame) -> list[dict]:
    """Score every session the marks hold that this book has not scored yet. Returns the
    new rows. Sessions are the marks' own dates: a day with no mark is not a session."""
    d = _book_dir(state, book)
    wide = _marks_wide(marks)
    sessions = sorted(wide["close"].index)
    scores = d / "scores.csv"
    done = set()
    if scores.exists():
        done = {dt.date.fromisoformat(r["date"]) for r in csv.DictReader(open(scores))}
    recs = _decisions(d)
    fills = []                                   # (fill session, decision), on-time only
    for r in recs:
        f = fill_session(r["_asof"], sessions)
        if f is not None and on_time(r, f):
            fills.append((f, r))
    rows = []
    for prev, day in zip(sessions, sessions[1:]):
        if day <= book.started or day in done:
            continue
        if done and day < max(done):
            raise ShadowError(f"{book.slug}: session {day} is unscored but later sessions are scored; "
                              "scores.csv is append-only and is not back-filled")
        live = [(f, r) for f, r in fills if f <= prev]
        held = max(live, key=lambda fr: (fr[0], fr[1]["_asof"]))[1] if live else None
        w = held["weights"] if held else {}
        # turnover booked on the session a decision fills in
        todays = [r for f, r in fills if f == day]
        turnover = None
        if todays:
            new = max(todays, key=lambda r: r["_asof"])["weights"]
            turnover = sum(abs(new.get(s, 0.0) - w.get(s, 0.0)) for s in set(new) | set(w))
        row = {"date": day.isoformat(), "prev": prev.isoformat(), "status": "FLAT", "pnl_price_usd": 0.0,
               "pnl_total_usd": 0.0, "gross": sum(abs(v) for v in w.values()), "net": sum(w.values()),
               "n_names": len(w), "turnover": "" if turnover is None else round(turnover, 6),
               "decision_asof": held["asof"] if held else "", "detail": "", "label": LABEL}
        if w:
            row.update(_score(book, wide, w, prev, day))
        _append(scores, SCORE_FIELDS, row)
        done.add(day)
        rows.append(row)
    return rows


def _score(book: Book, wide: dict, w: dict, prev: dt.date, day: dt.date) -> dict:
    close = wide["close"]
    missing = [s for s in w if s not in close.columns
               or pd.isna(close.at[prev, s]) or pd.isna(close.at[day, s])]
    if missing:
        return {"status": "UNMEASURED", "pnl_price_usd": "", "pnl_total_usd": "",
                "detail": f"no close on {prev} or {day} for {sorted(missing)}"}
    pnl_p, pnl_t, unexplained = 0.0, 0.0, []
    div_ok = wide["dividend"] is not None
    for s, wt in w.items():
        ratio = 1.0
        if wide["split"] is not None and not pd.isna(wide["split"].at[day, s]):
            ratio = float(wide["split"].at[day, s])
        ret = float(close.at[day, s]) * ratio / float(close.at[prev, s]) - 1.0
        if abs(ret) > SPLIT_GUARD and ratio == 1.0:
            unexplained.append(s)
        pnl_p += wt * ret
        if div_ok:
            dv = wide["dividend"].at[day, s]
            pnl_t += wt * (ret + (0.0 if pd.isna(dv) else float(dv)) / float(close.at[prev, s]))
    if unexplained:
        return {"status": "UNMEASURED", "pnl_price_usd": "", "pnl_total_usd": "",
                "detail": f"one-session move beyond {SPLIT_GUARD:.0%} with no split row: {sorted(unexplained)}"}
    return {"status": "SCORED", "pnl_price_usd": round(pnl_p * book.notional_usd, 2),
            # no dividend column: the total-return line is a stated gap, never the price line
            "pnl_total_usd": round(pnl_t * book.notional_usd, 2) if div_ok else "",
            "detail": "" if div_ok else "total return UNMEASURED: marks carry no dividend column"}


def late_decisions(book: Book, state: Path, sessions: list[dt.date]) -> list[str]:
    """As-of dates whose decision was written too late to count (reported, never scored)."""
    out = []
    for r in _decisions(_book_dir(state, book)):
        f = fill_session(r["_asof"], sessions)
        if f is not None and not on_time(r, f):
            out.append(r["asof"])
    return out
