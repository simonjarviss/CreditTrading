"""Explore: a SOFT cap on one fund group's net weight in the core CEF book. What does it cost, what tail does it cut?

    python3 results/ideas/core_group_cap/explore.py --data <a checkout's data/cef>

WHY: the paper book lost about 3.2% of capital in 34 sessions on the NAV moves of the two
muni funds it was short through a muni rally (results/ideas/2026-11-15_core_nav_hedge.md).
That card showed an ETF hedge of the NAV exposure does not help, and left one thing unread:
a cap on a group's net position. The desk killed HARD muni neutrality long ago (gross Sharpe
0.97 -> 0.82, docs/RESEARCH_STATE.md); nothing softer has a number. This is research on a
copy of the logic: nothing in ops/specs or the sleeve is touched, and no file under data/ is
written.

FIXED BEFORE ANY CAPPED RETURN WAS READ (2026-11-16). Only the uncapped book's group nets
(which define the caps) and the figures already in the core_nav_hedge card had been seen.
  BOOK      the frozen spec's targets: `build_targets(source=(prices, nav))`, then
            `band(T, BAND_WIDTH)`, both from scripts/cef/band_frontier.py, unchanged, exactly
            as results/ideas/core_nav_hedge/explore.py. shift(2) through harness.evaluate.
            Weights are in the harness's units (before the spec's sizing multiplier); the
            34-session windows are shown at the multiplier, as in that card.
  GROUPS    `grp` in data/cef/cef_universe.csv for the spec's universe.
  NET       a group's net on date t = the sum of that date's TARGET weights over its funds.
  CAPS      on each group's absolute net, applied to the targets BEFORE the band:
            MED   the group's own median |net| over every session with a live target up to
                  2019-12-31;
            P75   its 75th percentile over the same sessions;
            F25   0.25 for every group.
            MED and P75 are estimated on the sessions they are then applied to before 2020
            (a quantile, not a fitted optimum). 2020 onwards is the clean sample for them and
            is reported apart. F25 estimates nothing.
            XP75  (the no-lookahead form of P75) the cap on date t is the 75th percentile of
                  the group's |net| over live-target sessions strictly before t; no cap until
                  252 such sessions exist. ALIGNMENT asserted in code.
  HOW       three constructions, each reported for each cap:
            PRORATA  a group whose |net| exceeds its cap has all its positions multiplied by
                     cap/|net|. Nothing else moves, so gross is lower and the book is no
                     longer dollar-neutral (it carries the net that was cut).
            REGROSS  PRORATA, then the whole book multiplied by (uncapped gross / capped
                     gross) so gross is what it was. The cap is then exceeded by that factor;
                     the realised excess is reported.
            NEUTRAL  (added to the brief, fixed here before any return) clip each group's
                     net to its cap; if the clipped nets no longer sum to zero, scale the
                     nets of the larger side down pro rata until they do; give each group its
                     new net by moving every one of its held funds by the same amount. The
                     book stays dollar-neutral and within-group spreads are untouched. With a
                     cap of zero this is hard group neutrality, which is run as the reference
                     to the desk's killed test (HARD0).
  COMPARE   Sharpe, volatility, worst drawdown, the worst 34-session window of the NAV part
            and of the whole book (the live loss was a 34-session window), turnover, the
            NAV/discount split as in core_nav_hedge, by era (2013-15, 2016-19, 2020-22,
            2023-26) and both halves. Everything from the first session the book holds.
  TURNOVER  the desk compares policies within 5% turnover. A variant whose turnover differs
            from the uncapped book's by more than 5% is ALSO shown with its band width moved
            (bisection, to within 1%) until turnover matches. That is a derived width for
            the comparison, not a sweep, and it is labelled.
  CONTROLS  (a) SCALED: the uncapped book times (capped mean gross / uncapped mean gross):
            what a plain cut in size buys. Its Sharpe is the uncapped Sharpe by construction;
            a cap must cut the tail by more than this to be about groups at all. The tail is
            therefore also shown per unit of each book's own volatility.
            (b) PLACEBO: 200 random relabellings of the 13 funds into groups of the same
            sizes, the F25 and P75 caps derived and applied the same way (PRORATA). If the
            real grouping does not cut the NAV tail by more than random groupings do, the
            cap is a size cut and the group labels add nothing.
            (c) POLICY: the uncapped book and each PRORATA variant under the live policy's
            gross ceiling (`band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)`), to check
            the answer is not special to the plain band.
  EXPECTED  the group net is part of the signal (hard neutrality cost 0.15 of Sharpe), so a
            cap gives up a little Sharpe, less than that: about 0.02 to 0.08 for F25/P75 and
            more for MED. The NAV part's worst 34 sessions shrink by more than the size cut
            alone would give. Turnover rises a little. If the placebo cuts the tail as well,
            the conclusion is "this is a size cut".
  NOT HERE  the live window (2026-09-29 to 11-13): the panel ends before most of it, and
            nothing is chosen on it. Costs: gross is the headline; the desk's 5/15/30bp grid
            is beside it, from turnover.

Writes results.json (aggregates only) beside this file. Prints the tables.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore as _explore  # noqa: E402,F401  turns numexpr off (see its header)

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
CAP_FIT_END = "2019-12-31"
FLAT_CAP = 0.25                 # the brief's level (iii); not a spec parameter
XP_MIN = 252
WINDOW = 34                     # sessions in the live record on 2026-11-13
ERAS = (("2013", "2015"), ("2016", "2019"), ("2020", "2022"), ("2023", "2026"))
N_PLACEBO, SEED = 200, 20261116
TURN_TOL, MATCH_TOL = 0.05, 0.01
COST_BP = (5, 15, 30)


# ---------------------------------------------------------------------------- the cap
def group_nets(T: pd.DataFrame, grp: pd.Series) -> pd.DataFrame:
    return T.T.groupby(grp).sum().T


def cap_frame(T: pd.DataFrame, grp: pd.Series, kind: str) -> pd.DataFrame:
    """The cap on each group's |net| for each date, as a dates x groups frame (inf = no cap)."""
    net = group_nets(T, grp).abs()
    live = T.abs().sum(axis=1) > 0
    if kind in ("MED", "P75"):
        fit = net[live].loc[:CAP_FIT_END]
        if len(fit) < XP_MIN:
            raise RuntimeError(f"only {len(fit)} live-target sessions before {CAP_FIT_END}")
        q = fit.quantile(0.5 if kind == "MED" else 0.75)
        return pd.DataFrame(np.tile(q.values, (len(T), 1)), index=T.index, columns=q.index)
    if kind == "F25":
        return pd.DataFrame(FLAT_CAP, index=T.index, columns=net.columns)
    if kind == "HARD0":
        return pd.DataFrame(0.0, index=T.index, columns=net.columns)
    if kind == "XP75":
        # ALIGNMENT: the expanding quantile through t is shifted one live session, so the cap
        # used on date t reads nets strictly before t. Non-live sessions carry the last value.
        x = net[live].expanding(min_periods=XP_MIN).quantile(0.75).shift(1)
        c = x.reindex(T.index).ffill()
        first = c.dropna().index.min()
        assert int(live.loc[:first].sum()) > XP_MIN, "expanding cap starts before its history exists"
        return c.where(c.notna(), np.inf)
    raise ValueError(kind)


