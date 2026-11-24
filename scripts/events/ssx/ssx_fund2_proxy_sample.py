"""A5: classify a seeded random sample of listed CEF/BDC DEF 14A proxies for an advisory-agreement proposal (zero trials).

    export QUANTT_ENV_FILE=/abs/path/config/.env     # SEC_USER_AGENT; never printed
    python3 scripts/events/ssx/ssx_fund2_proxy_sample.py [--n 30] [--seed 20261019]

WHY THIS EXISTS
---------------
Idea A5 (adviser and sponsor changes) needs to know how often a fund proxy
carries an ADVISORY-AGREEMENT proposal, because that is the filing an adviser
change of control forces: under 1940 Act §15(a)(4) an advisory contract
terminates on its "assignment", and a change of control of the adviser is an
assignment, so shareholders must approve a new agreement. Annual-meeting
proxies (director elections only) are the background. The offline counts
(`ssx_fund2_offline_counts.py`) give the denominator; this samples the
numerator. The frame is every DEF 14A accession 2010-2025 indexed under a
listed fund CIK (`_cache_ssx_fund2/a5_def14a_frame.csv`), sampled with a
stated seed so the sample is reproducible and not picked.

The regex is deliberately narrow and is checked by reading: a proxy is
"advisory" if it asks shareholders to APPROVE a new or amended investment
advisory / management / sub-advisory agreement. The matching span is saved so
every classification can be re-read.
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

from scripts.events.ssx.ssx_fund2_common import OUT, CACHE, BudgetedClient, budget_used, now_utc  # noqa: E402
from scripts.events.ssx.ssx_fund2_bdc_listings import _strip_html  # noqa: E402

ADV_RE = re.compile(r"(?:to )?approv\w* (?:of )?(?:a |the )?(?:new |proposed |amended |interim )?(?:investment )?"
                    r"(?:sub-?advisory|advisory|management|investment management|sub-?investment advisory)"
                    r"(?: and administration)? agreement", re.I)
SUB_RE = re.compile(r"sub-?advis", re.I)
MERGER_RE = re.compile(r"reorganization|merger of|agreement and plan of", re.I)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20261019)
    a = ap.parse_args(argv)
    from scripts.data.edgar_client import filing_txt_url
    frame = pd.read_csv(CACHE / "a5_def14a_frame.csv", parse_dates=["date_filed"])
    samp = frame.sample(n=a.n, random_state=a.seed).sort_values("date_filed")
    cl = BudgetedClient("a5_proxy_sample", a.n + 2)
    rows = []
    for r in samp.itertuples(index=False):
        t = _strip_html(cl.get_text(filing_txt_url(int(r.cik), r.accession)))
        head = t[:60000]                                  # the notice and proposal list sit at the front
        m = ADV_RE.search(head)
        rows.append({"accession": r.accession, "cik": int(r.cik), "date_filed": r.date_filed.date(),
                     "company": r.company, "n_fund_ciks": int(r.n_fund_ciks),
                     "advisory_proposal": bool(m), "sub_advisory": bool(m and SUB_RE.search(m.group(0))),
                     "reorganization_mentioned": bool(MERGER_RE.search(head[:20000])),
                     "span": head[max(0, m.start() - 200): m.end() + 200] if m else ""})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "a5_proxy_sample.csv", index=False)
    summ = {"built_utc": now_utc(), "frame_accessions": int(len(frame)), "n": int(len(df)), "seed": a.seed,
            "advisory_proposal": int(df["advisory_proposal"].sum()),
            "sub_advisory": int(df["sub_advisory"].sum()),
            "joint_ge5_in_sample": int((df["n_fund_ciks"] >= 5).sum()),
            "advisory_among_joint_ge5": int(df.loc[df["n_fund_ciks"] >= 5, "advisory_proposal"].sum()),
            "live_requests": cl.n_requests, "seat_total": budget_used()}
    (OUT / "a5_proxy_sample_summary.json").write_text(json.dumps(summ, indent=1, default=str) + "\n")
    print(df[["date_filed", "company", "n_fund_ciks", "advisory_proposal", "sub_advisory"]].to_string(index=False))
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
