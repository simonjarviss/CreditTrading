"""Explore: merger arbitrage in US cash deals. The plain premium, and the event-time (hazard) spread.

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_sdc_deals.py
    python3 results/ideas/merger_arb/explore.py

BACKGROUND. `results/events/MERGER_ARB_V2_2026-10-19.md` designed an event-time trade on
Giglio & Shue (2014) and stopped before computing any return: under the rules of the time
the plain deal premium was a risk premium (not allowed), and the event-time spread was
unlikely to clear a t of 3. The team lead's 2026-11-09 ruling dropped both gates, so both
are tested here. The deal list is SDC's, not the October EDGAR census, for the reason in
scripts/research/stage_sdc_deals.py: the census only sees a deal once its proxy is filed.

FIXED BEFORE ANY RETURN WAS READ
  deals        SDC 'Merger' bids for US public targets, all cash by SDC's percentages
               (`cash_class == 'cash'`; the text rule agreed with the percentages on only 84%
               of deals, so text-only cash deals are left out). One-step mergers and tender
               offers are separate groups. No rule here reads SDC's final status. The
               STAGING does select on it (Completed, Withdrawn or Pending), which drops deals
               SDC later re-coded; scripts/research/stage_sdc_deals.py prints how many.
  entry        the decision is made at the close of the first session AFTER SDC's
               announcement date (t0). With shift(2) the first return earned is t0 + 2,
               three sessions after the announcement, so the announcement jump is never
               earned whichever side of the close the news came.
  eligible     judged once, at t0: the target trades that day, closes at $5 or more, and its
               trailing 21-session average dollar volume is $1M or more.
  exit         the first of: the target stops trading (its last row is CRSP's delisting row,
               which carries the cash paid); the session after SDC's withdrawal date; 252
               sessions after t0. A broken deal is therefore held THROUGH the break: the
               weights decided before the withdrawal was public earn the break-day return.
  PREMIUM      the plain book: every active deal, equal weights, long only, unit gross; flat
               with fewer than 5 deals. Shown raw (as every Explore table), over 3-month
               bills, and with its market beta: a cash deal's spread includes the bill rate,
               and the known risk is that deals break together when the market falls.
  HAZARD       the event-time book, inside the same deals: long deals in weeks when deals
               usually close, short deals in weeks when they usually do not. Each month the
               completion hazard by event week is re-estimated from deals announced at least
               365 days earlier (so every one is fully observed for 52 weeks); weeks are
               grouped in blocks of four; a block is High when its hazard is above the mean
               of the thirteen blocks. Half the book long across deals in High blocks, half
               short across deals in Low blocks, flat with fewer than 5 on either side or
               fewer than 200 earlier deals. This differs from the paper's fixed weeks on
               purpose: the October note showed today's deals close earlier than the
               paper's.
  CONTROL      the same HAZARD rule on cash tender offers. A tender's expiry date is
               published, so the passage of time is no surprise and the mechanism predicts
               no spread there.
  convention   shift(2) on the canonical harness; gross; no cost and no borrow modelled.

A target in two live deals at once (a competing bid) is held once.

ADDED AFTER THE FIRST RUN, so NOT pre-specified, and reported beside the fixed books
  friendly     the first run showed that SDC's 'Merger' form includes unsolicited and hostile
               proposals: 155 of the 1,529 eligible one-step deals, of which 95% were later
               withdrawn. Those are bids, not agreed deals, and merger arbitrage is about
               agreed deals. The `_friendly` books keep only deals SDC marks Friendly.
               [U] whether SDC ever revises that mark after the announcement; the table has
               an `attitude_change_yn` field and it is counted in the output.
  profile      the mean return over bills of a live friendly deal by four-week block of event
               time, with a t clustered by day. A description of where in a deal's life the
               return sits; nothing is traded on it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness, inference  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
DEALS, ROWS, MKT = RES / "sdc_ma_deals.parquet", RES / "crsp_ma_targets_daily.parquet", RES / "yf_daily.parquet"
RF = Path.home() / "quantt_data" / "riskfree_daily.parquet"
MIN_PRICE, MIN_ADV, MAX_HOLD, MIN_NAMES = 5.0, 1_000_000.0, 252, 5
BLOCK_WEEKS, N_BLOCKS, SEASONING_DAYS, MIN_PRIOR_DEALS = 4, 13, 365, 200


def load():
    d = pd.read_parquet(DEALS)
    for c in ("dateann", "dateannorig", "dateeff", "datewith"):
        d[c] = pd.to_datetime(d[c])
    d = d[d["cash_class"] == "cash"].copy()
    x = pd.read_parquet(ROWS)
    x["date"] = pd.to_datetime(x["date"])
    x = x[x["permno"].isin(d["permno"])]
    ret = x.pivot(index="date", columns="permno", values="ret")
    prc = x.pivot(index="date", columns="permno", values="prc")
    dv = x.pivot(index="date", columns="permno", values="dollar_volume")
    trading = x[x["delflg"] != "Y"].pivot(index="date", columns="permno", values="prc").notna()
    trading = trading.reindex(index=ret.index, columns=ret.columns, fill_value=False)
    return d, ret, prc, dv, trading


def spells(d: pd.DataFrame, sessions: pd.DatetimeIndex, prc, dv, trading) -> pd.DataFrame:
    """One row per deal: the first and last DECISION session index it is held on, or not eligible.
    ALIGNMENT: everything read here is dated on or before the decision session it gates."""
    n = len(sessions)
    t0 = sessions.searchsorted(d["dateann"].values, side="right")            # first session strictly after the announcement
    adv = dv.rolling(21, min_periods=10).mean()
    col = prc.columns.get_indexer(d["permno"])
    P, A, T = prc.to_numpy(), adv.to_numpy(), trading.to_numpy()
    ok = t0 < n
    i0 = np.where(ok, t0, 0)
    elig = ok & T[i0, col] & (np.nan_to_num(P[i0, col]) >= MIN_PRICE) & (np.nan_to_num(A[i0, col]) >= MIN_ADV)
    last_trade = np.array([np.flatnonzero(T[:, c])[-1] if T[:, c].any() else -1 for c in col])
    xw = sessions.searchsorted(d["datewith"].fillna(pd.Timestamp("2262-01-01")).values, side="right")   # the session the exit is decided
    end = np.minimum.reduce([t0 + MAX_HOLD - 1, last_trade, xw - 1])
    out = d[["deal", "permno", "dateann", "dateeff", "datewith", "tender", "deal_value", "attitude", "attitude_change_yn"]].copy()
    out["i0"], out["i1"], out["eligible"], out["col"] = t0, end, elig & (end >= t0), col
    out["cap_t0"] = np.where(ok, P[i0, col], np.nan)                          # placeholder, replaced below by market value
    return out


def active_matrix(sp: pd.DataFrame, shape, mask=None) -> np.ndarray:
    a = np.zeros(shape, dtype=bool)
    for i0, i1, c in sp.loc[sp["eligible"] if mask is None else (sp["eligible"] & mask), ["i0", "i1", "col"]].itertuples(index=False):
        a[i0:i1 + 1, c] = True
    return a


def long_only(active: np.ndarray, index, columns) -> pd.DataFrame:
    n = active.sum(axis=1)
    w = np.where((n >= MIN_NAMES)[:, None], active / np.maximum(n, 1)[:, None], 0.0)
    return pd.DataFrame(w, index=index, columns=columns)


def hazard_blocks(prior: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Completion hazard per four-week block from fully seasoned deals, and which blocks are High."""
    # week 1 is days 0 to 6 after the announcement: the SAME definition hazard_book uses to place a live deal
    wc = (prior["dateeff"] - prior["dateann"]).dt.days // 7 + 1
    ww = (prior["datewith"] - prior["dateann"]).dt.days // 7 + 1
    leave = np.fmin(wc.fillna(np.inf), ww.fillna(np.inf)).clip(lower=1)        # the week it left, either way
    haz = np.zeros(N_BLOCKS)
    for b in range(N_BLOCKS):
        lo, hi = b * BLOCK_WEEKS + 1, (b + 1) * BLOCK_WEEKS
        at_risk_weeks = (np.minimum(leave, hi) - lo + 1).clip(lower=0).sum()   # deal-weeks at risk inside the block
        done = ((wc >= lo) & (wc <= hi) & (wc <= ww.fillna(np.inf))).sum()
        haz[b] = done / at_risk_weeks if at_risk_weeks > 0 else 0.0
    return haz, haz > haz.mean()


