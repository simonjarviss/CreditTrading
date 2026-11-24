"""Fetch CEF distribution history + fund structure facts from yfinance.

    python3 scripts/fetch_cef_distributions.py           # the live run: every name, writes data/cef/
    python3 scripts/fetch_cef_distributions.py --out DIR --tickers PTY,PDI,...   # a research copy

Outputs:
  data/cef/cef_distributions.parquet   raw ex-date/amount panel (+ splits)
  data/cef/cef_dist_features.parquet   per-ticker/per-ex-date event features
  data/cef/cef_facts.csv               static/structural facts from .info
                                       *** A DATED SNAPSHOT, NOT A PANEL. ***
                                       Carries fetched_at. Every row holds the
                                       fund's attributes AS OF THAT INSTANT and
                                       there is no history behind them, so
                                       joining it to the 27-year panel applies
                                       today's facts to 2005 -- look-ahead with
                                       no error message. 13 of 46 columns were
                                       100% null and 5 constant across all 44
                                       rows at the 2026-07-31 fetch. Superseded
                                       by work order perfund/F1 (git tag pre-clean-slate).
  data/cef/_raw_info.json              raw .info dicts (audit trail)

`--out` AND `--tickers` (added 2026-10-27, both default off)
-----------------------------------------------------------
With no arguments this script does exactly what it did before: the nightly
collector (`quantt/collect/collect.py` step `distributions`) runs it bare, and
its outputs, files and printed lines are unchanged (proved byte for byte on a
fake yfinance, 2026-10-27, `results/events/EXDRIFT_STAGE0_2026-10-27.md` §2).

A research trial needs a refreshed distribution history WITHOUT touching
`data/`: the live sleeve decides on `data/` (CLAUDE.md landmine 9), and a
research refresh written there would change what the book trades on between
the collector's runs. The ex-date drift trial's Stage 0 (DG-X1,
`results/events/PREREG_EXDATE_DRIFT_2026-10-26.md` §8) is the first such
caller. So:

  * `--out DIR` writes the actions panels (`cef_distributions.parquet`,
    `cef_splits.parquet`) to DIR and nothing else. The features and facts
    sections are SKIPPED: features reads `data/cef/cef_prices.parquet` and both
    write into `data/cef/`, which is the thing `--out` exists to avoid. A DIR
    inside `data/` is refused.
  * `--tickers A,B,...` fetches only those names, each of which must be in
    `cef_universe.csv` (an unknown name raises). It is refused without `--out`:
    the live panels are REPLACED whole, so a subset written to `data/` would
    delete every other name's history, the very loss the write guard below
    exists to prevent. It also lets a trial keep sealed names unloaded (the 27
    `cef_universe.csv` names outside the deployed universe are a holdout).

`--data-book c4` (added 2026-10-29, default off; C4 deployment plan step 3, DARK)
---------------------------------------------------------------------------------
C4's own distribution panel, for its 74 frozen funds, through this same fetcher
and its same whole-panel write guard: `data/cef_c4/cef_distributions.parquet`
(and `cef_splits.parquet` when a split is recorded). The funds and their
families come from `scripts/cef/data_books.py` (the frozen file of 2026-10-14);
`data/cef/cef_universe.csv` is never read, so no core or holdout name is
fetched. Only the actions panels are written: the features file reads the
CORE's price panel, and the facts file is a dated snapshot that nothing on C4's
path reads (and that invites look-ahead, above). `data/cef_c4/` must already
exist (it is created by the seed, data_books.py SEED): a missing directory
refuses before any fetch rather than starting an unseeded book. With `--out`,
C4's actions go to DIR instead, as for the core. Absent, or `--data-book cef`,
the run is the bare run above, byte for byte
(scripts/data/tests/test_fetch_cef_distributions_books.py).
"""
import argparse
import json
from pathlib import Path
import os
import time
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ops.common import atomic_write   # noqa: E402

