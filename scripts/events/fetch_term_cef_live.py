"""Live term-CEF candidates: dated price, NAV and discount from CEFConnect, borrow flags from Alpaca.

    QUANTT_ENV_FILE=<path to config/.env> python3 scripts/events/fetch_term_cef_live.py
        # writes results/events/term_cef/term_cef_live_<today>.csv (the last 30 dated rows per fund)

WHY THIS EXISTS
---------------
SCALING §7.1 row 7 says "Live 2026-10-08: FTHY -4.7% (2027-08) and DTF -5.1%
(2028-03) are outside the holdout. BSL and BGB are holdout names." The agent
took those discounts from CEFConnect's DailyPricing snapshot, whose price was
dated 2026-10-08 and whose NAV was dated 2026-10-07. This fetches the DATED
daily rows instead (`/api/v3/pricinghistory/{TICKER}/1Y`, the endpoint the
repo already reads in `scripts/cef/fetch_daily.py`, `docs/REFERENCES.md` §8),
so a discount is always a price and a NAV of the same date, and the agent's
date can be re-read exactly. Nothing is written to `data/` (landmine 9).

TERM DATES are the 2026-10-09 agent's, with its labels: [V] where it read the
filing (FTHY 497 2020; ETX DEF 14A 2026-09-24; BTT 497 2012; PDO 424B1 2021),
[S] otherwise. They are carried for the "years to term" column only; nothing
here re-derives them (that needs the EDGAR fetcher, plan item 0.7).

READ-ONLY. CEFConnect is a public GET. Alpaca is read through
`AlpacaClient.asset` (GET /v2/assets/{symbol}, paper endpoint). `shortable`
changes daily: each row carries the time it was read.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:  # run as a script, not -m
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events"
TERM_CEF_DIR = OUT / "term_cef"        # the term-CEF outputs (term_pull_to_par.py's too); the notes sit in OUT
CC_URL = "https://www.cefconnect.com/api/v3/pricinghistory/{t}/1Y"
CC_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}  # as scripts/cef/fetch_daily.py
# ticker, stated termination date, maximum board extension (months), label (agent, 2026-10-09)
LIVE = (("BSL", "2027-05-31", 0, "S"), ("FTHY", "2027-08-01", 6, "V"), ("BGB", "2027-09-15", 0, "S"),
        ("DTF", "2028-03-01", 0, "S"), ("ETX", "2028-06-30", 12, "V"), ("RMI", "2030-10-25", 18, "S"),
        ("BTT", "2030-12-31", 0, "V"), ("NMCO", "2031-10-01", 24, "S"), ("PDO", "2033-01-27", 18, "V"),
        ("MMD", "2036-12-31", 0, "S"), ("BMN", "2037-09-30", 0, "S"))
KEEP_ROWS = 30
AGENT_DATE = pd.Timestamp("2026-10-08")


def cefconnect_history(ticker: str) -> pd.DataFrame:
    """CEFConnect's dated daily rows for `ticker`. Raises if the response has none."""
    import requests
    r = requests.get(CC_URL.format(t=ticker), headers=CC_HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json().get("Data")
    if not data or not data.get("PriceHistory"):
        raise ValueError(f"CEFConnect returned no PriceHistory for {ticker}")
    df = pd.DataFrame(data["PriceHistory"])
    out = pd.DataFrame({"ticker": ticker, "date": pd.to_datetime(df["DataDate"]).dt.normalize(),
                        "price": df["Data"].astype(float), "nav": df["NAVData"].astype(float),
                        "cc_discount_pct": df["DiscountData"].astype(float)})
    out["discount_pct"] = 100 * (out["price"] / out["nav"] - 1)
    out["cc_last_updated"] = data.get("LastUpdated")
    return out.sort_values("date").tail(KEEP_ROWS)


def main(argv=None) -> int:
    from quantt.broker.alpaca import AlpacaClient
    from scripts.events.acquirer_shortability import read_assets
    today = dt.date.today()
    fetched = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    hist = pd.concat([cefconnect_history(t) for t, *_ in LIVE], ignore_index=True)
    hist["fetched_utc"] = fetched
    uni = set(pd.read_csv(REPO / "data" / "cef" / "cef_universe.csv")["ticker"])
    a = read_assets(AlpacaClient.from_environment("cef"), [t for t, *_ in LIVE]).set_index("symbol")
    rows = []
    for t, term, ext, lab in LIVE:
        h = hist[hist["ticker"] == t].set_index("date")
        last = h.index.max()
        at = h.loc[AGENT_DATE] if AGENT_DATE in h.index else None
        yrs = (pd.Timestamp(term) - last).days / 365.25
        rows.append({"ticker": t, "term": term, "term_label": lab, "ext_months": ext, "in_universe": t in uni,
                     "disc_2026_10_08": round(at["discount_pct"], 2) if at is not None else None,
                     "cc_disc_2026_10_08": at["cc_discount_pct"] if at is not None else None,
                     "last_date": last.date(), "disc_last": round(h.at[last, "discount_pct"], 2),
                     "years_to_term": round(yrs, 2),
                     "disc_yield_pct_yr": round(-h.at[last, "discount_pct"] / yrs, 2),
                     "disc_yield_max_ext": round(-h.at[last, "discount_pct"] / (yrs + ext / 12), 2),
                     "alpaca_tradable": a.at[t, "tradable"] if t in a.index else None,
                     "alpaca_shortable": a.at[t, "shortable"] if t in a.index else None,
                     "alpaca_read_utc": a.at[t, "read_utc"] if t in a.index else None})
    summ = pd.DataFrame(rows)
    TERM_CEF_DIR.mkdir(parents=True, exist_ok=True)
    hist.to_csv(TERM_CEF_DIR / f"term_cef_live_{today.isoformat()}.csv", index=False)
    summ.to_csv(TERM_CEF_DIR / f"term_cef_live_summary_{today.isoformat()}.csv", index=False)
    pd.set_option("display.width", 220)
    print(f"CEFConnect fetched {fetched}; Alpaca read the same run")
    print(summ.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
