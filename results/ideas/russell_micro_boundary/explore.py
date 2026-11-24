"""Explore: the bottom edge of the Russell 2000, predicted from public market-value ranks.

    QUANTT_ENV_FILE=<env> python3 results/ideas/russell_micro_boundary/stage.py
    python3 results/ideas/russell_micro_boundary/explore.py

WHY: each June the Russell 2000 is rebuilt from a ranking of US companies by market value
taken weeks earlier (rank day). Funds tracking it must buy what enters and sell what leaves
at the reconstitution close. The top edge (rank 1000) and the big additions are crowded. The
BOTTOM edge, companies crossing rank 3000 between the index and the micro-cap zone, is a few
hundred companies of $50M to $300M that a large fund cannot trade in size. A book of $100k
to $1M can, and the ranking is public arithmetic. The team lead asked on 2026-11-16 for
index-arbitrage ideas "on things big money can't exploit". No Russell test is in
results/ideas/ or the KILLED table (the only index-rebalance entry, SCR-IDX-REBAL, is
fund-of-CEF indices).

FIXED BEFORE ANY RETURN WAS READ (2026-11-16). Only the rules and the staged row counts had
been read. The calendar, the universe and the eight predicted sets are in universe.py
(same date); this file fixes the trades.
  F          the reconstitution day (index funds trade at its close); r the rank day.
  TEST A (before)   long the predicted additions ADD, equal weights, 100%, against IWM 100%
             short. Decided at the rank-day close r, filled at the close of r+1, held to the
             close of F-1 (the session before reconstitution). Under shift(2) the weights
             are on rows r .. F-3 and earn the returns of r+2 .. F-1.
             Stated variant A': the same held INTO the reconstitution close (rows r .. F-2),
             because selling in that auction is what a trader would do.
  TEST B (after)    the reversal: long DEL (predicted deletions) and short ADD, equal
             weights, 100% a side, entered at the close of F (decided at F-1) and held 20
             and 60 sessions (rows F-1 .. F+18 and F-1 .. F+58). Reported also as DEL long
             against IWM alone, since additions this small may not be borrowable.
  CONTROLS   (1) the neighbours that do NOT change membership, in the same windows:
             STAY_IN for ADD (same rank zone 2501-3000, already members) and STAY_OUT for DEL
             (rank 3001-3500, already outside). The claim is about crossing the line, so it
             needs ADD above STAY_IN before, and DEL above STAY_OUT after. A result that the
             changers and the stayers share is small-cap momentum or reversal, not the index.
             (2) the same shares in the same windows ONE YEAR LATER (year y's sets on year
             y+1's calendar; shares that have delisted by then drop out, stated).
  SECONDARY, stated: ADD_ALL / DEL_ALL (every predicted crosser, not only those near the
             line), ADD_CLEAR / DEL_CLEAR (more than 100 ranks from the line), a split of
             ADD and DEL at $500,000 of 21-session average dollar volume on rank day, and a
             one-session skip on test B (entered at the close of F+1), because the F close
             is the forced print and a deletion bought there may simply bounce off the bid.
  ALSO REPORTED (not a trade): per-name buy-and-hold excess returns over IWM, which do not
             rebalance daily to equal weights as the harness book does; the same after
             buying at the closing ask and selling at the closing bid; t statistics on the
             25 yearly sums (one event a year: the days inside a year are not independent
             bets); rank-day price, market value, dollar volume and closing spread of each
             set; and reconstitution-day dollar volume over its usual level, which is the
             only check of the prediction available without the licensed lists: if predicted
             crossers do not trade far more than predicted stayers that day, the sets are wrong.
  EXPECTED   A: ADD positive against IWM and above STAY_IN, larger before 2010 than after.
             B: DEL above ADD and above STAY_OUT over 20 sessions; weaker at 60.
  LOOKAHEAD  every set uses rank-day closes only (asserted: no weight before row r), except
             the Compustat headquarters country, which is today's header (universe.py).
  MISSING RETURNS on a held share (no CRSP return that session, or after its delisting
             return) are booked as zero and COUNTED per book; nothing else is filled.
Gross; no cost is modelled. Writes results.json beside this file (aggregates only).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(HERE))
from scripts.research import explore, harness  # noqa: E402
import universe  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
RES = Path.home() / "quantt_research"
LIQUID_ADV = 500_000.0
# window name -> (first weight row, last weight row), as offsets; "r" from the rank day, "F" from reconstitution day
WINDOWS = {"A before (r+1 to F-1)": (("r", 0), ("F", -3)), "A' before, into the F close": (("r", 0), ("F", -2)),
           "B after, 20 sessions": (("F", -1), ("F", 18)), "B after, 60 sessions": (("F", -1), ("F", 58)),
           "B after, 20 sessions, one-session skip": (("F", 0), ("F", 18))}
ERAS = {"2001-08": (2001, 2008), "2009-15": (2009, 2015), "2016-19": (2016, 2019), "2020-22": (2020, 2022), "2023-25": (2023, 2025)}


def load():
    px = pd.read_parquet(RES / "russell_micro_boundary" / "daily.parquet")
    px["date"] = pd.to_datetime(px["date"])
    W = {c: px.pivot(index="date", columns="permno", values=c) for c in ("ret", "prc", "bid", "ask", "dollar_volume", "vol")}
    W["prc"] = W["prc"].abs()
    rd = pd.read_parquet(RES / "russell_micro_boundary" / "rankdays.parquet")
    yf = pd.read_parquet(RES / "yf_daily.parquet")
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"]
    top = pd.read_parquet(RES / "crsp_top4500_daily.parquet", columns=["date"])
    sessions = pd.DatetimeIndex(pd.to_datetime(top["date"]).unique()).sort_values()
    cal = universe.calendar(sessions)
    sets = universe.build_sets(rd, cal)
    panel = W["ret"].index
    for y in range(universe.FIRST_YEAR, universe.LAST_YEAR + 1):      # the staged months must hold every window whole
        i, j = sessions.get_loc(cal.loc[y, "rank_day"]), sessions.get_loc(cal.loc[y, "recon_day"])
        need = sessions[i - 21:j + 62]
        if not need.isin(panel).all():
            raise ValueError(f"{y}: the staged daily panel does not cover {need[0].date()} .. {need[-1].date()}")
    if iwm.reindex(panel).isna().any():
        raise ValueError("IWM has no return on a session of the daily panel")
    return W, iwm.reindex(panel), cal, sets, sessions


def rows_for(cal_y, panel, window):
    (a0, a1), (b0, b1) = WINDOWS[window]
    pos = {"r": panel.get_loc(cal_y["rank_day"]), "F": panel.get_loc(cal_y["recon_day"])}
    return pos[a0] + a1, pos[b0] + b1


def book(W, iwm, names, first, last, r_pos):
    """Equal-weight long `names` against IWM with weights on panel rows first..last. Returns pnl, info."""
    panel = W["ret"].index
    if first < r_pos:
        raise harness.LookaheadError("a weight is dated before the rank day that defines the set")
    names = [n for n in names if n in W["prc"].columns and pd.notna(W["prc"].iat[first, W["prc"].columns.get_loc(n)])]
    sl = slice(first - 3, last + harness.EXEC_LAG + 2)
    idx = panel[sl]
    if (idx[-1] - idx[0]).days > 200:
        raise ValueError("a window spans the months the panel does not hold")
    if not names:
        return pd.Series(0.0, index=idx), {"n": 0, "missing": 0, "held": 0, "turn": 0.0}
    raw = W["ret"].loc[idx, names]
    R = raw.fillna(0.0); R["IWM"] = iwm.loc[idx]
    H = pd.DataFrame(0.0, index=idx, columns=R.columns)
    H.iloc[3:3 + last - first + 1, :-1] = 1.0 / len(names)
    H["IWM"] = -H.iloc[:, :-1].sum(axis=1)
    res = harness.evaluate(H, R)
    held = harness.held(H[names]) != 0
    return res["pnl"], {"n": len(names), "missing": int((held & raw.isna()).sum().sum()), "held": int(held.sum().sum()),
                        "turn": float(H.diff().abs().sum().sum()),
                        "zero_volume": int((held & ~(W["vol"].loc[idx, names] > 0)).sum().sum())}


def per_name(W, iwm, names, first, last):
    """Buy-and-hold per name over the same returns the book earns, less IWM; and the same bought at the ask, sold at the bid."""
    panel = W["ret"].index
    e, x = first + 1, last + harness.EXEC_LAG                       # filled at the close of row e, out at the close of row x
    names = [n for n in names if n in W["prc"].columns and pd.notna(W["prc"].iat[first, W["prc"].columns.get_loc(n)])]
    if not names:
        return pd.DataFrame(columns=["bh", "bh_quote"])
    seg = W["ret"].iloc[e + 1:x + 1][names].fillna(0.0)
    bh = (1 + seg).prod() - 1
    bench = (1 + iwm.iloc[e + 1:x + 1]).prod() - 1
    ask_e, prc_e = W["ask"].iloc[e][names], W["prc"].iloc[e][names]
    last_row = W["prc"].iloc[e:x + 1][names].ffill().iloc[-1]         # the share's own last close inside the window (delisting)
    bid_x = W["bid"].iloc[e:x + 1][names].ffill().iloc[-1]
    ok = (ask_e > 0) & (bid_x > 0) & (ask_e >= prc_e * 0.5) & (bid_x <= last_row * 1.5)
    quote = ((1 + bh) * (bid_x / last_row) / (ask_e / prc_e) - 1).where(ok)
    return pd.DataFrame({"bh": bh - bench, "bh_quote": quote - bench})


def yearly(pnl: pd.Series) -> dict:
    y = pnl.groupby(pnl.index.year).sum()
    y = y.reindex(range(universe.FIRST_YEAR, universe.LAST_YEAR + 1)).dropna()
    out = {"years": int(len(y)), "mean_per_year": float(y.mean()), "t_years": float(y.mean() / y.std() * np.sqrt(len(y))) if y.std() > 0 else None,
           "positive_years": int((y > 0).sum())}
    for k, (a, b) in ERAS.items():
        out[k] = float(y.loc[a:b].mean()) if len(y.loc[a:b]) else None
    return out


def name_stats(df: pd.DataFrame) -> dict:
    if not len(df):
        return {"n": 0}
    ym = df.groupby("year")["bh"].mean()
    q = df["bh_quote"].dropna()
    out = {"n": int(len(df)), "mean": float(df["bh"].mean()), "median": float(df["bh"].median()), "positive": float((df["bh"] > 0).mean()),
           "mean_of_yearly_means": float(ym.mean()), "t_yearly_means": float(ym.mean() / ym.std() * np.sqrt(len(ym))) if len(ym) > 2 else None,
           "mean_without_20_best": float(df["bh"].sort_values().iloc[:-20].mean()) if len(df) > 40 else None,
           "n_with_quotes": int(len(q)), "mean_bought_at_ask_sold_at_bid": float(q.mean()) if len(q) else None,
           "median_bought_at_ask_sold_at_bid": float(q.median()) if len(q) else None}
    for k, (a, b) in ERAS.items():
        s = df[df["year"].between(a, b)]["bh"]
        out[k] = float(s.mean()) if len(s) else None
    return out


def run(W, iwm, cal, sets, sessions, *, calendar_shift=0, subsets=None):
    """Every set on every window. calendar_shift=1 puts year y's sets on year y+1's calendar (the placebo)."""
    panel = W["ret"].index
    full = sessions[(sessions >= "2001-01-01")]
    pnl, info, names_bh = {}, {}, {}
    groups = dict(subsets or {s: sets[sets["set"] == s] for s in universe.SETS})
    for window in WINDOWS:
        for sname, rows in groups.items():
            parts, inf, bh = [], [], []
            for y in range(universe.FIRST_YEAR, universe.LAST_YEAR + 1 - calendar_shift):
                cy = cal.loc[y + calendar_shift]
                first, last = rows_for(cy, panel, window)
                nm = rows.loc[rows["year"] == y, "permno"].tolist()
                p, i = book(W, iwm, nm, first, last, panel.get_loc(cal.loc[y, "rank_day"]))
                parts.append(p[p.index.isin(panel[first + harness.EXEC_LAG:last + harness.EXEC_LAG + 1])])
                inf.append(i)
                bh.append(per_name(W, iwm, nm, first, last).assign(year=y))
            s = pd.concat(parts)
            pnl[(window, sname)] = s.reindex(full).fillna(0.0)          # flat outside the windows: no position, no P&L
            ii = pd.DataFrame(inf)
            info[(window, sname)] = {"names_per_year": float(ii["n"].mean()), "names_min": int(ii["n"].min()), "events": int(ii["n"].sum()),
                                     "held_name_days": int(ii["held"].sum()), "held_name_days_without_return": int(ii["missing"].sum()),
                                     "held_name_days_zero_volume": int(ii["zero_volume"].sum()) if "zero_volume" in ii else 0,
                                     "turnover_per_year": float(ii["turn"].mean())}
            names_bh[(window, sname)] = pd.concat(bh, ignore_index=True)
    return pnl, info, names_bh


def describe(W, cal, sets) -> dict:
    """Rank-day liquidity of each set and reconstitution-day dollar volume over its usual level (medians)."""
    panel, out = W["ret"].index, {}
    rows = []
    for y in range(universe.FIRST_YEAR, universe.LAST_YEAR + 1):
        r, f = panel.get_loc(cal.loc[y, "rank_day"]), panel.get_loc(cal.loc[y, "recon_day"])
        g = sets[sets["year"] == y]
        nm = [n for n in g["permno"].unique() if n in W["dollar_volume"].columns]
        dv = W["dollar_volume"].iloc[r - 20:r + 1][nm]
        base = dv.median()
        d = pd.DataFrame({"adv21": dv.mean(), "recon_volume_ratio": W["dollar_volume"].iloc[f][nm] / base.where(base > 0),
                          "prior_week_volume_ratio": W["dollar_volume"].iloc[f - 5][nm] / base.where(base > 0)})
        rows.append(g.merge(d, left_on="permno", right_index=True, how="left"))
    a = pd.concat(rows, ignore_index=True)
    a["spread"] = ((a["ask"] - a["bid"]) / ((a["ask"] + a["bid"]) / 2)).where((a["bid"] > 0) & (a["ask"] >= a["bid"]))
    for s, g in a.groupby("set"):
        out[s] = {"events": int(len(g)), "per_year_mean": float(g.groupby("year").size().mean()), "per_year_min": int(g.groupby("year").size().min()),
                  "median_price": float(g["prc"].abs().median()), "median_company_value_usd": float(g["co_cap"].median() * 1000),
                  "median_adv21_usd": float(g["adv21"].median()), "share_adv_under_100k": float((g["adv21"] < 100_000).mean()),
                  "median_closing_spread": float(g["spread"].median()), "mean_closing_spread": float(g["spread"].mean()),
                  "median_recon_day_volume_ratio": float(g["recon_volume_ratio"].median()),
                  "median_volume_ratio_a_week_before": float(g["prior_week_volume_ratio"].median()),
                  "by_era": {k: {"events_per_year": float(len(e) / (b - a_ + 1)), "median_adv21_usd": float(e["adv21"].median()),
                                 "median_closing_spread": float(e["spread"].median()),
                                 "median_recon_day_volume_ratio": float(e["recon_volume_ratio"].median())}
                             for k, (a_, b) in ERAS.items() for e in [g[g["year"].between(a_, b)]]}}
    return out, a


def line(tag, p):
    s, yr = explore.stats(p), yearly(p)
    h = len(p) // 2
    eras = " ".join(f"{k} {yr[k] * 100:+.1f}%" for k in ERAS)
    print(f"  {tag:<34} SR {s['sharpe']:+.2f} (t {s['t']:+.2f})  per yr {yr['mean_per_year'] * 100:+.2f}% (t_yrs {yr['t_years']:+.2f}, {yr['positive_years']}/{yr['years']} up)  "
          f"halves {explore.stats(p.iloc[:h])['sharpe']:+.2f}/{explore.stats(p.iloc[h:])['sharpe']:+.2f}  | {eras}")
    return {**explore.summarise(p), "yearly": yr}


def report(pnl, info, bh, pairs, out, label=""):
    for window in WINDOWS:
        print(f"\n== {window}{label}")
        o = out.setdefault(window + label, {})
        for s in sorted({k[1] for k in pnl if k[0] == window}):
            i = info[(window, s)]
            o[s + " against IWM"] = {**line(f"{s} vs IWM ({i['names_per_year']:.0f}/yr)", pnl[(window, s)]), **i, "per_name": name_stats(bh[(window, s)])}
        for a, b in pairs:
            if (window, a) in pnl and (window, b) in pnl:
                o[f"{a} less {b}"] = line(f"{a} less {b}", pnl[(window, a)] - pnl[(window, b)])
        if all((window, k) in pnl for k in ("DEL", "ADD", "STAY_OUT", "STAY_IN")):
            dd = (pnl[(window, "DEL")] - pnl[(window, "ADD")]) - (pnl[(window, "STAY_OUT")] - pnl[(window, "STAY_IN")])
            o["(DEL less ADD) less (STAY_OUT less STAY_IN)"] = line("(DEL-ADD) less (STAY_OUT-STAY_IN)", dd)
        print("  per name, buy and hold less IWM:")
        for s in sorted({k[1] for k in pnl if k[0] == window}):
            n = name_stats(bh[(window, s)])
            if n["n"]:
                print(f"    {s:<10} n {n['n']:>5}  mean {n['mean'] * 100:+.2f}%  median {n['median'] * 100:+.2f}%  up {n['positive']:.0%}  t(yearly means) {n['t_yearly_means']:+.2f}  "
                      f"at the quote: mean {n['mean_bought_at_ask_sold_at_bid'] * 100:+.2f}% (n {n['n_with_quotes']})")


PAIRS = (("ADD", "STAY_IN"), ("DEL", "STAY_OUT"), ("DEL", "ADD"), ("STAY_OUT", "STAY_IN"), ("ADD_ALL", "STAY_IN"), ("DEL_ALL", "STAY_OUT"),
         ("DEL_ALL", "ADD_ALL"), ("ADD_CLEAR", "STAY_IN"), ("DEL_CLEAR", "STAY_OUT"), ("DEL_CLEAR", "ADD_CLEAR"))


def main() -> int:
    W, iwm, cal, sets, sessions = load()
    out = {"panel_last_date": str(W["ret"].index.max().date()), "iwm_last_date_used": str(iwm.dropna().index.max().date()),
           "calendar": {int(y): [str(r.rank_day.date()), str(r.recon_day.date())] for y, r in cal.iterrows()},
           "fixed": {"cut": universe.CUT, "min_price": universe.MIN_PRICE, "min_company_value_usd": universe.MIN_CAP_K * 1000, "liquid_adv": LIQUID_ADV}}
    desc, a = describe(W, cal, sets)
    out["sets"] = desc
    print("sets (rank-day medians; volume ratio = reconstitution-day dollar volume over the 21-session median):")
    for s in universe.SETS:
        d = desc[s]
        print(f"  {s:<10} {d['per_year_mean']:>5.0f}/yr (min {d['per_year_min']})  price ${d['median_price']:.2f}  value ${d['median_company_value_usd'] / 1e6:.0f}M  "
              f"ADV ${d['median_adv21_usd']:,.0f}  spread {d['median_closing_spread']:.2%}  recon-day volume x{d['median_recon_day_volume_ratio']:.1f} (a week before x{d['median_volume_ratio_a_week_before']:.1f})")
    pnl, info, bh = run(W, iwm, cal, sets, sessions)
    report(pnl, info, bh, PAIRS, out)
    # the liquidity split, stated in advance
    liq = a[a["set"].isin(["ADD", "DEL", "STAY_IN", "STAY_OUT"])]
    sub = {f"{s}, {'liquid' if k else 'thin'}": liq[(liq["set"] == s) & ((liq["adv21"] >= LIQUID_ADV) == k)] for s in ("ADD", "DEL", "STAY_IN", "STAY_OUT") for k in (True, False)}
    p2, i2, b2 = run(W, iwm, cal, sets, sessions, subsets=sub)
    report(p2, i2, b2, (("ADD, liquid", "STAY_IN, liquid"), ("DEL, liquid", "STAY_OUT, liquid"), ("DEL, liquid", "ADD, liquid"),
                        ("ADD, thin", "STAY_IN, thin"), ("DEL, thin", "STAY_OUT, thin")), out, label=" | split at $500k ADV")
    # the placebo: the same shares on next year's calendar
    core = {s: sets[sets["set"] == s] for s in ("ADD", "DEL", "STAY_IN", "STAY_OUT")}
    p3, i3, b3 = run(W, iwm, cal, sets, sessions, calendar_shift=1, subsets=core)
    report(p3, i3, b3, (("ADD", "STAY_IN"), ("DEL", "STAY_OUT"), ("DEL", "ADD")), out, label=" | PLACEBO: same shares, one year later")
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
