"""Re-derive one killed EVENTS trial's daily FIT-PERIOD P&L by running that branch's own committed code.

    python3 -I scripts/research/reopen_book/extract_trial_series.py navtender --tree <trial-events-navtender worktree> --out <dir>
    python3 -I scripts/research/reopen_book/extract_trial_series.py e1        --tree <trial-events-e1 worktree>        --out <dir>

`reopen_book.py` calls this in a child process, once per trial. Run it by hand only to debug.

WHY THIS EXISTS (2026-10-28)
----------------------------
The team lead's 2026-10-27 ruling (`docs/SYSTEM.md` §5) lets a sleeve that failed the
standalone deflated Sharpe join the PAPER book if it adds to the CEF book. Judging that
needs each sleeve's daily P&L series, and neither trial stored one:
`results/events/nav_tender/fit_2026-10-19.json` and `results/events/e1/e1_fit_verdict.json`
hold aggregates only, because the series is derived from licensed CRSP rows and the
trials kept row-level CRSP output out of tracked files. The ruling's own rule for this
case is to re-run the branch's committed script on fit-period data. This file does that
and nothing else: it imports the trial module FROM ITS OWN WORKTREE (`--tree`), calls the
same functions in the same order as that trial's `fit`, and stops at the sleeve. It
writes no file in the trial's worktree (`fit` there refuses to run twice, and its JSON
is a committed verdict), and it never calls the trial's `fit` or `holdout` entry points.

WHY A CHILD PROCESS: both worktrees and this one hold a package called `scripts`. Loading
two copies in one interpreter would let this desk's harness and the trial's mix
silently. The child puts the trial's tree first on `sys.path` and imports only that.
`-I` (isolated mode) keeps the caller's environment and this directory out of the path.

FIT ONLY (H13; the task's hard rule). Both trials read CRSP through
`crsp_events.daily`, which selects `date < 2023-01-01` and asserts it; neither holdout
reader is imported. The series written here are asserted to end before 2023-01-01.

NO PULL, NO NETWORK. A cache miss in `crsp_events._pull` would load an R2 credential
and download. Here a miss raises instead, the R2 client module is made unimportable, and
`ops.netguard` refuses every socket. If a trial's caches are incomplete, this fails
loudly; it never fetches.

THE PAPER VIEW (added 2026-10-28, after an independent review). Alpaca paper pays no
distributions (CLAUDE.md landmine 1), so each sleeve is also scored on PRICE returns, on
the same tradable positions (the same H, the same k, the same cap), by two methods:
  A. the trial's own builder re-run on CRSP `retx` (and `dlretx` for a delisting) in place
     of `ret` (`dlret`): `build_matrices` for NAV tenders, `returns_matrix` for E1;
  B. an overlay: the distribution leg sum_c H.shift(2)[t, c] * (ret - retx)[t, c] on the
     trial's tradable H, with a tendered fund's column scaled by (1 - pi) from its pricing
     session on (the residual), subtracted from the total-return P&L.
Both are written; the caller reports both and their difference. B omits the distribution
part of a delisting return, which A carries.

E1'S HARNESS TURNOVER (corrected 2026-10-28). `e1_merger_pair.sleeve` returns
`raw["turn_series"]`, the turnover of the UNSIZED, uncapped H, beside P&L on the sized and
capped Ht. The trial's committed `harness_turn` (14.40/yr) is therefore mis-scaled. It is
still compared here, to prove the reproduction, but the harness turnover written for use is
measured on Ht itself, and `check_same_h` refuses a P&L and a turnover from different H.

REPRODUCTION CHECK. Before writing anything, each sleeve's gross and net Sharpes,
vol, turnover, T and first/last session are recomputed by the trial's own `_stats`
and compared with the trial's committed fit JSON. A mismatch above 1e-9 raises: a
series that does not reproduce its committed verdict is not that trial's series.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

HOLDOUT_START = "2023-01-01"
TOL = 1e-9


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _git(tree: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=tree, capture_output=True, text=True, check=True).stdout.strip()


def _guard(tree: Path) -> None:
    """Put the trial's tree first on the path, then make every pull and connection raise."""
    sys.path.insert(0, str(tree))
    sys.modules["src.data.r2"] = None            # `from src.data.r2 import ...` now raises ImportError
    from ops import netguard
    netguard.install()
    from scripts.events import crsp_events as ce
    if Path(ce.__file__).resolve().parents[2] != tree.resolve():
        raise RuntimeError(f"crsp_events loaded from {ce.__file__}, not from the trial tree {tree}")
    orig = ce._pull

    def cached_only(name, sql_template, refresh):
        p = ce.CACHE / f"{name}.parquet"
        if refresh or not p.exists():
            raise RuntimeError(f"{p} is not cached in the trial tree; this re-derivation never pulls "
                               "(an R2 pull loads a credential). Stop and report.")
        return orig(name, sql_template, refresh)
    ce._pull = cached_only


