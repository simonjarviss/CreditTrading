"""Checks on the unit-trust termination result, written AFTER explore.py's one run. NOTHING HERE IS PRE-SPECIFIED.

    python3 results/ideas/uit_cef_flows/checks.py        # needs explore.py's events.parquet; no network

WHY EACH CHECK EXISTS (explore.py showed: funds fall about 40bp against the CEF market over
T-9..T, most of it on T-2, T-1 and T, and rise 20bp on T+1 and 11bp on T+2):
  1 MID QUOTES. A trustee selling into the close leaves the closing print near the bid, and a
    return measured from that print includes half a spread that no buyer earns unless the
    buyer's own order fills at that same print. Every window is rescored from the closing
    MIDPOINT (bid+ask)/2 at the start of the window to the closing midpoint at its end, with
    distributions added back (the day's CRSP total return less its price return). Also: where
    the close sat inside the quote at T and at T-40 (0 = bid, 1 = ask).
  2 ENTRY AT T's CLOSE. T is printed in a prospectus two years old, so an order for T's close
    can be decided at T-1 or long before: decide at t, fill at the next close, is kept. The
    pre-specified book waits a further day (decides at T, fills at T+1) and so gives away the
    T+1 return. Books on harness.evaluate, shift(2), earning T+1..T+3 and T+1..T+10, hedged
    with the equal-weighted CEF market and long-only, with the same book on the controls and
    on the T-40 placebo dates.
  3 A FILTER KNOWN IN ADVANCE. explore.py's sale-share terciles use every notice of the trust,
    the final one included, which is filed AFTER T. Here the trust's size is the units sold
    less redeemed in notices FILED at least 30 days before T (asserted), and the one threshold
    is the lane's own gate number, 5% of the fund's nine-session dollar volume T-18..T-10. No
    other threshold was tried.
  4 THE DESK'S OWN FUNDS (tickers in data/cef/cef_prices.parquet, read only) and the two
    sponsors separately.
  5 THE DEPOSIT LEG's +28bp: is it the rebound of a predecessor trust that terminates when the
    successor is deposited? Deposit events split by whether the same fund has a termination
    event within 12 sessions before to 3 after the deposit.
  6 Per-event cost arithmetic: the closing spread at T and at T+3 beside the mid-quote return.
LICENSED ROWS stay in ~/quantt_research/; checks.json holds aggregates only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
sys.path.insert(0, str(HERE))
import sizes as sizes_mod  # noqa: E402

OUT = Path.home() / "quantt_research" / "uit_cef_flows"
PANEL = Path.home() / "quantt_research" / "crsp_cef_daily.parquet"
DESK = REPO.parents[2] / "data" / "cef" / "cef_prices.parquet"          # the main checkout's panel, read only
MIN_PRICE, MIN_ADV = 2.0, 100_000.0
WINS = {"T-9..T": (-9, 0), "T-2..T": (-2, 0), "T+1": (1, 1), "T+1..T+3": (1, 3), "T+1..T+10": (1, 10), "T+2..T+11": (2, 11), "T+4..T+10": (4, 10)}


def cs(x, w, month) -> dict:
    ok = np.isfinite(x)
    x, w, month = x[ok], w[ok], month[ok]
    if len(x) < 30:
        return {"n": int(len(x))}
    m = float((w * x).sum() / w.sum())
    s = pd.Series(w * (x - m)).groupby(month).sum()
    se = float(np.sqrt((s ** 2).sum()) / w.sum())
    return {"n": int(len(x)), "mean_bp": round(m * 1e4, 2), "median_bp": round(float(np.median(x) * 1e4), 2),
            "share_positive": round(float((x > 0).mean()), 4), "t_clustered": round(m / se, 2) if se > 0 else None}


def main() -> int:
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    ret = df.pivot(index="date", columns="permno", values="ret")
    retx = df.pivot(index="date", columns="permno", values="retx")
    prc = df.pivot(index="date", columns="permno", values="prc").abs()
    dv = df.pivot(index="date", columns="permno", values="dollar_volume")
    dates, cols = ret.index, ret.columns
    n = len(dates)
    colpos = {p: i for i, p in enumerate(cols)}
    adv = dv.rolling(21, min_periods=10).mean()
    elig_now = (prc >= MIN_PRICE) & (adv >= MIN_ADV)
    elig = elig_now.shift(1, fill_value=False)             # ALIGNMENT: as explore.py, eligibility read the session before
    mkt = ret.where(elig).mean(axis=1)
    E = pd.read_parquet(OUT / "events.parquet")
    pos, col, w = E["pos"].values, E["col"].values, E["n_series"].values.astype(float)
    assert (E["permno"].map(colpos).values == col).all()
    month = (E["T"].dt.year * 100 + E["T"].dt.month).values
    out: dict = {"note": "nothing in this file was pre-specified", "panel_last_date": str(dates.max().date()), "events": int(len(E))}

    # ---- 1 mid quotes --------------------------------------------------------------------------------------
    q = pd.read_parquet(OUT / "cef_quotes.parquet")
    q["date"] = pd.to_datetime(q["date"])
    q = q[(q["bid"] > 0) & (q["ask"] >= q["bid"])]
    bid = q.pivot(index="date", columns="permno", values="bid").reindex(index=dates, columns=cols)
    ask = q.pivot(index="date", columns="permno", values="ask").reindex(index=dates, columns=cols)
    mid = ((bid + ask) / 2).values
    spr = ((ask - bid) / ((ask + bid) / 2)).values
    loc = ((prc - bid) / (ask - bid).where(ask > bid)).clip(-1, 2).values      # 0 = at the bid, 1 = at the ask
    R, RX = ret.values, retx.values
    miss = np.isnan(R)
    # log of the distribution factor (1+ret)/(1+retx), cumulated: what a holder receives beyond the price change
    dfac = np.where(miss | np.isnan(RX), 0.0, np.log1p(np.where(miss, 0.0, R)) - np.log1p(np.where(np.isnan(RX), 0.0, RX))).cumsum(axis=0)
    logf = np.where(miss, 0.0, np.log1p(np.where(miss, 0.0, R))).cumsum(axis=0)
    nmiss = miss.cumsum(axis=0)
    logm = np.log1p(mkt.fillna(0.0).values).cumsum()

    def close_win(p, c, a, b):
        lo, hi = p + a - 1, p + b
        ok = (lo >= 0) & (hi < n)
        x = np.full(len(p), np.nan)
        x[ok] = np.exp(logf[hi[ok], c[ok]] - logf[lo[ok], c[ok]]) - np.exp(logm[hi[ok]] - logm[lo[ok]])
        gap = np.zeros(len(p), bool)
        gap[ok] = (nmiss[hi[ok], c[ok]] - nmiss[lo[ok], c[ok]]) > 0
        x[gap] = np.nan
        return x

    def mid_win(p, c, a, b):
        lo, hi = p + a - 1, p + b
        ok = (lo >= 0) & (hi < n)
        x = np.full(len(p), np.nan)
        f = mid[hi[ok], c[ok]] / mid[lo[ok], c[ok]] * np.exp(dfac[hi[ok], c[ok]] - dfac[lo[ok], c[ok]])
        x[ok] = f - np.exp(logm[hi[ok]] - logm[lo[ok]])
        return x

    has = E["peer0"].values >= 0
    peers = E[[f"peer{j}" for j in range(5)]].values
    tab = {}
    for k, (a, b) in WINS.items():
        ctl = np.full(len(E), np.nan)
        ctl[has] = np.nanmean(np.column_stack([close_win(pos[has], peers[has, j], a, b) for j in range(5)]), axis=1)
        ctlm = np.full(len(E), np.nan)
        ctlm[has] = np.nanmean(np.column_stack([mid_win(pos[has], peers[has, j], a, b) for j in range(5)]), axis=1)
        tab[k] = {"close_to_close": cs(close_win(pos, col, a, b), w, month), "mid_to_mid": cs(mid_win(pos, col, a, b), w, month),
                  "close_less_control": cs(close_win(pos, col, a, b) - ctl, w, month), "mid_less_control_mid": cs(mid_win(pos, col, a, b) - ctlm, w, month),
                  "placebo_T-40_close": cs(close_win(pos - 40, col, a, b), w, month), "placebo_T-40_mid": cs(mid_win(pos - 40, col, a, b), w, month)}
    out["windows_close_and_mid"] = tab
    where = {}
    for k in (-40, -5, -2, -1, 0, 1, 2, 3):
        p2 = pos + k
        ok = (p2 >= 0) & (p2 < n)
        v = np.full(len(E), np.nan); v[ok] = loc[p2[ok], col[ok]]
        s = np.full(len(E), np.nan); s[ok] = spr[p2[ok], col[ok]]
        where[f"T{k:+d}"] = {"close_position_in_quote_mean": round(float(np.nanmean(v)), 4), "share_at_or_below_bid": round(float((v[np.isfinite(v)] <= 0).mean()), 4),
                             "spread_bp_median": round(float(np.nanmedian(s) * 1e4), 1), "spread_bp_mean": round(float(np.nanmean(s) * 1e4), 1)}
    out["close_inside_quote"] = where

    # ---- 6 worst case: buy at T's closing ASK, sell at the closing BID of the last day, less the market ------
    bidv, askv = bid.values, ask.values

    def cross_win(p, c, a, b):
        lo, hi = p + a - 1, p + b
        ok = (lo >= 0) & (hi < n)
        x = np.full(len(p), np.nan)
        x[ok] = bidv[hi[ok], c[ok]] / askv[lo[ok], c[ok]] * np.exp(dfac[hi[ok], c[ok]] - dfac[lo[ok], c[ok]]) - np.exp(logm[hi[ok]] - logm[lo[ok]])
        return x

    out["buy_at_ask_sell_at_bid"] = {k: cs(cross_win(pos, col, a, b), w, month) for k, (a, b) in WINS.items() if k in ("T+1..T+3", "T+1..T+10", "T+2..T+11")}
    print("ask-to-bid", out["buy_at_ask_sell_at_bid"])

    # ---- 3 a size known before T ---------------------------------------------------------------------------
    T = sizes_mod.closed_end_ciks()
    ce = T[T["cef_share"] > 0.5]
    rows = sizes_mod.rows_for(set(ce["cik"].astype(str)))
    N = []
    for r in rows:
        d = sizes_mod.parse_notice(sizes_mod.read(r[7]))
        if d is not None and not pd.isna(d["fy_end"]):
            N.append({"cik": r[5], "filed": pd.Timestamp(r[6]), **d})
    N = pd.DataFrame(N).drop_duplicates(["cik", "fy_end"], keep="last")
    ntr = T.groupby("cik")["trust_id"].nunique()
    m = ce[["trust_id", "cik", "termination"]].merge(N, on="cik")
    m = m[m["filed"] < m["termination"] - pd.Timedelta(days=30)]
    assert (m["filed"] < m["termination"]).all(), "a notice used for size must be public before T"
    m["net"] = m["sold"] - m["redeemed"]
    pit = (m.groupby("trust_id")["net"].sum().clip(lower=0) / m.groupby("trust_id")["cik"].first().map(ntr)).rename("size_pit")
    H = pd.read_parquet(OUT / "holdings.parquet").merge(ce[["trust_id", "termination", "deposit", "sponsor"]], on="trust_id")
    tk = df[["ticker", "permno", "date"]].dropna(subset=["ticker"]).sort_values("date").rename(columns={"date": "panel_date"})
    H = pd.merge_asof(H.sort_values("deposit"), tk, left_on="deposit", right_on="panel_date", by="ticker", direction="nearest", tolerance=pd.Timedelta(days=10))
    H = H[H["permno"].notna() & (H["termination"] <= dates.max())]
    H["pos"] = dates.searchsorted(H["termination"].values, side="right") - 1
    H = H.merge(pit, on="trust_id", how="left")
    H["sale_pit"] = H["size_pit"] * H["pct"] / 100.0
    g = H.groupby(["permno", "pos"]).agg(sale_pit=("sale_pit", lambda v: v.sum(min_count=1)),
                                         ft=("sponsor", lambda s: (s == "FT").any()), gu=("sponsor", lambda s: (s == "GUGG").any())).reset_index()
    E = E.merge(g, on=["permno", "pos"], how="left")
    E["share_pit"] = E["sale_pit"] / E["vol9"]
    big = (E["share_pit"] >= 0.05).values
    out["size_known_before_T"] = {"events_with_a_notice_filed_30d_before_T": int(E["share_pit"].notna().sum()), "events_at_or_over_5pct": int(big.sum()),
                                  "share_pit_quantiles": {f"p{int(k*100)}": round(float(v), 4) for k, v in E["share_pit"].quantile([.25, .5, .75, .9]).items()}}
    out["buy_at_ask_sell_at_bid_sale_at_or_over_5pct"] = {k: cs(cross_win(pos[big], col[big], a, b), w[big], month[big]) for k, (a, b) in WINS.items() if k in ("T+1..T+3", "T+1..T+10")}
    print("ask-to-bid, big", out["buy_at_ask_sell_at_bid_sale_at_or_over_5pct"])
    for nm, sel in (("sale_at_or_over_5pct_of_nine_session_volume", big), ("sale_under_5pct_or_unknown", ~big)):
        out["size_known_before_T"][nm] = {k: {"close_to_close": cs(close_win(pos[sel], col[sel], a, b), w[sel], month[sel]),
                                              "mid_to_mid": cs(mid_win(pos[sel], col[sel], a, b), w[sel], month[sel])} for k, (a, b) in WINS.items()}

    # ---- 4 the desk's own funds; sponsors ------------------------------------------------------------------
    desk_t = sorted(pd.read_parquet(DESK, columns=["ticker"])["ticker"].unique())
    last_tk = df.sort_values("date").groupby("permno")["ticker"].last()
    desk_permnos = set(last_tk[last_tk.isin(desk_t)].index)
    dsel = E["permno"].isin(desk_permnos).values
    out["desk_funds"] = {"tickers_in_desk_panel": len(desk_t), "matched_in_crsp": len(desk_permnos), "events": int(dsel.sum()),
                         "events_per_year": round(float(dsel.sum() / max(E["T"].dt.year.nunique(), 1)), 1),
                         **{k: {"close_to_close": cs(close_win(pos[dsel], col[dsel], a, b), w[dsel], month[dsel]),
                                "mid_to_mid": cs(mid_win(pos[dsel], col[dsel], a, b), w[dsel], month[dsel])} for k, (a, b) in WINS.items()}}
    out["by_sponsor"] = {}
    for nm, sel in (("first_trust_only", (E["ft"] & ~E["gu"]).values), ("guggenheim_only", (E["gu"] & ~E["ft"]).values)):
        out["by_sponsor"][nm] = {k: cs(close_win(pos[sel], col[sel], a, b), w[sel], month[sel]) for k, (a, b) in WINS.items()}
    eras = {"2013-2015": ("2013", "2015"), "2016-2019": ("2016", "2019"), "2020-2022": ("2020", "2022"), "2023-2025": ("2023", "2025")}
    out["by_era_mid"] = {}
    for nm, (a0, b0) in eras.items():
        sel = ((E["T"] >= a0) & (E["T"] <= b0 + "-12-31")).values
        out["by_era_mid"][nm] = {k: {"close_to_close": cs(close_win(pos[sel], col[sel], a, b), w[sel], month[sel]),
                                     "mid_to_mid": cs(mid_win(pos[sel], col[sel], a, b), w[sel], month[sel])} for k, (a, b) in WINS.items()}

    # ---- 2 books entered at T's close ----------------------------------------------------------------------
    Rf = ret.fillna(0.0)
    ne = elig.sum(axis=1)
    ew = elig.astype(float).div(ne.where(ne > 0), axis=0).fillna(0.0)
    start = dates[max(pos.min() - 1, 0)]
    cut = lambda s: s.loc[start:].iloc[:-harness.EXEC_LAG]

    def book(p_, c_, w_, a, b):
        M = np.zeros((n, len(cols)))
        for pp, cc, ww in zip(p_, c_, w_):
            lo, hi = pp + a, min(pp + b, n - 1)
            if 0 <= lo < n:
                M[lo:hi + 1, cc] += ww
        earn = pd.DataFrame(M, index=dates, columns=cols).where(elig, 0.0)
        tot = earn.sum(axis=1)
        long_ = earn.div(tot.where(tot > 0), axis=0).fillna(0.0)
        short = ew.mul((tot > 0).astype(float), axis=0)
        res = {}
        for nm, W in (("hedged", long_ - short), ("long_only", long_)):
            # ALIGNMENT: W is what is EARNED on session s; the harness holds H two sessions later, so the order for a
            # weight earned at T+1 is decided at T-1 and filled at T's close. T is public two years ahead (explore.py asserts it).
            r = harness.evaluate(W.shift(-harness.EXEC_LAG).fillna(0.0), Rf)
            res[nm] = (cut(r["pnl"]), float(r["turn"]))
        nf = (long_.loc[start:] > 0).sum(axis=1)
        return res, {"funds_per_active_day": round(float(nf.replace(0, np.nan).mean()), 1), "share_of_sessions_active": round(float((nf > 0).mean()), 3),
                     "median_adv_of_held_usd": round(float(adv.where(long_ > 0).loc[start:].stack().median()), 0)}

    books = {}
    hp, hw = np.repeat(pos[has], 5), np.repeat(w[has] / 5, 5)
    for nm, sel, (a, b) in (("T+1..T+3, all events", np.ones(len(E), bool), (1, 3)), ("T+1..T+10, all events", np.ones(len(E), bool), (1, 10)),
                            ("T+1..T+3, sale known before T at or over 5% of volume", big, (1, 3)),
                            ("T+2..T+4, all events (one day late)", np.ones(len(E), bool), (2, 4))):
        bk, info = book(pos[sel], col[sel], w[sel], a, b)
        ctl_sel = has & sel
        cb, _ = book(np.repeat(pos[ctl_sel], 5), peers[ctl_sel].ravel(), np.repeat(w[ctl_sel] / 5, 5), a, b)
        pb, _ = book(pos[sel] - 40, col[sel], w[sel], a, b)
        res = explore.summarise(bk["hedged"][0], controls={"controls, same book": cb["hedged"][0], "same funds 40 sessions earlier": pb["hedged"][0],
                                                           "long-only, no hedge": bk["long_only"][0]},
                                extra={"turnover_per_year": round(bk["hedged"][1], 1), **info})
        books[nm] = res
        print("\n##", nm, info, "turnover", round(bk["hedged"][1], 1)); print(explore.table(res))
    out["books_entered_at_T_close"] = books

    # ---- 5 the deposit leg ---------------------------------------------------------------------------------
    Hd = pd.read_parquet(OUT / "holdings.parquet").merge(ce[["trust_id", "deposit"]], on="trust_id")
    Hd = pd.merge_asof(Hd.sort_values("deposit"), tk, left_on="deposit", right_on="panel_date", by="ticker", direction="nearest", tolerance=pd.Timedelta(days=10))
    Hd = Hd[Hd["permno"].notna()]
    Hd["pos"] = dates.searchsorted(Hd["deposit"].values, side="left")
    Hd = Hd[Hd["pos"] < n - 1]
    dg = Hd.groupby(["permno", "pos"]).agg(n_series=("trust_id", "nunique")).reset_index()
    dg["col"] = dg["permno"].map(colpos)
    dg = dg[elig_now.values[np.clip(dg["pos"].values - 1, 0, n - 1), dg["col"].values]].reset_index(drop=True)
    term_pos = pd.read_parquet(OUT / "events.parquet").groupby("col")["pos"].apply(lambda s: np.sort(s.values)).to_dict()
    near = np.zeros(len(dg), bool)
    for i, (c_, p_) in enumerate(zip(dg["col"].values, dg["pos"].values)):
        tp = term_pos.get(c_)
        if tp is not None:
            j = np.searchsorted(tp, p_ - 3)
            near[i] = j < len(tp) and tp[j] <= p_ + 12            # a termination from 3 sessions before the deposit to 12 after... see note
    # note: "near" = the fund has a termination T with D-3 <= T <= D+12, i.e. the deposit falls 12 sessions before to 3 after a T
    dmo = (dates[dg["pos"].values].year * 100 + dates[dg["pos"].values].month).values
    dw = dg["n_series"].values.astype(float)
    out["deposit_leg"] = {}
    for nm, sel in (("termination_of_same_fund_nearby", near), ("no_termination_nearby", ~near)):
        out["deposit_leg"][nm] = {k: cs(close_win(dg["pos"].values[sel], dg["col"].values[sel], a, b), dw[sel], dmo[sel])
                                  for k, (a, b) in {"D-10..D-1": (-10, -1), "D+1..D+5": (1, 5), "D+1..D+21": (1, 21), "D+1..D+63": (1, 63)}.items()}

    (HERE / "checks.json").write_text(json.dumps(out, indent=1, default=str))
    f = lambda d: f"{d.get('mean_bp', float('nan')):+.1f} (t {d.get('t_clustered') or float('nan'):.1f}, n {d['n']})"
    print("\nwindow | close | mid | close-ctl | mid-ctl | placebo close | placebo mid")
    for k, v in tab.items():
        print(k, "|", " | ".join(f(v[c]) for c in v))
    print(json.dumps(where, indent=0))
    for sect in ("size_known_before_T",):
        print(out[sect]["events_at_or_over_5pct"], out[sect]["events_with_a_notice_filed_30d_before_T"], out[sect]["share_pit_quantiles"])
        for nm in ("sale_at_or_over_5pct_of_nine_session_volume", "sale_under_5pct_or_unknown"):
            print(nm, {k: (f(v["close_to_close"]), f(v["mid_to_mid"])) for k, v in out[sect][nm].items()})
    print("desk", out["desk_funds"]["events"], {k: (f(v["close_to_close"]), f(v["mid_to_mid"])) for k, v in out["desk_funds"].items() if isinstance(v, dict)})
    print("sponsor", {s: {k: f(v) for k, v in d.items()} for s, d in out["by_sponsor"].items()})
    print("era", {s: {k: (f(v["close_to_close"]), f(v["mid_to_mid"])) for k, v in d.items() if k in ("T-9..T", "T+1", "T+1..T+3", "T+1..T+10")} for s, d in out["by_era_mid"].items()})
    print("deposit", {s: {k: f(v) for k, v in d.items()} for s, d in out["deposit_leg"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