def apply_cap(T: pd.DataFrame, grp: pd.Series, cap: pd.DataFrame, how: str) -> pd.DataFrame:
    net = group_nets(T, grp)
    cap = cap[net.columns]
    clipped = net.clip(lower=-cap, upper=cap)
    if how in ("PRORATA", "REGROSS"):
        f = (clipped / net.where(net != 0)).fillna(1.0)          # zero net: nothing to scale
        out = T * f[grp.values].set_axis(T.columns, axis=1)
        if how == "REGROSS":
            g0, g1 = T.abs().sum(axis=1), out.abs().sum(axis=1)
            out = out.mul((g0 / g1.where(g1 > 0)).fillna(1.0), axis=0)
        return out
    if how == "NEUTRAL":
        pos, neg = clipped.clip(lower=0).sum(axis=1), -clipped.clip(upper=0).sum(axis=1)
        m = np.minimum(pos, neg)
        fp = (m / pos.where(pos > 0)).fillna(1.0)
        fn = (m / neg.where(neg > 0)).fillna(1.0)
        new = clipped.clip(lower=0).mul(fp, axis=0) + clipped.clip(upper=0).mul(fn, axis=0)
        assert float(new.sum(axis=1).abs().max()) < 1e-9
        heldn = (T != 0).T.groupby(grp).sum().T                  # funds with a target, per group
        shift = ((new - net) / heldn.where(heldn > 0)).fillna(0.0)
        out = T + shift[grp.values].set_axis(T.columns, axis=1).where(T != 0, 0.0)
        assert float(out.sum(axis=1).abs().max()) < 1e-9, "NEUTRAL must stay dollar-neutral"
        return out
    raise ValueError(how)


