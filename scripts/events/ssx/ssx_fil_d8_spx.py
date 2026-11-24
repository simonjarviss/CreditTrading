"""D8: S&P MidCap 400 / SmallCap 600 changes -- the zero-trial pieces that can be measured from R2.

    export QUANTT_ENV_FILE=/abs/path/config/.env
    python3 scripts/events/ssx/ssx_fil_d8_spx.py census

ZERO TRIALS. Index membership dates, pre-event dollar volume and market cap
(CRSP rows < 2023 only). No return of any kind.

WHAT THIS SCRIPT CAN AND CANNOT SAY
-----------------------------------
Compustat's `idxcst_his` on R2 holds CURRENT members only (S&P MidCap 400,
gvkeyx 024248: exactly 400 rows; S&P SmallCap 600, gvkeyx 030824: about 600),
so it cannot count changes per year: every deleted name is missing. It is used
for two labelled, survivorship-biased numbers only:
  * the addition year (`from`) of today's members, a LOWER BOUND on additions;
  * for today's members added 2015-2022, implied passive demand at addition in
    days of pre-event ADV: demand = passive share x market cap at t-11,
    against mean dollar volume over sessions t-30..t-11 before the effective
    date (11 sessions back, so neither an ad hoc announcement window -- 2 to 5
    sessions in the 2024-25 sample -- nor a quarterly one -- 10 sessions --
    is inside it).
The passive share is an input, not a measurement here: indexed assets from S&P
DJI's survey [S, search summary; the PDF returned 403] over index market cap
[S, Wikipedia]. Both are passed on the command line so the arithmetic is
visible and re-runnable with better inputs.

The change counts and announcement-to-effective gaps come from S&P DJI's own
press releases (PR Newswire), read by hand into the CARDS note; they are not
in this script.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.events.ssx import ssx_fil_common as C  # noqa: E402

GVKEYX = {"sp400": "024248", "sp600": "030824"}
OUT = C.OUT


def census(passive400: float, passive600: float) -> dict:
    p = C.CACHE / "comp_idxcst_his.parquet"
    r2, con = C._r2()
    if not p.exists():
        h = r2.q(con, f"SELECT * FROM read_parquet('{r2.r2_path('comp_na_daily_all', 'idxcst_his')}')")
        h.to_parquet(p)
    h = pd.read_parquet(p)
    h["from"] = pd.to_datetime(h["from"])
    out = {}
    links = C.cik_permno_links(offline=True)[["gvkey", "permno", "linkdt", "linkenddt"]].drop_duplicates()
    dv = C.dv_panel(offline=True)
    for name, gx in GVKEYX.items():
        m = h[h["gvkeyx"] == gx].copy()
        out[name] = {"rows_now": int(len(m)), "rows_with_open_thru": int(m["thru"].isna().sum()),
                     "added_by_year_current_members": {int(k): int(v) for k, v in m["from"].dt.year.value_counts().sort_index().items() if k >= 2008}}
        a = m[m["from"].dt.year.between(2015, 2022)].merge(links, on="gvkey")
        a = a[(a["linkdt"] <= a["from"]) & (a["from"] <= a["linkenddt"])].drop_duplicates(["gvkey", "from"])
        if a.empty:
            continue
        perms = sorted(a["permno"].astype(int).unique())
        px = r2.q(con, f"""SELECT permno, date, abs(prc) * shrout * 1000 AS mcap FROM read_parquet('{r2.r2_path('crsp_a_stock', 'dsf')}')
                           WHERE date BETWEEN DATE '2014-10-01' AND DATE '2022-12-31' AND prc IS NOT NULL AND shrout IS NOT NULL
                             AND permno IN ({','.join(map(str, perms))})""")
        px["date"] = pd.to_datetime(px["date"])
        if px["date"].max() >= pd.Timestamp(C.TIME_HOLDOUT):
            raise C.CensusError("2023+ CRSP row read")
        rows = []
        dvp = dv[dv["permno"].isin(perms)]
        a = a.rename(columns={"from": "eff"})
        for r in a.itertuples():
            g = dvp[dvp["permno"] == r.permno].sort_values("date")
            k = np.searchsorted(g["date"].values, np.datetime64(r.eff), side="left")
            w = g.iloc[max(0, k - 30):max(0, k - 10)]   # sessions t-30..t-11 before the effective date
            if len(w) < 15:
                continue
            assert w["date"].max() < r.eff, "ADV window reached the effective date"
            mc = px[(px["permno"] == r.permno) & (px["date"] <= w["date"].max())].sort_values("date")
            if mc.empty:
                continue
            rows.append({"permno": r.permno, "eff": r.eff, "adv": float(w["dv"].mean()),
                         "mcap": float(mc["mcap"].iloc[-1])})
        d = pd.DataFrame(rows)
        share = passive400 if name == "sp400" else passive600
        d["demand_usd"] = share * d["mcap"]
        d["demand_days_adv"] = d["demand_usd"] / d["adv"]
        out[name]["additions_2015_22_current_members_with_data"] = int(len(d))
        out[name]["passive_share_input"] = share
        out[name]["pre_event_adv_median_usd"] = float(d["adv"].median())
        out[name]["share_adv_ge_1m"] = round(float((d["adv"] >= 1e6).mean()), 4)
        out[name]["mcap_median_usd"] = float(d["mcap"].median())
        out[name]["demand_days_adv_median"] = round(float(d["demand_days_adv"].median()), 2)
        out[name]["demand_days_adv_p25_p75"] = [round(float(d["demand_days_adv"].quantile(q)), 2) for q in (.25, .75)]
    C.write_json(OUT / "d8_spx_summary.json", out)
    print(out)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("part", choices=("census",))
    # Indexed assets / index market cap, both [S]: 400: USD 397bn (S&P DJI survey, end-2024)
    # / USD 2.7tn (Wikipedia, 2023-12-29); 600: USD 162bn (survey, end-2025) / USD 1.83tn (Wikipedia, 2026-05-29).
    # Required, no default: a sourced input, never a number the script supplies itself.
    ap.add_argument("--passive400", type=float, required=True)
    ap.add_argument("--passive600", type=float, required=True)
    a = ap.parse_args(argv)
    census(a.passive400, a.passive600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
