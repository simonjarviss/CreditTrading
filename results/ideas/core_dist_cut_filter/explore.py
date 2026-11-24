"""Explore: do the live discount books buy a fund that has just CUT its distribution, and what would a fixed hold-off rule have done?

    python3 results/ideas/core_dist_cut_filter/explore.py --data <a checkout's data/cef> --families <its data/cef_families>

WHY: results/ideas/2026-11-16_cef_dist_changes.md found, on every CRSP closed-end fund since
2000, that a fund which cuts its regular distribution by 5% or more falls 130bp against the CEF
market in the announcement window and a further 85bp over the next 20 sessions and 137bp over
60 (n 2,224). A cut widens the discount, and the desk's two live books buy funds whose discount
has widened. The team lead asked on 2026-11-18 how that research can be used in the live books.
This measures, on the canonical harness, whether the books do buy fresh cuts and what a simple
rule would have done. It is research on a copy of the logic: nothing in the sleeve, ops/specs,
ops/books or data/ is touched, and nothing is written under data/.

HOW THIS DIFFERS FROM THE TWO DEAD USES OF DISTRIBUTION DATA (docs/RESEARCH_STATE.md,
"Distribution data"; pre-clean-slate:results/cef/ESTIMATOR_NOTE.md). (1) A distribution-cut
FILTER on the universe: 8 variants were run and the 1 that beat the baseline was chosen after
looking at all 8. (2) A cut-inflation term inside the Kalman estimator: 1.60 -> 1.28. Both
were on the 17-name book of the time, shift(1) era, IBKR. What is tested here is the same family
as (1), a hold-off on a fund after a cut, so it is a RE-TEST of a dead line and is counted as
one. It differs in three ways only: the event list and the two windows come from an outside
study of 2,224 events and not from this book's P&L; exactly two rules and two windows are fixed
below and nothing is chosen among them; and the placebo says whether any gain is the cut or
merely holding less of a fund.

FIXED BEFORE ANY RETURN WAS READ (2026-11-18). Only counts had been read: 38 qualifying cuts on
10 of the 13 core funds with a declaration from 2013-06-25 to 2025-12-31 (none in 2024-25);
236 on 58 of the 74 C4 funds from 2005; CRSP types every core fund's regular payment monthly;
data/cef/cef_distributions.parquet carries ex-dates and amounts only, no declaration date, last
ex-date 2026-09-03.

  BOOKS     CORE: the frozen spec's targets, `build_targets(source=(prices, nav))`, then
            `band(T, BAND_WIDTH)`, from scripts/cef/band_frontier.py, unchanged, exactly as
            results/ideas/core_group_cap/explore.py. shift(2) through harness.evaluate. Price
            returns, as every core baseline. From the first session the book holds.
            C4: the same functions on data/cef_families with the C4 spec's 74 funds and its
            nav-repeat and zero-volume masks (`c4_families.declared_mask`), which is CEF trial
            52's z book. The live C4 spec has since 2026-11-03 blended in a within-family
            discount-LEVEL target (trial 54); `c4_paper_benchmark.spec_targets` builds that
            blend from the trial's own code, and it is run as well if it accepts the full
            panel. No new backtester is written for either.
            Every live parameter is read from the specs; the C4 spec's z window, vol target,
            band, ADV floor and minimum names are asserted equal to the core's, which the
            harness's module constants carry.
  EVENTS    `declarations()` imported from results/ideas/cef_dist_changes/explore.py, so the
            definition is that card's to the letter: CRSP regular cash dividend ('CD','CDIV',
            monthly or quarterly), amount down 5% or more on the previous one, the two before
            within 5% of each other, same frequency, no split between, ratio 0.1 to 3, a
            declaration date not after the ex-date, first ex-date carrying that declaration.
            Read from the staged ~/quantt_research/cef_dist_changes/raw_dist.parquet (to
            2025-12-31; nothing is pulled here). The card's price and volume filter is NOT
            applied: the book's own eligibility decides what it can hold.
  MAPPING   desk ticker -> the permno carrying that ticker on the CRSP panel's last date
            (~/quantt_research/crsp_cef_daily.parquet). Checked, and raised on if it fails:
            the correlation of CRSP's daily price return (retx) with the desk panel's own close
            return over their common sessions must be at least 0.95 for every fund.
  TIMING    D0 = the first session of the book's index on or after CRSP's declaration date.
            Known at the close of K = D0 + 1 (the card's extra session). The rule changes the
            TARGET rows K .. K+H-1; a target decided at t fills at t+1 and earns t+2, so the
            changed rows earn K+2 .. K+1+H, the card's window. ALIGNMENT asserted: K is
            strictly after the declaration date, and no changed row is before K.
  (1) DESCRIPTIVE, no rule. For each cut with K on or after the book's first held session:
            the banded position decided at K-3 (the last decision before the announcement
            window D0-1 .. K+1), at K-1 and at K; the frictionless target at K-3, K and K+5;
            the banded position at K+5; the fund's discount and z at K-3 and K. "Bought more" =
            the banded position at K+5 is above the one at K-3. The same changes at the same
            funds' UNCHANGED declarations (below) are shown beside them.
            The book's P&L in the cut fund over its earning sessions K+2 .. K+1+h (h = 20, 60)
            against h times the same fund's mean daily P&L on every other session from the
            book's first; t clustered by month of K.
            The card's result re-read on our names with the desk's own panels: the fund's
            compounded price return over K+2 .. K+1+h less the equal-weighted return of the
            book's universe, and, which the card could not do, the same for its NAV return and
            the change in its discount less the universe's mean change.
  (2) RULE  two variants, two windows, nothing else. For H = 20 and H = 60 decision sessions:
            NNL   NO NEW LONG: the fund's target on rows K .. K+H-1 may not be above the
                  position the unchanged banded book held when the cut became known (its
                  position decided at K-1). A short may therefore not be covered either.
            FLAT  the fund's target on those rows is zero.
            Applied to the targets BEFORE the band, as core_group_cap applies its cap; nothing
            else moves, so the book is no longer exactly dollar-neutral inside a window.
            Windows of one fund that overlap take the lower cap.
            Compared with the unchanged book on Sharpe, return, volatility, worst drawdown,
            turnover, eras (core 2013-15, 2016-19, 2020-22, 2023-26; C4 the harness's five) and
            both halves, plus the daily difference rule less unchanged with its t.
  TURNOVER  the desk compares only within 5% turnover. The change is reported; a variant that
            moves turnover by more than 5% is also shown with the band width moved (bisection,
            within 1%) until turnover matches, labelled as a derived width.
  CONTROLS  fixed here. Both use the same rule, the same count of events per fund, 200 draws,
            seed 20261118:
            UNCH  dates drawn without replacement from that fund's own unchanged declarations
                  (amount within 0.5% of the previous, not within 60 sessions after one of the
                  fund's own 5% changes), dated K the same way. Same place in the ex-date
                  cycle, no news.
            RAND  sessions drawn uniformly without replacement from the book's first held
                  session to the last session an event could be dated.
            If the real cuts do not beat the placebo distribution, any gain is from holding
            less of a fund, or luck, not from the cut.
  SECONDARY (labelled, not the test) EXD: the same events dated from the EX-DATE close, target
            rows X .. X+H-1. This is the only form the desk's own panel could drive, since it
            has no declaration date. The card's own figure from the ex-date is -62bp over 20
            sessions. Also the live gross ceiling (`band_gross_capped` at each spec's
            max_gross_stress) and total returns (`total_returns`) as checks that the answer
            is not special to the plain band or to price returns.
  EXPECTED  with about 3 events a year on 13 funds, each moving one position of a few percent
            of capital for 20 to 60 sessions against an 85 to 137bp drift, the rule can be
            worth at most a few basis points of return a year on the core book. I expect the
            difference to be inside the placebo band on the core, and the C4 book, with six
            times the events, to be the only place a decision could come from. A null, or "too
            few events to tell", is a result.
  COUNTED   a re-test of the dead "distribution data" line (above). One look, four variants,
            two books.

Gross; the desk's 5/15/30bp grid is not shown because turnover is reported and the rule is
judged on the gross difference. Writes results.json (aggregates only; no per-security CRSP row)
beside this file. Prints the tables.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore as _explore  # noqa: E402,F401  turns numexpr off (see its header)

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
CRSP_PANEL = Path.home() / "quantt_research" / "crsp_cef_daily.parquet"
HOLDS = (20, 60)
KINDS = ("NNL", "FLAT")
PRE = 3                          # K-3: the last decision before the announcement window D0-1 .. K+1
POST = 5
BLOCK = 60
N_PLACEBO, SEED = 200, 20261118
TURN_TOL, MATCH_TOL = 0.05, 0.01
MAP_MIN_CORR = 0.95
CORE_ERAS = (("2013", "2015"), ("2016", "2019"), ("2020", "2022"), ("2023", "2026"))
C4_ERAS = (("2005", "2009"), ("2010", "2014"), ("2015", "2019"), ("2020", "2022"), ("2023", "2026"))


def card_module():
    """results/ideas/cef_dist_changes/explore.py, imported so its event definition is reused, not copied."""
    f = REPO / "results" / "ideas" / "cef_dist_changes" / "explore.py"
    spec = importlib.util.spec_from_file_location("cef_dist_changes_explore", f)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if not (m.STAGE / "raw_dist.parquet").exists():
        raise RuntimeError(f"{m.STAGE / 'raw_dist.parquet'} is not staged; run the cef_dist_changes reproducer first")
    return m


# ---------------------------------------------------------------------------- events
def permno_map(tickers: list[str], close: pd.DataFrame, confirmed: dict | None = None) -> tuple[dict, dict]:
    """desk ticker -> permno, by the ticker CRSP carries on its last date, checked on returns.

    FIX MADE AFTER THE FIRST RUN STOPPED HERE (2026-11-18; the core block had printed, no C4 figure
    existed). The 0.95 return-correlation bar refused ADX at 0.948 on the families panel. A
    correlation is in any case a weak identity check among equity funds, which correlate highly
    with each other. `confirmed` is an independent map (data/cef_families/crsp_permno_map.csv, built
    by the desk's own price join for trial C4): where it names the same permno the fund is accepted
    whatever the correlation, and where it names a different one the fund must correlate at
    least 0.99 on at least 100 sessions or this raises (second stop, same day: BTX, see below). Without it (the
    core book) the bar is unchanged. Funds accepted below the bar are listed in the output."""
    c = pd.read_parquet(CRSP_PANEL, columns=["permno", "ticker", "date", "retx"])
    c["date"] = pd.to_datetime(c["date"])
    last = c[c.date == c.date.max()].drop_duplicates("ticker").set_index("ticker").permno
    miss = [t for t in tickers if t not in last.index]
    out, corr, disagree = {}, {}, {}
    mine = close.pct_change(fill_method=None)
    for t in tickers:
        if t in miss:
            continue
        x = c[c.permno == last[t]].set_index("date").retx
        j = pd.concat([x, mine[t]], axis=1, join="inner").dropna()
        j = j[(j.abs() < 0.5).all(axis=1)]
        if len(j) < (250 if confirmed is None else 30):     # the desk map carries the identity where it exists (see the docstring)
            raise RuntimeError(f"{t}: only {len(j)} common sessions with CRSP permno {last[t]}")
        r = float(j.corr().iloc[0, 1])
        if confirmed is not None and int(confirmed.get(t, -1)) != int(last[t]):
            # The two maps disagree (BTX on 2026-11-18: the desk map, read to 2024-12-31, names a permno that is
            # not a closed-end fund in the CRSP panel; the fund took the ticker BTX from BIGZ in 2025). Accepted
            # only on a 0.99 return correlation, and listed in the output; otherwise raise.
            if r < 0.99 or len(j) < 100:                 # stricter on correlation: the paired C4 panel holds 232 BTX sessions
                raise RuntimeError(f"{t}: CRSP's last-date ticker gives permno {last[t]} (corr {r:.3f}, {len(j)} sessions), the desk's own map gives {confirmed.get(t)}")
            disagree[t] = {"used": int(last[t]), "desk_map": confirmed.get(t), "corr": round(r, 4), "sessions": int(len(j))}
        elif confirmed is None and r < MAP_MIN_CORR:
            raise RuntimeError(f"{t}: CRSP permno {last[t]} price returns correlate {r:.3f} with the desk panel; mapping refused")
        out[t], corr[t] = int(last[t]), r
    return out, {"unmapped": miss, "min_corr": round(min(corr.values()), 4), "crsp_last": str(c.date.max().date()),
                 "below_the_bar_but_confirmed_by_the_desk_map": {t: round(v, 3) for t, v in corr.items() if v < MAP_MIN_CORR},
                 "confirmed_against_the_desk_map": confirmed is not None, "desk_map_disagrees_resolved_on_returns": disagree}


def events_for(dc, pmap: dict, idx: pd.DatetimeIndex, cols: list[str]) -> pd.DataFrame:
    """Every regular declaration of the mapped funds on the book's own session index, with K."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")                    # the card's function sets columns on a slice; its output is checked by count below
        g, _ = dc.declarations()
    inv = {v: k for k, v in pmap.items()}
    g = g[g.permno.isin(inv)].copy()
    g["tk"] = g.permno.map(inv)
    g = g[g.decl.notna() & (g.decl <= g.disexdt)].copy()
    g["d0"] = idx.searchsorted(g.decl.to_numpy(), side="left")
    g["k"] = g.d0 + 1
    g["kx"] = idx.searchsorted(g.disexdt.to_numpy(), side="left")     # the ex-date session (secondary dating)
    g = g[(g.k + 2 < len(idx)) & (g.d0 >= PRE + 1)].copy()
    # ALIGNMENT: K is strictly after CRSP's declaration date; the ex-date session is not before the ex-date.
    assert (idx[g.k.to_numpy()] > g.decl.to_numpy()).all(), "lookahead: K is not after the declaration date"
    assert (idx[np.minimum(g.kx.to_numpy(), len(idx) - 1)] >= g.disexdt.to_numpy())[g.kx.to_numpy() < len(idx)].all()
    g["j"] = g.tk.map({t: i for i, t in enumerate(cols)})
    g["cut"] = g.event & (g.chg < 0)
    g["raise_"] = g.event & (g.chg > 0)
    # unchanged control: not within BLOCK sessions after one of the fund's own 5% changes
    ok = []
    chg_k = {t: np.sort(x.k.to_numpy()) for t, x in g[g.any_change].groupby("tk")}
    for t, k in zip(g.tk, g.k):
        ks = chg_k.get(t, np.array([], int))
        ok.append(not ((ks <= k) & (ks >= k - BLOCK)).any())
    g["unch_ctrl"] = g.unchanged & np.array(ok)
    g["ymonth"] = pd.Series(idx[g.k.to_numpy()], index=g.index).dt.to_period("M").astype(str)
    return g.sort_values(["k", "tk"]).reset_index(drop=True)


# ---------------------------------------------------------------------------- the rule
def apply_rule(T: pd.DataFrame, Href: pd.DataFrame, k: np.ndarray, j: np.ndarray, h: int, kind: str) -> pd.DataFrame:
    """Targets with the hold-off applied on rows k .. k+h-1 of column j, for each (k, j).
    ALIGNMENT: row k is the decision at the close the cut is known at; the NNL cap reads the
    unchanged book's position decided at k-1. Nothing before row k changes (asserted)."""
    A = T.to_numpy().copy()
    cap = np.full(A.shape, np.inf)
    ref = Href.to_numpy()
    n = len(A)
    for kk, jj in zip(k, j):
        a1 = min(kk + h, n)
        cap[kk:a1, jj] = np.minimum(cap[kk:a1, jj], 0.0 if kind == "FLAT" else ref[kk - 1, jj])
    hit = np.isfinite(cap)
    if kind == "FLAT":
        A[hit] = 0.0
    elif kind == "NNL":
        A = np.minimum(A, cap)
    else:
        raise ValueError(kind)
    if len(k):
        first = int(np.min(k))
        assert np.array_equal(A[:first], T.to_numpy()[:first]), "a target before the first K changed"
    return pd.DataFrame(A, index=T.index, columns=T.columns)


def st(p: pd.Series) -> dict:
    sd = p.std()
    cum = p.cumsum()
    return {"ann_ret_pct": round(100 * p.mean() * 252, 3), "vol_pct": round(100 * sd * 252 ** 0.5, 3),
            "sharpe": round(p.mean() / sd * 252 ** 0.5, 3) if sd > 0 else None,
            "t": round(p.mean() / sd * len(p) ** 0.5, 2) if sd > 0 else None,
            "max_dd_pct": round(100 * (cum - cum.cummax()).min(), 2)}


def clustered(x: np.ndarray, cl: np.ndarray) -> dict:
    """Mean of x with a t clustered on cl (month of K), as the card's cluster_t."""
    s = pd.DataFrame({"x": x, "c": cl}).dropna()
    if len(s) < 5:
        return {"n": int(len(s)), "mean": None, "median": None, "share_positive": None, "t": None}
    e = s.x - s.x.mean()
    se = np.sqrt((e.groupby(s.c).sum() ** 2).sum()) / len(s)
    return {"n": int(len(s)), "mean": round(float(s.x.mean()), 3), "median": round(float(s.x.median()), 3),
            "share_positive": round(float((s.x > 0).mean()), 3), "t": round(float(s.x.mean() / se), 2) if se > 0 else None}


# ---------------------------------------------------------------------------- one book
def run_book(name: str, T: pd.DataFrame, R: pd.DataFrame, p: dict, ev: pd.DataFrame, eras, band_w: float, cap_gross: float,
             R_total: pd.DataFrame | None, placebo: bool = True) -> dict:
    from scripts.cef import band_frontier as bf
    from scripts.research import harness
    idx, cols = T.index, list(T.columns)
    n = len(idx)
    H0 = bf.band(T, band_w)
    first = harness.held(H0).abs().sum(axis=1).gt(0).idxmax()
    f0 = idx.get_loc(first)
    S = slice(first, None)
    cuts = ev[ev.cut & (ev.k >= f0)].reset_index(drop=True)
    unch = ev[ev.unch_ctrl & (ev.k >= f0)].reset_index(drop=True)
    k, j = cuts.k.to_numpy(), cuts.j.to_numpy()
    years = (idx[-1] - first).days / 365.25
    last_event = str(idx[k.max()].date()) if len(k) else None
    out = {"panel_last": str(idx.max().date()), "first_held": str(first.date()), "funds": len(cols), "band_width": band_w,
           "events": {"cuts": int(len(cuts)), "funds_with_a_cut": int(cuts.tk.nunique()), "per_year": round(len(cuts) / years, 2),
                      "by_year": {int(a): int(b) for a, b in pd.Series(idx[k].year).value_counts().sort_index().items()},
                      "by_fund": cuts.tk.value_counts().sort_index().to_dict(),
                      "median_change": round(float(cuts.chg.median()), 4) if len(cuts) else None,
                      "last_cut_known": last_event, "unchanged_declarations_control": int(len(unch)),
                      "raises_same_definition": int((ev.raise_ & (ev.k >= f0)).sum())}}

    def score(H: pd.DataFrame, Ruse: pd.DataFrame = R) -> dict:
        e = harness.evaluate(H, Ruse)
        pnl = e["pnl"]
        mid = pnl.loc[S].index[len(pnl.loc[S]) // 2]
        o = {**st(pnl.loc[S]), "turnover_per_year": round(float(e["turn_series"].loc[S].mean() * 252), 3),
             "mean_gross": round(float(H.abs().sum(axis=1).loc[S].mean()), 4),
             "mean_abs_net": round(float(H.sum(axis=1).abs().loc[S].mean()), 4),
             "halves": {"split": str(mid.date()), "early": st(pnl.loc[first:mid])["sharpe"], "late": st(pnl.loc[mid:])["sharpe"]},
             "eras": {f"{lo}-{hi}": {"sharpe": st(pnl.loc[max(lo, str(first.date())):hi])["sharpe"],
                                     "ann_ret_pct": st(pnl.loc[max(lo, str(first.date())):hi])["ann_ret_pct"]} for lo, hi in eras}}
        o["_pnl"] = pnl
        return o

    def versus(r: dict, b: dict) -> None:
        d = (r["_pnl"] - b["_pnl"]).loc[S]
        mid = d.index[len(d) // 2]
        r["diff_vs_unchanged"] = {"ann_ret_bp": round(float(1e4 * d.mean() * 252), 2),
                                  "t": round(float(d.mean() / d.std() * len(d) ** 0.5), 2) if d.std() > 0 else None,
                                  "sharpe_diff": round(r["sharpe"] - b["sharpe"], 4),
                                  "turnover_change": round(r["turnover_per_year"] / b["turnover_per_year"] - 1, 4),
                                  "by_era_ann_ret_bp": {f"{lo}-{hi}": round(float(1e4 * d.loc[lo:hi].mean() * 252), 2) for lo, hi in eras},
                                  "halves_ann_ret_bp": [round(float(1e4 * d.loc[:mid].mean() * 252), 2), round(float(1e4 * d.loc[mid:].mean() * 252), 2)]}

    def matched(Tc: pd.DataFrame, target: float) -> tuple[pd.DataFrame, float]:
        lo, hi = band_w / 4, band_w * 4
        for _ in range(40):
            b = (lo + hi) / 2
            H = bf.band(Tc, b)
            t = float(H.diff().abs().sum(axis=1).fillna(0.0).loc[S].mean() * 252)
            if abs(t / target - 1) < MATCH_TOL:
                return H, b
            lo, hi = (b, hi) if t > target else (lo, b)
        raise RuntimeError("no band width matches the unchanged turnover")

    base = score(H0)
    out["variants"] = {"UNCHANGED": base}

    # ------------------------------------------------------------------ (1) descriptive
    Tn, Hn = T.to_numpy(), H0.to_numpy()
    # UNITS FIX (2026-11-18, after the first complete run): build_panel's `disc` is in PERCENT. The first run
    # multiplied it again by 100 (and by 1e4 for the bp column), so the two discount columns printed 100
    # times too large. Nothing else read them; no rule or P&L figure changed.
    disc, z = p["disc"].reindex(idx)[cols].ffill().to_numpy(), p["z"].reindex(idx)[cols].to_numpy()
    Wn = harness.held(H0).to_numpy()
    contrib = Wn * R.to_numpy()                                    # the book's daily P&L by fund

    def position_table(e: pd.DataFrame) -> dict:
        kk, jj = e.k.to_numpy(), e.j.to_numpy()
        ok = kk + POST < n
        kk, jj = kk[ok], jj[ok]
        if not len(kk):
            return {"n": 0}
        hpre, hk1, hk, hpost = Hn[kk - PRE, jj], Hn[kk - 1, jj], Hn[kk, jj], Hn[kk + POST, jj]
        tpre, tk, tpost = Tn[kk - PRE, jj], Tn[kk, jj], Tn[kk + POST, jj]
        live = (np.abs(tpre) + np.abs(tk) + np.abs(tpost) + np.abs(hpre) + np.abs(hpost)) > 0
        dd = disc[kk, jj] - disc[kk - PRE, jj]
        dz = z[kk, jj] - z[kk - PRE, jj]
        cl = e.ymonth.to_numpy()[ok]
        return {"n": int(len(kk)), "n_fund_in_the_book": int(live.sum()),
                "held_long_at_K-1": int((hk1 > 0).sum()), "held_short_at_K-1": int((hk1 < 0).sum()), "flat_at_K-1": int((hk1 == 0).sum()),
                "mean_position_K-3_pct": round(100 * float(hpre.mean()), 3), "mean_position_K_pct": round(100 * float(hk.mean()), 3),
                "mean_position_K+5_pct": round(100 * float(hpost.mean()), 3),
                "mean_target_K-3_pct": round(100 * float(tpre.mean()), 3), "mean_target_K_pct": round(100 * float(tk.mean()), 3),
                "mean_target_K+5_pct": round(100 * float(tpost.mean()), 3),
                "target_change_K-3_to_K+5_pct": clustered(100 * (tpost - tpre), cl),
                "position_change_K-3_to_K+5_pct": clustered(100 * (hpost - hpre), cl),
                "bought_more_position_up_K-3_to_K+5": int((hpost > hpre + 1e-12).sum()),
                "sold_position_down_K-3_to_K+5": int((hpost < hpre - 1e-12).sum()),
                "target_up_K-3_to_K+5": int((tpost > tpre + 1e-12).sum()), "target_down_K-3_to_K+5": int((tpost < tpre - 1e-12).sum()),
                "long_at_K+5": int((hpost > 0).sum()), "short_at_K+5": int((hpost < 0).sum()),
                "discount_change_K-3_to_K_pp": clustered(dd, cl), "z_change_K-3_to_K": clustered(dz, cl)}

    desc = {"cuts": position_table(cuts), "unchanged_declarations_same_funds": position_table(unch[unch.tk.isin(cuts.tk.unique())])}
    # the book's P&L in the fund after a cut, against the same fund's other sessions
    ret_nan = p["ret"].reindex(idx)[cols]
    mkt = ret_nan.mean(axis=1).fillna(0.0).to_numpy()
    Rf = ret_nan.fillna(0.0).to_numpy()
    navr = p["nav"].reindex(idx)[cols].pct_change(fill_method=None).where(lambda x: x.abs() < 0.5)
    navm = navr.mean(axis=1).fillna(0.0).to_numpy()
    navf = navr.fillna(0.0).to_numpy()
    dmean = np.nanmean(np.where(np.isfinite(disc), disc, np.nan), axis=1)
    cl_all = cuts.ymonth.to_numpy()
    for h in HOLDS:
        inwin = np.zeros((n, len(cols)), bool)
        for kk, jj in zip(k, j):
            inwin[kk + 2: min(kk + 2 + h, n), jj] = True
        livecol = np.zeros((n, len(cols)), bool)
        livecol[f0:] = True
        ev_sum, ev_excess, rel, nav_rel, disc_rel, wpos = [], [], [], [], [], []
        for kk, jj in zip(k, j):
            a0, a1 = kk + 2, kk + 2 + h
            if a1 > n:
                for lst in (ev_sum, ev_excess, rel, nav_rel, disc_rel, wpos):
                    lst.append(np.nan)
                continue
            other = livecol[:, jj] & ~inwin[:, jj]
            s = contrib[a0:a1, jj].sum()
            ev_sum.append(1e4 * s)
            ev_excess.append(1e4 * (s - h * contrib[other, jj].mean()))
            wpos.append(100 * Wn[a0:a1, jj].mean())
            rel.append(1e4 * (np.prod(1 + Rf[a0:a1, jj]) - np.prod(1 + mkt[a0:a1])))
            nav_rel.append(1e4 * (np.prod(1 + navf[a0:a1, jj]) - np.prod(1 + navm[a0:a1])))
            disc_rel.append(100 * ((disc[a1 - 1, jj] - disc[a0 - 1, jj]) - (dmean[a1 - 1] - dmean[a0 - 1])))   # disc is in percent (build_panel)
        wpos = np.array(wpos)
        desc[f"h{h}"] = {
            "book_pnl_in_cut_fund_bp_of_capital": clustered(np.array(ev_sum), cl_all),
            "less_h_times_the_funds_mean_on_other_sessions_bp": clustered(np.array(ev_excess), cl_all),
            "total_over_all_events_bp_of_capital": round(float(np.nansum(ev_sum)), 1),
            "mean_position_held_in_window_pct": round(float(np.nanmean(wpos)), 3),
            "events_held_long_on_average": int(np.nansum(wpos > 0)), "events_held_short_on_average": int(np.nansum(wpos < 0)),
            "fund_price_return_less_universe_bp": clustered(np.array(rel), cl_all),
            "fund_nav_return_less_universe_bp": clustered(np.array(nav_rel), cl_all),
            "fund_discount_change_less_universe_bp": clustered(np.array(disc_rel), cl_all),
            "pnl_long_events_bp": clustered(np.where(wpos > 0, ev_sum, np.nan), cl_all),
            "pnl_short_events_bp": clustered(np.where(wpos < 0, ev_sum, np.nan), cl_all)}
    ann = [1e4 * (np.prod(1 + Rf[kk - 2: kk + 2, jj]) - np.prod(1 + mkt[kk - 2: kk + 2])) for kk, jj in zip(k, j)]
    desc["announcement_window_price_less_universe_bp_D0-1_to_K+1"] = clustered(np.array(ann), cl_all)
    out["descriptive"] = desc

    # ------------------------------------------------------------------ (2) the rule
    def rule_books(kk, jj, Href, policy):
        for kind in KINDS:
            for h in HOLDS:
                yield f"{kind}/{h}", policy(apply_rule(T, Href, kk, jj, h, kind))

    for key, H in rule_books(k, j, H0, lambda Tc: bf.band(Tc, band_w)):
        r = score(H)
        versus(r, base)
        kind, _, h = key.partition("/")
        Tc = apply_rule(T, H0, k, j, int(h), kind)
        r["target_cells_changed"] = int((Tc.to_numpy() != Tn).sum())
        r["share_of_live_fund_days_changed"] = round(float((Tc.to_numpy() != Tn)[f0:].mean()), 5)
        if abs(r["diff_vs_unchanged"]["turnover_change"]) > TURN_TOL:
            Hm, b = matched(Tc, base["turnover_per_year"])
            m = score(Hm)
            versus(m, base)
            m["band_width_used"] = round(b, 5)
            m.pop("_pnl")
            r["turnover_matched"] = m
        out["variants"][key] = r

    # secondary: dated from the ex-date close
    cx = cuts[(cuts.kx >= f0) & (cuts.kx + 2 < n)]
    out["secondary_ex_date_dating"] = {"events": int(len(cx)), "median_sessions_K_to_ex_date": float((cx.kx - cx.k).median()) if len(cx) else None}
    for key, H in rule_books(cx.kx.to_numpy(), cx.j.to_numpy(), H0, lambda Tc: bf.band(Tc, band_w)):
        r = score(H)
        versus(r, base)
        r.pop("_pnl")
        out["secondary_ex_date_dating"][key] = r

    # check: the live gross ceiling
    Hc0 = bf.band_gross_capped(T, band_w, cap_gross)
    cb = score(Hc0)
    out["check_gross_ceiling"] = {"cap": cap_gross, "UNCHANGED": cb}
    for key, H in rule_books(k, j, Hc0, lambda Tc: bf.band_gross_capped(Tc, band_w, cap_gross)):
        r = score(H)
        versus(r, cb)
        r.pop("_pnl")
        out["check_gross_ceiling"][key] = r
    cb.pop("_pnl")

    # check: total returns
    if R_total is not None:
        tb = score(H0, R_total)
        out["check_total_returns"] = {"UNCHANGED": tb}
        for key, H in rule_books(k, j, H0, lambda Tc: bf.band(Tc, band_w)):
            r = score(H, R_total)
            versus(r, tb)
            r.pop("_pnl")
            out["check_total_returns"][key] = r
        tb.pop("_pnl")

    # ------------------------------------------------------------------ controls
    if placebo and len(cuts):
        rng = np.random.default_rng(SEED)
        need = cuts.groupby("j").size()
        pool_u = {jj: unch[unch.j == jj].k.to_numpy() for jj in need.index}
        short = {cols[jj]: (int(need[jj]), int(len(pool_u[jj]))) for jj in need.index if len(pool_u[jj]) < need[jj]}
        hi_k = int(k.max())
        out["placebo"] = {"n": N_PLACEBO, "seed": SEED, "funds_with_too_few_unchanged_declarations": short}
        # FIX MADE WHEN THE FIRST C4 RUN STOPPED HERE (2026-11-18, before any C4 figure was printed): two C4
        # funds that pay a share of NAV (HQH, HQL) have one fewer unchanged declaration than cuts. For such a
        # fund UNCH uses every unchanged declaration it has and fills the shortfall with random sessions, as
        # RAND draws them. The funds and counts are in the output (cuts, unchanged) and on the card.
        draws = {"UNCH": [], "RAND": []}
        for _ in range(N_PLACEBO):
            ku, kr, jl = [], [], []
            for jj, m in need.items():
                mu = min(m, len(pool_u[jj]))
                ku += list(rng.choice(pool_u[jj], size=mu, replace=False)) + list(rng.choice(np.arange(f0, hi_k + 1), size=m - mu, replace=False))
                kr += list(rng.choice(np.arange(f0, hi_k + 1), size=m, replace=False))
                jl += [jj] * m
            draws["UNCH"].append((np.array(ku), np.array(jl)))
            draws["RAND"].append((np.array(kr), np.array(jl)))
        for ctl, dl in draws.items():
            rows = {f"{kind}/{h}": [] for kind in KINDS for h in HOLDS}
            for kk, jj in dl:
                for key, H in rule_books(kk, jj, H0, lambda Tc: bf.band(Tc, band_w)):
                    pn = harness.evaluate(H, R)["pnl"].loc[S]
                    d = pn - base["_pnl"].loc[S]
                    rows[key].append((1e4 * d.mean() * 252, pn.mean() / pn.std() * 252 ** 0.5 - base["sharpe"]))
            out["placebo"][ctl] = {}
            for key, v in rows.items():
                P = pd.DataFrame(v, columns=["ann_ret_bp", "sharpe_diff"])
                real = out["variants"][key]["diff_vs_unchanged"]
                out["placebo"][ctl][key] = {c: {"real": real[c], "placebo_mean": round(float(P[c].mean()), 4),
                                                "placebo_median": round(float(P[c].median()), 4),
                                                "placebo_p5": round(float(P[c].quantile(0.05)), 4), "placebo_p95": round(float(P[c].quantile(0.95)), 4),
                                                "share_placebo_at_or_above_real": round(float((P[c] >= real[c]).mean()), 3)} for c in P.columns}
    for r in out["variants"].values():
        r.pop("_pnl")
    return out


def show(name: str, o: dict) -> None:
    e = o["events"]
    print(f"\n================ {name}: panel last {o['panel_last']}, first held {o['first_held']}, {o['funds']} funds, band {o['band_width']}")
    print(f"cuts {e['cuts']} on {e['funds_with_a_cut']} funds, {e['per_year']} a year, last known {e['last_cut_known']}; by year {e['by_year']}")
    print("by fund", e["by_fund"])
    print("descriptive:", json.dumps(o["descriptive"], indent=1))
    for title, blk in (("VARIANTS (plain band)", o["variants"]), ("EX-DATE DATING (secondary)", {a: b for a, b in o["secondary_ex_date_dating"].items() if isinstance(b, dict)}),
                       ("GROSS CEILING", {a: b for a, b in o["check_gross_ceiling"].items() if isinstance(b, dict)}),
                       ("TOTAL RETURNS", o.get("check_total_returns", {}))):
        print(f"\n{title}")
        for key, r in blk.items():
            d = r.get("diff_vs_unchanged", {})
            print(f"{key:10s} SR {r['sharpe']:6.3f} ret {r['ann_ret_pct']:6.3f} vol {r['vol_pct']:6.3f} dd {r['max_dd_pct']:7.2f} turn {r['turnover_per_year']:6.2f} "
                  f"halves {r['halves']['early']}/{r['halves']['late']} eras " + " ".join(f"{v['sharpe']}" for v in r["eras"].values())
                  + (f" | diff {d['ann_ret_bp']:+.2f}bp/yr t {d['t']} dSR {d['sharpe_diff']:+.4f} turn {d['turnover_change']:+.2%} eras {list(d['by_era_ann_ret_bp'].values())} halves {d['halves_ann_ret_bp']}" if d else "")
                  + (f" | matched b={r['turnover_matched']['band_width_used']} SR {r['turnover_matched']['sharpe']}" if "turnover_matched" in r else ""))
    if "placebo" in o:
        print("\nplacebo:", json.dumps(o["placebo"], indent=1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="a data/cef directory holding cef_prices, cef_nav, cef_distributions")
    ap.add_argument("--families", type=Path, default=None, help="a data/cef_families directory (C4); omitted = the core book only")
    a = ap.parse_args(argv)
    from scripts.cef import band_frontier as bf
    from scripts.cef import spec as cs
    dc = card_module()
    out = {"written": "2026-11-18", "event_source_last_date": None}

    # ------------------------------------------------------------------ CORE
    src = (a.data / "cef_prices.parquet", a.data / "cef_nav.parquet")
    T, R = bf.build_targets(source=src)
    p = bf.build_panel(source=src)
    pmap, minfo = permno_map(list(T.columns), p["px"])
    if minfo["unmapped"]:
        raise RuntimeError(f"core funds with no CRSP permno: {minfo['unmapped']}")
    out["event_source_last_date"] = minfo["crsp_last"]
    ev = events_for(dc, pmap, T.index, list(T.columns))
    old = bf.DATA_DIR
    bf.DATA_DIR = a.data                    # the module's documented switch: total_returns reads the same checkout's panels
    try:
        Rt = bf.total_returns(R)
    finally:
        bf.DATA_DIR = old
    core = run_book("CORE", T, R, p, ev, CORE_ERAS, bf.BAND_WIDTH, cs.MAX_GROSS_STRESS, Rt)
    core["mapping"] = minfo
    # the desk's own distributions panel: what it carries, and how many of the CRSP cuts it shows at the same ex-date
    dd = pd.read_parquet(a.data / "cef_distributions.parquet")
    dd = dd[dd.ticker.isin(T.columns) & (dd.amount > 0)].sort_values(["ticker", "ex_date"])
    dd["chg"] = dd.amount / dd.groupby("ticker").amount.shift(1) - 1
    cc = ev[ev.cut & (ev.k >= T.index.get_loc(pd.Timestamp(core["first_held"])))]
    mm = cc.merge(dd, left_on=["tk", "disexdt"], right_on=["ticker", "ex_date"], how="left", suffixes=("", "_desk"))
    core["desk_distribution_panel"] = {
        "columns": list(pd.read_parquet(a.data / "cef_distributions.parquet").columns), "last_ex_date": str(dd.ex_date.max().date()),
        "has_declaration_date": False,
        "crsp_cuts_with_the_same_ex_date_in_the_desk_panel": int(mm.ex_date.notna().sum()),
        "of_which_the_desk_panel_also_shows_a_fall_of_5pct": int((mm.chg_desk <= -0.05 + 1e-9).sum()),
        "desk_panel_falls_of_5pct_after_the_crsp_panel_ends": int(((dd.chg <= -0.05) & (dd.ex_date > minfo["crsp_last"])).sum()),
        "note": "the last row counts raw 5% falls in the desk panel, with no stable-base rule, so it includes cuts back from specials"}
    out["CORE"] = core
    show("CORE", core)

    # ------------------------------------------------------------------ C4
    if a.families is not None:
        from scripts.cef import c4_families as c4
        spec = json.loads((REPO / "ops" / "specs" / "c4_families.frozen.json").read_text())
        f = spec["frozen"]
        same = {"z_window": cs.Z_WINDOW, "vol_target_annual": cs.VOL_TARGET, "band_width": cs.BAND_WIDTH, "min_adv_usd": cs.MIN_ADV_USD, "min_names": cs.MIN_NAMES}
        diff = {key: (f[key], v) for key, v in same.items() if float(f[key]) != float(v)}
        if diff:
            raise RuntimeError(f"the C4 spec differs from the core's on {diff}; the harness's module constants would be wrong for it")
        if not (f["nav_repeat_mask"] and f["zero_volume_mask"]):
            raise RuntimeError("the C4 spec no longer sets both masks; declared_mask('M1M2') would not be its book")
        oldd, olds = c4.FAM_DIR, c4.FAM_SRC
        c4.FAM_DIR, c4.FAM_SRC = a.families, (a.families / "cef_prices.parquet", a.families / "cef_nav.parquet")
        try:
            have = set(bf.build_panel(universe=f["universe"], source=c4.FAM_SRC)["px"].columns)
            U = [t for t in f["universe"] if t in have]
            mask = c4.declared_mask(U, "M1M2")
            T4, R4 = bf.build_targets(universe=U, source=c4.FAM_SRC, mask=mask)
            p4 = bf.build_panel(universe=U, source=c4.FAM_SRC, mask=mask)
            blend_err, T4b = None, None
            try:
                from scripts.cef import c4_paper_benchmark as pb
                T4b = pb.spec_targets(a.families, T4, spec).reindex(columns=U)
                if T4b.isna().any().any() or not T4b.index.equals(T4.index):
                    raise RuntimeError("spec_targets returned a frame that does not cover the z book's index and funds")
            except Exception as e:                           # said aloud in results.json and the card; the z book still runs
                blend_err = f"{type(e).__name__}: {e}"[:400]
                T4b = None
        finally:
            c4.FAM_DIR, c4.FAM_SRC = oldd, olds
        try:
            R4t = bf.total_returns(R4, actions=a.families / "cef_actions.parquet", prices=a.families / "cef_prices.parquet", split_rulings=c4.SPLIT_RULINGS)
            tr_err = None
        except Exception as e:                               # said aloud, as above
            R4t, tr_err = None, f"{type(e).__name__}: {e}"[:400]
        dm = pd.read_csv(a.families / "crsp_permno_map.csv").dropna(subset=["current_permno"]).set_index("ticker").current_permno.astype(int).to_dict()
        pmap4, minfo4 = permno_map(U, p4["px"], confirmed=dm)
        if minfo4["unmapped"]:
            raise RuntimeError(f"C4 funds with no CRSP permno: {minfo4['unmapped']}")
        ev4 = events_for(dc, pmap4, T4.index, U)
        z4 = run_book("C4 z book (trial 52)", T4, R4, p4, ev4, C4_ERAS, float(f["band_width"]), float(f["max_gross_stress"]), R4t)
        z4["mapping"], z4["total_returns_error"] = minfo4, tr_err
        z4["universe_without_rows"] = sorted(set(f["universe"]) - have)
        out["C4_Z"] = z4
        show("C4 z book (trial 52)", z4)
        out["C4_BLEND_error"] = blend_err
        if T4b is not None:
            b4 = run_book("C4 blend (live spec, trial 54)", T4b, R4, p4, ev4, C4_ERAS, float(f["band_width"]), float(f["max_gross_stress"]), R4t)
            out["C4_BLEND"] = b4
            show("C4 blend (live spec, trial 54)", b4)
        else:
            print("\nC4 blend not run:", blend_err)
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
