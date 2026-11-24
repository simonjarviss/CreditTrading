"""Seeded document samples for seat `ssx_fund1` (A1, A3, A7): read filings, classify by text (ZERO TRIALS).

    export QUANTT_ENV_FILE=/abs/path/config/.env     # SEC_USER_AGENT; never printed
    python3 scripts/events/ssx/ssx_fund1_docs.py supplements [--max-live N]   # A1/A7 sample of listed supplements
    python3 scripts/events/ssx/ssx_fund1_docs.py proxies     [--max-live N]   # BDC DEF 14A: below-NAV issuance votes
    python3 scripts/events/ssx/ssx_fund1_docs.py tenq        [--max-live N]   # BDC 10-Q: below-NAV 10b5-1 buyback plans
    python3 scripts/events/ssx/ssx_fund1_docs.py ipos                         # BDC IPO prospectuses already cached (offline)
    add --offline to any part to read the cache only

WHY THIS EXISTS
---------------
The EDGAR index says THAT a fund filed a 497 or 424B, a DEF 14A or a 10-Q; it
cannot say WHAT the filing is. A1 needs the share of listed-fund supplements
that sell COMMON shares, and of those the share sold at the market (a
programme) rather than in one underwritten deal. A7 needs the share that sell
preferred shares or notes. A3 needs to know whether BDCs disclose buyback
plans that buy only below NAV, with what terms. Each answer is a share
measured on a SEEDED random sample, read by stated regular expressions whose
matched spans are kept so a reader can check them. No figure is a recollection.

WHAT IS READ, AND WHAT IS NOT
-----------------------------
Filing TEXT only. One level is read from text, the fund's own statement of
its last sale price and NAV per share in a supplement, and only for filings
dated before 2023-01-01 on funds outside `cef_universe.csv` (the brief allows a
state variable on an event date before 2023; the 44 are never priced). No
return of any kind is computed.

EDGAR ETIQUETTE (brief, 2026-10-19)
-----------------------------------
Nine other agents share the SEC's per-IP limit, and a lock-out stops the whole
desk. Every live request goes through `scripts/data/edgar_client.py` with
`RateLimiter(min_interval=1.5)` (0.67 req/s), and this seat may make at most
LIVE_BUDGET = 1,200 live requests in total. The running total is kept in
`results/events/ssx/ssx_fund1/run_meta.json`, and a part refuses to start a
request that would exceed the budget (it raises, naming the count). A cached
document costs nothing; the sample prefers no document over another, so cache
hits do not bias it.

CLASSIFIER RULES (on the main document's plain text; the cover = COVER_WIN characters from the
first "prospectus supplement" heading, see `cover_window`; hidden inline-XBRL headers removed)
-----------------------------------------------------------------------------------------
* rights:       THIS offering is a rights offering ("this/the rights offering", "is issuing
                (transferable) subscription rights", "upon exercise of ... rights", "rights to
                subscribe for").
* ipo:          "initial public offering" with "no (prior) public market"/"no history of public trading".
* atm:          an at-the-market phrase or a named sales/distribution agreement on the cover.
* underwritten: "underwrit" with "public offering price", an over-allotment option or an
                "underwriting discount/commission".
* drip, exchange (merger/reorganisation), base_shelf, offering_method_unread (an offering
  sentence with no method phrase), sticker (< 20,000 characters), other.
Security: whichever of preferred / notes / common the cover names first.
Precedence: rights > ipo > atm > underwritten > drip > exchange > base > offering_method_unread
> sticker > other. A1's event ("common issue") is common security AND atm, underwritten or
offering_method_unread.
HAND CHECK (2026-10-19): a seeded 20-document subset (random_state 20261019) was read by hand
against the labels: 19 of 20 right. The miss (TICC's 2017-11-20 base prospectus labelled a
rights offering) changed the rights rule; every remaining rights label (9) was then re-read and
is a rights offering. Two earlier rule versions were corrected before any count was used: the
12,000-character window (labelled notes takedowns as rights) and a missing ix:header strip.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("compute.use_numexpr", False)

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events" / "ssx" / "ssx_fund1"
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_fund1"
META = OUT / "run_meta.json"
LIVE_BUDGET = 1200
MIN_INTERVAL_S = 1.5
SEED = 20261019
TIME_HOLDOUT = pd.Timestamp("2023-01-01")
COVER = 12000
COVER_WIN = 6000
# A sale of new common shares for cash by the fund (A1's event). IPOs, rights, DRIP and mergers are not.
COMMON_ISSUE_KINDS = ("atm", "underwritten", "offering_method_unread")

# Strata for the supplement sample: (fund_type, era) -> fund-years drawn. 2024-25 is larger
# because it also feeds the Alpaca gate (today's flags on 2024-25 ATM filers).
ERAS = {"2010-15": (2010, 2015), "2016-19": (2016, 2019), "2020-22": (2020, 2022), "2024-25": (2024, 2025)}
FUND_YEARS_PER_STRATUM = {"2010-15": 15, "2016-19": 15, "2020-22": 15, "2024-25": 25}
DOCS_PER_FUND_YEAR = 4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _meta() -> dict:
    return json.loads(META.read_text()) if META.exists() else {}


def _meta_put(part: str, rec: dict) -> None:
    m = _meta()
    m[part] = rec
    META.write_text(json.dumps(m, indent=1, sort_keys=True, default=str) + "\n")


class BudgetedClient:
    """The shared EDGAR client at 1.5 s spacing, with this seat's cumulative live budget enforced."""

    def __init__(self, offline: bool, max_live: int):
        from scripts.data.edgar_client import EdgarClient, RateLimiter
        self.c = EdgarClient(offline=offline, limiter=RateLimiter(min_interval=MIN_INTERVAL_S))
        self.used_before = int(_meta().get("live_requests_total", 0))
        self.max_live = max_live

    def text(self, cik: int, accession: str) -> str:
        from scripts.data.edgar_client import cache_path, filing_txt_url
        url = filing_txt_url(int(cik), accession)
        if not cache_path(url).exists():
            if self.used_before + self.c.n_requests + 1 > LIVE_BUDGET:
                raise RuntimeError(f"live EDGAR budget: {self.used_before + self.c.n_requests} used of {LIVE_BUDGET}")
            if self.c.n_requests + 1 > self.max_live:
                raise RuntimeError(f"this run's --max-live {self.max_live} reached")
        from scripts.events.cef_corp_action_census import fetch_raw, strip_binary
        return strip_binary(fetch_raw(self.c, int(cik), accession))

    def close(self, part: str) -> dict:
        m = _meta()
        m["live_requests_total"] = self.used_before + self.c.n_requests
        m.setdefault("live_requests_log", []).append({"part": part, "utc": _now(), "live": self.c.n_requests,
                                                       "cache_hits": self.c.n_cache_hits})
        META.write_text(json.dumps(m, indent=1, sort_keys=True, default=str) + "\n")
        print(f"EDGAR live requests this run: {self.c.n_requests}; cache hits {self.c.n_cache_hits}; "
              f"seat total {m['live_requests_total']} of {LIVE_BUDGET}")
        return {"live": self.c.n_requests, "cache_hits": self.c.n_cache_hits, "seat_total": m["live_requests_total"]}


