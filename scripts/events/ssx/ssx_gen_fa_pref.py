"""Fallen-angel issuers that have exchange-listed preferreds or baby bonds today (ssx card G9).

    python3 scripts/events/ssx/ssx_gen_fa_pref.py      # local files only, no network

WHY. Card G9 asks whether the S3 forced-flow mechanism (WATCH: IG->HY index
exits are real and reverse; it died only in its ETF WRAPPER, D4) has a listed,
non-wrapper expression the desk can reach: the $25-par preferreds and baby bonds
of issuers whose bonds fall from IG to HY. This counts the issuers that had a
TRACE grade-flag flip I->H in the LEGACY panel (`data/forced_flow2/m6_events.parquet`,
last event 2025-10-31; TRACE's own flag, not the index rule) AND have a listed
preferred or baby bond at Alpaca today (`alpaca_census_2026-10-19.csv`, this seat's
read-only census). Matching is by issuer ticker: the part before "." for NYSE-style
symbols, otherwise the symbol minus a one- or two-letter suffix. A census tool,
not truth: every match is written out.

SURVIVORSHIP: only issues listed TODAY can match, so a downgraded issuer whose
preferreds were called or delisted is missed. The count is therefore a floor on
the historical event set, not an estimate of it.

ZERO TRIALS: no price or return is read.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "results" / "events" / "ssx" / "ssx_gen"


def main() -> int:
    m = pd.read_parquet(REPO / "data/forced_flow2/m6_events.parquet",
                        columns=["issuer6", "issuer_nm", "company_symbol", "event_date", "flip_month"])
    m = m.dropna(subset=["company_symbol"])
    m["event_date"] = pd.to_datetime(m.event_date)
    syms = set(m.company_symbol.astype(str).str.upper())
    a = pd.read_csv(OUT / "alpaca_census_2026-10-19.csv")
    a = a[a.tags.str.contains("preferred|baby_bond")]
    rows = []
    for r in a.itertuples():
        s = r.symbol.upper()
        cands = [s.split(".")[0]] if "." in s else [s[:-1], s[:-2]]
        hit = next((c for c in cands if c and c in syms), None)
        if hit:
            rows.append({"symbol": r.symbol, "issuer_ticker": hit, "name": r.name, "tags": r.tags,
                         "shortable": r.shortable})
    x = pd.DataFrame(rows)
    x.to_csv(OUT / "fa_pref_matches_2026-10-19.csv", index=False)
    mm = m[m.company_symbol.str.upper().isin(set(x.issuer_ticker))]
    im = mm.groupby(["company_symbol", "flip_month"]).size().reset_index()
    im["year"] = im.flip_month.astype(str).str[:4].astype(int)
    out = {"m6_last_event": str(m.event_date.max().date()),
           "alpaca_listed_pref_or_baby_bond_issues": int(len(a)),
           "issues_whose_issuer_had_an_I_to_H_flip": int(len(x)),
           "distinct_issuers": int(x.issuer_ticker.nunique()),
           "issuer_flip_months_2010_2025": int(im[im.year.between(2010, 2025)].shape[0]),
           "issuer_flip_months_by_year": im.groupby("year").size().to_dict(),
           "matched_issues_shortable_today": int(x.shortable.sum())}
    (OUT / "fa_pref_counts_2026-10-19.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))
    print(x.groupby("issuer_ticker").symbol.apply(lambda s: ",".join(s)).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
