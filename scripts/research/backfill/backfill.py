"""Backfill past trials' daily FIT-PERIOD P&L into the trial registry, after each
re-run reproduces the trial's committed fit exactly.

    python3 -m scripts.research.backfill.backfill stage            # copy the trials' gitignored caches in (read-only source)
    python3 -m scripts.research.backfill.backfill run              # re-run, check, print bar inputs; stores nothing
    python3 -m scripts.research.backfill.backfill run --record     # the same, then registry.record() each reproduced series
    python3 -m scripts.research.backfill.backfill census           # the census table (markdown)

WHY THIS EXISTS (2026-10-28)
----------------------------
Team lead, 2026-10-27 (`docs/SYSTEM.md` §5, row "Trial P&L series"): **backfill what
is reproducible.** The paper's deflated-Sharpe bar (effective N, measured V[SR]) may
gate a counter only once every canonical trial on it has a stored series
(`registry.bar_inputs(counter)["paper_bar_may_gate"]`). Until then the desk's
sqrt(2 ln N) gates. `census.py` lists every canonical trial on EVENTS, XASSET and
CEF; this file re-runs the ones whose committed fit path still runs offline, and
records them.

WHAT "REPRODUCES" MEANS HERE. Each rebuild calls the trial's OWN functions in the
order its fit entry point calls them, stops at the series, and compares every
figure it can recompute with the trial's committed fit JSON at 1e-9 (in practice
they are bit-identical). Where the trial cached its series (XASSET, C4, C5), the
rebuilt series is also compared with that cache value for value. A mismatch
raises; nothing is stored. A second method is printed beside it, never deciding:
the Newey-West t from `scripts/research/inference.py` on the rebuilt series
against the trial's committed t (the inference rule: statistics come from that
module).

FIT ONLY, AND NEVER THE 2023 HOLDOUT. Every stored series is asserted to end
before 2023-01-01 and to hold no NaN (`assert_fit_only`).
- EVENTS runs `scripts/research/reopen_book/extract_trial_series.py` in a child
  process on each trial's own worktree. It reads CRSP through `crsp_events.daily`
  (date < 2023-01-01, asserted there), refuses a cache miss, and installs netguard.
  E1's holdout has never been opened, and nothing here reads a 2023+ return for it.
- C5 reads its frozen copy, which was cut at 2022-12-30 when it was frozen and is
  re-verified against its committed hashes.
- C4's fit builds targets on the FULL families panel and slices them afterwards
  (its docstring, "THE HOLDOUT"). Here the price, NAV and actions panels and the
  CRSP extract are cut at 2022-12-30 ON READ (a parquet filter, so no 2023+ row is
  materialised) before anything runs. The nine frozen funds with no row before 2023
  then have no column, so their targets enter as zero columns, which is what the
  full-panel run gives them before 2023; the reproduction below proves it.
- XASSET's holdouts were opened once already (2026-10-14/15). Its panel loader
  reads the whole staged file, but `runner.load` truncates before any statistic
  and only the fit window is stored, for consistency with the other counters.
- The v7 check (CEF-48..50, REPORT ONLY) cuts the four CEF panels on read too.

OFFLINE. `ops.netguard` refuses every socket in this process and in the EVENTS
child. No broker, no R2, no network: a cache that is missing raises naming it.

ONE VARIANT PER TRIAL. The registry clusters over variants for the effective N.
Each trial stores the one series its verdict was judged on (the sized sleeve for
XASSET, the tradable sleeve for EVENTS, G for C5, the declared book for C4). The
capped, price-return or report-only views are not configurations the trial
evaluated as candidates, and near-copies would distort rho_bar.

E1'S TURNOVER. The committed `harness_turn` (14.40/yr) is the turnover of the raw,
unsized H beside P&L on the sized, capped Ht
(`results/research/REOPEN_BOOK_NAVTENDER_E1_2026-10-28.md`). The P&L is right. The
params store the event turnover the trial charged costs on, the harness turnover
measured on Ht itself, and the committed figure labelled as mis-scaled.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research.backfill import census as C  # noqa: E402

HOLDOUT_START = pd.Timestamp("2023-01-01")
FIT_END = pd.Timestamp("2022-12-30")
TOL = 1e-9
OUT = REPO / "results" / "research" / "backfill"
CACHE = OUT / "_cache_backfill"                    # gitignored (results/**/_cache_*)
EXTRACTOR = REPO / "scripts" / "research" / "reopen_book" / "extract_trial_series.py"

# The trials' gitignored caches, copied in by `stage` from the worktree each trial ran
# in. Every copy is then verified by the trial's own check (the XASSET manifest, the C5
# freeze record) or by the reproduction itself (C4's CRSP extract).
STAGE = {
    "trial-xasset": [f"results/xasset/_cache_xasset/{f}" for f in (
        "etf_daily_xasset.parquet", "dgs3mo.parquet", "aqr_tsmom_monthly.parquet", "aqr_vme_monthly.parquet",
        "x1_fit_series.parquet", "x2_fit_series.parquet", "x3_fit_series.parquet", "x4_fit_series.parquet")]
    + ["results/cef/w4/_cache_w4/ff5_umd_daily.parquet", "results/cef/w4/_cache_w4/ff5_umd_monthly.parquet"],
    "trial-c5": ["results/cef/c5/_cache_c5_frozen",
                 ("results/cef/c5/_cache_c5_fit/G_wide.parquet", "results/cef/c5/_cache_c5_ref/G_wide.parquet")],
    "trial-c4": ["results/cef/c4/_cache_c4/crsp_ret_families.parquet",
                 "results/cef/c4/_cache_c4/c4_fit_pnl_2026-10-14.parquet"],
}
C5_REF = REPO / "results" / "cef" / "c5" / "_cache_c5_ref" / "G_wide.parquet"
C4_REF = REPO / "results" / "cef" / "c4" / "_cache_c4" / "c4_fit_pnl_2026-10-14.parquet"
XASSET_MODULES = {"X1": "x1_credit_trend", "X2": "x2_rebalancing", "X3": "x3_month_end", "X4": "x4_multi_trend"}


class NotReproduced(RuntimeError):
    """A re-run does not reproduce the trial's committed figures: the series is not that trial's."""


# ============================================================ plumbing

def main_tree() -> Path:
    """The main checkout, the parent of every `.claude/worktrees/<name>`."""
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout.strip()
    return Path(common).parent


def trial_tree(name: str) -> Path:
    p = main_tree() / ".claude" / "worktrees" / name
    if not p.is_dir():
        raise FileNotFoundError(f"the trial worktree {p} is missing; its gitignored caches live only there")
    return p


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def copy_verified(src: Path, dst: Path) -> str:
    """Copy one file into this tree. An existing destination must be byte-identical: a
    stale or edited cache is never silently replaced."""
    if not src.is_file():
        raise FileNotFoundError(f"{src} is missing in the trial worktree")
    if dst.exists():
        if _sha(dst) != _sha(src):
            raise FileExistsError(f"{dst} exists and differs from {src}; remove it by hand if it is stale")
        return "present"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return "copied"


def stage() -> dict:
    """Copy each trial's gitignored inputs from its worktree. The source is only read."""
    done = {}
    for tree, items in STAGE.items():
        root = trial_tree(tree)
        for it in items:
            s_rel, d_rel = it if isinstance(it, tuple) else (it, it)
            src = root / s_rel
            files = sorted(p for p in src.rglob("*") if p.is_file()) if src.is_dir() else [src]
            if src.is_dir() and not files:
                raise FileNotFoundError(f"{src} is empty")
            for f in files:
                rel = Path(d_rel) / f.relative_to(src) if src.is_dir() else Path(d_rel)
                done[str(rel)] = copy_verified(f, REPO / rel)
    for rel in done:
        ign = subprocess.run(["git", "check-ignore", "-q", rel], cwd=REPO).returncode
        if ign != 0:
            raise RuntimeError(f"{rel} is not gitignored; licensed or vendor data must never be tracked")
    return done


