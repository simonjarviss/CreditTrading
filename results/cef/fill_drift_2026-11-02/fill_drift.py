"""Paper fill drift against 15:50 ET information, cef account (measured 2026-11-02).

Report only, zero trials. This measures our own fills; it does not test a strategy. Note:
`results/cef/FILL_DRIFT_2026-11-02.md`; output of record, aggregates only:
`results/cef/fill_drift_2026-11-02/aggregates_2026-11-02.json`.

WHY IT EXISTS. The live attribution (`results/cef/LIVE_ATTRIBUTION_2026-11-02.md`) found the fill line
(each fill against that day's close) at -$308.71, -5.5bp. It was concentrated after 10-13 (-9.5bp) and
in munis. On paper the plan is decided in the evening and sent as market `day` orders at about 15:52 ET
(CLAUDE.md hard rule 3, `execution.mode = late_market`). So the fill line mixes two things, the spread
paid and the market's move between 15:50 and the close. This splits them, against SIP quotes, and asks
whether the move before 15:50 predicts either part.

READ-ONLY. GETs only: the account's FILL activities, SIP quotes, SIP raw daily bars. The keys come from
the file named by QUANTT_ENV_FILE, through `quantt.broker.alpaca_probe`'s own loader. They are never
printed, and there is no default file: unset QUANTT_ENV_FILE raises. No order code is imported.

PUBLIC REPOSITORY. Per-fill rows are account data. They are written to `<out-dir>/private/` only, and
both outputs are refused anywhere git could see or under data/ (live_attribution's own guards). The
committed JSON holds aggregates only: no account, order or activity id, and no per-fill row.

INPUTS. `--cache-dir` is a `live_attribution.py fetch` cache, kept outside the repository, and its
fills.json is the base set. `--extra-from`/`--extra-through` add FILL activities read now, for later days
(the 2026-11-02 run added 10-31..11-02).

SIGNS AND UNITS. s = +1 buy, -1 sell or sell_short. Every cost is in bp of the 15:50 mid, positive =
worse for us:
  A  1550mid->fill  = s*(fill - mid1550)/mid1550
  B  fill vs close  = s*(fill - close)/mid1550        (the attribution's fill line, as a cost)
  C  1550mid->close = s*(close - mid1550)/mid1550     (the market's move after 15:50, in our direction)
  A = B + C exactly (asserted). Also E = fill vs the fill-time mid (the effective half-spread) and
  D = 1550 mid -> fill-time mid, so A = D + E.
Aggregates are notional-weighted (sum of cost$ / sum of notional at the 15:50 mid).

QUOTES. The last SIP quote at or before 15:50:00 ET, and at or before each fill's transaction time,
searched over the 6 hours before. A missing quote, close or previous close raises; nothing is filled in.

PERIOD SPLIT. `--split-after` is required, with no default (H14). On 2026-11-02 it was 2026-10-12, the
EOD equity peak that live_attribution measured at run time. Pass that date to reproduce.

Reproduce (outside the repository for both directories):
  QUANTT_ENV_FILE=<the cef key file> python3 results/cef/fill_drift_2026-11-02/fill_drift.py \\
      --cache-dir <live_attribution cache, through 2026-10-30> --extra-from 2026-10-31 \\
      --extra-through 2026-11-02 --split-after 2026-10-12 --out-dir <outside the repo>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from quantt.broker import alpaca_probe as ap  # noqa: E402  (read-only GET helpers and the key loader)
from scripts.cef.live_attribution import _refuse_data_dir, _refuse_git_visible  # noqa: E402

NY, UTC = ZoneInfo("America/New_York"), dt.timezone.utc
DATA_API = "https://data.alpaca.markets"
SIGN = {"buy": 1, "sell": -1, "sell_short": -1}
COLS = ["A_1550mid_to_fill", "B_fill_vs_close", "C_1550mid_to_close", "D_1550mid_to_fillmid", "E_fill_vs_fillmid"]
OUT_NAMES = ["aggregates.json", "private/fills_with_quotes.csv"]


def _session():
    envf = os.environ.get("QUANTT_ENV_FILE")
    if not envf:
        raise SystemExit("QUANTT_ENV_FILE is not set: name the cef key file (there is no default)")
    k, s = ap.load_credentials("cef", ap.read_env_file(Path(envf)))
    return ap._session(k, s)


def dget(sess, path, params):
    for attempt in range(6):
        r = sess.get(DATA_API + path, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(2 + 3 * attempt)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"GET {path} -> {r.status_code}: {r.text[:200]}")
        return r.json()
    raise RuntimeError(f"GET {path}: still 429 after retries")


def load_fills(sess, cache_dir: Path, extra_from, extra_through):
    fills = json.loads((cache_dir / "fills.json").read_text())
    seen = {f["id"] for f in fills}
    if extra_from is not None:
        for day in pd.bdate_range(extra_from, extra_through):
            q, tok = f"/v2/account/activities/FILL?date={day.date()}&direction=asc&page_size=100", None
            while True:
                r = ap._get(sess, q + (f"&page_token={tok}" if tok else ""))
                new = [a for a in r if a["id"] not in seen]
                fills += new
                seen |= {a["id"] for a in new}
                if len(r) < 100:
                    break
                tok = r[-1]["id"]
    rows = []
    for f in fills:
        t = pd.Timestamp(f["transaction_time"]).tz_convert(UTC)
        rows.append(dict(symbol=f["symbol"], side=SIGN[f["side"]], qty=int(float(f["qty"])),
                         px=float(f["price"]), t=t, date=t.tz_convert(NY).date()))
    F = pd.DataFrame(rows)
    if F.empty:
        raise RuntimeError("no fills")
    grp = pd.read_csv(REPO / "data" / "cef" / "cef_universe.csv").set_index("ticker")["grp"].to_dict()
    missing = sorted(set(F.symbol) - set(grp))
    if missing:
        raise RuntimeError(f"no grp for {missing}")
    F["grp"] = F.symbol.map(grp)
    return F


def daily_closes(sess, syms, d0, d1):
    closes, tok = {}, None
    while True:
        p = dict(symbols=",".join(syms), timeframe="1Day", start=f"{d0}T00:00:00Z",
                 end=dt.datetime.combine(d1, dt.time(17, 0), NY).astimezone(UTC).isoformat(),
                 adjustment="raw", feed="sip", limit=10000)
        if tok:
            p["page_token"] = tok
        j = dget(sess, "/v2/stocks/bars", p)
        for sym, bars in j["bars"].items():
            for b in bars:
                closes[(sym, pd.Timestamp(b["t"]).tz_convert(NY).date())] = b["c"]
        tok = j.get("next_page_token")
        if not tok:
            return closes


def last_quote(sess, sym, end_utc):
    j = dget(sess, f"/v2/stocks/{sym}/quotes", dict(start=(end_utc - pd.Timedelta(hours=6)).isoformat(),
             end=end_utc.isoformat(), feed="sip", limit=1, sort="desc"))
    if not j.get("quotes"):
        raise RuntimeError(f"{sym}: no quote in the 6h before {end_utc}")
    q = j["quotes"][0]
    return q["bp"], q["ap"], pd.Timestamp(q["t"])


def tstat(x):
    x = np.asarray(x, float)
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


def measure(sess, F, split_after: pd.Timestamp):
    syms = sorted(F.symbol.unique())
    d0, d1 = min(F.date) - dt.timedelta(days=7), max(F.date)
    closes = daily_closes(sess, syms, d0, d1)
    sessions = sorted({d for _, d in closes})

    def prev_session(d):
        p = [x for x in sessions if x < d]
        if not p:
            raise RuntimeError(f"no session before {d}")
        return p[-1]

    cache, out = {}, []
    for _, r in F.iterrows():
        c = closes.get((r.symbol, r.date))
        pc = closes.get((r.symbol, prev_session(r.date)))
        if c is None or pc is None:
            raise RuntimeError(f"{r.symbol} {r.date}: close {c} prev close {pc}")
        t1550 = pd.Timestamp(dt.datetime.combine(r.date, dt.time(15, 50)), tz=NY)
        if (r.symbol, r.date) not in cache:
            cache[(r.symbol, r.date)] = last_quote(sess, r.symbol, t1550.tz_convert(UTC))
        b0, a0, t0 = cache[(r.symbol, r.date)]
        b1, a1, t1 = last_quote(sess, r.symbol, r.t)
        out.append(dict(r, close=c, prev_close=pc, bid1550=b0, ask1550=a0,
                        q1550_age_s=(t1550 - t0).total_seconds(),
                        bidF=b1, askF=a1, qF_age_s=(r.t - t1).total_seconds()))
    X = pd.DataFrame(out)
    X["mid1550"] = (X.bid1550 + X.ask1550) / 2
    X["midF"] = (X.bidF + X.askF) / 2
    X["crossed1550"] = X.ask1550 <= X.bid1550
    X["crossedF"] = X.askF <= X.bidF
    X["notional"] = X.qty * X.mid1550
    for name, num in (("A_1550mid_to_fill", X.px - X.mid1550), ("B_fill_vs_close", X.px - X.close),
                      ("C_1550mid_to_close", X.close - X.mid1550), ("D_1550mid_to_fillmid", X.midF - X.mid1550),
                      ("E_fill_vs_fillmid", X.px - X.midF)):
        X[name + "_usd"] = X.side * num * X.qty
    assert np.allclose(X.A_1550mid_to_fill_usd, X.B_fill_vs_close_usd + X.C_1550mid_to_close_usd)
    lo, hi = f"to {split_after:%m-%d}", f"{(split_after + pd.Timedelta(days=1)):%m-%d} on"
    X["period"] = np.where(pd.to_datetime(X.date) <= split_after, lo, hi)
    X["side_l"] = np.where(X.side > 0, "buy", "sell")
    # +1: by 15:50 the price had already moved in our trade direction (e.g. buying after a rise).
    X["pre_move_with_us"] = np.sign(X.side * (X.mid1550 - X.prev_close))
    return X, syms


def aggregate(X, syms):
    def agg(g):
        n = g.notional.sum()
        d = {"fills": len(g), "symbol_days": g.groupby(["symbol", "date"]).ngroups, "notional_usd": round(n, 2)}
        for c in COLS:
            d[c + "_bp"] = round(g[c + "_usd"].sum() / n * 1e4, 2)
        return d

    tables = {"all": {"all": agg(X)}}
    for key in ("period", "grp", "side_l"):
        tables[key] = {v: agg(g) for v, g in X.groupby(key)}
    tables["period x grp"] = {f"{a} | {b}": agg(g) for (a, b), g in X.groupby(["period", "grp"])}

    # Predictability, at the symbol-day (order) level: t on symbol-day costs, and on day means
    # (clustered by date).
    SD = X.groupby(["symbol", "date"]).agg(
        notional=("notional", "sum"), side=("side", "first"), pre=("pre_move_with_us", "first"),
        B=("B_fill_vs_close_usd", "sum"), C=("C_1550mid_to_close_usd", "sum"),
        A=("A_1550mid_to_fill_usd", "sum")).reset_index()
    mixed = X.groupby(["symbol", "date"]).side.nunique().gt(1).sum()
    for c in "ABC":
        SD[c + "_bp"] = SD[c] / SD.notional * 1e4
    labels = {1.0: "price moved WITH our side by 15:50 (adverse, e.g. buying after a rise)",
              -1.0: "price moved AGAINST our side by 15:50", 0.0: "no move"}
    pred = {}
    for v, g in SD.groupby("pre"):
        pred[labels[v]] = {
            "symbol_days": len(g), "notional_usd": round(g.notional.sum(), 2),
            "B_fill_vs_close_bp_wtd": round(g.B.sum() / g.notional.sum() * 1e4, 2),
            "C_1550mid_to_close_bp_wtd": round(g.C.sum() / g.notional.sum() * 1e4, 2),
            "B_bp_mean_of_symbol_days": round(g.B_bp.mean(), 2), "B_t_symbol_days": round(tstat(g.B_bp), 2),
            "C_bp_mean_of_symbol_days": round(g.C_bp.mean(), 2), "C_t_symbol_days": round(tstat(g.C_bp), 2)}
    SDd = SD[SD.pre != 0].copy()
    SDd["x"] = SDd.pre
    diff_by_day = SDd.groupby("date").apply(lambda g: pd.Series(
        {c: (g[g.x > 0][c + "_bp"].mean() - g[g.x < 0][c + "_bp"].mean()) for c in "BC"})).dropna()
    pred["difference (with - against), mean over days having both, clustered by date"] = {
        "days": len(diff_by_day), "B_diff_bp": round(diff_by_day.B.mean(), 2), "B_t_days": round(tstat(diff_by_day.B), 2),
        "C_diff_bp": round(diff_by_day.C.mean(), 2), "C_t_days": round(tstat(diff_by_day.C), 2)}
    corr = SDd[["x", "B_bp", "C_bp"]].corr(method="spearman")
    pred["spearman over symbol-days (x vs B, x vs C)"] = {
        "n": len(SDd), "rho_B": round(corr.loc["x", "B_bp"], 3), "rho_C": round(corr.loc["x", "C_bp"], 3)}
    et = X.t.dt.tz_convert(NY)
    meta = {"fills": len(X), "first_date": str(min(X.date)), "last_date": str(max(X.date)),
            "sessions_with_fills": X.date.nunique(), "symbols": len(syms), "symbol_days_with_both_sides": int(mixed),
            "crossed_or_locked_quotes": {"at_1550": int(X.crossed1550.sum()), "at_fill": int(X.crossedF.sum())},
            "quote_age_s": {"1550_median": round(X.q1550_age_s.median(), 1), "1550_max": round(X.q1550_age_s.max(), 1),
                            "fill_median": round(X.qF_age_s.median(), 1), "fill_max": round(X.qF_age_s.max(), 1)},
            # Time of day, not the first and last timestamps: the 2026-11-02 draft printed the first
            # fill's time as "earliest" and was corrected by hand.
            "fill_time_of_day_ET": {"earliest": min(et.dt.time).strftime("%H:%M:%S"),
                                    "latest": max(et.dt.time).strftime("%H:%M:%S"),
                                    "share_in_15:52": round(((et.dt.hour == 15) & (et.dt.minute == 52)).mean(), 3)}}
    return meta, tables, pred


def tie_to_attribution(X, cache_dir: Path) -> dict:
    """B in USD over the cache's own fills: it should equal live_attribution's fill line for the same
    window (-$308.71 for the 2026-10-30 cache, PR #26). Reported, never asserted against that literal."""
    last = max(pd.Timestamp(f["transaction_time"]).tz_convert(NY).date()
               for f in json.loads((cache_dir / "fills.json").read_text()))
    m = X.date <= last
    return {"cache_last_fill_date": str(last), "fills": int(m.sum()),
            "B_fill_vs_close_usd_cost": round(float(X.loc[m, "B_fill_vs_close_usd"].sum()), 2),
            "A_minus_B_minus_C_usd": round(float((X.A_1550mid_to_fill_usd - X.B_fill_vs_close_usd
                                                  - X.C_1550mid_to_close_usd)[m].sum()), 6)}


def main(argv=None) -> int:
    ap_ = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap_.add_argument("--cache-dir", type=Path, required=True)
    ap_.add_argument("--out-dir", type=Path, required=True)
    ap_.add_argument("--split-after", required=True, help="last date of the first period (no default; H14)")
    ap_.add_argument("--extra-from")
    ap_.add_argument("--extra-through")
    a = ap_.parse_args(argv)
    if (a.extra_from is None) != (a.extra_through is None):
        raise SystemExit("--extra-from and --extra-through go together")
    _refuse_data_dir(a.out_dir)
    _refuse_git_visible(a.out_dir, OUT_NAMES)
    sess = _session()
    F = load_fills(sess, a.cache_dir, a.extra_from, a.extra_through)
    X, syms = measure(sess, F, pd.Timestamp(a.split_after))
    meta, tables, pred = aggregate(X, syms)
    meta = {"measured": dt.datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "read-only GETs: FILL activities, SIP quotes, SIP daily bars raw", **meta,
            "ties_to_attribution": tie_to_attribution(X, a.cache_dir)}
    (a.out_dir / "private").mkdir(parents=True, exist_ok=True)
    X.drop(columns=["t"]).to_csv(a.out_dir / "private" / "fills_with_quotes.csv", index=False)
    (a.out_dir / "aggregates.json").write_text(json.dumps(
        {"meta": meta, "definitions": __doc__.split("SIGNS AND UNITS.")[1].split("QUOTES.")[0].strip(),
         "tables": tables, "predictability": pred}, indent=1, default=str))
    print(json.dumps(meta, indent=1, default=str))
    for key, t in tables.items():
        print(f"\n== {key}")
        print(pd.DataFrame(t).T.to_string())
    print("\n== predictability")
    for k, v in pred.items():
        print(" ", k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
