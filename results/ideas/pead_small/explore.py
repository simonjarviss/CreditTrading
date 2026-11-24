"""Explore: earnings drift in SMALLER US stocks (ranked 1,501 to 4,000), two sorts.

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_equities.py --top 4500
    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_ibes_surprises.py
    python3 results/ideas/pead_small/explore.py

WHY: the team lead asked on 2026-11-15 for ideas in undersized markets a small book can
exploit. `pead_wide` (results/ideas/2026-11-11_pead_wide.md) found little drift on the 1,500
largest stocks sorted on the IBES surprise (0.21), and more when sorted on the stock's own
announcement move (0.73), a sort chosen AFTER looking. Smaller stocks are followed by fewer
analysts and are where the published drift is largest, and no return on them has been read
on this desk. They are therefore also a fresh universe for the announcement-move sort.

FIXED BEFORE ANY RETURN ON THESE STOCKS WAS READ (2026-11-15):
  UNIVERSE  previous month-end market-value rank 1,501 to 4,000, price >= $5 at t, 21-session
            average dollar volume >= $500,000 at t (the small-reversal test's universe).
  EVENT     as pead_wide: a US quarterly EPS release on IBES; t = the first session at whose
            close it is public (`pead_wide.explore.known_session`, imported).
  SORT A    the IBES surprise score (needs analyst estimates).
  SORT B    the announcement move: the stock's return less the universe's equal-weighted
            return, summed over t-1 and t. Known at t's close.
  BOOK      pead_wide's, imported: among stocks with a live signal (40 sessions from t),
            long the top tenth, short the bottom tenth, equal weights, unit gross; flat
            under 50 names. shift(2): the announcement day's own move is never earned.
  LONG LEG  the top tenth alone at 100%, against IWM short 100%: the half that needs no
            borrow. SHORT LEG likewise, for information.
  EXPECTED  both sorts positive and above their large-stock figures; B above A.
  CONTROL   each sort 126 sessions late.
  DESCRIPTIVE ONLY: halves and eras; capacity at $250k, $1M and $5M.
Gross only; no cost is modelled.
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
_spec = importlib.util.spec_from_file_location("pw", HERE.parent / "pead_wide" / "explore.py")
pw = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(pw)
RES = Path.home() / "quantt_research"
PANEL = RES / "crsp_top4500_daily.parquet"
RANK_LO, RANK_HI, MIN_PRICE, MIN_ADV, HOLD, STALE = 1500, 4000, 5.0, 500_000.0, 40, 126


def leg(H: pd.DataFrame, sign: int) -> pd.DataFrame:
    side = H.clip(lower=0.0) if sign > 0 else H.clip(upper=0.0)
    tot = side.abs().sum(axis=1)
    side = side.div(tot.where(tot > 1e-12), axis=0).fillna(0.0)
    return pd.concat([side, (-side.sum(axis=1)).rename("IWM")], axis=1)


def main() -> int:
    df = pd.read_parquet(PANEL, columns=["permno", "date", "ret", "prc", "cap_rank", "dollar_volume"])
    df["date"] = pd.to_datetime(df["date"])
    last = df["date"].max().date()
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc").astype("float32")
    rank = df.pivot(index="date", columns="permno", values="cap_rank").astype("float32")
    dv = df.pivot(index="date", columns="permno", values="dollar_volume")
    del df
    adv = dv.rolling(21, min_periods=10).mean()
    band = (rank > RANK_LO) & (rank <= RANK_HI)
    ok = band & (prc >= MIN_PRICE) & (adv >= MIN_ADV)
    mkt = ret.where(band).mean(axis=1)
    ab = ret.sub(mkt, axis=0)
    ev = pd.read_parquet(pw.EVENTS)
    ev = ev[ev["permno"].isin(ret.columns)].copy()
    ev["t"] = pw.known_session(ev, ret.index)
    ev = ev.dropna(subset=["t"]).sort_values(["t", "anndats"]).drop_duplicates(["t", "permno"], keep="last")
    # ALIGNMENT: the move is the abnormal return on t-1 and t, both dated <= t, the decision row.
    move2 = ab + ab.shift(1)
    pos = ret.index.get_indexer(ev["t"]); col = ret.columns.get_indexer(ev["permno"])
    ev["ann_move"] = move2.to_numpy()[pos, col]
    yf = pd.read_parquet(RES / "yf_daily.parquet")
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"]
    start = iwm.dropna().index.min()
    R = ret.fillna(0.0)
    Ri = R.loc[start:].copy(); Ri["IWM"] = iwm.reindex(Ri.index)
    if Ri["IWM"].isna().any():
        raise ValueError("IWM has no return on a CRSP session inside its own range")
    out = {"panel_last_date": str(last), "events_last_date": str(pd.to_datetime(ev["anndats"]).max().date()),
           "fixed": {"rank": [RANK_LO + 1, RANK_HI], "min_price": MIN_PRICE, "min_adv": MIN_ADV, "hold": HOLD}}
    for name, field in (("surprise", "suescore"), ("announcement_move", "ann_move")):
        S = ev.dropna(subset=[field]).pivot(index="t", columns="permno", values=field).reindex(index=ret.index, columns=ret.columns)
        H = pw.book(S.ffill(limit=HOLD - 1).where(ok))
        Hs = pw.book(S.shift(STALE).ffill(limit=HOLD - 1).where(ok))
        first = S.notna().any(axis=1).idxmax()
        res_h = harness.evaluate(H, R)
        pnl = res_h["pnl"].loc[first:].iloc[HOLD + harness.EXEC_LAG:]
        books = {"both": (pnl, harness.evaluate(Hs, R)["pnl"])}
        for lname, sign in (("long_leg", 1), ("short_leg", -1)):
            books[lname] = (harness.evaluate(leg(H.loc[start:], sign), Ri)["pnl"].reindex(pnl.index).dropna(),
                            harness.evaluate(leg(Hs.loc[start:], sign), Ri)["pnl"])
        o = {"events_with_signal": int(S.notna().sum().sum()), "names_per_day_mean": float((H != 0).sum(axis=1).loc[pnl.index].mean()),
             "turnover_per_year": float(res_h["turn"]),
             "held_name_days_with_no_row": int(((H.shift(harness.EXEC_LAG).fillna(0.0) != 0) & ret.isna()).sum().sum())}
        print(f"\n===== sort: {name} | events {o['events_with_signal']:,} | names a day {o['names_per_day_mean']:.0f} | turnover/yr {o['turnover_per_year']:.1f} | held name-days with no row {o['held_name_days_with_no_row']}")
        for bname, (p, st) in books.items():
            ctl = {"signal 126 sessions late": st.reindex(p.index)}
            res = explore.summarise(p, controls=ctl)
            o[bname] = res
            d = HERE / f"{name}_{bname}"; d.mkdir(exist_ok=True)
            explore.write(d, res, p, controls=ctl, title=f"Earnings drift, ranks 1,501-4,000, {name} sort, {bname}; shift(2), gross; to {last}")
            print(f"-- {bname}")
            print(explore.table(res))
        share = (H.abs() / adv).replace([np.inf, -np.inf], np.nan).loc["2024-01-01":]
        nz = share.where(H.loc["2024-01-01":] != 0).stack()
        o["capacity_2024_on"] = {f"position_pct_of_adv_at_{s:,}": {"median": float(nz.median() * s * 100), "p95": float(nz.quantile(0.95) * s * 100)}
                                 for s in (250_000, 1_000_000, 5_000_000)}
        print("capacity:", o["capacity_2024_on"])
        out[name] = o
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
