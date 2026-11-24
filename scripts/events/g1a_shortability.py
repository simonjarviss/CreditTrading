"""Gate G1a for trial E1: can the short-acquirer leg of a CEF/BDC merger pair be built?

    export QUANTT_ENV_FILE=/abs/path/config/.env   # Alpaca cef key, SEC_USER_AGENT; never printed
    python3 scripts/events/g1a_shortability.py             # EDGAR, Alpaca, IBKR file, FINRA files
    python3 scripts/events/g1a_shortability.py --offline   # the same, from the caches only

ZERO TRIALS. A COUNT, NOT A RETURN. Gate G1a of
`results/cef/RESEARCH_PLAN_2026-10-09.md` §2: "Alpaca shortability today of
acquirers in pending CEF/BDC mergers, and the historical share of shortable
acquirers ... passes when most acquirers are shortable; kills when the hedged
pair is not buildable." Nothing here computes a return. The 167-deal sample's
return columns are never read: the sample is selected by its `status` column
(priced = "ok" or "bridged") and the count is asserted.

READ-ONLY, AND WHAT IS CALLED
-----------------------------
* EDGAR (through `scripts/data/edgar_client.py` only): the quarterly indexes,
  the ticker file and the filings cited in `READINGS`. Rate limit and contact
  rules live in that client.
* Alpaca, paper endpoint, `cef` key (`AlpacaClient.from_environment`):
  `GET /v2/assets/{symbol}` and `GET /v1/corporate-actions`. No order path is
  reachable from this module.
* IBKR's public shortstock file, `https://www.interactivebrokers.com/shortstock/usa.txt`
  (the file `scripts/cef/real_money_costs.py` reads), once per run, cached.
* FINRA's semi-monthly equity short-interest files,
  `https://cdn.finra.org/equity/otcmarket/biweekly/shrt{YYYYMMDD}.csv`, plain
  GETs, cached. FINRA's query API needs POST for filters and a credential by
  its own documentation, so it is not used.
Every response is cached under `results/events/_cache_g1a/` (gitignored by
`results/**/_cache_*`). Borrow flags CHANGE DAILY (CLAUDE.md landmine 5): every
flag carries the time it was read and is true on that date only.

PART 1 -- PENDING DEALS TODAY
-----------------------------
There is no list of pending CEF mergers to download. The candidates are
derived, then read:
1. `fetch_edgar_events.build` gives every merger-kind filing (425, N-14 8C,
   N-14, merger proxies) of the CEF/BDC fund set.
2. `deal_components` links funds that share an accession number (the index
   lists a 425 under the filer AND each subject company), so one deal is one
   connected component.
3. A component is a CANDIDATE if a fund in it is listed today (SEC ticker file)
   and its last merger filing is within `PENDING_GAP_DAYS` (180) of the newest
   index date. 180 days is the fetcher's own merger-episode gap
   (`fetch_edgar_events.EPISODE_GAP_DAYS["merger"]`): a CEF merger files 425s,
   N-14 amendments and proxy supplements until its vote, so a deal silent that
   long is completed, terminated or dormant. Chosen from how the process runs,
   not fitted.
4. Every candidate must be covered by a hand reading in `READINGS`, which
   cites the filing (accession) or release that decides it. **An unread
   candidate raises** (`UnreadCandidate`): a new deal can never be dropped
   silently, and a deal that changes state (completes, is terminated) fails
   `check_readings` against Alpaca's asset status and corporate-actions feed
   until the reading is updated.
The index is blind to two things, both stated in the note: a deal announced
by press release with no EDGAR filing yet, and a party outside the CEF/BDC
fund set (a REIT target, an ETF or open-end acquirer), which appears only
through the fund that did file.

PART 2 -- THE HISTORICAL SHARE (the 167 EDGAR-dated, priced deals of 2010-22)
---------------------------------------------------------------------------
Alpaca keeps no flag history. Four measures, each with its exact coverage:
* H1 `ibkr_fee_history`: `data/cef/cef_borrow_history.parquet`, IBKR FEE_RATE,
  43 universe names from 2021-09-13. A COST, not an availability flag. It
  covers none of the 167 (they exclude every universe name), so H1b reports,
  as context, the fee the day before the first merger filing for UNIVERSE
  acquirers in the later deals the history does span (episodes whose first
  filing is an amendment continue an earlier deal and are dropped).
* H2 `finra_si`: the acquirer's reported short position at the last FINRA
  settlement date strictly before the announcement (files exist from
  2017-12-29; earlier dates return HTTP 403 [V 2026-10-13]). A position > 0
  means some member firm was short, so borrow existed somewhere; it is not
  evidence that Alpaca would lend. A ticker absent from a file has no reported
  position (FINRA lists only securities with one) -- or a ticker mismatch,
  which the name check flags.
* H3 Alpaca flags TODAY for acquirers that are still the same fund
  (`crsp_identity`, `identity_today`): the CRSP permno is listed on CRSP's last
  date (2024-12-31) with the share code it had at the announcement, Alpaca's
  asset under that last ticker is active, and Alpaca's name matches CRSP's last
  name (`edgar_merger_dates.name_score` >= MIN_SCORE) -- or, for a renamed fund,
  the EDGAR name history of the CIK the SEC ticker file gives for that ticker
  does. Anything else is reported as an identity failure, never as a flag.
* H4 the IBKR shortstock file TODAY for the same names.
H3 and H4 are true today; the gate asks about announcement dates. They are a
proxy and labelled as one.

VERDICT RULE (`segment_verdict`)
--------------------------------
"Most" is more than half. Per segment, the Alpaca measures that exist (pending
today, H3) each give a share of acquirers shortable. PASS if every one is
above 1/2, FAIL if every one is at or below 1/2, PARTIAL if they disagree, and
UNMEASURED if none exists. FINRA and IBKR are the second sources: shown beside
the verdict, never inside it, because the book cannot borrow at either.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:  # run as a script, not -m
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events"
G1A_DIR = OUT / "g1a"                                # the gate's outputs: the note sits in OUT, its data here
CACHE = OUT / "_cache_g1a"
SAMPLE = OUT / "merger_ann_sample_edgar.csv"         # merger_pairs.py --edgar-dates (gitignored)
BORROW_HISTORY = REPO / "data" / "cef" / "cef_borrow_history.parquet"
UNIVERSE = REPO / "data" / "cef" / "cef_universe.csv"

IBKR_URL = "https://www.interactivebrokers.com/shortstock/usa.txt"
FINRA_URL = "https://cdn.finra.org/equity/otcmarket/biweekly/shrt{d}.csv"
FINRA_FIRST = date(2017, 12, 29)     # earliest file found; 2017 dates before it return 403 [V 2026-10-13]
FINRA_MAX_LOOKBACK_DAYS = 31         # settlement dates are about two weeks apart
CRSP_LAST = "2024-12-31"             # the R2 CRSP names table's last date (docs/DATA.md §3)
PENDING_GAP_DAYS = 180               # = fetch_edgar_events.EPISODE_GAP_DAYS["merger"] (module docstring)
N_PRICED = 167                       # EDGAR_EVENTS_2026-10-12.md §3: the priced, EDGAR-dated sample
SEGMENTS = ("muni", "taxable_income", "equity_other", "bdc")
FINRA_HEADER = ("accountingYearMonthNumber|symbolCode|issueName|issuerServicesGroupExchangeCode|"
                "marketClassCode|currentShortPositionQuantity|previousShortPositionQuantity|stockSplitFlag|"
                "averageDailyVolumeQuantity|daysToCoverQuantity|revisionFlag|changePercent|"
                "changePreviousNumber|settlementDate")


class UnreadCandidate(RuntimeError):
    """A candidate deal that no reading covers. Read its filings, then add a READINGS row."""


class ReadingOutOfDate(RuntimeError):
    """A reading's stated status disagrees with Alpaca today. Re-read the deal."""


