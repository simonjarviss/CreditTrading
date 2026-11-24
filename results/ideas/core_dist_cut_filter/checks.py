"""Checks on core_dist_cut_filter, WRITTEN AFTER explore.py's RETURNS WERE READ (2026-11-18). Nothing here is pre-specified.

    python3 results/ideas/core_dist_cut_filter/checks.py --data <a checkout's data/cef> --families <its data/cef_families>

WHY: explore.py found that both fixed rules LOWER the return of both books, although the C4
funds do keep falling after a cut. Three questions follow, and each is answered with the same
functions explore.py used (imported, not copied):

  A  WHERE THE COST COMES FROM. The rule applied to three subsets of the cuts in turn, by the
     unchanged book's position decided at K-1: short, long, flat. NNL forbids covering a short,
     and FLAT closes one; if the cost sits in the "short" subset, the rule as written was the
     wrong shape, not the idea.
  B  THE NARROWER RULE THAT QUESTION POINTS TO, shown once and labelled as chosen after the
     fact: LONGCAP, the fund's target may not rise above max(position at K-1, 0). A short may
     be covered to flat; no long may be opened or added to. With the RAND placebo (200 draws,
     the same seed). This is an extra look at the same data and is counted as one.
  C  DO THE DESK'S OWN FUNDS SHOW THE CARD'S EFFECT? The card's per-event figure (fund's
     compounded CRSP total return over K+2 .. K+1+h less the equal-weighted eligible CEF
     market, price >= $2 and 21-session dollar volume >= $500,000 through K-1) recomputed for
     the cuts of the core 13 and of the C4 74 only, every such cut since 2000. explore.py's
     own version is on price returns against the book's universe; this one is the card's
     method to the letter, so the two can be compared with the card's -85bp and -137bp.

Writes checks.json (aggregates only) beside this file.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
_spec = importlib.util.spec_from_file_location("core_dist_cut_filter_explore", HERE / "explore.py")
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)
assert pd.get_option("compute.use_numexpr") is False


def longcap(T: pd.DataFrame, Href: pd.DataFrame, k, j, h: int) -> pd.DataFrame:
    """explore.apply_rule's NNL with the cap floored at zero: a short may be covered, no long opened or added to."""
    return ex.apply_rule(T, Href.clip(lower=0.0), k, j, h, "NNL")


def book_checks(T, R, ev, band_w: float) -> dict:
    from scripts.cef import band_frontier as bf
    from scripts.research import harness
    idx = T.index
    H0 = bf.band(T, band_w)
    first = harness.held(H0).abs().sum(axis=1).gt(0).idxmax()
    f0 = idx.get_loc(first)
    S = slice(first, None)
    cuts = ev[ev.cut & (ev.k >= f0)].reset_index(drop=True)
    k, j = cuts.k.to_numpy(), cuts.j.to_numpy()
    e0 = harness.evaluate(H0, R)
    base, turn0 = e0["pnl"].loc[S], float(e0["turn_series"].loc[S].mean() * 252)
    sr0 = base.mean() / base.std() * 252 ** 0.5

    def diff(Tc) -> dict:
        e = harness.evaluate(bf.band(Tc, band_w), R)
        pn = e["pnl"].loc[S]
        d = pn - base
        return {"ann_ret_bp": round(float(1e4 * d.mean() * 252), 2), "t": round(float(d.mean() / d.std() * len(d) ** 0.5), 2) if d.std() > 0 else None,
                "sharpe_diff": round(float(pn.mean() / pn.std() * 252 ** 0.5 - sr0), 4),
                "turnover_change": round(float(e["turn_series"].loc[S].mean() * 252 / turn0 - 1), 4)}

    pos = H0.to_numpy()[k - 1, j]
    out = {"A_by_position_at_K-1": {}, "B_longcap": {}}
    for lab, m in (("short", pos < 0), ("long", pos > 0), ("flat", pos == 0)):
        out["A_by_position_at_K-1"][lab] = {"events": int(m.sum()),
                                            **{f"{kind}/{h}": diff(ex.apply_rule(T, H0, k[m], j[m], h, kind)) for kind in ex.KINDS for h in ex.HOLDS}}
    rng = np.random.default_rng(ex.SEED)
    need = cuts.groupby("j").size()
    draws = []
    for _ in range(ex.N_PLACEBO):
        kr, jl = [], []
        for jj, m in need.items():
            kr += list(rng.choice(np.arange(f0, int(k.max()) + 1), size=m, replace=False))
            jl += [jj] * m
        draws.append((np.array(kr), np.array(jl)))
    for h in ex.HOLDS:
        real = diff(longcap(T, H0, k, j, h))
        P = pd.DataFrame([diff(longcap(T, H0, kk, jj, h)) for kk, jj in draws])
        real["placebo_RAND"] = {c: {"mean": round(float(P[c].mean()), 4), "p5": round(float(P[c].quantile(0.05)), 4), "p95": round(float(P[c].quantile(0.95)), 4),
                                    "share_at_or_above_real": round(float((P[c] >= real[c]).mean()), 3)} for c in ("ann_ret_bp", "sharpe_diff")}
        pn = harness.evaluate(bf.band(longcap(T, H0, k, j, h), band_w), R)["pnl"].loc[S]
        real["book"] = ex.st(pn)
        out["B_longcap"][str(h)] = real
    return out


