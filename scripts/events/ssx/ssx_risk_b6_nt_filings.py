"""B6 census: late-filing notices (NT forms) and auditor changes at closed-end
funds and BDCs, per year. A hygiene flag, zero trials.

WHY
---
A fund that cannot file its shareholder report (NT N-CSR) or its N-CEN, or a
BDC that cannot file its 10-K/10-Q (NT 10-K / NT 10-Q), or that changes
auditor (8-K item 4.01), is telling the market its NAV process is under strain.
For the discount book that is a reason not to buy the "cheap" discount on that
name: a subtract-only hygiene flag. Before designing it, count how often it
happens in our universe and in the wider CEF/BDC set.

WHAT IS COUNTED
---------------
* From the EDGAR quarterly master indexes, OFFLINE (shared cache), 2010-2025:
  NT N-CSR (`NT-NCSR`, `NTFNCSR`), NT N-CEN (`NT N-CEN`, `NT-NCEN`, `NTFNCEN`),
  NT NPORT (`NT NPORT-P`, `NT NPORT-EX`), NT N-SAR, NT 10-K and NT 10-Q (with
  `NTN` variants and amendments), by filer group:
    - `bdc`: CIKs that ever filed N-54A (the BDC election) in 2008-2026;
    - `cef`: other CIKs in the closed-end marker-form set
      (scripts/data/fetch_edgar_events.py MARKER_FORMS);
    - `universe44`: the 44 names of data/cef/cef_universe.csv (CIKs from the
      SEC ticker file cached 2026-10-12).
* Auditor changes at LISTED BDCs: 8-K filings whose `items` field contains
  4.01, from each BDC's submissions JSON (data.sec.gov), live through
  scripts/data/edgar_client.py at min_interval 1.5s, cached. "Listed" = the
  BDC's CIK carries an exchange ticker in the SEC ticker file TODAY, so this is
  a survivor set (stated, not corrected).
* Registered CEFs report auditor changes in shareholder-report filings, not in
  an indexed form; they are NOT counted here (stated as a gap).

Reproduce:
    python3 scripts/events/ssx/ssx_risk_b6_nt_filings.py                       # NT counts, offline
    QUANTT_ENV_FILE=<abs path> python3 scripts/events/ssx/ssx_risk_b6_nt_filings.py --auditor --max-requests 120
Output: results/events/ssx/ssx_risk/b6_nt_per_year.csv, b6_auditor_401_per_year.csv, b6_summary.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.data.edgar_client import EdgarClient, RateLimiter  # noqa: E402
from scripts.data.fetch_edgar_events import parse_master_index, INDEX_URL, MARKER_FORMS, SUBMISSIONS_URL, SUBMISSIONS_PAGE_URL  # noqa: E402

OUT = REPO / "results" / "events" / "ssx" / "ssx_risk"
NT = {
    "NT N-CSR": ("NT-NCSR", "NT-NCSR/A", "NTFNCSR"),
    "NT N-CEN": ("NT N-CEN", "NT-NCEN", "NT-NCEN/A", "NTFNCEN"),
    "NT NPORT": ("NT NPORT-P", "NT NPORT-EX"),
    "NT N-SAR": ("NT-NSAR", "NT-NSAR/A", "NTFNSAR"),
    "NT 10-K": ("NT 10-K", "NT 10-K/A", "NTN 10K"),
    "NT 10-Q": ("NT 10-Q", "NT 10-Q/A", "NTN 10Q"),
}
FORM2KIND = {f: k for k, fs in NT.items() for f in fs}
Y0, Y1 = 2010, 2025


def index_rows() -> pd.DataFrame:
    c = EdgarClient(offline=True)
    keep = set(FORM2KIND) | MARKER_FORMS
    frames = []
    for y in range(2008, 2027):
        for q in range(1, 5):
            df = parse_master_index(c.get_text(INDEX_URL.format(y=y, q=q)), f"{y}Q{q}", keep_forms=keep)
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def universe_ciks() -> dict[int, str]:
    j = json.loads((REPO / "results/events/_cache_edgar/www.sec.gov/files/company_tickers_exchange.json").read_text())
    t = pd.DataFrame(j["data"], columns=j["fields"])
    u = set(pd.read_csv(REPO / "data/cef/cef_universe.csv").ticker)
    m = t[t.ticker.isin(u)]
    if len(set(m.ticker)) != len(u):
        raise KeyError(f"universe names with no CIK: {sorted(u - set(m.ticker))}")
    return dict(zip(m.cik.astype(int), m.ticker))


def listed_bdcs(bdc: set[int]) -> pd.DataFrame:
    j = json.loads((REPO / "results/events/_cache_edgar/www.sec.gov/files/company_tickers_exchange.json").read_text())
    t = pd.DataFrame(j["data"], columns=j["fields"])
    t = t[t.cik.astype(int).isin(bdc) & t.exchange.notna()]
    return t.drop_duplicates("cik")


def auditor_changes(ciks: list[int], max_requests: int) -> pd.DataFrame:
    live = EdgarClient(limiter=RateLimiter(min_interval=1.5))
    rows = []
    for cik in ciks:
        if live.n_requests >= max_requests:
            raise RuntimeError(f"request cap {max_requests} reached at CIK {cik}; raise --max-requests deliberately")
        j = live.get_json(SUBMISSIONS_URL.format(cik=cik), max_age_s=None)
        blocks = [j["filings"]["recent"]]
        for page in j["filings"].get("files", []):
            blocks.append(live.get_json(SUBMISSIONS_PAGE_URL.format(name=page["name"]), max_age_s=None))
        for b in blocks:
            for form, date, items in zip(b["form"], b["filingDate"], b.get("items", [""] * len(b["form"]))):
                if form in ("8-K", "8-K/A") and "4.01" in (items or ""):
                    rows.append({"cik": cik, "name": j.get("name"), "form": form, "filing_date": date, "items": items})
    out = pd.DataFrame(rows, columns=["cik", "name", "form", "filing_date", "items"])
    out.attrs["live_requests"] = live.n_requests
    out.attrs["cache_hits"] = live.n_cache_hits
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--auditor", action="store_true")
    ap.add_argument("--max-requests", type=int, default=120)
    a = ap.parse_args(argv)
    idx = index_rows()
    bdc = set(idx.loc[idx.form.isin(["N-54A", "N-54A/A"]), "cik"])
    cef = set(idx.loc[idx.form.isin(MARKER_FORMS), "cik"]) - bdc
    uni = universe_ciks()
    nt = idx[idx.form.isin(FORM2KIND)].copy()
    nt["kind"] = nt.form.map(FORM2KIND)
    nt["year"] = nt.date_filed.dt.year
    nt = nt[nt.year.between(Y0, Y1)]
    nt["group"] = nt.cik.map(lambda c: "universe44" if c in uni else ("bdc" if c in bdc else ("cef" if c in cef else None)))
    nt = nt.dropna(subset=["group"])
    # universe44 rows are also CEFs: report them separately and inside "cef_all"
    per = nt.groupby(["group", "kind", "year"]).size().unstack("year", fill_value=0)
    OUT.mkdir(parents=True, exist_ok=True)
    per.to_csv(OUT / "b6_nt_per_year.csv")
    filers = nt.groupby(["group", "year"]).cik.nunique().unstack("year", fill_value=0)
    filers.to_csv(OUT / "b6_nt_distinct_filers_per_year.csv")
    summ = {"years": [Y0, Y1], "n_bdc_ciks": len(bdc), "n_cef_ciks": len(cef), "n_universe44": len(uni),
            "nt_filings_total_by_group_kind": {f"{g}|{k}": int(v) for (g, k), v in per.sum(axis=1).items()},
            "distinct_nt_filers_per_year_median": filers.median(axis=1).to_dict(),
            "universe44_nt_rows": nt[nt.group == "universe44"].assign(ticker=lambda d: d.cik.map(uni))
                [["ticker", "form", "date_filed"]].astype(str).values.tolist()}
    if a.auditor:
        lb = listed_bdcs(bdc)
        ac = auditor_changes(sorted(lb.cik.astype(int)), a.max_requests)
        ac.to_csv(OUT / "b6_auditor_401_listed_bdcs.csv", index=False)
        ac["year"] = pd.to_datetime(ac.filing_date).dt.year
        ac = ac[ac.year.between(Y0, Y1)]
        summ["auditor_401"] = {"listed_bdcs": int(len(lb)), "live_requests": ac.attrs.get("live_requests"),
                               "filings_8k_401_2010_2025": int(len(ac)),
                               "distinct_bdcs_with_401": int(ac.cik.nunique()),
                               "per_year": ac.groupby("year").cik.nunique().to_dict()}
    (OUT / "b6_summary.json").write_text(json.dumps(summ, indent=1, default=str))
    print(per.to_string())
    print(json.dumps({k: v for k, v in summ.items() if k != "universe44_nt_rows"}, indent=1, default=str))
    print("universe44 NT rows:", summ["universe44_nt_rows"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