# ------------------------------------------------------------------ readings
# Each row is a human reading of the cited documents, made 2026-10-13. `ciks`
# are the EDGAR filers the reading covers; `pairs` are (target, acquirer)
# tickers; `listed_acquirer` is False where the acquirer has no exchange
# listing, so no short leg can exist at any broker. Segment labels follow
# `merger_pairs.classify` on the EDGAR name, except LIEN, a BDC by its own
# filings, which that name regex would call equity_other.

@dataclass(frozen=True)
class Reading:
    key: str
    status: str                       # pending | completed | not_a_merger
    ciks: frozenset
    pairs: tuple = ()
    segment: str = ""
    sponsor: str = ""
    announced: str = ""               # first public date found, with its source
    announced_source: str = ""
    first_edgar: str = ""             # first EDGAR filing of the deal (accession)
    evidence: str = ""                # what decides the status (accession / release)
    listed_acquirer: bool = True
    nav_for_nav: str = ""             # the exchange basis, as the filing states it
    note: str = ""


READINGS = (
    Reading("NZF", "pending", frozenset({1137887, 1607997, 897421}),
            pairs=(("NMS", "NZF"), ("NPV", "NZF")), segment="muni", sponsor="Nuveen",
            announced="2026-04-29",
            announced_source="Business Wire release 'Nuveen Municipal Closed-End Funds Announce Proposed Mergers', "
                             "dateline Chicago 2026-04-29 (syndicated copy, finance.yahoo.com, fetched 2026-10-13)",
            first_edgar="2026-05-13 N-14 8C 0001999371-26-010609 (NZF)",
            evidence="425 of 2026-09-24, 0001999371-26-021258: the special meeting of 2026-09-24 'has been adjourned' "
                     "and 'will reconvene on October 29, 2026'",
            nav_for_nav="merger of each target into NZF (N-14 8C/A 0001999371-26-013622, 'Acquiring Fund')",
            note="NZF is in data/cef/cef_universe.csv: one of the four munis the live book dropped on Alpaca "
                 "(merger_pairs.DROPPED_ON_ALPACA), not one of the 13 it trades"),
    Reading("MMU", "pending", frozenset({886043, 882300}),
            pairs=(("SBI", "MMU"),), segment="muni", sponsor="Franklin Templeton / Western Asset",
            announced="2026-07-31",
            announced_source="Business Wire release 'Western Asset Intermediate Muni Fund Inc. and Western Asset "
                             "Managed Municipals Fund Inc. Announce Board Approval of Proposed Merger Plan' (URL "
                             "dated 20260731; search result, not fetched)",
            first_edgar="2026-08-04 N-14 8C 0001193125-26-332997 (MMU)",
            evidence="424B3 of 2026-09-22, 0001193125-26-397702: SBI special meeting 'on November 18, 2026'",
            nav_for_nav="SBI shares convert into MMU shares 'based on the net asset value' of SBI (424B3)",
            note="SBI's 2023 merger into MMU failed its vote (search summary of the 2023 releases, [S])"),
    Reading("BRW", "pending", frozenset({826020, 828803}),
            pairs=(("SABA", "BRW"),), segment="taxable_income", sponsor="Saba Capital",
            announced="2026-08-20",
            announced_source="Business Wire release of 2026-08-20 'announce reapproval of merger' (syndicated copy, "
                             "finviz.com, fetched 2026-10-13): 'would combine SABA into BRW', target Q4 2026",
            first_edgar="2026-08-27 N-14 8C 0001213900-26-094358 (BRW; placeholders, not effective)",
            evidence="N-14 8C of 2026-08-27 names SABA the Target Fund and BRW the Acquiring Fund; no meeting date set",
            nav_for_nav="not read in the filing",
            note="the first version was terminated: 8-K 2026-03-25, 0001398344-26-005637; RW 0001398344-26-005635"),
    Reading("LIEN", "pending", frozenset({1843162}),
            pairs=(("REFI", "LIEN"),), segment="bdc", sponsor="Chicago Atlantic",
            announced="2026-06-18",
            announced_source="LIEN 8-K item 1.01 filed 2026-06-18, 0001213900-26-069853 (agreement dated 2026-06-17)",
            first_edgar="2026-06-18 8-K 1.01 0001213900-26-069853 (LIEN)",
            evidence="N-14 8C/A of 2026-09-23, 0001140361-26-037360 (meeting date blank); EFFECT 2026-09-30",
            nav_for_nav="'the ratio ... of the Closing REFI NAV to the Closing LIEN NAV' (N-14 8C/A)",
            note="the target REFI is a mortgage REIT, not a fund: outside the CEF/BDC set the fetcher indexes"),
    Reading("VOYA", "pending", frozenset({1385632, 1496292}),
            pairs=(("IAE", "IEMLX"), ("IHD", "IEMLX")), segment="equity_other", sponsor="Voya",
            announced="2026-06-02",
            announced_source="press release filed as 425 on 2026-06-02, 0000895430-26-000004",
            first_edgar="2026-06-02 425 0000895430-26-000004 (filed by Voya Mutual Funds)",
            evidence="425 of 2026-08-24, 0000895430-26-000028: meeting 'on or about September 28, 2026', closing "
                     "'on or about October 16, 2026'",
            listed_acquirer=False,
            nav_for_nav="reorganisation into an open-end fund (IEMLX)",
            note="the acquirer is an open-end mutual fund: no exchange listing, so no short leg exists"),
    Reading("FCT", "completed", frozenset({1282850}),
            pairs=(("FCT", "FFLX"),), segment="taxable_income", sponsor="First Trust",
            evidence="Form 25-NSE of 2026-08-10, 0000876661-26-000668 (FCT delisted); 425 of 2026-05-18, "
                     "0001445546-26-003715: FCT -> First Trust Flexible Income ETF (FFLX), a new ETF"),
    Reading("MFM", "completed", frozenset({801961, 895574, 845606}),
            pairs=(("CMU", "MFM"), ("CXE", "MFM"), ("CXH", "MFM"), ("VFL", "MFM")), segment="muni",
            sponsor="abrdn / MFS",
            evidence="Alpaca corporate actions, stock_merger effective 2026-06-08 (CMU, CXE, CXH) and 2026-07-13 (VFL)"),
    Reading("MMT", "completed", frozenset({809173, 851170}),
            pairs=(("CIF", "MMT"), ("MCR", "MMT")), segment="taxable_income", sponsor="abrdn / MFS",
            evidence="Alpaca corporate actions, stock_merger effective 2026-06-18 (CIF, MCR)"),
    Reading("FRBP", "not_a_merger", frozenset({1825248}),
            evidence="424B3 of 2026-07-06, 0001213900-26-075316: the N-14 8C registers an exchange offer for "
                     "6.000% Notes due 2030"),
    Reading("FDUS", "not_a_merger", frozenset({1513363}),
            evidence="424B3 of 2026-09-16, 0001193125-26-392646: an exchange offer for 6.625% Notes due 2029"),
    Reading("ASA", "not_a_merger", frozenset({1230869}),
            evidence="N-14 8C of 2026-09-10, 0001398344-26-016877: one fund's proposed conversion to a BDC"),
)


