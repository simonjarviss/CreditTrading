"""Explore: a thin ETF against its liquid near-twin, fading the one-day gap between them.

    QUANTT_ENV_FILE=<env> python3 results/ideas/etf_twins/stage.py
    python3 results/ideas/etf_twins/explore.py

WHY: many indices are tracked by two or more ETFs, and a thin one often has a liquid
near-duplicate. If the thin fund's close-to-close return differs from the liquid one's, the
gap should close. A $100k-$1M book can trade a fund doing $0.2M-$20M a day; a large one
cannot. The desk's `pair-reversion` kill (docs/RESEARCH_STATE.md, 2026-07-31) was 22
hand-listed credit wrappers on spread levels; this is the rule-built, all-ETF, dead-funds-
included, one-day-gap version, and the question it must answer is whether anything is left
under shift(2) or whether it is all stale last-trade prices.

FIXED BEFORE ANY RETURN WAS READ (2026-11-16). Only the column list and CRSP's security-type
counts had been read. CRSP carries no fund name or category, so pairs are built from
returns alone (the lane's "names match" test cannot be applied; said on the card).
  PANEL     every CRSP security with securitytype FUND / subtype ETF, 2001-01-01 to
            2025-12-31, dead funds included (stage.py).
  PAIRS     re-formed at each month's last session m from data up to m, used for signals in
            the NEXT month only:
            thin   = 63-session median dollar volume $0.2M to $20M, price $5 or more, a
                     return on each of the last 250 sessions and a trade (volume > 0) on at
                     least 240 of them;
            liquid = 63-session median dollar volume $50M or more, 250 returns;
            twin   = the liquid fund with the highest 250-session daily return correlation
                     to the thin one, kept only if that correlation is 0.98 or more and the
                     thin fund's beta to it is 0.9 to 1.1 (which removes leveraged funds).
            One twin per thin fund.
  SIGNAL    each session t: d = thin return - twin return; z = d over the standard deviation
            of d across the 60 sessions ending t-1. Event when |z| >= 2 and the thin fund
            traded on t and on t-1 (so d is trade to trade).
  TRADE     against the gap: long thin / short twin if d < 0, the reverse if d > 0, equal
            dollars a leg. Decided at t's close, filled at t+1's close, held 5 sessions
            (earns t+2 .. t+6): harness shift(2). Each event is 1/(5 * max(n, 10)) of the
            book a leg, n = events that day, so a lone event is at most 2% and the book is
            100% a side only when 10 or more pairs fire every day.
  A (HEADLINE)   signal and P&L on CRSP returns (last trade, or CRSP's quote average on a
                 no-trade day).
  B (THE TEST)   signal and P&L on closing MID quotes (bid > 0, ask >= bid, spread <= 5% of
                 mid; total return = mid change times CRSP's own distribution adjustment).
                 A missing mid return on a held day falls back to the CRSP return and is
                 COUNTED. If A is stale prints or bid-ask bounce, B is flat.
  C              A's signal, P&L on mids: is A's profit there at a quotable price?
  D (SKIP)       A decided one session later (earns t+3 .. t+7).
  CONTROL   LIQUID-LIQUID: the same rule with the "thin" role played by a fund trading $50M
            or more, twinned with a MORE liquid fund. Convergence that is about thinness is
            absent there; a result that is general end-of-day noise scores the same.
  DOSE      the same rule on thin pairs with correlation 0.95 to under 0.98 (similar, not
            twins), descriptive.
  DECAY     per event, the signed thin-minus-twin return on each of t+1 .. t+6, on trades
            and on mids. t+1 cannot be traded under shift(2); it is shown to size what is
            lost by waiting.
  EXPECTED  A positive; most of the gap closes on t+1 (untradable); B much smaller than A.
            Promising only if B is positive in both halves and its per-event buy-and-hold
            return exceeds the thin leg's median closing spread.
  DESCRIPTIVE: pairs a month, events, turnover, dollar volume / price / closing spread of
            the thin leg at events, buy-and-hold per-event return (t+2 .. t+6 compounded).
Gross; no cost is modelled. Writes results.json (aggregates only) beside this file.
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
RES = Path.home() / "quantt_research" / "etf_twins"
THIN_LO, THIN_HI, LIQ_MIN, MIN_PRICE = 2e5, 2e7, 5e7, 5.0
CORR_WIN, DV_WIN, MIN_TRADED, Z_WIN, Z_MINP = 250, 63, 240, 60, 40
CORR_MIN, BETA_LO, BETA_HI, Z_ENTRY, HOLD, MIN_N, MAX_SPREAD = 0.98, 0.9, 1.1, 2.0, 5, 10, 0.05
DOSE_LO = 0.95


def load():
    """Long CRSP rows -> dense session x fund arrays (numpy, not pivot: 9M rows)."""
    df = pd.read_parquet(RES / "crsp_etf_quotes_daily.parquet",
                         columns=["permno", "date", "ret", "prc", "vol", "dollar_volume", "bid", "ask"])
    df["date"] = pd.to_datetime(df["date"])
    di, dates = pd.factorize(df["date"], sort=True)
    pi, permnos = pd.factorize(df["permno"], sort=True)
    if pd.Series(list(zip(di, pi))).duplicated().any():
        raise ValueError("a fund has two rows on one date")
    shape = (len(dates), len(permnos))

    def dense(col, dtype=np.float64):
        a = np.full(shape, np.nan, dtype=dtype)
        a[di, pi] = df[col].to_numpy()
        return a
    ret, prc, bid, ask = dense("ret"), np.abs(dense("prc")), dense("bid"), dense("ask")
    vol, dv = dense("vol", np.float32), dense("dollar_volume", np.float32)
    mid = (bid + ask) / 2
    spread = (ask - bid) / mid
    okq = (bid > 0) & (ask >= bid) & (spread <= MAX_SPREAD)
    mid = np.where(okq, mid, np.nan); spread = np.where(okq, spread, np.nan).astype(np.float32)
    # total return on mids: the mid's change times CRSP's own adjustment (1+ret)/(price ratio),
    # which carries distributions and splits. Row t uses rows t and t-1 only.
    with np.errstate(invalid="ignore", divide="ignore"):
        adj = (1 + ret[1:]) / (prc[1:] / prc[:-1])
        mret = np.full(shape, np.nan)
        mret[1:] = mid[1:] / mid[:-1] * adj - 1
    return pd.DatetimeIndex(dates), np.asarray(permnos), ret, mret, prc, vol, dv, spread


def form_pairs(dates, ret, prc, vol, dv):
    """Month-end pair lists. Row: formation index i, thin col, twin col, corr, beta, kind."""
    s = pd.Series(np.arange(len(dates)), index=dates)
    month_last = s.groupby(dates.to_period("M")).max().to_numpy()
    rows = []
    for i in month_last:
        if i < CORR_WIN - 1:
            continue
        w = ret[i - CORR_WIN + 1:i + 1]                                   # data up to and including m
        complete = ~np.isnan(w).any(axis=0)
        med = np.nanmedian(np.where(np.isnan(dv[i - DV_WIN + 1:i + 1]), 0.0, dv[i - DV_WIN + 1:i + 1]), axis=0)
        traded = (np.nan_to_num(vol[i - CORR_WIN + 1:i + 1]) > 0).sum(axis=0)
        liq = np.flatnonzero(complete & (med >= LIQ_MIN))
        thin = np.flatnonzero(complete & (med >= THIN_LO) & (med <= THIN_HI) & (prc[i] >= MIN_PRICE) & (traded >= MIN_TRADED))
        if len(liq) < 2:
            continue
        sd = w.std(axis=0)

        def z(cols):
            x = w[:, cols]
            return (x - x.mean(axis=0)) / np.where(sd[cols] > 0, sd[cols], np.nan)
        Zl = z(liq)
        for kind, cand in (("thin", thin), ("liquid", liq)):
            if not len(cand):
                continue
            C = np.nan_to_num(z(cand).T @ Zl / CORR_WIN, nan=-1.0)
            if kind == "liquid":                                         # twin must be MORE liquid than the fund itself
                C = np.where(med[liq][None, :] > med[cand][:, None], C, -1.0)
            j = C.argmax(axis=1)
            c = C[np.arange(len(cand)), j]
            beta = c * sd[cand] / sd[liq[j]]
            for a, b, cc, bb in zip(cand, liq[j], c, beta):
                if cc >= DOSE_LO and BETA_LO <= bb <= BETA_HI:
                    rows.append((i, a, b, cc, bb, kind, med[a], med[b]))
    return pd.DataFrame(rows, columns=["i", "thin", "twin", "corr", "beta", "kind", "dv_thin", "dv_twin"]), month_last


def find_events(pairs, month_last, sig, traded_ok):
    """Events for one pair table. sig: session x fund returns the signal is measured on.
    traded_ok[t, fund]: the fund's return at t is a usable observation for the signal."""
    nxt = dict(zip(month_last[:-1], month_last[1:]))
    out = []
    for i, g in pairs.groupby("i"):
        if i not in nxt:
            continue                                                     # last formation: no later session in the panel
        ni = nxt[i]
        a, b = g["thin"].to_numpy(), g["twin"].to_numpy()
        lo = i - Z_WIN
        D = pd.DataFrame(sig[lo:ni + 1][:, a] - sig[lo:ni + 1][:, b])
        sd = D.rolling(Z_WIN, min_periods=Z_MINP).std().shift(1)          # 60 sessions ending t-1
        Z = (D / sd).to_numpy()[Z_WIN + 1:]                               # sessions i+1 .. ni
        Dn = D.to_numpy()[Z_WIN + 1:]
        ok = traded_ok[i + 1:ni + 1][:, a] & traded_ok[i:ni][:, a] & traded_ok[i + 1:ni + 1][:, b]
        r, c = np.nonzero((np.abs(Z) >= Z_ENTRY) & ok & np.isfinite(Z))
        t = i + 1 + r
        assert (t > i).all(), "a signal session is not after its pair formation"
        out.append(pd.DataFrame({"t": t, "thin": a[c], "twin": b[c], "side": -np.sign(Dn[r, c]), "z": Z[r, c], "d": Dn[r, c]}))
    ev = pd.concat(out, ignore_index=True)
    return ev[ev["side"] != 0].reset_index(drop=True)


