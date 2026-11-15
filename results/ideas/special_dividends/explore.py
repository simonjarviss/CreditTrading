"""Explore: special cash dividends on common stocks. The wait, the ex-day, and the days after.

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_special_divs.py
    python3 results/ideas/special_dividends/explore.py

FIXED BEFORE ANY RETURN WAS READ (2026-11-15). Only event counts, yields and declaration
leads had been looked at (3,626 events; median yield 2.1%; median lead 13 calendar days).

  EVENT     a special cash dividend in US dollars on a common share (CRSP distype SD,
            security typed EQTY/COM/NS on the ex-date), with a declaration date on CRSP.
  DATING    D = the declaration date. CRSP gives no time of day, so the news is taken as
            public by the close of the first session AFTER D ("D1"). X = the ex-date.
  ELIGIBLE  measured at the close of the decision session, never later: price >= $2,
            21-session average dollar volume >= $500,000 (both the closed-end fund test's
            values), and yield = amount / that close >= 1%.
  THREE BOOKS, each name a fixed 10% of the book with IWM the same size the other way,
  scaled down pro rata when a side would pass 50% (the spin-off test's sizing):
    WAIT    long. Decided at D1, filled at the next close, earns from the session after
            that through X-1. Out at the close before the ex-date.
    EXDAY   long. Decided at X-2, filled at the close of X-1, earns the ex-date's total
            return (CRSP's return includes the dividend). Needs D1 <= X-2.
    AFTER   short. Earns X+1, X+2 and X+3: the closed-end fund rule, unchanged.
  EXPECTED SIGNS, written down first: WAIT positive (holders are paid to wait and buyers
  arrive before a large payment), EXDAY positive (the price falls by less than the
  dividend), AFTER positive for the short (the closed-end fund pattern). Any of the three
  may fail; each is reported whatever it shows.
  CONTROLS  (1) the same three books on every ORDINARY cash dividend of the same
            securities (no yield floor: an ordinary dividend is rarely 1%); (2) the AFTER
            book on the same events moved ten sessions later.
  DESCRIPTIVE ONLY, never used to choose: the event-time profile against IWM, and each
            book by yield bucket (1-2%, 2-5%, 5% and over).

ALIGNMENT. `harness.evaluate` earns row t's weights on session t+2. A weight that should
earn session s is therefore written on row s-2, and everything that decides it (the
declaration, the price, the volume) is dated at or before row s-2. An event whose first
weight row would fall before its D1 is skipped (corrected 2026-11-15: this said "the script
asserts", and the assert could not fail; an independent review confirmed that no weight
lies outside D1 .. X-3 of an eligible event).

NOT MODELLED: borrow on the AFTER short, dividend tax, and the due-bill rule for very large
dividends (CRSP's ex-date is used as given).
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

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
MIN_PRICE, MIN_ADV, MIN_YIELD = 2.0, 500_000.0, 0.01
UNIT, SIDE_CAP, AFTER_HOLD = 0.10, 0.50, 3
BUCKETS = {"1-2%": (0.01, 0.02), "2-5%": (0.02, 0.05), "5%+": (0.05, np.inf)}


def load():
    ev = pd.read_parquet(RES / "crsp_specdiv_events.parquet")
    px = pd.read_parquet(RES / "crsp_specdiv_daily.parquet")
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


def place(ev: pd.DataFrame, sessions: pd.DatetimeIndex, prc, adv, *, min_yield: float) -> pd.DataFrame:
    """Session positions of each event and its eligibility at each book's decision row."""
    e = ev.dropna(subset=["declared"]).copy()
    e = e[e["ex_date"].isin(sessions) & e["permno"].isin(prc.columns)]
    e["x"] = sessions.get_indexer(e["ex_date"])
    # D1 = the first session strictly after the declaration date
    e["d1"] = sessions.searchsorted(e["declared"].to_numpy(), side="right")
    e = e[(e["d1"] < len(sessions)) & (e["declared"] >= sessions[0])]
    cols = prc.columns.get_indexer(e["permno"])
    P, A = prc.to_numpy(), adv.to_numpy()

    def ok_at(row):                       # eligibility read on the decision row only
        row = row.to_numpy()
        good = row >= 0
        p = np.where(good, P[np.clip(row, 0, len(P) - 1), cols], np.nan)
        a = np.where(good, A[np.clip(row, 0, len(A) - 1), cols], np.nan)
        y = e["amount"].to_numpy() / p
        return (p >= MIN_PRICE) & (a >= MIN_ADV) & (y >= min_yield), y

    e["ok_wait"], e["yield_wait"] = ok_at(e["d1"])
    e["ok_exday"], e["yield_exday"] = ok_at(e["x"] - 2)
    e["ok_after"], e["yield_after"] = ok_at(e["x"] - 1)
    return e