def main_text(raw: str, form: str) -> str:
    """Plain text of the filing's own document (not its exhibits); the first document if the type differs."""
    from scripts.events.conditional_tender_census import plain
    blocks = raw.split("<DOCUMENT>")[1:]
    if not blocks:
        raise ValueError("no <DOCUMENT> block in the submission")
    pick = blocks[0]
    for b in blocks:
        m = re.search(r"<TYPE>([^\n<]+)", b)
        if m and m.group(1).strip().upper() == form.upper():
            pick = b
            break
    # Inline-XBRL filings (2022 on) open with a hidden <ix:header> of facts and contexts;
    # left in, its tokens fill the "cover" (measured 2026-10-19 on MSDL's 424B1 and OBDC's 424B2).
    pick = re.sub(r"(?is)<ix:header>.*?</ix:header>", " ", pick)
    return plain(pick)


def _span(t: str, m: re.Match, pad: int = 120) -> str:
    return t[max(0, m.start() - pad): m.end() + pad]


R = {
    # A shelf's list of what it MAY offer reads "subscription rights to purchase shares"; a
    # rights offering's cover says the fund IS issuing rights. Hand check 2026-10-19: TICC's
    # 2017-11-20 base prospectus was labelled a rights offering by the looser rule.
    # Second pass, same day: a bare "rights offering" also matched a shelf's plan of
    # distribution ("existing stockholders in a rights offering", Gladstone 2018-07-13) and a
    # table of contents ("Rights Offerings", Nuveen 2024-06-04). Only THIS offering counts.
    "rights": re.compile(r"(?:this|the) rights offering|(?:is|are) (?:issuing|distributing) (?:non-?)?(?:transfer+able )?"
                         r"(?:subscription )?rights|upon exercise of (?:non-?)?(?:transfer+able )?(?:subscription )?rights|"
                         r"rights to (?:subscribe|purchase) for", re.I),
    "ipo": re.compile(r"initial public offering", re.I),
    "ipo2": re.compile(r"no (?:prior |previous )?public market|no history of public trading|not previously been publicly traded", re.I),
    "atm": re.compile(r"at[- ]the[- ]market|at the market offering|deemed to be (?:an )?[\"“']?at the market|"
                      r"equity distribution agreement|(?:at market issuance |atm |common stock |controlled equity offering )?sales agreement|"
                      r"sales agency agreement|(?<!underwriting )distribution agreement|dealer manager agreement", re.I),
    "uw": re.compile(r"underwrit", re.I),
    "uw2": re.compile(r"over-?allotment|option to purchase (?:up to )?(?:an additional|[0-9,]+ additional)|"
                      r"option (?:within|for) [0-9]+ days", re.I),
    "pop": re.compile(r"public offering price", re.I),
    "offer": re.compile(r"(?:we are|is|are) (?:offering|selling)(?: for sale)?(?: up to)? (?:\$?[0-9][0-9,.]* (?:million )?)?"
                        r"(?:of )?(?:our )?(?:shares|common|notes|preferred|\$|[0-9])", re.I),
    "drip": re.compile(r"dividend reinvestment|distribution reinvestment", re.I),
    "exchange": re.compile(r"reorganization|merger|exchange offer", re.I),
    "base": re.compile(r"may offer,? from time to time|we may offer|the fund may offer", re.I),
    "pref": re.compile(r"preferred (?:shares|stock)|term preferred|VRDP|variable rate demand preferred|MuniFund Preferred|"
                       r"\bMFP\b|auction rate preferred|mandatory redeemable preferred", re.I),
    "notes": re.compile(r"notes due|% notes|senior notes|unsecured notes|baby bonds?|aggregate principal amount", re.I),
}


