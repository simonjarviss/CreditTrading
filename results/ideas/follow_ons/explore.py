"""Explore: follow-on share offerings. Does the issuer's share recover after pricing, and drift down later?

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_sdc_follow_ons.py
    python3 results/ideas/follow_ons/explore.py

FIXED BEFORE ANY RETURN WAS READ (2026-11-15). Only counts had been looked at: 13,491 US
public follow-ons since 2000 matched to a CRSP common share (about 500 a year); 8,044 launched
before their issue date (marketed) and 5,447 on it (overnight); median proceeds fell from
about $100M to $25M after 2022; median proceeds are 13-15% of market value.

  EVENT     an SDC follow-on (ipo = 'No', US, market 'U.S. Public'), one per issuer and
            issue date. D = SDC's issue date, which is the pricing date.
  DATING    SDC's issue date can be the evening before the first session the new shares
            trade (Corwin 2003 corrects it with volume). So nothing is decided on D: the
            decision row is D+1, by whose close the offering is public on either reading.
  ELIGIBLE  at the close of D+1: price >= $2, 21-session average dollar volume >= $500,000.
  TWO BOOKS, each name a fixed 10% of the book with IWM the same size the other way,
  scaled down pro rata when a side would pass 50%:
    REBOUND  long. Decided at D+1, filled at the close of D+2, earns D+3 through D+7.
    DRIFT    short. Earns D+8 through D+47 (forty sessions).
  EXPECTED SIGNS, written down first: REBOUND positive (the offering is sold at a discount
  and the price pressure should lift once it is placed; the catalogue's K6 card quotes a
  recovery "within 7 sessions" for marketed deals and a weaker one for overnight deals);
  DRIFT positive for the short (issuers sell when their shares are dear). Either may fail.
  CONTROLS  the REBOUND book on the same events moved 30 sessions earlier and 30 later.
  DESCRIPTIVE ONLY, never used to choose: the event-time profile against IWM, D-10 to
            D+50; each book by era; REBOUND for marketed and overnight deals, for offerings
            above and below 13% of market value, and on $5M-a-day names.

ALIGNMENT. `harness.evaluate` earns row t's weights on session t+2. A weight that should
earn session s is written on row s-2. REBOUND's first weight row is D+1, the decision row
itself; price and volume are read on that row and nothing later.

NOT MODELLED: borrow on the DRIFT short, and Regulation M Rule 105 (a short in the five
days before pricing bars buying in the offering; this book never buys in an offering).
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
BOOKS = {"rebound": (3, 7, 1.0), "drift": (8, 47, -1.0)}      # earning sessions D+a .. D+b, side
ERAS = {"2000-07": ("2000", "2007"), "2008-12": ("2008", "2012"), "2013-17": ("2013", "2017"),
        "2018-22": ("2018", "2022"), "2023-25": ("2023", "2025")}


def load():
    ev = pd.read_parquet(RES / "sdc_follow_ons.parquet")
    px = pd.read_parquet(RES / "crsp_follow_on_daily.parquet")
    yf = pd.read_parquet(RES / "yf_daily.parquet")
    for c in ("issue_date", "launch", "filed"):
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
    e = ev[ev["issue_date"].isin(sessions) & ev["permno"].isin(prc.columns)].copy()
    e["d"] = sessions.get_indexer(e["issue_date"])
    e = e[e["d"] + 1 < len(sessions)]
    cols = prc.columns.get_indexer(e["permno"])
    row = e["d"].to_numpy() + 1                        # the decision row, D+1
    P, A = prc.to_numpy()[row, cols], adv.to_numpy()[row, cols]
    e["ok"] = (P >= MIN_PRICE) & (A >= MIN_ADV)
    e["adv_dec"] = A
    e["overnight"] = e["launch"] == e["issue_date"]
    e["rel_size"] = e["proceeds_musd"] * 1e3 / e["cap_issue_k"]
    return e


def book(e, which, sessions, columns, *, shift=0):
    L = harness.EXEC_LAG
    a, b, side = BOOKS[which]
    W = np.zeros((len(sessions), len(columns)))
    cpos = pd.Index(columns).get_indexer(e["permno"])
    n = 0
    for d, c, ok in zip(e["d"].to_numpy(), cpos, e["ok"].to_numpy()):
        if not ok:
            continue
        lo, hi = d + a - L + shift, min(d + b - L + shift, len(sessions) - 1)
        # No weight before the decision row of the real event when unshifted; a shifted
        # control keeps the real event's eligibility flag and only moves the window.
        if hi < lo or lo < 0 or (shift == 0 and lo < d + 1):
            continue
        W[lo:hi + 1, c] += side * UNIT
        n += 1
    tot = np.abs(W).sum(axis=1)
    W *= np.where(tot > SIDE_CAP, SIDE_CAP / np.where(tot > 0, tot, 1.0), 1.0)[:, None]
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
                 "share_of_days_at_cap": float((gross >= SIDE_CAP - 1e-9).mean()),
                 "turnover_per_year": float(res["turn"])}


def profile(e, ret, iwm, lo, hi) -> dict:
    rel = ret.sub(iwm, axis=0).to_numpy()
    cpos = ret.columns.get_indexer(e["permno"])
    month = ret.index.to_period("M")
    out = {}
    for k in range(lo, hi + 1):
        rows = e["d"].to_numpy() + k
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
    e = place(ev, sessions, prc, adv)
    out = {"panel_first_date": str(sessions[0].date()), "panel_last_date": str(sessions[-1].date()),
           "fixed": {"min_price": MIN_PRICE, "min_adv": MIN_ADV, "unit": UNIT, "side_cap": SIDE_CAP, "books": BOOKS},
           "counts": {"placed": int(len(e)), "eligible": int(e["ok"].sum()),
                      "eligible_overnight": int((e["ok"] & e["overnight"]).sum()),
                      "eligible_marketed": int((e["ok"] & ~e["overnight"]).sum())}}
    print(json.dumps(out["counts"], indent=1))
    cuts = {"marketed": e[~e["overnight"]], "overnight": e[e["overnight"]],
            "13% of market value and over": e[e["rel_size"] >= 0.13], "under 13%": e[e["rel_size"] < 0.13],
            "$5M a day": e[e["adv_dec"] >= 5e6], "$20M a day": e[e["adv_dec"] >= 2e7]}
    for which in BOOKS:
        pnl, meta = run(e, which, sessions, R)
        controls = {}
        if which == "rebound":
            controls = {"same events, 30 sessions earlier": run(e, which, sessions, R, shift=-30)[0],
                        "same events, 30 sessions later": run(e, which, sessions, R, shift=30)[0]}
        res = explore.summarise(pnl, controls=controls, extra=meta)
        res["by_era"] = {k: explore.stats(pnl.loc[a:b]) for k, (a, b) in ERAS.items()}
        res["cuts"] = {}
        for k, sub in cuts.items():
            p, m = run(sub, which, sessions, R)
            res["cuts"][k] = {**explore.stats(p), "events_traded": m["events_traded"]}
        out[which] = res
        d = HERE / which
        d.mkdir(exist_ok=True)
        explore.write(d, res, pnl, controls=controls,
                      title=f"Follow-on offerings, {which}: 10% a name vs IWM; shift(2), gross; to {out['panel_last_date']}")
        print(f"\n== {which}: events {meta['events_traded']:,} ({meta['events_per_year']:.0f}/yr) | invested {meta['share_of_days_invested']:.0%} | at cap {meta['share_of_days_at_cap']:.0%} | "
              f"names held {meta['mean_names_held']:.1f} | missing-return name-days {meta['held_name_days_with_no_return']} of {meta['held_name_days']}")
        print(explore.table(res))
        print("  by era:", " | ".join(f"{b}: SR {v['sharpe']:.2f} t {v['t']:.1f}" for b, v in res["by_era"].items()))
        print("  cuts:", " | ".join(f"{b}: SR {v['sharpe']:.2f} t {v['t']:.1f} n {v['events_traded']}" for b, v in res["cuts"].items()))
    for label, sub in (("all eligible", e[e["ok"]]), ("marketed", e[e["ok"] & ~e["overnight"]]), ("overnight", e[e["ok"] & e["overnight"]])):
        out[f"profile, {label}"] = profile(sub, ret, iwm, -10, 50)
        print(f"\nprofile, {label} (bp, t by month):", " ".join(f"{a}:{v['mean_bp']:+.0f}({v['t_by_month']:+.1f})" for a, v in out[f"profile, {label}"].items()))
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