def card_method(dc, permnos: dict) -> dict:
    """The card's per-event buy-and-hold, fund less the eligible CEF market, for the given funds' cuts only."""
    df = pd.read_parquet(dc.PANEL)
    df["date"] = pd.to_datetime(df["date"])
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc")
    dv = df.pivot(index="date", columns="permno", values="dollar_volume")
    idx, cols = ret.index, ret.columns
    T = len(idx)
    adv = dv.rolling(21, min_periods=10).mean()
    elig = ((prc >= dc.MIN_PRICE) & (adv >= dc.MIN_ADV)).shift(1, fill_value=False)      # through s-1, as the card
    mk = ret.where(elig).mean(axis=1).fillna(0.0).to_numpy()
    Rn, eln, has = ret.fillna(0.0).to_numpy(), elig.to_numpy(), ret.notna().to_numpy()
    col_of = {p: i for i, p in enumerate(cols)}
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        g, _ = dc.declarations()
    g = g[g.permno.isin(cols) & g.decl.notna()].copy()
    g["k"] = idx.searchsorted(g.decl.to_numpy(), side="left") + 1
    g = g[(g.k + 2 < T) & (g.k >= 31)].copy()
    assert (idx[g.k.to_numpy()] > g.decl.to_numpy()).all()
    g["j"] = g.permno.map(col_of)
    g["elig"] = eln[g.k.to_numpy(), g.j.to_numpy()] & has[g.k.to_numpy(), g.j.to_numpy()]
    g["ym"] = pd.Series(idx[g.k.to_numpy()], index=g.index).dt.to_period("M").astype(str)
    cuts = g[g.event & (g.chg < 0) & g.elig]
    out = {"all_crsp_cefs_eligible_cuts": int(len(cuts))}
    for lab, pm in permnos.items():
        c = cuts[cuts.permno.isin(pm)]
        o = {"events": int(len(c)), "funds": int(c.permno.nunique())}
        for h in ex.HOLDS:
            v = [np.prod(1 + Rn[kk + 2: kk + 2 + h, jj]) - np.prod(1 + mk[kk + 2: kk + 2 + h]) if kk + 2 + h <= T else np.nan
                 for kk, jj in zip(c.k.to_numpy(), c.j.to_numpy())]
            o[f"h{h}_bp"] = ex.clustered(1e4 * np.array(v), c.ym.to_numpy())
        out[lab] = o
    # the card's own headline, as a check that this function reproduces it
    for h in ex.HOLDS:
        v = [np.prod(1 + Rn[kk + 2: kk + 2 + h, jj]) - np.prod(1 + mk[kk + 2: kk + 2 + h]) if kk + 2 + h <= T else np.nan
             for kk, jj in zip(cuts.k.to_numpy(), cuts.j.to_numpy())]
        out[f"all_h{h}_bp"] = ex.clustered(1e4 * np.array(v), cuts.ym.to_numpy())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--families", type=Path, required=True)
    a = ap.parse_args(argv)
    from scripts.cef import band_frontier as bf
    from scripts.cef import c4_families as c4
    dc = ex.card_module()
    out = {"written": "2026-11-18", "status": "written after explore.py's returns were read; nothing here is pre-specified"}
    src = (a.data / "cef_prices.parquet", a.data / "cef_nav.parquet")
    T, R = bf.build_targets(source=src)
    p = bf.build_panel(source=src)
    pmap, _ = ex.permno_map(list(T.columns), p["px"])
    out["CORE"] = book_checks(T, R, ex.events_for(dc, pmap, T.index, list(T.columns)), bf.BAND_WIDTH)

    f = json.loads((REPO / "ops" / "specs" / "c4_families.frozen.json").read_text())["frozen"]
    oldd, olds = c4.FAM_DIR, c4.FAM_SRC
    c4.FAM_DIR, c4.FAM_SRC = a.families, (a.families / "cef_prices.parquet", a.families / "cef_nav.parquet")
    try:
        have = set(bf.build_panel(universe=f["universe"], source=c4.FAM_SRC)["px"].columns)
        U = [t for t in f["universe"] if t in have]
        mask = c4.declared_mask(U, "M1M2")
        T4, R4 = bf.build_targets(universe=U, source=c4.FAM_SRC, mask=mask)
        p4 = bf.build_panel(universe=U, source=c4.FAM_SRC, mask=mask)
    finally:
        c4.FAM_DIR, c4.FAM_SRC = oldd, olds
    dm = pd.read_csv(a.families / "crsp_permno_map.csv").dropna(subset=["current_permno"]).set_index("ticker").current_permno.astype(int).to_dict()
    pmap4, _ = ex.permno_map(U, p4["px"], confirmed=dm)
    out["C4_Z"] = book_checks(T4, R4, ex.events_for(dc, pmap4, T4.index, U), float(f["band_width"]))
    out["C_card_method_on_the_desks_funds"] = card_method(dc, {"core_13": list(pmap.values()), "c4_74": list(pmap4.values())})
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
