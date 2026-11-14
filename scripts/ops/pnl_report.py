"""The daily P&L attribution and factor exposure report for one paper book (report only).

    python3 -m scripts.ops.pnl_report --book cef [--state-dir DIR] [--asof YYYY-MM-DD]

WHY THIS EXISTS (team lead, 2026-11-09)
---------------------------------------
Each book's P&L was explained by hand, session by session, from a laptop cache (the
10-30 loss that turned out to be muni NAVs under two shorts, `scripts/cef/
live_attribution.py`). The team lead ordered it as a daily VM job for BOTH paper books,
the core and C4: official P&L, hold split into NAV part and discount part, fill cost,
fees and distributions, then factor exposure against the review line. This is that job.
It runs on a timer (20:30 ET core, 20:35 ET C4), after the 20:00 EOD stamp and clear of
the 21:40 collect, through `install_vm --reports` (kind `pnl`, docs/RUNBOOK.md 8.12).

WHAT IT IS AND IS NOT
---------------------
A WRAPPER AND A READER. Every number is computed by `scripts/cef/live_attribution.py` and
`scripts/cef/exposure_readout.py` (imported, their rules unchanged) from the account's own
fills and Alpaca's EOD history; this module joins them into one report and writes
`<state>/reports/pnl/<asof>.{md,json}` (the JSON is what `risk_daily` reads) and nothing
outside that directory: its fetch cache is `_cache` there, yfinance's own SQLite caches are
kept in `_yf_cache` there (`_keep_yfinance_cache_under`), and a directory under data/ or
visible to git is refused before anything is read (`LA._refuse_data_dir`,
`LA._refuse_git_visible`), because the report holds the account's equity and P&L and this
repository is public. It holds no order code, no broker client and no key file: the
account is read through
`scripts/ops/alpaca_read.py` (HTTP GET only, keys from the process environment, which
systemd loads from the tmpfs file the secret service wrote). No import path reaches
order-sending code (scripts/ops/tests/test_report_no_order_path.py pins it).

REPORT ONLY. A breach of a factor review line appears in the report and sends NOTHING: this
module never pushes, never sets ACT, never calls `report_notify`, never halts or trades.
Report-only, zero trials, no counter moved.

WHAT IT REPORTS (per book)
--------------------------
One section for the session just closed and one cumulative from the book's first trade
(derived from the account's fills, never a date written here): official P&L (Alpaca EOD
history, the P&L of record, docs/SYSTEM.md section 5), hold split into NAV part and
discount part, fill cost, fees, distributions, then factor exposure at the last close
against the review line (REVIEW_FRACTION x vol_target_annual x sizing_multiplier, each from
the book's own spec; the multiplier since the team lead's ruling of 2026-11-10, because the
account holds m x the unit book and the readout measures the account) with the line's three
inputs printed beside it, the headline first and the by-family (C4) or muni/taxable (core)
split.

THE RECONCILIATION IS STILL THE POINT. Every session's rebuild (hold + fill + fees) must
equal the official EOD change to the cent. If it does not, the report says so loudly: the
overall status is UNRECONCILED, in the report's headline and on the job's stdout line, not
OK, with the line that names the session and the residual at the top; the JSON's
`reconciled` is false, and `risk_daily` shows WATCH; the attribution rows still print, for
diagnosis, and are labelled unreconciled. Since the team lead's ruling of 2026-11-10 the unit
also exits EXIT_UNRECONCILED (5), a failed unit, AFTER the report files are written (EXIT
CODES, below); before it the code was 0.

EXIT CODES (team lead, 2026-11-10; docs/RUNBOOK.md 8.12)
  0  EXIT_OK: the attribution ran and reconciled to the cent on every session. The factor
     block may still be PARTIAL or UNMEASURED: a factor gap costs only its own block.
  2  EXIT_REFUSED: refused before anything was read or written (no --state-dir and no
     QUANTT_STATE_DIR, or a state directory under data/ or visible to git).
  4  EXIT_INCOMPLETE: no broker read (no key, a failed read) or the attribution refused;
     the report says UNMEASURED and names why.
  5  EXIT_UNRECONCILED: the attribution ran, and on at least one session the rebuild
     (hold + fill + fees) does not equal Alpaca's official EOD change to the cent; the
     report's status is UNRECONCILED.
  A run that is both incomplete and unreconciled exits 4: with no broker read or a refused
  attribution nothing was reconciled, so the reconciliation is unknown, never "failed".
  1  is Python's own, an uncaught exception: a bug, and the report may not be written.
The report files are written before the process exits, whatever the code, so `risk_daily`
(its own timer, no dependency on this unit) reads the same JSON after a 4 or a 5 as after a
0. The rendered unit carries no SuccessExitStatus (install_vm's expected_report_service
admits none), so 4 and 5 both show as a failed unit in `systemctl`.

A MISSING INPUT IS UNMEASURED, NAMED, NEVER INFERRED (CLAUDE.md, no silent fallbacks).
  * no broker key, a failed broker read, or an attribution refusal: the report says
    UNMEASURED naming it and the unit exits non-zero (EXIT_INCOMPLETE), so a dead job is a
    failed unit, never a quiet green one. Its failure touches nothing else (no lock, no
    write under data/ or the clone, nothing another unit needs).
  * a fund's NAV not yet published at 20:30: the NAV/discount split is UNMEASURED for that
    name-day, named; hold, fill, fees and the reconciliation do not need NAV and stay
    complete; a cumulative NAV or discount part covers only sessions with every NAV, and
    says so. Each book's NAV symbols are its own (`live_attribution.nav_symbols`; C4's come
    from the committed map, 15 of its 74 funds not being on the core's X rule), so a gap
    here is a NAV the vendor has not served, never a symbol the wrong book's rule invented.
  * a distribution that cannot be resolved (the second source not current until the next
    session closes, `dist_score`): UNMEASURED, never zero.
  * a session with a modelled fee and no FEE row yet: "no FEE row yet (UNMEASURED)" in the
    fee check, never a measured 0.00 (the account's FEE rows post later than the trade date:
    `live_attribution`, FEES).
  * a held name without a same-day price (yfinance has not served it by 20:30; HYT lags,
    CLAUDE.md landmine 6) or without any price history: the factor block is PARTIAL, not
    UNMEASURED (team lead, 2026-11-10). It reads every other held name, names each one left
    out with the reason and their share of the book's gross, and labels every reading and
    REVIEW flag PARTIAL (`build_factor`). A factor ETF without its price, or no held name
    with its inputs: UNMEASURED, naming it. The attribution above it is unaffected either way.
    PARTIAL is about the as-of close only (independent review of PR #82, 2026-11-11): a name
    left out on an earlier date alone is a named note in the block's history, and the block
    is OK, because the job re-reads from the first trade every night and a fund yfinance no
    longer serves (merged, renamed) would otherwise keep every later night PARTIAL.
  * a book that holds nothing at the as-of close: the factor block is FLAT (independent
    review of PR #82, 2026-11-11). Nothing is held, so nothing is exposed; the block reads no
    exposure, no flag and no PARTIAL for that close, and never shows an earlier close's
    reading as the as-of one. FLAT is read only from a rebuild that reconciles: an
    unreconciled one makes the block UNMEASURED, naming why (team lead, 2026-11-11;
    `build_factor`), and risk_daily cross-checks every FLAT against the collector's account
    record for that close. Its history since the first trade is labelled with its dates;
    a history with no reading for a named reason is an UNMEASURED line in the FLAT block, and
    a bug, a LookaheadError or a failed price fetch while reading it makes the whole block
    UNMEASURED, as on a held night (second review of PR #82, 2026-11-11; `_factor_flat`).
  * a book whose Dimson lag rule has no answer: the factor block says UNMEASURED and why.

NO LOOKAHEAD (H7). The attribution uses fills and closes of the sessions it reports, the
factor exposure's betas come from the sessions strictly before each date
(`exposure_readout.window_rows` asserts it), and nothing here estimates anything.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.cef import exposure_readout as ER           # noqa: E402  (no order code; keyless yfinance only)
from scripts.cef import live_attribution as LA           # noqa: E402  (no order code)
from scripts.ops import alpaca_read as AR                # noqa: E402  (GET only)
from scripts.ops.data_qa import ET, expected_day, write_atomic  # noqa: E402

BOOKS = ("cef", "c4")
EXIT_OK = 0
EXIT_REFUSED = 2                   # refused before reading or writing anything (main)
EXIT_INCOMPLETE = 4                # no broker read or the attribution refused: the unit fails, the file says why
EXIT_UNRECONCILED = 5              # the rebuild missed the official EOD change on a session (team lead, 2026-11-10)
RESIDUAL_CENT = Fraction(1, 200)   # half a cent: "to the cent" per session (live_attribution's residual)
EOD_LOOKBACK_DAYS = 1100           # far enough back to reach any account's funding date
SINCE_PAD_DAYS = 7                 # sessions before the first funded point, so fetch can show it was flat
UNMEASURED = "UNMEASURED"
UNRECONCILED = "UNRECONCILED"      # an overall status: the rebuild missed the official change on a session
FLAT = "FLAT"                      # a factor-block status: nothing held at the as-of close (`_factor_flat`)


def _usd(x) -> str:
    return "UNMEASURED" if x is None else f"{float(x):+,.2f}"


# ---------------------------------------------------------------- the attribution

def session_row(res, d: dt.date) -> dict:
    """The daily row of session d, money as floats, UNMEASURED cells None."""
    r = res.daily[res.daily["date"] == d].iloc[0]
    out = {"date": d.isoformat()}
    for k in ("eod_change", "hold", "nav_part", "disc_part", "fill", "fees", "dist", "traded_usd", "sold_usd",
              "rebuilt", "residual", "eod_equity"):
        out[k] = None if r[k] is None else float(r[k])
    return out


def cumulative(res, first: dt.date) -> dict:
    """Totals over sessions from the first trade. A NAV or discount part is summed over the
    sessions that have every name-day measured, and says how many; distributions the same
    way; hold, fill, fees and the official change are always complete."""
    d = res.daily[res.daily["date"] >= first]
    def total(col):
        vals = list(d[col])
        known = [v for v in vals if v is not None]
        return (float(sum(known, Fraction(0))) if known else None,
                [dd.isoformat() for dd, v in zip(d["date"], vals) if v is None])
    out: dict = {"first_trade": first.isoformat(), "sessions": int(len(d)), "unmeasured": {}}
    for k in ("eod_change", "hold", "fill", "fees", "rebuilt", "residual", "traded_usd", "sold_usd"):
        out[k] = total(k)[0]
    for k in ("nav_part", "disc_part", "dist"):
        v, miss = total(k)
        out[k] = v
        out["unmeasured"][k] = miss
    out["hold_on_split_sessions"] = None if out["nav_part"] is None else out["nav_part"] + out["disc_part"]
    return out


def reconciliation(res, first: dt.date) -> dict:
    """Every session's residual against the official change, to the cent. An unreconciled
    session is named; the attribution is still shown for diagnosis, labelled."""
    bad = []
    for r in res.daily[res.daily["date"] >= first].itertuples():
        if abs(Fraction(r.residual)) > RESIDUAL_CENT:
            bad.append((r.date.isoformat(), float(r.residual)))
    max_res = max((abs(float(r)) for r in res.daily[res.daily["date"] >= first]["residual"]), default=0.0)
    lines = []
    if bad:
        lines.append(f"RECONCILIATION FAILED on {len(bad)} session(s): " +
                     ", ".join(f"{d} residual {v:+.2f}" for d, v in bad[:10]) +
                     (" ..." if len(bad) > 10 else "") +
                     ". The rebuild (hold + fill + fees) does not equal Alpaca's EOD change to the cent; "
                     "the figures below are unreconciled for those sessions.")
    return {"reconciled": not bad, "failed_sessions": bad, "max_abs_residual": max_res, "lines": lines}


def fee_check(res, reader, first: dt.date) -> list[str]:
    """The FEE activities against the modelled fees, per session from the first trade
    (FEES in live_attribution's docstring). A read failure or a row without the fields
    needed is UNMEASURED and named; it never changes the fees line."""
    try:
        rows = reader.fee_activities()
    except Exception as e:                  # the check is auxiliary; the line it checks stands
        return [f"FEE activity check UNMEASURED: {type(e).__name__}: {e}"]
    per: dict = {}
    for r in rows:
        day, amt = r.get("date"), r.get("net_amount")
        if not day or amt is None:
            return [f"FEE activity check UNMEASURED: row {r.get('id')} has no date or net_amount"]
        try:
            per[str(day)[:10]] = per.get(str(day)[:10], 0.0) + float(amt)
        except (TypeError, ValueError):
            return [f"FEE activity check UNMEASURED: row {r.get('id')} net_amount {amt!r} is not a number"]
    model = {d.isoformat(): float(f) for d, f in zip(res.daily["date"], res.daily["fees"]) if d >= first}
    # A session with a modelled fee and no FEE row is unposted, not zero: the rows post after
    # the trade date (`live_attribution`, FEES: 10-30's were missing under until=10-31), and at
    # 20:30 the session just closed may simply not have them. A session with no modelled fee
    # and no row owes nothing, so it agrees.
    pending = [d for d, f in model.items() if d not in per and abs(f) >= 0.005]
    compared = [d for d in model if d not in pending]
    agree = [d for d in compared if abs(per.get(d, 0.0) - model[d]) < 0.005]
    worse = [f"{d} account {per.get(d, 0.0):+.2f} vs modelled {model[d]:+.2f}" for d in compared if d not in agree]
    line = f"FEE activities against the modelled fees: {len(agree)} of {len(compared)} session(s) agree to the cent"
    if worse:
        line += "; DIFFER on " + "; ".join(worse[:8]) + (" ..." if len(worse) > 8 else "")
    if pending:
        line += f"; no FEE row yet (UNMEASURED) on {', '.join(pending[:8])}" + (" ..." if len(pending) > 8 else "")
    return [line]


def positions_frame(res, inp, first: dt.date, last: dt.date) -> pd.DataFrame:
    """Signed shares at each session's close from the first trade on, with that session's
    official equity, for the factor readout: read from the attribution's rebuilt positions."""
    eq = dict(inp.eod)
    nd = res.name_day[(res.name_day["date"] >= first) & (res.name_day["date"] <= last)]
    rows = [dict(date=r.date.isoformat(), symbol=r.symbol, shares=float(r.q_end), equity=float(eq[r.date]))
            for r in nd.itertuples() if r.q_end != 0]
    return pd.DataFrame(rows, columns=["date", "symbol", "shares", "equity"])


def attribution_lines(sess: dict, cum: dict, recon: dict, *, session_note: str | None) -> list[str]:
    """The report's text for the attribution: session then cumulative. Every line is read by
    `risk_daily` as a report line; none may start with "ACT" (risk_daily's push keys on it),
    so each starts with the word it is about."""
    L = list(recon["lines"])
    if session_note:
        L.append(session_note)
    sp = lambda k: _usd(sess.get(k))
    L += [f"Session {sess['date']}: official (Alpaca EOD change) {sp('eod_change')}; "
          f"hold {sp('hold')} = NAV part {sp('nav_part')} + discount part {sp('disc_part')}; "
          f"fill {sp('fill')}; fees (modelled) {sp('fees')}; distributions not credited by paper "
          f"{sp('dist')}; rebuild vs official residual {sp('residual')}",
          f"Cumulative from the first trade ({cum['first_trade']}, {cum['sessions']} sessions): official "
          f"{_usd(cum['eod_change'])}; hold {_usd(cum['hold'])}; fill {_usd(cum['fill'])}; "
          f"fees {_usd(cum['fees'])}"]
    for k, label in (("nav_part", "NAV part"), ("disc_part", "discount part")):
        miss = cum["unmeasured"][k]
        L.append(f"{label} over sessions with every NAV: {_usd(cum[k])}"
                 + (f" (UNMEASURED on {len(miss)} session(s): {', '.join(miss[:5])}"
                    f"{' ...' if len(miss) > 5 else ''})" if miss else f" (all {cum['sessions']} sessions)"))
    miss = cum["unmeasured"]["dist"]
    L.append(f"Distributions not credited by paper, resolved sessions: {_usd(cum['dist'])}"
             + (f" (UNMEASURED on {len(miss)} session(s), not zero: {', '.join(miss[:5])}"
                f"{' ...' if len(miss) > 5 else ''})" if miss else ""))
    L.append(f"Reconciliation: {'every session to the cent' if recon['reconciled'] else 'FAILED (above)'}"
             f"; largest |residual| {recon['max_abs_residual']:.2f}")
    return L


def build_attribution(book: str, state: Path, asof: dt.date, reader, groups: dict, *,
                      now_utc: dt.datetime, nav_fetcher, dist_check_fetcher) -> dict:
    """Fetch through the injected reader, then attribute. Raises what `fetch` and `attribute`
    raise (a broker read, a refusal): the caller records it and fails the unit."""
    cache = state / "reports" / "pnl" / "_cache"
    points = reader.eod_equity_history(asof - dt.timedelta(days=EOD_LOOKBACK_DAYS), asof)
    if not points:
        raise AR.AlpacaReadError(f"no funded EOD point on or before {asof}")
    # Start a week before the first funded point, so `fetch` can show the account was flat.
    since = points[0].date - dt.timedelta(days=SINCE_PAD_DAYS)
    LA.fetch(cache, since=since, asof=asof, client=reader, nav_fetcher=nav_fetcher,
             dist_check_fetcher=dist_check_fetcher, now=now_utc, book=book)
    inp = LA.load_cache(cache, grp=dict(groups))
    eod_dates = [d for d, _ in inp.eod]
    eff = max(d for d in eod_dates if d <= asof)
    res = LA.attribute(inp, asof=eff, breaks=[], nav_missing="unmeasured")
    if not inp.fills:
        raise LA.AttributionError("the account has no FILL activity")
    first = min(f.date for f in inp.fills)        # the book's first trade: the account's own fills
    sess = session_row(res, eff)
    cum = cumulative(res, first)
    recon = reconciliation(res, first)
    note = None
    if eff != asof:
        note = (f"Session {asof}: Alpaca's EOD history has no point for it yet (latest {eff}); "
                f"the session section below is {eff}'s, not {asof}'s.")
    fees = fee_check(res, reader, first)
    lines = attribution_lines(sess, cum, recon, session_note=note) + fees
    return {"status": "OK", "session": sess, "cumulative": cum, "reconciled": recon["reconciled"],
            "reconciliation": recon, "fee_check": fees, "lines": lines, "first_trade": first.isoformat(),
            "effective_session": eff.isoformat(), "gaps": list(res.gaps),
            "_res": res, "_inp": inp}


# ---------------------------------------------------------------- the factor readout

def build_factor(book: str, res, inp, *, groups: dict, asof: dt.date, reconciled, price_fetcher=None,
                 now_utc: dt.datetime | None = None) -> dict:
    """Factor exposure against the review line, headline first, by family or muni/taxable.
    Exposures need each held name's price history (keyless yfinance). Never a default.

    PARTIAL, NOT UNMEASURED, FOR A HELD NAME WITHOUT ITS INPUTS (team lead, 2026-11-10). Until
    that ruling a held name yfinance had not served at 20:30 made the whole block UNMEASURED,
    because a book read without one of its names is a different book. Now the fetch keeps a
    late name's history (`fetch_each(partial=True)`) and `readout(partial=True)` reads each
    held name on every date it has every input for, leaving it out, named, where it does not
    (exposure_readout's module docstring, PARTIAL). The block is then PARTIAL: it lists each
    name left out at the last close with its reason and their share of the book's gross, and
    every reading and REVIEW flag on the partial book says PARTIAL. The share is read at the
    attribution's own closes (Alpaca's daily bars, the marks the rebuild reconciles to official
    equity), the one source here that has every held name's close on the date, so the
    numerator and denominator come from one source. The block stays UNMEASURED, as before,
    when a factor ETF has no price at the last close, or when on some date no held name has
    its inputs (there is no book to read).

    THE BLOCK IS READ AT THE ATTRIBUTION'S CLOSE, `res.asof`, AND AT NO OTHER (independent
    review of PR #82, 2026-11-11). `positions_frame` drops flat rows, so on a night the book
    holds nothing at that close the readout's last date is the previous HELD close. Before
    this review the block then printed that close's exposure and flags under status OK (a
    book flat on 2026-01-22 showed "MUNI ... REVIEW" read at 01-21, and risk_daily passed it
    as INFO), and when a name had also been left out on an earlier date the PARTIAL share
    was read against the as-of close's gross, 0, and raised, so the block said UNMEASURED
    with a ReadoutError. A flat close happens when a thin session flattens the core (the live
    sleeve flattens where the harness holds, E-2026-11-02-11). The backtest shows that often
    (E-2026-11-02-16, a backtest window, not the live record); the live book had not seen it
    as of 2026-11-02 ("There has been no thin session since 2026-09-28", E-2026-11-02-11).
    (Corrected on the second review of PR #82, 2026-11-11: this said "The core is flat on many
    thin sessions, so both were common", a backtest's frequency read as the live book's.) Now a
    book with no position at that close gets the FLAT block (`_factor_flat`): nothing to
    expose, no flag, no PARTIAL, its history labelled with its dates; and `_factor_report`
    refuses a readout whose last date is not that close.

    NEVER FLAT FROM A REBUILD THAT DOES NOT RECONCILE (team lead, 2026-11-11, on the second
    review of PR #82). FLAT is read from the fill rebuild alone (`res.name_day`'s positions at
    `res.asof`), so a closing fill the account never made (the review's phantom fill: the
    activities listed a sale of the whole book at the close, the equity series was built from
    the real fills) made the block FLAT and risk_daily INFO while the account held positions;
    the rebuild failed to reconcile that night, which was the only sign. `reconciled` is the
    attribution's own (`reconciliation`, every session from the first trade, to the cent), and
    anything but True means the rebuild's positions are not shown to be the account's: the
    block is then UNMEASURED, naming why, and no FLAT and no exposure is read. A held book on
    an unreconciled night is read as before (the report's overall status is UNRECONCILED, the
    loudest, either way). A rebuild that reconciles while its positions are still wrong (the
    review's contrived fill whose P&L cancels its modelled fees) is caught by risk_daily's
    cross-check of a FLAT against the collector's account record (`risk_daily.factor_block`)."""
    fs = ER.factor_set(book)
    first = min(f.date for f in inp.fills)
    last = dt.date.fromisoformat(res.asof.isoformat())
    P = positions_frame(res, inp, first, last)
    if not (P["date"] == last.isoformat()).any():  # nothing held at the as-of close: FLAT, never a prior reading
        if reconciled is not True:               # FLAT only from a rebuild shown to be the account's
            return _factor_unmeasured(
                f"the fill rebuild holds no position at the close of {last}, but it does not reconcile to "
                f"Alpaca's official EOD change (reconciled={reconciled!r}), so whether the book is flat at that "
                f"close cannot be read from it: no FLAT and no exposure is read (team lead, 2026-11-11)", fs)
        return _factor_flat(book, fs, P, groups=groups, first=first, last=last, asof=asof,
                            price_fetcher=price_fetcher)
    if fs.dimson_lags is None:
        return _factor_unmeasured(f"book {book} has no Dimson lag: its lag rule has not produced one "
                                  "(scripts/cef/exposure_readout.py, THE C4 LAG RULE)", fs)
    try:
        ro, failed = _read(fs, P, groups, first=first, asof=asof, price_fetcher=price_fetcher, etf_close_on=last)
    except _NotRead as e:
        return _factor_unmeasured(str(e), fs)
    return _factor_report(ro, fs, book, last, partial=partial_info(ro, res, failed, last),
                          excluded=exclusions(ro, failed))


class _NotRead(Exception):
    """A named reason the factor readout has no reading (a factor ETF without its price at the
    as-of close, no held name with its inputs, a book with no Dimson lag): the block's
    UNMEASURED line, or a flat block's history line. A bug is not one of these and propagates;
    nor does the runtime no-lookahead assertion (LookaheadError) or a failed price fetch, which
    make the whole block UNMEASURED on a flat night as on a held one (second review of PR #82,
    2026-11-11; `_factor_flat`)."""


def _read(fs: ER.FactorSet, P: pd.DataFrame, groups: dict, *, first: dt.date, asof: dt.date, price_fetcher,
          etf_close_on: dt.date | None):
    """Fetch every held name's and factor ETF's prices and read the partial readout on P.
    Returns (readout, the fetch's failures by ticker). `etf_close_on` is the close every factor
    ETF must have a price on (the as-of close of a held book); None for a flat book's history,
    whose dates are all earlier and whose ETF returns `readout` checks on every window."""
    tickers = sorted(set(P["symbol"]) | set(fs.etfs))
    # 252 sessions of beta window (about 370 calendar days) plus lags before the first positions date.
    start = pd.Timestamp(first).date() - dt.timedelta(days=int(fs.window * 1.6) + 30)
    fetcher = price_fetcher or (lambda t, s, a: ER.fetch_each(t, s, a, required=fs.etfs, partial=True))
    px, _, failed = fetcher(tickers, start, asof)
    held_failed = sorted(set(failed) & set(P["symbol"]))
    if etf_close_on is not None:
        on_last = set() if px is None or not len(px) else \
            set(px.loc[(pd.to_datetime(px["date"]) == pd.Timestamp(etf_close_on))
                       & np.isfinite(px["close"].to_numpy(float)), "ticker"])
        etf_gone = [e for e in fs.etfs if e not in on_last]
        if etf_gone:                             # every exposure needs the factors: no partial reading
            raise _NotRead(f"factor ETF price unavailable at the close of {etf_close_on}: "
                           + "; ".join(f"{e} ({failed.get(e, 'no row on that date')})" for e in etf_gone)
                           + ("; held name(s) without a price history: " + "; ".join(
                               f"{t} ({failed[t]})" for t in held_failed) if held_failed else ""))
    try:
        ro = ER.readout(px, P, groups, fs=fs, partial=True)
    except ER.NoInputsError as e:
        raise _NotRead(f"{e}" + ("; fetch: " + "; ".join(f"{t} ({failed[t]})" for t in held_failed)
                                 if held_failed else "")) from e
    return ro, failed


def exclusions(ro, failed: dict) -> list[dict]:
    """Every (date, symbol, shares, reason) the partial readout left out, in date order, each
    reason with the fetch's own failure for that ticker when it has one."""
    ex = ro.excluded
    if ex is None or not len(ex):
        return []
    return [{"date": pd.Timestamp(r.date).date().isoformat(), "symbol": r.symbol, "shares": float(r.shares),
             "reason": r.reason + (f" ({failed[r.symbol]})" if r.symbol in failed else "")}
            for r in ex.sort_values(["date", "symbol"]).itertuples()]


def partial_info(ro, res, failed: dict, last: dt.date) -> dict | None:
    """What a PARTIAL block says (team lead, 2026-11-10; `build_factor`): each held name left
    out at the as-of close with its reason, the shares and its gross at the attribution's close;
    and their share of the book's gross, from the attribution's closes for every held name.

    None when every name held at the as-of close was read, even if a name was left out on an
    earlier date (independent review of PR #82, 2026-11-11): the block's status follows the
    as-of reading, and an earlier exclusion is a note in its history (`_factor_report`). Before
    that review an earlier-only exclusion made the block PARTIAL, and risk_daily a WATCH,
    every night from then on, since the job re-reads from the first trade. A name left out
    that the attribution holds no close for raises: its share would be a guess."""
    ex = ro.excluded
    if ex is None or not len(ex):
        return None
    at_last = ex[ex["date"] == pd.Timestamp(last)]
    if not len(at_last):
        return None
    nd = res.name_day[(res.name_day["date"] == last) & (res.name_day["q_end"] != 0)]
    gross = {r.symbol: abs(Fraction(r.q_end) * Fraction(r.close)) for r in nd.itertuples()}
    total = sum(gross.values(), Fraction(0))
    missing = []
    for r in at_last.itertuples():
        if r.symbol not in gross:
            raise ER.ReadoutError(f"{r.symbol} is left out at the close of {last}, and the attribution holds no "
                                  "position and close for it there: its share of the book's gross is unknown")
        missing.append({"symbol": r.symbol, "shares": float(r.shares), "gross_usd": float(gross[r.symbol]),
                        "reason": r.reason + (f" ({failed[r.symbol]})" if r.symbol in failed else "")})
    if total <= 0:                               # a held name at a close of 0: a data error, named
        raise ER.ReadoutError(f"the attribution's gross at the close of {last} is {total}: no share can be read")
    share = float(sum((gross[m["symbol"]] for m in missing), Fraction(0)) / total)
    return {"missing": missing, "missing_gross_share": share,
            "missing_gross_basis": (f"sum of |shares x close| of the names left out over that of every held name, "
                                    f"at the close of {last}, at the attribution's closes (Alpaca daily bars)")}


def _factor_unmeasured(why: str, fs: ER.FactorSet) -> dict:
    return {"status": UNMEASURED, "why": why, "headline": fs.headline,
            "lines": [f"Factor exposure UNMEASURED: {why}"]}


def _review_line(fs: ER.FactorSet) -> dict:
    return {"value": fs.review_line, "review_fraction": ER.REVIEW_FRACTION,
            "vol_target_annual": fs.vol_target, "sizing_multiplier": fs.sizing_multiplier,
            "multiplier_applied": fs.multiplier, "of_target": ER.REVIEW_FRACTION * fs.multiplier,
            "spec_id": fs.spec_id, "ruling": "team lead, 2026-11-10: the line includes the sizing multiplier"}


def _partial_dates(excluded: list[dict]) -> dict:
    dates: dict = {}
    for x in excluded:
        dates.setdefault(x["date"], []).append(x["symbol"])
    return dates


def _earlier_note(earlier: list[dict], why_no_severity: str) -> str:
    """The history's named note for names left out before the as-of close: the dates, names and
    reasons, and why it raises no severity (independent review of PR #82, 2026-11-11)."""
    n = len({x["date"] for x in earlier})
    return (f"History note ({why_no_severity}): a held name was left out on {n} earlier date(s), and the "
            f"readings on those dates are on the remaining names: "
            + "; ".join(f"{x['date']} {x['symbol']} ({x['reason']})" for x in earlier))


# Which sessions the cumulative factor P&L covers, said on every line that prints it (second
# review of PR #82, 2026-11-11). `exposure_readout.readout` reads E(t-1) x f(t) only on a
# positions date whose previous session is one, and `positions_frame` drops flat closes, so a
# session that closes flat after a held close has no row: its factor P&L is not read. The team
# lead left that gap to a follow-up PR (2026-11-11); until then the label keeps it visible.
FACTOR_PNL_SESSIONS = ("each a session whose previous close and own close both held a position; a session that "
                       "closed flat after a held close is not in it (not read here: a follow-up PR, team lead, "
                       "2026-11-11)")


def _factor_pnl(ro, order, pdates: set) -> tuple[list[str], dict]:
    """The cumulative factor P&L's line and JSON fields: the book's summed factor P&L per factor,
    labelled with the sessions it covers (FACTOR_PNL_SESSIONS: their count, first and last) and
    how many were read on a PARTIAL previous-session book.

    NEVER SILENT WHEN THERE IS NONE (second review of PR #82, 2026-11-11). With no session held
    at both its previous close and its own (a book held, then flat, then held again: the review's
    interlude), the readout has no factor P&L row; before that review the block then printed no
    line at all and its JSON said `factor_pnl: null` with no reason. Now the line says it was not
    read and why, and `factor_pnl_why` carries the same. No figure changes: the sums are the
    readout's own, over the same rows."""
    fp = ro.factor_pnl
    if not len(fp):
        why = ("no session since the first trade held a position at both its previous close and its own, so no "
               "E(t-1) x f(t) was read; a session that closed flat after a held close is not read here (a "
               "follow-up PR, team lead, 2026-11-11)")
        return [f"Cumulative factor P&L not read: {why}"], {"factor_pnl": None, "factor_pnl_why": why}
    book_rows = fp[fp["scope"] == "book"]
    pnl = {k: float(book_rows[book_rows["factor"] == k]["pnl_summed"].sum()) for k in order}
    on_partial = int(book_rows[book_rows["prev"].map(lambda d: pd.Timestamp(d).date().isoformat()).isin(pdates)]
                     ["date"].nunique()) if pdates else 0
    sessions = sorted({pd.Timestamp(d).date().isoformat() for d in book_rows["date"]})
    line = (f"Cumulative factor P&L (book, E(t-1) x f(t), model reading) over {len(sessions)} session(s), "
            f"{sessions[0]} to {sessions[-1]}, {FACTOR_PNL_SESSIONS}: "
            + ", ".join(f"{k} {v:+,.2f}" for k, v in pnl.items())
            + (f" ({on_partial} session(s) on a PARTIAL previous-session book)" if on_partial else ""))
    return [line], {"factor_pnl": pnl,
                    "factor_pnl_sessions": {"count": len(sessions), "first": sessions[0], "last": sessions[-1]}}


def _factor_flat(book: str, fs: ER.FactorSet, P: pd.DataFrame, *, groups: dict, first: dt.date, last: dt.date,
                 asof: dt.date, price_fetcher) -> dict:
    """The block for a book that holds nothing at the as-of close (independent review of PR #82,
    2026-11-11). Status FLAT: a flat book carries no factor risk, so there is nothing to
    review and nothing missing. It is reached only from a rebuild that reconciles
    (`build_factor`), and risk_daily shows it as INFO only when the collector's account record
    for the same close holds no position either; WATCH when it holds any, UNMEASURED when it
    cannot be read (team lead, 2026-11-11; `risk_daily.factor_block`).

    It says so in its first line and reads nothing for that close: no exposure, no within or
    REVIEW flag, no PARTIAL, no share. Before this review the block showed the previous held
    close's exposure as the as-of reading, under status OK, dated but easy to miss. The
    history since the first trade (the review-flag counts and the factor P&L over the earlier
    held closes) is still read, and every line of it says which dates it covers; a name left
    out on one of those dates is the history's note and raises nothing. A history with no
    reading for a named reason (`_NotRead`: no held name with its inputs on an earlier date, or
    a book with no Dimson lag) is UNMEASURED in its own line, named, and leaves the as-of
    reading FLAT, because that reading needs no price: the book holds nothing.

    ANYTHING ELSE PROPAGATES, AS ON A HELD NIGHT (second review of PR #82, 2026-11-11). This
    function caught every exception from the history read and kept the block FLAT, the report
    OK and risk_daily INFO, so a bug (a TypeError) and the runtime no-lookahead assertion
    (exposure_readout's LookaheadError, H7) passed as a history footnote on a flat night while
    the same failure on a held night made the block UNMEASURED, the report PARTIAL and
    risk_daily UNMEASURED; it also contradicted `_NotRead`, which says a bug propagates. Now
    only `_NotRead` is caught here, and anything else reaches `run_report`'s catch, which makes
    the block UNMEASURED as it does for a held book. That includes a yfinance outage: a factor
    ETF's failed fetch is re-raised by `fetch_each` (required tickers) as yfinance's own error,
    a ReadoutError ("yfinance returned no rows", yfinance 0.2.66 swallowing the transport
    error into an empty frame) or the transport's exception, never a `_NotRead`; so a flat
    night with yfinance down reads UNMEASURED, as a held night does, and is not a FLAT block
    with a history line. Widening `_NotRead` to cover it is the team lead's to rule."""
    order = [fs.headline] + list(fs.indicative)
    lines = [f"Factor exposure at the close of {last}: FLAT, the book holds no position at that close, so there "
             f"is nothing to expose: no exposure, no review-line reading and no flag is read for {last}, and no "
             f"earlier close's reading stands in for it"]
    out = {"status": FLAT, "asof": last.isoformat(), "flat": True, "headline": fs.headline,
           "review_line": _review_line(fs), "lines": lines, "history": None}
    if P.empty:
        lines.append(f"History since the first trade ({first}): no close held a position")
        return out
    try:
        if fs.dimson_lags is None:
            raise _NotRead(f"book {book} has no Dimson lag: its lag rule has not produced one "
                           "(scripts/cef/exposure_readout.py, THE C4 LAG RULE)")
        ro, failed = _read(fs, P, groups, first=first, asof=asof, price_fetcher=price_fetcher, etf_close_on=None)
    except _NotRead as e:                        # a named reason only; a bug, a LookaheadError or a failed fetch propagates
        why = str(e)
        lines.append(f"History since the first trade ({first}) UNMEASURED: {why}")
        out["history_why"] = why
        return out
    ex = ro.exposure
    held = sorted(pd.Timestamp(d).date().isoformat() for d in ex["date"].unique())
    if held[-1] >= last.isoformat():             # positions_frame holds nothing at `last`: a bug if the readout does
        raise ER.ReadoutError(f"a flat book's readout has a date {held[-1]} at or after its flat close {last}")
    excluded = exclusions(ro, failed)
    pdates = set(_partial_dates(excluded))
    history = {k: {"review_dates": int(ex[(ex["factor"] == k) & (ex["review"] == "REVIEW")]["date"].nunique()),
                   "dates": int(ex[ex["factor"] == k]["date"].nunique())} for k in order}
    lines.append(f"History since the first trade ({first}), each date read at its own close: {len(held)} earlier "
                 f"close(s) with a position, {held[0]} to {held[-1]}; REVIEW on "
                 + ", ".join(f"{k} {history[k]['review_dates']} of {history[k]['dates']}" for k in order)
                 + (f" ({len(pdates)} of those dates PARTIAL)" if pdates else ""))
    pnl_lines, pnl_out = _factor_pnl(ro, order, pdates)
    lines.extend(pnl_lines)
    if excluded:
        lines.append(_earlier_note(excluded, f"no severity: the book holds nothing at the close of {last}"))
    out.update(history=history, history_dates=[held[0], held[-1]], **pnl_out)
    if excluded:
        out.update(partial_dates=_partial_dates(excluded), earlier_exclusions=excluded)
    return out


def _factor_report(ro, fs: ER.FactorSet, book: str, last: dt.date, partial: dict | None = None,
                   excluded: list[dict] | None = None) -> dict:
    """The exposure at the as-of close and the review history. A review-line breach is a word
    in this report and nothing else: it pushes nothing and sets no severity (team lead,
    2026-11-09: report-only). The line is REVIEW_FRACTION x vol_target_annual x
    sizing_multiplier (team lead, 2026-11-10), and the JSON's `review_line` carries the value
    and its three inputs, so a reader sees what the flags were read against; c/target stays
    over vol_target_annual, and the header line says the line in those units too.

    With `partial` (team lead, 2026-11-10; `build_factor`) the block is PARTIAL: its first
    lines name what was left out and its share of the gross, every flag read on a partial book
    at the last close says "(PARTIAL)", in the JSON as in the text, and the review history and
    the factor P&L say how many of their dates were partial.

    `last` is the as-of close the block is read at, and the readout's last date must be it
    (independent review of PR #82, 2026-11-11): an earlier close's reading is never shown as
    the as-of one (a flat book never reaches here; `_factor_flat`). `excluded` is every name
    the readout left out on any date; those before `last`, when nothing is missing at `last`,
    are the history's named note, and the block stays OK (that review: the status follows the
    as-of reading)."""
    ex = ro.exposure
    if pd.Timestamp(ex["date"].max()) != pd.Timestamp(last):
        raise ER.ReadoutError(f"the readout's last date {pd.Timestamp(ex['date'].max()).date()} is not the as-of "
                              f"close {last}: an earlier close's reading is never shown as the as-of one")
    last = pd.Timestamp(last)
    excluded = excluded or []
    today = ex[ex["date"] == last].set_index("factor")
    pdates = set(_partial_dates(excluded))
    lab = " (PARTIAL)" if partial else ""
    def fac(k):
        r = today.loc[k]
        return {"exposure_usd": float(r["exposure_usd"]), "exposure_frac": float(r["exposure_frac"]),
                "contrib_of_target": float(r["contrib_of_target"]), "t_stat": float(r["t_stat"]),
                "review": str(r["review"]) + lab, "factor_vol": float(r["factor_vol"])}
    order = [fs.headline] + list(fs.indicative)
    factors = {k: fac(k) for k in order}
    history = {k: {"review_dates": int(ex[(ex["factor"] == k) & (ex["review"] == "REVIEW")]["date"].nunique()),
                   "dates": int(ex[ex["factor"] == k]["date"].nunique())} for k in order}
    if pdates:
        for k in order:
            history[k]["partial_dates"] = len(pdates)
    tv = ro.total_vol.set_index("date").loc[last]
    mult = "1 (key absent: the unit book)" if fs.sizing_multiplier is None else f"{fs.sizing_multiplier:.4g}"
    review_line = _review_line(fs)
    lines = [f"Factor exposure{' PARTIAL' if partial else ''} at the close of {last.date()} "
             f"(headline {fs.headline}, "
             f"line = REVIEW_FRACTION {ER.REVIEW_FRACTION} x vol target {fs.vol_target:.4g} x sizing multiplier "
             f"{mult} = {fs.review_line:.4g}, i.e. c/target {review_line['of_target']:.3f}, of book {book}; "
             f"window {ro.window} sessions strictly before each date, Dimson lags 0..{ro.lags}): "
             f"gross {float(tv['gross_usd']):,.0f} USD, net {float(tv['net_usd']):+,.0f} USD"
             f"{' of the names read' if lab else ''}, total factor vol {float(tv['total_of_target']):.3f} of target"
             f"{lab}"]
    if partial:
        miss = partial["missing"]
        lines.insert(0, f"Factor exposure PARTIAL (team lead, 2026-11-10): {len(miss)} held name(s) left out at "
                        f"the close of {last.date()}, without every input the readout needs, "
                        f"{partial['missing_gross_share']:.1%} of the book's gross at the attribution's closes: "
                        + "; ".join(f"{m['symbol']}, {m['shares']:+,.0f} shares, {m['gross_usd']:,.0f} USD gross, "
                                    f"{m['reason']}" for m in miss)
                        + ". The exposures, the review-line comparison and every flag at that close are on the "
                          "remaining names, each labelled PARTIAL")
        lines.insert(1, "Dates with a name left out: " + "; ".join(f"{d} {', '.join(s)}"
                                                                   for d, s in sorted(_partial_dates(excluded).items())))
    for k in order:
        f = factors[k]
        tag = "headline" if k == fs.headline else "indicative"
        lines.append(f"{k} ({tag}): E {f['exposure_usd']:+,.0f} USD ({f['exposure_frac']:+.3f} of equity), c/target "
                     f"{f['contrib_of_target']:.3f}, t {f['t_stat']:+.2f}: {f['review']}; REVIEW on "
                     f"{history[k]['review_dates']} of {history[k]['dates']} date(s) so far"
                     + (f", {len(pdates)} of them PARTIAL" if pdates else ""))
    split: dict
    if fs.group_split == "muni":
        mv = ER.muni_vs_taxable(ro)
        row = mv[mv["date"] == last].iloc[0]
        split = {"kind": "muni_vs_taxable", "muni_usd": float(row["muni_usd"]), "taxable_usd": float(row["taxable_usd"]),
                 "book_usd": float(row["book_usd"]), "muni_held": bool(row["muni_held"]),
                 "taxable_held": bool(row["taxable_held"]),
                 "taxable_by_group": dict(row["taxable_by_group"])}
        lines.append(f"{fs.headline} by side{lab}: muni group {split['muni_usd']:+,.0f} USD, taxable groups "
                     f"{split['taxable_usd']:+,.0f} USD ({', '.join(f'{g} {v:+,.0f}' for g, v in split['taxable_by_group'].items()) or 'none held'})")
    else:
        hg = ER.headline_by_group(ro)
        hg = hg[hg["date"] == last]
        split = {"kind": "by_family", "families": {r.grp: {"exposure_usd": float(r.exposure_usd),
                                                           "exposure_frac": float(r.exposure_frac),
                                                           "share_of_book": float(r.share_of_book)}
                                                   for r in hg.itertuples()},
                 "book_usd": float(hg["book_usd"].iloc[0]) if len(hg) else 0.0}
        lines.append(f"{fs.headline} by family{lab}: "
                     + ", ".join(f"{g} {v['exposure_usd']:+,.0f} ({v['share_of_book']:+.2f} of book)"
                                 for g, v in split["families"].items()))
    pnl_lines, pnl_out = _factor_pnl(ro, order, pdates)
    lines.extend(pnl_lines)
    earlier = [x for x in excluded if x["date"] < last.date().isoformat()]
    if earlier and not partial:
        lines.append(_earlier_note(earlier, f"no severity: every name held at the close of {last.date()} is read"))
    out = {"status": "PARTIAL" if partial else "OK", "asof": last.date().isoformat(),
           "headline": fs.headline, "review_line": review_line,
            "factors": factors, "history": history, "split": split, "factor_pnl": pnl_out["factor_pnl"],
            "lines": lines, "gross_usd": float(tv["gross_usd"]), "net_usd": float(tv["net_usd"]),
            "total_of_target": float(tv["total_of_target"])}
    out.update(pnl_out)                          # factor_pnl_sessions, or factor_pnl_why when there is none
    if partial:
        out.update(partial)
    if excluded:
        out.update(partial_dates=_partial_dates(excluded), earlier_exclusions=earlier)
    return out


# ---------------------------------------------------------------- the report

def exit_code(*, incomplete: bool, reconciled) -> int:
    """The unit's exit code (module docstring, EXIT CODES; team lead, 2026-11-10).

    Incomplete outranks unreconciled: with no broker read or a refused attribution nothing
    was reconciled, so `reconciled` is unknown there, never false. A completed attribution
    always says True or False; anything else is a bug here and raises, rather than exit 0
    for a reconciliation nobody checked."""
    if incomplete:
        return EXIT_INCOMPLETE
    if reconciled is True:
        return EXIT_OK
    if reconciled is False:
        return EXIT_UNRECONCILED
    raise ValueError(f"a completed attribution has reconciled={reconciled!r}, not True or False")


def safe_nav_fetcher(gaps: list, book: str):
    """yfinance NAVs (`live_attribution.yf_navs`, at `book`'s own NAV symbols), or no rows on
    a failure, named: a fund's NAV may not be published yet and yfinance can be down; the split
    is then UNMEASURED for those name-days, and hold, fill, fees and the reconciliation do not
    depend on it."""
    def f(symbols, start, end):
        try:
            return LA.yf_navs(symbols, start, end, book=book)
        except Exception as e:
            gaps.append(f"NAV source (yfinance, book {book}'s NAV symbols) failed: {type(e).__name__}: {e}; the "
                        f"NAV/discount split is UNMEASURED on every held name-day")
            return pd.DataFrame(columns=["date", "ticker", "nav"]), list(symbols)
    return f


def safe_dist_fetcher(gaps: list):
    """yfinance dividends (`live_attribution.yf_dividends`), or no rows, named: every
    distribution then resolves UNMEASURED by dist_score's two-source rule, never zero."""
    def f(symbols):
        try:
            return LA.yf_dividends(symbols)
        except Exception as e:
            gaps.append(f"second distribution source (yfinance dividends) failed: {type(e).__name__}: {e}; "
                        f"distributions are UNMEASURED")
            return pd.DataFrame(columns=["ticker", "ex_date", "amount"]), list(symbols)
    return f


def render_md(rep: dict) -> str:
    out = [f"# P&L attribution and factor exposure, {rep['book']}, as-of {rep['asof']}", "",
           f"Generated {rep['generated_at']} (report only; nothing here touches an order; zero trials).",
           f"Overall: **{rep['status']}**."]
    if rep["status"] == UNRECONCILED:
        out += [f"**{ln}**" for ln in (rep["attribution"].get("reconciliation") or {}).get("lines", [])]
    out += ["", "## Attribution"]
    out.extend(f"- {ln}" for ln in rep["attribution"]["lines"])
    out += ["", f"## Factor exposure against the review line ({rep['factor'].get('status')})"]
    out.extend(f"- {ln}" for ln in rep["factor"]["lines"])
    gaps = rep.get("gaps") or []
    if gaps:
        out += ["", "## Gaps and notes"]
        out.extend(f"- {g}" for g in gaps)
    out += ["", "A review-line breach is report-only: it appears here and sends nothing (team lead, 2026-11-09)."]
    return "\n".join(out) + "\n"


def _keep_yfinance_cache_under(out_dir: Path, gaps: list) -> None:
    """Put yfinance's SQLite caches beside the report, before its first fetch.

    By default yfinance writes `tkr-tz.db`, `cookies.db` and `isin-tkr.db` under the user cache
    directory (`platformdirs.user_cache_dir`, so `~/.cache/py-yfinance` on Linux), which the
    unit's promise of writing only under `${STATE_DIR}/reports/pnl` did not cover (review,
    2026-11-09). `set_tz_cache_location` moves all three: `yfinance/cache.py`
    `set_cache_location` sets the timezone, cookie and ISIN managers, read from the installed
    0.2.66 that requirements.txt pins. A failure is named and costs only the location: the
    fetches below report for themselves whether yfinance works at all."""
    try:
        import yfinance as yf
        where = out_dir / "_yf_cache"
        where.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(where))
    except Exception as e:
        gaps.append(f"yfinance's cache location was not set, so it may write in the user cache directory: "
                    f"{type(e).__name__}: {e}")


