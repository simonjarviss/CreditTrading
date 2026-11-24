"""Offline EDGAR counts for the ssx generator seat's cards (2026-10-19). No network.

    python3 scripts/events/ssx/ssx_gen_edgar.py --edgar-cache <worktree>/results/events/_cache_edgar

WHY THIS EXISTS
---------------
Two cards in `results/events/ssx/ssx_gen/CARDS_2026-10-19.md` need an event count
before they can be ranked:

* **G8, BDC consolidation.** A non-traded BDC merged into its listed sibling hands
  long-locked holders a listed share on a known closing date, the merger-route
  twin of a non-traded listing (A4). How many such mergers were there? The unit is
  the acquirer's N-14 episode; targets are other BDCs that share an accession
  number with the acquirer's merger filings (one filing is indexed under every
  party); a target is "listed" if it ever filed an 8-A12B or a 25-NSE, or
  has an exchange ticker in SEC's file today. That is an approximation and the
  per-episode table is written out so a reader can check every row.
* **G10, closed-end grantor-trust conversions.** Grayscale-style trusts that
  file 10-Ks; their 8-A12B (exchange registration) dates the conversion to an ETF.

BDC set: a CIK that filed a BDC election form (N-54A, N-54C, N-6F) in the
window, OR filed an N-2 family form AND a 10-K/10-Q (closed-end funds file
N-CSR, not 10-K; BDCs file both N-2 and 10-K). Pre-2008 elections are not in the
indexes, which the second rule covers for any BDC that registered an offering
since 2008.

ZERO TRIALS: filings are counted, nothing is priced. Reads the quarterly
`master.gz` indexes through `scripts/data/edgar_client.py` with offline=True,
which raises on a cache miss rather than fetching. 2026 quarters are read to the
cache's copy (the open quarter is partial) and labelled; per-year means use
2010-2025 only.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.data.edgar_client import EdgarClient                    # noqa: E402
from scripts.data.fetch_edgar_events import INDEX_URL, parse_master_index, quarters   # noqa: E402

OUT = REPO / "results" / "events" / "ssx" / "ssx_gen"
N14 = {"N-14", "N-14/A", "N-14 8C", "N-14 8C/A"}
MERGER_COMM = {"425", "DEFM14A", "PREM14A"}
ELECT = {"N-54A", "N-54A/A", "N-54C", "N-54C/A", "N-6F", "N-6F/A"}
N2 = {"N-2", "N-2/A", "N-2ASR", "N-2 POSASR", "N-2MEF"}
PERIODIC = {"10-K", "10-Q"}
LISTING = {"8-A12B", "25-NSE"}
KEEP = N14 | MERGER_COMM | ELECT | N2 | PERIODIC | LISTING | {"10-12G"}
GAP_DAYS = 180


def load(cache: Path, end: date) -> pd.DataFrame:
    c = EdgarClient(offline=True, cache=cache)
    parts = []
    for y, q in quarters(date(2008, 1, 1), end):
        txt = c.get_text(INDEX_URL.format(y=y, q=q))
        parts.append(parse_master_index(txt, f"{y}Q{q}", keep_forms=KEEP))
    return pd.concat(parts, ignore_index=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edgar-cache", type=Path, required=True)
    ap.add_argument("--end", default="2026-09-30")
    a = ap.parse_args(argv)
    idx = load(a.edgar_cache, date.fromisoformat(a.end))
    tick = json.loads((REPO / "results/events/_cache_edgar/www.sec.gov/files/company_tickers_exchange.json").read_text())
    tick = pd.DataFrame(tick["data"], columns=tick["fields"])
    has_ticker = set(tick.loc[tick.exchange.notna(), "cik"].astype(int))

    forms_by_cik = idx.groupby("cik")["form"].agg(set)
    bdc = {c for c, fs in forms_by_cik.items() if (fs & ELECT) or ((fs & N2) and (fs & PERIODIC))}
    listed = {c for c, fs in forms_by_cik.items() if fs & LISTING} | has_ticker
    name = idx.sort_values("date_filed").groupby("cik")["company"].last()

    # --- G8: BDC acquirer N-14 episodes and their BDC targets
    n = idx[idx.form.isin(N14) & idx.cik.isin(bdc)].sort_values(["cik", "date_filed"])
    eps = []
    for cik, g in n.groupby("cik"):
        start = prev = None
        for d in g.date_filed:
            if prev is None or (d - prev).days > GAP_DAYS:
                if start is not None:
                    eps.append((cik, start, prev))
                start = d
            prev = d
        eps.append((cik, start, prev))
    # A target is paired by ACCESSION, not by date: one 425 or N-14 is indexed under
    # every entity on it (filer and subject), so a BDC that shares an accession with
    # the acquirer's merger filings is a party to that deal. A date window alone
    # paired unrelated BDCs that happened to file 425s in the same months.
    mf = idx[idx.form.isin(MERGER_COMM | N14)]
    rows = []
    for cik, first, last in eps:
        own = mf[(mf.cik == cik) & (mf.date_filed >= first - pd.Timedelta(days=GAP_DAYS)) &
                 (mf.date_filed <= last + pd.Timedelta(days=GAP_DAYS))]
        w = mf[mf.accession.isin(set(own.accession)) & (mf.cik != cik) & mf.cik.isin(bdc)]
        tg = sorted(set(w.cik))
        rows.append({"acquirer_cik": cik, "acquirer": name[cik], "first_n14": first.date(), "last_n14": last.date(),
                     "acquirer_listed": cik in listed, "n_bdc_targets": len(tg),
                     "targets": "; ".join(f"{name[t]} ({t}, {'listed' if t in listed else 'unlisted'})" for t in tg),
                     "n_unlisted_targets": sum(t not in listed for t in tg)})
    e = pd.DataFrame(rows).sort_values("first_n14")
    e.to_csv(OUT / "edgar_bdc_n14_episodes.csv", index=False)
    e["year"] = pd.to_datetime(e.first_n14).dt.year
    lu = e[e.acquirer_listed & (e.n_unlisted_targets > 0)]

    # --- G10: Grayscale-style trusts
    gr = idx[idx.company.str.contains("GRAYSCALE", case=False)]
    trusts = gr[gr.form.isin(PERIODIC)].cik.unique()
    lst = gr[gr.form == "8-A12B"].groupby("cik").date_filed.min()
    t_rows = [{"cik": c, "name": name[c], "first_8a12b": (lst[c].date() if c in lst.index else None)} for c in trusts]
    t = pd.DataFrame(t_rows).sort_values("first_8a12b", na_position="last")
    t.to_csv(OUT / "edgar_grayscale_trusts.csv", index=False)

    yrs = range(2010, 2026)
    out = {"index_window": f"2008Q1..{a.end} (offline cache; 2026 quarters partial)",
           "bdc_set": {"n_ciks": len(bdc), "listed_proxy": len(bdc & listed)},
           "bdc_n14_episodes": {"all": int(len(e)),
                                "by_year": e.groupby("year").size().reindex(range(2008, 2027), fill_value=0).to_dict(),
                                "mean_2010_2025": round(float(e[e.year.between(2010, 2025)].shape[0] / len(yrs)), 2),
                                "listed_acquirer_with_unlisted_bdc_target": int(len(lu)),
                                "listed_acq_unlisted_target_by_year": lu.groupby("year").size().to_dict()},
           "grayscale_trusts_filing_10k_10q": int(len(t)),
           "grayscale_with_8a12b": int(t.first_8a12b.notna().sum()),
           "grayscale_8a12b_by_year": pd.to_datetime(t.first_8a12b.dropna()).dt.year.value_counts().sort_index().to_dict()}
    (OUT / "edgar_counts_2026-10-19.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
