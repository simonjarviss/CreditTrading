"""NAV-for-NAV CEF/BDC merger pairs, 2010-22: the repo re-run of SCALING §7.1 row 1.

    python3 scripts/events/merger_pairs.py          # writes results/events/merger_*.csv|json

ZERO TRIALS. DESCRIPTIVE ONLY. This is not a harness backtest (no shift(2)
policy, no turnover matching, no cost grid): it re-measures the descriptive
event statistics an agent printed on 2026-10-09 from scratch code that was then
deleted, so a pre-registration can cite a figure a script in the repo produces
(`results/cef/RESEARCH_PLAN_2026-10-09.md` §0, item 0.9). Nothing here may be
read as the E1 trial.

WHAT IS MEASURED (the original method, rebuilt; every change is listed below)
---------------------------------------------------------------------------
Events: CRSP delistings 2010-01-01..2022-12-31 of share-code 14/44 securities
(CEFs, BDCs) with a merger code (dlstcd 2xx). Target holders of a stock-for-
stock CEF merger receive acquirer shares at the closing NAV ratio, so

  r_final  = dlamt / |P_A(dlpdt)|   CRSP values the consideration at the
             acquirer's price on the payment date, so this backs out the shares
             of acquirer per target share (checked against filed ratios by the
             2026-10-09 agent: GGM 1.123347 vs 1.12334682, GPM 0.527929 vs
             0.52792920 [V, agent]; re-printed here for those deals);
  spread_k = r_final * P_A(t0) / P_T(t0) - 1 at t0 = k target trading days
             before the target's last day T; prices split-adjusted to the
             share units in force at T (target) and dlpdt (acquirer);
  pair_k   = long $1 target / short $1 acquirer, CRSP total return from the
             close of t0 to completion: target compounds `ret` over (t0, T] and
             then its delisting return `dlret`; acquirer compounds `ret` over
             (t0, dlpdt];
  ctrl_k   = the same pair over a window of the same length ending 252 target
             trading days before T (no deal pending, typically).

THE FIXED-OFFSET WINDOWS ARE EX POST. They are anchored on the completion date
and use the final ratio, which nobody knows at t0. They describe what the
spread did; they are not a tradable rule. The announcement-anchored sample
(`announcement_sample`) is the closest thing to an ex-ante entry, and it is the
figure the merger verdict turned on.

HOLDOUT. Every return statistic excludes any event whose target or acquirer is
in `data/cef/cef_universe.csv`. The 27-name comparison set was opened for
event trades by the team lead on 2026-10-09 (`docs/SYSTEM.md` §5), but the set
is CONSUMED by the first pre-registered test that computes returns on one of
its names, and this re-run is not that test. So returns stay off all 44 names,
as in the original. The universe is matched two ways and both are reported:
by ticker (the original) and by CRSP permno (`crsp_events.universe_permnos`,
which also catches a universe fund under an older ticker and keeps a recycled
ticker such as the 1990s BGT out). The G1c event COUNT (no returns) does
include events on the 27; see `g1c_counts`.

TIME HOLDOUT. `crsp_events.daily` returns no row on or after 2023-01-01. An
event whose payment date `dlpdt` falls in 2023 therefore has no acquirer price
at completion and drops out, and the drop is counted (`skip_reasons`).

CHANGES FROM THE 2026-10-09 SCRATCH CODE (each one visible in the output)
-------------------------------------------------------------------------
1. MISSING DAILY RETURNS WERE TREATED AS ZERO (`ret.fillna(0)`; 20 cases in
   the original's pair legs). That is the silent fallback CLAUDE.md forbids.
   CRSP's convention is that the next valid `ret` after a missing price is
   measured from the last valid price, which, if true, makes compounding the
   valid returns exact as long as the window's first and last prices exist.
   `bridging_check` tests that convention on these extracts; `window_return`
   compounds across a gap only when the convention held at that gap and the
   window's boundary prices exist, and otherwise returns NaN, counted. Both the
   corrected figure and the original zero-fill figure are reported, labelled.
2. The universe flag is also matched by permno (see HOLDOUT).
3. An acquirer whose CRSP name is not in force on the delisting date (a fund
   created by the merger) was given its FIRST later name record, silently.
   It still is, but the row says so (`a_name_source`).
4. Events are grouped by acquirer PERMNO and completion date, not by acquirer
   ticker, so an acquirer with no CRSP name is not dropped from the group count
   by pandas' groupby (the original's grouping key could be None).
The split adjustment the agent added mid-run (FHI/FHO -> FHY reverse split had
produced -66% spreads) is kept.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:  # run as a script, not -m
    sys.path.insert(0, str(REPO))

from scripts.events import crsp_events as ce  # noqa: E402

OUT = REPO / "results" / "events"
START, END = pd.Timestamp("2010-01-01"), pd.Timestamp("2022-12-31")
KS = (1, 5, 21, 63, 126, 252)
CTRL_LAG = 252
# CRSP: a valid return after a missing price spans at most 10 trading periods
# (CRSP Data Descriptions Guide, RET; [S], the convention itself is TESTED on
# these extracts by `bridging_check` before it is relied on).
MAX_GAP = 10

# The four names dropped from the deployed 17 because Alpaca would not short
# them (team lead, 2026-09-28, docs/SYSTEM.md §5 "Universe on Alpaca"). The
# other 13 are read from the frozen spec. Together they are the 17 the
# 2026-09-08 ruling kept; the remaining 27 of cef_universe.csv are the H9
# comparison set.
DROPPED_ON_ALPACA = ("NAD", "NEA", "NVG", "NZF")


def classify(comnam: str) -> str:
    """Asset class from the CRSP name. A regex, as in the original: it is a
    label for the by-class table, not a fact about the fund, and the per-event
    file carries the name so a reader can re-check any row."""
    n = str(comnam)
    if any(k in n for k in ["MUNI", "MUN ", "MUN.", "TAX FR", "TAX EX", "QLTY INC MUN", "MUNICIPAL", " MUN"]):
        return "muni"
    if any(k in n for k in ["CAPITAL CORP", "INVESTMENT CORP", "B D C", "FINANCE CORP", "LENDING",
                            "CAPITAL INC", "S L R", "CREDIT CORP"]):
        return "bdc"
    if any(k in n for k in ["INCOME", "INC FD", "INC OPP", "BOND", "CREDIT", "HIGH YLD", "HI INC", "HG IN",
                            "CR & MORT", "FLOAT", "MORTG", "PFD", "CURR", "HIGH INC", "GLB INC", "HIGH YIELD",
                            "CORP B", "EMER MKT", "WORLDWIDE I", "STRAT HI", "STRAT HIGH"]):
        return "taxable_income"
    return "equity_other"


def holdout_sets() -> tuple[set, set, set]:
    """(deployed 17, the 27 comparison names, all 44) as ticker sets."""
    sys.path.insert(0, str(REPO / "scripts" / "cef"))
    import spec  # noqa: E402  (the frozen spec is the only authority on the live universe)
    uni = set(ce.universe()["ticker"])
    deployed = set(spec.frozen("universe")) | set(DROPPED_ON_ALPACA)
    if len(deployed) != 17 or not deployed <= uni:
        raise ValueError(f"expected the 17 deployed names inside cef_universe.csv; got {sorted(deployed)}")
    comparison = uni - deployed
    if len(comparison) != 27:
        raise ValueError(f"expected 27 comparison names; got {len(comparison)}")
    return deployed, comparison, uni


# --------------------------------------------------------------------- census

def build_events(nm: pd.DataFrame, dl: pd.DataFrame, start=START, end=END, extra_codes: tuple = ()) -> pd.DataFrame:
    """Every CRSP merger delisting (dlstcd 2xx) of a share-code 14/44 security.

    `extra_codes` (added 2026-10-21 for E1's amendment 4; default empty, so every existing caller
    and published figure is unchanged) admits further delisting codes, each with an acquirer
    permno: CRSP codes many CEF reorganisations 331 (an exchange), not 231. A 331 with an acquirer
    permno is kind "stock" (the shareholders receive the acquirer's shares), so E1's universe can
    take it; test_merger_pairs_extra_codes.py pins the no-op."""
    d = dl[(dl["dlstdt"] >= start) & (dl["dlstdt"] <= end)]
    last = ce.last_name(nm)[["permno", "shrcd", "ticker", "comnam", "siccd"]]
    x = d.merge(last, on="permno", how="left")
    x = x[x["shrcd"].isin(ce.CEF_SHRCD) & ((x["dlstcd"] // 100 == 2) | x["dlstcd"].isin(list(extra_codes)))].copy()
    rows = []
    for r in x.itertuples():
        a = {"a_ticker": None, "a_comnam": None, "a_shrcd": np.nan, "a_name_source": "no acquirer permno"}
        if pd.notna(r.nwperm) and r.nwperm > 0:
            rec = ce.name_at(nm, int(r.nwperm), r.dlstdt)
            src = "in force at delisting"
            if rec is None:
                later = nm[(nm["permno"] == int(r.nwperm))].sort_values("namedt")
                rec = later.iloc[0] if len(later) else None
                src = "first record (none in force at delisting)" if rec is not None else "acquirer permno has no CRSP name"
            if rec is not None:
                a = {"a_ticker": rec["ticker"], "a_comnam": rec["comnam"], "a_shrcd": rec["shrcd"]}
            a["a_name_source"] = src
        rows.append(a)
    x = pd.concat([x.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    x["kind"] = np.select(
        [x["ticker"] == x["a_ticker"], x["dlstcd"] == 232, x["dlstcd"] == 241,
         (x["dlstcd"] == 231) & ~(x["nwperm"] > 0), x["dlstcd"] == 231,
         x["dlstcd"].isin(list(extra_codes)) & (x["nwperm"] > 0)],
        ["shell", "cash", "stock+cash", "stock_noacq", "stock", "stock"], default="other_2xx")
    return x


def flag_universe(x: pd.DataFrame, nm: pd.DataFrame) -> pd.DataFrame:
    deployed, comparison, uni = holdout_sets()
    up = ce.universe_permnos(nm)
    perm2tk = {p: tk for tk, ps in up.items() for p in ps}
    x = x.copy()
    x["t_uni_tk"] = x["ticker"].isin(uni)
    x["a_uni_tk"] = x["a_ticker"].isin(uni)
    x["t_uni_perm"] = x["permno"].isin(perm2tk)
    x["a_uni_perm"] = x["nwperm"].isin(perm2tk)
    x["touch_uni_tk"] = x["t_uni_tk"] | x["a_uni_tk"]
    x["touch_uni"] = x["touch_uni_tk"] | x["t_uni_perm"] | x["a_uni_perm"]
    tkt = x["permno"].map(perm2tk).fillna(x["ticker"])
    tka = x["nwperm"].map(perm2tk).fillna(x["a_ticker"])
    x["touch_deployed17"] = tkt.isin(deployed) | tka.isin(deployed)
    x["touch_comparison27"] = tkt.isin(comparison) | tka.isin(comparison)
    return x


# ----------------------------------------------------------- returns, checked

def bridging_check(px: pd.DataFrame) -> dict:
    """Test CRSP's missing-return convention on these extracts.

    For each day whose `retx` is missing and is followed by a valid `retx`,
    compare that next `retx` with the price change from the last valid price,
    split-adjusted. If CRSP bridges the gap, they agree; if it does not, the
    next return covers one day only and compounding across the gap would lose
    the missing day's move.
    """
    n = agree = 0
    worst = 0.0
    long_gaps = 0
    for _, g in px.sort_values("date").groupby("permno"):
        g = g.reset_index(drop=True)
        miss = g.index[g["retx"].isna()]
        for i in miss:
            j = i + 1
            if j >= len(g) or pd.isna(g.at[j, "retx"]) or pd.isna(g.at[j, "prc"]):
                continue
            prev = g.loc[: i - 1].dropna(subset=["prc"])
            if prev.empty:
                continue
            if i - prev.index[-1] > MAX_GAP:
                long_gaps += 1  # beyond CRSP's 10-period bridge: not expected to agree
                continue
            p0 = prev.iloc[-1]
            implied = (g.at[j, "prc"] / g.at[j, "cfacpr"]) / (p0["prc"] / p0["cfacpr"]) - 1
            n += 1
            err = abs(implied - g.at[j, "retx"])
            worst = max(worst, err)
            agree += int(err < 1e-4)
    return {"gaps_tested_le_max_gap": n, "agree_within_1e-4": agree, "worst_abs_diff": float(worst),
            "gaps_longer_than_max_gap_not_tested": long_gaps}


def window_return(s: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp) -> tuple[float, int, str]:
    """Total return over (a, b] from CRSP `ret`, with missing returns handled
    explicitly. Returns (value or NaN, number of missing returns, status).

    Compounds the valid returns only if (i) the price at `a` exists, (ii) the
    last day in the window has a valid return, and (iii) no run of missing
    returns is longer than MAX_GAP. Under CRSP's convention (tested by
    `bridging_check`) that is the exact window return. Otherwise NaN, with the
    reason; never a zero.
    """
    if a not in s.index or pd.isna(s.at[a, "prc"]):
        return np.nan, 0, "no price at window start"
    w = s.loc[(s.index > a) & (s.index <= b), "ret"]
    if w.empty:
        return np.nan, 0, "empty window"
    nmiss = int(w.isna().sum())
    if nmiss == 0:
        return float(np.prod(1 + w.values) - 1), 0, "ok"
    if pd.isna(w.iloc[-1]):
        return np.nan, nmiss, "missing return on the window's last day"
    run = (w.isna().astype(int).groupby((~w.isna()).cumsum()).sum()).max()
    if run > MAX_GAP:
        return np.nan, nmiss, f"gap of {run} days > {MAX_GAP}"
    return float(np.prod(1 + w.dropna().values) - 1), nmiss, "bridged"


def window_return_zero_fill(s: pd.DataFrame, a, b) -> float:
    """The ORIGINAL method (missing ret -> 0), kept only to show what the
    correction changes. Its output is labelled `orig_zero_fill` wherever it
    appears and is never the headline."""
    w = s.loc[(s.index > a) & (s.index <= b), "ret"].fillna(0)
    return float(np.prod(1 + w.values) - 1)


def fixed_offset_pairs(ev: pd.DataFrame, px: dict) -> tuple[pd.DataFrame, dict]:
    """The s05 measurement, per event. Returns (rows, skip_reasons)."""
    skips: dict[str, int] = {}
    rows = []
    for e in ev.itertuples():
        T, A = px.get(int(e.permno)), px.get(int(e.nwperm))
        why = None
        if T is None:
            why = "no target prices"
        elif A is None:
            why = "no acquirer prices"
        elif pd.isna(e.dlpdt):
            why = "no payment date"
        elif e.dlpdt >= ce.TIME_HOLDOUT:
            why = "payment date in the sealed 2023+ holdout"
        elif e.dlpdt not in A.index:
            why = "acquirer did not trade on the payment date"
        elif pd.isna(e.dlret):
            why = "no delisting return"
        if why:
            skips[why] = skips.get(why, 0) + 1
            continue
        r = float(e.dlamt) / A.at[e.dlpdt, "prc"]
        tdates = T.index[T.index <= e.dlstdt]
        dv_t, dv_a = T["prc"] * T["vol"], A["prc"] * A["vol"]
        rec = dict(permno=int(e.permno), ticker=e.ticker, comnam=e.comnam, nwperm=int(e.nwperm),
                   a_ticker=e.a_ticker, a_comnam=e.a_comnam, T=e.dlstdt.date(), dlpdt=e.dlpdt.date(),
                   r_final=r, dlret=float(e.dlret), cls=classify(e.comnam),
                   adv63_T=dv_t.loc[tdates[-63:]].mean() if len(tdates) >= 63 else np.nan,
                   adv63_A=dv_a.loc[A.index[A.index <= e.dlstdt][-63:]].mean())
        for k in KS:
            if len(tdates) <= k:
                continue
            t0 = tdates[-1 - k]
            if t0 not in A.index:
                continue
            pa = A.at[t0, "prc"] / A.at[t0, "cfacpr"] * A.at[e.dlpdt, "cfacpr"]
            pt = T.at[t0, "prc"] / T.at[t0, "cfacpr"] * T.at[e.dlstdt, "cfacpr"]
            rec[f"spread_{k}"] = r * pa / pt - 1
            rt, nt, st = window_return(T, t0, e.dlstdt)
            ra, na_, sa = window_return(A, t0, e.dlpdt)
            rec[f"pair_{k}"] = (1 + rt) * (1 + float(e.dlret)) - 1 - ra
            rec[f"nmiss_{k}"] = nt + na_
            rec[f"status_{k}"] = st if st != "ok" else sa
            rec[f"pair_{k}_orig_zero_fill"] = ((1 + window_return_zero_fill(T, t0, e.dlstdt)) * (1 + float(e.dlret)) - 1
                                              - window_return_zero_fill(A, t0, e.dlpdt))
            if len(tdates) > CTRL_LAG + k:
                c1, c0 = tdates[-1 - CTRL_LAG], tdates[-1 - CTRL_LAG - k]
                if c0 in A.index and c1 in A.index:
                    ct, _, _ = window_return(T, c0, c1)
                    ca, _, _ = window_return(A, c0, c1)
                    rec[f"ctrl_{k}"] = ct - ca
                    rec[f"ctrl_{k}_orig_zero_fill"] = (window_return_zero_fill(T, c0, c1)
                                                       - window_return_zero_fill(A, c0, c1))
        rows.append(rec)
    return pd.DataFrame(rows), skips


def summ(s: pd.Series) -> dict:
    s = s.dropna()
    return {"n": int(len(s)), "mean_bp": round(s.mean() * 1e4, 1), "median_bp": round(s.median() * 1e4, 1),
            "p10_bp": round(s.quantile(.1) * 1e4, 1), "p90_bp": round(s.quantile(.9) * 1e4, 1),
            "frac_pos": round(float((s > 0).mean()), 3)}


# ---------------------------------------------------- announcement-anchored

# Announcement dates for 13 deal groups, AS RECORDED by the 2026-10-09 agent
# (transcript of agent a77f1a269201e12b5, s08_ann_sample.py). They are NOT
# re-fetched here: the EDGAR fetcher (plan item 0.7) needs the SEC contact
# user-agent the team lead has not yet supplied, and this repo sets none by
# default. The agent's own labels are kept: "V" = it read the EDGAR filing
# index or the filing; "S" = a search summary of a press release or report.
# The at-announcement figure therefore reproduces ARITHMETIC on these dates;
# the dates themselves are [S] here until 0.7 re-derives them.
ANNOUNCEMENTS = (
    (("NQN", "NVN", "NUN", "NNF", "NKO"), "2012-06-22", "V", "Rule 425, EDGAR full-text search"),
    (("MFT", "BSD", "BBF"), "2020-06-16", "V", "Rule 425 dated 2020-06-16"),
    (("BFY", "BSE"), "2020-06-16", "S", "search summary of 425 / Business Wire"),
    (("IF", "LAQ", "SGF", "GCH", "ISL", "GRR", "ABE"), "2017-10-04", "V", "Rule 425, EDGAR full-text search"),
    (("GGM", "GPM"), "2021-04-20", "S", "search summary of an SEC filing"),
    (("MYC", "MCA", "MYJ", "MFL"), "2021-09-27", "S", "Business Wire via search"),
    (("NJV", "NPN"), "2020-08-07", "S", "Business Wire via search"),
    (("GDF",), "2015-11-16", "S", "search summary; 425 filed Nov 2015"),
    (("HIH", "HSA", "HAV", "HMH"), "2014-02-27", "S", "board date in N-CSR via search"),
    (("BPP", "PSY", "PSW"), "2012-07-27", "S", "board date in shareholder report via search"),
    (("OCSI",), "2020-10-28", "V", "8-K, merger agreement 2020-10-28"),
    (("SUNS",), "2021-12-01", "V", "8-K, merger agreement 2021-12-01"),
    (("FSKR",), "2020-11-24", "V", "Rule 425, EDGAR full-text search"),
)
BDC_TARGETS = ("OCSI", "SUNS", "FSKR")


def _announcement_row(e: pd.Series, a: pd.Timestamp, rec: dict, px: dict, skips: dict,
                      stock_codes: tuple = (231,)) -> dict:
    """One event's at-announcement measurement: entry at the close of A+1, held
    to completion. Shared by the agent-dated sample (`announcement_sample`) and
    the EDGAR-dated one (`announcement_sample_edgar`, added 2026-10-12, plan
    0.7), so the two figures differ ONLY in their dates. Factored out of
    `announcement_sample` unchanged except for one guard: an announcement with
    no trading day before it, none after it, or dated on or after completion is
    now a counted skip (the old code would have raised an IndexError; no
    agent-dated event reaches it). The no-op on the agent-dated sample was
    checked by re-running and diffing `merger_summary.json` byte for byte."""
    T, A = px.get(int(e["permno"])), px.get(int(e["nwperm"])) if e["nwperm"] > 0 else None
    td = T.index
    rec["days_to_close_cal"] = (e["dlstdt"] - a).days
    rec["tdays_to_close"] = int(((td > a) & (td <= e["dlstdt"])).sum())
    # `stock_codes` (added 2026-10-21, default (231,): unchanged) lets E1's amendment 4 price a 331
    # reorganisation into an acquirer permno by this same code; nothing else differs.
    if A is None or e["dlstcd"] not in stock_codes or e["dlpdt"] not in A.index or pd.isna(e["dlret"]):
        why = ("not a stock-only merger (dlstcd %d)" % e["dlstcd"]) if e["dlstcd"] not in stock_codes else "no acquirer price at payment"
        skips[why] = skips.get(why, 0) + 1
        rec["skip"] = why
        return rec
    if not (td < a).any() or not (td > a).any() or a >= e["dlstdt"]:
        # An announcement dated on or after the target's last trading day, or
        # outside its price history, has no A+1 entry before completion.
        why = "announcement not inside the target's price history before completion"
        skips[why] = skips.get(why, 0) + 1
        rec["skip"] = why
        return rec
    r = float(e["dlamt"]) / A.at[e["dlpdt"], "prc"]
    d_pre = td[td < a][-1]
    d_in = td[td > a][0]
    inwin = td[(td > a) & (td <= e["dlstdt"])]
    for nmk, d in (("pre", d_pre), ("A1", d_in), ("mid", inwin[len(inwin) // 2]), ("T1", td[td < e["dlstdt"]][-1])):
        if d in A.index:
            pa = A.at[d, "prc"] / A.at[d, "cfacpr"] * A.at[e["dlpdt"], "cfacpr"]
            pt = T.at[d, "prc"] / T.at[d, "cfacpr"] * T.at[e["dlstdt"], "cfacpr"]
            rec[f"spread_{nmk}"] = r * pa / pt - 1
    rt, nt, st = window_return(T, d_in, e["dlstdt"])
    ra, na_, sa = window_return(A, d_in, e["dlpdt"])
    rec["pair_A1_to_close"] = (1 + rt) * (1 + float(e["dlret"])) - 1 - ra
    rec["pair_A1_orig_zero_fill"] = ((1 + window_return_zero_fill(T, d_in, e["dlstdt"])) * (1 + float(e["dlret"])) - 1
                                     - window_return_zero_fill(A, d_in, e["dlpdt"]))
    rec["nmiss"] = nt + na_
    rec["status"] = st if st != "ok" else sa
    rec["adv63_T_pre"] = (T["prc"] * T["vol"]).loc[:d_pre].tail(63).mean()
    return rec


def announcement_sample(x: pd.DataFrame, px: dict) -> tuple[pd.DataFrame, dict]:
    """The s08 measurement: entry at the close of the first trading day AFTER
    the announcement date (A+1), so a pre-open or after-close release cannot be
    mis-timed in our favour; hold to completion."""
    rows, skips = [], {}
    for tks, ad, lab, src in ANNOUNCEMENTS:
        a = pd.Timestamp(ad)
        for tk in tks:
            e = x[(x["ticker"] == tk)]
            if e.empty:
                raise LookupError(f"announcement target {tk} has no 2010-22 CRSP merger delisting")
            e = e[e["dlstdt"] == e["dlstdt"].max()].iloc[0]
            if e["touch_uni"]:
                raise AssertionError(f"{tk}: the announcement sample must not touch cef_universe.csv")
            rec = dict(ticker=tk, acq=e["a_ticker"], ann=ad, label=lab, source=src,
                       completion=e["dlstdt"].date(), dlstcd=int(e["dlstcd"]))
            rows.append(_announcement_row(e, a, rec, px, skips))
    return pd.DataFrame(rows), skips


# ------------------------------------------- EDGAR-dated (added 2026-10-12)

EDGAR_DATES = OUT / "merger_edgar_dates.csv"   # scripts/events/edgar_merger_dates.py (gitignored: CRSP-joined)


def pairable_events(x: pd.DataFrame, by: str = "permno") -> pd.DataFrame:
    """The priced sample: stock-for-stock (dlstcd 231) mergers with an acquirer
    permno and no `cef_universe.csv` name -- matched by ticker or permno
    (`by="permno"`, the headline) or by ticker only (`by="ticker"`, the
    original's rule). Factored out of `main` (2026-10-12) so the EDGAR dating
    script reads the identical sample; `main`'s output is unchanged."""
    flag = {"permno": "touch_uni", "ticker": "touch_uni_tk"}[by]
    return x[(x["dlstcd"] == 231) & (x["kind"] == "stock") & (x["nwperm"] > 0) & ~x[flag]]


def announcement_sample_edgar(x: pd.DataFrame, px: dict, dates: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """`announcement_sample` on EDGAR-derived announcement dates, one per target
    permno (`edgar_merger_dates.py`). Same entry (close of A+1), same exit, same
    return code (`_announcement_row`). A target with no EDGAR date is counted
    under `skips`, never given another source's date."""
    rows, skips = [], {}
    dd = dates.set_index("permno")
    for e in pairable_events(x).itertuples(index=False):
        e = pd.Series(e._asdict())
        p = int(e["permno"])
        if p not in dd.index:
            raise LookupError(f"permno {p} ({e['ticker']}) is not in {EDGAR_DATES.name}: re-run edgar_merger_dates.py")
        d = dd.loc[p]
        if pd.isna(d["ann_date"]):
            why = "no EDGAR announcement date"
            skips[why] = skips.get(why, 0) + 1
            continue
        a = pd.Timestamp(d["ann_date"])
        rec = dict(ticker=e["ticker"], acq=e["a_ticker"], ann=str(a.date()), label="EDGAR",
                   source=f"{d['ann_form']} ({d['ann_party']}, {d['date_basis']})",
                   completion=e["dlstdt"].date(), dlstcd=int(e["dlstcd"]), permno=p,
                   nwperm=int(e["nwperm"]), cls=classify(e["comnam"]), date_basis=d["date_basis"])
        rows.append(_announcement_row(e, a, rec, px, skips))
    return pd.DataFrame(rows), skips


def clustered_t(v: pd.Series, groups: pd.Series) -> float:
    """t of the mean with standard errors clustered by `groups` (CR1).

    One board announcement often covers several targets (Nuveen's New York
    funds, 2012-06-22), so events inside a group are not independent; the
    plan's E1 kill test is stated on a group-clustered t. Descriptive here."""
    v = v.astype(float)
    n, mu = len(v), v.mean()
    g = (v - mu).groupby(groups.values).sum()
    G = len(g)
    if G < 2:
        return float("nan")
    var = (G / (G - 1)) * float((g ** 2).sum()) / n ** 2
    return float(mu / np.sqrt(var))


# Cost grid for one deal, in the units of the pair return (per $1 long).
# Entry trades $1 of target and $1 of acquirer short: 2 units of turnover. At
# completion the target's shares become acquirer shares and close the short,
# so no exit trade is assumed (2 units); if both legs are traded out instead,
# 4 units. The 2026-10-11 note's "35bp per deal ~ 18bp per unit" is the 2-unit
# convention. Borrow on the acquirer is NOT charged here (not measured
# historically; G1a measures today's shortability only).
COST_GRID_BP = (5, 15, 30)
UNITS_PER_DEAL = (2, 4)


def grid_table(v: pd.Series, groups: pd.Series) -> dict:
    """Gross median/mean/t and the median net of each cost and unit count."""
    if v.dropna().empty:
        raise ValueError("grid_table on an empty sample: a figure with N=0 is not a figure")
    s = summ(v)
    s["groups"] = int(groups.nunique())
    s["clustered_t_mean"] = round(clustered_t(v, groups), 2)
    s["net_median_bp"] = {f"{c}bp_x{u}": round(s["median_bp"] - c * u, 1)
                          for u in UNITS_PER_DEAL for c in COST_GRID_BP}
    s["net_mean_bp"] = {f"{c}bp_x{u}": round(s["mean_bp"] - c * u, 1)
                        for u in UNITS_PER_DEAL for c in COST_GRID_BP}
    return s


def edgar_report(x: pd.DataFrame, px: dict, ann_agent: pd.DataFrame) -> dict:
    """The at-announcement figure on EDGAR dates, beside the agent's dates."""
    dates = pd.read_csv(EDGAR_DATES)
    ed, sk = announcement_sample_edgar(x, px, dates)
    ed.to_csv(OUT / "merger_ann_sample_edgar.csv", index=False, float_format="%.8g")
    p = ed.dropna(subset=["pair_A1_to_close"]).copy()
    p["group"] = p["nwperm"].astype(str) + "@" + p["ann"]
    res = {"dates_file_rows": len(dates), "events_dated": int(dates["ann_date"].notna().sum()),
           "skips": sk, "all": grid_table(p["pair_A1_to_close"], p["group"]),
           "groups_by_ann_date": int(p["ann"].nunique()),
           "by_basis": {b: grid_table(g["pair_A1_to_close"], g["group"]) for b, g in p.groupby("date_basis")},
           "by_class": {c: grid_table(g["pair_A1_to_close"], g["group"]) for c, g in p.groupby("cls")}}
    # Two sensitivities, both stated in advance of looking (2026-10-12):
    # (1) one observation per group (the group's mean pair), so a board that
    #     merged eight funds at once counts once;
    # (2) every member of an acquirer x completion group entered on the
    #     group's EARLIEST EDGAR date (one board announcement can be filed under
    #     some targets a few days before others).
    gm = p.groupby("group")["pair_A1_to_close"].mean()
    res["group_level"] = {"groups": int(len(gm)), "median_bp": round(gm.median() * 1e4, 1),
                          "mean_bp": round(gm.mean() * 1e4, 1), "frac_pos": round(float((gm > 0).mean()), 3)}
    early = dates.copy()
    early["ann_date"] = pd.to_datetime(early["ann_date"])
    first = early.groupby(["nwperm", "completion"])["ann_date"].transform("min")
    for c in ("ann_form", "ann_party", "date_basis"):
        early[c] = early.sort_values("ann_date").groupby(["nwperm", "completion"])[c].transform("first")
    early["ann_date"] = first.dt.date.astype(str)
    eg, _ = announcement_sample_edgar(x, px, early)
    eg = eg.dropna(subset=["pair_A1_to_close"])
    res["group_earliest_date"] = grid_table(eg["pair_A1_to_close"], eg["nwperm"].astype(str) + "@" + eg["ann"])
    # The same 36 events as the agent-dated figure, with EDGAR's dates instead.
    a = ann_agent.dropna(subset=["pair_A1_to_close"]).copy()
    same = p[p["ticker"].isin(a["ticker"])].merge(a[["ticker", "ann", "label", "pair_A1_to_close"]],
                                                   on="ticker", suffixes=("", "_agent"))
    # `label` is "EDGAR" on the left; the agent's V/S label is `label_agent`.
    same["days_edgar_minus_agent"] = (pd.to_datetime(same["ann"]) - pd.to_datetime(same["ann_agent"])).dt.days
    res["agent_sample_redated"] = {
        "events": len(same), "agent_events": len(a),
        "edgar": grid_table(same["pair_A1_to_close"], same["group"]),
        "agent": grid_table(same["pair_A1_to_close_agent"],
                            same["nwperm"].astype(str) + "@" + same["ann_agent"]),
        "date_diff_days_by_agent_group": {f"{k[0]} ({k[1]})": sorted(set(g["days_edgar_minus_agent"].astype(int)))
                                          for k, g in same.groupby(["ann_agent", "label_agent"])},
        "edgar_on_agent_V_groups": grid_table(same.loc[same["label_agent"] == "V", "pair_A1_to_close"],
                                              same.loc[same["label_agent"] == "V", "group"]),
        "edgar_on_agent_S_groups": grid_table(same.loc[same["label_agent"] == "S", "pair_A1_to_close"],
                                              same.loc[same["label_agent"] == "S", "group"]),
        "agent_dates_on_V_groups": grid_table(same.loc[same["label_agent"] == "V", "pair_A1_to_close_agent"],
                                              same.loc[same["label_agent"] == "V", "nwperm"].astype(str)),
        "agent_dates_on_S_groups": grid_table(same.loc[same["label_agent"] == "S", "pair_A1_to_close_agent"],
                                              same.loc[same["label_agent"] == "S", "nwperm"].astype(str)
                                              + "@" + same.loc[same["label_agent"] == "S", "ann_agent"]),
    }
    return res


# ---------------------------------------------------------------- G1c count

def g1c_counts(x_all: pd.DataFrame) -> pd.DataFrame:
    """Event count by holdout tier and clustering. Counts only: no returns.

    A fourth clustering, (4) sponsor x completion year, takes the sponsor as
    the first word of the acquirer's CRSP name (NUVEEN, BLACKROCK, EATON...).
    It is a heuristic label, printed beside the others and never alone: a
    sponsor's board often announces a whole family's mergers at once, which
    is the dependence G1c is about.

    Tiers: (a) no universe name, as in every return statistic here; (b) the 27
    opened (events on the comparison set allowed, events on the deployed 17
    still out) -- the G1c reading; (c) everything. Clusters: (1) acquirer
    permno x completion date (the original's grouping); (2) completion date
    alone, a proxy for one board announcement spanning several acquirers
    (BlackRock 2021-04-09: BLE and BNY); (3) acquirer permno, any date -- the
    most conservative. Stock and stock-plus-cash mergers only (a cash or shell
    delisting is not a pair).
    """
    s = x_all[x_all["kind"].isin(["stock", "stock+cash"])].copy()
    s["period"] = np.where(s["dlstdt"] < ce.TIME_HOLDOUT, "2010-22", "2023-24 (count only)")
    s["sponsor"] = s["a_comnam"].fillna(s["comnam"]).str.split().str[0]
    s["year"] = s["dlstdt"].dt.year
    tiers = {
        "a: no universe name": ~s["touch_uni"],
        "b: the 27 opened (deployed 17 excluded)": ~s["touch_deployed17"],
        "c: all events": pd.Series(True, index=s.index),
    }
    out = []
    for per, g0 in s.groupby("period"):
        for tier, m in tiers.items():
            g = g0[m.loc[g0.index]]
            out.append({"period": per, "tier": tier, "events": len(g),
                        "groups_acq_x_date": g.groupby(["nwperm", "dlstdt"]).ngroups,
                        "groups_date": g["dlstdt"].nunique(),
                        "groups_acq": g["nwperm"].nunique(),
                        "groups_sponsor_x_year_heuristic": g.groupby(["sponsor", "year"]).ngroups})
    return pd.DataFrame(out)


# --------------------------------------------------------------------- main

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="re-pull the CRSP extracts")
    ap.add_argument("--edgar-dates", action="store_true",
                    help="also measure the at-announcement pair on EDGAR dates "
                         "(needs results/events/merger_edgar_dates.csv) -> merger_ann_edgar_summary.json")
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    nm, dl = ce.names(args.refresh), ce.delistings(args.refresh)
    res: dict = {"crsp_names_last": str(nm["nameendt"].max().date()),
                 "crsp_delist_last": str(dl["dlstdt"].max().date())}

    # --- census, 2010-22 (and 2023-24 for the count only)
    x_all = flag_universe(build_events(nm, dl, START, pd.Timestamp("2024-12-31")), nm)
    x = x_all[x_all["dlstdt"] <= END].copy()
    res["census"] = {
        "merger_delistings_2010_22": len(x),
        "by_kind": x["kind"].value_counts().to_dict(),
        "a_name_source": x["a_name_source"].value_counts().to_dict(),
        "touch_universe_by_ticker": int(x["touch_uni_tk"].sum()),
        "touch_universe_by_ticker_or_permno": int(x["touch_uni"].sum()),
        "ticker_vs_permno_disagree": x.loc[x["touch_uni"] != x["touch_uni_tk"],
                                           ["ticker", "a_ticker", "dlstdt"]].astype(str).values.tolist(),
    }
    st = x[x["kind"].isin(["stock", "stock+cash"])]
    for lab, m in (("ticker", ~st["touch_uni_tk"]), ("ticker_or_permno", ~st["touch_uni"])):
        g = st[m]
        res["census"][f"stock_events_no_universe_{lab}"] = {
            "events": len(g), "groups_acq_x_date": g.groupby(["nwperm", "dlstdt"]).ngroups,
            "groups_acq_ticker_x_date_original_key": g.groupby(["a_ticker", "dlstdt"]).ngroups}
    x.drop(columns=[c for c in x.columns if c in ("siccd",)]).to_csv(OUT / "merger_events_2010_2022.csv", index=False)

    # --- prices (pre-2023 only, enforced in crsp_events.daily)
    pairable = pairable_events(x, "permno")
    pairable_tk = pairable_events(x, "ticker")
    perms = set(x["permno"]) | set(x.loc[x["nwperm"] > 0, "nwperm"].astype(int))
    dsf = ce.daily(perms, args.refresh)
    res["dsf_last_date"] = str(dsf["date"].max().date())
    px = {int(p): g.set_index("date").sort_index() for p, g in dsf.groupby("permno")}
    res["bridging_check"] = bridging_check(dsf[dsf["permno"].isin(perms)])

    # --- fixed offsets; headline on the permno-or-ticker exclusion, original's ticker-only beside it
    fo, skips = fixed_offset_pairs(pairable, px)
    fo_tk, skips_tk = fixed_offset_pairs(pairable_tk, px)
    fo.to_csv(OUT / "merger_pairs_fixed_offset.csv", index=False, float_format="%.8g")
    res["fixed_offset"] = {"events_considered": len(pairable), "events_priced": len(fo), "skip_reasons": skips,
                           "by_class_priced": fo["cls"].value_counts().to_dict()}
    res["fixed_offset_ticker_only"] = {"events_considered": len(pairable_tk), "events_priced": len(fo_tk),
                                       "skip_reasons": skips_tk}
    # Acquirers of the priced events, for the G1a borrow check
    # (`acquirer_shortability.py`). CRSP's own last record says whether the
    # acquirer is still the same listed fund under the same ticker at CRSP's
    # end; an Alpaca symbol matched by ticker alone may be another security.
    last = ce.last_name(nm).set_index("permno")
    acq = (pd.concat([fo_tk.assign(sample="ticker_only"), fo.assign(sample="permno")])
           .groupby(["a_ticker", "nwperm"]).agg(a_comnam=("a_comnam", "first"), n_events=("ticker", "nunique"),
                                                 in_permno_sample=("sample", lambda v: "permno" in set(v)),
                                                 in_ticker_only_sample=("sample", lambda v: "ticker_only" in set(v)))
           .reset_index())
    acq["crsp_last_ticker"] = acq["nwperm"].map(last["ticker"])
    acq["crsp_last_nameendt"] = acq["nwperm"].map(last["nameendt"]).dt.date
    acq["same_fund_same_ticker_at_crsp_end"] = ((acq["crsp_last_ticker"] == acq["a_ticker"])
                                               & (acq["nwperm"].map(last["nameendt"]) >= pd.Timestamp("2024-12-31")))
    acq.to_csv(OUT / "merger_acquirers_2010_2022.csv", index=False)
    res["acquirers"] = {"tickers_ticker_only_sample": int(acq.loc[acq["in_ticker_only_sample"], "a_ticker"].nunique()),
                        "tickers_permno_sample": int(acq.loc[acq["in_permno_sample"], "a_ticker"].nunique()),
                        "same_fund_same_ticker_at_crsp_end": int(acq["same_fund_same_ticker_at_crsp_end"].sum())}
    tab = {}
    for k in KS:
        for c in ("spread", "pair", "ctrl", "pair_ZF", "ctrl_ZF"):
            col = {"pair_ZF": f"pair_{k}_orig_zero_fill", "ctrl_ZF": f"ctrl_{k}_orig_zero_fill"}.get(c, f"{c}_{k}")
            if col in fo:
                tab[f"{c}_{k}"] = summ(fo[col])
            if col in fo_tk:
                tab[f"{c}_{k}__ticker_only"] = summ(fo_tk[col])
    res["fixed_offset_table"] = tab
    res["pairs_with_missing_returns"] = {f"k{k}": {
        "windows_with_missing": int((fo.get(f"nmiss_{k}", pd.Series(dtype=float)) > 0).sum()),
        "status": fo.get(f"status_{k}", pd.Series(dtype=object)).value_counts().to_dict()} for k in (21, 63, 126)}
    bycls = {}
    for k in (21, 63, 126):
        for cls, g in fo.groupby("cls"):
            bycls[f"{cls}_k{k}"] = {"n": int(g[f"pair_{k}"].notna().sum()),
                                    "pair_median_bp": round(g[f"pair_{k}"].median() * 1e4, 1),
                                    "ctrl_median_bp": round(g[f"ctrl_{k}"].median() * 1e4, 1),
                                    "pair_median_bp_orig_zero_fill": round(g[f"pair_{k}_orig_zero_fill"].median() * 1e4, 1),
                                    "ctrl_median_bp_orig_zero_fill": round(g[f"ctrl_{k}_orig_zero_fill"].median() * 1e4, 1)}
    res["by_class"] = bycls
    res["by_class_ticker_only_k63"] = {cls: {"n": int(g["pair_63"].notna().sum()),
                                             "pair_median_bp": round(g["pair_63"].median() * 1e4, 1),
                                             "ctrl_median_bp": round(g["ctrl_63"].median() * 1e4, 1)}
                                       for cls, g in fo_tk.groupby("cls")}
    res["dlret"] = summ(fo["dlret"])
    res["dlret_ticker_only"] = summ(fo_tk["dlret"])
    res["adv63_median_usd_ticker_only"] = {"target": round(fo_tk["adv63_T"].median()),
                                           "acquirer": round(fo_tk["adv63_A"].median())}
    res["adv63_median_usd"] = {"target": round(fo["adv63_T"].median()), "acquirer": round(fo["adv63_A"].median())}
    real = {}
    for k in (21, 63, 126):
        s_ = fo[[f"spread_{k}", f"pair_{k}"]].dropna()
        sg = np.sign(s_.iloc[:, 0]) * s_.iloc[:, 1]
        real[f"k{k}"] = {"n": len(s_), "corr": round(s_.corr().iloc[0, 1], 3),
                         "slope": round(np.polyfit(s_.iloc[:, 0], s_.iloc[:, 1], 1)[0], 3),
                         "signed_by_hindsight_median_bp": round(sg.median() * 1e4, 1),
                         "signed_frac_pos": round(float((sg > 0).mean()), 3)}
    res["realisation"] = real
    ratio = fo[fo["ticker"].isin(["GGM", "GPM", "NQN", "NVN", "NUN", "NNF", "NKO", "BSE", "BFY", "FSKR", "OCSI", "SUNS"])]
    res["ratio_examples"] = dict(zip(ratio["ticker"], ratio["r_final"].round(6)))

    # --- announcement-anchored
    ann, ann_skips = announcement_sample(x, px)
    ann.to_csv(OUT / "merger_ann_sample.csv", index=False, float_format="%.8g")
    p = ann.dropna(subset=["pair_A1_to_close"]).copy()
    p["cls"] = np.where(p["ticker"].isin(BDC_TARGETS), "bdc",
                        np.where(p["acq"].isin(["CH"]), "equity_country",
                                 np.where(p["acq"].isin(["NRK", "BLE", "BNY", "MUC", "MUJ", "MUI", "NUW"]),
                                          "muni", "taxable")))
    res["announcement"] = {
        "events_pairable": len(p), "groups_by_ann_date": int(p["ann"].nunique()),
        "groups_by_acquirer_x_ann": int(p.groupby(["acq", "ann"]).ngroups),
        "skips": ann_skips,
        "pair": summ(p["pair_A1_to_close"]), "pair_orig_zero_fill": summ(p["pair_A1_orig_zero_fill"]),
        "spread_A1": summ(p["spread_A1"]), "spread_T1": summ(p["spread_T1"]),
        "by_class_median_bp": {c: [int(len(g)), round(g["pair_A1_to_close"].median() * 1e4, 1)]
                               for c, g in p.groupby("cls")},
        "signed_by_hindsight_median_bp": round((np.sign(p["spread_A1"]) * p["pair_A1_to_close"]).median() * 1e4, 1),
        "labels": p.groupby("label")["ann"].nunique().to_dict(),
        "verified_dates_only": summ(p.loc[p["label"] == "V", "pair_A1_to_close"]),
    }
    gc = g1c_counts(x_all)
    gc.to_csv(OUT / "merger_g1c_counts.csv", index=False)
    res["g1c"] = gc.to_dict(orient="records")
    (OUT / "merger_summary.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))
    if args.edgar_dates:
        # A separate file, so merger_summary.json stays the 2026-10-11 re-run's
        # output whether or not EDGAR dates exist.
        er = edgar_report(x, px, ann)
        er["dsf_last_date"] = res["dsf_last_date"]
        (OUT / "merger_ann_edgar_summary.json").write_text(json.dumps(er, indent=1, default=str))
        print(json.dumps(er, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