def cover_window(t: str) -> str:
    """The supplement's cover: COVER_WIN characters from its first "prospectus supplement" heading.

    CORRECTION 2026-10-19 (first version, measured before any count was used): the
    rules first ran on the first 12,000 characters of the document. That window
    reaches the base-prospectus summary, which lists every security the shelf MAY
    offer ("common stock, preferred stock, subscription rights, warrants, debt
    securities"), so notes takedowns by ARCC (2024-05-06) and FSK (2024-11-13) were
    labelled rights offerings. The cover of a supplement names the one security
    and the one method of THIS offering, so the window now starts at the heading.
    A document with no such heading (an IPO prospectus, a full 497 prospectus) is
    read from its first "prospectus" heading, then from its start.
    """
    for pat in (r"prospectus supplement", r"\bprospectus\b"):
        m = re.search(pat, t[:60000], re.I)
        if m:
            return t[m.start(): m.start() + COVER_WIN]
    return t[:COVER_WIN]


def classify(t: str) -> dict:
    """Offering method and security from the cover of a supplement (module docstring)."""
    cov = cover_window(t)
    out = {"n_chars": len(t)}
    hits = {k: R[k].search(cov) for k in R}
    if hits["rights"]:
        kind = "rights"
    elif hits["ipo"] and hits["ipo2"]:
        kind = "ipo"
    elif hits["atm"]:
        kind = "atm"
    elif hits["uw"] and (hits["pop"] or hits["uw2"] or re.search(r"underwriting (?:discount|commission)", cov, re.I)):
        kind = "underwritten"
    elif hits["drip"]:
        kind = "drip"
    elif hits["exchange"] and not hits["pop"]:
        kind = "exchange"
    elif hits["base"]:
        kind = "base_shelf"
    elif hits["offer"]:
        kind = "offering_method_unread"     # an offering sentence, but no method phrase on the cover
    elif len(t) < 20000:
        kind = "sticker"
    else:
        kind = "other"
    # Security: whichever class the cover names first.
    pos = {}
    for k, pat in (("preferred", R["pref"]), ("notes", R["notes"]),
                   ("common", re.compile(r"common (?:shares|stock)|shares of (?:beneficial interest|common)", re.I))):
        m = pat.search(cov)
        if m:
            pos[k] = m.start()
    out["security"] = min(pos, key=pos.get) if pos else "unknown"
    out["kind"] = kind
    span_key = {"rights": "rights", "ipo": "ipo", "atm": "atm", "underwritten": "uw", "drip": "drip",
                "exchange": "exchange", "base_shelf": "base", "offering_method_unread": "offer"}.get(kind)
    out["span"] = _span(cov, hits[span_key]) if span_key and hits[span_key] else cov[:240]
    return out


