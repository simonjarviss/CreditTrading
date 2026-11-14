"""Live P&L attribution of the cef paper account: hold, fill, fees, NAV, discount, distributions.

WHY THIS EXISTS (2026-11-02)
----------------------------
The cef paper account lost $982.14 on Alpaca's end-of-day portfolio history from
2026-09-28 to 2026-10-30, 24 sessions [V: read-only GETs by the main session,
2026-11-02]. That session explained the loss by hand. It rebuilt positions from
the account's 344 FILL activities, marked them at SIP daily closes, and split
what was held into what each fund's NAV did and what its discount did. The split
said the loss was NAV, not discount:
  * the NAV part was -$2,251 and the discount part +$1,583;
  * the muni shorts MQY and MHD lost $1,849 on NAV alone, as muni NAVs rose
    4-5% from 10-14 to 10-30 while the taxable names' NAVs moved -0.9% to +0.5%;
  * discounts narrowed in both legs, which is the signal's own bet
[V: same session, scratchpad scripts, not in the repo]. A figure that drives
the book's next decision has to be re-derivable (CLAUDE.md: double-check
anything that drives a decision). This module turns that one-off pass into a
tool with two steps. The second step can be tested, and replayed without keys:

  fetch    read-only GETs plus keyless yfinance -> a cache directory
  analyse  the cache only -> CSVs and a markdown summary

It is research and never on the live path. Nothing in quantt/ or src/deploy/
imports it. It writes nothing the book decides on, it refuses to write under
data/ (CLAUDE.md landmine 9), and it holds no order code. The only broker
methods it calls are the client's GETs.

THE DECOMPOSITION (name s, session t, previous session p)
-----------------------------------------------------------
q_prev is the signed number of shares at p's close, rebuilt from fills (long > 0,
short < 0). For each name and session:

  hold      = q_prev * (close_t - close_p)           the position held into t
  fill      = sum_f signed_qty_f * (close_t - px_f)   each fill against t's close
  nav_part  = q_prev * close_p * (NAV_t / NAV_p - 1)  what the fund's NAV did
  disc_part = hold - nav_part                         what its discount did
  dist      = q_prev * cash_per_share(ex-date == t)   what a real account books

and, once per session over all names (FEES below):

  fees      = -( ceil_cent(SEC rate * value sold on t) + ceil_cent(CAT rate * shares traded on t) )

hold + fill is the account's price P&L. hold + fill summed over names, plus the
session's fees, should equal Alpaca's end-of-day equity change. Every session's
residual (the EOD change minus that sum) is printed beside the value sold that session, and a
WARN line marks any residual above RESIDUAL_WARN_USD. nav_part is what the
holder would have made if the price had moved with the NAV (a constant
discount). disc_part is the rest: the discount's move. Long and short follow
from the sign of q_prev, so a short whose fund's NAV rises has a negative
nav_part.

FEES: PAPER CHARGES THEM AFTER ALL (review 2026-11-02)
------------------------------------------------------
The first build said paper "charges no fees" and called the residual a one-cent
difference between Alpaca's mark and the SIP close. Its own output said
otherwise. On the converted cache to 2026-10-30 the residual against hold + fill
was negative on 19 of 24 sessions, zero on the 5 with no fill, never positive,
-$6.16 in all, and it tracked the value sold: about $21.1 per $1M sold and
$0.7 per $1M bought, R2 0.9996 (a no-intercept fit over the 23 sessions after
2026-09-29) [V: the reviewer's script and the counts, re-run 2026-11-02]. A
mark difference has no sign and no tie to sales. This was a cash flow.

It is, to the cent, Alpaca's LIVE regulatory-fee schedule charged per session:
the SEC fee on the session's value sold (sells and short sales) at SEC_FEE_PER_
USD_SOLD, plus FINRA CAT on the session's shares traded (buys and sells) at
CAT_FEE_PER_SHARE, each summed over the session and rounded UP to the cent. That
rule reproduces the residual exactly on 24 of 24 sessions: analyse on that cache
now leaves a residual of exactly 0 (in Fraction) on every session [V: re-run
2026-11-02]. The rounding unit was found by search, in a scratchpad check: 3 x
3 x 4 x 3 x 2 variants were tried (per fill, order or session; up, half or
none; CAT on both sides or sells only). The next best matched 13 of 24. Alpaca's
paper page says paper does not simulate regulatory fees (docs/REFERENCES.md,
the paper-trading rows [V: page fetched 2026-10-13]). The page and the account disagree,
and this module follows the account.

CONFIRMED against the account's own record (2026-11-02): GET
/v2/account/activities/FEE lists 37 FEE activities over 2026-09-29..10-30, "REG
fee" (SEC) and "CAT fee" rows, summing to -$6.16; each REG row's "proceed" equals
the session's value sold computed here, and the per-session totals equal the
modelled fees on 34 of 34 sessions [V: read-only, by the main session with keys,
2026-11-02]. One trap for anyone re-checking: with `until=2026-10-31` the 10-30
rows were missing, so `until` appears to filter on posting time, not trade date;
the unbounded read has them. The model stays as the line (it needs only FILLs);
the FEE activities are its check.

So the fees line is modelled from the schedule and labelled as such. It is
reported per session and in total, never per name: it is rounded per session,
so it does not split exactly by name. fill + fees is paper's execution cost:
-$314.87 on that cache, against -$308.71 for fill alone [V: re-run 2026-11-02].
With the residual at 0, it now measures what the model misses: a missed fill, a wrong
sign, a mark difference, or a new SEC rate. A new rate shows as a residual in
proportion to the value sold, which is why daily.csv carries both.

The arithmetic is done in fractions.Fraction, on the decimal strings the sources
publish. nav_part + disc_part == hold therefore holds exactly, and so does each
session's reconciliation sum: no float rounding can hide a term. Floats appear
only in the written tables.

DISTRIBUTIONS: WHAT PAPER DOES NOT CREDIT
-----------------------------------------
Alpaca paper credits no distributions [V: docs.alpaca.markets/us/docs/
paper-trading, fetched 2026-09-28; CLAUDE.md landmine 1]. The account recorded
0 DIV activities over the window [V: main session, 2026-11-02]. On a CEF's
ex-date the price falls by about the distribution. A paper long loses that drop
with nothing credited back. A paper short gains it without paying its lender.
`dist` is therefore never part of the equity reconciliation. It is the third
line beside it (team lead 2026-10-09, `docs/SYSTEM.md` §5), and it follows both
halves of prod's rule (`quantt/session/dist_score.py`):

  * entitlement: the holder at the previous close is entitled on the ex-date. A
    long is credited, a short is charged, and shares traded on the ex-date
    trade ex and earn nothing;
  * resolution (review 2026-11-02): for a held name-day the amount comes from
    `dist_score.resolve` itself. It is called with Alpaca's records and a second
    source fetched into the cache, yfinance `Ticker.dividends` (the vendor of
    prod's panel, data/cef/cef_distributions.parquet). Alpaca's silence is not
    a zero. A zero needs both sources silent, with the second covering the name
    and fetched after the close of the session following the ex-date
    (`dist_score.panel_judgement`). Anything else is UNMEASURED: that name-day's
    dist is None, the line's total is UNMEASURED (a sum with a missing term is
    not the sum), and a GAP names each case.

The first build copied only the entitlement half. It counted any name-day that
Alpaca did not list as zero, so an ex-date late in the window, whose record
Alpaca had not published yet, would have made the line silently low. Prod's
third score booked +$320.85 on 10-13..10-15. The main session's independent
recompute holds the same +$320.85, which its script printed rounded as 321
[V: reviewer, 2026-11-02]. Cash dividends and capital-gains distributions both
count, as in `AlpacaClient.distributions` and dist_score. A cache that did not
query a kind says so in the summary as a GAP. The total is then labelled with
the kinds it covers.

EX-DATES AND THE DISCOUNT PART: A CONVENTION (review 2026-11-02)
----------------------------------------------------------------
On an ex-date, price and NAV both fall by about the distribution D. Write the
previous discount as d = 1 - close_p / NAV_p. If each falls by exactly D, then
hold = -q_prev * D and nav_part = -q_prev * D * close_p / NAV_p, so disc_part =
-q_prev * D * d. The dollar gap is unchanged, but the NAV under it is smaller,
so the discount is wider in percent. That mechanical widening lands in
disc_part: it counts against a long at a discount and for a short. It is not
the signal's discount bet. On the converted cache to 2026-10-30 it was -$61.28
on the long side (7 ex-date name-days) and +$63.16 on the short side (5), net
+$1.88, under the model that price and NAV each fall by exactly the
distribution. Neither leg's discount part changes sign (long +$1,031.36, short
+$552.12) [V: the reviewer's figures, re-run from name_day 2026-11-02]. The
module does not compute this split; it is a reading aid, not a line.
dist is the other half of the same event: a real account's ex-date P&L is
hold + dist.

THE NAV-ALIGNMENT CAVEAT
------------------------
yfinance serves stale vendor copies of some NAVs: a row dated D that carries
NAV(D-1) (results/cef/LIVE_NAV_QUALITY_2026-10-12.md; docs/REFERENCES.md §12h).
A stale copy moves P&L between nav_part and disc_part for those two days: the
NAV move is booked a day late, and disc_part absorbs the difference on both. It
never changes hold, fill or the reconciliation, which use only prices and fills.
A NAV split over a short window is therefore less certain than its sum; a split
over weeks, like the one above, mostly washes the lag out.

WHAT IT REFUSES (raises, naming what is missing; never a default)
-------------------------------------------------------------------
  * a missing close, where one is needed: a held name on t or p, or a traded
    name on t;
  * a missing NAV on a held name-day (t or p);
  * a fill on a day with no bar for its symbol, or on a day that is not a
    session of the EOD history;
  * duplicate FILL activity ids, which would count a fill twice;
  * a split, or any other share-count corporate action, naming a traded symbol
    in the window. Paper processes no corporate actions [V: docs/REFERENCES.md
    §12pc], so the account's share count would no longer match the price;
  * a cache that cannot show the account was flat when the rebuild starts
    (`check_flat_start`), or that did not query splits;
  * a fill on or before the first EOD point (it cannot be reconciled), a bar on
    a date the EOD history lacks, an ex-date that is not a session (in either
    distribution source), a traded symbol with no `grp` in
    data/cef/cef_universe.csv, and two identical distribution records under
    different ids (Alpaca once published a doubled QQQ record,
    scripts/rv/alpaca_daily.py);
  * a cache without the second distribution source, its fetch time, or the
    session after its last EOD point;
  * a write under data/, or of any file git could see in this repository.
No fillna on any price or NAV. A NAV or close that is present but not a finite
positive number counts as missing, and the error says so. A distribution that
cannot be resolved is UNMEASURED, never zero.

USAGE
-----
    python3 scripts/cef/live_attribution.py fetch   [--cache-dir D] [--asof YYYY-MM-DD] [--since YYYY-MM-DD]
    python3 scripts/cef/live_attribution.py analyse [--cache-dir D] [--out-dir D] [--asof YYYY-MM-DD]
                                                    [--break YYYY-MM-DD ...]

The cache holds the account's fills and equity series, and the analyse outputs
hold the same kind of data: daily.csv carries the account's EOD equity for every
session, and name_day.csv and positions_end.csv carry its positions. This
repository is public. Both default directories (results/cef/live_attribution/
_cache and _out) are gitignored, and both steps refuse to write any file that
git could see inside the repository (`_refuse_git_visible`, review 2026-11-02:
the first build's default --out-dir was visible). A directory outside the
repository is allowed. Whether any output may be committed is the team lead's
call; until then nothing can be.

C4 (team lead, 2026-11-09)
--------------------------
`--book c4` reads C4's paper account with the C4 keys (`ALPACA_C4_KEY_ID` / `_SECRET_KEY`),
and its group labels are the C4 spec's frozen `level_signal.family_of` (`load_groups_for`,
the five families), read at run time, never retyped. Every line (hold, fill, fees, NAV,
discount, distributions) and every refusal are the core's; so is the fee schedule, which
was measured on the cef account (FEES above). C4's own FEE activities are compared per
session in the nightly report (`scripts/ops/pnl_report.py`). The core's output does not
move: `analyse` on a cef cache is byte-identical before and after this change.

C4's NAV SYMBOLS ARE NOT THE CORE'S (review, 2026-11-09). The core's NAV rule is `X<TK>X`.
C4's is the committed map `results/cef/c4/c4_nav_symbols_2026-10-14.csv`, read by
`scripts/cef/fetch_daily.py` through `data_books.c4_nav_symbols`: 15 of its 74 funds use
another symbol (ADX XADEX, TY XTYCX, QQQX XQQQX and 12 more), and yfinance returned no
rows for the X-rule symbol of any of those 15 [V 2026-11-09]. Asking the X rule for them
made C4's NAV/discount split permanently UNMEASURED whenever one was held, under a
message that read like a late NAV. `nav_symbols` holds the rule per book, and a C4 name the
map lacks raises, naming it: the X rule is never tried as a stand-in.

THE FETCH PATH IS INJECTABLE, AND HOLDS NO BROKER CLIENT (team lead, 2026-11-09)
--------------------------------------------------------------------------------
`fetch(client=...)` takes the reader it reads through, and `book=` says which account.
The report job
(`scripts/ops/pnl_report.py`) passes `scripts/ops/alpaca_read.AlpacaReader`, built
from the key the VM's secret service put in the process environment
(`ALPACA_<BOOK>_KEY_ID` / `_SECRET_KEY`). The default for `python3 ... fetch` on a
research machine is that same reader: it reads those two variables from the
environment and never opens a key file (set them for the one command, for example
`set -a; . <key file>; set +a`). It is GET only and imports nothing from quantt/; so
this module's import closure holds no order code at all, even at function level, and
`scripts/ops/tests/test_report_no_order_path.py` pins that. (Until 2026-11-09 the
default went through `scripts/rv/alpaca_daily.make_client` -> `AlpacaClient`, whose
module holds `submit_order`; that one edge is why the two reads were split.)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import subprocess
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from functools import partial
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# Prod's distribution rules, reused rather than copied (module docstring). The
# module imports only the standard library; it holds no order code.
from quantt.session import dist_score as DS  # noqa: E402
# The GET-only reader the fetch path uses (module docstring, USAGE). It holds no order
# code and imports nothing from quantt/; scripts/ops/tests/test_report_no_order_path.py
# pins that nothing this module imports reaches the broker client.
from scripts.ops import alpaca_read as AR  # noqa: E402

NY = ZoneInfo("America/New_York")
BOOK = "cef"
BOOKS = ("cef", "c4")
C4_SPEC = REPO / "ops" / "specs" / "c4_families.frozen.json"
C4_GROUP_SOURCE = "ops/specs/c4_families.frozen.json level_signal.family_of"
C4_NAV_MAP = REPO / "results" / "cef" / "c4" / "c4_nav_symbols_2026-10-14.csv"
GROUP_SOURCE = {"cef": "data/cef/cef_universe.csv `grp`", "c4": C4_GROUP_SOURCE}
# Both gitignored (.gitignore); `_refuse_git_visible` enforces it at write time.
DEFAULT_CACHE = REPO / "results" / "cef" / "live_attribution" / "_cache"
DEFAULT_OUT = REPO / "results" / "cef" / "live_attribution" / "_out"
# Both books' caches and outputs are gitignored; C4's sit beside the core's (.gitignore).
DEFAULT_CACHE_C4 = REPO / "results" / "cef" / "live_attribution" / "_cache_c4"
DEFAULT_OUT_C4 = REPO / "results" / "cef" / "live_attribution" / "_out_c4"
UNIVERSE_CSV = REPO / "data" / "cef" / "cef_universe.csv"
DATA_DIR = REPO / "data"

# A session whose |EOD change - (hold + fill + fees)| exceeds this gets a WARN
# line. The first build justified $5 as several times a one-cent mark
# difference, which was the wrong explanation (FEES in the module docstring).
# With the fees modelled, the residual is 0.00 on all 24 sessions to 2026-10-30
# [V: analyse re-run, 2026-11-02]. $5 is then a missed fill or a wrong sign on
# any position of a few hundred dollars, and it is far above a fee-rate change
# at this book's size: at the SEC rate below, the whole SEC fee reaches $5 only
# on about $243k sold in one session [V: 5 / 0.0000206].
RESIDUAL_WARN_USD = 5.0

# Alpaca's regulatory fees (FEES in the module docstring). The rates are Alpaca's
# live schedule, revised 2026-10-01: docs/REFERENCES.md §12l [V], the same two
# numbers as scripts/cef/real_money_costs.py (a test pins them equal). FINRA's TAF
# is $0 a share there and was not charged on this account [V: the exact fit].
# Each is summed over the session and rounded UP to the cent.
SEC_FEE_PER_USD_SOLD = Fraction("0.0000206")     # sells and short sales
CAT_FEE_PER_SHARE = Fraction("0.000003")         # buys and sells

# Signed quantity per FILL side. A fill that opens or adds to a short says
# "sell_short" while its order says "sell" [V: measured 2026-09-30, 10-01;
# quantt/session/verify.py FILL_SIDE_ALIASES]. Any other side raises.
SIDE_SIGN = {"buy": 1, "sell": -1, "sell_short": -1}

SPLIT_TYPES = ("forward_split", "reverse_split", "unit_split")
DIST_KINDS = ("cash_dividend", "capital_gains_distribution")

# Query windows (fetch). Alpaca filters corporate actions on PROCESS date, which
# trails a dividend's ex-date by weeks (dist_score.QUERY_DAYS = 120) and a split's
# by up to 47 days, with rare backfills of years (docs/REFERENCES.md §12pc). The
# window is padded and every record is filtered here on its own market date.
DIST_QUERY_PAD_DAYS = 120
CA_QUERY_PAD_BEFORE_DAYS = 31
CA_QUERY_PAD_AFTER_DAYS = 120
# NAVs are fetched from this many days before the first session, so the first
# held day has a previous NAV even across a long weekend.
NAV_LOOKBACK_DAYS = 10
# An account funded before --since is shown flat by this many sessions of
# identical EOD equity before its first fill (flat_by_constant_equity). One week
# of closes: a held CEF position moves equity by at least a cent on nearly every
# close, so five unchanged closes are not a coincidence.
MIN_FLAT_SESSIONS = 5

FILES = {"manifest": "manifest.json", "fills": "fills.json", "eod": "eod.csv",
         "bars": "bars.csv", "dists": "distributions.json",
         "dists_check": "distributions_check.csv",
         "corp": "corporate_actions.json", "nav": "nav.csv"}
MONEY = ("hold", "fill", "nav_part", "disc_part", "dist", "traded_usd")
# Session-level columns: fees are rounded per session, so they have no per-name
# value; sold_usd and shares_traded are what the fees are charged on.
SESSION_MONEY = ("fees", "sold_usd", "shares_traded")
OUTPUT_TABLES = ("name_day", "daily", "by_name", "by_side", "by_grp", "by_grp_side",
                 "by_period", "by_period_grp", "dist_events", "positions_end")


class AttributionError(RuntimeError):
    """An input the attribution needs is missing or contradictory. Names it."""


# --------------------------------------------------------------- parsing

def _frac(v, what: str, *, positive: bool = False) -> Fraction:
    """A number as an exact Fraction of its decimal text, or raise naming it.

    A string is read as written ("4.12" -> 103/25). A float is read through
    str(float), its shortest round-trip decimal, so 10.75 stays 10.75 and a
    float32-rounded yfinance NAV stays the decimal the file holds. NaN, inf,
    None, booleans and junk raise; there is no default.
    """
    if v is None or isinstance(v, bool):
        raise AttributionError(f"{what}: {v!r} is not a number")
    if isinstance(v, int):
        x = Fraction(v)
    else:
        if isinstance(v, str):
            s = v.strip()
        else:
            try:
                f = float(v)
            except (TypeError, ValueError):
                raise AttributionError(f"{what}: {v!r} is not a number") from None
            if not math.isfinite(f):
                raise AttributionError(f"{what}: {v!r} is not finite")
            s = str(f)
        try:
            x = Fraction(s)
        except (ValueError, ZeroDivisionError):
            raise AttributionError(f"{what}: {v!r} is not a finite number") from None
    if positive and x <= 0:
        raise AttributionError(f"{what}: {v!r} is not a positive number")
    return x


def _date(v, what: str) -> dt.date:
    if isinstance(v, dt.datetime):
        raise AttributionError(f"{what}: {v!r} is a datetime, expected a date")
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v).strip())
    except ValueError:
        raise AttributionError(f"{what}: {v!r} is not YYYY-MM-DD") from None


@dataclass(frozen=True)
class Fill:
    id: str
    symbol: str
    date: dt.date          # New York date of transaction_time
    time: str              # transaction_time as Alpaca wrote it
    signed_qty: int        # buy > 0, sell / sell_short < 0
    price: Fraction


def parse_fills(raw: list) -> list[Fill]:
    """Alpaca FILL activity rows -> Fill, oldest first.

    Duplicate ids raise: activities are paged, and a page served twice (or a
    cache written from overlapping reads) would double a fill and every P&L line
    after it. Each partial fill is its own activity with its own `qty` (the
    increment), so `qty`, never `cum_qty`, is the quantity.
    """
    if not isinstance(raw, list):
        raise AttributionError(f"fills: expected a list of activities, got {type(raw).__name__}")
    ids = Counter(a.get("id") if isinstance(a, dict) else None for a in raw)
    dup = sorted(str(i) for i, n in ids.items() if n > 1)
    if dup:
        raise AttributionError(f"duplicate FILL activity ids (a fill would count twice): {dup[:5]}"
                               f"{' ...' if len(dup) > 5 else ''}")
    out = []
    for i, a in enumerate(raw):
        w = f"fill[{i}]"
        if not isinstance(a, dict):
            raise AttributionError(f"{w}: not an object")
        w = f"fill[{i}] id={a.get('id')!r}"
        for f in ("id", "activity_type", "symbol", "side", "qty", "price", "transaction_time"):
            if a.get(f) in (None, ""):
                raise AttributionError(f"{w}: field {f!r} is missing")
        if a["activity_type"] != "FILL":
            raise AttributionError(f"{w}: activity_type {a['activity_type']!r} is not FILL")
        if a["side"] not in SIDE_SIGN:
            raise AttributionError(f"{w}: side {a['side']!r} is not one of {sorted(SIDE_SIGN)}")
        qty = _frac(a["qty"], f"{w} qty", positive=True)
        if qty.denominator != 1:
            # Whole shares only: Alpaca cannot short fractions (CLAUDE.md landmine 3).
            raise AttributionError(f"{w}: qty {a['qty']!r} is not a whole number of shares")
        px = _frac(a["price"], f"{w} price", positive=True)
        ts = pd.Timestamp(a["transaction_time"])
        if ts.tzinfo is None:
            raise AttributionError(f"{w}: transaction_time {a['transaction_time']!r} has no offset")
        out.append(Fill(id=str(a["id"]), symbol=str(a["symbol"]),
                        date=ts.tz_convert(NY).date(), time=str(a["transaction_time"]),
                        signed_qty=SIDE_SIGN[a["side"]] * int(qty), price=px))
    return sorted(out, key=lambda f: (pd.Timestamp(f.time), f.id))


def parse_eod(rows) -> list[tuple[dt.date, Fraction]]:
    """[(session date in New York, equity)], strictly increasing dates.

    The dates are already New York session dates: `AlpacaClient.
    eod_equity_history` maps each 00:00 UTC stamp (the evening of its session in
    New York) to its session before the cache is written (docs/REFERENCES.md
    §12an). A zero or negative equity raises: the client drops the pre-funding
    zeros, so a zero here is not a session of this book.
    """
    out = []
    for i, r in enumerate(rows):
        d = _date(r[0], f"eod[{i}] date")
        eq = _frac(r[1], f"eod[{i}] equity on {d}", positive=True)
        out.append((d, eq))
    if not out:
        raise AttributionError("eod: the EOD history is empty")
    bad = [(a[0], b[0]) for a, b in zip(out, out[1:]) if b[0] <= a[0]]
    if bad:
        raise AttributionError(f"eod: dates not strictly increasing at {bad[:3]}")
    return out


def _value_map(frame: pd.DataFrame, col: str, what: str) -> tuple[dict, dict]:
    """{(ticker, date): Fraction} for rows whose `col` is a finite positive number,
    and {(ticker, date): raw} for rows that hold something else. Nothing is filled:
    a bad row is kept aside only so the error naming it can say what it held."""
    need = {"date", "ticker", col}
    if not need <= set(frame.columns):
        raise AttributionError(f"{what}: columns {sorted(need - set(frame.columns))} missing")
    good, bad = {}, {}
    seen = set()
    for t, d, v in zip(frame["ticker"], frame["date"], frame[col]):
        k = (str(t), _date(d, f"{what} {t}"))
        if k in seen:
            raise AttributionError(f"{what}: duplicate row for {k[0]} {k[1]}")
        seen.add(k)
        try:
            good[k] = _frac(v, f"{what} {k[0]} {k[1]}", positive=True)
        except AttributionError:
            bad[k] = v
    return good, bad


def parse_distributions(raw: list) -> list[dict]:
    """Distribution events -> [{id, symbol, ex_date, amount: Fraction, kind}].

    Duplicate ids raise. Two records alike in symbol, ex-date, amount and kind
    under different ids raise too: Alpaca published such a pair once (QQQ
    2022-09-19, scripts/rv/alpaca_daily.py), and summing it doubles the event.
    Distinct records on one ex-date (a regular plus a supplemental) are summed.
    """
    out, ids = [], Counter()
    for i, e in enumerate(raw):
        w = f"distribution[{i}]"
        for f in ("id", "symbol", "ex_date", "amount", "kind"):
            if not isinstance(e, dict) or e.get(f) in (None, ""):
                raise AttributionError(f"{w}: field {f!r} is missing")
        if e["kind"] not in DIST_KINDS:
            raise AttributionError(f"{w}: kind {e['kind']!r} is not one of {DIST_KINDS}")
        amt = _frac(e["amount"], f"{w} amount")
        if amt < 0:
            raise AttributionError(f"{w}: amount {e['amount']!r} is negative")
        ids[e["id"]] += 1
        out.append({"id": str(e["id"]), "symbol": str(e["symbol"]),
                    "ex_date": _date(e["ex_date"], f"{w} ex_date"), "amount": amt,
                    "kind": e["kind"]})
    dup = sorted(i for i, n in ids.items() if n > 1)
    if dup:
        raise AttributionError(f"duplicate distribution ids: {dup[:5]}")
    same = Counter((e["symbol"], e["ex_date"], e["amount"], e["kind"]) for e in out)
    twins = sorted((s, d.isoformat(), float(a), k) for (s, d, a, k), n in same.items() if n > 1)
    if twins:
        raise AttributionError(f"identical distribution records under different ids (would "
                               f"double-count; a human decides): {twins[:5]}")
    return out


def parse_dist_check(frame: pd.DataFrame) -> list[tuple[str, dt.date, Fraction]]:
    """The second distribution source's rows -> [(ticker, ex_date, amount)].

    Each row is one yfinance dividend. A name with no row is a name the source
    does not cover, and `dist_score.resolve` treats that as one silent source,
    not two. A row that is not a finite, non-negative amount raises: dropping it
    would make the name look silent on that day.
    """
    need = {"ticker", "ex_date", "amount"}
    if not need <= set(frame.columns):
        raise AttributionError(f"distributions_check: columns {sorted(need - set(frame.columns))} missing")
    out = []
    for i, (t, d, a) in enumerate(zip(frame["ticker"], frame["ex_date"], frame["amount"])):
        w = f"distributions_check[{i}] {t}"
        if t in (None, "") or (isinstance(t, float) and math.isnan(t)):
            raise AttributionError(f"distributions_check[{i}]: ticker is missing")
        amt = _frac(a, f"{w} amount")
        if amt < 0:
            raise AttributionError(f"{w}: amount {a!r} is negative")
        out.append((str(t), _date(d, f"{w} ex_date"), amt))
    return out


def parse_corp_actions(raw: list) -> list[dict]:
    """Non-dividend corporate actions -> [{id, type, date, parties: [(sym, role)]}],
    as `AlpacaClient.corporate_actions` returns them."""
    out = []
    for i, e in enumerate(raw):
        w = f"corporate_action[{i}]"
        for f in ("id", "type", "date", "parties"):
            if not isinstance(e, dict) or e.get(f) in (None, ""):
                raise AttributionError(f"{w}: field {f!r} is missing")
        parties = [(str(p[0]), str(p[1])) for p in e["parties"]]
        out.append({"id": str(e["id"]), "type": str(e["type"]),
                    "date": _date(e["date"], f"{w} date"), "parties": parties})
    return out


# --------------------------------------------------------------- inputs

@dataclass
class Inputs:
    """Everything `attribute` reads, already parsed. `load_cache` builds it from a
    cache directory; the tests build it directly."""
    fills: list
    eod: list
    closes: dict
    navs: dict
    dists: list
    corp: list
    grp: dict
    flat_start: dt.date               # the account held nothing at the start of this session
    fills_from: dt.date               # the fills in the cache cover every day from here
    corp_types: tuple = ()            # corporate-action types the cache's source was asked for
    dist_kinds: tuple = DIST_KINDS    # distribution kinds the cache's source was asked for
    # The second distribution source (parse_dist_check rows), when it was fetched
    # (tz-aware), and the session after the last EOD point. None means absent:
    # dist_score then cannot call any silence a zero, so it is UNMEASURED.
    dist_check: list | None = None
    dist_check_at: dt.datetime | None = None
    next_session: dt.date | None = None
    bad_closes: dict = field(default_factory=dict)
    bad_navs: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    cache_dir: str = ""
    book: str = "cef"


def load_grp(path: Path = UNIVERSE_CSV) -> dict:
    """{ticker: grp} from data/cef/cef_universe.csv (read only). Duplicates raise."""
    u = pd.read_csv(path, dtype=str)
    if not {"ticker", "grp"} <= set(u.columns):
        raise AttributionError(f"{path}: needs columns ticker and grp")
    dup = sorted(u.loc[u["ticker"].duplicated(), "ticker"])
    if dup:
        raise AttributionError(f"{path}: duplicate tickers {dup}")
    if u["grp"].isna().any():
        raise AttributionError(f"{path}: empty grp for {sorted(u.loc[u['grp'].isna(), 'ticker'])}")
    return dict(zip(u["ticker"], u["grp"]))


def load_groups_for(book: str) -> dict:
    """The group labels of `book`: the cef universe table, or C4's frozen family map
    (`frozen.level_signal.family_of`, read from the spec at run time). Raises naming a
    missing file or key; a default would mislabel a whole sleeve in silence."""
    if book == "cef":
        return load_grp()
    if book != "c4":
        raise AttributionError(f"unknown book {book!r} (books: {BOOKS})")
    if not C4_SPEC.is_file():
        raise AttributionError(f"C4's frozen spec is missing at {C4_SPEC}")
    frozen = json.loads(C4_SPEC.read_text()).get("frozen") or {}
    fam = (frozen.get("level_signal") or {}).get("family_of")
    if not isinstance(fam, dict) or not fam:
        raise AttributionError(f"{C4_SPEC}: frozen.level_signal.family_of is missing or empty")
    return dict(fam)


def c4_nav_symbols(path: Path | None = None) -> dict:
    """{ticker: yfinance NAV symbol} for C4's frozen universe, from the committed map.

    A COPY OF `scripts/cef/data_books.c4_nav_symbols`, and a test holds the two equal. It
    cannot be imported: data_books's function-level imports reach `scripts.cef.fetch_daily`
    and through it `requests`, which the report job's import closure forbids
    (`scripts/ops/tests/test_report_no_order_path.py`). Refuses the same maps data_books does,
    so that a bad map fails here and not as a silent NAV gap: a repeated ticker, an empty
    symbol, the price ticker as its own symbol (a price is not a NAV), two funds on one
    symbol, or a universe that is not exactly the spec's."""
    p = C4_NAV_MAP if path is None else Path(path)
    if not p.is_file():
        raise AttributionError(f"C4's NAV-symbol map is missing at {p}")
    t = pd.read_csv(p, dtype=str, keep_default_na=False)
    missing = {"ticker", "nav_symbol"} - set(t.columns)
    if missing:
        raise AttributionError(f"{p.name}: needs columns ticker and nav_symbol; {sorted(missing)} absent")
    out: dict = {}
    for tk, sym in zip(t["ticker"].str.strip(), t["nav_symbol"].str.strip()):
        if tk in out:
            raise AttributionError(f"{p.name}: {tk} is listed twice")
        if not sym or sym == tk:
            raise AttributionError(f"{p.name}: {tk}'s NAV symbol {sym!r} is empty or is the price ticker")
        out[tk] = sym
    uni = set(load_groups_for("c4"))
    if set(out) != uni:
        raise AttributionError(f"{p.name} does not cover C4's frozen universe: missing {sorted(uni - set(out))}, "
                               f"extra {sorted(set(out) - uni)}")
    dup = sorted({s for s in out.values() if list(out.values()).count(s) > 1})
    if dup:
        raise AttributionError(f"{p.name}: NAV symbol(s) {dup} are named for more than one fund")
    return out