warnings.filterwarnings("ignore")

ROOT = str(Path(__file__).resolve().parents[1])  # repo root, not hardcoded
CEF = os.path.join(ROOT, "data", "cef")


def naive_date(idx):
    s = pd.DatetimeIndex(idx)
    if s.tz is not None:
        s = s.tz_localize(None)
    return s.normalize()


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None,
                    help="write only the actions panels, to this directory (never inside data/)")
    ap.add_argument("--tickers", default=None,
                    help="comma-separated names from cef_universe.csv; requires --out")
    ap.add_argument("--data-book", choices=["c4", "cef"], default=None,
                    help="whose distributions: cef (the default; data/cef) or c4 (data/cef_c4, "
                         "the 74 frozen funds, actions panels only)")
    a = ap.parse_args(argv)
    if a.tickers is not None and a.out is None:
        raise SystemExit("--tickers requires --out: the data/ panels are replaced whole, so a subset "
                         "written there would delete every other name's distribution history.")
    if a.out is not None:
        out = Path(a.out).resolve()
        data_dir = (Path(ROOT) / "data").resolve()
        if out == data_dir or data_dir in out.parents:
            raise SystemExit(f"--out {out} is inside {data_dir}: the live sleeve decides on data/ "
                             "(CLAUDE.md landmine 9); a research copy goes elsewhere.")
    return a


def fetch_actions(TICKERS, GRP):
    """yfinance `Ticker.actions` per name -> (dist, splits). Raises if any name failed."""
    # ---------------------------------------------------------------- 1. actions
    rows = []
    errors = {}
    empty = []
    failed = []   # tickers whose fetch failed after every retry (see the write guard below)

    for i, tk in enumerate(TICKERS, 1):
        got = None
        for attempt in range(3):
            try:
                t = yf.Ticker(tk)
                act = t.actions
                if act is None or len(act) == 0:
                    # fall back to .dividends alone
                    dv = t.dividends
                    if dv is not None and len(dv) > 0:
                        act = dv.to_frame("Dividends")
                        act["Stock Splits"] = 0.0
                    else:
                        act = pd.DataFrame(columns=["Dividends", "Stock Splits"])
                got = act
                break
            except Exception as e:  # network / parse
                errors[tk] = f"{type(e).__name__}: {e}"
                time.sleep(2 + 2 * attempt)
        if got is None:
            print(f"  [{i:2d}/{len(TICKERS)}] {tk:5s} FAILED  {errors.get(tk)}")
            failed.append(tk)
            continue
        if len(got) == 0:
            empty.append(tk)
            print(f"  [{i:2d}/{len(TICKERS)}] {tk:5s} EMPTY (0 actions)")
            continue

        df = got.copy()
        df.index = naive_date(df.index)
        df = df.reset_index()
        df.columns = ["ex_date"] + list(df.columns[1:])
        df["ticker"] = tk
        df["grp"] = GRP.get(tk)
        rows.append(df)
        ndiv = int((df.get("Dividends", pd.Series(dtype=float)) > 0).sum())
        nspl = int((df.get("Stock Splits", pd.Series(dtype=float)) > 0).sum())
        print(f"  [{i:2d}/{len(TICKERS)}] {tk:5s} rows={len(df):4d} div={ndiv:4d} splits={nspl}")
        time.sleep(0.3)

    if not rows:
        raise SystemExit("NO distribution data fetched at all - aborting, nothing written.")
    # The panels below are REPLACED wholesale, so a ticker whose fetch failed would
    # vanish from them -- its whole distribution history deleted, exit 0. Harmless
    # while this was run by hand; since 2026-09-29 the nightly collector runs it
    # unattended (review 2026-09-29), so a failure now aborts with nothing written,
    # and the collector retries next slot.
    if failed:
        raise SystemExit(f"fetch FAILED for {failed} ({ {t: errors.get(t) for t in failed} }) - "
                         f"aborting, nothing written (the panels are replaced whole, so writing "
                         f"now would delete these tickers' history).")

    acts = pd.concat(rows, ignore_index=True)
    for c in ("Dividends", "Stock Splits"):
        if c not in acts.columns:
            acts[c] = 0.0
    acts = acts.rename(columns={"Dividends": "amount", "Stock Splits": "stock_split"})
    acts["amount"] = pd.to_numeric(acts["amount"], errors="coerce").fillna(0.0)
    acts["stock_split"] = pd.to_numeric(acts["stock_split"], errors="coerce").fillna(0.0)

    dist = acts[acts["amount"] > 0].copy()
    dist = dist[["ticker", "grp", "ex_date", "amount", "stock_split"]]
    dist = dist.sort_values(["ticker", "ex_date"]).reset_index(drop=True)

    splits = acts[acts["stock_split"] > 0][["ticker", "ex_date", "stock_split"]].copy()
    splits = splits.sort_values(["ticker", "ex_date"]).reset_index(drop=True)
    return dist, splits, errors, empty