_PRICE = re.compile(r"last (?:reported )?(?:sale|sales|closing) price[^.$]{0,200}?\$\s?([0-9]{1,3}\.[0-9]{2,4})", re.I)
_NAV = re.compile(r"net asset value (?:\(\"?NAV\"?\) )?per (?:common )?share[^.$]{0,200}?\$\s?([0-9]{1,3}\.[0-9]{2,4})", re.I)


def price_nav(t: str) -> dict:
    """The fund's own 'last reported sale price ... $X' and 'net asset value per share ... $Y' statements.

    The first match of each in the document. The NAV a BDC quotes is usually its
    last quarter-end NAV, so the premium read here is the market's price against
    a NAV that can be weeks old: a STATE label (premium or discount), not a
    precise level. Both spans are kept.
    """
    p, n = _PRICE.search(t), _NAV.search(t)
    if not (p and n):
        return {"px": None, "nav": None}
    px, nav = float(p.group(1)), float(n.group(1))
    return {"px": px, "nav": nav, "prem": px / nav - 1.0, "px_span": _span(t, p, 60), "nav_span": _span(t, n, 60)}


# ------------------------------------------------------------------ supplements (A1/A7)

def supplements(offline: bool, max_live: int) -> dict:
    from scripts.events.ssx.ssx_fund1_census import universe_ciks
    f = pd.read_csv(CACHE / "a1_listed_supplement_frame.csv", parse_dates=["date_filed"])
    f["year"] = f["date_filed"].dt.year
    rng = np.random.default_rng(SEED)
    picks = []
    for ft in ("bdc", "rcef"):
        for era, (lo, hi) in ERAS.items():
            fy = (f[(f["fund_type"] == ft) & f["year"].between(lo, hi)][["cik", "year"]]
                  .drop_duplicates().sort_values(["cik", "year"]).reset_index(drop=True))
            k = min(FUND_YEARS_PER_STRATUM[era], len(fy))
            idx = rng.choice(len(fy), size=k, replace=False)
            for i in sorted(idx):
                picks.append((ft, era, int(fy.loc[i, "cik"]), int(fy.loc[i, "year"]), len(fy)))
    client = BudgetedClient(offline, max_live)
    uni = universe_ciks()
    rows = []
    try:
        for ft, era, cik, year, n_fy in picks:
            docs = f[(f["cik"] == cik) & (f["year"] == year)].sort_values("accession")
            order = rng.permutation(len(docs))[:DOCS_PER_FUND_YEAR]
            for j in order:
                d = docs.iloc[int(j)]
                raw = client.text(cik, d["accession"])
                t = main_text(raw, d["form"])
                c = classify(t)
                rec = {"fund_type": ft, "era": era, "stratum_fund_years": n_fy, "cik": cik, "year": year,
                       "company": d["company"], "form": d["form"], "date_filed": d["date_filed"].date(),
                       "accession": d["accession"], "docs_in_fund_year": len(docs),
                       "universe44": cik in uni, **c}
                if d["date_filed"] < TIME_HOLDOUT and cik not in uni and c["security"] == "common" \
                        and c["kind"] in COMMON_ISSUE_KINDS:
                    rec.update(price_nav(t))
                rows.append(rec)
    finally:
        fetch = client.close("supplements")
        if rows:
            pd.DataFrame(rows).to_csv(CACHE / "supp_sample_classified.csv", index=False)
    s = pd.DataFrame(rows)
    return summarise_supplements(s, fetch)


