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
  * a split record in a fund the book has held: the fund is left out, named (symbol, ex-date,
    yfinance's ratio), only on the dates the split can touch, before its ex-date and, for the
    core, with the ex-date in its beta window (team lead, 2026-11-14, option A of the third
    review of PR #82; `exposure_readout._split_scope`); PARTIAL at the as-of close, a history
    note earlier, as above. Before that ruling one split in a fund ever held made the block
    UNMEASURED every night after.
  * a corporate action on a fund the book held into its date (team lead, 2026-11-14:
    "narrow and handle it", and 2026-11-15: "simplify"; `live_attribution`, CORPORATE ACTIONS).
    An acquirer's merger, a flat name and an event outside the window touch nothing. The
    rebuild takes positions from FILLs alone, never the market feed and never the account's own
    corporate-action activity rows: any such row on or before the job's as-of (not only the
    session read, on a late-EOD night) stops the attribution, every row named (symbol, type,
    date, share count), exit 4, because its REST format has never been measured. A forward or
    reverse split paper did not process is reconciled as the account
    shows it, with a labelled phantom line per event, its accrual until the account first
    trades the name, its crystallisation at that trade (with the session's fee term), and a
    cumulative phantom line, an estimate of what paper's missing split put into the official
    P&L, beside the official P&L, which stays the P&L of record (`corporate_action_lines`).
    Every crystallised phantom is labelled "approximate: <reason>" (line and JSON; the live
    sleeve's no-trade band, team lead, 2026-11-15), and so is any phantom whose other conditions
    fail; an open one is labelled only for a fractional q_prev x k. A session that does not
    reconcile (a frozen position, or a hand-pushed split with no row) is UNRECONCILED, exit 5,
    naming the session and the event (`reconciliation`). Any other count-changing type held into its date
    refuses the attribution, named (exit 4).
  * a book that holds nothing at the as-of close: the factor block is FLAT (independent
    review of PR #82, 2026-11-11). Nothing is held, so nothing is exposed; the block reads no
    exposure, no flag and no PARTIAL for that close, and never shows an earlier close's
    reading as the as-of one. FLAT is read only from a rebuild that reconciles: an
    unreconciled one makes the block UNMEASURED, naming why (team lead, 2026-11-11;
    `build_factor`). Its history since the first trade is labelled with its dates;
    a history with no reading for a named reason is an UNMEASURED line in the FLAT block, and
    a bug, a LookaheadError or a failed price fetch while reading it makes the whole block
    UNMEASURED, as on a held night (second review of PR #82, 2026-11-11; `_factor_flat`).
  * the factor block reads the fill rebuild's positions, never the account's. So the JSON
    carries those positions at the block's as-of close for every factor status
    (`rebuild_positions`), and risk_daily compares them, share for share, with the collector's
    account record of that close: a disagreement is its WATCH, a record it cannot read its
    UNMEASURED, never INFO (team lead, 2026-11-11/12, on the third review of PR #82, whose
    phantom sale of 2,000 AAA left the block OK at half the true MUNI exposure). A held book on
    an unreconciled night is read, for diagnosis, under status UNRECONCILED, never OK
    (`build_factor`).
  * Alpaca's EOD history with no point for the as-of D yet: the job reads the latest session it
    has, D-1, under D's name (`build_attribution`). The markdown's title and the line under its
    status then say "READ AT THE CLOSE OF D-1, NOT D", the JSON's `session_read` names D-1, and
    risk_daily shows both blocks UNMEASURED for D, never INFO (team lead, 2026-11-11/12, on the
    third review of PR #82, where D's report passed D-1's FLAT as INFO; `render_md`,
    `risk_daily._reading_of`).
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
    session is named; the attribution is still shown for diagnosis, labelled.

    A failure on or after a corporate action on a held name names the event too (team lead,
    2026-11-14; `live_attribution`, CORPORATE ACTIONS): paper may have frozen the position (H2),
    or support may have pushed the action by hand with no account row (H3), and the rebuild
    from fills cannot follow either, so the line says which event the residual follows."""
    bad = []
    for r in res.daily[res.daily["date"] >= first].itertuples():
        if abs(Fraction(r.residual)) > RESIDUAL_CENT:
            bad.append((r.date.isoformat(), float(r.residual)))
    max_res = max((abs(float(r)) for r in res.daily[res.daily["date"] >= first]["residual"]), default=0.0)
    lines = []
    if bad:
        events = [c for c in getattr(res, "corp_events", []) if c["session"].isoformat() <= bad[-1][0]]
        lines.append(f"RECONCILIATION FAILED on {len(bad)} session(s): " +
                     ", ".join(f"{d} residual {v:+.2f}" for d, v in bad[:10]) +
                     (" ..." if len(bad) > 10 else "") +
                     ". The rebuild (hold + fill + fees) does not equal Alpaca's EOD change to the cent; "
                     "the figures below are unreconciled for those sessions."
                     + (" Corporate action(s) on a held name on or before a failed session, which paper may "
                        "have frozen or processed without an account row the rebuild could follow: "
                        + "; ".join(f"{c['type']} {c['symbol']} ex {c['date']} (id {c['id']}), session {c['session']}"
                                    for c in events) if events else ""))
    return {"reconciled": not bad, "failed_sessions": bad, "max_abs_residual": max_res, "lines": lines}


def _px(x) -> str:
    return "UNMEASURED" if x is None else f"{float(x):,.4f}"


def corporate_action_lines(res, first: dt.date, eff: dt.date) -> tuple[list[str], dict]:
    """The labelled corporate-action lines and JSON fields (team lead, 2026-11-14;
    `live_attribution`, CORPORATE ACTIONS), or nothing when no corporate action touched a held
    name since the first trade, so such a report is the one it always was.

    A split paper did not process leaves the old count marked at the new-basis close: hold and
    the official EOD change both carry (q_prev - q_prev x k) x close_t on its session, a phantom.
    While it is open, paper's extra shares move with the price, and that accrual is phantom too
    (inside hold); the first trade in the name crystallises it (second review of the follow-up,
    2026-11-15, finding 1: the extra shares at the fill price against the last close, plus that
    session's fee term), and it takes no further terms. Each is shown per event, and the
    cumulative phantom (JSON `phantom_cumulative`), the booking plus the accruals, the
    crystallisations and the fee terms, is an estimate of what paper's missing splits put into
    the official P&L at the as-of: every crystallised one is labelled approximate (`approximate`,
    `phantom_approximate`), because the live sleeve's no-trade band means an account that
    processed the split need not have traded to the same position (live_attribution, CORPORATE
    ACTIONS, WHAT THE FIGURE IS; team lead, 2026-11-15). It sits BESIDE the official
    change, which stays the P&L of record (docs/SYSTEM.md section 5); nothing is subtracted from
    any line. A term the market record or a close cannot give is UNMEASURED, and so is any sum
    that holds it."""
    evs = [c for c in getattr(res, "corp_events", []) if c["session"] >= first]
    if not evs:
        return [], {}

    def f(x):
        return None if x is None else float(x)

    def moves(c, upto=None):
        """[(session, amount)] of one event's phantom: booking, accruals, crystallisation."""
        out = [(c["session"], f(c["phantom"]))] + [(d, f(a)) for d, a in c["accruals"]]
        if c["crystallised"] is not None:
            out.append((c["crystallised"]["session"], f(c["crystallised"]["amount"])))
        return [(d, a) for d, a in out if upto is None or d == upto]

    def total(pairs):
        return None if any(a is None for _, a in pairs) else sum((a for _, a in pairs), 0.0)

    lines = []
    for c in evs:
        lines.append(f"Phantom: paper did not process {c['type']} {c['symbol']} ex {c['date']} (id {c['id']}), "
                     f"session {c['session']}: (q_prev - q_prev x k) x close_t = "
                     + (f"{f(c['phantom']):+,.2f} (q_prev {c['q_prev']}, k {c['k']})" if c["phantom"] is not None
                        else f"UNMEASURED ({c['why']})")
                     + ", inside hold and the official change; that name-day's NAV/discount split is UNMEASURED"
                     + (f"; approximate: {c['approximate']}" if c["approximate"] else ""))
        if c["accruals"]:
            acc = total([(d, f(a)) for d, a in c["accruals"]])
            lines.append(f"Phantom accrual: paper's extra {c['extra']} share(s) of {c['symbol']} moved with the price "
                         f"on {len(c['accruals'])} session(s) after {c['session']}: {_usd(acc)}, inside hold")
        if c["crystallised"] is not None:
            cr = c["crystallised"]
            lines.append(f"Phantom crystallised by the trade on {cr['session']}: paper's extra {c['extra']} share(s) of "
                         f"{c['symbol']} at the fill price {_px(cr['price'])} against the close {_px(cr['reference_close'])}: "
                         f"{_usd(f(cr['amount']))}; the phantom of {c['type']} (id {c['id']}) takes no further terms "
                         "after this trade (team lead, 2026-11-15)")
        else:
            lines.append(f"Phantom of {c['type']} {c['symbol']} (id {c['id']}) still OPEN at the as-of: the account has "
                         "not traded the name since")
    fee_terms = [(t["session"], f(t["amount"])) for t in getattr(res, "phantom_fees", []) if t["session"] >= first]
    for t in getattr(res, "phantom_fees", []):
        if t["session"] >= first:
            lines.append(f"Phantom fee term on {t['session']}: that session's modelled fees less those of the same trades "
                         f"without paper's extra shares of {', '.join(t['symbols'])}: {_usd(f(t['amount']))}")
    cum = total([m for c in evs for m in moves(c)] + fee_terms)
    ses = [m for c in evs for m in moves(c, eff)] + [m for m in fee_terms if m[0] == eff]
    n_open = sum(1 for c in evs if c["crystallised"] is None)
    approx = [f"{c['symbol']} ({c['approximate']})" for c in evs if c["approximate"]]
    lines.append(f"Phantom from corporate actions paper did not process, estimated in the official P&L at the as-of: "
                 f"{_usd(cum)} ({len(evs)} event(s), {n_open} still open, {len(evs) - n_open} crystallised by a "
                 "trade); the official P&L above includes it and stays the P&L of record"
                 + (f"; approximate: {'; '.join(approx)}" if approx else ""))

    def js(v):
        """dates as ISO, Fractions as floats, through lists and dicts (the event record's shape)."""
        if isinstance(v, dt.date):
            return v.isoformat()
        if isinstance(v, Fraction):
            return float(v)
        if isinstance(v, dict):
            return {kk: js(vv) for kk, vv in v.items()}
        if isinstance(v, (list, tuple)):
            return [js(x) for x in v]
        return v

    out = {"corporate_actions": [{k: js(v) for k, v in c.items()} for c in evs],
           "phantom_cumulative": cum}
    if fee_terms:
        out["phantom_fee_terms"] = [[d.isoformat(), a] for d, a in fee_terms]
    if approx:
        out["phantom_approximate"] = approx
    if ses:
        out["phantom_session"] = total(ses)
    return lines, out


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


REBUILD_POSITIONS_SOURCE = ("the fill rebuild's signed whole shares per held name at the close the factor block is "
                            "read at (live_attribution name_day q_end, the positions the factor readout reads)")


def rebuild_positions(res) -> dict:
    """The rebuild's per-name signed shares at the factor block's as-of close (`res.asof`), for
    `risk_daily` to compare with the collector's account record of that close. Team lead,
    2026-11-11/12, on the third review of PR #82.

    WHY. The factor block reads the fill rebuild's positions, never the account's. The third
    review listed a sale of 2,000 AAA at the close that the account never made: the rebuild held
    AAA 2,000 where the account held 4,000, the block read OK with MUNI exposure at half its true
    value, and risk_daily passed it as INFO; priced so the rebuild still reconciled, every status
    was OK or INFO. Until then only a FLAT block was checked against the account
    (`risk_daily._flat_cross_check`). So the job now writes what the readout read, and risk_daily
    checks it for every factor status (`risk_daily.factor_block`).

    {"session": the as-of close, "qty": {symbol: signed shares}, "source": ...}. Only names with a
    non-zero position are listed (an empty `qty` is a flat close), as the collector's
    `positions.qty` lists only positions. Every quantity is a whole share: `Fill.signed_qty` is an
    int, so a rebuild quantity that is not one is a bug and raises (the caller names it)."""
    last = res.asof
    nd = res.name_day[(res.name_day["date"] == last) & (res.name_day["q_end"] != 0)]
    qty: dict = {}
    for r in nd.itertuples():
        q = Fraction(r.q_end)
        if q.denominator != 1:
            raise ValueError(f"the rebuild holds {r.symbol} {q} at the close of {last}: not a whole share")
        if r.symbol in qty:
            raise ValueError(f"the rebuild lists {r.symbol} twice at the close of {last}")
        qty[r.symbol] = int(q)
    return {"session": last.isoformat(), "qty": dict(sorted(qty.items())), "source": REBUILD_POSITIONS_SOURCE}


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
    # The account's own corporate-action rows stop the report at the JOB's as-of, not only at the
    # session read (fourth review of the follow-up, finding 2): on a night Alpaca has no EOD point
    # for the as-of yet, `attribute` reads the session before, and a row dated between the two
    # would otherwise go unnamed (`live_attribution`, CORPORATE ACTIONS).
    rows = [a for a in inp.corp_acts if a["date"] <= asof]
    if rows:
        raise LA.AttributionError(LA.account_rows_stop(rows, asof))
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
    ca_lines, ca_out = corporate_action_lines(res, first, eff)
    lines = attribution_lines(sess, cum, recon, session_note=note) + ca_lines + fees
    out = {"status": "OK", "session": sess, "cumulative": cum, "reconciled": recon["reconciled"],
           "reconciliation": recon, "fee_check": fees, "lines": lines, "first_trade": first.isoformat(),
           "effective_session": eff.isoformat(), "gaps": list(res.gaps),
           "_res": res, "_inp": inp}
    out.update(ca_out)                           # only when a corporate action touched a held name
    return out


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
    block is then UNMEASURED, naming why, and no FLAT and no exposure is read. A rebuild that
    reconciles while its positions are still wrong (the review's contrived fill whose P&L
    cancels its modelled fees) is caught by risk_daily's cross-check against the collector's
    account record (`risk_daily.factor_block`).

    A HELD BOOK ON AN UNRECONCILED NIGHT IS NEVER OK (team lead, 2026-11-11/12, on the third
    review of PR #82). It is still read, as the attribution rows still print on such a night,
    for diagnosis; but the block's status is UNRECONCILED, its first line says the readings are
    on a rebuild not shown to be the account's, and every flag says "(UNRECONCILED)"
    (`_factor_report`). Before that ruling it was OK: the review's phantom sale of 2,000 AAA at
    the close left the rebuild holding half the account's AAA, the block read OK with MUNI
    exposure at half its true value, and risk_daily read it INFO. risk_daily shows such a block
    as at least a WATCH; and since the same review every factor status carries the rebuild's
    positions (`rebuild_positions`, written by `run_report`) for its cross-check."""
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
        ro, failed, _ = _read(fs, P, groups, first=first, asof=asof, price_fetcher=price_fetcher, etf_close_on=last,
                              pnl_through=last)
    except _NotRead as e:
        return _factor_unmeasured(str(e), fs)
    return _factor_report(ro, fs, book, last, partial=partial_info(ro, res, failed, last),
                          excluded=exclusions(ro, failed), unreconciled=reconciled is not True)


class _NotRead(Exception):
    """A named reason the factor readout has no reading (a factor ETF without its price at the
    as-of close, no held name with its inputs, a book with no Dimson lag): the block's
    UNMEASURED line, or a flat block's history line. A bug is not one of these and propagates;
    nor does the runtime no-lookahead assertion (LookaheadError) or a failed price fetch, which
    make the whole block UNMEASURED on a flat night as on a held one (second review of PR #82,
    2026-11-11; `_factor_flat`)."""


def _read(fs: ER.FactorSet, P: pd.DataFrame, groups: dict, *, first: dt.date, asof: dt.date, price_fetcher,
          etf_close_on: dt.date | None, pnl_through: dt.date, flat_close: dt.date | None = None):
    """Fetch every held name's and factor ETF's prices and read the partial readout on P.
    Returns (readout, the fetch's failures by ticker, why the as-of term is not read or None).
    `etf_close_on` is the close every factor ETF must have a price on (the as-of close of a held
    book); None for a flat book's history, whose dates are all earlier and whose ETF returns
    `readout` checks on every window. `pnl_through` is the attribution's as-of close: the factor
    P&L reads each held close's next session up to it (team lead, 2026-11-11/12).

    `flat_close` (a flat book's as-of close, `_factor_flat`): when the book closed flat on that
    very session, its factor P&L E(last held close) x f(as-of) needs every factor ETF's return at
    the as-of. If one is not in the fetch, that term alone is UNMEASURED and named (the third
    value), and the P&L is read through the session before it; the FLAT reading needs no price
    and stands (the team lead's instruction for this PR)."""
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
    term_why = None if flat_close is None else _asof_term_gap(px, fs, P, flat_close)
    if term_why is not None:
        pnl_through = flat_close - dt.timedelta(days=1)   # every session before the as-of; the as-of term is named
    try:
        ro = ER.readout(px, P, groups, fs=fs, partial=True, pnl_through=pnl_through)
    except ER.NoInputsError as e:
        raise _NotRead(f"{e}" + ("; fetch: " + "; ".join(f"{t} ({failed[t]})" for t in held_failed)
                                 if held_failed else "")) from e
    return ro, failed, term_why


def _asof_term_gap(px: pd.DataFrame, fs: ER.FactorSet, P: pd.DataFrame, last: dt.date) -> str | None:
    """Why the factor P&L of a flat book's as-of session cannot be read, or None (`_read`).

    There is such a term only when the book's last held close is the NYSE session just before
    the as-of (it closed flat on the as-of itself); a book that went flat earlier has no exposure
    going into the as-of session, so that session's factor P&L is not missing, it is not there.
    The term needs each factor ETF's return at the as-of: a finite close on the as-of and on the
    price cache's session before it (`exposure_readout.returns_panel` divides one by the other)."""
    held = pd.DatetimeIndex(pd.to_datetime(P["date"]).unique()).sort_values()
    last_held = held[-1].date()
    after = ER.nyse_sessions(last_held + dt.timedelta(days=1), last)
    if not len(after) or after[0] != pd.Timestamp(last):
        return None
    t = pd.Timestamp(last)
    dates = pd.DatetimeIndex(pd.to_datetime(px["date"]).unique()).sort_values()
    if t not in dates:
        return f"the price fetch has no row on {last} for any ticker, so no factor ETF return at that close was read"
    prev = dates[dates.get_loc(t) - 1]
    rows = px.assign(_d=pd.to_datetime(px["date"]))
    gone = []
    for e in fs.etfs:
        for d in (prev, t):
            c = rows.loc[(rows["ticker"] == e) & (rows["_d"] == d), "close"].to_numpy(float)
            if len(c) != 1 or not np.isfinite(c[0]):
                gone.append(f"{e} (no close on {d.date()})")
    if not gone:
        return None
    return f"the factor ETF return(s) at the close of {last} are not in the price fetch: {'; '.join(gone)}"


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
# review of PR #82, 2026-11-11). Until the follow-up PR (team lead, 2026-11-11/12) the readout read
# E(t-1) x f(t) only on a positions date whose previous session was one, and `positions_frame`
# drops flat closes, so the session on which the book went flat was left out, and the label said
# so. Now the readout pairs each held close with its next session up to the attribution's as-of
# close (`exposure_readout.readout`, `pnl_through`), so that session is in the sum.
FACTOR_PNL_SESSIONS = ("each a session from the first trade to the as-of close whose previous close held a position, "
                       "a session that closed flat included (E(t-1) x f(t) needs only the previous close's book; team "
                       "lead, 2026-11-11/12)")


def _factor_pnl(ro, order, pdates: set, note: str | None = None) -> tuple[list[str], dict]:
    """The cumulative factor P&L's line and JSON fields: the book's summed factor P&L per factor,
    labelled with the sessions it covers (FACTOR_PNL_SESSIONS: their count, first and last) and
    how many were read on a PARTIAL previous-session book.

    NEVER SILENT WHEN THERE IS NONE (second review of PR #82, 2026-11-11). With no session held
    at both its previous close and its own (a book held, then flat, then held again: the review's
    interlude), the readout has no factor P&L row; before that review the block then printed no
    line at all and its JSON said `factor_pnl: null` with no reason. Now the line says it was not
    read and why, and `factor_pnl_why` carries the same. No figure changes: the sums are the
    readout's own, over the same rows.

    Since the follow-up PR (team lead, 2026-11-11/12) a flat-entry session is read, so the held ->
    flat -> held interlude has its row; a block with none is one whose only held close is the
    as-of close (the first trade's own session), or a flat block whose one term is the as-of
    session's and could not be read (`note`, from `_factor_flat`)."""
    fp = ro.factor_pnl
    if not len(fp):
        why = ("no session from the first trade to the as-of close followed a close that held a position (the only "
               "held close is the as-of close), so no E(t-1) x f(t) was read") if note is None else \
              f"no session before the as-of close followed a close that held a position, and {note}"
        return [f"Cumulative factor P&L not read: {why}"], {"factor_pnl": None, "factor_pnl_why": why}
    book_rows = fp[fp["scope"] == "book"]
    pnl = {k: float(book_rows[book_rows["factor"] == k]["pnl_summed"].sum()) for k in order}
    on_partial = int(book_rows[book_rows["prev"].map(lambda d: pd.Timestamp(d).date().isoformat()).isin(pdates)]
                     ["date"].nunique()) if pdates else 0
    sessions = sorted({pd.Timestamp(d).date().isoformat() for d in book_rows["date"]})
    line = (f"Cumulative factor P&L (book, E(t-1) x f(t), model reading) over {len(sessions)} session(s), "
            f"{sessions[0]} to {sessions[-1]}, {FACTOR_PNL_SESSIONS}: "
            + ", ".join(f"{k} {v:+,.2f}" for k, v in pnl.items())
            + (f" ({on_partial} session(s) on a PARTIAL previous-session book)" if on_partial else "")
            + (f"; not in it: {note}" if note else ""))
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
    history since the first trade (the review-flag counts over the earlier held closes, and the
    factor P&L of each session after one, up to the as-of: the session the book closed flat
    included, team lead 2026-11-11/12) is still read, and every line of it says which dates it
    covers; that as-of term needs the factor ETFs' returns at the as-of, and without them it is
    UNMEASURED in its own line, named (`_read`, `_asof_term_gap`); a name left
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
        ro, failed, term_why = _read(fs, P, groups, first=first, asof=asof, price_fetcher=price_fetcher,
                                     etf_close_on=None, pnl_through=last, flat_close=last)
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
    note = None
    if term_why is not None:
        note = (f"the factor P&L of the as-of session {last}, E({held[-1]}) x f({last}), the session the book closed "
                f"flat, is UNMEASURED: {term_why}")
        lines.append(f"Factor P&L of the as-of session {last} UNMEASURED: the book held positions at the close of "
                     f"{held[-1]} and closed flat at {last}, so that session's factor P&L is E({held[-1]}) x f({last}), "
                     f"and {term_why}")
        out["asof_term_why"] = term_why
    pnl_lines, pnl_out = _factor_pnl(ro, order, pdates, note)
    lines.extend(pnl_lines)
    if excluded:
        lines.append(_earlier_note(excluded, f"no severity: the book holds nothing at the close of {last}"))
    out.update(history=history, history_dates=[held[0], held[-1]], **pnl_out)
    if excluded:
        out.update(partial_dates=_partial_dates(excluded), earlier_exclusions=excluded)
    return out


def _factor_report(ro, fs: ER.FactorSet, book: str, last: dt.date, partial: dict | None = None,
                   excluded: list[dict] | None = None, unreconciled: bool = False) -> dict:
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
    as-of reading).

    With `unreconciled` (the attribution's rebuild does not reconcile to the official EOD
    change; team lead, 2026-11-11/12, `build_factor`) the status is UNRECONCILED, never OK or
    PARTIAL; `reading_status` keeps which of the two the reading would otherwise be, the first
    line says why, and every flag says "(UNRECONCILED)", in the JSON as in the text, as PARTIAL
    labels its flags. No figure changes."""
    ex = ro.exposure
    if pd.Timestamp(ex["date"].max()) != pd.Timestamp(last):
        raise ER.ReadoutError(f"the readout's last date {pd.Timestamp(ex['date'].max()).date()} is not the as-of "
                              f"close {last}: an earlier close's reading is never shown as the as-of one")
    last = pd.Timestamp(last)
    excluded = excluded or []
    today = ex[ex["date"] == last].set_index("factor")
    pdates = set(_partial_dates(excluded))
    lab = " (PARTIAL)" if partial else ""
    ulab = " (UNRECONCILED)" if unreconciled else ""
    def fac(k):
        r = today.loc[k]
        return {"exposure_usd": float(r["exposure_usd"]), "exposure_frac": float(r["exposure_frac"]),
                "contrib_of_target": float(r["contrib_of_target"]), "t_stat": float(r["t_stat"]),
                "review": str(r["review"]) + lab + ulab, "factor_vol": float(r["factor_vol"])}
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
    if unreconciled:
        lines.insert(0, f"Factor exposure UNRECONCILED (team lead, 2026-11-11/12): every reading below is on the fill "
                        f"rebuild's positions at the close of {last.date()}, and that rebuild does not reconcile to "
                        f"Alpaca's official EOD change (the attribution's RECONCILIATION FAILED line names the "
                        f"session(s)), so they are not shown to be the account's positions; each flag says "
                        f"UNRECONCILED. risk_daily checks the positions against the collector's account record")
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
    reading = "PARTIAL" if partial else "OK"
    out = {"status": UNRECONCILED if unreconciled else reading, "asof": last.date().isoformat(),
           "headline": fs.headline, "review_line": review_line,
            "factors": factors, "history": history, "split": split, "factor_pnl": pnl_out["factor_pnl"],
            "lines": lines, "gross_usd": float(tv["gross_usd"]), "net_usd": float(tv["net_usd"]),
            "total_of_target": float(tv["total_of_target"])}
    if unreconciled:
        out.update(reading_status=reading, reconciled=False)
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
    """The report's markdown. When the session read is not the as-of the job ran for (Alpaca's EOD
    history had no point for it yet: `build_attribution` reads the latest session it has), the
    title and the line under the status say so in capitals (team lead, 2026-11-11/12, on the
    third review of PR #82: the as-of session must be unmistakable). Before that the title said
    "as-of D" over figures that were all D-1's, and only a line inside the attribution section
    said otherwise. On any other night the markdown is unchanged, byte for byte."""
    read = rep.get("session_read")
    late = read is not None and read != rep["asof"]
    title = f"# P&L attribution and factor exposure, {rep['book']}, as-of {rep['asof']}"
    out = [title + (f": READ AT THE CLOSE OF {read}, NOT {rep['asof']}" if late else ""), "",
           f"Generated {rep['generated_at']} (report only; nothing here touches an order; zero trials).",
           f"Overall: **{rep['status']}**."]
    if late:
        out.append(f"**Alpaca's EOD history had no point for {rep['asof']} when this ran, so every figure below, the "
                   f"attribution and the factor exposure, is of the close of {read}, its latest point; nothing here is "
                   f"read for {rep['asof']}.**")
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
    if res is not None:                          # every factor status, for risk_daily's cross-check (`rebuild_positions`)
        try:
            factor["rebuild_positions"] = rebuild_positions(res)
        except Exception as e:                   # a bug: named, and risk_daily then cannot cross-check (UNMEASURED)
            factor["rebuild_positions_why"] = f"{type(e).__name__}: {e}"
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
    if att.get("effective_session") is not None:  # the session read: the as-of's, or the latest EOD point before it
        rep["session_read"] = att["effective_session"]
    write_atomic(out_dir / f"{asof.isoformat()}.json", json.dumps(rep, indent=1, default=str))
    write_atomic(out_dir / f"{asof.isoformat()}.md", render_md(rep))
    code = exit_code(incomplete=incomplete, reconciled=att.get("reconciled"))   # after both files exist
    read = rep.get("session_read")
    late = f" (READ AT THE CLOSE OF {read}, NOT {asof})" if read not in (None, asof.isoformat()) else ""
    print(f"pnl_report {book} {asof}: {status}{late}; exit {code}; wrote {out_dir / f'{asof.isoformat()}.md'}")
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