def book(ev, dates, R, extra_lag=0, raw=None):
    """Events -> harness weights -> daily P&L. R: session x fund returns the book earns."""
    T = len(dates)
    cols = np.unique(np.concatenate([ev["thin"].to_numpy(), ev["twin"].to_numpy()]))
    pos = {c: k for k, c in enumerate(cols)}
    H = np.zeros((T, len(cols)))
    n = ev.groupby("t")["t"].transform("size").to_numpy()
    w = ev["side"].to_numpy() / (HOLD * np.maximum(n, MIN_N))
    a = ev["thin"].map(pos).to_numpy(); b = ev["twin"].map(pos).to_numpy(); t = ev["t"].to_numpy() + extra_lag
    for k in range(HOLD):                                                # decided at t, carried HOLD sessions
        keep = t + k < T
        np.add.at(H, (t[keep] + k, a[keep]), w[keep])
        np.add.at(H, (t[keep] + k, b[keep]), -w[keep])
    Hd = pd.DataFrame(H, index=dates, columns=cols)
    Rr = R[:, cols]
    held = harness.held(Hd).to_numpy() != 0
    missing = int((held & np.isnan(Rr)).sum())
    fell_back = None if raw is None else int((held & np.isnan(raw[:, cols])).sum())   # held days where the mid return was missing
    res = harness.evaluate(Hd, pd.DataFrame(np.nan_to_num(Rr), index=dates, columns=cols))
    first = dates[int(ev["t"].min())]
    pnl = res["pnl"].loc[first:].iloc[harness.EXEC_LAG:]
    info = {"turnover_per_year": float(res["turn_series"].loc[first:].sum() * 252 / len(res["turn_series"].loc[first:])),
            "mean_gross_per_side": float(np.abs(H[int(ev["t"].min()):]).sum(axis=1).mean() / 2),
            "held_name_days": int(held.sum()), "held_name_days_without_return_booked_zero": missing,
            "held_name_days_mid_missing_fell_back_to_crsp_return": fell_back}
    return pnl, info


