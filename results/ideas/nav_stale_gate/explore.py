"""What deciding on a stale NAV costs the core book, and what holding a repeated NAV costs. Research only.

    python3 results/ideas/nav_stale_gate/explore.py --data <a data/cef directory>

WHY (2026-11-19). The core's stale-NAV gate (quantt/session/nav_gate.py) needs CEFConnect to
tell a stale Yahoo NAV from a genuine repeat. CEFConnect has served a block page since about
2026-10-21, and the gate runs in `report` mode: it writes "would defer" and the book decides
anyway. On the VM's 21 plans from 2026-10-21 to 2026-11-19, 111 of 273 name-days had a NAV
dated D equal to the cent to the previous NAV [V, read from plan.json's nav_gate block]. The
team lead asked for a gate that needs no second source. The only such rule available is the
one the gate already has for an unverified name at its final check: HOLD the name (no trade
in it that session). This script measures both sides of that trade-off on the canonical
harness, changing nothing in the sleeve, the spec or data/.

FIXED BEFORE ANY RETURN WAS READ
  Book      `build_targets(source=(prices, nav))` then `band(T, BAND_WIDTH)`, scripts/cef/
            band_frontier.py, unchanged; spec through scripts/cef/spec.py; scored by
            scripts/research/harness.evaluate (decide t, fill t+1 close, earn from t+2).
  Repeat    name-day whose NAV dated t equals its previous NAV row to half a cent, on the
            panel as it stands today (Yahoo corrects stale rows later, so these are the
            GENUINE repeats). g = their share of name-days from the book's first session.
  Stale     the live share of repeats, 111/273, less g, is the share of name-days assumed to
            carry a stale copy: q = 111/273 - g. Drawn at random by name-day (seeded), 200
            draws. A stale name-day's target is the target the same code builds from the NAV
            panel lagged one session (every NAV row moved one session later): the signal a
            stale row gives. Approximation, stated: the lag shifts the whole history, where
            a real stale copy is only the newest row; and the mixed target frame is not
            re-normalised across names.
  Variants  TRUE        every NAV current (what the backtests assume).
            STALE       stale name-days decide on the lagged target (what the book does now).
            ALL_LAG     every name-day lagged: the bound.
            HOLD_TRUE   on the true panel, a name is not traded on a genuine-repeat day (its
                        held weight stays the previous day's): the cost of the hold rule's
                        false alarms alone.
            HOLD_STALE  stale and genuine-repeat name-days are both held (a stale copy always
                        shows as a repeat), every other name-day trades on its true target:
                        what the hold rule would deliver.
  Report    gross Sharpe, return, vol, worst drawdown, sum of absolute weight changes a year,
            halves, eras 2013-15 / 2016-19 / 2020-22 / 2023-26; for the drawn variants the
            mean and the 5th-95th percentile across draws; HOLD_STALE less STALE per draw.
  Expect    staleness costs a little (a one-session NAV move is small against a 4.8% band);
            holding costs turnover-linked return on a fifth of name-days. Which is larger is
            the question.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore as _explore  # noqa: E402,F401  turns numexpr off

assert pd.get_option("compute.use_numexpr") is False
LIVE_REPEATS, LIVE_NAME_DAYS = 111, 273      # VM plan.json nav_gate blocks, 2026-10-21..2026-11-19 [V]
DRAWS, SEED = 200, 20261119
ERAS = {"2013-15": ("2013", "2015"), "2016-19": ("2016", "2019"), "2020-22": ("2020", "2022"), "2023-26": ("2023", "2026")}


def stats(p: pd.Series) -> dict:
    p = p.dropna()
    sd = p.std()
    sr = p.mean() / sd * 252 ** 0.5 if sd > 0 else float("nan")
    eq = p.cumsum()
    return {"sharpe": round(float(sr), 3), "t": round(float(sr * (len(p) / 252) ** 0.5), 2),
            "ret": round(float(p.mean() * 252), 5), "vol": round(float(sd * 252 ** 0.5), 5),
            "maxdd": round(float((eq - eq.cummax()).min()), 5), "n": int(len(p))}


def hold(H: pd.DataFrame, flag: pd.DataFrame) -> pd.DataFrame:
    """H with each flagged name-day carried from the previous session's (already held) value."""
    out = H.to_numpy(dtype=float, copy=True)
    f = flag.reindex(index=H.index, columns=H.columns).fillna(False).to_numpy()
    for i in range(1, len(out)):
        out[i] = np.where(f[i], out[i - 1], out[i])
    return pd.DataFrame(out, index=H.index, columns=H.columns)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("results.json"))
    a = ap.parse_args(argv)
    from scripts.cef import band_frontier as bf
    from scripts.research import harness
    src = (a.data / "cef_prices.parquet", a.data / "cef_nav.parquet")
    T, R = bf.build_targets(source=src)
    nav_long = pd.read_parquet(src[1])
    last_nav = pd.to_datetime(nav_long["date"]).max().date()
    # the NAV panel lagged one session: each fund's row dated t carries its previous row's NAV
    lag = nav_long.sort_values(["ticker", "date"]).copy()
    lag["nav"] = lag.groupby("ticker")["nav"].shift(1)
    lag = lag.dropna(subset=["nav"])
    tmp = Path(os.environ["TMPDIR"]) / "nav_stale_gate"
    tmp.mkdir(exist_ok=True)
    lag.to_parquet(tmp / "cef_nav_lag1.parquet", index=False)
    TL, RL = bf.build_targets(source=(src[0], tmp / "cef_nav_lag1.parquet"))
    # Returns must not depend on NAV. The lagged panel has no row on each fund's first NAV date,
    # so that fund's first return cell is absent there: at most one cell a fund may differ.
    # Every variant is scored on R, the true panel's returns, never on RL.
    differ = ((R.fillna(0) - RL.reindex_like(R).fillna(0)).abs() > 1e-12).sum()
    assert differ.max() <= 1, f"returns differ between the NAV panels beyond a fund's first row: {differ[differ > 1].to_dict()}"
    TL = TL.reindex(index=T.index, columns=T.columns)
    H0 = bf.band(T, bf.BAND_WIDTH)
    first = harness.held(H0).abs().sum(axis=1).gt(0).idxmax()
    S = slice(first, None)
    nav = nav_long.pivot(index="date", columns="ticker", values="nav").sort_index()
    nav.index = pd.to_datetime(nav.index)
    prev = nav.ffill().shift(1)
    rep = ((nav - prev).abs() <= 0.005) & nav.notna()
    rep = rep.reindex(index=T.index, columns=T.columns).fillna(False)
    in_book = T.loc[S].notna() & (T.loc[S] != 0)
    g = float(rep.loc[S][in_book].sum().sum() / in_book.sum().sum())
    q = LIVE_REPEATS / LIVE_NAME_DAYS - g
    if not 0 < q < 1:
        raise RuntimeError(f"stale share q = {q:.3f} from live {LIVE_REPEATS}/{LIVE_NAME_DAYS} and genuine {g:.3f} is not a share")

    def score(H: pd.DataFrame) -> dict:
        ev = harness.evaluate(H, R)
        p = ev["pnl"].loc[S]
        W = harness.held(H).loc[S]
        n = len(p)
        r = stats(p)
        r["turn"] = round(float(W.diff().abs().sum(axis=1).sum() / (n / 252)), 2)
        r["halves"] = [stats(p.iloc[: n // 2])["sharpe"], stats(p.iloc[n // 2:])["sharpe"]]
        r["eras"] = {k: stats(p.loc[lo:hi])["sharpe"] for k, (lo, hi) in ERAS.items()}
        return r

    out = {"panel_last_nav": str(last_nav), "first_session": str(first.date()), "names": int(T.shape[1]),
           "genuine_repeat_share": round(g, 4), "live_repeat_share": round(LIVE_REPEATS / LIVE_NAME_DAYS, 4),
           "assumed_stale_share": round(q, 4), "draws": DRAWS, "variants": {}}
    out["variants"]["TRUE"] = score(H0)
    out["variants"]["ALL_LAG"] = score(bf.band(TL, bf.BAND_WIDTH))
    out["variants"]["HOLD_TRUE"] = score(hold(H0, rep))
    rng = np.random.default_rng(SEED)
    keys = ("sharpe", "ret", "vol", "maxdd", "turn")
    acc = {"STALE": [], "HOLD_STALE": [], "HOLD_STALE_less_STALE": []}
    for _ in range(DRAWS):
        m = pd.DataFrame(rng.random(T.shape) < q, index=T.index, columns=T.columns)
        Hs = bf.band(T.where(~m, TL), bf.BAND_WIDTH)
        s1 = score(Hs)
        s2 = score(hold(H0, m | rep))
        acc["STALE"].append([s1[k] for k in keys])
        acc["HOLD_STALE"].append([s2[k] for k in keys])
        acc["HOLD_STALE_less_STALE"].append([s2[k] - s1[k] for k in keys])
    for name, rows in acc.items():
        A = np.array(rows)
        out["variants"][name] = {k: {"mean": round(float(A[:, j].mean()), 5), "p05": round(float(np.percentile(A[:, j], 5)), 5),
                                     "p95": round(float(np.percentile(A[:, j], 95)), 5)} for j, k in enumerate(keys)}
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "variants"}, indent=1))
    for k in ("TRUE", "ALL_LAG", "HOLD_TRUE"):
        v = out["variants"][k]
        print(f"{k:11s} SR {v['sharpe']:.2f} (t {v['t']:.2f}) ret {v['ret']:.2%} vol {v['vol']:.2%} dd {v['maxdd']:.1%} turn {v['turn']:.1f} halves {v['halves']} eras {v['eras']}")
    for k in ("STALE", "HOLD_STALE", "HOLD_STALE_less_STALE"):
        v = out["variants"][k]
        print(f"{k:22s} SR {v['sharpe']['mean']:+.3f} [{v['sharpe']['p05']:+.3f}, {v['sharpe']['p95']:+.3f}]  ret {v['ret']['mean']:+.3%} "
              f"[{v['ret']['p05']:+.3%}, {v['ret']['p95']:+.3%}]  turn {v['turn']['mean']:+.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