# --------------------------------------------------------------- part 1 core

def deal_components(filings: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    """One row per deal: merger-kind filings on/after `start`, funds linked by a shared accession.

    `filings` has cik, form, kind, date_filed, accession, company, ticker_now
    (the fetcher's table). Union-find, so no graph library is needed.
    """
    need = {"cik", "form", "kind", "date_filed", "accession", "company", "ticker_now"}
    if not need <= set(filings.columns):
        raise KeyError(f"deal_components needs {sorted(need - set(filings.columns))}")
    m = filings[(filings["kind"] == "merger") & (filings["date_filed"] >= start)]
    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _, g in m.groupby("accession"):
        cs = [int(c) for c in g["cik"].unique()]
        for c in cs[1:]:
            parent[find(c)] = find(cs[0])
        find(cs[0])
    if m.empty:
        return pd.DataFrame(columns=["component", "ciks", "listed", "first", "last", "n14_filers", "names"])
    m = m.assign(component=[find(int(c)) for c in m["cik"]])
    tk = filings.dropna(subset=["ticker_now"]).groupby("cik")["ticker_now"].first()
    names = filings.sort_values("date_filed").groupby("cik")["company"].last()
    rows = []
    for comp, g in m.groupby("component"):
        ciks = sorted(int(c) for c in g["cik"].unique())
        rows.append({"component": int(comp), "ciks": tuple(ciks),
                     "listed": tuple(c for c in ciks if c in tk.index),
                     "tickers": ";".join(str(tk[c]) for c in ciks if c in tk.index),
                     "first": g["date_filed"].min(), "last": g["date_filed"].max(),
                     "n14_filers": tuple(sorted(int(c) for c in g.loc[g["form"].str.startswith("N-14"), "cik"].unique())),
                     "names": "; ".join(str(names[c]) for c in ciks)})
    return pd.DataFrame(rows)


def candidates(comp: pd.DataFrame, newest: pd.Timestamp, gap_days: int = PENDING_GAP_DAYS) -> pd.DataFrame:
    """Components with a fund listed today and a merger filing within `gap_days` of `newest`."""
    keep = comp["listed"].map(len).gt(0) & (comp["last"] >= newest - pd.Timedelta(days=gap_days))
    return comp[keep].reset_index(drop=True)


def match_readings(cands: pd.DataFrame, readings=READINGS) -> pd.DataFrame:
    """Attach each candidate to exactly one reading, or raise.

    A candidate is covered when its LISTED funds are all inside one reading's
    `ciks`. Unlisted funds (merged away) do not need a reading. A candidate
    touching two readings raises too: one deal cannot have two statuses.
    """
    out = []
    for _, c in cands.iterrows():
        hit = [r for r in readings if set(c["listed"]) & r.ciks]
        if len(hit) != 1 or not set(c["listed"]) <= hit[0].ciks:
            raise UnreadCandidate(
                f"candidate deal {c['tickers']} (CIKs {c['ciks']}, merger filings {c['first'].date()} .. "
                f"{c['last'].date()}: {c['names']}) is covered by {len(hit)} readings "
                f"({[r.key for r in hit]}); read its filings and add or fix a READINGS row")
        out.append({**c.to_dict(), "reading": hit[0].key, "status": hit[0].status})
    return pd.DataFrame(out)


# --------------------------------------------------------------- parsers

def parse_ibkr_shortstock(text: str) -> tuple[pd.DataFrame, str]:
    """IBKR's usa.txt -> (rows, file stamp). Every row, not only the universe.

    `#BOF|YYYY.MM.DD|HH:MM:SS`, then a `#SYM|CUR|NAME|...` header, then
    pipe-delimited rows ending in a trailing pipe. AVAILABLE may read
    '>10000000': the bound is kept in `available_gt`, the number in `available`.
    A row whose fee or availability will not parse raises naming the symbol.
    """
    lines = text.splitlines()
    if not lines or not lines[0].startswith("#BOF|"):
        raise ValueError(f"IBKR shortstock: first line {lines[:1]} is not '#BOF|date|time'")
    _, fdate, ftime = lines[0].split("|")[:3]
    hdr = [h for h in lines[1].lstrip("#").split("|") if h]
    for need in ("SYM", "NAME", "FEERATE", "REBATERATE", "AVAILABLE"):
        if need not in hdr:
            raise ValueError(f"IBKR shortstock header lacks {need}: {hdr}")
    rows = []
    for ln in lines[2:]:
        if not ln.strip() or ln.startswith("#EOF"):
            continue
        f = ln.split("|")
        d = dict(zip(hdr, f))
        av = d["AVAILABLE"].strip()
        try:
            rows.append({"symbol": d["SYM"], "ibkr_name": html.unescape(d["NAME"]),
                         "fee_rate_pct": float(d["FEERATE"]) if d["FEERATE"] not in ("", "NA") else None,
                         "available": float(av.lstrip(">")), "available_gt": av.startswith(">")})
        except ValueError as e:
            raise ValueError(f"IBKR shortstock row for {d.get('SYM')!r} will not parse: {e}") from None
    out = pd.DataFrame(rows)
    if out["symbol"].duplicated().any():
        # The file carries a few symbols twice (different contracts); keep both, flag it.
        out["dup_symbol"] = out["symbol"].duplicated(keep=False)
    return out, f"{fdate.replace('.', '-')} {ftime}"


def parse_finra_si(text: str, label: str) -> pd.DataFrame:
    """One FINRA semi-monthly short-interest file -> symbol, issue name, position, ADV, days to cover."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FINRA_HEADER:
        raise ValueError(f"FINRA {label}: unexpected header {lines[:1]}")
    rows = [ln.split("|") for ln in lines[1:] if ln.strip()]
    bad = [i for i, r in enumerate(rows, 2) if len(r) != 14]
    if bad:
        raise ValueError(f"FINRA {label}: lines {bad[:5]} do not have 14 fields")
    df = pd.DataFrame(rows, columns=FINRA_HEADER.split("|"))
    out = pd.DataFrame({"symbol": df["symbolCode"], "finra_name": df["issueName"],
                        "si_shares": pd.to_numeric(df["currentShortPositionQuantity"], errors="raise"),
                        "adv": pd.to_numeric(df["averageDailyVolumeQuantity"], errors="raise"),
                        "days_to_cover": pd.to_numeric(df["daysToCoverQuantity"], errors="raise"),
                        "settlement": pd.to_datetime(df["settlementDate"])})
    return out


def last_before(dates, d) -> pd.Timestamp | None:
    """The latest of `dates` strictly before `d` (a position settled on the
    announcement day itself could already reflect it), or None."""
    d = pd.Timestamp(d)
    prior = sorted(x for x in map(pd.Timestamp, dates) if x < d)
    return prior[-1] if prior else None


# --------------------------------------------------------------- shares and verdicts

def share_table(df: pd.DataFrame, flag: str, by: str = "segment", unit: str = "deal",
                key: str | None = None) -> pd.DataFrame:
    """Per segment: n in scope, n measured, n True, share True of measured.

    `flag` is True / False / NaN; NaN is UNMEASURED and is never counted as
    False (a name nobody could read is not evidence it cannot be borrowed).
    unit="deal" counts rows; unit="acquirer" first keeps one row per `key`.
    """
    all_df = df
    if unit == "acquirer":
        if key is None:
            raise ValueError("unit='acquirer' needs the acquirer key column")
        # An acquirer with deals in two segments counts in each, and once in "all".
        df, all_df = df.drop_duplicates([by, key]), df.drop_duplicates(key)
    g = df.groupby(by)[flag]
    t = pd.DataFrame({"n": g.size(), "measured": g.apply(lambda s: int(s.notna().sum())),
                      "true": g.apply(lambda s: int((s == True).sum()))})  # noqa: E712
    allrow = pd.DataFrame({"n": [len(all_df)], "measured": [int(all_df[flag].notna().sum())],
                           "true": [int((all_df[flag] == True).sum())]}, index=["all"])  # noqa: E712
    t = pd.concat([t, allrow])
    t["share"] = (t["true"] / t["measured"]).where(t["measured"] > 0)
    return t


def segment_verdict(shares: list) -> str:
    """PASS / FAIL / PARTIAL / UNMEASURED from the Alpaca shares that exist (docstring)."""
    s = [x for x in shares if x is not None and pd.notna(x)]
    if not s:
        return "UNMEASURED"
    if all(x > 0.5 for x in s):
        return "PASS"
    if all(x <= 0.5 for x in s):
        return "FAIL"
    return "PARTIAL"


def crsp_identity(s: pd.DataFrame, nm: pd.DataFrame) -> pd.DataFrame:
    """For each deal row: the acquirer permno's CRSP name record AT the
    announcement (ticker, name, share code), and its LAST record.

    The announcement record gives the ticker to look up in a FINRA file of that
    date: `acq` in the sample is the ticker in force at the TARGET's delisting,
    months later, and a fund can change ticker in between. The last record gives
    today's identity: the permno must still be listed on CRSP's last date
    (CRSP_LAST) and carry the same share code as at the announcement -- a CEF
    that became an ETF (share code 73) or a REIT is no longer the instrument the
    pair would have shorted. A permno with no record covering the announcement
    date raises.
    """
    nm = nm[nm["permno"].isin(set(s["nwperm"]))]
    rows = []
    for perm, ann in zip(s["nwperm"], s["ann"]):
        g = nm[nm["permno"] == perm].sort_values("nameendt")
        at = g[(g["namedt"] <= ann) & (g["nameendt"] >= ann)]
        if len(at) != 1:
            raise ValueError(f"permno {perm}: {len(at)} CRSP name records cover {ann.date()}")
        a, e = at.iloc[0], g.iloc[-1]
        alive = str(e["nameendt"].date()) == CRSP_LAST
        same = alive and int(e["shrcd"]) == int(a["shrcd"])
        rows.append({"ticker_at_ann": a["ticker"], "comnam_at_ann": a["comnam"], "shrcd_at_ann": int(a["shrcd"]),
                     "ticker_end": e["ticker"], "comnam_end": e["comnam"], "shrcd_end": int(e["shrcd"]),
                     "nameendt_end": str(e["nameendt"].date()),
                     "crsp_end_state": ("same_share_code" if same else
                                        "gone_by_crsp_end" if not alive else "share_code_changed"),
                     "ticker_today": e["ticker"] if same else None})
    return pd.DataFrame(rows, index=s.index)


def edgar_names(client, cik: int) -> list:
    """A CIK's current EDGAR name and every former name (submissions API)."""
    from scripts.data.fetch_edgar_events import SUBMISSIONS_URL
    j = client.get_json(SUBMISSIONS_URL.format(cik=cik), max_age_s=7 * 86400)
    return [j["name"]] + [f["name"] for f in j.get("formerNames", []) if f.get("name")]


FINRA_NAME_WIDTH = 30     # FINRA's issueName is cut at 30 characters (measured in the files)


def finra_name_score(crsp_name: str, finra_name: str) -> float:
    """`edgar_merger_dates.name_score` adapted to FINRA's 30-character issue names.

    A FINRA name of full width is cut mid-word, so its last token is dropped,
    and only as many leading CRSP tokens are scored as FINRA tokens remain
    (CRSP abbreviates, FINRA truncates: the tails are not comparable). A
    sanity flag on a ticker matched on the same date, not an identity test.
    """
    from scripts.events.edgar_merger_dates import name_score, name_tokens
    ft = name_tokens(finra_name)
    if len(finra_name.rstrip()) >= FINRA_NAME_WIDTH and len(ft) > 1:
        ft = ft[:-1]
    ct = name_tokens(crsp_name)[:max(len(ft), 2)]
    return name_score(ct, ft)


def identity_today(r: dict) -> str:
    """Is Alpaca's asset under `ticker_today` the acquirer? (module docstring, H3)"""
    from scripts.events.edgar_merger_dates import MIN_SCORE
    if r["crsp_end_state"] != "same_share_code":
        return r["crsp_end_state"]
    if not r.get("alp_found"):
        return "not_on_alpaca"
    if r.get("alp_status") != "active":
        return "inactive_on_alpaca"
    sc = r.get("alp_name_score")
    return "same_fund" if sc is not None and sc >= MIN_SCORE else f"name_mismatch({sc})"


# --------------------------------------------------------------- fetchers (network)

def _http_get(url: str, timeout: int = 60) -> tuple[int, bytes]:
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; read-only)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def ibkr_file(today: str, offline: bool) -> tuple[pd.DataFrame, str]:
    p = CACHE / f"ibkr_usa_{today}.txt"
    if not p.exists():
        if offline:
            raise FileNotFoundError(f"offline and no cached IBKR file {p.name}")
        code, body = _http_get(IBKR_URL)
        if code != 200:
            raise RuntimeError(f"GET {IBKR_URL} -> HTTP {code}")
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
    return parse_ibkr_shortstock(p.read_text(encoding="utf-8", errors="replace"))


