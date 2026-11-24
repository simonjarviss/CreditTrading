"""B2 census: FEMA major-disaster declarations against single-state muni CEFs. Zero trials.

WHY
---
A single-state muni CEF holds one state's bonds. A major disaster there can
move its listed price before a matrix-priced NAV re-marks, and the discount
z-score would read the gap as cheapness. A subtract-only flag needs enough
independent (state, disaster) occasions a year to be worth a trial; the seat
brief's kill number is fewer than 30 independent pairs a year (declared before
this ran).

SOURCES AND TERMS
-----------------
* OpenFEMA, DisasterDeclarationsSummaries v2
  (https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries), keyless.
  Terms (https://www.fema.gov/about/openfema/terms-conditions, "last updated
  January 22, 2025", read 2026-10-19): use "solely for statistical research or
  as a reporting record"; cite the endpoint and version; carry the disclaimer
  "This product uses the Federal Emergency Management Agency's OpenFEMA API, but
  is not endorsed by FEMA." This census is statistical research. Whether a live
  trading flag fits that purpose clause is for the team lead.
* Single-state muni CEFs over time: SEC EDGAR quarterly master indexes, read
  OFFLINE from the shared cache (no live request). A fund counts in year y if a
  CIK in the closed-end/BDC marker-form set filed N-CSR or N-CSRS that year
  and its EDGAR name carries a state name and a muni keyword. Name regex is a
  census tool, not truth: every matched name is written out for checking.
* Today's tradability: one read-only Alpaca GET /v2/assets (--alpaca), names
  matched the same way, with tradable / shortable / easy_to_borrow.

INDEPENDENCE
------------
Three funds in one state hit by one declaration are ONE occasion, not three.
The gate counts distinct (state, disasterNumber) with at least one single-state
fund alive in that state that year; fund x disaster pairs are reported beside
it, labelled not independent. A stricter count, distinct (state, month), is
shown too, because one storm often produces several declarations.

Reproduce:
    python3 scripts/events/ssx/ssx_risk_b2_disasters.py                  # FEMA (cached after first run) + EDGAR offline
    QUANTT_ENV_FILE=<abs path> python3 scripts/events/ssx/ssx_risk_b2_disasters.py --alpaca
Output: results/events/ssx/ssx_risk/b2_*.csv, b2_summary.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
CACHE = REPO / "results" / "events" / "ssx" / "_cache_ssx_risk"
OUT = REPO / "results" / "events" / "ssx" / "ssx_risk"
FEMA_URL = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
FEMA_DISCLAIMER = ("This product uses the Federal Emergency Management Agency's OpenFEMA API, "
                   "but is not endorsed by FEMA.")
Y0, Y1 = 2008, 2025
KILL_PAIRS = 30

STATES = {
    "AL": "ALABAMA", "AK": "ALASKA", "AZ": "ARIZONA", "AR": "ARKANSAS", "CA": "CALIFORNIA", "CO": "COLORADO",
    "CT": "CONNECTICUT", "DE": "DELAWARE", "FL": "FLORIDA", "GA": "GEORGIA", "HI": "HAWAII", "ID": "IDAHO",
    "IL": "ILLINOIS", "IN": "INDIANA", "IA": "IOWA", "KS": "KANSAS", "KY": "KENTUCKY", "LA": "LOUISIANA",
    "ME": "MAINE", "MD": "MARYLAND", "MA": "MASSACHUSETTS", "MI": "MICHIGAN", "MN": "MINNESOTA",
    "MS": "MISSISSIPPI", "MO": "MISSOURI", "MT": "MONTANA", "NE": "NEBRASKA", "NV": "NEVADA",
    "NH": "NEW HAMPSHIRE", "NJ": "NEW JERSEY", "NM": "NEW MEXICO", "NY": "NEW YORK", "NC": "NORTH CAROLINA",
    "ND": "NORTH DAKOTA", "OH": "OHIO", "OK": "OKLAHOMA", "OR": "OREGON", "PA": "PENNSYLVANIA",
    "RI": "RHODE ISLAND", "SC": "SOUTH CAROLINA", "SD": "SOUTH DAKOTA", "TN": "TENNESSEE", "TX": "TEXAS",
    "UT": "UTAH", "VT": "VERMONT", "VA": "VIRGINIA", "WA": "WASHINGTON", "WV": "WEST VIRGINIA",
    "WI": "WISCONSIN", "WY": "WYOMING", "PR": "PUERTO RICO",
}
# longest names first so "WEST VIRGINIA" wins over "VIRGINIA", "NEW YORK" over "YORK"
_STATE_RE = re.compile(r"\b(" + "|".join(sorted((re.escape(v) for v in STATES.values()), key=len, reverse=True)) + r")\b")
# \bMUNI, not MUNI: "COMMUNITY" contains MUNI (a bank, TCBS, matched on 2026-10-19 before this fix)
_MUNI_RE = re.compile(r"\bMUNI|TAX[- ]?FREE|TAX[- ]?EXEMPT")
_NAME2CODE = {v: k for k, v in STATES.items()}


def state_of(name: str) -> str | None:
    """Two-letter code if the name is a single-state muni fund's, else None."""
    u = (name or "").upper().replace(".", " ")
    if not _MUNI_RE.search(u):
        return None
    m = _STATE_RE.findall(u)
    return _NAME2CODE[m[0]] if len(set(m)) == 1 else None


