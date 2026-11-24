"""EVENTS trial 2: NAV-tender participation, ETF-hedged (the trial script the pre-registration names).

    python3 scripts/events/nav_tender_trial.py stage0 --edgar-only   # Stage 0, part A: EDGAR readings only
    python3 scripts/events/nav_tender_trial.py stage0                 # Stage 0, all of it (needs the staged CRSP)
    python3 scripts/events/nav_tender_trial.py fit                    # stages 1-5 (refuses without Stage-0 rulings)
    python3 scripts/events/nav_tender_trial.py holdout                # stage 7, once, after the fit verdict commit
    python3 -m pytest scripts/events/tests/test_nav_tender_trial.py

    # credentialed staging, run by the team lead (agents never load the env file):
    export QUANTT_ENV_FILE=/abs/path/config/.env
    python3 scripts/events/nav_tender_trial.py stage --ibkr /abs/path/usa.txt

WHAT THIS IS
------------
`results/events/PREREG_NAV_TENDER_2026-10-19.md`, approved by the team lead on
2026-10-19 on all twelve defaults: EVENTS trial 2, bar N = 6. After a closed-end
fund announces an issuer tender at k% of NAV, buy it at the close of day 0 + 1,
tender every share, take P_final on the accepted fraction pi, sell the returned
residual at the close of F + 1, and short the asset-class ETF by the fund's
pre-event Dimson beta for the whole hold. Every rule here is the
pre-registration's; the section it comes from is cited beside it. Nothing is
swept and nothing is chosen with sight of a return.

NO NEW BACKTESTER (prereg §5.5)
-------------------------------
This module builds three matrices and hands them to existing code, unchanged:
  H  sessions x (one column per event, one per hedge ETF): decisions;
  R  CRSP total returns, with the tender session written into each event's
     column (§5.3);
  Q  the notional actually traded each session.
`band_frontier.evaluate(H, R)` applies H.shift(2) (decide t, fill at the close
of t + 1, earn t + 2), `band_frontier._stats(pnl, Q.abs().sum(axis=1))` gives
gross and the 5/15/30bp nets, `band_frontier.borrow_charge` the IBKR hedge
borrow, `validate._dsr` the bar, `w4_artifacts.nw_t/stationary_boot` and
`convert_issuance.cluster_t` the inference, `e1_etf_hedge_gate.windows/spans/
dimson` the hedge ratio, `event_store.observed_at/research_decision_time`
day 0, and the census's `parse_tender_offer/parse_tender_result/groups/
HEDGE_ETF` the terms. New code here: the event table, the readers the census
lacks (the final purchase price P_final, the pricing session, the final expiry,
terminations), the matrices, and the report.

THE ALIGNMENT, STATED (H7; asserted in `build_matrices` and `assert_alignment`)
------------------------------------------------------------------------------
* day 0 = the first NYSE session t whose 22:00 ET research decision time is at
  or after the day-0 filing's `observed_at` = max(the SEC header's
  ACCEPTANCE-DATETIME, 06:00 ET on EDGAR's filing date). The header, never the
  submissions API (prereg §4.2).
* H[t, event] = u for every decision row t in [day 0, F - 1] and 0 elsewhere.
  Under shift(2) the position is bought at the close of day 0 + 1, first earns
  on day 0 + 2, and is sold at the close of F + 1 (decided at F), so F + 1 is
  its last P&L session. The hedge column carries -beta * u on the same rows.
* pi and P_final enter R on the pricing session X_p only. No row of H depends
  on them; F depends on the outcome filing's `observed_at` alone (§5.3).
* beta uses fund and ETF returns on spans that end before day 0 - 42 valid
  sessions (`e1_etf_hedge_gate.windows`), asserted before day 0.
* The fit reader is `crsp_events.daily`, which cannot return a 2023 row; the
  holdout reader is a separate function that refuses to run until the fit
  verdict is committed (prereg §4.4 DG-NT-3, §7).

STAGE 0 AND THE RULINGS BLOCK (`.claude/skills/prereg/SKILL.md` §4b)
--------------------------------------------------------------------
Stage 0 writes a flag table (`results/events/nav_tender/stage0_flags_<date>.csv`,
keys check, ticker, date) and the trial calls `data_guards.require_stage0_rulings`
before it forms ANY P&L, fit or holdout. A flag nobody must answer is not a
check: C4's IGR bars were flagged and never ruled, and cost -10.87% of capital.
The 20% unread-outcome gate (§4.3) halts before any return exists; so does a
missing input. Each halt raises `Stage0Halt` naming what the team lead must do.

LICENSING AND THE PUBLIC REPOSITORY
-----------------------------------
CRSP is licensed: tracked outputs carry aggregates and EDGAR facts only. Per-event
P&L, prices, permnos and betas go to `results/events/nav_tender/_cache_trial/`
(gitignored by `results/**/_cache_*`).

ENVIRONMENT: `compute.use_numexpr` off at import (DG-NT-6,
scripts/events/numexpr_fault.py).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("compute.use_numexpr", False)   # DG-NT-6

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:  # run as a script, not -m
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events"
TRIAL_DIR = OUT / "nav_tender"
CACHE = TRIAL_DIR / "_cache_trial"                       # gitignored: licensed per-event rows
STAMP = "2026-10-19"                                      # the approval date; the files of this run carry it
EVENTS_CSV = OUT / "cef_corp_action_events.csv"
EPISODES_CSV = OUT / "edgar_cef_bdc_episodes.csv"
FILINGS_GZ = OUT / "edgar_cef_bdc_filings.csv.gz"         # the fetcher's filings table (gitignored)
COND_CSV = OUT / "conditional_tender_census.csv"
SUMMARY_JSON = OUT / "cef_corp_action_summary.json"
DG1_READINGS = TRIAL_DIR / f"dg_nt1_readings_{STAMP}.csv"   # tracked: the Stage-0 re-dating reads (§4.2)
DG4_READS = TRIAL_DIR / "dg_nt4_reads.json"                 # tracked: the hedge-availability read (§4.4)
RULINGS = TRIAL_DIR / f"nav_tender_stage0_rulings_{STAMP}.csv"
FLAGS = TRIAL_DIR / f"stage0_flags_{STAMP}.csv"
STAGE0_EVENTS = TRIAL_DIR / f"stage0_events_{STAMP}.csv"    # tracked: EDGAR facts per event, no CRSP field
STAGE0_JSON = TRIAL_DIR / f"stage0_{STAMP}.json"
FIT_JSON = TRIAL_DIR / f"fit_{STAMP}.json"
HOLDOUT_JSON = TRIAL_DIR / f"holdout_{STAMP}.json"

# ------------------------------------------------------------------ the declared constants
SCOPE_START = pd.Timestamp("2010-01-01")
HOLDOUT_START = pd.Timestamp("2023-01-01")      # = band_frontier.HOLDOUT_START (a test pins it)
FIT_LAST_SESSION = pd.Timestamp("2022-12-30")
HOLDOUT_LAST_SESSION = pd.Timestamp("2024-12-31")   # CRSP's last row (decision 8)
CUTOFF_SESSIONS = 3          # election cut-off: entry fill at least 3 sessions before expiry (decision 6)
RESIDUAL_LAG = 5             # residual sold no earlier than decided 5 sessions after pricing (decision 6)
EXCLUSION_MAX = 0.20         # §4.3: more than 20% of fit events unread -> halt, no trial spent
N_BAR = 6                    # decision 1
DSR_PASS = 0.95
T_BAR = 2.0                  # stages 1 and 3
ALPHA_T_BAR = 3.0            # stage 4
BETA_MAX = 0.10              # stage 4, summed |beta| at the vol target
STAGE3_BP = 15               # decision 5
COSTS_BP = (5, 15, 30)
ELECTION_FEE_USD = 100.0     # Alpaca, per unique election (decision 4; §12ac)
FEE_CAPITALS = (None, 1_000_000.0)   # None = the spec's capital_usd; $1m beside it (§6)
NW_LAGS = 21
SEED = 20261019
BOOT_REPS = 10_000
BOOT_BLOCKS = (21, 63)
PLACEBO_DRAWS = 1_000
PLACEBO_CLEAR = 126          # no tender episode of the fund within 126 sessions of a placebo day 0
ABS_RET_FLAG = 0.50          # quality screen (§4.4)
EPISODE_FAR_DAYS = 60
LATE_DOC_DAYS = 60           # day 0 this far before the offer document: read at Stage 0 (DG-NT-1)
COND_WINDOW_DAYS = 180       # a tender this soon after a triggered N1 window follows it
ERAS = (("2010-14", "2010-01-01", "2014-12-31"), ("2015-19", "2015-01-01", "2019-12-31"),
        ("2020-22", "2020-01-01", "2022-12-31"))
HOLDOUT_ERA = ("2023-24", "2023-01-01", "2024-12-31")
CREDIT_CLASSES = ("high_yield", "loans", "muni", "multisector", "preferred", "em_debt", "convertible")


class Stage0Halt(RuntimeError):
    """Stage 0 cannot finish, or finished with something the team lead must rule on. No P&L exists."""


class TrialError(RuntimeError):
    """A rule of the pre-registration could not be applied as written (names the event)."""


# ===================================================================== calendar

def is_session(d) -> bool:
    from ops.schedule.nyse_calendar import is_trading_day
    return bool(is_trading_day(pd.Timestamp(d).date()))


def session_on_or_after(d) -> pd.Timestamp:
    from ops.schedule.nyse_calendar import next_trading_day
    d = pd.Timestamp(d).normalize()
    return d if is_session(d) else pd.Timestamp(next_trading_day(d.date()))


def session_on_or_before(d) -> pd.Timestamp:
    from ops.schedule.nyse_calendar import previous_trading_day
    d = pd.Timestamp(d).normalize()
    return d if is_session(d) else pd.Timestamp(previous_trading_day(d.date()))


def add_sessions(d, n: int) -> pd.Timestamp:
    """The session n sessions after (n > 0) or before (n < 0) the SESSION d."""
    from ops.schedule.nyse_calendar import next_trading_day, previous_trading_day
    d = pd.Timestamp(d).normalize()
    if not is_session(d):
        raise TrialError(f"add_sessions: {d.date()} is not an NYSE session")
    x = d.date()
    for _ in range(abs(n)):
        x = next_trading_day(x) if n > 0 else previous_trading_day(x)
    return pd.Timestamp(x)


def sessions_between(a, b) -> pd.DatetimeIndex:
    """NYSE sessions in [a, b]."""
    days = pd.bdate_range(pd.Timestamp(a).normalize(), pd.Timestamp(b).normalize())
    return pd.DatetimeIndex([d for d in days if is_session(d)])


def day0_session(observed_utc: datetime) -> pd.Timestamp:
    """The first NYSE session t with research_decision_time(t) >= observed_at (prereg §4.2)."""
    from scripts.events.event_store import ET, research_decision_time
    t = session_on_or_after(pd.Timestamp(observed_utc.astimezone(ET).date()))
    while research_decision_time(t.date()) < observed_utc:
        t = add_sessions(t, 1)
    return t


# ===================================================================== EDGAR reading

_ACCEPT_RE = re.compile(r"<ACCEPTANCE-DATETIME>\s*(\d{14})")
_FILED_RE = re.compile(r"FILED AS OF DATE:\s*(\d{8})")
MON = (r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
       r"\s*\d{1,2}\s*,\s*\d{4}")


def header_times(raw: str) -> tuple[str, date]:
    """(ACCEPTANCE-DATETIME as 14 digits, EDGAR's filing date) from a complete submission's header."""
    head = raw[: raw.find("</SEC-HEADER>")] if "</SEC-HEADER>" in raw else raw[:6000]
    a, f = _ACCEPT_RE.search(head), _FILED_RE.search(head)
    if not a or not f:
        raise TrialError("no ACCEPTANCE-DATETIME or FILED AS OF DATE in the submission header")
    return a.group(1), datetime.strptime(f.group(1), "%Y%m%d").date()


def observed_from_raw(raw: str) -> tuple[datetime, str | None]:
    """(observed_at, note). `event_store.observed_at` raises when EDGAR's filing date precedes
    the acceptance date (a filing-date adjustment). The prereg's rule is the max of the two
    instants (§4.2), which is then the acceptance time itself; it is applied as written and the
    note makes the event a Stage-0 flag for the team lead."""
    from scripts.events.event_store import TimeKeyError, UTC, observed_at, parse_header_acceptance
    acc14, filed = header_times(raw)
    acc = parse_header_acceptance(acc14)
    try:
        return observed_at(acc, filed), None
    except TimeKeyError as e:
        return acc.astimezone(UTC), f"filing date {filed} precedes acceptance {acc14} ET; observed_at = acceptance ({e})"


def parse_mon(s: str) -> pd.Timestamp:
    from scripts.events.cef_corp_action_census import parse_date
    return parse_date(re.sub(r"(?<=[A-Za-z])(?=\d)", " ", s))


_FEE_BLOCK_RE = re.compile(r"CALCULATION\s+OF\s+FILING\s+FEE.{0,2500}?(?:Check\s+the\s+box|Amount\s+Previously\s+Paid)",
                           re.I | re.S)


def without_fee_block(t: str) -> str:
    """The text with the cover page's filing-fee calculation blanked. That block prices the
    ORIGINAL transaction valuation (often the NAV weeks before expiry: DSU 2018's results
    amendment still prints $12.44 at March 12 for an offer that expired April 17), so it is
    never read as the final price unless its date is the pricing date (`final_price`)."""
    return _FEE_BLOCK_RE.sub(" ", t)


def fee_block(t: str) -> str:
    m = _FEE_BLOCK_RE.search(t)
    return m.group(0) if m else ""


def norm_text(t: str) -> str:
    """Abbreviations that end in a full stop ("5:00 p.m. New York time") read as sentence ends to
    the readers below; they are written without the stops. Nothing else changes."""
    t = re.sub(r"\b([ap])\.\s?m\.", r"\1m", t, flags=re.I)
    return re.sub(r"\b(Inc|Co|Corp|Ltd|No|U\.S)\.", r"\1", t)


_EXPIRED_RE = re.compile(
    r"\b(?:expired|terminated|closed(?!-))\b(?:(?!\.\s)[^;]){0,140}?(?:\bon\s+)?(?:(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\s*,?\s*)?"
    r"(?P<d>" + MON + ")", re.I)
_SCHEDULED_RE = re.compile(r"(?:scheduled|originally|previously|was\s+to)\s+(?:to\s+)?(?:expire|terminate)", re.I)


def final_expiry(results_text: str, lo: pd.Timestamp, hi: pd.Timestamp) -> tuple[pd.Timestamp | None, str | None]:
    """The offer's final expiry as the results filing states it ("The Offer expired at 5:00
    p.m. ... on April 17, 2018"; "which offer expired on June 13, 2012"; PCF 2019's "The
    Offer terminated at 5:00 p.m. ... on March 18, 2019"). Only dates in [lo, hi] (the offer
    document's date to the results filing's date) are believed; a "scheduled to expire"
    clause is skipped. Two different believed dates -> None (a stated gap)."""
    t = norm_text(without_fee_block(results_text))
    found = []
    for m in _EXPIRED_RE.finditer(t):
        pre = t[max(0, m.start() - 60): m.start()]
        pre = re.split(r"\.\s", pre)[-1]                 # the same sentence only
        if _SCHEDULED_RE.search(pre):
            continue
        try:
            d = parse_mon(m.group("d"))
        except ValueError:
            continue
        if lo <= d <= hi:
            found.append((d, re.sub(r"\s+", " ", t[max(0, m.start() - 80): m.end() + 10])))
    if not found:
        return None, None
    ds = {d for d, _ in found}
    if len(ds) > 1:
        return None, "conflicting expiry dates: " + " | ".join(s for _, s in found[:3])
    return found[0][0], found[0][1]


_EXTEND_RE = re.compile(r"extend\w*\b(?:(?!\.\s)[^;]){0,200}?\b(?:to|until|through)\s+(?:(?:Mon|Tues|Wednes|Thurs|Fri)day\s*,?\s*)?"
                        r"(?:[^;.]{0,40}?\bon\s+)?(?P<d>" + MON + ")", re.I)


def extension_dates(text: str, lo: pd.Timestamp, hi: pd.Timestamp) -> list[tuple[pd.Timestamp, str]]:
    """Each "extended ... to/until <date>" in an amendment, dates in [lo, hi]."""
    out = []
    for m in _EXTEND_RE.finditer(norm_text(without_fee_block(text))):
        try:
            d = parse_mon(m.group("d"))
        except ValueError:
            continue
        if lo <= d <= hi:
            out.append((d, re.sub(r"\s+", " ", m.group(0))[:240]))
    return out


# --- the final purchase price (P_final): read from the results filing, never estimated (§4.3)
# A per-share price: digits, a decimal point and decimals, so an aggregate printed with
# thousands separators ("$278,774,260") cannot match; and inside [PRICE_MIN, PRICE_MAX].
_PRICE = r"\$\s?(?P<p>\d{1,4}\.\d{2,5})(?!\d)"
PRICE_MAX = 2_000.0
PRICE_MIN = 0.50          # a par value ("$0.001 per share") is never a share price
_NS = r"(?:(?!\.\s)[^;$])"          # within one sentence, before the next dollar sign
_PF_PATTERNS = [
    # "has accepted 14,143,225 shares for payment at a price equal to $5.98 per share";
    # "accepted 1,123,817 shares for payment on July 18, 2012, at $15.31 per share";
    # "338,382 Shares were accepted for purchase ... at a price of $4.9823 per share"
    ("accepted_at", re.compile(r"accept\w*\b" + _NS + r"{0,220}?\bat\s+(?:a\s+(?:cash\s+)?(?:purchase\s+)?price\s+"
                               r"(?:per\s+(?:common\s+)?share\s+)?(?:equal\s+to|of)\s+|the\s+(?:purchase\s+)?price\s+of\s+)?"
                               + _PRICE, re.I)),
    # "The Shares were repurchased at a price of $4.86"; "will be repurchased as promptly as
    # practicable at $16.89 per share"
    ("repurchased_at", re.compile(r"(?:re)?purchased\b" + _NS + r"{0,70}?\b(?:at|for)\s+(?:a\s+(?:cash\s+)?price\s+"
                                  r"(?:per\s+(?:common\s+)?share\s+)?(?:equal\s+to|of)\s+)?" + _PRICE, re.I)),
    # "The purchase price for tendered shares is $5.43 per share"; "The purchase price of $22.47
    # per share"; "a repurchase offer price of $9.47"; "The purchase price per share is
    # determined to be $4.9823"
    ("purchase_price_is", re.compile(r"(?:re)?purchase\s+(?:offer\s+)?price\s+(?:per\s+(?:common\s+)?share\s+|for\s+(?:the\s+)?"
                                     r"(?:(?:validly\s+|properly\s+)?tendered\s+|accepted\s+)?shares\s+)?(?:is|was|will\s+be|of|equals?|is\s+equal\s+to|"
                                     r"is\s+determined\s+to\s+be|was\s+determined\s+to\s+be|has\s+been\s+determined\s+to\s+be)\s+"
                                     + _PRICE, re.I)),
    # "elected to purchase all shares tendered at a price of $9.25 per Share"
    ("elected_purchase", re.compile(r"elected\s+to\s+purchase\b" + _NS + r"{0,120}?\bat\s+a\s+price\s+of\s+" + _PRICE, re.I)),
    # "at a price per share of $14.07 (the "Purchase Price")"
    ("price_per_share_of", re.compile(r"at\s+a\s+price\s+per\s+share\s+(?:of|equal\s+to)\s+" + _PRICE, re.I)),
    # "... per share calculated as of the close ... on September 6, 2017, which is equal to
    # $10.535 per share"; "at the NAV ... on the expiration date, October 7, 2019, which was
    # $23.1002 per share"
    ("which_is_equal", re.compile(r"(?:net\s+asset\s+value|NAV)\b" + _NS + r"{0,220}?which\s+(?:is|was)\s+(?:equal\s+to\s+)?"
                                  + _PRICE, re.I)),
]
_TABLE_HEAD_RE = re.compile(r"Purchase\s+Price", re.I)


_SENT_END_RE = re.compile(r"\.\s+(?=[A-Z(“\"])")


def _date_after(text: str, start: int, span: int = 320) -> tuple[pd.Timestamp | None, str | None]:
    """The NAV date printed with a price statement: the first "<Month> <d>, <yyyy>" after `start`
    in the SAME sentence, or in the next sentence when that one is about the price's NAV ("This
    purchase price is 98% of the Fund's net asset value per share of $11.25 as of the close ... on
    July 2, 2014"). A payment or settlement date ("for payment on July 18") is skipped. Anything
    further away (a press-release dateline, HERZ 2021) is not the NAV date: None."""
    w = text[start: start + span]
    ends = [m.start() for m in _SENT_END_RE.finditer(w)]
    stop = ends[0] if ends else len(w)
    if ends:
        nxt = w[ends[0] + 1: ends[1] if len(ends) > 1 else len(w)]
        if re.search(r"net\s+asset\s+value|\bNAV\b", nxt, re.I) and re.search(r"purchase\s+price|price", nxt, re.I):
            stop = ends[1] if len(ends) > 1 else len(w)
    w = w[:stop]
    for m in re.finditer(MON, w):
        pre = w[max(0, m.start() - 40): m.start()]
        if re.search(r"payment\s+on\s*$|on\s+or\s+about\s*$|paid\s+on\s*$|settle\w*\s+on\s*$", pre, re.I):
            continue
        try:
            return parse_mon(m.group(0)), re.sub(r"\s+", " ", w[: m.end()])
        except ValueError:
            continue
    return None, None


@dataclass
class PriceRead:
    p_final: float | None
    how: str | None
    span: str | None
    nav_date: pd.Timestamp | None       # the NAV date the statement gives (the pricing session, X_p)
    candidates: int = 0


def _fmt_count(n: float) -> list[str]:
    """The ways a share count is printed: 1,123,817 / 1,123,817.00 / 1123817."""
    whole = f"{int(round(n)):,}"
    out = [re.escape(whole), re.escape(whole.replace(",", ""))]
    if abs(n - round(n)) > 1e-9:
        out.insert(0, re.escape(f"{n:,.3f}".rstrip("0").rstrip(".")))
    return out


def _joint_reads(body: str, ticker: str | None, accepted: float | None) -> list[tuple[float, str, str, int]]:
    """Fund-anchored price statements in a joint release (several funds, several prices):
    "$15.12 for DHG and $8.64 for LBF"; "$14.65, $14.42 and $12.01 per common share for GLV, GLQ
    and GLO, respectively"; the fund's ticker row of a results table; a statement that follows
    the fund's own accepted share count ("The Fund has accepted 11,114,143 shares ... at a price
    equal to $12.15")."""
    out = []
    if ticker:
        tk = re.escape(ticker)
        body = re.sub(r"\$\s?0\.0\d+", " ", body)          # par values
        for m in re.finditer(_PRICE + r"\s+for\s+(?:the\s+)?" + tk + r"\b", body):
            out.append((float(m.group("p")), f"price for {ticker}", m.group(0), m.end()))
        P1 = r"\$\s?\d{1,4}\.\d{2,5}"
        lst = re.compile(r"(" + P1 + r"(?:\s*,\s*" + P1 + r")*\s*,?\s*and\s+" + P1 + r")\s+per\s+(?:common\s+)?share\s+"
                         r"for\s+([A-Z]{2,5}(?:\s*,\s*[A-Z]{2,5})*\s*,?\s*and\s+[A-Z]{2,5})\s*,?\s*respectively")
        for m in lst.finditer(body):
            ps = [float(x) for x in re.findall(r"\$\s?(\d{1,4}\.\d{2,5})", m.group(1))]
            ts = re.findall(r"[A-Z]{2,5}", m.group(2))
            ts = [t for t in ts if t != "AND"]
            if len(ps) == len(ts) and ticker in ts:
                out.append((ps[ts.index(ticker)], f"'respectively' list, {ticker}", m.group(0), m.end()))
        row = re.compile(r"\b" + tk + r"\b(?:[^$A-Za-z]|\(\d\)){0,90}?" + _PRICE)
        for m in row.finditer(body):
            nums = re.findall(r"\d{1,3}(?:,\d{3})+", m.group(0))
            if len(nums) >= 2:      # a table row: tendered and purchased counts before the price
                out.append((float(m.group("p")), f"results table, {ticker} row", m.group(0), m.end()))
    if accepted:
        for pat in _fmt_count(accepted):
            for m in re.finditer(r"\b" + pat + r"\b" + _NS + r"{0,260}?" + _PRICE, body):
                out.append((float(m.group("p")), "statement after the fund's accepted count", m.group(0), m.end()))
            if out and out[-1][1].startswith("statement after"):
                break
    return out


