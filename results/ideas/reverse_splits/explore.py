"""Explore: reverse stock splits on common shares. Does the share keep falling once the split is effective?

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_reverse_splits.py
    python3 results/ideas/reverse_splits/explore.py

FIXED BEFORE ANY RETURN WAS READ (2026-11-15). Only counts, ex-day prices and dollar volume
had been looked at (3,375 reverse splits on common shares since 2000; median ex-day price
$4.08; median ex-day dollar volume $810k; 1,852 with price >= $2 and volume >= $500k).

  EVENT     a reverse split on a common share: CRSP distype FRS or SP, price factor between
            -1 and 0, security typed EQTY/COM/NS on the ex-date.
  DATING    X = CRSP's ex-date, the first session the share trades at the new ratio. The
            split is public by the close of X whatever its announcement date was, so the
            main book needs no announcement date at all.
  ELIGIBLE  measured at the close of the decision session, never later: price >= $2 and
            21-session average dollar volume >= $500,000 (the values every event test on
            this desk has used; dollar volume does not change with the ratio).
  TWO BOOKS, each name a fixed 10% of the book with IWM the same size the other way,
  scaled down pro rata when a side would pass 50%:
    AFTER   short. Decided at the close of X, filled at the close of X+1, earns X+2
            through X+21 (twenty sessions).
    WAIT    short. Needs CRSP's declaration date D; D1 = the first session after D.
            Decided at D1, filled at the next close, earns from the session after that
            through X-1. Out before the split. Most splits are declared only days ahead,
            so this book is expected to be thin.
  EXPECTED SIGN, written down first: both shorts positive (a company that reverse-splits
  to keep its listing usually needs to sell shares soon after; holders who cannot own a
  low-priced or recently-split share sell).
  CONTROLS  (1) the AFTER book on FORWARD splits of common shares (factor > 0);
            (2) the AFTER book on the same reverse splits moved 60 sessions later, and
            (3) 60 sessions earlier: these shares were falling before the split, and a
            share that simply keeps falling at the same rate is not an event effect.
  DESCRIPTIVE ONLY, never used to choose: the event-time profile against IWM from X-10
            to X+40; the AFTER book by ratio (under 1-for-5, 1-for-5 to under 1-for-20,
            1-for-20 and over), by era, and on $5M-a-day names.

ALIGNMENT. `harness.evaluate` earns row t's weights on session t+2. A weight that should
earn session s is written on row s-2; price and volume are read on the decision row. The
AFTER book's first weight row is X itself. A WAIT event whose first weight row would fall
before its D1 is skipped.

NOT MODELLED, and it matters here more than anywhere: BORROW. The desk's October catalogue
(card G1) found most 2025 reverse-split names hard to short. A gross short return on these
names is a statement about prices, not about what the desk could have earned.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
MIN_PRICE, MIN_ADV = 2.0, 500_000.0
UNIT, SIDE_CAP, HOLD = 0.10, 0.50, 20
RATIO = {"under 1-for-5": (-0.8, 0.0), "1-for-5 to under 1-for-20": (-0.95, -0.8), "1-for-20 and over": (-1.0, -0.95)}
ERAS = {"2000-07": ("2000", "2007"), "2008-12": ("2008", "2012"), "2013-17": ("2013", "2017"),
        "2018-22": ("2018", "2022"), "2023-25": ("2023", "2025")}


def load():
    ev = pd.read_parquet(RES / "crsp_split_events.parquet")
    px = pd.read_parquet(RES / "crsp_split_daily.parquet")
    yf = pd.read_parquet(RES / "yf_daily.parquet")
    for c in ("ex_date", "declared"):
        ev[c] = pd.to_datetime(ev[c])
    px["date"] = pd.to_datetime(px["date"])
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"].dropna()
    sessions = pd.DatetimeIndex(sorted(px["date"].unique()))
    sessions = sessions[(sessions >= iwm.index.min()) & (sessions <= iwm.index.max())]
    if iwm.reindex(sessions).isna().any():
        raise ValueError("IWM has no return on a CRSP session inside its own range")
    piv = lambda col: px.pivot(index="date", columns="permno", values=col).reindex(sessions)  # noqa: E731
    return ev, piv("ret"), piv("prc"), piv("dollar_volume"), iwm.reindex(sessions), sessions


def place(ev, sessions, prc, adv) -> pd.DataFrame:
    """Session positions of each event and its eligibility on each book's decision row."""
    e = ev[ev["ex_date"].isin(sessions) & ev["permno"].isin(prc.columns)].copy()
    e["x"] = sessions.get_indexer(e["ex_date"])
    has_d = e["declared"].notna() & (e["declared"] >= sessions[0])
    # D1 = first session strictly after the declaration date; -1 where CRSP gives none
    e["d1"] = np.where(has_d, sessions.searchsorted(e["declared"].fillna(sessions[0]).to_numpy(), side="right"), -1)
    cols = prc.columns.get_indexer(e["permno"])
    P, A = prc.to_numpy(), adv.to_numpy()

    def ok_at(row):
        good = (row >= 0) & (row < len(P))
        r = np.clip(row, 0, len(P) - 1)
        return good & (P[r, cols] >= MIN_PRICE) & (A[r, cols] >= MIN_ADV)

    e["ok_after"] = ok_at(e["x"].to_numpy())
    e["ok_wait"] = ok_at(e["d1"].to_numpy()) & (e["d1"].to_numpy() >= 0)
    e["adv_x"] = A[e["x"].to_numpy(), cols]
    return e