def per_event(ev, dates, R, k0=2, k1=6):
    """Buy-and-hold: signed compounded thin less compounded twin over t+k0 .. t+k1."""
    T = len(dates)
    e = ev[ev["t"] + k1 < T]
    t, a, b, s = e["t"].to_numpy(), e["thin"].to_numpy(), e["twin"].to_numpy(), e["side"].to_numpy()
    ga, gb = np.ones(len(e)), np.ones(len(e))
    for k in range(k0, k1 + 1):
        ga *= 1 + np.nan_to_num(R[t + k, a]); gb *= 1 + np.nan_to_num(R[t + k, b])
    x = pd.Series(s * (ga - gb), index=dates[t])
    day = x.groupby(level=0).mean()                                      # t-stat on day means: events on one day are not independent
    return {"events": int(len(x)), "mean_bp": float(x.mean() * 1e4), "median_bp": float(x.median() * 1e4),
            "share_positive": float((x > 0).mean()), "t_on_day_means": float(day.mean() / day.std() * np.sqrt(len(day)))}


def decay(ev, dates, R, kmax=6):
    T = len(dates)
    e = ev[ev["t"] + kmax < T]
    t, a, b, s = e["t"].to_numpy(), e["thin"].to_numpy(), e["twin"].to_numpy(), e["side"].to_numpy()
    out = {}
    for k in range(0, kmax + 1):
        x = pd.Series(s * (R[t + k, a] - R[t + k, b]), index=dates[t]).dropna()
        day = x.groupby(level=0).mean()
        out[f"t+{k}"] = {"mean_bp": float(x.mean() * 1e4), "median_bp": float(x.median() * 1e4),
                         "t_on_day_means": float(day.mean() / day.std() * np.sqrt(len(day))), "n": int(len(x))}
    return out


