"""The quant and PM reviews' measurements of the te4 draft, re-run as one tracked script (2026-11-03).

    python3 results/cef/prereg_thin_te4/review_checks.py [--stamp YYYY-MM-DD] [--overwrite]
        -> review_checks_<stamp>.json, review_checks_output_<stamp>.txt (this folder); about a minute.
        Needs compose_<stamp>.json beside it (run compose.py with the same --stamp first): §R9 reads D_E there.

ZERO TRIALS. Written for `results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md` (drafted
as `PREREG_DRAFT_THIN_TRADE_ELIGIBLE_2026-11-03.md`; approved 2026-11-03 as CEF trial 55), section 12. FIT WINDOW ONLY for every return: the books are compose.py's (`bf.fit_only`, strictly
before 2023-01-01, asserted again here). One what-if reads a later row: §R8 applies the price panel's LAST
CLOSES (Alpaca's margin tiers are price-dependent) to the fit's weights; no return is computed on it. It
reads data/ and writes only beside itself (CLAUDE.md landmine 9).

WHY IT EXISTS. Two reviews of the draft (2026-11-03) measured its risk design with scratch scripts outside
the repository. The draft now quotes those measurements, and a figure in a tracked document names a script
that reproduces it (`.claude/rules/documents.md` rule 1). This is that script: the reviewers' code,
consolidated, with the paths made relative. Re-running it is also how their findings were CONFIRMED before
the draft was changed: each section's figures matched the reviewer's own output (the draft's section 12
says where one did not).

WHAT IT ANSWERS (spec's m, deferred flips, the live runner's rule, unless stated)
  R1   The stop split (quant 1, PM F1). The account's W1 drawdown and its window; that window's days split
       into reduced and full earning days; R1's population under the draft's Q3(a) (full-session earning
       days joined end to end) and K1's (the open episode's reduced earning days joined), each at the date
       the account first reaches HALVE and at its worst.
  R2   K0 on the one fit path (PM P1): the first decide inside an OPEN episode (first reduced decision to
       63 sessions after the last) with the account at or past HALVE; the book spliced onto the flatten
       book at the next reduced decision (exact: flatten is flat there).
  R3   K0 under the bootstrap (PM Q2; anchor PM A1): zero-edge and fit-edge 12-month P(HALVE) / P(KILL) on
       te4's W1 trading series with the session type (full / reduced) carried by the stationary bootstrap
       (SB21, SB63; zero edge demeans each type separately). Variants: base; K0 (once the path's drawdown
       reaches HALVE, reduced-day returns are 0 from two sessions later, and flatten's re-entry is ignored
       [U: approximation]); MR (reduced days at m_r / m, m_r = the 2026-10-29 rule fed the reduced-day unit
       sd [U: ignores the cap and band path]); MR+K0. The flatten book on its own trading sessions, same
       seeds, is the like-for-like anchor. Not comparable with compose §D2, which takes the worst of three
       methods including GAUSS: GAUSS cannot carry the session type.
  R4   m as a function of the reduced share s (PM P2): the 2026-10-29 rule fed the mixture of the full- and
       reduced-session unit sd (means included), at s = 0 ... 0.25 and W1's s.
  R5   Tails by session type (PM P3): vol, worst day, excess kurtosis and the worst single-name one-day
       contribution on full earning days, reduced earning days whose target has a single-fund side, and the
       other reduced days; and how often a reduced target has a single-fund side (short side, long side).
  R6   Crash-day stress (PM S1): the fit's 10 worst equal-weight universe days, each day's cross-section
       applied to every held reduced and full book.
  R7   Sponsor and muni exposure (PM P5): |net PIMCO|, PIMCO's share of gross and |net muni| of the held
       book, reduced against full decisions; how many eligible names are PIMCO on reduced decisions.
  R8   Alpaca maintenance margin (PM M1) on the fit's held books, at each decision's own closes and at the
       panel's last closes, by Alpaca's published tiers:
         long  price < 2.50 -> 100%; 2.50..6.00 -> 50%; above 6.00 -> 30%
               [S: docs.alpaca.markets margin-and-short-selling, as fetched by the PM review 2026-11-03; not
               yet in docs/REFERENCES.md]
         short price < 5 -> max(2.50 / price, 100%); price >= 5 -> max(5.00 / price, 30%)
               [V: docs/REFERENCES.md, "Short maintenance margin at Alpaca", fetched 2026-10-12]
       and the largest rise in the blended maintenance ratio at the start of a reduced run.
  R9   A horizon-matched K1 (PM K1h): each fit episode's drawdown over its first L thin earning days
       against compose §E's D_E(L), L = 21, 63, 126, 252.
  R10  The cost grid's traded notional per episode (quant 3): every trade each book makes from the episode's
       first reduced decision to the first decision after its last reduced one (gaps between runs
       included), against the draft's first formula (te4: the reduced decisions plus that last decision;
       flatten: the exit at the first reduced decision plus the re-entry at that last decision).
No mean return of any new variant is used to choose anything; the K0 and MR means are reported as costs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compose as C                                                     # noqa: E402  (sets the repo's sys.path)
bf, S = C.bf, C.S
from scripts.cef.portfolio_baseline import (HALVE_DD, KILL_DD, max_drawdown,  # noqa: E402
                                            stationary_index)

P = 252
LOG, OUT = [], {}


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def dd_series(x: pd.Series) -> pd.Series:
    eq = (1 + x).cumprod()
    return 1 - eq / eq.cummax()


def q(s) -> dict:
    s = pd.Series(s).dropna()
    return dict(p50=float(s.quantile(.5)), p90=float(s.quantile(.9)), p99=float(s.quantile(.99)),
                max=float(s.max()), share_gt_0_9=float((s > 0.9).mean()), share_gt_1=float((s > 1.0).mean()),
                n=int(len(s)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stamp", default=dt.date.today().isoformat())
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    outs = (HERE / f"review_checks_{args.stamp}.json", HERE / f"review_checks_output_{args.stamp}.txt")
    if any(f.exists() for f in outs) and not args.overwrite:
        raise SystemExit(f"{[f.name for f in outs if f.exists()]} exist; pass --overwrite or another --stamp")
    comp = HERE / f"compose_{args.stamp}.json"
    if not comp.exists():
        raise SystemExit(f"{comp.name} is missing: run compose.py --stamp {args.stamp} first (§R9 reads D_E there)")

    M, BAND, CAP, FLOOR, W1 = float(S.SIZING_MULTIPLIER), float(S.BAND_WIDTH), float(S.MAX_GROSS_STRESS), C.FLOOR, C.W1
    p(f"spec {S.SPEC_ID}: m {M}, band {BAND}, max_gross_stress {CAP}, HALVE {HALVE_DD}, KILL {KILL_DD}; "
      f"FLOOR {FLOOR} ({C.FLOOR_SOURCE}); stamp {args.stamp}")
    OUT["spec"] = dict(id=S.SPEC_ID, m=M, band=BAND, cap=CAP, halve=HALVE_DD, kill=KILL_DD, floor=FLOOR)

    T6, R = bf.build_targets()
    T4, _ = bf.build_targets(min_names=FLOOR)
    thin6 = bf.thin_sessions(T6.index)
    thin4 = bf.thin_sessions(T4.index, min_names=FLOOR)
    T6, Rf = bf.fit_only(T6, R)
    T4, _ = bf.fit_only(T4, R)
    thin6, thin4 = thin6.loc[T6.index], thin4.loc[T4.index]
    if T6.index.max() >= pd.Timestamp("2023-01-01") or Rf.index.max() >= pd.Timestamp("2023-01-01"):
        raise AssertionError("holdout leak")
    Rtr = bf.total_returns(Rf)
    reduced = thin6 & ~thin4
    idx = T6.index

    def book(rule, m, deferred):
        if rule == "flatten":
            H = bf.band_gross_capped(T6, BAND, CAP / m, defer_flips=deferred, below_min_names="flatten", thin=thin6)
        else:
            H = bf.band_gross_capped(T4, BAND, CAP / m, defer_flips=deferred, below_min_names="trade_eligible",
                                     thin=thin4, floor=FLOOR)
        return m * H

    Hd, Fd, Hu = book("te4", M, True), book("flatten", M, True), book("te4", 1.0, False)
    eps = C.episodes(reduced)
    open_ep = pd.Series(False, index=idx)
    for e in eps:
        open_ep.iloc[e["i0"]: min(e["i1"] + 63 + 1, len(idx))] = True
    red_dec = idx[reduced.to_numpy()]
    first_red = red_dec.min()

    # ------------------------------------------------------------ R1. the stop split
    R1 = {}
    for lab, RR in (("PR", Rf), ("TR", Rtr)):
        pn = bf.evaluate(Hd, RR)["pnl"].loc[W1:]
        red_e = reduced.shift(2).reindex(pn.index).fillna(False).astype(bool)
        g = Hd.abs().sum(axis=1)
        earn = (g.shift(2).fillna(0.0) > 0).reindex(pn.index).fillna(False).astype(bool)
        acct = dd_series(pn)
        dd = max_drawdown(pn)
        pk, tr = pd.Timestamp(dd["peak"]), pd.Timestamp(dd["trough"])
        seg = pn.loc[pk:tr].iloc[1:]
        rs = red_e.loc[seg.index]
        t_cross = acct[acct >= HALVE_DD].index.min()
        ep = [e for e in eps if idx[e["i0"]] <= t_cross <= idx[min(e["i1"] + 63, len(idx) - 1)]]
        full_j = pn[earn & ~red_e]                       # Q3(a): R1's population
        ddf = dd_series(full_j)
        rec = dict(account_maxdd=float(dd["mdd"]), peak=str(pk.date()), trough=str(tr.date()),
                   window_days=int(len(seg)), window_reduced_days=int(rs.sum()), window_full_days=int((~rs).sum()),
                   window_compounded_reduced=float(np.prod(1 + seg[rs]) - 1),
                   window_compounded_full=float(np.prod(1 + seg[~rs]) - 1),
                   first_halve=str(t_cross.date()), first_halve_in_open_episode=bool(len(ep)),
                   full_joined_maxdd_w1=float(max_drawdown(full_j)["mdd"]),
                   full_joined_dd_at_first_halve=float(ddf.loc[:t_cross].iloc[-1]))
        if ep:
            ed = C.earn_days(idx, ep[0]["parts"]).intersection(pn.index)
            ddr = dd_series(pn.loc[ed])
            rec.update(episode=f"{idx[ep[0]['i0']].date()}..{idx[ep[0]['i1']].date()}",
                       episode_reduced_dd_at_first_halve=float(ddr.loc[:t_cross].iloc[-1]),
                       episode_reduced_maxdd=float(ddr.max()),
                       account_dd_at_episode_start=float(acct.loc[:idx[ep[0]['i0']]].iloc[-1]))
        R1[lab] = rec
    OUT["R1_stop_split"] = R1
    p("\nR1. the stop split, te4 at m, deferred, W1:")
    for lab, r in R1.items():
        p(f"  {lab}: account maxDD {r['account_maxdd']:.2%} ({r['peak']} .. {r['trough']}); window {r['window_days']} "
          f"earning days = {r['window_reduced_days']} reduced (compounded {r['window_compounded_reduced']:+.2%}) + "
          f"{r['window_full_days']} full ({r['window_compounded_full']:+.2%}); first at HALVE {r['first_halve']} "
          f"(open episode {r.get('episode', 'none')}, account {r.get('account_dd_at_episode_start', float('nan')):.2%} "
          f"below its high at the episode's start); at that date R1's population (full days joined) reads "
          f"{r['full_joined_dd_at_first_halve']:.2%} (its W1 worst {r['full_joined_maxdd_w1']:.2%}), K1's (the "
          f"episode's reduced days joined) {r.get('episode_reduced_dd_at_first_halve', float('nan')):.2%} (its worst "
          f"{r.get('episode_reduced_maxdd', float('nan')):.2%})")

    # ------------------------------------------------------------ R2. K0 on the fit path
    R2 = {}
    for lab, RR in (("PR", Rf), ("TR", Rtr)):
        pn = bf.evaluate(Hd, RR)["pnl"].loc[W1:]
        dd = dd_series(pn)
        trig = [d for d in dd.index if dd.loc[d] >= HALVE_DD and open_ep.get(d, False)]
        rec = dict(maxdd=float(dd.max()), maxdd_date=str(dd.idxmax().date()))
        if trig:
            t0 = trig[0]
            d_r = idx[(idx >= t0) & reduced.to_numpy()].min()
            Hs = pd.concat([Hd.loc[:d_r].iloc[:-1], Fd.loc[d_r:]])
            if not Hs.index.equals(Hd.index) or float(Fd.loc[d_r].abs().sum()) != 0.0:
                raise AssertionError("the K0 splice is not exact")
            ps = bf.evaluate(Hs, RR)["pnl"].loc[W1:]
            ep = [e for e in eps if idx[e["i0"]] <= t0 <= idx[min(e["i1"] + 63, len(idx) - 1)]][0]
            e_end = idx[min(ep["i1"] + 2, len(idx) - 1)]
            rec.update(trigger=str(t0.date()), splice_at=str(d_r.date()),
                       maxdd_with_k0=float(dd_series(ps).max()), ann_te4=float(pn.mean() * P),
                       ann_with_k0=float(ps.mean() * P),
                       ann_flatten=float(bf.evaluate(Fd, RR)["pnl"].loc[W1:].mean() * P),
                       after_splice_te4=float(pn.loc[d_r:e_end].sum()), after_splice_k0=float(ps.loc[d_r:e_end].sum()))
        R2[lab] = rec
    OUT["R2_k0_path"] = R2
    p("\nR2. K0 on the fit path (W1):")
    for lab, r in R2.items():
        p(f"  {lab}: K0 fires {r.get('trigger')} (splice to flatten at {r.get('splice_at')}); maxDD {r['maxdd']:.2%} -> "
          f"{r.get('maxdd_with_k0', float('nan')):.2%}; W1 {r.get('ann_te4', float('nan')):.2%}/yr -> "
          f"{r.get('ann_with_k0', float('nan')):.2%}/yr (flatten {r.get('ann_flatten', float('nan')):.2%}); splice to "
          f"episode end: te4 {r.get('after_splice_te4', float('nan')):+.2%}, with K0 {r.get('after_splice_k0', float('nan')):+.2%}")

    # ------------------------------------------------------------ R3. K0 under the bootstrap, and m_r
    rem = json.loads((C.PV / "flatten_remeasure_2026-11-02_m1.30.json").read_text())
    sd = rem["sd_daily"]
    m_c4_rule = rem["implied_core_multiplier"]["flatten_active"] * sd["flatten_active"] / sd["c4"]
    pu = bf.evaluate(Hu, Rtr)["pnl"].loc[W1:]
    earn_u = (Hu.abs().sum(axis=1).shift(2).fillna(0.0) > 0).loc[W1:]
    red_u = reduced.shift(2).reindex(pu.index).fillna(False).astype(bool)
    sd_r = float(pu[earn_u & red_u].std())
    m_r = float(np.floor(m_c4_rule * sd["c4"] / sd_r * 100) / 100)
    REPS, H = 10_000, 252
    R3 = dict(m_r=dict(sd_reduced_unit=sd_r, m_r_raw=float(m_c4_rule * sd["c4"] / sd_r), m_r=m_r))

    def boot(x, f, idxs, variants):
        res = {}
        for edge in ("zero", "fit"):
            y = x.copy()
            if edge == "zero":
                if f is None:
                    y = y - y.mean()
                else:
                    y[f] -= y[f].mean()
                    y[~f] -= y[~f].mean()
            for meth, I in idxs.items():
                P_ = y[I]
                F_ = f[I] if f is not None else None
                for var in variants:
                    Q = P_.copy()
                    if "MR" in var:
                        Q = np.where(F_, Q * m_r / M, Q)
                    if "K0" in var:
                        eq = np.cumprod(1 + Q, axis=1)
                        dd = 1 - eq / np.maximum.accumulate(eq, axis=1)
                        hit = dd >= HALVE_DD
                        first = np.where(hit.any(axis=1), hit.argmax(axis=1), H + 10)
                        after = np.arange(H)[None, :] >= (first[:, None] + 2)
                        Q = np.where(after & F_, 0.0, Q)
                    eq = np.cumprod(1 + Q, axis=1)
                    peak = np.maximum.accumulate(np.concatenate([np.ones((REPS, 1)), eq], axis=1), axis=1)[:, 1:]
                    mdd = (1 - eq / peak).max(axis=1)
                    res[f"{edge}/{meth}/{var}"] = dict(p_halve=float((mdd >= HALVE_DD).mean()),
                                                       p_kill=float((mdd >= KILL_DD).mean()),
                                                       mean_ann=float(Q.mean() * P))
        return res

    for lab, RR in (("PR", Rf), ("TR", Rtr)):
        for name, Hx, typed in (("te4", Hd, True), ("flatten", Fd, False)):
            pn = bf.evaluate(Hx, RR)["pnl"].loc[W1:]
            earn = (Hx.abs().sum(axis=1).shift(2).fillna(0.0) > 0).loc[W1:]
            x = pn[earn].to_numpy()
            f = reduced.shift(2).reindex(pn.index).fillna(False).astype(bool)[earn].to_numpy() if typed else None
            n = len(x)
            idxs = {"SB21": stationary_index(n, H, REPS, 21, np.random.default_rng(20261030)),
                    "SB63": stationary_index(n, H, REPS, 63, np.random.default_rng(20261031))}
            R3[f"{name}/{lab}"] = boot(x, f, idxs, ("base", "K0", "MR", "MR+K0") if typed else ("base",))
            R3[f"{name}/{lab}"]["n"] = n
            if typed:
                R3[f"{name}/{lab}"]["reduced_share"] = float(f.mean())
    OUT["R3_k0_bootstrap"] = R3
    p(f"\nR3. 12-month P(HALVE) / P(KILL), W1 trading series, session type carried (10,000 paths); m_r = "
      f"{R3['m_r']['m_r']:.2f} (raw {R3['m_r']['m_r_raw']:.4f}; reduced-day unit sd {sd_r:.6f}):")
    for lab in ("PR", "TR"):
        for edge in ("zero", "fit"):
            for meth in ("SB21", "SB63"):
                cells = [f"te4 {v} {R3[f'te4/{lab}'][f'{edge}/{meth}/{v}']['p_halve']:.2%} / "
                         f"{R3[f'te4/{lab}'][f'{edge}/{meth}/{v}']['p_kill']:.2%} "
                         f"(mean {R3[f'te4/{lab}'][f'{edge}/{meth}/{v}']['mean_ann']:+.2%})"
                         for v in ("base", "K0", "MR", "MR+K0")]
                fl = R3[f"flatten/{lab}"][f"{edge}/{meth}/base"]
                p(f"  {lab} {edge:4s} {meth}: " + "; ".join(cells) +
                  f"; flatten {fl['p_halve']:.2%} / {fl['p_kill']:.2%}")

    # ------------------------------------------------------------ R4. m(s)
    gu = Hu.abs().sum(axis=1)
    earn = (gu.shift(2).fillna(0.0) > 0).loc[W1:]
    xf, xr = pu[earn & ~red_u], pu[earn & red_u]
    s_w1 = float(len(xr) / (len(xr) + len(xf)))

    def m_of(s):
        mu = (1 - s) * xf.mean() + s * xr.mean()
        var = (1 - s) * (xf.var(ddof=0) + (xf.mean() - mu) ** 2) + s * (xr.var(ddof=0) + (xr.mean() - mu) ** 2)
        return float(m_c4_rule * sd["c4"] / np.sqrt(var))
    R4 = dict(sd_full=float(xf.std()), sd_reduced=float(xr.std()), n_full=int(len(xf)), n_reduced=int(len(xr)),
              s_w1=s_w1, m_at={f"{s:.3f}": m_of(s) for s in (0.0, 0.05, 0.10, 0.15, 0.25, s_w1)})
    OUT["R4_m_of_s"] = R4
    p(f"\nR4. the 2026-10-29 rule fed the mixture (unit, instant, TR, W1): sd full {R4['sd_full']:.6f} [n {R4['n_full']}], "
      f"reduced {R4['sd_reduced']:.6f} [n {R4['n_reduced']}]; m(s): " +
      ", ".join(f"s {k} -> {v:.4f}" for k, v in R4["m_at"].items()))

    # ------------------------------------------------------------ R5. tails by session type
    single = ((T4.loc[red_dec] > 0).sum(axis=1).eq(1) | (T4.loc[red_dec] < 0).sum(axis=1).eq(1))
    sf = pd.Series(False, index=idx)
    sf.loc[single.index[single.to_numpy()]] = True
    sf_e = sf.shift(2).reindex(idx).fillna(False).astype(bool)
    R5 = dict(single_fund_side=dict(any=float(single.mean()),
                                    short_side=float((T4.loc[red_dec] < 0).sum(axis=1).eq(1).mean()),
                                    long_side=float((T4.loc[red_dec] > 0).sum(axis=1).eq(1).mean()),
                                    n=int(len(single))))
    for lab, RR in (("PR", Rf), ("TR", Rtr)):
        pn = bf.evaluate(Hd, RR)["pnl"]
        gd = Hd.abs().sum(axis=1).shift(2).reindex(pn.index).fillna(0.0) > 0
        re_ = reduced.shift(2).reindex(pn.index).fillna(False).astype(bool)
        win = pn.index >= first_red
        contrib = (Hd.shift(2) * RR).reindex(pn.index)
        worst_name = contrib.min(axis=1)
        groups = {"full": win & gd & ~re_,
                  "reduced_single_fund_side": win & re_ & sf_e.reindex(pn.index).to_numpy(),
                  "reduced_other": win & re_ & ~sf_e.reindex(pn.index).to_numpy()}
        R5[lab] = {}
        for gname, msk in groups.items():
            x, wn = pn[msk], worst_name[msk]
            R5[lab][gname] = dict(n=int(len(x)), vol=float(x.std() * np.sqrt(P)), worst_day=float(x.min()),
                                  worst_day_date=str(x.idxmin().date()), ex_kurt=float(x.kurt()),
                                  worst_single_name_contrib=float(wn.min()),
                                  worst_single_name_date=str(wn.idxmin().date()),
                                  worst_single_name=str(contrib.loc[wn.idxmin()].idxmin()))
    OUT["R5_tails"] = R5
    p(f"\nR5. a single-fund side in the reduced target on {R5['single_fund_side']['any']:.1%} of "
      f"{R5['single_fund_side']['n']} reduced decisions (short side {R5['single_fund_side']['short_side']:.1%}, long side "
      f"{R5['single_fund_side']['long_side']:.1%}); tails at m, deferred, from {first_red.date()}:")
    for lab in ("PR", "TR"):
        for gname, r in R5[lab].items():
            p(f"  {lab} {gname:25s} n {r['n']:5d}  vol {r['vol']:.2%}  worst day {r['worst_day']:+.2%} ({r['worst_day_date']})  "
              f"excess kurtosis {r['ex_kurt']:.1f}  worst single-name day {r['worst_single_name_contrib']:+.2%} "
              f"({r['worst_single_name']}, {r['worst_single_name_date']})")

    # ------------------------------------------------------------ R6. crash-day stress
    full_dec = idx[(~thin6).to_numpy() & (idx >= first_red)]
    full_dec = full_dec[Hd.loc[full_dec].abs().sum(axis=1).to_numpy() > 0]
    uni = list(T6.columns)
    rr = Rf.where(Rf.abs() < 0.5)
    ew = rr.mean(axis=1)
    worst_days = ew.nsmallest(10).index
    R6 = {"days": {str(d.date()): float(ew.loc[d]) for d in worst_days}}
    for lab, dec in (("reduced", red_dec), ("full", full_dec)):
        W = Hd.loc[dec]
        pl = []
        for d in worst_days:
            r = rr.loc[d].reindex(uni)
            miss = r.isna()
            pl.append((W.loc[:, ~miss] * r[~miss]).sum(axis=1))
        worst_each = pd.concat(pl, axis=1).min(axis=1)
        R6[lab] = dict(per_book_worst_loss=q(-worst_each), share_loss_gt_5pct=float((worst_each < -0.05).mean()),
                       share_loss_gt_12pct=float((worst_each < -0.12).mean()))
    OUT["R6_crash_stress"] = R6
    p(f"\nR6. the fit's 10 worst equal-weight universe days ({', '.join(R6['days'])}) applied to every held book:")
    for lab in ("reduced", "full"):
        r = R6[lab]["per_book_worst_loss"]
        p(f"  {lab:7s}: per-book worst one-day loss p50 {r['p50']:.1%} p90 {r['p90']:.1%} p99 {r['p99']:.1%} max "
          f"{r['max']:.1%} [n {r['n']}]; loss over 5% on {R6[lab]['share_loss_gt_5pct']:.0%} of books, over 12% on "
          f"{R6[lab]['share_loss_gt_12pct']:.1%}")

    # ------------------------------------------------------------ R7. sponsor and muni
    facts = pd.read_csv(bf.DATA_DIR / "cef_facts.csv")
    facts = facts[facts["ticker"].isin(uni)]
    nm = facts.groupby("ticker")["longName"].agg(lambda x: set(x.dropna()))
    if not all(len(nm[t]) == 1 for t in uni):
        raise AssertionError("sponsor names ambiguous in cef_facts.csv")
    spons = {t: next(iter(nm[t])).split()[0].upper() for t in uni}
    grp = pd.read_parquet(bf.DATA_DIR / "cef_prices.parquet", columns=["ticker", "grp"]).drop_duplicates()
    grp = grp[grp["ticker"].isin(uni)]
    if grp.groupby("ticker")["grp"].nunique().max() != 1 or set(grp["ticker"]) != set(uni):
        raise AssertionError("muni/taxable group ambiguous in cef_prices.parquet")
    gmap = dict(zip(grp["ticker"], grp["grp"]))
    pim = [t for t in uni if spons[t] == "PIMCO"]
    mun = [t for t in uni if gmap[t] == "muni"]

    def qd(s):
        return dict(p50=float(s.quantile(.5)), p90=float(s.quantile(.9)), p99=float(s.quantile(.99)), max=float(s.max()))
    R7 = dict(pimco=pim, muni=mun)
    for lab, dec in (("reduced", red_dec), ("full", full_dec)):
        Hx = Hd.loc[dec]
        R7[lab] = dict(pimco_net_abs=qd(Hx[pim].sum(axis=1).abs()),
                       pimco_gross_share=qd(Hx[pim].abs().sum(axis=1) / Hx.abs().sum(axis=1)),
                       muni_net_abs=qd(Hx[mun].sum(axis=1).abs()))
    R7["reduced"]["eligible_pimco_count"] = {int(k): int(v) for k, v in
                                             T4.loc[red_dec][pim].ne(0).sum(axis=1).value_counts().sort_index().items()}
    OUT["R7_sponsor"] = R7
    p(f"\nR7. PIMCO {pim}; muni {mun}:")
    for lab in ("reduced", "full"):
        r = R7[lab]
        p(f"  {lab:7s}: |net PIMCO| p50 {r['pimco_net_abs']['p50']:.3f} p99 {r['pimco_net_abs']['p99']:.3f} max "
          f"{r['pimco_net_abs']['max']:.3f}; PIMCO share of gross p50 {r['pimco_gross_share']['p50']:.0%} max "
          f"{r['pimco_gross_share']['max']:.0%}; |net muni| max {r['muni_net_abs']['max']:.3f}")
    p(f"  eligible PIMCO names on reduced decisions: {R7['reduced']['eligible_pimco_count']}")

    # ------------------------------------------------------------ R8. margin
    px = pd.read_parquet(bf.DATA_DIR / "cef_prices.parquet", columns=["date", "ticker", "close"])
    px = px[px.ticker.isin(uni)].pivot(index="date", columns="ticker", values="close").sort_index()
    px.index = pd.to_datetime(px.index)
    last_close = str(px.index.max().date())
    today = px.ffill().iloc[-1][uni]                 # landmine 6: each name's own last close
    pfit = px.loc[:"2022-12-30"].ffill().reindex(idx).ffill()[uni]

    def long_rate(pr):
        return np.where(pr < 2.5, 1.0, np.where(pr <= 6.0, 0.5, 0.3))

    def short_rate(pr):
        return np.where(pr < 5.0, np.maximum(2.5 / pr, 1.0), np.maximum(5.0 / pr, 0.3))

    def maint(W, Pz):
        Wv, Pv = W.to_numpy(), Pz.to_numpy()
        rate = np.where(Wv > 0, long_rate(Pv), np.where(Wv < 0, short_rate(Pv), 0.0))
        return pd.Series(np.nansum(np.abs(Wv) * rate, axis=1), index=W.index)
    R8 = dict(panel_last_close=last_close, today_close={t: float(today[t]) for t in uni},
              today_short_rate={t: float(short_rate(np.array([today[t]]))[0]) for t in uni},
              today_long_rate={t: float(long_rate(np.array([today[t]]))[0]) for t in uni})
    for lab, dec, Hx in (("reduced", red_dec, Hd), ("te4_full", full_dec, Hd), ("flatten_full", full_dec, Fd)):
        W = Hx.loc[dec]
        tod = pd.DataFrame([today.values] * len(dec), index=dec, columns=uni)
        R8[lab] = dict(own_prices=q(maint(W, pfit.loc[dec])), last_close_prices=q(maint(W, tod)))
    m_all, g_all = maint(Hd, pfit), Hd.abs().sum(axis=1)
    ratio = (m_all / g_all).where(g_all > 0)
    jump = []
    for i0, _ in C.runs_of(reduced):
        if i0 > 0 and np.isfinite(ratio.iloc[i0]) and np.isfinite(ratio.iloc[i0 - 1]):
            jump.append(float(ratio.iloc[i0] - ratio.iloc[i0 - 1]))
    R8["ratio_rise_at_run_start"] = dict(n=len(jump), max=float(max(jump)) if jump else None)
    OUT["R8_margin"] = R8
    p(f"\nR8. maintenance / equity on the fit's held books (last close {last_close}; short tiers [V REFERENCES], long "
      f"tiers [S]):")
    for lab in ("reduced", "te4_full", "flatten_full"):
        a, b = R8[lab]["last_close_prices"], R8[lab]["own_prices"]
        p(f"  {lab:12s}: at the last closes p50 {a['p50']:.3f} p99 {a['p99']:.3f} above 0.9 {a['share_gt_0_9']:.1%} "
          f"above 1.0 {a['share_gt_1']:.2%}; at each decision's own closes max {b['max']:.3f} [n {a['n']}]")
    p(f"  largest rise of the blended maintenance ratio at the start of a reduced run: "
      f"{R8['ratio_rise_at_run_start']['max']:.4f} over {R8['ratio_rise_at_run_start']['n']} runs")
    p(f"  short rate at the last closes: " + ", ".join(f"{t} {v:.2f} (${R8['today_close'][t]:.2f})"
                                                     for t, v in R8["today_short_rate"].items()))

    # ------------------------------------------------------------ R9. horizon-matched K1
    DE = json.loads(comp.read_text())["in_episode"]["D_E"]
    R9 = []
    for lab, RR in (("PR", Rf), ("TR", Rtr)):
        pn = bf.evaluate(Hd, RR)["pnl"]
        for e in eps:
            x = pn.loc[C.earn_days(idx, e["parts"]).intersection(pn.index)]
            row = dict(basis=lab, first=str(idx[e["i0"]].date()), days=int(len(x)))
            for L in (21, 63, 126, 252):
                mdd = float(max_drawdown(x.iloc[:L])["mdd"])
                row[f"dd{L}"], row[f"fires{L}"] = mdd, bool(mdd >= DE[str(L)]["D_E"])
            R9.append(row)
    OUT["R9_k1_horizon"] = dict(D_E={L: DE[str(L)]["D_E"] for L in ("21", "63", "126", "252")}, episodes=R9)
    fired = [r for r in R9 if any(r[f"fires{L}"] for L in (21, 63, 126, 252))]
    p(f"\nR9. a horizon-matched K1 (D_E(L) from {comp.name}: " +
      ", ".join(f"{L} {DE[L]['D_E']:.2%}" for L in ("21", "63", "126", "252")) + f"): fires on {len(fired)} of "
      f"{len(R9)} episode-bases: " + "; ".join(
          f"{r['basis']} {r['first']} (" + ", ".join(f"L{L} {r[f'dd{L}']:.2%}" for L in (21, 63, 126, 252)
                                                   if r[f'fires{L}']) + ")" for r in fired))

    # ------------------------------------------------------------ R10. the cost grid's notional
    dHf, dHt = Fd.diff().abs().sum(axis=1), Hd.diff().abs().sum(axis=1)
    R10 = []
    for e in eps:
        i0, i1 = e["i0"], e["i1"]
        j = i1 + 1
        red_rows = [i for a, b in e["parts"] for i in range(a, b + 1)]
        R10.append(dict(first=str(idx[i0].date()), runs=len(e["parts"]),
                        flatten_actual=float(dHf.iloc[i0:j + 1].sum()), flatten_formula=float(dHf.iloc[i0] + dHf.iloc[j]),
                        te4_actual=float(dHt.iloc[i0:j + 1].sum()),
                        te4_formula=float(dHt.iloc[red_rows].sum() + dHt.iloc[j])))
        r = R10[-1]
        r["net15_error_pp"] = float(((r["te4_actual"] - r["flatten_actual"]) - (r["te4_formula"] - r["flatten_formula"]))
                                    * 0.0015 * 100)
    OUT["R10_cost_notional"] = R10
    p("\nR10. traded notional per fit episode, NAV units (m, deferred): actual (gaps included) against the draft's "
      "first formula; the error in net at 15bp (actual minus formula; negative = the formula over-charged te4):")
    for r in R10:
        p(f"  {r['first']} ({r['runs']} runs): flatten {r['flatten_actual']:.2f} vs {r['flatten_formula']:.2f}; te4 "
          f"{r['te4_actual']:.2f} vs {r['te4_formula']:.2f}; net@15bp error {r['net15_error_pp']:+.2f}pp")

    outs[0].write_text(json.dumps(OUT, indent=1, default=str))
    outs[1].write_text("\n".join(LOG) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