def summarise_supplements(s: pd.DataFrame, fetch: dict) -> dict:
    s["common_issue"] = (s["security"] == "common") & s["kind"].isin(list(COMMON_ISSUE_KINDS))
    s["atm_common"] = (s["security"] == "common") & (s["kind"] == "atm")
    s["senior"] = s["security"].isin(["preferred", "notes"]) & ~s["kind"].isin(["sticker", "exchange", "rights", "drip"])
    fy = s.groupby(["fund_type", "era", "cik", "year"]).agg(
        common_issue=("common_issue", "any"), atm_common=("atm_common", "any"), senior=("senior", "any"),
        capped=("docs_in_fund_year", lambda v: int(v.iloc[0] > DOCS_PER_FUND_YEAR)),
        stratum_fund_years=("stratum_fund_years", "first")).reset_index()
    def share(g, col):
        n, k = len(g), int(g[col].sum())
        lo, hi = wilson(k, n)
        return {"k": k, "n": n, "share": k / n if n else None, "wilson95": [lo, hi]}
    by = {}
    for (ft, era), g in fy.groupby(["fund_type", "era"]):
        by[f"{ft}|{era}"] = {"fund_years_in_stratum": int(g["stratum_fund_years"].iloc[0]),
                             "common_issue": share(g, "common_issue"), "atm_common": share(g, "atm_common"),
                             "senior_securities": share(g, "senior"), "fund_years_capped_at_4_docs": int(g["capped"].sum())}
    # Per-year estimates: stratum share x fund-years in the stratum / calendar years in the era,
    # summed over BDC and registered CEF; the Wilson interval is carried through the same way.
    # A fund-year with more than DOCS_PER_FUND_YEAR supplements is read on 4, so these are
    # LOWER bounds for fund-years that issue often.
    est = {}
    for era, (lo, hi) in ERAS.items():
        ny = hi - lo + 1
        for col in ("common_issue", "atm_common", "senior_securities"):
            e = [0.0, 0.0, 0.0]
            for ft in ("bdc", "rcef"):
                b = by.get(f"{ft}|{era}")
                if b is None:
                    continue
                pop = b["fund_years_in_stratum"]
                c = b[col]
                e[0] += c["share"] * pop / ny
                e[1] += c["wilson95"][0] * pop / ny
                e[2] += c["wilson95"][1] * pop / ny
            est[f"{era}|{col}"] = {"per_year": round(e[0], 1), "wilson_lo": round(e[1], 1), "wilson_hi": round(e[2], 1)}
    kinds = s.groupby(["fund_type", "kind", "security"]).size().rename("docs").reset_index()
    kinds.to_csv(OUT / "a1_sample_doc_kinds.csv", index=False)
    pn = s.dropna(subset=["prem"]) if "prem" in s else s.iloc[0:0]
    prem = {"n": int(len(pn)), "share_at_premium": float((pn["prem"] > 0).mean()) if len(pn) else None,
            "median_prem": float(pn["prem"].median()) if len(pn) else None,
            "by_kind": {k: {"n": int(len(g)), "share_at_premium": float((g["prem"] > 0).mean())}
                        for k, g in pn.groupby("kind")} if len(pn) else {}}
    out = {"ran_utc": _now(), "seed": SEED, "docs_read": int(len(s)), "fund_years": int(len(fy)),
           "by_stratum": by, "estimated_fund_years_per_year": est,
           "premium_at_filing_pre2023_ex44": {**prem, "funds": int(pn["cik"].nunique()) if len(pn) else 0},
           "fetch": fetch}
    (OUT / "a1_sample_summary.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str)[:6000])
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return float(c - h), float(c + h)


# ------------------------------------------------------------------ BDC proxies and 10-Qs (A1 authorisations, A3)

_BELOW_NAV_ISSUE = re.compile(r"(?:sell|issue)[^.]{0,250}?(?:below|less than)[^.]{0,80}?net asset value", re.I)
_PLAN = re.compile(r"10b5-1", re.I)
_BELOW = re.compile(r"below (?:(?:our|the|its) )?(?:most recently (?:reported|announced|disclosed) |then[- ]current )?"
                    r"(?:net asset value|NAV)|less than (?:(?:our|the) )?(?:net asset value|NAV)", re.I)
_REPO = re.compile(r"repurchase|buyback|buy back|purchase (?:up to|of) ", re.I)
_SIZE = re.compile(r"up to \$\s?[0-9.,]+ (?:million|billion)|\$\s?[0-9.,]+ (?:million|billion)", re.I)
_EXPIRY = re.compile(r"(?:terminat|expir)[a-z]*[^.]{0,200}?(?:[0-9]{1,2}[- ]months|20[0-9]{2}|earliest)", re.I)


def listed_rows(form: str) -> pd.DataFrame:
    r = pd.read_parquet(CACHE / "fund_rows_listed.parquet")
    r = r[(r["form"] == form) & (r["fund_type"] == "bdc") & r["listed"].str.startswith("listed")].copy()
    r["year"] = r["date_filed"].dt.year
    return r


def sample_rows(r: pd.DataFrame, per_era: int, rng) -> pd.DataFrame:
    out = []
    for era, (lo, hi) in {"2010-15": (2010, 2015), "2016-19": (2016, 2019), "2020-22": (2020, 2022),
                          "2023-25": (2023, 2025)}.items():
        g = r[r["year"].between(lo, hi)].sort_values("accession").reset_index(drop=True)
        k = min(per_era, len(g))
        out.append(g.iloc[sorted(rng.choice(len(g), size=k, replace=False))].assign(era=era, era_pop=len(g)))
    return pd.concat(out, ignore_index=True)


def proxies(offline: bool, max_live: int, per_era: int = 15) -> dict:
    r = listed_rows("DEF 14A")
    pop = r.groupby("year").agg(filings=("accession", "nunique"), bdcs=("cik", "nunique")).reset_index()
    pop.to_csv(OUT / "a1_bdc_def14a_population_by_year.csv", index=False)
    smp = sample_rows(r, per_era, np.random.default_rng(SEED + 1))
    client = BudgetedClient(offline, max_live)
    rows = []
    try:
        for d in smp.itertuples(index=False):
            t = main_text(client.text(d.cik, d.accession), "DEF 14A")
            m = _BELOW_NAV_ISSUE.search(t)
            rows.append({"cik": d.cik, "company": d.company, "date_filed": d.date_filed.date(), "era": d.era,
                         "era_pop": d.era_pop, "accession": d.accession, "below_nav_issue_vote": bool(m),
                         "span": _span(t, m) if m else None})
    finally:
        fetch = client.close("proxies")
        if rows:
            pd.DataFrame(rows).to_csv(CACHE / "bdc_def14a_sample.csv", index=False)
    s = pd.DataFrame(rows)
    by = {}
    for era, g in s.groupby("era"):
        k, n = int(g["below_nav_issue_vote"].sum()), len(g)
        by[era] = {"k": k, "n": n, "share": k / n, "wilson95": wilson(k, n), "era_population": int(g["era_pop"].iloc[0])}
    out = {"ran_utc": _now(), "population": pop.set_index("year").to_dict("index"), "sample_by_era": by, "fetch": fetch}
    (OUT / "a1_bdc_def14a_summary.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))
    return out


def tenq(offline: bool, max_live: int, per_era: int = 12) -> dict:
    r = listed_rows("10-Q")
    pop = r.groupby("year").agg(filings=("accession", "nunique"), bdcs=("cik", "nunique")).reset_index()
    pop.to_csv(OUT / "a3_bdc_10q_population_by_year.csv", index=False)
    smp = sample_rows(r, per_era, np.random.default_rng(SEED + 2))
    client = BudgetedClient(offline, max_live)
    rows = []
    try:
        for d in smp.itertuples(index=False):
            t = main_text(client.text(d.cik, d.accession), "10-Q")
            plan_below, terms = False, {}
            for m in _PLAN.finditer(t):
                w = t[max(0, m.start() - 1500): m.end() + 1500]
                if _REPO.search(w) and _BELOW.search(w):
                    plan_below = True
                    terms = {"size": bool(_SIZE.search(w)), "expiry": bool(_EXPIRY.search(w)),
                             "span": t[max(0, m.start() - 300): m.end() + 500]}
                    break
            any_repo_below = bool(re.search(r"repurchase[^.]{0,300}below[^.]{0,60}(?:net asset value|NAV)", t, re.I))
            rows.append({"cik": d.cik, "company": d.company, "date_filed": d.date_filed.date(), "era": d.era,
                         "era_pop": d.era_pop, "accession": d.accession, "plan_10b5_1_below_nav": plan_below,
                         "any_repurchase_below_nav_text": any_repo_below, "terms_size": terms.get("size"),
                         "terms_expiry": terms.get("expiry"), "span": terms.get("span")})
    finally:
        fetch = client.close("tenq")
        if rows:
            pd.DataFrame(rows).to_csv(CACHE / "bdc_10q_sample.csv", index=False)
    s = pd.DataFrame(rows)
    by = {}
    for era, g in s.groupby("era"):
        k, n = int(g["plan_10b5_1_below_nav"].sum()), len(g)
        by[era] = {"k": k, "n": n, "share": k / n, "wilson95": wilson(k, n),
                   "any_repurchase_below_nav_text": int(g["any_repurchase_below_nav_text"].sum()),
                   "with_size": int(g["terms_size"].fillna(False).sum()),
                   "with_expiry": int(g["terms_expiry"].fillna(False).sum()),
                   "era_population_10q": int(g["era_pop"].iloc[0]), "distinct_bdcs_in_sample": int(g["cik"].nunique())}
    out = {"ran_utc": _now(), "population": pop.set_index("year").to_dict("index"), "sample_by_era": by, "fetch": fetch}
    (OUT / "a3_bdc_10q_summary.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("supplements", "proxies", "tenq"))
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--max-live", type=int, default=450)
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    {"supplements": supplements, "proxies": proxies, "tenq": tenq}[a.part](a.offline, a.max_live)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