def _provenance(tree: Path, script_rel: str, crsp_file: Path) -> dict:
    dirty = _git(tree, "status", "--porcelain", "--", script_rel)
    if dirty:
        raise RuntimeError(f"{script_rel} differs from HEAD in {tree}: not the branch's committed script")
    return {"tree": tree.name, "branch": _git(tree, "rev-parse", "--abbrev-ref", "HEAD"),
            "head": _git(tree, "rev-parse", "HEAD"), "script": script_rel,
            "script_last_commit": _git(tree, "log", "-1", "--format=%H", "--", script_rel),
            "crsp_extract": crsp_file.name, "crsp_sha256": _sha256(crsp_file)}


def _compare(got: dict, want: dict, label: str) -> dict:
    diffs = {k: abs(float(got[k]) - float(want[k])) for k in want}
    bad = {k: (got[k], want[k]) for k, d in diffs.items() if d > TOL}
    if bad:
        raise RuntimeError(f"{label}: the re-derived sleeve does not reproduce the committed fit JSON: {bad}")
    return {"max_abs_diff": max(diffs.values()), "compared": sorted(want)}


def check_same_h(H, R, pnl, turn=None, tol: float = 1e-12) -> None:
    """Raise unless `pnl` (and `turn`, if given) come from this one H, by evaluate()'s formulas.

    pnl[t] = sum_c H.shift(2)[t, c] * R[t, c] (NaN cells skipped, as `evaluate` sums them);
    turn[t] = sum_c |H[t, c] - H[t-1, c]|. E1's trial divided P&L on the sized, capped H by
    the turnover of the raw one (the docstring above); this is the check that would have
    caught it."""
    import numpy as np
    p = (H.shift(2).fillna(0.0) * R).sum(axis=1).reindex(pnl.index)
    if p.isna().any() or not np.allclose(p.values, pnl.values, rtol=0.0, atol=tol):
        raise ValueError(f"P&L is not evaluate(H, R) on this H (max |diff| {float((p - pnl).abs().max()):.3e})")
    if turn is not None:
        t = H.diff().abs().sum(axis=1).reindex(turn.index)
        if t.isna().any() or not np.allclose(t.values, turn.values, rtol=0.0, atol=tol):
            raise ValueError(f"turnover is not H.diff() on this H (max |diff| {float((t - turn).abs().max()):.3e}): "
                             "P&L and turnover come from different weights")


def _ex_dist(df, col: str, colx: str):
    """A copy of a CRSP frame with the total-return column replaced by its ex-distribution twin."""
    out = df.copy()
    out[col] = df[colx].astype(float)
    return out