def describe(ev, pairs, dates, prc, dv, spread):
    t, a = ev["t"].to_numpy(), ev["thin"].to_numpy()
    m = pairs.groupby("i").size()
    yr = pd.Series(dates[t].year).value_counts().sort_index()
    return {"pairs_per_month_mean": float(m.mean()), "pairs_per_month_median": float(m.median()), "formation_months": int(len(m)),
            "distinct_thin_funds": int(pairs["thin"].nunique()), "distinct_twins": int(pairs["twin"].nunique()),
            "events": int(len(ev)), "event_days": int(ev["t"].nunique()), "events_per_event_day_median": float(ev.groupby("t").size().median()),
            "events_by_year": {int(k): int(v) for k, v in yr.items()},
            "thin_leg_at_events": {"median_dollar_volume_that_day": float(np.nanmedian(dv[t, a])), "median_price": float(np.nanmedian(prc[t, a])),
                                   "median_closing_spread_bp": float(np.nanmedian(spread[t, a]) * 1e4),
                                   "mean_closing_spread_bp": float(np.nanmean(spread[t, a]) * 1e4),
                                   "share_with_valid_quote": float(np.isfinite(spread[t, a]).mean())},
            "median_abs_gap_bp": float(np.median(np.abs(ev["d"])) * 1e4), "median_pair_corr": float(pairs["corr"].median())}


