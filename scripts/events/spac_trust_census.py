"""SPAC trust-value census: a ZERO-TRIAL look at buying SPAC common below trust and redeeming at trust.

    export QUANTT_ENV_FILE=/abs/path/config/.env   # SEC_USER_AGENT, Alpaca keys, R2: read, never printed
    python3 scripts/events/spac_trust_census.py            # fetch what is not cached, then build
    python3 scripts/events/spac_trust_census.py --offline  # rebuild from the caches only
    python3 scripts/events/spac_trust_census.py --frozen   # keep the cached snapshot; fetch only what is missing
    python3 scripts/events/spac_trust_census.py --ibkr     # the gate re-run on IBKR's terms (2026-10-19); public files only

WHY THIS EXISTS (team lead, special-situations sprint, job 4 of 6, 2026-10-15)
-----------------------------------------------------------------------------
A SPAC holds its IPO money in a trust account; a public holder can redeem each
share for its pro-rata slice of the trust at a business-combination vote, at an
extension vote, or when the SPAC liquidates at its deadline. If the common
trades below that slice, a long position has a defined floor and needs no short
and no borrow. Before anyone spends a trial on it (EVENTS counter), the desk
needs the census this script builds: how many SPACs there are, which are
tradable at Alpaca, how far below trust they trade, what the terms imply as a
yield, how much can be bought, and whether Alpaca can redeem at all.

NO TRADE RETURN IS COMPUTED HERE. The historical section measures LEVELS only
(price and trust per share at one point in time) and only before 2023-01-01
(the desk's time holdout). Whether a position bought at that point was in fact
redeemed, and at what, is the trial, and is not read.

THE ROUTES, AND WHY
-------------------
EDGAR, all through `scripts/data/edgar_client.py` (rate limit, back-off, cache):

1. **Who is a SPAC.** SIC 6770 ("blank checks") is the SEC's code, but it is
   the code TODAY: a SPAC that completed its merger usually takes the
   operating company's SIC, so a SIC-6770 list alone would drop most completed
   deals (survivorship). Candidates are therefore the union of
     (a) every CIK whose SIC is 6770 today (the company browse, ~3,350 CIKs);
     (b) every CIK that filed a 424B4 (a final IPO prospectus) from 2014 on,
         from the quarterly full indexes (the route `fetch_edgar_events` uses).
   A candidate is a SPAC if its first 424B4 is dated 2010 or later and at
   least one of: SIC 6770 today; an 8-K item 5.06 ("Change in Shell Company
   Status") after that 424B4; or an XBRL balance sheet within three years of
   it on which assets held in trust are at least 90% of total assets (a
   trust-funded shell; no operating company looks like that). Which rule
   admitted each SPAC is a column, so the definition can be audited.
2. **Each company's filing history** comes from the SEC's nightly bulk
   `submissions.zip` and the XBRL facts from `companyfacts.zip`: ONE request
   each instead of ~6,000 per-company calls. The SEC's API page calls the bulk
   archives "the most efficient means to fetch large amounts of API data".
   A CIK that is not in the archive (registered after the nightly build) is
   fetched from the per-company API.
3. **Events**, dated from the forms (`spac_events`, which documents each rule):
   IPO (first 424B4), deal announced (first 425), deal completed (first 8-K
   with item 2.01 or 5.06, or a change-in-control 8-K beside a delisting when
   the deal used a new holding company), liquidated (a delisting or
   deregistration form with no completion and no periodic report after it),
   and extension votes (an 8-K with item 5.07, before any completion, whose
   text proposes to extend the deadline). Liquidations and extensions are
   confirmed by reading the 8-K text, not inferred from the form alone.

Alpaca (read-only GETs: `/v2/assets`, `/v2/stocks/bars`; NEVER an order
endpoint): which of today's live SPACs list a tradable common share, on which
exchange, and its dollar volume.

CRSP (R2, read-only; licensed, so its rows stay in gitignored `_cache_spac/`):
pre-2023 closing prices for the historical discount distribution, linked to
EDGAR by name and listing date (`link_crsp`).

WHAT IS NOT CLAIMED
-------------------
* The terms-implied yield is a yield TO THE STATED DEADLINE IF HELD AND
  REDEEMED AT THE TRUST VALUE LAST REPORTED. It is not a forecast: a SPAC can
  extend without offering redemption at the old deadline, can be delisted,
  and can pay out less than the 10-Q trust (taxes, dissolution expenses).
  Those risks are in the note, not in the number.
* Trust per share is the last 10-Q/10-K figure, NOT accrued to today: the
  headline discount is therefore conservative (the trust keeps earning).
  The `*_accrued`, `yield_total_*` and `spread_*` columns are a LABELLED
  MODEL (`accrued_terms`): the trust earning FRED's 3-month bill, gross of
  the taxes and withdrawals it pays out of interest. Never the headline.
* A SPAC whose deal vote has passed (`deal_vote_date`) has also passed the
  redemption deadline before it; its unredeemed shares ride the merger. It is
  kept in the CSV and out of the `redeemable_pool` every statistic uses
  (measured 2026-10-18: five such SPACs traded 13-52% below trust).

THE IBKR GATE (`--ibkr`, added 2026-10-19)
-----------------------------------------
Team lead ruling 2026-10-19: SPAC redemptions go through IBKR (opened as a
second broker, equities only), and the gate is re-run on IBKR's terms. The
`--ibkr` mode does NOT rebuild the census. It reads the census's committed
outputs (`LIVE_CSV`, `YEARS_CSV`, the 2026-10-15 snapshot) and two PUBLIC IBKR
files, and adds: which live SPACs IBKR lists (`ibkr_match`), the yield after
IBKR's commission and its USD 100 SPAC-redemption fee at a grid of ticket
sizes (`ibkr_net_terms`), the capacity that repays the fee, and the number of
elections a year (`ibkr_election_load`). It opens no EDGAR client, no broker
connection and reads no credentials. See `results/events/SPAC_IBKR_2026-10-19.md`.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:  # run as a script, not -m
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events"
SPAC_DIR = OUT / "spac"                # the census's and the IBKR gate's outputs; their notes sit in OUT
CACHE = OUT / "_cache_spac"            # gitignored (results/**/_cache_*): Alpaca snapshots, CRSP rows
NOTE_DATE = "2026-10-15"
LIVE_CSV = SPAC_DIR / f"spac_trust_census_live_{NOTE_DATE}.csv"
UNIVERSE_CSV = SPAC_DIR / f"spac_trust_census_universe_{NOTE_DATE}.csv"
YEARS_CSV = SPAC_DIR / f"spac_trust_census_years_{NOTE_DATE}.csv"
SUMMARY_JSON = SPAC_DIR / f"spac_trust_census_summary_{NOTE_DATE}.json"
HIST_ROWS = CACHE / "spac_hist_crsp_rows.csv"   # CRSP prices: licensed, never tracked

SIC_BROWSE_URL = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&SIC=6770&type=&dateb="
                  "&owner=include&count=100&start={start}&output=atom")
SUBMISSIONS_ZIP_URL = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
COMPANYFACTS_ZIP_URL = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
DAY = 86400

IPO_FORM = "424B4"
SPAC_IPO_START = date(2010, 1, 1)       # a 424B4 before this is not a SPAC IPO in scope
CENSUS_YEARS = range(2015, 2027)
HOLDOUT_START = date(2023, 1, 1)         # the desk's time holdout: history stops before it

# Forms that end a listing or a registration. 25-NSE is filed by the exchange
# and indexed under the issuer; 15-12B/15-12G/15-15D deregister.
TERMINATION_FORMS = frozenset({"25-NSE", "25", "15-12B", "15-12G", "15-15D"})
PERIODIC_FORMS = frozenset({"10-Q", "10-K", "10-Q/A", "10-K/A", "NT 10-Q", "NT 10-K", "20-F", "10-KT"})
# A liquidated SPAC files nothing periodic after it delists. This is the grace
# period for a late 10-K that covers the year it liquidated in.
POST_TERMINATION_GRACE_DAYS = 120
# "Still filing" for a live SPAC: a 10-Q is due within 40-45 days of each
# quarter end, so 200 days without a periodic report means two missed reports.
LIVE_LAST_FILING_DAYS = 200
# An IPO this recent may not have filed its first 10-Q yet.
RECENT_IPO_DAYS = 150
HOLDCO_WINDOW_DAYS = 30
TRUST_SHARE_OF_ASSETS = 0.90
TRUST_EVIDENCE_YEARS = 3

TRUST_CONCEPTS = ("AssetsHeldInTrustNoncurrent", "AssetsHeldInTrustCurrent", "AssetsHeldInTrust")


class CensusError(RuntimeError):
    """A required input is missing or contradicts itself."""


# ------------------------------------------------------------------ EDGAR parsing

_BROWSE_CIK_RE = re.compile(r"<cik>(\d{1,10})</cik>")


def parse_sic_browse(atom: str) -> list[int]:
    """CIKs on one page of the SIC company browse (Atom output)."""
    if "<feed" not in atom:
        raise CensusError("SIC browse page is not an Atom feed")
    return [int(c) for c in _BROWSE_CIK_RE.findall(atom)]


def items_of(s) -> frozenset:
    """'2.01,5.06,9.01' -> {'2.01','5.06','9.01'}; empty for a non-8-K row."""
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return frozenset()
    return frozenset(x.strip() for x in str(s).split(",") if x.strip())


def submissions_frame(blocks: list[dict], cik: int) -> pd.DataFrame:
    """The submissions API's column blocks -> one row per filing, de-duplicated, oldest first."""
    frames = []
    for b in blocks:
        n = len(b["accessionNumber"])
        if any(len(v) != n for v in b.values() if isinstance(v, list)):
            raise CensusError(f"CIK {cik}: ragged submissions block")
        if n:
            frames.append(pd.DataFrame({k: v for k, v in b.items() if isinstance(v, list)}))
    if not frames:
        raise CensusError(f"CIK {cik}: no filings in its submissions blocks")
    import warnings
    with warnings.catch_warnings():   # pandas warns when a page has an all-empty column (e.g. no 8-K items)
        warnings.simplefilter("ignore", FutureWarning)
        s = pd.concat(frames, ignore_index=True).drop_duplicates("accessionNumber")
    s["filingDate"] = pd.to_datetime(s["filingDate"])
    s["cik"] = int(cik)
    return s.sort_values(["filingDate", "accessionNumber"]).reset_index(drop=True)


# ------------------------------------------------------------------ events

def spac_events(f: pd.DataFrame, today: date) -> dict:
    """Date one SPAC's life from its filing list. Pure: `f` has form, filingDate, items.

    Rules, in the order they are applied (each is a fact about the FORMS; the
    text checks that confirm liquidations and extensions run elsewhere):

    ipo_date        first 424B4 dated SPAC_IPO_START or later. None -> not in scope.
    announce_date   first 425 after the IPO (a 425 is a business-combination
                    communication; it is indexed under the SPAC as subject).
    completion      first 8-K after the IPO with item 2.01 ("Completion of
                    Acquisition") or 5.06 ("Change in Shell Company Status").
                    Measured on M III Acquisition (CIK 1652362): its 2018
                    closing 8-K carries 2.01 but NOT 5.06, so 5.06 alone would
                    have called a completed deal a liquidation.
    holdco          no 2.01/5.06, but an 8-K with item 5.01 ("Changes in Control")
                    within HOLDCO_WINDOW_DAYS of the first termination form, and
                    a 425 before it: the deal closed into a NEW holding company,
                    which files the 2.01 under its own CIK. A 5.01 alone is not
                    enough: a sponsor sale is also a change in control.
    termination     first TERMINATION_FORMS filing after the IPO.
    status          completed | liquidated | live | delisted_alive | dormant:
                    liquidated = terminated, not completed, and no periodic
                    report more than POST_TERMINATION_GRACE_DAYS after it;
                    live = not completed, not terminated, a periodic report in
                    the last LIVE_LAST_FILING_DAYS (or an IPO in the last
                    RECENT_IPO_DAYS); delisted_alive = terminated but still
                    filing periodic reports; dormant = none of these.
    vote_8ks        accessions of 8-Ks with item 5.07 after the IPO and before
                    completion (or, if none, termination): the candidates for
                    extension votes, confirmed by text elsewhere.
    """
    need = {"form", "filingDate", "items", "accessionNumber"}
    if not need <= set(f.columns):
        raise CensusError(f"spac_events needs {sorted(need)}; missing {sorted(need - set(f.columns))}")
    f = f.sort_values(["filingDate", "accessionNumber"])
    t0 = pd.Timestamp(SPAC_IPO_START)
    ipo = f[(f["form"] == IPO_FORM) & (f["filingDate"] >= t0)]
    out = {"ipo_date": None, "announce_date": None, "completion_date": None, "completion_rule": None,
           "termination_date": None, "termination_form": None, "status": None, "vote_8ks": [],
           "last_periodic": None, "n_425": 0}
    if ipo.empty:
        out["status"] = "no_ipo_in_scope"
        return out
    ipo_d = ipo["filingDate"].iloc[0]
    out["ipo_date"] = ipo_d.date()
    after = f[f["filingDate"] >= ipo_d]
    eightk = after[after["form"] == "8-K"]
    it = eightk["items"].map(items_of)
    f425 = after[after["form"] == "425"]
    out["n_425"] = int(len(f425))
    if len(f425):
        out["announce_date"] = f425["filingDate"].iloc[0].date()
    def has(fn):  # a boolean mask over `eightk` (explicit dtype: an empty map is object)
        return it.map(fn).astype(bool).to_numpy() if len(it) else np.zeros(0, dtype=bool)
    comp = eightk.loc[has(lambda s: bool(s & {"2.01", "5.06"}))]
    term = after[after["form"].isin(TERMINATION_FORMS)]
    term_d = term["filingDate"].iloc[0] if len(term) else None
    if term_d is not None:
        out["termination_date"] = term_d.date()
        out["termination_form"] = term["form"].iloc[0]
    comp_d = None
    if len(comp):
        comp_d = comp["filingDate"].iloc[0]
        out["completion_rule"] = "8k_2.01_or_5.06"
    elif term_d is not None and len(f425) and f425["filingDate"].iloc[0] <= term_d:
        w = pd.Timedelta(days=HOLDCO_WINDOW_DAYS)
        ctl = eightk.loc[has(lambda s: "5.01" in s) & (eightk["filingDate"] >= term_d - w).to_numpy()
                         & (eightk["filingDate"] <= term_d + w).to_numpy()]
        if len(ctl):
            comp_d = ctl["filingDate"].iloc[0]
            out["completion_rule"] = "holdco_5.01_at_delisting"
    if comp_d is not None:
        out["completion_date"] = comp_d.date()
    per = after[after["form"].isin(PERIODIC_FORMS)]
    if len(per):
        out["last_periodic"] = per["filingDate"].iloc[-1].date()
    end_d = comp_d if comp_d is not None else term_d
    votes = eightk.loc[has(lambda s: "5.07" in s)]
    if end_d is not None:
        votes = votes[votes["filingDate"] < end_d]
    out["vote_8ks"] = list(votes["accessionNumber"])
    td = pd.Timestamp(today)
    if comp_d is not None:
        out["status"] = "completed"
    elif term_d is not None:
        late = per[per["filingDate"] > term_d + pd.Timedelta(days=POST_TERMINATION_GRACE_DAYS)]
        if late.empty:
            out["status"] = "liquidated"
        elif (td - late["filingDate"].iloc[-1]).days <= LIVE_LAST_FILING_DAYS:
            out["status"] = "delisted_alive"
        else:
            out["status"] = "dormant"
    elif len(per) and (td - per["filingDate"].iloc[-1]).days <= LIVE_LAST_FILING_DAYS:
        out["status"] = "live"
    elif (td - ipo_d).days <= RECENT_IPO_DAYS:
        out["status"] = "live"
    else:
        out["status"] = "dormant"
    return out


def year_counts(ev: pd.DataFrame, years=CENSUS_YEARS) -> pd.DataFrame:
    """Per calendar year: IPOs, deals announced, deals completed, liquidations, extension votes.

    `ev` has one row per SPAC with ipo_date, announce_date, completion_date,
    status, termination_date and `ext_dates` (a list of dated, text-confirmed
    extension votes). A liquidation is dated by its termination form.
    """
    def yr(col, mask=None):
        s = ev[col] if mask is None else ev.loc[mask, col]
        return pd.to_datetime(s.dropna()).dt.year.value_counts()
    ipo = yr("ipo_date")
    ann = yr("announce_date")
    comp = yr("completion_date")
    liq = yr("termination_date", ev["status"] == "liquidated")
    unc = yr("termination_date", ev["status"] == "unclassified")
    ext_d = pd.to_datetime(pd.Series([d for ds in ev["ext_dates"] for d in ds], dtype="object"))
    ext = ext_d.dt.year.value_counts() if len(ext_d) else pd.Series(dtype=int)
    ext_spacs = pd.Series(dtype=int)
    if len(ext_d):
        pairs = {(int(c), pd.Timestamp(d).year) for c, ds in zip(ev["cik"], ev["ext_dates"]) for d in ds}
        ext_spacs = pd.Series([y for _, y in pairs]).value_counts()
    rows = []
    for y in years:
        rows.append({"year": y, "ipos": int(ipo.get(y, 0)), "deals_announced": int(ann.get(y, 0)),
                     "deals_completed": int(comp.get(y, 0)), "liquidations": int(liq.get(y, 0)),
                     "delisted_unclassified": int(unc.get(y, 0)),
                     "extension_votes": int(ext.get(y, 0)), "spacs_with_extension_vote": int(ext_spacs.get(y, 0))})
    return pd.DataFrame(rows)


