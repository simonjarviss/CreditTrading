"""Explore: term and target-term closed-end funds in their last year. Every CEF on CRSP, dead included.

    QUANTT_ENV_FILE=<env> python3 results/ideas/cef_term_trusts/stage.py          # CRSP rows from 1990
    python3 results/ideas/cef_term_trusts/explore.py --list                       # the list, counts, liquidity: no return is read
    QUANTT_ENV_FILE=<env> python3 results/ideas/cef_term_trusts/stage.py --yahoo  # ETFs and X<TICKER>X NAVs
    python3 results/ideas/cef_term_trusts/explore.py

RESUMED RUN. The lane was started on 2026-11-16 and cut off when the editor was force quit.
No explore.py and no rule survived on disk (only three small staged tables and a zero-byte
panel), so THIS docstring, written on 2026-11-18 after reading names, counts and delisting
codes and before reading any return, is the pre-specified rule.

FIXED BEFORE LOOKING
  term fund  a CRSP closed-end fund (`securitysubtype = 'CEF'`) whose issuer name IN FORCE ON
             THE DAY (stocknames_v2 date ranges) matches TERM / TM / TRM / T T / TT / TGT /
             TRGT / TARGET / WDGT / MATURITY / DEFINEDTERM / DEFINED OPP or carries a year,
             and does not match LONG TERM, SH TM, LTD TRM, DEFINED STRATEGY, a trailing
             "INC TM", or a year earlier than the fund's first CRSP row. The scheduled year Y
             is the year in the name (four digits, or two as in "TM TR 95", "DEC18", "24 TT";
             two digits count only beside a term word: the --list run, before any return,
             showed "DOW 30" funds read as 2030, and the rule was tightened then).
             A term fund whose name holds no year has no date known in advance from CRSP
             alone and appears only in the hindsight table.
  eligible   price of $2 or more and a 21-session average dollar volume of $100,000 or more,
             both read at the decision close (a $100k to $1M book; these funds are small).
             The same book on $500,000 a day is reported beside it.
  T250       (the headline) at the last session of year Y-1, buy every eligible fund whose name
             that day carries the year Y. Decide at that close, fill at the next close, earn
             from the session after (shift(2), canonical harness). Hold to the fund's last
             CRSP row (the delisting return is in CRSP's last daily return) or, if it is still
             listed, to the last session of year Y. Equal weights across the funds held, 100%
             long when at least one is held, flat otherwise.
  T120, T60  the same entered at the last session of June and of September of year Y.
  hedges     (a) the equal-weighted return of every eligible CEF that was never a term fund
             (the CEF market: not tradable, PCEF is its proxy from 2010); (b) a bond ETF matched
             by the name on the decision day: MUN -> MUB; HIGH / HI / CR / CREDIT / FLTG / FL /
             FLOAT / SR / CONV / EMERG / PFD / ALCENTRA -> HYG; everything else -> AGG. An event
             before its ETF existed is left out of the ETF table and counted. Long only is
             shown unhedged first: most of these funds cannot be borrowed and need not be.
  control    for each event, the funds that were NEVER term funds, whose issuer name on the
             decision day starts with the same word (the sponsor) and agrees on MUN / not MUN
             (the category), eligible that day, held over the same sessions. If term funds earn
             only what their sponsor's ordinary funds of the same kind earn, the dated pull
             adds nothing. An event with no such fund is left out of the matched comparison
             and counted, never given a substitute.
  placebo    in the hindsight table, the same fund over the window of equal length that ends
             where the real window begins (sessions L-2K+1 .. L-K).
  hindsight  every fund whose name at its last CRSP row L was a term name: total return over
  table      the last 250, 120 and 60 sessions (L-K+1 .. L), raw, less the CEF market, less the
             ETF, less the control, by outcome (liquidated / merged or exchanged). The window
             is placed with L, which nobody knew in advance to the day; funds that extended or
             converted to perpetual are by construction not in it. It describes; T250 tests.
  with NAV   where Yahoo serves X<TICKER>X or the desk's panels hold the fund: the discount at
             the T250 decision close, and the T250 per-event return split at a discount of 3%
             or more. Yahoo keeps NAVs mostly for LIVE funds, so this half is survivorship
             biased; the count of events it covers is printed beside the count it does not.
  expected   the desk's census (CEF_CORP_ACTION_CENSUS_2026-10-15) found term funds within
             about 1% of NAV before termination, so I expect T250 unhedged to earn roughly a
             short bond fund's return, the excess over the matched ETF and over the control to
             be under 1% per event and not distinguishable from zero, and the 3% discount
             bucket to hold very few events. The idea survives only if the per-event excess
             over BOTH the ETF and the control is positive with t above 2 and larger than the
             closing spread.

ALIGNMENT (asserted in `events()`): an event decided at session D reads the name row in force
on D, the price on D and dollar volume through D, and its first earned return is D+2.
Returns are CRSP total returns: a distribution's ex-date drop is not a loss here.
NO NAV in CRSP; licensed rows stay under ~/quantt_research/; results.json holds aggregates.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False      # scripts/research/explore.py says why
HERE = Path(__file__).resolve().parent
STAGE = Path.home() / "quantt_research" / "cef_term_trusts"
MIN_PRICE, MIN_ADV, STRICT_ADV = 2.0, 100_000.0, 500_000.0
TERM_RX = re.compile(r"\bTERM\b|\bTM\b|\bTRM\b|\bT T\b|\bTT\b|\bTGT\b|\bTRGT\b|TARGET|\bWDGT\b|MATURITY|DEFINEDTERM|DEFINED OPP")
NOT_RX = re.compile(r"LONG TERM|\bSH TM\b|LTD TRM|DEFINED STRATEGY|INC TM$")
Y4_RX = re.compile(r"(?<!\d)((?:19|20)\d\d)(?!\d)")
Y2_RX = re.compile(r"(?:\b|(?<=[A-Z]))(\d\d)\b")
HY_RX = re.compile(r"\bHIGH\b|\bHI\b|\bCR\b|CREDIT|FLTG|\bFL\b|FLOAT|\bSR\b|\bCONV\b|EMERG|\bPFD\b|ALCENTRA")
BOOKS = {"T250": (12, -1), "T120": (6, 0), "T60": (9, 0)}     # decision month end, and year offset from Y


def name_year(nm: str) -> int | None:
    m = Y4_RX.search(nm)
    if m:
        return int(m.group(1))
    m = Y2_RX.search(nm) if TERM_RX.search(nm) else None      # two digits are a year only beside a term word ("TM TR 95", "24 TT"); "DOW 30" is not one
    if m:
        y = int(m.group(1))
        return 1900 + y if y >= 88 else 2000 + y
    return None


def classify(names: pd.DataFrame, first_row: pd.Series) -> pd.DataFrame:
    """One row per name interval: is_term, year. A year before the fund first traded is a
    vintage, not a termination (AMERICA FIRST FINL FD 1987)."""
    n = names.copy()
    n["year"] = n["issuernm"].map(name_year)
    first = n["permno"].map(first_row).dt.year
    n.loc[n["year"] < first, "year"] = np.nan
    key = n["issuernm"].str.contains(TERM_RX) | n["year"].notna()
    n["is_term"] = key & ~n["issuernm"].str.contains(NOT_RX)
    n.loc[~n["is_term"], "year"] = np.nan
    n["muni"] = n["issuernm"].str.contains("MUN")
    n["sponsor"] = n["issuernm"].str.split().str[0]
    n["etf"] = np.where(n["muni"], "MUB", np.where(n["issuernm"].str.contains(HY_RX), "HYG", "AGG"))
    return n


def name_on(n: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """The name row in force on `day`, per permno (point in time: no later name is read)."""
    x = n[(n["namedt"] <= day) & (n["nameenddt"] >= day)]
    return x.drop_duplicates("permno", keep="last").set_index("permno")


def load():
    df = pd.read_parquet(STAGE / "crsp_cef_daily_1990.parquet")
    df["date"] = pd.to_datetime(df["date"])
    piv = lambda c: df.pivot(index="date", columns="permno", values=c)
    P = {c: piv(c) for c in ("ret", "prc", "dollar_volume", "bid", "ask")}
    names = pd.read_parquet(STAGE / "names.parquet")
    for c in ("namedt", "nameenddt"):
        names[c] = pd.to_datetime(names[c])
    dl = pd.read_parquet(STAGE / "delists.parquet").drop_duplicates("permno", keep="last").set_index("permno")
    return df, P, names, dl


def etf_returns(cal: pd.DatetimeIndex) -> pd.DataFrame:
    out = {}
    for f in sorted((STAGE / "yahoo_etf").glob("*.parquet")):
        h = pd.read_parquet(f)
        if len(h):
            out[f.stem] = h.set_index("Date")["Adj Close"].pct_change()
    if not out:
        raise SystemExit("no ETF series staged: run stage.py --yahoo")
    return pd.DataFrame(out).reindex(cal)


def events(n, P, cal, last_row, min_adv) -> tuple[pd.DataFrame, dict]:
    """Every (book, fund, decision day). Counts what was dropped and why."""
    adv = P["dollar_volume"].rolling(21, min_periods=10).mean()
    rows, drop = [], {"not_listed_at_decision": 0, "ineligible": 0, "dead_before_first_earned_session": 0}
    years = pd.Series(cal.year, index=cal)
    for book, (month, off) in BOOKS.items():
        for yr in sorted(set(cal.year)):
            in_m = cal[(cal.year == yr) & (cal.month == month)]
            if not len(in_m):
                continue
            D = in_m[-1]
            Y = yr - off
            cur = name_on(n, D)
            for p, r in cur[cur["is_term"] & (cur["year"] == Y)].iterrows():
                i = cal.get_loc(D)
                if p not in P["prc"].columns or not np.isfinite(P["prc"].at[D, p]):
                    drop["not_listed_at_decision"] += 1
                    continue
                if not (P["prc"].at[D, p] >= MIN_PRICE and adv.at[D, p] >= min_adv):
                    drop["ineligible"] += 1
                    continue
                end = min(last_row[p], cal[cal.year == Y][-1])
                if i + harness.EXEC_LAG >= len(cal) or cal[i + harness.EXEC_LAG] > end:
                    drop["dead_before_first_earned_session"] += 1
                    continue
                first = cal[i + harness.EXEC_LAG]
                assert r["namedt"] <= D and first > D and (first - D).days >= 2      # nothing after D is read
                rows.append({"book": book, "permno": p, "D": D, "first": first, "end": end, "Y": Y,
                             "sponsor": r["sponsor"], "muni": bool(r["muni"]), "etf": r["etf"],
                             "died": bool(last_row[p] <= cal[cal.year == Y][-1]) and last_row[p] < cal[-1]})
    return pd.DataFrame(rows), drop


def controls_for(ev, n, P, never_term, min_adv) -> dict:
    adv = P["dollar_volume"].rolling(21, min_periods=10).mean()
    out = {}
    for k, e in ev.iterrows():
        cur = name_on(n, e["D"])
        c = cur[(cur["sponsor"] == e["sponsor"]) & (cur["muni"] == e["muni"]) & cur.index.isin(never_term)]
        ok = [p for p in c.index if p in P["prc"].columns and P["prc"].at[e["D"], p] >= MIN_PRICE and adv.at[e["D"], p] >= min_adv]
        out[k] = ok
    return out


def compound(R: pd.DataFrame | pd.Series, a, b):
    return (1.0 + R.loc[a:b].fillna(0.0)).prod() - 1.0


def clustered(x: pd.Series, cluster: pd.Series) -> dict:
    """Mean, median, share positive and a t that clusters on `cluster` (events entered the same
    month share the market they were held through)."""
    x = x.dropna()
    if len(x) < 3:
        return {"n": int(len(x)), "mean": float(x.mean()) if len(x) else None}
    e = x - x.mean()
    se = np.sqrt((e.groupby(cluster.reindex(x.index)).sum() ** 2).sum()) / len(x)
    return {"n": int(len(x)), "clusters": int(cluster.reindex(x.index).nunique()), "mean": float(x.mean()),
            "median": float(x.median()), "share_positive": float((x > 0).mean()),
            "t_clustered": float(x.mean() / se) if se > 0 else None}


def earn_frame(ev, cal, cols, legs: dict | None = None) -> pd.DataFrame:
    """Exposure EARNED each session: 1/N across events live that day. `legs` maps an event to
    the columns that carry its weight instead of the fund (the control basket)."""
    W = pd.DataFrame(0.0, index=cal, columns=cols)
    live = pd.Series(0.0, index=cal)
    for k, e in ev.iterrows():
        live.loc[e["first"]:e["end"]] += 1
    for k, e in ev.iterrows():
        w = (1.0 / live.loc[e["first"]:e["end"]])
        targets = [e["permno"]] if legs is None else legs[k]
        for p in targets:
            W.loc[e["first"]:e["end"], p] += w / len(targets)
    return W


def run_book(ev, cal, R, mkt, etf, ctrl) -> dict:
    """Calendar-time P&L through the canonical harness: long only, less the CEF market, less the
    matched ETF (events with an ETF), and term less control (events with a control)."""
    cols = list(R.columns)
    out = {}
    E = earn_frame(ev, cal, cols)
    res = harness.evaluate(E.shift(-harness.EXEC_LAG).fillna(0.0), R)
    gross = E.sum(axis=1)
    out["long"], out["turn"], out["earn"] = res["pnl"], float(res["turn"]), E
    out["vs_mkt"] = res["pnl"] - gross * mkt.fillna(0.0)
    has = ev[[np.isfinite(etf[e["etf"]].loc[e["first"]:e["end"]]).all() for _, e in ev.iterrows()]] if len(ev) else ev
    out["n_etf_events"] = int(len(has))
    if len(has):
        Ee = earn_frame(has, cal, cols)
        hedge = sum(earn_frame(has[has["etf"] == t].assign(permno=t), cal, [t])[t] * etf[t].fillna(0.0)
                    for t in has["etf"].unique())
        live_any = pd.Series(0.0, index=cal)
        for _, e in has.iterrows():
            live_any.loc[e["first"]:e["end"]] += 1
        # earn_frame on a subset re-normalises within the subset; the ETF legs must share one N
        hedge = pd.Series(0.0, index=cal)
        for _, e in has.iterrows():
            seg = slice(e["first"], e["end"])
            hedge.loc[seg] += (etf[e["etf"]].loc[seg] / live_any.loc[seg]).values
        out["vs_etf"] = harness.evaluate(Ee.shift(-harness.EXEC_LAG).fillna(0.0), R)["pnl"] - hedge
        out["etf_only"] = hedge
    m = ev[[len(ctrl[k]) > 0 for k in ev.index]] if len(ev) else ev
    out["n_ctrl_events"] = int(len(m))
    if len(m):
        Et = earn_frame(m, cal, cols)
        Ec = earn_frame(m, cal, cols, legs=ctrl)
        pt = harness.evaluate(Et.shift(-harness.EXEC_LAG).fillna(0.0), R)["pnl"]
        pc = harness.evaluate(Ec.shift(-harness.EXEC_LAG).fillna(0.0), R)["pnl"]
        g = Et.sum(axis=1)
        out["matched_term_vs_mkt"], out["control_vs_mkt"] = pt - g * mkt.fillna(0.0), pc - g * mkt.fillna(0.0)
        out["term_less_control"], out["control_long"] = pt - pc, pc
    return out


def per_event(ev, R, mkt, etf, ctrl) -> pd.DataFrame:
    rows = []
    for k, e in ev.iterrows():
        a, b = e["first"], e["end"]
        f = compound(R[e["permno"]], a, b)
        x = etf[e["etf"]].loc[a:b]
        c = [compound(R[p], a, b) for p in ctrl[k]]
        rows.append({"fund": f, "vs_mkt": f - compound(mkt, a, b),
                     "vs_etf": f - compound(x, a, b) if np.isfinite(x).all() else np.nan,
                     "vs_control": f - float(np.mean(c)) if c else np.nan,
                     "sessions": int(len(R.loc[a:b])), "month": e["D"].strftime("%Y-%m")})
    return pd.DataFrame(rows, index=ev.index)


def pstats(pnl: pd.Series, first: pd.Timestamp) -> dict:
    return explore.summarise(pnl.loc[first:].iloc[:-harness.EXEC_LAG])


def short_row(s: dict) -> dict:
    g = lambda d: {k: d[k] for k in ("ann_ret", "ann_vol", "sharpe", "t", "n_active_days", "max_drawdown")}
    return {"full": g(s["full"]), "early_half": g(s["early_half"]), "late_half": g(s["late_half"]),
            "split_date": s["split_date"], "eras": {k: g(v) for k, v in s["eras"].items()}}


def nav_series() -> dict:
    """ticker -> NAV series, from Yahoo X<TICKER>X caches and the desk's read-only panels.
    Nothing is filled: a ticker with no series is simply absent and is counted by the caller."""
    out = {}
    d = STAGE / "yahoo_nav"
    for f in sorted(d.glob("X*X.parquet")) if d.exists() else []:
        h = pd.read_parquet(f)
        if len(h) > 50:
            out[f.stem[1:-1]] = h.set_index("Date")["Close"].dropna()
    desk = REPO.parents[2] / "data"       # the main checkout's panels, READ ONLY (the live book decides on them)
    for rel in ("cef_families/cef_nav_cefconnect.parquet", "cef_families/cef_nav.parquet", "cef/cef_nav.parquet"):
        f = desk / rel
        if not f.exists():
            continue                      # a worktree without the panels: Yahoo only, and the count printed says so
        x = pd.read_parquet(f, columns=["date", "nav", "ticker"])
        for t, g in x.groupby("ticker"):
            if t not in out:
                out[t] = g.assign(date=pd.to_datetime(g["date"])).set_index("date")["nav"].dropna().sort_index()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="names, counts and liquidity only; reads no return")
    a = ap.parse_args(argv)
    df, P, names, dl = load()
    cal = P["ret"].index
    last = cal[-1]
    span = df.groupby("permno")["date"].agg(["min", "max"])
    first_row, last_row = span["min"], span["max"]
    n = classify(names, first_row)
    ever = set(n.loc[n["is_term"], "permno"])
    never_term = set(P["ret"].columns) - ever
    # ---- the list, outcomes, the live book: counts only -------------------------------------
    adv = P["dollar_volume"].rolling(21, min_periods=10).mean()
    mid = (P["bid"] + P["ask"]) / 2
    spread = ((P["ask"] - P["bid"]) / mid).where((P["bid"] > 0) & (P["ask"] > P["bid"]))
    rows = []
    for p in sorted(ever):
        x = n[n["permno"] == p].sort_values("namedt")
        at_end = name_on(n, last_row[p]).loc[p] if p in name_on(n, last_row[p]).index else x.iloc[-1]
        yrs = [int(y) for y in x.loc[x["is_term"], "year"].dropna().unique()]
        alive = last_row[p] >= last
        act = None if alive else (dl.at[p, "delactiontype"] if p in dl.index else "NO DELIST ROW")
        if alive:
            out = "alive, term name" if at_end["is_term"] else "alive, term name dropped (perpetual)"
        elif not at_end["is_term"]:
            out = "dead, term name dropped first"
        elif act == "GLI":
            out = "liquidated"
        else:
            out = f"dead, {act}"
        y_end = at_end["year"] if at_end["is_term"] else np.nan
        rows.append({"permno": p, "ticker": x["ticker"].dropna().iloc[-1] if x["ticker"].notna().any() else None,
                     "name": at_end["issuernm"], "first": first_row[p], "last": last_row[p], "outcome": out,
                     "years_in_names": yrs, "year_at_end": y_end, "muni": bool(at_end["muni"]), "etf": at_end["etf"],
                     "sponsor": at_end["sponsor"], "year_added_or_changed": len(yrs) > 1 or (len(yrs) == 1 and x.loc[x["is_term"], "year"].isna().any()),
                     "died_vs_year": (last_row[p].year - y_end) if (not alive and np.isfinite(y_end)) else np.nan})
    L = pd.DataFrame(rows).set_index("permno")
    L.to_parquet(STAGE / "term_list.parquet")
    live = L[L["outcome"] == "alive, term name"].copy()
    live["price"] = [P["prc"][p].dropna().iloc[-1] for p in live.index]
    live["adv21"] = [adv[p].dropna().iloc[-1] for p in live.index]
    live["spread_med_60d"] = [spread[p].iloc[-60:].median() for p in live.index]
    (STAGE / "nav_symbols.txt").write_text("\n".join(sorted(set(L.loc[L["last"] >= "2012-01-01", "ticker"].dropna()))))
    counts = {"term_funds_by_rule": int(len(L)), "outcomes": L["outcome"].value_counts().to_dict(),
              "with_a_year_in_some_name": int((L["years_in_names"].str.len() > 0).sum()),
              "year_added_or_changed_while_listed": int(L["year_added_or_changed"].sum()),
              "dead_with_year: last row minus name year": L["died_vs_year"].dropna().astype(int).value_counts().sort_index().to_dict(),
              "alive_today": int(len(live))}
    print("panel", cal[0].date(), "to", last.date(), "|", len(P["ret"].columns), "CEFs |", json.dumps(counts, indent=1, default=str))
    pd.set_option("display.width", 220)
    print(live[["ticker", "name", "year_at_end", "price", "adv21", "spread_med_60d"]].to_string())
    ev, drop = events(n, P, cal, last_row, MIN_ADV)
    evs, drops = events(n, P, cal, last_row, STRICT_ADV)
    print("events", ev.groupby("book").size().to_dict(), "dropped", drop, "| on $500k", evs.groupby("book").size().to_dict())
    t = ev[ev["book"] == "T250"]
    print("T250 by decision year:", t.groupby(t["D"].dt.year).size().to_dict())
    if a.list:
        return 0

    # ---- returns from here ------------------------------------------------------------------
    R = P["ret"].fillna(0.0)             # a fund with no row has not listed yet or has stopped trading; it is unheld then
    elig = ((P["prc"] >= MIN_PRICE) & (adv >= MIN_ADV)).shift(1, fill_value=False)      # known the session before
    mkt = P["ret"].where(elig)[sorted(never_term)].mean(axis=1)
    etf = etf_returns(cal)
    res = {"panel_first": str(cal[0].date()), "panel_last_date": str(last.date()), "counts": counts,
           "events_dropped": drop, "etf_last_dates": {c: str(etf[c].dropna().index.max().date()) for c in etf}}
    res["live_funds"] = [{"ticker": r["ticker"], "scheduled_year": None if not np.isfinite(r["year_at_end"]) else int(r["year_at_end"]),
                          "adv21_usd": float(r["adv21"]), "spread_med_60d_bp": float(r["spread_med_60d"] * 1e4),
                          "price": float(r["price"])} for _, r in live.iterrows()]
    summary_pnls = {}
    for label, E_all, thr in (("adv100k", ev, MIN_ADV), ("adv500k", evs, STRICT_ADV)):
        for book in BOOKS:
            e = E_all[E_all["book"] == book].reset_index(drop=True)
            if not len(e):
                continue
            ctrl = controls_for(e, n, P, never_term, thr)
            b = run_book(e, cal, R, mkt, etf, ctrl)
            pe = per_event(e, R, mkt, etf, ctrl)
            held = b["earn"] > 0
            gone = int((held & P["ret"].isna()).sum().sum())
            start = e["first"].min()
            key = f"{book}_{label}"
            r = {"events": int(len(e)), "events_per_year": float(len(e) / ((last - start).days / 365.25)),
                 "first_earned_session": str(start.date()), "funds_held_mean_when_invested": float(held.sum(axis=1)[held.any(axis=1)].mean()),
                 "share_of_sessions_invested": float(held.any(axis=1).loc[start:].mean()),
                 "turnover_per_year": b["turn"], "held_name_days_with_no_row": gone,
                 "events_that_died_in_window": int(e["died"].sum()), "events_alive_at_year_end": int((~e["died"]).sum()),
                 "median_sessions_held": float(pe["sessions"].median()),
                 "held_median_dollar_volume": float(P["dollar_volume"].where(held).stack().median()),
                 "held_median_price": float(P["prc"].where(held).stack().median()),
                 "held_median_spread_bp": float(spread.where(held).stack().median() * 1e4),
                 "held_p90_spread_bp": float(spread.where(held).stack().quantile(0.9) * 1e4),
                 "entry_day_median_spread_bp": float(np.nanmedian([spread.at[x["D"], x["permno"]] for _, x in e.iterrows()]) * 1e4),
                 "n_events_with_etf": b["n_etf_events"], "n_events_with_control": b["n_ctrl_events"],
                 "control_funds_per_event_median": float(np.median([len(ctrl[k]) for k in e.index])),
                 "per_event": {c: clustered(pe[c], pe["month"]) for c in ("fund", "vs_mkt", "vs_etf", "vs_control")},
                 "calendar": {k: short_row(pstats(b[k], start)) for k in ("long", "vs_mkt", "vs_etf", "etf_only", "matched_term_vs_mkt",
                                                                      "control_vs_mkt", "term_less_control", "control_long") if k in b}}
            res[key] = r
            pe.assign(permno=e["permno"], D=e["D"], end=e["end"], died=e["died"], etf=e["etf"]).to_parquet(STAGE / f"per_event_{key}.parquet")
            if label == "adv100k" and book == "T250":
                summary_pnls = {k: b[k].loc[start:].iloc[:-harness.EXEC_LAG] for k in ("long", "vs_mkt", "vs_etf", "term_less_control", "control_vs_mkt") if k in b}
                full = explore.summarise(summary_pnls["vs_mkt"], controls={"sponsor/category control less CEF market": summary_pnls["control_vs_mkt"]})
                res["T250_vs_mkt_house_table"] = full
                print(explore.table(full))

    # ---- hindsight table: the last K sessions before the fund's actual last row --------------
    hs = {}
    dead = L[L["outcome"].isin(["liquidated"]) | L["outcome"].str.startswith("dead, ")]
    for K in (250, 120, 60):
        rows = []
        for p, r in dead.iterrows():
            j = cal.get_loc(r["last"])
            i0 = cal.get_loc(first_row[p])
            if j - K + 1 <= i0:
                continue
            a_, b_ = cal[j - K + 1], cal[j]
            D = cal[j - K]
            cur = name_on(n, D)
            c = cur[(cur["sponsor"] == r["sponsor"]) & (cur["muni"] == r["muni"]) & cur.index.isin(never_term)]
            c = [q for q in c.index if q in P["prc"].columns and P["prc"].at[D, q] >= MIN_PRICE and adv.at[D, q] >= MIN_ADV]
            f = compound(R[p], a_, b_)
            x = etf[r["etf"]].loc[a_:b_]
            row = {"outcome": r["outcome"], "fund": f, "vs_mkt": f - compound(mkt, a_, b_),
                   "vs_etf": f - compound(x, a_, b_) if np.isfinite(x).all() else np.nan,
                   "vs_control": f - float(np.mean([compound(R[q], a_, b_) for q in c])) if c else np.nan,
                   "last_day_ret": float(P["ret"].at[b_, p]) if np.isfinite(P["ret"].at[b_, p]) else np.nan,
                   "month": r["last"].strftime("%Y-%m"), "era": int(r["last"].year)}
            if j - 2 * K + 1 > i0:
                pa, pb = cal[j - 2 * K + 1], cal[j - K]
                row["placebo_vs_mkt"] = compound(R[p], pa, pb) - compound(mkt, pa, pb)
            rows.append(row)
        T = pd.DataFrame(rows, index=[p for p in dead.index if cal.get_loc(dead.at[p, "last"]) - K + 1 > cal.get_loc(first_row[p])][:len(rows)])
        T.to_parquet(STAGE / f"hindsight_{K}.parquet")
        liq = T[T["outcome"] == "liquidated"]
        hs[str(K)] = {"liquidated": {c: clustered(liq[c], liq["month"]) for c in ("fund", "vs_mkt", "vs_etf", "vs_control", "placebo_vs_mkt") if c in liq},
                      "other_dead_n": int((T["outcome"] != "liquidated").sum()),
                      "liquidated_last_day_ret_below_minus_5pct": int((liq["last_day_ret"] < -0.05).sum()),
                      "liquidated_by_era_vs_mkt_mean": {f"{a0}-{b0}": (float(liq.loc[liq["era"].between(a0, b0), "vs_mkt"].mean()), int(liq["era"].between(a0, b0).sum()))
                                                        for a0, b0 in ((1990, 2001), (2002, 2008), (2009, 2015), (2016, 2019), (2020, 2022), (2023, 2025))}}
    res["hindsight"] = hs

    # ---- with NAV ---------------------------------------------------------------------------
    navs = nav_series()
    t = ev[ev["book"] == "T250"].reset_index(drop=True)
    pe = pd.read_parquet(STAGE / "per_event_T250_adv100k.parquet")
    tick = L["ticker"]
    disc = []
    for k, e in t.iterrows():
        s = navs.get(tick.get(e["permno"]))
        v = np.nan
        if s is not None and e["D"].year >= 2012:            # a 1990s ticker reused by a later fund is not this fund's NAV
            w = s.loc[e["D"] - pd.Timedelta(days=5):e["D"]]
            if len(w):
                v = P["prc"].at[e["D"], e["permno"]] / w.iloc[-1] - 1.0
        disc.append(v)
    pe["discount_at_D"] = disc
    have = pe.dropna(subset=["discount_at_D"])
    res["with_nav"] = {"t250_events": int(len(pe)), "t250_events_with_nav": int(len(have)),
                       "nav_symbols_asked": len((STAGE / "nav_symbols.txt").read_text().split()), "nav_symbols_served": len([t for t in (STAGE / "nav_symbols.txt").read_text().split() if t in navs]),
                       "discount_at_D": {"median": float(have["discount_at_D"].median()) if len(have) else None,
                                         "min": float(have["discount_at_D"].min()) if len(have) else None,
                                         "max": float(have["discount_at_D"].max()) if len(have) else None},
                       "discount_3pct_or_more": {c: clustered(have.loc[have["discount_at_D"] <= -0.03, c], have["month"]) for c in ("fund", "vs_etf", "vs_control")},
                       "discount_under_3pct": {c: clustered(have.loc[have["discount_at_D"] > -0.03, c], have["month"]) for c in ("fund", "vs_etf", "vs_control")}}
    live_nav = []
    for p, r in live.iterrows():
        s = navs.get(r["ticker"])
        if s is None:
            live_nav.append({"ticker": r["ticker"], "discount": None})
            continue
        w = s.loc[:last]
        live_nav.append({"ticker": r["ticker"], "nav_date": str(w.index[-1].date()),
                         "discount_at_panel_end": float(P["prc"][p].dropna().iloc[-1] / w.iloc[-1] - 1.0)})
    res["live_funds_discount"] = live_nav
    (HERE / "results.json").write_text(json.dumps(res, indent=1, default=str))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4))
    for k, v in summary_pnls.items():
        (v.cumsum() * 100).plot(ax=ax, label=k)
    ax.set_title(f"T250: term funds bought at the last session of the year before the scheduled year; gross, shift(2); to {last.date()}", fontsize=8)
    ax.set_ylabel("cumulative return, % (not compounded)"); ax.legend(fontsize=7); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(HERE / "equity.png", dpi=110); plt.close(fig)
    for k in ("T250_adv100k", "T120_adv100k", "T60_adv100k", "T250_adv500k"):
        if k in res:
            r = res[k]
            print("\n", k, {x: r[x] for x in r if x not in ("per_event", "calendar")})
            print(" per event:", json.dumps(r["per_event"], default=str))
            for c, v in r["calendar"].items():
                print(f"  {c:22s} SR {v['full']['sharpe']:+.2f} t {v['full']['t']:+.2f} ret {v['full']['ann_ret']:+.2%} vol {v['full']['ann_vol']:.2%} "
                      f"halves {v['early_half']['sharpe']:+.2f}/{v['late_half']['sharpe']:+.2f} eras " + " ".join(f"{e}:{s['sharpe']:+.2f}" if s["sharpe"] is not None else f"{e}:n/a" for e, s in v["eras"].items()))
    print("\nhindsight", json.dumps(hs, indent=1, default=str))
    print("\nNAV", json.dumps(res["with_nav"], indent=1, default=str), json.dumps(live_nav, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