def book(e, which, sessions, columns, *, shift=0):
    L = harness.EXEC_LAG
    W = np.zeros((len(sessions), len(columns)))
    cpos = pd.Index(columns).get_indexer(e["permno"])
    n = 0
    for x, d1, c, ok in zip(e["x"].to_numpy() + shift, e["d1"].to_numpy(), cpos, e[f"ok_{which}"].to_numpy()):
        if not ok:
            continue
        if which == "after":                 # earn x+2 .. x+21; first weight row is x
            first, last = x + L, x + L + HOLD - 1
            floor = x
        else:                                # wait: earn d1+2 .. x-1
            first, last = d1 + L, x - 1
            floor = d1
        lo, hi = first - L, min(last - L, len(sessions) - 1)
        if hi < lo or lo < 0 or lo < floor:
            continue
        W[lo:hi + 1, c] -= UNIT
        n += 1
    side = np.abs(W).sum(axis=1)
    W *= np.where(side > SIDE_CAP, SIDE_CAP / np.where(side > 0, side, 1.0), 1.0)[:, None]
    H = pd.DataFrame(W, index=sessions, columns=list(columns))
    H["IWM"] = -H.sum(axis=1)
    return H, n


def run(e, which, sessions, R, *, shift=0):
    H, n = book(e, which, sessions, R.columns.drop("IWM"), shift=shift)
    held = harness.held(H)
    names = held.drop(columns="IWM")
    missing = int(((names != 0) & R.drop(columns="IWM").isna()).sum().sum())
    res = harness.evaluate(H, R.fillna(0.0))
    pnl = res["pnl"].iloc[harness.EXEC_LAG:]
    gross = names.abs().sum(axis=1)
    return pnl, {"events_traded": n, "events_per_year": n / (len(sessions) / 252),
                 "held_name_days_with_no_return": missing, "held_name_days": int((names != 0).sum().sum()),
                 "mean_names_held": float((names != 0).sum(axis=1).mean()),
                 "share_of_days_invested": float((gross > 0).mean()),
                 "turnover_per_year": float(res["turn"])}


def profile(e, ret, iwm, lo, hi) -> dict:
    rel = ret.sub(iwm, axis=0).to_numpy()
    cpos = ret.columns.get_indexer(e["permno"])
    month = ret.index.to_period("M")
    out = {}
    for k in range(lo, hi + 1):
        rows = e["x"].to_numpy() + k
        good = (rows >= 0) & (rows < len(rel))
        v = pd.Series(rel[rows[good], cpos[good]], index=month[rows[good]]).dropna()
        m = v.groupby(level=0).mean()
        out[f"{k:+d}"] = {"mean_bp": float(v.mean() * 1e4), "median_bp": float(v.median() * 1e4), "n": int(len(v)),
                          "t_by_month": float(m.mean() / m.std() * np.sqrt(len(m)))}
    return out