def nav_symbols(book: str, tickers) -> dict:
    """{price ticker: the yfinance symbol of its NAV} for `tickers`, by the rule of `book`
    (module docstring, C4). A C4 name the map lacks raises, naming it: the core's X rule
    returns no rows for 15 of C4's funds, so it is never used as a stand-in."""
    tks = sorted(set(tickers))
    if book == "cef":
        return {tk: f"X{tk}X" for tk in tks}
    if book != "c4":
        raise AttributionError(f"unknown book {book!r} (books: {BOOKS})")
    mapped = c4_nav_symbols()
    absent = [tk for tk in tks if tk not in mapped]
    if absent:
        raise AttributionError(f"{C4_NAV_MAP.name} has no NAV symbol for {absent}: these are not C4's frozen "
                               f"names, so their NAV source is unknown")
    return {tk: mapped[tk] for tk in tks}


def load_cache(cache_dir: Path, grp: dict | None = None) -> Inputs:
    """Read a cache written by `fetch` (or by an equivalent converter) -> Inputs."""
    cache_dir = Path(cache_dir)
    missing = [f for f in FILES.values() if not (cache_dir / f).is_file()]
    if missing:
        raise AttributionError(f"cache {cache_dir}: files missing {missing}")
    man = json.loads((cache_dir / FILES["manifest"]).read_text())
    for k in ("flat_start", "fills", "eod", "corporate_actions", "distributions",
              "distributions_check"):
        if k not in man:
            raise AttributionError(f"cache manifest: section {k!r} is missing")
    fs = man["flat_start"]
    if not isinstance(fs, dict) or not fs.get("date") or not fs.get("evidence"):
        raise AttributionError("cache manifest: flat_start needs a date and the evidence for it")
    if not man["fills"].get("requested_start"):
        raise AttributionError("cache manifest: fills.requested_start is missing")
    if not man["eod"].get("next_session"):
        raise AttributionError("cache manifest: eod.next_session (the session after the last EOD "
                               "point) is missing; without it no zero can be shown on that point")
    at_raw = man["distributions_check"].get("fetched_at_utc")
    try:
        check_at = dt.datetime.fromisoformat(str(at_raw))
    except ValueError:
        raise AttributionError(f"cache manifest: distributions_check.fetched_at_utc {at_raw!r} is "
                               "not an ISO time") from None
    if check_at.tzinfo is None:
        raise AttributionError(f"cache manifest: distributions_check.fetched_at_utc {at_raw!r} "
                               "has no offset")
    check = pd.read_csv(cache_dir / FILES["dists_check"], dtype=str, keep_default_na=False)
    eod = pd.read_csv(cache_dir / FILES["eod"], dtype=str)
    if not {"date", "equity"} <= set(eod.columns):
        raise AttributionError("eod.csv: needs columns date and equity")
    bars = pd.read_csv(cache_dir / FILES["bars"], dtype=str, keep_default_na=False)
    nav = pd.read_csv(cache_dir / FILES["nav"], dtype=str, keep_default_na=False)
    closes, bad_closes = _value_map(bars, "close", "bars")
    navs, bad_navs = _value_map(nav, "nav", "nav")
    book = str(man.get("book") or BOOK)
    return Inputs(
        fills=parse_fills(json.loads((cache_dir / FILES["fills"]).read_text())),
        eod=parse_eod(list(zip(eod["date"], eod["equity"]))),
        closes=closes, bad_closes=bad_closes, navs=navs, bad_navs=bad_navs,
        dists=parse_distributions(json.loads((cache_dir / FILES["dists"]).read_text())),
        corp=parse_corp_actions(json.loads((cache_dir / FILES["corp"]).read_text())),
        grp=load_groups_for(book) if grp is None else grp,
        flat_start=_date(fs["date"], "manifest flat_start.date"),
        fills_from=_date(man["fills"]["requested_start"], "manifest fills.requested_start"),
        corp_types=tuple(man["corporate_actions"].get("types") or ()),
        dist_kinds=tuple(man["distributions"].get("kinds") or ()),
        dist_check=parse_dist_check(check), dist_check_at=check_at,
        next_session=_date(man["eod"]["next_session"], "manifest eod.next_session"),
        sources=man, cache_dir=str(cache_dir), book=book)


