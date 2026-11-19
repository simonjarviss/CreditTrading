"""How big is a closed-end trust when it is wound up? Form 24F-2NT, the annual notice of units sold.

    QUANTT_ENV_FILE=<env> python3 results/ideas/uit_cef_flows/sizes.py fetch    # network, through EdgarClient only
    python3 results/ideas/uit_cef_flows/sizes.py parse                          # no network

WRITTEN 2026-11-18, after the interruption, before any return was read. It reads no return.

WHY 24F-2NT. A prospectus shows only the seed portfolio (about $150,000). What the trust
grew to is in the registrant's annual notices under rule 24f-2: item 5(i), the aggregate sale
price of units sold in the fiscal year, and item 5(ii), the aggregate price of units redeemed
or repurchased. A First Trust registrant ("FT <n>") files one for each fiscal year; the last
one's year ends on the Mandatory Termination Date (seen on FT 3144: $23.9M sold in year one,
$0.7M sold and $7.2M redeemed in the final year).
TWO ESTIMATES, because the notice does not say how much of the final year's redemption was
the wind-up itself and how much left earlier in that year [U]:
  size_high   all sales less redemptions in fiscal years that END more than 10 days before
              the termination date (everything still there at the start of the final year);
  size_low    all sales less all redemptions (what was never redeemed at all: paid out at
              termination or rolled into the next series). NaN when the final notice (a
              fiscal year ending within 10 days of the termination date or later) is not in
              the crawl, which ends with the 2025 Q4 index.
Both are in dollars at the prices units were sold at, not at termination prices [U], and both
are floored at zero. A registrant with several trusts is split equally between them [U].
Only registrants with a CLOSED-END TRUST (more than half of the holding lines are CRSP
closed-end funds; the same rule as explore.py) are fetched: that is the cap on this crawl.
"""
from __future__ import annotations

import gzip, re, sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = Path.home() / "quantt_research" / "uit_cef_flows"
CACHE = OUT / "edgar_cache"
PANEL = Path.home() / "quantt_research" / "crsp_cef_daily.parquet"
AMT = r"\$?\s*(\(?\s*\$?\s*[\d,]+(?:\.\d+)?\s*\)?|-\s*0\s*-)"
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"


def closed_end_ciks() -> pd.DataFrame:
    T = pd.read_parquet(OUT / "trusts.parquet")
    H = pd.read_parquet(OUT / "holdings.parquet").merge(T[["trust_id", "deposit"]], on="trust_id").sort_values("deposit")
    tk = pd.read_parquet(PANEL, columns=["ticker", "permno", "date"]).dropna(subset=["ticker"])
    tk["date"] = pd.to_datetime(tk["date"])
    m = pd.merge_asof(H, tk.sort_values("date").rename(columns={"date": "panel_date"}), left_on="deposit", right_on="panel_date",
                      by="ticker", direction="nearest", tolerance=pd.Timedelta(days=10))
    share = m.groupby("trust_id")["permno"].apply(lambda s: s.notna().mean())
    T = T.set_index("trust_id"); T["cef_share"] = share
    return T.reset_index()


def rows_for(ciks: set[str]) -> list[list[str]]:
    rows = [ln.split("|") for ln in (OUT / "idx.csv").read_text().splitlines()[1:]]
    return [r for r in rows if r[2].startswith("24F-2NT") and r[5] in ciks]


def amount(s: str) -> float:
    s = s.replace("$", "").replace(",", "").replace("(", "").replace(")", "").replace(" ", "")
    return 0.0 if s in ("-0-", "") else float(s)


def parse_notice(t: str) -> dict | None:
    """Fiscal-year end, units sold (5(i)) and redeemed (5(ii)) from one notice: text or the 2022+ XML."""
    if "<edgarSubmission" in t or "aggregateSalePriceOfSecuritiesSold" in t:
        g = lambda tag: (re.search(rf"<(?:\w+:)?{tag}>\s*([^<]*)<", t) or [None, None])[1]
        fy, sold, red = g("lastDayOfFiscalYear"), g("aggregateSalePriceOfSecuritiesSold"), g("aggregatePriceOfSecuritiesRedeemedOrRepurchasedInFiscalYear")
        if fy is None or sold is None or red is None:
            return None
        return {"fy_end": pd.to_datetime(fy, errors="coerce"), "sold": abs(float(sold)), "redeemed": abs(float(red))}
    fy = re.search(r"Last day of (?:the )?fiscal year for which this (?:Form|notice) is filed:?\s*(" + MONTH + r"\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})", t, re.I)
    sold = re.search(r"Aggregate sale price of securities sold.*?24\(f\)\s*:?\s*" + AMT, t, re.S | re.I)
    red = re.search(r"redeemed or\s+repurchased during the fiscal year\s*:?\s*" + AMT, t, re.S | re.I)
    if not (fy and sold and red):
        return None
    return {"fy_end": pd.to_datetime(re.sub(r"\s+", " ", fy.group(1)), errors="coerce"), "sold": amount(sold.group(1)), "redeemed": amount(red.group(1))}


def read(path: str) -> str:
    from scripts.data.edgar_client import cache_path
    b = cache_path("https://www.sec.gov/Archives/" + path, CACHE).read_bytes()
    if b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    return b.decode("latin-1")


def main() -> int:
    T = closed_end_ciks()
    ce = T[T["cef_share"] > 0.5]
    rows = rows_for(set(ce["cik"].astype(str)))
    print(len(ce), "closed-end trusts in", ce["cik"].nunique(), "registrants;", len(rows), "notices in the index")
    if sys.argv[1] == "fetch":
        from scripts.data.edgar_client import EdgarClient, cache_path
        c = EdgarClient(cache=CACHE)
        for i, r in enumerate(rows):
            url = "https://www.sec.gov/Archives/" + r[7]
            if not cache_path(url, CACHE).exists():
                c.get(url)
            if i % 500 == 0:
                print(i, r[6], r[4], flush=True)
        print("requests", c.n_requests)
        return 0
    N, bad = [], 0
    for r in rows:
        d = parse_notice(read(r[7]))
        if d is None or pd.isna(d["fy_end"]):
            bad += 1
            continue
        N.append({"cik": r[5], "filed": pd.Timestamp(r[6]), **d})
    N = pd.DataFrame(N).drop_duplicates(["cik", "fy_end"], keep="last")
    print("notices parsed", len(N), "| not parsed", bad)
    out = []
    ntr = T.groupby("cik")["trust_id"].nunique()
    for t in ce.itertuples():
        n = N[N["cik"] == str(t.cik)]
        if n.empty:
            continue
        early = n[n["fy_end"] < t.termination - pd.Timedelta(days=10)]
        final = n[n["fy_end"] >= t.termination - pd.Timedelta(days=10)]
        k = int(ntr[t.cik])
        high = max(n["sold"].sum() - early["redeemed"].sum(), 0.0) / k
        low = max(n["sold"].sum() - n["redeemed"].sum(), 0.0) / k if len(final) else float("nan")
        out.append({"trust_id": t.trust_id, "size_high": high, "size_low": low, "n_notices": len(n), "has_final_notice": bool(len(final)),
                    "trusts_in_registrant": k, "sold_total": n["sold"].sum() / k})
    S = pd.DataFrame(out)
    S.to_parquet(OUT / "sizes.parquet")
    print("trusts sized", len(S), "of", len(ce), "| with a final notice", int(S["has_final_notice"].sum()))
    print(S[["size_high", "size_low", "sold_total"]].describe(percentiles=[.1, .25, .5, .75, .9]).round(0).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