def navtender(tree: Path) -> tuple:
    import pandas as pd
    from scripts.events import nav_tender_trial as nt
    from scripts.cef.band_frontier import _stats
    from scripts.cef.spec import MAX_GROSS_STRESS
    from scripts.events import crsp_events as ce
    if MAX_GROSS_STRESS is None:
        raise RuntimeError("the trial tree's spec has no max_gross_stress; the trial sized against it")
    committed = json.loads(nt.FIT_JSON.read_text())
    # The trial's own fit path, in its order: Stage 0 (A+B, the rulings block) on the
    # cached EDGAR and CRSP, write=False so no tracked Stage-0 file is touched; then
    # run_pnl with k derived from the raw sleeve and the cap at entry (fit_on, prereg §5.4).
    S = nt.stage0(edgar_only=False, write=False)
    D = S["data"]
    run = nt.run_pnl(D, nt.to_events(D.ev), None, MAX_GROSS_STRESS)
    a, b = D.t_first, D.t_last
    pnl = run["pnl_trad"].loc[a:b]
    turn = run["turn_trad"].loc[a:b]                     # Q: notional traded on every leg (the trial's grid)
    H = run["trad"]["H"]
    held = H.shift(2).fillna(0.0).abs().sum(axis=1).loc[a:b]   # evaluate()'s own convention: flat before the first decision
    st = _stats(pnl, turn)
    got = {"gross": st["sr"], "net5": st["nets"][0], "net15": st["nets"][1], "net30": st["nets"][2],
           "turn": st["turn"], "ann": st["ann"], "vol": st["vol"], "T": len(pnl), "k": run["k"]}
    want = {"gross": committed["grid_tradable"]["gross"], "net5": committed["grid_tradable"]["net5"],
            "net15": committed["grid_tradable"]["net15"], "net30": committed["grid_tradable"]["net30"],
            "turn": committed["grid_tradable"]["turn"], "ann": committed["grid_tradable"]["ann"],
            "vol": committed["stages"]["5"]["vol"], "T": committed["stages"]["5"]["T"],
            "k": committed["sizing"]["k"]}
    chk = _compare(got, want, "navtender")
    if str(pnl.index[0].date()) != committed["stages"]["5"]["first"] or \
            str(pnl.index[-1].date()) != committed["stages"]["5"]["last"]:
        raise RuntimeError(f"navtender: span {pnl.index[0].date()}..{pnl.index[-1].date()} is not the committed one")
    trad = run["trad"]
    check_same_h(H, trad["R"].fillna(0.0).where(H.shift(2).fillna(0.0) != 0.0, 0.0), pnl)   # sleeve_pnl's R
    decided = H.abs().sum(axis=1).loc[a:b]
    # ---- the paper view (price returns), on the SAME positions: events, betas and the capped w
    import numpy as np
    from scripts.events import e1_etf_hedge_gate as g
    events = nt.to_events(D.ev)
    plist = json.loads(nt.PERMNO_LIST.read_text())["permnos"]
    dsf = nt.daily_raw(plist)                             # the fit reader (no 2023 row, asserted there)
    dl = ce.delistings()
    dsf_x, dl_x = _ex_dist(dsf, "ret", "retx"), _ex_dist(dl, "dlret", "dlretx")
    names = ce.names()
    need_etf, _ = nt.etf_permnos_resolved(names, nt.hedge_symbols())
    etf_x = {s_: g.series(dsf_x[dsf_x["permno"] == int(p_)])[int(p_)]["ret"].reindex(D.sessions)
             for s_, p_ in need_etf.items() if s_ in D.etf}
    fr_x = {}
    for r in D.ev.itertuples():                           # stage0_partB's own call, on retx
        fs = nt.series_on(dsf_x, int(r.permno), D.sessions, nt.add_sessions(r.day0, 2) - pd.Timedelta(days=10),
                          r.last_session, dl_x)
        fr_x[r.eid] = fs["ret"].reindex(D.sessions)
    fc = {e_.eid: D.fund[e_.eid]["close"] for e_ in events}
    MX = nt.build_matrices(events, fr_x, fc, etf_x, D.sessions, weights=run["w"])     # method A
    if not MX["H"].equals(H):
        raise RuntimeError("navtender: the price-return rebuild did not reproduce the tradable H")
    pnl_px = nt.sleeve_pnl(MX).loc[a:b]
    # method B: the overlay on the tradable H
    d = dsf.assign(dist=dsf["ret"].astype(float) - dsf["retx"].astype(float)).pivot_table(
        index="date", columns="permno", values="dist").reindex(D.sessions)
    perm = dict(zip(D.ev["eid"], D.ev["permno"].astype(int)))
    Dm = pd.DataFrame(0.0, index=D.sessions, columns=H.columns)
    for e_ in events:
        col = d[perm[e_.eid]].copy()
        if e_.x_p is not None and e_.pi > 0:              # the residual from the pricing session on
            col.loc[col.index >= e_.x_p] *= (1.0 - e_.pi)
        Dm[e_.eid] = col
    for s_ in sorted({e_.etf for e_ in events}):
        Dm[s_] = d[need_etf[s_]]
    held_mask = H.shift(2).fillna(0.0) != 0.0
    gap = held_mask & Dm.isna()
    bridged_ok = gap & (trad["R"].fillna(0.0) == 0.0)      # the trial wrote these sessions as 0 (DG-NT-3)
    if (gap & ~bridged_ok).any().any():
        raise RuntimeError("navtender overlay: a held cell has no ret - retx and was not a bridged zero")
    Dm = Dm.where(~gap, 0.0)
    dist_overlay = (H.shift(2).fillna(0.0) * Dm).sum(axis=1).loc[a:b]
    paper = {"method_A_dist_ann": float((pnl - pnl_px).mean() * 252), "method_B_dist_ann": float(dist_overlay.mean() * 252),
             "max_abs_daily_diff_A_vs_B": float(((pnl - pnl_px) - dist_overlay).abs().max()),
             "sum_diff_A_minus_B": float(((pnl - pnl_px) - dist_overlay).sum()),
             "overlay_bridged_zero_cells": int(gap.sum().sum()),
             "etf_permnos": {k_: int(v_) for k_, v_ in need_etf.items() if k_ in H.columns}}
    frame = pd.DataFrame({"pnl": pnl, "pnl_price": pnl_px, "dist_overlay": dist_overlay, "turn": turn,
                          "held_gross": held, "decided_gross": decided})
    _, h = ce._plist(plist)
    prov = _provenance(tree, "scripts/events/nav_tender_trial.py", ce.CACHE / f"dsf_{h}.parquet")
    meta = {"trial": "navtender", "cost_convention": "turn = notional traded on every leg (fund entry, the "
            "residual sale, ETF hedge changes); `_stats(pnl, Q.abs().sum(axis=1))`, as the trial's grid",
            "reproduced": got, "committed": want, "check": chk, "provenance": prov,
            "events": int(len(D.ev)), "committed_fit_json": str(nt.FIT_JSON.relative_to(tree)),
            "r_book_committed": committed["report_only"]["r_book"], "paper_view": paper}
    return frame, meta