class FinraFiles:
    """FINRA semi-monthly files, found by probing back from a date; cached, absences too."""

    def __init__(self, offline: bool, pause_s: float = 0.25):
        self.offline, self.pause = offline, pause_s
        self.dir = CACHE / "finra"
        self.absent_path = self.dir / "_absent.json"
        self.absent = set(json.loads(self.absent_path.read_text())) if self.absent_path.exists() else set()
        self.requests = 0

    def get(self, d: date) -> pd.DataFrame | None:
        key = d.strftime("%Y%m%d")
        p = self.dir / f"shrt{key}.csv"
        if p.exists():
            return parse_finra_si(p.read_text(encoding="utf-8", errors="replace"), key)
        if key in self.absent:
            return None
        if self.offline:
            raise FileNotFoundError(f"offline and FINRA {key} neither cached nor known absent")
        time.sleep(self.pause)
        self.requests += 1
        code, body = _http_get(FINRA_URL.format(d=key))
        self.dir.mkdir(parents=True, exist_ok=True)
        if code == 200:
            p.write_bytes(body)
            return parse_finra_si(body.decode("utf-8", errors="replace"), key)
        if code in (403, 404):     # S3's answer for a key that does not exist
            self.absent.add(key)
            self.absent_path.write_text(json.dumps(sorted(self.absent)))
            return None
        raise RuntimeError(f"GET {FINRA_URL.format(d=key)} -> HTTP {code}")

    def last_before(self, d: pd.Timestamp) -> pd.DataFrame | None:
        """The newest file settled strictly before `d`, probing back at most FINRA_MAX_LOOKBACK_DAYS."""
        for k in range(1, FINRA_MAX_LOOKBACK_DAYS + 1):
            x = (d - pd.Timedelta(days=k)).date()
            if x < FINRA_FIRST:
                return None
            if x.weekday() >= 5:
                continue
            f = self.get(x)
            if f is not None:
                return f
        raise RuntimeError(f"no FINRA file in the {FINRA_MAX_LOOKBACK_DAYS} days before {d.date()}")


