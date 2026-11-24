"""SEC fails-to-deliver census for CEFs and BDCs, 2019-2022 (ssx generator, cards G1 and G11).

    export QUANTT_ENV_FILE=<abs path>          # SEC_USER_AGENT and R2 keys; never printed
    python3 scripts/events/ssx/ssx_gen_ftd.py fetch      # 96 half-month files, EdgarClient at 1.5 s
    python3 scripts/events/ssx/ssx_gen_ftd.py census     # cache + R2 CRSP; no other network

WHY THIS EXISTS
---------------
Card G1 (`results/events/ssx/ssx_gen/CARDS_2026-10-19.md`) asks whether the Reg SHO
threshold list is a dated, mechanical buy-in clock in the instruments the desk can
reach. A name is a threshold security when its aggregate fails at NSCC are at least
10,000 shares AND at least 0.5% of shares outstanding for five consecutive
settlement days (Rule 203(c)(6), read 2026-10-19 at law.cornell.edu); a
participant whose fail in a threshold security lasts 13 consecutive settlement
days must close it out by purchase (Rule 203(b)(3)). The exchanges' historical
lists are per exchange and not uniformly archived, so this script REBUILDS the
criterion from the SEC's own fails file (CUSIP, settlement date, quantity; Feb
2004 on, all fails from 2008-09-16) and CRSP shares outstanding.

Card G11 asks whether muni-CEF fails cluster at distribution record dates, as the
desk's E3 speculation (a payment in lieu of an exempt-interest dividend is
taxable to the lender, so muni lenders recall before record dates) predicts, with
taxable-bond CEFs as the negative control: their distributions are ordinary
income anyway, so a payment in lieu costs their lender nothing.

ZERO TRIALS. Fails and shares outstanding are counted; no price, return or P&L is
read. The fails file's PRICE column is dropped on load. CRSP rows are pulled
through `scripts/events/crsp_events.py`, which cannot return a 2023+ row; only
`shrout` and record dates are used. Output aggregates go to
`results/events/ssx/ssx_gen/`.

APPROXIMATIONS (each stated, none silent)
* Aggregate fails are not one participant's fails, so a run of >= 18 qualifying
  days (5 to list, 13 more) is an UPPER-BOUND proxy for a forced 203(b)(3)
  close-out, not a count of them.
* "Consecutive" is consecutive dates in the union of settlement dates the files
  contain (the market's settlement calendar as seen by NSCC).
* Shares outstanding: CRSP `shrout` (thousands) on the latest CRSP date at or
  before the settlement date; a fail-day with no CRSP shrout is reported, not
  imputed.
* CEF group by CRSP name: muni if the name matches MUNI|TAX-FREE|TAX FREE|
  TAX-EXEMPT|TAX EXEMPT|MUNICIPAL|INSURED|QUALITY INCOME (Nuveen naming) ...
  else taxable-bond if it matches INCOME|BOND|CREDIT|YIELD|LOAN|FLOAT|MORTGAGE|
  DEBT|FIXED|PREFERRED|STRATEGIC|OPPORTUN, else equity. The regex is a census
  tool; the per-name assignment is written out for checking.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
OUT = REPO / "results" / "events" / "ssx" / "ssx_gen"
# Rows keyed by CRSP permno are licensed row-level data: they go to the gitignored
# cache, never beside the committed aggregates (moved there 2026-10-19 at commit time).
ROWS = REPO / "results" / "events" / "ssx" / "_cache_ssx_gen"
URL = "https://www.sec.gov/files/data/fails-deliver-data/cnsfails{y}{m:02d}{h}.zip"
YEARS = range(2019, 2023)
MIN_SH, MIN_PCT, LIST_DAYS, CLOSE_DAYS = 10_000, 0.005, 5, 13
MUNI_RE = re.compile(r"MUNI|TAX[- ]?FREE|TAX[- ]?EXEMPT|MUNICIPAL|INSURED|QUALITY INC|CALIF|N Y |NEW YORK|NEW JERSEY|PENN", re.I)
TAXB_RE = re.compile(r"INCOME|BOND|CREDIT|YIELD|LOAN|FLOAT|MORTGAGE|DEBT|FIXED|PREF|STRATEGIC|OPPORTUN|TERM|SENIOR|GOVT|GOVERNMENT|DURATION", re.I)


def urls():
    return [URL.format(y=y, m=m, h=h) for y in YEARS for m in range(1, 13) for h in "ab"]


MANIFEST = OUT / "ftd_files_manifest.json"


def fetch() -> None:
    """Fetch every half-month file. The SEC names a few irregularly (October 2019's
    first half is `cnsfails201910a_0.zip`, read off the data page 2026-10-19), so a
    404 tries the `_0` and `_1` variants; a file still missing is RECORDED in the
    manifest as missing, and the census prints that list rather than skipping it
    quietly."""
    from scripts.data.edgar_client import EdgarClient, EdgarNotFound, RateLimiter
    c = EdgarClient(limiter=RateLimiter(min_interval=1.5))
    man = {}
    for u in urls():
        man[u] = None
        for v in (u, u.replace(".zip", "_0.zip"), u.replace(".zip", "_1.zip")):
            try:
                c.get(v)
                man[u] = v
                break
            except EdgarNotFound:
                continue
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(man, indent=1) + "\n")
    print(json.dumps({"files": len(man), "resolved": sum(v is not None for v in man.values()),
                      "missing": [k for k, v in man.items() if v is None],
                      "live_requests": c.n_requests, "cache_hits": c.n_cache_hits}))


def load_fails() -> pd.DataFrame:
    from scripts.data.edgar_client import EdgarClient
    c = EdgarClient(offline=True)
    man = json.loads(MANIFEST.read_text())
    parts = []
    for u in urls():
        if man.get(u) is None:
            continue                       # listed in the census output as missing_files
        u = man[u]
        z = zipfile.ZipFile(io.BytesIO(c.get(u)))
        if len(z.namelist()) != 1:
            raise ValueError(f"{u}: expected one member, got {z.namelist()}")
        lines = z.read(z.namelist()[0]).decode("latin-1").splitlines()
        if not lines[0].startswith("SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY"):
            raise ValueError(f"{u}: unexpected header {lines[0]!r}")
        body = [l.split("|") for l in lines[1:] if l and not l.startswith("Trailer")]
        # A description can itself contain "|" (e.g. 2021-04b, a SPAC warrant): the
        # first four fields and the last (price) are positional, so re-join the middle.
        body = [b[:4] + ["|".join(b[4:-1]), b[-1]] if len(b) > 6 else b for b in body]
        bad = [b for b in body if len(b) != 6]
        if bad:
            raise ValueError(f"{u}: {len(bad)} rows without 6 fields, first {bad[0]!r}")
        df = pd.DataFrame(body, columns=["sdate", "cusip", "symbol", "qty", "desc", "price"]).drop(columns="price")
        parts.append(df)
    f = pd.concat(parts, ignore_index=True)
    f["sdate"] = pd.to_datetime(f["sdate"], format="%Y%m%d")
    f["qty"] = pd.to_numeric(f["qty"], errors="raise")
    f["cusip8"] = f["cusip"].str[:8]
    return f


def runs(days: np.ndarray, cal_pos: dict) -> list[tuple[int, int]]:
    """Maximal runs of consecutive calendar positions: (start position, length)."""
    p = np.sort(np.array([cal_pos[d] for d in days]))
    out, s = [], 0
    for i in range(1, len(p) + 1):
        if i == len(p) or p[i] != p[i - 1] + 1:
            out.append((int(p[s]), i - s))
            s = i
    return out


def census() -> None:
    from scripts.events import crsp_events as ce
    f = load_fails()
    cal = np.sort(f.sdate.unique())
    cal_pos = {d: i for i, d in enumerate(cal)}

    nm = ce.names()
    # `crsp_events.names()` also returns every non-CEF name record ending 2005+
    # (its docstring), so keep the CEF records only: share code 14 or 44.
    nm = nm[nm.shrcd.isin([14, 44])].copy()
    nm["cusip8"] = nm["ncusip"].astype(str).str[:8]
    u = pd.read_csv(REPO / "results/data/universe_2026-10-08/universe_map.csv")
    bdc_perm = set(u.loc[u.family == "bdc", "permno"].dropna().astype(int))
    from src.data.r2 import connect, q, r2_path
    con = connect()
    bn = q(con, f"SELECT permno, ncusip, comnam, namedt, nameendt FROM read_parquet('{r2_path('crsp_a_stock','dsenames')}') "
                f"WHERE permno IN ({','.join(map(str, sorted(bdc_perm)))})")
    bn["cusip8"] = bn["ncusip"].astype(str).str[:8]
    cef_map = nm[["cusip8", "permno", "comnam"]].drop_duplicates("cusip8")
    cef_map["kind"] = "cef"
    bdc_map = bn[["cusip8", "permno", "comnam"]].drop_duplicates("cusip8")
    bdc_map["kind"] = "bdc"
    m = pd.concat([cef_map, bdc_map]).drop_duplicates("cusip8", keep="last")
    last = nm.sort_values("namedt").groupby("permno").comnam.last()
    grp = {p: ("muni" if MUNI_RE.search(n) else "taxable_bond" if TAXB_RE.search(n) else "equity")
           for p, n in last.items()}
    ff = f.merge(m, on="cusip8", how="inner")
    ff["group"] = np.where(ff.kind == "bdc", "bdc", ff.permno.map(grp))

    d = ce.daily(sorted(set(ff.permno.astype(int))))
    d = d[["permno", "date", "shrout"]].dropna().sort_values("date")
    d["date"] = pd.to_datetime(d["date"]).astype("datetime64[ns]")
    d["permno"] = d["permno"].astype(int)
    ff["permno"] = ff["permno"].astype(int)
    ff = ff.sort_values("sdate")
    ff = pd.merge_asof(ff, d.rename(columns={"date": "sdate"}), on="sdate", by="permno", direction="backward")
    no_sh = int(ff.shrout.isna().sum())
    ff["pct"] = ff.qty / (ff.shrout * 1000.0)
    ff["qual"] = (ff.qty >= MIN_SH) & (ff.pct >= MIN_PCT)

    ep = []
    for (perm, g_), g in ff[ff.qual].groupby(["permno", "group"]):
        for s, n in runs(g.sdate.values, cal_pos):
            if n >= LIST_DAYS:
                ep.append({"permno": int(perm), "group": g_, "name": last.get(perm, g.comnam.iloc[0]),
                           "start": pd.Timestamp(cal[s]).date(), "days": n,
                           "close_out_proxy": n >= LIST_DAYS + CLOSE_DAYS})
    ep = pd.DataFrame(ep)
    ROWS.mkdir(parents=True, exist_ok=True)
    ep.to_csv(ROWS / "ftd_threshold_like_episodes_2019_2022.csv", index=False)
    pd.Series(grp, name="group").rename_axis("permno").to_frame().join(last).to_csv(ROWS / "ftd_cef_group_assignment.csv")

    # G11: fail-days around distribution record dates, by group. Unit: name x
    # settlement day with any fail >= 10,000 shares (no % test: the question is
    # recall pressure, not list status). Baseline: every name-day of that group.
    dist = ce.distributions(sorted(set(ff.permno.astype(int))))
    dist = dist[dist.distcd.astype(str).str[:1] == "1"][["permno", "rcrddt"]].dropna()
    dist["rcrddt"] = pd.to_datetime(dist.rcrddt)
    dist = dist[(dist.rcrddt >= cal[0]) & (dist.rcrddt <= cal[-1])]
    rec_pos = {}
    for perm, g in dist.groupby("permno"):
        pos = np.searchsorted(cal, g.rcrddt.values)
        rec_pos[perm] = pos[pos < len(cal)]
    big = ff[ff.qty >= MIN_SH][["permno", "group", "sdate"]].drop_duplicates()
    big["pos"] = big.sdate.map(cal_pos)
    prof = []
    for g_ in ("muni", "taxable_bond", "equity", "bdc"):
        perms = [p for p in rec_pos if (grp.get(p) if g_ != "bdc" else ("bdc" if p in bdc_perm else None)) == g_]
        sub = big[big.permno.isin(perms)]
        n_names = len(perms)
        base = len(sub) / max(1, n_names * len(cal))
        for k in range(-6, 7):
            hits = tot = 0
            for p in perms:
                tgt = rec_pos[p] + k
                tgt = tgt[(tgt >= 0) & (tgt < len(cal))]
                tot += len(tgt)
                hits += int(np.isin(tgt, sub.loc[sub.permno == p, "pos"].values).sum())
            prof.append({"group": g_, "offset_sessions_from_record": k, "record_events": tot,
                         "fail_days": hits, "rate": hits / tot if tot else np.nan, "baseline_rate": base,
                         "names": n_names})
    prof = pd.DataFrame(prof)
    prof.to_csv(OUT / "ftd_record_date_profile_2019_2022.csv", index=False)

    man = json.loads(MANIFEST.read_text())
    out = {"missing_files": [k for k, v in man.items() if v is None],
           "fails_rows_2019_2022": int(len(f)), "settlement_days": int(len(cal)),
           "matched_rows_cef_bdc": int(len(ff)), "matched_rows_without_crsp_shrout": no_sh,
           "names_with_any_fail": ff.groupby("group").permno.nunique().to_dict(),
           "threshold_like_episodes": {} if ep.empty else {
               "all": int(len(ep)),
               "by_group": ep.groupby("group").size().to_dict(),
               "distinct_names_by_group": ep.groupby("group").permno.nunique().to_dict(),
               "by_year": pd.to_datetime(ep.start).dt.year.value_counts().sort_index().to_dict(),
               "close_out_proxy_runs": int(ep.close_out_proxy.sum()),
               "close_out_proxy_by_group": ep[ep.close_out_proxy].groupby("group").size().to_dict()},
           "record_date_profile": prof.pivot(index="offset_sessions_from_record", columns="group", values="rate")
                                      .round(4).to_dict(),
           "record_date_baseline": prof.groupby("group").baseline_rate.first().round(4).to_dict(),
           "record_events_by_group": prof[prof.offset_sessions_from_record == 0].set_index("group").record_events.to_dict()}
    (OUT / "ftd_census_2019_2022.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=("fetch", "census"))
    a = ap.parse_args(argv)
    fetch() if a.part == "fetch" else census()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
