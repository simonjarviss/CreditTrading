"""Read-only Alpaca census for the ssx generator seat's event cards (2026-10-19).

    export QUANTT_ENV_FILE=<abs path to the env file>      # never printed
    python3 scripts/events/ssx/ssx_gen_alpaca.py

WHY THIS EXISTS
---------------
The generator seat (`results/events/ssx/ssx_gen/CARDS_2026-10-19.md`) proposes
event cards whose feasibility turns on whether Alpaca carries a symbol at all,
and whether it can be shorted, today. A flag is true on its read date only
(CLAUDE.md landmine 5), so this script records the read time beside every row.

It asks, BY NAME (a regex is a census tool, not truth; every matched row is
written out so a reader can check it):

* G2   GSE junior preferreds and common (Fannie Mae / Freddie Mac), all OTC.
* G10  closed-end grantor trusts that could convert to ETFs (Grayscale and
       similar), and the ones that already trade on an exchange.
* G9   listed preferreds and baby bonds (the credit catalogue's own regex,
       imported, so the two censuses agree by construction).
* G12  listed single-bond trust certificates (PPLUS, CorTS, SATURNS, STRATS ...).
* a handful of named symbols (hedges and fund-of-CEF ETFs) read one by one.

ZERO TRIALS. No price, return or P&L is read. Only GET /v2/clock and
GET /v2/assets on the paper endpoint, through `quantt.broker.alpaca.AlpacaClient`
(which refuses any other endpoint and scrubs keys from errors). Nothing is
placed, replaced or cancelled.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = REPO / "results" / "events" / "ssx" / "ssx_gen"

GSE_RE = re.compile(r"FEDERAL NATIONAL MORTGAGE|FANNIE MAE|FEDERAL HOME LOAN MORTGAGE|FREDDIE MAC", re.I)
TRUST_RE = re.compile(r"GRAYSCALE|OSPREY|VALKYRIE", re.I)
CERT_RE = re.compile(r"\bPPLUS\b|\bCORTS\b|SATURNS|\bSTRATS\b|TRUST CERTIFICATES|"
                     r"CORPORATE BACKED TRUST|STRUCTURED PRODUCTS CORP|SYNTHETIC FIXED", re.I)
NAMED = ("XMPT", "PCEF", "YYY", "CEFS", "FFLX", "FCT", "BIZD", "PFF", "PGX", "PFFD", "PSK", "PGF",
         "FPE", "HYG", "IWM", "SPY", "KRE", "MUB", "FNMA", "FMCC", "FNMAS", "FMCKJ")


def main() -> int:
    from quantt.broker.alpaca import AlpacaClient, PAPER_BASE
    from scripts.events.ss_credit_catalogue_counts import classify_name
    c = AlpacaClient.from_environment("cef")
    clock = c.clock()
    raw = c._get(PAPER_BASE, "/v2/assets", {"status": "active", "asset_class": "us_equity"})
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("GET /v2/assets returned no list")
    read_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    rows = []
    for a in raw:
        name = a.get("name") or ""
        tags = []
        if GSE_RE.search(name):
            tags.append("gse")
        if TRUST_RE.search(name):
            tags.append("trust")
        if CERT_RE.search(name):
            tags.append("cert")
        k = classify_name(name)
        if k:
            tags.append(k)
        if a["symbol"] in NAMED:
            tags.append("named")
        if not tags:
            continue
        rows.append({"symbol": a["symbol"], "name": name, "tags": ";".join(tags),
                     "exchange": a.get("exchange"), "tradable": bool(a.get("tradable")),
                     "shortable": bool(a.get("shortable")), "easy_to_borrow": a.get("easy_to_borrow"),
                     "fractionable": bool(a.get("fractionable")), "read_at_utc": read_at})
    df = pd.DataFrame(rows).sort_values(["tags", "symbol"])
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "alpaca_census_2026-10-19.csv", index=False)

    def summ(mask):
        g = df[mask]
        return {"n": int(len(g)), "tradable": int(g.tradable.sum()), "shortable": int(g.shortable.sum()),
                "easy_to_borrow": int((g.easy_to_borrow == True).sum()),      # noqa: E712
                "by_exchange": g.exchange.value_counts().to_dict()}
    otc = [a for a in raw if a.get("exchange") == "OTC"]
    out = {"read_at_utc": read_at, "clock_timestamp": str(clock.get("timestamp")),
           "endpoint": "GET /v2/assets?status=active&asset_class=us_equity (paper, cef key)",
           "active_assets": len(raw),
           "otc_active": len(otc), "otc_tradable": sum(bool(a.get("tradable")) for a in otc),
           "gse": summ(df.tags.str.contains("gse")),
           "trust": summ(df.tags.str.contains("trust")),
           "cert": summ(df.tags.str.contains("cert")),
           "preferred": summ(df.tags.str.contains("preferred")),
           "baby_bond": summ(df.tags.str.contains("baby_bond")),
           "named": {r.symbol: {"exchange": r.exchange, "tradable": r.tradable, "shortable": r.shortable,
                                "easy_to_borrow": r.easy_to_borrow}
                     for r in df[df.tags.str.contains("named")].itertuples()},
           "named_absent_from_active_list": sorted(set(NAMED) - set(df.symbol))}
    (OUT / "alpaca_census_2026-10-19.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
