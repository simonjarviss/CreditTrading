"""Checks on the Russell bottom-edge test. NONE pre-specified: written 2026-11-18, after
explore.py's first run had been read, to see what the result does and does not rest on.

    python3 results/ideas/russell_micro_boundary/checks.py

  by year        the yearly sums of the series the card quotes, and their t without the two
                 best years: 25 events is a small sample and one year can carry it.
  prediction     the only test of the predicted sets available without the licensed lists:
                 the share of each set whose reconstitution-day dollar volume is at least 5
                 times its 21-session median, by era and by distance from the cut. A true
                 addition or deletion trades many times its usual volume that day; a
                 non-member that stays out should not.
  confirmed      the after-reconstitution trade with membership CONFIRMED by that volume:
                 decided at the close of F (the volume is public then), filled at the close
                 of F+1, held 20 and 60 sessions. If the reversal is real and diluted by
                 wrong predictions it should be larger here; if not, it is not the index.
                 Uses F's volume at the F close: no lookahead (asserted through book()).
  stayers        an observation the first run threw up, not a claim made in advance:
                 members that stay (STAY_IN) rose against IWM into reconstitution. Is it
                 above non-members just below (STAY_OUT), within the same liquidity half,
                 and is it there in the same shares one year later (the placebo)?
  cut            the company value at predicted rank 3000 each year (to compare with what
                 FTSE Russell publishes; not compared here: no published figure was fetched).
Writes checks.json beside this file (aggregates only).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE))
import explore as ex  # noqa: E402  (this directory's explore.py; it imports scripts.research.explore itself)
import universe  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
CONFIRM = 5.0
ex.WINDOWS["B confirmed, 20 sessions from F+1"] = (("F", 0), ("F", 19))
ex.WINDOWS["B confirmed, 60 sessions from F+1"] = (("F", 0), ("F", 59))


def years(p: pd.Series) -> pd.Series:
    y = p.groupby(p.index.year).sum()
    return y.reindex(range(universe.FIRST_YEAR, universe.LAST_YEAR + 1)).dropna()


def yr_line(tag, p, out):
    y = years(p)
    t = lambda s: float(s.mean() / s.std() * np.sqrt(len(s)))
    trimmed = y.sort_values().iloc[:-2] if y.mean() > 0 else y.sort_values().iloc[2:]
    out[tag] = {"mean_per_year": float(y.mean()), "t_years": t(y), "positive_years": int((y > 0).sum()), "years": int(len(y)),
                "mean_without_two_best_years": float(trimmed.mean()), "t_without_two_best_years": t(trimmed),
                "by_year": {int(k): round(float(v), 4) for k, v in y.items()}}
    o = out[tag]
    print(f"  {tag:<58} {o['mean_per_year'] * 100:+.2f}% a year (t {o['t_years']:+.2f}, {o['positive_years']}/{o['years']} up); "
          f"without its two best years {o['mean_without_two_best_years'] * 100:+.2f}% (t {o['t_without_two_best_years']:+.2f})")
    print("      " + " ".join(f"{str(k)[2:]}:{v * 100:+.0f}" for k, v in y.items()))


def main() -> int:
    W, iwm, cal, sets, sessions = ex.load()
    out = {"note": "not pre-specified", "panel_last_date": str(W["ret"].index.max().date())}
    desc, a = ex.describe(W, cal, sets)
    core = {s: sets[sets["set"] == s] for s in ("ADD", "DEL", "STAY_IN", "STAY_OUT")}

    print("== prediction: share of each set trading at least 5 times its usual dollar volume on reconstitution day")
    a["confirmed"] = a["recon_volume_ratio"] >= CONFIRM
    a["era"] = pd.cut(a["year"], [2000, 2008, 2015, 2019, 2022, 2025], labels=list(ex.ERAS))
    pq = a[a["set"].isin(core)].groupby(["set", "era"], observed=True)["confirmed"].mean().unstack()
    pq["all"] = a[a["set"].isin(core)].groupby("set")["confirmed"].mean()
    print((pq * 100).round(0).to_string())
    out["share_confirmed_by_volume"] = {s: {str(k): float(v) for k, v in r.items()} for s, r in pq.iterrows()}
    a["dist"] = (a["rank"] - universe.CUT).abs()
    a["band"] = pd.cut(a["dist"], [-1, 100, 250, 500], labels=["within 100 ranks", "101-250", "251-500"])
    bd = a[a["set"].isin(core)].groupby(["set", "band"], observed=True)["confirmed"].mean().unstack()
    print((bd * 100).round(0).to_string())
    out["share_confirmed_by_distance_from_cut"] = {s: {str(k): float(v) for k, v in r.items()} for s, r in bd.iterrows()}

    print("\n== cut: company value at predicted rank 3000, $M")
    cut = {}
    rd = pd.read_parquet(ex.RES / "russell_micro_boundary" / "rankdays.parquet")
    for y in range(universe.FIRST_YEAR, universe.LAST_YEAR + 1):
        c = universe.rank_universe(rd[rd["date"] == cal.loc[y, "rank_day"]])
        cut[y] = float(c.loc[c["rank"] == universe.CUT, "co_cap"].iloc[0] / 1000)
    print("  " + " ".join(f"{y}:{v:.0f}" for y, v in cut.items()))
    out["company_value_at_rank_3000_usd_m"] = cut

    print("\n== by year (sums of daily P&L inside each year's window, % of notional)")
    pnl, info, bh = ex.run(W, iwm, cal, sets, sessions, subsets=core)
    P = lambda w, s: pnl[(w, s)]
    b20, b60, bs, a1, a2 = "B after, 20 sessions", "B after, 60 sessions", "B after, 20 sessions, one-session skip", "A before (r+1 to F-1)", "A' before, into the F close"
    yb = out["by_year"] = {}
    yr_line("A: ADD against IWM, before", P(a1, "ADD"), yb)
    yr_line("A: ADD less STAY_IN, before", P(a1, "ADD") - P(a1, "STAY_IN"), yb)
    yr_line("B20: DEL less ADD", P(b20, "DEL") - P(b20, "ADD"), yb)
    yr_line("B20: DEL against IWM", P(b20, "DEL"), yb)
    yr_line("B20: DEL less STAY_OUT", P(b20, "DEL") - P(b20, "STAY_OUT"), yb)
    yr_line("B20: ADD against IWM (a short earns the opposite)", P(b20, "ADD"), yb)
    yr_line("B20: ADD less STAY_IN", P(b20, "ADD") - P(b20, "STAY_IN"), yb)
    yr_line("B20 with a one-session skip: ADD less STAY_IN", P(bs, "ADD") - P(bs, "STAY_IN"), yb)
    yr_line("B60: DEL less ADD", P(b60, "DEL") - P(b60, "ADD"), yb)
    yr_line("B60: DEL against IWM", P(b60, "DEL"), yb)
    yr_line("B60: DEL less STAY_OUT", P(b60, "DEL") - P(b60, "STAY_OUT"), yb)
    yr_line("B60: ADD less STAY_IN", P(b60, "ADD") - P(b60, "STAY_IN"), yb)

    print("\n== confirmed: decided at the F close on F's own volume, filled at F+1")
    conf = {}
    for s in ("ADD", "DEL", "STAY_IN", "STAY_OUT"):
        g = a[a["set"] == s]
        conf[f"{s} confirmed"] = g[g["confirmed"]]
        conf[f"{s} not confirmed"] = g[~g["confirmed"]]
    keep = dict(ex.WINDOWS)
    ex.WINDOWS = {k: v for k, v in keep.items() if k.startswith("B confirmed")}
    pc, ic, bc = ex.run(W, iwm, cal, sets, sessions, subsets=conf)
    ex.WINDOWS = keep
    oc = out["confirmed_by_volume"] = {}
    for w in ("B confirmed, 20 sessions from F+1", "B confirmed, 60 sessions from F+1"):
        print(f"  {w}")
        o = oc[w] = {}
        for s in conf:
            i, n = ic[(w, s)], ex.name_stats(bc[(w, s)])
            yr_line(f"{s} against IWM ({i['names_per_year']:.0f}/yr)", pc[(w, s)], o)
            o[f"{s} against IWM ({i['names_per_year']:.0f}/yr)"]["per_name"] = n
            if n["n"]:
                print(f"      per name: mean {n['mean'] * 100:+.2f}%  median {n['median'] * 100:+.2f}%  at the quote {n['mean_bought_at_ask_sold_at_bid'] * 100:+.2f}%")
        yr_line("DEL confirmed less ADD confirmed", pc[(w, "DEL confirmed")] - pc[(w, "ADD confirmed")], o)
        yr_line("DEL confirmed less DEL not confirmed", pc[(w, "DEL confirmed")] - pc[(w, "DEL not confirmed")], o)
        yr_line("ADD confirmed less ADD not confirmed", pc[(w, "ADD confirmed")] - pc[(w, "ADD not confirmed")], o)
        yr_line("DEL confirmed less STAY_OUT not confirmed", pc[(w, "DEL confirmed")] - pc[(w, "STAY_OUT not confirmed")], o)
        yr_line("ADD confirmed less STAY_IN (all)", pc[(w, "ADD confirmed")] - pc[(w, "STAY_IN confirmed")] * 0 - (
            pc[(w, "STAY_IN confirmed")] * ic[(w, "STAY_IN confirmed")]["events"] + pc[(w, "STAY_IN not confirmed")] * ic[(w, "STAY_IN not confirmed")]["events"])
            / (ic[(w, "STAY_IN confirmed")]["events"] + ic[(w, "STAY_IN not confirmed")]["events"]), o)

    print("\n== stayers: members that stay against non-members just below, before reconstitution")
    os_ = out["stayers_before"] = {}
    liq = a[a["set"].isin(["STAY_IN", "STAY_OUT"])]
    sub = {f"{s}, {'liquid' if k else 'thin'}": liq[(liq["set"] == s) & ((liq["adv21"] >= ex.LIQUID_ADV) == k)] for s in ("STAY_IN", "STAY_OUT") for k in (True, False)}
    ex.WINDOWS = {k: v for k, v in keep.items() if k.startswith("A")}
    p2, _, _ = ex.run(W, iwm, cal, sets, sessions, subsets=sub)
    p3, _, _ = ex.run(W, iwm, cal, sets, sessions, calendar_shift=1, subsets={**{k: core[k] for k in ("STAY_IN", "STAY_OUT")}, **sub})
    ex.WINDOWS = keep
    for w in (a1, a2):
        print(f"  {w}")
        o = os_[w] = {}
        yr_line("STAY_IN against IWM", P(w, "STAY_IN"), o)
        yr_line("STAY_IN less STAY_OUT", P(w, "STAY_IN") - P(w, "STAY_OUT"), o)
        yr_line("STAY_IN less STAY_OUT, both liquid", p2[(w, "STAY_IN, liquid")] - p2[(w, "STAY_OUT, liquid")], o)
        yr_line("STAY_IN less STAY_OUT, both thin", p2[(w, "STAY_IN, thin")] - p2[(w, "STAY_OUT, thin")], o)
        yr_line("PLACEBO a year later: STAY_IN against IWM", p3[(w, "STAY_IN")], o)
        yr_line("PLACEBO a year later: STAY_IN less STAY_OUT", p3[(w, "STAY_IN")] - p3[(w, "STAY_OUT")], o)
        yr_line("PLACEBO a year later: the same, both liquid", p3[(w, "STAY_IN, liquid")] - p3[(w, "STAY_OUT, liquid")], o)
    (HERE / "checks.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