def alpaca_reads(symbols, today: str, offline: bool) -> pd.DataFrame:
    """GET /v2/assets/{symbol} for each symbol, cached as one JSON per day."""
    p = CACHE / f"alpaca_assets_{today}.json"
    have = json.loads(p.read_text()) if p.exists() else {}
    want = sorted(set(symbols) - set(have))
    if want:
        if offline:
            raise FileNotFoundError(f"offline and {len(want)} symbols not in {p.name}: {want[:10]}")
        from quantt.broker.alpaca import AlpacaClient, AssetNotFound
        client = AlpacaClient.from_environment("cef")
        for s in want:
            t = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                a = client.asset(s)
                have[s] = {"read_utc": t, "found": True, **{k: a.get(k) for k in (
                    "name", "status", "exchange", "tradable", "shortable", "easy_to_borrow", "borrow_status")}}
            except AssetNotFound:
                have[s] = {"read_utc": t, "found": False}
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(have, indent=1, sort_keys=True))
    return pd.DataFrame([{"symbol": s, **have[s]} for s in sorted(set(symbols))])


def alpaca_mergers(today: str, offline: bool) -> pd.DataFrame:
    """Stock / stock-and-cash mergers effective in the last 365 days or listed ahead (two years)."""
    p = CACHE / f"alpaca_mergers_{today}.json"
    if not p.exists():
        if offline:
            raise FileNotFoundError(f"offline and no cached {p.name}")
        from quantt.broker.alpaca import AlpacaClient
        from scripts.events.acquirer_shortability import recent_mergers
        rm = recent_mergers(AlpacaClient.from_environment("cef"))
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_text(rm.to_json(orient="records"))
    return pd.read_json(p, orient="records", dtype={"effective_date": str})