# --------------------------------------------------------------- the attribution

@dataclass
class Result:
    name_day: pd.DataFrame      # one row per (session, name) held or traded; money cols are Fraction
    daily: pd.DataFrame         # one row per session; money cols are Fraction
    events: pd.DataFrame        # distribution events in the window, with q_prev and dist
    positions_end: pd.DataFrame
    periods: list               # [(label, first, last)]
    period_rule: str
    gaps: list                  # stated gaps, printed and written
    excluded_after_asof: int
    asof: dt.date
    first_session: dt.date
    sources: dict
    dist_kinds: tuple = ()      # the distribution kinds the cache's source was asked for
    dist_unmeasured: list = field(default_factory=list)   # [(date, symbol, q_prev, reason)]
    book: str = "cef"
    nav_unmeasured: list = field(default_factory=list)    # [(date, symbol, missing)] nav_missing="unmeasured"


def _ceil_cent(x: Fraction) -> Fraction:
    return Fraction(math.ceil(x * 100), 100)


def session_fees(fills) -> tuple[Fraction, Fraction, int]:
    """(fees, value sold, shares traded) for one session's fills (FEES in the
    module docstring). fees is negative, a charge: the SEC fee on the value sold
    (sell and sell_short) plus CAT on every share traded, each summed over the
    session and then rounded up to the cent."""
    sold = sum((abs(f.signed_qty) * f.price for f in fills if f.signed_qty < 0), Fraction(0))
    shares = sum(abs(f.signed_qty) for f in fills)
    fees = -(_ceil_cent(SEC_FEE_PER_USD_SOLD * sold) + _ceil_cent(CAT_FEE_PER_SHARE * shares))
    return fees, sold, shares