def write_actions(dist, splits, out_dir):
    out_dist = os.path.join(out_dir, "cef_distributions.parquet")
    atomic_write(dist, out_dist)
    print(f"\nwrote {out_dist}  {dist.shape}")
    if len(splits):
        atomic_write(splits, os.path.join(out_dir, "cef_splits.parquet"))
        print(f"wrote cef_splits.parquet  {splits.shape}")


def write_features(dist):
    # ---------------------------------------------------------------- 2. features
    px = pd.read_parquet(os.path.join(CEF, "cef_prices.parquet"))
    px = px[["ticker", "date", "close"]].dropna().sort_values(["ticker", "date"])

    feat = []
    for tk, g in dist.groupby("ticker", sort=True):
        g = g.sort_values("ex_date").reset_index(drop=True).copy()
        g["prev_amount"] = g["amount"].shift(1)
        g["prev_ex_date"] = g["ex_date"].shift(1)
        g["pct_change_vs_prev"] = (g["amount"] / g["prev_amount"] - 1.0) * 100.0
        g["days_since_prev"] = (g["ex_date"] - g["prev_ex_date"]).dt.days
        g["months_since_prev"] = g["days_since_prev"] / 30.436875
        g["is_cut"] = g["amount"] < g["prev_amount"] * 0.99
        g["is_raise"] = g["amount"] > g["prev_amount"] * 1.01
        # trailing 12m total = sum of amounts with ex_date in (t-365d, t]
        amt = g["amount"].values
        dts = g["ex_date"].values.astype("datetime64[D]").astype(int)
        t12 = np.empty(len(g))
        for j in range(len(g)):
            lo = dts[j] - 365
            t12[j] = amt[(dts > lo) & (dts <= dts[j])].sum()
        g["trailing_12m_total"] = t12
        # number of distributions in that same window -> implied frequency
        n12 = np.empty(len(g))
        for j in range(len(g)):
            lo = dts[j] - 365
            n12[j] = ((dts > lo) & (dts <= dts[j])).sum()
        g["n_dists_ttm"] = n12
        feat.append(g)

    f = pd.concat(feat, ignore_index=True)

    # price on ex_date: exact match if traded, else last close on/before ex_date
    f = f.sort_values("ex_date")
    merged = []
    for tk, g in f.groupby("ticker", sort=False):
        p = px[px["ticker"] == tk][["date", "close"]].sort_values("date")
        if len(p) == 0:
            g["price_on_ex_date"] = np.nan
            g["price_date_used"] = pd.NaT
            merged.append(g)
            continue
        g = g.sort_values("ex_date")
        m = pd.merge_asof(
            g, p.rename(columns={"date": "price_date_used", "close": "price_on_ex_date"}),
            left_on="ex_date", right_on="price_date_used", direction="backward",
            tolerance=pd.Timedelta("7D"),
        )
        merged.append(m)

    f = pd.concat(merged, ignore_index=True)
    f["price_is_exact"] = f["price_date_used"] == f["ex_date"]
    f["annualized_yield_pct"] = f["trailing_12m_total"] / f["price_on_ex_date"] * 100.0
    f.loc[~np.isfinite(f["annualized_yield_pct"]), "annualized_yield_pct"] = np.nan

    cols = [
        "ticker", "grp", "ex_date", "amount", "prev_amount", "prev_ex_date",
        "pct_change_vs_prev", "days_since_prev", "months_since_prev",
        "is_cut", "is_raise", "trailing_12m_total", "n_dists_ttm",
        "price_on_ex_date", "price_date_used", "price_is_exact",
        "annualized_yield_pct",
    ]
    f = f[cols].sort_values(["ticker", "ex_date"]).reset_index(drop=True)
    out_feat = os.path.join(CEF, "cef_dist_features.parquet")
    atomic_write(f, out_feat)
    print(f"wrote {out_feat}  {f.shape}")


