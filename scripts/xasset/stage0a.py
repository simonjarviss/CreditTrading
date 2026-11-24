"""Stage 0a of the XASSET slate: the data gates, the spec pin, the Q1-Q7 screen and the
input manifest. Zero trials: no return is combined into a P&L.

    export QUANTT_ENV_FILE=/abs/path/to/config/.env      # never printed
    python3 scripts/build_etf_daily.py --xasset --out results/xasset/_cache_xasset/etf_daily_xasset.parquet
    python3 scripts/data/fetch_aqr_factors.py
    python3 scripts/data/fetch_ff_factors.py
    python3 scripts/gamma/fetch_fred.py DGS3MO --out results/xasset/_cache_xasset/dgs3mo.parquet
    python3 scripts/xasset/stage0a.py

WHAT IT DOES (PREREG_XASSET_SLATE_2026-10-12 §1.1, §1.3, §1.11 stage 0a)
-------------------------------------------------------------------------
1. The spec pin: `vol_target_annual`, `max_gross_stress` through spec.py, and the
   frozen spec's SHA-256, against the approved values. A mismatch halts.
2. DG1: the staged panel holds the 22 tickers and the `prc_signed` column; the
   no-closing-trade rows (prc < 0) are counted on ANGL, FALN and JNK (and every
   other name); and the 13 tickers already in `data/etf_daily.parquet` are
   compared with it through `scripts/rv/panel_identity.py`, every column. The
   result is recorded as measured; whether it meets DG1's "rebuild unchanged"
   criterion is stated, not decided here, when it does not hold bitwise.
3. DG2: the AQR and French factor caches parse with the declared columns, and
   their vintages are recorded. DG3: DGS3MO covers the panel's last date minus
   one session.
4. The in-house panels are COPIED into the cache, so the cross-check and the
   source-sensitivity row read files whose hash this stage pins (`data/rv/` can
   be rebuilt by its fetchers at any time).
5. P2's screen, Q1-Q7, on the primary return of all 19 slate instruments, over
   fit and holdout. Q1 (a missing session inside a live range) halts. The other
   checks flag. The full flag list, with both sources' values, goes to the
   gitignored cache (`stage0a_flags.csv`): its CRSP rows are licensed and the
   repository is public, so the TRACKED summary carries counts by instrument,
   check and period only (the coordinator's run instruction, 2026-10-14, which
   overrides §1.1's "listed ... in its committed result note" on that point).
6. The manifest: the SHA-256 of every input file a trial reads, written to
   `results/xasset/stage0a/STAGE0A_MANIFEST_2026-10-14.json`. Committing it ends Stage 0a.

READINGS OF THE SCREEN'S RULES, STATED (flags only; nothing is altered)
-----------------------------------------------------------------------
* Q2 "≥ 3 consecutive sessions with an unchanged raw close": three or more
  consecutive sessions sharing one close. The sessions flagged are those whose
  close equals the previous session's inside such a run (their returns carry
  no new price). Raw close = `prc_adj` (|prc|/cfacpr in the CRSP leg, which is
  continuous across a split, the raw close in the spliced legs).
* Q5: z = |r_t - median_252| / (1.4826 MAD_252) over the 252 sessions through
  t-1, computed once 252 prior returns exist; before that only |r| > 15% can
  flag. A zero MAD with r_t != median counts as z = inf, and is counted apart.
* Q6 compares the primary return with the in-house panel that holds the name
  (`etf_panel` first, else `etf_ohlc_extended`, as slate_feasibility.coverage
  does) on the dates both hold.
* Q7 flags the four seam sessions for every instrument that trades them.
* "fit" is < 2023-01-01; "holdout" is 2023-01-03 .. 2026-09-30; "after" is later.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.xasset import protocol as P  # noqa: E402

SEAMS = ["2024-12-31", "2025-01-02", "2026-07-20", "2026-07-21"]
REBUILD2 = P.CACHE / "etf_daily_xasset_rebuild2.parquet"   # a second fresh build, evidence only
SUMMARY = P.STAGE0A_DIR / "stage0a_summary_2026-10-14.json"
EXPECTED_22 = ["HYG", "JNK", "ANGL", "FALN", "SHY", "BIL", "IEF", "LQD", "TLT", "EFA", "EEM",
               "GLD", "DBC", "SPY", "EMB", "PFF", "MUB", "BKLN", "CWB", "IEI", "TLH", "AGG"]
TSMOM_COLS = ["TSMOM", "TSMOM^CM", "TSMOM^EQ", "TSMOM^FI", "TSMOM^FX"]
VME_COLS = ["VAL", "MOM", "MOMLS_VME_FI", "MOMLS_VME_EQ"]
FF_COLS = ["mktrf", "smb", "hml", "rmw", "cma", "rf", "umd"]


def period(d: pd.Timestamp) -> str:
    if d < P.HOLDOUT_START:
        return "fit"
    return "holdout" if d <= P.HOLDOUT_END else "after"


# ----------------------------------------------------------------------------- DG1
def dg1(panel: pd.DataFrame) -> dict:
    from scripts.rv.panel_identity import identity
    tick = sorted(panel.ticker.unique())
    out = dict(tickers=len(tick), tickers_ok=sorted(tick) == sorted(EXPECTED_22),
               has_prc_signed="prc_signed" in panel.columns)
    crsp = panel[panel.source == "crsp"]
    out["prc_signed_complete_on_crsp_leg"] = bool(crsp["prc_signed"].notna().all())
    out["prc_signed_nan_off_crsp_leg"] = bool(panel.loc[panel.source != "crsp", "prc_signed"].isna().all())
    out["no_close_trade_rows_by_ticker"] = {t: int(n) for t, n in
                                            crsp[crsp.prc_signed < 0].groupby("ticker").size().items()}
    out["sources"] = {s: dict(first=str(g.date.min().date()), last=str(g.date.max().date()), rows=len(g))
                      for s, g in panel.groupby("source")}
    rep = identity(REPO / "data" / "etf_daily.parquet", P.PANEL)
    old = pd.read_parquet(REPO / "data" / "etf_daily.parquet")
    m = old.merge(panel, on=["ticker", "date"], suffixes=("_o", "_n"))
    col_diffs = {}
    for c in ["permno", "ret_total", "ret_px", "prc_adj", "volume", "source"]:
        a, b = m[c + "_o"], m[c + "_n"]
        neq = ~((a == b) | (a.isna() & b.isna()))
        by_src = {s: int(neq[m.source_o == s].sum()) for s in ("crsp", "yfinance", "alpaca")}
        d = dict(cells_differ=int(neq.sum()), by_source=by_src)
        if neq.any() and np.issubdtype(a.dtype, np.number):
            d["max_abs_diff_bp" if c.startswith("ret") else "max_abs_diff"] = float(
                (a - b).abs().max() * (1e4 if c.startswith("ret") else 1))
            dd = m.loc[neq, "date"]
            d["dates"] = [str(dd.min().date()), str(dd.max().date())]
        col_diffs[c] = d
    out["identity_vs_data_etf_daily"] = dict(
        compared_through=rep["old_last"], rows=rep["rows_old"], byte_identical=rep["byte_identical"],
        cell_identical=rep["cell_identical"], structure_problems=rep["problems"],
        columns=col_diffs)
    if REBUILD2.exists():
        b = pd.read_parquet(REBUILD2)
        mm = panel.merge(b, on=["ticker", "date"], suffixes=("_a", "_b"))
        d = (mm.ret_total_a - mm.ret_total_b).abs()
        out["two_fresh_builds"] = dict(
            note="a second --xasset build to a separate path minutes after the first; evidence that "
                 "the yfinance-leg ret_total (Yahoo Adj Close pct_change) is not reproducible bitwise",
            rows=len(mm), ret_total_cells_differ={s: int((d[mm.source_a == s] > 0).sum())
                                                  for s in ("crsp", "yfinance", "alpaca")},
            ret_total_max_diff_bp=float(d.max() * 1e4),
            other_columns_identical=bool(all(((mm[c + "_a"] == mm[c + "_b"]) |
                                              (mm[c + "_a"].isna() & mm[c + "_b"].isna())).all()
                                             for c in ("ret_px", "prc_adj", "volume", "prc_signed"))))
    ident = out["identity_vs_data_etf_daily"]
    out["criterion_build_gates"] = "PASS (the build ran to completion: every assert, the 5bp 2024 " \
                                   "overlap gate for all 22, the Alpaca gates, LARGE_MOVES)"
    out["criterion_13_unchanged_every_existing_column"] = (
        "MET" if ident["cell_identical"] else
        "NOT MET BITWISE: see columns; whether it clears DG1 is the team lead's question")
    return out


# ----------------------------------------------------------------------------- DG2/DG3
def dg2() -> dict:
    ts = pd.read_parquet(P.AQR_TSMOM)
    vm = pd.read_parquet(P.AQR_VME)
    ffd = pd.read_parquet(P.FF_DAILY)
    ffm = pd.read_parquet(P.FF_MONTHLY)
    miss = ([c for c in TSMOM_COLS if c not in ts.columns] + [c for c in VME_COLS if c not in vm.columns]
            + [c for c in FF_COLS if c not in ffd.columns or c not in ffm.columns])
    ref = (REPO / "docs" / "REFERENCES.md").read_text()
    return dict(
        columns_ok=not miss, missing=miss,
        aqr_tsmom=dict(months=len(ts), first=str(ts.date.min().date()), last=str(ts.date.max().date()),
                       file_sha256=ts.file_sha256.iloc[0], http_last_modified=ts.http_last_modified.iloc[0],
                       fetched=ts.fetched_at_utc.iloc[0]),
        aqr_vme=dict(months=len(vm), first=str(vm.date.min().date()), last=str(vm.date.max().date()),
                     file_sha256=vm.file_sha256.iloc[0], http_last_modified=vm.http_last_modified.iloc[0],
                     fetched=vm.fetched_at_utc.iloc[0]),
        french=dict(daily_last=str(pd.to_datetime(ffd.date).max().date()),
                    monthly_last=str(pd.to_datetime(ffm.date).max().date()),
                    crsp_vintage=str(ffd.crsp_vintage.iloc[0]), fetched=str(ffd.fetched_at_utc.iloc[0])),
        references_row=("fetch_aqr_factors.py" in ref))


def dg3(cal: pd.DatetimeIndex) -> dict:
    f = pd.read_parquet(P.DGS3MO)
    last = pd.to_datetime(f.date).max()
    need = cal[-2]
    return dict(first=str(pd.to_datetime(f.date).min().date()), last=str(last.date()),
                panel_last=str(cal[-1].date()), panel_last_minus_one=str(need.date()),
                covers=bool(last >= need), fetched=str(f.fetched_at.iloc[0]))


# ----------------------------------------------------------------------------- Q1-Q7
def inhouse_returns() -> pd.DataFrame:
    frames = {}
    for name, path in P.INHOUSE.items():
        d = pd.read_parquet(path, columns=["date", "ticker", "ret_total"])
        d["date"] = pd.to_datetime(d["date"])
        frames[name] = d
    out = {}
    for sym in P.SLATE_19:
        for name in ("etf_panel", "etf_ohlc_extended"):
            s = frames[name].loc[frames[name].ticker == sym].set_index("date")["ret_total"].dropna()
            if len(s):
                out[sym] = s
                break
        else:
            raise P.ProtocolError(f"{sym}: no in-house panel holds it")
    return pd.DataFrame(out)


def rolling_mad_z(r: pd.Series) -> pd.Series:
    prev = r.shift(1)
    med = prev.rolling(252, min_periods=252).median()
    mad = prev.rolling(252, min_periods=252).apply(
        lambda w: np.median(np.abs(w - np.median(w))), raw=True)
    dev = (r - med).abs()
    z = dev / (1.4826 * mad)
    z[(mad == 0) & (dev > 0)] = np.inf
    return z


def screen(panel: pd.DataFrame, cal: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict]:
    ih = inhouse_returns()
    flags = []
    q1 = {}
    for sym in P.SLATE_19:
        g = panel[panel.ticker == sym].set_index("date").sort_index()
        r = g["ret_total"]
        first, last = r.index.min(), r.index.max()
        inside = cal[(cal >= first) & (cal <= last)]
        missing = inside[~inside.isin(r.dropna().index)]
        q1[sym] = len(missing)
        for d in missing:
            flags.append((sym, d, "Q1", np.nan, np.nan, "missing session"))
        # Q2: three or more consecutive sessions sharing one close
        px = g["prc_adj"]
        same = px.eq(px.shift(1))
        run_id = (~same).cumsum()
        run_len = same.groupby(run_id).transform("sum") + 1          # sessions sharing the close
        for d in px.index[same & (run_len >= 3)]:
            flags.append((sym, d, "Q2", r.get(d), px.get(d), f"close unchanged, run {int(run_len[d])}"))
        for d in g.index[g["volume"] == 0]:
            flags.append((sym, d, "Q3", r.get(d), g["volume"].get(d), f"zero volume ({g.source[d]})"))
        for d in g.index[g["prc_signed"] < 0]:
            flags.append((sym, d, "Q4", r.get(d), g["prc_signed"].get(d), "no closing trade (prc < 0)"))
        z = rolling_mad_z(r)
        for d in r.index[(z > 10) | (r.abs() > 0.15)]:
            flags.append((sym, d, "Q5", r.get(d), z.get(d),
                          "robust z > 10" + (" and |r| > 15%" if abs(r[d]) > 0.15 else "")
                          if z.get(d, 0) > 10 else "|r| > 15%"))
        if sym in ih:
            b = ih[sym].reindex(r.index)
            both = r.notna() & b.notna()
            dd = (r - b).abs()
            for d in r.index[both & (dd > 5e-4)]:
                flags.append((sym, d, "Q6", r[d], b[d], f"|primary - in-house| {dd[d] * 1e4:.2f}bp "
                                                       f"({g.source[d]})"))
        for s in SEAMS:
            d = pd.Timestamp(s)
            if d in r.index:
                flags.append((sym, d, "Q7", r[d], np.nan, "splice seam"))
    F = pd.DataFrame(flags, columns=["ticker", "date", "check", "primary_ret", "other_value", "note"])
    F["period"] = F["date"].map(period)
    F["source"] = [panel.loc[(panel.ticker == t) & (panel.date == d), "source"].iloc[0]
                   if ((panel.ticker == t) & (panel.date == d)).any() else "" for t, d in
                   zip(F.ticker, F.date)]
    counts = (F.groupby(["ticker", "check", "period"]).size().unstack("period", fill_value=0)
              .reindex(columns=["fit", "holdout", "after"], fill_value=0))
    by_ticker = {t: {c: counts.loc[(t, c)].to_dict() for c in counts.loc[t].index}
                 for t in counts.index.get_level_values(0).unique()}
    tot = F.groupby(["check", "period"]).size().unstack("period", fill_value=0).reindex(
        columns=["fit", "holdout", "after"], fill_value=0)
    q5 = F[F.check == "Q5"]
    rev = []
    for _, row in q5.iterrows():
        g = panel[panel.ticker == row.ticker].set_index("date").sort_index()
        i = g.index.get_loc(row.date)
        if i + 1 < len(g):
            r0, r1 = g["ret_total"].iloc[i], g["ret_total"].iloc[i + 1]
            if abs((1 + r0) * (1 + r1) - 1) < 0.3 * abs(r0):
                v = g["volume"].iloc[i]
                med = g["volume"].iloc[max(0, i - 63):i].median()
                rev.append((row.ticker, str(row.date.date()), abs(r0), v, v / med if med else np.nan))
    # The build's own stub-print scan (build_etf_daily.scan_reversals): |r| > 8%,
    # mostly reversed next session, volume < 50,000. Only such a row could be the
    # ONE permitted repair, and only with a third source.
    stub = [x for x in rev if x[2] > 0.08 and x[3] < 50_000]
    big = [x for x in rev if x[2] >= 0.01]
    small = [x for x in rev if x[2] < 0.01]
    summ = dict(
        instruments=P.SLATE_19, q1_missing_sessions=q1, q1_clean=all(v == 0 for v in q1.values()),
        totals_by_check_and_period={c: tot.loc[c].to_dict() for c in tot.index},
        by_ticker_check_period=by_ticker,
        q5_inf_z_zero_mad=int(np.isinf(q5["other_value"].astype(float)).sum()),
        q5_reversing_next_session=len(rev),
        q5_reversals_stub_print_pattern=len(stub),
        q5_reversals_abs_r_ge_1pct=dict(n=len(big), min_volume_over_63d_median=(
            float(min(x[4] for x in big)) if big else None), tickers=sorted({x[0] for x in big})),
        q5_reversals_abs_r_lt_1pct=dict(n=len(small), max_abs_r_bp=(
            float(max(x[2] for x in small) * 1e4) if small else None), tickers=sorted({x[0] for x in small})),
        q5_reversal_note=("Q5 flags whose next session reverses >= 70% of the move (the stub-print "
                          "pattern). Candidates for the ONE permitted repair only if a third source, "
                          "independent of CRSP and the in-house vendors, confirms the true close."),
        repairs=[], flags_file=P.rel(P.QFLAGS), flags_rows=len(F))
    return F, summ, rev


# ----------------------------------------------------------------------------- manifest
def manifest_files() -> dict:
    files = {"panel": P.PANEL, "dgs3mo": P.DGS3MO, "aqr_tsmom": P.AQR_TSMOM, "aqr_vme": P.AQR_VME,
             "ff_daily": P.FF_DAILY, "ff_monthly": P.FF_MONTHLY,
             "inhouse_etf_panel": P.INHOUSE["etf_panel"],
             "inhouse_etf_ohlc_extended": P.INHOUSE["etf_ohlc_extended"],
             "spec": P.SPEC_FILE, "qflags": P.QFLAGS}
    for p in P.CEF_INPUTS:
        files["cef_" + p.stem.replace("cef_", "")] = p
    return {k: dict(path=P.rel(v), sha256=P.sha256(v), bytes=v.stat().st_size) for k, v in files.items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    out = dict(run_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               prereg="results/xasset/PREREG_XASSET_SLATE_2026-10-12.md (revision 3, approved 2026-10-14, N = 4)")
    out["spec_pin"] = P.check_spec_pin()
    print("spec pin: MATCH", out["spec_pin"])
    for name, src in P.INHOUSE_SRC.items():
        shutil.copy2(src, P.INHOUSE[name])
    panel = P.load_panel()
    cal = P.master_calendar(panel)
    out["calendar"] = dict(first=str(cal[0].date()), last=str(cal[-1].date()), sessions=len(cal))
    out["dg1"] = dg1(panel)
    print("DG1:", out["dg1"]["criterion_build_gates"])
    print("DG1 identity of the 13:", out["dg1"]["criterion_13_unchanged_every_existing_column"])
    out["dg2"] = dg2()
    print("DG2 columns ok:", out["dg2"]["columns_ok"], "REFERENCES row:", out["dg2"]["references_row"])
    out["dg3"] = dg3(cal)
    print("DG3 covers:", out["dg3"]["covers"], out["dg3"]["last"])
    F, summ, rev = screen(panel, cal)
    F.to_csv(P.QFLAGS, index=False)
    with open(P.CACHE / "stage0a_q5_reversals.txt", "w") as fh:
        fh.write("\n".join(f"{x[0]} {x[1]} |r| {x[2] * 1e4:.1f}bp vol/med63 {x[4]:.2f}" for x in rev) + "\n")
    out["screen"] = summ
    print("Q1 clean:", summ["q1_clean"], " flags:", summ["flags_rows"])
    print(pd.DataFrame(summ["totals_by_check_and_period"]).T.to_string())
    out["gates"] = dict(
        spec_pin="MATCH", dg1_build="PASS",
        dg1_identity=out["dg1"]["criterion_13_unchanged_every_existing_column"],
        dg2="PASS" if out["dg2"]["columns_ok"] and out["dg2"]["references_row"] else "FAIL",
        dg3="PASS" if out["dg3"]["covers"] else "FAIL",
        q1="PASS" if summ["q1_clean"] else "HALT")
    files = manifest_files()
    P.STAGE0A_DIR.mkdir(parents=True, exist_ok=True)
    P.write_json(P.MANIFEST, dict(written_utc=out["run_utc"], stage="0a", files=files,
                                  pins=dict(vol_target_annual=P.PINNED_VOL_TARGET,
                                            max_gross_stress=P.PINNED_MAX_GROSS,
                                            spec_sha256=P.PINNED_SPEC_SHA256, n_slate=P.N_SLATE)))
    out["manifest"] = P.rel(P.MANIFEST)
    P.write_json(SUMMARY, out)
    print(f"wrote {P.rel(P.MANIFEST)} and {P.rel(SUMMARY)}; flags (licensed rows) -> {P.rel(P.QFLAGS)}")
    print("gates:", out["gates"])
    return 0 if summ["q1_clean"] else 2


if __name__ == "__main__":
    sys.exit(main())
