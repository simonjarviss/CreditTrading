"""Explore: what happens to a share after it leaves, or joins, the S&P SmallCap 600.

    QUANTT_ENV_FILE=<env> python3 results/ideas/sp600_changes/stage.py
    python3 results/ideas/sp600_changes/explore.py

WHY: funds front-run S&P 500 changes; the 600 and the 400 get less attention, and a share
dropped from the 600 altogether is a small loser that index funds had to sell whatever the
price. If that selling pushes it below where it belongs, it should recover afterwards. The
census of 2026-10-19 (row D8) looked only at the run-up from announcement to effective date,
called it "likely waste" because the move is on a day shift(2) cannot trade, and wrote that
"a post-effective reversal form would be a new idea with its own gate". This is that form.
No return on it had been read on this desk.

THE DATA LIMIT, stated before anything else. R2 has no dated membership history: Compustat
`idxcst_his` holds today's members only. Membership is read from the MONTH-END holdings of
the index ETFs in CRSP Mutual Funds (IJR = 600, IJH = 400, IVV = 500). So a change is known
to the month, not the day, and this book enters 1 to about 23 sessions AFTER the effective
date. A rebound that is over within days of the change is partly or wholly missed. This is
a later entry than the lane asked for ("first close after the effective date"); it is not
that test.

FIXED BEFORE ANY RETURN WAS READ (2026-11-16). Only report counts and holdings counts per
report had been read (IJR is monthly from 2008-02, about 600 rows a report).
  LIST      a fund's list at report date r = the CRSP permnos in its holdings at r.
  STEP      two consecutive reports r0 < r1 not more than 35 days apart.
  DELETION  in the list at r0 and at the report before r0, absent at r1.
  ADDITION  in the list at r1, absent at r0 and at the report before r0.
  CLASS     a 600 deletion is OUT if at r1 it is in neither IJH nor IVV (it left the S&P
            1500 or was dropped for cause), UP if it is (promoted). A 600 addition is NEW if
            at r0 it was in neither IJH nor IVV, DOWN if it was. The same words for the 400
            (UP = to the 500, DOWN = to the 600) and the 500 (DOWN = to the 400 or 600).
  DECIDED   d = the first CRSP session strictly AFTER r1: a fund's holdings as of a close
            are public the next morning (and S&P announces changes before they take
            effect), so nothing unannounced is used. Filled at the close of d+1; earns the
            returns of d+2 onward (shift(2), harness.evaluate).
  ELIGIBLE  at d: a US common share with a CRSP return and volume that day (it still
            trades: a completed merger is gone), price $1 or more.
  BOOKS     (a) LONG 600 OUT deletions, held 20 and 60 sessions, against IWM.
            (b) 600 NEW additions, held 20 and 60 sessions, shown LONG against IWM; the
                idea (give-back) expects a NEGATIVE number, i.e. the short earns.
            Calendar-time: equal weight across live events, 100% gross per side, hedge
            100% IWM; FLAT on a day with fewer than 3 live names.
            The 400 and the 500, and the UP / DOWN classes, are reported the same way,
            separately, as description.
  PER EVENT buy and hold, no rebalancing: the share's compounded return over sessions
            d+2 .. d+1+H less IWM's over the same sessions, H = 20 and 60. Mean, median,
            share positive, and a t on monthly cohort means (events in one month share a
            decision date and are not independent).
  CONTROLS  C1 the same shares 60 sessions earlier (decided at d-60 sessions).
            C2 size-matched non-members: at d, the 5 eligible shares nearest in log market
               value that are in none of IJR / IJH / IVV at r1 and r0.
            C3 size-and-loser matched: among the 30 such nearest in size, the 5 nearest in
               their return over the 126 sessions to d. A dropped share is a small loser;
               the forced-selling story needs the deletions above C3, not just above IWM.
            C2 and C3 run on the treatment's own live days.
  EXPECTED  (a) positive against IWM and above C3; (b) negative against IWM and below C2.
  DESCRIPTIVE ONLY: events a year, market value, price, 21-session dollar volume, the
            closing bid-ask spread on the fill day, turnover, held name-days with no return
            (a delisted share: counted as zero AFTER CRSP's delisting return is booked).
FIX MADE AFTER THE INTERRUPTION (2026-11-18; the first run was cut off on 2026-11-16 before
any return was read: no results.json existed and the daily panel was a 0-byte file). CRSP
leaves some real shares in a fund's holdings WITHOUT a permno in some reports (counted
2026-11-18, before any return: 23 of 1,203 raw IJR disappearances and 18 of 1,224 raw
appearances are a share whose CUSIP or ticker is still in the fund, unmapped). Read
literally, the rule above would call those deletions and additions. A change is now dropped
when the share's CUSIP or ticker is in the same fund, without a permno, at the report on the
other side of the step. Nothing else in the rule was changed.
Gross; no cost is modelled. Writes results.json beside this file (aggregates only) and the
event list, which is derived from licensed rows, under ~/quantt_research/sp600_changes/.
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
OUT = RES / "sp600_changes"
MAX_GAP_DAYS, MIN_PRICE, MIN_LIVE, N_MATCH, N_POOL, PAST = 35, 1.0, 3, 5, 30, 126
HOLDS = (20, 60)
PLACEBO_SHIFT = 60
INDEX_FUND = {"600": "IJR", "400": "IJH", "500": "IVV"}
OTHERS = {"600": ("IJH", "IVV"), "400": ("IJR", "IVV"), "500": ("IJR", "IJH")}
UNMAPPED: dict = {}     # (fund, report) -> CUSIPs and tickers held without a permno
IDS: dict = {}          # (fund, report) -> permno -> its CUSIP and ticker in that report
DROPPED_UNMAPPED = {"DEL": 0, "ADD": 0}


def load():
    h = pd.read_parquet(OUT / "holdings.parquet")
    h["report_dt"] = pd.to_datetime(h["report_dt"])
    # Unmapped rows (no permno) that carry a CUSIP or ticker: the guard against a false change.
    un = h[h["permno"].isna()]
    UNMAPPED.update({k: set(g["cusip"].dropna()) | set(g["ticker"].dropna()) for k, g in un.groupby(["fund", "report_dt"])})
    m = h[h["permno"].notna()]
    for (f, r), g in m.groupby(["fund", "report_dt"]):
        IDS[(f, r)] = {int(p): {x for x in (c, t) if isinstance(x, str)} for p, c, t in zip(g["permno"], g["cusip"], g["ticker"])}
    h = m.copy()
    h["permno"] = h["permno"].astype(int)
    lists = {f: {r: set(g["permno"]) for r, g in h[h["fund"] == f].groupby("report_dt")} for f in h["fund"].unique()}
    px = pd.read_parquet(OUT / "daily.parquet")
    px["date"] = pd.to_datetime(px["date"])
    return lists, px


def events(lists: dict, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """One row per membership change, with its class and its decision session."""
    rows = []
    for idx, fund in INDEX_FUND.items():
        reps = sorted(lists[fund])
        for i in range(2, len(reps)):
            rm1, r0, r1 = reps[i - 2], reps[i - 1], reps[i]
            if (r1 - r0).days > MAX_GAP_DAYS or (r0 - rm1).days > MAX_GAP_DAYS:
                continue
            a, b = OTHERS[idx]
            if r1 not in lists[a] or r1 not in lists[b] or r0 not in lists[a] or r0 not in lists[b]:
                continue                                     # the class needs the other two funds on both dates
            later = sessions[sessions > r1]
            if len(later) == 0:
                continue
            d = later[0]
            assert d > r1                                    # ALIGNMENT: decided strictly after the report date
            prev, now, before = lists[fund][r0], lists[fund][r1], lists[fund][rm1]
            oth1, oth0 = lists[a][r1] | lists[b][r1], lists[a][r0] | lists[b][r0]
            big = {"600": lists["IJH"][r1] | lists["IVV"][r1], "400": lists["IVV"][r1], "500": set()}[idx]
            big0 = {"600": lists["IJH"][r0] | lists["IVV"][r0], "400": lists["IVV"][r0], "500": set()}[idx]
            for p in (prev & before) - now:
                if IDS[(fund, r0)][p] & UNMAPPED.get((fund, r1), set()):
                    DROPPED_UNMAPPED["DEL"] += 1             # still held at r1, only its permno is missing
                    continue
                cls = "OUT" if p not in oth1 else ("UP" if p in big else "DOWN")
                rows.append((idx, "DEL", cls, p, r1, d))
            for p in now - prev - before:
                if IDS[(fund, r1)][p] & (UNMAPPED.get((fund, r0), set()) | UNMAPPED.get((fund, rm1), set())):
                    DROPPED_UNMAPPED["ADD"] += 1             # already held before r1, only its permno was missing
                    continue
                cls = "NEW" if p not in oth0 else ("DOWN" if p in big0 else "UP")
                rows.append((idx, "ADD", cls, p, r1, d))
    return pd.DataFrame(rows, columns=["index", "kind", "cls", "permno", "r1", "decided"])


def main() -> int:
    lists, px = load()
    sessions = pd.DatetimeIndex(sorted(px["date"].unique()))
    ev = events(lists, sessions)
    yf = pd.read_parquet(RES / "yf_daily.parquet")
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda x: pd.to_datetime(x["date"])).set_index("date")["ret_total"].reindex(sessions)
    if iwm.loc[sessions[1]:].isna().any():
        raise ValueError("IWM has no return on a CRSP session")

    ret = px.pivot(index="date", columns="permno", values="ret")
    prc = px.pivot(index="date", columns="permno", values="prc").abs()
    cap = px.pivot(index="date", columns="permno", values="cap")
    vol = px.pivot(index="date", columns="permno", values="vol")
    dv = px.pivot(index="date", columns="permno", values="dollar_volume")
    spread = ((px["ask"] - px["bid"]) / ((px["ask"] + px["bid"]) / 2)).where((px["bid"] > 0) & (px["ask"] >= px["bid"]))
    spr = px.assign(s=spread).pivot(index="date", columns="permno", values="s")
    del px
    adv = dv.rolling(21, min_periods=10).mean()
    logcum = np.log1p(ret.fillna(0.0)).cumsum()
    pos = {d: i for i, d in enumerate(sessions)}

    # eligibility and descriptive fields at the decision session (all dated d or earlier)
    ev = ev[ev["permno"].isin(ret.columns)].copy()
    get = lambda F, r: F.at[r.decided, r.permno]
    ev["ret_d"] = [get(ret, r) for r in ev.itertuples()]
    ev["prc_d"] = [get(prc, r) for r in ev.itertuples()]
    ev["vol_d"] = [get(vol, r) for r in ev.itertuples()]
    ev["cap_d"] = [get(cap, r) for r in ev.itertuples()]
    ev["adv_d"] = [get(adv, r) for r in ev.itertuples()]
    n_all = ev.groupby(["index", "kind", "cls"]).size()
    ev = ev[ev["ret_d"].notna() & (ev["vol_d"] > 0) & (ev["prc_d"] >= MIN_PRICE) & (ev["cap_d"] > 0)].copy()
    ev["di"] = ev["decided"].map(pos)
    ev = ev[ev["di"] + 2 < len(sessions)].copy()
    ev["spread_fill"] = [spr.iat[r.di + 1, spr.columns.get_loc(r.permno)] for r in ev.itertuples()]
    ev["past126"] = [logcum.iat[r.di, logcum.columns.get_loc(r.permno)] - logcum.iat[r.di - PAST, logcum.columns.get_loc(r.permno)]
                     if r.di >= PAST and not np.isnan(ret.iat[r.di - PAST, ret.columns.get_loc(r.permno)]) else np.nan
                     for r in ev.itertuples()]

    # controls C2 and C3: chosen from data dated d or earlier only
    members_at = {}
    for r1 in ev["r1"].unique():
        r1 = pd.Timestamp(r1)
        s = set()
        for f in ("IJR", "IJH", "IVV"):
            reps = [x for x in sorted(lists[f]) if x <= r1][-2:]
            for x in reps:
                s |= lists[f][x]
        members_at[r1] = s
    c2, c3 = [], []
    for d, g in ev.groupby("decided"):
        i = pos[d]
        ok = ret.iloc[i].notna() & (vol.iloc[i] > 0) & (prc.iloc[i] >= MIN_PRICE) & (cap.iloc[i] > 0)
        pool = ok[ok].index.difference(pd.Index(sorted(members_at[pd.Timestamp(g["r1"].iloc[0])] | set(ev.loc[ev["decided"] == d, "permno"]))))
        lc = np.log(cap.iloc[i][pool])
        if i >= PAST:
            past = (logcum.iloc[i] - logcum.iloc[i - PAST])[pool].where(ret.iloc[i - PAST][pool].notna())
        else:
            past = pd.Series(np.nan, index=pool)
        for r in g.itertuples():
            near = (lc - np.log(r.cap_d)).abs().nsmallest(N_POOL)
            for p in near.index[:N_MATCH]:
                c2.append((r.Index, p))
            if not np.isnan(r.past126):
                pp = (past[near.index] - r.past126).abs().dropna().nsmallest(N_MATCH)
                for p in pp.index:
                    c3.append((r.Index, p))
    c2 = pd.DataFrame(c2, columns=["event", "permno"]); c3 = pd.DataFrame(c3, columns=["event", "permno"])

    keep = sorted(set(ev["permno"]) | set(c2["permno"]) | set(c3["permno"]))
    Rraw = ret[keep]
    R = Rraw.fillna(0.0).copy()
    R.columns = [str(c) for c in R.columns]
    R["IWM"] = iwm
    R = R.iloc[1:]
    Rraw = Rraw.iloc[1:]
    idx = R.index
    cols = list(R.columns)
    Rn = R.to_numpy()
    cpos = {c: j for j, c in enumerate(cols)}
    ipos = {d: i for i, d in enumerate(idx)}
    iw = cpos["IWM"]

    def bh(permno: int, d: pd.Timestamp, H: int, skip: int = 0):
        """Buy and hold: compounded return over sessions d+2+skip .. d+1+H less IWM's. None if the window runs off the panel."""
        i = ipos[d]
        a, b = i + 2 + skip, i + 2 + H
        if b > len(idx):
            return None
        s = np.prod(1 + Rn[a:b, cpos[str(permno)]]) - 1
        m = np.prod(1 + Rn[a:b, iw]) - 1
        return s - m

    def per_event(rows: pd.DataFrame, H: int, shift: int = 0, skip: int = 0, permnos=None) -> dict:
        vals, coh = [], []
        for k, r in enumerate(rows.itertuples()):
            i = ipos.get(r.decided)
            if i is None or i - shift < 0:
                continue
            d = idx[i - shift]
            for p in ([r.permno] if permnos is None else permnos.get(r.Index, [])):
                v = bh(p, d, H, skip)
                if v is not None:
                    vals.append(v); coh.append(d)
        if len(vals) < 5:
            return {"n": len(vals)}
        v = pd.Series(vals, index=pd.DatetimeIndex(coh))
        cm = v.groupby(level=0).mean()
        return {"n": int(len(v)), "cohorts": int(len(cm)), "mean": float(v.mean()), "median": float(v.median()),
                "share_positive": float((v > 0).mean()), "cohort_mean": float(cm.mean()),
                "cohort_t": float(cm.mean() / cm.std() * np.sqrt(len(cm))) if len(cm) > 2 and cm.std() > 0 else None,
                "p10": float(v.quantile(0.1)), "p90": float(v.quantile(0.9))}

    def book(rows: pd.DataFrame, H: int, shift: int = 0, permnos=None, mask=None):
        """Calendar-time long book against IWM; flat under MIN_LIVE live events."""
        e = []
        live = np.zeros(len(idx))
        for r in rows.itertuples():
            i = ipos.get(r.decided)
            if i is None or i - shift < 0:
                continue
            live[i - shift:i - shift + H] += 1
            for p in ([r.permno] if permnos is None else permnos.get(r.Index, [])):
                e.append((idx[i - shift], str(p), 1))
        e = pd.DataFrame(e, columns=["decided", "ticker", "side"])
        H_ = harness.event_weights(e, idx, cols, hold=H, sizing="calendar_time")
        on = (live >= MIN_LIVE) if mask is None else mask
        H_ = H_.mul(pd.Series(on.astype(float), index=idx), axis=0)
        H_["IWM"] = -H_.drop(columns="IWM").sum(axis=1)
        res = harness.evaluate(H_, R)
        hd = harness.held(H_.drop(columns="IWM"))
        miss = int(((hd.to_numpy() != 0) & Rraw.isna().to_numpy()).sum())
        return res["pnl"].iloc[harness.EXEC_LAG:], {"turnover_per_year": float(res["turn"]), "days_live": int(on.sum()),
                                                    "mean_live_events": float(live[live >= MIN_LIVE].mean()) if (live >= MIN_LIVE).any() else 0.0,
                                                    "held_name_days": int((hd.to_numpy() != 0).sum()), "held_name_days_without_return": miss}, on

    out = {"panel_last_date": str(sessions[-1].date()), "iwm_last_date": str(iwm.dropna().index.max().date()),
           "first_decision": str(ev["decided"].min().date()), "last_decision": str(ev["decided"].max().date()),
           "fixed": {"max_gap_days": MAX_GAP_DAYS, "min_price": MIN_PRICE, "min_live": MIN_LIVE, "n_match": N_MATCH,
                     "n_pool": N_POOL, "past_sessions": PAST, "holds": HOLDS, "placebo_shift": PLACEBO_SHIFT},
           "changes_dropped_as_unmapped_not_changed": dict(DROPPED_UNMAPPED),
           "changes_before_eligibility": {"/".join(k): int(v) for k, v in n_all.items()}, "groups": {}}
    fmt = lambda v: "n/a" if v is None else f"{v:.2f}"       # a half with no live day has no Sharpe (crash fixed 2026-11-18)
    c2m = c2.groupby("event")["permno"].apply(list).to_dict(); c3m = c3.groupby("event")["permno"].apply(list).to_dict()
    for (ix, kind, cls), g in ev.groupby(["index", "kind", "cls"]):
        name = f"{ix} {kind} {cls}"
        if len(g) < 30:
            out["groups"][name] = {"events": int(len(g)), "note": "under 30 events: not scored"}
            continue
        info = {"events": int(len(g)), "per_year": {int(k): int(v) for k, v in g.groupby(g["decided"].dt.year).size().items()},
                "median_cap_usd": float(g["cap_d"].median() * 1000), "median_price": float(g["prc_d"].median()),
                "median_adv_usd": float(g["adv_d"].median()), "p10_adv_usd": float(g["adv_d"].quantile(0.1)),
                "median_spread_fill_day": float(g["spread_fill"].median()), "p90_spread_fill_day": float(g["spread_fill"].quantile(0.9)),
                "median_past126": float(np.expm1(g["past126"].median())), "holds": {}}
        primary = name in ("600 DEL OUT", "600 ADD NEW")
        print(f"\n=== {name}{'  [PRIMARY]' if primary else ''}: {len(g)} events, median cap ${info['median_cap_usd'] / 1e6:,.0f}M, price ${info['median_price']:.2f}, "
              f"ADV ${info['median_adv_usd'] / 1e6:.2f}M, spread {info['median_spread_fill_day']:.4f}, past-126 {info['median_past126']:+.1%}")
        for H in HOLDS:
            pnl, binfo, on = book(g, H)
            p1, _, _ = book(g, H, shift=PLACEBO_SHIFT)
            p2, _, _ = book(g, H, permnos=c2m, mask=on)
            p3, _, _ = book(g, H, permnos=c3m, mask=on)
            if (pnl != 0).sum() < 120:
                info["holds"][H] = {"note": "fewer than 120 live days", **binfo,
                                    "per_event": per_event(g, H), "per_event_C3": per_event(g, H, permnos=c3m)}
                continue
            res = explore.summarise(pnl, controls={"C1 same shares 60 sessions earlier": p1, "C2 size-matched": p2, "C3 size-and-loser matched": p3})
            diff = {}
            for lab, c in (("less C2", p2), ("less C3", p3)):
                dd = pnl - c
                s = explore.stats(dd)
                diff[lab] = {**s, "halves": [explore.stats(dd.iloc[:len(dd) // 2])["sharpe"], explore.stats(dd.iloc[len(dd) // 2:])["sharpe"]]}
            pe = {"treatment": per_event(g, H), "treatment_skip_1_day": per_event(g, H, skip=1),
                  "C1": per_event(g, H, shift=PLACEBO_SHIFT), "C2": per_event(g, H, permnos=c2m), "C3": per_event(g, H, permnos=c3m)}
            info["holds"][H] = {**binfo, **res, "differences": diff, "per_event": pe}
            print(f"\n-- hold {H}: live {binfo['days_live']} days, {binfo['mean_live_events']:.1f} events live, turnover {binfo['turnover_per_year']:.1f}/yr, "
                  f"no-return name-days {binfo['held_name_days_without_return']} of {binfo['held_name_days']}")
            print(explore.table(res))
            for lab, s in diff.items():
                print(f"   {lab}: SR {s['sharpe']:.2f} (t {s['t']:.2f}), {s['ann_ret']:.2%} a year, halves {fmt(s['halves'][0])} / {fmt(s['halves'][1])}")
            for lab, s in pe.items():
                if s.get("n", 0) >= 5:
                    print(f"   per event {lab}: n {s['n']}, mean {s['mean']:+.2%}, median {s['median']:+.2%}, positive {s['share_positive']:.0%}, cohort t {s['cohort_t'] if s['cohort_t'] is None else round(s['cohort_t'], 2)}")
        out["groups"][name] = info
    ev.assign(n_c2=ev.index.map(lambda k: len(c2m.get(k, []))), n_c3=ev.index.map(lambda k: len(c3m.get(k, [])))).to_parquet(OUT / "events.parquet")
    c2.to_parquet(OUT / "c2.parquet"); c3.to_parquet(OUT / "c3.parquet")
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
