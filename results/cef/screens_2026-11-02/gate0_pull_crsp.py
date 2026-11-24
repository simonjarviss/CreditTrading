"""Gate 0 (survivorship) of PREREG_C4_LEVEL: the CRSP pull, for the team lead to run.

    export QUANTT_ENV_FILE=<absolute path to the env file holding the R2 keys>
    python3 results/cef/screens_2026-11-02/gate0_pull_crsp.py            # the pull (read-only, R2)
    python3 results/cef/screens_2026-11-02/gate0_pull_crsp.py --dry-run  # print the SQL; no connection

WHY THIS PULL
-------------
C4's 74 funds are the funds alive, listed, tradable and shortable on
2026-10-14. A discount-LEVEL book that is partly a persistent fund-level bet
(the screen's K3: weights' rank correlation 0.59 at 12 months) is exposed to
survivorship. Gate 0 re-runs the fit screen on survivors plus the funds that
died, before any 2023+ return of the signal is read. The level needs a NAV.
**R2 holds no CEF NAV history** (docs/DATA.md §3: `crsp_q_mutualfunds` did
not hold any of the 44 credit CEFs, measured 2026-10-08), so this pull does
two things:

  1. the dead population, from CRSP: every security with a CEF share code
     (14 or 44, the repo's own rule: scripts/data/stage_crsp_cef_families.py
     CEF_SHRCD) and a name record overlapping 2004-01-02 .. 2022-12-30, with
     its names, daily prices and returns, distributions and delisting record;
  2. a decisive NAV-coverage probe: does CRSP's mutual-fund file hold ANY of
     those securities (by 8-character CUSIP or ticker)? The 2026-10-08 check
     covered the 44 credit tickers only. If it does, their monthly NAVs come
     with the pull. If it does not, Gate 0's NAVs come from the funds'
     N-CSR/N-CSRS period-end NAVs on EDGAR (the census reader
     `scripts/events/cef_corp_action_census.py::nav_beside_price`), a second,
     separate fetch.

TABLES, FIELDS, DATES (the 2023 holdout is enforced in the SQL and re-asserted)
-------------------------------------------------------------------------------
  crsp_a_stock.stocknames  permno namedt nameenddt shrcd exchcd siccd ncusip ticker comnam cusip
                           WHERE shrcd IN (14, 44) AND namedt <= 2022-12-30 AND nameenddt >= 2004-01-02
  crsp_a_stock.dsf         permno date prc ret retx vol shrout cfacpr cfacshr openprc
                           for those permnos, 2004-01-02 .. 2022-12-30
  crsp_a_stock.dsedist     permno distcd divamt facpr facshr dclrdt exdt rcrddt paydt
                           for those permnos, exdt 2004-01-02 .. 2022-12-30
  crsp_a_stock.dsedelist   permno dlstdt dlstcd nwperm dlprc dlamt dlret dlretx, every row for
                           those permnos; dlret/dlretx/dlprc/dlamt are NULLED where dlstdt >
                           2022-12-30 (a later delisting is kept as a dated EVENT, never as a return)
  crsp_q_mutualfunds.fund_hdr     crsp_fundno cusip8 ncusip ticker fund_name dead_flag et_flag
                           WHERE cusip8 or ncusip matches a pulled ncusip, or ticker matches the
                           CEF's ticker or its Yahoo-style NAV symbol X<TK>X (every match is
                           reviewed by name at Gate 0: a recycled ticker is not a NAV source)
  crsp_q_mutualfunds.monthly_nav  crsp_fundno caldt mnav, for any matched fund, caldt <= 2022-12-31

WRITES (gitignored by `results/**/_cache_*`; nothing under data/; CRSP is licensed and
the repository is public, so none of these is ever committed):
  results/cef/screens_2026-11-02/_cache_gate0/
      cef_names.parquet  cef_dsf.parquet  cef_dist.parquet  cef_delist.parquet
      mf_matches.parquet mf_monthly_nav.parquet  manifest.json (row counts, date
      ranges, the SQL text, UTC time; no credential, no bucket name)

Read-only. It prints row counts and dates, never a key, a secret or the bucket.
`--local-root DIR` runs the identical SQL against DIR/<schema>/<table>.parquet,
so that the queries can be tested without R2 (`--self-test` builds such a DIR
from synthetic rows and checks the holdout filters).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

OUT = HERE / "_cache_gate0"
START, FIT_END = "2004-01-02", "2022-12-30"
CEF_SHRCD = (14, 44)            # scripts/data/stage_crsp_cef_families.py CEF_SHRCD


def queries(path) -> dict[str, str]:
    """The SQL, keyed by output name. `path(schema, table)` gives a parquet location."""
    names = (f"SELECT permno, namedt, nameenddt, shrcd, exchcd, siccd, ncusip, ticker, comnam, cusip "
             f"FROM read_parquet('{path('crsp_a_stock', 'stocknames')}') "
             f"WHERE shrcd IN {CEF_SHRCD} AND namedt <= DATE '{FIT_END}' AND nameenddt >= DATE '{START}'")
    perm = f"SELECT DISTINCT permno FROM ({names})"
    return {
        "cef_names": names,
        "cef_dsf": (f"SELECT permno, date, prc, ret, retx, vol, shrout, cfacpr, cfacshr, openprc "
                    f"FROM read_parquet('{path('crsp_a_stock', 'dsf')}') "
                    f"WHERE permno IN ({perm}) AND date BETWEEN DATE '{START}' AND DATE '{FIT_END}'"),
        "cef_dist": (f"SELECT permno, distcd, divamt, facpr, facshr, dclrdt, exdt, rcrddt, paydt "
                     f"FROM read_parquet('{path('crsp_a_stock', 'dsedist')}') "
                     f"WHERE permno IN ({perm}) AND exdt BETWEEN DATE '{START}' AND DATE '{FIT_END}'"),
        "cef_delist": (f"SELECT permno, dlstdt, dlstcd, nwperm, "
                       f"CASE WHEN dlstdt <= DATE '{FIT_END}' THEN dlprc END AS dlprc, "
                       f"CASE WHEN dlstdt <= DATE '{FIT_END}' THEN dlamt END AS dlamt, "
                       f"CASE WHEN dlstdt <= DATE '{FIT_END}' THEN dlret END AS dlret, "
                       f"CASE WHEN dlstdt <= DATE '{FIT_END}' THEN dlretx END AS dlretx "
                       f"FROM read_parquet('{path('crsp_a_stock', 'dsedelist')}') WHERE permno IN ({perm})"),
        "mf_matches": (f"SELECT h.crsp_fundno, h.cusip8, h.ncusip, h.ticker, h.fund_name, h.dead_flag, h.et_flag "
                       f"FROM read_parquet('{path('crsp_q_mutualfunds', 'fund_hdr')}') h "
                       f"WHERE h.cusip8 IN (SELECT DISTINCT ncusip FROM ({names})) "
                       f"OR h.ncusip IN (SELECT DISTINCT ncusip FROM ({names})) "
                       f"OR h.ticker IN (SELECT DISTINCT ticker FROM ({names}) WHERE ticker IS NOT NULL) "
                       f"OR h.ticker IN (SELECT DISTINCT 'X' || ticker || 'X' FROM ({names}) WHERE ticker IS NOT NULL)"),
    }


def mf_nav_query(path, fundnos: list[int]) -> str:
    ids = ", ".join(str(int(f)) for f in fundnos) or "NULL"
    return (f"SELECT crsp_fundno, caldt, mnav FROM read_parquet('{path('crsp_q_mutualfunds', 'monthly_nav')}') "
            f"WHERE crsp_fundno IN ({ids}) AND caldt <= DATE '2022-12-31'")


def check_holdout(frames: dict[str, pd.DataFrame]) -> None:
    """Raise if any return-bearing row is dated after FIT_END (the SQL should make this impossible)."""
    end = pd.Timestamp(FIT_END)
    for name, col in (("cef_dsf", "date"), ("cef_dist", "exdt"), ("mf_monthly_nav", "caldt")):
        f = frames.get(name)
        if f is not None and len(f) and pd.to_datetime(f[col]).max() > end + pd.Timedelta(days=1):
            raise AssertionError(f"{name}: a row dated {pd.to_datetime(f[col]).max().date()} > {FIT_END}")
    d = frames.get("cef_delist")
    if d is not None and len(d):
        late = pd.to_datetime(d["dlstdt"]) > end
        if d.loc[late, ["dlret", "dlretx", "dlprc", "dlamt"]].notna().any().any():
            raise AssertionError("cef_delist: a delisting return after the fit end was not nulled")


def run(con, path, out: Path, sql_only: bool = False) -> dict:
    q = queries(path)
    if sql_only:
        for k, v in q.items():
            print(f"-- {k}\n{v};\n")
        print("-- mf_monthly_nav\n" + mf_nav_query(path, [0]) + ";  -- with the matched crsp_fundno list")
        return {}
    frames = {k: con.execute(v).df() for k, v in q.items()}
    fundnos = sorted(frames["mf_matches"]["crsp_fundno"].dropna().astype(int).unique())
    frames["mf_monthly_nav"] = con.execute(mf_nav_query(path, fundnos)).df() if fundnos else \
        pd.DataFrame(columns=["crsp_fundno", "caldt", "mnav"])
    check_holdout(frames)
    out.mkdir(parents=True, exist_ok=True)
    man = {"pulled_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "fit_end": FIT_END, "start": START, "cef_shrcd": list(CEF_SHRCD), "tables": {}}
    for k, f in frames.items():
        f.to_parquet(out / f"{k}.parquet", index=False)
        dcol = next((c for c in ("date", "exdt", "dlstdt", "caldt", "namedt") if c in f.columns), None)
        man["tables"][k] = {"rows": int(len(f)),
                            "permnos": int(f["permno"].nunique()) if "permno" in f.columns else None,
                            "date_min": str(pd.to_datetime(f[dcol]).min().date()) if dcol and len(f) else None,
                            "date_max": str(pd.to_datetime(f[dcol]).max().date()) if dcol and len(f) else None}
    man["sql"] = {k: v.replace(str(path("x", "y")).rsplit("/wrds/", 1)[0], "<root>") for k, v in q.items()}
    (out / "manifest.json").write_text(json.dumps(man, indent=1))
    for k, v in man["tables"].items():
        print(f"  {k:<16} rows {v['rows']:>9}  permnos {v['permnos']}  {v['date_min']} .. {v['date_max']}")
    print(f"  CRSP-MF matches: {len(fundnos)} fund(s) -> "
          f"{'a NAV source exists for some CEFs' if fundnos else 'NO NAV source in R2: Gate 0 NAVs come from EDGAR N-CSR'}")
    return man


def self_test() -> int:
    """The SQL on synthetic local tables: CEF filter, date filters, the delisting null."""
    import duckdb
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        def put(schema, table, df):
            (root / schema).mkdir(parents=True, exist_ok=True)
            df.to_parquet(root / schema / f"{table}.parquet", index=False)
        D = pd.Timestamp
        put("crsp_a_stock", "stocknames", pd.DataFrame({
            "permno": [1, 2, 3], "namedt": [D("2000-01-03")] * 3, "nameenddt": [D("2024-12-31")] * 3,
            "shrcd": [14, 44, 11], "exchcd": [1, 1, 1], "siccd": [6726] * 3, "ncusip": ["AAAAAAAA", "BBBBBBBB", "CCCCCCCC"],
            "ticker": ["AAA", "BBB", "CCC"], "comnam": ["A FUND", "B FUND", "C CORP"], "cusip": ["AAAAAAAA", "BBBBBBBB", "CCCCCCCC"]}))
        dates = [D("2003-12-31"), D("2010-06-30"), D("2022-12-30"), D("2023-01-03")]
        put("crsp_a_stock", "dsf", pd.DataFrame([dict(permno=p, date=d, prc=10.0, ret=0.01, retx=0.01, vol=100.0,
                                                      shrout=1.0, cfacpr=1.0, cfacshr=1.0, openprc=10.0)
                                                 for p in (1, 2, 3) for d in dates]))
        put("crsp_a_stock", "dsedist", pd.DataFrame([dict(permno=p, distcd=1232, divamt=0.1, facpr=0.0, facshr=0.0,
                                                          dclrdt=d, exdt=d, rcrddt=d, paydt=d) for p in (1, 2) for d in dates]))
        put("crsp_a_stock", "dsedelist", pd.DataFrame({
            "permno": [1, 2], "dlstdt": [D("2015-05-01"), D("2024-03-01")], "dlstcd": [233, 233], "nwperm": [0, 0],
            "dlprc": [9.0, 9.0], "dlamt": [9.0, 9.0], "dlret": [0.05, 0.05], "dlretx": [0.05, 0.05]}))
        put("crsp_q_mutualfunds", "fund_hdr", pd.DataFrame({
            "crsp_fundno": [77], "cusip8": ["BBBBBBBB"], "ncusip": [None], "ticker": ["XBBB"], "fund_name": ["B FUND"],
            "dead_flag": ["N"], "et_flag": [None]}))
        put("crsp_q_mutualfunds", "monthly_nav", pd.DataFrame({
            "crsp_fundno": [77, 77], "caldt": [D("2022-12-30"), D("2023-01-31")], "mnav": [10.0, 10.1]}))
        con = duckdb.connect()
        path = lambda s, t: str(root / s / f"{t}.parquet")
        out = root / "out"
        man = run(con, path, out)
        t = man["tables"]
        assert t["cef_names"]["permnos"] == 2, "the CEF share-code filter"
        assert t["cef_dsf"]["date_min"] == "2010-06-30" and t["cef_dsf"]["date_max"] == "2022-12-30", "dsf date filter"
        dl = pd.read_parquet(out / "cef_delist.parquet").set_index("permno")
        assert dl.loc[1, "dlret"] == 0.05 and pd.isna(dl.loc[2, "dlret"]), "a post-fit delisting return must be nulled"
        assert t["mf_matches"]["rows"] == 1 and t["mf_monthly_nav"]["date_max"] == "2022-12-30", "MF probe and its date cut"
    print("self-test passed: share-code filter, date filters, delisting null, MF probe and cut")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print the SQL and exit; no connection")
    ap.add_argument("--self-test", action="store_true", help="run the SQL on synthetic local tables")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if a.dry_run:
        run(None, lambda s, t: f"s3://<bucket>/wrds/{s}/{t}.parquet", OUT, sql_only=True)
        return 0
    from src.data import r2
    cfg = r2.load_config()          # raises, naming what is missing; never prints a value
    con = r2.connect(cfg)
    run(con, lambda s, t: r2.r2_path(s, t, cfg), OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