def check_flat_start(inp: Inputs, s0: dt.date) -> None:
    """The rebuild starts from no position. Raise unless the cache shows that.

    It needs three facts. The account held nothing at the start of `flat_start`
    (the manifest names the evidence: Alpaca reported no funded equity on an
    earlier session). The fills cover every day from `fills_from`, which is no
    later than `flat_start`. And `flat_start` is no later than the first EOD point
    s0. A fill dated before `flat_start` contradicts the evidence, and raises.
    """
    if not inp.fills_from <= inp.flat_start <= s0:
        raise AttributionError(
            f"cannot assert a flat start: need fills_from {inp.fills_from} <= flat_start "
            f"{inp.flat_start} <= first EOD point {s0}. Fetch with an earlier --since")
    early = [f for f in inp.fills if f.date < inp.flat_start]
    if early:
        raise AttributionError(
            f"{len(early)} fill(s) before flat_start {inp.flat_start} (first: {early[0].symbol} "
            f"{early[0].date}): the account was not flat where the rebuild starts")


def flat_by_constant_equity(points, fills, since: dt.date) -> dict:
    """The flat-start evidence for an account funded before --since.

    WHY. The first build showed a flat start only by an unfunded session before
    the first EOD point. The cef paper account was funded with $100,000 months
    before its first fill [V: EOD history read 2026-11-02, flat from 2026-05-04
    at the latest], so no --since could satisfy that rule and `fetch` never ran.
    For such an account the evidence is that equity did not move: Alpaca marks
    every held position at each close, so an account whose equity is identical
    to the cent on every one of at least MIN_FLAT_SESSIONS sessions before its
    first fill (and with no fill from --since until then) held nothing. Raises,
    naming why, otherwise; a moved equity may mean a position from before
    --since, which only an earlier --since can show or rule out.
    """
    first_fill = min(f.date for f in fills)
    pre = [(d, e) for d, e, _ in points if d < first_fill]
    if len(pre) < MIN_FLAT_SESSIONS:
        raise AttributionError(
            f"the account was already funded at --since {since}, and only {len(pre)} EOD point(s) "
            f"precede its first fill ({first_fill}); {MIN_FLAT_SESSIONS} sessions of unchanged "
            f"equity are needed to show it flat; pass an earlier --since")
    moved = sorted({e for _, e in pre})
    if len(moved) != 1:
        raise AttributionError(
            f"equity moved before the first fill ({first_fill}): {len(moved)} distinct values on "
            f"{pre[0][0]}..{pre[-1][0]}, so a position from before --since {since} cannot be ruled "
            f"out; pass an earlier --since")
    return {"date": pre[0][0].isoformat(),
            "evidence": (f"the account was funded before --since {since}; its EOD equity is "
                         f"unchanged at {moved[0]:,.2f} on all {len(pre)} sessions from {pre[0][0]} "
                         f"to {pre[-1][0]}, and no FILL activity exists from {since} until the "
                         f"first fill on {first_fill}. Alpaca marks held positions at each close, "
                         f"so the account held nothing at the start of {pre[0][0]}")}


def default_breaks(eod: list, sessions: list) -> tuple[list, str]:
    """Split the window after the EOD equity peak, measured now from the cache
    (CLAUDE.md H14: no rule keys on a date written in a document)."""
    eq = dict(eod)
    peak = max(sessions, key=lambda d: (eq[d], -d.toordinal()))   # first day of the highest equity
    i = sessions.index(peak)
    if i == 0 or i == len(sessions) - 1:
        return [], (f"one period: the EOD equity peak ({peak}) is the "
                    f"{'first' if i == 0 else 'last'} session")
    return [sessions[i + 1]], f"split after the EOD equity peak on {peak} (equity {float(eq[peak]):,.2f})"