def cut_parquet(src: Path, dst: Path, col: str = "date", end: pd.Timestamp = FIT_END,
                allow_empty: bool = False) -> dict:
    """Write `src`'s rows with `col` <= `end` to `dst`, filtering ON READ so no later row
    is ever materialised. Asserts the result and returns what was kept. An empty cut
    raises unless `allow_empty` (an event file, such as splits, can have no fit-period
    row; a price or NAV panel cannot)."""
    d = pd.read_parquet(src, filters=[(col, "<=", end)])
    if not len(d):
        if not allow_empty:
            raise ValueError(f"{src.name}: no row on or before {end.date()}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        d.to_parquet(dst)
        return {"rows": 0, "last": None}
    last = pd.to_datetime(d[col]).max()
    if last > end:
        raise AssertionError(f"{src.name}: the filtered read returned {last.date()} > {end.date()}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    d.to_parquet(dst)
    return {"rows": int(len(d)), "last": str(last.date())}


def assert_fit_only(pnl: pd.Series, label: str) -> None:
    if not isinstance(pnl.index, pd.DatetimeIndex):
        raise TypeError(f"{label}: the series is not indexed by dates")
    if pnl.index.max() >= HOLDOUT_START:
        raise AssertionError(f"{label}: the series reaches {pnl.index.max().date()}, inside the 2023 holdout")
    if pnl.isna().any():
        raise ValueError(f"{label}: the series holds {int(pnl.isna().sum())} NaN")


def plain(o):
    """JSON-plain: numpy scalars to Python, tuples to lists, NaN/inf to None (the
    convention the trials' own JSON writers use)."""
    if isinstance(o, dict):
        return {str(k): plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [plain(v) for v in o]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return float(o) if math.isfinite(float(o)) else None
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    return o


def _leaves(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _leaves(v, f"{path}.{k}" if path else str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _leaves(v, f"{path}[{i}]")
    else:
        yield path, o


def compare(got, want, label: str, tol: float = TOL) -> dict:
    """Every leaf of `want` must be in `got` and equal: numbers within `tol`, everything
    else exactly. Raises NotReproduced naming each mismatch."""
    g, w = dict(_leaves(plain(got))), dict(_leaves(plain(want)))
    bad, diffs = [], []
    for k, wv in w.items():
        if k not in g:
            bad.append((k, "missing", wv))
            continue
        gv = g[k]
        num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
        if isinstance(gv, bool) or isinstance(wv, bool):     # True == 1 in Python; a flag is not a number
            if type(gv) is not type(wv) or gv != wv:
                bad.append((k, gv, wv))
        elif num(gv) and num(wv):
            d = abs(float(gv) - float(wv))
            diffs.append(d)
            if not d <= tol:
                bad.append((k, gv, wv))
        elif gv != wv:
            bad.append((k, gv, wv))
    if bad:
        raise NotReproduced(f"{label}: {len(bad)} of {len(w)} committed figures do not reproduce, "
                            f"e.g. {bad[:5]}")
    if not w:
        raise NotReproduced(f"{label}: nothing to compare")
    return {"compared": len(w), "max_abs_diff": max(diffs) if diffs else 0.0}


def same_series(a: pd.Series, b: pd.Series, label: str) -> None:
    if not (a.index.equals(b.index) and np.array_equal(a.to_numpy(dtype=float), b.to_numpy(dtype=float))):
        raise NotReproduced(f"{label}: the rebuilt series differs from the trial's cached one")


def second_method(pnl: pd.Series, committed_t: float, lags: int, what: str) -> dict:
    """inference.newey_west_t on the rebuilt series beside the trial's committed t. Reported."""
    from scripts.research.inference import newey_west_t
    t = float(newey_west_t(pnl.to_numpy(dtype=float), lags))
    return {"what": what, "lags": int(lags), "inference_nw_t": t, "committed_t": float(committed_t),
            "abs_diff": abs(t - float(committed_t))}


def _rebuilt(counter, trial, variant, pnl, params, check, second, note) -> dict:
    assert_fit_only(pnl, f"{counter}/{trial}")
    return dict(counter=counter, trial=trial, variant=variant, pnl=pnl.astype(float), params=plain(params),
                check=plain(check), second=plain(second), note=note)


# ============================================================ EVENTS

def _events(name: str, trial: str, variant: str) -> dict:
    tree = trial_tree(f"trial-events-{name}")
    CACHE.mkdir(parents=True, exist_ok=True)
    # -I: isolated (no caller env, no script dir on the path); -B: no bytecode written into the trial tree.
    subprocess.run([sys.executable, "-I", "-B", str(EXTRACTOR), name, "--tree", str(tree), "--out", str(CACHE)],
                   check=True)
    frame = pd.read_parquet(CACHE / f"{name}_fit_series.parquet")
    meta = json.loads((CACHE / f"{name}_fit_check.json").read_text())
    pnl = frame["pnl"]
    committed = json.loads((tree / meta["committed_fit_json"]).read_text())
    if name == "e1":
        s4 = committed["stage4"]
        second = second_method(pnl, s4["nw_t"]["L21"], 21, "stage 4 NW t, L 21")
        params = dict(segment="muni", deals=meta["reproduced"]["deals"], k=meta["reproduced"]["k"],
                      gross_cap="max_gross_stress (trial tree's spec)", returns="total (CRSP ret, dlret)",
                      convention="shift(2)", turn_event_ann=meta["reproduced"]["turn"],
                      cost_convention=meta["cost_convention"],
                      harness_turn_sized_ann=meta["harness_turn_sized_ann_own_span"],
                      harness_turn_committed_raw_H_ann_MISSCALED=meta["harness_turn_committed_raw_H_ann"])
    else:
        s5 = committed["stages"]["5"]
        second = second_method(pnl, s5["nw_t"], 21, "stage 5 NW t, L 21 (NW_LAGS; the automatic lag is reported beside it)")
        params = dict(events=meta["events"], k=meta["reproduced"]["k"], returns="total (CRSP ret, dlret)",
                      convention="shift(2)", turn_legs_ann=meta["reproduced"]["turn"],
                      cost_convention=meta["cost_convention"])
    params.update(source_tree=meta["provenance"]["tree"], source_head=meta["provenance"]["head"],
                  script=meta["provenance"]["script"], script_last_commit=meta["provenance"]["script_last_commit"],
                  crsp_extract_sha256=meta["provenance"]["crsp_sha256"], committed_fit_json=meta["committed_fit_json"],
                  rebuilt_by="scripts/research/reopen_book/extract_trial_series.py " + name)
    check = dict(compared=len(meta["check"]["compared"]), figures=meta["check"]["compared"],
                 max_abs_diff=meta["check"]["max_abs_diff"], committed=meta["committed"],
                 span=[str(pnl.index[0].date()), str(pnl.index[-1].date())])
    note = (f"backfill 2026-10-28: {meta['provenance']['script']} at {meta['provenance']['head'][:7]} "
            f"({meta['provenance']['tree']}), re-derived by extract_trial_series.py; reproduces "
            f"{meta['committed_fit_json']} ({len(meta['check']['compared'])} figures, max |diff| "
            f"{meta['check']['max_abs_diff']:.1e}); fit period only")
    return _rebuilt("EVENTS", trial, variant, pnl, params, check, second, note)


def events_e1() -> dict:
    return _events("e1", "EVENTS-1", "e1_muni_tradable")


def events_navtender() -> dict:
    return _events("navtender", "EVENTS-2", "navtender_tradable")


# ============================================================ XASSET

def xasset(key: str) -> dict:
    """runner.decide (stages 0b-5, the fit path `fit()` calls) on the staged fit panel."""
    import importlib
    from scripts.xasset import protocol as P, runner
    spec = importlib.import_module(f"scripts.xasset.{XASSET_MODULES[key]}").SPEC
    pin = P.check_spec_pin()
    P.verify_inputs(["panel", "dgs3mo", "aqr_tsmom", "aqr_vme", "ff_daily", "ff_monthly", "spec"])
    committed = json.loads(runner.fit_json(key).read_text())
    data = runner.preflight_data()
    pf = runner.preflight(spec, data)
    out, _ = runner.decide(spec, committed["trial"], data)
    ser = out.pop("_series")
    chk = compare(json.loads(json.dumps(P.to_jsonable(out))), {k: committed[k] for k in out}, f"XASSET {key}")
    cpf = compare(pf, committed["preflight"], f"XASSET {key} preflight")
    cache = P.CACHE / f"{key.lower()}_fit_series.parquet"
    if P.sha256(cache) != committed["fit_series_cache"]["sha256"]:
        raise NotReproduced(f"XASSET {key}: the staged fit-series cache does not match the committed sha256")
    same_series(ser["pnl_sized"], pd.read_parquet(cache)["pnl_sized"], f"XASSET {key}")
    pnl = ser["pnl_sized"]
    second = second_method(pnl, committed["stage1"]["nw_t21"], 21, "stage 1 NW t, L 21")
    trial = f"XASSET-{committed['trial']}"
    s0 = committed["stage0b"]
    params = dict(test=key, slate_trial=committed["trial"], k=s0["k"], series="pnl_sized (sized, uncapped: decides)",
                  turn_sized_ann=s0["turnover_per_yr_sized"], returns="excess total returns",
                  convention="shift(2)", spec_pin=pin["spec_sha256"], committed_fit_json=P.rel(runner.fit_json(key)),
                  fit_series_cache_sha256=committed["fit_series_cache"]["sha256"],
                  rebuilt_by=f"scripts.xasset.runner.decide via scripts/xasset/{XASSET_MODULES[key]}.py")
    check = dict(compared=chk["compared"] + cpf["compared"], max_abs_diff=max(chk["max_abs_diff"], cpf["max_abs_diff"]),
                 verdict=out["fit_verdict"], cached_series="identical", window=committed["window"])
    note = (f"backfill 2026-10-28: scripts/xasset/{XASSET_MODULES[key]}.py stages 0b-5 re-run offline on the "
            f"Stage 0a manifest's inputs; reproduces {P.rel(runner.fit_json(key))} ({check['compared']} figures, "
            f"max |diff| {check['max_abs_diff']:.1e}) and the cached series; fit period only")
    return _rebuilt("XASSET", trial, f"{key.lower()}_sized", pnl, params, check, second, note)


# ============================================================ CEF

def cef_c5() -> dict:
    """C5's G on the frozen copy: FitData, gain and stage 1, as `fit()` calls them."""
    from scripts.cef import c5_open_auction as c5
    frz = c5.verify_frozen()
    committed = json.loads(c5.FIT_VERDICT.read_text())
    with c5.frozen():
        F = c5.FitData()
        G = F.gain().loc[F.W]
        s1 = c5.stage1(F)
    chk = compare(s1, committed["stage1"], "CEF C5 stage 1")
    if not C5_REF.exists():
        raise FileNotFoundError(f"{C5_REF} is missing: run `stage`")
    same_series(G, pd.read_parquet(C5_REF)["G"], "CEF C5")
    second = second_method(G, committed["stage1"]["stats"]["t21"], 21, "stage 1 NW t, L 21")
    params = dict(series="G = open-fill gain over the MOC fill on WIDE's holdings path", book="WIDE",
                  window=committed["window"], turn_yr=s1["turn_yr"], N=committed["N"],
                  frozen_record=committed["frozen_record"], frozen_files=len(frz["files"]),
                  returns="session returns open -> close on the frozen copy", convention="shift(2) holdings",
                  committed_fit_json="results/cef/c5/C5_FIT_VERDICT.json",
                  rebuilt_by="scripts/cef/c5_open_auction.py FitData().gain() and stage1()")
    check = dict(chk, verdict=committed["verdict"], cached_series="identical", window=committed["window"])
    note = (f"backfill 2026-10-28: scripts/cef/c5_open_auction.py on the frozen copy (re-verified, "
            f"{len(frz['files'])} files); reproduces C5_FIT_VERDICT.json stage 1 ({chk['compared']} figures, "
            f"max |diff| {chk['max_abs_diff']:.1e}) and the cached G; fit period only")
    return _rebuilt("CEF", "CEF-51", "c5_G_wide", G, params, check, second, note)


def cef_c4() -> dict:
    """C4's declared book on panels cut at 2022-12-30, through the trial's own functions."""
    from scripts.cef import c4_families as c4
    from scripts.cef import w4_artifacts as w4
    committed = json.loads(c4.FIT_JSON.read_text())
    cut = CACHE / "c4_cut"
    kept = {f: cut_parquet(c4.FAM_DIR / f"{f}.parquet", cut / f"{f}.parquet")
            for f in ("cef_prices", "cef_nav", "cef_actions")}
    old = (c4.FAM_DIR, c4.FAM_SRC)
    c4.FAM_DIR, c4.FAM_SRC = cut, (cut / "cef_prices.parquet", cut / "cef_nav.parquet")
    try:
        U = c4.universes()
        pool, UF = U["pool"], U["frozen"]
        px, nav = c4.load_panels(pool)
        # crsp_returns() also gates that the extract reaches 2024-12-31 (holdout coverage); the fit
        # uses CRSP only through 2022-12-30, so the extract is read cut and that gate does not apply.
        crsp = pd.read_parquet(c4.CRSP_RET, filters=[("date", "<=", FIT_END)])
        crsp["date"] = pd.to_datetime(crsp["date"])
        if sorted(set(pool) - set(crsp["ticker"])):
            raise NotReproduced("C4: pool funds with no CRSP rows before 2023")
        crsp = crsp[crsp["ticker"].isin(pool)]
        qr = c4.qqqx_rule(crsp, px)
        if not qr["use_predecessor"]:
            raise NotReproduced("C4: the QQQX rule's decision differs on the fit rows")
        have = set(px["ticker"]) & set(nav["ticker"])
        UFd = [t for t in UF if t in have]
        no_fit = sorted(set(UF) - have)
        if no_fit != committed["funds_without_fit_data"]:
            raise NotReproduced(f"C4: funds without fit data {no_fit} != committed {committed['funds_without_fit_data']}")
        # A fund with no pre-2023 row has no column in the cut panel; on the full panel its targets
        # are 0 before 2023 (no paired price and NAV). It enters as a zero column (checked below).
        T74 = c4.fit_slice(c4.build_book(UFd)).reindex(columns=UF, fill_value=0.0)
        R_ret = c4.crsp_pivot(crsp, pool, T74.index, qr, "ret", px=px)
        w4._assert_fit(T74.index, R_ret)
        row, P, H, R0, p0, _ = c4.run_book("C4 (74, declared)", UF, R_ret, T=T74)
        # Stage 1 as fit() computes it (c4_families.py, "# ---------------- Stage 1")
        t21, t5 = w4.nw_t(P, c4.NW_L), w4.nw_t(P, c4.NW_L_W4)
        L94 = w4.nw94_lag(P)
        m21, s21 = c4._boot(P, c4.BOOT_BLOCK)
        m63, s63 = c4._boot(P, c4.BOOT_BLOCK_2)
        tmb, lomb, himb = w4.block_boot_t(P)
        ci = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]  # noqa: E731
        s1 = dict(gross_sr=row["sr"], nw_t21=t21, nw_t5=t5, nw94_lag=L94, nw_t94=w4.nw_t(P, L94),
                  boot21_mean_ci_pct=[x * 252 * 100 for x in ci(m21)], boot21_sr_ci=ci(s21),
                  boot63_mean_ci_pct=[x * 252 * 100 for x in ci(m63)], boot63_sr_ci=ci(s63),
                  moving_block_t=tmb, moving_block_mean_ci_pct=[lomb * 252 * 100, himb * 252 * 100],
                  pass_=bool(t21 >= c4.D1_T))
        from scripts.cef import band_frontier as bf
        TU = bf.evaluate(H, R0)["turn_series"].loc[p0:FIT_END]      # fit()'s TU, for the era rows
        eras = [dict(book="C4 (74, declared)", era=lab, **c4.row_stats(P.loc[a:b], TU.loc[a:b]))
                for lab, a, b in c4.FIT_ERAS if len(P.loc[a:b]) > 20]
        grid = dict(gross=row["sr"], net5=row["net5"], net15=row["net15"], net30=row["net30"], turn=row["turn"],
                    flips=row["flips"])
    finally:
        c4.FAM_DIR, c4.FAM_SRC = old
    chk = compare(dict(stage1=s1, cost_grid=grid, eras=eras, funds_with_fit_data=len(UFd)),
                  {k: committed[k] for k in ("stage1", "cost_grid", "eras", "funds_with_fit_data")}, "CEF C4")
    same_series(P, pd.read_parquet(C4_REF)["c4_gross_pnl"], "CEF C4")
    second = second_method(P, committed["stage1"]["nw_t21"], 21, "stage 1 NW t, L 21")
    params = dict(book="C4 (74, declared)", universe=len(UF), funds_with_fit_data=len(UFd), first_held=str(p0.date()),
                  turn_ann=row["turn"], returns="CRSP total (ret)", convention="shift(2)",
                  policy="band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS) from the spec",
                  panels_cut_on_read=kept, committed_fit_json="results/cef/c4/c4_fit_verdict_2026-10-14.json",
                  rebuilt_by="scripts/cef/c4_families.py build_book + run_book on panels cut at 2022-12-30")
    check = dict(chk, verdict=committed["verdict"], cached_series="identical",
                 span=[str(P.index[0].date()), str(P.index[-1].date())])
    note = (f"backfill 2026-10-28: scripts/cef/c4_families.py build_book/run_book on the families panels and the "
            f"CRSP extract cut at 2022-12-30 on read; reproduces c4_fit_verdict_2026-10-14.json stage 1, cost grid "
            f"and eras ({chk['compared']} figures, max |diff| {chk['max_abs_diff']:.1e}) and the cached fit P&L; "
            "fit period only")
    return _rebuilt("CEF", "CEF-52", "c4_74_declared", P, params, check, second, note)


# The v7 note's committed figures that use only pre-2023 data
# (results/cef/PREREG_ALPACA_V7_2026-09-28.md §3a, §3b and "By era"; the script's RECORDED_* constants).
V7_COMMITTED = {
    "k17": 0.304953, "w5_17": 0.038264817497540925, "w5_17_end": "2020-03-18",
    "k13": 0.00, "w5_13": 0.0425814, "w5_13_end": "2020-03-18", "muni13_target_share": 0.074,
    "eras": {"v6 band, 17 names": {"2010-14": (0.86, 2.7), "2015-19": (1.48, 9.9), "2020-22": (2.17, 16.0)},
             "v7-on-Alpaca": {"2010-14": (0.72, 2.2), "2015-19": (0.82, 5.6), "2020-22": (1.06, 6.7)}},
}


def cef_v7_fit_check() -> dict:
    """REPORT ONLY (CEF-48..50 are not stored: their headlines span the 2023 holdout).
    Re-runs `alpaca_v7_derivation.py`'s functions on the four CEF panels cut at
    2022-12-30 on read, and compares the figures the v7 note committed that use only
    pre-2023 data, at their stated precision. It says whether a fit-period series for
    those books could be stored if the team lead accepted these figures as the check."""
    from scripts.cef import alpaca_v7_derivation as v7
    from scripts.cef import band_frontier as bf
    from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS
    cut = CACHE / "cef_cut"
    kept = {f: cut_parquet(bf.DATA_DIR / f"{f}.parquet", cut / f"{f}.parquet", col, allow_empty=empty)
            for f, col, empty in (("cef_prices", "date", False), ("cef_nav", "date", False),
                                  ("cef_distributions", "ex_date", False), ("cef_splits", "ex_date", True))}
    v6 = json.loads(subprocess.run(["git", "show", "spec-cef_discount.v6.20260906:ops/specs/cef_discount.frozen.json"],
                                   cwd=REPO, capture_output=True, text=True, check=True).stdout)
    u17 = list((v6.get("frozen") or v6)["universe"])
    u13 = [t for t in u17 if t not in v7.DROPPED]
    old = bf.DATA_DIR
    bf.DATA_DIR = cut
    try:
        T17, R17 = bf.fit_only(*bf.build_targets(u17))
        Rt17 = bf.total_returns(R17)
        H17 = bf.band(T17, BAND_WIDTH)
        T13, R13 = bf.fit_only(*bf.build_targets(u13))
        Rt13 = bf.total_returns(R13)
        H13 = bf.band(T13, BAND_WIDTH)
        Hc = bf.band_gross_capped(T13, BAND_WIDTH, MAX_GROSS_STRESS)
        w17, d17 = v7.w5(H17, Rt17)
        w13, d13 = v7.w5(H13, Rt13)
        muni13, _ = v7.groups(u13)
        got = {"k17": round(v7.k_median(T17, u17), 6), "w5_17": w17, "w5_17_end": str(d17.date()),
               "k13": round(v7.k_median(T13, u13), 2), "w5_13": float(f"{w13:.7f}"), "w5_13_end": str(d13.date()),
               "muni13_target_share": round(float((T13.loc[v7.TRADED_START:v7.FIT_END, muni13].abs().sum(axis=1) > 0)
                                                  .mean()), 3), "eras": {}}
        for name, H, Rt in (("v6 band, 17 names", H17, Rt17), ("v7-on-Alpaca", Hc, Rt13)):
            got["eras"][name] = {}
            for lab, a, b in v7.ERAS:
                if lab in V7_COMMITTED["eras"][name]:
                    s = v7.stats(H, Rt, a, b)
                    got["eras"][name][lab] = (round(s["sr"], 2), round(s["ann"], 1))
    finally:
        bf.DATA_DIR = old
    want = plain(V7_COMMITTED)
    gotp = plain(got)
    rows = []
    for k, w in _leaves(want):
        g = dict(_leaves(gotp)).get(k)
        ok = (abs(g - w) <= 1e-12) if k == "w5_17" else (g == w)
        rows.append(dict(figure=k, committed=w, rebuilt=g, match=bool(ok)))
    return dict(report_only=True, panels_cut_on_read=kept, v6_universe=u17, figures=rows,
                all_match=all(r["match"] for r in rows),
                reading=("every committed pre-2023 figure of the v7 note reproduces on panels cut at 2022-12-30"
                         if all(r["match"] for r in rows) else "some committed pre-2023 figures do not reproduce"))


REBUILDERS = {"events_e1": events_e1, "events_navtender": events_navtender, "cef_c5": cef_c5, "cef_c4": cef_c4,
              **{f"xasset:{k}": (lambda k=k: xasset(k)) for k in XASSET_MODULES}}


# ============================================================ run

def run(record: bool = False, only=None) -> dict:
    from ops import netguard
    from scripts.research import registry as rg
    netguard.install()
    counters = rg._counters()
    summary = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                                      check=True).stdout.strip(),
               "record": record, "counters": {}, "trials": {}}
    for counter in ("EVENTS", "XASSET", "CEF"):
        canon = counters[counter]["trials"]
        rows = C.validate(counter, canon)          # the census must cover the canonical count read now (H14)
        summary["counters"][counter] = {"canonical_trials": canon}
        for r in rows:
            ent = dict(trial=r["trial"], status=r["status"], reason=r["reason"], script=r["script"], source=r["source"])
            if r["status"] == C.REBUILD and (only is None or r["id"] in only):
                print(f"\n==== {r['id']}: {r['trial']}")
                b = REBUILDERS[r["rebuild"]]()
                if b["trial"] != r["id"]:
                    raise RuntimeError(f"{r['rebuild']} built {b['trial']}, the census says {r['id']}")
                ent.update(variant=b["variant"], check=b["check"], second_method=b["second"],
                           first=str(b["pnl"].index[0].date()), last=str(b["pnl"].index[-1].date()), n=len(b["pnl"]))
                print(f"{r['id']}: REPRODUCED ({b['check']['compared']} figures, max |diff| "
                      f"{b['check']['max_abs_diff']:.1e}); {ent['first']}..{ent['last']}, T {ent['n']}; "
                      f"second method: inference NW t {b['second']['inference_nw_t']:.4f} vs committed "
                      f"{b['second']['committed_t']:.4f}")
                if record:
                    # Each backfilled trial stores the one series it was judged on
                    # (registry.record's judged flag, 2026-10-28).
                    line = rg.record(b["pnl"], counter=counter, trial=b["trial"], variant=b["variant"],
                                     params=b["params"], note=b["note"], judged=True)
                    ent.update(status="STORED", ledger={k: line[k] for k in ("commit", "dirty", "first", "last", "n",
                                                                              "sr_annual", "skew", "kurt", "sha256")})
                else:
                    ent.update(status="REPRODUCED (not recorded: run with --record)")
            elif r["status"] == C.REBUILD:
                ent.update(status="SKIPPED (--only)")
            summary["trials"][r["id"]] = ent
    print("\n==== CEF-48..50: the v7 note's pre-2023 figures (REPORT ONLY; nothing is stored)")
    v7c = cef_v7_fit_check()
    for f in v7c["figures"]:
        print(f"  {f['figure']:<38} committed {f['committed']!s:<24} rebuilt {f['rebuilt']!s:<24} "
              f"{'match' if f['match'] else 'MISMATCH'}")
    summary["cef_48_50_fit_check"] = v7c
    for counter in ("EVENTS", "XASSET", "CEF"):
        if rg.entries(counter):
            bi = rg.bar_inputs(counter)
            summary["counters"][counter]["bar_inputs"] = plain(bi)
            print(f"\nbar_inputs({counter}): {plain(bi)}")
        else:
            summary["counters"][counter]["bar_inputs"] = "no stored series"
            print(f"\nbar_inputs({counter}): no stored series")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"backfill_{dt.date.today().isoformat()}.json"
    path.write_text(json.dumps(plain(summary), indent=1) + "\n")
    print(f"\nwrote {path.relative_to(REPO)}")
    return summary


def census_markdown() -> str:
    from scripts.research import registry as rg
    counters = rg._counters()
    out = ["| id | trial | source | script | status | reason |", "|---|---|---|---|---|---|"]
    for counter in ("EVENTS", "XASSET", "CEF"):
        for r in C.validate(counter, counters[counter]["trials"]):
            out.append(f"| {r['id']} | {r['trial']} | {r['source']} | {r['script']} | {r['status']} | {r['reason']} |")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stage", help="copy the trials' gitignored caches into this tree")
    r = sub.add_parser("run", help="re-run, check and (with --record) store")
    r.add_argument("--record", action="store_true")
    r.add_argument("--only", nargs="+", help="trial ids to rebuild (default: every REBUILD row)")
    sub.add_parser("census", help="print the census table")
    a = ap.parse_args(argv)
    # pandas' numexpr option is left as the XASSET, C4 and C5 trials ran it; the EVENTS
    # extractor sets it off itself, as those trials did (DG-NT-6 / DG-E1-6).
    if a.cmd == "stage":
        for k, v in stage().items():
            print(f"{v:>8}  {k}")
    elif a.cmd == "run":
        run(record=a.record, only=set(a.only) if a.only else None)
    else:
        print(census_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
