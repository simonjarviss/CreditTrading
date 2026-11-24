"""Checks on the share-class pairs book. NONE pre-specified: written 2026-11-18, after
explore.py's first and only run, to see whether the result survives the obvious objections.

    python3 results/ideas/dual_class_pairs/checks.py

Everything here re-uses explore.py's own functions and constants; nothing about the rule is
changed. It rebuilds the pre-specified trades and cuts them:

  exit reason      how each trade ended (gap closed, 20 sessions up, a leg left CRSP), and the
                   buy-and-hold result of each group: is the profit the ordinary closing of a
                   gap, or a few conversions and takeovers?
  by pair          how concentrated the profit is: the share of the summed trade return from
                   the five best pairs, and the mean trade without them.
  by liquidity     trades split on the thinner leg's 21-session dollar volume. The desk's
                   thesis is that the THIN pairs pay; this says where the money is.
  after the quote  each trade's buy-and-hold return less the two legs' quoted spreads known at
                   entry (half a spread per leg in, half out). A real-money view, labelled; the
                   desk's headline stays gross.
  cost grid        the book's return less turnover x 5 / 15 / 30 bp (the house grid).
  by era           mean buy-and-hold trade by era, closing prices and mid quotes.
  tails            the worst trades.

Aggregates only are written (checks.json).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dcp_explore", HERE / "explore.py")
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)

assert pd.get_option("compute.use_numexpr") is False
ERAS = {"2000-01": ("2000", "2001"), "2002-08": ("2002", "2008"), "2009-15": ("2009", "2015"), "2016-19": ("2016", "2019"),
        "2020-22": ("2020", "2022"), "2023-25": ("2023", "2025")}


def cut(t: pd.DataFrame) -> dict:
    """The few figures every cut shows. t-statistics treat trades as independent, which
    overstates them: trades in different pairs overlap in time."""
    if len(t) < 3:
        return {"trades": int(len(t))}
    o = {"trades": int(len(t)), "pairs": int(t["pair"].nunique())}
    for tag in ("close", "mid"):
        x = t[f"bh_{tag}"]
        o[f"{tag}_mean_bp"] = float(x.mean() * 1e4)
        o[f"{tag}_median_bp"] = float(x.median() * 1e4)
        o[f"{tag}_t"] = float(x.mean() / x.std() * np.sqrt(len(x)))
    o["median_two_leg_spread_bp"] = float(t["cost"].median() * 1e4)
    o["mean_two_leg_spread_bp"] = float(t["cost"].mean() * 1e4)
    o["close_less_quoted_spread_mean_bp"] = float((t["bh_close"] - t["cost"]).mean() * 1e4)
    o["median_adv_thinner_leg_usd"] = float(t[["adv_long", "adv_short"]].min(axis=1).median())
    o["median_sessions_held"] = float(t["sessions_held"].median())
    return o


def main() -> int:
    w = ex.load()
    dates = w["ret"].index
    col = {p: i for i, p in enumerate(w["ret"].columns)}
    pairs = pd.read_parquet(ex.RES / "pairs.parquet")
    ia = np.array([col[p] for p in pairs["permno_a"]]); ib = np.array([col[p] for p in pairs["permno_b"]])
    sig = ex.signals(w, w["ret"], ia, ib, gate=True)
    pos, trades = ex.simulate(sig)
    tt = ex.trade_table(trades, sig, w, ia, ib, dates)
    # exit reason, from the same arrays simulate() read
    T = len(dates)
    reason = {}
    for p, e, x, side in trades:
        if x >= T:
            r = "open at panel end"
        elif not sig["present"][x, p]:
            r = "a leg left CRSP"
        elif x - e >= ex.MAX_HOLD:
            r = "20 sessions up"
        else:
            r = "gap closed"
        reason[(p, dates[e])] = r
    tt["reason"] = [reason[(r.pair, r.entry)] for r in tt.itertuples()]
    tt = tt[tt["entry"] >= ex.FIRST].copy()
    out = {"note": "not pre-specified", "panel_last_date": str(dates[-1].date()), "all": cut(tt)}
    pr = lambda k, v: print(f"  {k:<44}", {a: (round(b, 1) if isinstance(b, float) else b) for a, b in v.items()})
    print("all trades"); pr("all", out["all"])

    print("by exit reason")
    out["by_exit_reason"] = {k: cut(g) for k, g in tt.groupby("reason")}
    for k, v in out["by_exit_reason"].items():
        pr(k, v)

    print("by pair (concentration)")
    by = tt.groupby("pair")["bh_close"].agg(["sum", "size"]).sort_values("sum", ascending=False)
    top5 = by.index[:5]
    out["by_pair"] = {"pairs_traded": int(len(by)), "pairs_with_positive_sum": int((by["sum"] > 0).sum()),
                      "share_of_summed_return_from_5_best_pairs": float(by["sum"].iloc[:5].sum() / by["sum"].sum()),
                      "share_of_trades_in_5_best_pairs": float(by["size"].iloc[:5].sum() / by["size"].sum()),
                      "share_of_trades_in_10_most_traded_pairs": float(by["size"].sort_values(ascending=False).iloc[:10].sum() / by["size"].sum()),
                      "without_5_best_pairs": cut(tt[~tt["pair"].isin(top5)])}
    pr("concentration", {k: v for k, v in out["by_pair"].items() if not isinstance(v, dict)})
    pr("without the 5 best pairs", out["by_pair"]["without_5_best_pairs"])

    print("by the thinner leg's dollar volume at entry")
    thin = tt[["adv_long", "adv_short"]].min(axis=1)
    out["by_thinner_leg_adv"] = {}
    for name, lo, hi in (("under $500k", 0, 5e5), ("$500k to $2M", 5e5, 2e6), ("$2M to $10M", 2e6, 1e7), ("$10M and over", 1e7, np.inf)):
        out["by_thinner_leg_adv"][name] = cut(tt[(thin >= lo) & (thin < hi)])
        pr(name, out["by_thinner_leg_adv"][name])

    print("by era (entry date)")
    out["by_era"] = {k: cut(tt[(tt["entry"] >= a) & (tt["entry"] <= f"{b}-12-31")]) for k, (a, b) in ERAS.items()}
    for k, v in out["by_era"].items():
        pr(k, v)

    print("short leg is the more liquid class and trades $1M a day or more (borrow plausible), against the rest")
    easy = (tt["adv_short"] >= tt["adv_long"]) & (tt["adv_short"] >= ex.LIQUID_SHORT_ADV)
    out["borrow"] = {"short leg liquid": cut(tt[easy]), "the rest": cut(tt[~easy])}
    for k, v in out["borrow"].items():
        pr(k, v)

    x = tt["bh_close"]
    out["tails"] = {"p1_bp": float(x.quantile(0.01) * 1e4), "p5_bp": float(x.quantile(0.05) * 1e4), "p95_bp": float(x.quantile(0.95) * 1e4),
                    "p99_bp": float(x.quantile(0.99) * 1e4), "worst_bp": float(x.min() * 1e4), "best_bp": float(x.max() * 1e4),
                    "mean_without_20_best_bp": float(x.sort_values().iloc[:-20].mean() * 1e4),
                    "mean_without_20_worst_bp": float(x.sort_values().iloc[20:].mean() * 1e4)}
    print("tails"); pr("trade return, closing prices", out["tails"])

    # the house cost grid on the book: mean return less mean turnover x bp. Volatility is left as
    # the gross book's (a constant charge per unit traded moves it very little); labelled so.
    pnl, info = ex.book(pos, ia, ib, w["ret"])
    s = ex.explore.stats(pnl)
    out["cost_grid"] = {"gross_ann_ret": s["ann_ret"], "ann_vol": s["ann_vol"], "turnover_per_year": info["turnover_per_year"],
                        **{f"net_ann_ret_{bp}bp": float(s["ann_ret"] - info["turnover_per_year"] * bp / 1e4) for bp in (5, 15, 30)},
                        **{f"net_sharpe_{bp}bp_at_gross_vol": float((s["ann_ret"] - info["turnover_per_year"] * bp / 1e4) / s["ann_vol"]) for bp in (5, 15, 30)}}
    print("cost grid"); pr("book", out["cost_grid"])
    # per unit of gross actually invested, so the figure can be compared with other cards
    out["return_per_unit_gross"] = float(s["ann_ret"] / info["mean_gross"])
    print("  return a year per unit of gross held:", round(out["return_per_unit_gross"], 4))
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