def attribute(inp: Inputs, asof: dt.date | None = None, breaks: list | None = None,
              nav_missing: str = "raise") -> Result:
    """The decomposition in the module docstring, for every session after the first
    EOD point up to `asof` (default: the last EOD point). Raises on any gap, except that
    with `nav_missing="unmeasured"` (the report job only, whose 20:30 run can precede a
    fund's NAV for the day) a held name-day with no NAV has nav_part and disc_part None,
    named in `Result.nav_unmeasured`; hold, fill, fees and the reconciliation need no NAV
    and stay complete, and any sum over a missing term is UNMEASURED, never a smaller sum."""
    if nav_missing not in ("raise", "unmeasured"):
        raise AttributionError(f"nav_missing must be 'raise' or 'unmeasured', got {nav_missing!r}")
    sessions_all = [d for d, _ in inp.eod]
    eq = dict(inp.eod)
    s0 = sessions_all[0]
    asof = sessions_all[-1] if asof is None else asof
    if asof not in eq:
        raise AttributionError(f"asof {asof} is not a session of the EOD history "
                               f"({sessions_all[0]}..{sessions_all[-1]})")
    sessions = [d for d in sessions_all if d <= asof]
    if len(sessions) < 2:
        raise AttributionError(f"nothing to attribute: the EOD history has no session after {s0}")
    window = sessions[1:]
    in_window = set(window)
    check_flat_start(inp, s0)

    missing_split = [t for t in SPLIT_TYPES if t not in inp.corp_types]
    if missing_split:
        raise AttributionError(
            f"the cache's corporate-action source was not asked for {missing_split}: it cannot show "
            f"that no split hit a held name, and paper would not have processed one")
    if "cash_dividend" not in inp.dist_kinds:
        raise AttributionError("the cache's distribution source did not query cash dividends")

    used = [f for f in inp.fills if f.date <= asof]
    later = len(inp.fills) - len(used)
    at_start = [f for f in used if f.date <= s0]
    if at_start:
        raise AttributionError(
            f"{len(at_start)} fill(s) on or before the first EOD point {s0} (first: {at_start[0].symbol} "
            f"{at_start[0].date}): no earlier equity exists to reconcile them against")
    off = sorted({(f.symbol, f.date) for f in used if f.date not in in_window})
    if off:
        raise AttributionError(f"fill(s) on a day that is not a session of the EOD history: {off[:5]}")
    for f in used:
        if (f.symbol, f.date) not in inp.closes:
            held = inp.bad_closes.get((f.symbol, f.date), "no row")
            raise AttributionError(f"fill {f.id} in {f.symbol} on {f.date}: no bar for that day "
                                   f"(bars hold {held!r})")
    symbols = sorted({f.symbol for f in used})
    no_grp = [s for s in symbols if s not in inp.grp]
    if no_grp:
        raise AttributionError(f"traded symbol(s) {no_grp} have no grp in the universe table")

    # A bar on a date inside the window that the EOD history lacks means a
    # session is missing from the history: hold would then span two days while
    # the equity change spans one, and the reconciliation would mislead.
    stray = sorted({d for (s, d) in list(inp.closes) + list(inp.bad_closes)
                    if s in symbols and s0 < d <= asof and d not in in_window})
    if stray:
        raise AttributionError(f"bars dated {stray[:5]} fall on no session of the EOD history")

    # Paper processes no corporate actions (docs/REFERENCES.md §12pc), so a split,
    # merger or name change in a traded symbol leaves the account's share count on
    # the old basis while the price moves to the new one. Nothing here can rebase it.
    hits = [e for e in inp.corp if s0 <= e["date"] <= asof
            and any(p in symbols for p, _ in e["parties"])]
    if hits:
        raise AttributionError(
            "share-count corporate action(s) in the window on a traded symbol: "
            + "; ".join(f"{e['type']} {e['date']} {[p for p, _ in e['parties']]} (id {e['id']})"
                        for e in hits[:5]))

    ev = defaultdict(list)
    for e in inp.dists:
        if e["symbol"] in symbols and s0 < e["ex_date"] <= asof:
            if e["ex_date"] not in in_window:
                raise AttributionError(f"{e['kind']} {e['symbol']} ex {e['ex_date']} (id {e['id']}) "
                                       f"is not a session of the EOD history")
            ev[(e["symbol"], e["ex_date"])].append(e)

    # The second distribution source, in the frame dist_score.resolve reads (its
    # `panel`). Every row of a traded name is kept, because "the source has rows for
    # the name" is half of the rule that lets both silences be a zero. An ex-date
    # in the window that is not a session raises, as Alpaca's does above.
    check = None
    if inp.dist_check is not None:
        for t, d, _ in inp.dist_check:
            if t in symbols and s0 < d <= asof and d not in in_window:
                raise AttributionError(f"second distribution source: {t} ex {d} is not a session "
                                       f"of the EOD history")
        rows_c = [(t, d, float(a)) for t, d, a in inp.dist_check if t in symbols]
        check = pd.DataFrame(rows_c, columns=["ticker", "ex_date", "amount"])
    check_last = max((d for _, d, _ in inp.dist_check), default=None) if inp.dist_check else None

    def following(d):
        """The session after d: the next EOD point, or the manifest's next_session
        after the last one. None if the cache cannot say."""
        j = sessions_all.index(d)
        return sessions_all[j + 1] if j + 1 < len(sessions_all) else inp.next_session

    def resolve_day(d, held: dict) -> tuple[dict, dict, dict]:
        """({symbol: Fraction per share}, {symbol: reason UNMEASURED}, {symbol:
        resolve's note}) for the names held into d, by prod's own rules
        (dist_score.resolve). In resolve's notes "the panel" is the second source."""
        nxt = following(d)
        if inp.dist_check is None or inp.dist_check_at is None:
            current, note = False, "the cache holds no second distribution source"
        elif nxt is None:
            current, note = False, f"the session after {d} is not in the cache"
        else:
            current, note = DS.panel_judgement(d, inp.dist_check_at, check_last, nxt)
            note = f"second source (yfinance dividends): {note}"
        alp = [e for s in held for e in ev.get((s, d), [])]
        per_share, gaps_d, notes_d, _ = DS.resolve(sorted(held), d, alp, check,
                                                    panel_current=current, panel_note=note)
        amounts, unmeasured = {}, {}
        for s in held:
            if s in gaps_d:
                unmeasured[s] = gaps_d[s]
            elif ev.get((s, d)):
                # Alpaca's amount, exactly: resolve returns it as a float sum.
                amounts[s] = sum((e["amount"] for e in ev[(s, d)]), Fraction(0))
            elif per_share.get(s) == 0.0:
                amounts[s] = Fraction(0)        # both sources silent, the second current
            else:
                raise AttributionError(f"{s} ex {d}: dist_score.resolve returned {per_share.get(s)!r} "
                                       "with no Alpaca record (a rule this module does not know)")
        return amounts, unmeasured, notes_d

    if breaks is None:
        brk, rule = default_breaks(inp.eod, sessions)
    else:
        brk = sorted(set(breaks))
        bad =[b for b in brk if b not in in_window or b == window[0]]
        if bad:
            raise AttributionError(f"--break {bad}: a break must be a session after the first one "
                                   f"in {window[0]}..{asof}")
        rule = f"split at the requested break(s) {[b.isoformat() for b in brk]}"
    bounds = [window[0]] + brk
    periods = []
    for j, start in enumerate(bounds):
        days = [d for d in window if start <= d and (j + 1 == len(bounds) or d < bounds[j + 1])]
        periods.append((f"{days[0]}..{days[-1]}", days[0], days[-1]))

    def period_of(d):
        return periods[bisect_right(bounds, d) - 1][0]

    def need(table, bad, s, d, what, why):
        if (s, d) in table:
            return table[(s, d)]
        held = bad.get((s, d))
        raise AttributionError(f"missing {what} for {s} on {d} ({why}); the cache holds "
                               f"{'no row' if held is None else repr(held)}. Nothing is filled")

    by_day = defaultdict(list)
    for f in used:
        by_day[f.date].append(f)
    q: dict = defaultdict(int)          # the flat start, asserted in check_flat_start
    nav_gaps: list = []                 # (date, symbol, what is missing), nav_missing="unmeasured"
    q_prev_at: dict = {}
    dist_status: dict = {}              # (symbol, date) -> how its dist was resolved
    unmeasured_all = []
    rows = []
    zero = Fraction(0)
    for i, d in enumerate(sessions[1:], start=1):
        p = sessions[i - 1]
        day = by_day.get(d, [])
        names = sorted({s for s, x in q.items() if x} | {f.symbol for f in day})
        # Entitlement (dist_score.py): the holder at p's close, q_prev, gets the
        # distribution with ex-date d. Resolution: dist_score.resolve, for exactly
        # the names held into d (module docstring, DISTRIBUTIONS).
        held = {s: q[s] for s in names if q[s]}
        amounts, unmeasured, notes = resolve_day(d, held) if held else ({}, {}, {})
        for s, why in sorted(unmeasured.items()):
            unmeasured_all.append((d, s, held[s], why))
        for s in names:
            qp = q[s]
            q_prev_at[(s, d)] = qp
            fs = [f for f in day if f.symbol == s]
            c_t = need(inp.closes, inp.bad_closes, s, d, "close", "held or traded")
            if qp:
                c_p = need(inp.closes, inp.bad_closes, s, p, "close", f"held into {d}")
                if nav_missing == "raise":
                    n_t = need(inp.navs, inp.bad_navs, s, d, "NAV", "held")
                    n_p = need(inp.navs, inp.bad_navs, s, p, "NAV", f"held into {d}")
                else:
                    n_t = inp.navs.get((s, d))
                    n_p = inp.navs.get((s, p))
                hold = qp * (c_t - c_p)
                if n_t is None or n_p is None:
                    nav_part = None              # unmeasured, named in the report below
                else:
                    nav_part = qp * c_p * (n_t / n_p - 1)
            else:
                c_p = n_t = n_p = None
                hold = nav_part = zero
            if nav_part is None:
                disc = None
                missing = [x for x, v in (("NAV on " + str(d), n_t), ("NAV on " + str(p), n_p)) if v is None]
                nav_gaps.append((d, s, " and ".join(missing)))
            else:
                disc = hold - nav_part
                if nav_part + disc != hold:      # exact in Fraction; a float here would be a bug
                    raise AttributionError(f"{s} {d}: nav_part + disc_part != hold")
            fill = sum((f.signed_qty * (c_t - f.price) for f in fs), zero)
            traded = sum((abs(f.signed_qty) * f.price for f in fs), zero)
            if not qp:
                dist, status = zero, "not held at the previous close: not entitled"
            elif s in unmeasured:
                dist, status = None, f"UNMEASURED: {unmeasured[s]}"
            else:
                dist = qp * amounts[s]
                status = (f"Alpaca's record: {notes[s]}" if ev.get((s, d)) else
                          "none: both sources silent, the second current and covering the name")
            dist_status[(s, d)] = status
            q_end = qp + sum(f.signed_qty for f in fs)
            side = ("long" if qp > 0 else "short" if qp < 0 else
                    "long" if q_end > 0 else "short" if q_end < 0 else "flat")
            rows.append({"date": d, "prev_date": p, "period": period_of(d), "symbol": s,
                         "grp": inp.grp[s], "side": side, "q_prev": qp, "q_end": q_end,
                         "n_fills": len(fs), "close_prev": c_p, "close": c_t,
                         "nav_prev": n_p, "nav": n_t, "hold": hold, "fill": fill,
                         "nav_part": nav_part, "disc_part": disc, "dist": dist,
                         "traded_usd": traded, "dist_status": status})
            q[s] = q_end
    nd = pd.DataFrame(rows, columns=["date", "prev_date", "period", "symbol", "grp", "side",
                                     "q_prev", "q_end", "n_fills", "close_prev", "close",
                                     "nav_prev", "nav", *MONEY, "dist_status"])

    daily = []
    for i, d in enumerate(sessions[1:], start=1):
        p = sessions[i - 1]
        sub = nd[nd["date"] == d]
        sums = {k: (None if any(x is None for x in sub[k]) else sum(sub[k], zero))
                for k in MONEY if k != "dist"}
        # A sum with a missing term is not the sum (dist_score, score.py).
        sums["dist"] = None if any(x is None for x in sub["dist"]) else sum(sub["dist"], zero)
        fees, sold, shares = session_fees(by_day.get(d, []))
        rebuilt = sums["hold"] + sums["fill"] + fees
        change = eq[d] - eq[p]
        daily.append({"date": d, "period": period_of(d), **{k: sums[k] for k in MONEY},
                      "fees": fees, "sold_usd": sold, "shares_traded": shares,
                      "rebuilt": rebuilt, "eod_equity": eq[d], "eod_change": change,
                      "residual": change - rebuilt})
    daily = pd.DataFrame(daily)

    evrows = []
    for (s, d), es in sorted(ev.items()):
        for e in es:
            qp = q_prev_at.get((s, d), 0)
            st = dist_status.get((s, d), "not held at the previous close: not entitled")
            evrows.append({"symbol": s, "ex_date": d, "kind": e["kind"], "amount": e["amount"],
                           "id": e["id"], "q_prev": qp,
                           "dist": None if st.startswith("UNMEASURED") else qp * e["amount"],
                           "dist_status": st})
    events = pd.DataFrame(evrows, columns=["symbol", "ex_date", "kind", "amount", "id", "q_prev",
                                           "dist", "dist_status"])

    pos = [{"symbol": s, "grp": inp.grp[s], "qty": x, "close": inp.closes.get((s, asof)),
            "market_value": None if (s, asof) not in inp.closes else x * inp.closes[(s, asof)]}
           for s, x in sorted(q.items()) if x]
    positions_end = pd.DataFrame(pos, columns=["symbol", "grp", "qty", "close", "market_value"])

    gaps = []
    if nav_gaps:
        gaps.append(f"the NAV/discount split is UNMEASURED on {len(nav_gaps)} held name-day(s): "
                    + ", ".join(f"{s} {d} ({w})" for d, s, w in nav_gaps[:10])
                    + (" ..." if len(nav_gaps) > 10 else ""))
    if "capital_gains_distribution" not in inp.dist_kinds:
        gaps.append("capital-gains distributions were NOT queried by the cache's source: the "
                    "distribution line covers cash dividends only")
    if unmeasured_all:
        gaps.append(f"the distribution line is UNMEASURED: {len(unmeasured_all)} held name-day(s) "
                    "could not be resolved (name_day.csv dist_status names each)")
        gaps += [f"distribution UNMEASURED: {s} ex {d}, {qp} share(s) held at the previous close: {why}"
                 for d, s, qp, why in unmeasured_all[:10]]
        if len(unmeasured_all) > 10:
            gaps.append(f"... and {len(unmeasured_all) - 10} more UNMEASURED name-day(s)")
    return Result(name_day=nd, daily=daily, events=events, positions_end=positions_end,
                  periods=periods, period_rule=rule, gaps=gaps, excluded_after_asof=later,
                  asof=asof, first_session=window[0], sources=inp.sources,
                  dist_kinds=tuple(inp.dist_kinds), dist_unmeasured=unmeasured_all,
                  book=inp.book, nav_unmeasured=nav_gaps)