def final_price(results_text: str, ticker: str | None, multi_fund: bool, expiry: pd.Timestamp | None,
                accepted: float | None = None) -> PriceRead:
    """P_final, the final purchase price per share, from the results filing (prereg §4.3).

    Single-fund filings, in order: (1) the narrative statements of `_PF_PATTERNS` anywhere in
    the filing outside the filing-fee block; (2) a results table (the fund's ticker row, or
    the first price after a "Purchase Price" header); (3) the filing-fee block, ONLY where its
    NAV date is the final expiry or the session after it (KF 2017 restates the valuation at
    the final price). Joint releases (`multi_fund`, the census's rule): only fund-anchored
    statements are believed -- the fund's own Rule 13e-4(c)(4) item block, then
    `_joint_reads`. In every tier all believed statements must agree to the fourth decimal,
    else the price is a gap. Returns the NAV date printed after the statement, when given.
    """
    from scripts.events.cef_corp_action_census import ITEM_BLOCK_CHARS, _ITEM_BLOCK_RE
    body = norm_text(without_fee_block(results_text))

    def scan(src: str):
        hits = []
        for how, rx in _PF_PATTERNS:
            for m in rx.finditer(src):
                p = float(m.group("p"))
                if not PRICE_MIN < p < PRICE_MAX:
                    continue
                d, _ = _date_after(src, m.end())
                hits.append((p, how, re.sub(r"\s+", " ", src[max(0, m.start() - 60): m.end() + 120]), d))
        return hits

    def verdict(hits, label):
        ps = {round(h[0], 4) for h in hits}
        if len(ps) == 1:
            dates = [h[3] for h in hits if h[3] is not None]
            return PriceRead(hits[0][0], f"{hits[0][1]} ({label})", hits[0][2], dates[0] if dates else None, len(hits))
        return PriceRead(None, f"conflicting prices in the {label}: {sorted(ps)}",
                         " | ".join(h[2] for h in hits[:3]), None, len(hits))

    if multi_fund:
        blk = _ITEM_BLOCK_RE.search(body)
        if blk:
            hits = scan(body[blk.end(): blk.end() + 4 * ITEM_BLOCK_CHARS])
            if hits:
                return verdict(hits, "item block")
        jr = _joint_reads(body, ticker, accepted)
        if jr:
            hits = [(p, how, re.sub(r"\s+", " ", sp), _date_after(body, end)[0]) for p, how, sp, end in jr]
            return verdict(hits, "joint release, fund-anchored")
        return PriceRead(None, "joint release, no fund-anchored price (a gap)", None, None, 0)
    hits = scan(body)
    if hits:
        return verdict(hits, "filing")
    jr = _joint_reads(body, ticker, None)
    if jr:
        hits = [(p, how, re.sub(r"\s+", " ", sp), None) for p, how, sp, end in jr]
        return verdict(hits, "results table")
    h = _TABLE_HEAD_RE.search(body)
    while h:
        w = body[h.end(): h.end() + 600]
        m = re.search(_PRICE, w)
        if m and re.search(r"pro[- ]?ration|tendered", body[max(0, h.start() - 600): h.start() + 600], re.I):
            return PriceRead(float(m.group("p")), "results table (Purchase Price column)",
                             re.sub(r"\s+", " ", body[max(0, h.start() - 200): h.end() + m.end()]), None, 1)
        h = _TABLE_HEAD_RE.search(body, h.end())
    fb = norm_text(fee_block(results_text))
    if fb and expiry is not None:
        m = re.search(_PRICE + r"\s*,?\s*\(?\s*(?:which\s+represents\s+)?\d{2,3}(?:\.\d+)?\s?%\s+of\s+(?:the\s+)?"
                      r"(?:Fund[’'`]?s\s+)?net\s+asset\s+value", fb, re.I)
        if m:
            d, _ = _date_after(fb, m.end(), 260)
            E = session_on_or_after(expiry)
            if d is not None and (d == pd.Timestamp(expiry) or d == add_sessions(E, 1)):
                return PriceRead(float(m.group("p")), "filing-fee block dated at the final expiry",
                                 re.sub(r"\s+", " ", fb[max(0, m.start() - 120): m.end() + 200]), d, 1)
    return PriceRead(None, None, None, None, 0)


# --- terminations (prereg §4.3, §5.3: pi = 0, the whole position sold after the termination is public)
_TERMINATED_RE = re.compile(
    r"(?:(?:has|have|had)\s+(?:determined\s+to\s+|decided\s+to\s+|elected\s+to\s+)?(?:terminated|withdrawn|cancell?ed)\s+"
    r"(?:the|its|their)\s+(?:cash\s+)?(?:self[- ])?(?:tender\s+)?offer"
    r"|(?:tender\s+)?offer\s+(?:has\s+been|was|is\s+being|had\s+been)\s+(?:terminated|withdrawn|cancell?ed)\b(?!\s+at\s+\d)"
    r"|(?:decided|determined|elected|voted)\s+(?:not\s+to\s+proceed|to\s+(?:terminate|withdraw|cancel))\s+(?:with\s+)?"
    r"(?:the|its)\s+(?:cash\s+)?(?:tender\s+)?offer)", re.I)


def termination(text: str) -> str | None:
    """The span that says the offer was terminated or withdrawn, or None. "The Offer terminated
    at 5:00 p.m. ..." is an expiry (PCF 2019), not a termination, and does not match."""
    m = _TERMINATED_RE.search(without_fee_block(text))
    return re.sub(r"\s+", " ", text[max(0, m.start() - 120): m.end() + 120]) if m else None


# --- the pricing session from the offer's own terms (used only when the results filing names no NAV date)
_NEXT_BD_RE = re.compile(r"(?:next|first)\s+business\s+day\s+(?:after|following|immediately\s+following)\s+(?:the\s+)?"
                         r"(?:date\s+(?:on\s+which\s+)?(?:the\s+)?(?:tender\s+)?offer\s+expires|day\s+(?:the\s+)?(?:tender\s+)?offer\s+expires|"
                         r"expiration\s+date|termination\s+date)", re.I)
_ON_EXPIRY_RE = re.compile(r"net\s+asset\s+value\b(?:(?!\.\s)[^;]){0,160}?\b(?:on|as\s+of)\s+(?:the\s+)?(?:Expiration\s+Date|"
                           r"date\s+(?:on\s+which\s+)?(?:the\s+)?(?:tender\s+)?offer\s+expires|day\s+(?:on\s+which\s+)?(?:the\s+)?"
                           r"(?:tender\s+)?offer\s+expires|expiration\s+date)", re.I)


def pricing_rule(offer_text: str) -> tuple[str | None, str | None]:
    """'next_bd' (NAV of the business day after expiry), 'expiry' (NAV of the expiry date), or None."""
    t = without_fee_block(offer_text)
    a, b = _NEXT_BD_RE.search(t), _ON_EXPIRY_RE.search(t)
    if a and not b:
        return "next_bd", re.sub(r"\s+", " ", t[max(0, a.start() - 120): a.end() + 20])
    if b and not a:
        return "expiry", re.sub(r"\s+", " ", t[max(0, b.start() - 40): b.end() + 20])
    if a and b:
        # Both phrasings appear (a summary and a definition): the NAV-anchored statement is the term.
        return "conflict", re.sub(r"\s+", " ", t[max(0, a.start() - 80): a.end()]) + " | " + \
            re.sub(r"\s+", " ", t[max(0, b.start() - 40): b.end()])
    return None, None


# ===================================================================== the event table

def load_inputs() -> dict:
    """The tracked census tables and the fetcher's filings table. A missing input raises naming it."""
    for p in (EVENTS_CSV, EPISODES_CSV, COND_CSV, SUMMARY_JSON):
        if not p.exists():
            raise Stage0Halt(f"{p.relative_to(REPO)} is missing (tracked input)")
    if not FILINGS_GZ.exists():
        raise Stage0Halt(f"{FILINGS_GZ.relative_to(REPO)} is missing: run "
                         "`python3 scripts/data/fetch_edgar_events.py --offline` (or the `stage` step)")
    ev = pd.read_csv(EVENTS_CSV, parse_dates=["ann_date", "expire", "doc_date", "nav_date"], low_memory=False)
    ep = pd.read_csv(EPISODES_CSV, parse_dates=["first_date", "last_date"])
    fl = pd.read_csv(FILINGS_GZ, parse_dates=["date_filed"])
    cond = pd.read_csv(COND_CSV, parse_dates=["window_end"])
    return {"events": ev, "episodes": ep, "filings": fl, "cond": cond,
            "summary": json.loads(SUMMARY_JSON.read_text())}


def base_events(inp: dict) -> pd.DataFrame:
    """The census's nav_tender rule, unchanged (prereg §4.1): every row of type nav_tender, with its
    tender episode (joined on the day-0 accession; a miss raises) and the screens the
    pre-registration names. The 44 `cef_universe.csv` funds are kept here and dropped later,
    counted."""
    from scripts.events import nav_tender_feasibility as nf
    nt = inp["events"][inp["events"]["type"] == "nav_tender"].copy()
    if nt.empty:
        raise Stage0Halt("no nav_tender rows in the census table")
    m = nf.attach_episodes(nt, inp["episodes"])
    m["merger_open"] = nf.merger_open(m, inp["episodes"]).values
    m["programme"] = nf.triggered_programme(m, inp["cond"], COND_WINDOW_DAYS).values
    m["late_doc"] = (m["doc_date"] - m["ann_date"]).dt.days > LATE_DOC_DAYS
    m["episode_far"] = (m["last_date"] - m["expire"]).dt.days.abs() > EPISODE_FAR_DAYS
    m["cik"] = m["cik"].astype(int)
    m["event_id"] = m["ann_accession"]
    m["label"] = [(t.split(";")[0] if isinstance(t, str) and t.strip() else (tk if isinstance(tk, str) else f"CIK{c}"))
                  for t, tk, c in zip(m["ticker_now"], m["ticker"], m["cik"])]
    return m.reset_index(drop=True)


def offer_filings(fl: pd.DataFrame, cik: int, first: pd.Timestamp, last: pd.Timestamp, doc_acc: str) -> dict:
    """The event's offer within its episode: the census's offer document (the episode's first
    SC TO-I), its amendments (every SC TO-I/A after it and before the episode's NEXT SC TO-I),
    and its results filing = the last of those amendments (prereg §4.3 "the offer and its last
    amendments"). An episode can hold two offers (the 8 'episode far' fit events); the census
    read the episode's LAST amendment, which for them belongs to a later offer."""
    g = fl[(fl["cik"] == cik) & (fl["kind"] == "tender") & (fl["date_filed"] >= first) & (fl["date_filed"] <= last)]
    g = g.sort_values(["date_filed", "accession"]).reset_index(drop=True)
    i0 = g.index[g["accession"] == doc_acc]
    if len(i0) != 1:
        raise TrialError(f"CIK {cik}: offer document {doc_acc} is not in its episode's filings")
    i0 = int(i0[0])
    later_offers = g.index[(g.index > i0) & (g["form"] == "SC TO-I")]
    stop = int(later_offers[0]) if len(later_offers) else len(g)
    own = g.iloc[i0 + 1: stop]
    amends = own[own["form"] == "SC TO-I/A"]
    return {"all": g, "amendments": amends, "results": amends.iloc[-1] if len(amends) else None,
            "later_offers": int(len(later_offers)), "pre_offer": g.iloc[:i0]}


