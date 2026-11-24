"""G1a, measured today: can the acquirer leg of a CEF merger pair be shorted at Alpaca?

    QUANTT_ENV_FILE=<path to config/.env> python3 scripts/events/acquirer_shortability.py

READ-ONLY. Every call is a GET through `quantt.broker.alpaca.AlpacaClient`
(paper endpoint only, keys from the file `$QUANTT_ENV_FILE` names, never
printed): `/v2/assets/{symbol}` and the market-data corporate-actions feed. No
order path is reachable from here.

WHY THIS EXISTS
---------------
Gate G1a of `results/cef/RESEARCH_PLAN_2026-10-09.md`: the merger pair is long
the target and short the acquirer; if the acquirers cannot be borrowed, the
hedged pair cannot be built, and a long-target-only version is a beta-carrying
bet that the 2026-10-09 "alpha only" ruling excludes. The 2026-10-09 agent
answered it from `results/data/universe_2026-10-08/universe_map.csv`: "26 of
59 historical acquirers not shortable". That map is a snapshot of 2026-10-08,
and it matched acquirers by TICKER, so a ticker now carried by a different
security (or by a fund that has since merged away) counted as the acquirer.
This re-measures it from Alpaca now and keeps CRSP's identity check beside each
row (`same_fund_same_ticker_at_crsp_end`, from `merger_pairs.py`).

WHAT IT CANNOT MEASURE
----------------------
The gate's first half -- acquirers in PENDING CEF/BDC mergers today -- needs an
announcement feed. Alpaca's corporate-actions data is almost entirely
effective actions: asked on 2026-10-11 for 2026-10-10..2028-12-31 it returned
ONE future-dated merger (NSC -> UNP, 2027-03-31) and no CEF or BDC. So its
coverage of pending deals is partial at best [U], and an empty pending list
from it is not evidence that none exist. EDGAR is the source (plan item 0.7),
once the team lead supplies the SEC contact user-agent. This script still asks
the feed for the next two years and reports what it lists, and, as the nearest
measurable proxy, lists mergers COMPLETED in the last 365 days whose acquirer
is a CEF or BDC (family from the 2026-10-08 universe map), reading each
acquirer's borrow flags now. Those are counts and flags, not returns, so the
sealed 2023+ time holdout is not touched.

`shortable` and `easy_to_borrow` CHANGE DAILY (CLAUDE.md landmine 5). Every row
carries the UTC time it was read; it is true on that date only.
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
ACQ_CSV = OUT / "merger_acquirers_2010_2022.csv"
G1A_DIR = OUT / "g1a"           # this gate's outputs: the note sits in OUT, its data here
UNIVERSE_MAP = REPO / "results" / "data" / "universe_2026-10-08" / "universe_map.csv"
FIELDS = ("name", "status", "exchange", "tradable", "shortable", "easy_to_borrow", "borrow_status")


def read_assets(client, symbols) -> pd.DataFrame:
    """GET /v2/assets/{symbol} for each symbol; a 404 is a recorded finding."""
    from quantt.broker.alpaca import AssetNotFound
    rows = []
    for sym in sorted(set(symbols)):
        t = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        try:
            a = client.asset(sym)
            rows.append({"symbol": sym, "read_utc": t, "found": True, **{f: a.get(f) for f in FIELDS}})
        except AssetNotFound:
            rows.append({"symbol": sym, "read_utc": t, "found": False})
    return pd.DataFrame(rows)


def recent_mergers(client, days_back: int = 365, days_fwd: int = 730) -> pd.DataFrame:
    """Stock and stock-and-cash mergers effective from `days_back` days ago to
    `days_fwd` days ahead, from the market-data corporate-actions feed
    (GET /v1/corporate-actions), paged. Future-dated rows are the feed's only
    view of a pending deal (module docstring: partial)."""
    start = dt.date.today() - dt.timedelta(days=days_back)
    end = dt.date.today() + dt.timedelta(days=days_fwd)
    rows, token = [], None
    while True:
        params = {"types": "stock_merger,stock_and_cash_merger", "start": start.isoformat(),
                  "end": end.isoformat(), "limit": 1000}
        if token:
            params["page_token"] = token
        r = client._get(client._data, "/v1/corporate-actions", params)
        if not isinstance(r, dict) or "corporate_actions" not in r:
            raise ValueError("GET /v1/corporate-actions: no 'corporate_actions' in the response")
        for typ, items in r["corporate_actions"].items():
            for it in items:
                rows.append({"type": typ, **it})
        token = r.get("next_page_token")
        if not token:
            break
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    from quantt.broker.alpaca import AlpacaClient
    client = AlpacaClient.from_environment("cef")
    today = dt.date.today().isoformat()
    if not ACQ_CSV.exists():
        raise FileNotFoundError(f"{ACQ_CSV} is missing: run scripts/events/merger_pairs.py first")

    # --- historical acquirers (the 2010-22 priced sample)
    acq = pd.read_csv(ACQ_CSV)
    a = read_assets(client, acq["a_ticker"])
    h = acq.merge(a, left_on="a_ticker", right_on="symbol", how="left")
    G1A_DIR.mkdir(parents=True, exist_ok=True)
    h.to_csv(G1A_DIR / f"alpaca_acquirers_{today}.csv", index=False)
    tk = h[h["in_ticker_only_sample"]].drop_duplicates("a_ticker").copy()
    # Muni by CRSP name, the same words merger_pairs.classify keys on: a label
    # for the split the original reported ("mostly munis"), not a fact.
    tk["muni_by_name"] = tk["a_comnam"].fillna("").str.contains(r"MUN|TAX FR|TAX EX|QLTY INC MUN")
    summary = {"read_date": today}
    print(f"== historical acquirers, Alpaca read {today}")
    for lab, g in (("all_tickers_original_set", tk),
                   ("same_fund_same_ticker_at_crsp_end", tk[tk["same_fund_same_ticker_at_crsp_end"]])):
        act = g[(g["found"] == True) & (g["status"] == "active")]  # noqa: E712  (NaN for not-found rows)
        d = {"tickers": len(g), "not_found": int((g["found"] != True).sum()),  # noqa: E712
             "inactive": int(((g["found"] == True) & (g["status"] != "active")).sum()),  # noqa: E712
             "active": len(act), "active_shortable": int((act["shortable"] == True).sum()),  # noqa: E712
             "active_not_shortable": int((act["shortable"] == False).sum()),  # noqa: E712
             "active_easy_to_borrow": int((act["easy_to_borrow"] == True).sum()),  # noqa: E712
             "active_muni_by_name": int(act["muni_by_name"].sum()),
             "active_muni_shortable": int((act["muni_by_name"] & (act["shortable"] == True)).sum())}  # noqa: E712
        summary[lab] = d
        print(lab, d)

    # --- the pending-merger proxy: recent completed CEF/BDC mergers
    um = pd.read_csv(UNIVERSE_MAP)[["symbol", "family"]]
    cefbdc = set(um.loc[um["family"].fillna("").str.match(r"^(cef_|bdc$)"), "symbol"])
    rm = recent_mergers(client)
    if rm.empty:
        raise ValueError("GET /v1/corporate-actions returned no stock mergers for the last 365 days: "
                         "an empty feed is not a finding about CEF mergers")
    fut = rm[pd.to_datetime(rm["effective_date"]) > pd.Timestamp(today)]
    summary["feed_future_dated_any_issuer"] = fut[["effective_date", "acquiree_symbol", "acquirer_symbol"]].astype(str).values.tolist()
    rm = rm[rm["acquirer_symbol"].isin(cefbdc) & (rm["acquirer_symbol"] != rm["acquiree_symbol"])]
    summary["feed_future_dated_cef_bdc"] = int((pd.to_datetime(rm["effective_date"]) > pd.Timestamp(today)).sum())
    # The feed repeats some actions (same pair, a rate differing in the 6th
    # decimal, or a second effective date three days later: BXMX/DIAX->SPXX).
    # One merger is one (acquiree, acquirer) pair; the repeats stay in the CSV.
    n_rows = len(rm)
    ra = read_assets(client, rm["acquirer_symbol"])
    rm = rm.merge(ra, left_on="acquirer_symbol", right_on="symbol", how="left")
    rm.to_csv(G1A_DIR / f"alpaca_recent_cef_bdc_mergers_{today}.csv", index=False)
    ev = rm.drop_duplicates(["acquiree_symbol", "acquirer_symbol"])
    u = rm.drop_duplicates("acquirer_symbol")
    summary["last_365d_and_future"] = {"feed_rows": n_rows, "mergers": len(ev), "acquirers": len(u),
                              "acquirers_shortable": int((u["shortable"] == True).sum()),  # noqa: E712
                              "acquirers_not_shortable": int((u["shortable"] == False).sum()),  # noqa: E712
                              "mergers_with_shortable_acquirer": int((ev["shortable"] == True).sum())}  # noqa: E712
    print("\n== CEF/BDC acquirers in stock mergers effective in the last 365 days (or listed as future):",
          summary["last_365d_and_future"], "| future-dated, any issuer:", summary["feed_future_dated_any_issuer"],
          "| future-dated CEF/BDC:", summary["feed_future_dated_cef_bdc"])
    import json
    (G1A_DIR / f"alpaca_g1a_summary_{today}.json").write_text(json.dumps(summary, indent=1))
    print(rm[["effective_date", "acquiree_symbol", "acquirer_symbol", "acquirer_rate", "type",
              "shortable", "easy_to_borrow", "name"]].sort_values("effective_date").to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