# ---------------------------------------------------------------------------- statistics
def st(p: pd.Series) -> dict:
    sd = p.std()
    cum = p.cumsum()
    return {"ann_ret_pct": round(100 * p.mean() * 252, 2), "vol_pct": round(100 * sd * 252 ** 0.5, 2),
            "sharpe": round(p.mean() / sd * 252 ** 0.5, 3) if sd > 0 else None,
            "t": round(p.mean() / sd * len(p) ** 0.5, 2) if sd > 0 else None,
            "max_dd_pct": round(100 * (cum - cum.cummax()).min(), 2)}


def win(p: pd.Series, mult: float) -> dict:
    r = p.rolling(WINDOW).sum().dropna() * mult * 100
    return {"worst": round(float(r.min()), 2), "p1": round(float(r.quantile(0.01)), 2),
            "p5": round(float(r.quantile(0.05)), 2), "mean": round(float(r.mean()), 2),
            "sd": round(float(r.std()), 2), "worst_date": str(r.idxmin().date()),
            "worst_in_sd": round(float(r.min() / r.std()), 2)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="a data/cef directory holding cef_prices, cef_nav, cef_universe")
    a = ap.parse_args(argv)
    from scripts.cef import band_frontier as bf
    from scripts.cef.spec import MAX_GROSS_STRESS, SIZING_MULTIPLIER
    from scripts.research import harness
    src = (a.data / "cef_prices.parquet", a.data / "cef_nav.parquet")
    T, R = bf.build_targets(source=src)
    p = bf.build_panel(source=src)
    grp = pd.read_csv(a.data / "cef_universe.csv").set_index("ticker")["grp"].reindex(T.columns)
    if grp.isna().any():
        raise RuntimeError(f"no group for {list(grp[grp.isna()].index)}")
    navret = p["nav"].pct_change(fill_method=None).where(lambda x: x.abs() < 0.5).reindex(T.index)[T.columns]
    H0 = bf.band(T, bf.BAND_WIDTH)
    first = harness.held(H0).abs().sum(axis=1).gt(0).idxmax()     # first session the book holds
    S = slice(first, None)

    def score(H: pd.DataFrame, tag: str = "") -> dict:
        ev = harness.evaluate(H, R)
        W = harness.held(H)
        pnl = ev["pnl"]
        navp = (W * navret.fillna(0.0)).sum(axis=1)
        disc = pnl - navp
        turn = float(ev["turn_series"].loc[S].mean() * 252)
        mid = pnl.loc[S].index[len(pnl.loc[S]) // 2]
        gn = group_nets(H, grp).loc[S]
        o = {"book": st(pnl.loc[S]), "nav_part": st(navp.loc[S]), "disc_part": st(disc.loc[S]),
             "turnover_per_year": round(turn, 2),
             "mean_gross": round(float(H.abs().sum(axis=1).loc[S].mean()), 3),
             "mean_abs_book_net": round(float(H.sum(axis=1).abs().loc[S].mean()), 3),
             "muni_abs_net_mean_p95_max": [round(float(x), 3) for x in
                                           (gn["muni"].abs().mean(), gn["muni"].abs().quantile(0.95), gn["muni"].abs().max())],
             "win34_book": win(pnl.loc[S], SIZING_MULTIPLIER), "win34_nav": win(navp.loc[S], SIZING_MULTIPLIER),
             "win34_disc": win(disc.loc[S], SIZING_MULTIPLIER),
             "corr_nav_disc": round(float(navp.loc[S].corr(disc.loc[S])), 3),
             "halves": {"split": str(mid.date()), "early": st(pnl.loc[first:mid])["sharpe"], "late": st(pnl.loc[mid:])["sharpe"]},
             "eras": {f"{lo}-{hi}": {"book": st(pnl.loc[lo:hi])["sharpe"], "nav_ret_pct": st(navp.loc[lo:hi])["ann_ret_pct"],
                                     "nav_vol_pct": st(navp.loc[lo:hi])["vol_pct"], "vol_pct": st(pnl.loc[lo:hi])["vol_pct"],
                                     "ret_pct": st(pnl.loc[lo:hi])["ann_ret_pct"],
                                     "worst34_nav": win(navp.loc[lo:hi], SIZING_MULTIPLIER)["worst"],
                                     "worst34_book": win(pnl.loc[lo:hi], SIZING_MULTIPLIER)["worst"]} for lo, hi in ERAS},
             "net_sharpe_at_bp": {str(c): round((pnl.loc[S].mean() * 252 - turn * c / 1e4) / (pnl.loc[S].std() * 252 ** 0.5), 3) for c in COST_BP}}
        o["_pnl"], o["_nav"] = pnl, navp
        return o

    def matched(Tc: pd.DataFrame, target_turn: float) -> tuple[pd.DataFrame, float]:
        """Band width at which Tc's turnover equals the uncapped book's (bisection; turnover falls as the band widens)."""
        lo, hi = bf.BAND_WIDTH / 4, bf.BAND_WIDTH * 4
        for _ in range(40):
            b = (lo + hi) / 2
            H = bf.band(Tc, b)
            t = float(H.diff().abs().sum(axis=1).fillna(0.0).loc[S].mean() * 252)
            if abs(t / target_turn - 1) < MATCH_TOL:
                return H, b
            lo, hi = (b, hi) if t > target_turn else (lo, b)
        raise RuntimeError("no band width matches the uncapped turnover")

    base = score(H0)
    assert abs(base["_pnl"].sum() - harness.evaluate(H0, R)["pnl"].sum()) < 1e-12
    t0 = base["turnover_per_year"]
    tnet = group_nets(T, grp)
    live = T.abs().sum(axis=1) > 0
    out = {"panel_last": str(T.index.max().date()), "first_held": str(first.date()), "names": list(T.columns),
           "groups": grp.groupby(grp).size().to_dict(), "band_width": bf.BAND_WIDTH, "sizing_multiplier": SIZING_MULTIPLIER,
           "caps": {}, "target_abs_net": {}, "variants": {}, "matched": {}, "policy_gross_ceiling": {}}
    for g in tnet.columns:
        x, y = tnet.loc[live, g].abs().loc[:CAP_FIT_END], tnet.loc[live, g].abs().loc["2020":]
        out["target_abs_net"][g] = {"pre2020": {q: round(float(x.quantile(v)), 3) for q, v in (("p50", .5), ("p75", .75), ("p95", .95), ("max", 1))},
                                    "from2020": {q: round(float(y.quantile(v)), 3) for q, v in (("p50", .5), ("p75", .75), ("p95", .95), ("max", 1))}}
    out["variants"]["UNCAPPED"] = base

    kinds = ("MED", "P75", "F25", "XP75")
    for kind in kinds:
        cap = cap_frame(T, grp, kind)
        out["caps"][kind] = ({g: round(float(cap[g].iloc[-1]), 3) for g in cap.columns} if kind != "XP75"
                             else {g: [round(float(cap[g].replace(np.inf, np.nan).dropna().iloc[0]), 3), round(float(cap[g].iloc[-1]), 3)] for g in cap.columns})
        bind = (tnet.abs() > cap[tnet.columns] + 1e-12)[live].loc[S]
        for how in ("PRORATA", "REGROSS", "NEUTRAL"):
            Tc = apply_cap(T, grp, cap, how)
            if how != "REGROSS":      # the cap holds on the targets in these two
                assert bool((group_nets(Tc, grp).abs() <= cap[tnet.columns] + 1e-9).all().all())
            name = f"{kind}/{how}"
            r = score(bf.band(Tc, bf.BAND_WIDTH))
            r["share_days_binding"] = {g: round(float(bind[g].mean()), 3) for g in bind.columns}
            r["turnover_vs_uncapped"] = round(r["turnover_per_year"] / t0 - 1, 3)
            if how == "REGROSS":
                ex = (group_nets(Tc, grp).abs() / cap[tnet.columns]).where(bind.reindex(T.index, fill_value=False))
                r["cap_excess_factor_mean_on_binding_days"] = round(float(np.nanmean(ex.values)), 3)
            # control (a): the uncapped book at the same mean gross
            k = r["mean_gross"] / base["mean_gross"]
            r["control_scaled"] = {"scale": round(k, 3), "worst34_nav": round(base["win34_nav"]["worst"] * k, 2),
                                   "worst34_book": round(base["win34_book"]["worst"] * k, 2),
                                   "max_dd_pct": round(base["book"]["max_dd_pct"] * k, 2), "vol_pct": round(base["book"]["vol_pct"] * k, 2)}
            out["variants"][name] = r
            if abs(r["turnover_vs_uncapped"]) > TURN_TOL:
                Hm, b = matched(Tc, t0)
                m = score(Hm)
                m["band_width_used"] = round(b, 5)
                out["matched"][name] = m
            if how == "PRORATA":
                out["policy_gross_ceiling"][name] = score(bf.band_gross_capped(Tc, bf.BAND_WIDTH, MAX_GROSS_STRESS))
    out["policy_gross_ceiling"]["UNCAPPED"] = score(bf.band_gross_capped(T, bf.BAND_WIDTH, MAX_GROSS_STRESS))
    out["variants"]["HARD0/NEUTRAL"] = score(bf.band(apply_cap(T, grp, cap_frame(T, grp, "HARD0"), "NEUTRAL"), bf.BAND_WIDTH))
    out["variants"]["HARD0/NEUTRAL"]["turnover_vs_uncapped"] = round(out["variants"]["HARD0/NEUTRAL"]["turnover_per_year"] / t0 - 1, 3)

    # control (b): random relabellings with the same group sizes
    rng = np.random.default_rng(SEED)
    out["placebo"] = {"n": N_PLACEBO, "seed": SEED}
    for kind in ("F25", "P75"):
        rows = []
        for _ in range(N_PLACEBO):
            g2 = pd.Series(rng.permutation(grp.values), index=grp.index)
            r = score(bf.band(apply_cap(T, g2, cap_frame(T, g2, kind), "PRORATA"), bf.BAND_WIDTH))
            rows.append((r["book"]["sharpe"], r["win34_nav"]["worst"], r["win34_book"]["worst"], r["nav_part"]["vol_pct"],
                         r["mean_gross"], r["book"]["max_dd_pct"], r["win34_nav"]["worst"] / r["mean_gross"]))
        P = pd.DataFrame(rows, columns=["sharpe", "worst34_nav", "worst34_book", "nav_vol_pct", "mean_gross", "max_dd_pct", "worst34_nav_per_gross"])
        real = out["variants"][f"{kind}/PRORATA"]
        rv = {"sharpe": real["book"]["sharpe"], "worst34_nav": real["win34_nav"]["worst"], "worst34_book": real["win34_book"]["worst"],
              "nav_vol_pct": real["nav_part"]["vol_pct"], "mean_gross": real["mean_gross"], "max_dd_pct": real["book"]["max_dd_pct"],
              "worst34_nav_per_gross": real["win34_nav"]["worst"] / real["mean_gross"]}
        out["placebo"][kind] = {c: {"real": round(float(rv[c]), 3), "placebo_median": round(float(P[c].median()), 3),
                                    "placebo_p5": round(float(P[c].quantile(0.05)), 3), "placebo_p95": round(float(P[c].quantile(0.95)), 3),
                                    "share_placebo_above_real": round(float((P[c] > rv[c]).mean()), 3)} for c in P.columns}

    # the last weeks of the panel: what each cap would have held in the muni group (report only)
    tail = {}
    for name in ("UNCAPPED", "MED/PRORATA", "P75/PRORATA", "F25/PRORATA", "XP75/PRORATA", "F25/NEUTRAL"):
        kind, _, how = name.partition("/")
        Hc = H0 if name == "UNCAPPED" else bf.band(apply_cap(T, grp, cap_frame(T, grp, kind), how), bf.BAND_WIDTH)
        m = group_nets(Hc, grp)["muni"].loc["2026-09-29":]
        tail[name] = {"muni_net_mean": round(float(m.mean()), 3), "muni_net_min": round(float(m.min()), 3),
                      "muni_net_last": round(float(m.iloc[-1]), 3), "sessions": int(len(m))}
    out["muni_net_held_from_2026-09-29"] = tail

    # differences from the uncapped book, as a daily series: is the Sharpe given up distinguishable from zero?
    for name, r in out["variants"].items():
        if name != "UNCAPPED":
            d = (r["_pnl"] - base["_pnl"]).loc[S]
            r["diff_vs_uncapped"] = {"ann_ret_pct": round(100 * d.mean() * 252, 2), "t": round(float(d.mean() / d.std() * len(d) ** 0.5), 2)}
    for blk in (out["variants"], out["matched"], out["policy_gross_ceiling"]):
        for r in blk.values():
            r.pop("_pnl"), r.pop("_nav")
    (HERE / "results.json").write_text(json.dumps(out, indent=1))

    print(f"panel last {out['panel_last']}  first held {out['first_held']}  groups {out['groups']}  band {bf.BAND_WIDTH}  x{SIZING_MULTIPLIER}")
    print("target |net| by group:", json.dumps(out["target_abs_net"]))
    print("caps:", json.dumps(out["caps"]))

    def line(k, r):
        b, e = r["book"], r["eras"]
        return (f"{k:16s} SR {b['sharpe']:5.2f} t {b['t']:5.2f} ret {b['ann_ret_pct']:5.2f} vol {b['vol_pct']:5.2f} dd {b['max_dd_pct']:6.2f} "
                f"| w34 nav {r['win34_nav']['worst']:6.2f} book {r['win34_book']['worst']:6.2f} | navvol {r['nav_part']['vol_pct']:4.2f} navret {r['nav_part']['ann_ret_pct']:5.2f} "
                f"disc {r['disc_part']['ann_ret_pct']:5.2f} | turn {r['turnover_per_year']:5.1f} gross {r['mean_gross']:.2f} net {r['mean_abs_book_net']:.2f} "
                f"| halves {r['halves']['early']:.2f}/{r['halves']['late']:.2f} | " + " ".join(f"{e[x]['book']:5.2f}" for x in e))
    for title, blk in (("VARIANTS (band at spec width)", out["variants"]), ("TURNOVER-MATCHED (band width moved)", out["matched"]),
                       ("UNDER THE LIVE GROSS CEILING", out["policy_gross_ceiling"])):
        print(f"\n{title}")
        for k, r in blk.items():
            print(line(k, r) + (f"  b={r['band_width_used']}" if "band_width_used" in r else ""))
    print("\nplacebo:", json.dumps(out["placebo"], indent=1))
    print("muni net held from 2026-09-29:", json.dumps(tail))
    return 0


if __name__ == "__main__":
    sys.exit(main())
