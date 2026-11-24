"""C7 census: BDC baby bonds against BDC equity -- count, borrow, ADV and no-trade share (pre-2023 volume).

    python3 scripts/events/ssx/ssx_lcred_bdc.py        # offline: census + volume cache + universe map

WHY (graveyard check first)
---------------------------
C7 says a BDC's exchange-listed notes lag its equity after a non-accrual or
NAV shock. `leadlag` (KILLED, D1) died because the "lag" of thin wrappers was
non-synchronous trading measured on a non-transactable price: a close printed
on a day with no trade, or (H+L)/2, is a stale mark, and the lag vanishes at an
executable close. So the first number that matters for C7 is how often a BDC
baby bond does not trade at all: each no-trade session is a stale close, the
exact artefact `leadlag` measured. The second is capacity (ADV) and the third
borrow (a lagging long-the-notes/short-the-equity pair needs the equity short;
the opposite pair needs the notes short).

Inputs: today's census (BDC issuer = issuer CIK is a BDC common's CIK in the
2026-10-08 universe map), the pre-2023 Alpaca volume cache (volume only), and
the universe map's BDC equity ADV [doc: CRSP adv63, window ending 2024-12-31].
Share volume x $25 par is used as a dollar proxy so no price is read.
ZERO TRIALS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx.ssx_lcred_common import OUT, REPO, write_json


def main() -> int:
    cen = pd.read_csv(OUT / "census_2026-10-19.csv")
    vol = pd.read_csv(OUT / "volume_per_symbol_2016_2022.csv")
    u = pd.read_csv(REPO / "results" / "data" / "universe_2026-10-08" / "universe_map.csv")
    d = cen.merge(vol[["symbol", "first_bar", "no_trade_share", "thin_share_n_le_2", "adv_shares_2022", "sessions_listed"]],
                  on="symbol", how="left")
    groups = {"bdc_baby_bond": d[(d.kind == "baby_bond") & d.bdc_issuer],
              "other_baby_bond": d[(d.kind == "baby_bond") & ~d.bdc_issuer],
              "preferred": d[d.kind == "preferred"]}
    out = {"census_date": "2026-10-19", "volume_window": "2016-01-04..2022-12-30 (pre-2023 only)"}
    for k, g in groups.items():
        gv = g[g.no_trade_share.notna()]
        g22 = gv[gv.adv_shares_2022 > 0]
        out[k] = {"issues_today": int(len(g)), "tradable": int(g.tradable.sum()), "shortable": int(g.shortable.sum()),
                  "issuers": int(g.cik.nunique()), "with_pre2023_volume": int(len(gv)),
                  "no_trade_share_median": round(float(gv.no_trade_share.median()), 3) if len(gv) else None,
                  "no_trade_share_p75": round(float(gv.no_trade_share.quantile(.75)), 3) if len(gv) else None,
                  "thin_share_n_le_2_median": round(float(gv.thin_share_n_le_2.median()), 3) if len(gv) else None,
                  "thin_share_n_le_2_p75": round(float(gv.thin_share_n_le_2.quantile(.75)), 3) if len(gv) else None,
                  "adv_shares_2022_median": round(float(g22.adv_shares_2022.median()), 0) if len(g22) else None,
                  "adv_par_usd_2022_median": round(float(g22.adv_shares_2022.median()) * 25, 0) if len(g22) else None}
    b = u[u.family == "bdc"]
    out["bdc_equity_doc"] = {"n_in_map": int(len(b)), "shortable_2026_10_08": int((b.shortable == True).sum()),  # noqa: E712
                             "median_adv63_usd": round(float(b.adv63.median()), 0),
                             "label": "[doc] universe_map.csv adv63 (CRSP, window ending 2024-12-31)"}
    bb = groups["bdc_baby_bond"]
    issuers_with_notes = set(bb.cik.dropna().astype(int))
    out["bdc_issuers_with_listed_notes"] = len(issuers_with_notes)
    write_json(OUT / "c7_bdc_summary.json", out)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