def load_dg1_readings(path: Path | None = None) -> pd.DataFrame:
    """The Stage-0 hand readings of day 0 (DG-NT-1). Columns: cik, ann_accession (the census's
    day-0 filing), reading ('definite' | 'redated'), day0_accession, quote (verbatim from the
    day-0 filing, checked against it), reason, read_by, read_on."""
    path = Path(path or DG1_READINGS)
    if not path.exists():
        raise Stage0Halt(f"{path} is missing: DG-NT-1 needs the Stage-0 readings of every "
                         "late-document and post-N1-window event (prereg §4.2)")
    r = pd.read_csv(path, dtype=str, keep_default_na=False)
    need = ["cik", "ann_accession", "reading", "day0_accession", "quote", "reason", "read_by", "read_on"]
    miss = [c for c in need if c not in r.columns]
    if miss:
        raise Stage0Halt(f"{path.name} lacks columns {miss}")
    bad = r[~r["reading"].isin(("definite", "redated"))]
    if len(bad):
        raise Stage0Halt(f"{path.name}: readings must be 'definite' or 'redated': {bad['ann_accession'].tolist()}")
    if r["ann_accession"].duplicated().any():
        raise Stage0Halt(f"{path.name} reads one event twice")
    r["cik"] = r["cik"].astype(int)
    return r


def read_events(inp: dict, client, *, edgar_only: bool, cef_tickers: set | None) -> pd.DataFrame:
    """Every event's EDGAR facts (DG-NT-1, DG-NT-2): day 0 from the header of the day-0 filing,
    the final expiry, the pricing session, P_final, pi and its method, the outcome and the
    outcome filing's observed_at. Unread fields stay None with the reason; nothing is filled.

    `cef_tickers` (CRSP share codes 14/44, any date) decides the census's joint-release rule
    (`other_fund_tickers`). With `edgar_only` and no CRSP names, pi is taken from the census's
    own reading where the results filing IS the census's (the same reader on the same filing)
    and is otherwise left unread with the reason "needs CRSP names"."""
    from scripts.events.cef_corp_action_census import (fetch_raw, other_fund_tickers, parse_tender_offer,
                                                       parse_tender_result, strip_binary)
    from scripts.events.conditional_tender_census import plain, quote_in
    from scripts.data.edgar_client import EdgarHTTPError
    m = base_events(inp)
    fl = inp["filings"]
    dg1 = load_dg1_readings()
    rows = []

    def raw_or_none(cik: int, acc: str, misses: list) -> str | None:
        """A filing's complete submission, or None when the OFFLINE cache lacks it; the miss is
        recorded on the event (the `stage` step fetches it). Online, a failure raises."""
        try:
            return fetch_raw(client, cik, acc)
        except EdgarHTTPError:
            if not getattr(client, "offline", False):
                raise
            misses.append(acc)
            return None

    def plain_or_none(cik: int, acc: str, misses: list) -> str | None:
        raw = raw_or_none(cik, acc, misses)
        return None if raw is None else plain(strip_binary(raw))

    for r in m.itertuples():
        rec = {"event_id": r.event_id}
        misses: list[str] = []
        rec["uncached"] = misses
        off = offer_filings(fl, r.cik, r.ann_date, r.last_date, r.doc_accession) if isinstance(r.doc_accession, str) \
            else None
        rec["later_offers_in_episode"] = off["later_offers"] if off else None
        # ---- DG-NT-1: which filing is day 0
        need_read = bool(r.late_doc or r.programme)
        rd = dg1[dg1["ann_accession"] == r.ann_accession]
        if need_read and rd.empty and not r.in_universe:
            rec.update(dg1="UNREAD (late document or post-N1 window, prereg §4.2)")
            day0_acc = r.ann_accession
        elif len(rd):
            x = rd.iloc[0]
            day0_acc = x["day0_accession"]
            src = plain(strip_binary(fetch_raw(client, r.cik, day0_acc)))
            if not quote_in(src, x["quote"]):
                raise Stage0Halt(f"{r.label} {r.ann_date.date()}: the DG-NT-1 quote is not in {day0_acc}")
            rec.update(dg1=x["reading"], dg1_reason=x["reason"], dg1_quote=x["quote"])
        else:
            day0_acc = r.ann_accession
            rec.update(dg1="not flagged")
        raw0 = fetch_raw(client, r.cik, day0_acc)
        obs0, note0 = observed_from_raw(raw0)
        rec["day0_time_note"] = note0
        acc14, filed0 = header_times(raw0)
        rec.update(day0_accession=day0_acc, day0_acceptance=acc14, day0_filed=str(filed0),
                   day0_observed_utc=obs0.isoformat(), day0=day0_session(obs0))
        rec["redated_days"] = int((rec["day0"] - session_on_or_after(r.ann_date)).days)
        # ---- DG-NT-2: terms and outcome
        rec.update(results_accession=None, expiry=None, expiry_how=None, x_p=None, x_p_how=None, p_final=None,
                   p_final_how=None, p_final_span=None, pi=None, pi_how=None, pi_second=None, outcome="unread",
                   outcome_accession=None, outcome_observed_utc=None, outcome_session=None, termination_span=None)
        if off is None:
            rec["outcome_reason"] = "no offer document (census doc_accession missing)"
            rows.append(rec)
            continue
        offer_text = plain_or_none(r.cik, r.doc_accession, misses)
        if offer_text is None:
            rec["outcome_reason"] = "offer document not cached"
            rows.append(rec)
            continue
        offer = parse_tender_offer(offer_text)
        own = offer["ticker"] or (r.ticker_now.split(";")[0] if isinstance(r.ticker_now, str) else None)
        # termination anywhere in the offer's amendments (the earliest one that says so)
        term = None
        amend_text = {}
        for a in off["amendments"].itertuples():
            tt = plain_or_none(r.cik, a.accession, misses)
            if tt is None:
                continue
            amend_text[a.accession] = tt
            sp = termination(tt)
            if sp:
                term = (a, sp)
                break
        res = off["results"]
        if res is None and term is None:
            rec["outcome_reason"] = "no SC TO-I/A after the offer document (no results filing)"
            rows.append(rec)
            continue
        if term is None and res["accession"] in misses:
            rec["outcome_reason"] = "results filing not cached"
            rows.append(rec)
            continue
        if term is not None:
            a, sp = term
            rawt = fetch_raw(client, r.cik, a.accession)
            obs, rec["outcome_time_note"] = observed_from_raw(rawt)
            rec.update(outcome="terminated", pi=0.0, pi_how="terminated or withdrawn (pi = 0, §4.3)",
                       termination_span=sp, outcome_accession=a.accession, outcome_observed_utc=obs.isoformat(),
                       outcome_session=day0_session(obs), results_accession=a.accession)
            rec["expiry"] = offer["expire"]
            rec["expiry_how"] = "offer document (terminated)"
            rows.append(rec)
            continue
        rec["results_accession"] = res["accession"]
        rawr = fetch_raw(client, r.cik, res["accession"])
        rt = plain(strip_binary(rawr))
        obs, rec["outcome_time_note"] = observed_from_raw(rawr)
        rec.update(outcome_accession=res["accession"], outcome_observed_utc=obs.isoformat(),
                   outcome_session=day0_session(obs))
        lo = pd.Timestamp(r.doc_date)
        hi = pd.Timestamp(res["date_filed"])
        e, espan = final_expiry(rt, lo, hi)
        if e is not None:
            rec.update(expiry=e, expiry_how="results filing", expiry_span=espan)
        else:
            ext = []
            for acc, tt in amend_text.items():
                ext += extension_dates(tt, lo, hi)
            if ext:
                d, sp = max(ext, key=lambda z: z[0])
                rec.update(expiry=d, expiry_how="last extension in the amendments", expiry_span=sp)
            elif offer["expire"] is not None and not pd.isna(offer["expire"]):
                rec.update(expiry=pd.Timestamp(offer["expire"]), expiry_how="offer document (no extension read)",
                           expiry_span=espan)
            else:
                rec.update(expiry_how=f"unread ({espan or 'no expiry statement'})")
        # pi: the census's reader on THIS results filing
        same_as_census = res["accession"] == r.result_accession
        if cef_tickers is not None:
            others = other_fund_tickers(rt, own, cef_tickers)
            pr = parse_tender_result(rt, ticker=own, sought_shares=offer["sought_shares"], multi_fund=bool(others))
            multi = bool(others)
            pi, how = pr["proration"], pr["proration_how"]
            accepted = pr["accepted"]
            if pi is None and offer["size_pct"] == 100.0:
                pi, how = 1.0, "offer for 100% of shares: no pro-ration possible"
            second = (min(1.0, offer["size_pct"] / pr["pct_tendered"]) if pr["pct_tendered"] and offer["size_pct"]
                      else None)
        elif same_as_census:
            multi = bool(r.multi_fund) if not pd.isna(r.multi_fund) else False
            pi = None if pd.isna(r.proration) else float(r.proration)
            how = (r.proration_how if isinstance(r.proration_how, str) else None)
            how = f"{how} [census reading of this filing]" if how else None
            second = None if pd.isna(r.proration_xcheck) else float(r.proration_xcheck)
            accepted = None if pd.isna(r.accepted) else float(r.accepted)
        elif joint_release_decided_without_crsp(rt, own):
            # The census's rule counts the OTHER CEF tickers printed "(NYSE: XXX)" in the release
            # (`other_fund_tickers`: found & CRSP's CEF tickers, minus the fund's own; with no own
            # ticker a single one is presumed its own). When the release prints no ticker but the
            # fund's own (or, with no own ticker, at most one), that set is empty whatever CRSP's
            # list holds, so the release is not joint and the reader runs exactly as with CRSP.
            pr = parse_tender_result(rt, ticker=own, sought_shares=offer["sought_shares"], multi_fund=False)
            multi = False
            pi, how = pr["proration"], pr["proration_how"]
            accepted = pr["accepted"]
            if pi is None and offer["size_pct"] == 100.0:
                pi, how = 1.0, "offer for 100% of shares: no pro-ration possible"
            second = (min(1.0, offer["size_pct"] / pr["pct_tendered"]) if pr["pct_tendered"] and offer["size_pct"]
                      else None)
        else:
            multi, pi, how, second = False, None, "needs CRSP names (joint-release rule); read at the full Stage 0", None
            accepted = None
        if pi is None and second is not None:
            pi, how = second, "second method only (offer size / % of outstanding tendered), labelled (§4.3)"
        rec.update(pi=pi, pi_how=how, pi_second=second, joint_release=multi)
        # P_final and the pricing session
        pr_ = final_price(rt, own, multi, rec["expiry"], accepted)
        rec.update(p_final=pr_.p_final, p_final_how=pr_.how, p_final_span=pr_.span)
        if rec["expiry"] is not None:
            E = session_on_or_after(rec["expiry"])
            if pr_.nav_date is not None and E - pd.Timedelta(days=3) <= pr_.nav_date <= E + pd.Timedelta(days=7):
                rec.update(x_p=session_on_or_before(pr_.nav_date), x_p_how="NAV date beside P_final (results filing)")
            else:
                rule, sp = pricing_rule(offer_text)
                if rule == "next_bd":
                    rec.update(x_p=add_sessions(E, 1), x_p_how="offer terms: NAV of the business day after expiry")
                elif rule == "expiry":
                    rec.update(x_p=E, x_p_how="offer terms: NAV of the expiry date")
                elif rule == "conflict":
                    rec.update(x_p=None, x_p_how="offer terms state both rules: " + sp[:200])
                else:
                    rec.update(x_p=E, x_p_how="expiry (offer states no other pricing date, §4.3)")
            rec["x_p_span"] = None if pr_.nav_date is None else pr_.span
        if pi is not None and rec["p_final"] is not None and rec["x_p"] is not None:
            rec["outcome"] = "completed"
        else:
            miss = [n for n, v in (("pi", pi), ("P_final", rec["p_final"]), ("pricing session", rec["x_p"])) if v is None]
            rec["outcome_reason"] = "unread: " + ", ".join(miss)
        rows.append(rec)
    E = pd.DataFrame(rows)
    out = m.merge(E, on="event_id", how="left", validate="one_to_one")
    return out


def joint_release_decided_without_crsp(text: str, own: str | None) -> bool:
    """True when the census's joint-release test cannot depend on CRSP's ticker list: every
    "(NYSE: XXX)" ticker in the release is the fund's own, or (no own ticker) there is at most one."""
    from scripts.events.cef_corp_action_census import _EXCH_TICKER_RE
    found = {m.group("t") for m in _EXCH_TICKER_RE.finditer(text)}
    return (found <= {own}) if own else (len(found) < 2)


def exit_session(outcome_session, x_p, lag: int = RESIDUAL_LAG, terminated: bool = False) -> pd.Timestamp:
    """F (prereg §5.3): the later of the outcome filing's session and X_p + lag sessions; for a
    terminated offer, the later of the termination's session and that session + lag."""
    if terminated:
        return add_sessions(outcome_session, lag)
    return max(pd.Timestamp(outcome_session), add_sessions(x_p, lag))


def assign_period(day0, last_session) -> str:
    """fit / gap / holdout / after_crsp (prereg §7), by day 0 and the last P&L session F + 1."""
    day0 = pd.Timestamp(day0)
    if day0 < SCOPE_START:
        return "before_scope"
    if day0 < HOLDOUT_START:
        return "fit" if last_session <= FIT_LAST_SESSION else "gap"
    return "holdout" if last_session <= HOLDOUT_LAST_SESSION else "after_crsp"


def schedule(ev: pd.DataFrame, lag: int = RESIDUAL_LAG) -> pd.DataFrame:
    """The entry session (day 0 + 1), F, the last P&L session F + 1, the election cut-off test
    and the period of every event (prereg §5.1, §5.3, §7). An unread event keeps the census's
    proxy period: it is excluded and counted in that period either way."""
    from scripts.events import nav_tender_feasibility as nf
    ev = ev.copy()
    F, last, entry, cut_ok, period = [], [], [], [], []
    for r in ev.itertuples():
        e0 = add_sessions(r.day0, 1)
        entry.append(e0)
        E = None if r.expiry is None or pd.isna(r.expiry) else session_on_or_before(r.expiry)
        cut_ok.append(None if E is None else bool(e0 <= add_sessions(E, -CUTOFF_SESSIONS)))
        if r.outcome in ("completed", "terminated"):
            f = exit_session(r.outcome_session, r.x_p, lag, terminated=(r.outcome == "terminated"))
            F.append(f)
            last.append(add_sessions(f, 1))
            period.append(assign_period(r.day0, last[-1]))
        else:
            F.append(pd.NaT)
            last.append(pd.NaT)
            proxy_last = nf.last_pnl_session(r.last_date, r.expire) if not pd.isna(r.expire) else pd.NaT
            period.append(assign_period(r.ann_date, proxy_last) if not pd.isna(proxy_last) else
                          ("fit" if r.ann_date < HOLDOUT_START else "holdout"))
    ev["entry_session"], ev["F"], ev["last_session"], ev["cutoff_ok"], ev["period"] = entry, F, last, cut_ok, period
    return ev


def one_position_per_fund(ev: pd.DataFrame) -> pd.Series:
    """True where an earlier traded event of the same fund (CIK) is still live (its F + 1 is on
    or after this day 0): the second is not entered (prereg §4.1)."""
    blocked = pd.Series(False, index=ev.index)
    live_until: dict[int, pd.Timestamp] = {}
    for i in ev.sort_values("day0").index:
        r = ev.loc[i]
        if not r["tradable_pre_overlap"]:
            continue
        lu = live_until.get(r["cik"])
        if lu is not None and r["day0"] <= lu:
            blocked.loc[i] = True
            continue
        live_until[r["cik"]] = r["last_session"]
    return blocked


# ===================================================================== the 20% gate (DG-NT-2)

def eligible(ev: pd.DataFrame) -> pd.Series:
    """The pre-registration's event set before the reading gate: outside the 44, day 0 in scope,
    no merger episode open at day 0 (prereg §1, §4.1)."""
    return (~ev["in_universe"].astype(bool)) & (ev["ann_date"] >= SCOPE_START) & (~ev["merger_open"].astype(bool))


def deferred(ev: pd.DataFrame) -> pd.Series:
    """Events whose pi could not be read without CRSP's names (the joint-release rule needs the
    list of CEF tickers): read at the full Stage 0."""
    return ev["pi_how"].fillna("").str.startswith("needs CRSP names")


def dg_nt2_gate(ev: pd.DataFrame, period: str = "fit") -> dict:
    """The share of `period` events excluded for an unread outcome or P_final (prereg §4.3).
    'lo' counts the deferred events as read, 'hi' as unread; the gate FAILS (halt, no trial
    spent) when the decided share exceeds EXCLUSION_MAX. With no deferred event lo == hi."""
    x = ev[eligible(ev) & (ev["period"] == period)]
    unread = x["outcome"] == "unread"
    d = deferred(x) & unread
    n = int(len(x))
    lo, hi = int((unread & ~d).sum()), int(unread.sum())
    out = {"period": period, "events": n, "unread_lo": lo, "unread_hi": hi, "deferred": int(d.sum()),
           "share_lo": lo / n if n else float("nan"), "share_hi": hi / n if n else float("nan"),
           "max_share": EXCLUSION_MAX,
           "reasons": x.loc[unread, "outcome_reason"].value_counts().to_dict()}
    if n and lo / n > EXCLUSION_MAX:
        out["verdict"] = "FAIL"
    elif n and hi / n <= EXCLUSION_MAX:
        out["verdict"] = "PASS"
    else:
        out["verdict"] = "UNDECIDED (deferred events decide it; needs CRSP names)"
    return out


