"""Check C5's input: the real expiry date of each rights offering, read from the fund's own prospectus.

    QUANTT_ENV_FILE=<env> python3 results/ideas/cef_rights_offerings/edgar_expiry.py

WHY: CRSP dates the ex-rights day but not the day the subscription closes, and the
pre-specified rule had to assume ex-date + 25 sessions. EDGAR has the offering documents.
Everything goes through scripts/data/edgar_client.py (polite, cached, rate-limited).

HOW, AND WHAT IT CANNOT DO
  fund -> CIK   by the fund's ticker at the ex-date in the SEC's company_tickers.json. That
                file lists LIVE registrants only, and a ticker reused by another company would
                mismatch, so a match is kept only if the registrant later files a document that
                names an expiry inside the window. Dead funds are not matched: coverage is
                reported, and C5 is a check on a subset, not a replacement for the rule.
  documents     the registrant's 497, 424B1/2/3/5 and N-2/N-2A filings dated from 75 days
                before the ex-date to 10 days after, nearest the ex-date first, at most 6.
  expiry        every "expire ... on <Month d, yyyy>" and "Expiration Date ... <Month d, yyyy>"
                in the document; the most frequent date that falls 5 to 75 calendar days after
                the ex-date. An extension announced later is not seen [U].
Output (per fund, so outside the repository): ~/quantt_research/cef_rights_offerings/expiry.parquet
"""
from __future__ import annotations

import html
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
STAGE = Path.home() / "quantt_research" / "cef_rights_offerings"
FORMS = ("497", "424B1", "424B2", "424B3", "424B5", "N-2", "N-2/A", "N-2ASR", "POS EX", "497AD")
MON = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
EXP = [re.compile(r"expir\w*[^.]{0,160}?\bon\s+(?:\w+day,?\s+)?(" + MON + ")", re.I),
       re.compile(r"Expiration\s+Date[^.]{0,120}?(" + MON + ")", re.I)]
DAY30 = 30 * 86400.0


def filings(client, cik: int) -> pd.DataFrame:
    j = client.get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", max_age_s=DAY30)
    parts = [j["filings"]["recent"]]
    for f in j["filings"].get("files", []):
        parts.append(client.get_json(f"https://data.sec.gov/submissions/{f['name']}", max_age_s=DAY30))
    df = pd.concat([pd.DataFrame({k: p[k] for k in ("accessionNumber", "filingDate", "form", "primaryDocument")}) for p in parts])
    df["filingDate"] = pd.to_datetime(df["filingDate"])
    return df


def plain(raw: str) -> str:
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t)


def expiry_in(text: str, ex: pd.Timestamp):
    c = Counter()
    for rx in EXP:
        for m in rx.finditer(text):
            d = pd.to_datetime(m.group(1), errors="coerce")
            if pd.notna(d) and 5 <= (d - ex).days <= 75:
                c[d] += 1
    return c.most_common(1)[0][0] if c else None


def main() -> int:
    from scripts.data.edgar_client import EdgarClient, EdgarNotFound, filing_txt_url
    client = EdgarClient()
    ev = pd.read_parquet(STAGE / "events.parquet")
    ev["ex_date"] = pd.to_datetime(ev["ex_date"])
    tk = client.get_json("https://www.sec.gov/files/company_tickers.json", max_age_s=DAY30)
    cik_of = {v["ticker"].upper(): int(v["cik_str"]) for v in tk.values()}
    rows, cache = [], {}
    for r in ev.itertuples():
        rec = {"permno": int(r.permno), "ex_date": r.ex_date, "cik": None, "expiry": None, "form": None, "accession": None, "why": None}
        cik = cik_of.get(str(r.ticker).upper()) if r.ticker else None
        if cik is None:
            rec["why"] = "ticker not a live registrant"
            rows.append(rec); continue
        rec["cik"] = cik
        if cik not in cache:
            cache[cik] = filings(client, cik)
        f = cache[cik]
        g = f[f["form"].isin(FORMS) & (f["filingDate"] >= r.ex_date - pd.Timedelta(days=75)) & (f["filingDate"] <= r.ex_date + pd.Timedelta(days=10))
              & f["primaryDocument"].astype(str).str.len().gt(0)].copy()
        if g.empty:
            rec["why"] = "no offering document in the window"
            rows.append(rec); continue
        g["gap"] = (g["filingDate"] - r.ex_date).abs()
        for x in g.sort_values("gap").head(6).itertuples():
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{x.accessionNumber.replace('-', '')}/{x.primaryDocument}"
            try:
                raw = client.get_text(url)
            except EdgarNotFound:
                # Filings before about 2001 list a primary document that EDGAR no longer serves
                # by that name; the complete-submission text holds the same document.
                raw = client.get_text(filing_txt_url(cik, x.accessionNumber))
            d = expiry_in(plain(raw), r.ex_date)
            if d is not None:
                rec.update(expiry=d, form=x.form, accession=x.accessionNumber)
                break
        if rec["expiry"] is None:
            rec["why"] = "no expiry date parsed"
        rows.append(rec)
        print(r.ticker, r.ex_date.date(), rec["expiry"].date() if rec["expiry"] is not None else rec["why"], flush=True)
    out = pd.DataFrame(rows)
    out["expiry"] = pd.to_datetime(out["expiry"])
    out.to_parquet(STAGE / "expiry.parquet", index=False)
    print(len(out), "events |", int(out["expiry"].notna().sum()), "with an expiry |", out["why"].value_counts(dropna=True).to_dict())
    print("calendar days ex-date to expiry:", (out["expiry"] - out["ex_date"]).dt.days.describe().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