def fema(refresh: bool = False) -> pd.DataFrame:
    path = CACHE / "openfema_dr_2008_2025.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    import requests
    rows, skip = [], 0
    flt = (f"declarationType eq 'DR' and declarationDate ge '{Y0}-01-01T00:00:00.000Z' "
           f"and declarationDate le '{Y1}-12-31T23:59:59.999Z'")
    while True:
        r = requests.get(FEMA_URL, params={"$filter": flt, "$select": "disasterNumber,state,declarationType,"
                                           "declarationDate,incidentType,declarationTitle,incidentBeginDate",
                                           "$top": 1000, "$skip": skip, "$orderby": "id"},
                         headers={"User-Agent": "QUANTT research (statistical census)"}, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"OpenFEMA GET skip={skip} -> HTTP {r.status_code}")
        batch = r.json()["DisasterDeclarationsSummaries"]
        rows += batch
        if len(batch) < 1000:
            break
        skip += 1000
        time.sleep(1.0)
    df = pd.DataFrame(rows)
    df["declarationDate"] = pd.to_datetime(df.declarationDate).dt.tz_localize(None)
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return df


def edgar_single_state_funds() -> pd.DataFrame:
    from scripts.data.edgar_client import EdgarClient
    from scripts.data.fetch_edgar_events import parse_master_index, INDEX_URL, MARKER_FORMS
    c = EdgarClient(offline=True)
    frames = []
    for y in range(Y0, Y1 + 1):
        for q in range(1, 5):
            df = parse_master_index(c.get_text(INDEX_URL.format(y=y, q=q)), f"{y}Q{q}",
                                    keep_forms=MARKER_FORMS | {"N-CSR", "N-CSRS"})
            df["year"] = y
            frames.append(df)
    idx = pd.concat(frames, ignore_index=True)
    marker = set(idx.loc[idx.form.isin(MARKER_FORMS), "cik"])
    ncsr = idx[idx.form.isin(["N-CSR", "N-CSRS"]) & idx.cik.isin(marker)]
    names = ncsr.sort_values("date_filed").groupby("cik").company.last()
    st = names.map(state_of).dropna()
    alive = ncsr[ncsr.cik.isin(st.index)].groupby(["cik", "year"]).size().reset_index()[["cik", "year"]]
    alive["state"] = alive.cik.map(st)
    alive["company"] = alive.cik.map(names)
    return alive, marker