FIELDS = [
    "symbol", "longName", "shortName", "quoteType", "typeDisp", "legalType",
    "category", "fundFamily", "totalAssets", "netAssets", "marketCap",
    "nonDilutedMarketCap", "sharesOutstanding", "impliedSharesOutstanding",
    "yield", "dividendYield", "dividendRate", "trailingAnnualDividendRate",
    "trailingAnnualDividendYield", "fiveYearAvgDividendYield", "payoutRatio",
    "lastDividendValue", "lastDividendDate", "exDividendDate", "dividendDate",
    "navPrice", "bookValue", "priceToBook", "beta", "beta3Year",
    "fundInceptionDate", "totalDebt", "debtToEquity", "totalExpenseRatio",
    "annualReportExpenseRatio", "netExpenseRatio", "annualHoldingsTurnover",
    "sector", "industry", "exchange", "fullExchangeName", "currency",
    "longBusinessSummary",
]


def write_facts(TICKERS, GRP, errors, empty):
    # ---------------------------------------------------------------- 3. facts
    raw_info = {}
    fact_rows = []
    info_err = {}
    for i, tk in enumerate(TICKERS, 1):
        info = None
        for attempt in range(3):
            try:
                info = yf.Ticker(tk).info
                break
            except Exception as e:
                info_err[tk] = f"{type(e).__name__}: {e}"
                time.sleep(2 + 2 * attempt)
        if not info:
            print(f"  info [{i:2d}] {tk:5s} FAILED {info_err.get(tk)}")
            raw_info[tk] = {}
            fact_rows.append({"ticker": tk, "grp": GRP.get(tk)})
            continue
        raw_info[tk] = info
        r = {"ticker": tk, "grp": GRP.get(tk)}
        for fld in FIELDS:
            v = info.get(fld, None)
            if isinstance(v, str):
                v = v.replace("\n", " ").strip()
                if fld == "longBusinessSummary":
                    v = v[:400]
            r[fld] = v
        # leverage hints scraped from the business summary text
        summ = (info.get("longBusinessSummary") or "").lower()
        r["summary_mentions_leverage"] = ("leverage" in summ) or ("leveraged" in summ)
        fact_rows.append(r)
        print(f"  info [{i:2d}/{len(TICKERS)}] {tk:5s} n_fields={len(info)} quoteType={info.get('quoteType')}")
        time.sleep(0.3)

    facts = pd.DataFrame(fact_rows)

    # STAMP THE SNAPSHOT. Without this column cef_facts.csv looks like a fact table
    # and is not one: it is a single yfinance .info snapshot taken on one afternoon,
    # with no history. Joining it to the 27-year price/NAV panel applies TODAY's
    # fund attributes to every historical date -- a look-ahead error that produces
    # no error message. Measured 2026-09-10 on the 2026-07-31 snapshot: 13 of its
    # 46 columns are 100% null (netAssets, netExpenseRatio, fundFamily,
    # fundInceptionDate among them) and quoteType/typeDisp/sector/industry are
    # constant across all 44 rows, so most of what looks like per-fund data is not.
    # (ops/doctor.py, now deleted, warned until this column existed.) See work order perfund/F1 at git tag pre-clean-slate,
    # which supersedes this file with a dated characteristics panel.
    facts.insert(0, "fetched_at", pd.Timestamp.utcnow().tz_localize(None).isoformat(timespec="seconds"))

    out_facts = os.path.join(CEF, "cef_facts.csv")
    atomic_write(facts, out_facts)
    print(f"wrote {out_facts}  {facts.shape}  (fetched_at stamped; this is a SNAPSHOT,")
    print("  not a panel -- do not join it to history without reading its header note)")

    with open(os.path.join(CEF, "_raw_info.json"), "w") as fh:
        json.dump({k: {kk: (str(vv) if not isinstance(vv, (int, float, str, bool, type(None))) else vv)
                       for kk, vv in v.items()} for k, v in raw_info.items()}, fh, indent=1)

    diag = {
        "n_universe": len(TICKERS),
        "fetch_errors": errors,
        "empty_action_tickers": empty,
        "info_errors": info_err,
    }
    with open(os.path.join(CEF, "_fetch_diagnostics.json"), "w") as fh:
        json.dump(diag, fh, indent=1)