def hazard_book(sp: pd.DataFrame, group: pd.DataFrame, sessions, shape, columns):
    """+0.5 across active deals in High blocks, -0.5 across those in Low blocks. `group` is every
    linked deal of the kind (eligible or not): the hazard is a fact about deals, not about prices."""
    W = np.zeros(shape)
    months = pd.Series(np.arange(len(sessions)), index=sessions).groupby(sessions.to_period("M"))
    log = []
    el = sp[sp["eligible"]]
    ann_days = el["dateann"].values.astype("datetime64[D]")
    for per, idx in months:
        start = per.start_time
        prior = group[group["dateann"] <= start - pd.Timedelta(days=SEASONING_DAYS)]
        if len(prior) < MIN_PRIOR_DEALS:
            continue
        haz, high = hazard_blocks(prior)
        log.append({"month": str(per), "prior_deals": int(len(prior)), "high_blocks": [int(b) for b in np.flatnonzero(high)],
                    "hazard": [round(float(h), 4) for h in haz]})
        for i in idx.values:
            day = sessions[i].to_datetime64().astype("datetime64[D]")
            live = (el["i0"].values <= i) & (el["i1"].values >= i)
            if not live.any():
                continue
            week = ((day - ann_days[live]).astype(int) // 7) + 1
            block = (week - 1) // BLOCK_WEEKS
            cols = el["col"].values[live]
            inb = block < N_BLOCKS
            hi_c = np.unique(cols[inb & high[np.minimum(block, N_BLOCKS - 1)]])
            lo_c = np.setdiff1d(np.unique(cols[inb & ~high[np.minimum(block, N_BLOCKS - 1)]]), hi_c)
            if len(hi_c) >= MIN_NAMES and len(lo_c) >= MIN_NAMES:
                W[i, hi_c] = 0.5 / len(hi_c)
                W[i, lo_c] = -0.5 / len(lo_c)
    return pd.DataFrame(W, index=sessions, columns=columns), log


def market_fit(pnl: pd.Series, mkt_x: pd.Series) -> dict:
    """pnl on the market's excess return and its one-session lag (targets can trade thinly).
    Reported, never gated: the beta, the beta in the market's worst months, the alpha."""
    df = pd.DataFrame({"y": pnl, "m": mkt_x, "m1": mkt_x.shift(1)}).dropna()
    X = np.column_stack([np.ones(len(df)), df["m"], df["m1"]])
    b = np.linalg.lstsq(X, df["y"].values, rcond=None)[0]
    resid = df["y"].values - X @ b
    alpha = pd.Series(resid + b[0], index=df.index)
    mon = pd.DataFrame({"y": df["y"], "m": df["m"]}).groupby(df.index.to_period("M")).sum()
    down = mon[mon["m"] < -0.04]
    bd = float(np.polyfit(down["m"], down["y"], 1)[0]) if len(down) >= 8 else None
    up = mon[mon["m"] >= -0.04]
    return {"beta": float(b[1] + b[2]), "beta_same_day": float(b[1]), "alpha_per_year": float(b[0] * 252),
            "alpha_t_newey_west": float(inference.newey_west_t(alpha.values)),
            "months_market_below_minus_4pct": int(len(down)), "beta_in_those_months": bd,
            "mean_return_in_those_months": float(down["y"].mean()) if len(down) else None,
            "beta_other_months": float(np.polyfit(up["m"], up["y"], 1)[0]) if len(up) >= 8 else None}


def main() -> int:
    d, ret, prc, dv, trading = load()
    sessions = ret.index
    R = ret.fillna(0.0)                                   # after its delisting row a target has no row: it is cash
    missing_in_life = ret.isna() & trading                # a session the target traded but CRSP gives no return
    last = sessions.max().date()
    mk = pd.read_parquet(MKT)
    spy = mk[mk["ticker"] == "SPY"].set_index("date")["ret_total"].reindex(sessions)
    rf = pd.read_parquet(RF).set_index("date")["rf_daily"].reindex(sessions).ffill()
    if spy.loc["2000-02-01":].isna().sum() > 5 or rf.loc["2000-02-01":].isna().any():
        raise RuntimeError("the market or bill series does not cover the deal calendar")
    mkt_x = (spy - rf)
    out, shape = {}, ret.shape
    sp_all = spells(d, sessions, prc, dv, trading)
    cap = (x := pd.read_parquet(ROWS, columns=["permno", "date", "cap"])).assign(date=pd.to_datetime(x["date"])).pivot(index="date", columns="permno", values="cap").reindex(index=sessions, columns=ret.columns).to_numpy()
    sp_all["cap_t0"] = cap[np.minimum(sp_all["i0"].values, len(sessions) - 1), sp_all["col"].values]

    # ---- the dating check: where does the announcement jump sit relative to SDC's date?
    A = sessions.searchsorted(d["dateann"].values, side="left")
    on_session = (A < len(sessions)) & (sessions[np.minimum(A, len(sessions) - 1)] == d["dateann"].values)
    Rn = ret.to_numpy()
    prof = {}
    for k in range(-3, 6):
        i = A + k
        okk = on_session & (i >= 0) & (i < len(sessions))
        v = Rn[i[okk], sp_all["col"].values[okk]]
        v = v[~np.isnan(v)]
        prof[f"A{k:+d}"] = {"mean_pct": float(v.mean() * 100), "median_pct": float(np.median(v) * 100), "n": int(len(v))}
    out["announcement_dating"] = {"share_announced_on_a_session": float(on_session.mean()),
                                  "share_dateann_after_dateannorig": float((d["dateann"] > d["dateannorig"]).mean()),
                                  "share_dateann_before_dateannorig": float((d["dateann"] < d["dateannorig"]).mean()),
                                  "target_return_by_session": prof}

    start = pd.Timestamp("2000-02-01")
    series = {}
    for name, flag, friendly in (("one_step", "No", False), ("tender", "Yes", False),
                                 ("one_step_friendly", "No", True), ("tender_friendly", "Yes", True)):
        g = sp_all[(sp_all["tender"] == flag) & ((sp_all["attitude"] == "Friendly") | (not friendly))]
        act = active_matrix(g, shape)
        H = long_only(act, sessions, ret.columns)
        ev = harness.evaluate(H, R)
        pnl = ev["pnl"].loc[start:]
        n_act = pd.Series(act.sum(axis=1), index=sessions).loc[start:]
        xs = pnl - rf.reindex(pnl.index) * (H.shift(harness.EXEC_LAG).abs().sum(axis=1).reindex(pnl.index).fillna(0.0))   # bills only on days the book is invested
        series[f"premium_{name}"] = pnl
        series[f"premium_{name}_excess"] = xs
        held_days = (H.shift(harness.EXEC_LAG).fillna(0.0) != 0)
        info = {"deals_linked": int(len(g)), "deals_eligible": int(g["eligible"].sum()),
                "held_name_days": int(held_days.sum().sum()),
                "held_name_days_with_no_return_while_trading": int((held_days & missing_in_life).sum().sum()),
                "deals_active_per_day_median": float(n_act.median()), "flat_day_share": float((n_act < MIN_NAMES).mean()),
                "turnover_per_year": float(ev["turn"]),
                "held_sessions_median": float((g.loc[g["eligible"], "i1"] - g.loc[g["eligible"], "i0"] + 1).median()),
                "excess_over_bills": explore.stats(xs), "market": market_fit(xs, mkt_x)}
        # hedged with a beta estimated on the previous 252 sessions, lagged two sessions
        cov = xs.rolling(252).cov(mkt_x.reindex(xs.index)); var = mkt_x.reindex(xs.index).rolling(252).var()
        beta_roll = (cov / var).shift(harness.EXEC_LAG)
        hedged = (xs - beta_roll * mkt_x.reindex(xs.index)).dropna()
        info["hedged_with_rolling_beta"] = explore.stats(hedged)
        # by size: target market value at t0 against the median of deals announced earlier
        ge = g[g["eligible"]].sort_values("dateann")
        med = ge["cap_t0"].expanding(min_periods=50).median().shift(1)
        small = ge["cap_t0"] < med
        for lab, m in (("small_targets", small & med.notna()), ("large_targets", ~small & med.notna())):
            Hs = long_only(active_matrix(ge, shape, mask=m.reindex(ge.index)), sessions, ret.columns)
            ps = harness.evaluate(Hs, R)["pnl"].loc[start:]
            info[lab] = {"excess_over_bills": explore.stats(ps - rf.reindex(ps.index) * (Hs.shift(harness.EXEC_LAG).abs().sum(axis=1).reindex(ps.index).fillna(0.0)))}
        out[f"premium_{name}"] = {**explore.summarise(pnl), **info}

        group_all = d[(d["tender"] == flag) & ((d["attitude"] == "Friendly") | (not friendly))]
        info_att = {"attitude_changed_flag_share": float((g.loc[g["eligible"], "attitude_change_yn"] == "Yes").mean())}
        out[f"premium_{name}"].update(info_att)
        if friendly and flag == "No":
            # the event-time profile: mean daily return over bills of a live deal, by four-week block
            el = g[g["eligible"]]
            ann_days = el["dateann"].values.astype("datetime64[D]")
            Rn, rfn = R.to_numpy(), rf.to_numpy()
            acc = {b: [] for b in range(N_BLOCKS)}
            for i in range(len(sessions) - harness.EXEC_LAG):
                live = (el["i0"].values <= i) & (el["i1"].values >= i)
                if not live.any():
                    continue
                day = sessions[i].to_datetime64().astype("datetime64[D]")
                block = (((day - ann_days[live]).astype(int) // 7)) // BLOCK_WEEKS
                r2 = Rn[i + harness.EXEC_LAG, el["col"].values[live]] - rfn[i + harness.EXEC_LAG]   # ALIGNMENT: decided at i, earned at i+2
                for b in np.unique(block[block < N_BLOCKS]):
                    acc[int(b)].append((r2[block == b].mean(), int((block == b).sum())))
            prof = {}
            for b, v in acc.items():
                if len(v) < 60:
                    continue
                x = np.array([m for m, _ in v])
                prof[f"weeks_{b * BLOCK_WEEKS + 1}_{(b + 1) * BLOCK_WEEKS}"] = {
                    "mean_bp_per_day": float(x.mean() * 1e4), "t_by_day": float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))),
                    "days": int(len(x)), "deal_days": int(sum(k for _, k in v))}
            out[f"premium_{name}"]["event_time_profile_over_bills"] = prof
        Hz, log = hazard_book(g, group_all, sessions, shape, ret.columns)
        evz = harness.evaluate(Hz, R)
        first = Hz.abs().sum(axis=1).gt(0).idxmax()
        pz = evz["pnl"].loc[first:].iloc[harness.EXEC_LAG:]
        series[f"hazard_{name}"] = pz
        legs = {}
        for lab, part in (("high_leg", Hz.clip(lower=0) * 2), ("low_leg", (-Hz).clip(lower=0) * 2)):
            pl = harness.evaluate(part, R)["pnl"].reindex(pz.index)
            legs[lab] = explore.stats(pl - rf.reindex(pz.index) * (part.shift(harness.EXEC_LAG).abs().sum(axis=1).reindex(pz.index).fillna(0.0)))
        live_days = Hz.abs().sum(axis=1).reindex(pz.index) > 0
        first_log, last_log = (log[0], log[-1]) if log else (None, None)
        out[f"hazard_{name}"] = {**explore.summarise(pz), "turnover_per_year": float(evz["turn"]),
                                 "invested_day_share": float(live_days.mean()), "legs_excess_over_bills": legs,
                                 "market": market_fit(pz, mkt_x), "windows_first_month": first_log, "windows_last_month": last_log,
                                 "months_block_was_high": {str(b): int(sum(b in m["high_blocks"] for m in log)) for b in range(N_BLOCKS)},
                                 "months_estimated": int(len(log))}

    # the control beside the idea, on the idea's dates
    hz, ctl = series["hazard_one_step"], series["hazard_tender"]
    for nm in ("one_step", "one_step_friendly"):
        h = series[f"hazard_{nm}"]
        out[f"hazard_{nm}"]["controls"] = {"same rule on cash tender offers": explore.stats(ctl.reindex(h.index).fillna(0.0))}
        out[f"hazard_{nm}"]["corr_with_premium"] = float(np.corrcoef(h, series[f"premium_{nm}_excess"].reindex(h.index).fillna(0.0))[0, 1])
    # capacity of the premium book, 2024 on
    g = sp_all[sp_all["tender"] == "No"]
    H = long_only(active_matrix(g, shape), sessions, ret.columns)
    adv = dv.rolling(21, min_periods=10).mean()
    share = (H / adv).where(H > 0).loc["2024-01-01":].stack()
    out["premium_one_step"]["capacity_2024_on"] = {f"pct_of_adv_at_{s // 10**6}M": {"median": float(share.median() * s * 100),
                                                   "p95": float(share.quantile(0.95) * s * 100)} for s in (10**6, 5 * 10**6, 10**7)}
    out["panel_last_date"] = str(last)
    import json
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    explore.write(HERE / "premium", {**out["premium_one_step"]}, series["premium_one_step_excess"],
                  title=f"Cash one-step mergers, every live deal, over bills; shift(2), gross; to {last}",
                  controls={"friendly deals only (not pre-specified)": series["premium_one_step_friendly_excess"]})
    explore.write(HERE / "hazard", {**out["hazard_one_step"]}, hz,
                  title=f"Cash mergers: long high-hazard weeks, short low; shift(2), gross; to {last}", controls={"tender offers": ctl})
    (HERE / "results.json").write_text(json.dumps(out, indent=1))

    a = out["announcement_dating"]
    print("panel to", last, "| announced on a session", f"{a['share_announced_on_a_session']:.1%}", "| dateann after / before dateannorig",
          f"{a['share_dateann_after_dateannorig']:.1%} / {a['share_dateann_before_dateannorig']:.1%}")
    print("target return around SDC's date, %:", " ".join(f"{k}:{v['mean_pct']:+.2f}" for k, v in a["target_return_by_session"].items()))
    for k in ("premium_one_step", "premium_one_step_friendly", "premium_tender", "premium_tender_friendly",
              "hazard_one_step", "hazard_one_step_friendly", "hazard_tender"):
        r = out[k]
        print(f"\n== {k}")
        print(explore.table({**r, "controls": r.get("controls", {})}))
        if k.startswith("premium"):
            e, m, hd = r["excess_over_bills"], r["market"], r["hedged_with_rolling_beta"]
            print(f"deals linked {r['deals_linked']:,}, eligible {r['deals_eligible']:,}, live a day (median) {r['deals_active_per_day_median']:.0f}, "
                  f"flat days {r['flat_day_share']:.1%}, held (median) {r['held_sessions_median']:.0f} sessions, turnover/yr {r['turnover_per_year']:.1f}, "
                  f"held name-days with no return while trading {r['held_name_days_with_no_return_while_trading']} of {r['held_name_days']:,} (earned as zero)")
            print(f"over bills: {e['ann_ret']:.2%}/yr, vol {e['ann_vol']:.2%}, Sharpe {e['sharpe']:.2f}, max drawdown {e['max_drawdown']:.2%}")
            print(f"market: beta {m['beta']:.2f} (same day {m['beta_same_day']:.2f}); in {m['months_market_below_minus_4pct']} months below -4%: beta {m['beta_in_those_months']}, "
                  f"mean {m['mean_return_in_those_months']:.2%}; other months beta {m['beta_other_months']:.2f}; alpha {m['alpha_per_year']:.2%}/yr, NW t {m['alpha_t_newey_west']:.2f}")
            print(f"hedged with rolling beta: Sharpe {hd['sharpe']:.2f}, {hd['ann_ret']:.2%}/yr")
            print("small / large targets, Sharpe over bills:", round(r["small_targets"]["excess_over_bills"]["sharpe"], 2), "/", round(r["large_targets"]["excess_over_bills"]["sharpe"], 2),
                  "| attitude-changed flag on", f"{r['attitude_changed_flag_share']:.1%}", "of eligible deals")
            if "event_time_profile_over_bills" in r:
                print("event-time profile over bills, bp/day (t):", " ".join(f"{kk[6:]}:{vv['mean_bp_per_day']:+.1f}({vv['t_by_day']:+.1f})" for kk, vv in r["event_time_profile_over_bills"].items()))
        else:
            print(f"invested days {r['invested_day_share']:.1%}, turnover/yr {r['turnover_per_year']:.1f}, months estimated {r['months_estimated']}, "
                  f"months each block was High {r['months_block_was_high']}")
            print("legs over bills, Sharpe: high", round(r["legs_excess_over_bills"]["high_leg"]["sharpe"], 2), "low", round(r["legs_excess_over_bills"]["low_leg"]["sharpe"], 2),
                  "| return/yr: high", f"{r['legs_excess_over_bills']['high_leg']['ann_ret']:.2%}", "low", f"{r['legs_excess_over_bills']['low_leg']['ann_ret']:.2%}",
                  "| beta", round(r["market"]["beta"], 3))
    print("\ncapacity, premium one-step:", out["premium_one_step"]["capacity_2024_on"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