# ===================================================================== CRSP inputs (DG-NT-3)

PERMNO_LIST = CACHE / "crsp_permnos.json"      # the one batch `stage` pulls (licensed ids: gitignored)


def crsp_cache_missing() -> list[str]:
    """The CRSP extracts the full Stage 0 reads and the cache lacks. Agents never pull: the pull
    loads R2 credentials, so the team lead runs `stage` (module docstring)."""
    from scripts.events import crsp_events as ce
    miss = [f for f in ("dsenames.parquet", "dsedelist.parquet") if not (ce.CACHE / f).exists()]
    if not PERMNO_LIST.exists():
        miss.append(str(PERMNO_LIST.relative_to(REPO)))
    else:
        _, h = ce._plist(json.loads(PERMNO_LIST.read_text())["permnos"])
        if not (ce.CACHE / f"dsf_{h}.parquet").exists():
            miss.append(f"dsf_{h}.parquet")
    return miss


def fund_permnos(ev: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    """Each event's permno by the census's CrspMap (ticker first, then the name matcher), on its
    day 0. Unmatched stays None with the reason (excluded and counted)."""
    from scripts.events.cef_corp_action_census import CrspMap
    cm = CrspMap(names)
    perm, how = [], []
    for r in ev.itertuples():
        tk = r.ticker if isinstance(r.ticker, str) and r.ticker.strip() else (
            r.ticker_now if isinstance(r.ticker_now, str) else None)
        p, h = cm.permno(r.fund, tk, r.day0)
        perm.append(p)
        how.append(h)
    out = ev.copy()
    out["permno"], out["permno_how"] = perm, how
    return out


def assert_no_universe(ev: pd.DataFrame, names: pd.DataFrame) -> dict:
    """No traded event is a `cef_universe.csv` fund, by ticker or by any CRSP permno that carried a
    universe ticker (as e1_etf_hedge_gate.assert_no_universe): the 27-name set (H9) is not consumed."""
    from scripts.events import crsp_events as ce
    uni = ce.universe()
    tick = set(uni["ticker"])
    perm = {p for ps in ce.universe_permnos(names).values() for p in ps}
    tks = ev["ticker"].fillna("").astype(str).str.split(";").str[0]
    tkn = ev["ticker_now"].fillna("").astype(str).str.split(";").str[0]
    hit = ev[ev["permno"].isin(perm) | tks.isin(tick) | tkn.isin(tick)]
    if len(hit):
        raise AssertionError(f"traded events on cef_universe.csv funds: {hit['label'].tolist()}")
    return {"universe_tickers": len(tick), "universe_permnos": len(perm), "events_checked": int(len(ev))}


def etf_permnos_resolved(names: pd.DataFrame, symbols, start=None, end=None) -> tuple[dict, dict]:
    """(symbol -> permno, symbol -> why unresolved) by `e1_etf_hedge_gate.etf_permnos` one symbol at a
    time. An ETF CRSP cannot name over the window has no CRSP returns, so it fails §5.2(b) and is
    skipped by the route rule; it is reported, never guessed."""
    from scripts.events import e1_etf_hedge_gate as g
    start = start or pd.Timestamp("2008-01-01")
    end = end or FIT_LAST_SESSION
    ok, bad = {}, {}
    for sym in sorted(set(symbols)):
        try:
            ok.update(g.etf_permnos(names, [sym], start, end))
        except LookupError as e:
            bad[sym] = str(e)
    return ok, bad


def hedge_symbols() -> list[str]:
    from scripts.events.cef_corp_action_census import HEDGE_ALTERNATES, HEDGE_ETF
    out = set(HEDGE_ETF.values()) | {s for v in HEDGE_ALTERNATES.values() for s in v}
    return sorted(out | set(FACTOR_ETFS))


FACTOR_ETFS = ("IEF", "HYG", "MUB")          # TERM = IEF - RF, HY = HYG - IEF, MUNI = MUB - IEF (DG-NT-5)


def daily_raw(permnos) -> pd.DataFrame:
    """`crsp_events.daily` (the fit reader: no 2023 row, asserted) and, beside it, the SIGN of
    `prc` from the same cached extract: `daily` returns |prc|, and the quality screen needs to
    know where CRSP had no closing trade (prc < 0, the bid/ask average; prereg §4.4)."""
    from scripts.events import crsp_events as ce
    d = ce.daily(permnos)
    s, h = ce._plist(permnos)
    raw = pd.read_parquet(ce.CACHE / f"dsf_{h}.parquet", columns=["permno", "date", "prc"])
    raw["date"] = pd.to_datetime(raw["date"])
    d = d.merge(raw.rename(columns={"prc": "prc_raw"}), on=["permno", "date"], how="left", validate="one_to_one")
    d["no_close"] = d["prc_raw"].astype(float) < 0
    return d.drop(columns="prc_raw")


# ===================================================================== hedge routes (DG-NT-4)

def load_dg4(path: Path | None = None) -> dict:
    """The hedge-availability read: Alpaca's flags and IBKR's public file, on ONE date (§4.4)."""
    p = Path(path or DG4_READS)
    if not p.exists():
        raise Stage0Halt(f"{p} is missing: DG-NT-4 needs Alpaca's asset flags (cef paper key) and IBKR's usa.txt "
                         "read on one date; the team lead runs `stage --ibkr <usa.txt>`")
    d = json.loads(p.read_text())
    for k in ("alpaca", "ibkr"):
        if k not in d or "symbols" not in d[k]:
            raise Stage0Halt(f"{p.name} lacks the {k} read")
    return d


def hedge_route(cls: str, dg4: dict, covered) -> tuple[str | None, str, float | None, str]:
    """(symbol, 'alpaca' | 'ibkr' | 'none', IBKR fee %/yr or None, why) for an asset class: the first
    ETF in the census's declared order (HEDGE_ETF, then HEDGE_ALTERNATES) that (a) was shortable at
    Alpaca or showed availability > 0 in IBKR's file on DG-NT-4's read, and (b) `covered(symbol)`
    (CRSP returns over the beta window and the hold). Prereg §5.2; decision 3."""
    from scripts.events.cef_corp_action_census import HEDGE_ALTERNATES, HEDGE_ETF
    if cls not in HEDGE_ETF:
        raise TrialError(f"asset class {cls!r} has no declared hedge")
    order = (HEDGE_ETF[cls],) + tuple(HEDGE_ALTERNATES.get(cls, ()))
    al, ib = dg4["alpaca"]["symbols"], dg4["ibkr"]["symbols"]
    for s in order:
        if s not in al:
            raise Stage0Halt(f"{s} has no Alpaca read in {DG4_READS.name}: every candidate is read")
        a_ok = bool(al[s].get("found", True)) and bool(al[s].get("shortable"))
        i = ib.get(s)
        i_ok = i is not None and float(i.get("available") or 0) > 0
        if not (a_ok or i_ok):
            continue
        if not covered(s):
            continue
        return (s, "alpaca", None, "shortable at Alpaca") if a_ok else (s, "ibkr", float(i["fee_rate_pct"]),
                                                                         "available in IBKR's file")
    return None, "none", None, "no declared ETF available and priced"


# ===================================================================== the hedge ratio

BETA_TEST_H = 1   # SPEC flag `beta_window`: windows() refuses h = 0 (its own anchor assertion)


def beta_for(fund: pd.DataFrame, etf: pd.DataFrame, day0: pd.Timestamp) -> dict:
    """The Dimson beta of the fund on the ETF (prereg §5.2): `e1_etf_hedge_gate.windows`, `spans`
    and `dimson`, unchanged with their constants (EST_SESSIONS 252, GUARD_SESSIONS 42,
    MIN_EST_OBS 200, MAX_GAP 10). The estimation window is windows()'s (s_est, s0] with the
    smallest test length it accepts (BETA_TEST_H). Every span ends at or before s0 < day 0 (H7,
    asserted)."""
    from scripts.events import e1_etf_hedge_gate as g
    valid = fund.index[fund["idx"].notna()]
    win = g.windows(valid, day0, BETA_TEST_H)
    if win is None:
        return {"status": "no beta history", "beta": None}
    s_est, s0, e = win
    est, drops = g.spans(fund, etf, s_est, s0)
    prev = valid[valid < s_est]
    lag_first = np.nan
    if len(prev):
        pre, _ = g.spans(fund, etf, prev[-1], s_est)
        lag_first = pre["rH"].iloc[-1] if len(pre) else np.nan
    est["rH_lag"] = np.concatenate([[lag_first], est["rH"].values[:-1]])
    ok = (est["gap"] <= g.MAX_GAP) & est["rH"].notna() & est["rH_lag"].notna()
    est = est[ok]
    if len(est) and est["end"].max() >= day0:
        raise AssertionError(f"beta window reaches day 0 {day0.date()}: lookahead")
    if len(est) < g.MIN_EST_OBS:
        return {"status": f"{len(est)} aligned spans (< {g.MIN_EST_OBS})", "beta": None}
    b, b_ols = g.dimson(est["rT"].values.astype(float), est["rH"].values.astype(float),
                        est["rH_lag"].values.astype(float))
    return {"status": "ok", "beta": b, "beta_ols": b_ols, "n": int(len(est)), "est_start": s_est, "est_end": s0}


# ===================================================================== the matrices (prereg §5.3-§5.5)

@dataclass
class Ev:
    """One traded event, everything the matrices need. Weights are per unit of original notional."""
    eid: str
    group: str
    day0: pd.Timestamp
    F: pd.Timestamp
    x_p: pd.Timestamp | None
    pi: float
    p_final: float | None
    u: float
    beta: float
    etf: str


def tender_return(pi: float, p_final: float, close_prev: float, ret_xp: float) -> float:
    """The fund column's return on the pricing session X_p, per unit of original notional (§5.3):
    the accepted fraction is sold to the fund at P_final against the previous close, the residual
    earns the day's CRSP return."""
    if not (0.0 <= pi <= 1.0):
        raise TrialError(f"pi {pi} outside [0, 1]")
    if not (np.isfinite(p_final) and np.isfinite(close_prev) and close_prev > 0 and np.isfinite(ret_xp)):
        raise TrialError(f"tender row inputs not finite: P_final {p_final}, close {close_prev}, ret {ret_xp}")
    return pi * (p_final / close_prev - 1.0) + (1.0 - pi) * ret_xp


def build_matrices(events: list[Ev], fund_ret: dict, fund_close: dict, etf_ret: dict,
                   sessions: pd.DatetimeIndex, weights: dict | None = None, entry: dict | None = None,
                   exit_: dict | None = None, elect: bool = True) -> dict:
    """H (decisions), R (returns with the tender rows written in), Q (traded notional) and the
    per-event P&L ledger (prereg §5.5).

    fund_ret[eid] / etf_ret[symbol]: Series of CRSP total returns on `sessions` (bridged NaNs
    already written as 0); fund_close[eid]: |prc|, for the tender row's previous close.
    `weights[eid]` replaces u (the sized and capped sleeve). `entry[eid]` / `exit_[eid]` replace
    the entry decision (day 0) and the exit decision (F) for the report-only rows; `elect=False`
    never tenders (the no-tender twin B, the placebo).

    ALIGNMENT: H[t, eid] = w on decision rows [entry, exit) (shift(2): bought at the close of
    entry + 1, sold at the close of exit + 1, so the P&L sessions are entry + 2 .. exit + 1).
    The tender row is R[X_p] and must be one of those P&L sessions (asserted); the cut-off rule
    guarantees it for the declared rows."""
    cols = [e.eid for e in events]
    etfs = sorted({e.etf for e in events})
    H = pd.DataFrame(0.0, index=sessions, columns=cols + etfs)
    R = pd.DataFrame(np.nan, index=sessions, columns=cols + etfs)
    Q = pd.DataFrame(0.0, index=sessions, columns=cols + etfs)
    pos = {d: i for i, d in enumerate(sessions)}
    ledger = {}
    for e in events:
        w = (weights or {}).get(e.eid, e.u)
        d0 = (entry or {}).get(e.eid, e.day0)
        Fd = (exit_ or {}).get(e.eid, e.F)
        if d0 not in pos or Fd not in pos:
            raise TrialError(f"{e.eid}: entry {d0} or exit {Fd} is not a session of the matrix")
        i0, iF = pos[d0], pos[Fd]
        if iF <= i0:
            raise TrialError(f"{e.eid}: exit decision {Fd.date()} not after the entry decision {d0.date()}")
        if iF + 1 >= len(sessions):
            raise TrialError(f"{e.eid}: the last P&L session is beyond the matrix")
        H.iloc[i0:iF, H.columns.get_loc(e.eid)] = w
        H.iloc[i0:iF, H.columns.get_loc(e.etf)] += -e.beta * w
        pl = sessions[i0 + 2: iF + 2]                       # the event's P&L sessions
        r = fund_ret[e.eid].reindex(pl).astype(float).copy()
        tendered = elect and e.x_p is not None and e.pi > 0
        if tendered:
            if e.x_p not in pos or not (i0 + 2 <= pos[e.x_p] <= iF + 1):
                raise AssertionError(f"{e.eid}: pricing session {e.x_p} is not a P&L session of the hold")
            prev = sessions[pos[e.x_p] - 1]
            r.loc[e.x_p] = tender_return(e.pi, e.p_final, float(fund_close[e.eid].loc[prev]),
                                         float(fund_ret[e.eid].loc[e.x_p]))
            after = pl[pl > e.x_p]
            r.loc[after] = (1.0 - e.pi) * r.loc[after]
        R.loc[pl, e.eid] = r.values
        Q.iloc[i0, Q.columns.get_loc(e.eid)] += w
        Q.iloc[iF, Q.columns.get_loc(e.eid)] += (1.0 - e.pi if tendered else 1.0) * w
        er = etf_ret[e.etf].reindex(pl).astype(float)
        ledger[e.eid] = {"pnl_fund": float((w * r).sum()), "pnl_hedge": float((-e.beta * w * er).sum()),
                         "sessions": int(len(pl)), "first_pl": pl[0], "last_pl": pl[-1], "w": w}
    for s in etfs:
        R[s] = etf_ret[s].reindex(sessions).astype(float)
        dh = H[s].diff().abs()
        dh.iloc[0] = abs(H[s].iloc[0])
        Q[s] = dh
    assert_alignment(H, R)
    return {"H": H, "R": R, "Q": Q, "ledger": ledger}


def assert_alignment(H: pd.DataFrame, R: pd.DataFrame) -> None:
    """R must be finite wherever H.shift(2) holds a position: evaluate() treats a NaN return on a
    held day as 0, which would be a silent fallback (prereg §5.5). Names the event and the date."""
    held = H.shift(2).fillna(0.0) != 0.0
    bad = held & ~np.isfinite(R)
    if bad.any().any():
        c = bad.any()[bad.any()].index[0]
        d = bad.index[bad[c]][0]
        raise AssertionError(f"R is not finite on a held day: {c} {d.date()}")


def sleeve_pnl(M: dict) -> pd.Series:
    """The daily P&L, by `band_frontier.evaluate` unchanged; asserts the per-event ledger sums to it."""
    from scripts.cef.band_frontier import evaluate
    pnl = evaluate(M["H"], M["R"].fillna(0.0).where(M["H"].shift(2).fillna(0.0) != 0.0, 0.0))["pnl"]
    led = sum(v["pnl_fund"] + v["pnl_hedge"] for v in M["ledger"].values())
    if not np.isclose(pnl.sum(), led, rtol=1e-9, atol=1e-12):
        raise AssertionError(f"per-event P&L {led:.12f} != evaluate() sum {pnl.sum():.12f}")
    assert_denormal_free(pnl)
    return pnl


def assert_denormal_free(x: pd.Series) -> None:
    """DG-NT-6: no P&L value is denormal-like (scripts/events/numexpr_fault.py found numexpr writing
    1e-310-scale garbage into DataFrame arithmetic)."""
    v = np.abs(np.asarray(x, dtype=float))
    if np.any((v > 0) & (v < 1e-250)):
        raise AssertionError("a P&L value is denormal-like: the numexpr fault (DG-NT-6)")


# ===================================================================== sizing (prereg §5.4)

def sigma_active(pnl: pd.Series, H: pd.DataFrame) -> float:
    """The raw sleeve's annualised daily gross P&L vol on sessions with at least one live event."""
    live = (H.shift(2).fillna(0.0).abs().sum(axis=1) > 0)
    x = pnl[live]
    if len(x) < 30:
        raise TrialError(f"only {len(x)} live sessions: sigma_active undefined")
    return float(x.std() * np.sqrt(252))


def capped_weights(events: list[Ev], k: float, sessions: pd.DatetimeIndex, cap: float) -> tuple[dict, dict]:
    """The tradable sleeve's weights: k * u, with the gross cap applied at entry only (§5.4). Groups
    enter together in day-0 order; a group takes the largest scale s in [0, 1] for which the
    book's gross on its decision day (fund plus |hedge|, hedges netted per ETF) stays within
    `cap`; s = 0 is not entered. Live events are never cut."""
    pos = {d: i for i, d in enumerate(sessions)}
    cols = [e.eid for e in events] + sorted({e.etf for e in events})
    H = pd.DataFrame(0.0, index=sessions, columns=cols)
    w_out, scale = {}, {}
    by_group: dict[tuple, list[Ev]] = {}
    for e in events:
        by_group.setdefault((e.day0, e.group), []).append(e)
    for (d0, g), evs in sorted(by_group.items(), key=lambda z: (z[0][0], z[0][1])):
        i0 = pos[d0]
        G = pd.Series(0.0, index=cols)
        for e in evs:
            G[e.eid] += k * e.u
            G[e.etf] += -e.beta * k * e.u
        before = H.iloc[i0]

        def gross(s):
            return float((before + s * G).abs().sum())
        if gross(0.0) >= cap - 1e-12:            # no room: not entered (counted by the caller)
            s = 0.0
        elif gross(1.0) <= cap:
            s = 1.0
        else:
            lo, hi = 0.0, 1.0
            for _ in range(60):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if gross(mid) <= cap else (lo, mid)
            s = lo
        for e in evs:
            scale[e.eid] = s
            w_out[e.eid] = s * k * e.u
            if s > 0:
                iF = pos[e.F]
                H.iloc[i0:iF, H.columns.get_loc(e.eid)] += w_out[e.eid]
                H.iloc[i0:iF, H.columns.get_loc(e.etf)] += -e.beta * w_out[e.eid]
    return w_out, scale


# ===================================================================== inference

def per_event_table(events: list[Ev], ledger: dict, pis: dict, c_bp: float = 0.0) -> pd.DataFrame:
    """Per event, raw units (u-weighted, as the raw sleeve holds it; prereg §6):
    gross = the event's fund + hedge P&L; net = gross - u * c * (1 + (1 - pi) + 2|beta|)."""
    rows = []
    for e in events:
        L = ledger[e.eid]
        g = L["pnl_fund"] + L["pnl_hedge"]
        units = 1.0 + (1.0 - (0.0 if e.x_p is None else pis[e.eid])) + 2.0 * abs(e.beta)
        rows.append({"eid": e.eid, "group": e.group, "u": e.u, "gross": g,
                     "net": g - e.u * c_bp / 1e4 * units, "per_notional": g / e.u, "day0": e.day0})
    return pd.DataFrame(rows)


def cluster_stats(x: pd.Series, groups: pd.Series, seed: int = SEED, reps: int = BOOT_REPS) -> dict:
    """Mean, CR1 cluster t by group (`convert_issuance.cluster_t`), plain t, and a group bootstrap."""
    from scripts.events.convert_issuance import cluster_t
    v = np.asarray(x, dtype=float)
    t, G = cluster_t(v, np.asarray(groups))
    plain_t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))
    rng = np.random.default_rng(seed)
    gs = pd.Series(v).groupby(np.asarray(groups))
    sums, counts = gs.sum().to_numpy(), gs.size().to_numpy()
    idx = rng.integers(0, len(sums), size=(reps, len(sums)))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    return {"n": int(len(v)), "groups": int(G), "mean": float(v.mean()), "cluster_t": float(t),
            "plain_t": float(plain_t), "boot_p_le0": float((boot <= 0).mean()),
            "boot_lo": float(np.quantile(boot, 0.025)), "boot_hi": float(np.quantile(boot, 0.975))}


