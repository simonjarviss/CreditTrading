"""Survivorship count for C4/C6: preferred-pattern redemptions and partial calls in Alpaca's
corporate-actions feed, per year 2020-2025.

    export QUANTT_ENV_FILE=<absolute path to the env file>       # never printed
    python3 scripts/events/ssx/ssx_lcred_redemptions.py

WHY
---
Today's census (`ssx_lcred_census.py`) holds only issues that SURVIVED: a
preferred that was called is gone from the asset list. C4 (did fixed-to-float
issues float or get called?) and C6 (how often does a call pin a preferred's
price?) both need the called side. Alpaca's `/v1/corporate-actions` carries
`redemption` and `partial_call` events. A NYSE preferred is written with ".PR"
in Alpaca's symbol, so counting those symbols is a lower bound on preferred
calls (Nasdaq preferreds and baby bonds carry no marker and are not counted).
The corp catalogue found Alpaca's history thin before 2020, so 2020-2025 only.
Event counts only; no price. ZERO TRIALS.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx.ssx_lcred_common import OUT, alpaca, write_json

PREF_SYM = re.compile(r"\.PR[A-Z]?$")


def main() -> int:
    c = alpaca()
    rows = []
    for y in range(2020, 2026):
        for q0 in (1, 4, 7, 10):
            s = dt.date(y, q0, 1)
            e = (dt.date(y, q0 + 3, 1) if q0 < 10 else dt.date(y + 1, 1, 1)) - dt.timedelta(days=1)
            token = None
            for _ in range(200):
                params = {"types": "redemption,partial_call", "start": s.isoformat(), "end": e.isoformat(),
                          "limit": 1000}
                if token:
                    params["page_token"] = token
                body = c._get(c._data, "/v1/corporate-actions", params)
                ca = body.get("corporate_actions") or {}
                for key in ("redemptions", "partial_calls"):
                    for r in ca.get(key) or []:
                        rows.append({"type": key, "symbol": r.get("symbol"), "process_date": r.get("process_date"),
                                     "id": r.get("id")})
                token = body.get("next_page_token")
                if not token:
                    break
    df = pd.DataFrame(rows).drop_duplicates("id")
    df["year"] = pd.to_datetime(df.process_date).dt.year
    df["pref_symbol"] = df.symbol.fillna("").str.contains(PREF_SYM)
    out = {"source": "Alpaca GET /v1/corporate-actions types=redemption,partial_call, read 2026-10-19",
           "rows": int(len(df)),
           "by_year_type_all": df.groupby(["year", "type"]).size().unstack(fill_value=0).to_dict(orient="index"),
           "by_year_type_nyse_pref_symbols": df[df.pref_symbol].groupby(["year", "type"]).size()
                                             .unstack(fill_value=0).to_dict(orient="index"),
           "note": "NYSE '.PR' symbols only: a lower bound on preferred calls"}
    write_json(OUT / "redemptions_summary.json", out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