# --------------------------------------------------------------- checks

def check_readings(readings, flags: pd.DataFrame, feed: pd.DataFrame, today: str) -> list:
    """Each reading's status against Alpaca today; a disagreement raises ReadingOutOfDate.

    pending   -> every listed target is an active Alpaca asset and the feed has no
                 effective merger for it on or before today;
    completed -> the feed has an effective merger for each target, or the target
                 is no longer an active asset.
    """
    f = flags.set_index("symbol")
    eff = feed[pd.to_datetime(feed["effective_date"]) <= pd.Timestamp(today)]
    done = set(eff["acquiree_symbol"])
    notes = []
    for r in readings:
        for tgt, _acq in r.pairs:
            active = tgt in f.index and bool(f.loc[tgt, "found"]) and f.loc[tgt, "status"] == "active"
            if r.status == "pending" and (not active or tgt in done):
                raise ReadingOutOfDate(f"{r.key}: target {tgt} is no longer pending (active={active}, "
                                       f"effective merger in feed={tgt in done}); re-read the deal")
            if r.status == "completed" and active and tgt not in done:
                raise ReadingOutOfDate(f"{r.key}: target {tgt} is still active and the feed shows no merger")
            notes.append({"reading": r.key, "target": tgt, "status": r.status, "target_active_today": active,
                          "feed_effective_merger": tgt in done})
    return notes


# --------------------------------------------------------------- main