def c4_universe_frame():
    """C4's 74 frozen funds as the (ticker, grp) frame this script fetches, grp
    = the frozen family (the families panels' own `grp`), sorted by ticker."""
    from scripts.cef import data_books
    fam = data_books.c4_universe()
    return pd.DataFrame({"ticker": sorted(fam), "grp": [fam[t] for t in sorted(fam)]})


def main(argv=None) -> int:
    a = parse_args(argv)
    c4 = a.data_book == "c4"
    if c4:
        from scripts.cef import data_books
        c4_dir = str(data_books.C4_DIR)
        if a.out is None and not os.path.isdir(c4_dir):
            raise SystemExit(f"--data-book c4: {c4_dir} does not exist; seed it first "
                             f"(scripts/cef/data_books.py, SEED), nothing fetched")
        uni, uni_name = c4_universe_frame(), data_books.C4_UNIVERSE.name
    else:
        uni = pd.read_csv(os.path.join(CEF, "cef_universe.csv"))
        uni_name = "cef_universe.csv"
    if a.tickers is not None:
        want = [t.strip() for t in a.tickers.split(",") if t.strip()]
        unknown = sorted(set(want) - set(uni["ticker"]))
        if not want or unknown:
            raise SystemExit(f"--tickers: {unknown or 'no names'} not in {uni_name}")
        uni = uni[uni["ticker"].isin(want)]          # the other names are never fetched
    TICKERS = uni["ticker"].tolist()
    GRP = dict(zip(uni["ticker"], uni["grp"]))
    print(f"universe: {len(TICKERS)} tickers")

    dist, splits, errors, empty = fetch_actions(TICKERS, GRP)
    if a.out is not None:
        os.makedirs(a.out, exist_ok=True)
        write_actions(dist, splits, a.out)
        print("\nDONE (--out: actions panels only; features and facts are written only to data/cef)")
        return 0
    if c4:
        # C4's own panel, replaced whole like the core's; nothing else is
        # written (module docstring, --data-book c4).
        write_actions(dist, splits, c4_dir)
        print("\nDONE (--data-book c4: actions panels only)")
        print("empty:", empty)
        print("errors:", list(errors))
        return 0
    write_actions(dist, splits, CEF)
    write_features(dist)
    write_facts(TICKERS, GRP, errors, empty)
    print("\nDONE")
    print("empty:", empty)
    print("errors:", list(errors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
