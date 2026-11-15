"""Merger premium in targets too small for arbitrage funds. A size band on the 2026-11-12 book.

    python3 results/ideas/merger_arb/micro.py

WHY: the team lead asked on 2026-11-15 for ideas in undersized markets a small book can
exploit. The merger-premium book (explore.py) required $5 and $1M a day and found that
among those, larger targets did better. Targets below that floor were never looked at: a
fund cannot put a position on in a share trading $300,000 a day, so the spread there has
fewer buyers. Whether it is wider, or just riskier, is the question.

FIXED BEFORE ANY RETURN IN THIS BAND WAS READ (2026-11-15):
  DEALS     explore.py's: all-cash SDC 'Merger' bids for US targets linked to a CRSP common
            share, marked Friendly (the correction the first test needed), one-step and
            tender offers together.
  BAND      at the close of the first session after the announcement: price >= $2 and
            21-session average dollar volume from $100,000 to under $1,000,000.
            The comparison band is the original one, price >= $5 and $1M or more, friendly.
  BOOK      explore.py's functions, imported: entered at that close's decision, held until
            the target stops trading, the session after SDC's withdrawal date, or 252
            sessions; equal weights; flat under 5 live deals; shift(2); gross.
  REPORTED  raw Sharpe; Sharpe over bills (a cash deal's spread includes the bill rate);
            halves and eras; beta and alpha against SPY over bills; worst drawdown; live
            deals a day; share of deals withdrawn; mean return per deal over its life.
  EXPECTED  over bills, above the original band's 0.48.
NOT MODELLED: the spread (not staged for these rows), and SDC's final status is not read by
any rule. The staging keeps deals of every final status that SDC recorded as announced; the
card of 2026-11-12 says which selection remains.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ma", HERE / "explore.py")
ma = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ma)
ERAS = {"2000-07": ("2000", "2007"), "2008-12": ("2008", "2012"), "2013-17": ("2013", "2017"),
        "2018-22": ("2018", "2022"), "2023-25": ("2023", "2025")}


def main() -> int:
    d, ret, prc, dv, trading = ma.load()
    sessions = ret.index
    R = ret.fillna(0.0)
    mk = pd.read_parquet(ma.MKT)
    spy = mk[mk["ticker"] == "SPY"].set_index("date")["ret_total"].reindex(sessions)
    rf = pd.read_parquet(ma.RF).set_index("date")["rf_daily"].reindex(sessions).ffill()
    mkt_x = spy - rf
    adv = dv.rolling(21, min_periods=10).mean().to_numpy()
    start = pd.Timestamp("2000-02-01")
    out = {"panel_last_date": str(sessions.max().date())}
    for label, min_price, lo, hi in (("micro: $2, $100k to $1M a day", 2.0, 1e5, 1e6), ("original: $5, $1M and over", 5.0, 1e6, np.inf),
                                     ("between: $2, $1M to $5M", 2.0, 1e6, 5e6)):
        ma.MIN_PRICE, ma.MIN_ADV = min_price, lo
        sp = ma.spells(d, sessions, prc, dv, trading)
        a0 = adv[np.minimum(sp["i0"].to_numpy(), len(sessions) - 1), sp["col"].to_numpy()]
        g = sp[(sp["attitude"] == "Friendly") & (np.nan_to_num(a0) < hi)]
        act = ma.active_matrix(g, ret.shape)
        H = ma.long_only(act, sessions, ret.columns)
        ev = harness.evaluate(H, R)
        pnl = ev["pnl"].loc[start:]
        inv = H.shift(harness.EXEC_LAG).abs().sum(axis=1).reindex(pnl.index).fillna(0.0)
        xs = pnl - rf.reindex(pnl.index) * inv
        ge = g[g["eligible"]]
        n_act = pd.Series(act.sum(axis=1), index=sessions).loc[start:]
        Rn = R.to_numpy()
        life = np.array([Rn[i0 + harness.EXEC_LAG:i1 + harness.EXEC_LAG + 1, c].sum() for i0, i1, c in ge[["i0", "i1", "col"]].itertuples(index=False)])
        o = {"deals_eligible": int(len(ge)), "deals_per_year": float(len(ge) / 25.9), "live_deals_median": float(n_act.median()),
             "flat_day_share": float((n_act < ma.MIN_NAMES).mean()), "share_withdrawn": float(ge["datewith"].notna().mean()),
             "held_sessions_median": float((ge["i1"] - ge["i0"] + 1).median()),
             "per_deal_return_pct": {"mean": float(life.mean() * 100), "median": float(np.median(life) * 100), "p5": float(np.quantile(life, .05) * 100),
                                     "worst": float(life.min() * 100), "share_positive": float((life > 0).mean())},
             "raw": explore.stats(pnl), "over_bills": explore.stats(xs), "market": ma.market_fit(xs, mkt_x),
             "over_bills_by_era": {k: explore.stats(xs.loc[a:b])["sharpe"] for k, (a, b) in ERAS.items()},
             "over_bills_halves": [explore.stats(xs.iloc[:len(xs) // 2])["sharpe"], explore.stats(xs.iloc[len(xs) // 2:])["sharpe"]]}
        out[label] = o
        print(f"\n== {label}: deals {o['deals_eligible']} ({o['deals_per_year']:.0f}/yr) | live a day {o['live_deals_median']:.0f} | flat {o['flat_day_share']:.0%} | withdrawn {o['share_withdrawn']:.1%} | held {o['held_sessions_median']:.0f} sessions")
        print(f"   raw SR {o['raw']['sharpe']:.2f} (t {o['raw']['t']:.2f}) ret/yr {o['raw']['ann_ret']:.2%} vol {o['raw']['ann_vol']:.2%} dd {o['raw']['max_drawdown']:.1%} | over bills SR {o['over_bills']['sharpe']:.2f} (t {o['over_bills']['t']:.2f}) {o['over_bills']['ann_ret']:.2%}/yr | halves {o['over_bills_halves'][0]:.2f}/{o['over_bills_halves'][1]:.2f}")
        print("   over bills by era:", " ".join(f"{k}:{v:.2f}" for k, v in o["over_bills_by_era"].items()), "| market fit:", {k: round(v, 3) for k, v in o["market"].items() if isinstance(v, float)})
        print("   per deal %:", {k: round(v, 2) for k, v in o["per_deal_return_pct"].items()})
    (HERE / "micro.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