def live_at(ev: pd.DataFrame, when: pd.Timestamp) -> int:
    """SPACs whose IPO was on or before `when` and whose life had not ended by it."""
    ipo = pd.to_datetime(ev["ipo_date"])
    end = pd.to_datetime(ev["completion_date"]).fillna(pd.to_datetime(ev["termination_date"]))
    # A SPAC with no end date and status 'dormant' stopped filing at an unknown
    # date; it is excluded rather than counted as alive forever.
    alive_open = end.isna() & ev["status"].isin(["live", "delisted_alive"])
    return int(((ipo <= when) & ((end > when) | alive_open)).sum())


# ------------------------------------------------------------------ text checks

_TAG_RE = re.compile(r"<[^>]{0,400}>")


def plain(text: str) -> str:
    """HTML/SGML -> one line of plain text (tags removed, entities decoded, whitespace collapsed)."""
    import html
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", text))).strip()


# Measured 2026-10-15: a looser proximity rule ("extension ... deadline ...
# business combination") matched the forward-looking boilerplate of a DEAL-vote
# 8-K ("the potential failure to obtain an extension of the business
# combination deadline", Cerberus Telecom, CIK 1824577). An extension is now
# recognised only by the proposal's own name or by the charter language.
EXTENSION_RE = re.compile(
    r"extension (?:amendment )?proposal|extension amendment|(?:charter|articles) extension"
    r"|extension (?:special |general |extraordinary general )?meeting"
    r"|extend the (?:date|deadline|period|termination date)[^.]{0,80}(?:by which|within which|for)[^.]{0,80}"
    r"(?:must|has to|is required to|to) (?:consummate|complete|effect)", re.I)
# Widened 2026-10-18 on the liquidated member of the declared sample, Social
# Capital Hedosophia IV (CIK 1818876): "redeem (the “Redemption”) 100% of the
# Company’s issued and outstanding Class A ordinary shares", missed by the
# first alternative and so left "unclassified" even on its full submission.
LIQUIDATION_RE = re.compile(
    r"redeem (?:\([^)]{0,40}\) )?(?:all|100%)(?: of)? (?:the |its |our |the company[’']s )?"
    r"(?:outstanding |issued and outstanding )?(?:public |ipo )?"
    r"(?:class a )?(?:shares|ordinary shares|common stock|units)"
    r"|redemption of (?:all|100%)(?: of)? (?:the |its |our )?(?:outstanding )?(?:public |ipo )?(?:class a )?(?:shares|ordinary shares|common stock)"
    r"|will not (?:be able to )?consummate (?:an|its|the) initial business combination within the time period"
    r"|(?:will|intends to|has determined to|elected to|decided to) (?:dissolve and )?liquidate"
    r"|liquidation of the trust account|ceased? all operations except for the purposes? of winding up"
    r"|dissolve and liquidate|wind up (?:its|the company's) (?:affairs|operations)", re.I)
COMPLETION_RE = re.compile(
    r"(?:consummated|completed|closed) (?:the|its|their) (?:initial |previously announced |proposed )?"
    r"(?:business combination|merger|transactions?|acquisition)"
    r"|(?:shareholders|stockholders)[^.]{0,120}(?:approved|adopted)[^.]{0,80}(?:business combination|merger agreement|"
    r"merger proposal|transaction agreement|acquisition)"
    r"|(?:business combination|merger|acquisition|transaction) proposal (?:was|were) (?:duly )?approved", re.I)
REDEEM_PRICE_RE = re.compile(
    r"(?:approximately|of)\s+\$\s?(\d{1,2}\.\d{2,4})\s+per\s+(?:public\s+|class a\s+(?:ordinary\s+|common\s+)?)?share",
    re.I)


# A vote 8-K on the DEAL itself. Measured 2026-10-18 on the live SPACs: two
# of them (Black Hawk, CIK 2000775, 2026-10-13; Ribbon, CIK 2035016,
# 2026-09-11) traded more than 40% below their last reported trust because
# their deal votes had passed, and with them the redemption deadline that
# preceded each vote; unredeemed shares now ride the merger, not the trust.
# Calisa (CIK 2026767, 2026-10-08) names its "Business Combination Proposal"
# without any wording COMPLETION_RE recognises, so the proposal's own name is
# the test, not the word "approved".
DEAL_VOTE_RE = re.compile(
    r"business combination proposal|merger proposal|acquisition proposal|transaction proposal"
    r"|approve (?:and adopt )?the (?:business combination|merger) agreement", re.I)


def is_deal_vote_text(t: str) -> bool:
    """A 5.07 8-K reporting a vote on the business combination (not only on an extension).

    An 8-K that reports both an extension and an approved deal (one meeting,
    both proposals) counts as a deal vote: the redemption window that
    preceded it was the deal's.
    """
    return bool(DEAL_VOTE_RE.search(t)) and (not is_extension_text(t) or is_completion_text(t))


def is_extension_text(t: str) -> bool:
    """An 8-K whose text proposes or reports extending the business-combination deadline."""
    return bool(EXTENSION_RE.search(t))


def is_completion_text(t: str) -> bool:
    """An 8-K whose text reports a business combination approved by holders or consummated."""
    return bool(COMPLETION_RE.search(t))


def is_liquidation_text(t: str) -> bool:
    """An 8-K whose text announces redeeming all public shares / liquidating the trust."""
    return bool(LIQUIDATION_RE.search(t))


def per_share_prices(t: str, lo: float = 9.0, hi: float = 13.0) -> list[float]:
    """Dollar-per-share figures in the plausible trust range ($9-$13) quoted in a text."""
    return [float(x) for x in REDEEM_PRICE_RE.findall(t) if lo <= float(x) <= hi]


# ------------------------------------------------------------------ deadlines

_MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december")
DATE_RE = re.compile(rf"\b({_MONTHS})\s+(\d{{1,2}}),?\s+(20\d\d)\b", re.I)
_WORDNUM = {"six": 6, "nine": 9, "twelve": 12, "fifteen": 15, "eighteen": 18, "twenty-one": 21,
            "twenty one": 21, "twenty-four": 24, "twenty four": 24, "twenty-seven": 27, "thirty": 30,
            "thirty-six": 36, "thirty six": 36, "twenty-two": 22, "twenty-three": 23, "thirteen": 13,
            "fourteen": 14, "sixteen": 16, "seventeen": 17, "nineteen": 19, "twenty": 20}
MONTHS_FROM_IPO_RE = re.compile(
    r"(\d{1,2}|" + "|".join(sorted((re.escape(k) for k in _WORDNUM), key=len, reverse=True)) + r")"
    r"(?:\s*\(\d{1,2}\))?\s+months\s+from\s+the\s+closing\s+of\s+(?:this|the|our)\s+(?:initial\s+public\s+)?offering",
    re.I)
COMBINATION_CONTEXT_RE = re.compile(
    r"(?:business combination|combination period|to consummate|to complete|liquidate|dissolution)", re.I)


def parse_date(m: re.Match) -> date:
    return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()


def months_from_ipo(prospectus: str) -> list[int]:
    """Every 'N months from the closing of this offering' in a prospectus, in order of appearance."""
    out = []
    for m in MONTHS_FROM_IPO_RE.finditer(prospectus):
        g = m.group(1).lower()
        out.append(int(g) if g.isdigit() else _WORDNUM[g])
    return out


def base_deadline_months(prospectus: str) -> int | None:
    """The base completion window of a SPAC prospectus: the modal 'N months from the closing'.

    A prospectus repeats the base window many times and mentions extended
    windows ("or up to 18 months if we extend") less often; the mode is the
    base. None if the phrase never occurs (the prospectus words it otherwise),
    and the row is then reported as unparsed, never guessed.
    """
    ms = [m for m in months_from_ipo(prospectus) if 6 <= m <= 36]
    if not ms:
        return None
    vc = pd.Series(ms).value_counts()
    top = vc[vc == vc.max()].index
    return int(min(top))  # a tie between base and extended: the shorter is the base


DEADLINE_SENTENCE_RE = re.compile(
    r"[^.]{0,400}(?:until|by|before|on or before|prior to)\s+(?:" + _MONTHS + r")\s+\d{1,2},?\s+20\d\d[^.]{0,400}", re.I)


def deadline_candidates(text: str, after: date) -> list[date]:
    """Dates after `after` named in sentences that speak of completing a business combination.

    Used on the latest 10-Q of a live SPAC. A 10-Q states its deadline in
    several forms ("we have until March 1, 2027", "by March 1, 2027 (or up to
    September 1, 2027 if extended)"); every such date is returned, sorted, and
    the caller takes the latest as the deadline if fully extended
    (conservative for a yield) and the earliest as the next one.
    """
    out = set()
    for s in DEADLINE_SENTENCE_RE.finditer(text):
        sent = s.group(0)
        if not COMBINATION_CONTEXT_RE.search(sent):
            continue
        if not re.search(r"business combination|combination period", sent, re.I):
            continue
        for m in DATE_RE.finditer(sent):
            try:
                d = parse_date(m)
            except ValueError:
                continue
            if d > after:
                out.add(d)
    return sorted(out)


# ------------------------------------------------------------------ XBRL trust

def concept_points(facts: dict, concept: str, unit: str = "USD") -> pd.DataFrame:
    """Instant facts of one us-gaap concept from a companyfacts JSON: end, val, form, filed, accn."""
    try:
        rows = facts["facts"]["us-gaap"][concept]["units"][unit]
    except KeyError:
        return pd.DataFrame(columns=["end", "val", "form", "filed", "accn", "concept"])
    df = pd.DataFrame(rows)
    if df.empty or "end" not in df:
        return pd.DataFrame(columns=["end", "val", "form", "filed", "accn", "concept"])
    if "start" in df:
        df = df[df["start"].isna()]   # instants only (balance-sheet values)
    df = df.assign(end=pd.to_datetime(df["end"]), filed=pd.to_datetime(df["filed"]), concept=concept)
    return df[["end", "val", "form", "filed", "accn", "concept"]]


def trust_series(facts: dict) -> pd.DataFrame:
    """Assets held in trust by balance-sheet date (latest filing wins for a date).

    SPACs tag the trust with one of three us-gaap elements, and some switch
    from Noncurrent to Current as the deadline nears. Where two elements give
    different values for one date, the larger is the trust (a filer that tags
    both splits nothing: the trust is one account), and the disagreement is
    counted in `n_conflict` rather than resolved silently.
    """
    parts = [concept_points(facts, c) for c in TRUST_CONCEPTS]
    df = pd.concat([p for p in parts if len(p)], ignore_index=True) if any(len(p) for p in parts) else None
    if df is None or df.empty:
        return pd.DataFrame(columns=["end", "trust", "n_conflict", "filed", "accn"])
    df = df.sort_values("filed").drop_duplicates(["end", "concept"], keep="last")
    g = df.groupby("end")
    out = pd.DataFrame({"trust": g["val"].max(), "n_conflict": g["val"].nunique() - 1,
                        "filed": g["filed"].max(), "accn": g["accn"].last()}).reset_index()
    return out.sort_values("end").reset_index(drop=True)


def latest_point(facts: dict, concept: str, unit: str, end: pd.Timestamp) -> float | None:
    """The value of `concept` at exactly balance-sheet date `end` (latest filing), or None."""
    p = concept_points(facts, concept, unit)
    p = p[p["end"] == end].sort_values("filed")
    return float(p["val"].iloc[-1]) if len(p) else None


def trust_asset_share(facts: dict) -> pd.DataFrame:
    """Trust / total assets by balance-sheet date (the SPAC signature: ~1)."""
    tr = trust_series(facts)
    a = concept_points(facts, "Assets").sort_values("filed").drop_duplicates("end", keep="last")
    if tr.empty or a.empty:
        return pd.DataFrame(columns=["end", "trust", "assets", "share"])
    m = tr.merge(a[["end", "val"]].rename(columns={"val": "assets"}), on="end")
    m = m[m["assets"] > 0]
    return m.assign(share=m["trust"] / m["assets"])[["end", "trust", "assets", "share"]]


# ------------------------------------------------------------------ terms yield

def terms_yield(price: float, trust_ps: float, asof: date, deadline: date) -> dict:
    """Discount to trust and the annualised yield to `deadline` at the reported trust.

    discount   price / trust_ps - 1 (negative = below trust)
    gain       trust_ps / price - 1, the gross gain if redeemed at trust
    simple     gain * 365 / days
    compound   (1 + gain) ** (365 / days) - 1
    Raises on a non-positive input or a deadline not after `asof` (a passed
    deadline has no yield; the caller reports it as such).
    """
    if not (price > 0 and trust_ps > 0):
        raise ValueError(f"price {price} and trust_ps {trust_ps} must be positive")
    days = (deadline - asof).days
    if days <= 0:
        raise ValueError(f"deadline {deadline} is not after {asof}")
    gain = trust_ps / price - 1.0
    return {"discount": price / trust_ps - 1.0, "gain": gain, "days": days,
            "simple": gain * 365.0 / days, "compound": (1.0 + gain) ** (365.0 / days) - 1.0}


TBILL_CACHE = CACHE / "fred_DTB3.parquet"
TBILL_SERIES = "DTB3"    # FRED: 3-month Treasury bill, secondary market, discount basis, % p.a.


def tbill_series(offline: bool) -> pd.Series:
    """FRED DTB3 (percent), date-indexed, from `scripts/gamma/fetch_fred.py`'s format; cached.

    WHY a T-bill rate at all: the trust holds T-bills or a government money
    fund (prospectus quotes in `spac_mechanics`), so a share bought AT trust
    earns about the bill rate, and the interest earned after the last balance
    sheet is part of what a redeeming holder is paid. The census headline
    stays on the REPORTED trust (the brief's definition); this rate feeds only
    the labelled accrual columns. It is gross of the taxes and permitted
    withdrawals a trust pays out of interest, so it is an upper bound.
    """
    if TBILL_CACHE.exists():
        df = pd.read_parquet(TBILL_CACHE)
    elif offline:
        raise CensusError(f"offline and {TBILL_CACHE.name} is not cached")
    else:
        from scripts.gamma.fetch_fred import fetch
        df = fetch(TBILL_SERIES)
        CACHE.mkdir(parents=True, exist_ok=True)
        df.to_parquet(TBILL_CACHE)
    if set(df["series"].unique()) != {TBILL_SERIES}:
        raise CensusError(f"{TBILL_CACHE.name} is not {TBILL_SERIES}")
    s = df.set_index(pd.to_datetime(df["date"]))["value"].sort_index()
    if s.isna().any():
        raise CensusError(f"{TBILL_SERIES} has missing values")
    return s


def accrued_terms(price: float, trust_ps: float, start: date, asof: date, deadline: date, tb: pd.Series) -> dict:
    """The terms with the trust earning the T-bill rate after its last report (a labelled model).

    trust_ps_accrued = trust_ps * (1 + r_past * (asof - start)/365), r_past the
                       mean DTB3 over (start, asof]: interest since the report.
    yield_total      = (trust_ps_accrued * (1 + r_now * days/365) / price - 1) * 365/days,
                       r_now the last DTB3 on or before `asof`: the yield to
                       `deadline` if the trust keeps earning today's bill rate.
    spread           = yield_total - r_now: the excess over holding the bill.
    Only rates published on or before `asof` are used. Raises if none is.
    """
    if not (price > 0 and trust_ps > 0):
        raise ValueError("price and trust_ps must be positive")
    days = (deadline - asof).days
    if days <= 0:
        raise ValueError(f"deadline {deadline} is not after {asof}")
    if start > asof:
        raise ValueError(f"accrual start {start} is after {asof}")
    known = tb[tb.index <= pd.Timestamp(asof)]
    if known.empty:
        raise CensusError(f"no {TBILL_SERIES} rate on or before {asof}")
    r_now = float(known.iloc[-1]) / 100.0
    win = known[known.index > pd.Timestamp(start)]
    r_past = float(win.mean()) / 100.0 if len(win) else r_now
    acc = trust_ps * (1.0 + r_past * (asof - start).days / 365.0)
    yt = (acc * (1.0 + r_now * days / 365.0) / price - 1.0) * 365.0 / days
    return {"tbill_past": r_past, "tbill_now": r_now, "trust_ps_accrued": acc,
            "discount_accrued": price / acc - 1.0, "yield_total": yt, "spread": yt - r_now}


# A price more than this far below the reported trust is not left open by the
# funds that hold SPACs unless the redemption right is gone (a deal vote has
# passed) or the trust figure is wrong. It is a REPORTING screen: such rows are
# itemised and kept out of the capacity sums, never silently dropped. It was
# set on 2026-10-18 AFTER the extreme rows had been seen, so `gap_screen_band`
# in the summary reports the range of screens that select exactly the same
# rows: a result that moves inside that band would be a choice, not a finding.
GAP_SCREEN = 0.05
MERGER_PROXY_FORMS = frozenset({"DEFM14A", "DEFM14C"})


# ------------------------------------------------------------------ Alpaca

def alpaca_kind(name: str) -> str:
    """unit | warrant | right | share, from an Alpaca asset name."""
    u = (name or "").upper()
    if re.search(r"\bUNITS?\b", u):
        return "unit"
    if re.search(r"\bWARRANTS?\b|\bWTS?\b", u):
        return "warrant"
    if re.search(r"\bRIGHTS?\b", u):
        return "right"
    return "share"


def common_symbol(tickers: list[str], assets: dict) -> dict | None:
    """The Alpaca asset that is the SPAC's common share, from the CIK's EDGAR tickers.

    `assets` maps symbol -> asset dict (name, exchange, tradable, ...). The
    common is the one ticker whose Alpaca name reads as a share, not a unit,
    warrant or right. Two such tickers (a share class pair) -> the tradable
    one, then the shorter symbol; that choice is recorded as `n_share_tickers`.
    """
    shares = [assets[t] | {"symbol": t} for t in tickers if t in assets and alpaca_kind(assets[t].get("name")) == "share"]
    if not shares:
        return None
    shares.sort(key=lambda a: (not a.get("tradable"), len(a["symbol"]), a["symbol"]))
    return shares[0] | {"n_share_tickers": len(shares)}