def main() -> int:
    dates, permnos, ret, mret, prc, vol, dv, spread = load()
    print(f"panel {dates[0].date()} .. {dates[-1].date()}, {len(permnos):,} funds, {np.isfinite(ret).sum():,} returns; "
          f"valid closing quote on {np.isfinite(spread).sum() / np.isfinite(prc).sum():.1%} of fund-days")
    allp, month_last = form_pairs(dates, ret, prc, vol, dv)
    twins = allp[(allp["kind"] == "thin") & (allp["corr"] >= CORR_MIN)]
    dose = allp[(allp["kind"] == "thin") & (allp["corr"] < CORR_MIN)]
    liqp = allp[(allp["kind"] == "liquid") & (allp["corr"] >= CORR_MIN)]
    traded = (np.nan_to_num(vol) > 0) & np.isfinite(ret)
    quoted = np.isfinite(mret)
    # liquid twins need a return, not a trade test of their own; the thin leg's rule is applied to both for simplicity
    ev_a = find_events(twins, month_last, ret, traded)
    ev_b = find_events(twins, month_last, mret, quoted)
    ev_dose = find_events(dose, month_last, ret, traded)
    ev_liq = find_events(liqp, month_last, ret, traded)
    mfill = np.where(np.isnan(mret), ret, mret)                          # counted below, never silent
    out = {"panel_first_date": str(dates[0].date()), "panel_last_date": str(dates[-1].date()), "funds_in_panel": int(len(permnos)),
           "share_fund_days_with_valid_closing_quote": float(np.isfinite(spread).sum() / np.isfinite(prc).sum()),
           "fixed": {"thin_dollar_volume": [THIN_LO, THIN_HI], "liquid_min": LIQ_MIN, "min_price": MIN_PRICE, "corr_min": CORR_MIN,
                     "beta": [BETA_LO, BETA_HI], "z_entry": Z_ENTRY, "hold_sessions": HOLD, "min_n": MIN_N, "max_spread": MAX_SPREAD}}
    runs = {"A trades/trades (headline)": (ev_a, twins, ret, 0), "B mids/mids (the test)": (ev_b, twins, mfill, 0),
            "C trade signal, mid P&L": (ev_a, twins, mfill, 0), "D A with one more session's wait": (ev_a, twins, ret, 1),
            "CONTROL liquid-liquid": (ev_liq, liqp, ret, 0), "DOSE corr 0.95-0.98": (ev_dose, dose, ret, 0)}
    pnl = {}
    for name, (ev, pr, R, lag) in runs.items():
        p, info = book(ev, dates, R, lag, raw=mret if R is mfill else None)
        pnl[name] = p
        res = explore.summarise(p)
        out[name] = {**info, **describe(ev, pr, dates, prc, dv, spread), **res,
                     "per_event_buy_and_hold_t+2..t+6": {"on_trades": per_event(ev, dates, ret), "on_mids": per_event(ev, dates, mfill)},
                     "decay_on_trades": decay(ev, dates, ret), "decay_on_mids": decay(ev, dates, mret)}
        d = out[name]
        print(f"\n== {name}: {d['pairs_per_month_mean']:.0f} pairs a month ({d['distinct_thin_funds']} funds), {d['events']:,} events on {d['event_days']:,} days, "
              f"turnover {d['turnover_per_year']:.0f}/yr, gross a side {d['mean_gross_per_side']:.2f}; thin leg median ${d['thin_leg_at_events']['median_dollar_volume_that_day']:,.0f}, "
              f"${d['thin_leg_at_events']['median_price']:.0f}, spread {d['thin_leg_at_events']['median_closing_spread_bp']:.1f}bp; gap {d['median_abs_gap_bp']:.0f}bp; "
              f"no-return held days {d['held_name_days_without_return_booked_zero']} of {d['held_name_days']}")
        print(explore.table(res))
        pe = d["per_event_buy_and_hold_t+2..t+6"]
        print(f"per event t+2..t+6: trades {pe['on_trades']['mean_bp']:.1f}bp (median {pe['on_trades']['median_bp']:.1f}, t {pe['on_trades']['t_on_day_means']:.1f}); "
              f"mids {pe['on_mids']['mean_bp']:.1f}bp (median {pe['on_mids']['median_bp']:.1f}, t {pe['on_mids']['t_on_day_means']:.1f})")
        print("decay, signed thin less twin, bp (t): trades " + "  ".join(f"{k} {v['mean_bp']:.1f} ({v['t_on_day_means']:.1f})" for k, v in d["decay_on_trades"].items()))
        print("                                       mids   " + "  ".join(f"{k} {v['mean_bp']:.1f} ({v['t_on_day_means']:.1f})" for k, v in d["decay_on_mids"].items()))
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