# --------------------------------------------------------------- reporting

def _float_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if out[c].map(lambda v: isinstance(v, Fraction)).any():
            out[c] = out[c].map(lambda v: None if v is None else float(v))
    return out


def _sum_or_unmeasured(x: pd.Series) -> float:
    """The sum, or NaN (printed UNMEASURED) if any term is missing. pandas' own
    sum skips NaN, which would turn an UNMEASURED distribution into a zero."""
    return float(sum(x)) if x.notna().all() else float("nan")


def group_table(nd: pd.DataFrame, keys) -> pd.DataFrame:
    """Money columns summed by `keys`, plus price P&L (hold + fill), the
    distribution-adjusted total, and the fill in bp of traded notional. The
    session-level fees are not here: they have no per-name value."""
    f = _float_frame(nd[list(keys) + list(MONEY)])
    plain = [k for k in MONEY if k != "dist"]
    g = f.groupby(list(keys), sort=True)[plain].sum()
    g["dist"] = f.groupby(list(keys), sort=True)["dist"].agg(_sum_or_unmeasured)
    g = g[list(MONEY)]
    g["price_pnl"] = g["hold"] + g["fill"]
    g["with_dist"] = g["price_pnl"] + g["dist"]           # NaN stays NaN: UNMEASURED
    g["fill_bp_of_traded"] = (g["fill"] / g["traded_usd"] * 1e4).where(g["traded_usd"] > 0)
    return g.reset_index()


def reconcile_lines(daily: pd.DataFrame) -> list[str]:
    lines = []
    for r in daily.itertuples():
        res = float(r.residual)
        lines.append(f"  {r.date}  eod_change {float(r.eod_change):>10,.2f}  hold+fill+fees "
                     f"{float(r.rebuilt):>10,.2f}  (fees {float(r.fees):>6,.2f} on "
                     f"{float(r.sold_usd):>10,.2f} sold)  residual {res:>8,.2f}")
        if abs(res) > RESIDUAL_WARN_USD:
            lines.append(f"WARN {r.date}: |residual| {abs(res):,.2f} > {RESIDUAL_WARN_USD:.2f} USD: "
                         f"the rebuilt book (prices, fills and the modelled fees) and Alpaca's "
                         f"equity disagree on this session ({float(r.sold_usd):,.2f} sold)")
    return lines


def totals(res: Result) -> dict:
    """Window totals as floats. dist and with_dist are None when any session's
    distribution is UNMEASURED: a sum with a missing term is not the sum."""
    d = res.daily
    t = {k: (None if any(x is None for x in d[k]) else float(sum(d[k], Fraction(0))))
         for k in (*[m for m in MONEY if m != "dist"], *SESSION_MONEY, "rebuilt", "eod_change",
                   "residual")}
    t["dist"] = None if any(x is None for x in d["dist"]) else float(sum(d["dist"], Fraction(0)))
    t["price_pnl"] = t["hold"] + t["fill"]
    t["execution"] = t["fill"] + t["fees"]
    bp = (lambda x: x / t["traded_usd"] * 1e4) if t["traded_usd"] else (lambda x: float("nan"))
    t["fill_bp_of_traded"] = bp(t["fill"])
    t["execution_bp_of_traded"] = bp(t["execution"])
    t["residual_per_musd_sold"] = t["residual"] / t["sold_usd"] * 1e6 if t["sold_usd"] else float("nan")
    t["with_dist"] = None if t["dist"] is None else t["rebuilt"] + t["dist"]
    t["max_abs_residual"] = float(max(abs(x) for x in d["residual"]))
    t["sessions"] = len(d)
    return t


def _usd(x) -> str:
    return "UNMEASURED" if x is None else f"{x:,.2f}"


def _md_table(df: pd.DataFrame, money_cols) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        cells = []
        for c, v in zip(cols, r):
            missing = v is None or (isinstance(v, float) and math.isnan(v))
            if c in ("dist", "with_dist") and missing:
                cells.append("UNMEASURED")
            elif c in money_cols and not missing:
                cells.append(f"{v:,.2f}" if c != "fill_bp_of_traded" else f"{v:,.1f}")
            elif missing:
                cells.append("")
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def write_outputs(res: Result, out_dir: Path) -> dict:
    """CSVs and summary.md under `out_dir`. Returns {name: path}. Refuses, before
    writing anything, a directory under data/ or a file git could see."""
    out_dir = Path(out_dir)
    names = [f"{k}.csv" for k in OUTPUT_TABLES] + ["summary.md"]
    _refuse_data_dir(out_dir)
    _refuse_git_visible(out_dir, names)
    out_dir.mkdir(parents=True, exist_ok=True)
    tabs = {
        "name_day": _float_frame(res.name_day),
        "daily": _float_frame(res.daily),
        "by_name": group_table(res.name_day, ["symbol", "grp"]),
        "by_side": group_table(res.name_day, ["side"]),
        "by_grp": group_table(res.name_day, ["grp"]),
        "by_grp_side": group_table(res.name_day, ["grp", "side"]),
        "by_period": group_table(res.name_day, ["period"]),
        "by_period_grp": group_table(res.name_day, ["period", "grp"]),
        "dist_events": _float_frame(res.events),
        "positions_end": _float_frame(res.positions_end),
    }
    if tuple(tabs) != OUTPUT_TABLES:
        raise AttributionError(f"output tables {tuple(tabs)} != OUTPUT_TABLES {OUTPUT_TABLES}: the "
                               "write guard checked a different list")
    paths = {}
    for k, df in tabs.items():
        p = out_dir / f"{k}.csv"
        df.to_csv(p, index=False)
        paths[k] = p
    p = out_dir / "summary.md"
    p.write_text(summary_markdown(res, tabs))
    paths["summary"] = p
    return paths