def sleeve_stats(pnl: pd.Series, turn: pd.Series, T_first, T_last) -> dict:
    """The tradable sleeve's headline (prereg §8): annualised gross Sharpe from the first P&L
    session to T_last, idle sessions included; the 5/15/30bp nets by `_stats` on Q; NW t (L 21)
    with the automatic lag beside it; stationary bootstrap at blocks 21 and 63; `_dsr` at N."""
    from scripts.cef.band_frontier import _stats
    from scripts.cef.validate import _dsr
    from scripts.cef.w4_artifacts import nw_auto_lag, nw_t, stationary_boot
    p = pnl.loc[T_first:T_last]
    q = turn.loc[T_first:T_last]
    st = _stats(p, q)
    sk, ku = float(p.skew()), float(p.kurt() + 3.0)
    dsr, sr0, emax = _dsr(st["sr"], len(p), sk, ku, N_BAR)
    out = {"T": int(len(p)), "first": str(p.index[0].date()), "last": str(p.index[-1].date()),
           "gross_sr": float(st["sr"]), "ann": float(st["ann"]), "vol": float(st["vol"]), "turn": float(st["turn"]),
           "net_sr": {str(c): float(n) for c, n in zip(COSTS_BP, st["nets"])},
           "nw_t": float(nw_t(p, NW_LAGS)), "nw_auto_lag": int(nw_auto_lag(p)),
           "skew": sk, "kurt": ku, "dsr": float(dsr), "sr0": float(sr0), "e_max": float(emax), "N": N_BAR,
           "sr_sqrt_years": float(st["sr"] * np.sqrt(len(p) / 252))}
    for b in BOOT_BLOCKS:
        bs = stationary_boot(p, mean_block=b, reps=BOOT_REPS, seed=SEED)
        out[f"boot_sr_lo_b{b}"], out[f"boot_sr_hi_b{b}"] = float(bs["lo_sr"]), float(bs["hi_sr"])
        out[f"boot_p_mean_le0_b{b}"] = float((bs["means"] <= 0).mean())
    return out


def rd4(pnl: pd.Series, factors: pd.DataFrame, scale: float) -> dict:
    """R-D4 (prereg §9): OLS of the sleeve's daily gross P&L on Mkt-RF SMB HML RMW CMA UMD TERM HY
    MUNI, each at t and t - 1 (Dimson), HAC (maxlags 21); betas summed and multiplied by `scale`
    (vol_target / sigma of the tradable sleeve). Pass: alpha t >= 3.0 and every |beta| <= 0.10."""
    import statsmodels.api as sm
    F = factors.reindex(pnl.index)
    X = pd.concat([F, F.shift(1).add_suffix("_l1")], axis=1)
    d = pd.concat([pnl.rename("y"), X], axis=1).dropna()
    m = sm.OLS(d["y"], sm.add_constant(d.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})
    betas = {c: float((m.params[c] + m.params[c + "_l1"]) * scale) for c in factors.columns}
    m0 = sm.OLS(d["y"], sm.add_constant(d[list(factors.columns)])).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})
    return {"n": int(len(d)), "alpha_t": float(m.tvalues["const"]), "alpha_ann": float(m.params["const"] * 252),
            "betas_summed_at_target": betas, "max_abs_beta": float(max(abs(b) for b in betas.values())),
            "pass": bool(m.tvalues["const"] >= ALPHA_T_BAR and all(abs(b) <= BETA_MAX for b in betas.values())),
            "r0_alpha_t": float(m0.tvalues["const"]),
            "r0_betas_at_target": {c: float(m0.params[c] * scale) for c in factors.columns}}


def election_fee_series(events: list[Ev], weights: dict, sessions: pd.DatetimeIndex, capital: float) -> pd.Series:
    """$100 per election as a return on the tradable sleeve, charged on the pricing session (§6):
    fee / (weight * capital) per unit of the event's notional, times its weight = fee / capital."""
    fee = pd.Series(0.0, index=sessions)
    for e in events:
        if e.x_p is not None and weights.get(e.eid, 0.0) > 0:
            fee.loc[e.x_p] += ELECTION_FEE_USD / capital
    return fee


# ===================================================================== price series (DG-NT-3)

def series_on(dsf: pd.DataFrame, permno: int, sessions: pd.DatetimeIndex, a, b,
              delist: pd.DataFrame | None = None, tolerant: bool = False) -> dict:
    """One permno's total return and |prc| on the sessions in [a, b], by DG-NT-3's rules:
    * a NaN `ret` (or a session with no CRSP row) is allowed only where CRSP's next valid `ret`
      bridges it -- `merger_pairs.bridging_check` on that gap, at most MAX_GAP missing days --
      and is then written as 0 explicitly and counted; anything else raises naming the date;
    * a delisting inside [a, b] (dsedelist) ends the series there, with `dlret` compounded into
      that day's return, and is returned as `delisted` for the caller to flag.
    `tolerant` (the placebo's whole-history series only) leaves an unbridged gap as NaN instead of
    raising; a placebo window that contains one is not drawn.
    Returns dict(ret, close, bridged, delisted, unbridged)."""
    from scripts.events.merger_pairs import MAX_GAP, bridging_check
    g = dsf[dsf["permno"] == permno].sort_values("date").set_index("date")
    sess = sessions[(sessions >= a) & (sessions <= b)]
    delisted = None
    if delist is not None and len(delist):
        d = delist[(delist["permno"] == permno) & (delist["dlstdt"] >= a) & (delist["dlstdt"] <= b)]
        if len(d):
            delisted = (pd.Timestamp(d["dlstdt"].iloc[0]), float(d["dlret"].iloc[0]) if not pd.isna(d["dlret"].iloc[0])
                        else float("nan"))
            sess = sess[sess <= delisted[0]]
    ret = g["ret"].reindex(sess)
    close = g["prc"].reindex(sess)
    bridged = 0
    unbridged: list[str] = []
    miss = ret.isna()
    if miss.any():
        runs = (miss != miss.shift()).cumsum()[miss]
        for _, idx in runs.groupby(runs).groups.items():
            first, last = idx[0], idx[-1]
            nxt = sess[sess > last]
            why = None
            if len(idx) > MAX_GAP or not len(nxt) or pd.isna(ret.get(nxt[0])):
                why = f"missing return {first.date()}..{last.date()} is not bridged"
            else:
                before = g.loc[g.index < first].dropna(subset=["prc"])
                if before.empty:
                    why = f"no valid price before the gap at {first.date()}"
                else:
                    sub = pd.concat([before.iloc[[-1]], g.reindex(idx), g.loc[[nxt[0]]]])
                    sub.index.name = "date"
                    sub = sub.reset_index()
                    sub["permno"] = permno
                    chk = bridging_check(sub)
                    if chk["gaps_tested_le_max_gap"] < 1 or chk["agree_within_1e-4"] != chk["gaps_tested_le_max_gap"]:
                        why = f"CRSP's next return does not bridge the gap at {first.date()} ({chk})"
            if why is not None:
                if not tolerant:
                    raise TrialError(f"permno {permno}: {why}")
                unbridged.append(why)
                continue
            ret.loc[idx] = 0.0
            bridged += len(idx)
    if delisted is not None:
        dd, dlret = delisted
        if not np.isfinite(dlret):
            raise TrialError(f"permno {permno}: delisted {dd.date()} inside the hold with no dlret")
        r0 = ret.get(dd, np.nan)
        ret.loc[dd] = (1 + (0.0 if pd.isna(r0) else r0)) * (1 + dlret) - 1
    return {"ret": ret, "close": close, "bridged": bridged, "delisted": delisted, "unbridged": unbridged}


def factor_frame(ff: pd.DataFrame, etf: dict) -> pd.DataFrame:
    """Mkt-RF SMB HML RMW CMA UMD (French, decimals) and TERM = IEF - RF, HY = HYG - IEF, MUNI = MUB -
    IEF from CRSP total returns (DG-NT-5). A date missing any column is dropped by the regression,
    never filled."""
    f = ff.set_index("date")[["mktrf", "smb", "hml", "rmw", "cma", "umd", "rf"]].copy()
    f.index = pd.to_datetime(f.index)
    out = f[["mktrf", "smb", "hml", "rmw", "cma", "umd"]].copy()
    out["TERM"] = etf["IEF"] - f["rf"]
    out["HY"] = etf["HYG"] - etf["IEF"]
    out["MUNI"] = etf["MUB"] - etf["IEF"]
    return out


def load_ff() -> pd.DataFrame:
    p = REPO / "results" / "cef" / "w4" / "_cache_w4" / "ff5_umd_daily.parquet"
    if not p.exists():
        raise Stage0Halt(f"{p.relative_to(REPO)} is missing: run `python3 scripts/data/fetch_ff_factors.py` (DG-NT-5)")
    ff = pd.read_parquet(p)
    ff["date"] = pd.to_datetime(ff["date"])
    return ff


# ===================================================================== the run on data (fit or holdout)

@dataclass
class Data:
    """Everything a P&L run reads, already checked by Stage 0."""
    ev: pd.DataFrame            # the traded events (one row each), with permno, etf, route, fee, beta
    fund: dict                  # eid -> dict(ret, close) on the run's sessions
    etf: dict                   # symbol -> Series of total returns on the run's sessions
    sessions: pd.DatetimeIndex
    factors: pd.DataFrame | None
    t_first: pd.Timestamp       # the first P&L session (first day 0 + 2)
    t_last: pd.Timestamp        # 2022-12-30 (fit) / 2024-12-31 (holdout)
    etf_frames: dict | None = None   # symbol -> e1_etf_hedge_gate.series frame (beta re-estimation rows)


def to_events(ev: pd.DataFrame, beta_mode: str = "dimson", unit: str = "group") -> list[Ev]:
    """Ev records. beta_mode: 'dimson' (declared), 'one', 'zero' (robustness). unit: 'group' (u = 1/m,
    decision 9) or 'event' (u = 1)."""
    m = ev.groupby("group")["eid"].transform("size")
    out = []
    for r, mm in zip(ev.itertuples(), m):
        b = {"dimson": r.beta, "one": 1.0, "zero": 0.0}[beta_mode]
        out.append(Ev(eid=r.eid, group=r.group, day0=r.day0, F=r.F,
                      x_p=None if r.outcome == "terminated" else r.x_p,
                      pi=float(r.pi), p_final=None if r.outcome == "terminated" else float(r.p_final),
                      u=(1.0 / mm) if unit == "group" else 1.0, beta=float(b), etf=r.etf))
    return out


def run_pnl(D: Data, events: list[Ev], k: float | None, cap: float | None, **kw) -> dict:
    """Raw and tradable sleeves for `events`. k None = derive it from the raw sleeve (fit);
    a number = the frozen fit k (holdout). Returns the matrices, P&L, k and the cap's effect."""
    fr = {e.eid: D.fund[e.eid]["ret"] for e in events}
    fc = {e.eid: D.fund[e.eid]["close"] for e in events}
    raw = build_matrices(events, fr, fc, D.etf, D.sessions, **kw)
    pnl_raw = sleeve_pnl(raw)
    sig = sigma_active(pnl_raw.loc[D.t_first:D.t_last], raw["H"].loc[:D.t_last])
    k_used = k if k is not None else None
    if k_used is None:
        from scripts.cef.spec import VOL_TARGET
        k_used = VOL_TARGET / sig
    w, scale = capped_weights(events, k_used, D.sessions, cap) if cap is not None else (
        {e.eid: k_used * e.u for e in events}, {e.eid: 1.0 for e in events})
    trad = build_matrices(events, fr, fc, D.etf, D.sessions, weights=w, **kw)
    pnl_trad = sleeve_pnl(trad)
    return {"raw": raw, "pnl_raw": pnl_raw, "sigma_active": sig, "k": k_used, "w": w, "scale": scale,
            "trad": trad, "pnl_trad": pnl_trad,
            "turn_trad": trad["Q"].abs().sum(axis=1), "turn_raw": raw["Q"].abs().sum(axis=1)}


def grid(pnl: pd.Series, turn: pd.Series, a, b) -> dict:
    from scripts.cef.band_frontier import _stats
    st = _stats(pnl.loc[a:b], turn.loc[a:b])
    return {"gross": float(st["sr"]), "ann": float(st["ann"]), "turn": float(st["turn"]),
            **{f"net{c}": float(n) for c, n in zip(COSTS_BP, st["nets"])},
            "flips": bool(np.sign(st["sr"]) != np.sign(st["nets"][-1]))}


def borrow_line(trad: dict, ev: pd.DataFrame, a, b) -> dict:
    """IBKR-routed hedges at their fee on DG-NT-4's date, through `band_frontier.borrow_charge`
    (shift(2), 102% collateral, actual/360); Alpaca easy-to-borrow ETFs at zero (§6). One day's
    fee applied to the whole period: a counterfactual, labelled."""
    from scripts.cef.band_frontier import borrow_charge
    H = trad["H"]
    etfs = sorted(ev["etf"].unique())
    fee = {}
    for s in etfs:
        x = ev[ev["etf"] == s]
        routes = set(x["route"])
        if routes == {"alpaca"}:
            fee[s] = 0.0
        elif routes == {"ibkr"}:
            fee[s] = float(x["fee_pct"].iloc[0])
        else:
            raise TrialError(f"{s} is routed both ways")
    F = pd.DataFrame({s: fee[s] for s in etfs}, index=H.index)
    bc = borrow_charge(H[etfs], F)
    c = bc["cost"].loc[a:b]
    return {"borrow_ann": float(c.mean() * 252), "covered_share": bc["covered_share"], "fees_pct": fee}


def per_event(D: Data, events: list[Ev], led: dict, c_bp: float = 0.0) -> pd.DataFrame:
    pis = {e.eid: e.pi for e in events}
    return per_event_table(events, led, pis, c_bp)