def book(e: pd.DataFrame, which: str, sessions, columns, *, shift: int = 0) -> tuple[pd.DataFrame, int]:
    """Weights on DECISION rows (earning session minus the harness lag). Returns (H, events used)."""
    L = harness.EXEC_LAG
    W = np.zeros((len(sessions), len(columns)))
    cpos = pd.Index(columns).get_indexer(e["permno"])
    n = 0
    for x, d1, c, ok in zip(e["x"].to_numpy() + shift, e["d1"].to_numpy(), cpos, e[f"ok_{which}"].to_numpy()):
        if not ok:
            continue
        if which == "wait":          # earn d1+2 .. x-1
            first, last, side = d1 + L, x - 1, 1.0
        elif which == "exday":       # earn x
            first, last, side = x, x, 1.0
        else:                        # earn x+1 .. x+3
            first, last, side = x + 1, x + AFTER_HOLD, -1.0
        lo, hi = first - L, min(last - L, len(sessions) - 1)
        if hi < lo:
            continue
        if lo < d1:
            continue                 # the news was not public by the decision row: not traded
        W[lo:hi + 1, c] += side * UNIT
        n += 1
    side_sum = np.abs(W).sum(axis=1)
    scale = np.where(side_sum > SIDE_CAP, SIDE_CAP / np.where(side_sum > 0, side_sum, 1.0), 1.0)
    W = W * scale[:, None]
    H = pd.DataFrame(W, index=sessions, columns=list(columns))
    H["IWM"] = -H.sum(axis=1)
    return H, n


def run(e, which, sessions, R, *, shift=0) -> tuple[pd.Series, dict]:
    H, n = book(e, which, sessions, R.columns.drop("IWM"), shift=shift)
    held = harness.held(H)
    missing = int(((held.drop(columns="IWM") != 0) & R.drop(columns="IWM").isna()).sum().sum())
    res = harness.evaluate(H, R.fillna(0.0))
    pnl = res["pnl"].iloc[harness.EXEC_LAG:]
    gross = held.drop(columns="IWM").abs().sum(axis=1)
    return pnl, {"events_traded": n, "events_per_year": n / (len(sessions) / 252),
                 "held_name_days_with_no_return": missing,
                 "mean_names_held": float((held.drop(columns="IWM") != 0).sum(axis=1).mean()),
                 "share_of_days_invested": float((gross > 0).mean()),
                 "mean_gross_one_side_when_invested": float(gross[gross > 0].mean()) if (gross > 0).any() else 0.0,
                 "turnover_per_year": float(res["turn"])}


def profile(e, ret, iwm, key: str, lo: int, hi: int) -> dict:
    """Mean return less IWM by session offset from `key` ('x' or 'd1'), t clustered by month."""
    rel = ret.sub(iwm, axis=0).to_numpy()
    cpos = ret.columns.get_indexer(e["permno"])
    month = ret.index.to_period("M")
    out = {}
    for k in range(lo, hi + 1):
        rows = e[key].to_numpy() + k
        good = (rows >= 0) & (rows < len(rel))
        v = pd.Series(rel[rows[good], cpos[good]], index=month[rows[good]]).dropna()
        m = v.groupby(level=0).mean()
        out[f"{k:+d}"] = {"mean_bp": float(v.mean() * 1e4), "n": int(len(v)),
                          "t_by_month": float(m.mean() / m.std() * np.sqrt(len(m))) if len(m) > 2 else None,
                          "median_bp": float(v.median() * 1e4)}
    return out