# ------------------------------------------------------------------ sampling

SAMPLE_SALT = "spac-census-2026-10-15"


def declared_order(ciks) -> list[int]:
    """CIKs ordered by sha256(SAMPLE_SALT:cik): the declared, content-blind sampling order."""
    return sorted((int(c) for c in ciks), key=lambda c: hashlib.sha256(f"{SAMPLE_SALT}:{c}".encode()).hexdigest())


# ------------------------------------------------------------------ EDGAR documents

_DOC_RE = re.compile(r"^[A-Za-z0-9._-]+\.(?:htm|html|txt)$")


def filing_doc_url(cik, accession: str, primary: str) -> str:
    """The primary document of one filing (smaller than the complete-submission .txt).

    Validated like `edgar_client.filing_txt_url`, for the same reason: a
    malformed archive path is answered with HTTP 403, which the client reads
    as throttling and backs off on for twelve minutes.
    """
    from scripts.data.edgar_client import filing_txt_url
    base = filing_txt_url(cik, accession).rsplit("/", 1)[0]   # validates cik and accession
    if not isinstance(primary, str) or not _DOC_RE.match(primary):
        raise ValueError(f"not a primary-document name: {primary!r}")
    return f"{base}/{primary}"


def fetch_doc(client, cik: int, accession: str, primary: str) -> str:
    """Plain text of a filing's primary document (cache first)."""
    return plain(client.get_text(filing_doc_url(int(cik), accession, primary)))


SPAC_PROSPECTUS_RE = re.compile(r"trust account", re.I)
BUSINESS_COMBINATION_RE = re.compile(r"business (?:combination|transaction)", re.I)
IPO_RE = re.compile(r"initial public offering", re.I)
COVER_CHARS = 25_000


def prospectus_flags(t: str) -> dict:
    """The counts behind `is_spac_prospectus`, kept so the rule can be audited per CIK."""
    cover = t[:COVER_CHARS]
    return {"n_trust": len(SPAC_PROSPECTUS_RE.findall(t)), "n_bc": len(BUSINESS_COMBINATION_RE.findall(t)),
            "cover_trust": bool(SPAC_PROSPECTUS_RE.search(cover)), "cover_ipo": bool(IPO_RE.search(cover))}


def is_spac_prospectus(t: str) -> bool:
    """A 424B4 that is a SPAC's IPO prospectus.

    Its cover (the first COVER_CHARS characters of plain text) names an initial
    public offering AND a trust account, and the body speaks of the trust
    account and of a business combination (or "business transaction", the
    wording of some BVI SPACs) at least five times each. Measured on the
    2026-10-15 candidates: operating-company prospectuses that reverse-merged
    into a shell later (Oruka, LENZ, Jade, ...) mention a trust account zero
    times; an operating company's resale prospectus after its de-SPAC can
    mention the SPAC's trust account in the body but not on its cover.
    """
    f = prospectus_flags(t)
    return f["cover_trust"] and f["cover_ipo"] and f["n_trust"] >= 5 and f["n_bc"] >= 5


# ------------------------------------------------------------------ trust per share from a 10-Q

# "23,000,000 shares at redemption value of $10.45 per share" and the two-period
# form "... at redemption value of $10.45 and $10.21 per share as of September
# 30, 2026 and December 31, 2025, respectively": the FIRST figure is the
# report's own balance-sheet date (a 10-Q prints the current period first).
#
# Widened 2026-10-18 after three misses measured on the live 10-Qs, each of
# which left the headline on an XBRL share count that was wrong:
#   "... of $ 10.02 and $ 0 per share" (a first 10-Q: the prior period is $0;
#       InterPrivate V, CIK 2105274; SUMA, CIK 2105838);
#   "25,800,000 shares at $ 10.60 and $ 10.42 per share redemption value" (BEAG);
#   "at redemption value of $ 12.00 and $ 11.63 as of June 30, 2026" (no "per share").
_PRIOR_VALUE = r"(?:\s+and\s+\$?\s?\d{1,2}(?:\.\d{1,4})?)?"
REDEMPTION_VALUE_RE = re.compile(
    r"redemption\s+value\s+(?:of\s+)?(?:approximately\s+)?\$\s?(\d{1,2}\.\d{2,4})" + _PRIOR_VALUE +
    r"(?:\s+per\s+share|(?=\s*,?\s+(?:as\s+of|at)\s+(?:" + _MONTHS + r")))", re.I)
REDEMPTION_VALUE_AFTER_RE = re.compile(
    r"\bat\s+\$\s?(\d{1,2}\.\d{2,4})" + _PRIOR_VALUE + r"\s+per\s+share\s+redemption\s+value", re.I)
# "46,000,000 shares at redemption value", "25,300,000 shares issued and
# outstanding subject to possible redemption" (both measured, 2026-10-15), and
# the first-10-Q forms "20,125,000 and no shares at redemption value" and
# "17,250,000 shares and no shares at a redemption value" (2026-10-18).
# Not a table row: "... Accretion ... 19,746,129 Class A ordinary shares subject
# to possible redemption, June 30, 2026 $ 230,178,997" (WLCO, 2026-10-18) is a
# dollar amount followed by the next row's label, hence the date lookahead.
REDEEMABLE_SHARES_RE = re.compile(
    r"([\d,]{6,})(?:\s+and\s+(?:none|no|[\d,]+))?\s+(?:class\s+a\s+)?(?:ordinary\s+|common\s+)?shares\s+"
    r"(?:and\s+(?:none|no|[\d,]+)\s+shares\s+)?(?:issued\s+and\s+outstanding\s+)?"
    r"(?:(?:subject\s+to\s+possible\s+redemption\s*,?\s*)?at\s+(?:a\s+)?(?:\$\s?\d{1,2}\.\d{2,4}" + _PRIOR_VALUE +
    r"\s+per\s+share\s+)?redemption\s+value"
    r"|subject\s+to\s+possible\s+redemption(?!\s*,?\s*(?:" + _MONTHS + r")\s+\d))",
    re.I)
IPO_CLOSE_RE = re.compile(
    r"On\s+(" + _MONTHS + r")\s+(\d{1,2}),?\s+(20\d\d),?\s+(?:the\s+Company|we)\s+consummated\s+(?:the|its|our)\s+"
    r"(?:Initial\s+Public\s+Offering|initial\s+public\s+offering|IPO)", re.I)


def ipo_close_date(t: str) -> date | None:
    """'On October 1, 2025, the Company consummated the Initial Public Offering' -> 2025-10-01 (modal)."""
    ds = []
    for m in IPO_CLOSE_RE.finditer(t):
        try:
            ds.append(parse_date(m))
        except ValueError:
            continue
    if not ds:
        return None
    return pd.Series(ds).value_counts().index[0]


MONTHS_FROM_CLOSE_RE = re.compile(
    r"(\d{1,2})\s+months\s+from\s+the\s+(?:closing|consummation)\s+of\s+(?:the|its|our|this)\s+"
    r"(?:Initial\s+Public\s+Offering|initial\s+public\s+offering|IPO|offering)", re.I)


def months_from_close(t: str) -> list[int]:
    """Every 'N months from the closing of the Initial Public Offering' in a 10-Q, 6..48 only."""
    return [int(x) for x in MONTHS_FROM_CLOSE_RE.findall(t) if 6 <= int(x) <= 48]


def text_redemption_value(t: str, lo: float = 9.0, hi: float = 13.0) -> list[float]:
    """Per-share redemption values printed beside the temporary-equity line, in order of appearance."""
    hits = [(m.start(), m.group(1)) for rx in (REDEMPTION_VALUE_RE, REDEMPTION_VALUE_AFTER_RE) for m in rx.finditer(t)]
    return [float(x) for _, x in sorted(hits) if lo <= float(x) <= hi]


def text_redeemable_shares(t: str) -> list[int]:
    """Share counts printed as '<n> shares at redemption value', in order of appearance."""
    out = []
    for x in REDEEMABLE_SHARES_RE.findall(t):
        n = int(x.replace(",", ""))
        if n >= 100_000:
            out.append(n)
    return out


TRUST_AT_IPO_RE = re.compile(
    r"\$\s?(\d{1,2}\.\d{2,3})\s+per\s+(?:unit|share|public\s+share|class\s+a\s+(?:ordinary|common)\s+share)", re.I)


def trust_per_unit_at_ipo(prospectus: str) -> float | None:
    """The amount per unit (or share) the prospectus places in trust: the modal $9-$11.50 figure
    quoted within 300 characters of 'trust account'. None if no such figure is quoted."""
    vals = []
    for m in SPAC_PROSPECTUS_RE.finditer(prospectus):
        win = prospectus[max(0, m.start() - 300): m.end() + 300]
        vals += [float(x) for x in TRUST_AT_IPO_RE.findall(win) if 9.0 <= float(x) <= 11.5]
    if not vals:
        return None
    vc = pd.Series(vals).value_counts()
    return float(vc.index[0])


# ------------------------------------------------------------------ CRSP link (historical)

_ABBR = {"ACQUISITION": "ACQ", "ACQUISITIONS": "ACQ", "CORPORATION": "CORP", "COMPANY": "CO",
         "LIMITED": "LTD", "INCORPORATED": "INC", "INTERNATIONAL": "INTL", "HOLDINGS": "HLDGS",
         "HOLDING": "HLDG", "TECHNOLOGY": "TECH", "TECHNOLOGIES": "TECH", "CAPITAL": "CAP",
         "PARTNERS": "PTNRS", "GROUP": "GRP", "OPPORTUNITY": "OPP", "OPPORTUNITIES": "OPP",
         "GLOBAL": "GLBL", "AMERICA": "AMER", "AMERICAN": "AMER", "ENERGY": "ENRGY", "I": "1",
         "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6", "VII": "7", "VIII": "8", "IX": "9", "X": "10"}
_STOP = {"THE", "INC", "CORP", "CO", "LTD", "LLC", "PLC", "NEW", "DE", "CAYMAN", "ISLANDS", "BVI"}


def norm_name(s: str) -> tuple[str, ...]:
    """Tokens of a company name after the abbreviations CRSP uses, without legal suffixes."""
    s = (s or "").upper().replace("&", " AND ")
    s = re.sub(r"/[A-Z]{2}/?$", " ", s)            # EDGAR's state suffix, e.g. /DE/
    raw = re.findall(r"[A-Z0-9]+", s)
    # CRSP spells initials apart ("C F FINANCE ACQUISITION CORP", "T P G PACE"):
    # a run of single letters is joined back into one token before comparing.
    toks, run = [], ""
    for t in raw:
        if len(t) == 1 and t.isalpha():
            run += t
            continue
        if run:
            toks.append(run)
            run = ""
        toks.append(t)
    if run:
        toks.append(run)
    toks = [_ABBR.get(t, t) for t in toks]
    return tuple(t for t in toks if t not in _STOP)


def name_score(a: str, b: str) -> float:
    """Similarity of two names in [0, 1]: token-set overlap, CRSP truncation allowed.

    CRSP truncates long names, so a token of one name that is a prefix of a
    token of the other counts as a match (ACQ vs ACQUISITION is already
    folded by `norm_name`; 'DECARBONIZATION PL' vs 'PLUS' needs this).
    """
    ta, tb = norm_name(a), norm_name(b)
    if not ta or not tb:
        return 0.0
    def hit(t, other):
        return any(o == t or (len(t) >= 2 and (o.startswith(t) or t.startswith(o)) and len(o) >= 2) for o in other)
    m = sum(hit(t, tb) for t in ta) + sum(hit(t, ta) for t in tb)
    return m / (len(ta) + len(tb))


LINK_MIN_SCORE = 0.75
COMMON_SHRCD = (10, 11, 12)
LINK_WINDOW_DAYS = (-10, 150)   # the common starts trading at the IPO or when units separate (~52 days)


def link_crsp(spacs: pd.DataFrame, names: pd.DataFrame) -> pd.DataFrame:
    """EDGAR SPAC (cik, ipo_date, ipo_name) -> CRSP permno of its common, or no link.

    `names` is CRSP dsenames (permno, namedt, comnam, shrcd). A permno is a
    candidate if its FIRST name record starts within LINK_WINDOW_DAYS of the
    IPO; the candidate with the best `name_score` is taken if it scores at
    least LINK_MIN_SCORE and no other candidate ties it. Unlinked SPACs are
    reported as such, never matched on a looser rule.
    """
    first = names.sort_values("namedt").groupby("permno").first().reset_index()
    first["namedt"] = pd.to_datetime(first["namedt"])
    # Ordinary shares only (CRSP share codes 10-12): a unit (7x) carries the same
    # name and would otherwise tie with, or replace, the common.
    first = first[first["shrcd"].isin(COMMON_SHRCD)]
    rows = []
    for r in spacs.itertuples():
        ipo = pd.Timestamp(r.ipo_date)
        lo, hi = ipo + pd.Timedelta(days=LINK_WINDOW_DAYS[0]), ipo + pd.Timedelta(days=LINK_WINDOW_DAYS[1])
        cand = first[(first["namedt"] >= lo) & (first["namedt"] <= hi)]
        best, second, best_p, best_nm = 0.0, 0.0, None, None
        for c in cand.itertuples():
            s = name_score(r.ipo_name, c.comnam)
            if s > best:
                best, second, best_p, best_nm = s, best, int(c.permno), c.comnam
            elif s > second:
                second = s
        ok = best >= LINK_MIN_SCORE and best > second
        rows.append({"cik": r.cik, "permno": best_p if ok else None, "crsp_name": best_nm if ok else None,
                     "link_score": round(best, 3), "runner_up": round(second, 3)})
    return pd.DataFrame(rows)


def fixed_point(ipo: date, base_months: int, before_months: int = 3) -> date:
    """IPO date + base window - `before_months`: the historical measurement date."""
    return (pd.Timestamp(ipo) + pd.DateOffset(months=base_months - before_months)).date()


# ------------------------------------------------------------------ quote verification

def normalise(s: str) -> str:
    """The form in which a quote is matched against a filing (as the tender census does)."""
    s = plain(s).casefold()
    s = s.translate(str.maketrans({"’": "'", "‘": "'", "`": "'", "“": '"', "”": '"',
                                   "–": "-", "—": "-", "\xa0": " "}))
    s = re.sub(r"(?<=\d)\s+%", "%", s)
    return re.sub(r"\s+", " ", s)


def quote_in(doc: str, quote: str) -> bool:
    """True if `quote` occurs in `doc` after `normalise` on both. An empty quote raises."""
    if not quote or not quote.strip():
        raise ValueError("empty quote")
    return normalise(quote) in normalise(doc)


# ------------------------------------------------------------------ CRSP access (R2, read-only)

CRSP_NAMES_CACHE = CACHE / "crsp_dsenames_2014plus.parquet"
CRSP_PX_CACHE = CACHE / "crsp_spac_px.parquet"
CRSP_START = date(2014, 1, 1)
CRSP_END = date(2022, 12, 31)    # the time holdout starts 2023-01-01: no CRSP row after this is read


def crsp_names(offline: bool) -> pd.DataFrame:
    """CRSP dsenames rows alive on or after 2014 (permno, names, share codes). Cached; licensed."""
    if CRSP_NAMES_CACHE.exists():
        return pd.read_parquet(CRSP_NAMES_CACHE)
    if offline:
        raise CensusError(f"offline and {CRSP_NAMES_CACHE} is not cached")
    from src.data import r2
    con = r2.connect()
    df = r2.q(con, f"""SELECT permno, permco, namedt, nameendt, shrcd, exchcd, siccd, ncusip, ticker, comnam,
                              shrcls, primexch, secstat, trdstat
                       FROM read_parquet('{r2.r2_path("crsp_a_stock", "dsenames")}')
                       WHERE nameendt >= DATE '{CRSP_START}'""")
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CRSP_NAMES_CACHE)
    return df


def crsp_prices(permnos, offline: bool) -> pd.DataFrame:
    """CRSP daily prc/vol/bid/ask for `permnos`, CRSP_START..CRSP_END (never past the holdout)."""
    want = sorted({int(p) for p in permnos})
    if CRSP_PX_CACHE.exists():
        px = pd.read_parquet(CRSP_PX_CACHE)
        if set(want) <= set(px["permno"].unique()) | set(px.attrs.get("empty_permnos", [])):
            return px[px["permno"].isin(want)]
    if offline:
        raise CensusError(f"offline and {CRSP_PX_CACHE} lacks some of {len(want)} permnos")
    from src.data import r2
    con = r2.connect()
    con.register("pp", pd.DataFrame({"permno": want}))
    px = r2.q(con, f"""SELECT d.permno, d.date, CAST(d.prc AS DOUBLE) AS prc, CAST(d.vol AS DOUBLE) AS vol,
                              CAST(d.bid AS DOUBLE) AS bid, CAST(d.ask AS DOUBLE) AS ask
                       FROM read_parquet('{r2.r2_path("crsp_a_stock", "dsf")}') d JOIN pp USING (permno)
                       WHERE d.date BETWEEN DATE '{CRSP_START}' AND DATE '{CRSP_END}'""")
    if len(px) and pd.to_datetime(px["date"]).max() > pd.Timestamp(CRSP_END):
        raise CensusError("a CRSP row past the holdout start was returned")
    CACHE.mkdir(parents=True, exist_ok=True)
    px.to_parquet(CRSP_PX_CACHE)
    return px