def placebo(D: Data, events: list[Ev], episodes: pd.DataFrame, ev: pd.DataFrame,
            draws: int = PLACEBO_DRAWS, seed: int = SEED) -> dict:
    """Stage 2 (prereg §8): each event's day 0 replaced by a session drawn uniformly from the same
    fund's fit sessions with no tender episode of the fund (any class) within PLACEBO_CLEAR
    sessions, no merger or contest episode open, a beta history (enough valid sessions for
    `windows`), and the real hold length fitting inside the fit with every return priced. A plain
    sale (pi = 0, no fee), the same u and ETF, beta re-estimated at the placebo date. The statistic
    is each draw's mean per-event gross P&L in raw units (u-weighted, as stage 1)."""
    from scripts.events import e1_etf_hedge_gate as g
    rng = np.random.default_rng(seed)
    sess = D.sessions
    n = len(sess)
    pos = {d: i for i, d in enumerate(sess)}
    lo_i = int(np.searchsorted(sess.values, np.datetime64(D.t_first)))
    hi_i = int(np.searchsorted(sess.values, np.datetime64(D.t_last), side="right")) - 1
    need_hist = g.EST_SESSIONS + g.GUARD_SESSIONS + BETA_TEST_H + 1
    cand, holds = {}, {}
    idx = np.arange(n)
    for e in events:
        r = ev.loc[ev["eid"] == e.eid].iloc[0]
        L = pos[e.F] - pos[e.day0]
        holds[e.eid] = L
        fr = D.fund[e.eid]["full_ret"].reindex(sess)
        valid = fr.notna().to_numpy()
        hist = np.concatenate([[0], np.cumsum(valid)[:-1]])          # valid sessions strictly before t
        nan_cum = np.concatenate([[0], np.cumsum(~valid)])            # NaNs in [0, i)
        ok = valid & (hist >= need_hist) & (idx >= lo_i) & (idx + L + 1 <= hi_i)
        # the P&L window [i + 2, i + L + 1] has no missing return
        s_, e_ = np.minimum(idx + 2, n), np.minimum(idx + L + 2, n)
        ok &= (nan_cum[e_] - nan_cum[s_]) == 0
        eps = episodes[episodes["cik"] == r.cik]
        for x in eps[eps["kind"] == "tender"].itertuples():
            a_ = int(np.searchsorted(sess.values, np.datetime64(pd.Timestamp(x.first_date))))
            b_ = int(np.searchsorted(sess.values, np.datetime64(pd.Timestamp(x.last_date)), side="right")) - 1
            ok[max(0, a_ - PLACEBO_CLEAR): min(n, b_ + PLACEBO_CLEAR + 1)] = False
        for x in eps[eps["kind"].isin(("merger", "contest"))].itertuples():
            a_ = int(np.searchsorted(sess.values, np.datetime64(pd.Timestamp(x.first_date))))
            b_ = int(np.searchsorted(sess.values, np.datetime64(pd.Timestamp(x.last_date)), side="right")) - 1
            ok[a_: b_ + 1] = False
        cand[e.eid] = idx[ok]
    beta_memo: dict = {}
    fr_np = {e.eid: D.fund[e.eid]["full_ret"].reindex(sess).to_numpy() for e in events}
    et_np = {s_: D.etf[s_].reindex(sess).to_numpy() for s_ in {e.etf for e in events}}
    means = np.empty(draws)
    skipped = 0
    for k_ in range(draws):
        vals = []
        for e in events:
            c = cand[e.eid]
            if not len(c):
                continue
            i = int(c[rng.integers(0, len(c))])
            key = (e.eid, i)
            if key not in beta_memo:
                beta_memo[key] = beta_for(D.fund[e.eid]["full_frame"], D.fund[e.eid]["etf_frame"], sess[i])["beta"]
            b = beta_memo[key]
            if b is None:
                skipped += 1
                continue
            w = slice(i + 2, i + holds[e.eid] + 2)
            re_ = et_np[e.etf][w]
            if not np.isfinite(re_).all():
                skipped += 1
                continue
            vals.append(e.u * float(np.sum(fr_np[e.eid][w] - b * re_)))
        means[k_] = np.mean(vals) if vals else np.nan
    return {"draws": draws, "p95": float(np.nanquantile(means, 0.95)), "mean": float(np.nanmean(means)),
            "p50": float(np.nanquantile(means, 0.5)), "share_draw_means_ge_real": None,
            "events_with_candidates": int(sum(1 for v in cand.values() if len(v))),
            "median_candidates": float(np.median([len(v) for v in cand.values()])),
            "skipped_event_draws": int(skipped), "draw_means": means}


# ===================================================================== Stage 0

TRACKED_EVENT_COLS = ["event_id", "cik", "label", "fund", "sponsor", "asset_class", "ann_date", "ann_form", "in_universe",
                      "merger_open", "late_doc", "programme", "episode_far", "later_offers_in_episode", "dg1",
                      "day0_accession", "day0_acceptance", "day0", "redated_days", "doc_accession", "k_pct", "size_pct",
                      "results_accession", "expiry", "expiry_how", "x_p", "x_p_how", "p_final", "p_final_how", "pi",
                      "pi_how", "pi_second", "outcome", "outcome_reason", "outcome_accession", "outcome_session",
                      "entry_session", "F", "last_session", "cutoff_ok", "period", "uncached"]


def offline_client():
    from scripts.data.edgar_client import EdgarClient
    return EdgarClient(offline=True)


def groups_of(ev: pd.DataFrame) -> pd.Series:
    """The independent unit: sponsor x day 0 (prereg §5.1; the census's `groups` key)."""
    return ev["sponsor"].astype(str) + "@" + pd.to_datetime(ev["day0"]).dt.strftime("%Y-%m-%d")


def edgar_flags(ev: pd.DataFrame) -> pd.DataFrame:
    """Stage-0 flags from the EDGAR readings, for the team lead's rulings (§4b). Keys check,
    ticker (the event's label), date (its census day 0)."""
    x = ev[eligible(ev) & ev["period"].isin(("fit", "holdout"))]
    rows = []

    def add(check, r, note):
        rows.append({"check": check, "ticker": r.label, "date": str(pd.Timestamp(r.ann_date).date()),
                     "period": r.period, "event_id": r.event_id, "note": note})
    for r in x.itertuples():
        if r.dg1 in ("definite", "redated"):
            add(f"dg1_{r.dg1}", r, f"day 0 {pd.Timestamp(r.day0).date()} from {r.day0_accession}: {r.dg1_reason}")
        if isinstance(r.day0_time_note, str) or isinstance(getattr(r, "outcome_time_note", None), str):
            add("time_key", r, (r.day0_time_note if isinstance(r.day0_time_note, str) else r.outcome_time_note))
        if r.episode_far:
            add("quality_episode_far", r, f"episode spans {int(r.later_offers_in_episode or 0) + 1} offer(s); the event is "
                                          f"the first, results {r.results_accession}")
        if r.outcome == "completed" and not pd.isna(r.nav) and not pd.isna(r.p_final):
            ratio = r.p_final / (r.k_pct / 100.0 * r.nav)
            if abs(ratio - 1) > 0.15:
                add("pfinal_vs_offer_nav", r, f"P_final {r.p_final} is {ratio:.3f} x k% of the offer's NAV {r.nav} "
                                              f"({pd.Timestamp(r.nav_date).date()}): {r.p_final_how}")
        if r.outcome == "completed" and r.expiry is not None and not pd.isna(r.expiry) and r.x_p is not None:
            E = session_on_or_after(r.expiry)
            if r.x_p > add_sessions(E, 1) or r.x_p < E:
                add("pricing_session", r, f"X_p {pd.Timestamp(r.x_p).date()} vs expiry {pd.Timestamp(r.expiry).date()}: {r.x_p_how}")
    return pd.DataFrame(rows, columns=["check", "ticker", "date", "period", "event_id", "note"])


SPEC_FLAGS = [
    ("spec_beta_window", "e1_etf_hedge_gate.windows refuses a test length of 0 (its anchor assertion s0 < e); the "
                         "script fits on windows()'s (s_est, s0] with h = 1: 252 spans ending 43 valid sessions before "
                         "day 0, one more than the prereg's 42. Rule: keep h = 1, or fit on (s_est, e] with est = 251."),
    ("spec_results_filing", "The results filing is the offer's own last SC TO-I/A (prereg §4.3); an offer whose outcome "
                            "was published only as a post-expiry SC TO-C press release is unread. Rule: keep, or admit "
                            "that press release as the results filing (the census never read one)."),
    ("spec_per_event_units", "Stage 1 and 3 statistic: x_e = u_e * (fund + hedge P&L per unit notional), u_e = 1/m, mean "
                             "over events, cluster_t by sponsor x day 0 (the literal 'raw units'); the mean of group "
                             "means is printed beside it. Rule: keep, or decide on the group means."),
]


def stage0(edgar_only: bool, client=None, write: bool = True) -> dict:
    """Stage 0 (prereg §12, stage 0). Part A reads EDGAR (DG-NT-1, DG-NT-2 and the 20% gate);
    part B needs the staged CRSP extracts (DG-NT-3..6, the quality screen, the hedge and beta).
    Every halt raises `Stage0Halt` after the record is written. The rulings block runs last."""
    inp = load_inputs()
    client = client or offline_client()
    names = None
    if not edgar_only:
        miss = crsp_cache_missing()
        if miss:
            raise Stage0Halt("CRSP is not staged in this checkout (" + ", ".join(miss) + "). The team lead runs "
                             "`QUANTT_ENV_FILE=... python3 scripts/events/nav_tender_trial.py stage --ibkr <usa.txt>`; "
                             "agents never load the env file.")
        from scripts.events import crsp_events as ce
        names = ce.names()
    cef_tickers = None if names is None else set(names.loc[names["shrcd"].isin((14, 44)), "ticker"].dropna())
    ev = read_events(inp, client, edgar_only=edgar_only, cef_tickers=cef_tickers)
    ev = schedule(ev)
    ev["group"] = groups_of(ev)
    el = eligible(ev)
    rec = {"stamp": STAMP, "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "part": "A (EDGAR only)" if edgar_only else "A+B", "events_census": int(len(ev)),
           "in_universe_excluded": int(ev["in_universe"].astype(bool).sum()),
           "merger_open_excluded": int((~ev["in_universe"].astype(bool) & ev["merger_open"].astype(bool)).sum())}
    by = {}
    for per in ("fit", "gap", "holdout", "after_crsp"):
        x = ev[el & (ev["period"] == per)]
        by[per] = {"events": int(len(x)), "groups": int(x["group"].nunique()),
                   "completed": int((x["outcome"] == "completed").sum()),
                   "terminated": int((x["outcome"] == "terminated").sum()),
                   "unread": int((x["outcome"] == "unread").sum()),
                   "redated": int((x["dg1"] == "redated").sum()),
                   "cutoff_fail": int((x["cutoff_ok"] == False).sum()),  # noqa: E712
                   "pi_second_method": int(x["pi_how"].fillna("").str.startswith("second method").sum())}
    rec["periods"] = by
    rec["gate_fit"] = dg_nt2_gate(ev, "fit")
    rec["gate_holdout_count_only"] = dg_nt2_gate(ev, "holdout")
    rec["uncached_documents"] = int(sum(len(u) for u in ev["uncached"]))
    unread1 = el & ev["dg1"].fillna("").str.startswith("UNREAD")
    rec["unread_dg1"] = ev.loc[unread1 & (ev["period"] == "fit"), "label"].tolist()
    rec["unread_dg1_holdout_read_at_its_stage0"] = ev.loc[unread1 & (ev["period"] == "holdout"), "label"].tolist()
    flags = edgar_flags(ev)
    for chk, note in SPEC_FLAGS:
        flags.loc[len(flags)] = {"check": chk, "ticker": "-", "date": STAMP, "period": "all", "event_id": "-", "note": note}
    if write:
        TRIAL_DIR.mkdir(parents=True, exist_ok=True)
        cols = [c for c in TRACKED_EVENT_COLS if c in ev.columns]
        out = ev[cols].copy()
        out["uncached"] = out["uncached"].map(lambda u: ";".join(u))
        out.to_csv(STAGE0_EVENTS, index=False)
    S = {"rec": rec, "ev": ev, "flags": flags}
    halt = None
    if rec["unread_dg1"]:
        halt = f"DG-NT-1: {len(rec['unread_dg1'])} flagged events have no Stage-0 reading: {rec['unread_dg1'][:10]}"
    elif rec["gate_fit"]["verdict"] == "FAIL":
        g = rec["gate_fit"]
        halt = (f"DG-NT-2 FAIL: {g['unread_lo']} of {g['events']} fit events ({g['share_lo']:.1%}) have an unread "
                f"outcome or P_final, above {EXCLUSION_MAX:.0%}. The run halts before any return; no trial is spent; "
                "the list goes to the team lead (prereg §4.3).")
    elif edgar_only:
        halt = ("Stage 0 part A recorded (EDGAR). Part B (DG-NT-3..6, the quality screen, hedge and beta, the 20% gate's "
                f"{rec['gate_fit']['deferred']} deferred events) needs the CRSP staging run by the team lead.")
    try:
        if halt is None:
            S.update(stage0_partB(ev, names, flags, rec))
    finally:
        if write:
            flags.to_csv(FLAGS, index=False)
            STAGE0_JSON.write_text(json.dumps(_jsonable(rec), indent=1, sort_keys=True))
    if halt is not None:
        raise Stage0Halt(halt)
    return S


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (pd.Timestamp, date)):
        return str(pd.Timestamp(o).date())
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    return o


def stage0_partB(ev: pd.DataFrame, names: pd.DataFrame, flags: pd.DataFrame, rec: dict) -> dict:
    """DG-NT-3..6, the hedge, beta and the quality screen on the FIT events; then the rulings block.
    Returns the checked data for the fit run."""
    from scripts.cef.data_guards import require_stage0_rulings, stage0_rulings_template
    from scripts.events import crsp_events as ce
    from scripts.events import e1_etf_hedge_gate as g
    el = eligible(ev)
    t = ev[el & (ev["period"] == "fit") & ev["outcome"].isin(("completed", "terminated"))].copy()
    rec["cutoff_not_traded"] = int((t["cutoff_ok"] == False).sum())  # noqa: E712
    t = t[t["cutoff_ok"] == True].copy()  # noqa: E712
    t["tradable_pre_overlap"] = True
    t["cik"] = t["cik"].astype(int)
    blk = one_position_per_fund(t)
    rec["overlap_not_entered"] = int(blk.sum())
    t = t[~blk].copy()
    t = fund_permnos(t, names)
    rec["unmapped_permno"] = t.loc[t["permno"].isna(), "label"].tolist()
    t = t[t["permno"].notna()].copy()
    t["permno"] = t["permno"].astype(int)
    rec["universe_check"] = assert_no_universe(t, names)
    plist = json.loads(PERMNO_LIST.read_text())["permnos"]
    need_etf, etf_unresolved = etf_permnos_resolved(names, hedge_symbols())
    rec["etf_unresolved_in_crsp"] = etf_unresolved
    for f in FACTOR_ETFS + ("SPY",):
        if f not in need_etf:
            raise Stage0Halt(f"DG-NT-5: CRSP cannot name {f}: {etf_unresolved.get(f)}")
    missing = sorted(set(t["permno"]) - set(plist)) + sorted(set(need_etf.values()) - set(plist))
    if missing:
        raise Stage0Halt(f"{len(missing)} needed permnos are not in the staged batch ({PERMNO_LIST.name}): re-run `stage`")
    dsf = daily_raw(plist)
    dl = ce.delistings()
    sessions = pd.DatetimeIndex(sorted(dsf.loc[dsf["permno"] == need_etf["SPY"], "date"].unique()))
    sessions = sessions[sessions >= pd.Timestamp("2008-01-01")]   # the first beta window starts in 2008
    cal = sessions_between(sessions[0], sessions[-1])
    if not sessions.equals(cal):
        raise Stage0Halt(f"CRSP's SPY dates and the NYSE calendar differ: {sorted(set(sessions) ^ set(cal))[:5]}")
    etf_frames = g.series(dsf[dsf["permno"].isin(need_etf.values())])
    etf_ret = {s: etf_frames[p]["ret"].reindex(sessions) for s, p in need_etf.items()}
    fund_frames = g.series(dsf[dsf["permno"].isin(set(t["permno"]))])
    dg4 = load_dg4()
    rec["dg4"] = {"alpaca_read": dg4["alpaca"].get("read_utc"), "ibkr_stamp": dg4["ibkr"].get("stamp")}
    if str(dg4["alpaca"].get("read_utc", ""))[:10] != str(dg4["ibkr"].get("date", "")):
        flags.loc[len(flags)] = {"check": "spec_dg4_reads", "ticker": "-", "date": STAMP, "period": "all", "event_id": "-",
                                 "note": f"Alpaca read {dg4['alpaca'].get('read_utc')} and IBKR file "
                                         f"{dg4['ibkr'].get('stamp')} are not one date (§4.4)"}
    rows, fund_data = [], {}
    for r in t.itertuples():
        pl_end = r.last_session
        valid = fund_frames[r.permno].index[fund_frames[r.permno]["idx"].notna()]
        win = g.windows(valid, r.day0, BETA_TEST_H)
        if win is None:
            rows.append({"eid": r.event_id, "excluded": "beta: no beta history"})
            continue

        def covered(sym, s_est=win[0], pl_end=pl_end):
            """CRSP returns for the ETF over the beta window and the hold (§5.2)."""
            return bool(etf_ret[sym].loc[s_est:pl_end].notna().all())
        sym, route, fee, why = hedge_route(r.asset_class, dg4, covered)
        if sym is None:
            rows.append({"eid": r.event_id, "excluded": f"hedge: {why}"})
            continue
        b = beta_for(fund_frames[r.permno], etf_frames[need_etf[sym]], r.day0)
        if b["beta"] is None:
            rows.append({"eid": r.event_id, "excluded": f"beta: {b['status']}"})
            continue
        try:
            fs = series_on(dsf, r.permno, sessions, add_sessions(r.day0, 2) - pd.Timedelta(days=10), pl_end, dl)
        except TrialError as e:
            rows.append({"eid": r.event_id, "excluded": f"DG-NT-3: {e}"})
            continue
        if fs["delisted"] is not None:
            flags.loc[len(flags)] = {"check": "quality_delisted_in_hold", "ticker": r.label, "date": str(r.ann_date.date()),
                                     "period": "fit", "event_id": r.event_id, "note": f"delisted {fs['delisted'][0].date()}"}
        hold = sessions[(sessions >= add_sessions(r.day0, 2)) & (sessions <= pl_end)]
        big = fs["ret"].reindex(hold).abs() > ABS_RET_FLAG
        for d in hold[big.values]:
            flags.loc[len(flags)] = {"check": "quality_abs_ret", "ticker": r.label, "date": str(d.date()),
                                     "period": "fit", "event_id": r.event_id,
                                     "note": f"|ret| > 50% inside the hold of the event of {r.ann_date.date()}"}
        nc = dsf[(dsf["permno"] == r.permno) & dsf["date"].isin([r.entry_session, pl_end]) & dsf["no_close"]]
        for d in nc["date"]:
            flags.loc[len(flags)] = {"check": "quality_no_close", "ticker": r.label, "date": str(pd.Timestamp(d).date()),
                                     "period": "fit", "event_id": r.event_id,
                                     "note": f"CRSP prc < 0 (no closing trade) on the entry or exit session of the "
                                             f"event of {r.ann_date.date()}"}
        full = series_on(dsf, r.permno, sessions, sessions[0], FIT_LAST_SESSION, None, tolerant=True)
        fund_data[r.event_id] = {"ret": fs["ret"].reindex(sessions), "close": fs["close"].reindex(sessions),
                                 "bridged": fs["bridged"], "full_ret": full["ret"].reindex(sessions),
                                 "full_frame": fund_frames[r.permno], "etf_frame": etf_frames[need_etf[sym]]}
        # report-only inputs (prereg §10): the residual sold 10 sessions after pricing needs a
        # longer priced window; None (counted) where it runs past the fit or cannot be priced.
        F10 = exit_session(r.outcome_session, r.x_p, 10, terminated=(r.outcome == "terminated"))
        try:
            if add_sessions(F10, 1) > FIT_LAST_SESSION:
                raise TrialError("past the fit")
            f10 = series_on(dsf, r.permno, sessions, add_sessions(r.day0, 2) - pd.Timedelta(days=10),
                            add_sessions(F10, 1), dl)
            fund_data[r.event_id].update(ret10=f10["ret"].reindex(sessions), close10=f10["close"].reindex(sessions))
        except TrialError:
            fund_data[r.event_id].update(ret10=None, close10=None)
        from scripts.events.cef_corp_action_census import adv_before, post_discount
        adv = adv_before(dsf, r.permno, r.day0)
        disc, why = None, "no offer-stated NAV"
        if not pd.isna(r.nav) and not pd.isna(r.nav_date):
            cl = dsf.loc[(dsf["permno"] == r.permno) & (dsf["date"] == pd.Timestamp(r.nav_date)), "prc"]
            disc, why = post_discount(float(r.nav), r.nav_date, r.day0, float(cl.iloc[0]) if len(cl) else None)
        rows.append({"eid": r.event_id, "excluded": None, "etf": sym, "route": route, "fee_pct": fee, "beta": b["beta"],
                     "beta_ols": b["beta_ols"], "beta_n": b["n"], "adv_usd": adv, "disc_post": disc, "disc_post_why": why})
    X = pd.DataFrame(rows)
    rec["excluded_partB"] = X.loc[X["excluded"].notna(), "excluded"].value_counts().to_dict() if len(X) else {}
    X = X[X["excluded"].isna()].drop(columns="excluded")
    t = t.rename(columns={"event_id": "eid"}).merge(X, on="eid", how="inner", validate="one_to_one")
    ff = load_ff()
    fac = factor_frame(ff, {s: etf_ret[s] for s in FACTOR_ETFS})
    cover = fac.loc["2009-01-02":"2022-12-30"].dropna()
    rec["dg_nt5"] = {"ff_first": str(ff["date"].min().date()), "ff_last": str(ff["date"].max().date()),
                     "ff_vintage": str(ff["crsp_vintage"].iloc[0]) if "crsp_vintage" in ff else None,
                     "factor_rows_2009_2022": int(len(cover))}
    if ff["date"].min() > pd.Timestamp("2009-01-02") or ff["date"].max() < pd.Timestamp("2022-12-30"):
        raise Stage0Halt("DG-NT-5: the French factors do not cover 2009-01 .. 2022-12")
    rec["traded_fit"] = {"events": int(len(t)), "groups": int(t["group"].nunique()),
                         "ibkr_routed": int((t["route"] == "ibkr").sum()),
                         "beta_median": float(t["beta"].median()), "beta_q10": float(t["beta"].quantile(0.1)),
                         "beta_q90": float(t["beta"].quantile(0.9)),
                         "bridged_days": int(sum(v["bridged"] for v in fund_data.values()))}
    if not RULINGS.exists() and len(flags):
        stage0_rulings_template(flags[["check", "ticker", "date"]], RULINGS)
    from scripts.cef.data_guards import Stage0BlockError
    try:
        ruled = require_stage0_rulings(flags[["check", "ticker", "date"]], RULINGS, context="NAV-tender Stage 0")
    except Stage0BlockError as e:
        raise Stage0Halt(f"the rulings block (prereg skill §4b): {e}") from None
    first_pl = add_sessions(t["day0"].min(), 2)
    D = Data(ev=t, fund=fund_data, etf=etf_ret, sessions=sessions, factors=fac, t_first=first_pl,
             t_last=FIT_LAST_SESSION, etf_frames={s: etf_frames[p] for s, p in need_etf.items()})
    return {"data": D, "ruled": ruled, "flags": flags}


