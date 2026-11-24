"""Cheap independent cross-checks from the R2 mirror (lead's note, 2026-10-19): SDC IPO counts and Thomson code-P counts.

    export QUANTT_ENV_FILE=/abs/path/config/.env
    python3 scripts/events/ssx/ssx_ins_r2_crosscheck.py          # SDC + TR counts
    python3 scripts/events/ssx/ssx_ins_r2_crosscheck.py k5       # K5 split by SDC deal size; hedge flags today

WHY: the D5 IPO count is built from CRSP first-listing dates plus EDGAR 424B
filings (`ssx_ins_ipo_census.py`), and the D1 purchase count from the SEC
Insider Transactions Data Sets (`ssx_ins_insider_census.py`). The data
librarian's inventory (results/events/ssx/ssx_data/R2_FULL_INVENTORY_TABLES_2026-10-19.md)
shows two independent vendors on R2: SDC New Issues (`tr_sdc_ni.wrds_ni_details`,
to 2026-07-02) and Thomson Reuters insiders (`tr_insiders.table1`, to
2026-06-26). This script COUNTS rows per year in each, so the three sources sit
side by side; disagreements are reported, never averaged. Zero trials: no price,
no return.

FILTERS (stated, not tuned):
  SDC: ipo = 'Yes', nation = 'United States', security in COMMON_SECURITIES
       (units, MLP interests, beneficial interests, ADS excluded), sicp not 6770
       (blank check), counted as distinct master_deal_no by year(ipodate).
  TR:  formtype '4', trancode 'P', acqdisp 'A', counted as distinct
       (dcn, seqnum) rows by year(fdate), and distinct cusip6 issuers.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
OUT = REPO / "results" / "events" / "ssx" / "ssx_ins"
COMMON_SECURITIES = ("Common Shares", "Ord/Common Shs.", "Class A Shares", "Ordinary Shares", "Class A Ord Shs",
                     "Class B Shares")


def main() -> int:
    from src.data.r2 import connect, r2_path, q
    con = connect()
    con.execute("SET enable_progress_bar = false")
    sec = ", ".join(f"'{s}'" for s in COMMON_SECURITIES)
    sdc = q(con, f"""SELECT year(ipodate) AS year, count(DISTINCT master_deal_no) AS sdc_us_common_ipos
                     FROM read_parquet('{r2_path("tr_sdc_ni", "wrds_ni_details")}')
                     WHERE ipo = 'Yes' AND nation = 'United States' AND security IN ({sec})
                       AND coalesce(sicp, '') <> '6770' AND ipodate BETWEEN DATE '2006-01-01' AND DATE '2026-06-30'
                     GROUP BY 1 ORDER BY 1""")
    tr = q(con, f"""SELECT year(fdate) AS year, count(*) AS tr_p_rows,
                           count(DISTINCT cusip6) AS tr_p_issuers_cusip6
                    FROM (SELECT DISTINCT dcn, seqnum, fdate, cusip6
                          FROM read_parquet('{r2_path("tr_insiders", "table1")}')
                          WHERE formtype = '4' AND trancode = 'P' AND acqdisp = 'A'
                            AND fdate BETWEEN DATE '2006-01-01' AND DATE '2025-12-31')
                    GROUP BY 1 ORDER BY 1""")
    sdc.to_csv(OUT / "xcheck_sdc_ipos_by_year.csv", index=False)
    tr.to_csv(OUT / "xcheck_tr_insider_p_by_year.csv", index=False)
    meta_p = OUT / "ipo_meta.json"
    m = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    m["r2_crosscheck"] = {"ran_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "sdc_filter": f"ipo='Yes', nation='United States', security in {COMMON_SECURITIES}, sicp<>'6770'",
                          "tr_filter": "formtype='4', trancode='P', acqdisp='A', distinct (dcn, seqnum)"}
    meta_p.write_text(json.dumps(m, indent=1, default=str) + "\n")
    print(sdc.to_string(index=False))
    print(tr.to_string(index=False))
    return 0


if __name__ == "__main__" and len(sys.argv) == 1:
    raise SystemExit(main())


def k5_size_split() -> dict:
    """K5 refinement, still zero trials: is the shortable share higher for LARGE deals?

    Joins the K5 list (`ssx_ins_ipo_census.py alpaca`) to SDC by ticker
    (`upticker`) with |ipodate - 424B date| <= 7 days, and splits today's
    shortable flag by SDC proceeds (`totdolamt`, $m as SDC records it) at
    $100m. Offer proceeds are an offering term, not a market price, so no
    2023+ price is read. Also re-reads today's flags on the D1 hedge ETFs.
    """
    import pandas as pd
    from src.data.r2 import connect, r2_path, q
    from quantt.broker.alpaca import AlpacaClient
    k = pd.read_parquet(REPO / "results" / "events" / "ssx" / "_cache_ssx_ins" / "k5_ipo_alpaca_flags.parquet")
    k = k[k.at_alpaca]
    con = connect()
    con.execute("SET enable_progress_bar = false")
    s = q(con, f"""SELECT upticker, ipodate, totdolamt FROM read_parquet('{r2_path("tr_sdc_ni", "wrds_ni_details")}')
                   WHERE ipo = 'Yes' AND nation = 'United States' AND ipodate >= DATE '2024-12-01'""")
    s["ipodate"] = pd.to_datetime(s.ipodate)
    m = k.merge(s, left_on="ticker", right_on="upticker", how="left")
    m = m[m.ipodate.isna() | ((m.ipodate - m.ipo_filed).abs() <= pd.Timedelta(days=7))]
    m = m.sort_values("totdolamt", ascending=False).drop_duplicates("cik")
    today = pd.Timestamp("2026-10-19")
    out = {}
    for label, d in (("near_day_150_210", m[(m.age_days >= 150) & (m.age_days <= 210)]),
                     ("all_2025", m[m.ipo_filed.dt.year == 2025])):
        big = d[d.totdolamt >= 100]
        small = d[d.totdolamt < 100]
        out[label] = {"n": int(len(d)), "sdc_matched": int(d.totdolamt.notna().sum()),
                      "ge_100m": {"n": int(len(big)), "shortable": int((big.shortable == True).sum())},  # noqa: E712
                      "lt_100m": {"n": int(len(small)), "shortable": int((small.shortable == True).sum())}}  # noqa: E712
    c = AlpacaClient.from_environment("cef")
    A = {a["symbol"]: a for a in c.assets(status="active")}
    hedges = {h: ({"shortable": A[h]["shortable"], "etb": A[h]["easy_to_borrow"]} if h in A else "ABSENT")
              for h in ("IWM", "SPY", "IJR", "XLF", "XLK", "XLV", "XLE", "XLI", "XBI", "KRE")}
    out["hedge_flags_today"] = hedges
    return out


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "k5":
    r = k5_size_split()
    p = OUT / "ipo_meta.json"
    mm = json.loads(p.read_text())
    mm["k5_size_split"] = {"ran_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **r}
    p.write_text(json.dumps(mm, indent=1, default=str) + "\n")
    print(json.dumps(r, indent=1, default=str))
