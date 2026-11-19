"""Do stale NAV copies sit on large NAV moves? The caveat of explore.py, tested on what the VM saw. Research only.

    python3 results/ideas/nav_stale_gate/checks.py [--refetch]

WHY. explore.py drew stale name-days at random and found they cost about 0.2% a year. If a
NAV is late BECAUSE something happened, stale days are the big-move days and that cost is
understated. The team lead asked for this test before deciding (2026-11-19).

DATA
  * ~/quantt_research/nav_stale_gate/vm_nav_gate_checks.csv: every per-fund check the core's
    stale-NAV gate recorded in the VM's plan.json files (2026-10-15 on): the NAV dated D the
    session actually saw (`nav_d`), the previous panel NAV, and the trigger. Copied from the
    VM read-only on 2026-11-19; public NAVs, no account data.
  * Yahoo's NAV series X<TICKER>X for the same 13 funds, fetched NOW through yfinance (the
    source the live fetcher uses, scripts/cef/fetch_daily.py), cached as
    ~/quantt_research/nav_stale_gate/yahoo_nav_now.parquet. Yahoo corrects a stale row
    later, so today's value for D is the best available truth for D. A row Yahoo never
    corrected still looks genuine here: confirmed stale is a LOWER bound.

FIXED BEFORE READING ANY MOVE
  For each checked name-day with a repeat trigger: CONFIRMED STALE if today's Yahoo NAV for D
  differs from the NAV the session saw by more than half a cent; GENUINE REPEAT if it does
  not. Every other checked name-day is FRESH. The true one-session NAV move of a name-day is
  today's Yahoo NAV(D) / today's Yahoo NAV(previous session) - 1.
  Test: mean and median |move| of CONFIRMED STALE against FRESH name-days, and the share of
  the largest-decile |move| name-days (decile cut over all checked name-days) that were
  stale, against the overall stale share. If stale days were random, the two shares match.
  Then, not pre-specified in its numbers but fixed in form: explore.py's STALE variant re-run
  with stale name-days drawn with probability proportional to the measured stale share in
  each |NAV move| quintile, 200 draws, to restate the cost under the measured clustering.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore as _explore  # noqa: E402,F401

OUT = Path.home() / "quantt_research" / "nav_stale_gate"
CHECKS = OUT / "vm_nav_gate_checks.csv"
CACHE = OUT / "yahoo_nav_now.parquet"


def fetch(funds: list, start: str) -> pd.DataFrame:
    import yfinance as yf
    rows = []
    for tk in funds:
        h = yf.Ticker(f"X{tk}X").history(start=start, auto_adjust=False)
        if h.empty:
            raise RuntimeError(f"Yahoo returned no NAV history for X{tk}X")
        s = h["Close"].dropna()
        rows.append(pd.DataFrame({"date": s.index.tz_localize(None).normalize(), "ticker": tk, "nav": s.to_numpy()}))
        time.sleep(0.6)
    return pd.concat(rows, ignore_index=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true")
    ap.add_argument("--data", type=Path, default=None, help="a data/cef directory: also restate the cost under the measured clustering")
    a = ap.parse_args(argv)
    c = pd.read_csv(CHECKS, parse_dates=["asof", "prev_date"])
    c = c.drop_duplicates(["asof", "fund"], keep="last")
    funds = sorted(c["fund"].unique())
    if a.refetch or not CACHE.exists():
        fetch(funds, "2026-09-01").to_parquet(CACHE, index=False)
    y = pd.read_parquet(CACHE)
    fetched_last = y["date"].max().date()
    Y = y.pivot(index="date", columns="ticker", values="nav").sort_index()
    mv = Y / Y.shift(1) - 1.0                    # today's Yahoo NAV(D) against today's NAV(previous Yahoo row)
    c["now"] = [Y[f].get(d, np.nan) for d, f in zip(c["asof"], c["fund"])]
    c["move"] = [mv[f].get(d, np.nan) for d, f in zip(c["asof"], c["fund"])]
    miss = int(c["now"].isna().sum())
    c = c.dropna(subset=["now", "move"])
    rep = c["trigger"].fillna("").str.contains("yf_repeat")
    stale = rep & ((c["now"] - c["nav_d"]).abs() > 0.005)
    c["kind"] = np.where(stale, "STALE", np.where(rep, "GENUINE", "FRESH"))
    # a non-repeat row that Yahoo later changed is a different defect (a revised NAV): counted, not mixed in
    revised = (~rep) & ((c["now"] - c["nav_d"]).abs() > 0.005)
    c["absmove_bp"] = c["move"].abs() * 1e4
    out = {"checks_file_rows": int(len(c) + miss), "name_days_without_a_yahoo_row_now": miss, "yahoo_fetched_last_date": str(fetched_last),
           "sessions": [str(c["asof"].min().date()), str(c["asof"].max().date())], "name_days": int(len(c)),
           "revised_non_repeats": int(revised.sum()), "by_kind": {}}
    for k, g in c.groupby("kind"):
        out["by_kind"][k] = {"n": int(len(g)), "share": round(len(g) / len(c), 4),
                             "mean_abs_move_bp": round(float(g["absmove_bp"].mean()), 2),
                             "median_abs_move_bp": round(float(g["absmove_bp"].median()), 2),
                             "share_zero_move": round(float((g["absmove_bp"] < 0.5).mean()), 3)}
    cut = c["absmove_bp"].quantile(0.9)
    top = c[c["absmove_bp"] >= cut]
    out["top_decile"] = {"cut_bp": round(float(cut), 2), "n": int(len(top)), "stale_share": round(float((top["kind"] == "STALE").mean()), 4),
                         "overall_stale_share": round(float((c["kind"] == "STALE").mean()), 4)}
    c["q"] = pd.qcut(c["absmove_bp"].rank(method="first"), 5, labels=False)
    byq = c.groupby("q").agg(n=("kind", "size"), stale=("kind", lambda s: float((s == "STALE").mean())),
                             lo=("absmove_bp", "min"), hi=("absmove_bp", "max"))
    out["stale_share_by_abs_move_quintile"] = [{"quintile": int(q) + 1, "n": int(r.n), "abs_move_bp": [round(float(r.lo), 1), round(float(r.hi), 1)],
                                               "stale_share": round(float(r.stale), 4)} for q, r in byq.iterrows()]
    # per-session clustering: a t-test across name-days overstates; the same comparison within session
    ws = c.groupby("asof").apply(lambda g: g.loc[g["kind"] == "STALE", "absmove_bp"].mean() - g.loc[g["kind"] == "FRESH", "absmove_bp"].mean())
    ws = ws.dropna()
    out["stale_less_fresh_abs_move_bp_within_session"] = {"sessions": int(len(ws)), "mean": round(float(ws.mean()), 2),
                                                          "t": round(float(ws.mean() / (ws.std() / len(ws) ** 0.5)), 2) if len(ws) > 2 else None,
                                                          "share_positive": round(float((ws > 0).mean()), 3)}
    if a.data is not None:
        from scripts.cef import band_frontier as bf
        from scripts.research import harness
        src = (a.data / "cef_prices.parquet", a.data / "cef_nav.parquet")
        T, R = bf.build_targets(source=src)
        TL, _ = bf.build_targets(source=(src[0], Path(os.environ["TMPDIR"]) / "nav_stale_gate" / "cef_nav_lag1.parquet"))
        TL = TL.reindex(index=T.index, columns=T.columns)
        H0 = bf.band(T, bf.BAND_WIDTH)
        first = harness.held(H0).abs().sum(axis=1).gt(0).idxmax()
        nav = pd.read_parquet(src[1]).pivot(index="date", columns="ticker", values="nav").sort_index()
        nav.index = pd.to_datetime(nav.index)
        am = (nav / nav.ffill().shift(1) - 1.0).abs().reindex(index=T.index, columns=T.columns)
        rank = am.loc[first:].stack().rank(pct=True).unstack().reindex(index=T.index, columns=T.columns)
        shares = [x["stale_share"] for x in out["stale_share_by_abs_move_quintile"]]
        prob = pd.DataFrame(0.0, index=T.index, columns=T.columns)
        for i, sh in enumerate(shares):
            prob = prob.mask((rank > i / 5) & (rank <= (i + 1) / 5), sh)
        prob = prob.mask(am < 0.5e-4, 0.0)        # a NAV that did not move cannot be a confirmed stale copy
        rng = np.random.default_rng(20261119)

        def sr(H):
            p = harness.evaluate(H, R)["pnl"].loc[first:]
            return float(p.mean() / p.std() * 252 ** 0.5), float(p.mean() * 252)
        base = sr(H0)
        res = np.array([sr(bf.band(T.where(~(pd.DataFrame(rng.random(T.shape), index=T.index, columns=T.columns) < prob), TL), bf.BAND_WIDTH))
                        for _ in range(200)])
        out["cost_under_measured_clustering"] = {
            "true_sharpe": round(base[0], 3), "true_ret": round(base[1], 5), "mean_stale_prob": round(float(prob.loc[first:].stack().mean()), 4),
            "stale_sharpe_mean_p05_p95": [round(float(res[:, 0].mean()), 3), round(float(np.percentile(res[:, 0], 5)), 3), round(float(np.percentile(res[:, 0], 95)), 3)],
            "stale_ret_mean_p05_p95": [round(float(res[:, 1].mean()), 5), round(float(np.percentile(res[:, 1], 5)), 5), round(float(np.percentile(res[:, 1], 95)), 5)]}
    Path(__file__).with_name("checks.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
