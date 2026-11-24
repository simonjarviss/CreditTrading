"""A5: sponsor (adviser-parent) M&A deals touching listed CEF/BDC families, 2010-2025, and the funds each touched (zero trials).

    export QUANTT_ENV_FILE=/abs/path/config/.env     # R2 (SDC); never printed
    python3 scripts/events/ssx/ssx_fund2_sponsor_deals.py

WHY THIS EXISTS
---------------
Idea A5: when a fund's adviser changes control, 1940 Act §15(a)(4) terminates
the advisory contract on assignment, so every fund in the family must hold a
shareholder vote on a new agreement. The event is one deal touching many
funds at once, so the INDEPENDENT count is deals, not funds. This script
takes the deal dates from SDC M&A on the R2 mirror (`tr_sdc_ma.wrds_ma_details`,
to 2026-07; a licensed database, so only deal names and dates are written,
no SDC financial fields) for a DECLARED list of deals whose targets advised
listed CEFs or BDCs, and measures the funds touched from EDGAR: listed fund
CIKs (the `ssx_fund2_offline_counts.classify` flag) whose index name carries
the family keyword and which filed a DEF 14A, PRE 14A or DEFA14A between the
announcement and 90 days after the effective date (the vote window).

The deal list is declared below, from the SDC search printed in the note
(target SIC 6282/6211/6799, CEF-sponsor names, 2009-2025). It is a judgement
list: deals not touching a listed CEF/BDC family (ETF-only, private-wealth or
UK-trust targets) are left out, and that is the recall limit. Keyword
matching on fund names can miss renamed funds and can add a same-named
unrelated fund; the per-deal fund list is written so it can be read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.events.ssx.ssx_fund2_common import OUT, CACHE, load_index, now_utc  # noqa: E402

# (SDC master_deal_no, short label, family-name regex on EDGAR fund names)
DEALS = [
    (2062780020, "Columbia Management -> Ameriprise", r"COLUMBIA"),
    (2628305020, "Nuveen -> TIAA", r"NUVEEN"),
    (3013549020, "Janus -> Henderson (merger of parents)", r"JANUS|HENDERSON"),
    (3003825040, "Pioneer -> Amundi", r"PIONEER"),
    (3055427020, "Calamos go-private", r"CALAMOS"),
    (3076665040, "Aberdeen -> Standard Life", r"ABERDEEN"),
    (3115245020, "Tortoise -> Lovell Minnick", r"TORTOISE"),
    (3234859020, "Triangle Capital portfolio / Barings externalisation", r"TRIANGLE CAPITAL|BARINGS BDC"),
    (3276399020, "OppenheimerFunds -> Invesco", r"OPPENHEIMER"),
    (3302900020, "Benefit Street -> Franklin", r"BENEFIT STREET|BUSINESS DEVELOPMENT CORP OF AMERICA"),
    (3363056020, "Oaktree -> Brookfield", r"OAKTREE"),
    (3515414020, "Legg Mason -> Franklin", r"WESTERN ASSET|LEGG MASON|LMP |CLEARBRIDGE"),
    (3645819020, "Eaton Vance -> Morgan Stanley", r"EATON VANCE"),
    (3651331020, "Wells Fargo AM -> GTCR/Reverence (Allspring)", r"WELLS FARGO|ALLSPRING"),
    (3820667020, "Oak Hill Advisors -> T. Rowe Price", r"OHA |T SERIES MIDDLE"),
    (4078769020, "Angelo Gordon -> TPG", r"AG TWIN BROOK|ANGELO GORDON"),
    (4086837020, "Putnam -> Franklin", r"PUTNAM"),
    (4224602020, "Amundi US -> Victory", r"PIONEER"),
    (4309018020, "HPS -> BlackRock", r"HPS CORPORATE"),
]


def main() -> int:
    from src.data.r2 import connect, r2_path, q
    from scripts.events.ssx.ssx_fund2_offline_counts import classify
    con = connect()
    p = r2_path("tr_sdc_ma", "wrds_ma_details")
    ids = ",".join(str(d[0]) for d in DEALS)
    sdc = q(con, f"""SELECT master_deal_no, dateann, dateeff, status, tmanames, amanames
                     FROM read_parquet('{p}') WHERE CAST(master_deal_no AS BIGINT) IN ({ids})""")
    if len(sdc) != len(DEALS):
        raise KeyError(f"SDC returned {len(sdc)} of {len(DEALS)} declared deals")
    sdc["master_deal_no"] = sdc["master_deal_no"].astype("int64")   # stored as text on the mirror
    sdc = sdc.set_index("master_deal_no")
    idx = load_index()
    idx["date_filed"] = pd.to_datetime(idx["date_filed"])
    f = classify(idx).set_index("cik")
    listed = set(f.index[f["listed"]])
    names = idx[idx["cik"].isin(listed)].groupby("cik")["company"].agg(lambda s: " | ".join(sorted(set(s))))
    prox = idx[idx["cik"].isin(listed) & idx["form"].isin(["DEF 14A", "PRE 14A", "DEFA14A"])]
    rows, funds = [], []
    for no, label, rx in DEALS:
        a, e = pd.Timestamp(sdc.loc[no, "dateann"]), pd.Timestamp(sdc.loc[no, "dateeff"])
        fam = names[names.str.upper().str.contains(rx, regex=True)]
        w = prox[prox["cik"].isin(fam.index) & prox["date_filed"].between(a, e + pd.Timedelta(days=90))]
        touched = sorted(w["cik"].unique())
        # family funds alive at announcement: any index filing in the 400 days before it
        alive = idx[idx["cik"].isin(fam.index) & idx["date_filed"].between(a - pd.Timedelta(days=400), a)]["cik"].nunique()
        rows.append({"sdc_deal": no, "deal": label, "announced": a.date(), "effective": e.date(),
                     "status": sdc.loc[no, "status"], "family_listed_ciks_alive": int(alive),
                     "listed_ciks_with_proxy_in_window": len(touched),
                     "proxy_accessions_in_window": int(w["accession"].nunique())})
        funds += [{"sdc_deal": no, "cik": int(c), "names": names[c]} for c in touched]
    D = pd.DataFrame(rows).sort_values("announced")
    D.to_csv(CACHE / "a5_sponsor_deals_rows.csv", index=False)          # with SDC deal numbers: cache only
    D.drop(columns=["sdc_deal"]).to_csv(OUT / "a5_sponsor_deals.csv", index=False)
    pd.DataFrame(funds).to_csv(CACHE / "a5_sponsor_deal_funds.csv", index=False)
    in_win = D[(pd.to_datetime(D["announced"]) >= "2010-01-01") | (pd.to_datetime(D["effective"]) >= "2010-01-01")]
    summ = {"built_utc": now_utc(), "deals_declared": len(D),
            "deals_touching_ge1_listed_fund": int((D["listed_ciks_with_proxy_in_window"] > 0).sum()),
            "funds_touched_total": int(D["listed_ciks_with_proxy_in_window"].sum()),
            "deals_announced_le_2022": int((pd.to_datetime(D["announced"]) <= "2022-12-31").sum()),
            "deals_by_year": pd.to_datetime(D["announced"]).dt.year.value_counts().sort_index().to_dict(),
            "n_in_window": len(in_win)}
    (OUT / "a5_sponsor_deals_summary.json").write_text(json.dumps(summ, indent=1, default=str) + "\n")
    pd.set_option("display.width", 220)
    print(D.to_string(index=False))
    print(json.dumps(summ, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
