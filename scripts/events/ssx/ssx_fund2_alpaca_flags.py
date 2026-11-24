"""Today's Alpaca flags on the BDCs behind A4 and A9 (read-only GETs; flags are true on the read date only).

    export QUANTT_ENV_FILE=/abs/path/config/.env     # Alpaca cef key; never printed
    python3 scripts/events/ssx/ssx_fund2_alpaca_flags.py

WHY: both BDC ideas need a short (A4: the released name around a lock-up date;
A9: the name the tracker must buy or sell). A short that cannot be borrowed is
not a trade (CLAUDE.md landmine 5: `borrow_status` changes daily). The symbol
list is BIZD's last CRSP MF holdings snapshot (tickers as CRSP records them)
plus the A4 listings still trading, plus the BDC trackers themselves. One
`GET /v2/assets/{symbol}` each, through `quantt/broker/alpaca.py`'s read
method; no order, cancel, watchlist or account call.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.events.ssx.ssx_fund2_common import OUT, CACHE, now_utc  # noqa: E402

A4_LIVE = ["TSLX", "FSK", "CGBD", "BCSF", "OBDC", "CCAP", "TRIN", "CION", "RWAY", "BXSL", "PSBD", "MSDL",
           "NCDL", "KBDC", "MSIF", "OTF", "FSSL"]
TRACKERS = ["BIZD", "BDCZ", "BDCX", "PBDC", "VPC", "FBDC", "HBDC"]


def main() -> int:
    from quantt.broker.alpaca import AlpacaClient, AssetNotFound
    h = pd.read_parquet(CACHE / "bizd_crsp_mf_holdings.parquet")
    h["report_dt"] = pd.to_datetime(h["report_dt"])
    last = h[h["report_dt"] == h["report_dt"].max()]
    bizd_now = sorted({str(t) for t in last["ticker"].dropna() if str(t).isalpha()})
    syms = sorted(set(bizd_now) | set(A4_LIVE) | set(TRACKERS))
    c = AlpacaClient.from_environment("cef")
    clock = c.clock()
    rows = []
    for s in syms:
        try:
            a = c.asset(s)
            rows.append({"symbol": s, "found": True, "exchange": a.get("exchange"), "tradable": a.get("tradable"),
                         "shortable": a.get("shortable"), "easy_to_borrow": a.get("easy_to_borrow"),
                         "borrow_status": a.get("borrow_status")})
        except AssetNotFound:
            rows.append({"symbol": s, "found": False})
    df = pd.DataFrame(rows)
    df["group"] = ["tracker" if s in TRACKERS else ("bizd_holding" if s in bizd_now else "a4_listing") for s in df["symbol"]]
    df.loc[df["symbol"].isin(A4_LIVE) & df["symbol"].isin(bizd_now), "group"] = "bizd_holding+a4"
    df.to_csv(OUT / "alpaca_bdc_flags.csv", index=False)
    bdcs = df[df["group"] != "tracker"]
    summ = {"read_utc": now_utc(), "alpaca_clock": str(clock.get("timestamp")),
            "bizd_snapshot": str(last["report_dt"].max().date()), "n_bizd_tickers": len(bizd_now),
            "bdcs_read": int(len(bdcs)), "bdcs_found": int(bdcs["found"].sum()),
            "bdcs_shortable": int((bdcs["shortable"] == True).sum()),          # noqa: E712
            "bdcs_easy_to_borrow": int((bdcs["easy_to_borrow"] == True).sum()),  # noqa: E712
            "a4_listings_shortable": df[df["symbol"].isin(A4_LIVE)][["symbol", "shortable", "easy_to_borrow"]].to_dict("records"),
            "trackers": df[df["group"] == "tracker"][["symbol", "found", "shortable", "easy_to_borrow"]].to_dict("records")}
    (OUT / "alpaca_bdc_flags_summary.json").write_text(json.dumps(summ, indent=1, default=str) + "\n")
    print(df.to_string(index=False))
    print(json.dumps({k: v for k, v in summ.items() if k not in ("a4_listings_shortable",)}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