def main() -> int:
    ev, ret, prc, dv, iwm, sessions = load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy()
    R["IWM"] = iwm
    out = {"panel_last_date": str(sessions[-1].date()), "panel_first_date": str(sessions[0].date()),
           "fixed": {"min_price": MIN_PRICE, "min_adv": MIN_ADV, "min_yield": MIN_YIELD, "unit": UNIT,
                     "side_cap": SIDE_CAP, "after_hold": AFTER_HOLD}}
    sd = place(ev[ev["distype"] == "SD"], sessions, prc, adv, min_yield=MIN_YIELD)
    cd = place(ev[ev["distype"] == "CD"], sessions, prc, adv, min_yield=0.0)
    raw_sd = ev[(ev["distype"] == "SD") & ev["ex_date"].isin(sessions)]
    out["counts"] = {"special_in_window": int(len(raw_sd)), "special_no_declaration_date": int(raw_sd["declared"].isna().sum()),
                     "special_placed": int(len(sd)), "ordinary_placed": int(len(cd)),
                     "special_eligible_wait": int(sd["ok_wait"].sum()), "special_eligible_exday": int(sd["ok_exday"].sum()),
                     "special_eligible_after": int(sd["ok_after"].sum()),
                     "sessions_d1_to_x_median": float((sd["x"] - sd["d1"]).median()),
                     "share_with_d1_after_x_minus_2": float(((sd["x"] - 2) < sd["d1"]).mean())}
    print(json.dumps(out["counts"], indent=1))
    series = {}
    for which in ("wait", "exday", "after"):
        pnl, meta = run(sd, which, sessions, R)
        ctl, cmeta = run(cd, which, sessions, R)
        controls = {"ordinary dividends, same names": ctl}
        if which == "after":
            controls["same events, 10 sessions later"] = run(sd, which, sessions, R, shift=10)[0]
        res = explore.summarise(pnl, controls=controls, extra={**meta, "control_ordinary": cmeta})
        res["by_yield_bucket"] = {}
        for b, (lo, hi) in BUCKETS.items():
            y = sd[f"yield_{which}"]
            bp, bm = run(sd[(y >= lo) & (y < hi)], which, sessions, R)
            res["by_yield_bucket"][b] = {**explore.stats(bp), **{k: bm[k] for k in ("events_traded", "share_of_days_invested")}}
        out[which] = res
        series[which] = pnl
        d = HERE / which
        d.mkdir(exist_ok=True)
        explore.write(d, res, pnl, controls=controls,
                      title=f"Special dividends, {which}: 10% a name vs IWM; shift(2), gross; to {out['panel_last_date']}")
        print(f"\n== {which}: events {meta['events_traded']:,} ({meta['events_per_year']:.0f}/yr) | invested {meta['share_of_days_invested']:.0%} of days | "
              f"names held {meta['mean_names_held']:.1f} | missing-return name-days {meta['held_name_days_with_no_return']}")
        print(explore.table(res))
        print("  by yield:", " | ".join(f"{b}: SR {v['sharpe']:.2f} t {v['t']:.1f} n {v['events_traded']}" for b, v in res["by_yield_bucket"].items()))
    elig = sd[sd["ok_after"]]
    out["profile_vs_iwm_around_ex"] = profile(elig, ret, iwm, "x", -10, 10)
    out["profile_vs_iwm_around_d1"] = profile(sd[sd["ok_wait"]], ret, iwm, "d1", -5, 8)
    out["profile_ordinary_around_ex"] = profile(cd[cd["ok_after"]], ret, iwm, "x", -5, 5)
    for k in ("profile_vs_iwm_around_ex", "profile_vs_iwm_around_d1", "profile_ordinary_around_ex"):
        print(f"\n{k} (bp, t by month):", " ".join(f"{a}:{v['mean_bp']:+.0f}({v['t_by_month']:+.1f})" for a, v in out[k].items()))
    c = pd.DataFrame(series).corr()
    out["correlation_of_books"] = c.round(3).to_dict()
    print("\ncorrelation of the three books:\n", c.round(2).to_string())
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
