"""Checks on the group cap that were NOT pre-specified (written 2026-11-16 after explore.py's tables were read).

    python3 results/ideas/core_group_cap/checks.py --data <a checkout's data/cef>

WHY: explore.py showed two things its docstring did not foresee. (1) The muni group has no
target at all before 2020, so the caps derived from its own pre-2020 history (MED, P75, and
the expanding XP75) are ZERO: they remove the group, they do not soften it. (2) The flat 25%
cap binds mostly on the multi-sector and high-yield groups, not on the muni group that
motivated it. So, labelled as after-the-fact:
  MUNI25    the 25% cap on the muni group ONLY (the motivation taken literally), PRORATA and
            NEUTRAL.
  FROM2020  every headline variant scored from 2020-01-01 only, the period in which the muni
            group is in the book, with the 34-session windows on that period.
  WORST     when each book's worst 34-session windows fall.
  LAST12    the NAV part over the panel's sessions from 2026-09-29 (the start of the live
            record), per variant. The panel ends 2026-10-14, before most of the live loss.
  SCALEDM   the turnover-matched rows in explore.py narrow the band for a book whose gross the
            cap has cut. A plain size cut gets the same favour, so: the UNCAPPED targets times
            the F25 books' scale (mean gross ratio from results.json), band width moved by
            the same bisection until turnover equals the uncapped book's.
Writes checks.json beside this file.
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
spec = importlib.util.spec_from_file_location("gc_explore", HERE / "explore.py")
ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
assert pd.get_option("compute.use_numexpr") is False


def muni_win(x: pd.Series, mult: float) -> dict:
    """ex.win, except that a book which never holds the muni group has no window to rank (its NAV part is identically zero)."""
    if not (x != 0).any():
        return {"worst": 0.0, "never_held": True}
    return ex.win(x, mult)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--data", type=Path, required=True)
    a = ap.parse_args(argv)
    from scripts.cef import band_frontier as bf
    from scripts.cef.spec import SIZING_MULTIPLIER as M
    from scripts.research import harness
    src = (a.data / "cef_prices.parquet", a.data / "cef_nav.parquet")
    T, R = bf.build_targets(source=src)
    p = bf.build_panel(source=src)
    grp = pd.read_csv(a.data / "cef_universe.csv").set_index("ticker")["grp"].reindex(T.columns)
    navret = p["nav"].pct_change(fill_method=None).where(lambda x: x.abs() < 0.5).reindex(T.index)[T.columns]
    H0 = bf.band(T, bf.BAND_WIDTH)
    first = harness.held(H0).abs().sum(axis=1).gt(0).idxmax()
    t0 = float(H0.diff().abs().sum(axis=1).loc[first:].mean() * 252)

    muni_only = ex.cap_frame(T, grp, "F25").copy()
    muni_only[[c for c in muni_only.columns if c != "muni"]] = np.inf
    books = {"UNCAPPED": T}
    for kind in ("F25", "P75", "MED"):
        for how in ("PRORATA", "NEUTRAL"):
            books[f"{kind}/{how}"] = ex.apply_cap(T, grp, ex.cap_frame(T, grp, kind), how)
    books["MUNI25/PRORATA"] = ex.apply_cap(T, grp, muni_only, "PRORATA")
    books["MUNI25/NEUTRAL"] = ex.apply_cap(T, grp, muni_only, "NEUTRAL")
    out, base = {}, None
    for name, Tc in books.items():
        H = bf.band(Tc, bf.BAND_WIDTH)
        pnl = harness.evaluate(H, R)["pnl"]
        W = harness.held(H)
        nav = (W * navret.fillna(0.0)).sum(axis=1)
        muni_cols = list(grp[grp == "muni"].index)
        nav_muni = (W[muni_cols] * navret[muni_cols].fillna(0.0)).sum(axis=1)
        if base is None:
            base = pnl
        r = {}
        for tag, lo in (("from_first_held", first), ("from_2020", pd.Timestamp("2020-01-01"))):
            s, n = pnl.loc[lo:], nav.loc[lo:]
            d = (pnl - base).loc[lo:]
            r[tag] = {"book": ex.st(s), "nav_part": ex.st(n), "muni_nav_part": ex.st(nav_muni.loc[lo:]),
                      "win34_book": ex.win(s, M), "win34_nav": ex.win(n, M), "win34_muni_nav": muni_win(nav_muni.loc[lo:], M),
                      "turnover_per_year": round(float(H.diff().abs().sum(axis=1).loc[lo:].mean() * 252), 1),
                      "mean_gross": round(float(H.abs().sum(axis=1).loc[lo:].mean()), 3),
                      "diff_vs_uncapped": None if name == "UNCAPPED" else
                      {"ann_ret_pct": round(100 * d.mean() * 252, 2), "t": round(float(d.mean() / d.std() * len(d) ** 0.5), 2)}}
        w = (nav.loc[first:].rolling(ex.WINDOW).sum() * M * 100).dropna()
        r["nav_windows_below_minus3pct_share"] = round(float((w < -3.0).mean()), 4)
        r["nav_windows_below_minus2pct_share"] = round(float((w < -2.0).mean()), 4)
        r["last12_nav_part_pct_at_mult"] = round(float(nav.loc["2026-09-29":].sum() * M * 100), 2)
        r["last12_book_pct_at_mult"] = round(float(pnl.loc["2026-09-29":].sum() * M * 100), 2)
        r["turnover_vs_uncapped"] = round(r["from_first_held"]["turnover_per_year"] / t0 - 1, 3)
        out[name] = r
    res = json.loads((HERE / "results.json").read_text())
    S = slice(first, None)
    for name in ("F25/PRORATA", "F25/NEUTRAL"):
        k = res["variants"][name]["mean_gross"] / res["variants"]["UNCAPPED"]["mean_gross"]
        lo, hi = bf.BAND_WIDTH / 4, bf.BAND_WIDTH * 4
        for _ in range(40):
            b = (lo + hi) / 2
            H = bf.band(T * k, b)
            t = float(H.diff().abs().sum(axis=1).fillna(0.0).loc[S].mean() * 252)
            if abs(t / t0 - 1) < ex.MATCH_TOL:
                break
            lo, hi = (b, hi) if t > t0 else (lo, b)
        else:
            raise RuntimeError("no band width matches")
        pnl = harness.evaluate(H, R)["pnl"].loc[S]
        nav = (harness.held(H) * navret.fillna(0.0)).sum(axis=1).loc[S]
        out[f"SCALED_MATCHED as {name}"] = {"scale": round(k, 3), "band_width_used": round(b, 5), "book": ex.st(pnl),
                                             "win34_book": ex.win(pnl, M), "win34_nav": ex.win(nav, M), "turnover_per_year": round(t, 1),
                                             "matched_capped_sharpe": res["matched"][name]["book"]["sharpe"]}
        print(f"SCALED_MATCHED as {name}", json.dumps(out[f"SCALED_MATCHED as {name}"]))
    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    for tag in ("from_first_held", "from_2020"):
        print(f"\n{tag}")
        for k, r in out.items():
            if tag not in r:
                continue
            x = r[tag]; d = x["diff_vs_uncapped"]
            print(f"{k:16s} SR {x['book']['sharpe']:5.2f} ret {x['book']['ann_ret_pct']:5.2f} vol {x['book']['vol_pct']:5.2f} dd {x['book']['max_dd_pct']:6.2f} "
                  f"| w34 book {x['win34_book']['worst']:6.2f} ({x['win34_book']['worst_date']}) nav {x['win34_nav']['worst']:6.2f} ({x['win34_nav']['worst_date']}) p1 {x['win34_nav']['p1']:5.2f} "
                  f"muni-nav {x['win34_muni_nav']['worst']:6.2f} | navvol {x['nav_part']['vol_pct']:4.2f} | turn {x['turnover_per_year']:5.1f} gross {x['mean_gross']:.2f} "
                  f"| diff {'' if d is None else str(d['ann_ret_pct']) + ' t ' + str(d['t'])}")
    print()
    for k, r in out.items():
        if "last12_nav_part_pct_at_mult" not in r:
            continue
        print(f"{k:16s} nav windows < -3%: {r['nav_windows_below_minus3pct_share']:.4f}  < -2%: {r['nav_windows_below_minus2pct_share']:.4f}  last12 nav {r['last12_nav_part_pct_at_mult']:6.2f} book {r['last12_book_pct_at_mult']:6.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
