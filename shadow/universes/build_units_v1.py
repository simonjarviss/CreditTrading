"""Build `units_v1.csv`: listed partnership and trust units that pay distributions.

    QUANTT_ENV_FILE=<key file> python3 -m shadow.universes.build_units_v1

WHY: the ex-date fall is as strong in partnership and trust units as in closed-end funds
(results/ideas/2026-11-11_exdate_other_wrappers.md), on CRSP's "units" share type. CRSP rows
are licensed and stay out of the repository, so the live list is rebuilt here from public
sources and never copied from CRSP:
  1. Nasdaq Trader's symbol directory (`nasdaqlisted.txt`, `otherlisted.txt`): every US
     listing with its security name (docs/REFERENCES.md 12sd).
  2. A NAME RULE, fixed before the list was read against any return: the name says units
     of a partnership or trust (`NAME_RULE`), and is not a preferred, a fund, an ETF, a
     warrant, a right, or a unit "consisting of" other securities (a SPAC unit).
  3. Alpaca, read-only: the asset is tradable, and the corporate-actions feed shows at
     least one cash distribution in the last 400 days. A unit that pays nothing has no
     ex-date and would only dilute the long leg.
Each row records whether Alpaca called it shortable and its borrow status ON THE BUILD DATE.
Those change daily: they describe the list, and no book may gate on the stored value.

Re-run to refresh; the file is a snapshot and says its date. Nothing here is typed by hand.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
URL = "https://www.nasdaqtrader.com/dynamic/SymDir/{}.txt"
FILES = {"nasdaqlisted": "Symbol", "otherlisted": "ACT Symbol"}
# The issuer is a partnership ("L.P.", "LP", "Limited Partnership"), or the security is
# called units, or it is a royalty trust (the directory spells one "Royality").
NAME_RULE = re.compile(r"\bunits?\b|limited partner|\bL\.?P\.?(?=[\s,]|$)|royali?ty trust", re.I)
# Not partnership units: preferreds, funds, warrants, rights, notes, SPAC units, the
# convertible "equity units" and "corporate units" companies issue, depositary shares of a
# foreign bank's units, and REITs (their own group in the card, and a weak one).
EXCLUDE = re.compile(r"preferred|\bfund\b|warrant|\brights?\b|consisting of|each unit|\bnotes?\b|\betf\b|\betn\b"
                     r"|equity units?|corporate units|depositary shares|real estate investment trust", re.I)
LOOKBACK_DAYS = 400


def directory() -> list:
    rows = []
    for f, col in FILES.items():
        req = urllib.request.Request(URL.format(f), headers={"User-Agent": "python-urllib"})
        with urllib.request.urlopen(req, timeout=60) as r:          # noqa: S310 (fixed https URL)
            text = r.read().decode("utf-8")
        got = [x for x in csv.DictReader(io.StringIO(text), delimiter="|") if x.get("Security Name")]
        if len(got) < 1000:
            raise RuntimeError(f"{f}: {len(got)} rows; the directory looks truncated")
        rows += [(x[col], x["Security Name"]) for x in got if x.get("Test Issue") != "Y" and x.get("ETF") != "Y"]
    return rows


def candidates(rows: list) -> list:
    return sorted({(s, n) for s, n in rows
                   if NAME_RULE.search(n) and not EXCLUDE.search(n) and re.fullmatch(r"[A-Z]{1,5}", s)})


def main(argv=None) -> int:
    from shadow.sources import ReadOnlyData
    today = dt.date.today()
    cand = candidates(directory())
    data = ReadOnlyData("cef")
    flags = {s: data.asset_flags(s) for s, _ in cand}
    listed = [s for s, _ in cand if flags[s] and flags[s]["tradable"]]
    paid = {e["symbol"] for e in data.distributions(listed, today - dt.timedelta(days=LOOKBACK_DAYS), today)}
    keep = [s for s in listed if s in paid]
    if len(keep) < 20:
        raise RuntimeError(f"only {len(keep)} units survive; refusing to write a universe this thin")
    out = HERE / "units_v1.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "source", "shortable", "borrow_status", "built"])
        for s in keep:
            w.writerow([s, "nasdaqtrader_name_rule", flags[s]["shortable"], flags[s]["borrow_status"] or "", today.isoformat()])
    n_short = sum(1 for s in keep if flags[s]["shortable"])
    n_easy = sum(1 for s in keep if flags[s]["borrow_status"] == "easy_to_borrow")
    print(f"name rule: {len(cand)} | tradable at Alpaca: {len(listed)} | paid a distribution in {LOOKBACK_DAYS} days: {len(keep)} "
          f"| shortable: {n_short} | easy to borrow: {n_easy} | wrote {out.name} ({today})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