# ------------------------------------------------------------------ Alpaca (read-only GETs)

ASSET_FIELDS = ("symbol", "name", "exchange", "status", "tradable", "fractionable", "shortable",
                "easy_to_borrow", "marginable", "attributes")
BARS_LOOKBACK_DAYS = 120          # covers the 63 sessions the ADV is measured over
ADV_SESSIONS = 63


def alpaca_client():
    from quantt.broker.alpaca import AlpacaClient
    return AlpacaClient.from_environment("cef")


def alpaca_assets(asof: str, offline: bool) -> dict:
    """Every active us_equity asset WITH its name, cached as one JSON per day.

    `AlpacaClient.assets()` drops `name`, which this census needs to tell a
    SPAC's common from its units, warrants and rights; so the same read-only
    GET /v2/assets is issued through the client's `_get` (retry, scrubbed
    errors, paper base URL only) and the fields above are kept.
    """
    p = CACHE / f"alpaca_assets_active_{asof}.json"
    if p.exists():
        return json.loads(p.read_text())
    if offline:
        raise CensusError(f"offline and {p.name} is not cached")
    from quantt.broker.alpaca import PAPER_BASE
    c = alpaca_client()
    raw = c._get(PAPER_BASE, "/v2/assets", {"status": "active", "asset_class": "us_equity"})
    if not isinstance(raw, list) or not raw:
        raise CensusError("GET /v2/assets returned no list")
    out = {}
    for a in raw:
        if a["symbol"] in out:
            raise CensusError(f"GET /v2/assets lists {a['symbol']} twice")
        out[a["symbol"]] = {k: a.get(k) for k in ASSET_FIELDS}
    snap = {"read_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "assets": out}
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snap, sort_keys=True))
    return snap


def alpaca_bars(symbols, start: date, end: date, asof: str, offline: bool) -> pd.DataFrame:
    """Daily SIP bars (raw) for `symbols`, start..end, cached per as-of date. One row per (symbol, day)."""
    p = CACHE / f"alpaca_bars_{asof}.parquet"
    req = CACHE / f"alpaca_bars_{asof}.requested.json"   # a symbol with no bar at all is still "asked"
    want = sorted(set(symbols))
    if p.exists() and req.exists():
        if set(want) <= set(json.loads(req.read_text())):
            df = pd.read_parquet(p)
            return df[df["symbol"].isin(want)]
    if offline:
        raise CensusError(f"offline and {p.name} is not cached for all symbols")
    from scripts.rv.alpaca_daily import _paged, NY
    c = alpaca_client()
    rows = []
    for i in range(0, len(want), 100):
        chunk = want[i:i + 100]
        params = {"symbols": ",".join(chunk), "timeframe": "1Day", "feed": "sip", "adjustment": "raw",
                  "start": datetime(start.year, start.month, start.day, 0, tzinfo=NY).isoformat(),
                  "end": datetime(end.year, end.month, end.day, 20, tzinfo=NY).isoformat(), "limit": 10000}
        for page in _paged(c, "/v2/stocks/bars", params, "bars"):
            for sym, bars in page.items():
                if sym not in chunk:
                    raise CensusError(f"bars for unrequested symbol {sym}")
                for b in bars:
                    miss = [k for k in ("t", "c", "v") if b.get(k) is None]
                    if miss:
                        raise CensusError(f"bar {sym} {b.get('t')} lacks {miss}")
                    ts = pd.Timestamp(b["t"]).tz_convert(NY)
                    rows.append({"symbol": sym, "date": ts.normalize().tz_localize(None), "o": b.get("o"),
                                 "h": b.get("h"), "l": b.get("l"), "c": float(b["c"]), "v": float(b["v"]),
                                 "vw": b.get("vw"), "n": b.get("n")})
    df = pd.DataFrame(rows, columns=["symbol", "date", "o", "h", "l", "c", "v", "vw", "n"])
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)
    req.write_text(json.dumps(want))
    return df


def alpaca_sessions(start: date, end: date, offline: bool, asof: str) -> list:
    """NYSE sessions from Alpaca's own calendar (GET /v2/calendar), cached per as-of date."""
    p = CACHE / f"alpaca_calendar_{asof}.json"
    if p.exists():
        return [pd.Timestamp(d) for d in json.loads(p.read_text())]
    if offline:
        raise CensusError(f"offline and {p.name} is not cached")
    cal = alpaca_client().calendar(start, end)
    days = sorted(str(r["date"]) for r in cal)
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(days))
    return [pd.Timestamp(d) for d in days]


def liquidity(bars: pd.DataFrame, sessions: list, n: int = ADV_SESSIONS) -> pd.DataFrame:
    """Per symbol over the last `n` sessions: last close, ADV in dollars and shares, sessions traded.

    A session with no bar is a session in which no trade printed (Alpaca sends
    no bar then), so it adds ZERO volume: the ADV is total dollar volume over
    the `n` sessions divided by `n`, not by the sessions that traded. Both the
    mean and the median of daily dollar volume (zeros included) are reported,
    with `sessions_traded` beside them so a thin name is visible as thin.
    """
    win = sorted(sessions)[-n:]
    if len(win) < n:
        raise CensusError(f"only {len(win)} sessions in the calendar window, need {n}")
    b = bars[bars["date"].isin(win)].copy()
    off = bars[~bars["date"].isin(sessions) & (bars["date"] >= win[0])]
    if len(off):
        raise CensusError(f"{len(off)} bars on non-sessions, e.g. {off.iloc[0].to_dict()}")
    b["dv"] = b["c"] * b["v"]
    out = []
    for sym, g in b.groupby("symbol"):
        dv = g.set_index("date")["dv"].reindex(win, fill_value=0.0)
        sh = g.set_index("date")["v"].reindex(win, fill_value=0.0)
        last = g.sort_values("date").iloc[-1]
        out.append({"symbol": sym, "last_close": float(last["c"]), "last_bar_date": last["date"].date(),
                    "adv_usd_mean": float(dv.mean()), "adv_usd_median": float(dv.median()),
                    "adv_shares_mean": float(sh.mean()), "sessions_traded": int((sh > 0).sum()), "window": n})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ historical levels (pre-2023)

FIXED_POINTS_MONTHS = (6, 3, 1)   # months before the base deadline; 3 is the headline (the task's example)
TRUST_RATIO_BAND = (0.98, 1.10)   # V(t)/V(t1) outside this: redemptions or deposits moved the trust
FIRST_TRUST_LAG_DAYS = 45         # the over-allotment closes within 45 days of the IPO


def trust_ps_at(facts: dict, ipo: date, t0: float, when: date) -> dict:
    """Trust per share known at `when`, as T0 x V(t)/V(t1), from balance sheets FILED by `when`.

    T0 is the prospectus's per-unit trust deposit; V is assets held in trust
    (`trust_series`). t1 is the first balance-sheet date at least
    FIRST_TRUST_LAG_DAYS after the IPO (the over-allotment has closed), t the
    last balance-sheet date on or before `when`. Only facts filed on or before
    `when` are used (what the market could know then). If no public shares
    were redeemed between t1 and t the share count is unchanged and the ratio
    is pure interest; a ratio outside TRUST_RATIO_BAND means redemptions or a
    deposit changed the count or the trust, and the row is returned with
    `ok=False` rather than a number.
    """
    w = pd.Timestamp(when)
    out = {"ok": False, "why": None, "t1": None, "t": None, "ratio": None, "trust_ps": None, "xbrl_pps": None}
    if facts is None:
        out["why"] = "no_xbrl_facts"
        return out
    ts = trust_series(facts)
    known = ts[(ts["filed"] <= w) & (ts["end"] <= w)]
    known = known[known["end"] >= pd.Timestamp(ipo) + pd.Timedelta(days=FIRST_TRUST_LAG_DAYS)]
    if known.empty:
        out["why"] = "no_trust_balance_known"
        return out
    v1, vt = known.iloc[0], known.iloc[-1]
    ratio = float(vt["trust"] / v1["trust"]) if v1["trust"] > 0 else None
    out.update(t1=v1["end"].date(), t=vt["end"].date(), ratio=ratio)
    p = concept_points(facts, "TemporaryEquityRedemptionPricePerShare", "USD/shares")
    p = p[(p["end"] == vt["end"]) & (p["filed"] <= w)].sort_values("filed")
    if len(p):
        out["xbrl_pps"] = float(p["val"].iloc[-1])
    if ratio is None or not (TRUST_RATIO_BAND[0] <= ratio <= TRUST_RATIO_BAND[1]):
        out["why"] = "trust_changed"
        return out
    out.update(ok=True, trust_ps=t0 * ratio)
    return out


def price_at(px: pd.DataFrame, when: date) -> dict | None:
    """CRSP close on the last row on or before `when` (|prc|; prc < 0 is CRSP's bid/ask midpoint)."""
    g = px[(px["date"] <= pd.Timestamp(when)) & px["prc"].notna() & (px["prc"] != 0)]
    if g.empty:
        return None
    r = g.sort_values("date").iloc[-1]
    return {"px_date": r["date"].date(), "price": abs(float(r["prc"])), "traded": bool(r["prc"] > 0),
            "stale_days": (pd.Timestamp(when) - r["date"]).days}


def hist_levels(spacs: pd.DataFrame, facts_of, px: pd.DataFrame, months_before: int,
                tb: pd.Series | None = None) -> pd.DataFrame:
    """One row per SPAC alive at (base deadline - months_before), with price and trust LEVELS.

    `spacs`: cik, ipo_date, base_months, t0, permno, completion_date,
    termination_date. `facts_of(cik)` returns the companyfacts JSON. Rows whose
    measurement date is on or after HOLDOUT_START are not built at all.
    """
    rows = []
    for r in spacs.itertuples():
        if pd.isna(r.base_months) or pd.isna(r.t0) or pd.isna(r.permno):
            continue
        fp = fixed_point(r.ipo_date, int(r.base_months), months_before)
        if fp >= HOLDOUT_START or fp > CRSP_END:
            continue
        ended = [pd.Timestamp(d) for d in (r.completion_date, r.termination_date) if d is not None and not pd.isna(d)]
        if any(d <= pd.Timestamp(fp) for d in ended):
            continue   # not alive at the measurement date
        tr = trust_ps_at(facts_of(int(r.cik)), r.ipo_date, float(r.t0), fp)
        pr = price_at(px[px["permno"] == int(r.permno)], fp)
        ann = getattr(r, "announce_date", None)
        announced = bool(ann is not None and not pd.isna(ann) and pd.Timestamp(ann) <= pd.Timestamp(fp))
        row = {"cik": int(r.cik), "ipo_date": r.ipo_date, "base_months": int(r.base_months), "t0": float(r.t0),
               "months_before": months_before, "fixed_point": fp, "deal_announced": announced,
               **{f"tr_{k}": v for k, v in tr.items()}}
        if pr is not None:
            row.update(pr)
        if tr["ok"] and pr is not None:
            row["discount"] = pr["price"] / tr["trust_ps"] - 1.0
            days = (pd.Timestamp(r.ipo_date) + pd.DateOffset(months=int(r.base_months)) - pd.Timestamp(fp)).days
            row["days_to_base_deadline"] = days
            row["yield_simple"] = (tr["trust_ps"] / pr["price"] - 1.0) * 365.0 / days
            if tb is not None:   # the labelled accrual model, with bill rates known by the fixed point only
                dl = (pd.Timestamp(r.ipo_date) + pd.DateOffset(months=int(r.base_months))).date()
                a = accrued_terms(pr["price"], tr["trust_ps"], tr["t"], fp, dl, tb)
                row.update(discount_accrued=a["discount_accrued"], spread=a["spread"], tbill_now=a["tbill_now"])
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ external benchmark (Ritter)

RITTER_URL = "https://site.warrington.ufl.edu/ritter/files/IPOs-SPACs.pdf"
_RITTER_YEAR_RE = re.compile(r"^\s*(19\d\d|20\d\d)\s+[\d,]+\s+-?[\d.]+%\s+(\d+)\s+([\d,]+)\s+([\d,]+)\b", re.M)
_RITTER_Q_RE = re.compile(r"(?<!\d)([1-4])Q\s?(\d{2})\s+(\d+)\s+-?[\d.]+%")
_RITTER_DESPAC_RE = re.compile(r"^\s*(20\d\d)\s+(\d+)\s+-?[\d.]+%", re.M)


def parse_ritter(pages: list[str]) -> dict:
    """Ritter's Table 15b (SPAC IPOs by year and 2026 by quarter) and 15c (deSPACs by merger year).

    Each yearly row must satisfy non-unit + unit == total, or this raises: a
    shifted column would otherwise enter the benchmark silently.
    """
    t15b = next((p for p in pages if "Table 15b" in p and "Non-unit" in p), None)
    t15c = next((p for p in pages if "Table 15c" in p and "Post-merger Returns" in p), None)
    if t15b is None or t15c is None:
        raise CensusError("Ritter PDF: Table 15b or 15c not found")
    years = {}
    for y, nu, u, tot in _RITTER_YEAR_RE.findall(t15b):
        nu, u, tot = int(nu), int(u.replace(",", "")), int(tot.replace(",", ""))
        if nu + u != tot:
            raise CensusError(f"Ritter 15b {y}: {nu} + {u} != {tot}")
        years[int(y)] = tot
    tq = next((p for p in pages if "SPAC IPOs by Quarter" in p), "")
    quarters = {f"20{yy}Q{q}": int(n) for q, yy, n in _RITTER_Q_RE.findall(tq)}
    for y in range(2021, 2026):   # the quarters of a closed year must sum to its yearly total
        qs = [quarters.get(f"{y}Q{q}") for q in range(1, 5)]
        if all(v is not None for v in qs) and y in years and sum(qs) != years[y]:
            raise CensusError(f"Ritter {y}: quarters sum {sum(qs)} != yearly {years[y]}")
    body = t15c.split("Average 1-year Return")[-1] if "Average 1-year Return" in t15c else t15c
    despac = {int(y): int(n) for y, n in _RITTER_DESPAC_RE.findall(body)}
    if not years or not despac:
        raise CensusError("Ritter PDF: no rows parsed")
    return {"spac_ipos_by_year": years, "spac_ipos_by_quarter": quarters, "despacs_by_year": despac}