def main() -> int:
    ev, ret, prc, dv, iwm, sessions = load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy(); R["IWM"] = iwm
    out = {"panel_first_date": str(sessions[0].date()), "panel_last_date": str(sessions[-1].date()),
           "fixed": {"min_price": MIN_PRICE, "min_adv": MIN_ADV, "unit": UNIT, "side_cap": SIDE_CAP, "hold": HOLD}}
    rs = place(ev[ev["facpr"] < 0], sessions, prc, adv)
    fs = place(ev[ev["facpr"] > 0], sessions, prc, adv)
    out["counts"] = {"reverse_placed": int(len(rs)), "reverse_eligible_after": int(rs["ok_after"].sum()),
                     "reverse_eligible_wait": int(rs["ok_wait"].sum()),
                     "forward_placed": int(len(fs)), "forward_eligible_after": int(fs["ok_after"].sum()),
                     "sessions_d1_to_x_median": float((rs["x"] - rs["d1"])[rs["d1"] >= 0].median()),
                     "share_declared_with_d1_at_or_after_x_minus_2": float(((rs["x"] - 2) <= rs["d1"])[rs["d1"] >= 0].mean())}
    print(json.dumps(out["counts"], indent=1))
    for which in ("after", "wait"):
        pnl, meta = run(rs, which, sessions, R)
        controls = {}
        if which == "after":
            controls = {"forward splits, same rule": run(fs, "after", sessions, R)[0],
                        "same events, 60 sessions later": run(rs, "after", sessions, R, shift=60)[0],
                        "same events, 60 sessions earlier": run(rs, "after", sessions, R, shift=-60)[0]}
        res = explore.summarise(pnl, controls=controls, extra=meta)
        if which == "after":
            res["by_ratio"] = {}
            for b, (lo, hi) in RATIO.items():
                p, m = run(rs[(rs["facpr"] > lo) & (rs["facpr"] <= hi)] if lo > -1 else rs[rs["facpr"] <= hi], which, sessions, R)
                res["by_ratio"][b] = {**explore.stats(p), "events_traded": m["events_traded"]}
            res["by_era"] = {k: explore.stats(pnl.loc[a:b]) for k, (a, b) in ERAS.items()}
            p5, m5 = run(rs[rs["adv_x"] >= 5e6], which, sessions, R)
            res["adv_5m"] = {**explore.stats(p5), "events_traded": m5["events_traded"]}
        out[which] = res
        d = HERE / which
        d.mkdir(exist_ok=True)
        explore.write(d, res, pnl, controls=controls,
                      title=f"Reverse splits, {which} (short): 10% a name vs IWM; shift(2), gross, no borrow; to {out['panel_last_date']}")
        print(f"\n== {which}: events {meta['events_traded']:,} ({meta['events_per_year']:.0f}/yr) | invested {meta['share_of_days_invested']:.0%} | "
              f"names held {meta['mean_names_held']:.1f} | missing-return name-days {meta['held_name_days_with_no_return']} of {meta['held_name_days']}")
        print(explore.table(res))
        for k in ("by_ratio", "by_era"):
            if k in res:
                print(f"  {k}:", " | ".join(f"{b}: SR {v['sharpe']:.2f} t {v['t']:.1f}" + (f" n {v['events_traded']}" if 'events_traded' in v else "") for b, v in res[k].items()))
        if "adv_5m" in res:
            print(f"  $5M names: SR {res['adv_5m']['sharpe']:.2f} t {res['adv_5m']['t']:.2f} n {res['adv_5m']['events_traded']}")
    out["profile_vs_iwm_around_x"] = profile(rs[rs["ok_after"]], ret, iwm, -10, 40)
    print("\nprofile (bp, t by month):", " ".join(f"{a}:{v['mean_bp']:+.0f}({v['t_by_month']:+.1f})" for a, v in out["profile_vs_iwm_around_x"].items()))
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