# ===================================================================== the fit (stages 1-5)

def verdict_of(stages: dict) -> str:
    """The first rule that fails, in the declared order (prereg §12); stage 7 is the holdout's."""
    order = [("1", "KILL D1 (stage 1: per-event cluster t < 2.0)"),
             ("2", "KILL D1 (stage 2: real mean at or below the placebo p95)"),
             ("3", "KILL D2 (stage 3: net per-event mean at 15bp, cluster t < 2.0)"),
             ("4", "KILL D4 (stage 4: alpha t < 3.0 or a summed |beta| > 0.10)"),
             ("5", "NEITHER (stage 5: _dsr <= 0.95 at N = 6; the team lead rules WATCH or D5)")]
    for k, label in order:
        if not stages[k]["pass"]:
            return label
    return "FIT PASSES stages 1-5 (the holdout, stage 7, decides PASS or KILL D3)"


def fit_on(D: Data, episodes: pd.DataFrame, capital: float, cap: float | None,
           placebo_draws: int = PLACEBO_DRAWS, quality_ids: set | None = None, book: pd.Series | None = None) -> dict:
    """Every statistic of every fit stage, whatever the verdict (prereg §12), plus the grid,
    borrow, fees, the report-only rows and the robustness block. Aggregates only."""
    from scripts.cef.spec import VOL_TARGET
    ev = D.ev
    events = to_events(ev)
    run = run_pnl(D, events, None, cap)
    a, b = D.t_first, D.t_last
    pe = per_event(D, events, run["raw"]["ledger"])
    s1 = cluster_stats(pe["gross"], pe["group"])
    s1["mean_of_group_means"] = float(pe.groupby("group")["gross"].sum().mean())
    s1["pass"] = s1["cluster_t"] >= T_BAR
    pl = placebo(D, events, episodes, ev, draws=placebo_draws)
    dm = pl.pop("draw_means")
    pl["share_draw_means_ge_real"] = float(np.nanmean(dm >= s1["mean"]))
    s2 = {**pl, "real_mean": s1["mean"], "pass": bool(s1["mean"] > pl["p95"])}
    pe15 = per_event(D, events, run["raw"]["ledger"], STAGE3_BP)
    s3 = cluster_stats(pe15["net"], pe15["group"])
    s3["pass"] = s3["cluster_t"] >= T_BAR
    pt = run["pnl_trad"].loc[a:b]
    sig_t = float(pt.std() * np.sqrt(252))
    s4 = rd4(pt, D.factors, VOL_TARGET / sig_t)
    s4["pass"] = s4["pass"]
    s5 = sleeve_stats(run["pnl_trad"], run["turn_trad"], a, b)
    s5["pass"] = s5["dsr"] > DSR_PASS
    stages = {"1": s1, "2": s2, "3": s3, "4": s4, "5": s5}
    out = {"verdict": verdict_of(stages), "stages": stages,
           "sizing": {"sigma_active": run["sigma_active"], "k": run["k"], "vol_target": VOL_TARGET, "cap": cap,
                      "entered_below_size": int(sum(1 for v in run["scale"].values() if v < 1)),
                      "not_entered": int(sum(1 for v in run["scale"].values() if v == 0)),
                      "events": len(events)},
           "grid_tradable": grid(run["pnl_trad"], run["turn_trad"], a, b),
           "grid_raw": grid(run["pnl_raw"], run["turn_raw"], a, b),
           "borrow_tradable": borrow_line(run["trad"], ev, a, b)}
    for cap_usd in (capital, 1_000_000.0):
        fee = election_fee_series(events, run["w"], D.sessions, cap_usd).loc[a:b]
        out[f"election_fee_ann_at_{int(cap_usd)}"] = float(fee.mean() * 252)
    # ETF legs at 5bp, fund legs on the grid
    Q = run["trad"]["Q"]
    qf = Q[[e.eid for e in events]].abs().sum(axis=1).loc[a:b]
    qe = Q.drop(columns=[e.eid for e in events]).abs().sum(axis=1).loc[a:b]
    out["etf_legs_at_5bp"] = {str(c): float((pt.mean() * 252 - (qf.mean() * c + qe.mean() * 5) * 252 / 1e4) / (pt.std() * np.sqrt(252)))
                              for c in COSTS_BP}
    # eras (H5), with turnover sd/mean
    eras = {}
    for lab, ea, eb in ERAS:
        x = pe[(pe["day0"] >= ea) & (pe["day0"] <= eb)]
        tq = run["turn_trad"].loc[ea:eb]
        eras[lab] = {"events": int(len(x)), "groups": int(x["group"].nunique()),
                     **({k: v for k, v in cluster_stats(x["gross"], x["group"]).items() if k in ("mean", "cluster_t")}
                        if x["group"].nunique() >= 2 else {}),
                     "sleeve_gross_sr": grid(run["pnl_trad"], run["turn_trad"], ea, eb)["gross"],
                     "turn_sd_over_mean": float(tq.std() / tq.mean()) if tq.mean() > 0 else None}
    out["eras"] = eras
    yr = pt.groupby(pt.index.year).sum()
    out["calendar_year_positive_share"] = float((yr > 0).mean())
    gsum = pe.groupby("group")["gross"].sum()
    out["largest_group_share_of_pnl"] = float(gsum.abs().max() / gsum.sum()) if gsum.sum() != 0 else None
    logo = [(pe.loc[pe["group"] != gg, "gross"].mean()) for gg in gsum.index]
    out["leave_one_group_out_mean"] = {"min": float(np.min(logo)), "median": float(np.median(logo)), "max": float(np.max(logo))}
    out["report_only"] = report_only_rows(D, events, run, pe)
    out["report_only"]["mechanism_slope"] = mechanism_slope(ev, pe)
    out["report_only"]["capacity"] = capacity(ev, events, run["w"])
    out["report_only"]["r_book"] = r_book(run["pnl_trad"].loc[a:b], book)
    out["robustness"] = robustness(D, ev, episodes, cap, quality_ids or set())
    return out


def mechanism_slope(ev: pd.DataFrame, pe: pd.DataFrame) -> dict:
    """Report-only (prereg §8): per-event gross P&L per unit notional on the terms-implied spread of
    the accepted slice, (k x NAV) / price - 1 (`census.accepted_slice_spread`), on the events whose
    offer-stated NAV is dated on or after day 0 (the census's `disc_post` rule,
    `census.post_discount`, applied at the trial's day 0). OLS, t clustered by group. The
    mechanism predicts a positive slope."""
    import statsmodels.api as sm
    from scripts.events.cef_corp_action_census import accepted_slice_spread
    x = ev[["eid", "k_pct", "disc_post"]].merge(pe[["eid", "per_notional", "group"]], on="eid")
    x = x[x["disc_post"].notna() & x["k_pct"].notna()].copy()
    if len(x) < 5 or x["group"].nunique() < 3:
        return {"n": int(len(x)), "not computed": "fewer than 5 events with a post-announcement NAV"}
    x["spread"] = [accepted_slice_spread(float(k), float(d)) for k, d in zip(x["k_pct"], x["disc_post"])]
    m = sm.OLS(x["per_notional"].astype(float), sm.add_constant(x["spread"].astype(float))).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(x["group"])[0]})
    return {"n": int(len(x)), "groups": int(x["group"].nunique()), "slope": float(m.params["spread"]),
            "slope_t_cluster": float(m.tvalues["spread"]), "spread_median": float(x["spread"].median())}


def capacity(ev: pd.DataFrame, events: list[Ev], w: dict) -> dict:
    """Report-only (prereg §10): each event's entry is its tradable weight times capital; against
    its 63-session ADV before day 0 (`census.adv_before`). The capital at which the median event's
    entry reaches 1% and 5% of ADV; participation and the election fee (bp of the event's
    notional) at $100k, $1m and $10m."""
    adv = ev.set_index("eid")["adv_usd"]
    rows = [(e.eid, w.get(e.eid, 0.0), adv.get(e.eid)) for e in events]
    rows = [(i, ww, a) for i, ww, a in rows if ww > 0 and a is not None and np.isfinite(a) and a > 0]
    if not rows:
        return {"not computed": "no entered event with an ADV"}
    W = np.array([r[1] for r in rows])
    A = np.array([r[2] for r in rows])
    out = {"events": len(rows), "adv_median_usd": float(np.median(A))}
    for x in (0.01, 0.05):
        out[f"capital_at_{int(x * 100)}pct_adv_median_event_usd"] = float(np.median(x * A / W))
    for C in (100_000.0, 1_000_000.0, 10_000_000.0):
        part = W * C / A
        out[f"at_{int(C)}"] = {"participation_median": float(np.median(part)), "participation_max": float(part.max()),
                               "election_fee_bp_of_notional_median": float(np.median(ELECTION_FEE_USD / (W * C) * 1e4))}
    return out


def book_pnl() -> pd.Series:
    """The deployed CEF book's daily total-return P&L, as `scripts/xasset/book_profile.py` builds it
    (band to edge, gross-capped by the spec, evaluate() on total returns)."""
    from scripts.cef.band_frontier import band_gross_capped, build_targets, evaluate, total_returns
    from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS
    if MAX_GROSS_STRESS is None:
        raise TrialError("spec has no max_gross_stress")
    T_, R_ = build_targets()
    H_ = band_gross_capped(T_, BAND_WIDTH, MAX_GROSS_STRESS)
    return evaluate(H_, total_returns(R_))["pnl"]


def r_book(pnl: pd.Series, book: pd.Series | None) -> dict:
    """R-BOOK (prereg §9), report-only, never a kill: correlation and beta of the tradable sleeve's
    daily P&L with the deployed book's, on the dates both exist and the book holds a position."""
    if book is None:
        return {"not computed": "no book P&L supplied"}
    d = pd.concat([pnl.rename("s"), book.rename("b")], axis=1, join="inner").dropna()
    d = d[d["b"] != 0]
    if len(d) < 60:
        return {"not computed": f"{len(d)} overlapping sessions"}
    beta = float(np.cov(d["s"], d["b"])[0, 1] / d["b"].var())
    return {"n": int(len(d)), "first": str(d.index[0].date()), "last": str(d.index[-1].date()),
            "corr": float(d["s"].corr(d["b"])), "beta_on_book": beta}


def report_only_rows(D: Data, events: list[Ev], run: dict, pe: pd.DataFrame) -> dict:
    """The no-tender twin B, A - B, the late entry and shift(3) (prereg §8); none decides."""
    from scripts.cef.band_frontier import evaluate
    pos = {d: i for i, d in enumerate(D.sessions)}
    fr = {e.eid: D.fund[e.eid]["ret"] for e in events}
    fc = {e.eid: D.fund[e.eid]["close"] for e in events}
    out = {}
    tw = [e for e in events if e.x_p is not None]
    exit_b = {e.eid: D.sessions[pos[e.x_p] - 2] for e in tw}
    MB = build_matrices(tw, fr, fc, D.etf, D.sessions, exit_=exit_b, elect=False)
    sleeve_pnl(MB)
    peB = per_event_table(tw, MB["ledger"], {e.eid: e.pi for e in tw})
    peA = pe[pe["eid"].isin(peB["eid"])].set_index("eid").loc[peB["eid"]].reset_index()
    out["twin_B"] = cluster_stats(peB["gross"], peB["group"])
    diff = peA["gross"].values - peB["gross"].values
    out["A_minus_B"] = cluster_stats(pd.Series(diff), peB["group"])
    late = {}
    clipped = 0
    for e in tw:
        r = D.ev.loc[D.ev["eid"] == e.eid].iloc[0]
        E = session_on_or_before(r["expiry"])
        d = D.sessions[pos[E] - CUTOFF_SESSIONS - 5 - 1]
        if d < e.day0:
            d, clipped = e.day0, clipped + 1
        late[e.eid] = d
    ML = build_matrices(tw, fr, fc, D.etf, D.sessions, entry=late)
    sleeve_pnl(ML)
    peL = per_event_table(tw, ML["ledger"], {e.eid: e.pi for e in tw})
    out["late_entry"] = {**cluster_stats(peL["gross"], peL["group"]), "clipped_to_day0": clipped}
    # shift(3): the same decisions one session later. R is built only on each event's own P&L
    # sessions, so the delayed hold's last session (F + 2) earns 0 here: an approximation, labelled.
    raw = run["raw"]
    p3 = evaluate(raw["H"].shift(1).fillna(0.0), raw["R"].fillna(0.0))["pnl"].loc[D.t_first:D.t_last]
    out["shift3_raw_sleeve_sr"] = float(p3.mean() / p3.std() * np.sqrt(252))
    return out


