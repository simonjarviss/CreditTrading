"""D7: customer-supplier contagion -- feasibility only (are customer links extractable, and how many events a year?).

    export QUANTT_ENV_FILE=/abs/path/config/.env
    python3 scripts/events/ssx/ssx_fil_d7_chain.py census --bulk-cache <cache root holding companyfacts.zip>

ZERO TRIALS. Bankruptcy filing counts, firm size from XBRL, and customer names
disclosed by suppliers. No price, no return.

WHY THIS FEASIBILITY CHECK
--------------------------
Hertzel, Li, Officer & Rodgers (JFE 2008): a customer's bankruptcy filing is
associated with negative, significant stock-price effects for its suppliers,
before and at the filing [V abstract]. Cohen & Frazzini (JF 2008): supplier
prices under-react to news about principal customers; a long-short strategy
earned over 150bp a month [V abstract]. Both need the LINK: which listed
supplier names which customer. ASC 280 requires the amount of revenue from each
10%-customer but not its identity; Reg S-K Item 101 has asked for the name when
the loss of the customer would be material (not re-read here [U]).

THE EVENT COUNT
---------------
Chapter 11 is 8-K item 1.03 (bankruptcy or receivership), from the bulk
submissions archive (every 8-K of every periodic filer). "Large" is total
assets (us-gaap:Assets, the last value filed before the 8-K) >= $1bn or
>= $100m, from the companyfacts archive.

THE LINK, TWO ROUTES
--------------------
1. Free: XBRL dimensional facts. The SEC's Financial Statement Data Sets carry a
   `segments` column in num.txt; a supplier that tags revenue concentration on
   a MajorCustomers member (e.g. `MajorCustomers=TheHomeDepotInc.`) names the
   customer machine-readably. Measured on one quarter elsewhere (CARDS note).
2. Licensed: Compustat `seg_customer` on R2 (customer name `cnms`, from
   datadate 2020-06-30 only). Used here for the 10-bankruptcy sample: for each
   large listed filer, supplier rows naming it in the two years before filing,
   matched on the customer's first two significant name tokens and then listed
   for a human read (`d7_sample_matches.csv`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx import ssx_fil_common as C  # noqa: E402

SALT = "ssx_fil_d7_v1"
N_SAMPLE = 10
OUT = C.OUT
STOP = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LLC", "LP", "HOLDINGS", "HOLDING", "GROUP",
        "THE", "PLC", "SA", "NV", "TRUST", "INTERNATIONAL", "INTL", "AND", "OF", "DE", "USA", "US",
        "CL", "CLASS", "NEW", "OLD", "REDH", "ADR"}


def tokens(name: str) -> list[str]:
    t = re.sub(r"/[A-Z]{2}/?|\\[A-Z]{2}\\?", " ", (name or "").upper())
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    return [w for w in t.split() if w not in STOP and len(w) > 1]


def assets_before(z, names, cik: int, date: pd.Timestamp):
    fn = f"CIK{int(cik):010d}.json"
    if fn not in names:
        return None
    j = json.loads(z.read(fn))
    node = j.get("facts", {}).get("us-gaap", {}).get("Assets")
    if not node:
        return None
    v = [x for x in node.get("units", {}).get("USD", []) if x.get("filed") and pd.Timestamp(x["filed"]) < date]
    if not v:
        return None
    v.sort(key=lambda x: (x["filed"], x.get("end", "")))
    return float(v[-1]["val"])


def census(bulk_cache: Path | None) -> dict:
    ev = pd.read_parquet(C.CACHE / "d6_8k_flag_events_linked.parquet")
    b = ev[ev["i103"]].copy()
    z = C.bulk_zip(C.COMPANYFACTS_ZIP_URL, bulk_cache)
    names = set(z.namelist())
    b["assets"] = [assets_before(z, names, c, d) for c, d in zip(b["cik"], b["date"])]
    g = b.groupby("year")
    yr = pd.DataFrame({"item_103": g.size(), "issuers": g["cik"].nunique(),
                       "assets_known": g["assets"].apply(lambda s: int(s.notna().sum())),
                       "assets_ge_100m": g["assets"].apply(lambda s: int((s >= 1e8).sum())),
                       "assets_ge_1bn": g["assets"].apply(lambda s: int((s >= 1e9).sum())),
                       "listed_common": g["listed_common"].sum(),
                       "listed_assets_ge_1bn": g.apply(lambda x: int((x["listed_common"] & (x["assets"] >= 1e9)).sum()), include_groups=False),
                       "issuers_assets_ge_1bn": g.apply(lambda x: x.loc[x["assets"] >= 1e9, "cik"].nunique(), include_groups=False)})
    yr.to_csv(OUT / "d7_bankruptcy_by_year.csv")

    # The 10-bankruptcy sample: large (>= $1bn), listed on the 8-K date, filed 2020-01-01..2022-12-31,
    # in declared sha256 order. Compustat seg_customer starts at datadate 2020-06-30, so a strictly
    # pre-filing window would be empty for most 2020 filers; the LINK is therefore looked for in
    # supplier reports dated from 2 years before to 1 year after the filing. That measures whether a
    # link exists (feasibility), not what a live rule knew on the day (stated in the CARDS note).
    pool = b[(b["assets"] >= 1e9) & b["listed_common"] & (b["date"] >= "2020-01-01") & (b["date"] <= "2022-12-31")]
    pool = pool.drop_duplicates("cik")
    meta = pd.read_parquet(C.CACHE / "subs_meta.parquet").set_index("cik")
    pick = C.declared_order(pool["accessionNumber"].tolist(), SALT)[:N_SAMPLE]
    p = C.CACHE / "comp_seg_customer.parquet"
    if not p.exists():
        r2, con = C._r2()
        sc = r2.q(con, f"SELECT * FROM read_parquet('{r2.r2_path('comp_na_daily_all', 'seg_customer')}')")
        sc.to_parquet(p)
    sc = pd.read_parquet(p)
    sc["datadate"] = pd.to_datetime(sc["datadate"])
    sc["tok"] = sc["cnms"].map(tokens)
    links = C.cik_permno_links(offline=True)
    rows, summary_rows = [], []
    for acc in pick:
        r = pool.set_index("accessionNumber").loc[acc]
        nm = meta.at[int(r["cik"]), "name"] if int(r["cik"]) in meta.index else ""
        conm = links.loc[links["cik"] == int(r["cik"]), "conm"]
        nm2 = conm.iloc[0] if len(conm) else nm
        key = tokens(nm2)[:2] or tokens(nm)[:2]
        win = sc[(sc["ctype"] == "COMPANY") & (sc["datadate"] <= r["date"] + pd.DateOffset(years=1))
                 & (sc["datadate"] >= r["date"] - pd.DateOffset(years=2))]
        # A distinctive first token (>= 5 letters) is enough to propose a match; a short one needs two.
        key = key[:1] if key and len(key[0]) >= 5 else key
        hit = win[win["tok"].map(lambda t, key=key: len(key) > 0 and t[:len(key)] == key)]
        sup = hit["gvkey"].nunique()
        summary_rows.append({"accession": acc, "cik": int(r["cik"]), "name": nm2, "date": r["date"].date().isoformat(),
                             "assets_usd": r["assets"], "match_key": " ".join(key), "supplier_gvkeys": int(sup),
                             "customer_names_matched": "; ".join(sorted(hit["cnms"].unique())[:5])})
        for h in hit.drop_duplicates(["gvkey", "cnms"]).itertuples():
            rows.append({"bankrupt": nm2, "supplier_gvkey": h.gvkey, "cnms": h.cnms, "datadate": h.datadate.date().isoformat(),
                         "salecs": h.salecs})
    S = pd.DataFrame(summary_rows)
    S.to_csv(C.CACHE / "d7_sample_summary_full.csv", index=False)           # Compustat customer strings: licensed
    S.drop(columns=["customer_names_matched"]).to_csv(OUT / "d7_sample_summary.csv", index=False)
    pd.DataFrame(rows).to_csv(C.CACHE / "d7_sample_matches.csv", index=False)   # licensed rows
    sc_y = sc[sc["ctype"] == "COMPANY"].groupby(sc["datadate"].dt.year).agg(rows=("gvkey", "size"), suppliers=("gvkey", "nunique"))
    summ = {"sample_n": int(len(S)), "sample_with_any_supplier": int((S["supplier_gvkeys"] > 0).sum()),
            "sample_suppliers_total": int(S["supplier_gvkeys"].sum()),
            "pool_large_listed_2020H2_2022": int(len(pool)),
            "seg_customer_company_rows_by_year": {int(k): {"rows": int(v.rows), "suppliers": int(v.suppliers)} for k, v in sc_y.iterrows()},
            "seg_customer_ctype_counts": {str(k): int(v) for k, v in sc["ctype"].value_counts().items()}}
    C.write_json(OUT / "d7_chain_summary.json", summ)
    print(yr.to_string())
    print(S.to_string())
    print(summ)
    return summ


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("census",))
    ap.add_argument("--bulk-cache", type=Path, default=None)
    a = ap.parse_args(argv)
    census(a.bulk_cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
