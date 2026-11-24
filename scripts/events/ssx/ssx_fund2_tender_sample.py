"""A16: is "amount tendered against amount offered" machine-readable in final SC TO-I/A amendments of unlisted funds? (zero trials)

    export QUANTT_ENV_FILE=/abs/path/config/.env     # SEC_USER_AGENT; never printed
    python3 scripts/events/ssx/ssx_fund2_tender_sample.py [--n 15] [--seed 20261019]

WHY THIS EXISTS
---------------
Idea A16 frames the quarterly repurchase tenders of non-traded BDCs and
tender-offer funds as a private-credit STRESS STATE (tendered / offered), not a
trade. It is only usable if the ratio can be read from filings without a
human. The final amendment of each tender episode (the last SC TO-I/A, filed
after expiry under Rule 13e-4(c)(4)) is where the result is reported. This
samples final amendments of UNLISTED BDCs and CEFs (the
`ssx_fund2_offline_counts.classify` flag), 2016-2025, with a stated seed, and
tries two narrow regexes: shares (or dollars) tendered, and shares (or
dollars) offered / accepted. Each hit's span is saved for reading. An episode
is the fetcher's own rule (`fetch_edgar_events.episodes`: tender filings of a
fund within 120 days of each other).
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

from scripts.events.ssx.ssx_fund2_common import OUT, load_index, BudgetedClient, budget_used, now_utc  # noqa: E402
from scripts.events.ssx.ssx_fund2_bdc_listings import _strip_html  # noqa: E402

NUM = r"\$?\s?[\d,]{3,}(?:\.\d+)?"
TENDERED_RE = re.compile(rf"({NUM})\s+(?:shares|units|interests|Shares|Units|Interests)?[^.]{{0,80}}?(?:were|was)?\s*(?:validly|properly)?\s*tendered", re.I)
OFFER_RE = re.compile(rf"(?:offer(?:ed)? to (?:purchase|repurchase)|up to)\s+({NUM}|[\d.]+%)", re.I)
ACCEPT_RE = re.compile(rf"(?:accepted for (?:purchase|repurchase)|purchased|repurchased)\s+({NUM})", re.I)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--seed", type=int, default=20261019)
    a = ap.parse_args(argv)
    from scripts.data.edgar_client import filing_txt_url
    from scripts.data.fetch_edgar_events import episodes
    from scripts.events.ssx.ssx_fund2_offline_counts import classify
    idx = load_index()
    idx["date_filed"] = pd.to_datetime(idx["date_filed"])
    f = classify(idx).set_index("cik")
    un = set(f.index[~f["listed"] & f["ftype"].isin(["BDC", "CEF"])])
    t = idx[idx["cik"].isin(un) & idx["form"].isin(["SC TO-I", "SC TO-I/A", "SC TO-C"])].copy()
    t["kind"] = "tender"
    ep = episodes(t)
    ep = ep[(pd.to_datetime(ep["first_date"]) >= "2016-01-01") & (pd.to_datetime(ep["last_date"]) <= "2025-12-31")]
    ep = ep[ep["forms"].str.contains("SC TO-I/A")]
    last = (t[t["form"] == "SC TO-I/A"].sort_values("date_filed").groupby("cik"))
    rows = []
    ep["ftype"] = ep["cik"].map(f["ftype"])
    samp = pd.concat([ep[ep["ftype"] == "BDC"].sample(n=a.n // 2 + 1, random_state=a.seed),
                      ep[ep["ftype"] == "CEF"].sample(n=a.n - a.n // 2 - 1, random_state=a.seed)])
    cl = BudgetedClient("a16_tender_sample", a.n + 2)
    for e in samp.itertuples(index=False):
        g = t[(t["cik"] == e.cik) & (t["form"] == "SC TO-I/A") & t["date_filed"].between(
            pd.Timestamp(e.first_date), pd.Timestamp(e.last_date))].sort_values("date_filed")
        fin = g.iloc[-1]
        raw = cl.get_text(filing_txt_url(int(fin.cik), fin.accession))
        txt = _strip_html(raw)
        mt, mo, ma = TENDERED_RE.search(txt), OFFER_RE.search(txt), ACCEPT_RE.search(txt)
        rows.append({"cik": int(e.cik), "ftype": e.ftype, "company": fin.company, "final_accession": fin.accession,
                     "date_filed": fin.date_filed.date(), "has_filing_fee_exhibit": "EX-FILING FEES" in raw,
                     "tendered_found": bool(mt), "offered_found": bool(mo), "accepted_found": bool(ma),
                     "tendered_span": txt[max(0, mt.start() - 150): mt.end() + 100] if mt else "",
                     "offered_span": txt[max(0, mo.start() - 100): mo.end() + 100] if mo else ""})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "a16_tender_sample.csv", index=False)
    summ = {"built_utc": now_utc(), "episodes_frame": int(len(ep)), "n": int(len(df)), "seed": a.seed,
            "tendered_found": int(df["tendered_found"].sum()), "offered_found": int(df["offered_found"].sum()),
            "both_found": int((df["tendered_found"] & df["offered_found"]).sum()),
            "filing_fee_exhibit": int(df["has_filing_fee_exhibit"].sum()),
            "live_requests": cl.n_requests, "seat_total": budget_used()}
    (OUT / "a16_tender_sample_summary.json").write_text(json.dumps(summ, indent=1, default=str) + "\n")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 160)
    print(df[["ftype", "company", "date_filed", "tendered_found", "offered_found", "tendered_span"]].to_string(index=False))
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
