"""Explore: IPO lock-up expiries. Does the stock fall when the insiders are free to sell?

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_sdc_ipo_lockups.py
    python3 results/ideas/ipo_lockups/explore.py

FIXED BEFORE ANY RETURN WAS READ (2026-11-15). Only counts had been looked at: 2,823 US IPOs
since 2000 with a lock-up date on SDC and a CRSP common share (about 108 a year; 2,569 with
a 180-day lock-up; median proceeds $114M).

  EVENT     the lock-up expiry date SDC records for a US IPO (the earliest, when a deal has
            several). L = the first session on or after it. The date is the prospectus's,
            known from the IPO, so nothing about dating depends on a filing time.
  ELIGIBLE  read at the close of L-3, the decision close of the first day held: price >= $5
            and 21-session average dollar volume >= $1M (the spin-off test's floors for a
            newly listed share).
  THE BOOK  SHORT the stock over L-1, L and L+1, the three-session window the desk's
            catalogue card quoted from the literature (K5: about -1.5%), LONG IWM the same
            size. Each name a fixed 10% of the book, scaled down when a side would pass 50%.
  EXPECTED  positive for the short. It may fail: the effect has been public since 2001.
  CONTROLS  the same book with the window moved 30 sessions earlier and 30 later, each with
            its own eligibility read three sessions before its own window.
  DESCRIPTIVE ONLY, never used to choose: the event-time profile against IWM from L-15 to
            L+15; the book split by IPO proceeds (under and from $100M, the October note's
            "way back"), by lock-up length (180 days and other) and by era.

ALIGNMENT. `harness.evaluate` earns row t's weights on session t+2, so a weight that earns
session s sits on row s-2 and eligibility is read on the first such row (L-3). Every event's
first weight row is at least 20 sessions after its first trading day, or it is skipped: the
volume average needs that history.

NOT MODELLED: borrow. A recently listed share is often hard to borrow, and the October gate
found 15 of 36 near day 180 shortable at Alpaca. This test reads the gross effect only.
SDC carries a lock-up date for 4,995 of about 10,700 US IPO rows; the ones without a date
are not in the test and may differ.
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
MIN_PRICE, MIN_ADV, UNIT, SIDE_CAP = 5.0, 1_000_000.0, 0.10, 0.50
WINDOW = (-1, 1)                      # earning sessions relative to L
MIN_HISTORY = 20
L_ = harness.EXEC_LAG


def load():
    ev = pd.read_parquet(RES / "sdc_ipo_lockups.parquet")
    px = pd.read_parquet(RES / "crsp_ipo_lockup_daily.parquet")
    yf = pd.read_parquet(RES / "yf_daily.parquet")
    px["date"] = pd.to_datetime(px["date"])
    for c in ("ipo_date", "first_date", "lock_date"):
        ev[c] = pd.to_datetime(ev[c])
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"].dropna()
    sessions = pd.DatetimeIndex(sorted(px["date"].unique()))
    sessions = sessions[(sessions >= iwm.index.min()) & (sessions <= iwm.index.max())]
    if iwm.reindex(sessions).isna().any():
        raise ValueError("IWM has no return on a CRSP session inside its own range")
    piv = lambda col: px.pivot(index="date", columns="permno", values=col).reindex(sessions)  # noqa: E731
    return ev, piv("ret"), piv("prc"), piv("dollar_volume"), iwm.reindex(sessions), sessions


def place(ev, sessions, prc, adv, *, shift: int = 0) -> pd.DataFrame:
    """Session row of L for each event (plus `shift`), and eligibility read at the decision row."""
    e = ev[ev["permno"].isin(prc.columns)].copy()
    e = e[(e["lock_date"] >= sessions[0]) & (e["lock_date"] <= sessions[-1])]
    e["l"] = sessions.searchsorted(e["lock_date"].to_numpy(), side="left") + shift
    e["first_row"] = sessions.searchsorted(e["first_date"].to_numpy(), side="left")
    dec = e["l"] + WINDOW[0] - L_                          # the first weight row
    e = e[(dec >= 0) & (e["l"] + WINDOW[1] < len(sessions))].copy()
    dec = (e["l"] + WINDOW[0] - L_).to_numpy()
    cols = prc.columns.get_indexer(e["permno"])
    p, a = prc.to_numpy()[dec, cols], adv.to_numpy()[dec, cols]
    e["dec"] = dec
    e["ok"] = (p >= MIN_PRICE) & (a >= MIN_ADV) & (dec - e["first_row"].to_numpy() >= MIN_HISTORY)
    return e


def run(e, sessions, R) -> tuple[pd.Series, dict]:
    names = R.columns.drop("IWM")
    W = np.zeros((len(sessions), len(names)))
    cpos = names.get_indexer(e["permno"])
    n = 0
    for l, c, ok in zip(e["l"].to_numpy(), cpos, e["ok"].to_numpy()):
        if ok:
            W[l + WINDOW[0] - L_:l + WINDOW[1] - L_ + 1, c] -= UNIT
            n += 1
    tot = np.abs(W).sum(axis=1)
    W *= np.where(tot > SIDE_CAP, SIDE_CAP / np.where(tot > 0, tot, 1.0), 1.0)[:, None]
    H = pd.DataFrame(W, index=sessions, columns=names)
    H["IWM"] = -H.sum(axis=1)
    held = harness.held(H)
    missing = int(((held[names] != 0) & R[names].isna()).sum().sum())
    res = harness.evaluate(H, R.fillna(0.0))
    gross = held[names].abs().sum(axis=1)
    return res["pnl"].iloc[L_:], {"events_traded": n, "events_per_year": n / (len(sessions) / 252),
                                  "held_name_days_with_no_return": missing,
                                  "share_of_days_invested": float((gross > 0).mean()),
                                  "mean_names_held": float((held[names] != 0).sum(axis=1).mean()),
                                  "turnover_per_year": float(res["turn"])}


def profile(e, ret, iwm, lo, hi) -> dict:
    rel = ret.sub(iwm, axis=0).to_numpy()
    cpos = ret.columns.get_indexer(e["permno"])
    month = ret.index.to_period("M")
    out = {}
    for k in range(lo, hi + 1):
        rows = e["l"].to_numpy() + k
        good = (rows >= 0) & (rows < len(rel))
        v = pd.Series(rel[rows[good], cpos[good]], index=month[rows[good]]).dropna()
        m = v.groupby(level=0).mean()
        out[f"{k:+d}"] = {"mean_bp": float(v.mean() * 1e4), "median_bp": float(v.median() * 1e4), "n": int(len(v)),
                          "t_by_month": float(m.mean() / m.std() * np.sqrt(len(m)))}
    return out


def main() -> int:
    ev, ret, prc, dv, iwm, sessions = load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy()
    R["IWM"] = iwm
    e = place(ev, sessions, prc, adv)
    out = {"panel_first_date": str(sessions[0].date()), "panel_last_date": str(sessions[-1].date()),
           "fixed": {"min_price": MIN_PRICE, "min_adv": MIN_ADV, "unit": UNIT, "side_cap": SIDE_CAP, "window": WINDOW},
           "counts": {"staged": int(len(ev)), "placed": int(len(e)), "eligible": int(e["ok"].sum()),
                      "eligible_180_day": int((e["ok"] & (e["lock_days"] == 180)).sum()),
                      "eligible_proceeds_100m": int((e["ok"] & (e["proceeds_musd"] >= 100)).sum())}}
    print(json.dumps(out["counts"]))
    pnl, meta = run(e, sessions, R)
    controls = {f"window moved {k:+d} sessions": run(place(ev, sessions, prc, adv, shift=k), sessions, R)[0] for k in (-30, 30)}
    res = explore.summarise(pnl, controls=controls, extra=meta)
    splits = {"proceeds under $100M": e[e["proceeds_musd"] < 100], "proceeds $100M and over": e[e["proceeds_musd"] >= 100],
              "180-day lock-up": e[e["lock_days"] == 180], "other lock-up lengths": e[e["lock_days"] != 180]}
    res["splits"] = {}
    for k, sub in splits.items():
        p, m = run(sub, sessions, R)
        res["splits"][k] = {**explore.stats(p), "events_traded": m["events_traded"]}
    out["book"] = res
    out["profile_vs_iwm"] = profile(e[e["ok"]], ret, iwm, -15, 15)
    explore.write(HERE, res, pnl, controls=controls,
                  title=f"IPO lock-up expiry: short L-1..L+1, 10% a name vs IWM; shift(2), gross; to {out['panel_last_date']}")
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    print(f"\nevents {meta['events_traded']:,} ({meta['events_per_year']:.0f}/yr) | invested {meta['share_of_days_invested']:.0%} of days | "
          f"names held {meta['mean_names_held']:.2f} | missing-return name-days {meta['held_name_days_with_no_return']}")
    print(explore.table(res))
    print("splits:", " | ".join(f"{k}: SR {v['sharpe']:.2f} t {v['t']:.1f} n {v['events_traded']}" for k, v in res["splits"].items()))
    print("profile vs IWM (bp, t by month):", " ".join(f"{a}:{v['mean_bp']:+.0f}({v['t_by_month']:+.1f})" for a, v in out["profile_vs_iwm"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