def summary_markdown(res: Result, tabs: dict) -> str:
    t = totals(res)
    money = set(MONEY) | {"price_pnl", "with_dist", "fill_bp_of_traded", "eod_change", "rebuilt",
                          "residual", "eod_equity"}
    man = res.sources or {}
    kinds = list(res.dist_kinds)        # from the cache, never a default (review 2026-11-02)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    warn = [ln for ln in reconcile_lines(res.daily) if ln.startswith("WARN")]
    neg = sum(1 for x in res.daily["residual"] if x < 0)
    pos = sum(1 for x in res.daily["residual"] if x > 0)
    fee_sentence = ("the cef account's FEE activities are REG and CAT rows that equal this schedule on every "
                    "session read so far (the module docstring, FEES)." if res.book == "cef" else
                    "the schedule was measured on the cef account (the module docstring, FEES); this "
                    "account's own FEE activities are compared per session in the nightly report.")
    group_word = "group" if res.book == "cef" else "family"
    L = [f"# Live P&L attribution, {res.book} paper account, {res.first_session} to {res.asof}", "",
         f"Generated {now} by `scripts/cef/live_attribution.py analyse` from the cache "
         f"`{man.get('_cache_dir', '')}` (fetched {man.get('fetched_at_utc', 'time not recorded')}). "
         "Every figure below is computed by that script from that cache [V: computed at "
         "generation]; the sources are listed at the end. Research output: zero trials, no "
         "counter moved, nothing on the live path.", "",
         "Paper charges no borrow and credits no distributions (CLAUDE.md landmine 1). It does "
         "charge Alpaca's live regulatory fees (SEC on the value sold, CAT on shares traded, per "
         "session, rounded up), although Alpaca's paper page says it does not simulate them: "
         f"{fee_sentence} The fees line below is that "
         "schedule, modelled from the fills; the FEE activities are its check. The distribution "
         "line is what a real account would have booked, never part of the reconciliation.", "",
         "## Reconciliation against Alpaca's EOD history (the P&L of record)", "",
         "| line | USD |", "|---|---|",
         f"| official: EOD equity change, {res.first_session}..{res.asof} | {t['eod_change']:,.2f} |",
         f"| rebuilt: hold + fill + fees | {t['rebuilt']:,.2f} |",
         f"| official - rebuilt (residual) | {t['residual']:,.2f} |",
         f"| largest single-session residual (abs) | {t['max_abs_residual']:,.2f} |",
         f"| residual per $1M sold | {t['residual_per_musd_sold']:,.2f} |", "",
         f"{t['sessions']} sessions; residual negative on {neg}, positive on {pos}. A residual in "
         "proportion to the value sold would be a fee rate the model does not have. WARN "
         f"threshold ${RESIDUAL_WARN_USD:.2f}: "
         + (f"{len(warn)} session(s) above it." if warn else "no session above it.")]
    L += [f"- {w}" for w in warn]
    L += ["", "## Components", "",
          "| component | USD |", "|---|---|",
          f"| hold (q_prev x close change) | {t['hold']:,.2f} |",
          f"| of which nav_part (q_prev x close_prev x NAV return) | {t['nav_part']:,.2f} |",
          f"| of which disc_part (hold - nav_part) | {t['disc_part']:,.2f} |",
          f"| fill (fills against that day's close) | {t['fill']:,.2f} |",
          f"| fees (modelled: SEC on {t['sold_usd']:,.2f} sold, CAT on {t['shares_traded']:,.0f} "
          f"shares; per session, rounded up) | {t['fees']:,.2f} |",
          f"| execution cost on paper: fill + fees | {t['execution']:,.2f} |",
          f"| traded notional | {t['traded_usd']:,.2f} |",
          f"| fill, bp of traded | {t['fill_bp_of_traded']:,.1f} |",
          f"| fill + fees, bp of traded | {t['execution_bp_of_traded']:,.1f} |",
          f"| distributions not credited by paper ({', '.join(kinds)}) | {_usd(t['dist'])} |",
          f"| hold + fill + fees + distributions | {_usd(t['with_dist'])} |", "",
          "On an ex-date the mechanical widening of the discount (price and NAV fall by the same "
          "dollars, so the discount is wider in percent) lands in disc_part; see the module "
          "docstring, EX-DATES.", ""]
    if res.excluded_after_asof:
        L += [f"{res.excluded_after_asof} fill(s) in the cache dated after {res.asof} are outside "
              "the window and excluded.", ""]
    L += [f"## By period ({res.period_rule})", "", _md_table(tabs["by_period"], money), "",
          "The tables below leave the fees out: they are charged per session, not per name "
          "(daily.csv and the totals carry them).", "",
          f"## By {group_word} ({GROUP_SOURCE.get(res.book, res.book)})", "", _md_table(tabs["by_grp"], money), "",
          "## By side (the side of q_prev; a name opened that day takes the side it opened)", "",
          _md_table(tabs["by_side"], money), "",
          f"## By {group_word} and side", "", _md_table(tabs["by_grp_side"], money), "",
          f"## By period and {group_word}", "", _md_table(tabs["by_period_grp"], money), "",
          "## By name", "", _md_table(tabs["by_name"], money), "",
          "## Distribution events in the window", "",
          (_md_table(tabs["dist_events"], {"dist"}) if len(tabs["dist_events"])
           else "None in the cache's source for the traded symbols."), "",
          "## Every session's reconciliation", "", "```", *reconcile_lines(res.daily), "```", "",
          "## Gaps and caveats", ""]
    L += [f"- GAP: {g}" for g in res.gaps]
    L += ["- NAV alignment: a stale yfinance NAV copy (NAV(D-1) stamped D, "
          "results/cef/LIVE_NAV_QUALITY_2026-10-12.md) moves P&L between nav_part and disc_part; "
          "it never changes hold, fill or the reconciliation.",
          "- Positions are rebuilt from fills from a flat start: "
          f"{man.get('flat_start', {}).get('evidence', '(evidence not recorded)')}", "",
          "## Sources (from the cache manifest)", ""]
    for k in ("fills", "eod", "bars", "distributions", "distributions_check",
              "corporate_actions", "nav"):
        v = man.get(k)
        if v is not None:
            L.append(f"- **{k}**: {json.dumps(v, default=str, ensure_ascii=False)}")
    return "\n".join(L) + "\n"


def report(res: Result) -> str:
    t = totals(res)
    lines = [f"live attribution {res.first_session}..{res.asof}: {t['sessions']} sessions",
             *reconcile_lines(res.daily),
             f"official (EOD change) {t['eod_change']:,.2f}   rebuilt (hold+fill+fees) {t['rebuilt']:,.2f}"
             f"   official-rebuilt {t['residual']:,.2f}   max |session residual| {t['max_abs_residual']:,.2f}",
             f"hold {t['hold']:,.2f} = nav_part {t['nav_part']:,.2f} + disc_part {t['disc_part']:,.2f}"
             f"   fill {t['fill']:,.2f} ({t['fill_bp_of_traded']:,.1f}bp of {t['traded_usd']:,.2f} traded)"
             f"   fees (modelled) {t['fees']:,.2f} on {t['sold_usd']:,.2f} sold"
             f"   fill+fees {t['execution']:,.2f} ({t['execution_bp_of_traded']:,.1f}bp)"
             f"   dist (not credited) {_usd(t['dist'])}"]
    lines += [f"GAP: {g}" for g in res.gaps]
    if res.excluded_after_asof:
        lines.append(f"{res.excluded_after_asof} fill(s) after {res.asof} excluded")
    return "\n".join(lines)


# --------------------------------------------------------------- fetch

def _refuse_data_dir(path: Path) -> None:
    """Never write under data/ (CLAUDE.md landmine 9): in every worktree it is a
    symlink to the panels the live sleeve decides on."""
    p = Path(path).resolve()
    d = DATA_DIR.resolve()
    if p == d or d in p.parents:
        raise AttributionError(f"refusing to write {path}: it is under data/ ({d})")