def ritter_benchmark(offline: bool) -> dict:
    """Fetch (cached) and parse Ritter's SPAC IPO tables; the PDF's own 'updated' date is kept."""
    p = CACHE / "ritter_IPOs-SPACs.pdf"
    if not p.exists():
        if offline:
            raise CensusError(f"offline and {p.name} is not cached")
        import urllib.request
        req = urllib.request.Request(RITTER_URL, headers={"User-Agent": "Mozilla/5.0 (research census)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
        if not body.startswith(b"%PDF"):
            raise CensusError("Ritter URL did not return a PDF")
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
    from pypdf import PdfReader
    pages = [pg.extract_text() or "" for pg in PdfReader(str(p)).pages]
    out = parse_ritter(pages)
    m = re.search(r"Table 15b \(updated ([A-Za-z]+ \d{1,2}, \d{4})\)", "\n".join(pages))
    out["table_15b_updated"] = m.group(1) if m else None
    out["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    out["url"] = RITTER_URL
    return out


# ------------------------------------------------------------------ live terms

TRUST_PS_RANGE = (9.5, 13.0)       # a per-share trust outside this is a parse error, not a SPAC
TRUST_PS_DISAGREE = 0.01           # sources more than 1% apart are flagged, never averaged


def _mode_min(xs):
    vc = pd.Series(xs).value_counts()
    return int(min(vc[vc == vc.max()].index))


def pick_trust_ps(cands: dict, counts: list, amount: float | None) -> tuple[float | None, str | None]:
    """The headline trust per share of a live SPAC, by the balance-sheet identity.

    A 10-Q prints the temporary-equity line as N shares at P per share = A.
    Measured 2026-10-18, each single source fails somewhere: the share count
    (XBRL, or a loose text match) can be another number (WLCO: 19,746,129, an
    accretion amount, against 23,000,000 printed on the line), the printed P
    can be a label ("$10.00 per share" beside an amount that is $10.23 a share;
    CRAC) or the PRIOR period printed first (MMTX). So, with A the XBRL carrying
    amount (or the trust balance when the carry is not tagged) and `counts`
    every share count read (the text's, then XBRL's):
      1. the printed P, if N x P is within TRUST_PS_DISAGREE of A for some N
                                                  -> "pps_text_checked";
      2. else the XBRL per-share price, on the same test -> "pps_xbrl_checked";
      3. else A over the first printed count     -> "amount_over_text_shares";
      4. else the first available of pps_text, pps_xbrl, carry_ps, trust_ps,
         labelled "<source>_unchecked".
    Returns (None, None) if there is no candidate.
    """
    ns = [float(n) for n in counts if n]
    for k in ("pps_text", "pps_xbrl"):
        p = cands.get(k)
        if p is not None and amount and any(abs(n * p / amount - 1.0) <= TRUST_PS_DISAGREE for n in ns):
            return p, f"{k}_checked"
    if "amount_text_ps" in cands:
        return cands["amount_text_ps"], "amount_over_text_shares"
    for k in ("pps_text", "pps_xbrl", "carry_ps", "trust_ps"):
        if k in cands:
            return cands[k], f"{k}_unchecked"
    return None, None


def live_terms(doc: str, period_end: date, ipo_date: date, facts: dict | None, t0: float | None,
               prospectus_months: list[int], ext_texts: list[str], asof: date) -> dict:
    """Trust per share and deadlines of one live SPAC from its latest 10-Q/10-K (plain text).

    Trust per share, every source kept in `trust_ps_sources`:
      pps_text      the per-share redemption value printed beside temporary equity;
      amount_text_ps XBRL TemporaryEquityCarryingAmountAttributableToParent (else
                    the XBRL trust balance) / the text's first share count;
      carry_ps      the same amount / XBRL TemporaryEquitySharesOutstanding;
      trust_ps      XBRL assets held in trust / XBRL shares;
      pps_xbrl      XBRL TemporaryEquityRedemptionPricePerShare;
      t0            the prospectus's per-unit trust deposit, used ONLY when the
                    report's balance sheet predates the IPO (no trust yet), and
                    labelled: it omits interest since the IPO (conservative).
    The headline is chosen by `pick_trust_ps` (the balance-sheet identity).
    Sources more than TRUST_PS_DISAGREE apart are flagged in `trust_ps_spread`.

    Deadlines: the IPO closing date from the report ("On <date>, the Company
    consummated the Initial Public Offering"), else the 424B4 date (flagged);
    plus every "N months from the closing" (base = the modal N, max = the
    largest), else the prospectus's; plus every dated deadline in a
    business-combination sentence of the report or of a text-confirmed
    extension 8-K. deadline_max is the latest date any source allows
    (conservative for a yield); deadline_next the earliest still after `asof`.
    """
    out = {}
    pe = pd.Timestamp(period_end)
    pre_ipo = pe < pd.Timestamp(ipo_date)
    sh_text = text_redeemable_shares(doc)
    pps_text = text_redemption_value(doc)
    xb = {"trust": None, "carry": None, "shares": None, "pps": None}
    if facts is not None:
        ts = trust_series(facts)
        hit = ts[ts["end"] == pe]
        xb["trust"] = float(hit["trust"].iloc[0]) if len(hit) else None
        xb["carry"] = latest_point(facts, "TemporaryEquityCarryingAmountAttributableToParent", "USD", pe)
        xb["shares"] = latest_point(facts, "TemporaryEquitySharesOutstanding", "shares", pe)
        xb["pps"] = latest_point(facts, "TemporaryEquityRedemptionPricePerShare", "USD/shares", pe)
    n_text = float(sh_text[0]) if sh_text else None
    shares = n_text or xb["shares"]
    amount = xb["carry"] or xb["trust"]
    cands = {}
    if not pre_ipo:
        if pps_text:
            cands["pps_text"] = pps_text[0]
        if n_text and amount:
            cands["amount_text_ps"] = amount / n_text
        if xb["shares"] and xb["carry"]:
            cands["carry_ps"] = xb["carry"] / xb["shares"]
        if xb["shares"] and xb["trust"]:
            cands["trust_ps"] = xb["trust"] / xb["shares"]
        if xb["pps"]:
            cands["pps_xbrl"] = xb["pps"]
    cands = {k: v for k, v in cands.items() if TRUST_PS_RANGE[0] <= v <= TRUST_PS_RANGE[1]}
    v, src = pick_trust_ps(cands, sh_text[:3] + [xb["shares"]], None if pre_ipo else amount)
    if v is not None:
        out.update(trust_ps=v, trust_ps_source=src)
    elif t0 is not None:
        out.update(trust_ps=t0, trust_ps_source="prospectus_t0")
    else:
        out.update(trust_ps=None, trust_ps_source=None)
    out["trust_ps_spread"] = (max(cands.values()) / min(cands.values()) - 1.0) if len(cands) > 1 else None
    out["trust_ps_sources"] = ";".join(f"{k}={v:.4f}" for k, v in cands.items())
    out["redeemable_shares"] = shares
    out["balance_sheet_date"] = period_end
    out["pre_ipo_balance_sheet"] = pre_ipo
    # deadlines
    close = ipo_close_date(doc)
    out["ipo_close"] = close or ipo_date
    out["ipo_close_source"] = "10q_text" if close else "424b4_date"
    ms = months_from_close(doc) or [m for m in prospectus_months if 6 <= m <= 48]
    dates = set(deadline_candidates(doc, period_end))
    for et in ext_texts:
        dates |= set(deadline_candidates(et, ipo_date))
    base_d = max_d = None
    if ms:
        out["months_base"], out["months_max"] = _mode_min(ms), max(ms)
        base_d = (pd.Timestamp(out["ipo_close"]) + pd.DateOffset(months=out["months_base"])).date()
        max_d = (pd.Timestamp(out["ipo_close"]) + pd.DateOffset(months=out["months_max"])).date()
    allc = sorted({d for d in (base_d, max_d) if d} | dates)
    out["deadline_max"] = allc[-1] if allc else None
    fut = [d for d in allc if d > asof]
    out["deadline_next"] = fut[0] if fut else None
    out["n_dated_deadlines"] = len(dates)
    out["beyond_36m"] = bool(out["deadline_max"] and
                             out["deadline_max"] > (pd.Timestamp(out["ipo_close"]) + pd.DateOffset(months=36)).date())
    return out


# ------------------------------------------------------------------ the build

INDEX_START = date(2014, 1, 1)
NAME_NET_RE = re.compile(
    r"ACQUISITION|ACQ\b|MERGER|\bSPAC\b|BLANK CHECK|CAPITAL CORP|HOLDINGS CORP|GROWTH CORP|OPPORTUNIT|PARTNERS CORP"
    r"|TECHNOLOGY CORP|HOLDINGS LTD|INVESTMENT CORP|VENTURES CORP|CAPITAL PARTNERS|TRUST CORP", re.I)
ZIP_MAX_AGE_S = 7 * DAY


def _zip(client, url: str) -> zipfile.ZipFile:
    from scripts.data.edgar_client import cache_path
    client.get(url, max_age_s=None if client.offline else ZIP_MAX_AGE_S)   # one request, cached
    return zipfile.ZipFile(cache_path(url, client.cache))


def sic_6770_ciks(client) -> list[int]:
    out, start = [], 0
    while True:
        page = parse_sic_browse(client.get_text(SIC_BROWSE_URL.format(start=start),
                                                max_age_s=None if client.offline else 2 * DAY))
        out += page
        if len(page) < 100:
            return sorted(set(out))
        start += 100
        if start > 50_000:
            raise CensusError("SIC browse did not end")


def ipo_index(client, today: date) -> pd.DataFrame:
    """Every 424B4 in the quarterly full indexes from INDEX_START (cik, company-at-filing, date, accession)."""
    from scripts.data import fetch_edgar_events as fe
    frames = []
    for y, q in fe.quarters(INDEX_START, today):
        url = fe.INDEX_URL.format(y=y, q=q)
        text = client.get_text(url, max_age_s=None if (client.offline or fe.quarter_is_closed(y, q, today)) else DAY)
        frames.append(fe.parse_master_index(text, label=f"{y}Q{q}", keep_forms={IPO_FORM}))
    return pd.concat(frames, ignore_index=True)


def load_submissions(client, ciks) -> tuple[pd.DataFrame, dict]:
    """Filing lists and entity metadata for `ciks`, from the bulk archive (API for any CIK it lacks)."""
    z = _zip(client, SUBMISSIONS_ZIP_URL)
    names = set(z.namelist())
    frames, meta = [], {}
    for cik in sorted(set(int(c) for c in ciks)):
        fn = f"CIK{cik:010d}.json"
        if fn in names:
            j = json.loads(z.read(fn))
            pages = [json.loads(z.read(p["name"])) for p in j["filings"].get("files", [])]
        else:
            j = client.get_json(SUBMISSIONS_URL.format(cik=cik), max_age_s=None if client.offline else 7 * DAY)
            pages = [client.get_json(f"https://data.sec.gov/submissions/{p['name']}") for p in j["filings"].get("files", [])]
        blocks = [j["filings"]["recent"]] + pages
        if not any(len(b["accessionNumber"]) for b in blocks):
            continue
        f = submissions_frame(blocks, cik)
        frames.append(f[["cik", "accessionNumber", "filingDate", "form", "items", "primaryDocument", "reportDate"]])
        meta[cik] = {k: j.get(k) for k in ("name", "sic", "tickers", "exchanges", "stateOfIncorporation", "formerNames")}
    return pd.concat(frames, ignore_index=True), meta


class Facts:
    """companyfacts JSON per CIK from the bulk archive; None if the CIK has no XBRL facts."""

    def __init__(self, client):
        self.z = _zip(client, COMPANYFACTS_ZIP_URL)
        self.names = set(self.z.namelist())
        self._c: dict = {}

    def __call__(self, cik: int):
        if cik not in self._c:
            fn = f"CIK{int(cik):010d}.json"
            self._c[cik] = json.loads(self.z.read(fn)) if fn in self.names else None
        return self._c[cik]


def xbrl_trust_signature(facts, ipo: date) -> float | None:
    """Largest trust / total assets on a balance sheet within TRUST_EVIDENCE_YEARS of the IPO."""
    if facts is None:
        return None
    ts = trust_asset_share(facts)
    ip = pd.Timestamp(ipo)
    w = ts[(ts["end"] >= ip) & (ts["end"] <= ip + pd.DateOffset(years=TRUST_EVIDENCE_YEARS))]
    return float(w["share"].max()) if len(w) else None


def build_universe(client, today: date) -> dict:
    """Candidates -> events -> SPAC test. Returns the frames the later stages need."""
    sic = sic_6770_ciks(client)
    idx = ipo_index(client, today)
    cands = set(sic) | set(idx["cik"])
    F, meta = load_submissions(client, cands)
    facts = Facts(client)
    rows = []
    for cik, g in F.groupby("cik"):
        e = spac_events(g, today)
        if e["ipo_date"] is None:
            continue
        ipo_acc = g[(g["form"] == IPO_FORM) & (g["filingDate"] == pd.Timestamp(e["ipo_date"]))]["accessionNumber"].iloc[0]
        it = g[(g["form"] == "8-K") & (g["filingDate"] >= pd.Timestamp(e["ipo_date"]))]["items"].map(items_of)
        rows.append({"cik": int(cik), **{k: v for k, v in e.items() if k != "vote_8ks"}, "vote_8ks": e["vote_8ks"],
                     "ipo_accession": ipo_acc, "sic_now": meta[cik]["sic"], "name_now": meta[cik]["name"],
                     "item_506": bool(it.map(lambda s: "5.06" in s).any()) if len(it) else False,
                     "xbrl_trust_share": xbrl_trust_signature(facts(int(cik)), e["ipo_date"])})
    ev = pd.DataFrame(rows)
    ipo_name = idx.drop_duplicates("accession").set_index("accession")["company"]
    ev["ipo_name"] = ev["ipo_accession"].map(ipo_name).fillna(ev["name_now"])
    ev["net_sic6770"] = ev["sic_now"] == "6770"
    ev["net_xbrl"] = ev["xbrl_trust_share"].fillna(0) >= TRUST_SHARE_OF_ASSETS
    ev["net_name"] = ev["ipo_name"].str.contains(NAME_NET_RE)
    ev = ev[ev["net_sic6770"] | ev["item_506"] | ev["net_xbrl"] | ev["net_name"]].copy()
    prim = F.set_index("accessionNumber")["primaryDocument"].to_dict()
    flags = []
    for r in ev.itertuples():
        t = fetch_doc(client, r.cik, r.ipo_accession, prim[r.ipo_accession])
        flags.append({"cik": r.cik, **prospectus_flags(t), "prospectus_test": is_spac_prospectus(t),
                      "base_months": base_deadline_months(t), "prospectus_months": months_from_ipo(t)[:20],
                      "t0": trust_per_unit_at_ipo(t)})
    ev = ev.merge(pd.DataFrame(flags), on="cik")
    # THE SPAC TEST (module docstring): a trust-account prospectus, confirmed
    # either by its cover or by a trust-funded XBRL balance sheet.
    ev["is_spac"] = (ev["n_trust"] >= 5) & (ev["prospectus_test"] | ev["net_xbrl"])
    return {"ev": ev, "F": F, "meta": meta, "facts": facts, "prim": prim, "n_candidates": len(cands),
            "n_sic6770": len(sic), "n_424b4_filers": int(idx["cik"].nunique())}


def text_checks(client, U: pd.DataFrame, F: pd.DataFrame, prim: dict) -> pd.DataFrame:
    """Read every pre-completion vote 8-K and every 8-K in the 120 days before a liquidation's delisting."""
    rows = []
    for r in U.itertuples():
        acc = [(a, "vote") for a in r.vote_8ks]
        if r.status == "liquidated":
            g = F[(F["cik"] == r.cik) & (F["form"] == "8-K")]
            td = pd.Timestamp(r.termination_date)
            k = g[(g["filingDate"] >= td - pd.Timedelta(days=120)) & (g["filingDate"] <= td + pd.Timedelta(days=10))]
            acc += [(a, "liq") for a in k["accessionNumber"]]
        for a, kind in acc:
            t = fetch_doc(client, r.cik, a, prim[a])
            rows.append({"cik": r.cik, "accession": a, "kind": kind, "ext": is_extension_text(t),
                         "liq": is_liquidation_text(t), "deal_vote": is_deal_vote_text(t),
                         "prices": per_share_prices(t)})
    return pd.DataFrame(rows, columns=["cik", "accession", "kind", "ext", "liq", "deal_vote", "prices"])


def live_stage(client, U: pd.DataFrame, F: pd.DataFrame, meta: dict, facts, prim: dict, K: pd.DataFrame,
               asof: date, offline: bool) -> pd.DataFrame:
    """Today's live SPACs: Alpaca listing and liquidity, trust per share, deadlines, discount and yield."""
    L = U[U["status"].isin(["live", "delisted_alive"])].copy()
    snap = alpaca_assets(asof.isoformat(), offline)
    A = snap["assets"]
    fdate = F.drop_duplicates("accessionNumber").set_index("accessionNumber")["filingDate"].dt.date
    rows = []
    for r in L.itertuples():
        m = meta[r.cik]
        cs = common_symbol(m["tickers"] or [], A)
        g = F[(F["cik"] == r.cik) & F["form"].isin(["10-Q", "10-K", "10-Q/A", "10-K/A"])
              & (F["filingDate"] >= pd.Timestamp(r.ipo_date))].sort_values("filingDate")
        row = {"cik": r.cik, "name": m["name"], "status": r.status, "ipo_date": r.ipo_date,
               "domicile": m["stateOfIncorporation"], "tickers": ";".join(m["tickers"] or []),
               "symbol": cs["symbol"] if cs else None, "exchange": cs["exchange"] if cs else None,
               "tradable": bool(cs["tradable"]) if cs else False, "fractionable": cs.get("fractionable") if cs else None,
               "announce_date": r.announce_date, "n_425": r.n_425}
        t0 = None if pd.isna(r.t0) else float(r.t0)
        bm = None if pd.isna(r.base_months) else int(r.base_months)
        ext = K[(K["cik"] == r.cik) & K["ext"]]
        row["n_extension_votes"] = int(ext["accession"].nunique())
        dv = K[(K["cik"] == r.cik) & (K["kind"] == "vote") & K["deal_vote"]]
        row["deal_vote_date"] = max((fdate[a] for a in dv["accession"]), default=None)
        mp = F[(F["cik"] == r.cik) & F["form"].isin(MERGER_PROXY_FORMS) & (F["filingDate"] >= pd.Timestamp(r.ipo_date))]
        row["merger_proxy_date"] = mp["filingDate"].max().date() if len(mp) else None
        ext_texts = [fetch_doc(client, r.cik, a, prim[a]) for a in ext["accession"].unique()]
        if len(g):
            x = g.iloc[-1]
            doc = fetch_doc(client, r.cik, x["accessionNumber"], x["primaryDocument"])
            pe = pd.Timestamp(x["reportDate"]).date() if x["reportDate"] else x["filingDate"].date()
            row.update(report_form=x["form"], report_accession=x["accessionNumber"], report_filed=x["filingDate"].date())
            row.update(live_terms(doc, pe, r.ipo_date, facts(r.cik), t0, list(r.prospectus_months), ext_texts, asof))
        else:
            # No periodic report yet: the trust is the prospectus deposit, funded at the IPO.
            close = r.ipo_date
            row.update(report_form=None, trust_ps=t0, trust_ps_source="prospectus_t0" if t0 else None,
                       ipo_close=close, ipo_close_source="424b4_date")
            if bm:
                row.update(months_base=bm, months_max=max([m for m in r.prospectus_months if 6 <= m <= 48] or [bm]))
                row["deadline_max"] = (pd.Timestamp(close) + pd.DateOffset(months=row["months_max"])).date()
                nxt = (pd.Timestamp(close) + pd.DateOffset(months=bm)).date()
                row["deadline_next"] = nxt if nxt > asof else None
        rows.append(row)
    D = pd.DataFrame(rows)
    syms = sorted(D.loc[D["tradable"], "symbol"].dropna())
    start = asof - timedelta(days=BARS_LOOKBACK_DAYS)
    sess = alpaca_sessions(start, asof, offline, asof.isoformat())
    if sess[-1].date() != asof:
        raise CensusError(f"the census date {asof} is not the last session in Alpaca's calendar")
    liq = liquidity(alpaca_bars(syms, start, asof, asof.isoformat(), offline), sess)
    D = D.merge(liq, on="symbol", how="left")
    stale_cut = sorted(sess)[-6].date()          # a close older than five sessions is not a price today
    for k in ("discount", "gain", "yield_max", "yield_next", "days_max", "days_next"):
        D[k] = np.nan
    for i, r in D.iterrows():
        if not (r.get("tradable") and pd.notna(r.get("last_close")) and pd.notna(r.get("trust_ps"))):
            continue
        if r["last_bar_date"] < stale_cut:
            continue
        D.at[i, "discount"] = r["last_close"] / r["trust_ps"] - 1.0
        D.at[i, "gain"] = r["trust_ps"] / r["last_close"] - 1.0
        for tag in ("max", "next"):
            d = r.get(f"deadline_{tag}")
            if d is not None and not (isinstance(d, float) and math.isnan(d)) and d > asof:
                y = terms_yield(r["last_close"], r["trust_ps"], asof, d)
                D.at[i, f"yield_{tag}"], D.at[i, f"days_{tag}"] = y["simple"], y["days"]
    # Interest after the balance sheet (a labelled model, never the headline).
    tb = tbill_series(offline)
    acc_cols = ("accrual_start", "tbill_past", "tbill_now", "trust_ps_accrued", "discount_accrued",
                "yield_total_next", "spread_next", "yield_total_max", "spread_max")
    for k in acc_cols:
        D[k] = None if k == "accrual_start" else np.nan
    for i, r in D.iterrows():
        if pd.isna(r.get("discount")):
            continue
        bs = r.get("balance_sheet_date")
        start = bs if (isinstance(bs, date) and not r.get("pre_ipo_balance_sheet")) else r.get("ipo_close")
        if not isinstance(start, date):
            raise CensusError(f"CIK {r['cik']}: a priced row with no accrual start date")
        D.at[i, "accrual_start"] = start
        for tag in ("next", "max"):
            d = r.get(f"deadline_{tag}")
            if not isinstance(d, date) or d <= asof:
                continue
            a = accrued_terms(r["last_close"], r["trust_ps"], start, asof, d, tb)
            D.at[i, f"yield_total_{tag}"], D.at[i, f"spread_{tag}"] = a["yield_total"], a["spread"]
            for k in ("tbill_past", "tbill_now", "trust_ps_accrued", "discount_accrued"):
                D.at[i, k] = a[k]
    D["gap_over_screen"] = D["discount"] < -GAP_SCREEN
    D["redeemable_pool"] = D["tradable"] & D["discount"].notna() & D["deal_vote_date"].isna()
    D.attrs["alpaca_read_utc"] = snap["read_utc"]
    D.attrs["tbill_last"] = (tb.index[-1].date().isoformat(), float(tb.iloc[-1]))
    return D


def hist_stage(U: pd.DataFrame, facts, offline: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pre-2023 discount-to-trust LEVELS at fixed points before the base deadline (CRSP prices)."""
    H = U[(pd.to_datetime(U["ipo_date"]) >= pd.Timestamp(CRSP_START))
          & (pd.to_datetime(U["ipo_date"]) < pd.Timestamp(HOLDOUT_START))].copy()
    names = crsp_names(offline)
    link = link_crsp(H[["cik", "ipo_date", "ipo_name"]], names)
    H = H.merge(link, on="cik", how="left")
    # A late-2022 IPO whose common first trades in 2023 (measured 2026-10-18:
    # Plutonian, AlphaVest, Horizon Space I) has no CRSP row before the
    # holdout, so it is never asked for one; its fixed points are 2023+ and
    # `hist_levels` builds no row for it anyway.
    H["crsp_first_namedt"] = H["permno"].map(pd.to_datetime(names.groupby("permno")["namedt"].min()))
    pre = H["permno"].notna() & (H["crsp_first_namedt"] < pd.Timestamp(HOLDOUT_START))
    px = crsp_prices(H.loc[pre, "permno"], offline)
    px = px.assign(date=pd.to_datetime(px["date"]))
    tb = tbill_series(offline)
    levels = pd.concat([hist_levels(H, facts, px, mb, tb) for mb in FIXED_POINTS_MONTHS], ignore_index=True)
    return H, levels


def describe(x: pd.Series) -> dict:
    x = pd.Series(x).dropna()
    if x.empty:
        return {"n": 0}
    q = x.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
    return {"n": int(len(x)), "mean": float(x.mean()), "p10": float(q[0.1]), "p25": float(q[0.25]),
            "median": float(q[0.5]), "p75": float(q[0.75]), "p90": float(q[0.9]),
            "share_below_zero": float((x < 0).mean())}


def classify_terminated(texts: dict) -> str:
    """Final status of a SPAC that delisted with no completion 8-K, from the texts of its last 8-Ks.

    `texts`: accession -> plain text (primary document, or the complete
    submission with exhibits when the primary document was not enough).
    completed_holdco  some 8-K reports holders approving, or the company
                      closing, the business combination, and none announces
                      redeeming all public shares (the deal closed into a
                      new holding company, which reports under its own CIK);
    liquidated        some 8-K announces redeeming all public shares / winding
                      up, and none reports a completed or approved deal;
    unclassified      both or neither: reported as such, never guessed.
    """
    liq = any(is_liquidation_text(t) for t in texts.values())
    comp = any(is_completion_text(t) for t in texts.values())
    if comp and not liq:
        return "completed_holdco"
    if liq and not comp:
        return "liquidated"
    return "unclassified"


# ------------------------------------------------------------------ sample, mechanics, outputs

def declared_sample(U: pd.DataFrame, K: pd.DataFrame) -> dict:
    """The reading sample, drawn by the rule declared in `spac_mechanics` (recomputed every run)."""
    # Drawn on the status the FORMS gave (`status_forms`), as it was drawn on
    # 2026-10-15 before any text was read; the text reclassification of
    # delisted SPACs came later and must not move the sample.
    sf = U["status_forms"]
    live = U[(sf == "live") & U["tradable_common"]]
    comp = U[(sf == "completed") & (pd.to_datetime(U["completion_date"]) < pd.Timestamp(HOLDOUT_START))]
    liq = U[(sf == "liquidated") & (pd.to_datetime(U["termination_date"]) < pd.Timestamp(HOLDOUT_START))]
    ext = sorted(set(K.loc[K["ext"], "cik"]))
    return {"live": declared_order(live["cik"])[:6], "completed": declared_order(comp["cik"])[:3],
            "liquidated": declared_order(liq["cik"])[:3], "extension": declared_order(ext)[:4]}


def verify_mechanics(client, sample: dict) -> int:
    """Every coded quote must be in its cited document, and every cited CIK in the declared sample."""
    from scripts.events import spac_mechanics as M
    allowed = {c for v in sample.values() for c in v}
    n = 0
    for m in M.MECHANICS + M.EIGHT_K:
        cik, acc, doc = m["src"]
        if cik not in allowed:
            raise CensusError(f"mechanics quote cites CIK {cik}, which is not in the declared sample")
        if not quote_in(fetch_doc(client, cik, acc, doc), m["quote"]):
            raise CensusError(f"quote not found in {cik} {acc} {doc}: {m['quote'][:80]}...")
        n += 1
    return n


NEAR_DEADLINE_DAYS = 183    # "near the deadline": the next deadline within six months
PARTICIPATION = 0.10        # a buyer taking 10% of ADV ...
ACCUMULATION_SESSIONS = 20  # ... for 20 sessions: the capacity convention of this note (stated, not fitted)


# Alpaca Securities' brokerage fee schedule (revised 2026-10-12): "Voluntary
# Corporate Actions Processing $100 per unique election" (docs/REFERENCES.md
# §12ac). Used here only to show the position size at which one election's
# fee is repaid; any gate re-reads the schedule before it is applied.
VOLUNTARY_ELECTION_FEE_USD = 100.0
COST_GRID_BP = (0, 5, 15, 30)   # gross, then the desk's grid (CLAUDE.md research rules, H3)


def _is_date(d) -> bool:
    return isinstance(d, date)


def live_splits(pool: pd.DataFrame, asof: date) -> dict:
    """Discount, yield and capacity of the redeemable pool, split by deal status and time to deadline.

    `pool`: priced, tradable live SPACs whose deal vote has not been held
    (`redeemable_pool`). Capacity is a BUYER taking PARTICIPATION of ADV for
    ACCUMULATION_SESSIONS, on the mean and on the median daily dollar volume
    (SPAC volume comes in a few large days: the median is the honest one).
    Rows past GAP_SCREEN are kept out of the capacity sums and itemised.
    """
    p = pool.copy()
    p["announced"] = p["announce_date"].notna()
    nd = p["deadline_next"].map(lambda d: _is_date(d) and (d - asof).days <= NEAR_DEADLINE_DAYS).astype(bool)
    cols = ("discount", "discount_accrued", "yield_next", "yield_max", "yield_total_next", "spread_next",
            "yield_total_max", "spread_max")
    def block(m):
        return {"n": int(m.sum()), **{c: describe(p.loc[m, c]) for c in cols}}
    def grid(m):
        """The desk's cost grid (5 / 15 / 30bp, H3) as one buy amortised over the days to the next deadline."""
        g = p[m & p["spread_next"].notna() & (p["days_next"] > 0)]
        out_g = {}
        for c in COST_GRID_BP:
            amort = c / 1e4 * 365.0 / g["days_next"]
            for k in ("spread_next", "yield_next"):
                net = g[k] - amort
                out_g[f"{k}_net_{c}bp"] = {"n": int(len(g)), "median": float(net.median()) if len(g) else None,
                                           "share_above_zero": float((net > 0).mean()) if len(g) else None}
        return out_g
    out = {"all": {**block(pd.Series(True, index=p.index)), "cost_grid": grid(pd.Series(True, index=p.index))},
           "announced": block(p["announced"]), "not_announced": block(~p["announced"]),
           "near_deadline": {**block(nd), "cost_grid": grid(nd), "adv_usd_mean": describe(p.loc[nd, "adv_usd_mean"]),
                             "adv_usd_median": describe(p.loc[nd, "adv_usd_median"])}}
    ok = ~p["gap_over_screen"].astype(bool)
    below = (p["discount"] < 0) & ok
    below_acc = (p["discount_accrued"] < 0) & ok
    for tag, m in (("below_trust", below), ("near_deadline_below_trust", below & nd),
                   ("below_accrued_trust", below_acc), ("near_deadline_below_accrued_trust", below_acc & nd)):
        g = p[m]
        gain = g["gain"] if "accrued" not in tag else g["trust_ps_accrued"] / g["last_close"] - 1.0
        cap_mean = g["adv_usd_mean"] * PARTICIPATION * ACCUMULATION_SESSIONS
        cap_med = g["adv_usd_median"] * PARTICIPATION * ACCUMULATION_SESSIONS
        out[tag] = {"n": int(len(g)), "sum_adv_usd_mean": float(g["adv_usd_mean"].sum()),
                    "sum_adv_usd_median": float(g["adv_usd_median"].sum()),
                    "capacity_usd_on_mean_adv": float(cap_mean.sum()),
                    "capacity_usd_on_median_adv": float(cap_med.sum()),
                    "gain_usd_on_mean_adv": float((cap_mean * gain).sum()),
                    "gain_usd_on_median_adv": float((cap_med * gain).sum()),
                    "median_gain": float(gain.median()) if len(g) else None,
                    "median_breakeven_position_usd_for_one_election":
                        float((VOLUNTARY_ELECTION_FEE_USD / gain).median()) if len(g) else None,
                    "n_median_adv_capacity_repays_one_election":
                        int((cap_med * gain > VOLUNTARY_ELECTION_FEE_USD).sum())}
    caught = p.loc[~ok, "discount"].abs()
    kept = p.loc[ok & (p["discount"] < 0), "discount"].abs()
    out["gap_screen_band"] = {"screen": GAP_SCREEN, "n_caught": int(len(caught)),
                              "same_rows_for_screens_between": [float(kept.max()) if len(kept) else 0.0,
                                                                float(caught.min()) if len(caught) else None]}
    return out


def _era(y: int) -> str:
    """The desk's eras (H5), restricted to the census's pre-holdout span."""
    return "pre-2015" if y < 2015 else ("2015-19" if y <= 2019 else "2020-22")


def hist_splits(levels: pd.DataFrame) -> dict:
    """Historical discount at each fixed point, by deal status at that date, by era and by year of the date."""
    out = {}
    for mb in FIXED_POINTS_MONTHS:
        L = levels[(levels["months_before"] == mb) & levels["discount"].notna()]
        yr = pd.to_datetime(L["fixed_point"]).dt.year
        era = yr.map(_era)
        out[f"{mb}m"] = {"announced": describe(L.loc[L["deal_announced"], "discount"]),
                         "not_announced": describe(L.loc[~L["deal_announced"], "discount"]),
                         **{f"era_{e}": {"discount": describe(L.loc[era == e, "discount"]),
                                         "discount_accrued": describe(L.loc[era == e, "discount_accrued"])}
                            for e in sorted(era.unique())},
                         "by_year": {int(y): {"discount": describe(L.loc[yr == y, "discount"]),
                                              "discount_accrued": describe(L.loc[yr == y, "discount_accrued"])}
                                     for y in sorted(yr.unique())}}
    return out


# ------------------------------------------------------------------ IBKR gate (added 2026-10-19)
#
# WHY THIS SECTION EXISTS. The 2026-10-15 census stopped at G-S1 because
# Alpaca does not document a SPAC-redemption election. The team lead ruled on
# 2026-10-19 that redemptions go through IBKR. IBKR's own FAQ "How do I request
# a Special Purpose Acquisition Company (SPAC) redemption?" (read 2026-10-19,
# docs/REFERENCES.md §12ag) documents the channel (Client Portal, Corporate
# Actions Manager) and says "A SPAC redemption request is subjected to 100 USD
# processing fee". IBKR's fee table lists "All Other (Mandatory, Voluntary,
# With Options, etc) | Free" and, separately, DWAC "USD 100 per settled
# transaction". The two IBKR pages disagree on whether a voluntary election is
# free; the SPAC-specific FAQ is used (USD 100), and whether the DWAC fee is
# charged ON TOP is unknown, so it is a separate fee case (USD 200), never
# averaged in. Every fee below is re-read from IBKR before any trade.

IBKR_DATE = "2026-10-19"
IBKR_LIVE_CSV = SPAC_DIR / f"spac_ibkr_gate_live_{IBKR_DATE}.csv"
IBKR_SUMMARY_JSON = SPAC_DIR / f"spac_ibkr_gate_summary_{IBKR_DATE}.json"
# The public "Products and Exchange Search" page calls this endpoint without a
# login (read from its own script, /products.exchanges.search/index.js, 2026-10-19).
IBKR_PRODUCTS_URL = "https://www.interactivebrokers.com/webrest/search/products-by-exchangeId-productType"
IBKR_PRODUCTS_REFERER = "https://www.interactivebrokers.com/en/trading/products-exchanges.php"
IBKR_SHORTSTOCK_URL = "https://www.interactivebrokers.com/shortstock/usa.txt"
IBKR_EXCHANGES = ("NASDAQ", "NYSE", "AMEX")   # where the census found every live tradable common (Alpaca labels)
IBKR_PAGE_SIZE = 500
IBKR_REQUEST_GAP_S = 1.0                       # one request a second: a public web page's endpoint, not an API

IBKR_SPAC_REDEMPTION_FEE_USD = 100.0   # FAQ 160415308: "subjected to 100 USD processing fee"
IBKR_DWAC_FEE_USD = 100.0              # fee table and FAQ 28216616: "USD 100.00 fee is charged per DWAC settlement"
# Fee cases, each reported beside the others (never one blended number):
#   liquidation: the SPAC liquidates at its deadline, a mandatory action, no election;
#   vote: a holder election at a deal or extension vote (the SPAC FAQ's fee);
#   vote_dwac_stacked: the same, if the DWAC settlement fee is charged as well [U].
IBKR_FEE_CASES = {"liquidation": 0.0, "vote": IBKR_SPAC_REDEMPTION_FEE_USD,
                  "vote_dwac_stacked": IBKR_SPAC_REDEMPTION_FEE_USD + IBKR_DWAC_FEE_USD}
# IBKR Pro Fixed, US stocks (commissions-stocks.php, read 2026-10-19): USD 0.005
# a share, minimum USD 1.00, maximum 1% of trade value. Fixed carries regulatory
# fees only; on a BUY that is FINRA's CAT fee (USD 0.000003 x quantity). There is
# no sale: the exit is the redemption, so the SEC fee on sales does not arise.
IBKR_FIXED_PER_SHARE = 0.005
IBKR_FIXED_MIN_USD = 1.00
IBKR_FIXED_MAX_FRAC = 0.01
FINRA_CAT_PER_SHARE = 0.000003
# "The redemption payment is typically paid to the account within 1-3 weeks"
# (FAQ 160415308): the capital is idle for that long. 0 and 21 days are shown.
IBKR_PAYMENT_LAG_DAYS = (0, 21)
IBKR_TICKETS_USD = (2_500, 5_000, 10_000, 25_000, 50_000, 100_000)   # a grid, not a choice: sizing is G-S3
# EDGAR state-of-incorporation codes -> the ISIN country prefix they imply.
# Used only as a cross-check that IBKR's contract is the SPAC's own share.
_DOMICILE_ISIN = {"E9": "KY", "D8": "VG"}
_US_STATES = frozenset("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH "
                       "NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())


def ibkr_fixed_commission(shares: int, price: float) -> float:
    """IBKR Pro Fixed commission on one US stock order: 0.005/share, min 1.00, max 1% of value."""
    if not (shares >= 1 and price > 0):
        raise ValueError(f"shares {shares} and price {price}: an order needs at least one share at a positive price")
    value = shares * price
    return min(max(IBKR_FIXED_PER_SHARE * shares, IBKR_FIXED_MIN_USD), IBKR_FIXED_MAX_FRAC * value)


def ibkr_net_terms(price: float, days: int, gross_yield: float, tbill_now: float, ticket_usd: float,
                   fee_usd: float, lag_days: int = 0, grid_bp: float = 0.0) -> dict:
    """Annualised yield and spread over bills after IBKR's costs, for ONE position held to `days`.

    `gross_yield` is a census yield to the next deadline, annualised simply
    (`yield_total_next` [model] or `yield_next`, no further interest). The
    position buys floor(ticket / price) whole shares (whole shares only, as
    at Alpaca), pays the Fixed commission, the CAT fee, `fee_usd` at the exit
    and the desk's `grid_bp` (spread and impact, H3) on the buy. The cash
    comes back `lag_days` after the deadline, earning nothing meanwhile.

        M        = 1 + gross_yield * days / 365            gross multiple to the deadline
        net_mult = M - costs / value
        net      = (net_mult - 1) * 365 / (days + lag)
        spread   = net - tbill_now

    With no commission, no fee and no lag this is exactly the census grid
    (`live_splits.grid`): gross - grid_bp * 365 / days. Raises on a ticket
    below one share's price (no position, not a zero) or a passed deadline.
    """
    if not (price > 0 and days > 0 and ticket_usd > 0 and fee_usd >= 0 and lag_days >= 0):
        raise ValueError(f"price {price}, days {days}, ticket {ticket_usd}, fee {fee_usd}, lag {lag_days}")
    shares = int(ticket_usd // price)
    if shares < 1:
        raise ValueError(f"ticket {ticket_usd} buys no whole share at {price}")
    value = shares * price
    costs = ibkr_fixed_commission(shares, price) + FINRA_CAT_PER_SHARE * shares + fee_usd + grid_bp / 1e4 * value
    net_mult = 1.0 + gross_yield * days / 365.0 - costs / value
    net = (net_mult - 1.0) * 365.0 / (days + lag_days)
    return {"shares": shares, "value": value, "costs_usd": costs, "net": net, "spread": net - tbill_now}


def ibkr_breakeven_ticket(price: float, days: int, gross_yield: float, tbill_now: float, fee_usd: float,
                          lag_days: int = 0, grid_bp: float = 0.0, hi: float = 1e7) -> float | None:
    """Smallest ticket (USD, to the share) at which the net SPREAD over bills is >= 0, or None if none <= `hi`.

    The spread rises with the ticket (the fixed fee is spread over more
    dollars), so a bisection on the share count is exact up to one share.
    """
    def ok(n):
        return ibkr_net_terms(price, days, gross_yield, tbill_now, n * price, fee_usd, lag_days, grid_bp)["spread"] >= 0
    lo_n, hi_n = 1, int(hi // price)
    if hi_n < 1 or not ok(hi_n):
        return None
    if ok(lo_n):
        return lo_n * price
    while hi_n - lo_n > 1:
        mid = (lo_n + hi_n) // 2
        lo_n, hi_n = (lo_n, mid) if ok(mid) else (mid, hi_n)
    return hi_n * price


def _ibkr_post(url: str, payload: dict) -> dict:
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Referer": IBKR_PRODUCTS_REFERER,
                                          "User-Agent": "Mozilla/5.0 (research census)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status != 200:
            raise CensusError(f"IBKR listing {payload.get('exchangeId')} page {payload.get('pageNumber')}: HTTP {r.status}")
        return json.loads(r.read())


def ibkr_listing(asof: str, offline: bool) -> pd.DataFrame:
    """IBKR's public listing of US stocks on each exchange in IBKR_EXCHANGES (cached per date).

    One row per (exchange list, symbol, conid). IBKR's per-exchange STK list
    is wider than the primary listings (NYSE and AMEX each list ~7,100 STK,
    Nasdaq ~4,000 on 2026-10-19), so `isPrimeExchId` == 'T' marks the primary
    exchange. The page count is checked against `productCount`; a short page
    raises. ISIN and CUSIP are read for the cross-check but never written to a
    tracked file (CUSIPs are licensed identifiers; this repository is public).
    """
    import time
    p = CACHE / f"ibkr_listing_{asof}.json"
    if p.exists():
        pages = json.loads(p.read_text())
    elif offline:
        raise CensusError(f"offline and {p.name} is not cached")
    else:
        pages = {}
        for ex in IBKR_EXCHANGES:
            got, n, pg = [], None, 1
            while n is None or len(got) < n:
                d = _ibkr_post(IBKR_PRODUCTS_URL, {"domain": "com", "exchangeId": ex, "pageNumber": pg,
                                                   "pageSize": IBKR_PAGE_SIZE, "productType": ["STK"],
                                                   "sortDirection": "asc", "sortField": "symbol"})
                n = int(d["productCount"])
                rows = d.get("products") or []
                if not rows and len(got) < n:
                    raise CensusError(f"IBKR {ex} page {pg} is empty with {len(got)} of {n} read")
                got += rows
                pg += 1
                time.sleep(IBKR_REQUEST_GAP_S)
            pages[ex] = {"read_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "productCount": n, "products": got}
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(pages))
    rows = []
    for ex, blk in pages.items():
        if len(blk["products"]) != blk["productCount"]:
            raise CensusError(f"IBKR {ex}: {len(blk['products'])} rows read, productCount {blk['productCount']}")
        for r in blk["products"]:
            rows.append({"list": ex, "symbol": r["symbol"], "conid": int(r["conid"]), "type": r["type"],
                         "exchange": r["exchangeId"], "primary": r.get("isPrimeExchId") == "T",
                         "description": r.get("description") or "", "isin": r.get("isin") or "",
                         "read_utc": blk["read_utc"]})
    out = pd.DataFrame(rows)
    if out.empty or (out["type"] != "STK").any():
        raise CensusError("IBKR listing: empty, or a non-STK row in an STK request")
    return out


def parse_ibkr_shortstock_ids(text: str) -> tuple[pd.DataFrame, str]:
    """IBKR's usa.txt -> (symbol, name, conid, isin) and the file stamp.

    `g1a_shortability.parse_ibkr_shortstock` keeps fees and availability but
    not the contract id, which is what a cross-check needs. Raises on a
    missing header field or an unparsable conid, naming the symbol.
    """
    lines = text.splitlines()
    if not lines or not lines[0].startswith("#BOF|"):
        raise CensusError(f"IBKR shortstock: first line {lines[:1]} is not '#BOF|date|time'")
    _, fdate, ftime = lines[0].split("|")[:3]
    hdr = [h for h in lines[1].lstrip("#").split("|") if h]
    for need in ("SYM", "NAME", "CON", "ISIN"):
        if need not in hdr:
            raise CensusError(f"IBKR shortstock header lacks {need}: {hdr}")
    rows = []
    for ln in lines[2:]:
        if not ln.strip() or ln.startswith("#EOF"):
            continue
        d = dict(zip(hdr, ln.split("|")))
        try:
            rows.append({"symbol": d["SYM"], "name": d["NAME"], "conid": int(d["CON"]), "isin": d["ISIN"]})
        except (KeyError, ValueError):
            raise CensusError(f"IBKR shortstock row for {d.get('SYM')!r} will not parse") from None
    return pd.DataFrame(rows), f"{fdate.replace('.', '-')} {ftime}"


def ibkr_shortstock(asof: str, offline: bool) -> tuple[pd.DataFrame, str]:
    p = CACHE / f"ibkr_shortstock_usa_{asof}.txt"
    if not p.exists():
        if offline:
            raise CensusError(f"offline and {p.name} is not cached")
        import urllib.request
        req = urllib.request.Request(IBKR_SHORTSTOCK_URL, headers={"User-Agent": "Mozilla/5.0 (research census)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
    return parse_ibkr_shortstock_ids(p.read_text(encoding="utf-8", errors="replace"))


_UNIT_LIKE_RE = re.compile(r"-(?:UN|WT|WS|RT)$")


def ibkr_candidate_symbols(symbol, tickers) -> list[str]:
    """Symbols that could be the SPAC's common at IBKR, best first.

    The census's Alpaca common symbol comes first. Then the EDGAR tickers,
    with NYSE-style unit/warrant/right suffixes (-UN, -WT, -WS, -RT) cut back
    to their base, and any ticker that is another ticker plus one letter
    (U, W or R: the Nasdaq unit, warrant and right) dropped.
    """
    ts = [t for t in str(tickers).split(";") if t and t != "nan"] if isinstance(tickers, str) else []
    bases = [_UNIT_LIKE_RE.sub("", t) for t in ts]
    keep = [b for b in bases if not (len(b) > 1 and b[-1] in "UWR" and b[:-1] in bases)]
    out = []
    for c in ([symbol] if isinstance(symbol, str) and symbol else []) + keep:
        if c not in out:
            out.append(c)
    return out


_CLASS_SUFFIX_RE = re.compile(r"(?:[\s-]+CL(?:ASS)?)?[\s-]+[A-Z]$|[\s-]+CL(?:ASS)?[\s-]*[A-Z]$")


def ibkr_name(desc: str) -> str:
    """IBKR's description without its share-class tail ('-A', ' CL-A', ' CLASS A')."""
    return _CLASS_SUFFIX_RE.sub("", (desc or "").upper()).strip()


IBKR_PREFIX_MIN_CHARS = 12   # a truncated stem shorter than this ("SPAC PARTNER") proves nothing


def ibkr_truncated_prefix(desc: str, name: str) -> bool:
    """IBKR's description, class tail removed, is a truncation of the census name.

    WHY: IBKR cuts long names at a fixed width and then appends the class
    ("OAKTREE ACQUISITION CORP I-A" is Oaktree Acquisition Corp. III Life
    Sciences; "CHENGHE ACQUISITION II-CL A" is Chenghe Acquisition III Co.).
    A cut through a Roman numeral turns III into I, which `name_score`
    reads as a different number. Measured 2026-10-19: 16 of the 288 listed
    commons failed `name_score` and 15 of them are such truncations; this rule
    was written AFTER seeing them, so the CSV records which rule admitted
    each name (`name_rule`), and the other checks are reported beside it.
    Letters and digits only are compared, so 'A SPAC III' meets 'ASPAC III'.
    """
    stem = re.sub(r"[^A-Z0-9]", "", ibkr_name(desc))
    full = re.sub(r"[^A-Z0-9]", "", (name or "").upper())
    return len(stem) >= IBKR_PREFIX_MIN_CHARS and full.startswith(stem)


def ibkr_match(live: pd.DataFrame, listing: pd.DataFrame, shortstock: pd.DataFrame) -> pd.DataFrame:
    """For each live SPAC: IBKR's contract for its common, and three checks on it.

    `listed_ibkr`: an STK row in IBKR's listing with a candidate symbol.
    Checks, each its own column, never folded into one flag:
      name_ok        name_score(IBKR description without class tail, census name) >= LINK_MIN_SCORE
                     ('tokens'), or the description is a truncation of the name
                     ('truncated_prefix'); `name_rule` says which
      conid_in_shortstock_agrees   the shortstock file carries the symbol with the same conid
      isin_matches_domicile        the ISIN's country prefix is what EDGAR's state code implies
    A symbol IBKR lists under two conids is `ambiguous` and is not chosen
    between. `tradable_ibkr` = listed, one conid, name_ok. It is a listing,
    not a promise that a given account may trade it (IBKR's permissions are
    per account and are not public).
    """
    stk = listing.sort_values(["primary", "list"], ascending=[False, True])
    by_sym = {s: g for s, g in stk.groupby("symbol", sort=False)}
    ss = shortstock.drop_duplicates(["symbol", "conid"]).groupby("symbol")["conid"].apply(set).to_dict()
    out = []
    for r in live.itertuples():
        cands = ibkr_candidate_symbols(getattr(r, "symbol", None), getattr(r, "tickers", None))
        hit = next((c for c in cands if c in by_sym), None)
        # An unlisted SPAC has zero IBKR contracts and no checks to report (None, not False).
        row = {"cik": r.cik, "ibkr_candidates": ";".join(cands), "ibkr_symbol": hit, "listed_ibkr": hit is not None,
               "ibkr_conid": None, "ibkr_n_conids": 0, "ibkr_primary_exchange": None, "ibkr_description": None,
               "ibkr_name_score": None, "name_ok": None, "name_rule": None, "conid_in_shortstock_agrees": None,
               "isin_matches_domicile": None}
        if hit is not None:
            g = by_sym[hit]
            conids = sorted(g["conid"].unique())
            first = g.iloc[0]
            prim = g.loc[g["primary"], "exchange"].unique()
            score = name_score(ibkr_name(first["description"]), r.name)
            rule = ("tokens" if score >= LINK_MIN_SCORE
                    else "truncated_prefix" if ibkr_truncated_prefix(first["description"], r.name) else None)
            dom = getattr(r, "domicile", None)
            want = _DOMICILE_ISIN.get(dom) or ("US" if dom in _US_STATES else None)
            row |= {"ibkr_conid": int(conids[0]) if len(conids) == 1 else None, "ibkr_n_conids": len(conids),
                    "ibkr_primary_exchange": prim[0] if len(prim) == 1 else (";".join(prim) if len(prim) else None),
                    "ibkr_description": first["description"], "ibkr_name_score": round(score, 3),
                    "name_ok": rule is not None, "name_rule": rule,
                    "conid_in_shortstock_agrees": (bool(ss.get(hit) and len(conids) == 1 and conids[0] in ss[hit])
                                                   if hit in ss else None),
                    "isin_matches_domicile": (first["isin"][:2] == want) if (want and first["isin"]) else None}
        out.append(row)
    M = pd.DataFrame(out)
    M["ambiguous"] = M["ibkr_n_conids"] > 1
    M["tradable_ibkr"] = M["listed_ibkr"] & (M["ibkr_n_conids"] == 1) & M["name_ok"].map(lambda v: v is True)
    return M


def ibkr_election_load(years: pd.DataFrame, recent=(2024, 2025)) -> dict:
    """How often the exit needs an election, from the census's own event counts (universe, by year).

    Every redemption window is a vote: an extension vote, or the deal vote
    before a completion. A liquidation needs no election. The share of
    windows-or-liquidations that are votes is what fraction of exits taken at
    the FIRST event need a USD 100 election; the share of terminal events
    (completion vs liquidation) is the floor for a holder who skips every
    extension window and holds to the end. Counts are floors where the census
    says so (completions, §1.2).
    """
    y = years[years["year"].isin(recent)]
    if len(y) != len(recent):
        raise CensusError(f"years table lacks one of {recent}")
    ext, comp, liq = (int(y[c].sum()) for c in ("extension_votes", "deals_completed", "liquidations"))
    return {"years": list(recent), "extension_votes": ext, "deals_completed": comp, "liquidations": liq,
            "share_first_event_is_vote": (ext + comp) / (ext + comp + liq),
            "share_terminal_event_is_deal": comp / (comp + liq)}


def ibkr_stage(asof: str, offline: bool) -> dict:
    """The gate re-run on IBKR's terms. Reads the census's committed outputs; writes the IBKR CSV and JSON."""
    D = pd.read_csv(LIVE_CSV, parse_dates=["deadline_next"])
    years = pd.read_csv(YEARS_CSV)
    live = D[D["status"] == "live"].copy()
    listing = ibkr_listing(asof, offline)
    ss, ss_stamp = ibkr_shortstock(asof, offline)
    M = ibkr_match(live, listing, ss)
    L = live.merge(M, on="cik", how="left", validate="one_to_one")

    # The census's redeemable pool, restricted to commons that pass every IBKR listing check:
    # the gate is about what IBKR can hold. (The price is still the census's Alpaca SIP close.)
    pool_alpaca = L[(L["tradable"] == True) & L["discount"].notna() & (L["redeemable_pool"] == True)]   # noqa: E712
    pool = pool_alpaca[pool_alpaca["tradable_ibkr"] == True].copy()   # noqa: E712
    # The census grid's own filter (`live_splits.grid`): a deadline ahead and a modelled spread.
    priced = pool[(pool["days_next"] > 0) & pool["spread_next"].notna()].copy()
    nd = priced["days_next"] <= NEAR_DEADLINE_DAYS
    ok = ~priced["gap_over_screen"].astype(bool)
    near_below_acc = nd & ok & (priced["discount_accrued"] < 0)
    priced["cap_median_adv"] = priced["adv_usd_median"] * PARTICIPATION * ACCUMULATION_SESSIONS

    def net_col(r, ticket, fee, lag, grid, which):
        y = r["yield_total_next"] if which == "spread" else r["yield_next"]
        t = ibkr_net_terms(r["last_close"], int(r["days_next"]), y, r["tbill_now"], ticket, fee, lag, grid)
        return t["spread"] if which == "spread" else t["net"]

    grid = {}
    for case, fee in IBKR_FEE_CASES.items():
        for lag in IBKR_PAYMENT_LAG_DAYS:
            for tk in IBKR_TICKETS_USD:
                for bp in COST_GRID_BP:
                    for which in ("spread", "yield_no_interest"):
                        v = priced.apply(lambda r: net_col(r, tk, fee, lag, bp, which), axis=1)
                        for setname, m in (("pool", pd.Series(True, index=priced.index)), ("near_deadline", nd),
                                           ("near_deadline_below_accrued", near_below_acc)):
                            x = v[m]
                            grid[f"{setname}|{which}|{case}|lag{lag}|{tk}|{bp}bp"] = {
                                "n": int(len(x)), "median": float(x.median()) if len(x) else None,
                                "share_above_zero": float((x > 0).mean()) if len(x) else None}
    # Per name: the ticket that repays the vote-route costs (spread >= 0), gross and at 30bp, no lag.
    for case in ("vote", "vote_dwac_stacked"):
        for bp in (0, 30):
            priced[f"breakeven_ticket_{case}_{bp}bp"] = priced.apply(
                lambda r: ibkr_breakeven_ticket(r["last_close"], int(r["days_next"]), r["yield_total_next"],
                                                r["tbill_now"], IBKR_FEE_CASES[case], 0, bp), axis=1)
    cap = {}
    for case in ("vote", "vote_dwac_stacked"):
        # A name with no breakeven up to USD 10M never repays the fee: +inf, so no capacity "fits" it.
        be = priced[f"breakeven_ticket_{case}_0bp"].map(lambda v: np.inf if v is None or pd.isna(v) else v)
        for setname, m in (("pool_below_accrued", ok & (priced["discount_accrued"] < 0)),
                           ("near_deadline_below_accrued", near_below_acc)):
            g = priced[m]
            fits = g["cap_median_adv"] >= be[m]
            finite = be[m][np.isfinite(be[m])]
            # One-off dollars OVER BILLS after IBKR's costs, each fitting name bought at its
            # median-ADV capacity and held to its next deadline: spread_net * value * days / 365.
            gain = {bp: float(sum(
                (t := ibkr_net_terms(r.last_close, int(r.days_next), r.yield_total_next, r.tbill_now,
                                     r.cap_median_adv, IBKR_FEE_CASES[case], 0, bp))["spread"]
                * t["value"] * r.days_next / 365.0 for r in g[fits].itertuples())) for bp in COST_GRID_BP}
            cap[f"{setname}|{case}"] = {
                "n": int(len(g)), "n_capacity_repays_costs": int(fits.sum()),
                "capacity_usd_median_adv_all": float(g["cap_median_adv"].sum()),
                "capacity_usd_median_adv_where_it_repays": float(g.loc[fits, "cap_median_adv"].sum()),
                "breakeven_ticket": describe(finite), "n_no_breakeven": int((~np.isfinite(be[m])).sum()),
                "gain_over_bills_usd_at_capacity_where_it_repays": {f"{bp}bp": v for bp, v in gain.items()}}
    load = ibkr_election_load(years)
    nb = priced[near_below_acc]
    nb_be = nb["breakeven_ticket_vote_0bp"].map(lambda v: np.inf if v is None or pd.isna(v) else v)
    nb_fit = nb[nb["cap_median_adv"] >= nb_be]
    days_cycle = float(nb_fit["days_next"].median()) if len(nb_fit) else None

    keep = ["cik", "name", "symbol", "exchange", "tradable", "ibkr_candidates", "ibkr_symbol", "listed_ibkr",
            "ibkr_conid", "ibkr_n_conids", "ibkr_primary_exchange", "ibkr_description", "ibkr_name_score",
            "name_ok", "name_rule", "conid_in_shortstock_agrees", "isin_matches_domicile", "ambiguous", "tradable_ibkr"]
    out = L[keep].merge(priced[["cik", "cap_median_adv"] + [c for c in priced.columns if c.startswith("breakeven_ticket_")]],
                        on="cik", how="left")
    SPAC_DIR.mkdir(parents=True, exist_ok=True)
    out.sort_values(["tradable_ibkr", "symbol"], ascending=[True, True]).to_csv(IBKR_LIVE_CSV, index=False, float_format="%.6g")

    alp, ib = L["tradable"] == True, L["tradable_ibkr"] == True   # noqa: E712
    summary = {
        "ibkr_asof": asof, "census_asof": NOTE_DATE, "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ibkr_listing_read_utc": sorted(listing["read_utc"].unique().tolist()), "ibkr_shortstock_stamp": ss_stamp,
        "ibkr_listing_rows": {ex: int((listing["list"] == ex).sum()) for ex in IBKR_EXCHANGES},
        "live": int(len(L)), "listed_ibkr": int(L["listed_ibkr"].sum()), "tradable_ibkr": int(ib.sum()),
        "ambiguous": int(L["ambiguous"].sum()), "name_check_failed": int((L["listed_ibkr"] & (L["name_ok"] == False)).sum()),   # noqa: E712
        "name_rule": L["name_rule"].value_counts(dropna=False).rename(str).to_dict(),
        "conid_shortstock": L["conid_in_shortstock_agrees"].value_counts(dropna=False).rename(str).to_dict(),
        "isin_vs_domicile": L["isin_matches_domicile"].value_counts(dropna=False).rename(str).to_dict(),
        "primary_exchange_vs_alpaca": pd.crosstab(L.loc[ib, "exchange"].fillna("none"),
                                                  L.loc[ib, "ibkr_primary_exchange"].fillna("none")).to_dict(),
        "alpaca_and_ibkr": int((alp & ib).sum()), "alpaca_only": int((alp & ~ib).sum()),
        "ibkr_only": int((~alp & ib).sum()), "neither": int((~alp & ~ib).sum()),
        "not_tradable_ibkr_rows": L.loc[~ib, ["symbol", "tickers", "name", "exchange", "ibkr_candidates", "ibkr_symbol",
                                              "ibkr_description", "ibkr_name_score"]].to_dict("records"),
        "pool_alpaca": int(len(pool_alpaca)), "pool": int(len(pool)), "pool_priced_deadline_ahead": int(len(priced)),
        "pool_tradable_ibkr": int(len(pool)),
        "near_deadline": int(nd.sum()), "near_deadline_below_accrued": int(near_below_acc.sum()),
        "fee_cases_usd": IBKR_FEE_CASES, "tickets_usd": list(IBKR_TICKETS_USD), "lags_days": list(IBKR_PAYMENT_LAG_DAYS),
        "commission": {"per_share": IBKR_FIXED_PER_SHARE, "min": IBKR_FIXED_MIN_USD, "max_frac": IBKR_FIXED_MAX_FRAC,
                       "cat_per_share": FINRA_CAT_PER_SHARE},
        "net_grid": grid, "capacity": cap, "election_load": load | {
            "near_deadline_names_that_repay_vote_costs": int(len(nb_fit)),
            "median_days_to_next_deadline_there": days_cycle,
            "elections_per_slot_per_year_lag0": (365.0 / days_cycle) if days_cycle else None,
            "elections_per_slot_per_year_lag21": (365.0 / (days_cycle + 21)) if days_cycle else None,
            # Every fitting name held, each exit taken at the first event: a vote with
            # probability share_first_event_is_vote (the 2024-25 universe mix).
            "elections_per_year_all_fitting_names_lag0": (len(nb_fit) * 365.0 / days_cycle
                                                          * load["share_first_event_is_vote"]) if days_cycle else None,
            "elections_per_year_all_fitting_names_lag21": (len(nb_fit) * 365.0 / (days_cycle + 21)
                                                           * load["share_first_event_is_vote"]) if days_cycle else None},
    }
    IBKR_SUMMARY_JSON.write_text(json.dumps(summary, indent=1, default=str))
    return summary


def freeze(client) -> None:
    """Make `client` treat every cached document as immutable (the `--frozen` mode).

    WHY: the census is a snapshot. Its date-sensitive inputs (the SIC browse,
    the current quarter's index, the two bulk archives) are re-fetched online
    once they pass their `max_age_s`, and a re-fetch days later moves the
    snapshot: new IPOs, new 10-Qs, a different live count from the same
    `--asof`. Measured 2026-10-18: the 2026-10-15 run had been cut off while
    it fetched complete submissions, and finishing it online would have
    re-read the browse and the archives three days late. Frozen, a missing
    filing (immutable) is still fetched, and nothing cached is replaced.
    """
    get = client.get
    client.get = lambda url, max_age_s=None: get(url, None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true", help="rebuild from the caches; no network")
    ap.add_argument("--asof", default=NOTE_DATE, help="census date (the last session's close)")
    ap.add_argument("--frozen", action="store_true",
                    help="use every cached EDGAR document whatever its age; fetch only what is not cached")
    ap.add_argument("--ibkr", action="store_true",
                    help="re-run the gate on IBKR's terms from the committed census outputs and IBKR's public files "
                         "(no EDGAR, no broker, no credentials); with --offline, from the cached IBKR files")
    ap.add_argument("--ibkr-asof", default=IBKR_DATE, help="date of the IBKR public files (cache key)")
    a = ap.parse_args(argv)
    if a.ibkr:
        S = ibkr_stage(a.ibkr_asof, a.offline)
        print(json.dumps({k: S[k] for k in ("ibkr_asof", "live", "listed_ibkr", "tradable_ibkr", "alpaca_and_ibkr",
                                            "alpaca_only", "ibkr_only", "neither", "pool_tradable_ibkr")}, indent=1))
        return 0
    asof = date.fromisoformat(a.asof)
    from scripts.data.edgar_client import EdgarClient
    client = EdgarClient(offline=a.offline)
    if a.frozen:
        freeze(client)

    B = build_universe(client, asof)
    ev, F, meta, facts, prim = B["ev"], B["F"], B["meta"], B["facts"], B["prim"]
    U = ev[ev["is_spac"]].copy()
    K = text_checks(client, U, F, prim)

    # Final status of delisted SPACs with no completion 8-K: by the text of their last 8-Ks
    # (primary documents; the complete submission, with exhibits, where those are not enough).
    from scripts.data.edgar_client import filing_txt_url
    term_status = {}
    for r in U[U["status"] == "liquidated"].itertuples():
        accs = list(K.loc[(K["cik"] == r.cik) & (K["kind"] == "liq"), "accession"])
        texts = {x: fetch_doc(client, r.cik, x, prim[x]) for x in accs}
        st = classify_terminated(texts)
        if st == "unclassified" and accs:
            texts = {x: plain(client.get_text(filing_txt_url(int(r.cik), x))) for x in accs}
            st = classify_terminated(texts)
        term_status[r.cik] = st
    U["status_forms"] = U["status"]
    U.loc[U["cik"].isin(term_status), "status"] = U.loc[U["cik"].isin(term_status), "cik"].map(term_status)
    ch = U["status"] == "completed_holdco"
    U.loc[ch, "completion_date"] = U.loc[ch, "termination_date"]
    U.loc[ch, "completion_rule"] = "holdco_text_at_delisting"
    U.loc[ch, "status"] = "completed"

    # Extension votes: text-confirmed, dated by the 8-K.
    fdate = F.drop_duplicates("accessionNumber").set_index("accessionNumber")["filingDate"]
    ext = K[K["ext"] & (K["kind"] == "vote")]
    ext_dates = ext.assign(d=ext["accession"].map(fdate).dt.date).groupby("cik")["d"].apply(lambda s: sorted(set(s)))
    U["ext_dates"] = U["cik"].map(ext_dates).apply(lambda v: v if isinstance(v, list) else [])
    U["n_extension_votes"] = U["ext_dates"].map(len)

    A = alpaca_assets(asof.isoformat(), a.offline)["assets"]
    U["common_symbol"] = U["cik"].map(lambda c: (common_symbol(meta[c]["tickers"] or [], A) or {}).get("symbol"))
    U["tradable_common"] = U["cik"].map(lambda c: bool((common_symbol(meta[c]["tickers"] or [], A) or {}).get("tradable")))

    years = year_counts(U)
    ritter = ritter_benchmark(a.offline)
    years["ritter_spac_ipos"] = years["year"].map(ritter["spac_ipos_by_year"])
    years["ritter_despacs"] = years["year"].map(ritter["despacs_by_year"])
    years["live_at_year_end"] = years["year"].map(lambda y: live_at(U, pd.Timestamp(f"{y}-12-31")))
    q26 = sum(v for k, v in ritter["spac_ipos_by_quarter"].items() if k.startswith(str(asof.year)))
    ours26 = int((pd.to_datetime(U["ipo_date"]) < pd.Timestamp(f"{asof.year}-10-01")).sum()
                 - (pd.to_datetime(U["ipo_date"]) < pd.Timestamp(f"{asof.year}-01-01")).sum())

    D = live_stage(client, U, F, meta, facts, prim, K, asof, a.offline)
    H, levels = hist_stage(U, facts, a.offline)

    sample = declared_sample(U, K)
    n_quotes = verify_mechanics(client, sample)

    # CRSP cross-check of the delisting classification (linked SPACs only).
    dl = pd.read_parquet(CACHE / "crsp_stkdelists_2014plus.parquet") if (CACHE / "crsp_stkdelists_2014plus.parquet").exists() else None
    xcheck = None
    if dl is not None:
        m = H.merge(dl[["permno", "delistingdt", "delactiontype"]], on="permno", how="inner")
        m = m[m["termination_date"].notna()]
        m = m[(pd.to_datetime(m["delistingdt"]) - pd.to_datetime(m["termination_date"])).abs().dt.days <= 30]
        xcheck = pd.crosstab(m["status"], m["delactiontype"]).to_dict()

    # ---------------- outputs
    SPAC_DIR.mkdir(parents=True, exist_ok=True)
    ucols = ["cik", "name_now", "ipo_name", "ipo_date", "ipo_accession", "sic_now", "net_sic6770", "item_506",
             "xbrl_trust_share", "net_name", "n_trust", "n_bc", "cover_trust", "cover_ipo", "prospectus_test",
             "base_months", "t0", "status", "status_forms", "announce_date", "n_425", "completion_date",
             "completion_rule", "termination_date", "termination_form", "n_extension_votes", "ext_dates",
             "last_periodic", "common_symbol", "tradable_common"]
    Uo = U[ucols].copy()
    Uo["ext_dates"] = Uo["ext_dates"].map(lambda v: ";".join(str(d) for d in v))
    Uo.sort_values(["ipo_date", "cik"]).to_csv(UNIVERSE_CSV, index=False, float_format="%.6g")
    years.to_csv(YEARS_CSV, index=False)
    D.sort_values(["status", "deadline_next", "cik"], na_position="last").to_csv(LIVE_CSV, index=False, float_format="%.6g")
    CACHE.mkdir(parents=True, exist_ok=True)
    levels.merge(H[["cik", "permno", "crsp_name", "link_score"]], on="cik", how="left").to_csv(HIST_ROWS, index=False)

    live = D[D["status"] == "live"]
    tr = live[live["tradable"]]
    priced = tr[tr["discount"].notna()]
    pool = priced[priced["redeemable_pool"]]
    itemise = ["symbol", "cik", "name", "trust_ps", "trust_ps_source", "trust_ps_sources", "balance_sheet_date",
               "last_close", "discount", "deal_vote_date", "merger_proxy_date", "adv_usd_mean", "adv_usd_median"]
    summary = {
        "asof": asof.isoformat(), "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "alpaca_assets_read_utc": D.attrs.get("alpaca_read_utc"),
        "universe": {"candidates": B["n_candidates"], "sic6770_now": B["n_sic6770"], "424b4_filers_2014plus": B["n_424b4_filers"],
                     "spacs": int(len(U)), "by_status": U["status"].value_counts().to_dict(),
                     "admitted_by": {"prospectus_cover_test": int(U["prospectus_test"].sum()),
                                     "xbrl_only": int((~U["prospectus_test"] & U["net_xbrl"]).sum())},
                     "ritter_2026_through_q3": q26, "ours_2026_through_q3": ours26,
                     "ritter_table_15b_updated": ritter["table_15b_updated"], "ritter_sha256": ritter["sha256"]},
        "text_checks": {"vote_8ks": int((K["kind"] == "vote").sum()), "extension_8ks": int(len(ext)),
                        "terminated_final": pd.Series(term_status).value_counts().to_dict()},
        "crsp_delisting_crosscheck": xcheck,
        "live": {"n_live": int(len(live)), "n_delisted_alive": int((D["status"] == "delisted_alive").sum()),
                 "tradable_common": int(len(tr)), "by_exchange": tr["exchange"].value_counts().to_dict(),
                 "not_on_alpaca": int(live["symbol"].isna().sum()),
                 "priced": int(len(priced)), "discount": describe(priced["discount"]),
                 "share_below_trust": float((priced["discount"] < 0).mean()) if len(priced) else None,
                 "yield_to_deadline_max": describe(priced["yield_max"]),
                 "yield_to_deadline_next": describe(priced["yield_next"]),
                 "adv_usd_mean": describe(tr["adv_usd_mean"]), "adv_usd_median": describe(tr["adv_usd_median"]),
                 "trust_ps_source": priced["trust_ps_source"].value_counts().to_dict(),
                 "trust_ps_spread_over_1pct": int((priced["trust_ps_spread"] > TRUST_PS_DISAGREE).sum()),
                 "deal_vote_held": int(priced["deal_vote_date"].notna().sum()),
                 "merger_proxy_filed_no_deal_vote": int((priced["merger_proxy_date"].notna()
                                                         & priced["deal_vote_date"].isna()).sum()),
                 "redeemable_pool": int(len(pool)),
                 "pool_share_below_trust": float((pool["discount"] < 0).mean()) if len(pool) else None,
                 "pool_share_below_accrued_trust": float((pool["discount_accrued"] < 0).mean()) if len(pool) else None,
                 "tbill_last": D.attrs.get("tbill_last"),
                 "deal_vote_rows": priced.loc[priced["deal_vote_date"].notna(), itemise].to_dict("records"),
                 "gap_rows": priced.loc[priced["gap_over_screen"].astype(bool), itemise].to_dict("records")},
        "live_splits": live_splits(pool, asof),
        "historical_splits": hist_splits(levels),
        "historical_levels": {f"{mb}m": {"discount": describe(levels.loc[levels["months_before"] == mb, "discount"]),
                                         "discount_accrued": describe(levels.loc[levels["months_before"] == mb, "discount_accrued"]),
                                         "spread": describe(levels.loc[levels["months_before"] == mb, "spread"]),
                                         "price_is_quote_midpoint": int((levels.loc[levels["months_before"] == mb, "traded"] == False).sum()),
                                         "yield_simple": describe(levels.loc[levels["months_before"] == mb, "yield_simple"]),
                                         "rows": int((levels["months_before"] == mb).sum()),
                                         "trust_not_ok": levels.loc[levels["months_before"] == mb, "tr_why"].value_counts().to_dict()}
                              for mb in FIXED_POINTS_MONTHS},
        "crsp_link": {"spacs_2014_2022": int(len(H)), "linked": int(H["permno"].notna().sum())},
        "sample": sample, "mechanics_quotes_verified": n_quotes,
        "edgar_requests": client.n_requests, "edgar_cache_hits": client.n_cache_hits,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=1, default=str, sort_keys=False))
    print(json.dumps({k: summary[k] for k in ("universe", "live")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