def alpaca_today(cef_ciks: set) -> pd.DataFrame:
    from quantt.broker.alpaca import AlpacaClient, PAPER_BASE
    c = AlpacaClient.from_environment("cef")
    raw = c._get(PAPER_BASE, "/v2/assets", {"status": "active", "asset_class": "us_equity"})
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("GET /v2/assets returned no list")
    rows = []
    for a in raw:
        s = state_of(a.get("name") or "")
        if s is None:
            continue
        rows.append({"symbol": a["symbol"], "name": a.get("name"), "state": s, "exchange": a.get("exchange"),
                     "tradable": bool(a.get("tradable")), "shortable": bool(a.get("shortable")),
                     "easy_to_borrow": a.get("easy_to_borrow")})
    df = pd.DataFrame(rows).sort_values(["state", "symbol"])
    # CEF or not: the symbol's CIK (SEC ticker file, cached 2026-10-12) is in the
    # closed-end marker-form set. ETFs and operating companies are not.
    j = json.loads((REPO / "results/events/_cache_edgar/www.sec.gov/files/company_tickers_exchange.json").read_text())
    t = pd.DataFrame(j["data"], columns=j["fields"])
    sym2cik = dict(zip(t.ticker, t.cik.astype(int)))
    df["cik"] = df.symbol.map(sym2cik)
    df["is_cef"] = df.cik.isin(cef_ciks)
    df.attrs["read_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    df.attrs["active_assets"] = len(raw)
    return df


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--alpaca", action="store_true")
    ap.add_argument("--refresh-fema", action="store_true")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    f = fema(a.refresh_fema)
    f["year"] = f.declarationDate.dt.year
    f = f[f.year.between(Y0, Y1)]
    dis = f.drop_duplicates(["disasterNumber"])[["disasterNumber", "state", "year", "declarationDate",
                                                  "incidentType", "declarationTitle"]]
    sy = dis.groupby(["state", "year"]).size().unstack(fill_value=0)
    sy.to_csv(OUT / "b2_fema_dr_state_year.csv")

    funds, marker = edgar_single_state_funds()
    funds.to_csv(OUT / "b2_single_state_muni_cef_years.csv", index=False)
    fy = funds.groupby(["year", "state"]).cik.nunique().rename("n_funds").reset_index()

    rows = []
    for y in range(Y0, Y1 + 1):
        live = fy[fy.year == y]
        d = dis[(dis.year == y) & dis.state.isin(live.state)]
        nf = live.set_index("state").n_funds
        rows.append({"year": y, "single_state_funds": int(nf.sum()), "states_with_funds": int(len(nf)),
                     "indep_state_disaster_pairs": int(len(d)),
                     "indep_state_month_pairs": int(d.assign(m=d.declarationDate.dt.to_period("M"))
                                                    .drop_duplicates(["state", "m"]).shape[0]),
                     "fund_disaster_pairs_not_indep": int(d.state.map(nf).sum()),
                     "all_dr_declarations_all_states": int((dis.year == y).sum())})
    py = pd.DataFrame(rows)
    py.to_csv(OUT / "b2_pairs_per_year.csv", index=False)

    summ = {"fema_disclaimer": FEMA_DISCLAIMER, "fema_endpoint": FEMA_URL + " (v2)",
            "fema_rows": int(len(f)), "fema_distinct_dr": int(len(dis)),
            "years": [Y0, Y1], "kill_pairs_per_year": KILL_PAIRS,
            "indep_pairs_per_year_median": float(py.indep_state_disaster_pairs.median()),
            "indep_state_month_per_year_median": float(py.indep_state_month_pairs.median()),
            "indep_pairs_2021_2025_median": float(py[py.year >= 2021].indep_state_disaster_pairs.median()),
            "single_state_funds_2008": int(py.loc[py.year == Y0, "single_state_funds"].iloc[0]),
            "single_state_funds_2025": int(py.loc[py.year == Y1, "single_state_funds"].iloc[0]),
            "years_below_kill": int((py.indep_state_disaster_pairs < KILL_PAIRS).sum()),
            "funds_by_state_2025": fy[fy.year == Y1].set_index("state").n_funds.to_dict(),
            "indep_pairs_per_year_median_excl_PR": float(pd.Series([
                int(((dis.year == y) & dis.state.isin(set(fy[(fy.year == y) & (fy.state != "PR")].state))).sum())
                for y in range(Y0, Y1 + 1)]).median())}
    summ["verdict"] = "KILL" if summ["indep_pairs_per_year_median"] < KILL_PAIRS else "PASS"
    if a.alpaca:
        al = alpaca_today(marker)
        al.to_csv(OUT / f"b2_alpaca_single_state_muni_{dt.date.today().isoformat()}.csv", index=False)
        alc = al[al.is_cef]
        summ["alpaca_today_cef_only"] = {"n": int(len(alc)), "shortable": int(alc.shortable.sum()),
                                         "easy_to_borrow": int((alc.easy_to_borrow == True).sum()),  # noqa: E712
                                         "by_state": alc.groupby("state").symbol.apply(list).to_dict(),
                                         "shortable_symbols": alc.loc[alc.shortable, "symbol"].tolist(),
                                         "not_in_sec_ticker_file": al.loc[al.cik.isna(), "symbol"].tolist()}
        summ["alpaca_today"] = {"read_at_utc": al.attrs["read_at_utc"], "active_assets": al.attrs["active_assets"],
                                "n": int(len(al)), "tradable": int(al.tradable.sum()),
                                "shortable": int(al.shortable.sum()),
                                "easy_to_borrow": int((al.easy_to_borrow == True).sum()),   # noqa: E712
                                "by_state": al.groupby("state").symbol.apply(list).to_dict(),
                                "shortable_symbols": al.loc[al.shortable, "symbol"].tolist()}
        u = pd.read_csv(REPO / "data" / "cef" / "cef_universe.csv")
        summ["in_cef_universe_44"] = sorted(set(al.symbol) & set(u.ticker))
    (OUT / "b2_summary.json").write_text(json.dumps(summ, indent=1, default=str))
    print(py.to_string(index=False))
    print(json.dumps(summ, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
