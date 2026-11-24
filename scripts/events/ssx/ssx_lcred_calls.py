"""C6 (and C4 sample): first optional-redemption / float dates read from each issue's own prospectus.

    export QUANTT_ENV_FILE=<absolute path to the env file>        # SEC contact, never printed
    python3 scripts/events/ssx/ssx_lcred_calls.py c6               # the shortable issues above par today
    python3 scripts/events/ssx/ssx_lcred_calls.py c4 --n 30        # a sample of name-tagged fixed-to-float/reset issues

WHY
---
C6's superset (shortable today AND last close above $25 par; `ssx_lcred_snapshot.py`)
must be cut to issues whose call date is inside 12 months (or already passed).
C4 needs float/reset dates. Neither is in Alpaca's data, and the listed name
rarely states them. The issue's own 424B prospectus does ("on or after
<date>", "from and including <date> ... floating rate"). This script locates
it from public EDGAR filings only:

  1. the issuer's 8-A12B filings (from its submissions JSON) -- each names the
     class it registers; the one whose title carries the issue's coupon (or
     series letter) is the issue's listing registration;
  2. the nearest 424B2/424B5 filed in the 45 days before that 8-A12B is the
     final prospectus;
  3. sentences with "redeem"/"redemption" + a date, and "floating"/"reset" + a
     date, are extracted for reading. The extracted date is the earliest date
     in the first matching sentence; the sentence is written out so a reader
     can check it.
An issue whose 8-A12B or 424B cannot be found is reported as not found, never
guessed. Licensed data are not used here.
ZERO TRIALS.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx.ssx_lcred_common import CACHE, OUT, EdgarBudget, write_json
from scripts.data.edgar_client import filing_txt_url

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_RE = re.compile(rf"({MONTHS})\s+\d{{1,2}},\s+(19|20)\d{{2}}")
REDEEM_RE = re.compile(rf"[^.]{{0,300}}\b(redeem|redemption)\b[^.]{{0,300}}?({MONTHS})\s+\d{{1,2}},\s+(19|20)\d{{2}}[^.]{{0,200}}", re.I)
FLOAT_RE = re.compile(rf"[^.]{{0,300}}\b(floating rate|reset date|first reset|reset period)\b[^.]{{0,300}}?({MONTHS})\s+\d{{1,2}},\s+(19|20)\d{{2}}[^.]{{0,200}}", re.I)


def _clean(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&#\d+;|&nbsp;|&amp;|&ldquo;|&rdquo;|&thinsp;|&#8217;", " ", t)
    return re.sub(r"\s+", " ", t)


def _first_date(s: str):
    m = DATE_RE.search(s)
    return dt.datetime.strptime(re.sub(r"\s+", " ", m.group(0)), "%B %d, %Y").date() if m else None


def locate(eb, fil: pd.DataFrame, cik: int, coupon: str | None, series: str | None, near: dt.date | None):
    a8 = fil[(fil.cik == cik) & (fil.form == "8-A12B")].sort_values("filingDate")
    # at most four 8-A12B reads per issue: the two nearest the first bar when it is known;
    # if the issue has no pre-2023 bar it listed in 2023 or later; if its first bar is the
    # data start (2016-01-04) it listed before 2016.
    if near is not None and near > dt.date(2016, 1, 6):
        a8 = a8.iloc[(pd.to_datetime(a8.filingDate) - pd.Timestamp(near)).abs().argsort()[:2]]
    elif near is None:
        a8 = a8[a8.filingDate >= dt.date(2023, 1, 1)].tail(4)
    else:
        a8 = a8[a8.filingDate <= dt.date(2016, 1, 31)].tail(4)
    found = None
    for r in a8.itertuples():
        txt = _clean(eb.text(filing_txt_url(cik, r.accessionNumber)))
        i = txt.upper().find("TITLE OF EACH CLASS")
        seg = txt[i:i + 1200] if i >= 0 else txt[:5000]
        ok_c = coupon is None or coupon in seg
        ok_s = series is None or re.search(rf"Series {series}\b", seg, re.I)
        if ok_c and ok_s:
            found = (r.accessionNumber, r.filingDate, seg[:200])
            break
    if not found:
        return None
    a8_date = found[1]
    b = fil[(fil.cik == cik) & fil.form.isin(["424B2", "424B5"])].copy()
    b["gap"] = (pd.to_datetime(a8_date) - pd.to_datetime(b.filingDate)).dt.days
    b = b[(b.gap >= 0) & (b.gap <= 45)].sort_values("gap")
    for r in b.head(3).itertuples():
        t = _clean(eb.text(filing_txt_url(cik, r.accessionNumber)))
        if coupon is None or coupon in t[:40000]:
            return {"a8": found[0], "a8_date": str(a8_date), "b": r.accessionNumber, "b_date": str(r.filingDate),
                    "text": t}
    return {"a8": found[0], "a8_date": str(a8_date), "b": None, "b_date": None, "text": None}


def _coupon_series(name: str):
    c = re.search(r"(\d{1,2}\.\d{2,3})\s*%", name)
    s = re.search(r"Series\s+([A-Z]{1,2})\b", name)
    return (c.group(1) if c else None), (s.group(1) if s else None)


def run(symbols: list[str], label: str) -> pd.DataFrame:
    cen = pd.read_csv(OUT / "census_2026-10-19.csv")
    vol = pd.read_csv(OUT / "volume_per_symbol_2016_2022.csv", parse_dates=["first_bar"])
    fil = pd.read_parquet(CACHE / "issuer_filings.parquet")
    fil["filingDate"] = pd.to_datetime(fil.filingDate).dt.date
    eb = EdgarBudget(offline=False)
    rows = []
    for sym in symbols:
        r = cen[cen.symbol == sym].iloc[0]
        coupon, series = _coupon_series(r["name"])
        fb = vol.loc[vol.symbol == sym, "first_bar"]
        near = fb.iloc[0].date() if len(fb) else None
        rec = {"symbol": sym, "coupon": coupon, "series": series, "first_bar": near}
        if pd.isna(r.cik):
            rec["status"] = "no CIK"
            rows.append(rec)
            continue
        try:
            loc = locate(eb, fil, int(r.cik), coupon, series, near)
        except RuntimeError as e:
            rec["status"] = str(e)[:80]
            rows.append(rec)
            break
        if loc is None:
            rec["status"] = "8-A12B not found"
        elif loc["text"] is None:
            rec.update({"status": "424B not found", "a8": loc["a8"], "a8_date": loc["a8_date"]})
        else:
            t = loc["text"]
            m1 = REDEEM_RE.search(t)
            m2 = FLOAT_RE.search(t)
            rec.update({"status": "ok", "a8": loc["a8"], "a8_date": loc["a8_date"], "prospectus": loc["b"],
                        "prospectus_date": loc["b_date"],
                        "first_redeem_date": _first_date(m1.group(0)[m1.start(1) - m1.start(0):]) if m1 else None,
                        "redeem_sentence": m1.group(0)[:400] if m1 else None,
                        "float_date": _first_date(m2.group(0)[m2.start(1) - m2.start(0):]) if m2 else None,
                        "float_sentence": m2.group(0)[:400] if m2 else None})
        rows.append(rec)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"{label}_prospectus_dates.csv", index=False)
    print(f"live EDGAR requests {eb.live}")
    return df


def cmd_c6(args) -> None:
    snap = json.loads((OUT / "c6_summary.json").read_text())
    syms = [s[0] for s in snap["shortable_above_par_symbols"]]
    df = run(syms, "c6")
    today = dt.date(2026, 10, 19)
    df["call_within_12m"] = df.first_redeem_date.map(
        lambda d: None if pd.isna(d) else (pd.Timestamp(d).date() <= today + dt.timedelta(days=365)))
    out = {"superset_shortable_above_25": len(syms), "prospectus_found": int((df.status == "ok").sum()),
           "call_date_within_12m_or_passed": int((df.call_within_12m == True).sum()),
           "call_date_beyond_12m": int((df.call_within_12m == False).sum()),
           "call_date_not_established": int(df.call_within_12m.isna().sum()),
           "rows": df[["symbol", "status", "first_redeem_date", "call_within_12m", "prospectus"]].astype(str).values.tolist()}
    write_json(OUT / "c6_calls_summary.json", out)
    print(json.dumps(out, indent=1, default=str))


def cmd_c4(args) -> None:
    """Two seeded samples: (a) name-tagged fixed-to-float/reset issues, for their float or
    reset dates; (b) untagged fixed-looking preferreds, for the tag's RECALL (how many
    floaters the name misses). Sentences are written out for reading."""
    cen = pd.read_csv(OUT / "census_2026-10-19.csv")
    base = cen[cen.tradable & (cen.exchange != "OTC")]
    tagged = base[base.name_fixed_to_float | base.name_reset]
    untagged = base[(base.kind == "preferred") & ~(base.name_fixed_to_float | base.name_reset | base.name_floating)]
    rng = random.Random(20261019)
    t, u = sorted(tagged.symbol), sorted(untagged.symbol)
    rng.shuffle(t)
    rng.shuffle(u)
    a = run(t[: args.n], "c4_tagged")
    b = run(u[: args.m], "c4_untagged")
    print(a[["symbol", "status", "first_redeem_date", "float_date"]].to_string())
    print(b[["symbol", "status", "first_redeem_date", "float_date"]].to_string())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("c6")
    c = sp.add_parser("c4")
    c.add_argument("--n", type=int, default=20)
    c.add_argument("--m", type=int, default=15)
    a = ap.parse_args(argv)
    {"c6": cmd_c6, "c4": cmd_c4}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