def _refuse_git_visible(directory: Path, names) -> None:
    """Refuse to write any of `names` into `directory` if git could see it.

    Both the cache and the outputs hold the paper account's fills, equity and
    positions, and this repository is public (module docstring, USAGE). The first
    build's default --out-dir was visible to git (review 2026-11-02). Outside the
    repository, git cannot see the files, so nothing is checked. Inside it, every
    file must be ignored (`git check-ignore`; a tracked file counts as visible).
    If git cannot answer, the write is refused: there is no default.
    """
    root = REPO.resolve()
    p = Path(directory).resolve()
    if p != root and root not in p.parents:
        return
    paths = [(p / n).relative_to(root).as_posix() for n in names]
    try:
        r = subprocess.run(["git", "-C", str(root), "check-ignore", *paths],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        raise AttributionError(f"refusing to write in {directory}: git check-ignore could not "
                               f"run ({type(e).__name__}: {e})") from None
    if r.returncode not in (0, 1):      # 0 some ignored, 1 none ignored, else an error
        raise AttributionError(f"refusing to write in {directory}: git check-ignore exited "
                               f"{r.returncode}: {r.stderr.strip()[:200]}")
    visible = sorted(set(paths) - set(r.stdout.splitlines()))
    if visible:
        raise AttributionError(
            f"refusing to write {visible[:3]}{' ...' if len(visible) > 3 else ''}: git can see "
            "them, and this public repository must not carry the account's fills, equity or "
            f"positions. Use the gitignored default, or a directory outside {root}")


def yf_dividends(symbols) -> tuple[pd.DataFrame, list]:
    """The second distribution source: yfinance `Ticker.dividends`, keyless, the
    vendor and the ex-date convention of data/cef/cef_distributions.parquet
    (scripts/fetch_cef_distributions.py; docs/REFERENCES.md, the panel's CRSP
    check). Every row yfinance has is kept, so that "the source has rows for the
    name" means what it means in dist_score. Returns the rows and the names with
    none. An exception propagates: fetch writes nothing then."""
    import yfinance as yf
    rows, empty = [], []
    for tk in sorted(set(symbols)):
        dv = yf.Ticker(tk).dividends
        if dv is None or not len(dv):
            empty.append(tk)
            continue
        idx = pd.DatetimeIndex(dv.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)          # the exchange's wall date, as the panel does
        for day, v in zip(idx.normalize(), dv.values):
            rows.append({"ticker": tk, "ex_date": day.date().isoformat(), "amount": repr(float(v))})
    return pd.DataFrame(rows, columns=["ticker", "ex_date", "amount"]), empty


def yf_navs(symbols, start: dt.date, end: dt.date, *, book: str = BOOK) -> tuple[pd.DataFrame, list]:
    """yfinance daily Close as the NAV, the source and call of
    scripts/cef/fetch_daily.py (docs/REFERENCES.md §12h), at each book's own NAV
    symbol (`nav_symbols`). Keyless. Returns the rows dated [start, end], labelled
    by the price ticker, and the tickers for which yfinance returned none (a gap
    the analysis raises on only if that name was held)."""
    import yfinance as yf
    rows, empty = [], []
    symbol_of = nav_symbols(book, symbols)
    for tk in sorted(set(symbols)):
        h = yf.Ticker(symbol_of[tk]).history(start=start.isoformat(),
                                             end=(end + dt.timedelta(days=1)).isoformat(),
                                             auto_adjust=False)
        if not len(h):
            empty.append(tk)
            continue
        d = pd.to_datetime(h.index).tz_localize(None).normalize()
        for day, v in zip(d, h["Close"]):
            if start <= day.date() <= end:
                rows.append({"date": day.date().isoformat(), "ticker": tk, "nav": repr(float(v))})
    return pd.DataFrame(rows, columns=["date", "ticker", "nav"]), empty


def fetch(cache_dir: Path, *, since: dt.date, asof: dt.date | None = None, client=None,
          nav_fetcher=None, dist_check_fetcher=None, now: dt.datetime | None = None,
          book: str = BOOK) -> dict:
    """Read-only GETs on the cef paper account plus keyless yfinance -> the cache.

    Order: the EOD history first, because its first funded point fixes where the
    rebuild starts; then the session after the last point (the calendar); then
    fills for every calendar day from `since`; then bars, distributions and
    corporate actions for every filled symbol; then NAVs and the second
    distribution source (yfinance dividends). Raises before writing anything, or
    calling the broker, if the cache directory is under data/ or visible to git.
    Raises before writing anything if the asof point is not final (its stamp is
    in the future), or if no session before the first funded point was asked
    for, since then the flat start cannot be shown.

    `now` is also the second source's fetch time in the manifest. It is taken
    before the source is read, so it errs early: dist_score's "fetched after the
    close of the session following D" can only be judged false too often.
    """
    _refuse_data_dir(cache_dir)
    _refuse_git_visible(Path(cache_dir), list(FILES.values()))
    client = AR.AlpacaReader.from_environment(book) if client is None else client
    nav_fetcher = partial(yf_navs, book=book) if nav_fetcher is None else nav_fetcher
    dist_check_fetcher = yf_dividends if dist_check_fetcher is None else dist_check_fetcher
    now = dt.datetime.now(dt.timezone.utc) if now is None else now
    asof = AR.last_complete_date(now) if asof is None else asof
    if asof <= since:
        raise AttributionError(f"asof {asof} must be after since {since}")

    points = list(client.eod_equity_history(since, asof))
    if not points:
        raise AttributionError(f"EOD history: no funded point in {since}..{asof}")
    future = [d for d, _, stamp in points if stamp > now]
    if future:
        raise AttributionError(f"EOD point(s) {future} are stamped after now ({now:%Y-%m-%d %H:%M}Z): "
                               "not final yet; fetch again later")
    eod_rows = [(d.isoformat(), repr(float(e))) for d, e, _ in points]
    first, last = points[0][0], points[-1][0]
    after = client.calendar(last + dt.timedelta(days=1), last + dt.timedelta(days=14))
    if not after:
        raise AttributionError(f"the calendar lists no session in the 14 days after {last}")
    next_session = after[0]["date"]

    fills = []
    day = since
    while day <= last:
        fills.extend(client.activities_fills(day))
        day += dt.timedelta(days=1)
    parsed = parse_fills(fills)                         # raises on duplicates before writing
    syms = sorted({a["symbol"] for a in fills})
    if not syms:
        raise AttributionError(f"no FILL activity in {since}..{last}")

    if since < first:
        before = [r["date"] for r in client.calendar(since, first - dt.timedelta(days=1))]
        if not before:
            raise AttributionError(
                f"no session between --since {since} and the first funded EOD point {first} was "
                f"asked for, so the account cannot be shown flat at {first}; pass an earlier --since")
        flat = {"date": first.isoformat(),
                "evidence": (f"Alpaca's EOD history, asked from {since}, has no funded point before "
                             f"{first}: {len(before)} session(s) from {before[0]} to {before[-1]} "
                             f"carry equity 0 or no point, so the account held nothing at the start "
                             f"of {first}")}
    else:
        flat = flat_by_constant_equity(points, parsed, since)

    bars = AR.fetch_bars(client, syms, first, last)
    d_lo = first - dt.timedelta(days=DIST_QUERY_PAD_DAYS)
    d_hi = last + dt.timedelta(days=DIST_QUERY_PAD_DAYS)
    dists = [dict(e, ex_date=e["ex_date"].isoformat()) for e in client.distributions(syms, d_lo, d_hi)]
    c_lo = first - dt.timedelta(days=CA_QUERY_PAD_BEFORE_DAYS)
    c_hi = last + dt.timedelta(days=CA_QUERY_PAD_AFTER_DAYS)
    corp = [{"id": e["id"], "type": e["type"], "date": e["date"].isoformat(),
             "process_date": e["process_date"].isoformat(), "parties": e["parties"]}
            for e in client.corporate_actions(syms, c_lo, c_hi)]
    nav, nav_empty = nav_fetcher(syms, first - dt.timedelta(days=NAV_LOOKBACK_DAYS), last)
    check, check_empty = dist_check_fetcher(syms)
    parse_dist_check(check)                             # raises on a bad row before writing

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / FILES["fills"]).write_text(json.dumps(fills, indent=1))
    pd.DataFrame(eod_rows, columns=["date", "equity"]).to_csv(cache_dir / FILES["eod"], index=False)
    b = bars.copy()
    b["date"] = b["date"].dt.date.astype(str)
    b.to_csv(cache_dir / FILES["bars"], index=False)
    (cache_dir / FILES["dists"]).write_text(json.dumps(dists, indent=1, default=str))
    (cache_dir / FILES["corp"]).write_text(json.dumps(corp, indent=1))
    nav.to_csv(cache_dir / FILES["nav"], index=False)
    check.to_csv(cache_dir / FILES["dists_check"], index=False)
    man = {
        "book": book, "asof": last.isoformat(), "fetched_at_utc": now.isoformat(),
        "flat_start": flat,
        "fills": {"source": "GET /v2/account/activities/FILL, one call per calendar day "
                            "(AlpacaReader.activities_fills)",
                  "requested_start": since.isoformat(), "requested_end": last.isoformat(),
                  "n": len(fills)},
        "eod": {"source": "GET /v2/account/portfolio/history timeframe=1D "
                          "(AlpacaReader.eod_equity_history; stamps mapped to NY sessions)",
                "requested_start": since.isoformat(), "first_point": first.isoformat(),
                "next_session": next_session.isoformat(),
                "next_session_source": "GET /v2/calendar (AlpacaReader.calendar)"},
        "bars": {"source": "GET data.alpaca.markets/v2/stocks/bars timeframe=1Day feed=sip "
                           "adjustment=raw (scripts/ops/alpaca_read.fetch_bars)",
                 "range": [first.isoformat(), last.isoformat()]},
        "distributions": {"source": "GET data.alpaca.markets/v1/corporate-actions "
                                    "(AlpacaReader.distributions)",
                          "kinds": list(DIST_KINDS), "query": [d_lo.isoformat(), d_hi.isoformat()]},
        "corporate_actions": {"source": "GET data.alpaca.markets/v1/corporate-actions, no symbols "
                                        "filter, data_quality=all (AlpacaReader.corporate_actions)",
                              "types": sorted(AR.CORPORATE_ACTION_TYPES),
                              "query": [c_lo.isoformat(), c_hi.isoformat()]},
        "distributions_check": {"source": "yfinance Ticker.dividends, keyless, every row (the "
                                          "vendor of data/cef/cef_distributions.parquet, prod's "
                                          "second source in quantt/session/dist_score.py)",
                                "fetched_at_utc": now.isoformat(), "n": len(check),
                                "no_rows": check_empty},
        "nav": {"source": ("yfinance X{tk}X history(auto_adjust=False) Close, keyless" if book == BOOK else
                           f"yfinance {C4_NAV_MAP.name} symbols, history(auto_adjust=False) Close, keyless"),
                "no_rows": nav_empty},
    }
    (cache_dir / FILES["manifest"]).write_text(json.dumps(man, indent=1))
    print(f"cache {cache_dir}: {len(fills)} fills, {len(syms)} symbols, EOD {first}..{last}, "
          f"{len(bars)} bars, {len(dists)} distribution records, {len(corp)} corporate actions, "
          f"{len(nav)} NAV rows, {len(check)} second-source dividend rows"
          + (f"; NO NAV ROWS for {nav_empty}" if nav_empty else "")
          + (f"; NO DIVIDEND ROWS (second source) for {check_empty}" if check_empty else ""))
    return man


# --------------------------------------------------------------- CLI

def analyse(cache_dir: Path, out_root: Path, *, asof=None, breaks=None, grp=None) -> tuple[Result, dict]:
    inp = load_cache(cache_dir, grp=grp)
    inp.sources = dict(inp.sources, _cache_dir=str(cache_dir))
    res = attribute(inp, asof=asof, breaks=breaks)
    paths = write_outputs(res, Path(out_root) / res.asof.isoformat())
    return res, paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="read-only GETs + keyless yfinance -> cache")
    f.add_argument("--book", choices=BOOKS, default=BOOK)
    f.add_argument("--cache-dir", type=Path, default=None)
    f.add_argument("--asof", type=dt.date.fromisoformat, default=None)
    # Any date before the account's first funded session works; the cef paper
    # account opened on 2026-09-28 (quantt/collect/collect.py BOOKS eod_from), and
    # fetch raises if --since is not before its first funded point. C4 has no default:
    # its account's funding date is not this file's to assume.
    f.add_argument("--since", type=dt.date.fromisoformat, default=None)
    a = sub.add_parser("analyse", help="the cache only -> CSVs + summary.md")
    a.add_argument("--book", choices=BOOKS, default=BOOK)
    a.add_argument("--cache-dir", type=Path, default=None)
    a.add_argument("--out-dir", type=Path, default=None)
    a.add_argument("--asof", type=dt.date.fromisoformat, default=None)
    a.add_argument("--break", dest="breaks", type=dt.date.fromisoformat, action="append", default=None)
    args = ap.parse_args(argv)
    cache = args.cache_dir or (DEFAULT_CACHE if args.book == BOOK else DEFAULT_CACHE_C4)
    if args.cmd == "fetch":
        since = args.since
        if since is None:
            if args.book != BOOK:
                raise AttributionError("--since is required for book c4: a date before its first funded session")
            since = dt.date(2026, 9, 21)
        fetch(cache, since=since, asof=args.asof, book=args.book)
        return 0
    out = args.out_dir or (DEFAULT_OUT if args.book == BOOK else DEFAULT_OUT_C4)
    res, paths = analyse(cache, out, asof=args.asof, breaks=args.breaks,
                         grp=None)
    print(report(res))
    print(f"wrote {paths['summary'].parent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
