"""Crawl EDGAR form 487 (unit investment trust prospectuses) for closed-end-fund series.

    QUANTT_ENV_FILE=<env> python3 results/ideas/uit_cef_flows/crawl.py index     # form indexes 2012Q1..2025Q4
    QUANTT_ENV_FILE=<env> python3 results/ideas/uit_cef_flows/crawl.py filings   # the capped set (see do_filings); `filings all` for every 487
    QUANTT_ENV_FILE=<env> python3 results/ideas/uit_cef_flows/crawl.py sizes     # 24F-2NT of the CEF series

WHY A SEPARATE CACHE DIRECTORY. Every request goes through scripts/data/edgar_client.py
(its contact header, rate limit and back-off). The client is given a cache directory under
~/quantt_research/uit_cef_flows/edgar_cache instead of the repository's, because the laptop
had 1.2 GB of free disk on 2026-11-16 and 9,000 prospectuses of 200-350 kB each do not fit.
So this script keeps what it needs and frees the rest:
  * a quarterly form index is reduced to its 487 and 24F-2NT rows (idx.csv) and deleted;
  * a 487 that is not a closed-end-fund candidate is deleted after one line about it is
    written to filings.jsonl (accession, trust name, count of "closed-end" in the text);
  * a candidate is kept, gzip-compressed in place (the client reads a gzip body as text).
CANDIDATE RULE (liberal; the strict rule is in parse.py): "closed-end" appears 15 or more
times in the main document. A plain equity series has 0 to a few; a series that holds some
funds among shares has about 30; a closed-end series has 50 to 200.

SPONSORS KEPT: First Trust ("FT <n>") and Guggenheim Defined Portfolios (before 2010 named
Claymore Securities Defined Portfolios). They are the two largest filers of form 487 and both
print a ticker beside every holding. Invesco, SmartTrust and Advisors Disciplined Trust are
counted in the index only (Invesco prints fund names without tickers).
EDGAR is public; nothing here is licensed. It refuses to run with under 400 MB free.
"""
from __future__ import annotations

import gzip, json, re, shutil, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.data.edgar_client import EdgarClient, cache_path  # noqa: E402

OUT = Path.home() / "quantt_research" / "uit_cef_flows"
CACHE = OUT / "edgar_cache"
IDX, LOG = OUT / "idx.csv", OUT / "filings.jsonl"
QUARTERS = [(y, q) for y in range(2012, 2026) for q in (1, 2, 3, 4)]
SPONSOR = (("FT", re.compile(r"^FT \d+$")),
           ("GUGG", re.compile(r"^(GUGGENHEIM|CLAYMORE SECURITIES) DEFINED PORTFOLIOS,? SERIES \d+$", re.I)),
           ("INVESCO", re.compile(r"^(INVESCO|VAN KAMPEN) UNIT TRUSTS", re.I)),
           ("SMART", re.compile(r"^SMART ?TRUST", re.I)),
           ("ADT", re.compile(r"^ADVISORS DISCIPLINED TRUST", re.I)))
CRAWLED = ("FT", "GUGG")
MIN_MENTIONS = 15


def free_mb() -> float:
    return shutil.disk_usage(OUT).free / 1e6


def sponsor(name: str) -> str | None:
    for k, rx in SPONSOR:
        if rx.match(name.strip()):
            return k
    return None


def do_index(c: EdgarClient) -> None:
    done = set()
    if IDX.exists():
        done = {tuple(ln.split("|")[:2]) for ln in IDX.read_text().splitlines()[1:]}
    else:
        IDX.write_text("year|qtr|form|sponsor|name|cik|filed|path\n")
    for y, q in QUARTERS:
        if (str(y), str(q)) in done:
            continue
        url = f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.gz"
        txt = c.get_text(url)
        n = 0
        with IDX.open("a") as f:
            for ln in txt.splitlines():
                m = re.match(r"^(487|24F-2NT(?:/A)?)\s+(.+?)\s+(\d+)\s+(\d{4}-\d\d-\d\d)\s+(edgar/\S+)\s*$", ln)
                if not m:
                    continue
                sp = sponsor(m.group(2))
                if sp is None and m.group(1) != "487":
                    continue
                f.write(f"{y}|{q}|{m.group(1)}|{sp or 'OTHER'}|{m.group(2).replace('|', ' ')}|{m.group(3)}|{m.group(4)}|{m.group(5)}\n")
                n += 1
        cache_path(url, CACHE).unlink()
        print(y, q, n, flush=True)


