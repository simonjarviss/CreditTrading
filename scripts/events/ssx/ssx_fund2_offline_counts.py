"""Offline EDGAR-index counts for A5 (proxies), A6 (CEF 8-K waves) and A16 (non-traded tender pressure). Zero trials.

    export QUANTT_ENV_FILE=/abs/path/config/.env     # R2 (CRSP headers for the "ever listed" flag); never printed
    python3 scripts/events/ssx/ssx_fund2_offline_counts.py

WHY THIS EXISTS
---------------
Three ideas in the ssx_fund2 seat (brief, 2026-10-19) need only counts of
filings by closed-end funds and BDCs, by form and period, split into LISTED
and NOT LISTED vehicles:

* A16 (non-traded BDC / tender-offer-fund / interval-fund redemption
  pressure as a private-credit state variable): SC TO-I and SC TO-I/A by
  unlisted funds per quarter, and N-23C3A (the interval-fund repurchase
  notice) per quarter, 2010-2025.
* A5 (adviser and sponsor changes): DEF 14A / PRE 14A / DEFA14A by fund CIKs
  per year, and how many are JOINT proxies (one accession indexed under many
  fund CIKs: the signature of a sponsor-wide vote, which is what an adviser
  change of control forces under 1940 Act §15(a)).
* A6 (control-share provisions): 8-Ks by listed non-BDC CEFs per month. A CEF
  rarely files an 8-K; bylaw amendments are 8-K item 5.03, so a sponsor-wide
  bylaw wave (the 2020-21 control-share adoptions) should appear as a spike.
  The index carries no item numbers, so the spike is a pointer, not a count
  of control-share adoptions; that limit is stated in the note.

Counts are of unique accessions (one filing) and of (CIK, accession) pairs
(one filing x one fund it covers); each table says which. No return, no price.

"LISTED" (ever, 2008-2025): the fund CIK (a) has a ticker in the SEC's
company_tickers_exchange.json on NYSE, Nasdaq or CBOE (the cached copy of
2026-10-12, so a fund that died earlier has none; OTC tickers do not count), or (b) filed an 8-A12B / 8-A12B/A 2008-2025, or (c)
matches a CRSP CIZ security of subtype CEF by normalised name (the A4 key).
A fund listed before 2008 that died before 2026 and has a name CRSP abbreviates
past the key can still be misfiled as unlisted; the share is bounded by a
hand-checked sample in the note, not assumed to be zero.

TYPES: BDC = filed N-54A/N-6F; interval = filed N-23C3A/B/C; else CEF.
A CIK can be both BDC and interval (rare); BDC wins, stated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.events.ssx.ssx_fund2_common import OUT, load_index, fund_rule, now_utc, offline_client  # noqa: E402
from scripts.events.ssx.ssx_fund2_bdc_listings import norm, crsp_cef_headers  # noqa: E402

START, END = pd.Timestamp("2010-01-01"), pd.Timestamp("2025-12-31")


def classify(idx: pd.DataFrame) -> pd.DataFrame:
    rule = fund_rule(idx)
    f = pd.DataFrame({"cik": list(rule), "set_rule": list(rule.values())})
    bdc = set(idx.loc[idx["form"].isin(["N-54A", "N-6F"]), "cik"])
    itv = set(idx.loc[idx["form"].isin(["N-23C3A", "N-23C3A/A", "N-23C3B", "N-23C3C"]), "cik"])
    f["ftype"] = ["BDC" if c in bdc else ("interval" if c in itv else "CEF") for c in f["cik"]]
    from scripts.data.fetch_edgar_events import TICKERS_URL
    j = offline_client().get_json(TICKERS_URL, max_age_s=None)       # cached 2026-10-12
    tk = pd.DataFrame(j["data"], columns=j["fields"])
    # Exchange tickers only: the file also lists OTC and exchange-less tickers (2,542 OTC and 176
    # None of 10,435 rows, read 2026-10-19), which would mark an unlisted fund as listed.
    has_tk = set(tk.loc[tk["exchange"].isin(["NYSE", "Nasdaq", "CBOE"]), "cik"].astype(int))
    a8 = set(idx.loc[idx["form"].isin(["8-A12B", "8-A12B/A"]), "cik"])
    crsp = crsp_cef_headers()
    keys = {norm(n) for ns in crsp["names"] for n in ns}
    names = idx[idx["cik"].isin(f["cik"])].groupby("cik")["company"].agg(lambda s: set(s))
    f["ticker_now"] = f["cik"].isin(has_tk)
    f["a8"] = f["cik"].isin(a8)
    f["crsp_name"] = [any(norm(n) in keys for n in names.get(c, set())) for c in f["cik"]]
    f["listed"] = f["ticker_now"] | f["a8"] | f["crsp_name"]
    return f


def main() -> int:
    idx = load_index()
    idx["date_filed"] = pd.to_datetime(idx["date_filed"])
    f = classify(idx)
    fi = f.set_index("cik")
    w = idx[idx["cik"].isin(fi.index) & idx["date_filed"].between(START, END)].copy()
    w["ftype"] = w["cik"].map(fi["ftype"])
    w["listed"] = w["cik"].map(fi["listed"])
    w["q"] = w["date_filed"].dt.to_period("Q").astype(str)
    w["y"] = w["date_filed"].dt.year
    out = {"built_utc": now_utc(), "fund_ciks": int(len(f)),
           "fund_ciks_by_type_listed": {f"{a}|listed={b}": int(n) for (a, b), n in f.groupby(["ftype", "listed"]).size().items()}}

    # ---- A16: tender filings by unlisted funds, per quarter (accessions, distinct issuers)
    t = w[w["form"].isin(["SC TO-I", "SC TO-I/A", "N-23C3A"])]
    g = (t.groupby(["q", "form", "ftype", "listed"])
          .agg(accessions=("accession", "nunique"), issuers=("cik", "nunique")).reset_index())
    g.to_csv(OUT / "a16_tender_counts_by_quarter.csv", index=False)
    un = t[~t["listed"]]
    yr = (un.groupby([un["date_filed"].dt.year.rename("year"), "form", "ftype"])
            .agg(accessions=("accession", "nunique"), issuers=("cik", "nunique")).reset_index())
    yr.to_csv(OUT / "a16_unlisted_tender_counts_by_year.csv", index=False)
    piv = un[un["form"] == "SC TO-I"].groupby(["q", "ftype"])["accession"].nunique().unstack("ftype").fillna(0).astype(int)
    out["a16"] = {
        "unlisted_SC_TO-I_per_year_by_type": yr[yr["form"] == "SC TO-I"].pivot(index="year", columns="ftype", values="accessions").fillna(0).astype(int).to_dict(),
        "unlisted_SC_TO-I/A_per_year_by_type": yr[yr["form"] == "SC TO-I/A"].pivot(index="year", columns="ftype", values="accessions").fillna(0).astype(int).to_dict(),
        "N-23C3A_per_year_all": t[t["form"] == "N-23C3A"].groupby("y")["accession"].nunique().to_dict(),
        "N-23C3A_issuers_per_year_all": t[t["form"] == "N-23C3A"].groupby("y")["cik"].nunique().to_dict(),
        "unlisted_BDC_SC_TO-I_issuers_per_year": un[(un["form"] == "SC TO-I") & (un["ftype"] == "BDC")].groupby("y")["cik"].nunique().to_dict(),
        "quarters_covered": int(piv.shape[0]),
    }

    # ---- A5: proxies by fund CIKs per year
    p = w[w["form"].isin(["DEF 14A", "PRE 14A", "DEFA14A"])].copy()
    ncik = p.groupby("accession")["cik"].nunique()
    p["joint_ge5"] = p["accession"].map(ncik) >= 5
    a5 = (p.groupby(["y", "form", "listed"])
            .agg(accessions=("accession", "nunique"), cik_accession_pairs=("cik", "size"),
                 joint_ge5_accessions=("accession", lambda s: s[p.loc[s.index, "joint_ge5"]].nunique())).reset_index())
    a5.to_csv(OUT / "a5_proxy_counts_by_year.csv", index=False)
    lp = p[p["listed"]]
    out["a5"] = {
        "listed_DEF14A_accessions_per_year": lp[lp["form"] == "DEF 14A"].groupby("y")["accession"].nunique().to_dict(),
        "listed_DEF14A_fund_pairs_per_year": lp[lp["form"] == "DEF 14A"].groupby("y").size().to_dict(),
        "listed_PRE14A_accessions_per_year": lp[lp["form"] == "PRE 14A"].groupby("y")["accession"].nunique().to_dict(),
        "listed_DEFA14A_accessions_per_year": lp[lp["form"] == "DEFA14A"].groupby("y")["accession"].nunique().to_dict(),
        "all_funds_DEF14A_accessions_2010_2025": int(p.loc[p["form"] == "DEF 14A", "accession"].nunique()),
        "listed_DEF14A_accessions_2010_2025": int(lp.loc[lp["form"] == "DEF 14A", "accession"].nunique()),
        "listed_DEF14A_joint_ge5_accessions_2010_2025": int(lp.loc[(lp["form"] == "DEF 14A") & lp["joint_ge5"], "accession"].nunique()),
    }
    # the sampling frame for the live classification (listed funds' DEF 14A, one row per accession)
    frame = (lp[lp["form"] == "DEF 14A"].sort_values("cik").groupby("accession")
               .agg(cik=("cik", "first"), date_filed=("date_filed", "first"), n_fund_ciks=("cik", "nunique"),
                    company=("company", "first")).reset_index())
    frame.to_csv(OUT.parent / "_cache_ssx_fund2" / "a5_def14a_frame.csv", index=False)

    # ---- A6: 8-Ks by listed non-BDC CEFs per month (bylaw waves show here)
    k = w[(w["form"] == "8-K") & w["listed"] & (w["ftype"] == "CEF")]
    m = k.groupby(k["date_filed"].dt.to_period("M").astype(str)).agg(
        accessions=("accession", "nunique"), fund_ciks=("cik", "nunique"))
    m.to_csv(OUT / "a6_listed_cef_8k_by_month.csv")
    out["a6"] = {"listed_cef_8k_fund_ciks_by_year": k.groupby("y")["cik"].nunique().to_dict(),
                 "top_months_by_fund_ciks": m.sort_values("fund_ciks", ascending=False).head(12)["fund_ciks"].to_dict(),
                 "median_month_fund_ciks_2015_2019": float(m.loc[(m.index >= "2015-01") & (m.index <= "2019-12"), "fund_ciks"].median())}
    (OUT / "offline_counts_summary.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