def e1(tree: Path) -> tuple:
    import pandas as pd
    from scripts.events import e1_merger_pair as e
    from scripts.cef.band_frontier import _stats
    from scripts.cef.spec import MAX_GROSS_STRESS, VOL_TARGET
    committed = json.loads(e.FIT_JSON.read_text())
    # The trial's own fit() (e1_merger_pair.py, lines "def fit(args)"), step for step, as
    # far as the sleeve. Control 2's pick is skipped: it decides stage 3, and the sleeve
    # (`sleeve(M, R, cal, ...)`) never reads it. The control-2 POOL is kept, because it
    # widens the permno set and the cached extract is keyed by that set.
    e._require_stage0_clear()
    nm, dl = e.crsp_tables()
    comp, fail = e._load_trial_deals(nm, dl, date.fromisoformat(committed["provenance"]["today"]))
    D = pd.concat([comp[comp["part"] == e.FIT_SET], fail[fail["part"] == e.FIT_SET]], ignore_index=True)
    etf_perm = {tk: int(nm[(nm["ticker"] == tk) & (nm["shrcd"] == 73) & (nm["nameendt"] >= e.FIT_START)]["permno"].iloc[0])
                for tk in e.ETF_TICKERS}
    perms0 = set(D["permno"].astype(int)) | set(D["nwperm"].astype(int)) | set(etf_perm.values())
    px0 = e.price_series(e.fit_daily(perms0))
    cal = e.market_calendar(pd.concat([v.reset_index()[["date"]] for v in px0.values()]), e.CAL_START, e.FIT_END)
    pool = {}
    for i, row in D.iterrows():
        w = e.deal_window(row, px0, cal, failed=bool(row["failed"]), fail_date=row["fail_date"])
        if w is not None and not w["why"]:
            pool[i] = (w, e.control2_candidates(row, nm, cal, w, set()))
    perms = perms0 | {int(p) for _, c in pool.values() for p in c["permno"]}
    dsf = e.fit_daily(perms)
    px = e.price_series(dsf)
    R = e.returns_matrix(px, cal, D)
    P, _ = e.price_deals(D, px, cal, R)
    M = P[P["seg"] == "muni"].copy()                     # decision 2: the headline segment
    S = e.sleeve(M, R, cal, k=None, cap=MAX_GROSS_STRESS, vol_target=VOL_TARGET)
    pnl, turn = S["pnl"], S["turn"]                       # turn: EVENT turnover (a conversion is not a trade)
    held = S["H"].shift(2).fillna(0.0).abs().sum(axis=1).loc[pnl.index]   # evaluate()'s convention
    st = _stats(pnl, turn)
    s4 = committed["stage4"]
    got = {"gross": st["sr"], "net5": st["nets"][0], "net15": st["nets"][1], "net30": st["nets"][2],
           "turn": st["turn"], "ann": st["ann"], "vol": st["vol"], "T": len(pnl), "k": S["k"],
           "harness_turn": float(S["harness_turn"].mean() * 252), "deals": len(M)}
    want = {"gross": s4["gross_sr"], "net5": s4["net_sr"]["5bp"], "net15": s4["net_sr"]["15bp"],
            "net30": s4["net_sr"]["30bp"], "turn": s4["turn"], "ann": s4["ann"], "vol": s4["vol"],
            "T": committed["stage6"]["T"], "k": s4["k"], "harness_turn": s4["harness_turn"],
            "deals": committed["deals"]}
    chk = _compare(got, want, "e1")
    if str(pnl.index[0].date()) != s4["first"]:
        raise RuntimeError(f"e1: first session {pnl.index[0].date()} is not the committed {s4['first']}")
    from scripts.cef import band_frontier as bf
    Ht = S["H"]
    Rh = R.reindex(index=cal, columns=Ht.columns)
    ev_t = bf.evaluate(Ht, Rh)
    harness_sized = ev_t["turn_series"].loc[pnl.index]   # turnover of the H the P&L is earned on
    check_same_h(Ht, Rh, pnl, harness_sized)
    decided = Ht.abs().sum(axis=1).loc[pnl.index]
    # ---- the paper view (price returns), on the same Ht
    import numpy as np
    dsf_x = _ex_dist(dsf, "ret", "retx")
    Dx = _ex_dist(D, "dlret", "dlretx")
    Rx = e.returns_matrix(e.price_series(dsf_x), cal, Dx).reindex(index=cal, columns=Ht.columns)   # method A
    pnl_px = bf.evaluate(Ht, Rx)["pnl"].loc[pnl.index]
    check_same_h(Ht, Rx, pnl_px)
    dist_cells = (dsf.assign(dist=dsf["ret"].astype(float) - dsf["retx"].astype(float))
                  .pivot_table(index="date", columns="permno", values="dist").reindex(index=cal, columns=Ht.columns))
    dist_overlay = (Ht.shift(2).fillna(0.0) * dist_cells).sum(axis=1).loc[pnl.index]          # method B
    Dm_ = D.loc[M["row"]]                                 # price_deals keeps D's row label in `row`
    lost_dl = int((~Dm_["failed"].astype(bool) & Dm_["dlret"].notna() & Dm_["dlretx"].isna()).sum())
    paper = {"method_A_dist_ann": float((pnl - pnl_px).mean() * 252), "method_B_dist_ann": float(dist_overlay.mean() * 252),
             "max_abs_daily_diff_A_vs_B": float(((pnl - pnl_px) - dist_overlay).abs().max()),
             "sum_diff_A_minus_B": float(((pnl - pnl_px) - dist_overlay).sum()),
             "muni_deals_with_dlret_but_no_dlretx": lost_dl}
    frame = pd.DataFrame({"pnl": pnl, "pnl_price": pnl_px, "dist_overlay": dist_overlay, "turn": turn,
                          "held_gross": held, "decided_gross": decided, "harness_turn": harness_sized,
                          "harness_turn_raw_H": S["harness_turn"].reindex(pnl.index)})
    prov = _provenance(tree, "scripts/events/e1_merger_pair.py", e._dsf_path(perms))
    meta = {"trial": "e1", "cost_convention": "turn = EVENT turnover (`bf.event_turnover`: a merger conversion "
            "is not a trade), `_stats(pnl, turn)`, as the trial's stage 4; the harness's own count "
            "(conversions as trades), measured on the sized and capped Ht, is stored beside it as "
            "harness_turn; the trial's committed harness_turn is on the raw H (mis-scaled) and is kept "
            "only as harness_turn_raw_H",
            "harness_turn_sized_ann_own_span": float(harness_sized.mean() * 252),
            "harness_turn_committed_raw_H_ann": float(s4["harness_turn"]),
            "reproduced": got, "committed": want, "check": chk, "provenance": prov,
            "committed_fit_json": str(e.FIT_JSON.relative_to(tree)),
            "r_book_committed": committed["stage5"]["r_book"], "paper_view": paper}
    return frame, meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("trial", choices=("navtender", "e1"))
    ap.add_argument("--tree", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    tree = a.tree.resolve()
    _guard(tree)
    import pandas as pd
    pd.set_option("compute.use_numexpr", False)          # DG-NT-6 / DG-E1-6: the numexpr fault
    frame, meta = (navtender if a.trial == "navtender" else e1)(tree)
    if frame.index.max() >= pd.Timestamp(HOLDOUT_START) or frame.isna().any().any():
        raise RuntimeError(f"{a.trial}: the series reaches 2023 or holds NaN; refusing to write it")
    a.out.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(a.out / f"{a.trial}_fit_series.parquet")
    (a.out / f"{a.trial}_fit_check.json").write_text(json.dumps(meta, indent=1, default=float))
    print(f"{a.trial}: {len(frame)} sessions {frame.index[0].date()}..{frame.index[-1].date()}; "
          f"reproduces the committed fit (max |diff| {meta['check']['max_abs_diff']:.1e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