def main_doc(txt: str) -> str:
    """The first <DOCUMENT> of a complete submission: the prospectus itself."""
    a = txt.find("<DOCUMENT>")
    b = txt.find("</DOCUMENT>", a)
    if a < 0 or b < 0:
        raise ValueError("no <DOCUMENT> block")
    return txt[a:b]


def do_filings(c: EdgarClient, limit: int | None) -> None:
    rows = [ln.split("|") for ln in IDX.read_text().splitlines()[1:]]
    rows = [r for r in rows if r[2] == "487" and r[3] in CRAWLED]
    done = set()
    if LOG.exists():
        done = {json.loads(ln)["path"] for ln in LOG.read_text().splitlines()}
    # CAP ON THE CRAWL (added 2026-11-18, after the interruption; decided before any return was read).
    # A prospectus took 1.45 s to arrive (measured on the first 200), so all 9,398 would take 3.8 hours.
    # Order: (0) every Guggenheim filing; (1) every THIRD First Trust filing in (filing date, path)
    # order, all years: a systematic one-in-three sample, which is what the event study uses;
    # (2) every other First Trust filing from 2024-11-01, so that the calendar of terminations
    # for the 12 months after 2026-11-18 is complete for 24-month trusts. Anything else is
    # fetched only if `filings all` is asked for. explore.py reads `ft_sample` to keep to (0)+(1).
    ft = sorted((r for r in rows if r[3] == "FT"), key=lambda r: (r[6], r[7]))
    third = {r[7] for i, r in enumerate(ft) if i % 3 == 0}
    def tier(r):
        if r[3] == "GUGG":
            return 0
        if r[7] in third:
            return 1
        return 2 if r[6] >= "2024-11-01" else 3
    todo = [r for r in rows if r[7] not in done and (limit == -1 or tier(r) < 3)]
    todo.sort(key=lambda r: (tier(r), r[6], r[7]))
    limit = None if limit == -1 else limit
    print(len(rows), "filings of", CRAWLED, "|", len(todo), "to fetch", flush=True)
    t0 = time.time()
    for i, r in enumerate(todo[:limit]):
        if free_mb() < 400:
            raise SystemExit(f"stopping: {free_mb():.0f} MB free")
        url = "https://www.sec.gov/Archives/" + r[7]
        doc = main_doc(c.get_text(url))
        n = len(re.findall(r"closed-end", doc, re.I))
        keep = n >= MIN_MENTIONS
        p = cache_path(url, CACHE)
        if keep:
            p.write_bytes(gzip.compress(doc.encode("latin-1"), 6))   # main document only
        else:
            p.unlink()
        with LOG.open("a") as f:
            f.write(json.dumps({"path": r[7], "sponsor": r[3], "name": r[4], "cik": r[5], "filed": r[6],
                                "closed_end_mentions": n, "kept": keep, "bytes": len(doc)}) + "\n")
        if i % 200 == 0:
            print(i, r[6], r[4], n, f"{time.time() - t0:.0f}s free {free_mb():.0f}MB", flush=True)
    (OUT / "ft_sample.json").write_text(json.dumps(sorted(third)))


def do_sizes(c: EdgarClient) -> None:
    """24F-2NT (annual notice of securities sold) of every registrant with a kept 487."""
    kept = {json.loads(ln)["cik"] for ln in LOG.read_text().splitlines() if json.loads(ln)["kept"]}
    rows = [ln.split("|") for ln in IDX.read_text().splitlines()[1:]]
    rows = [r for r in rows if r[2].startswith("24F-2NT") and r[5] in kept]
    print(len(rows), "24F-2NT filings of", len(kept), "candidate registrants", flush=True)
    for i, r in enumerate(rows):
        if free_mb() < 400:
            raise SystemExit(f"stopping: {free_mb():.0f} MB free")
        url = "https://www.sec.gov/Archives/" + r[7]
        p = cache_path(url, CACHE)
        if p.exists():
            continue
        txt = c.get_text(url)
        p.write_bytes(gzip.compress(txt.encode("latin-1"), 6))
        if i % 200 == 0:
            print(i, r[6], r[4], flush=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    client = EdgarClient(cache=CACHE)
    what = sys.argv[1]
    if what == "index":
        do_index(client)
    elif what == "filings":
        do_filings(client, (-1 if sys.argv[2] == "all" else int(sys.argv[2])) if len(sys.argv) > 2 else None)
    elif what == "sizes":
        do_sizes(client)
    else:
        raise SystemExit("index | filings [n] | sizes")
    print("requests", client.n_requests, "cache hits", client.n_cache_hits)
