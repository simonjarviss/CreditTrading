"""Explore: short-term reversal within industry on SMALLER US stocks (ranked 1,501 to 4,000).

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_equities.py --top 4500
    python3 results/ideas/st_reversal_small/explore.py

WHY: the team lead asked on 2026-11-15 for niche ideas in undersized markets that a small
book can exploit. `st_reversal_wide` (results/ideas/2026-11-10_st_reversal_wide.md) is the
wage for providing liquidity, earned on the 1,500 largest stocks: gross 0.96, but 0.67 since
2013. Liquidity is scarcer below the top 1,500 and large funds cannot work there, so the
wage should be higher. Whether it is, with the same one-session gap that keeps bid-ask
bounce out, is the question.

FIXED BEFORE ANY RETURN WAS READ (2026-11-15). Nothing on this panel had been looked at
except its row count (27.1M rows, 4,151 names a day).
  RULE      `st_reversal_wide`'s, imported and not edited: signal at t = minus the 5-session
            return ending at t, less the 2-digit-SIC industry mean (at least 5 names);
            weights = signal / sum of absolute values; shift(2).
  UNIVERSE  the only change: previous month-end market-value rank 1,501 to 4,000 (the wide
            book stops at 1,500), price >= $5 at t (the wide book's floor), and 21-session
            average dollar volume >= $500,000 at t (the desk's event-test floor; the wide
            book needed none).
  THREE BOOKS from the same weights:
    BOTH      long losers and short winners, unit gross: comparable with the wide book.
    LONG LEG  the positive weights only, rescaled to 100% long, against IWM short 100%.
              This is the version that needs no borrow in small stocks.
    SHORT LEG the negative weights only against IWM long, for information.
  EXPECTED: BOTH above the wide book's 0.96; the long leg positive.
  CONTROLS  the signal 21 sessions stale (BOTH and LONG LEG); the wide book's own result is
            the comparison.
  DESCRIPTIVE ONLY: halves and eras; rank 1,501-2,500 against 2,501-4,000; capacity as each
            position's share of its own 21-session dollar volume at $250k, $1M and $5M.

THE PANEL holds ranks to 4,500 so a stock slipping below 4,000 keeps its returns while held.
A held stock with no row has stopped trading (CRSP puts the delisting return on its last
row): its return is zero afterwards, and those name-days are counted.
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

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("wide", HERE.parent / "st_reversal_wide" / "explore.py")
wide = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(wide)
RES = Path.home() / "quantt_research"
PANEL = RES / "crsp_top4500_daily.parquet"
RANK_LO, RANK_HI, MIN_PRICE, MIN_ADV, WINDOW = 1500, 4000, 5.0, 500_000.0, 5


def leg(H: pd.DataFrame, sign: int, iwm: pd.Series) -> pd.DataFrame:
    """One side of H rescaled to 100%, with IWM the same size the other way."""
    side = H.clip(lower=0.0) if sign > 0 else H.clip(upper=0.0)
    tot = side.abs().sum(axis=1)
    side = side.div(tot.where(tot > 1e-12), axis=0).fillna(0.0)
    side["IWM"] = -side.sum(axis=1)
    return side


def main() -> int:
    df = pd.read_parquet(PANEL, columns=["permno", "date", "ret", "prc", "cap_rank", "siccd", "dollar_volume"])
    df["date"] = pd.to_datetime(df["date"])
    last = df["date"].max().date()
    piv = lambda c, t="float32": df.pivot(index="date", columns="permno", values=c).astype(t)  # noqa: E731
    ret = piv("ret", "float64")
    prc, rank, dv = piv("prc"), piv("cap_rank"), piv("dollar_volume", "float64")
    ind = df.assign(i=df["siccd"] // 100).pivot(index="date", columns="permno", values="i")
    del df
    yf = pd.read_parquet(RES / "yf_daily.parquet")
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"]
    adv = dv.rolling(21, min_periods=10).mean()
    # ALIGNMENT: every input to the signal at t is dated <= t (5-session return ending at t,
    # previous month-end rank, t's close, volume through t).
    r5 = ret.rolling(WINDOW, min_periods=WINDOW).sum()
    band = (rank > RANK_LO) & (rank <= RANK_HI)
    ok = band & (prc >= MIN_PRICE) & (adv >= MIN_ADV) & r5.notna()
    sig = (-r5).where(ok)
    H = wide.weights(sig, ind)
    start = iwm.dropna().index.min()
    R = ret.fillna(0.0)
    out = {"panel_last_date": str(last), "fixed": {"rank": [RANK_LO + 1, RANK_HI], "min_price": MIN_PRICE, "min_adv": MIN_ADV, "window": WINDOW},
           "names_per_day_mean": float((H != 0).sum(axis=1).mean()),
           "held_name_days_with_no_row": int(((H.shift(harness.EXEC_LAG).fillna(0.0) != 0) & ret.isna()).sum().sum())}
    res_h = harness.evaluate(H, R)
    out["turnover_per_year"] = float(res_h["turn"])
    series = {"both": res_h["pnl"].iloc[WINDOW + harness.EXEC_LAG:]}
    Hs = wide.weights(sig.shift(21), ind.shift(21))
    stale = {"both": harness.evaluate(Hs, R)["pnl"]}
    Ri = R.loc[start:].copy(); Ri["IWM"] = iwm.reindex(Ri.index)
    if Ri["IWM"].isna().any():
        raise ValueError("IWM has no return on a CRSP session inside its own range")
    for name, sign in (("long_leg", 1), ("short_leg", -1)):
        series[name] = harness.evaluate(leg(H.loc[start:], sign, iwm), Ri)["pnl"].iloc[WINDOW + harness.EXEC_LAG:]
        stale[name] = harness.evaluate(leg(Hs.loc[start:], sign, iwm), Ri)["pnl"]
    for name, pnl in series.items():
        ctl = {"signal 21 sessions stale": stale[name].reindex(pnl.index)}
        res = explore.summarise(pnl, controls=ctl)
        out[name] = res
        d = HERE / name; d.mkdir(exist_ok=True)
        explore.write(d, res, pnl, controls=ctl, title=f"Reversal within industry, stocks ranked 1,501-4,000, {name}; shift(2), gross; to {last}")
        print(f"\n== {name}")
        print(explore.table(res))
    for label, lo, hi in (("rank 1,501-2,500", 1500, 2500), ("rank 2,501-4,000", 2500, 4000)):
        s2 = sig.where((rank > lo) & (rank <= hi))
        p = harness.evaluate(wide.weights(s2, ind), R)["pnl"].iloc[WINDOW + harness.EXEC_LAG:]
        out[label] = explore.stats(p)
        print(f"  {label}: SR {out[label]['sharpe']:.2f} t {out[label]['t']:.2f} | from 2013: {explore.stats(p.loc['2013-01-01':])['sharpe']:.2f}")
    share = (H.abs() / adv).replace([np.inf, -np.inf], np.nan).loc["2024-01-01":]
    nz = share.where(H.loc["2024-01-01":] != 0).stack()
    out["capacity_2024_on_both"] = {f"position_pct_of_adv_at_{s:,}": {"median": float(nz.median() * s * 100), "p95": float(nz.quantile(0.95) * s * 100)}
                                    for s in (250_000, 1_000_000, 5_000_000)}
    Hl = leg(H, 1, iwm).drop(columns="IWM")
    nzl = (Hl / adv).replace([np.inf, -np.inf], np.nan).loc["2024-01-01":].where(Hl.loc["2024-01-01":] != 0).stack()
    out["capacity_2024_on_long_leg"] = {f"position_pct_of_adv_at_{s:,}": {"median": float(nzl.median() * s * 100), "p95": float(nzl.quantile(0.95) * s * 100)}
                                        for s in (250_000, 1_000_000, 5_000_000)}
    out["corr_long_short_legs"] = float(pd.concat(series, axis=1).corr().loc["long_leg", "short_leg"])
    print("\nnames a day", round(out["names_per_day_mean"]), "| turnover/yr", round(out["turnover_per_year"], 1), "| held name-days with no row", out["held_name_days_with_no_row"])
    print("capacity both:", out["capacity_2024_on_both"]); print("capacity long leg:", out["capacity_2024_on_long_leg"])
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