def run(today: str, offline: bool) -> dict:
    from scripts.data.edgar_client import EdgarClient
    from scripts.data import fetch_edgar_events as fe
    from scripts.events.crsp_events import names
    from scripts.events.merger_pairs import classify
    from scripts.events.edgar_merger_dates import MIN_SCORE, name_score, name_tokens

    summary: dict = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "as_of": today}

    # ---------------- part 1: pending deals
    res = fe.build(EdgarClient(offline=offline), date.fromisoformat(today))
    filings = res["filings"]
    newest = filings["date_filed"].max()
    comp = deal_components(filings, newest - pd.Timedelta(days=2 * PENDING_GAP_DAYS))
    cands = match_readings(candidates(comp, newest))
    summary["edgar"] = {"newest_filing_date_in_index": str(newest.date()),
                        "components_since": str((newest - pd.Timedelta(days=2 * PENDING_GAP_DAYS)).date()),
                        "candidates": cands[["tickers", "first", "last", "reading", "status"]]
                        .astype(str).to_dict("records")}
    pend = [r for r in READINGS if r.status == "pending"]
    pend_syms = {s for r in pend for p in r.pairs for s in p} | {t for r in READINGS for t, _ in r.pairs}

    # ---------------- part 2 inputs: the 167 deals
    s = pd.read_csv(SAMPLE, parse_dates=["ann", "completion"])
    s = s[s["status"].isin(["ok", "bridged"])].copy()
    if len(s) != N_PRICED:
        raise ValueError(f"{SAMPLE.name}: {len(s)} priced deals, expected {N_PRICED}")
    s["segment"] = s["cls"]
    s = s.join(crsp_identity(s, names()))

    # ---------------- Alpaca today, one read for everything
    flags = alpaca_reads(sorted(pend_syms | set(s["ticker_today"].dropna())), today, offline)
    feed = alpaca_mergers(today, offline)
    summary["reading_checks"] = check_readings(READINGS, flags, feed, today)
    fut = feed[pd.to_datetime(feed["effective_date"]) > pd.Timestamp(today)]
    summary["alpaca_feed_future_dated"] = fut[["effective_date", "acquiree_symbol", "acquirer_symbol"]] \
        .astype(str).values.tolist()
    ib, stamp = ibkr_file(today, offline)
    ibx = ib.drop_duplicates("symbol").set_index("symbol")
    summary["ibkr_file_stamp"] = stamp

    def ibkr(sym):
        if sym in ibx.index:
            r = ibx.loc[sym]
            return {"ibkr_listed": True, "ibkr_fee_pct": r["fee_rate_pct"], "ibkr_available": r["available"],
                    "ibkr_available_gt": bool(r["available_gt"])}
        return {"ibkr_listed": False, "ibkr_fee_pct": None, "ibkr_available": 0.0, "ibkr_available_gt": False}

    fx = flags.set_index("symbol")
    uni = set(pd.read_csv(UNIVERSE)["ticker"])
    prow = []
    for r in pend:
        for tgt, a in r.pairs:
            fa = fx.loc[a].to_dict() if a in fx.index else {}
            ft = fx.loc[tgt].to_dict() if tgt in fx.index else {}
            prow.append({"target": tgt, "acquirer": a, "segment": r.segment, "sponsor": r.sponsor,
                         "announced": r.announced, "first_edgar": r.first_edgar, "status_evidence": r.evidence,
                         "listed_acquirer": r.listed_acquirer,
                         "acq_alpaca_found": fa.get("found", False), "acq_status": fa.get("status"),
                         "acq_tradable": fa.get("tradable"), "acq_shortable": fa.get("shortable"),
                         "acq_easy_to_borrow": fa.get("easy_to_borrow"), "acq_borrow_status": fa.get("borrow_status"),
                         "acq_read_utc": fa.get("read_utc"),
                         **{f"acq_{k}": v for k, v in ibkr(a).items()},
                         "tgt_status": ft.get("status"), "tgt_tradable": ft.get("tradable"),
                         "tgt_shortable": ft.get("shortable"), **{f"tgt_{k}": v for k, v in ibkr(tgt).items()},
                         "acq_in_cef_universe": a in uni, "tgt_in_cef_universe": tgt in uni})
    P = pd.DataFrame(prow)
    # A short leg exists today only if the acquirer is listed AND Alpaca says shortable.
    P["hedge_buildable_alpaca"] = P["listed_acquirer"] & (P["acq_shortable"] == True)  # noqa: E712
    P["hedge_buildable_ibkr"] = P["listed_acquirer"] & (P["acq_ibkr_available"] > 0)

    # ---------------- historical measures
    # H3: Alpaca today, same fund.
    s = s.merge(flags.add_prefix("alp_"), left_on="ticker_today", right_on="alp_symbol", how="left")
    s["alp_name_score"] = [
        round(name_score(name_tokens(c), name_tokens(n)), 3) if isinstance(n, str) and isinstance(c, str) else None
        for c, n in zip(s["comnam_end"], s["alp_name"])]
    s["alp_identity"] = [identity_today(r) for r in s.to_dict("records")]
    # A renamed fund fails the name check against CRSP's 2024 name. Second
    # route: the SEC ticker file maps today's ticker to a CIK, and that CIK's
    # EDGAR name history must contain a name matching CRSP's. A ticker now
    # carried by a different company (BNY: BNY Mellon) fails both.
    t2c = (filings.dropna(subset=["ticker_now"]).assign(t=lambda d: d["ticker_now"].str.split(";"))
           .explode("t").drop_duplicates(["t", "cik"]).groupby("t")["cik"].apply(list))
    edgar_client = EdgarClient(offline=offline)
    ed_score = []
    for r in s.to_dict("records"):
        if not str(r["alp_identity"]).startswith("name_mismatch"):
            ed_score.append(None)
            continue
        best = 0.0
        for cik in t2c.get(r["ticker_today"], []):
            for n in edgar_names(edgar_client, int(cik)):
                best = max(best, name_score(name_tokens(r["comnam_end"]), name_tokens(n)))
        ed_score.append(round(best, 3))
    s["edgar_name_history_score"] = ed_score
    s.loc[s["edgar_name_history_score"].fillna(0) >= MIN_SCORE, "alp_identity"] = "same_fund_by_edgar_name"
    s["same_fund_today"] = s["alp_identity"].isin(["same_fund", "same_fund_by_edgar_name"])
    s["H3_alpaca_shortable_today"] = s["alp_shortable"].where(s["same_fund_today"]).astype("object")
    # H4: IBKR file today, same names.
    s["H4_ibkr_available_today"] = [
        (t in ibx.index and ibx.loc[t, "available"] > 0) if ok else None
        for t, ok in zip(s["ticker_today"], s["same_fund_today"])]
    # H1: IBKR FEE_RATE history at announcement.
    bh = pd.read_parquet(BORROW_HISTORY)
    first_fee = bh.groupby("ticker")["date"].min()
    s["H1_fee_covered"] = [a in first_fee.index and pd.Timestamp(d) > first_fee[a] for a, d in zip(s["acq"], s["ann"])]
    # H2: FINRA short interest at the last settlement before announcement.
    ff = FinraFiles(offline)
    h2 = []
    for _, r in s.iterrows():
        if r["ann"].date() <= FINRA_FIRST:
            h2.append({"H2_settlement": None, "H2_si_shares": None, "H2_days_to_cover": None,
                       "H2_finra_name": None, "H2_name_score": None, "H2_si_positive": None})
            continue
        f = ff.last_before(r["ann"])
        row = f[f["symbol"] == r["ticker_at_ann"]]
        if row.empty:
            h2.append({"H2_settlement": str(f["settlement"].iloc[0].date()), "H2_si_shares": 0,
                       "H2_days_to_cover": None, "H2_finra_name": None, "H2_name_score": None,
                       "H2_si_positive": False})
            continue
        x = row.iloc[0]
        sc = finra_name_score(r["comnam_at_ann"], x["finra_name"])
        h2.append({"H2_settlement": str(x["settlement"].date()), "H2_si_shares": int(x["si_shares"]),
                   "H2_days_to_cover": float(x["days_to_cover"]), "H2_finra_name": x["finra_name"],
                   "H2_name_score": round(sc, 3), "H2_si_positive": bool(x["si_shares"] > 0)})
    s = pd.concat([s.reset_index(drop=True), pd.DataFrame(h2)], axis=1)
    summary["finra_requests_this_run"] = ff.requests

    # H1b: universe-name acquirers in later deals that the fee history does cover
    # (fees, not returns; the 167 exclude every universe name by construction).
    ep = res["episodes"]
    ep = ep[(ep["kind"] == "merger") & ep["forms"].str.contains("N-14 8C", regex=False)].copy()
    ep["first_date"] = pd.to_datetime(ep["first_date"])
    ep["tk"] = ep["ticker_now"].fillna("").str.split(";")
    ep = ep.explode("tk")
    ep = ep[ep["tk"].isin(first_fee.index) & (ep["first_date"] > ep["tk"].map(first_fee))]
    # An episode that opens with an amendment continues an earlier deal (its
    # first filing fell more than the episode gap before): not an announcement.
    ep = ep[~ep["first_form"].str.endswith("/A")]
    bhp = bh.pivot(index="date", columns="ticker", values="fee_rate_pct").sort_index()
    h1b = []
    for _, e in ep.iterrows():
        fees = bhp[e["tk"]].dropna()
        fd = last_before(fees.index, e["first_date"])     # the fee known before the filing day
        h1b.append({"acquirer": e["tk"], "segment": classify(str(e["company_last"]).upper()),
                    "first_merger_filing": str(e["first_date"].date()),
                    "first_form": e["first_form"], "last_merger_filing": str(e["last_date"]),
                    "fee_date": str(fd.date()) if fd is not None else None,
                    "fee_rate_pct": float(fees.loc[fd]) if fd is not None else None})
    summary["H1b_universe_acquirers_fee_at_first_filing"] = h1b
    hb = pd.DataFrame(h1b)
    summary["H1b_fee_summary"] = hb.groupby("segment")["fee_rate_pct"].agg(
        ["count", "min", "median", "max"]).round(2).reset_index().to_dict("records") if len(hb) else []

    # ---------------- tables
    tabs = {}
    # Today's flags are one value per acquirer, so both units are shown. H1 and
    # H2 are dated per deal (an acquirer's position differs across its deals),
    # so they are deal-weighted only.
    for name, col, units in (("H3_alpaca_today", "H3_alpaca_shortable_today", ("deal", "acquirer")),
                             ("H4_ibkr_today", "H4_ibkr_available_today", ("deal", "acquirer")),
                             ("H2_finra_si_positive", "H2_si_positive", ("deal",)),
                             ("H1_fee_history_covered", "H1_fee_covered", ("deal",))):
        for unit in units:
            t = share_table(s, col, unit=unit, key="nwperm")
            tabs[f"{name}_{unit}"] = t.reset_index().rename(columns={"index": "segment"}).to_dict("records")
    tabs["identity_today"] = s.groupby(["segment", "alp_identity"]).size().rename("deals").reset_index().to_dict("records")
    # Row-level lists carry CRSP names (licensed): they go to the gitignored
    # detail file; the tracked summary keeps their counts.
    detail = {}
    low = s["H2_name_score"].notna() & (s["H2_name_score"] < MIN_SCORE)
    detail["H2_name_score_below_min"] = s.loc[low, ["ticker_at_ann", "comnam_at_ann", "H2_finra_name",
                                                    "H2_name_score"]].drop_duplicates().astype(str).values.tolist()
    tabs["H2_coverage"] = {"deals_announced_after_first_file": int((s["ann"].dt.date > FINRA_FIRST).sum()),
                           "deals_with_name_score_below_min": int(low.sum())}
    mis = s["alp_identity"].str.startswith("name_mismatch")
    detail["H3_identity_failures"] = s.loc[mis, ["ticker_today", "comnam_end", "alp_name", "alp_name_score",
                                                 "edgar_name_history_score"]].drop_duplicates().astype(str).values.tolist()
    detail["H3_same_fund_by_edgar_name"] = s.loc[s["alp_identity"] == "same_fund_by_edgar_name",
                                                 ["ticker_today", "comnam_end", "alp_name"]] \
        .drop_duplicates().astype(str).values.tolist()
    tabs["H3_identity_failure_deals"] = int(mis.sum())
    # How big a shortable-only sample would be, on today's flags (a count).
    sh = s[s["H3_alpaca_shortable_today"] == True]  # noqa: E712
    tabs["H3_shortable_today_deals_and_groups"] = {
        seg: {"deals": int((sh["segment"] == seg).sum()),
              "acquirer_x_announcement_groups": int(sh.loc[sh["segment"] == seg, ["nwperm", "ann"]]
                                                    .drop_duplicates().shape[0])}
        for seg in SEGMENTS}
    per_acq = s[s["same_fund_today"]].drop_duplicates("nwperm")
    detail["H3_H4_by_acquirer"] = per_acq[["segment", "ticker_today", "alp_shortable", "alp_easy_to_borrow",
                                         "alp_borrow_status", "H4_ibkr_available_today"]] \
        .sort_values(["segment", "ticker_today"]).astype(str).values.tolist()
    pos = s[s["H2_si_positive"] == True]  # noqa: E712
    tabs["H2_positive_si_by_segment"] = pos.groupby("segment").agg(
        deals=("acq", "size"), median_si_shares=("H2_si_shares", "median"),
        median_days_to_cover=("H2_days_to_cover", "median")).reset_index().to_dict("records")
    # The verdict counts LISTED acquirers only: a merger into an open-end fund or
    # a new ETF has no short leg at any broker and no pair, and the 167-deal
    # sample (both legs CRSP-listed) contains no such deal either. Those deals
    # are reported beside the table, not inside it.
    tabs["pending_no_listed_acquirer"] = P.loc[~P["listed_acquirer"], ["target", "acquirer", "segment"]] \
        .to_dict("records")
    PL = P[P["listed_acquirer"]]
    P_seg = PL.assign(flag=PL["hedge_buildable_alpaca"].astype(object))
    pend_tab = share_table(P_seg, "flag", unit="deal")
    pend_tab_acq = share_table(P_seg, "flag", unit="acquirer", key="acquirer")
    tabs["pending_alpaca_deal"] = pend_tab.reset_index().rename(columns={"index": "segment"}).to_dict("records")
    tabs["pending_alpaca_acquirer"] = pend_tab_acq.reset_index().rename(columns={"index": "segment"}).to_dict("records")
    tabs["pending_ibkr_deal"] = share_table(PL.assign(flag=PL["hedge_buildable_ibkr"].astype(object)), "flag") \
        .reset_index().rename(columns={"index": "segment"}).to_dict("records")

    # ---------------- verdicts
    h3 = share_table(s, "H3_alpaca_shortable_today", unit="acquirer", key="nwperm")
    verdicts = {}
    for seg in SEGMENTS + ("all",):
        sh = [pend_tab_acq["share"].get(seg), h3["share"].get(seg)]
        verdicts[seg] = {"pending_acquirers_shortable_share": None if pd.isna(sh[0]) else round(float(sh[0]), 3),
                         "historical_acquirers_shortable_today_share": None if pd.isna(sh[1]) else round(float(sh[1]), 3),
                         "verdict": segment_verdict(sh)}
    summary["tables"] = tabs
    summary["verdicts"] = verdicts
    return {"summary": summary, "detail": detail, "pending": P, "historical": s, "candidates": cands}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true", help="caches only; no network")
    ap.add_argument("--today", default=date.today().isoformat(), help="the as-of date (YYYY-MM-DD)")
    a = ap.parse_args(argv)
    out = run(a.today, a.offline)
    G1A_DIR.mkdir(parents=True, exist_ok=True)
    out["pending"].to_csv(G1A_DIR / f"g1a_pending_{a.today}.csv", index=False)
    out["historical"].to_csv(G1A_DIR / "g1a_historical_deals.csv", index=False)      # gitignored: CRSP-joined
    (G1A_DIR / f"g1a_summary_{a.today}.json").write_text(json.dumps(out["summary"], indent=1, default=str))
    (G1A_DIR / f"g1a_detail_{a.today}.json").write_text(json.dumps(out["detail"], indent=1, default=str))  # gitignored
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    P = out["pending"]
    print(P[["target", "acquirer", "segment", "listed_acquirer", "acq_status", "acq_shortable", "acq_easy_to_borrow",
             "acq_borrow_status", "acq_ibkr_fee_pct", "acq_ibkr_available", "hedge_buildable_alpaca"]].to_string(index=False))
    print(json.dumps(out["summary"]["verdicts"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
