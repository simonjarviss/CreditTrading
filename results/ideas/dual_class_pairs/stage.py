"""Stage same-issuer share-class pairs from CRSP: the pair list, their matched controls, daily rows.

    QUANTT_ENV_FILE=<env file> python3 results/ideas/dual_class_pairs/stage.py monthly
    QUANTT_ENV_FILE=<env file> python3 results/ideas/dual_class_pairs/stage.py daily

WHY TWO STEPS: each is one scan of CRSP's daily file on R2 (110M rows over https), which
takes minutes and sometimes times out. `monthly` writes one row per common share and month;
the pair list and the control matches are built from it locally; `daily` then pulls daily
rows for exactly those securities in one scan.

WHAT IS A PAIR, BY RULE (no hand-picked list): two CRSP permnos with the same permco (CRSP's
issuer key), both common shares (securitytype EQTY, subtype COM, sharetype NS; ADRs, units,
funds and preferreds are other types), both with rows in the same month for at least 12
months between 1999-01 and 2025-12. Dead issuers are in: CRSP keeps delisted securities.
Tracking stocks (a second common line that tracks one division, not the whole company)
share a permco too and are NOT removed by this rule; explore.py reports results with and
without pairs whose CRSP security names mark them as tracking or group shares.

THE CONTROL, PSEUDO-PAIRS: for every pair and every calendar year it is alive, class A is
kept and class B is replaced by a different company: same two-digit SIC code as B, not an
issuer in the pair list, alive in December of the year before, and nearest to B in log
market value at that December's last trading day. Matched on information dated before the
year it is used in.

WHERE IT WRITES: ~/quantt_research/dual_class_pairs/ only (licensed rows never enter the
repository). Read-only at R2. Prints counts only.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = Path.home() / "quantt_research" / "dual_class_pairs"
COMMON = "securitytype = 'EQTY' and securitysubtype = 'COM' and sharetype = 'NS'"
START, END = "1999-01-01", "2025-12-31"
MIN_OVERLAP_MONTHS = 12


def connect():
    from src.data import r2
    con = r2.connect()
    con.execute("set enable_progress_bar = false")
    con.execute("set http_timeout = 600000")
    con.execute("set http_retries = 8")
    return con, r2


def retry(fn, n=4):
    for i in range(n):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001  re-raised after the last attempt, never swallowed
            print(f"attempt {i + 1} failed: {type(e).__name__}: {str(e)[:160]}", flush=True)
            if i == n - 1:
                raise
            time.sleep(20)


def monthly() -> None:
    con, r2 = connect()
    dsf = r2.r2_path("crsp_a_stock", "dsf_v2")
    mp = OUT / "monthly.parquet"
    retry(lambda: con.execute(f"""
        copy (select permno, permco, date_trunc('month', dlycaldt) as month, min(dlycaldt) as first_day,
                     max(dlycaldt) as last_day, count(*) as n_days,
                     arg_max(cast(dlycap as double), dlycaldt) as cap, arg_max(siccd, dlycaldt) as siccd,
                     arg_max(ticker, dlycaldt) as ticker, avg(cast(dlyprcvol as double)) as adv,
                     arg_max(usincflg, dlycaldt) as usincflg
              from read_parquet('{dsf}')
              where dlycaldt between date '{START}' and date '{END}' and {COMMON}
              group by 1, 2, 3)
        to '{mp}' (format parquet, compression zstd)"""))
    sn = r2.r2_path("crsp_a_stock", "stocknames_v2")
    retry(lambda: con.execute(f"copy (select * from read_parquet('{sn}')) to '{OUT / 'stocknames.parquet'}' (format parquet)"))
    m = pd.read_parquet(mp)
    print(f"monthly.parquet: {len(m):,} rows, {m['permno'].nunique():,} permnos, {m['month'].min().date()} .. {m['last_day'].max()}")


def build_pairs() -> tuple[pd.DataFrame, pd.DataFrame]:
    m = pd.read_parquet(OUT / "monthly.parquet")
    m["month"] = pd.to_datetime(m["month"])
    multi = m.groupby(["permco", "month"])["permno"].nunique()
    multi = multi[multi >= 2].reset_index()[["permco", "month"]]
    mm = m.merge(multi, on=["permco", "month"])
    j = mm.merge(mm, on=["permco", "month"], suffixes=("_a", "_b"))
    j = j[j["permno_a"] < j["permno_b"]]
    pairs = j.groupby(["permco", "permno_a", "permno_b"]).agg(
        first_month=("month", "min"), last_month=("month", "max"), months=("month", "count"),
        ticker_a=("ticker_a", "last"), ticker_b=("ticker_b", "last"), siccd=("siccd_b", "last")).reset_index()
    pairs = pairs[pairs["months"] >= MIN_OVERLAP_MONTHS].reset_index(drop=True)
    # controls: per pair and year, a different company matched to class B on SIC2 and size, as of the prior December
    dual_permcos = set(pairs["permco"])
    dec = m[m["month"].dt.month == 12].copy()
    dec["year_used"] = dec["month"].dt.year + 1
    dec["sic2"] = dec["siccd"] // 100
    dec = dec[dec["cap"] > 0]
    pool = dec[~dec["permco"].isin(dual_permcos)]
    rows = []
    for p in pairs.itertuples():
        for y in range(max(p.first_month.year, 2000), p.last_month.year + 1):
            b = dec[(dec["permno"] == p.permno_b) & (dec["year_used"] == y)]
            if b.empty:
                continue                     # B had no December row the year before: no control that year (counted)
            b = b.iloc[0]
            c = pool[(pool["year_used"] == y) & (pool["sic2"] == b["sic2"])]
            if c.empty:
                continue
            k = (np.log(c["cap"]) - np.log(b["cap"])).abs().idxmin()
            assert c.loc[k, "month"] < pd.Timestamp(y, 1, 1)          # matched on data dated before the year of use
            rows.append({"permno_a": p.permno_a, "permno_b": p.permno_b, "year": y, "match": int(c.loc[k, "permno"]),
                         "cap_b": float(b["cap"]), "cap_match": float(c.loc[k, "cap"])})
    ctl = pd.DataFrame(rows)
    pairs.to_parquet(OUT / "pairs.parquet"); ctl.to_parquet(OUT / "controls.parquet")
    alive = {y: int(((pairs["first_month"].dt.year <= y) & (pairs["last_month"].dt.year >= y)).sum()) for y in range(1999, 2026)}
    print(f"pairs: {len(pairs)} on {pairs['permco'].nunique()} issuers; alive by year: {alive}")
    print(f"controls: {len(ctl)} pair-years matched, {ctl['match'].nunique()} distinct matches; "
          f"median |log cap gap| {float((np.log(ctl['cap_match']) - np.log(ctl['cap_b'])).abs().median()):.3f}")
    return pairs, ctl


def daily() -> None:
    pairs, ctl = build_pairs()
    ids = sorted(set(pairs["permno_a"]) | set(pairs["permno_b"]) | set(ctl["match"]))
    con, r2 = connect()
    dsf = r2.r2_path("crsp_a_stock", "dsf_v2")
    con.register("ids", pd.DataFrame({"permno": ids}))
    dp = OUT / "daily.parquet"
    retry(lambda: con.execute(f"""
        copy (select x.permno, x.dlycaldt as date, cast(x.dlyret as double) as ret, cast(x.dlyprc as double) as prc,
                     x.dlyprcflg as prcflg, cast(x.dlyvol as double) as vol, cast(x.dlyprcvol as double) as dollar_volume,
                     cast(x.dlybid as double) as bid, cast(x.dlyask as double) as ask, cast(x.dlycap as double) as cap,
                     x.dlydelflg as delflg, x.securitysubtype as subtype, x.sharetype as sharetype
              from read_parquet('{dsf}') x
              where x.permno in (select permno from ids) and x.dlycaldt between date '{START}' and date '{END}'
              order by date, permno)
        to '{dp}' (format parquet, compression zstd)"""))
    d = con.execute(f"select count(*), count(distinct permno), min(date), max(date) from read_parquet('{dp}')").fetchone()
    print(f"daily.parquet: {d[0]:,} rows on {d[1]:,} securities, {d[2]} .. {d[3]}")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    {"monthly": monthly, "pairs": build_pairs, "daily": daily}[sys.argv[1]]()
