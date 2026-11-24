"""The core account at its multiplier, built EXACTLY as each implementation would trade it (CEF trial 53, DRAFT).

    python3 results/cef/prereg_voltarget/impl_core.py --scratch SCRATCH [--m 1.24]
        -> impl_core_2026-10-30.json, impl_core_output_2026-10-30.txt (this folder)

ZERO TRIALS; fit window only. The live panels are copied with a parquet filter at 2022-12-30 into
SCRATCH/prereg_voltarget/fitcut_cef (no later row is loaded) and band_frontier.DATA_DIR is pointed
there (the C5 frozen-copy switch). Nothing under data/ is written. No new backtester: every book is
band_frontier.build_targets -> band_gross_capped -> evaluate, the canonical path.

WHY THIS EXISTS. The multipliers were derived under the house rescaling model (m x the decided unit
book, one uniform cap per account, the cap's feedback into the next day's band ignored). The draft
chooses implementation B (`sizing_multiplier`), and prices A (raise `vol_target_annual`) beside it.
This measures, at the one derived value and nowhere else (no sweep), how far each implementation's
traded book is from the model the value was derived on:

  unit   the deployed book today: build_targets at the spec's vol target, band 4.8%, cap 1.80
  model  m x unit, capped per row at cap / (m x gross)            (what derive.py and risk.py assume)
  B      m x band_gross_capped(T, band, cap / m): the band and the cap act on the unit book, as the
         sleeve would under `sizing_multiplier` (held / m against the target; _cap_gross at cap / m)
  A      band_gross_capped(T at vol target 0.06 x m, band, cap): the sleeve with vol_target_annual
         raised (the band is then 4.8% of a book m times larger, and the vol-scalar clip moves)

The declaration (declared_2026-10-30.json) chose B on mechanism before this ran; A decides nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from scripts.cef import band_frontier as bf  # noqa: E402
from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS, SPEC_ID, VOL_TARGET  # noqa: E402
from scripts.cef.portfolio_baseline import max_drawdown  # noqa: E402

STAMP = "2026-10-30"
FIT_END = pd.Timestamp("2022-12-30")
W1 = pd.Timestamp("2013-06-25")
ERAS = (("2013-06..2017", "2013-06-25", "2017-12-31"), ("2018..2022", "2018-01-01", "2022-12-30"))


def cut_panels(dst: Path) -> dict:
    dst.mkdir(parents=True, exist_ok=True)
    info = {}
    for name, col in (("cef_prices", "date"), ("cef_nav", "date"), ("cef_distributions", "ex_date"),
                      ("cef_splits", "ex_date")):
        d = pd.read_parquet(REPO / "data" / "cef" / f"{name}.parquet", filters=[(col, "<=", FIT_END)])
        if len(d) and pd.to_datetime(d[col]).max() > FIT_END:
            raise AssertionError(f"{name}: the filter let a later row through")
        d.to_parquet(dst / f"{name}.parquet", index=False)
        info[name] = dict(rows=len(d), last=str(pd.to_datetime(d[col]).max().date()) if len(d) else None)
    return info


def line(H: pd.DataFrame, R: pd.DataFrame, cap_acct: float, ref: pd.Series | None = None) -> dict:
    res = bf.evaluate(H, R)
    pnl, turn = res["pnl"].loc[W1:], res["turn_series"].loc[W1:]
    if pnl.index.max() > FIT_END:
        raise AssertionError("holdout leak")
    ann, vol = pnl.mean() * 252, pnl.std() * np.sqrt(252)
    t = turn.mean() * 252
    g = H.abs().sum(axis=1).loc[W1:]
    out = dict(sr=ann / vol, ann=ann, vol=vol, mdd=max_drawdown(pnl)["mdd"], turn=t,
               net_pct={bp: (ann - t * bp * 1e-4) * 100 for bp in (5, 15, 30)},
               net_sr={bp: (ann - t * bp * 1e-4) / vol for bp in (5, 15, 30)},
               breakeven_bp=ann / t * 1e4, mean_gross=float(g.mean()),
               at_cap=float((g >= cap_acct - 1e-9).mean()),
               eras={lab: float(pnl.loc[a:b].mean() / pnl.loc[a:b].std() * np.sqrt(252)) for lab, a, b in ERAS})
    if ref is not None:
        out["corr_with_model"] = float(pnl.corr(ref.loc[W1:]))
        out["ann_minus_model_pct"] = float((pnl.mean() - ref.loc[W1:].mean()) * 252 * 100)
    return out, res["pnl"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--m", type=float, default=None,
                    help="the core's multiplier; required (the ruled value is 1.24)")
    ap.add_argument("--stamp", default=STAMP,
                    help="output stamp (2026-11-01: the approved x1.13 run writes its own files)")
    a = ap.parse_args()
    if a.m is None:
        raise SystemExit("--m is required: the multiplier is an input, never a default")
    dec = json.loads((HERE / "declared_2026-10-30.json").read_text())
    if not datetime.fromisoformat(dec["declared_utc"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
        raise AssertionError("the declaration is not older than this run")
    m, cap = float(a.m), float(MAX_GROSS_STRESS)
    say, out = [], dict(spec=SPEC_ID, m=m, band=BAND_WIDTH, cap=cap, vol_target=VOL_TARGET)

    def p(*x):
        s = " ".join(str(v) for v in x)
        print(s, flush=True)
        say.append(s)

    cut = a.scratch / "prereg_voltarget" / "fitcut_cef"
    out["cut"] = cut_panels(cut)
    p("fit-cut panels:", out["cut"])
    bf.DATA_DIR = cut
    T, R = bf.fit_only(*bf.build_targets())
    Rtr = bf.total_returns(R)
    H1 = bf.band_gross_capped(T, BAND_WIDTH, cap)
    # the unit book must be the series the multipliers were derived on
    ref = pd.read_parquet(a.scratch / "alloc" / "series" / "core_pnl.parquet")["pnl"]
    p1 = bf.evaluate(H1, Rtr)["pnl"]
    diff = float((p1.reindex(ref.index) - ref).abs().max())
    if diff > 1e-12:
        raise AssertionError(f"the unit book does not reproduce SCRATCH/alloc/series/core_pnl: {diff}")
    p(f"unit book reproduces the derivation's core series: max abs diff {diff:.1e}")
    G1 = H1.abs().sum(axis=1)
    f = np.minimum(1.0, cap / (m * G1).where(G1 > 0, np.inf))
    HM = H1.mul(m * f, axis=0)                                    # the model's held book
    HB = m * bf.band_gross_capped(T, BAND_WIDTH, cap / m)          # implementation B
    vt0 = bf.VOL_TARGET
    try:
        bf.VOL_TARGET = vt0 * m                                    # implementation A, in this process only
        TA, _ = bf.fit_only(*bf.build_targets())
    finally:
        bf.VOL_TARGET = vt0
    HA = bf.band_gross_capped(TA, BAND_WIDTH, cap)
    for b, RR in (("TR", Rtr), ("PR", R)):
        mod, mp = line(HM, RR, cap)
        rows = {"unit (today)": line(H1, RR, cap)[0], "model": mod,
                "B sizing_multiplier": line(HB, RR, cap, mp)[0], "A vol_target_annual": line(HA, RR, cap, mp)[0]}
        out[b] = rows
        p(f"\n{b} (W1 {W1.date()}..{FIT_END.date()}), core account, m = {m}")
        for k, v in rows.items():
            extra = (f" | corr with model {v['corr_with_model']:.4f}, ann - model {v['ann_minus_model_pct']:+.2f}%/yr"
                     if "corr_with_model" in v else "")
            p(f"  {k:22s} SR {v['sr']:.3f} ann {v['ann'] * 100:5.2f}% vol {v['vol'] * 100:4.2f}% maxDD {v['mdd'] * 100:5.2f}% "
              f"turn {v['turn']:5.1f}/yr mean gross {v['mean_gross']:.3f} at cap {v['at_cap']:.1%} | net SR "
              + " / ".join(f"{x:.3f}" for x in v["net_sr"].values()) + f" | breakeven {v['breakeven_bp']:.1f}bp | eras "
              + " / ".join(f"{x:.3f}" for x in v["eras"].values()) + extra)
    # ---- R1 on the fit path: how often a 12% drawdown episode occurs at m (model and B) ----------
    from scripts.cef.portfolio_baseline import HALVE_DD
    for lab, H in (("unit (today)", H1), ("model", HM), ("B sizing_multiplier", HB)):
        for b, RR in (("TR", Rtr), ("PR", R)):
            x = bf.evaluate(H, RR)["pnl"].loc[W1:]
            eq = (1 + x).cumprod()
            dd = 1 - eq / eq.cummax().clip(lower=1.0)
            hit = dd >= HALVE_DD
            starts = list(dd.index[hit & ~hit.shift(1, fill_value=False)])
            out.setdefault("halve_episodes", {})[f"{lab} {b}"] = [str(s.date()) for s in starts]
            p(f"  {lab:22s} {b}: sessions on which the drawdown first reaches {HALVE_DD:.0%} again: "
              f"{[str(s.date()) for s in starts]}")

    # ---- the RAMP: switching a held x1.0 book to B (the band then trades a name only once it is more
    # than band_width from target in unit terms, so the raise phases in). This copies
    # band_gross_capped's loop with a START STATE, and first proves that from zeros it IS that loop.
    from src.deploy.sleeves.cef_discount import _cap_gross

    def band_from(T_, b_, cap_, cur0, i0):
        A_, cur = T_.values, cur0.copy()
        Hh = np.zeros((len(A_) - i0, A_.shape[1]))
        for j, i in enumerate(range(i0, len(A_))):
            gap = A_[i] - cur
            mv = np.abs(gap) > b_
            cur = cur.copy()
            cur[mv] = A_[i][mv] - np.sign(gap[mv]) * b_
            w_, _ = _cap_gross(pd.Series(cur, index=T_.columns), cap_)
            cur = w_.values
            Hh[j] = cur
        return pd.DataFrame(Hh, index=T_.index[i0:], columns=T_.columns)

    chk = band_from(T, BAND_WIDTH, cap / m, np.zeros(T.shape[1]), 0)
    if float((chk.values - HB.values / m).__abs__().max()) > 1e-12:
        raise AssertionError("band_from from zeros does not reproduce band_gross_capped")
    ramp = []
    for y in range(2013, 2022):
        t0 = T.index[T.index <= f"{y}-12-31"][-1]
        i0 = T.index.get_loc(t0) + 1
        Hr = m * band_from(T, BAND_WIDTH, cap / m, H1.iloc[i0 - 1].values / m, i0)
        g_r, g_b = Hr.abs().sum(axis=1), HB.loc[Hr.index].abs().sum(axis=1)
        ratio = (g_r / g_b.where(g_b > 0)).dropna()
        n95 = int(np.argmax(ratio.values >= 0.95)) if (ratio.values >= 0.95).any() else None
        same = (Hr - HB.loc[Hr.index]).abs().max(axis=1) < 1e-9
        nconv = int(np.argmax(same.values)) if same.any() else None
        ramp.append(dict(switch=str(t0.date()), gross_ratio_day1=float(ratio.iloc[0]),
                         sessions_to_95pct_gross=n95, sessions_to_identical=nconv))
    out["ramp"] = ramp
    p("\nRAMP (a held x1.0 book switched to B at each year-end; gross relative to B's own path):")
    for r_ in ramp:
        p(f"  {r_['switch']}: day-1 gross {r_['gross_ratio_day1']:.3f} of B's; 95% after {r_['sessions_to_95pct_gross']} "
          f"sessions; identical to B after {r_['sessions_to_identical']}")
    n95s = [r_["sessions_to_95pct_gross"] for r_ in ramp if r_["sessions_to_95pct_gross"] is not None]
    p(f"  median sessions to 95% of B's gross: {float(np.median(n95s)) if n95s else None} (of {len(ramp)} switches)")
    (HERE / f"impl_core_{a.stamp}.json").write_text(json.dumps(out, indent=1, default=float))
    (HERE / f"impl_core_output_{a.stamp}.txt").write_text("\n".join(say) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
