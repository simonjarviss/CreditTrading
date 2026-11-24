"""A4 census: BDCs that listed on an exchange after a period of public reporting while unlisted (zero trials).

    export QUANTT_ENV_FILE=/abs/path/config/.env      # R2 + SEC_USER_AGENT; never printed
    python3 scripts/events/ssx/ssx_fund2_bdc_listings.py candidates        # offline index + CRSP headers
    python3 scripts/events/ssx/ssx_fund2_bdc_listings.py docs [--max-new N] # live: listing filings, lock-up text
    python3 scripts/events/ssx/ssx_fund2_bdc_listings.py terms              # offline: verify coded quotes, date releases
    python3 scripts/events/ssx/ssx_fund2_bdc_listings.py adv                # R2: pre-release ADV, releases <= 2022 only

WHY THIS EXISTS
---------------
Idea A4 (ssx brief, 2026-10-19): when a non-traded (or privately offered) BDC
lists, its pre-listing holders are released to sell on dates fixed IN ADVANCE
by a lock-up or by a staggered share-class conversion. A release date is a
known supply event in a security with no creation/redemption mechanism. The
kill gate is a COUNT: fewer than 30 lock-up release events in 2010-2025 -> D7.
So this script counts listings and release events. It computes no return.

THE EVENT DEFINITION, AND WHY EACH PART
---------------------------------------
1. A BDC: a CIK that filed Form N-54A (the §54(a) election) or N-6F (notice
   of intent to elect) in the 2008-2025 indexes. A BDC that elected before
   2008 and never re-filed is missed; for 2010+ listings of BDCs that had
   been REPORTING while unlisted, the election normally falls inside the
   window (stated as a recall gap).
2. Listed: the CRSP CIZ header's first trading date (`securitybegdt`) of a
   security of subtype CEF (CRSP files BDCs as CEF, measured 2026-10-19),
   matched to the BDC CIK by normalised issuer name; cross-checked against the
   CIK's own 8-A12B / 8-A12B/A filing dates (an 8-A12B registers a class on an
   exchange under §12(b)). The brief asked for exactly this cross-check. The
   CRSP header is read for DATES only; no price, no return.
3. Prior history: the CIK filed a 10-K or 10-Q at least 180 days before its
   first trading date. That is what makes it a pre-existing holder base with a
   lock-up problem rather than a new IPO. 180 days is a stated choice (one
   semi-annual reporting cycle), not fitted to anything.
4. Dates are counted to 2025-12-31 (brief). CRSP's header carries 2025 first
   trading dates on the mirror read 2026-10-19 (FSSL, 2025-11-13), so 2025 is
   covered by CRSP as well as by the 8-A12B; any disagreement is printed.

WHAT IS A "RELEASE EVENT"
-------------------------
A date on which a block of pre-listing shares becomes freely saleable under a
term stated in a filing: the end of a lock-up for pre-IPO holders, or each
tranche of a staggered conversion (e.g. one third at 60, 120, 180 days). One
listing can contribute several. They are read from the listing filings by the
`docs` step (live, budgeted), and every coded term carries its quoted span.
Releases of one listing are NOT independent of each other; the note reports
listings and release events side by side.

OUTPUTS
-------
`results/events/ssx/ssx_fund2/a4_bdc_listing_candidates.csv`  (EDGAR facts + CRSP first-trade dates; no permnos, no prices;
                                                              the row file with permnos is in the gitignored cache)
`results/events/ssx/ssx_fund2/a4_lockup_terms.csv`             (per listing: documents read, spans)
`results/events/ssx/ssx_fund2/a4_summary.json`

NO SILENT FALLBACKS: an unmatched name is reported as unmatched; a listing
with no lock-up text found is a stated gap, never "no lock-up".
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.events.ssx.ssx_fund2_common import (OUT, CACHE, load_index, now_utc, BudgetedClient,  # noqa: E402
                                                 budget_used)

CAND_OUT = CACHE / "a4_bdc_listing_candidates_rows.csv"      # carries CRSP permnos: licensed, cache only
CAND_PUBLIC = OUT / "a4_bdc_listing_candidates.csv"          # the same rows without CRSP identifiers
TERMS_OUT = OUT / "a4_lockup_terms.csv"
SUMMARY_OUT = OUT / "a4_summary.json"
PRIOR_DAYS = 180
LIST_START, LIST_END = pd.Timestamp("2010-01-01"), pd.Timestamp("2025-12-31")

_STOP = {"INC", "CORP", "CORPORATION", "CO", "LTD", "LLC", "LP", "THE", "FUND", "FD", "COMPANY", "NEW", "DE", "MD"}
# CRSP's 32-character issuer names abbreviate; these are the abbreviations met in
# the BDC rows (read 2026-10-19), expanded so the key matches EDGAR's full name.
_ABBR = {"FIN": "FINANCE", "DIR": "DIRECT", "LEND": "LENDING", "GR": "GROWTH", "RT": "RATE", "CAP": "CAPITAL",
         "INVT": "INVESTMENT", "SPECLTY": "SPECIALTY"}


def norm(name: str) -> str:
    """A space-free match key: upper-case, punctuation dropped, CRSP abbreviations expanded, stop words dropped.

    Space-free so CRSP's spaced initials ("F S K K R", "B D C") meet EDGAR's
    ("FS KKR", "BDC"). A collision can only ADD a candidate, and every
    candidate is read by hand in the `docs` step, so it cannot pass silently.
    """
    s = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper().replace("&#298;", "I"))
    toks = [_ABBR.get(t, t) for t in s.split()]
    return "".join(t for t in toks if t not in _STOP)


def crsp_cef_headers() -> pd.DataFrame:
    """CRSP CIZ security headers, subtypes CEF and COM (all begin dates, so an older listing is seen): permno, first/last date, names, tickers (no prices).

    COM is included because CRSP files some BDCs as COM (CCT 2017, OTF 2025; read 2026-10-19)."""
    from src.data.r2 import connect, r2_path, q
    con = connect()
    p = r2_path("crsp_a_stock", "stksecurityinfohist")
    d = q(con, f"""SELECT permno, securitybegdt, securityenddt, issuernm, ticker, cusip, secinfostartdt
                   FROM read_parquet('{p}') WHERE securitysubtype IN ('CEF', 'COM')""")
    if d.empty:
        raise RuntimeError("CRSP stksecurityinfohist: no CEF/COM rows")
    d["securitybegdt"] = pd.to_datetime(d["securitybegdt"])
    d["securityenddt"] = pd.to_datetime(d["securityenddt"])
    g = d.sort_values("secinfostartdt").groupby("permno").agg(
        beg=("securitybegdt", "min"), end=("securityenddt", "max"),
        names=("issuernm", lambda s: sorted(set(map(str, s)))), tickers=("ticker", lambda s: sorted(set(map(str, s)))),
        first_cusip=("cusip", "first")).reset_index()
    return g


def candidates() -> dict:
    idx = load_index()
    idx["date_filed"] = pd.to_datetime(idx["date_filed"])
    bdc = idx[idx["form"].isin(["N-54A", "N-6F"])].groupby("cik").agg(
        elect_first=("date_filed", "min"), elect_form=("form", "first"))
    names = idx[idx["cik"].isin(bdc.index)].groupby("cik")["company"].agg(lambda s: sorted(set(s)))
    per = idx[idx["cik"].isin(bdc.index) & idx["form"].isin(["10-K", "10-Q"])].groupby("cik")["date_filed"].min()
    k10 = idx[idx["cik"].isin(bdc.index) & (idx["form"] == "10-K")].groupby("cik")["date_filed"].min()
    a8 = idx[idx["cik"].isin(bdc.index) & idx["form"].isin(["8-A12B", "8-A12B/A"])].groupby("cik")["date_filed"].agg(
        lambda s: sorted(x.date().isoformat() for x in s))
    n54c = idx[idx["cik"].isin(bdc.index) & (idx["form"] == "N-54C")].groupby("cik")["date_filed"].min()

    crsp = crsp_cef_headers()
    crsp_by_norm: dict[str, list[int]] = {}
    for r in crsp.itertuples(index=False):
        for n in r.names:
            crsp_by_norm.setdefault(norm(n), []).append(int(r.permno))
    crsp_i = crsp.set_index("permno")
    # Second bridge: the SEC's CIK -> ticker file (cached 2026-10-12, offline) against CRSP
    # tickers of securities still active at the header's end. Live names only, by design.
    from scripts.data.fetch_edgar_events import TICKERS_URL
    from scripts.events.ssx.ssx_fund2_common import offline_client
    j = offline_client().get_json(TICKERS_URL, max_age_s=None)   # the cached copy of 2026-10-12, stated
    if j.get("fields") != ["cik", "name", "ticker", "exchange"]:
        raise ValueError(f"company_tickers_exchange.json fields changed: {j.get('fields')}")
    tk = pd.DataFrame(j["data"], columns=j["fields"])
    tk_by_cik = tk.groupby("cik")["ticker"].agg(lambda v: set(map(str, v))).to_dict()
    end = crsp["end"].max()
    crsp_live_by_ticker: dict[str, list[int]] = {}
    for r in crsp[crsp["end"] == end].itertuples(index=False):
        for t in r.tickers:
            crsp_live_by_ticker.setdefault(t, []).append(int(r.permno))

    rows = []
    for cik in bdc.index:
        cn = names.get(cik, [])
        permnos = sorted({p for n in cn for p in crsp_by_norm.get(norm(n), [])}
                         | {p for t in tk_by_cik.get(int(cik), set()) for p in crsp_live_by_ticker.get(t, [])})
        first_trade = min((crsp_i.loc[p, "beg"] for p in permnos), default=pd.NaT)
        rows.append({"cik": int(cik), "edgar_names": " | ".join(cn), "elect_first": bdc.loc[cik, "elect_first"].date(),
                     "n54c_first": n54c.get(cik, pd.NaT), "first_periodic": per.get(cik, pd.NaT),
                     "first_10k": k10.get(cik, pd.NaT), "a8_dates": ";".join(a8.get(cik, [])),
                     "crsp_permnos": ";".join(map(str, permnos)),
                     "crsp_tickers": ";".join(sorted({t for p in permnos for t in crsp_i.loc[p, "tickers"]})),
                     "crsp_first_trade": first_trade})
    df = pd.DataFrame(rows)
    for c in ("first_periodic", "first_10k", "crsp_first_trade", "n54c_first"):
        df[c] = pd.to_datetime(df[c])

    # Listing date: CRSP first trade if matched; else the first 8-A12B/A dated after the first periodic report.
    def a8_after(r):
        if not r.a8_dates:
            return pd.NaT
        ds = [pd.Timestamp(x) for x in r.a8_dates.split(";")]
        if pd.notna(r.first_periodic):
            ds = [x for x in ds if x - r.first_periodic >= pd.Timedelta(days=PRIOR_DAYS)]
        return min(ds) if ds else pd.NaT
    df["a8_after_history"] = df.apply(a8_after, axis=1)
    df["listing_date"] = df["crsp_first_trade"].where(df["crsp_first_trade"].notna(), df["a8_after_history"])
    df["listing_basis"] = df["crsp_first_trade"].notna().map({True: "crsp_first_trade", False: "8-A12B_after_history"})
    df.loc[df["listing_date"].isna(), "listing_basis"] = "not_listed_by_either"
    df["prior_history_days"] = (df["listing_date"] - df["first_periodic"]).dt.days
    df["in_window"] = df["listing_date"].between(LIST_START, LIST_END)
    df["has_prior_history"] = df["prior_history_days"] >= PRIOR_DAYS
    # A former BDC that withdrew its election (N-54C) BEFORE listing listed as an operating company, not a BDC.
    df["withdrew_before_listing"] = df["n54c_first"].notna() & (df["n54c_first"] < df["listing_date"])
    df["a8_within_30d_of_crsp"] = [
        (pd.notna(r.crsp_first_trade) and any(abs((pd.Timestamp(x) - r.crsp_first_trade).days) <= 30
                                              for x in (r.a8_dates.split(";") if r.a8_dates else [])))
        for r in df.itertuples(index=False)]
    # The BDC election must precede the listing: a CIK that elected AFTER its 8-A12B listed as
    # something else (measured 2026-10-19: HighLight Networks, 8-A12B 2011-11-21, N-54A 2013-11-08).
    df["elected_before_listing"] = pd.to_datetime(df["elect_first"]) <= df["listing_date"]
    df["candidate"] = (df["in_window"] & df["has_prior_history"] & ~df["withdrew_before_listing"]
                       & df["elected_before_listing"])
    # Labelled sensitivity rows, NOT in the strict count (each reason measured above):
    #  * withdrew-then-listed: a non-traded BDC that withdrew its election weeks before listing
    #    as a registered CEF through a successor CIK (FS Energy & Power -> FSSL, 2025);
    #  * converted from a registered CEF: prior N-CSR history instead of 10-K/10-Q (TCPC, 2012).
    ncsr = idx[idx["cik"].isin(bdc.index) & (idx["form"] == "N-CSR")].groupby("cik")["date_filed"].min()
    df["first_ncsr"] = df["cik"].map(ncsr)
    df["sensitivity"] = ""
    df.loc[df["in_window"] & df["has_prior_history"] & df["withdrew_before_listing"]
           & ((df["listing_date"] - df["n54c_first"]).dt.days <= 60), "sensitivity"] = "withdrew_election_<=60d_before_listing"
    df.loc[df["in_window"] & ~df["has_prior_history"] & df["first_ncsr"].notna()
           & ((df["listing_date"] - df["first_ncsr"]).dt.days >= PRIOR_DAYS), "sensitivity"] = "prior_NCSR_history"
    df = df.sort_values("listing_date")
    df.to_csv(CAND_OUT, index=False)
    df.drop(columns=["crsp_permnos"]).to_csv(CAND_PUBLIC, index=False)
    c = df[df["candidate"]]
    summ = {"built_utc": now_utc(), "bdc_ciks_2008_2025": int(len(df)),
            "bdc_ciks_matched_to_crsp_cef": int((df["crsp_permnos"] != "").sum()),
            "listed_in_window_any_history": int(df["in_window"].sum()),
            "candidates_prior_history": int(len(c)),
            "candidates_by_basis": c["listing_basis"].value_counts().to_dict(),
            "candidates_a8_within_30d_of_crsp": int(c["a8_within_30d_of_crsp"].sum()),
            "candidates_by_year": c["listing_date"].dt.year.value_counts().sort_index().to_dict(),
            "withdrew_before_listing_excluded": int((df["in_window"] & df["has_prior_history"]
                                                     & df["withdrew_before_listing"]).sum()),
            "elected_after_listing_excluded": int((df["in_window"] & df["has_prior_history"]
                                                   & ~df["elected_before_listing"]).sum()),
            "sensitivity_rows": df.loc[df["sensitivity"] != "", ["cik", "crsp_tickers", "sensitivity"]]
                                  .astype(str).to_dict("records")}
    prev = json.loads(SUMMARY_OUT.read_text()) if SUMMARY_OUT.exists() else {}
    prev["candidates"] = summ
    SUMMARY_OUT.write_text(json.dumps(prev, indent=1, default=str) + "\n")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    print(c[["cik", "edgar_names", "listing_date", "listing_basis", "first_periodic", "prior_history_days",
             "crsp_tickers", "a8_dates", "a8_within_30d_of_crsp"]].to_string(index=False))
    print(json.dumps(summ, indent=1, default=str))
    return summ


SNIPPETS = CACHE / "a4_listing_snippets.json"
LOCK_RE = re.compile(r"lock[- ]?up|locked[- ]up|staggered|one[- ]third|1/3|tranche|convert(?:ed|s)? (?:automatically )?into"
                     r"|eligible (?:for|to be) (?:sale|sold|transfer)|transfer restrictions?|may not (?:sell|transfer)"
                     r"|days (?:after|following) (?:the )?(?:listing|completion of (?:this|the) offering|the date of this prospectus)",
                     re.I)


def _strip_html(t: str) -> str:
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;|&#160;|&#xa0;", " ", t)
    t = re.sub(r"&#8217;|&#x2019;|&rsquo;", "'", t)
    t = re.sub(r"&#8220;|&#8221;|&ldquo;|&rdquo;", '"', t)
    t = re.sub(r"&amp;", "&", t)
    t = re.sub(r"&#8212;|&#8211;|&mdash;|&ndash;", "-", t)
    return re.sub(r"\s+", " ", t)


def pick_filings(idx: pd.DataFrame, cik: int, listing: pd.Timestamp) -> pd.DataFrame:
    """The listing's own documents, chosen from the index (no submissions API needed).

    An IPO-listing's prospectus (424B4/424B1/424B3, or 497 for BDCs before about 2020, within 30 days before to 5 after) carries the
    lock-up of pre-IPO holders. A direct listing's terms sit in the listing 8-K (10 days before to
    3 after) and in the proxy that approved the charter change (DEF 14A/DEFA14A within 240 days
    before). Windows are chosen from how listings are run, not fitted.
    """
    f = idx[idx["cik"] == cik].copy()
    f["d"] = (f["date_filed"] - listing).dt.days
    pro = f[f["form"].isin(["424B4", "424B1", "424B3", "497"]) & f["d"].between(-30, 5)].sort_values("d")
    k8 = f[(f["form"] == "8-K") & f["d"].between(-10, 3)].sort_values("d")
    px = f[f["form"].isin(["DEF 14A", "DEFA14A"]) & f["d"].between(-240, 0)].sort_values("d")
    a8 = f[f["form"].isin(["8-A12B", "8-A12B/A"]) & f["d"].between(-5, 5)].sort_values("d")
    if len(pro):
        return pd.concat([pro.tail(1), k8.head(1)])
    return pd.concat([k8.head(2), px.tail(1), a8.head(1) if not len(k8) else a8.iloc[0:0]])


def docs(max_new: int) -> None:
    from scripts.data.edgar_client import filing_txt_url
    idx = load_index()
    idx["date_filed"] = pd.to_datetime(idx["date_filed"])
    cand = pd.read_csv(CAND_OUT, parse_dates=["listing_date"])
    use = cand[cand["candidate"] | (cand["sensitivity"].fillna("") != "")]
    # FSSL listed through a successor CIK (2065812, "New FS Specialty Lending Fund"): its listing
    # documents are filed there, so both CIKs are searched for that row.
    extra = {1501729: [2065812]}
    client = BudgetedClient("a4_docs", max_new)
    out = json.loads(SNIPPETS.read_text()) if SNIPPETS.exists() else {}
    for r in use.itertuples(index=False):
        picks = pd.concat([pick_filings(idx, c, r.listing_date) for c in [int(r.cik)] + extra.get(int(r.cik), [])])
        for p in picks.itertuples(index=False):
            key = f"{r.cik}|{p.accession}"
            if key in out:
                continue
            txt = _strip_html(client.get_text(filing_txt_url(int(p.cik), p.accession)))
            spans = []
            for m in LOCK_RE.finditer(txt):
                spans.append(txt[max(0, m.start() - 350): m.end() + 450])
            out[key] = {"cik": int(r.cik), "tickers": r.crsp_tickers, "listing_date": str(r.listing_date.date()),
                        "form": p.form, "date_filed": str(p.date_filed.date()), "accession": p.accession,
                        "filer_cik": int(p.cik), "n_chars": len(txt), "n_hits": len(spans), "spans": spans[:60]}
            SNIPPETS.write_text(json.dumps(out, indent=1))
            print(r.crsp_tickers, p.form, p.date_filed.date(), p.accession, "hits", len(spans), flush=True)
    print("live requests this run:", client.n_requests, "seat total:", budget_used())

# ---------------------------------------------------------------- coded terms (read by hand, 2026-10-19)
# One row per listing: the document read, a VERBATIM quote (checked against the cached filing on
# every run by `terms`), and the release offsets in days from the listing/prospectus date that the
# quote states for NON-AFFILIATED pre-listing holders. Affiliate-only releases (adviser, directors)
# are listed separately and NOT counted as events: an adviser rarely sells its seed stake.
# offsets = [] with status "none_found" means the documents read carry no holder lock-up; it is a
# statement about those documents, never "no lock-up existed".
TERMS = [
    dict(t="KIPO", cik=1444706, acc="0001157523-11-006852", offsets=[], status="none_found",
         quote="Our planned December 12 th listing date allows us to fulfill our commitment to investors"),
    dict(t="TSLX", cik=1508655, acc="0001193125-14-110468", offsets=[180, 270], affiliate=[365], status="coded",
         quote="180 days after the date of this prospectus for all shares of common stock held by those stockholders and 270 days after the date of this prospectus for 50% of the shares"),
    dict(t="FSIC", cik=1422183, acc="0001193125-14-058066", offsets=[], status="none_found",
         quote="The Company expects that the Tender Offer will commence at the time of the Listing"),
    dict(t="CGBD", cik=1544206, acc="0001193125-17-203505", offsets=[180, 540, 720, 900], status="coded",
         quote="During the period beginning 720 days after the Release Date and thereafter: any remaining Pre-IPO Shares"),
    dict(t="CCT", cik=1494538, acc="0001387131-17-005250", offsets=[], status="none_found",
         quote="The Company currently expects that the Listing-Related Tender Offer will commence at the time of the Listing"),
    dict(t="BCSF", cik=1655050, acc="0001047469-18-007272", offsets=[180], status="coded",
         quote="Stockholders that purchased our shares of common stock prior to this offering are not permitted to transfer their shares without our and our Advisor's prior written consent until such date that is 180 days after the completion of this offering"),
    dict(t="ORCC", cik=1655888, acc="0001193125-19-196326", offsets=[180, 270, 365], affiliate=[540], status="coded",
         quote="(iii) one-third of the shares of our common stock held by such shareholder prior to the date of an Exchange Listing for 365 days following the Exchange Listing"),
    dict(t="CCAP", cik=1633336, acc="0001193125-20-022152", offsets=[], status="none_found",
         quote="the Company has agreed to repurchase in open market transactions"),
    dict(t="FSKR", cik=1525759, acc="0001387131-20-005741", offsets=[], status="none_found", quote=""),
    dict(t="TRIN", cik=1786108, acc="0001104659-21-009495", offsets=[], status="not_established",
         quote="Transfer Restrictions/Lock-up Periods Under the Common Stock Registration Rights Agreement"),
    dict(t="CION", cik=1534254, acc="0001140361-21-032445", offsets=[], status="none_found", quote=""),
    dict(t="RWAY", cik=1653384, acc="0001104659-21-128483", offsets=[180, 270, 360, 365, 450], status="coded",
         quote="will not be subject to any transfer restrictions on the 270th day following the expiration of the initial 180 day lock-up period"),
    dict(t="BXSL", cik=1736035, acc="0001193125-21-313514", offsets=None,
         dates=["2022-01-03", "2022-03-01", "2022-05-01", "2022-07-01"], status="coded",
         quote="(iv) 50% of the common shares held by such shareholder prior to the later of 240 days following an Exchange Listing and July 1, 2022"),
    dict(t="PSBD", cik=1794776, acc="0001213900-24-004584", offsets=[180, 270, 360], status="coded",
         quote="for 360 days following this offering, a shareholder is not permitted"),
    dict(t="MSDL", cik=1782524, acc="0001104659-24-006251", offsets=[180, 270, 365], affiliate=[365], status="coded",
         quote="the remaining 33% of the shares of the Company's Common Stock held by such stockholder prior to this offering will be released from such transfer restrictions 365 days after the date of the prospectus"),
    dict(t="NCDL", cik=1737924, acc="0001628280-24-002305", offsets=[91, 181, 271], affiliate=[365], status="coded",
         quote="beginning with the 181st day following the date of this prospectus through the 270th day following the date of this prospectus"),
    dict(t="OBDE", cik=1807427, acc="0001193125-24-008555", offsets=[180, 270, 365], status="coded",
         quote="Lock-ups expire on one third of remaining position at each of 180 days, 270 days, and 365 days post-listing"),
    dict(t="KBDC", cik=1747172, acc="0001213900-24-046057", offsets=[180, 270, 365], status="coded",
         quote="the remaining 33.3% of the shares of the Company's Common Stock held by such stockholder prior to this offering will be released from such transfer restrictions 365 days after the date of the prospectus"),
    dict(t="MSIF", cik=1535778, acc="0001535778-25-000050", offsets=[180, 270, 365], status="coded",
         quote="180 days after the Trading Date for one-third of the Restricted Shares held by such stockholder"),
    dict(t="OTF", cik=1747777, acc="0001193125-25-134115", offsets=[180, 270, 365], status="coded",
         quote="Lock-ups expire on one third of remaining position at each of 180 days, 270 days, and 365 days post-listing"),
    # labelled sensitivity rows (not in the strict count)
    dict(t="TCPC", cik=1370755, acc="0001047469-12-003911", offsets=[180], affiliate=[1095], status="sensitivity",
         quote="The term of the lock-up agreements entered into by non-affiliates is for a period of 180 days after the date of the underwriting agreement"),
    dict(t="FSSL", cik=2065812, acc="0001104659-25-103244", offsets=[], status="sensitivity_none_found", quote=""),
]
# Terra Income Fund 6 (CIK 1577134): its 2021-02-10 8-A12B registered NOTES ("$34,750,000 7.00% Notes
# due 2026", 424B1 0001104659-21-012259), not common stock; CRSP has no common listing. Excluded.
EXCLUDED_BY_READING = {1577134: "8-A12B of 2021-02-10 registered 7.00% Notes due 2026 (424B1 0001104659-21-012259); no common listing"}


def _norm_text(t: str) -> str:
    import html
    t = html.unescape(t)
    t = t.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    t = re.sub(r"\s*-\s*", "-", t)
    return re.sub(r"\s+", " ", t)


def terms() -> dict:
    """Verify every coded quote against the cached filing, then date the release events (offline)."""
    from scripts.data.edgar_client import filing_txt_url
    from scripts.events.ssx.ssx_fund2_common import offline_client
    c = offline_client()
    cand = pd.read_csv(CAND_OUT, parse_dates=["listing_date"])
    lst = dict(zip(cand["cik"], cand["listing_date"]))
    lst[2065812] = lst[1501729]                                    # FSSL: successor CIK, same listing
    rows, ev = [], []
    for r in TERMS:
        txt = _norm_text(_strip_html(c.get_text(filing_txt_url(r["cik"], r["acc"]))))
        q = _norm_text(r["quote"])
        if q and q not in txt:
            raise ValueError(f"{r['t']}: quote not found in {r['acc']}: {r['quote'][:80]!r}")
        L = lst[r["cik"]]
        dates = ([pd.Timestamp(d) for d in r["dates"]] if r.get("dates")
                 else [L + pd.Timedelta(days=int(o)) for o in (r["offsets"] or [])])
        rows.append({"ticker": r["t"], "cik": r["cik"], "accession": r["acc"], "listing_date": L.date(),
                     "status": r["status"], "n_release_events": len(dates),
                     "release_dates": ";".join(d.date().isoformat() for d in dates),
                     "affiliate_only_offsets": ";".join(map(str, r.get("affiliate", []))),
                     "quote_verified": bool(q), "quote": r["quote"]})
        for d in dates:
            ev.append({"ticker": r["t"], "status": r["status"], "release_date": d})
    T = pd.DataFrame(rows)
    T.to_csv(TERMS_OUT, index=False)
    E = pd.DataFrame(ev)
    strict = E[E["status"] == "coded"]
    summ = {"built_utc": now_utc(), "listings_read": int((~T["status"].str.startswith("sensitivity")).sum()),
            "listings_with_coded_releases": int((T["status"] == "coded").sum()),
            "listings_none_found": int((T["status"] == "none_found").sum()),
            "listings_not_established": int((T["status"] == "not_established").sum()),
            "release_events_strict_total": int(len(strict)),
            "release_events_strict_le_2025_12_31": int((strict["release_date"] <= "2025-12-31").sum()),
            "release_events_strict_le_2022_12_31": int((strict["release_date"] <= "2022-12-31").sum()),
            "listings_with_release_le_2022_12_31": int(strict.loc[strict["release_date"] <= "2022-12-31", "ticker"].nunique()),
            "release_events_by_year": strict["release_date"].dt.year.value_counts().sort_index().to_dict(),
            "distinct_release_months": int(strict["release_date"].dt.to_period("M").nunique()),
            "excluded_by_reading": EXCLUDED_BY_READING}
    prev = json.loads(SUMMARY_OUT.read_text()) if SUMMARY_OUT.exists() else {}
    prev["terms"] = summ
    SUMMARY_OUT.write_text(json.dumps(prev, indent=1, default=str) + "\n")
    print(T[["ticker", "listing_date", "status", "n_release_events", "release_dates"]].to_string(index=False))
    print(json.dumps(summ, indent=1, default=str))
    return summ


def adv() -> dict:
    """Pre-release ADV for coded release events dated <= 2022-12-31 (dsf rows < 2023 only; holdout sealed).

    Mean CRSP dollar volume over the 20 sessions ending two sessions before each
    release date. A level, not a return. Permno from the candidate table.
    """
    from src.data.r2 import connect, r2_path, q
    T = pd.read_csv(TERMS_OUT)
    cand = pd.read_csv(CAND_OUT)
    perm = {int(r.cik): int(str(r.crsp_permnos).split(";")[0]) for r in cand.itertuples(index=False)
            if isinstance(r.crsp_permnos, str) and r.crsp_permnos}
    ev = []
    for r in T[T["status"] == "coded"].itertuples(index=False):
        for d in str(r.release_dates).split(";"):
            if d and pd.Timestamp(d) < pd.Timestamp("2023-01-01"):
                ev.append({"ticker": r.ticker, "permno": perm[int(r.cik)], "release": pd.Timestamp(d)})
    E = pd.DataFrame(ev)
    con = connect()
    dsf = r2_path("crsp_a_stock", "dsf")
    px = q(con, f"""SELECT permno, date, abs(prc) * vol AS dv FROM read_parquet('{dsf}')
                    WHERE permno IN ({",".join(map(str, sorted(E["permno"].unique())))})
                      AND date < DATE '2023-01-01' AND prc IS NOT NULL AND vol IS NOT NULL""")
    px["date"] = pd.to_datetime(px["date"])
    if px["date"].max() >= pd.Timestamp("2023-01-01"):
        raise RuntimeError("a 2023+ dsf row was read")
    by = {p_: g.sort_values("date") for p_, g in px.groupby("permno")}
    E["adv_usd"] = [float(by[r.permno][by[r.permno]["date"] < r.release].tail(22).head(20)["dv"].mean())
                    for r in E.itertuples(index=False)]
    summ = {"built_utc": now_utc(), "events": int(len(E)), "median_adv_usd": float(E["adv_usd"].median()),
            "min_adv_usd": float(E["adv_usd"].min()), "share_ge_1m": float((E["adv_usd"] >= 1e6).mean()),
            "by_ticker_median_adv_usd": E.groupby("ticker")["adv_usd"].median().round(0).to_dict()}
    prev = json.loads(SUMMARY_OUT.read_text()) if SUMMARY_OUT.exists() else {}
    prev["adv_fit_releases"] = summ
    SUMMARY_OUT.write_text(json.dumps(prev, indent=1, default=str) + "\n")
    print(json.dumps(summ, indent=1, default=str))
    return summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("step", choices=("candidates", "docs", "terms", "adv"))
    ap.add_argument("--max-new", type=int, default=80, help="cap on live EDGAR requests in this run")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    if a.step == "candidates":
        candidates()
    elif a.step == "docs":
        docs(a.max_new)
    elif a.step == "terms":
        terms()
    elif a.step == "adv":
        adv()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