def robustness(D: Data, ev: pd.DataFrame, episodes: pd.DataFrame, cap: float | None,
               quality_ids: set | None = None) -> dict:
    """Reported, never chosen from, and none of it rescues a failed headline (prereg §10)."""
    out = {}

    def row(events, label, D_=None, **kw):
        D_ = D_ or D
        try:
            r = run_pnl(D_, events, None, cap, **kw)
            pe = per_event(D_, events, r["raw"]["ledger"])
            cs = cluster_stats(pe["gross"], pe["group"]) if pe["group"].nunique() >= 2 else {"n": len(pe)}
            out[label] = {"per_event": {k: cs.get(k) for k in ("n", "groups", "mean", "cluster_t")},
                          "sleeve": grid(r["pnl_trad"], r["turn_trad"], D_.t_first, D_.t_last)}
        except (TrialError, AssertionError, ValueError) as e:
            out[label] = {"not computed": str(e)}
    row(to_events(ev, unit="event"), "one unit per event")
    row(to_events(ev, beta_mode="one"), "beta = 1")
    row(to_events(ev, beta_mode="zero"), "beta = 0 (unhedged)")
    row(to_events(ev[ev["route"] == "alpaca"]), "Alpaca-only hedges (IBKR-routed dropped)")
    row(to_events(ev[ev["asset_class"].isin(CREDIT_CLASSES)]), "credit classes only")
    for lab, mask in (("programme stratum", ev["programme"].astype(bool)),
                      ("offers for >= 50% of shares", ev["size_pct"].fillna(0) >= 50),
                      ("re-dated stratum", ev["dg1"] == "redated"),
                      ("second-method pi stratum", ev["pi_how"].fillna("").str.startswith("second method")),
                      ("day-0 form SC TO-C", ev["ann_form"] == "SC TO-C")):
        if mask.sum() >= 2:
            row(to_events(ev[mask]), lab)
        else:
            out[lab] = {"n": int(mask.sum())}
    # the residual decided at the outcome filing alone (lag 0) and 10 sessions after pricing
    ev0 = ev.copy()
    ev0["F"] = [exit_session(o, x, 0, terminated=(oc == "terminated"))
                for o, x, oc in zip(ev0["outcome_session"], ev0["x_p"], ev0["outcome"])]
    row(to_events(ev0), "residual lag 0 (outcome filing only)")
    ok10 = [i for i in ev["eid"] if D.fund[i].get("ret10") is not None]
    ev10 = ev[ev["eid"].isin(ok10)].copy()
    ev10["F"] = [exit_session(o, x, 10, terminated=(oc == "terminated"))
                 for o, x, oc in zip(ev10["outcome_session"], ev10["x_p"], ev10["outcome"])]
    D10 = Data(ev=ev10, fund={i: {**D.fund[i], "ret": D.fund[i]["ret10"], "close": D.fund[i]["close10"]} for i in ok10},
               etf=D.etf, sessions=D.sessions, factors=D.factors, t_first=D.t_first, t_last=D.t_last,
               etf_frames=D.etf_frames)
    row(to_events(ev10), f"residual lag 10 ({len(ok10)} of {len(ev)} events priced to F + 1)", D_=D10)
    q = ev[~ev["eid"].isin(quality_ids or set())]
    row(to_events(q), f"quality-screen events removed ({len(ev) - len(q)} removed)")
    # muni events hedged with IEF (duration only), beta re-estimated on IEF with the declared rule
    if D.etf_frames is not None and "IEF" in D.etf_frames:
        evI = ev.copy()
        dropped = 0
        for i in evI.index[evI["asset_class"] == "muni"]:
            b = beta_for(D.fund[evI.at[i, "eid"]]["full_frame"], D.etf_frames["IEF"], evI.at[i, "day0"])
            if b["beta"] is None:
                dropped += 1
                evI = evI.drop(index=i)
                continue
            evI.at[i, "etf"], evI.at[i, "beta"], evI.at[i, "route"] = "IEF", b["beta"], "alpaca"
        row(to_events(evI), f"muni hedged with IEF ({int((ev['asset_class'] == 'muni').sum())} muni events, {dropped} without an IEF beta)")
    try:
        r = run_pnl(D, to_events(ev), None, None)
        out["uncapped sized sleeve"] = grid(r["pnl_trad"], r["turn_trad"], D.t_first, D.t_last)
    except (TrialError, AssertionError, ValueError) as e:
        out["uncapped sized sleeve"] = {"not computed": str(e)}
    return out


def fit_verdict_committed() -> bool:
    """True when FIT_JSON exists with a verdict and is committed in this checkout's history."""
    if not FIT_JSON.exists() or "verdict" not in json.loads(FIT_JSON.read_text()):
        return False
    r = subprocess.run(["git", "log", "--format=%H", "--", str(FIT_JSON.relative_to(REPO))], cwd=REPO,
                       capture_output=True, text=True, check=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "--", str(FIT_JSON.relative_to(REPO))], cwd=REPO,
                           capture_output=True, text=True, check=True)
    return bool(r.stdout.strip()) and not dirty.stdout.strip()


def fit() -> dict:
    """Stages 1-5 on the fit, after Stage 0 and its rulings. Writes FIT_JSON (aggregates)."""
    from scripts.cef.spec import CAPITAL_USD, MAX_GROSS_STRESS
    if FIT_JSON.exists():
        raise TrialError(f"{FIT_JSON.name} exists: the fit runs once")
    S = stage0(edgar_only=False)
    inp = load_inputs()
    fl = S["flags"]
    quality = set(fl.loc[fl["check"].str.startswith("quality_"), "event_id"])
    try:
        book = book_pnl()
    except Exception as e:  # noqa: BLE001 -- report-only (§9): the failure is recorded, never filled
        book = None
        S["rec"]["r_book_error"] = f"{type(e).__name__}: {e}"
    res = fit_on(S["data"], inp["episodes"], CAPITAL_USD, MAX_GROSS_STRESS, quality_ids=quality, book=book)
    res["stage0"] = S["rec"]
    FIT_JSON.write_text(json.dumps(_jsonable(res), indent=1, sort_keys=True))
    return res


# ===================================================================== the holdout (stage 7)

def holdout_daily(permnos, refresh: bool = False) -> pd.DataFrame:
    """CRSP `dsf` rows 2023-01-01 .. 2024-12-31 for `permnos`: the holdout reader, a separate
    function from the fit's `crsp_events.daily` (prereg §4.4). It refuses to run until the fit
    verdict is committed; the pull itself needs R2 (the team lead's `stage --holdout`)."""
    from scripts.events import crsp_events as ce
    if not fit_verdict_committed():
        raise TrialError("the holdout opens only after the fit verdict is committed (prereg §7)")
    s, h = ce._plist(permnos)
    df = ce._pull(f"dsf_holdout_{h}",
                  "SELECT permno, date, prc, ret, retx, vol, shrout, cfacpr FROM read_parquet('{dsf}') "
                  f"WHERE permno IN ({s}) AND date >= DATE '2023-01-01' AND date <= DATE '2024-12-31'", refresh)
    df["date"] = pd.to_datetime(df["date"])
    if len(df) and (df["date"].min() < HOLDOUT_START or df["date"].max() > HOLDOUT_LAST_SESSION):
        raise AssertionError("holdout extract outside 2023-01-01 .. 2024-12-31")
    df["no_close"] = df["prc"].astype(float) < 0
    df["prc"] = df["prc"].astype(float).abs()
    return df


def holdout() -> dict:
    """Stage 7, opened once after the fit verdict's commit: (a) the mean per-event gross P&L > 0
    and (b) the tradable sleeve's mean daily gross P&L > 0, with k and the beta rule frozen from
    the fit (beta rolls). Its own Stage 0 comes first, and its 20% unread gate first of all
    (prereg §4.3, §11.1: "If it fails on the holdout, the holdout halts and is reported; the fit
    verdict stands"). That gate reads EDGAR only, so a failing holdout is recorded without any
    2023-24 price being read."""
    if HOLDOUT_JSON.exists():
        raise TrialError(f"{HOLDOUT_JSON.name} exists: the holdout opens once")
    if not fit_verdict_committed():
        raise TrialError("the fit verdict is not committed: the holdout stays sealed")
    S = stage0(edgar_only=False, write=False)
    g = S["rec"]["gate_holdout_count_only"]
    out = {"opened_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "fit_verdict": json.loads(FIT_JSON.read_text())["verdict"], "gate": g,
           "holdout_events_unread": S["ev"].loc[eligible(S["ev"]) & (S["ev"]["period"] == "holdout")
                                                & (S["ev"]["outcome"] == "unread"), "label"].tolist()}
    if g["verdict"] == "FAIL":
        out["verdict"] = ("HALTED at the holdout's 20% unread gate (prereg §4.3, §11.1): no 2023-24 price or return "
                          "was read; the fit verdict stands")
        HOLDOUT_JSON.write_text(json.dumps(_jsonable(out), indent=1, sort_keys=True))
        return out
    raise Stage0Halt("the holdout's gate passes: its Stage 0 needs the 2023-24 CRSP extract (`stage --holdout`, the "
                     "team lead) and the holdout events' DG-NT-1 readings and rulings")


def rederive() -> dict:
    """A second method for the fit's headline numbers (CLAUDE.md data rules: double-check what
    drives a decision). Independent of `build_matrices`, `evaluate`, `cluster_t` and the Stage-0
    return series: it reads CRSP's rows again through `crsp_events.daily`, writes each event's
    daily P&L in a plain loop (the fund's return, the tender row on X_p, (1 - pi) after it, minus
    beta times the ETF's return, on sessions day 0 + 2 .. F + 1), and computes the per-event mean,
    a CR1 cluster t and both sleeves' Sharpes by hand. Sizing (k and the cap) is taken from the
    first method: this checks the P&L arithmetic and the alignment, not the sizing rule."""
    from scripts.events import crsp_events as ce
    fit_res = json.loads(FIT_JSON.read_text())
    S = stage0(edgar_only=False, write=False)
    D = S["data"]
    ev = D.ev
    plist = json.loads(PERMNO_LIST.read_text())["permnos"]
    dsf = ce.daily(plist)
    names = ce.names()
    etf_p, _ = etf_permnos_resolved(names, hedge_symbols())
    by = {p: g.set_index("date").sort_index() for p, g in dsf.groupby("permno")}
    sess = D.sessions
    pos = {d: i for i, d in enumerate(sess)}
    m = ev.groupby("group")["eid"].transform("size")
    daily_raw_, per = {}, []
    for (_, r), mm in zip(ev.iterrows(), m):
        u = 1.0 / mm
        f, x = by[int(r["permno"])], by[etf_p[r["etf"]]]
        pl = sess[pos[r["day0"]] + 2: pos[r["F"]] + 2]
        tot, rows = 0.0, {}
        for d in pl:
            rf = float(f.at[d, "ret"])
            if r["outcome"] == "completed":
                if d == r["x_p"]:
                    prev = sess[pos[d] - 1]
                    rf = r["pi"] * (r["p_final"] / float(f.at[prev, "prc"]) - 1) + (1 - r["pi"]) * rf
                elif d > r["x_p"]:
                    rf = (1 - r["pi"]) * rf
            v = rf - r["beta"] * float(x.at[d, "ret"])
            rows[d] = v
            tot += v
        daily_raw_[r["eid"]] = (u, pd.Series(rows))
        pi_exit = r["pi"] if r["outcome"] == "completed" else 0.0
        per.append({"eid": r["eid"], "group": r["group"], "x": u * tot,
                    "x15": u * tot - u * STAGE3_BP / 1e4 * (1 + (1 - pi_exit) + 2 * abs(r["beta"]))})
    P = pd.DataFrame(per)

    def cr1(col):
        xb = P[col].mean()
        Gs = P.groupby("group")[col].apply(lambda v: (v - xb).sum())
        nG_ = len(Gs)
        return float(xb), float(xb / np.sqrt(nG_ / (nG_ - 1) * (Gs ** 2).sum() / len(P) ** 2)), nG_
    xbar, t_cr1, nG = cr1("x")
    x15, t15, _ = cr1("x15")
    N = len(P)
    k = fit_res["sizing"]["k"]
    from scripts.cef.spec import MAX_GROSS_STRESS
    w, _ = capped_weights(to_events(ev), k, sess, MAX_GROSS_STRESS)
    raw = pd.Series(0.0, index=sess)
    trad = pd.Series(0.0, index=sess)
    for eid, (u, ser) in daily_raw_.items():
        raw.loc[ser.index] += u * ser.values
        trad.loc[ser.index] += w[eid] * ser.values
    a, b = D.t_first, D.t_last

    def sr(x):
        x = x.loc[a:b]
        return float(x.mean() / x.std() * np.sqrt(252))
    out = {"per_event_mean": float(xbar), "per_event_cluster_t": float(t_cr1), "n": N, "groups": nG,
           "per_event_net15_mean": x15, "per_event_net15_cluster_t": t15,
           "raw_sleeve_sr": sr(raw), "tradable_sleeve_sr": sr(trad),
           "first_method": {"per_event_mean": fit_res["stages"]["1"]["mean"],
                            "per_event_cluster_t": fit_res["stages"]["1"]["cluster_t"],
                            "per_event_net15_mean": fit_res["stages"]["3"]["mean"],
                            "per_event_net15_cluster_t": fit_res["stages"]["3"]["cluster_t"],
                            "raw_sleeve_sr": fit_res["grid_raw"]["gross"],
                            "tradable_sleeve_sr": fit_res["stages"]["5"]["gross_sr"]}}
    (TRIAL_DIR / f"rederive_{STAMP}.json").write_text(json.dumps(_jsonable(out), indent=1, sort_keys=True))
    return out


# ===================================================================== staging (the team lead's run)

def stage(ibkr: str | None, holdout_pull: bool = False) -> None:
    """The credentialed staging the agents never run (CLAUDE.md: credentials stay the team lead's):
    EDGAR documents the offline cache lacks (SEC_USER_AGENT from the env file), CRSP names,
    delistings and ONE batch of fit `dsf` rows (R2), the French factors, and DG-NT-4's Alpaca read
    (cef paper key) beside IBKR's public file on the same date. It computes no return."""
    from scripts.data.edgar_client import EdgarClient
    from scripts.events import crsp_events as ce
    from scripts.events import e1_etf_hedge_gate as g
    from scripts.events.g1a_shortability import alpaca_reads, parse_ibkr_shortstock
    inp = load_inputs()
    names = ce.names()
    ce.delistings()
    cef_tickers = set(names.loc[names["shrcd"].isin((14, 44)), "ticker"].dropna())
    ev = schedule(read_events(inp, EdgarClient(), edgar_only=False, cef_tickers=cef_tickers))
    el = eligible(ev) & ev["outcome"].isin(("completed", "terminated"))
    t = fund_permnos(ev[el], names)
    fit_p = sorted({int(p) for p, per in zip(t["permno"], t["period"]) if not pd.isna(p) and per == "fit"})
    ho_p = sorted({int(p) for p, per in zip(t["permno"], t["period"]) if not pd.isna(p) and per == "holdout"})
    etf_ok, etf_bad = etf_permnos_resolved(names, hedge_symbols())
    if etf_bad:
        print(f"ETFs CRSP cannot name (skipped by the route rule, §5.2): {sorted(etf_bad)}")
    etf_p = sorted(set(etf_ok.values()))
    plist = sorted(set(fit_p) | set(etf_p))
    CACHE.mkdir(parents=True, exist_ok=True)
    PERMNO_LIST.write_text(json.dumps({"permnos": plist, "written_utc": datetime.now(timezone.utc).isoformat()}))
    ce.daily(plist)
    subprocess.run([sys.executable, str(REPO / "scripts" / "data" / "fetch_ff_factors.py")], check=True)
    if ibkr:
        rows, stamp = parse_ibkr_shortstock(Path(ibkr).read_text(encoding="latin-1"))
        today = datetime.strptime(stamp.split()[0], "%Y-%m-%d").date().isoformat() if "-" in stamp else \
            datetime.strptime(stamp.split()[0], "%Y.%m.%d").date().isoformat()
        al = alpaca_reads(hedge_symbols(), today, offline=False)
        ib = rows[rows["symbol"].isin(hedge_symbols())]
        DG4_READS.write_text(json.dumps(_jsonable({
            "alpaca": {"read_utc": str(al["read_utc"].min()), "source": "GET /v2/assets/{symbol}, cef paper key",
                       "symbols": {r.symbol: {"found": r.found is True or r.found == True,  # noqa: E712
                                              "shortable": getattr(r, "shortable", None) is True or getattr(r, "shortable", None) == True,  # noqa: E712
                                              "easy_to_borrow": getattr(r, "easy_to_borrow", None) is True or getattr(r, "easy_to_borrow", None) == True}  # noqa: E712
                                   for r in al.itertuples()}},
            "ibkr": {"stamp": stamp, "date": today, "source": "https://www.interactivebrokers.com/shortstock/usa.txt",
                     "symbols": {r.symbol: {"available": float(r.available), "fee_rate_pct": r.fee_rate_pct}
                                 for r in ib.itertuples()}}}), indent=1, sort_keys=True))
    if holdout_pull:
        holdout_daily(sorted(set(ho_p) | set(etf_p)))


# ===================================================================== CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s0 = sub.add_parser("stage0")
    s0.add_argument("--edgar-only", action="store_true")
    sub.add_parser("fit")
    sub.add_parser("holdout")
    sub.add_parser("rederive")
    st = sub.add_parser("stage")
    st.add_argument("--ibkr")
    st.add_argument("--holdout", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "stage0":
            S = stage0(a.edgar_only)
            print(json.dumps(_jsonable(S["rec"]), indent=1, sort_keys=True))
        elif a.cmd == "fit":
            print(json.dumps(_jsonable(fit()), indent=1, sort_keys=True))
        elif a.cmd == "holdout":
            print(json.dumps(_jsonable(holdout()), indent=1, sort_keys=True))
        elif a.cmd == "rederive":
            print(json.dumps(_jsonable(rederive()), indent=1, sort_keys=True))
        else:
            stage(a.ibkr, a.holdout)
    except Stage0Halt as e:
        if STAGE0_JSON.exists():
            print(STAGE0_JSON.read_text())
        print(f"\nHALT: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
