"""Checks on the rights-offering test. C1 to C5 were named in explore.py before any return was
read; everything under NP was added on 2026-11-18 AFTER the first results and is NOT pre-specified.

    python3 results/ideas/cef_rights_offerings/explore.py
    QUANTT_ENV_FILE=<env> python3 results/ideas/cef_rights_offerings/edgar_expiry.py     (C5's dates)
    python3 results/ideas/cef_rights_offerings/checks.py

C1  buy-and-hold on closing mid quotes (CRSP `dlybid`/`dlyask`), so a bounce between bid and
    ask at either end is not counted; and the closing spread of what is held.
C2  entry one session later.
C3  the 60-session book hedged with PCEF (tradable, from 2010) instead of the CEF market.
C4  ordinary ex-dates inside each window, event funds against K2 funds: the desk's ex-date
    drift (+22bp before, -30bp after) can explain a gap only if the counts differ.
C5  real expiry dates from EDGAR (112 of 147 events): entry at the first close after the real
    expiry, decided at the close of the expiry day itself (the date is in the prospectus).

NP1 (not pre-specified) the fall itself as a trade: the fund against the CEF market from the
    close of X to X+25, where the ex-date was declared at least two sessions before X by
    CRSP's own date (one session added to it, as the desk does for dividends). A book would
    have to be SHORT the fund to earn it.
NP2 (not pre-specified) how many of these funds are in the desk's own panels.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts.research import explore as ex  # noqa: E402
from scripts.research import harness  # noqa: E402
import explore as E  # noqa: E402  (this idea's own explore.py)

assert pd.get_option("compute.use_numexpr") is False
HERE, STAGE = E.HERE, E.STAGE
DESK = REPO.parents[2] / "data" / "cef"          # read-only; the worktree has no data/ of its own


def brief(s: dict) -> dict:
    return {k: (round(s[k], 4) if s[k] is not None else None) for k in ("ann_ret", "ann_vol", "sharpe", "t")} | {"active": s["n_active_days"]}


def main() -> int:
    P, adv, elig, ev = E.load()
    R0, idx = P["ret"], P["ret"].index
    R = R0.fillna(0.0)
    uni = R0.where(elig.shift(1, fill_value=False)).mean(axis=1).fillna(0.0)
    cols = elig.columns
    is_el = lambda k, d: 0 <= d < len(idx) and bool(elig.iat[d, cols.get_loc(k)])
    ev["eligible"] = [is_el(k, p + E.EXPIRY - 1) for k, p in zip(ev["permno"], ev["p"])]
    by_fund = ev.groupby("permno")["p"].apply(list).to_dict()
    pairs = list(zip(ev["permno"], ev["p"]))
    k2 = E.matched(ev, elig, P["cap"], by_fund)
    out = {"panel_last_date": str(idx.max().date())}

    # ---- C1 mid quotes and spread
    q = pd.read_parquet(STAGE / "quotes.parquet")
    q["date"] = pd.to_datetime(q["date"])
    out["quotes_last_date"] = str(q["date"].max().date())
    ok = (q["bid"] > 0) & (q["ask"] >= q["bid"])
    q = q[ok]
    mid = ((q["bid"] + q["ask"]) / 2).groupby([q["date"], q["permno"]]).last().unstack().reindex(idx)
    spr = ((q["ask"] - q["bid"]) / ((q["bid"] + q["ask"]) / 2)).groupby([q["date"], q["permno"]]).last().unstack().reindex(idx)

    def bh_mid(k, p, a, b):
        """Total-return buy and hold from the mid at the close of p+a-1 to the mid at the close of p+b."""
        v = E.bh(R0, uni, k, p, a, b)
        if v is None or k not in mid.columns:
            return None
        m0, m1, c0, c1 = mid[k].iloc[p + a - 1], mid[k].iloc[p + b], P["prc"][k].iloc[p + a - 1], P["prc"][k].iloc[p + b]
        if not np.isfinite([m0, m1, c0, c1]).all():
            return None
        fund = float((1 + R0[k].iloc[p + a:p + b + 1]).prod()) * (m1 / c1) / (m0 / c0)
        return fund - float((1 + uni.iloc[p + a:p + b + 1]).prod())

    el = ev[ev["eligible"]]
    month = pd.Series([str(idx[min(p + E.EXPIRY, len(idx) - 1)])[:7] for p in el["p"]], index=el.index)
    c1 = {}
    for name, (a, b) in E.WINDOWS.items():
        if a == b:
            continue
        c1[name] = {"close_to_close": E.clustered(pd.Series([E.bh(R0, uni, r.permno, r.p, a, b) for r in el.itertuples()], index=el.index, dtype=float), month),
                    "mid_to_mid": E.clustered(pd.Series([bh_mid(r.permno, r.p, a, b) for r in el.itertuples()], index=el.index, dtype=float), month)}
    sp_entry = pd.Series([spr[r.permno].iloc[r.p + E.EXPIRY] if r.permno in spr.columns and r.p + E.EXPIRY < len(idx) else np.nan for r in el.itertuples()])
    sp_ex = pd.Series([spr[r.permno].iloc[r.p] if r.permno in spr.columns else np.nan for r in el.itertuples()])
    out["C1_mid_quotes"] = c1
    out["closing_spread_bp"] = {"at_entry_X+25": {"median": float(sp_entry.median() * 1e4), "p75": float(sp_entry.quantile(.75) * 1e4), "p90": float(sp_entry.quantile(.9) * 1e4), "n": int(sp_entry.notna().sum())},
                                "on_X": {"median": float(sp_ex.median() * 1e4), "p90": float(sp_ex.quantile(.9) * 1e4)},
                                "at_entry_2016_on_median": float(sp_entry[(el["ex_date"] >= "2016-01-01").to_numpy()].median() * 1e4)}
    out["liquidity_at_entry"] = {"median_adv": float(np.median([adv[r.permno].iloc[min(r.p + 24, len(idx) - 1)] for r in el.itertuples()])),
                                 "median_price": float(np.median([P["prc"][r.permno].iloc[min(r.p + 24, len(idx) - 1)] for r in el.itertuples()])),
                                 "median_cap_musd": float(np.nanmedian([P["cap"][r.permno].iloc[min(r.p + 24, len(idx) - 1)] for r in el.itertuples()]) / 1e3)}

    # ---- C2 one session later
    out["C2_skip_day"] = {}
    for hold in (60, 20):
        s = ex.stats(E.run(pairs, elig, R, hold, offset=E.EXPIRY)[0]["pnl"].loc[idx[60]:])
        out["C2_skip_day"][f"book_hold_{hold}"] = brief(s)
        out["C2_skip_day"][f"per_event_[27,{26 + hold}]"] = E.clustered(pd.Series([E.bh(R0, uni, r.permno, r.p, 27, 26 + hold) for r in el.itertuples()], index=el.index, dtype=float), month)

    # ---- C3 PCEF hedge
    pc = pd.read_parquet(STAGE / "pcef.parquet").set_index("date")["adj_close"].pct_change()
    out["pcef_last_date"] = str(pc.index.max().date())
    L = E.book(pairs, elig, 60)[0]
    long_pnl = harness.evaluate(L, R)["pnl"]
    on = harness.held(L).sum(axis=1) > 0
    pcr = pc.reindex(idx)
    seg = idx[(idx >= pc.dropna().index.min())]
    if pcr.loc[seg].isna().any():
        raise ValueError("PCEF has no return on a CRSP session after its first date")
    vs_pcef = (long_pnl - pcr.where(on, 0.0)).loc[seg]
    vs_mkt = E.run(pairs, elig, R, 60)[0]["pnl"].loc[seg]
    out["C3_pcef_hedge_hold_60"] = {"against_PCEF": brief(ex.stats(vs_pcef)), "against_CEF_market_same_dates": brief(ex.stats(vs_mkt)),
                                    "long_only_same_dates": brief(ex.stats(long_pnl.loc[seg])), "from": str(seg.min().date())}

    # ---- C4 ordinary ex-dates in the windows
    isex = P["div"].fillna(0.0) > 0
    def n_ex(prs, a, b):
        v = [int(isex[k].iloc[p + a:p + b + 1].sum()) for k, p in prs if p + b < len(idx) and is_el(k, p + E.EXPIRY - 1)]
        return float(np.mean(v))
    out["C4_ordinary_ex_dates_per_window"] = {w: {"event_funds": n_ex(pairs, a, b), "K2_funds": n_ex(k2, a, b)}
                                              for w, (a, b) in (("[1,25]", (1, 25)), ("[26,45]", (26, 45)), ("[26,85]", (26, 85)))}

    # ---- C5 real expiry
    xp = pd.read_parquet(STAGE / "expiry.parquet")
    m = ev.merge(xp[["permno", "ex_date", "expiry"]], on=["permno", "ex_date"], how="left")
    have = m[m["expiry"].notna()].copy()
    have["pe"] = idx.searchsorted(have["expiry"])                       # the expiry session (or the first after it)
    have = have[have["pe"] < len(idx)]
    assert (idx[have["pe"]] >= have["expiry"].to_numpy()).all()         # ALIGNMENT: decided no earlier than the expiry day
    have["sessions_to_expiry"] = have["pe"] - have["p"]
    have["el5"] = [is_el(k, d) for k, d in zip(have["permno"], have["pe"])]
    h = have[have["el5"]]
    mon5 = pd.Series([str(idx[min(d + 1, len(idx) - 1)])[:7] for d in h["pe"]], index=h.index)
    c5 = {"events_with_expiry": int(len(have)), "eligible_at_expiry": int(len(h)),
          "sessions_ex_to_expiry": {"median": float(have["sessions_to_expiry"].median()), "p10": float(have["sessions_to_expiry"].quantile(.1)), "p90": float(have["sessions_to_expiry"].quantile(.9))},
          "per_event": {}, "books": {}}
    for name, (a, b) in (("expiry+2 .. +21", (2, 21)), ("expiry+2 .. +61", (2, 61)), ("expiry+22 .. +61", (22, 61)), ("X+1 .. expiry", (None, None))):
        if b is None:
            v = [E.bh(R0, uni, r.permno, r.p, 1, r.pe - r.p) if r.pe > r.p else None for r in h.itertuples()]
        else:
            v = [E.bh(R0, uni, r.permno, r.pe, a, b) for r in h.itertuples()]
        c5["per_event"][name] = E.clustered(pd.Series(v, index=h.index, dtype=float), mon5)
    c5["per_event"]["same events, fixed rule [26,85]"] = E.clustered(pd.Series([E.bh(R0, uni, r.permno, r.p, 26, 85) for r in h.itertuples()], index=h.index, dtype=float), mon5)
    c5["per_event"]["same events, fixed rule [26,45]"] = E.clustered(pd.Series([E.bh(R0, uni, r.permno, r.p, 26, 45) for r in h.itertuples()], index=h.index, dtype=float), mon5)
    p5 = list(zip(have["permno"], have["pe"]))
    for hold in (60, 20):
        # decided at the expiry session (offset 0), filled at the next close, earns expiry+2 .. expiry+hold+1
        c5["books"][f"hold_{hold}"] = brief(ex.stats(E.run(p5, elig, R, hold, offset=0)[0]["pnl"].loc[idx[60]:]))
    c5["books"]["fixed_rule_same_events_hold_60"] = brief(ex.stats(E.run(list(zip(have["permno"], have["p"])), elig, R, 60)[0]["pnl"].loc[idx[60]:]))
    out["C5_real_expiry"] = c5

    # ---- NP1 the fall as a trade (NOT pre-specified)
    dec = pd.to_datetime(ev["declared"])
    dpos = pd.Series(idx.searchsorted(dec.fillna(pd.Timestamp("2100-01-01"))), index=ev.index) + 1      # one session late, as for dividends
    known = dec.notna() & (dpos <= ev["p"] - 1)                          # ALIGNMENT: public by the close of X-1, when the short is decided
    np1 = {"events_declared_in_time": int(known.sum()), "events_no_declaration_date": int(dec.isna().sum())}
    for label, sub in (("declared in time", ev[known]), ("all events (date assumed known) [U]", ev)):
        sub = sub[[is_el(k, p - 1) for k, p in zip(sub["permno"], sub["p"])]]
        mo = pd.Series([str(d)[:7] for d in sub["ex_date"]], index=sub.index)
        pr = list(zip(sub["permno"], sub["p"]))
        res = E.run(pr, elig, R, 25, offset=-1)[0]["pnl"].loc[idx[60]:]
        np1[label] = {"n": int(len(sub)),
                      "per_event_fund_less_market_[1,25]": E.clustered(pd.Series([E.bh(R0, uni, r.permno, r.p, 1, 25) for r in sub.itertuples()], index=sub.index, dtype=float), mo),
                      "per_event_mid_to_mid_[1,25]": E.clustered(pd.Series([bh_mid(r.permno, r.p, 1, 25) for r in sub.itertuples()], index=sub.index, dtype=float), mo),
                      "book_SHORT_fund_long_market": ex.summarise(-res)}
    k2e = [(k, p) for k, p in k2]
    np1["K2_book_SHORT_matched_long_market"] = brief(ex.stats(-E.run(k2e, elig, R, 25, offset=-1)[0]["pnl"].loc[idx[60]:]))
    k1 = [(k, p - E.YEAR) for k, p in pairs if p - E.YEAR >= 0 and all(abs(x - (p - E.YEAR)) > E.CLEAR for x in by_fund[k])]
    np1["K1_book_SHORT_year_earlier_long_market"] = brief(ex.stats(-E.run(k1, elig, R, 25, offset=-1)[0]["pnl"].loc[idx[60]:]))
    out["NP1_fall_as_a_trade_not_prespecified"] = np1

    # ---- NP2 the desk's own funds
    out["NP2_desk_panels"] = {}
    for label, f in (("data/cef (the core book's panel)", DESK / "cef_prices.parquet"), ("data/cef_families", DESK.parent / "cef_families" / "cef_prices.parquet")):
        desk = set(pd.read_parquet(f, columns=["ticker"])["ticker"].astype(str).unique())
        hit = ev[ev["ticker"].isin(desk)]
        out["NP2_desk_panels"][label] = {"panel_tickers": len(desk), "rights_events_in_them": int(len(hit)), "funds": int(hit["ticker"].nunique()),
                                         "since_2016": int((hit["ex_date"] >= "2016-01-01").sum())}

    # ---- NP3 (NOT pre-specified) the late part of the rebound, and whether the controls have it too
    k1e = [(k, p) for k, p in k1 if is_el(k, p + E.EXPIRY - 1)]
    k2e_ = [(k, p) for k, p in k2 if is_el(k, p + E.EXPIRY - 1)]
    def tab(prs, a, b):
        mo = pd.Series([str(idx[min(p + E.EXPIRY, len(idx) - 1)])[:7] for _, p in prs])
        return E.clustered(pd.Series([E.bh(R0, uni, k, p, a, b) for k, p in prs], dtype=float), mo)
    elp = list(zip(el["permno"], el["p"]))
    out["NP3_late_rebound_not_prespecified"] = {w: {"event_funds": tab(elp, a, b), "K1_year_earlier": tab(k1e, a, b), "K2_matched": tab(k2e_, a, b)}
                                                for w, (a, b) in (("[46,85]", (46, 85)), ("[26,85]", (26, 85)), ("[1,85]", (1, 85)), ("[-20,85]", (-20, 85)))}
    (HERE / "checks.json").write_text(json.dumps(out, indent=1, default=str))
    def show(d, ind=0):
        for k, v in d.items():
            if isinstance(v, dict) and any(isinstance(x, dict) for x in v.values()):
                print(" " * ind + str(k)); show(v, ind + 2)
            else:
                print(" " * ind + str(k), {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items()} if isinstance(v, dict) else v)
    show(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
