"""Fetch Wayback Machine captures of fund-of-CEF ETF holdings pages (public archive).

WHY: the three ETFs (YYY, PCEF, XMPT) are not in data/holdings/nport_holdings.parquet
(it holds HYG, JNK, LQD only), EDGAR is off limits in this screen, and Nasdaq GIW
shows historical YLDA weights only to subscribers. The issuer holdings pages archived
by the Wayback Machine are the only credential-free history left, so this script
lists (CDX) and downloads (id_ raw mode) every capture of the pages named below.

Writes only under raw/wayback/ in this folder; appends one row per request to
raw/fetch_log.csv (file, url, http status, UTC fetch time, bytes). Never touches data/.
Usage: python3 -I fetch_wayback.py <cdx-url-pattern> <prefix> [from_year] [to_year]
"""
from __future__ import annotations

import csv
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw" / "wayback"
SNAPS = RAW / "snaps"
LOG = HERE / "raw" / "fetch_log.csv"
UA = "Mozilla/5.0 (research screen; contact via repo owner)"


def _get(url: str, timeout: int = 120) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:  # a real status: report it, do not retry 4xx
            if e.code < 500:
                return e.code, b""
            last = e
        except Exception as e:  # network error: back off and retry, then raise
            last = e
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"giving up on {url}: {last!r}")


def _log(fname: str, url: str, status: int, n: int) -> None:
    new = not LOG.exists()
    with LOG.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["file", "url", "status", "fetched_utc", "bytes"])
        w.writerow([fname, url, status, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), n])


def fetch_rows(rows: list[list[str]], prefix: str) -> None:
    SNAPS.mkdir(parents=True, exist_ok=True)
    for ts, orig, *_ in rows:
        out = SNAPS / f"{prefix}_{ts}.bin"
        if out.exists() and out.stat().st_size > 0:
            continue
        url = f"https://web.archive.org/web/{ts}id_/{orig}"
        st, b = _get(url)
        out.write_bytes(b)
        _log(out.name, url, st, len(b))
        print(f"  {ts} {st} {len(b)} {orig}")
        time.sleep(1.5)


def main() -> None:
    if sys.argv[1] == "--rows":  # --rows <cdx file> <regex on the original url> <prefix>
        rx = re.compile(sys.argv[3])
        rows = [ln.split() for ln in Path(sys.argv[2]).read_text().splitlines() if ln.strip()]
        rows = [r for r in rows if rx.search(r[1])]
        print(f"{len(rows)} rows match")
        fetch_rows(rows, sys.argv[4])
        return
    pattern, prefix = sys.argv[1], sys.argv[2]
    y0 = sys.argv[3] if len(sys.argv) > 3 else "2010"
    y1 = sys.argv[4] if len(sys.argv) > 4 else "2023"
    q = urllib.parse.urlencode({"url": pattern, "from": y0, "to": y1, "filter": "statuscode:200",
                                "fl": "timestamp,original,mimetype,length,digest", "collapse": "digest"})
    cdx_url = f"https://web.archive.org/cdx/search/cdx?{q}"
    st, body = _get(cdx_url, timeout=300)
    if st != 200:
        raise RuntimeError(f"CDX returned {st} for {pattern}")
    rows = [ln.split() for ln in body.decode().splitlines() if ln.strip()]
    (RAW / f"cdx_{prefix}.txt").write_text(body.decode())
    _log(f"cdx_{prefix}.txt", cdx_url, st, len(body))
    print(f"{pattern}: {len(rows)} captures")
    fetch_rows(rows, prefix)


if __name__ == "__main__":
    main()
