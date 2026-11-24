"""Convertible issues: does Alpaca's news feed name the deal, and when, against SDC's issue date?

    QUANTT_ENV_FILE=<env> python3 results/ideas/convert_issuance/news_dating.py

WHY: the rebound book (explore.py) has no live list of pricings. Alpaca's news feed
(Benzinga headlines) is the candidate. Before any reader is built, measure on last year's
issues: for how many does the feed carry a headline naming a convertible, and how does the
first such headline's time sit against SDC's issue date D? The test decides at the close of
D+1 and its result decays by the day (0.87 from D+2, 0.67 from D+3, 0.45 from D+4), so a
feed that is a day late is a different trade.

WHAT IT READS (read-only; the core account's key, as the shadow books do):
  the staged SDC convertible events with an issue date in --year, their CRSP ticker on the
  issue date (staged daily file has none, so the ticker is read from R2's daily table);
  GET /v1beta1/news for each ticker from D-7 to D+3 calendar days; headlines matching
  "convertible" (case-insensitive). The first such headline's New York time is compared
  with 16:00 on D-1, D and D+1.
Writes `~/quantt_research/convert_news/news_dating_<year>.json` and prints the counts. The file
pairs each ticker with SDC's issue date and market, which are licensed rows: it stays outside
the repository (corrected 2026-11-15: the first version wrote it beside this script).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
OUT = RES / "convert_news"      # outside the repository: each row pairs a ticker with SDC's issue date
NY = ZoneInfo("America/New_York")
PAT = re.compile(r"convertible", re.I)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2025)
    a = ap.parse_args(argv)
    from quantt.broker.alpaca import AlpacaClient, _SYMBOL_RE
    from src.data import r2
    ev = pd.read_parquet(RES / "sdc_convertibles.parquet")
    ev["issue_date"] = pd.to_datetime(ev["issue_date"])
    ev = ev[ev["issue_date"].dt.year == a.year]
    con = r2.connect()
    con.register("ev", ev[["permno", "issue_date"]])
    tk = con.execute(f"""select e.permno, e.issue_date, d.ticker from ev e join read_parquet('{r2.r2_path("crsp_a_stock", "dsf_v2")}') d
                         on d.permno = e.permno and d.dlycaldt = cast(e.issue_date as date)""").df()
    ev = ev.merge(tk, on=["permno", "issue_date"], how="left")
    c = AlpacaClient.from_environment("cef")
    rows = []
    for r in ev.itertuples():
        d = r.issue_date.date()
        rec = {"ticker": r.ticker, "issue_date": d.isoformat(), "market": r.market, "headlines": 0, "first_ny": None, "first_headline": None}
        if isinstance(r.ticker, str) and _SYMBOL_RE.match(r.ticker):
            news, token = [], None
            for _ in range(20):
                p = {"symbols": r.ticker, "start": (d - dt.timedelta(days=7)).isoformat() + "T00:00:00Z",
                     "end": (d + dt.timedelta(days=4)).isoformat() + "T00:00:00Z", "limit": 50, "sort": "asc"}
                if token:
                    p["page_token"] = token
                body = c._get(c._data, "/v1beta1/news", p)
                news += body.get("news") or []
                token = body.get("next_page_token")
                if not token:
                    break
            hits = [(dt.datetime.fromisoformat(n["created_at"].replace("Z", "+00:00")).astimezone(NY), n["headline"])
                    for n in news if PAT.search(n.get("headline") or "")]
            rec["all_news_in_window"] = len(news)
            rec["headlines"] = len(hits)
            if hits:
                t, h = min(hits)
                rec["first_ny"], rec["first_headline"] = t.isoformat(), h[:160]
                close = lambda k: dt.datetime.combine(d + dt.timedelta(days=k), dt.time(16, 0), tzinfo=NY)  # noqa: E731
                # calendar-day buckets around SDC's date; sessions are not needed for a first read
                rec["bucket"] = ("before the close of D-1" if t <= close(-1) else "after it, by the close of D" if t <= close(0)
                                 else "after it, by the close of D+1" if t <= close(1) else "later")
        rows.append(rec)
    df = pd.DataFrame(rows)
    summary = {"read_on": dt.date.today().isoformat(), "year": a.year, "events": int(len(df)),
               "with_a_convertible_headline": int((df["headlines"] > 0).sum()),
               "with_any_news_in_window": int((df.get("all_news_in_window", 0) > 0).sum()),
               "first_headline_bucket (calendar days)": df["bucket"].value_counts().to_dict() if "bucket" in df else {},
               "by_market": {m: {"events": int(len(g)), "with_headline": int((g["headlines"] > 0).sum())} for m, g in df.groupby("market")}}
    print(json.dumps(summary, indent=1))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"news_dating_{a.year}.json").write_text(json.dumps({"summary": summary, "events": rows}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