def run_report(book: str, state: Path, asof: dt.date, *, now_utc=None, reader=None, groups=None,
               nav_fetcher=None, dist_check_fetcher=None, price_fetcher=None) -> tuple[dict, int]:
    """One book's report: writes `<state>/reports/pnl/<asof>.{md,json}`. Returns (report, code),
    the code by `exit_code` and decided only after both files are written (module docstring,
    EXIT CODES). A directory under data/ or visible to git raises before anything is read or
    written."""
    now = now_utc or dt.datetime.now(dt.timezone.utc)
    out_dir = state / "reports" / "pnl"
    LA._refuse_data_dir(out_dir)
    LA._refuse_git_visible(out_dir, [f"{asof.isoformat()}.json", f"{asof.isoformat()}.md"])
    gaps: list = []
    if nav_fetcher is None or dist_check_fetcher is None or price_fetcher is None:
        _keep_yfinance_cache_under(out_dir, gaps)
    nav_f = nav_fetcher or safe_nav_fetcher(gaps, book)
    div_f = dist_check_fetcher or safe_dist_fetcher(gaps)
    incomplete = False
    att: dict
    res = inp = None
    try:
        reader = AR.AlpacaReader.from_environment(book) if reader is None else reader
        groups = LA.load_groups_for(book) if groups is None else groups
        att = build_attribution(book, state, asof, reader, groups, now_utc=now, nav_fetcher=nav_f,
                                dist_check_fetcher=div_f)
        res, inp = att.pop("_res"), att.pop("_inp")
        gaps += att.pop("gaps")
    except Exception as e:                       # a failed read or refusal: this report's failure, named
        incomplete = True
        att = {"status": UNMEASURED, "why": f"{type(e).__name__}: {e}",
               "lines": [f"Attribution UNMEASURED: {type(e).__name__}: {e}"], "session": None, "cumulative": None,
               "reconciled": None}
    try:
        if res is None:
            factor = {"status": UNMEASURED, "why": "the attribution did not run", "lines":
                      ["Factor exposure UNMEASURED: the attribution did not run, so the book's positions are unknown"]}
        else:
            factor = build_factor(book, res, inp, groups=groups, asof=asof, reconciled=att.get("reconciled"),
                                  price_fetcher=price_fetcher, now_utc=now)
    except Exception as e:                       # the factor readout's failure costs only its block
        factor = {"status": UNMEASURED, "why": f"{type(e).__name__}: {e}",
                  "lines": [f"Factor exposure UNMEASURED: {type(e).__name__}: {e}"]}
    if att["status"] != "OK":
        status = UNMEASURED
    elif att.get("reconciled") is False:
        status = UNRECONCILED                    # loudest first: a factor gap is not the headline here
    else:
        # FLAT is a complete reading (nothing held, nothing to expose), not a gap: OK overall
        # (independent review of PR #82, 2026-11-11).
        status = "OK" if factor["status"] in ("OK", FLAT) else "PARTIAL"
    rep = {"book": book, "asof": asof.isoformat(), "generated_at": now.astimezone(ET).isoformat(timespec="seconds"),
           "status": status, "attribution": att, "factor": factor, "gaps": gaps,
           "note": "report only; zero trials; a review-line breach sends nothing"}
    write_atomic(out_dir / f"{asof.isoformat()}.json", json.dumps(rep, indent=1, default=str))
    write_atomic(out_dir / f"{asof.isoformat()}.md", render_md(rep))
    code = exit_code(incomplete=incomplete, reconciled=att.get("reconciled"))   # after both files exist
    print(f"pnl_report {book} {asof}: {status}; exit {code}; wrote {out_dir / f'{asof.isoformat()}.md'}")
    return rep, code


def main(argv=None, *, now_utc=None, reader=None) -> int:
    ap = argparse.ArgumentParser(description="The daily P&L attribution and factor exposure report (report only).")
    ap.add_argument("--book", required=True, choices=sorted(BOOKS))
    ap.add_argument("--state-dir", type=Path, default=None, help="default $QUANTT_STATE_DIR")
    ap.add_argument("--asof", type=dt.date.fromisoformat, default=None)
    a = ap.parse_args(argv)
    state = a.state_dir or (Path(os.environ["QUANTT_STATE_DIR"]) if os.environ.get("QUANTT_STATE_DIR") else None)
    if state is None:
        print("REFUSED: no --state-dir and no QUANTT_STATE_DIR", file=sys.stderr)
        return EXIT_REFUSED
    now = now_utc or dt.datetime.now(dt.timezone.utc)
    asof = a.asof or expected_day(now.astimezone(ET))
    try:
        _, code = run_report(a.book, state, asof, now_utc=now, reader=reader)
    except LA.AttributionError as e:             # a refused directory: nothing was read or written
        print(f"REFUSED: {e}", file=sys.stderr)
        return EXIT_REFUSED
    return code


if __name__ == "__main__":
    raise SystemExit(main())
