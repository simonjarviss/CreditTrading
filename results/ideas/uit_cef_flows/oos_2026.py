"""Out of sample: the unit-trust termination rule on 2026, a year the idea's data never held. Research only.

    python3 results/ideas/uit_cef_flows/oos_2026.py [--refetch]

WHY. The idea (card 2026-11-16_uit_cef_flows.md) was measured on CRSP to 2025-12-31, and its
entry at T's own close was chosen after seeing the daily profile. The rule was then written
down in shadow/signals/uit_termination.py (commit 96b05ff, 2026-11-18) before any 2026 price
was fetched. This script is the first read of 2026: every trust in the committed calendar
whose termination session T fell in 2026 with T+3 already past. The team lead asked for it on
2026-11-19.

FIXED HERE BEFORE ANY 2026 RETURN IS READ
  Calendar  shadow/universes/uit_terminations_v1.csv as committed (First Trust and Guggenheim
            closed-end trusts, from prospectuses filed more than 30 days before T).
  Prices    Yahoo daily for every calendar fund with a 2026 termination, and PCEF: close and
            volume for the rule's floors, adjusted close for total returns. Cached under
            ~/quantt_research/uit_cef_flows/. Yahoo serves no dead tickers under their old
            names: a fund with no price is listed and cannot be an event (the shadow book
            could not hold it either), which biases toward survivors and is stated.
  Events    (fund, T) is ELIGIBLE exactly when the committed signal would buy it: the fund is
            in `_targets(T-1, px, <that T's calendar rows>, None)` (floors read at T-10, a
            close on T-1). Nothing about the rule is re-implemented here.
  Measure   per event, total return: R13 = close(T+3)/close(T) - 1 (the trade), R1 =
            close(T+1)/close(T) - 1, PRE = close(T)/close(T-10) - 1 (the selling window,
            sessions T-9..T), LATE = close(T+4)/close(T+1) - 1 (the same trade a day late).
            Each less (a) CONTROL: the equal-weighted mean, over the same sessions, of calendar
            funds with no termination session of their own within 15 sessions either side of
            T; (b) PCEF.
  Test      events collapsed to ONE observation per termination session (the mean across that
            session's funds): mean, median, share of sessions positive, t across sessions.
            The idea's in-sample figures to beat: R13 less the CEF market +33bp with 77% of
            sessions positive; PRE about -40bp.
  Books     the two committed shadow signals (`all_events`, `big_sale`) run for every 2026
            session and scored decide t, fill t+1 close, earn from t+2: total return over the
            period, sessions invested, and the mean daily return on invested sessions. About
            ten months: no Sharpe is claimed.
  Not here  bid-ask (Yahoo has no closing quotes): whether the T close can be had is still the
            open condition; only paper fills can show it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore as _explore  # noqa: E402,F401
from shadow.signals import uit_termination as sig  # noqa: E402

OUT = Path.home() / "quantt_research" / "uit_cef_flows"
CACHE = OUT / "oos_2026_px.parquet"
START, YEAR = "2025-10-01", 2026
CONTROL_GAP = 15          # sessions either side of T with no termination of the fund's own


def fetch(symbols: list) -> pd.DataFrame:
    import yfinance as yf
    rows, none = [], []
    for i in range(0, len(symbols), 40):
        batch = symbols[i:i + 40]
        d = yf.download(batch, start=START, auto_adjust=False, progress=False, threads=False, group_by="ticker")
        for s in batch:
            try:
                g = d[s].dropna(subset=["Close"])
            except KeyError:
                g = pd.DataFrame()
            if g.empty:
                none.append(s)
                continue
            rows.append(pd.DataFrame({"date": g.index.tz_localize(None).normalize(), "symbol": s, "close": g["Close"].to_numpy(),
                                      "adj": g["Adj Close"].to_numpy(), "volume": g["Volume"].to_numpy()}))
        time.sleep(1.0)
    df = pd.concat(rows, ignore_index=True)
    df.attrs["none"] = none
    return df


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true")
    a = ap.parse_args(argv)
    cal = sig.read_calendar(sig._csv(sig.CALENDAR))
    for r in cal:
        r["T"] = sig.termination_session(r["termination"])
    cal26 = [r for r in cal if r["T"].year == YEAR]
    funds = sorted({r["symbol"] for r in cal26})
    OUT.mkdir(parents=True, exist_ok=True)
    if a.refetch or not CACHE.exists():
        df = fetch(funds + ["PCEF"])
        df.to_parquet(CACHE, index=False)
    px = pd.read_parquet(CACHE)
    px["date"] = pd.to_datetime(px["date"])
    # FIX AFTER THE FIRST RUN (2026-11-19, 12:20 New York): Yahoo returns a row for the session
    # in progress, so the first run's last day was an intraday price. Rows after the last
    # CLOSED session are dropped; the first run's figures moved only in the books' last day.
    from shadow.fetch import common as _common
    px = px[px["date"].dt.date <= _common.last_closed_date()]
    last = px["date"].max().date()
    no_price = sorted(set(funds) - set(px["symbol"]))
    A = px.pivot(index="date", columns="symbol", values="adj").sort_index()
    days = [d.date() for d in A.index]
    pos = {d: i for i, d in enumerate(days)}
    panel = px[["date", "symbol", "close", "volume"]]
    own_T = {}
    for r in cal:
        own_T.setdefault(r["symbol"], set()).add(r["T"])
    Ts = sorted({r["T"] for r in cal26 if r["T"] in pos and pos[r["T"]] + 4 < len(days) and pos[r["T"]] >= 10})
    skipped_T = sorted({r["T"] for r in cal26} - set(Ts))

    def ret(sym, i0, i1):
        v0, v1 = A[sym].iloc[i0], A[sym].iloc[i1]
        return float(v1 / v0 - 1.0) if np.isfinite(v0) and np.isfinite(v1) and v0 > 0 else np.nan

    ev = []
    for T in Ts:
        rows_T = [r for r in cal if r["T"] == T]
        elig = sig._targets(sig.previous_trading_day(T), panel, rows_T, None)
        i = pos[T]
        ctrl = [s for s in A.columns if s != "PCEF" and all(abs(pos.get(t, 10 ** 6) - i) > CONTROL_GAP for t in own_T.get(s, ()))]
        def bench(i0, i1, names):
            v = [ret(s, i0, i1) for s in names]
            v = [x for x in v if np.isfinite(x)]
            return float(np.mean(v)) if v else np.nan
        wins = {"R13": (i, i + 3), "R1": (i, i + 1), "PRE": (i - 10, i), "LATE": (i + 1, i + 4)}
        # PLACEBOS, NOT PRE-SPECIFIED (added after the first run, because the result was better
        # than in sample and a result that good is assumed wrong first): the same funds over a
        # three-session window 20 sessions later and 30 sessions earlier, where nothing is sold.
        if i + 23 < len(days):
            wins["PLACEBO_AFTER"] = (i + 20, i + 23)
        if i - 30 >= 0:
            wins["PLACEBO_BEFORE"] = (i - 30, i - 27)
        cb = {k: bench(*w, ctrl) for k, w in wins.items()}
        pb = {k: ret("PCEF", *w) for k, w in wins.items()}
        n_held = len({r["symbol"] for r in rows_T})
        for s in elig.index:
            e = {"T": T, "symbol": s, "n_ctrl": len(ctrl), "n_calendar_funds": n_held}
            for k, w in wins.items():
                x = ret(s, *w)
                e[k], e[k + "_ctrl"], e[k + "_pcef"] = x, x - cb[k], x - pb[k]
            ev.append(e)
    E = pd.DataFrame(ev)
    by_T = E.groupby("T").mean(numeric_only=True)

    def line(col):
        v = by_T[col].dropna()
        return {"mean_bp": round(float(v.mean() * 1e4), 1), "median_bp": round(float(v.median() * 1e4), 1),
                "share_positive": round(float((v > 0).mean()), 3), "t": round(float(v.mean() / (v.std() / len(v) ** 0.5)), 2),
                "sessions": int(len(v)), "per_event_mean_bp": round(float(E[col].mean() * 1e4), 1),
                "per_event_median_bp": round(float(E[col].median() * 1e4), 1), "events": int(E[col].notna().sum())}

    out = {"price_last_date": str(last), "calendar_trusts_2026": len({r["trust_key"] for r in cal26}),
           "termination_sessions_2026_scored": len(Ts), "first_T": str(Ts[0]), "last_T": str(Ts[-1]),
           "termination_sessions_not_scored": [str(t) for t in skipped_T],
           "calendar_funds_2026": len(funds), "funds_with_no_yahoo_price": no_price,
           "eligible_events": int(len(E)), "eligible_funds": int(E["symbol"].nunique()),
           "median_eligible_per_session": float(E.groupby("T").size().median()),
           "results": {k: line(k) for k in ("R13_ctrl", "R13_pcef", "R13", "R1_ctrl", "PRE_ctrl", "PRE_pcef", "LATE_ctrl",
                                                  "PLACEBO_AFTER_ctrl", "PLACEBO_BEFORE_ctrl")}}
    # NOT PRE-SPECIFIED: without the ten best sessions, and the share of the total from them
    v = by_T["R13_ctrl"].dropna().sort_values()
    out["R13_ctrl_without_10_best_sessions_bp"] = round(float(v.iloc[:-10].mean() * 1e4), 1)
    out["control_funds_median"] = float(E.groupby("T")["n_ctrl"].first().median())
    # by half of the year, and the months, on the primary line
    half = by_T["R13_ctrl"].dropna()
    mid = len(half) // 2
    out["R13_ctrl_halves_bp"] = [round(float(half.iloc[:mid].mean() * 1e4), 1), round(float(half.iloc[mid:].mean() * 1e4), 1)]
    m = half.groupby([t.month for t in half.index]).mean()
    out["R13_ctrl_by_month_bp"] = {int(k): round(float(v * 1e4), 1) for k, v in m.items()}
    # the two committed books, decide t, fill t+1 close, earn from t+2
    R = A.pct_change(fill_method=None)
    sess = [d for d in days if d.year == YEAR or d >= dt.date(YEAR - 1, 12, 24)]
    for name, fn in (("all_events", sig.all_events), ("big_sale", sig.big_sale)):
        W = {}
        for s in sess:
            if not sig.is_trading_day(s):
                continue
            w = fn(s, {sig.PX: panel})
            W[s] = w
        pnl, gross = [], []
        for j, d in enumerate(days):
            if j < 2 or days[j - 2] not in W:
                continue
            w = W[days[j - 2]]
            r = R.iloc[j].reindex(w.index)
            if len(w) and r.isna().any():
                r = r.fillna(np.nan)
            p = float((w * r).sum(skipna=False)) if len(w) else 0.0
            pnl.append((d, p)); gross.append(float(w.sum()) if len(w) else 0.0)
        P = pd.Series(dict(pnl))
        G = pd.Series(gross, index=P.index)
        inv = G > 0
        out[f"book_{name}"] = {"sessions": int(len(P)), "sessions_invested": int(inv.sum()), "sessions_unmeasured": int(P.isna().sum()),
                               "total_return": round(float(P.sum(skipna=True)), 5), "mean_gross_when_invested": round(float(G[inv].mean()), 3) if inv.any() else None,
                               "mean_daily_bp_when_invested": round(float(P[inv].mean() * 1e4), 2) if inv.any() else None,
                               "share_positive_days_when_invested": round(float((P[inv] > 0).mean()), 3) if inv.any() else None,
                               "worst_day_bp": round(float(P.min() * 1e4), 1), "first": str(P.index[0]), "last": str(P.index[-1])}
    Path(__file__).with_name("oos_2026.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
