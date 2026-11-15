"""Special dividends: is CRSP's declaration date the day the dividend became public? A sample against EDGAR.

    QUANTT_ENV_FILE=<env> python3 results/ideas/special_dividends/edgar_dates.py

WHY: the WAIT book (explore.py) decides at the close of D1, the first session after CRSP's
declaration date, on the assumption that the dividend is public by then. The card says this
was never checked against a company filing. If CRSP's date ran EARLY (the board's date, with
the press release days later) the book would be trading on news nobody had: lookahead. If it
ran LATE the book is merely slow. Not pre-specified; written 2026-11-15 after the result.

WHAT IT DOES
  sample   WAIT-eligible events with an ex-date from 2019, whose CRSP ticker on the ex-date
           is in the SEC's current ticker list (survivors and unchanged tickers only: stated,
           not corrected). --n of them, drawn with a fixed seed.
  filings  the company's 8-Ks accepted from 10 calendar days before the declaration date to
           7 after D1, from EDGAR's submissions index (acceptance time to the second).
  mention  each such 8-K's full text is searched for "special" within 60 characters of
           "dividend" (either order). The first accepted 8-K with a mention dates the news.
  classes  A  accepted by the close (16:00 New York) of the declaration date or earlier;
           B  after that and by the close of D1: public when the book decides;
           C  after the close of D1: the first 8-K is LATER than the decision. An 8-K may
              follow a press release by up to four business days, so C is not proof of
              lookahead; each C is listed for reading;
           N  no 8-K in the window mentions it.
Every request goes through the repo's EDGAR client (rate limit, cache, the desk's declared
contact). Writes edgar_dates.json: tickers, dates and classes, all public facts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("sd_explore", HERE / "explore.py")
ex = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ex)
NY = ZoneInfo("America/New_York")
MENTION = re.compile(r"special.{0,60}dividend|dividend.{0,60}special", re.I | re.S)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=20261115)
    a = ap.parse_args(argv)
    from scripts.data.edgar_client import EdgarClient, EdgarNotFound, filing_txt_url
    client = EdgarClient()
    ev, ret, prc, dv, iwm, sessions = ex.load()
    adv = dv.rolling(21, min_periods=10).mean()
    sd = ex.place(ev[ev["distype"] == "SD"], sessions, prc, adv, min_yield=ex.MIN_YIELD)
    sd = sd[sd["ok_wait"] & (sd["x"] - 1 >= sd["d1"] + 2) & (sd["ex_date"] >= "2019-01-01")]
    px = pd.read_parquet(ex.RES / "crsp_specdiv_daily.parquet", columns=["permno", "date", "ticker"])
    px["date"] = pd.to_datetime(px["date"])
    sd = sd.merge(px.rename(columns={"date": "ex_date"}), on=["permno", "ex_date"], how="left")
    tick = client.get_json("https://www.sec.gov/files/company_tickers.json", max_age_s=7 * 86400)
    cik = {v["ticker"].upper(): int(v["cik_str"]) for v in tick.values()}
    sd["cik"] = sd["ticker"].map(cik)
    pool = sd.dropna(subset=["cik"])
    counts = {"wait_events_2019_on": int(len(sd)), "with_a_current_sec_ticker": int(len(pool))}
    pick = pool.sample(n=min(a.n, len(pool)), random_state=a.seed).sort_values("ex_date")
    rows = []
    for r in pick.itertuples():
        decl, d1 = r.declared.date(), sessions[r.d1].date()
        lo, hi = decl - dt.timedelta(days=10), d1 + dt.timedelta(days=7)
        sub = client.get_json(f"https://data.sec.gov/submissions/CIK{int(r.cik):010d}.json", max_age_s=7 * 86400)
        blocks = [sub["filings"]["recent"]]
        for f in sub["filings"].get("files", []):
            if f["filingTo"] >= lo.isoformat() and f["filingFrom"] <= hi.isoformat():
                blocks.append(client.get_json(f"https://data.sec.gov/submissions/{f['name']}", max_age_s=7 * 86400))
        cands = []
        for b in blocks:
            for form, acc, when in zip(b["form"], b["accessionNumber"], b["acceptanceDateTime"]):
                t = dt.datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(NY)
                if form == "8-K" and lo <= t.date() <= hi:
                    cands.append((t, acc))
        first, n_read = None, 0
        for t, acc in sorted(cands):
            try:
                text = client.get_text(filing_txt_url(int(r.cik), acc))
            except EdgarNotFound:
                continue
            n_read += 1
            if MENTION.search(text):
                first = (t, acc)
                break
        close = lambda d: dt.datetime.combine(d, dt.time(16, 0), tzinfo=NY)  # noqa: E731
        cls = "N" if first is None else "A" if first[0] <= close(decl) else "B" if first[0] <= close(d1) else "C"
        rows.append({"ticker": r.ticker, "cik": int(r.cik), "declared_crsp": decl.isoformat(), "d1": d1.isoformat(),
                     "ex_date": r.ex_date.date().isoformat(), "amount": float(r.amount), "eight_ks_in_window": len(cands),
                     "eight_ks_read": n_read, "first_mention_accepted_ny": first[0].isoformat() if first else None,
                     "accession": first[1] if first else None, "class": cls,
                     "calendar_days_mention_minus_declared": (first[0].date() - decl).days if first else None})
        print(f"{r.ticker:6s} declared {decl} D1 {d1} first 8-K mention {first[0].strftime('%Y-%m-%d %H:%M') if first else '-':16s} class {cls}")
    c = pd.Series([x["class"] for x in rows]).value_counts().to_dict()
    lag = pd.Series([x["calendar_days_mention_minus_declared"] for x in rows]).dropna()
    counts.update(sampled=len(rows), classes=c, days_mention_minus_declared=lag.value_counts().sort_index().to_dict(),
                  read_on=dt.date.today().isoformat(), requests=client.n_requests)
    print(json.dumps(counts, indent=1, default=str))
    (HERE / "edgar_dates.json").write_text(json.dumps({"summary": counts, "events": rows}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
