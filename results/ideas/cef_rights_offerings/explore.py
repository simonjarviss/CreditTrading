"""Explore: closed-end funds after a rights offering expires. Every CEF on CRSP, dead funds included.

    QUANTT_ENV_FILE=<env> python3 results/ideas/cef_rights_offerings/stage.py
    python3 results/ideas/cef_rights_offerings/explore.py

PROVENANCE OF THIS RULE. The lane was started on 2026-11-16 and cut off after `stage.py`
and the event list existed; no explore.py, no results and no card had been written. This
rule was written on 2026-11-18 BEFORE any return was read. What had been read: event counts
by year, the share with a right value and a declaration date, and price, market value and
dollar volume at the ex-date.

FIXED BEFORE LOOKING
  event      a row of CRSP `stkdistributions` with disdetailtype 'SECRD' (subscription rights
             in the fund's own shares) on a CEF permno, ex-rights date X (`disexdt`), 2000 on.
             147 rows on 85 funds; about 7 a year from 2010.
  expiry     CRSP does not carry it (`dispaydt` is the day the rights are handed out, a median
             of 3 days after X). So the lane's stated fallback is THE rule: expiry is taken as
             X + 25 sessions for every event. [U] against the real date; see check C5.
  trade (a)  long the fund from the close of X+25 for H sessions, H = 60 (the headline,
             because the book is invested on more days) and H = 20 (beside it, equal standing).
             Decided at the close of X+24, filled at the close of X+25, earns X+26 .. X+25+H.
             X is public weeks before, so the decision reads only the calendar.
  eligible   price >= $2 and 21-session average dollar volume >= $500,000, both read at the
             decision close (X+24) for the event fund and at each decision close for the hedge.
  weights    calendar time. +1 split equally across event funds in a window; -1 split equally
             across every eligible CEF (the CEF market; not tradable as such, PCEF is the
             tradable stand-in and is check C3). Flat when no event fund is in a window.
  hedge      as above. The long leg alone is shown beside it (the long-only version).
  (b) path   for information: mean cumulative return less the equal-weighted eligible CEF
             market from X-20 to X+60, and buy-and-hold windows [-20,-1], [0], [1,25],
             [26,45], [26,85] per event.
  (c) split  CRSP gives a right a value (`disdivamt`) when the right traded, i.e. the offering
             was transferable; 136 have one, 11 do not. The 11 are shown but are too few to
             read; on them CRSP's return on X is NOT adjusted for the right [U].
  controls   K1 the same funds, same book, with X moved 252 sessions earlier (dropped when
                the fund had a real ex-rights date within 126 sessions of the moved date);
             K2 for each event the three eligible CEFs nearest in log market value at X-1
                with no rights offering of their own within 252 sessions of X, same book.
             If the idea is wrong, K1 and K2 score as well as the event book.
  expected   a fall into and through the subscription period, and a positive return against
             the CEF market after expiry of the order of 1 to 2% over 20 sessions, above
             both controls.
  checks named in advance (in checks.py)
             C1 buy-and-hold [26,45] on closing mid quotes; C2 entry one session later;
             C3 hedge with PCEF from 2010; C4 ordinary ex-dates inside the window, event
             funds against K2 funds (the desk's ex-date drift); C5 real expiry dates read
             from EDGAR prospectuses where they can be parsed, entry at the first close
             after the real expiry.
Returns are CRSP total returns (`dlyret`), which add the right's value back on X, so the
ex-rights price drop is not a return.
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

assert pd.get_option("compute.use_numexpr") is False      # scripts/research/explore.py says why
HERE = Path(__file__).resolve().parent
STAGE = Path.home() / "quantt_research" / "cef_rights_offerings"
PANEL = Path.home() / "quantt_research" / "crsp_cef_daily.parquet"
EXPIRY, MIN_PRICE, MIN_ADV, YEAR, CLEAR = 25, 2.0, 500_000.0, 252, 126
WINDOWS = {"pre [-20,-1]": (-20, -1), "ex day [0]": (0, 0), "subscription [1,25]": (1, 25),
           "after expiry 20 [26,45]": (26, 45), "after expiry 60 [26,85]": (26, 85)}


def load():
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    P = {c: df.pivot(index="date", columns="permno", values=c) for c in ("ret", "prc", "dollar_volume", "cap", "div")}
    adv = P["dollar_volume"].rolling(21, min_periods=10).mean()
    # ALIGNMENT: elig.loc[t] reads price and volume through t only; it is used for decisions made at t.
    elig = (P["prc"] >= MIN_PRICE) & (adv >= MIN_ADV)
    ev = pd.read_parquet(STAGE / "events.parquet")
    ev["ex_date"] = pd.to_datetime(ev["ex_date"])
    idx = P["ret"].index
    ev = ev[ev["permno"].isin(P["ret"].columns) & ev["ex_date"].isin(idx)].copy()
    ev["p"] = idx.get_indexer(ev["ex_date"])
    ev["transferable"] = ev["right_value"].notna()
    return P, adv, elig, ev.reset_index(drop=True)


def book(pairs, elig: pd.DataFrame, hold: int, offset: int = EXPIRY - 1) -> pd.DataFrame:
    """Decided weights. pairs = (permno, p): long from decision row p+offset for `hold` rows,
    if the fund is eligible at that decision close. Hedge -1 across the eligible market."""
    idx, cols = elig.index, elig.columns
    side = np.zeros((len(idx), len(cols)))
    for permno, p in pairs:
        d = p + offset
        if d < 0 or d >= len(idx) or not bool(elig.iat[d, cols.get_loc(permno)]):
            continue
        side[d:min(d + hold, len(idx)), cols.get_loc(permno)] = 1.0
    long_ = pd.DataFrame(side, index=idx, columns=cols)
    n = long_.sum(axis=1)
    e = elig.astype(float)
    ne = e.sum(axis=1)
    on = (n > 0) & (ne > 0)
    L = long_.div(n.where(on), axis=0).fillna(0.0)
    S = e.div(ne.where(on), axis=0).fillna(0.0)
    return L, S


def run(pairs, elig, R, hold, offset=EXPIRY - 1):
    L, S = book(pairs, elig, hold, offset)
    res = harness.evaluate(L - S, R)
    long_only = harness.evaluate(L, R)
    return res, long_only, L


def bh(R: pd.DataFrame, uni: pd.Series, permno, p: int, a: int, b: int):
    """Buy-and-hold return of the fund less the market over sessions p+a .. p+b; None if any is missing."""
    if p + a < 0 or p + b >= len(R):
        return None
    r = R[permno].iloc[p + a:p + b + 1]
    if r.isna().any():
        return None
    return float((1 + r).prod() - (1 + uni.iloc[p + a:p + b + 1]).prod())


def clustered(v: pd.Series, month: pd.Series) -> dict:
    """Mean, median, share positive and a t statistic clustered by calendar month of entry."""
    v = v.dropna()
    if len(v) < 5:
        return {"n": int(len(v))}
    m = v.mean()
    g = (v - m).groupby(month.loc[v.index]).sum()
    se = np.sqrt((g ** 2).sum()) / len(v)
    return {"n": int(len(v)), "mean_bp": float(m * 1e4), "median_bp": float(v.median() * 1e4),
            "share_positive": float((v > 0).mean()), "t_clustered_by_month": float(m / se) if se > 0 else None}


def per_event(ev: pd.DataFrame, R, uni, idx) -> pd.DataFrame:
    out = ev[["permno", "p", "ex_date", "transferable", "eligible"]].copy()
    for k, (a, b) in WINDOWS.items():
        out[k] = [bh(R, uni, r.permno, r.p, a, b) for r in ev.itertuples()]
    out["month"] = [str(idx[min(p + EXPIRY, len(idx) - 1)])[:7] for p in ev["p"]]
    return out


def matched(ev, elig, cap, events_by_fund) -> list:
    """K2: three eligible funds nearest in log market value at X-1, none with an offering within a year of X."""
    out = []
    for r in ev.itertuples():
        if r.p < 1:
            continue
        c = np.log(cap.iloc[r.p - 1].where(elig.iloc[r.p - 1]))
        if r.permno not in c.index or not np.isfinite(cap.iloc[r.p - 1][r.permno]):
            continue
        target = np.log(cap.iloc[r.p - 1][r.permno])
        d = (c - target).abs().dropna().drop(index=r.permno, errors="ignore")
        ok = [q for q in d.sort_values().index if all(abs(x - r.p) > YEAR for x in events_by_fund.get(q, []))][:3]
        out += [(q, r.p) for q in ok]
    return out


def main() -> int:
    P, adv, elig, ev = load()
    R0, idx = P["ret"], P["ret"].index
    last = idx.max().date()
    R = R0.fillna(0.0)                       # a fund with no row has stopped trading (stage_crsp_cefs.py)
    uni = R0.where(elig.shift(1, fill_value=False)).mean(axis=1).fillna(0.0)   # market earned on s: eligible at s-1
    ev["eligible"] = [bool(elig.iat[min(p + EXPIRY - 1, len(idx) - 1), elig.columns.get_loc(k)]) and p + EXPIRY - 1 < len(idx)
                      for k, p in zip(ev["permno"], ev["p"])]
    by_fund = ev.groupby("permno")["p"].apply(list).to_dict()
    pairs = list(zip(ev["permno"], ev["p"]))
    k1 = [(k, p - YEAR) for k, p in pairs if p - YEAR >= 0 and all(abs(x - (p - YEAR)) > CLEAR for x in by_fund[k])]
    k2 = matched(ev, elig, P["cap"], by_fund)

    out = {"panel_last_date": str(last), "events_staged": int(len(ev)), "events_eligible_at_entry": int(ev["eligible"].sum()),
           "events_by_year": {int(k): int(v) for k, v in ev.groupby(ev["ex_date"].dt.year).size().items()},
           "eligible_events_per_year_2010_on": float(ev[ev["eligible"] & (ev["ex_date"] >= "2010-01-01")].shape[0] / 16.0),
           "k1_placebo_events": len(k1), "k2_matched_fund_events": len(k2), "books": {}}
    start = idx[60]
    for hold in (60, 20):
        res, lo, L = run(pairs, elig, R, hold)
        pnl = res["pnl"].loc[start:]
        c1 = run(k1, elig, R, hold)[0]["pnl"]
        c2 = run(k2, elig, R, hold)[0]["pnl"]
        ctr = {"K1 same funds a year earlier": c1, "K2 size-matched, no offering": c2,
               "long leg alone (not hedged)": lo["pnl"]}
        held = harness.held(L) > 0
        gone = int((held & R0.isna()).sum().sum())
        s = explore.summarise(pnl, controls=ctr, extra={
            "turnover_per_year": float(res["turn"]), "event_funds_held_mean_on_active_days": float(held.sum(axis=1)[held.any(axis=1)].mean()),
            "held_name_days_with_no_row": gone,
            "median_price_held": float(P["prc"].where(held).stack().median()),
            "median_adv_held": float(adv.where(held).stack().median()),
            "event_minus_K2": explore.stats((pnl - c2.reindex(pnl.index)))})
        out["books"][f"hold_{hold}"] = s
        if hold == 60:
            explore.write(HERE, s, pnl, title=f"Long CEFs for 60 sessions from ex-rights + 25, short the CEF market; shift(2), gross; to {last}",
                          controls={k: v for k, v in ctr.items() if k.startswith("K")})
        print(f"\n== hold {hold}: turnover/yr {res['turn']:.1f}, funds held {s['event_funds_held_mean_on_active_days']:.2f}, no-row {gone}, "
              f"median price {s['median_price_held']:.2f}, median ADV {s['median_adv_held']:,.0f}")
        print(explore.table(s))
        print("event minus K2:", {k: round(v, 3) for k, v in s["event_minus_K2"].items() if k in ("sharpe", "t", "ann_ret")})

    # per-event buy-and-hold, fund less market
    pe = per_event(ev, R0, uni, idx)
    pe.to_parquet(STAGE / "per_event.parquet", index=False)          # licensed rows: outside the repository
    tab = {}
    for name, sub in (("eligible events", pe[pe["eligible"]]), ("all events", pe),
                      ("eligible, transferable", pe[pe["eligible"] & pe["transferable"]]),
                      ("eligible, no right value", pe[pe["eligible"] & ~pe["transferable"]]),
                      ("eligible, 2010 on", pe[pe["eligible"] & (pe["ex_date"] >= "2010-01-01")])):
        tab[name] = {k: clustered(sub[k], sub["month"]) for k in WINDOWS}
    for cname, cpairs in (("K1 a year earlier", k1), ("K2 matched", k2)):
        ce = pd.DataFrame(cpairs, columns=["permno", "p"])
        ce["ok"] = [bool(elig.iat[min(p + EXPIRY - 1, len(idx) - 1), elig.columns.get_loc(k)]) for k, p in cpairs]
        ce = ce[ce["ok"]].reset_index(drop=True)
        ce["month"] = [str(idx[min(p + EXPIRY, len(idx) - 1)])[:7] for p in ce["p"]]
        tab[cname] = {k: clustered(pd.Series([bh(R0, uni, r.permno, r.p, a, b) for r in ce.itertuples()], dtype=float), ce["month"])
                      for k, (a, b) in WINDOWS.items()}
    out["per_event_buy_and_hold_less_market"] = tab
    print("\nper event, buy and hold, fund less market (bp): n / mean / median / share positive / t clustered")
    for name, t in tab.items():
        print(f"  {name}")
        for k, v in t.items():
            print(f"    {k:26s}", v["n"], *(f"{v[x]:+.0f}" if "bp" in x else f"{v[x]:.2f}" for x in ("mean_bp", "median_bp", "share_positive", "t_clustered_by_month") if x in v))

    # (b) the path, eligible events with every session present
    rel = R0.sub(uni, axis=0)
    paths = []
    for r in ev[ev["eligible"]].itertuples():
        if r.p - 20 >= 0 and r.p + 85 < len(idx):
            v = rel[r.permno].iloc[r.p - 20:r.p + 86].to_numpy()
            if not np.isnan(v).any():
                paths.append(v)
    car = np.cumsum(np.array(paths), axis=1)
    out["path_mean_cumulative_bp"] = {"n": int(len(paths)), **{f"X{k:+d}": float(car[:, k + 20].mean() * 1e4)
                                      for k in (-20, -10, -5, -1, 0, 1, 5, 10, 15, 20, 25, 30, 35, 45, 60, 85)}}
    print("\npath (bp, cumulative from X-20):", {k: round(v) for k, v in out["path_mean_cumulative_bp"].items()})

    # by era, the per-event headline
    pe_e = pe[pe["eligible"]]
    out["per_event_by_era"] = {}
    for a, b in explore.ERAS + (("2000-01-01", "2001-12-31"),):
        sub = pe_e[(pe_e["ex_date"] >= a) & (pe_e["ex_date"] <= b)]
        out["per_event_by_era"][f"{a[:4]}-{b[:4]}"] = {k: clustered(sub[k], sub["month"]) for k in ("after expiry 20 [26,45]", "after expiry 60 [26,85]", "subscription [1,25]")}
    print(json.dumps(out["per_event_by_era"], indent=0)[:3000])
    res_all = json.loads((HERE / "results.json").read_text())
    (HERE / "results.json").write_text(json.dumps({"headline_hold_60": res_all, **out}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
