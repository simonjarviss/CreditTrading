"""Can a book's Alpaca paper account see bonds? One read-only GET per bond asset class.

    QUANTT_ENV_FILE=/abs/path/config/.env python3 scripts/ops/alpaca_bond_assets.py [--book cef]

WHY (RESEARCH_PLAN_2026-10-09 item 0.11). The 2026-10-09 ruling put cash bonds
in bounds. Whether the paper account the book trades in can list a Treasury or
a corporate bond is a measurement, not a reading of the docs. The `AssetClass`
enum of `GET /v2/assets` lists `treasury` and `corporate` [V: reference, fetched
2026-10-11], but Alpaca's Fixed Income guide sells bonds to Broker API partners.

WHAT IT DOES. `GET https://paper-api.alpaca.markets/v2/assets?asset_class=<c>`
for c in (treasury, corporate), with no other parameter, through
`AlpacaClient`'s own HTTP session, so the keys stay in its headers and an error
body is scrubbed. It prints the UTC time, the HTTP status, the row count, the
counts by class/status/tradable, and up to five example symbols. Unlike
`AlpacaClient._get` it does NOT raise on a non-200: the status code is the
finding. Nothing about the account is read or printed -- no number, no ID, no
key (this repository is public).
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

ASSET_CLASSES = ("treasury", "corporate")


def read(client, asset_class: str) -> dict:
    from quantt.broker.alpaca import PAPER_BASE, TIMEOUT_S
    t0 = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = client._session.get(PAPER_BASE + "/v2/assets", params={"asset_class": asset_class},
                            timeout=TIMEOUT_S, allow_redirects=False)   # key headers: never follow a 3xx
    rec = {"asset_class": asset_class, "utc": t0, "status": r.status_code}
    try:
        body = r.json()
    except ValueError:
        rec["body"] = client._scrub(r.text[:300])
        return rec
    if not isinstance(body, list):
        rec["body"] = client._scrub(json.dumps(body)[:300])
        return rec
    rec["rows"] = len(body)
    for f in ("class", "status", "tradable"):
        rec[f"by_{f}"] = dict(collections.Counter(str(a.get(f)) for a in body))
    rec["examples"] = [{k: a.get(k) for k in ("symbol", "name", "class", "exchange", "tradable")}
                       for a in body[:5]]
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default="cef")
    book = ap.parse_args(argv).book
    from quantt.broker.alpaca import AlpacaClient
    client = AlpacaClient.from_environment(book)
    for c in ASSET_CLASSES:
        print(json.dumps({"book": book, **read(client, c)}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
