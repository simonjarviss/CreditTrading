"""Explore: dividend initiations and resumptions on common stocks. Does the share drift up for a quarter?

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_div_initiations.py
    python3 results/ideas/div_initiations/explore.py

FIXED BEFORE ANY RETURN WAS READ (2026-11-15). Only counts had been looked at: 1,625 events
since 2000 (about 63 a year; 169 in 2003, the year the dividend tax was cut); 1,006 are the
security's first cash dividend on CRSP and 619 follow at least 730 days without one; 30 have
no declaration date; the median declaration is 16 days before the ex-date.

  EVENT     an ordinary cash dividend on a common share with no cash dividend of any kind in
            the 730 days before its ex-date, the share listed on CRSP for at least those
            730 days (scripts/research/stage_crsp_div_initiations.py).
  DATING    D = CRSP's declaration date, D1 = the first session after it. The decision row
            is D1+1, ONE SESSION LATER than the special-dividend test used: that test's
            check against 8-K filings found CRSP's date 1 to 4 days ahead of the filing for
            half the sampled events (results/ideas/2026-11-15_special_dividends.md).
  ELIGIBLE  at the close of D1+1: price >= $2, 21-session average dollar volume >= $500,000.
  ONE BOOK  DRIFT, long. Each name a fixed 10% of the book with IWM the same size the other
            way, scaled down pro rata when a side would pass 50%. Decided at D1+1, filled at
            the close of D1+2, earns D1+3 through D1+62 (sixty sessions).
  EXPECTED SIGN, written down first: positive (the published record is a drift of several
            percent over the following year; a company starts paying when it expects the
            cash to last).
  CONTROLS  the same events with the window moved 120 sessions later, and 60 sessions
            earlier (not tradable: it shows what these shares were doing before the news).
  DESCRIPTIVE ONLY, never used to choose: by era; first-ever dividends against resumptions;
            names trading $5M a day; the first 20 earning sessions against the other 40; the
            event-time profile against IWM in ten-session blocks from D1-20 to D1+120.

ALIGNMENT. `harness.evaluate` earns row t's weights on session t+2. A weight that should
earn session s is written on row s-2; the first weight row is D1+1, the decision row, and
price and volume are read on that row.
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
UNIT, SIDE_CAP = 0.10, 0.50
DELAY, FIRST, LAST = 1, 3, 62        # decision row D1+DELAY; earning sessions D1+FIRST .. D1+LAST
ERAS = {"2000-07": ("2000", "2007"), "2008-12": ("2008", "2012"), "2013-17": ("2013", "2017"),
        "2018-22": ("2018", "2022"), "2023-25": ("2023", "2025")}


def load():
    ev = pd.read_parquet(RES / "crsp_div_init_events.parquet")
    px = pd.read_parquet(RES / "crsp_div_init_daily.parquet")
    yf = pd.read_parquet(RES / "yf_daily.parquet")
    for c in ("ex_date", "declared", "prev_ex"):
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
    e = ev.dropna(subset=["declared"]).copy()
    e = e[(e["declared"] >= sessions[0]) & e["permno"].isin(prc.columns)]
    e["d1"] = sessions.searchsorted(e["declared"].to_numpy(), side="right")   # first session strictly after D
    e = e[e["d1"] + DELAY < len(sessions)]
    cols = prc.columns.get_indexer(e["permno"])
    row = e["d1"].to_numpy() + DELAY
    P, A = prc.to_numpy()[row, cols], adv.to_numpy()[row, cols]
    e["ok"] = (P >= MIN_PRICE) & (A >= MIN_ADV)
    e["adv_dec"] = A
    e["first_ever"] = e["prev_ex"].isna()
    return e


def book(e, sessions, columns, *, first=FIRST, last=LAST, shift=0):
    L = harness.EXEC_LAG
    W = np.zeros((len(sessions), len(columns)))
    cpos = pd.Index(columns).get_indexer(e["permno"])
    n = 0
    for d1, c, ok in zip(e["d1"].to_numpy(), cpos, e["ok"].to_numpy()):
        if not ok:
            continue
        lo, hi = d1 + first - L + shift, min(d1 + last - L + shift, len(sessions) - 1)
        if hi < lo or lo < 0 or (shift == 0 and lo < d1 + DELAY):
            continue                      # never a weight before the decision row of the real event
        W[lo:hi + 1, c] += UNIT
        n += 1
    tot = W.sum(axis=1)
    W *= np.where(tot > SIDE_CAP, SIDE_CAP / np.where(tot > 0, tot, 1.0), 1.0)[:, None]
    H = pd.DataFrame(W, index=sessions, columns=list(columns))
    H["IWM"] = -H.sum(axis=1)
    return H, n


def run(e, sessions, R, **kw):
    H, n = book(e, sessions, R.columns.drop("IWM"), **kw)
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
                 "share_of_days_at_cap": float((gross >= SIDE_CAP - 1e-9).mean()),
                 "turnover_per_year": float(res["turn"])}


def blocks(e, ret, iwm, lo, hi, step=10) -> dict:
    """Mean summed return less IWM per event over ten-session blocks from D1, t by month."""
    rel = ret.sub(iwm, axis=0).to_numpy()
    cpos = ret.columns.get_indexer(e["permno"])
    month = ret.index.to_period("M")
    out = {}
    for a in range(lo, hi, step):
        v, mth = [], []
        for d1, c in zip(e["d1"].to_numpy(), cpos):
            if d1 + a < 0 or d1 + a + step > len(rel):
                continue
            x = rel[d1 + a:d1 + a + step, c]
            if np.isnan(x).all():
                continue
            v.append(np.nansum(x)); mth.append(month[d1])
        s = pd.Series(v, index=mth)
        m = s.groupby(level=0).mean()
        out[f"{a:+d}..{a + step - 1:+d}"] = {"mean_pct": float(s.mean() * 100), "median_pct": float(s.median() * 100), "n": int(len(s)),
                                             "t_by_month": float(m.mean() / m.std() * np.sqrt(len(m)))}
    return out


def main() -> int:
    ev, ret, prc, dv, iwm, sessions = load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy(); R["IWM"] = iwm
    e = place(ev, sessions, prc, adv)
    out = {"panel_first_date": str(sessions[0].date()), "panel_last_date": str(sessions[-1].date()),
           "fixed": {"min_price": MIN_PRICE, "min_adv": MIN_ADV, "unit": UNIT, "side_cap": SIDE_CAP, "delay": DELAY, "first": FIRST, "last": LAST},
           "counts": {"placed": int(len(e)), "eligible": int(e["ok"].sum()), "eligible_first_ever": int((e["ok"] & e["first_ever"]).sum())}}
    print(json.dumps(out["counts"], indent=1))
    pnl, meta = run(e, sessions, R)
    controls = {"same events, 120 sessions later": run(e, sessions, R, shift=120)[0],
                "same events, 60 sessions earlier": run(e, sessions, R, shift=-60)[0]}
    res = explore.summarise(pnl, controls=controls, extra=meta)
    res["by_era"] = {k: explore.stats(pnl.loc[a:b]) for k, (a, b) in ERAS.items()}
    res["cuts"] = {}
    for k, (sub, kw) in {"first-ever dividends": (e[e["first_ever"]], {}), "resumptions": (e[~e["first_ever"]], {}),
                         "$5M a day": (e[e["adv_dec"] >= 5e6], {}), "$20M a day": (e[e["adv_dec"] >= 2e7], {}),
                         "first 20 earning sessions": (e, {"last": FIRST + 19}), "the other 40": (e, {"first": FIRST + 20})}.items():
        p, m = run(sub, sessions, R, **kw)
        res["cuts"][k] = {**explore.stats(p), "events_traded": m["events_traded"]}
    out["drift"] = res
    explore.write(HERE, res, pnl, controls=controls,
                  title=f"Dividend initiations, long 60 sessions: 10% a name vs IWM; shift(2), gross; to {out['panel_last_date']}")
    print(f"\n== drift: events {meta['events_traded']:,} ({meta['events_per_year']:.0f}/yr) | invested {meta['share_of_days_invested']:.0%} | at cap {meta['share_of_days_at_cap']:.0%} | "
          f"names held {meta['mean_names_held']:.1f} | missing-return name-days {meta['held_name_days_with_no_return']} of {meta['held_name_days']}")
    print(explore.table(res))
    print("  by era:", " | ".join(f"{b}: SR {v['sharpe']:.2f} t {v['t']:.1f}" for b, v in res["by_era"].items()))
    print("  cuts:", " | ".join(f"{b}: SR {v['sharpe']:.2f} t {v['t']:.1f} n {v['events_traded']}" for b, v in res["cuts"].items()))
    out["blocks_vs_iwm_from_d1"] = blocks(e[e["ok"]], ret, iwm, -20, 120)
    print("\nten-session blocks from D1 (% less IWM, t by month):", " ".join(f"[{a}] {v['mean_pct']:+.2f} ({v['t_by_month']:+.1f})" for a, v in out["blocks_vs_iwm_from_d1"].items()))
    (HERE / "results_full.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
